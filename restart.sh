#!/usr/bin/env bash
# 平滑重启 mc-ai-bot: 优雅退出(落盘当前会话) → 带 VIKTOR_RESTORE 自动灌回, 对玩家无感。
# 用法: ./restart.sh
set -euo pipefail
cd "$(dirname "$0")"
REPO="$PWD"

# 找 bot 进程: 命令行里含 bot.py 的 python3(脚本自身命令行不含 bot.py, 不会误伤)
find_bot_pids() {
    local p cmd
    for p in $(pgrep -x python3 2>/dev/null || true); do
        cmd=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null || true)
        case "$cmd" in *bot.py*) echo "$p" ;; esac
    done
}

mapfile -t pids < <(find_bot_pids)
dump=""

if [ "${#pids[@]}" -gt 0 ]; then
    if [ "${#pids[@]}" -ne 1 ]; then
        echo "错误: 发现多个 bot 进程, 请先手动清理: ${pids[*]}" >&2
        exit 1
    fi
    pid="${pids[0]}"
    echo "优雅退出 bot (pid $pid) ..."
    kill -TERM "$pid"
    for _ in $(seq 1 30); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
    done
    if kill -0 "$pid" 2>/dev/null; then
        echo "错误: bot 未在 15s 内退出; 如需强杀: kill -KILL $pid" >&2
        exit 1
    fi
    latest=$(ls -t logs/sessions/session-*.jsonl 2>/dev/null | head -1 || true)
    if [ -n "$latest" ]; then
        dump="$REPO/$latest"
        echo "已落盘会话: $dump"
    else
        echo "警告: 未找到落盘会话, 将全新启动"
    fi
else
    echo "没有正在运行的 bot, 全新启动"
fi

screen -wipe >/dev/null 2>&1 || true  # 清理可能残留的死屏

if [ -n "$dump" ]; then
    screen -dmS viktor bash -c "cd '$REPO' && VIKTOR_RESTORE='$dump' ./run.sh"
else
    screen -dmS viktor bash -c "cd '$REPO' && ./run.sh"
fi
sleep 2
echo "已启动:"
screen -ls | grep -E '\.(viktor|mc)\b' || true
