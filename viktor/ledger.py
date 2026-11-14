"""施工台账(build ledger): 把「切创造 → 建造批次 → 提交/撤销」写成 append-only JSONL。

为什么需要它: 这些信息在会话 JSONL 里只存在于工具调用与结果文本中, 「压缩」口径读历史时
会被整段丢掉; 按文件读又贵又重复(恢复会话会把同一批工具调用在原文件与新文件里各落一份)。
台账在写入那一刻就把结构化事实存下来 —— 谁、为什么(切创造的理由 + 触发原话)、造了什么、
在哪个包围盒、多少格、什么材料、提交校验如何、后来有没有撤销 —— 一次查询就能回答
「今天造了什么 / 上次那座塔在哪」, 不用扫 100 MB 会话文件, 也不靠模型事后生成摘要。

一条台账 = 一行 JSON, 两种 kind:

  episode  action=open/close   一次"进入创造模式"(= 一段施工任务, 以理由为标题)
  op       action=preview/commit/undo  一次建造批次(以 jid 为幂等键)

字段(缺省即没有该项):
  episode: eid, ts, mode, player, session, session_start, reason, trigger, sfile
  op:      eid, ts, jid, name, origin, facing, from/to/size, cells, palette, materials,
           program(相对路径), program_lines, changed, boxes, verify, restored, undoOf

依赖方向: ledger → paths; 不 import bot_* / session(回填只用本模块的容错解析)。
"""
import json
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path

from . import paths

VERSION = 1
MAX_MATERIALS = 16          # 台账里每种批次最多记多少种材料(按用量降序)
MAX_FILE_BYTES = 32 * 1024 * 1024

_TS_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?$")
_DAY_RE = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$")
_MD_RE = re.compile(r"^(\d{1,2})[-/.](\d{1,2})$")
_REL_RE = re.compile(r"^(\d+)\s*(d|day|days|天|日|h|hour|hours|小时|m|min|minutes|分钟)$")
_FNAME_TIME_RE = re.compile(r"(\d{8})-(\d{6})")       # session-YYYYmmdd-HHMMSS-sN.jsonl
_LOG_LINE_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")
_LOG_BUILD_RE = re.compile(r"\[建造\] (预览|提交|撤销) (\S+)")
_LOG_PREVIEW_RE = re.compile(r"\[建造\] 预览 (\S+) (.*?) \((\d+), (\d+), (\d+)\) (\d+)格")
_BOX_RE = re.compile(r"包围盒 \((-?\d+), (-?\d+), (-?\d+)\)\.\."
                     r"\((-?\d+), (-?\d+), (-?\d+)\) = (\d+)×(\d+)×(\d+)")
_PREVIEW_ID_RE = re.compile(r"^预览 (\S+)")
_CELLS_RE = re.compile(r"将写入 (\d+) 格, (\d+) 种方块")
_COMMIT_RE = re.compile(r"提交 (\S+): 写入 (\d+) 格, (\d+) 批")
_UNDO_RE = re.compile(r"^已撤销 (\S+): 还原 (\d+) 格")
_MISMATCH_RE = re.compile(r"校验: (\d+) 格不符(?:\(空洞 (\d+), 放错 (\d+))?")

WEEKDAY_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


# ---------- 路径 / 时间 ----------

def ledger_path() -> Path:
    return paths.LEDGER_PATH


def program_dir() -> Path:
    return paths.PROGRAM_DIR


def now_ts() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_ts(text) -> datetime | None:
    try:
        return datetime.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None


def fmt_ts(ts, with_weekday: bool = False) -> str:
    dt = _parse_ts(ts)
    if dt is None:
        return str(ts or "?")
    return f"{dt:%Y-%m-%d %H:%M}" + (f" {WEEKDAY_CN[dt.weekday()]}" if with_weekday else "")


def day_label(ts, now: datetime | None = None) -> str:
    """把时间搓成「今天/昨天/前天/MM-DD」, 便于模型和玩家对齐。"""
    dt = _parse_ts(ts)
    if dt is None:
        return "?"
    now = now or datetime.now()
    delta = (now.date() - dt.date()).days
    if delta == 0:
        return "今天"
    if delta == 1:
        return "昨天"
    if delta == 2:
        return "前天"
    return f"{dt:%m-%d}"


def now_line(now: datetime | None = None) -> str:
    """给系统注记用的一行绝对时间(模型默认不知道"现在几点", 相对时间也算不准)。"""
    now = now or datetime.now()
    off = now.astimezone().utcoffset()
    tz = ""
    if off is not None:
        hours = off.total_seconds() / 3600
        tz = f" (UTC{hours:+g})"
    return f"{now:%Y-%m-%d %H:%M} {WEEKDAY_CN[now.weekday()]}{tz}"


def parse_when(text, now: datetime | None = None, end: bool = False) -> datetime | None:
    """把「today/今天/昨天/3天/7d/2小时/2026-11-01/11-01」解析成时间点。

    end=True 用于 until: 只给日期时覆盖到当天结束(次日 00:00, 由调用方按 <= 之外处理)。
    空串返回 None; 认不出来抛 ValueError(让工具回一句可读的错误, 而不是静默不过滤)。
    """
    s = str(text or "").strip().lower().replace(" ", "")
    if not s:
        return None
    now = now or datetime.now()
    if s in ("today", "今天", "今日"):
        base = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif s in ("yesterday", "昨天", "昨日"):
        base = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif s in ("前天",):
        base = (now - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif s in ("本周", "这周", "thisweek", "week"):
        base = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0)
    elif s in ("上周", "lastweek"):
        base = (now - timedelta(days=now.weekday() + 7)).replace(
            hour=0, minute=0, second=0, microsecond=0)
    elif s in ("now", "现在", "刚才"):
        base = now
    else:
        m = _REL_RE.match(s)
        if m:
            n, unit = int(m.group(1)), m.group(2)
            if unit in ("d", "day", "days", "天", "日"):
                base = (now - timedelta(days=n)).replace(hour=0, minute=0, second=0,
                                                         microsecond=0)
            elif unit in ("h", "hour", "hours", "小时"):
                base = now - timedelta(hours=n)
            else:
                base = now - timedelta(minutes=n)
        else:
            m = _TS_RE.match(s)
            if m:
                y, mo, d, hh, mm, ss = m.groups()
                base = datetime(int(y), int(mo), int(d),
                                int(hh or 0), int(mm or 0), int(ss or 0))
                if hh is None and end:
                    base += timedelta(days=1)
            else:
                m = _DAY_RE.match(s)
                if m:
                    base = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    if end:
                        base += timedelta(days=1)
                else:
                    m = _MD_RE.match(s)
                    if not m:
                        raise ValueError(f"看不懂的时间 {text!r}; 可用 today/昨天/3d/2小时/"
                                         "2026-11-01/11-01 这类写法")
                    mo, d = int(m.group(1)), int(m.group(2))
                    base = datetime(now.year, mo, d)
                    if end:
                        base += timedelta(days=1)
    return base


def _file_start(meta: dict, path: Path) -> datetime | None:
    started = _parse_ts((meta or {}).get("started"))
    if started:
        return started
    m = _FNAME_TIME_RE.search(path.name)
    if m:
        try:
            return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
        except ValueError:
            pass
    try:
        return datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return None


# ---------- 存储 ----------

_cache: dict = {"key": None, "records": []}
_append_lock = threading.Lock()


def load(path: Path | None = None) -> list[dict]:
    """读全量台账(按 文件大小+mtime 缓存); 半行/坏行直接跳过(落盘中断不致命)。"""
    p = Path(path or ledger_path())
    try:
        st = p.stat()
    except OSError:
        return []
    key = (str(p), st.st_size, st.st_mtime_ns)
    if _cache["key"] == key:
        return _cache["records"]
    if st.st_size > MAX_FILE_BYTES:
        records = []  # 异常膨胀的台账不整份读进内存, 当作没有(不阻塞其它功能)
    else:
        records = []
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(rec, dict) and rec.get("kind"):
                        records.append(rec)
        except OSError:
            records = []
    _cache["key"] = key
    _cache["records"] = records
    return records


def _append(recs: list[dict]) -> None:
    if not recs:
        return
    p = ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with _append_lock:
        with open(p, "a", encoding="utf-8") as f:
            for rec in recs:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    _cache["key"] = None


def save_program(jid: str, code: str) -> tuple[str, int]:
    """把建造程序源码另存一份(压缩后仍可续建/重放), 返回 (相对路径, 行数)。"""
    if not code or not jid:
        return "", 0
    d = program_dir()
    d.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(jid))[:60]
    p = d / f"{safe}.py"
    text = code if code.endswith("\n") else code + "\n"
    try:
        p.write_text(text, encoding="utf-8")
    except OSError:
        return "", 0
    try:
        rel = str(p.relative_to(paths.BASE_DIR))
    except ValueError:
        rel = str(p)
    return rel, text.count("\n")


# ---------- 运行时写入 ----------

class Ledger:
    """进程内写台账。

    写入时机(全部是"事情已经发生"之后, 不依赖模型事后总结):
      1. set_mode 真正切进创造模式 → episode open(理由 + 触发原话)
      2. build_preview 成功 → op preview(名字/包围盒/格数/材料/程序源码)
      3. build_commit 成功 → op commit(写入格数/校验结果)
      4. build_undo 成功 → op undo(还原格数)
      5. set_mode 切回普通 / 下一次 open / 会话结束 → episode close(尽力而为)

    所以模型即使一直没切回普通模式也不影响任何记录: close 只是"结束说明", 查询侧的作品
    区间与状态完全由 op 自己的时间戳、提交/撤销事实推出来(见 episodes())。
    台账写入失败只记一行日志, 绝不让建造/查询工具因此报错。
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._open: dict | None = None
        self._seq: int | None = None
        self._eid: int | None = None

    # 计数器懒初始化: 台账可能已有回填的历史记录, id 必须接着往下排
    def _init_counters(self, records: list[dict]) -> None:
        if self._seq is not None:
            return
        seq = 0
        eid = 0
        for rec in records:
            m = re.fullmatch(r"r(\d+)", str(rec.get("id") or ""))
            if m:
                seq = max(seq, int(m.group(1)))
            m = re.fullmatch(r"e(\d+)", str(rec.get("eid") or ""))
            if m:
                eid = max(eid, int(m.group(1)))
        self._seq = seq
        self._eid = eid

    def _emit(self, rec: dict) -> dict:
        """分配 id/ts 并落盘(必须在锁内调用)。"""
        rec.setdefault("v", VERSION)
        rec.setdefault("ts", now_ts())
        self._seq = int(self._seq or 0) + 1
        rec["id"] = f"r{self._seq:05d}"
        _append([rec])
        return rec

    def _safe(self, fn, *args, **kwargs):
        """台账是旁路: 任何异常只记日志, 不影响工具本身的返回值。"""
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 - 台账绝不能拖垮施工
            try:
                paths.log(f"[台账] 写入失败({type(e).__name__}: {e})")
            except Exception:
                pass
            return None

    def open_episode(self, mode: str, reason: str, player: str = "",
                     trigger: str = "", session=None, session_start: str = "",
                     sfile: str = "") -> str:
        return self._safe(self._open_episode, mode, reason, player, trigger,
                          session, session_start, sfile) or ""

    def _open_episode(self, mode, reason, player, trigger, session, session_start, sfile):
        with self._lock:
            # 上一段没等到切回普通模式就又开始施工: 隐式收尾, 保证台账里区间干净
            if self._open:
                self._close_episode("进入下一次创造模式")
            self._init_counters(load())
            self._eid = int(self._eid or 0) + 1
            eid = f"e{self._eid:05d}"
            self._emit({"kind": "episode", "action": "open", "eid": eid, "mode": mode,
                        "player": player, "session": session,
                        "session_start": session_start, "sfile": sfile,
                        "reason": reason, "trigger": (trigger or "")[:400]})
            self._open = {"eid": eid, "session": session,
                          "session_start": session_start, "player": player}
            return eid

    def close_episode(self, reason: str = "", ts: str = "") -> None:
        self._safe(self._close_episode, reason, ts)

    def _close_episode(self, reason: str = "", ts: str = "") -> None:
        with self._lock:
            if not self._open:
                return
            rec = {"kind": "episode", "action": "close", "eid": self._open["eid"],
                   "reason": (reason or "")[:200]}
            if ts:
                rec["ts"] = ts
            self._init_counters(load())
            self._emit(rec)
            self._open = None

    def _op_ctx(self, session=None, session_start: str = "") -> dict:
        if self._open:
            return {"eid": self._open["eid"],
                    "session": session if session is not None else self._open.get("session"),
                    "session_start": session_start or self._open.get("session_start") or ""}
        return {"eid": None, "session": session, "session_start": session_start}

    def record_preview(self, jid: str, name: str, data: dict, stats: dict,
                       origin=None, facing: str = "", program: str = "",
                       session=None, session_start: str = "", mode: str = "",
                       player: str = "", trigger: str = "") -> None:
        """写一个批次。没有 open 的 episode 时(重启/恢复会话后继续施工, 或历史断档)
        自动补开一个, 免得批次变成找不到理由的孤儿记录。"""
        self._safe(self._record_preview, jid, name, data, stats, origin, facing,
                   program, session, session_start, mode, player, trigger)

    def _record_preview(self, jid, name, data, stats, origin, facing, program,
                        session, session_start, mode, player, trigger):
        if self._open is None and str(mode).startswith("creative"):
            self._open_episode(mode, "(未记录到切换: 重启/恢复后直接施工)", player,
                               trigger, session, session_start)
        b = (data or {}).get("bounds") or {}
        frm, to = b.get("from"), b.get("to")
        size = (stats or {}).get("size") or []
        cells = int((data or {}).get("cells") or (stats or {}).get("cells") or 0)
        materials = dict((stats or {}).get("materials") or {})
        program_path, program_lines = save_program(jid, program)
        rec = {"kind": "op", "action": "preview", "jid": jid,
               "name": (name or "")[:60], "origin": list(origin or []),
               "facing": facing or "", "from": frm, "to": to,
               "size": list(size), "cells": cells,
               "palette": int((data or {}).get("paletteSize")
                              or (stats or {}).get("palette") or 0),
               "materials": dict(sorted(materials.items(),
                                        key=lambda kv: -kv[1])[:MAX_MATERIALS]),
               "program": program_path, "program_lines": program_lines}
        rec.update(self._op_ctx(session, session_start))
        with self._lock:
            self._init_counters(load())
            self._emit(rec)

    def record_commit(self, jid: str, data: dict,
                      session=None, session_start: str = "") -> None:
        self._safe(self._record_commit, jid, data, session, session_start)

    def _record_commit(self, jid, data, session, session_start):
        rec = {"kind": "op", "action": "commit", "jid": jid,
               "changed": int((data or {}).get("changed") or 0),
               "boxes": int((data or {}).get("boxes") or 0),
               "verify": (data or {}).get("verify") or {},
               "undoOf": (data or {}).get("undoOf")}
        rec.update(self._op_ctx(session, session_start))
        with self._lock:
            self._init_counters(load())
            self._emit(rec)

    def record_undo(self, jid: str, data: dict,
                    session=None, session_start: str = "") -> None:
        self._safe(self._record_undo, jid, data, session, session_start)

    def _record_undo(self, jid, data, session, session_start):
        rec = {"kind": "op", "action": "undo",
               "jid": (data or {}).get("undoOf") or jid or "",
               "restored": int((data or {}).get("changed") or 0)}
        rec.update(self._op_ctx(session, session_start))
        with self._lock:
            self._init_counters(load())
            self._emit(rec)


# ---------- 聚合(查询侧共用) ----------

def _blank_op(rec: dict) -> dict:
    return {"jid": rec.get("jid") or "", "name": rec.get("name") or "",
            "ts": rec.get("ts") or "", "origin": rec.get("origin") or [],
            "facing": rec.get("facing") or "", "from": None, "to": None, "size": None,
            "cells": 0, "palette": 0, "materials": {}, "blocks": [], "program": "",
            "program_lines": 0, "committed": False, "changed": 0, "boxes": 0,
            "verify": None, "undone": False, "restored": 0, "stages": []}


def _apply_op(rec: dict, op: dict) -> None:
    action = rec.get("action")
    op["stages"].append(action)
    if action == "preview":
        op["name"] = rec.get("name") or op["name"]
        op["from"] = rec.get("from") or op["from"]
        op["to"] = rec.get("to") or op["to"]
        op["size"] = rec.get("size") or op["size"]
        op["origin"] = rec.get("origin") or op["origin"]
        op["facing"] = rec.get("facing") or op["facing"]
        op["cells"] = int(rec.get("cells") or 0)
        op["palette"] = int(rec.get("palette") or 0)
        op["materials"] = dict(rec.get("materials") or {})
        op["blocks"] = list(rec.get("blocks") or [])
        op["program"] = rec.get("program") or ""
        op["program_lines"] = int(rec.get("program_lines") or 0)
        if rec.get("ts"):
            op["ts"] = rec["ts"]
    elif action == "commit":
        op["committed"] = True
        op["changed"] = int(rec.get("changed") or 0)
        op["boxes"] = int(rec.get("boxes") or 0)
        op["verify"] = rec.get("verify") or {}
        if not op["ts"] and rec.get("ts"):
            op["ts"] = rec["ts"]
    elif action == "undo":
        op["undone"] = True
        op["restored"] = int(rec.get("restored") or 0)


def _new_episode(rec: dict) -> dict:
    return {"eid": rec.get("eid") or "", "ts": rec.get("ts") or "",
            "mode": rec.get("mode") or "creative",
            "player": rec.get("player") or "", "session": rec.get("session"),
            "session_start": rec.get("session_start") or "",
            "reason": rec.get("reason") or "", "trigger": rec.get("trigger") or "",
            "closed": "", "close_reason": "", "ops": []}


def episodes(records: list[dict] | None = None) -> list[dict]:
    """台账记录 → 按时间排好的 episode 列表(含各自合并后的 op 明细)。

    没有 eid 的 op(重启后先施工、或回填时的孤儿批次)挂到它之前最近的一个 episode 上;
    完全找不到就自己合成一个无理由的 episode, 保证不丢施工记录。
    """
    recs = load() if records is None else records
    eps: list[dict] = []
    by_id: dict[str, dict] = {}
    ops: list[dict] = []
    for rec in recs:
        kind = rec.get("kind")
        if kind == "episode" and rec.get("action") == "open":
            ep = _new_episode(rec)
            eps.append(ep)
            if ep["eid"]:
                by_id[ep["eid"]] = ep
        elif kind == "episode" and rec.get("action") == "close":
            ep = by_id.get(rec.get("eid") or "")
            if ep is not None:
                ep["closed"] = rec.get("ts") or ""
                ep["close_reason"] = rec.get("reason") or ""
        elif kind == "op":
            ops.append(rec)
    eps.sort(key=lambda e: e["ts"])
    pending: dict[tuple, dict] = {}
    jid_owner: dict[str, dict] = {}
    for rec in sorted(ops, key=lambda r: r.get("ts") or ""):
        jid = rec.get("jid") or ""
        # 撤销/提交记录可能落在后一个 episode(例如"撤销刚才那批"是新开的创造任务),
        # 但它描述的是**原来那一批**: 统一挂回首次 preview 所属的 episode。
        owner = jid_owner.get(jid) if jid else None
        if owner is None:
            owner = by_id.get(rec.get("eid") or "")
        if owner is None:
            # 没有 eid: 优先同 session_start 的最后一个 episode, 否则按时间就近
            cands = [e for e in eps
                     if not e["ts"] or (rec.get("ts") or "") >= e["ts"]]
            same = [e for e in cands
                    if (e["session_start"] or "") == (rec.get("session_start") or "")]
            owner = (same or cands or eps)[-1] if (same or cands or eps) else None
        if owner is None:
            key = ("orphan", rec.get("ts") or "")
            owner = pending.get(key)
            if owner is None:
                owner = _new_episode({"ts": rec.get("ts") or "", "eid": ""})
                pending[key] = owner
                eps.append(owner)
        if jid:
            op = next((o for o in owner["ops"] if o["jid"] == jid), None)
            if op is None:
                op = _blank_op(rec)
                owner["ops"].append(op)
            if rec.get("action") == "preview":
                jid_owner[jid] = owner
        else:
            op = _blank_op(rec)
            owner["ops"].append(op)
        _apply_op(rec, op)
    return [e for e in eps if e["ops"] or e["reason"]]


# ---------- 回填(历史会话 + bot.log) ----------

def _read_session_file(path: Path) -> tuple[dict, list[dict]]:
    """容错读取会话 JSONL: 返回 (meta, messages)。坏行/半行跳过。"""
    meta: dict = {}
    messages: list[dict] = []
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return meta, messages
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(rec, dict):
                    continue
                if "_meta" in rec:
                    meta = rec["_meta"] or {}
                elif rec.get("role"):
                    messages.append(rec)
    except OSError:
        pass
    return meta, messages


def _args_of(tc: dict) -> dict:
    raw = (tc.get("function") or {}).get("arguments")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "{}")
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(p.get("text") or "") for p in content
                         if isinstance(p, dict) and p.get("type") == "text")
    return ""


def log_build_info(bot_log: Path | None = None) -> dict[str, dict]:
    """从 bot.log 抽 jid → {ts, name, size, cells}: 回填历史时补精确时间,
    并在会话里只剩提交/撤销记录(压缩把预览结果丢了)时补上作品名与体积。"""
    out: dict[str, dict] = {}
    p = Path(bot_log or paths.LOG_PATH)
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                if "[建造]" not in line:
                    continue
                m = _LOG_LINE_RE.match(line)
                b = _LOG_BUILD_RE.search(line)
                if not (m and b):
                    continue
                ts = m.group(1).replace(" ", "T")
                info = out.setdefault(b.group(2), {})
                info.setdefault("ts", ts)
                pv = _LOG_PREVIEW_RE.search(line)
                if pv and pv.group(1) == b.group(2):
                    info.setdefault("name", pv.group(2).strip())
                    info.setdefault("size", [int(pv.group(i)) for i in (3, 4, 5)])
                    info.setdefault("cells", int(pv.group(6)))
    except OSError:
        pass
    return out


_BLOCK_TOKEN_RE = re.compile(r"""[\"']([a-z][a-z0-9_]{2,40})[\"']""")


def blocks_in_program(code: str, block_ids: set | None = None) -> list[str]:
    """程序里出现的方块 ID(历史回填用: 没有编译产物, 只能从源码里认)。

    给了 block_ids 就只留真实方块名, 免得把 "歇山"/"南" 这类风格参数当材料。
    """
    if not code:
        return []
    found = {m.group(1) for m in _BLOCK_TOKEN_RE.finditer(code)}
    found -= {"air", "cave_air", "void_air"}
    if block_ids:
        found = {b for b in found if b in block_ids}
    return sorted(found)[:24]


def scan_session_file(path: Path, jid_info: dict[str, dict] | None = None) -> dict:
    """扫一个会话文件, 抽出 creative episode 与建造批次(回填用)。

    返回 {"start": datetime|None, "session": int|None, "episodes": [...], "ops": {jid: op}}。
    episode 的 ts 取它第一个批次的时间(查 bot.log); 没有批次时退回会话开始时间。
    """
    jid_info = jid_info or {}
    meta, messages = _read_session_file(path)
    start = _file_start(meta, path)
    start_ts = start.isoformat(timespec="seconds") if start else ""
    results: dict[str, str] = {}
    for m in messages:
        if m.get("role") == "tool" and m.get("tool_call_id"):
            results[str(m["tool_call_id"])] = _text_of(m.get("content"))

    episodes: list[dict] = []
    ops: dict[str, dict] = {}
    cur: dict | None = None
    last_user = ""
    last_player = ""
    for m in messages:
        role = m.get("role")
        if role == "user":
            text = _text_of(m.get("content")).strip()
            mm = re.match(r"^([^:\n]{1,24}):\s*(.*)$", text, re.S)
            if mm:
                last_player, last_user = mm.group(1).strip(), mm.group(2).strip()
            else:
                last_user = text
            continue
        if role != "assistant":
            continue
        for tc in m.get("tool_calls") or []:
            fn = tc.get("function") or {}
            name, args = fn.get("name"), _args_of(tc)
            if name == "set_mode":
                mode = str(args.get("mode") or "")
                if mode.startswith("creative"):
                    cur = {"reason": str(args.get("reason") or ""),
                           "trigger": last_user[:400], "player": last_player,
                           "mode": mode, "ts": "", "closed": "", "close_reason": "",
                           "jids": [], "session": meta.get("session"),
                           "session_start": start_ts}
                    episodes.append(cur)
                else:
                    if cur is not None:
                        cur["closed"] = ""     # 精确时间回填时补
                        cur["close_reason"] = str(args.get("reason") or "")
                    cur = None
            elif name == "build_preview":
                res = results.get(str(tc.get("id") or ""), "")
                jid = ""
                mm = _PREVIEW_ID_RE.match(res.strip())
                if mm:
                    jid = mm.group(1)
                if not jid:
                    continue
                op = ops.get(jid)
                if op is None:
                    info = jid_info.get(jid) or {}
                    op = {"jid": jid,
                          "name": str(args.get("name") or info.get("name") or "")[:60],
                          "origin": args.get("origin") or [], "facing": str(args.get("facing") or ""),
                          "from": None, "to": None, "size": info.get("size"),
                          "cells": int(info.get("cells") or 0),
                          "palette": 0, "materials": {}, "program": "",
                          "program_lines": 0, "ts": info.get("ts") or start_ts,
                          "program_code": str(args.get("program") or ""),
                          "committed": False, "changed": 0, "boxes": 0,
                          "verify": None, "undone": False, "restored": 0}
                    b = _BOX_RE.search(res)
                    if b:
                        op["from"] = [int(b.group(i)) for i in (1, 2, 3)]
                        op["to"] = [int(b.group(i)) for i in (4, 5, 6)]
                        op["size"] = [int(b.group(i)) for i in (7, 8, 9)]
                    c = _CELLS_RE.search(res)
                    if c:
                        op["cells"] = int(c.group(1))
                        op["palette"] = int(c.group(2))
                    ops[jid] = op
                if cur is not None and jid not in cur["jids"]:
                    cur["jids"].append(jid)
            elif name in ("build_commit", "build_undo"):
                jid = str(args.get("operation_id") or "").strip()
                if not jid:
                    continue
                res = results.get(str(tc.get("id") or ""), "")
                op = ops.get(jid)
                if op is None:
                    info = jid_info.get(jid) or {}
                    op = {"jid": jid, "name": str(info.get("name") or "")[:60],
                          "origin": [], "facing": "",
                          "from": None, "to": None, "size": info.get("size"),
                          "cells": int(info.get("cells") or 0),
                          "palette": 0, "materials": {}, "program": "",
                          "program_lines": 0, "ts": info.get("ts") or start_ts,
                          "program_code": "", "committed": False, "changed": 0,
                          "boxes": 0, "verify": None, "undone": False, "restored": 0}
                    ops[jid] = op
                if name == "build_commit" and not op["committed"]:
                    mm = _COMMIT_RE.search(res)
                    if mm:
                        op["committed"] = True
                        op["changed"] = int(mm.group(2))
                        op["boxes"] = int(mm.group(3))
                    bad = _MISMATCH_RE.search(res)
                    if bad:
                        op["verify"] = {"mismatch": int(bad.group(1)),
                                        "holes": int(bad.group(2) or 0),
                                        "wrong": int(bad.group(3) or 0)}
                    elif "校验: 全部正确" in res:
                        op["verify"] = {"mismatch": 0, "holes": 0, "wrong": 0}
                elif name == "build_undo" and not op["undone"]:
                    mm = _UNDO_RE.search(res.strip())
                    if mm:
                        op["undone"] = True
                        op["restored"] = int(mm.group(2))
                if cur is not None and jid not in cur["jids"]:
                    cur["jids"].append(jid)
    return {"start": start, "session": meta.get("session"),
            "episodes": episodes, "ops": ops}


def backfill(bot_log: Path | None = None, save_programs: bool = True,
             dirs: tuple[Path, ...] | None = None, dry_run: bool = False,
             block_ids: set | None = None) -> dict:
    """从历史会话文件(+ bot.log 时间)生成台账, 幂等: 已记过的 episode/批次不会再写。

    返回统计 {"episodes": 新增, "ops": 新增, "skipped_episodes":, "skipped_ops":,
              "candidates": 扫到的 episode 数, "programs": 存了几份源码}
    dry_run=True 只统计不写盘(也不存源码)。
    """
    existing = load()
    seen_eids: dict[tuple, str] = {}       # (player, reason, trigger) → eid
    seen_jids = set()
    for rec in existing:
        if rec.get("kind") == "episode" and rec.get("action") == "open":
            key = (rec.get("player") or "", rec.get("reason") or "",
                   rec.get("trigger") or "")
            if rec.get("eid"):
                seen_eids[key] = rec["eid"]
        elif rec.get("kind") == "op" and rec.get("jid"):
            seen_jids.add(rec["jid"])

    jid_info = log_build_info(bot_log)
    searched = dirs or (paths.SESSION_DIR, paths.ONESHOT_DIR)
    scans = []
    for directory in searched:
        if not Path(directory).is_dir():
            continue
        for p in sorted(Path(directory).glob("*.jsonl")):
            try:
                scans.append((_file_start({}, p) or datetime.min, p))
            except OSError:
                continue
    scans.sort(key=lambda t: t[0])

    seq = max([int(re.fullmatch(r"r(\d+)", str(r.get("id") or "")).group(1))
               for r in existing
               if re.fullmatch(r"r(\d+)", str(r.get("id") or ""))] or [0])
    n_eid = max([int(re.fullmatch(r"e(\d+)", str(r.get("eid") or "")).group(1))
                 for r in existing
                 if re.fullmatch(r"e(\d+)", str(r.get("eid") or ""))] or [0])

    def nid() -> str:
        nonlocal seq
        seq += 1
        return f"r{seq:05d}"

    new_records: list[dict] = []
    stats = {"episodes": 0, "ops": 0, "skipped_episodes": 0, "skipped_ops": 0,
             "candidates": 0, "programs": 0}
    for _start, path in scans:
        scan = scan_session_file(path, jid_info)
        for ep in scan["episodes"]:
            stats["candidates"] += 1
            key = (ep.get("player") or "", ep.get("reason") or "",
                   ep.get("trigger") or "")
            op_rows = [scan["ops"][j] for j in ep["jids"] if j in scan["ops"]]
            fresh = [o for o in op_rows if o["jid"] not in seen_jids]
            stats["skipped_ops"] += len(op_rows) - len(fresh)
            if key in seen_eids:
                eid = seen_eids[key]
                stats["skipped_episodes"] += 1
            elif ep["jids"] and not fresh:
                stats["skipped_episodes"] += 1     # 整段都是已记过的批次(恢复会话副本)
                continue
            else:
                n_eid += 1
                eid = f"e{n_eid:05d}"
                seen_eids[key] = eid
                ts = (fresh[0]["ts"] if fresh else "") or ep["session_start"] or now_ts()
                stats["episodes"] += 1
                new_records.append({
                    "v": VERSION, "id": nid(), "ts": ts, "kind": "episode",
                    "action": "open", "eid": eid, "mode": ep.get("mode") or "creative",
                    "player": ep.get("player") or "", "session": ep.get("session"),
                    "session_start": ep.get("session_start") or "",
                    "reason": ep.get("reason") or "",
                    "trigger": (ep.get("trigger") or "")[:400]})
                if ep.get("close_reason"):
                    last_ts = max([o["ts"] for o in op_rows] or [ts])
                    new_records.append({
                        "v": VERSION, "id": nid(), "ts": last_ts, "kind": "episode",
                        "action": "close", "eid": eid,
                        "reason": ep["close_reason"][:200]})
            for op in fresh:
                seen_jids.add(op["jid"])
                stats["ops"] += 1
                prog, lines = ("", 0)
                if save_programs and not dry_run:
                    prog, lines = save_program(op["jid"], op.get("program_code") or "")
                    if prog:
                        stats["programs"] += 1
                new_records.append({
                    "v": VERSION, "id": nid(), "ts": op["ts"], "kind": "op",
                    "action": "preview", "eid": eid, "jid": op["jid"],
                    "name": op["name"], "origin": op["origin"],
                    "facing": op["facing"], "from": op["from"], "to": op["to"],
                    "size": op["size"], "cells": op["cells"],
                    "palette": op["palette"], "materials": op["materials"],
                    "blocks": blocks_in_program(op.get("program_code") or "", block_ids),
                    "program": prog, "program_lines": lines,
                    "session": scan["session"],
                    "session_start": ep["session_start"]})
                if op["committed"]:
                    new_records.append({
                        "v": VERSION, "id": nid(), "ts": (jid_info.get(op["jid"]) or {}).get("ts") or op["ts"],
                        "kind": "op", "action": "commit", "eid": eid, "jid": op["jid"],
                        "changed": op["changed"], "boxes": op["boxes"],
                        "verify": op["verify"], "session": scan["session"],
                        "session_start": ep["session_start"]})
                if op["undone"]:
                    new_records.append({
                        "v": VERSION, "id": nid(), "ts": (jid_info.get(op["jid"]) or {}).get("ts") or op["ts"],
                        "kind": "op", "action": "undo", "eid": eid, "jid": op["jid"],
                        "restored": op["restored"], "session": scan["session"],
                        "session_start": ep["session_start"]})
    new_records.sort(key=lambda r: (r.get("ts") or "", r.get("kind") == "episode"))
    if not dry_run:
        _append(new_records)
    return stats
