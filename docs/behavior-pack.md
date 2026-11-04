# 行为包协议与请求总线

行为包源码位于 [`behavior_pack/viktor_bridge/`](../behavior_pack/viktor_bridge/)，当前协议为 **v4**。
部署和软链接维护见该目录的 [README](../behavior_pack/README.md)；空间查询和建造的高层用法分别见
[工具与并发](tools.md) 与[建造引擎](build-engine.md)。

## 1. 为什么需要行为包

BDS 控制台不回显玩家聊天，也没有 Java 版 `/data` 等查询能力。`viktor_bridge` 使用
`@minecraft/server` 订阅聊天、读取世界并通过 `console.log` 写回 screen 日志；Bot 再用
`screen -S mc -X stuff` 注入 `scriptevent`，形成双向桥接。

```text
Bot ── scriptevent viktor:* [r<id>] ──► BDS 行为包
Bot ◄── logs/server.log: [VIKTOR-*] r<id> ... ──┘
```

聊天事件：

```text
world.beforeEvents.chatSend → [VIKTOR-CHAT] 玩家: 内容
```

进出服仍使用 BDS 原生的 `Player connected/disconnected` 日志。

## 2. 协议版本与握手

| 协议 | 能力 |
|---|---|
| v3 | 请求 id 路由、JSON 分帧回包、高度图/切面/区域检查/找方块/能力查询 |
| v4 | 在 v3 上增加世界快照与 preview/commit/undo 建造引擎 |

启动握手：

```text
scriptevent viktor:hello <nonce>
[VIKTOR-HELLO] <nonce> v4
```

`bus_protocol=auto` 默认通过 hello 探测；`v3` 跳过探测；`off` 禁用总线，相关查询明确报错。
协议不足时，空间查询或建造工具会提示重载/升级行为包，而不是猜测或错领旧格式回包。

能力广播：

```text
scriptevent viktor:caps [r<id>]
[VIKTOR-CAPS] r<id> ... { protocol, apis, limits }
```

结果包含协议号、`runJob` / `fillBlocks` / `runCommand` 可用性以及帧长、每 tick 工作量、查询体积等上限。

## 3. 请求 id 与分帧

请求第一个参数可带 `r<数字>`；脚本在回包中保留该 id。不带 id 的旧式点查格式仍兼容，但总线工具使用 id 路由。

- 点查可直接返回若干行，末行用 `DONE` 表示结束。
- 较大的查询结果编码为一个 JSON payload，再切成多帧：

```text
[VIKTOR-XXX] r<id> #1/n <片段>
[VIKTOR-XXX] r<id> #2/n <片段>
...
[VIKTOR-XXX] r<id> DONE
```

`viktor/bus.py` 按请求 id 收集，并按帧号而非到达顺序重组。缺帧、重复/异常帧或超时直接报错，
不静默返回截断 JSON。行为包当前下行帧正文常量为 700 字符；建造上行另有更严格的 560 字符限制。

## 4. 点查与 ID 导出

| 控制台事件 | 日志回包 | 用途 |
|---|---|---|
| `scriptevent viktor:pos [id]` | `[VIKTOR-POS] [id] 玩家 x y z 维度`，最后 DONE | 在线玩家整数方块坐标 |
| `scriptevent viktor:inv [id]` | `[VIKTOR-INV] [id] 玩家 槽位 物品 数量` 与 DONE | 在线玩家手持物品 |
| `scriptevent viktor:block [id] <x> <y> <z> [维度]` | `[VIKTOR-BLOCK] [id] x y z 维度 方块ID [状态]` | 单点读取方块与状态 |
| `scriptevent viktor:ids` | `[VIKTOR-IDS] ITEMS/BLOCKS ...`，最后 DONE | 导出服务器本体的物品/方块 ID |

`scriptevent viktor:ids` 用于离线重建 `data/raw_ids.txt` 和 `data/items.json`，步骤见[工具与并发](tools.md#2-物品方块-id-速查表)。

## 5. 空间感知原语（v3）

| 事件 | 回包 | 说明与上限 |
|---|---|---|
| `viktor:heightmap [id] <x1> <z1> <x2> <z2> [维度] [yMax] [yMin]` | `[VIKTOR-MAP]` + JSON | 每列地表 y 与顶面方块；≤4096 列 |
| `viktor:slice [id] <axis> <level> <a1> <b1> <a2> <b2> [维度]` | `[VIKTOR-SLICE]` + JSON | 调色板 + base36 行；≤4096 格 |
| `viktor:inspect [id] <x1> <y1> <z1> <x2> <y2> <z2> [维度] [filter] [detail] [limit]` | `[VIKTOR-INSPECT]` + JSON | 类型计数；filter 时给 match/mismatch 与坐标；≤32768 格 |
| `viktor:find [id] <方块ID> <x1> <y1> <z1> <x2> <y2> <z2> [维度] [limit]` | `[VIKTOR-FIND]` + JSON | 类型子串匹配的总数与坐标；≤32768 格 |

细节：

- 高度图利用相邻列高度相关性，从上一列高度向上/向下搜索，而不是每列从 y=320 逐格扫到底。
- `axis=y` 时 a=x、b=z；`axis=x` 时 a=z、b=y；`axis=z` 时 a=x、b=y。
- 侧视/前视自动按高度从高到低输出，避免图倒置。
- `inspect` 的不符合项优先报告空洞，适合施工复检；`detail=cells` 可返回具体单元。
- `find` 和 `inspect(filter=...)` 都是类型子串匹配，例如 `ore` 可匹配矿石族。
- 大范围读取通过 `system.runJob` 按 `CELLS_PER_TICK=512` 让出主线程，避免长时间卡住世界。

## 6. 世界快照与建造（v4）

```text
scriptevent viktor:snapshot [id] <x1> <y1> <z1> <x2> <y2> <z2> [维度]
→ [VIKTOR-SNAP] + JSON（palette + RLE，≤65536 格）
```

索引 0 的 `?` 表示未加载/未知。快照用于 `build_preview(scan=...)`、`render_region` 和悬空检查。

建造事务：

```text
viktor:build put <jid> <i>/<n> <片段>
viktor:build preview <r<id>> <jid>
viktor:build commit  <r<id>> <jid>
viktor:build undo    <r<id>> <jid|->
viktor:build list    <r<id>>
viktor:build abort   <jid>
viktor:build drop    <jid>
→ [VIKTOR-BUILD] <r<id>> + 分帧 JSON
```

- 上行每帧 560 字符，一帧一次 `screen stuff`；不要把多帧拼进一次 stuff。
- 期望体积为 palette（0=KEEP）+ y/z/x 顺序 base36 RLE。
- 提交前重新 diff，贪心合并长方体后调用 `fillBlocks`，最后自动复读校验。
- `[VIKTOR-BPROG] <jid> <d|w|v> <done>/<total>` 是独立进度事件，不进入总线回包。
- 暂存数、TTL、撤销栈和当前多格方块处理见[建造引擎](build-engine.md)。

## 7. ServerBus：降低查询延迟

BDS 大约每 0.8–1.0 秒批量读取一次 stdin。逐条查询会各付一次轮询延迟；`ServerBus` 则：

1. 为一组查询登记独立 `r<id>`；
2. 一次性下发整批 scriptevent；
3. 读线程 tail `server.log`，按 tag + id 路由；
4. 各请求独立收齐行/分帧并结束。

`ptc` 中相邻的 bus 查询会自动合批，每批默认最多 `bus_batch_max=8` 个。控制台指令、常加载、备份等
需要读取任意控制台输出、无法按 id 认领的操作仍经 `console_gate` 串行，避免抢回包。

相关配置：`bus_protocol`、`bus_reader_poll_sec`、`bus_batch_max`、`position_timeout_sec`、
`inventory_timeout_sec`、`block_timeout_sec`、`spatial_timeout_sec`。

## 8. 依赖与热重载

当前部署基线为 BDS 1.21.132.3：

- `@minecraft/server = 2.5.0-beta`
- `@minecraft/server-ui = 2.1.0-beta`

该服务端的稳定版 server 2.4.0 / ui 2.0.0 虽可加载，但 `world.beforeEvents.chatSend` 不可用，因此不能改回稳定版。
还需要在 `level.dat` 中启用对应实验脚本能力。

| 改动 | 生效方式 |
|---|---|
| `scripts/main.js` | `node --check` 后在 BDS 控制台 `reload`，再用 hello 验证 |
| `manifest.json` 的依赖/版本/UUID | 必须重启 BDS；`reload` 不重读 manifest |

`reload` 会中断进行中的扫描并清空建造暂存与撤销栈；服务器有玩家或 Bot 忙时不要随意执行。
在开发设备上没有运行中的 BDS 时，只做静态语法检查和离线自测，不要把部署命令当作本地测试步骤。

## 9. 修改协议时的检查清单

1. 同步修改行为包、`viktor/constants.py` 的路由正则/协议号和 `viktor/bus.py`。
2. 若改 schema 或工具参数，同步 `viktor/schemas.py`、handler 与技能书。
3. 保持请求 id、DONE、分帧序号、缺帧错误和超时语义一致。
4. 运行 `python3 bot.py --test` 与 `node --check behavior_pack/viktor_bridge/scripts/main.js`。
5. 仅在已部署服务器且 Bot 空闲时 reload；随后用 hello/caps 和短小的只读查询做实测。
6. 更新本文、相关模块文档及行为包 README，避免版本号和上限再次漂移。
