class _StructureLib:
    def groin_vault(self, u1, w1, u2, w2, base_v, height, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        if height <= 0:
            raise ValueError("groin_vault height 必须 >0")
        hu, hw = max(1, (ub - ua) / 2), max(1, (wb - wa) / 2)
        uc, wc = (ua + ub) / 2, (wa + wb) / 2
        for u in range(ua, ub + 1):
            hu_height = height * math.sqrt(max(0, 1 - ((u - uc) / hu) ** 2))
            for w in range(wa, wb + 1):
                hw_height = height * math.sqrt(max(0, 1 - ((w - wc) / hw) ** 2))
                self.put(u, base_v + self.jround(min(hu_height, hw_height)), w, block)

    def rib_vault(self, u1, w1, u2, w2, base_v, height, rib_lift, rib_block, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        hu, hw = max(1, (ub - ua) / 2), max(1, (wb - wa) / 2)
        uc, wc = (ua + ub) / 2, (wa + wb) / 2
        for u in range(ua, ub + 1):
            tu = (u - uc) / hu
            hx = height * math.sqrt(max(0, 1 - tu * tu))
            for w in range(wa, wb + 1):
                tw = (w - wc) / hw
                hz = height * math.sqrt(max(0, 1 - tw * tw))
                v = base_v + self.jround(min(hx, hz))
                self.put(u, v, w, block)
                if abs(abs(tu) - abs(tw)) < 0.16:
                    for k in range(1, max(1, int(rib_lift)) + 1):
                        self.put(u, v + k, w, self.block(rib_block, self.block(block)))

    def fan_vault(self, cu, cv, cw, radius, drop, ribs, rings, block):
        if radius <= 0:
            raise ValueError("fan_vault radius 必须 >0")
        rf, rg = max(4, int(ribs)), max(1, int(rings))
        for k in range(rf):
            angle = math.tau * k / rf
            for r in range(1, int(radius) + 1):
                t = r / radius
                self.put(cu + self.jround(r * math.cos(angle)), cv - self.jround(drop * t * t),
                         cw + self.jround(r * math.sin(angle)), block)
        for q in range(1, rg + 1):
            r = max(1, self.jround(radius * q / rg))
            v = cv - self.jround(drop * (r / radius) ** 2)
            for du in range(-r, r + 1):
                for dw in range(-r, r + 1):
                    if self.polygon_ring(du, dw, r, rf):
                        self.put(cu + du, v, cw + dw, block)

    def viaduct(self, u1, w1, u2, w2, base_v, ground_v, spans, arch_height,
                thickness, deck_block, pier_block=None):
        if spans <= 0:
            raise ValueError("viaduct spans 必须 >0")
        along = abs(u2 - u1) >= abs(w2 - w1)
        a1, a2 = self.span(u1 if along else w1, u2 if along else w2)
        fixed = w1 if along else u1
        th = max(1, int(thickness))
        span_len = max(1, (a2 - a1 + 1) // int(spans))
        for s in range(int(spans)):
            start = a1 + s * span_len
            end = a2 if s == spans - 1 else start + span_len - 1
            mid, half = (start + end) // 2, max(1, (end - start) / 2)
            for a in range(start, end + 1):
                lift = self.jround(arch_height * math.sqrt(max(0, 1 - ((a - mid) / half) ** 2)))
                for d in range(th):
                    self.put(a if along else fixed + d, base_v + lift,
                             fixed + d if along else a, deck_block)
            pier = start
            for v in range(int(ground_v), int(base_v)):
                for d in range(th):
                    self.put(pier if along else fixed + d, v,
                             fixed + d if along else pier, self.block(pier_block, self.block(deck_block)))
        for v in range(int(ground_v), int(base_v)):
            for d in range(th):
                self.put(a2 if along else fixed + d, v,
                         fixed + d if along else a2, self.block(pier_block, self.block(deck_block)))

    def space_frame(self, u1, w1, u2, w2, v, depth, grid, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        g, d = max(2, int(grid)), max(1, int(depth))
        for k in range(2):
            vv = v + (d if k else 0)
            for u in range(ua, ub + 1):
                for w in range(wa, wb + 1):
                    if (u - ua) % g == 0 or u == ub or (w - wa) % g == 0 or w == wb:
                        self.put(u, vv, w, block)
        for u in range(ua, ub + 1, g):
            for w in range(wa, wb + 1, g):
                flip = ((u - ua) // g + (w - wa) // g) % 2 == 0
                tu = min(ub, u + g if flip else u - g)
                tw = min(wb, w - g if flip else w + g)
                if tu < ua:
                    tu = min(ub, u + g)
                if tw < wa:
                    tw = min(wb, w + g)
                self.put(tu, v, tw, block)
                self.put(tu, v + d, tw, block)
                self.put(u, v + d // 2, w, block)

    def hyperboloid(self, cu, cw, base_v, bottom_radius, waist_radius, top_radius,
                    height, sides, block):
        if height <= 0:
            raise ValueError("hyperboloid height 必须 >0")
        for i in range(int(height) + 1):
            t = i / height
            end = bottom_radius if t < 0.5 else top_radius
            r = max(1, self.jround(waist_radius + (end - waist_radius) * abs(2 * t - 1) ** 2.2))
            for du in range(-r - 1, r + 2):
                for dw in range(-r - 1, r + 2):
                    if self.polygon_ring(du, dw, r, sides):
                        self.put(cu + du, base_v + i, cw + dw, block)

    def hyperbolic_paraboloid(self, u1, w1, u2, w2, base_v, height, thickness, block):
        ua, ub = self.span(u1, u2)
        wa, wb = self.span(w1, w2)
        su, sw = max(1, ub - ua), max(1, wb - wa)
        for u in range(ua, ub + 1):
            a = (u - ua) * 2 / su - 1
            for w in range(wa, wb + 1):
                b = (w - wa) * 2 / sw - 1
                v = base_v + self.jround(height * (a * a - b * b) / 2)
                for k in range(max(1, int(thickness))):
                    self.put(u, v + k, w, block)

    def helicoid(self, cu, cw, base_v, radius, turns, height, thickness, block):
        if radius <= 0 or turns <= 0:
            raise ValueError("helicoid radius/turns 必须 >0")
        steps = max(8, self.jround(turns * 72))
        for s in range(steps + 1):
            angle = math.tau * turns * s / steps
            v = base_v + self.jround(height * s / steps)
            for r in range(int(radius) + 1):
                u = cu + self.jround(r * math.cos(angle))
                w = cw + self.jround(r * math.sin(angle))
                for k in range(max(1, int(thickness))):
                    self.put(u, v + k, w, block)

    def superellipsoid(self, cu, cv, cw, ru, rv, rw, exponent, hollow, block):
        if min(ru, rv, rw) <= 0:
            raise ValueError("superellipsoid 半径必须 >0")
        e = max(1.0, float(exponent))
        for u in range(cu - ru, cu + ru + 1):
            au = (abs(u - cu) / ru) ** e
            if au > 1:
                continue
            for v in range(cv - rv, cv + rv + 1):
                av = (abs(v - cv) / rv) ** e
                if au + av > 1:
                    continue
                for w in range(cw - rw, cw + rw + 1):
                    value = au + av + (abs(w - cw) / rw) ** e
                    if value <= 1 and (not hollow or value >= 0.62):
                        self.put(u, v, w, block)

    def twisted_tower(self, cu, cw, base_v, bottom_radius, top_radius, height,
                      sides, twist_deg, block):
        if height <= 0:
            raise ValueError("twisted_tower height 必须 >0")
        for i in range(int(height) + 1):
            t = i / height
            r = max(1, self.jround(bottom_radius + (top_radius - bottom_radius) * t))
            rotation = math.radians(twist_deg) * t
            for k in range(max(3, int(sides))):
                angle = rotation + math.tau * k / max(3, int(sides))
                self.put(cu + self.jround(r * math.cos(angle)), base_v + i,
                         cw + self.jround(r * math.sin(angle)), block)

    def ribbed_shell(self, cu, cv, cw, ru, rv, rw, ribs, rings, rib_lift, rib_block, panel_block=None):
        if min(ru, rv, rw) <= 0:
            raise ValueError("ribbed_shell 半径必须 >0")
        rf, rg, lift = max(3, int(ribs)), max(0, int(rings)), max(1, int(rib_lift))
        for v in range(cv - rv, cv + rv + 1):
            tv = (v - cv) / rv
            ring_sq = 1 - tv * tv
            if ring_sq <= 0:
                continue
            rxz = math.sqrt(ring_sq)
            for u in range(cu - ru, cu + ru + 1):
                tu = (u - cu) / ru
                if tu * tu > ring_sq:
                    continue
                for w in range(cw - rw, cw + rw + 1):
                    tw = (w - cw) / rw
                    value = tu * tu + tv * tv + tw * tw
                    if value > 1 or value < 0.72:
                        continue
                    rho = math.hypot(u - cu, w - cw)
                    on_rib = False
                    if rho > 0.5:
                        angle = math.atan2(w - cw, u - cu)
                        sector = math.tau / rf
                        frac = (angle / sector) % 1
                        tolerance = max(0.06, 0.6 / max(1, rho))
                        on_rib = min(frac, 1 - frac) * sector < tolerance
                    on_ring = False
                    if rg:
                        lat = math.asin(max(-1, min(1, tv)))
                        g = (lat + math.pi / 2) / (math.pi / (rg + 1))
                        on_ring = abs(g - self.jround(g)) < max(0.1, 0.6 / max(1, rxz * rv))
                    if on_rib or on_ring:
                        ou = u + self.jround(lift * (u - cu) / ru)
                        ov = v + self.jround(lift * (v - cv) / rv)
                        ow = w + self.jround(lift * (w - cw) / rw)
                        self.put(ou, ov, ow, rib_block)
                    if panel_block:
                        self.put(u, v, w, panel_block)

    def curtain_wall(self, u1, base_v, w1, u2, top_v, w2, mullion_every,
                     floor_every, mullion_block, glass_block):
        along = abs(u2 - u1) >= abs(w2 - w1)
        a1, a2 = self.span(u1 if along else w1, u2 if along else w2)
        fixed = w1 if along else u1
        low, high = self.span(base_v, top_v)
        mu, fh = max(1, int(mullion_every)), max(1, int(floor_every))
        for a in range(a1, a2 + 1):
            mullion = (a - a1) % mu == 0 or a == a2
            for v in range(low, high + 1):
                beam = (v - low) % fh == 0 or v == high
                self.put(a if along else fixed, v, fixed if along else a,
                         mullion_block if mullion or beam else glass_block)

    def diagrid(self, u1, base_v, w1, u2, top_v, w2, panel_width,
                panel_height, line_width, block):
        along = abs(u2 - u1) >= abs(w2 - w1)
        a1, a2 = self.span(u1 if along else w1, u2 if along else w2)
        fixed = w1 if along else u1
        low, high = self.span(base_v, top_v)
        pw, ph = max(1, int(panel_width)), max(1, int(panel_height))
        mod, lw = pw * ph, max(1, min(pw * ph, int(line_width)))
        for a in range(a1, a2 + 1):
            for v in range(low, high + 1):
                du, dv = a - a1, v - low
                x = (du * ph + dv * pw) % mod
                y = (du * ph - dv * pw) % mod
                if x < lw or y < lw:
                    self.put(a if along else fixed, v, fixed if along else a, block)

    def stair_tower(self, cu, cw, base_v, radius, steps, turns, core_radius,
                    step_block, core_block=None):
        if radius <= 0 or steps <= 0:
            raise ValueError("stair_tower radius/steps 必须 >0")
        cr = max(0, int(core_radius))
        cb = self.block(core_block, self.block(step_block))
        if cr:
            for v in range(base_v, base_v + steps + 1):
                for du in range(-cr, cr + 1):
                    for dw in range(-cr, cr + 1):
                        if du * du + dw * dw <= cr * cr:
                            self.put(cu + du, v, cw + dw, cb)
        for s in range(int(steps) + 1):
            angle = math.tau * turns * s / steps
            for r in range(max(1, cr), int(radius) + 1):
                u = cu + self.jround(r * math.cos(angle))
                w = cw + self.jround(r * math.sin(angle))
                self.put(u, base_v + s, w, step_block)
                if r >= radius - 1:
                    self.put(u, base_v + s + 1, w, cb)

    def lattice_truss(self, u1, v1, w1, u2, v2, w2, spacing, block):
        ua, ub = self.span(u1, u2)
        va, vb = self.span(v1, v2)
        wa, wb = self.span(w1, w2)
        sp = max(2, int(spacing))
        estimate = ((ub - ua) // sp + 1) * ((vb - va) // sp + 1) * ((wb - wa) // sp + 1) * (3 * sp // 2 + 1)
        if estimate > 40000:
            raise ValueError("lattice_truss 预计 %d 格超过 40000；请缩小范围或增大 spacing" % estimate)
        for u in range(ua, ub + 1, sp):
            for v in range(va, vb + 1, sp):
                for w in range(wa, wb + 1, sp):
                    self.line((u, v, w), (min(ub, u + sp), v, w), block)
                    self.line((u, v, w), (u, min(vb, v + sp), w), block)
                    self.line((u, v, w), (u, v, min(wb, w + sp)), block)
