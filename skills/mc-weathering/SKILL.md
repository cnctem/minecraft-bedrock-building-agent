---
name: mc-weathering
description: 做旧与细节手册——给建筑、废墟、遗迹、室内、场景添加合理的风化、裂纹、苔藓、藤蔓、磨损、修补痕迹、生活道具与叙事细节，避免"全新塑料感"和随机撒杂色。玩家要求做旧、废墟化、遗迹化、破败感、年代感、生活气息、增加细节，或说"太新""太空""没有故事"时加载。
---

# 做旧与细节手册(风化 / 损伤 / 叙事)

做旧不是把方块随机换色，而是让表面留下**环境、时间和使用者的证据**。
每次先问四件事：**这是什么建筑？暴露在哪？谁在用？发生了什么？** 四个答案决定风化方向。

## 0. 四层做旧法

1. **结构层**：先保证承重线完整。柱、梁、拱、屋顶可以破损，但不能全部断掉。
2. **表面层**：按暴露位置换材质，控制杂色、裂纹、苔藓、铜绿。
3. **损伤层**：开洞、缺块、塌角、断梁、碎裂瓦片；损伤必须集中在受力点/雨水线/人流线。
4. **叙事层**：补丁、脚手架、杂物、旧灯、堆货、断枝、洪水线，让玩家读出时间。

> 顺序固定：`结构 → 表面风化 → 损伤 → 修补痕迹 → 道具与植被`。先做道具会在大改时全部返工。

## 1. 风化预算(防花防脏)

- 普通使用中的建筑：风化材质 10%~20%，只做基座、檐口、背阴面和交通线。
- 老旧建筑：20%~35%，增加裂纹、缺块和修补痕迹。
- 废墟：35%~60%，保留 1~2 条清晰结构主线；不是全图噪声。
- 单一变体 `cracked_*` / `mossy_*` 占同族材质 ≤20%。
- 任意 10×10 区域内，藤蔓/苔藓/断枝等特殊细节 ≤15%。
- 藤蔓 1 处/3~5 格墙长，垂 2~4 格；苔藓成 3~7 格团，禁止单格孤立点。
- 生活道具密度：每 5×5 功能区 1~2 件小物；门口/桌面/墙角优先。
- 小建筑总细节上限：每 10 格立面不超过 3 个视觉焦点。

## 2. 材质风化配方

| 材质族 | 少量风化 | 中度风化 | 重度/废墟 |
|---|---|---|---|
| 石砌 | `stonebrick` + `stonebrick["stone_brick_type"="cracked"]` | `cobblestone` + `mossy_cobblestone` + `andesite` | `deepslate` + `cobbled_deepslate` + `gravel` |
| 砖墙 | `brick_block` + `granite` | `brick_block` + `stonebrick["stone_brick_type"="cracked"]` | `deepslate_bricks` + `tuff_bricks` + `mossy_cobblestone` |
| 木材 | `<木>_planks` + `stripped_log` | `<木>_planks` + `trapdoor` + `fence` | `dark_oak_planks` + `air` 缺口 + `dirt["dirt_type"="coarse"]` |
| 屋顶 | 主瓦 + 10% 深色变体 | `mossy_cobblestone` + `vine` + 缺瓦 | 露梁 + `moss_block` + 落叶 + 破口 |
| 铜/金属 | 原铜 + 1 阶氧化 | 2~3 阶氧化 + `copper_grate` | 全氧化 + 铁栏杆 + 锈水痕 |
| 沙岩/土坯 | `sandstone` + `sandstone["sand_stone_type"="cut"]` | `sandstone` 缺角 + `sand` 堆 | `terracotta` + `granite` + 裂口 |
| 柔软物 | 地毯磨损角 | 多色旧地毯 + 补丁 | 破布感 `white_wool` + `carpet` 拼块 |

- 石系渐变链：`stone → andesite → tuff → cobblestone → mossy_cobblestone → stonebrick → stonebrick["stone_brick_type"="cracked"] → deepslate → cobbled_deepslate → blackstone`。
- 暖木链：`oak_planks → spruce_planks → stripped_spruce_log → dark_oak_planks → dark_oak_log`。
- 铜绿链：`copper_block → exposed_copper → weathered_copper → oxidized_copper`；同一面墙按 2~3 段混，不是整面一次氧化。
- 湿区优先用 `moss_block`、`moss_carpet`、`vine`、`clay`；干区用 `dirt["dirt_type"="coarse"]`、`gravel`、`cracked_*`。

## 3. 损伤语法

- **雨水线**：墙脚 1~2 层更深更糙；檐口下方、窗台下方、门洞两侧加污渍/裂纹。
- **受力损伤**：裂纹从门洞上角、梁端、拱脚、墙角开始，不要凭空出现在大墙中央。
- **结构暴露**：先移除屋瓦/外墙 1~3 格，再补露出的梁、椽、柱；露结构必须有连续性。
- **塌角**：选择一角/一侧，从顶部向下 2~5 格逐层退，底部堆 rubble；不要四面同时塌。
- **缺窗**：玻璃留 1~2 格缺口，边缘用 `iron_bars`/`trapdoor`/木条；破口周围加少量碎石。
- **火烧**：近火源换 `cracked_deepslate_bricks`/`blackstone`/`deepslate_tiles`，上方加 `campfire` 烟痕；木质保留焦黑边缘。
- **洪水/潮湿**：水线以下石头加深、苔藓加密，木结构改 `dark_oak`/mud；水生植物只放水边。
- 先保留结构线，再破坏 1~2 个局部。**空、断、塌三选一，不要同时全塞。**

## 4. 修补与时间痕迹

- 补墙用不同批次材料：新 `stonebrick` 补旧 `cobblestone`，接缝留 1 格 `cracked_*`。
- 门洞用横木板/木板条封 1~3 格；旁边放 `ladder`、`scaffolding`、`fence` 做施工痕迹。
- 屋顶补瓦用不同深浅；补丁占屋面 5%~15%，不要补成棋盘。
- 修复柱外包一圈 `log`/`stonebrick`，保留内部破损；新旧材质差异就是故事。
- 道路车辙/门槛磨痕沿人流线：每 10~15 格一处 `dirt["dirt_type"="coarse"]`/`gravel`/深色 path。
- 废墟中保留 1 条清晰可读的旧路/墙基，玩家才能看出原来是什么。

## 5. 细节与生活道具

- 生命感来自"刚被使用过"：半开的门、亮着的灯、桌上食物、炉中火、晾衣、堆货、脚印旁的工具。
- 功能细节：灯、招牌、栅栏、楼梯、排水沟、烟囱、储物、工作台、座椅、花盆。
- 故事细节：破车、断桥、遗弃营火、散落书页、捆绑原木、集市摊、祭坛、墓碑、警告牌。
- 用组合而不是单块：`barrel + trapdoor + lantern` 是柜台，`fence + pressure_plate` 是小桌，`log + rail` 是货物，`lectern + trapdoor` 是摊开的书。
- 门口/窗边/转角优先；大墙中央只放一个焦点，不要满墙挂件。

详细材质、损伤与修补配方见 **`references/aging.md`**；道具清单、密度和场景故事模板见 **`references/details.md`**。

## 6. 落地流程

1. `get_slice` 读原结构与材质、`get_heightmap` 看地坪高差；`get_player_position` 定观察方向，先远看轮廓。
2. 用 `find_items` 找同族旧化方块，先做 3×3 小样确认颜色层级。
3. `pin_region` 覆盖施工面；表面换色用 `fill ... replace`，局部损伤用 `setblock`。
4. 大面积杂色/补丁/碎石用 `ptc` 批量提交 `run_server_command`；保存原结构线，不要用一次 `fill` 全墙换色。
5. 先做损伤，再加修补，再放道具，最后补藤蔓/苔藓/灯。
6. `inspect_region` 抽检：结构线连续、无单格苔藓、无悬空藤蔓、无堵路、无过度杂色。

## 7. 坑清单

- 随机满墙杂色 → 像噪点，不像风化；只沿暴露/受力/人流线分布。
- 苔藓单格孤立、藤蔓整墙满铺 → 成团、成簇、限高。
- 结构全断还叫废墟 → 先保留 1~2 条承重主线。
- 新旧材质无过渡 → 接缝留 10%~20% 中间色或裂纹。
- 只做损坏不做修补 → 缺少时间故事；补丁和脚手架很重要。
- 生活道具堆成仓库 → 每个功能区 1~2 件，围绕真实用途摆放。
- 室内照搬室外做旧 → 室内重磨损、烟熏、旧布和收纳，少用大型塌方。
- 忘 `pin_region`、ID 凭记忆猜 → 区块卸载会失败，Bedrock ID 以 `find_items`/`get_block` 为准。
