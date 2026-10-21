"""测试支撑：fixture 回放服务器、隔离的 CLI 运行器。

测试只通过 CLI 与产物文件观察行为；work/daily-knowledge 用环境变量指向临时目录，
GitHub API 用本地服务器回放 tests/fixtures/ 下的真实返回。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Self

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def fixture(name: str) -> object:
    """读取 fixture JSON（真实 GitHub 返回快照）。"""
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def fixture_bytes(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def search_request(path: str) -> tuple[str, int]:
    """从搜索请求路径解析 star 区间与页码。"""
    query = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
    text = (query.get("q") or [""])[0]
    match = re.search(r"stars:(\S+)", text)
    star_range = match.group(1) if match else ""
    page = int((query.get("page") or ["1"])[0])
    return star_range, page


def search_payload(items: list[dict]) -> bytes:
    """把条目列表包装成搜索响应体。"""
    return json.dumps(
        {"total_count": len(items), "incomplete_results": False, "items": items},
        ensure_ascii=False,
    ).encode("utf-8")


class FixtureServer:
    """本地 HTTP 服务器，按路径回放搜索与 star 历史 fixture。

    break_first_search=True 时，第一次搜索请求只发送一半响应体并断开，
    用于复现 http.client.IncompleteRead。

    search_pages 可按 (star 区间, 页码) 覆盖搜索响应；值可以是条目列表、
    完整响应 dict 或原始字节。未覆盖的请求回放 search_repositories.json。

    search_failures 按 (star 区间, 页码) 指定要返回的 HTTP 状态码，用于模拟单区间失败。
    star_history_body 可覆盖 star 历史响应，用于模拟当天增量尚未产生的全 0 返回。
    """

    def __init__(
        self,
        break_first_search: bool = False,
        search_pages: dict[tuple[str, int], object] | None = None,
        search_failures: dict[tuple[str, int], int] | None = None,
        star_history_body: object | None = None,
    ) -> None:
        self.break_first_search = break_first_search
        self.search_pages = search_pages or {}
        self.search_failures = search_failures or {}
        self.star_history_body = star_history_body
        self.requests: list[str] = []
        self._search_requests = 0
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}"

    def _search_body(self, path: str) -> bytes:
        value = self.search_pages.get(search_request(path))
        if value is None:
            return fixture_bytes("search_repositories.json")
        if isinstance(value, (bytes, bytearray)):
            return bytes(value)
        if isinstance(value, list):
            return search_payload(value)
        return json.dumps(value, ensure_ascii=False).encode("utf-8")

    def _handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def do_GET(self) -> None:
                outer.requests.append(self.path)
                if self.path.startswith("/search/repositories"):
                    outer._search_requests += 1
                    status = outer.search_failures.get(search_request(self.path))
                    if status is not None:
                        self.send_response(status)
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                    body = outer._search_body(self.path)
                    broken = outer.break_first_search and outer._search_requests == 1
                elif "/stargazers/history" in self.path:
                    if outer.star_history_body is None:
                        body = fixture_bytes("star_history.json")
                    else:
                        body = json.dumps(outer.star_history_body, ensure_ascii=False).encode("utf-8")
                    broken = False
                elif self.path == "/rate_limit":
                    body = b"{}"
                    broken = False
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if broken:
                    self.wfile.write(body[: len(body) // 2])
                    self.wfile.flush()
                    self.close_connection = True
                    return
                self.wfile.write(body)

        return Handler

    def __enter__(self) -> Self:
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc) -> None:
        self._server.shutdown()
        self._server.server_close()


def render_report(organized: dict, score: dict | None = None) -> str:
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
        star_line = f"- Star：{item['stars_total']:,}（今日 +{item['stars_today']}）"
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


def run_cli(
    script: str,
    *args: str,
    work_dir: Path,
    output_dir: Path | None = None,
    api: str | None = None,
    token: str = "test-token",
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """在隔离环境里跑 scripts/<script>，返回 CompletedProcess。"""
    env = os.environ.copy()
    for key in (
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "KNOWLEDGE_WORK_DIR",
        "KNOWLEDGE_OUTPUT_DIR",
        "KNOWLEDGE_GITHUB_API",
    ):
        env.pop(key, None)
    env["KNOWLEDGE_WORK_DIR"] = str(work_dir)
    if output_dir is not None:
        env["KNOWLEDGE_OUTPUT_DIR"] = str(output_dir)
    if api is not None:
        env["KNOWLEDGE_GITHUB_API"] = api
    env["GITHUB_TOKEN"] = token
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=str(ROOT),
        check=False,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
