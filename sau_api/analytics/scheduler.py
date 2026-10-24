"""每日定时采集：在 Web 服务进程内起一个守护线程。

调度配置存在 SQLite 的 setting 表：
{"enabled": true, "time": "08:30", "accounts": [{"platform": "douyin", "account": "creator"}]}
accounts 为空表示采集所有已登录的抖音账号。
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from conf import BASE_DIR
from sau_api.analytics import store

CHECK_INTERVAL = 30
SCHEDULE_KEY = "analytics.schedule"
LAST_RUN_KEY = store.LAST_RUN_KEY
DEFAULT_PLATFORM = "douyin"

_run_lock = threading.Lock()
_thread: threading.Thread | None = None


def cookie_accounts(platform: str = DEFAULT_PLATFORM) -> list[str]:
    folder = Path(BASE_DIR) / "cookies"
    prefix = f"{platform}_"
    return sorted(path.stem[len(prefix):] for path in folder.glob(f"{prefix}*.json"))


def run_collect(platform: str, account: str, source: str = "schedule") -> int:
    cmd = [
        sys.executable,
        "-u",
        "-m",
        "sau_api.analytics.collector",
        "--platform",
        platform,
        "--account",
        account,
        "--source",
        source,
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    lines = (proc.stdout or "").strip().splitlines()
    if lines:
        print(f"[analytics] {lines[-1]}")
    if proc.returncode != 0:
        print(f"[analytics] 采集失败 {platform}/{account}: {(proc.stderr or '').strip()}")
    return proc.returncode


def _run_scheduled(cfg: dict[str, Any]) -> bool:
    with _run_lock:
        entries = cfg.get("accounts") or []
        if not entries:
            entries = [
                {"platform": DEFAULT_PLATFORM, "account": account}
                for account in cookie_accounts()
            ]
        failed = False
        for entry in entries:
            platform = entry.get("platform") or DEFAULT_PLATFORM
            account = entry.get("account")
            if account and run_collect(platform, account) != 0:
                failed = True
        return not failed


def _tick() -> None:
    cfg = store.get_setting(SCHEDULE_KEY, {}) or {}
    if not cfg.get("enabled") or not cfg.get("time"):
        return
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    if now.strftime("%H:%M") < str(cfg["time"]):
        return
    if store.get_setting(LAST_RUN_KEY) == today:
        return
    # 先占位再执行：多个实例同时检查时只有第一个能抢到当天，避免重复采集；
    # 全部成功后才写回日期，失败的话下个检查周期会重试。
    if not store.claim_last_run(today):
        return
    print(f"[analytics] 开始每日采集 {today} {cfg['time']}")
    if _run_scheduled(cfg):
        store.set_setting(LAST_RUN_KEY, today)
    else:
        store.clear_last_run()
        print("[analytics] 本次每日采集有账号失败，将在下个检查周期重试")


def _loop() -> None:
    while True:
        try:
            _tick()
        except Exception as exc:  # noqa: BLE001
            print(f"[analytics] 调度检查失败: {exc}")
        time.sleep(CHECK_INTERVAL)


def start() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    store.init_db()
    _thread = threading.Thread(target=_loop, name="analytics-scheduler", daemon=True)
    _thread.start()
