"""가짜 키 입력 생성기. 맥이 아니거나 권한 설정 전에 동작을 시험하기 위한 용도."""
from __future__ import annotations

import random
import time
from typing import Callable


class SimKeyListener:
    name = "simulated"

    def __init__(self, on_key: Callable[[], None], rate: float = 8.0, seed: int | None = None):
        self._on_key = on_key
        self._rate = max(0.1, rate)
        self._rng = random.Random(seed)
        self._running = False

    def run(self) -> None:
        self._running = True
        while self._running:
            # 평균 rate 회/초, 사람 타이핑처럼 간격에 약간의 흔들림을 준다.
            time.sleep(self._rng.expovariate(self._rate))
            if self._running:
                self._on_key()

    def stop(self) -> None:
        self._running = False
