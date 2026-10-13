# 内饰专家规则与扩充配方

配套 `SKILL.md`。以下是从公开 Wiki 家具教程、Grian 技巧汇总、室内设计指南与社区家具合集提炼的**可执行惯例**。
个别透光/贴面行为与具体 Bedrock 状态未逐条二次验证，落地以游戏内 `get_block` 与实机观感为准。

## 1. 三条总纲

1. **深度 > 颜色**：墙面至少结构层 + 填充层 + 细节层。家具先用楼梯/半砖/栅栏做出可读剪影，再谈配色。
2. **一处一焦点**：壁炉、床、大窗、书架墙或主灯先定，家具围绕焦点布置，动线朝向焦点。
3. **只有家具不算有人住**：每个空间至少补 3 件"无用但合理"的杂物，但总杂物面积 <20%，成组、不堵路。

## 2. 扩充家具配方

### 客厅 / 餐厅
- 基础沙发：同材质 `stairs` 并排作座，两端上放 `slab` 作扶手；靠背用后排 `stairs` 或竖排 `trapdoor`。
- 转角沙发：两排 `stairs` 成 L，转角放 `slab`，两端 `slab` 收边。
- 小圆桌：`fence` ×1 + 顶部同材质 `pressure_plate`；方桌：四角 `fence` + 2×2 `slab`/`carpet`。
- 咖啡桌：2×1/2×2 `trapdoor` 平放，下方四角 `sign`；现代矮桌用黑白 `carpet` 2×2。
- 电视柜：倒置 `stairs` 一排 + `pressure_plate` 台面；墙面 `black_concrete`/`black_stained_glass_pane` + `frame` 模拟屏幕。
- 书架墙：`bookshelf`/`chiseled_bookshelf` 满墙，每 3~4 格插空一格放 `flower_pot`/`lantern`；间隔放 `ladder`。
- 展示柜：`glass_pane` 围 1 格，内放 `armor_stand` 或 `flower_pot`。
- 餐桌：`slab` 一排 3~6 格 + `fence`/`sign` 腿，两侧 `stairs` 椅；桌面中央 `flower_pot`，两端 `candle`。
- 餐边柜：靠墙 `barrel` ×3 + 上方 `slab` 台面 + 墙面竖排 `trapdoor` 作吊柜。
- 吧台：倒置 `stairs`/`slab` 作台，外侧 `fence` + `pressure_plate` 吧凳。
- 吊灯：桌上方 `chain` 1~2 格 + `lantern`；华丽款用 `fence` 灯架 + 四角 `candle`。

### 厨房
- 底柜：`barrel`/`chest` 一排 + 正面 `trapdoor` 柜门 + 顶层 `slab` 台面；下沿贴 `button` 作把手。
- 吊柜：墙面 y+3 处贴一排 `trapdoor`，或包住 `barrel` 侧面。
- 炉灶真功能：`furnace` + 顶部平放 `trapdoor` + 侧面 `button`。
- 装饰炉灶：`iron_block`/`smooth_stone` ×1 + 顶部四 `button` + 正面 `trapdoor`；上方用铁活板门/平滑石半砖做抽油烟机。
- 冰箱：2 格高 `quartz_block`/`iron_block`/`white_concrete` + 正面 2 个 `iron_door` 或 `iron_trapdoor` + 顶部 `pressure_plate`。
- 微波炉：台面 `quartz_block` + 正面 `frame` + 顶部 `button`；小家电用 `cauldron`/`flower_pot` + `button`。
- 水槽：台面换 `cauldron` 装水，墙面 `trapdoor` 作水龙头；台面连续 ≥3 格。
- 中岛：3×2 `slab` 台面 + 下体 `barrel`/`trapdoor`，外围 `fence` 或吧凳。
- 厨房三角：灶台、水槽、储物三点距离各 2~4 格，操作台连续 ≥3 格。

### 卧室 / 书房
- 床头板：床头墙竖排 2~3 格 `trapdoor`，中央 `frame` 或 `button`；两侧 `carpet` 作床品延伸。
- 四柱床：床四角 `fence`/`log` 升到 y+3，顶盖 2×2 `slab`/`carpet`，四角挂 `banner` 或 `vine`，顶内藏灯。
- 上下铺：两张床垂直叠，靠墙侧 `ladder`，床脚 `trapdoor` 挡板。
- 床头柜：`barrel`/`chest` + 顶部 `slab`/`pressure_plate`，放 `candle`、`flower_pot`、`clock`。
- 衣柜：2×1×3 `barrel`/深色木门组合，顶部 `slab`；或 `armor_stand` + `trapdoor` 开口柜。
- 书桌：`slab` 台面 + `sign` 腿，桌面 `lectern`，上面盖 2 个 `trapdoor` 作摊开的书。
- 转椅：`stairs`/`slab` + 底部一圈 `trapdoor`；书架墙间隔 `ladder` 与 `lantern`。

### 卫浴 / 壁炉
- 马桶：靠墙空 `cauldron` + 后方竖 `trapdoor` 水箱 + 顶部铁 `pressure_plate`，墙面 `button` 冲水。
- 洗手台：`slab` 台面 + `cauldron` 面盆，墙 `glass_pane` 镜子，旁边 `trapdoor` 柜。
- 浴缸：2×3/3×4 区域四周 `slab` 围边，内部水；四角竖 `trapdoor`，旁边 `cauldron` + `button`。
- 淋浴：1×1 角落，顶部平放 `trapdoor` 花洒，三面 `glass_pane` 围合，地面 `cauldron` 或地垫。
- 现代壁炉：墙洞 1×2 放 `campfire`，洞口用铁 `trapdoor` 半遮，边框石砖/深板岩。
- 隐藏营火：`campfire` 上方盖 `hopper`，烟可过、火焰不明显，四周 `stairs` 收边。
- 古典壁炉：2×3/3×3 石砖包边，内部 `campfire`/`soul_campfire`，顶部外挑 1 格 `slab` 作壁炉台。
- 烟囱：石砖/圆石垒 3~5 格到屋顶，顶端再放 `campfire` 做更长烟柱。

### 灯具与软装
- 落地灯：`fence` + 顶部 `sea_lantern`/`lantern`；台灯用 `end_rod`/`candle` + `trapdoor` 灯罩。
- 纸灯：白色羊毛/白色染色玻璃板包隐藏光源，或用 `chain` 吊 `lantern`。
- 盆栽：`flower_pot`、`barrel`、`decorated_pot`；绿墙 `vine + moss_block + azalea`；垂吊 `hanging_roots`/`glow_lichen`。
- 照片墙：走廊/楼梯间 `frame` 5~9 个错落排，地图/画/物品混用。
- 宠物角：`carpet` + `bowl` + 骨头 + `<色>_wool` 围 2 格小窝。

## 3. 灯光硬指标与藏灯

- 敌对生物在光照等级 0 生成；室内任意可站方块目标 ≥7，最低不得为 0。
- 常见亮度：火把/灯笼/营火 14；荧石/海晶灯/红石灯 15；灵魂火把/灯笼/营火 10；蜡烛每根 3，最多 12。
- 光每格衰减 1；灯笼间距 ≤10 格，灵魂灯 ≤7 格，水中再额外 -3/格，水景灯距减半。
- 主灯每房 1 处；功能灯在工作区/床头/镜前；氛围灯低频放在书架、壁炉、展柜、地面洗墙。
- 房间至少 3 处光源且高度不同；全屋顶光均匀会像手术室。
- 藏灯法：地毯下、半砖下、树叶中、画后、活板门后、家具背后、吊顶灯带、水景底灯。地毯/玻璃/半砖等透明或特殊方块是否挡光应以实机版本实测；不透明全方块一定会截光。

## 4. 配色、地板、墙面、吊顶

- 60-30-10：主色 60、次色 30、强调 10；色相 ≤2，总材质 3~5。
- 同色系渐变优先：橡木/云杉/白桦/白羊毛；现代白/黑/深灰/玻璃；中世纪深橡木/云杉/石砖/红地毯；日式竹/樱花木/白/红。
- 每个房间至少一组"粗糙 vs 平滑"对比，如圆石 vs 石英、原木 vs 木板。
- 地板：纯色木、2 格棋盘、2×2 拼花、深色边框、楼梯/半砖地台；地毯叠层，边缘别与墙完全齐平。
- 墙裙：下 1~2 格深木/石砖，顶压 `slab`，上部浅色；每 3~5 格立原木或做 1 格深壁龛。
- 吊顶：每 3~4 格一根原木梁；局部下降 1 格藏灯；天花板通常比地板深 1 档。
- 窗户：四周 `stairs` 倒角，窗台 `slab` 外挑，两侧 `banner` 或上方 `trapdoor` 作窗帘。

## 5. 布局与生活气息

- 一间房一个主功能 + 一个焦点；门打开后第一眼看到完整对景，别正对床尾/桌背。
- 餐厅地毯区、客厅地毯区、吊顶边界可代替隔墙；小户型用单人沙发、半砖桌、墙面收纳、借光。
- 生活气息密度：每房 ≥3 件杂物；厨房台面 ≥2 件小物 + 1 面钟；客厅书架留 2~3 空格；卧室床尾放 1 件"刚脱下"的装备；玄关补鞋、伞架、挂钩。
- 植物每房 ≥1 盆，窗边 3 盆成组；大空间角落放 1 棵室内树。
- "使用中"痕迹：讲台摊开的书、壁炉明火、炼药锅中的碗、书架间的灯笼、桌面蛋糕与蜡烛。
- 杂物只贴墙、贴桌、贴地面，成 3 件一组；不悬空、不撒胡椒面、不阻断门扇扫掠格。

## 6. 交付自检

- [ ] 每面墙有 ≥3 层材质/凹凸，不是平墙 + 平板地板。
- [ ] 门能开、主通道 ≥2、拉椅空间 ≥1。
- [ ] 主色/辅色/强调符合 60-30-10，总材质 ≤5。
- [ ] 家具高度正确：桌 0.5~1.5，座 0.5~1，床和柜不悬空。
- [ ] 焦点清晰，家具成组，不沿墙摆一圈。
- [ ] 每房 ≥3 件杂物、≥1 盆植物，杂物 <20%。
- [ ] 至少 3 处、3 个高度的光源；所有可站方块光照 ≥1，最好 ≥7。
- [ ] 厨房/卫浴材质分区正确，窗洞和门洞有收边。
- [ ] 地毯不压半砖；楼梯朝向、活板门开合/半砖上下已 `get_block` 抽检。
