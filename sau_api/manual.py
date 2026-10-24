"""手动发布：打开平台的官方后台（创作者中心），带登录态，交给用户手动操作。

以子进程运行：python -m sau_api.manual --platform douyin --account creator
启动一个有界面的浏览器，注入账号 cookie 后打开官方后台，保持运行直到用户关闭窗口。
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from patchright.async_api import async_playwright

from conf import DATA_DIR
from utils.base_social_media import set_init_script

# 各平台官方后台入口（优先直接落在发布页/内容管理页）
PLATFORM_HOME_URL = {
    "douyin": "https://creator.douyin.com/creator-micro/content/publish",
    "tencent": "https://channels.weixin.qq.com/platform/post/create",
    "xiaohongshu": "https://creator.xiaohongshu.com",
    "kuaishou": "https://cp.kuaishou.com/article/publish/video",
    "bilibili": "https://member.bilibili.com/platform/upload/video/frame",
    "weibo": "https://weibo.com/",
    "hupu": "https://bbs.hupu.com/newpost",
    "alipay": "https://c.alipay.com/page/content-creation/posts",
    "baijiahao": "https://baijiahao.baidu.com/builder/rc/edit",
    "dayu": "https://mp.dayu.com/dashboard/video/write",
    "xueqiu": "https://mp.xueqiu.com/",
    "zhihu": "https://www.zhihu.com/creator",
    "facebook": "https://business.facebook.com/latest/composer/",
    "facebook-page": "https://business.facebook.com/latest/composer/",
    "instagram": "https://www.instagram.com/",
    "youtube": "https://studio.youtube.com",
}


def _cookie_file(platform: str, account: str) -> Path:
    return Path(DATA_DIR) / "cookies" / f"{platform}_{account}.json"


async def open_creator(platform: str, account: str) -> None:
    cookie = _cookie_file(platform, account)
    if not cookie.exists():
        raise FileNotFoundError(f"账号文件不存在: cookies/{cookie.name}")
    url = PLATFORM_HOME_URL.get(platform)
    if not url:
        raise ValueError(f"平台 {platform} 暂不支持打开官方后台")

    print(f"[手动发布] 打开 {platform}/{account} 官方后台: {url}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="chromium")
        context = await browser.new_context(storage_state=str(cookie))
        await set_init_script(context)
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=120000)
        print("[手动发布] 浏览器已打开，登录态已注入，请在窗口中手动操作。")

        # 保持运行，直到用户关闭浏览器窗口
        while browser.is_connected():
            await asyncio.sleep(1)
        print("[手动发布] 浏览器已关闭。")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sau-manual")
    parser.add_argument("--platform", required=True)
    parser.add_argument("--account", required=True)
    args = parser.parse_args(argv)
    try:
        asyncio.run(open_creator(args.platform, args.account))
    except Exception as exc:  # noqa: BLE001
        print(f"[手动发布] 失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
