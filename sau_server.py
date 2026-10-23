"""新版 Web 服务入口：把 sau CLI 的全部平台能力暴露为 HTTP API。

与旧的 sau_backend.py 的区别：
- 平台覆盖来自 sau_cli 的 parser 自省，新增平台无需改后端；
- 不再硬编码 4 个平台的发布函数；
- 任务以子进程执行，前端看日志与状态。
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

from conf import BASE_DIR
from sau_api import accounts as accounts_mod
from sau_api.login import login_manager
from sau_api.schema import build_platform_schema, serialize_arguments
from sau_api.tasks import manager

PROJECT_ROOT = Path(BASE_DIR)
FRONTEND_DIST = PROJECT_ROOT / "sau_frontend" / "dist"

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIST / "assets"),
    static_url_path="/assets",
)
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024

_parser = None


def get_parser() -> argparse.ArgumentParser:
    global _parser
    if _parser is None:
        from sau_cli import build_parser

        _parser = build_parser()
    return _parser


def _action_parser(platform: str, action: str) -> argparse.ArgumentParser:
    parser = get_parser()
    platforms = parser._subparsers._group_actions[0].choices
    if platform not in platforms:
        raise ValueError(f"未知平台: {platform}")
    actions = platforms[platform]._subparsers._group_actions[0].choices
    if action not in actions:
        raise ValueError(f"平台 {platform} 不支持动作: {action}")
    return actions[action]


def _build_argv(platform: str, action: str, values: dict[str, Any]) -> list[str]:
    """按 argparse 字段描述把前端提交的 values 拼成命令行参数。"""
    schema = serialize_arguments(_action_parser(platform, action))
    argv: list[str] = [platform, action]
    missing: list[str] = []

    for field in schema["fields"]:
        dest = field["dest"]
        if dest not in values:
            if field["required"]:
                missing.append(field["flag"])
            continue

        value = values[dest]
        blank = value is None or value == "" or value == []
        if blank:
            if field["required"]:
                missing.append(field["flag"])
            continue

        flags = field["flags"]
        if field["kind"] == "bool":
            wanted = bool(value)
            matched = None
            default = field["default"]
            for variant in field.get("variants") or []:
                if bool(variant["value"]) == wanted:
                    matched = variant["flag"]
                    break
            # 与默认值一致时不传，避免生成互相冲突的开关
            if matched is not None and default != wanted:
                argv.append(matched)
            continue

        if field["positional"]:
            argv.append(str(value))
            continue

        flag = flags[0] if flags else field["flag"]
        if field["kind"] == "list" or isinstance(value, list):
            items = value if isinstance(value, list) else [value]
            argv.append(flag)
            argv.extend(str(item) for item in items)
            continue

        argv.extend([flag, str(value)])

    if missing:
        raise ValueError("缺少必填参数: " + ", ".join(missing))

    return argv


def _ok(data: Any = None, msg: str | None = None):
    return jsonify({"code": 200, "data": data, "msg": msg})


def _err(msg: str, code: int = 400):
    return jsonify({"code": code, "data": None, "msg": msg}), code


# ---------------------------------------------------------------- schema

@app.get("/api/schema")
def api_schema():
    try:
        schema = build_platform_schema(get_parser())
    except Exception as exc:  # noqa: BLE001
        return _err(f"生成参数结构失败: {exc}", 500)
    labels = accounts_mod.PLATFORM_LABELS
    payload = {
        name: {
            "label": labels.get(name, name),
            "help": info["help"],
            "actions": info["actions"],
        }
        for name, info in schema.items()
    }
    return _ok(payload)


@app.get("/api/health")
def api_health():
    return _ok({"ok": True, "root": str(PROJECT_ROOT)})


# ---------------------------------------------------------------- tasks

@app.post("/api/tasks")
def api_create_task():
    body = request.get_json(silent=True) or {}
    platform = body.get("platform")
    action = body.get("action")
    values = body.get("values") or {}
    if not platform or not action:
        return _err("缺少 platform 或 action")

    try:
        argv = _build_argv(platform, action, values)
    except ValueError as exc:
        return _err(str(exc))

    task = manager.create(platform, action, argv)
    manager.start(task)
    return _ok(task.snapshot(include_logs=False))


@app.get("/api/tasks")
def api_list_tasks():
    limit = min(int(request.args.get("limit", 50)), 200)
    return _ok([t.snapshot(include_logs=False) for t in manager.list(limit)])


@app.get("/api/tasks/<task_id>")
def api_get_task(task_id: str):
    task = manager.get(task_id)
    if not task:
        return _err("任务不存在", 404)
    tail = int(request.args.get("tail", 0) or 0)
    return _ok(task.snapshot(include_logs=True, tail=tail))


@app.post("/api/tasks/<task_id>/cancel")
def api_cancel_task(task_id: str):
    task = manager.get(task_id)
    if not task:
        return _err("任务不存在", 404)
    cancelled = manager.cancel(task)
    return _ok({"cancelled": cancelled, "task": task.snapshot(include_logs=False)})


@app.delete("/api/tasks")
def api_clear_tasks():
    return _ok({"cleared": manager.clear_finished()})


# ---------------------------------------------------------------- accounts

@app.get("/api/accounts")
def api_accounts():
    return _ok(accounts_mod.list_accounts())


@app.delete("/api/accounts")
def api_delete_account():
    platform = request.args.get("platform", "")
    account = request.args.get("account", "")
    if not platform or not account:
        return _err("缺少 platform 或 account")
    if accounts_mod.delete_account(platform, account):
        return _ok({"deleted": True})
    return _err("账号不存在", 404)


@app.post("/api/accounts/upload")
def api_upload_account():
    platform = request.form.get("platform", "")
    account = request.form.get("account", "")
    file = request.files.get("file")
    if not platform or not account or not file:
        return _err("缺少 platform / account / file")
    try:
        info = accounts_mod.save_uploaded_cookie(platform, account, file.read())
    except ValueError as exc:
        return _err(str(exc))
    return _ok(info)


# ---------------------------------------------------------------- materials

@app.get("/api/materials")
def api_materials():
    return _ok(accounts_mod.list_materials())


@app.post("/api/materials/upload")
def api_upload_material():
    file = request.files.get("file")
    if not file or not file.filename:
        return _err("没有收到文件")
    info = accounts_mod.save_material(file.filename, file.read())
    return _ok(info)


@app.delete("/api/materials")
def api_delete_material():
    name = request.args.get("name", "")
    if not name:
        return _err("缺少 name")
    if accounts_mod.delete_material(name):
        return _ok({"deleted": True})
    return _err("文件不存在", 404)


@app.get("/api/materials/preview/<path:name>")
def api_preview_material(name: str):
    target = accounts_mod.VIDEO_DIR / name
    if not target.exists() or not target.is_file():
        return _err("文件不存在", 404)
    return send_from_directory(target.parent, target.name)


# ---------------------------------------------------------------- login

@app.post("/api/login/start")
def api_login_start():
    body = request.get_json(silent=True) or {}
    platform = body.get("platform")
    account = body.get("account")
    headless = bool(body.get("headless", True))
    if not platform or not account:
        return _err("缺少 platform 或 account")
    try:
        session = login_manager.start(platform, account, headless)
    except ValueError as exc:
        return _err(str(exc))
    return _ok(session.snapshot())


@app.get("/api/login/<session_id>/stream")
def api_login_stream(session_id: str):
    session = login_manager.get(session_id)
    if not session:
        return _err("登录会话不存在", 404)
    return Response(
        login_manager.stream(session),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/login/platforms")
def api_login_platforms():
    from sau_api import login as login_mod

    labels = accounts_mod.PLATFORM_LABELS
    qr = login_mod.qr_ready_platforms()
    browser = login_mod.browser_only_platforms()
    return _ok(
        {
            "qrcode": [
                {"platform": p, "label": labels.get(p, p), "mode": "qrcode"} for p in qr
            ],
            "browser": [
                {"platform": p, "label": labels.get(p, p), "mode": "browser"}
                for p in browser
            ],
        }
    )


@app.get("/api/login/sessions")
def api_login_sessions():
    return _ok(login_manager.list())


# ---------------------------------------------------------------- static

@app.get("/")
def index():
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return send_from_directory(FRONTEND_DIST, "index.html")
    return _ok(
        {
            "message": "前端尚未构建，请先 cd sau_frontend && npm run build",
            "dist": str(FRONTEND_DIST),
        }
    )


@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return _err("接口不存在", 404)
    # 先尝试 dist 根目录下的真实文件（favicon、vite.svg 等）
    rel = request.path.lstrip("/")
    if rel:
        candidate = FRONTEND_DIST / rel
        try:
            if candidate.is_file() and FRONTEND_DIST in candidate.resolve().parents:
                return send_from_directory(FRONTEND_DIST, rel)
        except OSError:
            pass
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return send_from_directory(FRONTEND_DIST, "index.html")
    return _err("Not Found", 404)


if __name__ == "__main__":
    port = int(os.environ.get("SAU_WEB_PORT", "5409"))
    app.run(host="0.0.0.0", port=port, threaded=True)
