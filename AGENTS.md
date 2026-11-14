# AGENTS.md — mc-ai-bot 工作指南

> 给在本仓库工作的 AI Agent。先判断自己位于**开发设备**还是**已部署 MC 服务器**，再决定可执行的操作。
> 项目介绍见 [README.md](README.md)，技术细节入口见 [docs/README.md](docs/README.md)。

## 0. 第一原则：区分开发设备与部署服务器

同一个仓库可能同时存在于开发机和生产服务器。**仓库里出现部署路径、脚本或运维文档，不代表当前机器正在运行 MC。**

### 0.1 开发设备

典型情况：本地只有源码；没有 `/home/jrj/minecraft-bedrock`，没有 screen `mc` / `viktor`，没有 `logs/agent.state`，
也可能不是 Linux。

可以做：

- 阅读和修改代码、文档、配置示例；
- `python3 bot.py --test`；
- `node --check behavior_pack/viktor_bridge/scripts/main.js`（有 Node 时）；
- 不需要线上服务的生成器 `--check`、静态检查和 git 操作。

不要做：

- 不假定 `screen`、BDS、世界、行为包软链接、备份目录或线上会话存在；
- 不执行 `run.sh`、`restart.sh`、BDS `reload`、`save hold`、世界扫描或任何生产重启；
- 不伪造“已实机验证/已 reload/玩家无感”的结论；
- 不为了测试读取或提交真实 `config.json`、`memory.md`、`logs/` 中的秘密；
- 不引用 `/home/jrj/scripts` 等部署机脚本，除非已确认当前机器和文件都存在。

如果用户要求线上验证而当前是开发设备，应明确说明只能完成离线验证，并列出需要在服务器执行的后续步骤。

### 0.2 已部署 MC 服务器

参考部署布局（**先核实，不要直接假定**）：

| 项目 | 参考路径/名称 |
|---|---|
| Bot 仓库 | `/home/jrj/repo/mc-ai-bot` |
| BDS | `/home/jrj/minecraft-bedrock` |
| 世界 | 由 `server.properties` 的 `level-name` 决定，参考部署为 `worlds/OSCP` |
| 行为包 | 服务器的 `behavior_packs/viktor_bridge` 软链接到仓库源码 |
| screen | `mc` = BDS，`viktor` = Bot |
| 状态 | `logs/agent.state` |
| 备份 | 参考为 `/home/jrj/mc_backup`，以 config 为准 |
| 外部运维脚本 | `/home/jrj/scripts` 仅在这台部署机可能存在，不属于本仓库 |

只有在确认当前路径、进程和状态都符合后，才适用以下规则：

1. **玩家优先、影响最小化**：有玩家或 Bot 忙时优先只读；不要重启、reload、备份、扫描或改世界。
2. **先查 busy**：`busy = agent_busy or pending 非空 or 智能压缩运行中`。busy 时不要清空、压缩、备份或重启。
3. **不污染 mc 控制台**：注入命令会进入 `server.log`，可能干扰 Bot。测试应短、可逆、可预期，优先只读。
4. **优雅重启**：代码和配置改完先自测，再在空闲时用 `./restart.sh`；不要常规 `kill -9`。
5. **BDS 重启后重挂日志**：重新执行 `run.sh` 或重启 Bot，否则 screen 日志失效。
6. **行为包 reload 有副作用**：会中断扫描并清空建造暂存/撤销栈；只在空闲时做，随后用 hello 验证。
7. **备份走 save hold/resume**：不要直接复制写入中的 worlds；无论成功失败都要恢复世界写入。

### 0.3 无法判断时

按开发设备/只读环境处理。先检查当前目录、必要路径和进程；仍不确定就向用户说明，不要试探性执行生产命令。
文档中的命令按所处环境选择，不要“为了完整测试”把开发和部署两套步骤都跑一遍。

## 1. 项目速览

- Minecraft 基岩版智能管家，默认 DeepSeek Flash，支持会话级模型档案。
- Python 3.11+，**零第三方 Python 依赖**；不要无理由引入包管理文件或新依赖。
- BDS 通过 screen 日志与 Bot 通信，行为包负责聊天桥、空间查询和建造执行。
- `bot.py` 是入口，业务实现都在 `viktor/`；`capabilities.py` 是能力注册和 ptc 调度中心。
- 当前行为包协议 v4；建筑函数库为 8 类 216 个函数。

详细架构：[docs/architecture.md](docs/architecture.md)。

## 2. 代码边界与不变量

### 2.1 依赖方向

```text
bot.py
  → BotCore / BotControl / BotTools / BotBuild / BotAgent / BotApp（职责 mixin）
  → session / bus / bridge / config / profiles / models
  → paths / constants / prompts / schemas
```

- mixin 之间不要互相 import；通过组合后的 `self.*` 协作。
- 下层不得 import 上层，避免循环依赖。
- `paths` 的可重绑值按 `paths.X` 读取，不要 from-import 固定值。

### 2.2 上下文

- 会话平时 append-only；切模式、更新记忆只追加系统注记，不重写固定前缀。
- 不在 tool_calls 与 tool 响应之间插入其他消息；中断时补齐工具响应。
- 只有普通压缩、智能压缩和完整初始化可以重建上下文。
- 模型是会话级状态，会话内不能换；一次性对话始终用默认 flash。

详见 [docs/conversation.md](docs/conversation.md)。

### 2.3 工具与权限

新增/修改工具时同步检查：

1. `viktor/schemas.py` 或 `capabilities.py` 的 schema；
2. handler 与 `capabilities.register()`；
3. concurrency：parallel / bus / serial；
4. `viktor/profiles.py` 的每个模式白名单和执行层黑名单；
5. ptc 是否可绕过限制、子线程是否继承限制；
6. 自测、[docs/tools.md](docs/tools.md) 和相关技能书。

特别注意：建造事务工具只在 creative/creative_max；pin_region 只在 creative 家族可用。

### 2.4 行为包协议

修改协议必须同步：行为包 JS、`constants.py` 路由/版本、`bus.py` 编解码、相关工具与文档。
保持请求 id、DONE、分帧、缺帧失败和超时语义一致。建造上行 560 字符/帧，一帧一次 screen stuff。

详见 [docs/behavior-pack.md](docs/behavior-pack.md)。

### 2.5 建造引擎

- Bot 编译纯几何，行为包读写世界；不要给沙箱增加文件、网络或直接世界访问。
- KEEP 表示“不写也不删”；挖空必须显式 air。
- commit 重新 diff，完成后 verify；mismatch 和 unloaded 要分开报告。
- 多格方块当前由编译器处理，不要恢复旧设计中“一律拒绝门/床/高草”的规则。
- `docs/build-engine.md` 描述当前实现；已删除的 `p2-build-engine.md` 是过时阶段文档，不要当作事实来源。

详见 [docs/build-engine.md](docs/build-engine.md)。

## 3. 常用检查

在仓库根目录：

```bash
# 必跑：离线自测
python3 bot.py --test

# 修改行为包 JS 后（开发/服务器都可做静态检查）
node --check behavior_pack/viktor_bridge/scripts/main.js

# 修改建筑函数/registry 后
python3 tools/gen_buildlib_docs.py
python3 tools/gen_buildlib_docs.py --check

# 修改生成技能文本的来源后（需要原模组文件，开发机没有就说明跳过原因）
python3 tools/gen_skill_guides.py
python3 tools/gen_skill_guides.py --check
```

不要为通过测试而删除权限校验、放宽沙箱、跳过配对检查或改写预期事实。
当前完整 selftest 含有部署机备份前置条件，会检查 `/home/jrj/minecraft-bedrock/worlds/Bedrock level`。
开发设备若在该断言处失败，应记录为**环境依赖未满足**，保留此前已通过的检查输出；不要创建假的线上目录来假装全绿，
也不要因此执行真实备份。其余代码若在此之后还有自测，需在具备测试 fixture 的环境继续验证。
开发设备不能完成 BDS 实测时，在结果中明确区分“离线自测通过/部分通过”与“线上未验证”。

## 4. 文档与生成物

文档入口：[docs/README.md](docs/README.md)。

- 根 README 保持简洁：介绍、特性、快速开始、基本用法、目录和文档链接；技术细节放对应 docs。
- 改行为就改对应模块文档，不要只更新根 README 或 AGENTS。
- `viktor/buildlib/registry.py` 是函数签名元数据唯一来源；改函数后重跑 `gen_buildlib_docs.py`。
- `tools/gen_skill_guides.py` 生成的技能理论文档不要手改；没有原类来源时保留并说明无法重生成。
- `skills/README.md` 记录原 Java 类与技能文档的对应关系。
- 更新路径、工具名、协议号或文件名后，检查 Markdown 链接和代码中的文档引用。

## 5. 配置、秘密与运行数据

- `config.json`、`memory.md`、`logs/` 已 gitignore，不得提交。
- 示例秘密只写占位符到 `config.example.json`；不要把真实 key 复制进文档、测试输出或补丁。
- 会话、日志、记忆和备份可能含玩家私人信息；读取应出于明确任务需要，分享前脱敏。
- 施工台账 `logs/build_ledger.jsonl` 与程序源码 `logs/programs/` 同样属于运行数据，不提交；
  台账是 append-only 派生数据，删掉只会丢历史查询，不影响世界与会话。升级后回填一次
  `python3 tools/backfill_build_ledger.py`（建议 bot 停止时跑），幂等可重复。
- 不把开发机配置覆盖到服务器，也不把服务器配置/会话无条件拷回开发机。
- `/home/jrj/...` 是参考部署路径；跨环境修改时使用当前仓库相对路径或先确认实际配置。

## 6. 按任务类型的完成标准

### 改 Python / 工具 / 会话

- 保持依赖方向和上下文不变量；
- 更新 schema、profile、自测与模块文档；台账（`viktor/ledger.py`）写入点与工具输出要保持
  “模型无需额外输出”这一前提，不要为了记录给模型加参数或强制工具调用；
- `python3 bot.py --test` 通过；若开发设备因上述部署目录断言中止，明确报告未覆盖的后续检查；
- 服务器部署需在空闲时再平滑重启，开发设备不要尝试。

### 改行为包 / 总线

- 两端协议同步，JS 语法检查与 Python 自测通过；
- 服务器实测前确认 Bot 空闲，reload 后验证 hello/caps 和短小只读查询；
- 开发设备明确标注未做线上握手。

### 改建造 / buildlib

- 编译器与行为包限额、编码一致；
- 修改 registry 并生成函数文档；
- 自测通过；视觉验证优先 preview/render，只有授权且空闲才写世界。

### 只改文档

- 核对当前代码，不复制旧阶段文档的限制和权限；
- README 不再堆技术细节；
- 检查相对链接、文件路径和开发/服务器措辞；
- 不需要为了 Markdown 修改去重启线上 Bot。

## 7. 延伸阅读

- [运行模式](docs/modes.md)
- [工具与 ptc](docs/tools.md)
- [配置参考](docs/configuration.md)
- [运行与运维](docs/operations.md)
- [行为包源码](behavior_pack/README.md)
- [技能来源](skills/README.md)
