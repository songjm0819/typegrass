"""대체 풀잎 PNG 14장을 assets/blades/ 에 저장한다.

    python tools/make_placeholder_assets.py            # 없는 파일만 생성
    python tools/make_placeholder_assets.py --force    # 모두 덮어쓰기(주의: 직접 만든 파일도 덮어씀)
    python tools/make_placeholder_assets.py --sheet    # 미리보기 시트도 저장
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from typegrass.grass import procedural  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--sheet", action="store_true")
    args = ap.parse_args()

    out = ROOT / "assets" / "blades"
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for name in procedural.all_names():
        path = out / f"{name}.png"
        if path.exists() and not args.force:
            print(f"건너뜀(이미 있음): {path.name}")
            continue
        img = procedural.make_sprite(name)
        img.save(path)
        made.append((name, img))
        print(f"생성: {path.relative_to(ROOT)}  {img.size}")

    if args.sheet:
        names = procedural.all_names()
        sheet = Image.new("RGBA", (130 * len(names), 262), (70, 55, 40, 255))
        for i, n in enumerate(names):
            im = procedural.make_sprite(n)
            sheet.alpha_composite(im, (i * 130 + 1, 262 - im.height - 2))
        sheet.save(ROOT / "docs" / "preview_sheet.png")
        print("미리보기: docs/preview_sheet.png")


if __name__ == "__main__":
    main()
