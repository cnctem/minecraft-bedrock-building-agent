#!/usr/bin/env python3
"""把 Java 模组 tasks/*.class 里内嵌的「设计指导文本」抽出来，落成技能书参考资料。

为什么不再手写理论: 原模组把成熟的设计标准直接写进了 Java 常量池(向量检索之外的
"硬规则"), 例如中式流派路由、官式殿宇/故宫三段比例、圆明园两种语汇、装饰守则、
建造正确性红线。这些比手写文档更完整、且与函数签名一一对应(函数名沿用 camelCase,
建筑函数库同时支持 camelCase 与 snake_case)。

只抽取"纯文本常量", 不改写内容; 分章与补充说明由本脚本加。

用法:
  python3 tools/gen_skill_guides.py                      # 从 ~/repo/tasks 读, 写 skills/
  python3 tools/gen_skill_guides.py --tasks /path/to/tasks
  python3 tools/gen_skill_guides.py --check              # 只比对是否最新, 不写文件
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DEFAULT_TASKS = Path("/home/jrj/repo/tasks")

HEADER = ("<!-- 由 tools/gen_skill_guides.py 抽取自 Java 模组 {cls}.class 的内嵌指导文本。"
          "内容为原模组的设计标准, 已按本项目函数库对齐函数名; 不要手改, 改脚本或原类。 -->\n\n"
          "> 函数名两种写法都能用: `api.lib.chineseRoof(...)` 与 `api.lib.chinese_roof(...)`;\n"
          "> 参数里的 `{{...}}` 是选项名清单, 在本项目里写成关键字参数(见 `api.lib.help(\"名字\")`)。\n\n")


def class_strings(path: Path, min_len: int = 40) -> list[str]:
    """读 .class 常量池里的 UTF-8 字符串(只依赖标准库, 不需要 JVM)。"""
    data = path.read_bytes()
    if data[:4] != b"\xca\xfe\xba\xbe":
        raise ValueError(f"{path} 不是 class 文件")
    off = 8
    count = struct.unpack_from(">H", data, off)[0]
    off += 2
    pool: list[str | None] = [None] * count
    i = 1
    while i < count:
        tag = data[off]
        off += 1
        if tag == 1:  # Utf8
            size = struct.unpack_from(">H", data, off)[0]
            off += 2
            raw = data[off:off + size]
            pool[i] = raw.decode("utf-8", "replace")
            off += size
        elif tag in (3, 4):  # Integer / Float
            off += 4
        elif tag in (5, 6):  # Long / Double 占两个槽位
            off += 8
            i += 1
        elif tag in (7, 8, 16, 19, 20):  # Class / String / MethodType / Module / Package
            off += 2
        elif tag in (9, 10, 11, 12, 17, 18):  # Field / Method / InterfaceMethod / NameAndType / Dynamic
            off += 4
        elif tag == 15:  # MethodHandle
            off += 3
        else:
            raise ValueError(f"{path}: 未知常量池 tag {tag} (槽位 {i})")
        i += 1
    return [s for s in pool if isinstance(s, str) and len(s) >= min_len]


def split_sections(text: str, titles: list[str]) -> dict[str, str]:
    """按 '== ★标题' 切章; titles 是要抓的章标题前缀(顺序即输出顺序)。"""
    marks = []
    for title in titles:
        at = text.find("== " + title)
        if at < 0:
            raise SystemExit(f"ShapeGuide 里找不到章节: {title}")
        marks.append((at, title))
    marks.sort()
    out = {}
    for idx, (at, title) in enumerate(marks):
        end = marks[idx + 1][0] if idx + 1 < len(marks) else len(text)
        body = text[at:end].strip()
        # 去掉标题上下那两条 === 装饰线, 但要保留章节标题本身
        lines = [ln for ln in body.splitlines()]
        cleaned = []
        for ln in lines:
            if ln.startswith("====="):
                continue
            if ln.startswith("��次") or ln.startswith("== "):
                cleaned.append("\n## " + ln[3:].strip())
                continue
            cleaned.append(ln)
        out[title] = "\n".join(cleaned).strip()
    return out


def tidy(body: str) -> str:
    lines = [ln.rstrip() for ln in body.splitlines()]
    out = []
    blank = 0
    for ln in lines:
        if not ln.strip():
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        out.append(ln)
    return "\n".join(out).strip() + "\n"


ALL_SECTIONS = [
    "★中国建筑构件函数（官式 + 地域流派；不要用 fill 手搓曲线）",
    "★★中式流派路由（第一步必做：先判断是哪个流派，不要默认故宫）",
    "官式构件（屋顶 / 斗拱 / 台基 / 门窗 / 塔）",
    "★曲面与拱顶函数（做\"有点高级\"的建筑时用，模型手搓不出来）",
    "★古建细部（屋顶做了 curvedRoof 之后必须补这几样才像中国建筑）",
    "★圆明园构件（玩家说\"圆明园/西洋楼/大水法/海晏堂/黄花阵/石舫/九曲桥\"就照这做）",
    "★结构与立面函数（现代建筑用；模型手写循环最易错间距与两端）",
]

# (输出文件, 章节标题列表, 章首导语)
TARGETS = [
    (
        "skills/mc-architecture/references/shape-guide-chinese.md",
        ["★中国建筑构件函数（官式 + 地域流派；不要用 fill 手搓曲线）",
         "★★中式流派路由（第一步必做：先判断是哪个流派，不要默认故宫）",
         "官式构件（屋顶 / 斗拱 / 台基 / 门窗 / 塔）",
         "★古建细部（屋顶做了 curvedRoof 之后必须补这几样才像中国建筑）",
         ],
        "中式（官式 + 八个地域流派）的构件选择、比例与组合套路。**先读「流派路由」**，\n"
        "再按玩家说的地域/等级取用构件；不要默认故宫。\n",
    ),
    (
        "skills/mc-architecture/references/shape-guide-garden-western.md",
        ["★圆明园构件（玩家说\"圆明园/西洋楼/大水法/海晏堂/黄花阵/石舫/九曲桥\"就照这做）"],
        "圆明园式「中式园林 + 西洋石构」双语汇: 西洋楼石构、水景(大水法)、园林构筑\n"
        "(石舫/九曲桥/叠石假山/游廊/花池), 以及西洋楼立面、水景、园林组团三套套路。\n",
    ),
    (
        "skills/mc-architecture/references/shape-guide-advanced.md",
        ["★曲面与拱顶函数（做\"有点高级\"的建筑时用，模型手搓不出来）",
         "★结构与立面函数（现代建筑用；模型手写循环最易错间距与两端）"],
        "做“有点高级”的建筑时用: 数学曲面(双曲面/马鞍面/螺旋面/超椭球)、拱顶(十字拱/\n"
        "肋拱/扇拱/水道桥/网架)、现代结构(幕墙/斜交网格/旋转楼梯/点阵桁架)与高层套路。\n",
    ),
    (
        "skills/mc-build/references/mega-build-guide.md",
        None,  # 整篇 MegaBuildGuide
        "大规模建造的函数库全景与硬规则: 选项写法、纪念性结构、装饰函数(含 **y 在最后一位**\n"
        "的 7 个例外)、普通民居整套、预制风格库与**占地契约**、超大规模分区策略、\n"
        "**建造正确性红线**(含“后写覆盖先写”“挖空必须显式写 air”)。\n",
    ),
    (
        "skills/mc-terrain/references/domain-generators.md",
        None,  # DomainGenerators.GUIDE
        "自然与遗迹生成器(植被/遗迹/地形/道路)的定位与用法。本项目里对应\n"
        "`api.lib.vegetation / ruins / terrain / road`, 都是确定性的(同坐标同 seed 同结果)。\n",
    ),
]


def build_outputs(tasks: Path) -> dict[Path, str]:
    outputs: dict[Path, str] = {}

    shape = class_strings(tasks / "ShapeGuide.class", 1000)
    if not shape:
        raise SystemExit("ShapeGuide.class 里没抽到长文本")
    guide = max(shape, key=len)
    titles = ALL_SECTIONS
    sections = split_sections(guide, titles)

    mega = max(class_strings(tasks / "MegaBuildGuide.class", 1000), key=len)
    domain = max(class_strings(tasks / "DomainGenerators.class", 500), key=len)

    for rel, chapter_titles, intro in TARGETS:
        cls = Path(rel).stem
        if rel.endswith("mega-build-guide.md"):
            body = tidy(mega)
            cls = "MegaBuildGuide"
        elif rel.endswith("domain-generators.md"):
            body = tidy(domain)
            cls = "DomainGenerators"
        else:
            parts = [sections[t] for t in chapter_titles]
            body = tidy("\n\n".join(parts))
            cls = "ShapeGuide"
        outputs[BASE / rel] = HEADER.format(cls=cls) + f"# {cls} · {Path(rel).stem}\n\n{intro}\n" + body
    return outputs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default=str(DEFAULT_TASKS))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    tasks = Path(args.tasks)
    if not (tasks / "ShapeGuide.class").exists():
        print(f"找不到 {tasks}/ShapeGuide.class; 用 --tasks 指定解包目录")
        return 2
    outputs = build_outputs(tasks)
    bad = 0
    for path, text in outputs.items():
        if args.check:
            old = path.read_text(encoding="utf-8") if path.exists() else ""
            if old != text:
                print(f"过期: {path.relative_to(BASE)}")
                bad += 1
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"写入 {path.relative_to(BASE)} ({len(text)} 字符)")
    if args.check:
        print("全部一致" if not bad else f"{bad} 处需要更新")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
