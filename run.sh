#!/usr/bin/env bash
# 启动 mc-ai-bot。screen 的日志设置在 MC 服务器重启后会失效, 每次启动前重新应用。
set -euo pipefail
cd "$(dirname "$0")"

if ! screen -list | grep -q "\.mc\b"; then
    echo "错误: 找不到名为 mc 的 screen 会话(MC 服务器未运行?)" >&2
    exit 1
fi

# 加宽窗口减少日志折行; 开启输出日志供 tail; flush 间隔调小否则抓不到指令输出
screen -S mc -X width 400 24 || true
screen -S mc -X logfile "$PWD/logs/server.log" || true
screen -S mc -X log on || true
screen -S mc -X logfile flush 1 || true

exec python3 bot.py
