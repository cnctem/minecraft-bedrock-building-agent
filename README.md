# mc-ai-bot

使用 DeepSeek 模型与 API 服务，在 Minecraft 基岩版服务器中完成**感知 → 规划 → 执行 → 校验 → 修复**的 Agent 闭环。

玩家直接在游戏里提出需求，agent 通过工具读取现场、查询资料、编写受限 Python 建造程序，
预览差异与渲染图后提交，依据校验结果修复，也可以撤销施工。运行时仅依赖 **Python 3.11+ 标准库**。

## 能力

- 自然对话、任务中插话、软停止与强制停止。
- 普通、创造、创造 max，以及隔离的一次性对话。
- 长期记忆、append-only 上下文、自动智能压缩与会话恢复。
- DeepSeek 原生联网搜索、网页读取与视觉；支持玩家图片直链和建造渲染图。
- 玩家、方块、地形、切面及区域感知，按需加载的 9 本技能书与 216 个建筑函数。
- 事务式建造、机器校验、修复、撤销，以及自动记录的施工台账。

## 快速开始

离线自测无需 API key、私人配置或 Minecraft：

```bash
python3 bot.py --test
```

部署需要 Linux、Python 3.11+、screen 和已运行的 Bedrock Dedicated Server。
配置 DeepSeek 连接及 BDS screen 会话：

```bash
cp config.example.json config.json
```

填写 `api_key`；`api_base` 默认 `https://api.deepseek.com`，`model` 默认 `deepseek-flash`。
`screen_session` 指向 BDS 会话，默认 `mc`。完整参数见[配置参考](docs/configuration.md)。

按[行为包说明](behavior_pack/README.md)安装 `behavior_pack/agent_bridge`，启用脚本实验能力后启动：

```bash
./run.sh

# 或在独立 screen 会话中启动：
screen -dmS agent bash -c 'cd /path/to/mc-ai-bot && exec ./run.sh'
```

BDS screen 重建后需要重新启动 Agent，应用日志设置。
启动、空闲重启和恢复步骤见[运行文档](docs/operations.md)。

## 游戏内使用

直接与 agent 聊天，例如“agent，在我旁边设计并建造一座石桥”。

| 输入 | 作用 |
|---|---|
| `1 查一下我的坐标` | 与主会话隔离的一次性任务 |
| `0 玩家之间的聊天` | 不进入 Agent 上下文 |
| `停止` / `强制停止` | 到安全点停止 / 立即中止当前主任务 |
| `1 强制停止` | 中止全部一次性任务 |
| `不停止` | 撤销尚未生效的停止请求 |
| `清空` | 空闲时开始新会话 |
| `压缩` / `智能压缩` | 保留对话 / 生成工作摘要后重建上下文 |
| `恢复会话` | 空闲时恢复最近对话 |
| `正文开` / `正文关` | 显示或隐藏模型正文 |
| `工具开` / `工具关` | 显示或隐藏工具调用摘要 |

控制词需要完全匹配，由程序处理。

## 项目结构

```text
bot.py                         命令行入口与离线自测
agent/                         Agent、会话、总线、工具与建造引擎
capabilities.py                能力注册、ptc、记忆、技能与物品查询
behavior_pack/agent_bridge/    聊天、空间感知及建造执行
skills/                        技能书与参考资料
data/                          物品、方块与别名数据
tools/                         数据、台账与函数文档工具
docs/                          架构、协议和模块文档
run.sh / restart.sh            启动与空闲重启辅助
```

文档从 [docs/README.md](docs/README.md) 进入；贡献规则见 [AGENTS.md](AGENTS.md)。

## 使用边界

项目面向可信玩家的服务器。游戏内指令以控制台身份执行，主要限制来自指令黑名单、模式工具权限和建造沙箱，
并不提供细粒度玩家权限系统。部署前请阅读[工具与权限](docs/tools.md)。

`config.json`、`memory.md` 与 `logs/` 属于本地运行数据，已忽略，不应提交；分享日志前请脱敏。

## 许可证

[MIT](LICENSE) · Copyright (c) 2026 mc-ai-bot contributors
