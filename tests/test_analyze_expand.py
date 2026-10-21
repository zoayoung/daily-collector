"""分析阶段扩容的回归测试：50 条上限、repeat 简化与统计透传。

只通过 validate.py 的 CLI 与 work/daily-knowledge 产物观察行为。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.support import run_cli

DAY = "2026-10-22"
HISTORY_DAY = "2026-08-31"


def repo(name: str, stars_today: int) -> dict:
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


def analyzed(name: str, stars_today: int = 30, repeat: dict | None = None) -> dict:
    item = repo(name, stars_today)
    item.update(
        {
            "themes": ["示例标签"],
            "repeat": repeat,
            "core": "示例项目的分析要点。",
            "why": "示例项目的评价与建议。",
        }
    )
    return item


def analyze_document(items: list[dict], dropped: int | None = 0) -> dict:
    stats = {"github_count": len(items)}
    if dropped is not None:
        stats["dropped_recent_duplicates"] = dropped
    return {"date": DAY, "github": items, "stats": stats, "gaps": []}


def collect_document(stats: dict | None) -> dict:
    document = {
        "date": DAY,
        "collected_at": f"{DAY} 08:00",
        "github": [repo("owner/repo", 30)],
        "gaps": [],
    }
    if stats is not None:
        document["stats"] = stats
    return document


class AnalyzeValidateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.work = self.root / "work"
        self.daily = self.root / "daily-knowledge"
        self.daily.mkdir(parents=True)
        (self.daily / f"{HISTORY_DAY}.md").write_text(
            "# 历史日报\n\n### 1. owner/repo\n", encoding="utf-8"
        )

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

    def test_fifty_analyzed_items_are_accepted(self) -> None:
        items = [
            analyzed(f"owner/repo{index:02d}", stars_today=50 - index)
            for index in range(50)
        ]

        result = self.validate(self.write("analyze.json", analyze_document(items)))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_fifty_one_analyzed_items_are_rejected(self) -> None:
        items = [
            analyzed(f"owner/repo{index:02d}", stars_today=51 - index)
            for index in range(51)
        ]

        result = self.validate(self.write("analyze.json", analyze_document(items)))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_repeat_with_only_last_seen_is_accepted(self) -> None:
        item = analyzed("owner/repo", repeat={"last_seen": HISTORY_DAY})

        result = self.validate(self.write("analyze.json", analyze_document([item])))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_repeat_with_new_progress_is_rejected(self) -> None:
        item = analyzed(
            "owner/repo",
            repeat={"last_seen": HISTORY_DAY, "new_progress": None},
        )

        result = self.validate(self.write("analyze.json", analyze_document([item])))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("new_progress", result.stdout)

    def test_repeat_without_last_seen_is_rejected(self) -> None:
        item = analyzed("owner/repo", repeat={})

        result = self.validate(self.write("analyze.json", analyze_document([item])))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_stats_dropped_recent_duplicates_must_match_collect(self) -> None:
        self.write(
            "collect.json",
            collect_document(
                {"candidates": 5, "eligible": 4, "dropped_recent_duplicates": 1}
            ),
        )
        item = analyzed("owner/fresh")

        self.assertEqual(
            self.validate(
                self.write("analyze.json", analyze_document([item], dropped=1))
            ).returncode,
            0,
        )
        mismatch = self.validate(
            self.write("analyze.json", analyze_document([item], dropped=0))
        )
        self.assertEqual(mismatch.returncode, 1, mismatch.stdout + mismatch.stderr)
        self.assertIn("dropped_recent_duplicates", mismatch.stdout)

    def test_old_collect_without_stats_treats_dropped_as_zero(self) -> None:
        self.write("collect.json", collect_document(None))
        item = analyzed("owner/fresh")

        accepted = self.validate(
            self.write("analyze.json", analyze_document([item], dropped=0))
        )
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)

        rejected = self.validate(
            self.write("analyze.json", analyze_document([item], dropped=2))
        )
        self.assertEqual(rejected.returncode, 1, rejected.stdout + rejected.stderr)
        self.assertIn("dropped_recent_duplicates", rejected.stdout)


if __name__ == "__main__":
    unittest.main()
