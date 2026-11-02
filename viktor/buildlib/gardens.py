class _GardenLib:
    def classical_column(self, cu, cw, base_v, height, size, block, crown=None):
        if height < 3 or size < 1:
            raise ValueError("classical_column height>=3, size>=1")
        lo_u, hi_u = cu - (size - 1) // 2, cu - (size - 1) // 2 + size - 1
        lo_w = cw - (size - 1) // 2
        hi_w = lo_w + size - 1
        self.fill((lo_u - 1, base_v, lo_w - 1), (hi_u + 1, base_v, hi_w + 1), block)
        shaft_lo, shaft_hi = base_v + 1, base_v + height - 3
        for v in range(shaft_lo, shaft_hi + 1):
            t = (v - shaft_lo) / max(1, shaft_hi - shaft_lo)
            shrink = math.floor((t - 0.66) * 3) if t > 0.66 and size >= 3 else 0
            if lo_u + shrink <= hi_u - shrink and lo_w + shrink <= hi_w - shrink:
                self.fill((lo_u + shrink, v, lo_w + shrink), (hi_u - shrink, v, hi_w - shrink), block)
        for k in range(2):
            grow = k + 1
            self.fill((lo_u - grow, base_v + height - 2 + k, lo_w - grow),
                      (hi_u + grow, base_v + height - 2 + k, hi_w + grow), self.block(crown, self.block(block)))

    def baroque_portico(self, u1, w1, u2, w2, base_v, columns, height, facing,
                        stone, trim=None):
        if columns < 2 or height < 4:
            raise ValueError("baroque_portico columns>=2, height>=4")
        along = self.along_u(facing)
        a, b = self.span(u1 if along else w1, u2 if along else w2)
        fixed = w1 if along else u1
        span = b - a
        if span < columns * 2:
            raise ValueError("baroque_portico 面宽至少为 columns*2；当前 %d，需要 %d" % (span, columns * 2))
        du, dw = self.face(facing)
        step = max(2, span // (columns - 1))
        positions = [min(b, a + i * step) for i in range(columns)]
        positions[-1] = b
        for a0 in positions:
            for v in range(base_v + 1, base_v + height + 1):
                for d in range(2):
                    self.put(a0 if along else fixed + du * d, v,
                             fixed + dw * d if along else a0,
                             self.block(trim, self.block(stone)) if v >= base_v + height - 1 else stone)
        for v in (base_v + height + 1, base_v + height + 2):
            for a0 in range(a - 1, b + 2):
                for d in range(3):
                    self.put(a0 if along else fixed + du * d, v,
                             fixed + dw * d if along else a0, self.block(trim, self.block(stone)))
        ped_base, ped_h = base_v + height + 3, max(2, height // 3)
        for k in range(ped_h):
            inset = self.jround(k * span / 2 / ped_h)
            for a0 in range(a + inset, b - inset + 1):
                for d in range(3):
                    self.put(a0 if along else fixed + du * d, ped_base + k,
                             fixed + dw * d if along else a0, stone)

    def volute(self, cu, cv, cw, radius, side, block):
        if radius < 1:
            raise ValueError("volute radius>=1")
        for scale in (1.0, 0.55):
            last = None
            for i in range(19):
                theta = math.pi * 1.5 * i / 18
                r = radius * scale * (0.25 + 0.75 * (1 - i / 18))
                pos = (cu + self.jround(math.cos(theta) * r) * side,
                       cv + self.jround(math.sin(theta) * r))
                if pos != last:
                    self.put(pos[0], pos[1], cw, block)
                    last = pos
        self.put(cu, cv, cw, block)

    def balustrade(self, u1, w1, u2, w2, base_v, spacing, block, rail=None):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        sp = max(2, int(spacing))
        self.ring(ua, wa, ub, wb, base_v, block)
        self.ring(ua, wa, ub, wb, base_v + 4, self.block(rail, self.block(block)))
        for u in range(ua, ub + 1):
            for w in range(wa, wb + 1):
                if u not in (ua, ub) and w not in (wa, wb):
                    continue
                corner = u in (ua, ub) and w in (wa, wb)
                along = w - wa if u in (ua, ub) else u - ua
                if corner or along % sp == 0:
                    self.fill((u, base_v + 1, w), (u, base_v + 3, w), block)

    def arched_window(self, cu, cw, sill_v, width, height, facing, frame, glass):
        if width < 3 or height < 2:
            raise ValueError("arched_window width>=3, height>=2")
        along, half = self.along_u(facing), width // 2
        du, dw = self.face(facing)
        for k in range(int(height)):
            for t in range(-half, half + 1):
                self.put(cu + t if along else cu, sill_v + k, cw if along else cw + t,
                         frame if abs(t) == half else glass)
        top = sill_v + height + half
        for v in range(sill_v + height, top + 1):
            dv = v - (sill_v + height)
            rr = half + 0.5
            width_here = math.floor(math.sqrt(max(0, rr * rr - dv * dv)) + 0.5)
            for t in range(-width_here, width_here + 1):
                self.put(cu + t if along else cu, v, cw if along else cw + t,
                         frame if abs(t) == width_here else glass)
        self.put(cu + du if not along else cu, top, cw if along else cw + dw, frame)
        for t in range(-half - 1, half + 2):
            self.put(cu + t if along else cu, sill_v - 1, cw if along else cw + t, frame)

    def pilaster_strip(self, u1, w1, u2, w2, base_v, top_v, spacing, facing,
                       block, capital=None):
        if top_v < base_v:
            raise ValueError("pilaster_strip top_v>=base_v")
        along = self.along_u(facing)
        a1, a2 = self.span(u1 if along else w1, u2 if along else w2)
        fixed = w1 if along else u1
        du, dw = self.face(facing)
        positions = list(range(a1, a2 + 1, max(2, int(spacing))))
        if positions[-1] != a2:
            positions.append(a2)
        for a in positions:
            for v in range(base_v, top_v + 1):
                for d in (0, 1):
                    self.put(a if along else fixed + du * d, v,
                             fixed + dw * d if along else a,
                             self.block(capital, self.block(block)) if v == top_v else block)

    def cornice(self, u1, w1, u2, w2, v, step, layers, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        if layers < 1:
            raise ValueError("cornice layers>=1")
        for k in range(int(layers)):
            grow = k * max(1, int(step))
            self.ring(ua - grow, wa - grow, ub + grow, wb + grow, v + k, block)

    def water_basin(self, u1, w1, u2, w2, floor_v, wall_height, wall,
                    floor=None, water="water"):
        if wall_height < 2:
            raise ValueError("water_basin wall_height>=2")
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        self.fill((ua, floor_v, wa), (ub, floor_v, wb), self.block(floor, self.block(wall)))
        top = floor_v + wall_height
        for v in range(floor_v + 1, top + 1):
            self.ring(ua, wa, ub, wb, v, wall)
        if ub - ua >= 2 and wb - wa >= 2:
            self.fill((ua + 1, top - 1, wa + 1), (ub - 1, top - 1, wb - 1), water)

    def round_basin(self, cu, cw, floor_v, radius, wall_height, wall, water="water"):
        if radius < 2 or wall_height < 2:
            raise ValueError("round_basin radius>=2, wall_height>=2")
        top, ri = floor_v + wall_height, max(0, radius - 1)
        for du in range(-radius, radius + 1):
            for dw in range(-radius, radius + 1):
                d2 = du * du + dw * dw
                if d2 > radius * radius:
                    continue
                self.put(cu + du, floor_v, cw + dw, wall)
                if d2 > ri * ri:
                    self.fill((cu + du, floor_v + 1, cw + dw), (cu + du, top, cw + dw), wall)
                else:
                    self.put(cu + du, top - 1, cw + dw, water)

    def cascade(self, cu, cw, top_v, width, steps, drop, out_step, block, facing="front"):
        if steps < 1 or drop < 1:
            raise ValueError("cascade steps/drop>=1")
        du, dw = self.face(facing)
        pu, pw = self.perpendicular(facing)
        half = max(0, width // 2)
        v = top_v
        for s in range(int(steps)):
            offset = (s + 1) * max(1, int(out_step))
            for t in range(-half, half + 1):
                self.put(cu + du * offset + pu * t, v, cw + dw * offset + pw * t, "water")
            for k in range(1, int(drop)):
                self.put(cu + du * offset, v - k, cw + dw * offset, "water")
                self.put(cu + du * (offset + 1), v - k, cw + dw * (offset + 1), block)
            v -= drop

    def zigzag_bridge(self, u1, w1, u2, w2, deck_v, bents, width, deck, rail=None):
        if bents < 1:
            raise ValueError("zigzag_bridge bents>=1")
        half = max(1, int(width)) // 2
        du, dw = (u2 - u1) / bents, (w2 - w1) / bents
        amp = max(2, min(abs(du), abs(dw)))
        pu, pw = (0, 1) if abs(du) > abs(dw) else (1, 0)
        points = []
        for i in range(bents + 1):
            off = amp if i % 2 and i != bents else 0
            points.append((self.jround(u1 + du * i + pu * off),
                           self.jround(w1 + dw * i + pw * off)))
        for i in range(bents):
            au, aw = points[i]
            bu, bw = points[i + 1]
            n = max(abs(bu - au), abs(bw - aw))
            for s in range(n + 1):
                t = s / n if n else 0
                cu, cw = self.jround(au + (bu - au) * t), self.jround(aw + (bw - aw) * t)
                for ou in range(-half, half + 1):
                    for ow in range(-half, half + 1):
                        self.put(cu + ou, deck_v, cw + ow, deck)
                        if rail and abs(ou) == half and abs(ow) == half:
                            self.put(cu + ou, deck_v + 1, cw + ow, rail)

    def stone_boat(self, cu, cw, deck_v, length, width, hull_height, cabin_height,
                   hull, cabin=None, roof=None):
        if length < 5 or width < 3:
            raise ValueError("stone_boat length>=5, width>=3")
        hl, hw = length // 2, width // 2
        for v in range(deck_v - hull_height, deck_v + 1):
            for d in range(-hl, hl + 1):
                taper = 1 if abs(d) >= hl - 1 else 0
                self.fill((cu - hw + taper, v, cw + d), (cu + hw - taper, v, cw + d), hull)
        cl, cw2 = max(2, int(length * 0.3)), max(1, hw - 2)
        for k in range(1, cabin_height + 1):
            for d in range(-cl, cl + 1):
                for q in range(-cw2, cw2 + 1):
                    self.put(cu + q, deck_v + k, cw + d,
                             self.block(cabin, self.block(hull)) if abs(q) == cw2 or abs(d) == cl else "air")
        for k in range(2):
            grow = 1 - k
            self.fill((cu - cw2 - grow, deck_v + cabin_height + 1 + k, cw - cl - grow),
                      (cu + cw2 + grow, deck_v + cabin_height + 1 + k, cw + cl + grow),
                      self.block(roof, self.block(hull)))

    def rockery(self, cu, cw, base_v, ru, rv, rw, holes, shell, core=None):
        if ru < 2 or rv < 3 or rw < 2:
            raise ValueError("rockery ru/rw>=2, rv>=3")
        hd = max(2, int(holes))
        for v in range(int(rv) + 1):
            scale = 1 - 0.75 * (v / rv) ** 1.4
            for u in range(-ru, ru + 1):
                for w in range(-rw, rw + 1):
                    nu = u / ru / max(0.2, scale)
                    nw = w / rw / max(0.2, scale)
                    d2 = nu * nu + nw * nw
                    if d2 > 1:
                        continue
                    tunnel = (u + v) % hd == 0 or (w + 2 * v) % hd == 0
                    if tunnel and d2 < 0.35:
                        continue
                    self.put(cu + u, base_v + v, cw + w,
                             shell if d2 > 0.6 else self.block(core, self.block(shell)))

    def covered_walkway(self, u1, w1, u2, w2, base_v, width, height,
                        column_step, pillar, roof, bench=None):
        if height < 2:
            raise ValueError("covered_walkway height>=2")
        half, step = max(1, width // 2), max(2, int(column_step))
        n = max(abs(u2 - u1), abs(w2 - w1))
        if not n:
            raise ValueError("covered_walkway 两端不能重合")
        along = abs(u2 - u1) >= abs(w2 - w1)
        for s in range(n + 1):
            t = s / n
            cu, cw = self.jround(u1 + (u2 - u1) * t), self.jround(w1 + (w2 - w1) * t)
            for k in range(-half - 1, half + 2):
                u, w = (cu, cw + k) if along else (cu + k, cw)
                self.put(u, base_v + height + 1, w, roof)
                if abs(k) <= half:
                    self.put(u, base_v, w, roof)
            if s % step == 0 or s == n:
                for side in (-1, 1):
                    u, w = (cu, cw + side * half) if along else (cu + side * half, cw)
                    self.fill((u, base_v + 1, w), (u, base_v + height, w), pillar)
                    if bench:
                        self.put(u, base_v + 1, w, bench)

    def flower_bed(self, u1, w1, u2, w2, base_v, rim_height, wall,
                   soil="dirt", flower="poppy", stride=2):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        for u in range(ua + 1, ub):
            for w in range(wa + 1, wb):
                self.put(u, base_v, w, soil)
                if flower and (u + w) % max(1, int(stride)) == 0:
                    self.put(u, base_v + 1, w, flower)
        for k in range(max(1, int(rim_height)) + 1):
            self.ring(ua, wa, ub, wb, base_v + k, wall)
