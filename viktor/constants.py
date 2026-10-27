"""无状态常量: 日志正则、控制词、模式名、总线协议表、可重试 HTTP 码。

依赖方向: 叶子模块, 不 import 任何项目内模块。
"""
import re

# BDS 日志格式: [2026-10-10 14:15:11:690 INFO] <内容>
RE_LINE = re.compile(
    r"^\[\d{4}-\d{2}-\d{2} (\d{2}:\d{2}:\d{2}):\d+ (INFO|WARN|ERROR|DEBUG)\] (.*)$")
RE_CHAT = re.compile(r"^<([^>]+)> (.*)$")
# 行为包脚本桥: [Scripting] [VIKTOR-CHAT] 玩家名: 消息 (名字限定 ASCII, 避免误吃脚本报错行)
RE_BRIDGE = re.compile(r"^\[Scripting\] \[VIKTOR-CHAT\] (.{1,32}?): (.*)$")
RE_JOIN = re.compile(r"^Player connected: ([^,]+), xuid: (\d+)")
RE_LEAVE = re.compile(r"^Player disconnected: ([^,]+), xuid:")
RE_LIST = re.compile(r"^There are (\d+)/(\d+) players online")
# 协议 v3: 行为包把请求 id 原样回显在每一行里, 供 ServerBus 按 id 路由;
# 查询回包是「一个 JSON payload 分多帧」(`#i/n <片段>` 行 + DONE), 由 bus 重组。
BUS_ROUTE_RE = re.compile(
    r"\[VIKTOR-(POS|INV|BLOCK|MAP|SLICE|INSPECT|FIND|CAPS|BUILD|SNAP)\] (r\d+)(?:[ \t](.*))?$")
BUS_FRAME_RE = re.compile(r"^#(\d+)/(\d+) (.*)$", re.S)
RE_BPROG = re.compile(r"\[VIKTOR-BPROG\] (\S+) ([dwv]) (\d+)/(\d+)")
RE_HELLO = re.compile(r"\[VIKTOR-HELLO\] \S+ v(\d+)")
PACK_PROTO_SPATIAL = 3  # 感知原语(heightmap/slice/inspect/find)所需的行为包协议
PACK_PROTO_BUILD = 4    # 建造引擎(preview/commit/undo)所需的行为包协议
BUILD_FRAME_CHARS = 560 # 建造 payload 每帧字符数(整条命令 <~700, 见 [实测])
BUILD_TIMEOUT_SEC = 120 # 预览/提交/撤销的等待上限(大体积要跑好几秒)

# 控制面硬编码词: 完全匹配时直接中止正在运行的 Agent 任务(不走模型, 类似 Ctrl-C)
FORCE_STOP_WORD = "强制停止"  # 控制面: 立即中止当前任务(连工具内部等待也打断)
SOFT_STOP_WORD = "停止"      # 控制面: 到安全点停止(当前步骤做完、工具往返闭合后停)
NO_STOP_WORD = "不停止"       # 控制面: 撤销还未生效的停止/强制停止
PIN_NAME = "viktor_pin"  # 常加载区域命名前缀(仅创造/执行模式; 离开即清理)
CLEAR_WORD = "清空"  # 控制面: 默认模型的清空触发词(其余触发词见 models.py 的模型档案;
                     # 实际分发用 models.resolve_trigger, 这里只作默认值/文档)
COMPACT_WORD = "压缩"  # 控制面: 压缩会话上下文(只留玩家消息与发言, 不进上下文)
SMART_COMPACT_WORD = "智能压缩"  # 控制面: 用模型把上下文压成工作摘要(保留进度/坐标/建造状态)
SMART_COMPACT_AUTO_PCT = 95  # 上下文占用到输入预算的这个百分比就自动智能压缩(配置可覆盖)
STATUS_WORD = "状态"  # 控制面: 播报服务器进程/负载/在线玩家(任何玩家可触发, 不进上下文)
BACKUP_WORD = "备份"  # 控制面: 触发存档热备份(需空闲; 不可中止, 结果回执走 [系统])
PLAN_WORD = "计划模式"  # 控制面: 进入计划模式(任何玩家可触发, 程序处理)
EXIT_PLAN_WORD = "退出计划"  # 控制面: 退出计划模式回 normal(任何玩家可触发)
RESTORE_WORD = "恢复会话"  # 控制面: 把最近一次落盘的会话灌回(任何玩家可触发)
RESTORE_DEFAULT_WORD = "恢复会话d"  # 控制面: 同上, 但强制用默认模型(flash)灌回
BODY_ON_WORD, BODY_OFF_WORD = "正文开", "正文关"  # 控制面: 正文转发开关(不进上下文)
TOOL_ON_WORD, TOOL_OFF_WORD = "工具开", "工具关"  # 控制面: 工具转发开关(不进上下文)

# 运行模式(名字仅作标识; 行为/限制/工具白名单由三张 profile 表组合而成, 见下方 Mode/MODES)
MODE_NORMAL = "normal"
MODE_CREATIVE = "creative"
MODE_CREATIVE_MAX = "creative_max"
MODE_PLAN = "plan"        # 未来: 与用户对话确认/完善计划
MODE_EXECUTE = "execute"  # 未来: 只执行既定计划
MODE_ONESHOT = "oneshot"  # 只能由 "1 ..." 触发, set_mode 进不去/出不来/不可知
CREATIVE_MODES = (MODE_CREATIVE, MODE_CREATIVE_MAX)
PIN_MODES = (MODE_CREATIVE, MODE_CREATIVE_MAX, MODE_EXECUTE)  # 支持常加载: 创造家族 + 执行(施工)
HM_MAX_COLUMNS = 4096    # get_heightmap 列数上限(64×64), 与行为包硬上限一致
SLICE_MAX_CELLS = 4096   # get_slice 单面格数上限(64×64)
INSPECT_MAX_VOLUME = 32768   # inspect_region 体积上限(32×32×32)
FIND_MAX_VOLUME = 32768      # find_blocks 体积上限
CELLS_STATED = 256       # 体积查询里默认返回的单元/样本条数
CELLS_HARD = 512
CONTEXT_WARN_START_PCT = 70  # 上下文占用提醒起始档(第一次; 分母是模型窗口, 默认 1M)
CONTEXT_WARN_STEP_PCT = 10   # 之后每跨过这么多百分点再提醒一次(70/80/90...)
# 走服务端请求总线的查询工具: name -> (kind, 超时配置项)
BUS_TOOLS = {
    "get_player_position": ("pos", "position_timeout_sec"),
    "get_player_hand": ("inv", "inventory_timeout_sec"),
    "get_block": ("block", "block_timeout_sec"),
    "get_heightmap": ("map", "spatial_timeout_sec"),
    "get_slice": ("slice", "spatial_timeout_sec"),
    "inspect_region": ("inspect", "spatial_timeout_sec"),
    "find_blocks": ("find", "spatial_timeout_sec"),
    # 建造引擎走自己的超时(见 BUILD_TIMEOUT_SEC), 这里只登记 kind
    "build_preview": ("build", "spatial_timeout_sec"),
    "build_commit": ("build", "spatial_timeout_sec"),
    "build_undo": ("build", "spatial_timeout_sec"),
    "build_status": ("build", "spatial_timeout_sec"),
}
BUS_TIMEOUT_TEXT = {
    "get_player_position": "行为包脚本没有回应, 取不到坐标(可能脚本未加载)。",
    "get_player_hand": "行为包脚本没有回应, 取不到手持物品(可能脚本未加载)。",
    "get_block": "行为包脚本没有回应, 查不到方块(可能脚本未加载, 或区块未加载)。",
    "get_heightmap": "行为包脚本没有回应, 取不到高度图(可能脚本未加载), 或区域太大被区块未加载拖慢。",
    "get_slice": "行为包脚本没有回应, 取不到切面(可能脚本未加载), 或区域太大被区块未加载拖慢。",
    "inspect_region": "行为包脚本没有回应, 区域检查失败(可能脚本未加载), 或体积太大被区块未加载拖慢。",
    "find_blocks": "行为包脚本没有回应, 没找到(可能脚本未加载), 或体积太大被区块未加载拖慢。",
    "build_preview": "行为包没有回应建造预览(可能脚本未加载, 或 payload 没传完整)。",
    "build_commit": "行为包没有回应提交结果(可能脚本未加载); 若已写入一部分, 可用 build_undo 还原。",
    "build_undo": "行为包没有回应撤销结果(可能脚本未加载)。",
    "build_status": "行为包没有回应操作列表(可能脚本未加载)。",
    "snapshot": "行为包没有回应世界快照(可能脚本未加载, 或 scan 范围太大)。",
}
# 静默消息: "0 ..." 开头(或单一个 "0")是玩家之间的普通聊天, 程序直接丢弃,
# 既不进主对话队列也不进任何上下文, 模型完全看不到(不会接话、不唤醒会话)。
# 想对 bot 说话不要加前缀; 只有明确不想让 bot 掺和时才用 "0 "。
IGNORE_TRIGGER = re.compile(r"^0(?:[ \u3000]+|$)")
ONESHOT_TRIGGER = re.compile(r"^1(?:[ \u3000]+|$)")  # "1 " / "1　" 开头, 或单一个 "1" = 一次性对话
ONESHOT_FORCE_STOP = re.compile(r"^1[ \u3000]+强制停止$")  # 停止全部一次性对话


# 可重试的 HTTP 状态码: 限流/瞬态错误重试有意义; 4xx(400 参数错/401 鉴权)重试无意义。
RETRYABLE_HTTP = {408, 409, 425, 429, 500, 502, 503, 504}


class Aborted(Exception):
    """一次 API 请求被「强制停止」打断。不是 API 错误, 不该给玩家报错。
    放在这里(而不是 bot_agent)是因为控制面 bot_control 也要捕获它,
    而 bot_control 不该 import bot_agent。"""
