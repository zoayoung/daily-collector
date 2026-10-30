"""候选池扩容的回归测试：多 star 区间、翻页、50 条上限与统计。

测试只通过 collect.py / validate.py 的 CLI 与产物文件观察行为。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from tests.support import NEW_REPOS_CHANNEL, FixtureServer, run_cli, search_request

DAY = "2026-10-21"
RANGES = ("100..500", "500..2000", "2000..10000", ">10000")


def item(full_name: str, stars: int) -> dict:
    return {
        "full_name": full_name,
        "html_url": f"https://github.com/{full_name}",
        "description": "示例项目",
        "language": "Go",
        "stargazers_count": stars,
        "forks_count": 10,
        "created_at": "2020-01-01T00:00:00Z",
        "pushed_at": "2026-10-21T00:00:00Z",
    }


def empty_pages() -> dict[tuple[str, int], object]:
    return {(star_range, 1): [] for star_range in RANGES}


class CandidatePoolTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name) / "work"
        self.output = Path(self._tmp.name) / "daily-knowledge"

    def collect(
        self, search_pages: dict[tuple[str, int], object], **kwargs: object
    ) -> tuple[dict, list[str]]:
        with FixtureServer(search_pages=search_pages, **kwargs) as server:
            result = run_cli(
                "collect.py",
                "--date",
                DAY,
                work_dir=self.work,
                output_dir=self.output,
                api=server.url,
            )
            requests = list(server.requests)
        self.assertEqual(result.returncode, 0, result.stderr)
        path = self.work / DAY / "collect.json"
        return json.loads(path.read_text(encoding="utf-8")), requests

    def test_searches_four_star_ranges_and_dedupes_by_full_name(self) -> None:
        pages = empty_pages()
        pages[("100..500", 1)] = [item("Alpha/One", 100), item("Shared/Repo", 200)]
        pages[("500..2000", 1)] = [item("shared/repo", 600), item("Beta/Two", 800)]

        data, requests = self.collect(pages)

        self.assertEqual(
            [entry["full_name"] for entry in data["github"]],
            ["Alpha/One", "Shared/Repo", "Beta/Two"],
        )
        searched = {
            search_request(path)[0]
            for path in requests
            if path.startswith("/search/repositories")
        }
        self.assertEqual(searched, set(RANGES) | {NEW_REPOS_CHANNEL})

    def searches_in_range(self, requests: list[str], star_range: str) -> list[int]:
        return sorted(
            page
            for path in requests
            if path.startswith("/search/repositories")
            for found_range, page in [search_request(path)]
            if found_range == star_range
        )

    def test_fetches_second_page_only_when_first_page_is_full(self) -> None:
        pages = empty_pages()
        pages[("100..500", 1)] = [item(f"owner/first{i}", 500 - i) for i in range(100)]
        pages[("100..500", 2)] = [item("owner/second-page", 450)]

        _, requests = self.collect(pages)

        self.assertEqual(self.searches_in_range(requests, "100..500"), [1, 2])

    def test_first_page_below_full_does_not_request_second_page(self) -> None:
        pages = empty_pages()
        pages[("100..500", 1)] = [item(f"owner/short{i}", 500 - i) for i in range(99)]

        _, requests = self.collect(pages)

        self.assertEqual(self.searches_in_range(requests, "100..500"), [1])

    def test_picks_at_most_fifty_by_daily_gain_without_nulls(self) -> None:
        pages = empty_pages()
        pages[("100..500", 1)] = [item(f"owner/repo{i:02d}", 500 - i) for i in range(60)]

        data, _ = self.collect(pages)

        entries = data["github"]
        self.assertEqual(len(entries), 50)
        self.assertTrue(all(entry["stars_today"] is not None for entry in entries))
        gains = [entry["stars_today"] for entry in entries]
        self.assertEqual(gains, sorted(gains, reverse=True))
        self.assertEqual(
            [entry["full_name"] for entry in entries],
            [f"owner/repo{i:02d}" for i in range(50)],
        )

    def test_zero_daily_gain_falls_back_to_total_order_and_says_so(self) -> None:
        week = int(datetime(2026, 10, 18, tzinfo=UTC).timestamp())
        history = [{"week": week, "total": 0, "days": [0, 0, 0, 0, 0, 0, 0]}]
        pages = empty_pages()
        pages[("100..500", 1)] = [item("owner/small", 300), item("owner/big", 500)]

        data, _ = self.collect(pages, star_history_body=history)

        self.assertEqual(
            [entry["full_name"] for entry in data["github"]],
            ["owner/big", "owner/small"],
        )
        self.assertEqual([entry["stars_today"] for entry in data["github"]], [0, 0])
        self.assertTrue(any("数据归属日增量全为 0" in gap for gap in data["gaps"]))
        self.assertFalse(any("有增量" in gap for gap in data["gaps"]))

    def test_picks_by_different_local_diff_gains_in_descending_order(self) -> None:
        baseline = self.work / "2026-10-20" / "collect.json"
        baseline.parent.mkdir(parents=True)
        baseline.write_text(
            json.dumps(
                {
                    "github": [
                        {"full_name": "owner/alpha", "stars_total": 990},
                        {"full_name": "owner/beta", "stars_total": 870},
                        {"full_name": "owner/gamma", "stars_total": 1080},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        pages = empty_pages()
        pages[("100..500", 1)] = [
            item("owner/alpha", 1000),
            item("owner/beta", 900),
            item("owner/gamma", 1100),
        ]

        data, requests = self.collect(pages)

        self.assertEqual(
            [entry["full_name"] for entry in data["github"]],
            ["owner/beta", "owner/gamma", "owner/alpha"],
        )
        self.assertEqual(
            [entry["stars_today"] for entry in data["github"]],
            [30, 20, 10],
        )
        self.assertTrue(all(entry["stars_today_source"] == "local_diff" for entry in data["github"]))
        self.assertFalse([path for path in requests if "/stargazers/history" in path])

    def test_star_history_fallback_is_capped_at_one_hundred_fifty_calls(self) -> None:
        pages = empty_pages()
        pages[("100..500", 1)] = [item(f"owner/repo{i:03d}", 900 - i) for i in range(100)]
        pages[("100..500", 2)] = [item(f"owner/repo{i:03d}", 800 - i) for i in range(100, 160)]

        data, requests = self.collect(pages)

        history_calls = [path for path in requests if "/stargazers/history" in path]
        self.assertEqual(len(history_calls), 150)
        self.assertEqual(len(data["github"]), 50)
        self.assertTrue(any("star_history 调用 150 次" in gap for gap in data["gaps"]))

    def test_reports_self_consistent_candidate_stats_after_window_filter(self) -> None:
        self.output.mkdir(parents=True)
        (self.output / "2026-09-21.md").write_text(
            "# 知识日报 · 2026-09-21\n\n### 1. Shared/Repo\n", encoding="utf-8"
        )
        pages = empty_pages()
        pages[("100..500", 1)] = [item("Alpha/One", 100), item("Shared/Repo", 200)]
        pages[("500..2000", 1)] = [item("shared/repo", 600), item("Beta/Two", 800)]

        data, _ = self.collect(pages)

        self.assertEqual(
            data["stats"],
            {
                "candidates": 3,
                "eligible": 2,
                "dropped_recent_duplicates": 1,
                "channels": {"star_bands": 3, "new_repos": 0},
            },
        )
        self.assertEqual(
            data["stats"]["candidates"] - data["stats"]["dropped_recent_duplicates"],
            data["stats"]["eligible"],
        )
        self.assertGreaterEqual(data["stats"]["eligible"], len(data["github"]))


class CollectStatsValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name) / "work"
        self.output = Path(self._tmp.name) / "daily-knowledge"

    def write(self, day: str, document: dict) -> Path:
        path = self.work / day / "collect.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return path

    def collect_document(self, day: str, stats: dict | None) -> dict:
        repo = item("owner/repo", 120)
        document = {
            "date": day,
            "collected_at": f"{day} 08:00",
            "github": [
                {
                    "full_name": repo["full_name"],
                    "url": repo["html_url"],
                    "description": repo["description"],
                    "language": repo["language"],
                    "stars_total": repo["stargazers_count"],
                    "stars_today": 12,
                    "stars_today_source": "star_history",
                    "forks": repo["forks_count"],
                    "created_at": "2020-01-01",
                    "pushed_at": "2026-10-21",
                }
            ],
            "gaps": [],
        }
        if stats is not None:
            document["stats"] = stats
        return document

    def validate(self, *args: str) -> object:
        return run_cli(
            "validate.py",
            *args,
            work_dir=self.work,
            output_dir=self.output,
        )

    def test_inconsistent_stats_are_rejected(self) -> None:
        path = self.write(
            "2026-10-21",
            self.collect_document(
                "2026-10-21",
                {"candidates": 5, "eligible": 4, "dropped_recent_duplicates": 0},
            ),
        )

        result = self.validate("--file", str(path))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("stats", result.stdout)

    def test_old_collect_without_stats_still_passes_all(self) -> None:
        self.write("2026-10-20", self.collect_document("2026-10-20", None))

        result = self.validate("--all")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("2026-10-20", result.stdout)


if __name__ == "__main__":
    unittest.main()
