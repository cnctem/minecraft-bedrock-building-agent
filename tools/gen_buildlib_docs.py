#!/usr/bin/env python3
"""从 agent/buildlib/registry.py 生成技能书里的函数目录文档。

函数签名只有一个来源(SPEC), 所以文档不会和实现漂移:
  python3 tools/gen_buildlib_docs.py          # 重写 skills/*/references/functions-*.md
  python3 tools/gen_buildlib_docs.py --check  # 只检查是否与实现一致(不写文件)

生成的文件统一带 “由 tools/gen_buildlib_docs.py 生成, 勿手改” 头。
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from agent import buildlib as L  # noqa: E402

HEADER = ("<!-- 由 tools/gen_buildlib_docs.py 从 agent/buildlib/registry.py 生成, 不要手改。 -->\n"
          "<!-- 改函数签名请改 registry.SPEC, 再重跑该脚本。 -->\n\n")

# (目标文件, 标题, 类别, 导语)
TARGETS = [
    (
        "skills/mc-architecture/references/functions-chinese.md",
        "中式建筑函数(官式 + 地域)",
        ["chinese", "regional"],
        "做中式建筑**先看这一份**: 屋顶/斗拱/台基/门窗/塔, 以及江南、徽派、闽南、岭南、\n"
        "川蜀、西北、藏式、客家八个地域流派的标志构件。\n\n"
        "用法: `api.lib.chinese_roof(u1, w1, u2, w2, 檐口v, 高, \"歇山\", \"deepslate_tiles\", \"polished_blackstone\")`\n"
        "—— 一个函数出完整屋面(举折凹曲 + 瓦垄 + 正脊 + 四角起翘), 不要再用循环手拼斜屋面。\n\n"
        "纪律:\n"
        "- 屋顶高度 = 进深 × 0.35~0.45, 平面比墙身每边外挑 2~4 格;\n"
        "- 黄琉璃 + 斗拱 + 须弥座是**官式等级符号**, 民居用它们会变成“缩小版故宫”;\n"
        "- `moon_gate` / `brick_gatehouse` 会写 air(真挖洞), 必须用在已建好的墙上;\n"
        "- `tulou` 自带环形瓦檐, 不要再盖 `chinese_roof`;\n"
        "- `tile_ridges` 只配 `curved_roof`, 参数要逐字一致, 配 `chinese_roof` 会叠两层瓦垄。\n",
    ),
    (
        "skills/mc-architecture/references/functions-vault.md",
        "拱顶 / 曲面 / 结构函数",
        ["vault"],
        "做大厅、教堂、大跨度屋盖、现代造型时用这一份。模型手写循环最容易出错的地方\n"
        "(谷线、壳厚、肋的位置、收分与扭转)都已封在函数里。\n\n"
        "常见的“别自己搓”:\n"
        "- 十字拱用 `groin_vault`(有谷线), 不是排一排 `arch`(那是筒拱);\n"
        "- 哥特顶用 `rib_vault`(肋沿对角线凸起), 不是给 `groin_vault` 换材质;\n"
        "- 冷却塔/扭转塔/双曲屋面用 `hyperboloid` / `twisted_tower` / `hyperbolic_paraboloid`;\n"
        "- 幕墙/斜交网格用 `curtain_wall` / `diagrid`(两端一定有龙骨, 不会出现“没边框的玻璃”);\n"
        "- 能走的旋转楼梯用 `stair_tower`, 只做装饰螺线才用 `spiral_staircase`。\n",
    ),
    (
        "skills/mc-architecture/references/functions-western.md",
        "西洋古典 / 纪念性建筑函数",
        ["western"],
        "柱式、门廊、卷涡、宝瓶栏、拱券窗、壁柱带、檐口、玫瑰窗、飞扶壁、凯旋门、尖塔、\n"
        "城堡主楼、回廊院、列柱厅、露天剧场、城墙、广场铺装。\n\n"
        "**立面太素**时先加 `pilaster_strip`(墙面上凸出 1 格的窄柱), 再考虑雕刻;\n"
        "**立面收不住头**时加 `cornice`(逐层外挑的檐口); 西洋楼不要盖中式曲面屋顶。\n\n"
        "比例纪律(实测最影响像不像):\n"
        "- 柱高 : 门廊总宽 ≈ 1 : 3~4;\n"
        "- 窗宽 : 窗距 ≈ 1 : 1, 同一面墙所有窗台同高;\n"
        "- 檐口总挑出 ≈ 3 格(挑太少看不出, 挑太多变中式飞檐);\n"
        "- `baroque_portico` 是单面构件(贴墙), 面宽必须 ≥ 柱数×2, 否则直接报错。\n",
    ),
    (
        "skills/mc-build/references/functions-geometry.md",
        "基础几何函数(圆/球/锥/拱/斜面)",
        ["geometry"],
        "`api.lib` 里的通用几何原语。写建造程序时**优先用这些**, 而不是自己推扫描线:\n"
        "它们内部已经处理了 half-up 取整、半径收敛与逐层内缩, 不会出现“被压扁的圆”\n"
        "或“楼梯状斜屋面”。需要手算特殊曲线时再看 `references/circle-tables.md` 等旧表。\n\n"
        "约定:\n"
        "- 所有坐标是局部 `(u, v, w)`, 由 `origin` + `facing` 变换到世界;\n"
        "- `cu/cw` 是中心, `base_v` 是起始高度(球是球心高度);\n"
        "- `facing` 传 `\"front\"/\"back\"/\"left\"/\"right\"`(跟着建造朝向自动转), 也可直接给东南西北;\n"
        "- 方块名用基岩版 ID; Java 版写法(`stone_bricks`/`dandelion`/`bricks` …)会被自动映射;\n"
        "- 参数写错会直接报错并附接口签名, 不会静默少放方块。\n",
    ),
    (
        "skills/mc-interior/references/functions-interior.md",
        "室内与装饰函数(家具 / 房间成套 / 门窗细节)",
        ["decor"],
        "家具与房间成套函数。**整间房优先用 `*_set` 一次成型**, 再按喜好换材质/挪焦点;\n"
        "单件家具用于补空隙。\n\n"
        "常用组合:\n"
        "- 客厅 `living_room_set(cu, v, cw, facing)` / 卧室 `bedroom_set` / 厨房 `kitchen_counter`;\n"
        "- 玄关 `entryway_set` / 储物 `storage_nook` / 置物 `shelf_run` / 杂物 `clutter_corner`;\n"
        "- 整屋外壳+门窗+檐+路灯 `cottage_exterior`, 整屋内饰 `cottage_interior`(小户型直接用这两个)。\n\n"
        "注意:\n"
        "- 家具的 `facing` 同样跟 `origin/facing` 走, 写 `\"front\"` 表示朝向建造正前方;\n"
        "- 需要依附面的方块(活板门/告示牌/栅栏)由函数自己算朝向, 不要手写 states;\n"
        "- 灯距 >10 格会刷怪: 大房间配 `lantern_ceiling` 或 `chandelier` 补光。\n",
    ),
    (
        "skills/mc-details/references/functions-garden.md",
        "园林与水景函数(池 / 桥 / 假山 / 游廊 / 绿化)",
        ["garden"],
        "园林构筑的函数化做法。这些形状手搓几乎必错(尤其假山和跌水), 直接用:\n"
        "- 水池 `water_basin` / `round_basin`(底/壁/水面三层齐全), 跌水 `cascade`(逐层外挑的水槽);\n"
        "- 九曲桥 `zigzag_bridge`(转角自动补实), 石舫 `stone_boat`, 游廊 `covered_walkway`;\n"
        "- 太湖石假山 `rockery`(上收下阔 + 内部真挖穿), **不要**用 sphere/ellipsoid 糊一个球;\n"
        "- 花池 `flower_bed`, 园路 `garden_path`, 绿篱 `hedge`, 花架 `arbor`。\n\n"
        "纪律: 水面永远比池沿低 1 格(函数自动做); 水最后放, 避免提前冲垮工地;\n"
        "园林密度: 建筑三成、水石三成、绿化空场四成。\n",
    ),
    (
        "skills/mc-terrain/references/functions-generators.md",
        "自然生成器与整栋模板",
        ["create"],
        "确定性的地形/植被/遗迹/道路生成器, 以及几套整栋模板。\n\n"
        "生成器都吃 `seed`(不传则按坐标推导), **同一坐标永远给同一结果**, 可反复重跑、\n"
        "可分块施工而不会互相打脸。用法:\n"
        "```python\n"
        "api.lib.terrain(0, 0, 0, 24, \"mountains\")      # 先起伏地面\n"
        "api.lib.ruins(0, 0, 20, 20, 45)               # 再放废墟(age=45)\n"
        "api.lib.vegetation(0, 0, 16, 16, \"forest\")     # 周边种树\n"
        "api.lib.road(0, 0, 0, 20, 0, 20, 5, \"stone\")   # 从路口通到废墟\n"
        "```\n\n"
        "注意: 生成器只铺一层地表(+下两层), 不做体量收分; 大范围地形仍要按 `mc-terrain`\n"
        "的“控制点/等高线”思路分层做, 生成器负责自然感与植被分布。\n",
    ),
    (
        "skills/mc-architecture/references/functions-index.md",
        "建筑函数索引(按类别)",
        None,
        "不确定用哪个函数时先看这张表, 再展开对应类别文档:\n"
        "- 中式 → `functions-chinese.md`\n"
        "- 拱顶/曲面/结构 → `functions-vault.md`\n"
        "- 西洋/纪念性 → `functions-western.md`\n"
        "- 基础几何 → 技能 `mc-build` 的 `references/functions-geometry.md`\n"
        "- 室内家具 → 技能 `mc-interior` 的 `references/functions-interior.md`\n"
        "- 园林水景 → 技能 `mc-details` 的 `references/functions-garden.md`\n"
        "- 生成器/整栋模板 → 技能 `mc-terrain` 的 `references/functions-generators.md`\n\n"
        "程序里可以用 `print(api.lib.help(\"roof\"))` 反查签名(输出会作为 `[程序输出]` 回到你这边);\n"
        "`print(api.lib.help())` 打印全部类别。\n",
    ),
]


def build_text(title: str, categories, intro: str) -> str:
    if categories is None:
        lines = [f"# {title}\n", intro]
        for cat, names in L.CATEGORIES.items():
            meta = L.CATEGORY_META.get(cat, (cat, ""))
            lines.append(f"## {cat} — {meta[0]}（{len(names)} 个）")
            lines.append("`" + "` `".join(names) + "`")
            lines.append("")
        return HEADER + "\n".join(lines).rstrip() + "\n"
    body = L.index_text(categories, verbose=True)
    return HEADER + f"# {title}\n\n{intro}\n\n" + body


def main() -> int:
    check = "--check" in sys.argv
    missing = L.missing_from_spec()
    if missing:
        print(f"registry 与 SPEC 不一致: {missing}")
        return 1
    bad = 0
    for rel, title, cats, intro in TARGETS:
        path = BASE / rel
        text = build_text(title, cats, intro)
        if len(text) > 24000:
            print(f"⚠ {rel} 超过技能单次载入上限 24000 字符({len(text)})")
            bad += 1
        if check:
            old = path.read_text(encoding="utf-8") if path.exists() else ""
            if old != text:
                print(f"过期: {rel}")
                bad += 1
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"写入 {rel} ({len(text)} 字符)")
    if check:
        print("全部一致" if not bad else f"{bad} 处需要更新")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
