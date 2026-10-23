"""全量自测: python3 bot.py --test。

不连真服务器; 日志/会话/记忆全部指向 /tmp, 不污染生产文件。
依赖方向: selftest → Bot(viktor 包) + capabilities; 仅 --test 时由入口导入。
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

import capabilities

from . import Bot, paths, wiki
from .bridge import ScreenBridge
from .config import load_config
from .constants import (
    MODE_CREATIVE,
    MODE_CREATIVE_MAX,
    MODE_EXECUTE,
    MODE_NORMAL,
    MODE_ONESHOT,
    MODE_PLAN,
    PIN_MODES,
)
from .profiles import MODES
from .session import Session, memory_note


def self_test():
    # 自测全程写临时日志, 不污染 logs/bot.log(假记录会把真实故障排查看歪)
    paths.LOG_PATH = Path("/tmp/viktor-botlog-test.log")
    paths.LOG_PATH.write_text("", encoding="utf-8")
    paths.SERVER_LOG_PATH = Path("/tmp/viktor-bot-serverlog-test.log")
    paths.SERVER_LOG_PATH.write_text("", encoding="utf-8")
    # 清空=完整初始化会落盘会话, 自测也指到临时目录
    paths.SESSION_DIR = Path("/tmp/viktor-sessions-test")
    paths.ONESHOT_DIR = Path("/tmp/viktor-oneshot-test")
    # 长期记忆也用临时文件: 真实 memory.md 会越长越占上下文, 让"压缩预算"这类用例
    # 随真实数据漂移(记忆一长, 压缩后仍超限 → 退化成清空 → 测试误报)。
    _mem_tmp = Path("/tmp/viktor-memory-test.md")
    _mem_tmp.write_text("# 测试记忆\n- 无\n", encoding="utf-8")
    _mem_orig = capabilities.MEMORY_PATH
    capabilities.MEMORY_PATH = _mem_tmp
    bot = Bot(load_config())
    samples = [
        "[2026-10-10 14:20:00:000 INFO] Player connected: TestPlayer, xuid: 12345",
        "[2026-10-10 14:20:05:000 INFO] <TestPlayer> 大家好",
        "[2026-10-10 14:20:10:000 INFO] <TestPlayer> 维克托,介绍一下你自己",
        "[2026-10-10 14:20:15:000 INFO] <TestPlayer> 再见",
        "[2026-10-10 14:20:30:000 INFO] Player disconnected: TestPlayer, xuid: 12345, pfid: abc",
    ]
    for s in samples:
        bot.process_line(s)
    # 新会话生命周期: 离服(→0)不结束会话; 下次 0→1 进服才完整初始化
    # 覆盖播报, 避免自测真的往游戏里发 tellraw
    bot.bridge.say_as_viktor = lambda text, *a, **k: None
    assert bot.session is not None, "离服后会话应保持"
    assert bot.players == set(), "离服后玩家列表应为空"
    # 所有聊天都应入队, 是否回复由 Agent 判断
    got = [(p, c) for p, c in bot.pending]
    want = [("TestPlayer", "大家好"),
            ("TestPlayer", "维克托,介绍一下你自己"),
            ("TestPlayer", "再见")]
    assert got == want, got
    sid = bot.session.id
    bot.process_line(
        "[2026-10-10 14:21:00:000 INFO] Player connected: TestPlayer, xuid: 12345")
    assert bot.session is not None and bot.session.id != sid, "0→1 进服应初始化新会话"
    # 0→1 时若任务在进行: 不初始化也不挂起, 只提示
    bot.agent_busy = True
    sid2 = bot.session.id
    bot.process_line(
        "[2026-10-10 14:22:00:000 INFO] Player disconnected: TestPlayer, xuid: 12345, pfid: abc")
    bot.process_line(
        "[2026-10-10 14:22:10:000 INFO] Player connected: TestPlayer, xuid: 12345")
    assert bot.session.id == sid2, "任务进行中, 0→1 不应初始化"
    bot.agent_busy = False
    assert bot.session.id == sid2, "0→1 不挂起初始化, 会话不应被重置"
    bot.process_line(
        "[2026-10-10 14:23:00:000 INFO] Player disconnected: TestPlayer, xuid: 12345, pfid: abc")
    assert bot.players == set(), "测试收尾: 玩家列表应为空"
    # send_chat_message 能力已注册
    names = [s["function"]["name"] for s in capabilities.tool_schemas()]
    assert "send_chat_message" in names and "update_memory" in names, names
    print("self-test OK:", json.dumps(got, ensure_ascii=False))

    # 能力测试: 记忆更新(用临时文件)
    tmp = Path("/tmp/viktor-memory-test.md")
    orig_path, orig_backup = capabilities.MEMORY_PATH, capabilities.MEMORY_BACKUP_DIR
    capabilities.MEMORY_PATH = tmp
    capabilities.MEMORY_BACKUP_DIR = Path("/tmp/viktor-memory-backup-test")
    try:
        r = capabilities.execute("update_memory",
                                 json.dumps({"content": "# 记忆\n- 玩家喜欢石英"}, ensure_ascii=False))
        assert "已更新" in r, r
        assert capabilities.read_memory().startswith("# 记忆")
        capabilities.execute("update_memory", json.dumps({"content": "# 记忆 v2"}))
        backups = list(capabilities.MEMORY_BACKUP_DIR.glob("memory-*.md"))
        assert backups, "重写前应产生备份"
        r = capabilities.execute("不存在的能力", "{}")
        assert "未知能力" in r, r
        # system prompt 注入检查
        bot2 = Bot(load_config())
        bot2.players.add("T")
        bot2._start_session()
        msgs = bot2.session.build_request_messages()
        # 记忆已从固定 system 前缀移到日志里的系统注记(第 2 条), 前缀保持恒定
        assert msgs[0]["role"] == "system" and "你的长期记忆" not in msgs[0]["content"]
        assert "你的长期记忆" in msgs[1]["content"] and "记忆 v2" in msgs[1]["content"]

        # 上下文截断: 不能从 assistant(tool_calls)/tool 中间切开(否则 DeepSeek 400)
        def _fake_pairs(sess, n):
            for i in range(n):
                sess.messages.append({"role": "assistant", "content": None, "tool_calls": [
                    {"id": f"c{i}", "type": "function",
                     "function": {"name": "f", "arguments": "{}"}}]})
                sess.messages.append({"role": "tool", "tool_call_id": f"c{i}", "content": "ok"})

        # 已取消滚动截断: 上下文永不裁剪(裁剪会破坏缓存前缀, 还会从 tool 对中间切开 400),
        # 超预算时由 _maybe_compact_for_size() 压缩; 压缩后仍超预算才整段清空
        s = Session(99)
        s.add_user("a")
        _fake_pairs(s, 60)
        s.add_user("b")
        msgs = s.build_request_messages()
        assert len(msgs) == len(s.messages) + 1, "不应再做滚动截断"
        assert msgs[1]["content"] == "a: a" or "a" in msgs[1]["content"], msgs[1]

        # 超预算不再截断(而是压缩/清空); _maybe_compact_for_size 的行为在下面自测
        s3 = Session(97)
        _fake_pairs(s3, 20)
        s3.add_user("汉" * 5000)
        assert Session._est_tokens(s3.messages) > 5000, Session._est_tokens(s3.messages)
        s3.messages.clear()
        assert s3.messages == []
        print("上下文截断自测 OK")
    finally:
        capabilities.MEMORY_PATH, capabilities.MEMORY_BACKUP_DIR = orig_path, orig_backup
        tmp.unlink(missing_ok=True)

    # 能力测试: 控制词“强制停止”立即中止、“停止”到安全点停止、“不停止/不清空”反悔(不走模型)
    sent = []
    orig_say = bot2.bridge.say_as_viktor
    bot2.bridge.say_as_viktor = lambda text, *a, **k: sent.append(text)
    bot2.players.add("Stopper")
    bot2.agent_busy = True
    bot2.abort.clear()
    bot2.process_line("[2026-10-10 18:40:00:000 INFO] [Scripting] [VIKTOR-CHAT] Stopper: 强制停止")
    assert bot2.abort.is_set(), "强制停止应置位中止标志"
    assert sent == ["已强制停止当前任务。"], sent
    assert not bot2.pending, "强制停止应清空待处理队列"
    assert not any(m.get("role") == "user" for m in bot2.session.messages), "强制停止不应进上下文"
    reply, spoke = bot2.call_api()  # 已置位时应立即返回, 不发网络请求
    assert "中止" in reply and not spoke, reply
    bot2.agent_busy = False
    bot2.abort.clear()
    sent.clear()
    bot2.process_line("[2026-10-10 18:40:05:000 INFO] [Scripting] [VIKTOR-CHAT] Stopper: 强制停止")
    assert sent == ["当前没有正在执行的任务。"], sent
    assert not bot2.abort.is_set()
    # “停止”软停止: 置 soft_abort 而不动 abort, 安全点生效
    bot2.agent_busy = True
    bot2.process_line("[2026-10-10 18:40:06:000 INFO] [Scripting] [VIKTOR-CHAT] Stopper: 停止")
    assert bot2.soft_abort.is_set() and not bot2.abort.is_set(), "停止应只置软停止标志"
    assert "做完就停" in sent[-1], sent
    reply, spoke = bot2.call_api()
    assert "安全点" in reply and not spoke, reply
    # “不停止”: 撤销未生效的软停止, 任务继续
    bot2.process_line("[2026-10-10 18:40:07:000 INFO] [Scripting] [VIKTOR-CHAT] Stopper: 不停止")
    assert not bot2.soft_abort.is_set(), "不停止应清除未生效的软停止"
    assert "已撤销" in sent[-1] and "停止" in sent[-1], sent
    # 没有未生效指令时
    bot2.process_line("[2026-10-10 18:40:09:000 INFO] [Scripting] [VIKTOR-CHAT] Stopper: 不停止")
    assert sent[-1] == "当前没有尚未生效的停止指令。", sent
    bot2.agent_busy = False
    bot2.soft_abort.clear()
    bot2.process_line("[2026-10-10 18:40:10:000 INFO] [Scripting] [VIKTOR-CHAT] Stopper: 维克托, 停止")
    assert any(p == "Stopper" for p, _ in bot2.pending), "非完全匹配应走正常流程"
    bot2.pending.clear()
    bot2.bridge.say_as_viktor = orig_say
    print("停止词自测 OK")

    # 能力测试: “清空”只在停止状态下生效; 任务进行中清空无效(不中止、不清、不进上下文)
    bot2.bridge.say_as_viktor = lambda text, *a, **k: sent.append(text)
    bot2.session.add_user("AAA: 先前的闲聊")
    bot2.mode = MODE_CREATIVE
    old_sid = bot2.session.id
    bot2.agent_busy = True
    bot2.abort.clear()
    sent.clear()
    bot2.process_line("[2026-10-10 18:41:00:000 INFO] [Scripting] [VIKTOR-CHAT] 路人甲: 清空")
    assert not bot2.abort.is_set(), "任务进行中清空不应中止任务"
    assert bot2.session.id == old_sid and bot2.session.messages, "任务进行中不应清空"
    assert sent and "清空无效" in sent[0], sent
    bot2.agent_busy = False
    # 空闲时立即清
    bot2.session.add_user("AAA: 又聊了两句")
    old_sid = bot2.session.id
    sent.clear()
    bot2.process_line("[2026-10-10 18:41:02:000 INFO] [Scripting] [VIKTOR-CHAT] 路人甲: 清空")
    msgs = bot2.session.messages
    assert msgs and all(m["role"] == "system" for m in msgs), "空闲清空后应只剩系统注记"
    assert msgs[0]["content"].startswith("# 你的长期记忆"), msgs[0]["content"][:40]
    assert "可用技能书" in "".join(m["content"] for m in msgs[1:]), "应含技能书清单注记"
    assert bot2.session.id != old_sid, "空闲清空也应开新会话"
    assert "已清空" in sent[0], sent
    bot2.process_line("[2026-10-10 18:41:05:000 INFO] [Scripting] [VIKTOR-CHAT] 路人甲: 清空一下")
    assert any(p == "路人甲" for p, _ in bot2.pending), "非完全匹配应走正常流程"
    bot2.pending.clear()
    # 超预算兜底: 压缩后仍超(玩家消息本身就超预算) → 整段清空, 复用完整初始化
    bot2.cfg["context_window_tokens"] = 1000  # 预算降到 4096 下限
    bot2.session.add_user("B: " + "汉" * 20000)
    bot2.mode = MODE_CREATIVE
    old_sid = bot2.session.id
    assert Session._est_tokens(bot2.session.messages) > bot2._input_token_budget()
    assert bot2._maybe_compact_for_size()
    assert all(m["role"] == "system" for m in bot2.session.messages), "兜底应整段清空(只剩系统注记)"
    assert bot2.session.id != old_sid and bot2.mode == MODE_NORMAL, "超长清空也应完整初始化"
    bot2.cfg["context_window_tokens"] = 1048576
    assert not bot2._maybe_compact_for_size(), "未超预算不应清空/压缩"
    bot2.bridge.say_as_viktor = orig_say
    print("清空词自测 OK")

    # ===== 压缩(compact)自测 =====

    # Session.compact 纯函数: 只留玩家消息与游戏内发言(send_chat_message 直接 + ptc 内嵌),
    # 其余工具调用/结果、普通正文、思考、旧系统注记全部丢弃, 且保持 tool 配对
    def _mk_tc(cid, name, args):
        return {"id": cid, "type": "function",
                "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}

    cs = Session(555)
    cs.add_system(memory_note())
    cs.add_user("A: 你好")
    cs.messages.append({"role": "assistant", "content": None, "reasoning_content": "想查坐标",
                        "tool_calls": [_mk_tc("c1", "get_player_position", {"player": "A"})]})
    cs.messages.append({"role": "tool", "tool_call_id": "c1", "content": "A 的坐标: 1, 2, 3"})
    cs.add_assistant("玩家看不到的正文")
    cs.messages.append({"role": "assistant", "content": "顺便说一句", "reasoning_content": "想",
                        "tool_calls": [_mk_tc("c2", "get_block", {"x": 1, "y": 2, "z": 3}),
                                       _mk_tc("c3", "send_chat_message", {"text": "已经看过现场了"})]})
    cs.messages.append({"role": "tool", "tool_call_id": "c2", "content": "石头"})
    cs.messages.append({"role": "tool", "tool_call_id": "c3", "content": "已发送到游戏内聊天。"})
    cs.messages.append({"role": "assistant", "content": None, "reasoning_content": "想",
                        "tool_calls": [_mk_tc("c4", "ptc", {"calls": [
                            {"tool": "inspect_region", "arguments": {"x1": 0, "y1": 0, "z1": 0,
                                                                     "x2": 0, "y2": 0, "z2": 15}},
                            {"tool": "send_chat_message", "arguments": {"text": "扫描完了"}}]})]})
    cs.messages.append({"role": "tool", "tool_call_id": "c4",
                        "content": "[1] inspect_region -> 区域 共 16 格\n"
                                   "[2] send_chat_message -> 已发送到游戏内聊天。"})
    cs.add_user("A: 继续")
    kept, stats = Session.compact(cs.messages)
    assert stats["kept_user"] == 2 and stats["kept_speech"] == 2, stats
    assert stats["dropped"] == len(cs.messages) - len(kept), stats
    # 保留顺序: user / 发言(c3) / ptc 重写(c4) / user, 旧注记与工具噪音都没有
    assert kept[0]["content"] == "A: 你好", kept[0]
    assert [m["role"] for m in kept] == ["user", "assistant", "tool", "assistant", "tool", "user"], \
        [m["role"] for m in kept]
    assert not any(m.get("role") == "system" for m in kept), "旧系统注记应被丢弃"
    dumped = json.dumps(kept, ensure_ascii=False)
    assert "玩家看不到的正文" not in dumped and "顺便说一句" not in dumped and "想查坐标" not in dumped
    assert "石头" not in dumped and "A 的坐标" not in dumped, dumped
    assert kept[1]["content"] is None and kept[1]["reasoning_content"] == ""
    assert [c["id"] for c in kept[1]["tool_calls"]] == ["c3"], kept[1]
    kept_ptc = kept[3]["tool_calls"][0]
    assert kept_ptc["function"]["name"] == "ptc", kept_ptc
    assert json.loads(kept_ptc["function"]["arguments"])["calls"] == [
        {"tool": "send_chat_message", "arguments": {"text": "扫描完了"}}], kept_ptc
    assert kept[4]["content"] == "[1] send_chat_message -> 已发送到游戏内聊天。", kept[4]
    # 配对严格: _sanitize 不应再丢弃任何东西
    assert len(Session._sanitize(kept)) == len(kept)
    # 缺 tool 结果的 send_chat_message 消息整体丢弃(与 _sanitize 同口径)
    broken = [{"role": "user", "content": "A: 在吗"},
              {"role": "assistant", "content": None,
               "tool_calls": [_mk_tc("b1", "send_chat_message", {"text": "在"})]}]
    kept_b, stats_b = Session.compact(broken)
    assert [m["content"] for m in kept_b] == ["A: 在吗"] and stats_b["kept_speech"] == 0, kept_b

    # 「压缩」控制词: 空闲生效(旧会话落盘 compact-*, 模式不变, loaded_skills 清空)
    orig_say_c = bot2.bridge.say_as_viktor
    bot2.bridge.say_as_viktor = lambda text, *a, **k: sent.append(text)
    bot2.agent_busy = False
    bot2.pending.clear()
    bot2.mode = MODE_CREATIVE
    if not bot2.session:
        bot2.players.add("T")
        bot2._start_session()
    bot2.session.messages.clear()
    bot2.session.add_system(memory_note())
    bot2.session.add_system(bot2._mode_note())
    bot2.session.add_user("A: 查一下这块")
    bot2.session.messages.append({"role": "assistant", "content": None, "reasoning_content": "想",
                                  "tool_calls": [_mk_tc("k1", "get_block", {"x": 0, "y": 1, "z": 0})]})
    bot2.session.messages.append({"role": "tool", "tool_call_id": "k1", "content": "minecraft:stone"})
    bot2.session.add_assistant("工具细节正文")
    bot2.session.loaded_skills.add("mc-commands/")
    old_sid = bot2.session.id
    sent.clear()
    bot2.process_line("[2026-10-10 18:42:00:000 INFO] [Scripting] [VIKTOR-CHAT] 路人甲: 压缩")
    assert bot2.session.id != old_sid, "压缩应换新会话"
    assert bot2.mode == MODE_CREATIVE, "压缩不应复位模式"
    assert not bot2.session.loaded_skills, "压缩后技能正文已丢, 应允许重新载入"
    cmsgs = bot2.session.messages
    assert cmsgs[0]["content"].startswith("# 你的长期记忆"), cmsgs[0]["content"][:40]
    assert cmsgs[2]["content"].startswith("# 当前模式: "), cmsgs[2]["content"][:40]
    assert cmsgs[-1]["content"].startswith("# 上下文已压缩"), cmsgs[-1]["content"][:40]
    assert any(m.get("content") == "A: 查一下这块" for m in cmsgs), "玩家消息应保留"
    cflat = json.dumps(cmsgs, ensure_ascii=False)
    assert "工具细节正文" not in cflat and "minecraft:stone" not in cflat, cflat
    assert sent and "已压缩" in sent[0], sent
    assert list(paths.SESSION_DIR.glob("compact-*.jsonl")), "旧会话应落盘 compact-*"
    # 忙时压缩无效(与「清空」同规则)
    bot2.agent_busy = True
    sid_busy = bot2.session.id
    sent.clear()
    bot2.process_line("[2026-10-10 18:42:01:000 INFO] [Scripting] [VIKTOR-CHAT] 路人甲: 压缩")
    assert bot2.session.id == sid_busy and sent and "压缩无效" in sent[0], sent
    bot2.agent_busy = False
    # 非完全匹配 → 走普通聊天
    bot2.pending.clear()
    bot2.process_line("[2026-10-10 18:42:02:000 INFO] [Scripting] [VIKTOR-CHAT] 路人甲: 压缩一下")
    assert any(p == "路人甲" for p, _ in bot2.pending), bot2.pending
    bot2.pending.clear()
    bot2.mode = MODE_NORMAL

    # 与真实 memory.md 的体积解耦: 自动压缩的预算是写死的 4096, 真实记忆变长会把预算占满,
    # 让“压缩”退化成“清空”(测试会误报)。这里换成一条很短的假记忆。
    _mtmp = paths.BASE_DIR / "logs" / "selftest-memory.md"
    _mtmp.parent.mkdir(parents=True, exist_ok=True)
    _mtmp.write_text("# 测试记忆\n- 无\n", encoding="utf-8")
    _orig_mem_path = capabilities.MEMORY_PATH
    capabilities.MEMORY_PATH = _mtmp
    try:
        # 自动压缩: 工具噪音撑爆预算 → 压缩(玩家的消息保留, 不清空); notify 开关生效
        bot2.cfg["context_window_tokens"] = 1000  # 预算 4096
        bot2.session = Session(777)
        bot2.session.add_system(memory_note())
        bot2.session.add_system(bot2._mode_note())
        bot2.session.add_user("A: 大扫描")
        bot2.session.messages.append({"role": "assistant", "content": None, "reasoning_content": "想",
                                      "tool_calls": [_mk_tc("s1", "inspect_region",
                                                            {"x1": 0, "y1": 0, "z1": 0,
                                                             "x2": 0, "y2": 0, "z2": 15})]})
        bot2.session.messages.append({"role": "tool", "tool_call_id": "s1", "content": "x" * 8000})
        old_sid = bot2.session.id
        sent.clear()
        assert bot2._maybe_compact_for_size()
        assert bot2.session.id != old_sid, "自动压缩应换新会话"
        assert any(m.get("content") == "A: 大扫描" for m in bot2.session.messages), "玩家消息应保留"
        assert not any(m.get("role") == "tool" for m in bot2.session.messages), "工具结果应被压缩掉"
        assert bot2.session.messages[-1]["content"].startswith("# 上下文已压缩")
        assert sent and "已压缩" in sent[-1], sent
        # 通知开关关闭 → 不再播报(仍是压缩路径: 玩家消息本身很短, 超限来自工具噪音)
        bot2.cfg["notify_context_clear"] = False
        bot2.session.add_user("A: 再看一次")
        bot2.session.messages.append({"role": "assistant", "content": None,
                                      "tool_calls": [_mk_tc("s2", "inspect_region",
                                                            {"x1": 0, "y1": 0, "z1": 0,
                                                             "x2": 0, "y2": 0, "z2": 15})]})
        bot2.session.messages.append({"role": "tool", "tool_call_id": "s2", "content": "y" * 8000})
        sent.clear()
        assert bot2._maybe_compact_for_size()
        assert sent == [], sent
        bot2.cfg["notify_context_clear"] = True
        bot2.cfg["context_window_tokens"] = 1048576
    finally:
        capabilities.MEMORY_PATH = _orig_mem_path
        _mtmp.unlink(missing_ok=True)

    # 工具轮次中途溢出: 安全点压缩后本轮继续跑完(重建 messages、换新会话)
    bot2.cfg["context_window_tokens"] = 1000
    bot2.session = Session(888)
    bot2.session.add_system(memory_note())
    bot2.session.add_system(bot2._mode_note())
    bot2.session.add_user("T: 干活")
    bot2.mode = MODE_NORMAL
    seq_mid = [0]

    def fake_post_compact(messages, params):
        seq_mid[0] += 1
        if seq_mid[0] == 1:
            return ({"role": "assistant", "content": None, "tool_calls": [
                {"id": "h1", "type": "function",
                 "function": {"name": "find_items", "arguments": '{"query":"stone"}'}}]},
                "tool_calls")
        return {"role": "assistant", "content": "做完了", "tool_calls": None}, "stop"

    orig_exec_mid = capabilities.execute
    capabilities.execute = lambda name, args: "z" * 8000
    orig_post_midc = bot2._post
    bot2._post = fake_post_compact
    bot2.abort.clear(); bot2.soft_abort.clear(); bot2.pending.clear()
    try:
        reply_mid, spoke_mid = bot2.call_api()
    finally:
        bot2._post = orig_post_midc
        capabilities.execute = orig_exec_mid
        bot2.cfg["context_window_tokens"] = 1048576
    assert reply_mid == "做完了" and seq_mid[0] == 2, (reply_mid, seq_mid)
    assert bot2.session.id != 888, "轮次间超预算应压缩换新会话"
    assert any(m.get("content") == "T: 干活" for m in bot2.session.messages)
    assert not any("z" * 100 in json.dumps(m, ensure_ascii=False)
                   for m in bot2.session.messages), "巨型工具结果应被压缩掉"
    assert bot2.session.messages[-1]["content"].startswith("# 上下文已压缩")
    # 压缩后的上下文仍严格配对、可直接继续追加
    assert len(bot2.session.build_request_messages()) == len(bot2.session.messages) + 1
    bot2.bridge.say_as_viktor = orig_say_c
    print("压缩自测 OK")

    # 上下文占用提醒: 70% 起, 每跨 10% 一档提一次(同档不重复); 压缩/新会话后复位
    war = []
    orig_say_w = bot2.bridge.say_as_viktor
    bot2.bridge.say_as_viktor = lambda text, *a, **k: war.append(text)
    bot2.cfg["context_window_tokens"] = 1_000_000
    bot2._context_warn_level = 0
    bot2._maybe_warn_context_size(699_000)      # 69% -> 不提醒
    assert war == [], war
    bot2._maybe_warn_context_size(705_000)      # 70% -> 第一档
    assert len(war) == 1 and "70%" in war[0], war
    bot2._maybe_warn_context_size(790_000)      # 79% -> 仍 70 档, 不重复
    assert len(war) == 1, war
    bot2._maybe_warn_context_size(800_000)      # 80% -> 再提
    bot2._maybe_warn_context_size(950_000)      # 95% -> 90 档
    assert len(war) == 3 and "80%" in war[1] and "90%" in war[2], war
    bot2._maybe_warn_context_size(990_000)      # 同 90 档不重复
    bot2._maybe_warn_context_size(1_050_000)    # 超 100% -> 由压缩接管, 不提醒
    assert len(war) == 3, war
    # 压缩后档位复位: 重新从 70% 起提醒
    bot2.session = Session(43210)
    bot2._apply_compact([{"role": "system", "content": "x"}],
                        {"kept_user": 0, "kept_speech": 0, "dropped": 0})
    assert bot2._context_warn_level == 0
    bot2._maybe_warn_context_size(705_000)
    assert len(war) == 4, war
    bot2.bridge.say_as_viktor = orig_say_w
    print("上下文占用提醒自测 OK")

    # ===== 状态 / 备份控制词自测 =====
    # 两个工具已下线: 模型侧不可见, 改由程序控制词提供
    tnames = set(capabilities.registered_names())
    assert not ({"get_server_status", "backup_world"} & tnames), sorted(tnames)
    assert not ({"get_server_status", "backup_world"} & bot2._allowed_tools()), "工具白名单不应含已下线工具"

    # 「状态」: ≤2 条 [系统]、任务进行中也可查、不进队列/上下文
    orig_say_st = bot2.bridge.say_as_viktor
    stsay = []
    bot2.bridge.say_as_viktor = lambda text, *a, **k: stsay.append(text)
    bot2.agent_busy = True
    bot2.pending.clear()
    bot2.process_line("[2026-10-10 18:44:00:000 INFO] [Scripting] [VIKTOR-CHAT] Tester: 状态")
    bot2.agent_busy = False
    assert 1 <= len(stsay) <= 2 and any("在线玩家" in x for x in stsay), stsay
    assert not bot2.pending, "「状态」不应进队列/上下文"
    # 非完全匹配 → 普通聊天
    stsay.clear()
    bot2.process_line("[2026-10-10 18:44:01:000 INFO] [Scripting] [VIKTOR-CHAT] Tester: 状态一下")
    assert bot2.pending == [("Tester", "状态一下")], bot2.pending
    bot2.pending.clear()
    bot2.bridge.say_as_viktor = orig_say_st
    print("状态词自测 OK")

    # 「备份」守卫: 忙时拒绝(不启动); 备份中重复触发提示; 备份中「强制停止」无法中止
    orig_say_bk = bot2.bridge.say_as_viktor
    bksay = []
    bot2.bridge.say_as_viktor = lambda text, *a, **k: bksay.append(text)
    bot2._backup_running = False
    bot2.agent_busy = True
    bot2.process_line("[2026-10-10 18:45:00:000 INFO] [Scripting] [VIKTOR-CHAT] Tester: 备份")
    assert not bot2._backup_running and bksay and "备份无效" in bksay[0], bksay
    bot2.agent_busy = False
    bot2._backup_running = True
    bksay.clear()
    bot2.process_line("[2026-10-10 18:45:01:000 INFO] [Scripting] [VIKTOR-CHAT] Tester: 备份")
    assert bksay and "正在进行中" in bksay[0], bksay
    bot2.abort.clear()
    bksay.clear()
    bot2.process_line("[2026-10-10 18:45:02:000 INFO] [Scripting] [VIKTOR-CHAT] Tester: 强制停止")
    assert not bot2.abort.is_set() and bksay and "无法中止" in bksay[0], (bot2.abort.is_set(), bksay)
    # 备份期间一次性对话被拒
    bksay.clear()
    bot2._spawn_oneshot("Tester", "随便做点什么")
    assert bksay and "备份正在进行中" in bksay[0], bksay
    assert not bot2._active_oneshots and bot2._oneshot_active == 0
    bot2._backup_running = False

    # 备份执行: 打桩, 成功 → 开始+完成两条 [系统]; 失败 → 备份失败: …
    orig_bk_locked = bot2._backup_world_locked
    bksay.clear()
    bot2._backup_world_locked = lambda args: "备份完成: /tmp/x.7z (1MB, 用时 1 秒)。世界写入已恢复。"
    bot2._run_backup()
    assert len(bksay) == 2 and "请稍候" in bksay[0] and "备份完成" in bksay[1], bksay
    assert not bot2._backup_running, "备份结束应复位 _backup_running"
    bksay.clear()
    bot2._backup_world_locked = lambda args: "系统里找不到 7z 命令, 无法备份。"
    bot2._run_backup()
    assert bksay and bksay[-1].startswith("备份失败: "), bksay
    bot2._backup_world_locked = orig_bk_locked

    # 备份期间 worker 不开新任务: 消息排队, 备份结束(notify)后继续处理
    import threading as _th2
    import time as _time
    bot2.session = Session(2001)
    bot2.session.add_system(memory_note())
    bot2.running = True
    bot2._nudge = False
    bot2._backup_running = True
    bot2.pending.clear()
    bot2.pending.append(("A", "任务"))
    orig_post_hold = bot2._post
    bot2._post = lambda messages, params: (
        {"role": "assistant", "content": None, "reasoning_content": "想",
         "tool_calls": [
            {"id": "hs1", "type": "function",
             "function": {"name": "stay_silent", "arguments": "{}"}}]}, "tool_calls")
    wt = _th2.Thread(target=bot2._worker, daemon=True)
    wt.start()
    _time.sleep(0.4)
    assert bot2.pending == [("A", "任务")], "备份期间不应开新任务"
    bot2._backup_running = False
    with bot2.cv:
        bot2.cv.notify_all()
    _time.sleep(0.6)
    assert not bot2.pending, "备份结束后应继续处理积压消息"
    assert any(m.get("content") == "A: 任务" for m in bot2.session.messages), bot2.session.messages
    bot2.running = False
    with bot2.cv:
        bot2.cv.notify_all()
    wt.join(timeout=2)
    bot2._post = orig_post_hold
    bot2.bridge.say_as_viktor = orig_say_bk
    print("备份词自测 OK")



    # 能力测试: 玩家进出记录查询(用临时日志)
    tmp_log = Path("/tmp/viktor-serverlog-test.log")
    orig_log = capabilities.SERVER_LOG
    capabilities.SERVER_LOG = tmp_log
    try:
        now = datetime.now()
        old = now - timedelta(minutes=120)
        tmp_log.write_text(
            f"[{old:%Y-%m-%d %H:%M:%S}:000 INFO] Player connected: OldPlayer, xuid: 1\n"
            f"[{now:%Y-%m-%d %H:%M:%S}:000 INFO] Player connected: NewPlayer, xuid: 2\n"
            f"[{now:%Y-%m-%d %H:%M:%S}:000 INFO] Player disconnected: NewPlayer, xuid: 2, pfid: x\n",
            encoding="utf-8")
        r = capabilities.execute("get_player_activity", json.dumps({"minutes": 60}))
        assert "NewPlayer" in r and "OldPlayer" not in r, r
        r = capabilities.execute("get_player_activity", json.dumps({"minutes": 180}))
        assert "OldPlayer" in r, r
    finally:
        capabilities.SERVER_LOG = orig_log
        tmp_log.unlink(missing_ok=True)

    # 能力测试: 指令执行(不再有玩家白名单判定, 只保留危险指令黑名单)
    r = bot2._tool_run_command({"command": "/stop"})
    assert "禁止列表" in r, r
    # 能力测试: 服务端查询走请求总线(协议 v2)。
    # 假应答: 从下发命令里取请求 id, 同步拼回带同一个 id 的行; bus 读线程按 id 路由。
    import re as _re
    bot2.bus_enabled = True
    orig_send_commands = bot2.bridge.send_commands
    _responders = {}

    def _fake_send_commands(cmds):
        for cmd in cmds:
            m = _re.search(r"viktor:(\w+)(?: (r\d+))?", cmd)
            if not m:
                continue
            fn = _responders.get(m.group(1))
            if not fn:
                continue
            for line in fn(cmd, m.group(2) or ""):
                with open(paths.SERVER_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(line + "\n")

    bot2.bridge.send_commands = _fake_send_commands

    _responders["pos"] = lambda cmd, rid: [
        f"[2026-10-10 18:29:00:000 INFO] [Scripting] [VIKTOR-POS] {rid} "
        "kirin9000S 660 67 -268 minecraft:overworld",
        f"[2026-10-10 18:29:00:000 INFO] [Scripting] [VIKTOR-POS] {rid} DONE",
    ]
    r = bot2._tool_get_position({"player": "kirin9000S"})
    assert "kirin9000S 的坐标" in r and "660" in r, r
    print(r)

    _responders["pos"] = lambda cmd, rid: [
        f"[2026-10-10 18:29:01:000 INFO] [Scripting] [VIKTOR-POS] {rid} (无玩家在线)",
        f"[2026-10-10 18:29:01:000 INFO] [Scripting] [VIKTOR-POS] {rid} DONE",
    ]
    r = bot2._tool_get_position({"player": "Ghost"})
    assert "没有玩家在线" in r, r
    print(r)

    # 能力测试: 手持物品解析(按 id 路由)
    _responders["inv"] = lambda cmd, rid: [
        f"[2026-10-10 18:30:00:000 INFO] [Scripting] [VIKTOR-INV] {rid} TestPlayer 0 diamond 3",
        f"[2026-10-10 18:30:00:000 INFO] [Scripting] [VIKTOR-INV] {rid} TestPlayer 5 iron_pickaxe 1",
        f"[2026-10-10 18:30:00:000 INFO] [Scripting] [VIKTOR-INV] {rid} TestPlayer DONE 5",
        f"[2026-10-10 18:30:00:000 INFO] [Scripting] [VIKTOR-INV] {rid} DONE",
    ]
    r = bot2._tool_get_hand({"player": "TestPlayer"})
    assert "iron_pickaxe x1" in r, r
    print(r)

    # 能力测试: 读坐标方块
    _responders["block"] = lambda cmd, rid: [
        f"[2026-10-10 18:31:00:000 INFO] [Scripting] [VIKTOR-BLOCK] {rid} "
        "660 66 -269 minecraft:overworld minecraft:grass_block",
    ]
    r = bot2._tool_get_block({"x": 660, "y": 66, "z": -269})
    assert "grass_block" in r and "(660, 66, -269)" in r, r
    print(r)

    _responders["block"] = lambda cmd, rid: [
        f"[2026-10-10 18:31:01:000 INFO] [Scripting] [VIKTOR-BLOCK] {rid} "
        "(区块未加载或超出世界高度: 73 73 1)",
    ]
    r = bot2._tool_get_block({"x": 73, "y": 73, "z": 1})
    assert "区块未加载" in r, r
    print(r)

    # id 路由: 别人的回包(不同 id)不会被认领
    _responders["block"] = lambda cmd, rid: [
        "[2026-10-10 18:31:02:000 INFO] [Scripting] [VIKTOR-BLOCK] r999999 "
        "999 99 999 minecraft:overworld minecraft:bedrock",
        f"[2026-10-10 18:31:03:000 INFO] [Scripting] [VIKTOR-BLOCK] {rid} "
        "12 34 56 minecraft:overworld minecraft:obsidian",
    ]
    r = bot2._tool_get_block({"x": 12, "y": 34, "z": 56})
    assert "obsidian" in r and "bedrock" not in r, r
    print(r)
    assert "需要整数坐标" in bot2._tool_get_block({"x": "a", "y": 1, "z": 2})

    # 能力测试: 空间感知原语 v3(分帧 JSON payload)
    bot2.pack_proto = 3

    def _frames(tag, rid, obj, size=48, reverse=False):
        """把 payload 切成 `#i/n` 帧(故意切很小以验证重组), 末帧后跟 DONE。"""
        body = json.dumps(obj, ensure_ascii=False)
        parts = [body[i:i + size] for i in range(0, len(body), size)] or [""]
        rows = [f"[2026-10-10 18:32:00:000 INFO] [Scripting] [{tag}] {rid} "
                f"#{i + 1}/{len(parts)} {part}" for i, part in enumerate(parts)]
        if reverse:  # 乱序到达也必须按 index 拼回
            rows.reverse()
        rows.append(f"[2026-10-10 18:32:00:000 INFO] [Scripting] [{tag}] {rid} DONE")
        return rows

    # 高度图: 2×2 列, 一行未加载
    _responders["heightmap"] = lambda cmd, rid: _frames("VIKTOR-MAP", rid, {
        "ok": True, "dim": "minecraft:overworld", "from": [10, 20], "to": [11, 21],
        "w": 2, "h": 2, "yMin": -64, "yMax": 320,
        "palette": ["grass_block", "water"], "heights": [64, 65, 62, 66],
        "types": [0, 1, 0, 0], "low": 62, "high": 66, "unloaded": 0, "missing": 0,
    }, reverse=True)
    r = bot2._tool_get_heightmap({"x1": 10, "z1": 20, "x2": 11, "z2": 21})
    assert "地形高度" in r and "地表 y 62~66" in r, r
    assert " 64  65" in r and " 62  66" in r, r          # 高度网格
    assert "grass_block" in r and "water" in r, r          # 图例
    print(r)

    # 缺帧: 明确报“回包不完整”, 不能拿半截 JSON 当结果
    _responders["heightmap"] = lambda cmd, rid: [
        f"[2026-10-10 18:32:00:000 INFO] [Scripting] [VIKTOR-MAP] {rid} #1/2 {{\"ok\":true,",
        f"[2026-10-10 18:32:00:000 INFO] [Scripting] [VIKTOR-MAP] {rid} DONE",
    ]
    r = bot2._tool_get_heightmap({"x1": 0, "z1": 0, "x2": 1, "z2": 1})
    assert "回包不完整" in r, r

    # 切面: 3 宽 2 高, 侧视, 含空气与未加载
    _responders["slice"] = lambda cmd, rid: _frames("VIKTOR-SLICE", rid, {
        "ok": True, "dim": "minecraft:overworld", "axis": "y", "level": 64,
        "a0": 0, "a1": 2, "b0": 0, "b1": 1, "w": 3, "h": 2,
        "palette": ["stone", "air"], "rows": ["001", "1?1"], "counts": [3, 2], "unloaded": 1,
    })
    r = bot2._tool_get_slice({"axis": "y", "level": 64, "x1": 0, "y1": 64, "z1": 0,
                              "x2": 2, "y2": 64, "z2": 1})
    assert "切面 y=64" in r and "3×2 格" in r, r
    assert "未加载 1 格" in r, r
    assert "stone" in r and "air" in r, r
    print(r)

    # 区域检查 + filter: 直接给不符合项坐标(复检主力)
    _responders["inspect"] = lambda cmd, rid: _frames("VIKTOR-INSPECT", rid, {
        "ok": True, "dim": "minecraft:overworld", "from": [0, 60, 0], "to": [3, 60, 0],
        "volume": 4, "unloaded": 0, "air": 1, "palette": ["stone_bricks", "air"],
        "types": {"stone_bricks": 3, "air": 1}, "otherTypes": 0,
        "filter": "stone_bricks", "match": 3, "mismatch": 1,
        "mismatchSamples": [[2, 60, 0, "air"]],
    })
    r = bot2._tool_inspect_region({"x1": 0, "y1": 60, "z1": 0, "x2": 3, "y2": 60, "z2": 0,
                                   "filter": "stone_bricks"})
    assert "命中 3 格" in r and "不符合 1 格" in r, r
    assert "(2, 60, 0) air" in r, r
    print(r)

    # 区域检查 detail=cells: 单元清单带类型名
    _responders["inspect"] = lambda cmd, rid: _frames("VIKTOR-INSPECT", rid, {
        "ok": True, "dim": "minecraft:overworld", "from": [0, 60, 0], "to": [1, 60, 0],
        "volume": 2, "unloaded": 0, "air": 0,
        "palette": ["stone", "dirt"], "types": {"stone": 1, "dirt": 1}, "otherTypes": 0,
        "cells": [[0, 60, 0, 0], [1, 60, 0, 1]], "cellsTruncated": True,
    })
    r = bot2._tool_inspect_region({"x1": 0, "y1": 60, "z1": 0, "x2": 1, "y2": 60, "z2": 0,
                                   "detail": "cells", "limit": 2})
    assert "(0, 60, 0) stone" in r and "(1, 60, 0) dirt" in r, r
    assert "已达条数上限" in r, r
    print(r)

    # 找方块
    _responders["find"] = lambda cmd, rid: _frames("VIKTOR-FIND", rid, {
        "ok": True, "dim": "minecraft:overworld", "block": "water",
        "from": [0, 55, 0], "to": [3, 70, 3], "volume": 1024, "unloaded": 4,
        "match": 9, "positions": [[1, 60, 2], [2, 60, 2]], "truncated": True,
    })
    r = bot2._tool_find_blocks({"block": "water", "x1": 0, "y1": 55, "z1": 0,
                                "x2": 3, "y2": 70, "z2": 3, "limit": 2})
    assert "water" in r and "9 处" in r, r
    assert "(1,60,2)" in r and "只列前 2 处" in r, r
    assert "4 格未加载" in r, r
    print(r)

    # 脚本报错 -> 直接转述, 不伪造结果
    _responders["inspect"] = lambda cmd, rid: _frames("VIKTOR-INSPECT", rid,
                                                     {"ok": False, "error": "体积超过上限"})
    r = bot2._tool_inspect_region({"x1": 0, "y1": 0, "z1": 0, "x2": 1, "y2": 1, "z2": 1})
    assert "体积超过上限" in r, r

    # 参数校验: 不发指令直接拒绝(省一次往返)
    from .bus import BusArgError
    assert "高度图列数最多" in bot2._tool_get_heightmap(
        {"x1": 0, "z1": 0, "x2": 64, "z2": 64})
    assert "最多 32768 格" in bot2._tool_inspect_region(
        {"x1": 0, "y1": 0, "z1": 0, "x2": 40, "y2": 40, "z2": 40})
    assert "最多 32768 格" in bot2._tool_find_blocks(
        {"block": "ore", "x1": 0, "y1": 0, "z1": 0, "x2": 40, "y2": 40, "z2": 40})
    assert "切面最多" in bot2._tool_get_slice(
        {"axis": "y", "level": 0, "x1": 0, "y1": 0, "z1": 0, "x2": 64, "y2": 0, "z2": 64})
    assert "axis 只能是" in bot2._tool_get_slice(
        {"axis": "q", "level": 0, "x1": 0, "y1": 0, "z1": 0, "x2": 1, "y2": 1, "z2": 1})
    # 切面命令只取 level 那一层, 另两轴从两角点投影
    assert bot2._slice_cmd("r1", {"axis": "x", "level": 100, "x1": 0, "y1": 60, "z1": 5,
                                  "x2": 0, "y2": 70, "z2": 8}) == \
        "scriptevent viktor:slice r1 x 100 5 60 8 70 overworld"
    assert bot2._heightmap_cmd("r2", {"x1": 0, "z1": 0, "x2": 1, "z2": 1, "y_max": 61}) == \
        "scriptevent viktor:heightmap r2 0 0 1 1 overworld 61 -64"

    # 协议过旧: 明确提示重载, 不要静默失败
    bot2.pack_proto = 2
    r = bot2._tool_get_heightmap({"x1": 0, "z1": 0, "x2": 1, "z2": 1})
    assert "协议过旧" in r and "重载" in r, r
    bot2.pack_proto = 3

    # 并发批测: ptc 里连续的多个 scan 只触发 1 次 send_commands(整批一次下发)
    capabilities.set_bus_batch_runner(bot2._run_bus_batch)
    _batches = []

    def _counting_send(cmds):
        _batches.append(list(cmds))
        _fake_send_commands(cmds)

    bot2.bridge.send_commands = _counting_send
    capabilities.set_ptc_limit(10)
    _responders["inspect"] = lambda cmd, rid: _frames("VIKTOR-INSPECT", rid, {
        "ok": True, "dim": "minecraft:overworld", "from": [0, 60, 0], "to": [3, 60, 0],
        "volume": 4, "unloaded": 0, "air": 0, "palette": ["stone"],
        "types": {"stone": 4}, "otherTypes": 0,
    })
    _ptc = json.dumps({"calls": [
        {"tool": "inspect_region", "arguments": {"x1": 0, "y1": 0, "z1": 0, "x2": 0, "y2": 0, "z2": 15}},
        {"tool": "inspect_region", "arguments": {"x1": 0, "y1": 0, "z1": 16, "x2": 0, "y2": 0, "z2": 31}},
        {"tool": "inspect_region", "arguments": {"x1": 0, "y1": 0, "z1": 32, "x2": 0, "y2": 0, "z2": 47}},
    ]})
    _r = capabilities.execute("ptc", _ptc)
    assert len(_batches) == 1 and len(_batches[0]) == 3, _batches
    assert _r.count("区域") == 3, _r
    print("PTC 查询批量下发自测 OK")

    bot2.bridge.send_commands = orig_send_commands
    bot2.bus_enabled = False

    # 指令执行: 输出必须包含 ERROR/WARN 行, 否则模型看不到失败会编造成功
    sample = ('[2026-10-10 22:11:52:487 ERROR] Syntax error: Unexpected "20"\n'
              '[2026-10-10 22:11:53:000 INFO] Block placed\n'
              '[2026-10-10 22:11:54:000 WARN] something odd\n'
              '[2026-10-10 22:11:55:000 INFO] [Scripting] [VIKTOR-CHAT] X: hi\n')
    got = bot2._extract_command_output(sample, "fill")
    assert got == ['[错误] Syntax error: Unexpected "20"', "Block placed",
                   "[警告] something odd"], got
    print("ERROR 行捕获自测 OK", got)

    # 能力测试: 备份能力的前置校验(只查世界目录, 不真的打包)
    srv = Path(bot2.cfg["mc_server_dir"])
    wd = srv / "worlds" / bot2._world_name(srv)
    assert wd.is_dir(), wd
    print("备份能力前置校验 OK:", wd)

    # 能力测试: PTC 批量工具调用
    capabilities.set_ptc_limit(3)
    # 宽容解析: 少了 tool 键 / OpenAI function 嵌套 / args 别名 都要能认
    r = capabilities.execute("ptc", json.dumps({"calls": [
        {"function": {"name": "stay_silent", "arguments": {}}},
        {"tool_name": "stay_silent", "args": {}},
        {"arguments": {}},
    ]}, ensure_ascii=False))
    assert r.count("已保持安静") == 2, r
    assert "缺少工具名" in r and "keys=" in r, r
    r = capabilities.execute("ptc", json.dumps({"calls": [
        {"tool": "stay_silent", "arguments": {}},
        {"tool": "不存在", "arguments": {}},
        {"tool": "ptc", "arguments": {"calls": []}},
    ]}, ensure_ascii=False))
    assert "已保持安静" in r and "未知能力" in r and "不允许嵌套" in r, r
    assert "最多 3 个" in capabilities.execute(
        "ptc", json.dumps({"calls": [{"tool": "stay_silent", "arguments": {}}] * 4})), "上限未生效"
    # 口头 12 / 程序 24: 超一点能过, 超一倍才拒
    capabilities.set_ptc_limits(24, 30000, 12)
    _ok = json.dumps({"calls": [{"tool": "stay_silent", "arguments": {}}] * 24})
    _no = json.dumps({"calls": [{"tool": "stay_silent", "arguments": {}}] * 25})
    assert "已保持安静" in capabilities.execute("ptc", _ok), "程序放行 24 应通过"
    assert "最多 12 个" in capabilities.execute("ptc", _no), "超限报错口径应是口头值 12"
    capabilities._REGISTRY["_boom"] = (
        {"type": "function", "function": {"name": "_boom", "parameters": {}}},
        lambda a: "[错误] 炸了")
    try:
        r = capabilities.execute("ptc", json.dumps({"calls": [
            {"tool": "_boom", "arguments": {}},
            {"tool": "stay_silent", "arguments": {}}],
            "stop_on_error": True}, ensure_ascii=False))
        assert "跳过剩余" in r and "已保持安静" not in r, r
    finally:
        capabilities._REGISTRY.pop("_boom", None)
        capabilities.set_ptc_limit(bot2.cfg.get("ptc_max_calls", 12))
    # ptc 里夹带 send_chat_message 也要算作已发言(否则会重复播报)
    assert Bot._ptc_speaks({"function": {"arguments": json.dumps(
        {"calls": [{"tool": "send_chat_message", "arguments": {"text": "hi"}}]})}})
    assert not Bot._ptc_speaks({"function": {"arguments": "{}"}})
    # 不回显参数: 结果里不应出现模型自己那份 arguments(省 token)
    _r = capabilities.execute("ptc", json.dumps({"calls": [
        {"tool": "stay_silent", "arguments": {"zzz": "UNIQUE_ARG"}}]}))
    assert "已保持安静" in _r and "UNIQUE_ARG" not in _r, _r
    assert "stay_silent -> " in _r, _r
    print("PTC 自测 OK")

    # PTC 并发模型: 默认并行 + serial 屏障(执行端排队)
    import time as _time
    events = []

    def _tool_h(nm, dur):
        def h(_a):
            events.append(("start", nm))
            _time.sleep(dur)
            events.append(("end", nm))
            return f"ok:{nm}"
        return h

    def _reg_c(nm, dur, conc):
        capabilities.register(nm, {"type": "function",
                                   "function": {"name": nm, "parameters": {}}},
                              _tool_h(nm, dur), concurrency=conc)

    _reg_c("_p1", 0.3, "parallel")
    _reg_c("_p2", 0.3, "parallel")
    _reg_c("_s1", 0.1, "serial")
    try:
        t0 = _time.time()
        r = capabilities.execute("ptc", json.dumps({"calls": [
            {"tool": "_p1", "arguments": {}}, {"tool": "_p2", "arguments": {}}]}))
        dt = _time.time() - t0
        assert "ok:_p1" in r and "ok:_p2" in r, r
        assert dt < 0.55, f"parallel 调用未并行(耗时 {dt:.2f}s)"
        # serial 是屏障: 它的前一组先结束, 后一组才开始
        events.clear()
        capabilities.execute("ptc", json.dumps({"calls": [
            {"tool": "_p1", "arguments": {}},
            {"tool": "_s1", "arguments": {}},
            {"tool": "_p2", "arguments": {}}]}))
        assert events.index(("end", "_s1")) < events.index(("start", "_p2")), events
        assert events.index(("end", "_p1")) < events.index(("start", "_s1")), events
        print("PTC 并行 + serial 屏障自测 OK")
    finally:
        for _nm in ("_p1", "_p2", "_s1"):
            capabilities._REGISTRY.pop(_nm, None)
            capabilities._CONCURRENCY.pop(_nm, None)

    # 能力测试: 创造模式(权限/等待提醒/参数切换/payload/思维链剥离/会话复位)
    assert "set_mode" in [s["function"]["name"] for s in capabilities.tool_schemas()]
    csaid = []
    orig_say3 = bot2.bridge.say_as_viktor
    bot2.bridge.say_as_viktor = lambda text, *a, **k: csaid.append(text)
    r = bot2._tool_set_mode({"mode": MODE_CREATIVE, "reason": "测试"})
    assert "已进入创造模式" in r and bot2.creative_mode, r
    # 创造模式第一轮是长思考, 必须由程序立刻提醒玩家等待(不依赖模型自觉)
    assert len(csaid) == 1 and "创造模式已开启" in csaid[0], f"开启创造模式应立刻提醒玩家等待: {csaid}"
    csaid.clear()
    # 重复切同一模式: 不重复播报
    bot2._tool_set_mode({"mode": MODE_CREATIVE, "reason": "重复开启"})
    assert csaid == [], "已处于该模式时不应重复播报"
    # 创造模式下 ptc 上限也要放宽(探索/抽检要用)
    bot2._apply_mode_limits(bot2._mode_params())
    _m, _r, _st = capabilities.get_ptc_limits()
    assert _m == bot2.cfg["creative_ptc_max_calls"], _m
    assert _st == bot2.cfg["creative_ptc_stated_calls"], _st
    assert _m == 2 * _st, "程序限制应是口头的两倍"
    assert _r == bot2.cfg["creative_ptc_result_limit"], _r
    # 三态: normal→low, creative→high, creative_max→max
    bot2.mode = MODE_NORMAL
    bot2._apply_mode_limits(bot2._mode_params())
    _m, _r, _st = capabilities.get_ptc_limits()
    assert _m == bot2.cfg["ptc_max_calls"], _m
    bot2.mode = MODE_CREATIVE
    cp = bot2._mode_params()
    assert cp["effort"] == "high" and cp["tool_rounds"] > 8 and cp["max_tokens"] > 1500, cp
    payload = json.loads(bot2._build_payload([], cp))
    assert payload["effort"] == "high" and payload["model"] == "deepseek-flash", payload
    assert "temperature" not in payload, "创造模式不传采样参数"
    # 只有玩家明确要求最高规格(creative_max)才升到 max, 已开启时也应能升档
    r = bot2._tool_set_mode({"mode": MODE_CREATIVE_MAX, "reason": "玩家要最好"})
    assert bot2.mode == MODE_CREATIVE_MAX and bot2._mode_params()["effort"] == "max", (r, bot2.mode)
    assert csaid == [], "升档到 max 不重复播报进入提醒"
    # 创造max 的限制相对创造翻倍(工具轮次 64、输出/ ptc 翻倍、分段也翻倍)
    cm = bot2._mode_params()
    cmax = MODES[MODE_CREATIVE_MAX].scale
    assert cm["tool_rounds"] == cmax * cp["tool_rounds"], (cp, cm)
    assert cm["max_tokens"] == cmax * cp["max_tokens"], (cp, cm)
    assert cm["ptc_calls"] == cmax * cp["ptc_calls"], (cp, cm)
    assert bot2._reply_max_chunks() == cmax * bot2.cfg["creative_reply_max_chunks"]
    bot2.mode = MODE_NORMAL
    csaid.clear()
    bot2._tool_set_mode({"mode": MODE_NORMAL, "reason": "测试"})
    assert csaid == [], "退出创造模式不需要播报"
    bot2.bridge.say_as_viktor = orig_say3
    np_ = bot2._mode_params()
    assert np_["effort"] == "low", np_
    payload2 = json.loads(bot2._build_payload([], np_))
    assert payload2["effort"] == "low" and payload2["temperature"] == bot2.cfg["temperature"]

    # 思维链处理: 带 tool_calls 的 assistant 必须保留 reasoning_content(DeepSeek 思考模式要求,
    # 否则 _sanitize 修好配对后会 400); 纯正文消息的思维链不进上下文
    if not bot2.session:
        bot2.players.add("T")
        bot2._start_session()
    canned = iter([
        {"role": "assistant", "content": None, "reasoning_content": "让我想想……",
         "tool_calls": [{"id": "t1", "type": "function",
                         "function": {"name": "stay_silent", "arguments": "{}"}}]},
        {"role": "assistant", "content": "", "tool_calls": None},
    ])
    orig_post = bot2._post
    bot2._post = lambda messages, params: (next(canned), "stop")
    bot2.abort.clear()
    bot2.call_api()
    bot2._post = orig_post
    tc_msgs = [m for m in bot2.session.messages if m.get("tool_calls")]
    assert tc_msgs and all("reasoning_content" in m for m in tc_msgs), tc_msgs

    # 兜底播报: 模型把回复写在正文(玩家看不到)时必须自动补发
    said2 = []
    orig_say2 = bot2.bridge.say_as_viktor
    bot2.bridge.say_as_viktor = lambda text, *a, **k: said2.append(text)
    if not bot2.session:
        bot2.players.add("T")
        bot2._start_session()
    assert bot2._finish_turn("报告: 25 格全是石头", False)
    assert said2 == ["报告: 25 格全是石头"], said2
    assert bot2.session.messages[-1]["content"].startswith("报告")
    said2.clear()
    bot2._finish_turn("", True)  # 已通过工具发过言, 不该重复播报
    assert said2 == [], said2
    bot2.bridge.say_as_viktor = orig_say2
    print("兜底播报自测 OK")

    # 任务进行中插话: 安全点注入当前请求并写入上下文, 不另起一轮
    if not bot2.session:
        bot2.players.add("T")
        bot2._start_session()
    bot2.agent_busy = True
    bot2.abort.clear()
    bot2.soft_abort.clear()
    bot2.pending.clear()
    mid_calls = {"n": 0}
    injected: list[bool] = []

    def fake_post_mid(messages, params):
        mid_calls["n"] += 1
        if mid_calls["n"] == 1:
            with bot2.cv:  # 模拟任务进行中玩家插话
                bot2.pending.append(("Boss", "改一下, 用石英"))
            return ({"role": "assistant", "content": None, "tool_calls": [
                {"id": "m1", "type": "function",
                 "function": {"name": "get_player_activity",
                              "arguments": "{\"minutes\": 1}"}}]}, "tool_calls")
        injected.append(any(m.get("role") == "user" and "石英" in (m.get("content") or "")
                            for m in messages))
        return ({"role": "assistant", "content": "好的, 改用石英。"}, "stop")

    orig_post_mid = bot2._post
    bot2._post = fake_post_mid
    bot2.call_api()
    bot2._post = orig_post_mid
    assert injected == [True], injected
    assert not bot2.pending, "插话应在安全点被取走, 不另起一轮"
    assert any("石英" in (m.get("content") or "") for m in bot2.session.messages), \
        "插话应写入上下文"
    bot2.agent_busy = False
    print("任务中插话自测 OK")

    # 多工具调用 + 状态注记: 注记必须排在**全部** tool 响应之后。
    # 插在中间会拆散 assistant(tool_calls)/tool 的相邻配对, DeepSeek 回 400
    # "insufficient tool messages following tool_calls message"(2026-10-13 实机踩到)。
    if not bot2.session:
        bot2.players.add("T")
        bot2._start_session()
    bot2.agent_busy = True
    bot2.abort.clear()
    bot2.soft_abort.clear()
    bot2.pending.clear()
    pair_calls = {"n": 0}
    payloads: list[list[dict]] = []
    orig_say_pair = bot2.bridge.say_as_viktor
    bot2.bridge.say_as_viktor = lambda text, *a, **k: None  # 测试期间不要真发言

    def fake_post_pair(messages, params):
        payloads.append([dict(m) for m in messages])
        pair_calls["n"] += 1
        if pair_calls["n"] == 1:
            return ({"role": "assistant", "content": None, "tool_calls": [
                {"id": "n1", "type": "function", "function": {"name": "ptc", "arguments": json.dumps(
                    {"calls": [{"tool": "set_mode", "arguments": {
                        "mode": MODE_CREATIVE_MAX, "reason": "自测"}}]}, ensure_ascii=False)}},
                {"id": "n2", "type": "function", "function": {
                    "name": "get_player_activity", "arguments": "{\"minutes\": 1}"}}]},
                "tool_calls")
        return ({"role": "assistant", "content": "好的。"}, "stop")

    orig_post_pair = bot2._post
    bot2._post = fake_post_pair
    bot2.call_api()
    bot2._post = orig_post_pair
    bot2.agent_busy = False
    assert pair_calls["n"] == 2, pair_calls
    for msgs in payloads[1:]:  # 第 1 次是本轮开头, 第 2 次才带上工具往返
        for idx, m in enumerate(msgs):
            ids = [c.get("id") for c in (m.get("tool_calls") or [])]
            if not ids:
                continue
            followers = []
            for f in msgs[idx + 1:]:
                if f.get("role") != "tool":
                    break
                followers.append(f.get("tool_call_id"))
            assert all(t in followers for t in ids), \
                f"tool_calls {ids} 后面只跟了 {followers} —— 状态注记插错位置了"
    assert any(m.get("role") == "system" and "模式" in (m.get("content") or "")
               for m in bot2.session.messages), "切模式应留下系统注记"
    bot2._tool_set_mode({"mode": MODE_NORMAL, "reason": "自测复位"})
    bot2.bridge.say_as_viktor = orig_say_pair
    print("状态注记排在 tool 响应之后自测 OK")

    # 保持安静: 调用 stay_silent 后立即收尾, 既不追发一轮, 也不兜底播报
    said_s = []
    orig_say_s = bot2.bridge.say_as_viktor
    bot2.bridge.say_as_viktor = lambda text, *a, **k: said_s.append(text)
    if not bot2.session:
        bot2.players.add("T")
        bot2._start_session()
    canned_s = iter([
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "s1", "type": "function",
                         "function": {"name": "stay_silent", "arguments": "{}"}}]},
        {"role": "assistant", "content": "保持安静——这句不该被兜底播报", "tool_calls": None},
    ])
    orig_post_s = bot2._post
    bot2._post = lambda messages, params: (next(canned_s), "stop")
    bot2.abort.clear()
    reply_s, spoke_s = bot2.call_api()
    bot2._post = orig_post_s
    assert (reply_s, spoke_s) == ("", False), (reply_s, spoke_s)
    assert bot2._finish_turn(reply_s, spoke_s) is False
    assert said_s == [], said_s
    bot2.bridge.say_as_viktor = orig_say_s
    print("保持安静不兜底自测 OK")

    # 被 max_tokens 截断时要抬高额度重试(只抬高不降低), 而不是沉默
    budgets = []

    def fake_post_length(messages, params):
        budgets.append(params["max_tokens"])
        if len(budgets) == 1:
            return {"role": "assistant", "content": "", "tool_calls": None}, "length"
        return {"role": "assistant", "content": "想好了", "tool_calls": None}, "stop"

    bot2.mode = MODE_NORMAL
    bot2._post = fake_post_length
    bot2.abort.clear()
    reply, spoke = bot2.call_api()
    bot2._post = orig_post
    assert budgets[0] == bot2.cfg["max_reply_tokens"], budgets
    assert budgets[1] == bot2.cfg["retry_max_reply_tokens"], f"重试应抬高额度: {budgets}"
    assert reply == "想好了", reply
    # 已在重试额度之上时不得被压低
    assert max(393216, bot2.cfg["retry_max_reply_tokens"]) == 393216
    print("截断重试自测 OK", budgets)

    # 额度已达重试上限(如 creative_max=32768)时, 抬高无空间: 必须直接放弃重试、告知玩家,
    # 绝不能把等价的请求再发一次白烧一整轮生成。
    budgets_nc = []
    said_nc = []
    orig_say_nc = bot2.bridge.say_as_viktor
    bot2.bridge.say_as_viktor = lambda text, *a, **k: said_nc.append(text)

    def fake_post_noheadroom(messages, params):
        budgets_nc.append(params["max_tokens"])
        return {"role": "assistant", "content": "", "tool_calls": None}, "length"

    bot2._tls.mode = MODE_CREATIVE_MAX
    bot2._post = fake_post_noheadroom
    bot2.abort.clear()
    reply_nc, spoke_nc = bot2.call_api()
    bot2._post = orig_post
    bot2.bridge.say_as_viktor = orig_say_nc
    cap = bot2.cfg["retry_max_reply_tokens"]
    assert budgets_nc == [2 * bot2.cfg["creative_max_reply_tokens"]], budgets_nc
    assert budgets_nc[0] >= cap, budgets_nc
    assert spoke_nc is True and said_nc, (spoke_nc, said_nc)
    print("截断但无抬高空间不重试自测 OK", budgets_nc)

    # 工具轮次用尽: 给模型一次"无工具"收尾汇报的机会(不再由程序替它发消息)
    bot2.mode = MODE_NORMAL
    bot2.session = Session(999)
    bot2.session.add_system(memory_note())
    bot2.session.add_user("Tester: 造一座塔")
    bot2._tls.session = bot2.session
    bot2._tls.mode = MODE_NORMAL
    bot2._tls.abort = bot2.abort
    bot2._tls.soft_abort = bot2.soft_abort
    bot2.cfg["max_tool_rounds"] = 2
    round_posts = []

    def fake_post_rounds(messages, params):
        round_posts.append(bool(params.get("no_tools")))
        if params.get("no_tools"):
            return {"role": "assistant",
                    "content": "已完成地基; 下一步筑墙。回复「继续」我就接着做。"}, "stop"
        return {"role": "assistant", "content": "", "tool_calls": [
            {"id": "r1", "type": "function",
             "function": {"name": "find_items", "arguments": '{"query":"stone","limit":1}'}}]}, "tool_calls"

    orig_post_rounds = bot2._post
    bot2._post = fake_post_rounds
    bot2.abort.clear()
    bot2.soft_abort.clear()
    try:
        reply, spoke = bot2.call_api()
    finally:
        bot2._post = orig_post_rounds
        bot2.cfg["max_tool_rounds"] = 8
        for attr in ("session", "mode", "abort", "soft_abort"):
            if hasattr(bot2._tls, attr):
                delattr(bot2._tls, attr)
    assert "已完成" in reply and "继续" in reply, reply
    assert round_posts and round_posts[-1] is True and round_posts.count(True) == 1, round_posts
    print("轮次限制自测 OK")

    # 切回低上限模式(创造→普通)不应把已用轮次倒扣成超限、误触发收尾
    bot2.mode = MODE_CREATIVE
    bot2.session = Session(4321)
    bot2.session.add_system(memory_note())
    for _attr in ("session", "mode", "abort", "soft_abort", "oneshot"):
        if hasattr(bot2._tls, _attr):
            delattr(bot2._tls, _attr)
    bot2.cfg["max_tool_rounds"] = 2          # 普通上限压到 2; 创造仍是 32
    seq3 = [0]

    def fake_post_lowcap(m, p):
        seq3[0] += 1
        if seq3[0] == 3:
            bot2.mode = MODE_NORMAL          # 模拟第 3 轮后切回普通(上限 2)
        if seq3[0] <= 4:
            return {"role": "assistant", "content": "", "tool_calls": [
                {"id": f"L{seq3[0]}", "type": "function",
                 "function": {"name": "find_items", "arguments": '{"query":"stone","limit":1}'}}]}, "tool_calls"
        return {"role": "assistant", "content": "正常收尾", "tool_calls": None}, "stop"

    orig3 = bot2._post
    bot2._post = fake_post_lowcap
    bot2.abort.clear(); bot2.soft_abort.clear(); bot2.pending.clear()
    try:
        reply3, _ = bot2.call_api()
    finally:
        bot2._post = orig3
        bot2.cfg["max_tool_rounds"] = 8
        bot2.mode = MODE_NORMAL
    assert reply3 == "正常收尾" and seq3[0] == 5, (reply3, seq3[0])
    print("轮次上限切模式自测 OK")

    # 安全点注入新的玩家消息: 刷新一轮工具轮次预算(插入后重新开始计数)
    bot2.mode = MODE_NORMAL
    bot2.session = Session(7777)
    bot2.session.add_system(memory_note())
    bot2.session.add_user("Tester: 造塔")
    bot2._tls.session = bot2.session
    bot2._tls.mode = MODE_NORMAL
    bot2._tls.abort = bot2.abort
    bot2._tls.soft_abort = bot2.soft_abort
    bot2.cfg["max_tool_rounds"] = 2
    reset_seq = [0]

    def fake_post_reset(messages, params):
        reset_seq[0] += 1
        if reset_seq[0] == 1:
            # 第 1 轮工具往返中途玩家发来新消息: 下一个安全点会被注入 -> 重置轮次
            bot2.pending.append(("Tester", "顺便把门也开个口"))
        if reset_seq[0] <= 3:
            return {"role": "assistant", "content": "", "tool_calls": [
                {"id": f"R{reset_seq[0]}", "type": "function",
                 "function": {"name": "find_items", "arguments": '{"query":"stone","limit":1}'}}]}, "tool_calls"
        return {"role": "assistant", "content": "收尾", "tool_calls": None}, "stop"

    orig_reset = bot2._post
    bot2._post = fake_post_reset
    bot2.abort.clear(); bot2.soft_abort.clear(); bot2.pending.clear()
    try:
        reply_reset, _ = bot2.call_api()
    finally:
        bot2._post = orig_reset
        bot2.cfg["max_tool_rounds"] = 8
        bot2.mode = MODE_NORMAL
        for attr in ("session", "mode", "abort", "soft_abort", "oneshot"):
            if hasattr(bot2._tls, attr):
                delattr(bot2._tls, attr)
    # 不重置的话上限 2 轮就撞到收尾; 注入后重新计数, 跑满 3 轮工具才进收尾(post 共 4 次)
    assert reply_reset == "收尾" and reset_seq[0] == 4, (reply_reset, reset_seq[0])
    assert any("顺便把门" in (m.get("content") or "") for m in bot2.session.messages), \
        "注入的玩家消息应写进上下文"
    print("安全点注入刷新轮次自测 OK")

    # API 错误有界退避重试: 可重试的 503 重试后成功; 400 不重试直接抛错
    import io as _io
    import urllib.error as _ue
    import urllib.request as _ur

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {
                "role": "assistant", "content": "重试成功", "tool_calls": None},
                "finish_reason": "stop"}], "usage": {}}).encode()

    retry_calls = []

    def fake_urlopen(req, timeout=None):
        retry_calls.append(1)
        if len(retry_calls) < 3:
            raise _ue.HTTPError(req.full_url, 503, "busy", {}, _io.BytesIO(b"busy"))
        return _Resp()

    bot2.session = Session(1000)
    bot2._tls.session = bot2.session
    bot2._tls.mode = MODE_NORMAL
    bot2.cfg["api_retry_backoff_sec"] = 0
    orig_urlopen = _ur.urlopen
    _ur.urlopen = fake_urlopen
    try:
        msg, finish = bot2._post([{"role": "user", "content": "hi"}],
                                 {"max_tokens": 100, "effort": "low"})
    finally:
        _ur.urlopen = orig_urlopen
        bot2.cfg["api_retry_backoff_sec"] = 1
        for attr in ("session", "mode"):
            if hasattr(bot2._tls, attr):
                delattr(bot2._tls, attr)
    assert msg["content"] == "重试成功" and finish == "stop", (msg, finish)
    assert len(retry_calls) == 3, retry_calls

    bad_calls = []

    def fake_urlopen_400(req, timeout=None):
        bad_calls.append(1)
        raise _ue.HTTPError(req.full_url, 400, "bad", {}, _io.BytesIO(b"bad request"))

    _ur.urlopen = fake_urlopen_400
    try:
        try:
            bot2._post([{"role": "user", "content": "hi"}],
                       {"max_tokens": 100, "effort": "low"})
            raise AssertionError("400 应当直接抛错")
        except RuntimeError as e:
            assert "HTTP 400" in str(e), e
    finally:
        _ur.urlopen = orig_urlopen
    assert len(bad_calls) == 1, bad_calls
    print("API 重试自测 OK")

    # 配对破损自愈: 孤儿 tool 消息与缺配对 tool_calls 必须在发送前修好
    s4 = Session(96)
    s4.add_user("a")
    s4.messages.append({"role": "assistant", "content": None, "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "f", "arguments": "{}"}}]})
    s4.messages.append({"role": "tool", "tool_call_id": "c1", "content": "ok"})
    s4.messages.append({"role": "tool", "tool_call_id": "ORPHAN", "content": "无主"})   # 孤儿
    s4.messages.append({"role": "assistant", "content": None, "tool_calls": [
        {"id": "c2", "type": "function", "function": {"name": "f", "arguments": "{}"}}]})  # 缺响应
    s4.messages.append({"role": "tool", "tool_call_id": "c3", "content": "不匹配"})
    s4.add_user("b")
    clean = s4.build_request_messages()[1:]
    assert not any(m.get("role") == "tool" and m.get("tool_call_id") in ("ORPHAN", "c3")
                   for m in clean), clean
    ids = [c["id"] for m in clean if m.get("tool_calls") for c in m["tool_calls"]]
    assert ids == ["c1"], f"缺配对的 tool_calls 应被剥掉: {clean}"
    for m in clean:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            followers = [x.get("tool_call_id") for x in clean
                         if x.get("role") == "tool"]
            assert all(c["id"] in followers for c in m["tool_calls"]), clean
    print("配对自愈自测 OK")

    # 会话结束自动复位 + 创造提示词注入
    bot2.mode = MODE_CREATIVE_MAX
    bot2._end_session()
    assert bot2.mode == MODE_NORMAL, "会话结束应自动复位到普通模式"
    sp = bot2._mode_note(MODE_CREATIVE)
    assert "创造模式" in sp and "先规划后施工" in sp
    assert "施工后必复检" in sp and "发现问题主动修复" in sp
    # 交互模式(有收尾汇报)不明示工具轮次, 免得模型为凑/省轮次而多想
    assert "轮工具调用" not in sp and "工具轮次" not in sp, sp
    assert "轮工具调用" not in bot2._mode_note(MODE_NORMAL)
    # 创造模式结束后 ptc 上限应回落
    bot2._apply_mode_limits(bot2._mode_params())
    _m, _r, _st = capabilities.get_ptc_limits()
    assert _m == bot2.cfg["ptc_max_calls"], _m
    print("创造模式自测 OK")

    # ===== 计划模式自测 =====
    psaid = []
    orig_say_plan = bot2.bridge.say_as_viktor
    bot2.bridge.say_as_viktor = lambda text, *a, **k: psaid.append(text)
    if not bot2.session:
        bot2.players.add("T")
        bot2._start_session()
    bot2.agent_busy = False
    bot2.pending.clear()
    bot2._nudge = False
    bot2.mode = MODE_NORMAL
    # 任何玩家可进入; 以 nudge 触发一次引导回合, 不进用户消息
    bot2.process_line("[2026-10-10 18:46:00:000 INFO] [Scripting] [VIKTOR-CHAT] 路人乙: 计划模式")
    assert bot2.mode == MODE_PLAN, bot2.mode
    assert bot2._nudge and not bot2.pending, "进入计划模式应 nudge 引导, 不入队用户消息"
    assert psaid and "计划模式" in psaid[-1] and "退出计划" in psaid[-1], psaid
    # 计划模式工具: 黑名单挡住 MC 命令/改世界; 查询/说话/ptc/set_mode 保留
    ptools = bot2._allowed_tools(MODE_PLAN)
    assert not ({"run_server_command", "pin_region"} & ptools), ptools
    assert {"get_player_position", "inspect_region", "get_slice", "get_heightmap",
            "find_blocks", "get_block",
            "send_chat_message", "ptc", "set_mode"} <= ptools, ptools
    # 计划/执行: effort high, 其余对齐创造max(heavy ×2)
    pp = bot2._mode_params(MODE_PLAN)
    ep = bot2._mode_params(MODE_EXECUTE)
    assert pp["effort"] == "high" == ep["effort"], (pp, ep)
    assert pp["tool_rounds"] == ep["tool_rounds"] == 2 * bot2.cfg["creative_max_tool_rounds"]
    assert pp["max_tokens"] == ep["max_tokens"] == 2 * bot2.cfg["creative_max_reply_tokens"]
    assert pp["ptc_calls"] == ep["ptc_calls"] == 2 * bot2.cfg["creative_ptc_max_calls"]
    # 计划→执行: 任何玩家都可(不受指令权限限制)
    r = bot2._tool_set_mode({"mode": MODE_EXECUTE, "reason": "计划定稿"})
    assert bot2.mode == MODE_EXECUTE and "执行" in r, (r, bot2.mode)
    # 执行模式为一次性: 回合结束程序自动回 normal
    bot2._maybe_exit_execute()
    assert bot2.mode == MODE_NORMAL, bot2.mode
    # 退出计划: 非计划模式时提示; 计划模式时回 normal
    psaid.clear()
    bot2._on_exit_plan("路人乙")
    assert bot2.mode == MODE_NORMAL and "不在计划模式" in psaid[-1], psaid
    bot2.mode = MODE_PLAN
    bot2._on_exit_plan("路人乙")
    assert bot2.mode == MODE_NORMAL and "已退出计划模式" in psaid[-1], psaid
    # 会话结束应把 plan/execute 也复位
    bot2.mode = MODE_PLAN
    bot2._end_session()
    assert bot2.mode == MODE_NORMAL, bot2.mode
    bot2.bridge.say_as_viktor = orig_say_plan
    print("计划模式自测 OK")

    # 常加载仅创造/执行模式支持: normal/oneshot/plan 都不暴露 pin_region
    for _m in (MODE_NORMAL, MODE_ONESHOT, MODE_PLAN):
        assert "pin_region" not in bot2._allowed_tools(_m), (_m, bot2._allowed_tools(_m))
    for _m in PIN_MODES:
        assert "pin_region" in bot2._allowed_tools(_m), _m
    # 离开创造模式 -> 自动清理常加载
    unp = []
    orig_send_pin = bot2.bridge.send_command
    bot2.bridge.send_command = lambda cmd: unp.append(cmd)
    bot2._pinned = ["viktor_pin_test"]
    bot2.mode = MODE_CREATIVE_MAX
    r = bot2._tool_set_mode({"mode": MODE_NORMAL, "reason": "测试"})
    bot2.bridge.send_command = orig_send_pin
    assert not bot2._pinned and any("tickingarea remove viktor_pin_test" in c for c in unp), unp
    assert bot2.mode == MODE_NORMAL, bot2.mode
    print("常加载生命周期自测 OK")

    # 恢复: 灌回落盘会话; 旧 tool_calls 缺 reasoning_content 应补空串; 模式从注记推断
    rp = Path("/tmp/viktor-resume-test.jsonl")
    rp.write_text("\n".join(json.dumps(m, ensure_ascii=False) for m in [
        {"role": "system", "content": memory_note()},
        {"role": "system", "content": bot2._mode_note(MODE_PLAN)},
        {"role": "user", "content": "T: 接着规划"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "r1", "type": "function",
             "function": {"name": "stay_silent", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "r1", "content": "ok"},
        {"role": "assistant", "content": "计划定稿"},
    ]) + "\n", encoding="utf-8")
    saved_sess, saved_mode = bot2.session, bot2.mode
    bot2.resume_session(str(rp))
    assert bot2.mode == MODE_PLAN, bot2.mode
    assert any(m.get("content") == "计划定稿" for m in bot2.session.messages)
    # 恢复时若技能清单与旧会话不同, 末尾补注一条(append-only, 不破坏前缀缓存)
    _sk = [m for m in bot2.session.messages if m.get("role") == "system"
           and (m.get("content") or "").startswith("# 可用技能书(skill)")]
    assert _sk and "mc-interior" in _sk[-1]["content"], _sk
    assert all("reasoning_content" in m for m in bot2.session.messages
               if m["role"] == "assistant"), "恢复时应给 assistant 补 reasoning_content"
    bot2.session, bot2.mode = saved_sess, saved_mode
    rp.unlink(missing_ok=True)
    print("会话恢复自测 OK")

    # ===== 一次性对话自测 =====
    import shutil as _shutil
    _shutil.rmtree(paths.ONESHOT_DIR, ignore_errors=True)
    osaid = []
    bot2.bridge.say_as_viktor = lambda text, *a, **k: osaid.append(text)
    if not bot2.session:
        bot2.players.add("T")
        bot2._start_session()
    # 触发词路由: "1 ..." 不进主对话队列、不写主上下文
    before_msgs = list(bot2.session.messages)
    bot2.pending.clear()
    spawned = []
    orig_spawn = bot2._spawn_oneshot
    bot2._spawn_oneshot = lambda name, body: spawned.append((name, body))
    bot2.process_line("[2026-10-10 18:50:00:000 INFO] [Scripting] [VIKTOR-CHAT] Tester: 1 记住我现在的位置")
    assert spawned == [("Tester", "记住我现在的位置")], spawned
    assert bot2.pending == [], "一次性触发不应进入主对话队列"
    assert bot2.session.messages == before_msgs, "一次性触发不应写主上下文"
    # "1 强制停止" 走控制面, 不再 spawn
    osaid.clear()
    bot2.process_line("[2026-10-10 18:50:01:000 INFO] [Scripting] [VIKTOR-CHAT] Tester: 1 强制停止")
    assert spawned == [("Tester", "记住我现在的位置")], "强制停止不应再 spawn"
    assert osaid and "没有正在进行" in osaid[-1], osaid
    # 空正文提示
    osaid.clear()
    bot2.process_line("[2026-10-10 18:50:02:000 INFO] [Scripting] [VIKTOR-CHAT] Tester: 1")
    assert len(spawned) == 1 and osaid and "写清" in osaid[-1], (spawned, osaid)
    # "1x" 不是一次性(必须 1 + 空格, 或单一个 1)
    osaid.clear()
    bot2.pending.clear()
    bot2.process_line("[2026-10-10 18:50:03:000 INFO] [Scripting] [VIKTOR-CHAT] Tester: 1x 你好")
    assert len(spawned) == 1 and bot2.pending == [("Tester", "1x 你好")], (spawned, bot2.pending)
    bot2.pending.clear()
    bot2._spawn_oneshot = orig_spawn
    # 并发上限
    bot2.oneshot_max_concurrent = 1
    bot2._oneshot_active = 1
    osaid.clear()
    bot2._spawn_oneshot("Tester", "随便")
    assert osaid and "有点多" in osaid[-1], osaid
    bot2._oneshot_active = 0
    bot2.oneshot_max_concurrent = bot2.cfg.get("oneshot_max_concurrent", 4)
    # 执行层黑名单: 即便经过 ptc 夹带也要挡住(黑名单 = 全量 − 本模式白名单)
    capabilities.set_blocked_tools(capabilities.registered_names() - bot2._allowed_tools(MODE_ONESHOT))
    assert "不支持" in capabilities.execute("pin_region", "{}")
    assert "不支持" in capabilities.execute("set_mode", '{"mode":"creative"}')
    capabilities.set_blocked_tools(())
    # 技能表只含本模式白名单(未列出的模型看不到, 而不是"被告知不可用")
    names = [s["function"]["name"] for s in capabilities.tool_schemas(allow=bot2._allowed_tools(MODE_ONESHOT))]
    assert not ({"pin_region", "set_mode", "stay_silent"} & set(names)), names
    assert "get_player_position" in names and "update_memory" in names, names
    # 模式注记(一次性)含行为与数值
    osp = bot2._mode_note(MODE_ONESHOT)
    assert "一次性对话模式" in osp and "必须一次性做完" in osp
    assert "创造模式(当前已开启)" not in osp
    # 一次性是闭式任务(无收尾机会): 必须明示工具轮次上限, 提醒别做冗余操作
    assert "轮工具调用" in osp and "用完即止" in osp, osp
    # 完整一次性执行: 独立 context, 多轮工具(查位置→写记忆→说话), 主对话不受影响
    tsess = bot2.session
    tmsg_before = list(tsess.messages)
    orig_exec = capabilities.execute
    executed = []
    capabilities.execute = lambda name, args: (executed.append(name) or f"fake:{name}")
    fake_seq = iter([
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "o1", "type": "function",
             "function": {"name": "get_player_position", "arguments": '{"player":"Tester"}'}}]},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "o2", "type": "function",
             "function": {"name": "update_memory", "arguments": '{"content":"- 神庙在 Tester 位置"}'}}]},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "o3", "type": "function",
             "function": {"name": "send_chat_message", "arguments": '{"text":"已记住"}'}}]},
        {"role": "assistant", "content": "", "tool_calls": None},
    ])
    checked = []

    def fake_post_os(messages, params):
        assert bot2._oneshot() is True
        assert bot2._session() is not tsess, "一次性不能使用主会话"
        checked.append(" ".join(m.get("content") or "" for m in messages
                                if m.get("role") == "system"))
        return next(fake_seq), "stop"

    orig_post_os = bot2._post
    bot2._post = fake_post_os
    try:
        bot2._run_oneshot("Tester", "记住我现在的位置")
    finally:
        bot2._post = orig_post_os
        capabilities.execute = orig_exec
        capabilities.set_blocked_tools(())
    assert executed == ["get_player_position", "update_memory", "send_chat_message"], executed
    assert bot2.session is tsess and bot2.session.messages == tmsg_before, "一次性不能碰主会话"
    assert checked and "一次性对话模式" in checked[0], checked[:1]
    assert not bot2._active_oneshots and bot2._oneshot_active == 0, "一次性收尾应清理活动表"
    files = list(Path(paths.ONESHOT_DIR).glob("oneshot-*.jsonl"))
    assert files, "一次性应单独落盘到 logs/oneshot/"
    # 并发隔离: 两个一次性线程各自的请求上下文/会话互不影响
    import threading as _th
    seen_ctx = {}
    orig_post_c = bot2._post

    def fake_post_c(messages, params):
        seen_ctx[_th.get_ident()] = (bot2._oneshot(), bot2._mode(),
                                     bot2._session() is not bot2.session)
        return {"role": "assistant", "content": "done", "tool_calls": None}, "stop"

    bot2._post = fake_post_c
    try:
        ths = [_th.Thread(target=bot2._run_oneshot, args=(f"P{i}", f"任务{i}")) for i in range(2)]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
    finally:
        bot2._post = orig_post_c
    assert len(seen_ctx) == 2 and all(v == (True, MODE_ONESHOT, True)
                                      for v in seen_ctx.values()), seen_ctx
    assert bot2.session is tsess and bot2.session.messages == tmsg_before
    print("一次性对话自测 OK")

    # [系统] 前缀: 程序生成的提示带 [系统] 且不带 <维克托>; 模型发言带 <维克托> 不带 [系统]
    sys_out = []
    orig_send_cmd = bot2.bridge.send_command
    bot2.bridge.send_command = lambda cmd: sys_out.append(cmd)
    ScreenBridge.say_as_viktor(bot2.bridge, "已清空", 120, 3, system=True)
    ScreenBridge.say_as_viktor(bot2.bridge, "模型的话", 120, 3)
    bot2.bridge.send_command = orig_send_cmd
    assert any("[系统]" in c and "已清空" in c and "<维克托>" not in c for c in sys_out), sys_out
    assert any("模型的话" in c and "<维克托>" in c and "[系统]" not in c for c in sys_out), sys_out
    print("系统前缀自测 OK")

    # 恢复会话: 从最近落盘的 dump 灌回, 并回一条 [系统] 提示
    paths.SESSION_DIR.mkdir(parents=True, exist_ok=True)
    rdump = paths.SESSION_DIR / "session-20990101-000000-s1.jsonl"
    rdump.write_text("\n".join(json.dumps(m, ensure_ascii=False) for m in [
        {"role": "system", "content": memory_note()},
        {"role": "user", "content": "Bob: 记住这座桥"},
        {"role": "assistant", "content": "好的"},
    ]) + "\n", encoding="utf-8")
    rs = []
    orig_say_rs = bot2.bridge.say_as_viktor
    bot2.bridge.say_as_viktor = lambda text, *a, **k: rs.append(text)
    bot2.agent_busy = False
    bot2.pending.clear()
    bot2._on_restore_session("Tester")
    assert any("已恢复" in t for t in rs), rs
    assert any(m.get("content") == "好的" for m in bot2.session.messages)
    assert bot2.session.messages[-1].get("role") == "system" \
        and bot2.session.messages[-1]["content"].startswith("# 可用技能书"), bot2.session.messages[-1]
    bot2.bridge.say_as_viktor = orig_say_rs
    rdump.unlink(missing_ok=True)
    print("恢复会话自测 OK")

    # 仅系统注记的空会话不落盘(否则会污染 sessions/ 并被“恢复”误选)
    esess = Session(9999)
    esess.add_system(memory_note())
    _before = set(paths.SESSION_DIR.glob("session-*.jsonl"))
    assert esess.dump() is None, "只有系统注记的会话不应落盘"
    assert set(paths.SESSION_DIR.glob("session-*.jsonl")) == _before, "不应新增空会话文件"
    esess.add_user("Bob: 你好")
    _p = esess.dump()
    assert _p is not None and _p.exists(), "有对话的会话应正常落盘"
    assert bot2._dump_has_conversation(_p), "有 user 的 dump 应算有对话"
    _emptyp = paths.SESSION_DIR / "session-20000101-000000-s0.jsonl"
    _emptyp.write_text(json.dumps({"role": "system", "content": "x"}) + "\n",
                       encoding="utf-8")
    assert not bot2._dump_has_conversation(_emptyp), "只有 system 的历史 dump 应被跳过"
    _p.unlink(missing_ok=True)
    _emptyp.unlink(missing_ok=True)
    print("空会话不落盘自测 OK")

    # 物品/方块 ID 速查(数据来自 data/items.json)
    r = capabilities.execute("find_items", '{"query":"混凝土","limit":40}')
    assert "white_concrete" in r and "白色混凝土" in r, r
    r = capabilities.execute("find_items", '{"query":"玻璃板","limit":40}')
    assert "glass_pane" in r, r
    r = capabilities.execute("find_items", '{"query":"金块"}')
    assert "gold_block" in r, r
    r = capabilities.execute("find_items", '{"query":"床"}')
    assert "bed" in r, r
    r = capabilities.execute("find_items", '{"category":"红石"}')
    assert "红石" in r and "comparator" in r, r
    r = capabilities.execute("find_items", "{}")
    assert "共" in r and "建筑" in r, r
    print("物品速查自测 OK")

    # 技能书: 清单注记 + 正文/附件按需载入 + 去重
    note = capabilities.skills_note()
    assert "mc-commands" in note and "system prompt 为准" in note, note
    r = capabilities.execute("use_skill", '{"name":"mc-commands"}')
    assert r.startswith("# 技能书:") and "weirdo_direction" in r, r[:150]
    r = capabilities.execute("use_skill", '{"name":"mc-commands","file":"references/block-states.md"}')
    assert "pillar_axis" in r, r[:150]
    for _name in ("mc-build", "mc-verify", "mc-lighting", "mc-details"):
        assert _name in note, (_name, note)
    r = capabilities.execute("use_skill", '{"name":"mc-build","file":"references/circle-tables.md"}')
    assert "0,5 1,5 2,5 3,4 4,3 5,0" in r, r[:150]
    assert "mc-interior" in note, note
    r = capabilities.execute("use_skill", '{"name":"mc-interior","file":"references/furniture.md"}')
    assert "weirdo_direction" in r and "barrel" in r, r[:150]
    assert "mc-architecture" in note, note
    r = capabilities.execute("use_skill", '{"name":"mc-architecture","file":"references/structure.md"}')
    assert "梁柱" in r and "飞扶壁" in r, r[:150]
    assert "mc-terrain" in note, note
    r = capabilities.execute("use_skill", '{"name":"mc-terrain","file":"references/vegetation.md"}')
    assert "云杉" in r and "树冠" in r, r[:150]
    r = capabilities.execute("use_skill", '{"name":"mc-verify"}')
    assert "mismatch" in r and "诊断表" in r, r[:200]
    r = capabilities.execute("use_skill", '{"name":"mc-lighting"}')
    assert "光源亮度表" in r and "隐藏光源" in r, r[:200]
    r = capabilities.execute("use_skill", '{"name":"mc-commands","file":"../SKILL.md"}')
    assert "没有附带资料" in r, r
    r = capabilities.execute("use_skill", '{"name":"nonexistent"}')
    assert "没有名为" in r, r
    print("技能书自测 OK")

    # wiki: HTML 清洗(丢 infobox/保留表格与配方网格) + 章节切分(离线, 不联网)
    _w = (
        '<div class="mw-parser-output">'
        '<table class="infobox"><tr><td>硬度</td><td>3</td></tr></table>'
        '<p>钻石（Diamond）是<b>稀有</b>物品。</p>'
        '<h2>获取</h2><p>挖掘钻石矿石获得。</p>'
        '<table class="wikitable"><tr><th>材料</th><th>配方</th></tr><tr><td>钻石块</td>'
        '<td><span class="mcui mcui-Crafting_Table">'
        '<span class="mcui-row"><span class="invslot"></span>'
        '<span class="invslot"><span class="invslot-item" title="钻石块"></span></span></span>'
        '<span class="mcui-output"><span class="invslot">'
        '<span class="invslot-item" title="钻石"></span>'
        '<span class="invslot-stacksize">9</span></span></span>'
        '<span class="searchaux">[[|]]</span></span></td></tr></table>'
        '<h2>数据值</h2><p>ID 为 diamond。</p></div>')
    _t = wiki.html_to_text(_w)
    assert "硬度" not in _t, "infobox 应被丢弃"
    assert "钻石（Diamond）是稀有物品。" in _t, _t
    assert "[[|]]" not in _t, "searchaux 应被丢弃"
    assert "【配方】" in _t and "[钻石块]" in _t and "→ 钻石 x9" in _t, _t
    assert [h[2] for h in wiki._headings(_t)] == ["获取", "数据值"], wiki._headings(_t)
    _sec, _name = wiki._slice_section(_t, "获取")
    assert _name == "获取" and "挖掘钻石矿石" in _sec and "数据值" not in _sec, _sec
    assert wiki.first_paragraph("| x |\n\n钻石（Diamond）是稀有物品。", min_len=10) \
        == "钻石（Diamond）是稀有物品。"
    # 工具已注册且对模型可见
    assert {"search_wiki", "read_wiki_page"} <= capabilities.registered_names()
    assert {"search_wiki", "read_wiki_page"} <= bot2._allowed_tools(), "应全模式可用"
    print("wiki 清洗/章节/注册自测 OK")

    # 转发开关: 正文开/关、工具开/关(控制词不进上下文; 转发只显示、不进上下文)
    fwd = []
    orig_side = bot2.bridge.say_side
    orig_sys_fwd = bot2._sys
    bot2.bridge.say_side = lambda label, text, *a: fwd.append((label, text))
    bot2._sys = lambda text: None
    try:
        bot2.session = Session(333)
        bot2.session.add_system(memory_note())
        bot2.body_forward = bot2.tool_forward = False
        bot2.pending.clear()

        def _fwd_chat(t):
            bot2.process_line(
                f"[2026-10-12 21:00:00:000 INFO] [Scripting] [VIKTOR-CHAT] T: {t}")

        _fwd_chat("正文开")
        assert bot2.body_forward
        _fwd_chat("工具开")
        assert bot2.tool_forward
        _fwd_chat("正文开一下")           # 非完全匹配不应触发
        assert bot2.body_forward
        _fwd_chat("正文关")
        _fwd_chat("工具关")
        assert not bot2.body_forward and not bot2.tool_forward
        assert all("正文开" not in (m.get("content") or "") for m in bot2.session.messages), \
            "控制词不应进上下文"
        # 工具预览取“工具命令”前 40 字
        pv = Bot._tool_preview({"function": {"name": "run_server_command",
             "arguments": json.dumps({"command": "fill 1 2 3 4 5 6 7 8 9 stone 0 replace air"})}})
        assert pv.startswith("fill") and len(pv) == 40, pv
        # 转发只走 say_side, 不进上下文
        bot2.body_forward = bot2.tool_forward = True
        n0 = len(bot2.session.messages)
        bot2._forward_body("正文ABC")
        bot2._forward_tool({"function": {"name": "run_server_command",
             "arguments": json.dumps({"command": "fill 1 2 3"})}})
        assert ("[正文]", "正文ABC") in fwd and any(l == "[工具]" for l, _ in fwd), fwd
        assert len(bot2.session.messages) == n0, "转发不应写入上下文"
        bot2.pending.clear()
    finally:
        bot2.bridge.say_side = orig_side
        bot2._sys = orig_sys_fwd
    print("转发开关自测 OK")

    # 启动清理僵尸常加载区: 只清 viktor_pin* 前缀
    _seen = []
    _oc, _sc = bot2._console_output, bot2.bridge.send_command
    bot2._console_output = lambda cmd: ("List of all ticking areas in current dimension\n"
                                        "- viktor_pin: 1 0 1 to 2 0 2\n"
                                        "- viktorpark: 3 0 3 to 4 0 4")
    bot2.bridge.send_command = lambda c: _seen.append(c)
    try:
        bot2._cleanup_stale_pins()
    finally:
        bot2._console_output, bot2.bridge.send_command = _oc, _sc
    assert any("tickingarea remove viktor_pin" in c for c in _seen), _seen
    assert not any("viktorpark" in c for c in _seen), _seen
    print("常加载残留清理自测 OK")

    # pin_region 撞名自愈: 先清残留再重试
    _calls = []
    _outs = iter(["[错误] A ticking area with the name viktor_pin already exists.",
                  "Removed ticking area(s)",
                  ("Added ticking area")])
    _oc2, _sc2 = bot2._console_output, bot2.bridge.send_command
    bot2.bridge.send_command = lambda c: _calls.append(c)
    bot2._cleanup_stale_pins = lambda: None
    bot2._console_output = lambda cmd: (_calls.append(cmd) or next(_outs))
    try:
        r = bot2._tool_pin_region({"x1": 0, "z1": 0, "x2": 15, "z2": 15})
    finally:
        bot2._console_output, bot2.bridge.send_command = _oc2, _sc2
        bot2._pinned.clear()
    assert "已设置" in r, r
    assert any("tickingarea remove viktor_pin" in c for c in _calls), _calls
    print("pin_region 撞名自愈自测 OK")

    # ---------- 建造引擎(P2.1) ----------
    from . import build as B

    prog = """
W, D, H = 9, 7, 5
api.fill((-1, -1, -1), (W, -1, D), "stonebrick")
api.box((0, 0, 0), (W-1, H-1, D-1), "oak_planks")
api.fill((1, 0, 1), (W-2, H-2, D-2), "air")
for u in range(0, W, 3):
    api.box((u, 0, 0), (u, H-1, 0), "spruce_log")
"""
    payload, stats = B.compile_build(prog, (100, 64, 200), "south", B.block_ids())
    assert stats["ops"] == 6 and stats["cells"] > 200, stats   # fill+box+fill+3×box(循环)
    assert payload["s"][1] == 6 and payload["o"] == [99, 63, 199], payload
    assert len(payload["p"]) == stats["palette"], payload["p"]
    assert ":" in payload["rle"] and " " not in payload["rle"], payload["rle"][:60]
    print("建造编译自测 OK", stats["size"], stats["cells"], "格", stats["payload_bytes"], "字节")

    # 朝向: south 与 east 的局部→世界映射
    assert B.to_world((0, 0, 0), "south", 1, 2, 3) == (1, 2, 3)
    assert B.to_world((0, 0, 0), "north", 1, 2, 3) == (-1, 2, -3)
    assert B.to_world((0, 0, 0), "east", 1, 2, 3) == (3, 2, -1)
    assert B.to_world((0, 0, 0), "west", 1, 2, 3) == (-3, 2, 1)

    # 沙箱: import / open / dunder / exec 全部拦在编译期
    for bad, want in (("import os", "Import"), ('open("/etc/passwd")', "open"),
                      ("api.__class__", "下划线"), ('exec("1")', "exec")):
        try:
            B.compile_build(bad, (0, 0, 0), "south", B.block_ids())
            raise AssertionError(f"应拦截: {bad}")
        except B.BuildError as e:
            assert want in str(e), (bad, e)
    # 未知方块 / 超体积 / 空程序
    for bad, want in (('api.fill((0,0,0),(1,1,1),"not_a_block")', "未知方块"),
                      ("def f(:", "语法错误"),
                      ("W = 3  # 只有变量, 没有放置", "没有放置任何方块")):
        try:
            B.compile_build(bad, (0, 0, 0), "south", B.block_ids())
            raise AssertionError(f"应报错: {bad}")
        except B.BuildError as e:
            assert want in str(e), (bad, e)
    try:
        B.compile_build("api.fill((0,0,0),(80,80,80),'stone')", (0, 0, 0), "south", B.block_ids())
        raise AssertionError("超体积应被拒")
    except B.BuildError as e:
        assert "超过上限" in str(e), e
    print("建造沙箱/校验自测 OK")

    # 读世界: 预取快照后程序里能问地形(离线构造 3×3×3 快照: 底层石头, 上面空气)
    snap = {"o": [0, 64, 0], "s": [3, 3, 3], "p": ["stone", "air"], "rle": "0:9,1:18",
            "unloaded": 0}
    prog_snap = """
h = api.height(1, 1)
assert h == 0, h
assert api.block(1, 0, 1) == "stone", api.block(1, 0, 1)
assert api.solid(1, 1, 1) is False
api.fill((0, 0, 0), (2, 0, 2), "stonebrick")
"""
    payload2, stats2 = B.compile_build(prog_snap, (0, 64, 0), "south", B.block_ids(), snap)
    assert stats2["snapshot"] and stats2["cells"] == 9, stats2
    # 未知方块("?")按空气处理, height 跳过它继续往下找
    snap2 = {"o": [0, 64, 0], "s": [1, 2, 1], "p": ["?", "stone"], "rle": "0:1,1:1"}
    _, stats3 = B.compile_build("h = api.height(0, 0)\napi.fill((0,0,0),(0,0,0),'stone')",
                                (0, 64, 0), "south", B.block_ids(), snap2)
    assert stats3["snapshot"], stats3
    print("建造读世界(快照)自测 OK")

    # 多格方块: 门/高草展开成两格, 床只写一格(引擎自动生成床尾)
    prog_multi = """
api.set(0, 0, 0, "wooden_door", {"direction": 0})
api.set(3, 0, 0, "bed", {"direction": 0})
api.set(6, 0, 0, "tall_grass")
"""
    pm, sm = B.compile_build(prog_multi, (0, 64, 0), "south", B.block_ids())
    assert sm["cells"] == 5, sm          # 门2 + 床1 + 草2
    kinds = [e["b"] for e in pm["p"]]
    assert kinds.count("minecraft:wooden_door") == 2, kinds
    assert kinds.count("minecraft:bed") == 1, kinds
    assert kinds.count("minecraft:tall_grass") == 2, kinds
    bed = [e for e in pm["p"] if e["b"] == "minecraft:bed"][0]
    assert "head_piece_bit" not in (bed.get("s") or {}), bed   # 床头/床尾由引擎决定
    door_states = sorted(e["s"]["upper_block_bit"] for e in pm["p"]
                         if e["b"] == "minecraft:wooden_door")
    assert door_states == [False, True], door_states
    print("多格方块展开自测 OK")

    # 对称检查: 包围盒中线 / 显式对称轴
    asym = 'api.fill((0,0,0),(6,4,6),"stonebrick")\napi.set(-1,0,3,"stonebrick")'
    _, s1 = B.compile_build(asym, (0, 64, 0), "south", B.block_ids(), None, "u:3")
    assert s1["checks"]["symmetry"]["mismatch"] == 1, s1["checks"]["symmetry"]
    _, s2 = B.compile_build('api.fill((-3,0,0),(3,4,6),"stonebrick")',
                            (0, 64, 0), "south", B.block_ids(), None, "u")
    assert s2["checks"]["symmetry"]["mismatch"] == 0, s2["checks"]["symmetry"]
    # 悬空检查: 只在快照覆盖范围内判断; 没有快照就如实说"没检查"
    snap_f = {"o": [0, 63, 0], "s": [5, 4, 5], "p": ["grass_block", "air"],
              "rle": "0:25,1:75", "unloaded": 0}
    _, s3 = B.compile_build('api.fill((0,0,0),(4,0,4),"stonebrick")\n'
                            'api.set(2, 2, 2, "stonebrick")',
                            (0, 64, 0), "south", B.block_ids(), snap_f)
    assert s3["checks"]["floating"]["count"] == 1, s3["checks"]["floating"]
    _, s4 = B.compile_build('api.fill((0,0,0),(4,0,4),"stonebrick")',
                            (0, 64, 0), "south", B.block_ids(), snap_f)
    assert s4["checks"]["floating"]["count"] == 0, s4["checks"]["floating"]
    _, s5 = B.compile_build('api.fill((0,0,0),(4,0,4),"stonebrick")',
                            (0, 64, 0), "south", B.block_ids(), None)
    assert s5["checks"]["floating"]["checked"] is False, s5["checks"]["floating"]
    print("对称/悬空校验自测 OK")

    # 标准库糖: 屋顶(逐层内缩) 与 楼梯(逐阶升高)
    _, r1 = B.compile_build('api.roof((0,0,0),(4,0,4),"stonebrick")',
                            (0, 64, 0), "south", B.block_ids())
    assert r1["cells"] == 45, r1          # 5×5 + 5×3 + 5×1
    _, r2 = B.compile_build('api.roof((0,0,0),(4,0,4),"stonebrick",style="hip")',
                            (0, 64, 0), "south", B.block_ids())
    assert r2["cells"] == 35, r2          # 25 + 9 + 1
    _, r3 = B.compile_build('api.roof((0,0,0),(4,0,4),"stonebrick",hollow=True)',
                            (0, 64, 0), "south", B.block_ids())
    assert r3["cells"] == 33, r3          # 16 + 12 + 5(逐层只铺外圈)
    _, r4 = B.compile_build('api.roof((0,0,0),(4,0,4),"stonebrick",y=None)'
                            if False else 'api.stair((0,0,0),(0,0,4),"stonebrick")',
                            (0, 64, 0), "south", B.block_ids())
    assert r4["cells"] == 5, r4           # 5 阶, 每阶 1 格深
    _, r5 = B.compile_build('api.stair((0,0,0),(2,0,4),"stonebrick",rise=2,run=2)',
                            (0, 64, 0), "south", B.block_ids())
    assert r5["cells"] == 15, r5          # 3 阶 × 3 格宽 × (2+2+1 格深)
    print("屋顶/楼梯糖自测 OK")

    # 建造进度转发: 只转发当前操作, 受开关与节流控制
    _side, _sent = bot2.bridge.say_side, []
    bot2.bridge.say_side = lambda *a, **k: _sent.append(a)
    try:
        bot2._build_active = "b1"
        bot2._build_progress_at = 0
        bot2.cfg["build_progress"] = True
        bot2.cfg["build_progress_min_sec"] = 0
        bot2._on_build_progress("b1", "d", 40, 100)
        assert _sent and "40/100" in _sent[-1][1] and "核对现场" in _sent[-1][1], _sent
        bot2._on_build_progress("b2", "v", 90, 100)      # 不是当前操作 -> 不转发
        assert len(_sent) == 1, _sent
        bot2._on_build_progress("b1", "w", 2, 8)         # 写入阶段用「批」
        assert "2/8 批" in _sent[-1][1], _sent[-1]
        bot2.cfg["build_progress"] = False
        bot2._on_build_progress("b1", "v", 60, 100)      # 开关关掉 -> 不转发
        assert len(_sent) == 2, _sent
    finally:
        bot2.bridge.say_side = _side
        bot2._build_active = None
        bot2.cfg["build_progress"] = True
    print("建造进度转发自测 OK")

    # 视觉反馈: 编解码往返 + 三种视角 + PNG 写入
    from . import render as R
    p3, st3 = B.compile_build('api.fill((0,0,0),(2,0,2),"stonebrick")\n'
                              'api.fill((0,1,0),(2,1,0),"oak_planks")',
                              (0, 64, 0), "south", B.block_ids())
    pal3, cel3, bnd3 = B.decode_payload(p3)
    assert len(cel3) == st3["cells"], (len(cel3), st3["cells"])
    front = R.ascii_view(pal3, cel3, bnd3, "front")
    assert "stonebrick" in front and "oak_planks" in front, front
    assert front.splitlines()[1] == "===" and front.splitlines()[2] == "###", front
    top = R.ascii_view(pal3, cel3, bnd3, "top")
    assert top.count("=") >= 3, top                            # 俯视看到顶层木板
    iso = R.ascii_view(pal3, cel3, bnd3, "iso")
    assert "等距视图" in iso and "=" in iso, iso
    png = R.write_png("/tmp/viktor-render-test.png", R._pixels(pal3, cel3, bnd3, "front"), 2)
    raw = png.read_bytes()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n" and raw[12:16] == b"IHDR", raw[:16]
    assert int.from_bytes(raw[16:20], "big") == 6, raw[16:20]      # 3 列 × scale 2
    png.unlink(missing_ok=True)
    print("视觉反馈(渲染/PNG)自测 OK")

    # 蓝图墙: 马赛克配色与朝向
    palB, celB, bbB, wB, hB = R.blueprint_cells(pal3, cel3, bnd3, "front",
                                                (10, 70, 5), "south")
    assert (wB, hB) == (3, 2), (wB, hB)
    assert len(celB) == 6, celB                     # 全像素铺满(含背景)
    blocks = {str(e["b"]) for e in palB[1:]}
    assert "minecraft:brown_concrete" in blocks, blocks   # 木板 -> 棕
    assert "minecraft:light_gray_concrete" in blocks, blocks  # 石头 -> 浅灰
    assert all(z == 5 for (_x, _y, z) in celB), celB       # 朝南 -> 同一 z 平面
    _p, celE, _b, _w, _h = R.blueprint_cells(pal3, cel3, bnd3, "front",
                                             (10, 70, 5), "east")
    assert all(x == 10 for (x, _y, _z) in celE), celE      # 朝东 -> 同一 x 平面
    print("蓝图墙(马赛克)自测 OK")

    # 模式门禁: 建造工具只在创造模式家族可见(用户明确要求)
    for mode in (MODE_NORMAL, MODE_PLAN, MODE_EXECUTE, MODE_ONESHOT):
        names = bot2._allowed_tools(mode)
        assert not ({"build_preview", "build_commit", "build_undo", "build_status"} & names), \
            (mode, sorted(names))
    for mode in (MODE_CREATIVE, MODE_CREATIVE_MAX):
        names = bot2._allowed_tools(mode)
        assert {"build_preview", "build_commit", "build_undo", "build_status"} <= names, mode
    print("建造工具模式门禁自测 OK(仅 creative / creative_max)")

    # 渲染: 预览 / 提交 / 撤销
    pv = bot2._render_build_preview("b1-1", {
        "ok": True, "jid": "b1-1", "name": "小屋", "cells": 531, "paletteSize": 6,
        "bounds": {"from": [0, 64, 0], "to": [10, 73, 8]},
        "diff": {"place": 385, "replace": 0, "noop": 146, "unloaded": 0},
        "plan": {"boxes": 26}, "warnings": [], "samples": {},
    }, {"size": (11, 10, 9), "ops": 9, "cells": 531, "palette": 6})
    assert "新放置 385" in pv and "26 个批量填充" in pv and "build_commit" in pv, pv
    cm = bot2._render_build_commit("b1-1", {
        "ok": True, "jid": "b1-1", "changed": 531, "boxes": 26, "ms": 89, "undoDepth": 1,
        "verify": {"mismatch": 2, "holes": 1, "wrong": 1,
                   "samples": [[1, 64, 1, "air"], [2, 64, 2, "dirt"]]},
    })
    assert "531 格" in cm and "空洞 1" in cm and "(1, 64, 1) 实际是 air" in cm, cm
    assert "不要直接" in cm or "补丁程序" in cm, cm
    ok = bot2._render_build_commit("b1-1", {
        "ok": True, "jid": "b1-1", "changed": 10, "boxes": 2, "ms": 5,
        "verify": {"mismatch": 0, "holes": 0, "wrong": 0, "samples": []},
    })
    assert "全部正确" in ok, ok
    # 幂等: 已经正确的格子跳过不写
    idem = bot2._render_build_commit("b1-1", {
        "ok": True, "jid": "b1-1", "changed": 0, "boxes": 0, "ms": 3, "noop": 108,
        "verify": {"mismatch": 0, "holes": 0, "wrong": 0, "samples": []},
    })
    assert "108 格本来就对" in idem, idem
    print("建造渲染自测 OK")

    r = bot2._tool_run_command({"command": "list"})
    assert r.strip() and "禁止" not in r, r
    print(r)
    print("capabilities self-test OK")

