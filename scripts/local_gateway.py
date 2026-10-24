"""Single-URL local gateway: serves the built frontend and proxies the API.

把构建后的前端（apps/frontend/dist）和后端 API（127.0.0.1:8000）合并到一个
本地端口上，让前端和后端同源，从而只需一条隧道/一个公网网址即可对外服务，
且浏览器不再触发 CORS。

路由规则：
- 精确匹配 SPA 路由（/、/login、/register、/chat、/knowledge、/aiops、/mcp）
  → 返回 dist/index.html（前端路由接管）。
- dist 中真实存在的文件（/assets/*、favicon 等）→ 直接返回静态文件。
- 其余所有路径 → 原样反代到后端（含 POST/PATCH/DELETE 与 SSE 流式响应）。

用法（在仓库根目录）：
    python scripts/local_gateway.py                # 默认 4173 端口
    python scripts/local_gateway.py --port 8080    # 自定义端口

仅依赖 Python 标准库；只在本机运行，不应对公网直接暴露（公网侧请用隧道）。
"""

from __future__ import annotations

import argparse
import http.client
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = REPO_ROOT / "apps" / "frontend" / "dist"
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
SPA_ROUTES = frozenset({"/", "/login", "/register", "/chat", "/knowledge", "/aiops", "/mcp"})
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


class GatewayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "agent-py-gateway/1.0"
    backend_port = 8000

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._handle()

    def do_POST(self) -> None:  # noqa: N802
        self._handle()

    def do_PUT(self) -> None:  # noqa: N802
        self._handle()

    def do_PATCH(self) -> None:  # noqa: N802
        self._handle()

    def do_DELETE(self) -> None:  # noqa: N802
        self._handle()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._handle()

    def do_HEAD(self) -> None:  # noqa: N802
        self._handle()

    def _handle(self) -> None:
        path = self.path.split("?", 1)[0]
        if self.command == "GET" and (path in SPA_ROUTES or self._static_file_path(path) is not None):
            self._serve_static(path)
            return
        self._proxy()

    def _static_file_path(self, path: str) -> Path | None:
        if not path or path == "/":
            return None
        candidate = (DIST_DIR / path.lstrip("/")).resolve()
        try:
            candidate.relative_to(DIST_DIR.resolve())
        except ValueError:
            return None
        return candidate if candidate.is_file() else None

    def _serve_static(self, path: str) -> None:
        file_path = self._static_file_path(path)
        if file_path is None:
            file_path = DIST_DIR / "index.html"
        if not file_path.is_file():
            self._plain(404, "frontend build output not found; run `npm run frontend:build` first")
            return
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _proxy(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length > 0 else None
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP and key.lower() != "host"
        }
        headers["Host"] = f"{BACKEND_HOST}:{BACKEND_PORT}"
        try:
            connection = http.client.HTTPConnection(BACKEND_HOST, self.backend_port, timeout=300)
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
        except OSError as exc:
            self._plain(502, f"backend unreachable: {exc}")
            return

        self.send_response(response.status)
        for key, value in response.getheaders():
            if key.lower() in HOP_BY_HOP or key.lower() == "content-length":
                continue
            self.send_header(key, value)
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        if self.command == "HEAD":
            connection.close()
            return
        try:
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            connection.close()

    def _plain(self, status: int, message: str) -> None:
        payload = message.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        print(f"[gateway] {self.address_string()} {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Single-URL frontend + API gateway")
    parser.add_argument("--port", type=int, default=4173, help="本地监听端口（默认 4173）")
    parser.add_argument("--backend-port", type=int, default=BACKEND_PORT, help="后端端口（默认 8000）")
    args = parser.parse_args()

    GatewayHandler.backend_port = args.backend_port

    if not (DIST_DIR / "index.html").is_file():
        print(f"[gateway] 未找到 {DIST_DIR / 'index.html'}，请先执行 npm run frontend:build")
        raise SystemExit(1)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), GatewayHandler)
    print(f"[gateway] http://127.0.0.1:{args.port}  (dist={DIST_DIR}, api=127.0.0.1:{args.backend_port})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
