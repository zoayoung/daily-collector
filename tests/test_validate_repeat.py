"""校验脚本的回归测试：repeat 历史从 daily-knowledge/ 读取。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.support import run_cli

DAY = "2026-10-22"
HISTORY_DAY = "2026-08-31"


def analyze_document(last_seen: str, new_progress: str | None) -> dict:
    return {
        "date": DAY,
        "github": [
            {
                "full_name": "owner/repo",
                "url": "https://github.com/owner/repo",
                "description": "示例项目",
                "language": "Go",
                "stars_total": 1200,
                "stars_today": 30,
                "stars_today_source": "local_diff",
                "forks": 80,
                "created_at": "2020-01-01",
                "pushed_at": DAY,
                "themes": [],
                "repeat": {"last_seen": last_seen, "new_progress": new_progress},
                "core": "示例项目的分析要点。",
                "why": "示例项目的评价与建议。",
            }
        ],
        "stats": {"github_count": 1, "dropped_recent_duplicates": 0},
        "gaps": [],
    }


class ValidateRepeatHistoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name) / "work"
        self.daily = Path(self._tmp.name) / "daily-knowledge"
        self.daily.mkdir(parents=True)
        (self.daily / f"{HISTORY_DAY}.md").write_text(
            "# 历史日报\n\n### 1. owner/repo\n", encoding="utf-8"
        )

    def write_analyze(self, document: dict) -> Path:
        path = self.work / DAY / "analyze.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return path

    def test_repeat_history_is_read_from_daily_knowledge(self) -> None:
        self.write_analyze(analyze_document(HISTORY_DAY, None))

        result = run_cli("validate.py", "--date", DAY, work_dir=self.work, output_dir=self.daily)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_repeat_history_error_names_daily_knowledge(self) -> None:
        self.write_analyze(analyze_document("2026-08-30", None))

        result = run_cli("validate.py", "--date", DAY, work_dir=self.work, output_dir=self.daily)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("daily-knowledge/", result.stdout)
        self.assertNotIn("output/", result.stdout)


if __name__ == "__main__":
    unittest.main()
