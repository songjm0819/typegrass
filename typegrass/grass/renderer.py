"""풀밭 그리기 (PySide6 / QPainter).

성능 설계
  1) 이미 자란 풀잎은 '구워 둔 이미지(baked)' 한 장에 그려 두고 매 프레임 그것만 복사한다.
     -> 풀잎이 5만 개여도 한 프레임 비용은 이미지 1장 + 지금 자라는 몇 개뿐.
  2) 새 풀잎은 짧은 성장 애니메이션(약 0.45초) 동안만 따로 그리고, 끝나면 baked 에 합친다.
  3) 처음 불러오기/창 크기 변경/깊이 순서 정리는 '조각 작업'으로 프레임마다 몇 ms 만 써서
     화면이 멈추지 않게 한다. (뒤쪽 풀잎이 앞쪽 풀잎 위에 덮이는 오차는 이 정리가 바로잡는다.)
  4) 풀잎 이미지는 (이름, 색조, 크기단계)별로 미리 줄여서 캐시 -> 줄이기 품질 저하/계산 낭비 방지.
"""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QTransform

from .assets import SpriteLibrary
from .layout import Blade

REF_HEIGHT = 1080.0  # scale 1.0 = 높이 1080 화면 기준 크기
GROW_SECONDS = 0.45


def _ease_out_back(t: float) -> float:
    t = min(1.0, max(0.0, t))
    c1, c3 = 1.2, 2.2
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


class MeadowCanvas:
    def __init__(self, lib: SpriteLibrary, ground: bool = True):
        self.lib = lib
        self.ground = ground  # False 면 배경 없이 투명(바탕화면용)
        self.w = 1280
        self.h = 720
        self.dpr = 1.0
        self.blades: list[Blade] = []
        self.growing: list[tuple[Blade, float]] = []
        self.baked: QImage | None = None
        self._job: dict | None = None
        self._late = 0  # 마지막 정리 이후 '순서 무시하고' 얹은 풀잎 수

    # ------------------------------------------------------------------ 상태
    def set_size(self, w: int, h: int, dpr: float = 1.0) -> None:
        if (w, h, dpr) == (self.w, self.h, self.dpr) and self.baked is not None:
            return
        self.w, self.h, self.dpr = max(1, w), max(1, h), dpr
        self._start_rebuild(clear_first=True)

    def set_blades(self, blades: list[Blade]) -> None:
        self.blades = list(blades)
        self.growing.clear()
        self._start_rebuild(clear_first=True)

    def add(self, new: list[Blade], animate: bool) -> None:
        """새 풀잎을 추가한다. animate=True 면 짧은 성장 애니메이션 후 baked 에 합쳐진다."""
        if not new:
            return
        self.blades.extend(new)
        if animate:
            now = time.perf_counter()
            self.growing.extend((b, now) for b in new)
        else:
            self._bake_now(new)

    # ------------------------------------------------------------ 그리기 조각
    def _new_image(self) -> QImage:
        img = QImage(
            int(self.w * self.dpr), int(self.h * self.dpr), QImage.Format.Format_ARGB32_Premultiplied
        )
        img.setDevicePixelRatio(self.dpr)
        img.fill(Qt.GlobalColor.transparent)
        return img

    def _draw_blade(self, p: QPainter, b: Blade, grow: float = 1.0) -> None:
        s = b.scale * (self.h / REF_HEIGHT)
        if s <= 0 or grow <= 0:
            return
        level = SpriteLibrary.level_for(s * self.dpr)
        img = self.lib.get(b.sprite, b.tint, level)
        k = s / (1.5**level)  # 단계 이미지에서 실제 크기로 남은 배율 (대략 0.75~1.5)
        sx = -k if b.flip else k
        sy = k * b.stretch * grow
        r = math.radians(b.rot)
        c, sn = math.cos(r), math.sin(r)
        p.setTransform(QTransform(sx * c, sx * sn, -sy * sn, sy * c, b.x * self.w, b.y * self.h))
        p.drawImage(QPointF(-img.width() / 2.0, -float(img.height())), img)

    @staticmethod
    def _painter(img: QImage) -> QPainter:
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        return p

    def _bake_now(self, blades: list[Blade]) -> None:
        """깊이 순서를 따지지 않고 baked 위에 바로 얹는다 (빠르지만 순서는 근사)."""
        if self.baked is None:
            return
        p = self._painter(self.baked)
        for b in blades:
            self._draw_blade(p, b)
        p.end()
        self._late += len(blades)
        if self._job is not None and self._job["swap"]:
            self._job["late"].extend(blades)  # 새 이미지로 교체될 때 함께 얹는다

    # ------------------------------------------------------- 조각 작업(재구성)
    def _start_rebuild(self, clear_first: bool) -> None:
        """모든 풀잎을 먼(위쪽) 것부터 순서대로 다시 그린다. 프레임마다 조금씩 진행."""
        growing_ids = {id(b) for b, _ in self.growing}  # 아직 자라는 중인 것은 나중에 따로 합쳐진다
        order = sorted((b for b in self.blades if id(b) not in growing_ids), key=lambda b: (b.y, b.idx))
        img = self._new_image()
        if clear_first:
            self.baked = img  # 빈 화면에서 시작해 점점 채워지는 모습이 그대로 보인다
        self._job = {"img": img, "order": order, "pos": 0, "late": [], "swap": not clear_first}
        self._late = 0

    def needs_frames(self) -> bool:
        return bool(self.growing) or self._job is not None

    def step(self, budget_ms: float = 8.0) -> None:
        """프레임 타이머에서 호출: 성장 끝난 풀잎 합치기 + 재구성 작업을 budget_ms 만큼 진행."""
        now = time.perf_counter()
        if self.growing:
            done = [b for b, t0 in self.growing if now - t0 >= GROW_SECONDS]
            if done:
                self.growing = [(b, t0) for b, t0 in self.growing if now - t0 < GROW_SECONDS]
                self._bake_now(done)
        if self._job is None and self._late >= max(800, len(self.blades) // 10):
            self._start_rebuild(clear_first=False)

        job = self._job
        if job is None:
            return
        t_end = time.perf_counter() + budget_ms / 1000.0
        order, pos = job["order"], job["pos"]
        n = len(order)
        p = self._painter(job["img"])
        while pos < n and time.perf_counter() < t_end:
            for _ in range(64):
                if pos >= n:
                    break
                self._draw_blade(p, order[pos])
                pos += 1
        job["pos"] = pos
        if pos >= n:
            for b in job["late"]:
                self._draw_blade(p, b)
            p.end()
            self.baked = job["img"]
            self._job = None
            self._late = 0
        else:
            p.end()

    def finish_sync(self) -> None:
        """(이미지 저장용) 진행 중인 작업과 성장 애니메이션을 한 번에 끝낸다."""
        while self._job is not None:
            self.step(budget_ms=1e9)
        if self.growing:
            self._bake_now([b for b, _ in self.growing])
            self.growing = []

    # ---------------------------------------------------------------- 그리기
    def paint(self, p: QPainter) -> None:
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.resetTransform()
        if self.ground:
            g = QLinearGradient(0, 0, 0, self.h)
            g.setColorAt(0.0, QColor(58, 52, 34))
            g.setColorAt(1.0, QColor(44, 36, 24))
            p.fillRect(QRectF(0, 0, self.w, self.h), g)
        if self.baked is not None:
            p.drawImage(QPointF(0, 0), self.baked)
        now = time.perf_counter()
        for b, t0 in self.growing:
            self._draw_blade(p, b, _ease_out_back((now - t0) / GROW_SECONDS))
        p.resetTransform()

    def render_to_image(self) -> QImage:
        self.finish_sync()
        img = QImage(
            int(self.w * self.dpr), int(self.h * self.dpr), QImage.Format.Format_ARGB32_Premultiplied
        )
        img.setDevicePixelRatio(self.dpr)
        p = QPainter(img)
        self.paint(p)
        p.end()
        return img
