"""JSON 契约校验：按 schemas/ 校验采集、分析、整理产物。

用法：
    uv run python scripts/validate.py --file work/2026-10-21/collect.json
    uv run python scripts/validate.py --date 2026-10-21
    uv run python scripts/validate.py --all
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (
    DATE_RE,
    OUTPUT_DIR,
    SCHEMA_DIR,
    WORK_DIR,
    cjk_count,
    is_date,
    parse_topics,
    read_json,
    today,
)
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

STAGE_SCHEMAS = {
    "collect": "collect.schema.json",
    "analyze": "analyze.schema.json",
    "organize": "organize.schema.json",
}


def load_registry() -> Registry:
    contracts = read_json(SCHEMA_DIR / "contracts.schema.json")
    return Registry().with_resource(contracts["$id"], Resource.from_contents(contracts))


def _contracts() -> dict:
    return read_json(SCHEMA_DIR / "contracts.schema.json")


def _resolve_ref(ref: str, contracts: dict) -> dict:
    prefix = f"{contracts.get('$id', '')}#/"
    if not ref.startswith(prefix):
        return {}
    node: object = contracts
    for part in ref[len(prefix):].split("/"):
        if not isinstance(node, dict):
            return {}
        node = node.get(part, {})
    return node if isinstance(node, dict) else {}


def _keys(schema: dict, contracts: dict) -> set[str]:
    """从 schema（含 $ref / allOf）推导允许的字段名，避免与 schemas/ 重复手写。"""
    keys = set((schema.get("properties") or {}).keys())
    ref = schema.get("$ref")
    if ref:
        keys |= _keys(_resolve_ref(ref, contracts), contracts)
    for sub in schema.get("allOf") or []:
        keys |= _keys(sub, contracts)
    return keys


def stage_of(path: Path) -> str | None:
    stem = path.name
    for stage in STAGE_SCHEMAS:
        if stem == f"{stage}.json":
            return stage
    return None


def _unknown(value, allowed: set[str], where: str, errors: list[str]) -> None:
    extra = sorted(set(value) - allowed)
    if extra:
        errors.append(f"{where} 出现未知字段：{', '.join(extra)}")


def _history_dates() -> set[str]:
    if not OUTPUT_DIR.exists():
        return set()
    return {path.stem for path in OUTPUT_DIR.glob("*.md") if DATE_RE.match(path.stem)}


def _topic_names() -> set[str]:
    return {topic["name"] for topic in parse_topics()}


def _days_between(earlier: str, later: str) -> int:
    return (date.fromisoformat(later) - date.fromisoformat(earlier)).days


def _check_repeat(item: dict, day: str, history: set[str], where: str, errors: list[str]) -> None:
    repeat = item.get("repeat")
    if not repeat:
        return
    last_seen = repeat.get("last_seen")
    if last_seen not in history:
        errors.append(f"{where} repeat.last_seen={last_seen} 在 output/ 历史中不存在")
        return
    if (
        is_date(last_seen)
        and is_date(day)
        and _days_between(last_seen, day) > 30
        and repeat.get("new_progress")
    ):
        errors.append(f"{where} 30 天外的条目不应写 new_progress")


def _check_themes(item: dict, topics: set[str], where: str, errors: list[str]) -> None:
    themes = item.get("themes")
    if not isinstance(themes, list):
        return
    unknown = sorted(set(themes) - topics)
    if unknown:
        errors.append(f"{where} themes 含 topics.md 之外的主题：{', '.join(unknown)}")


def _check_order(items: list[dict], errors: list[str], where: str) -> None:
    values = [item.get("stars_today") for item in items]
    if all(isinstance(value, int) for value in values) and values != sorted(values, reverse=True):
        errors.append(f"{where} 未按 stars_today 降序排列")


def validate_document(data: dict, stage: str, path: Path | None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    schema = read_json(SCHEMA_DIR / STAGE_SCHEMAS[stage])
    contracts = _contracts()
    validator = Draft202012Validator(schema, registry=load_registry())
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.path)):
        location = "/".join(str(part) for part in error.path) or "(根)"
        errors.append(f"schema：{location}：{error.message}")
    if errors:
        return errors, warnings

    top_keys = set((schema.get("properties") or {}).keys())
    item_keys = _keys(schema["properties"]["github"]["items"], contracts)
    stats_keys = _keys(schema["properties"].get("stats", {}), contracts)
    _unknown(data, top_keys, "顶层", errors)
    day = data.get("date")

    if path is not None and is_date(path.parent.name) and day != path.parent.name:
        errors.append(f"date={day} 与目录名 {path.parent.name} 不一致")

    items = data.get("github") or []
    history = _history_dates()
    names: list[str] = []
    for index, item in enumerate(items, start=1):
        where = f"github[{index}]"
        _unknown(item, item_keys, where, errors)
        names.append(item.get("full_name"))
        if stage != "collect":
            _check_repeat(item, day, history, where, errors)

    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        errors.append(f"github 出现重复仓库：{', '.join(duplicates)}")

    if stage == "collect":
        nulls = [item.get("full_name") for item in items if item.get("stars_today") is None]
        if nulls:
            errors.append(f"collect 不应包含 stars_today=null 的条目：{', '.join(nulls)}")
        if len(items) < 15:
            warnings.append(f"入榜不足 15 条（实际 {len(items)} 条），gaps 中应说明原因")
        _check_order(items, errors, "github")

    if stage in {"analyze", "organize"}:
        topics = _topic_names()
        for index, item in enumerate(items, start=1):
            _check_themes(item, topics, f"github[{index}]", errors)
        stats = data.get("stats") or {}
        _unknown(stats, stats_keys, "stats", errors)
        if stats.get("github_count") != len(items):
            errors.append(f"stats.github_count={stats.get('github_count')} 与条目数 {len(items)} 不一致")
        _check_order(items, errors, "github")

    if stage == "analyze":
        stats = data.get("stats") or {}
        dropped = stats.get("dropped_recent_duplicates")
        if not isinstance(dropped, int) or dropped < 0:
            errors.append("stats.dropped_recent_duplicates 必须是非负整数")

    if stage == "organize":
        ranks = [item.get("rank") for item in items]
        if ranks != list(range(1, len(items) + 1)):
            errors.append(f"rank 必须是 1..{len(items)} 的连续整数，实际为 {ranks}")
        for index, item in enumerate(items, start=1):
            length = cjk_count(item.get("core"))
            if length > 100:
                errors.append(f"github[{index}] core 含 {length} 个汉字，超过 100")
        overview = data.get("overview") or {}
        overview_schema = schema["properties"]["overview"]
        if "$ref" in overview_schema:
            overview_schema = _resolve_ref(overview_schema["$ref"], contracts)
        _unknown(overview, set(overview_schema.get("properties") or {}), "overview", errors)
        theme_keys = _keys(
            ((overview_schema.get("properties") or {}).get("themes") or {}).get("items", {}),
            contracts,
        )
        topic_names = _topic_names()
        used = {theme for item in items for theme in item.get("themes") or []}
        for index, theme in enumerate(overview.get("themes") or [], start=1):
            name = theme.get("name")
            _unknown(theme, theme_keys, f"overview.themes[{index}]", errors)
            if name not in topic_names:
                errors.append(f"overview.themes[{index}].name={name} 不在 topics.md 中")
            if name not in used:
                warnings.append(f"overview.themes[{index}].name={name} 当日无条目命中")
        stats = data.get("stats") or {}
        if not isinstance(stats.get("dropped_by_organize"), int):
            errors.append("stats.dropped_by_organize 必须是整数")

        analyze_path = (path.parent if path else None)
        analyze_path = analyze_path / "analyze.json" if analyze_path else None
        if analyze_path and analyze_path.exists():
            try:
                analyzed = read_json(analyze_path)
            except (OSError, ValueError):
                analyzed = None
            if isinstance(analyzed, dict):
                expected = len(analyzed.get("github") or []) - len(items)
                if stats.get("dropped_by_organize") != expected:
                    errors.append(
                        "stats.dropped_by_organize="
                        f"{stats.get('dropped_by_organize')} 与「分析条目数 - 整理条目数 = {expected}」不一致"
                    )
                analyzed_dropped = (analyzed.get("stats") or {}).get("dropped_recent_duplicates")
                if stats.get("dropped_recent_duplicates") != analyzed_dropped:
                    errors.append(
                        "stats.dropped_recent_duplicates 应沿用 analyze.json 的 "
                        f"{analyzed_dropped}"
                    )
                analyzed_names = {item.get("full_name") for item in analyzed.get("github") or []}
                invented = [name for name in names if name not in analyzed_names]
                if invented:
                    errors.append(f"整理新增了分析阶段不存在的条目：{', '.join(invented)}")

    return errors, warnings


def validate_file(path: Path) -> tuple[list[str], list[str], str | None]:
    stage = stage_of(path)
    if stage is None:
        return [f"无法从文件名判断阶段：{path.name}"], [], None
    try:
        data = read_json(path)
    except FileNotFoundError:
        return [f"文件不存在：{path}"], [], stage
    except ValueError as error:
        return [f"JSON 不可解析：{error}"], [], stage
    if not isinstance(data, dict):
        return ["顶层必须是 JSON 对象"], [], stage
    errors, warnings = validate_document(data, stage, path)
    return errors, warnings, stage


def report(path: Path) -> bool:
    errors, warnings, stage = validate_file(path)
    label = f"{path.as_posix()}（{stage or '未知阶段'}）"
    if errors:
        print(f"❌ 校验未通过：{label}")
        for error in errors:
            print(f"  - {error}")
        for warning in warnings:
            print(f"  · {warning}")
        return False
    print(f"✅ 校验通过：{label}")
    for warning in warnings:
        print(f"  · {warning}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="校验知识采集系统的 JSON 契约")
    parser.add_argument("--file", action="append", default=[], help="待校验文件，可重复")
    parser.add_argument("--date", help="校验某日期的 collect/analyze/organize")
    parser.add_argument("--all", action="store_true", help="校验最近一个 work 日期目录")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args()

    targets: list[Path] = [Path(value) for value in args.file]
    if args.date:
        targets.extend(WORK_DIR / args.date / f"{stage}.json" for stage in STAGE_SCHEMAS)
        targets = [path for path in targets if path.exists()]
    if args.all:
        dates = sorted(path.name for path in WORK_DIR.glob("*") if is_date(path.name))
        if dates:
            targets.extend(WORK_DIR / dates[-1] / f"{stage}.json" for stage in STAGE_SCHEMAS)
            targets = [path for path in targets if path.exists()]
    if not targets:
        targets = [WORK_DIR / today() / f"{stage}.json" for stage in STAGE_SCHEMAS]
        targets = [path for path in targets if path.exists()]
    if not targets:
        print("❌ 校验未通过：未找到可校验的产物", file=sys.stderr)
        return 2

    results = []
    ok = True
    for path in targets:
        errors, warnings, stage = validate_file(path)
        ok = ok and not errors
        results.append(
            {
                "file": path.as_posix(),
                "stage": stage,
                "valid": not errors,
                "errors": errors,
                "warnings": warnings,
            }
        )

    if args.json:
        print(json.dumps({"valid": ok, "results": results}, ensure_ascii=False, indent=2))
    else:
        for path in targets:
            report(path)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
