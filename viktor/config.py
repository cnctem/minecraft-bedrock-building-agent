"""配置加载(config.json)。

依赖方向: config → paths; 不 import 更高层模块。
"""
import json

from . import paths


def load_config() -> dict:
    with open(paths.CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)
