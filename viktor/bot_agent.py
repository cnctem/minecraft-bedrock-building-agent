"""Agent 循环: 模式参数解析、DeepSeek function calling、工具轮次与收尾汇报。

依赖方向: bot_agent → session/profiles/constants/paths/capabilities; 不 import 其它 bot_* 模块。
"""
import json
import re
import time
import urllib.error
import urllib.request

import capabilities

from .constants import (CONTEXT_WARN_START_PCT, CONTEXT_WARN_STEP_PCT, CREATIVE_MODES,
                        MODE_EXECUTE, MODE_NORMAL, PIN_MODES, RETRYABLE_HTTP)
from .paths import log
from .profiles import EFFORT_KEYS, LIMIT_DEFAULTS, LIMIT_KEYS, MODES, PROMPTS, TOOLS, Mode
from .session import Session


class BotAgentMixin:
    """模式参数 / API 请求 / Agent 循环 / worker。"""

    @staticmethod
    def _ptc_speaks(tc: dict) -> bool:
        """ptc 批量调用里若包含 send_chat_message, 也算本回合已发言。
        否则会误判为“一直没说话”而重复播报。"""
        try:
            calls = json.loads(tc["function"].get("arguments") or "{}").get("calls") or []
        except Exception:
            return False
        return any((c.get("tool") or c.get("name")) == "send_chat_message"
                   for c in calls if isinstance(c, dict))

    @staticmethod
    def _spoken_text(tc: dict) -> str:
        """取出一次工具调用里“真正说出口”的最后一句文本(直接 send_chat_message,
        或 ptc 内嵌的最后一条)。用于记录「对话状态」: 对话是否还在、结尾是不是提问。"""
        fn = tc.get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except (TypeError, ValueError):
            return ""
        if not isinstance(args, dict):
            return ""
        if fn.get("name") == "send_chat_message":
            return str(args.get("text") or "")
        texts = []
        for item in (args.get("calls") or []):
            if not isinstance(item, dict) or capabilities._ptc_name(item) != "send_chat_message":
                continue
            a = capabilities._ptc_args(item)
            if isinstance(a, str):
                try:
                    a = json.loads(a or "{}")
                except ValueError:
                    a = {}
            if isinstance(a, dict) and a.get("text"):
                texts.append(str(a["text"]))
        return texts[-1] if texts else ""

    _QUESTION_RE = re.compile(
        r"(?:[?？]|吗|呢|么|好不好|对不对|行不行|要不要|可不可以|怎么样)[\s。.!！~～]*$")

    @classmethod
    def _asks_question(cls, text: str) -> bool:
        """这句话是不是以提问收尾(用于对话状态: 你刚问过, 对方的短回答就是答案)。"""
        lines = [ln.strip() for ln in (text or "").strip().splitlines() if ln.strip()]
        if not lines:
            return False
        last = lines[-1]
        if "?" in last or "？" in last:
            return True
        return bool(cls._QUESTION_RE.search(last))

    @staticmethod
    def _fmt_ago(sec: float) -> str:
        sec = max(0, int(sec))
        if sec < 60:
            return f"{sec} 秒前"
        if sec < 3600:
            return f"{sec // 60} 分钟前"
        return f"{sec / 3600:.1f} 小时前"

    # ---------- 对话状态(判断“该不该接话”的依据) ----------

    def _describe_dialog(self, player: str, now: float) -> str:
        entry = self._dialog.get(player)
        if not entry:
            return f"- 你在这段对话里还没对 {player} 说过话"
        ts, asked = entry
        age = now - ts
        q = "那次有提问" if asked else "那次没提问"
        win = self.dialog_window_sec
        if age > win:
            span = f"{int(win // 60)} 分钟" if win >= 60 else f"{int(win)} 秒"
            return (f"- 你对 {player} 最后一次发言: {self._fmt_ago(age)}, {q}"
                    f"(已超出 {span}的对话窗口)")
        return f"- 你对 {player} 最后一次发言: {self._fmt_ago(age)}, {q}"

    def _dialog_note(self, batch: list[tuple[str, str]]) -> str:
        """回合开头的「对话状态」注记: 玩家不带称呼时该不该接话, 靠这份事实记录判断,
        而不是靠模型自己从长上下文里猜多久以前说过话。只追加、不改旧消息 -> 前缀缓存不受影响。"""
        now = time.time()
        senders = list(dict.fromkeys(p for p, _ in batch))
        online = sorted(self.players)
        lines = ["# 对话状态(系统记录; 以最新一条为准, 不要回应这条注记)",
                 f"- 这句话来自: {', '.join(senders) or '(系统)'}; "
                 f"当前在线 {len(online)} 人"
                 + (f": {', '.join(online[:8])}" if online else "")]
        for p in senders:
            lines.append(self._describe_dialog(p, now))
        # 顺带列出最近跟其他人聊过谁, 方便判断“这句话是不是在对别人说”
        others = [p for p, _ in sorted(self._dialog.items(), key=lambda kv: -kv[1][0])
                  if p not in senders][:2]
        for p in others:
            entry = self._dialog.get(p)
            if entry and now - entry[0] <= self.dialog_window_sec:
                lines.append(self._describe_dialog(p, now))
        if not any((self._dialog.get(p) and now - self._dialog[p][0] <= self.dialog_window_sec)
                   for p in senders):
            lines.append("- 你和说话的玩家之间没有正在进行的对话: 没明确叫你时保持沉默。")
        return "\n".join(lines)

    def _update_dialog(self, audience: set[str], spoken: list[str], spoke: bool) -> None:
        """回合结束后更新对话状态。说过话 -> 记下对谁说过、结尾是否提问;
        保持沉默 -> 与这批玩家的连续对话就此断开(不能拿几分钟前的话当“还在聊”)。"""
        if self._oneshot():
            return
        now = time.time()
        who = {p for p in audience if p}
        if spoke:
            # 只要本轮说过的话里有提问就算“提过问”: 对方哪怕只回一个“3”也可能是在回答
            asks = any(self._asks_question(t) for t in spoken)
            for p in (who or set(self.players)):
                self._dialog[p] = (now, asks)
        else:
            for p in who:
                self._dialog.pop(p, None)
        # 太久远的记录顺手清掉, 防止随在线玩家数无限增长
        keep = max(self.dialog_window_sec * 4, 900)
        self._dialog = {p: v for p, v in self._dialog.items() if now - v[0] <= keep}

    def _seed_dialog_from(self, msgs: list[dict], at: float) -> None:
        """恢复会话时从历史里找回最近一次“对谁说过话”, 免得重启后把正在对话误判成冷启动。
        会话里没有逐条时间戳, 用落盘文件的 mtime 近似; 太久之前的记录自然会超出窗口。"""
        speaker, text = "", ""
        for m in msgs:
            role = m.get("role")
            if role == "user":
                content = m.get("content") or ""
                if ":" in content:
                    speaker = content.split(":", 1)[0].strip()[:32]
            elif role == "assistant":
                for tc in (m.get("tool_calls") or []):
                    t = self._spoken_text(tc)
                    if t:
                        text = t
        if not text or not speaker:
            return
        asked = self._asks_question(text)
        self._dialog[speaker] = (at, asked)
        log(f"[恢复] 对话状态: 上次对 {speaker} 发言({self._fmt_ago(time.time() - at)}), "
            f"{'提问' if asked else '非提问'}")

    # ---------- DeepSeek ----------

    def _mode_info(self, mode: str | None = None) -> Mode:
        return MODES[mode or self._mode()]

    def _mode_next(self, mode: str | None = None) -> tuple:
        """当前模式允许 set_mode 切到的目标(其它模式对模型不可知)。"""
        return self._mode_info(mode).next_modes

    def _mode_params(self, mode: str | None = None) -> dict:
        """当前(或指定)模式的 API 参数, 全部来自该模式的限制 profile(×scale)。
        四态+未来模式都走同一张表, 不再逐个 if。"""
        m = self._mode_info(mode)
        k = LIMIT_KEYS[m.limits]
        s = m.scale
        def val(key: str):
            return self.cfg.get(key, LIMIT_DEFAULTS.get(key))
        return {
            "effort": self.cfg.get(EFFORT_KEYS[m.effort], "low"),
            "max_tokens": s * val(k["tokens"]),
            "tool_rounds": s * val(k["rounds"]),
            "temperature": (self.cfg.get("creative_temperature")
                            if m.limits == "heavy" else self.cfg["temperature"]),
            "ptc_calls": s * val(k["ptc"]),
            "ptc_stated": s * val(k["stated"]),
            "ptc_result_limit": s * val(k["result"]),
        }

    def _mode_note(self, mode: str | None = None) -> str:
        """模式注记: 当前模式 + 行为提示词 profile + 本模式动态数值。
        会话开始与每次切模式后追加在日志尾部, 刷新模型已知的模式与上限。"""
        m = self._mode_info(mode)
        p = self._mode_params(mode)
        parts = [f"# 当前模式: {m.label}"]
        text = PROMPTS.get(m.prompt, "")
        if text:
            parts.append(text)
        caps = [f"批量工具调用(ptc)单次最多 {p['ptc_stated']} 条"]
        # 只有一次性模式明示工具轮次(闭式任务, 无收尾机会, 靠它克制冗余调用);
        # 交互模式有收尾汇报, 不透露轮次, 免得模型为凑/省轮次而多想。
        if m.reveal_rounds:
            caps.append(f"单次任务最多 {p['tool_rounds']} 轮工具调用(用完即止, 没有补救机会)")
        caps.append(f"单条回复输出上限 {p['max_tokens']} tokens")
        parts.append("本模式能力参数(随模式刷新): " + "; ".join(caps) + "。")
        return "\n\n".join(parts)

    def _allowed_tools(self, mode: str | None = None) -> set:
        """本模式暴露给模型的工具白名单。未列出的工具根本不会出现在工具表里。
        工具 profile 支持 None(全部)/{"only": 白名单}/{"except": 黑名单}。
        不可切换的模式(如一次性)连 set_mode 都不暴露。"""
        m = self._mode_info(mode)
        spec = TOOLS[m.tools]
        names = set(capabilities.registered_names())
        if spec is None:
            allow = names
        elif "only" in spec:
            allow = set(spec["only"])
        else:
            allow = names - set(spec.get("except", ()))
        if not m.next_modes:
            allow.discard("set_mode")
        # 常加载仅创造/执行模式支持
        if (mode or self._mode()) not in PIN_MODES:
            allow.discard("pin_region")
        return allow

    def _apply_mode_limits(self, params: dict):
        """把当前模式的 ptc 上限与工具黑名单同步给能力层(按线程隔离)。
        黑名单 = 全量 − 本模式白名单, 兜底阻止经 ptc 夹带白名单外的工具。"""
        capabilities.set_ptc_limits(params["ptc_calls"], params["ptc_result_limit"],
                                    params["ptc_stated"])
        capabilities.set_blocked_tools(capabilities.registered_names() - self._allowed_tools())

    def _maybe_compact_for_size(self) -> bool:
        """纯程序判断: 估算上下文超过输入预算就压缩(只留玩家消息与游戏内发言),
        返回是否重建过上下文。压缩后仍超预算(例如玩家消息本身太长)才整段清空兜底,
        沿用与“清空”同一套完整初始化。不走模型、不询问玩家。
        一次性对话的 ephemeral 上下文很短, 且绝不能清主会话, 直接跳过。"""
        if self._oneshot() or not self.session:
            return False
        used = Session._est_tokens(self.session.messages)
        budget = self._input_token_budget()
        self._maybe_warn_context_size(used)
        if used <= budget:
            return False
        msgs, stats = self._build_compact_messages()
        if Session._est_tokens(msgs) > budget:
            n = self._reset_session()
            log(f"[清空] 上下文约 {used} 估算 token 超过预算 {budget}, 压缩后仍超限, "
                f"已完整初始化新会话(丢弃 {n} 条消息)")
            if self.cfg.get("notify_context_clear", True):
                self._sys("上下文太长, 我已清空重开。发送「恢复会话」可找回上一段对话; "
                          "以后可提前发「压缩」, 只压缩对话、不清空。")
            return True
        self._apply_compact(msgs, stats)
        log(f"[压缩] 上下文约 {used} 估算 token 超过预算 {budget}, 已自动压缩"
            f"(保留玩家消息 {stats['kept_user']} 条、发言 {stats['kept_speech']} 条, "
            f"移除 {stats['dropped']} 条过程记录)")
        if self.cfg.get("notify_context_clear", True):
            self._sys("上下文太长, 我已自动压缩对话(保留玩家消息与我说过的话)。"
                      "以后想随时整理上下文, 发「压缩」即可。")
        return True

    def _maybe_warn_context_size(self, used: int) -> None:
        """上下文占用每跨过一档(70% 起、步长 10%)就用 [系统] 提醒玩家一次, 同一档只提一次。
        分母是模型窗口(context_window_tokens, 默认 1M); 压缩/清空/新会话后档位复位,
        之后会重新从 70% 起提醒。提醒里告知玩家可以手动发「压缩」, 只提醒、不改行为。"""
        window = self.cfg.get("context_window_tokens", 1048576)
        if window <= 0:
            return
        pct = int(used * 100 / window)
        level = (pct // CONTEXT_WARN_STEP_PCT) * CONTEXT_WARN_STEP_PCT
        # 只提醒 70~90 这几档: 到 100% 就直接压缩(压缩本身会回一条 [系统]), 不再重复提醒。
        if (level < CONTEXT_WARN_START_PCT or level >= 100
                or level <= self._context_warn_level):
            return
        self._context_warn_level = level
        log(f"[上下文] 估算 {used} token / 窗口 {window} (~{level}%), 已用 [系统] 提醒玩家")
        self._sys(f"对话上下文已占用约 {level}%, 接近上限时我会自动压缩对话"
                  f"(只保留玩家消息与我说过的话)。想现在就压缩, 发「压缩」即可"
                  f"(有任务在跑时先「停止」或「强制停止」); 当前任务不受影响。")

    def _input_token_budget(self) -> int:
        """输入能占多少 token: 模型窗口 − 本轮最大输出 − 安全余量。
        deepseek-flash: 窗口 1M, 单次最大输出 384000。API 要求
        prompt_tokens + max_tokens 不超过窗口, 所以输出额度必须从输入里扣掉。"""
        window = self.cfg.get("context_window_tokens", 1048576)
        reserve = self.cfg.get("context_safety_tokens", 4096)
        return max(4096, window - self._mode_params()["max_tokens"] - reserve)

    def _reply_max_chunks(self) -> int:
        if self.creative_mode:
            base = self.cfg.get("creative_reply_max_chunks", 10)
            return base * self._mode_info().scale
        return self.cfg["reply_max_chunks"]

    def _build_payload(self, messages: list[dict], params: dict) -> bytes:
        payload = {
            "model": self.cfg["model"],
            "messages": messages,
            "max_tokens": params["max_tokens"],
            "effort": params["effort"],  # deepseek-flash 思考强度: low/high/max
        }
        if not params.get("no_tools"):  # 收尾发言用 no_tools 逼模型用正文总结
            payload["tools"] = capabilities.tool_schemas(
                allow=self._allowed_tools(), mode_choices=list(self._mode_next()))
        if params.get("temperature") is not None:
            payload["temperature"] = params["temperature"]
        if self.cfg.get("parallel_tool_calls") and not params.get("no_tools"):
            payload["parallel_tool_calls"] = True  # 鼓励一次返回多个工具调用
        return json.dumps(payload).encode()

    def _rate_limit(self) -> None:
        """全局最小间隔: 只串行化“发起时刻”, 不包住整个请求/工具执行, 以允许并发一次性。"""
        with self.rate_lock:
            gap = time.time() - self.last_api_call
            if gap < self.cfg["api_min_interval_sec"]:
                time.sleep(self.cfg["api_min_interval_sec"] - gap)
            self.last_api_call = time.time()

    @staticmethod
    def _backoff_delay(attempt: int, base: float, retry_after=None) -> float:
        """第 attempt 次尝试失败后的等待: base·2^(n-1), 上限 30s; 有 Retry-After 取较大者(≤60s)。"""
        delay = min(base * (2 ** (attempt - 1)), 30.0)
        if retry_after:
            try:
                delay = max(delay, min(float(retry_after), 60.0))
            except (TypeError, ValueError):
                pass
        return delay

    def _post(self, messages: list[dict], params: dict) -> tuple[dict, str]:
        # 发送前兜底: assistant(tool_calls)/tool 配对只要破损(被截断/被中途插入别的消息),
        # DeepSeek 就回 400 "insufficient tool messages following tool_calls message",
        # 而且之后每次请求都会 400; 先按同口径修好配对再发。
        messages = Session._sanitize(messages)
        cfg = self.cfg
        payload = self._build_payload(messages, params)
        url = cfg["api_base"].rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {cfg['api_key']}"}
        attempts = max(1, int(cfg.get("api_max_attempts", 3)))
        base = float(cfg.get("api_retry_backoff_sec", 1.0))
        data = None
        for attempt in range(1, attempts + 1):
            self._rate_limit()  # 每次尝试(含重试)都遵守最小间隔
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=cfg["api_timeout_sec"]) as resp:
                    data = json.loads(resp.read())
                break
            except urllib.error.HTTPError as e:
                # HTTPError 的正文里才有 DeepSeek 的具体报错原因, 必须读出来
                body = e.read().decode("utf-8", "replace")[:400]
                if e.code not in RETRYABLE_HTTP or attempt >= attempts:
                    raise RuntimeError(f"HTTP {e.code}: {body}") from None
                delay = self._backoff_delay(
                    attempt, base, e.headers.get("Retry-After") if e.headers else None)
                log(f"[API] HTTP {e.code} ({body[:100]}) — {delay:.1f}s 后第 {attempt+1}/{attempts} 次尝试")
                time.sleep(delay)
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                if attempt >= attempts:
                    raise RuntimeError(f"{type(e).__name__}: {e}") from None
                delay = self._backoff_delay(attempt, base)
                log(f"[API] {type(e).__name__}: {e} — {delay:.1f}s 后第 {attempt+1}/{attempts} 次尝试")
                time.sleep(delay)
        usage = data.get("usage", {})
        choice = data["choices"][0]
        finish = choice.get("finish_reason") or ""
        log(f"[API] {cfg['model']}/effort={params['effort']}/max={params['max_tokens']} "
            f"tokens: prompt={usage.get('prompt_tokens')} "
            f"(缓存命中 {usage.get('prompt_cache_hit_tokens', '?')}) "
            f"completion={usage.get('completion_tokens')}"
            f"(思考 {usage.get('completion_tokens_details', {}).get('reasoning_tokens', '?')})"
            f" finish={finish}")
        return choice["message"], finish

    def _wrap_up_reply(self, messages: list[dict]) -> str:
        """工具轮次用尽时, 让模型做一次"无工具"的收尾发言: 汇报已完成 + 下一步计划,
        引导玩家回复「继续」或调整。程序无法知道已完成什么, 所以交给模型。"""
        note = ("# 工具轮次已用尽\n"
                "本次任务允许的工具轮次已用完, 你不能再调用任何工具。请直接用正文向玩家汇报: "
                "①已完成的内容 ②下一步计划, 并引导玩家回复「继续」继续, 或说明想调整的地方。"
                "务必简洁, 不要调用工具。")
        params = self._mode_params()
        params["no_tools"] = True
        try:
            msg, _ = self._post(messages + [{"role": "system", "content": note}], params)
        except Exception as e:
            log(f"[轮次] 收尾发言失败: {e}")
            return ""
        return (msg.get("content") or "").strip()

    def call_api(self) -> tuple[str, bool]:
        """function calling 循环: AI 可调能力工具, 执行结果回传后再生成最终回复。
        工具轮次也 append-only 写入会话上下文, 保持缓存前缀稳定。
        返回 (最终文本, 本轮是否已通过 send_chat_message 发言)。
        每轮重新读取模式参数: 中途切换创造模式, 下一轮即生效。
        中止(玩家发“强制停止”): 立即停手, 但每个 tool_call_id 都必须补上响应,
        否则会话上下文里会留下孤立的 tool_calls, 后续请求会被 API 判为 400。
        “停止”(软停止)只在轮次开头与两次工具调用之间生效(安全点), 不打断工具内部等待。"""
        oneshot = self._oneshot()
        self._tls.spoken = []   # 本回合真正说出口的话(按顺序), 回合结束用来更新对话状态
        if not oneshot:
            self._maybe_compact_for_size()
        session = self._session()
        messages = session.build_request_messages()
        spoke = False
        rounds = 0
        budget_retries = 0
        round_cap = 0  # 本轮工具轮次预算: 取用过的各模式上限的最大值, 只增不减
        while True:
            params = self._mode_params()  # 每轮重读: 中途切创造模式下一轮生效
            self._apply_mode_limits(params)
            # 中途切回低上限模式(如创造→普通)不应把已用轮次“倒扣”成超限、误触发收尾
            round_cap = max(round_cap, params["tool_rounds"])
            if budget_retries:
                # 上一轮被 max_tokens 截断: 抬高额度再来一次(不消耗工具轮次)。
                # 用 max() 保证只抬高不降低。
                params["max_tokens"] = max(params["max_tokens"],
                                           self.cfg.get("retry_max_reply_tokens", 32768))
            if rounds >= round_cap:
                break
            if self._abort().is_set():
                return "(用户要求强制停止, 任务已中止)", spoke
            if self._soft_abort().is_set():
                return "(用户要求停止, 任务已到安全点停下)", spoke
            # 安全点: 工具往返已闭合。把任务进行中到达的新消息写入上下文并注入本次请求,
            # 让玩家能在多轮任务中途调整方向/纠错。这些消息已从队列取走, 不会再另起一轮。
            # 一次性对话是闭式任务, 不接受主对话的消息注入(完全隔离)。
            if not oneshot:
                mid = self._take_pending_mid_task()
                if mid:
                    for m in self._commit_to_context(mid):
                        messages.append(m)
                    # 中途插话的玩家也算本轮“对话对象”: 之后你回的话就是对他说的
                    self._tls.turn_players = set(getattr(self._tls, "turn_players", ())) | {
                        p for p, _ in mid}
                    log(f"[介入] 任务进行中注入 {len(mid)} 条新消息: "
                        + "; ".join(f"{p}: {c}" for p, c in mid))
                    # 安全点注入新的玩家消息 = 新的一次任务: 把工具轮次计数与上限一并重置,
                    # 让新请求拿到一份完整预算(插入后重新开始计数), 而不是接着旧任务扣。
                    # 一次性对话是闭式任务, 不走这条路(它的轮次上限始终是硬顶)。
                    rounds = 0
                    round_cap = params["tool_rounds"]
                # 安全点再查一次体积: 长任务中途上下文增长超预算就地压缩(清空兜底会换新会话),
                # 然后按新会话重建本次请求的 messages。
                if self._maybe_compact_for_size():
                    session = self._session()
                    messages = session.build_request_messages()
            msg, finish = self._post(messages, params)
            # 思维链只记日志; 但带 tool_calls 的 assistant 消息必须把 reasoning_content
            # 一并回传 —— DeepSeek 思考模式的要求, 否则(尤其在 _sanitize 修复配对后)会 400
            # "reasoning_content must be passed back"。纯正文消息的思维链仍不进上下文。
            thinking = msg.get("reasoning_content")
            if thinking:
                log(f"[思考] {str(thinking)[:300].replace(chr(10), ' ')}")
            calls = msg.get("tool_calls") or []
            if not calls:
                msg.pop("reasoning_content", None)
                # finish=length: 思考 token 与正文/工具调用共用 max_tokens, 复杂规划
                # 会把额度烧在思考上, 导致正文为空、工具调用为空——玩家看到沉默。
                if finish == "length" and budget_retries < 1:
                    # 抬高额度要有实际空间才重试: 若当前额度已达到(或超过)重试上限,
                    # 再发一次请求与刚才完全等价, 只会把同一份额度再烧一遍, 纯浪费一整轮生成。
                    raised = max(params["max_tokens"],
                                 self.cfg.get("retry_max_reply_tokens", 32768))
                    if raised > params["max_tokens"]:
                        budget_retries += 1
                        log(f"[API] 输出被 max_tokens={params['max_tokens']} 截断, "
                            f"抬高到 {raised} 重试")
                        continue
                    log(f"[API] 输出被 max_tokens={params['max_tokens']} 截断, "
                        f"但已达重试上限 {raised} 无法再抬高, 不再重试")
                content = msg.get("content") or ""
                if finish == "length":
                    # 重试后仍被截断: 有正文就发正文(截断也好过全无), 一字未吐就说明情况
                    if not content.strip():
                        log(f"[API] 截断后仍无正文(重试 {budget_retries} 次), 告知玩家")
                        if oneshot:
                            msg_txt = "这次一次性请求内容较多, 我没能一次算完, 请拆成更小的请求重发。"
                        elif self._mode() in CREATIVE_MODES:
                            msg_txt = ("这件事我一遍想不完, 刚才没能给出答复。请把它拆成更小的步骤, "
                                       "一次让我只做一段, 我再接着往下干。")
                        else:
                            msg_txt = ("这件事我一遍想不完, 刚才没能给出答复。请拆小一点再说, "
                                       "或者让我开创造模式慢慢做。")
                        self._sys(msg_txt)
                        return "(输出被截断且无正文, 已告知玩家拆分需求)", True
                if self.body_forward and content.strip():
                    self._forward_body(content)
                    spoke = True  # 已以 [正文] 显示, 不再兜底重复
                return content, spoke
            rounds += 1
            log(f"[能力] AI 请求调用: {[c['function']['name'] for c in calls]}")
            # 旁路转发(仅显示给玩家观察, 不进上下文): 工具轮的模型正文 + 每个工具调用
            self._forward_body(msg.get("content") or "")
            if self.tool_forward:
                for tc in calls:
                    self._forward_tool(tc)
            session.messages.append(msg)
            messages.append(msg)
            silent = False
            pending_notes: list[str] = []
            for tc in calls:
                fname = tc["function"]["name"]
                if fname == "stay_silent":
                    silent = True
                before_mode = self._mode()
                if self._abort().is_set():
                    result = "(已中止)"
                elif self._soft_abort().is_set():
                    result = "(已到安全点停止)"
                else:
                    result = capabilities.execute(fname, tc["function"].get("arguments", "{}"))
                log(f"[能力] {fname} -> {result}")
                if fname == "send_chat_message" or (fname == "ptc" and self._ptc_speaks(tc)):
                    spoke = True
                    if not result.startswith("错误"):
                        text = self._spoken_text(tc)
                        if text:
                            self._tls.spoken.append(text)
                tool_msg = {"role": "tool", "tool_call_id": tc["id"], "content": result}
                session.messages.append(tool_msg)
                messages.append(tool_msg)
                # 状态变更(切模式/更新记忆)先攒着, 等**全部** tool 响应追加完再统一写注记:
                # 同一 assistant 消息带多条 tool_calls 时, 注记插在中间会拆散
                # assistant(tool_calls)/tool 的相邻配对, API 直接 400。
                pending_notes.extend(self._state_notes(result, before_mode))
            # 注记作为追加式系统消息写在所有 tool 响应之后, 只往日志尾部加,
            # 不改动 system 前缀 -> 缓存不失效, 历史也不会前后矛盾。
            for note in pending_notes:
                note_msg = {"role": "system", "content": note}
                session.messages.append(note_msg)
                messages.append(note_msg)
            # 已明确保持安静: 立即收尾, 不再追发一轮。否则模型会在正文里补一句
            # 解释, 被 _finish_turn 当作“未调用工具的正文”兜底播报出去, 等于没闭嘴。
            if silent and not spoke:
                return "", False
        # 轮次用尽: 给主会话一次"无工具"收尾汇报的机会 —— 由模型讲清已完成什么、下一步计划,
        # 并引导玩家回复「继续」或调整(它才知道做过什么, 程序不知道)。
        # 一次性是闭式任务, 不走"继续"这一套, 仍用它的固定回执。
        if not oneshot:
            wrap = self._wrap_up_reply(messages)
            if wrap:
                log("[轮次] 工具轮次用尽, 模型收尾汇报")
                return wrap, False  # 交给 worker 的 _finish_turn 兜底播报并写回上下文
            # 收尾这步本身也失败(通常是 API 报错): 才用程序一句话兜底, 别让玩家对着沉默
            self._sys("任务分批较多, 我先做到这里。请核对现场, 说“继续”我再往下做。")
            return "(工具轮次用尽, 收尾失败, 已程序兜底)", True
        self._sys("这次一次性请求步骤较多, 我没能一次做完, 请拆小后重发。")
        return "(工具轮次用尽, 已告知玩家)", True

    def _state_notes(self, result: str, before_mode: str) -> list[str]:
        """工具执行后若状态变化, 生成追加式 system 注记。
        必须放在 tool 响应之后, 否则会拆散 assistant(tool_calls)/tool 配对。
        ptc 内部夹带的 set_mode/update_memory 也会被这里捕获。"""
        notes: list[str] = []
        if self._mode() != before_mode:
            notes.append(self._mode_note())
        if "记忆已更新" in result:
            notes.append("# 长期记忆已更新(以下为最新版, 覆盖此前所有记忆)\n\n"
                         + (capabilities.read_memory() or "(空)"))
        return notes

    def _finish_turn(self, reply: str, spoke: bool) -> bool:
        """把本回合结果写回上下文。若模型把回复写在了正文里(玩家看不到),
        就在这里兜底播报——宁可多发一句, 也不能让玩家对着一片沉默。"""
        if reply.strip() and not spoke:
            log(f"[注意] AI 未调用工具却在正文输出, 已兜底播报: {reply[:80]}")
            self.bridge.say_as_viktor(reply, self.cfg["reply_chunk_len"],
                                      self._reply_max_chunks())
            spoke = True
        self.session.add_assistant(reply or ("(已通过工具发言)" if spoke else "(保持沉默)"))
        self.session.replied_count += 1
        return spoke

    def _worker(self):
        while self.running:
            with self.cv:
                # 「备份」期间不开新任务: 消息继续入队, 备份结束(_run_backup 会 notify)再处理
                while self.running and (self._backup_running
                                        or (not self.pending and not self._nudge)):
                    self.cv.wait(timeout=1)
                # 积压多条时合并成一次请求(所有消息已在上下文中, 一次回复即可)
                batch, self.pending = self.pending[:], []
                nudge, self._nudge = self._nudge, False
            if not self.session or (not batch and not nudge):
                continue
            self.abort.clear()       # 新任务开始, 清掉上一次的中止信号
            self.soft_abort.clear()
            self._tls.turn_players = {p for p, _ in batch}  # 本轮对话对象(供对话状态记录)
            if batch:
                # 「对话状态」注记: 写在玩家消息之前, 让模型判断“这句话是不是对我说的”
                self.session.add_system(self._dialog_note(batch))
            self._commit_to_context(batch)  # 本批消息写入上下文(call_api 从会话构建请求)
            if len(batch) > 1:
                log(f"[合并] {len(batch)} 条待回复合并为一次请求")
            # 不再用全局锁包住整轮: 主对话与并发一次性可同时发起请求。
            # 缓存前缀由“主会话只由本 worker 串行追加”保证; 发起节奏由 _post 的 rate_lock 限速。
            self.agent_busy = True
            reply, spoke = None, False
            try:
                reply, spoke = self.call_api()
            except Exception as e:
                log(f"[API 错误] {e}")
                if not self._abort().is_set():
                    self._sys("抱歉, 我这边暂时连不上或出错了, 刚才这条没能处理。请稍后再发一次。")
            finally:
                self.agent_busy = False
            if reply is None:
                pass  # API 出错: 本批不做回复(已记日志)
            elif self._abort().is_set():
                log("[强制停止] 任务已按玩家要求中止")
                self.session.add_assistant(reply)
            elif self._soft_abort().is_set():
                log("[停止] 任务已到安全点停下")
                self.session.add_assistant(reply)
            else:
                self._finish_turn(reply, spoke)
            if (reply is not None and not self._abort().is_set()
                    and not self._soft_abort().is_set()):
                self._update_dialog(self._tls.turn_players, self._tls.spoken, spoke)
            self._maybe_exit_execute()

    def _maybe_exit_execute(self):
        """执行模式是一次性周期: 本回合结束(完成/停止/出错)后程序自动回 normal。
        计划模式不在此列——它靠模型 set_mode("execute") 或玩家「退出计划」结束。"""
        if self.mode == MODE_EXECUTE:
            self.mode = MODE_NORMAL
            if self.session:
                self.session.add_system(self._mode_note())
            log("[计划] 执行周期结束, 已自动回到普通模式")
