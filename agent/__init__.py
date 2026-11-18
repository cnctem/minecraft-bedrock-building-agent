"""agent: Minecraft 基岩版服务器智能管家。

分层与依赖方向(严格单向、无环; 上层可以 import 下层, 下层绝不反向 import 上层):

    bot.py (入口)  →  agent.selftest (--test)
        │
        agent.Bot = BotCoreMixin + BotControlMixin + BotToolsMixin + BotBuildMixin
                     + BotAgentMixin + BotAppMixin      ← 各职责 mixin(彼此不 import,
        │                                                只用 self.* 经 MRO 协作)
        session / bus / bridge / config / profiles
        │
        paths / constants / prompts / schemas ← 叶子层

同一层的模块之间也尽量不互相依赖; 需要跨职责协作时, 通过组合后的 Bot 实例(self.*)完成。
"""
from .bot_agent import BotAgentMixin
from .bot_app import BotAppMixin
from .bot_build import BotBuildMixin
from .bot_control import BotControlMixin
from .bot_core import BotCoreMixin
from .bot_tools import BotToolsMixin

__all__ = ["Bot"]


class Bot(BotCoreMixin, BotControlMixin, BotToolsMixin, BotBuildMixin,
          BotAgentMixin, BotAppMixin):
    """主对话机器人: 由各职责 mixin 组合而成, 对外接口与拆分前的 bot.Bot 一致。"""
