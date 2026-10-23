"""建造工具: 预览 / 提交 / 撤销 / 状态。

职责边界: 本模块只做「编排」——编译(交给 build.py)、上行分帧、等回包、渲染结果。
世界写入全在行为包里发生; 这里不碰世界。

仅创造模式可见(profiles.TOOLS 的白名单 + 执行层黑名单双重保证)。

依赖方向: bot_build → build/bus/constants/capabilities; 不 import 其它 bot_* 模块。
"""
import json
import time

import capabilities

from . import build
from .bus import Req
from .constants import (
    BUILD_FRAME_CHARS,
    BUILD_TIMEOUT_SEC,
    PACK_PROTO_BUILD,
)
from .paths import log


class BotBuildMixin:
    """_tool_build_* 四个工具。"""

    # ---------- 公共 ----------

    def _build_ready(self) -> str:
        if err := self._require_bus():
            return err
        if getattr(self, "pack_proto", 0) < PACK_PROTO_BUILD:
            return (f"行为包协议过旧(v{getattr(self, 'pack_proto', 0)}), 不支持建造引擎; "
                    "请重载更新后的 viktor_bridge 行为包。")
        return ""

    def _build_name(self, jid: str, name: str = "") -> str:
        """名字只存在 bot 侧(行为包不需要): 预览/状态回显时按 jid 取。"""
        if not hasattr(self, "_build_names"):
            self._build_names = {}
        if name:
            self._build_names[jid] = name
        return self._build_names.get(jid, "")

    def _new_jid(self) -> str:
        if not hasattr(self, "_build_seq"):
            self._build_seq = 0
        self._build_seq += 1
        return f"b{int(time.time()) % 1000000}-{self._build_seq}"

    def _build_upload(self, jid: str, payload: dict) -> int:
        """把建造 payload 分帧上行。

        一帧一次 `screen stuff`: [实测] 单次 stuff 整包 ~768 字节上限,
        ~760 字节的批会被整条丢弃, 而连续 12 次小调用可以全部到达且保序。
        """
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if "\\" in text:  # screen 会解释反斜杠转义; 我们的编码里不应出现
            raise build.BuildError("payload 里出现反斜杠, 无法安全上行(内部错误)")
        frames = [text[i:i + BUILD_FRAME_CHARS]
                  for i in range(0, len(text), BUILD_FRAME_CHARS)]
        for i, frag in enumerate(frames):
            self.bridge.send_command(
                f"scriptevent viktor:build put {jid} {i + 1}/{len(frames)} {frag}")
        return len(frames)

    def _build_await(self, rid: str, cmd: str, jid: str = "") -> Req | None:
        req = self.bus.submit_many([(rid, "build", cmd, BUILD_TIMEOUT_SEC, {})])[0]
        if not self.bus.wait(req, self._abort()):
            if self._abort().is_set() and jid:
                # 让行为包也停下来: 否则它会把剩下的批次写完
                self.bridge.send_command(f"scriptevent viktor:build abort {jid}")
            return None
        return req

    def _build_result(self, name: str, req: Req) -> dict | str:
        if req is None:
            return "已中止。"
        data = self._payload(name, req)
        return data

    # ---------- 工具 ----------

    def _snapshot_fetch(self, box: tuple, origin: tuple, facing: str) -> dict | str:
        """按局部坐标框预取世界快照(dense palette+RLE), 供程序读地形。"""
        lx0, ly0, lz0, lx1, ly1, lz1 = box
        corners = [build.to_world(origin, facing, u, v, w)
                   for u in (lx0, lx1) for v in (ly0, ly1) for w in (lz0, lz1)]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        zs = [c[2] for c in corners]
        wb = (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))
        volume = ((wb[3] - wb[0] + 1) * (wb[4] - wb[1] + 1) * (wb[5] - wb[2] + 1))
        if volume > build.MAX_VOLUME:
            return f"scan 范围 {volume} 格超过上限 {build.MAX_VOLUME}, 请缩小"
        rid = self.bus.next_id()
        cmd = (f"scriptevent viktor:snapshot {rid} {wb[0]} {wb[1]} {wb[2]}"
               f" {wb[3]} {wb[4]} {wb[5]} overworld")
        req = self._build_await(rid, cmd)
        data = self._build_result("snapshot", req)
        return data

    def _tool_build_preview(self, args: dict) -> str:
        if err := self._build_ready():
            return err
        program = str(args.get("program") or "").strip()
        if not program:
            return "缺少 program(建造程序正文)。"
        origin = args.get("origin") or []
        facing = str(args.get("facing") or "south").lower()
        name = str(args.get("name") or "").strip()[:40]
        symmetry = str(args.get("symmetry") or "").strip() or None
        snapshot = None
        scan = args.get("scan")
        if scan:
            try:
                box = tuple(int(v) for v in scan)
                assert len(box) == 6
            except (TypeError, ValueError, AssertionError):
                return "scan 需要 6 个整数 [x1, y1, z1, x2, y2, z2](局部坐标框)。"
            snap = self._snapshot_fetch(box, tuple(int(v) for v in origin), facing)
            if isinstance(snap, str):
                return snap
            snapshot = snap
        try:
            payload, stats = build.compile_build(
                program, origin, facing, build.block_ids() or capabilities.item_ids(),
                snapshot, symmetry)
        except build.BuildError as e:
            return f"建造程序编译失败: {e}"
        jid = self._new_jid()
        try:
            frames = self._build_upload(jid, payload)
        except build.BuildError as e:
            return str(e)
        rid = self.bus.next_id()
        req = self._build_await(rid, f"scriptevent viktor:build preview {rid} {jid}", jid)
        data = self._build_result("build_preview", req)
        if isinstance(data, str):
            return data
        data["name"] = self._build_name(jid, name)
        log(f"[建造] 预览 {jid} {name} {stats['size']} {stats['cells']}格 "
            f"{frames}帧 {stats['payload_bytes']}B")
        return self._render_build_preview(jid, data, stats)

    def _render_build_preview(self, jid: str, data: dict, stats: dict) -> str:
        b = data.get("bounds") or {}
        frm, to = b.get("from"), b.get("to")
        diff = data.get("diff") or {}
        size = stats["size"]
        cells = data.get("cells") or stats["cells"]
        out = []
        title = f"「{data['name']}」" if data.get("name") else ""
        where = f"({frm[0]}, {frm[1]}, {frm[2]})..({to[0]}, {to[1]}, {to[2]})" if frm else "—"
        out.append(f"预览 {jid} {title} 包围盒 {where} = {size[0]}×{size[1]}×{size[2]}, "
                   f"将写入 {cells} 格, {data.get('paletteSize', stats['palette'])} 种方块")
        out.append(f"差异: 新放置 {diff.get('place', 0)} 格 / 覆盖 {diff.get('replace', 0)} 格 / "
                   f"已正确 {diff.get('noop', 0)} 格 / 未加载 {diff.get('unloaded', 0)} 格")
        out.append(f"执行计划: {(data.get('plan') or {}).get('boxes', '?')} 个批量填充"
                   f"(程序 {stats['ops']} 个形状)")
        chk = stats.get("checks") or {}
        sym = chk.get("symmetry")
        if sym:
            if sym["mismatch"] == 0:
                out.append(f"对称: {sym['axis']} 轴(中心 {sym['center']}) {sym['checked']} 格全对称")
            else:
                out.append(f"⚠ 对称: {sym['axis']} 轴(中心 {sym['center']}) 有 {sym['mismatch']} 处不对称")
                for u, v, w, mine, other in sym["samples"][:4]:
                    out.append(f"    ({u}, {v}, {w}) 是 {mine}, 镜像处是 {other}")
        fl = chk.get("floating") or {}
        if fl.get("checked"):
            if fl.get("count"):
                out.append(f"⚠ 悬空: {fl['count']} 格下方与四周都没有支撑(如属设计请忽略)")
                for u, v, w, name in fl["samples"][:4]:
                    out.append(f"    ({u}, {v}, {w}) {name}")
        if stats.get("snapshot_unloaded"):
            out.append(f"⚠ 快照里有 {stats['snapshot_unloaded']} 格未加载, "
                       "这些列的 api.height 不可靠(必要时缩小 scan 或先 pin_region)")
        for w in data.get("warnings") or []:
            out.append(f"⚠ {w}")
        samples = data.get("samples") or {}
        if samples.get("protected"):
            out.append("受保护方块(会被跳过): " +
                       ", ".join(f"({x},{y},{z}) {t}" for x, y, z, t in samples["protected"][:4]))
        if samples.get("unsupported"):
            out.append("多格方块(请改成普通方块): " + ", ".join(samples["unsupported"][:6]))
        if diff.get("unloaded"):
            out.append("提示: 未加载的格子既不会写也不会被校验; 远处施工先 pin_region 覆盖。")
        out.append(f"确认无误后调用 build_commit(operation_id=\"{jid}\"); "
                   "要改就先改程序再 build_preview。")
        return "\n".join(out)

    def _tool_build_commit(self, args: dict) -> str:
        if err := self._build_ready():
            return err
        jid = str(args.get("operation_id") or "").strip()
        if not jid:
            return "缺少 operation_id(用 build_preview 返回的那个)。"
        rid = self.bus.next_id()
        req = self._build_await(rid, f"scriptevent viktor:build commit {rid} {jid}", jid)
        data = self._build_result("build_commit", req)
        if isinstance(data, str):
            return data
        log(f"[建造] 提交 {jid} 写入 {data.get('changed')} 格, "
            f"{data.get('boxes')} 批, {data.get('ms')}ms, 校验 {data.get('verify')}")
        return self._render_build_commit(jid, data)

    def _render_build_commit(self, jid: str, data: dict) -> str:
        out = []
        if data.get("undoOf"):
            out.append(f"已撤销 {data['undoOf']}: 还原 {data.get('changed', 0)} 格, "
                       f"{data.get('boxes', 0)} 批, {data.get('ms', 0)}ms")
        else:
            out.append(f"提交 {jid}: 写入 {data.get('changed', 0)} 格, "
                       f"{data.get('boxes', 0)} 批批量填充, {data.get('ms', 0)}ms")
            if data.get("noop"):
                out.append(f"(其中 {data['noop']} 格本来就对, 已跳过不写)")
            if data.get("skippedUnloaded"):
                out.append(f"⚠ {data['skippedUnloaded']} 格因未加载被跳过(没有写)")
        if data.get("failed"):
            out.append(f"⚠ 有 {data['failed']} 批失败(方块 ID 或状态非法/区块未加载)")
        if data.get("aborted"):
            out.append("⚠ 被中止: 只写了一部分, 可用 build_undo 还原")
        v = data.get("verify") or {}
        mm = v.get("mismatch", 0)
        if mm == 0:
            out.append("校验: 全部正确(mismatch 0)"
                       + (f"; {v.get('unloaded')} 格未加载, 未参与校验" if v.get("unloaded") else ""))
        else:
            out.append(f"校验: {mm} 格不符(空洞 {v.get('holes', 0)}, 放错 {v.get('wrong', 0)}"
                       + (f", 未加载 {v.get('unloaded')}" if v.get("unloaded") else "") + ")")
            for x, y, z, t in (v.get("samples") or [])[:8]:
                out.append(f"  ({x}, {y}, {z}) 实际是 {t}")
            out.append("按上面的坐标写一个小补丁程序, 再 build_preview/build_commit 一次。")
        if data.get("undoDepth"):
            out.append(f"(可撤销, 撤销栈 {data['undoDepth']} 个)")
        return "\n".join(out)

    def _tool_build_undo(self, args: dict) -> str:
        if err := self._build_ready():
            return err
        jid = str(args.get("operation_id") or "").strip() or "-"
        rid = self.bus.next_id()
        req = self._build_await(rid, f"scriptevent viktor:build undo {rid} {jid}", jid)
        data = self._build_result("build_undo", req)
        if isinstance(data, str):
            return data
        log(f"[建造] 撤销 {data.get('undoOf')} 还原 {data.get('changed')} 格")
        return self._render_build_commit(jid, data)

    def _tool_build_status(self, args: dict) -> str:
        if err := self._build_ready():
            return err
        rid = self.bus.next_id()
        req = self._build_await(rid, f"scriptevent viktor:build list {rid}")
        data = self._build_result("build_status", req)
        if isinstance(data, str):
            return data
        ops = data.get("ops") or []
        undo = data.get("undo") or []
        if not ops and not undo:
            return "当前没有暂存或可撤销的建造操作。"
        out = []
        if ops:
            out.append("暂存的操作:")
            for o in ops:
                b = o.get("bounds") or {}
                where = (f"({b['from'][0]},{b['from'][1]},{b['from'][2]}).."
                         f"({b['to'][0]},{b['to'][1]},{b['to'][2]})") if b.get("from") else "—"
                state = "已提交" if o.get("committed") else ("待提交" if o.get("complete") else "上传中")
                nm = o.get("name") or self._build_name(o.get("jid", ""))
                out.append(f"  {o.get('jid')} 「{nm or '未命名'}」 {where} "
                           f"{o.get('cells', 0)} 格 {state}")
        if undo:
            out.append("可撤销: " + ", ".join(
                f"{u.get('jid')}「{u.get('name') or self._build_name(u.get('jid', '')) or '未命名'}」"
                for u in undo))
        return "\n".join(out)
