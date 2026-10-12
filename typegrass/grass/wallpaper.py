"""바탕화면 풀밭 창: 배경 없이 투명, 마우스 클릭 통과, 바탕화면 아이콘 '바로 아래' 레벨.

* macOS: 창 레벨을 '바탕화면 아이콘 레벨 - 1' 로 내려서 배경화면 위, 아이콘/다른 창 아래에 둔다.
  모든 데스크톱(Spaces)에 보이고, Mission Control/Cmd+Tab 에 나타나지 않게 한다.
* 그 설정이 실패하면(또는 macOS 가 아니면) Qt 의 '항상 맨 아래' 옵션만으로 동작한다.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from .window import MeadowWindow


def send_to_desktop_level(widget) -> bool:
    """macOS 전용. 성공하면 True."""
    if sys.platform != "darwin":
        return False
    try:
        import objc
        import Quartz
        from AppKit import (
            NSColor,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorIgnoresCycle,
            NSWindowCollectionBehaviorStationary,
        )

        view = objc.objc_object(c_void_p=int(widget.winId()))
        win = view.window()
        win.setLevel_(Quartz.CGWindowLevelForKey(Quartz.kCGDesktopIconWindowLevelKey) - 1)
        win.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorIgnoresCycle
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        win.setIgnoresMouseEvents_(True)
        win.setOpaque_(False)
        win.setBackgroundColor_(NSColor.clearColor())
        win.setHasShadow_(False)
        return True
    except Exception as e:  # pyobjc 없음/OS 변경 등: 창은 계속 동작
        print(f"[경고] 바탕화면 레벨 설정 실패(대신 '항상 맨 아래' 창으로 동작): {e}")
        return False


class WallpaperWindow(MeadowWindow):
    def __init__(self, store, lib, port, screen_index: int = 0, opacity: float = 1.0, demo_rate=None):
        super().__init__(store, lib, port, demo_rate=demo_rate)
        self.canvas.ground = False  # 배경 없이 풀만 (투명)
        self.show_hud = False
        self.setWindowTitle("TypeGrass Wallpaper")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnBottomHint
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowOpacity(max(0.1, min(1.0, opacity)))

        screens = QGuiApplication.screens()
        self.target_screen = screens[screen_index] if 0 <= screen_index < len(screens) else QGuiApplication.primaryScreen()
        self.setScreen(self.target_screen)
        self.setGeometry(self.target_screen.geometry())

    def show_on_desktop(self) -> bool:
        self.setGeometry(self.target_screen.geometry())
        self.show()
        ok = send_to_desktop_level(self)
        self.lower()
        return ok

    def keyPressEvent(self, e) -> None:  # 클릭/키 입력을 받지 않는 창
        pass
