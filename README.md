# mc-ai-bot — 维克托

把 Minecraft 基岩版服务器（运行在 screen 会话 `mc` 中）的聊天接入 DeepSeek。
AI 人设：**维克托·米哈伊洛维奇·切布里科夫 (Viktor Chebrikov)**，服务器智能管家。
已具备说话/沉默、长期记忆、服务器与玩家状态查询、执行服务器指令等能力（见下文“能力”）。
当前不硬编码任何指令词：每条玩家聊天都交给模型判断该不该回应。

## 架构

```
玩家聊天 → bedrock_server → screen 日志(logs/server.log)
                                  │ tail 解析
                            bot.py(滚动上下文)
                                  │
                            DeepSeek API
                                  │
              screen -X stuff "tellraw @a ..." → 游戏内显示
```

零第三方依赖，只用 Python 3.11+ 标准库。

## 会话与上下文机制

- **以 0 玩家为分水岭**：解析 `Player connected/disconnected` 维护在线人数；
  人数清零 → 会话结束（上下文落盘到 `logs/sessions/`）；下一人进服 → 全新会话。
- **缓存命中**：system prompt 固定 + 会话内消息 append-only，逐轮请求前缀一致，
  DeepSeek 自动前缀缓存可命中（日志里 `缓存命中 N` 字段可看效果）。
- 服务器内所有聊天都进上下文（维克托能“听到”大家说话），但要不要回应、该不该沉默由模型自己判断。

## 思考强度与创造模式

所有请求都走 `deepseek-flash`（DeepSeek-V4.1-Flash，支持 `effort` 思考强度档位 low/high/max）。

- **普通模式**：`effort=low`，回复短、便宜、快，适合闲聊和简单指令。
- **创造模式**：玩家在游戏里说"开创造模式/认真做"等，维克托调 `set_creative_mode(true)` 切换。
  `effort=max`，并注入面向精细创造的额外提示词（先规划后施工、先试小块再铺开、成片 fill），
  同时放宽输出 token、工具轮次、上下文条数、发言分段数。任务完成或会话结束自动复位。
  仅限白名单/op。思维链（`reasoning_content`）只写入 `logs/bot.log`，不进会话上下文。

## 运行

```bash
./run.sh                      # 前台运行(自动重新应用 screen 日志设置)

# 或挂后台:
screen -dmS viktor bash -c "cd /home/jrj/repo/mc-ai-bot && ./run.sh"
screen -r viktor              # 查看(Ctrl+A D 退出)

python3 bot.py --test         # 解析逻辑自测
```

注意：**MC 服务器（screen 会话 mc）重启后必须重启本 bot**（或重新执行 run.sh），
否则 screen 日志失效，bot 收不到聊天。

## 能力（function calling）

| 工具 | 说明 |
|---|---|
| `send_chat_message(text)` | 在游戏内发言（唯一的“说话”方式，正文玩家看不到） |
| `stay_silent()` | 本条消息不回应 |
| `update_memory(content)` | 仅在用户明确要求记住/修改/忘记时改长期记忆 |
| `get_player_activity(minutes)` | 解析日志，查玩家进出记录 |
| `get_server_status()` | 进程 CPU/内存、运行时长、负载、在线玩家 |
| `run_server_command(cmd)` | 以控制台身份执行基岩版指令（如 `tp`/`fill`/`locate`），输出返回给模型 |
| `get_player_position(player?)` | 在线玩家实时坐标（行为包脚本，无指令可查） |
| `get_player_inventory(player?)` | 在线玩家物品栏（36 格） |
| `get_player_hand(player?)` | 在线玩家手持物品 |
| `backup_world()` | 把当前存档热备份成 `.7z`（`save hold` → 7z → `save resume`） |
| `set_creative_mode(enabled, reason?)` | 切换创造模式（思考强度 max + 创造提示词 + 放宽上限） |

能力注册表在 `capabilities.py`，可运行时 `register()` 扩展。

### 行为包脚本桥

BDS 控制台 **不回显玩家聊天**，所以用行为包 `viktor_bridge` 订阅事件并 `console.log`：

- `world.beforeEvents.chatSend` → `[VIKTOR-CHAT] 玩家: 内容`
- `scriptevent viktor:pos` → `[VIKTOR-POS] 玩家 x y z 维度`
- `scriptevent viktor:inv` → `[VIKTOR-INV] 玩家 槽位 物品 数量`（末行 `DONE 手持槽位`）

需要 `@minecraft/server` 的 **beta** 模块与 `level.dat` 里的实验开关。
修改脚本后用控制台 `reload` 热重载，不必重启服务器。

### 指令权限

`run_server_command` 双重校验：

- 请求者是 **服务器 operator**（读 `permissions.json`，配合进服日志里的 `名字→xuid` 映射）
- 或者列在 `command_users` 里

危险指令（`stop`/`op`/`deop`/`whitelist`/`ban` 等，见 `command_blocklist`）一律拒绝。

## 停止（中断运行中的任务）

玩家在游戏里单独发一条 **`停止`**（完全匹配，前后空白可忽略）时，系统**不走模型**，
直接中止正在进行的 Agent 任务，并立即回执：

- 有任务在跑 → 置位中止标志、清空待处理队列，回“已停止当前任务。”
- 空闲 → 回“当前没有正在执行的任务。”
- 不是完全匹配（如“维克托，停止”）→ 当普通聊天交给模型判断

中止会在三个层次生效：下一轮工具调用开始前、每个工具执行前、
以及工具内部的轮询等待中（`run_server_command`/坐标/物品栏）。
被中止的 `tool_calls` 会补上 `(已中止)` 响应，保证上下文里的
`assistant(tool_calls)` 与 `tool` 始终成对——否则 DeepSeek 会报 400。

这是唯一一处硬编码的“控制面”词（类似 Ctrl-C），其余指令词仍全部交给模型判断。
停止消息**不进上下文**，以免在多线程追加时插到工具序列中间。

## 配置（config.json）

| 键 | 说明 |
|---|---|
| `model` / `temperature` / `max_reply_tokens` / `api_timeout_sec` | DeepSeek 参数 |
| `api_min_interval_sec` | 全局 API 最小间隔（保护缓存前缀顺序与限流） |
| `max_context_messages` | 上下文兜底截断（触发会破坏缓存前缀，正常不会到） |
| `reply_chunk_len` / `reply_max_chunks` | 回复分片发送，防止过长 |
| `mc_server_dir` | 服务器目录（读 `permissions.json`） |
| `command_users` | 指令白名单（额外的，operator 自动放行） |
| `command_blocklist` | 禁止执行的指令 |
| `command_result_timeout_sec` / `position_timeout_sec` / `inventory_timeout_sec` | 等待脚本/控制台回包的秒数 |
| `normal_effort` / `creative_effort` | 普通/创造模式的思考强度（low / max） |
| `creative_max_reply_tokens` / `creative_max_tool_rounds` / `creative_max_context_messages` / `creative_reply_max_chunks` | 创造模式放宽的各项上限 |
| `backup_dir` | 备份输出目录（默认 `/home/jrj/mc_backup`，文件名 `世界名-YYYYmmdd-HHMMSS.7z`） |
| `backup_hold_timeout_sec` / `backup_timeout_sec` | 等 `save hold` 完成 / 7z 打包的超时 |
| `backup_compression_level` | 7z 压缩级别（`-mx`，默认 5） |
| `max_queue` | 已移除；每条聊天都由模型判断 |

> screen 日志的 flush 间隔必须调小（`logfile flush 1`，见 `run.sh`），
> 否则指令输出、脚本回包会延迟十几秒才落盘，导致捕捉超时。

## 文件

- `logs/server.log` — screen 捕获的服务器控制台输出（bot 的数据源）
- `logs/bot.log` — 机器人运行日志
- `logs/sessions/*.jsonl` — 每次会话的完整上下文存档
- `logs/xuid-cache.json` — 玩家名到 xuid 的映射（判断 operator 用）
- `memory.md` — 长期记忆（每次初始化注入 system prompt），备份在 `logs/memory-backup/`
- `capabilities.py` — 能力注册表
- `/home/jrj/mc_backup/` — 存档备份输出目录
- `run.sh` — 启动脚本：重设 screen 日志设置并跑 bot
