"""网页登录：把各平台差异极大的 login_* 函数统一成一个 SSE 会话。

三种登录形态，全部靠 inspect 自省判断，不写死参数列表：
1. QR 型   —— login_* 接受 qrcode_callback，二维码直接推到前端显示；
2. 浏览器型 —— login_* 只接受 account_name/headless，弹出窗口由用户手动完成；
3. 会话型  —— dayu / xueqiu / zhihu 的 login_* 在 uploader.*.session 里，
              第一个参数是 account_file 而不是 account_name。
"""
from __future__ import annotations

import asyncio
import base64
import inspect
import json
import mimetypes
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable

# 形态一/二：sau_commands 里的 login_* 包装
COMMAND_LOGIN_FUNCS: dict[str, tuple[str, str]] = {
    "douyin": ("sau_commands.douyin", "login_douyin_account"),
    "alipay": ("sau_commands.alipay", "login_alipay_account"),
    "baijiahao": ("sau_commands.baijiahao", "login_baijiahao_account"),
    "weibo": ("sau_commands.weibo", "login_weibo_account"),
    "hupu": ("sau_commands.hupu", "login_hupu_account"),
    "kuaishou": ("sau_commands.kuaishou", "login_kuaishou_account"),
    "xiaohongshu": ("sau_commands.xiaohongshu", "login_xiaohongshu_account"),
    "bilibili": ("sau_commands.bilibili", "login_bilibili_account"),
    "tencent": ("sau_commands.tencent", "login_tencent_account"),
    "youtube": ("sau_commands.youtube", "login_youtube_account"),
    "facebook": ("sau_commands.facebook", "login_facebook_account"),
    "facebook-page": ("sau_commands.facebook_page", "login_meta_account"),
    "instagram": ("sau_commands.instagram", "login_instagram_account"),
}

# 形态三：uploader.*.session 里第一个参数就是 account_file
SESSION_LOGIN_FUNCS: dict[str, tuple[str, str]] = {
    "dayu": ("uploader.dayu_uploader.session", "login_dayu_account"),
    "xueqiu": ("uploader.xueqiu_uploader.session", "login_xueqiu_account"),
    "zhihu": ("uploader.zhihu_uploader.session", "login_zhihu_account"),
}

LOGIN_TIMEOUT = 600


def _resolve(platform: str) -> tuple[str, Callable[..., Any]]:
    """返回 (形态, 登录函数)。形态是 command / session。"""
    if platform in COMMAND_LOGIN_FUNCS:
        module_name, func_name = COMMAND_LOGIN_FUNCS[platform]
        kind = "command"
    elif platform in SESSION_LOGIN_FUNCS:
        module_name, func_name = SESSION_LOGIN_FUNCS[platform]
        kind = "session"
    else:
        raise ValueError(f"平台 {platform} 不支持网页登录")
    module = __import__(module_name, fromlist=[func_name])
    return kind, getattr(module, func_name)


def _supports_qrcode(platform: str) -> bool:
    try:
        _, func = _resolve(platform)
    except Exception:  # noqa: BLE001
        return False
    return "qrcode_callback" in inspect.signature(func).parameters


def all_login_platforms() -> list[str]:
    return list(COMMAND_LOGIN_FUNCS) + list(SESSION_LOGIN_FUNCS)


def qr_ready_platforms() -> list[str]:
    return [p for p in all_login_platforms() if _supports_qrcode(p)]


def browser_only_platforms() -> list[str]:
    return [p for p in all_login_platforms() if not _supports_qrcode(p)]


def account_file_of(platform: str, account: str) -> Path:
    from conf import BASE_DIR

    path = Path(BASE_DIR) / "cookies" / f"{platform}_{account}.json"
    path.parent.mkdir(exist_ok=True)
    return path


def build_login_kwargs(
    platform: str, account: str, headless: bool, qrcode_callback
) -> dict[str, Any]:
    """按真实签名拼关键字参数，多余的一律不传，避免 TypeError。"""
    kind, func = _resolve(platform)
    params = inspect.signature(func).parameters
    kwargs: dict[str, Any] = {}

    if kind == "session":
        # login_xueqiu_account(account_file, expected_name=None, timeout=600)
        kwargs["account_file"] = str(account_file_of(platform, account))
        if "timeout" in params:
            kwargs["timeout"] = LOGIN_TIMEOUT
        return kwargs

    if "account_name" in params:
        kwargs["account_name"] = account
    if "platform" in params:
        # facebook-page 的 login_meta_account(platform, account_name, ...)
        kwargs["platform"] = platform
    if "headless" in params:
        kwargs["headless"] = headless
    if "qrcode_callback" in params:
        kwargs["qrcode_callback"] = qrcode_callback
    return kwargs


def _normalize_qrcode(payload: dict) -> dict[str, str]:
    """多数平台只落盘二维码 png，这里补一个 data URL 让前端能直接显示。"""
    image_path = str(payload.get("image_path") or "")
    data_url = str(payload.get("image_data_url") or "")
    if not data_url and image_path:
        try:
            raw = Path(image_path).read_bytes()
            mime = mimetypes.guess_type(image_path)[0] or "image/png"
            data_url = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
        except OSError:
            data_url = ""
    return {"image_data_url": data_url, "image_path": image_path}


@dataclass
class LoginSession:
    id: str
    platform: str
    account: str
    queue: Queue = field(default_factory=Queue)
    status: str = "starting"
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    message: str = ""

    def emit(self, event: str, data: Any = None) -> None:
        self.queue.put({"event": event, "data": data, "ts": time.time()})

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "platform": self.platform,
            "account": self.account,
            "status": self.status,
            "message": self.message,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


class LoginManager:
    def __init__(self) -> None:
        self._sessions: dict[str, LoginSession] = {}
        self._lock = threading.Lock()

    def start(self, platform: str, account: str, headless: bool = True) -> LoginSession:
        if platform not in COMMAND_LOGIN_FUNCS and platform not in SESSION_LOGIN_FUNCS:
            raise ValueError(f"平台 {platform} 不支持网页登录")
        if not account.strip():
            raise ValueError("账号名称不能为空")
        session = LoginSession(
            id=uuid.uuid4().hex[:12], platform=platform, account=account.strip()
        )
        with self._lock:
            self._sessions[session.id] = session
        threading.Thread(target=self._run, args=(session, headless), daemon=True).start()
        return session

    def get(self, session_id: str) -> LoginSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            sessions = list(self._sessions.values())
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return [s.snapshot() for s in sessions]

    def _run(self, session: LoginSession, headless: bool) -> None:
        wants_qr = _supports_qrcode(session.platform)

        def qrcode_callback(payload: dict) -> None:
            session.emit("qrcode", _normalize_qrcode(payload))

        async def runner() -> Any:
            _, func = _resolve(session.platform)
            kwargs = build_login_kwargs(
                session.platform, session.account, headless, qrcode_callback
            )
            if wants_qr:
                session.emit(
                    "status",
                    {"status": "waiting", "message": "正在启动浏览器并获取登录二维码..."},
                )
            else:
                session.emit(
                    "status",
                    {"status": "waiting", "message": "请在弹出的浏览器窗口中完成登录"},
                )
            return await func(**kwargs)

        try:
            result = asyncio.run(asyncio.wait_for(runner(), timeout=LOGIN_TIMEOUT))
        except asyncio.TimeoutError:
            session.status = "timeout"
            session.message = f"登录超时（{LOGIN_TIMEOUT} 秒）"
            session.finished_at = time.time()
            session.emit("result", {"success": False, "message": session.message})
            return
        except Exception as exc:  # noqa: BLE001
            session.status = "failed"
            session.message = f"{type(exc).__name__}: {exc}"
            session.finished_at = time.time()
            session.emit("result", {"success": False, "message": session.message})
            return

        if isinstance(result, dict):
            success = bool(result.get("success"))
            session.message = str(
                result.get("message") or ("登录成功" if success else "登录失败")
            )
        else:
            success = bool(result)
            session.message = "登录成功" if success else "登录失败"
        session.status = "success" if success else "failed"
        session.finished_at = time.time()
        session.emit("result", {"success": success, "message": session.message})

    def stream(self, session: LoginSession):
        """生成 SSE 事件流。"""
        deadline = time.time() + LOGIN_TIMEOUT + 60
        while time.time() < deadline:
            try:
                item = session.queue.get(timeout=1.0)
            except Empty:
                if session.status in ("success", "failed", "timeout"):
                    break
                yield ": ping\n\n"
                continue
            event = item["event"]
            payload = item["data"]
            yield f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if event == "result":
                break


login_manager = LoginManager()
