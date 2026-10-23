---
name: mc-commands
description: 基岩版(Bedrock)命令与文本手册——fill/setblock/clone 的完整变体、方块状态与朝向、超量分段、施工套路；tellraw 文本组件与可点击消息(rawtext/clickEvent/hoverEvent、传送/网页/导航菜单/公告按钮)。用 run_server_command 做零星施工或给玩家发格式化文本时加载(成规模建造请走 mc-build 的建造引擎)。
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

---

# 附:tellraw 与可点击消息

> 从原 `mc-commands` 合并进来的内容。**基岩版 tellraw 不支持 clickEvent/hoverEvent**,
> 需要"点一下"的交互请用 `send_menu`(底层 `scriptevent viktor:menu`, server-ui 表单)。
> 附表: `references/examples.md`, `references/rawtext.md`。

# tellraw 超链接与可点击消息手册

`tellraw` 发的是 **Bedrock rawtext JSON**，不是 Java 版直接 `{"text":...}` 语法。
`run_server_command` 里命令**不带前导 `/`**；JSON 内 `run_command` 的 value**要带 `/`**。

## 0. 能力与边界

- 可点击文本能：`open_url` 打开网页、`run_command` 执行一条命令、`suggest_command` 只填入聊天框。
- 悬浮文本能：`show_text` 显示说明；`show_item`/`show_entity` 版本差异大，先小范围实测。
- **一次点击只执行一条命令**。要“传送 + 播放音效 + 发消息”，需要事先做函数/命令链或拆成多个按钮。
- `tellraw` 不改变权限：`run_command` 仍受点击玩家自己的命令权限/作弊设置限制。
- 命令行不写 `/tellraw`，从 `tellraw` 开始；JSON 外的目标选择器 `@a`/`@p` 交给 `run_server_command`。

## 1. 最小模板

```
tellraw <目标> {"rawtext":[{"text":"普通文本"}]}
```

例：

```
tellraw @a {"rawtext":[{"text":"欢迎来到主城","color":"gold","bold":true}]}
```

- `<目标>` 常用 `@a`(所有人)、`@p`(最近玩家)、玩家名(推荐精确发送)。
- 从控制台发消息时，顶层目标不要用 `@s`；`@s` 适合放进点击后执行的 `run_command` 里。
- 多个文本组件按数组顺序拼接：

```
tellraw @a {"rawtext":[{"text":"["},{"text":"传送","color":"aqua"},{"text":"]"}]}
```

## 2. 文本组件字段

| 字段 | 作用 | 示例 |
|---|---|---|
| `text` | 显示文本 | `"text":"传送"` |
| `color` | 颜色 | `"color":"gold"` |
| `bold` | 粗体 | `"bold":true` |
| `italic` | 斜体 | `"italic":true` |
| `underlined` | 下划线 | `"underlined":true` |
| `strikethrough` | 删除线 | `"strikethrough":true` |
| `obfuscated` | 乱码 | `"obfuscated":true` |
| `clickEvent` | 点击动作 | 见 §3 |
| `hoverEvent` | 悬浮提示 | 见 §3 |

颜色优先用 `gold/aqua/green/red/yellow/gray`；不要依赖 `§` 转义。按钮文字建议 ≤10 个汉字，重要按钮加粗+下划线。

## 3. 点击与悬浮动作

### 打开网页

```
tellraw @p {"rawtext":[{"text":"打开服务器地图","color":"aqua","underlined":true,"clickEvent":{"action":"open_url","value":"https://example.com/map"},"hoverEvent":{"action":"show_text","value":"点击后在浏览器打开地图"}}]}
```

### 传送到坐标

```
tellraw @p {"rawtext":[{"text":"[传送到喷泉]","color":"gold","bold":true,"clickEvent":{"action":"run_command","value":"/tp @s 120 65 -40"},"hoverEvent":{"action":"show_text","value":"点击传送到喷泉"}}]}
```

- `@s` 在点击时解析为**点击者**，适合个人传送。
- 坐标要用绝对整数；相对 `~` 会相对点击者当前位置。
- 先 `get_player_position` + `get_block` 确认落点，建议 y 取地面上一层。
- 跨维度：`value":"/execute in nether run tp @s 0 64 0"`；先小范围测试语法。

### 执行命令 / 只建议命令

```
tellraw @a {"rawtext":[{"text":"[领取今日补给]","color":"green","bold":true,"clickEvent":{"action":"run_command","value":"/give @s bread 3"},"hoverEvent":{"action":"show_text","value":"每人每天限领"}}]}
```

```
tellraw @p {"rawtext":[{"text":"[填写回城命令]","color":"yellow","clickEvent":{"action":"suggest_command","value":"/tp @s 100 64 200"},"hoverEvent":{"action":"show_text","value":"只填入聊天框，不会立即执行"}}]}
```

- 破坏性、发物品、扣分/经济命令必须得到玩家明确授权。
- 对公开服务器优先 `suggest_command`；要直接执行时限制目标并做权限/冷却校验。

### 纯悬浮说明

```
tellraw @p {"rawtext":[{"text":"旧传送门","color":"light_purple","hoverEvent":{"action":"show_text","value":"已废弃，点击无效果"}}]}
```

## 4. 坐标超链接工作流

1. `get_player_position` 拿到落点 `x y z`，换算成安全站立位置。
2. 用 `inspect_region`/`get_block` 确认目标不是岩浆、水、基岩或高空悬空。
3. 构造 `rawtext`，把坐标写成绝对整数，按钮放入 `run_command`。
4. 先向自己发一条测试：`tellraw @p {...}`，斜杠值使用 `/tp @s x y z`。
5. 点击验证落点、维度、权限和提示；失败先检查 JSON 引号与 `/`。
6. 批量地标列表用 `ptc` 一次提交多条 `tellraw @p ...`，每条控制一行，避免超长命令。

## 5. 常见界面模板

- 单按钮：`[传送]` + `clickEvent.run_command` + `hoverEvent.show_text`。
- 横向菜单：`[主城] [矿场] [农场]`，组件之间用 `{"text":"  "}` 分隔。
- 多行列表：连续发多条 `tellraw @p ...`；不要把所有按钮挤在一条超长 JSON。
- 网页组件：`open_url`；命令组件：`run_command`；教学/敏感组件：`suggest_command`。
- 按钮颜色：传送=gold/aqua，危险=red，领取=green，教学=yellow，普通链接=blue/aqua。
- 每条消息不超过 5~7 个按钮；按钮超过一屏滚屏后很难点。

完整字段、转义和多组件规则见 **`references/rawtext.md`**；坐标、网页、菜单、地标、商店与批量模板见 **`references/examples.md`**。

## 6. 转义与长度

- JSON 字符串内的双引号写成 `\"`，反斜杠写成 `\\`；URL 的 `&` 原样保留，玩家名/命令中的引号必须转义。
- 不要把单条命令拼到几百个按钮；`tellraw` 过长会被截断/报语法错误，按行拆分。
- 不要在 `text` 里直接写未经转义的用户输入；先替换 `\\`、`\"` 和控制字符。
- 目标是多人时避免每人各自执行 `open_url`；需要个人化按钮就分别指定玩家名/`@p`。

## 7. 坑清单

- 用了 Java 版 `{"text":"..."}` → Bedrock 需要外层 `{"rawtext":[...]}`。
- `run_command` 的 value 忘写前导 `/` → 点击不执行或报错。
- 顶层用 `@s` 发送 → 控制台没有点击者语义；用 `@a`/`@p`/玩家名。
- `open_url` 用了非法 URL 或 `http` 兼容性差 → 优先 HTTPS，发送前检查完整域名。
- 多个动作写成一个按钮 → 只会执行一条命令；拆按钮或预先做命令链。
- 坐标用相对值 → 每个点击者传送到不同位置；地标必须用绝对整数。
- 直接发破坏性命令按钮 → 必须明确授权、限定目标并做权限检查。
- 颜色用 `§` 或 Java 组件字段 → 优先用 Bedrock `color`/`bold`/`underlined`。
- 忘测跨维度/权限 → 先向自己发测试消息，确认后再广播。
