"""올인원 앱: 카운터 + 바탕화면 풀밭 + 메뉴바 아이콘 (.app 배포판이 실행하는 것)."""
from __future__ import annotations

import sys

from . import DEFAULT_PORT, paths


def _setup_logging_if_frozen() -> None:
    """더블클릭으로 연 .app 은 터미널이 없으므로 로그를 파일로 남긴다."""
    if paths.is_frozen():
        f = open(paths.data_dir() / "typegrass.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = f


def run_app(port: int = DEFAULT_PORT, mode: str = "wallpaper", screen: int = 0, opacity: float = 1.0,
            simulate: bool = False, sim_rate: float = 8.0, count_repeats: bool = False) -> int:
    from PySide6.QtWidgets import QApplication, QMessageBox

    from .counter.service import CounterService
    from .grass.assets import SpriteLibrary
    from .grass.meadow_store import MeadowStore
    from .grass.tray import TrayController
    from .grass.wallpaper import WallpaperWindow
    from .grass.window import MeadowWindow

    _setup_logging_if_frozen()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 창이 없어도(메뉴바만 남아도) 계속 실행

    service = CounterService(port, simulate=simulate, sim_rate=sim_rate, count_repeats=count_repeats)
    try:
        service.start()
    except OSError:
        QMessageBox.warning(None, "이미 실행 중이에요",
                            f"포트 {port} 를 이미 사용 중입니다.\nTypeGrass 가 이미 켜져 있는지 확인해 주세요.")
        return 1

    lib = SpriteLibrary(paths.assets_dir())
    mstore = MeadowStore(paths.meadow_db_path())
    if mode == "wallpaper":
        win = WallpaperWindow(mstore, lib, port, screen_index=screen, opacity=opacity)
        win.show_on_desktop()
    else:  # 'window': 바탕화면에 깔기 전에 일반 창으로 시험
        win = MeadowWindow(mstore, lib, port)
        win.show()
        win.show_on_desktop = win.show  # 트레이 메뉴 공용 인터페이스
    tray = TrayController(app, service, win, mstore, lib, port)  # noqa: F841 (참조 유지)

    print(f"TypeGrass 시작: mode={mode}, 카운터 포트 {port}")
    print("에셋:\n" + lib.describe())
    code = app.exec()
    service.stop()
    mstore.close()
    return code
