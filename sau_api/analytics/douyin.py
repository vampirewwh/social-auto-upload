"""抖音创作者中心数据采集。

不逆向构造带签名的请求，而是打开作品管理页，让页面自己发请求，
再拦截这些 JSON 响应。这样平台换签名算法时不需要跟着改，
只需要适配响应字段。
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from patchright.async_api import async_playwright

from conf import BASE_DIR
from utils.base_social_media import set_init_script

MANAGE_URL = "https://creator.douyin.com/creator-micro/content/manage"
FIRST_RESPONSE_TIMEOUT = 40
NEXT_PAGE_TIMEOUT = 12
MAX_IDLE_SCROLLS = 3
SCROLL_PIXELS = 4000


def _cookie_file(account: str) -> Path:
    return Path(BASE_DIR) / "cookies" / f"douyin_{account}.json"


def _first_url(data: dict[str, Any] | None) -> str:
    urls = (data or {}).get("url_list") or []
    return urls[0] if urls else ""


def _parse_creator_info(data: dict[str, Any]) -> dict[str, Any]:
    info = data.get("douyin_user_verify_info") or {}
    return {
        "nickname": info.get("nick_name"),
        "douyin_id": info.get("douyin_unique_id"),
        "avatar": info.get("avatar_url"),
        "follower_count": info.get("follower_count"),
        "following_count": info.get("following_count"),
        "total_favorited": info.get("total_favorited"),
    }


def _parse_media_info(data: dict[str, Any]) -> dict[str, Any]:
    user = data.get("user") or {}
    return {
        "nickname": user.get("nickname"),
        "avatar": _first_url(user.get("avatar_larger")) or _first_url(user.get("avatar_medium")),
        "follower_count": user.get("follower_count"),
        "following_count": user.get("following_count"),
        "total_favorited": user.get("total_favorited"),
        "aweme_count": user.get("aweme_count"),
        "enterprise_verify": user.get("enterprise_verify_reason"),
    }


def _parse_work(item: dict[str, Any]) -> dict[str, Any] | None:
    aweme_id = str(item.get("aweme_id") or item.get("item_id") or "")
    if not aweme_id:
        return None
    stat = item.get("statistics") or {}
    status = item.get("status") or {}
    video = item.get("video") or {}
    return {
        "aweme_id": aweme_id,
        "desc": item.get("desc") or item.get("item_title") or "",
        "cover": _first_url(item.get("Cover")) or _first_url(video.get("cover")),
        "create_time": item.get("create_time") or 0,
        "is_private": 1 if status.get("is_private") else 0,
        "in_reviewing": 1 if status.get("in_reviewing") else 0,
        "play_count": stat.get("play_count") or 0,
        "digg_count": stat.get("digg_count") or 0,
        "comment_count": stat.get("comment_count") or 0,
        "share_count": stat.get("share_count") or 0,
        "collect_count": stat.get("collect_count") or 0,
        "duration": item.get("duration") or 0,
    }


async def _wait_page(queue: asyncio.Queue, timeout: float) -> dict[str, Any] | None:
    try:
        return await asyncio.wait_for(queue.get(), timeout=timeout)
    except asyncio.TimeoutError:
        return None


async def _classify_empty(page) -> None:
    text = ""
    try:
        text = await page.evaluate("document.body ? document.body.innerText : ''")
    except Exception:  # noqa: BLE001
        pass
    if "扫码登录" in text or "手机号登录" in text or "/login" in page.url:
        raise RuntimeError("抖音登录态已失效，请先在账号管理中重新登录")
    raise RuntimeError("未能读取到作品列表，创作者中心页面结构可能已变化")


async def collect_douyin(
    account: str,
    headless: bool = True,
    max_works: int = 500,
    max_scrolls: int = 30,
) -> dict[str, Any]:
    cookie = _cookie_file(account)
    if not cookie.exists():
        raise FileNotFoundError(f"账号文件不存在: cookies/{cookie.name}")

    profile: dict[str, Any] = {}
    works: dict[str, dict[str, Any]] = {}
    pages: asyncio.Queue = asyncio.Queue()
    pending: set[asyncio.Task] = set()

    def merge(extra: dict[str, Any], prefer: bool = False) -> None:
        for key, value in extra.items():
            if value in (None, ""):
                continue
            if prefer or not profile.get(key):
                profile[key] = value

    async def handle(response) -> None:
        url = response.url
        if "creator.douyin.com" not in url:
            return
        try:
            if "aweme/v1/creator/user/info" in url:
                merge(_parse_creator_info(await response.json()), prefer=True)
            elif "web/api/media/user/info" in url:
                merge(_parse_media_info(await response.json()))
            elif "pc/work_list" in url:
                data = await response.json()
                for item in data.get("aweme_list") or []:
                    work = _parse_work(item)
                    if work:
                        works[work["aweme_id"]] = work
                await pages.put({
                    "has_more": bool(data.get("has_more")),
                    "total": int(data.get("total") or 0),
                })
        except Exception:  # noqa: BLE001
            return

    def on_response(response) -> None:
        task = asyncio.create_task(handle(response))
        pending.add(task)
        task.add_done_callback(pending.discard)

    total = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, channel="chromium")
        context = await browser.new_context(storage_state=str(cookie))
        await set_init_script(context)
        page = await context.new_page()
        page.on("response", on_response)
        try:
            await page.goto(MANAGE_URL, wait_until="domcontentloaded", timeout=60000)
            first = await _wait_page(pages, FIRST_RESPONSE_TIMEOUT)
            if first is None:
                await _classify_empty(page)

            has_more = first["has_more"]
            total = first["total"]
            idle = 0
            await page.mouse.move(640, 400)
            for _ in range(max_scrolls):
                if not has_more or len(works) >= max_works:
                    break
                if total and len(works) >= total:
                    break
                await page.mouse.wheel(0, SCROLL_PIXELS)
                nxt = await _wait_page(pages, NEXT_PAGE_TIMEOUT)
                if nxt is None:
                    idle += 1
                    if idle >= MAX_IDLE_SCROLLS:
                        break
                    continue
                idle = 0
                has_more = nxt["has_more"]
                total = nxt["total"] or total

            await page.wait_for_timeout(1500)
            if pending:
                await asyncio.wait(list(pending), timeout=10)
        finally:
            await browser.close()

    return {
        "profile": profile,
        "works": list(works.values())[:max_works],
        "total": total or len(works),
    }
