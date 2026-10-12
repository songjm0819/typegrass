"""군락 배치 알고리즘 (화면/그래픽과 무관한 순수 계산 모듈).

핵심 규칙
  * 타자 1회 = 풀잎 정확히 1개 (generate_blade 한 번 호출 = 풀잎 1개)
  * 하루 시작 시 seed 로 '군락 중심점 후보'를 미리 전부 정해 둔다(plan_centers).
    - Mitchell best-candidate 방식: 새 중심점은 기존 점들과 가장 먼 곳에 놓여
      화면 곳곳에 고르게 흩어지되, 규칙적인 격자처럼 보이지는 않는다.
  * 활성 군락 수 K(n) 은 누적 타수 n 에 따라 늘어난다 (3 + sqrt(n)/3.5).
  * 풀잎은 기존 활성 군락 중에서 (풀잎 수+1)^0.85 에 비례해 선택된다
    -> 이미 큰 군락이 더 잘 자란다(선호적 부착). K 가 늘어날 때만 새 군락이 열린다.
  * 군락 안 위치는 가우시안. 군락이 커질수록 반경이 넓어지고, 막 열린 군락의 첫
    풀잎들은 반경이 넓어 '드문드문 새싹'처럼 흩어진다.
  * 풀잎마다 난수는 Random(seed, idx) 로 독립 생성 -> 재시작해도 이어서 같은 결과.

좌표계: x, y 모두 0~1 로 정규화(왼쪽 위가 0,0). 화면 크기가 달라도 같은 풀밭을 그린다.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

LAYOUT_VERSION = 1

MAX_CLUSTERS = 64
# 군락 반경 계산용 기준 화면(16:9). 픽셀이 아니라 '비율'을 정하기 위한 값.
WORLD_W, WORLD_H = 1600.0, 900.0
SQUASH_Y = 0.6  # 세로로 납작한 타원 (바닥에 퍼진 느낌)

TINT_HUE_STEPS = 7  # 어두운 청록 -> 밝은 연두
TINT_VAL_STEPS = 3  # 밝기 3단계
TINT_COUNT = TINT_HUE_STEPS * TINT_VAL_STEPS

SPROUT, GRASS, WEED = "sprout", "grass", "weed"


@dataclass
class ClusterPlan:
    id: int
    cx: float
    cy: float
    sigma: float  # 기본 반경(기준 화면 픽셀 단위)
    lean: float  # 이 군락 풀잎들이 공통으로 기우는 각도(도)
    hue: float  # 이 군락의 색조 치우침 (-1 ~ 1)


@dataclass
class Blade:
    idx: int  # 그날의 몇 번째 타자인지 (0부터)
    cluster: int
    x: float
    y: float
    sprite: str  # 예: "grass_03"
    scale: float
    stretch: float  # 세로 방향 추가 배율
    rot: float  # 도 단위, 풀뿌리를 기준으로 회전
    flip: bool
    tint: int  # 0 ~ TINT_COUNT-1


# ---------------------------------------------------------------- 군락 중심점

def plan_centers(seed: int, n: int = MAX_CLUSTERS) -> list[ClusterPlan]:
    rng = random.Random(f"centers:{seed}")
    pts: list[tuple[float, float]] = []

    def dist(a, b):
        dx = (a[0] - b[0]) * WORLD_W
        dy = (a[1] - b[1]) * WORLD_H / SQUASH_Y
        return math.hypot(dx, dy)

    for i in range(n):
        best, best_d = None, -1.0
        tries = 1 if i == 0 else 14
        for _ in range(tries):
            cand = (rng.uniform(0.04, 0.96), rng.uniform(0.06, 0.96))
            d = min((dist(cand, p) for p in pts), default=1e9)
            if d > best_d:
                best, best_d = cand, d
        pts.append(best)

    plans = []
    for i, (cx, cy) in enumerate(pts):
        plans.append(
            ClusterPlan(
                id=i,
                cx=cx,
                cy=cy,
                sigma=rng.uniform(34.0, 58.0),
                lean=rng.uniform(-7.0, 7.0),
                hue=rng.uniform(-1.0, 1.0),
            )
        )
    return plans


def target_active(n: int, max_clusters: int = MAX_CLUSTERS) -> int:
    """누적 타수 n 일 때 열려 있어야 할 군락 수."""
    return min(max_clusters, 3 + int(math.sqrt(max(0, n)) / 3.5))


# -------------------------------------------------------------- 풀잎 생성기

class MeadowGenerator:
    """한 날짜의 풀밭 상태(군락들)를 들고 풀잎을 하나씩 만들어 낸다.

    counts: 군락별 현재 풀잎 수 (저장된 풀잎에서 복원 가능)
    opened: 이미 열린 군락 id 목록 (열린 순서)
    """

    def __init__(
        self,
        seed: int,
        plans: list[ClusterPlan],
        sprites_by_cat: dict[str, list[str]],
        counts: dict[int, int] | None = None,
        opened: list[int] | None = None,
    ):
        self.seed = seed
        self.plans = plans
        self.sprites = sprites_by_cat
        self.counts: dict[int, int] = dict(counts or {})
        self.opened: list[int] = list(opened or [])
        for cid in self.opened:
            self.counts.setdefault(cid, 0)
        self.total = sum(self.counts.values())

    # 새로 열린 군락 id 를 알아야 DB 에 기록할 수 있어 별도로 노출한다.
    last_opened: int | None = None

    def _pick_cluster(self, idx: int, rng: random.Random) -> int:
        self.last_opened = None
        want = target_active(idx, len(self.plans))
        if len(self.opened) < want:
            cid = len(self.opened)  # 미리 정해 둔 다음 중심점
            self.opened.append(cid)
            self.counts[cid] = 0
            self.last_opened = cid
            return cid
        weights = [(self.counts[c] + 1.0) ** 0.85 for c in self.opened]
        r = rng.random() * sum(weights)
        acc = 0.0
        for c, w in zip(self.opened, weights):
            acc += w
            if r <= acc:
                return c
        return self.opened[-1]

    def next_blade(self) -> Blade:
        idx = self.total
        rng = random.Random(f"{self.seed}:{idx}")
        cid = self._pick_cluster(idx, rng)
        plan = self.plans[cid]
        m = self.counts[cid]  # 이 군락의 기존 풀잎 수 = 군락의 나이

        # --- 위치: 군락이 클수록 넓어지고, 갓 열린 군락의 첫 풀잎은 흩어진다
        grow = 1.0 + 0.6 * math.sqrt(m / 120.0)
        youth = 1.0 + 1.4 * max(0.0, 1.0 - m / 10.0)
        sigma = plan.sigma * grow * youth
        x = y = 0.0
        for _ in range(4):
            x = plan.cx + rng.gauss(0, sigma) / WORLD_W
            y = plan.cy + rng.gauss(0, sigma * SQUASH_Y) / WORLD_H
            if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                break
        x = min(0.999, max(0.001, x))
        y = min(0.999, max(0.001, y))

        # --- 종류: 어린 군락은 새싹, 자라면 풀 위주 + 가끔 잡초/새싹
        r = rng.random()
        if m < 6:
            cat = SPROUT if r < 0.85 else GRASS
        elif m < 25:
            cat = SPROUT if r < 0.30 else (WEED if r < 0.38 else GRASS)
        else:
            cat = SPROUT if r < 0.05 else (WEED if r < 0.12 else GRASS)
        pool = self.sprites.get(cat) or self.sprites.get(GRASS) or next(iter(self.sprites.values()))
        sprite = pool[rng.randrange(len(pool))]

        # --- 크기: 아래쪽(가까운 쪽)일수록 크게 + 로그정규 변동
        depth = 0.75 + 0.5 * y
        base = {SPROUT: 0.50, GRASS: 0.42, WEED: 0.34}.get(cat, 0.42)
        scale = base * depth * math.exp(rng.gauss(0, 0.22))
        stretch = rng.uniform(0.85, 1.30)

        # --- 기울기: 군락 공통 기울기 + 개별 흔들림
        rot = plan.lean + rng.gauss(0, 8.0)
        flip = rng.random() < 0.5

        # --- 색조: 군락 색조 치우침 + 개별 노이즈, 밝기 3단계
        hue_pos = (plan.hue * 0.35 + 0.5) * (TINT_HUE_STEPS - 1) + rng.gauss(0, 1.1)
        hue_i = int(round(min(TINT_HUE_STEPS - 1, max(0, hue_pos))))
        val_i = rng.choices([0, 1, 2], weights=[0.25, 0.5, 0.25])[0]
        tint = val_i * TINT_HUE_STEPS + hue_i

        blade = Blade(idx, cid, x, y, sprite, scale, stretch, rot, flip, tint)
        self.counts[cid] = m + 1
        self.total += 1
        return blade

    def generate(self, n: int) -> list[Blade]:
        return [self.next_blade() for _ in range(n)]


def tint_factors(tint: int) -> tuple[float, float, float]:
    """tint 번호 -> (R, G, B) 곱셈 계수. 렌더러/에셋 로더가 공유한다."""
    hue_i = tint % TINT_HUE_STEPS
    val_i = tint // TINT_HUE_STEPS
    u = hue_i / (TINT_HUE_STEPS - 1) * 2.0 - 1.0  # -1(청록) ~ +1(연두/노랑)
    v = (val_i - 1) * 0.16  # -0.16, 0, +0.16
    return (
        max(0.0, (1.0 + 0.28 * u) * (1.0 + v)),
        max(0.0, (1.0 + 0.07 * u) * (1.0 + v)),
        max(0.0, (1.0 - 0.28 * u) * (1.0 + v)),
    )
