"""Linux 启动辅助：定位当前仓库实例、检查任务空闲、解析会话路径。"""
import argparse
import json
import sys
import time
from pathlib import Path

from . import paths


def instance_pids(repo: Path, proc_root: Path = Path("/proc")) -> list[int]:
    """只认当前仓库内运行 bot.py 的进程，不按 Python 进程名全局匹配。"""
    repo = repo.resolve()
    found = []
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if (entry / "cwd").resolve(strict=True) != repo:
                continue
            args = (entry / "cmdline").read_bytes().decode().split("\0")
            if not args or not Path(args[0]).name.startswith("python"):
                continue
            script = next((arg for arg in args[1:] if arg not in ("-u", "-B", "-E", "-s")), "")
            if script and (repo / script).resolve() == repo / "bot.py":
                found.append(int(entry.name))
        except (OSError, UnicodeError, RuntimeError):
            continue
    return sorted(found)


def require_idle(pid: int, state_path: Path, repo: Path, *, now: float | None = None) -> None:
    """拒绝忙碌、过期或无法归属当前实例的状态，不向进程发送信号。"""
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise ValueError("任务状态格式无效")
    if state.get("pid") != pid or state.get("repo") != str(repo.resolve()):
        raise ValueError("任务状态不属于当前仓库实例")
    age = (time.time() if now is None else now) - float(state["updated"])
    if not -1 <= age <= 5:
        raise ValueError("任务状态已过期，请确认 Agent 正常运行")
    if state.get("busy") is not False or any(
        state.get(key) for key in ("pending", "compact", "oneshot_active")
    ):
        raise ValueError("Agent 正在执行任务，请等待任务结束或先在游戏中停止")


def resolve_session(arg: str, directory: Path) -> Path:
    explicit = Path(arg).expanduser()
    if explicit.is_file():
        return explicit.resolve()
    matches = sorted(p for p in directory.glob("*.jsonl") if arg in p.name)
    if len(matches) != 1:
        raise ValueError(f"会话匹配数量为 {len(matches)}，请指定完整路径或唯一文件名")
    return matches[0].resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("pids", "guard", "resolve", "latest"))
    parser.add_argument("value", nargs="?")
    args = parser.parse_args()
    try:
        if args.action == "pids":
            for pid in instance_pids(paths.BASE_DIR):
                print(pid)
        elif args.action == "guard":
            require_idle(int(args.value), paths.STATE_PATH, paths.BASE_DIR)
        elif args.action == "resolve":
            print(resolve_session(args.value, paths.SESSION_DIR))
        else:
            dumps = list(paths.SESSION_DIR.glob("session-*.jsonl"))
            if dumps:
                print(max(dumps, key=lambda p: p.stat().st_mtime).resolve())
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
