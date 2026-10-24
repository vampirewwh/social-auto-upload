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

from conf import DATA_DIR

DB_PATH = Path(DATA_DIR) / "db" / "analytics.db"
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


def dashboard_summary(accounts: list[dict[str, Any]]) -> dict[str, Any]:
    """总览页聚合：每个账号的粉丝/播放/互动、数据新鲜度、待处理提醒。

    accounts 来自 accounts.list_accounts()，用来把"有 cookie 但没数据"的账号也算进覆盖率。
    """
    conn = _connect()
    try:
        # 每个账号最新快照
        snapshots: dict[str, dict[str, Any]] = {}
        for row in conn.execute(
            "SELECT platform, account, nickname, follower_count, total_favorited, "
            "aweme_count, captured_at FROM account_snapshot "
            "WHERE id IN (SELECT MAX(id) FROM account_snapshot GROUP BY platform, account)"
        ):
            item = dict(row)
            snapshots[f"{item['platform']}/{item['account']}"] = item

        # 作品互动汇总
        work_stats: dict[str, dict[str, int]] = {}
        for row in conn.execute(
            "SELECT platform, account, COUNT(*) AS works, "
            "COALESCE(SUM(play_count), 0) AS plays, "
            "COALESCE(SUM(digg_count), 0) AS digs, "
            "COALESCE(SUM(comment_count), 0) AS comments, "
            "COALESCE(SUM(share_count), 0) AS shares, "
            "COALESCE(SUM(collect_count), 0) AS collects "
            "FROM work GROUP BY platform, account"
        ):
            item = dict(row)
            work_stats[f"{item['platform']}/{item['account']}"] = item

        # 近 30 天发布量（按平台 + 日期）
        cutoff_30d = time.time() - 30 * 86400
        rhythm_rows = conn.execute(
            "SELECT platform, date(create_time, 'unixepoch', 'localtime') AS day, "
            "COUNT(*) AS count FROM work WHERE create_time >= ? "
            "GROUP BY platform, day ORDER BY day",
            [int(cutoff_30d)],
        ).fetchall()

        # 可用趋势天数
        days = conn.execute(
            "SELECT COUNT(DISTINCT date(captured_at, 'unixepoch', 'localtime')) "
            "FROM account_snapshot"
        ).fetchone()[0]
    finally:
        conn.close()

    now = time.time()
    platforms: dict[str, dict[str, Any]] = {}
    alerts: list[dict[str, Any]] = []
    totals = {"fans": 0, "plays": 0, "interactions": 0, "works": 0}
    synced = 0

    for account in accounts:
        platform = account["platform"]
        key = f"{platform}/{account['account']}"
        snapshot = snapshots.get(key)
        stats = work_stats.get(key) or {}
        label = account.get("label") or platform

        entry = platforms.setdefault(platform, {
            "platform": platform,
            "label": label,
            "accounts": 0,
            "fans": 0,
            "plays": 0,
            "interactions": 0,
            "works": 0,
            "last_sync": None,
            "stale_hours": None,
        })
        entry["accounts"] += 1

        if not snapshot:
            alerts.append({
                "level": "info",
                "platform": platform,
                "account": account["account"],
                "label": label,
                "text": "从未同步数据",
                "action": "同步数据",
                "last_success": None,
            })
            continue

        synced += 1
        fans = int(snapshot.get("follower_count") or 0)
        plays = int(stats.get("plays") or 0)
        interactions = sum(
            int(stats.get(k) or 0) for k in ("digs", "comments", "shares", "collects")
        )
        captured = float(snapshot.get("captured_at") or 0)

        entry["fans"] += fans
        entry["plays"] += plays
        entry["interactions"] += interactions
        entry["works"] += int(stats.get("works") or 0)
        if captured > (entry["last_sync"] or 0):
            entry["last_sync"] = captured

        totals["fans"] += fans
        totals["plays"] += plays
        totals["interactions"] += interactions
        totals["works"] += int(stats.get("works") or 0)

        stale_hours = round((now - captured) / 3600, 1) if captured else None
        if stale_hours is not None and stale_hours >= 24:
            alerts.append({
                "level": "warning",
                "platform": platform,
                "account": account["account"],
                "label": label,
                "text": f"数据已 {int(stale_hours)} 小时未更新",
                "action": "同步数据",
                "last_success": captured,
            })

    for entry in platforms.values():
        if entry["last_sync"]:
            entry["stale_hours"] = round((now - entry["last_sync"]) / 3600, 1)

    # 登录态问题优先级最高
    for account in accounts:
        if account.get("login_valid") is False:
            snapshot = snapshots.get(f"{account['platform']}/{account['account']}") or {}
            alerts.insert(0, {
                "level": "error",
                "platform": account["platform"],
                "account": account["account"],
                "label": account.get("label") or account["platform"],
                "text": "登录态已失效",
                "action": "重新登录",
                "last_success": snapshot.get("captured_at"),
            })

    rhythm: dict[str, dict[str, int]] = {}
    for row in rhythm_rows:
        rhythm.setdefault(row["platform"], {})[row["day"]] = row["count"]

    last_7d = sum(
        count for by_day in rhythm.values() for day, count in by_day.items()
        if day >= time.strftime("%Y-%m-%d", time.localtime(now - 7 * 86400))
    )

    return {
        "coverage": {"synced": synced, "total": len(accounts)},
        "totals": totals,
        "publish": {
            "last_30d": sum(c for by_day in rhythm.values() for c in by_day.values()),
            "last_7d": last_7d,
        },
        "platforms": sorted(platforms.values(), key=lambda x: -x["plays"]),
        "alerts": alerts[:5],
        "rhythm": rhythm,
        "trend_days_available": int(days or 0),
        "generated_at": now,
    }


def trend_series(days: int = 30) -> dict[str, Any]:
    """按天聚合粉丝与播放，供趋势折线图使用。

    粉丝取每天最后一条快照；播放没有历史快照，用作品发布时间近似累计。
    """
    conn = _connect()
    try:
        fan_rows = conn.execute(
            "SELECT date(captured_at, 'unixepoch', 'localtime') AS day, "
            "platform, follower_count FROM account_snapshot "
            "ORDER BY captured_at"
        ).fetchall()

        work_rows = conn.execute(
            "SELECT date(create_time, 'unixepoch', 'localtime') AS day, "
            "platform, COUNT(*) AS count, COALESCE(SUM(play_count), 0) AS plays "
            "FROM work WHERE create_time > 0 "
            "GROUP BY day, platform ORDER BY day"
        ).fetchall()
    finally:
        conn.close()

    # 每天每平台取最后一条粉丝快照
    fans: dict[str, dict[str, int]] = {}
    for row in fan_rows:
        fans.setdefault(row["day"], {})[row["platform"]] = int(row["follower_count"] or 0)

    plays: dict[str, dict[str, int]] = {}
    counts: dict[str, dict[str, int]] = {}
    for row in work_rows:
        plays.setdefault(row["day"], {})[row["platform"]] = int(row["plays"] or 0)
        counts.setdefault(row["day"], {})[row["platform"]] = int(row["count"] or 0)

    all_days = sorted(set(fans) | set(plays))
    all_platforms = sorted({p for by_platform in fans.values() for p in by_platform} |
                           {p for by_platform in plays.values() for p in by_platform})

    series = []
    for day in all_days[-days:]:
        series.append({
            "day": day,
            "fans": fans.get(day, {}),
            "plays": plays.get(day, {}),
            "published": counts.get(day, {}),
        })

    return {
        "days_available": len(all_days),
        "platforms": all_platforms,
        "series": series,
    }
