"""校验脚本的回归测试：`--all` 跳过没有阶段产物的日期目录。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.support import FixtureServer, run_cli

ARTIFACT_DATE = "2026-10-21"
LATER_DATE = "2026-10-22"


class ValidateAllTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name) / "work"
        self.output = Path(self._tmp.name) / "output"

    def test_all_uses_latest_date_that_has_stage_artifacts(self) -> None:
        with FixtureServer() as server:
            collected = run_cli(
                "collect.py",
                "--date",
                ARTIFACT_DATE,
                work_dir=self.work,
                output_dir=self.output,
                api=server.url,
            )
        self.assertEqual(collected.returncode, 0, collected.stderr)

        tokens_only = self.work / LATER_DATE
        tokens_only.mkdir(parents=True)
        (tokens_only / "tokens.json").write_text(json.dumps({"date": LATER_DATE, "runs": []}), encoding="utf-8")

        result = run_cli("validate.py", "--all", work_dir=self.work, output_dir=self.output)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(ARTIFACT_DATE, result.stdout)
        self.assertNotIn(LATER_DATE, result.stdout)


if __name__ == "__main__":
    unittest.main()
