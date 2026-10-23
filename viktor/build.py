"""建造程序: AST 白名单 + 子进程沙箱 + 体素化 + KEEP/RLE 编码。

模型写的是**函数体**, 作用域里有 `api`(纯几何, 不碰世界)。本模块把它变成
「期望体素体积」: palette(索引 0 固定 = KEEP 不写) + 分层 RLE, 交给行为包执行。

依赖方向: 叶子模块, 只 import 标准库; 不 import 项目内模块。
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

# ---------- 限额(与行为包 BUILD_MAX_VOLUME / 调色板 64 对齐) ----------
MAX_VOLUME = 65536        # 单次操作体积(格)
MAX_CELLS = 65536         # 实际写入格数
MAX_OPS = 20000           # 程序产出的形状数
MAX_PROGRAM = 16000       # 程序源码字节
MAX_PALETTE = 64
MAX_BOUNDS = 512          # 单轴跨度上限(防止一条线拉出天文数字的包围盒)
SANDBOX_TIMEOUT = 8.0     # 墙钟秒
SANDBOX_MEM_MB = 256

FACINGS = ("north", "south", "east", "west")

# 多格方块: 编译器自动展开成两格(实测状态名, 见 docs/p2-build-engine.md)
TALL_PLANTS = {
    "tall_grass", "large_fern", "sunflower", "lilac", "rose_bush", "peony",
    "pitcher_plant", "tall_dripleaf",
}
# 床: 写入格 = 床头; 床尾由引擎自动放在 direction 方向(实测 0=北 1=东 2=南 3=西, 即 头→尾)
BED_DIR = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}
CARD2NUM = {"south": 0, "west": 1, "north": 2, "east": 3,
            "minecraft:south": 0, "minecraft:west": 1,
            "minecraft:north": 2, "minecraft:east": 3}
# 仍不支持(需要邻居/朝向计算, 或写入语义不明)
UNSUPPORTED: set = set()


_RAW_IDS = Path(__file__).resolve().parent.parent / "data" / "raw_ids.txt"
_BLOCK_IDS: set | None = None


def limit_hint(label: str, cur: int, limit: int, shape: str, unit: str = "格") -> str:
    """限额报错要能照着改: 说清上限的等价尺寸、当前多少、超了几倍。"""
    over = (cur / limit) if limit else 0
    return (f"{label}最多 {limit} {unit}(上限相当于 {shape}), 当前 {cur} {unit}"
            f"(约 {over:.1f} 倍), 请缩到 {shape} 或更小/分块做。")


def block_ids() -> set:
    """服务器本体导出的方块 ID(不含 minecraft:), 用于校验程序里的方块名。

    注意不能只用 data/items.json: 那是"可用物品"清单, 不含 air/water 这类方块。
    """
    global _BLOCK_IDS
    if _BLOCK_IDS is None:
        ids: set = set()
        try:
            for line in _RAW_IDS.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[0] == "BLOCK":
                    ids.add(parts[1].replace("minecraft:", "", 1))
        except OSError:
            ids = set()
        _BLOCK_IDS = ids
    return _BLOCK_IDS


class BuildError(ValueError):
    """编译/校验失败: 消息直接回给模型。"""


# ---------- 沙箱 ----------
_FORBIDDEN_NAMES = {
    "exec", "eval", "compile", "open", "input", "__import__", "globals", "locals",
    "vars", "getattr", "setattr", "delattr", "breakpoint", "memoryview", "object",
    "type", "super", "help", "exit", "quit",
}
_ALLOWED_NODES = {
    ast.Module, ast.FunctionDef, ast.Return, ast.Assign, ast.AugAssign, ast.AnnAssign,
    ast.For, ast.While, ast.If, ast.Expr, ast.Call, ast.Attribute, ast.Name, ast.Load,
    ast.Store, ast.Constant, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Subscript,
    ast.List, ast.Tuple, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp,
    ast.GeneratorExp, ast.comprehension, ast.IfExp, ast.Pass, ast.Break, ast.Continue,
    ast.JoinedStr, ast.FormattedValue, ast.Slice, ast.keyword, ast.Starred,
    ast.arg, ast.arguments, ast.NamedExpr, ast.Assert,  # 函数/海象/自检断言
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or, ast.Eq, ast.NotEq, ast.Lt, ast.LtE,
    ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Is, ast.IsNot, ast.Invert, ast.BitAnd,
    ast.BitOr, ast.BitXor, ast.LShift, ast.RShift,
}


def validate_ast(source: str) -> None:
    """静态白名单: 没有 import / 文件 / 网络 / 反射 / dunder。"""
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as e:
        raise BuildError(f"程序语法错误(第 {e.lineno} 行): {e.msg}")
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODES:
            line = getattr(node, "lineno", None)
            where = f"第 {line} 行" if line else "程序里"
            raise BuildError(f"{where}不允许使用 {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise BuildError(f"程序里不允许使用 {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise BuildError(f"程序里不允许访问下划线属性 {node.attr}")
        if isinstance(node, ast.FunctionDef) and node.name.startswith("_"):
            raise BuildError(f"函数名不能以下划线开头: {node.name}")


_PRELUDE = r'''
import json, math, sys
OPS = []
MAX_OPS = int(sys.argv[1]) if len(sys.argv) > 1 else 20000

def _pt(p, what="坐标"):
    if isinstance(p, (list, tuple)) and len(p) == 3:
        try:
            return [int(p[0]), int(p[1]), int(p[2])]
        except (TypeError, ValueError):
            pass
    raise ValueError("%s 必须是 [u, v, w] 三个整数, 收到 %r" % (what, p))

def _norm(a, b):
    return ([min(a[0], b[0]), min(a[1], b[1]), min(a[2], b[2])],
            [max(a[0], b[0]), max(a[1], b[1]), max(a[2], b[2])])

class _Api:
    def __init__(self):
        self.origin = (0, 0, 0)
        self.facing = "south"
        self.ops = OPS
    def _add(self, d):
        if len(self.ops) >= MAX_OPS:
            raise ValueError("形状数超过上限 %d, 请用循环生成而不是逐个 set" % MAX_OPS)
        self.ops.append(d)
    def set(self, u, v, w, block, states=None):
        p = _pt((u, v, w))
        self._add({"op": "fill", "a": p, "b": list(p), "k": str(block), "s": states or None})
    def fill(self, a, b, block, states=None):
        lo, hi = _norm(_pt(a), _pt(b))
        self._add({"op": "fill", "a": lo, "b": hi, "k": str(block), "s": states or None})
    def box(self, a, b, block, hollow=False, states=None):
        lo, hi = _norm(_pt(a), _pt(b))
        self._add({"op": "box", "a": lo, "b": hi, "k": str(block), "hollow": bool(hollow), "s": states or None})
    def walls(self, a, b, block, thickness=1, states=None):
        lo, hi = _norm(_pt(a), _pt(b))
        self._add({"op": "walls", "a": lo, "b": hi, "k": str(block), "t": max(1, int(thickness)), "s": states or None})
    def frame(self, a, b, block, step=4, thickness=1, states=None):
        lo, hi = _norm(_pt(a), _pt(b))
        self._add({"op": "frame", "a": lo, "b": hi, "k": str(block), "step": max(1, int(step)), "t": max(1, int(thickness)), "s": states or None})
    def line(self, a, b, block, states=None):
        self._add({"op": "line", "a": _pt(a), "b": _pt(b), "k": str(block), "s": states or None})
    def plane(self, a, b, block, axis="v", states=None):
        lo, hi = _norm(_pt(a), _pt(b))
        self._add({"op": "plane", "a": lo, "b": hi, "k": str(block), "axis": str(axis), "s": states or None})
    def cylinder(self, center, radius, height, block, axis="v", hollow=False, states=None):
        self._add({"op": "cylinder", "c": _pt(center, "center"), "r": int(radius), "h": int(height),
                   "k": str(block), "axis": str(axis), "hollow": bool(hollow), "s": states or None})
    def sphere(self, center, radius, block, hollow=False, states=None):
        self._add({"op": "sphere", "c": _pt(center, "center"), "r": int(radius),
                   "k": str(block), "hollow": bool(hollow), "s": states or None})
    def pyramid(self, a, b, height, block, hollow=True, states=None):
        lo, hi = _norm(_pt(a), _pt(b))
        self._add({"op": "pyramid", "a": lo, "b": hi, "h": int(height), "k": str(block),
                   "hollow": bool(hollow), "s": states or None})
    def roof(self, a, b, block, style="gable", ridge="u", height=None, hollow=False, states=None):
        """屋顶: 逐层内缩的斜面。a/b 是屋顶底面范围(v 取屋檐那层)。

        style: gable(双坡/人字) / hip(四坡) / flat(平顶)
        ridge: 双坡屋脊沿 "u"(左右) 或 "w"(前后)
        height: 屋顶高; 不传则按跨度自动(每层内缩 1 格)
        hollow: True 只铺每层外圈(省料、留内部空间)
        """
        lo, hi = _norm(_pt(a), _pt(b))
        u0, v0, w0 = lo
        u1, v1, w1 = hi
        style = str(style).lower()
        if style == "flat":
            self.fill((u0, v0, w0), (u1, v1, w1), block, states)
            return
        if style == "gable":
            ridge = "w" if str(ridge).lower()[:1] == "w" else "u"
            span = (w1 - w0 + 1) if ridge == "u" else (u1 - u0 + 1)
            h = int(height) if height else (span + 1) // 2
            for i in range(max(1, h)):
                if ridge == "u":
                    z0, z1 = w0 + i, w1 - i
                    if z0 > z1:
                        break
                    x0, x1 = u0, u1
                else:
                    x0, x1 = u0 + i, u1 - i
                    if x0 > x1:
                        break
                    z0, z1 = w0, w1
                y = v0 + i
                if hollow:
                    self._ring(x0, x1, z0, z1, y, block, states)
                else:
                    self.fill((x0, y, z0), (x1, y, z1), block, states)
            return
        if style == "hip":
            h = int(height) if height else (min(u1 - u0, w1 - w0) + 1) // 2 + 1
            for i in range(max(1, h)):
                x0, x1, z0, z1 = u0 + i, u1 - i, w0 + i, w1 - i
                if x0 > x1 or z0 > z1:
                    break
                y = v0 + i
                if hollow:
                    self._ring(x0, x1, z0, z1, y, block, states)
                else:
                    self.fill((x0, y, z0), (x1, y, z1), block, states)
            return
        raise ValueError("roof 的 style 只能是 gable / hip / flat, 收到 %r" % (style,))

    def stair(self, a, b, block, axis="w", rise=1, run=1, states=None):
        """直跑楼梯: 沿 axis("w" 或 "u") 每 run 格升 rise 格, 一阶一格厚。"""
        lo, hi = _norm(_pt(a), _pt(b))
        u0, v0, w0 = lo
        u1, v1, w1 = hi
        rise = max(1, int(rise))
        run = max(1, int(run))
        if str(axis).lower()[:1] == "u":
            n = u1 - u0 + 1
            steps = (n + run - 1) // run
            for k in range(steps):
                x0 = u0 + k * run
                x1 = min(u1, x0 + run - 1)
                self.fill((x0, v0 + k * rise, w0), (x1, v0 + k * rise, w1), block, states)
        else:
            n = w1 - w0 + 1
            steps = (n + run - 1) // run
            for k in range(steps):
                z0 = w0 + k * run
                z1 = min(w1, z0 + run - 1)
                self.fill((u0, v0 + k * rise, z0), (u1, v0 + k * rise, z1), block, states)

    def _ring(self, x0, x1, z0, z1, y, block, states):
        """单层外圈(给 hollow 屋顶用): 上下两条 + 左右两条。"""
        self.fill((x0, y, z0), (x1, y, z0), block, states)
        if z1 != z0:
            self.fill((x0, y, z1), (x1, y, z1), block, states)
        if x1 > x0 and z1 > z0:
            self.fill((x0, y, z0 + 1), (x0, y, z1 - 1), block, states)
            self.fill((x1, y, z0 + 1), (x1, y, z1 - 1), block, states)

    def pattern(self, a, b, blocks, axis="v", states=None):
        lo, hi = _norm(_pt(a), _pt(b))
        self._add({"op": "pattern", "a": lo, "b": hi, "k": [str(x) for x in blocks],
                   "axis": str(axis), "s": states or None})
    def dirnum(self, where="front"):
        """局部方向 -> 旧式 direction 整数(0=南 1=西 2=北 3=东), 给门/床用。"""
        return {"south": 0, "west": 1, "north": 2, "east": 3}[self.dir(where)]
    def dir(self, where="front"):
        w = str(where).lower()
        f = self.facing
        table = {
            "south": {"front": "south", "back": "north", "left": "east", "right": "west"},
            "north": {"front": "north", "back": "south", "left": "west", "right": "east"},
            "east":  {"front": "east", "back": "west", "left": "north", "right": "south"},
            "west":  {"front": "west", "back": "east", "left": "south", "right": "north"},
        }
        return table.get(f, table["south"]).get(w, "south")

def _decode_rle(text, total):
    out = bytearray(total)
    pos = 0
    if text:
        for part in str(text).split(","):
            if not part:
                continue
            a, b = part.split(":")
            v = int(a, 36)
            n = int(b, 36)
            end = min(total, pos + n)
            for i in range(pos, end):
                out[i] = v
            pos = end
    return out

class _Snap:
    """只读世界快照(由 build_preview 的 scan 参数预取)。坐标同样用局部 u/v/w。"""
    def __init__(self, data, origin, facing):
        self.o = data["o"]
        self.s = data["s"]
        self.p = data["p"]
        self.cells = _decode_rle(data.get("rle"), self.s[0] * self.s[1] * self.s[2])
        self.origin = origin
        self.facing = facing
        self._air = set(i for i, n in enumerate(self.p) if str(n) in ("air", "cave_air", "void_air"))
    def _world(self, u, v, w):
        ox, oy, oz = self.origin
        f = self.facing
        if f == "south":
            return ox + u, oy + v, oz + w
        if f == "north":
            return ox - u, oy + v, oz - w
        if f == "east":
            return ox + w, oy + v, oz - u
        return ox - w, oy + v, oz + u
    def _idx(self, x, y, z):
        ox, oy, oz = self.o
        sx, sy, sz = self.s
        lx, ly, lz = x - ox, y - oy, z - oz
        if lx < 0 or ly < 0 or lz < 0 or lx >= sx or ly >= sy or lz >= sz:
            return -1
        return (ly * sz + lz) * sx + lx
    def block(self, u, v, w):
        x, y, z = self._world(u, v, w)
        i = self._idx(x, y, z)
        return "?" if i < 0 else self.p[self.cells[i]]
    def air(self, u, v, w):
        return self.block(u, v, w) in ("air", "cave_air", "void_air", "?")   # "?" = 未知
    def solid(self, u, v, w):
        b = self.block(u, v, w)
        return b not in ("air", "cave_air", "void_air", "?", "water", "lava", "flowing_water", "flowing_lava")
    def height(self, u, w):
        """该列在快照范围内最高的非空气方块的局部 v; 整列为空返回 None。"""
        sy = self.s[1]
        base_v = self.o[1] - self.origin[1]   # 快照底层对应的局部 v
        for ly in range(sy - 1, -1, -1):
            v = base_v + ly
            x, y, z = self._world(u, v, w)
            i = self._idx(x, y, z)
            if i < 0:
                continue
            if self.cells[i] not in self._air and self.p[self.cells[i]] != "?":
                return v
        return None

api = _Api()
data = json.loads(sys.stdin.read())
api.origin = tuple(data.get("origin") or (0, 0, 0))
api.facing = str(data.get("facing") or "south").lower()
snap = _Snap(data["snap"], api.origin, api.facing) if data.get("snap") else None
if snap is not None:
    api.block = snap.block
    api.air = snap.air
    api.solid = snap.solid
    api.height = snap.height
g = {"api": api, "math": math, "range": range, "len": len, "min": min, "max": max,
     "abs": abs, "int": int, "float": float, "round": round, "sum": sum,
     "enumerate": enumerate, "zip": zip, "list": list, "dict": dict, "tuple": tuple,
     "sorted": sorted, "reversed": reversed, "str": str, "bool": bool, "set": set,
     "True": True, "False": False, "None": None}
g["__builtins__"] = {
    "range": range, "len": len, "min": min, "max": max, "abs": abs, "int": int,
    "float": float, "round": round, "sum": sum, "enumerate": enumerate, "zip": zip,
    "list": list, "dict": dict, "tuple": tuple, "sorted": sorted, "reversed": reversed,
    "str": str, "bool": bool, "set": set, "True": True, "False": False, "None": None,
}
exec(compile(data["program"], "<build>", "exec"), g)
sys.stdout.write(json.dumps({"ops": OPS}))
'''


def _limit_resources():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (SANDBOX_MEM_MB * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_CPU, (int(SANDBOX_TIMEOUT), int(SANDBOX_TIMEOUT) + 1))
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    except Exception:
        pass


def run_program(program: str, origin: tuple, facing: str, snapshot: dict | None = None) -> list:
    """在隔离子进程里执行程序, 返回形状描述(ops)。snapshot 非空时程序可读世界。"""
    if len(program.encode("utf-8")) > MAX_PROGRAM:
        raise BuildError(f"程序太长(>{MAX_PROGRAM} 字节), 请用循环/函数压缩")
    validate_ast(program)
    payload = json.dumps({"program": program, "origin": list(origin),
                          "facing": facing, "snap": snapshot}, ensure_ascii=False)
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-S", "-c", _PRELUDE, str(MAX_OPS)],
            input=payload, capture_output=True, text=True,
            timeout=SANDBOX_TIMEOUT, preexec_fn=_limit_resources,
        )
    except subprocess.TimeoutExpired:
        raise BuildError(f"程序执行超过 {SANDBOX_TIMEOUT:.0f} 秒, 可能有死循环")
    if proc.returncode != 0:
        err = (proc.stderr or "").strip().splitlines()
        tail = err[-1] if err else f"退出码 {proc.returncode}"
        raise BuildError(f"程序执行失败: {tail}")
    try:
        return json.loads(proc.stdout)["ops"]
    except Exception as e:
        raise BuildError(f"程序输出无法解析: {e}")


# ---------- 坐标变换 ----------
def to_world(origin, facing, u, v, w):
    ox, oy, oz = origin
    if facing == "south":
        return ox + u, oy + v, oz + w
    if facing == "north":
        return ox - u, oy + v, oz - w
    if facing == "east":
        return ox + w, oy + v, oz - u
    return ox - w, oy + v, oz + u   # west


def from_world(origin, facing, x, y, z):
    """世界坐标 -> 局部 (u, v, w); to_world 的逆。"""
    ox, oy, oz = origin
    v = y - oy
    if facing == "south":
        return x - ox, v, z - oz
    if facing == "north":
        return ox - x, v, oz - z
    if facing == "east":
        return oz - z, v, x - ox
    return z - oz, v, ox - x   # west


# 不需要支撑的方块(靠墙/靠顶/贴地生长等), 悬空检查跳过
_ATTACHABLE = (
    "torch", "soul_torch", "lantern", "soul_lantern", "ladder", "lever", "button",
    "sign", "chain", "rail", "vine", "glow_lichen", "hanging_roots", "flower", "tulip",
    "orchid", "allium", "bluet", "daisy", "poppy", "sapling", "fern", "grass",
    "carpet", "pane", "candle", "flower_pot", "item_frame", "painting", "bell",
)
_LIQUIDS = ("water", "lava", "flowing_water", "flowing_lava")


def _needs_support(name: str) -> bool:
    base = name.replace("minecraft:", "", 1)
    if base in ("air", "cave_air", "void_air") or base in _LIQUIDS:
        return False
    return not any(k in base for k in _ATTACHABLE)


def check_symmetry(palette: list, cells: dict, origin, facing, spec: str) -> dict:
    """按局部 u 或 w 轴做镜像对称检查(只比方块类型, 不比朝向/状态)。

    spec = "u" / "w"(用包围盒中线) 或 "u:0" / "w:-2"(显式指定对称轴坐标)。
    """
    raw = (spec or "").strip().lower()
    axis = raw[:1]
    if axis not in ("u", "w"):
        raise BuildError('symmetry 只能是 "u"(左右) / "w"(前后), 可加 ":坐标" 指定对称轴')
    explicit = None
    if ":" in raw:
        try:
            explicit = int(raw.split(":", 1)[1])
        except ValueError:
            raise BuildError(f"symmetry 的对称轴坐标必须是整数: {raw}")
    local = {from_world(origin, facing, *p): pi for p, pi in cells.items()}
    us = [k[0] for k in local]
    ws = [k[2] for k in local]
    u0, u1, w0, w1 = min(us), max(us), min(ws), max(ws)
    center_u = 2 * explicit if explicit is not None else u0 + u1
    center_w = 2 * explicit if explicit is not None else w0 + w1
    mism = []
    for (u, v, w), pi in local.items():
        pu = center_u - u if axis == "u" else u
        pw = center_w - w if axis == "w" else w
        other = local.get((pu, v, pw))
        mine = palette[pi]["b"]
        if other is None:
            mism.append((u, v, w, mine.replace("minecraft:", ""), "空"))
        elif palette[other]["b"] != mine:
            mism.append((u, v, w, mine.replace("minecraft:", ""),
                         palette[other]["b"].replace("minecraft:", "")))
    return {"axis": axis, "center": (center_u if axis == "u" else center_w) / 2,
            "checked": len(local), "mismatch": len(mism), "samples": mism[:8]}


def check_floating(palette: list, cells: dict, snapshot: dict | None,
                   origin, facing) -> dict:
    """悬空检查: 写入的方块下方与四邻都没有支撑 -> 疑似悬空。

    只用「期望体积 ∪ 世界快照」判断, 不额外读世界; 没有快照就不检查(如实说明)。
    """
    if not snapshot:
        return {"checked": False, "reason": "没给 scan 快照, 无法判断支撑"}
    so = snapshot["o"]
    ss = snapshot["s"]
    rle = snapshot.get("rle") or ""
    dense = bytearray(ss[0] * ss[1] * ss[2])
    pos = 0
    if rle:
        for part in str(rle).split(","):
            if not part:
                continue
            a, b = part.split(":")
            v, n = int(a, 36), int(b, 36)
            end = min(len(dense), pos + n)
            for i in range(pos, end):
                dense[i] = v
            pos = end
    spal = snapshot.get("p") or []

    def solid(x, y, z) -> bool:
        pi = cells.get((x, y, z))
        if pi is not None:
            name = palette[pi]["b"]
        else:
            lx, ly, lz = x - so[0], y - so[1], z - so[2]
            if lx < 0 or ly < 0 or lz < 0 or lx >= ss[0] or ly >= ss[1] or lz >= ss[2]:
                return True     # 视野外当作可能被支撑, 不误报
            idx = (ly * ss[2] + lz) * ss[0] + lx
            name = spal[dense[idx]] if dense[idx] < len(spal) else "?"
        base = str(name).replace("minecraft:", "", 1)
        if base in ("?", "air", "cave_air", "void_air") or base in _LIQUIDS:
            return False
        return not any(k in base for k in _ATTACHABLE)

    floating = []
    for (x, y, z), pi in cells.items():
        if not _needs_support(palette[pi]["b"]):
            continue
        if not (solid(x, y - 1, z) or solid(x + 1, y, z) or solid(x - 1, y, z)
                or solid(x, y, z + 1) or solid(x, y, z - 1)):
            lu, lv, lw = from_world(origin, facing, x, y, z)
            floating.append((lu, lv, lw, palette[pi]["b"].replace("minecraft:", "")))
    return {"checked": True, "count": len(floating), "samples": floating[:8]}


# ---------- 体素化 ----------
def _circle(r, hollow):
    """圆盘/圆环的 (du, dw) 偏移。hollow 时只留外环。"""
    out = []
    rr = r * r
    inner = (r - 1) * (r - 1)
    for du in range(-r, r + 1):
        for dw in range(-r, r + 1):
            d = du * du + dw * dw
            if d > rr:
                continue
            if hollow and r > 0 and d < inner:
                continue
            out.append((du, dw))
    return out


def _line_cells(a, b):
    """三维 Bresenham。"""
    x0, y0, z0 = a
    x1, y1, z1 = b
    dx, dy, dz = abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)
    sx = 1 if x1 >= x0 else -1
    sy = 1 if y1 >= y0 else -1
    sz = 1 if z1 >= z0 else -1
    if dx >= dy and dx >= dz:
        p1, p2 = 2 * dy - dx, 2 * dz - dx
        while True:
            yield x0, y0, z0
            if x0 == x1:
                break
            if p1 >= 0:
                y0 += sy
                p1 -= 2 * dx
            if p2 >= 0:
                z0 += sz
                p2 -= 2 * dx
            p1 += 2 * dy
            p2 += 2 * dz
            x0 += sx
    elif dy >= dx and dy >= dz:
        p1, p2 = 2 * dx - dy, 2 * dz - dy
        while True:
            yield x0, y0, z0
            if y0 == y1:
                break
            if p1 >= 0:
                x0 += sx
                p1 -= 2 * dy
            if p2 >= 0:
                z0 += sz
                p2 -= 2 * dy
            p1 += 2 * dx
            p2 += 2 * dz
            y0 += sy
    else:
        p1, p2 = 2 * dy - dz, 2 * dx - dz
        while True:
            yield x0, y0, z0
            if z0 == z1:
                break
            if p1 >= 0:
                y0 += sy
                p1 -= 2 * dz
            if p2 >= 0:
                x0 += sx
                p2 -= 2 * dz
            p1 += 2 * dy
            p2 += 2 * dx
            z0 += sz


def _shape_cells(op):
    """把一条形状描述展开成局部坐标 + 方块说明。"""
    kind = op["op"]
    k = op.get("k")
    st = op.get("s")
    if kind == "fill":
        a, b = op["a"], op["b"]
        for x in range(a[0], b[0] + 1):
            for y in range(a[1], b[1] + 1):
                for z in range(a[2], b[2] + 1):
                    yield (x, y, z), k, st
    elif kind == "box":
        a, b = op["a"], op["b"]
        hollow = op.get("hollow")
        for x in range(a[0], b[0] + 1):
            for y in range(a[1], b[1] + 1):
                for z in range(a[2], b[2] + 1):
                    if hollow and a[0] < x < b[0] and a[1] < y < b[1] and a[2] < z < b[2]:
                        continue
                    yield (x, y, z), k, st
    elif kind == "walls":
        a, b = op["a"], op["b"]
        t = op.get("t", 1)
        for x in range(a[0], b[0] + 1):
            for y in range(a[1], b[1] + 1):
                for z in range(a[2], b[2] + 1):
                    if (x - a[0] < t or b[0] - x < t or z - a[2] < t or b[2] - z < t):
                        yield (x, y, z), k, st
    elif kind == "frame":
        a, b = op["a"], op["b"]
        step = op.get("step", 4)
        t = op.get("t", 1)
        us = list(range(a[0], b[0] + 1, step))
        ws = list(range(a[2], b[2] + 1, step))
        if b[0] not in us:
            us.append(b[0])
        if b[2] not in ws:
            ws.append(b[2])
        for u in us:
            for z in (a[2], b[2]):
                for du in range(t):
                    for y in range(a[1], b[1] + 1):
                        yield (u + du, y, z), k, st
        for w in ws:
            for x in (a[0], b[0]):
                for dw in range(t):
                    for y in range(a[1], b[1] + 1):
                        yield (x, y, w + dw), k, st
    elif kind == "line":
        for p in _line_cells(op["a"], op["b"]):
            yield p, k, st
    elif kind == "plane":
        a, b = op["a"], op["b"]
        axis = op.get("axis", "v")
        idx = {"u": 0, "v": 1, "w": 2}.get(str(axis).lower()[:1], 1)
        for x in range(a[0], b[0] + 1):
            for y in range(a[1], b[1] + 1):
                for z in range(a[2], b[2] + 1):
                    p = [x, y, z]
                    if p[idx] != a[idx]:
                        continue
                    yield (x, y, z), k, st
    elif kind == "cylinder":
        c = op["c"]
        r = op["r"]
        h = op["h"]
        hollow = op.get("hollow")
        axis = str(op.get("axis", "v")).lower()[:1]
        disc = _circle(r, hollow)
        for i in range(h):
            for du, dw in disc:
                if axis == "u":
                    yield (c[0] + i, c[1] + du, c[2] + dw), k, st
                elif axis == "w":
                    yield (c[0] + du, c[1] + dw, c[2] + i), k, st
                else:
                    yield (c[0] + du, c[1] + i, c[2] + dw), k, st
    elif kind == "sphere":
        c = op["c"]
        r = op["r"]
        hollow = op.get("hollow")
        rr = r * r
        inner = (r - 1) * (r - 1)
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    d = dx * dx + dy * dy + dz * dz
                    if d > rr or (hollow and r > 0 and d < inner):
                        continue
                    yield (c[0] + dx, c[1] + dy, c[2] + dz), k, st
    elif kind == "pyramid":
        a, b = op["a"], op["b"]
        h = op["h"]
        hollow = op.get("hollow", True)
        for i in range(h):
            x0, x1 = a[0] + i, b[0] - i
            z0, z1 = a[2] + i, b[2] - i
            if x0 > x1 or z0 > z1:
                break
            y = a[1] + i
            for x in range(x0, x1 + 1):
                for z in range(z0, z1 + 1):
                    if hollow and x0 < x < x1 and z0 < z < z1:
                        continue
                    yield (x, y, z), k, st
    elif kind == "pattern":
        a, b = op["a"], op["b"]
        blocks = k
        if not isinstance(blocks, list) or not blocks:
            raise BuildError("pattern 的 blocks 必须是非空列表")
        axis = str(op.get("axis", "v")).lower()[:1]
        n = len(blocks)
        for x in range(a[0], b[0] + 1):
            for y in range(a[1], b[1] + 1):
                for z in range(a[2], b[2] + 1):
                    i = {"u": x, "v": y, "w": z}.get(axis, y)
                    yield (x, y, z), blocks[i % n], st
    else:
        raise BuildError(f"未知形状 {kind}")


def _expand_multiblock(base: str, pos: tuple, states: dict | None):
    """把多格方块展开成 [(世界坐标, states), ...]; 单格方块原样返回。

    实测(1.21.0.03, 脚本 API setPermutation/fillBlocks 路径):
      门   wooden_door / *_door: 只写下半会被引擎删除 → 必须写上下两半
          (upper_block_bit=false / true)
      床   bed: 写入的那一格**永远被当作床头**, 床尾由引擎自动放在
          direction 方向(实测 0=北 1=东 2=南 3=西) → 只写一格, 不要写两格(会互相翻转)
      高草 tall_grass 等双格植物: 与门同类, 写上下两半(upper_block_bit)
    """
    st = dict(states or {})
    x, y, z = pos
    if base.endswith("_door") or base == "wooden_door":
        st.pop("head_piece_bit", None)
        return [((x, y, z), {**st, "upper_block_bit": False}),
                ((x, y + 1, z), {**st, "upper_block_bit": True})]
    if base == "bed":
        d = st.get("direction", 0)
        if isinstance(d, str):
            d = CARD2NUM.get(d.lower(), 0)
        try:
            d = int(d)
        except (TypeError, ValueError):
            d = 0
        st.pop("head_piece_bit", None)
        return [((x, y, z), {**st, "direction": d if d in BED_DIR else 0})]
    if base in TALL_PLANTS:
        st.pop("head_piece_bit", None)
        return [((x, y, z), {**st, "upper_block_bit": False}),
                ((x, y + 1, z), {**st, "upper_block_bit": True})]
    return [((x, y, z), st or None)]


def voxelize(ops: list, origin: tuple, facing: str, valid_blocks=None):
    """形状 → (palette, cells dict, bounds)。后写的覆盖先写的(KEEP 不参与)。"""
    cells: dict = {}
    palette: list = [None]          # 0 固定 KEEP
    index: dict = {}
    for op in ops:
        for (u, v, w), block, states in _shape_cells(op):
            name = str(block)
            if not name.startswith("minecraft:"):
                name = "minecraft:" + name
            base = name.split("[", 1)[0].replace("minecraft:", "", 1)
            if valid_blocks is not None and base not in valid_blocks:
                raise BuildError(f"未知方块 {name}; 先用 find_items 查准确 ID(基岩版)")
            for wpos, wstates in _expand_multiblock(base, to_world(origin, facing, u, v, w), states):
                key = (name, json.dumps(wstates, sort_keys=True) if wstates else "")
                pi = index.get(key)
                if pi is None:
                    if len(palette) >= MAX_PALETTE:
                        raise BuildError(f"用到的方块种类超过 {MAX_PALETTE} 种, 请减少配色")
                    pi = len(palette)
                    index[key] = pi
                    palette.append({"b": name, **({"s": wstates} if wstates else {})})
                cells[wpos] = pi
    if not cells:
        raise BuildError("程序没有放置任何方块")
    xs = [p[0] for p in cells]
    ys = [p[1] for p in cells]
    zs = [p[2] for p in cells]
    bounds = (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))
    size = (bounds[3] - bounds[0] + 1, bounds[4] - bounds[1] + 1, bounds[5] - bounds[2] + 1)
    if any(s > MAX_BOUNDS for s in size):
        raise BuildError(f"包围盒 {size[0]}×{size[1]}×{size[2]} 单轴超过 {MAX_BOUNDS}, 请拆成多次")
    volume = size[0] * size[1] * size[2]
    if volume > MAX_VOLUME:
        raise BuildError(limit_hint("包围盒体积", volume, MAX_VOLUME, "40×40×40")
                         + " 建议按模块（地基/墙/屋顶）分开提交。")
    if len(cells) > MAX_CELLS:
        raise BuildError(limit_hint("写入格数", len(cells), MAX_CELLS, "40×40×40"))
    return palette, cells, bounds


def encode(palette: list, cells: dict, bounds: tuple, origin: tuple, facing: str) -> dict:
    """稠密化 + 分层 RLE(y 层 → z 行 → x, x 最快)。"""
    x0, y0, z0, x1, y1, z1 = bounds
    sx, sy, sz = x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1
    dense = bytearray(sx * sy * sz)
    for (x, y, z), pi in cells.items():
        dense[((y - y0) * sz + (z - z0)) * sx + (x - x0)] = pi
    parts = []
    i = 0
    n = len(dense)
    while i < n:
        v = dense[i]
        j = i + 1
        while j < n and dense[j] == v:
            j += 1
        parts.append(f"{v:x}:{j - i:x}" if False else f"{_b36(v)}:{_b36(j - i)}")
        i = j
    return {
        "o": [x0, y0, z0], "s": [sx, sy, sz],
        "p": palette[1:], "rle": ",".join(parts),
        "origin": list(origin), "facing": facing,
    }


def _b36(n: int) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    if n == 0:
        return "0"
    out = []
    while n:
        n, r = divmod(n, 36)
        out.append(digits[r])
    return "".join(reversed(out))


def decode_volume(o, s, palette: list, rle: str, skip_zero: bool = True):
    """palette + 分层 RLE -> (palette, cells, bounds)。渲染/测试用(与行为包同一套解码)。"""
    sx, sy, sz = int(s[0]), int(s[1]), int(s[2])
    total = sx * sy * sz
    dense = bytearray(total)
    pos = 0
    if rle:
        for part in str(rle).split(","):
            if not part:
                continue
            a, b = part.split(":")
            v, n = int(a, 36), int(b, 36)
            end = min(total, pos + n)
            for i in range(pos, end):
                dense[i] = v
            pos = end
    cells = {}
    layer = sx * sz
    for i, v in enumerate(dense):
        if skip_zero and v == 0:
            continue
        y = int(o[1]) + i // layer
        rem = i % layer
        cells[(int(o[0]) + rem % sx, y, int(o[2]) + rem // sx)] = v
    bounds = (int(o[0]), int(o[1]), int(o[2]),
              int(o[0]) + sx - 1, int(o[1]) + sy - 1, int(o[2]) + sz - 1)
    return list(palette), cells, bounds


def decode_payload(payload: dict):
    """建造 payload(索引 0 = KEEP) -> (palette, cells, bounds)。"""
    return decode_volume(payload["o"], payload["s"],
                         [None] + list(payload.get("p") or ()), payload.get("rle") or "")


def compile_build(program: str, origin: tuple, facing: str, valid_blocks=None,
                  snapshot: dict | None = None, symmetry: str | None = None) -> tuple:
    """程序 → (payload, stats)。payload 直接上行给行为包。"""
    facing = (facing or "south").lower()
    if facing not in FACINGS:
        raise BuildError(f"facing 必须是 {'/'.join(FACINGS)}, 收到 {facing}")
    try:
        origin = tuple(int(v) for v in origin)
    except (TypeError, ValueError):
        raise BuildError("origin 必须是三个整数 [x, y, z]")
    if len(origin) != 3:
        raise BuildError("origin 必须是三个整数 [x, y, z]")
    ops = run_program(program, origin, facing, snapshot)
    palette, cells, bounds = voxelize(ops, origin, facing, valid_blocks)
    payload = encode(palette, cells, bounds, origin, facing)
    checks = {}
    if symmetry:
        checks["symmetry"] = check_symmetry(palette, cells, origin, facing, symmetry)
    checks["floating"] = check_floating(palette, cells, snapshot, origin, facing)
    stats = {
        "ops": len(ops), "cells": len(cells), "palette": len(palette) - 1,
        "bounds": bounds, "size": (bounds[3] - bounds[0] + 1,
                                   bounds[4] - bounds[1] + 1,
                                   bounds[5] - bounds[2] + 1),
        "payload_bytes": len(json.dumps(payload, ensure_ascii=False)),
        "snapshot": bool(snapshot),
        "snapshot_unloaded": (snapshot or {}).get("unloaded", 0),
        "checks": checks,
    }
    return payload, stats
