---
name: mc-tellraw
description: 基岩版 tellraw 超链接与可点击消息手册——用 rawtext JSON 生成坐标传送、传送到地标、打开网页、执行/建议命令、悬浮说明、彩色按钮和菜单。玩家要求点一下传送、做导航菜单、发可点击链接、做服务器公告或操作面板时加载。
---

# tellraw 超链接与可点击消息手册

`tellraw` 发的是 **Bedrock rawtext JSON**，不是 Java 版直接 `{"text":...}` 语法。
`run_server_command` 里命令**不带前导 `/`**；JSON 内 `run_command` 的 value**要带 `/`**。

## 0. 能力与边界

- 可点击文本能：`open_url` 打开网页、`run_command` 执行一条命令、`suggest_command` 只填入聊天框。
- 悬浮文本能：`show_text` 显示说明；`show_item`/`show_entity` 版本差异大，先小范围实测。
- **一次点击只执行一条命令**。要“传送 + 播放音效 + 发消息”，需要事先做函数/命令链或拆成多个按钮。
- `tellraw` 不改变权限：`run_command` 仍受点击玩家自己的命令权限/作弊设置限制。
- 命令行不写 `/tellraw`，从 `tellraw` 开始；JSON 外的目标选择器 `@a`/`@p` 交给 `run_server_command`。

## 1. 最小模板

```
tellraw <目标> {"rawtext":[{"text":"普通文本"}]}
```

例：

```
tellraw @a {"rawtext":[{"text":"欢迎来到主城","color":"gold","bold":true}]}
```

- `<目标>` 常用 `@a`(所有人)、`@p`(最近玩家)、玩家名(推荐精确发送)。
- 从控制台发消息时，顶层目标不要用 `@s`；`@s` 适合放进点击后执行的 `run_command` 里。
- 多个文本组件按数组顺序拼接：

```
tellraw @a {"rawtext":[{"text":"["},{"text":"传送","color":"aqua"},{"text":"]"}]}
```

## 2. 文本组件字段

| 字段 | 作用 | 示例 |
|---|---|---|
| `text` | 显示文本 | `"text":"传送"` |
| `color` | 颜色 | `"color":"gold"` |
| `bold` | 粗体 | `"bold":true` |
| `italic` | 斜体 | `"italic":true` |
| `underlined` | 下划线 | `"underlined":true` |
| `strikethrough` | 删除线 | `"strikethrough":true` |
| `obfuscated` | 乱码 | `"obfuscated":true` |
| `clickEvent` | 点击动作 | 见 §3 |
| `hoverEvent` | 悬浮提示 | 见 §3 |

颜色优先用 `gold/aqua/green/red/yellow/gray`；不要依赖 `§` 转义。按钮文字建议 ≤10 个汉字，重要按钮加粗+下划线。

## 3. 点击与悬浮动作

### 打开网页

```
tellraw @p {"rawtext":[{"text":"打开服务器地图","color":"aqua","underlined":true,"clickEvent":{"action":"open_url","value":"https://example.com/map"},"hoverEvent":{"action":"show_text","value":"点击后在浏览器打开地图"}}]}
```

### 传送到坐标

```
tellraw @p {"rawtext":[{"text":"[传送到喷泉]","color":"gold","bold":true,"clickEvent":{"action":"run_command","value":"/tp @s 120 65 -40"},"hoverEvent":{"action":"show_text","value":"点击传送到喷泉"}}]}
```

- `@s` 在点击时解析为**点击者**，适合个人传送。
- 坐标要用绝对整数；相对 `~` 会相对点击者当前位置。
- 先 `get_player_position` + `get_block` 确认落点，建议 y 取地面上一层。
- 跨维度：`value":"/execute in nether run tp @s 0 64 0"`；先小范围测试语法。

### 执行命令 / 只建议命令

```
tellraw @a {"rawtext":[{"text":"[领取今日补给]","color":"green","bold":true,"clickEvent":{"action":"run_command","value":"/give @s bread 3"},"hoverEvent":{"action":"show_text","value":"每人每天限领"}}]}
```

```
tellraw @p {"rawtext":[{"text":"[填写回城命令]","color":"yellow","clickEvent":{"action":"suggest_command","value":"/tp @s 100 64 200"},"hoverEvent":{"action":"show_text","value":"只填入聊天框，不会立即执行"}}]}
```

- 破坏性、发物品、扣分/经济命令必须得到玩家明确授权。
- 对公开服务器优先 `suggest_command`；要直接执行时限制目标并做权限/冷却校验。

### 纯悬浮说明

```
tellraw @p {"rawtext":[{"text":"旧传送门","color":"light_purple","hoverEvent":{"action":"show_text","value":"已废弃，点击无效果"}}]}
```

## 4. 坐标超链接工作流

1. `get_player_position` 拿到落点 `x y z`，换算成安全站立位置。
2. 用 `inspect_region`/`get_block` 确认目标不是岩浆、水、基岩或高空悬空。
3. 构造 `rawtext`，把坐标写成绝对整数，按钮放入 `run_command`。
4. 先向自己发一条测试：`tellraw @p {...}`，斜杠值使用 `/tp @s x y z`。
5. 点击验证落点、维度、权限和提示；失败先检查 JSON 引号与 `/`。
6. 批量地标列表用 `ptc` 一次提交多条 `tellraw @p ...`，每条控制一行，避免超长命令。

## 5. 常见界面模板

- 单按钮：`[传送]` + `clickEvent.run_command` + `hoverEvent.show_text`。
- 横向菜单：`[主城] [矿场] [农场]`，组件之间用 `{"text":"  "}` 分隔。
- 多行列表：连续发多条 `tellraw @p ...`；不要把所有按钮挤在一条超长 JSON。
- 网页组件：`open_url`；命令组件：`run_command`；教学/敏感组件：`suggest_command`。
- 按钮颜色：传送=gold/aqua，危险=red，领取=green，教学=yellow，普通链接=blue/aqua。
- 每条消息不超过 5~7 个按钮；按钮超过一屏滚屏后很难点。

完整字段、转义和多组件规则见 **`references/rawtext.md`**；坐标、网页、菜单、地标、商店与批量模板见 **`references/examples.md`**。

## 6. 转义与长度

- JSON 字符串内的双引号写成 `\"`，反斜杠写成 `\\`；URL 的 `&` 原样保留，玩家名/命令中的引号必须转义。
- 不要把单条命令拼到几百个按钮；`tellraw` 过长会被截断/报语法错误，按行拆分。
- 不要在 `text` 里直接写未经转义的用户输入；先替换 `\\`、`\"` 和控制字符。
- 目标是多人时避免每人各自执行 `open_url`；需要个人化按钮就分别指定玩家名/`@p`。

## 7. 坑清单

- 用了 Java 版 `{"text":"..."}` → Bedrock 需要外层 `{"rawtext":[...]}`。
- `run_command` 的 value 忘写前导 `/` → 点击不执行或报错。
- 顶层用 `@s` 发送 → 控制台没有点击者语义；用 `@a`/`@p`/玩家名。
- `open_url` 用了非法 URL 或 `http` 兼容性差 → 优先 HTTPS，发送前检查完整域名。
- 多个动作写成一个按钮 → 只会执行一条命令；拆按钮或预先做命令链。
- 坐标用相对值 → 每个点击者传送到不同位置；地标必须用绝对整数。
- 直接发破坏性命令按钮 → 必须明确授权、限定目标并做权限检查。
- 颜色用 `§` 或 Java 组件字段 → 优先用 Bedrock `color`/`bold`/`underlined`。
- 忘测跨维度/权限 → 先向自己发测试消息，确认后再广播。
