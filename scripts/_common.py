"""知识采集系统脚本公共工具：路径、时间、JSON 读写与汉字计数。"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
WORK_DIR = Path(os.environ.get("KNOWLEDGE_WORK_DIR") or ROOT / "work")
DAILY_KNOWLEDGE_DIR = Path(os.environ.get("KNOWLEDGE_OUTPUT_DIR") or ROOT / "daily-knowledge")
SCHEMA_DIR = ROOT / "schemas"
CONFIG_DIR = ROOT / "config"
SPEC = ROOT / ".scratch" / "knowledge-daily" / "spec.md"

TIMEZONE = timezone(timedelta(hours=8))
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
HEADING_RE = re.compile(r"^###\s+\d+\.\s+(\S+/\S+)\s*$")


def _load_env_file(path: Path) -> None:
    """读取项目根 .env；已存在的进程环境变量优先，不被覆盖。"""
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip()
        if value[:1] in {'"', "'"}:
            quote = value[0]
            end = value.find(quote, 1)
            value = value[1:end] if end != -1 else value[1:]
        else:
            value = value.split(" #", 1)[0].strip()
        if not key or not value or key in os.environ:
            continue
        os.environ[key] = value


_load_env_file(ROOT / ".env")


def now() -> datetime:
    """本地时间（UTC+8）。"""
    return datetime.now(TIMEZONE)


def today() -> str:
    return now().strftime("%Y-%m-%d")


def stamp() -> str:
    return now().strftime("%Y-%m-%d %H:%M")


def is_date(value: object) -> bool:
    return isinstance(value, str) and bool(DATE_RE.match(value))


def work_path(date: str, name: str) -> Path:
    return WORK_DIR / date / name


def read_json(path: Path | str):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path: Path | str, data) -> Path:
    """原子写入 UTF-8 JSON（2 空格缩进、末尾换行）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(tmp, path)
    return path


def cjk_count(text: str | None) -> int:
    """统计文本中的汉字数量（英文单词与数字不计）。"""
    return len(CJK_RE.findall(text or ""))


VALIDATION_RULE_KEYS = (
    "dedupe_window_days",
    "collect_min_items",
    "report_min_items",
    "report_max_items",
    "core_max_cjk",
)


def load_validation_rules() -> dict:
    """读取语义阈值配置；缺失或缺键时给出可定位的失败信息。"""
    path = CONFIG_DIR / "validation-rules.json"
    try:
        rules = read_json(path)
    except FileNotFoundError as error:
        raise SystemExit(f"❌ 校验失败：找不到校验规则 {path.as_posix()}") from error
    except (OSError, ValueError) as error:
        raise SystemExit(f"❌ 校验失败：无法读取校验规则 {path.as_posix()}：{error}") from error
    missing = [key for key in VALIDATION_RULE_KEYS if key not in rules]
    if missing:
        raise SystemExit(f"❌ 校验失败：{path.as_posix()} 缺少 {', '.join(missing)}")
    return rules


def window_start(day: str, window_days: int) -> str:
    """重复窗口的起始日：day 之前第 window_days 天（含当天）。"""
    return (date.fromisoformat(day) - timedelta(days=window_days)).isoformat()


def published_history(day: str) -> dict[str, list[str]]:
    """已发布日报的项目历史：{小写 full_name: [发布日期升序]}，不含 day 及之后。"""
    history: dict[str, list[str]] = {}
    if not DAILY_KNOWLEDGE_DIR.exists():
        return history
    current = date.fromisoformat(day)
    for path in sorted(DAILY_KNOWLEDGE_DIR.glob("*.md")):
        stem = path.stem
        if not is_date(stem) or date.fromisoformat(stem) >= current:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        for line in text.splitlines():
            match = HEADING_RE.match(line)
            if match:
                history.setdefault(match.group(1).lower(), []).append(stem)
    for dates in history.values():
        dates.sort()
    return history


def recent_duplicates(day: str, window_days: int) -> set[str]:
    """重复窗口内出现过的项目（小写 full_name），用于采集过滤。"""
    start = window_start(day, window_days)
    return {
        name
        for name, dates in published_history(day).items()
        if dates and dates[-1] >= start
    }
