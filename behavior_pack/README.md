# 行为包源码（viktor_bridge）

这里是 **BDS 行为包 `viktor_bridge` 的唯一源码位置**。在参考部署服务器上，
`/home/jrj/minecraft-bedrock/behavior_packs/viktor_bridge` 是指向本目录的**软链接**；其他部署应使用各自的仓库和 BDS 路径。
开发设备上的独立 checkout 可以只有源码，不意味着它已经连接到某个线上服务器。

在已配置软链接的部署中：

- 改这里的 `scripts/main.js` = 改服务器上正在用的脚本，不需要拷贝/同步；
- 提交到本仓库即等于给行为包做了版本管理（改之前能随时回滚）；
- **不要**把软链接换成实体目录（会出现两份拷贝、互相漂移）。

```text
~/repo/mc-ai-bot/behavior_pack/viktor_bridge   ← 改这里（git 跟踪）
        ▲ 软链接
        └─ ~/minecraft-bedrock/behavior_packs/viktor_bridge   ← BDS 读这里
```

## 生效方式

| 改动内容 | 生效方式 |
|---|---|
| `scripts/main.js`（脚本逻辑） | 控制台 `reload` **热重载**，不必重启服务器 |
| `manifest.json`（依赖/版本/UUID） | 必须**重启服务端**，`reload` 不重读 manifest |

改完先 `node --check scripts/main.js` 过一遍语法（BDS 报错信息很难读），再 `reload`；
`reload` 后用 `scriptevent viktor:hello test` 验一下握手是否还回 `[VIKTOR-HELLO] test v4`。

依赖版本（BDS 1.21.132.3）：`@minecraft/server` = `2.5.0-beta`，`@minecraft/server-ui` = `2.1.0-beta`。
稳定版 `2.4.0`/`2.0.0` 能加载但 `world.beforeEvents.chatSend` 为 undefined（聊天桥会失效），不要改回去。

## 协议

脚本实现的行为包协议见 [`docs/behavior-pack.md`](../docs/behavior-pack.md)（当前协议 **v4**：请求 id 路由、
分帧回包、空间感知、世界快照与建造引擎）。服务器有玩家或 Bot 忙时不要随意 `reload`：重载会中断正在进行的扫描，
并清空建造暂存与撤销栈。

如果当前只是开发设备、没有运行中的 BDS，只做 `node --check` 和离线自测即可；不要假定这里一定已软链接到线上服务器。
环境判断见根目录 [`AGENTS.md`](../AGENTS.md)。

## 备份

参考部署机上可能留有纳入 git 前的原始副本 `/home/jrj/viktor_bridge.pre-git.backup.20261023`（仅作应急，
先确认文件确实存在；它不属于本仓库，开发设备不要假定可用）。注意**不要**把备份目录放进 `behavior_packs/` 里——
BDS 会把它当第二个包扫到，UUID 冲突会导致加载失败。
