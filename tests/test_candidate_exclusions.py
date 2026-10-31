"""候选排除规则的 CLI 回归测试：Awesome 列表、空描述与 excluded 统计。

测试只通过 collect.py / validate.py 的 CLI 与产物文件观察行为。
"""

from __future__ import annotations

import unittest

from tests.support import (
    DEFAULT_DAY,
    CliCase,
    collect_document,
    empty_search_pages,
    search_item,
)

DAY = DEFAULT_DAY
MISSING = object()


def repo(full_name: str, stars: int, description: object = "示例项目") -> dict:
    """构造搜索条目；description=MISSING 时删掉该字段。"""
    item = search_item(full_name, stars)
    if description is MISSING:
        item.pop("description")
    else:
        item["description"] = description
    return item


class CandidateExclusionTest(CliCase):
    def test_excludes_awesome_lists_by_repo_name_and_curated_description(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [
            repo("owner/Awesome-Go", 500),
            repo("owner/curated", 450, "A Curated List of useful tools"),
            repo("owner/plain", 400),
        ]

        data, _ = self.collect(pages)

        self.assertEqual([entry["full_name"] for entry in data["github"]], ["owner/plain"])
        stats = data["stats"]
        self.assertEqual(stats["candidates"], 3)
        self.assertEqual(stats["excluded"], 2)
        self.assertEqual(stats["eligible"], 1)
        self.assertEqual(
            stats["candidates"] - stats["excluded"] - stats["dropped_recent_duplicates"],
            stats["eligible"],
        )
        self.assertEqual(stats["channels"], {"star_bands": 3, "new_repos": 0, "new_7d": 0})
        self.assertTrue(any("排除 2 个" in gap for gap in data["gaps"]), data["gaps"])

    def test_excludes_repositories_without_usable_description(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [
            repo("owner/missing", 500, MISSING),
            repo("owner/null", 450, None),
            repo("owner/blank", 400, "   "),
            repo("owner/empty", 350, ""),
            repo("owner/plain", 300),
        ]

        data, _ = self.collect(pages)

        self.assertEqual([entry["full_name"] for entry in data["github"]], ["owner/plain"])
        stats = data["stats"]
        self.assertEqual(stats["candidates"], 5)
        self.assertEqual(stats["excluded"], 4)
        self.assertEqual(stats["eligible"], 1)
        self.assertEqual(
            stats["candidates"] - stats["excluded"] - stats["dropped_recent_duplicates"],
            stats["eligible"],
        )

    def test_exclusion_happens_before_duplicate_window_filter(self) -> None:
        self.output.mkdir(parents=True)
        (self.output / "2026-09-21.md").write_text(
            "# 知识日报 · 2026-09-21\n\n### 1. owner/awesome-tools\n", encoding="utf-8"
        )
        pages = empty_search_pages()
        pages[("100..500", 1)] = [repo("owner/awesome-tools", 500), repo("owner/plain", 400)]

        data, _ = self.collect(pages)

        stats = data["stats"]
        self.assertEqual(stats["candidates"], 2)
        self.assertEqual(stats["excluded"], 1)
        self.assertEqual(stats["dropped_recent_duplicates"], 0)
        self.assertEqual(stats["eligible"], 1)

    def test_curated_list_prefix_without_article_is_excluded(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [
            repo("owner/curated", 500, "curated list of libraries"),
            repo("owner/plain", 400, "一个普通的开源项目"),
        ]

        data, _ = self.collect(pages)

        self.assertEqual([entry["full_name"] for entry in data["github"]], ["owner/plain"])
        self.assertEqual(data["stats"]["excluded"], 1)


class ExcludedStatsValidationTest(CliCase):
    def test_validation_accepts_identity_with_excluded(self) -> None:
        path = self.write_collect(
            collect_document(
                DAY,
                {
                    "candidates": 4,
                    "excluded": 1,
                    "eligible": 2,
                    "dropped_recent_duplicates": 1,
                    "channels": {"star_bands": 4, "new_repos": 0, "new_7d": 0},
                },
            )
        )

        result = self.validate("--file", str(path))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_validation_rejects_identity_that_ignores_excluded(self) -> None:
        path = self.write_collect(
            collect_document(
                DAY,
                {
                    "candidates": 4,
                    "excluded": 1,
                    "eligible": 4,
                    "dropped_recent_duplicates": 0,
                    "channels": {"star_bands": 4, "new_repos": 0, "new_7d": 0},
                },
            )
        )

        result = self.validate("--file", str(path))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("stats", result.stdout)

    def test_legacy_collect_without_excluded_still_passes(self) -> None:
        path = self.write_collect(
            collect_document(
                DAY,
                {
                    "candidates": 3,
                    "eligible": 2,
                    "dropped_recent_duplicates": 1,
                    "channels": {"star_bands": 3, "new_repos": 0, "new_7d": 0},
                },
            )
        )

        result = self.validate("--file", str(path))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
