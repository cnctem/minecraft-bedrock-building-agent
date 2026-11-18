<!-- 由 tools/gen_buildlib_docs.py 从 agent/buildlib/registry.py 生成, 不要手改。 -->
<!-- 改函数签名请改 registry.SPEC, 再重跑该脚本。 -->

# 西洋古典 / 纪念性建筑函数

柱式、门廊、卷涡、宝瓶栏、拱券窗、壁柱带、檐口、玫瑰窗、飞扶壁、凯旋门、尖塔、
城堡主楼、回廊院、列柱厅、露天剧场、城墙、广场铺装。

**立面太素**时先加 `pilaster_strip`(墙面上凸出 1 格的窄柱), 再考虑雕刻;
**立面收不住头**时加 `cornice`(逐层外挑的檐口); 西洋楼不要盖中式曲面屋顶。

比例纪律(实测最影响像不像):
- 柱高 : 门廊总宽 ≈ 1 : 3~4;
- 窗宽 : 窗距 ≈ 1 : 1, 同一面墙所有窗台同高;
- 檐口总挑出 ≈ 3 格(挑太少看不出, 挑太多变中式飞檐);
- `baroque_portico` 是单面构件(贴墙), 面宽必须 ≥ 柱数×2, 否则直接报错。


## western — 西洋古典与纪念性（24 个）
- classical_column(cu, cw, base_v, height, size, block, crown=None)
    古典柱(柱础+收分+两层柱头)
- baroque_portico(u1, w1, u2, w2, base_v, columns, height, facing, stone, trim=None)
    巴洛克门廊(柱列+额枋+山花)
- volute(cu, cv, cw, radius, side, block)
    卷涡(山花两端, 左右各 side=±1)
- balustrade(u1, w1, u2, w2, base_v, spacing, block, rail=None)
    西洋宝瓶栏杆(4 层高, 屋顶/露台/池边)
- arched_window(cu, cw, sill_v, width, height, facing, frame, glass)
    拱券窗(矩形段+半圆券+券心石)
- pilaster_strip(u1, w1, u2, w2, base_v, top_v, spacing, facing, block, capital=None)
    壁柱带(墙面凸出 1 格, 立面最便宜的一招)
- cornice(u1, w1, u2, w2, v, step, layers, block)
    檐口线脚(逐层外挑)
- window_band(u1, v, w1, u2, w2, height, wall, glass, spacing=4, width=2)
    成排条窗(先留洞或贴皮)
- rose_window(cu, v, cw, radius, frame, glass='light_blue_stained_glass', axis='z', spokes=8)
    玫瑰窗(辐条+中环)
- flying_buttress(u, v, w, span, height, facing, block)
    飞扶壁
- triumphal_arch(cu, v, cw, span, height, thickness, facing, block, accent=None)
    凯旋门
- steeple(cu, v, cw, width, height, block, band=None, spire=None, band_every=6, belfry=5)
    尖塔(钟楼层+收分尖顶)
- keep(u, v, w, width, depth, height, block, merlon=None, tower_block=None, roof=None, tower_r=None, door=True)
    城堡主楼(角塔+城垛)
- cloister(cu, v, cw, inner_half, corridor_width, height, block, floor='stonebrick', roof=None, pave='grass_block', spacing=3)
    回廊院(内院+柱廊+外环)
- hypostyle_hall(u1, v, w1, u2, w2, spacing, height, block, cap=None, ceiling=None, beam=None, floor=None)
    列柱厅(柱网+梁+可选天花)
- amphitheater(cu, base_v, cw, outer_radius, tiers, tier_height, block, arena=None, accent=None, aisles=4)
    露天剧场(阶梯看台+环墙)
- gatehouse(u1, v, w1, u2, w2, height, block, tower_r=None, tower_h=None, tower_block=None, merlon=None, road=None)
    城门楼/拱门(中空+双塔+垛口)
- rampart(u1, v, w1, u2, w2, height, thickness, block, walkway=None, merlon=None)
    城墙(带步道与垛口)
- balustrade_run(u1, v, w1, u2, w2, block, post_every=6)
    栏板+望柱(线状, 沿桥/台边)
- colonnaded_street(u1, v, w1, u2, w2, spacing, height, block, pave='smooth_stone', roof=None, side_offset=3)
    柱廊街(路面+两侧柱列, 可选顶)
- plaza_paving(u1, v, w1, u2, w2, a, b, pattern='checker', scale=3)
    广场铺装(checker/stripes/rings/border/diamond/radial)
- coffer_ceiling(u1, v, w1, u2, w2, cell, block, inset=None)
    方格天花
- banner_row(u1, v, w1, u2, w2, height, block, accent='red_wool', spacing=5)
    旗杆列
- statue_group(cu, v, cw, count, height, block, base='stonebrick', radius=8)
    环形雕像群
