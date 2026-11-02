<!-- 由 tools/gen_buildlib_docs.py 从 viktor/buildlib/registry.py 生成, 不要手改。 -->
<!-- 改函数签名请改 registry.SPEC, 再重跑该脚本。 -->

# 建筑函数索引(按类别)

不确定用哪个函数时先看这张表, 再展开对应类别文档:
- 中式 → `functions-chinese.md`
- 拱顶/曲面/结构 → `functions-vault.md`
- 西洋/纪念性 → `functions-western.md`
- 基础几何 → 技能 `mc-build` 的 `references/functions-geometry.md`
- 室内家具 → 技能 `mc-interior` 的 `references/functions-interior.md`
- 园林水景 → 技能 `mc-details` 的 `references/functions-garden.md`
- 生成器/整栋模板 → 技能 `mc-terrain` 的 `references/functions-generators.md`

程序里可以用 `print(api.lib.help("roof"))` 反查签名(输出会作为 `[程序输出]` 回到你这边);
`print(api.lib.help())` 打印全部类别。

## geometry — 基础几何与线脚（38 个）
`cylinder` `sphere` `ellipsoid` `dome` `cone` `pyramid` `obelisk` `octagon_prism` `hexagon_prism` `polygon` `prism` `polygon_dome` `ellipse_wall` `disc` `torus` `tapered_cylinder` `onion_dome` `barrel_vault` `gable` `arch` `pointed_arch` `arch_wall` `buttress` `arc_wall` `catenary` `catenary_bridge` `line3d` `box_shell` `hip_roof` `mansard_roof` `slope_slab` `battlement` `terrace` `colonnade` `turret` `spiral_staircase` `spiral_ramp` `straight_stairs`

## chinese — 中式官式构件（20 个）
`chinese_roof` `curved_roof` `flying_eave` `xieshan_roof` `chinese_hip_roof` `pyramid_roof` `dougong` `sumeru_base` `moon_gate` `railing` `pagoda` `tile_ridges` `caisson_ceiling` `sparrow_bracket` `hanging_lattice` `horse_head_wall` `screen_wall` `paifang` `ridge_beasts` `stepped_terrace`

## regional — 中式地域语汇（12 个）
`guanyin_dou` `river_steps` `meiren_kao` `sky_well` `brick_gatehouse` `swallowtail_ridge` `huoer_wall` `chuandou_frame` `stilt_house` `yaodong` `tibetan_fort` `tulou`

## vault — 拱顶 / 曲面 / 结构（15 个）
`groin_vault` `rib_vault` `fan_vault` `viaduct` `space_frame` `hyperboloid` `hyperbolic_paraboloid` `helicoid` `superellipsoid` `twisted_tower` `ribbed_shell` `curtain_wall` `diagrid` `stair_tower` `lattice_truss`

## western — 西洋古典与纪念性（24 个）
`classical_column` `baroque_portico` `volute` `balustrade` `arched_window` `pilaster_strip` `cornice` `window_band` `rose_window` `flying_buttress` `triumphal_arch` `steeple` `keep` `cloister` `hypostyle_hall` `amphitheater` `gatehouse` `rampart` `balustrade_run` `colonnaded_street` `plaza_paving` `coffer_ceiling` `banner_row` `statue_group`

## garden — 园林构筑与水景（8 个）
`water_basin` `round_basin` `cascade` `zigzag_bridge` `stone_boat` `rockery` `covered_walkway` `flower_bed`

## decor — 装饰与家具（85 个）
`eaves_trim` `wall_trim` `crown_molding` `window_unit` `flower_box` `lamp_post` `fountain` `garden_path` `hedge` `chimney` `pillar_decor` `carpet_area` `table` `chair` `sofa` `bookshelf_wall` `fireplace` `chandelier` `dormer` `dormer_row` `balcony` `bay_window` `well` `arbor` `planter_row` `shutter` `porch` `crates` `clothesline` `bed_canopy` `kitchen` `throne` `bar` `wardrobe` `potted_plants` `wall_shelf` `floor_lamp` `aquarium` `library_ladder` `flag_banner` `outdoor_bench` `stone_lantern` `flower_garden` `berry_bush_row` `stone_bridge` `vine_wall` `mosaic_floor` `roof_finial` `stone_foundation` `picket_fence` `market_umbrella` `ceiling_beams` `chest_storage` `enchanting_corner` `brewing_corner` `dining_set` `rug_runner` `window_seat` `bedside_table` `pot_rack` `wine_cellar` `weapon_rack` `study_desk` `tea_corner` `music_corner` `lantern_ceiling` `room_divider` `living_room_set` `bedroom_set` `kitchen_counter` `storage_nook` `entryway_set` `shelf_run` `hanging_herbs` `clutter_corner` `attic_ladder` `doorway` `window_row` `roof_ridge` `chimney_stack` `eave_bracket` `fence_gate` `window_awning` `cottage_exterior` `cottage_interior`

## create — 生成器与整栋模板（14 个）
`vegetation` `ruins` `terrain` `road` `medieval_house` `chinese_pavilion` `japanese_pagoda` `roman_temple` `modern_villa` `castle_keep` `city_wall` `lighthouse` `windmill` `harbor_dock`
