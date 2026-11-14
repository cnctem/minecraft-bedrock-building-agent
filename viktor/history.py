"""施工台账查询与会话历史定位读取。

三件事:

1. `find_builds` / `read_build` —— 查 `viktor/ledger.py` 的施工台账: 谁、为什么、造了什么、
   在哪个包围盒、多少格、什么材料、提交与撤销状态。它回答的是「今天造了什么」「上次那座塔
   在哪」这类问题, 不需要读会话正文(理由/坐标都是切创造与建造那一刻就记下来的结构化事实)。
2. `search_history` —— 跨会话文件按关键词找「当时聊了什么」, 回文件 + 对话行号。
3. `read_session` —— 按文件名只读一段对话(围绕关键词/行号), 不再整份渲染。

`list_sessions` 仍保留给脚本与排障用, 但不进模型工具表: 模型要定位直接 search_history 就行,
先列文件清单再逐个读是之前低效的根源。

会话落盘是 append-only 的 JSONL(首行 `_meta`, 之后每行一条消息), 对话口径复用
`Session.compact`: 只留玩家消息与维克托在游戏内说过的话(含 ptc 内嵌发言)。聊天记录本身没有
逐条时间戳, 所以对话只能按文件开始时间标注; 精确到分钟的时间在台账里。

依赖方向: history → ledger/paths/session(只用其 compact 与文本工具); 不 import bot_*。
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path

from . import ledger, paths
from .session import Session

DEFAULT_LIST_LIMIT = 10
DEFAULT_MAX_CHARS = 12000
DEFAULT_BUILD_LIMIT = 8
DEFAULT_SEARCH_LIMIT = 10
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_SEARCH_FILES = 400          # 一次检索最多扫多少个会话文件(按新到旧)
WORK_GAP_HOURS = 12             # 同名作品相隔多久还合并成一条(同一次施工的后续批次)
XZ_MERGE = 24                   # 同一段任务里, 水平相距多少格以内算同一件作品
PLAIN_ATTACH_MIN = 20           # 没有坐标的批次, 挂到多久以内的邻居批次所属作品
OPS_SHOWN = 5                   # 一条作品最多列几个批次
MATERIALS_SHOWN = 6
HISTORY_NOTE = "以上是历史记录, 之后可能已有改动(续建/改造前再查询现场)。"
_NAME_SPLIT_RE = re.compile(r"[-—–:：]")


class HistoryError(RuntimeError):
    """文件名不合法/找不到/文件过大等可控失败。"""


# ---------- 文件定位 ----------

def _dirs() -> tuple[tuple[str, Path], ...]:
    return (("对话", paths.SESSION_DIR), ("一次性", paths.ONESHOT_DIR))


def _resolve(name: str) -> Path:
    """只接受纯文件名(不带目录, 防路径穿越), 在会话目录里查找。"""
    raw = (name or "").strip().strip("\"'")
    if not raw:
        raise HistoryError("没有给会话文件名; 用 search_history 找要读哪一段(它会回文件名)。")
    if raw != Path(raw).name or raw.startswith("."):
        raise HistoryError("只接受文件名(如 session-20261102-134225-s1.jsonl), 不要带路径。")
    for _kind, directory in _dirs():
        candidate = directory / raw
        if candidate.is_file():
            return candidate
    raise HistoryError(f"找不到会话文件 {raw}; 用 search_history 查关键词定位。")


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


def _file_start(path: Path, meta: dict | None = None) -> datetime | None:
    return ledger._file_start(meta or {}, path)


# ---------- 会话文件清单(脚本/排障; 不进模型工具表) ----------

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


# ---------- 对话口径(压缩) ----------

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


def _dialogue(messages: list[dict]) -> list[str]:
    """压缩后的消息 → 逐行对话(玩家消息已带 "玩家名: " 前缀, 维克托发言加 "维克托: ")。"""
    lines: list[str] = []
    for m in messages:
        role = m.get("role")
        if role == "user":
            text = Session._content_text(m.get("content")).strip()
            if text:
                lines.append(text)
        elif role == "assistant":
            lines.extend("维克托: " + text for text in _speech([m]))
    return lines


def _session_file_name(session_id, session_start: str = "") -> str:
    """按会话 id + 开始时间找回落盘文件名(只读首行 _meta, 不整份加载)。"""
    if session_id is None:
        return ""
    want = (session_start or "")[:16]
    for _kind, directory in _dirs():
        if not directory.is_dir():
            continue
        for path in directory.glob(f"*-s{session_id}.jsonl"):
            if not want:
                return path.name
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    first = f.readline()
                meta = (json.loads(first) or {}).get("_meta") or {}
            except (OSError, ValueError):
                meta = {}
            started = str(meta.get("started") or "")
            if started.startswith(want) or _file_start(path).isoformat()[:16].startswith(want):
                return path.name
    return ""


def _clip_middle(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = max_chars // 4
    tail = max_chars - head
    return (text[:head] + f"\n…(中间省略 {len(text) - max_chars} 字符)…\n" + text[-tail:])


def _clip(text: str, n: int) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= n else text[:n - 1] + "…"


# ---------- 施工台账 ----------

_UNDOISH_RE = re.compile(r"撤销|undo|回滚|还原|撤回")


def _op_name_prefix(op: dict) -> str:
    """「埃菲尔铁塔-塔基」→「埃菲尔铁塔」。没有分隔符的名字不算命名分组(各批次是独立作品)。"""
    name = str(op.get("name") or "").strip()
    if not name:
        return ""
    parts = _NAME_SPLIT_RE.split(name, 1)
    if len(parts) < 2:
        return ""
    pre = parts[0].strip()
    return pre if len(pre) >= 2 else ""


def _bbox_of(op: dict):
    frm, to = op.get("from"), op.get("to")
    if not (frm and to and len(frm) == 3 and len(to) == 3):
        return None
    return list(frm), list(to)


def _bbox_overlap(a, b) -> int:
    """两个包围盒的交集体积(0 = 不相交)。"""
    vol = 1
    for i in range(3):
        lo = max(a[0][i], b[0][i])
        hi = min(a[1][i], b[1][i])
        if hi < lo:
            return 0
        vol *= hi - lo + 1
    return vol


def _xz_gap(a, b) -> int:
    """两个包围盒在水平面(x/z)上的间距, 相交为 0。

    同一座楼的基座(y 69~78)和塔冠(y 96~121)在竖直方向完全不相交, 但水平投影是同一块地;
    所以"是不是同一件东西"看水平距离而不是三维包围盒相交。
    """
    gap = 0
    for i in (0, 2):
        gap = max(gap, a[0][i] - b[1][i], b[0][i] - a[1][i], 0)
    return gap


def _name_conflict(pre: str, other: str) -> bool:
    """两个命名前缀互不包含 → 是两件不同的东西(「克宫-城墙」不能并进「天安门」)。

    空前缀(未命名批次)不算冲突: 先造了一堆没名字的模块、后面才起名, 仍应归成一件。
    """
    if not pre or not other:
        return False
    return not (pre.startswith(other) or other.startswith(pre))


def _work_title(w: dict) -> str:
    """作品标题: 命名前缀 → （整段任务就是这一件时）切创造的理由 → 最早那个批次的名字。"""
    key = (w.get("name_prefix") or "").strip()
    if not key and w.get("whole") and w["reasons"]:
        key = w["reasons"][0]
    if not key:
        names = [str(o.get("name") or "").strip() for o in w["ops"]]
        names = [n for n in names if n]
        key = names[0] if names else (w["reasons"][0] if w["reasons"] else "未命名")
    key = key.strip() or "未命名"
    return key if len(key) <= 28 else key[:27] + "…"


def _works(eps: list[dict], group: bool = True) -> list[dict]:
    """episode → 「作品」。

    一个创造 episode 里可能有好几件东西(同一个理由下交替施工、或一口气造一片), 所以不能
    按"一次切创造 = 一个作品"硬切。归属顺序:

      1. 名字前缀一致(「埃菲尔铁塔-塔基/塔身」) → 同一件;
      2. 名字没有前缀时看包围盒是否相交 → 同一件(白宫的 17 个子步骤都在同一块地基上);
      3. 都没有(如只有提交记录的批次) → 归到同一 episode 里最近的那件。

    距离用时间窗 `WORK_GAP_HOURS` 限制, 免得几天后再造同名建筑被并进旧作品;
    交叉施工(甲→乙→甲)靠"在原作品的时间窗内"回到原作品, 不会拆成两件。
    """
    works: list[dict] = []
    boxes: list[tuple] = []       # (work, (x0,y0,z0), (x1,y1,z1)) 供空间索引
    grid: dict[tuple, list] = {}  # (cx,cz) → 上面列表的下标, 避免每次 O(所有批次)
    by_prefix: dict[str, list] = {}  # 命名前缀 → 作品
    by_ep: dict[str, list] = {}      # episode → 涉及它的作品

    def new_work(op: dict, ep: dict, ts: str, ts_dt, strong: set | None = None) -> dict:
        pre = _op_name_prefix(op)
        w = {"name_prefix": pre, "strong_prefix": pre if pre in (strong or ()) else "",
             "ts_start": ts, "ts_end": ts,
             "_ts_end": ts_dt, "ops": [], "eps": [], "players": [], "reasons": [],
             "triggers": [], "closed": [], "whole": False}
        works.append(w)
        if w["name_prefix"]:
            by_prefix.setdefault(w["name_prefix"], []).append(w)
        return w

    def index_box(w: dict, box) -> None:
        i = len(boxes)
        boxes.append((w, box[0], box[1]))
        for cx in range(box[0][0] // 64, box[1][0] // 64 + 1):
            for cz in range(box[0][2] // 64, box[1][2] // 64 + 1):
                grid.setdefault((cx, cz), []).append(i)

    def gap_ok(w: dict, ts_dt) -> bool:
        # 时间戳解析很贵(datetime.fromisoformat): 每个作品缓存一份, 每个批次只解析一次
        end = w["_ts_end"]
        if end is None or ts_dt is None:
            return True
        return abs((ts_dt - end).total_seconds()) <= WORK_GAP_HOURS * 3600

    def touch(w: dict, ts: str, ts_dt, ep: dict) -> None:
        if ts and (not w["ts_start"] or ts < w["ts_start"]):
            w["ts_start"] = ts
        if ts and ts > w["ts_end"]:
            w["ts_end"] = ts
        if ts_dt and (w["_ts_end"] is None or ts_dt > w["_ts_end"]):
            w["_ts_end"] = ts_dt
        if ep.get("eid") and ep["eid"] not in w["eps"]:
            w["eps"].append(ep["eid"])
        if ep.get("player") and ep["player"] not in w["players"]:
            w["players"].append(ep["player"])
        for key, field in (("reasons", "reason"), ("triggers", "trigger")):
            text = (ep.get(field) or "").strip()
            if text and text not in w[key]:
                w[key].append(text)
        if ep.get("closed"):
            w["closed"].append(ep["closed"])

    def match(op: dict, ep: dict, ts_dt, strong: set | None = None):
        pre = _op_name_prefix(op)
        strong = strong or set()
        strong_pre = pre if pre in strong else ""
        if pre:
            # 命名前缀可以跨 episode(主线造完、下一条"加细节"还是同一件作品)
            named = [w for p, ws in by_prefix.items()
                     for w in ws
                     if (pre.startswith(p) or p.startswith(pre)) and gap_ok(w, ts_dt)]
            if named:
                return max(named, key=lambda w: w["ts_end"])
        box = _bbox_of(op)
        if box:
            # 空间距离只在"同一段任务"里作数: 同一个 episode 的多个子步骤(白宫 17 批),
            # 或跨 episode 但理由相同(同一件事的续做)。否则同一块地皮上先后造的不同东西
            # (平整地形 / 斯大林主楼 / 白宫)会被并成一条, 位置与理由都会失真。
            mine = {ep.get("reason") or ""}
            x0, y0, z0 = box[0]
            x1, y1, z1 = box[1]
            seen: set[int] = set()
            best, best_key = None, None
            for cx in range((x0 - XZ_MERGE) // 64, (x1 + XZ_MERGE) // 64 + 1):
                for cz in range((z0 - XZ_MERGE) // 64, (z1 + XZ_MERGE) // 64 + 1):
                    for i in grid.get((cx, cz), ()):
                        if i in seen:
                            continue
                        seen.add(i)
                        w, b0, b1 = boxes[i]
                        if not (ep.get("eid") in w["eps"] or (mine & set(w["reasons"]))):
                            continue
                        # 真的和已有作品占同一块空间(哪怕名字不同): 就是那件东西的一部分
                        # ——「航站楼」里的「布光-西段」「外立面修-中段」属于航站楼。
                        vol = _bbox_overlap(box, (b0, b1))
                        if vol:
                            key = (0, -vol)
                        else:
                            if _name_conflict(strong_pre, w["strong_prefix"]):
                                continue
                            gx = max(b0[0] - x1, x0 - b1[0], 0)
                            gz = max(b0[2] - z1, z0 - b1[2], 0)
                            gap = gx if gx > gz else gz
                            if gap > XZ_MERGE:
                                continue
                            key = (1, gap)
                        if best_key is None or key < best_key:
                            best, best_key = w, key
            if best is not None:
                return best
        # 没有几何信息的批次(只有提交/撤销): 归到同一 episode 里最近的作品
        if not box and ep.get("eid"):
            same = [w for w in by_ep.get(ep["eid"], ()) if gap_ok(w, ts_dt)]
            if same:
                return max(same, key=lambda w: w["ts_end"])
        return None

    ep_op_ids: dict[str, set] = {}
    for ep in sorted(eps, key=lambda e: e.get("ts") or ""):
        ts = ep.get("ts") or ""
        ts_dt = ledger._parse_ts(ts)
        # 纯撤销任务(没有自己的批次, 只是把上一批撤掉): 效果已落在原批次的「已撤销」上, 不单列
        if not ep["ops"] and _UNDOISH_RE.search(ep.get("reason") or ""):
            continue
        if not ep["ops"]:
            w = None
            if group:
                reason = ep.get("reason") or ""
                cands = [x for x in works if x["reasons"] and x["reasons"][0] == reason
                         and gap_ok(x, ts_dt)]
                w = max(cands, key=lambda x: x["ts_end"]) if cands else None
            if w is None:
                w = new_work({}, ep, ts, ts_dt)
            touch(w, ts, ts_dt, ep)
            continue
        ep_op_ids[ep.get("eid") or ""] = {id(o) for o in ep["ops"]}
        # 「强前缀」= 这段任务里被两个以上批次共用的名字前缀(埃菲尔铁塔/克宫/天安门);
        # 只出现一次的(推平A/客舱补丁)不算独立作品身份, 否则一条船会被拆成好几条.
        pre_counts: dict[str, int] = {}
        for o in ep["ops"]:
            pre = _op_name_prefix(o)
            if pre:
                pre_counts[pre] = pre_counts.get(pre, 0) + 1
        strong = {k for k, v in pre_counts.items() if v >= 2}

        def place(op, w) -> None:
            w["ops"].append(op)
            pre = _op_name_prefix(op)
            if pre and not w["name_prefix"]:
                w["name_prefix"] = pre
                by_prefix.setdefault(pre, []).append(w)
            if pre in strong and not w["strong_prefix"]:
                # 强前缀 = 这件作品的真名。先被"清理a-b区域"这类单批次占用的作品,
                # 在第一个「克宫-xx」进来时改名, 免得整座克宫挂在一条清理记录名下。
                w["strong_prefix"] = pre
                w["name_prefix"] = pre
                by_prefix.setdefault(pre, []).append(w)
            box = _bbox_of(op)
            if box:
                index_box(w, box)
            eid = ep.get("eid") or ""
            if eid and w not in by_ep.setdefault(eid, []):
                by_ep[eid].append(w)
            op_dt = ledger._parse_ts(op.get("ts") or "") or ts_dt
            touch(w, op.get("ts") or ts, ts_dt, ep)

        # 第一趟: 有坐标的批次按命名前缀 / 空间距离归并
        placed: list[tuple] = []
        for op in ep["ops"]:
            if not _bbox_of(op):
                continue
            op_dt = ledger._parse_ts(op.get("ts") or "") or ts_dt
            w = match(op, ep, op_dt, strong) if group else None
            if w is None:
                w = new_work(op, ep, op.get("ts") or ts, op_dt, strong)
            place(op, w)
            placed.append((op_dt, op, w))
        # 第二趟: 只剩提交/撤销记录、没有坐标的批次。
        # 先按名字前缀找作品(克宫-69 即使紧挨着纪念碑批次, 也回克宫), 再退到时间上最近的
        # 已归属批次; 前缀冲突或相距太远就单列。
        for op in ep["ops"]:
            if _bbox_of(op):
                continue
            op_dt = ledger._parse_ts(op.get("ts") or "") or ts_dt
            pre = _op_name_prefix(op)
            strong_pre = pre if pre in strong else ""
            best, best_gap = None, None
            if pre:
                named = [w for w in works
                         if w["name_prefix"]
                         and (pre.startswith(w["name_prefix"])
                              or w["name_prefix"].startswith(pre))]
                if named:
                    best = max(named, key=lambda w: w["ts_end"])
            if best is None:
                for dt, _other, w in placed:
                    if _name_conflict(strong_pre, w["strong_prefix"]):
                        continue
                    sec = abs((op_dt - dt).total_seconds()) if (op_dt and dt) else 0
                    if sec <= PLAIN_ATTACH_MIN * 60 and (best_gap is None or sec < best_gap):
                        best, best_gap = w, sec
            if best is None and group:
                same = [w for w in by_ep.get(ep.get("eid") or "", ())
                        if not _name_conflict(strong_pre, w["strong_prefix"])]
                if len(same) == 1:
                    best = same[0]
            w = best or new_work(op, ep, op.get("ts") or ts, op_dt, strong)
            place(op, w)
    # 收尾: 判断这件作品是否吃下了它涉及的所有 episode 的全部批次
    # (是 → 可以用 episode 理由当标题; 否则用批次名/命名前缀)
    for w in works:
        covered = {id(o) for o in w["ops"]}
        w["whole"] = all(covered >= ep_op_ids[e] for e in w["eps"] if e in ep_op_ids)
    works.sort(key=lambda w: w["ts_start"] or "")
    return works


def _gap_hours(a: str, b: str) -> float:
    da, db = ledger._parse_ts(a), ledger._parse_ts(b)
    if not da or not db:
        return 0.0
    return abs((db - da).total_seconds()) / 3600


def _work_state(w: dict) -> str:
    committed = [o for o in w["ops"] if o.get("committed")]
    live = [o for o in committed if not o.get("undone")]
    if live:
        return "built"
    if committed:
        return "undone"
    return "draft" if w["ops"] else "cmd"


def _work_haystack(w: dict) -> str:
    parts = [w.get("name_prefix") or "", _work_title(w)]
    parts += w.get("reasons") or []
    parts += w.get("triggers") or []
    parts += w.get("players") or []
    parts += w.get("eps") or []
    for op in w["ops"]:
        parts += [op.get("jid") or "", op.get("name") or "", op.get("program") or "",
                  op.get("facing") or ""]
        parts += list((op.get("materials") or {}).keys())
        parts += list(op.get("blocks") or [])
    return " \n".join(parts).casefold()


def _work_bounds(w: dict) -> tuple[list | None, list | None, str]:
    """作品的包围盒: 优先只算"还在场"的已提交批次; 全撤销了就标注出来。"""
    committed = [o for o in w["ops"]
                 if o.get("committed") and not o.get("undone")
                 and o.get("from") and o.get("to")]
    pool = committed or [o for o in w["ops"] if o.get("from") and o.get("to")]
    if not pool:
        return None, None, ""
    frm = [min(o["from"][i] for o in pool) for i in range(3)]
    to = [max(o["to"][i] for o in pool) for i in range(3)]
    return frm, to, ("built" if committed else "history")


def _op_visible(op: dict) -> bool:
    """没有任何几何/数量信息的批次(只会出现在历史撤销记录里)不单列, 免得满屏 jid。"""
    return bool(op.get("from") or op.get("to") or op.get("name")
                or (op.get("changed") or 0) or (op.get("cells") or 0)
                or (op.get("restored") or 0))


def _op_state(op: dict) -> str:
    if op.get("undone"):
        return f"已撤销(还原 {op.get('restored') or 0} 格)"
    if op.get("committed"):
        verify = op.get("verify") or {}
        if verify.get("mismatch"):
            return f"已提交({verify['mismatch']}格不符)"
        return "已提交"
    return "未提交(仅预览)"


def _fmt_bounds(op: dict) -> str:
    frm, to = op.get("from"), op.get("to")
    if not (frm and to):
        return ""
    size = op.get("size") or [to[i] - frm[i] + 1 for i in range(3)]
    return (f"({frm[0]},{frm[1]},{frm[2]})..({to[0]},{to[1]},{to[2]}) "
            f"{size[0]}×{size[1]}×{size[2]}")


def _fmt_when(start: str, end: str, now: datetime) -> str:
    """时间片段: 今天/昨天只显示时分, 更早的显示 MM-DD HH:MM。"""
    day = ledger.day_label(start, now)
    st = ledger.fmt_ts(start)
    if day in ("今天", "昨天", "前天"):
        when = f"{day} {st[11:16]}"
    else:
        when = st[5:16]
    if end and end[:16] != start[:16]:
        tail = ledger.fmt_ts(end)
        if day in ("今天", "昨天", "前天") and tail[:10] == st[:10]:
            when += f"~{tail[11:16]}"
        else:
            when += f"~{tail[5:16]}"
    return when


def _fmt_work(idx: int, w: dict, now: datetime) -> list[str]:
    state = _work_state(w)
    tag = {"built": "", "undone": " [已全部撤销]", "draft": " [未提交]",
           "cmd": " [无建造批次]"}[state]
    who = ", ".join(w["players"]) or "?"
    when = _fmt_when(w["ts_start"], w["ts_end"], now)
    title = _work_title(w)
    lines = [f"[{idx}] {when} · {who} · {title}{tag}"]

    # 标题本来就是理由时不再重复一遍, 改成给玩家原话(更有信息量)
    reasons = [r for r in w["reasons"][:3] if r.strip() != title.strip()]
    if reasons:
        lines.append("    理由: " + _clip(" / ".join(reasons), 180))
    elif w["triggers"]:
        lines.append("    触发: " + _clip(w["triggers"][0], 180))

    visible = [o for o in w["ops"] if _op_visible(o)]
    for i, op in enumerate(visible):
        if i >= OPS_SHOWN:
            lines.append(f"    …另 {len(visible) - OPS_SHOWN} 个批次")
            break
        where = _fmt_bounds(op)
        cells = op.get("changed") if op.get("committed") else op.get("cells")
        name = op.get("name") or ("撤销操作" if op.get("undone") else "未命名批次")
        bits = [name, where,
                (f"{cells} 格" if cells else ""), _op_state(op)]
        lines.append("    批次: " + " · ".join(b for b in bits if b))

    live = [o for o in w["ops"] if o.get("committed") and not o.get("undone")]
    undone = [o for o in w["ops"] if o.get("undone")]
    placed = sum(o.get("changed") or o.get("cells") or 0 for o in live)
    restored = sum(o.get("restored") or 0 for o in undone)
    total = placed + restored
    if total:
        extra = (f", 其中已撤销 {restored} 格(现存约 {total - restored} 格)"
                 if restored else "")
        lines.append(f"    合计: 累计写入 {total} 格{extra}")

    counts: dict[str, int] = {}
    blocks: list[str] = []
    for op in w["ops"]:
        for name, n in (op.get("materials") or {}).items():
            counts[name] = counts.get(name, 0) + int(n or 0)
        for b in op.get("blocks") or []:
            if b not in blocks:
                blocks.append(b)
    if counts:
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:MATERIALS_SHOWN]
        lines.append("    材料: " + ", ".join(f"{n} {c}" for n, c in top))
    elif blocks:
        lines.append("    材料(程序里用到的): " + ", ".join(blocks[:MATERIALS_SHOWN]))
    frm, to, _kind = _work_bounds(w)
    if frm and to:
        center = [(frm[i] + to[i]) // 2 for i in range(3)]
        note = "(已撤销, 以下为当时的范围)" if state == "undone" else ""
        lines.append(f"    位置: ({frm[0]},{frm[1]},{frm[2]})..({to[0]},{to[1]},{to[2]}) "
                     f"中心约 ({center[0]},{center[1]},{center[2]}){note}")
    eids = [e for e in w["eps"] if e]
    if eids:
        lines.append(f'    台账: {", ".join(eids[:6])} → read_build("{eids[0]}")')
    return lines


def find_builds(query: str = "", since: str = "", until: str = "", player: str = "",
                limit: int = DEFAULT_BUILD_LIMIT, state: str = "built",
                group: bool = True) -> str:
    """查施工台账: 关键词/时间段/玩家过滤, 返回作品清单(含理由、包围盒、格数、材料、状态)。"""
    now = datetime.now()
    try:
        limit = max(1, min(int(limit or DEFAULT_BUILD_LIMIT), 30))
    except (TypeError, ValueError):
        limit = DEFAULT_BUILD_LIMIT
    state = (state or "built").strip().lower()
    if state not in ("built", "all", "draft", "undone", "cmd"):
        return "[错误] state 只能是 built(默认)/all/draft/undone/cmd。"
    try:
        t0 = ledger.parse_when(since, now)
        t1 = ledger.parse_when(until, now, end=True)
    except ValueError as e:
        return f"[错误] {e}"
    eps = ledger.episodes()
    if not eps:
        return ("台账还是空的: 还没进入过创造模式, 或历史还没回填"
                "(python3 tools/backfill_build_ledger.py)。\n"
                "（若刚重启且台账文件被删, 历史施工记录不会自动恢复; 现场状态可以照常用查询工具看。）")
    works = _works(eps, group=bool(group))
    q = (query or "").strip().casefold()
    picked = []
    for w in works:
        start = ledger._parse_ts(w["ts_start"])
        end = ledger._parse_ts(w["ts_end"] or w["ts_start"])
        if t0 and end and end < t0:
            continue
        if t1 and start and start >= t1:
            continue
        if player:
            p = player.strip().casefold()
            if not any(p in (x or "").casefold() for x in w["players"]):
                continue
        st = _work_state(w)
        if state != "all" and st != state:
            continue
        if q and q not in _work_haystack(w):
            continue
        picked.append(w)
    picked.sort(key=lambda w: w["ts_start"] or "", reverse=True)
    picked = picked[:limit]
    if not picked:
        cond = "、".join(x for x in (f'关键词 "{query}"' if query else "",
                                    f"since {since}" if since else "",
                                    f"until {until}" if until else "",
                                    f"玩家 {player}" if player else "",
                                    f"state {state}") if x)
        return (f"台账里没有符合条件的施工记录({cond or '无过滤'})。\n"
                "可以换短一点的关键词(如只写“塔”“白宫”)、放宽 since, "
                "或 state=all 看未提交/已撤销的(这类任务可能只用了 fill 指令, 没有建造批次)。")
    rows = [f"施工台账: {len(picked)} 条(新的在前; 时间为批次时间, 精确到分钟)"]
    for i, w in enumerate(picked, 1):
        rows.extend(_fmt_work(i, w, now))
    rows.append(HISTORY_NOTE)
    return "\n".join(rows)


def _program_text(rel_path: str, max_lines: int) -> tuple[str, int]:
    if not rel_path:
        return "", 0
    p = Path(rel_path)
    if not p.is_absolute():
        p = paths.BASE_DIR / p
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "", 0
    return "\n".join(lines[:max_lines]), len(lines)


def read_build(ref: str, program_lines: int = 40) -> str:
    """按台账编号(e00012)或批次 jid 读一次施工的细节(含程序源码开头)。"""
    try:
        program_lines = max(0, min(int(program_lines or 0), 200))
    except (TypeError, ValueError):
        program_lines = 40
    key = (ref or "").strip().strip('"\'')
    if not key:
        return "[错误] 没给台账编号; 先用 find_builds 查, 结果里每行末尾就是编号。"
    if re.fullmatch(r"\d+", key):
        key = "e" + key.zfill(5)
    elif re.fullmatch(r"e\d+", key, re.I):
        key = "e" + key[1:].zfill(5)
    eps = ledger.episodes()
    matches = [e for e in eps if e["eid"] == key]
    focus = ""
    if not matches:
        matches = [e for e in eps if any(o.get("jid") == key for o in e["ops"])]
        focus = key
    if not matches:
        return (f"[错误] 台账里找不到 {ref}; 先用 find_builds 查(编号形如 e00012 或批次 jid)。")
    ep = matches[0]
    # 源码只展开一个批次: 指定 jid 时展开它, 否则展开最后(最近)有源码的批次,
    # 免得一个工程 17 个批次每个都附 40 行把上下文顶爆。其余批次给路径按需再查。
    with_prog = [o for o in ep["ops"] if o.get("program")]
    expand_jid = focus or (with_prog[-1]["jid"] if with_prog else "")
    now = datetime.now()
    start = ep["ts"]
    span = (ledger.fmt_ts(ep["closed"])[11:] if ep.get("closed")
            else "未记录结束(不影响已记批次)")
    head = [f"[台账] {ep['eid']} · {ledger.day_label(start, now)} "
            f"{ledger.fmt_ts(start)}~{span} · {ep['mode']} · {ep['player'] or '?'}"]
    sfile = ep.get("sfile") or _session_file_name(ep.get("session"),
                                                ep.get("session_start"))
    head.append(f"[会话] {sfile or '(已不在 logs/ 里)'}"
                f" · 会话开始 {ledger.fmt_ts(ep.get('session_start'))}")
    if ep.get("reason"):
        head.append("[理由] " + _clip(ep["reason"], 300))
    if ep.get("trigger"):
        head.append("[触发] " + _clip(ep["trigger"], 300))
    rows = list(head)
    for i, op in enumerate(ep["ops"], 1):
        bits = [f"[批次 {i}/{len(ep['ops'])}] {op.get('jid') or '-'}",
                f"「{op.get('name') or '无预览记录'}」"]
        if op.get("facing"):
            bits.append(f"facing {op['facing']}")
        if op.get("origin"):
            bits.append(f"origin {tuple(op['origin'])}")
        rows.append(" · ".join(bits))
        where = _fmt_bounds(op)
        if where:
            rows.append(f"   包围盒 {where} · {op.get('cells') or 0} 格 · "
                        f"{op.get('palette') or 0} 种方块")
        if op.get("materials"):
            rows.append("   材料: " + ", ".join(
                f"{n} {c}" for n, c in list(op["materials"].items())[:MATERIALS_SHOWN]))
        state = _op_state(op)
        if op.get("committed"):
            verify = op.get("verify") or {}
            state += (f"; 写入 {op.get('changed') or 0} 格/{op.get('boxes') or 0} 批, "
                      + ("校验全部正确" if not verify.get("mismatch")
                         else f"校验 {verify['mismatch']} 格不符(空洞 "
                              f"{verify.get('holes', 0)}, 放错 {verify.get('wrong', 0)})"))
        rows.append("   状态: " + state)
        if op.get("program"):
            if program_lines and op.get("jid") == expand_jid:
                code, total = _program_text(op["program"], program_lines)
                if code:
                    rows.append(f"   程序: {op['program']} (共 {total} 行, "
                                f"显示前 {min(program_lines, total)} 行)")
                    rows.append("[程序开始]")
                    rows.append(code)
                    rows.append("[程序结束]")
            else:
                rows.append(f"   程序: {op['program']} (共 {op.get('program_lines') or 0} 行; "
                            f'要源码就 read_build("{op.get("jid")}") )')
    rows.append("[历史] " + HISTORY_NOTE.replace("以上是历史记录, ", ""))
    return "\n".join(rows)


# ---------- 聊天记录定位 ----------

def search_history(query: str, since: str = "", file: str = "",
                   limit: int = DEFAULT_SEARCH_LIMIT) -> str:
    """跨会话文件按关键词找对话行, 回「文件 + 对话行号」, 供 read_session(around=) 精读。"""
    q = (query or "").strip()
    if not q:
        return "[错误] 要给关键词(比如“埃菲尔铁塔”“白桦林”)。"
    try:
        limit = max(1, min(int(limit or DEFAULT_SEARCH_LIMIT), 40))
    except (TypeError, ValueError):
        limit = DEFAULT_SEARCH_LIMIT
    try:
        t0 = ledger.parse_when(since)
    except ValueError as e:
        return f"[错误] {e}"
    if file:
        try:
            candidates = [(0.0, _resolve(file))]
        except HistoryError as e:
            return f"[错误] {e}"
    else:
        entries = []
        for _kind, directory in _dirs():
            if not directory.is_dir():
                continue
            for p in directory.glob("*.jsonl"):
                try:
                    entries.append((p.stat().st_mtime, p))
                except OSError:
                    continue
        entries.sort(key=lambda t: -t[0])
        candidates = entries[:MAX_SEARCH_FILES]
    needle = q.casefold()
    needle_b = q.encode("utf-8")
    ascii_q = q.isascii()
    hits: list[tuple[Path, int, str, datetime | None]] = []
    seen: set[str] = set()
    scanned = 0
    for _mtime, path in candidates:
        start = _file_start(path)
        if t0 and start and start < t0:
            continue
        # 先用字节预筛(不解码/不 casefold 整个文件): 657 个文件约 160 ms;
        # 命中才解析成对话, 避免为了找一句话把 100 MB 会话全解一遍。
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            blob = path.read_bytes()
        except OSError:
            continue
        if needle_b not in blob and (not ascii_q or needle_b.lower() not in blob.lower()):
            continue
        scanned += 1
        try:
            meta, messages = _load(path)
        except (HistoryError, OSError):
            continue
        lines = _dialogue(messages)
        for idx, text in enumerate(lines, 1):
            if needle not in text.casefold():
                continue
            key = text.strip()
            if key in seen:
                continue      # 压缩/恢复会话会让同一句出现在多个文件里, 只报最新的那次
            seen.add(key)
            hits.append((path, idx, text, _file_start(path, meta)))
            if len(hits) >= limit:
                break
        if len(hits) >= limit:
            break
    if not hits:
        return (f'没有在会话记录里找到 "{q}"' + (f"(since {since})" if since else "") + "。\n"
                "先确认关键词是否接近原话(可以只用一个词), 或去掉 since 再试; "
                "问建造/位置这类结构化历史, 用 find_builds 更准。")
    rows = [f'命中 {len(hits)} 处(扫了 {scanned} 个含关键词的会话文件; 对话行号用于精读):']
    for path, idx, text, start in hits:
        day = f"{start:%m-%d}" if start else "?"
        rows.append(f"- {path.name}#{idx} [{day}] {_clip(text, 160)}")
    rows.append('读命中处附近: read_session(file="文件名", around=行号, window=3)')
    return "\n".join(rows)


def read_session(name: str, contains: str = "", around=None, window: int = 3,
                 max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """按文件名读会话的对话记录; 给 contains/around 时只读命中附近的片段。"""
    try:
        try:
            max_chars = max(500, int(max_chars or DEFAULT_MAX_CHARS))
        except (TypeError, ValueError):
            max_chars = DEFAULT_MAX_CHARS
        try:
            window = max(0, min(int(window if window is not None else 3), 20))
        except (TypeError, ValueError):
            window = 3
        anchor = None
        if around not in (None, ""):
            anchor = int(str(around).strip().lstrip("#"))
        path = _resolve(name)
        meta, messages = _load(path)
    except (HistoryError, ValueError) as e:
        return f"[错误] {e}"
    except OSError as e:
        return f"[错误] 读不了会话文件: {e}"
    if not messages:
        return f"[会话] {path.name}\n[内容] 文件里没有对话消息(只有元信息或已损坏)。"
    kept, stats = Session.compact(messages)
    lines = _dialogue(kept)
    header = [
        f"[会话] {path.name} · 模型 {meta.get('model') or '?'} · "
        f"开始 {meta.get('started') or ledger.fmt_ts(_file_start(path, meta))} · "
        f"对话 {len(lines)} 行",
        f"[统计] 文件内 {len(messages)} 条消息 → 保留 {stats['kept_user']} 条玩家消息 / "
        f"{stats['kept_speech']} 句维克托发言(工具调用与正文已按「压缩」口径丢弃)",
    ]
    needle = (contains or "").strip().casefold()
    idxs: list[int] = []
    if needle:
        idxs = [i for i, text in enumerate(lines, 1) if needle in text.casefold()]
        if not idxs:
            return ("\n".join(header)
                    + f'\n[内容] 这份会话里没有含 "{contains}" 的对话; 换关键词或用 search_history。')
    if anchor is not None:
        if anchor < 1 or anchor > len(lines):
            return "\n".join(header) + f"\n[错误] around={anchor} 超出范围(1~{len(lines)})。"
        idxs.append(anchor)
    if idxs:
        keep: list[int] = []
        for i in idxs:
            for j in range(max(1, i - window), min(len(lines), i + window) + 1):
                if j not in keep:
                    keep.append(j)
        keep.sort()
        blocks: list[str] = []
        prev = 0
        for i in keep:
            if i - prev > 1:
                blocks.append(f"…(省略第 {prev + 1}~{i - 1} 行)…")
            blocks.append(f"#{i} {lines[i - 1]}")
            prev = i
        if prev < len(lines):
            blocks.append(f"…(省略第 {prev + 1}~{len(lines)} 行)…")
        header.append("[定位] 命中行 " + ", ".join(f"#{i}" for i in sorted(set(idxs)))
                      + f" · 每处前后各 {window} 行")
        body = "\n".join(blocks)
    else:
        body = "\n".join(f"#{i} {text}" for i, text in enumerate(lines, 1))
    body = body.strip()
    if not body:
        return "\n".join(header) + "\n[内容] 这段会话里没有可读的对话。"
    return "\n".join(header) + "\n\n" + _clip_middle(body, max_chars)
