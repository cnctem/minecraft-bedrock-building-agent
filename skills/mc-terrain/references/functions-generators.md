<!-- 由 tools/gen_buildlib_docs.py 从 agent/buildlib/registry.py 生成, 不要手改。 -->
<!-- 改函数签名请改 registry.SPEC, 再重跑该脚本。 -->

# 自然生成器与整栋模板

确定性的地形/植被/遗迹/道路生成器, 以及几套整栋模板。

生成器都吃 `seed`(不传则按坐标推导), **同一坐标永远给同一结果**, 可反复重跑、
可分块施工而不会互相打脸。用法:
```python
api.lib.terrain(0, 0, 0, 24, "mountains")      # 先起伏地面
api.lib.ruins(0, 0, 20, 20, 45)               # 再放废墟(age=45)
api.lib.vegetation(0, 0, 16, 16, "forest")     # 周边种树
api.lib.road(0, 0, 0, 20, 0, 20, 5, "stone")   # 从路口通到废墟
```

注意: 生成器只铺一层地表(+下两层), 不做体量收分; 大范围地形仍要按 `mc-terrain`
的“控制点/等高线”思路分层做, 生成器负责自然感与植被分布。


## create — 生成器与整栋模板（14 个）
- vegetation(cu, base_v, cw, size, biome='forest', seed=None)
    植被: 乔木+地被(确定性)
- ruins(cu, base_v, cw, size, age=45, seed=None)
    废墟(围墙+地面, 按 age 风化)
- terrain(cu, base_v, cw, size, profile='hills', seed=None)
    地形: hills/mountains/plateau/basin/islands
- road(u1, v1, w1, u2, v2, w2, width=5, kind='dirt', seed=None)
    自然弯曲道路(含路边石与路灯)
- medieval_house(u, v, w, size=9, wall='white_terracotta', floor='spruce_planks', roof_fill='cobblestone_stairs')
    半木结构小屋(整栋)
- chinese_pavilion(cu, v, cw, half_width=4, pillar_height=4, pillar='spruce_log', tile='deepslate_tiles', ridge='polished_blackstone', base='stonebrick')
    中式亭(台基+斗拱+攒尖)
- japanese_pagoda(cu, v, cw, radius=4, tiers=3, tier_height=3, body='dark_oak_planks', eave='dark_oak_slab')
    日式塔
- roman_temple(cu, v, cw, width=11, depth=15, column_height=6, stylobate=2, stone='quartz_block', tile='deepslate_tiles')
    罗马神庙(台基+柱廊+山花)
- modern_villa(u, v, w, width=15, depth=11, floors=2, floor_height=4, wall='white_concrete', glass='glass_pane', accent='dark_oak_planks')
    现代别墅(错位盒体+幕墙+露台)
- castle_keep(u, v, w, width=13, depth=13, height=16, block='stonebrick')
    城堡主楼整栋
- city_wall(u1, v, w1, u2, w2, height=7, thickness=3, block='stonebrick', walkway=None, merlon=None)
    城墙段
- lighthouse(cu, v, cw, radius=4, height=18, block='quartz_block', band='red_terracotta', light='sea_lantern')
    灯塔
- windmill(cu, v, cw, radius=4, tower_height=10, blade_length=7, tower='cobblestone', blade='oak_planks')
    风车
- harbor_dock(u1, w1, u2, w2, v, water_v=None, deck='oak_planks', post='oak_log', rail='oak_fence')
    码头(栈桥+桩+栏)
