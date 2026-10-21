"""语义阈值回归测试：去重窗口、最少条数与核心内容上限。

阈值由 config/validation-rules.json 提供，测试只通过 CLI 观察行为是否保持不变。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.support import run_cli

DAY = "2026-10-22"


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
        "pushed_at": DAY,
    }


class ValidationThresholdTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name) / "work"
        self.daily = Path(self._tmp.name) / "daily-knowledge"
        self.daily.mkdir(parents=True)

    def write(self, name: str, document: dict) -> Path:
        path = self.work / DAY / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return path

    def validate(self, path: Path) -> object:
        return run_cli(
            "validate.py",
            "--file",
            str(path),
            work_dir=self.work,
            output_dir=self.daily,
        )

    def test_collect_below_min_items_warns(self) -> None:
        items = [repo(f"owner/repo{i}", 40 - i) for i in range(9)]
        document = {
            "date": DAY,
            "collected_at": "2026-10-22 08:00",
            "github": items,
            "gaps": [],
        }

        result = self.validate(self.write("collect.json", document))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("入榜不足 10 条", result.stdout)

    def test_collect_at_min_items_has_no_warning(self) -> None:
        items = [repo(f"owner/repo{i}", 40 - i) for i in range(10)]
        document = {
            "date": DAY,
            "collected_at": "2026-10-22 08:00",
            "github": items,
            "gaps": [],
        }

        result = self.validate(self.write("collect.json", document))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("入榜不足", result.stdout)

    def analyze_document(self, last_seen: str, new_progress: str | None) -> dict:
        (self.daily / f"{last_seen}.md").write_text(
            "# 历史日报\n\n### 1. owner/repo\n", encoding="utf-8"
        )
        item = repo("owner/repo")
        item.update(
            {
                "themes": ["示例"],
                "repeat": {"last_seen": last_seen, "new_progress": new_progress},
                "core": "示例项目的分析要点。",
                "why": "示例项目的评价与建议。",
            }
        )
        return {
            "date": DAY,
            "github": [item],
            "stats": {"github_count": 1, "dropped_recent_duplicates": 0},
            "gaps": [],
        }

    def test_new_progress_at_window_edge_is_rejected(self) -> None:
        document = self.analyze_document("2026-09-22", "发布了新版本")

        result = self.validate(self.write("analyze.json", document))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("30 天窗口", result.stdout)

    def test_new_progress_beyond_window_is_rejected(self) -> None:
        document = self.analyze_document("2026-09-21", "发布了新版本")

        result = self.validate(self.write("analyze.json", document))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("30 天外的条目不应写 new_progress", result.stdout)

    def organize_document(self, core: str) -> dict:
        item = repo("owner/repo")
        item.update(
            {
                "themes": ["示例"],
                "repeat": None,
                "core": core,
                "why": "示例项目的评价与建议。",
                "rank": 1,
            }
        )
        return {
            "date": DAY,
            "github": [item],
            "overview": {"lead": "今日概览一句话。", "themes": []},
            "stats": {
                "github_count": 1,
                "dropped_recent_duplicates": 0,
                "dropped_by_organize": 0,
            },
            "gaps": [],
        }

    def test_core_at_limit_is_accepted(self) -> None:
        document = self.organize_document("核" * 100)

        result = self.validate(self.write("organize.json", document))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_core_over_limit_is_rejected(self) -> None:
        document = self.organize_document("核" * 101)

        result = self.validate(self.write("organize.json", document))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("超过 100", result.stdout)


if __name__ == "__main__":
    unittest.main()
