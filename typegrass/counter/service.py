"""카운터를 '다른 프로그램 안에서' 돌리기 위한 묶음 (앱 모드에서 사용).

키 감지는 별도 스레드, 저장은 백그라운드 스레드, 조회 API 는 HTTP 서버 스레드.
풀밭 쪽과는 여전히 HTTP 로만 연결된다(타수 측정/시각화 분리 유지).
"""
from __future__ import annotations

import sys
import threading

from .. import DEFAULT_PORT, paths
from .api import make_server, serve_in_thread
from .store import CountStore
from .tally import Tally

STARTING, RUNNING, NEED_PERMISSION, FAILED = "starting", "running", "need_permission", "failed"


class CounterService:
    def __init__(self, port: int = DEFAULT_PORT, simulate: bool = False, sim_rate: float = 8.0,
                 count_repeats: bool = False, db_path=None):
        self.port, self.simulate, self.sim_rate, self.count_repeats = port, simulate, sim_rate, count_repeats
        self.status = STARTING
        self.error = ""
        self._db_path = db_path or paths.counts_db_path()
        self._stop = threading.Event()
        self._listener = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """포트가 이미 사용 중이면 OSError. 그 외에는 키 감지를 백그라운드로 시작한다."""
        self.store = CountStore(self._db_path)
        self.tally = Tally(self.store)
        try:
            self.server = make_server(
                self.tally, self.store, self.port, backend="simulated" if self.simulate else "macos"
            )
        except OSError:
            self.store.close()
            raise
        self.tally.start()
        serve_in_thread(self.server)
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def today(self) -> tuple[str, int]:
        return self.tally.today()

    def _make_listener(self):
        if self.simulate:
            from .listener_sim import SimKeyListener

            return SimKeyListener(self.tally.increment, rate=self.sim_rate)
        if sys.platform != "darwin":
            raise RuntimeError("macOS 에서만 실제 키 입력을 셀 수 있습니다 (시험용: --simulate)")
        from . import listener_macos

        if not listener_macos.has_permission():
            listener_macos.request_permission()  # 시스템 권한 팝업
        return listener_macos.MacKeyListener(self.tally.increment, count_repeats=self.count_repeats)

    def _listen_loop(self) -> None:
        try:
            self._listener = self._make_listener()
        except Exception as e:
            self.status, self.error = FAILED, str(e)
            return
        while not self._stop.is_set():
            try:
                self.status = RUNNING
                self._listener.run()  # stop() 전까지 반환하지 않음
                return
            except Exception as e:
                if e.__class__.__name__ != "PermissionDenied":
                    self.status, self.error = FAILED, str(e)
                    return
                self.status = NEED_PERMISSION
                self._stop.wait(3.0)  # 권한을 켤 때까지 3초마다 재시도

    def stop(self) -> None:
        self._stop.set()
        if self._listener is not None:
            self._listener.stop()
        if self._thread:
            self._thread.join(timeout=2)
        self.server.shutdown()
        self.tally.stop()
        self.store.close()
