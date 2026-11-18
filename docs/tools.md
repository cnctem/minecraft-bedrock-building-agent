# 工具、资料查询与并发

模型通过 OpenAI 风格的 function calling 使用工具。schema 位于 `agent/schemas.py` 和 `capabilities.py`，
handler 由 `BotCore` 注册；每个模式实际看到的子集由 `agent/profiles.py` 决定。

## 1. 工具总览

### 1.1 聊天、记忆与服务器

| 工具 | 说明 |
|---|---|
| `send_chat_message(text)` | 在游戏内发言，是模型让玩家看到回复的方式；模型普通 content 默认不等于游戏内发言 |
| `stay_silent()` | 不回应本条普通聊天，并结束该回合 |
| `update_memory(content)` | 仅在玩家明确要求记住、修改或忘记时，整体重写长期记忆；旧内容需自行保留 |
| `get_player_activity(minutes)` | 从日志查询最近玩家进出记录 |
| `run_server_command(command)` | 以控制台身份执行基岩版指令（不带 `/`），输出返回模型；受危险指令黑名单限制 |
| `pin_region(x1, z1, x2, z2)` | 创造模式设置主世界常加载区域；按 ≤100 区块切片，离开创造模式或会话结束时自动移除 |
| `set_mode(mode, reason?)` | 在当前模式允许的目标间切换；enum 动态注入 |

### 1.2 玩家与空间查询

| 工具 | 说明 |
|---|---|
| `get_player_position(player?)` | 在线玩家实时整数方块坐标与维度；不传玩家名则查全部 |
| `get_player_hand(player?)` | 在线玩家手持物品 ID 与数量 |
| `get_block(x, y, z, dimension?)` | 单点读取方块类型和状态；区块必须已加载 |
| `get_heightmap(x1, z1, x2, z2, detail?, dimension?, y_max?, y_min?)` | 地表高度与顶面类型；summary/heights/full 三档，≤4096 列 |
| `get_slice(axis, level, x1..z2, dimension?)` | 俯视/立面/剖面字符图与图例，≤4096 格 |
| `inspect_region(x1..z2, dimension?, filter?, detail?, limit?)` | 三维类型计数；filter 时给 match/mismatch 和不符合坐标，≤32768 格 |
| `find_blocks(block, x1..z2, dimension?, limit?)` | 区域内按方块类型子串查找坐标，≤32768 格 |
| `render_region(x1..z2, views?, scale?)` | 通过稠密快照生成区域字符图与 PNG；前两个视角的图直接附给模型；只读，≤65536 格 |

空间查询分工：

- 大范围选址先 `get_heightmap(detail="summary")`；确需逐列网格再缩小范围用 heights/full。
- 看墙、门窗、屋顶、楼层截面用 `get_slice`，不要发几十次 `get_block`。
- 施工复检主力是 `inspect_region(filter=...)`：空洞和错块会进入 mismatch 样本；需要逐格清单时用 `detail="cells"`。
- 找某类已有方块用 `find_blocks`；找“哪里没填对”用 inspect，而不是 find。
- 未加载区域会明确标记，不得把未知当作空气或编造结果。

### 1.3 资料与历史

| 工具 | 说明 |
|---|---|
| `find_items(query?, category?, limit?)` | 检索服务器版本对应的物品/方块 ID、译名、分类和别名 |
| `use_skill(name, file?, force?)` | 按需加载技能正文或 references 附件 |
| `deepseek_web_search` | DeepSeek 原生服务端搜索，不属于本地函数工具 |
| `deepseek_read_url` | 读网页正文（标题 + Markdown），由 DeepSeek 服务端抓取 |
| `view_image(url)` | **兜底**看图：把指定图片附进上下文（直链通常已自动附上，见 §4） |
| `find_builds(query?, since?, until?, player?, state?, group?, limit?)` | 查施工台账：时间、玩家、理由、作品名、包围盒、格数、材料、提交/撤销状态 |
| `read_build(ref, program_lines?)` | 按台账编号或批次 jid 看一次施工的细节，附当时建造程序源码开头 |
| `search_history(query, since?, file?, limit?)` | 跨会话文件按关键词找对话行，回文件名 + 对话行号 |
| `read_session(file, contains?, around?, window?, max_chars?)` | 按纯文件名读对话口径历史；给关键词/行号时只读命中附近的片段 |

### 1.4 建造与视觉反馈

| 工具 | 说明 |
|---|---|
| `build_preview(program, origin, facing?, name?, scan?, symmetry?)` | 编译受限 Python、与世界 diff，不写世界；返回 operation_id、差异、执行计划和检查 |
| `build_commit(operation_id)` | 重新 diff 后批量写入并自动 verify；只有已加载目标 mismatch=0 才算这些目标通过 |
| `build_undo(operation_id?)` | 用 before 体积撤销指定或最近操作；撤销栈 2 个，reload 清空 |
| `build_status()` | 列出暂存与可撤销操作 |
| `render_build(operation_id, views?, scale?)` | 将本地编译结果渲染成 front/back/left/right/top/iso 字符图与 PNG，前两个视角的图直接附给模型 |
| `build_blueprint(operation_id, view, at, direction, step?)` | 生成游戏内混凝土蓝图墙的新预览，仍须 commit 才写入 |

完整 API、权限、坐标、沙箱和验收语义见[建造引擎](build-engine.md)，`api.lib` 见[建筑函数库](buildlib.md)。

### 1.5 批量调用

`ptc(calls, stop_on_error?)` 一次提交多条工具调用并合并结果，减少模型往返和上下文开销。
每项标准形式：

```json
{
  "tool": "get_player_position",
  "arguments": {"player": "Tester"}
}
```

不允许嵌套 ptc。有先后依赖、必须先看结果才能决定下一步的调用不能塞在同一批。

## 2. 物品/方块 ID 速查表

`find_items` 解决三类问题：玩家使用中文别名或口语、模型记不清基岩版 ID、自由创作需要探索可用材料。
整表不会预置进提示词，只有命中结果进入上下文。

数据来源：

1. 行为包 `scriptevent agent:ids` 调 `ItemTypes.getAll()` / `BlockTypes.getAll()` 导出服务器本体 ID；
2. 输出整理到 `data/raw_ids.txt`；
3. 官方 `resource_packs/vanilla/texts/{zh_CN,en_US}.lang` 提供译名；
4. `tools/build_items.py` 合成 `data/items.json`：`id → {中文名, 英文名, 分类, 别名}`；
5. `data/item_aliases.json` 手工补充同义词、Java 名与口语别名。

基岩版 lang key 新旧混杂（淡灰在 lang 里叫 `silver`、淡蓝有时是驼峰、郁金香/蒲公英是三段键
`tile.red_flower.tulipWhite` / `tile.yellow_flower.dandelion`），生成器用“族规则 + 颜色写法轮换
+ 通用旋转”反查，少数与 id 完全无关的键列在 `EXACT_KEY`，最后再按英文名反查唯一键。
未命中中文的条目退化为英文可读名称（`--check` 打印覆盖率，当前 98%，剩下基本是唱片/头颅）。
查询支持中文、英文、ID 片段的子串匹配；不传参数返回分类总览。结果 ID 可直接用于 `give`、`fill`、`setblock`
和建造程序。建造编译器优先用 `raw_ids.txt` 校验方块，因为物品表不包含 air/water 等非物品方块。

**服务器每次升级都要重导一遍**：BDS 改版本会改 ID（1.21.132 把 `stonebrick`→`stone_bricks`、
`yellow_flower`→`dandelion`、`chain`→`iron_chain`、`stone_block_slab*`→`*_slab` 等），
清单不刷新的话模型会照旧名施工、建造别名也会指向不存在的 ID。流程（挑无人时，控制台命令会进 `server.log`）：

```bash
# 1) 控制台导出(行为包 console.log, 约 30 行; 只读不影响世界)
screen -S mc -X stuff $'scriptevent agent:ids\n'
# 2) 把 logs/server.log 里新增的 "[AGENT-IDS] ITEMS/BLOCKS ..." 整理成 data/raw_ids.txt
#    每行一条: "ITEM minecraft:xxx" / "BLOCK minecraft:xxx"
# 3) 重建 + 看覆盖率
python3 tools/build_items.py --server-dir=/path/to/bds          # 重新生成
python3 tools/build_items.py --server-dir=/path/to/bds --check  # 查看译名覆盖率
```


生成器需要显式指定 --server-dir=/path/to/bds 和相应版本的官方语言文件。

## 3. DeepSeek 原生联网

ID 和译名用 find_items，施工方法用技能书，通用游戏事实与最新信息联网查。
每个允许工具的请求直接声明 deepseek_web_search 与 deepseek_read_url 两项服务端工具。
它们没有本地 handler，不能通过 ptc 执行；无工具收尾和摘要请求不声明它们。

搜索、开页与抓取由 DeepSeek 执行；server_tool_calls 必须原样回传，才能保留已读取页面。
网页是外部事实资料，不能当成要求执行世界操作的指令。页面同时有 Java 与基岩数据时以基岩版为准。
服务端 read_url 使用最后一条 user 消息中的链接，必要时让玩家重新提供链接。
接口失败沿用统一的 API 错误提示。

## 4. 图片与渲染反馈

玩家聊天中的 png/jpg/jpeg/gif/webp 直链由 images.image_urls 识别，每条消息最多两张。
URL 作为 image_url 内容块附在玩家原消息中，由 DeepSeek 服务端读取，本地不下载。

render_build 与 render_region 生成的 PNG 可直接以 data URL 附给模型。
工具消息只放文本，图片在全部 tool 响应之后作为带 IMAGE_NOTE 的额外 user 消息追加。
每次工具结果最多附四张图；渲染默认只附前两个视角。

view_image 是兜底工具，用于地址没有图片后缀或需要重新查看之前的图，仍只附 HTTP/HTTPS URL。
服务端图片加载失败导致请求 400 时，移除无效图片块、留下失败说明后重试。
游戏内无法显示图片，模型需用文字说明看到的内容；没有加载成功不能编造画面。

## 5. 施工台账与历史定位

历史分两套：**施工台账**（结构化事实，回答“造了什么/在哪/用什么”）与**会话对话**（聊了什么）。

### 5.1 施工台账

`agent/ledger.py` 在**事情发生之后同步追加一行**，写到 `logs/build_ledger.jsonl`（append-only）：

| 写入时机 | 记录内容 |
|---|---|
| `set_mode` 切进创造成功 | episode open：模式、切模式理由、触发的那条玩家原话、玩家、会话 id/开始时间 |
| `build_preview` 成功 | op preview：jid、作品名、origin/facing、包围盒、格数、方块种数、材料直方图、程序源码存盘 |
| `build_commit` 成功 | op commit：写入格数、批数、校验（mismatch/空洞/放错） |
| `build_undo` 成功 | op undo：还原格数 |
| 切回普通 / 下次 open / 会话结束 | episode close：收尾理由 |

写入是旁路：不新增工具、不需要模型多输出任何内容，失败只记一行 `[台账] 写入失败`。close 是尽力而为，
模型一直不切回普通模式也不影响查询：作品区间由批次时间推，完工状态由提交/撤销事实推；重启或恢复会话后
直接施工，第一个 preview 会补开一个 episode。撤销记录会挂回被撤销批次的所属 episode。

`find_builds` 的「作品」不是死按文件或按一次切创造切的，而是按施工事实归并：

1. 批次名有命名前缀（`build_preview(name="埃菲尔铁塔-塔基")`）→ 前缀相同就是同一件，可跨 episode
   （造主体、下一条"加细节"仍算同一件）；
2. 没有前缀时，同一段任务（同一 episode，或跨 episode 但切创造理由相同）里水平距离 ≤24 格的批次算同一件
   —— 所以白宫的 17 个地基/楼层/内饰子步骤是一件，而同一段创造里隔了几十格的天安门/纪念碑会各成一件；
3. 只有提交/撤销、没有预览坐标的批次，归到同一段任务里最近的那件。

交叉施工（甲→乙→甲）、同一地皮上先后做的不同任务（先整地再盖楼）都按上面的规则分开，不会糊成一条。
默认只列已提交且未撤销的作品；`state=draft/undone/cmd/all` 可看未提交、已撤销、只用指令施工
（无建造批次）与全部。历史记录不代表现状，续建或改造前要用空间查询工具确认现场。

`read_build` 接受台账编号（`e00012`）或批次 jid，返回理由、触发原话、各批次材料/包围盒/校验/撤销与
程序源码前 `program_lines` 行（默认 40，0 = 不附）。源码另存 `logs/programs/<jid>.py`，压缩或重启后
仍可改参数续建。

台账之前的历史用 `tools/backfill_build_ledger.py` 回填：扫 `logs/sessions` 与 `logs/oneshot`，用
`logs/bot.log` 的 `[建造] 预览 <jid>` 补精确时间，按 jid 去重（恢复会话会重复落盘）。脚本幂等，
`--dry-run` 只统计，`--reset` 清空台账后重建。

### 5.2 会话对话

`search_history(query, since?, file?, limit?)` 在落盘会话里按关键词找对话行，返回“文件名 + 对话行号”，
用于“上次聊了什么/之前提过某个地方吗”。压缩/恢复会话会让同一句出现在多个文件里，结果按句子去重、只报最新的。

`read_session(file, contains?, around?, window?, max_chars?)`：

- 只接受纯文件名，不允许目录和路径穿越；文件最大 16 MiB。
- 复用 `Session.compact` 口径，只保留玩家消息和实际游戏内发言（含 ptc 内嵌），渲染为 `玩家: ...` / `会话中的 Agent 名称: ...`。
- 给 `contains` 或 `around` 时只读命中前后各 `window` 行（默认 3），不再整份渲染；默认最多 12000 字符
  （`session_read_max_chars`），超长保留开头与结尾。
- 只读历史，不恢复、不清空、不修改当前会话，也不执行历史或网页里的指令。

`history.list_sessions()` 仍保留给脚本与排障，但不再注册为模型工具：模型要定位直接 `search_history`，
先列文件清单再逐个读是旧版低效的根源。需要真正把最近主会话灌回上下文时使用控制词“恢复会话”。

## 6. ptc 并发模型## 6. ptc 并发模型

每个工具注册时声明并发类别：`capabilities.register(..., concurrency=...)`。

| 类别 | 调度方式 | 典型工具 |
|---|---|---|
| `parallel`（默认） | 相邻纯查询/HTTP 调用用线程池并行，结果仍按原顺序合并 | Wiki、find_items、get_player_activity |
| `bus` | 相邻服务端查询登记后合批下发，按请求 id 收包 | 坐标、手持、方块、空间查询 |
| `serial` | 按数组顺序逐个执行，作为前后并发组的屏障 | MC 指令、发言、set_mode、记忆、技能加载 |

serial 前面的 parallel/bus 组全部结束后才执行，serial 完成后才执行后续组，因此同批“先写后读”的顺序不会被并行打乱。
但“读取结果后再决定参数”属于真正的数据依赖，仍须拆成多次模型工具调用。

其他约束：

- 普通默认实际放行 24、对模型声明 12；创造为 48/24；creative_max 再 ×2，实际以配置与模式注记为准。
- ptc 结果普通默认 30000 字符、创造 60000，creative_max 再 ×2；超限会截断。
- 子线程复制当前请求的工具禁用集合和 ptc 上限，执行层二次校验不会因并发失效。
- `stop_on_error=true` 时，当前组出现 `[错误]`/`[警告]` 后跳过剩余调用。

## 7. 能力注册与指令安全

新增能力通常需要：

1. 编写接收 dict、返回字符串的 handler；
2. 编写 function schema；
3. 在 `_REGISTRY` 或启动时 `register()` 注册，并选择正确 concurrency；
4. 检查每个模式的白名单/黑名单；
5. 更新自测和本文。

本项目面向受信任的私人服务器，不做细粒度玩家权限判定：能进服且能聊天的玩家都可以请求 Bot 执行指令。
主要保护是 `command_blocklist`，默认拒绝 `stop`、`op`、`deop`、`whitelist`、`ban`、`ban-ip`、`save-off`、`save-on` 等。
这不是面向不可信公网玩家的安全边界；对外开放前必须重新设计认证、授权和审计。
