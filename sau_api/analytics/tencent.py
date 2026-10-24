"""视频号创作者中心数据采集。

视频号作品列表是 POST 分页（currentPage + rawKeyBuff 游标），
不是滚动加载，所以拦截第一页拿参数模板后，用页面 fetch 手动翻页。
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any

from patchright.async_api import async_playwright

from conf import DATA_DIR
from utils.base_social_media import set_init_script

POST_LIST_URL = "https://channels.weixin.qq.com/platform/post/list"
FIRST_RESPONSE_TIMEOUT = 40
FETCH_JS = """
async ({url, body}) => {
    const resp = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body),
        credentials: 'include',
    });
    return await resp.json();
}
"""


def _cookie_file(account: str) -> Path:
    return Path(DATA_DIR) / "cookies" / f"tencent_{account}.json"


def _parse_account(data: dict[str, Any]) -> dict[str, Any]:
    finder = (data.get("data") or {}).get("finderUser") or {}
    return {
        "nickname": finder.get("nickname"),
        "avatar": finder.get("headImgUrl"),
        "follower_count": finder.get("fansCount"),
        "following_count": None,
        "total_favorited": None,
        "aweme_count": finder.get("feedsCount"),
        "enterprise_verify": finder.get("adminNickname"),
        "douyin_id": finder.get("uniqId"),
    }


def _parse_work(item: dict[str, Any]) -> dict[str, Any] | None:
    object_id = str(item.get("objectId") or item.get("exportId") or "")
    if not object_id:
        return None
    desc = item.get("desc") or {}
    media = desc.get("media") or []
    first = media[0] if media else {}
    return {
        "aweme_id": object_id,
        "desc": desc.get("description") or "",
        "cover": first.get("coverUrl") or first.get("thumbUrl") or "",
        "create_time": item.get("createTime") or 0,
        "is_private": 0 if item.get("visibleType") == 1 else 1,
        "in_reviewing": 0,
        "play_count": item.get("readCount") or 0,
        "digg_count": item.get("likeCount") or 0,
        "comment_count": item.get("commentCount") or 0,
        "share_count": item.get("forwardCount") or 0,
        "collect_count": item.get("favCount") or 0,
        "duration": first.get("videoPlayLen") or 0,
    }


def _new_rid() -> str:
    return f"{uuid.uuid4().hex[:8]}-{uuid.uuid4().hex[:8]}"


def _re_rid(url: str, new_rid: str) -> str:
    import re
    return re.sub(r"_rid=[0-9a-f]{8}-[0-9a-f]{8}", f"_rid={new_rid}", url)


async def collect_tencent(
    account: str,
    headless: bool = True,
    max_works: int = 500,
    max_pages: int = 50,
) -> dict[str, Any]:
    cookie = _cookie_file(account)
    if not cookie.exists():
        raise FileNotFoundError(f"账号文件不存在: cookies/{cookie.name}")

    profile: dict[str, Any] = {}
    works: dict[str, dict[str, Any]] = {}
    req_template: dict[str, Any] = {"url": "", "body": {}}
    first_page: asyncio.Queue = asyncio.Queue()
    total = 0

    def merge(extra: dict[str, Any], prefer: bool = False) -> None:
        for key, value in extra.items():
            if value in (None, ""):
                continue
            if prefer or not profile.get(key):
                profile[key] = value

    def ingest(data: dict[str, Any]) -> tuple[bool, int, str]:
        payload = (data.get("data") or {})
        for item in payload.get("list") or []:
            work = _parse_work(item)
            if work:
                works[work["aweme_id"]] = work
        return (
            bool(payload.get("continueFlag")),
            int(payload.get("totalCount") or 0),
            payload.get("lastBuff") or "",
        )

    async def on_request(req) -> None:
        if "/post/post_list" in req.url and not req_template["url"]:
            req_template["url"] = req.url
            try:
                req_template["body"] = json.loads(req.post_data or "{}")
            except Exception:  # noqa: BLE001
                req_template["body"] = {}

    async def on_response(resp) -> None:
        url = resp.url
        if "channels.weixin.qq.com" not in url:
            return
        try:
            if "/auth/auth_data" in url:
                merge(_parse_account(await resp.json()), prefer=True)
            elif "/post/post_list" in url:
                has_more, total, last_buff = ingest(await resp.json())
                await first_page.put({"has_more": has_more, "total": total, "last_buff": last_buff})
        except Exception:  # noqa: BLE001
            return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, channel="chromium")
        context = await browser.new_context(storage_state=str(cookie))
        await set_init_script(context)
        page = await context.new_page()
        page.on("request", lambda r: asyncio.create_task(on_request(r)))
        page.on("response", lambda r: asyncio.create_task(on_response(r)))
        try:
            await page.goto(POST_LIST_URL, wait_until="domcontentloaded", timeout=60000)
            first = await asyncio.wait_for(first_page.get(), timeout=FIRST_RESPONSE_TIMEOUT)

            has_more = first["has_more"]
            total = first["total"]
            last_buff = first["last_buff"]
            page_num = 2
            while has_more and len(works) < max_works and page_num <= max_pages:
                body = dict(req_template["body"])
                body["currentPage"] = page_num
                body["rawKeyBuff"] = last_buff
                body["timestamp"] = str(int(time.time() * 1000))
                url = _re_rid(req_template["url"], _new_rid())
                data = await page.evaluate(FETCH_JS, {"url": url, "body": body})
                has_more, total, last_buff = ingest(data)
                page_num += 1

            await page.wait_for_timeout(1500)
        finally:
            await browser.close()

    if profile.get("total_favorited") in (None, 0):
        profile["total_favorited"] = sum(
            w.get("digg_count") or 0 for w in works.values()
        )

    return {
        "profile": profile,
        "works": list(works.values())[:max_works],
        "total": total or len(works),
    }
