"""控制面: 停止/清空/计划模式/恢复会话/一次性对话等硬编码控制词(不走模型)。

依赖方向: bot_control → session/profiles/constants/paths/capabilities; 不 import 其它 bot_* 模块。
"""
import json
import re
import threading
from pathlib import Path

import capabilities

from . import paths
from .constants import MODE_NORMAL, MODE_ONESHOT, MODE_PLAN, ONESHOT_TRIGGER
from .paths import log
from .profiles import MODES
from .session import OneShotContext, Session, memory_note


class BotControlMixin:
    """控制词 / 计划模式 / 恢复会话 / 一次性对话。"""

    def _on_soft_stop(self, name: str):
        """玩家发来完全匹配的“停止”: 到安全点停止, 不经过模型。
        不打断正在执行的工具(当前步骤做完、工具往返闭合), 在下一次工具调用前停。"""
        with self.cv:
            busy = self.agent_busy or bool(self.pending)
            self.pending.clear()  # 尚未开始处理的消息一并作废, 不开启新任务
        if busy:
            self.soft_abort.set()
            log(f"[停止] {name} 要求到安全点停止, 已置位标志")
            msg = ("收到, 我把当前这一步做完就停。反悔请发「不停止」, "
                   "需要立即中止请发「强制停止」。")
        else:
            log(f"[停止] {name} 要求停止, 但当前没有运行中的任务")
            msg = "当前没有正在执行的任务。"
        self._sys(msg)

    def _on_force_stop(self, name: str):
        """玩家发来完全匹配的“强制停止”: 立即中止运行中的任务, 不经过模型。
        连工具内部的轮询等待也一并打断。"""
        with self.cv:
            busy = self.agent_busy or bool(self.pending)
            self.pending.clear()  # 尚未开始处理的消息也一并作废
        if busy:
            self.abort.set()
            log(f"[强制停止] {name} 要求强制停止, 已向运行中的任务发出中止信号")
            msg = "已强制停止当前任务。"
        else:
            log(f"[强制停止] {name} 要求强制停止, 但当前没有运行中的任务")
            msg = "当前没有正在执行的任务。"
        self._sys(msg)

    def _say_later(self, text: str, delay: float = 5.0, system: bool = False):
        """延迟播报: 进服瞬间客户端尚未就绪, 立即 tellraw 会丢消息(实测)。"""
        t = threading.Timer(delay, lambda: self.bridge.say_as_viktor(
            text, self.cfg["reply_chunk_len"], self._reply_max_chunks(), system=system))
        t.daemon = True
        t.start()

    def _sys(self, text: str):
        """发送程序生成(非模型)的系统提示, 带 [系统] 前缀, 让玩家区分这不是 AI 回复。"""
        self.bridge.say_as_viktor(text, self.cfg["reply_chunk_len"],
                                  self._reply_max_chunks(), system=True)

    def _on_body_toggle(self, name: str, on: bool):
        """完全匹配的「正文开/正文关」: 模型正文是否以 [正文] 前缀转发到聊天。
        只是显示开关, 不中止任务、不进上下文, 任何玩家可切换。"""
        self.body_forward = on
        log(f"[转发] {name} {'开启' if on else '关闭'}正文转发")
        self._sys("正文转发已开启: 模型正文会以 [正文] 前缀发到聊天。" if on
                  else "正文转发已关闭。")

    def _on_tool_toggle(self, name: str, on: bool):
        """完全匹配的「工具开/工具关」: 工具调用是否以 [工具] 前缀转发到聊天。"""
        self.tool_forward = on
        log(f"[转发] {name} {'开启' if on else '关闭'}工具转发")
        self._sys("工具转发已开启: 工具调用会以 [工具] 前缀发到聊天。" if on
                  else "工具转发已关闭。")

    def _forward_body(self, text: str):
        """正文转发(开关): 模型正文以 [正文] 前缀发到聊天, 仅供观察, 不进上下文。"""
        if self.body_forward and text and text.strip():
            self.bridge.say_side("[正文]", text, self.cfg["reply_chunk_len"],
                                 self._reply_max_chunks())

    @staticmethod
    def _tool_preview(tc: dict) -> str:
        """工具转发预览(前20字): run_server_command 给命令; ptc 给子工具名; 其余给 名+参数。"""
        fn = tc.get("function") or {}
        name = fn.get("name") or "?"
        raw = fn.get("arguments") or ""
        try:
            args = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except Exception:
            args = {}
        if name == "run_server_command" and isinstance(args, dict):
            body = str(args.get("command", ""))
        elif name == "ptc" and isinstance(args, dict):
            subs = [capabilities._ptc_name(c) for c in (args.get("calls") or [])
                    if isinstance(c, dict)]
            body = "ptc " + ",".join(s for s in subs if s)
        else:
            body = f"{name} {raw}".strip() if raw else name
        return re.sub(r"\s+", " ", body).strip()[:20]

    def _forward_tool(self, tc: dict):
        """工具转发(开关): 每次工具调用以 [工具]+前20字 发到聊天, 仅供观察, 不进上下文。"""
        if self.tool_forward:
            preview = self._tool_preview(tc)
            if preview:
                self.bridge.say_side("[工具]", preview, self.cfg["reply_chunk_len"], 1)

    def _on_no_stop(self, name: str):
        """玩家发来完全匹配的“不停止”: 撤销还未生效的停止/强制停止, 不经过模型。
        已生效的(任务已停下)无法撤销。"""
        revoked = []
        if self.agent_busy and self._soft_abort().is_set():
            self.soft_abort.clear()
            revoked.append("停止")
        if self.agent_busy and self._abort().is_set():
            self.abort.clear()
            revoked.append("强制停止")
        if revoked:
            log(f"[不停止] {name} 撤销了尚未生效的{'、'.join(revoked)}")
            msg = f"已撤销尚未生效的{'、'.join(revoked)}指令, 任务继续。"
        else:
            log(f"[不停止] {name} 要求不停止, 但没有尚未生效的停止指令")
            msg = "当前没有尚未生效的停止指令。"
        self._sys(msg)

    def _on_clear(self, name: str):
        """玩家发来完全匹配的“清空”: 丢弃整个会话上下文, 任何玩家都可触发。
        只能在停止状态下清空: 有任务在跑(或队列有待处理消息)时清空无效——
        不中止任务、不清上下文, 只回一句提示。控制词不进上下文。"""
        with self.cv:
            busy = self.agent_busy or bool(self.pending)
        if busy:
            log(f"[清空] {name} 要求清空, 但有任务在进行, 清空无效")
            self._sys("现在有任务正在进行, 清空无效。请先发「停止」(做完当前这一步再停)"
                      "或「强制停止」(立即中止), 停下来后再清空。")
            return
        n = self._reset_session()
        log(f"[清空] {name} 要求清空上下文, 已完整初始化新会话(丢弃 {n} 条消息)")
        self._sys(f"上下文已清空(丢弃 {n} 条消息)。发送「恢复会话」可找回刚才的对话。")

    def _reset_session(self) -> int:
        """完整初始化: 结束当前会话(落盘、复位任何非普通模式)并开启一个全新会话。
        玩家发“清空”与“玩家数 0→1”走同一套初始化; 返回被丢弃的消息条数。"""
        n = len(self.session.messages) if self.session else 0
        self._end_session()
        self._start_session()
        return n

    def resume_session(self, path: str) -> None:
        """重启后把一份已落盘的会话上下文灌回当前会话。
        旧数据里带 tool_calls 的 assistant 可能缺 reasoning_content(历史 bug), 而 DeepSeek
        思考模式 + tools 要求每条 assistant 都带该字段, 否则 400; 这里统一补空串。
        当前模式从最后一条模式注记('# 当前模式: <label>')推断。"""
        p = Path(path)
        msgs = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()
                if line.strip()]
        for m in msgs:
            if m.get("role") == "assistant" and "reasoning_content" not in m:
                m["reasoning_content"] = ""
        self.session_counter += 1
        self.session = Session(self.session_counter)
        self.session.messages = msgs
        for m in reversed(msgs):
            if m.get("role") == "system" and (m.get("content") or "").startswith("# 当前模式: "):
                label = m["content"].split("\n", 1)[0].split(": ", 1)[1].strip()
                for name, mode in MODES.items():
                    if mode.label == label:
                        self.mode = name
                        break
                break
        log(f"[恢复] 从 {p.name} 灌回 {len(msgs)} 条消息, 模式={MODES[self.mode].label}")

    def _on_restore_session(self, name: str):
        """硬编码控制词"恢复会话": 把最近一次落盘的会话灌回(程序处理, 不走模型)。"""
        with self.cv:
            busy = self.agent_busy or bool(self.pending)
        if busy:
            self._sys("现在有任务在进行, 请先「停止」或等它做完, 再恢复会话。")
            return
        dumps = sorted(paths.SESSION_DIR.glob("session-*.jsonl"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if not dumps:
            self._sys("没有可恢复的历史会话。")
            return
        path = dumps[0]
        try:
            self.resume_session(str(path))
        except Exception as e:
            log(f"[恢复] 失败: {e}")
            self._sys("恢复会话失败, 请稍后再试。")
            return
        self._sys(f"已恢复上一段会话({path.name}, {len(self.session.messages)} 条消息, "
                  f"模式 {MODES[self.mode].label})。")

    # ---------- 计划模式(硬编码控制词, 程序处理, 不走模型) ----------

    def _program_set_mode(self, mode: str, name: str) -> None:
        """程序侧切模式: 设置模式并追加一条模式注记(append-only, 不改前缀)。"""
        self.mode = mode
        if self.session:
            self.session.add_system(self._mode_note())
        log(f"[计划] {name} 切换到 {MODES[mode].label} 模式")

    def _on_plan_mode(self, name: str):
        """硬编码控制词"计划模式": 任何玩家可进入。不重置上下文(以便利用既有上下文,
        如之前用创造模式造过什么), 进入后追加模式注记并 nudge 一次让 Agent 主动引导。"""
        with self.cv:
            busy = self.agent_busy or bool(self.pending)
        if busy:
            self._sys("现在有任务在进行, 请先发「停止」或等它做完, 再进入计划模式。")
            return
        if self.mode == MODE_PLAN:
            self._sys("已在计划模式中, 发送「退出计划」可退出。")
            return
        if not self.session:
            self.players.add(name)
            self._start_session()
        self._program_set_mode(MODE_PLAN, name)
        self._sys("已切换到计划模式, 发送「退出计划」可退出计划模式。")
        # 让 Agent 主动开口引导(无用户消息, 仅以 nudge 触发一次模型回合)
        with self.cv:
            self._nudge = True
            self.cv.notify()

    def _on_exit_plan(self, name: str):
        """硬编码控制词"退出计划": 从计划模式回到普通模式(程序处理, 不走模型)。"""
        with self.cv:
            busy = self.agent_busy or bool(self.pending)
        if busy:
            self._sys("我正在回复, 请稍后再发「退出计划」。")
            return
        if self.mode != MODE_PLAN:
            self._sys("当前不在计划模式。")
            return
        self._program_set_mode(MODE_NORMAL, name)
        self._sys("已退出计划模式, 回到普通模式。")

    # ---------- 一次性对话(可并发, 与主对话完全隔离) ----------

    def _handle_oneshot_line(self, name: str, stripped: str) -> None:
        """处理 "1 ..." 触发。先剥掉前缀再交给一次性线程; 前缀本身不进任何上下文。"""
        body = ONESHOT_TRIGGER.sub("", stripped, count=1).strip()
        if not body:
            self._sys("一次性对话要在“1 ”后面写清要做的事, 例如: 1 记住我现在的位置。")
            return
        if body == "强制停止":
            self._on_oneshot_force_stop(name)
            return
        self._spawn_oneshot(name, body)

    def _spawn_oneshot(self, name: str, body: str) -> None:
        with self._oneshot_lock:
            if self._oneshot_active >= self.oneshot_max_concurrent:
                full, active = True, self._oneshot_active
            else:
                full = False
                self._oneshot_active += 1
                active = self._oneshot_active
        if full:
            log(f"[一次性] {name} 触发被拒: 已有 {active} 个在跑"
                f"(上限 {self.oneshot_max_concurrent})")
            self._sys("现在一次性对话有点多, 请稍后再发。")
            return
        log(f"[一次性] {name} 触发: {body}")
        threading.Thread(target=self._run_oneshot, args=(name, body), daemon=True).start()

    def _on_oneshot_force_stop(self, name: str) -> None:
        """"1 强制停止": 停止全部正在进行的一次性对话(不走模型, 不进任何上下文)。"""
        with self._oneshot_lock:
            ctxs = list(self._active_oneshots.values())
        for c in ctxs:
            c.abort.set()
        if ctxs:
            log(f"[一次性] {name} 要求强制停止, 已向 {len(ctxs)} 个一次性对话发出中止信号")
            msg = f"已强制停止 {len(ctxs)} 个一次性对话。"
        else:
            log(f"[一次性] {name} 要求强制停止, 但没有正在进行的一次性对话")
            msg = "当前没有正在进行的一次性对话。"
        self._sys(msg)

    def _run_oneshot(self, name: str, body: str) -> None:
        """一次性对话工作线程: 独立 context, 结束后落盘 logs/oneshot/, 绝不碰主会话。"""
        with self._oneshot_lock:
            self._oneshot_counter += 1
            oid = self._oneshot_counter
            ctx = OneShotContext(oid, name, body)
            self._active_oneshots[oid] = ctx
        self._tls.oneshot = True
        self._tls.abort = ctx.abort
        self._tls.soft_abort = ctx.soft_abort
        self._tls.session = ctx.session
        self._tls.mode = MODE_ONESHOT
        # 一次性会话的注记(记忆 + 本模式行为与数值), 都写在第一条用户消息之前
        ctx.session.add_system(memory_note())
        skills = capabilities.skills_note()
        if skills:
            ctx.session.add_system(skills)
        ctx.session.add_system(self._mode_note())
        ctx.session.add_user(f"{name}: {body}")
        log(f"=== 一次性对话 #{oid} 开始 (玩家: {name}) ===")
        reply, spoke = "", False
        try:
            reply, spoke = self.call_api()
        except Exception as e:
            log(f"[一次性#{oid}] 出错: {e}")
        finally:
            try:
                if not spoke and not ctx.abort.is_set():
                    # 兜底: 模型把回复写在正文(玩家看不到)时必须补发; 程序兜底文本带 [系统]
                    if reply.strip():
                        self.bridge.say_as_viktor(reply, self.cfg["reply_chunk_len"],
                                                  self._reply_max_chunks())
                    else:
                        self._sys("抱歉, 这次一次性请求没算完, 请拆小后再发一次。")
                ctx.session.add_assistant(reply or "(已通过工具发言)")
            except Exception as e:
                log(f"[一次性#{oid}] 收尾发言失败: {e}")
            ctx.session.dump(paths.ONESHOT_DIR, tag="oneshot")
            with self._oneshot_lock:
                self._active_oneshots.pop(oid, None)
                self._oneshot_active = max(0, self._oneshot_active - 1)
            for attr in ("oneshot", "abort", "soft_abort", "session", "mode"):
                try:
                    delattr(self._tls, attr)
                except AttributeError:
                    pass
            log(f"=== 一次性对话 #{oid} 结束 (消息 {len(ctx.session.messages)} 条, "
                f"abort={ctx.abort.is_set()}) ===")
