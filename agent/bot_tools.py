"""能力工具 handler 与服务端操作: 聊天/技能/查询(bus)/控制台指令/常加载。

依赖方向: bot_tools → bus/constants/profiles/paths/capabilities; 不 import 其它 bot_* 模块。
"""
import json
import re
import time

import capabilities

from . import build, history, images, paths
from .bus import BusArgError, Req
from .constants import (
    BUS_TIMEOUT_TEXT,
    BUS_TOOLS,
    CREATIVE_MODES,
    PIN_NAME,
    RE_LINE,
    CELLS_HARD,
    FIND_MAX_VOLUME,
    HM_MAX_COLUMNS,
    INSPECT_MAX_VOLUME,
    PACK_PROTO_SPATIAL,
    SLICE_MAX_CELLS,
)
from .paths import log
from .profiles import MODES


class BotToolsMixin:
    """全部 _tool_* handler 与服务端查询渲染。"""

    def _tool_send_message(self, args: dict) -> str:
        self.bridge.say_as_agent(args["text"], self.cfg["reply_chunk_len"],
                                  self._reply_max_chunks())
        return "已发送到游戏内聊天。"

    def _tool_use_skill(self, args: dict) -> str:
        name = (args.get("name") or "").strip()
        file = (args.get("file") or "").strip()
        key = f"{name}/{file}" if file else name
        sess = self._session()
        if sess is not None and key in sess.loaded_skills and not args.get("force"):
            return f"（本会话已载入过技能 {key}, 内容见上文; 如确需重新载入请加 force=true。）"
        text = capabilities.use_skill(name, file)
        if sess is not None and text.startswith("# 技能书:"):
            sess.loaded_skills.add(key)
        return text

    @staticmethod
    def _looks_like_name_list(line: str) -> bool:
        """判断是否为 list 指令的裸名单行(无时间戳), 如 'kirin9000S, RED83051059'。"""
        s = line.strip()
        return bool(s) and bool(re.fullmatch(
            r"[A-Za-z0-9 _\-\.]{1,20}(, *[A-Za-z0-9 _\-\.]{1,20})*", s))

    # ---------- 服务端查询: 走请求总线(协议 v5) ----------
    # 同一批 bus 查询先全部登记、再一次性下发, 只付一次 stdin 轮询延迟, 回包按 id 路由。
    # 行为包需支持 agent:hello 握手与 r<id> 回显(见 main.js); 未握手成功时 bus_enabled=False。

    def _bus_cmd(self, name: str, rid: str, args: dict) -> str:
        """构造带请求 id 的 scriptevent 命令; 参数非法抛 BusArgError(消息回给模型)。"""
        if name == "get_player_position":
            return f"scriptevent agent:pos {rid}"
        if name == "get_player_hand":
            return f"scriptevent agent:inv {rid}"
        if name == "get_block":
            try:
                x, y, z = (int(args[k]) for k in ("x", "y", "z"))
            except (KeyError, TypeError, ValueError):
                raise BusArgError("需要整数坐标 x y z。")
            dim = (args.get("dimension") or "overworld").strip().lower()
            return f"scriptevent agent:block {rid} {x} {y} {z} {dim}"
        if name == "get_heightmap":
            return self._heightmap_cmd(rid, args)
        if name == "get_slice":
            return self._slice_cmd(rid, args)
        if name == "inspect_region":
            return self._inspect_cmd(rid, args)
        if name == "find_blocks":
            return self._find_cmd(rid, args)
        raise BusArgError(f"错误: 未知的查询工具 {name}")

    # ---------- 空间感知原语(协议 v5): 由粗到细 ----------
    # 一次调用看清一片, 而不是切几十张薄片、每格一行:
    #   get_heightmap  地形高度(选址/落差/地基)
    #   get_slice      一张平面字符图(看形状/立面/剖面)
    #   inspect_region 区域聚合(类型计数 / 不符项坐标: 施工复检主力)
    #   find_blocks    区域内找某方块坐标
    # 参数校验放在下发之前: 省一次往返, 错误信息也直接可读。

    @staticmethod
    def _box(args: dict, names=("x1", "y1", "z1", "x2", "y2", "z2")) -> tuple:
        try:
            return tuple(int(args[k]) for k in names)
        except (KeyError, TypeError, ValueError):
            raise BusArgError("需要整数坐标 " + " ".join(names) + "。")

    def _heightmap_cmd(self, rid: str, args: dict) -> str:
        detail = str(args.get("detail") or "summary").strip().lower()
        if detail not in ("summary", "heights", "full"):
            raise BusArgError('detail 只能是 "summary" / "heights" / "full"。')
        x1, z1, x2, z2 = self._box(args, ("x1", "z1", "x2", "z2"))
        cols = (abs(x2 - x1) + 1) * (abs(z2 - z1) + 1)
        if cols > HM_MAX_COLUMNS:
            raise BusArgError(build.limit_hint(
                "高度图列数", cols, HM_MAX_COLUMNS, "64×64", "列")
                + f" 当前范围 {abs(x2 - x1) + 1}×{abs(z2 - z1) + 1}。")
        dim = (args.get("dimension") or "overworld").strip().lower()
        cmd = f"scriptevent agent:heightmap {rid} {x1} {z1} {x2} {z2} {dim}"
        extra = []
        for key in ("y_max", "y_min"):
            if args.get(key) is not None:
                extra.append(str(int(args[key])))
        if extra:  # 行为包按位置解析 yMax yMin, 只给一个时补齐另一个
            if len(extra) == 1:
                extra.append("-64")
            cmd += " " + " ".join(extra)
        return cmd

    def _slice_cmd(self, rid: str, args: dict) -> str:
        axis = (args.get("axis") or "y").strip().lower()
        if axis not in ("x", "y", "z"):
            raise BusArgError("axis 只能是 x / y / z。")
        try:
            level = int(args["level"])
        except (KeyError, TypeError, ValueError):
            raise BusArgError("需要整数 level(切面所在坐标)。")
        x1, y1, z1, x2, y2, z2 = self._box(args)
        # 只取 level 那一层: level 轴塌缩成 level, 另两个轴的范围来自两角点
        if axis == "y":
            a1, a2, b1, b2 = x1, x2, z1, z2
        elif axis == "x":
            a1, a2, b1, b2 = z1, z2, y1, y2
        else:
            a1, a2, b1, b2 = x1, x2, y1, y2
        cells = (abs(a2 - a1) + 1) * (abs(b2 - b1) + 1)
        if cells > SLICE_MAX_CELLS:
            raise BusArgError(build.limit_hint("切面", cells, SLICE_MAX_CELLS, "64×64"))
        dim = (args.get("dimension") or "overworld").strip().lower()
        return f"scriptevent agent:slice {rid} {axis} {level} {a1} {b1} {a2} {b2} {dim}"

    def _inspect_cmd(self, rid: str, args: dict) -> str:
        x1, y1, z1, x2, y2, z2 = self._box(args)
        volume = (abs(x2 - x1) + 1) * (abs(y2 - y1) + 1) * (abs(z2 - z1) + 1)
        if volume > INSPECT_MAX_VOLUME:
            raise BusArgError(build.limit_hint("区域", volume, INSPECT_MAX_VOLUME, "32×32×32")
                              + " 只看地表用 get_heightmap、只看一层用 get_slice 更省。")
        dim = (args.get("dimension") or "overworld").strip().lower()
        detail = (args.get("detail") or "summary").strip().lower()
        if detail not in ("summary", "cells"):
            raise BusArgError('detail 只能是 "summary" 或 "cells"。')
        limit = max(1, min(int(args.get("limit") or 64), CELLS_HARD))
        filt = re.sub(r"\s+", "", str(args.get("filter") or "")).lower().replace("minecraft:", "")
        return (f"scriptevent agent:inspect {rid} {x1} {y1} {z1} {x2} {y2} {z2}"
                f" {dim} {filt or '-'} {detail} {limit}")

    def _find_cmd(self, rid: str, args: dict) -> str:
        block = re.sub(r"\s+", "", str(args.get("block") or "")).lower().replace("minecraft:", "")
        if not block:
            raise BusArgError("需要 block(方块类型, 可写片段如 ore)。")
        x1, y1, z1, x2, y2, z2 = self._box(args)
        volume = (abs(x2 - x1) + 1) * (abs(y2 - y1) + 1) * (abs(z2 - z1) + 1)
        if volume > FIND_MAX_VOLUME:
            raise BusArgError(build.limit_hint("搜索范围", volume, FIND_MAX_VOLUME, "32×32×32"))
        dim = (args.get("dimension") or "overworld").strip().lower()
        limit = max(1, min(int(args.get("limit") or 128), CELLS_HARD))
        return (f"scriptevent agent:find {rid} {block} {x1} {y1} {z1} {x2} {y2} {z2}"
                f" {dim} {limit}")

    def _bus_spec(self, name: str, args: dict):
        """返回 (kind, timeout, args); 命令在拿到 rid 后再构造, 便于把校验错误回给模型。"""
        kind, tkey = BUS_TOOLS[name]
        return (kind, self.cfg.get(tkey, 5), args)

    def _bus_call(self, name: str, args: dict) -> str:
        """单个 bus 查询: 登记 -> 下发 -> 按 id 等回包 -> 渲染。"""
        kind, timeout, a = self._bus_spec(name, args)
        rid = self.bus.next_id()
        try:
            cmd = self._bus_cmd(name, rid, a)
        except BusArgError as e:
            return str(e)
        req = self.bus.submit_many([(rid, kind, cmd, timeout, a)])[0]
        if not self.bus.wait(req, self._abort()):
            if self._abort().is_set():
                return "已中止。"
            return BUS_TIMEOUT_TEXT[name]
        return self._bus_render(name, req, a)

    def _run_bus_batch(self, jobs):
        """capabilities 的批量执行器: jobs=[(name, args)]; 返回等长结果列表。
        一次登记整批 -> 一次下发 -> 按 id 收齐, 共享一次服务端轮询延迟。"""
        outs: list = [None] * len(jobs)
        specs, meta = [], []
        for i, (name, args) in enumerate(jobs):
            kind, timeout, a = self._bus_spec(name, args)
            rid = self.bus.next_id()
            try:
                cmd = self._bus_cmd(name, rid, a)
            except BusArgError as e:
                outs[i] = str(e)
                continue
            specs.append((rid, kind, cmd, timeout, a))
            meta.append((i, name, a))
        if specs:
            reqs = self.bus.submit_many(specs)
            for req, (i, name, a) in zip(reqs, meta):
                if self.bus.wait(req, self._abort()):
                    outs[i] = self._bus_render(name, req, a)
                elif self._abort().is_set():
                    outs[i] = "已中止。"
                else:
                    outs[i] = BUS_TIMEOUT_TEXT[name]
        return outs

    def _bus_render(self, name: str, req: Req, args: dict) -> str:
        if name == "get_player_position":
            return self._render_position(req, args)
        if name == "get_player_hand":
            return self._render_hand(req, args)
        if name == "get_block":
            return self._render_block(req, args)
        if name == "get_heightmap":
            return self._render_heightmap(req, args)
        if name == "get_slice":
            return self._render_slice(req, args)
        if name == "inspect_region":
            return self._render_inspect(req, args)
        return self._render_find(req, args)

    def _render_position(self, req: Req, args: dict) -> str:
        found: dict[str, str] = {}
        empty = False
        for body in req.lines:
            if not body or body == "DONE":
                continue
            if body.startswith("("):
                empty = empty or ("无玩家在线" in body)
                continue
            parts = body.split()
            if len(parts) >= 5:
                found[parts[0]] = f"{parts[1]}, {parts[2]}, {parts[3]} ({parts[4]})"
        if not found:
            if empty:
                return "当前没有玩家在线, 取不到坐标。"
            return BUS_TIMEOUT_TEXT["get_player_position"]
        self.player_positions.update(found)
        want = (args.get("player") or "").strip()
        if want:
            for nm, pos in found.items():
                if nm.lower() == want.lower():
                    return f"{nm} 的坐标: {pos}"
            return f"玩家 {want} 不在线。当前在线: {', '.join(sorted(found))}"
        return "在线玩家坐标:\n" + "\n".join(f"{n}: {p}" for n, p in sorted(found.items()))

    def _render_hand(self, req: Req, args: dict) -> str:
        data: dict[str, dict] = {}
        empty = False
        for body in req.lines:
            if not body or body == "DONE":
                continue
            if body.startswith("("):
                empty = empty or ("无玩家在线" in body)
                continue
            m = re.match(r"^(\S+) DONE (-?\d+)$", body)
            if m:
                rec = data.setdefault(m.group(1), {"slots": {}, "selected": -1})
                rec["selected"] = int(m.group(2))
                continue
            parts = body.split()
            if len(parts) >= 4:
                rec = data.setdefault(parts[0], {"slots": {}, "selected": -1})
                try:
                    rec["slots"][int(parts[1])] = (parts[2].replace("minecraft:", ""), int(parts[3]))
                except ValueError:
                    pass
        if not data:
            if empty:
                return "当前没有玩家在线, 取不到手持物品。"
            return BUS_TIMEOUT_TEXT["get_player_hand"]
        picked, err = self._pick_players(args, data)
        if err:
            return err
        lines = []
        for name, rec in sorted(picked.items()):
            item = rec["slots"].get(rec["selected"])
            if item:
                lines.append(f"{name} 手持(槽{rec['selected']}): {item[0]} x{item[1]}")
            else:
                lines.append(f"{name} 空手")
        return "\n".join(lines)[:600]

    def _render_block(self, req: Req, args: dict) -> str:
        x, y, z = (int(args[k]) for k in ("x", "y", "z"))
        for body in req.lines:
            if not body:
                continue
            if body.startswith("("):  # 脚本的提示/错误行, 例如区块未加载
                return f"查不到方块: {body}"
            parts = body.split(" ", 4)
            if len(parts) < 5:
                return f"脚本回包异常: {body}"
            bdim, block = parts[3], parts[4].replace("minecraft:", "", 1)
            return f"坐标 ({x}, {y}, {z}) [{bdim}] 的方块是: {block}"
        return BUS_TIMEOUT_TEXT["get_block"]

    # ---------- 查询渲染: JSON payload -> 紧凑可读文本 ----------

    # 字符图符号: 空气固定 "."(最好认), 其余方块按调色板顺序取下面的符号;
    # "?" 专门表示未加载/未知, "-" 表示高度缺失, 都不参与分配, 避免混淆。
    GRID_SYMBOLS = "#=+*%@&$~^<>oOxXvVzZ0123456789"
    AIR_TYPES = ("air", "cave_air", "void_air")

    @classmethod
    def _symbols(cls, palette: list) -> list:
        """调色板索引 -> 单字符。同一张图里 legend 与网格共用这一份映射。"""
        out, k = [], 0
        for name in palette:
            if name in (None, "", "?"):
                out.append("?")
            elif name in cls.AIR_TYPES:
                out.append(".")
            else:
                out.append(cls.GRID_SYMBOLS[k] if k < len(cls.GRID_SYMBOLS) else "?")
                k += 1
        return out

    @classmethod
    def _sym(cls, palette: list, idx: int) -> str:
        syms = cls._symbols(palette)
        return syms[idx] if 0 <= idx < len(syms) else "?"

    def _payload(self, name: str, req: Req) -> dict | str:
        """取出分帧 JSON; 返回 dict, 或直接可回给模型的错误文本。"""
        if req.payload is None:
            if req.chunks:
                got = len(req.chunks)
                return (f"行为包回包不完整({got}/{req.chunk_total} 帧), 可能是日志被截断; "
                        "请缩小范围重试。")
            return BUS_TIMEOUT_TEXT[name]
        try:
            data = json.loads(req.payload)
        except (json.JSONDecodeError, TypeError) as e:
            return f"行为包回包不是合法 JSON: {e}"
        if not isinstance(data, dict) or not data.get("ok"):
            err = data.get("error") if isinstance(data, dict) else data
            return f"查询失败: {err or '未知错误'}"
        return data

    @staticmethod
    def _dim(data: dict) -> str:
        return str(data.get("dim", "")).replace("minecraft:", "") or "overworld"

    @classmethod
    def _legend(cls, palette: list, counts=None, limit: int = 14) -> str:
        """图例: 符号=类型(数量), 与网格使用同一份符号映射。"""
        syms = cls._symbols(palette)
        parts = []
        for i, name in enumerate(palette):
            if name in (None, "", "?"):
                continue
            n = counts[i] if isinstance(counts, list) and i < len(counts) else None
            tag = f" {n}" if n is not None else ""
            parts.append(f"{syms[i]}={name}{tag}")
            if len(parts) >= limit:
                parts.append("…")
                break
        return "  ".join(parts)

    def _render_heightmap(self, req: Req, args: dict) -> str:
        data = self._payload("get_heightmap", req)
        if isinstance(data, str):
            return data
        detail = str(args.get("detail") or "summary").strip().lower()
        w, h = data["w"], data["h"]
        heights, types, palette = data["heights"], data["types"], data["palette"]
        fx, fz = data["from"]
        tx, tz = data["to"]
        unloaded, missing = data.get("unloaded", 0), data.get("missing", 0)

        # types=255 才表示未加载/无方块; 高度本身可以是负数。
        def unavailable(i: int) -> bool:
            return i >= len(heights) or i >= len(types) or types[i] == 255

        valid_indices = [i for i in range(w * h) if not unavailable(i)]
        valid = [heights[i] for i in valid_indices]
        low, high = (min(valid), max(valid)) if valid else (None, None)
        head = (f"地形高度 x {fx}..{tx}, z {fz}..{tz} [{self._dim(data)}]: {w}×{h} 列, "
                + (f"地表 y {low}~{high}" if valid else "没有可读地表"))
        if unloaded:
            head += f", 未加载 {unloaded} 列"
        if missing:
            head += f", 无方块 {missing} 列"
        out = [head]
        if not valid:
            # 没数据时打印几千个 --- 只会浪费上下文。
            out.append("所有列均未加载或没有方块，已省略空网格。")
            return "\n".join(out)

        counts = [0] * len(palette)
        for i in valid_indices:
            p = types[i]
            if 0 <= p < len(counts):
                counts[p] += 1
        materials = sorted(((name, counts[i]) for i, name in enumerate(palette)
                            if name not in (None, "", "?") and counts[i]),
                           key=lambda item: (-item[1], item[0]))

        def material_text() -> str:
            parts = [f"{name} {count}列" for name, count in materials[:10]]
            if len(materials) > 10:
                parts.append(f"其他 {sum(n for _, n in materials[10:])}列")
            return ", ".join(parts)

        if detail == "summary":
            # 默认只给决策所需的信息，不把两张 O(w*h) 的网格灌进上下文。
            low_i = next(i for i in valid_indices if heights[i] == low)
            high_i = next(i for i in valid_indices if heights[i] == high)
            out.append(
                f"高度摘要: 平均 {sum(valid) / len(valid):.1f}, 落差 {high - low}; "
                f"最低 {low} @ ({fx + low_i % w},{fz + low_i // w}), "
                f"最高 {high} @ ({fx + high_i % w},{fz + high_i // w})")
            points, seen = [], set()
            for label, c, r in (("中心", w // 2, h // 2), ("西北", 0, 0),
                                ("东北", w - 1, 0), ("西南", 0, h - 1),
                                ("东南", w - 1, h - 1)):
                if (c, r) in seen:
                    continue
                seen.add((c, r))
                i = r * w + c
                value = "---" if unavailable(i) else str(heights[i])
                points.append(f"{label}({fx + c},{fz + r})={value}")
            out.append("关键点地表 y: " + "; ".join(points))
            if materials:
                out.append("顶面类型: " + material_text())
            return "\n".join(out)

        # heights = 完整高度网格 + 顶面计数; full = 再加顶面分布图。
        out.append("完整逐列高度: 行=z(北→南), 列=x(西→东); --- = 未加载/无方块")
        for r in range(h):
            row = []
            for c in range(w):
                i = r * w + c
                row.append("---" if unavailable(i) else f"{heights[i]:3d}")
            out.append(" ".join(row))
        if materials:
            out.append("顶面类型计数: " + material_text())
        if detail == "full" and palette:
            out.append("顶面方块分布:")
            syms = self._symbols(palette)
            for r in range(h):
                row = types[r * w:(r + 1) * w]
                out.append("".join("?" if v == 255 else (syms[v] if v < len(syms) else "?")
                                   for v in row))
            out.append("图例: " + self._legend(palette, counts))
        return "\n".join(out)

    def _render_slice(self, req: Req, args: dict) -> str:
        data = self._payload("get_slice", req)
        if isinstance(data, str):
            return data
        axis, level = data["axis"], data["level"]
        palette, rows, counts = data["palette"], data["rows"], data.get("counts") or []
        w, h, unloaded = data["w"], data["h"], data.get("unloaded", 0)
        orient = {
            "y": "行=z(北→南), 列=x(西→东), 俯视",
            "x": "行=y(高→低), 列=z(北→南), 侧视",
            "z": "行=y(高→低), 列=x(西→东), 前视",
        }[axis]
        head = f"{orient} 切面 {axis}={level} [{self._dim(data)}]: {w}×{h} 格"
        if unloaded:
            head += f", 未加载 {unloaded} 格(显示 ?)"
        out = [head]
        for row in rows:
            syms = self._symbols(palette)
            line = []
            for ch in row:
                if ch == "?":
                    line.append("?")
                    continue
                i = int(ch, 36)
                line.append(syms[i] if i < len(syms) else "?")
            out.append("".join(line))
        out.append("图例: " + self._legend(palette, counts))
        return "\n".join(out)

    def _render_inspect(self, req: Req, args: dict) -> str:
        data = self._payload("inspect_region", req)
        if isinstance(data, str):
            return data
        fx, fy, fz = data["from"]
        tx, ty, tz = data["to"]
        volume, unloaded, air = data["volume"], data.get("unloaded", 0), data.get("air", 0)
        head = (f"区域 ({fx}, {fy}, {fz})..({tx}, {ty}, {tz}) [{self._dim(data)}] "
                f"共 {volume} 格: 空气 {air} 格")
        if unloaded:
            head += f", 未加载 {unloaded} 格(结论只覆盖已加载部分)"
        out = [head]
        types = data.get("types") or {}
        if types:
            total = max(1, volume - unloaded)
            items = [f"{n} {c}格({c * 100 / total:.1f}%)" for n, c in types.items()]
            if data.get("otherTypes"):
                items.append(f"其他 {data['otherTypes']}格")
            out.append("类型: " + ", ".join(items))
        if data.get("filter"):
            extra = ""
            if "holes" in data:
                extra = f'(其中空洞 {data.get("holes", 0)} 格, 放错 {data.get("wrong", 0)} 格)'
            out.append(f'筛选 "{data["filter"]}": 命中 {data.get("match", 0)} 格, '
                       f'不符合 {data.get("mismatch", 0)} 格{extra}')
            samples = data.get("mismatchSamples") or []
            if samples:
                out.append("不符合的位置(供逐条修复):")
                for x, y, z, t in samples:
                    out.append(f"  ({x}, {y}, {z}) {str(t).replace('minecraft:', '')}")
        cells = data.get("cells")
        if cells is not None:
            label = "命中单元" if data.get("filter") else "非空气单元"
            out.append(f"{label} {len(cells)} 条")
            palette = data.get("palette") or []
            for x, y, z, i in cells:
                name = palette[i] if 0 <= i < len(palette) else "?"
                out.append(f"  ({x}, {y}, {z}) {name}")
            if data.get("cellsTruncated"):
                out.append("  …(已达条数上限, 还有更多)")
        if not types and not data.get("filter") and not cells:
            out.append("区域内没有可报告的方块(可能整片未加载)。")
        return "\n".join(out)

    def _render_find(self, req: Req, args: dict) -> str:
        data = self._payload("find_blocks", req)
        if isinstance(data, str):
            return data
        fx, fy, fz = data["from"] if "from" in data else (
            args.get("x1", "?"), args.get("y1", "?"), args.get("z1", "?"))
        tx, ty, tz = data["to"] if "to" in data else (
            args.get("x2", "?"), args.get("y2", "?"), args.get("z2", "?"))
        block = data.get("block", "")
        match, positions = data.get("match", 0), data.get("positions") or []
        out = [f'在 ({fx}, {fy}, {fz})..({tx}, {ty}, {tz}) [{self._dim(data)}] '
               f'{data.get("volume", "?")} 格中找 "{block}": {match} 处']
        if positions:
            out.append("坐标: " + ", ".join(f"({x},{y},{z})" for x, y, z in positions))
        if data.get("truncated"):
            out.append(f"(只列前 {len(positions)} 处, 共有 {match} 处; 想全看请缩小范围)")
        if data.get("unloaded"):
            out.append(f"注意: 有 {data['unloaded']} 格未加载, 未参与搜索(可能漏掉)。")
        return "\n".join(out)

    def _require_bus(self) -> str:
        if self.bus_enabled:
            return ""
        return ("行为包脚本未响应协议握手(agent:hello)。"
                "请确认已更新并重载 agent_bridge 行为包(需支持 r<id> 回显)。")

    def _tool_get_position(self, args: dict) -> str:
        if err := self._require_bus():
            return err
        return self._bus_call("get_player_position", args or {})

    def _pick_players(self, args: dict, data: dict) -> tuple[dict, str]:
        """按 player 参数筛选玩家, 返回 (选中, 错误信息)。"""
        want = (args.get("player") or "").strip()
        if not data:
            return {}, "当前没有玩家在线。"
        if not want:
            return data, ""
        for name in data:
            if name.lower() == want.lower():
                return {name: data[name]}, ""
        return {}, f"玩家 {want} 不在线。当前在线: {', '.join(sorted(data))}"

    def _tool_get_hand(self, args: dict) -> str:
        if err := self._require_bus():
            return err
        return self._bus_call("get_player_hand", args or {})

    def _tool_get_block(self, args: dict) -> str:
        if err := self._require_bus():
            return err
        return self._bus_call("get_block", args or {})

    def _require_spatial(self) -> str:
        """空间感知原语需要协议 v5; 协议过旧时明确报错, 不要让它拿到空数据。"""
        if err := self._require_bus():
            return err
        if getattr(self, "pack_proto", 0) < PACK_PROTO_SPATIAL:
            return (f"行为包协议过旧(v{getattr(self, 'pack_proto', 0)}), "
                    "不支持 heightmap/slice/inspect/find; 请重载更新后的 agent_bridge 行为包。")
        return ""

    def _tool_get_heightmap(self, args: dict) -> str:
        if err := self._require_spatial():
            return err
        return self._bus_call("get_heightmap", args or {})

    def _tool_get_slice(self, args: dict) -> str:
        if err := self._require_spatial():
            return err
        return self._bus_call("get_slice", args or {})

    def _tool_inspect_region(self, args: dict) -> str:
        if err := self._require_spatial():
            return err
        return self._bus_call("inspect_region", args or {})

    def _tool_find_blocks(self, args: dict) -> str:
        if err := self._require_spatial():
            return err
        return self._bus_call("find_blocks", args or {})

    # ---------- 图片兜底 ----------

    def _tool_view_image(self, args: dict) -> str:
        """兜底: 把指定图片附进上下文。直链通常已自动附上, 这里只处理"没自动附上"的场合。"""
        url = images.normalize_url(str(args.get("url") or ""))
        if not url:
            return "错误: 需要图片地址。"
        if not url.lower().startswith(("http://", "https://")):
            return "错误: 只支持 http/https 图片地址。"
        part = self._image_part(url)
        if part is None:
            return (f"错误: 读不到 {url} 这张图(地址不是有效图片或无法访问); "
                    "如实告诉玩家图片没加载出来, 不要描述画面。")
        if not capabilities.add_image_block(part):
            return "错误: 本次附带的图片太多, 这张没有附上; 需要就分批看图。"
        return (f"[图片] {url} 已附在上下文里(系统在工具结果之后补一条消息), 直接看图。"
                "游戏聊天栏显示不了图片, 用一两句话把主体/颜色/文字转述给玩家。")

    # ---------- 施工台账 / 会话历史(只读查询, 不恢复会话) ----------

    def _tool_find_builds(self, args: dict) -> str:
        return history.find_builds(
            query=str(args.get("query") or ""),
            since=str(args.get("since") or ""),
            until=str(args.get("until") or ""),
            player=str(args.get("player") or ""),
            limit=args.get("limit", history.DEFAULT_BUILD_LIMIT),
            state=str(args.get("state") or "built"),
            group=bool(args.get("group", True)),
        )

    def _tool_read_build(self, args: dict) -> str:
        return history.read_build(
            str(args.get("ref") or ""),
            program_lines=args.get("program_lines", 40),
        )

    def _tool_search_history(self, args: dict) -> str:
        return history.search_history(
            str(args.get("query") or ""),
            since=str(args.get("since") or ""),
            file=str(args.get("file") or ""),
            limit=args.get("limit", history.DEFAULT_SEARCH_LIMIT),
        )

    def _tool_read_session(self, args: dict) -> str:
        return history.read_session(
            str(args.get("file") or ""),
            contains=str(args.get("contains") or ""),
            around=args.get("around"),
            window=args.get("window", 3),
            max_chars=int(args.get("max_chars")
                          or self.cfg.get("session_read_max_chars", history.DEFAULT_MAX_CHARS)),
        )

    # ---------- 台账写入上下文(给 agent/ledger.py 用) ----------

    def _ledger_ctx(self) -> dict:
        """当前会话在哪落盘 + 本回合谁在说话: 台账要能回到会话文件与玩家。"""
        sess = self._session()
        started = getattr(sess, "started", None)
        players = getattr(self._tls, "turn_players", None) or set()
        return {"session": getattr(sess, "id", None),
                "session_start": started.isoformat(timespec="seconds") if started else "",
                "player": ", ".join(sorted(players)),
                "trigger": self._last_user_text()}

    def _last_user_text(self) -> str:
        """上一条玩家消息(去掉 “玩家名: ” 前缀), 作为台账里“触发这次施工”的原话。"""
        sess = self._session()
        for m in reversed(getattr(sess, "messages", []) or []):
            if m.get("role") != "user":
                continue
            text = str(m.get("content") or "").strip()
            head = text.split("\n", 1)[0]
            if re.match(r"^[^:\n]{1,24}:\s", text):
                text = re.sub(r"^[^:\n]{1,24}:\s+", "", text, count=1)
            return (text or head)[:400]
        return ""

    def _extract_command_output(self, text: str, cmd: str) -> list[str]:
        """从日志文本里抽出指令输出。ERROR/WARN 行必须保留并加标记——
        否则指令静默失败时模型看不到任何反馈, 会编造“已办妥”。"""
        lines = []
        for line in text.splitlines():
            m = RE_LINE.match(line)
            if m:
                level, body = m.group(2), m.group(3)
                if any(t in body for t in ("[AGENT-CHAT]", "[AGENT-POS]",
                                          "[AGENT-INV]", "[AGENT-BLOCK]",
                                          "[AGENT-SCAN]")):
                    continue  # 桥接上报行不是指令输出
                if level == "ERROR":
                    body = "[错误] " + body
                elif level == "WARN":
                    body = "[警告] " + body
                lines.append(body)
            elif self._looks_like_name_list(line) and line.strip() != cmd:
                lines.append(line.strip())
        return lines

    def _console_output(self, cmd: str) -> str:
        """发一条控制台指令并轮询等待输出, 返回抽取后的输出文本。
        超时、被中止或读不到日志时返回空串。"""
        log_file = paths.SERVER_LOG_PATH
        try:
            offset = log_file.stat().st_size
        except FileNotFoundError:
            return ""
        self.bridge.send_command(cmd)
        # screen 日志 flush 有延迟(实测可达 3s), 轮询等待输出
        timeout = self.cfg.get("command_result_timeout_sec", 6)
        deadline = time.time() + timeout
        while True:
            if self._abort().is_set():
                return ""
            try:
                with open(log_file, encoding="utf-8", errors="replace") as f:
                    f.seek(offset)
                    new = f.read()
            except FileNotFoundError:
                return ""
            # 带时间戳的输出行(剔除聊天桥行, 保留错误/警告) + list 的裸名单行(无时间戳)
            lines = self._extract_command_output(new, cmd)
            if lines:
                time.sleep(0.5)  # 宽限, 让多行输出到齐
                with open(log_file, encoding="utf-8", errors="replace") as f:
                    f.seek(offset)
                    new = f.read()
                return "\n".join(self._extract_command_output(new, cmd)).strip()
            if time.time() >= deadline:
                return ""
            time.sleep(0.3)

    def _tool_run_command(self, args: dict) -> str:
        with self.console_gate:
            return self._run_command_locked(args)

    def _run_command_locked(self, args: dict) -> str:
        cmd = re.sub(r"[\r\n]+", " ", args["command"].strip()).lstrip("/").strip()
        if not cmd:
            return "空指令, 未执行。"
        verb = cmd.split()[0].lower()
        blocklist = {c.lower() for c in self.cfg.get("command_blocklist", [])}
        if verb in blocklist:
            return f"指令 {verb} 在禁止列表中, 未执行。"
        log(f"[指令] /{cmd}")  # 只进日志: 命令在模型自己的 tool_call 里, 不必再回显占用上下文
        out = self._console_output(cmd)
        if out:
            return out[:800]
        if self._abort().is_set():
            return "已中止(指令已发出, 无法撤回)"
        timeout = self.cfg.get("command_result_timeout_sec", 6)
        return f"已执行, {timeout}s 内无输出"

    # ---------- 常加载区域 ----------

    def _tool_pin_region(self, args: dict) -> str:
        with self.console_gate:
            return self._pin_region_locked(args)

    def _pin_region_locked(self, args: dict) -> str:
        """pin_region: 创造模式下把施工区域设为常加载(ticking area)。
        生命周期 = 创造模式: 离开该模式(切回 normal 等)或会话结束时由 _unpin_all 移除。"""
        try:
            x1, z1, x2, z2 = (int(args[k]) for k in ("x1", "z1", "x2", "z2"))
        except (KeyError, TypeError, ValueError):
            return "错误: 需要整数参数 x1, z1, x2, z2。"
        # 基岩版单个常加载区域上限 100 区块(实测报错), 按 10x10 区块对齐切片。
        # 区域边界向外对齐到区块, 保证每片不超限。
        cx1, cx2 = sorted((x1 // 16, x2 // 16))
        cz1, cz2 = sorted((z1 // 16, z2 // 16))
        tiles = []
        for cx in range(cx1, cx2 + 1, 10):
            for cz in range(cz1, cz2 + 1, 10):
                tiles.append((cx * 16, cz * 16,
                              min(cx + 9, cx2) * 16 + 15, min(cz + 9, cz2) * 16 + 15))
        max_areas = self.cfg.get("pin_max_areas", 6)
        if len(tiles) > max_areas:
            return (f"错误: 这片区域需要 {len(tiles)} 个常加载片(单片上限 100 区块), "
                    f"超过上限 {max_areas}。请缩小范围或分段施工。")
        self._unpin_all()  # 同一回合再次调用 = 移动区域
        for i, (ax1, az1, ax2, az2) in enumerate(tiles):
            if self._abort().is_set():
                self._unpin_all()
                return "(已中止)"
            name = PIN_NAME if len(tiles) == 1 else f"{PIN_NAME}_{i + 1}"
            out = self._console_output(f"tickingarea add {ax1} 0 {az1} {ax2} 0 {az2} {name}")
            if "[错误]" in out and "already exists" in out:
                # 上次进程被强杀可能留下同名僵尸区域(没来得及 _unpin_all): 清掉重试一次(自愈)
                log(f"[常加载] {name} 已存在, 先清理残留再重试")
                self._console_output(f"tickingarea remove {name}")
                out = self._console_output(f"tickingarea add {ax1} 0 {az1} {ax2} 0 {az2} {name}")
            if "[错误]" in out or not out:
                self._unpin_all()  # 设了一半失败要清干净, 不留下孤儿区域
                return f"错误: 设置常加载区域失败: {out or '指令无回执, 请检查服务器状态'}"
            self._pinned.append(name)
        log(f"[常加载] 已设置 {len(self._pinned)} 个区域覆盖 "
            f"({x1},{z1})~({x2},{z2}): {', '.join(self._pinned)}")
        return (f"已设置 {len(self._pinned)} 个常加载区域, 覆盖 ({x1},{z1})~({x2},{z2}) "
                "整列(不限高度)。离开创造模式时会自动移除; 再次调用会移动区域。")

    def _unpin_all(self):
        """移除本任务设置的常加载区域(任务结束/中止/会话结束/进程退出时调用)。"""
        if not self._pinned:
            return
        names, self._pinned = self._pinned, []
        for name in names:
            self.bridge.send_command(f"tickingarea remove {name}")
        log(f"[常加载] 已移除 {len(names)} 个区域: {', '.join(names)}")

    def _cleanup_stale_pins(self):
        """启动时清理世界里残留的 agent_pin* 常加载区(上次进程被强杀留下的)。
        启动时没有任务在跑, 删掉绝对安全; 只碰自己的名字前缀。"""
        out = self._console_output("tickingarea list")
        names = sorted(set(re.findall(rf"- ({re.escape(PIN_NAME)}[A-Za-z0-9_]*):", out)))
        for name in names:
            self.bridge.send_command(f"tickingarea remove {name}")
            log(f"[常加载] 启动清理残留区域: {name}")


    # ---------- 创造模式 ----------

    def _tool_set_mode(self, args: dict) -> str:
        mode = (args.get("mode") or "").strip()
        reason = (args.get("reason") or "").strip()
        if mode not in MODES:
            return "未知的模式。"
        if mode not in self._mode_next():
            return "当前模式不能切换到该模式。"
        if mode == self._mode():
            return f"当前已处于 {MODES[mode].label} 模式。"
        was_creative = self.creative_mode
        self.mode = mode
        if mode not in CREATIVE_MODES:
            self._unpin_all()  # 离开创造模式 -> 常加载区域生命周期结束
        p = self._mode_params()
        if mode in CREATIVE_MODES:
            log(f"[模式] {'切换' if was_creative else '进入'}创造模式: {mode} "
                f"(原因: {reason or '未说明'}; 思考强度 {p['effort']})")
            # 台账: 从普通进创造才算一次新的施工任务; creative↔creative_max 算同一次
            if not was_creative:
                ctx = self._ledger_ctx()
                self.ledger.open_episode(mode, reason, player=ctx["player"],
                                         trigger=ctx["trigger"], session=ctx["session"],
                                         session_start=ctx["session_start"])
            # 从普通进入创造: 第一轮是长思考, 玩家会干等几十秒没反馈。
            # 这是程序行为, 不依赖模型自觉: 开关一翻就直接播报(升档不重复播报)。
            if not was_creative and self.cfg.get("notify_creative_mode", True):
                self._sys("创造模式已开启: 我在深度思考, 可能要等一会儿, 请稍候。")
            return (f"已进入{MODES[mode].label}模式: 从下一次请求起思考强度 {p['effort']}, "
                    "并启用创造工作方式(更长输出、更多工具轮次、更大上下文)。"
                    "完成后记得用 set_mode 切回 normal。")
        log(f"[模式] 切换到 {MODES[mode].label} (原因: {reason or '未说明'})")
        if was_creative:
            self.ledger.close_episode(reason)  # 全是尽力而为: 不切回来也不影响已记的批次
        return f"已切换到 {MODES[mode].label} 模式。"
