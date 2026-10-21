"""质量评分：5 个维度确定性打分 + A/B/C 等级 + 进度条，写 score.json。

用法：
    uv run python scripts/score.py --file work/2026-10-21/organize.json
    uv run python scripts/score.py --date 2026-10-21 --json
"""

from __future__ import annotations

import argparse
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
    parse_topics,
    read_json,
    stamp,
    today,
    write_json,
)
from validate import validate_file

DEFAULT_RULES = {
    "grades": {"A": 80, "B": 60},
    "filler_words": [],
    "tech_terms": [],
    "action_words": [],
    "advice_words": [],
    "metric_words": [],
}

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


def load_rules() -> dict:
    path = CONFIG_DIR / "score-rules.json"
    rules = dict(DEFAULT_RULES)
    if path.exists():
        raw = read_json(path)
        for key, value in raw.items():
            rules[key] = value
    return rules


def _hits(text: str, terms: list[str]) -> list[str]:
    lowered = (text or "").lower()
    found = []
    for term in terms:
        if term and term.lower() in lowered and term not in found:
            found.append(term)
    return found


def _score_summary(core: str, rules: dict) -> dict:
    length = cjk_count(core)
    if 40 <= length <= 100:
        length_score = 10
    elif 25 <= length < 40:
        length_score = 8
    elif 15 <= length < 25 or 100 < length <= 130:
        length_score = 5
    elif length > 130:
        length_score = 1
    elif length > 0:
        length_score = 2
    else:
        length_score = 0

    facts = min(
        8,
        len(VERSION_RE.findall(core))
        + len(METRIC_RE.findall(core))
        + len(NUMBER_RE.findall(core)),
    )
    action = 4 if _hits(core, rules["action_words"]) else 0
    stripped = core.rstrip()
    clarity = 3 if stripped.endswith(("。", "！", "？")) else (1 if "。" in core else 0)

    notes = [f"汉字数 {length}", f"事实信号 {facts} 处"]
    if not action:
        notes.append("未见动作动词")
    return {
        "score": length_score + facts + action + clarity,
        "max": 25,
        "notes": notes,
    }


def _score_depth(core: str, why: str, rules: dict) -> dict:
    text = f"{core} {why}"
    terms = _hits(text, rules["tech_terms"])
    term_score = min(10, 2 * len(terms))
    specificity = min(8, 2 * len(VERSION_RE.findall(text)) + 2 * len(METRIC_RE.findall(text)))
    advice = 5 if _hits(why, rules["advice_words"]) else 0
    elaboration = 2 if cjk_count(core) >= 40 else 0

    notes = []
    if terms:
        notes.append(f"术语：{'、'.join(terms[:6])}")
    if specificity:
        notes.append("含版本/指标")
    if not advice:
        notes.append("why 未给出跟进建议")
    return {
        "score": term_score + specificity + advice + elaboration,
        "max": 25,
        "notes": notes,
    }


def _score_format(item: dict) -> dict:
    required = ["full_name", "url", "themes", "rank", "core", "why"]
    present = sum(1 for key in required if item.get(key) not in (None, "", []))
    field_score = present * 2

    core_length = cjk_count(item.get("core"))
    length_score = 4 if 20 <= core_length <= 110 else 2
    why_length = cjk_count(item.get("why"))
    why_score = 4 if 10 <= why_length <= 80 else 2

    notes = [f"字段 {present}/{len(required)}", f"why 汉字数 {why_length}"]
    return {
        "score": field_score + length_score + why_score,
        "max": 20,
        "notes": notes,
    }


def _score_tags(item: dict, topics: list[dict], rules: dict) -> dict:
    themes = item.get("themes") or []
    names = {topic["name"] for topic in topics}
    text = " ".join(
        str(item.get(key) or "") for key in ("full_name", "description", "core", "why")
    )

    base = 5 if themes else 0
    valid = 3 if themes and all(theme in names for theme in themes) else 0
    evidence = 0
    for topic in topics:
        if topic["name"] in themes and _hits(text, topic["keywords"]):
            evidence = 4
            break
    spread = 3 if len(themes) <= 3 else 1

    notes = [f"主题 {len(themes)} 个"]
    if not themes:
        notes.append("未命中任何主题")
    if evidence == 0 and themes:
        notes.append("主题缺关键词证据")
    return {
        "score": base + valid + evidence + spread,
        "max": 15,
        "notes": notes,
    }


def _score_filler(core: str, why: str, rules: dict) -> dict:
    found = _hits(f"{core} {why}", rules["filler_words"])
    score = max(0, 15 - 5 * len(found))
    notes = [f"命中空洞词：{'、'.join(found)}"] if found else ["未命中空洞词"]
    return {"score": score, "max": 15, "notes": notes, "hits": found}


def score_item(item: dict, topics: list[dict], rules: dict) -> dict:
    core = item.get("core") or ""
    why = item.get("why") or ""
    dimensions = {
        "summary": _score_summary(core, rules),
        "depth": _score_depth(core, why, rules),
        "format": _score_format(item),
        "tags": _score_tags(item, topics, rules),
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
    verdict = "通过" if result["pass"] else f"未通过（{len(summary['below_min'])} 条 <60）"
    lines = [
        f"📊 质量评分 · {result['date']} 第 {result['attempt']} 次 · 均分 {summary['average']}",
        f"等级分布：A {grades['A']} / B {grades['B']} / C {grades['C']} · 结论：{verdict}",
        "─" * 32,
    ]
    for item in result["items"]:
        lines.append(f"{item['rank']}. {item['full_name']} · {item['grade']} · {item['total']}/100")
        for key, dimension in item["dimensions"].items():
            lines.append(
                f"   {DIMENSION_LABELS[key]}  {_bar(dimension['score'], dimension['max'])} "
                f"{dimension['score']}/{dimension['max']}"
            )
        if item["grade"] == "C":
            for dimension in item["dimensions"].values():
                for note in dimension["notes"]:
                    if note.startswith(("命中空洞词", "未见", "why", "主题缺", "未命中")):
                        lines.append(f"   ⚠ {note}")
    return "\n".join(lines)


def evaluate(path: Path, rules: dict, topics: list[dict]) -> dict:
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
    items = [score_item(item, topics, rules) for item in data.get("github") or []]
    grades = {"A": 0, "B": 0, "C": 0}
    for item in items:
        grades[item["grade"]] += 1
    below = [item["full_name"] for item in items if item["grade"] == "C"]
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


def write_score(path: Path, result: dict) -> Path:
    score_file = path.parent / "score.json"
    attempts: list[dict] = []
    if score_file.exists():
        try:
            previous = read_json(score_file)
            if isinstance(previous.get("attempts"), list):
                attempts = previous["attempts"]
        except (OSError, ValueError):
            attempts = []

    attempt = len(attempts) + 1
    result["attempt"] = attempt
    result["file"] = path.as_posix()
    result["attempts"] = attempts + [
        {
            "attempt": attempt,
            "scored_at": result.get("scored_at") or stamp(),
            "valid": result["valid"],
            "pass": result["pass"],
            "items": [
                {
                    "full_name": item["full_name"],
                    "total": item["total"],
                    "grade": item["grade"],
                }
                for item in result.get("items", [])
            ],
        }
    ]
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
    topics = parse_topics()
    result = evaluate(path, rules, topics)
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
