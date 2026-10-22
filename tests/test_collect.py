"""采集脚本的回归测试：fixture 回放、响应中断重试、无凭证守门、日期落盘。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.support import FixtureServer, fixture, run_cli

FIXTURE_DATE = "2026-10-21"
FIXTURE_GAIN = 152
RANGES = ("100..500", "500..2000", "2000..10000", ">10000")
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
        self.assertEqual(len(search_calls), 5)
        self.assertEqual(len(data["github"]), 3)

    def test_single_range_failure_is_recorded_as_gap(self) -> None:
        with FixtureServer(search_failures={("500..2000", 1): 500}) as server:
            data = self.collect(server)

        self.assertEqual([entry["full_name"] for entry in data["github"]], EXPECTED_REPOS)
        self.assertTrue(
            any("500..2000" in gap and "失败" in gap for gap in data["gaps"]),
            data["gaps"],
        )

    def test_all_search_failures_abort_without_artifact(self) -> None:
        failures = {(star_range, 1): 500 for star_range in RANGES}
        with FixtureServer(search_failures=failures) as server:
            result = run_cli(
                "collect.py",
                "--date",
                FIXTURE_DATE,
                work_dir=self.work,
                output_dir=self.output,
                api=server.url,
            )

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("搜索 API 未返回任何候选", result.stderr)
        self.assertFalse((self.work / FIXTURE_DATE / "collect.json").exists())

    def test_same_day_collect_is_not_a_baseline(self) -> None:
        path = self.work / FIXTURE_DATE / "collect.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {"github": [{"full_name": name, "stars_total": 0} for name in EXPECTED_REPOS]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with FixtureServer() as server:
            data = self.collect(server)

        self.assertEqual([item["stars_today"] for item in data["github"]], [FIXTURE_GAIN] * 3)
        self.assertTrue(all(item["stars_today_source"] == "star_history" for item in data["github"]))

    def test_gain_date_controls_star_history_window(self) -> None:
        with FixtureServer() as server:
            result = run_cli(
                "collect.py",
                "--date",
                "2026-10-21",
                "--gain-date",
                "2026-10-20",
                "--dry-run",
                work_dir=self.work,
                output_dir=self.output,
                api=server.url,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["date"], "2026-10-21")
        self.assertEqual([item["stars_today"] for item in data["github"]], [335] * 3)

    def test_gain_date_env_controls_star_history_window(self) -> None:
        with FixtureServer() as server:
            result = run_cli(
                "collect.py",
                "--date",
                "2026-10-21",
                "--dry-run",
                work_dir=self.work,
                output_dir=self.output,
                api=server.url,
                extra_env={"KNOWLEDGE_GAIN_DATE": "2026-10-20"},
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["date"], "2026-10-21")
        self.assertEqual([item["stars_today"] for item in data["github"]], [335] * 3)

    def test_default_date_honors_knowledge_date_env(self) -> None:
        override = "2026-10-20"
        with FixtureServer() as server:
            result = run_cli(
                "collect.py",
                "--dry-run",
                work_dir=self.work,
                output_dir=self.output,
                api=server.url,
                extra_env={"KNOWLEDGE_DATE": override},
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["date"], override)
        self.assertEqual([item["stars_today"] for item in data["github"]], [335] * 3)

    def test_invalid_date_env_fails_before_requests(self) -> None:
        cases = (
            ({"KNOWLEDGE_DATE": "2026-13-99"}, []),
            ({"KNOWLEDGE_GAIN_DATE": "2026-13-99"}, ["--date", "2026-10-21"]),
        )
        for extra_env, argv in cases:
            with self.subTest(extra_env=extra_env), FixtureServer() as server:
                result = run_cli(
                    "collect.py",
                    *argv,
                    "--dry-run",
                    work_dir=self.work,
                    output_dir=self.output,
                    api=server.url,
                    extra_env=extra_env,
                )

                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("日期格式非法", result.stderr)
                self.assertEqual(server.requests, [])

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
