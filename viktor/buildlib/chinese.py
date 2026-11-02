class _ChineseLib:
    def _roof_height(self, u, w, ua, wa, ub, wb, base_v, height, gable_at, point_top, hung=False):
        half_u = max(1, (ub - ua) // 2)
        half_w = max(1, (wb - wa) // 2)
        cap = max(1, min(half_u, half_w))
        due, dwe = min(u - ua, ub - u), min(w - wa, wb - w)
        if hung and not point_top:
            along = ub - ua >= wb - wa
            perp = dwe if along else due
            s = self.juzhe(perp / cap)
        elif point_top:
            s = self.juzhe(min(due / half_u, dwe / half_w))
        elif gable_at > 0:
            g = min(0.95, gable_at)
            in_u = max(1, self.jround(cap * g ** (1 / 1.65)))
            end = self.juzhe(dwe / cap)
            s = end if due >= in_u else min(end, g * self.juzhe(due / in_u))
        else:
            s = min(self.juzhe(due / cap), self.juzhe(dwe / cap))
        return base_v + self.jround(height * s)

    def _roof_shell(self, ua, wa, ub, wb, base_v, height, gable_at, point_top,
                    block, ridge=None, tile_every=2, hung=False, gable_wall=None, flare=False):
        if height <= 0 or ub <= ua or wb <= wa:
            raise ValueError("屋顶范围每边至少 3 格，高度必须 >0")
        width, depth = ub - ua + 1, wb - wa + 1
        max_v = base_v + height
        hf = [[self._roof_height(ua + i, wa + j, ua, wa, ub, wb, base_v, height,
                                 gable_at, point_top, hung)
               for j in range(depth)] for i in range(width)]
        if flare:
            r = max(2, min(8, min(width, depth) // 10))
            lift_max = max(1, self.jround(height * 0.3))
            for i in range(width):
                for j in range(depth):
                    corner = max(min(i, width - 1 - i), min(j, depth - 1 - j))
                    if corner <= r:
                        t = corner / r
                        lift = self.jround(lift_max * (1 - t) ** 1.7)
                        hf[i][j] += max(0, lift)
        rb = self.block(ridge, self.block(block))
        for i in range(width):
            for j in range(depth):
                v = hf[i][j]
                lo = v
                if i > 0:
                    lo = min(lo, hf[i - 1][j])
                if i < width - 1:
                    lo = min(lo, hf[i + 1][j])
                if j > 0:
                    lo = min(lo, hf[i][j - 1])
                if j < depth - 1:
                    lo = min(lo, hf[i][j + 1])
                lo -= 1
                eave = i in (0, width - 1) or j in (0, depth - 1)
                for vv in range(lo, v + 1):
                    self.put(ua + i, vv, wa + j, rb if eave and vv == lo else block)
        if hung and gable_wall:
            along = ub - ua >= wb - wa
            if along:
                for j in range(depth):
                    for i in (0, width - 1):
                        self.fill((ua + i, base_v, wa + j), (ua + i, hf[i][j], wa + j), gable_wall)
            else:
                for i in range(width):
                    for j in (0, depth - 1):
                        self.fill((ua + i, base_v, wa + j), (ua + i, hf[i][j], wa + j), gable_wall)
        if tile_every < 0:
            return
        every = max(0, tile_every)
        for i in range(width):
            for j in range(depth):
                u, w, v = ua + i, wa + j, hf[i][j]
                due, dwe = min(i, width - 1 - i), min(j, depth - 1 - j)
                on_ridge = v == max_v or (due == dwe and due > 0)
                if on_ridge:
                    self.put(u, v + 1, w, rb)
                    if v == max_v:
                        self.put(u, v + 2, w, rb)
                elif every > 0 and (i % every == 0 if dwe < due else j % every == 0):
                    self.put(u, v + 1, w, block)

    def chinese_roof(self, u1, w1, u2, w2, base_v, height, style,
                     tile, ridge=None):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        if height <= 0 or ub - ua < 2 or wb - wa < 2:
            raise ValueError("chinese_roof: 屋顶每边至少 3 格，height 必须 >0")
        st = str(style or "歇山").strip()
        aliases = {"wudian": "庑殿", "xieshan": "歇山", "cuanjian": "攒尖",
                   "xuanshan": "悬山", "yingshan": "硬山", "double_wudian": "重檐庑殿",
                   "double_xieshan": "重檐歇山"}
        st = aliases.get(st.lower(), st)
        allowed = ("庑殿", "歇山", "攒尖", "悬山", "硬山", "重檐庑殿", "重檐歇山", "亭")
        if not any(k in st for k in allowed):
            raise ValueError("chinese_roof style 应为 庑殿/歇山/攒尖/悬山/硬山/重檐庑殿/重檐歇山")
        doubled = "重檐" in st
        pointed = "攒" in st or "亭" in st
        hung = "悬" in st or "硬" in st
        gable = 0.55 if "歇" in st else 0.0
        if pointed or hung:
            gable = 0.0
        every = 3 if max(ub - ua, wb - wa) < 14 else 2
        flare = not hung
        if not doubled:
            self._roof_shell(ua, wa, ub, wb, base_v, int(height), gable, pointed,
                             tile, ridge, every, hung, ridge if hung else None, flare)
            return
        h1 = max(2, self.jround(height * 0.4))
        h2 = max(2, int(height) - h1 - 2)
        self._roof_shell(ua, wa, ub, wb, base_v, h1, gable, False,
                         tile, ridge, every, hung, ridge if hung else None, flare)
        waist_v = base_v + h1 + 1
        inset_u = max(2, self.jround((ub - ua) * 0.16))
        inset_w = max(2, self.jround((wb - wa) * 0.16))
        iu1, iu2, iw1, iw2 = ua + inset_u, ub - inset_u, wa + inset_w, wb - inset_w
        if iu2 - iu1 < 2 or iw2 - iw1 < 2:
            raise ValueError("重檐屋顶太小：内收后上下檐均需至少 3×3；请扩大平面或改用单檐")
        rb = self.block(ridge, self.block(tile))
        self.ring(iu1, iw1, iu2, iw2, waist_v, rb)
        self.ring(iu1, iw1, iu2, iw2, waist_v + 1, rb)
        every2 = 3 if max(iu2 - iu1, iw2 - iw1) < 14 else 2
        self._roof_shell(iu1, iw1, iu2, iw2, waist_v + 2, h2, gable, False,
                         tile, ridge, every2, hung, ridge if hung else None, flare)

    def curved_roof(self, u1, w1, u2, w2, base_v, height, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        depth = wb - wa
        if depth <= 0 or height < 0:
            raise ValueError("curved_roof: 进深至少 2 格，height 不能为负")
        half = max(1, depth // 2)
        previous = None
        for i in range(depth + 1):
            dist = min(i, depth - i)
            lift = self.jround(height * min(1, dist / half) ** 1.7)
            v = base_v + lift
            if previous is not None:
                self.fill((ua, min(previous, v), wa + i), (ub, max(previous, v), wa + i), block)
            previous = v

    def flying_eave(self, u1, w1, u2, w2, v, lift, corner_span, out, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        span = max(1, int(corner_span))
        for u in range(ua, ub + 1):
            for w in range(wa, wb + 1):
                if u not in (ua, ub) and w not in (wa, wb):
                    continue
                along, edge_len = ((u - ua, ub - ua) if w in (wa, wb) else (w - wa, wb - wa))
                corner_dist = min(along, edge_len - along)
                t = 1 - min(1, corner_dist / span)
                lift_here = self.jround(lift * t * t)
                if corner_dist == 0 and out > 0:
                    ou = -out if u == ua else (out if u == ub else 0)
                    ow = -out if w == wa else (out if w == wb else 0)
                    if ou or ow:
                        self.put(u + ou, v + lift_here, w + ow, block)
                for k in range(lift_here + 1):
                    self.put(u, v + k, w, block)

    def xieshan_roof(self, u1, w1, u2, w2, base_v, height, gable_at, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        self._roof_shell(ua, wa, ub, wb, base_v, height, max(0.1, min(0.95, gable_at)),
                         False, block, block, -1)

    def chinese_hip_roof(self, u1, w1, u2, w2, base_v, height, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        self._roof_shell(ua, wa, ub, wb, base_v, height, 0, False, block, block, -1)

    def pyramid_roof(self, cu, cw, base_v, half_width, height, finial, block, finial_block=None):
        h = max(1, int(height))
        self._roof_shell(cu - half_width, cw - half_width, cu + half_width, cw + half_width,
                         base_v, h, 0, True, block, block, -1)
        for k in range(1, max(0, int(finial)) + 1):
            self.put(cu, base_v + h + k, cw, self.block(finial_block, self.block(block)))

    def dougong(self, cu, cv, cw, radius, layers, block):
        if layers <= 0:
            raise ValueError("dougong layers 必须 >0")
        for k in range(int(layers)):
            r = max(1, int(radius)) + k
            self.ring(cu - r, cw - r, cu + r, cw + r, cv + k, block)

    def sumeru_base(self, u1, w1, u2, w2, base_v, height, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        if height <= 0:
            raise ValueError("sumeru_base height 必须 >0")
        for i in range(int(height)):
            waist = height >= 3 and 0 < i < height - 1
            inset = 1 if waist else 0
            if ua + inset > ub - inset or wa + inset > wb - inset:
                raise ValueError("sumeru_base 平面太小，无法做束腰")
            if i == height - 1:
                self.fill((ua + inset, base_v + i, wa + inset),
                          (ub - inset, base_v + i, wb - inset), block)
            else:
                self.ring(ua + inset, wa + inset, ub - inset, wb - inset, base_v + i, block)

    def moon_gate(self, cu, cv, cw, axis, radius, trim):
        if radius <= 0:
            raise ValueError("moon_gate radius 必须 >0")
        along = self.axis_u(axis)
        r, rr, outer = int(radius), int(radius) ** 2, (int(radius) + 1) ** 2
        for du in range(-r - 1, r + 2):
            for dv in range(-r - 1, r + 2):
                d2 = du * du + dv * dv
                u, w = (cu + du, cw) if along else (cu, cw + du)
                if d2 <= rr:
                    self.put(u, cv + dv, w, "air")
                elif trim and d2 <= outer:
                    self.put(u, cv + dv, w, trim)

    def railing(self, u1, w1, u2, w2, v, post_every, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        every = max(2, int(post_every))
        for u in range(ua, ub + 1):
            for w in range(wa, wb + 1):
                if u not in (ua, ub) and w not in (wa, wb):
                    continue
                along = u - ua if w in (wa, wb) else w - wa
                post = along % every == 0 or (u == ub and w in (wa, wb)) or (w == wb and u in (ua, ub))
                self.put(u, v + 1, w, block)
                if post:
                    self.put(u, v + 2, w, block)

    def pagoda(self, cu, cw, base_v, radius, tiers, tier_height, sides, body, eave):
        if tiers <= 0 or tier_height <= 0:
            raise ValueError("pagoda tiers/tier_height 必须 >0")
        v = base_v
        for t in range(int(tiers)):
            r = max(1, int(radius) - t)
            for k in range(int(tier_height)):
                for du in range(-r - 1, r + 2):
                    for dw in range(-r - 1, r + 2):
                        if self.polygon_ring(du, dw, r, sides):
                            self.put(cu + du, v + k, cw + dw, body)
            ev = v + tier_height
            for du in range(-r - 2, r + 3):
                for dw in range(-r - 2, r + 3):
                    if self.polygon_ring(du, dw, r + 1, sides):
                        self.put(cu + du, ev, cw + dw, self.block(eave, self.block(body)))
            v += tier_height + 1
        self.put(cu, v, cw, self.block(eave, self.block(body)))
        self.put(cu, v + 1, cw, self.block(eave, self.block(body)))

    def tile_ridges(self, u1, w1, u2, w2, base_v, height, ridge_every, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        depth = wb - wa
        if depth <= 0:
            raise ValueError("tile_ridges 进深至少 2 格")
        every, half = max(1, int(ridge_every)), max(1, depth // 2)
        for u in range(ua, ub + 1):
            if (u - ua) % every:
                continue
            for i in range(depth + 1):
                t = min(i, depth - i) / half
                v = base_v + self.jround(height * min(1, t) ** 1.7)
                self.put(u, v + 1, wa + i, block)

    def caisson_ceiling(self, cu, cv, cw, half_width, layers, block, center_block=None):
        hw = int(half_width)
        if hw <= 0 or layers <= 0:
            raise ValueError("caisson_ceiling half_width/layers 必须 >0")
        for i in range(int(layers)):
            if hw < 0:
                break
            if hw == 0:
                self.put(cu, cv + i, cw, self.block(center_block, self.block(block)))
            else:
                self.ring(cu - hw, cw - hw, cu + hw, cw + hw, cv + i, block)
            hw -= 1

    def sparrow_bracket(self, cu, cv, cw, axis, size, block):
        along = self.axis_u(axis)
        for k in range(max(1, int(size))):
            width = int(size) - k
            for d in range(width):
                self.put(cu + (d if along else 0), cv - k, cw + (0 if along else d), block)

    def hanging_lattice(self, u1, v, w1, u2, w2, step, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        st = max(1, int(step))
        for u in range(ua, ub + 1):
            for w in range(wa, wb + 1):
                if u not in (ua, ub) and w not in (wa, wb):
                    continue
                along = u - ua if w in (wa, wb) else w - wa
                if st == 1 or along % st != 1:
                    self.put(u, v, w, block)

    def horse_head_wall(self, u1, w1, u2, w2, base_v, steps, step_width, step_height, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        sw, sh = max(1, int(step_width)), max(1, int(step_height))
        if steps <= 0:
            raise ValueError("horse_head_wall steps 必须 >0")
        for u in range(ua, ub + 1):
            dist = min(u - ua, ub - u)
            level = min(int(steps) - 1, dist // sw)
            top = base_v + (int(steps) - 1 - level) * sh
            self.fill((u, base_v, wa), (u, top, wb), block)

    def screen_wall(self, cu, cv, cw, axis, width, height, block, cap_block=None):
        if width <= 0 or height <= 0:
            raise ValueError("screen_wall width/height 必须 >0")
        along, half = self.axis_u(axis), int(width) // 2
        for d in range(-half, half + 1):
            u, w = (cu + d, cw) if along else (cu, cw + d)
            self.fill((u, cv, w), (u, cv + height - 1, w), block)
            self.put(u, cv + height, w, self.block(cap_block, self.block(block)))
        for d in (-half - 1, half + 1):
            u, w = (cu + d, cw) if along else (cu, cw + d)
            self.put(u, cv + height, w, self.block(cap_block, self.block(block)))

    def paifang(self, cu, cv, cw, axis, spans, height, span_width,
                column_block, beam_block, roof_block):
        if spans <= 0:
            raise ValueError("paifang spans 必须 >0")
        along, sw = self.axis_u(axis), max(1, int(span_width))
        half = int(spans) * sw // 2
        for c in range(int(spans) + 1):
            d = -half + c * sw
            u, w = (cu + d, cw) if along else (cu, cw + d)
            self.fill((u, cv, w), (u, cv + height, w), column_block)
        for d in range(-half, half + 1):
            u, w = (cu + d, cw) if along else (cu, cw + d)
            self.put(u, cv + height, w, beam_block)
        for d in range(-half - 1, half + 2):
            u, w = (cu + d, cw) if along else (cu, cw + d)
            self.put(u, cv + height + 1, w, roof_block)

    def ridge_beasts(self, u1, w1, u2, w2, v, count, block):
        along = abs(u2 - u1) >= abs(w2 - w1)
        a1, a2 = self.span(u1 if along else w1, u2 if along else w2)
        fixed = w1 if along else u1
        for end in (a1, a2):
            for k in (1, 2):
                self.put(end if along else fixed, v + k, fixed if along else end, block)
        for i in range(1, max(0, int(count)) + 1):
            a = a1 + self.jround((a2 - a1) * i / (int(count) + 1))
            self.put(a if along else fixed, v + 1, fixed if along else a, block)

    def stepped_terrace(self, u1, w1, u2, w2, base_v, steps, step_height, step_depth, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        sh, sd = max(1, int(step_height)), max(1, int(step_depth))
        for i in range(max(0, int(steps))):
            v = base_v + i * sh
            start = max(wa, wb - (i + 1) * sd + 1)
            end = max(wa, wb - i * sd)
            if start <= end:
                self.fill((ua, v, start), (ub, v, end), block)
