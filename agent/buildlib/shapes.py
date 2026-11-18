class _ShapeLib:
    def cylinder(self, cu, cv, cw, radius, height, block, hollow=False):
        r, inner = max(1, int(radius)), max(1, int(radius)) - 1 if hollow else -1
        for du in range(-r, r + 1):
            for dw in range(-r, r + 1):
                d = math.sqrt(du * du + dw * dw)
                if d <= r + 0.4 and d > inner + 0.2:
                    self.fill((cu + du, cv, cw + dw),
                              (cu + du, cv + max(1, int(height)) - 1, cw + dw), block)

    def sphere(self, cu, base_v, cw, radius, block, hollow=False):
        r = max(1, int(radius))
        for du in range(-r, r + 1):
            for dv in range(-r, r + 1):
                for dw in range(-r, r + 1):
                    d = math.sqrt(du * du + dv * dv + dw * dw)
                    if (r - 0.8 <= d <= r + 0.2) if hollow else (d <= r + 0.2):
                        self.put(cu + du, base_v + r + dv, cw + dw, block)

    def ellipsoid(self, cu, cv, cw, ru, rv, rw, block, hollow=False):
        ru, rv, rw = max(1, int(ru)), max(1, int(rv)), max(1, int(rw))
        for du in range(-ru, ru + 1):
            for dv in range(-rv, rv + 1):
                for dw in range(-rw, rw + 1):
                    d = (du / ru) ** 2 + (dv / rv) ** 2 + (dw / rw) ** 2
                    if d <= 1.05 and (not hollow or d >= 0.62):
                        self.put(cu + du, cv + dv, cw + dw, block)

    def dome(self, cu, base_v, cw, radius, block):
        r = max(1, int(radius))
        for du in range(-r, r + 1):
            for dw in range(-r, r + 1):
                for h in range(r + 1):
                    horiz = math.sqrt(du * du + dw * dw)
                    if horiz > math.sqrt(r * r - h * h) + 0.4:
                        continue
                    low = math.sqrt(max(0, r * r - (h + 1) * (h + 1)))
                    if h == 0 or horiz >= low - 0.3:
                        self.put(cu + du, base_v + h, cw + dw, block)

    def cone(self, cu, base_v, cw, radius, height, block, hollow=False):
        h, r0 = max(1, int(height)), max(1, int(radius))
        for i in range(h):
            r = self.jround(r0 * (1 - i / h))
            for du in range(-r, r + 1):
                for dw in range(-r, r + 1):
                    d = math.sqrt(du * du + dw * dw)
                    if d <= r + 0.4 and (not hollow or r < 2 or d > r - 1.4):
                        self.put(cu + du, base_v + i, cw + dw, block)

    def pyramid(self, cu, base_v, cw, size, block):
        s = max(1, int(size))
        for i in range((s + 1) // 2):
            width = s - i * 2
            if width < 1:
                break
            lo = -width // 2
            self.fill((cu + lo, base_v + i, cw + lo),
                      (cu + lo + width - 1, base_v + i, cw + lo + width - 1), block)

    def obelisk(self, u, base_v, w, height, block):
        h = max(2, int(height))
        for k in range(h - 2):
            shrink = k * 2 // max(1, h - 2)
            if 1 - shrink >= 0:
                self.fill((u, base_v + k, w), (u + 1 - shrink, base_v + k, w + 1 - shrink), block)
        self.pyramid(u, base_v + h - 2, w, 2, block)

    def octagon_prism(self, cu, base_v, cw, radius, height, block):
        r = max(2, int(radius))
        for du in range(-r, r + 1):
            for dw in range(-r, r + 1):
                d = max(abs(du), abs(dw)) + 0.5 * min(abs(du), abs(dw))
                if r - 1.2 < d <= r + 0.3:
                    self.fill((cu + du, base_v, cw + dw),
                              (cu + du, base_v + max(1, int(height)) - 1, cw + dw), block)

    def hexagon_prism(self, cu, base_v, cw, radius, height, block):
        r = max(2, int(radius))
        for du in range(-r, r + 1):
            for dw in range(-r, r + 1):
                au, aw = abs(du), abs(dw)
                d = au + max(0, aw - au // 2) if au > aw / 2 + 0.5 else max(au, aw)
                if r - 1 <= d <= r:
                    self.fill((cu + du, base_v, cw + dw),
                              (cu + du, base_v + max(1, int(height)) - 1, cw + dw), block)

    def polygon(self, cu, base_v, cw, radius, sides, block, height=1, hollow=True):
        r = max(1, int(radius))
        for du in range(-r - 1, r + 2):
            for dw in range(-r - 1, r + 2):
                inside = self.polygon_ring(du, dw, r, sides)
                if not hollow:
                    inside = inside or math.hypot(du, dw) < r * math.cos(math.pi / max(3, sides)) - 0.85
                if inside:
                    self.fill((cu + du, base_v, cw + dw),
                              (cu + du, base_v + max(1, int(height)) - 1, cw + dw), block)

    def prism(self, cu, base_v, cw, radius, height, sides, block, hollow=True):
        self.polygon(cu, base_v, cw, radius, sides, block, height, hollow)

    def polygon_dome(self, cu, base_v, cw, radius, sides, block):
        r = max(1, int(radius))
        for h in range(r + 1):
            rr = self.jround(math.sqrt(max(0, r * r - h * h)))
            self.polygon(cu, base_v + h, cw, max(1, rr), sides, block)

    def ellipse_wall(self, cu, base_v, cw, a, b, height, block):
        ra, rb = max(2, int(a)), max(2, int(b))
        for du in range(-ra, ra + 1):
            for dw in range(-rb, rb + 1):
                value = du * du / (ra * ra) + dw * dw / (rb * rb)
                if 0.75 <= value <= 1.05:
                    self.fill((cu + du, base_v, cw + dw),
                              (cu + du, base_v + max(1, int(height)) - 1, cw + dw), block)

    def disc(self, cu, v, cw, radius, block):
        r = max(1, int(radius))
        for du in range(-r, r + 1):
            for dw in range(-r, r + 1):
                if math.sqrt(du * du + dw * dw) <= r + 0.4:
                    self.put(cu + du, v, cw + dw, block)

    def arch(self, cu, base_v, cw, span, height, facing, block):
        s = max(3, int(span) | 1)
        r = s // 2
        along = self.along_u(facing)
        for i in range(-r, r + 1):
            for h in range(max(1, int(height))):
                if abs(i) == r:
                    self.put(cu + (i if along else 0), base_v + h, cw + (0 if along else i), block)
            for h in range(int(height), int(height) + r + 1):
                t = h - int(height)
                if abs(i) >= self.jround(r - math.sqrt(max(0, r * r - t * t))):
                    self.put(cu + (i if along else 0), base_v + h, cw + (0 if along else i), block)

    def pointed_arch(self, cu, base_v, cw, span, height, facing, block):
        s, h0 = max(3, int(span) | 1), int(height)
        r = s // 2
        along = self.along_u(facing)
        for h in range(h0):
            for i in (-r, r):
                self.put(cu + (i if along else 0), base_v + h, cw + (0 if along else i), block)
        arc_h = r + 1
        for t in range(arc_h + 1):
            half = self.jround(r * (1 - math.sqrt(t / arc_h)))
            for i in range(-half, half + 1):
                if abs(i) >= half - 1:
                    self.put(cu + (i if along else 0), base_v + h0 + t, cw + (0 if along else i), block)
        self.put(cu, base_v + h0 + arc_h + 1, cw, block)

    def arch_wall(self, u1, base_v, w1, u2, w2, spacing, height, span, block):
        along = abs(u2 - u1) >= abs(w2 - w1)
        length = abs(u2 - u1) if along else abs(w2 - w1)
        sign = 1 if (u2 if along else w2) >= (u1 if along else w1) else -1
        for start in range(0, length + 1, max(2, int(spacing))):
            cu = u1 + sign * (start + span // 2) if along else u1
            cw = w1 if along else w1 + sign * (start + span // 2)
            self.arch(cu, base_v, cw, span, height, "south" if along else "east", block)

    def buttress(self, u, base_v, w, length, height, facing, block):
        du, dw = self.face(facing)
        n = max(2, int(length))
        for i in range(n):
            top = int(height) - i * int(height) // n
            self.fill((u + du * i, base_v, w + dw * i),
                      (u + du * i, base_v + top, w + dw * i), block)

    def hip_roof(self, u1, base_v, w1, u2, w2, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        level = 0
        while ub >= ua and wb >= wa and level <= 64:
            self.ring(ua, wa, ub, wb, base_v + level, block)
            ua, ub, wa, wb = ua + 1, ub - 1, wa + 1, wb - 1
            level += 1

    def mansard_roof(self, u1, base_v, w1, u2, w2, steep, flat):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        levels = max(1, min(ub - ua, wb - wa) // 3)
        for i in range(levels):
            self.ring(ua + i, wa + i, ub - i, wb - i, base_v + i, steep)
        self.ring(ua + levels, wa + levels, ub - levels, wb - levels, base_v + levels, flat)

    def slope_slab(self, u1, base_v, w1, u2, w2, drop, block):
        along = abs(u2 - u1) >= abs(w2 - w1)
        length = abs(u2 - u1) if along else abs(w2 - w1)
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        for i in range(length + 1):
            h = self.jround(drop * (1 - i / max(1, length)))
            if along:
                u = u1 + i if u2 > u1 else u1 - i
                self.fill((u, base_v + h, wa), (u, base_v + h, wb), block)
            else:
                w = w1 + i if w2 > w1 else w1 - i
                self.fill((ua, base_v + h, w), (ub, base_v + h, w), block)

    def spiral_staircase(self, cu, base_v, cw, radius, height, block):
        r, h = max(2, int(radius)), int(height)
        steps = max(4, h * 4)
        for i in range(steps):
            angle = i * math.pi / (2 * steps / h)
            u = cu + self.jround(r * math.cos(angle))
            w = cw + self.jround(r * math.sin(angle))
            v = base_v + self.jround(i * h / steps)
            self.put(u, v, w, block)
        self.fill((cu, base_v, cw), (cu, base_v + h - 1, cw), block)

    def straight_stairs(self, u, base_v, w, length, facing, block):
        du, dw = self.face(facing)
        stair = self.stair(block)
        for i in range(max(1, int(length))):
            self.put(u + du * i, base_v + i, w + dw * i, stair,
                     self.stair_states(("back" if (du, dw) == (0, 1) else
                                        "front" if (du, dw) == (0, -1) else
                                        "left" if (du, dw) == (1, 0) else "right")))

    def line3d(self, u1, v1, w1, u2, v2, w2, block):
        self.line((u1, v1, w1), (u2, v2, w2), block)

    def catenary(self, u1, v1, w1, u2, v2, w2, sag, block):
        n = max(abs(u2 - u1), abs(w2 - w1), 1)
        for i in range(n + 1):
            t = i / n
            u = self.jround(u1 + (u2 - u1) * t)
            w = self.jround(w1 + (w2 - w1) * t)
            v = self.jround(v1 + (v2 - v1) * t - sag * 4 * t * (1 - t))
            self.put(u, v, w, block)

    def turret(self, cu, base_v, cw, radius, body_height, body, roof):
        self.cylinder(cu, base_v, cw, radius, body_height, body, True)
        self.cone(cu, base_v + body_height, cw, radius + 1, radius + 2, roof, False)

    def box_shell(self, u1, v1, w1, u2, v2, w2, block, floor=True, ceiling=True):
        ua, ub = self.span(u1, u2)
        va, vb = self.span(v1, v2)
        wa, wb = self.span(w1, w2)
        self.api.walls((ua, va, wa), (ub, vb, wb), self.block(block))
        if floor:
            self.fill((ua, va, wa), (ub, va, wb), block)
        if ceiling:
            self.fill((ua, vb, wa), (ub, vb, wb), block)

    def arc_wall(self, cu, base_v, cw, radius, height, start_deg, end_deg, block):
        r = max(2, int(radius))
        a0, a1 = min(start_deg, end_deg), max(start_deg, end_deg)
        for deg in range(math.ceil(a0), math.floor(a1) + 1):
            rad = math.radians(deg)
            u = cu + self.jround(r * math.sin(rad))
            w = cw - self.jround(r * math.cos(rad))
            self.fill((u, base_v, w), (u, base_v + max(1, int(height)) - 1, w), block)

    def battlement(self, u1, v, w1, u2, w2, block):
        along = abs(u2 - u1) >= abs(w2 - w1)
        length = abs(u2 - u1) if along else abs(w2 - w1)
        su = (u2 > u1) - (u2 < u1)
        sw = (w2 > w1) - (w2 < w1)
        for i in range(length + 1):
            if i % 3 != 2:
                self.fill((u1 + su * i, v, w1 + sw * i),
                          (u1 + su * i, v + 1, w1 + sw * i), block)

    def colonnade(self, u1, base_v, w1, u2, w2, spacing, height, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        sp = max(2, int(spacing))
        for u in list(range(ua, ub + 1, sp)) + ([] if (ub - ua) % sp == 0 else [ub]):
            for w in (wa, wb):
                self.fill((u, base_v, w), (u, base_v + max(1, int(height)) - 1, w), block)
        for w in list(range(wa + sp, wb, sp)):
            for u in (ua, ub):
                self.fill((u, base_v, w), (u, base_v + max(1, int(height)) - 1, w), block)

    def terrace(self, cu, base_v, cw, size, layers, block):
        s = max(3, int(size))
        for i in range(max(1, int(layers))):
            width = s - i * 2
            if width < 1:
                break
            r = width // 2
            self.fill((cu - r, base_v + i, cw - r), (cu + r, base_v + i, cw + r), "dirt")
            self.ring(cu - r, cw - r, cu + r, cw + r, base_v + i, block)

    def torus(self, cu, cv, cw, major_radius, tube_radius, block, axis="v"):
        r, t = max(2, int(major_radius)), max(1, int(tube_radius))
        for a in range(-r - t, r + t + 1):
            for b in range(-r - t, r + t + 1):
                for h in range(-t, t + 1):
                    if (math.sqrt(a * a + b * b) - r) ** 2 + h * h <= t * t + 0.2:
                        pos = (cu + a, cv + h, cw + b) if axis == "v" else ((cu + a, cv + b, cw + h) if axis == "w" else (cu + h, cv + a, cw + b))
                        self.put(*pos, block)

    def tapered_cylinder(self, cu, base_v, cw, bottom_radius, top_radius, height, block, hollow=False):
        h = max(1, int(height))
        for k in range(h):
            r = self.jround(bottom_radius + (top_radius - bottom_radius) * k / max(1, h - 1))
            self.cylinder(cu, base_v + k, cw, max(1, r), 1, block, hollow)

    def onion_dome(self, cu, base_v, cw, radius, height, block):
        r, h = max(2, int(radius)), max(2, int(height))
        for k in range(h):
            t = k / (h - 1)
            rr = r * (0.72 + 0.38 * math.sin(math.pi * t)) * (1 - t ** 3)
            self.cylinder(cu, base_v + k, cw, max(1, self.jround(rr)), 1, block, True)

    def barrel_vault(self, u1, w1, u2, w2, base_v, height, block, axis="u", thickness=1):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        if axis == "u":
            center, half = (wa + wb) / 2, max(1, (wb - wa) / 2)
            for w in range(wa, wb + 1):
                lift = self.jround(height * math.sqrt(max(0, 1 - ((w - center) / half) ** 2)))
                self.fill((ua, base_v + lift, w), (ub, base_v + lift + thickness - 1, w), block)
        else:
            center, half = (ua + ub) / 2, max(1, (ub - ua) / 2)
            for u in range(ua, ub + 1):
                lift = self.jround(height * math.sqrt(max(0, 1 - ((u - center) / half) ** 2)))
                self.fill((u, base_v + lift, wa), (u, base_v + lift + thickness - 1, wb), block)

    def catenary_bridge(self, u1, v1, w1, u2, v2, w2, width, sag, deck, cable=None):
        n = max(abs(u2 - u1), abs(w2 - w1), 1)
        du, dw = u2 - u1, w2 - w1
        length = math.hypot(du, dw) or 1
        pu, pw = -dw / length, du / length
        for i in range(n + 1):
            t = i / n
            cu = self.jround(u1 + du * t)
            cw = self.jround(w1 + dw * t)
            v = self.jround(v1 + (v2 - v1) * t)
            for k in range(-width // 2, width // 2 + 1):
                self.put(cu + self.jround(pu * k), v, cw + self.jround(pw * k), deck)
            if cable:
                drop = self.jround(sag * 4 * t * (1 - t))
                for side in (-1, 1):
                    k = side * (width // 2 + 1)
                    self.put(cu + self.jround(pu * k), v + 2 - drop, cw + self.jround(pw * k), cable)

    def spiral_ramp(self, cu, base_v, cw, inner_radius, outer_radius, height, turns, block, width=2):
        steps = max(12, self.jround(abs(turns) * 72))
        for i in range(steps + 1):
            t = i / steps
            angle = turns * math.tau * t
            v = base_v + self.jround(height * t)
            for r in range(max(0, inner_radius), max(inner_radius + 1, outer_radius + 1)):
                self.put(cu + self.jround(r * math.cos(angle)), v,
                         cw + self.jround(r * math.sin(angle)), block)

    def gable(self, u1, base_v, w1, u2, w2, height, block, axis="u", hollow=False):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        for k in range(max(1, int(height))):
            if axis == "u":
                if wa + k > wb - k:
                    break
                if hollow:
                    self.fill((ua, base_v + k, wa + k), (ub, base_v + k, wa + k), block)
                    self.fill((ua, base_v + k, wb - k), (ub, base_v + k, wb - k), block)
                else:
                    self.fill((ua, base_v + k, wa + k), (ub, base_v + k, wb - k), block)
            else:
                if ua + k > ub - k:
                    break
                if hollow:
                    self.fill((ua + k, base_v + k, wa), (ua + k, base_v + k, wb), block)
                    self.fill((ub - k, base_v + k, wa), (ub - k, base_v + k, wb), block)
                else:
                    self.fill((ua + k, base_v + k, wa), (ub - k, base_v + k, wb), block)
