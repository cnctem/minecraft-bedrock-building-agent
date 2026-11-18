#!/usr/bin/env bash
# 为已运行的 BDS 配置 screen 日志，然后启动 Agent。
set -euo pipefail
cd -- "$(dirname -- "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
command -v screen >/dev/null || { echo "错误: 请先安装 screen" >&2; exit 1; }
mc_screen=$("$PYTHON_BIN" -c 'from agent.config import load_config; s = load_config()["screen_session"]; assert isinstance(s, str) and s.strip() and "\n" not in s; print(s)')
if ! screen -S "$mc_screen" -Q windows >/dev/null 2>&1; then
    echo "错误: 找不到 BDS screen 会话: $mc_screen" >&2
    exit 1
fi
mkdir -p logs
screen -S "$mc_screen" -X width 400 24 || true
screen -S "$mc_screen" -X logfile "$PWD/logs/server.log"
screen -S "$mc_screen" -X log on
screen -S "$mc_screen" -X logfile flush 1
exec "$PYTHON_BIN" bot.py "$@"
