"""模型档案: 一次会话用哪个模型, 以及该模型的请求参数怎么拼。

依赖方向: 叶子模块, 不 import 任何项目内模块(只读传入的 cfg)。

设计要点:
- 模型是「会话级」的: 只在「清空」/「清空<键>」开新会话时选定, 会话内不可切换。
- 每个模型自带触发词、显示名、模型 ID、Base URL、API key、上下文窗口、输出上限、
  思考强度映射、是否回传思考链、采样温度。第三方/订阅套餐的差异全部数据化。
- 顶层 api_key/api_base/model/context_window_tokens 仍是默认模型(flash)的来源,
  保持向后兼容; 其它模型的身份字段必须自己写全(不继承 key/base/model, 免得配错指向别家)。

思考强度映射: 模式只产出三档硬编码值 low/high/max(见 profiles.EFFORT_KEYS),
模型档案用 effort_param + effort_map 决定"发哪个字段、值映射成什么"。
映射到 None 表示该档不传这个字段。

联网能力: DeepSeek 的接口原生支持联网工具(deepseek_web_search / deepseek_read_url), 由
native_web_tools() 判定; 别家模型没有这类工具, 退回同名函数工具(实现见 websearch.py)。
"""
import urllib.parse

DEFAULT_MODEL = "flash"  # 普通「清空」与进服自动开新会话用的模型

# 模式默认采样温度(模型档案里没写 temperature 时用这个规则): 创造类不传, 其余用 cfg.temperature
_UNSET = object()
UNSET = _UNSET  # 对外暴露: 供 bot_agent 判断“模型档案是否显式指定了温度”

_IDENTITY = ("label", "trigger", "api_base", "api_key", "model")
# 身份/计费默认值: 只有默认模型从顶层配置继承, 其它模型必须自己声明
_DEFAULT_IDENTITY = {
    "label": "DeepSeek Flash",
    "trigger": "清空",
    "api_base": "https://api.deepseek.com",
    "api_key": "",
    "model": "deepseek-flash",
}
# 行为默认值: 所有模型都可继承, 需要时覆盖
_DEFAULT_BEHAVIOR = {
    "context_window_tokens": 1048576,
    "max_output_tokens": 32768,
    "effort_param": "effort",
    "effort_map": {"low": "low", "high": "high", "max": "max"},
    "reasoning_content": True,  # 带 tool_calls 的 assistant 要不要回传思考链
    "vision": True,             # 能不能收图片内容块(渲染图 / 玩家发的图片直链会附)
    "temperature": _UNSET,      # _UNSET = 按模式默认; None = 一律不传; 数字 = 固定值
}


def _default_identity(cfg: dict) -> dict:
    """默认模型(flash)的身份字段: 顶层配置优先, 缺省用内置默认值。"""
    ident = dict(_DEFAULT_IDENTITY)
    for key in _IDENTITY:
        if cfg.get(key):
            ident[key] = cfg[key]
    return ident


def _behavior_defaults(cfg: dict, alias: str) -> dict:
    """行为字段的默认值。默认模型(flash)沿用顶层配置(向后兼容老配置/自测改 cfg)。"""
    defaults = dict(_DEFAULT_BEHAVIOR)
    if alias == DEFAULT_MODEL:
        if cfg.get("context_window_tokens"):
            defaults["context_window_tokens"] = int(cfg["context_window_tokens"])
        if cfg.get("retry_max_reply_tokens"):
            defaults["max_output_tokens"] = int(cfg["retry_max_reply_tokens"])
    return defaults


def _overlay_behavior(spec: dict, raw: dict, defaults: dict) -> None:
    """行为字段: 数值/映射可继承默认, 写法与默认不同就覆盖。"""
    for key, default in defaults.items():
        if key not in raw:
            spec[key] = dict(default) if isinstance(default, dict) else default
            continue
        value = raw[key]
        if key == "effort_map":
            merged = dict(defaults["effort_map"])
            merged.update(value or {})  # 允许只写要改的档位
            spec[key] = merged
        else:
            spec[key] = value


def specs(cfg: dict) -> dict[str, dict]:
    """解析出全部模型档案: {别名: spec}(顺序 = 配置文件里的顺序)。"""
    out: dict[str, dict] = {}
    default_ident = _default_identity(cfg)
    table = cfg.get("models") or {}
    for alias, raw in table.items():
        if not isinstance(raw, dict):
            continue
        spec = {"alias": alias, "enabled": raw.get("enabled", True)}
        if alias == DEFAULT_MODEL:
            spec.update(default_ident)
        else:
            spec.update({key: raw.get(key, "") for key in _IDENTITY})
        _overlay_behavior(spec, raw, _behavior_defaults(cfg, alias))
        # 行为字段之外的自定义键原样保留(便于以后加参数, 不用改代码)
        for key, value in raw.items():
            if key not in spec:
                spec[key] = value
        if not (spec.get("api_base") and spec.get("api_key") and spec.get("model")):
            spec["enabled"] = False  # 缺 Base URL / key / 模型名 = 还没接好
        out[alias] = spec
    if DEFAULT_MODEL not in out:  # 老配置(没有 models 段): 合成一个默认模型
        spec = {"alias": DEFAULT_MODEL, "enabled": True}
        spec.update(default_ident)
        _overlay_behavior(spec, {}, _behavior_defaults(cfg, DEFAULT_MODEL))
        out[DEFAULT_MODEL] = spec
    return out


def spec(cfg: dict, alias: str | None = None) -> dict:
    """取某个模型的档案; 别名不认识时退回默认模型(不会抛异常, 调用方免写 try)。"""
    all_specs = specs(cfg)
    return all_specs.get(alias or DEFAULT_MODEL) or all_specs[DEFAULT_MODEL]


def trigger_map(cfg: dict) -> dict[str, str]:
    """触发词 -> 别名(只收非空触发词; 精确匹配由调用方做)。"""
    return {s["trigger"]: alias for alias, s in specs(cfg).items() if s.get("trigger")}


def resolve_trigger(cfg: dict, text: str) -> str | None:
    """完全匹配的触发词 -> 模型别名; 不认识返回 None(交给模型当普通聊天)。"""
    return trigger_map(cfg).get(text)


def selectable(cfg: dict) -> list[tuple[str, dict]]:
    """可用于提示玩家的 (触发词, spec) 列表(含尚未接通的, 好让玩家知道有这条路)。"""
    return [(s["trigger"], s) for s in specs(cfg).values() if s.get("trigger")]


def describe(cfg: dict, alias: str | None = None) -> str:
    """一行说明: 别名/显示名/模型 ID, 用于系统提示与日志。"""
    s = spec(cfg, alias)
    return f"{s['alias']}({s.get('label') or s.get('model')})"


def _is_deepseek_host(spec_dict: dict) -> bool:
    """Base URL 是不是 DeepSeek 的接口(DeepSeek 扩展能力都按这个判定)。"""
    host = (urllib.parse.urlsplit(str(spec_dict.get("api_base") or "")).hostname or "").lower()
    return host == "deepseek.com" or host.endswith(".deepseek.com")


def remote_image_url(spec_dict: dict) -> bool:
    """能不能直接收 http(s) 图片地址(由模型服务端下载, 本地不取字节)。

    DeepSeek 支持(见 Vision 指南的 External image URL); 实测 Kimi 只认 data: URL,
    传 http 地址直接 400。显式写了 remote_image_url(true/false) 就听配置。"""
    if isinstance(spec_dict.get("remote_image_url"), bool):
        return bool(spec_dict["remote_image_url"])
    return _is_deepseek_host(spec_dict)


def native_web_tools(spec_dict: dict) -> bool:
    """该模型是否原生支持 DeepSeek 的服务端联网工具(deepseek_web_search / deepseek_read_url)。

    这类工具是 DeepSeek 的扩展: 声明在 tools 里, 模型自己决定何时联网, 搜索、开页与抓取
    都在服务端完成, 客户端不执行任何工具。显式写了 web_tools(true/false) 就听配置;
    否则看 Base URL 是不是 DeepSeek 的接口 —— 切到别家模型(kimi 等)时自动退回同名
    函数工具(仍由 DeepSeek 的 Search/Fetch 接口提供联网能力)。"""
    if isinstance(spec_dict.get("web_tools"), bool):
        return bool(spec_dict["web_tools"])
    return _is_deepseek_host(spec_dict)


def effort_of(spec_dict: dict, effort: str) -> tuple[str | None, str | None]:
    """把模式的 low/high/max 映射成 (请求字段名, 字段值); 该档不传则返回 (None, None)。"""
    field = spec_dict.get("effort_param")
    if not field:
        return None, None
    value = (spec_dict.get("effort_map") or {}).get(effort)
    if value is None:
        return None, None
    return field, value
