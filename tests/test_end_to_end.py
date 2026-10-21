"""全链路验收：夹具采集 → 分析 → 整理 → 校验 → 评分 → 渲染。

唯一 seam 仍是 CLI + 产物文件 + FixtureServer；日报与 token 报告由测试按
spec 的「渲染模板」机械生成，不新增生产脚本。
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from tests.support import ROOT, FixtureServer, run_cli, search_request

DAY = "2026-10-21"
WINDOW_HISTORY_DAY = "2026-10-10"
OLD_HISTORY_DAY = "2026-08-01"
WINDOW_REPO = "window/repo"
OLD_REPO = "legacy/repo"
RANGES = ("100..500", "500..2000", "2000..10000", ">10000")
CORE = (
    "该项目提供向量检索与推理调度能力，支持多模态输入与 RAG 工作流，"
    "适合在本地服务中评估其架构与吞吐表现。"
)
WHY = "适合对照其调度实现，建议关注后续版本的并发与延迟优化。"
TOKEN_DATE = "2026-10-22"
TOKEN_KEYS = (
    "messages",
    "input",
    "output",
    "cache_read",
    "cache_write",
    "reasoning",
    "cost",
)


def search_item(full_name: str, stars: int) -> dict:
    return {
        "full_name": full_name,
        "html_url": f"https://github.com/{full_name}",
        "description": "示例项目",
        "language": "Go",
        "stargazers_count": stars,
        "forks_count": 10,
        "created_at": "2020-01-01T00:00:00Z",
        "pushed_at": f"{DAY}T00:00:00Z",
    }


def candidate_pages() -> dict[tuple[str, int], object]:
    """51 个候选：50 个可入榜 + 1 个 30 天窗口内项目。"""
    pages: dict[tuple[str, int], object] = {(star_range, 1): [] for star_range in RANGES}
    items = [search_item(OLD_REPO, 1_900)]
    items.extend(search_item(f"owner/repo{index:02d}", 1_800 - index) for index in range(49))
    items.append(search_item(WINDOW_REPO, 1_700))
    pages[("100..500", 1)] = items
    return pages


def history_markdown(day: str, name: str) -> str:
    return f"# 知识日报 · {day}\n\n### 1. {name}\n"


def analyzed_item(collected: dict, repeat: dict | None) -> dict:
    return {
        **collected,
        "themes": ["向量检索", "推理调度"],
        "repeat": repeat,
        "core": CORE,
        "why": WHY,
    }


def analyze_document(collected: dict) -> dict:
    items = []
    for item in collected["github"]:
        repeat = {"last_seen": OLD_HISTORY_DAY} if item["full_name"] == OLD_REPO else None
        items.append(analyzed_item(item, repeat))
    return {
        "date": DAY,
        "github": items,
        "stats": {
            "github_count": len(items),
            "dropped_recent_duplicates": collected["stats"]["dropped_recent_duplicates"],
        },
        "gaps": [],
    }


def organize_document(analyzed: dict, final_count: int) -> dict:
    ranked = [
        {**item, "rank": index}
        for index, item in enumerate(analyzed["github"][:final_count], start=1)
    ]
    return {
        "date": DAY,
        "github": ranked,
        "overview": {
            "lead": "今日项目集中在向量检索与推理调度方向。",
            "themes": [{"name": "向量检索", "note": "检索与推理调度项目最活跃。"}],
        },
        "stats": {
            "github_count": len(ranked),
            "dropped_recent_duplicates": analyzed["stats"]["dropped_recent_duplicates"],
            "dropped_by_organize": len(analyzed["github"]) - len(ranked),
        },
        "gaps": ["按内容相关度批量剔除，保留当天最值得关注的条目。"],
    }


def render_report(organized: dict, score: dict | None) -> str:
    """按 spec「渲染模板」机械填充；只做排版，不改写文字与数字。"""
    lines = [f"# 知识日报 · {organized['date']}", ""]
    summary = (score or {}).get("summary") if score and score.get("valid") else None
    if summary and summary.get("average") is not None and summary.get("grades"):
        grades = summary["grades"]
        lines.extend(
            [
                (
                    f"> 质量评分：均分 {summary['average']} · "
                    f"A {grades.get('A', 0)} / B {grades.get('B', 0)} / C {grades.get('C', 0)}"
                ),
                "",
            ]
        )

    overview = organized["overview"]
    lines.extend(["## 今日概览", "", overview["lead"], ""])
    for theme in overview["themes"]:
        lines.append(f"- **{theme['name']}**：{theme['note']}")
    lines.extend(["", "## GitHub 趋势", ""])

    scores = {}
    if summary:
        scores = {
            (item["rank"], item["full_name"]): item
            for item in (score or {}).get("items", [])
        }
    for item in organized["github"]:
        tags = " ".join(f"[{tag}]" for tag in item["themes"] or ["其他"])
        star_line = (
            f"- Star：{item['stars_total']:,}（今日 +{item['stars_today']}）"
        )
        matched = scores.get((item["rank"], item["full_name"]))
        if matched:
            star_line += f" · 评分：{matched['total']} / {matched['grade']}"
        lines.extend(
            [
                f"### {item['rank']}. {item['full_name']}",
                "",
                f"- 标签：{tags}",
                star_line,
            ]
        )
        if item.get("repeat"):
            lines.append(f"- 🔁 重复：上次 {item['repeat']['last_seen']}")
        lines.extend(
            [
                f"- 链接：{item['url']}",
                f"- 核心内容：{item['core']}",
                f"- 为什么值得关注：{item['why']}",
                "",
            ]
        )
    return "\n".join(lines)


def report_entries(markdown: str) -> list[str]:
    return re.findall(r"^###\s+\d+\.\s+(\S+)\s*$", markdown, flags=re.MULTILINE)


def collect_without_stats(name: str = "owner/old") -> dict:
    return {
        "date": DAY,
        "collected_at": f"{DAY} 08:00",
        "github": [
            {
                "full_name": name,
                "url": f"https://github.com/{name}",
                "description": "示例项目",
                "language": "Go",
                "stars_total": 1200,
                "stars_today": 30,
                "stars_today_source": "star_history",
                "forks": 80,
                "created_at": "2020-01-01",
                "pushed_at": DAY,
            }
        ],
        "gaps": [],
    }


class EndToEndTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.work = self.root / "work"
        self.daily = self.root / "daily-knowledge"
        self.daily.mkdir(parents=True)
        (self.daily / f"{WINDOW_HISTORY_DAY}.md").write_text(
            history_markdown(WINDOW_HISTORY_DAY, WINDOW_REPO), encoding="utf-8"
        )
        (self.daily / f"{OLD_HISTORY_DAY}.md").write_text(
            history_markdown(OLD_HISTORY_DAY, OLD_REPO), encoding="utf-8"
        )

    def write(self, name: str, document: dict) -> Path:
        path = self.work / DAY / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return path

    def run_cli(self, script: str, *args: str, api: str | None = None):
        return run_cli(
            script,
            *args,
            work_dir=self.work,
            output_dir=self.daily,
            api=api,
        )

    def test_fixture_pipeline_produces_publishable_report(self) -> None:
        with FixtureServer(search_pages=candidate_pages()) as server:
            collected = self.run_cli("collect.py", "--date", DAY, api=server.url)
            searched = {
                search_request(path)[0]
                for path in server.requests
                if path.startswith("/search/repositories")
            }
            self.assertEqual(searched, set(RANGES))
        self.assertEqual(collected.returncode, 0, collected.stdout + collected.stderr)

        collect = json.loads((self.work / DAY / "collect.json").read_text(encoding="utf-8"))
        stats = collect["stats"]
        self.assertEqual(len(collect["github"]), 50)
        self.assertEqual(stats["candidates"] - stats["dropped_recent_duplicates"], stats["eligible"])
        self.assertEqual(stats["candidates"], 51)
        self.assertEqual(stats["eligible"], 50)
        self.assertEqual(stats["dropped_recent_duplicates"], 1)
        self.assertNotIn(WINDOW_REPO, [item["full_name"] for item in collect["github"]])

        analyzed = analyze_document(collect)
        analyze_path = self.write("analyze.json", analyzed)
        validated = self.run_cli("validate.py", "--file", str(analyze_path))
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)

        organized = organize_document(analyzed, final_count=12)
        organize_path = self.write("organize.json", organized)
        validated = self.run_cli("validate.py", "--file", str(organize_path))
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)

        scored = self.run_cli("score.py", "--file", str(organize_path), "--json")
        self.assertEqual(scored.returncode, 0, scored.stdout + scored.stderr)
        score = json.loads(scored.stdout)
        self.assertTrue(score["valid"])
        self.assertTrue(score["pass"], score["summary"])

        report = render_report(organized, score)
        (self.daily / f"{DAY}.md").write_text(report, encoding="utf-8")

        entries = report_entries(report)
        self.assertGreaterEqual(len(entries), 10)
        self.assertLessEqual(len(entries), 15)
        self.assertEqual(len(entries), len(organized["github"]))
        self.assertNotIn(WINDOW_REPO, entries)
        self.assertNotIn("新进展", report)
        self.assertIn(f"🔁 重复：上次 {OLD_HISTORY_DAY}", report)
        self.assertGreaterEqual(stats["eligible"], len(collect["github"]))
        self.assertGreaterEqual(len(collect["github"]), len(organized["github"]))
        self.assertGreaterEqual(len(organized["github"]), len(entries))
        for item in score["items"]:
            self.assertIn(
                f"评分：{item['total']} / {item['grade']}",
                report,
            )

    def test_legacy_collect_without_stats_still_passes_all(self) -> None:
        legacy = self.root / "legacy-work"
        path = legacy / DAY / "collect.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(collect_without_stats(), ensure_ascii=False),
            encoding="utf-8",
        )

        result = run_cli(
            "validate.py",
            "--all",
            work_dir=legacy,
            output_dir=self.daily,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(DAY, result.stdout)


def parse_bucket(cells: list[str]) -> dict:
    values = [int(cell) if cell else 0 for cell in cells]
    return dict(zip(TOKEN_KEYS, values, strict=True))


def parse_token_report(markdown: str) -> tuple[list[dict], dict]:
    """解析 token 报告：按 run 聚合代理行与合计行，并读取当日合计。"""
    runs: list[dict] = []
    daily: dict = {}
    current: dict | None = None
    section = "runs"
    for line in markdown.splitlines():
        if line.startswith("## Run"):
            match = re.match(r"## Run \d+ · (.+?) [–-] (.+)$", line)
            if not match:
                continue
            current = {
                "started_at": match.group(1).strip(),
                "ended_at": match.group(2).strip(),
                "agents": {},
                "total": {},
            }
            runs.append(current)
            section = "runs"
            continue
        if line.startswith("## 当日合计"):
            section = "daily"
            continue
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or cells[0] in {"代理", "消息数"} or set(cells[0]) <= {"-"}:
            continue
        if section == "daily":
            daily = parse_bucket(cells)
        elif current is not None:
            if cells[0] == "合计":
                current["total"] = parse_bucket(cells[1:])
            else:
                current["agents"][cells[0]] = parse_bucket(cells[1:])
    return runs, daily


def sum_buckets(buckets: list[dict]) -> dict:
    return {key: sum(bucket.get(key, 0) for bucket in buckets) for key in TOKEN_KEYS}


class TokenArtifactConsistencyTest(unittest.TestCase):
    def test_token_report_and_usage_artifact_are_consistent(self) -> None:
        report_path = ROOT / "daily-knowledge" / "tokens" / f"{TOKEN_DATE}.md"
        usage_path = ROOT / "work" / TOKEN_DATE / "tokens.json"
        if not report_path.exists() or not usage_path.exists():
            self.skipTest(f"缺少真实 token 产物：{report_path} / {usage_path}")

        runs, daily = parse_token_report(report_path.read_text(encoding="utf-8"))
        usage = json.loads(usage_path.read_text(encoding="utf-8"))
        usage_runs = usage.get("runs") or []
        self.assertTrue(runs)
        self.assertTrue(usage_runs)

        for run in runs:
            self.assertEqual(run["total"], sum_buckets(list(run["agents"].values())))
        self.assertEqual(daily, sum_buckets([run["total"] for run in runs]))

        for run in usage_runs:
            self.assertEqual(run["total"], sum_buckets(list(run["agents"].values())))

        usage_by_start = {run["started_at"]: run for run in usage_runs}
        for run in runs:
            counterpart = usage_by_start.get(run["started_at"])
            if counterpart is None:
                continue
            self.assertEqual(run["agents"], counterpart["agents"])
            self.assertEqual(run["total"], counterpart["total"])
            self.assertEqual(run["started_at"], counterpart["started_at"])


if __name__ == "__main__":
    unittest.main()
