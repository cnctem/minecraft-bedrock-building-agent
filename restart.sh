#!/usr/bin/env bash
# 平滑重启 mc-ai-bot: 优雅退出(落盘当前会话) → 带 VIKTOR_RESTORE 自动灌回, 对玩家无感。
# 用法: ./restart.sh [session]
#   session 可选:
#     - 指定要灌回的会话(绝对路径, 或 logs/sessions/ 下唯一的文件名/子串);
#     - 省略时: 若优雅退出了正在运行的 bot, 灌回它刚落盘的会话; 否则全新启动。
#
# 健壮性(2026-10-13):
#   「先杀后起」本身不是原子操作 —— 一旦在这两步之间被打断(终端掉线/SSH 断/Ctrl-C/
#   某条命令失败), 结果就是旧 bot 已死、新 bot 没起, 且脚本无声退出。为此:
#     1) 忽略 SIGHUP: 关终端/SSH 掉线不再打断重启;
#     2) EXIT 兜底: 只要已经对旧 bot 动过手、退出时却仍没有 bot 进程, 就自动拉起;
#     3) 启动前清掉同名残留 screen 会话并等它真正消失, 启动带重试;
#     4) 启动后校验 bot 进程真的在跑, 失败以非 0 退出码报警。
set -euo pipefail
cd "$(dirname "$0")"
REPO="$PWD"
SCREEN_NAME=viktor

trap '' HUP  # 终端挂断(SIGHUP)不打断重启, 避免卡在“杀了没起”的中间态

# 解析可选的 session 参数 -> 绝对路径; 找不到/多个匹配时报错退出
resolve_restore() {
    local arg="$1" m matches=()
    if [ -f "$arg" ]; then
        readlink -f "$arg"
        return
    fi
    while IFS= read -r m; do matches+=("$m"); done \
        < <(ls -1t logs/sessions/*"$arg"* 2>/dev/null || true)
    if [ "${#matches[@]}" -eq 0 ]; then
        echo "错误: 找不到匹配的会话: $arg" >&2
        return 1
    fi
    if [ "${#matches[@]}" -gt 1 ]; then
        echo "匹配到多个会话(共 ${#matches[@]} 个, 按时间新→旧; 最多列出 10 个), 请指定其一:" >&2
        local i=1
        for m in "${matches[@]:0:10}"; do
            printf '  [%d] %s  (%s 条消息, %s)\n' "$i" "${m##*/}" \
                "$(wc -l < "$m" | tr -d ' ')" "$(date -r "$m" '+%Y-%m-%d %H:%M:%S')" >&2
            i=$((i + 1))
        done
        return 1
    fi
    readlink -f "${matches[0]}"
}

# 找 bot 进程: 命令行里含 bot.py 的 python3(本脚本自身命令行不含 bot.py, 不会误伤)
find_bot_pids() {
    local p cmd
    for p in $(pgrep -x python3 2>/dev/null || true); do
        cmd=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null || true)
        case "$cmd" in *bot.py*) echo "$p" ;; esac
    done
}

has_bot() { if [ -n "$(find_bot_pids)" ]; then return 0; else return 1; fi; }

screen_alive() {
    if screen -ls 2>/dev/null | grep -qE "\.${SCREEN_NAME}\b"; then return 0; else return 1; fi
}

# 启动新 bot: 清残留 screen 会话 → 带重试启动 → 校验 bot 进程真的起来了
start_bot() {
    local i j
    if screen_alive; then
        screen -S "$SCREEN_NAME" -X quit >/dev/null 2>&1 || true
    fi
    for i in $(seq 1 20); do     # 等旧 screen 会话的 socket 真正消失(最多 10s)
        if ! screen_alive; then break; fi
        sleep 0.5
    done
    screen -wipe >/dev/null 2>&1 || true

    for i in $(seq 1 5); do      # 启动重试(最多 5 轮)
        if [ -n "$dump" ]; then
            screen -dmS "$SCREEN_NAME" bash -c \
                "cd '$REPO' && VIKTOR_RESTORE='$dump' ./run.sh" || true
        else
            screen -dmS "$SCREEN_NAME" bash -c "cd '$REPO' && ./run.sh" || true
        fi
        for j in $(seq 1 10); do     # 等 bot 进程出现(最多 5s)
            if has_bot; then return 0; fi
            sleep 0.5
        done
        echo "警告: 第 $i 次启动后未见 bot 进程, 重试 ..." >&2
        screen -wipe >/dev/null 2>&1 || true
    done
    return 1
}

killed=0   # 是否已经对旧 bot 动过手(供 EXIT 兜底判断)
dump=""
on_exit() {
    local rc=$?
    trap - EXIT
    if [ "$killed" = 1 ] && ! has_bot; then
        echo "警告: 重启过程中断且 bot 未运行, 自动拉起 ..." >&2
        if start_bot; then
            echo "已自动恢复: bot pid $(find_bot_pids | tr '\n' ' ')"
        else
            echo "错误: 自动拉起失败, 请手动检查: $REPO/run.sh" >&2
        fi
        rc=1   # 中断恢复过, 以非 0 退出码让调用方/自动化能察觉
    fi
    exit "$rc"
}
trap on_exit EXIT

if [ -n "${1:-}" ]; then
    dump="$(resolve_restore "$1")" || exit 1
    echo "指定回溯会话: $dump"
fi

mapfile -t pids < <(find_bot_pids)

if [ "${#pids[@]}" -gt 0 ]; then
    if [ "${#pids[@]}" -ne 1 ]; then
        echo "错误: 发现多个 bot 进程, 请先手动清理: ${pids[*]}" >&2
        exit 1
    fi
    pid="${pids[0]}"
    echo "优雅退出 bot (pid $pid) ..."
    kill -TERM "$pid"
    killed=1
    for _ in $(seq 1 30); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
    done
    if kill -0 "$pid" 2>/dev/null; then
        echo "错误: bot 未在 15s 内退出; 如需强杀: kill -KILL $pid" >&2
        exit 1
    fi
    if [ -z "$dump" ]; then  # 未指定会话: 灌回刚优雅落盘的那份
        latest=$(ls -t logs/sessions/session-*.jsonl 2>/dev/null | head -1 || true)
        if [ -n "$latest" ]; then
            dump="$REPO/$latest"
            echo "已落盘会话: $dump"
        else
            echo "警告: 未找到落盘会话, 将全新启动"
        fi
    fi
else
    echo "没有正在运行的 bot"
    [ -n "$dump" ] && echo "按指定会话启动" || echo "全新启动"
fi

if start_bot; then
    echo "已启动:"
    screen -ls | grep -E '\.(viktor|mc)\b' || true
    echo "bot pid: $(find_bot_pids | tr '\n' ' ')"
else
    echo "错误: bot 启动失败(screen 会话或进程都没起来)" >&2
    exit 1
fi
