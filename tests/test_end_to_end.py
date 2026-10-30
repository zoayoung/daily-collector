"""全链路验收：夹具采集 → 分析 → 整理 → 校验 → 评分 → 渲染。

唯一 seam 仍是 CLI + 产物文件 + FixtureServer；日报与 token 报告由测试按
spec 的「渲染模板」机械生成，不新增生产脚本。
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from tests.support import (
    NEW_REPOS_CHANNEL,
    FixtureServer,
    render_report,
    run_cli,
    search_request,
)

DAY = "2026-10-21"
WINDOW_HISTORY_DAY = "2026-10-10"
OLD_HISTORY_DAY = "2026-08-01"
WINDOW_REPO = "window/repo"
OLD_REPO = "legacy/repo"
RANGES = ("100..500", "500..2000", "2000..10000", ">10000")
CORE = (
    "该项目提供向量检索与推理调度能力，支持多模态输入与 RAG 工作流，"
    "适合在本地服务中评估其架构与吞吐表现。"
)
WHY = "适合对照其调度实现，建议关注后续版本的并发与延迟优化。"


def search_item(full_name: str, stars: int) -> dict:
    return {
        "full_name": full_name,
        "html_url": f"https://github.com/{full_name}",
        "description": "示例项目",
        "language": "Go",
        "stargazers_count": stars,
        "forks_count": 10,
        "created_at": "2020-01-01T00:00:00Z",
        "pushed_at": f"{DAY}T00:00:00Z",
    }


def candidate_pages() -> dict[tuple[str, int], object]:
    """51 个候选：50 个可入榜 + 1 个 30 天窗口内项目。"""
    pages: dict[tuple[str, int], object] = {(star_range, 1): [] for star_range in RANGES}
    items = [search_item(OLD_REPO, 1_900)]
    items.extend(search_item(f"owner/repo{index:02d}", 1_800 - index) for index in range(49))
    items.append(search_item(WINDOW_REPO, 1_700))
    pages[("100..500", 1)] = items
    return pages


def history_markdown(day: str, name: str) -> str:
    return f"# 知识日报 · {day}\n\n### 1. {name}\n"


def analyzed_item(collected: dict, repeat: dict | None) -> dict:
    return {
        **collected,
        "themes": ["向量检索", "推理调度"],
        "repeat": repeat,
        "core": CORE,
        "why": WHY,
    }


def analyze_document(collected: dict) -> dict:
    items = []
    for item in collected["github"]:
        repeat = {"last_seen": OLD_HISTORY_DAY} if item["full_name"] == OLD_REPO else None
        items.append(analyzed_item(item, repeat))
    return {
        "date": DAY,
        "github": items,
        "stats": {
            "github_count": len(items),
            "dropped_recent_duplicates": collected["stats"]["dropped_recent_duplicates"],
        },
        "gaps": [],
    }


def organize_document(analyzed: dict, final_count: int) -> dict:
    ranked = [
        {**item, "rank": index}
        for index, item in enumerate(analyzed["github"][:final_count], start=1)
    ]
    return {
        "date": DAY,
        "github": ranked,
        "overview": {
            "lead": "今日项目集中在向量检索与推理调度方向。",
            "themes": [{"name": "向量检索", "note": "检索与推理调度项目最活跃。"}],
        },
        "stats": {
            "github_count": len(ranked),
            "dropped_recent_duplicates": analyzed["stats"]["dropped_recent_duplicates"],
            "dropped_by_organize": len(analyzed["github"]) - len(ranked),
        },
        "gaps": ["按内容相关度批量剔除，保留当天最值得关注的条目。"],
    }


def report_entries(markdown: str) -> list[str]:
    return re.findall(r"^###\s+\d+\.\s+(\S+)\s*$", markdown, flags=re.MULTILINE)


def collect_without_stats(name: str = "owner/old") -> dict:
    return {
        "date": DAY,
        "collected_at": f"{DAY} 08:00",
        "github": [
            {
                "full_name": name,
                "url": f"https://github.com/{name}",
                "description": "示例项目",
                "language": "Go",
                "stars_total": 1200,
                "stars_today": 30,
                "stars_today_source": "star_history",
                "forks": 80,
                "created_at": "2020-01-01",
                "pushed_at": DAY,
            }
        ],
        "gaps": [],
    }


class EndToEndTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.work = self.root / "work"
        self.daily = self.root / "daily-knowledge"
        self.daily.mkdir(parents=True)
        (self.daily / f"{WINDOW_HISTORY_DAY}.md").write_text(
            history_markdown(WINDOW_HISTORY_DAY, WINDOW_REPO), encoding="utf-8"
        )
        (self.daily / f"{OLD_HISTORY_DAY}.md").write_text(
            history_markdown(OLD_HISTORY_DAY, OLD_REPO), encoding="utf-8"
        )

    def write(self, name: str, document: dict) -> Path:
        path = self.work / DAY / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return path

    def run_cli(self, script: str, *args: str, api: str | None = None):
        return run_cli(
            script,
            *args,
            work_dir=self.work,
            output_dir=self.daily,
            api=api,
        )

    def test_fixture_pipeline_produces_publishable_report(self) -> None:
        with FixtureServer(search_pages=candidate_pages()) as server:
            collected = self.run_cli("collect.py", "--date", DAY, api=server.url)
            searched = {
                search_request(path)[0]
                for path in server.requests
                if path.startswith("/search/repositories")
            }
            self.assertEqual(searched, set(RANGES) | {NEW_REPOS_CHANNEL})
        self.assertEqual(collected.returncode, 0, collected.stdout + collected.stderr)

        collect = json.loads((self.work / DAY / "collect.json").read_text(encoding="utf-8"))
        stats = collect["stats"]
        self.assertEqual(len(collect["github"]), 50)
        self.assertEqual(stats["candidates"] - stats["dropped_recent_duplicates"], stats["eligible"])
        self.assertEqual(stats["candidates"], 51)
        self.assertEqual(stats["eligible"], 50)
        self.assertEqual(stats["dropped_recent_duplicates"], 1)
        self.assertNotIn(WINDOW_REPO, [item["full_name"] for item in collect["github"]])

        analyzed = analyze_document(collect)
        analyze_path = self.write("analyze.json", analyzed)
        validated = self.run_cli("validate.py", "--file", str(analyze_path))
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)

        organized = organize_document(analyzed, final_count=12)
        organize_path = self.write("organize.json", organized)
        validated = self.run_cli("validate.py", "--file", str(organize_path))
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)

        scored = self.run_cli("score.py", "--file", str(organize_path), "--json")
        self.assertEqual(scored.returncode, 0, scored.stdout + scored.stderr)
        score = json.loads(scored.stdout)
        self.assertTrue(score["valid"])
        self.assertTrue(score["pass"], score["summary"])

        report = render_report(organized, score)
        (self.daily / f"{DAY}.md").write_text(report, encoding="utf-8")

        entries = report_entries(report)
        self.assertGreaterEqual(len(entries), 10)
        self.assertLessEqual(len(entries), 15)
        self.assertEqual(len(entries), len(organized["github"]))
        self.assertNotIn(WINDOW_REPO, entries)
        self.assertNotIn("新进展", report)
        self.assertIn(f"🔁 重复：上次 {OLD_HISTORY_DAY}", report)
        self.assertGreaterEqual(stats["eligible"], len(collect["github"]))
        self.assertGreaterEqual(len(collect["github"]), len(organized["github"]))
        self.assertGreaterEqual(len(organized["github"]), len(entries))
        for item in score["items"]:
            self.assertIn(
                f"评分：{item['total']} / {item['grade']}",
                report,
            )

    def test_legacy_collect_without_stats_still_passes_all(self) -> None:
        legacy = self.root / "legacy-work"
        path = legacy / DAY / "collect.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(collect_without_stats(), ensure_ascii=False),
            encoding="utf-8",
        )

        result = run_cli(
            "validate.py",
            "--all",
            work_dir=legacy,
            output_dir=self.daily,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(DAY, result.stdout)


if __name__ == "__main__":
    unittest.main()
