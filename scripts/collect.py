"""采集脚本：GitHub 搜索 API（4 个 star 区间）→ 今日新增 star → 排序取前 50 → collect.json。

用法：
    uv run python scripts/collect.py --date 2026-10-21
    uv run python scripts/collect.py --date 2026-10-21 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime, timedelta
from http.client import IncompleteRead
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (
    WORK_DIR,
    dedupe_window_days,
    is_date,
    read_json,
    recent_duplicates,
    stamp,
    today,
    write_json,
)

API = (os.environ.get("KNOWLEDGE_GITHUB_API") or "https://api.github.com").rstrip("/")
STAR_RANGES = ("100..500", "500..2000", "2000..10000", ">10000")
MAX_PAGES = 2
PER_PAGE = 100
MAX_HISTORY_CALLS = 100
PICK_LIMIT = 50
MIN_ENTRIES = 10


def token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def headers() -> dict[str, str]:
    result = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "knowledge-daily-collect",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    value = token()
    if value:
        result["Authorization"] = f"Bearer {value}"
    return result


def get_json(url: str):
    """GET 并解析 JSON；对连接中断与网络异常重试，HTTP 错误直接抛出。"""
    last_error: Exception | None = None
    for attempt in range(3):
        request = urllib.request.Request(url, headers=headers())
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            reset = error.headers.get("X-RateLimit-Reset") if error.headers else None
            hint = f"，限流重置时间戳 {reset}" if reset else ""
            auth_hint = "，请检查 GITHUB_TOKEN 是否有效" if error.code == 401 else ""
            raise RuntimeError(f"HTTP {error.code} {url}{hint}{auth_hint}") from error
        except (IncompleteRead, urllib.error.URLError) as error:
            last_error = error
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    reason = getattr(last_error, "reason", last_error)
    raise RuntimeError(f"网络不可达 {url}：{reason}") from last_error


def load_baselines(day: str) -> dict[str, tuple[str, int]]:
    """读取 work/**/collect.json，取日期早于 day 的最近一次 stars_total。"""
    baselines: dict[str, tuple[str, int]] = {}
    if not WORK_DIR.exists():
        return baselines
    for path in sorted(WORK_DIR.glob("*/collect.json")):
        baseline_day = path.parent.name
        if not is_date(baseline_day) or baseline_day >= day:
            continue
        try:
            data = read_json(path)
        except (OSError, ValueError):
            continue
        for repo in data.get("github", []):
            name = repo.get("full_name")
            stars = repo.get("stars_total")
            if not name or not isinstance(stars, int):
                continue
            previous = baselines.get(name)
            if previous is None or baseline_day > previous[0]:
                baselines[name] = (baseline_day, stars)
    return baselines


def search_candidates(day: str) -> list[dict]:
    cutoff = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    collected: list[dict] = []
    for star_range in STAR_RANGES:
        query = f"pushed:>={cutoff} stars:{star_range}"
        for page in range(1, MAX_PAGES + 1):
            params = urllib.parse.urlencode(
                {
                    "q": query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": PER_PAGE,
                    "page": page,
                }
            )
            payload = get_json(f"{API}/search/repositories?{params}")
            items = payload.get("items", [])
            for item in items:
                collected.append(
                    {
                        "full_name": item.get("full_name"),
                        "url": item.get("html_url"),
                        "description": item.get("description"),
                        "language": item.get("language"),
                        "stars_total": item.get("stargazers_count"),
                        "stars_today": None,
                        "stars_today_source": None,
                        "forks": item.get("forks_count"),
                        "created_at": (item.get("created_at") or "")[:10],
                        "pushed_at": (item.get("pushed_at") or "")[:10],
                    }
                )
            if len(items) < PER_PAGE:
                break
    seen: set[str] = set()
    repos: list[dict] = []
    for repo in collected:
        key = (repo.get("full_name") or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        repos.append(repo)
    return repos


def star_history(full_name: str, day: str) -> int | None:
    """官方 star 历史接口：按周返回 {week, total, days[7]}，days[i] 为周内第 i 天新增。"""
    url = f"{API}/repos/{full_name}/stargazers/history"
    try:
        payload = get_json(url)
    except RuntimeError:
        return None
    if not isinstance(payload, list):
        return None
    for bucket in payload:
        if not isinstance(bucket, dict):
            continue
        week = bucket.get("week")
        days = bucket.get("days")
        if not isinstance(week, int) or not isinstance(days, list):
            continue
        start = datetime.fromtimestamp(week, UTC).date()
        for offset, count in enumerate(days[:7]):
            if (start + timedelta(days=offset)).isoformat() == day and isinstance(count, int):
                return count
    return None


def build(day: str) -> dict:
    gaps: list[str] = []
    baselines = load_baselines(day)
    yesterday = (date.fromisoformat(day) - timedelta(days=1)).isoformat()

    candidates = search_candidates(day)
    if not candidates:
        raise RuntimeError("搜索 API 未返回任何候选")

    recent = recent_duplicates(day, dedupe_window_days())
    eligible = [repo for repo in candidates if repo["full_name"].lower() not in recent]
    dropped_recent_duplicates = len(candidates) - len(eligible)
    if not eligible:
        raise RuntimeError("按 30 天重复窗口过滤后没有任何候选")
    stats = {
        "candidates": len(candidates),
        "eligible": len(eligible),
        "dropped_recent_duplicates": dropped_recent_duplicates,
    }

    local_diff = 0
    history_calls = 0
    history_failed = 0

    for repo in eligible:
        name = repo["full_name"]
        baseline = baselines.get(name)
        if baseline and baseline[0] == yesterday:
            repo["stars_today"] = repo["stars_total"] - baseline[1]
            repo["stars_today_source"] = "local_diff"
            local_diff += 1

    pending = [
        repo
        for repo in eligible
        if repo["stars_today_source"] is None
    ]
    pending.sort(key=lambda repo: repo["stars_total"] or 0, reverse=True)
    for repo in pending:
        if history_calls >= MAX_HISTORY_CALLS:
            break
        history_calls += 1
        value = star_history(repo["full_name"], day)
        if value is None:
            history_failed += 1
            gaps.append(f"{repo['full_name']} 未取到 star 历史增量")
            continue
        repo["stars_today"] = value
        repo["stars_today_source"] = "star_history"

    ranked = sorted(
        (repo for repo in eligible if repo["stars_today"] is not None),
        key=lambda repo: repo["stars_today"],
        reverse=True,
    )
    picked = ranked[:PICK_LIMIT]
    if not picked:
        raise RuntimeError(
            "没有任何候选能取到今日新增 star（需要上一自然日的本地基线，或可用的 star 历史接口）"
        )
    missing = [repo["full_name"] for repo in picked if not repo["url"] or not repo["full_name"]]

    gaps.insert(
        0,
        f"候选 {len(candidates)} 个，30 天窗口剔除 {dropped_recent_duplicates} 个，入榜 {len(picked)} 个",
    )
    gaps.append(
        f"star_history 调用 {history_calls} 次（上限 {MAX_HISTORY_CALLS}），失败 {history_failed} 次"
    )
    if len(ranked) > len(picked):
        gaps.append(f"未纳入 {len(ranked) - len(picked)} 个有增量的候选（排名在 {PICK_LIMIT} 之后）")
    if len(picked) < MIN_ENTRIES:
        gaps.append(f"入榜不足 {MIN_ENTRIES} 条（实际 {len(picked)} 条）")
    if missing:
        gaps.append(f"字段缺失：{', '.join(missing)}")

    return {
        "date": day,
        "collected_at": stamp(),
        "github": picked,
        "stats": stats,
        "gaps": gaps,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="采集 GitHub 当日趋势并写入 collect.json")
    parser.add_argument("--date", default=today(), help="归属日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--dry-run", action="store_true", help="只打印 JSON，不落盘")
    args = parser.parse_args()

    if not is_date(args.date):
        print(f"❌ 采集失败；原因：日期格式非法 {args.date}", file=sys.stderr)
        return 2

    if not token():
        print(
            "❌ 采集失败；原因：未配置 GITHUB_TOKEN；"
            "建议：在项目根 .env 或环境变量中提供（见 AGENTS.md「凭证」）",
            file=sys.stderr,
        )
        return 2

    try:
        payload = build(args.date)
    except RuntimeError as error:
        print(f"❌ 采集失败；原因：{error}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    path = write_json(WORK_DIR / args.date / "collect.json", payload)
    print(
        f"✅ 采集完成；产物：{path.relative_to(WORK_DIR.parent).as_posix()}；"
        f"入榜 {len(payload['github'])} 条；gaps：{'有' if payload['gaps'] else '无'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
