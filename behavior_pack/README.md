# 行为包源码（viktor_bridge）

这里是 **BDS 行为包 `viktor_bridge` 的唯一源码位置**。服务器目录
`/home/jrj/minecraft-bedrock/behavior_packs/viktor_bridge` 是指向本目录的**软链接**，
所以：

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
`reload` 后用 `scriptevent viktor:hello test` 验一下握手是否还回 `[VIKTOR-HELLO] test v2`。

## 协议

脚本实现的行为包协议见仓库根 `README.md` 的「行为包脚本桥」一节（协议 v2：请求 id 回显 +
`system.runJob` 非阻塞扫描）。服务器不在人少/无人时不要随意 `reload`：重载会中断正在进行的扫描。

## 备份

纳入 git 之前的原始副本留在 `/home/jrj/viktor_bridge.pre-git.backup.20261023`（仅作应急，
确认历史提交可用后可删）。注意**不要**把备份目录放进 `behavior_packs/` 里——BDS 会把它当第二个包扫到，
UUID 冲突会导致加载失败。
