"""CI 定时回归：日报必须在 UTC+8 每天 08:00 触发。

GitHub Actions 的 cron 只认 UTC；14:00 UTC 会变成 22:00 UTC+8，
延迟跨过午夜时还会把日报写到次日。这里把 UTC+8 的触发时刻钉住。
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "daily-knowledge.yml"


def schedule_cron(text: str) -> str:
    match = re.search(r"(?m)^\s*-\s*cron:\s*[\"']([^\"']+)[\"']\s*$", text)
    if match is None:
        raise AssertionError("workflow 未声明 schedule cron")
    return match.group(1)


def utc_plus_8(expr: str) -> tuple[int, int]:
    fields = expr.split()
    if len(fields) != 5:
        raise AssertionError(f"cron 字段数不是 5：{expr}")
    minute, hour, day_of_month, month, day_of_week = fields
    if (day_of_month, month, day_of_week) != ("*", "*", "*"):
        raise AssertionError(f"cron 不是每日触发：{expr}")
    return (int(hour) + 8) % 24, int(minute)


class WorkflowScheduleTest(unittest.TestCase):
    def test_daily_run_is_0800_utc_plus_8(self) -> None:
        cron = schedule_cron(WORKFLOW.read_text(encoding="utf-8"))
        self.assertEqual(utc_plus_8(cron), (8, 0))
