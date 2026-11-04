#!/usr/bin/env python3
"""
mc-ai-bot 入口: 把 MC 基岩版服务器(screen 会话)的聊天接入大模型
(默认 DeepSeek; 「清空k」可开一个 Kimi 模型的新会话, 见 viktor/models.py)。

工作方式:
  - tail screen 日志(logs/server.log) 解析玩家聊天/进出服事件
  - 玩家全部离开(→0)不结束会话, 任务可跨离线期继续; 玩家数 0→1 时完整初始化新会话
  - 每条玩家聊天都进上下文, 是否回应由模型判断; "1 " 开头触发与主对话隔离的一次性对话
  - 通过 screen stuff 注入 tellraw 命令回复到游戏内

实现按职责拆在 viktor/ 包内(依赖方向见 viktor/__init__.py 的分层图):
  - viktor/bot_core.py     构造、请求上下文、会话生命周期、待处理队列
  - viktor/bot_control.py  控制词/恢复会话/一次性对话
  - viktor/bot_tools.py    能力工具 handler(聊天/查询/指令/常加载/备份/模式)
  - viktor/bot_agent.py    function calling 循环与模式参数(请求按当前模型档案拼)
  - viktor/models.py       模型档案(触发词/模型名/Base URL/key/窗口/思考强度映射)
  - viktor/bot_app.py      服务器日志 tail 解析与主循环
  - viktor/selftest.py     python3 bot.py --test 的自测

缓存命中设计(DeepSeek 前缀缓存):
  - system prompt 是常量, 长期记忆/当前模式不写进去, 而是作为「系统注记」追加在日志里
  - 会话内消息只追加、不修改、不重排(append-only); 切模式/更新记忆只追加尾部
  - 会话边界即上下文边界, 天然短上下文, 逐轮请求前缀一致 -> 稳定命中缓存
"""
import sys

from viktor import Bot
from viktor.config import load_config


def main() -> None:
    if "--test" in sys.argv:
        from viktor.selftest import self_test
        self_test()
        return
    bot = Bot(load_config())
    if "--resume" in sys.argv:
        bot.resume_session(sys.argv[sys.argv.index("--resume") + 1])
    bot.run()


if __name__ == "__main__":
    main()
