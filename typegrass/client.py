"""카운터 API 를 조회하는 간단한 클라이언트 (다른 파이썬 프로그램에서도 import 해서 쓸 수 있다)."""
from __future__ import annotations

import json
import urllib.request

from . import DEFAULT_PORT


def get_today(port: int = DEFAULT_PORT, timeout: float = 1.0) -> dict:
    url = f"http://127.0.0.1:{port}/today"
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def get_history(days: int = 30, port: int = DEFAULT_PORT, timeout: float = 2.0) -> list[dict]:
    url = f"http://127.0.0.1:{port}/history?days={days}"
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))["days"]
