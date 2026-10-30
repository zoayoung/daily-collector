"""历史增量预算轮转的回归测试：150 次上限、通道交替、本地差分不占预算、失败与耗尽说明。

测试只通过 collect.py CLI 与产物文件观察行为。
"""

from __future__ import annotations

import json
import unittest

from tests.support import (
    NEW_REPOS_CHANNEL,
    CliCase,
    empty_search_pages,
    history_names,
    search_item,
)


class HistoryBudgetRotationTest(CliCase):
    def test_pending_candidates_rotate_between_channels(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [search_item("Band/High", 5000), search_item("Band/Mid", 4000)]
        pages[(NEW_REPOS_CHANNEL, 1)] = [search_item("New/Low", 60), search_item("New/High", 400)]

        data, requests = self.collect(pages)

        self.assertEqual(
            history_names(requests),
            ["Band/High", "New/High", "Band/Mid", "New/Low"],
        )
        self.assertEqual(
            sorted(entry["full_name"] for entry in data["github"]),
            ["Band/High", "Band/Mid", "New/High", "New/Low"],
        )
        self.assertTrue(all(entry["stars_today"] == 152 for entry in data["github"]))

    def test_low_star_new_repo_gains_before_large_band_pool(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [search_item(f"band/repo{index:03d}", 10000 - index) for index in range(100)]
        pages[("100..500", 2)] = [
            search_item(f"band/repo{index:03d}", 9000 - index) for index in range(100, 200)
        ]
        pages[(NEW_REPOS_CHANNEL, 1)] = [search_item("new/low", 50)]
        baseline = self.work / "2026-10-20" / "collect.json"
        baseline.parent.mkdir(parents=True)
        baseline.write_text(
            json.dumps(
                {
                    "github": [
                        {"full_name": f"band/repo{index:03d}", "stars_total": 10000 - index}
                        for index in range(100)
                    ]
                    + [
                        {"full_name": f"band/repo{index:03d}", "stars_total": 9000 - index}
                        for index in range(100, 200)
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        data, requests = self.collect(pages)

        self.assertIn("new/low", history_names(requests))
        self.assertEqual(data["github"][0]["full_name"], "new/low")
        self.assertEqual(data["github"][0]["stars_today"], 152)

    def test_local_diff_candidates_do_not_consume_budget(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [search_item(f"owner/repo{index:03d}", 900 - index) for index in range(100)]
        pages[("100..500", 2)] = [
            search_item(f"owner/repo{index:03d}", 800 - index) for index in range(100, 160)
        ]
        baseline = self.work / "2026-10-20" / "collect.json"
        baseline.parent.mkdir(parents=True)
        baseline.write_text(
            json.dumps(
                {
                    "github": [
                        {"full_name": f"owner/repo{index:03d}", "stars_total": 900 - index}
                        for index in range(10)
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        data, requests = self.collect(pages)

        self.assertEqual(len(history_names(requests)), 150)
        self.assertTrue(any("star_history 调用 150 次（上限 150）" in gap for gap in data["gaps"]))

    def test_budget_exhaustion_is_explained_in_gaps(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [search_item(f"owner/repo{index:03d}", 900 - index) for index in range(100)]
        pages[("100..500", 2)] = [
            search_item(f"owner/repo{index:03d}", 800 - index) for index in range(100, 170)
        ]

        data, requests = self.collect(pages)

        self.assertEqual(len(history_names(requests)), 150)
        self.assertTrue(
            any("预算耗尽" in gap and "20 个候选未尝试计算增量" in gap for gap in data["gaps"]),
            data["gaps"],
        )

    def test_failed_history_calls_are_not_counted_as_untried(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [
            search_item(f"owner/repo{index:03d}", 900 - index) for index in range(100)
        ]
        pages[("100..500", 2)] = [
            search_item(f"owner/repo{index:03d}", 800 - index) for index in range(100, 171)
        ]

        data, requests = self.collect(pages, history_failures={"owner/repo000"})

        self.assertEqual(len(history_names(requests)), 150)
        self.assertTrue(any("失败 1 次" in gap for gap in data["gaps"]), data["gaps"])
        self.assertTrue(
            any("另有 21 个候选未尝试计算增量" in gap for gap in data["gaps"]),
            data["gaps"],
        )
        self.assertFalse(
            any("21 个候选未计算增量" in gap for gap in data["gaps"]), data["gaps"]
        )

    def test_history_failure_is_recorded_and_leaves_candidate_null(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [search_item("owner/fail", 600), search_item("owner/keep", 500)]

        data, _ = self.collect(pages, history_failures={"owner/fail"})

        self.assertEqual([entry["full_name"] for entry in data["github"]], ["owner/keep"])
        self.assertTrue(
            any("owner/fail 未取到 star 历史增量" in gap for gap in data["gaps"]),
            data["gaps"],
        )
        self.assertTrue(any("失败 1 次" in gap for gap in data["gaps"]), data["gaps"])


if __name__ == "__main__":
    unittest.main()
