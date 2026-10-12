"""풀밭 창 (별도 창). 카운터 API 를 주기적으로 조회해 풀잎 수를 타수에 맞춘다.

타수 측정(counter)과는 HTTP 로만 연결되어 있다. 이 창이 꺼져 있어도 카운터는 계속 세고,
창을 다시 켜면 '모자란 만큼' 풀잎을 한꺼번에 만들어 타수와 풀잎 수를 일치시킨다.
"""
from __future__ import annotations

import json
import time
from datetime import date

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QColor, QFont, QKeyEvent, QPainter
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QWidget

from .assets import SpriteLibrary
from .meadow_store import MeadowStore, grow_to
from .renderer import MeadowCanvas

POLL_MS = 150
ANIMATE_UP_TO = 40  # 한 번에 이만큼 이하로 늘 때만 성장 애니메이션 (그 이상은 한꺼번에 반영)
GEN_CHUNK = 2000  # 한 번에 만드는 풀잎 수 상한 (UI 멈춤 방지)


class MeadowWindow(QWidget):
    def __init__(
        self,
        store: MeadowStore,
        lib: SpriteLibrary,
        port: int,
        view_day: str | None = None,
        demo_rate: float | None = None,
    ):
        super().__init__()
        self.setWindowTitle("타자수만큼 풀자라기")
        self.resize(1280, 720)
        self.store, self.lib, self.port = store, lib, port
        self.canvas = MeadowCanvas(lib, ground=True)
        self.show_hud = True
        self.status = "카운터 연결 대기 중…"
        self.counter_count = 0
        self.day = view_day or date.today().isoformat()
        self.view_only = view_day is not None
        self.demo_rate = demo_rate
        self._demo_start = time.perf_counter()

        # 타이머를 먼저 만들어 둔다 (_open_day 가 _kick_frames 를 부르기 때문)
        self.frame_timer = QTimer(self)
        self.frame_timer.setInterval(16)
        self.frame_timer.timeout.connect(self._on_frame)

        self.gen = None
        self._open_day(self.day)

        if not self.view_only:
            self.net = QNetworkAccessManager(self)
            self.poll_timer = QTimer(self)
            self.poll_timer.setInterval(POLL_MS)
            self.poll_timer.timeout.connect(self._poll)
            self.poll_timer.start()
        self._kick_frames()

    # ----------------------------------------------------------- 날짜별 풀밭
    def _open_day(self, day: str) -> None:
        self.day = day
        self.gen = self.store.open_generator(day, self.lib.by_cat)
        blades = self.store.load_blades(day)
        self.gen.total = len(blades)  # 저장된 풀잎 수와 생성기 상태를 일치시킨다
        self.canvas.set_blades(blades)
        self._kick_frames()

    def blade_count(self) -> int:
        return self.gen.total

    # --------------------------------------------------------------- 카운터 조회
    def _poll(self) -> None:
        if self.demo_rate is not None:  # 데모: 가짜 타수가 일정 속도로 증가
            n = int((time.perf_counter() - self._demo_start) * self.demo_rate)
            self.apply_count(self.day, n)
            return
        req = QNetworkRequest(QUrl(f"http://127.0.0.1:{self.port}/today"))
        req.setTransferTimeout(1000)
        reply = self.net.get(req)
        reply.finished.connect(lambda r=reply: self._on_reply(r))

    def _on_reply(self, reply: QNetworkReply) -> None:
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.status = "카운터에 연결할 수 없음 (typegrass counter 를 먼저 실행하세요)"
                return
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
            self.status = ""
            self.apply_count(str(data["date"]), int(data["count"]))
        except Exception as e:  # 응답이 이상해도 창이 죽지 않도록
            self.status = f"응답 처리 오류: {e}"
        finally:
            reply.deleteLater()
            self.update()

    def apply_count(self, day: str, count: int) -> None:
        """카운터가 알려 준 (날짜, 누적 타수)에 풀잎 수를 맞춘다. 풀잎은 줄이지 않는다."""
        if day != self.day and self.demo_rate is None:
            self._open_day(day)  # 자정이 지남: 새 풀밭 시작 (어제 풀밭은 DB 에 그대로 남음)
        self.counter_count = count
        missing = count - self.gen.total
        if missing <= 0:
            return
        todo = min(missing, GEN_CHUNK)
        new = grow_to(self.store, self.gen, self.day, self.gen.total + todo)
        self.canvas.add(new, animate=(missing <= ANIMATE_UP_TO))
        self._kick_frames()

    # ----------------------------------------------------------------- 프레임
    def _kick_frames(self) -> None:
        if self.canvas.needs_frames() and not self.frame_timer.isActive():
            self.frame_timer.start()
        self.update()

    def _on_frame(self) -> None:
        self.canvas.step(8.0)
        self.update()
        if not self.canvas.needs_frames():
            self.frame_timer.stop()

    # ------------------------------------------------------------------ 이벤트
    def resizeEvent(self, e) -> None:
        self.canvas.set_size(self.width(), self.height(), self.devicePixelRatioF())
        self._kick_frames()

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        self.canvas.paint(p)
        if self.show_hud:
            self._paint_hud(p)
        p.end()

    def _paint_hud(self, p: QPainter) -> None:
        p.setFont(QFont("Apple SD Gothic Neo", 13))
        opened = self.store.opened_cluster_count(self.day)
        text = (
            f"{self.day}   타수 {self.counter_count:,}   풀잎 {self.blade_count():,}   군락 {opened}"
        )
        if self.view_only:
            text += "   (지난 기록 보기)"
        if self.status:
            text += f"\n{self.status}"
        p.setPen(QColor(0, 0, 0, 160))
        p.drawText(self.rect().adjusted(13, 13, -10, -10), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, text)
        p.setPen(QColor(255, 255, 255, 235))
        p.drawText(self.rect().adjusted(12, 12, -10, -10), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, text)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        k = e.key()
        if k in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
            self.close()
        elif k == Qt.Key.Key_H:
            self.show_hud = not self.show_hud
            self.update()
        elif k == Qt.Key.Key_F:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
