---
name: mc-build
description: 建造引擎手册——用受限 Python 写建造程序(api.fill/box/walls/cylinder/sphere/pyramid 等)，经 build_preview 预览差异、build_commit 提交并自动校验、build_undo 撤销。玩家要求成规模的建造/改造(房子、塔、城墙、地形整平、批量替换、按图纸施工)，或说"用建造引擎""写个程序建""一次建完""别一条条 fill"时加载。仅创造模式可用。
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
| `api.dir("front"/"back"/"left"/"right")` | 局部方向 → 世界方向名(给楼梯/门的状态用) |
| `api.origin` / `api.facing` | 只读上下文 |

语言子集：`for / if / 函数 / 算术`，`math.sin/cos/sqrt/floor/pi`，`range`。
**没有** `import`、文件、网络、`exec/eval/open`。死循环会被 8 秒超时杀掉。

## 1.5 读世界(贴地形建)

给 `build_preview` 传 `scan=[x1,y1,z1,x2,y2,z2]`（**局部坐标框**，体积 ≤65536）预取快照后，
程序里就能读世界：

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
- **多格方块会被拒绝**：门、床、高草/大型蕨、双箱等单格写入只出一半。用普通方块替代，
  或单独用 `run_server_command` 的 `setblock` 放（那里走原生命令）。

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
