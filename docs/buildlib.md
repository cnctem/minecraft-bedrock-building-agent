# 建筑函数库（`api.lib` / `viktor/buildlib/`）

把 Java 建筑模组里的几何库**按算法移植**到 bot 的建造引擎上：模型不再手写几百行循环去逼近
一个中式屋顶或十字拱，而是写 `api.lib.chinese_roof(...)`。

- 实现：`viktor/buildlib/{core,shapes,chinese,structures,regional,gardens,decor,creations}.py`
- 元数据（唯一来源）：`viktor/buildlib/registry.py` → `CATEGORIES` / `SPEC`
- 注入：`viktor/build.py` 把 `LIB_SOURCE` 随 payload 经 stdin 送进沙箱子进程，在用户程序 `exec`
  之前构造 `api.lib`
- 文档：`python3 tools/gen_buildlib_docs.py` → `skills/*/references/functions-*.md`
- 自测：`python3 bot.py --test` 内的「建筑函数库分类自测 / 函数库 help/别名自测」

## 1. 为什么不做成“第二套 DSL”

原模组里有一套 `BuildCodeInterpreter`（自研 DSL + 函数注册表）。本项目的建造引擎已经是
**受限 Python**，能力更强且已有沙箱、限额、preview/commit/undo、渲染与校验。所以只移植
**几何算法**，把 `BuildCodeInterpreter` 当作“哪些函数、参数怎么排、默认值是什么”的参考：

| 原实现 | 这里 |
|---|---|
| `BuildCodeInterpreter` DSL + 内置函数（sphere/cylinder/polygon…） | `api.*` 基础原语（已有）+ `api.lib` 高层函数 |
| `ShapeFunctions` / `SurfaceShapes` / `StructureShapes` | `shapes.py` + `structures.py` |
| `AncientShapes` / `VaultShapes` | `chinese.py` + `structures.py` |
| `RegionalShapes` | `regional.py` |
| `GardenShapes` / `MonumentFunctions` | `gardens.py` + `creations.py`（纪念性） |
| `HouseDecor` / `DecorationFunctions` | `decor.py` |
| `DomainGenerators` / `GenNoise` | `creations.py`（确定性 hash 噪声，不用 Python `random`） |
| `MegaStyles` | `creations.py` 的整栋模板（参数化，可分段提交） |
| `ShapeGuide`（35KB 提示词） | 拆成 `skills/*/references/functions-*.md`，按技能按需载入 |

## 2. 移植时统一改写的语义

1. **坐标**：Java 的绝对 `x/y/z` → 局部 `(u, v, w)`，世界坐标由 `origin` + `facing` 变换，
   四朝向自动旋转（`facing="front"` 跟着建造朝向走）。
2. **方块 ID**：Java 名 → 基岩版 ID（`stone_bricks`→`stonebrick`、`bricks`→`brick_block`、
   `dandelion`→`yellow_flower`…）。别名表在 `core._LibBase._ALIAS`，**一次维护，两处生效**
   （沙箱预置代码 + 宿主侧），`api.fill` 这类原语也同样受益。
3. **状态**：需要状态的变体（`cracked/mossy/chiseled`、`coarse_dirt`、`quartz chisel_type`…）
   由别名表直接带出 states，模型不必记基岩版状态名。
4. **随机**：不用 `random`，全部走 `hash_mix/hash2/hash3/fbm2`（与原模组同一套整数散列），
   同坐标同 `seed` 永远同结果，可分块施工、可重跑。
5. **错误**：原实现里“参数不合法就返回 0、方块凭空消失”的做法**一律改成抛错**，并附接口签名：

   ```
   baroque_portico: 面宽至少为 columns*2；当前 8，需要 10
   接口: baroque_portico(u1, w1, u2, w2, base_v, columns, height, facing, stone, trim=None)
   ```

6. **破坏性写入显式化**：`moon_gate` / `brick_gatehouse` / `yaodong` / `stone_foundation` 会写 `air`；
   `water_basin` / `round_basin` / `cascade` / `zigzag_bridge(water)` 会写水。文档里逐条标注。
7. **限额**：库只产出普通 ops，仍受 `MAX_VOLUME/MAX_CELLS/MAX_OPS/MAX_PALETTE` 约束；
   超限报错会建议按模块拆分（底座/墙身/屋顶），不放大全局限额。

## 3. 与技能书的分工

函数库解决“构件形状对不齐”，技能书解决“该建什么、比例多少、先做什么”：

| 技能 | 负责 | 对应函数目录 |
|---|---|---|
| `mc-architecture` | 体块/比例/模数、结构选型、风格与地域路由、组合顺序 | `functions-chinese/vault/western.md` + `functions-index.md` |
| `mc-build` | 建造程序怎么写、KEEP/限额/自检、基础几何 | `functions-geometry.md` |
| `mc-interior` | 分区、动线、配色、成套家具 | `functions-interior.md` |
| `mc-details` | 做旧、绿化、园林密度 | `functions-garden.md` |
| `mc-terrain` | 自然感五律、地形分层、水与道路 | `functions-generators.md` |
| `mc-lighting` | 光级/刷怪门槛/隐藏光源 | 用 `lantern_ceiling` 等埋灯 |
| `mc-verify` | 验收阶梯、补丁流程 | 函数库编译期自检也并入这一章 |

## 4. 新增 / 修改函数的流程

1. 在对应实现文件里加方法（只 `self.put/fill/box/line`，不要碰世界、不要 `import`）。
2. 在 `registry.CATEGORIES` 里登记类别，在 `registry.SPEC` 里写一行签名 + 一句话说明。
   `missing_from_spec()` 会校验两边一致（自测里跑）。
3. `python3 tools/gen_buildlib_docs.py` 重生成技能文档（`--check` 查漂移）。
4. `cd ~/repo/mc-ai-bot && python3 bot.py --test`。
5. 需要视觉确认时用 `build_preview` + `render_build(views=["front","top","iso"])` 看字符图/PNG。

## 5. 已知取舍

- 只移植“有明确几何价值”的函数；原模组的任务调度、NPC 行为、图片体素化（`ImageDepthExtruder`、
  `ReferenceImageVoxelizer`）等与建造几何无关的部分不在范围内。
- `MegaStyles` 的整栋模板改成**参数化 + 可分段**：整栋一次性提交容易顶到体积上限，
  文档里建议按「地基/墙身/屋顶/内饰」分四次 preview/commit。
- 原 `ShapeGuide` 里个别组合建议彼此矛盾（例如屋顶后是否还要叠飞檐/瓦垄）。本库以**实际实现 +
  渲染验证**为准，文档由 `registry.SPEC` 生成，避免“说明书和代码两套说法”。

## 6. 来源与授权注意

- 算法参考自反编译得到的 Java 类（`ShapeFunctions`、`AncientShapes`、`GardenShapes`、
  `RegionalShapes`、`VaultShapes`、`StructureShapes`、`SurfaceShapes`、`MonumentFunctions`、
  `HouseDecor`、`DecorationFunctions`、`DomainGenerators`、`MegaStyles`、`BuildCodeInterpreter`、
  `ShapeGuide`）。反编译产物本身**没有进仓库**，这里只有按基岩版语义重写的 Python 实现。
- 若要对外分发本仓库，先确认原模组的许可证是否允许衍生/再分发；只在私人服务器自用则不受影响。
- 原模组的数值、比例建议（屋顶高度系数、柱高比、开窗节奏等）被整理进技能书，属于“经验参数”，
  实际以渲染/实机效果为准。
\n