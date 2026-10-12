"""앱 아이콘 assets/icon.png (1024x1024) 생성. 풀잎 그래픽으로 직접 그린 아이콘이라 저작권 걱정이 없다.

    python tools/make_icon.py
(맥에서 packaging/build_macos.sh 가 이 PNG 를 .icns 로 변환한다)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from typegrass.grass import procedural  # noqa: E402

S = 1024


def main():
    bg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / S
        gd.line([(0, y), (S, y)], fill=(int(190 - 90 * t), int(228 - 70 * t), int(170 - 90 * t), 255))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((40, 40, S - 40, S - 40), radius=210, fill=255)
    bg.paste(grad, (0, 0), mask)

    layout = [  # (스프라이트, 가운데 x, 높이 px)
        ("grass_04", 250, 560), ("grass_02", 800, 600), ("grass_03", 400, 700),
        ("grass_06", 640, 760), ("grass_01", 520, 820), ("weed_04", 170, 420),
    ]
    clip = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    for name, cx, h in layout:
        sp = procedural.make_sprite(name)
        k = h / sp.height
        sp = sp.resize((max(1, int(sp.width * k)), h), Image.LANCZOS)
        clip.alpha_composite(sp, (cx - sp.width // 2, S - 90 - h))
    clip_masked = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    clip_masked.paste(clip, (0, 0), mask)
    bg.alpha_composite(clip_masked)
    out = ROOT / "assets" / "icon.png"
    bg.save(out)
    print("저장:", out)


if __name__ == "__main__":
    main()
