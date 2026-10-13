# mc-ai-bot — 维克托

把 Minecraft 基岩版服务器（运行在 screen 会话 `mc` 中）的聊天接入 DeepSeek。
AI 人设：**维克托·米哈伊洛维奇·切布里科夫 (Viktor Chebrikov)**，服务器智能管家。
已具备说话/沉默、长期记忆、服务器与玩家状态查询、执行服务器指令等能力（见下文“能力”）。
当前不硬编码任何指令词：每条玩家聊天都交给模型判断该不该回应。

## 架构

```
   ┌── 玩家聊天(行为包 viktor_bridge 桥接) / 进出服(BDS 原生日志) / 查询回包([VIKTOR-*] r<id>)
   ▼
bedrock_server ───► screen 日志(logs/server.log)
   ▲                     │ tail 解析(viktor/bot_app.py)
   │                     ▼
   │            会话上下文(append-only, 前缀缓存)
   │                     │
   │          Agent 循环(viktor/bot_agent.py) ⇄ DeepSeek API
   │                     │ function calling 工具执行
   │          capabilities.py + viktor/bot_tools.py
   │                     │
   └── screen -X stuff ◄─┘
       tellraw 回复 / 服务端指令 / scriptevent 查询
```

- 上下文**平时只追加、不重排、不做滑动窗口**：切模式/更新记忆只往日志尾部追加系统注记，
  保持 DeepSeek 前缀缓存命中。唯一的重写路径是**压缩**（见下文「压缩」）：只保留玩家消息与
  维克托的游戏内发言，其余工具调用/结果与正文移除；压缩后仍超预算才整段清空重开会话。
- 查询类工具(坐标/手持/方块/扫描)经 `scriptevent` 交给行为包脚本执行，回包同样落进 `server.log`，
  由 `ServerBus` 按请求 id 路由（见下文「服务端请求总线」）。

零第三方依赖，只用 Python 3.11+ 标准库。

## 代码结构

`bot.py` 只是入口（命令行参数 + 启动），实现全部在 `viktor/` 包里，按职责分层，**依赖方向严格单向向下、无环**：

```
bot.py(入口) → viktor.selftest(--test)
                   │
        viktor.Bot = BotCoreMixin + BotControlMixin + BotToolsMixin
                     + BotAgentMixin + BotAppMixin    ← 职责 mixin, 彼此不 import,
                   │                                     只用 self.* 经 MRO 协作
        session / bus / bridge / config / profiles
                   │
        paths / constants / prompts / schemas          ← 叶子层(不依赖项目内其它模块)
```

| 模块 | 职责 |
|---|---|
| `viktor/bot_core.py` | 构造、请求上下文(`_tls` 回落)、会话生命周期、待处理队列 |
| `viktor/bot_control.py` | 控制词(停止/清空/压缩/计划模式/恢复会话)、一次性对话调度 |
| `viktor/bot_tools.py` | 全部 `_tool_*` handler：聊天/查询(bus)/指令/常加载/备份/模式切换 |
| `viktor/bot_agent.py` | 模式参数、DeepSeek function calling 循环、worker 与收尾汇报 |
| `viktor/bot_app.py` | `logs/server.log` tail 解析、启动握手、主循环 |
| `viktor/session.py` | `Session`(append-only 上下文) 与 `OneShotContext` |
| `viktor/bus.py` / `viktor/bridge.py` | 服务端请求总线 / `screen` 注入与 `tellraw` |
| `viktor/profiles.py` | 模式组合表：提示词 × 限制 × 工具白名单 |
| `viktor/prompts.py` / `viktor/schemas.py` / `viktor/constants.py` / `viktor/paths.py` | 提示词 / 工具 schema / 常量 / 路径与日志(叶子层) |
| `capabilities.py` | 能力注册表(工具注册、ptc、记忆、技能书、物品速查) |

改一个方向的东西只需要动对应层：加工具 = `schemas.py` + `bot_tools.py`；调模式 = `profiles.py`；改提示词 = `prompts.py`。

## 会话与上下文机制

- **以 0→1 为初始化时机**：解析 `Player connected/disconnected` 维护在线人数；
  玩家全部离开（→0）**不结束会话**，正在进行的任务跨离线期继续跑；
  下次有人进服（0→1）时完整初始化新会话（上下文落盘到 `logs/sessions/`）。
  若进服时有任务正在进行：**不初始化、也不挂起初始化**，只发一条提示告知任务在跑，
  并介绍可用控制词（停止/强制停止/压缩/清空）；会话与上下文保留。
- **增量组装、前缀恒定**：system prompt 是常量；长期记忆与当前模式**不写进 system prompt**，
  而是作为 `role=system` 的系统注记追加在对话日志里（会话开始时一条记忆注记；
  `update_memory` 后再追一条最新记忆；`set_mode` 后在工具响应之后追一条模式注记）。
  日志只追加、不修改、不重排，逐轮请求前缀严格一致，DeepSeek 前缀缓存稳定命中
  （日志里 `缓存命中 N` 字段可看效果）。切模式/更新记忆只是尾部追加，不会把整段前缀作废。
- 服务器内所有聊天都进上下文（维克托能“听到”大家说话），但要不要回应、该不该沉默由模型自己判断。
- **任务进行中可插话调整**：Agent 多轮任务执行期间收到的玩家消息，会在安全点（工具往返闭合后）
  注入当前工作循环，模型下一轮即可调整方向/纠错，而不必等任务结束。消息由 worker 开轮时
  或安全点统一写入上下文，保证 `assistant(tool_calls)` 与 `tool` 严格成对。
  注入的消息**可能是任务调整，也可能是玩家间的普通闲聊**，由模型自行判断：相关的照做、
  无关的忽略并继续任务（提示词里已明确）。这些消息在注入时即被消费，不会再另起一轮。

## 模式（提示词 / 限制 / 工具白名单）

所有请求都走 `deepseek-flash`（DeepSeek-V4.1-Flash，支持 `effort` 思考强度档位 low/high/max）。

- **normal（普通）**：`effort=low`，回复短、便宜、快，适合闲聊和简单指令。
- **creative（创造）**：玩家说“开创造模式/认真做”等时切到。`effort=high`，并在切换时
  向对话尾部追加一条“创造工作方式”系统注记（先规划后施工、先试小块再铺开、成片 fill），
  同时放宽输出 token、工具轮次、ptc 批量、发言分段数。
- **creative_max（创造max）**：仅当玩家明确要求“最好/最强/最大/max/不惜代价”这类最高规格时才切到。
  `effort=max`，且上述各项上限在 creative 基础上再翻倍（工具轮次 32→64 等），最慢最贵。

模式由三张正交 profile 表组合而成（`viktor/profiles.py` 里 `PROMPTS` / `LIMITS` / `TOOLS` + `Mode`/`MODES`）：
**提示词**决定行为、**限制**决定数值预算（effort、输出 token、工具轮次、ptc 批量）、**工具白名单**决定模型能看到哪些工具。
`creative_max` = creative 的提示词 + 同一份 heavy 限制 ×2 + effort max；计划/执行模式就是共用 heavy 限制、只换提示词的例子。

切换用 `set_mode(mode, reason?)`，**可选目标由程序按当前模式注入 `mode.enum`**：普通 ↔ 创造/创造max 互相可达；一次性根本没有 `set_mode` 工具；计划模式只能切到执行模式。也就是**不能通过任何方式切进一次性/计划模式**，未列出的模式对模型不可知。
每次切模式会在 tool 响应之后追加一条**模式注记**（当前模式 + 行为提示词 + 刷新后的 ptc 单次上限/工具轮次/输出上限），只往日志尾部加、不改 system 前缀；切模式/更新记忆都不会让前缀缓存失效。
思维链（`reasoning_content`）只写入 `logs/bot.log`，不进会话上下文。

## 撞轮次上限：一次收尾汇报

单次任务的工具轮次有上限（见模式注记）。轮次用尽时**不再由程序替它发消息**，而是给模型一次
「无工具」收尾机会：追加一条系统注记，要求它用正文汇报「已完成什么」+「下一步计划」，并引导玩家回复
「继续」继续或说明调整——这就是那次“停下核对”。

- 收尾请求不带 `tools`（`params["no_tools"]`），模型只能出正文，由 `_finish_turn` 兜底播报并写回上下文
  （`_wrap_up_reply()`）。
- **轮次预算按“本轮用到过的最高模式上限”计**（`round_cap` 只增不减）：中途从创造切回普通这类
  低上限模式时不会把已用轮次“倒扣”成超限、误触发收尾（创造上限 32/64 vs 普通 8，否则"干完切回普通"几乎必现）。
- 一次性对话是闭式任务，不走“继续”，仍用它自己的固定回执。
- 仅当收尾这一步本身失败（通常是 API 报错）时，才退回一句程序兜底，避免玩家对着沉默。

## 计划模式 / 执行模式

由硬编码控制词驱动（任何玩家可用，不走模型）：

- **`计划模式`**：切到计划模式，回一条“已切换到计划模式，发送「退出计划」可退出计划模式”，然后 **nudge 一次**让 Agent 主动开口引导玩家规划。**不重置上下文**，以便利用已有上下文（例如之前用创造模式做过什么）。
  - 限制与创造max 对齐（`effort=high`，其余数值 = heavy ×2）；但工具用**黑名单**：`run_server_command` / `pin_region` / `backup_world` 不给出（未列出的模型看不到），因此计划阶段不能改世界；查询/说话/记忆/ptc/`set_mode` 仍在。
  - 提示词要求**计划精确到坐标**（范围、基准点、材料、步骤顺序、验收标准），并明确告知规划者**执行是一次性**（单轮做完，超出就分阶段），定稿并经玩家确认后，模型 `set_mode("execute")`。
- **`退出计划`**：任何时刻把计划模式切回 normal（程序处理）。
- **执行模式**：模型从计划模式切过来；限制同计划，工具全开。**一次性周期**——本回合执行完（或停止/出错）后**程序自动切回 normal**，不依赖模型自觉。

模型侧 `set_mode` 的 `next_modes`：普通↔创造/创造max；计划→执行；执行→normal；一次性无 `set_mode`。`计划模式`/`退出计划` 是仅有的两个进入/退出计划的硬编码词，因此**一次性/计划模式无法被 `set_mode` 切进去**。

## 一次性对话（`1 ...`）

玩家在聊天里以 `1 ` 开头（数字 1 + 空格；单独发一个 `1` 也算，随后提示补内容）时，触发**一次性对话**。任何玩家都能用。

- **不进主对话**：触发词、这次的全部工具往返与上下文都不进主会话，主对话完全不知道它存在，也不会顺带开启/清空主会话。每次一次性单独落盘到 `logs/oneshot/`。
- **新状态、闭式完成**：组装提示词时追加一次性规则，bot 知道这是一次“下达指令 → 执行 → 回报”的任务，必须一次做完、**不能中途向玩家提问**。但允许一整轮多步工具调用（例：先查坐标 → 写长期记忆 → 发消息回报）。
- **只做确定性操作**：不切创造模式、不设常加载区域、不做开放式设计或大规模施工。
- **模糊请求**：若完全无法判断，只回一条——说明缺哪些关键细节、请补充后重新组织再发，并提醒这是一次性对话。
- **可并发**：主任务进行中也能触发，且支持同时多个一次性对话（`oneshot_max_concurrent`，默认 4）。因为查询类工具共用同一条 `server.log`，**工具执行会全局串行**（API 调用仍并行），避免并发时抢到彼此的回包。
- **中断**：`1 强制停止` 立即停止**全部**正在进行的一次性对话；没有 `1 停止`。bare `停止/强制停止` 仍只作用于主对话。
- **工具白名单**：一次性对话只暴露一张确定性的工具白名单（不含 `pin_region`、`set_mode`、`stay_silent`）；未列出的工具模型根本看不到，执行层再以「全量 − 白名单」兜底，防止经 `ptc` 夹带。

相关配置：`oneshot_effort`、`oneshot_max_reply_tokens`、`oneshot_max_tool_rounds`、`oneshot_max_concurrent`。

## 运行

```bash
./run.sh                      # 前台运行(自动重新应用 screen 日志设置)

# 或挂后台:
screen -dmS viktor bash -c "cd /home/jrj/repo/mc-ai-bot && ./run.sh"
screen -r viktor              # 查看(Ctrl+A D 退出)

./restart.sh                  # 平滑重启: 优雅退出(落盘当前会话) → 带 VIKTOR_RESTORE 自动灌回, 玩家无感

python3 bot.py --test         # 解析逻辑自测
```

`restart.sh` 做的事: 找到唯一的 bot 进程 → `kill -TERM` 优雅退出(触发会话落盘到 `logs/sessions/`) →
取最新落盘、以 `VIKTOR_RESTORE=<它>` 重新起 screen。升级代码/改配置后用它对玩家零感知。

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
| `get_player_position(player?)` | 在线玩家实时坐标（行为包脚本，无指令可查）。返回整数**方块坐标**（向下取整），与玩家屏幕左上角显示的坐标完全一致 |
| `get_player_hand(player?)` | 在线玩家手持物品 |
| `get_block(x, y, z, dimension?)` | 读坐标上的方块类型与状态（行为包脚本；基岩版无 `/data`） |
| `scan_blocks(x1..z2, dimension?, filter?)` | 批量扫一个 1 格厚切面（≤16×16×1，厚轴可为 X/Y/Z）：默认回非空气方块，给 `filter` 则回类型含该关键字的方块并附未匹配类型统计 |
| `find_items(query?, category?, limit?)` | 查基岩版物品/方块 ID 速查表（唯一权威来源）。`query` 支持中文/英文/ID 片段子串匹配，`category` 限定分类，不传参数返回分类总览。结果 id 可直接用于 `give`/`fill`/`setblock` |
| `use_skill(name, file?, force?)` | 按需载入一本技能书（skill）的正文；`file` 展开其附带资料。系统在会话开头只列出技能名与适用场景，正文用时才载入 |
| `pin_region(x1, z1, x2, z2)` | **仅创造/执行模式下可用**：把施工面设为常加载（ticking area，自动按 ≤100 区块切片）：防止玩家走开/离线后区块卸载导致 fill 失败。**生命周期 = 创造/执行模式**：离开这些模式（切回 normal 等）或会话结束时自动移除 |
| `backup_world()` | 把当前存档热备份成 `.7z`（`save hold` → 7z → `save resume`） |
| `set_mode(mode, reason?)` | 切换运行模式；可选目标按当前模式动态注入（普通↔创造/创造max；计划→执行；一次性无此工具） |
| `ptc(calls, stop_on_error?)` | 批量工具调用：一次提交多条工具调用，合并成一条结果。连续的查询类调用（坐标/手持/方块/扫描）会合成一批一次性下发，只等一趟往返；施工/状态变更仍按顺序串行（省往返与上下文） |

能力注册表在 `capabilities.py`，可运行时 `register()` 扩展。

### 物品/方块 ID 速查表

解决“玩家说别名/口语、模型想不起 ID、自由创作不知道有哪些 ID”三类问题。
数据全部来自**服务器本体**，版本精确、无需手工维护：

- **ID 清单**：行为包 `scriptevent viktor:ids` 调 `ItemTypes.getAll()` / `BlockTypes.getAll()` 导出
  （控制台跑一次，输出 `[VIKTOR-IDS] …`，先落到 `data/raw_ids.txt`）
- **译名**：`resource_packs/vanilla/texts/{zh_CN,en_US}.lang` 官方译名
- 生成脚本 `tools/build_items.py` 把二者合成 `data/items.json`（`id → {中文名, 英文名, 分类, 别名}`）；
  基岩版 lang 键新旧混杂（`tile.birchFence` / `tile.wooden_slab.birch` / `tile.concretePowder.black`），
  脚本用一组“族规则 + 通用旋转”反查，约 89% 能自动拿到中文名，其余退化为英文名（模型可自行翻译）。
  同义词/Java 名/口语别名写在 `data/item_aliases.json`。

**Agent 友好 / 省 token 的做法**：整表（~1240 项）**绝不进提示词**，只暴露一个 `find_items` 工具按需检索，
命中结果才进上下文；中文名让“混凝土”“台阶”这类模糊词直接子串命中整族。所有模式（含一次性/计划）都可查。

服务器升级后重跑：控制台 `scriptevent viktor:ids` → 更新 `data/raw_ids.txt` → `python3 tools/build_items.py`。

### 技能书（skill）

把“按需才需要的长篇技能知识”从提示词里拆出去，用到才载入。移植自 pi Agent 的
[skills 机制](../)（描述常驻、正文按需、附件再按需）：

- **格式**：一个目录 + `SKILL.md`，YAML frontmatter 声明 `name` / `description`（目录可再带 `references/*.md` 等资料）。
  直接兼容 pi / Agent Skills 规范的技能目录，放进去即生效，**加技能不改代码**。
- **常驻层**：会话开始时只把每本技能的 `name + description` 作为一条 system 注记注入
  （`capabilities.skills_note()`，在 `_start_session` / `_spawn_oneshot` 里追加），正文不进上下文。
- **按需层**：模型判断任务落在某技能范围内时调用 `use_skill(name)`，正文才作为工具结果进上下文；
  技能若附带 `references/`，`SKILL.md` 会列出文件名，模型用 `use_skill(name, "references/x.md")` 再展开。
- **去重**：同一会话内重复载入同一技能会直接返回“已载入过”（`Session.loaded_skills`），加 `force=true` 可强制重载。
- **优先级**：技能只是补充说明，**与 system prompt 冲突时以 system prompt 为准**（已写入技能清单注记）。

内置示例：

- `skills/mc-commands/`（基岩版命令施工手册：fill/setblock/clone 变体、方块状态与朝向、
  超量分段、施工套路；附表 `references/block-states.md` 是实测状态名）。
- `skills/mc-shapes/`（体素造型手册：扫描公式画圆/椭圆/拱/圆柱/球/圆顶，用楼梯台阶做柔和曲面；
  附表 `references/circle-tables.md` 是半径 1–30 的 1/4 弧表、偶数直径环表、球体逐层半径表，
  `references/smooth-surfaces.md` 讲坡度配比与包边）。
- `skills/mc-interior/`（室内装修手册：家具方块能力总表、房间功能清单、家具拼搭配方、配色与灯光；
  附表 `references/furniture.md` 是 40+ 件家具的摆法与命令，`references/rooms.md` 是各房间必备清单，
  `references/palette-light.md` 是配色与隐藏光源）。
- `skills/mc-architecture/`（建筑设计与结构手册：体块/比例/模数、承重体系选型与搭法、立面门窗屋顶、
  风格库；附表 `references/structure.md` 讲梁柱/拱券/穹顶/飞扶壁/桁架/框架/承重墙/悬挑/柱式/斗拱，
  `references/facade.md` 讲三段式立面与门窗屋顶，`references/styles.md` 是 16 种风格要素）。
- `skills/mc-terrain/`（地形与景观手册：自然感五律、高度场方法、山崖河谷湖海沙丘沼泽火山、
  自定义树木、水景道路桥、农田梯田、与建筑衔接；附表 `references/landforms.md`、
  `references/vegetation.md`、`references/water-road.md`）。
- `skills/mc-greenery/`（绿化与景观手册：室内绿植、庭院花园、建筑周边、绿墙绿顶、水景、树木灌木地被、
  步道与口袋公园；附表 `references/plants.md` 是植物能力表，`references/landscape.md` 讲庭院与风格园林，
  `references/pocket-parks.md` 是口袋公园分区布局）。
- `skills/mc-tellraw/`（基岩版 tellraw 手册：rawtext JSON 文本组件、clickEvent/hoverEvent、
  坐标传送/网页/导航菜单/公告按钮；附表 `references/rawtext.md` 是组件字段与转义，
  `references/examples.md` 是可套用模板）。
- `skills/mc-weathering/`（做旧与细节手册：风化预算、材质风化配方、损伤语法、修补痕迹、生活道具与叙事细节；
  附表 `references/aging.md` 是风化/损伤/修补配方，`references/details.md` 是道具与场景模板）。

以上技能全模式可用（含一次性/计划）。

新增技能只需建目录 `skills/<name>/SKILL.md`，写好 frontmatter 的 `description`（要同时说清“是什么 + 何时用”）。

### 行为包脚本桥

BDS 控制台 **不回显玩家聊天**，所以用行为包 `viktor_bridge` 订阅事件并 `console.log`：

- `world.beforeEvents.chatSend` → `[VIKTOR-CHAT] 玩家: 内容`
- **协议 v2**：bot 在事件参数最前面带一个请求 id `r<数字>`，脚本把该 id 原样回显在每一行里；bot 可一次下发整批请求、按 id 认领各自回包（见下文「服务端请求总线」）。不带 id 时保持旧格式，向后兼容。
- `scriptevent viktor:pos [id]` → `[VIKTOR-POS] [id] 玩家 x y z 维度`（整数方块坐标，与玩家屏幕一致），末行 `[VIKTOR-POS] [id] DONE`
- `scriptevent viktor:inv [id]` → `[VIKTOR-INV] [id] 玩家 槽位 物品 数量`（每人末行 `DONE 手持槽位`，全体末行 `[VIKTOR-INV] [id] DONE`）
- `scriptevent viktor:block [id] <x> <y> <z> [维度]` → `[VIKTOR-BLOCK] [id] x y z 维度 方块ID [状态]`
- `scriptevent viktor:scan [id] <x1> <y1> <z1> <x2> <y2> <z2> [维度] [过滤]` → 逐行 `[VIKTOR-SCAN] [id] x y z 维度 方块ID [状态]`，末行 `[VIKTOR-SCAN] [id] DONE total=.. matched=.. unloaded=.. other=..`。扫描用 `system.runJob` 周期性让出主线程，不再卡世界。
- `scriptevent viktor:hello <nonce>` → `[VIKTOR-HELLO] <nonce> v2`：bot 启动时的协议握手，确认行为包装了新协议后才启用请求总线
- `scriptevent viktor:ids` → 分块输出全部物品/方块 ID（`[VIKTOR-IDS] ITEMS/BLOCKS …`、末行 `DONE`），供离线重建 ID 速查表

需要 `@minecraft/server` 的 **beta** 模块与 `level.dat` 里的实验开关。
修改脚本后用控制台 `reload` 热重载，不必重启服务器。

#### 服务端请求总线（降低查询延迟）

`bedrock_server` 每隔约 0.8–1.0s 才把 stdin 里积压的控制台命令整批读走一次。因此逐个下发查询要逐个等 ~1s，
而把一批 `r<id>` 请求一次 `stuff` 进去只付一次轮询延迟。`viktor/bus.py` 的 `ServerBus` 负责：登记 → 一次下发 →
一个读线程 tail `server.log` 按 `[VIKTOR-*] r<id>` 路由 → 各请求按自己的 id 收齐。
`ptc` 里连续的查询类调用会自动合成一批下发（每批上限 `bus_batch_max`）；
指令执行/常加载/备份这类“读任意控制台输出、无法按 id 认领”的工具仍用 `console_gate` 串行。
若行为包未升级（`viktor:hello` 无响应），查询工具会明确报错提示重载行为包，而不是错领回包。

### 指令安全

不做玩家权限判定——能进本服（`allowlist.json`）的都是自己人，**任何玩家**都可以让维克托执行指令。
唯一的保护是**危险指令黑名单**：`stop`/`op`/`deop`/`whitelist`/`ban` 等（见 `command_blocklist`）一律拒绝。

## 停止 / 强制停止 / 撤销（中断运行中的任务）

玩家在游戏里单独发一条控制词（完全匹配，前后空白可忽略）时，系统**不走模型**，直接生效并回执：

- **`停止`**（软停止）：到安全点停止——不打断正在执行的工具，当前步骤做完、
  工具往返闭合后，在下一次工具调用/下一轮开始前停下。回“收到，我把当前这一步做完就停”。
- **`强制停止`**：立即中止，连工具内部的轮询等待（`run_server_command`/坐标/手持）也打断。
  回“已强制停止当前任务。”
- **`不停止`**：撤销**还未生效**的停止/强制停止，任务继续；已停下的无法撤销。
- 空闲时发停止 → 回“当前没有正在执行的任务。”
- 不是完全匹配（如“维克托，停止”）→ 当普通聊天交给模型判断

被中止的 `tool_calls` 会补上 `(已中止)`/`(已到安全点停止)` 响应，保证上下文里的
`assistant(tool_calls)` 与 `tool` 始终成对——否则 DeepSeek 会报 400。

控制词消息**不进上下文**，以免在多线程追加时插到工具序列中间。

## 清空（重置会话）

玩家单独发一条 **`清空`**（完全匹配）时，不走模型，直接对整个会话做**完整初始化**——
和「玩家数 0 → 1」开新会话完全一致：

- 结束当前会话（落盘到 `logs/sessions/`、创造模式复位回 `normal`）
- 开启一个全新会话（新 session id、空上下文、重新注入长期记忆）
- 有任务在跑 → 先中止任务，到安全点（工具往返闭合）再重置，避免拆散 `tool_calls`，否则 DeepSeek 会报 400

上下文超过输入预算时先自动**压缩**（见下节）；压缩后仍超预算（例如玩家消息本身就超）才由
`_maybe_compact_for_size()` 触发**同一套完整初始化**。清空/自动清空后旧会话已落盘，可用下面的 `恢复会话` 找回。

## 压缩（保留对话，移除过程）

玩家单独发一条 **`压缩`**（完全匹配，任何玩家，不走模型），或上下文超过输入预算**自动触发**
（每次请求开始时 + 每个工具轮次的安全点各查一次），会把会话压缩成一份「对话记录」：

- **保留**：全部玩家消息；维克托的游戏内发言（`send_chat_message` 直接调用；`ptc` 里夹带的
  `send_chat_message` 会被重写成只含这些子调用，结果也只留对应行并重新编号）。
- **移除**：其他工具调用与结果、assistant 普通正文、思考内容（`reasoning_content`）、旧系统注记。
  保留的 `assistant(tool_calls)` 与 `tool` 结果严格成对（配不全的整条丢弃），直接接着写不会 400。
- **换新会话**：旧会话完整落盘成 `logs/sessions/compact-YYYYmmdd-HHMMSS-s<id>.jsonl` 留档，
  新会话重新注入 长期记忆 / 技能书 / 当前模式 三条开场注记，末尾追加一条 `# 上下文已压缩` 系统注记
  （它天然位于下一条玩家消息之前）。模式、常加载区域、玩家名单都不变；已载入技能集合随新会话清空
  （技能正文已不在上下文，需要时重新 `use_skill`）。
- 有任务在跑（或队列有待处理消息）时压缩无效，回 `[系统]` 提示先「停止」/「强制停止」；一次性对话不压缩。
- 压缩后仍超预算 → 走「清空」的兜底完整初始化。
- 压缩是**有意为之的有损重写**（会打破此前的前缀缓存；压缩后的新前缀从下一次请求起重新稳定命中），
  `compact-*` 留档**不参与**「恢复会话」与 `restart.sh` 的自动恢复（两者只认 `session-*.jsonl`）。

## 恢复会话

`恢复会话`（完全匹配，任何玩家，不走模型）把**最近一次落盘的会话**灌回当前上下文：

- 每次完整初始化（`0→1` / `清空` / 超预算兜底清空）都会把旧会话落盘到 `logs/sessions/session-*.jsonl`；`恢复会话`（与 `restart.sh` 自动恢复）取其中最新的一个；压缩留档 `compact-*.jsonl` 不参与。
- 模式也从那条会话最后一条模式注记（`# 当前模式: …`）推断恢复。
- 旧版落盘里带 `tool_calls` 的 assistant 可能缺 `reasoning_content`，恢复时统一补空串，避免思考模式 + tools 报 400。
- 新会话开始（`0→1` 进服）会回一条 `[系统] 新会话已开始。发送「恢复会话」可找回上一段对话。`
- **平滑重启**：以 `VIKTOR_RESTORE=<落盘会话路径>` 启动时，启动后自动把该会话灌回（静默、不发聊天），
  用于升级/重启时对玩家无感。先 `kill -TERM <pid>` 优雅退出（会落盘），再用该环境变量重启即可。

## 控制面词

硬编码、完全匹配、**不走模型、不进上下文**：`停止` / `强制停止` / `不停止` / `清空` / `压缩` / `计划模式` / `退出计划` / `恢复会话` / `正文开` / `正文关` / `工具开` / `工具关`；其余所有聊天仍交给模型判断。

程序生成的控制面回执一律带 **`[系统]`** 前缀（如 `[系统] 已清空…`、`[系统] 已切换到计划模式…`），且**不带 `<维克托>` 前缀**（与 `[正文]`/`[工具]` 一致）；模型经 `send_chat_message` 发出的回复才带 `<维克托>`——玩家据此区分「系统提示」与「AI 发言」。

## 正文 / 工具转发（观察运行状态）

玩家会担心“AI 好久没说话是不是卡了”，但正文/工具刷屏又吵。用完全匹配的 `正文开` / `正文关`、`工具开` / `工具关` 切换两路旁路转发（程序处理、**不走模型、不进上下文**，任何玩家可切换，**会话初始化默认都关**）：

- **`正文开`**：模型每轮的正文（`content`，含带 `tool_calls` 的轮次）以 `[正文] …` 前缀发到聊天。
- **`工具开`**：每次工具调用以 `[工具] {工具命令前 20 字}` 前缀发到聊天（`run_server_command` 给命令；`ptc` 给子工具名）。
- 两路都只是**显示**：通过控制台 `tellraw` 发出，不写入会话上下文，也不会被当成玩家聊天回灌。

## 配置（config.json）

| 键 | 说明 |
|---|---|
| `model` / `temperature` / `max_reply_tokens` / `api_timeout_sec` | DeepSeek 参数 |
| `api_min_interval_sec` | 全局 API 最小间隔（保护缓存前缀顺序与限流）；每次尝试（含重试）都遵守 |
| `api_max_attempts` / `api_retry_backoff_sec` | 单次 API 请求的最大尝试次数（默认 3）与指数退避基数秒（默认 1，上限 30s，尊重 `Retry-After`）。只对超时/429/5xx 等瞬态错误重试；400/401 等直接失败。全部尝试失败时回一条 `[系统]` 告诉玩家稍后重发 |
| `context_window_tokens` / `context_safety_tokens` | 模型窗口（`deepseek-flash` 为 1M）与安全余量。输入预算 = 窗口 − 本轮输出上限 − 余量；超出预算自动**压缩**（只留玩家消息与发言），压缩后仍超才整段清空并完整初始化；自动处理的通知受 `notify_context_clear` 控制 |
| `reply_chunk_len` / `reply_max_chunks` | 回复分片发送，防止过长 |
| `mc_server_dir` | 服务器目录（备份时定位世界存档） |
| `command_blocklist` | 禁止执行的指令 |
| `command_result_timeout_sec` / `position_timeout_sec` / `inventory_timeout_sec` / `block_timeout_sec` / `scan_timeout_sec` | 等待脚本/控制台回包的秒数 |
| `bus_protocol` | 服务端请求总线协议：`auto`（默认，用 `viktor:hello` 探测）/ `v2`（跳过探测）/ `off`（禁用，查询报错） |
| `bus_reader_poll_sec` | 总线读线程 tail `server.log` 的轮询间隔（默认 0.05） |
| `bus_batch_max` | 一次下发给服务端的查询请求上限（默认 8），保护服务端主线程 |
| `scan_result_limit` | `scan_blocks` 返回文本的字符上限（超出截断） |
| `normal_effort` / `creative_effort` / `creative_max_effort` | 各模式的思考强度（low / high / max） |
| `oneshot_effort` / `oneshot_max_reply_tokens` / `oneshot_max_tool_rounds` / `oneshot_max_concurrent` | 一次性对话的思考强度、输出上限、工具轮次上限与最大并发数（默认 low / 6000 / 4 / 4） |
| `parallel_tool_calls` | 是否告诉 API 允许一次返回多个工具调用（默认 true） |
| `ptc_max_calls` / `ptc_stated_calls` | `ptc` 程序放行数（24）与对模型声明的口径（12）——留一倍余量 |
| `ptc_result_limit` / `creative_ptc_result_limit` | `ptc` 合并结果的字符上限（30000 / 60000；`creative_max` 再 ×2） |
| `creative_ptc_max_calls` / `creative_ptc_stated_calls` | 创造模式下的同一对数值（48 / 24） |
| `creative_max_reply_tokens` / `creative_max_tool_rounds` / `creative_reply_max_chunks` | 创造模式放宽的各项上限；`creative_max` 下这些上限自动 ×2（工具轮次 32→64、ptc 48/24→96/48 等） |
| `backup_dir` | 备份输出目录（默认 `/home/jrj/mc_backup`，文件名 `世界名-YYYYmmdd-HHMMSS.7z`） |
| `backup_hold_timeout_sec` / `backup_timeout_sec` | 等 `save hold` 完成 / 7z 打包的超时 |
| `backup_compression_level` | 7z 压缩级别（`-mx`，默认 5） |
| `pin_max_areas` | `pin_region` 单次最多切几个常加载片（默认 6；基岩版单片上限 100 区块、全维度上限 10 个） |
| `max_queue` | 已移除；每条聊天都由模型判断 |

> screen 日志的 flush 间隔必须调小（`logfile flush 1`，见 `run.sh`），
> 否则指令输出、脚本回包会延迟十几秒才落盘，导致捕捉超时。

## 文件

- `logs/server.log` — screen 捕获的服务器控制台输出（bot 的数据源）
- `logs/bot.log` — 机器人运行日志
- `logs/sessions/session-*.jsonl` — 每次会话的完整上下文存档（可被「恢复会话」找回）；`logs/sessions/compact-*.jsonl` — 压缩前的完整留档（仅供排障）
- `memory.md` — 长期记忆（会话开始时注入为系统注记；人工直接改动在下一次会话生效，`update_memory` 则即时追加新注记），备份在 `logs/memory-backup/`
- `capabilities.py` — 能力注册表
- `viktor/` — 机器人实现包：入口组装(`__init__.py`) + 职责 mixin(`bot_*.py`) + 会话/总线/桥/模式/提示词/schema/常量/自测(详见“代码结构”)
- `data/items.json` — 物品/方块 ID 速查表（`tools/build_items.py` 生成；含中文名、分类、别名）
- `data/raw_ids.txt` — `scriptevent viktor:ids` 导出的原始 ID 清单（重建速查表的输入）
- `data/item_aliases.json` — 手写的同义词/Java 名/口语别名
- `tools/build_items.py` — 从 `data/raw_ids.txt` + 官方 lang 生成 `data/items.json`
- `skills/<name>/SKILL.md`（+ `references/`）— 技能书；`use_skill` 按需载入，会话开头只注入名字与描述
- `/home/jrj/mc_backup/` — 存档备份输出目录
- `run.sh` — 启动脚本：重设 screen 日志设置并跑 bot
- `restart.sh` — 平滑重启：优雅退出(落盘会话) → 带 `VIKTOR_RESTORE` 自动灌回，玩家无感
