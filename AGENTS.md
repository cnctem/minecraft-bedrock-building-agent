# AGENTS.md — mc-ai-bot 工作指南

先区分开发设备与部署服务器。仓库中的部署脚本不代表本机正在运行 Minecraft。
项目介绍见 [README.md](README.md)，技术文档见 [docs/README.md](docs/README.md)。

## 环境与操作

- 开发设备可以修改源码、运行离线自测、JS/Shell 语法检查和生成器检查；不要执行启动、重启、
  reload 或世界操作。环境不明确时按开发设备处理。
- 部署服务器必须先核实目录、BDS 进程、screen 会话、在线玩家及任务状态。
  有玩家或 Agent 忙时优先只读；不要主动 reload、重启或扫描世界。
- `busy = agent_busy or pending 非空 or 智能压缩运行中`。重启还须确认一次性任务为零。
  `logs/agent.state` 是任务状态快照，不能用过期快照证明空闲。
- 使用 `./restart.sh` 优雅重启；它只操作当前仓库的 Agent。BDS screen 重建后重新运行启动入口。
- reload 会中断扫描并清空建造暂存和撤销栈；实际操作后需验证 hello/caps。
  开发机不能声称完成了线上握手或世界验证。

## 架构与不变量

- Python 3.11+、零第三方 Python 依赖；单套 DeepSeek 配置，基础字段为 `api_key/api_base/model`。
- `bot.py → Bot 职责 mixin → session/bus/bridge/config/profiles → paths/constants/prompts/schemas`。
  mixin 之间不互相 import，通过组合后的 `self.*` 协作；下层不依赖上层。
- `paths` 的可重绑值通过 `paths.X` 读取，不要 from-import 固定路径值。
- 上下文平时 append-only；切模式、记忆更新只追加系统注记，不重写固定前缀。
  只有普通压缩、智能压缩和完整初始化可以重建上下文。
- 不在 tool_calls 与全部 tool 响应之间插入消息；中断也要补齐工具响应。
- DeepSeek 联网是服务端工具，不注册本地 handler，也不允许通过 ptc 调用。
  `server_tool_calls` 原样回传，带工具调用的 assistant 保留 `reasoning_content`。
- 玩家图片 URL 附在原 user 消息中；工具渲染图在 tool 响应之后追加为带系统说明的 user 消息。
  tool 消息只放文本。

## 修改工具与建造

新增或修改工具时同步检查 schema、handler、注册、parallel/bus/serial 并发类别、全部模式白名单、
执行层黑名单和 ptc 子线程限制，并更新自测与模块文档。
建造事务仅 creative/creative_max 可用；pin_region 仅创造模式可用。

- Python 编译纯几何，行为包读写世界；沙箱不得增加文件、网络或直接世界访问。
- KEEP 表示不写不删，挖空必须显式 air。
- commit 重新 diff，再 verify；mismatch 与 unloaded 分开报告。
- 门、床、高草由编译器处理，不要改回一律拒绝。
- 当前行为包协议 v5。修改协议同步 JS、Python 常量、总线、工具与文档；
  保持请求 ID、DONE、分帧、缺帧失败和超时语义。建造上行 560 字符/帧，一帧一次 screen stuff。

## 检查与文档

```bash
python3 bot.py --test
node --check behavior_pack/agent_bridge/scripts/main.js
bash -n run.sh
bash -n restart.sh
python3 tools/gen_buildlib_docs.py --check
```

自测必须使用临时目录和假凭据，不依赖真实 config、日志、记忆或部署目录。
保留权限、沙箱与工具配对断言，不能为了通过检查放宽约束。

`agent/buildlib/registry.py` 是函数签名元数据唯一来源；修改后运行
`python3 tools/gen_buildlib_docs.py`，再执行 `--check`。
技能理论资料直接维护在 `skills/`，不需要外部项目文件。
行为变更更新对应模块文档；README 只保留介绍、快速开始和入口。
改名后检查 Markdown 链接、路径和交叉引用。

## 本地数据

`config.json`、`memory.md` 和 `logs/` 不得提交。密钥示例只用占位符。
施工台账和建造程序源码同属运行数据；记录由程序自动完成，不给模型增加记录参数或强制调用。
不要在不同环境之间覆盖配置或复制私人会话。
