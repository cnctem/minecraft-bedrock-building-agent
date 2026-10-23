# tellraw 实战模板

配套 `SKILL.md`。以下是可直接替换坐标/URL/目标名的最小模板。
所有命令在 `run_server_command` 中不带前导 `/`；JSON 内的 `run_command`、`suggest_command` 值带 `/`。

## 1. 纯文本公告

```
tellraw @a {"rawtext":[{"text":"[公告] ","color":"gold","bold":true},{"text":"今晚 8 点主城集合","color":"yellow"}]}
```

## 2. 点击传送到坐标

```
tellraw @p {"rawtext":[{"text":"[传送到喷泉]","color":"gold","bold":true,"underlined":true,"clickEvent":{"action":"run_command","value":"/tp @s 120 65 -40"},"hoverEvent":{"action":"show_text","value":"点击传送到喷泉广场"}}]}
```

跨维度：

```
tellraw @p {"rawtext":[{"text":"[传送到下界大厅]","color":"red","bold":true,"clickEvent":{"action":"run_command","value":"/execute in nether run tp @s 0 64 0"},"hoverEvent":{"action":"show_text","value":"点击前往下界大厅"}}]}
```

## 3. 打开网页

```
tellraw @a {"rawtext":[{"text":"[打开在线地图]","color":"aqua","underlined":true,"clickEvent":{"action":"open_url","value":"https://example.com/map"},"hoverEvent":{"action":"show_text","value":"在浏览器中打开地图"}}]}
```

## 4. 横向导航菜单

```
tellraw @p {"rawtext":[{"text":"== 导航 == ","color":"gray"},{"text":"[主城]","color":"gold","bold":true,"clickEvent":{"action":"run_command","value":"/tp @s 100 64 100"},"hoverEvent":{"action":"show_text","value":"主城广场"}},{"text":"  "},{"text":"[矿场]","color":"aqua","bold":true,"clickEvent":{"action":"run_command","value":"/tp @s -320 42 180"},"hoverEvent":{"action":"show_text","value":"地下矿场入口"}},{"text":"  "},{"text":"[农场]","color":"green","bold":true,"clickEvent":{"action":"run_command","value":"/tp @s 260 70 -160"},"hoverEvent":{"action":"show_text","value":"公共农场"}}]}
```

## 5. 多行地标列表

```
tellraw @p {"rawtext":[{"text":"▶ 主城广场","color":"gold","clickEvent":{"action":"run_command","value":"/tp @s 100 64 100"},"hoverEvent":{"action":"show_text","value":"点击前往"}}]}
tellraw @p {"rawtext":[{"text":"▶ 矿场入口","color":"aqua","clickEvent":{"action":"run_command","value":"/tp @s -320 42 180"},"hoverEvent":{"action":"show_text","value":"点击前往"}}]}
tellraw @p {"rawtext":[{"text":"▶ 公共农场","color":"green","clickEvent":{"action":"run_command","value":"/tp @s 260 70 -160"},"hoverEvent":{"action":"show_text","value":"点击前往"}}]}
```

## 6. 只在聊天框填入命令

```
tellraw @p {"rawtext":[{"text":"[填入回城命令]","color":"yellow","clickEvent":{"action":"suggest_command","value":"/tp @s 100 64 100"},"hoverEvent":{"action":"show_text","value":"不会立即执行，需按回车确认"}}]}
```

## 7. 危险操作二次确认

```
tellraw @p {"rawtext":[{"text":"[重置个人领地] ","color":"red","bold":true,"clickEvent":{"action":"suggest_command","value":"/land reset confirm"},"hoverEvent":{"action":"show_text","value":"只会填入命令，请确认后执行"}}]}
```

## 8. 权限/规则说明

```
tellraw @a {"rawtext":[{"text":"[规则] ","color":"gold","bold":true},{"text":"禁止破坏他人建筑。","color":"white"},{"text":"[查看完整规则]","color":"aqua","underlined":true,"clickEvent":{"action":"open_url","value":"https://example.com/rules"},"hoverEvent":{"action":"show_text","value":"打开规则页面"}}]}
```

## 9. 商店/领取按钮

```
tellraw @p {"rawtext":[{"text":"[领取每日面包]","color":"green","bold":true,"clickEvent":{"action":"run_command","value":"/give @s bread 3"},"hoverEvent":{"action":"show_text","value":"每人每天限领一次"}}]}
```

- 实际服务器必须先做冷却/权限/扣分校验；此模板只展示 tellraw 结构。

## 10. 状态展示 + 按钮

```
tellraw @p {"rawtext":[{"text":"当前坐标：","color":"gray"},{"text":"120 65 -40","color":"white","bold":true},{"text":"  "},{"text":"[复制位置说明]","color":"aqua","clickEvent":{"action":"suggest_command","value":"/msg 玩家 我的位置是 120 65 -40"},"hoverEvent":{"action":"show_text","value":"填入消息模板"}}]}
```

## 11. 组合按钮与分隔符

```
tellraw @p {"rawtext":[{"text":"[是]","color":"green","bold":true,"clickEvent":{"action":"run_command","value":"/tp @s 0 64 0"}},{"text":"  |  "},{"text":"[否]","color":"red","bold":true,"hoverEvent":{"action":"show_text","value":"留在原地"}}]}
```

- “否”没有 clickEvent 是合法占位；也可改成关闭/返回菜单命令。

## 12. 批量导航消息

把多条 `tellraw @p ...` 放进 `ptc` 的 `calls` 数组一次提交：
- 第 1 条：标题；
- 第 2 条：主城按钮；
- 第 3 条：矿场按钮；
- 第 4 条：农场按钮。

每条保持独立 JSON，避免把十几个按钮塞进一条命令。

## 13. 测试顺序

1. `tellraw @p {"rawtext":[{"text":"tellraw test","color":"green"}]}` 验证目标。
2. 加 `hoverEvent`，确认提示显示。
3. 加 `clickEvent`，先用 `suggest_command` 验证框内内容。
4. 改为 `run_command`，验证执行者与权限。
5. 再广播 `tellraw @a ...`。
