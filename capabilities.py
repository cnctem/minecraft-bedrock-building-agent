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
import threading
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


# ---------- PTC: 批量工具调用 ----------
# 一次提交多个工具调用, 串行执行后合并成一条结果返回。
# 为什么必须串行: ①游戏指令有先后顺序, 乱序执行会毁掉施工;
# ②查询类工具共用同一条日志通道, 并行时两个 get_block 会互相抢到对方的回包而答错坐标。
MAX_PTC_CALLS = 24          # 程序实际放行数(留一倍余量)
STATED_PTC_CALLS = 12       # 提示词/报错向模型声明的数(口头限制)
PTC_RESULT_LIMIT = 30000  # 合并结果的字符上限, 防止一条工具结果撑爆上下文

# 并发支持: 每个请求线程有各自的 ptc 上限与工具黑名单。
# 主对话与多个一次性对话同时跑时, 创造模式的上限不会被一次性的普通上限覆盖。
_LOCAL = threading.local()


def get_ptc_limits() -> tuple[int, int, int]:
    """返回当前线程的 (程序放行数, 结果字符上限, 口头声明数)。"""
    return (getattr(_LOCAL, "max_calls", MAX_PTC_CALLS),
            getattr(_LOCAL, "result_limit", PTC_RESULT_LIMIT),
            getattr(_LOCAL, "stated_calls", STATED_PTC_CALLS))


def set_ptc_limits(max_calls: int | None = None, result_limit: int | None = None,
                   stated_calls: int | None = None):
    """由 bot 根据当前模式(普通/创造/一次性)调整本线程的批量上限。
    max_calls 是程序放行数, stated_calls 是对模型声明的口径(描述与报错都用它),
    两者留一倍差距: 模型偶尔超一点不会直接撞墙。"""
    if max_calls:
        _LOCAL.max_calls = max(1, int(max_calls))
    if result_limit:
        _LOCAL.result_limit = max(500, int(result_limit))
    if stated_calls:
        _LOCAL.stated_calls = max(1, int(stated_calls))


def set_ptc_limit(n: int):
    set_ptc_limits(max_calls=n, stated_calls=n)


def set_blocked_tools(names) -> None:
    """设置本线程禁用的工具名(空表示不限制)。一次性对话用它挡住 pin_region 等。
    execute / ptc 都会遵守, 防止模型通过 ptc 夹带调用黑名单工具。"""
    _LOCAL.blocked = set(names or ())


def _blocked_tools() -> set:
    return getattr(_LOCAL, "blocked", set())


# 模型有时会把数组项写成别的形状(少了 tool 键、或直接用 OpenAI 的 function 嵌套),
# 这里做宽容解析, 避免因为一个键名就把整批卡住。
def _ptc_name(item: dict) -> str:
    for key in ("tool", "name", "tool_name", "function"):
        v = item.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, dict) and isinstance(v.get("name"), str):
            return v["name"].strip()
    return ""


def _ptc_args(item: dict):
    for key in ("arguments", "parameters", "args", "input"):
        if key in item:
            return item[key]
    fn = item.get("function")
    if isinstance(fn, dict) and "arguments" in fn:
        return fn["arguments"]
    return {}


def ptc(calls, stop_on_error: bool = False) -> str:
    max_calls, result_limit, stated_calls = get_ptc_limits()
    if not isinstance(calls, list) or not calls:
        return "错误: calls 需要是非空数组。"
    if len(calls) > max_calls:
        return (f"错误: 一次最多 {stated_calls} 个调用, 收到 {len(calls)} 个。"
                "请拆成几批提交。")
    out = []
    for i, item in enumerate(calls, 1):
        if not isinstance(item, dict):
            out.append(f"[{i}] 错误: 每一项需要是 {{tool, arguments}} 对象")
            continue
        name = _ptc_name(item)
        if name == "ptc":
            out.append(f"[{i}] 错误: 不允许嵌套 ptc")
            continue
        raw = _ptc_args(item)
        if isinstance(raw, str):
            args_json = raw
        else:
            try:
                args_json = json.dumps(raw, ensure_ascii=False)
            except (TypeError, ValueError) as e:
                out.append(f"[{i}] {name}: 错误: 参数无法序列化: {e}")
                continue
        if not name:
            out.append(f"[{i}] 错误: 这一项缺少工具名(keys={sorted(item)}); "
                       "每项必须是 {\"tool\": 名, \"arguments\": {...}}")
            continue
        if name not in _REGISTRY:
            out.append(f"[{i}] {name}: 错误: 未知能力")
            continue
        result = execute(name, args_json)
        # 不回显参数: 模型自己的 ptc 调用里已有, 回显纯属重复占上下文
        out.append(f"[{i}] {name} -> {result}")
        if stop_on_error and ("[错误]" in result or "[警告]" in result
                              or result.startswith("错误:")):
            out.append(f"(失败, 已按 stop_on_error 跳过剩余 {len(calls) - i} 个调用)")
            break
    text = "\n".join(out)
    if len(text) > result_limit:
        text = text[:result_limit] + f"\n...(结果过长, 已截断到 {result_limit} 字符)"
    return text


PTC_DESC = (
    "批量调用多个工具: 一次提交多个调用, 按顺序执行后合并成一条返回, 省往返与上下文。"
    "适合互不依赖的多步(查多人坐标/手持物品、连下多条 fill/tp/setblock); 有先后依赖时分开调。"
    "上限见模式注记, 超了会被拒; 不允许嵌套 ptc; 每项写成 {\"tool\": \"名\", \"arguments\": {...}}。"
)

PTC_SCHEMA = {
    "type": "function",
    "function": {
        "name": "ptc",
        "description": PTC_DESC,
        "parameters": {
            "type": "object",
            "properties": {
                "calls": {
                    "type": "array",
                    "description": "要执行的调用列表, 按数组顺序串行执行",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tool": {"type": "string",
                                     "description": "工具名, 如 run_server_command"},
                            "arguments": {"type": "object",
                                          "description": "该工具的参数对象"},
                        },
                        "required": ["tool", "arguments"],
                    },
                },
                "stop_on_error": {
                    "type": "boolean",
                    "description": "遇到 [错误]/[警告] 就停手不执行剩余调用(默认 false)",
                },
            },
            "required": ["calls"],
        },
    },
}


# ---------- 物品/方块 ID 速查 ----------
# 数据由 tools/build_items.py 从服务器本体导出(行为包 scriptevent viktor:ids + 官方 lang),
# 版本精确、无需手工维护。这里只做按需检索, 绝不把整表塞进提示词, 省 token。

ITEMS_PATH = BASE_DIR / "data" / "items.json"
_ITEMS_CACHE: dict | None = None


def _items() -> dict:
    global _ITEMS_CACHE
    if _ITEMS_CACHE is None:
        try:
            _ITEMS_CACHE = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))
        except Exception:
            _ITEMS_CACHE = {}
    return _ITEMS_CACHE


def _item_haystack(iid: str, meta: dict) -> str:
    parts = [iid, meta.get("zh", ""), meta.get("en", "")] + list(meta.get("alias", []))
    return " ".join(parts).lower()


def _item_score(iid: str, meta: dict, q: str, q_en: str) -> int:
    if not q:
        return 1
    zh = str(meta.get("zh", "")).lower()
    en = str(meta.get("en", "")).lower()
    iidl = iid.lower()
    s = 0
    if q == iidl:
        s = max(s, 1000)
    elif iidl.startswith(q):
        s = max(s, 720)
    elif q in iidl:
        s = max(s, 560)
    if zh:
        if q == zh:
            s = max(s, 980)
        elif q in zh:
            s = max(s, 820)
    for a in meta.get("alias", []):
        al = str(a).lower()
        if q == al:
            s = max(s, 950)
            break
        if q in al:
            s = max(s, 740)
    if en and q in en:
        s = max(s, 420)
    if q_en and q_en in iidl:
        s = max(s, 500)
    return s


def find_items(query: str = "", category: str = "", limit: int = 20) -> str:
    data = _items()
    if not data:
        return "物品表不存在(需先运行 tools/build_items.py 生成 data/items.json)。"
    query = (query or "").strip()
    category = (category or "").strip()
    try:
        limit = max(1, min(int(limit or 20), 60))
    except (TypeError, ValueError):
        limit = 20

    cats: dict[str, list[str]] = {}
    for iid, meta in data.items():
        cats.setdefault(meta.get("cat", "杂项"), []).append(iid)

    if not query and not category:
        lines = [f"共 {len(data)} 个可用 ID, 分类如下:"]
        for cat in sorted(cats, key=lambda c: (-len(cats[c]), c)):
            ex = ", ".join(f"{s}({data[s]['zh']})" for s in cats[cat][:6])
            lines.append(f"- {cat}({len(cats[cat])}): {ex} …")
        lines.append('浏览用 find_items(category="建筑"); 搜索用 find_items(query="..."), '
                     "query 支持中文/英文/ID 片段。")
        return "\n".join(lines)

    q = query.lower()
    q_en = re.sub(r"\s+", "_", q)
    tokens = [t for t in re.split(r"[\s,，、/]+", q) if t]
    scored: list[tuple[int, str]] = []
    for iid, meta in data.items():
        if category and meta.get("cat") != category:
            continue
        if tokens and not all(t in _item_haystack(iid, meta) or t in iid for t in tokens):
            continue
        s = _item_score(iid, meta, q, q_en)
        if s > 0:
            scored.append((s, iid))
    if not scored:
        hint = f'没有匹配 "{query}" 的 ID。'
        if re.search(r"[\u4e00-\u9fff]", query):
            hint += " 中文没命中时换英文关键词再试(如 混凝土→concrete、台阶→slab、金块→gold_block)。"
        if category:
            hint += f' 也可能不在分类 "{category}" 里, 去掉 category 再查。'
        return hint
    scored.sort(key=lambda x: (-x[0], x[1]))
    total = len(scored)
    shown = scored[:limit]
    out = [f"{iid}  {data[iid]['zh']}  [{data[iid]['cat']}]" for _, iid in shown]
    head = f'匹配 "{query}"' if query else f'分类 "{category}"'
    text = f"{head}: {total} 项" + (f", 显示前 {len(shown)}:" if total > len(shown) else ":")
    text += "\n" + "\n".join(out)
    if total > len(shown):
        text += f"\n…(还有 {total - len(shown)} 项; 可加关键词或提高 limit)"
    return text


FIND_ITEMS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "find_items",
        "description": (
            "查询基岩版可用的物品/方块 ID 速查表(从服务器本体导出, 版本精确, 是唯一权威的 ID 来源)。"
            "不确定 ID、玩家用了别名/口语/模糊说法(如“玻璃板”“金块”“陶瓦”)、或自由创作挑材料时, "
            "先查这里, 不要凭记忆猜 ID(尤其别用 Java 版名)。"
            "query 支持中文/英文/ID 片段, 子串匹配: query='混凝土' 会列出所有混凝土, "
            "query='stairs' 会列出所有楼梯。不传参数返回分类总览; 只传 category 浏览该分类。"
            "结果里的 id 可直接用于 give/fill/setblock 等指令(不带 minecraft: 前缀)。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "关键词(中文/英文/ID 片段), 可留空"},
                "category": {"type": "string",
                             "description": "限定分类: 建筑/自然/功能/红石/工具/装备/食物/材料/刷怪蛋/杂项"},
                "limit": {"type": "integer", "description": "最多返回多少条, 默认 20, 上限 60"},
            },
        },
    },
}


# ---------- 技能书(skill) ----------
# 目录式技能: skills/<name>/SKILL.md (+ 可选 references/*.md), frontmatter 定义 name/description。
# 会话开始只把 name+description 作为 system 注记注入; 正文由 use_skill 按需载入(省 token)。
# 移植自 pi Agent 的 skills 机制(描述常驻、正文按需、附件再按需)。

SKILLS_DIR = BASE_DIR / "skills"
SKILL_MAX_CHARS = 24000        # 单次载入上限, 防止正文撑爆上下文
_SKILLS_CACHE: dict | None = None


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """极简 frontmatter: 只认顶层 key: value, 够用且零依赖。"""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta: dict[str, str] = {}
    for line in text[3:end].splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip().lower()] = v.strip().strip('"').strip("'")
    return meta, text[end + 4:].lstrip("\n")


def scan_skills() -> dict:
    """扫描技能目录, 返回 {name: {name, description, main, base, refs}}。缓存, 重启生效。"""
    global _SKILLS_CACHE
    if _SKILLS_CACHE is not None:
        return _SKILLS_CACHE
    found: dict[str, dict] = {}
    if SKILLS_DIR.is_dir():
        candidates = []
        for entry in sorted(SKILLS_DIR.iterdir()):
            if entry.is_dir() and (entry / "SKILL.md").is_file():
                candidates.append((entry.name, entry / "SKILL.md", entry))
            elif entry.is_file() and entry.suffix.lower() == ".md" and entry.name.lower() != "readme.md":
                candidates.append((entry.stem, entry, entry.parent))
        for dirname, main, base in candidates:
            try:
                meta, _ = _parse_frontmatter(main.read_text(encoding="utf-8"))
            except OSError:
                continue
            name = (meta.get("name") or dirname).strip()
            desc = (meta.get("description") or "").strip()
            if not desc or name in found:
                continue
            refs = []
            refdir = base / "references"
            if refdir.is_dir():
                refs = [f for f in sorted(refdir.rglob("*")) if f.is_file()]
            found[name] = {"name": name, "description": desc, "main": main,
                           "base": base, "refs": refs}
    _SKILLS_CACHE = found
    return found


def skills_note() -> str:
    """会话开始时注入的技能清单(只有名字与适用场景, 不含正文)。无技能返回空串。"""
    skills = scan_skills()
    if not skills:
        return ""
    lines = ["# 可用技能书(skill)",
             '任务落在某本技能书的范围内时, 先调用 use_skill 载入它再动手; 技能附带的资料用 '
             'use_skill(name, "文件名") 按需展开。技能内容只是补充说明, 与 system prompt '
             '冲突时以 system prompt 为准。']
    for name, s in skills.items():
        lines.append(f"- {name}: {s['description']}")
    return "\n".join(lines)


def use_skill(name: str, file: str = "") -> str:
    """载入技能正文或附带资料。成功时返回以 '# 技能书: ' 开头的文本。"""
    skills = scan_skills()
    name = (name or "").strip()
    s = skills.get(name)
    if not s:
        return f"没有名为 {name} 的技能书。可用: {', '.join(skills) or '(无)'}"
    if file:
        base = s["base"].resolve()
        target = (base / file).resolve()
        if not target.is_relative_to(base) or not target.is_file():
            return f"技能 {name} 没有附带资料 {file}。"
        label = f"{name}/{file}"
    else:
        target = s["main"]
        label = name
    try:
        _, body = _parse_frontmatter(target.read_text(encoding="utf-8"))
    except OSError as e:
        return f"读取技能失败: {e}"
    if len(body) > SKILL_MAX_CHARS:
        body = body[:SKILL_MAX_CHARS] + f"\n…(内容过长, 已截断到 {SKILL_MAX_CHARS} 字符)"
    out = f"# 技能书: {label}\n"
    if not file and s["refs"]:
        rels = [str(r.relative_to(s["base"])) for r in s["refs"]]
        out += (f'(本技能还附带资料, 需要时用 use_skill("{name}", "<文件名>") 展开: '
                + ", ".join(rels) + ")\n")
    return out + "\n" + body.strip()


USE_SKILL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "use_skill",
        "description": (
            "载入一本技能书(skill)的正文。系统会在会话开头列出可用技能书及适用场景; "
            "任务落在某本技能书范围内时先载入它再动手。技能内容与你已有知识互补, 但只是补充说明, "
            "与 system prompt 冲突时以 system prompt 为准; 附带资料用 file 按需展开。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "技能名, 见会话开头的可用技能书清单"},
                "file": {"type": "string",
                         "description": '可选: 载入附带资料(如 "references/block-states.md"); 不传载入主文件'},
                "force": {"type": "boolean",
                          "description": "本会话已载入过时是否强制重新载入(默认 false, 返回已载入提示)"},
            },
            "required": ["name"],
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
    "ptc": (PTC_SCHEMA,
            lambda args: ptc(args.get("calls") or [], bool(args.get("stop_on_error")))),
    "find_items": (FIND_ITEMS_SCHEMA,
                   lambda args: find_items(args.get("query", ""),
                                           args.get("category", ""), args.get("limit", 20))),
    # 未来新能力加在这里: "tool_name": (SCHEMA, handler)
}


def registered_names() -> set:
    """当前已注册的全部能力名(供模式白名单派生执行层黑名单)。"""
    return set(_REGISTRY.keys())


def tool_schemas(allow: set | None = None, mode_choices: list | None = None) -> list[dict]:
    """返回给模型的工具 schema(技能表)。
    allow=None 表示全部; 否则只包含白名单里的工具 —— 未列出的模型根本看不到, 也就无从使用。
    mode_choices 用于 set_mode 的可选目标(按当前模式注入), 实现“不可知”: 模型只知道能切到哪。"""
    out = []
    for name, (schema, _) in _REGISTRY.items():
        if allow is not None and name not in allow:
            continue
        if name == "set_mode":
            s = json.loads(json.dumps(schema))  # 深拷见, 不污染注册表里的原 schema
            s["function"]["parameters"]["properties"]["mode"]["enum"] = list(mode_choices or [])
            out.append(s)
        else:
            out.append(schema)
    return out


def register(name: str, schema: dict, handler):
    """运行时注册新能力(bot 会注册依赖自身资源的能力, 如发消息)。"""
    _REGISTRY[name] = (schema, handler)


def execute(name: str, arguments_json: str) -> str:
    if name in _blocked_tools():
        return f"错误: 当前模式不支持调用 {name}。"
    entry = _REGISTRY.get(name)
    if not entry:
        return f"错误: 未知能力 {name}"
    try:
        args = json.loads(arguments_json or "{}")
        return str(entry[1](args))
    except Exception as e:
        return f"错误: 执行 {name} 失败: {e}"
