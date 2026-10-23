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

# 本引擎单格写入会留下残缺另一半的多格方块(门/床/高草等)
UNSUPPORTED = {
    "bed", "tall_grass", "large_fern", "sunflower", "lilac", "rose_bush", "peony",
    "small_dripleaf", "big_dripleaf", "big_dripleaf_stem", "tall_dripleaf", "pitcher_plant",
    "cave_vines", "cave_vines_body_with_berries", "cave_vines_head_with_berries",
    "hanging_roots", "spore_blossom",
}


_RAW_IDS = Path(__file__).resolve().parent.parent / "data" / "raw_ids.txt"
_BLOCK_IDS: set | None = None


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
            raise BuildError(f"程序里不允许使用 {type(node).__name__}(第 {getattr(node, 'lineno', '?')} 行)")
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
    def pattern(self, a, b, blocks, axis="v", states=None):
        lo, hi = _norm(_pt(a), _pt(b))
        self._add({"op": "pattern", "a": lo, "b": hi, "k": [str(x) for x in blocks],
                   "axis": str(axis), "s": states or None})
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

api = _Api()
data = json.loads(sys.stdin.read())
api.origin = tuple(data.get("origin") or (0, 0, 0))
api.facing = str(data.get("facing") or "south").lower()
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


def run_program(program: str, origin: tuple, facing: str) -> list:
    """在隔离子进程里执行程序, 返回形状描述(ops)。"""
    if len(program.encode("utf-8")) > MAX_PROGRAM:
        raise BuildError(f"程序太长(>{MAX_PROGRAM} 字节), 请用循环/函数压缩")
    validate_ast(program)
    payload = json.dumps({"program": program, "origin": list(origin),
                          "facing": facing}, ensure_ascii=False)
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
            key = (name, json.dumps(states, sort_keys=True) if states else "")
            pi = index.get(key)
            if pi is None:
                if len(palette) >= MAX_PALETTE:
                    raise BuildError(f"用到的方块种类超过 {MAX_PALETTE} 种, 请减少配色")
                pi = len(palette)
                index[key] = pi
                palette.append({"b": name, **({"s": states} if states else {})})
            cells[to_world(origin, facing, u, v, w)] = pi
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
        raise BuildError(f"包围盒体积 {volume} 格超过上限 {MAX_VOLUME}, 请拆成多次或缩小范围")
    if len(cells) > MAX_CELLS:
        raise BuildError(f"写入格数 {len(cells)} 超过上限 {MAX_CELLS}")
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


def compile_build(program: str, origin: tuple, facing: str, valid_blocks=None) -> tuple:
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
    ops = run_program(program, origin, facing)
    palette, cells, bounds = voxelize(ops, origin, facing, valid_blocks)
    payload = encode(palette, cells, bounds, origin, facing)
    stats = {
        "ops": len(ops), "cells": len(cells), "palette": len(palette) - 1,
        "bounds": bounds, "size": (bounds[3] - bounds[0] + 1,
                                   bounds[4] - bounds[1] + 1,
                                   bounds[5] - bounds[2] + 1),
        "payload_bytes": len(json.dumps(payload, ensure_ascii=False)),
    }
    return payload, stats
