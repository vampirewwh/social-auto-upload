"""账号与素材：直接读写项目内的 cookies/ 与 videos/ 目录。

CLI 主线用 cookies/<platform>_<account>.json 作为账号载体，
所以 web 端只要扫描这个目录就能列出全部平台的全部账号。
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from conf import BASE_DIR

PROJECT_ROOT = Path(BASE_DIR)
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


def list_accounts() -> list[dict[str, Any]]:
    COOKIE_DIR.mkdir(exist_ok=True)
    accounts: list[dict[str, Any]] = []
    for path in sorted(COOKIE_DIR.glob("*.json")):
        platform, account = _platform_from_filename(path.stem)
        stat = path.stat()
        cookie_count = 0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            cookie_count = len(data.get("cookies", []))
        except Exception:  # noqa: BLE001
            cookie_count = -1
        accounts.append({
            "platform": platform,
            "label": PLATFORM_LABELS.get(platform, platform),
            "account": account,
            "file": path.name,
            "size": stat.st_size,
            "updated_at": stat.st_mtime,
            "cookie_count": cookie_count,
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
