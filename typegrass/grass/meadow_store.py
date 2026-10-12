"""풀밭 저장소 (SQLite). 하루 = 풀밭 하나.

meadows : 날짜별 seed
clusters: 날짜별 군락 중심점 계획 (미리 정해 둔 전부) + 열린 순서
blades  : 풀잎 하나하나의 위치/모양 (타자 1회 = 1행)
"""
from __future__ import annotations

import random
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from .layout import (
    LAYOUT_VERSION,
    MAX_CLUSTERS,
    Blade,
    ClusterPlan,
    MeadowGenerator,
    plan_centers,
)


class MeadowStore:
    def __init__(self, path: str | Path):
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS meadows(
              day TEXT PRIMARY KEY, seed INTEGER NOT NULL,
              layout_version INTEGER NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS clusters(
              day TEXT NOT NULL, id INTEGER NOT NULL,
              cx REAL NOT NULL, cy REAL NOT NULL, sigma REAL NOT NULL,
              lean REAL NOT NULL, hue REAL NOT NULL,
              opened_at INTEGER,            -- 몇 번째 타자에서 열렸는지 (NULL=아직 안 열림)
              PRIMARY KEY(day, id));
            CREATE TABLE IF NOT EXISTS blades(
              day TEXT NOT NULL, idx INTEGER NOT NULL, cluster INTEGER NOT NULL,
              x REAL NOT NULL, y REAL NOT NULL, sprite TEXT NOT NULL,
              scale REAL NOT NULL, stretch REAL NOT NULL, rot REAL NOT NULL,
              flip INTEGER NOT NULL, tint INTEGER NOT NULL,
              PRIMARY KEY(day, idx)) WITHOUT ROWID;
            """
        )
        self._db.commit()

    # ---------------------------------------------------------- 조회
    def days(self) -> list[str]:
        with self._lock:
            return [r[0] for r in self._db.execute("SELECT day FROM meadows ORDER BY day")]

    def has_meadow(self, day: str) -> bool:
        with self._lock:
            return self._db.execute("SELECT 1 FROM meadows WHERE day=?", (day,)).fetchone() is not None

    def blade_count(self, day: str) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM blades WHERE day=?", (day,)).fetchone()[0]

    def load_blades(self, day: str, start: int = 0) -> list[Blade]:
        with self._lock:
            rows = self._db.execute(
                "SELECT idx,cluster,x,y,sprite,scale,stretch,rot,flip,tint FROM blades"
                " WHERE day=? AND idx>=? ORDER BY idx",
                (day, start),
            ).fetchall()
        return [Blade(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], bool(r[8]), r[9]) for r in rows]

    def opened_cluster_count(self, day: str) -> int:
        with self._lock:
            return self._db.execute(
                "SELECT COUNT(*) FROM clusters WHERE day=? AND opened_at IS NOT NULL", (day,)
            ).fetchone()[0]

    # ---------------------------------------------------------- 생성기
    def open_generator(
        self, day: str, sprites_by_cat: dict[str, list[str]], seed: int | None = None
    ) -> MeadowGenerator:
        """그날의 풀밭 생성기를 만든다. 없으면 새로 만들고, 있으면 저장된 상태를 복원한다."""
        with self._lock:
            row = self._db.execute("SELECT seed FROM meadows WHERE day=?", (day,)).fetchone()
            if row is None:
                seed = seed if seed is not None else random.SystemRandom().randrange(1, 2**31)
                plans = plan_centers(seed, MAX_CLUSTERS)
                self._db.execute(
                    "INSERT INTO meadows VALUES (?,?,?,?)",
                    (day, seed, LAYOUT_VERSION, datetime.now().isoformat(timespec="seconds")),
                )
                self._db.executemany(
                    "INSERT INTO clusters(day,id,cx,cy,sigma,lean,hue,opened_at) VALUES (?,?,?,?,?,?,?,NULL)",
                    [(day, p.id, p.cx, p.cy, p.sigma, p.lean, p.hue) for p in plans],
                )
                self._db.commit()
                return MeadowGenerator(seed, plans, sprites_by_cat)

            seed = row[0]
            plans = [
                ClusterPlan(r[0], r[1], r[2], r[3], r[4], r[5])
                for r in self._db.execute(
                    "SELECT id,cx,cy,sigma,lean,hue FROM clusters WHERE day=? ORDER BY id", (day,)
                )
            ]
            opened = [
                r[0]
                for r in self._db.execute(
                    "SELECT id FROM clusters WHERE day=? AND opened_at IS NOT NULL ORDER BY opened_at, id",
                    (day,),
                )
            ]
            counts = dict(
                self._db.execute(
                    "SELECT cluster, COUNT(*) FROM blades WHERE day=? GROUP BY cluster", (day,)
                ).fetchall()
            )
        return MeadowGenerator(seed, plans, sprites_by_cat, counts=counts, opened=opened)

    def append(self, day: str, blades: list[Blade], newly_opened: list[tuple[int, int]]) -> None:
        """풀잎들을 저장한다. newly_opened = [(군락 id, 열린 시점의 타자 번호)]"""
        with self._lock:
            self._db.executemany(
                "INSERT INTO blades VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [
                    (day, b.idx, b.cluster, b.x, b.y, b.sprite, b.scale, b.stretch, b.rot, int(b.flip), b.tint)
                    for b in blades
                ],
            )
            for cid, at in newly_opened:
                self._db.execute(
                    "UPDATE clusters SET opened_at=? WHERE day=? AND id=?", (at, day, cid)
                )
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()


def grow_to(
    store: MeadowStore, gen: MeadowGenerator, day: str, target: int, chunk: int = 2000
) -> list[Blade]:
    """풀잎 수가 target 이 될 때까지 생성해 저장하고, 새로 만든 풀잎들을 돌려준다."""
    out: list[Blade] = []
    while gen.total < target:
        batch: list[Blade] = []
        opened: list[tuple[int, int]] = []
        for _ in range(min(chunk, target - gen.total)):
            b = gen.next_blade()
            batch.append(b)
            if gen.last_opened is not None:
                opened.append((gen.last_opened, b.idx))
        store.append(day, batch, opened)
        out.extend(batch)
    return out
