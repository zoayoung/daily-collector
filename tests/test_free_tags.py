"""自由标签回归测试：任意标签与空数组通过校验，标签评分只按个数分档。

只通过 CLI 与产物文件观察：校验看退出码与输出，评分看 score.py --json 的标签维度。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.support import run_cli

DAY = "2026-10-22"
CORE = "该项目提供向量检索与推理调度能力，支持多模态输入，适合用于 RAG 场景。"
WHY = "适合评估其调度实现，值得跟进后续版本。"


def repo(themes: list[str], name: str = "owner/repo") -> dict:
    return {
        "full_name": name,
        "url": f"https://github.com/{name}",
        "description": "示例项目",
        "language": "Go",
        "stars_total": 1200,
        "stars_today": 30,
        "stars_today_source": "local_diff",
        "forks": 80,
        "created_at": "2020-01-01",
        "pushed_at": DAY,
        "themes": themes,
        "repeat": None,
        "core": CORE,
        "why": WHY,
    }


def analyze_document(themes: list[str]) -> dict:
    return {
        "date": DAY,
        "github": [repo(themes)],
        "stats": {"github_count": 1, "dropped_recent_duplicates": 0},
        "gaps": [],
    }


def organize_document(
    themes: list[str], overview_themes: list[dict] | None = None
) -> dict:
    item = repo(themes)
    item["rank"] = 1
    return {
        "date": DAY,
        "github": [item],
        "overview": {"lead": "今日概览一句话。", "themes": overview_themes or []},
        "stats": {
            "github_count": 1,
            "dropped_recent_duplicates": 0,
            "dropped_by_organize": 0,
        },
        "gaps": [],
    }


class FreeTagsValidateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name) / "work"
        self.output = Path(self._tmp.name) / "daily-knowledge"

    def validate(self, document: dict, name: str = "analyze.json") -> object:
        path = self.work / DAY / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return run_cli(
            "validate.py",
            "--file",
            str(path),
            work_dir=self.work,
            output_dir=self.output,
        )

    def test_arbitrary_tags_are_accepted(self) -> None:
        result = self.validate(analyze_document(["量子计算", "手冲咖啡", "Rust 生态"]))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("topics.md", result.stdout)

    def test_empty_themes_are_accepted(self) -> None:
        result = self.validate(analyze_document([]))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_empty_string_tag_is_rejected(self) -> None:
        result = self.validate(analyze_document(["AI 代理", ""]))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("themes", result.stdout)

    def test_duplicate_tags_are_rejected(self) -> None:
        result = self.validate(analyze_document(["AI 代理", "AI 代理"]))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_non_string_tag_is_rejected(self) -> None:
        result = self.validate(analyze_document([123]))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_merged_overview_group_name_need_not_match_a_tag(self) -> None:
        document = organize_document(
            ["量子计算", "手冲咖啡"],
            [{"name": "前沿探索", "note": "合并后的组名，不对应任何单个标签。"}],
        )

        result = self.validate(document, "organize.json")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("topics.md", result.stdout)
        self.assertNotIn("当日无条目命中", result.stdout)

    def test_overview_allows_at_most_six_groups(self) -> None:
        groups = [{"name": f"组{i}", "note": f"第 {i} 组要点。"} for i in range(6)]
        self.assertEqual(
            self.validate(organize_document(["标签"], groups), "organize.json").returncode,
            0,
        )

        groups.append({"name": "组7", "note": "第七组要点。"})
        result = self.validate(organize_document(["标签"], groups), "organize.json")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("overview", result.stdout)


class FreeTagsScoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name) / "work"
        self.output = Path(self._tmp.name) / "daily-knowledge"

    def tags_dimension(self, themes: list[str], name: str = "owner/repo") -> dict:
        path = self.work / DAY / "organize.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        document = organize_document(themes)
        document["github"][0] = repo(themes, name)
        document["github"][0]["rank"] = 1
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        result = run_cli(
            "score.py",
            "--file",
            str(path),
            "--json",
            "--no-write",
            work_dir=self.work,
            output_dir=self.output,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)["items"][0]["dimensions"]["tags"]

    def test_tags_score_depends_only_on_count(self) -> None:
        zero = self.tags_dimension([])
        one = self.tags_dimension(["标签甲"])
        pairs = [self.tags_dimension(["标签甲", "标签乙"]), self.tags_dimension(["甲", "乙", "丙"])]
        quads = self.tags_dimension(["甲", "乙", "丙", "丁"])
        many = [
            self.tags_dimension(["甲", "乙", "丙", "丁", "戊"]),
            self.tags_dimension(["甲", "乙", "丙", "丁", "戊", "己"]),
        ]

        self.assertEqual(zero["score"], 0)
        self.assertGreater(one["score"], 0)
        self.assertLess(one["score"], one["max"])
        self.assertEqual({item["score"] for item in pairs + [quads]}, {quads["max"]})
        self.assertEqual(quads["score"], quads["max"])
        self.assertTrue(all(0 < item["score"] < item["max"] for item in many))
        self.assertEqual(many[0]["score"], many[1]["score"])

    def test_tags_score_ignores_tag_names_and_content_keywords(self) -> None:
        former_topics = self.tags_dimension(["AI / LLM", "Golang"])
        arbitrary = self.tags_dimension(["量子计算", "手冲咖啡"])

        self.assertEqual(former_topics["score"], arbitrary["score"])
        self.assertEqual(former_topics["max"], arbitrary["max"])


if __name__ == "__main__":
    unittest.main()
