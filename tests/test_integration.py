"""카운터(가짜 키 입력) -> HTTP API -> 풀밭 창: 타수와 풀잎 수가 일치하는지 확인."""
import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from typegrass.counter.api import make_server, serve_in_thread  # noqa: E402
from typegrass.counter.store import CountStore  # noqa: E402
from typegrass.counter.tally import Tally  # noqa: E402
from typegrass.grass.assets import SpriteLibrary  # noqa: E402
from typegrass.grass.meadow_store import MeadowStore  # noqa: E402
from typegrass.grass.window import MeadowWindow  # noqa: E402


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_window_follows_counter_exactly(tmp_path):
    app = QApplication.instance() or QApplication([])
    cstore = CountStore(tmp_path / "c.db")
    tally = Tally(cstore)
    start_count = tally.today()[1]
    srv = make_server(tally, cstore, 0)
    port = srv.server_address[1]
    serve_in_thread(srv)

    mstore = MeadowStore(tmp_path / "m.db")
    win = MeadowWindow(mstore, SpriteLibrary(None), port)
    win.resize(800, 450)
    win.show()
    try:
        tally.increment(25)  # 사용자가 25번 타자를 침
        pump(1.0)
        assert win.blade_count() == start_count + 25
        tally.increment(1)
        pump(0.6)
        assert win.blade_count() == start_count + 26 == mstore.blade_count(win.day)

        tally.increment(3000)  # 한꺼번에 많이 늘어도(창을 오래 꺼 둔 경우) 따라잡는다
        pump(2.5)
        assert win.blade_count() == start_count + 3026
        win.canvas.finish_sync()
        assert len(win.canvas.blades) == win.blade_count()
    finally:
        win.close()
        srv.shutdown()

    # 창을 다시 열어도 같은 풀밭(같은 풀잎들)
    before = mstore.load_blades(win.day)
    win2 = MeadowWindow(mstore, SpriteLibrary(None), port)
    assert win2.blade_count() == len(before)
    assert mstore.load_blades(win2.day) == before
    win2.close()
