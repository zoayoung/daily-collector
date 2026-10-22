"""30 天重复窗口的回归测试：今天、30 天前、31 天前三个边界。

采集与校验共用 scripts/_common.py 的窗口与历史解析口径，测试只通过 CLI 观察行为。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.support import FixtureServer, run_cli


def daily_markdown(day: str, *names: str) -> str:
    lines = [f"# 知识日报 · {day}", ""]
    for index, name in enumerate(names, start=1):
        lines.extend([f"### {index}. {name}", ""])
    return "\n".join(lines)


def repo(name: str, stars_today: int = 30) -> dict:
    return {
        "full_name": name,
        "url": f"https://github.com/{name}",
        "description": "示例项目",
        "language": "Go",
        "stars_total": 1200,
        "stars_today": stars_today,
        "stars_today_source": "local_diff",
        "forks": 80,
        "created_at": "2020-01-01",
        "pushed_at": "2026-10-22",
    }


def analyzed(name: str, repeat: dict | None) -> dict:
    item = repo(name)
    item.update(
        {
            "themes": [],
            "repeat": repeat,
            "core": "示例项目的分析要点。",
            "why": "示例项目的评价与建议。",
        }
    )
    return item


class CollectWindowTest(unittest.TestCase):
    """采集在计算数据归属日新增 star 之前完成过滤。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name) / "work"
        self.daily = Path(self._tmp.name) / "daily-knowledge"
        self.daily.mkdir(parents=True)

    def write_daily(self, day: str, name: str) -> None:
        (self.daily / f"{day}.md").write_text(daily_markdown(day, name), encoding="utf-8")

    def test_today_is_not_history_and_30_day_edge_is_filtered(self) -> None:
        day = "2026-10-21"
        self.write_daily(day, "public-apis/public-apis")
        self.write_daily("2026-09-21", "freeCodeCamp/freeCodeCamp")
        self.write_daily("2026-09-20", "openclaw/openclaw")

        with FixtureServer() as server:
            result = run_cli(
                "collect.py",
                "--date",
                day,
                work_dir=self.work,
                output_dir=self.daily,
                api=server.url,
            )
            history_calls = [path for path in server.requests if "/stargazers/history" in path]

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads((self.work / day / "collect.json").read_text(encoding="utf-8"))
        self.assertEqual(
            [item["full_name"] for item in payload["github"]],
            ["public-apis/public-apis", "openclaw/openclaw"],
        )
        self.assertTrue(any("30 天窗口剔除 1 个" in gap for gap in payload["gaps"]), payload["gaps"])
        self.assertEqual(len(history_calls), 2)


class ValidateWindowTest(unittest.TestCase):
    """校验对分析/整理产物做硬闸，窗口内零例外。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name) / "work"
        self.daily = Path(self._tmp.name) / "daily-knowledge"
        self.daily.mkdir(parents=True)

    def write_daily(self, day: str, *names: str) -> None:
        (self.daily / f"{day}.md").write_text(daily_markdown(day, *names), encoding="utf-8")

    def write(self, day: str, name: str, document: dict) -> Path:
        path = self.work / day / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return path

    def analyze_document(self, day: str, item: dict) -> dict:
        return {
            "date": day,
            "github": [item],
            "stats": {"github_count": 1, "dropped_recent_duplicates": 0},
            "gaps": [],
        }

    def validate(self, path: Path) -> object:
        return run_cli(
            "validate.py",
            "--file",
            str(path),
            work_dir=self.work,
            output_dir=self.daily,
        )

    def test_30_days_ago_is_rejected_even_with_repeat(self) -> None:
        day = "2026-10-22"
        self.write_daily("2026-09-22", "owner/recent")
        item = analyzed("owner/recent", {"last_seen": "2026-09-22"})

        result = self.validate(self.write(day, "analyze.json", self.analyze_document(day, item)))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("30 天窗口", result.stdout)

    def test_today_published_project_is_not_history(self) -> None:
        day = "2026-10-22"
        self.write_daily(day, "owner/today")
        item = analyzed("owner/today", None)

        result = self.validate(self.write(day, "analyze.json", self.analyze_document(day, item)))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_31_days_ago_repeat_must_equal_latest_publication(self) -> None:
        day = "2026-10-22"
        self.write_daily("2026-08-01", "owner/old")
        self.write_daily("2026-09-21", "owner/old")
        item = analyzed("owner/old", {"last_seen": "2026-08-01"})

        result = self.validate(self.write(day, "analyze.json", self.analyze_document(day, item)))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("最近发布日期 2026-09-21", result.stdout)

    def test_31_days_ago_repeat_with_latest_publication_is_accepted(self) -> None:
        day = "2026-10-22"
        self.write_daily("2026-08-01", "owner/old")
        self.write_daily("2026-09-21", "owner/old")
        item = analyzed("owner/old", {"last_seen": "2026-09-21"})

        result = self.validate(self.write(day, "analyze.json", self.analyze_document(day, item)))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_31_days_ago_requires_repeat(self) -> None:
        day = "2026-10-22"
        self.write_daily("2026-09-21", "owner/old")
        item = analyzed("owner/old", None)

        result = self.validate(self.write(day, "analyze.json", self.analyze_document(day, item)))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("必须写 repeat.last_seen=2026-09-21", result.stdout)

    def test_organize_rejects_window_project(self) -> None:
        day = "2026-10-22"
        self.write_daily("2026-09-22", "owner/recent")
        item = analyzed("owner/recent", None)
        item["rank"] = 1
        document = {
            "date": day,
            "github": [item],
            "overview": {"lead": "今日概览一句话。", "themes": []},
            "stats": {
                "github_count": 1,
                "dropped_recent_duplicates": 0,
                "dropped_by_organize": 0,
            },
            "gaps": [],
        }

        result = self.validate(self.write(day, "organize.json", document))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("30 天窗口", result.stdout)


if __name__ == "__main__":
    unittest.main()
