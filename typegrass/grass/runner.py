"""풀밭 창/이미지 내보내기 실행 도우미 (PySide6 import 는 여기서만)."""
from __future__ import annotations

import sys
import time
from datetime import date

from .. import DEFAULT_PORT, paths


def _make_lib(procedural: bool):
    from .assets import SpriteLibrary

    return SpriteLibrary(paths.assets_dir(), force_procedural=procedural)


def run_window(port: int = DEFAULT_PORT, view_day: str | None = None, demo: bool = False,
               demo_rate: float = 25.0, procedural: bool = False) -> int:
    from PySide6.QtWidgets import QApplication

    from .meadow_store import MeadowStore
    from .window import MeadowWindow

    app = QApplication.instance() or QApplication(sys.argv)
    lib = _make_lib(procedural)
    print("풀잎 에셋:\n" + lib.describe())
    store = MeadowStore(":memory:" if demo else paths.meadow_db_path())
    if view_day and not store.has_meadow(view_day):
        print(f"[!] {view_day} 의 풀밭 기록이 없습니다. 기록된 날짜: {', '.join(store.days()) or '(없음)'}")
        return 1
    win = MeadowWindow(store, lib, port, view_day=view_day, demo_rate=demo_rate if demo else None)
    if demo:
        win.setWindowTitle("타자수만큼 풀자라기 (데모: 가짜 타수, 저장 안 함)")
    win.show()
    print("창 단축키: H=정보 표시 전환, F=전체화면, Esc/Q=닫기")
    code = app.exec()
    store.close()
    return code


def render_png(count: int, out: str, size: tuple[int, int] = (1920, 1080), seed: int = 2024,
               procedural: bool = False, store_db: str | None = None, day: str | None = None) -> float:
    """창 없이 PNG 로 저장. day 가 있으면 저장된 그날의 풀밭, 없으면 seed/count 로 임시 생성."""
    from PySide6.QtGui import QGuiApplication

    from .layout import MAX_CLUSTERS, MeadowGenerator, plan_centers
    from .meadow_store import MeadowStore, grow_to
    from .renderer import MeadowCanvas

    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    lib = _make_lib(procedural)
    canvas = MeadowCanvas(lib, ground=True)
    canvas.w, canvas.h = size
    if day:
        store = MeadowStore(store_db or paths.meadow_db_path())
        blades = store.load_blades(day)
    else:
        store = MeadowStore(":memory:")
        gen = store.open_generator("preview", lib.by_cat, seed=seed)
        blades = grow_to(store, gen, "preview", count)
    t0 = time.perf_counter()
    canvas.set_blades(blades)
    canvas.finish_sync()
    img = canvas.render_to_image()
    dt = time.perf_counter() - t0
    img.save(out)
    return dt
