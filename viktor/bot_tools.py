"""能力工具 handler 与服务端操作: 聊天/技能/查询(bus)/控制台指令/常加载/备份执行。

依赖方向: bot_tools → bus/constants/profiles/paths/capabilities; 不 import 其它 bot_* 模块。
"""
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

import capabilities

from . import paths, wiki
from .bus import BusArgError, Req
from .constants import (
    BUS_TIMEOUT_TEXT,
    BUS_TOOLS,
    CREATIVE_MODES,
    PIN_MODES,
    PIN_NAME,
    RE_LINE,
    SCAN_MAX_CELLS,
    SCAN_STATED_CELLS,
)
from .paths import log
from .profiles import MODES


class BotToolsMixin:
    """全部 _tool_* handler 与服务端查询渲染。"""

    def _tool_send_message(self, args: dict) -> str:
        self.bridge.say_as_viktor(args["text"], self.cfg["reply_chunk_len"],
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

    # ---------- 服务端查询: 走请求总线(协议 v2) ----------
    # 同一批 bus 查询先全部登记、再一次性下发, 只付一次 stdin 轮询延迟, 回包按 id 路由。
    # 行为包需支持 viktor:hello 握手与 r<id> 回显(见 main.js); 未握手成功时 bus_enabled=False。

    def _bus_cmd(self, name: str, rid: str, args: dict) -> str:
        """构造带请求 id 的 scriptevent 命令; 参数非法抛 BusArgError(消息回给模型)。"""
        if name == "get_player_position":
            return f"scriptevent viktor:pos {rid}"
        if name == "get_player_hand":
            return f"scriptevent viktor:inv {rid}"
        if name == "get_block":
            try:
                x, y, z = (int(args[k]) for k in ("x", "y", "z"))
            except (KeyError, TypeError, ValueError):
                raise BusArgError("需要整数坐标 x y z。")
            dim = (args.get("dimension") or "overworld").strip().lower()
            return f"scriptevent viktor:block {rid} {x} {y} {z} {dim}"
        if name == "scan_blocks":
            return self._scan_cmd(rid, args)
        raise BusArgError(f"错误: 未知的查询工具 {name}")

    def _scan_cmd(self, rid: str, args: dict) -> str:
        try:
            x1, y1, z1, x2, y2, z2 = (int(args[k]) for k in
                                      ("x1", "y1", "z1", "x2", "y2", "z2"))
        except (KeyError, TypeError, ValueError):
            raise BusArgError("需要整数坐标 x1 y1 z1 x2 y2 z2。")
        dim = (args.get("dimension") or "overworld").strip().lower()
        filt = re.sub(r"\s+", "", args.get("filter") or "").lower()
        xs, ys, zs = sorted((x1, x2)), sorted((y1, y2)), sorted((z1, z2))
        ex, ey, ez = xs[1] - xs[0] + 1, ys[1] - ys[0] + 1, zs[1] - zs[0] + 1
        ext = sorted((ex, ey, ez))
        if ext[0] != 1:
            raise BusArgError(f"这不是 1 格厚的切面({ex}×{ey}×{ez})。请让其中一个轴只有 1 格。")
        cells = ex * ey * ez
        if cells > SCAN_MAX_CELLS:
            raise BusArgError(f"单层切面总格数最多 {SCAN_STATED_CELLS} 格(程序上限 {SCAN_MAX_CELLS}), "
                              f"当前 {ex}×{ey}×{ez}={cells} 格, 请分几次扫描。")
        cmd = f"scriptevent viktor:scan {rid} {x1} {y1} {z1} {x2} {y2} {z2} {dim}"
        if filt:
            cmd += f" {filt}"
        return cmd

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
        return self._render_scan(req, args)

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

    def _render_scan(self, req: Req, args: dict) -> str:
        x1, y1, z1, x2, y2, z2 = (int(args[k]) for k in
                                  ("x1", "y1", "z1", "x2", "y2", "z2"))
        dim = (args.get("dimension") or "overworld").strip().lower()
        filt = re.sub(r"\s+", "", args.get("filter") or "").lower()
        xs, ys, zs = sorted((x1, x2)), sorted((y1, y2)), sorted((z1, z2))
        ex, ey, ez = xs[1] - xs[0] + 1, ys[1] - ys[0] + 1, zs[1] - zs[0] + 1
        rows, done = [], None
        for body in req.lines:
            if body.startswith("DONE"):
                done = body[4:].strip()
                continue
            parts = body.split(" ", 4)
            if len(parts) >= 5 and all(p.lstrip("-").isdigit() for p in parts[:3]):
                rows.append(parts)
        if done is None:
            return BUS_TIMEOUT_TEXT["scan_blocks"]
        info = dict(re.findall(r"(\w+)=([^\s]+)", done))
        if "error" in info:
            return f"扫描失败: {info['error']}"
        total, matched = info.get("total", "?"), info.get("matched", "?")
        unloaded, other = info.get("unloaded", "0"), info.get("other", "")
        label = f'匹配 "{filt}"' if filt else "非空"
        head = (f"切面 {ex}×{ey}×{ez} [{dim}] 共 {total} 格: {label} {matched} 格, "
                f"未加载 {unloaded} 格")
        if other:
            head += f"; 其他方块: {other}"
        limit = self.cfg.get("scan_result_limit", 6000)
        out = [head]
        for p in rows:
            out.append(f"({p[0]}, {p[1]}, {p[2]}) {p[4].replace('minecraft:', '', 1)}")
            if len("\n".join(out)) > limit:
                out.append(f"...(结果过长, 已截断; 共匹配 {matched} 格)")
                break
        return "\n".join(out)

    def _require_bus(self) -> str:
        if self.bus_enabled:
            return ""
        return ("行为包脚本未响应协议握手(viktor:hello)。"
                "请确认已更新并重载 viktor_bridge 行为包(需支持 r<id> 回显)。")

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

    def _tool_scan_blocks(self, args: dict) -> str:
        if err := self._require_bus():
            return err
        return self._bus_call("scan_blocks", args or {})

    # ---------- Minecraft Wiki 查询(HTTP, 实时抓取) ----------
    # 定位是施工辅助: 查事实与数值(配方/掉落/生成/机制/数据值)。ID 用 find_items,
    # 施工手法用技能书。两个工具都是纯查询, 在 ptc 里默认并行。

    def _wiki_lang(self, args: dict) -> str:
        lang = (args.get("lang") or self.cfg.get("wiki_default_lang", "zh")).strip().lower()
        return lang if lang in wiki.WIKI_SITES else "zh"

    def _tool_search_wiki(self, args: dict) -> str:
        return wiki.search(
            args.get("query", ""),
            lang=self._wiki_lang(args),
            limit=args.get("limit", 8),
            timeout=self.cfg.get("wiki_timeout_sec", 15),
            user_agent=self.cfg.get("wiki_user_agent", ""),
        )

    def _tool_read_wiki_page(self, args: dict) -> str:
        return wiki.read_page(
            args.get("title", ""),
            section=args.get("section") or "",
            lang=self._wiki_lang(args),
            max_chars=self.cfg.get("wiki_max_chars", 12000),
            timeout=self.cfg.get("wiki_timeout_sec", 15),
            user_agent=self.cfg.get("wiki_user_agent", ""),
        )

    def _extract_command_output(self, text: str, cmd: str) -> list[str]:
        """从日志文本里抽出指令输出。ERROR/WARN 行必须保留并加标记——
        否则指令静默失败时模型看不到任何反馈, 会编造“已办妥”。"""
        lines = []
        for line in text.splitlines():
            m = RE_LINE.match(line)
            if m:
                level, body = m.group(2), m.group(3)
                if any(t in body for t in ("[VIKTOR-CHAT]", "[VIKTOR-POS]",
                                          "[VIKTOR-INV]", "[VIKTOR-BLOCK]",
                                          "[VIKTOR-SCAN]")):
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
        """pin_region: 创造/执行模式下把施工区域设为常加载(ticking area)。
        生命周期 = 创造/执行模式: 离开这些模式(切回 normal 等)或会话结束时由 _unpin_all 移除。"""
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
                "整列(不限高度)。离开创造/执行模式时会自动移除; 再次调用会移动区域。")

    def _unpin_all(self):
        """移除本任务设置的常加载区域(任务结束/中止/会话结束/进程退出时调用)。"""
        if not self._pinned:
            return
        names, self._pinned = self._pinned, []
        for name in names:
            self.bridge.send_command(f"tickingarea remove {name}")
        log(f"[常加载] 已移除 {len(names)} 个区域: {', '.join(names)}")

    def _cleanup_stale_pins(self):
        """启动时清理世界里残留的 viktor_pin* 常加载区(上次进程被强杀留下的)。
        启动时没有任务在跑, 删掉绝对安全; 只碰自己的名字前缀。"""
        out = self._console_output("tickingarea list")
        names = sorted(set(re.findall(rf"- ({re.escape(PIN_NAME)}[A-Za-z0-9_]*):", out)))
        for name in names:
            self.bridge.send_command(f"tickingarea remove {name}")
            log(f"[常加载] 启动清理残留区域: {name}")

    # ---------- 存档备份 ----------

    @staticmethod
    def _world_name(server_dir: Path) -> str:
        try:
            for line in (server_dir / "server.properties").read_text(encoding="utf-8").splitlines():
                if line.startswith("level-name="):
                    return line.split("=", 1)[1].strip()
        except FileNotFoundError:
            pass
        return "Bedrock level"

    def _await_log(self, pattern: str, timeout: float, offset: int) -> tuple[bool, int]:
        """从 offset 开始轮询 server.log 等某个正则出现。返回 (是否命中, 新 offset)。"""
        rx = re.compile(pattern)
        deadline = time.time() + timeout
        log_file = paths.SERVER_LOG_PATH
        while time.time() < deadline:
            if self._abort().is_set():
                return False, offset
            try:
                with open(log_file, encoding="utf-8", errors="replace") as f:
                    f.seek(offset)
                    new = f.read()
                    offset = f.tell()
            except FileNotFoundError:
                new = ""
            if rx.search(new):
                return True, offset
            time.sleep(0.3)
        return False, offset

    def _backup_world_locked(self, args: dict) -> str:
        """按 BDS 官方热备份流程打包存档: save hold -> 7z -> save resume。
        由「备份」控制词在后台线程调用(持有 console_gate); 无论如何都保证 save resume,
        否则服务器会一直不再存盘。"""
        seven = shutil.which("7z") or shutil.which("7zz")
        if not seven:
            return "系统里找不到 7z 命令, 无法备份(需要先 sudo apt install 7zip)。"
        server_dir = Path(self.cfg.get("mc_server_dir", "/home/jrj/minecraft-bedrock"))
        world = self._world_name(server_dir)
        world_parent = server_dir / "worlds"
        if not (world_parent / world).is_dir():
            return f"找不到世界目录: {world_parent / world}"
        backup_dir = Path(self.cfg.get("backup_dir", "~/mc_backup")).expanduser()
        backup_dir.mkdir(parents=True, exist_ok=True)
        out = backup_dir / f"{world}-{datetime.now():%Y%m%d-%H%M%S}.7z"
        level = self.cfg.get("backup_compression_level", 5)
        log_file = paths.SERVER_LOG_PATH
        try:
            offset = log_file.stat().st_size
        except FileNotFoundError:
            offset = 0
        started = time.time()
        held = False
        try:
            self.bridge.send_command("save hold")
            # BDS 的流程: save hold 只开始异步写盘(回 "Saving..."), 必须周期性地
            # 发 save query 才能问到状态; 直到回 "Data saved. Files are now ready to be copied."
            # 才真正冻结完毕, 此时才能安全拷贝。
            deadline = time.time() + self.cfg.get("backup_hold_timeout_sec", 60)
            while True:
                self.bridge.send_command("save query")
                held, offset = self._await_log(
                    r"Data saved\. Files are now ready", 3, offset)
                if held or self._abort().is_set() or time.time() >= deadline:
                    break
                time.sleep(0.7)
            if not held:
                if self._abort().is_set():
                    return "已中止。"
                return "存档写盘超时, 未开始打包(已恢复世界写入)。"
            log(f"[备份] 世界已冻结, 开始打包 {out.name}")
            pack_started = time.time()
            proc = subprocess.Popen(
                [seven, "a", "-t7z", f"-mx={level}", "-bso0", "-bsp0", str(out), world],
                cwd=str(world_parent), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            timeout = self.cfg.get("backup_timeout_sec", 600)
            timed_out = False
            while proc.poll() is None:
                if self._abort().is_set():
                    proc.terminate()
                    try:
                        proc.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    out.unlink(missing_ok=True)
                    return "已中止(半成品压缩包已删除)。"
                if time.time() - pack_started > timeout:
                    proc.kill()
                    timed_out = True
                    break
                time.sleep(0.5)
            if timed_out:
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    pass
                out.unlink(missing_ok=True)
                return f"打包超过 {timeout}s, 已终止并丢弃半成品。"
            tail = (proc.stdout.read() or "").strip()[-200:] if proc.stdout else ""
            if proc.returncode != 0:
                out.unlink(missing_ok=True)
                return f"7z 打包失败(退出码 {proc.returncode}): {tail}"
            size_mb = out.stat().st_size / 1024 / 1024
            log(f"[备份] 完成 {out} ({size_mb:.0f}MB, 用时 {time.time() - pack_started:.0f}s)")
            return (f"备份完成: {out} ({size_mb:.0f}MB, 打包用时 {time.time() - pack_started:.0f} 秒, "
                    f"总耗时 {time.time() - started:.0f} 秒)。世界写入已恢复。")
        finally:
            # 无论成败都必须恢复存盘, 否则服务器会一直不再保存世界
            self.bridge.send_command("save resume")
            if held:
                self._await_log(r"Changes to the world are resumed", 15, offset)

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
        if mode not in PIN_MODES:
            self._unpin_all()  # 离开创造/执行模式 -> 常加载区域生命周期结束
        p = self._mode_params()
        if mode in CREATIVE_MODES:
            log(f"[模式] {'切换' if was_creative else '进入'}创造模式: {mode} "
                f"(原因: {reason or '未说明'}; 思考强度 {p['effort']})")
            # 从普通进入创造: 第一轮是长思考, 玩家会干等几十秒没反馈。
            # 这是程序行为, 不依赖模型自觉: 开关一翻就直接播报(升档不重复播报)。
            if not was_creative and self.cfg.get("notify_creative_mode", True):
                self._sys("创造模式已开启: 我在深度思考, 可能要等一会儿, 请稍候。")
            return (f"已进入{MODES[mode].label}模式: 从下一次请求起思考强度 {p['effort']}, "
                    "并启用创造工作方式(更长输出、更多工具轮次、更大上下文)。"
                    "完成后记得用 set_mode 切回 normal。")
        log(f"[模式] 切换到 {MODES[mode].label} (原因: {reason or '未说明'})")
        return f"已切换到 {MODES[mode].label} 模式。"
