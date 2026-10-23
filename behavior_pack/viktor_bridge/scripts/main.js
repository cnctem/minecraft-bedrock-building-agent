// Viktor Bridge: 把聊天、玩家坐标、物品栏桥接给外部 bot。
// BDS 控制台不回显玩家聊天, 这里用 console.log 输出到控制台/日志。
//
// 协议 v2: bot 在事件参数最前面带一个请求 id `r<数字>`, 本脚本把该 id 原样回显到
// 每一行输出里, 于是 bot 可以一次下发整批请求、再按 id 认领各自回包 (见 [VIKTOR-*] 行)。
// 旧格式 (无 id) 依旧兼容: takeId 只在首 token 形如 r123 时才认作 id。
import { world, system, ItemTypes, BlockTypes } from "@minecraft/server";
import * as mc from "@minecraft/server";
import { ActionFormData } from "@minecraft/server-ui";

const CHAT_TAG = "[VIKTOR-CHAT]";
const POS_TAG = "[VIKTOR-POS]";
const INV_TAG = "[VIKTOR-INV]";
const BLOCK_TAG = "[VIKTOR-BLOCK]";
const IDS_TAG = "[VIKTOR-IDS]";  // 导出全部物品/方块 ID, 供离线生成速查表
const HELLO_TAG = "[VIKTOR-HELLO]";  // 协议握手: bot 据此判断行为包是否支持 v2
const MENU_TAG = "[VIKTOR-MENU]";    // 可点击菜单(server-ui 表单)回执
const MAP_TAG = "[VIKTOR-MAP]";        // 地形高度图
const SLICE_TAG = "[VIKTOR-SLICE]";    // 二维切面(调色板 + base36 行)
const INSPECT_TAG = "[VIKTOR-INSPECT]"; // 三维区域摘要 / 单元列表 / 不符合项
const FIND_TAG = "[VIKTOR-FIND]";      // 区域内搜方块坐标
const CAPS_TAG = "[VIKTOR-CAPS]";      // 能力广播(协议/可用 API/各项上限)
const BUILD_TAG = "[VIKTOR-BUILD]";    // 建造引擎回包(分帧 JSON)
// v3: 新增 heightmap/slice/inspect/find/caps; 查询回包改为「一个 JSON payload 分多帧」
const PROTOCOL = "v4";
// 分帧: 每帧 JSON 字符数。console.log 的行长没有官方保证, 700 是实测安全的保守值;
// 一帧一行, bot 侧按 `#i/n` 重组, 因此单次回包不再受行长限制。
const FRAME_CHARS = 700;
// 大范围扫描的时间切片: 每个 tick 处理多少格后让出主线程。
// 太小会拖长任务(4096 格 ≈ 8 tick), 太大则单 tick 卡顿; 512 实测平稳。
const CELLS_PER_TICK = 512;
const HARD_VOLUME = 32768;   // inspect/find 三维体积硬上限(格; 与 bot 声明一致, 32³)
const HARD_COLUMNS = 4096;   // heightmap 列数硬上限(64×64)
const HARD_SLICE = 4096;     // slice 单面格数硬上限(64×64)
const WORLD_TOP = 320;       // 主世界建造上限(用于高度图缺省搜索窗口)
const WORLD_BOTTOM = -64;
let subscribed = false;

try {
  world.beforeEvents.chatSend.subscribe((ev) => {
    console.log(`${CHAT_TAG} ${ev.sender.name}: ${ev.message}`);
  });
  subscribed = true;
} catch (e) {
  console.error(`${CHAT_TAG} 订阅 chatSend 失败: ${e}`);
}

// 玩家坐标上报“方块坐标”(block position): 对实体坐标向下取整, 与基岩版左上角
// “Show Coordinates”显示的整数完全一致。不能用四舍五入——例如实体 x=1670.5 时
// 屏幕上显示 1670, 而 round 会得到 1671, 与玩家所见不符。
const blockCoord = (n) => Math.floor(n);

// 协议 v2: 首 token 是请求 id(r<数字>) 时拆出来, 否则视为旧格式。
function takeId(message) {
  const s = String(message || "").trim();
  const m = s.match(/^(r\d+)(?:\s+([\s\S]*))?$/);
  return m ? { id: m[1], rest: (m[2] || "").trim() } : { id: "", rest: s };
}

function tagOf(base, id) {
  return id ? `${base} ${id}` : base;
}

// ---------- v3: JSON payload 分帧 + 调色板 ----------
// 一次查询只回一个 JSON; 超过一帧长度就切成 `#i/n <片段>` 多行, 末行 DONE。
// bot 侧按 index 重组(不依赖到达顺序), 于是大块数据的传输不受单行长度限制。
function emitPayload(tagBase, id, payload) {
  const tag = tagOf(tagBase, id);
  let s;
  try {
    s = JSON.stringify(payload);
  } catch (e) {
    s = JSON.stringify({ ok: false, error: `payload 序列化失败: ${e}` });
  }
  const n = Math.max(1, Math.ceil(s.length / FRAME_CHARS));
  for (let i = 0; i < n; i++) {
    console.log(`${tag} #${i + 1}/${n} ${s.slice(i * FRAME_CHARS, (i + 1) * FRAME_CHARS)}`);
  }
  console.log(`${tag} DONE`);
}

function shortId(typeId) {
  return String(typeId || "").replace(/^minecraft:/, "");
}

// 调色板: 方块 ID -> 索引(按首次出现顺序), 输出里只存索引, 体积降一个数量级。
// limit=36 时索引可用单字符 base36 编码, 超出的类型统一归到最后一格 "?"。
function makePalette(limit) {
  const at = new Map();
  const list = [];
  const cap = limit && limit > 1 ? limit : 0;   // 0 = 不限
  return {
    id(typeId) {
      const t = shortId(typeId);
      let i = at.get(t);
      if (i !== undefined) return i;
      if (cap && list.length >= cap - 1) {
        i = cap - 1;
        at.set(t, i);
        if (!list[i]) list[i] = "?";
        return i;
      }
      i = list.length;
      at.set(t, i);
      list.push(t);
      return i;
    },
    list,
  };
}

function resolveDimension(arg) {
  const d = String(arg || "overworld").toLowerCase();
  if (d === "nether" || d === "minecraft:nether") return world.getDimension("nether");
  if (d === "the_end" || d === "end" || d === "minecraft:the_end") return world.getDimension("the_end");
  return world.getDimension("overworld");
}

// 区块未加载 / 越界: getBlock 会抛错或返回 undefined, 统一归为“读不到”。
function readBlock(dim, x, y, z) {
  try {
    return dim.getBlock({ x, y, z }) || undefined;
  } catch (e) {
    return undefined;
  }
}

function fail(tag, id, message) {
  emitPayload(tag, id, { ok: false, error: message });
}

// 解析一组整数参数; 失败返回 null。
function ints(parts, from, count) {
  const out = [];
  for (let i = from; i < from + count; i++) {
    const v = Number(parts[i]);
    if (parts[i] === undefined || !Number.isFinite(v)) return null;
    out.push(Math.floor(v));
  }
  return out;
}

function getPlayers() {
  try {
    return world.getAllPlayers();
  } catch (e) {
    console.error(`[VIKTOR] getAllPlayers 失败: ${e}`);
    return [];
  }
}

// 坐标查询: `scriptevent viktor:pos [id]`
// 每人一行; 无论有无玩家, 末尾都补一条 `DONE` 让 bot 有明确终止信号。
function reportPositions(message) {
  const { id } = takeId(message);
  const tag = tagOf(POS_TAG, id);
  const players = getPlayers();
  if (players.length === 0) {
    console.log(`${tag} (无玩家在线)`);
  }
  for (const p of players) {
    try {
      const l = p.location;
      console.log(`${tag} ${p.name} ${blockCoord(l.x)} ${blockCoord(l.y)} ${blockCoord(l.z)} ${p.dimension.id}`);
    } catch (e) {
      console.error(`${tag} 读取 ${p.name} 坐标失败: ${e}`);
    }
  }
  if (id) console.log(`${tag} DONE`);
}

// 物品栏/手持查询: `scriptevent viktor:inv [id]`
// 每人若干行: `<玩家> <槽位> <物品ID> <数量>`; 每人末行 `<玩家> DONE <手持槽位>`;
// 全体末尾再补一条 `DONE` 作为整批终止信号。
function reportInventory(message) {
  const { id } = takeId(message);
  const tag = tagOf(INV_TAG, id);
  const players = getPlayers();
  if (players.length === 0) {
    console.log(`${tag} (无玩家在线)`);
  }
  for (const p of players) {
    let container = undefined;
    let selected = -1;
    try {
      const inv = p.getComponent("minecraft:inventory");
      container = inv?.container;
      selected = inv?.selectedSlotIndex ?? p.selectedSlotIndex ?? -1;
    } catch (e) {
      console.error(`${tag} ${p.name} 读取物品栏组件失败: ${e}`);
    }
    if (!container) {
      console.log(`${tag} ${p.name} DONE ${selected}`);
      continue;
    }
    for (let i = 0; i < container.size; i++) {
      try {
        const item = container.getItem(i);
        if (!item) continue;
        console.log(`${tag} ${p.name} ${i} ${item.typeId} ${item.amount}`);
      } catch (e) {
        console.error(`${tag} ${p.name} 读取槽位 ${i} 失败: ${e}`);
      }
    }
    console.log(`${tag} ${p.name} DONE ${selected}`);
  }
  if (id) console.log(`${tag} DONE`);
}

// 方块查询: `scriptevent viktor:block [id] <x> <y> <z> [维度]`
// 基岩版没有 `data get block`(那是 Java 版), 只能由脚本读取方块类型
function reportBlock(message) {
  const { id, rest } = takeId(message);
  const tag = tagOf(BLOCK_TAG, id);
  const parts = String(rest || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length < 3) {
    console.log(`${tag} (参数不足: 需要 x y z [维度])`);
    return;
  }
  const x = Math.floor(Number(parts[0]));
  const y = Math.floor(Number(parts[1]));
  const z = Math.floor(Number(parts[2]));
  if (![x, y, z].every(Number.isFinite)) {
    console.log(`${tag} (坐标不是数字: ${parts.slice(0, 3).join(" ")})`);
    return;
  }
  const dimArg = String(parts[3] || "overworld").toLowerCase();
  let dimension;
  try {
    if (dimArg === "nether" || dimArg === "minecraft:nether") dimension = world.getDimension("nether");
    else if (dimArg === "the_end" || dimArg === "end" || dimArg === "minecraft:the_end") dimension = world.getDimension("the_end");
    else dimension = world.getDimension("overworld");
  } catch (e) {
    console.log(`${tag} (未知维度 ${parts[3]})`);
    return;
  }
  try {
    const block = dimension.getBlock({ x, y, z });
    if (!block) {
      console.log(`${tag} (区块未加载或超出世界高度: ${x} ${y} ${z})`);
      return;
    }
    // 附带方块状态(朝向、半砖、开关等), 便于判断具体形态
    let states = "";
    try {
      const st = block.permutation.getAllStates();
      if (st && Object.keys(st).length) states = " " + JSON.stringify(st);
    } catch (e) { /* 部分方块无状态 */ }
    console.log(`${tag} ${x} ${y} ${z} ${dimension.id} ${block.typeId}${states}`);
  } catch (e) {
    console.log(`${tag} (读取失败: ${e})`);
  }
}

// ---------- v3: 感知原语 ----------
// 目标: 让 bot 用「由粗到细」的少数几次调用看清现场, 而不是切几十个薄片、每格一行。
//   caps      : 能力广播(协议/可用 API/上限)
//   heightmap : 每列地表高度 + 顶面方块(选址/地形/地基)
//   slice     : 一张平面/立面/剖面(调色板 + base36 行), 看形状最省 token
//   inspect   : 三维区域摘要(类型计数) / 单元清单 / 与 filter 不符的位置(= 空洞、填错)
//   find      : 在三维区域内找某方块的全部坐标

function reportCaps(message) {
  const { id } = takeId(message);
  let fillBlocks = false;
  try {
    fillBlocks = typeof world.getDimension("overworld").fillBlocks === "function";
  } catch (e) { /* 旧引擎无此 API */ }
  emitPayload(CAPS_TAG, id, {
    ok: true,
    proto: PROTOCOL,
    apis: { runJob: typeof system.runJob === "function", fillBlocks },
    limits: {
      volume: HARD_VOLUME, columns: HARD_COLUMNS, slice: HARD_SLICE,
      frame: FRAME_CHARS, cellsPerTick: CELLS_PER_TICK,
    },
  });
}

// 一列的地表: 从猜测高度出发向上爬到顶、再向下找到第一个非空气。
// 相邻列高度相关, 用上一列结果当猜测, 平均每列只探 1~3 次, 比逐格从 320 扫下来快两个数量级。
function* heightmapJob(tag, id, dim, xs, zs, yMax, yMin) {
  const pal = makePalette();
  const heights = [];
  const types = [];
  let unloaded = 0, missing = 0, work = 0, guess = yMax;
  for (let z = zs[0]; z <= zs[1]; z++) {
    for (let x = xs[0]; x <= xs[1]; x++) {
      let y = Math.min(yMax, Math.max(yMin, guess));
      let b = readBlock(dim, x, y, z);
      work++;
      if (b === undefined) {           // 首探就失败 -> 该列未加载
        unloaded++;
        heights.push(-1);
        types.push(255);
        guess = yMax;
        continue;
      }
      while (y < yMax) {               // 猜测点埋在实心地形里(悬崖/上坡): 向上爬到顶
        const up = readBlock(dim, x, y + 1, z);
        work++;
        if (up === undefined || up.typeId === "minecraft:air") break;
        y++;
        b = up;
      }
      while (b !== undefined && b.typeId === "minecraft:air" && y > yMin) {
        y--;                           // 下坡/空列: 向下找
        b = readBlock(dim, x, y, z);
        work++;
      }
      if (b !== undefined && b.typeId !== "minecraft:air") {
        heights.push(y);
        types.push(pal.id(b.typeId));
        guess = y;
      } else {
        missing++;
        heights.push(-1);
        types.push(255);
      }
      if (work >= CELLS_PER_TICK) { work = 0; yield; }
    }
  }
  let lo = -1, hi = -1;
  for (const h of heights) {
    if (h < 0) continue;
    if (lo < 0 || h < lo) lo = h;
    if (h > hi) hi = h;
  }
  emitPayload(tag, id, {
    ok: true, dim: dim.id,
    from: [xs[0], zs[0]], to: [xs[1], zs[1]],
    w: xs[1] - xs[0] + 1, h: zs[1] - zs[0] + 1,
    yMin, yMax, palette: pal.list, heights, types,
    low: lo, high: hi, unloaded, missing,
  });
}

function heightmap(message) {
  const { id, rest } = takeId(message);
  const parts = String(rest || "").trim().split(/\s+/).filter(Boolean);
  const box = ints(parts, 0, 4);
  if (!box) {
    fail(MAP_TAG, id, "参数需为 x1 z1 x2 z2 [维度] [yMax] [yMin]");
    return;
  }
  const xs = [Math.min(box[0], box[2]), Math.max(box[0], box[2])];
  const zs = [Math.min(box[1], box[3]), Math.max(box[1], box[3])];
  const cols = (xs[1] - xs[0] + 1) * (zs[1] - zs[0] + 1);
  if (cols > HARD_COLUMNS) {
    fail(MAP_TAG, id, `列数 ${xs[1] - xs[0] + 1}×${zs[1] - zs[0] + 1}=${cols} 超过上限 ${HARD_COLUMNS}`);
    return;
  }
  let yMax = WORLD_TOP, yMin = WORLD_BOTTOM;
  if (parts[5] !== undefined) {
    const v = Number(parts[5]);
    if (!Number.isFinite(v)) { fail(MAP_TAG, id, `yMax 不是数字: ${parts[5]}`); return; }
    yMax = Math.floor(v);
  }
  if (parts[6] !== undefined) {
    const v = Number(parts[6]);
    if (!Number.isFinite(v)) { fail(MAP_TAG, id, `yMin 不是数字: ${parts[6]}`); return; }
    yMin = Math.floor(v);
  }
  if (yMin > yMax) { const t = yMin; yMin = yMax; yMax = t; }
  const job = heightmapJob(MAP_TAG, id, resolveDimension(parts[4]), xs, zs, yMax, yMin);
  runJob(job);
}

// 一张平面: 调色板 + 每行 base36 索引。
// axis=y: a=x b=z(俯视) / axis=x: a=z b=y(侧视) / axis=z: a=x b=y(前视)。
// 侧视/前视的行按 y 从高到低输出, 看立面不用自己脑内翻转。
function* sliceJob(tag, id, dim, axis, level, a0, a1, b0, b1, bStep) {
  const pal = makePalette(36);   // 36 = 0-9a-z 单字符; 超出部分归入索引 35 的 "?"
  const rows = [];
  const counts = [];
  let unloaded = 0, work = 0;
  for (let b = b0; bStep > 0 ? b <= b1 : b >= b1; b += bStep) {
    let row = "";
    for (let a = a0; a <= a1; a++) {
      const x = axis === "y" ? a : axis === "x" ? level : a;
      const y = axis === "y" ? level : b;
      const z = axis === "y" ? b : axis === "x" ? a : level;
      const blk = readBlock(dim, x, y, z);
      work++;
      if (!blk) {
        row += "?";
        unloaded++;
      } else {
        const i = pal.id(blk.typeId);
        row += i.toString(36);
        counts[i] = (counts[i] || 0) + 1;
      }
    }
    rows.push(row);
    if (work >= CELLS_PER_TICK) { work = 0; yield; }
  }
  emitPayload(tag, id, {
    ok: true, dim: dim.id, axis, level,
    a0, a1, b0, b1, w: a1 - a0 + 1, h: Math.abs(b1 - b0) + 1,
    palette: pal.list, rows, counts, unloaded,
  });
}

function sliceBlocks(message) {
  const { id, rest } = takeId(message);
  const parts = String(rest || "").trim().split(/\s+/).filter(Boolean);
  const axis = String(parts[0] || "y").toLowerCase();
  if (axis !== "x" && axis !== "y" && axis !== "z") {
    fail(SLICE_TAG, id, `axis 必须是 x/y/z, 收到 ${parts[0]}`);
    return;
  }
  const level = Number(parts[1]);
  if (!Number.isFinite(level)) {
    fail(SLICE_TAG, id, `level 不是数字: ${parts[1]}`);
    return;
  }
  const ab = ints(parts, 2, 4);
  if (!ab) {
    fail(SLICE_TAG, id, "参数需为 x1 z1 x2 z2 [维度]");
    return;
  }
  const a0 = Math.min(ab[0], ab[2]), a1 = Math.max(ab[0], ab[2]);
  const b0r = Math.min(ab[1], ab[3]), b1r = Math.max(ab[1], ab[3]);
  const cells = (a1 - a0 + 1) * (b1r - b0r + 1);
  if (cells > HARD_SLICE) {
    fail(SLICE_TAG, id, `切面 ${a1 - a0 + 1}×${b1r - b0r + 1}=${cells} 格超过上限 ${HARD_SLICE}`);
    return;
  }
  // 侧视/前视从上往下画
  const b0 = axis === "y" ? b0r : b1r;
  const b1 = axis === "y" ? b1r : b0r;
  const bStep = axis === "y" ? 1 : -1;
  const job = sliceJob(SLICE_TAG, id, resolveDimension(parts[6]), axis,
    Math.floor(level), a0, a1, b0, b1, bStep);
  runJob(job);
}

// 三维区域: 默认只回类型计数(体积可以很大); detail=cells 回具体坐标。
// 给了 filter 时额外回「不符合 filter 的位置」——复检空洞/填错就靠这个, 不用自己数行。
function* inspectJob(tag, id, dim, xs, ys, zs, filter, detail, limit) {
  const pal = makePalette();
  const counts = [];
  const cells = [];
  const mismHoles = [];   // 空洞优先: 复检时最该先看到的就是“该有方块却是空气”
  const mismOther = [];
  let volume = 0, unloaded = 0, air = 0, match = 0, mismatch = 0, holes = 0, wrong = 0, work = 0;
  for (let x = xs[0]; x <= xs[1]; x++) {
    for (let y = ys[0]; y <= ys[1]; y++) {
      for (let z = zs[0]; z <= zs[1]; z++) {
        volume++;
        work++;
        const blk = readBlock(dim, x, y, z);
        if (!blk) {
          unloaded++;
        } else {
          const t = shortId(blk.typeId);
          const isAir = t === "air";
          if (isAir) air++;
          const hit = filter ? t.includes(filter) : true;
          if (hit) match++;
          const i = pal.id(blk.typeId);
          counts[i] = (counts[i] || 0) + 1;
          if (detail === "cells" && hit && !isAir && cells.length < limit) cells.push([x, y, z, i]);
          if (filter && !hit) {
            mismatch++;
            if (isAir) {
              holes++;
              if (mismHoles.length < limit) mismHoles.push([x, y, z, t]);
            } else {
              wrong++;
              if (mismOther.length < limit) mismOther.push([x, y, z, t]);
            }
          }
        }
        if (work >= CELLS_PER_TICK) { work = 0; yield; }
      }
    }
  }
  const entries = counts
    .map((n, i) => [pal.list[i], n])
    .sort((p, q) => q[1] - p[1]);
  const top = {};
  let shown = 0;
  for (const [name, n] of entries) {
    if (shown++ >= 12) break;
    top[name] = n;
  }
  const other = entries.slice(12).reduce((s, e) => s + e[1], 0);
  const out = {
    ok: true, dim: dim.id,
    from: [xs[0], ys[0], zs[0]], to: [xs[1], ys[1], zs[1]],
    volume, unloaded, air, types: top, otherTypes: other, palette: pal.list,
  };
  if (filter) {
    out.filter = filter;
    out.match = match;
    out.mismatch = mismatch;          // 含空气: 空洞也算不符合
    out.holes = holes;                // 空洞(该有方块却是空气)
    out.wrong = wrong;                // 放错(有方块但不是目标)
    out.mismatchSamples = mismHoles.concat(mismOther).slice(0, limit);
  }
  if (detail === "cells") {
    out.cells = cells;
    out.cellsTruncated = cells.length >= limit;
  }
  emitPayload(tag, id, out);
}

function inspectRegion(message) {
  const { id, rest } = takeId(message);
  const parts = String(rest || "").trim().split(/\s+/).filter(Boolean);
  const box = ints(parts, 0, 6);
  if (!box) {
    fail(INSPECT_TAG, id, "参数需为 x1 y1 z1 x2 y2 z2 [维度] [filter] [detail] [limit]");
    return;
  }
  const xs = [Math.min(box[0], box[3]), Math.max(box[0], box[3])];
  const ys = [Math.min(box[1], box[4]), Math.max(box[1], box[4])];
  const zs = [Math.min(box[2], box[5]), Math.max(box[2], box[5])];
  const volume = (xs[1] - xs[0] + 1) * (ys[1] - ys[0] + 1) * (zs[1] - zs[0] + 1);
  if (volume > HARD_VOLUME) {
    fail(INSPECT_TAG, id, `体积 ${volume} 超过上限 ${HARD_VOLUME}, 请拆成几块`);
    return;
  }
  // "-" = 不带 filter 的占位符(空字符串会把后面的位置参数挤位)
  const rawFilter = String(parts[7] || "-").toLowerCase().replace(/^minecraft:/, "");
  const filter = rawFilter === "-" ? "" : rawFilter;
  const detail = String(parts[8] || "summary").toLowerCase();
  let limit = Number(parts[9]);
  if (!Number.isFinite(limit)) limit = 64;
  limit = Math.max(1, Math.min(Math.floor(limit), 512));
  const job = inspectJob(INSPECT_TAG, id, resolveDimension(parts[6]),
    xs, ys, zs, filter, detail, limit);
  runJob(job);
}

function* findJob(tag, id, dim, block, xs, ys, zs, limit) {
  const positions = [];
  let match = 0, unloaded = 0, volume = 0, work = 0;
  for (let x = xs[0]; x <= xs[1]; x++) {
    for (let y = ys[0]; y <= ys[1]; y++) {
      for (let z = zs[0]; z <= zs[1]; z++) {
        volume++;
        work++;
        const blk = readBlock(dim, x, y, z);
        if (!blk) {
          unloaded++;
        } else if (shortId(blk.typeId).includes(block)) {
          match++;
          if (positions.length < limit) positions.push([x, y, z]);
        }
        if (work >= CELLS_PER_TICK) { work = 0; yield; }
      }
    }
  }
  emitPayload(tag, id, {
    ok: true, dim: dim.id, block,
    from: [xs[0], ys[0], zs[0]], to: [xs[1], ys[1], zs[1]],
    volume, unloaded, match,
    positions, truncated: match > positions.length,
  });
}

function findBlocks(message) {
  const { id, rest } = takeId(message);
  const parts = String(rest || "").trim().split(/\s+/).filter(Boolean);
  const block = String(parts[0] || "").toLowerCase().replace(/^minecraft:/, "");
  if (!block) {
    fail(FIND_TAG, id, "缺少方块 ID(可用片段, 如 diamond_ore / ore)");
    return;
  }
  const box = ints(parts, 1, 6);
  if (!box) {
    fail(FIND_TAG, id, "参数需为 <方块ID> x1 y1 z1 x2 y2 z2 [维度] [limit]");
    return;
  }
  const xs = [Math.min(box[0], box[3]), Math.max(box[0], box[3])];
  const ys = [Math.min(box[1], box[4]), Math.max(box[1], box[4])];
  const zs = [Math.min(box[2], box[5]), Math.max(box[2], box[5])];
  const volume = (xs[1] - xs[0] + 1) * (ys[1] - ys[0] + 1) * (zs[1] - zs[0] + 1);
  if (volume > HARD_VOLUME) {
    fail(FIND_TAG, id, `体积 ${volume} 超过上限 ${HARD_VOLUME}, 请拆成几块`);
    return;
  }
  let limit = Number(parts[8]);
  if (!Number.isFinite(limit)) limit = 128;
  limit = Math.max(1, Math.min(Math.floor(limit), 512));
  const job = findJob(FIND_TAG, id, resolveDimension(parts[7]), block,
    xs, ys, zs, limit);
  runJob(job);
}

// 统一跑 job: 有 system.runJob 就用它(分片让出主线程), 旧引擎兜底同步跑完。
function runJob(job) {
  if (typeof system.runJob === "function") {
    system.runJob(job);
    return;
  }
  let r = job.next();
  while (!r.done) r = job.next();
}


// ---------- v4: 建造引擎 ----------
// 分工: bot 负责把「建造程序」编译成期望体素(纯几何), 这里负责
//   预览(diff) → 提交(贪心合并 + fillBlocks 时间切片) → 校验(复读比对) → 撤销(before 体积)
// 期望体积编码: palette(索引 0 固定 = KEEP 不写) + 分层 RLE("idx:count" base36, 逗号分隔)。
const BUILD_MAX_VOLUME = 65536;      // 单次操作体积上限(格)
const BUILD_TTL_MS = 10 * 60 * 1000; // 暂存操作有效期
const BUILD_MAX_PENDING = 4;         // 同时暂存的操作数
const BUILD_MAX_UNDO = 2;            // 撤销栈深度
const BUILD_SAMPLES = 8;             // 回包里每类样本条数
// 这些方块不允许被覆盖(世界骨架/系统方块)
const PROTECTED_TYPES = new Set([
  "bedrock", "barrier", "command_block", "chain_command_block", "repeating_command_block",
  "structure_block", "structure_void", "jigsaw", "light_block", "deny", "allow", "border_block",
]);
// 多格方块: 单格写入会留下残缺的另一半(本引擎版本早于 1.26.10 的官方修复)
const UNSUPPORTED_TYPES = new Set([
  "bed", "tall_grass", "large_fern", "sunflower", "lilac", "rose_bush", "peony",
  "small_dripleaf", "big_dripleaf", "big_dripleaf_stem", "tall_dripleaf", "pitcher_plant",
  "cave_vines", "cave_vines_body_with_berries", "cave_vines_head_with_berries",
  "hanging_roots", "spore_blossom",
]);
const builds = new Map();  // jid -> { parts, total, raw, op, created, aborted, before, name }
const undoStack = [];      // [{ jid, name, op }]

function splitAction(message) {
  const s = String(message || "").trim();
  const i = s.indexOf(" ");
  return i < 0 ? { action: s.toLowerCase(), rest: "" } : { action: s.slice(0, i).toLowerCase(), rest: s.slice(i + 1) };
}

function decodeRle(str, total) {
  const out = new Uint8Array(total);   // 缺省 0 = KEEP
  let pos = 0;
  if (str) {
    for (const part of String(str).split(",")) {
      if (!part) continue;
      const c = part.indexOf(":");
      const v = parseInt(part.slice(0, c), 36);
      const n = parseInt(part.slice(c + 1), 36);
      if (!Number.isFinite(v) || !Number.isFinite(n) || n <= 0) continue;
      const end = Math.min(total, pos + n);
      out.fill(v, pos, end);
      pos = end;
    }
  }
  return out;
}

function encodeRle(cells) {
  const parts = [];
  let i = 0;
  while (i < cells.length) {
    const v = cells[i];
    let j = i + 1;
    while (j < cells.length && cells[j] === v) j++;
    parts.push(`${v.toString(36)}:${(j - i).toString(36)}`);
    i = j;
  }
  return parts.join(",");
}

function decodeBuild(raw) {
  const obj = JSON.parse(raw);
  const o = (obj.o || []).map((v) => Math.floor(Number(v)));
  const s = (obj.s || []).map((v) => Math.floor(Number(v)));
  const pal = obj.p;
  if (o.length !== 3 || s.length !== 3 || !Array.isArray(pal) || pal.length === 0) {
    throw new Error("payload 需要 o[3] / s[3] / p[]");
  }
  if (s.some((v) => !Number.isFinite(v) || v <= 0)) throw new Error(`尺寸非法: ${s.join("x")}`);
  const volume = s[0] * s[1] * s[2];
  if (volume > BUILD_MAX_VOLUME) throw new Error(`体积 ${volume} 超过上限 ${BUILD_MAX_VOLUME}`);
  // bot 端发来的 p 已去掉索引 0(KEEP); 这里补回占位, 保证索引与 RLE 对齐
  const palette = [{ b: "keep" },
    ...pal.map((e) => (typeof e === "string" ? { b: e } : { b: String(e.b), s: e.s }))];
  if (palette.length > 65) throw new Error(`调色板 ${palette.length - 1} 项超过上限 64`);
  return {
    ox: o[0], oy: o[1], oz: o[2], sx: s[0], sy: s[1], sz: s[2],
    volume, cells: decodeRle(obj.rle, volume), palette,
  };
}

// 贪心合并: 每层做 2D 最大矩形合并, 再把同位置连续层合并成 3D 长方体。
// 目的是把「几万格」压成「几十个 fillBlocks 调用」。
function planBoxes(op) {
  const { ox, oy, oz, sx, sy, sz, cells } = op;
  const rects = [];
  const seen = new Uint8Array(sx * sz);
  for (let ly = 0; ly < sy; ly++) {
    seen.fill(0);
    const base = ly * sz * sx;
    for (let lz = 0; lz < sz; lz++) {
      for (let lx = 0; lx < sx; lx++) {
        const k = lz * sx + lx;
        if (seen[k]) continue;
        const p = cells[base + k];
        if (p === 0) { seen[k] = 1; continue; }
        let w = 1;
        while (lx + w < sx && !seen[k + w] && cells[base + k + w] === p) w++;
        let h = 1;
        outer: while (lz + h < sz) {
          for (let i = 0; i < w; i++) {
            const kk = (lz + h) * sx + lx + i;
            if (seen[kk] || cells[base + kk] !== p) break outer;
          }
          h++;
        }
        for (let dz = 0; dz < h; dz++) for (let i = 0; i < w; i++) seen[(lz + dz) * sx + lx + i] = 1;
        rects.push({ p, x0: ox + lx, x1: ox + lx + w - 1, z0: oz + lz, z1: oz + lz + h - 1, y: oy + ly });
      }
    }
  }
  const groups = new Map();
  for (const r of rects) {
    const key = `${r.x0},${r.x1},${r.z0},${r.z1},${r.p}`;
    const list = groups.get(key);
    if (list) list.push(r.y); else groups.set(key, [r.y]);
  }
  const boxes = [];
  for (const [key, ys] of groups) {
    ys.sort((a, b) => a - b);
    const [x0, x1, z0, z1, p] = key.split(",").map(Number);
    let start = ys[0], prev = ys[0];
    for (let i = 1; i <= ys.length; i++) {
      const y = ys[i];
      if (y !== prev + 1) {
        boxes.push({ x0, x1, z0, z1, y0: start, y1: prev, p });
        start = y;
      }
      prev = y;
    }
  }
  return boxes;
}

function resolvePerm(entry) {
  try {
    return mc.BlockPermutation.resolve(entry.b, entry.s);
  } catch (e) {
    return undefined;
  }
}

function cellCoords(op, i) {
  const layer = op.sx * op.sz;
  const y = op.oy + Math.floor(i / layer);
  const rem = i % layer;
  return { x: op.ox + (rem % op.sx), y, z: op.oz + Math.floor(rem / op.sx) };
}

function statesMatch(block, want) {
  if (!want) return true;
  try {
    const have = block.permutation.getAllStates() || {};
    for (const k of Object.keys(want)) {
      if (String(have[k]) !== String(want[k])) return false;
    }
    return true;
  } catch (e) {
    return false;
  }
}

// 提交前把「将要被覆盖的当前方块」存成同样的 palette+RLE, 撤销时原样写回。
function snapshotBefore(op, dim) {
  const total = op.volume;
  const cells = new Uint8Array(total);
  const palette = [{ b: "keep" }];
  const at = new Map();
  for (let i = 0; i < total; i++) {
    if (op.cells[i] === 0) continue;      // KEEP 格不动, 不记录
    const c = cellCoords(op, i);
    const b = readBlock(dim, c.x, c.y, c.z);
    if (!b) continue;                      // 未加载: 不记录, 撤销时也不碰
    let states;
    try {
      const st = b.permutation.getAllStates();
      if (st && Object.keys(st).length) states = st;
    } catch (e) { /* 无状态 */ }
    const key = `${b.typeId}|${states ? JSON.stringify(states) : ""}`;
    let pi = at.get(key);
    if (pi === undefined) {
      pi = palette.length;
      at.set(key, pi);
      palette.push({ b: b.typeId, s: states });
    }
    cells[i] = pi;
  }
  return { ox: op.ox, oy: op.oy, oz: op.oz, sx: op.sx, sy: op.sy, sz: op.sz,
           volume: total, cells, palette };
}

function* previewJob(rid, jid, op, dim) {
  const out = { place: 0, replace: 0, noop: 0, unloaded: 0, protectedN: 0, unsupported: 0 };
  const protSamples = [], badSamples = [], unloadSamples = [];
  let work = 0, cellsUsed = 0;
  let minX = Infinity, minY = Infinity, minZ = Infinity, maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
  for (let i = 0; i < op.volume; i++) {
    const pi = op.cells[i];
    if (pi === 0) continue;
    cellsUsed++;
    const entry = op.palette[pi];
    const name = shortId(entry.b);
    if (UNSUPPORTED_TYPES.has(name) || /_door$|_bed$/.test(name)) {
      out.unsupported++;
      if (badSamples.length < BUILD_SAMPLES) badSamples.push(name);
    }
    const c = cellCoords(op, i);
    minX = Math.min(minX, c.x); maxX = Math.max(maxX, c.x);
    minY = Math.min(minY, c.y); maxY = Math.max(maxY, c.y);
    minZ = Math.min(minZ, c.z); maxZ = Math.max(maxZ, c.z);
    const b = readBlock(dim, c.x, c.y, c.z);
    if (!b) {
      out.unloaded++;
      if (unloadSamples.length < BUILD_SAMPLES) unloadSamples.push([c.x, c.y, c.z]);
    } else {
      const cur = shortId(b.typeId);
      if (PROTECTED_TYPES.has(cur)) {
        out.protectedN++;
        if (protSamples.length < BUILD_SAMPLES) protSamples.push([c.x, c.y, c.z, cur]);
      }
      const same = b.typeId === entry.b && statesMatch(b, entry.s);
      if (same) out.noop++;
      else if (cur === "air") out.place++;
      else out.replace++;
    }
    if (++work >= CELLS_PER_TICK) { work = 0; yield; }
  }
  const boxes = planBoxes(op);
  const rec = builds.get(jid);
  if (rec) {
    rec.bounds = cellsUsed ? { from: [minX, minY, minZ], to: [maxX, maxY, maxZ] } : null;
    rec.cells = cellsUsed;
  }
  emitPayload(BUILD_TAG, rid, {
    ok: true, jid, name: rec ? rec.name : "", volume: op.volume, cells: cellsUsed,
    bounds: cellsUsed ? { from: [minX, minY, minZ], to: [maxX, maxY, maxZ] } : null,
    paletteSize: op.palette.length - 1,
    diff: out, plan: { boxes: boxes.length },
    samples: { protected: protSamples, unsupported: badSamples, unloaded: unloadSamples },
    warnings: buildWarnings(out, cellsUsed),
  });
}

function buildWarnings(diff, cells) {
  const w = [];
  if (diff.unloaded) w.push(`有 ${diff.unloaded} 格未加载, 这部分既不会写也不会被校验`);
  if (diff.protectedN) w.push(`有 ${diff.protectedN} 格是受保护方块, 会被跳过`);
  if (diff.unsupported) w.push(`有 ${diff.unsupported} 格是多格方块(门/床/高草等), 单格写入会残缺, 请改用普通方块`);
  if (cells > 20000) w.push(`本次 ${cells} 格, 提交会比较久, 建议按模块拆分`);
  return w;
}

function* executeJob(rid, jid, op, dim, before, extra) {
  const t0 = Date.now();
  const out = { changed: 0, boxes: 0, failed: 0, aborted: false };
  const boxes = planBoxes(op);
  out.boxes = boxes.length;
  const hasFill = typeof dim.fillBlocks === "function" && typeof mc.BlockVolume === "function";
  for (let bi = 0; bi < boxes.length; bi++) {
    const box = boxes[bi];
    const rec = builds.get(jid);
    if (rec && rec.aborted) { out.aborted = true; break; }
    const entry = op.palette[box.p];
    const perm = resolvePerm(entry);
    if (!perm) { out.failed++; continue; }
    const count = (box.x1 - box.x0 + 1) * (box.y1 - box.y0 + 1) * (box.z1 - box.z0 + 1);
    try {
      if (hasFill) {
        const vol = new mc.BlockVolume(
          { x: box.x0, y: box.y0, z: box.z0 },
          { x: box.x1, y: box.y1, z: box.z1 });
        dim.fillBlocks(vol, perm);
        out.changed += count;
      } else {
        for (let y = box.y0; y <= box.y1; y++) {
          for (let z = box.z0; z <= box.z1; z++) {
            for (let x = box.x0; x <= box.x1; x++) {
              try {
                const b = dim.getBlock({ x, y, z });
                if (b) { b.setPermutation(perm); out.changed++; }
              } catch (e) { /* 单格失败不中断整批 */ }
            }
          }
        }
      }
    } catch (e) {
      out.failed++;
    }
    if (bi % 8 === 7) yield;
  }
  yield;
  // 校验: 复读比对, 空洞优先
  const verify = { mismatch: 0, holes: 0, wrong: 0, unloaded: 0 };
  const holes = [], wrongs = [];
  let work = 0;
  for (let i = 0; i < op.volume; i++) {
    const pi = op.cells[i];
    if (pi === 0) continue;
    const entry = op.palette[pi];
    const c = cellCoords(op, i);
    const b = readBlock(dim, c.x, c.y, c.z);
    if (!b) { verify.unloaded++; }
    else if (b.typeId !== entry.b || !statesMatch(b, entry.s)) {
      verify.mismatch++;
      const cur = shortId(b.typeId);
      if (cur === "air" && shortId(entry.b) !== "air") {
        verify.holes++;
        if (holes.length < BUILD_SAMPLES) holes.push([c.x, c.y, c.z, "air"]);
      } else {
        verify.wrong++;
        if (wrongs.length < BUILD_SAMPLES) wrongs.push([c.x, c.y, c.z, cur]);
      }
    }
    if (++work >= CELLS_PER_TICK) { work = 0; yield; }
  }
  verify.samples = holes.concat(wrongs).slice(0, BUILD_SAMPLES);
  // 撤销记录
  if (before) {
    const rec = builds.get(jid);
    undoStack.push({ jid, name: rec ? rec.name : "", op: before });
    while (undoStack.length > BUILD_MAX_UNDO) undoStack.shift();
  }
  emitPayload(BUILD_TAG, rid, {
    ok: true, jid, changed: out.changed, boxes: out.boxes, failed: out.failed,
    aborted: out.aborted, ms: Date.now() - t0, verify,
    undoDepth: undoStack.length, ...extra,
  });
}

function gcBuilds() {
  const now = Date.now();
  for (const [jid, rec] of builds) {
    if (now - rec.created > BUILD_TTL_MS) builds.delete(jid);
  }
}

function getBuildOp(jid) {
  const rec = builds.get(jid);
  if (!rec) return { err: `操作 ${jid} 不存在或已过期(reload 会清空暂存), 请重新 build_preview` };
  if (!rec.op) {
    if (rec.total && rec.parts.size !== rec.total) {
      return { err: `上传不完整(${rec.parts.size}/${rec.total} 帧), 请重新 preview` };
    }
    try {
      rec.op = decodeBuild(rec.raw);
    } catch (e) {
      return { err: `payload 解析失败: ${e}` };
    }
  }
  return { rec };
}

function handleBuild(message) {
  const { id: rid0 } = takeId(String(message || "").replace(/^(\S+)\s+/, ""));
  try {
    handleBuildInner(message);
  } catch (e) {
    console.error(`${BUILD_TAG} 处理失败: ${e}`);
    emitPayload(BUILD_TAG, rid0, { ok: false, error: `行为包内部错误: ${e}` });
  }
}

function handleBuildInner(message) {
  const { action, rest } = splitAction(message);
  gcBuilds();
  if (action === "put") {
    const m = String(rest).match(/^(\S+)\s+(\d+)\/(\d+)\s+([\s\S]*)$/);
    if (!m) { console.error(`${BUILD_TAG} put 参数错误: ${String(rest).slice(0, 80)}`); return; }
    const jid = m[1];
    let rec = builds.get(jid);
    if (!rec) {
      if (builds.size >= BUILD_MAX_PENDING) {
        // 丢最旧的未提交操作
        let oldest = null, oldestAt = Infinity;
        for (const [k, v] of builds) if (v.created < oldestAt) { oldestAt = v.created; oldest = k; }
        if (oldest) builds.delete(oldest);
      }
      rec = { parts: new Map(), total: 0, raw: "", created: Date.now(), aborted: false, name: "" };
      builds.set(jid, rec);
    }
    rec.parts.set(Number(m[2]), m[4]);
    rec.total = Number(m[3]);
    rec.raw = "";
    for (let i = 1; i <= rec.total; i++) {
      const part = rec.parts.get(i);
      if (part === undefined) { rec.raw = ""; break; }
      rec.raw += part;
    }
    return;
  }
  if (action === "abort") {
    const rec = builds.get(String(rest).trim());
    if (rec) rec.aborted = true;
    return;
  }
  if (action === "drop") {
    builds.delete(String(rest).trim());
    return;
  }
  if (action === "list") {
    const { id } = takeId(rest);
    const ops = [];
    for (const [jid, rec] of builds) {
      ops.push({ jid, name: rec.name, created: rec.created, cells: rec.cells || 0,
                 bounds: rec.bounds || null, complete: !rec.total || rec.parts.size === rec.total,
                 committed: !!rec.committed });
    }
    emitPayload(BUILD_TAG, id, { ok: true, ops, undo: undoStack.map((u) => ({ jid: u.jid, name: u.name })) });
    return;
  }
  // preview / commit / undo 都带请求 id
  const { id, rest: rest2 } = takeId(rest);
  const jid = (id ? rest2 : rest).trim();
  if (!jid) {
    emitPayload(BUILD_TAG, id, { ok: false, error: "缺少操作 id" });
    return;
  }
  if (action === "undo") {
    let idx = -1;
    if (jid && jid !== "-") idx = undoStack.findIndex((u) => u.jid === jid);
    if (idx < 0) idx = undoStack.length - 1;
    if (idx < 0) {
      emitPayload(BUILD_TAG, id, { ok: false, error: "没有可撤销的操作" });
      return;
    }
    const entry = undoStack.splice(idx, 1)[0];
    const dim = resolveDimension("overworld");
    runJob(executeJob(id, entry.jid, entry.op, dim, null, { undoOf: entry.jid }));
    return;
  }
  const got = getBuildOp(jid);
  if (got.err) {
    emitPayload(BUILD_TAG, id, { ok: false, error: got.err });
    return;
  }
  const rec = got.rec;
  const dim = resolveDimension(rec.op.dim || "overworld");
  if (action === "preview") {
    rec.name = rec.name || "";
    runJob(previewJob(id, jid, rec.op, dim));
    return;
  }
  if (action === "commit") {
    const before = snapshotBefore(rec.op, dim);
    rec.committed = true;
    runJob(executeJob(id, jid, rec.op, dim, before, {}));
    return;
  }
  emitPayload(BUILD_TAG, id, { ok: false, error: `未知动作 ${action}` });
}

// 导出全部物品/方块 ID: `scriptevent viktor:ids`(控制台触发, 供离线重建 data/items.json)。
// 分块输出, 避免单行过长被切断。升级服务器版本后可重跑一次刷新 ID 清单。
function dumpIds() {
  const CHUNK = 100;
  const emit = (tag, ids) => {
    ids.sort();
    for (let i = 0; i < ids.length; i += CHUNK) {
      console.log(`${IDS_TAG} ${tag} ${ids.slice(i, i + CHUNK).join(",")}`);
    }
  };
  try {
    emit("ITEMS", ItemTypes.getAll().map((t) => String(t.id)));
  } catch (e) {
    console.log(`${IDS_TAG} ERROR items: ${e}`);
  }
  try {
    emit("BLOCKS", BlockTypes.getAll().map((t) => String(t.id)));
  } catch (e) {
    console.log(`${IDS_TAG} ERROR blocks: ${e}`);
  }
  console.log(`${IDS_TAG} DONE`);
}

// 可点击菜单(server-ui 表单): `scriptevent viktor:menu ...`
// 基岩版 tellraw 不支持 clickEvent, 所以“点一下传送/做按钮菜单”只能靠表单。
// 协议(逐条下发, 避免单条命令超长):
//   viktor:menu new <玩家> <标题...>        开始一个新菜单
//   viktor:menu add <玩家> <按钮文字>|<命令>  追加一个按钮(命令可带或不带前导 /)
//   viktor:menu show <玩家>                  弹出表单; 按钮点击后以该玩家身份执行命令
const pendingMenus = new Map();  // 玩家名 -> { title, buttons: [{label, command}] }

function playerByName(name) {
  for (const p of getPlayers()) if (p.name === name) return p;
  return undefined;
}

function showMenu(player, title, buttons) {
  const form = new ActionFormData();
  form.title(title || "菜单");
  for (const b of buttons) form.button(b.label);
  const onResult = (resp) => {
    if (!resp || resp.canceled) {
      console.log(`${MENU_TAG} ${player.name} 关闭了菜单`);
      return;
    }
    const b = buttons[resp.selection];
    if (!b) return;
    console.log(`${MENU_TAG} ${player.name} 选择: ${b.label}`);
    try {
      player.runCommand(String(b.command).replace(/^\//, ""));
    } catch (e) {
      console.error(`${MENU_TAG} ${player.name} 执行 [${b.command}] 失败: ${e}`);
    }
  };
  const attempt = (tries) => {
    form.show(player).then(onResult).catch((e) => {
      // 玩家正好开着别的界面时会 UserBusy, 稍后重试几次
      if (String(e).includes("UserBusy") && tries < 20) {
        system.runTimeout(() => attempt(tries + 1), 10);
      } else {
        console.error(`${MENU_TAG} 向 ${player.name} 显示菜单失败: ${e}`);
      }
    });
  };
  attempt(0);
}

function handleMenu(message) {
  const s = String(message || "").trim();
  const m = s.match(/^(\S+)\s+(\S+)(?:\s+([\s\S]*))?$/);
  if (!m) {
    console.error(`${MENU_TAG} 参数不足: ${s}`);
    return;
  }
  const action = m[1].toLowerCase();
  const playerName = m[2];
  const rest = m[3] || "";
  if (action === "new") {
    pendingMenus.set(playerName, { title: rest, buttons: [] });
    return;
  }
  if (action === "add") {
    const menu = pendingMenus.get(playerName);
    if (!menu) {
      console.error(`${MENU_TAG} ${playerName} 未先 new 菜单`);
      return;
    }
    const i = rest.indexOf("|");
    if (i <= 0) {
      console.error(`${MENU_TAG} add 缺少 标签|命令: ${rest}`);
      return;
    }
    menu.buttons.push({ label: rest.slice(0, i), command: rest.slice(i + 1) });
    return;
  }
  if (action === "show") {
    const menu = pendingMenus.get(playerName) || { title: "", buttons: [] };
    pendingMenus.delete(playerName);
    const player = playerByName(playerName);
    if (!menu.buttons.length) {
      console.error(`${MENU_TAG} ${playerName} 的菜单没有按钮`);
      return;
    }
    if (!player) {
      console.error(`${MENU_TAG} 玩家 ${playerName} 不在线, 菜单作废`);
      return;
    }
    showMenu(player, menu.title, menu.buttons);
    return;
  }
  console.error(`${MENU_TAG} 未知动作: ${action}`);
}

system.afterEvents.scriptEventReceive.subscribe((ev) => {
  if (ev.id === "viktor:hello") console.log(`${HELLO_TAG} ${String(ev.message || "").trim()} ${PROTOCOL}`);
  else if (ev.id === "viktor:pos") reportPositions(ev.message);
  else if (ev.id === "viktor:inv") reportInventory(ev.message);
  else if (ev.id === "viktor:block") reportBlock(ev.message);
  else if (ev.id === "viktor:heightmap") heightmap(ev.message);
  else if (ev.id === "viktor:slice") sliceBlocks(ev.message);
  else if (ev.id === "viktor:inspect") inspectRegion(ev.message);
  else if (ev.id === "viktor:find") findBlocks(ev.message);
  else if (ev.id === "viktor:caps") reportCaps(ev.message);
  else if (ev.id === "viktor:build") handleBuild(ev.message);
  else if (ev.id === "viktor:menu") handleMenu(ev.message);
  else if (ev.id === "viktor:ids") dumpIds();
}, { namespaces: ["viktor"] });

system.runTimeout(() => {
  console.log(`${CHAT_TAG} bridge loaded, protocol ${PROTOCOL}, chatSend subscribed = ${subscribed}`);
}, 20);
