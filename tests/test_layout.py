import math
from collections import Counter

from typegrass.grass.layout import (
    MAX_CLUSTERS, MeadowGenerator, plan_centers, target_active, tint_factors, TINT_COUNT,
)
from typegrass.grass.meadow_store import MeadowStore, grow_to

SPRITES = {
    "sprout": ["sprout_01", "sprout_02"],
    "grass": ["grass_01", "grass_02", "grass_03"],
    "weed": ["weed_01"],
}


def gen(seed=7):
    return MeadowGenerator(seed, plan_centers(seed), SPRITES)


def test_one_blade_per_call_and_sequential_idx():
    g = gen()
    blades = g.generate(500)
    assert len(blades) == 500 == g.total
    assert [b.idx for b in blades] == list(range(500))


def test_deterministic():
    a = gen(5).generate(300)
    b = gen(5).generate(300)
    assert a == b
    assert a != gen(6).generate(300)


def test_blades_stay_on_screen_and_tint_valid():
    for b in gen().generate(3000):
        assert 0 <= b.x <= 1 and 0 <= b.y <= 1
        assert 0 <= b.tint < TINT_COUNT
        assert b.sprite in sum(SPRITES.values(), [])
        assert b.scale > 0
        assert all(f > 0 for f in tint_factors(b.tint))


def test_centers_spread_across_screen():
    plans = plan_centers(11)
    assert len(plans) == MAX_CLUSTERS
    xs = [p.cx for p in plans]
    ys = [p.cy for p in plans]
    assert min(xs) < 0.2 and max(xs) > 0.8 and min(ys) < 0.25 and max(ys) > 0.75
    # 가장 가까운 두 중심점도 너무 붙어 있지 않다
    d = min(math.hypot(a.cx - b.cx, (a.cy - b.cy) * 0.56) for i, a in enumerate(plans) for b in plans[i + 1:])
    assert d > 0.03


def test_not_uniform_blades_cluster_around_centers():
    """균등 랜덤이면 8x8 격자 칸별 개수가 비슷하다. 군락 방식은 칸별 편차가 훨씬 크다."""
    g = gen(21)
    blades = g.generate(1500)
    cells = Counter((int(b.x * 8), int(b.y * 8)) for b in blades)
    counts = [cells.get((i, j), 0) for i in range(8) for j in range(8)]
    mean = sum(counts) / 64
    var = sum((c - mean) ** 2 for c in counts) / 64
    # 균등 분포(푸아송)의 분산은 평균 근처. 군락은 몇 배 이상.
    assert var > 4 * mean


def test_growth_stages_cluster_count_increases():
    assert target_active(0) == 3
    assert target_active(100) < target_active(1000) < target_active(10000)
    assert target_active(10**7) == MAX_CLUSTERS
    g = gen(3)
    g.generate(40)
    few = len(g.opened)
    g.generate(4000)
    assert len(g.opened) > few


def test_existing_clusters_get_priority():
    """이미 큰 군락일수록 더 많이 자란다 (선호적 부착)."""
    g = gen(9)
    g.generate(6000)
    sizes = sorted(g.counts.values(), reverse=True)
    assert sizes[0] > 3 * sizes[-1]


def test_early_blades_are_sprouts():
    g = gen(4)
    first = g.generate(8)
    assert sum(b.sprite.startswith("sprout") for b in first) >= 5


def test_resume_after_restart_matches_continuous(tmp_path):
    db = tmp_path / "m.db"
    store = MeadowStore(db)
    g = store.open_generator("2026-10-04", SPRITES, seed=99)
    grow_to(store, g, "2026-10-04", 700)
    store.close()

    store2 = MeadowStore(db)
    g2 = store2.open_generator("2026-10-04", SPRITES)
    assert g2.total == 700  # 저장된 풀잎 수에서 상태 복원
    saved = store2.load_blades("2026-10-04")
    assert len(saved) == 700
    grow_to(store2, g2, "2026-10-04", 1000)
    resumed = store2.load_blades("2026-10-04")

    ref = MeadowGenerator(99, plan_centers(99), SPRITES).generate(1000)
    assert resumed == ref  # 재실행 후 이어 자라도 처음부터 만든 것과 완전히 같다
    assert store2.blade_count("2026-10-04") == 1000
    ref_gen = MeadowGenerator(99, plan_centers(99), SPRITES)
    ref_gen.generate(1000)
    assert store2.opened_cluster_count("2026-10-04") == len(ref_gen.opened)


def test_each_day_has_its_own_meadow(tmp_path):
    store = MeadowStore(tmp_path / "m.db")
    a = store.open_generator("2026-10-04", SPRITES, seed=1)
    grow_to(store, a, "2026-10-04", 50)
    b = store.open_generator("2026-10-05", SPRITES, seed=2)
    grow_to(store, b, "2026-10-05", 20)
    assert store.days() == ["2026-10-04", "2026-10-05"]
    assert store.blade_count("2026-10-04") == 50  # 어제 풀밭은 그대로
    assert store.blade_count("2026-10-05") == 20
