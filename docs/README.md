# 文档导航

根目录 [README](../README.md) 只保留项目介绍、快速开始和入口链接；实现细节按模块放在这里。
修改代码时，应更新对应文档，而不是把技术细节重新堆回根 README。

## 系统与对话

| 文档 | 内容 | 主要代码依据 |
|---|---|---|
| [架构与代码结构](architecture.md) | 数据流、依赖方向、模块职责、运行时文件 | `viktor/__init__.py`、`bot.py` |
| [运行模式与对话策略](modes.md) | normal/creative/plan/execute/oneshot、沉默、插话、轮次收尾 | `profiles.py`、`prompts.py`、`bot_agent.py` |
| [会话、上下文与模型](conversation.md) | 生命周期、append-only、模型档案、压缩、恢复 | `session.py`、`models.py`、`bot_control.py` |
| [工具、资料查询与并发](tools.md) | function calling、ID/Wiki/URL/历史、ptc、指令安全 | `schemas.py`、`capabilities.py` |

## Minecraft 与建造

| 文档 | 内容 | 主要代码依据 |
|---|---|---|
| [行为包协议与请求总线](behavior-pack.md) | v3/v4 协议、分帧、空间查询、ServerBus、热重载 | `behavior_pack/`、`bus.py`、`constants.py` |
| [建造引擎](build-engine.md) | 当前 preview/commit/verify/undo、沙箱、API、快照、渲染 | `build.py`、`bot_build.py`、`render.py` |
| [建筑函数库](buildlib.md) | `api.lib` 的移植语义、8 类 216 函数、生成文档流程 | `buildlib/`、`registry.py` |
| [技能书](skills.md) | 按需加载、目录规范、9 本内置技能、生成物维护 | `skills/`、`capabilities.py` |

## 部署与维护

| 文档 | 内容 |
|---|---|
| [配置参考](configuration.md) | config.json 全量配置、模型档案、环境变量 |
| [运行、运维与控制面](operations.md) | 部署、自测、重启、控制词、停止、备份、错误呈现 |
| [行为包源码说明](../behavior_pack/README.md) | 软链接、依赖、reload 与源码唯一性 |
| [技能来源与生成规则](../skills/README.md) | 原 Java 类到技能文档的对应关系、未移植函数替代 |

## 文档维护约定

- 行为、权限、默认值和限制以当前代码为准；示例配置以 `config.example.json` 为准。
- `docs/build-engine.md` 是当前实现文档，不是阶段提案；不要恢复已删除的 `p2-build-engine.md` 中的历史状态。
- 函数签名由 `viktor/buildlib/registry.py` 生成到技能 references，避免双份手工维护。
- 文档中的 `/home/jrj/...` 仅是部署机示例；开发设备与服务器环境的操作边界见根目录 `AGENTS.md`。
- 修改文件路径、协议版本或模块职责后，同时检查所有 Markdown 链接和交叉引用。
