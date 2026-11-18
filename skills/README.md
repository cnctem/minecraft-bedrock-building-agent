# 技能书目录

技能正文和理论资料直接维护在本仓库，运行时按需加载。
函数索引由 agent/buildlib/registry.py 生成，签名变更后运行：

~~~bash
python3 tools/gen_buildlib_docs.py
python3 tools/gen_buildlib_docs.py --check
~~~

修改理论或工作流直接编辑 Markdown，保持与工具能力一致。
函数索引不要手改；加载机制见[技能文档](../docs/skills.md)。

## 技能清单

| 技能 | 定位 | 独有资料 |
|---|---|---|
| `mc-architecture` | 建筑设计与风格/流派（主） | shape-guide-* / category-guide / structure / facade / styles / detail / functions-* |
| `mc-build` | 建造引擎与写程序 | mega-build-guide / functions-geometry / circle-tables / dome / slopes / smooth-surfaces / spiral |
| `mc-plan` | 施工规划（场地/规模/体块/参考图） | site-analysis / scale-tiers / blockout-layers / reference-image |
| `mc-verify` | 体检与修复 | audit-rules |
| `mc-terrain` | 地形与景观 | domain-generators / landforms / vegetation / water-road / expert-rules / functions-generators |
| `mc-interior` | 室内与装饰 | furniture / rooms / palette-light / expert-rules / functions-interior |
| `mc-details` | 做旧与绿化 | aging / details / plants / landscape / pocket-parks / functions-garden |
| `mc-lighting` | 光照与夜景 | — |
| `mc-commands` | 指令与文本 | block-states / rawtext / examples |
