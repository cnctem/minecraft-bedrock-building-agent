<!-- 由 tools/gen_buildlib_docs.py 从 viktor/buildlib/registry.py 生成, 不要手改。 -->
<!-- 改函数签名请改 registry.SPEC, 再重跑该脚本。 -->

# 园林与水景函数(池 / 桥 / 假山 / 游廊 / 绿化)

园林构筑的函数化做法。这些形状手搓几乎必错(尤其假山和跌水), 直接用:
- 水池 `water_basin` / `round_basin`(底/壁/水面三层齐全), 跌水 `cascade`(逐层外挑的水槽);
- 九曲桥 `zigzag_bridge`(转角自动补实), 石舫 `stone_boat`, 游廊 `covered_walkway`;
- 太湖石假山 `rockery`(上收下阔 + 内部真挖穿), **不要**用 sphere/ellipsoid 糊一个球;
- 花池 `flower_bed`, 园路 `garden_path`, 绿篱 `hedge`, 花架 `arbor`。

纪律: 水面永远比池沿低 1 格(函数自动做); 水最后放, 避免提前冲垮工地;
园林密度: 建筑三成、水石三成、绿化空场四成。


## garden — 园林构筑与水景（8 个）
- water_basin(u1, w1, u2, w2, floor_v, wall_height, wall, floor=None, water='water')
    方形水池(底/壁/水面齐)
- round_basin(cu, cw, floor_v, radius, wall_height, wall, water='water')
    圆形水池
- cascade(cu, cw, top_v, width, steps, drop, out_step, block, facing='front')
    跌水(逐层水槽+落水)
- zigzag_bridge(u1, w1, u2, w2, deck_v, bents, width, deck, rail=None)
    九曲桥(转角补实)
- stone_boat(cu, cw, deck_v, length, width, hull_height, cabin_height, hull, cabin=None, roof=None)
    石舫(船体+舱房+挑顶)
- rockery(cu, cw, base_v, ru, rv, rw, holes, shell, core=None)
    叠石假山(上收下阔+内部真挖穿)
- covered_walkway(u1, w1, u2, w2, base_v, width, height, column_step, pillar, roof, bench=None)
    游廊(有顶有坐凳)
- flower_bed(u1, w1, u2, w2, base_v, rim_height, wall, soil='dirt', flower='poppy', stride=2)
    花池(池壁+土+散花)
