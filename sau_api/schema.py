"""从 argparse 结构自省出前端可渲染的表单 schema。

CLI 每个平台命令都由 sau_cli.build_parser() 声明参数，
这里直接读取 argparse 对象的 _actions，因此 CLI 新增参数时
前端表单会自动跟上，不需要手工维护字段列表。
"""
from __future__ import annotations

import argparse
from typing import Any, Iterable

# argparse 的 type 名字 -> 前端控件类型
_TYPE_MAP = {
    "int": "number",
    "float": "number",
    "existing_file_path": "file",
    "existing_dir_path": "dir",
    "schedule_value": "datetime",
}

_TYPE_HINT = {
    "int": "number",
    "float": "number",
    "existing_file_path": "file",
    "existing_dir_path": "dir",
    "schedule_value": "datetime",
}

# 布尔型 store_true/store_false 的 nargs 为 0
_BOOL_ACTION_TYPES = (argparse._StoreTrueAction, argparse._StoreFalseAction)


def _iter_actions(parser: argparse.ArgumentParser) -> Iterable[argparse.Action]:
    for action in parser._actions:
        if action.dest in ("help", "command"):
            continue
        yield action


def _action_kind(action: argparse.Action, variants: list[dict[str, Any]] | None = None) -> str:
    if isinstance(action, _BOOL_ACTION_TYPES):
        return "bool"
    type_name = getattr(action.type, "__name__", None)
    if type_name in _TYPE_MAP:
        return _TYPE_MAP[type_name]
    if action.choices:
        return "select"
    if action.nargs in ("+", "*") or (isinstance(action.nargs, int) and action.nargs > 1):
        return "list"
    return "string"


def _action_default(action: argparse.Action) -> Any:
    default = action.default
    if default is argparse.SUPPRESS or default is None:
        return None
    if isinstance(default, (str, int, float, bool)):
        return default
    return None


def _bool_variants(action: argparse.Action) -> list[dict[str, Any]]:
    """store_true 的值是 True，store_false 的值是 False，都记下来。"""
    if isinstance(action, argparse._StoreTrueAction):
        value = True
    elif isinstance(action, argparse._StoreFalseAction):
        value = False
    else:
        value = True
    return [{"flag": flag, "value": value} for flag in action.option_strings]


def serialize_arguments(parser: argparse.ArgumentParser) -> dict[str, Any]:
    """把一个 action 子命令的参数序列化成前端字段描述。"""
    fields: list[dict[str, Any]] = []
    index: dict[str, dict[str, Any]] = {}

    for action in _iter_actions(parser):
        options = action.option_strings
        flag = options[0] if options else action.dest
        kind = _action_kind(action)

        existing = index.get(action.dest)
        if existing is not None:
            # 同一个 dest 的互斥开关（如 --headed / --headless）合并成一个字段
            for flag_name in options:
                if flag_name not in existing["flags"]:
                    existing["flags"].append(flag_name)
            if kind == "bool":
                variants = existing.setdefault("variants", [])
                for item in _bool_variants(action):
                    if item["flag"] not in {v["flag"] for v in variants}:
                        variants.append(item)
                # 让字段的 flag/help 跟随默认值对应的那个开关，
                # 否则 --headed/--headless 合并后 help 会描述反义的那个。
                default = existing.get("default")
                for variant in variants:
                    if default is not None and variant["value"] == default:
                        existing["flag"] = variant["flag"]
                        existing["help"] = (action.help or existing["help"]).replace("%%", "%")
                        break
            continue

        field: dict[str, Any] = {
            "dest": action.dest,
            "flag": flag,
            "flags": list(options),
            "kind": kind,
            "required": bool(getattr(action, "required", False)),
            "default": _action_default(action),
            "nargs": action.nargs if isinstance(action.nargs, (str, int)) else None,
            "help": (action.help or "").replace("%%", "%"),
            "choices": list(action.choices) if action.choices else None,
            "metavar": action.metavar,
            "positional": not options,
        }
        if kind == "bool":
            field["variants"] = _bool_variants(action)
        fields.append(field)
        index[action.dest] = field

    fields.sort(key=lambda f: (not f["required"],))
    return {"fields": fields}


def build_platform_schema(cli_parser: argparse.ArgumentParser) -> dict[str, Any]:
    """把整个 sau CLI 的 parser 转成 {平台: {actions: {...}}} 结构。"""
    result: dict[str, Any] = {}
    platform_actions = cli_parser._subparsers._group_actions[0].choices

    for platform_name, platform_parser in platform_actions.items():
        action_parsers = platform_parser._subparsers._group_actions[0].choices
        result[platform_name] = {
            "help": platform_parser.description or "",
            "actions": {
                action_name: serialize_arguments(action_parser)
                for action_name, action_parser in action_parsers.items()
            },
        }
    return result
