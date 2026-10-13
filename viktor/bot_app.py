"""主循环: tail 服务器日志并解析事件, 启动握手/信号收尾。

依赖方向: bot_app → constants/paths; 不 import 其它 bot_* 模块。
"""
import os
import re
import signal
import threading
import time

from . import paths
from .constants import (
    BODY_OFF_WORD,
    BODY_ON_WORD,
    CLEAR_WORD,
    COMPACT_WORD,
    EXIT_PLAN_WORD,
    FORCE_STOP_WORD,
    NO_STOP_WORD,
    ONESHOT_FORCE_STOP,
    ONESHOT_TRIGGER,
    PLAN_WORD,
    RE_BRIDGE,
    RE_CHAT,
    RE_HELLO,
    RE_JOIN,
    RE_LEAVE,
    RE_LINE,
    RE_LIST,
    RESTORE_WORD,
    SOFT_STOP_WORD,
    TOOL_OFF_WORD,
    TOOL_ON_WORD,
)
from .paths import log


class BotAppMixin:
    """日志解析 / 启动握手 / tail 主循环。"""

    # ---------- 日志解析 ----------

    def process_line(self, raw: str):
        m = RE_LINE.match(raw)
        if not m:
            # 无时间戳前缀的行: 命令回显等, 忽略——除了 list 响应的名单续行
            if self._await_list_names and raw.strip():
                self._await_list_names = False
                # 名单行应全是逗号分隔的合法玩家名, 否则是混入的其他输出
                if re.fullmatch(r"[A-Za-z0-9 _\-\.]{1,20}(, *[A-Za-z0-9 _\-\.]{1,20})*",
                                raw.strip()):
                    self.players = {n.strip() for n in raw.split(",") if n.strip()}
                    log(f"[校准] list 玩家名单: {sorted(self.players)}")
                else:
                    log(f"[校准] 名单行格式异常, 忽略: {raw[:60]}")
            return
        body = m.group(3)

        if mm := RE_LIST.match(body):
            count = int(mm.group(1))
            if count == 0 and self.players:
                # 启动时校准: list 显示 0 人但内存里有人(漏了解析), 直接清零。
                # 不结束会话: 离开不再结束会话, 会话留给下次 0→1 初始化。
                log(f"[校准] list 显示 0 人, 清空玩家列表 {sorted(self.players)}")
                self.players.clear()
            elif count > 0 and not self.session:
                self._start_session()
            self._await_list_names = count > 0  # 下一行(无时间戳)是逗号分隔的玩家名
            return
        if mm := RE_JOIN.match(body):
            self._on_join(mm.group(1), mm.group(2))
            return
        if mm := RE_LEAVE.match(body):
            self._on_leave(mm.group(1))
            return
        chat = RE_BRIDGE.match(body) or RE_CHAT.match(body)
        if chat:
            name, content = chat.group(1), chat.group(2)
            log(f"<{name}> {content}")
            stripped = content.strip()
            # 一次性对话: "1 ..." 截获, 完全不进主对话、也不开启主会话(完全隔离)
            if ONESHOT_FORCE_STOP.match(stripped):
                self._on_oneshot_force_stop(name)
                return
            if ONESHOT_TRIGGER.match(stripped):
                self._handle_oneshot_line(name, stripped)
                return
            if not self.session:
                # 有聊天却不在会话中(例如漏掉进服事件), 容错开启会话
                self.players.add(name)
                self._start_session()
            if stripped == FORCE_STOP_WORD:
                self._on_force_stop(name)
                return
            if stripped == SOFT_STOP_WORD:
                self._on_soft_stop(name)
                return
            if stripped == NO_STOP_WORD:
                self._on_no_stop(name)
                return
            if stripped == CLEAR_WORD:
                self._on_clear(name)
                return
            if stripped == COMPACT_WORD:
                self._on_compact(name)
                return
            if stripped == PLAN_WORD:
                self._on_plan_mode(name)
                return
            if stripped == EXIT_PLAN_WORD:
                self._on_exit_plan(name)
                return
            if stripped == RESTORE_WORD:
                self._on_restore_session(name)
                return
            if stripped == BODY_ON_WORD:
                self._on_body_toggle(name, True)
                return
            if stripped == BODY_OFF_WORD:
                self._on_body_toggle(name, False)
                return
            if stripped == TOOL_ON_WORD:
                self._on_tool_toggle(name, True)
                return
            if stripped == TOOL_OFF_WORD:
                self._on_tool_toggle(name, False)
                return
            # 消息本身不在这里写上下文: 由 worker 开轮时(或 Agent 循环的安全点)
            # 统一提交, 避免插进 assistant(tool_calls) 与 tool 中间拆散配对。
            self._enqueue(name, content)  # 每条聊天都交给 Agent 判断是否接话

    # ---------- 主循环 ----------

    def _probe_bridge(self) -> bool:
        """协议握手: 发 `viktor:hello <nonce>`, 等行为包回 `[VIKTOR-HELLO] <nonce> v2`。
        确认行为包支持 v2(id 回显)才启用请求总线; 否则 bus 查询会明确报错而非错领回包。
        config 的 bus_protocol 可强制: "auto"(默认, 探测) / "v2"(跳过探测) / "off"(禁用)。"""
        mode = (self.cfg.get("bus_protocol") or "auto").lower()
        if mode == "v2":
            return True
        if mode == "off":
            return False
        log_file = paths.SERVER_LOG_PATH
        try:
            offset = log_file.stat().st_size
        except FileNotFoundError:
            offset = 0
        nonce = f"p{int(time.time() * 1000) % 100000000}"
        for _ in range(3):
            self.bridge.send_command(f"scriptevent viktor:hello {nonce}")
            deadline = time.time() + 2.0
            while time.time() < deadline:
                try:
                    with open(log_file, encoding="utf-8", errors="replace") as f:
                        f.seek(offset)
                        new = f.read()
                except FileNotFoundError:
                    new = ""
                if RE_HELLO.search(new) and nonce in new:
                    return True
                time.sleep(0.1)
        return False

    def tail_loop(self):
        log_file = paths.SERVER_LOG_PATH
        log_file.touch(exist_ok=True)
        self.offset = log_file.stat().st_size  # 只处理新内容
        self._cleanup_stale_pins()  # 先清残留(不与 list 校准抢日志)
        self.bridge.sync_player_count()
        self.bus_enabled = self._probe_bridge()
        log("[协议] 行为包交互协议: "
            + ("v2 (id 路由 + 批量下发)" if self.bus_enabled
               else "未握手成功, 服务端查询将报错(请重载 viktor_bridge 行为包)"))
        # 平滑重启: 若指定 VIKTOR_RESTORE=<落盘会话路径>, 启动时自动灌回(静默, 不发聊天)
        restore = os.environ.get("VIKTOR_RESTORE")
        if restore:
            try:
                self.resume_session(restore)
                log(f"[恢复] 启动时自动恢复 {restore}")
            except Exception as e:
                log(f"[恢复] 启动自动恢复失败: {e}")
        worker = threading.Thread(target=self._worker, daemon=True)
        worker.start()
        log(f"机器人已启动, tail {log_file}, screen 会话: {self.cfg['screen_session']}")
        while self.running:
            try:
                size = log_file.stat().st_size
                if size < self.offset:  # 日志被截断/轮转
                    self.offset = 0
                with open(log_file, encoding="utf-8", errors="replace") as f:
                    f.seek(self.offset)
                    for line in f:
                        self.process_line(line.rstrip("\n"))
                    self.offset = f.tell()
            except FileNotFoundError:
                pass
            except Exception as e:
                log(f"[tail 错误] {e}")
            time.sleep(self.cfg["poll_interval_sec"])

    def run(self):
        signal.signal(signal.SIGTERM, lambda *_: self.stop())
        signal.signal(signal.SIGINT, lambda *_: self.stop())
        self.tail_loop()

    def stop(self):
        log("收到退出信号")
        self.running = False
        self.bus.stop()
        with self.cv:
            self.cv.notify_all()
        self._end_session()
