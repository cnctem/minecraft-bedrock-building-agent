#!/usr/bin/env python3
"""回填施工台账(agent/ledger.py) —— 一次性把历史会话变成可查询的记录。

台账是运行时自动写的(切创造/预览/提交/撤销各写一行), 这个脚本只负责把**台账上线之前**
的历史补进去: 扫 logs/sessions 与 logs/oneshot 的 JSONL, 必要时用 logs/bot.log 里的
`[建造] 预览/提交/撤销 <jid>` 行补精确时间, 再按 jid 去重(恢复会话会把同一批调用再落一份)。

幂等: 已经记过的 episode(同玩家+理由+触发原话)与批次(同 jid)不会再写, 可以重复跑。
建议在 bot 停止时跑: 运行中的 bot 也往同一份台账追加, 两边同时分配记录编号会撞号
(撞号只影响记录顺序的可读性, 不影响按 episode/jid 查询)。

用法:
  python3 tools/backfill_build_ledger.py --dry-run     # 只看会写多少, 不落盘
  python3 tools/backfill_build_ledger.py               # 回填(默认连程序源码一起存)
  python3 tools/backfill_build_ledger.py --no-programs # 只回填台账, 不存程序源码
  python3 tools/backfill_build_ledger.py --bot-log /path/to/bot.log
"""
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from agent import build, ledger, paths  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="把历史会话回填成施工台账")
    ap.add_argument("--bot-log", default=None, help="用哪个日志补 jid 时间(默认 logs/bot.log)")
    ap.add_argument("--no-programs", action="store_true", help="不保存建造程序源码")
    ap.add_argument("--dry-run", action="store_true", help="只统计, 不写台账")
    ap.add_argument("--reset", action="store_true",
                    help="先清空台账(仅台账与 program 目录, 不动会话文件)再回填")
    args = ap.parse_args()

    if args.reset:
        if args.dry_run:
            print("--reset 不能和 --dry-run 一起用")
            return 2
        for p in (paths.LEDGER_PATH,):
            try:
                p.unlink()
            except FileNotFoundError:
                pass
        print(f"已清空 {paths.LEDGER_PATH}(程序源码目录 {paths.PROGRAM_DIR} 保留, 按 jid 覆盖)")

    stats = ledger.backfill(bot_log=args.bot_log,
                            save_programs=not args.no_programs,
                            dry_run=args.dry_run,
                            block_ids=build.block_ids())
    print(f"台账: {paths.LEDGER_PATH}")
    print(f"扫到 episode {stats['candidates']} 个 → 新增 episode {stats['episodes']} 个, "
          f"跳过重复 {stats['skipped_episodes']} 个")
    print(f"新增批次 {stats['ops']} 个, 跳过重复 {stats['skipped_ops']} 个, "
          f"存程序源码 {stats['programs']} 份")
    if args.dry_run:
        print("(dry-run: 没有写盘)")
    else:
        total = len(ledger.load())
        print(f"台账现有 {total} 条记录; 之后用 find_builds / read_build 查询")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
