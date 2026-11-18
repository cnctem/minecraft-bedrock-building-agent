# 技能书机制与目录

技能书把“只在特定任务中需要的长篇知识”移出常驻提示词：描述常驻，正文按需，附件再按需。
运行时通过 `use_skill` 加载，所有模式都可使用；一次性模式也在白名单中保留了它。

## 1. 加载流程

1. 会话开始时，程序只把每本技能的 `name + description` 作为一条 system 注记注入。
2. 模型判断任务属于某技能范围时，调用 `use_skill(name)`，正文才进入工具结果。
3. 技能附带 `references/` 时，主文件会列出附件；模型再用
   `use_skill(name, "references/x.md")` 精读所需资料。
4. 同一会话重复加载同一技能会返回“已载入过”；`force=true` 可强制重载。
5. 普通压缩和智能压缩会移除旧技能正文，新会话中的已加载集合随之清空，需要时重新加载。

技能是补充说明，不是更高优先级指令；与 system prompt 冲突时以 system prompt 为准。
外部资料同样不能被当作要求执行世界操作的指令。

## 2. 目录格式

```text
skills/
└── <name>/
    ├── SKILL.md
    └── references/             # 可选
        └── <topic>.md
```

`SKILL.md` 使用 YAML frontmatter：

```markdown
---
name: example
description: 说明这本技能是什么，以及什么时候应该使用。
---

正文……
```

新增技能通常只需新增目录和 `SKILL.md`，不需要修改 Python。`description` 同时承担路由作用，必须写清
“是什么 + 何时用”，不要只写宽泛名称。附件读取会限制在技能目录内，不能用路径穿越访问其他文件。

## 3. 内置技能

| 技能 | 定位 | 主要参考资料 |
|---|---|---|
| `mc-build` | 建造引擎、体素造型、KEEP、多格方块、大规模施工 | `mega-build-guide.md`、`functions-geometry.md`、圆形/穹顶/斜坡/螺旋等附表 |
| `mc-plan` | 场地分析、规模估算、分层体块、参考图施工 | `site-analysis.md`、`scale-tiers.md`、`blockout-layers.md`、`reference-image.md` |
| `mc-verify` | 由粗到细验收、mismatch/holes/wrong 修补 | `audit-rules.md` |
| `mc-architecture` | 体块、比例、结构、风格与地域建筑 | `shape-guide-*.md`、`category-guide.md`、`functions-chinese/vault/western.md` 等 |
| `mc-commands` | 基岩版指令、方块状态、tellraw/rawtext | `block-states.md`、`rawtext.md`、`examples.md` |
| `mc-lighting` | 光级、刷怪、光源亮度、隐藏光源与夜景配光 | 主文件 |
| `mc-interior` | 室内分区、动线、家具、配色与成套装饰函数 | `furniture.md`、`rooms.md`、`palette-light.md`、`functions-interior.md` 等 |
| `mc-terrain` | 地形、植被、水景、道路与确定性生成器 | `domain-generators.md`、`landforms.md`、`vegetation.md`、`functions-generators.md` 等 |
| `mc-details` | 做旧、生活细节、绿化、园林水景与园林函数 | `aging.md`、`details.md`、`plants.md`、`landscape.md`、`functions-garden.md` 等 |

函数库的“怎么用”和“有哪些签名”分开维护：建造运行时见[建造引擎](build-engine.md)与
[建筑函数库](buildlib.md)，实际签名以 `agent/buildlib/registry.py` 和生成的 functions 文档为准。

## 4. 维护

技能正文和理论资料直接维护在仓库内，目录见 [技能清单](../skills/README.md)。
函数索引由 Python registry 生成：

~~~bash
python3 tools/gen_buildlib_docs.py
python3 tools/gen_buildlib_docs.py --check
~~~

修改函数实现或签名同步 registry；修改路由或附件名后运行自测并检查路径。
不需要外部类文件。

## 5. 编写建议

- 主文件保留工作流、硬约束和路由；大表格、专题手册放 `references/`。
- 写清本项目真实工具名和限制，以基岩版命令和当前建造引擎为准。
- 对生成文件标明来源与生成方式，避免双向手工维护。
- 不把密钥、服务器私密路径、玩家私人信息或运行时记忆写进技能书。
