"""运行路径与日志输出。

依赖方向: 最底层叶子模块, 不 import 任何项目内模块。

LOG_PATH / SERVER_LOG_PATH / SESSION_DIR / ONESHOT_DIR 是运行时可变值(自测会重绑到
临时目录)。其它模块必须按 `paths.X` 属性读取, 不要 from-import 具体值, 否则拿不到重绑。
"""
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # 仓库根目录(本文件在 viktor/ 包内)
CONFIG_PATH = BASE_DIR / "config.json"
LOG_DIR = BASE_DIR / "logs"
LOG_PATH = LOG_DIR / "bot.log"  # 自测会指到临时文件, 避免假记录污染生产日志
SERVER_LOG_PATH = LOG_DIR / "server.log"  # 同上: 自测写入的假回包行不能被线上读到
SESSION_DIR = LOG_DIR / "sessions"
ONESHOT_DIR = LOG_DIR / "oneshot"  # 每次一次性对话单独落盘, 便于并发时排障
STATE_PATH = LOG_DIR / "agent.state"  # 忙碌/空闲状态快照, 供外部脚本(重启守卫)读取


def log(msg: str):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")
