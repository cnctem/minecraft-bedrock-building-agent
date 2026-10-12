# 方块状态速查(基岩版, 实测)

命令写法: `<方块ID> ["状态名"="值", ...]`(见主手册第 4 节)。以下是本服版本实测的状态名与默认值, 拿不准时以 `get_block` 实测为准。

| 方块 | 状态(默认值) |
|---|---|
| `oak_stairs` | `weirdo_direction`=0, `upside_down_bit`=false |
| `stone_slab` | `minecraft:vertical_half`="bottom", `top_slot_bit`=false, `stone_slab_type`="smooth_stone" |
| `oak_slab` | `minecraft:vertical_half`="bottom", `top_slot_bit`=false, `wood_type`="oak" |
| `oak_double_slab` | `minecraft:vertical_half`="bottom", `top_slot_bit`=false, `wood_type`="oak" |
| `oak_log` | `pillar_axis`="y", `old_log_type`="oak" |
| `oak_wood` | `pillar_axis`="y", `stripped_bit`=false, `wood_type`="oak" |
| `deepslate` | `pillar_axis`="y" |
| `quartz_block` | `pillar_axis`="y", `chisel_type`="default" |
| `purpur_block` | `pillar_axis`="y", `chisel_type`="default" |
| `chain` | `pillar_axis`="y" |
| `torch` / `redstone_torch` / `soul_torch` | `torch_facing_direction`="unknown" |
| `ladder` | `facing_direction`=0 |
| `wooden_door` | `open_bit`=false, `direction`=0, `upper_block_bit`=false, `door_hinge_bit`=false |
| `trapdoor` | `upside_down_bit`=false, `open_bit`=false, `direction`=0 |
| `fence_gate` | `in_wall_bit`=false, `open_bit`=false, `direction`=0 |
| `standing_sign` | `ground_sign_direction`=0 |
| `wall_sign` | `facing_direction`=0 |
| `standing_banner` | `ground_sign_direction`=0 |
| `wall_banner` | `facing_direction`=0 |
| `chest` | `minecraft:cardinal_direction`="north", `facing_direction`=2 |
| `furnace` | `minecraft:cardinal_direction`="south", `facing_direction`=3 |
| `hopper` | `toggle_bit`=false, `facing_direction`=0 |
| `piston` / `sticky_piston` | `facing_direction`=0 |
| `observer` | `minecraft:facing_direction`="down", `powered_bit`=false, `facing_direction`=0 |
| `dispenser` / `dropper` | `triggered_bit`=false, `facing_direction`=0 |
| `anvil` | `minecraft:cardinal_direction`="south", `damage`="undamaged", `direction`=0 |
| `sandstone` | `sand_stone_type`="default" |
| `redstone_wire` | `redstone_signal`=0 |
| `unpowered_repeater` / `powered_repeater` | `minecraft:cardinal_direction`="south", `repeater_delay`=0, `direction`=0 |
| `unpowered_comparator` / `powered_comparator` | `minecraft:cardinal_direction`="south", `output_lit_bit`=false, `output_subtract_bit`=false, `direction`=0 |
| `rail` | `rail_direction`=0 |
| `lever` | `lever_direction`="down_east_west", `open_bit`=false |
| `stone_button` | `facing_direction`=0, `button_pressed_bit`=false |
| `stone_pressure_plate` | `redstone_signal`=0 |
| `candle` | `candles`=0, `lit`=false |
| `bell` | `attachment`="standing", `toggle_bit`=false, `direction`=0 |
| `lantern` | `hanging`=false |
| `campfire` | `minecraft:cardinal_direction`="south", `extinguished`=false, `direction`=0 |
| `grindstone` | `attachment`="standing", `direction`=0 |
| `stonecutter_block` | `minecraft:cardinal_direction`="north", `facing_direction`=2 |
| `end_rod` / `lightning_rod` | `facing_direction`=0 |
| `tripwire_hook` | `powered_bit`=false, `direction`=0, `attached_bit`=false |
| `vine` | `vine_direction_bits`=0 |
| `snow_layer` | `height`=0, `covered_bit`=false |
| `farmland` | `moisturized_amount`=0 |
| `chorus_flower` | `age`=0 |
| `bamboo` | `bamboo_leaf_size`="no_leaves", `bamboo_stalk_thickness`="thin", `age_bit`=false |
| `pointed_dripstone` | `dripstone_thickness`="tip", `hanging`=true |
| `polished_deepslate` / `glass_pane` / `iron_bars` / `grass_path` | (无状态) |

## 朝向数值速记

- `facing_direction`: **0下 1上 2北 3南 4西 5东**(基岩通用)。
- `weirdo_direction`(楼梯): **0东 1西 2南 3北**。
- `minecraft:cardinal_direction` / `direction` 类: 直接用 `"north"/"south"/"east"/"west"` 时更直观; 旧式 `direction`(0–3)与门/活板门相关的朝向请以实测为准。
- 立式告示牌/旗帜 `ground_sign_direction`: 0–15, 每档 22.5°。
