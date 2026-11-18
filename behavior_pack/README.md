# Agent Bridge 行为包

源码位于 [agent_bridge](agent_bridge/)，与 Python Agent 使用协议 v5。
行为包订阅聊天、查询空间、读取快照并执行建造事务。

## 安装（仅部署服务器）

将示例路径替换为实际位置：

~~~bash
ln -s /path/to/mc-ai-bot/behavior_pack/agent_bridge /path/to/bds/behavior_packs/agent_bridge
~~~

在世界的 world_behavior_packs.json 中启用 manifest 的 header UUID：

~~~json
[
  {
    "pack_id": "2c6a2552-7f38-4494-8811-f082a8769065",
    "version": [1, 0, 0]
  }
]
~~~

参考 BDS 版本为 1.21.132.3，依赖 @minecraft/server = 2.5.0-beta。
需要启用相应实验脚本能力；稳定版 API 不提供本项目使用的聊天订阅能力。
安装或修改 manifest 后需要重启 BDS；仅改脚本时可在空闲时 reload。
操作前核实部署环境、在线玩家与 Agent 状态。

## 验证

开发机只做：

~~~bash
node --check behavior_pack/agent_bridge/scripts/main.js
python3 bot.py --test
~~~

部署服务器空闲时，可在 BDS 控制台做短小只读握手：

~~~text
scriptevent agent:hello check
→ [AGENT-HELLO] check v5
scriptevent agent:caps r1
→ [AGENT-CAPS] r1 ... DONE
~~~

reload 会中断扫描并清空建造暂存、撤销栈。BDS screen 重建后重新执行 Agent 启动入口应用日志设置。
请求、分帧、限额与回包见[协议文档](../docs/behavior-pack.md)。
