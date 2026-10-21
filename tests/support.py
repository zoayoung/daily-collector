"""测试支撑：fixture 回放服务器、隔离的 CLI 运行器。

测试只通过 CLI 与产物文件观察行为；work/daily-knowledge 用环境变量指向临时目录，
GitHub API 用本地服务器回放 tests/fixtures/ 下的真实返回。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
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


class FixtureServer:
    """本地 HTTP 服务器，按路径回放搜索与 star 历史 fixture。

    break_first_search=True 时，第一次搜索请求只发送一半响应体并断开，
    用于复现 http.client.IncompleteRead。
    """

    def __init__(self, break_first_search: bool = False) -> None:
        self.break_first_search = break_first_search
        self.requests: list[str] = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}"

    def _handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def do_GET(self) -> None:
                outer.requests.append(self.path)
                if self.path.startswith("/search/repositories"):
                    body = fixture_bytes("search_repositories.json")
                    broken = outer.break_first_search and outer.requests.count(self.path) == 1
                elif "/stargazers/history" in self.path:
                    body = fixture_bytes("star_history.json")
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
