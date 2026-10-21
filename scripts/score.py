"""质量评分：5 个维度确定性打分 + A/B/C 等级 + 进度条，写 score.json。

用法：
    uv run python scripts/score.py --file work/2026-10-21/organize.json
    uv run python scripts/score.py --date 2026-10-21 --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (
    CONFIG_DIR,
    WORK_DIR,
    cjk_count,
    is_date,
    read_json,
    stamp,
    today,
    write_json,
)
from validate import validate_file

VERSION_RE = re.compile(r"v?\d+\.\d+(?:\.\d+)?")
METRIC_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:ms|毫秒|秒|%|倍|QPS|TPS|MB|GB|ns|us|核)"
)
NUMBER_RE = re.compile(r"\d{2,}")
DIMENSION_LABELS = {
    "summary": "摘要质量",
    "depth": "技术深度",
    "format": "格式规范",
    "tags": "标签精度",
    "filler": "空洞词",
}


REQUIRED_RULE_KEYS = (
    "grades",
    "dimensions",
    "format_fields",
    "length",
    "filler_words",
    "tech_terms",
    "action_words",
    "advice_words",
)


def load_rules() -> dict:
    path = CONFIG_DIR / "score-rules.json"
    try:
        rules = read_json(path)
    except FileNotFoundError as error:
        raise SystemExit(f"❌ 质量评分失败：找不到评分规则 {path.as_posix()}") from error
    missing = [key for key in REQUIRED_RULE_KEYS if key not in rules]
    if missing:
        raise SystemExit(f"❌ 质量评分失败：{path.as_posix()} 缺少 {', '.join(missing)}")
    return rules


def _hits(text: str, terms: list[str]) -> list[str]:
    lowered = (text or "").lower()
    found = []
    for term in terms:
        if term and term.lower() in lowered and term not in found:
            found.append(term)
    return found


def _score_summary(core: str, rules: dict) -> dict:
    weights = rules["dimensions"]["summary"]
    bands = rules["length"]["summary"]
    factors = bands["factors"]
    length_max = weights["length"]
    length = cjk_count(core)
    best_low, best_high = bands["best"]
    good_low, good_high = bands["good"]
    fair_low, fair_high = bands["fair"][0]
    long_low, long_high = bands["fair"][1]
    if best_low <= length <= best_high:
        length_score = length_max
    elif good_low <= length < good_high:
        length_score = round(length_max * factors["good"])
    elif fair_low <= length < fair_high or long_low < length <= long_high:
        length_score = round(length_max * factors["fair"])
    elif length > bands["long_over"]:
        length_score = round(length_max * factors["long"])
    elif length > 0:
        length_score = round(length_max * factors["tiny"])
    else:
        length_score = 0

    facts = min(
        weights["facts"],
        len(VERSION_RE.findall(core))
        + len(METRIC_RE.findall(core))
        + len(NUMBER_RE.findall(core)),
    )
    action = weights["action"] if _hits(core, rules["action_words"]) else 0
    stripped = core.rstrip()
    if stripped.endswith(("。", "！", "？")):
        clarity = weights["clarity"]
    elif "。" in core:
        clarity = max(1, round(weights["clarity"] / 3))
    else:
        clarity = 0

    notes = [f"汉字数 {length}", f"事实信号 {facts} 处"]
    if not action:
        notes.append("未见动作动词")
    return {
        "score": length_score + facts + action + clarity,
        "max": sum(weights.values()),
        "notes": notes,
    }


def _score_depth(core: str, why: str, rules: dict) -> dict:
    weights = rules["dimensions"]["depth"]
    text = f"{core} {why}"
    terms = _hits(text, rules["tech_terms"])
    term_score = min(weights["terms"], 2 * len(terms))
    specificity = min(
        weights["specificity"],
        2 * len(VERSION_RE.findall(text)) + 2 * len(METRIC_RE.findall(text)),
    )
    advice = weights["advice"] if _hits(why, rules["advice_words"]) else 0
    elaboration = (
        weights["elaboration"]
        if cjk_count(core) >= rules["length"]["elaboration_min"]
        else 0
    )

    notes = []
    if terms:
        notes.append(f"术语：{'、'.join(terms[:6])}")
    if specificity:
        notes.append("含版本/指标")
    if not advice:
        notes.append("why 未给出跟进建议")
    return {
        "score": term_score + specificity + advice + elaboration,
        "max": sum(weights.values()),
        "notes": notes,
    }


def _score_format(item: dict, rules: dict) -> dict:
    weights = rules["dimensions"]["format"]
    required = rules["format_fields"]
    present = sum(1 for key in required if item.get(key) not in (None, "", []))
    field_score = round(weights["fields"] * present / len(required))

    core_low, core_high = rules["length"]["core"]
    core_length = cjk_count(item.get("core"))
    length_score = (
        weights["core_length"]
        if core_low <= core_length <= core_high
        else round(weights["core_length"] / 2)
    )
    why_low, why_high = rules["length"]["why"]
    why_length = cjk_count(item.get("why"))
    why_score = (
        weights["why_length"]
        if why_low <= why_length <= why_high
        else round(weights["why_length"] / 2)
    )

    notes = [f"字段 {present}/{len(required)}", f"why 汉字数 {why_length}"]
    return {
        "score": field_score + length_score + why_score,
        "max": sum(weights.values()),
        "notes": notes,
    }


def _score_tags(item: dict, rules: dict) -> dict:
    """标签分档与提示全部来自配置，脚本不写阈值。"""
    weights = rules["dimensions"]["tags"]
    count = len(item.get("themes") or [])

    score = 0
    band_note = None
    for band in weights["bands"]:
        upper = band.get("max")
        if count >= band["min"] and (upper is None or count <= upper):
            score = band["score"]
            band_note = band.get("note")
            break

    notes = [f"标签 {count} 个"]
    if band_note:
        notes.append(band_note)
    return {"score": score, "max": weights["max"], "notes": notes}


def _score_filler(core: str, why: str, rules: dict) -> dict:
    weights = rules["dimensions"]["filler"]
    found = _hits(f"{core} {why}", rules["filler_words"])
    score = max(0, weights["max"] - weights["per_hit"] * len(found))
    notes = [f"命中空洞词：{'、'.join(found)}"] if found else ["未命中空洞词"]
    return {"score": score, "max": weights["max"], "notes": notes, "hits": found}


def score_item(item: dict, rules: dict) -> dict:
    core = item.get("core") or ""
    why = item.get("why") or ""
    dimensions = {
        "summary": _score_summary(core, rules),
        "depth": _score_depth(core, why, rules),
        "format": _score_format(item, rules),
        "tags": _score_tags(item, rules),
        "filler": _score_filler(core, why, rules),
    }
    total = sum(dimension["score"] for dimension in dimensions.values())
    grades = rules["grades"]
    if total >= grades["A"]:
        grade = "A"
    elif total >= grades["B"]:
        grade = "B"
    else:
        grade = "C"
    return {
        "rank": item.get("rank"),
        "full_name": item.get("full_name"),
        "total": total,
        "grade": grade,
        "dimensions": dimensions,
        "filler_hits": dimensions["filler"].get("hits", []),
    }


def _bar(score: int, maximum: int, width: int = 10) -> str:
    filled = round(width * score / maximum) if maximum else 0
    return "█" * filled + "░" * (width - filled)


def render_card(result: dict) -> str:
    if not result.get("valid"):
        lines = ["❌ 质量评分跳过：organize.json 未通过校验"]
        lines.extend(f"  - {error}" for error in result.get("errors", []))
        return "\n".join(lines)

    summary = result["summary"]
    grades = summary["grades"]
    verdict = "通过" if result["pass"] else f"未通过（{len(summary['below_min'])} 条未达标）"
    lines = [
        f"📊 质量评分 · {result['date']} 第 {result['attempt']} 次 · 均分 {summary['average']}",
        f"等级分布：A {grades['A']} / B {grades['B']} / C {grades['C']} · 结论：{verdict}",
        "─" * 32,
    ]
    max_total = (
        sum(dimension["max"] for dimension in result["items"][0]["dimensions"].values())
        if result["items"]
        else 0
    )
    for item in result["items"]:
        lines.append(
            f"{item['rank']}. {item['full_name']} · {item['grade']} · "
            f"{item['total']}/{max_total}"
        )
        for key, dimension in item["dimensions"].items():
            lines.append(
                f"   {DIMENSION_LABELS[key]}  {_bar(dimension['score'], dimension['max'])} "
                f"{dimension['score']}/{dimension['max']}"
            )
        if item["grade"] == "C":
            for key, dimension in item["dimensions"].items():
                if key == "tags":
                    # 标签维度的提示文案由配置分档提供，未满分时原样展示
                    notes = dimension["notes"] if dimension["score"] < dimension["max"] else []
                else:
                    notes = [
                        note
                        for note in dimension["notes"]
                        if note.startswith(("命中空洞词", "未见", "why"))
                    ]
                for note in notes:
                    lines.append(f"   ⚠ {note}")
    return "\n".join(lines)


def evaluate(path: Path, rules: dict) -> dict:
    errors, warnings, _ = validate_file(path)
    day = path.parent.name if is_date(path.parent.name) else today()
    if errors:
        return {
            "date": day,
            "valid": False,
            "pass": False,
            "errors": errors,
            "warnings": warnings,
            "items": [],
        }

    data = read_json(path)
    items = [score_item(item, rules) for item in data.get("github") or []]
    grades = {"A": 0, "B": 0, "C": 0}
    for item in items:
        grades[item["grade"]] += 1
    below = [
        item["full_name"] for item in items if item["total"] < rules["grades"]["B"]
    ]
    average = round(sum(item["total"] for item in items) / len(items), 1) if items else 0.0
    return {
        "date": data.get("date") or day,
        "valid": True,
        "attempt": 1,
        "scored_at": stamp(),
        "items": items,
        "summary": {
            "average": average,
            "grades": grades,
            "below_min": below,
            "pass": not below,
        },
        "pass": not below,
        "errors": [],
        "warnings": warnings,
    }


def _attempt_entry(attempt: int, result: dict, content_hash: str) -> dict:
    return {
        "attempt": attempt,
        "scored_at": result.get("scored_at") or stamp(),
        "valid": result["valid"],
        "pass": result["pass"],
        "content_hash": content_hash,
        "items": [
            {
                "full_name": item["full_name"],
                "total": item["total"],
                "grade": item["grade"],
            }
            for item in result.get("items", [])
        ],
    }


def write_score(path: Path, result: dict) -> Path:
    """写 score.json；同一份得分重复触发时只刷新时间，不打回计次。"""
    score_file = path.parent / "score.json"
    attempts: list[dict] = []
    if score_file.exists():
        try:
            previous = read_json(score_file)
            if isinstance(previous.get("attempts"), list):
                attempts = previous["attempts"]
        except (OSError, ValueError):
            attempts = []

    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    last = attempts[-1] if attempts else None
    if not result["valid"]:
        attempt = len(attempts)
    else:
        entry = _attempt_entry(len(attempts) + 1, result, content_hash)
        if last and last.get("valid") and last.get("content_hash") == content_hash:
            attempt = last.get("attempt", len(attempts))
            entry["attempt"] = attempt
            attempts = attempts[:-1] + [entry]
        else:
            attempt = entry["attempt"]
            attempts = attempts + [entry]

    result["attempt"] = attempt
    result["file"] = path.as_posix()
    result["attempts"] = attempts
    write_json(score_file, result)
    return score_file


def main() -> int:
    parser = argparse.ArgumentParser(description="给整理产物打分并写 score.json")
    parser.add_argument("--file", help="organize.json 路径")
    parser.add_argument("--date", default=today(), help="归属日期（未给 --file 时使用）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出（含卡片文本）")
    parser.add_argument("--no-write", action="store_true", help="不写 score.json")
    args = parser.parse_args()

    path = Path(args.file) if args.file else WORK_DIR / args.date / "organize.json"
    if not path.exists():
        message = f"❌ 质量评分失败：找不到 {path.as_posix()}"
        print(json.dumps({"valid": False, "pass": False, "card": message}, ensure_ascii=False) if args.json else message)
        return 2

    rules = load_rules()
    result = evaluate(path, rules)
    score_file = None if args.no_write else write_score(path, result)
    result["card"] = render_card(result)
    result["score_file"] = score_file.as_posix() if score_file else None

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["card"])
        if score_file:
            print(f"\n评分记录：{score_file.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
