# 运行与控制

## 1. 环境

开发设备只需 Python 3.11+。离线自测使用假配置与临时目录，不需要 Minecraft 或 API key。
修改行为包建议安装 Node.js；Shell 脚本可静态检查。

部署辅助面向 Linux，重启脚本需要 Bash 4+ 和 `/proc`，并依赖 screen。
BDS 必须已经运行，默认位于 `mc` 会话；Agent 默认使用独立的 `agent` 会话。
脚本只管理本仓库 Agent，不启动或重启 BDS。

## 2. 配置与启动

复制 `config.example.json` 为 `config.json`，填写 DeepSeek key，核对 `screen_session`。
行为包安装见[行为包说明](../behavior_pack/README.md)。

```bash
./run.sh
# 指定 Python：
PYTHON_BIN=/path/to/python3 ./run.sh
# 后台启动：
screen -dmS agent bash -c 'cd /path/to/mc-ai-bot && exec ./run.sh'
```

启动入口创建日志目录，读取配置的 BDS screen 名，设置日志文件、刷新间隔和宽度后启动 Python。
BDS screen 重建后，必须再次运行启动入口应用这些设置。
每个仓库实例应使用独立的 Agent screen 名。

## 3. 自测与平滑重启

```bash
python3 bot.py --test
node --check behavior_pack/agent_bridge/scripts/main.js
bash -n run.sh
bash -n restart.sh
python3 tools/gen_buildlib_docs.py --check
```

自测使用临时目录、假凭据和 screen/API 桩，不读取真实运行数据，不执行世界操作。
Python 自测与语法检查不能代替 BDS 实测。

仅在已确认的部署服务器、玩家与 Agent 均适合操作时使用：

```bash
./restart.sh
./restart.sh session-....jsonl
AGENT_SCREEN_NAME=agent-other ./restart.sh
```

脚本按工作目录和脚本路径定位本仓库实例，检查 `logs/agent.state`：
PID、仓库路径必须匹配，更新时间不超过 5 秒，主任务、队列、智能压缩及一次性任务均须空闲。
缺失、过期或不匹配的状态会拒绝重启。多个实例或无法确认归属的同名 screen 也会拒绝操作。
先结束任务时在游戏里发送停止控制词；脚本不会自动中止任务。

重启使用 SIGTERM，让会话落盘，再通过 `AGENT_RESTORE` 恢复。
退出超时会报错，不自动强杀。启动失败会有限重试，已退出后流程中断会尝试重新启动并返回失败状态。
可指定绝对会话路径、当前路径中的文件或 sessions 中的唯一文件名片段。
若原本没有运行实例且未指定会话，则全新启动。

## 4. 控制词总表

控制词完全匹配，由程序处理，不进入模型上下文。

| 输入 | 行为 |
|---|---|
| `停止` | 当前步骤结束、工具往返闭合后停止主任务，清空待处理队列 |
| `强制停止` | 立即中止主任务及可中止的请求等待 |
| `不停止` | 撤销尚未生效的停止请求 |
| `清空` | 空闲时落盘旧会话并初始化 |
| `压缩` | 空闲时只保留玩家文字与实际发言 |
| `智能压缩` | 空闲时生成工作摘要后重建上下文 |
| `恢复会话` | 空闲时恢复最近实际对话 |
| `正文开` / `正文关` | 正文观察开关，默认关 |
| `工具开` / `工具关` | 工具调用摘要开关，默认开 |
| `1 ...` | 隔离的一次性任务 |
| `1 强制停止` | 中止全部一次性任务 |
| `0 ...` | 静默消息 |

## 5. 错误与状态

重试仅针对限流、瞬态错误与网络异常；参数和鉴权错误不重复请求。
失败以 `[系统]` 提示模型 ID、状态码及简短原因，不写入虚构的 assistant 回复。
强制停止属于任务中止，不作为 API 故障播报。

`agent.state` 包含 PID、repo、busy、pending、compact、oneshot_active、mode、updated。
它是重启辅助快照，不是模型工具。日志、记忆、会话、台账及程序属于本地运行数据，不提交。
