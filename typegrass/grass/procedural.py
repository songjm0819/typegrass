"""대체(임시) 풀잎 그래픽을 코드로 그려서 만든다 (Pillow 사용, 외부 이미지 불필요).

- 투명 배경 RGBA, 뿌리가 이미지 아래쪽 가운데에 오도록 그린다(= 실제 에셋 규격과 동일).
- 4배 크게 그린 뒤 줄여서 가장자리를 부드럽게 한다.
- 사진처럼 사실적이지는 않다. 실제 사진 에셋이 준비되기 전의 '자리 표시자'이자
  테스트용이다. (assets/blades/ 에 같은 이름의 PNG 를 넣으면 그쪽이 우선 사용된다.)

생성되는 파일 이름은 SPRITE_SPECS 의 키와 같다.
"""
from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw

SS = 4  # 슈퍼샘플링 배율

CANVAS = {"grass": (128, 256), "sprout": (96, 128), "weed": (128, 160)}

# 이름 -> 카테고리 (파일명 규칙: <카테고리>_<번호>.png)
SPRITE_NAMES = {
    "sprout": ["sprout_01", "sprout_02", "sprout_03", "sprout_04"],
    "grass": ["grass_01", "grass_02", "grass_03", "grass_04", "grass_05", "grass_06"],
    "weed": ["weed_01", "weed_02", "weed_03", "weed_04"],
}


# ------------------------------------------------------------------ 도형 도우미
def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _gradient(size, y_top, y_bottom, c_top, c_bottom):
    """세로 그라데이션 RGB 이미지."""
    w, h = size
    img = Image.new("RGB", size, c_bottom)
    d = ImageDraw.Draw(img)
    span = max(1, y_bottom - y_top)
    for y in range(h):
        t = min(1.0, max(0.0, (y - y_top) / span))  # 위=0, 아래=1
        d.line([(0, y), (w, y)], fill=_lerp(c_top, c_bottom, t))
    return img


def _spine(base, tip, curve, n=28):
    """뿌리 -> 끝으로 휘어지는 중심선 좌표."""
    (bx, by), (tx, ty) = base, tip
    pts = []
    for i in range(n + 1):
        t = i / n
        x = bx + (tx - bx) * t + curve * math.sin(t * math.pi * 0.5) ** 2 * abs(ty - by) * 0.5
        y = by + (ty - by) * t
        pts.append((x, y))
    return pts


def _outline(spine, half_width_fn):
    """중심선 양옆으로 폭을 준 좌/우 윤곽선."""
    left, right = [], []
    n = len(spine) - 1
    for i, (x, y) in enumerate(spine):
        j = min(n, i + 1)
        k = max(0, i - 1)
        dx, dy = spine[j][0] - spine[k][0], spine[j][1] - spine[k][1]
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln, dx / ln
        hw = half_width_fn(i / n)
        left.append((x + nx * hw, y + ny * hw))
        right.append((x - nx * hw, y - ny * hw))
    return left, right


class _Canvas:
    def __init__(self, w, h):
        self.w, self.h = w * SS, h * SS
        self.img = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))

    def part(self, poly, c_top, c_bottom, y_top=None, y_bottom=None):
        ys = [p[1] for p in poly]
        y_top = min(ys) if y_top is None else y_top
        y_bottom = max(ys) if y_bottom is None else y_bottom
        mask = Image.new("L", (self.w, self.h), 0)
        ImageDraw.Draw(mask).polygon(poly, fill=255)
        grad = _gradient((self.w, self.h), y_top, y_bottom, c_top, c_bottom)
        self.img.paste(grad, (0, 0), mask)
        return mask

    def overlay_poly(self, poly, rgba):
        ov = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        ImageDraw.Draw(ov).polygon(poly, fill=rgba)
        self.img = Image.alpha_composite(self.img, ov)

    def overlay_line(self, pts, rgba, width):
        ov = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        ImageDraw.Draw(ov).line(pts, fill=rgba, width=max(1, int(width)), joint="curve")
        self.img = Image.alpha_composite(self.img, ov)

    def overlay_ellipse(self, box, rgba):
        ov = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        ImageDraw.Draw(ov).ellipse(box, fill=rgba)
        self.img = Image.alpha_composite(self.img, ov)

    def finish(self, w, h):
        return self.img.resize((w, h), Image.LANCZOS)


def _leaf(cv, base, length, angle_deg, width, curve, c_top, c_bottom, midrib=True, teeth=0, veins=0):
    """한 장의 잎. angle_deg: 0=위쪽, +는 오른쪽으로 기울어짐. 좌표는 슈퍼샘플 기준."""
    a = math.radians(angle_deg)
    tip = (base[0] + math.sin(a) * length, base[1] - math.cos(a) * length)
    spine = _spine(base, tip, curve)

    def hw(t):
        w = width * (math.sin(min(1.0, t * 1.15 + 0.08) * math.pi * 0.5 + 0.0)) * (1 - t) ** 0.62
        w = max(w, 0.0)
        if teeth:
            w *= 0.72 + 0.28 * (1 if int(t * teeth * 2) % 2 == 0 else 0)
        return w

    left, right = _outline(spine, hw)
    poly = left + right[::-1]
    cv.part(poly, c_top, c_bottom)
    # 입체감: 한쪽 면을 살짝 밝게, 가운데 줄기는 어둡게
    cv.overlay_poly(spine + left[::-1], (255, 255, 220, 38))
    if midrib:
        cv.overlay_line(spine[1:-2], (20, 55, 15, 110), SS * 1.4)
    for i in range(veins):
        t = (i + 1) / (veins + 1) * 0.8
        k = int(t * (len(spine) - 1))
        cv.overlay_line([spine[k], left[min(len(left) - 1, k + 3)]], (20, 55, 15, 60), SS * 0.8)
        cv.overlay_line([spine[k], right[min(len(right) - 1, k + 3)]], (20, 55, 15, 60), SS * 0.8)
    return spine


# -------------------------------------------------------------------- 풀 (grass)
_GRASS_SPECS = {
    # curve: 휘어짐, width: 최대 폭(픽셀), height: 높이 비율, 색: (끝, 뿌리)
    "grass_01": dict(curve=0.30, width=7.0, height=0.95, top=(150, 200, 70), bot=(28, 80, 28)),
    "grass_02": dict(curve=-0.22, width=6.0, height=0.88, top=(128, 190, 80), bot=(24, 74, 34)),
    "grass_03": dict(curve=0.55, width=8.0, height=0.80, top=(170, 205, 70), bot=(40, 90, 26)),
    "grass_04": dict(curve=-0.45, width=5.0, height=1.00, top=(140, 195, 60), bot=(30, 78, 24)),
    "grass_05": dict(curve=0.10, width=9.0, height=0.70, top=(120, 180, 70), bot=(26, 70, 30)),
    "grass_06": dict(curve=-0.12, width=4.5, height=0.92, top=(175, 210, 90), bot=(34, 84, 30)),
}


def _make_grass(name):
    s = _GRASS_SPECS[name]
    w, h = CANVAS["grass"]
    cv = _Canvas(w, h)
    base = (w * SS / 2, (h - 2) * SS)
    _leaf(
        cv, base, length=(h - 8) * SS * s["height"], angle_deg=0, width=s["width"] * SS,
        curve=s["curve"], c_top=s["top"], c_bottom=s["bot"],
    )
    return cv.finish(w, h)


# ------------------------------------------------------------------ 새싹 (sprout)
def _make_sprout(name):
    w, h = CANVAS["sprout"]
    cv = _Canvas(w, h)
    bx, by = w * SS / 2, (h - 2) * SS
    top, bot = (170, 215, 100), (60, 120, 40)
    if name == "sprout_01":  # 떡잎 두 장
        stem = _spine((bx, by), (bx, by - 40 * SS), 0.05)
        cv.overlay_line(stem, (70, 130, 50, 255), SS * 2.2)
        _leaf(cv, stem[-1], 38 * SS, -62, 10 * SS, -0.1, top, bot)
        _leaf(cv, stem[-1], 38 * SS, 62, 10 * SS, 0.1, top, bot)
        _leaf(cv, stem[-1], 24 * SS, 0, 5 * SS, 0.0, (190, 225, 110), bot)
    elif name == "sprout_02":  # 짧은 풀 세 가닥
        for ang, ln, wd in ((-22, 62, 4.5), (3, 80, 5.0), (24, 56, 4.2)):
            _leaf(cv, (bx, by), ln * SS, ang, wd * SS, ang * 0.006, top, bot)
    elif name == "sprout_03":  # 꼬불 새싹 한 가닥
        _leaf(cv, (bx, by), 92 * SS, 8, 5.5 * SS, 0.7, (185, 225, 105), (55, 115, 40))
    else:  # 새싹 04: 둥근 잎 한 쌍 + 끝눈
        stem = _spine((bx, by), (bx + 3 * SS, by - 46 * SS), 0.2)
        cv.overlay_line(stem, (70, 130, 50, 255), SS * 2.0)
        _leaf(cv, stem[len(stem) // 2], 30 * SS, -70, 12 * SS, -0.1, (160, 210, 90), bot)
        _leaf(cv, stem[len(stem) // 2], 30 * SS, 70, 12 * SS, 0.1, (160, 210, 90), bot)
        _leaf(cv, stem[-1], 30 * SS, 4, 7 * SS, 0.1, (190, 228, 110), bot)
    return cv.finish(w, h)


# -------------------------------------------------------------------- 잡초 (weed)
def _make_weed(name):
    w, h = CANVAS["weed"]
    cv = _Canvas(w, h)
    bx, by = w * SS / 2, (h - 2) * SS
    if name == "weed_01":  # 토끼풀(클로버): 줄기 + 세 갈래 잎
        stem = _spine((bx, by), (bx + 4 * SS, by - 70 * SS), 0.15)
        cv.overlay_line(stem, (70, 125, 50, 255), SS * 2.0)
        cx, cy = stem[-1]
        for ang in (-58, 0, 58):
            rad = math.radians(ang)
            ox, oy = cx + math.sin(rad) * 18 * SS, cy - math.cos(rad) * 14 * SS
            pts = [
                (ox + math.cos(k / 18 * math.tau) * 17 * SS, oy + math.sin(k / 18 * math.tau) * 15 * SS)
                for k in range(18)
            ]
            cv.part(pts, (125, 190, 80), (40, 110, 45))
            cv.overlay_line([(cx, cy), (ox, oy)], (210, 235, 190, 120), SS * 1.2)
            cv.overlay_poly(
                [(ox - 9 * SS, oy), (ox, oy - 6 * SS), (ox + 9 * SS, oy), (ox, oy + 4 * SS)],
                (235, 245, 215, 70),
            )
    elif name == "weed_02":  # 질경이 같은 넓은 잎 (잎맥)
        _leaf(cv, (bx, by), 112 * SS, 6, 26 * SS, 0.18, (120, 185, 75), (36, 96, 38), veins=5)
    elif name == "weed_03":  # 민들레 잎 (톱니)
        _leaf(cv, (bx, by), 118 * SS, -10, 20 * SS, -0.3, (135, 195, 70), (45, 100, 35), teeth=7)
    else:  # weed_04: 작은 들꽃(데이지 느낌)
        stem = _spine((bx, by), (bx - 3 * SS, by - 98 * SS), -0.12)
        cv.overlay_line(stem, (70, 125, 50, 255), SS * 2.0)
        _leaf(cv, stem[8], 34 * SS, 55, 7 * SS, 0.1, (130, 190, 80), (40, 100, 40))
        fx, fy = stem[-1]
        for k in range(10):
            ang = k / 10 * math.tau
            cx, cy = fx + math.cos(ang) * 11 * SS, fy + math.sin(ang) * 11 * SS
            cv.overlay_ellipse((cx - 6 * SS, cy - 6 * SS, cx + 6 * SS, cy + 6 * SS), (250, 250, 245, 255))
        cv.overlay_ellipse((fx - 6.5 * SS, fy - 6.5 * SS, fx + 6.5 * SS, fy + 6.5 * SS), (245, 200, 50, 255))
    return cv.finish(w, h)


def make_sprite(name: str) -> Image.Image:
    cat = name.split("_")[0]
    if cat == "grass":
        return _make_grass(name)
    if cat == "sprout":
        return _make_sprout(name)
    if cat == "weed":
        return _make_weed(name)
    raise KeyError(name)


def all_names() -> list[str]:
    return [n for names in SPRITE_NAMES.values() for n in names]
