<!-- 由 tools/gen_buildlib_docs.py 从 viktor/buildlib/registry.py 生成, 不要手改。 -->
<!-- 改函数签名请改 registry.SPEC, 再重跑该脚本。 -->

# 基础几何函数(圆/球/锥/拱/斜面)

`api.lib` 里的通用几何原语。写建造程序时**优先用这些**, 而不是自己推扫描线:
它们内部已经处理了 half-up 取整、半径收敛与逐层内缩, 不会出现“被压扁的圆”
或“楼梯状斜屋面”。需要手算特殊曲线时再看 `references/circle-tables.md` 等旧表。

约定:
- 所有坐标是局部 `(u, v, w)`, 由 `origin` + `facing` 变换到世界;
- `cu/cw` 是中心, `base_v` 是起始高度(球是球心高度);
- `facing` 传 `"front"/"back"/"left"/"right"`(跟着建造朝向自动转), 也可直接给东南西北;
- 方块名用基岩版 ID; Java 版写法(`stone_bricks`/`dandelion`/`bricks` …)会被自动映射;
- 参数写错会直接报错并附接口签名, 不会静默少放方块。


## geometry — 基础几何与线脚（38 个）
- cylinder(cu, cv, cw, radius, height, block, hollow=False)
    圆筒/圆柱, 逐层复制同一圆
- sphere(cu, base_v, cw, radius, block, hollow=False)
    球/球壳, base_v 是球心高度
- ellipsoid(cu, cv, cw, ru, rv, rw, block, hollow=False)
    椭球/椭球壳
- dome(cu, base_v, cw, radius, block)
    半球穹顶(实心逐层收)
- cone(cu, base_v, cw, radius, height, block, hollow=False)
    圆锥/塔尖
- pyramid(cu, base_v, cw, size, block)
    实心四棱锥(塔尖/陵墓, 不是攒尖顶)
- obelisk(u, base_v, w, height, block)
    方尖碑
- octagon_prism(cu, base_v, cw, radius, height, block)
    八棱柱(塔身/洗礼堂)
- hexagon_prism(cu, base_v, cw, radius, height, block)
    六棱柱
- polygon(cu, base_v, cw, radius, sides, block, height=1, hollow=True)
    任意边数多边形筒
- prism(cu, base_v, cw, radius, height, sides, block, hollow=True)
    多边形棱柱(带高度)
- polygon_dome(cu, base_v, cw, radius, sides, block)
    多边形穹顶(收成一点)
- ellipse_wall(cu, base_v, cw, a, b, height, block)
    椭圆墙/椭圆筒
- disc(cu, v, cw, radius, block)
    单层圆盘(地台/花坛底)
- torus(cu, cv, cw, major_radius, tube_radius, block, axis='v')
    圆环(环廊/大环结构)
- tapered_cylinder(cu, base_v, cw, bottom_radius, top_radius, height, block, hollow=False)
    收分圆柱(烟囱/冷却塔身)
- onion_dome(cu, base_v, cw, radius, height, block)
    洋葱顶(东正/俄式)
- barrel_vault(u1, w1, u2, w2, base_v, height, block, axis='u', thickness=1)
    筒拱(单向拱顶)
- gable(u1, base_v, w1, u2, w2, height, block, axis='u', hollow=False)
    双坡屋面(逐层内缩, 无曲线)
- arch(cu, base_v, cw, span, height, facing, block)
    半圆券(券脸, 单面一层)
- pointed_arch(cu, base_v, cw, span, height, facing, block)
    尖券(哥特)
- arch_wall(u1, base_v, w1, u2, w2, spacing, height, span, block)
    连续拱廊(墙上一排券)
- buttress(u, base_v, w, length, height, facing, block)
    扶壁(逐段收分)
- arc_wall(cu, base_v, cw, radius, height, start_deg, end_deg, block)
    弧墙(按角度扫)
- catenary(u1, v1, w1, u2, v2, w2, sag, block)
    悬链线(索桥/悬索屋盖)
- catenary_bridge(u1, v1, w1, u2, v2, w2, width, sag, deck, cable=None)
    悬索桥(桥面+两侧悬索)
- line3d(u1, v1, w1, u2, v2, w2, block)
    三维直线
- box_shell(u1, v1, w1, u2, v2, w2, block, floor=True, ceiling=True)
    空心盒(墙+可选地板天花板)
- hip_roof(u1, base_v, w1, u2, w2, block)
    庑殿/四坡顶(逐层内缩)
- mansard_roof(u1, base_v, w1, u2, w2, steep, flat)
    孟莎顶(陡下坡+平顶)
- slope_slab(u1, base_v, w1, u2, w2, drop, block)
    单坡斜面
- battlement(u1, v, w1, u2, w2, block)
    城垛(隔 2 空 1)
- terrace(cu, base_v, cw, size, layers, block)
    方形台地(逐层收)
- colonnade(u1, base_v, w1, u2, w2, spacing, height, block)
    柱廊(矩形四周立柱, 无顶)
- turret(cu, base_v, cw, radius, body_height, body, roof)
    角塔(筒身+锥顶)
- spiral_staircase(cu, base_v, cw, radius, height, block)
    螺旋楼梯(单格踏面, 观光用)
- spiral_ramp(cu, base_v, cw, inner_radius, outer_radius, height, turns, block)
    螺旋坡道
- straight_stairs(u, base_v, w, length, facing, block)
    直跑楼梯(自动取楼梯方块与朝向)
