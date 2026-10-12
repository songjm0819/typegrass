"""명령줄 진입점:  python -m typegrass <명령>"""
from __future__ import annotations

import argparse
import sys
import time

from . import DEFAULT_PORT, __version__, paths


def _cmd_counter(a) -> int:
    from .counter.daemon import run_daemon

    return run_daemon(a.port, simulate=a.simulate, sim_rate=a.sim_rate, count_repeats=a.count_repeats)


def _cmd_grass(a) -> int:
    from .grass.runner import run_window

    return run_window(a.port, view_day=a.date, demo=a.demo, demo_rate=a.demo_rate, procedural=a.procedural)


def _cmd_app(a) -> int:
    from .app import run_app

    return run_app(a.port, mode="window" if a.window else "wallpaper", screen=a.screen, opacity=a.opacity,
                   simulate=a.simulate, sim_rate=a.sim_rate, count_repeats=a.count_repeats)


def _cmd_today(a) -> int:
    from .client import get_today

    try:
        d = get_today(a.port)
    except Exception as e:
        print(f"카운터에 연결할 수 없습니다: {e}")
        return 1
    print(f"{d['date']}  {d['count']:,}타")
    return 0


def _cmd_watch(a) -> int:
    from .client import get_today

    print("실시간 타수 (Ctrl+C 로 종료)")
    last = None
    try:
        while True:
            try:
                d = get_today(a.port)
                line = f"\r{d['date']}  {d['count']:>8,}타   "
            except Exception:
                line = "\r카운터에 연결할 수 없음…            "
            if line != last:
                sys.stdout.write(line)
                sys.stdout.flush()
                last = line
            time.sleep(0.2)
    except KeyboardInterrupt:
        print()
    return 0


def _cmd_history(a) -> int:
    from .client import get_history

    try:
        rows = get_history(a.days, a.port)
    except Exception:
        # 카운터가 꺼져 있어도 DB 에서 직접 읽는다
        from .counter.store import CountStore

        rows = [{"date": d, "count": c} for d, c in CountStore(paths.counts_db_path()).history(a.days)]
    for r in rows:
        print(f"{r['date']}  {r['count']:>9,}")
    if not rows:
        print("(기록 없음)")
    return 0


def _cmd_export_csv(a) -> int:
    from .counter.store import CountStore

    n = CountStore(paths.counts_db_path()).export_csv(a.out)
    print(f"{n}일치 기록을 {a.out} 에 저장했습니다.")
    return 0


def _cmd_preview(a) -> int:
    from .grass.runner import render_png

    counts = [int(c) for c in a.counts.split(",")]
    for c in counts:
        out = f"{a.prefix}_{c}.png"
        dt = render_png(c, out, size=(a.width, a.height), seed=a.seed, procedural=a.procedural)
        print(f"{c:>6,}개 -> {out}   (렌더링 {dt:.2f}초)")
    return 0


def _cmd_export_png(a) -> int:
    from .grass.runner import render_png

    dt = render_png(0, a.out, size=(a.width, a.height), day=a.date, procedural=a.procedural)
    print(f"{a.date} 풀밭을 {a.out} 에 저장했습니다 (렌더링 {dt:.2f}초)")
    return 0


def _cmd_assets(a) -> int:
    from .grass.assets import SpriteLibrary

    lib = SpriteLibrary(paths.assets_dir(), force_procedural=a.procedural)
    print(f"에셋 폴더: {paths.assets_dir()}")
    print(lib.describe())
    for cat, names in lib.by_cat.items():
        for n in names:
            print(f"    {n:<12} [{lib.sources[n]}]")
    return 0


def _cmd_doctor(a) -> int:
    import platform

    print(f"Python {platform.python_version()} · {platform.platform()}")
    ok = True
    if sys.version_info < (3, 11):
        print("[!] Python 3.11 이상을 권장합니다.")
        ok = False
    print(f"데이터 폴더: {paths.data_dir()}")
    for mod in ("PySide6", "PIL"):
        try:
            __import__(mod)
            print(f"[OK] {mod}")
        except ImportError:
            print(f"[X] {mod} 미설치 -> pip install -r requirements.txt")
            ok = False
    if sys.platform == "darwin":
        try:
            from .counter import listener_macos

            print("[OK] pyobjc Quartz")
            granted = listener_macos.has_permission()
            print("[OK] 입력 모니터링 권한 있음" if granted else
                  "[X] 입력 모니터링 권한 없음 -> 시스템 설정 > 개인정보 보호 및 보안 > 입력 모니터링")
            ok = ok and granted
        except ImportError:
            print("[X] pyobjc-framework-Quartz 미설치 -> pip install -r requirements.txt")
            ok = False
    else:
        print("(macOS 가 아니므로 키 감지는 --simulate 로만 시험할 수 있습니다)")
    try:
        from .client import get_today

        d = get_today(a.port)
        print(f"[OK] 카운터 실행 중: 오늘 {d['count']:,}타")
    except Exception:
        print("[ ] 카운터가 아직 실행 중이 아닙니다 (python -m typegrass counter)")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="typegrass", description="타자수만큼 풀자라기")
    ap.add_argument("--version", action="version", version=f"typegrass {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        p = sub.add_parser(name, help=help_)
        p.set_defaults(fn=fn)
        return p

    p = add("counter", _cmd_counter, "키 입력 횟수 세기 + 조회 API 서버 실행")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--simulate", action="store_true", help="실제 키 대신 가짜 입력으로 시험")
    p.add_argument("--sim-rate", type=float, default=8.0, help="--simulate 의 초당 입력 수")
    p.add_argument("--count-repeats", action="store_true", help="키를 꾹 눌러 반복되는 입력도 센다")

    p = add("app", _cmd_app, "올인원 실행: 카운터 + 바탕화면 풀밭 + 메뉴바 아이콘")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--window", action="store_true", help="바탕화면 대신 일반 창으로 (시험용)")
    p.add_argument("--screen", type=int, default=0, help="풀을 깔 모니터 번호 (0=주 모니터)")
    p.add_argument("--opacity", type=float, default=1.0, help="풀 투명도 0.1~1.0")
    p.add_argument("--simulate", action="store_true", help="실제 키 대신 가짜 입력으로 시험")
    p.add_argument("--sim-rate", type=float, default=8.0)
    p.add_argument("--count-repeats", action="store_true")

    p = add("grass", _cmd_grass, "풀밭 창 열기")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--date", help="지난 날짜(YYYY-MM-DD)의 풀밭 보기")
    p.add_argument("--demo", action="store_true", help="카운터 없이 가짜 타수로 시연 (저장 안 함)")
    p.add_argument("--demo-rate", type=float, default=25.0, help="--demo 의 초당 타수")
    p.add_argument("--procedural", action="store_true", help="PNG 대신 코드로 그린 임시 풀잎 사용")

    for name, fn, h in (("today", _cmd_today, "오늘 타수 한 번 조회"), ("watch", _cmd_watch, "오늘 타수 실시간 보기")):
        p = add(name, fn, h)
        p.add_argument("--port", type=int, default=DEFAULT_PORT)

    p = add("history", _cmd_history, "날짜별 타수 기록 보기")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)

    p = add("export-csv", _cmd_export_csv, "날짜별 타수를 CSV 로 저장")
    p.add_argument("--out", default="typegrass_counts.csv")

    p = add("preview", _cmd_preview, "타수별 풀밭 모습을 PNG 로 저장 (창 없이)")
    p.add_argument("--counts", default="30,300,3000,30000")
    p.add_argument("--prefix", default="preview")
    p.add_argument("--seed", type=int, default=2024)
    p.add_argument("--width", type=int, default=1920)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--procedural", action="store_true")

    p = add("export-png", _cmd_export_png, "저장된 날짜의 풀밭을 PNG 로 저장")
    p.add_argument("--date", required=True)
    p.add_argument("--out", default="meadow.png")
    p.add_argument("--width", type=int, default=1920)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--procedural", action="store_true")

    p = add("assets", _cmd_assets, "풀잎 에셋 상태 확인")
    p.add_argument("--procedural", action="store_true")

    p = add("doctor", _cmd_doctor, "설치/권한 점검")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
