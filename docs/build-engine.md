# 建造引擎

本文描述**当前实现**，不再沿用早期 P2/P3 阶段设计或历史 benchmark。高层建筑函数见
[建筑函数库](buildlib.md)，模型侧完整使用方法见 [`skills/mc-build/SKILL.md`](../skills/mc-build/SKILL.md)。

## 1. 职责与数据流

建造引擎把“模型逐条下 `/fill`”变成“程序声明形状 → 预览差异 → 提交 → 复读校验 → 可撤销”：

```text
LLM：受限 Python 建造程序 + origin + facing
  │
  ▼
Bot（viktor/build.py）
  │ AST 白名单 + 隔离子进程
  │ api.* / api.lib.* → 形状 ops → 期望体素
  │ 局部坐标变换、方块 ID 校验、多格方块处理
  │ palette（0 = KEEP）+ 分层 RLE
  ▼
行为包（behavior_pack/viktor_bridge/scripts/main.js）
  │ preview：逐格读取世界并计算 diff
  │ commit：重新 diff → 贪心合并 → fillBlocks
  │ verify：复读期望体积，报告 holes / wrong / unloaded
  │ undo：用提交前保存的 before 体积回写
  ▼
Minecraft 世界
```

关键边界：**Bot 只负责纯几何编译，世界读写只发生在行为包**。模型只声明期望结果，不能从沙箱直接访问世界、
文件或网络。

主要实现：

| 文件 | 职责 |
|---|---|
| `viktor/build.py` | AST 校验、沙箱、基础 API、体素化、坐标变换、KEEP/RLE 编码、对称与悬空检查 |
| `viktor/bot_build.py` | 工具编排、上行分帧、总线等待、结果格式化 |
| `viktor/render.py` | 字符图、PNG、游戏内蓝图墙 |
| `behavior_pack/viktor_bridge/scripts/main.js` | 世界快照、preview/commit/verify/undo、操作缓存、进度事件 |
| `viktor/buildlib/` | 可选的高层建筑函数库，最终仍只产生普通形状 ops |

## 2. 工具与模式门禁

| 工具 | 当前行为 |
|---|---|
| `build_preview(program, origin, facing?, name?, scan?, symmetry?)` | 编译并上传期望体积，与世界做 diff；**不写世界**。返回 `operation_id`、包围盒、差异、批量填充计划、检查结果与警告 |
| `build_commit(operation_id)` | 提交前重新读取世界，只写实际差异；随后自动 verify。返回 changed/noop/failed/aborted/skippedUnloaded 与校验样本 |
| `build_undo(operation_id?)` | 撤销指定操作；不传 id 时撤销最近一个可撤销操作 |
| `build_status()` | 列出上传中、待提交、已提交操作及撤销栈 |
| `render_build(operation_id, views?, scale?)` | 渲染 Bot 本地保存的编译结果；不读世界、不写世界 |
| `render_region(x1..z2, views?, scale?)` | 通过 `viktor:snapshot` 读取世界区域并渲染；只读 |
| `build_blueprint(operation_id, view, at, direction, step?)` | 把已有计划转成混凝土马赛克墙的**新预览**；仍须 `build_commit` 才写世界，可 `build_undo` |

权限以 `viktor/profiles.py` 为准：

- `creative`、`creative_max` 暴露完整的预览、提交、撤销、状态、渲染与蓝图工具。
- `normal` 的建造相关只读能力仅有 `render_region`；`render_region` 通过世界快照工作，不属于写入门禁。
- 一次性模式的白名单不包含上述建造/渲染工具。
- 除 schema 白名单外，执行层还会按当前模式再次拒绝禁用工具，防止经 `ptc` 夹带。

## 3. 标准工作流程

1. 用 `get_player_position`、`get_heightmap`、`inspect_region` 等确认基准点和现场。
2. 远处施工先用 `pin_region` 覆盖工作面，避免区块卸载。
3. `build_preview` 编译并检查 diff、警告、对称/悬空结果。
4. 较大体量先 `render_build(views=["front", "top", "iso"])` 检查比例和屋顶收口。
5. 修改程序则重新 preview；确认后 `build_commit`。
6. 以 verify 为验收依据。`mismatch == 0` 表示已参与校验的目标格全部匹配；
   若 `unloaded > 0`，仍有区域没有验证，必须如实说明，不能宣称整个范围都完成。
7. 有空洞或错块时，根据样本坐标写小补丁程序，再 preview/commit；需要回滚时用 `build_undo`。

推荐按“地基 → 墙身 → 屋顶 → 室内 → 细节”拆成多个操作。单次失败只影响一个模块，也更容易预览、修补和撤销。

## 4. 建造程序

模型传入的是受限 Python **语句块/函数体**，不是可自由导入模块的脚本。最小示例：

```python
W, D, H = 9, 7, 5
api.fill((-1, -1, -1), (W, -1, D), "stone_bricks")
api.box((0, 0, 0), (W - 1, H - 1, D - 1), "oak_planks")
api.fill((1, 0, 1), (W - 2, H - 2, D - 2), "air")
api.fill((3, 0, 0), (4, 2, 0), "air")
api.roof((-1, H, -1), (W, H, D), "dark_oak_planks", style="gable", ridge="u")
```

### 4.1 基础 API

所有形状坐标都是局部 `(u, v, w)`；`a`、`b` 是包含端点的两角坐标，顺序任意。

| API | 说明 |
|---|---|
| `api.set(u, v, w, block, states=None)` | 单格 |
| `api.fill(a, b, block, states=None)` | 实心长方体 |
| `api.box(a, b, block, hollow=False, states=None)` | 六面盒；`hollow=True` 去掉内部 |
| `api.walls(a, b, block, thickness=1, states=None)` | 四面墙，无顶底 |
| `api.frame(a, b, block, step=4, thickness=1, states=None)` | 外框立柱骨架 |
| `api.line(a, b, block, states=None)` | 三维 Bresenham 线 |
| `api.plane(a, b, block, axis="v", states=None)` | 取 `a` 所在单层平面 |
| `api.cylinder(center, radius, height, block, axis="v", hollow=False, states=None)` | 圆柱/圆筒，可沿 u/v/w |
| `api.sphere(center, radius, block, hollow=False, states=None)` | 球/球壳 |
| `api.pyramid(a, b, height, block, hollow=True, states=None)` | 逐层内缩四棱锥 |
| `api.roof(a, b, block, style="gable", ridge="u", height=None, hollow=False, states=None)` | 双坡、四坡或平顶；双坡屋脊沿 u/w |
| `api.stair(a, b, block, axis="w", rise=1, run=1, states=None)` | 直跑台阶形状，每 run 格升 rise 格 |
| `api.pattern(a, b, blocks, axis="v", states=None)` | 按指定局部坐标轴循环使用方块列表 |
| `api.dir(where="front")` | front/back/left/right 转为世界方向名 |
| `api.dirnum(where="front")` | 转为旧式 direction 整数：0=南、1=西、2=北、3=东 |
| `api.origin` / `api.facing` | 当前基准点与朝向 |

这些 API 只追加形状描述；后写的体素覆盖先写的体素。方块别名统一来自 `buildlib.BLOCK_ALIAS`，
ID 再按 `data/raw_ids.txt`（优先）或物品表校验。

### 4.2 KEEP 语义

- 程序没有提到的格子是 **KEEP**：不写，也不删。
- 挖空必须显式 `api.fill(..., "air")`。
- 已符合目标的格子在提交时改为 KEEP，因此重复提交是幂等的，不会无谓重写。

### 4.3 多格方块

当前编译器已处理常见多格方块，不再沿用“门/床/高草一律不支持”的旧设计：

- 门与双格植物：自动展开上下两格，并设置 `upper_block_bit`。
- 床：传入的一格是床头；床尾由引擎按 `direction` 放置，不要再手写第二格。
- 方向性方块不会被坐标旋转换算自动修正状态；使用 `api.dir()` / `api.dirnum()` 显式给出方向。

## 5. 坐标与朝向

`origin=[x,y,z]` 是局部 `(0,0,0)` 对应的世界坐标；局部 u 向右、v 向上、w 向建筑正面。

| `facing` | 世界 x | 世界 y | 世界 z |
|---|---|---|---|
| `south` | `ox + u` | `oy + v` | `oz + w` |
| `north` | `ox - u` | `oy + v` | `oz - w` |
| `east` | `ox + w` | `oy + v` | `oz - u` |
| `west` | `ox - w` | `oy + v` | `oz + u` |

## 6. 世界快照与编译期检查

### 6.1 `scan` 快照

`build_preview(..., scan=[u1,v1,w1,u2,v2,w2])` 会先按 origin/facing 换算世界范围，再调用
`scriptevent viktor:snapshot` 获取稠密 palette+RLE 快照。程序随后可用：

| API | 说明 |
|---|---|
| `api.block(u, v, w)` | 快照中的方块名；范围外或未知为 `?` |
| `api.air(u, v, w)` | 空气类方块或 `?` 返回 true |
| `api.solid(u, v, w)` | 非空气、非未知、非水/熔岩返回 true |
| `api.height(u, w)` | 快照范围内最高非空气方块的局部 v；空列返回 `None` |

快照是 preview 开始时的只读副本，不包含当前程序即将放置的方块。需要看本次建造结果时，应分模块预览。
快照含未加载格时，`api.height` 可能不可靠；结果会明确提示，不能当作完整现场。

### 6.2 对称与悬空

- `symmetry="u"` / `"w"` 使用包围盒中线；`"u:0"` / `"w:-2"` 指定局部对称轴。
  只比较位置与方块类型，不比较朝向和状态。
- 有 `scan` 时才做悬空检查：期望体积与快照合并后，下方和四邻都没有支撑的方块会被列出。
  快照外视为“可能被支撑”，避免误报；没有快照时明确标记为未检查。
- 这些检查是设计辅助，不替代提交后的 verify。

## 7. 沙箱与限额

| 项目 | 当前上限/行为 |
|---|---|
| 源码 | 16000 字节 |
| 形状 ops | 20000 |
| 包围盒 | 65536 格，且单轴不超过 512 |
| 实际写入体素 | 65536 格 |
| palette | 64 种（KEEP 不占用户 palette） |
| 沙箱进程 | `python3 -I -S`，内存 256 MiB，CPU/墙钟约 8 秒 |
| 语言限制 | AST 白名单；禁止 import、文件、网络、反射、下划线属性、exec/eval/open 等 |
| 程序输出 | `print(...)` 收集为 `[程序输出]`，最多保留 40 条，不直接写 stdout |

沙箱用于降低误操作和资源失控风险；世界安全仍由模式门禁、预览、运行时校验和操作者审查共同保证。

## 8. 传输与执行

### 8.1 编码与分帧

- 期望体积编码为 `o`（原点）、`s`（尺寸）、`p`（palette）、`rle`。
- RLE 顺序为 **y 层 → z 行 → x**，索引和计数使用 base36；索引 0 固定为 KEEP。
- 上行：`scriptevent viktor:build put <jid> <i>/<n> <片段>`，Bot 每帧 **560 字符**，
  并且**一帧一次 `screen stuff`**，规避控制台整包长度限制。
- 下行：`[VIKTOR-BUILD] r<id> #i/n ...` + `DONE`，由 `ServerBus` 重组；缺帧报错。
- 快照使用 `[VIKTOR-SNAP]`，进度使用独立的 `[VIKTOR-BPROG]`，不与查询回包混帧。

### 8.2 preview

行为包按每 tick 512 格让出主线程，统计：

- `place`：目标位置当前为空气；
- `replace`：当前非空气且与目标不同；
- `noop`：ID 与指定状态已匹配；
- `unloaded`：区块未加载；
- `protectedN` / `unsupported`：诊断计数和样本；
- `plan.boxes`：按完整体积估算的批量填充数。

预览会报告保护方块诊断，但它不是完整的世界权限/领地保护系统；出现警告时应先调整设计，不要直接提交。

### 8.3 commit 与 verify

1. 提交时重新逐格读取世界：已正确的改为 KEEP，未加载的跳过，同时保存实际差异格的 before 状态。
2. 每个 y 层做同 palette 的二维矩形贪心合并，再把同位置连续层合并成长方体。
3. 优先调用 `fillBlocks`；API 不可用时有逐格 `setPermutation` 回退。失败批次计入 `failed`。
4. 每 8 批让出一次主线程，并检查 abort；停止可能留下部分写入，可用 undo 回滚。
5. 最后对原始期望体积复读：目标非空气却仍是空气计为 `holes`，其他不符计为 `wrong`，未加载单列。
6. 大范围进度按“核对现场 / 写入 / 校验”上报；Bot 再按 `build_progress_min_sec` 节流转发。

## 9. 操作生命周期与撤销

| 状态 | 当前规则 |
|---|---|
| 暂存操作 | 行为包最多保留 4 个，超出时淘汰最旧记录；暂存记录 TTL 为 10 分钟 |
| 撤销栈 | 最近 2 个有实际变更的操作；空提交不占槽位 |
| `reload` | 清空行为包内的暂存操作与撤销栈 |
| Bot 重启 | 本地渲染 payload 丢失；旧操作需重新 `build_preview` 才能 `render_build` |
| 撤销方式 | 用 before 体积回写真实改动格，而不是简单填空气 |

撤销只能恢复提交时记录的状态；如果玩家之后又在同区域施工，回滚可能覆盖这些后续修改，使用前应检查现场。

## 10. 渲染与蓝图

- 视角：`front` / `back` / `left` / `right` / `top` / `iso`。
- 字符图适合检查体块、立面、屋顶和楼层关系；超宽/超高会整数降采样。
- PNG 由标准库 `zlib` + `struct` 生成，输出到 `logs/renders/`。
- 等距视图按远近顺序覆盖，展示体块关系；精确逐格验收仍用 `get_slice` / `inspect_region` / verify。
- 蓝图墙把渲染像素映射为彩色混凝土，最大约 96×96；`step` 控制降采样。
  它复用同一 preview/commit/undo 路径，不是额外的直接写世界接口。

## 11. 修改与验证

```bash
python3 bot.py --test
node --check behavior_pack/viktor_bridge/scripts/main.js
```

修改编译器、payload 或行为包协议时，必须同步检查两端限额、编解码顺序、错误回包与自测。
修改工具签名时，同时更新 `viktor/schemas.py`、相关技能书和本文；不要恢复历史设计文档中已经删除的限制或权限描述。
