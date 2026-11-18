class _CreationLib:
    # ---------- natural / ruins / terrain / roads (deterministic) ----------
    def vegetation(self, cu, base_v, cw, size, biome="forest", seed=None):
        s = max(1, min(64, int(size)))
        biome = str(biome or "forest").lower()
        sd = int(seed) if seed else self.auto_seed(cu, base_v, cw)
        density = {"jungle": 0.42, "taiga": 0.30, "forest": 0.28, "birch": 0.26,
                   "swamp": 0.16, "plains": 0.09, "savanna": 0.07,
                   "desert": 0.02}.get(biome, 0.24)
        ground = {"jungle": 0.55, "forest": 0.34, "taiga": 0.26, "birch": 0.32,
                  "swamp": 0.40, "plains": 0.44, "savanna": 0.28,
                  "desert": 0.05}.get(biome, 0.34)
        u0, w0 = cu - s // 2, cw - s // 2
        for gu in range(0, s, 3):
            for gw in range(0, s, 3):
                r = self.hash2(u0 + gu, w0 + gw, sd)
                if r >= density:
                    continue
                tu = u0 + gu + int(self.hash2(gu, gw, sd + 7) * 3)
                tw = w0 + gw + int(self.hash2(gw, gu, sd + 11) * 3)
                self._grow_tree(tu, base_v, tw, r, sd, biome)
        plants = self._ground_plants(biome)
        for du in range(s):
            for dw in range(s):
                u, w = u0 + du, w0 + dw
                if self.hash2(u, w, sd + 999) >= ground:
                    continue
                pick = self.hash2(w, u, sd + 3001)
                self.put(u, base_v, w, plants[int(pick * len(plants))])

    def _ground_plants(self, biome):
        return {
            "desert": ("dead_bush", "dead_bush", "dead_bush", "sand"),
            "swamp": ("short_grass", "fern", "moss_carpet", "brown_mushroom", "red_mushroom"),
            "taiga": ("short_grass", "fern", "fern", "large_fern", "sweet_berry_bush"),
            "jungle": ("short_grass", "short_grass", "tall_grass", "fern", "large_fern"),
            "savanna": ("short_grass", "short_grass", "short_grass", "tall_grass"),
        }.get(biome, ("short_grass", "short_grass", "short_grass", "tall_grass",
                       "yellow_flower", "poppy", "oxeye_daisy", "cornflower"))

    def _grow_tree(self, u, v, w, r, sd, biome):
        species = {"taiga": "spruce", "jungle": "jungle", "savanna": "acacia",
                   "desert": "cactus", "swamp": "swamp_oak", "birch": "birch"}.get(
            biome, ("oak", "birch", "big_oak")[min(2, int(r * 3))])
        hx = self.hash_mix(u, sd) & 7
        if species == "birch":
            h = 6 + (hx & 3)
            self._trunk(u, v, w, h, "birch_log")
            self.ellipse_blob(u, v + h - 1, w, 2, 2, 2, "birch_leaves", sd + 31, 0.8)
        elif species == "spruce":
            h = 8 + (hx & 3)
            self._trunk(u, v, w, h, "spruce_log")
            for dv in range(2, h + 2):
                rad = max(0, (h + 2 - dv) * 3 // (h + 2))
                self._leaf_ring(u, v + dv, w, rad, "spruce_leaves", sd + 41, 0.86)
        elif species == "jungle":
            h = 10 + (hx & 3)
            self._trunk(u, v, w, h, "jungle_log")
            self.ellipse_blob(u, v + h - 1, w, 3, 2, 3, "jungle_leaves", sd + 51, 0.88)
            for k in range(6):
                vu = u + ((self.hash_mix(k, sd + 61) & 7) - 3)
                vw = w + ((self.hash_mix(k, sd + 67) & 7) - 3)
                for i in range(2 + (self.hash_mix(k, sd + 71) & 3)):
                    self.put(vu, v + h - 2 - i, vw, "vine")
        elif species == "acacia":
            h = 5 + (hx & 3)
            ou = 1 if (self.hash_mix(u, sd + 81) & 1) == 0 else -1
            ow = 1 if (self.hash_mix(w, sd + 83) & 1) == 0 else -1
            self._trunk(u, v, w, h, "acacia_log")
            for i in range(3):
                self.put(u + ou * (i + 1), v + h + i, w + ow * (i + 1), "acacia_log")
            self._leaf_ring(u + ou * 3, v + h + 3, w + ow * 3, 3, "acacia_leaves", sd + 91, 0.85)
            self._leaf_ring(u + ou * 3, v + h + 4, w + ow * 3, 2, "acacia_leaves", sd + 92, 0.75)
        elif species == "cactus":
            self._trunk(u, v, w, 1 + (hx & 2), "cactus")
        elif species == "swamp_oak":
            h = 4 + (hx & 2)
            self._trunk(u, v, w, h, "oak_log")
            self.ellipse_blob(u, v + h - 1, w, 3, 1, 3, "oak_leaves", sd + 101, 0.82)
            for k in range(3):
                self.put(u + ((self.hash_mix(k, sd + 111) & 5) - 2), v + h - 3,
                         w + ((self.hash_mix(k, sd + 113) & 5) - 2), "vine")
        elif species == "big_oak":
            h = 5 + (hx & 3)
            self._trunk(u, v, w, h, "dark_oak_log")
            self.ellipse_blob(u, v + h - 1, w, 3, 2, 3, "dark_oak_leaves", sd + 121, 0.86)
            for k in range(2):
                su = 1 if (self.hash_mix(k, sd + 131) & 1) == 0 else -1
                sw = 1 if (self.hash_mix(k, sd + 137) & 1) == 0 else -1
                for i in range(1, 3):
                    self.put(u + su * i, v + h - 2 + i, w + sw * i, "dark_oak_log")
        else:
            h = 4 + (hx & 3)
            self._trunk(u, v, w, h, "oak_log")
            self.ellipse_blob(u, v + h - 1, w, 2, 2, 2, "oak_leaves", sd + 21, 0.86)

    def _trunk(self, u, v, w, height, log):
        self.fill((u, v, w), (u, v + max(1, int(height)) - 1, w), log)

    def _leaf_ring(self, cu, cv, cw, radius, leaves, sd, density):
        r = max(0, int(radius))
        for du in range(-r, r + 1):
            for dw in range(-r, r + 1):
                if (du * du + dw * dw) / (r * r + 0.25) > 1:
                    continue
                if self.hash3(cu + du, cv, cw + dw, sd) > density:
                    continue
                self.put(cu + du, cv, cw + dw, leaves)

    def ruins(self, cu, base_v, cw, size, age=45, seed=None):
        s = max(5, min(64, int(size)))
        age = max(0, min(100, int(age)))
        sd = int(seed) if seed else self.auto_seed(cu, base_v, cw)
        decay = age / 100
        u0, w0 = cu - s // 2, cw - s // 2
        u1, w1 = u0 + s - 1, w0 + s - 1
        wall_h = max(3, min(9, s // 4))
        for u in range(u0, u1 + 1):
            for w in range(w0, w1 + 1):
                r = self.hash2(u, w, sd + 5)
                if r < decay * 0.55:
                    continue
                self.put(u, base_v, w,
                         "cracked_stone_bricks" if r > 0.86 else
                         ("mossy_stone_bricks" if r > 0.72 else "stonebrick"))
        for u in range(u0, u1 + 1):
            for w in range(w0, w1 + 1):
                if u not in (u0, u1) and w not in (w0, w1):
                    continue
                doorway = w == w1 and abs(u - cu) <= 1
                for dv in range(wall_h):
                    if doorway and dv < 3:
                        continue
                    keep = 1 - decay * (0.3 + 0.7 * dv / max(1, wall_h - 1))
                    if self.hash3(u, base_v + dv, w, sd + 13) > keep:
                        if dv == 0 and self.hash3(w, base_v, u, sd + 17) < 0.35:
                            self.put(u, base_v + 1, w,
                                     "cobblestone" if self.hash2(u, w, sd + 19) < 0.5 else "gravel")
                        continue
                    pick = self.hash3(u, dv, w, sd + 23)
                    self.put(u, base_v + dv, w,
                             "mossy_stone_bricks" if pick < 0.3 else
                             ("cracked_stone_bricks" if pick < 0.46 else "stonebrick"))
        for cu2, cw2 in ((u0, w0), (u0, w1), (u1, w0), (u1, w1)):
            for dv in range(wall_h + 2):
                keep = 1 - decay * 0.7 * (0.25 + 0.75 * dv / (wall_h + 1))
                if self.hash3(cu2, base_v + dv, cw2, sd + 29) <= keep:
                    self.put(cu2, base_v + dv, cw2, "chiseled_stone_bricks")
        for k in range(6):
            u = u0 + 1 + int(self.hash2(k, 0, sd + 31) * max(1, s - 2))
            w = w0 + 1 + int(self.hash2(k, 1, sd + 37) * max(1, s - 2))
            if self.hash2(u, w, sd + 41) < decay + 0.15:
                self.put(u, base_v + 1, w, "cobweb")

    def terrain(self, cu, base_v, cw, size, profile="hills", seed=None):
        s = max(2, min(48, int(size)))
        profile = str(profile or "hills").lower()
        amp = {"mountains": 14, "plateau": 6, "basin": 6, "islands": 5}.get(profile, 4)
        freq = {"mountains": 0.045, "plateau": 0.035}.get(profile, 0.06)
        sd = int(seed) if seed else self.auto_seed(cu, base_v, cw)
        water = profile in ("basin", "islands")
        half = max(1.0, s / 2)
        u0, w0 = cu - s // 2, cw - s // 2
        for du in range(s):
            for dw in range(s):
                u, w = u0 + du, w0 + dw
                n = self.fbm2(u * freq, w * freq, 4, sd)
                v = 0.5 + (n - 0.5) * 2.6
                v = max(0.0, min(0.999, v))
                if water:
                    vu, vw = (u - cu) / half, (w - cw) / half
                    fall = 1 - min(1.0, vu * vu + vw * vw)
                    v = max(0.0, min(0.999, 0.5 + (n - 0.5) * fall))
                h = self.jround((v - 0.5) * 2 * amp)
                if profile == "basin":
                    h = -abs(h)
                if profile == "plateau":
                    h = self.jround(h / 3) * 3
                top = base_v + h
                surface = ("snow_block" if amp >= 10 and h >= amp * 0.8 else
                           "stone" if amp >= 10 and h >= amp * 0.6 else
                           "sand" if water and h <= 0 else "grass_block")
                self.put(u, top, w, surface)
                self.put(u, top - 1, w, "dirt")
                self.put(u, top - 2, w, "stone")
                if water and top < base_v:
                    self.fill((u, top + 1, w), (u, base_v, w), "water")

    def road(self, u1, v1, w1, u2, v2, w2, width=5, kind="dirt", seed=None):
        width = max(1, min(16, int(width)))
        kind = str(kind or "dirt").lower()
        surface = {"stone": "stonebrick", "cobble": "cobblestone", "mud": "mud_bricks",
                   "highway": "polished_andesite"}.get(kind, "grass_path")
        border = {"stone": "chiseled_stone_bricks", "cobble": "mossy_cobblestone",
                  "mud": "mud_bricks", "highway": "deepslate_tiles"}.get(kind, "dirt")
        sd = int(seed) if seed else self.auto_seed(u1, w1, u2)
        du, dv, dw = u2 - u1, v2 - v1, w2 - w1
        length = math.sqrt(du * du + dv * dv + dw * dw)
        steps = max(1, min(2048, math.ceil(length * 2)))
        radius = max(0, (width - 1) // 2)
        nu, nw = -dw, du
        norm = math.sqrt(nu * nu + nw * nw) or 1.0
        nu, nw = nu / norm, nw / norm
        lamp_step = max(8, steps // 8)
        for i in range(steps + 1):
            t = i / steps
            ju = (self.fbm2(t * 5, 0, 2, sd + 3) - 0.5) * width * 1.2
            jw = (self.fbm2(0, t * 5, 2, sd + 9) - 0.5) * width * 1.2
            cu = self.jround(u1 + du * t + ju)
            cw = self.jround(w1 + dw * t + jw)
            cv = self.jround(v1 + dv * t)
            for ou in range(-radius, radius + 1):
                for ow in range(-radius, radius + 1):
                    edge = max(abs(ou), abs(ow)) == radius and radius > 0
                    r = self.hash2(cu + ou, cw + ow, sd + 21)
                    if edge and r > 0.9:
                        continue
                    self.put(cu + ou, cv, cw + ow, border if edge else
                             ("gravel" if not edge and r > 0.94 else surface))
                    self.put(cu + ou, cv - 1, cw + ow, "dirt")
            if i == 0 or i % lamp_step:
                continue
            lu = cu + self.jround(nu * (radius + 2))
            lw = cw + self.jround(nw * (radius + 2))
            self.fill((lu, cv + 1, lw), (lu, cv + 2, lw), "oak_fence")
            self.put(lu, cv + 3, lw, "lantern")

    # ---------- monuments ----------
    def amphitheater(self, cu, base_v, cw, outer_radius, tiers, tier_height, block, arena=None, accent=None, aisles=4):
        r, n, th = max(4, min(160, int(outer_radius))), max(1, min(40, int(tiers))), max(1, min(8, int(tier_height)))
        seat = self.block(block, "stonebrick")
        arena_b = self.block(arena, "smooth_stone")
        acc = self.block(accent, seat)
        arena_r = max(2, r // 3)
        step = max(1, (r - arena_r) // n)
        seg = 360.0 / aisles if aisles else 0
        for du in range(-arena_r, arena_r + 1):
            for dw in range(-arena_r, arena_r + 1):
                if math.hypot(du, dw) <= arena_r + 0.4:
                    self.put(cu + du, base_v, cw + dw, arena_b)
        for i in range(1, n + 1):
            r_in, r_out, top = arena_r + (i - 1) * step + 1, arena_r + i * step, base_v + i * th
            for du in range(-r_out, r_out + 1):
                for dw in range(-r_out, r_out + 1):
                    d = math.hypot(du, dw)
                    if d < r_in - 0.4 or d > r_out + 0.4:
                        continue
                    aisle = seg and abs(((math.degrees(math.atan2(dw, du)) + 180) % seg) - seg / 2) < seg * 0.07
                    if aisle:
                        self.put(cu + du, top, cw + dw, seat)
                    else:
                        self.fill((cu + du, base_v, cw + dw), (cu + du, top, cw + dw), seat)
        r_top, h_top = arena_r + n * step, base_v + n * th
        wall_out = r_top + 2
        for du in range(-wall_out, wall_out + 1):
            for dw in range(-wall_out, wall_out + 1):
                d = math.hypot(du, dw)
                if d < r_top + 0.6 or d > wall_out + 0.4:
                    continue
                pier = int(math.floor((math.degrees(math.atan2(dw, du)) + 540) / 15)) % 2 == 0
                for v in range(base_v, h_top + 3):
                    if not pier and base_v + 3 < v < h_top:
                        continue
                    self.put(cu + du, v, cw + dw, acc)

    def hypostyle_hall(self, u1, v, w1, u2, w2, spacing, height, block,
                       cap=None, ceiling=None, beam=None, floor=None):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        sp, h = max(3, min(24, int(spacing))), max(3, min(64, int(height)))
        pillar = self.block(block, "quartz_block")
        cap_b = self.block(cap, "chiseled_quartz_block")
        if floor:
            self.fill((ua, v - 1, wa), (ub, v - 1, wb), floor)
        for u in range(ua, ub + 1, sp):
            for w in range(wa, wb + 1, sp):
                self.fill((u, v, w), (u, v + h - 1, w), pillar)
                self.put(u, v + h, w, cap_b)
        beam_b = self.block(beam, pillar)
        for u in range(ua, ub + 1, sp):
            self.fill((u, v + h + 1, wa), (u, v + h + 1, wb), beam_b)
        for w in range(wa, wb + 1, sp):
            self.fill((ua, v + h + 1, w), (ub, v + h + 1, w), beam_b)
        if ceiling:
            self.fill((ua, v + h + 2, wa), (ub, v + h + 2, wb), ceiling)

    def gatehouse(self, u1, v, w1, u2, w2, height, block,
                 tower_r=None, tower_h=None, tower_block=None,
                 merlon=None, road=None):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        h = max(4, min(220, int(height)))
        wall = self.block(block, "stonebrick")
        along_x = ub - ua >= wb - wa
        span = ub - ua if along_x else wb - wa
        thick = wb - wa if along_x else ub - ua
        mid = (wa + wb) // 2 if along_x else (ua + ub) // 2
        tr = max(1, min(10, int(tower_r or max(2, span // 8))))
        th_ = max(h, min(220, int(tower_h or h + 4)))
        tb = self.block(tower_block, wall)
        mb = self.block(merlon, wall)
        road_b = self.block(road, "smooth_stone_slab")
        half = max(1, span // 3 // 2)
        spring = max(1, h * 2 // 3 - half)
        lo, hi = (ua, ub) if along_x else (wa, wb)
        center = (lo + hi) // 2
        for a in range(lo, hi + 1):
            dv = a - center
            open_top = -1
            if abs(dv) <= half:
                open_top = v + spring + self.jround(math.sqrt(max(0, half * half - dv * dv)))
            for t in range(mid - thick // 2, mid - thick // 2 + thick):
                for vv in range(v, v + h):
                    if vv <= open_top:
                        self.put(a if along_x else t, vv, t if along_x else a, "air")
                    else:
                        self.put(a if along_x else t, vv, t if along_x else a, wall)
                self.put(a if along_x else t, v + h, t if along_x else a, road_b)
                if h >= 3 and (a - lo) % 2 == 0:
                    if along_x:
                        self.put(a, v + h + 1, wa, mb)
                        self.put(a, v + h + 1, wb, mb)
                    else:
                        self.put(ua, v + h + 1, a, mb)
                        self.put(ub, v + h + 1, a, mb)
        for a in (lo + tr, hi - tr):
            tcu, tcw = (a, mid) if along_x else (mid, a)
            self.cylinder(tcu, v, tcw, tr, th_, tb)
            self.cylinder(tcu, v + th_, tcw, tr, 3, tb, True)
            for du in range(-tr, tr + 1):
                for dw in range(-tr, tr + 1):
                    if math.hypot(du, dw) <= tr + 0.4 and (du + dw) % 2 == 0:
                        self.put(tcu + du, v + th_ + 3, tcw + dw, mb)

    def flying_buttress(self, u, v, w, span, height, facing, block):
        s, h = max(2, min(32, int(span))), max(3, min(220, int(height)))
        b = self.block(block, "stonebrick")
        du, dw = self.face(facing)
        self.fill((u - 1, v, w - 1), (u + 1, v + h - 1, w + 1), b)
        for i in range(s + 1):
            pu, pw = u + du * i, w + dw * i
            pv = v + h - 1 + i // 2
            for k in (-1, 0, 1):
                if du:
                    self.fill((pu, pv + k, pw - 1), (pu, pv + k, pw + 1), b)
                else:
                    self.fill((pu - 1, pv + k, pw), (pu + 1, pv + k, pw), b)
        wu, ww = u + du * s, w + dw * s
        climb = h + s // 2
        if du:
            self.fill((wu, v, ww - 1), (wu + du, v + climb, ww + 1), b)
        else:
            self.fill((wu - 1, v, ww), (wu + 1, v + climb, ww + dw), b)

    def rose_window(self, cu, v, cw, radius, frame, glass="light_blue_stained_glass",
                    axis="z", spokes=8):
        r = max(3, min(48, int(radius)))
        fr, gl = self.block(frame, "stonebrick"), self.block(glass)
        z_axis = str(axis).lower() != "x"
        spokes = max(4, min(24, int(spokes)))
        seg = 360.0 / spokes
        for du in range(-r, r + 1):
            for dv in range(-r, r + 1):
                d = math.hypot(du, dv)
                if d > r + 0.4:
                    continue
                angle = math.degrees(math.atan2(dv, du))
                spoke = abs(((angle + 180) % seg) - seg / 2) < seg * 0.12
                mid_ring = abs(d - r * 0.6) < 0.9
                b = fr if d > r - 1.2 or spoke or mid_ring else gl
                self.put(cu + (du if z_axis else 0), v + dv,
                         cw + (0 if z_axis else du), b)

    def cloister(self, cu, v, cw, inner_half, corridor_width, height, block,
                 floor="stonebrick", roof=None, pave="grass_block", spacing=3):
        hh, cwid, h = max(3, min(160, int(inner_half))), max(2, min(16, int(corridor_width))), max(3, min(48, int(height)))
        pillar = self.block(block, "stonebrick")
        outer = hh + cwid
        self.fill((cu - hh, v, cw - hh), (cu + hh, v, cw + hh), pave)
        for u in range(cu - outer, cu + outer + 1):
            for w in range(cw - outer, cw + outer + 1):
                if abs(u - cu) <= hh and abs(w - cw) <= hh:
                    continue
                self.put(u, v, w, floor)
        for a in range(-hh, hh + 1):
            if a % max(2, int(spacing)) and abs(a) != hh:
                continue
            for vv in range(v + 2, v + h):
                self.put(cu + a, vv, cw - hh, pillar)
                self.put(cu + a, vv, cw + hh, pillar)
                self.put(cu - hh, vv, cw + a, pillar)
                self.put(cu + hh, vv, cw + a, pillar)
        for a in range(cu - outer, cu + outer + 1):
            for vv in range(v + 1, v + h):
                self.put(a, vv, cw - outer, pillar)
                self.put(a, vv, cw + outer, pillar)
        for a in range(cw - outer + 1, cw + outer):
            for vv in range(v + 1, v + h):
                self.put(cu - outer, vv, a, pillar)
                self.put(cu + outer, vv, a, pillar)
        if roof:
            for u in range(cu - hh, cu + outer + 1):
                for w in range(cw - hh, cw + outer + 1):
                    if abs(u - cu) < hh and abs(w - cw) < hh:
                        continue
                    self.put(u, v + h, w, roof)

    def keep(self, u, v, w, width, depth, height, block, merlon=None,
             tower_block=None, roof=None, tower_r=None, door=True):
        W, D, H = max(5, min(160, int(width))), max(5, min(160, int(depth))), max(4, min(220, int(height)))
        wall = self.block(block, "stonebrick")
        mb = self.block(merlon, wall)
        tb = self.block(tower_block, wall)
        tr = max(1, min(8, int(tower_r or max(2, min(W, D) // 6))))
        u2, w2 = u + W - 1, w + D - 1
        door_cu = (u + u2) // 2
        for vv in range(v, v + H):
            for uu in range(u, u2 + 1):
                if not (door and vv < v + 4 and abs(uu - door_cu) <= 1):
                    self.put(uu, vv, w, wall)
                self.put(uu, vv, w2, wall)
            for ww in range(w + 1, w2):
                self.put(u, vv, ww, wall)
                self.put(u2, vv, ww, wall)
            if vv > v and (vv - v) % 6 == 0:
                self.fill((u + 1, vv, w + 1), (u2 - 1, vv, w2 - 1), wall)
        for uu in range(u, u2 + 1):
            if (uu - u) % 2 == 0:
                self.put(uu, v + H, w, mb)
                self.put(uu, v + H, w2, mb)
        for ww in range(w + 1, w2):
            if (ww - w) % 2 == 0:
                self.put(u, v + H, ww, mb)
                self.put(u2, v + H, ww, mb)
        tower_top = v + H + tr + 1
        for cu, cw in ((u, w), (u, w2), (u2, w), (u2, w2)):
            self.cylinder(cu, v, cw, tr, tower_top - v, tb)
            for du in range(-tr, tr + 1):
                for dw in range(-tr, tr + 1):
                    if math.hypot(du, dw) <= tr + 0.4 and (du + dw) % 2 == 0:
                        self.put(cu + du, tower_top, cw + dw, mb)
        if roof:
            for i in range(max(W, D) // 2 + 1):
                if u + i > u2 - i or w + i > w2 - i:
                    break
                self.fill((u + i, v + H + i, w + i), (u2 - i, v + H + i, w2 - i), roof)

    def steeple(self, cu, v, cw, width, height, block, band=None,
                spire=None, band_every=6, belfry=5):
        w = max(3, min(31, int(width)))
        if w % 2 == 0:
            w += 1
        h = max(6, min(220, int(height)))
        wall = self.block(block, "stonebrick")
        band_b = self.block(band, "chiseled_stone_bricks")
        spire_b = self.block(spire, "deepslate_tiles")
        band_every, belfry = max(2, min(20, int(band_every))), max(0, min(12, int(belfry)))
        half = w // 2
        belfry_start = max(1, h - belfry)
        for k in range(h):
            is_band = k > 0 and k % band_every == 0
            open_belfry = belfry > 0 and k >= belfry_start
            for du in range(-half, half + 1):
                for dw in range(-half, half + 1):
                    if abs(du) != half and abs(dw) != half:
                        continue
                    if open_belfry and not (abs(du) == half and abs(dw) == half):
                        continue
                    self.put(cu + du, v + k, cw + dw, band_b if is_band else wall)
        for du in range(-half - 1, half + 2):
            for dw in (-half - 1, half + 1):
                self.put(cu + du, v + h, cw + dw, band_b)
        for dw in range(-half, half + 1):
            for du in (-half - 1, half + 1):
                self.put(cu + du, v + h, cw + dw, band_b)
        top, cur, level = v + h + 1, half, 0
        while cur > 0:
            self.ring(cu - cur, cw - cur, cu + cur, cw + cur, top + level, spire_b)
            level += 1
            if level % 2 == 0:
                cur -= 1
        self.fill((cu, top + level, cw), (cu, top + level + 1, cw), spire_b)
        self.put(cu, top + level + 2, cw, "lantern")

    def triumphal_arch(self, cu, v, cw, span, height, thickness, facing, block, accent=None):
        sp, h, th = max(3, min(60, int(span))), max(6, min(220, int(height))), max(2, min(16, int(thickness)))
        body, acc = self.block(block, "quartz_block"), self.block(accent, "chiseled_quartz_block")
        along = str(facing or "south").lower() in ("north", "south")
        half, pier = sp // 2, max(2, sp // 5)
        spring = max(1, h * 2 // 3 - half)
        u0 = cu - half - pier if along else cu - th // 2
        u1 = cu + half + pier if along else u0 + th - 1
        w0 = cw - th // 2 if along else cw - half - pier
        w1 = w0 + th - 1 if along else cw + half + pier
        for u in range(u0, u1 + 1):
            for w in range(w0, w1 + 1):
                off = u - cu if along else w - cw
                open_top = v + spring + self.jround(math.sqrt(max(0, half * half - off * off))) if abs(off) <= half else -1
                for vv in range(v, v + h):
                    if vv > open_top:
                        self.put(u, vv, w, acc if vv >= v + h - 1 else body)
                self.put(u, v + h, w, acc)
        self.ring(u0 - 1, w0 - 1, u1 + 1, w1 + 1, v + h, acc)
        for du, dw in ((u0, w0), (u1, w1)):
            self.put(du, v + h + 1, dw, acc)
            self.put(du, v + h + 2, dw, acc)

    def window_band(self, u1, v, w1, u2, w2, height, wall, glass, spacing=4, width=2):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        h, spacing, width = max(1, min(12, int(height))), max(2, min(24, int(spacing))), max(1, min(6, int(width)))
        along = ub - ua >= wb - wa
        lo, hi = (ua, ub) if along else (wa, wb)
        any_slot = False
        a = lo + spacing // 2
        while a + width - 1 <= hi - spacing // 2:
            self._window_slot(a, v, width, h, along, wall, glass, ua, ub, wa, wb)
            any_slot = True
            a += spacing
        if not any_slot:
            ww = min(width, hi - lo + 1)
            mid = max(lo, min(hi - ww + 1, (lo + hi) // 2 - ww // 2))
            self._window_slot(mid, v, ww, h, along, wall, glass, ua, ub, wa, wb)

    def _window_slot(self, a, v, width, height, along, wall, glass, ua, ub, wa, wb):
        for k in range(width):
            g = a + k
            for t in range(wa, wb + 1) if along else range(ua, ub + 1):
                for vv in range(v, v + height):
                    self.put(g if along else t, vv, t if along else g, glass)
                self.put(g if along else t, v + height, t if along else g, wall)
                self.put(g if along else t, v - 1, t if along else g, wall)
        for g in (a - 1, a + width):
            for t in range(wa, wb + 1) if along else range(ua, ub + 1):
                for vv in range(v, v + height):
                    self.put(g if along else t, vv, t if along else g, wall)

    def coffer_ceiling(self, u1, v, w1, u2, w2, cell, block, inset=None):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        c = max(2, min(24, int(cell)))
        rib = self.block(block, "deepslate_tiles")
        self.fill((ua, v, wa), (ub, v, wb), self.block(inset, rib))
        for u in range(ua, ub + 1, c):
            self.fill((u, v, wa), (u, v, wb), rib)
        for w in range(wa, wb + 1, c):
            self.fill((ua, v, w), (ub, v, w), rib)

    def plaza_paving(self, u1, v, w1, u2, w2, a, b, pattern="checker", scale=3):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        scale = max(1, min(16, int(scale)))
        pattern = str(pattern or "checker").lower()
        cu, cw = (ua + ub) / 2, (wa + wb) / 2
        for u in range(ua, ub + 1):
            for w in range(wa, wb + 1):
                if pattern == "stripes":
                    use_b = (u - ua) // scale % 2 == 1
                elif pattern == "rings":
                    d = min(u - ua, ub - u, w - wa, wb - w)
                    use_b = d // scale % 2 == 1
                elif pattern == "border":
                    use_b = u < ua + scale or u > ub - scale or w < wa + scale or w > wb - scale
                elif pattern == "diamond":
                    use_b = (abs(u - ua) + abs(w - wa)) // scale % 2 == 1
                elif pattern == "radial":
                    angle = math.degrees(math.atan2(w - cw, u - cu))
                    use_b = int(math.floor((angle + 540) / (180 / scale))) % 2 == 0
                else:
                    use_b = (u + w) % 2 == 0
                self.put(u, v, w, b if use_b else a)

    def colonnaded_street(self, u1, v, w1, u2, w2, spacing, height, block,
                          pave="smooth_stone", roof=None, side_offset=3):
        sp, h = max(2, min(24, int(spacing))), max(2, min(64, int(height)))
        col = self.block(block, "quartz_block")
        side = max(1, min(16, int(side_offset)))
        cu, cw = u2 - u1, w2 - w1
        length = math.hypot(cu, cw)
        if length < 1:
            raise ValueError("colonnaded_street 两端不能重合")
        nu, nw = -cw / length, cu / length
        steps = max(2, min(4096, int(length * 2) + 1))
        for i in range(steps + 1):
            t = i / steps
            bu, bw = self.jround(u1 + cu * t), self.jround(w1 + cw * t)
            for s in range(-side, side + 1):
                self.put(bu + self.jround(nu * s), v, bw + self.jround(nw * s), pave)
        cols = max(2, min(4096, int(length // sp) + 1))
        for i in range(cols):
            t = i / (cols - 1)
            bu, bw = self.jround(u1 + cu * t), self.jround(w1 + cw * t)
            for s in (-side, side):
                su, sw = bu + self.jround(nu * s), bw + self.jround(nw * s)
                self.fill((su, v + 1, sw), (su, v + h, sw), col)
                if roof:
                    self.put(su, v + h + 1, sw, roof)
        if roof:
            for i in range(steps + 1):
                t = i / steps
                bu, bw = self.jround(u1 + cu * t), self.jround(w1 + cw * t)
                for s in range(-side, side + 1):
                    self.put(bu + self.jround(nu * s), v + h + 1, bw + self.jround(nw * s), roof)

    def rampart(self, u1, v, w1, u2, w2, height, thickness, block,
                walkway=None, merlon=None):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        h, th = max(2, min(220, int(height))), max(1, min(12, int(thickness)))
        wall = self.block(block, "stonebrick")
        mb = self.block(merlon, wall)
        walk = self.block(walkway, wall)
        along = ub - ua >= wb - wa
        lo, hi = (ua, ub) if along else (wa, wb)
        edge = (wa if along else ua) - th // 2
        for a in range(lo, hi + 1):
            for t in range(th):
                o = edge + t
                self.fill((a if along else o, v, o if along else a),
                          (a if along else o, v + h - 1, o if along else a), wall)
                self.put(a if along else o, v + h, o if along else a, walk)
            if (a - lo) % 2 == 0:
                self.put(a if along else edge, v + h + 1, edge if along else a, mb)

    def balustrade_run(self, u1, v, w1, u2, w2, block, post_every=6):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        b = self.block(block, "stonebrick")
        along = ub - ua >= wb - wa
        lo, hi = (ua, ub) if along else (wa, wb)
        fixed = wa if along else ua
        sp = max(2, min(32, int(post_every)))
        for i in range(lo, hi + 1):
            a = i - lo
            u, w = (i, fixed) if along else (fixed, i)
            self.put(u, v, w, b)
            self.put(u, v + 2, w, b)
            if a % sp == 0 or a % 2 == 0:
                self.put(u, v + 1, w, b)

    def banner_row(self, u1, v, w1, u2, w2, height, block, accent="red_wool", spacing=5):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        h = max(1, min(12, int(height)))
        along = ub - ua >= wb - wa
        lo, hi = (ua, ub) if along else (wa, wb)
        fixed = wa if along else ua
        sp = max(1, min(32, int(spacing)))
        for i in range(lo, hi + 1):
            u, w = (i, fixed) if along else (fixed, i)
            self.put(u, v, w, block)
            if (i - lo) % sp == 0:
                for k in range(1, h + 1):
                    self.put(i + 1 if along else fixed, v - k,
                             fixed if along else i + 1, accent)

    def statue_group(self, cu, v, cw, count, height, block, base="stonebrick", radius=8):
        n, bh = max(1, min(32, int(count))), max(3, min(16, int(height)))
        body = self.block(block, "quartz_block")
        for i in range(n):
            angle = math.tau * i / n
            su = cu + self.jround(radius * math.cos(angle))
            sw = cw + self.jround(radius * math.sin(angle))
            self.fill((su - 1, v, sw - 1), (su + 1, v + 1, sw + 1), base)
            self.fill((su, v + 2, sw), (su, v + 1 + bh, sw), body)
            self.put(su - 1, v + bh - 1, sw, body)
            self.put(su + 1, v + bh - 1, sw, body)
            self.put(su, v + bh + 2, sw, body)

    # ---------- whole-building templates ----------
    def medieval_house(self, u, v, w, size=9, wall="white_terracotta",
                       floor="spruce_planks", roof_fill="cobblestone_stairs"):
        s = max(7, int(size))
        self.box_shell(u, v, w, u + s, v + 4, w + s, wall, True, True)
        self.fill((u, v, w), (u + s, v, w + s), floor)
        for pu, pw in ((u, w), (u + s, w), (u, w + s), (u + s, w + s)):
            self.fill((pu, v, pw), (pu, v + 4, pw), "dark_oak_log")
        self.gable(u - 1, v + 5, w - 1, u + s + 1, w + s + 1, (s + 3) // 2, roof_fill, axis="u")
        self.fill((u + 1, v, w), (u + s - 1, v + 2, w), "air")
        cx = u + s // 2
        self.doorway(cx, v, w, "front", "wooden_door", {"frame": "dark_oak_planks"})
        self.window_row(cx, v + 2, w + s, 1, 4, "back", "dark_oak_planks", "glass_pane")
        self.chimney_stack(u + s - 1, v + 5, w + s - 1, 3, "brick_block")
        self.table(cx, v + 1, w + s // 2, 2)
        self.fireplace(u + s - 1, v + 1, w + s // 2, "left", "brick_block")
        self.chandelier(cx, v + 4, w + s // 2, 1, "chain", "lantern")

    def chinese_pavilion(self, cu, v, cw, half_width=4, pillar_height=4,
                         pillar="spruce_log", tile="deepslate_tiles",
                         ridge="polished_blackstone", base="stonebrick"):
        hw = max(2, int(half_width))
        self.sumeru_base(cu - hw - 1, cw - hw - 1, cu + hw + 1, cw + hw + 1, v, 2, base)
        self.railing(cu - hw - 1, cw - hw - 1, cu + hw + 1, cw + hw + 1, v + 2, 3, base)
        for du in (-hw, hw):
            for dw in (-hw, hw):
                self.fill((cu + du, v + 2, cw + dw), (cu + du, v + 1 + pillar_height, cw + dw), pillar)
        self.dougong(cu - hw, v + 1 + pillar_height, cw - hw, 1, 2, pillar)
        self.dougong(cu + hw, v + 1 + pillar_height, cw - hw, 1, 2, pillar)
        self.dougong(cu - hw, v + 1 + pillar_height, cw + hw, 1, 2, pillar)
        self.dougong(cu + hw, v + 1 + pillar_height, cw + hw, 1, 2, pillar)
        self.chinese_roof(cu - hw - 2, cw - hw - 2, cu + hw + 2, cw + hw + 2,
                          v + 3 + pillar_height, max(3, hw), "攒尖", tile, ridge)

    def japanese_pagoda(self, cu, v, cw, radius=4, tiers=3, tier_height=3,
                        body="dark_oak_planks", eave="dark_oak_slab"):
        self.pagoda(cu, cw, v, radius, tiers, tier_height, 4, body, eave)

    def roman_temple(self, cu, v, cw, width=11, depth=15, column_height=6,
                     stylobate=2, stone="quartz_block", tile="deepslate_tiles"):
        W, D = max(7, int(width)), max(9, int(depth))
        hu, hw = W // 2, D // 2
        for i in range(stylobate):
            self.ring(cu - hu - i, cw - hw - i, cu + hu + i, cw + hw + i, v - i - 1, stone)
        floor_v = v + stylobate - 1
        self.fill((cu - hu, floor_v, cw - hw), (cu + hu, floor_v, cw + hw), stone)
        cols = 4
        for i in range(cols):
            pu = cu - hu + 1 + self.jround((2 * hu - 2) * i / (cols - 1))
            for pw in (cw - hw + 1, cw + hw - 1):
                self.classical_column(pu, pw, floor_v + 1, column_height, 1, stone)
        self.fill((cu - hu + 1, floor_v + column_height, cw - hw + 1),
                  (cu + hu - 1, floor_v + column_height, cw + hw - 1), stone)
        self.gable(cu - hu - 1, floor_v + column_height + 1, cw - hw - 1,
                   cu + hu + 1, cw + hw + 1, max(3, hu // 2), tile, axis="u")

    def modern_villa(self, u, v, w, width=15, depth=11, floors=2, floor_height=4,
                     wall="white_concrete", glass="glass_pane", accent="dark_oak_planks"):
        W, D, H = max(9, int(width)), max(7, int(depth)), max(3, int(floor_height))
        for f in range(max(1, int(floors))):
            fu, fw = u + (f % 2) * 2, w + (f % 2) * 2
            base = v + f * H
            self.fill((fu, base, fw), (fu + W - 1, base, fw + D - 1), accent)
            for side in range(4):
                if side == 0:
                    self.curtain_wall(fu, base + 1, fw, fu + W - 1, base + H - 1, fw, 3, 2, accent, glass)
                elif side == 1:
                    self.curtain_wall(fu, base + 1, fw + D - 1, fu + W - 1, base + H - 1, fw + D - 1, 3, 2, accent, glass)
                elif side == 2:
                    self.curtain_wall(fu, base + 1, fw, fu, base + H - 1, fw + D - 1, 3, 2, accent, glass)
                else:
                    self.curtain_wall(fu + W - 1, base + 1, fw, fu + W - 1, base + H - 1, fw + D - 1, 3, 2, accent, glass)
        self.fill((u, v + floors * H, w), (u + W - 1, v + floors * H, w + D - 1), wall)
        self.balustrade(u, w, u + W - 1, w + D - 1, v + floors * H + 1, 3, wall)

    def castle_keep(self, u, v, w, width=13, depth=13, height=16, block="stonebrick"):
        self.keep(u, v, w, width, depth, height, block, tower_radius=max(2, min(width, depth) // 6))

    def city_wall(self, u1, v, w1, u2, w2, height=7, thickness=3, block="stonebrick",
                  walkway=None, merlon=None):
        self.rampart(u1, v, w1, u2, w2, height, thickness, block, walkway, merlon)

    def lighthouse(self, cu, v, cw, radius=4, height=18, block="quartz_block",
                   band="red_terracotta", light="sea_lantern"):
        r, h = max(2, int(radius)), max(6, int(height))
        step = max(3, h // 6)
        for k in range(h):
            rr = max(1, r - k * r // (h + 4))
            self.cylinder(cu, v + k, cw, rr, 1, band if (k // step) % 2 else block)
        self.fill((cu - r - 1, v + h, cw - r - 1), (cu + r + 1, v + h, cw + r + 1), block)
        self.railing(cu - r - 1, cw - r - 1, cu + r + 1, cw + r + 1, v + h, 2, block)
        self.fill((cu, v + h + 1, cw), (cu, v + h + 3, cw), light)
        self.cone(cu, v + h + 4, cw, r, r + 1, band)

    def windmill(self, cu, v, cw, radius=4, tower_height=10, blade_length=7,
                 tower="cobblestone", blade="oak_planks"):
        self.cylinder(cu, v, cw, radius, tower_height, tower, True)
        self.cone(cu, v + tower_height, cw, radius + 1, radius + 2, "deepslate_tiles")
        for k in range(4):
            angle = math.tau * k / 4
            du, dw = math.cos(angle), math.sin(angle)
            for i in range(1, int(blade_length) + 1):
                for t in (-1, 0, 1):
                    self.put(cu + self.jround(du * i) + self.jround(-dw * t),
                             v + tower_height - 1 + self.jround(dw * i) + self.jround(du * t),
                             cw + 1, blade)

    def harbor_dock(self, u1, w1, u2, w2, v, water_v=None, deck="oak_planks",
                    post="oak_log", rail="oak_fence"):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        self.fill((ua, v, wa), (ub, v, wb), deck)
        for u in range(ua, ub + 1, 4):
            for w in (wa, wb):
                self.fill((u, (water_v if water_v is not None else v - 3), w), (u, v - 1, w), post)
        self.fill((ua, v + 1, wa), (ub, v + 1, wa), rail)
        self.fill((ua, v + 1, wb), (ub, v + 1, wb), rail)
