#!/usr/bin/env bash
# Linux / Bash 4+: 空闲检查 → 优雅退出 → 恢复会话。仅操作当前仓库的 Agent。
set -euo pipefail
cd -- "$(dirname -- "$0")"
REPO="$PWD"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SCREEN_NAME="${AGENT_SCREEN_NAME:-agent}"
trap '' HUP
command -v screen >/dev/null || { echo "错误: 请先安装 screen" >&2; exit 1; }
[[ -d /proc ]] || { echo "错误: restart.sh 需要 Linux /proc" >&2; exit 1; }

find_bot_pids() { "$PYTHON_BIN" -m agent.runtime pids; }
screen_alive() { screen -S "$SCREEN_NAME" -Q windows >/dev/null 2>&1; }

dump=""
if [[ -n "${1:-}" ]]; then
    dump=$("$PYTHON_BIN" -m agent.runtime resolve "$1")
fi
pid_list=$(find_bot_pids)
pids=()
if [[ -n "$pid_list" ]]; then mapfile -t pids <<< "$pid_list"; fi
if (( ${#pids[@]} > 1 )); then
    echo "错误: 当前仓库有多个 Agent 进程，请先检查: ${pids[*]}" >&2
    exit 1
fi
if (( ${#pids[@]} == 0 )) && screen_alive; then
    echo "错误: screen $SCREEN_NAME 已被占用，请检查或设置 AGENT_SCREEN_NAME" >&2
    exit 1
fi
if (( ${#pids[@]} == 1 )); then
    "$PYTHON_BIN" -m agent.runtime guard "${pids[0]}"
    if screen_alive && [[ "${STY:-}" == *".$SCREEN_NAME" ]]; then
        echo "错误: 请从 Agent screen 会话之外执行重启" >&2
        exit 1
    fi
fi

start_bot() {
    local i j
    for i in 1 2 3; do
        if screen_alive; then
            echo "错误: screen $SCREEN_NAME 已被占用，停止启动" >&2
            return 1
        fi
        screen -dmS "$SCREEN_NAME" env "AGENT_RESTORE=$dump" "PYTHON_BIN=$PYTHON_BIN" \
            bash -c 'cd -- "$1" && exec ./run.sh' _ "$REPO" || return 1
        for j in {1..20}; do
            pid_list=$(find_bot_pids) || return 1
            if [[ -n "$pid_list" ]]; then return 0; fi
            sleep 0.25
        done
        if screen_alive; then
            echo "错误: screen $SCREEN_NAME 仍在运行但未见 Agent，请检查该会话" >&2
            return 1
        fi
        echo "警告: 第 $i 次启动未见当前仓库的 Agent 进程" >&2
    done
    return 1
}

stopped=0
on_exit() {
    local rc=$?
    trap - EXIT
    if [[ "$stopped" == 1 ]]; then
        if ! pid_list=$(find_bot_pids); then
            echo "错误: 无法确认 Agent 进程，请检查后执行 ./run.sh" >&2
            rc=1
        elif [[ -z "$pid_list" ]]; then
            echo "重启过程未完成，尝试重新启动 Agent ..." >&2
            start_bot || echo "错误: 自动启动失败，请检查 logs/bot.log 并执行 ./run.sh" >&2
            rc=1
        fi
    fi
    exit "$rc"
}
trap on_exit EXIT

if (( ${#pids[@]} == 1 )); then
    pid="${pids[0]}"
    echo "优雅退出当前仓库的 Agent (PID $pid) ..."
    kill -TERM "$pid"
    stopped=1
    for _ in {1..60}; do
        if ! kill -0 "$pid" 2>/dev/null; then break; fi
        sleep 0.25
    done
    if kill -0 "$pid" 2>/dev/null; then
        echo "错误: Agent 未在 15 秒内退出，请检查后重试" >&2
        exit 1
    fi
    # 不清理无法确认归属的 screen；旧会话应随 Agent 的 exec 进程退出。
    for _ in {1..20}; do
        if ! screen_alive; then break; fi
        sleep 0.25
    done
    if screen_alive; then
        echo "错误: screen $SCREEN_NAME 仍被占用，请检查" >&2
        stopped=0
        exit 1
    fi
    if [[ -z "$dump" ]]; then dump=$("$PYTHON_BIN" -m agent.runtime latest); fi
fi
if ! start_bot; then
    echo "错误: Agent 启动失败" >&2
    exit 1
fi
stopped=0
echo "Agent 已启动，screen: $SCREEN_NAME，PID: $pid_list"
