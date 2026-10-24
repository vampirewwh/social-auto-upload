"""账号数据分析的本地存储：快照、作品、采集记录与调度设置。

用独立的 db/analytics.db，避免和旧版 sau_backend 的 database.db 混在一起。
采集在子进程里写，Web 进程读，因此开启 WAL 并设置 busy timeout。
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from conf import BASE_DIR

DB_PATH = Path(BASE_DIR) / "db" / "analytics.db"
LAST_RUN_KEY = "analytics.last_schedule_date"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS account_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    account TEXT NOT NULL,
    captured_at REAL NOT NULL,
    nickname TEXT,
    douyin_id TEXT,
    avatar TEXT,
    follower_count INTEGER,
    following_count INTEGER,
    total_favorited INTEGER,
    aweme_count INTEGER,
    enterprise_verify TEXT
);
CREATE INDEX IF NOT EXISTS idx_snapshot
    ON account_snapshot(platform, account, captured_at DESC);

CREATE TABLE IF NOT EXISTS work (
    platform TEXT NOT NULL,
    account TEXT NOT NULL,
    aweme_id TEXT NOT NULL,
    desc TEXT,
    cover TEXT,
    create_time INTEGER,
    is_private INTEGER DEFAULT 0,
    in_reviewing INTEGER DEFAULT 0,
    play_count INTEGER DEFAULT 0,
    digg_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    share_count INTEGER DEFAULT 0,
    collect_count INTEGER DEFAULT 0,
    duration INTEGER DEFAULT 0,
    captured_at REAL NOT NULL,
    PRIMARY KEY (platform, account, aweme_id)
);
CREATE INDEX IF NOT EXISTS idx_work_time
    ON work(platform, account, create_time DESC);

CREATE TABLE IF NOT EXISTS collect_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    account TEXT NOT NULL,
    status TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual',
    work_count INTEGER DEFAULT 0,
    error TEXT,
    started_at REAL NOT NULL,
    finished_at REAL
);

CREATE TABLE IF NOT EXISTS setting (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

SNAPSHOT_FIELDS = (
    "nickname",
    "douyin_id",
    "avatar",
    "follower_count",
    "following_count",
    "total_favorited",
    "aweme_count",
    "enterprise_verify",
)

WORK_FIELDS = (
    "aweme_id",
    "desc",
    "cover",
    "create_time",
    "is_private",
    "in_reviewing",
    "play_count",
    "digg_count",
    "comment_count",
    "share_count",
    "collect_count",
    "duration",
)


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    # 先设超时再切 WAL：切 WAL 本身要拿写锁，否则并发时会立刻 SQLITE_BUSY
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def save_snapshot(
    platform: str, account: str, profile: dict[str, Any], captured_at: float | None = None
) -> int:
    captured_at = captured_at or time.time()
    columns = ", ".join(SNAPSHOT_FIELDS)
    placeholders = ", ".join("?" for _ in SNAPSHOT_FIELDS)
    values = [profile.get(field) for field in SNAPSHOT_FIELDS]
    conn = _connect()
    try:
        cursor = conn.execute(
            f"INSERT INTO account_snapshot (platform, account, captured_at, {columns}) "
            f"VALUES (?, ?, ?, {placeholders})",
            [platform, account, captured_at, *values],
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def recent_snapshots(platform: str, account: str, limit: int = 2) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM account_snapshot WHERE platform = ? AND account = ? "
            "ORDER BY captured_at DESC LIMIT ?",
            [platform, account, limit],
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_overview(platform: str, account: str) -> dict[str, Any]:
    snapshots = recent_snapshots(platform, account, limit=2)
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS total, "
            "COALESCE(SUM(play_count), 0) AS play, "
            "COALESCE(SUM(digg_count), 0) AS digg "
            "FROM work WHERE platform = ? AND account = ?",
            [platform, account],
        ).fetchone()
        last_run = conn.execute(
            "SELECT status, source, error, started_at, finished_at FROM collect_run "
            "WHERE platform = ? AND account = ? ORDER BY started_at DESC LIMIT 1",
            [platform, account],
        ).fetchone()
    finally:
        conn.close()

    return {
        "platform": platform,
        "account": account,
        "latest": snapshots[0] if snapshots else None,
        "previous": snapshots[1] if len(snapshots) > 1 else None,
        "works_total": row["total"] if row else 0,
        "works_play": row["play"] if row else 0,
        "works_digg": row["digg"] if row else 0,
        "last_run": dict(last_run) if last_run else None,
    }


def upsert_works(
    platform: str,
    account: str,
    works: list[dict[str, Any]],
    captured_at: float | None = None,
) -> int:
    if not works:
        return 0
    captured_at = captured_at or time.time()
    columns = ", ".join(WORK_FIELDS)
    placeholders = ", ".join("?" for _ in WORK_FIELDS)
    updates = ", ".join(
        f"{field} = excluded.{field}" for field in WORK_FIELDS if field != "aweme_id"
    )
    sql = (
        f"INSERT INTO work (platform, account, {columns}, captured_at) "
        f"VALUES (?, ?, {placeholders}, ?) "
        f"ON CONFLICT(platform, account, aweme_id) DO UPDATE SET "
        f"{updates}, captured_at = excluded.captured_at"
    )
    rows = [
        [platform, account, *[work.get(field) for field in WORK_FIELDS], captured_at]
        for work in works
    ]
    conn = _connect()
    try:
        conn.executemany(sql, rows)
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def list_works(
    platform: str,
    account: str,
    page: int = 1,
    size: int = 20,
    keyword: str = "",
) -> dict[str, Any]:
    where = "platform = ? AND account = ?"
    params: list[Any] = [platform, account]
    if keyword:
        where += " AND desc LIKE ?"
        params.append(f"%{keyword}%")

    conn = _connect()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM work WHERE {where}", params
        ).fetchone()[0]
        offset = max(0, (page - 1) * size)
        rows = conn.execute(
            f"SELECT * FROM work WHERE {where} "
            "ORDER BY create_time DESC LIMIT ? OFFSET ?",
            [*params, size, offset],
        ).fetchall()
    finally:
        conn.close()
    return {"items": [dict(row) for row in rows], "total": total, "page": page, "size": size}


def start_run(platform: str, account: str, source: str = "manual") -> int:
    conn = _connect()
    try:
        cursor = conn.execute(
            "INSERT INTO collect_run (platform, account, status, source, started_at) "
            "VALUES (?, ?, 'running', ?, ?)",
            [platform, account, source, time.time()],
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def finish_run(
    run_id: int, status: str, work_count: int = 0, error: str | None = None
) -> None:
    conn = _connect()
    try:
        conn.execute(
            "UPDATE collect_run SET status = ?, work_count = ?, error = ?, finished_at = ? "
            "WHERE id = ?",
            [status, work_count, error, time.time(), run_id],
        )
        conn.commit()
    finally:
        conn.close()


def get_setting(key: str, default: Any = None) -> Any:
    conn = _connect()
    try:
        row = conn.execute("SELECT value FROM setting WHERE key = ?", [key]).fetchone()
    finally:
        conn.close()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except (TypeError, ValueError):
        return default


def set_setting(key: str, value: Any) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO setting (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [key, json.dumps(value, ensure_ascii=False)],
        )
        conn.commit()
    finally:
        conn.close()


def claim_last_run(today: str) -> bool:
    """原子占位：仅当记录不是今天时才写入，返回是否抢到。"""
    conn = _connect()
    try:
        cursor = conn.execute(
            "INSERT INTO setting (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value "
            "WHERE setting.value != excluded.value",
            [LAST_RUN_KEY, json.dumps(today)],
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def clear_last_run() -> None:
    conn = _connect()
    try:
        conn.execute("DELETE FROM setting WHERE key = ?", [LAST_RUN_KEY])
        conn.commit()
    finally:
        conn.close()


def list_runs(platform: str, account: str, limit: int = 10) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM collect_run WHERE platform = ? AND account = ? "
            "ORDER BY started_at DESC LIMIT ?",
            [platform, account, limit],
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
