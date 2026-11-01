"""新爆款窗口入配置：改一处天数，采集第三通道与校验分层边界同时变化。

测试只通过 collect.py / validate.py 的 CLI 与产物文件观察行为；
配置用 KNOWLEDGE_CONFIG_DIR 指向临时目录，避免改动仓库默认配置。
"""

from __future__ import annotations

import json
import unittest
import urllib.parse

from tests.support import (
    NEW_7D_CHANNEL,
    CliCase,
    collect_item,
    empty_search_pages,
    search_item,
    search_request,
)

DAY = "2026-10-21"
GAIN = "2026-10-20"
WINDOW = 3
MIN_STARS = 400


def query_of(path: str) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlparse(path).query)


def channel_requests(requests: list[str], channel: str) -> list[str]:
    return [
        path
        for path in requests
        if path.startswith("/search/repositories") and search_request(path)[0] == channel
    ]


class WindowConfigTest(CliCase):
    def setUp(self) -> None:
        super().setUp()
        self.use_config(new_burst_window_days=WINDOW)

    def validate_items(self, items: list[dict]) -> object:
        document = {
            "date": DAY,
            "collected_at": f"{DAY} 08:00",
            "github": items,
            "gaps": [],
        }
        path = self.work / DAY / "collect.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return self.validate("--file", str(path))

    def test_channel_cutoff_and_validation_boundary_follow_the_config(self) -> None:
        pages = empty_search_pages()
        pages[(NEW_7D_CHANNEL, 1)] = [
            search_item("fresh/burst", 150, created_at="2026-10-18T00:00:00Z")
        ]

        _, requests = self.collect(pages, gain_date=GAIN)

        paths = channel_requests(requests, NEW_7D_CHANNEL)
        self.assertIn("created:>=2026-10-17", query_of(paths[0])["q"][0])

        boundary = collect_item("edge/repo", "2026-10-17", 150, 5)
        strict_new = collect_item("new/burst", "2026-10-18", 150, 10)
        old = collect_item("old/repo", "2020-01-01", 5000, 20)
        for items in ([boundary, strict_new, old], [strict_new, old, boundary]):
            with self.subTest(items=[item["full_name"] for item in items]):
                result = self.validate_items(items)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_layering_uses_the_configured_window(self) -> None:
        baseline = self.work / "2026-10-20" / "collect.json"
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text(
            json.dumps(
                {
                    "github": [
                        {"full_name": "new/true", "stars_total": 1100},
                        {"full_name": "mid/false", "stars_total": 1001},
                        {"full_name": "old/big", "stars_total": 1050},
                    ]
                }
            ),
            encoding="utf-8",
        )
        pages = empty_search_pages()
        pages[("500..2000", 1)] = [
            search_item("new/true", 1110, created_at="2026-10-18T00:00:00Z"),
            search_item("mid/false", 1002, created_at="2026-10-16T00:00:00Z"),
            search_item("old/big", 1100, created_at="2020-01-01T00:00:00Z"),
        ]

        data, _ = self.collect(pages)

        self.assertEqual(
            [entry["full_name"] for entry in data["github"]],
            ["new/true", "old/big", "mid/false"],
        )


class MinStarsConfigTest(CliCase):
    def setUp(self) -> None:
        super().setUp()
        self.use_config(new_burst_min_stars=MIN_STARS)

    def validate_items(self, items: list[dict]) -> object:
        document = {
            "date": DAY,
            "collected_at": f"{DAY} 08:00",
            "github": items,
            "gaps": [],
        }
        path = self.work / DAY / "collect.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return self.validate("--file", str(path))

    def test_third_channel_query_follows_the_configured_threshold(self) -> None:
        pages = empty_search_pages()
        pages[(NEW_7D_CHANNEL, 1)] = [
            search_item("fresh/burst", 150, created_at="2026-10-18T00:00:00Z")
        ]

        _, requests = self.collect(pages, gain_date=GAIN)

        paths = channel_requests(requests, NEW_7D_CHANNEL)
        self.assertIn(f"stars:>={MIN_STARS}", query_of(paths[0])["q"][0])

    def test_layering_uses_the_configured_threshold(self) -> None:
        baseline = self.work / "2026-10-20" / "collect.json"
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text(
            json.dumps({"github": [{"full_name": "old/high", "stars_total": 5000}]}),
            encoding="utf-8",
        )
        pages = empty_search_pages()
        pages[("500..2000", 1)] = [search_item("old/high", 5900)]
        pages[(NEW_7D_CHANNEL, 1)] = [
            search_item("fresh/low", 150, created_at="2026-10-18T00:00:00Z")
        ]

        data, _ = self.collect(pages)

        self.assertEqual(
            [entry["full_name"] for entry in data["github"]],
            ["old/high", "fresh/low"],
        )

    def test_validation_layering_uses_the_configured_threshold(self) -> None:
        result = self.validate_items(
            [
                collect_item("old/repo", "2020-01-01", 5000, 10),
                collect_item("fresh/low", "2026-10-19", 150, 5),
            ]
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
