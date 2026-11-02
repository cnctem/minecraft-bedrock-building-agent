# 技能书目录（与 Java 模组 `tasks/*.class` 的对应关系）

这些技能书有两层来源，**理论部分一律以原模组类里的内嵌指导文本为准**（比手写更完整、
且与函数签名一一对应），手写部分只补“本项目工具链怎么落地”。

## 1. 类 → 文档对照

| 原类 | 落到哪 | 生成方式 |
|---|---|---|
| `ShapeGuide`（35KB） | `mc-architecture/references/shape-guide-chinese.md`、`shape-guide-garden-western.md`、`shape-guide-advanced.md` | `tools/gen_skill_guides.py`（按章切分） |
| `BuildCategoryGuide` | `mc-architecture/references/category-guide.md`（九类设计标准 + 中式强覆盖） | 手工整理自类文本 |
| `MegaBuildGuide` | `mc-build/references/mega-build-guide.md` | `tools/gen_skill_guides.py`（整篇） |
| `DomainGenerators.GUIDE` | `mc-terrain/references/domain-generators.md` | `tools/gen_skill_guides.py`（整篇） |
| `BuildingPlanner` / `SiteAnalysis` | `mc-plan/references/site-analysis.md` | 手工整理自类文本 |
| `BuildScale` | `mc-plan/references/scale-tiers.md`（+ 整栋方块数表） | 手工整理自类文本 |
| `LayeredBuildGuide` | `mc-plan/references/blockout-layers.md`（适配成本项目做法） | 手工整理自类文本 |
| `ImageBuildGuide` | `mc-plan/references/reference-image.md`（适配成本项目做法） | 手工整理自类文本 |
| `BuildGeometryAudit` / `BuildStructureAudit` / `BuildFootprints` / `BuildQualityFeedback` | `mc-verify/references/audit-rules.md` | 手工整理自类文本 |
| `ShapeFunctions` / `AncientShapes` / `VaultShapes` / `StructureShapes` / `SurfaceShapes` / `RegionalShapes` / `GardenShapes` / `MonumentFunctions` / `HouseDecor` / `DecorationFunctions` / `MegaStyles` | `viktor/buildlib/*.py`（函数实现）+ 各技能的 `functions-*.md`（签名索引） | `tools/gen_buildlib_docs.py` |
| `BuildCodeInterpreter` | 不移植（本项目用受限 Python）；只参考它的函数注册表与错误口径 | — |

## 2. 维护规则

```bash
python3 tools/gen_skill_guides.py            # 重抽类里的指导文本
python3 tools/gen_skill_guides.py --check    # 查是否与类文件一致（需要 ~/repo/tasks）
python3 tools/gen_buildlib_docs.py           # 重生成函数签名索引
python3 tools/gen_buildlib_docs.py --check   # 查签名漂移（bot.py --test 里也会查）
```

- 改函数签名：先改 `viktor/buildlib/registry.py` 的 `SPEC`，再重跑 `gen_buildlib_docs.py`；
- 改教学口径：改原类（`tasks/`）再重跑 `gen_skill_guides.py`，**不要直接改生成出来的 md**；
- 手写文档（category-guide / audit-rules / mc-plan 四篇）需要人工同步原类改动。

## 3. 没有移植的函数 → 本项目用什么代替

原模组文档里会出现下列函数，本项目没有直接移植，按右列做法处理：

| 原函数 | 本项目做法 |
|---|---|
| `mirror(axis, …)` | 写参数化函数，左右各调一次（`def wing(du): …; wing(1); wing(-1)`）；或用 `build_preview(symmetry="u")` 验对称 |
| `rotate90` | 改 `facing` 重跑程序，或用循环换坐标轴 |
| `arrayLinear` / `arrayRadial` | `for` 循环 + 偏移（比内置阵列更可控） |
| `clone` | 重跑同一段程序（KEEP 语义不会破坏已建部分） |
| `replace` | 先铺满、再覆盖；需要挖空就显式 `api.fill(..., "air")` |
| `clear` | `api.fill(范围, "air")`（**必须显式**） |
| `pillarGrid` | `api.lib.hypostyle_hall(...)` 已覆盖柱网场景 |
| `<layers>` 分层体块图 | 见 `mc-plan/references/blockout-layers.md`（画网格 → 写程序） |
| `<slices>` 参考图 / 图像体素化 | 见 `mc-plan/references/reference-image.md`（看图 → 剪影 → 写程序） |
| 选项 `{key: value}` | 本项目写成关键字参数（`merlon="stonebrick"`），camelCase 键也识别 |

## 4. 技能清单

| 技能 | 定位 | 独有资料 |
|---|---|---|
| `mc-architecture` | 建筑设计与风格/流派（主） | shape-guide-* / category-guide / structure / facade / styles / detail / functions-* |
| `mc-build` | 建造引擎与写程序 | mega-build-guide / functions-geometry / circle-tables / dome / slopes / smooth-surfaces / spiral |
| `mc-plan` | 施工规划（场地/规模/体块/参考图） | site-analysis / scale-tiers / blockout-layers / reference-image |
| `mc-verify` | 体检与修复 | audit-rules |
| `mc-terrain` | 地形与景观 | domain-generators / landforms / vegetation / water-road / expert-rules / functions-generators |
| `mc-interior` | 室内与装饰 | furniture / rooms / palette-light / expert-rules / functions-interior |
| `mc-details` | 做旧与绿化 | aging / details / plants / landscape / pocket-parks / functions-garden |
| `mc-lighting` | 光照与夜景 | — |
| `mc-commands` | 指令与文本 | block-states / rawtext / examples |
