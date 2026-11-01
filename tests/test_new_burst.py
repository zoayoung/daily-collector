"""新爆款优先的回归测试：第三通道、三路去重、分层排序、边界容错与渲染标记。

测试只通过 collect.py / validate.py 的 CLI 与产物文件观察行为。
"""

from __future__ import annotations

import json
import unittest
import urllib.parse
from datetime import date, timedelta

from tests.support import (
    NEW_7D_CHANNEL,
    NEW_BURST_WINDOW_DAYS,
    NEW_REPOS_CHANNEL,
    CliCase,
    collect_document,
    collect_item,
    empty_search_pages,
    render_report,
    search_item,
    search_request,
)

DAY = "2026-10-21"
GAIN = "2026-10-20"
NEW_7D_CUTOFF = "2026-10-14"
BOUNDARY = (
    date.fromisoformat(DAY) - timedelta(days=NEW_BURST_WINDOW_DAYS + 1)
).isoformat()


def query_of(path: str) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlparse(path).query)


def channel_requests(requests: list[str], channel: str) -> list[str]:
    return [
        path
        for path in requests
        if path.startswith("/search/repositories") and search_request(path)[0] == channel
    ]


def analyzed_item(item: dict) -> dict:
    return {
        **item,
        "themes": ["示例标签"],
        "repeat": None,
        "core": "示例项目的分析要点。",
        "why": "示例项目的评价与建议。",
    }


class New7dChannelTest(CliCase):
    def test_requests_recent_7d_repos_with_gain_date_cutoff(self) -> None:
        pages = empty_search_pages()
        pages[(NEW_7D_CHANNEL, 1)] = [
            search_item("fresh/burst", 120, created_at="2026-10-19T00:00:00Z")
        ]

        data, requests = self.collect(pages, gain_date=GAIN)

        paths = channel_requests(requests, NEW_7D_CHANNEL)
        self.assertEqual([search_request(path)[1] for path in paths], [1])
        query = query_of(paths[0])
        text = query["q"][0]
        self.assertIn("created:>=2026-10-13", text)
        self.assertIn("stars:>=100", text)
        self.assertNotIn("pushed:", text)
        self.assertEqual(query["sort"], ["stars"])
        self.assertEqual(query["order"], ["desc"])
        self.assertEqual(query["per_page"], ["100"])
        self.assertEqual([entry["full_name"] for entry in data["github"]], ["fresh/burst"])

    def test_default_gain_date_uses_publish_day_cutoff(self) -> None:
        pages = empty_search_pages()
        pages[(NEW_7D_CHANNEL, 1)] = [
            search_item("fresh/burst", 120, created_at="2026-10-19T00:00:00Z")
        ]

        _, requests = self.collect(pages)

        paths = channel_requests(requests, NEW_7D_CHANNEL)
        self.assertIn(f"created:>={NEW_7D_CUTOFF}", query_of(paths[0])["q"][0])

    def test_fetches_second_page_only_when_first_page_is_full(self) -> None:
        pages = empty_search_pages()
        pages[(NEW_7D_CHANNEL, 1)] = [
            search_item(f"new7/bulk{index:03d}", 500 - index, created_at="2026-10-19T00:00:00Z")
            for index in range(100)
        ]
        pages[(NEW_7D_CHANNEL, 2)] = [
            search_item("new7/second", 100, created_at="2026-10-19T00:00:00Z")
        ]

        data, requests = self.collect(pages)

        self.assertEqual(
            sorted(search_request(path)[1] for path in channel_requests(requests, NEW_7D_CHANNEL)),
            [1, 2],
        )
        self.assertEqual(data["stats"]["channels"]["new_7d"], 101)

    def test_short_first_page_does_not_request_second_page(self) -> None:
        pages = empty_search_pages()
        pages[(NEW_7D_CHANNEL, 1)] = [
            search_item(f"new7/short{index:03d}", 500 - index, created_at="2026-10-19T00:00:00Z")
            for index in range(99)
        ]

        _, requests = self.collect(pages)

        self.assertEqual(
            [search_request(path)[1] for path in channel_requests(requests, NEW_7D_CHANNEL)],
            [1],
        )

    def test_merges_three_channels_case_insensitively_keeping_first_channel(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [search_item("Shared/Repo", 200)]
        pages[(NEW_REPOS_CHANNEL, 1)] = [
            search_item("shared/repo", 600, created_at="2026-10-01T00:00:00Z")
        ]
        pages[(NEW_7D_CHANNEL, 1)] = [
            search_item("SHARED/REPO", 900, created_at="2026-10-19T00:00:00Z"),
            search_item("fresh/only", 150, created_at="2026-10-19T00:00:00Z"),
        ]

        data, _ = self.collect(pages)

        self.assertEqual(
            sorted(entry["full_name"] for entry in data["github"]),
            ["Shared/Repo", "fresh/only"],
        )
        self.assertEqual(
            data["stats"]["channels"],
            {"star_bands": 1, "new_repos": 0, "new_7d": 1},
        )
        self.assertEqual(data["stats"]["candidates"], 2)
        self.assertEqual(
            sum(data["stats"]["channels"].values()), data["stats"]["candidates"]
        )

    def test_rendered_new_burst_heading_counts_as_history(self) -> None:
        self.output.mkdir(parents=True)
        (self.output / "2026-09-21.md").write_text(
            "# 知识日报 · 2026-09-21\n\n### 1. 🆕 fresh/burst\n", encoding="utf-8"
        )
        pages = empty_search_pages()
        pages[(NEW_7D_CHANNEL, 1)] = [
            search_item("fresh/burst", 150, created_at="2026-10-19T00:00:00Z"),
            search_item("fresh/keep", 140, created_at="2026-10-19T00:00:00Z"),
        ]

        data, _ = self.collect(pages)

        self.assertEqual([entry["full_name"] for entry in data["github"]], ["fresh/keep"])
        self.assertEqual(data["stats"]["dropped_recent_duplicates"], 1)

    def test_gaps_report_new_7d_contribution_and_failure(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [search_item("owner/keep", 300)]
        pages[(NEW_7D_CHANNEL, 1)] = [
            search_item("fresh/burst", 150, created_at="2026-10-19T00:00:00Z")
        ]

        data, _ = self.collect(pages)

        self.assertTrue(
            any("近 7 天新建通道贡献 1 条候选" in gap for gap in data["gaps"]),
            data["gaps"],
        )
        self.assertTrue(
            any("刷星" in gap and "未做自动判定" in gap for gap in data["gaps"]),
            data["gaps"],
        )

        failed, _ = self.collect(
            pages, search_failures={(NEW_7D_CHANNEL, 1): 500}
        )
        self.assertTrue(
            any("近 7 天新建通道" in gap and "失败" in gap for gap in failed["gaps"]),
            failed["gaps"],
        )


class LayeredCollectTest(CliCase):
    def test_new_burst_precedes_old_projects_even_with_lower_gain(self) -> None:
        baseline = self.work / "2026-10-20" / "collect.json"
        baseline.parent.mkdir(parents=True)
        baseline.write_text(
            '{"github": ['
            '{"full_name": "old/high", "stars_total": 1000},'
            '{"full_name": "old/low", "stars_total": 1000},'
            '{"full_name": "new/burst-low", "stars_total": 1000},'
            '{"full_name": "new/burst-high", "stars_total": 1000}'
            "]}",
            encoding="utf-8",
        )
        pages = empty_search_pages()
        pages[("500..2000", 1)] = [
            search_item("old/high", 1100),
            search_item("old/low", 1010),
            search_item("new/burst-low", 1001, created_at="2026-10-19T00:00:00Z"),
            search_item("new/burst-high", 1050, created_at="2026-10-18T00:00:00Z"),
        ]

        data, _ = self.collect(pages)

        self.assertEqual(
            [entry["full_name"] for entry in data["github"]],
            ["new/burst-high", "new/burst-low", "old/high", "old/low"],
        )
        self.assertEqual(
            [entry["stars_today"] for entry in data["github"]],
            [50, 1, 100, 10],
        )

    def test_partial_zero_gain_uses_total_as_tiebreak_within_new_layer(self) -> None:
        baseline = self.work / "2026-10-20" / "collect.json"
        baseline.parent.mkdir(parents=True)
        baseline.write_text(
            json.dumps({"github": [{"full_name": "old/boosted", "stars_total": 300}]}),
            encoding="utf-8",
        )
        history = [{"week": 1792281600, "total": 0, "days": [0, 0, 0, 0, 0, 0, 0]}]
        pages = empty_search_pages()
        pages[("100..500", 1)] = [search_item("old/boosted", 305)]
        pages[(NEW_7D_CHANNEL, 1)] = [
            search_item(f"new/burst{index:02d}", 100 + index, created_at="2026-10-19T00:00:00Z")
            for index in range(50)
        ]

        data, _ = self.collect(pages, star_history_body=history)

        totals = [entry["stars_total"] for entry in data["github"]]
        self.assertEqual(len(totals), 50)
        self.assertEqual(totals, sorted(totals, reverse=True))
        self.assertEqual([entry["stars_today"] for entry in data["github"]], [0] * 50)
        result = self.validate("--file", str(self.work / DAY / "collect.json"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_equal_gain_sorts_by_total_within_layer_and_validates(self) -> None:
        history = [{"week": 1792281600, "total": 14, "days": [0, 0, 0, 7, 0, 0, 0]}]
        pages = empty_search_pages()
        pages[("500..2000", 1)] = [
            search_item("old/small", 900),
            search_item("old/big", 1200),
        ]

        data, _ = self.collect(pages, star_history_body=history)

        self.assertEqual(
            [entry["full_name"] for entry in data["github"]],
            ["old/big", "old/small"],
        )
        self.assertEqual([entry["stars_today"] for entry in data["github"]], [7, 7])
        result = self.validate("--file", str(self.work / DAY / "collect.json"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_all_zero_gain_keeps_layers_and_sorts_by_total_within_layer(self) -> None:
        week = 1792281600
        history = [{"week": week, "total": 0, "days": [0, 0, 0, 0, 0, 0, 0]}]
        pages = empty_search_pages()
        pages[("500..2000", 1)] = [
            search_item("old/small", 1000),
            search_item("new/small", 150, created_at="2026-10-19T00:00:00Z"),
            search_item("old/big", 1999),
            search_item("new/big", 300, created_at="2026-10-18T00:00:00Z"),
        ]

        data, _ = self.collect(pages, star_history_body=history)

        self.assertEqual(
            [entry["full_name"] for entry in data["github"]],
            ["new/big", "new/small", "old/big", "old/small"],
        )
        self.assertEqual([entry["stars_today"] for entry in data["github"]], [0, 0, 0, 0])


class LayeredValidationTest(CliCase):
    def validate_items(self, items: list[dict], stage: str = "collect") -> object:
        if stage == "collect":
            document = {
                "date": DAY,
                "collected_at": f"{DAY} 08:00",
                "github": items,
                "gaps": [],
            }
        elif stage == "analyze":
            analyzed = [analyzed_item(item) for item in items]
            document = {
                "date": DAY,
                "github": analyzed,
                "stats": {"github_count": len(analyzed), "dropped_recent_duplicates": 0},
                "gaps": [],
            }
        else:
            ranked = [{**analyzed_item(item), "rank": index} for index, item in enumerate(items, 1)]
            document = {
                "date": DAY,
                "github": ranked,
                "overview": {"lead": "今日概览一句话。", "themes": []},
                "stats": {
                    "github_count": len(ranked),
                    "dropped_recent_duplicates": 0,
                    "dropped_by_organize": 0,
                },
                "gaps": [],
            }
        path = self.work / DAY / f"{stage}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return self.validate("--file", str(path))

    def old(self, name: str = "old/repo", today: int = 100) -> dict:
        return collect_item(name, "2020-01-01", 5000, today)

    def new(self, name: str = "new/burst", today: int = 5) -> dict:
        return collect_item(name, "2026-10-19", 150, today)

    def test_old_before_new_is_rejected_for_every_stage(self) -> None:
        for stage in ("collect", "analyze", "organize"):
            with self.subTest(stage=stage):
                result = self.validate_items([self.old(), self.new()], stage)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("老项目出现在新爆款之前", result.stdout)

    def test_new_before_old_is_accepted(self) -> None:
        result = self.validate_items([self.new(), self.old()])

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_non_descending_within_new_layer_is_rejected(self) -> None:
        result = self.validate_items(
            [self.new("new/low", 5), self.new("new/high", 10), self.old()]
        )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("新爆款层", result.stdout)

    def test_non_descending_within_old_layer_is_rejected(self) -> None:
        result = self.validate_items(
            [self.new(), self.old("old/low", 10), self.old("old/high", 20)]
        )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("老项目层", result.stdout)

    def test_all_zero_falls_back_to_total_within_layer(self) -> None:
        accepted = self.validate_items(
            [
                collect_item("new/big", "2026-10-18", 300, 0),
                collect_item("new/small", "2026-10-19", 150, 0),
                collect_item("old/big", "2020-01-01", 5000, 0),
                collect_item("old/small", "2020-01-01", 2000, 0),
            ]
        )
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)

        rejected = self.validate_items(
            [
                collect_item("new/small", "2026-10-19", 150, 0),
                collect_item("new/big", "2026-10-18", 300, 0),
                collect_item("old/big", "2020-01-01", 5000, 0),
                collect_item("old/small", "2020-01-01", 2000, 0),
            ]
        )
        self.assertEqual(rejected.returncode, 1, rejected.stdout + rejected.stderr)

    def test_equal_gain_order_is_not_reported_as_error(self) -> None:
        for order in (
            [("old/high", 1200), ("old/low", 900)],
            [("old/low", 900), ("old/high", 1200)],
        ):
            items = [
                collect_item(name, "2020-01-01", total, 7) for name, total in order
            ]
            with self.subTest(order=[name for name, _ in order]):
                result = self.validate_items(items)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_publish_minus_eight_days_boundary_accepts_either_layer(self) -> None:
        boundary = collect_item("edge/repo", BOUNDARY, 150, 5)
        strict_new = self.new()
        old = self.old()

        for items in (
            [boundary, strict_new, old],
            [strict_new, old, boundary],
        ):
            with self.subTest(items=[item["full_name"] for item in items]):
                result = self.validate_items(items)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_created_at_with_time_component_still_hits_boundary_and_layer(self) -> None:
        boundary = collect_item("edge/repo", f"{BOUNDARY}T00:00:00Z", 150, 5)
        strict_new = collect_item("new/burst", "2026-10-19T00:00:00Z", 150, 10)

        result = self.validate_items([boundary, strict_new, self.old()])

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_boundary_does_not_mask_strict_old_before_new(self) -> None:
        boundary = collect_item("edge/repo", BOUNDARY, 150, 5)
        result = self.validate_items([boundary, self.old(), self.new()])

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("老项目出现在新爆款之前", result.stdout)


class ChannelStatsCompatTest(CliCase):
    def test_three_channel_stats_pass(self) -> None:
        path = self.write_collect(
            collect_document(
                DAY,
                {
                    "candidates": 1,
                    "eligible": 1,
                    "dropped_recent_duplicates": 0,
                    "channels": {"star_bands": 0, "new_repos": 0, "new_7d": 1},
                },
            )
        )

        result = self.validate("--file", str(path))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_old_two_channel_stats_still_pass(self) -> None:
        path = self.write_collect(
            collect_document(
                DAY,
                {
                    "candidates": 1,
                    "eligible": 1,
                    "dropped_recent_duplicates": 0,
                    "channels": {"star_bands": 1, "new_repos": 0},
                },
            )
        )

        result = self.validate("--file", str(path))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class NewBurstRenderTest(CliCase):
    def organize(self, items: list[dict]) -> dict:
        ranked = [{**analyzed_item(item), "rank": index} for index, item in enumerate(items, 1)]
        return {
            "date": DAY,
            "github": ranked,
            "overview": {"lead": "今日概览一句话。", "themes": []},
            "stats": {
                "github_count": len(ranked),
                "dropped_recent_duplicates": 0,
                "dropped_by_organize": 0,
            },
            "gaps": [],
        }

    def test_marker_only_on_new_burst_titles(self) -> None:
        report = render_report(
            self.organize(
                [
                    collect_item("new/burst", "2026-10-19", 150, 50),
                    collect_item("old/repo", "2020-01-01", 5000, 100),
                ]
            )
        )

        self.assertIn("### 1. 🆕 new/burst", report)
        self.assertIn("### 2. old/repo", report)
        self.assertEqual(report.count("🆕"), 1)

    def test_boundary_follows_the_given_gain_date(self) -> None:
        organized = self.organize([collect_item("edge/repo", BOUNDARY, 150, 5)])

        self.assertIn("### 1. 🆕 edge/repo", render_report(organized, gain_date=GAIN))
        self.assertNotIn("🆕", render_report(organized))


if __name__ == "__main__":
    unittest.main()
