"""候选池扩容的回归测试：多 star 区间、翻页、50 条上限与统计。

测试只通过 collect.py / validate.py 的 CLI 与产物文件观察行为。
"""

from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime

from tests.support import (
    EXPECTED_STAR_RANGES,
    NEW_REPOS_CHANNEL,
    CliCase,
    collect_document,
    empty_search_pages,
    search_item,
    search_request,
)

DAY = "2026-10-21"


class CandidatePoolTest(CliCase):
    def test_searches_four_star_ranges_and_dedupes_by_full_name(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [search_item("Alpha/One", 100), search_item("Shared/Repo", 200)]
        pages[("500..2000", 1)] = [search_item("shared/repo", 600), search_item("Beta/Two", 800)]

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
        self.assertEqual(searched, set(EXPECTED_STAR_RANGES) | {NEW_REPOS_CHANNEL})

    def searches_in_range(self, requests: list[str], star_range: str) -> list[int]:
        return sorted(
            page
            for path in requests
            if path.startswith("/search/repositories")
            for found_range, page in [search_request(path)]
            if found_range == star_range
        )

    def test_fetches_second_page_only_when_first_page_is_full(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [search_item(f"owner/first{i}", 500 - i) for i in range(100)]
        pages[("100..500", 2)] = [search_item("owner/second-page", 450)]

        _, requests = self.collect(pages)

        self.assertEqual(self.searches_in_range(requests, "100..500"), [1, 2])

    def test_first_page_below_full_does_not_request_second_page(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [search_item(f"owner/short{i}", 500 - i) for i in range(99)]

        _, requests = self.collect(pages)

        self.assertEqual(self.searches_in_range(requests, "100..500"), [1])

    def test_picks_at_most_fifty_by_daily_gain_without_nulls(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [search_item(f"owner/repo{i:02d}", 500 - i) for i in range(60)]

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
        pages = empty_search_pages()
        pages[("100..500", 1)] = [search_item("owner/small", 300), search_item("owner/big", 500)]

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
        pages = empty_search_pages()
        pages[("100..500", 1)] = [
            search_item("owner/alpha", 1000),
            search_item("owner/beta", 900),
            search_item("owner/gamma", 1100),
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
        pages = empty_search_pages()
        pages[("100..500", 1)] = [search_item(f"owner/repo{i:03d}", 900 - i) for i in range(100)]
        pages[("100..500", 2)] = [search_item(f"owner/repo{i:03d}", 800 - i) for i in range(100, 160)]

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
        pages = empty_search_pages()
        pages[("100..500", 1)] = [search_item("Alpha/One", 100), search_item("Shared/Repo", 200)]
        pages[("500..2000", 1)] = [search_item("shared/repo", 600), search_item("Beta/Two", 800)]

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


class CollectStatsValidationTest(CliCase):
    def test_inconsistent_stats_are_rejected(self) -> None:
        path = self.write_collect(
            collect_document(
                DAY,
                {"candidates": 5, "eligible": 4, "dropped_recent_duplicates": 0},
            )
        )

        result = self.validate("--file", str(path))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("stats", result.stdout)

    def test_old_collect_without_stats_still_passes_all(self) -> None:
        self.write_collect(collect_document("2026-10-20"), "2026-10-20")

        result = self.validate("--all")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("2026-10-20", result.stdout)


if __name__ == "__main__":
    unittest.main()
