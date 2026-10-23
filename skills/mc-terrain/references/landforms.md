# 地貌造法(山 / 崖 / 谷 / 水 / 岸 / 火山)

配套 `SKILL.md` §4。每个地貌: **造型法则 → 分层材质 → 步骤/命令 → 收边细节**。
ID 以 `find_items` 为准; 常见: `grass_block` `dirt` `podzol` `mud` `gravel` `sand` `clay` `stone`
`cobblestone` `andesite` `granite` `diorite` `deepslate` `tuff` `calcite` `dripstone_block` `basalt`
`blackstone` `magma` `obsidian` `moss_block` `snow_layer` `ice`。

---

## 1. 山脉 / 丘陵

**法则**: 2~3 个主峰, 峰间有鞍部; 主坡 1:1.5~1:2; 山脊线弯曲; 从下到上草→土→石→(雪)。

**步骤**:
1. 定峰位(错开, 别排成一行)与峰高(主峰 h, 次峰 0.5~0.7h)。
2. 用**分层等高线**: 每升高 1~2 格, 用一个不规则闭合曲线(在 `mc-build` 圆上扰动)圈范围, 层层收缩。
3. 相邻层之间用半砖/楼梯接坡(见 `SKILL.md` §3)。
4. 铺材质: 山脚 `grass_block`+`dirt`; 山腰陡处露 `stone`/`andesite`/`tuff`; 山顶 `stone`+`gravel`,
   很高再盖 `snow_layer`。
5. 收边: 山脊加孤石、崖坎、灌木; 坡上散落碎石(`cobblestone`/`andesite` 单块)。

**命令片段**:
```
fill <x1> <y> <z1> <x2> <y> <z2> stone            # 某层台面
setblock <x> <y> <z> stone                        # 每层轮廓用曲线点生成(见 mc-build)
```

## 2. 悬崖 / 崖壁

**法则**: 垂直面**分层**——最上 1~2 格草/土盖帽, 往下多层岩石**深浅交错**; 崖面**凹凸**(有进有出)、
有**竖向裂缝**、有**突出岩块**和**小悬挑**。

**步骤**:
1. 先切出垂直崖面(直线太假 → 让崖线弯, 用曲线)。
2. 岩层: 每 2~4 格高换一种近似石色(如 `deepslate`→`cobblestone`→`andesite`→`tuff`), 层间有起伏。
3. 凹凸: 局部往里退 1 格(`fill ... air`), 局部往外凸 1 格; 加 1~3 格的**竖向凹槽**(裂缝)。
4. 突出: 在崖面挂几块**悬挑岩**(下方用台阶倒扣做支撑错觉)。
5. 崖脚: 堆**碎石坡**(`cobblestone`/`gravel`/`andesite` 单块, 从下往上越来越小)。
6. 崖顶边缘: 草皮盖帽 + 灌木/枯树, 边缘破碎。

> 崖壁不需要"看起来能爬", 但**要有层次和破面**, 一整片纯色光面 = 最假。

## 3. 河谷 / 峡谷

- **河谷**: 谷底宽而平(河床 + 河漫滩), 两坡缓; 沿等高线做阶地(一层一层的平地)。
- **峡谷**: 谷底窄(几格), 两壁**近乎垂直**, 顶部比底部略宽或略窄(上宽=风化, 上窄=险峻)。
- 底部铺 `gravel`/`sand`/`clay`(水冲积), 侧壁露岩层; 谷中放河/溪(见 `water-road.md`)。
- 收边: 谷壁的凹龛、倒木、藤蔓、谷口堆积扇。

## 4. 洞穴口 / 地下入口

- 在崖壁/山坡挖一个**拱形洞口**(用 `mc-build` 半圆), 洞口内收 1 格做阴影。
- 洞口上方崖壁突出作"眉", 洞内壁用 `deepslate`/`cobblestone`, 深处放 `glow_lichen`/`light_block` 微光。
- 洞口堆碎石、断木, 长苔藓/藤蔓。矿洞口加木支撑门框(`*_log` + `<木>_planks`)。

## 5. 湖泊 / 池塘

**法则**: 碗形底、岸线不规则、水下有地形、岸边有植被。

**步骤**:
1. 用 `mc-build` 画一个**不规则圆/椭圆**(在弧线上随机加减 1~2 格)作为岸线。
2. 从岸线向内、向下用逐层缩小的同心轮廓挖出**碗形**, 深 2~4 格。
3. 底铺: 中间 `sand`/`clay`/`mud`, 靠岸 `gravel`(浅滩)。
4. 注水: `fill <x1> <water_y> <z1> <x2> <water_y> <z2> water`, 只填**最上层**即可(下层有水源会保持),
   或整片填水更保险; 岸要封实防漏。
5. 岸线: 用 `grass_block`/`moss_block`/`gravel`/`dirt` 混合, 随机凹凸; 陡岸加石。
6. 植被: 岸边 `sugar_cane`、水面 `waterlily`(睡莲)、水下 `seagrass`/`kelp`/`sea_pickle`。
7. 细节: 倒木(斜插的 `*_log`)、荷叶、芦苇、萤火(隐藏光源)。

## 6. 海岸 / 沙滩

- **渐变**: 内陆草土 → 沙(`sand`) → 湿沙/砾石(`gravel`) → 海(`water`)。
- **岸线弯曲**: 岬角(伸出的岩/沙)、海湾(内凹), 别一条直线。
- **潮间带**: 靠水线铺更深色的沙/砾, 制造"湿"的错觉。
- **礁石**: 海里散落 `stone`/`andesite`/`prismarine` 小块; 潮池(小水坑 + `sea_pickle`/珊瑚)。
- **沙丘后方**: 稀疏草、`short_grass`、棕榈。

## 7. 沙丘 / 沙漠

- **风成波形**: 一系列**新月形**沙丘, 迎风坡**缓**、背风坡**陡**(用 `sand` 铺缓坡, 背风直接垂直断)。
- 层理: 不同深浅的沙色(`sand` + `sandstone` 暴露层)交替。
- 点缀: 仙人掌(`cactus`)、枯灌木、砂岩露头(`sandstone`/`red_sandstone`)、绿洲(小水池 + 棕榈)。
- 收边: 沙与石/土的过渡要糙, 别一条平滑曲线。

## 8. 沼泽

- 泥 + 浅水交织: `mud`/`mud_bricks`(干处)、浅水坑、`moss_block`/`moss_carpet`(湿苔)。
- 植被: 枯萎感 —— 深色 `*_leaves`、枯树、`brown_mushroom`/`red_mushroom`、藤蔓、`seagrass`。
- 水色偏绿(用 `moss_block`/`kelp`/`seagrass` 营造); 气泡柱(`magma` + 水? 或 `soul_sand` 做上升气泡)当沼气。
- 半沉没的倒木、树桩。氛围阴暗潮湿。

## 9. 火山 / 雪原 / 冰

- **火山**: 主体 `basalt`/`blackstone`/`deepslate`, 山顶火山口(凹陷 + `magma`/`lava` 池),
  熔岩流 = `magma`/`blackstone` 蜿蜒从口流下(冷却的熔岩), 火山灰坡 = `blackstone`/`basalt` 渐变。
  点缀 `magma` 发光、`obsidian` 黑曜石。**别大面积真 lava**(会流、会烧、卡)。
- **雪原**: 从下到上 `grass_block`(带雪?)→ `snow_layer`(逐层 1~7 高) → 山顶 `snow_layer` 满层 + `ice`。
  雪用 `snow_layer` 做**高度渐变**最自然(不是满格 `snow`)。结冰水面用 `ice`/`packed_ice`/`blue_ice` 分层。
- **冰川**: `blue_ice` 做冰舌, 边缘 `packed_ice`/`ice`; 裂缝用深色 `ice`。
- 雪面要**微微起伏 + 露出岩石/树梢**, 全白一片会失去层次。

---

## 通用收边细节(做完地貌补这些)

- **碎石**: `cobblestone`/`gravel`/`andesite` 单块, 从陡处"滚"到坡脚, 由密到疏。
- **倒木 / 树桩**: 斜插或截断的 `*_log`。
- **藤蔓 / 苔藓**: 待在崖壁阴面、石缝、水边(`vine`/`glow_lichen`/`moss_carpet`)。
- **残株 / 断枝 / 骨**: 打碎人工痕迹。
- **光**: 地缝/水边埋隐藏光源(`mc-interior` 的隐藏光技巧), 让暗处有微光但不突兀。
- **不留直线**: 最后绕一圈, 把所有笔直的边都用随机 1~2 格凹凸破掉。
