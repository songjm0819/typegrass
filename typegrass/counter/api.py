"""다른 프로그램이 오늘 타수를 실시간으로 조회하는 로컬 HTTP API.

127.0.0.1(내 컴퓨터 안)에서만 접속 가능하다. 응답에는 날짜와 횟수만 들어 있다.

    curl http://127.0.0.1:47831/count      -> 1234          (숫자만)
    curl http://127.0.0.1:47831/today      -> {"date": "...", "count": 1234, ...}
    curl "http://127.0.0.1:47831/history?days=7"
    curl http://127.0.0.1:47831/health
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .store import CountStore
from .tally import Tally

_ALLOWED_HOSTS = {"127.0.0.1", "localhost"}


def make_server(
    tally: Tally, store: CountStore, port: int, backend: str = "unknown"
) -> ThreadingHTTPServer:
    started = time.time()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # 터미널을 어지럽히지 않도록 로그 끔
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self._send(code, body, "application/json; charset=utf-8")

        def do_GET(self):
            # DNS rebinding 방어: 브라우저가 다른 도메인 이름으로 접근하는 것을 막는다.
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            if host not in _ALLOWED_HOSTS:
                return self._json({"error": "forbidden host"}, 403)

            url = urlparse(self.path)
            if url.path == "/count":
                _, count = tally.today()
                return self._send(200, str(count).encode(), "text/plain; charset=utf-8")
            if url.path == "/today":
                day, count = tally.today()
                return self._json({"date": day, "count": count})
            if url.path == "/history":
                q = parse_qs(url.query)
                try:
                    days = max(1, min(3650, int(q.get("days", ["30"])[0])))
                except ValueError:
                    return self._json({"error": "days must be an integer"}, 400)
                tally.flush()
                rows = store.history(days)
                return self._json(
                    {"days": [{"date": d, "count": c} for d, c in rows]}
                )
            if url.path == "/health":
                return self._json(
                    {"ok": True, "backend": backend, "uptime_sec": int(time.time() - started)}
                )
            return self._json({"error": "not found"}, 404)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def serve_in_thread(server: ThreadingHTTPServer) -> threading.Thread:
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return t
