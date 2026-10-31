"""入榜 README 门槛的 CLI 回归测试：404 剔除、非 404 保留、预算与统计。

测试只通过 collect.py / validate.py 的 CLI 与产物文件观察行为。
"""

from __future__ import annotations

import json
import unittest

from tests.support import (
    DEFAULT_DAY,
    CliCase,
    collect_document,
    empty_search_pages,
    readme_names,
    search_item,
)

DAY = DEFAULT_DAY


class ReadmeGateCollectTest(CliCase):
    def test_missing_readme_is_dropped_and_counted(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [
            search_item("owner/no-readme", 300),
            search_item("owner/with-readme", 200),
        ]

        data, requests = self.collect(
            pages, readme_failures={"owner/no-readme": 404}
        )

        self.assertEqual([entry["full_name"] for entry in data["github"]], ["owner/with-readme"])
        self.assertEqual(data["stats"]["readme_dropped"], 1)
        self.assertEqual(data["stats"]["eligible"], 2)
        self.assertGreaterEqual(data["stats"]["eligible"], len(data["github"]))
        self.assertEqual(readme_names(requests), ["owner/no-readme", "owner/with-readme"])
        self.assertTrue(
            any("README 缺失剔除 1 个" in gap for gap in data["gaps"]), data["gaps"]
        )

    def test_non_404_error_keeps_candidate_and_records_gap(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [
            search_item("owner/flaky", 300),
            search_item("owner/fine", 200),
        ]

        data, _ = self.collect(pages, readme_failures={"owner/flaky": 500})

        self.assertEqual(
            [entry["full_name"] for entry in data["github"]],
            ["owner/flaky", "owner/fine"],
        )
        self.assertEqual(data["stats"]["readme_dropped"], 0)
        self.assertTrue(
            any("owner/flaky" in gap and "README" in gap for gap in data["gaps"]),
            data["gaps"],
        )

    def test_readme_check_follows_layered_rank_order(self) -> None:
        baseline = self.work / "2026-10-20" / "collect.json"
        baseline.parent.mkdir(parents=True)
        baseline.write_text(
            json.dumps(
                {
                    "github": [
                        {"full_name": "owner/a", "stars_total": 900},
                        {"full_name": "owner/b", "stars_total": 900},
                        {"full_name": "owner/c", "stars_total": 900},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        pages = empty_search_pages()
        pages[("100..500", 1)] = [
            search_item("owner/c", 960),
            search_item("owner/b", 980),
            search_item("owner/a", 1000),
        ]

        data, requests = self.collect(pages)

        self.assertEqual(
            [entry["full_name"] for entry in data["github"]],
            ["owner/a", "owner/b", "owner/c"],
        )
        self.assertEqual(
            readme_names(requests), ["owner/a", "owner/b", "owner/c"]
        )

    def test_stops_checking_once_fifty_candidates_are_collected(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [
            search_item(f"owner/full{i:02d}", 500 - i) for i in range(60)
        ]

        data, requests = self.collect(pages)

        self.assertEqual(len(data["github"]), 50)
        self.assertEqual(len(readme_names(requests)), 50)
        self.assertFalse(any("未做 README 检查" in gap for gap in data["gaps"]))

    def test_all_readmes_missing_yields_empty_lineup(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [
            search_item("owner/no-readme-a", 300),
            search_item("owner/no-readme-b", 200),
        ]

        data, requests = self.collect(
            pages,
            readme_failures={
                "owner/no-readme-a": 404,
                "owner/no-readme-b": 404,
            },
        )

        self.assertEqual(data["github"], [])
        self.assertEqual(data["stats"]["readme_dropped"], 2)
        self.assertEqual(
            readme_names(requests),
            ["owner/no-readme-a", "owner/no-readme-b"],
        )
        self.assertTrue(
            any(
                "入榜 0 个" in gap and "README 缺失剔除 2 个" in gap
                for gap in data["gaps"]
            ),
            data["gaps"],
        )
        self.assertFalse(
            any("没有任何候选通过 README 检查" in gap for gap in data["gaps"]),
            data["gaps"],
        )

    def test_fewer_than_ten_items_warns_in_gaps_and_validation(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [
            search_item("owner/first", 300),
            search_item("owner/second", 200),
        ]

        data, _ = self.collect(pages)

        self.assertEqual(len(data["github"]), 2)
        self.assertTrue(
            any("入榜不足 10 条（实际 2 条）" in gap for gap in data["gaps"]),
            data["gaps"],
        )
        result = self.validate("--file", str(self.work / DAY / "collect.json"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("入榜不足 10 条（实际 2 条）", result.stdout)

    def test_budget_stops_after_one_hundred_checks_and_reports_untried(self) -> None:
        names = [f"owner/seq{i:03d}" for i in range(120)]
        pages = empty_search_pages()
        pages[("100..500", 1)] = [
            search_item(name, 500 - index) for index, name in enumerate(names[:100])
        ]
        pages[("100..500", 2)] = [
            search_item(name, 400 - index) for index, name in enumerate(names[100:])
        ]
        failures = {name: 404 for name in names[:60]}

        data, requests = self.collect(pages, readme_failures=failures)

        self.assertEqual(len(readme_names(requests)), 100)
        self.assertEqual(len(data["github"]), 40)
        self.assertEqual(data["stats"]["readme_dropped"], 60)
        self.assertTrue(
            any("另有 20 条未做 README 检查" in gap for gap in data["gaps"]),
            data["gaps"],
        )


class ReadmeDroppedValidationTest(CliCase):
    def test_empty_collect_passes_with_visible_warning(self) -> None:
        path = self.write_collect(
            {
                "date": DAY,
                "collected_at": f"{DAY} 08:00",
                "github": [],
                "stats": {
                    "candidates": 2,
                    "eligible": 2,
                    "dropped_recent_duplicates": 0,
                    "readme_dropped": 2,
                    "channels": {"star_bands": 2, "new_repos": 0, "new_7d": 0},
                },
                "gaps": ["README 缺失剔除 2 个，入榜 0 个"],
            }
        )

        result = self.validate("--file", str(path))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("入榜不足 10 条（实际 0 条）", result.stdout)

    def test_new_collect_with_readme_dropped_passes(self) -> None:
        path = self.write_collect(
            collect_document(
                DAY,
                {
                    "candidates": 2,
                    "eligible": 2,
                    "dropped_recent_duplicates": 0,
                    "readme_dropped": 1,
                    "channels": {"star_bands": 2, "new_repos": 0, "new_7d": 0},
                },
            )
        )

        result = self.validate("--file", str(path))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_old_collect_without_readme_dropped_still_passes(self) -> None:
        path = self.write_collect(
            collect_document(
                DAY,
                {
                    "candidates": 2,
                    "eligible": 2,
                    "dropped_recent_duplicates": 0,
                    "channels": {"star_bands": 2, "new_repos": 0, "new_7d": 0},
                },
            )
        )

        result = self.validate("--file", str(path))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_negative_readme_dropped_is_rejected(self) -> None:
        path = self.write_collect(
            collect_document(
                DAY,
                {
                    "candidates": 1,
                    "eligible": 1,
                    "dropped_recent_duplicates": 0,
                    "readme_dropped": -1,
                    "channels": {"star_bands": 1, "new_repos": 0, "new_7d": 0},
                },
            )
        )

        result = self.validate("--file", str(path))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
