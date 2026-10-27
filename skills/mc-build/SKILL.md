---
name: mc-build
description: 建造引擎 + 体素造型手册——用受限 Python 写建造程序(api.fill/box/walls/cylinder/sphere/pyramid/roof/stair 等)，经 build_preview 预览差异、build_commit 提交并自动校验、build_undo 撤销；含圆/椭圆/拱/圆柱/球/穹顶/坡度/螺旋等造型公式与半径表。玩家要求成规模的建造/改造(房子、塔、城墙、桥、地形整平、批量替换、按图纸施工)，或说"用建造引擎""写个程序建""一次建完""别一条条 fill"时加载。仅创造模式可用。
---

# 建造引擎(mc-build)

一句话：**写程序 → 预览 → 提交 → 看校验**。不要一条条 `fill`，也不要凭印象报完成。

```
get_heightmap / get_slice / inspect_region   看现场
pin_region                                   远处施工先常加载
build_preview(program, origin, facing)       编译 + 差异, 不写世界
build_commit(operation_id)                   批量写入 + 自动复读校验
build_undo                                   还原(最近 2 个)
```

## 1. 程序怎么写

程序是**函数体**，作用域里有 `api`。坐标是局部坐标 `[u 右, v 上, w 前]`，
由 `origin` + `facing` 变换到世界坐标——**换朝向不用改程序**。

```python
W, D, H = 13, 9, 6
api.fill((-1, -1, -1), (W, -1, D), "stonebrick")        # 地基, 外扩一圈
api.box((0, 0, 0), (W - 1, H - 1, D - 1), "oak_planks")  # 外墙
api.fill((1, 0, 1), (W - 2, H - 2, D - 2), "air")        # 掏空
api.fill((5, 0, 0), (7, 2, 0), "air")                    # 门洞(w=0 是正面)
for u in range(0, W, 4):                                 # 木骨架
    api.box((u, 0, 0), (u, H - 1, 0), "spruce_log")
    api.box((u, 0, D - 1), (u, H - 1, D - 1), "spruce_log")
api.box((0, H, -1), (W - 1, H, D), "dark_oak_planks", hollow=True)   # 出檐平顶
api.pattern((1, 0, 1), (W - 2, H - 2, 1), ["oak_planks", "spruce_planks"])  # 内墙纹理
```

### API

| 方法 | 说明 |
|---|---|
| `api.set(u, v, w, block, states=None)` | 单格 |
| `api.fill(a, b, block, states=None)` | 实心长方体，两角顺序任意 |
| `api.box(a, b, block, hollow=False)` | 空心盒(6 面) |
| `api.walls(a, b, block, thickness=1)` | 四面墙(无顶底) |
| `api.frame(a, b, block, step=4, thickness=1)` | 立柱骨架 |
| `api.line(a, b, block)` | 三维线 |
| `api.plane(a, b, block, axis="v")` | 单层平面(axis: u/v/w) |
| `api.cylinder(center, r, h, block, axis="v", hollow=False)` | 圆柱/筒 |
| `api.sphere(center, r, block, hollow=False)` | 球/壳 |
| `api.pyramid(a, b, height, block, hollow=True)` | 四棱锥(屋顶/塔尖) |
| `api.pattern(a, b, [blocks], axis="v")` | 按坐标取模铺纹理 |
| `api.roof(a, b, block, style="gable", ridge="u", height=None, hollow=False)` | **屋顶**：逐层内缩。`gable` 双坡（人字）/ `hip` 四坡 / `flat` 平顶；`ridge` 屋脊沿 u 或 w；`hollow=True` 只铺每层外圈（省料、留内部空间）。a/b 给屋檐那层的范围 |
| `api.stair(a, b, block, axis="w", rise=1, run=1)` | **直跑楼梯**：沿 axis 每 `run` 格升 `rise` 格，一阶一格厚 |
| `api.dir("front"/"back"/"left"/"right")` | 局部方向 → 世界方向名(给楼梯/门的状态用) |
| `api.origin` / `api.facing` | 只读上下文 |

语言子集：`for / if / 函数 / 算术`，`math.sin/cos/sqrt/floor/pi`，`range`。
**没有** `import`、文件、网络、`exec/eval/open`。死循环会被 8 秒超时杀掉。

## 1.5 读世界(贴地形建)

给 `build_preview` 传 `scan=[x1,y1,z1,x2,y2,z2]`（**局部坐标框**，体积 ≤65536）预取快照后，
程序里就能读世界：

```python
# 9×7 小屋: 墙 + 人字屋顶 + 门口台阶
api.box((0, 0, 0), (8, 4, 6), "oak_planks")
api.fill((1, 0, 1), (7, 3, 5), "air")
api.roof((-1, 4, -1), (9, 4, 7), "spruce_planks", style="gable", ridge="u")  # 带一圈出檐
api.stair((3, 4, 7), (5, 4, 9), "stonebrick", axis="w")                       # 室外台阶
```

```python
# 地基跟着地形走: 每列从地面往下垫到 -3
for u in range(0, W):
    for w in range(0, D):
        h = api.height(u, w)
        if h is not None:
            api.fill((u, h, w), (u, min(h, -1), w), "stonebrick")
```

| 方法 | 返回 |
|---|---|
| `api.height(u, w)` | 该列在快照范围内最高的非空气方块的局部 v；整列空返回 `None` |
| `api.block(u, v, w)` | 该格的方块名（`"air"` / `"stonebrick"` …）；超出快照返回 `"?"` |
| `api.solid(u, v, w)` | 是否实体（空气/水/岩浆/未知都算 False） |
| `api.air(u, v, w)` | 是否空气（或超出快照） |

注意：快照是**预览开始时**的只读副本，程序里看不到自己刚放下的方块；
要先看效果就分两个模块（先建 → 再 preview 下一段）。
建造程序需要大量逐列高度时优先走这里，让 `api.height` 直接读快照；不要用 `get_heightmap(detail="full")` 把大网格读进上下文再手抄成程序。

## 1.6 两道自检(预览阶段, 不写世界)

| 参数 | 作用 |
|---|---|
| `symmetry="u"` / `"w"` | 左右 / 前后镜像对称检查；默认用包围盒中线，可写 `"u:0"` 指定对称轴。只比位置与方块类型(不比朝向状态)，不对称会给出坐标 |
| `scan=[...]` 给了快照 | 顺带做**悬空检查**：写入的方块下方与四邻都没有支撑会列出坐标（玻璃顶、吊灯等有意为之的忽略即可） |

对称性检查是**写世界之前**抓设计错误最便宜的手段：先 `symmetry` 预览一遍，比建完再改省得多。
悬空检查只在快照覆盖范围内判断，`scan` 要比建造范围大一圈。

## 1.7 动手前先"看"一眼(视觉反馈)

`build_preview` 之后、`build_commit` 之前，可用 `render_build` 把计划渲染成字符图：

```text
render_build(operation_id="b123-1", views=["front", "iso"])
```

- `front/back/left/right` 立面、`top` 俯视、`iso` 等距立体（看屋顶与体块最直观）
- 字符图里 `.` 是空气，其余符号看图例；超宽会自动降采样
- 同时导出 PNG 到服务器 `logs/renders/`（玩家游戏内看不到，但运营/留档可用）
- 看已建好的东西用 `render_region(x1,y1,z1,x2,y2,z2, views=["iso"])`

比例不对、屋顶收口别扭、门窗节奏乱了——在这一步就该改程序，而不是建完再返工。

**给玩家看的**：`build_blueprint(operation_id, view="front", at=[x,y,z], direction="south")`
会把图铺成彩色混凝土马赛克墙（1 像素 1 格，`step=2` 减半）。它同样先预览、再
`build_commit`、`build_undo` 可撤。玩家说"先画个样子给我看/在外面立个图"时用它。

## 2. 三条必须记住的语义

1. **KEEP**：程序没提到的格子**不写也不删**。清空必须 `api.fill(..., "air")`。
   所以"只补一个屋顶"不会误删室内。
2. **后写覆盖先写**：同一格多次写，以最后一次为准（可以先铺满再掏洞）。
3. **未加载 = 不写也不校验**：preview 的 `未加载` 不为 0 时，先 `pin_region` 再 preview。

## 3. 方块 ID 与状态

- 用基岩版 ID：`stonebrick`（不是 `stone_bricks`）、`oak_planks`、`short_grass`（不是 `grass`）。
  不确定就 `find_items("石砖")` 查。
- 带状态时用 `states`，键名是基岩版状态名：
  ```python
  d = api.dir("front")                      # 比如 "south"
  api.set(0, 0, 0, "oak_stairs", {"weirdo_direction": 2})
  ```
- **多格方块现在支持**，编译器会自动按实测规则处理（不用你自己写两格）：
  | 方块 | 程序里怎么写 | 引擎行为 |
  |---|---|---|
  | 门 `*_door` / `wooden_door` | `api.set(u,v,w,"wooden_door",{"direction":d})` | 自动补上下两半（`upper_block_bit`） |
  | 床 `bed` | `api.set(u,v,w,"bed",{"direction":d})` | 你给的格子是**床头**，床尾自动放在 `direction` 方向（0=北 1=东 2=南 3=西） |
  | 高草/大型蕨等双格植物 | `api.set(u,v,w,"tall_grass")` | 自动补上下两半；**必须放在草/土上**，否则引擎会自己消失 |
  `direction` 用整数（旧式 state）；`d = api.dirnum("front")` 可以按朝向取。

## 4. 工作流(按模块)

```
地基 → 骨架 → 墙 → 门窗 → 楼板 → 屋顶 → 室内 → 细节
```

每个模块：`build_preview` → 看差异/警告 → `build_commit` → 看 `verify`。

- `verify.mismatch == 0` 才算这个模块完成；否则按 `holes`（空洞，该有方块却是空气）与
  `wrong`（放错）的样本坐标写**补丁程序**（只改那几处，KEEP 语义保证不动别处）。
- 一个模块失败只影响它自己，不用重做整栋。
- 玩家说"拆了/不要了"：`build_undo`（栈里只有最近 2 个操作）。

## 5. 常见错误

| 现象 | 原因 / 处理 |
|---|---|
| `未知方块 xxx` | ID 写错或写成 Java 版名字；`find_items` 查 |
| `包围盒体积超过上限` | 一次太大；按模块拆，或先整平再建 |
| preview 全是"未加载" | 区块没加载；`pin_region` 覆盖施工面后重试 |
| `多格方块…会残缺` | 换成普通方块，或改用 `setblock` |
| commit 后 `mismatch>0` | 看 samples 坐标写补丁；不要直接说"完成了" |
| `操作不存在或已过期` | 行为包 reload 过；重新 `build_preview` |

---

# 附:体素造型公式(圆/球/穹顶/坡度/螺旋)

> 下面是从原 `mc-build` 合并进来的造型公式。用建造引擎时优先用 `api.cylinder/sphere/roof/stair`
> 直接表达; 需要手算扫描线(例如只用 `run_server_command` 的 fill)时再用这些表。
> 附表: `references/circle-tables.md`、`references/dome.md`、`references/slopes.md`、`references/smooth-surfaces.md`、`references/spiral.md`。

# 体素造型手册(圆 / 弧 / 球 / 曲面)

把连续曲线塞进整数网格，固定用三件事：**half-up 离散公式、8 折对称、半高方块补落差**。
指令语法见 `mc-commands`；ID 不确定先 `find_items`。

## 0. 动手前定清楚

- 圆心/起点、半径还是直径、空心轮廓还是实心面、所在平面、材质。
- 地面圆/圆台在 X-Z 平面；圆窗/拱在 X-Y 或 Z-Y 平面，把公式里的一个轴换成 y。
- 默认：玩家附近地面、半径 8~10、单层空心轮廓、醒目方块；拿不准只问一句。
- 奇数中心优先：半径 R 的跨度 = 2R+1。偶数直径把中心放在 4 块接缝处。

## 1. 最稳公式：half-up 扫描 + 两遍

圆心 `(cx, cz)`、半径 `R`，取右上 1/4 弧：

```
z = round_half_up(sqrt(R*R - x*x))，x = 0..R
第 1 遍：x 从 -R 到 R，每列放 (cx+x, cz±z)
第 2 遍：z 从 -R 到 R，每列取 x = round_half_up(sqrt(R*R - z*z))，放 (cx±x, cz+z)
```

- **两遍必须做**；第 2 遍补齐左右两侧近乎竖直的弧，少了会像被压扁的 `()`。
- `R=5` 的 1/4 弧是 `0,5 1,5 2,5 3,4 4,3 5,0`；展开后用 `ptc` 批量提交。
- `round()` 指 half-up（0.5 向上）；不要用截断或 banker's rounding，否则 `.5` 半径会偏 1 格。
- R≤20 直接查 `references/circle-tables.md`；R>20 用公式/Plotz，并按 8 个 45° 扇区校验接缝。

## 2. 空心与实心口径

- **空心轮廓/墙/塔/穹顶肋骨**：用两遍描边扫描。实测 R=3~59 与 Bresenham/midpoint 一致。
- **实心圆盘**：可只做第 1 遍，每列 `fill cz-z → cz+z`，共 2R+1 条命令。
- 欧氏阈值填充 `sqrt(x²+z²) ≤ R+0.5` 会在 45° 对角多出孤立凸块；未声明口径时改用描边法向内填，视觉略小半格但更稳。
- 偶数直径用格子中心 `(i+0.5,j+0.5)`，满足 `round(hypot(...)) == D/2`；两侧会略平，允许时直接用 D+1 奇数。

## 3. 常用变体

- **椭圆**：`z = round_half_up(b*sqrt(1-(x/a)^2))`，x 取 -a..a，再沿对角线翻一遍。
- **竖直圆/圆窗/拱**：把一个水平轴换成 y；半圆只取 y≥圆心的上半。
- **圆柱**：一段高度内每层复制同一圆；实心逐列 `fill` 更省。
- **球/半球**：逐层半径 `r_k = round_half_up(sqrt(R²-k²))`，第 k 层画半径 r_k 的实心圆，k=0..R 为上半球。
- **圆角矩形**：四角各画半径 2~4 的 1/4 圆，四边直线连接，边缘再用楼梯/半砖收口。

## 4. 柔和曲面

- 相邻层/列高差保持 ≤1 格；接近球顶半径不变时，用楼梯、倒楼梯或上半砖收成帽。
- **凸角换楼梯，凹角换半砖**；楼梯朝向贴曲线切线，不要一律朝圆心。
- 过渡带：高差 ≥1/格用整块，0.5~1/格用楼梯，≤0.5/格用半砖；8~12 格坡常见整块:楼梯:半砖 ≈ 4:4:2。
- 楼梯 ≈45°，上下半砖交替 ≈22.5°，纯整块逐层收 ≈视觉 45°；更缓坡用半砖拆成 0.5 格。
- 材质同色系，否则半砖/楼梯会产生斑马纹；用明度梯度强化曲率。
- 详细包边见 `references/smooth-surfaces.md`。

## 5. 专题速查

- **穹顶/洋葱顶/尖顶**：半球逐层半径、R=6/8/16 表、鼓腹 `D+2/D+4`、8/12 根哥特肋见 `references/dome.md`。
- **螺旋楼梯**：22.5°/45°/90°/级的步数、井径、净高、双螺旋见 `references/spiral.md`。
- **斜墙/坡度**：1:1/1:2/1:3/2:3 模板、45° 之字墙半砖夹层见 `references/slopes.md`。
- **大曲面 R≥30**：先设中心柱与 10 格参考网格，再按 45° 分 8 段闭合；每段单独校验接缝。

## 6. 工具落地

1. `get_player_position` 定圆心高度；`pin_region(x±(R+4), z±(R+4))`。
2. 标中心：`setblock cx y cz glowstone`；立临时中心柱到球形顶部，避免逐层从上一层量误差累积。
3. 空心每条 `setblock`；实心每列 `fill`；把 `run_server_command` 统一用 `ptc` 提交，别逐条往返。
4. 先做 R=4~6 小样，确认楼梯朝向与包边，再放大。
5. `get_slice` 扫切面看形状；`get_block` 抽检四极点 `(cx±R,cz)`、`(cx,cz±R)` 与 45° 点。
6. 清中心标记，汇报半径、口径、材质。

## 7. 坑清单

- 空心圆漏第 2 遍 → 两侧缺块。
- 偶数直径硬找中心块 → 整体偏半格；中心应落在 4 块接缝。
- 穹顶逐层从上一层量 → 误差累积成椭圆；必须围绕中心柱/固定轴。
- 穹顶单一收分到底 → 轮廓死板；洋葱顶忘记赤道外扩鼓腹。
- 螺旋楼梯级高 1 格 → 碰头；净高至少 2 格，栏杆不能断档。
- 45° 之字墙不做面接触 → 远看断裂；用整砖 + 半砖夹层 + 楼梯外沿。
- 楼梯朝向贴错或材质不同色 → 越抹越乱、远看斑马纹。
- 一次 `fill` 超 `max_block_modifications`；大圆拆列/分批 `ptc`。
- 坐标轴搞混；地面圆 y 固定，竖直圆才改 y。
- 半砖 `vertical_half`、楼梯 `weirdo_direction`/`upside_down_bit` 拿不准时，先 `get_block` 读回照抄。
