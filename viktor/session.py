"""会话上下文: Session(append-only 日志)与 OneShotContext(隔离的一次性上下文)。

依赖方向: session → paths, prompts, capabilities; 不 import bot_*。
"""
import json
import threading
from datetime import datetime
from pathlib import Path

import capabilities

from . import paths
from .paths import log
from .prompts import SYSTEM_PROMPT


def memory_note() -> str:
    """长期记忆注记。会话开始时注入一条; update_memory 之后再追加一条(以最新为准)。
    读文件与固定前缀无关, 所以人工改 memory.md 也不会改动已发出的前缀。"""
    return "# 你的长期记忆\n\n" + (capabilities.read_memory() or "(空)")


class Session:
    """一次会话: 从有人进服到服务器清零。上下文 append-only 以保证缓存命中。"""

    def __init__(self, session_id: int):
        self.id = session_id
        self.started = datetime.now()
        self.messages: list[dict] = []  # 不含 system
        self.replied_count = 0
        self.loaded_skills: set[str] = set()  # 本会话已载入的技能, 避免重复占上下文

    def add_user(self, content: str):
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str):
        self.messages.append({"role": "assistant", "content": content})

    def add_system(self, content: str):
        """追加一条系统注记(长期记忆/模式切换等)。只追加, 不改前缀。"""
        self.messages.append({"role": "system", "content": content})

    @staticmethod
    def _est_tokens(msgs: list[dict]) -> int:
        """上下文体积的粗略估算: 累加每条消息的 JSON 字符数。
        中文大致 1 字符兑 1 token, 英文/JSON 密度更低, 因此该值偏大。"""
        return sum(len(json.dumps(m, ensure_ascii=False)) for m in msgs)

    @staticmethod
    def _sanitize(msgs: list[dict]) -> list[dict]:
        """保证 assistant(tool_calls) 与紧随其后的 tool 响应严格成对。
        配对破损(例如清空撞在工具往返中间)会让 DeepSeek 返回 400,
        且之后每次请求都 400; 发送前必须先修好。"""
        out: list[dict] = []
        dropped = 0
        i = 0
        while i < len(msgs):
            m = msgs[i]
            role = m.get("role")
            if role == "tool":  # 无主的 tool 响应
                dropped += 1
                i += 1
                continue
            calls = m.get("tool_calls") if role == "assistant" else None
            if calls:
                want = [c.get("id") for c in calls]
                followers = []
                j = i + 1
                while j < len(msgs) and msgs[j].get("role") == "tool":
                    followers.append(msgs[j])
                    j += 1
                have = {f.get("tool_call_id") for f in followers}
                if all(t in have for t in want):
                    out.append(m)
                    kept = set()
                    for f in followers:  # 只留 id 对得上的, 多余的(孤儿)丢弃
                        fid = f.get("tool_call_id")
                        if fid in want and fid not in kept:
                            out.append(f)
                            kept.add(fid)
                        else:
                            dropped += 1
                    i = j
                    continue
                # 配对不全: 丢掉 tool_calls 只留正文, 后面那些无主响应一并丢弃
                dropped += len(followers)
                rest = {k: v for k, v in m.items() if k != "tool_calls"}
                i = j
                if (rest.get("content") or "").strip():
                    out.append(rest)
                continue
            out.append(m)
            i += 1
        if dropped:
            log(f"[上下文] 发送前修复了 {dropped} 条不成对的 tool 消息(否则 API 会 400)")
        return out

    def build_request_messages(self) -> list[dict]:
        """全局常量 system 前缀 + append-only 日志, 不做任何裁剪。
        模式行为与动态数值都在日志里的系统注记中, 所以切模式/更新记忆只追加尾部,
        前缀不变。裁剪会破坏缓存前缀, 且从 assistant(tool_calls)/tool 中间切开会产生
        孤立 tool 消息, 导致 API 400。"""
        return [{"role": "system", "content": SYSTEM_PROMPT}] \
            + self._sanitize(self.messages)

    def dump(self, directory: Path | None = None, tag: str = "session"):
        directory = directory or paths.SESSION_DIR
        directory.mkdir(parents=True, exist_ok=True)
        name = self.started.strftime(f"{tag}-%Y%m%d-%H%M%S") + f"-s{self.id}.jsonl"
        with open(directory / name, "w", encoding="utf-8") as f:
            for m in self.messages:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")


class OneShotContext:
    """一次一次性对话的独立上下文。与主对话完全隔离, 可多个并发。"""

    def __init__(self, oid: int, player: str, content: str):
        self.id = oid
        self.player = player
        self.content = content
        self.abort = threading.Event()       # 单独中止这一个(目前只有全局 "1 强制停止" 会置位)
        self.soft_abort = threading.Event()
        self.session = Session(oid)          # ephemeral: 结束后落盘到 logs/oneshot/, 不进主会话

