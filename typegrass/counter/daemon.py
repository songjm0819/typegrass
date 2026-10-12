"""카운터 프로그램 본체: 키 감지 + 저장 + 조회 API 를 묶는다."""
from __future__ import annotations

import signal
import sys

from .. import DEFAULT_PORT, paths
from .api import make_server, serve_in_thread
from .store import CountStore
from .tally import Tally

PERMISSION_HELP = """
[!] 키 입력 감지를 시작하지 못했습니다 (권한 문제로 보입니다).

  1) 시스템 설정 > 개인정보 보호 및 보안 > 입력 모니터링
  2) 지금 이 명령을 실행 중인 앱(터미널/iTerm/VS Code 등)을 목록에 추가하고 켜기
  3) 그 앱을 완전히 종료(Cmd+Q)한 뒤 다시 열어서 재실행
  (안 되면 '손쉬운 사용' 목록에도 같은 앱을 추가해 보세요)
"""


def build_listener(simulate: bool, sim_rate: float, count_repeats: bool, on_key):
    if simulate:
        from .listener_sim import SimKeyListener

        return SimKeyListener(on_key, rate=sim_rate)
    if sys.platform != "darwin":
        raise SystemExit(
            "이 컴퓨터는 macOS 가 아니라서 실제 키 감지를 쓸 수 없습니다. --simulate 를 붙여 실행하세요."
        )
    from . import listener_macos

    if not listener_macos.has_permission():
        listener_macos.request_permission()
    return listener_macos.MacKeyListener(on_key, count_repeats=count_repeats)


def run_daemon(
    port: int = DEFAULT_PORT,
    simulate: bool = False,
    sim_rate: float = 8.0,
    count_repeats: bool = False,
) -> int:
    store = CountStore(paths.counts_db_path())
    tally = Tally(store)
    try:
        server = make_server(tally, store, port, backend="simulated" if simulate else "macos")
    except OSError as e:
        print(f"[!] 포트 {port} 를 열 수 없습니다: {e}\n    이미 카운터가 실행 중일 수 있습니다.")
        return 1

    listener = build_listener(simulate, sim_rate, count_repeats, tally.increment)

    def _stop(*_):
        listener.stop()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    tally.start()
    serve_in_thread(server)
    day, count = tally.today()
    print(f"타자수만큼 풀자라기 카운터 시작 ({listener.name})")
    print(f"  오늘({day}) 현재 {count:,}타 · 저장 위치: {paths.counts_db_path()}")
    print(f"  조회: curl http://127.0.0.1:{port}/count     (Ctrl+C 로 종료)")
    if not simulate:
        print("  ※ 입력 내용은 저장하지 않고 '횟수'만 셉니다.")

    code = 0
    try:
        listener.run()
    except Exception as e:  # PermissionDenied 포함
        if e.__class__.__name__ == "PermissionDenied":
            print(PERMISSION_HELP)
            code = 2
        else:
            raise
    finally:
        server.shutdown()
        tally.stop()
        store.close()
        print("종료했습니다. 오늘 기록을 저장했습니다." if code == 0 else "")
    return code
