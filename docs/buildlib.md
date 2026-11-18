# 建筑函数库（`api.lib` / `agent/buildlib/`）

建筑函数库为建造引擎提供可复用的 Python 几何构件：模型不再手写几百行循环去逼近
一个中式屋顶或十字拱，而是写 `api.lib.chinese_roof(...)`。底层沙箱、preview/commit/verify/undo、
坐标和渲染见[建造引擎](build-engine.md)。

当前共有 **8 类、216 个函数**，全部只产出普通形状 ops，因此复用同一套编译限额、预览、提交、撤销、渲染与校验。

| 类别 | 内容 | 签名文档 |
|---|---|---|
| `geometry` | 圆/球/椭球/锥/多边形/环面、拱顶、坡屋顶、楼梯 | [`functions-geometry.md`](../skills/mc-build/references/functions-geometry.md) |
| `chinese` | 中式屋顶、斗拱、须弥座、月洞门、塔、牌坊、藻井 | [`functions-chinese.md`](../skills/mc-architecture/references/functions-chinese.md) |
| `regional` | 江南、徽派、闽南、岭南、川蜀、窑洞、碉房、土楼 | 同 `functions-chinese.md` |
| `vault` | 十字拱/肋拱/扇拱、曲面、网架、幕墙、旋转楼梯 | [`functions-vault.md`](../skills/mc-architecture/references/functions-vault.md) |
| `western` | 柱式、门廊、拱券、玫瑰窗、飞扶壁、城堡、剧场 | [`functions-western.md`](../skills/mc-architecture/references/functions-western.md) |
| `garden` | 水池、跌水、九曲桥、石舫、假山、游廊、花池 | [`functions-garden.md`](../skills/mc-details/references/functions-garden.md) |
| `decor` | 门窗、线脚、阳台、壁炉、吊灯与成套室内家具 | [`functions-interior.md`](../skills/mc-interior/references/functions-interior.md) |
| `create` | 确定性地形/植被/遗迹/道路生成器与整栋模板 | [`functions-generators.md`](../skills/mc-terrain/references/functions-generators.md) |

- 实现：`agent/buildlib/{core,shapes,chinese,structures,regional,gardens,decor,creations}.py`
- 元数据（唯一来源）：`agent/buildlib/registry.py` → `CATEGORIES` / `SPEC`
- 注入：`agent/build.py` 把 `LIB_SOURCE` 随 payload 经 stdin 送进沙箱子进程，在用户程序 `exec`
  之前构造 `api.lib`
- 文档：`python3 tools/gen_buildlib_docs.py` → `skills/*/references/functions-*.md`
- 自测：`python3 bot.py --test` 内的「建筑函数库分类自测 / 函数库 help/别名自测」

`print(api.lib.help(...))` 等程序输出不会直接写 stdout，而会作为 `[程序输出]` 附在 build_preview 结果里。
参数错误会带出 `registry.SPEC` 中的接口签名，便于模型自行纠正。

## 1. 与建造引擎协作

函数经 api.lib 生成普通 ops，再由统一的受限 Python 编译、预览、提交、校验和撤销流程执行。
支持 snake_case 和 camelCase，不引入第二套解释器。

## 2. 统一语义

1. **坐标**：使用局部 `(u, v, w)`，世界坐标由 `origin` + `facing` 变换，
   四朝向自动旋转（`facing="front"` 跟着建造朝向走）。
2. **方块 ID**：Java 名 → 服务器真实 ID。注意 BDS **1.21.132 起 ID 已统一成 Java 叫法**
   （`stone_bricks`、`quartz_pillar`、`iron_chain`、`dandelion`、`sugar_cane` 都是真 ID，
   原本的 `stonebrick`/`yellow_flower`/`chain`/`reeds` 已从 ID 表里消失），所以别名表现在
   是“旧名 → 新 ID”的反查（`stonebrick`→`stone_bricks`、`chain`→`iron_chain`…），
   旧教程/旧技能书里的写法仍然可用。表在 `core._LibBase._ALIAS`，**一次维护，两处生效**
   （沙箱预置代码 + 宿主侧），`api.fill` 这类原语也同样受益。服务器再升级后用
   `scriptevent agent:ids` + `tools/build_items.py` 重导 ID 表，并核对别名表的目标 ID 是否还在。
3. **状态**：仍需要状态的变体（`coarse_dirt`→`dirt{dirt_type}`、`red_sand`→`sand{sand_type}`、
   门/楼梯的 `direction` 等）由别名表带出 states；而 `cracked/mossy/chiseled` 石砖、
   `smooth_quartz`/`quartz_pillar` 在新版已是独立 ID，不再用 `stone_brick_type`/`chisel_type` 状态。
4. **随机**：不用 `random`，全部走 `hash_mix/hash2/hash3/fbm2`（确定性整数散列），
   同坐标同 `seed` 永远同结果，可分块施工、可重跑。
5. **错误**：非法参数直接抛错，并附接口签名：

   ```
   baroque_portico: 面宽至少为 columns*2；当前 8，需要 10
   接口: baroque_portico(u1, w1, u2, w2, base_v, columns, height, facing, stone, trim=None)
   ```

6. **破坏性写入显式化**：`moon_gate` / `brick_gatehouse` / `yaodong` / `stone_foundation` 会写 `air`；
   `water_basin` / `round_basin` / `cascade` / `zigzag_bridge(water)` 会写水。文档里逐条标注。
7. **限额**：库只产出普通 ops，仍受 `MAX_VOLUME/MAX_CELLS/MAX_OPS/MAX_PALETTE` 约束；
   超限报错会建议按模块拆分（底座/墙身/屋顶），不放大全局限额。

## 3. 与技能书的分工

函数库解决“构件形状对不齐”，技能书解决“该建什么、比例多少、先做什么”：

| 技能 | 负责 | 对应函数目录 |
|---|---|---|
| `mc-architecture` | 体块/比例/模数、结构选型、风格与地域路由、组合顺序 | `functions-chinese/vault/western.md` + `functions-index.md` |
| `mc-build` | 建造程序怎么写、KEEP/限额/自检、基础几何 | `functions-geometry.md` |
| `mc-interior` | 分区、动线、配色、成套家具 | `functions-interior.md` |
| `mc-details` | 做旧、绿化、园林密度 | `functions-garden.md` |
| `mc-terrain` | 自然感五律、地形分层、水与道路 | `functions-generators.md` |
| `mc-lighting` | 光级/刷怪门槛/隐藏光源 | 用 `lantern_ceiling` 等埋灯 |
| `mc-verify` | 验收阶梯、补丁流程 | 函数库编译期自检也并入这一章 |

## 4. 新增 / 修改函数的流程

1. 在对应实现文件里加方法（只 `self.put/fill/box/line`，不要碰世界、不要 `import`）。
2. 在 `registry.CATEGORIES` 里登记类别，在 `registry.SPEC` 里写一行签名 + 一句话说明。
   `missing_from_spec()` 会校验两边一致（自测里跑）。
3. `python3 tools/gen_buildlib_docs.py` 重生成技能文档（`--check` 查漂移）。
4. `python3 bot.py --test`。
5. 需要视觉确认时用 `build_preview` + `render_build(views=["front","top","iso"])` 看字符图/PNG。

## 5. 维护约定

- 库函数只负责几何，不执行任务调度或世界操作。
- 整栋模板支持参数化，仍建议按地基、墙身、屋顶、内饰分批预览和提交。
- 设计比例以实现和渲染验证为准；签名由 registry 生成，教学资料直接维护在技能目录。
