"""整理定稿回归测试：10–15 条边界、只告警的下限与 repeat 契约收紧。

只通过 validate.py / score.py 的 CLI 与 work 产物观察行为；日报渲染按
spec「渲染模板」在测试内生成，断言重复只输出「🔁 重复：上次」一行。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.support import render_report, run_cli

DAY = "2026-10-22"
HISTORY_DAY = "2026-08-31"
CORE = "该项目提供向量检索与推理调度能力，支持多模态输入，适合用于 RAG 场景。"
WHY = "适合评估其调度实现，值得跟进后续版本。"


def repo(name: str, stars_today: int, repeat: dict | None = None) -> dict:
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
        "themes": ["向量检索", "推理调度"],
        "repeat": repeat,
        "core": CORE,
        "why": WHY,
    }


def analyze_document(items: list[dict]) -> dict:
    return {
        "date": DAY,
        "github": items,
        "stats": {"github_count": len(items), "dropped_recent_duplicates": 0},
        "gaps": [],
    }


def organize_document(
    items: list[dict], dropped_by_organize: int = 0
) -> dict:
    ranked = []
    for index, item in enumerate(items, start=1):
        ranked.append({**item, "rank": index})
    return {
        "date": DAY,
        "github": ranked,
        "overview": {"lead": "今日概览一句话。", "themes": []},
        "stats": {
            "github_count": len(ranked),
            "dropped_recent_duplicates": 0,
            "dropped_by_organize": dropped_by_organize,
        },
        "gaps": [],
    }


def analyzed_items(count: int) -> list[dict]:
    return [repo(f"owner/repo{index:02d}", 100 - index) for index in range(count)]


class OrganizeFinalizeTest(unittest.TestCase):
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

    def test_ten_final_items_are_accepted(self) -> None:
        result = self.validate(self.write("organize.json", organize_document(analyzed_items(10))))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_fifteen_final_items_are_accepted(self) -> None:
        result = self.validate(self.write("organize.json", organize_document(analyzed_items(15))))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_sixteen_final_items_are_rejected(self) -> None:
        result = self.validate(self.write("organize.json", organize_document(analyzed_items(16))))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_below_ten_final_items_warns_and_passes(self) -> None:
        result = self.validate(self.write("organize.json", organize_document(analyzed_items(9))))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("定稿不足 10 条", result.stdout)

    def test_repeat_with_new_progress_is_rejected(self) -> None:
        item = repo(
            "owner/repo",
            30,
            repeat={"last_seen": HISTORY_DAY, "new_progress": None},
        )
        result = self.validate(self.write("analyze.json", analyze_document([item])))

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("new_progress", result.stdout)

    def test_dropped_by_organize_must_equal_analyze_minus_organize(self) -> None:
        self.write("analyze.json", analyze_document(analyzed_items(20)))
        accepted = self.validate(
            self.write(
                "organize.json",
                organize_document(analyzed_items(12), dropped_by_organize=8),
            )
        )
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)

        rejected = self.validate(
            self.write(
                "organize.json",
                organize_document(analyzed_items(12), dropped_by_organize=7),
            )
        )
        self.assertEqual(rejected.returncode, 1, rejected.stdout + rejected.stderr)
        self.assertIn("dropped_by_organize", rejected.stdout)

    def test_fifty_candidates_finalize_twelve_through_validate_and_score(self) -> None:
        self.write("analyze.json", analyze_document(analyzed_items(50)))
        path = self.write(
            "organize.json",
            organize_document(analyzed_items(12), dropped_by_organize=38),
        )

        validated = self.validate(path)
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)

        scored = run_cli(
            "score.py",
            "--file",
            str(path),
            "--json",
            work_dir=self.work,
            output_dir=self.daily,
        )
        self.assertEqual(scored.returncode, 0, scored.stdout + scored.stderr)
        payload = json.loads(scored.stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual(len(payload["items"]), 12)
        self.assertTrue((self.work / DAY / "score.json").exists())

    def test_rendered_report_shows_only_last_seen_for_repeat(self) -> None:
        items = analyzed_items(12)
        items[0] = repo("owner/repeat", 100, repeat={"last_seen": HISTORY_DAY})
        report = render_report(organize_document(items, dropped_by_organize=0))

        self.assertIn("🔁 重复：上次 2026-08-31", report)
        self.assertNotIn("新进展", report)


if __name__ == "__main__":
    unittest.main()
