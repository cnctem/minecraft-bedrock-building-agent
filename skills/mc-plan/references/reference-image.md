<!-- 整理自 Java 模组 ImageBuildGuide / ImageDepthExtruder / ReferenceImageVoxelizer /
     ImageVolumeSculptor 的做法: 参考图 → 正面剪影 → 纵深分层 → 体素。
     本项目没有图片→体素的自动管线, 这里保留“看图施工”的判据与配色映射,
     落地方式改为: 看图 → 自己写建造程序(或先描网格)。 -->

# 参考图施工法（照着玩家给的图建）

玩家给一张图说“照这个建”时，第一目标**不是自由发挥**，而是把图变成三维：
**剪影一致 → 主色分区一致 → 关键特征（眼/窗/门/标志）一致 → 纵深合理**。

## 1. 体量口径

原模组的换算：**4×4 像素 ≈ 1 个方块**。

```
成品正面宽 ≈ 图片像素宽 / 4
成品正面高 ≈ 图片像素高 / 4
总方块数 ≈ 正面格数 × 平均纵深（厚度）
```

- 体量按**图片**定，不按“规模档位”放大或缩小；
- 若图很大（比如 512×512 → 128×128 正面），一次提交装不下，就按“正面分块 + 纵深分层”切；
- 先跟玩家确认一句“按这个比例大概是 W×H 格，可以吗”，比建完返工便宜。

## 2. 正面剪影（最重要的一步）

1. 先把图**压成低分辨率字符网格**（1 字符 ≈ 1 格），只保留 `#`(实心) / `.`(空)；
   网格宽高按上面的口径。
2. 对照原图检查：宽高比有没有被拉扁/拉长？关键转折（耳鳍、发梢、尾巴、屋檐）是否还占 2~3 格？
3. 剪影定稿后再谈材质；剪影错了，后面全白做。
4. 左右对称的题材，让网格关于中轴对称（本项目：`build_preview(..., symmetry="u")` 直接验）。

## 3. 纵深（厚度）分层

原模组会单独让模型给每个像素一个 0~9 的厚度，并**拒绝“整张图同一个厚度”**（那是块厚板）。
判据：

| 部位 | 厚度 |
|---|---|
| 躯干、头、裙子、底座、饱满处 | 7~9 |
| 四肢、面部、服饰主体 | 4~6 |
| 耳鳍、尾鳍、发梢、飘带、边缘 | 1~3 |
| 本来就不该有方块的地方 | 0 |

原模组会检查“不同厚度档位 ≥3 种”，否则判定“没在思考”并替换。
本项目对应做法：写程序时用**厚度变量**而不是常数：

```python
def depth_at(u, v):        # 手动给几个区域，别用同一个数字
    if v > HEAD:  return 6
    if v > BODY:  return 8
    return 4

for u in range(W):
    for v in range(H):
        if solid(u, v):
            d = depth_at(u, v)
            api.fill((u, v, 0), (u, v, d - 1), color(u, v))
```

## 4. 颜色 → 方块（原模组给的映射，直接照用）

| 图片颜色 | 方块 |
|---|---|
| 白/米白 | `white_concrete` / `quartz_block` / `smooth_quartz` |
| 浅灰 | `light_gray_concrete` / `stone` / `andesite` |
| 中灰 | `gray_concrete` / `stonebrick` / `deepslate_tiles` |
| 深灰/黑 | `black_concrete` / `deepslate` / `blackstone` |
| 红 | `red_concrete` / `red_terracotta` / `brick_block` |
| 橙 | `orange_concrete` / `orange_terracotta` |
| 黄 | `yellow_concrete` / `gold_block` |
| 绿 | `green_concrete` / `lime_concrete` / `moss_block` |
| 青蓝 | `cyan_concrete` / `light_blue_concrete` |
| 蓝 | `blue_concrete` / `lapis_block` |
| 紫 | `purple_concrete` / `magenta_concrete` |
| 粉 | `pink_concrete` |
| 棕/木 | `oak_planks` / `spruce_planks` / `brown_concrete` |
| 金属 | `iron_block` / `copper_block` |
| 透明 | `glass` / `glass_pane` |

同色系挑 1~2 种即可；整张图主色不超过 5 种，否则会花。

## 5. 输出前自检

1. 正面剪影和图片对得上吗？（最重要）
2. 宽高比是否与图片一致（没有被拉扁/拉长）？
3. 主色分区是否 ≤5 种，且关键特征（眼睛/窗/门/标志）都在？
4. 纵深是否有 ≥3 个档位，而不是一块板？
5. 有没有多加“展示台/边框底座”？（除非玩家要，否则不要）
6. 建完用 `render_build(views=["front"])` 和原图并排看一遍；不对就改程序重来。

## 6. 本项目落地顺序

1. `read_url` 或玩家附图（图片会作为消息附件给到你）先**看图**，用文字记下：主体、主色、关键特征；
2. 估体量（宽高/4）并告诉玩家；
3. 画剪影网格（可写在消息里自检，不必给玩家看）；
4. 写程序：剪影用 `fill`，纵深用厚度变量，颜色走上面的映射；
5. `build_preview` → `render_build(views=["front","iso"])` → 与图对比 → `build_commit`；
6. 正面优先，侧面/背面按“同一材质语言”补，不要背面完全不管。
