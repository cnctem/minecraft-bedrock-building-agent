"""控制面: 停止/清空/压缩/状态/备份/计划模式/恢复会话/一次性对话等硬编码控制词(不走模型)。

依赖方向: bot_control → session/profiles/constants/paths/capabilities; 不 import 其它 bot_* 模块。
"""
import json
import re
import subprocess
import threading
from pathlib import Path

import capabilities

from . import paths
from .constants import MODE_NORMAL, MODE_ONESHOT, MODE_PLAN, ONESHOT_TRIGGER
from .paths import log
from .profiles import MODES
from .prompts import COMPACT_NOTE
from .session import OneShotContext, Session, memory_note

# 工具转发里永远不外显的“对话类”调用:
# send_chat_message 的内容本身就是游戏内发言(再转一遍“[工具] send_chat_message …”是重复),
# stay_silent 只是内部决定(显示出来反而暴露“维克托刚判断不该说话”, 纯噪音)。
_NO_FORWARD_TOOLS = frozenset({"send_chat_message", "stay_silent"})


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
        连工具内部的轮询等待也一并打断; 备份不可中止(只回提示, 不置位任何标志)。"""
        with self.cv:
            busy = self.agent_busy or bool(self.pending)
            self.pending.clear()  # 尚未开始处理的消息也一并作废
        if busy:
            self.abort.set()
            log(f"[强制停止] {name} 要求强制停止, 已向运行中的任务发出中止信号")
            msg = "已强制停止当前任务。"
        elif self._backup_running:
            log(f"[强制停止] {name} 要求强制停止, 但备份不可中止")
            msg = "备份正在进行中, 无法中止, 请稍候。"
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
        """工具转发预览(前40字): run_server_command 给命令; ptc 给子工具名; 其余给 名+参数。
        发言/沉默类调用不外显: 直接调用返回空; ptc 里把它们过滤掉, 只剩它们也不外显。"""
        fn = tc.get("function") or {}
        name = fn.get("name") or "?"
        if name in _NO_FORWARD_TOOLS:
            return ""
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
            subs = [s for s in subs if s and s not in _NO_FORWARD_TOOLS]
            if not subs:
                return ""
            body = "ptc " + ",".join(subs)
        else:
            body = f"{name} {raw}".strip() if raw else name
        return re.sub(r"\s+", " ", body).strip()[:40]

    def _forward_tool(self, tc: dict):
        """工具转发(开关): 每次工具调用以 [工具]+前40字 发到聊天, 仅供观察, 不进上下文。"""
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

    def _on_compact(self, name: str):
        """玩家发来完全匹配的“压缩”: 把上下文压缩成对话记录(只保留玩家消息与游戏内发言),
        旧会话落盘留档、开新会话。与「清空」同一并发规则: 有任务在跑(或队列有待处理消息)
        时压缩无效——不中止任务、不改上下文, 只回一句提示。控制词不进上下文。"""
        with self.cv:
            busy = self.agent_busy or bool(self.pending)
        if busy:
            log(f"[压缩] {name} 要求压缩, 但有任务在进行, 压缩无效")
            self._sys("现在有任务正在进行, 压缩无效。请先发「停止」(做完当前这一步再停)"
                      "或「强制停止」(立即中止), 停下来后再压缩。")
            return
        stats = self._compact_session()
        log(f"[压缩] {name} 要求压缩上下文: 保留玩家消息 {stats['kept_user']} 条、"
            f"发言 {stats['kept_speech']} 条, 移除 {stats['dropped']} 条过程记录")
        self._sys(f"上下文已压缩(保留 {stats['kept_user']} 条玩家消息 / "
                  f"{stats['kept_speech']} 条发言; 移除 {stats['dropped']} 条过程记录)。")

    def _build_compact_messages(self) -> tuple[list[dict], dict]:
        """组装压缩后的新会话消息: 记忆/技能书/当前模式三条开场注记 + 保留的对话 + 压缩注记。
        只组装不提交(自动溢出时先用它试算体积)。"""
        kept, stats = Session.compact(self.session.messages)
        msgs: list[dict] = [{"role": "system", "content": memory_note()}]
        skills = capabilities.skills_note()
        if skills:
            msgs.append({"role": "system", "content": skills})
        msgs.append({"role": "system", "content": self._mode_note()})
        msgs.extend(kept)
        msgs.append({"role": "system", "content": COMPACT_NOTE})
        return msgs, stats

    def _apply_compact(self, msgs: list[dict], stats: dict) -> None:
        """压缩落盘 + 换新会话: 旧会话 dump 成 compact-*.jsonl 留档(不参与“恢复会话”),
        新会话获得新 id 并装载压缩后的消息。模式/常加载/玩家名单/队列都不动。"""
        old = self.session
        if old is not None:
            old.dump(tag="compact")
            log(f"=== 会话 #{old.id} 结束(压缩留档: 保留玩家消息 {stats['kept_user']} 条、"
                f"发言 {stats['kept_speech']} 条, 移除 {stats['dropped']} 条过程记录) ===")
        self.session_counter += 1
        self.session = Session(self.session_counter)
        self.session.messages = msgs
        self._context_warn_level = 0  # 压缩后上下文变短, 占用提醒档位复位
        log(f"=== 会话 #{self.session.id} 开始(由压缩重建, 消息 {len(msgs)} 条) ===")

    def _compact_session(self) -> dict:
        """压缩当前会话(组装 + 提交), 返回统计。仅供“压缩”控制词直接调用。"""
        msgs, stats = self._build_compact_messages()
        self._apply_compact(msgs, stats)
        return stats

    # ---------- 状态 / 备份(硬编码控制词, 不走模型) ----------

    def _on_status(self, name: str):
        """玩家发来完全匹配的“状态”: 播报服务器进程/负载与在线玩家(≤2 条 [系统])。
        纯读操作, 任何时候(任务进行中/备份中)都可触发; 永不抛异常。"""
        parts = []
        try:
            pids = subprocess.run(["pgrep", "-x", "bedrock_server"],
                                  capture_output=True, text=True).stdout.split()
            if pids:
                out = subprocess.run(
                    ["ps", "-o", "%cpu=,%mem=,rss=,etime=", "-p", pids[0]],
                    capture_output=True, text=True).stdout.split()
                if len(out) == 4:
                    cpu, mem, rss, etime = out
                    parts.append(f"bedrock_server(PID {pids[0]}): CPU {cpu}%, "
                                 f"内存 {int(rss) // 1024}MB, 已运行 {etime}")
            if not parts:
                parts.append("警告: 找不到 bedrock_server 进程")
        except Exception as e:
            parts.append(f"警告: 进程状态读取失败({e})")
        try:
            with open("/proc/loadavg") as f:
                parts.append("负载 " + "/".join(f.read().split()[:3]))
        except Exception:
            pass  # 读不到负载(如非 Linux)就不报, 不影响其余状态
        players = sorted(self.players)
        log(f"[状态] {name} 查询服务器状态: {'; '.join(parts)}; 在线 {len(players)} 人")
        self._sys("; ".join(parts))
        self._sys(f"在线玩家 {len(players)} 人" + (f": {', '.join(players)}" if players else ""))

    def _on_backup(self, name: str):
        """玩家发来完全匹配的“备份”: 触发存档热备份(后台线程执行, 不可中止)。
        与「清空」同一并发规则: 有任务在跑(或队列有待处理消息)时无效——
        只回一句提示; 已在备份中则提示稍候。控制词不进上下文。"""
        with self.cv:
            busy = self.agent_busy or bool(self.pending)
        if self._backup_running:
            self._sys("备份正在进行中, 请稍候。")
            return
        if busy:
            log(f"[备份] {name} 要求备份, 但有任务在进行, 备份无效")
            self._sys("现在有任务正在进行, 备份无效。请先发「停止」(做完当前这一步再停)"
                      "或「强制停止」(立即中止), 停下来后再备份。")
            return
        log(f"[备份] {name} 触发存档热备份")
        self._backup_running = True
        threading.Thread(target=self._run_backup, daemon=True).start()

    def _run_backup(self):
        """备份工作线程: 播报开始 → save hold → 7z → save resume → 播报结果。
        不可中止: 线程内装一枚永不置位的 abort 事件, 「强制停止」打断不了备份;
        结束时复位 _backup_running 并唤醒 worker(备份期间消息只排队, 备份完再处理)。"""
        self._tls.abort = threading.Event()  # 永不置位 = 备份不可中止
        self._sys("正在备份存档, 服务器会卡几十秒, 请稍候…")
        try:
            with self.console_gate:
                out = self._backup_world_locked({})
        except Exception as e:
            log(f"[备份] 出错: {e}")
            out = f"出错: {e}"
        finally:
            try:
                del self._tls.abort
            except AttributeError:
                pass
            self._backup_running = False
            with self.cv:
                self.cv.notify_all()
        if out.startswith("备份完成"):
            self._sys(out)
        else:
            log(f"[备份] 未完成: {out}")
            self._sys(f"备份失败: {out}")

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
        # 重启后别把“正在对话”误判成冷启动: 从历史里找回最近一次对谁说过话(时间用 mtime 近似)
        self._seed_dialog_from(msgs, p.stat().st_mtime)
        for m in reversed(msgs):
            if m.get("role") == "system" and (m.get("content") or "").startswith("# 当前模式: "):
                label = m["content"].split("\n", 1)[0].split(": ", 1)[1].strip()
                for name, mode in MODES.items():
                    if mode.label == label:
                        self.mode = name
                        break
                break
        # 技能目录可能在会话落盘后才变动: 恢复时若最新技能清单与旧的不同, 在末尾补一条。
        # 只追加、不改前缀 -> 前缀缓存仍命中; 否则新增技能书要等到下次“清空/新会话”才可见。
        note = capabilities.skills_note()
        if note:
            old = next((m.get("content") or "" for m in reversed(msgs)
                        if m.get("role") == "system"
                        and (m.get("content") or "").startswith("# 可用技能书(skill)")), "")
            if old.strip() != note.strip():
                self.session.add_system(note)
                log("[恢复] 技能清单已更新, 末尾补注入一条")
        # 关键: 恢复的是"已完成的历史"。不点明的话, 模型会把这轮对话当成还没做完的任务,
        # 下一句话就把之前的工具调用整批重跑一遍(玩家看到 [工具] 全被重新转发)。
        note = ("# 会话已恢复(重启)\n"
                "以上是重启之前的对话记录, 其中的工具调用都已经真实执行过、世界状态也已落定。\n"
                "不要重跑、不要补做、不要重新转发上面出现过的工具调用。\n"
                "从现在起只处理玩家新说的话; 需要现场状态时用查询工具重新确认, "
                "不要凭历史推断当前世界。")
        if not any((m.get("content") or "").startswith("# 会话已恢复")
                   for m in reversed(msgs) if m.get("role") == "system"):
            self.session.add_system(note)
            log("[恢复] 已追加「历史已执行过, 不要重跑」注记")
        log(f"[恢复] 从 {p.name} 灌回 {len(msgs)} 条消息, 模式={MODES[self.mode].label}")

    @staticmethod
    def _dump_has_conversation(path: Path) -> bool:
        """落盘文件里是否有实际对话(user/assistant)。历史遗留的空会话(只有系统注记)不参与恢复。"""
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    role = json.loads(line).get("role")
                except ValueError:
                    continue
                if role in ("user", "assistant"):
                    return True
        except OSError:
            return False
        return False

    def _on_restore_session(self, name: str):
        """硬编码控制词"恢复会话": 把最近一次落盘的会话灌回(程序处理, 不走模型)。"""
        with self.cv:
            busy = self.agent_busy or bool(self.pending)
        if busy:
            self._sys("现在有任务在进行, 请先「停止」或等它做完, 再恢复会话。")
            return
        dumps = [p for p in sorted(paths.SESSION_DIR.glob("session-*.jsonl"),
                                   key=lambda p: p.stat().st_mtime, reverse=True)
                 if self._dump_has_conversation(p)]
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
        if self._backup_running:
            log(f"[一次性] {name} 触发被拒: 备份进行中")
            self._sys("备份正在进行中, 请稍后再发一次性对话。")
            return
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
