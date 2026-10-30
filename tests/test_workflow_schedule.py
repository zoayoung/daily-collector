"""CI 定时回归：清晨窗口内抢发，且单班必须能在 08:00 前出结论。

GitHub Actions 的 cron 只认 UTC，而且只是 best-effort：整点高负载时会被推迟
数小时，甚至整条丢弃。这里钉住三件事：所有班次都落在 06:00–08:00（UTC+8）、
至少两班冗余、最后一班加上任务超时仍不越过窗口终点。
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "daily-knowledge.yml"

WINDOW_START = 6 * 60
WINDOW_END = 8 * 60


def schedule_crons(text: str) -> list[str]:
    crons = re.findall(r"(?m)^\s*-\s*cron:\s*[\"']([^\"']+)[\"']\s*$", text)
    if not crons:
        raise AssertionError("workflow 未声明 schedule cron")
    return crons


def utc_plus_8(expr: str) -> tuple[int, int]:
    fields = expr.split()
    if len(fields) != 5:
        raise AssertionError(f"cron 字段数不是 5：{expr}")
    minute, hour, day_of_month, month, day_of_week = fields
    if (day_of_month, month, day_of_week) != ("*", "*", "*"):
        raise AssertionError(f"cron 不是每日触发：{expr}")
    return (int(hour) + 8) % 24, int(minute)


def utc_plus_8_minutes(expr: str) -> int:
    hour, minute = utc_plus_8(expr)
    return hour * 60 + minute


def daily_timeout_minutes(text: str) -> int:
    match = re.search(r"(?m)^\s*timeout-minutes:\s*(\d+)\s*$", text)
    if match is None:
        raise AssertionError("workflow 未声明 timeout-minutes")
    return int(match.group(1))


class WorkflowScheduleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.crons = schedule_crons(self.text)

    def test_every_run_lands_in_the_morning_window(self) -> None:
        for cron in self.crons:
            minutes = utc_plus_8_minutes(cron)
            self.assertGreaterEqual(minutes, WINDOW_START, f"{cron} 早于 06:00（UTC+8）")
            self.assertLess(minutes, WINDOW_END, f"{cron} 不早于 08:00（UTC+8）")

    def test_has_more_than_one_attempt(self) -> None:
        self.assertGreaterEqual(len(self.crons), 2, "定时只有一班，调度被推迟时没有兜底")

    def test_last_attempt_finishes_before_window_closes(self) -> None:
        last = max(utc_plus_8_minutes(cron) for cron in self.crons)
        self.assertLessEqual(
            last + daily_timeout_minutes(self.text),
            WINDOW_END,
            "最后一班加上 timeout-minutes 会越过 08:00（UTC+8）",
        )
