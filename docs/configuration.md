# 配置参考（config.json）

Bot 启动时从仓库根目录读取 `config.json`。新部署可复制示例：

```bash
cp config.example.json config.json
```

然后至少填写默认模型的 `api_key`，并按环境检查 `api_base`、模型名和服务器路径。
`config.json` 含密钥，已被 `.gitignore` 排除；不要提交、粘贴到 issue 或写入文档。修改配置后需重启 Bot 生效。

示例中的 `/home/jrj/...` 是部署机路径，不是开发设备的必备目录。模型名称和可用性也以实际账号与配置为准。

## 1. 模型与 API

| 键 | 说明 |
|---|---|
| `api_key` / `api_base` / `model` | 默认模型 flash 的密钥、Base URL 和模型 ID |
| `models` | 会话级模型档案表，键为别名，如 flash/kimi/gpt |
| `temperature` | 默认采样温度；模型档案显式设置时优先 |
| `max_reply_tokens` | normal 本轮输出上限 |
| `retry_max_reply_tokens` | flash 档案的 `max_output_tokens` 默认值，用于窗口输入预算等计算 |
| `api_timeout_sec` | 默认 API 请求超时；模型档案可覆盖 |
| `api_min_interval_sec` | 全局 API 最小间隔；每次尝试（含重试）都遵守 |
| `api_max_attempts` | 单次请求最大尝试次数，默认 3 |
| `api_retry_backoff_sec` | 指数退避基数秒，默认 1，上限 30；尊重 Retry-After |

`models.<alias>` 支持：

| 字段 | 说明 |
|---|---|
| `label` / `trigger` | 显示名与完全匹配的清空触发词，如“清空k” |
| `api_base` / `api_key` / `model` | 非默认模型必须分别写全，不继承 flash 的身份字段 |
| `enabled` | 是否接通；缺 Base URL/key/model 也会自动视为未接通 |
| `context_window_tokens` / `max_output_tokens` | 上下文窗口和输出预算 |
| `effort_param` / `effort_map` | low/high/max 映射到哪个请求字段和值；映射 null 表示不传 |
| `reasoning_content` | 历史 assistant(tool_calls) 是否回传思考链 |
| `temperature` | 固定温度；null 表示一律不传，省略则按模式默认规则 |

重试只覆盖超时、408/409/425/429 和部分 5xx 等瞬态错误；400/401 等直接失败。
最终失败会把模型实际错误摘要以 `[系统]` 回给玩家，过程细节写 `logs/bot.log`。

## 2. 上下文与压缩

| 键 | 默认值/说明 |
|---|---|
| `context_window_tokens` | flash 默认 1048576；其他模型在 models 档案中设置 |
| `context_safety_tokens` | 默认 4096；输入预算 = 窗口 − 本轮输出上限 − 安全余量 |
| `smart_compact_auto_pct` | 默认 95；到输入预算该比例时自动智能压缩 |
| `smart_compact_keep_recent` | 默认 8；智能压缩后保留的最近消息数 |
| `smart_compact_input_chars` | 默认 40000；摘要器输入上限，超出保留头尾并标注省略 |
| `smart_compact_max_tokens` | 默认 2048；摘要请求输出上限 |
| `notify_context_clear` | 是否发送自动压缩/清空相关通知 |
| `session_read_max_chars` | `read_session` 默认结果上限，12000 |

70/80/90% 占用提醒以模型窗口为分母；95% 自动智能压缩以输入预算为分母。
超输入预算先普通压缩，仍超才完整初始化。详见[会话、上下文与模型](conversation.md)。

## 3. 模式、回复与批量工具

| 键 | 说明 |
|---|---|
| `normal_effort` / `creative_effort` / `creative_max_effort` | 各模式逻辑思考强度，默认 low/high/max |
| `max_tool_rounds` | normal 工具轮次上限，示例 8 |
| `creative_max_reply_tokens` / `creative_max_tool_rounds` | creative 的输出与工具轮次上限，示例 16384/32 |
| `creative_reply_max_chunks` | creative 游戏内回复最大分段数；creative_max 等倍率按 profiles 处理 |
| `reply_chunk_len` / `reply_max_chunks` | 普通回复分片长度与最大片数 |
| `parallel_tool_calls` | 是否允许 API 一次返回多个工具调用 |
| `ptc_max_calls` / `ptc_stated_calls` | 普通 ptc 实际放行数/对模型声明数，默认 24/12 |
| `ptc_result_limit` | 普通 ptc 合并结果上限，默认 30000 字符 |
| `creative_ptc_max_calls` / `creative_ptc_stated_calls` | creative ptc 实际/声明上限，默认 48/24 |
| `creative_ptc_result_limit` | creative ptc 结果上限，默认 60000；creative_max 再 ×2 |
| `chat_dialog_window_sec` | “正在对话”窗口，默认 180 秒 |
| `notify_creative_mode` | 是否播报创造模式切换通知 |
| `oneshot_effort` | 一次性对话思考强度，默认 low |
| `oneshot_max_reply_tokens` / `oneshot_max_tool_rounds` | 一次性输出与工具轮次上限，默认 6000/4 |
| `oneshot_max_concurrent` | 一次性对话最大并发，默认 4 |

`creative_max` 的倍率与工具权限由 `viktor/profiles.py` 组合，不是简单读取同名字段。
`max_queue` 已移除：普通聊天都交给模型判断，不使用旧的固定队列上限配置。

## 4. 日志、总线与空间查询

| 键 | 说明 |
|---|---|
| `screen_session` | BDS 所在 screen 会话，默认/示例为 `mc` |
| `poll_interval_sec` | 主日志 tail 轮询间隔，示例 0.5 秒 |
| `replay_log_on_truncate` | 日志截断/轮转后是否从头重放；默认 false，避免重复处理旧聊天和旧工具 |
| `bus_protocol` | `auto` 默认握手探测；`v3` 跳过探测；`off` 禁用查询总线 |
| `bus_reader_poll_sec` | 总线读线程 tail 间隔，默认 0.05 秒 |
| `bus_batch_max` | 一次下发的查询请求上限，默认 8 |
| `command_result_timeout_sec` | 普通控制台指令结果等待时间 |
| `position_timeout_sec` / `inventory_timeout_sec` / `block_timeout_sec` | 坐标/手持/单方块查询超时 |
| `spatial_timeout_sec` | 高度图、切面、区域检查、找方块等空间查询超时，默认 25 秒 |
| `command_blocklist` | 禁止模型执行的控制台指令列表 |

`run.sh` 会设置 `screen` 的 `logfile flush 1`。flush 过大可能让指令输出和脚本回包延迟十几秒，造成误判超时。
BDS 重启后 screen 日志设置会失效，必须重新执行 run.sh 或重启 Bot。

## 5. 建造与常加载

| 键 | 说明 |
|---|---|
| `build_progress` | 是否向玩家转发建造阶段进度，默认 true |
| `build_progress_min_sec` | Bot 侧再次转发进度的最小间隔，默认 2 秒 |
| `render_attach_png` | 渲染图是否直接作为图片附给模型（flash/kimi 都能读图），默认 true |
| `render_attach_max` | 一次渲染最多附几张图，默认 2；其余视角只给字符图 |
| `pin_max_areas` | pin_region 单次最多切出的常加载片数，默认 6；同时受 BDS 每维度上限约束 |

编译器体积、源码、沙箱和协议上限是代码常量，不由 config 任意放大；当前值见[建造引擎](build-engine.md)。

## 6. 备份

| 键 | 说明 |
|---|---|
| `mc_server_dir` | BDS 目录，用于定位世界存档；示例 `/home/jrj/minecraft-bedrock` |
| `backup_dir` | 备份输出目录，示例 `/home/jrj/mc_backup` |
| `backup_hold_timeout_sec` | 等待 `save hold` 完成的超时 |
| `backup_timeout_sec` | 7z 打包超时 |
| `backup_compression_level` | 7z `-mx` 压缩级别，默认 5 |

备份依赖系统 `7z`，通过 `save hold → 7z → save resume` 完成。不要直接复制正在写入的 `worlds/`。

## 7. 联网搜索与抓取

| 键 | 说明 |
|---|---|
| `web_search_count` | 单次搜索返回条数，默认 8（工具侧上限 20） |
| `web_search_timeout_sec` | Search/Fetch 请求超时，默认 30 秒 |
| `web_search_max_chars` | 单次结果（搜索列表 / 网页正文）返回上限，默认 12000 |
| `web_search_api_base` | 可选：搜索/抓取接口 Base URL，留空用顶层 `api_base`（DeepSeek） |
| `web_search_api_key` | 可选：搜索/抓取接口 key，留空用顶层 `api_key` |
| `image_fetch_timeout_sec` | 本地取图超时，默认 15 秒（只给不认 http 图片地址的模型用） |
| `image_fetch_max_bytes` | 本地取图体积上限，默认 4194304（4 MiB），超过就不附图 |
| `image_fetch_allow_private` | 本地取图是否允许内网/回环地址；默认 false，非必要不要打开 |

默认模型走 DeepSeek 原生联网（请求 `tools` 里的 `deepseek_web_search` / `deepseek_read_url`，
服务端执行），**不读这些键**；它们只在切到别家模型、同名工具退化成函数工具时使用。
模型是否原生联网由 `models.native_web_tools()` 判定（Base URL 是 DeepSeek 即为真，
也可在模型档案里显式写 `web_tools: true/false`）。

玩家发的图片直链是否直接附给模型，由 `models.remote_image_url()` 判定（DeepSeek 支持 http 图片地址，
Kimi 只认 `data:` URL），同样可在模型档案里写 `remote_image_url: true/false` 覆盖。
为真的模型只附 URL（服务端下载）；为假的模型由 `websearch.fetch_image()` 在本地取一次字节转 base64
（DeepSeek 的接口不回图片字节，这是唯一办法），受上面三个 `image_fetch_*` 限制，取不到就不附图。

## 8. 环境变量与命令行

| 入口 | 用途 |
|---|---|
| `VIKTOR_RESTORE=<path>` | 启动后静默恢复指定落盘会话，`restart.sh` 使用 |
| `python3 bot.py --test` | 离线自测，不启动线上主循环 |
| `python3 bot.py --resume <path>` | 启动并恢复指定会话 |
| `./restart.sh [session]` | 在已部署服务器上优雅重启；可指定 session 路径、文件名或唯一子串 |

这些入口都假定当前工作目录和配置属于同一个仓库。跨开发设备/部署服务器操作时，先按根目录 `AGENTS.md` 判断环境。
