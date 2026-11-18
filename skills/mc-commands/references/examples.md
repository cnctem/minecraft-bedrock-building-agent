# tellraw 文本模板

所有命令通过 run_server_command 执行，不带前导斜杠。

## 公告

~~~text
tellraw @a {"rawtext":[{"text":"§6[公告] §e今晚 8 点主城集合。"}]}
~~~

## 坐标与网址

~~~text
tellraw @p {"rawtext":[{"text":"§a喷泉广场：120 65 -40"}]}
tellraw @p {"rawtext":[{"text":"地图：https://example.com/map"}]}
~~~

## 施工进度

~~~text
tellraw @a {"rawtext":[{"text":"§7[施工] §f地基已通过校验，下一步搭建桥墩。"}]}
~~~

需要多条消息时，用 ptc 依次调用 run_server_command。文字变量须先进行 JSON 转义；
未完成校验时不要使用“施工完成”的模板。
