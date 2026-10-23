"""视觉反馈: 把体素体积渲染成 ASCII 图与 PNG。

为什么需要: 模型看不到截图, 但"比例对不对/屋顶收口/立面节奏"这类判断,
用一张立面字符图就能看清; 玩家则可以直接打开导出的 PNG。

依赖方向: 叶子模块, 只 import 标准库; 不 import 项目内模块。
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

def name_of(entry) -> str:
    """调色板条目可能是 "minecraft:x" 或 {"b": "minecraft:x", "s": {...}}。"""
    if isinstance(entry, dict):
        entry = entry.get("b")
    return str(entry or "").replace("minecraft:", "", 1)


# 字符图符号: 空气固定 "."(最好认), 其余按调色板顺序取, "?" 留给未知/未加载
SYMBOLS = "#=+*%@&$~^<>oOxXvVzZ0123456789"

# 方块族 -> 颜色(做 PNG 用)。没命中的走稳定哈希色, 保证同一方块每次同色。
_FAMILY_COLORS = [
    (("stone", "cobble", "deepslate", "andesite", "granite", "diorite", "tuff", "basalt"),
     (128, 128, 132)),
    (("brick",), (150, 90, 80)),
    (("terracotta",), (152, 94, 67)),
    (("concrete",), (200, 200, 200)),
    (("planks", "log", "wood", "bamboo"), (156, 118, 72)),
    (("leaves", "moss", "grass", "fern", "vine", "azalea"), (86, 140, 60)),
    (("water", "ice"), (60, 110, 190)),
    (("glass",), (170, 220, 230)),
    (("sand",), (222, 210, 160)),
    (("snow",), (240, 245, 250)),
    (("lava", "magma", "fire"), (220, 110, 40)),
    (("glowstone", "sea_lantern", "lantern", "torch", "candle", "shroomlight"),
     (250, 220, 120)),
    (("copper",), (180, 120, 90)),
    (("gold", "brass"), (230, 200, 90)),
    (("iron", "anvil"), (190, 190, 195)),
    (("netherite", "black"), (60, 55, 60)),
    (("quartz", "white"), (238, 238, 232)),
    (("wool", "carpet"), (190, 170, 190)),
]


def block_color(name: str) -> tuple:
    base = str(name).replace("minecraft:", "", 1)
    for keys, rgb in _FAMILY_COLORS:
        if any(k in base for k in keys):
            return rgb
    h = 0
    for ch in base:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return (90 + (h & 0x3F), 90 + ((h >> 6) & 0x3F), 90 + ((h >> 12) & 0x3F))


def symbols_for(palette: list) -> list:
    """调色板索引 -> 单字符。空气固定 '.', 其余按顺序分配。"""
    out, k = [], 0
    for name in palette:
        base = name_of(name)
        if base in ("air", "cave_air", "void_air", "?"):
            out.append(".")
        elif not base:
            out.append(".")
        else:
            out.append(SYMBOLS[k] if k < len(SYMBOLS) else "?")
            k += 1
    return out


AIR_TYPES = {"air", "cave_air", "void_air", "?"}


def _air_indices(palette) -> set:
    out = set()
    for i, name in enumerate(palette or ()):
        base = name_of(name)
        if not base or base in AIR_TYPES:
            out.add(i)
    return out


def _grid(palette, cells, bounds, view: str):
    """把体素投影成二维索引网格(行=从上到下)。返回 (rows, 说明文字)。

    rows 里是调色板索引或 None(空); 调用方用 symbols_for(palette) 取字符。
    """
    x0, y0, z0, x1, y1, z1 = bounds
    air = _air_indices(palette)

    def idx_at(p):
        pi = cells.get(p)
        return None if pi is None or pi in air else pi

    if view == "top":
        rows = []
        for z in range(z0, z1 + 1):
            row = []
            for x in range(x0, x1 + 1):
                hit = None
                for y in range(y1, y0 - 1, -1):
                    hit = idx_at((x, y, z))
                    if hit is not None:
                        break
                row.append(hit)
            rows.append(row)
        return rows, "俯视(行=z 北→南, 列=x 西→东), 每格显示最顶层方块"

    if view in ("front", "back"):
        zs = range(z0, z1 + 1) if view == "front" else range(z1, z0 - 1, -1)
        rows = []
        for y in range(y1, y0 - 1, -1):
            row = []
            for x in range(x0, x1 + 1):
                hit = None
                for z in zs:
                    hit = idx_at((x, y, z))
                    if hit is not None:
                        break
                row.append(hit)
            rows.append(row)
        side = "正面" if view == "front" else "背面"
        return rows, f"{side}立面(行=y 高→低, 列=x 西→东), 显示最先看到的方块"

    if view in ("left", "right"):
        xs = range(x0, x1 + 1) if view == "right" else range(x1, x0 - 1, -1)
        rows = []
        for y in range(y1, y0 - 1, -1):
            row = []
            for z in range(z0, z1 + 1):
                hit = None
                for x in xs:
                    hit = idx_at((x, y, z))
                    if hit is not None:
                        break
                row.append(hit)
            rows.append(row)
        side = "右侧" if view == "right" else "左侧"
        return rows, f"{side}立面(行=y 高→低, 列=z 北→南)"

    if view == "iso":
        pts = []
        for (x, y, z), pi in cells.items():
            if pi in air:
                continue
            pts.append((x + z, y, x - z, (x + z) // 2 - y, pi))
        if not pts:
            return [[None]], "等距视图(空)"
        pts.sort(key=lambda t: (t[0], t[1]))            # x+z 越大越靠近观察者, 后画覆盖
        canvas = {}
        for _d, _y, sx, sy, pi in pts:
            canvas[(sx, sy)] = pi
        xs = [k[0] for k in canvas]
        ys = [k[1] for k in canvas]
        # sy 越小越靠上 -> 从 min(ys) 开始
        rows = [[canvas.get((x, y)) for x in range(min(xs), max(xs) + 1)]
                for y in range(min(ys), max(ys) + 1)]
        return rows, "等距视图(斜 45°, 越靠上越高)"

    raise ValueError(f"未知视角 {view}(可用 top/front/back/left/right/iso)")


def ascii_view(palette: list, cells: dict, bounds: tuple, view: str = "front",
               max_width: int = 96, max_rows: int = 48) -> str:
    """渲染成字符图 + 图例。超宽/超高会按整数倍降采样(提示里说明)。"""
    syms = symbols_for(palette)
    rows, note = _grid(palette, cells, bounds, view)
    if len(rows[0]) > max_width or len(rows) > max_rows:
        step = 1
        while len(rows[0]) // step > max_width or len(rows) // step > max_rows:
            step += 1
        rows = [row[::step] for row in rows[::step]]
        note += f"(已按 1/{step} 降采样)"
    out = [note]
    for row in rows:
        out.append("".join("." if pi is None else (syms[pi] if pi < len(syms) else "?")
                           for pi in row))
    used = []
    for row in rows:
        for pi in row:
            if pi is not None and pi not in used:
                used.append(pi)
    parts = [f"{syms[i] if i < len(syms) else '?'}={name_of(palette[i])}"
             for i in used[:20]]
    if parts:
        out.append("图例: " + "  ".join(parts))
    return "\n".join(out)


def _pixels(palette: list, cells: dict, bounds: tuple, view: str):
    rows, _ = _grid(palette, cells, bounds, view)
    px = []
    for row in rows:
        line = []
        for pi in row:
            line.append((246, 246, 242, 255) if pi is None
                        else (*block_color(name_of(palette[pi])), 255))
        px.append(line)
    return px


def write_png(path: str | Path, pixels: list, scale: int = 1) -> Path:
    """最小 PNG 写入(标准库 zlib+struct), 1 像素 1 格, 可选整数放大。"""
    h = len(pixels)
    w = len(pixels[0]) if h else 0
    scale = max(1, int(scale))
    raw = bytearray()
    for row in pixels:
        line = bytearray()
        for px in row:
            line += bytes(px) * scale
        for _ in range(scale):
            raw += b"\x00" + bytes(line)          # 每行前缀 filter=0
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w * scale, h * scale, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
           + chunk(b"IEND", b""))
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(png)
    return p


def render(palette: list, cells: dict, bounds: tuple, views: list, png_dir: Path | None,
           name: str = "build", scale: int = 6) -> tuple:
    """返回 (文本, [png 路径])。"""
    chunks, pngs = [], []
    for view in views:
        text = ascii_view(palette, cells, bounds, view)
        chunks.append(text)
        if png_dir is not None:
            try:
                px = _pixels(palette, cells, bounds, view)
                pngs.append(write_png(png_dir / f"{name}-{view}.png", px, scale))
            except Exception:
                pass
    return "\n\n".join(chunks), pngs
