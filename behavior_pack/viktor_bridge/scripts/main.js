// Viktor Bridge: 把聊天、玩家坐标、物品栏桥接给外部 bot。
// BDS 控制台不回显玩家聊天, 这里用 console.log 输出到控制台/日志。
//
// 协议 v2: bot 在事件参数最前面带一个请求 id `r<数字>`, 本脚本把该 id 原样回显到
// 每一行输出里, 于是 bot 可以一次下发整批请求、再按 id 认领各自回包 (见 [VIKTOR-*] 行)。
// 旧格式 (无 id) 依旧兼容: takeId 只在首 token 形如 r123 时才认作 id。
import { world, system, ItemTypes, BlockTypes } from "@minecraft/server";
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
// v3: 新增 heightmap/slice/inspect/find/caps; 查询回包改为「一个 JSON payload 分多帧」
const PROTOCOL = "v3";
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
  else if (ev.id === "viktor:menu") handleMenu(ev.message);
  else if (ev.id === "viktor:ids") dumpIds();
}, { namespaces: ["viktor"] });

system.runTimeout(() => {
  console.log(`${CHAT_TAG} bridge loaded, protocol ${PROTOCOL}, chatSend subscribed = ${subscribed}`);
}, 20);
