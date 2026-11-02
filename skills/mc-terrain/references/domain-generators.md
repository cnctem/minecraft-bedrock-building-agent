<!-- 由 tools/gen_skill_guides.py 抽取自 Java 模组 DomainGenerators.class 的内嵌指导文本。内容为原模组的设计标准, 已按本项目函数库对齐函数名; 不要手改, 改脚本或原类。 -->

> 函数名两种写法都能用: `api.lib.chineseRoof(...)` 与 `api.lib.chinese_roof(...)`;
> 参数里的 `{...}` 是选项名清单, 在本项目里写成关键字参数(见 `api.lib.help("名字")`)。

# DomainGenerators · domain-generators

自然与遗迹生成器(植被/遗迹/地形/道路)的定位与用法。本项目里对应
`api.lib.vegetation / ruins / terrain / road`, 都是确定性的(同坐标同 seed 同结果)。

== 自然与遗迹生成器（四类空白领域：植被 / 遗迹 / 地形 / 道路）==
★ 需要「树林植被 / 荒废遗迹 / 地形起伏 / 道路小径」时，**优先调用下列函数**，
  不要用 setBlock 一格一格手摆 —— 手摆出来的是『方块树』和『地面上插着随机方块』。
vegetation(x, y, z, size, [biome]) - 植被：乔木 + 灌木 + 地被。size = 占地边长（≤64），y = 地面高度。
  biome: forest(默认) / plains / taiga / jungle / savanna / swamp / desert / birch
ruins(x, y, z, size, [age]) - 遗迹：古代院落（围墙 + 角楼 + 地面），按 age 风化坍塌。
  age: 0~100（默认 45）；0 = 基本完好，100 = 只剩墙根残基。
terrain(x, y, z, size, [profile]) - 地形：起伏地面。size = 占地边长（≤48），y = 中心地面高度。
  profile: hills(默认) / mountains / plateau / basin / islands（后两者的低处会自动灌水）
road(x1, y1, z1, x2, y2, z2, [width], [kind]) - 道路：两点之间的自然弯曲路面（含路边石与路灯）。
  width 默认 5；kind: dirt(默认) / stone / cobble / mud / highway
★ 这四个函数都是**确定性**的（同一坐标一定给出同一结果），多个 NPC 协作建同一处不会互相打架。
★ 用法示例：先 terrain 出起伏地面 → 再 ruins 放一座废墟 → 周边 vegetation 种树 →
  最后 road 从城门口通到废墟，四种拼起来就是一片『被森林吞没的古代遗迹』。
