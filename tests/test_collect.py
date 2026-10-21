"""采集脚本的回归测试：fixture 回放、响应中断重试、无凭证守门、日期落盘。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.support import FixtureServer, fixture, run_cli

FIXTURE_DATE = "2026-10-21"
FIXTURE_GAIN = 152
EXPECTED_REPOS = [item["full_name"] for item in fixture("search_repositories.json")["items"]]


class CollectCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name) / "work"
        self.output = Path(self._tmp.name) / "daily-knowledge"

    def collect(self, server: FixtureServer) -> dict:
        result = run_cli(
            "collect.py",
            "--date",
            FIXTURE_DATE,
            work_dir=self.work,
            output_dir=self.output,
            api=server.url,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        path = self.work / FIXTURE_DATE / "collect.json"
        self.assertTrue(path.exists(), result.stderr)
        return json.loads(path.read_text(encoding="utf-8"))

    def test_parses_weekly_star_history_into_daily_gain(self) -> None:
        with FixtureServer() as server:
            data = self.collect(server)

        self.assertEqual(data["date"], FIXTURE_DATE)
        self.assertRegex(data["collected_at"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        self.assertEqual([item["full_name"] for item in data["github"]], EXPECTED_REPOS)
        self.assertEqual([item["stars_today"] for item in data["github"]], [FIXTURE_GAIN] * 3)
        self.assertTrue(all(item["stars_today_source"] == "star_history" for item in data["github"]))
        self.assertTrue(any("star_history 调用 3 次" in gap for gap in data["gaps"]))

    def test_retries_after_incomplete_response(self) -> None:
        with FixtureServer(break_first_search=True) as server:
            data = self.collect(server)

        search_calls = [path for path in server.requests if path.startswith("/search/repositories")]
        self.assertEqual(len(search_calls), 2)
        self.assertEqual(len(data["github"]), 3)

    def test_fails_without_token_and_makes_no_request(self) -> None:
        with FixtureServer() as server:
            result = run_cli(
                "collect.py",
                "--date",
                FIXTURE_DATE,
                work_dir=self.work,
                output_dir=self.output,
                api=server.url,
                token="",
            )

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("GITHUB_TOKEN", result.stderr)
        self.assertEqual(server.requests, [])
        self.assertFalse((self.work / FIXTURE_DATE / "collect.json").exists())


if __name__ == "__main__":
    unittest.main()
