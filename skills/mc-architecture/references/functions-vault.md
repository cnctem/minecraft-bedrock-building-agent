<!-- 由 tools/gen_buildlib_docs.py 从 agent/buildlib/registry.py 生成, 不要手改。 -->
<!-- 改函数签名请改 registry.SPEC, 再重跑该脚本。 -->

# 拱顶 / 曲面 / 结构函数

做大厅、教堂、大跨度屋盖、现代造型时用这一份。模型手写循环最容易出错的地方
(谷线、壳厚、肋的位置、收分与扭转)都已封在函数里。

常见的“别自己搓”:
- 十字拱用 `groin_vault`(有谷线), 不是排一排 `arch`(那是筒拱);
- 哥特顶用 `rib_vault`(肋沿对角线凸起), 不是给 `groin_vault` 换材质;
- 冷却塔/扭转塔/双曲屋面用 `hyperboloid` / `twisted_tower` / `hyperbolic_paraboloid`;
- 幕墙/斜交网格用 `curtain_wall` / `diagrid`(两端一定有龙骨, 不会出现“没边框的玻璃”);
- 能走的旋转楼梯用 `stair_tower`, 只做装饰螺线才用 `spiral_staircase`。


## vault — 拱顶 / 曲面 / 结构（15 个）
- groin_vault(u1, w1, u2, w2, base_v, height, block)
    十字拱(四个方向拱面相交, 有谷线)
- rib_vault(u1, w1, u2, w2, base_v, height, rib_lift, rib_block, block)
    肋拱(哥特)
- fan_vault(cu, cv, cw, radius, drop, ribs, rings, block)
    扇拱(肋+同心环)
- viaduct(u1, w1, u2, w2, base_v, ground_v, spans, arch_height, thickness, deck_block, pier_block=None)
    多跨高架拱(水道桥)
- space_frame(u1, w1, u2, w2, v, depth, grid, block)
    双层网架屋盖
- hyperboloid(cu, cw, base_v, bottom_radius, waist_radius, top_radius, height, sides, block)
    单叶双曲面(冷却塔)
- hyperbolic_paraboloid(u1, w1, u2, w2, base_v, height, thickness, block)
    马鞍面薄壳
- helicoid(cu, cw, base_v, radius, turns, height, thickness, block)
    螺旋面
- superellipsoid(cu, cv, cw, ru, rv, rw, exponent, hollow, block)
    超椭球(指数 2=球, 4=圆角立方)
- twisted_tower(cu, cw, base_v, bottom_radius, top_radius, height, sides, twist_deg, block)
    扭转塔
- ribbed_shell(cu, cv, cw, ru, rv, rw, ribs, rings, rib_lift, rib_block, panel_block=None)
    肋壳(椭球经线肋+纬线环)
- curtain_wall(u1, base_v, w1, u2, top_v, w2, mullion_every, floor_every, mullion_block, glass_block)
    玻璃幕墙(竖龙骨+层间横梁)
- diagrid(u1, base_v, w1, u2, top_v, w2, panel_width, panel_height, line_width, block)
    斜交网格立面
- stair_tower(cu, cw, base_v, radius, steps, turns, core_radius, step_block, core_block=None)
    旋转楼梯整体(中心柱+可走踏面+扶手)
- lattice_truss(u1, v1, w1, u2, v2, w2, spacing, block)
    点阵桁架(超 40000 格直接报错)
