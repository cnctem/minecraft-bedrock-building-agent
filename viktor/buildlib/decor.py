class _DecorLib:
    def _place_opts(self, u, v, w, block, opts, key, default=None):
        return self.put(u, v, w, self.option(opts, key, default) if default is not None else (opts or {}).get(key) or block)

    def eaves_trim(self, u1, v, w1, u2, w2, overhang, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        for i in range(1, max(1, int(overhang)) + 1):
            self.ring(ua - i, wa - i, ub + i, wb + i, v, block)

    def wall_trim(self, u1, v, w1, u2, w2, block):
        self.ring(u1, w1, u2, w2, v, block)

    def crown_molding(self, u1, v, w1, u2, w2, block):
        self.ring(u1, w1, u2, w2, v, block)

    def window_unit(self, cu, v, cw, width, height, facing, frame, glass):
        """窗套: 墙面(贴皮)一圈框 + 内凹 1 格的玻璃 + 上下窗台线。

        需要已有墙: 它是“装饰皮”, **不挖洞**。要真的通透就先 fill 留洞再套。
        """
        width, height = max(1, int(width)), max(1, int(height))
        du, dw = self.face(facing)            # 外法线
        pu, pw = self.perpendicular(facing)   # 沿墙面
        start = -(width - 1) // 2
        for a in range(width):
            for h in range(height):
                edge = a in (0, width - 1) or h in (0, height - 1)
                u = cu + pu * (start + a)
                w = cw + pw * (start + a)
                self.put(u, v + h, w, frame)
                if not edge:
                    self.put(u - du, v + h, w - dw, glass)   # 玻璃退一格(内凹)
        for a in range(-1, width + 1):
            u, w = cu + pu * (start + a), cw + pw * (start + a)
            self.put(u, v - 1, w, frame)      # 窗台
            self.put(u, v + height, w, frame)  # 过梁
    def flower_box(self, cu, v, cw, width, facing):
        pu, pw = self.perpendicular(facing)
        start = -(max(1, int(width)) - 1) // 2
        for i in range(max(1, int(width))):
            self.put(cu + pu * (start + i), v, cw + pw * (start + i), "dirt")
            self.put(cu + pu * (start + i), v + 1, cw + pw * (start + i),
                     ("poppy", "yellow_flower", "oxeye_daisy", "cornflower")[(i % 4)])

    def lamp_post(self, u, v, w, height, pole="oak_fence", light="lantern"):
        self.fill((u, v, w), (u, v + max(1, int(height)) - 1, w), pole)
        self.put(u, v + height, w, light)

    def fountain(self, cu, v, cw, radius, basin="stonebrick"):
        for du in range(-radius, radius + 1):
            for dw in range(-radius, radius + 1):
                d = math.sqrt(du * du + dw * dw)
                if radius - 1.2 < d <= radius:
                    self.put(cu + du, v, cw + dw, basin)
                elif d <= radius - 1.2:
                    self.put(cu + du, v, cw + dw, "water")
        self.put(cu, v + 1, cw, basin)
        self.put(cu, v + 2, cw, "water")

    def garden_path(self, u1, w1, u2, w2, v, main, accent=None, seed=1):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        for u in range(ua, ub + 1):
            for w in range(wa, wb + 1):
                self.put(u, v, w, main if self.hash2(u, w, seed) < 0.7 or not accent else accent)

    def hedge(self, u1, v, w1, u2, w2, block, height=2):
        for k in range(max(1, int(height))):
            self.ring(u1, w1, u2, w2, v + k, block)

    def chimney(self, u, v, w, height, block="brick_block"):
        self.fill((u, v, w), (u, v + max(1, int(height)) - 1, w), block)
        self.put(u, v + height, w, "campfire")

    def pillar_decor(self, u, v, w, height, base, shaft, capital):
        self.put(u, v, w, base)
        for i in range(1, max(1, int(height))):
            self.put(u, v + i, w, shaft)
        self.put(u, v + height, w, capital)
        self.put(u, v + height + 1, w, capital)

    def carpet_area(self, u1, v, w1, u2, w2, main, border):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        for u in range(ua, ub + 1):
            for w in range(wa, wb + 1):
                self.put(u, v, w, border if u in (ua, ub) or w in (wa, wb) else main)

    def table(self, u, v, w, width, top="spruce_slab", leg="oak_fence"):
        width = max(1, int(width))
        for i in range(width):
            self.put(u + i, v, w, top)
            if i in (0, width - 1):
                self.put(u + i, v - 1, w, leg)

    def chair(self, u, v, w, facing, block="spruce_stairs"):
        self.put(u, v, w, self.stair(block), self.stair_states(facing))

    def sofa(self, u, v, w, width, facing, block="spruce_stairs"):
        du, dw = self.face(facing)
        along_u = dw != 0
        for i in range(max(1, int(width))):
            pu_ = u + (i if along_u else 0)
            pw_ = w + (0 if along_u else i)
            self.put(pu_, v, pw_, self.stair(block), self.stair_states(facing))
            self.put(pu_ - du, v, pw_ - dw, block)
            self.put(pu_ - du, v + 1, pw_ - dw, block)

    def bookshelf_wall(self, u1, v1, w1, u2, v2, w2):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        va, vb = self.span(v1, v2)
        for v in range(va, vb + 1):
            for u in range(ua, ub + 1):
                for w in range(wa, wb + 1):
                    if v == va and (u + w) % 2 == 0:
                        self.put(u, v, w, "lectern")
                    else:
                        self.put(u, v, w, "bookshelf" if (u + v + w) % 3 == 0 else "loom")

    def fireplace(self, cu, v, cw, facing, block="stonebrick"):
        du, dw = self.face(facing)
        pu, pw = self.perpendicular(facing)
        for k in (-1, 0, 1):
            self.put(cu + du + pu * k, v, cw + dw + pw * k, block)
            self.put(cu + du + pu * k, v + 1, cw + dw + pw * k, "air" if k == 0 else block)
        self.put(cu, v, cw, "campfire")
        self.put(cu, v + 1, cw, "air")
        for k in (-1, 0, 1):
            self.put(cu + pu * k, v + 2, cw + pw * k, block)
        self.put(cu + du, v + 3, cw + dw, block)
        self.put(cu + du, v + 4, cw + dw, block)

    def chandelier(self, cu, v, cw, radius, chain="chain", light="glowstone"):
        self.fill((cu, v - 1, cw), (cu, v, cw), chain)
        self.put(cu, v - 2, cw, light)
        for du in range(-radius, radius + 1):
            for dw in range(-radius, radius + 1):
                d = math.sqrt(du * du + dw * dw)
                if radius - 1.2 < d <= radius:
                    self.put(cu + du, v - 2, cw + dw, "lantern")
                if abs(d - radius / 2) < 0.6:
                    self.put(cu + du, v - 1, cw + dw, chain)

    def dormer(self, cu, v, cw, width, facing, wall, glass="glass_pane"):
        """老虎窗: 从屋面探出的 3 高小盒子 + 顶部披檐, 前面中间一格是玻璃。

        cu/cw 是**屋面上开口的中心**, facing 是它朝外的方向(通常朝檐口)。
        """
        width = max(1, int(width))
        du, dw = self.face(facing)
        pu, pw = self.perpendicular(facing)
        start = -(width - 1) // 2
        for d in range(1, 3):                 # 2 格进深(向外)
            for a in range(width):
                for h in range(3):
                    u = cu + pu * (start + a) + du * d
                    w = cw + pw * (start + a) + dw * d
                    front = d == 2
                    side = a in (0, width - 1)
                    roof = h == 2
                    if front and h == 1 and start + a == -(width // 2) + (width - 1) // 2:
                        self.put(u, v + h, w, glass)
                    elif roof or side or front:
                        self.put(u, v + h, w, wall)
        stair = self.stair(wall)
        for a in range(-1, width + 1):
            self.put(cu + pu * (start + a) + du * 3, v + 3,
                     cw + pw * (start + a) + dw * 3,
                     stair, self.stair_states(facing))
    def dormer_row(self, cu, v, cw, count, spacing, facing, wall):
        pu, pw = self.perpendicular(facing)
        start = -(int(count) - 1) * int(spacing) // 2
        for i in range(int(count)):
            self.dormer(cu + pu * (start + i * spacing), v, cw + pw * (start + i * spacing),
                        int(spacing) - 1, facing, wall)

    def balcony(self, u, v, w, width, depth, facing, floor="spruce_slab", rail="oak_fence"):
        du, dw = self.face(facing)
        pu, pw = self.perpendicular(facing)
        for i in range(max(1, int(width))):
            for d in range(max(1, int(depth))):
                self.put(u + du * d + pu * i, v, w + dw * d + pw * i, floor)
        for i in range(max(1, int(width))):
            self.put(u + du * (depth - 1) + pu * i, v + 1, w + dw * (depth - 1) + pw * i, rail)
        for d in range(depth):
            for i in (0, width - 1):
                self.put(u + du * d + pu * i, v + 1, w + dw * d + pw * i, rail)

    def bay_window(self, cu, v, cw, width, height, facing, wall, glass):
        """凸窗: 向外探出 2 格的窗体, 正面与两侧在中间层是玻璃, 底/顶收口。

        需要已有墙; 它**不挖洞**, 只做凸出的窗箱。
        """
        width, height = max(1, int(width)), max(1, int(height))
        du, dw = self.face(facing)
        pu, pw = self.perpendicular(facing)
        start = -(width - 1) // 2
        for d in (1, 2):
            for a in range(-1, width + 1):
                u = cu + pu * (start + a) + du * d
                w = cw + pw * (start + a) + dw * d
                self.put(u, v - 1, w, wall)                       # 窗台底
                for h in range(height):
                    mid = 0 < h < height - 1
                    front_glass = d == 2 and mid and start + a not in (-1, width)
                    self.put(u, v + h, w, glass if front_glass else wall)
                self.put(u, v + height, w, wall)                  # 顶板
        for h in range(height):
            for side in (-1, 1):
                u = cu + pu * (start + side * (width + 1) // 2) + du
                w = cw + pw * (start + side * (width + 1) // 2) + dw
                self.put(u, v + h, w, glass if 0 < h < height - 1 else wall)
    def well(self, cu, v, cw, block="stonebrick"):
        for du in range(-1, 2):
            for dw in range(-1, 2):
                self.put(cu + du, v, cw + dw, block if abs(du) == 1 or abs(dw) == 1 else "water")
        for du, dw in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            self.fill((cu + du, v + 1, cw + dw), (cu + du, v + 2, cw + dw), block)
        for du in (-1, 0, 1):
            self.put(cu + du, v + 3, cw, block)

    def arbor(self, u1, w1, u2, w2, v, log="oak_log", leaves="oak_leaves"):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        for u, w in ((ua, wa), (ub, wa), (ua, wb), (ub, wb)):
            self.fill((u, v, w), (u, v + 2, w), log)
        self.ring(ua, wa, ub, wb, v + 3, leaves)
        for u in range(ua + 1, ub):
            for w in range(wa + 1, wb):
                if self.hash2(u, w, 7) < 0.25:
                    self.put(u, v + 3, w, leaves)

    def planter_row(self, u, v, w, width, facing, seed=1):
        pu, pw = self.perpendicular(facing)
        for i in range(0, max(1, int(width)), 2):
            self.put(u + pu * i, v, w + pw * i,
                     ("flower_pot", "potted_fern", "potted_poppy")[self.hash2(i, 0, seed) * 3 // 3])

    def shutter(self, u, v, w, height, facing, block="spruce_trapdoor"):
        du, dw = self.face(facing)
        for h in range(max(1, int(height))):
            self.put(u - dw, v + h, w - du, block, {"direction": 2, "open_bit": True})
            self.put(u + dw, v + h, w + du, block, {"direction": 0, "open_bit": True})

    def porch(self, cu, v, cw, width, facing, roof, pillar="oak_log"):
        du, dw = self.face(facing)
        pu, pw = self.perpendicular(facing)
        for i in (0, max(1, int(width)) - 1):
            u = cu + pu * i + du * 2
            w = cw + pw * i + dw * 2
            self.fill((u, v, w), (u, v + 2, w), pillar)
        for i in range(-1, int(width) + 1):
            self.put(cu + pu * i + du * 2, v + 3, cw + pw * i + dw * 2, roof)
        self.put(cu, v, cw, self.stair(roof), self.stair_states(facing))

    def crates(self, u, v, w, count, seed=1):
        for i in range(max(1, int(count))):
            du = int(self.hash2(u, i, seed) * 3) - 1
            dw = int(self.hash2(w, i, seed + 1) * 3) - 1
            for h in range(1 + int(self.hash2(i, u + w, seed + 2) * 2)):
                self.put(u + du, v + h, w + dw, ("barrel", "barrel", "chest", "hay_block")[i % 4])

    def clothesline(self, u1, w1, u2, w2, v, pole="oak_fence"):
        self.fill((u1, v, w1), (u1, v + 1, w1), pole)
        self.fill((u2, v, w2), (u2, v + 1, w2), pole)
        su = (u2 > u1) - (u2 < u1)
        sw = (w2 > w1) - (w2 < w1)
        for i in range(1, max(abs(u2 - u1), abs(w2 - w1))):
            self.put(u1 + su * i, v + 1, w1 + sw * i, "chain")

    def bed_canopy(self, u, v, w, facing, frame="dark_oak_log"):
        du, dw = self.face(facing)
        self.put(u, v, w, "bed", {"direction": 0})
        for d in (0, 1):
            for h in range(1, 4):
                self.put(u + du * d, v + h, w + dw * d, frame)
        for i in range(2):
            self.put(u, v + 4, w + dw * (i - 1), frame)
            self.put(u + du * i, v + 4, w + dw, frame)

    def kitchen(self, u, v, w, width, facing):
        pu, pw = self.perpendicular(facing)
        width = max(1, int(width))
        for i in range(width):
            if i == 0:
                self.put(u + pu * i, v, w + pw * i, "smoker")
            elif i == width - 1:
                self.put(u + pu * i, v, w + pw * i, "cauldron")
            elif i == width // 2:
                self.put(u + pu * i, v, w + pw * i, "furnace")
            else:
                self.put(u + pu * i, v, w + pw * i, "stonecutter")
        self.put(u + pu * (width // 2) - pw, v, w + pw * (width // 2) - pu, "campfire")

    def throne(self, u, v, w, facing, block="quartz_block"):
        du, dw = self.face(facing)
        pu, pw = self.perpendicular(facing)
        self.put(u, v, w, self.stair(block), self.stair_states(facing))
        self.put(u - du, v, w - dw, block)
        self.put(u - du, v + 1, w - dw, block)
        self.put(u - du, v + 2, w - dw, "gold_block")
        for k in (-1, 1):
            self.put(u + pu * k, v, w + pw * k, "gold_block")
            self.put(u - du + pu * k, v + 1, w - dw + pw * k, block)

    def bar(self, u, v, w, width, facing, block="dark_oak_planks"):
        du, dw = self.face(facing)
        pu, pw = self.perpendicular(facing)
        for i in range(max(1, int(width))):
            self.put(u + pu * i, v, w + pw * i, block)
            self.put(u + pu * i, v + 1, w + pw * i, "air")
            self.put(u + pu * i - du, v, w + pw * i - dw, "barrel")
        for i in range(1, max(1, int(width)), 2):
            self.put(u + pu * i + du, v, w + pw * i + dw,
                     self.stair(block), self.stair_states(facing))

    def wardrobe(self, u, v, w, facing, block="spruce_planks"):
        du, dw = self.face(facing)
        pu, pw = self.perpendicular(facing)
        self.fill((u, v, w), (u, v + 1, w), block)
        for h in range(2):
            self.put(u + pw, v + h, w + pu, block)
            self.put(u - pw, v + h, w - pu, block)

    def potted_plants(self, u, v, w, count, seed=1):
        for i in range(max(1, int(count))):
            du = int(self.hash2(i, u, seed) * 3) - 1
            dw = int(self.hash2(i, w, seed + 1) * 3) - 1
            self.put(u + du, v, w + dw, "flower_pot")

    def wall_shelf(self, u, v, w, width, facing, block="spruce_trapdoor"):
        pu, pw = self.perpendicular(facing)
        for i in range(max(1, int(width))):
            self.put(u + pu * i, v, w + pw * i, block,
                     {"direction": 2, "open_bit": True, "upside_down_bit": True})
            if i % 3 == 1:
                self.put(u + pu * i, v - 1, w + pw * i, "oak_fence")

    def floor_lamp(self, u, v, w, pole="dark_oak_fence", light="shroomlight"):
        self.fill((u, v, w), (u, v + 1, w), pole)
        self.put(u, v + 2, w, light)
        self.put(u, v + 3, w, "spruce_trapdoor")

    def aquarium(self, u, v, w, width, block="glass"):
        width = max(1, int(width))
        for i in range(width):
            for h in range(2):
                self.put(u + i, v + h, w, block if h == 0 or i in (0, width - 1) else "water")
        self.put(u + width // 2, v, w, "seagrass")

    def library_ladder(self, u, v, w, height):
        for h in range(max(2, int(height))):
            self.put(u, v + h, w, "bookshelf")
            self.put(u, v + h, w + 1, "ladder")
        for i in (-1, 0, 1):
            self.put(u + i, v + height, w, "bookshelf")

    def flag_banner(self, u, v, w, facing, banner="red_banner"):
        self.fill((u, v, w), (u, v + 2, w), "oak_fence")
        self.put(u, v + 3, w, banner)
        self.put(u, v + 4, w, banner)

    def outdoor_bench(self, u, v, w, width, block="smooth_stone_slab"):
        for i in range(max(1, int(width))):
            self.put(u + i, v, w, block)
            if i in (0, max(1, int(width)) - 1):
                self.put(u + i, v - 1, w, "stonebrick")

    def stone_lantern(self, u, v, w, block="stonebrick"):
        self.fill((u, v, w), (u, v + 1, w), block)
        self.put(u, v + 2, w, "lantern")
        self.put(u, v + 3, w, block)

    def flower_garden(self, u1, w1, u2, w2, v, seed=1):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        flowers = ("poppy", "yellow_flower", "oxeye_daisy", "cornflower",
                   "azure_bluet", "short_grass", "tall_grass", "lilac", "peony", "rose_bush")
        for u in range(ua, ub + 1):
            for w in range(wa, wb + 1):
                if self.hash2(u, w, seed) < 0.55:
                    self.put(u, v, w, flowers[int(self.hash2(w, u, seed + 1) * len(flowers))])

    def berry_bush_row(self, u, v, w, width, facing):
        pu, pw = self.perpendicular(facing)
        for i in range(0, max(1, int(width)), 2):
            self.put(u + pu * i, v, w + pw * i, "sweet_berry_bush")

    def stone_bridge(self, u1, v, w1, u2, w2, block="stonebrick"):
        """小石桥: 沿主轴起拱, 桥面带两侧栏(各高 1), 拱高 = 跨/4。"""
        along = abs(u2 - u1) >= abs(w2 - w1)
        length = max(1, abs(u2 - u1) if along else abs(w2 - w1))
        arc_h = max(2, length // 4)
        step = 1 if (u2 >= u1 if along else w2 >= w1) else -1
        # 桥宽方向(横跨主轴)的两侧偏移
        pu, pw = ((0, 1) if along else (1, 0))
        for i in range(length + 1):
            u = u1 + step * i if along else u1
            w = w1 if along else w1 + step * i
            arc = self.jround(arc_h * math.sin(math.pi * i / length))
            self.fill((u, v + arc, w), (u, v + arc, w), block)
            for side in (-1, 1):
                self.put(u + pu * side, v + arc + 1, w + pw * side, block)

    def vine_wall(self, u, v, w, width, height, facing, seed=1):
        pu, pw = self.perpendicular(facing)
        for i in range(max(1, int(width))):
            for h in range(max(1, int(height))):
                if self.hash2(i + u, h + w, seed) < 0.6:
                    self.put(u + pu * i, v + h, w + pw * i,
                             "vine" if self.hash2(h, i, seed + 1) < 0.5 else "hanging_roots")

    def mosaic_floor(self, u1, w1, u2, w2, v, a, b, c=None, seed=1):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        for u in range(ua, ub + 1):
            for w in range(wa, wb + 1):
                value = (u + w) % 4
                self.put(u, v, w, a if value in (0, 2) else (b if value == 1 or not c else c))

    def roof_finial(self, u, v, w):
        self.put(u, v, w, "oak_fence")
        self.put(u, v + 1, w, "red_banner")

    def stone_foundation(self, u1, v, w1, u2, w2, block="stonebrick"):
        self.ring(u1 - 1, w1 - 1, u2 + 1, w2 + 1, v, block)
        self.fill((u1, v, w1), (u2, v, w2), "air")

    def picket_fence(self, u1, v, w1, u2, w2, block="oak_fence"):
        self.ring(u1, w1, u2, w2, v, block)

    def market_umbrella(self, u, v, w, canopy="red_wool"):
        self.fill((u, v, w), (u, v + 2, w), "oak_fence")
        self.fill((u - 1, v + 3, w - 1), (u + 1, v + 3, w + 1), canopy)

    def ceiling_beams(self, u1, v, w1, u2, w2, block="spruce_log"):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        for u in range(ua, ub + 1, 3):
            self.fill((u, v, wa), (u, v, wb), block)
        for w in range(wa + 2, wb + 1, 4):
            self.fill((ua, v, w), (ub, v, w), block)

    def chest_storage(self, u, v, w, width, height, facing):
        pu, pw = self.perpendicular(facing)
        for i in range(max(1, int(width))):
            for h in range(max(1, int(height))):
                self.put(u + pu * i, v + h, w + pw * i, "chest", {"cardinal_direction": facing})

    def enchanting_corner(self, u, v, w):
        self.put(u, v, w, "enchanting_table")
        for du, dw in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -2), (1, -2)):
            self.put(u + du, v, w + dw, "bookshelf")
        self.put(u, v + 3, w, "lantern")

    def brewing_corner(self, u, v, w):
        self.put(u, v, w, "brewing_stand")
        self.put(u + 1, v, w, "cauldron")
        self.put(u - 1, v, w, "barrel")

    def dining_set(self, u, v, w, block="spruce_stairs"):
        self.table(u, v, w, 2, "spruce_slab", "oak_fence")
        self.chair(u - 1, v, w + 1, "east", block)
        self.chair(u + 2, v, w + 1, "west", block)
        self.chair(u, v, w - 1, "south", block)
        self.chair(u + 1, v, w + 2, "north", block)

    def rug_runner(self, u, v, w, length, facing, main, border):
        pu, pw = self.perpendicular(facing)
        for i in range(max(1, int(length))):
            self.put(u + pu * i, v, w + pw * i, border if i in (0, length - 1) else main)

    def window_seat(self, u, v, w, width, facing, block="spruce_stairs"):
        pu, pw = self.perpendicular(facing)
        for i in range(max(1, int(width))):
            self.put(u + pu * i, v, w + pw * i, self.stair(block), self.stair_states(facing))
            if i % 2 == 0:
                self.put(u + pu * i, v + 1, w + pw * i, "white_carpet")

    def bedside_table(self, u, v, w):
        self.put(u, v, w, "barrel")
        self.put(u, v + 1, w, "lantern")

    def pot_rack(self, u, v, w, width):
        for i in range(max(1, int(width))):
            self.put(u + i, v, w, "oak_fence")
            if i % 2 == 1:
                self.put(u + i, v - 1, w, "chain")
                self.put(u + i, v - 2, w, "cauldron")

    def wine_cellar(self, u, v, w, width):
        for i in range(max(1, int(width))):
            self.fill((u + i, v, w), (u + i, v + 1, w), "barrel")

    def weapon_rack(self, u, v, w, facing):
        du, dw = self.face(facing)
        self.put(u - dw, v, w - du, "red_banner")
        self.put(u + dw, v, w + du, "blue_banner")
        self.put(u, v, w, "anvil")
        self.fill((u, v + 1, w), (u, v + 2, w), "oak_fence")

    def study_desk(self, u, v, w, facing):
        du, dw = self.face(facing)
        self.put(u, v, w, "lectern", {"cardinal_direction": facing})
        self.chair(u + du, v, w + dw, facing)
        self.floor_lamp(u + du * 2, v, w + dw * 2)

    def tea_corner(self, u, v, w):
        self.put(u, v, w, "oak_pressure_plate")
        self.put(u - 1, v, w, "white_carpet")
        self.put(u + 1, v, w, "white_carpet")
        self.potted_plants(u, v, w + 1, 2)

    def music_corner(self, u, v, w):
        self.put(u, v, w, "jukebox")
        self.put(u + 1, v, w, "note_block")
        self.put(u + 2, v, w, "note_block")

    def lantern_ceiling(self, u1, w1, u2, w2, v, spacing=4):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        sp = max(1, int(spacing))
        for u in range(ua + sp // 2, ub + 1, sp):
            for w in range(wa + sp // 2, wb + 1, sp):
                self.put(u, v, w, "lantern", {"hanging": True})

    def room_divider(self, u1, v, w1, u2, w2, height, block="spruce_planks", door=True):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        along = ub - ua >= wb - wa
        h = max(1, int(height))
        if along:
            mid_w, mid_u = (wa + wb) // 2, (ua + ub) // 2
            for u in range(ua, ub + 1):
                gap = door and u in (mid_u, mid_u - 1)
                for k in range(h):
                    if not (gap and k < 2):
                        self.put(u, v + k, mid_w, block)
            if door:
                self.put(mid_u, v, mid_w, self.block(block))
        else:
            mid_u, mid_w = (ua + ub) // 2, (wa + wb) // 2
            for w in range(wa, wb + 1):
                gap = door and w in (mid_w, mid_w - 1)
                for k in range(h):
                    if not (gap and k < 2):
                        self.put(mid_u, v + k, w, block)
            if door:
                self.put(mid_u, v, mid_w, block)

    def living_room_set(self, cu, v, cw, facing, opts=None):
        du, dw = self.face(facing)
        pu, pw = self.perpendicular(facing)
        opts = opts or {}
        carpet = self.option(opts, "carpet", "brown_carpet")
        border = self.option(opts, "border", "red_carpet")
        wood = self.option(opts, "wood", "spruce_planks")
        radius = max(1, min(8, int(self.option(opts, "radius", 2))))
        for a in range(-radius, radius + 1):
            for b in range(-radius, radius + 1):
                self.put(cu + a, v, cw + b, border if max(abs(a), abs(b)) == radius else carpet)
        for i in (-1, 0, 1):
            u, w = cu - du * radius + pu * i, cw - dw * radius + pw * i
            self.put(u, v + 1, w, wood)
            self.put(u, v + 2, w, self.option(opts, "cushion", "red_wool"))
            self.put(u - du, v + 2, w - dw, self.option(opts, "back", "spruce_trapdoor"))
        self.put(cu, v + 2, cw, wood)
        self.put(cu, v + 1, cw, "oak_fence")
        self.put(cu + pu * radius, v + 1, cw + pw * radius, "bookshelf")
        self.put(cu + pu * radius, v + 2, cw + pw * radius, "bookshelf")
        self.put(cu - pu * radius, v + 1, cw + pw * radius, "flower_pot")
        self.put(cu + du * (radius - 1), v + 3, cw + dw * (radius - 1), "lantern")

    def bedroom_set(self, cu, v, cw, facing, opts=None):
        du, dw = self.face(facing)
        pu, pw = self.perpendicular(facing)
        opts = opts or {}
        bed = self.option(opts, "bed", "red_wool")
        pillow = self.option(opts, "pillow", "white_wool")
        frame = self.option(opts, "frame", "spruce_log")
        for a in range(-2, 3):
            for b in range(-2, 3):
                self.put(cu + a, v, cw + b,
                         self.option(opts, "border", "red_carpet") if max(abs(a), abs(b)) == 2
                         else self.option(opts, "carpet", "brown_carpet"))
        hu, hw = cu - du, cw - dw
        self.put(hu, v + 1, hw, pillow)
        self.put(hu, v + 2, hw, frame)
        self.put(hu + du, v + 1, hw + dw, bed)
        self.put(hu + pu, v + 1, hw + pw, "barrel")
        self.put(hu + pu, v + 2, hw + pw, "lantern")
        self.fill((cu + pu * 2, v + 1, cw + pw * 2), (cu + pu * 2, v + 2, cw + pw * 2), frame)
        self.put(cu + pu * 2 + du, v + 1, cw + pw * 2 + dw, "spruce_trapdoor")
        self.put(cu + pu * 2 + du, v + 2, cw + pw * 2 + dw, "spruce_trapdoor")

    def kitchen_counter(self, u, v, w, width, facing, opts=None):
        pu, pw = self.perpendicular(facing)
        opts = opts or {}
        top = self.option(opts, "top", "smooth_stone")
        base = self.option(opts, "base", "spruce_planks")
        width = max(2, min(24, int(width)))
        for i in range(width):
            self.put(u + pu * i, v, w + pw * i, base)
            self.put(u + pu * i, v + 1, w + pw * i, top)
            if i % 2 == 1:
                self.put(u + pu * i, v + 3, w + pw * i, "spruce_trapdoor")
        self.put(u, v, w, "furnace")
        self.put(u, v + 1, w, "campfire")
        self.put(u, v + 2, w, "iron_bars")
        self.put(u + pu * (width - 1), v + 1, w + pw * (width - 1), "cauldron")

    def storage_nook(self, u, v, w, facing, opts=None):
        pu, pw = self.perpendicular(facing)
        opts = opts or {}
        width = max(1, min(16, int(self.option(opts, "width", 3))))
        height = max(1, min(2, int(self.option(opts, "height", 1))))
        for i in range(width):
            for h in range(height):
                self.put(u + pu * i, v + h, w + pw * i, "chest", {"cardinal_direction": facing})
        self.put(u - pu, v, w - pw, "barrel")
        self.put(u + pu * width, v, w + pw * width, "barrel")

    def entryway_set(self, u, v, w, facing, opts=None):
        du, dw = self.face(facing)
        pu, pw = self.perpendicular(facing)
        opts = opts or {}
        mat = self.option(opts, "mat", "brown_carpet")
        pole = self.option(opts, "pole", "spruce_fence")
        self.put(u, v, w, mat)
        self.put(u + pu, v, w + pw, mat)
        self.fill((u - pu, v, w - pw), (u - pu, v + 2, w - pw), pole)
        self.put(u - pu + du, v + 2, w - pw + dw, "spruce_trapdoor")
        self.put(u - pu, v + 1, w + pw, self.stair("spruce_planks"))
        self.put(u - pu, v + 1, w - pw, "flower_pot")

    def shelf_run(self, u, v, w, width, facing, block="spruce_trapdoor", opts=None):
        pu, pw = self.perpendicular(facing)
        opts = opts or {}
        rows = max(1, min(5, int(self.option(opts, "rows", 2))))
        step = max(1, min(4, int(self.option(opts, "step", 2))))
        deco = ("flower_pot", "lantern", "bookshelf", "barrel", "candle", "smooth_stone")
        for r in range(rows):
            for i in range(max(1, int(width))):
                self.put(u + pu * i, v + r * step, w + pw * i, block)
                if self.hash2(u + i, w + r, 11) < 0.55:
                    self.put(u + pu * i, v + r * step + 1, w + pw * i,
                             deco[int(self.hash2(i, r, 31) * len(deco))])

    def hanging_herbs(self, u1, v, w1, u2, w2, opts=None):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        sp = max(1, min(12, int(self.option(opts, "spacing", 2))))
        items = ("hay_block", "brown_mushroom", "red_mushroom", "lantern", "dried_kelp_block")
        along = ub - ua >= wb - wa
        rng = range(ua, ub + 1, sp) if along else range(wa, wb + 1, sp)
        for a in rng:
            self.put(a if along else ua, v, wa if along else a, "chain")
            self.put(a if along else ua, v - 1, wa if along else a,
                     items[int(self.hash2(a, 0, 7) * len(items))])

    def clutter_corner(self, u, v, w, count, seed=1):
        deco = ("barrel", "chest", "flower_pot", "hay_block", "bookshelf", "cobblestone")
        for i in range(max(1, min(40, int(count)))):
            du = int(self.hash2(i, u, seed) * 5) - 2
            dw = int(self.hash2(i, w, seed + 1) * 5) - 2
            dv = int(self.hash2(i, du + dw, seed + 2) * 3)
            self.put(u + du, v + dv, w + dw, deco[int(self.hash2(u + i, w, seed + 3) * len(deco))])

    def attic_ladder(self, u, v, w, height, facing):
        du, dw = self.face(facing)
        for k in range(max(2, min(32, int(height)))):
            self.put(u, v + k, w, "ladder")
            if k % 2:
                self.put(u + du, v + k, w + dw, "spruce_trapdoor")
        self.fill((u, v + height, w), (u + du, v + height, w + dw), "spruce_planks")

    def cottage_exterior(self, u, v, w, width, depth, height, facing, wall, roof, opts=None):
        opts = opts or {}
        du, dw = self.face(facing)
        pu, pw = self.perpendicular(facing)
        width, depth = max(5, min(64, int(width))), max(5, min(64, int(depth)))
        height = max(3, min(20, int(height)))
        u2, w2 = u + width - 1, w + depth - 1
        self.ring(u - 1, w - 1, u2 + 1, w2 + 1, v - 1,
                  self.option(opts, "footing", "stonebrick"))
        if du:
            fu, fw = (u2 if du > 0 else u), w + depth // 2
        else:
            fu, fw = u + width // 2, (w2 if dw > 0 else w)
        if self.option(opts, "autoDoor", True):
            self.doorway(fu, v, fw, facing, self.option(opts, "door", "wooden_door"), opts)
        frame = self.option(opts, "frame", "spruce_planks")
        glass = self.option(opts, "glass", "glass_pane")
        wy = v + max(1, min(height - 2, int(self.option(opts, "windowY", 1))))
        front = width if dw else depth
        if front >= 9:
            self.window_row(fu, wy, fw, 2, 6, facing, frame, glass, opts)
        elif front >= 7:
            self.window_row(fu, wy, fw, 2, 4, facing, frame, glass, opts)
        if dw:
            self.window_row(u, wy, w + depth // 2, 1, 3, "west", frame, glass, opts)
            self.window_row(u2, wy, w + depth // 2, 1, 3, "east", frame, glass, opts)
        else:
            self.window_row(u + width // 2, wy, w, 1, 3, "north", frame, glass, opts)
            self.window_row(u + width // 2, wy, w2, 1, 3, "south", frame, glass, opts)
        bracket = self.option(opts, "bracket", "spruce_trapdoor")
        if du:
            self.eave_bracket(u, v + height - 1, fw, u2, fw, facing, bracket, opts)
        else:
            self.eave_bracket(fu, v + height - 1, w, fu, w2, facing, bracket, opts)
        if self.option(opts, "road", True):
            road = self.option(opts, "roadBlock", "grass_path")
            for i in range(1, 7):
                self.put(fu + du * i, v - 1, fw + dw * i, road)
        if self.option(opts, "lamp", True):
            pole = self.option(opts, "lampPole", "oak_fence")
            for s in (-1, 1):
                lu, lw = fu + pu * 3 * s, fw + pw * 3 * s
                self.fill((lu, v - 1, lw), (lu, v, lw), pole)
                self.put(lu, v + 1, lw, "lantern")
        if self.option(opts, "ridge", False):
            ry = min(v + height + 16, max(v, int(self.option(opts, "roofY", v + height + 2))))
            self.roof_ridge(u, ry, w, u2, w2,
                            self.option(opts, "ridgeBlock", roof or "spruce_slab"), opts)
        if self.option(opts, "chimney", False):
            cu = u + width // 4 if du else u
            cw = w if du else w + depth // 4
            self.chimney_stack(cu, v, cw, height + 2,
                               self.option(opts, "chimneyBlock", "brick_block"), opts)

    def doorway(self, cu, v, cw, facing, door="wooden_door", opts=None):
        opts = opts or {}
        du, dw = self.face(facing)
        pu, pw = self.perpendicular(facing)
        frame = self.option(opts, "frame", "spruce_log")
        step_block = self.option(opts, "step", "stonebrick")
        lamp = self.option(opts, "lantern", "lantern")
        awning = self.option(opts, "awning", None)
        height = max(2, min(6, int(self.option(opts, "height", 3))))
        door_block = self.block(door, "wooden_door")
        self.put(cu, v, cw, door_block, {"direction": 0, "upper_block_bit": False})
        self.put(cu, v + 1, cw, door_block, {"direction": 0, "upper_block_bit": True})
        for k in range(height + 1):
            self.put(cu - pu, v + k, cw - pw, frame)
            self.put(cu + pu, v + k, cw + pw, frame)
        for a in (-1, 0, 1):
            self.put(cu + pu * a, v + height, cw + pw * a, frame)
        self.put(cu - pu, v + 2, cw - pw, lamp)
        self.put(cu + pu, v + 2, cw + pw, lamp)
        self.put(cu + du, v - 1, cw + dw, step_block)
        self.put(cu + du * 2, v - 1, cw + dw * 2, step_block)
        if awning:
            for a in (-1, 0, 1):
                self.put(cu + pu * a + du, v + height, cw + pw * a + dw, awning)

    def window_row(self, cu, v, cw, count, spacing, facing, frame="spruce_planks",
                   glass="glass_pane", opts=None):
        opts = opts or {}
        du, dw = self.face(facing)
        pu, pw = self.perpendicular(facing)
        count, spacing = max(1, min(24, int(count))), max(2, min(16, int(spacing)))
        h = max(1, min(5, int(self.option(opts, "height", 2))))
        sill = self.option(opts, "sill", None)
        shutter = self.option(opts, "shutter", None)
        box = self.option(opts, "flowerBox", None)
        soil = self.option(opts, "soil", "dirt")
        flower = self.option(opts, "flower", "poppy")
        start = -((count - 1) * spacing) // 2
        for i in range(count):
            off = start + i * spacing
            u, w = cu + pu * off, cw + pw * off
            for k in range(h):
                self.put(u, v + 1 + k, w, glass)
            self.put(u, v, w, frame)
            self.put(u, v + 1 + h, w, frame)
            for k in range(h + 1):
                self.put(u - pu, v + 1 + k, w - pw, frame)
                self.put(u + pu, v + 1 + k, w + pw, frame)
            if sill:
                self.put(u, v - 1, w, sill)
            if shutter:
                for k in range(h):
                    self.put(u - pu + du, v + 1 + k, w - pw + dw, shutter)
                    self.put(u + pu + du, v + 1 + k, w + pw + dw, shutter)
            if box:
                self.put(u + du, v - 1, w + dw, box)
                self.put(u + du, v, w + dw, soil)
                self.put(u + du, v + 1, w + dw, flower)

    def roof_ridge(self, u1, v, w1, u2, w2, block="spruce_slab", opts=None):
        opts = opts or {}
        cap = self.option(opts, "cap", block)
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        if ub - ua >= wb - wa:
            mw = (wa + wb) // 2
            for u in range(ua, ub + 1):
                self.put(u, v, mw, block)
                if mw < wb:
                    self.put(u, v, mw + 1, block)
            self.put(ua, v + 1, mw, cap)
            self.put(ub, v + 1, mw, cap)
        else:
            mu = (ua + ub) // 2
            for w in range(wa, wb + 1):
                self.put(mu, v, w, block)
                if mu < ub:
                    self.put(mu + 1, v, w, block)
            self.put(mu, v + 1, wa, cap)
            self.put(mu, v + 1, wb, cap)

    def chimney_stack(self, u, v, w, height, block="brick_block", opts=None):
        opts = opts or {}
        h = max(1, min(40, int(height)))
        self.fill((u, v, w), (u, v + h - 1, w), block)
        ty = v + h
        for du in (-1, 0, 1):
            for dw in (-1, 0, 1):
                if du or dw:
                    self.put(u + du, ty, w + dw, self.option(opts, "cap", "stonebrick"))
        self.put(u, ty, w, "campfire" if self.option(opts, "smoke", False)
                 else self.option(opts, "cap", "stonebrick"))

    def eave_bracket(self, u1, v, w1, u2, w2, facing, block="spruce_trapdoor", opts=None):
        opts = opts or {}
        du, dw = self.face(facing)
        sp = max(1, min(16, int(self.option(opts, "spacing", 3))))
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        if ub - ua >= wb - wa:
            for u in range(ua, ub + 1, sp):
                self.put(u, v + 1, wa, block)
                self.put(u, v, wa + dw, block)
        else:
            for w in range(wa, wb + 1, sp):
                self.put(ua, v + 1, w, block)
                self.put(ua + du, v, w, block)

    def fence_gate(self, cu, v, cw, facing, block="oak_fence", opts=None):
        opts = opts or {}
        du, dw = self.face(facing)
        pu, pw = self.perpendicular(facing)
        post = self.option(opts, "post", "stonebrick")
        gate = self.option(opts, "gate", "oak_fence_gate")
        for k in range(3):
            self.put(cu - pu * 2, v + k, cw - pw * 2, block)
            self.put(cu + pu * 2, v + k, cw + pw * 2, block)
        self.put(cu - pu * 2, v + 3, cw - pw * 2, post)
        self.put(cu + pu * 2, v + 3, cw + pw * 2, post)
        self.put(cu, v, cw, gate)
        self.put(cu - pu, v + 1, cw - pw, block)
        self.put(cu + pu, v + 1, cw + pw, block)

    def window_awning(self, cu, v, cw, width, facing, canopy="red_wool", opts=None):
        opts = opts or {}
        du, dw = self.face(facing)
        pu, pw = self.perpendicular(facing)
        width = max(1, min(15, int(width)))
        start = -((width - 1) // 2)
        for i in range(width):
            u, w = cu + pu * (start + i), cw + pw * (start + i)
            self.put(u, v + 1, w, canopy)
            self.put(u + du, v + 1, w + dw, canopy)
        bracket = self.option(opts, "bracket", "spruce_fence")
        self.put(cu + pu * start + du, v, cw + pw * start + dw, bracket)
        self.put(cu + pu * (start + width - 1) + du, v,
                 cw + pw * (start + width - 1) + dw, bracket)

    def cottage_interior(self, u, v, w, width, depth, height, facing, opts=None):
        opts = opts or {}
        du, dw = self.face(facing)
        width, depth = max(5, min(64, int(width))), max(5, min(64, int(depth)))
        height = max(3, min(12, int(height)))
        u2, w2 = u + width - 1, w + depth - 1
        wall = self.option(opts, "wall", "spruce_planks")
        if max(width, depth) >= 8:
            self.room_divider(u, v, w, u2, w2, height, wall, True)
        fu = (u2 - width // 4 if du > 0 else u + width // 4) if du else u + width // 2
        fw = (w2 - depth // 4 if dw > 0 else w + depth // 4) if dw else w + depth // 2
        self.living_room_set(fu, v, fw, ("back" if dw > 0 else "front") if dw else ("right" if du > 0 else "left"), opts)
        if max(width, depth) >= 7:
            bu = (u + width // 4 if du > 0 else u2 - width // 4) if du else u + width // 2
            bw = (w + depth // 4 if dw > 0 else w2 - depth // 4) if dw else w + depth // 2
            self.bedroom_set(bu, v, bw, facing, opts)
        self.kitchen_counter(u + 1, v, w + 1, min(8, min(width, depth) - 2), "north", opts)
        self.storage_nook(u2 - 1, v, w + 1, "west", {"width": 2})
        self.clutter_corner(u + width // 2, v, w2 - 1, 6)
        beam = self.option(opts, "beam", "spruce_log")
        for i in range(0, width, 3):
            self.line((u + i, v + height - 1, w), (u + i, v + height - 1, w2), beam)
        self.put(fu, v + height - 2, fw, "chain")
        self.put(fu, v + height - 3, fw, "lantern")
