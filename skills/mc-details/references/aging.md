# 风化、损伤与修补配方

配套 `SKILL.md` §2~§4。所有比例是社区建筑惯例，最终以实机观感和 Bedrock `find_items` 结果为准。

## 1. 石材建筑

### 轻度老化
- 主材：`stonebrick` / `smooth_stone` / `andesite`。
- 辅材：`stonebrick["stone_brick_type"="cracked"]` 10%、`stonebrick["stone_brick_type"="mossy"]` 5%~10%、`gravel` 点缀。
- 位置：墙脚 1 格、檐口下沿、窗台下方、背阴面。
- 裂纹从门窗上角或墙角向上斜 2~4 格，不横穿整面墙。

### 中度老化
- 主材保留 50%~60%，混 `cobblestone` 20%、`mossy_cobblestone` 15%、`andesite` 10%。
- 每 4~6 格墙面做 1~2 格缺口，缺口后填 `air` 或露 `spruce_log` 梁。
- 墙脚 2 层加深；台阶边缘换 `stonebrick["stone_brick_type"="cracked"]`。
- 苔藓成团 3~7 格，集中在墙脚、阴面、水边，不沿水平线铺满。

### 重度废墟
- 墙体只留原有高度的 30%~60%，保留至少一条完整转角或拱线。
- 上部逐层退 1~3 格形成塌角；底部 1~3 圈堆 `cobblestone + gravel + andesite`。
- 露梁：`spruce_log` / `dark_oak_log` 从墙内伸出 2~5 格，断口处不悬空。
- 地面撒 `dirt["dirt_type"="coarse"] + gravel + moss_block`，每 10×10 特殊块 ≤15%。

## 2. 木构与半木建筑

- 木墙旧化：`oak_planks` → `spruce_planks` → `stripped_spruce_log` → `dark_oak_planks`。
- 竖直承重柱保持完整；填充板随机缺 1~3 格，缺口后露 `cobblestone` 或深色木梁。
- 门窗下沿/门槛加 `trapdoor`、`slab` 补丁，模拟反复踩踏后的修补。
- 地板沿入口至主桌方向换 1 格 `dirt["dirt_type"="coarse"]`/深色木板做磨损路径，每 10~15 格重复一段。
- 屋顶缺瓦 5%~15%，缺瓦下必须有 `log` 椽；边缘挂 `vine` 2~4 格。
- 苔藓不乱铺木墙：只放墙脚石基、屋脊背阴侧和排水处。

## 3. 屋顶与檐口

- 主瓦 + 10%~15% 深色变体，每 4~6 格出现 1 处旧瓦/缺瓦。
- 屋脊端头和檐角优先破损；屋面中间保留完整，不撒胡椒面。
- 缺瓦处露梁：`spruce_log`/`dark_oak_log` 横铺 1 格，间隔 2~4 格。
- 苔藓集中在背阴坡、屋脊交界、排水口，3~7 格成团。
- 补瓦用不同深浅材质，补丁覆盖 5%~15%，形状取矩形或不规则 1~2 格。

## 4. 铜、铁与工业

- 铜四阶段：`copper_block` → `exposed_copper` → `weathered_copper` → `oxidized_copper`。
- 同一墙按 2~3 段混：迎水面氧化重，檐下和接缝轻；每段 4~8 格。
- `cut_copper`/`copper_grate` 可做维修板，和锈蚀铜形成新旧差。
- 铁件用 `iron_bars`、`chain`、`cauldron`、`hopper`；锈水痕用 `brown_terracotta`/`brown_concrete` 向下铺 2~5 格。
- 工业废墟：破窗格、外露管道、`observer`/`target` 当仪表、`redstone_lamp` 半亮、地上 `cobweb` 少许。

## 5. 沙岩、土坯与暖色建筑

- 主材 `sandstone` + `sandstone["sand_stone_type"="cut"]` + `sandstone["sand_stone_type"="smooth"]`；旧化混 `sand`、`terracotta`、`granite`。
- 缺角后填 `sand`，不要留下直角黑洞；墙脚堆 1~2 格沙丘。
- 裂缝中填 `brown_terracotta`/`orange_terracotta` 做风化层。
- 木梁用 `acacia_log`/`dark_oak_log`，断口加 `trapdoor` 或 `slab` 挡板。
- 干旱区少苔藓，改用 `dirt["dirt_type"="coarse"]`、`deadbush`、`gravel` 和风蚀缺口。

## 6. 损伤模板

### 门洞受力裂
- 门洞两侧上方各 1 格 `stonebrick["stone_brick_type"="cracked"]`。
- 裂缝向上斜走 2~4 格，每格左右交替 1 格。
- 顶部 1 格用 `slab`/`stairs` 补过梁，旁边放 1 根 `scaffolding`。

### 水线
- 水线以上 `stonebrick`，水线以下 `mossy_cobblestone`/`clay`。
- 水线处每 3~5 格 1 团 `moss_block`，上面向下挂 `vine` 1~3 格。
- 木桩入水段换 `dark_oak_log`/`mud`，再加 `moss_carpet`。

### 塌角
- 从角部顶端向两面各退 2~5 格。
- 每下降 1 层，缺口向内多收 1 格。
- 底部堆 2~3 层碎石，坡度不超过 1:2。
- 保留原角柱至少一格，玩家能读出原轮廓。

### 屋顶破洞
- 破口 2~4 格宽，边缘楼梯/半砖收口。
- 洞下露 1~2 根梁；梁下放 `air` 1~2 格形成阴影。
- 洞口边缘挂 `vine` 1~2 格，室内对应位置放 `cauldron` 接水或 `barrel` 收纳。

## 7. 修补痕迹

- 新石补旧石：`stonebrick` 补 `cobblestone`，交界放 `stonebrick["stone_brick_type"="cracked"]` 10%。
- 木板封窗：横板每格 1 块 `*_planks`，加 1 根 `fence` 斜撑。
- 临时支架：`scaffolding` 或 `log + fence` 放在破损侧 1~2 格。
- 补瓦：与主瓦不同色，占屋面 5%~15%，带 1 格 `slab` 收边。
- 修复后保留旧线：旧墙基、门框、窗洞轮廓至少保留一条。

## 8. 曝光方向与密度

- 背阴面：北/东面（或建筑被遮挡侧）优先苔藓、藤蔓、潮湿深色。
- 向阳面：裂缝、褪色、干裂、少苔藓。
- 迎风面：屋顶/墙角缺口、沙尘、裸岩。
- 水边：水线、苔、芦苇、湿木、倒木。
- 人流线：门槛、台阶中间、转角、柜台前加磨损和修补。
- 任意 10×10 区域：特殊风化块 ≤15%；同族裂纹 ≤20%。
