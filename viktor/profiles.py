"""模式与三张正交 profile 表: 提示词(行为) × 限制(数值) × 工具白名单。

依赖方向: profiles → constants, prompts; 不 import 任何运行时/机器人模块。
"""

from .constants import (
    MODE_CREATIVE,
    MODE_CREATIVE_MAX,
    MODE_EXECUTE,
    MODE_NORMAL,
    MODE_ONESHOT,
    MODE_PLAN,
)
from .prompts import CREATIVE_PROMPT, EXECUTE_PROMPT, ONESHOT_PROMPT, PLAN_PROMPT


class Mode:
    """一个运行模式 = 提示词 profile + 限制 profile + 工具白名单 profile(+倍率/可达模式)。
    三个维度互相独立、可复用: 计划/执行模式提示词不同但可共用 heavy 限制;
    creative_max 只是 heavy 限制 ×2 再换 max 思考强度; 一次性则换一张工具白名单。"""
    __slots__ = ("prompt", "limits", "tools", "effort", "scale", "label",
                 "next_modes", "reset_to", "reveal_rounds")

    def __init__(self, prompt: str, limits: str, tools: str = "all",
                 effort: str = "normal", scale: int = 1, label: str = "",
                 next_modes: tuple = (), reset_to: str = MODE_NORMAL,
                 reveal_rounds: bool = False):
        self.prompt = prompt
        self.limits = limits
        self.tools = tools
        self.effort = effort
        self.scale = scale
        self.label = label
        self.next_modes = tuple(next_modes)
        self.reset_to = reset_to
        # 模式注记是否向模型明示“工具轮次”上限。交互模式(有收尾汇报机会)一律不明示,
        # 免得模型为凑轮次而多想/缩手缩脚; 一次性是闭式任务(无补救机会), 必须明示。
        self.reveal_rounds = reveal_rounds


# 提示词 profile: 只放"行为", 不含任何数字(数字随模式注记刷新)
PROMPTS = {
    "none": "",
    "creative": CREATIVE_PROMPT.strip(),
    "plan": PLAN_PROMPT.strip(),
    "execute": EXECUTE_PROMPT.strip(),
    "oneshot": ONESHOT_PROMPT.strip(),
}

# 数值 profile: 字段名 -> config 键(沿用现有配置); effort 单独放模式上, 因为 max 与 heavy 共享数值但强度不同
LIMIT_KEYS = {
    "quick": {"tokens": "max_reply_tokens", "rounds": "max_tool_rounds",
              "ptc": "ptc_max_calls", "stated": "ptc_stated_calls",
              "result": "ptc_result_limit"},
    "heavy": {"tokens": "creative_max_reply_tokens", "rounds": "creative_max_tool_rounds",
              "ptc": "creative_ptc_max_calls", "stated": "creative_ptc_stated_calls",
              "result": "creative_ptc_result_limit"},
    "oneshot": {"tokens": "oneshot_max_reply_tokens", "rounds": "oneshot_max_tool_rounds",
                "ptc": "ptc_max_calls", "stated": "ptc_stated_calls",
                "result": "ptc_result_limit"},
}
LIMIT_DEFAULTS = {
    "max_reply_tokens": 6000, "max_tool_rounds": 8,
    "ptc_max_calls": 24, "ptc_stated_calls": 12, "ptc_result_limit": 30000,
    "creative_max_reply_tokens": 16384, "creative_max_tool_rounds": 32,
    "creative_ptc_max_calls": 48, "creative_ptc_stated_calls": 24,
    "creative_ptc_result_limit": 60000,
    "oneshot_max_reply_tokens": 6000, "oneshot_max_tool_rounds": 4,
}
EFFORT_KEYS = {
    "normal": "normal_effort", "creative": "creative_effort",
    "creative_max": "creative_max_effort", "oneshot": "oneshot_effort",
}

# 工具 profile: None = 全部注册工具; {"only": {...}} = 白名单; {"except": {...}} = 黑名单(全量减去)
# 无论哪种, 未出现在最终白名单里的工具模型都看不到, 执行层也拦。
TOOLS = {
    "all": None,
    "oneshot": {"only": {
        "send_chat_message", "update_memory", "get_player_activity",
        "get_player_position", "get_player_hand", "search_wiki", "read_wiki_page",
        "run_server_command", "get_block", "get_heightmap", "get_slice",
        "inspect_region", "find_blocks", "ptc",
        "find_items", "use_skill",
    }},
    # 计划模式: 黑名单, 不让它执行 MC 命令/动世界(查询、说话、记忆、ptc 仍在)
    "no_commands": {"except": {"run_server_command", "pin_region",
                               "build_preview", "build_commit", "build_undo", "build_status"}},
    # 建造引擎(含 Python 沙箱)只在创造模式家族暴露: 其它模式连工具名都看不到
    "no_build": {"except": {"build_preview", "build_commit", "build_undo", "build_status",
                            "render_build"}},
}

# 模式表: 只组合上面的 profile。next_modes = set_mode 允许切到的目标(其它模式对模型“不可知”);
# 空元组 = 不可切换(连 set_mode 都不暴露)。plan/oneshot 不在任何 next_modes 里 -> 无法被切进去。
MODES = {
    MODE_NORMAL:       Mode("none",     "quick",   "no_build", "normal",       label="普通",
                            next_modes=(MODE_CREATIVE, MODE_CREATIVE_MAX)),
    MODE_CREATIVE:     Mode("creative", "heavy",   "all",      "creative",     label="创造",
                            next_modes=(MODE_NORMAL, MODE_CREATIVE_MAX)),
    MODE_CREATIVE_MAX: Mode("creative", "heavy",   "all",      "creative_max", label="创造max", scale=2,
                            next_modes=(MODE_NORMAL, MODE_CREATIVE)),
    MODE_PLAN:         Mode("plan",     "heavy",   "no_commands", "creative",     label="计划", scale=2,
                            next_modes=(MODE_EXECUTE,)),
    MODE_EXECUTE:      Mode("execute",  "heavy",   "no_build",    "creative",     label="执行", scale=2,
                            next_modes=(MODE_NORMAL,)),
    MODE_ONESHOT:      Mode("oneshot",  "oneshot", "oneshot",  "oneshot",      label="一次性",
                            reveal_rounds=True),
}

