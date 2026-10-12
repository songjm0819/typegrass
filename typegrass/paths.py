"""데이터 저장 위치. 환경변수 TYPEGRASS_HOME 으로 바꿀 수 있다(테스트용)."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("TYPEGRASS_HOME")
    if override:
        base = Path(override).expanduser()
    elif sys.platform == "darwin":
        base = Path("~/Library/Application Support/TypeGrass").expanduser()
    else:
        base = Path("~/.local/share/typegrass").expanduser()
    base.mkdir(parents=True, exist_ok=True)
    return base


def counts_db_path() -> Path:
    return data_dir() / "counts.db"


def meadow_db_path() -> Path:
    return data_dir() / "meadow.db"


def is_frozen() -> bool:
    """PyInstaller 로 만든 앱(.app)으로 실행 중인지."""
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    """소스 실행: 프로젝트 폴더 / 앱 실행: 번들 안의 리소스 폴더."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def user_assets_dir() -> Path:
    return data_dir() / "assets" / "blades"


def assets_dir() -> Path:
    """풀잎 PNG 폴더. 사용자 폴더에 PNG 가 있으면 그쪽이 우선(앱을 다시 빌드하지 않고 에셋 교체 가능)."""
    user = user_assets_dir()
    if user.is_dir() and any(user.glob("*.png")):
        return user
    return project_root() / "assets" / "blades"
