import json
import time
import urllib.request

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from typegrass import paths  # noqa: E402
from typegrass.counter.service import CounterService, RUNNING  # noqa: E402
from typegrass.grass.assets import SpriteLibrary  # noqa: E402
from typegrass.grass.meadow_store import MeadowStore  # noqa: E402
from typegrass.grass.wallpaper import WallpaperWindow  # noqa: E402


def pump(sec):
    end = time.time() + sec
    while time.time() < end:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_service_counts_and_serves(tmp_path):
    svc = CounterService(port=0, simulate=True, sim_rate=200, db_path=tmp_path / "c.db")
    svc.start()
    try:
        port = svc.server.server_address[1]
        time.sleep(0.6)
        assert svc.status == RUNNING
        c = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/today").read())["count"]
        assert c > 20
    finally:
        svc.stop()


def test_service_port_in_use(tmp_path):
    a = CounterService(port=0, simulate=True, db_path=tmp_path / "a.db")
    a.start()
    port = a.server.server_address[1]
    b = CounterService(port=port, simulate=True, db_path=tmp_path / "b.db")
    try:
        with pytest.raises(OSError):
            b.start()
    finally:
        a.stop()


def test_wallpaper_window_transparent_and_follows_counter(tmp_path):
    app = QApplication.instance() or QApplication([])
    svc = CounterService(port=0, simulate=True, sim_rate=60, db_path=tmp_path / "c.db")
    svc.start()
    port = svc.server.server_address[1]
    mstore = MeadowStore(tmp_path / "m.db")
    win = WallpaperWindow(mstore, SpriteLibrary(None), port, opacity=0.9)
    win.show_on_desktop()
    try:
        pump(2.0)
        n = svc.today()[1]
        assert n > 30
        assert abs(win.blade_count() - n) <= 15  # 폴링 지연만큼만 차이 (창은 항상 따라잡음)
        win.canvas.finish_sync()
        img = win.canvas.render_to_image()
        assert img.pixelColor(1, 1).alpha() == 0  # 바탕화면 모드는 배경이 투명
        assert win.show_hud is False
    finally:
        win.close()
        svc.stop()


def test_user_assets_override(tmp_path, monkeypatch):
    monkeypatch.setenv("TYPEGRASS_HOME", str(tmp_path))
    assert paths.assets_dir() == paths.project_root() / "assets" / "blades"
    from PIL import Image

    paths.user_assets_dir().mkdir(parents=True)
    Image.new("RGBA", (10, 20), (0, 200, 0, 255)).save(paths.user_assets_dir() / "grass_01.png")
    assert paths.assets_dir() == paths.user_assets_dir()
