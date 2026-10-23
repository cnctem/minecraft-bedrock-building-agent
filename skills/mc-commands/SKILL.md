---
name: mc-commands
description: 基岩版(Bedrock)命令施工手册——fill/setblock/clone 的完整变体、方块朝向与状态、超量填充分段、批量施工套路。要下指令、批量施工, 或不确定命令语法/朝向/状态时先加载。
---

# 基岩版命令施工手册

`run_server_command` 以控制台身份执行指令。**本手册是基岩版(Bedrock)语法, 不是 Java 版** —— 写错版本会 Syntax error。方块 ID 不确定先用 `find_items` 查(唯一权威来源)。

## 0. 下单前

- 坐标用整数方块坐标(`get_player_position` 返回的就是)。fill/setblock 接受小数, 但按住它选实际方块即可。
- 指令不用带斜杠。
- 输出判读: 成功回 `N blocks filled` / `Block placed`; 常见失败:
  - `Syntax error` —— 语法/ID 错(可能是 Java 语法)。
  - `Cannot place blocks outside of the world` —— 区块未加载或越界, 多半是区块没加载 → 先 `pin_region`。
  - `0 blocks filled` / `No block changed` —— 范围里没有可改的方块(常因区块没加载或都被同种状态占了)。
  - `Too many blocks` / 体积超限 —— 一次填太多, 分段。

## 1. fill —— 批量填一个长方体

```
fill <对角1> <对角2> <方块ID> [方块状态] [处理模式]
fill <对角1> <对角2> <新方块ID> [方块状态] replace <被替换方块> [其状态]
```

- 两个对角点顺序无所谓(任一方向的两个角都行)。
- **处理模式**(默认 `replace`):
  - `replace` 全部替换(默认)。
  - `keep` 只替换空气 —— 在已有结构上补墙、填空隙常用, 不动已有方块。
  - `outline` 只在外壳放方块, 内部保持原样。
  - `hollow` 外壳用新方块、内部清成空气 —— 一步造"盒子/房间"。
  - `destroy` 破坏式替换并掉落物品 —— 大批量会卡服又刷物品, **慎用**。
  - `strict` 要所有目标都能放置才执行。
- 写法要点:
  - 只要处理模式、不给状态: 直接跟在方块后, 如 `fill 0 0 0 4 0 4 stone keep`。
  - 要状态 + 处理模式: 状态在前、模式在后; 无状态就写 `[]`, 如
    `fill 0 0 0 4 0 4 oak_stairs ["weirdo_direction"=0] replace`。
- 只替换指定旧方块: `fill 0 0 0 9 9 9 stone [] replace dirt`(把这片里的泥土换成石头)。
- **上限**: 一次默认 **32768 格**(受 gamerule `max_block_modifications` 影响)。超了会失败, 要**分段**: 沿一个轴切成若干 ≤32768 的长方体, 再用 `ptc` 一次提交。
- 清空: 目标方块填 `air`。
- 远处施工区块会卸载导致失败, 创造/执行模式先用 `pin_region` 把施工面设为常加载。

## 2. setblock —— 放单块(可精确指定朝向/状态)

```
setblock <x y z> <方块ID> [方块状态] [destroy|keep|replace]
```

- 默认 `replace`; `keep` 仅在原方块是空气时生效; `destroy` 会掉落原方块。
- **fill 只会把整片铺成同一种状态; 要每块不同朝向(楼梯、弧线、旋转、曲面)时, 必须逐块 `setblock`**, 用 `ptc` 一次提交几十条, 比一条条调省往返。

## 3. clone —— 复制一块区域

```
clone <对角1> <对角2> <目标点> [replace|masked] [normal|force|move]
clone <对角1> <对角2> <目标点> filtered <normal|force|move> <方块ID> [状态]
```

- `replace`(默认)连空气一起复制; `masked` 只复制非空气 —— 把图案"盖章"到已有表面上常用 `masked`。
- `normal`(默认); `force` 允许目标与源重叠; `move` 复制后清空源(等于移动)。
- 跨维度: `clone from <源维度> <对角1> <对角2> to <目标维度> <目标点> ...`(维度: `overworld`/`nether`/`the_end`)。

## 4. 方块状态(朝向/形态) —— 最容易错的地方

语法: 方块 ID 后空一格, 用 `["状态名"="值", ...]`。状态名可带 `minecraft:` 前缀; 数字/布尔不加引号。

```
setblock ~ ~ ~ chest ["minecraft:cardinal_direction"="east"]
setblock ~ ~2 ~ quartz_slab ["minecraft:vertical_half"="top"]
setblock ~ ~ ~ oak_stairs ["weirdo_direction"=2,"upside_down_bit"=true]
```

常用状态:

| 方块 | 状态名 | 取值 |
|---|---|---|
| 楼梯 `*_stairs` | `weirdo_direction` | 0东 1西 2南 3北(整块那一侧朝向) |
| | `upside_down_bit` | `true`=倒置 |
| 台阶 `*_slab` | `minecraft:vertical_half` | `"bottom"` / `"top"` |
| 整台阶 | —— | 是另一个方块 `*_double_slab`, **不是状态** |
| 原木/柱状(原木/石英/紫珀/深板岩/锁链/玄武岩…) | `pillar_axis` | `"x"` / `"y"` / `"z"` |
| 火把/红石火把 | `torch_facing_direction` | `"unknown"`(地上) / `"north"`/`"south"`/`"east"`/`"west"`(贴墙) |
| 箱子/熔炉/切石机/营火 | `minecraft:cardinal_direction` | `"north"`/`"south"`/`"east"`/`"west"` |
| 朝向方块(活塞/发射器/投掷器/观察者/末地烛/避雷针/按钮…) | `facing_direction` | 0下 1上 2北 3南 4西 5东 |
| 立式告示牌/旗帜 | `ground_sign_direction` | 0–15(旋转) |
| 活板门 | `direction`(0–3) / `open_bit` / `upside_down_bit` | |
| 门 | `direction` / `open_bit` / `upper_block_bit` / `door_hinge_bit` | 下半块与上半块要各放一次 |
| 栅栏门 | `direction` / `open_bit` / `in_wall_bit` | |
| 灯笼 | `hanging` | `true`=吊在方块下方 |
| 蜡烛 | `candles`(0–4) / `lit` | |

**拿不准数值时最稳的办法**: 在世界里放/找一块同类方块, 用 `get_block` 读出它的 states(返回的就是状态名与值), 照抄进 `["名"=值]`。状态名以游戏实测为准, 别硬背。更全的状态表见 `references/block-states.md`。

## 5. 施工套路

- **先小样后铺开**: 先 fill 一小块确认效果与朝向, 再 `ptc` 批量铺开。
- **长条/大面分段**: 单轴切成 ≤32768 的块, `ptc` 一次提交。
- **只换旧块**: `fill ... <新方块> [] replace <旧方块>` 保留其它方块。
- **造壳体/房间**: `hollow` 一步出"外壳+空腔", 再 `setblock` 开门窗。
- **复制装饰**: 做一小段后用 `clone` 复制。
- **朝向编排(弧线/螺旋/曲面)**: 用 `ptc` 一次提交几十条 `setblock`, 每条带各自的状态。
- **复检**: 填完用 `inspect_region`(filter=目标方块, 看 mismatch) / `get_slice` 抽检, 别只看"指令已执行"。

## 6. 坑清单

- **Java 语法直接报错**: Java 用 `stone[axis=y]`, 基岩用 `["pillar_axis"="y"]`(方括号紧挨方块、`=` 两侧、值要引号)。
- **基岩特有 ID**(写 Java 名会 Syntax error): 橡木门是 `wooden_door`(不是 `oak_door`)、橡木告示牌是 `standing_sign`/`wall_sign`、中继器是 `unpowered_repeater`/`powered_repeater`、比较器是 `unpowered_comparator`/`powered_comparator`、史莱姆方块是 `slime`、砖块是 `brick_block`。拿不准就 `find_items`。
- fill 不能每格不同状态 —— 要变化就用 `setblock`。
- 忘写状态 = 用默认朝向(楼梯默认 `weirdo_direction=0`), 弧线/朝向会错。
- "Cannot place blocks outside of the world" 多半是区块未加载, 先 `pin_region`。
- 两个对角点写反无所谓, 但别写成零体积(起点=终点只有 1 格)。
