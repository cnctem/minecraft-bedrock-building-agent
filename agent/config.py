"""配置加载(config.json)。

依赖方向: config → paths; 不 import 更高层模块。
"""
import json

from . import paths


def get_agent_name(cfg: dict) -> str:
    """读取显示名称；名字用于身份与发言前缀，不作为聊天触发词。"""
    name = cfg.get("agent_name", "agent")
    if (not isinstance(name, str) or not 1 <= len(name.strip()) <= 32
            or not name.isprintable() or any(c in name for c in "§<>")):
        raise ValueError("agent_name 必须为 1–32 字符的可见名称，不能含控制字符或 §<>。")
    return name.strip()


def load_config() -> dict:
    with open(paths.CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)
