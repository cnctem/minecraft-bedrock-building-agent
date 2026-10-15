"""Bot 核心: 构造、请求上下文(_tls 回落)、会话生命周期、待处理消息队列。

依赖方向: bot_core → bridge/bus/session/schemas/profiles/constants/paths; 不 import 其它 bot_* 模块。
与其它职责模块只通过 self.* 方法协作(MRO 组合), 模块之间没有互相 import。
"""
import json
import os
import threading
import time

import capabilities

from . import paths
from .bridge import ScreenBridge
from .bus import ServerBus
from .constants import CREATIVE_MODES, MODE_NORMAL
from .paths import log
from .profiles import MODES
from .schemas import (
    GET_BLOCK_SCHEMA,
    GET_HAND_SCHEMA,
    GET_POSITION_SCHEMA,
    PIN_REGION_SCHEMA,
    RUN_COMMAND_SCHEMA,
    SCAN_BLOCKS_SCHEMA,
    SEND_CHAT_SCHEMA,
    SET_MODE_SCHEMA,
)
from .session import OneShotContext, Session, memory_note


class BotCoreMixin:
    """构造 / 请求上下文 / 会话生命周期 / 待处理队列。"""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.bridge = ScreenBridge(cfg["screen_session"])
        self.bus = ServerBus(self.bridge, paths.SERVER_LOG_PATH,
                             cfg.get("bus_reader_poll_sec", 0.05))
        self.bus_enabled = False  # 启动握手(应对行为包未升级)后才置位
        # bus 批量执行器: 同一批 ptc 查询一次性下发、按 id 收齐
        capabilities.set_bus_batch_runner(self._run_bus_batch)
        capabilities.set_bus_batch_max(cfg.get("bus_batch_max", 8))
        capabilities.register("send_chat_message", SEND_CHAT_SCHEMA, self._tool_send_message)
        capabilities.register("use_skill", capabilities.USE_SKILL_SCHEMA, self._tool_use_skill)
        capabilities.register("run_server_command", RUN_COMMAND_SCHEMA, self._tool_run_command)
        capabilities.register("get_player_position", GET_POSITION_SCHEMA,
                             self._tool_get_position, concurrency="bus")
        capabilities.register("get_player_hand", GET_HAND_SCHEMA,
                             self._tool_get_hand, concurrency="bus")
        capabilities.register("set_mode", SET_MODE_SCHEMA, self._tool_set_mode)
        capabilities.register("get_block", GET_BLOCK_SCHEMA,
                             self._tool_get_block, concurrency="bus")
        capabilities.register("scan_blocks", SCAN_BLOCKS_SCHEMA,
                             self._tool_scan_blocks, concurrency="bus")
        capabilities.register("pin_region", PIN_REGION_SCHEMA, self._tool_pin_region)
        capabilities.set_ptc_limits(cfg.get("ptc_max_calls", 24),
                                    cfg.get("ptc_result_limit", 30000),
                                    cfg.get("ptc_stated_calls", 12))
        self._await_list_names = False
        self.player_positions: dict[str, str] = {}
        self.players: set[str] = set()
        self.session: Session | None = None
        self.session_counter = 0
        self.offset = 0
        self.running = True
        self.last_api_call = 0.0
        self.rate_lock = threading.Lock()   # 仅用于 api_min_interval 限速(不再包住整轮)
        self.console_gate = threading.RLock()  # 串行化“读任意控制台输出”的工具(指令/常加载/备份)
        self._tls = threading.local()       # 每个一次性线程一份请求上下文
        # 一次性对话(可并发)
        self.oneshot_max_concurrent = cfg.get("oneshot_max_concurrent", 4)
        self._oneshot_lock = threading.Lock()
        self._oneshot_active = 0
        self._oneshot_counter = 0
        self._active_oneshots: dict[int, "OneShotContext"] = {}
        self.pending: list[tuple[str, str]] = []  # (player, content) 待处理事件
        self.cv = threading.Condition()
        self.abort = threading.Event()   # 置位 = 立即中止当前任务(强制停止)
        self.soft_abort = threading.Event()  # 置位 = 到安全点停止(不打断工具内部等待)
        self.agent_busy = False          # 当前是否有任务在跑(供停止词判断)
        self._nudge = False              # 置位 = 唤醒 worker 但不带用户消息(计划模式主动引导用)
        self.mode = MODE_NORMAL          # 主对话当前模式(见 MODES); 一次性线程各自用 MODE_ONESHOT
        self._pinned: list[str] = []     # 本轮任务设置的常加载区域名(轮次结束自动移除)
        self._context_warn_level = 0     # 上下文占用提醒已报到哪一档(70 起; 压缩/新会话后复位)
        self.body_forward = False        # 正文转发开关(玩家用「正文开/关」切换; 仅显示, 不进上下文)
        self.tool_forward = True         # 工具转发开关(默认开; 玩家用「工具开/关」切换; 仅显示, 不进上下文)
        self._backup_running = False     # 「备份」控制词的后台热备份是否在跑(期间不开新任务)

    def _write_state(self) -> None:
        """原子写一份忙碌/空闲快照到 paths.STATE_PATH, 供外部脚本判断「停止状态」。
        busy 沿用「清空」的判定: agent_busy or 队列有待处理消息。"""
        with self.cv:
            state = {
                "pid": os.getpid(),
                "busy": self.agent_busy or bool(self.pending),
                "pending": len(self.pending),
                "backup": self._backup_running,
                "mode": self.mode,
                "updated": time.time(),
            }
        tmp = paths.STATE_PATH.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(state), encoding="utf-8")
            os.replace(tmp, paths.STATE_PATH)
        except OSError:
            pass  # 状态文件写失败不影响主流程

    # ---------- 请求上下文(主对话 + 并发一次性线程) ----------
    # 工具 handler 经由下面这几个 helper 读取“当前请求”的状态, 主线程回落到 self.*,
    # 一次性线程在 _tls 里放自己的一份, 互不干扰。

    def _abort(self) -> threading.Event:
        return getattr(self._tls, "abort", self.abort)

    def _soft_abort(self) -> threading.Event:
        return getattr(self._tls, "soft_abort", self.soft_abort)

    def _session(self):
        return getattr(self._tls, "session", self.session)

    def _mode(self) -> str:
        return getattr(self._tls, "mode", self.mode)

    def _oneshot(self) -> bool:
        return getattr(self._tls, "oneshot", False)

    @property
    def creative_mode(self) -> bool:
        """是否处于创造模式(creative 或 creative_max)。"""
        return self._mode() in CREATIVE_MODES

    # ---------- 会话管理 ----------


    def _start_session(self):
        self.session_counter += 1
        self.session = Session(self.session_counter)
        # 长期记忆作为第一条系统注记追加进日志(而不是写进固定的 system 前缀),
        # 之后每次 update_memory 再追加新注记, 前缀始终稳定。
        self.session.add_system(memory_note())
        skills = capabilities.skills_note()
        if skills:
            self.session.add_system(skills)
        # 初始模式(normal)注记, 紧跟在 system prompt 之后、第一条用户消息之前
        self.session.add_system(self._mode_note())
        # 转发开关随会话初始化复位(正文默认关, 工具默认开)
        self.body_forward = False
        self.tool_forward = True
        self._context_warn_level = 0  # 新会话上下文占用从零开始, 提醒档位复位
        log(f"=== 会话 #{self.session.id} 开始 (玩家: {sorted(self.players)}) ===")

    def _end_session(self):
        self._unpin_all()  # 兜底: 会话结束时不留常加载区域
        if self.mode != MODE_NORMAL:
            log(f"[模式] 会话结束, {MODES[self.mode].label} 自动复位到普通模式")
            self.mode = MODE_NORMAL
        if self.session:
            self.session.dump()
            log(f"=== 会话 #{self.session.id} 结束 "
                f"(消息 {len(self.session.messages)} 条, AI 回复 {self.session.replied_count} 次) ===")
            self.session = None

    def _on_join(self, name: str, xuid: str | None = None):
        was_empty = not self.players
        self.players.add(name)
        if was_empty:
            self._reset_on_rejoin(name)
        log(f"[+] {name} 进服, 当前 {len(self.players)} 人")

    def _reset_on_rejoin(self, name: str):
        """玩家数 0→1: 完整初始化会话(与“清空”同一套 _reset_session)。
        若此时有任务在跑: 不初始化也不挂起初始化, 只发一条提示告知任务在进行,
        并介绍可用的控制词(停止/强制停止/压缩/清空)。玩家全部离开期间会话不结束,
        任务可以跨离线期继续做。"""
        if not self.session:
            self._start_session()
            self._say_later("新会话已开始。发送「恢复会话」可找回上一段对话。", system=True)
            return
        with self.cv:
            busy = self.agent_busy
            self.pending.clear()  # 离线期积压的消息随旧会话一起作废
        if busy:
            log(f"[清空] {name} 进服(0→1): 有任务在进行, 不初始化, 仅提示")
            self._say_later(
                "欢迎回来。我手头还有任务在进行。"
                "要我停就发「停止」(做完当前这一步再停)或「强制停止」(立即中止); "
                "想压缩或清空上下文, 请先停下再发「压缩」或「清空」。", system=True)
            return
        n = self._reset_session()
        log(f"[清空] {name} 进服(0→1), 已完整初始化新会话(丢弃 {n} 条消息)")
        self._say_later("新会话已开始。发送「恢复会话」可找回上一段对话。", system=True)

    def _on_leave(self, name: str):
        """玩家离开只更新名单。全部离开(→0)不再结束会话: 正在进行的任务继续跑,
        会话留到下次 0→1(或“清空”/超预算)时才初始化。"""
        self.players.discard(name)
        log(f"[-] {name} 离服, 当前 {len(self.players)} 人")

    def _enqueue(self, player: str, content: str):
        with self.cv:
            self.pending.append((player, content))
            self.cv.notify()

    def _commit_to_context(self, msgs: list[tuple[str, str]]) -> list[dict]:
        """把一批玩家消息按顺序写入会话上下文, 返回对应的 user 消息(供当前请求追加)。"""
        out = []
        for player, content in msgs:
            text = f"{player}: {content}"
            self.session.add_user(text)
            out.append({"role": "user", "content": text})
        return out

    def _take_pending_mid_task(self) -> list[tuple[str, str]]:
        """安全点: 取走任务进行中到达的新消息, 交给当前 Agent 循环即时纳入。"""
        with self.cv:
            batch, self.pending = self.pending, []
        return batch
