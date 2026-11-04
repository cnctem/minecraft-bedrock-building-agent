# mc-ai-bot — 维克托

把 Minecraft 基岩版服务器的聊天接入大模型，让玩家在游戏中与智能管家**维克托·米哈伊洛维奇·切布里科夫**
（Viktor Chebrikov）交流。Bot 能判断何时回复或保持沉默，并通过 function calling 查询服务器、执行指令、
读取资料、保存长期记忆和完成可预览/校验/撤销的建造任务。

默认使用 DeepSeek Flash，也支持按会话配置其他 OpenAI 兼容模型。运行时仅依赖 **Python 3.11+ 标准库**。

## 特性

- **自然对话**：普通聊天无需命令前缀；模型结合对话状态决定接话或沉默，任务中也可插话调整。
- **多种工作模式**：普通、创造、创造 max，以及相互隔离的一次性对话。
- **长期上下文**：append-only 会话、稳定前缀缓存、普通/智能压缩、历史读取和断线恢复。
- **服务器与空间感知**：玩家坐标/手持、方块、高度图、切面、区域检查、物品 ID 与 Wiki 查询。
- **事务式建造**：受限 Python → preview → commit → verify → undo，支持字符图、PNG 和游戏内蓝图。
- **按需技能与函数库**：9 本技能书，以及 8 类 216 个几何、建筑、装饰和生成器函数。
- **可运维**：软/强制停止、状态与热备份控制词、平滑重启、正文/工具观察开关。

## 运行要求

开发设备：

- Python 3.11+；
- 修改行为包时建议安装 Node.js，用于 JavaScript 语法检查；
- 不需要本地安装 Minecraft，即可运行离线自测。

部署服务器（参考环境为 Linux）：

- 已运行的 Minecraft Bedrock Dedicated Server；
- `screen`，BDS 位于名为 `mc` 的会话；
- 本项目 `viktor_bridge` 行为包及所需 beta 脚本 API；
- 模型 API key；热备份另需 `7z`。

开发设备与线上服务器的操作边界见 [AGENTS.md](AGENTS.md)。不要把部署文档中的 `/home/jrj/...`
当成本机必然存在的路径。

## 快速开始

### 1. 配置

```bash
git clone <your-repository-url> mc-ai-bot
cd mc-ai-bot
cp config.example.json config.json
```

编辑 `config.json`，至少填写默认模型的 `api_key`，并按部署环境检查 `api_base`、模型名、
`mc_server_dir` 和 `backup_dir`。该文件已 gitignore，不要提交真实密钥。

完整字段见[配置参考](docs/configuration.md)。

### 2. 离线自测

```bash
python3 bot.py --test

# 修改过行为包时：
node --check behavior_pack/viktor_bridge/scripts/main.js
```

完整 selftest 目前含部署机世界目录的备份前置断言；开发设备缺少该 fixture 时，应记录失败点及未覆盖的后续检查，
不要为了“全绿”伪造服务器目录。详见[运维文档](docs/operations.md#3-自测与平滑重启)。

### 3. 部署行为包并启动（仅 MC 服务器）

将 `behavior_pack/viktor_bridge` 软链接到 BDS 的 `behavior_packs/`，启用对应实验脚本能力，然后：

```bash
./run.sh                      # 前台运行，并重新应用 screen 日志设置

# 或后台运行：
screen -dmS viktor bash -c 'cd /path/to/mc-ai-bot && ./run.sh'
```

行为包安装、beta 依赖和 reload 规则见[行为包说明](behavior_pack/README.md)与
[协议文档](docs/behavior-pack.md)。完整启动、重启和备份步骤见[运维文档](docs/operations.md)。

> MC 服务端或 screen 会话 `mc` 重启后，需要重新执行 `run.sh` 或重启 Bot，否则日志桥可能失效。

## 基本用法

直接聊天即可与维克托交流；只有以下前缀和控制词具有特殊含义：

| 输入 | 作用 |
|---|---|
| `1 查一下我的坐标` | 开启与主会话隔离的一次性对话 |
| `0 玩家们自己的聊天` | 静默消息：不交给模型、不回复、不唤醒会话 |
| `停止` / `强制停止` | 到安全点停止 / 立即中止主任务 |
| `清空` | 用默认模型开始全新会话 |
| `压缩` / `智能压缩` | 只留对话 / 用模型工作摘要重建上下文 |
| `恢复会话` / `恢复会话d` | 恢复最近会话，沿用原模型 / 强制默认模型 |
| `状态` / `备份` | 查询服务器状态 / 热备份世界 |
| `正文开`、`工具开` | 开启正文、工具调用的游戏内观察转发 |

所有硬编码控制词都需要完全匹配，不走模型，也不进入会话上下文。模型切换、并发限制和其余控制词见
[会话文档](docs/conversation.md)与[控制面总表](docs/operations.md#4-控制词总表)。

## 架构概览

```text
玩家聊天 / BDS 事件 / 行为包回包
              │
              ▼
       logs/server.log ──► Bot 会话与 Agent 循环 ──► 模型 API
              ▲                     │
              └──── screen 注入 ◄── function calling 工具
                    tellraw / 指令 / scriptevent
```

实现按职责拆在 `viktor/`，行为包执行世界内查询和建造。依赖方向、模块表和运行时文件见
[架构文档](docs/architecture.md)。

## 项目结构

```text
.
├── bot.py                     # 命令行入口与 --test
├── capabilities.py            # 能力注册、ptc、记忆、技能与物品查询
├── config.example.json        # 配置模板（真实 config.json 不提交）
├── viktor/                    # Bot、会话、总线、模型、工具与建造实现
├── behavior_pack/viktor_bridge/
├── skills/                    # 9 本按需加载的技能书
├── data/                      # 服务器 ID、译名与别名数据
├── tools/                     # 数据/文档生成器
├── docs/                      # 分模块技术文档
├── run.sh / restart.sh        # 部署启动与平滑重启
└── AGENTS.md                  # Agent 环境与贡献指南
```

## 文档

从 [docs/README.md](docs/README.md) 进入完整文档导航：

| 模块 | 文档 |
|---|---|
| 系统 | [架构](docs/architecture.md) · [模式与对话](docs/modes.md) · [会话与模型](docs/conversation.md) |
| 能力 | [工具与并发](docs/tools.md) · [技能书](docs/skills.md) |
| Minecraft | [行为包与总线](docs/behavior-pack.md) · [行为包源码](behavior_pack/README.md) |
| 建造 | [建造引擎](docs/build-engine.md) · [建筑函数库](docs/buildlib.md) |
| 维护 | [配置](docs/configuration.md) · [运行与运维](docs/operations.md) · [技能来源](skills/README.md) |

## 安全说明

本项目面向受信任的私人服务器，不提供细粒度玩家权限系统。任何能进服聊天的玩家都可请求 Bot 执行指令，
主要防护是 `command_blocklist`、模式工具白名单、URL SSRF 检查和建造沙箱。不要直接将其暴露给不可信公网玩家。

`config.json`、`memory.md` 和 `logs/` 可能包含密钥或玩家信息，均已 gitignore；分享日志前请脱敏。
