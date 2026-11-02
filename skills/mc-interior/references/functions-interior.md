<!-- 由 tools/gen_buildlib_docs.py 从 viktor/buildlib/registry.py 生成, 不要手改。 -->
<!-- 改函数签名请改 registry.SPEC, 再重跑该脚本。 -->

# 室内与装饰函数(家具 / 房间成套 / 门窗细节)

家具与房间成套函数。**整间房优先用 `*_set` 一次成型**, 再按喜好换材质/挪焦点;
单件家具用于补空隙。

常用组合:
- 客厅 `living_room_set(cu, v, cw, facing)` / 卧室 `bedroom_set` / 厨房 `kitchen_counter`;
- 玄关 `entryway_set` / 储物 `storage_nook` / 置物 `shelf_run` / 杂物 `clutter_corner`;
- 整屋外壳+门窗+檐+路灯 `cottage_exterior`, 整屋内饰 `cottage_interior`(小户型直接用这两个)。

注意:
- 家具的 `facing` 同样跟 `origin/facing` 走, 写 `"front"` 表示朝向建造正前方;
- 需要依附面的方块(活板门/告示牌/栅栏)由函数自己算朝向, 不要手写 states;
- 灯距 >10 格会刷怪: 大房间配 `lantern_ceiling` 或 `chandelier` 补光。


## decor — 装饰与家具（85 个）
- eaves_trim(u1, v, w1, u2, w2, overhang, block)
    出檐线(逐层外扩一圈)
- wall_trim(u1, v, w1, u2, w2, block)
    墙身单圈线脚
- crown_molding(u1, v, w1, u2, w2, block)
    顶角线(墙顶一圈)
- window_unit(cu, v, cw, width, height, facing, frame, glass)
    窗套(框+玻璃+窗台)
- flower_box(cu, v, cw, width, facing)
    窗台花箱
- lamp_post(u, v, w, height, pole='oak_fence', light='lantern')
    路灯
- fountain(cu, v, cw, radius, basin='stonebrick')
    小喷泉(池+水柱)
- garden_path(u1, w1, u2, w2, v, main, accent=None, seed=1)
    园路(双材质混铺)
- hedge(u1, v, w1, u2, w2, block, height=2)
    绿篱(沿边一圈)
- chimney(u, v, w, height, block='brick_block')
    烟囱(单格柱+营火)
- pillar_decor(u, v, w, height, base, shaft, capital)
    独立装饰柱
- carpet_area(u1, v, w1, u2, w2, main, border)
    地毯区(带边框)
- table(u, v, w, width, top='spruce_slab', leg='oak_fence')
    桌子(半砖面+栅栏腿)
- chair(u, v, w, facing, block='spruce_stairs')
    椅子(楼梯, 自动朝向)
- sofa(u, v, w, width, facing, block='spruce_stairs')
    沙发(座+靠背)
- bookshelf_wall(u1, v1, w1, u2, v2, w2)
    书架墙
- fireplace(cu, v, cw, facing, block='stonebrick')
    壁炉(带烟道)
- chandelier(cu, v, cw, radius, chain='chain', light='glowstone')
    吊灯
- dormer(cu, v, cw, width, facing, wall, glass='glass_pane')
    老虎窗
- dormer_row(cu, v, cw, count, spacing, facing, wall)
    一排老虎窗
- balcony(u, v, w, width, depth, facing, floor='spruce_slab', rail='oak_fence')
    挑阳台
- bay_window(cu, v, cw, width, height, facing, wall, glass)
    凸窗
- well(cu, v, cw, block='stonebrick')
    水井
- arbor(u1, w1, u2, w2, v, log='oak_log', leaves='oak_leaves')
    花架/棚架
- planter_row(u, v, w, width, facing, seed=1)
    成排花盆
- shutter(u, v, w, height, facing, block='spruce_trapdoor')
    百叶窗板
- porch(cu, v, cw, width, facing, roof, pillar='oak_log')
    门廊
- crates(u, v, w, count, seed=1)
    货箱堆
- clothesline(u1, w1, u2, w2, v, pole='oak_fence')
    晾衣绳
- bed_canopy(u, v, w, facing, frame='dark_oak_log')
    四柱床
- kitchen(u, v, w, width, facing)
    灶台(烟熏炉/熔炉/炼药锅)
- throne(u, v, w, facing, block='quartz_block')
    王座
- bar(u, v, w, width, facing, block='dark_oak_planks')
    吧台
- wardrobe(u, v, w, facing, block='spruce_planks')
    衣柜
- potted_plants(u, v, w, count, seed=1)
    盆栽群
- wall_shelf(u, v, w, width, facing, block='spruce_trapdoor')
    壁挂搁板
- floor_lamp(u, v, w, pole='dark_oak_fence', light='shroomlight')
    落地灯
- aquarium(u, v, w, width, block='glass')
    鱼缸
- library_ladder(u, v, w, height)
    书架+爬梯
- flag_banner(u, v, w, facing, banner='red_banner')
    旗帜
- outdoor_bench(u, v, w, width, block='smooth_stone_slab')
    户外长凳
- stone_lantern(u, v, w, block='stonebrick')
    石灯笼
- flower_garden(u1, w1, u2, w2, v, seed=1)
    花境(散点花与草)
- berry_bush_row(u, v, w, width, facing)
    浆果丛列
- stone_bridge(u1, v, w1, u2, w2, block='stonebrick')
    小石桥(拱起)
- vine_wall(u, v, w, width, height, facing, seed=1)
    爬藤墙
- mosaic_floor(u1, w1, u2, w2, v, a, b, c=None, seed=1)
    拼花地面
- roof_finial(u, v, w)
    屋脊端饰
- stone_foundation(u1, v, w1, u2, w2, block='stonebrick')
    石砌地基(外圈+掏空)
- picket_fence(u1, v, w1, u2, w2, block='oak_fence')
    栅栏
- market_umbrella(u, v, w, canopy='red_wool')
    集市伞
- ceiling_beams(u1, v, w1, u2, w2, block='spruce_log')
    天花横梁
- chest_storage(u, v, w, width, height, facing)
    储物柜墙
- enchanting_corner(u, v, w)
    附魔角
- brewing_corner(u, v, w)
    酿造角
- dining_set(u, v, w, block='spruce_stairs')
    餐桌四椅
- rug_runner(u, v, w, length, facing, main, border)
    走廊长毯
- window_seat(u, v, w, width, facing, block='spruce_stairs')
    窗边座
- bedside_table(u, v, w)
    床头柜
- pot_rack(u, v, w, width)
    吊锅架
- wine_cellar(u, v, w, width)
    酒窖桶阵
- weapon_rack(u, v, w, facing)
    武器架
- study_desk(u, v, w, facing)
    书桌+椅+落地灯
- tea_corner(u, v, w)
    茶角落
- music_corner(u, v, w)
    音乐角
- lantern_ceiling(u1, w1, u2, w2, v, spacing=4)
    天花吊灯笼阵
- room_divider(u1, v, w1, u2, w2, height, block='spruce_planks', door=True)
    室内隔断(带门洞)
- living_room_set(cu, v, cw, facing, opts=None)
    客厅组(地毯+沙发+茶几+书架+灯)
- bedroom_set(cu, v, cw, facing, opts=None)
    卧室组(床+柜+窗板)
- kitchen_counter(u, v, w, width, facing, opts=None)
    厨房台面(灶+水槽)
- storage_nook(u, v, w, facing, opts=None)
    储物龛
- entryway_set(u, v, w, facing, opts=None)
    玄关组
- shelf_run(u, v, w, width, facing, block='spruce_trapdoor', opts=None)
    成排置物架
- hanging_herbs(u1, v, w1, u2, w2, opts=None)
    悬挂干草/香草
- clutter_corner(u, v, w, count, seed=1)
    杂物角
- attic_ladder(u, v, w, height, facing)
    阁楼梯
- doorway(cu, v, cw, facing, door='wooden_door', opts=None)
    门洞组(门+门套+台阶+灯)
- window_row(cu, v, cw, count, spacing, facing, frame='spruce_planks', glass='glass_pane', opts=None)
    成排窗(框+玻璃+窗台)
- roof_ridge(u1, v, w1, u2, w2, block='spruce_slab', opts=None)
    屋脊(自动沿长边)
- chimney_stack(u, v, w, height, block='brick_block', opts=None)
    烟囱(带压顶)
- eave_bracket(u1, v, w1, u2, w2, facing, block='spruce_trapdoor', opts=None)
    檐下托块
- fence_gate(cu, v, cw, facing, block='oak_fence', opts=None)
    院门
- window_awning(cu, v, cw, width, facing, canopy='red_wool', opts=None)
    窗上雨篷
- cottage_exterior(u, v, w, width, depth, height, facing, wall, roof, opts=None)
    小屋外观全套(门/窗/檐/灯/路/院门)
- cottage_interior(u, v, w, width, depth, height, facing, opts=None)
    小屋内饰全套
