"""풀잎 이미지(에셋) 불러오기, 색조 입히기, 크기별 캐시.

규칙
  * assets/blades/<카테고리>_<번호>.png  (카테고리: sprout / grass / weed)
  * 투명 배경 PNG(RGBA). 풀뿌리가 이미지 '아래쪽 가운데'에 오도록 만든다.
  * 어떤 카테고리에 파일이 하나라도 있으면 그 파일들만 쓰고,
    하나도 없으면 코드로 그린 임시 풀잎(procedural.py)을 대신 쓴다.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image
from PySide6.QtGui import QImage

from . import procedural
from .layout import GRASS, SPROUT, WEED, tint_factors

CATEGORIES = (SPROUT, GRASS, WEED)
MAX_NATIVE_HEIGHT = 256  # 너무 큰 원본은 불러올 때 줄여 메모리를 아낀다
LEVEL_BASE = 1.5  # 크기 단계 간격 (1.5배씩)


def _to_qimage(img: Image.Image) -> QImage:
    img = img.convert("RGBA")
    w, h = img.size
    q = QImage(img.tobytes(), w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
    return q.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)


def _tint(img: Image.Image, tint: int) -> Image.Image:
    fr, fg, fb = tint_factors(tint)
    r, g, b, a = img.split()
    lut = lambda f: [min(255, int(v * f + 0.5)) for v in range(256)]  # noqa: E731
    return Image.merge("RGBA", (r.point(lut(fr)), g.point(lut(fg)), b.point(lut(fb)), a))


class SpriteLibrary:
    def __init__(self, assets_dir: str | Path | None = None, force_procedural: bool = False):
        self.sources: dict[str, str] = {}  # 이름 -> "file" | "procedural"
        self._base: dict[str, Image.Image] = {}
        self.by_cat: dict[str, list[str]] = {c: [] for c in CATEGORIES}
        self._cache: dict[tuple[str, int, int], QImage] = {}

        found: dict[str, list[tuple[str, Path]]] = {c: [] for c in CATEGORIES}
        if assets_dir and not force_procedural:
            for p in sorted(Path(assets_dir).glob("*.png")):
                cat = p.stem.split("_")[0]
                if cat in found:
                    found[cat].append((p.stem, p))

        for cat in CATEGORIES:
            if found[cat]:
                for name, path in found[cat]:
                    try:
                        img = Image.open(path).convert("RGBA")
                    except Exception as e:  # 깨진 파일은 건너뛴다
                        print(f"[경고] 이미지를 읽지 못해 건너뜀: {path.name} ({e})")
                        continue
                    if img.height > MAX_NATIVE_HEIGHT:
                        k = MAX_NATIVE_HEIGHT / img.height
                        img = img.resize((max(1, round(img.width * k)), MAX_NATIVE_HEIGHT), Image.LANCZOS)
                    self._base[name] = img
                    self.sources[name] = "file"
                    self.by_cat[cat].append(name)
            if not self.by_cat[cat]:
                for name in procedural.SPRITE_NAMES[cat]:
                    self._base[name] = procedural.make_sprite(name)
                    self.sources[name] = "procedural"
                    self.by_cat[cat].append(name)

    # 저장된 풀잎이 가리키는 이름이 지금 없을 때(에셋 교체 등) 같은 카테고리의 다른 것으로 대체
    def resolve(self, name: str) -> str:
        if name in self._base:
            return name
        cat = name.split("_")[0]
        pool = self.by_cat.get(cat) or self.by_cat[GRASS]
        return pool[sum(map(ord, name)) % len(pool)]

    def native_height(self, name: str) -> int:
        return self._base[self.resolve(name)].height

    def get(self, name: str, tint: int, level: int) -> QImage:
        """name 스프라이트에 tint 색조를 입히고 LEVEL_BASE**level 배로 줄이거나 키운 이미지."""
        name = self.resolve(name)
        key = (name, tint, level)
        q = self._cache.get(key)
        if q is None:
            q = _to_qimage(_tint(self._base[name], tint))
            k = LEVEL_BASE**level
            if abs(k - 1.0) > 1e-6:
                from PySide6.QtCore import Qt

                q = q.scaled(
                    max(1, round(q.width() * k)),
                    max(1, round(q.height() * k)),
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            self._cache[key] = q
        return q

    @staticmethod
    def level_for(scale: float) -> int:
        return max(-9, min(2, round(math.log(max(scale, 1e-3), LEVEL_BASE))))

    def describe(self) -> str:
        lines = []
        for cat in CATEGORIES:
            n_file = sum(1 for n in self.by_cat[cat] if self.sources[n] == "file")
            kind = f"파일 {n_file}장" if n_file else "임시 그래픽(코드로 그림)"
            lines.append(f"  {cat:<7} {len(self.by_cat[cat])}종 · {kind}")
        return "\n".join(lines)
