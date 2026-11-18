<!-- 由 tools/gen_buildlib_docs.py 从 agent/buildlib/registry.py 生成, 不要手改。 -->
<!-- 改函数签名请改 registry.SPEC, 再重跑该脚本。 -->

# 中式建筑函数(官式 + 地域)

做中式建筑**先看这一份**: 屋顶/斗拱/台基/门窗/塔, 以及江南、徽派、闽南、岭南、
川蜀、西北、藏式、客家八个地域流派的标志构件。

用法: `api.lib.chinese_roof(u1, w1, u2, w2, 檐口v, 高, "歇山", "deepslate_tiles", "polished_blackstone")`
—— 一个函数出完整屋面(举折凹曲 + 瓦垄 + 正脊 + 四角起翘), 不要再用循环手拼斜屋面。

纪律:
- 屋顶高度 = 进深 × 0.35~0.45, 平面比墙身每边外挑 2~4 格;
- 黄琉璃 + 斗拱 + 须弥座是**官式等级符号**, 民居用它们会变成“缩小版故宫”;
- `moon_gate` / `brick_gatehouse` 会写 air(真挖洞), 必须用在已建好的墙上;
- `tulou` 自带环形瓦檐, 不要再盖 `chinese_roof`;
- `tile_ridges` 只配 `curved_roof`, 参数要逐字一致, 配 `chinese_roof` 会叠两层瓦垄。


## chinese — 中式官式构件（20 个）
- chinese_roof(u1, w1, u2, w2, base_v, height, style, tile, ridge=None)
    中式屋顶一次成型: 庑殿/歇山/攒尖/悬山/硬山/重檐庑殿/重檐歇山；自带举折凹曲、瓦垄、正脊、四角起翘
- curved_roof(u1, w1, u2, w2, base_v, height, block)
    单向凹曲两坡屋面(廊/厢房)
- flying_eave(u1, w1, u2, w2, v, lift, corner_span, out, block)
    飞檐翘角(只叠在已有檐口更夸张时用)
- xieshan_roof(u1, w1, u2, w2, base_v, height, gable_at, block)
    歇山单件版(无瓦垄无脊, 正式建筑优先 chinese_roof)
- chinese_hip_roof(u1, w1, u2, w2, base_v, height, block)
    庑殿单件版
- pyramid_roof(cu, cw, base_v, half_width, height, finial, block, finial_block=None)
    攒尖顶+宝顶(亭/角楼)
- dougong(cu, cv, cw, radius, layers, block)
    斗拱(每柱顶一层层外挑, 2~4 层)
- sumeru_base(u1, w1, u2, w2, base_v, height, block)
    须弥座台基(上宽-束腰-下宽)
- moon_gate(cu, cv, cw, axis, radius, trim)
    月洞门(真挖 air, 必须用在已建好的墙上)
- railing(u1, w1, u2, w2, v, post_every, block)
    中式望柱栏杆(2 层)
- pagoda(cu, cw, base_v, radius, tiers, tier_height, sides, body, eave)
    塔(逐层收分+出檐+塔刹)
- tile_ridges(u1, w1, u2, w2, base_v, height, ridge_every, block)
    瓦垄(只配 curved_roof, 参数要逐字一致)
- caisson_ceiling(cu, cv, cw, half_width, layers, block, center_block=None)
    藻井(逐层内收方井+井心)
- sparrow_bracket(cu, cv, cw, axis, size, block)
    雀替(柱梁交角托座)
- hanging_lattice(u1, v, w1, u2, w2, step, block)
    挂落(檐下透雕花格)
- horse_head_wall(u1, w1, u2, w2, base_v, steps, step_width, step_height, block)
    马头墙(徽派, 两端高)
- screen_wall(cu, cv, cw, axis, width, height, block, cap_block=None)
    影壁/照壁
- paifang(cu, cv, cw, axis, spans, height, span_width, column_block, beam_block, roof_block)
    牌坊(间数 3 = 三间四柱)
- ridge_beasts(u1, w1, u2, w2, v, count, block)
    屋脊吻兽: 范围给**正脊**两端(不是屋檐外框), v 给脊顶所在层; 给成屋檐范围会把吻兽挂到脊外
- stepped_terrace(u1, w1, u2, w2, base_v, steps, step_height, step_depth, block)
    月台/踏道台阶

## regional — 中式地域语汇（12 个）
- guanyin_dou(u1, w1, u2, w2, base_v, height, extra, block)
    江南观音兜(连续弧, 中间最高)
- river_steps(cu, cw, water_v, width, steps, axis, block, water_block=None)
    河埠头石阶
- meiren_kao(u1, w1, u2, w2, seat_v, back_side, block)
    美人靠(座面+弧形靠背)
- sky_well(u1, w1, u2, w2, floor_v, depth, wall_block, bottom_block)
    天井(四水归堂)
- brick_gatehouse(cu, cv, cw, axis, width, height, frame_block, carving_block=None, cap_block='deepslate_tiles')
    徽派砖雕门罩(门洞真空)
- swallowtail_ridge(u1, w1, u2, w2, ridge_v, lift, block)
    闽南燕尾脊(两端上翘分叉)
- huoer_wall(u1, w1, u2, w2, base_v, height, ear_lift, block)
    岭南镬耳墙(中段平, 两端半圆)
- chuandou_frame(u1, w1, u2, w2, ground_v, eave_v, bays, post_block, tie_beam_block)
    川蜀穿斗木构(密柱+穿枋, 无斗拱)
- stilt_house(u1, w1, u2, w2, ground_v, lift_height, post_block, deck_block, wall_block)
    吊脚楼(架空楼板)
- yaodong(u1, w1, u2, w2, ground_v, facade_height, arch_radius, soil_block, frame_block)
    窑洞(半圆券门洞+退台, 平顶)
- tibetan_fort(u1, w1, u2, w2, base_v, height, taper, stone_block, band_block)
    藏式碉房(收分+边玛墙)
- tulou(cu, cw, base_v, radius, floors, floor_height, wall_thickness, soil_block, tile_block)
    客家土楼(自带环形瓦檐)
