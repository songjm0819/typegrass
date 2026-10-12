"""날짜별 타수 저장소 (SQLite, 표준 라이브러리만 사용).

저장하는 것은 (날짜, 횟수)뿐이다. 어떤 키를 눌렀는지는 저장하지 않는다.
"""
from __future__ import annotations

import csv
import sqlite3
import threading
from datetime import datetime
from pathlib import Path


class CountStore:
    def __init__(self, path: str | Path):
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS daily_counts ("
            " day TEXT PRIMARY KEY,"
            " count INTEGER NOT NULL,"
            " updated_at TEXT NOT NULL)"
        )
        self._db.commit()

    def get(self, day: str) -> int:
        with self._lock:
            row = self._db.execute(
                "SELECT count FROM daily_counts WHERE day = ?", (day,)
            ).fetchone()
        return int(row[0]) if row else 0

    def set(self, day: str, count: int) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            self._db.execute(
                "INSERT INTO daily_counts(day, count, updated_at) VALUES (?, ?, ?)"
                " ON CONFLICT(day) DO UPDATE SET count = excluded.count,"
                " updated_at = excluded.updated_at",
                (day, int(count), now),
            )
            self._db.commit()

    def history(self, limit: int = 30) -> list[tuple[str, int]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT day, count FROM daily_counts ORDER BY day DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [(r[0], int(r[1])) for r in rows]

    def export_csv(self, path: str | Path) -> int:
        with self._lock:
            rows = self._db.execute(
                "SELECT day, count FROM daily_counts ORDER BY day"
            ).fetchall()
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Date", "Count"])
            w.writerows(rows)
        return len(rows)

    def close(self) -> None:
        with self._lock:
            self._db.close()
