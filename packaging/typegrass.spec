# PyInstaller 설정: macOS 용 TypeGrass.app 을 만든다.   실행은 packaging/build_macos.sh 로.
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ICON = os.path.join(ROOT, "build", "icon.icns")
BUNDLE_ID = os.environ.get("TYPEGRASS_BUNDLE_ID", "io.github.songjm0819.typegrass")
IDENTITY = os.environ.get("CODESIGN_IDENTITY") or None  # 없으면 임시(ad-hoc) 서명

a = Analysis(
    [os.path.join(ROOT, "packaging", "entry.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "assets", "blades"), "assets/blades")],
    hiddenimports=["typegrass.counter.listener_macos", "Quartz", "objc", "AppKit", "Foundation"],
    excludes=["tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="TypeGrass",
    console=False,
    codesign_identity=IDENTITY,
    entitlements_file=os.path.join(ROOT, "packaging", "entitlements.plist") if IDENTITY else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="TypeGrass")
app = BUNDLE(
    coll,
    name="TypeGrass.app",
    icon=ICON if os.path.exists(ICON) else None,
    bundle_identifier=BUNDLE_ID,
    version="0.2.0",
    info_plist={
        "CFBundleName": "TypeGrass",
        "CFBundleDisplayName": "TypeGrass",
        "LSUIElement": True,  # Dock 에 아이콘을 만들지 않고 메뉴바에만 표시
        "NSHighResolutionCapable": True,
    },
)
