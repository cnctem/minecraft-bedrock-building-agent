# 细节、道具与场景叙事

配套 `SKILL.md` §5。细节不是越多越好，而是让每个功能区看起来**刚被使用过**。

## 1. 细节密度

- 每 5×5 功能区：1~2 件小物 + 1 个主视觉。
- 每 10 格立面：不超过 3 个视觉焦点；大墙中央只放 1 个。
- 每个房间/庭院：至少 1 件光源、1 件储物、1 件"使用痕迹"。
- 任意 10×10 地面：特殊道具 ≤15%，不要让每格都放东西。
- 道具成组摆 3 件或围绕一个功能区摆，禁止均匀散点。

## 2. 功能细节

| 功能 | 组合 |
|---|---|
| 照明 | `chain + lantern`、`fence + lantern`、`end_rod + lantern`、`candle` |
| 储物 | `barrel` 堆、`chest + trapdoor`、`bookshelf`、`frame` 标签 |
| 工作 | `crafting_table`、`anvil`、`smithing_table`、`grindstone`、`lectern` |
| 运输 | `rail`、`minecart`、`boat`、`barrel`、`hay_block` |
| 道路 | `grass_path`、`gravel`、`dirt["dirt_type"="coarse"]`、`stone_slab` |
| 排水 | `cauldron`、`hopper`、`chain`、`trapdoor` 水槽 |
| 座椅 | `stairs`、`slab`、`fence + pressure_plate` |
| 餐桌 | `slab` 桌 + `fence` 腿 + `flower_pot`/`cake`/`candle` |

## 3. 生活痕迹

- 门半开、灯亮着、壁炉有余火、书摊在讲台上、杯盘留在桌面。
- 门口放 1~2 个 `barrel`/`composter`/`hay_block`，旁边加 `scaffolding`。
- 晾衣：`fence` 横杆 + `carpet`/`banner`/`trapdoor`。
- 货物：`log` 堆上横 `rail`；`barrel + chest` 围成货堆；`hay_block` 成捆。
- 餐桌：`flower_pot` + `cake` + `candle`/`pressure_plate` 餐盘。
- 桌面：`lectern` + 2 个 `trapdoor` 作摊开的书；`cauldron + button` 作打字机。
- 磨痕：门口、走廊、柜台前用 `dirt["dirt_type"="coarse"]`/深色 `grass_path` 局部替换。
- 烟痕：烟囱顶/底各放 `campfire`；厨房墙上加 `blackstone`/深色砖 1~3 格。

## 4. 故事道具

### 废弃营地
- 1 个破帐篷：`white_wool` + `spruce_trapdoor`。
- 1 个半灭 `campfire`，周围 `barrel`、`chest`、`crafting_table`。
- 地面 `dirt["dirt_type"="coarse"]`、`gravel`、散落 `stick`/`bone`（展示框）。

### 旧集市
- 摊位：`fence` 柱 + `trapdoor` 台面 + `<色>_carpet` 顶棚。
- 货架：`barrel` + `chest` + `frame`；悬挂 `lantern` 每 4~6 格。
- 地面补丁：`grass_path` + `dirt["dirt_type"="coarse"]`，摊位下 1 格深色。

### 废墟庄园
- 保留大门轴线、旧墙基、壁炉和 1 条楼梯主线。
- 破屋顶露 1~2 根梁，房间内 `cobweb` 1~2 处。
- 新补丁用 `stonebrick` 补旧 `cobblestone`，旁边放 `scaffolding`。
- 花园让 `vine`/`moss_block` 从墙脚向建筑侵入 1~3 格。

### 工业遗址
- 破窗格 + 外露 `chain`/`iron_bars` + `copper_grate`。
- 管道外露 1~2 格，端头 `hopper`/`cauldron` 做机件。
- `redstone_lamp` 少量发光、`target` 当仪表、地面油污用 `blackstone`/`deepslate_tiles`。

## 5. 植被做旧

- 藤蔓从墙脚/檐口/裂缝开始，1 处/3~5 格，垂 2~4 格，成簇不成墙。
- 苔藓 3~7 格成团，水边 40%+，背阴 15%~30%，向阳少。
- 屋顶草皮只出现在背阴坡和排水口，地面用 `moss_carpet`/`short_grass` 少量点缀。
- 倒木斜插地面，断口用 `stripped_log`；周围 1~2 格 `dirt["dirt_type"="coarse"]`。
- 禁止悬空藤蔓、单格苔藓、浮空落叶和堵门灌木。

## 6. 按场景控制强度

| 场景 | 风化 | 损伤 | 修补 | 道具 |
|---|---:|---:|---:|---:|
| 使用中的民居 | 10%~20% | 0~5% | 5%~10% | 每功能区 1~2 |
| 老宅/旧商铺 | 20%~35% | 5%~15% | 10%~20% | 每区 2~3 |
| 废墟/遗迹 | 35%~60% | 20%~40% | 0~10% | 成组、稀疏 |
| 现代建筑 | 5%~10% | 0~3% | 0~5% | 功能为主 |
| 奇幻废墟 | 30%~50% | 15%~30% | 0~10% | 发光植物/祭坛 |

## 7. 细节交付自检

- [ ] 结构主线仍在，破损不违反基本受力。
- [ ] 风化集中在暴露、受力、人流、水线位置。
- [ ] 裂纹 ≤20%，特殊装饰 ≤15%，藤蔓不成墙。
- [ ] 每处破损都有碎石/阴影/修补至少一种收尾。
- [ ] 道具围绕功能组摆，不堵门、不堵路、不悬空。
- [ ] 至少留下一处"谁来过、发生了什么"的可读痕迹。
- [ ] 室内做旧偏使用痕迹，室外才做大面积结构和植被侵入。
