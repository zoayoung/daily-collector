"""采集脚本：GitHub 搜索 API（4 个 star 区间 + 新仓库通道）→ 数据归属日新增 star → 排序取前 50 → collect.json。

用法：
    uv run python scripts/collect.py --date 2026-10-21
    uv run python scripts/collect.py --date 2026-10-21 --gain-date 2026-10-20
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
from collections import deque
from datetime import UTC, date, datetime, timedelta
from http.client import IncompleteRead
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (
    WORK_DIR,
    is_date,
    load_validation_rules,
    read_json,
    recent_duplicates,
    stamp,
    today,
    write_json,
)

API = (os.environ.get("KNOWLEDGE_GITHUB_API") or "https://api.github.com").rstrip("/")
STAR_RANGES = ("100..500", "500..2000", "2000..10000", ">10000")
CHANNELS = ("star_bands", "new_repos")
STAR_BANDS_CHANNEL, NEW_REPOS_CHANNEL = CHANNELS
CHANNEL_LABELS = {STAR_BANDS_CHANNEL: "区间", NEW_REPOS_CHANNEL: "新仓库"}
NEW_REPOS_MIN_STARS = 50
NEW_REPOS_WINDOW_DAYS = 30
MAX_PAGES = 2
PER_PAGE = 100
MAX_HISTORY_CALLS = 150
PICK_LIMIT = 50


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


def candidate(item: dict) -> dict:
    return {
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


def search_page(query: str, page: int) -> list[dict]:
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
    return payload.get("items", [])


def search_candidates(
    day: str, gaps: list[str]
) -> tuple[list[dict], dict[str, str]]:
    cutoff = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    collected: list[tuple[str, dict]] = []
    for star_range in STAR_RANGES:
        query = f"pushed:>={cutoff} stars:{star_range}"
        for page in range(1, MAX_PAGES + 1):
            try:
                items = search_page(query, page)
            except RuntimeError as error:
                gaps.append(f"搜索区间 {star_range} 第 {page} 页失败：{error}")
                break
            collected.extend((STAR_BANDS_CHANNEL, candidate(item)) for item in items)
            if len(items) < PER_PAGE:
                break

    new_cutoff = (date.fromisoformat(day) - timedelta(days=NEW_REPOS_WINDOW_DAYS)).isoformat()
    query = f"created:>={new_cutoff} stars:>={NEW_REPOS_MIN_STARS}"
    for page in range(1, MAX_PAGES + 1):
        try:
            items = search_page(query, page)
        except RuntimeError as error:
            gaps.append(f"搜索新仓库通道第 {page} 页失败：{error}")
            break
        collected.extend((NEW_REPOS_CHANNEL, candidate(item)) for item in items)
        if len(items) < PER_PAGE:
            break

    seen: set[str] = set()
    repos: list[dict] = []
    channel_of: dict[str, str] = {}
    for channel, repo in collected:
        key = (repo.get("full_name") or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        repos.append(repo)
        channel_of[key] = channel
    return repos, channel_of


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


def build(day: str, gain_day: str) -> dict:
    gaps: list[str] = []
    rules = load_validation_rules()
    window_days = rules["dedupe_window_days"]
    baselines = load_baselines(day)
    yesterday = (date.fromisoformat(day) - timedelta(days=1)).isoformat()

    candidates, channel_of = search_candidates(day, gaps)
    if not candidates:
        raise RuntimeError("搜索 API 未返回任何候选")

    recent = recent_duplicates(day, window_days)
    eligible = [repo for repo in candidates if repo["full_name"].lower() not in recent]
    dropped_recent_duplicates = len(candidates) - len(eligible)
    if not eligible:
        raise RuntimeError(f"按 {window_days} 天重复窗口过滤后没有任何候选")
    channels = {channel: 0 for channel in CHANNELS}
    for repo in candidates:
        channels[channel_of[repo["full_name"].lower()]] += 1
    stats = {
        "candidates": len(candidates),
        "eligible": len(eligible),
        "dropped_recent_duplicates": dropped_recent_duplicates,
        "channels": channels,
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

    pending_by_channel: dict[str, list[dict]] = {channel: [] for channel in CHANNELS}
    for repo in eligible:
        if repo["stars_today_source"] is None:
            pending_by_channel[channel_of[repo["full_name"].lower()]].append(repo)
    pending: list[dict] = []
    queues = {
        channel: deque(
            sorted(
                pending_by_channel[channel],
                key=lambda repo: repo["stars_total"] or 0,
                reverse=True,
            )
        )
        for channel in CHANNELS
    }
    while any(queues.values()):
        for channel in CHANNELS:
            if queues[channel]:
                pending.append(queues[channel].popleft())

    for repo in pending:
        if history_calls >= MAX_HISTORY_CALLS:
            break
        history_calls += 1
        value = star_history(repo["full_name"], gain_day)
        if value is None:
            history_failed += 1
            gaps.append(f"{repo['full_name']} 未取到 star 历史增量")
            continue
        repo["stars_today"] = value
        repo["stars_today_source"] = "star_history"
    skipped = len(pending) - history_calls

    with_gain = [repo for repo in eligible if repo["stars_today"] is not None]
    all_zero_gain = not any(repo["stars_today"] for repo in with_gain)
    if all_zero_gain:
        ranked = sorted(with_gain, key=lambda repo: repo["stars_total"] or 0, reverse=True)
    else:
        ranked = sorted(with_gain, key=lambda repo: repo["stars_today"], reverse=True)
    picked = ranked[:PICK_LIMIT]
    if not picked:
        raise RuntimeError(
            "没有任何候选能取到数据归属日新增 star（需要上一自然日的本地基线，或可用的 star 历史接口）"
        )
    missing = [repo["full_name"] for repo in picked if not repo["url"] or not repo["full_name"]]

    channel_summary = "、".join(
        f"{CHANNEL_LABELS[channel]} {channels[channel]}" for channel in CHANNELS
    )
    gaps.insert(
        0,
        f"候选 {len(candidates)} 个（{channel_summary}），"
        f"{window_days} 天窗口剔除 {dropped_recent_duplicates} 个，入榜 {len(picked)} 个",
    )
    gaps.append(
        f"star_history 调用 {history_calls} 次（上限 {MAX_HISTORY_CALLS}），失败 {history_failed} 次"
    )
    if skipped > 0:
        gaps.append(
            f"历史增量预算耗尽（上限 {MAX_HISTORY_CALLS} 次），"
            f"另有 {skipped} 个候选未尝试计算增量"
        )
    if len(ranked) > len(picked):
        gaps.append(f"未纳入 {len(ranked) - len(picked)} 个候选（排名在 {PICK_LIMIT} 之后）")
    if picked and not any(repo["stars_today"] for repo in picked):
        gaps.append("数据归属日增量全为 0（数据可能尚未产生），本次按 stars_total 降序排列")
    min_items = rules["collect_min_items"]
    if len(picked) < min_items:
        gaps.append(f"入榜不足 {min_items} 条（实际 {len(picked)} 条）")
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
    parser.add_argument("--date", help="发布日 YYYY-MM-DD（默认取 KNOWLEDGE_DATE，再取今天）")
    parser.add_argument(
        "--gain-date",
        help="数据归属日 YYYY-MM-DD（默认取 KNOWLEDGE_GAIN_DATE，再取 --date；CI 定时任务取发布日前一天）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印 JSON，不落盘")
    args = parser.parse_args()
    day = args.date or os.environ.get("KNOWLEDGE_DATE") or today()
    gain_date = args.gain_date or os.environ.get("KNOWLEDGE_GAIN_DATE") or day

    if not is_date(day):
        print(f"❌ 采集失败；原因：日期格式非法 {day}", file=sys.stderr)
        return 2
    if not is_date(gain_date):
        print(f"❌ 采集失败；原因：数据归属日期格式非法 {gain_date}", file=sys.stderr)
        return 2

    if not token():
        print(
            "❌ 采集失败；原因：未配置 GITHUB_TOKEN；"
            "建议：在项目根 .env 或环境变量中提供（见 AGENTS.md「凭证」）",
            file=sys.stderr,
        )
        return 2

    try:
        payload = build(day, gain_date)
    except RuntimeError as error:
        print(f"❌ 采集失败；原因：{error}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    path = write_json(WORK_DIR / day / "collect.json", payload)
    print(
        f"✅ 采集完成；产物：{path.relative_to(WORK_DIR.parent).as_posix()}；"
        f"入榜 {len(payload['github'])} 条；gaps：{'有' if payload['gaps'] else '无'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
