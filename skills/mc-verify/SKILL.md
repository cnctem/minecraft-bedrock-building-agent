---
name: mc-verify
description: 检查与修复手册——用 heightmap/get_slice/inspect_region/find_blocks/get_block 由粗到细地验收现场；建造引擎的 verify(mismatch/holes/wrong)、对称与悬空自检；漏填/错位/朝向/悬空/未加载的诊断表与补丁程序写法。玩家说"检查一下/验收/看看哪里漏了/对不对/修一下"时加载。
---

# 检查与修复

**唯一可信的完成依据是读回来的方块，不是命令回执。**
`N blocks filled` / `Block placed` / `操作成功` 都只说明"命令被执行了"。

## 0. 体检判据（本手册的审计口径）

验收从三个角度检查：**几何体**（Y 层尖峰 / 等截面柱 / 飘空薄板 / 散点层 / 结构重叠）、
**结构体**（门窗悬空 / 结构碎裂 / 外壳缺口）、**占地**（构件 XZ 相交）。
每条判据对应的根因与修法见 **`references/audit-rules.md`**——它同时也是本项目
`build_preview` / `render_build` / `verify` 结果怎么读的说明书。

## 1. 由粗到细的检查阶梯

| 想知道 | 用 |
|---|---|
| 地面多高、落差多少、有没有坑 | `get_heightmap`（默认摘要；逐列核对才对小范围用 `detail="heights"`，看顶面分布才用 `full`） |
| 某一层/立面/剖面长什么样 | `get_slice`（字符图 + 图例，最省 token） |
| 这片区域里有什么、各多少格 | `inspect_region`（默认只回类型计数） |
| 目标方块有没有铺满、哪里不对 | `inspect_region(filter=目标)` → `match` / `mismatch` + 不符坐标 |
| 某种方块在哪 | `find_blocks` |
| 单个格子到底是什么 | `get_block` |

不要用几十个 `get_block` 拼出一片区域——又慢又贵，而且你还得自己数行。

## 2. 复检的标准流程（施工后必做）

```
1. inspect_region(filter=目标方块, limit=64)
   → 命中 X 格, 不符合 Y 格(其中空洞 H, 放错 W)
2. Y == 0 才算完成, 可以去回报玩家
3. Y > 0: 按样本坐标写一个**补丁程序**（只改那几处），build_preview → build_commit
4. 再复检一次，直到 Y == 0
```

补丁程序示例（只补空洞，别动其他东西）：

```python
holes = [(3, 0, 1), (4, 0, 1), (4, 1, 1)]     # 从 mismatch 样本抄过来
for u, v, w in holes:
    api.set(u, v, w, "stonebrick", {"direction": 0})
```

KEEP 语义保证：程序没提到的格子既不写也不删，所以补丁不会破坏已经对的部分。

## 2.5 函数库自带的“编译期自检”

用 `api.lib` 写程序时, 下面三类问题**在 preview 之前就会报错**(不用等建完才发现):

| 报错 | 含义 | 怎么改 |
|---|---|---|
| `xxx 参数不对: … 接口: xxx(...)` | 参数个数/类型不对 | 照接口签名补参数, 或 `print(api.lib.help("xxx"))` 反查 |
| `xxx: 屋顶每边至少 3 格…`(带接口行) | 尺寸太小, 函数拒绝出残缺构件 | 把范围放大到函数要求的最小值 |
| `未知方块 minecraft:xxx` | 方块 ID 写错/Java 名未映射 | `find_items` 查; 常见 Java 名(stone_bricks/bricks/dandelion)已自动映射 |

程序里的 `print(...)` 会以 `[程序输出]` 附在 `build_preview` 结果里, 适合打印
`api.lib.help()` 或自己的尺寸断言; 但不要把大段数据 print 出来占上下文。

## 3. 建造引擎自带的两道自检

| 参数 | 抓什么 | 说明 |
|---|---|---|
| `build_preview(..., symmetry="u"/"w")` | 左右/前后不对称 | 只比位置与方块类型(不比朝向)。可写 `"u:0"` 指定对称轴 |
| `build_preview(..., scan=[...])` | 悬空方块 | 下方与四邻都没支撑会列坐标；`scan` 要比建造范围大一圈 |
| `build_commit` 的 `verify` | 漏填/放错 | `holes` = 该有方块却是空气；`wrong` = 有方块但不对 |

## 4. 诊断表

| 现象 | 常见原因 | 处理 |
|---|---|---|
| 整片 `air`、`未加载>0` | 区块没加载 / 玩家走远了 | `pin_region` 覆盖施工面，重试 |
| 只有部分格子空 | 空洞（被别的填充/方块占过） | 用 `mismatch` 样本写补丁 |
| 高草/花自己消失 | 支撑面不对（石头、沙子上不能长） | 先铺 `grass_block` / 泥土 |
| 门/床只剩一半 | 玩家手动放的残缺件 | 拆掉重放：门要上下两格、床只写床头 |
| 楼梯/门朝向反了 | `direction`/`weirdo_direction` 值不对 | 用 `api.dirnum("front")` 取方向再写 |
| 悬空 | 忘了柱子/挑梁 | 加支撑，或 `inspect_region` 找出悬空点 |
| 左右不对称 | 循环只做了一侧 | `symmetry="u"` 定位，再补镜像那一侧 |
| 覆盖了箱子/告示牌 | 施工面压到已有功能方块 | `build_undo` 恢复，再缩小范围 |

## 5. 交付前检查清单

- [ ] `verify.mismatch == 0`（或 `inspect_region(filter=…)` 的 mismatch 为 0）
- [ ] `未加载` 为 0，或已如实告诉玩家"这部分没验证"
- [ ] 形状：`get_slice` 看俯视/立面，门窗位置、屋顶收口、对称都对
- [ ] 出入口能走：门口是空气、台阶能上、室内不是实心
- [ ] 悬空：没有意外的孤立方块（有 `scan` 时看自检结果）
- [ ] 光照：室内不刷怪（见 `mc-lighting`）
- [ ] 没有把玩家原有的东西静默替换掉（必要时 `build_undo`）
