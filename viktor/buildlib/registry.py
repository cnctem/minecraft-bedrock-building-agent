"""建筑函数库索引: 类别 → 函数名, 以及一句话签名(给提示词与技能文档生成用)。

这里只存元数据; 实现分散在 core/shapes/chinese/structures/regional/gardens/decor/creations。
新增函数时: 写进对应实现文件, 再到 SPEC 里加一行(名字、参数、说明)。
"""

# category -> (中文名, 主要归属技能)
CATEGORY_META = {
    "geometry": ("基础几何与线脚", "mc-build"),
    "chinese": ("中式官式构件", "mc-architecture"),
    "regional": ("中式地域语汇", "mc-architecture"),
    "vault": ("拱顶 / 曲面 / 结构", "mc-architecture"),
    "western": ("西洋古典与纪念性", "mc-architecture"),
    "garden": ("园林构筑与水景", "mc-details"),
    "decor": ("装饰与家具", "mc-interior"),
    "create": ("生成器与整栋模板", "mc-terrain"),
}

# category -> [func, ...]
CATEGORIES: dict[str, list[str]] = {
    "geometry": [
        "cylinder", "sphere", "ellipsoid", "dome", "cone", "pyramid", "obelisk",
        "octagon_prism", "hexagon_prism", "polygon", "prism", "polygon_dome",
        "ellipse_wall", "disc", "torus", "tapered_cylinder", "onion_dome",
        "barrel_vault", "gable", "arch", "pointed_arch", "arch_wall", "buttress",
        "arc_wall", "catenary", "catenary_bridge", "line3d", "box_shell",
        "hip_roof", "mansard_roof", "slope_slab", "battlement", "terrace",
        "colonnade", "turret", "spiral_staircase", "spiral_ramp", "straight_stairs",
    ],
    "chinese": [
        "chinese_roof", "curved_roof", "flying_eave", "xieshan_roof",
        "chinese_hip_roof", "pyramid_roof", "dougong", "sumeru_base", "moon_gate",
        "railing", "pagoda", "tile_ridges", "caisson_ceiling", "sparrow_bracket",
        "hanging_lattice", "horse_head_wall", "screen_wall", "paifang",
        "ridge_beasts", "stepped_terrace",
    ],
    "regional": [
        "guanyin_dou", "river_steps", "meiren_kao", "sky_well", "brick_gatehouse",
        "swallowtail_ridge", "huoer_wall", "chuandou_frame", "stilt_house",
        "yaodong", "tibetan_fort", "tulou",
    ],
    "vault": [
        "groin_vault", "rib_vault", "fan_vault", "viaduct", "space_frame",
        "hyperboloid", "hyperbolic_paraboloid", "helicoid", "superellipsoid",
        "twisted_tower", "ribbed_shell", "curtain_wall", "diagrid", "stair_tower",
        "lattice_truss",
    ],
    "western": [
        "classical_column", "baroque_portico", "volute", "balustrade",
        "arched_window", "pilaster_strip", "cornice", "window_band", "rose_window",
        "flying_buttress", "triumphal_arch", "steeple", "keep", "cloister",
        "hypostyle_hall", "amphitheater", "gatehouse", "rampart",
        "balustrade_run", "colonnaded_street", "plaza_paving", "coffer_ceiling",
        "banner_row", "statue_group",
    ],
    "garden": [
        "water_basin", "round_basin", "cascade", "zigzag_bridge", "stone_boat",
        "rockery", "covered_walkway", "flower_bed",
    ],
    "decor": [
        "eaves_trim", "wall_trim", "crown_molding", "window_unit", "flower_box",
        "lamp_post", "fountain", "garden_path", "hedge", "chimney", "pillar_decor",
        "carpet_area", "table", "chair", "sofa", "bookshelf_wall", "fireplace",
        "chandelier", "dormer", "dormer_row", "balcony", "bay_window", "well",
        "arbor", "planter_row", "shutter", "porch", "crates", "clothesline",
        "bed_canopy", "kitchen", "throne", "bar", "wardrobe", "potted_plants",
        "wall_shelf", "floor_lamp", "aquarium", "library_ladder", "flag_banner",
        "outdoor_bench", "stone_lantern", "flower_garden", "berry_bush_row",
        "stone_bridge", "vine_wall", "mosaic_floor", "roof_finial",
        "stone_foundation", "picket_fence", "market_umbrella", "ceiling_beams",
        "chest_storage", "enchanting_corner", "brewing_corner", "dining_set",
        "rug_runner", "window_seat", "bedside_table", "pot_rack", "wine_cellar",
        "weapon_rack", "study_desk", "tea_corner", "music_corner",
        "lantern_ceiling", "room_divider", "living_room_set", "bedroom_set",
        "kitchen_counter", "storage_nook", "entryway_set", "shelf_run",
        "hanging_herbs", "clutter_corner", "attic_ladder", "doorway",
        "window_row", "roof_ridge", "chimney_stack", "eave_bracket", "fence_gate",
        "window_awning", "cottage_exterior", "cottage_interior",
    ],
    "create": [
        "vegetation", "ruins", "terrain", "road", "medieval_house",
        "chinese_pavilion", "japanese_pagoda", "roman_temple", "modern_villa",
        "castle_keep", "city_wall", "lighthouse", "windmill", "harbor_dock",
    ],
}

# 一行签名: 只列参数名与类型含义, 默认值在实现里。用于生成技能文档与报错提示。
SPEC: dict[str, tuple] = {
    # ---------- geometry ----------
    "cylinder": ("cylinder(cu, cv, cw, radius, height, block, hollow=False)", "圆筒/圆柱, 逐层复制同一圆"),
    "sphere": ("sphere(cu, base_v, cw, radius, block, hollow=False)", "球/球壳, base_v 是球心高度"),
    "ellipsoid": ("ellipsoid(cu, cv, cw, ru, rv, rw, block, hollow=False)", "椭球/椭球壳"),
    "dome": ("dome(cu, base_v, cw, radius, block)", "半球穹顶(实心逐层收)"),
    "cone": ("cone(cu, base_v, cw, radius, height, block, hollow=False)", "圆锥/塔尖"),
    "pyramid": ("pyramid(cu, base_v, cw, size, block)", "实心四棱锥(塔尖/陵墓, 不是攒尖顶)"),
    "obelisk": ("obelisk(u, base_v, w, height, block)", "方尖碑"),
    "octagon_prism": ("octagon_prism(cu, base_v, cw, radius, height, block)", "八棱柱(塔身/洗礼堂)"),
    "hexagon_prism": ("hexagon_prism(cu, base_v, cw, radius, height, block)", "六棱柱"),
    "polygon": ("polygon(cu, base_v, cw, radius, sides, block, height=1, hollow=True)", "任意边数多边形筒"),
    "prism": ("prism(cu, base_v, cw, radius, height, sides, block, hollow=True)", "多边形棱柱(带高度)"),
    "polygon_dome": ("polygon_dome(cu, base_v, cw, radius, sides, block)", "多边形穹顶(收成一点)"),
    "ellipse_wall": ("ellipse_wall(cu, base_v, cw, a, b, height, block)", "椭圆墙/椭圆筒"),
    "disc": ("disc(cu, v, cw, radius, block)", "单层圆盘(地台/花坛底)"),
    "torus": ("torus(cu, cv, cw, major_radius, tube_radius, block, axis='v')", "圆环(环廊/大环结构)"),
    "tapered_cylinder": ("tapered_cylinder(cu, base_v, cw, bottom_radius, top_radius, height, block, hollow=False)", "收分圆柱(烟囱/冷却塔身)"),
    "onion_dome": ("onion_dome(cu, base_v, cw, radius, height, block)", "洋葱顶(东正/俄式)"),
    "barrel_vault": ("barrel_vault(u1, w1, u2, w2, base_v, height, block, axis='u', thickness=1)", "筒拱(单向拱顶)"),
    "gable": ("gable(u1, base_v, w1, u2, w2, height, block, axis='u', hollow=False)", "双坡屋面(逐层内缩, 无曲线)"),
    "arch": ("arch(cu, base_v, cw, span, height, facing, block)", "半圆券(券脸, 单面一层)"),
    "pointed_arch": ("pointed_arch(cu, base_v, cw, span, height, facing, block)", "尖券(哥特)"),
    "arch_wall": ("arch_wall(u1, base_v, w1, u2, w2, spacing, height, span, block)", "连续拱廊(墙上一排券)"),
    "buttress": ("buttress(u, base_v, w, length, height, facing, block)", "扶壁(逐段收分)"),
    "arc_wall": ("arc_wall(cu, base_v, cw, radius, height, start_deg, end_deg, block)", "弧墙(按角度扫)"),
    "catenary": ("catenary(u1, v1, w1, u2, v2, w2, sag, block)", "悬链线(索桥/悬索屋盖)"),
    "catenary_bridge": ("catenary_bridge(u1, v1, w1, u2, v2, w2, width, sag, deck, cable=None)", "悬索桥(桥面+两侧悬索)"),
    "line3d": ("line3d(u1, v1, w1, u2, v2, w2, block)", "三维直线"),
    "box_shell": ("box_shell(u1, v1, w1, u2, v2, w2, block, floor=True, ceiling=True)", "空心盒(墙+可选地板天花板)"),
    "hip_roof": ("hip_roof(u1, base_v, w1, u2, w2, block)", "庑殿/四坡顶(逐层内缩)"),
    "mansard_roof": ("mansard_roof(u1, base_v, w1, u2, w2, steep, flat)", "孟莎顶(陡下坡+平顶)"),
    "slope_slab": ("slope_slab(u1, base_v, w1, u2, w2, drop, block)", "单坡斜面"),
    "battlement": ("battlement(u1, v, w1, u2, w2, block)", "城垛(隔 2 空 1)"),
    "terrace": ("terrace(cu, base_v, cw, size, layers, block)", "方形台地(逐层收)"),
    "colonnade": ("colonnade(u1, base_v, w1, u2, w2, spacing, height, block)", "柱廊(矩形四周立柱, 无顶)"),
    "turret": ("turret(cu, base_v, cw, radius, body_height, body, roof)", "角塔(筒身+锥顶)"),
    "spiral_staircase": ("spiral_staircase(cu, base_v, cw, radius, height, block)", "螺旋楼梯(单格踏面, 观光用)"),
    "spiral_ramp": ("spiral_ramp(cu, base_v, cw, inner_radius, outer_radius, height, turns, block)", "螺旋坡道"),
    "straight_stairs": ("straight_stairs(u, base_v, w, length, facing, block)", "直跑楼梯(自动取楼梯方块与朝向)"),

    # ---------- chinese ----------
    "chinese_roof": ("chinese_roof(u1, w1, u2, w2, base_v, height, style, tile, ridge=None)",
                     "中式屋顶一次成型: 庑殿/歇山/攒尖/悬山/硬山/重檐庑殿/重檐歇山；自带举折凹曲、瓦垄、正脊、四角起翘"),
    "curved_roof": ("curved_roof(u1, w1, u2, w2, base_v, height, block)", "单向凹曲两坡屋面(廊/厢房)"),
    "flying_eave": ("flying_eave(u1, w1, u2, w2, v, lift, corner_span, out, block)", "飞檐翘角(只叠在已有檐口更夸张时用)"),
    "xieshan_roof": ("xieshan_roof(u1, w1, u2, w2, base_v, height, gable_at, block)", "歇山单件版(无瓦垄无脊, 正式建筑优先 chinese_roof)"),
    "chinese_hip_roof": ("chinese_hip_roof(u1, w1, u2, w2, base_v, height, block)", "庑殿单件版"),
    "pyramid_roof": ("pyramid_roof(cu, cw, base_v, half_width, height, finial, block, finial_block=None)", "攒尖顶+宝顶(亭/角楼)"),
    "dougong": ("dougong(cu, cv, cw, radius, layers, block)", "斗拱(每柱顶一层层外挑, 2~4 层)"),
    "sumeru_base": ("sumeru_base(u1, w1, u2, w2, base_v, height, block)", "须弥座台基(上宽-束腰-下宽)"),
    "moon_gate": ("moon_gate(cu, cv, cw, axis, radius, trim)", "月洞门(真挖 air, 必须用在已建好的墙上)"),
    "railing": ("railing(u1, w1, u2, w2, v, post_every, block)", "中式望柱栏杆(2 层)"),
    "pagoda": ("pagoda(cu, cw, base_v, radius, tiers, tier_height, sides, body, eave)", "塔(逐层收分+出檐+塔刹)"),
    "tile_ridges": ("tile_ridges(u1, w1, u2, w2, base_v, height, ridge_every, block)", "瓦垄(只配 curved_roof, 参数要逐字一致)"),
    "caisson_ceiling": ("caisson_ceiling(cu, cv, cw, half_width, layers, block, center_block=None)", "藻井(逐层内收方井+井心)"),
    "sparrow_bracket": ("sparrow_bracket(cu, cv, cw, axis, size, block)", "雀替(柱梁交角托座)"),
    "hanging_lattice": ("hanging_lattice(u1, v, w1, u2, w2, step, block)", "挂落(檐下透雕花格)"),
    "horse_head_wall": ("horse_head_wall(u1, w1, u2, w2, base_v, steps, step_width, step_height, block)", "马头墙(徽派, 两端高)"),
    "screen_wall": ("screen_wall(cu, cv, cw, axis, width, height, block, cap_block=None)", "影壁/照壁"),
    "paifang": ("paifang(cu, cv, cw, axis, spans, height, span_width, column_block, beam_block, roof_block)", "牌坊(间数 3 = 三间四柱)"),
    "ridge_beasts": ("ridge_beasts(u1, w1, u2, w2, v, count, block)", "屋脊吻兽"),
    "stepped_terrace": ("stepped_terrace(u1, w1, u2, w2, base_v, steps, step_height, step_depth, block)", "月台/踏道台阶"),

    # ---------- regional ----------
    "guanyin_dou": ("guanyin_dou(u1, w1, u2, w2, base_v, height, extra, block)", "江南观音兜(连续弧, 中间最高)"),
    "river_steps": ("river_steps(cu, cw, water_v, width, steps, axis, block, water_block=None)", "河埠头石阶"),
    "meiren_kao": ("meiren_kao(u1, w1, u2, w2, seat_v, back_side, block)", "美人靠(座面+弧形靠背)"),
    "sky_well": ("sky_well(u1, w1, u2, w2, floor_v, depth, wall_block, bottom_block)", "天井(四水归堂)"),
    "brick_gatehouse": ("brick_gatehouse(cu, cv, cw, axis, width, height, frame_block, carving_block=None, cap_block='deepslate_tiles')", "徽派砖雕门罩(门洞真空)"),
    "swallowtail_ridge": ("swallowtail_ridge(u1, w1, u2, w2, ridge_v, lift, block)", "闽南燕尾脊(两端上翘分叉)"),
    "huoer_wall": ("huoer_wall(u1, w1, u2, w2, base_v, height, ear_lift, block)", "岭南镬耳墙(中段平, 两端半圆)"),
    "chuandou_frame": ("chuandou_frame(u1, w1, u2, w2, ground_v, eave_v, bays, post_block, tie_beam_block)", "川蜀穿斗木构(密柱+穿枋, 无斗拱)"),
    "stilt_house": ("stilt_house(u1, w1, u2, w2, ground_v, lift_height, post_block, deck_block, wall_block)", "吊脚楼(架空楼板)"),
    "yaodong": ("yaodong(u1, w1, u2, w2, ground_v, facade_height, arch_radius, soil_block, frame_block)", "窑洞(半圆券门洞+退台, 平顶)"),
    "tibetan_fort": ("tibetan_fort(u1, w1, u2, w2, base_v, height, taper, stone_block, band_block)", "藏式碉房(收分+边玛墙)"),
    "tulou": ("tulou(cu, cw, base_v, radius, floors, floor_height, wall_thickness, soil_block, tile_block)", "客家土楼(自带环形瓦檐)"),

    # ---------- vault ----------
    "groin_vault": ("groin_vault(u1, w1, u2, w2, base_v, height, block)", "十字拱(四个方向拱面相交, 有谷线)"),
    "rib_vault": ("rib_vault(u1, w1, u2, w2, base_v, height, rib_lift, rib_block, block)", "肋拱(哥特)"),
    "fan_vault": ("fan_vault(cu, cv, cw, radius, drop, ribs, rings, block)", "扇拱(肋+同心环)"),
    "viaduct": ("viaduct(u1, w1, u2, w2, base_v, ground_v, spans, arch_height, thickness, deck_block, pier_block=None)", "多跨高架拱(水道桥)"),
    "space_frame": ("space_frame(u1, w1, u2, w2, v, depth, grid, block)", "双层网架屋盖"),
    "hyperboloid": ("hyperboloid(cu, cw, base_v, bottom_radius, waist_radius, top_radius, height, sides, block)", "单叶双曲面(冷却塔)"),
    "hyperbolic_paraboloid": ("hyperbolic_paraboloid(u1, w1, u2, w2, base_v, height, thickness, block)", "马鞍面薄壳"),
    "helicoid": ("helicoid(cu, cw, base_v, radius, turns, height, thickness, block)", "螺旋面"),
    "superellipsoid": ("superellipsoid(cu, cv, cw, ru, rv, rw, exponent, hollow, block)", "超椭球(指数 2=球, 4=圆角立方)"),
    "twisted_tower": ("twisted_tower(cu, cw, base_v, bottom_radius, top_radius, height, sides, twist_deg, block)", "扭转塔"),
    "ribbed_shell": ("ribbed_shell(cu, cv, cw, ru, rv, rw, ribs, rings, rib_lift, rib_block, panel_block=None)", "肋壳(椭球经线肋+纬线环)"),
    "curtain_wall": ("curtain_wall(u1, base_v, w1, u2, top_v, w2, mullion_every, floor_every, mullion_block, glass_block)", "玻璃幕墙(竖龙骨+层间横梁)"),
    "diagrid": ("diagrid(u1, base_v, w1, u2, top_v, w2, panel_width, panel_height, line_width, block)", "斜交网格立面"),
    "stair_tower": ("stair_tower(cu, cw, base_v, radius, steps, turns, core_radius, step_block, core_block=None)", "旋转楼梯整体(中心柱+可走踏面+扶手)"),
    "lattice_truss": ("lattice_truss(u1, v1, w1, u2, v2, w2, spacing, block)", "点阵桁架(超 40000 格直接报错)"),

    # ---------- western ----------
    "classical_column": ("classical_column(cu, cw, base_v, height, size, block, crown=None)", "古典柱(柱础+收分+两层柱头)"),
    "baroque_portico": ("baroque_portico(u1, w1, u2, w2, base_v, columns, height, facing, stone, trim=None)", "巴洛克门廊(柱列+额枋+山花)"),
    "volute": ("volute(cu, cv, cw, radius, side, block)", "卷涡(山花两端, 左右各 side=±1)"),
    "balustrade": ("balustrade(u1, w1, u2, w2, base_v, spacing, block, rail=None)", "西洋宝瓶栏杆(4 层高, 屋顶/露台/池边)"),
    "arched_window": ("arched_window(cu, cw, sill_v, width, height, facing, frame, glass)", "拱券窗(矩形段+半圆券+券心石)"),
    "pilaster_strip": ("pilaster_strip(u1, w1, u2, w2, base_v, top_v, spacing, facing, block, capital=None)", "壁柱带(墙面凸出 1 格, 立面最便宜的一招)"),
    "cornice": ("cornice(u1, w1, u2, w2, v, step, layers, block)", "檐口线脚(逐层外挑)"),
    "window_band": ("window_band(u1, v, w1, u2, w2, height, wall, glass, spacing=4, width=2)", "成排条窗(先留洞或贴皮)"),
    "rose_window": ("rose_window(cu, v, cw, radius, frame, glass='light_blue_stained_glass', axis='z', spokes=8)", "玫瑰窗(辐条+中环)"),
    "flying_buttress": ("flying_buttress(u, v, w, span, height, facing, block)", "飞扶壁"),
    "triumphal_arch": ("triumphal_arch(cu, v, cw, span, height, thickness, facing, block, accent=None)", "凯旋门"),
    "steeple": ("steeple(cu, v, cw, width, height, block, band=None, spire=None, band_every=6, belfry=5)", "尖塔(钟楼层+收分尖顶)"),
    "keep": ("keep(u, v, w, width, depth, height, block, merlon=None, tower_block=None, roof=None, tower_r=None, door=True)", "城堡主楼(角塔+城垛)"),
    "cloister": ("cloister(cu, v, cw, inner_half, corridor_width, height, block, floor='stonebrick', roof=None, pave='grass_block', spacing=3)", "回廊院(内院+柱廊+外环)"),
    "hypostyle_hall": ("hypostyle_hall(u1, v, w1, u2, w2, spacing, height, block, cap=None, ceiling=None, beam=None, floor=None)", "列柱厅(柱网+梁+可选天花)"),
    "amphitheater": ("amphitheater(cu, base_v, cw, outer_radius, tiers, tier_height, block, arena=None, accent=None, aisles=4)", "露天剧场(阶梯看台+环墙)"),
    "gatehouse": ("gatehouse(u1, v, w1, u2, w2, height, block, tower_r=None, tower_h=None, tower_block=None, merlon=None, road=None)", "城门楼/拱门(中空+双塔+垛口)"),
    "rampart": ("rampart(u1, v, w1, u2, w2, height, thickness, block, walkway=None, merlon=None)", "城墙(带步道与垛口)"),
    "balustrade_run": ("balustrade_run(u1, v, w1, u2, w2, block, post_every=6)", "栏板+望柱(线状, 沿桥/台边)"),
    "colonnaded_street": ("colonnaded_street(u1, v, w1, u2, w2, spacing, height, block, pave='smooth_stone', roof=None, side_offset=3)", "柱廊街(路面+两侧柱列, 可选顶)"),
    "plaza_paving": ("plaza_paving(u1, v, w1, u2, w2, a, b, pattern='checker', scale=3)", "广场铺装(checker/stripes/rings/border/diamond/radial)"),
    "coffer_ceiling": ("coffer_ceiling(u1, v, w1, u2, w2, cell, block, inset=None)", "方格天花"),
    "banner_row": ("banner_row(u1, v, w1, u2, w2, height, block, accent='red_wool', spacing=5)", "旗杆列"),
    "statue_group": ("statue_group(cu, v, cw, count, height, block, base='stonebrick', radius=8)", "环形雕像群"),

    # ---------- garden ----------
    "water_basin": ("water_basin(u1, w1, u2, w2, floor_v, wall_height, wall, floor=None, water='water')", "方形水池(底/壁/水面齐)"),
    "round_basin": ("round_basin(cu, cw, floor_v, radius, wall_height, wall, water='water')", "圆形水池"),
    "cascade": ("cascade(cu, cw, top_v, width, steps, drop, out_step, block, facing='front')", "跌水(逐层水槽+落水)"),
    "zigzag_bridge": ("zigzag_bridge(u1, w1, u2, w2, deck_v, bents, width, deck, rail=None)", "九曲桥(转角补实)"),
    "stone_boat": ("stone_boat(cu, cw, deck_v, length, width, hull_height, cabin_height, hull, cabin=None, roof=None)", "石舫(船体+舱房+挑顶)"),
    "rockery": ("rockery(cu, cw, base_v, ru, rv, rw, holes, shell, core=None)", "叠石假山(上收下阔+内部真挖穿)"),
    "covered_walkway": ("covered_walkway(u1, w1, u2, w2, base_v, width, height, column_step, pillar, roof, bench=None)", "游廊(有顶有坐凳)"),
    "flower_bed": ("flower_bed(u1, w1, u2, w2, base_v, rim_height, wall, soil='dirt', flower='poppy', stride=2)", "花池(池壁+土+散花)"),

    # ---------- decor ----------
    "eaves_trim": ("eaves_trim(u1, v, w1, u2, w2, overhang, block)", "出檐线(逐层外扩一圈)"),
    "wall_trim": ("wall_trim(u1, v, w1, u2, w2, block)", "墙身单圈线脚"),
    "crown_molding": ("crown_molding(u1, v, w1, u2, w2, block)", "顶角线(墙顶一圈)"),
    "window_unit": ("window_unit(cu, v, cw, width, height, facing, frame, glass)", "窗套(框+玻璃+窗台)"),
    "flower_box": ("flower_box(cu, v, cw, width, facing)", "窗台花箱"),
    "lamp_post": ("lamp_post(u, v, w, height, pole='oak_fence', light='lantern')", "路灯"),
    "fountain": ("fountain(cu, v, cw, radius, basin='stonebrick')", "小喷泉(池+水柱)"),
    "garden_path": ("garden_path(u1, w1, u2, w2, v, main, accent=None, seed=1)", "园路(双材质混铺)"),
    "hedge": ("hedge(u1, v, w1, u2, w2, block, height=2)", "绿篱(沿边一圈)"),
    "chimney": ("chimney(u, v, w, height, block='brick_block')", "烟囱(单格柱+营火)"),
    "pillar_decor": ("pillar_decor(u, v, w, height, base, shaft, capital)", "独立装饰柱"),
    "carpet_area": ("carpet_area(u1, v, w1, u2, w2, main, border)", "地毯区(带边框)"),
    "table": ("table(u, v, w, width, top='spruce_slab', leg='oak_fence')", "桌子(半砖面+栅栏腿)"),
    "chair": ("chair(u, v, w, facing, block='spruce_stairs')", "椅子(楼梯, 自动朝向)"),
    "sofa": ("sofa(u, v, w, width, facing, block='spruce_stairs')", "沙发(座+靠背)"),
    "bookshelf_wall": ("bookshelf_wall(u1, v1, w1, u2, v2, w2)", "书架墙"),
    "fireplace": ("fireplace(cu, v, cw, facing, block='stonebrick')", "壁炉(带烟道)"),
    "chandelier": ("chandelier(cu, v, cw, radius, chain='chain', light='glowstone')", "吊灯"),
    "dormer": ("dormer(cu, v, cw, width, facing, wall, glass='glass_pane')", "老虎窗"),
    "dormer_row": ("dormer_row(cu, v, cw, count, spacing, facing, wall)", "一排老虎窗"),
    "balcony": ("balcony(u, v, w, width, depth, facing, floor='spruce_slab', rail='oak_fence')", "挑阳台"),
    "bay_window": ("bay_window(cu, v, cw, width, height, facing, wall, glass)", "凸窗"),
    "well": ("well(cu, v, cw, block='stonebrick')", "水井"),
    "arbor": ("arbor(u1, w1, u2, w2, v, log='oak_log', leaves='oak_leaves')", "花架/棚架"),
    "planter_row": ("planter_row(u, v, w, width, facing, seed=1)", "成排花盆"),
    "shutter": ("shutter(u, v, w, height, facing, block='spruce_trapdoor')", "百叶窗板"),
    "porch": ("porch(cu, v, cw, width, facing, roof, pillar='oak_log')", "门廊"),
    "crates": ("crates(u, v, w, count, seed=1)", "货箱堆"),
    "clothesline": ("clothesline(u1, w1, u2, w2, v, pole='oak_fence')", "晾衣绳"),
    "bed_canopy": ("bed_canopy(u, v, w, facing, frame='dark_oak_log')", "四柱床"),
    "kitchen": ("kitchen(u, v, w, width, facing)", "灶台(烟熏炉/熔炉/炼药锅)"),
    "throne": ("throne(u, v, w, facing, block='quartz_block')", "王座"),
    "bar": ("bar(u, v, w, width, facing, block='dark_oak_planks')", "吧台"),
    "wardrobe": ("wardrobe(u, v, w, facing, block='spruce_planks')", "衣柜"),
    "potted_plants": ("potted_plants(u, v, w, count, seed=1)", "盆栽群"),
    "wall_shelf": ("wall_shelf(u, v, w, width, facing, block='spruce_trapdoor')", "壁挂搁板"),
    "floor_lamp": ("floor_lamp(u, v, w, pole='dark_oak_fence', light='shroomlight')", "落地灯"),
    "aquarium": ("aquarium(u, v, w, width, block='glass')", "鱼缸"),
    "library_ladder": ("library_ladder(u, v, w, height)", "书架+爬梯"),
    "flag_banner": ("flag_banner(u, v, w, facing, banner='red_banner')", "旗帜"),
    "outdoor_bench": ("outdoor_bench(u, v, w, width, block='smooth_stone_slab')", "户外长凳"),
    "stone_lantern": ("stone_lantern(u, v, w, block='stonebrick')", "石灯笼"),
    "flower_garden": ("flower_garden(u1, w1, u2, w2, v, seed=1)", "花境(散点花与草)"),
    "berry_bush_row": ("berry_bush_row(u, v, w, width, facing)", "浆果丛列"),
    "stone_bridge": ("stone_bridge(u1, v, w1, u2, w2, block='stonebrick')", "小石桥(拱起)"),
    "vine_wall": ("vine_wall(u, v, w, width, height, facing, seed=1)", "爬藤墙"),
    "mosaic_floor": ("mosaic_floor(u1, w1, u2, w2, v, a, b, c=None, seed=1)", "拼花地面"),
    "roof_finial": ("roof_finial(u, v, w)", "屋脊端饰"),
    "stone_foundation": ("stone_foundation(u1, v, w1, u2, w2, block='stonebrick')", "石砌地基(外圈+掏空)"),
    "picket_fence": ("picket_fence(u1, v, w1, u2, w2, block='oak_fence')", "栅栏"),
    "market_umbrella": ("market_umbrella(u, v, w, canopy='red_wool')", "集市伞"),
    "ceiling_beams": ("ceiling_beams(u1, v, w1, u2, w2, block='spruce_log')", "天花横梁"),
    "chest_storage": ("chest_storage(u, v, w, width, height, facing)", "储物柜墙"),
    "enchanting_corner": ("enchanting_corner(u, v, w)", "附魔角"),
    "brewing_corner": ("brewing_corner(u, v, w)", "酿造角"),
    "dining_set": ("dining_set(u, v, w, block='spruce_stairs')", "餐桌四椅"),
    "rug_runner": ("rug_runner(u, v, w, length, facing, main, border)", "走廊长毯"),
    "window_seat": ("window_seat(u, v, w, width, facing, block='spruce_stairs')", "窗边座"),
    "bedside_table": ("bedside_table(u, v, w)", "床头柜"),
    "pot_rack": ("pot_rack(u, v, w, width)", "吊锅架"),
    "wine_cellar": ("wine_cellar(u, v, w, width)", "酒窖桶阵"),
    "weapon_rack": ("weapon_rack(u, v, w, facing)", "武器架"),
    "study_desk": ("study_desk(u, v, w, facing)", "书桌+椅+落地灯"),
    "tea_corner": ("tea_corner(u, v, w)", "茶角落"),
    "music_corner": ("music_corner(u, v, w)", "音乐角"),
    "lantern_ceiling": ("lantern_ceiling(u1, w1, u2, w2, v, spacing=4)", "天花吊灯笼阵"),
    "room_divider": ("room_divider(u1, v, w1, u2, w2, height, block='spruce_planks', door=True)", "室内隔断(带门洞)"),
    "living_room_set": ("living_room_set(cu, v, cw, facing, opts=None)", "客厅组(地毯+沙发+茶几+书架+灯)"),
    "bedroom_set": ("bedroom_set(cu, v, cw, facing, opts=None)", "卧室组(床+柜+窗板)"),
    "kitchen_counter": ("kitchen_counter(u, v, w, width, facing, opts=None)", "厨房台面(灶+水槽)"),
    "storage_nook": ("storage_nook(u, v, w, facing, opts=None)", "储物龛"),
    "entryway_set": ("entryway_set(u, v, w, facing, opts=None)", "玄关组"),
    "shelf_run": ("shelf_run(u, v, w, width, facing, block='spruce_trapdoor', opts=None)", "成排置物架"),
    "hanging_herbs": ("hanging_herbs(u1, v, w1, u2, w2, opts=None)", "悬挂干草/香草"),
    "clutter_corner": ("clutter_corner(u, v, w, count, seed=1)", "杂物角"),
    "attic_ladder": ("attic_ladder(u, v, w, height, facing)", "阁楼梯"),
    "doorway": ("doorway(cu, v, cw, facing, door='wooden_door', opts=None)", "门洞组(门+门套+台阶+灯)"),
    "window_row": ("window_row(cu, v, cw, count, spacing, facing, frame='spruce_planks', glass='glass_pane', opts=None)", "成排窗(框+玻璃+窗台)"),
    "roof_ridge": ("roof_ridge(u1, v, w1, u2, w2, block='spruce_slab', opts=None)", "屋脊(自动沿长边)"),
    "chimney_stack": ("chimney_stack(u, v, w, height, block='brick_block', opts=None)", "烟囱(带压顶)"),
    "eave_bracket": ("eave_bracket(u1, v, w1, u2, w2, facing, block='spruce_trapdoor', opts=None)", "檐下托块"),
    "fence_gate": ("fence_gate(cu, v, cw, facing, block='oak_fence', opts=None)", "院门"),
    "window_awning": ("window_awning(cu, v, cw, width, facing, canopy='red_wool', opts=None)", "窗上雨篷"),
    "cottage_exterior": ("cottage_exterior(u, v, w, width, depth, height, facing, wall, roof, opts=None)", "小屋外观全套(门/窗/檐/灯/路/院门)"),
    "cottage_interior": ("cottage_interior(u, v, w, width, depth, height, facing, opts=None)", "小屋内饰全套"),

    # ---------- create ----------
    "vegetation": ("vegetation(cu, base_v, cw, size, biome='forest', seed=None)", "植被: 乔木+地被(确定性)"),
    "ruins": ("ruins(cu, base_v, cw, size, age=45, seed=None)", "废墟(围墙+地面, 按 age 风化)"),
    "terrain": ("terrain(cu, base_v, cw, size, profile='hills', seed=None)", "地形: hills/mountains/plateau/basin/islands"),
    "road": ("road(u1, v1, w1, u2, v2, w2, width=5, kind='dirt', seed=None)", "自然弯曲道路(含路边石与路灯)"),
    "medieval_house": ("medieval_house(u, v, w, size=9, wall='white_terracotta', floor='spruce_planks', roof_fill='cobblestone_stairs')", "半木结构小屋(整栋)"),
    "chinese_pavilion": ("chinese_pavilion(cu, v, cw, half_width=4, pillar_height=4, pillar='spruce_log', tile='deepslate_tiles', ridge='polished_blackstone', base='stonebrick')", "中式亭(台基+斗拱+攒尖)"),
    "japanese_pagoda": ("japanese_pagoda(cu, v, cw, radius=4, tiers=3, tier_height=3, body='dark_oak_planks', eave='dark_oak_slab')", "日式塔"),
    "roman_temple": ("roman_temple(cu, v, cw, width=11, depth=15, column_height=6, stylobate=2, stone='quartz_block', tile='deepslate_tiles')", "罗马神庙(台基+柱廊+山花)"),
    "modern_villa": ("modern_villa(u, v, w, width=15, depth=11, floors=2, floor_height=4, wall='white_concrete', glass='glass_pane', accent='dark_oak_planks')", "现代别墅(错位盒体+幕墙+露台)"),
    "castle_keep": ("castle_keep(u, v, w, width=13, depth=13, height=16, block='stonebrick')", "城堡主楼整栋"),
    "city_wall": ("city_wall(u1, v, w1, u2, w2, height=7, thickness=3, block='stonebrick', walkway=None, merlon=None)", "城墙段"),
    "lighthouse": ("lighthouse(cu, v, cw, radius=4, height=18, block='quartz_block', band='red_terracotta', light='sea_lantern')", "灯塔"),
    "windmill": ("windmill(cu, v, cw, radius=4, tower_height=10, blade_length=7, tower='cobblestone', blade='oak_planks')", "风车"),
    "harbor_dock": ("harbor_dock(u1, w1, u2, w2, v, water_v=None, deck='oak_planks', post='oak_log', rail='oak_fence')", "码头(栈桥+桩+栏)"),
}


def all_functions() -> list[str]:
    return [name for names in CATEGORIES.values() for name in names]


def category_of(name: str) -> str:
    for cat, names in CATEGORIES.items():
        if name in names:
            return cat
    return ""


def missing_from_spec() -> list[str]:
    """自检用: CATEGORIES 里有、SPEC 里没有(或反之)的函数名。"""
    listed = set(all_functions())
    return sorted(listed ^ set(SPEC))


def index_text(categories=None, verbose=True) -> str:
    """生成给模型/文档看的函数目录。categories=None 表示全部。"""
    cats = list(CATEGORIES) if categories is None else [
        c for c in CATEGORIES if c in set(categories)]
    out = []
    for cat in cats:
        title, _ = CATEGORY_META.get(cat, (cat, ""))
        names = CATEGORIES[cat]
        if not names:
            continue
        out.append(f"## {cat} — {title}（{len(names)} 个）")
        for name in names:
            sig, desc = SPEC.get(name, (name + "(...)", ""))
            out.append(f"- {sig}\n    {desc}" if verbose and desc else f"- {sig}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"
