> 函数名两种写法都能用: `api.lib.chineseRoof(...)` 与 `api.lib.chinese_roof(...)`;
> 参数里的 `{...}` 是选项名清单, 在本项目里写成关键字参数(见 `api.lib.help("名字")`)。

# 大规模建造指导

大规模建造的函数库全景与硬规则: 选项写法、纪念性结构、装饰函数(含 **y 在最后一位**
的 7 个例外)、普通民居整套、预制风格库与**占地契约**、超大规模分区策略、
**建造正确性红线**(含“后写覆盖先写”“挖空必须显式写 air”)。

== 大规模函数库与内外饰参考（建造大型建筑前必读）==

★ 选项写法（全篇通用，动手写代码前先读这一段）
  函数签名里的 {...} 是**选项名清单**，只告诉你「有这几个键」，**不代表值是布尔量**。
  要传选项时必须写成「键: 值」，例如：
    ✔ gatehouse(x, y, z, x2, z2, 8, 'stone_bricks', {merlon: 'stone_bricks', towerH: 9, road: 'stone_brick_slab'})
  ① 凡是要写**方块/材质**的选项，值必须是**带引号的完整方块名**。常见方块类键：
     merlon / towerBlock / walkway / road / roof / cap / ceiling / floor / beam / pave / accent /
     inset / base / band / spire / glass / frame / sill / shutter / step / lantern / soil / flower /
     carpet / border / wood / bed / pillow / trim / doorBlock / chain / pole / bracket / post / gate /
     mat / top / footing / stone / wall / ridgeBlock / chimneyBlock / fenceBlock / lampPole / roadBlock …
     例：merlon: 'stone_bricks'、road: 'dirt_path'、cap: 'chiseled_quartz_block'。
  ② **绝不要给方块名选项写 true / false / 数字**。写 {merlon: true} 会被当成方块名 "true"，
     整片构件只能退化成「用主体材料补位」⇒ 材质错乱（垛口/马道/窗台突然变成怪材料的根因）。
  ③ 只有**真正的开关**才写 true / false：选项里的 door、smoke。注意 doorBlock 是方块名，别搞混。
  ④ 拿不准的键**宁可不写**，让它走缺省值 —— 缺省值一定是合理材质，瞎猜一定毁外观。

【一】纪念性结构函数（一条命令产出一个大型构件，大型建筑的主力积木）
amphitheater(cx, y, cz, outerR, tiers, tierH, block, {arena, accent, aisles}) 圆形剧场/斗兽场看台（层层升高的环形阶梯+中心场地+带壁柱外立面）
hypostyleHall(x1, y, z1, x2, z2, spacing, height, block, {cap, ceiling, beam, floor}) 柱厅（满堂柱网+柱头+井字主梁+天花，神庙内殿/大教堂中殿/宫殿大厅）
gatehouse(x1, y, z1, x2, z2, height, block, {towerH, towerR, towerBlock, merlon, road}) 城门楼（中央半圆拱通道+两端圆塔+垛口+顶面马道）
flyingButtress(x, y, z, span, height, facing, block) 飞扶壁（墩柱+斜撑拱，哥特教堂外支撑）
roseWindow(cx, y, cz, radius, frame, {glass, axis, spokes}) 玫瑰窗（同心环+放射辐条+彩窗玻璃）
cloister(cx, y, cz, innerHalf, corridorW, height, block, {floor, roof, pave, spacing}) 回廊内院（围廊柱列+内院+可选封顶）
keep(x, y, z, w, d, height, block, {towerR, towerBlock, merlon, roof}) 城堡主楼（空心墙+楼层+四角圆塔+双面垛口+可选坡顶）
steeple(cx, y, cz, width, height, block, {band, spire, bandEvery, belfry}) 教堂尖塔（方塔身+层带线脚+顶部空廊+收分尖顶+顶饰）
triumphalArch(cx, y, cz, span, height, thickness, facing, block, {accent}) 凯旋门（拱洞+壁柱+外挑檐口+铭文带+顶饰）
windowBand(x1, y, z1, x2, z2, height, wall, glass, {spacing, width}) 立面窗带（沿整面墙等距开窗，自动补窗楣/窗台/竖框）
pillarGrid(x1, y, z1, x2, z2, spacing, height, block, {cap, base}) 柱网（地下大殿/市场棚顶支撑）
cofferCeiling(x1, y, z1, x2, z2, cell, block, {inset}) 藻井天花（方格井字梁+素色格心）
plazaPaving(x1, y, z1, x2, z2, a, b, {pattern, scale}) 广场铺装（pattern: checker/stripes/rings/border/diamond/radial）
colonnadedStreet(x1, y, z1, x2, z2, spacing, height, block, {pave, roof, sideOffset}) 列柱大街（铺装+双侧柱廊+可选横梁）
rampart(x1, y, z1, x2, z2, height, thickness, block, {walkway, merlon}) 城墙（厚墙+顶面马道+外侧雉堞）
balustradeRun(x1, y, z1, x2, z2, block, {postEvery}) 栏杆长排（底梁+扶手+立柱+望柱）
bannerRow(x1, y, z1, x2, z2, height, block, {accent, spacing}) 垂旗排（横杆+垂挂旗面）
statueGroup(cx, y, cz, count, height, block, {base, radius}) 雕像群（环形排布人形雕像+基座）

【二】其它几何/宏观函数（与前文互补）
棱柱：prism / polygon / polygonDome / octagonPrism / hexagonPrism / obelisk(x,y,z,height,block)
曲线墙：ellipseWall(cx,y,cz,a,b,height,block) / arcWall(cx,y,cz,radius,height,startDeg,endDeg,block) / disc(cx,y,cz,radius,block)
拱与顶：pointedArch(cx,y,cz,span,height,facing,block) 哥特尖拱 / hipRoof(x1,z1,x2,z2,檐口Y,高度,block) 四坡顶 / mansardRoof(x1,y,z1,x2,z2,steep,flat) 孟莎顶 / slopeSlab(x1,y,z1,x2,z2,drop,block) 单坡
塔与梯：turret(cx,y,cz,radius,bodyHeight,body,roof) 锥顶角塔 / spiralStaircase(cx,y,cz,radius,height,block) / straightStairs(x,y,z,length,facing,block) / terrace(cx,y,cz,size,layers,block) 梯田台地
变换：mirror(axis,coord,x1,y1,z1,x2,y2,z2) 镜像（对称建筑神器） / rotate90 / arrayLinear / arrayRadial / clone / replace / clear

【三】装饰函数（主体完成后必用；装饰方块应占总量的 5%~10%）
外饰：eavesTrim 挑檐 / wallTrim 腰线 / crownMolding 顶角线 / windowUnit 完整窗 / flowerBox 窗台花箱 / lampPost 灯柱 / fountain 喷泉 / gardenPath 小径 / hedge 树篱 / chimney 烟囱 / pillarDecor 装饰柱 / dormer 老虎窗 / dormerRow 老虎窗排 / balcony 阳台 / bayWindow 凸肚窗 / porch 门廊 / shutter 百叶窗 / planterRow 花盆排 / well 水井 / arbor 藤架 / crates 货物堆 / clothesline 晾衣绳 / flagBanner 旗帜 / outdoorBench 长凳 / stoneLantern 石灯笼 / flowerGarden 花园 / berryBushRow 浆果丛 / stoneBridge 拱桥 / vineWall 垂藤墙 / picketFence 栅栏 / marketUmbrella 遮阳伞 / waterTrough 饮水槽 / stoneFoundation 加宽基座 / roofFinial 屋顶尖饰 / mosaicFloor 马赛克地面
内饰：carpetArea 双色地毯 / rugRunner 长条地毯 / table / chair / sofa / diningSet / bedCanopy 四柱床 / bedsideTable / wardrobe / bookshelfWall 书架墙 / libraryLadder / fireplace 壁炉 / chandelier 吊灯 / lanternCeiling 天花灯笼格 / ceilingBeams 天花横梁 / floorLamp / wallShelf / pottedPlants / kitchen / bar / throne 王座 / studyDesk / teaCorner / musicCorner / wineCellar / chestStorage / weaponRack / enchantingCorner / brewingCorner / aquarium / potRack / windowSeat
★ 参数顺序警告：下面这 7 个装饰函数的 **y（高度）在最后一个参数位**，
  不是第三个！其余装饰函数才是主流的 (x1, y, z1, x2, z2) 顺序。
  写错顺序 → y 被当成 z2 用，整片装饰会飘到半空或埋进地里
  （这就是"花草/铺装整片撒错区域或悬空"的最常见原因）。
    gardenPath(x1,z1,x2,z2, y, main, accent) 小径
    carpetArea(x1,z1,x2,z2, y, main, border) 双色地毯
    arbor(x1,z1,x2,z2, y, log, leaves) 藤架
    clothesline(x1,z1,x2,z2, y, pole) 晾衣绳
    flowerGarden(x1,z1,x2,z2, y) 花园（y = 花草所在层，脚下 y-1 需为泥土/草/砂土；
      园内高草/丁香/牡丹/玫瑰丛为双高植物，系统会自动补上半格）
    mosaicFloor(x1,z1,x2,z2, y, a, b, c) 马赛克地面
    lanternCeiling(x1,z1,x2,z2, y, spacing) 天花灯笼格
  ★ flowerGarden 与 gardenPath 的 y 语义一致：都是"方块所在层"，
    即花草/铺装本身放在 y，地面实体在 y-1。想让花园贴着已有小径，
    两者传同一个 y 即可。
装饰守则：窗一律用 windowUnit/windowBand（不要徒手挖洞）；屋顶完成必加 eavesTrim；墙面上/中/下三段分别用 wallTrim/crownMolding 分层；室内必备 carpetArea+chandelier 或 fireplace；门前 lampPost；庭院中心 fountain+gardenPath；广场四周 statueGroup+planterRow。

【三·补】普通民居 / 小建筑（单栋 ≤ 15×15）内外饰 —— 专治"小房子像盒子"
症状：小房子用 fill/shell 堆完最难看——门洞像窟窿、窗子没框、屋檐平秃、室内空荡。以下函数专治此症。
★ 整套一键（推荐：先调这两个，再按需微调）：
  cottageExterior(x, y, z, w, d, height, facing, wall, roof, {footing,door,frame,glass,windowY,road,lamp,fence,ridge,roofY,chimney})
    → 外饰整套：勒脚 + 完整门头(门框/门扇/台阶/门灯) + 三面开窗 + 檐下托架 + 门前小径 + 两侧路灯；可选一圈栅栏(带门)/屋脊/烟囱。前提：墙+屋顶已建好。
  cottageInterior(x, y, z, w, d, height, facing, {wall,trim,beam,carpet,border})
    → 内饰整套：室内隔断(留两格门洞) + 前厅起居 + 后室卧室 + 厨房台 + 储物角 + 杂物角 + 天花梁 + 吊灯。
门窗外饰单件：doorway(cx,y,cz, facing, door, {frame,step,lantern,awning,height}) 完整门头 /
  windowRow(cx,y,cz, count,spacing, facing, frame, glass, {height,sill,shutter,flowerBox}) 成排开窗 /
  windowAwning(cx,y,cz, width, facing, canopy) 悬挑雨篷 / fenceGate(cx,y,cz, facing, block) 栅栏门
屋顶线脚：roofRidge(x1,y,z1,x2,z2, block, {cap}) 屋脊 / eaveBracket(x1,y,z1,x2,z2, facing, block, {spacing}) 檐下托架 /
  chimneyStack(x,y,z, height, block, {cap,smoke}) 烟囱
室内单件：roomDivider(x1,y,z1,x2,z2, height, block, {trim,door,doorBlock}) 室内隔断 / livingRoomSet(cx,y,cz, facing) 起居整套 /
  bedroomSet(cx,y,cz, facing) 卧室整套 / kitchenCounter(x,y,z, width, facing) 厨房台 / storageNook(x,y,z, facing, {width,height}) 储物角 /
  entrywaySet(x,y,z, facing) 玄关三件套 / shelfRun(x,y,z, width, facing, block, {rows,step}) 多层壁架 / hangingHerbs(x1,y,z1,x2,z2, {spacing}) 悬挂香料 /
  clutterCorner(x,y,z, count) 杂物角 / atticLadder(x,y,z, height, facing) 阁楼梯
坐标约定：x,y,z 为房屋最小角；y 是地面层（勒脚/小径铺在 y-1，装饰放在 y 及以上）；facing 取 north/south/east/west。
小房子硬性要求（不满足视为观感不合格）：① 门必须用 doorway（不要徒手留洞）② 每面可见墙至少 windowRow 一扇带框窗
③ 屋檐必加 eaveBracket 或 eavesTrim ④ 室内至少 livingRoomSet + bedroomSet + storageNook + chandelier
⑤ 门前必加 road 小径 + 两侧 lamp 路灯 ⑥ 屋顶可选 roofRidge 屋脊 + chimneyStack 烟囱。
一行建小屋示范：shell(...) 建房壳 → cottageExterior(...) → cottageInterior(...) → lampPost 门前 → 完成（装饰占比 15%~25%，小房子比大建筑更需要装饰）。

【四】预制风格库（一条命令出一栋完整建筑且自带装饰，填充街区/城市必用）
签名统一：风格名(x, y, z, size, facing)，facing 取 north/south/east/west
★占地契约（务必先算再放，这是“建筑压到城墙/互相穿插”的唯一来源）：
  · (x, z) 是占地的**最小角**（-X/-Z 那一角），建筑向 **+X 和 +Z 各展开 size 格**
    ⇒ 实际占地 = [x, x+size] × [z, z+size]。**不是以 (x,z) 为中心**。
    例：medievalChurch(-104, 40, 22) 占 Z 40..62，不是 Z 29..51。
  · 摆放前先算两个矩形是否相交；相邻建筑至少留 2 格净距（中心距 ≥ size₁/2 + size₂/2 + 4）。
  · facing 目前**不改变几何**（仅保留参数），不要指望它转向。
★围墙（rampart）几何：rampart(x1,y,z1,x2,z2,height,thickness,block,{walkway,merlon})
  · 厚度**以给定的线为中心向两侧展开** ⇒ 墙块占 [线-thickness/2, 线-thickness/2+thickness-1]。
    例：rampart(-140,0,60,110,60,12,3,…) 占 Z 59..61（**内表面 z=59**）。
  · 副建筑 / 御道 / 广场必须**完全落在围墙内表面以内**（留 ≥2 格净距），
    绝不能让建筑轮廓越过内表面 —— 否则城墙会把建筑切掉一块（或反过来）。
  · 角塔（prism / polygonDome）与城门楼（gatehouse）压在墙上是**有意的**，其余构件不许压墙。
  · 城门洞要通，**城门楼必须写在城墙之后**（后写覆盖先写），通道才挖得穿。
中世纪：medievalHouse / medievalTavern / medievalBakery / medievalBlacksmith / medievalStable / medievalChurch / castleKeep / cityWall / cityGate / watchTower / marketStall / monastery / windmill / lighthouse / medievalFarmBarn / guildHall
北欧寒带：nordicLonghouse / snowLodge
东方：japanesePagoda / japaneseTeahouse / chinesePavilion
沙漠：desertVilla / desertWatchtower / egyptianPyramid
奇幻：mushroomHouse / elvenTower / dwarvenHall / wizardTower
古罗马/现代/港口：romanTemple / romanBath / modernVilla / harborDock
单体方块数参考：medievalHouse≈400 / medievalTavern≈800 / medievalChurch≈1800 / castleKeep≈2500 / cityGate≈600 / windmill≈500 / marketStall≈120 / lighthouse≈900 / dwarvenHall≈2000 / cityWall≈8×长度
所需建筑数 = 目标方块数 ÷ 单体方块数（例：100 万 ≈ 2000 栋中世纪民宅，或 500 栋房屋 + 2000 米城墙 + 50 座功能建筑）

【五】超大规模分区装饰策略（≥10 万方块必读）
1. 按 30~50 格划分功能区（主殿/广场/街道/庭院/园林/居住区/市场）；**每个区主体完成后立即装饰该区**，再建下一区
2. 批量装饰用 for 循环：街道每隔 8~12 格 lampPost；街道两侧 gardenPath+hedge；屋顶建完一段就 eavesTrim 一段
3. 每个居住室内至少 carpetArea + chandelier + floorLamp + table + chair×2 + bedCanopy；厨房区用 kitchen；酒馆用 bar；宫殿用 throne；图书馆用 libraryLadder
4. 广场/庭院中心 fountain，四周 arbor + planterRow + statueGroup；市场区 crates + marketUmbrella；立面用 dormer + bayWindow + shutter 增加进深
5. 用自定义 function 封装「装饰一个标准单元」，再循环调用，保证装饰密度
6. 街区填充示范（风格库 + 装饰混用）：
   function blockUnit(x, z) {
     medievalHouse(x, 64, z, 8, 'north');
     lampPost(x + 4, 64, z + 5, 5, 'spruce_fence', 'lantern');
     gardenPath(x - 3, z - 3, x + 3, z + 3, 64, 'dirt_path', 'gravel');
   }
   for (var i = 0; i < 40; i++) {
     for (var j = 0; j < 25; j++) {
       if ((i + j) % 7 == 0) { medievalTavern(12 + i * 14, 64, 12 + j * 14, 9, 'north'); }
       else { blockUnit(12 + i * 14, 12 + j * 14); }
     }
   }
7. 代码末尾自查：以上装饰函数与风格库合计至少使用 8 种，否则补充装饰段落

【六】建造正确性红线（命中任一条即视为不合格，输出前逐条自查）
1. block 参数**只能是方块 ID 字符串**（如 'oak_planks'），绝不能是数字/布尔/尺寸：
   ✗ fill(x,y,z, x2,y2,z2, 3.0)      ✗ windowUnit(cx,y,cz, 3, 2, 'south', true, 'glass_pane')
   ✓ fill(x,y,z, x2,y2,z2, 'oak_planks')   ✓ windowUnit(cx,y,cz, 2, 2, 'south', 'spruce_planks', 'glass_pane')
   系统会用主体材料**补位**非法名（能避免留洞，但材质就错了 —— 表现出来就是"有的方块没放对"）。
2. 开窗/开门/雨篷必须**贴在实际墙面上**：窗的 (cx,cz) 要落在墙体所在的 x 或 z 平面上，
   y 要落在这段墙的层高区间内。**严禁**把窗、门、雨篷放到半空、地面、屋顶上方或建筑轮廓之外
   —— 这是"凭空多出意义不明的窗户"的唯一来源。
3. 同一坐标重复写入时 **后写的覆盖先写的**（“先写的生效”是旧文档的错误说法）。
   要把某格**挖空必须显式写 'air'**，只“跳过不写”挖不动 ——
   前面写过的构件已经把格子占住了（实测城门楼的门洞因此被先写的城墙焊死）。
   想"改"某处就直接写最终想要的那一个方块，不要同一格先放墙、后放玻璃。
4. 各函数**参数顺序不同**，调用前照本参考的签名逐个数参数；多写或少写一个参数
   会导致整条调用**静默失效**（不报错、不放置）。
5. 尺寸类参数一律给**整数**；跨度不要超过建筑自身范围。
6. 输出前自查：① 每条 place/fill 的最后一个参数都是方块 ID ② 所有窗/门都贴墙
   ③ 没有同一坐标写两次 ④ 每个函数的实参个数与签名一致
