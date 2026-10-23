# P2 建造引擎设计（以终为始）

> 目标：把「模型一条条下 `/fill`」换成「模型写一个建造程序 → 运行时编译/预览/提交/校验/撤销」。
> 本文是落地前的设计基线；括号里的 `[实测]` 是本机验证过的数字。

## 0. 为什么重构

现在的建造路径是：模型自己算坐标 → 逐条 `run_server_command("fill …")`。

| 问题 | 后果 |
|---|---|
| token 随**方块数**增长 | 一栋房子几十条 fill，每条都要模型复述坐标 |
| 无 diff | 已经是对的格子也重写；改了世界不知道 |
| 无事务 | 做错只能靠再 fill 一次"盖回去"（不可靠，原方块信息已丢） |
| 无校验 | 只能靠 `N blocks filled` 回执猜"改对了"，实际常出现漏格/错位 |
| 指令行长限制 | 一条 `fill` 超 32768 格要拆；`setblock` 逐格更慢 |
| 坐标/朝向漂移 | 模型在东/西/南/北之间反复推导，楼梯/门朝向常错 |
| 多格方块 | 门/床只写一半（本引擎 1.21.0.03 早于 1.26.10 的修复） |

## 1. 架构

```
LLM ──建造程序(受限 Python)──▶ Bot 编译器（Python，可信）
                                │ 1. 子进程沙箱执行程序 → ops(HIR，形状描述)
                                │ 2. 体素化：ops → desired volume（稀疏，KEEP 语义）
                                │ 3. 局部坐标(u,v,w) → 世界坐标（origin + facing）
                                │ 4. 编码：palette + 分层 RLE
                                ▼
                              Pack 执行器（@minecraft/server，在服务器内）
                                │ 5. preview：逐格 diff → place/replace/remove/noop
                                │ 6. commit：贪心合并单方块长方体 → fillBlocks(时间切片)
                                │ 7. verify：复读比对 → mismatch（空洞优先）
                                │ 8. undo：before 体积回写
                                ▼
                              世界
```

**关键分工**：体素化在 bot（纯几何，无世界依赖），diff + 执行在 pack（要读实时世界、要用 `fillBlocks`）。
模型只产出**形状意图**，世界写入权始终在运行时。

## 2. 工具面（4 个，创造/执行模式可见）

| 工具 | 作用 |
|---|---|
| `build_preview(program, origin, facing?, name?)` | 编译 + 预览，**不写世界**。返回 `operation_id`、bounds、体积、变更统计（place/replace/remove/noop）、执行计划（多少 `fillBlocks`）、警告（越界/未加载/保护方块/多格方块/未知 ID） |
| `build_commit(operation_id)` | 提交执行 + 自动 verify，返回 changed/skipped/耗时 + `mismatch`（空洞/放错）+ 样本坐标 |
| `build_undo(operation_id?)` | 用 before 体积还原，返回还原格数 |
| `build_status()` | 列出缓存的操作（id/名称/bounds/状态/体积） |

`build_preview` 与 `build_commit` 分开是刻意的（事务语义）：模型可以先看 diff 再决定写不写，
也可以"预览 → 改程序 → 再预览"迭代，而不产生任何世界修改。

## 3. 建造程序（受限 Python）

模型写的是**函数体**，作用域里有 `api`：

```python
# 15×11 两层小屋，正面朝南；origin 是 (0,0,0) 处的世界坐标
W, D, H = 15, 11, 8

api.fill((-1, -1, -1), (W, -1, D), "stone_bricks")          # 地基（多铺一圈）
api.box((0, 0, 0), (W - 1, H - 1, D - 1), "oak_planks")     # 外墙
api.fill((1, 0, 1), (W - 2, H - 2, D - 2), "air")           # 掏空
api.fill((1, 0, 0), (3, 2, 0), "air")                       # 门洞（朝正面 w=0）
for u in range(0, W, 4):                                    # 木骨架
    api.box((u, 0, 0), (u, H - 1, 0), "spruce_log")
    api.box((u, 0, D - 1), (u, H - 1, D - 1), "spruce_log")
api.box((0, H, -1), (W - 1, H, D), "dark_oak_planks", hollow=True)  # 平顶带檐
```

### API 清单（P2.1）

| 方法 | 说明 |
|---|---|
| `api.set(u, v, w, block, states=None)` | 单格 |
| `api.fill(a, b, block)` | 实心长方体（a/b 为局部坐标，顺序任意） |
| `api.box(a, b, block, hollow=False)` | 空心盒（6 面，可带厚度） |
| `api.walls(a, b, block, thickness=1)` | 四面墙（无顶底） |
| `api.frame(a, b, block, step=4, thickness=1)` | 立柱骨架 |
| `api.line(a, b, block)` | 三维线（Bresenham） |
| `api.plane(a, b, block, axis="v")` | 单层平面 |
| `api.cylinder(center, radius, height, block, axis="v", hollow=False)` | 圆柱/筒 |
| `api.sphere(center, radius, block, hollow=False)` | 球/壳 |
| `api.pyramid(base_a, base_b, height, block, hollow=True)` | 四棱锥（屋顶/塔尖） |
| `api.pattern(a, b, blocks, axis="v")` | 按 `(u+v+w) % len(blocks)` 铺纹理，避免大面积单色 |
| `api.dir("front"\|"back"\|"left"\|"right")` | 局部方向 → 世界方向名（喂给楼梯/门的 `states`） |
| `api.origin` / `api.facing` | 只读上下文 |

语言子集：普通 `for/if/函数定义/算术`，`math` 的 `sin/cos/sqrt/floor/pi`，`range`。
**没有** `import`、文件、网络、`exec/eval/open`、dunder 属性。

### 沙箱

- AST 白名单：拒绝 `Import/ImportFrom/With/Try/Class/Global/Nonlocal/Yield/Await`；
  拒绝任何 `__x__` 属性名；拒绝 `exec/eval/compile/open/input/getattr/setattr/globals/locals/vars/__import__`。
- 执行在**独立子进程**（`python3 -I -S`），`RLIMIT_AS=256MB`、`RLIMIT_CPU=5`、墙钟 8s。
- 程序 ≤ 16KB；产出 ops ≤ 20000；体素 ≤ 65536；palette ≤ 64。

## 4. 坐标与朝向

`origin`：局部 `(0,0,0)` 对应的世界坐标（整数）。
`facing`：建筑正面朝向 `north(-z)/south(+z)/east(+x)/west(-x)`，默认取玩家朝向。

| facing | 世界 x | 世界 z |
|---|---|---|
| south | `ox + u` | `oz + w` |
| north | `ox - u` | `oz - w` |
| east | `ox + w` | `oz - u` |
| west | `ox - w` | `oz + u` |

`v` 始终是 `oy + v`。方向性方块的状态**不自动旋转**（旋转状态名是坑），
而是给 `api.dir()` 让模型显式取世界方向。

## 5. 编码与上行分帧

- 体素表：`dict[(x,y,z)] -> palette_idx`；`palette[0]` 固定为 **KEEP**（不写、不删）。
  未出现过的格子 = KEEP，所以「没提到」≠「空气」，清空必须显式 `fill(..., "air")`。
- 编码：`{"o":[ox,oy,oz],"s":[sx,sy,sz],"p":[...],"rle":"0:5a,1:2,…"}`
  按 **y 层 → z 行 → x** 行优先，`paletteIdx:count` 都用 base36，逗号分隔。
- 上行：**必须分帧**。`[实测]` 单条 `scriptevent` 消息体 ≤700 字符可用，750 整条被丢弃
  （全行约 768 字节上限）。所以：

```
scriptevent viktor:build put <jid> <i>/<n> <片段>     # 每帧 ≤600 字符, 每批 ≤8 帧一次 stuff
scriptevent viktor:build preview <jid>
scriptevent viktor:build commit <jid>
scriptevent viktor:build undo <jid>
scriptevent viktor:build drop <jid>
```

- 下行沿用 v3 分帧（`[VIKTOR-BUILD] <jid> #i/n …` + `DONE`），新增 kind `BUILD`。
- 进度行用独立 tag `[VIKTOR-BPROG]`（不进总线，避免和回包混帧）。

## 6. Pack 执行器

### preview
逐格读（`system.runJob`，512 格/tick）→ 分类：
`place`（当前空气）/ `replace`（当前非空气且不同）/ `noop`（已相同）/ `unloaded`；
命中保护方块 → `protected` 计数 + 样本；多格方块 → `unsupported`。
同时算出贪心分解后的 `fillBlocks` 调用数（不执行）。

### commit
1. **差异预处理**：逐格复读，已经正确的格子标 KEEP（**幂等**：重复提交不再写），
   未加载的格子也不写；同时把"将被覆盖的当前方块"记成 before 体积（撤销只还原真正改动的格子）。
2. 未加载比例过高时提示先 `pin_region`（当前实现：跳过并回报 `skippedUnloaded`）。
3. 贪心分解：逐 y 层做 2D 最大矩形合并（只合并同一 palette 且非 KEEP 的格子）→
   `(box, paletteIdx)` 列表；每个 box 调 `dim.fillBlocks(volume, perm)`。
4. 时间切片 + abort 检查点：每批 box 后 `yield`，可被"强制停止"打断。
5. verify：复读 bounds 与 desired 比对 → `mismatch / holes / wrong` + 样本（**空洞优先**）。
6. 回包：`{ok, changed, skipped, ms, verify:{…}}`。

### undo
用 before 体积走同一个执行器写回；`before` 里 KEEP 的格子不动。

## 7. 事务与撤销

- 操作记录：`id / name / bounds / palette / desired RLE / before RLE / diff / result / verify`。
- 撤销栈：pack 内保留**最近 2 个**操作（内存上限约 2×65536 格 RLE）。
- `reload` 会清空暂存与撤销栈 → 报"操作已失效，请重新预览"（不静默）。
- 建议按模块提交（地基 → 墙 → 屋顶 → 室内 → 细节），单模块失败只回滚该模块。

## 8. 完成判定（postcondition）

**唯一依据是 verify 结果**，不是命令回执：

- `mismatch == 0` 才能对玩家说完成；
- 否则按 `holes`（该有方块却是空气）与 `wrong`（放错）的样本坐标，写一个**补丁程序**再 preview/commit；
- 未加载导致的 `unloaded` 必须如实说明"这部分没验证"。

P2.2 追加机器校验：悬空方块、越界、保护方块未被动、给定对称轴的对称性。

## 9. 安全

| 项 | 规则 |
|---|---|
| 体积 | ≤ 65536 格/操作（如 32×32×64） |
| 坐标 | 主世界 y ∈ [-64, 320]，越界直接拒绝（不静默裁剪） |
| 方块 ID | 用 `data/items.json` 校验；未知 ID 在 preview 报错并提示 `find_items` |
| 保护方块 | `bedrock/barrier/command_block/structure_block/jigsaw/light_block` 拒绝覆盖 |
| 容器/告示牌/刷怪笼 | 默认跳过并报告；`allow_overwrite_containers=true` 才覆盖 |
| 未加载 | preview 报告比例，>5% 拒绝 commit（提示先 `pin_region`） |
| 权限 | 仅 `creative / creative_max / execute` 模式可见可用（与 `pin_region` 同族） |
| 中断 | `停止/强制停止` 在批次间生效；中断后返回"已写入 N 格，可 undo" |

## 10. 分阶段

- **P2.1 内核**：编译器 + 沙箱 + 体素化/RLE + 上行分帧 + pack preview/commit（`fillBlocks` + 贪心合并）+ verify。
  工具：`build_preview` / `build_commit`。
- **P2.2 事务**：undo + before 体积 + 保护策略 + 悬空/对称校验 + 中断可恢复 + 进度回报。
- **P2.3 表达力**：程序内只读快照（`api.height/api.block`）、标准库糖（roof/arch/stairs）、
  `ops` JSON 直通（简单场景不写代码）、建造上下文 anchors。

## 11. 落地状态（P2.1 已完成）

已实现并实测：

| 项 | 结果 |
|---|---|
| 编译器 + 沙箱 | `viktor/build.py`：AST 白名单 + 子进程（`-I -S`、256MB、5s CPU、8s 墙钟）；import/open/dunder/exec/死循环全部拦住 |
| 体素化 + 编码 | 9 个形状 → 531 格 → 1.0KB / 2 帧；包围盒与 palette 与预期一致 |
| 上行分帧 | 每帧 ≤560 字符、一帧一次 `stuff`；`[实测]` 12 帧连发全部到达且保序 |
| preview | 531 格 / 26 个批量填充 / 1.0s；差异 `新放置 385 / 已正确 146` |
| commit | 531 格 / 26 批 / **89ms** / `verify.mismatch 0` |
| undo | 还原 531 格 / 9 批 / 72ms；撤销后复扫 990 格全为空气（无残留） |
| 模式门禁 | 只有 `creative` / `creative_max` 可见；normal/plan/execute/oneshot 连工具名都看不到 |

### P2.2 已落地部分

- **对称校验**（bot 侧，纯期望体积，不读世界）：`build_preview(..., symmetry="u"|"w"|"u:0")`
  → 镜像比对位置与方块类型，回 `mismatch` 与坐标样本。写世界前就能抓出设计错误。
- **悬空校验**（bot 侧，用 `scan` 快照 + 期望体积）：写入方块的下方与四邻都没支撑 → 报坐标；
  没有快照时明确说"没检查"，不假装通过。快照外一律视为"可能被支撑"，避免误报。

### P2.2 已落地部分（进度回报）

大工程的耗时其实在"差异核对"和"校验"两个逐格循环里, 所以进度按阶段上报:
`[VIKTOR-BPROG] <jid> <d|w|v> <done>/<total>`（d=核对现场 w=写入 v=校验），
每 1.2 秒最多一条；bot 侧只在"当前正在提交的这个操作"上转发到聊天，并再节流一次
（`build_progress` / `build_progress_min_sec`）。实测 10800 格地台提交 2.4s，
期间如实播报"核对现场 / 校验结果"。

### P2.3 已落地部分（标准库糖）

| 糖 | 作用 |
|---|---|
| `api.roof(a, b, block, style="gable"\|"hip"\|"flat", ridge="u"\|"w", height, hollow)` | 屋顶逐层内缩；`hollow=True` 只铺每层外圈（省料、留阁楼空间） |
| `api.stair(a, b, block, axis, rise=1, run=1)` | 直跑楼梯：每 run 格升 rise 格 |

两者都只产出普通 `fill` 形状，所以仍然走同一套体素化/差异/校验。
实测：9×7 小屋 + 带出檐人字屋顶 + 室外台阶 = 28 个形状 → 33 个批量填充，
对称检查 564 格全对称。


- **程序内读世界**：`build_preview(..., scan=[x1,y1,z1,x2,y2,z2])` 先预取稠密快照
  （`viktor:snapshot`，palette+RLE，≤65536 格），沙箱里提供 `api.height(u,w)` /
  `api.block(u,v,w)` / `api.solid` / `api.air`。快照是预览开始时的**只读副本**，
  程序看不到自己刚放的方块（要看效果就分模块）。
- 未加载格在快照里编码为索引 0 的 `?`：`api.air` 视为空气、`height` 跳过它继续往下找，
  预览会提示"快照里有 N 格未加载, 这些列的 api.height 不可靠"。
- 实测：48 个柱状形状（每列按地面高度垫墙）→ 合并成 4 个批量填充，2.0s（含快照往返）。

## 11.5 P3 视觉反馈（已落地第一层）

模型看不到截图，所以"比例/体块/屋顶收口"改用**字符图**：

- `render_build(operation_id, views=["front","top","iso"])`：渲染编译好的建造计划，
  不读世界、不写世界。视角 front/back/left/right/top/iso，超宽超高自动整数倍降采样。
- `render_region(x1..z2, views)`：先取稠密快照（`viktor:snapshot`）再渲染，看已建建筑。
- 同时导出 PNG（标准库 zlib+struct 手写，无第三方依赖）到 `logs/renders/`；
  按方块族着色的调色板，同一方块永远同色。
- 等距视图用画家算法（按 `x+z` 从远到近覆盖），能看出屋顶形态与体块关系。

### P3 第二层（已落地）：游戏内蓝图墙

`build_blueprint(operation_id, view, at, direction, step?)`：
把某个视角的渲染结果换成**彩色混凝土马赛克**（1 像素 1 格），按 `at`（墙面左下角）+
`direction` 铺成 1 格厚的墙面。

- 配色: 浅灰=石 / 棕=木 / 绿=植物 / 蓝=水 / 淡蓝=玻璃 / 黄=光·金 / 红=火 / 橙=砖 /
  白=雪·石英 / 品红=羊毛 / 灰=其他；空气铺白色背景
- **走同一套事务**：先生成预览（返回 operation_id），`build_commit` 才真正写入，
  `build_undo` 可撤——不引入新的世界写入路径
- `step>1` 降采样，墙更小；最大 96×96 像素

实测: 13×12 像素小屋立面 → 156 格 / 11 批 / 93ms / 校验 0，配色正确
（浅灰底座、淡蓝玻璃、棕木墙），撤销后复原。

## 12. 待实测 / 待定

1. `/setblock` 在 1.21.0.03 放门/床是否也是半块？（决定是否放行"命令回退"）
2. `fillBlocks` 单次调用的体积上限与跨区块行为（决定贪心 box 上限与 `pin_region` 必要性）。
3. 上行分帧的批大小与可靠性：是否需要序号校验 + 重传（丢帧检测）。
4. 预览与提交之间世界被玩家改动：MVP 靠"commit 时重新 diff，只写差异"天然容忍；
   但 undo 的 before 可能过时 → 记录并在 undo 回包里提示。
5. 表达方式：Python 程序（表达力强、token 省）vs JSON ops（更好校验、但无循环）。
   倾向 Python + 严格沙箱（BuilderGPT 与 Build Harness v2 都验证过这条路）。
