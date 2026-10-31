"""topics 贯通测试：采集写入、分析/整理透传、旧产物兼容与非法值拒绝。

测试只通过 collect.py / validate.py 的 CLI 与产物文件观察行为。
"""

from __future__ import annotations

import json
import unittest

from tests.support import CliCase, collect_document, empty_search_pages, search_item

DAY = "2026-10-21"


def collect_item(
    name: str,
    topics: object = None,
    stars: int = 1200,
    stars_today: int = 30,
) -> dict:
    item = {
        "full_name": name,
        "url": f"https://github.com/{name}",
        "description": "示例项目",
        "language": "Go",
        "stars_total": stars,
        "stars_today": stars_today,
        "stars_today_source": "star_history",
        "forks": 80,
        "created_at": "2020-01-01",
        "pushed_at": DAY,
    }
    if topics is not None:
        item["topics"] = topics
    return item


def collect_with(items: list[dict]) -> dict:
    return {
        "date": DAY,
        "collected_at": f"{DAY} 08:00",
        "github": items,
        "gaps": [],
    }


def analyze_item(item: dict) -> dict:
    return {
        **item,
        "themes": ["LLM 应用"],
        "repeat": None,
        "core": "该项目提供向量检索与推理调度能力，适合本地评估。",
        "why": "适合对照其调度实现，关注后续并发优化。",
    }


class TopicsCollectTest(CliCase):
    def test_collect_writes_cleaned_topics_from_search_response(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [
            search_item(
                "owner/with-topics",
                500,
                topics=["llm", "agent", "llm", "", "   ", 7, None],
            ),
            search_item("owner/without-topics", 400),
        ]

        data, _ = self.collect(pages)

        self.assertEqual(
            [entry["full_name"] for entry in data["github"]],
            ["owner/with-topics", "owner/without-topics"],
        )
        self.assertEqual(data["github"][0]["topics"], ["llm", "agent"])
        self.assertEqual(data["github"][1]["topics"], [])
        self.assertEqual(data["stats"]["candidates"], 2)

    def test_collect_gap_passes_when_artifact_contains_topics(self) -> None:
        pages = empty_search_pages()
        pages[("100..500", 1)] = [search_item("owner/tagged", 500, topics=["cli"])]

        data, _ = self.collect(pages)

        self.assertEqual(data["github"][0]["topics"], ["cli"])
        path = self.work / DAY / "collect.json"
        result = self.validate("--file", str(path))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class TopicsPassthroughTest(CliCase):
    def test_analyze_and_organize_keep_topics_and_pass_validation(self) -> None:
        topics = ["llm", "agent"]
        self.write_collect(collect_with([collect_item("owner/repo", topics=topics)]))

        analyzed = {
            "date": DAY,
            "github": [analyze_item(collect_item("owner/repo", topics=topics))],
            "stats": {"github_count": 1, "dropped_recent_duplicates": 0},
            "gaps": [],
        }
        analyze_path = self.work / DAY / "analyze.json"
        analyze_path.write_text(json.dumps(analyzed, ensure_ascii=False), encoding="utf-8")
        result = self.validate("--file", str(analyze_path))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        organized = {
            **analyzed,
            "github": [{**analyzed["github"][0], "rank": 1}],
            "overview": {
                "lead": "今日项目集中在 LLM 应用方向。",
                "themes": [{"name": "LLM 应用", "note": "检索与调度项目最活跃。"}],
            },
            "stats": {
                "github_count": 1,
                "dropped_recent_duplicates": 0,
                "dropped_by_organize": 0,
            },
            "gaps": [],
        }
        organize_path = self.work / DAY / "organize.json"
        organize_path.write_text(json.dumps(organized, ensure_ascii=False), encoding="utf-8")
        result = self.validate("--file", str(organize_path))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_legacy_artifacts_without_topics_still_pass(self) -> None:
        self.write_collect(collect_document(DAY))

        result = self.validate("--all")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class TopicsValidationTest(CliCase):
    def test_invalid_topics_are_rejected(self) -> None:
        cases = {
            "duplicate": ["llm", "llm"],
            "blank": ["llm", ""],
            "non-string": ["llm", 7],
            "not-array": "llm",
        }
        for label, topics in cases.items():
            with self.subTest(label=label):
                path = self.write_collect(collect_with([collect_item("owner/repo", topics=topics)]))

                result = self.validate("--file", str(path))

                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("topics", result.stdout)


if __name__ == "__main__":
    unittest.main()
