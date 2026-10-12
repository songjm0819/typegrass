import json
import threading
import urllib.request
from datetime import datetime

from typegrass.counter.api import make_server, serve_in_thread
from typegrass.counter.store import CountStore
from typegrass.counter.tally import Tally


class FakeClock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def test_count_persists_across_restart(tmp_path):
    db = tmp_path / "c.db"
    clock = FakeClock(datetime(2026, 10, 4, 9, 0))
    s = CountStore(db)
    t = Tally(s, clock)
    for _ in range(123):
        t.increment()
    t.stop()
    s.close()

    s2 = CountStore(db)
    t2 = Tally(s2, clock)
    assert t2.today() == ("2026-10-04", 123)  # 재실행해도 이어받음
    t2.increment()
    assert t2.today()[1] == 124


def test_midnight_resets_today_and_keeps_yesterday(tmp_path):
    s = CountStore(tmp_path / "c.db")
    clock = FakeClock(datetime(2026, 10, 4, 23, 59, 58))
    t = Tally(s, clock)
    for _ in range(50):
        t.increment()
    clock.t = datetime(2026, 10, 5, 0, 0, 1)
    assert t.today() == ("2026-10-05", 0)  # 키를 안 눌러도 조회 값은 0 으로 시작
    t.increment()
    t.increment()
    assert t.today() == ("2026-10-05", 2)
    t.flush()
    assert s.get("2026-10-04") == 50  # 어제 기록 보존
    assert s.get("2026-10-05") == 2


def test_month_boundary_same_day_number(tmp_path):
    """KeyCounter 는 '일(day)'만 비교해 한 달 뒤 같은 일자에서는 리셋이 안 되던 문제가 있었다."""
    s = CountStore(tmp_path / "c.db")
    clock = FakeClock(datetime(2026, 9, 4, 12, 0))
    t = Tally(s, clock)
    t.increment(10)
    clock.t = datetime(2026, 10, 4, 12, 0)
    assert t.today() == ("2026-10-04", 0)
    assert s.get("2026-09-04") == 10


def test_thread_safety(tmp_path):
    s = CountStore(tmp_path / "c.db")
    t = Tally(s, FakeClock(datetime(2026, 10, 4, 12, 0)))
    def work():
        for _ in range(2000):
            t.increment()
    ths = [threading.Thread(target=work) for _ in range(8)]
    [x.start() for x in ths]
    [x.join() for x in ths]
    assert t.today()[1] == 16000


def test_http_api(tmp_path):
    s = CountStore(tmp_path / "c.db")
    t = Tally(s, FakeClock(datetime(2026, 10, 4, 12, 0)))
    t.increment(7)
    srv = make_server(t, s, 0, backend="test")
    port = srv.server_address[1]
    serve_in_thread(srv)
    try:
        base = f"http://127.0.0.1:{port}"
        assert urllib.request.urlopen(base + "/count").read() == b"7"
        d = json.loads(urllib.request.urlopen(base + "/today").read())
        assert d == {"date": "2026-10-04", "count": 7}
        t.increment()
        assert urllib.request.urlopen(base + "/count").read() == b"8"  # 실시간 반영
        h = json.loads(urllib.request.urlopen(base + "/history?days=5").read())
        assert h["days"][0] == {"date": "2026-10-04", "count": 8}
        # 다른 호스트 이름(DNS rebinding)은 거부
        req = urllib.request.Request(base + "/count", headers={"Host": "evil.example.com"})
        try:
            urllib.request.urlopen(req)
            assert False, "should be forbidden"
        except urllib.error.HTTPError as e:
            assert e.code == 403
    finally:
        srv.shutdown()


def test_csv_export(tmp_path):
    s = CountStore(tmp_path / "c.db")
    s.set("2026-10-03", 5)
    s.set("2026-10-04", 9)
    out = tmp_path / "o.csv"
    assert s.export_csv(out) == 2
    assert out.read_text(encoding="utf-8").splitlines() == ["Date,Count", "2026-10-03,5", "2026-10-04,9"]
