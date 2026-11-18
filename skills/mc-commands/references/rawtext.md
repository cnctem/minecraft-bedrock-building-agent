# Bedrock rawtext 参考

run_server_command 中命令不带前导斜杠：

~~~text
tellraw @a {"rawtext":[{"text":"§6[提示] §f文字内容"}]}
~~~

顶层为含 rawtext 数组的对象，可使用 text、selector、score、translate 及相应 with 参数：

~~~json
{"rawtext":[{"text":"在线玩家："},{"selector":"@a"}]}
~~~

颜色和样式写在 text 字符串中的 § 格式码里，例如 §6 金色、§a 绿色、§l 粗体、§r 重置。
不同组件连续显示，空格需显式写出。

使用 JSON 序列化处理引号、反斜杠和换行，避免拼接未转义的玩家输入。
多行说明可分成多条 tellraw，通过 ptc 顺序提交。选择明确的目标，坐标与网址用文字列出。
