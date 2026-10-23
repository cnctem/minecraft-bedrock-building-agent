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
const SCAN_TAG = "[VIKTOR-SCAN]";
const IDS_TAG = "[VIKTOR-IDS]";  // 导出全部物品/方块 ID, 供离线生成速查表
const HELLO_TAG = "[VIKTOR-HELLO]";  // 协议握手: bot 据此判断行为包是否支持 v2
const MENU_TAG = "[VIKTOR-MENU]";    // 可点击菜单(server-ui 表单)回执
const PROTOCOL = "v2";
const MAX_CELLS = 300;  // 单层切面总格数程序上限(与 bot 端一致; 提示词向模型声明 256)
const SCAN_YIELD_EVERY = 16;  // 每次让出主线程前扫描的格数(非阻塞扫描)
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

// 切面批量扫描: `scriptevent viktor:scan [id] <x1> <y1> <z1> <x2> <y2> <z2> [维度] [过滤]`
// 1 格厚矩形切面(单层总格数 ≤300, 可拉 1×1×256 这样的长条), 默认只报非空气方块;
// 给了过滤关键字则只报 typeId 含该关键字的方块。
// 逐行 `[VIKTOR-SCAN] [id] x y z 维度 方块ID [状态]`; 末行 `[VIKTOR-SCAN] [id] DONE ...`。
// 扫描体量可能不小, 用 system.runJob + 周期性 yield 让出主线程, 避免世界卡顿。
function resolveDimension(arg) {
  const d = String(arg || "overworld").toLowerCase();
  if (d === "nether" || d === "minecraft:nether") return world.getDimension("nether");
  if (d === "the_end" || d === "end" || d === "minecraft:the_end") return world.getDimension("the_end");
  return world.getDimension("overworld");
}

function* scanJob(tag, dimension, xs, ys, zs, filter) {
  let total = 0, matched = 0, unloaded = 0, n = 0;
  const others = {};  // 非匹配方块类型计数
  for (let x = xs[0]; x <= xs[1]; x++) {
    for (let y = ys[0]; y <= ys[1]; y++) {
      for (let z = zs[0]; z <= zs[1]; z++) {
        total++;
        let block;
        try { block = dimension.getBlock({ x, y, z }); } catch (e) { block = undefined; }
        if (!block) {
          unloaded++;
        } else {
          const bid = String(block.typeId || "").replace(/^minecraft:/, "");
          const ok = filter ? bid.toLowerCase().includes(filter) : bid !== "air";
          if (!ok) {
            others[bid] = (others[bid] || 0) + 1;
          } else {
            matched++;
            let states = "";
            try {
              const st = block.permutation.getAllStates();
              if (st && Object.keys(st).length) states = " " + JSON.stringify(st);
            } catch (e) { /* 部分方块无状态 */ }
            console.log(`${tag} ${x} ${y} ${z} ${dimension.id} ${block.typeId}${states}`);
          }
        }
        if ((++n % SCAN_YIELD_EVERY) === 0) yield;  // 让出主线程, 别卡世界
      }
    }
  }
  const otherStr = Object.entries(others).sort((a, b) => b[1] - a[1]).slice(0, 6)
    .map(([k, v]) => `${k}=${v}`).join(",");
  console.log(`${tag} DONE total=${total} matched=${matched} `
    + `unloaded=${unloaded} other=${otherStr}`);
}

function scanBlocks(message) {
  const { id, rest } = takeId(message);
  const tag = tagOf(SCAN_TAG, id);
  const parts = String(rest || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length < 6) {
    console.log(`${tag} DONE error=参数不足需要6个坐标`);
    return;
  }
  const n = parts.slice(0, 6).map((s) => Math.floor(Number(s)));
  if (!n.every(Number.isFinite)) {
    console.log(`${tag} DONE error=坐标不是数字`);
    return;
  }
  const dimension = resolveDimension(parts[6]);
  const filter = String(parts[7] || "").toLowerCase().replace(/^minecraft:/, "");
  const xs = [n[0], n[3]].sort((a, b) => a - b);
  const ys = [n[1], n[4]].sort((a, b) => a - b);
  const zs = [n[2], n[5]].sort((a, b) => a - b);
  const ex = xs[1] - xs[0] + 1, ey = ys[1] - ys[0] + 1, ez = zs[1] - zs[0] + 1;
  const ext = [ex, ey, ez].sort((a, b) => a - b);
  const cells = ex * ey * ez;
  if (ext[0] !== 1 || cells > MAX_CELLS) {
    console.log(`${tag} DONE error=不是1格厚切面或超过${MAX_CELLS}格: ${ex}x${ey}x${ez}`);
    return;
  }
  const job = scanJob(tag, dimension, xs, ys, zs, filter);
  if (typeof system.runJob === "function") {
    system.runJob(job);
  } else {
    // 兜底(旧引擎没有 runJob): 同步跑完, 至少功能不缺
    let r = job.next();
    while (!r.done) r = job.next();
  }
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
  else if (ev.id === "viktor:scan") scanBlocks(ev.message);
  else if (ev.id === "viktor:menu") handleMenu(ev.message);
  else if (ev.id === "viktor:ids") dumpIds();
}, { namespaces: ["viktor"] });

system.runTimeout(() => {
  console.log(`${CHAT_TAG} bridge loaded, protocol ${PROTOCOL}, chatSend subscribed = ${subscribed}`);
}, 20);
