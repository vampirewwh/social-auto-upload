"""任务执行器：把 sau CLI 作为独立进程运行，集中管理状态与日志。

用子进程而不是 in-process 调用，原因：
1. playwright 的 asyncio 事件循环与 Flask 线程模型冲突；
2. 每个任务崩溃不会带崩整个 web 服务；
3. 可以直接复用 CLI 的参数校验和退出码语义。
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Deque, Literal

from conf import BASE_DIR

PROJECT_ROOT = Path(BASE_DIR)
MAX_LOG_LINES = 4000

Status = Literal["pending", "running", "success", "failed", "cancelled"]


@dataclass
class Task:
    id: str
    platform: str
    action: str
    argv: list[str]
    status: Status = "pending"
    exit_code: int | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    logs: Deque[str] = field(default_factory=lambda: deque(maxlen=MAX_LOG_LINES))
    error: str | None = None
    module: str = "sau_cli"
    process: subprocess.Popen | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def append(self, line: str) -> None:
        with self._lock:
            self.logs.append(line)

    def snapshot(self, include_logs: bool = True, tail: int = 0) -> dict[str, Any]:
        with self._lock:
            lines = list(self.logs)
        if tail and len(lines) > tail:
            lines = lines[-tail:]
        data: dict[str, Any] = {
            "id": self.id,
            "platform": self.platform,
            "action": self.action,
            "argv": self.argv,
            "status": self.status,
            "exit_code": self.exit_code,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
        }
        if include_logs:
            data["logs"] = lines
        else:
            data["log_count"] = len(lines)
            data["last_line"] = lines[-1] if lines else None
        return data


class TaskManager:
    """全局任务表；线程安全，最多保留 MAX_TASKS 条历史。"""

    MAX_TASKS = 200

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()

    def create(
        self, platform: str, action: str, argv: list[str], module: str = "sau_cli"
    ) -> Task:
        task = Task(
            id=uuid.uuid4().hex[:12],
            platform=platform,
            action=action,
            argv=argv,
            module=module,
        )
        with self._lock:
            self._tasks[task.id] = task
            self._evict_locked()
        return task

    def _evict_locked(self) -> None:
        if len(self._tasks) <= self.MAX_TASKS:
            return
        finished = sorted(
            (t for t in self._tasks.values() if t.status in ("success", "failed", "cancelled")),
            key=lambda t: t.created_at,
        )
        for task in finished[: len(self._tasks) - self.MAX_TASKS]:
            self._tasks.pop(task.id, None)

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def list(self, limit: int = 50) -> list[Task]:
        with self._lock:
            tasks = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]

    def start(self, task: Task) -> None:
        thread = threading.Thread(target=self._run, args=(task,), daemon=True)
        thread.start()

    def _run(self, task: Task) -> None:
        task.status = "running"
        task.started_at = time.time()
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.setdefault("PYTHONUNBUFFERED", "1")

        cmd = [sys.executable, "-u", "-m", task.module, *task.argv]
        prefix = "sau" if task.module == "sau_cli" else task.module
        task.append(f"$ {prefix} {' '.join(task.argv)}")

        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            task.status = "failed"
            task.error = f"启动失败: {exc}"
            task.append(task.error)
            task.finished_at = time.time()
            return

        task.process = process
        assert process.stdout is not None
        for raw in process.stdout:
            task.append(raw.rstrip("\r\n"))

        exit_code = process.wait()
        task.exit_code = exit_code
        task.finished_at = time.time()
        if task.status == "cancelled":
            pass
        elif exit_code == 0:
            task.status = "success"
        else:
            task.status = "failed"
            task.error = f"进程退出码 {exit_code}"
        task.append(f"[完成] 退出码 {exit_code}")

    def clear_finished(self) -> int:
        """清掉已结束的任务记录，返回删除条数。"""
        with self._lock:
            done = [
                tid
                for tid, t in self._tasks.items()
                if t.status in ("success", "failed", "cancelled")
            ]
            for tid in done:
                self._tasks.pop(tid, None)
        return len(done)

    def cancel(self, task: Task) -> bool:
        process = task.process
        if not process or process.poll() is not None:
            return False
        task.status = "cancelled"
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except Exception as exc:  # noqa: BLE001
            task.append(f"取消失败: {exc}")
            return False
        return True


manager = TaskManager()
