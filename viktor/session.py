"""会话上下文: Session(append-only 日志)与 OneShotContext(隔离的一次性上下文)。

依赖方向: session → paths, prompts, capabilities; 不 import bot_*。
"""
import json
import re
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


def _clip_chars(text: str, limit: int) -> str:
    """按字符截断并标注省略(与 bot_agent._clip 同口径, 但这里是叶子模块的独立实现)。"""
    text = text or ""
    return text if len(text) <= limit else text[:limit] + "…"


class Session:
    """一次会话: 从有人进服到服务器清零。上下文平时 append-only 以保证缓存命中;
    唯一的重写路径是 compact()(压缩): 只留玩家消息与游戏内发言, 有损、会打破前缀缓存。"""

    def __init__(self, session_id: int, model: str | None = None):
        self.id = session_id
        self.model = model  # 本会话用的模型别名(见 models.py); 只有开新会话时能变
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

    # ---------- 压缩(compact) ----------
    # 只保留"对话记录": 玩家消息 + 维克托的游戏内发言(send_chat_message, 含 ptc 内嵌)。
    # 工具调用/结果、普通正文、思考内容、旧系统注记全部丢弃; 由调用方负责重新注入
    # 记忆/技能书/模式注记与压缩完成注记, 并开新会话。

    @staticmethod
    def _args_of(tc: dict) -> dict:
        """取一次工具调用的参数字典; 解析失败按空字典处理(宁可少信息也不抛)。"""
        raw = (tc.get("function") or {}).get("arguments")
        try:
            args = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (TypeError, ValueError):
            return {}
        return args if isinstance(args, dict) else {}

    @staticmethod
    def _rewrite_ptc_call(tc: dict) -> dict | None:
        """ptc 调用若夹带 send_chat_message, 重写成只含这些子调用的调用; 否则返回 None。"""
        fn = tc.get("function") or {}
        raw = fn.get("arguments")
        try:
            args = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (TypeError, ValueError):
            return None
        calls = args.get("calls") if isinstance(args, dict) else None
        if not isinstance(calls, list):
            return None
        kept = [c for c in calls if isinstance(c, dict)
                and capabilities._ptc_name(c) == "send_chat_message"]
        if not kept:
            return None
        new_fn = dict(fn)
        new_fn["arguments"] = json.dumps({"calls": kept}, ensure_ascii=False)
        return {**tc, "function": new_fn}

    @staticmethod
    def _rewrite_ptc_result(content: str) -> str:
        """ptc 结果只保留 send_chat_message 的行并重新编号; 没有对应行则返回空串。"""
        lines = []
        for line in (content or "").splitlines():
            m = re.match(r"^\[\d+\]\s*send_chat_message -> (.*)$", line)
            if m:
                lines.append(f"[{len(lines) + 1}] send_chat_message -> {m.group(1)}")
        return "\n".join(lines)

    @staticmethod
    def compact(messages: list[dict], keep_reasoning: bool = True) -> tuple[list[dict], dict]:
        """把上下文压缩成对话记录, 返回 (保留的消息, 统计)。

        保留: 全部 user 消息; assistant 里 send_chat_message 直接调用(及其 tool 结果)、
        ptc 中夹带的 send_chat_message(参数与结果重写成只含这些子调用)。
        丢弃: 其他工具调用与结果、assistant 普通正文与思考、旧 system 注记、孤儿 tool。

        保留的 assistant(tool_calls) 统一 content=None; keep_reasoning=True 时补
        reasoning_content=""(DeepSeek 思考模式要求该字段存在, 空串可用),
        不需要回传思考链的模型(kimi 等)直接不带该字段, 省输入 token。
        某个该保留的调用缺对应 tool 结果时, 整条 assistant 消息丢弃(与 _sanitize 同口径,
        保证配对严格)。
        """
        out: list[dict] = []
        kept_user = kept_speech = 0
        i, n = 0, len(messages)
        while i < n:
            m = messages[i]
            role = m.get("role")
            if role == "user":
                out.append(m)
                kept_user += 1
                i += 1
                continue
            calls = m.get("tool_calls") if role == "assistant" else None
            if calls:
                followers: list[dict] = []
                j = i + 1
                while j < n and messages[j].get("role") == "tool":
                    followers.append(messages[j])
                    j += 1
                have = {f.get("tool_call_id") for f in followers}
                kept_calls, kept_tools, speech = [], [], 0
                broken = False
                for tc in calls:
                    fn = tc.get("function") or {}
                    name = fn.get("name")
                    cid = tc.get("id")
                    if name == "send_chat_message":
                        if cid not in have:
                            broken = True
                            break
                        kept_calls.append(tc)
                        kept_tools.append(next(f for f in followers
                                               if f.get("tool_call_id") == cid))
                        speech += 1
                    elif name == "ptc":
                        rw = Session._rewrite_ptc_call(tc)
                        follower = next((f for f in followers
                                         if f.get("tool_call_id") == cid), None)
                        if rw is None or follower is None:
                            continue
                        result = Session._rewrite_ptc_result(follower.get("content") or "")
                        if not result:
                            continue
                        kept_calls.append(rw)
                        kept_tools.append({**follower, "content": result})
                        speech += len(json.loads(rw["function"]["arguments"])["calls"])
                if broken:
                    kept_calls, kept_tools, speech = [], [], 0
                if kept_calls:
                    kept_msg = {"role": "assistant", "content": None, "tool_calls": kept_calls}
                    if keep_reasoning:
                        kept_msg["reasoning_content"] = ""
                    out.append(kept_msg)
                    out.extend(kept_tools)
                    kept_speech += speech
                i = j
                continue
            i += 1  # 普通正文/思考/旧 system 注记/孤儿 tool: 一律丢弃
        stats = {"kept_user": kept_user, "kept_speech": kept_speech,
                 "dropped": len(messages) - len(out)}
        return out, stats

    # ---------- 智能压缩(摘要式压缩)的输入与附带材料 ----------

    # 建造程序只存在于工具调用参数里(不在世界、也不在行为包留档), 压缩会把它整个丢掉。
    # 智能压缩 / 普通压缩都会把「最后一次」原样带进新会话, 其余模块的源码只能由模型重写。
    BUILD_PROGRAM_TOOLS = ("build_preview", "build_commit", "build_blueprint")

    @classmethod
    def transcript(cls, messages: list[dict], max_chars: int = 40000,
                   arg_chars: int = 240, result_chars: int = 600) -> str:
        """把上下文压成「智能压缩」用的纯文本记录(压缩器模型的输入)。

        保留: 玩家消息、你在游戏内说过的话、工具调用名与参数前段、工具结果前段。
        丢弃: system 注记(记忆/技能书/模式注记压缩后会重新注入)、思考链、你不可见的正文长度。
        超长时保留开头与结尾(开头是原始需求, 结尾是当前进度), 并在中间**明确标注**省略了多少字符——
        不标注的话压缩器会把断口两侧当成连续的事实。"""
        lines: list[str] = []
        for m in messages:
            role = m.get("role")
            if role == "system":
                continue
            if role == "user":
                lines.append("玩家: " + (m.get("content") or ""))
                continue
            if role == "tool":
                lines.append("结果: " + _clip_chars(m.get("content") or "", result_chars))
                continue
            content = (m.get("content") or "").strip()
            if content:
                lines.append("你的正文: " + _clip_chars(content, 300))
            for tc in (m.get("tool_calls") or []):
                fn = tc.get("function") or {}
                name = fn.get("name") or "?"
                args = cls._args_of(tc)
                if name == "send_chat_message":
                    lines.append("你在游戏内说: " + str(args.get("text") or ""))
                    continue
                lines.append(f"调用 {name}: "
                             + _clip_chars(json.dumps(args, ensure_ascii=False), arg_chars))
        text = "\n".join(lines)
        if len(text) <= max_chars:
            return text
        head = max_chars // 4
        tail = max_chars - head
        return (text[:head]
                + f"\n…(中间省略 {len(text) - max_chars} 字符)…\n"
                + text[-tail:])

    @classmethod
    def last_build_program(cls, messages: list[dict], result_chars: int = 500) -> str:
        """取出「压缩前最后一次建造程序」: 程序源码 + 参数(origin/facing/name…) + 结果摘要。

        程序源码只存在于 build_* 的工具调用参数里 —— 压缩把它们全丢掉, 之后既不能复原也查不到,
        继续施工只能重写。这块单独原样保一份, 模型压缩后还能接着改参数、接着预览/提交。
        没有建造调用时返回空串。"""
        for i in range(len(messages) - 1, -1, -1):
            m = messages[i]
            if m.get("role") != "assistant":
                continue
            for tc in reversed(m.get("tool_calls") or []):
                fn = tc.get("function") or {}
                name = fn.get("name")
                if name not in cls.BUILD_PROGRAM_TOOLS:
                    continue
                args = cls._args_of(tc)
                program = args.get("program")
                if not isinstance(program, str) or not program.strip():
                    continue
                meta = {k: args[k] for k in ("name", "origin", "facing", "scan", "symmetry")
                        if k in args}
                result = ""
                for f in messages[i + 1:]:
                    if f.get("role") == "assistant":
                        break
                    if f.get("role") == "tool" and f.get("tool_call_id") == tc.get("id"):
                        result = f.get("content") or ""
                        break
                parts = ["# 压缩前最后一次建造程序(原样保留: 可以直接改参数重新预览/提交)",
                         f"- 调用: {name}"
                         + (f", 参数: {json.dumps(meta, ensure_ascii=False)}" if meta else "")]
                if result:
                    parts.append(f"- 那次调用的结果(前 {result_chars} 字): "
                                 + _clip_chars(result, result_chars))
                parts.extend(["- 程序源码:", "[程序开始]", program.strip(), "[程序结束]"])
                return "\n".join(parts)
        return ""

    def build_request_messages(self) -> list[dict]:
        """全局常量 system 前缀 + append-only 日志, 不做任何裁剪。
        模式行为与动态数值都在日志里的系统注记中, 所以切模式/更新记忆只追加尾部,
        前缀不变。裁剪会破坏缓存前缀, 且从 assistant(tool_calls)/tool 中间切开会产生
        孤立 tool 消息, 导致 API 400。"""
        return [{"role": "system", "content": SYSTEM_PROMPT}] \
            + self._sanitize(self.messages)

    def has_conversation(self) -> bool:
        """是否含实际对话(玩家消息/发言)。只有系统注记(记忆/技能书/模式)的会话没有落盘价值。"""
        return any(m.get("role") in ("user", "assistant") for m in self.messages)

    def dump(self, directory: Path | None = None, tag: str = "session"):
        """把会话落盘为 jsonl。只有系统注记、没有实际对话的会话不落盘——
        否则“玩家进服后立刻退出/重启”会留下空会话文件, 污染 logs/sessions/,
        还会被“恢复会话”当成最近一段误选。返回落盘路径, 跳过时返回 None。"""
        if not self.has_conversation():
            log(f"[会话] #{self.id} 只有系统注记、无对话内容, 跳过落盘")
            return None
        directory = directory or paths.SESSION_DIR
        directory.mkdir(parents=True, exist_ok=True)
        name = self.started.strftime(f"{tag}-%Y%m%d-%H%M%S") + f"-s{self.id}.jsonl"
        with open(directory / name, "w", encoding="utf-8") as f:
            # 首行是元信息(不是消息): 记录本会话用的模型, 供「恢复会话」按原模型灌回。
            # 读会话时按 "_meta" 键跳过这一行(见 bot_control.resume_session)。
            f.write(json.dumps({"_meta": {"session": self.id, "model": self.model,
                                          "started": self.started.isoformat(timespec="seconds")}},
                               ensure_ascii=False) + "\n")
            for m in self.messages:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
        return directory / name


class OneShotContext:
    """一次一次性对话的独立上下文。与主对话完全隔离, 可多个并发。"""

    def __init__(self, oid: int, player: str, content: str):
        self.id = oid
        self.player = player
        self.content = content
        self.abort = threading.Event()       # 单独中止这一个(目前只有全局 "1 强制停止" 会置位)
        self.soft_abort = threading.Event()
        self.session = Session(oid)          # ephemeral: 结束后落盘到 logs/oneshot/, 不进主会话

