# 架构与代码结构

维克托把 Minecraft 基岩版服务器聊天接入大模型。默认模型是 DeepSeek Flash，也支持按会话选择其他模型档案。
运行时只使用 Python 3.11+ 标准库，无第三方 Python 依赖。

## 1. 系统数据流

```text
   ┌── 玩家聊天（行为包 viktor_bridge）/ 进出服（BDS 原生日志）/ 查询回包（[VIKTOR-*] r<id>）
   ▼
bedrock_server ───► screen 日志（logs/server.log）
   ▲                     │ tail 解析（viktor/bot_app.py）
   │                     ▼
   │            会话上下文（append-only，稳定前缀）
   │                     │
   │          Agent 循环（viktor/bot_agent.py）⇄ 模型 API
   │                     │ function calling 工具执行
   │          capabilities.py + viktor/bot_tools.py
   │                     │
   └── screen -X stuff ◄─┘
       tellraw 回复 / 服务端指令 / scriptevent 查询
```

- BDS 控制台不回显玩家聊天，因此聊天由行为包订阅后写入日志。
- `ScreenBridge` 用 `screen -S mc -X stuff` 注入 tellraw、服务器指令和 scriptevent。
- `ServerBus` 给查询分配请求 id，批量下发并按 `[VIKTOR-*] r<id>` 路由回包。
- 普通聊天由模型判断回复或沉默，不靠硬编码指令词；控制面词例外，见[运维与控制面](operations.md)。
- 会话日志平时只追加、不重排、不做滑动窗口；只有压缩/智能压缩会有意重写上下文，见[会话与上下文](conversation.md)。

## 2. 分层与依赖方向

`bot.py` 只负责命令行入口和启动，实现位于 `viktor/`。上层可以依赖下层，下层不得反向依赖上层；
职责 mixin 之间不互相 import，只通过组合后的 `self.*` 和 MRO 协作。

```text
bot.py（入口） → viktor.selftest（--test）
                   │
        viktor.Bot = BotCoreMixin + BotControlMixin + BotToolsMixin
                     + BotBuildMixin + BotAgentMixin + BotAppMixin
                   │
        session / bus / bridge / config / profiles / models
                   │
        paths / constants / prompts / schemas / models（叶子层）
```

## 3. 模块职责

| 模块 | 职责 |
|---|---|
| `bot.py` | 参数解析、`--test`、`--resume` 与启动 |
| `viktor/__init__.py` | 组合 `Bot` 与职责 mixin，声明依赖方向 |
| `viktor/bot_core.py` | 构造、请求上下文、会话生命周期、待处理队列、能力注册 |
| `viktor/bot_control.py` | 控制词、一次性对话调度、计划模式、恢复会话 |
| `viktor/bot_tools.py` | 聊天、查询、指令、记忆、常加载、模式切换等工具 handler |
| `viktor/bot_agent.py` | 模型参数、function calling 循环、worker、插话安全点、收尾汇报 |
| `viktor/bot_app.py` | `logs/server.log` tail、事件解析、启动握手、主循环 |
| `viktor/bot_build.py` | 建造工具编排、上传、预览、提交、撤销、状态与渲染 |
| `viktor/build.py` | 受限 Python 沙箱、体素化、坐标变换、KEEP/RLE 编码、编译期检查 |
| `viktor/buildlib/` | 216 个几何/构件/装饰/生成器函数；`registry.py` 是签名元数据唯一来源 |
| `viktor/render.py` | 字符图、PNG 与游戏内蓝图 |
| `viktor/session.py` | `Session` append-only 上下文、压缩与 `OneShotContext` |
| `viktor/bus.py` | 服务端请求总线、批量请求、分帧重组 |
| `viktor/bridge.py` | screen 注入、tellraw、控制台命令与输出等待 |
| `viktor/profiles.py` | 提示词 × 数值限制 × 工具白名单的模式组合表 |
| `viktor/models.py` | 模型档案、触发词、上下文窗口、输出与思考参数映射 |
| `viktor/config.py` / `viktor/paths.py` | 配置读取 / 路径、日志与运行时状态文件 |
| `viktor/prompts.py` / `viktor/schemas.py` / `viktor/constants.py` | 提示词 / 工具 schema / 正则、控制词与协议常量 |
| `viktor/history.py` | 会话清单与按压缩口径读取历史 |
| `viktor/wiki.py` | Minecraft Wiki 搜索、页面解析与配方/表格文本化 |
| `viktor/webfetch.py` | URL 读取、SSRF 防护、网页正文与图片处理 |
| `viktor/selftest.py` | 标准库自测入口 |
| `capabilities.py` | 能力注册表、ptc 调度、记忆、技能书、物品速查 |
| `behavior_pack/viktor_bridge/` | BDS 行为包唯一源码，负责聊天桥、空间查询与建造执行 |
| `skills/` | 按需载入的技能书及参考资料 |
| `tools/` | 物品表、函数文档和技能指导文本生成器 |

## 4. 常见修改入口

| 需求 | 通常需要修改 |
|---|---|
| 新增模型工具 | `viktor/schemas.py` + 对应 handler + `capabilities.register()`；必要时更新 `profiles.py` 白名单 |
| 调整模式行为 | `viktor/profiles.py`；行为文字在 `viktor/prompts.py`，数值来自 `config.json` |
| 新增模型供应商 | `config.json` 的 `models`；特殊请求映射在 `viktor/models.py` / `bot_agent.py` |
| 修改会话策略 | `viktor/session.py` + `bot_control.py` / `bot_agent.py` |
| 修改行为包协议 | `viktor/constants.py`、`viktor/bus.py` 与行为包脚本同步修改 |
| 修改建造 API | `viktor/build.py`、`bot_build.py`、`schemas.py`，必要时同步行为包 |
| 新增建筑函数 | 对应 `viktor/buildlib/*.py` + `registry.py`，再生成函数文档 |
| 新增技能 | `skills/<name>/SKILL.md`，通常无需改代码 |

任何影响玩家可见行为、权限、协议或配置的修改，都应同步更新对应文档和自测。

## 5. 运行时文件

| 路径 | 用途 |
|---|---|
| `config.json` | 本地配置与 API key；已 gitignore，不提交 |
| `memory.md` | 长期记忆；已 gitignore，更新前自动备份 |
| `logs/server.log` | screen 捕获的服务端控制台输出，是 Bot 的主要数据源 |
| `logs/bot.log` | 运行日志、重试细节与思考链；可能含敏感上下文 |
| `logs/agent.state` | PID、busy、队列、备份、模式等状态快照 |
| `logs/sessions/session-*.jsonl` | 可恢复的主会话落盘 |
| `logs/sessions/compact-*.jsonl` | 压缩前留档，仅供排障，不参与自动恢复 |
| `logs/oneshot/` | 每次一次性对话的独立记录 |
| `logs/memory-backup/` | 长期记忆更新前备份 |
| `logs/renders/` | 建造计划和世界区域的 PNG 渲染 |
| `data/raw_ids.txt` | 行为包导出的原始物品/方块 ID |
| `data/items.json` | 生成的 ID、译名、分类与别名速查表 |
| `data/item_aliases.json` | 手工维护的同义词、Java 名和口语别名 |

`logs/`、`memory.md`、`config.json` 均不应提交。`paths` 中运行时可重绑的路径必须按 `paths.X` 读取，
不要 from-import 固定值，否则自测重绑不会生效。

## 6. 延伸阅读

- [运行模式](modes.md)
- [会话、上下文与模型](conversation.md)
- [工具与并发](tools.md)
- [行为包与请求总线](behavior-pack.md)
- [建造引擎](build-engine.md) / [建筑函数库](buildlib.md)
- [配置参考](configuration.md) / [运维与控制面](operations.md)
