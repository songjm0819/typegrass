#!/bin/bash
# 맥에서 TypeGrass.app 과 배포용 zip 을 만든다.   사용: bash packaging/build_macos.sh
# (Developer ID 서명까지 하려면: CODESIGN_IDENTITY="Developer ID Application: 이름 (TEAMID)" bash packaging/build_macos.sh)
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m venv .venv-build
source .venv-build/bin/activate
pip install --upgrade pip
pip install -r requirements.txt pyinstaller

# 아이콘: assets/icon.png -> build/icon.icns
python tools/make_icon.py
rm -rf build/icon.iconset && mkdir -p build/icon.iconset
for s in 16 32 128 256 512; do
  sips -z $s $s assets/icon.png --out build/icon.iconset/icon_${s}x${s}.png >/dev/null
  sips -z $((s*2)) $((s*2)) assets/icon.png --out build/icon.iconset/icon_${s}x${s}@2x.png >/dev/null
done
iconutil -c icns build/icon.iconset -o build/icon.icns

rm -rf dist
pyinstaller --noconfirm --clean packaging/typegrass.spec

# zip 으로 묶기 (ditto 는 맥 앱의 서명/속성을 보존한다. 일반 zip 명령은 앱을 깨뜨릴 수 있음)
ditto -c -k --sequesterRsrc --keepParent dist/TypeGrass.app dist/TypeGrass-macOS.zip
echo "완료: dist/TypeGrass.app , dist/TypeGrass-macOS.zip"
