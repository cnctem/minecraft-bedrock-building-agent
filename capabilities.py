#!/usr/bin/env python3
"""维克托的能力注册表。

新增能力的方法:
  1. 写一个 handler: 接收 dict 参数, 返回给 AI 看的执行结果字符串
  2. 写一个 OpenAI function calling 格式的 schema
  3. 在 _REGISTRY 里登记 (schema, handler)

bot 会把所有注册的 schema 通过 function calling 告诉 DeepSeek,
AI 决定调用时由 bot 执行 handler 并把结果回传, 然后 AI 再生成最终回复。
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SERVER_LOG = BASE_DIR / "logs" / "server.log"
MEMORY_PATH = BASE_DIR / "memory.md"
MEMORY_BACKUP_DIR = BASE_DIR / "logs" / "memory-backup"
MEMORY_SOFT_LIMIT = 4000  # 字符; 超出时提醒 AI 下次精简


# ---------- 记忆 ----------

def read_memory() -> str:
    """每次请求前调用, 人工直接编辑 memory.md 也会即时生效。"""
    try:
        return MEMORY_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def update_memory(content: str) -> str:
    """整篇重写记忆, 重写前自动备份旧版本。"""
    old = read_memory()
    if old:
        MEMORY_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup = MEMORY_BACKUP_DIR / datetime.now().strftime("memory-%Y%m%d-%H%M%S.md")
        backup.write_text(old + "\n", encoding="utf-8")
    MEMORY_PATH.write_text(content.strip() + "\n", encoding="utf-8")
    msg = "记忆已更新。"
    if len(content) > MEMORY_SOFT_LIMIT:
        msg += (f"注意: 当前 {len(content)} 字符, 已超过 {MEMORY_SOFT_LIMIT} 软上限, "
                "请在下一次更新时精简合并。")
    return msg


# ---------- 服务器日志查询 ----------

_RE_TS = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}):\d+ INFO\] (.*)$")
_RE_JOIN = re.compile(r"^Player connected: ([^,]+), xuid:")
_RE_LEAVE = re.compile(r"^Player disconnected: ([^,]+), xuid:")


def get_player_activity(minutes: int = 60) -> str:
    """从 screen 日志解析最近 N 分钟的玩家进出记录。"""
    minutes = max(1, min(int(minutes), 24 * 60))
    cutoff = datetime.now() - timedelta(minutes=minutes)
    events = []
    try:
        lines = SERVER_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return "服务器日志不存在。"
    for line in lines:
        m = _RE_TS.match(line)
        if not m:
            continue
        ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        if ts < cutoff:
            continue
        if j := _RE_JOIN.match(m.group(2)):
            events.append(f"{m.group(1)[11:]} {j.group(1)} 进服")
        elif l := _RE_LEAVE.match(m.group(2)):
            events.append(f"{m.group(1)[11:]} {l.group(1)} 离服")
    if not events:
        return f"最近 {minutes} 分钟内没有玩家进出记录。"
    body = "\n".join(events[-30:])
    return f"最近 {minutes} 分钟内的玩家进出记录:\n{body}"


GET_ACTIVITY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_player_activity",
        "description": (
            "查询玩家进服/离服记录, 回答“刚才谁来过/什么时候走的”这类问题。"
            "数据来自服务器日志, 只能查到日志开始记录以来(本次开服后)的事件。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "minutes": {"type": "integer", "description": "向前查多少分钟, 默认 60"},
            },
        },
    },
}


# ---------- 注册表 ----------

UPDATE_MEMORY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "update_memory",
        "description": (
            "仅当玩家明确要求你记住、修改或忘记信息时调用(例如“记住…”“记一下…”“忘掉…”“改一下记忆”)。"
            "绝对不要主动调用, 也不要主动问玩家是否需要记录。"
            "用新全文(markdown)整体替换长期记忆——旧内容不会被自动保留, "
            f"需要保留的部分必须包含在新全文里。尽量控制在 {MEMORY_SOFT_LIMIT} 字符以内。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "长期记忆的新全文(markdown)"},
            },
            "required": ["content"],
        },
    },
}

STAY_SILENT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "stay_silent",
        "description": "保持安静, 不向游戏内聊天栏发送任何消息。",
        "parameters": {"type": "object", "properties": {}},
    },
}

_REGISTRY = {
    "update_memory": (UPDATE_MEMORY_SCHEMA, lambda args: update_memory(args["content"])),
    "stay_silent": (STAY_SILENT_SCHEMA, lambda args: "已保持安静。"),
    "get_player_activity": (GET_ACTIVITY_SCHEMA,
                            lambda args: get_player_activity(args.get("minutes", 60))),
    # 未来新能力加在这里: "tool_name": (SCHEMA, handler)
}


def tool_schemas() -> list[dict]:
    return [schema for schema, _ in _REGISTRY.values()]


def register(name: str, schema: dict, handler):
    """运行时注册新能力(bot 会注册依赖自身资源的能力, 如发消息)。"""
    _REGISTRY[name] = (schema, handler)


def execute(name: str, arguments_json: str) -> str:
    entry = _REGISTRY.get(name)
    if not entry:
        return f"错误: 未知能力 {name}"
    try:
        args = json.loads(arguments_json or "{}")
        return str(entry[1](args))
    except Exception as e:
        return f"错误: 执行 {name} 失败: {e}"
