# 架构与代码结构

mc-ai-bot 使用 DeepSeek 驱动 Minecraft 基岩版 Agent。Python 只依赖标准库，行为包负责世界内读写。

## 数据流

```text
玩家聊天 / BDS 事件 / 行为包回包
             ↓
screen → logs/server.log → 事件解析与会话队列
             ↑                  ↓
        screen stuff ← 工具 ← Agent 循环 ⇄ DeepSeek API
             ↓
       查询 / preview → commit → verify → 修复或 undo
```

聊天由行为包写出 `[AGENT-CHAT]`，进出服使用 BDS 原生日志。
查询通过 `scriptevent agent:*` 发出，`ServerBus` 按请求 ID 收集 `[AGENT-*]` 回包。
运行模式管理行为、额度与工具权限；所有会话共用当前 DeepSeek 配置。

## 分层

```text
bot.py → agent.Bot
           BotCore + BotControl + BotTools + BotBuild + BotAgent + BotApp mixin
                              ↓
            session / bus / bridge / config / profiles
                              ↓
                paths / constants / prompts / schemas
```

mixin 之间不互相 import，借助组合后的实例协作。下层不依赖上层；可重绑路径通过 `paths.X` 访问。

## 模块职责

| 模块 | 职责 |
|---|---|
| `bot.py` | 启动、`--test`、`--resume` |
| `agent/bot_core.py` | 生命周期、队列、能力注册、图片注入、任务状态 |
| `agent/bot_control.py` | 停止、清空、压缩、恢复、显示开关及一次性任务 |
| `agent/bot_agent.py` | DeepSeek 请求、重试、工具调用、插话、worker 与收尾 |
| `agent/bot_tools.py` | 聊天、感知、指令、技能、常加载与历史工具 |
| `agent/bot_build.py` | 建造编译、上传、提交、校验、撤销、渲染编排 |
| `agent/build.py` / `agent/buildlib/` | 受限 Python、体素编码及建筑函数 |
| `agent/render.py` / `agent/images.py` | 字符图与 PNG / 图片 URL 识别 |
| `agent/session.py` | append-only 会话、配对修复、压缩及一次性上下文 |
| `agent/bus.py` / `agent/bridge.py` | 请求总线 / screen 命令与发言 |
| `agent/profiles.py` | 提示词、数值限制及工具白名单 |
| `agent/history.py` / `agent/ledger.py` | 历史定位、作品查询与自动台账 |
| `agent/runtime.py` | Linux 实例定位与空闲重启检查 |
| `agent/config.py` / `agent/paths.py` | 单套配置 / 可重绑路径 |
| `capabilities.py` | 工具注册、ptc、记忆、技能、物品表 |
| `behavior_pack/agent_bridge/` | 聊天、感知、快照与世界内建造 |
| `agent/selftest.py` | 独立临时目录内的完整离线自测 |

## 运行数据

`config.json` 保存连接配置；`memory.md` 保存当前长期记忆。
`logs/` 包括日志、会话、一次性任务、施工台账、程序源码、渲染图和 `agent.state`。
这些文件均被 Git 忽略。

台账在模式和施工事件发生时自动追加，不要求模型额外输出。
修改依赖方向、协议、工具权限或用户可见行为时，同步自测与对应文档。
