# 家具配方库(基岩版)

配套 `SKILL.md`。给出常见家具的**就地摆法与示例命令**。ID 用 `find_items` 确认;
`<木>` 是可替换的木材(oak / spruce / birch / jungle / acacia / dark_oak / mangrove / cherry / crimson / warped),
`<色>` 是颜色(white / gray / red / blue / …)。

## 坐标与朝向约定

- 相对坐标 **(x, y, z)**, `y` = 家具落脚的第一格(其下 `y-1` 是地板)。家具默认**面朝 +Z(南)**。
- 楼梯 `weirdo_direction`: **0 东(+X) 1 西(−X) 2 南(+Z) 3 北(−Z)**, 指**高(完整)那一侧**朝向。
  椅子/沙发的**高侧 = 靠背方向**(面朝 +Z 时靠背在 −Z, 用 `3`)。
- 告示牌块 ID: 橡木 `standing_sign` / `wall_sign`, 其他 `<木>_standing_sign` / `<木>_wall_sign`。
- 状态拿不准: 先放一块 `get_block` 读回来, 照抄。批量摆放用 `ptc`。

---

## A. 座椅

### A1 简易椅(1 格)
一个楼梯就是一个椅子: 高侧朝后当靠背, 低侧朝前当座。
```
setblock <x> <y> <z> oak_stairs ["weirdo_direction"=3]     # 面朝南
```

### A2 靠背椅(背更高一点)
楼梯当座; 座后放一块实心块 + 其上一条半砖, 得到 1.5 格靠背。
```
setblock <x> <y>   <z-1> oak_planks
setblock <x> <y+1> <z-1> oak_slab ["minecraft:vertical_half"="bottom"]
setblock <x> <y>   <z>   oak_stairs ["weirdo_direction"=3]
```

### A3 扶手椅(3 格宽)
```
setblock <x-1> <y> <z-1> oak_planks          # 背左
setblock <x>   <y> <z-1> oak_planks          # 背中
setblock <x+1> <y> <z-1> oak_planks          # 背右
setblock <x-1> <y> <z>   oak_planks          # 左扶手
setblock <x+1> <y> <z>   oak_planks          # 右扶手
setblock <x>   <y> <z>   oak_stairs ["weirdo_direction"=3]   # 座
setblock <x-1> <y+1> <z> oak_slab            # 扶手加高(可选)
setblock <x+1> <y+1> <z> oak_slab
```

### A4 沙发 / 长凳(3 座, 面朝 +Z)
背排用整块(可再叠一层半砖加高), 座排用半砖, 两端整块当扶手; 想软一点把座面换 `<色>_wool`。
```
fill <x-1> <y>   <z-1> <x+1> <y>   <z-1> oak_planks          # 背
fill <x-1> <y+1> <z-1> <x+1> <y+1> <z-1> oak_slab            # 背加高
fill <x-1> <y>   <z>   <x+1> <y>   <z>   oak_slab            # 座
setblock <x-2> <y> <z> oak_planks                            # 左扶手
setblock <x+2> <y> <z> oak_planks                            # 右扶手
fill <x-1> <y+1> <z> <x+1> <y+1> <z> <色>_carpet            # 坐垫(在整块座面时更稳)
```

---

## B. 桌子

### B1 边桌 / 床头柜(1×1)
整块 + 半砖 = 1.5 高的桌; 面上可放花盆/灯/书。
```
setblock <x> <y>   <z> oak_planks
setblock <x> <y+1> <z> oak_slab ["minecraft:vertical_half"="bottom"]
```

### B2 长桌 / 餐桌(栅栏腿 + 半砖面)
栅栏做腿(被上层半砖遮掉上半段, 正好留 1 格腿), 半砖铺面。桌子面高 1.5 格。
```
fill <x1> <y+1> <z1> <x2> <y+1> <z2> oak_slab        # 桌面
setblock <x1> <y> <z1> oak_fence                     # 四角腿
setblock <x2> <y> <z1> oak_fence
setblock <x1> <y> <z2> oak_fence
setblock <x2> <y> <z2> oak_fence
```
> 桌面很大时中间可加 `<木>_log`(柱状)支腿; 想更薄就桌面用 `<木>_trapdoor` 平铺一层。

### B2b 薄桌面小桌 / 茶几(栅栏腿 + 地毯或压力板当桌板)
半砖桌面"实"、地毯桌面"轻"。**栅栏当腿 + 地毯当桌板**是最省料的组合, 矮而精致, 适合茶几、圆桌、
户外咖啡桌、床头小台; 四面都能看, 不占地方。
```
setblock <x> <y>   <z> oak_fence                     # 腿
setblock <x> <y+1> <z> white_carpet                 # 地毯桌板(可换任意 <色>_carpet)
# 或换成薄板桌子:  setblock <x> <y+1> <z> oak_pressure_plate
```
> **四腿长桌同理**: 四角栅栏腿 + 每个顶格一块地毯当桌面, 比半砖桌面更轻更薄。
> 地毯做桌板时其下必须是栅栏/墙等有顶面的方块; 放完用 `get_block` 确认桌板在你想要的高度
> (想要更正/更高就改回半砖 `*_slab`)。桌上再摆 `candle`/`flower_pot`/`cake` 收尾。
> 地毯还能一物多用: 桌布、坐垫、墙面软包、床尾毯 —— 见 `SKILL.md` 能力总表。

### B3 书桌
整块桌面(2 高) + 正面活板门当抽屉 + 桌面摆 `lectern` / `frame` / 灯。
```
fill <x1> <y+1> <z1> <x2> <y+1> <z2> oak_planks      # 桌面
setblock <x1> <y> <z1> oak_planks                    # 桌体
setblock <x1> <y+0> <z2> oak_trapdoor ["direction"=2]   # 抽屉面(朝向以实测为准)
```

---

## C. 床与卧室

### C1 床
床本体是 `bed`(2 格长, 方向状态以 `get_block` 实测)。放在抬高的地台上更精致:
```
# 地台(比地板高 1 格)
fill <x-1> <y> <z-1> <x+2> <y> <z+2> oak_planks
# 床(占 2 格, 抬高 1 格)
setblock <x> <y+1> <z> bed ["direction"=0]           # 朝向状态请实测
setblock <x> <y+1> <z+1> bed ["direction"=0]
# 床头板
fill <x-1> <y+1> <z-1> <x+2> <y+2> <z-1> oak_planks
# 床头柜两盏灯
setblock <x-1> <y+1> <z-1> ... ; setblock <x+2> <y+1> <z-1> ...
```

---

## D. 储物与柜子

- **木桶** `barrel` = 现成的柜/凳/箱, 可堆叠、可当矮桌。
- **箱子墙**: `chest` 并排 + 上方 `frame`(物品展示框)标注内容 → 一目了然的仓库。
- **衣柜**: 整块柜体 + 正面 `<木>_trapdoor` 当柜门; 上方一条 `oak_slab` 压顶。
```
fill <x1> <y> <z> <x2> <y+2> <z> oak_planks            # 柜体(3 高)
fill <x1> <y> <z+1> <x2> <y+2> <z+1> oak_trapdoor      # 柜门(贴正面)
```
- **展示柜**: 石英/白混凝土柜体 + `glass_pane` 正面 + 里面 `frame` 摆物。

---

## E. 厨房与餐饮

### E1 台面(整排)
底柜用整块, 台面用半砖。高 1.5 格。
```
fill <x1> <y>   <z> <x2> <y>   <z> smooth_stone       # 底柜
fill <x1> <y+1> <z> <x2> <y+1> <z> quartz_slab        # 台面
```
### E2 水槽
把台面某格换成 `cauldron`(可盛水), 其上方不放半砖 → 内嵌水槽; 龙头用墙上的 `lever` 或 `tripwire_hook`。
```
setblock <xs> <y>   <z> cauldron                     # 替换底柜
# <xs> 处 <y+1> 不放台面
setblock <xs> <y+2> <z> lever ["lever_direction"="side"]   # 龙头(状态实测)
```
### E3 灶台 / 烤箱
`campfire` 当明火灶(注意点火状态), `smoker`/`furnace` 当烤箱, 正面加 `iron_trapdoor` 当炉门。
```
setblock <xo> <y>   <z> smoker
setblock <xo> <y+1> <z> iron_trapdoor ["direction"=2]   # 炉门(朝外)
setblock <xc> <y>   <z> campfire ["extinguished"=false] # 灶眼
```
### E4 冰箱
`iron_block`/`white_concrete` 柜体 + `iron_door` 或 `iron_trapdoor` 柜门。
### E5 上柜 / 吊柜
从天花板吊下 `<木>_trapdoor` 或 `glass_pane` 柜门; 或直接挂一排 `barrel` 当吊柜。
### E6 餐桌布置
桌面放 `cake`、`flower_pot`、`<色>_candle`、`frame`; 桌上给每人放一个盘子 = `white_carpet`。

---

## F. 卫浴

### F1 浴缸
下沉式: 地面 `cauldron` 或 `water` ×2, 四周 `stone_slab` 收边, 配 `<木>_trapdoor` 边。
```
fill <x1> <y> <z1> <x2> <y> <z2> water              # 水面(或 cauldron)
setblock <x1-1> <y> <z1> smooth_stone ...            # 围边
```
> 用 `cauldron` 更"浴缸", 用 `water` 更"泳池/温泉"。水会流动, 记得周围封边。
### F2 马桶
`brewing_stand` 当马桶座, 后方一堵矮墙 + 水箱(整块), 旁边 `lever` 当冲水。
```
setblock <x> <y> <z> brewing_stand
setblock <x> <y> <z-1> smooth_stone                  # 水箱
```
### F3 洗手台 / 镜子
`hopper` 或 `cauldron` 当盆, 半砖台面, 上方 `glass_pane`(灰/淡蓝染色)当镜子 + `frame` 边框。
### F4 毛巾架
墙上 `oak_fence`/`iron_bars` + `<色>_carpet`/`<色>_banner` 当毛巾。

---

## G. 书架 / 书房 / 工作台

- **书架墙**: 整排 `bookshelf` 或 `chiseled_bookshelf`(可显示书), 顶上一圈 `oak_slab`/`oak_stairs` 收边。
- **书桌**: 见 B3; 桌面摆 `lectern`(放书)、`frame`(挂地图)、`candle`。
- **工作间**: `crafting_table` / `smithing_table` / `stonecutter_block` / `grindstone` / `anvil` / `loom` / `cartography_table`
  沿墙排开, 墙上 `frame` 挂工具, `barrel` 装材料, 地面 `iron_bars` 做笼/架。
- **展示架/酒架**: `iron_bars` 或 `chain` 做隔层 + `frame` 摆瓶(用染色玻璃/药水当酒瓶)。

---

## H. 壁炉

```
fill <x1> <y-1> <z> <x2> <y+2> <z> stonebrick        # 炉体
fill <x> <y> <z> <x> <y+1> <z> air                     # 掏空炉膛
setblock <x> <y-1> <z> campfire ["extinguished"=false]  # 火
setblock <x> <y+2> <z> stone_brick_slab                 # 壁炉台
# 台上摆 candelabra: 两条 fence + 蜡烛
```
> 烟囱向上打通到屋顶; 灵魂营火=蓝色火, 更冷调。

---

## I. 灯光与灯具(详见 `palette-light.md`)

- **吊灯**: 天花板下挂 `chain`(1~3 格), 底端 `lantern`; 华丽的用 `end_rod` + 四角 `lantern`。
- **壁灯**: 墙上 `torch`(暖) / `soul_torch`(冷); 或用 `lantern` 挂在方块/`trapdoor` 下。
- **落地灯**: `oak_fence` 杆 + 顶 `end_rod` 或 `lantern`。
- **烛台**: 两条 `oak_fence` + `candle`(可多根 `candles` 状态)。
- **隐藏光灯**: 地板/墙/天花埋 `glowstone`/`shroomlight`/`sea_lantern`/`ochre_froglight`, 上面盖 `*_carpet`(透光)或半砖。
- **隐形光**: `setblock <x> <y> <z> light_block ["block_light_level"=15]`(完全看不见, 补暗角神器, 但玩家可能看不见触发不了红石)。

---

## J. 植物与绿植

- **盆栽**: `flower_pot`(内容状态实测) 或 `barrel`/`decorated_pot` 里插 `bamboo`/`fern`。
- **绿墙**: `vine` + `moss_block` + `azalea`/`flowering_azalea` 贴墙, 地上 `moss_carpet`。
- **垂吊**: 天花板挂 `hanging_roots` / `glow_lichen` / `big_dripleaf`, 或 `chain` + `vine`。
- **庭院树**: 室内角落放 `spruce_log` + 树苗装饰, 或直接用 `azalea_leaves_flowered` 做小树。

---

## K. 墙面装饰与软装

- **画/展示框**: `painting`(随机图案)、`frame`/`glow_frame`(放地图/武器/唱片) 挂墙。
- **旗帜**: `wall_banner` 挂墙, `standing_banner` 立地; 可当窗帘/隔断/床幔。
- **窗帘**: 门框两侧挂 `wall_banner` 或一列 `<色>_wool`/`carpet`。
- **地毯**: `*_carpet` 拼区; 图案地板用两种方块 `fill` 交替(棋盘/条纹/回字)。
- **护墙板**: 下半墙换深色木材/石砖, 顶上压一条 `slab` 或 `trapdoor` 当腰线; 上部浅色。
- **天花**: 木梁用 `<木>_log`(axis 顺梁方向) 跨顶, 之间铺浅色板; 吊顶可下沉 1 格藏灯。
- **踢脚线**: 墙脚一圈 `oak_slab` 或 `trapdoor`。
- **盔甲架** `armor_stand` 当衣架/门卫/模特。

---

## L. 杂物与生活气息(最重要的一步)

空荡是内饰最大的敌人。摆完家具后随手补:

- 桌上: `cake`、面包/苹果(用 `frame`)、`flower_pot`、`<色>_candle`、散落的 `book`(讲台上)。
- 地上: `<色>_carpet` 小毯、`barrel` 当收纳、`hay_block` 当坐垫、`web` 蛛网角落。
- 墙上: `frame` 挂地图/工具/食物、`flower_pot` 挂墙(状态)、`sign` 写标签。
- 角落: `decorated_pot`、`cauldron`(接雨/杂物)、`composter`(厨余)、`grindstone`。
- 光线: 关掉过于均匀的照明, 留一处暗角用蜡烛/灵魂灯打氛围。

> 一句话: **家具(硬) + 软装(软) + 一点杂物(乱) + 层次灯光 = 有人住过的感觉。**
