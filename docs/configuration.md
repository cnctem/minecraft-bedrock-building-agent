# 配置参考

运行时从根目录读取 `config.json`，从 `config.example.json` 复制并填写 key。
离线自测自动建立假配置，不需要创建此文件。默认值以示例和代码为准。

## DeepSeek

| 配置 | 说明 |
|---|---|
| `api_key` | DeepSeek API key，仅保存在本地 |
| `api_base` | 默认 `https://api.deepseek.com`；客户端追加 `/chat/completions` |
| `model` | 模型 ID，默认 `deepseek-flash` |
| `api_timeout_sec` | 请求读超时，默认 60 秒 |
| `api_min_interval_sec` | 每次尝试的最小发起间隔，默认 0.1 秒 |
| `api_max_attempts` | 瞬态错误最大尝试数，默认 3 |
| `api_retry_backoff_sec` | 基础退避，默认 1 秒 |
| `parallel_tool_calls` | 鼓励同时生成多个函数调用，默认 true |

主会话、一次性任务和智能压缩使用同一套连接。
联网由 DeepSeek 服务端执行，不需要单独的联网凭据或客户端抓取参数。

## Agent 名称

| 配置 | 说明 |
|---|---|
| `agent_name` | 游戏内显示名称与模型身份，默认 `agent`；可配置为 `小筑` 等名称 |

名称为 1–32 字符的可见文本，首尾空格会去掉，不能含控制字符或 `§<>`。
修改配置后重启 Agent 生效；主会话和一次性任务共用该名称，系统回执仍使用 `[系统]`。
历史会话保留落盘时的名称；恢复后的模型身份使用当前配置。

名称不作为唤醒词，也不用于过滤聊天。是否回应由模型结合当前消息、上下文和长期记忆判断。
如需特定的接话习惯，可直接在 `memory.md` 中维护，或明确要求 Agent 记住；
手工修改记忆后，在空闲时清空会话或压缩上下文以重新载入。

## 模式与输出

| 配置 | 说明 |
|---|---|
| `normal_effort` / `creative_effort` / `creative_max_effort` / `oneshot_effort` | DeepSeek effort，默认 low / high / max / low |
| `temperature` | 普通及一次性任务采样温度，默认 0.7 |
| `creative_temperature` | 可选；创造模式默认不发送 temperature |
| `max_reply_tokens` / `creative_max_reply_tokens` / `oneshot_max_reply_tokens` | 普通 / 创造 / 一次性输出，默认 6000 / 16384 / 6000 |
| `retry_max_reply_tokens` | 截断重试上限，同时限制模式输出，默认 32768 |
| `max_tool_rounds` / `creative_max_tool_rounds` / `oneshot_max_tool_rounds` | 工具轮次，默认 8 / 32 / 4 |
| `ptc_max_calls` / `ptc_stated_calls` / `ptc_result_limit` | 普通 ptc 实际条数 / 声明条数 / 结果字符数，默认 24 / 12 / 30000 |
| `creative_ptc_max_calls` / `creative_ptc_stated_calls` / `creative_ptc_result_limit` | 创造 ptc 额度，默认 48 / 24 / 60000 |
| `oneshot_max_concurrent` | 并发一次性任务上限，默认 4 |

creative_max 将创造模式数值预算、ptc 和分段额度翻倍，输出仍受总上限约束。
权限与行为见[运行模式](modes.md)。

## 上下文

| 配置 | 说明 |
|---|---|
| `context_window_tokens` | 上下文窗口，默认 1048576 |
| `context_safety_tokens` | 输入安全余量，默认 4096 |
| `smart_compact_auto_pct` | 自动智能压缩的输入预算百分比，默认 95 |
| `smart_compact_keep_recent` | 摘要后保留最近消息数，默认 8 |
| `smart_compact_input_chars` | 摘要输入字符预算，默认 40000 |
| `smart_compact_max_tokens` | 摘要输出预算，默认 2048 |
| `notify_context_clear` | 自动压缩或清空时通知，默认 true |
| `notify_creative_mode` | 模式切换通知，默认 true |
| `session_read_max_chars` | 历史读取默认字符限制，默认 12000 |

语义见[会话文档](conversation.md)。

## BDS 桥接与显示

| 配置 | 说明 |
|---|---|
| `screen_session` | 已运行 BDS 的 screen 名，默认 mc |
| `poll_interval_sec` | 主日志轮询，默认 0.5 秒 |
| `bus_protocol` | auto 探测协议 v5，或 off 禁用总线 |
| `bus_reader_poll_sec` / `bus_batch_max` | 总线轮询 / 批请求数，默认 0.05 秒 / 8 |
| `command_blocklist` | 禁止执行的指令，保留 stop/op/权限管理等限制 |
| `command_result_timeout_sec` | 控制台结果等待，默认 6 秒 |
| `position_timeout_sec` / `inventory_timeout_sec` / `block_timeout_sec` | 坐标 / 手持 / 方块超时，默认 4 / 5 / 5 秒 |
| `spatial_timeout_sec` | 空间查询超时，默认 25 秒 |
| `reply_chunk_len` / `reply_max_chunks` | 普通发言每段字数 / 段数，默认 120 / 3 |
| `creative_reply_max_chunks` | 创造发言段数，默认 10 |
| `build_progress` / `build_progress_min_sec` | 进度转发 / 最小间隔，默认 true / 2 秒 |
| `render_attach_png` / `render_attach_max` | 附渲染图 / 最大视角数，默认 true / 2 |
| `replay_log_on_truncate` | 日志截断后从头重放，默认 false，避免重复执行 |

## 启动变量

| 变量 | 用途 |
|---|---|
| `PYTHON_BIN` | 启动/重启使用的 Python，默认 python3 |
| `AGENT_RESTORE` | 启动时恢复的会话路径 |
| `AGENT_SCREEN_NAME` | 重启管理的 Agent screen 名，默认 agent |

这些变量不改变 DeepSeek 凭据。示例见[运行文档](operations.md)。
