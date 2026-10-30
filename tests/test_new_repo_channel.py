"""新仓库通道的回归测试：查询条件、两路去重、窗口过滤与通道统计。

测试只通过 collect.py / validate.py 的 CLI 与产物文件观察行为。
"""

from __future__ import annotations

import unittest
import urllib.parse

from tests.support import (
    NEW_REPOS_CHANNEL,
    CliCase,
    collect_document,
    empty_search_pages,
    search_item,
    search_request,
)

DAY = "2026-10-21"
NEW_CUTOFF = "2026-09-21"


def query_of(path: str) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlparse(path).query)


class NewRepoChannelTest(CliCase):
    def new_requests(self, requests: list[str]) -> list[str]:
        return [
            path
            for path in requests
            if path.startswith("/search/repositories")
            and search_request(path)[0] == NEW_REPOS_CHANNEL
        ]

    def test_requests_recent_repos_without_pushed_filter(self) -> None:
        pages = empty_search_pages()
        pages[(NEW_REPOS_CHANNEL, 1)] = [search_item("fresh/hot", 80)]

        data, requests = self.collect(pages)

        new_paths = self.new_requests(requests)
        self.assertEqual([search_request(path)[1] for path in new_paths], [1])
        query = query_of(new_paths[0])
        text = query["q"][0]
        self.assertIn(f"created:>={NEW_CUTOFF}", text)
        self.assertIn("stars:>=50", text)
        self.assertNotIn("pushed:", text)
        self.assertEqual(query["sort"], ["stars"])
        self.assertEqual(query["order"], ["desc"])
        self.assertEqual(query["per_page"], ["100"])
        self.assertEqual([entry["full_name"] for entry in data["github"]], ["fresh/hot"])

    def test_new_channel_fetches_second_page_only_when_first_page_is_full(self) -> None:
        pages = empty_search_pages()
        pages[(NEW_REPOS_CHANNEL, 1)] = [
            search_item(f"new/bulk{index:03d}", 300 - index) for index in range(100)
        ]
        pages[(NEW_REPOS_CHANNEL, 2)] = [search_item("new/second", 50)]

        data, requests = self.collect(pages)

        self.assertEqual(
            sorted(search_request(path)[1] for path in self.new_requests(requests)),
            [1, 2],
        )
        self.assertEqual(data["stats"]["candidates"], 101)
        self.assertEqual(data["stats"]["channels"], {"star_bands": 0, "new_repos": 101})

    def test_new_channel_stops_after_a_short_first_page(self) -> None:
        pages = empty_search_pages()
        pages[(NEW_REPOS_CHANNEL, 1)] = [
            search_item(f"new/short{index:03d}", 300 - index) for index in range(99)
        ]

        _, requests = self.collect(pages)

        self.assertEqual(
            [search_request(path)[1] for path in self.new_requests(requests)], [1]
        )

    def test_merges_channels_case_insensitively_and_counts_each_channel(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [search_item("Shared/Repo", 200)]
        pages[(NEW_REPOS_CHANNEL, 1)] = [search_item("shared/repo", 600), search_item("new/only", 70)]

        data, _ = self.collect(pages)

        self.assertEqual(
            [entry["full_name"] for entry in data["github"]],
            ["Shared/Repo", "new/only"],
        )
        self.assertEqual(
            data["stats"]["channels"], {"star_bands": 1, "new_repos": 1}
        )
        self.assertEqual(data["stats"]["candidates"], 2)
        self.assertEqual(
            sum(data["stats"]["channels"].values()), data["stats"]["candidates"]
        )
        self.assertTrue(any("候选 2 个" in gap for gap in data["gaps"]), data["gaps"])
        self.assertTrue(
            any("（区间 1、新仓库 1）" in gap for gap in data["gaps"]),
            data["gaps"],
        )
        self.assertTrue(
            any("新仓库通道贡献 1 条候选" in gap for gap in data["gaps"]),
            data["gaps"],
        )

    def test_new_channel_candidates_are_filtered_by_duplicate_window(self) -> None:
        self.output.mkdir(parents=True)
        (self.output / "2026-09-21.md").write_text(
            "# 知识日报 · 2026-09-21\n\n### 1. new/old\n", encoding="utf-8"
        )
        pages = empty_search_pages()
        pages[(NEW_REPOS_CHANNEL, 1)] = [search_item("new/old", 90), search_item("new/fresh", 80)]

        data, _ = self.collect(pages)

        self.assertEqual([entry["full_name"] for entry in data["github"]], ["new/fresh"])
        self.assertEqual(data["stats"]["candidates"], 2)
        self.assertEqual(data["stats"]["dropped_recent_duplicates"], 1)
        self.assertEqual(data["stats"]["eligible"], 1)
        self.assertEqual(data["stats"]["channels"], {"star_bands": 0, "new_repos": 2})
        self.assertTrue(
            any("30 天窗口剔除 1 个" in gap for gap in data["gaps"]), data["gaps"]
        )

    def test_new_channel_search_failure_is_recorded(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [search_item("owner/keep", 300)]

        data, _ = self.collect(
            pages, search_failures={(NEW_REPOS_CHANNEL, 1): 500}
        )

        self.assertTrue(
            any("新仓库通道" in gap and "失败" in gap for gap in data["gaps"]),
            data["gaps"],
        )
        self.assertEqual(data["stats"]["channels"], {"star_bands": 1, "new_repos": 0})
        self.assertTrue(
            any("（区间 1、新仓库 0）" in gap for gap in data["gaps"]),
            data["gaps"],
        )
        self.assertTrue(
            any("新仓库通道贡献 0 条候选" in gap for gap in data["gaps"]),
            data["gaps"],
        )


class ChannelStatsValidationTest(CliCase):
    def test_old_collect_without_channels_still_passes(self) -> None:
        path = self.write_collect(
            collect_document(
                DAY, {"candidates": 1, "eligible": 1, "dropped_recent_duplicates": 0}
            )
        )

        result = self.validate("--file", str(path))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_collect_with_channel_stats_passes(self) -> None:
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

    def test_inconsistent_channel_stats_are_rejected(self) -> None:
        path = self.write_collect(
            collect_document(
                DAY,
                {
                    "candidates": 1,
                    "eligible": 1,
                    "dropped_recent_duplicates": 0,
                    "channels": {"star_bands": 2, "new_repos": 0},
                },
            )
        )

        result = self.validate("--file", str(path))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("stats.channels 合计 2 与 stats.candidates=1 不一致", result.stdout)


if __name__ == "__main__":
    unittest.main()
