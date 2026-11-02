"""会话历史: 列出落盘会话, 把某个会话按「压缩」口径渲染成对话记录。

会话落盘是 append-only 的 JSONL(首行 `_meta`, 之后每行一条消息), 本身已经是压缩后的产物
(压缩/智能压缩会重建会话并落盘), 所以读的时候不再回放工具调用: 复用 `Session.compact`
只留玩家消息与维克托在游戏内说过的话, 再渲染成 `玩家: …` / `维克托: …` 的纯文本。

用途: 玩家问「上次聊了什么/之前那个工程做到哪」, 或需要参考历史时按需读取, 而不是
把历史预置进上下文。

依赖方向: history → paths/session(只用其 compact 与文本工具); 不 import bot_*。
"""
import json
from pathlib import Path

from . import paths
from .session import Session

DEFAULT_LIST_LIMIT = 10
DEFAULT_MAX_CHARS = 12000
MAX_FILE_BYTES = 16 * 1024 * 1024


class HistoryError(RuntimeError):
    """文件名不合法/找不到/文件过大等可控失败。"""


# ---------- 文件定位 ----------

def _dirs() -> tuple[tuple[str, Path], ...]:
    return (("对话", paths.SESSION_DIR), ("一次性", paths.ONESHOT_DIR))


def _resolve(name: str) -> Path:
    """只接受纯文件名(不带目录, 防路径穿越), 在会话目录里查找。"""
    raw = (name or "").strip().strip("\"'")
    if not raw:
        raise HistoryError("没有给会话文件名; 先用 list_sessions 看有哪些可读的会话。")
    if raw != Path(raw).name or raw.startswith("."):
        raise HistoryError("只接受文件名(如 session-20261102-134225-s1.jsonl), 不要带路径。")
    for _kind, directory in _dirs():
        candidate = directory / raw
        if candidate.is_file():
            return candidate
    raise HistoryError(f"找不到会话文件 {raw}; 用 list_sessions 看可读的列表。")


def _size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def _load(path: Path) -> tuple[dict, list[dict]]:
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise HistoryError(f"{path.name} 有 {_size(size)}, 超过 {_size(MAX_FILE_BYTES)} 的读取上限。")
    meta: dict = {}
    messages: list[dict] = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except ValueError:
                continue  # 落盘中断的半行: 跳过
            if not isinstance(item, dict):
                continue
            if "_meta" in item:
                meta = item.get("_meta") or {}
            elif item.get("role"):
                messages.append(item)
    return meta, messages


def _scan(path: Path, max_lines: int = 20000) -> tuple[dict, int, str]:
    """轻量扫描: 元信息 + 消息条数 + 首条玩家消息(截断)。"""
    meta: dict = {}
    count = 0
    first = ""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if count >= max_lines:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(item, dict):
                    continue
                if "_meta" in item:
                    meta = item.get("_meta") or {}
                    continue
                if not item.get("role"):
                    continue
                count += 1
                if not first and item.get("role") == "user":
                    text = Session._content_text(item.get("content")).strip().replace("\n", " ")
                    first = text[:60] + ("…" if len(text) > 60 else "")
    except OSError:
        pass
    return meta, count, first


# ---------- 对外 ----------

def list_sessions(limit: int = DEFAULT_LIST_LIMIT) -> str:
    """列出最近的落盘会话(默认 10 个), 含文件名/类型/模型/时间/条数/大小/首句。"""
    try:
        limit = max(1, min(int(limit or DEFAULT_LIST_LIMIT), 50))
    except (TypeError, ValueError):
        limit = DEFAULT_LIST_LIMIT
    entries = []
    for kind, directory in _dirs():
        if not directory.is_dir():
            continue
        for path in directory.glob("*.jsonl"):
            try:
                stat = path.stat()
            except OSError:
                continue
            entries.append((stat.st_mtime, kind, path, stat.st_size))
    if not entries:
        return "没有落盘的会话记录(会话结束/重启/清空后才会落盘)。"
    entries.sort(key=lambda t: t[0], reverse=True)
    rows = [f"最近 {min(limit, len(entries))} 个落盘会话(按修改时间, 新的在前):"]
    for _mtime, kind, path, size in entries[:limit]:
        meta, count, first = _scan(path)
        parts = [path.name, kind]
        if meta.get("model"):
            parts.append(str(meta["model"]))
        if meta.get("started"):
            parts.append(str(meta["started"]))
        parts.append(f"{count} 条")
        parts.append(_size(size))
        rows.append("- " + " · ".join(parts))
        if first:
            rows.append("    首句: " + first)
    rows.append('读某个会话: read_session(file="上面某一行的文件名")')
    return "\n".join(rows)


def _call_args(call: dict) -> dict:
    """工具调用的参数字典: 兼容 {arguments: ...} 与 {function: {arguments: ...}} 两种形状。"""
    raw = call.get("arguments")
    if raw is None and isinstance(call.get("function"), dict):
        raw = call["function"].get("arguments")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "{}")
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _speech(messages: list[dict]) -> list[str]:
    """从压缩后的消息里取出维克托真正说出口的话(send_chat_message, 含 ptc 内嵌)。"""
    out: list[str] = []
    for m in messages:
        for tc in m.get("tool_calls") or []:
            fn = tc.get("function") or {}
            name = fn.get("name")
            args = _call_args(tc)
            if name == "send_chat_message":
                text = str(args.get("text") or "").strip()
                if text:
                    out.append(text)
            elif name == "ptc":
                for call in args.get("calls") or []:
                    if not isinstance(call, dict):
                        continue
                    if str(call.get("tool") or call.get("name") or "") != "send_chat_message":
                        continue
                    text = str(_call_args(call).get("text") or "").strip()
                    if text:
                        out.append(text)
    return out


def _render(messages: list[dict]) -> str:
    """压缩后的消息 → 纯文本对话: 玩家消息原样(已带 "玩家名: " 前缀), 交互发言按顺序。"""
    lines: list[str] = []
    for m in messages:
        role = m.get("role")
        if role == "user":
            text = Session._content_text(m.get("content")).strip()
            if text:
                lines.append(text)
        elif role == "assistant":
            lines.extend("维克托: " + text for text in _speech([m]))
    return "\n".join(lines)


def _clip_middle(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = max_chars // 4
    tail = max_chars - head
    return (text[:head] + f"\n…(中间省略 {len(text) - max_chars} 字符)…\n" + text[-tail:])


def read_session(name: str, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """按文件名读一个会话, 返回压缩后的对话记录(工具调用/正文细节不保留)。"""
    try:
        try:
            max_chars = max(500, int(max_chars or DEFAULT_MAX_CHARS))
        except (TypeError, ValueError):
            max_chars = DEFAULT_MAX_CHARS
        path = _resolve(name)
        meta, messages = _load(path)
    except HistoryError as e:
        return f"[错误] {e}"
    except OSError as e:
        return f"[错误] 读不了会话文件: {e}"
    if not messages:
        return f"[会话] {path.name}\n[内容] 文件里没有对话消息(只有元信息或已损坏)。"
    kept, stats = Session.compact(messages)
    header = [
        f"[会话] {path.name} · 模型 {meta.get('model') or '?'} · 开始 {meta.get('started') or '?'}",
        f"[统计] 文件内 {len(messages)} 条消息 → 保留 {stats['kept_user']} 条玩家消息 / "
        f"{stats['kept_speech']} 句维克托发言(工具调用与正文已按「压缩」口径丢弃)",
    ]
    body = _render(kept).strip()
    if not body:
        return "\n".join(header) + "\n[内容] 这段会话里没有可读的对话。"
    return "\n".join(header) + "\n\n" + _clip_middle(body, max_chars)
