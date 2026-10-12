"""메뉴바(트레이) 아이콘: 오늘 타수 보기, 풀 숨기기/보이기, 지난 풀밭 보기, 종료."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QPainter, QPixmap, QPolygonF
from PySide6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon

from ..counter.service import FAILED, NEED_PERMISSION, RUNNING
from .window import MeadowWindow

SETTINGS_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"


def make_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for dx, h, col in ((-14, 34, "#4f9d2d"), (0, 50, "#6cc04a"), (14, 30, "#3c8a22")):
        poly = QPolygonF([QPointF(32 + dx - 5, 60), QPointF(32 + dx + 5, 60), QPointF(32 + dx + dx * 0.15, 60 - h)])
        p.setBrush(QColor(col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(poly)
    p.end()
    return QIcon(pm)


class TrayController:
    def __init__(self, app, service, wallpaper_win, meadow_store, lib, port):
        self.service, self.win, self.store, self.lib, self.port = service, wallpaper_win, meadow_store, lib, port
        self.history_windows: list[MeadowWindow] = []
        self._warned = False

        self.tray = QSystemTrayIcon(make_icon(), app)
        self.menu = QMenu()
        self.count_action = QAction("오늘 0타", self.menu)
        self.count_action.setEnabled(False)
        self.status_action = QAction("", self.menu)
        self.status_action.setEnabled(False)
        self.toggle_action = QAction("풀 숨기기", self.menu)
        self.toggle_action.triggered.connect(self._toggle)
        self.history_menu = QMenu("지난 풀밭 보기", self.menu)
        quit_action = QAction("종료", self.menu)
        quit_action.triggered.connect(app.quit)

        for a in (self.count_action, self.status_action):
            self.menu.addAction(a)
        self.menu.addSeparator()
        self.menu.addAction(self.toggle_action)
        self.menu.addMenu(self.history_menu)
        self.menu.addSeparator()
        self.menu.addAction(quit_action)
        self.menu.aboutToShow.connect(self._refresh)
        self.tray.setContextMenu(self.menu)
        self.tray.setToolTip("타자수만큼 풀자라기")
        self.tray.show()

        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self._refresh()

    def _toggle(self) -> None:
        if self.win.isVisible():
            self.win.hide()
            self.toggle_action.setText("풀 보이기")
        else:
            self.win.show_on_desktop()
            self.toggle_action.setText("풀 숨기기")

    def _status_text(self) -> str:
        s = self.service.status
        if s == RUNNING:
            return "키 입력 감지 중 (횟수만 셉니다)"
        if s == NEED_PERMISSION:
            return "⚠ 입력 모니터링 권한이 필요합니다"
        if s == FAILED:
            return f"⚠ 오류: {self.service.error}"
        return "시작 중…"

    def _refresh(self) -> None:
        day, count = self.service.today()
        self.count_action.setText(f"오늘({day}) {count:,}타")
        self.status_action.setText(self._status_text())
        self.history_menu.clear()
        today = date.today().isoformat()
        days = [d for d in reversed(self.store.days()) if d != today][:14]
        if not days:
            a = self.history_menu.addAction("(아직 지난 기록이 없어요)")
            a.setEnabled(False)
        for d in days:
            a = self.history_menu.addAction(f"{d}  ({self.store.blade_count(d):,}잎)")
            a.triggered.connect(lambda _=False, d=d: self._open_history(d))

    def _open_history(self, day: str) -> None:
        w = MeadowWindow(self.store, self.lib, self.port, view_day=day)
        w.setWindowTitle(f"타자수만큼 풀자라기 — {day}")
        w.show()
        self.history_windows.append(w)

    def _tick(self) -> None:
        self.count_action.setText(f"오늘 {self.service.today()[1]:,}타")
        if self.service.status == NEED_PERMISSION and not self._warned:
            self._warned = True
            self._permission_dialog()

    def _permission_dialog(self) -> None:
        box = QMessageBox()
        box.setWindowTitle("키보드 입력 횟수를 세려면 권한이 필요해요")
        box.setText(
            "시스템 설정 > 개인정보 보호 및 보안 > 입력 모니터링 에서 'TypeGrass'(또는 실행 중인 앱)를 켜 주세요.\n\n"
            "켠 뒤에는 앱을 한 번 종료했다가 다시 실행해야 적용될 수 있어요.\n"
            "입력한 내용은 저장하지 않고 '횟수'만 셉니다."
        )
        open_btn = box.addButton("시스템 설정 열기", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("나중에", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl(SETTINGS_URL))
