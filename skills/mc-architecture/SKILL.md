---
name: mc-architecture
description: 建筑设计手册 + 建筑函数库——**主依据是原建筑模组的 ShapeGuide/BuildCategoryGuide**(中式八大地域流派路由、官式殿宇与故宫三段比例、圆明园双語汇、曲面/拱顶、西洋立面、类别级设计标准与自检)，配套体块/比例/模数、承重体系、立面材质等速查，以及 api.lib 的 216 个函数(中式屋顶/斗拱/马头墙/土楼、十字拱/肋拱、柱式/门廊/卷涡、玫瑰窗/尖塔、城墙/剧场、假山/九曲桥)。玩家要求建房子/城堡/教堂/塔楼/别墅/神庙/宫殿/园林建筑，或说"外墙太素""屋顶不会做""看着不稳""像火柴盒""要气派/宏伟"时加载。
---

# 建筑设计手册(结构 / 立面 / 风格)

把"摆方块"升级成"造建筑"。执行顺序固定为 **判类别 → 定体块 → 结构 → 深度 → 配色 → 细节**。

## 0. 先判类别与流派（这一步决定后面全部）

原建筑模组在生成前先做**类别识别**与**中式流派路由**，因为不同类别/流派的标准互相冲突。
本项目照同一顺序：

1. **类别**：读玩家原话，落到 `references/category-guide.md` 的九类之一
   （民居/塔楼/城堡/地标/聚落/基础设施/遗迹/园林/通用），按该类别的
   【设计要求】+【输出前自检】执行；
2. **中式流派**：若涉及中式，先读 `references/shape-guide-chinese.md` 的「★★中式流派路由」，
   按关键词（江南/徽派/闽南/岭南/川蜀/西北/藏式/客家/官式）选全套语汇，
   **不要默认故宫**；
3. **风格语汇**：中式 → `shape-guide-chinese.md`；圆明园/西洋楼/园林 → `shape-guide-garden-western.md`；
   曲面/拱顶/现代结构 → `shape-guide-advanced.md`；
4. **构件函数**：以上文档里点名的函数都在 `api.lib` 里（camelCase 与 snake_case 都可用），
   签名索引见 `references/functions-index.md` / `functions-chinese|vault|western.md`。

**中式五条铁律**（摘自 ShapeGuide 与 BuildCategoryGuide，冲突时以此为准）：

1. 屋顶只用 `chineseRoof`，形制按等级：正殿「重檐庑殿」、城门楼「重檐歇山」、
   配殿「歇山」、亭/角楼「攒尖」；**禁止** dome / polygonDome / cone / gable 做中式屋顶。
2. 屋顶进深比墙身**每边外挑 2~4 格**；檐下加 `dougong`，台基用 `sumeruBase` + `railing`。
3. 比例：屋顶高 ≈ 进深 × 0.35~0.45 且 ≥ 柱高 × 0.8；台基高 ≈ 柱高 / 3 且 ≥ 3 格。
   屋顶比墙身矮 = 棚子。
4. 配色：黄琉璃**只属于皇宫**；民居用青瓦（deepslate_tiles）、红瓦（terracotta）或茅草。
5. `chineseRoof` 已自带四角起翘、瓦垄、檐口勾边与正脊，**不要再叠**
   `flyingEave` / `tileRidges` / `ridgeBeasts`。

```text
玩家原话 → 类别(category-guide) → 流派/风格(shape-guide-*) → 体块与比例 → api.lib 构件 → 程序
```

**参数写错会直接报错并附接口签名**；不确定就 `print(api.lib.help("roof"))`（输出以 `[程序输出]` 回来）。

## 0.5 函数库速查

| 要做的 | 直接调 | 看哪份文档 |
|---|---|---|
| 中式屋顶/斗拱/须弥座/月洞门/塔/牌坊/藻井 | `chineseRoof` `dougong` `sumeruBase` `moonGate` `pagoda` `paifang` `caissonCeiling` | `references/shape-guide-chinese.md` + `functions-chinese.md` |
| 地域民居(江南/徽派/闽南/岭南/川蜀/西北/藏式/客家) | `guanyinDou` `horseHeadWall` `swallowtailRidge` `huoerWall` `chuandouFrame` `yaodong` `tibetanFort` `tulou` | 同上 |
| 圆明园/西洋楼/水景/园林构筑 | `baroquePortico` `volute` `waterBasin` `cascade` `zigzagBridge` `stoneBoat` `rockery` | `references/shape-guide-garden-western.md` |
| 曲面/拱顶/网架/幕墙/斜交网格 | `hyperboloid` `hyperbolicParaboloid` `groinVault` `ribVault` `spaceFrame` `curtainWall` `diagrid` | `references/shape-guide-advanced.md` + `functions-vault.md` |
| 柱式/门廊/玫瑰窗/尖塔/城墙/剧场 | `classicalColumn` `baroquePortico` `roseWindow` `steeple` `keep` `rampart` `amphitheater` | `functions-western.md` |
| 圆/球/锥/拱/斜面等基础几何 | `cylinder` `sphere` `dome` `cone` `arch` `hipRoof` `gable` … | 技能 `mc-build` 的 `functions-geometry.md` |
| 家具/整间房 | `livingRoomSet` `bedroomSet` `kitchenCounter` `cottageInterior` … | 技能 `mc-interior` 的 `functions-interior.md` |
| 水池/假山/桥/游廊 | `waterBasin` `cascade` `rockery` `zigzagBridge` `coveredWalkway` | 技能 `mc-details` 的 `functions-garden.md` |
| 地形/植被/遗迹/道路/整栋模板 | `terrain` `vegetation` `ruins` `road` `medievalHouse` `chinesePavilion` … | 技能 `mc-terrain` 的 `functions-generators.md` |

最短的中式殿宇程序(体量、台基、屋顶一次到位):

```python
W, D = 15, 11                      # 面宽:进深 ≈ 4:3
api.lib.sumeruBase(-2, -2, W + 1, D + 1, 0, 3, "quartz_block")
api.fill((0, 0, 3), (W - 1, 7, D - 1), "red_terracotta")      # 墙身到檐口
api.fill((1, 3, 1), (W - 2, 6, D - 2), "air")
api.lib.dougong(0, 8, 0, 2, 2, "gold_block")                  # 每根柱顶各来一个
api.lib.chineseRoof(-4, -4, W + 3, D + 3, 8, 5, "歇山",
                    "yellow_glazed_terracotta", "deepslate_tiles")
```

## 0.7 施工顺序

1. **选址定向**：`get_player_position` 定朝向，`get_heightmap` 量落差，`get_slice` 看已有建筑；
   高差 >4 格或场地太窄先看技能 `mc-plan`（台基/台地/换地方）。
2. **体块草稿**：主块 + 次块 + 连接体，至少 2~3 个体块穿插、每处差 ≥2 格；
   关键 3~5 层平面先定轮廓（收分与外墙闭合），见 `mc-plan` 的分层体块法。
3. **定网格**：按 5/7/9 格模数排柱、窗、开间；大型工程按 16×16/32×32 分区。奇数宽优先。
4. **结构先行**：柱、梁、拱、桁架、承重墙先落地，再填墙。让力线可见。
5. **立面深度**：三段式 + 每 4~6 格一处 1 格凹凸；纯平墙最长不超过 7 格。
6. **材质与渐变**：主材 ≥70%，辅助 2~3 种；每 3~5 格分段，交界 2~3 格 dithering（`references/detail.md`）。
7. **屋顶与第五立面**：坡屋顶高度约占建筑总高 1/3~1/2；出檐 1~2 格（日式 2~3）；
   屋顶要有屋脊、老虎窗、烟囱或端头装饰。中式屋顶一律用 `chineseRoof`（见 shape-guide-chinese）。
8. **落地**：`pin_region` 覆盖工地 → 写程序（`api.lib` 构件 + `fill` 体块）→
   `build_preview` → `render_build` 看比例 → `build_commit` → 按 `mc-verify` 验收（mismatch=0）。

> **自主默认**：玩家只说"建个房子"→ 沿用附近群系/建筑材质；尺寸默认 9×7、层高 4、木石组合、人字坡屋顶。先给轮廓，再深化。

## 1. 比例硬指标

| 项 | 推荐值 |
|---|---|
| 奇数原则 | 门面/窗组/塔宽优先 3/5/7/9 格 |
| 小屋 / 民居 | 7×9~9×11；标准民居 11×9 起；宅邸 15×21 起 |
| 正面宽 : 侧深 | 3:2~5:4；别做无细节的大方盒 |
| 层高 | 净高 3~4；宏大 5~6；教堂中殿 8+；2 格必压抑 |
| 多层视觉高度 | 底层:中层:顶层 ≈ 5:4:3；逐层收分每边 1 格 |
| 塔楼 | 宽/径 ≥5；高宽比 ≤5:1；主塔 11×11~13×13，高 ≈ 宽×1.5~2 |
| 悬挑 | 无支撑 ≤3 格；超过加柱、斜撑或托座 |
| 门脸 | 民居宽 1~2、公共建筑 3~5；门高 2~3，门上必有过梁/尖拱 |
| 台基 / 出檐 | 台基外扩 1、高 1~2；出檐 1~2，下面有椽/托 |
| 坡屋顶 | 屋顶高 ≥ 墙高 ×0.5；满砖 45°、楼梯视觉约 63°、半砖交替约 22.5° |

## 2. 结构选型

| 类型 | 体系 | 可见做法 |
|---|---|---|
| 民居/木屋 | 木构架 + 填充墙 | 外露角柱、横梁、45° 斜撑，间距 4~5 格 |
| 城堡/要塞 | 承重厚墙 + 扶壁 + 塔楼 | 收分、垛口、箭窗、转角石 |
| 教堂/哥特 | 尖券 + 束柱 + 肋拱 + 飞扶壁 | 窄高窗 1~2×5~7，竖向壁柱每 2~3 格 |
| 古典神庙 | 梁柱柱式 + 山花 | 柱高≈柱径 7~10 倍，台基、额枋、山花完整 |
| 拜占庭/东正 | 帆拱 + 中央穹顶 | 方基座四角层层托出，再起穹顶/鼓座 |
| 中式殿堂 | 木构 + 斗拱 + 大坡顶 | 台基、柱网、斗拱外挑 2~4 层、歇山/庑殿 |
| 现代别墅 | 框架 + 幕墙 + 悬挑 + 平顶 | 2~3 个错位盒体，通长玻璃 ≥5 格 |
| 工业/仓库 | 桁架 + 砖墙 + 钢窗 | 三角桁架、红砖、铁栏格窗、露管 |
| 塔楼/灯塔 | 筒体 + 收分 + 挑檐 | 每 5~7 层收 2~3 格，避免蜡烛形 |

各体系的 MC 搭法与跨度见 `references/structure.md`。总原则：**柱落地、梁搭柱、拱有起拱、挑有托、墙有厚度借口。**

## 3. 立面与深度(外墙不素)

- **三层墙**：主体填充层 + 内凹 1 格层 + 外凸 1 格层。凸出用角柱、门窗套、横梁、窗台；内凹用窗洞、门廊、壁龛。
- **三段式**：基座:墙身:檐口 ≈ 1 : 3~5 : 0.5~1；颜色按深→中→浅或反向分层。
- **开窗**：同层齐顶、等距、成组；民居 1×2/2×2 内凹 1 格，哥特窗宽 1~2、高 5~7，现代条窗 ≥5 格。
- **转角**：必须用深色 log 包角、错缝转角石或凸柱，别让两面墙裸着相交。
- **节奏**：每 4~6 格至少一处开口、柱位或凹凸；中世纪可不对称，公共建筑严格对称。
- **背面也是立面**：四面都有窗、结构线或材质变化，禁止"No back of building"。
- 门窗、栏杆、线脚、老虎窗、烟囱详见 `references/facade.md`。

## 4. 材质、渐变与做旧

- **调色板容量**：主色 1 + 辅助 2~3，总数 ≤4。主材 ≥70%，辅助 15%~30%。
- **竖向渐变**：上浅下深，每 3~5 格一档；基座 2 层强制用最暗/最糙变体。
- **抖动过渡**：两色交界用 2~3 格棋盘混铺，比例 50:50 → 70:30 → 100:0。
- **石系链**：`stone` → `andesite` → `tuff` → `cobblestone` → `mossy_cobblestone` → `stonebrick` → `stonebrick["stone_brick_type"="cracked"]` → `deepslate` → `cobbled_deepslate` → `blackstone`。
- **暖木链**：`oak_planks` → `spruce_planks` → `stripped_spruce_log` → `dark_oak_planks` → `dark_oak_log`。
- **做旧上限**：cracked/mossy ≤10%~20%；藤蔓每 3~5 格 1 处、延伸 2~4 格，成簇不成撒胡椒面。
- 深度、渐变、生活化细节与大佬工作流速查见 **`references/detail.md`**。

## 5. 风格速查（细节一律以类源文档为准）

| 玩家说的 | 去哪份文档 | 关键语汇 |
|---|---|---|
| 中式（任何细分） | `shape-guide-chinese.md` | **先走流派路由**：江南观音兜/徽派马头墙/闽南燕尾脊/岭南镬耳/川蜀穿斗/窑洞/碉房/土楼/官式斗拱须弥座；黄琉璃只属于皇宫 |
| 故宫/紫禁城/宫殿/大殿 | `shape-guide-chinese.md` 的「故宫式宫殿套路」 | 三段比例 台基 H/3 · 墙身 H · 屋顶 0.8~1.2H；重檐庑殿 + 朱红 + 汉白玉；院落有配殿廊庑 |
| 圆明园/西洋楼/大水法/石舫/九曲桥 | `shape-guide-garden-western.md` | 两种语汇拼在一座园：中式木构曲面屋 + 西洋汉白玉柱式山花；水法必须用 cascade 逐层跌 |
| 哥特/教堂 | `shape-guide-advanced.md` + `functions-western.md` | 尖券 + 束柱 + 肋拱（`ribVault`）+ 飞扶壁（`flyingButtress`）+ 玫瑰窗 |
| 现代/高层 | `shape-guide-advanced.md` | 核心筒 → `curtainWall` 幕墙 → `diagrid` 造型 → `spaceFrame`/双曲屋面 → `stairTower` |
| 中世纪/都铎/北欧/沙漠/奇幻 | 技能 `mc-build` 的 `references/mega-build-guide.md`【四】预制风格库 | 半木框架、陡坡顶、白墙深木、石基；整栋模板自带装饰 |
| 蒸汽朋克/奇幻 | `references/styles.md` + `references/detail.md` | 铜的四阶段氧化、管道齿轮、有机曲线与藤蔓 |

补充：`references/styles.md`（各风格完整结构/材质/起手）、`references/detail.md`（深度与渐变配方）、
`references/structure.md`（承重体系的 MC 搭法）、`references/facade.md`（门窗栏杆线脚）。

## 6. 建材与工具落地

| 用途 | 常用方块(Bedrock ID 先 `find_items` 确认) |
|---|---|
| 重石/基座 | `stonebrick`、`cobblestone`、`smooth_stone`、`deepslate`、`polished_deepslate` |
| 高级石材 | `quartz_block`、`calcite`、`diorite`、`andesite`、`tuff_bricks` |
| 木构/墙板 | `*_planks`、`*_log`、`stripped_*_log`、`*_stairs`、`*_slab`、`*_trapdoor` |
| 现代/工业 | `*_concrete`、`glass_pane`、`copper_block`、`copper_grate`、`iron_bars`、`chain` |

落地顺序(与 `mc-build` 的 preview/commit 一致):

1. `get_heightmap` / `get_slice` / `inspect_region` 读现场, `pin_region` 覆盖工地;
2. 写**一个模块一段程序**: 台基 → 墙身/柱网 → 屋顶 → 门窗/线脚 → 细节;
3. 每段 `build_preview` → `render_build(views=["front", "iso"])` 看比例 → `build_commit`;
4. 结构/屋顶/柱式这类曲线件直接调 `api.lib`(见 §0.5), 不要用 `fill` 循环拼斜屋面;
5. 完工按 `mc-verify` 复检: `verify.mismatch == 0` 才算完成。

> 函数库只负责“构件形状正确”, **比例与组合仍然是这一章的事**:
> 屋顶该多高、出檐该多深、院落该几进——先按 §1~§5 定, 再交给函数执行。


## 7. 坑清单

- 先抠细节 → 体块与比例救不回来。**永远先轮廓**。
- 全楼同材质、玻璃贴平、纯平墙 >7 格 → 盒子病；用 3 层深度 + 渐变 + 线脚。
- 柱不落地、梁不搭柱、悬挑无托 → 视觉不稳。
- 屋顶 < 墙高 1/3、无出檐、无屋脊 → 像盒子扣盖。
- 地形落差 >2 格不处理 → 建筑没扎根；补台基或挡土墙。
- 窗距随手、同层不齐、四面缺细节 → 先排模数，再做"无背面建筑"。
- 大工程忘 `pin_region` → 区块卸载，`fill` 报 0 blocks。
- Bedrock ID 凭记忆猜 → 一律 `find_items` + `get_block` 实测。
