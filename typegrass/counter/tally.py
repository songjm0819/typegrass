"""오늘의 누적 타수를 메모리에서 세고, 주기적으로 저장소에 기록한다.

- 키를 누를 때마다 DB에 쓰지 않는다(느려지므로). 메모리에서 +1 하고
  1초마다(바뀐 경우에만) 저장한다. 종료 시에도 저장한다.
- 날짜가 바뀌면(자정) 어제 값을 저장하고 오늘 값은 0부터 다시 시작한다.
  어제 기록은 DB에 그대로 남는다.
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Callable

from .store import CountStore


class Tally:
    def __init__(
        self,
        store: CountStore,
        clock: Callable[[], datetime] = datetime.now,
        flush_interval: float = 1.0,
    ):
        self._store = store
        self._clock = clock
        self._lock = threading.Lock()
        self._dirty = False
        self._day = self._today_str()
        self._count = store.get(self._day)  # 재실행해도 오늘 값 이어받기
        self._stop = threading.Event()
        self._flush_interval = flush_interval
        self._thread: threading.Thread | None = None

    def _today_str(self) -> str:
        return self._clock().date().isoformat()

    def _roll_if_needed(self) -> None:
        """호출 전에 self._lock 을 잡고 있어야 한다."""
        today = self._today_str()
        if today != self._day:
            if self._dirty:
                self._store.set(self._day, self._count)
                self._dirty = False
            self._day = today
            self._count = self._store.get(today)

    def increment(self, n: int = 1) -> None:
        with self._lock:
            self._roll_if_needed()
            self._count += n
            self._dirty = True

    def today(self) -> tuple[str, int]:
        with self._lock:
            self._roll_if_needed()
            return self._day, self._count

    def flush(self) -> None:
        with self._lock:
            if self._dirty:
                self._store.set(self._day, self._count)
                self._dirty = False

    # ---- 백그라운드 저장 스레드 ----
    def start(self) -> None:
        if self._thread:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.wait(self._flush_interval):
            self.flush()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.flush()
