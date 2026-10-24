"""账号与素材：直接读写项目内的 cookies/ 与 videos/ 目录。

CLI 主线用 cookies/<platform>_<account>.json 作为账号载体，
所以 web 端只要扫描这个目录就能列出全部平台的全部账号。
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from conf import DATA_DIR

PROJECT_ROOT = Path(DATA_DIR)
COOKIE_DIR = PROJECT_ROOT / "cookies"
VIDEO_DIR = PROJECT_ROOT / "videos"
UPLOAD_DIR = PROJECT_ROOT / "videos"

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".flv", ".webm", ".m4v"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

PLATFORM_LABELS = {
    "douyin": "抖音",
    "kuaishou": "快手",
    "xiaohongshu": "小红书",
    "bilibili": "Bilibili",
    "tencent": "视频号",
    "alipay": "支付宝生活号",
    "weibo": "微博",
    "hupu": "虎扑",
    "facebook": "Facebook",
    "facebook-page": "Facebook Page",
    "instagram": "Instagram",
    "youtube": "YouTube",
    "baijiahao": "百家号",
    "dayu": "大鱼号",
    "xueqiu": "雪球",
    "zhihu": "知乎",
    "article": "本地文章工具",
}


def _platform_from_filename(stem: str) -> tuple[str, str]:
    """cookies 文件名形如 douyin_myaccount，平台名可能自带连字符。"""
    candidates = sorted(PLATFORM_LABELS, key=len, reverse=True)
    for platform in candidates:
        prefix = f"{platform}_"
        if stem.startswith(prefix):
            return platform, stem[len(prefix):]
    if "_" in stem:
        platform, account = stem.split("_", 1)
        return platform, account
    return "unknown", stem


# 从 localStorage 里找头像/昵称时按顺序尝试这些字段名
_AVATAR_KEYS = (
    "userAvatar", "avatarUrl", "avatar_url", "avatar",
    "headImg", "headImgUrl", "head_url", "profileImage", "image_url",
)
_NICKNAME_KEYS = ("nickname", "nickName", "userName", "name", "displayName")


def _extract_profile(data: dict[str, Any]) -> dict[str, str]:
    """从 storage_state 的 localStorage 里尽力提取头像和昵称。

    只挑 http 开头的头像地址和简短昵称，绝不带出手机号等敏感字段。
    """
    avatar = ""
    nickname = ""
    for origin in data.get("origins", []):
        for item in origin.get("localStorage", []):
            value = item.get("value", "")
            if not isinstance(value, str) or not value:
                continue
            try:
                obj = json.loads(value)
            except (TypeError, ValueError):
                continue
            if not isinstance(obj, dict):
                continue
            if not avatar:
                for key in _AVATAR_KEYS:
                    candidate = obj.get(key)
                    if isinstance(candidate, str) and candidate.startswith("http"):
                        avatar = candidate
                        break
            if not nickname:
                for key in _NICKNAME_KEYS:
                    candidate = obj.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        nickname = candidate.strip()
                        break
            if avatar and nickname:
                return {"avatar": avatar, "nickname": nickname}
    return {"avatar": avatar, "nickname": nickname}


def _profile_from_snapshot(platform: str, account: str) -> dict[str, Any]:
    """抖音等平台 cookie 里没有头像与经营数据，回退到数据分析采集的账号快照。"""
    db = PROJECT_ROOT / "db" / "analytics.db"
    empty = {
        "avatar": "",
        "nickname": "",
        "follower_count": None,
        "total_favorited": None,
        "aweme_count": None,
        "platform_id": "",
    }
    if not db.exists():
        return empty
    try:
        conn = sqlite3.connect(db)
        try:
            row = conn.execute(
                "SELECT avatar, nickname, follower_count, total_favorited, aweme_count, "
                "douyin_id "
                "FROM account_snapshot "
                "WHERE platform = ? AND account = ? "
                "ORDER BY captured_at DESC LIMIT 1",
                (platform, account),
            ).fetchone()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        return empty
    if not row:
        return empty
    return {
        "avatar": row[0] or "",
        "nickname": row[1] or "",
        "follower_count": row[2],
        "total_favorited": row[3],
        "aweme_count": row[4],
        "platform_id": row[5] or "",
    }


def _login_status_file() -> Path:
    return PROJECT_ROOT / "db" / "login_status.json"


def load_login_status() -> dict[str, dict[str, Any]]:
    """读取各账号最近一次登录态校验结果。key 为 platform/account。"""
    path = _login_status_file()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def save_login_status(platform: str, account: str, valid: bool, message: str = "") -> None:
    path = _login_status_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_login_status()
    data[f"{platform}/{account}"] = {
        "valid": bool(valid),
        "message": message,
        "checked_at": time.time(),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_accounts() -> list[dict[str, Any]]:
    COOKIE_DIR.mkdir(exist_ok=True)
    cached_status = load_login_status()
    accounts: list[dict[str, Any]] = []
    for path in sorted(COOKIE_DIR.glob("*.json")):
        platform, account = _platform_from_filename(path.stem)
        stat = path.stat()
        cookie_count = 0
        data: dict[str, Any] = {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            cookie_count = len(data.get("cookies", []))
        except Exception:  # noqa: BLE001
            cookie_count = -1

        profile = _extract_profile(data) if data else {}
        snapshot = _profile_from_snapshot(platform, account)
        # localStorage 优先，缺失时用数据分析快照兜底
        profile["avatar"] = profile.get("avatar") or snapshot.get("avatar", "")
        profile["nickname"] = profile.get("nickname") or snapshot.get("nickname", "")

        # 真实登录态来自最近一次校验；没有校验记录时不冒充“正常”
        cached = cached_status.get(f"{platform}/{account}") or {}
        if "valid" in cached:
            login_valid = bool(cached["valid"])
            login_checked_at = cached.get("checked_at")
        else:
            login_valid = None
            login_checked_at = None

        accounts.append({
            "platform": platform,
            "label": PLATFORM_LABELS.get(platform, platform),
            "account": account,
            "nickname": profile.get("nickname", ""),
            "avatar": profile.get("avatar", ""),
            "follower_count": snapshot.get("follower_count"),
            "total_favorited": snapshot.get("total_favorited"),
            "aweme_count": snapshot.get("aweme_count"),
            "platform_id": snapshot.get("platform_id", ""),
            "file": path.name,
            "size": stat.st_size,
            "updated_at": stat.st_mtime,
            "cookie_count": cookie_count,
            "login_valid": login_valid,
            "login_checked_at": login_checked_at,
        })
    return accounts


def delete_account(platform: str, account: str) -> bool:
    path = COOKIE_DIR / f"{platform}_{account}.json"
    if not path.exists():
        return False
    path.unlink()
    return True


def save_uploaded_cookie(platform: str, account: str, raw: bytes) -> dict[str, Any]:
    COOKIE_DIR.mkdir(exist_ok=True)
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"cookie 文件不是合法 JSON: {exc}") from exc
    if "cookies" not in data:
        raise ValueError("cookie 文件缺少 cookies 字段")
    path = COOKIE_DIR / f"{platform}_{account}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"file": path.name, "cookie_count": len(data.get("cookies", []))}


def _human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024:
            return f"{num:.1f}{unit}"
        num /= 1024
    return f"{num:.1f}TB"


def list_materials() -> list[dict[str, Any]]:
    VIDEO_DIR.mkdir(exist_ok=True)
    items: list[dict[str, Any]] = []
    for path in sorted(VIDEO_DIR.iterdir()):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext in VIDEO_EXT:
            kind = "video"
        elif ext in IMAGE_EXT:
            kind = "image"
        else:
            continue
        stat = path.stat()
        items.append({
            "name": path.name,
            "kind": kind,
            "size": stat.st_size,
            "size_text": _human_size(stat.st_size),
            "updated_at": stat.st_mtime,
            # CLI 的 --file 接受绝对路径，这里直接给出完整路径，避免前端猜目录
            "path": str(path),
            "rel_path": f"videos/{path.name}",
        })
    items.sort(key=lambda x: x["updated_at"], reverse=True)
    return items


def _safe_name(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    return name or f"upload_{int(time.time())}"


def save_material(filename: str, raw: bytes) -> dict[str, Any]:
    VIDEO_DIR.mkdir(exist_ok=True)
    safe = _safe_name(filename)
    target = VIDEO_DIR / safe
    if target.exists():
        stem, suffix = target.stem, target.suffix
        target = VIDEO_DIR / f"{stem}_{int(time.time())}{suffix}"
    target.write_bytes(raw)
    stat = target.stat()
    return {
        "name": target.name,
        "size": stat.st_size,
        "size_text": _human_size(stat.st_size),
        "path": str(target),
    }


def delete_material(name: str) -> bool:
    target = VIDEO_DIR / _safe_name(name)
    if not target.exists() or not target.is_file():
        return False
    target.unlink()
    return True
