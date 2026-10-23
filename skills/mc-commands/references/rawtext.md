# Bedrock rawtext 组件参考

配套 `SKILL.md`。`tellraw` 接收 raw JSON 消息；官方命令签名是：

```
/tellraw <target: target> <raw json message: json>
```

在 `run_server_command` 中省略命令前导 `/`，但组件内部的 `run_command` 值保留 `/`。

## 1. 顶层结构

```
{"rawtext":[ 组件1, 组件2, ... ]}
```

- 组件按数组顺序拼接；每个组件可有自己的样式和事件。
- 顶层必须是对象，`rawtext` 必须是数组。
- 不要直接写 Java 版 `{"text":"..."}` 作为顶层。

## 2. 文本组件

```
{"text":"内容","color":"gold","bold":true,"italic":true,"underlined":true,"strikethrough":false,"obfuscated":false}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `text` | string | 显示文本，可含 `\n`(取决于客户端/位置) |
| `color` | string | 颜色名，如 `black`/`dark_blue`/`gold`/`gray`/`white` |
| `bold` | bool | 粗体 |
| `italic` | bool | 斜体 |
| `underlined` | bool | 下划线 |
| `strikethrough` | bool | 删除线 |
| `obfuscated` | bool | 乱码/随机字符 |

- 样式字段只影响当前组件；后续组件不会自动继承。
- 多组件拼接时，空格/括号也要单独写成 `{"text":" "}` 或包含在文本里。
- `text` 内出现 `"` 用 `\"`，出现反斜杠用 `\\`（最终 JSON 里合法转义）。

## 3. clickEvent

```
"clickEvent":{"action":"run_command","value":"/tp @s 100 64 200"}
```

| action | value | 用途 |
|---|---|---|
| `open_url` | `https://...` | 打开网页/地图/文档 |
| `run_command` | `/<命令>` | 立即执行命令 |
| `suggest_command` | `/<命令>` | 填入聊天框，不执行 |
| `change_page` | 页码 | 仅特定书本 UI，`tellraw` 中不要假设可用 |

- `run_command` 是**玩家点击时**执行，`@s` 指点击者；权限不足会失败。
- `open_url` 只接受 URL，不是命令。
- 对可能存在副作用的命令使用 `suggest_command`，或先做权限/冷却校验。
- 事件只绑定当前组件，按钮外文字不要误包进同一组件。

## 4. hoverEvent

```
"hoverEvent":{"action":"show_text","value":"点击后传送"}
```

| action | value | 用途 |
|---|---|---|
| `show_text` | 字符串/文本 | 悬浮说明，最稳定 |
| `show_item` | 物品数据 | 不同版本兼容性不同，先小范围实测 |
| `show_entity` | 实体数据 | 不同版本兼容性不同，先小范围实测 |

- 悬浮提示不代替按钮文字；按钮本身应能读出动作。
- 提示建议 ≤20 字，写清“会做什么”和“可能的影响”。

## 5. 动态/特殊组件

- 选择器：`{"selector":"@p"}` 可显示选择器结果；是否按上下文替换需实测。
- 分数：`{"score":{"name":"*","objective":"scoreboard_name"}}`，用于排行榜/状态显示。
- 翻译：`{"translate":"key"}`，键不存在时显示键名；普通建造消息用 `text` 更稳。
- 混合数组：文本、选择器、分数组件可拼接，但每个组件的点击事件只作用于自己的显示范围。

## 6. 安全生成规则

1. 用数据序列化而不是手拼用户输入；必须手拼时先转义 `\`、`"`、换行和控制字符。
2. URL 只允许预期域名；禁止把玩家输入直接塞进 `open_url`。
3. `run_command` 不拼接玩家名/自定义文本；需要参数时用固定白名单模板。
4. 公开广播前先 `tellraw @p` 自测；确认 JSON 可解析、按钮颜色清楚、命令权限正确。
5. 一条消息只解决一个任务；列表、商店、导航分别发消息。

## 7. 长度与显示

- 按钮文字推荐 2~10 个汉字；超过 10 个会缩短可读性。
- 每条消息 5~7 个按钮以内；更多操作拆成两行/两页。
- 多行优先连续多条 `tellraw`；只有确认 `\n` 渲染正常时才合并进单条。
- 长 URL、长命令、长文本会接近命令长度上限；拆分或使用短链接。
