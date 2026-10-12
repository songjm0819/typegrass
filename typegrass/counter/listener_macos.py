"""macOS 전역 키 입력 감지 (Quartz CGEventTap, 읽기 전용).

개인정보 보호:
  - keyDown 이벤트가 "발생했다"는 사실만 센다.
  - 키코드/문자/수정키 정보를 읽지도, 저장하지도 않는다.
  - 이벤트를 가로채거나 바꾸지 않는다(listen-only).

필요한 권한: 시스템 설정 > 개인정보 보호 및 보안 > '입력 모니터링'
  (이 프로그램을 실행하는 터미널 앱에 허용)

※ 이 파일은 macOS 에서만 import 할 수 있다(pyobjc 필요).
"""
from __future__ import annotations

import sys
from typing import Callable

if sys.platform != "darwin":  # pragma: no cover
    raise ImportError("listener_macos 는 macOS 에서만 사용할 수 있습니다.")

import Quartz  # noqa: E402


class PermissionDenied(RuntimeError):
    pass


def has_permission() -> bool:
    """입력 모니터링 권한이 있는지 확인 (macOS 10.15+). 확인 불가하면 True."""
    fn = getattr(Quartz, "CGPreflightListenEventAccess", None)
    return bool(fn()) if fn else True


def request_permission() -> None:
    """권한 요청 팝업을 띄운다(이미 거부했다면 팝업이 안 뜰 수 있다)."""
    fn = getattr(Quartz, "CGRequestListenEventAccess", None)
    if fn:
        fn()


class MacKeyListener:
    name = "macos-cgeventtap"

    def __init__(self, on_key: Callable[[], None], count_repeats: bool = False):
        self._on_key = on_key
        self._count_repeats = count_repeats
        self._tap = None
        self._running = False

    def _callback(self, proxy, event_type, event, refcon):
        # 시스템이 탭을 꺼버리면(너무 느리거나 권한 변경) 다시 켠다.
        if event_type in (
            Quartz.kCGEventTapDisabledByTimeout,
            Quartz.kCGEventTapDisabledByUserInput,
        ):
            if self._tap is not None:
                Quartz.CGEventTapEnable(self._tap, True)
            return event
        if event_type == Quartz.kCGEventKeyDown:
            if not self._count_repeats:
                # 키를 꾹 눌러 자동 반복되는 입력은 1회로만 센다.
                if Quartz.CGEventGetIntegerValueField(
                    event, Quartz.kCGKeyboardEventAutorepeat
                ):
                    return event
            self._on_key()
        return event

    def run(self) -> None:
        """호출한 스레드를 점유하며 이벤트를 받는다. stop() 이 호출되면 반환."""
        mask = Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            mask,
            self._callback,
            None,
        )
        if self._tap is None:
            raise PermissionDenied(
                "키 입력 감지를 시작할 수 없습니다. '입력 모니터링' 권한을 확인하세요."
            )
        source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetCurrent(), source, Quartz.kCFRunLoopCommonModes
        )
        Quartz.CGEventTapEnable(self._tap, True)
        self._running = True
        # 0.25초마다 깨어나 종료 신호(Ctrl+C)를 확인한다.
        while self._running:
            Quartz.CFRunLoopRunInMode(Quartz.kCFRunLoopDefaultMode, 0.25, False)

    def stop(self) -> None:
        self._running = False
