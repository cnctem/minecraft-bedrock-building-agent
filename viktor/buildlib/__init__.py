"""建筑函数库(buildlib): 由 Java 模组(ShapeFunctions / AncientShapes / GardenShapes /
RegionalShapes / VaultShapes / StructureShapes / SurfaceShapes / MonumentFunctions /
HouseDecor / DecorationFunctions / DomainGenerators / MegaStyles) 的算法移植而来,
统一改写为**局部坐标 + 基岩版方块 ID + 整数确定性**, 并通过 `api.lib.<函数>` 暴露给建造程序。

设计约束(与 viktor/build.py 一致):
- 只产出普通 api ops(set/fill/box/line), 不碰世界、不读文件、不用随机数生成器;
- 坐标一律局部 (u, v, w), 由 origin + facing 负责世界坐标与四朝向;
- 非法参数抛 ValueError(明确说清要求), 不允许“静默返回 0、方块凭空消失”;
- 需要覆盖/挖空的函数在文档里显式声明(moon_gate 写 air, water_basin 写水 …)。

用法(模块级):
    from viktor.buildlib import LIB_SOURCE, index_text, CATEGORIES, BuildLib
建造沙箱通过 LIB_SOURCE 注入(随 payload 经 stdin 传入), 模型侧写 `api.lib.chinese_roof(...)`。
"""
from __future__ import annotations

from pathlib import Path

from . import core as _core
from .core import _LibBase
from .shapes import _ShapeLib
from .chinese import _ChineseLib
from .structures import _StructureLib
from .regional import _RegionalLib
from .gardens import _GardenLib
from .decor import _DecorLib
from .creations import _CreationLib
from .registry import (CATEGORIES, CATEGORY_META, SPEC, all_functions,
                       category_of, index_text, missing_from_spec)

__all__ = [
    "BuildLib", "BLOCK_ALIAS", "LIB_SOURCE", "CATEGORIES", "CATEGORY_META", "SPEC",
    "all_functions", "category_of", "index_text", "missing_from_spec",
    "lib_note", "source_paths",
]

_LIB_DIR = Path(__file__).resolve().parent
# 拼接顺序 = 沙箱里的定义顺序; 基类必须最后(它的 __init__ 打头)。
_FILES = ("core.py", "shapes.py", "chinese.py", "structures.py", "regional.py",
          "gardens.py", "decor.py", "creations.py")
_BASES = (_ShapeLib, _ChineseLib, _StructureLib, _RegionalLib, _GardenLib,
          _DecorLib, _CreationLib, _LibBase)

# 沙箱里的收尾代码: 组合类 → 参数签名包装 → 签名/类别表。
# 包装器让“参数写错”变成带接口说明的 TypeError/ValueError, 模型能自己改对。
_WRAPPER = '''
def _snake(name):
    out = []
    for ch in str(name):
        if ch.isupper():
            out.append("_")
            out.append(ch.lower())
        else:
            out.append(ch)
    return "".join(out).lstrip("_")

def _camel(name):
    parts = str(name).split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])

def _wrap_lib(name, fn):
    sig = _LIB_SIGNATURES.get(name, name + "(...)")
    accepted = list(fn.__code__.co_varnames[:fn.__code__.co_argcount])[1:]  # 去掉 self
    def wrapper(*args, **kwargs):
        # 兼容原模组的 camelCase 选项名(towerH/towerBlock/…)与 Python 的 snake_case
        if kwargs:
            fixed = {}
            for key, value in kwargs.items():
                real = key if key in accepted else _snake(key)
                if real not in accepted:
                    raise TypeError("%s 不认识参数 %r; 可用: %s\\n接口: %s"
                                    % (name, key, ", ".join(accepted), sig))
                fixed[real] = value
            kwargs = fixed
        try:
            return fn(*args, **kwargs)
        except TypeError as exc:
            raise TypeError("%s 参数不对: %s\\n接口: %s" % (name, exc, sig))
        except ValueError as exc:
            msg = str(exc)
            if sig in msg:
                raise
            raise ValueError("%s: %s\\n接口: %s" % (name, msg, sig))
    wrapper.__name__ = name
    wrapper.__doc__ = getattr(fn, "__doc__", None)
    return wrapper

for _name in list(_LIB_SIGNATURES):
    if hasattr(_BuildLib, _name):
        _wrapped = _wrap_lib(_name, getattr(_BuildLib, _name))
        setattr(_BuildLib, _name, _wrapped)
        # 原模组文档用的是 camelCase, 两种写法都能调
        setattr(_BuildLib, _camel(_name), _wrapped)
del _name, _wrapped
'''


class BuildLib(*_BASES):
    """单实例门面: 由建造程序里的 api 构造, 所有方法只记录 ops。"""


def source_paths() -> list[Path]:
    return [_LIB_DIR / name for name in _FILES]


def _source() -> str:
    """把分文件实现拼成一段可直接 exec 的源码(沙箱子进程用)。"""
    parts = []
    for path in source_paths():
        text = path.read_text(encoding="utf-8")
        # 分文件里没有 import, 只有 class 体, 拼在一起就是同一命名空间里的多继承来源。
        parts.append(f"# ---- buildlib/{path.name} ----\n{text.strip()}\n")
    bases = ", ".join(cls.__name__ for cls in _BASES)
    parts.append(f"\nclass _BuildLib({bases}):\n    pass\n")
    parts.append("\n_LIB_SIGNATURES = " + repr({n: s[0] for n, s in SPEC.items()}) + "\n")
    parts.append("_LIB_CATEGORIES = " + repr(CATEGORIES) + "\n")
    parts.append(_WRAPPER)
    return "\n".join(parts)


# 生成沙箱预置代码之前先取出别名表(它与 core 里的表是同一份)。
BLOCK_ALIAS = dict(_LibBase._ALIAS)

LIB_SOURCE = _source()

# 宿主侧(单测/文档生成)同样能查签名: 直接挂到 core 模块上。
_core._LIB_SIGNATURES = {name: spec[0] for name, spec in SPEC.items()}
_core._LIB_CATEGORIES = CATEGORIES


def lib_note() -> str:
    """给提示词/技能文档用的一句话索引(非 verbose 版)。"""
    counts = ", ".join(f"{cat} {len(names)}" for cat, names in CATEGORIES.items())
    return (f"api.lib 共 {len(all_functions())} 个建筑函数({counts}); "
            '先用 use_skill("mc-architecture", "references/functions-index.md") 查签名。')
