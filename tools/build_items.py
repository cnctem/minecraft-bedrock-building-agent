#!/usr/bin/env python3
"""从游戏自带的 ID 清单 + 官方语言文件, 生成物品/方块速查表 data/items.json。

数据来源(全部来自服务器本体, 版本精确, 无需手工维护):
  - `scriptevent viktor:ids` 导出的 ID 清单(见 data/raw_ids.txt, 由行为包 viktor_bridge 提供)
  - resource_packs/vanilla/texts/{zh_CN,en_US}.lang 官方译名

用法:
  python3 tools/build_items.py                 # 读 data/raw_ids.txt, 写 data/items.json
  python3 tools/build_items.py --check         # 只打印覆盖率统计

基岩版 lang 键新旧混杂(tile.birchFence / tile.wooden_slab.birch / tile.concretePowder.black),
所以这里用一组“族规则 + 通用旋转”候选去反查; 命中不了的退化为英文 ID 的人类可读形式。
"""
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DEFAULT_RAW = BASE / "data" / "raw_ids.txt"
DEFAULT_OUT = BASE / "data" / "items.json"
DEFAULT_SERVER = Path("/home/jrj/minecraft-bedrock")
ALIASES = BASE / "data" / "item_aliases.json"

COLORS = ["white", "orange", "magenta", "light_blue", "yellow", "lime", "pink",
          "gray", "light_gray", "cyan", "purple", "blue", "brown", "green",
          "red", "black"]
WOODS = ["oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove",
         "cherry", "bamboo", "crimson", "warped"]
WOOD_LEGACY = {"dark_oak": ["dark_oak", "big_oak"]}
CORAL_COLOR = {"tube": "blue", "brain": "pink", "bubble": "purple",
               "fire": "red", "horn": "yellow"}
SLAB_LEGACY = {"brick": "stone_slab.brick", "cobblestone": "stone_slab.cobble",
               "nether_brick": "stone_slab.nether_brick", "quartz": "stone_slab.quartz",
               "sandstone": "stone_slab.sand", "smooth_stone": "stone_slab.stone",
               "stone_brick": "stone_slab.smoothStoneBrick",
               "red_sandstone": "stone_slab2.red_sandstone"}
FLOWER = {"allium": "allium", "blue_orchid": "blueOrchid",
          "cornflower": "cornflower", "oxeye_daisy": "oxeyeDaisy",
          "lily_of_the_valley": "lilyOfTheValley", "poppy": "poppy"}


def camel(s: str) -> str:
    p = s.split("_")
    return p[0] + "".join(w[:1].upper() + w[1:] for w in p[1:])


def load_lang(path: Path) -> dict:
    d = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            d[k] = v.split("\t")[0]
    return d


def candidates(i: str):
    """给出所有可能命中的 lang 键(不含 .name 后缀)。"""
    ids = [i]
    if "dark_oak" in i:                       # 旧 lang 用 big_oak 表示深色橡木
        ids.append(i.replace("dark_oak", "big_oak"))
    out = []
    for x in ids:
        out += _cands(x)
    return out


def _cands(i: str):
    c = [f"item.{i}", f"tile.{i}", f"item.{camel(i)}", f"tile.{camel(i)}"]
    w = i.split("_")
    for k in range(1, len(w)):                      # 通用旋转 + camel
        a, b = "_".join(w[:k]), "_".join(w[k:])
        for base in (b, camel(b)):
            for var in (a, camel(a)):
                c.append(f"tile.{base}.{var}")
                c.append(f"item.{base}.{var}")
    for wood in WOODS:                              # <wood>_<base>
        if not i.startswith(wood + "_"):
            continue
        rest = i[len(wood) + 1:]
        for wl in WOOD_LEGACY.get(wood, [wood]):
            c += [f"tile.{rest}.{wl}", f"tile.{rest}.{camel(wl)}",
                  f"tile.{wl}{rest[:1].upper() + rest[1:]}",
                  f"tile.{camel(wl)}{rest[:1].upper() + rest[1:]}"]
    for color in COLORS:                            # <color>_<base>
        if i.startswith(color + "_"):
            rest = i[len(color) + 1:]
            c += [f"tile.{rest}.{color}", f"tile.{camel(rest)}.{color}",
                  f"item.{rest}.{color}"]
    # 各族特例
    if i.endswith("_concrete"):
        c.append(f"tile.concrete.{i[:-9]}")
    if i.endswith("_concrete_powder"):
        c.append(f"tile.concretePowder.{i[:-16]}")
    if i.endswith("_glazed_terracotta"):
        c.append(f"tile.glazedTerracotta.{i[:-18]}")
    if i.endswith("_terracotta"):
        c.append(f"tile.stained_hardened_clay.{i[:-11]}")
    if i.endswith("_shulker_box"):
        v = i[:-12]
        c += [f"tile.shulkerBox.{v}",
              f"tile.shulkerBox{v[:1].upper() + v[1:]}" if v else "tile.shulkerBox"]
    if i.endswith("_spawn_egg"):
        c.append(f"item.spawn_egg.entity.{i[:-10]}")
    if i.endswith("_chest_boat"):
        c.append(f"item.chest_boat.{i[:-11]}")
    elif i.endswith("_boat"):
        c.append(f"item.boat.{i[:-5]}")
    if i.endswith("_banner_pattern"):
        c.append(f"item.banner_pattern.{i[:-15]}")
    if i.endswith("_dye"):
        c.append(f"item.dye.{i[:-4]}_new")
    if i.endswith("_coral_block") and i[:-12] in CORAL_COLOR:
        c.append(f"tile.coral_block.{CORAL_COLOR[i[:-12]]}")
    if i.endswith("_coral_fan") and i[:-10] in CORAL_COLOR:
        c.append(f"tile.coral_fan.{CORAL_COLOR[i[:-10]]}_fan")
    if i.endswith("_coral") and i[:-6] in CORAL_COLOR:
        c.append(f"tile.coral.{CORAL_COLOR[i[:-6]]}")
    if i.endswith("_slab"):
        v = i[:-5]
        c.append(f"tile.wooden_slab.{v}")
        if v in SLAB_LEGACY:
            c.append("tile." + SLAB_LEGACY[v])
    if i == "cobblestone_wall":
        c.append("tile.cobblestone_wall.normal")
    if i == "mossy_cobblestone_wall":
        c.append("tile.cobblestone_wall.mossy")
    if i in FLOWER:
        c.append(f"tile.red_flower.{FLOWER[i]}")
    if i == "bone_meal":
        c.append("item.dye.white")
    if i == "carrot_on_a_stick":
        c.append("item.carrotOnAStick")
    if i in ("andesite", "diorite", "granite"):
        c.append(f"tile.stone.{i}")
    if i.startswith("polished_") and i[9:] in ("andesite", "diorite", "granite"):
        c.append(f"tile.stone.{i[9:]}Smooth")
    if i == "cooked_cod":
        c.append("item.cooked_fish")
    if i in ("lilac", "peony", "rose_bush", "sunflower"):
        c.append({"lilac": "tile.double_plant.syringa",
                  "peony": "tile.double_plant.paeonia",
                  "rose_bush": "tile.double_plant.rose",
                  "sunflower": "tile.double_plant.sunflower"}[i])
    return c


# ---------------- 分类 ----------------

BLOCK_SUFFIX = {
    "建筑": ("planks", "log", "wood", "leaves", "stairs", "slab", "fence",
             "fence_gate", "wall", "door", "trapdoor", "button", "pressure_plate",
             "concrete", "concrete_powder", "wool", "carpet", "terracotta",
             "glazed_terracotta", "shulker_box", "stained_glass", "stained_glass_pane",
             "bricks", "brick", "sandstone", "quartz", "prismarine", "purpur",
             "blackstone", "deepslate", "tuff", "mud", "copper", "candle", "sign",
             "banner", "glass", "glass_pane", "stained_glass", "walls"),
}
BUILD_IDS = {
    "stone", "cobblestone", "mossy_cobblestone", "smooth_stone", "stonebrick",
    "chiseled_stone_bricks", "cracked_stone_bricks", "mossy_stone_bricks",
    "granite", "diorite", "andesite", "polished_granite", "polished_diorite",
    "polished_andesite", "brick_block", "end_bricks", "nether_brick",
    "red_nether_brick", "end_stone", "obsidian", "crying_obsidian",
    "glowstone", "sea_lantern", "shroomlight", "ochre_froglight",
    "verdant_froglight", "pearlescent_froglight", "hay_block", "bone_block",
    "honeycomb_block", "nether_wart_block", "warped_wart_block", "sculk",
    "iron_bars", "chain", "lantern", "soul_lantern", "campfire", "soul_campfire",
    "torch", "soul_torch", "redstone_lamp", "sea_lantern", "magma", "glowstone",
    "hardened_clay", "gold_block", "iron_block", "diamond_block", "emerald_block",
    "lapis_block", "coal_block", "netherite_block", "copper_block", "quartz_block",
    "raw_iron_block", "raw_gold_block", "raw_copper_block", "honey_block", "slime",
    "amethyst_block", "purpur_block", "quartz_bricks",
}
# 技术/调试方块, 不给模型看(ID 清单里的干扰项)
JUNK = {"air", "allow", "deny", "unknown", "reserved6", "info_update",
        "info_update2", "client_request_placeholder_block", "moving_block",
        "bubble_column", "flowing_water", "flowing_lava", "water", "lava",
        "fire", "soul_fire", "portal", "end_portal", "end_gateway",
        "netherreactor", "glowingobsidian", "chemical_heat", "chemistry_table",
        "colored_torch_bp", "colored_torch_rg", "coral_fan_hang",
        "coral_fan_hang2", "coral_fan_hang3", "trip_wire", "reeds",
        "piston_arm_collision", "sticky_piston_arm_collision", "camera", "jigsaw"}
NATURAL = {
    "dirt", "grass_block", "grass_path", "dirt_with_roots", "podzol", "mycelium",
    "sand", "red_sand", "gravel", "clay", "snow", "snow_layer", "ice", "packed_ice",
    "blue_ice", "farmland", "mud", "packed_mud", "moss_block", "moss_carpet",
    "deepslate", "netherrack", "soul_sand", "soul_soil", "basalt", "blackstone",
    "smooth_basalt", "calcite", "amethyst_block", "budding_amethyst", "dripstone_block",
    "pointed_dripstone", "tuff", "waterlily", "vine", "lily_of_the_valley",
    "deadbush", "short_grass", "tall_grass", "fern", "large_fern", "bamboo",
    "cactus", "red_mushroom", "brown_mushroom", "spore_blossom", "moss",
    "sculk_vein", "hanging_roots", "big_dripleaf", "small_dripleaf_block",
}
REDSTONE = {
    "piston", "sticky_piston", "observer", "repeater", "comparator",
    "redstone_torch", "redstone_lamp", "redstone_block", "redstone_wire",
    "dropper", "dispenser", "hopper", "lever", "target", "daylight_detector",
    "tripwire_hook", "trip_wire", "rail", "golden_rail", "detector_rail",
    "activator_rail", "tnt", "note_block", "noteblock", "sculk_sensor",
    "calibrated_sculk_sensor", "sculk_shrieker", "sculk_catalyst",
    "lightning_rod", "copper_bulb", "crafter", "daylight_detector_inverted",
}
FUNCTIONAL = {
    "crafting_table", "furnace", "lit_furnace", "blast_furnace", "lit_blast_furnace",
    "smoker", "lit_smoker", "chest", "trapped_chest", "ender_chest", "barrel",
    "bed", "anvil", "brewing_stand", "cauldron", "enchanting_table", "grindstone",
    "loom", "stonecutter_block", "stonecutter", "cartography_table", "fletching_table",
    "smithing_table", "lectern", "bell", "composter", "jukebox", "bookshelf",
    "chiseled_bookshelf", "decorated_pot", "flower_pot", "conduit", "beacon",
    "respawn_anchor", "lodestone", "ladder", "scaffolding", "frame", "glow_frame",
    "painting", "bee_nest", "beehive", "mob_spawner", "trial_spawner", "vault",
    "light_block", "candle", "candle_cake", "cake", "sweet_berry_bush",
    "carrots", "potatoes", "beetroot", "wheat", "pumpkin", "melon_block",
    "pumpkin_stem", "melon_stem", "chorus_flower", "chorus_plant", "dragon_egg",
    "turtle_egg", "sniffer_egg", "frog_spawn", "sculk_catalyst", "tinted_glass",
    "crying_obsidian", "sponge", "wet_sponge", "slime", "honey_block",
    "trial_spawner", "vault", "mangrove_propagule", "azalea", "flowering_azalea",
    "azalea_leaves", "azalea_leaves_flowered", "cave_vines", "glow_lichen",
}
TOOLS_ARMOR = {
    "sword", "pickaxe", "axe", "shovel", "hoe", "shears", "flint_and_steel",
    "fishing_rod", "bow", "crossbow", "arrow", "shield", "trident", "mace",
    "helmet", "chestplate", "leggings", "boots", "horse_armor", "elytra",
    "totem_of_undying", "spyglass", "brush", "bucket", "water_bucket",
    "lava_bucket", "milk_bucket", "powder_snow_bucket", "name_tag", "lead",
    "compass", "clock", "recovery_compass", "lodestone_compass", "map",
    "empty_map", "writable_book", "written_book", "saddle", "carrot_on_a_stick",
    "warped_fungus_on_a_stick", "goat_horn", "firework_rocket", "firework_star",
    "wind_charge", "ominous_bottle",
}
FOOD = {
    "apple", "golden_apple", "appleEnchanted", "enchanted_golden_apple", "bread",
    "cookie", "melon_slice", "sweet_berries", "glow_berries", "carrot", "potato",
    "baked_potato", "poisonous_potato", "beetroot_soup", "beetroot", "dried_kelp",
    "beef", "cooked_beef", "porkchop", "cooked_porkchop", "chicken", "cooked_chicken",
    "mutton", "cooked_mutton", "rabbit", "cooked_rabbit", "cod", "cooked_cod",
    "salmon", "cooked_salmon", "tropical_fish", "pufferfish", "fish", "cooked_fish",
    "mushroom_stew", "rabbit_stew", "suspicious_stew", "pumpkin_pie", "rotten_flesh",
    "spider_eye", "cake", "honey_bottle", "chorus_fruit", "popped_chorus_fruit",
}
MATERIAL_KEY = ("ingot", "nugget", "scrap", "raw_", "dye", "shard", "crystal",
                "dust", "powder", "stick", "string", "leather", "feather", "paper",
                "book", "clay_ball", "brick", "coal", "charcoal", "diamond", "emerald",
                "redstone", "lapis_lazuli", "quartz", "amethyst_shard", "nether_star",
                "blaze_rod", "blaze_powder", "gunpowder", "glowstone_dust", "sugar",
                "wheat_seeds", "melon_seeds", "pumpkin_seeds", "beetroot_seeds",
                "bone", "bone_meal", "egg", "snowball", "slime_ball", "magma_cream",
                "ender_pearl", "ender_eye", "ghast_tear", "phantom_membrane",
                "prismarine_shard", "prismarine_crystals", "nautilus_shell",
                "heart_of_the_sea", "shulker_shell", "turtle_scute", "armadillo_scute",
                "rabbit_foot", "rabbit_hide", "honeycomb", "ink_sac", "glow_ink_sac",
                "resin", "resin_clump", "turtle_helmet", "breeze_rod", "heavy_core")


def categorize(i: str) -> str:
    if i.endswith("_spawn_egg"):
        return "刷怪蛋"
    if i in FOOD or i in ("fish",):
        return "食物"
    if i in BUILD_IDS:
        return "建筑"
    for kw in BLOCK_SUFFIX["建筑"][:-1]:
        if i == kw or i.endswith("_" + kw):
            return "建筑"
    if i in NATURAL or i.endswith("_leaves") or i.endswith("_sapling") or i.endswith("_log") \
            or i.endswith("_wood") or i.endswith("_ore") or i.endswith("_flower") \
            or i.endswith("_tulip") or i.endswith("_coral") or i.endswith("_coral_block") \
            or i.endswith("_coral_fan"):
        return "自然"
    if i in REDSTONE or i.endswith("_button") or i.endswith("_pressure_plate"):
        return "红石"
    if i in FUNCTIONAL:
        return "功能"
    if i in TOOLS_ARMOR:
        return "工具/装备"
    if any(k in i for k in ("sword", "pickaxe", "axe", "shovel", "hoe", "helmet",
                            "chestplate", "leggings", "boots", "horse_armor")):
        return "工具/装备"
    if any(k in i for k in MATERIAL_KEY):
        return "材料"
    return "杂项"


def humanize(i: str) -> str:
    return " ".join(w.capitalize() for w in i.split("_"))


def main():
    check = "--check" in sys.argv
    raw = DEFAULT_RAW
    server = DEFAULT_SERVER
    out = DEFAULT_OUT
    for a in sys.argv[1:]:
        if a.startswith("--raw="):
            raw = Path(a.split("=", 1)[1])
        elif a.startswith("--server-dir="):
            server = Path(a.split("=", 1)[1])
        elif a.startswith("--out="):
            out = Path(a.split("=", 1)[1])

    items, blocks = set(), set()
    for line in raw.read_text(encoding="utf-8").splitlines():
        t = line.split()
        if len(t) == 2 and t[1].startswith("minecraft:"):
            (items if t[0] == "ITEM" else blocks).add(t[1][10:])
    ids = set(items)
    keys_zh = set(load_lang(server / "resource_packs/vanilla/texts/zh_CN.lang"))
    ids |= {b for b in blocks if f"tile.{b}" in keys_zh}   # 只补有官方名的方块
    ids = {i for i in ids if i not in JUNK and not re.fullmatch(r"element_\d+", i)
           and not i.startswith("hard_")}

    zh = load_lang(server / "resource_packs/vanilla/texts/zh_CN.lang")
    en = load_lang(server / "resource_packs/vanilla/texts/en_US.lang")
    alias = json.loads(ALIASES.read_text(encoding="utf-8")) if ALIASES.exists() else {}

    entries, hit_zh = {}, 0
    for i in sorted(ids):
        name_zh = name_en = None
        for c in candidates(i):
            if name_zh is None:
                name_zh = zh.get(c + ".name") or zh.get(c)
            if name_en is None:
                name_en = en.get(c + ".name") or en.get(c)
            if name_zh and name_en:
                break
        if not name_zh:
            name_zh = name_en or humanize(i)
        else:
            hit_zh += 1
        entries[i] = {"zh": name_zh, "en": name_en or humanize(i),
                      "cat": categorize(i),
                      "alias": alias.get(i, [])}
    print(f"共 {len(entries)} 项, 中文名自动命中 {hit_zh} ({hit_zh/len(entries):.0%})")
    if check:
        from collections import Counter
        for cat, n in Counter(e["cat"] for e in entries.values()).most_common():
            print(f"  {cat}: {n}")
        miss = [i for i, e in entries.items() if e["zh"] == e["en"]]
        print("  无中文名样本:", miss[:25])
        return
    out.write_text(json.dumps(entries, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    print(f"已写入 {out}")


if __name__ == "__main__":
    main()
