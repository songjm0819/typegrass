import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from typegrass.grass.assets import SpriteLibrary  # noqa: E402
from typegrass.grass.layout import GRASS, SPROUT, WEED, TINT_COUNT  # noqa: E402
from typegrass.grass.meadow_store import MeadowStore, grow_to  # noqa: E402
from typegrass.grass.renderer import MeadowCanvas  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QGuiApplication.instance() or QGuiApplication([])


def test_fallback_when_no_assets(app, tmp_path):
    lib = SpriteLibrary(tmp_path / "does_not_exist")
    for cat in (SPROUT, GRASS, WEED):
        assert lib.by_cat[cat]
        assert all(lib.sources[n] == "procedural" for n in lib.by_cat[cat])


def test_user_files_take_priority_and_missing_name_resolves(app, tmp_path):
    from PIL import Image

    Image.new("RGBA", (40, 80), (30, 160, 40, 255)).save(tmp_path / "grass_01.png")
    lib = SpriteLibrary(tmp_path)
    assert lib.by_cat[GRASS] == ["grass_01"] and lib.sources["grass_01"] == "file"
    assert lib.by_cat[WEED] and lib.sources[lib.by_cat[WEED][0]] == "procedural"
    assert lib.resolve("grass_06") == "grass_01"  # 예전에 저장된 이름이 없어져도 안전


def test_tints_differ(app):
    lib = SpriteLibrary(None)
    a = lib.get("grass_01", 0, 0)
    b = lib.get("grass_01", TINT_COUNT - 1, 0)
    assert a.size() == b.size() and a != b


def test_render_transparent_background_and_blade_count(app):
    lib = SpriteLibrary(None)
    store = MeadowStore(":memory:")
    g = store.open_generator("d", lib.by_cat, seed=3)
    blades = grow_to(store, g, "d", 600)
    c = MeadowCanvas(lib, ground=False)  # 바탕화면용 투명 배경
    c.set_size(800, 450)
    c.set_blades(blades)
    img = c.render_to_image()
    assert img.pixelColor(2, 2).alpha() == 0  # 풀이 없는 곳은 완전 투명
    opaque = sum(1 for x in range(0, 800, 4) for y in range(0, 450, 4) if img.pixelColor(x, y).alpha() > 0)
    assert opaque > 50
    assert len(c.blades) == 600


def test_incremental_add_and_growth_animation(app):
    lib = SpriteLibrary(None)
    store = MeadowStore(":memory:")
    g = store.open_generator("d", lib.by_cat, seed=3)
    c = MeadowCanvas(lib, ground=False)
    c.set_size(640, 360)
    c.add(grow_to(store, g, "d", 5), animate=True)
    assert len(c.growing) == 5 and c.needs_frames()
    c.finish_sync()
    assert not c.growing and len(c.blades) == 5
