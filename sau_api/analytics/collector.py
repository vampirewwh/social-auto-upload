"""采集入口：python -m sau_api.analytics.collector --platform douyin --account creator"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time

from sau_api.analytics import store
from sau_api.analytics.douyin import collect_douyin

SUPPORTED = {"douyin"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sau-analytics")
    parser.add_argument("--platform", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--source", default="manual", help="manual / schedule")
    parser.add_argument("--max-works", type=int, default=500)
    parser.add_argument("--headed", action="store_true", help="显示浏览器窗口，便于排查登录问题")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.platform not in SUPPORTED:
        print(f"[错误] 暂不支持平台: {args.platform}", file=sys.stderr)
        return 2

    store.init_db()
    run_id = store.start_run(args.platform, args.account, args.source)
    print(f"[开始] 采集 {args.platform}/{args.account} ...")
    captured_at = time.time()
    try:
        result = asyncio.run(
            collect_douyin(
                args.account,
                headless=not args.headed,
                max_works=args.max_works,
            )
        )
    except Exception as exc:  # noqa: BLE001
        store.finish_run(run_id, "failed", 0, str(exc))
        print(f"[失败] {exc}", file=sys.stderr)
        return 1

    profile = result["profile"]
    works = result["works"]
    if not profile and not works:
        msg = "采集结果为空，可能是登录态失效"
        store.finish_run(run_id, "failed", 0, msg)
        print(f"[失败] {msg}", file=sys.stderr)
        return 1

    store.save_snapshot(args.platform, args.account, profile, captured_at)
    try:
        count = store.upsert_works(args.platform, args.account, works, captured_at)
    except Exception as exc:  # noqa: BLE001
        # 写库失败也要收敛采集记录，否则会一直显示 running
        store.finish_run(run_id, "failed", 0, f"写入作品失败: {exc}")
        print(f"[失败] 写入作品失败: {exc}", file=sys.stderr)
        return 1
    store.finish_run(run_id, "success", count)

    print(
        f"[完成] {profile.get('nickname') or args.account}："
        f"粉丝 {profile.get('follower_count')}，作品 {count} 条"
    )
    print(json.dumps({"profile": profile, "work_count": count}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
