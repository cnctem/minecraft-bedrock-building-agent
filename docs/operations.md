# 运行、运维与控制面

本文区分**开发设备上的离线检查**和**已部署 MC 服务器上的运行操作**。不要在没有 BDS/screen 的开发设备上执行生产命令。
Agent 操作前还必须阅读根目录 `AGENTS.md` 的环境判断与红线。

## 1. 运行依赖

| 依赖 | 用途 |
|---|---|
| Python 3.11+ | Bot；仅使用标准库 |
| Linux / proc 工具 | 当前部署基线；状态、进程管理和部分资源限制依赖它 |
| `screen` | 捕获 BDS 控制台日志并注入命令 |
| Minecraft Bedrock Dedicated Server | 运行在名为 `mc` 的 screen 会话 |
| `viktor_bridge` 行为包与 beta 脚本 API | 聊天桥、空间查询、建造执行 |
| `7z` | 仅存档热备份需要 |
| 模型 API key | 默认 DeepSeek；其他模型按 models 档案配置 |

开发设备只需要 Python；若修改行为包，还建议有 Node.js 做 `node --check`。没有线上服务器不妨碍离线自测和文档开发。

## 2. 初次部署

### 2.1 配置

```bash
cd /path/to/mc-ai-bot
cp config.example.json config.json
# 编辑 config.json，填写 api_key，并检查模型、mc_server_dir、backup_dir 等路径
python3 bot.py --test
```

### 2.2 安装行为包（仅服务器）

将仓库中的 `behavior_pack/viktor_bridge` 链接到 BDS 的 `behavior_packs/`。目标不存在时才创建链接：

```bash
ln -s /path/to/mc-ai-bot/behavior_pack/viktor_bridge \
  /path/to/minecraft-bedrock/behavior_packs/viktor_bridge
```

仓库是行为包唯一源码，服务器侧保留软链接，不要复制成两份实体目录。启用世界实验脚本能力，并按
[行为包协议](behavior-pack.md#8-依赖与热重载) 检查 beta 依赖。

### 2.3 启动

确保 BDS 已在 screen 会话 `mc` 中运行，然后：

```bash
./run.sh
```

`run.sh` 会重新设置 screen 窗口宽度、日志路径、`log on` 和 `logfile flush 1`，再执行 `python3 bot.py`。

后台运行示例：

```bash
screen -dmS viktor bash -c 'cd /path/to/mc-ai-bot && ./run.sh'
screen -r viktor
# 离开 screen：Ctrl+A，然后 D；不要按 Ctrl+C 除非确实要停 Bot
```

**MC 服务端或 screen 会话 mc 重启后，必须重新执行 run.sh 或重启 Bot**，否则日志捕获可能失效，Bot 收不到聊天和回包。

## 3. 自测与平滑重启

开发/部署都可做离线检查：

```bash
python3 bot.py --test
node --check behavior_pack/viktor_bridge/scripts/main.js
```

注意：当前完整 selftest 的备份前置检查引用部署机世界目录 `/home/jrj/minecraft-bedrock/worlds/Bedrock level`。
开发设备没有该 fixture 时会在对应断言失败，这不代表需要安装或启动 BDS；应如实报告失败点和后续未覆盖检查，
不要伪造目录或执行生产备份。

仅在已部署服务器、确认唯一 Bot 进程且空闲时平滑重启：

```bash
./restart.sh
./restart.sh logs/sessions/session-YYYYmmdd-HHMMSS-sN.jsonl
./restart.sh <logs/sessions 下唯一的文件名子串>
```

脚本会：找到唯一 Bot → SIGTERM 优雅退出并落盘 → 选择 session → 在 screen `viktor` 中带 `VIKTOR_RESTORE` 启动 →
检查进程确实出现。它包含挂断和中断后的拉起兜底，但不替代“先确认空闲”的运维判断。

台账回填（升级到带台账的版本后跑一次，把历史会话补进 `logs/build_ledger.jsonl`）：

```bash
python3 tools/backfill_build_ledger.py --dry-run   # 只统计会写多少
python3 tools/backfill_build_ledger.py             # 回填（幂等，可重复跑）
```

只读会话文件，不碰服务器与世界；`--reset` 清空台账后重建，`--no-programs` 不存建造程序源码。
建议在 bot 停止时执行（运行中的 bot 也在追加同一份台账，同时分配记录编号会撞号，只影响可读性不影响查询）。
自己写的程序源码会落到 `logs/programs/`，与 `logs/` 其余内容一样不提交。

不要用 `kill -9` 作为常规重启方式。外部 `agent-restart.sh` 等守卫脚本只存在于特定部署机，使用前确认文件真实存在；
它们不是本仓库的跨环境依赖。

## 4. 控制词总表

硬编码控制词完全匹配（忽略前后空白）时由程序直接处理，**不走模型、不进上下文**。任何玩家都可使用；
“维克托，停止”这类不完全匹配文本仍按普通聊天处理。

| 控制词 | 作用 | 空闲要求/备注 |
|---|---|---|
| `停止` | 软停止主任务，并清空尚未处理的排队消息 | 当前工具完成后到安全点停 |
| `强制停止` | 立即中止主任务，并清空排队消息 | 可打断 API/工具等待；备份不可中止 |
| `不停止` | 撤销尚未生效的停止/强制停止 | 已停下的任务不能恢复 |
| `清空` | 用默认 flash 开全新主会话 | 必须空闲 |
| `清空k` / `清空g` | 使用对应 models 触发词开新会话 | 必须空闲且模型已接通；实际以配置为准 |
| `压缩` | 只保留玩家消息和游戏内发言 | 必须空闲 |
| `智能压缩` | 模型生成工作摘要后重建会话 | 必须空闲；执行期间 busy，可强制停止 |
| `恢复会话` | 恢复最近有效 session，沿用原模型 | 主任务和队列必须空闲 |
| `恢复会话d` | 恢复最近有效 session，强制 flash | 同上 |
| `状态` | 播报 BDS 进程、负载、在线玩家 | 任何时候可用 |
| `备份` | 后台热备份世界 | 必须空闲；不可中止 |
| `正文开` / `正文关` | 开关模型 content 旁路转发 | 新会话默认关 |
| `工具开` / `工具关` | 开关工具调用旁路转发 | 新会话默认开 |
| `1 强制停止` | 停止全部一次性对话 | 不属于主任务停止词 |
| `0 ...` | 静默消息，直接丢弃 | 不回执、不进上下文、不唤醒会话 |

程序控制回执使用 `[系统]`；模型经 send_chat_message 发出的内容使用 `<维克托>`；旁路观察使用 `[正文]` / `[工具]`。
这些系统提示不写入会话，也不会作为玩家聊天回灌。

## 5. 停止语义

### 5.1 软停止

“停止”不打断正在执行的工具；当前步骤结束、工具往返闭合后，在下一次工具调用或下一轮开始前停止。
尚未处理的 pending 消息会一并作废。

### 5.2 强制停止

“强制停止”会置位 abort：

- 工具内部轮询（指令、坐标、手持、建造等）可提前退出；
- 非流式 API 请求在后台线程执行，主线程每约 0.2 秒检查中止，不必等完整 socket 超时；
- 被打断的请求不再重试，退避 sleep 也可中止；
- 已发出的请求仍可能被供应商计费，但结果不写入上下文，也不向玩家报 API 错误；
- 被中止的 tool_calls 会补齐中止响应，保持上下文配对合法。

备份使用独立、不可置位的 abort 语义，“强制停止”只会提示备份无法中止。

## 6. 状态与备份

### 6.1 状态

“状态”随时可用，播报 1–2 条系统消息：

- `bedrock_server` PID、CPU、内存、运行时长；读不到则警告；
- Linux 系统负载（平台不支持时省略）；
- 当前在线人数和名单。

### 6.2 备份

“备份”要求 Bot 空闲，且不能同时已有备份。流程：

```text
save hold → 等待可备份状态 → 7z 打包世界 → save resume → 系统回执
```

- 备份在后台线程执行，聊天解析不中断，但新任务和一次性对话会等待/拒绝，完成后继续。
- 开始和完成/失败都有 `[系统]` 回执。
- 输出路径、超时和压缩级别见[配置参考](configuration.md#6-备份)。
- 不要直接拷贝正在运行的 `worlds/`；`save hold` 期间不要改世界，并确保最终 `save resume`。

## 7. 正文与工具转发

- `正文开`：每轮模型 content（包括同时带 tool_calls 的正文）以 `[正文]` 发到游戏聊天。
- `工具开`：工具调用以 `[工具]` + 前 40 字预览发到聊天；run_server_command 显示命令，ptc 显示子工具名。
- `send_chat_message` 不重复转发；`stay_silent` 永不显示，避免暴露内部沉默判断。
- ptc 混合调用会过滤上述两类，只显示其余工具。
- 两路只是 tellraw 观察信息，不进入上下文，也不会被当成玩家输入。

## 8. 模型错误呈现

最终失败（重试用尽或不可重试）时，程序向玩家补一条系统消息，避免 Bot 无声：

```text
[系统] flash(DeepSeek Flash) 请求失败: HTTP 429 Rate limit reached for requests。这条消息没处理。
[系统] kimi(Kimi K3.1 Pro) 请求失败: HTTP 402 Insufficient Balance。这条消息没处理。
```

格式使用模型别名/显示名、HTTP 状态和供应商返回的 `error.message` 或原文，压成一行并截断；
非 HTTP 异常带异常类型。程序不自行编造状态码解释或修复建议。

- 重试过程只写 `logs/bot.log`，游戏内只出现最终结果。
- 覆盖主对话、一次性对话和轮次上限后的收尾请求。
- 玩家主动强制停止不播报为错误。

## 9. 日志检查（仅对应环境）

```bash
# 开发设备：只查看仓库内是否已有这些文件，不存在是正常现象
python3 bot.py --test

# 部署服务器：确认 screen、状态与日志
screen -ls
python3 - <<'PY'
from pathlib import Path
p = Path('logs/agent.state')
print(p.read_text() if p.exists() else 'no agent.state')
PY

tail -f logs/bot.log
tail -f logs/server.log
```

`logs/bot.log` 可能含思考链和敏感对话，`logs/server.log` 可能含玩家信息；排障分享前应脱敏。
运行时文件说明见[架构与代码结构](architecture.md#5-运行时文件)。
