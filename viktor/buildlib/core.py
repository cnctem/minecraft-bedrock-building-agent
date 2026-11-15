# Trusted build-library source, loaded into the build sandbox before user code.
# All coordinates are local (u, v, w); functions only emit ordinary api ops.

class _LibBase:
    def __init__(self, api):
        self.api = api

    def span(self, a, b):
        return (min(int(a), int(b)), max(int(a), int(b)))

    def jround(self, value):
        # Java Math.round semantics (half-up), unlike Python's bankers rounding.
        return math.floor(float(value) + 0.5)

    # Java 版名字 / 常见误写 → 基岩版 (ID, states)。states 为 None 表示无状态。
    _ALIAS = {
        # 1.21.132 起服务器 ID 已改成 Java 版名字(stone_bricks / quartz_pillar /
        # iron_chain / dandelion / sugar_cane 都是真 ID), 所以这些只需留旧名反查。
        "stonebrick": ("stone_bricks", None),
        "bricks": ("brick_block", None),
        "dirt_path": ("grass_path", None),
        "chain": ("iron_chain", None),
        "oak_door": ("wooden_door", None),
        "smooth_quartz_block": ("smooth_quartz", None),
        "stonebrick_stairs": ("stone_brick_stairs", None),
        "stonebrick_slab": ("stone_brick_slab", None),
        "cobblestone_stairs": ("stone_stairs", None),
        "cobweb": ("web", None),
        "snow_block": ("snow", None),
        "dead_bush": ("deadbush", None),
        "note_block": ("noteblock", None),
        "oak_fence_gate": ("fence_gate", None),
        "oak_pressure_plate": ("wooden_pressure_plate", None),
        "red_sand": ("sand", {"sand_type": "red"}),
        "terracotta": ("hardened_clay", None),
        "spruce_slabs": ("spruce_slab", None),
        "red_bed": ("bed", None), "white_bed": ("bed", None),
        "light_blue_bed": ("bed", None),
        "potted_fern": ("flower_pot", None), "potted_poppy": ("flower_pot", None),
        "potted_dandelion": ("flower_pot", None),
        "potted_azalea_bush": ("flower_pot", None),
        "potted_oak_sapling": ("flower_pot", None),
        "potted_red_mushroom": ("flower_pot", None),
        "red_banner": ("red_wool", None), "blue_banner": ("blue_wool", None),
        "white_banner": ("white_wool", None),
        "yellow_flower": ("dandelion", None),
        "reeds": ("sugar_cane", None),
        "stone_brick": ("stone_bricks", None),
        "grass": ("short_grass", None),
        "wooden_slab": ("oak_slab", None),
        "log": ("oak_log", None),
        "leaves": ("oak_leaves", None),
    }

    def resolve(self, value, default="stonebrick"):
        """方块名 → (基岩版 ID, states)。空值回退 default; 未知名字原样返回(由编译器报错)。"""
        if value is None or str(value).strip() in ("", "null", "None"):
            value = default
        b = str(value).strip().lower()
        if b.startswith("minecraft:"):
            b = b[10:]
        alias = globals().get("_BLOCK_ALIAS") or self._ALIAS
        return alias.get(b, (b, None))

    def block(self, value, default="stonebrick"):
        return self.resolve(value, default)[0]

    def put(self, u, v, w, block, states=None):
        name, alias_states = self.resolve(block)
        self.api.set(int(u), int(v), int(w), name,
                     states if states is not None else alias_states)

    def fill(self, a, b, block, states=None):
        name, alias_states = self.resolve(block)
        self.api.fill(a, b, name, states if states is not None else alias_states)

    def box(self, a, b, block, hollow=False):
        name, alias_states = self.resolve(block)
        self.api.box(a, b, name, hollow=hollow, states=alias_states)

    def line(self, a, b, block):
        name, alias_states = self.resolve(block)
        self.api.line(a, b, name, states=alias_states)

    def face(self, facing="front"):
        f = str(facing or "front").strip().lower()
        return {
            "front": (0, 1), "south": (0, 1), "s": (0, 1),
            "back": (0, -1), "north": (0, -1), "n": (0, -1),
            "right": (1, 0), "east": (1, 0), "e": (1, 0),
            "left": (-1, 0), "west": (-1, 0), "w": (-1, 0),
        }.get(f, (0, 1))

    def axis_u(self, axis="u"):
        return str(axis or "u").strip().lower() not in ("w", "z")

    def along_u(self, facing):
        du, dw = self.face(facing)
        return dw != 0

    def perpendicular(self, facing):
        du, dw = self.face(facing)
        return (-dw, du)

    def stair(self, block):
        b = self.block(block, "spruce_stairs")
        if b.endswith("_stairs"):
            return b
        special = {
            "brick_block": "brick_stairs", "quartz_block": "quartz_stairs",
            "purpur_block": "purpur_stairs", "deepslate": "cobbled_deepslate_stairs",
            "stone_bricks": "stone_brick_stairs", "mud_bricks": "mud_brick_stairs",
            "tuff_bricks": "tuff_brick_stairs", "deepslate_bricks": "deepslate_brick_stairs",
            "deepslate_tiles": "deepslate_tile_stairs",
        }
        if b in special:
            return special[b]
        if b.endswith("_bricks"):
            return b[:-7] + "_brick_stairs"
        if b.endswith("_tiles"):
            return b[:-6] + "_tile_stairs"
        if b.endswith("_planks"):
            return b[:-7] + "_stairs"
        if b.endswith("_block"):
            b = b[:-6]
        return b + "_stairs"

    def stair_states(self, facing="front", upside=False):
        du, dw = self.face(facing)
        # Bedrock weirdo_direction: 0 east, 1 west, 2 south, 3 north.
        d = 0 if du > 0 else (1 if du < 0 else (2 if dw > 0 else 3))
        return {"weirdo_direction": d, "upside_down_bit": bool(upside)}

    def help(self, name=None):
        """函数目录: 不传参数列出各类别函数, 传名字给出签名与一句话说明。"""
        spec = globals().get("_LIB_SIGNATURES") or {}
        cats = globals().get("_LIB_CATEGORIES") or {}
        if not spec:
            raise ValueError("函数目录未注入; 见技能 mc-architecture 的 functions-index.md")
        if not name:
            return "\n".join("[%s] %s" % (cat, " ".join(names)) for cat, names in cats.items())
        key = str(name).strip()
        if key in spec:
            return "%s\n接口: %s" % (key, spec[key])
        hits = [k for k in spec if key in k]
        if not hits:
            raise ValueError("没有函数 %r; 先用 api.lib.help() 看类别清单" % key)
        return "\n".join("%s: %s" % (k, spec[k]) for k in hits[:20])

    def option(self, opts, key, default=None):
        if not opts:
            return default
        value = opts.get(key, default)
        return default if value is None else value

    def hash_mix(self, key, seed):
        # Java-compatible signed 32-bit integer hash; no random module needed.
        mask = 0xffffffff
        h = (int(key) * -1640531535 + int(seed) * -2048144777) & mask
        h ^= h >> 16
        h = (h * 2146121005) & mask
        h ^= h >> 15
        h = (h * -2073254261) & mask
        h ^= h >> 16
        return h

    def hash2(self, u, w, seed):
        k = (int(u) * 73856093) ^ (int(w) * 19349663)
        return ((self.hash_mix(k, seed) >> 8) & 0xffffff) / 16777216.0

    def hash3(self, u, v, w, seed):
        k = (int(u) * 73856093) ^ (int(v) * 83492791) ^ (int(w) * 19349663)
        return ((self.hash_mix(k, seed) >> 8) & 0xffffff) / 16777216.0

    def noise2(self, x, z, seed):
        x0, z0 = math.floor(x), math.floor(z)
        fx, fz = x - x0, z - z0
        fx, fz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
        n00 = self.hash2(x0, z0, seed)
        n10 = self.hash2(x0 + 1, z0, seed)
        n01 = self.hash2(x0, z0 + 1, seed)
        n11 = self.hash2(x0 + 1, z0 + 1, seed)
        a = n00 + (n10 - n00) * fx
        b = n01 + (n11 - n01) * fx
        return a + (b - a) * fz

    def fbm2(self, x, z, octaves, seed):
        total = norm = 0.0
        amp, freq = 1.0, 1.0
        for i in range(max(1, min(8, int(octaves)))):
            total += self.noise2(x * freq, z * freq, seed + i * 1013) * amp
            norm += amp
            amp *= 0.5
            freq *= 2.0
        return total / norm if norm else 0.5

    def auto_seed(self, a, b, c):
        h = self.hash_mix(int(a) * 73856093 ^ int(b) * 19349663 ^ int(c) * 83492791,
                          0x5eed5eed)
        return h or 1

    def polygon_ring(self, du, dw, radius, sides):
        r = int(radius)
        if r <= 0:
            return du == 0 and dw == 0
        dist = math.hypot(du, dw)
        if dist < 0.5:
            return False
        theta = math.atan2(dw, du)
        sector = math.pi * 2 / max(3, int(sides))
        a = theta - round(theta / sector) * sector
        edge = r * math.cos(sector / 2) / max(1e-6, math.cos(a))
        return edge - 0.85 <= dist <= edge + 0.6

    def juzhe(self, t):
        if t <= 0:
            return 0.0
        if t >= 1:
            return 1.0
        return t ** 1.65

    def ring(self, u1, w1, u2, w2, v, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        self.fill((ua, v, wa), (ub, v, wa), block)
        if wb != wa:
            self.fill((ua, v, wb), (ub, v, wb), block)
        if ub > ua and wb - wa > 1:
            self.fill((ua, v, wa + 1), (ua, v, wb - 1), block)
            self.fill((ub, v, wa + 1), (ub, v, wb - 1), block)

    def ellipse_blob(self, cu, cv, cw, ru, rv, rw, block, seed=1, density=1.0):
        ru, rv, rw = max(1, int(ru)), max(1, int(rv)), max(1, int(rw))
        for dv in range(-rv, rv + 1):
            for dw in range(-rw, rw + 1):
                for du in range(-ru, ru + 1):
                    d = du * du / (ru * ru) + dv * dv / (rv * rv) + dw * dw / (rw * rw)
                    if d <= 1 and self.hash3(cu + du, cv + dv, cw + dw, seed) <= density:
                        self.put(cu + du, cv + dv, cw + dw, block)
