class _RegionalLib:
    def guanyin_dou(self, u1, w1, u2, w2, base_v, height, extra, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        if height <= 0:
            raise ValueError("guanyin_dou height 必须 >0")
        span = ub - ua
        for u in range(ua, ub + 1):
            t = 0.5 if span == 0 else (u - ua) / span
            lift = self.jround(max(0, extra) * (1 - (2 * t - 1) ** 2))
            self.fill((u, base_v, wa), (u, base_v + height - 1 + lift, wb), block)

    def river_steps(self, cu, cw, water_v, width, steps, axis, block, water_block=None):
        if width <= 0 or steps <= 0:
            raise ValueError("river_steps width/steps 必须 >0")
        along, half = self.axis_u(axis), width // 2
        for i in range(int(steps)):
            v = water_v + steps - 1 - i
            for d in range(-half, half + 1):
                u, w = (cu + i, cw + d) if along else (cu + d, cw + i)
                self.fill((u, water_v, w), (u, v, w), block)
        if water_block:
            for d in range(-half, half + 1):
                u, w = (cu + steps, cw + d) if along else (cu + d, cw + steps)
                self.put(u, water_v, w, water_block)

    def meiren_kao(self, u1, w1, u2, w2, seat_v, back_side, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        self.fill((ua, seat_v, wa), (ub, seat_v, wb), block)
        side = str(back_side or "back").lower()
        du, dw = self.face({"n": "north", "s": "south", "e": "east", "w": "west"}.get(side, side))
        # Backrest lies on the edge opposite its outward normal.
        if dw:
            fixed = wa if dw > 0 else wb
            a1, a2 = ua, ub
        else:
            fixed = ua if du > 0 else ub
            a1, a2 = wa, wb
        length = a2 - a1
        for a in range(a1, a2 + 1):
            t = 0.5 if length == 0 else (a - a1) / length
            h = 2 + self.jround(2 * (1 - (2 * t - 1) ** 2))
            for k in range(1, h + 1):
                self.put(a if dw else fixed, seat_v + k, fixed if dw else a, block)

    def sky_well(self, u1, w1, u2, w2, floor_v, depth, wall_block, bottom_block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        if depth <= 0:
            raise ValueError("sky_well depth 必须 >0")
        for u in range(ua, ub + 1):
            for w in range(wa, wb + 1):
                if u in (ua, ub) or w in (wa, wb):
                    self.fill((u, floor_v - depth, w), (u, floor_v - 1, w), wall_block)
                else:
                    self.put(u, floor_v - depth, w, bottom_block)

    def brick_gatehouse(self, cu, cv, cw, axis, width, height, frame_block,
                        carving_block=None, cap_block="deepslate_tiles"):
        if width <= 0 or height <= 0:
            raise ValueError("brick_gatehouse width/height 必须 >0")
        along, half = self.axis_u(axis), width // 2
        for d in range(-half, half + 1):
            u, w = (cu + d, cw) if along else (cu, cw + d)
            for k in range(int(height)):
                self.put(u, cv + k, w, frame_block if d in (-half, half) else "air")
            self.put(u, cv + height, w, frame_block)
        for d in range(-half - 1, half + 2):
            u, w = (cu + d, cw) if along else (cu, cw + d)
            self.put(u, cv + height + 1, w, self.block(carving_block, self.block(frame_block)))
        for d in range(-half - 2, half + 3):
            u, w = (cu + d, cw) if along else (cu, cw + d)
            self.put(u, cv + height + 2, w, cap_block)

    def swallowtail_ridge(self, u1, w1, u2, w2, ridge_v, lift, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        span = ub - ua
        for u in range(ua, ub + 1):
            t = 0.5 if span == 0 else abs((u - ua) / span - 0.5) * 2
            f = 0 if t <= 0.6 else (t - 0.6) / 0.4
            up = self.jround(max(0, lift) * f * f)
            self.fill((u, ridge_v + up, wa), (u, ridge_v + up, wb), block)
            if f >= 0.99 and lift > 0:
                self.fill((u, ridge_v + up + 1, wa), (u, ridge_v + up + 1, wb), block)

    def huoer_wall(self, u1, w1, u2, w2, base_v, height, ear_lift, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        ear_width = max(1, (ub - ua) // 5)
        for u in range(ua, ub + 1):
            d = min(u - ua, ub - u)
            lift = self.jround(max(0, ear_lift) * math.sin((d + 1) / ear_width * math.pi / 2)) if d < ear_width else 0
            self.fill((u, base_v, wa), (u, base_v + height - 1 + lift, wb), block)

    def chuandou_frame(self, u1, w1, u2, w2, ground_v, eave_v, bays,
                       post_block, tie_beam_block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        if bays <= 0 or eave_v <= ground_v:
            raise ValueError("chuandou_frame bays>0 且 eave_v>ground_v")
        for i in range(int(bays) + 1):
            u = ua + self.jround((ub - ua) * i / bays)
            self.fill((u, ground_v, wa), (u, eave_v, wb), post_block)
        for v in (ground_v + (eave_v - ground_v) // 2, eave_v - 1):
            if v > ground_v:
                self.fill((ua, v, wa), (ub, v, wb), tie_beam_block)

    def stilt_house(self, u1, w1, u2, w2, ground_v, lift_height,
                    post_block, deck_block, wall_block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        if lift_height <= 0:
            raise ValueError("stilt_house lift_height 必须 >0")
        deck_v = ground_v + lift_height
        mu, mw = (ua + ub) // 2, (wa + wb) // 2
        for u, w in ((ua, wa), (ua, wb), (ub, wa), (ub, wb),
                     (mu, wa), (mu, wb), (ua, mw), (ub, mw)):
            self.fill((u, ground_v, w), (u, deck_v - 1, w), post_block)
        self.fill((ua - 1, deck_v, wa - 1), (ub + 1, deck_v, wb + 1), deck_block)
        for u in range(ua, ub + 1):
            for w in range(wa, wb + 1):
                if u in (ua, ub) or w in (wa, wb):
                    self.fill((u, deck_v + 1, w), (u, deck_v + 3, w), wall_block)

    def yaodong(self, u1, w1, u2, w2, ground_v, facade_height, arch_radius,
                soil_block, frame_block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        if facade_height <= 0 or arch_radius <= 0:
            raise ValueError("yaodong facade_height/arch_radius 必须 >0")
        cu = (ua + ub) // 2
        radius = min(arch_radius, max(1, (ub - ua) // 3))
        arch_top = ground_v + radius
        for u in range(ua, ub + 1):
            for w in range(wa, wb + 1):
                for k in range(int(facade_height)):
                    v = ground_v + k
                    if v < arch_top:
                        hole = abs(u - cu) <= radius
                        ring = abs(u - cu) == radius and v == ground_v
                    else:
                        du, dv = u - cu, v - arch_top
                        d2 = du * du + dv * dv
                        hole = d2 <= radius * radius
                        ring = hole and d2 > (radius - 1) ** 2
                    if hole:
                        self.put(u, v, w, frame_block if ring else "air")
                    else:
                        self.put(u, v, w, soil_block)
        for t in range(1, max(0, facade_height // 4) + 1):
            if ua + t <= ub - t:
                self.fill((ua + t, ground_v + facade_height + t - 1, wa),
                          (ub - t, ground_v + facade_height + t - 1, wb), soil_block)

    def tibetan_fort(self, u1, w1, u2, w2, base_v, height, taper,
                     stone_block, band_block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        band_h = max(1, int(height) // 8)
        for k in range(max(0, int(height))):
            inset = math.floor(max(0, taper) * k)
            au, bu, aw, bw = ua + inset, ub - inset, wa + inset, wb - inset
            if au > bu or aw > bw:
                break
            self.ring(au, aw, bu, bw, base_v + k, band_block if k >= height - band_h else stone_block)

    def tulou(self, cu, cw, base_v, radius, floors, floor_height, wall_thickness,
              soil_block, tile_block):
        if radius <= 0 or floors <= 0 or floor_height <= 0:
            raise ValueError("tulou radius/floors/floor_height 必须 >0")
        ro, ri = int(radius), max(2, int(radius) - int(wall_thickness))
        total_h = floors * floor_height
        for du in range(-ro, ro + 1):
            for dw in range(-ro, ro + 1):
                d2 = du * du + dw * dw
                if d2 > ro * ro:
                    continue
                if d2 > ri * ri:
                    self.fill((cu + du, base_v, cw + dw), (cu + du, base_v + total_h - 1, cw + dw), soil_block)
                    continue
                rr = self.jround(math.sqrt(d2))
                if rr >= ri - 1:
                    for f in range(1, int(floors)):
                        self.put(cu + du, base_v + f * floor_height - 1, cw + dw, "oak_planks")
                if d2 > 1:
                    self.put(cu + du, base_v, cw + dw, soil_block)
        re = ro + 2
        for du in range(-re, re + 1):
            for dw in range(-re, re + 1):
                d2 = du * du + dw * dw
                if d2 <= re * re and d2 > (ro - 1) ** 2:
                    self.put(cu + du, base_v + total_h, cw + dw, tile_block)
                    if d2 > (re - 1) ** 2:
                        self.put(cu + du, base_v + total_h + 1, cw + dw, tile_block)
