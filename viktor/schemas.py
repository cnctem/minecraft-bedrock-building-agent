"""function calling 工具 schema(startup 时注册进 capabilities)。

依赖方向: 叶子模块, 不 import 任何项目内模块。
"""

SEND_CHAT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "send_chat_message",
        "description": "向游戏内聊天栏发送一条消息。想说话时调用; 不想说话就不要调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "消息内容, 简短, 纯文本"},
            },
            "required": ["text"],
        },
    },
}

GET_STATUS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_server_status",
        "description": "查询 MC 服务器进程状态: CPU/内存占用、运行时长、系统负载、当前在线玩家。",
        "parameters": {"type": "object", "properties": {}},
    },
}

GET_POSITION_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_player_position",
        "description": (
            "获取在线玩家的实时坐标(x y z 与维度)。"
            "返回的是整数方块坐标(对实体坐标向下取整), 与玩家屏幕左上角“Show Coordinates”"
            "显示的完全一致, 可直接使用, 不要四舍五入/取整/加 0.5。"
            "基岩版没有查坐标的指令, 这个能力通过行为包脚本实现, 只能查当前在线的玩家。"
            "可用于回答\"我在哪\"、把玩家传送回某处前先确认位置等。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "player": {"type": "string", "description": "玩家名; 不传则返回所有在线玩家"},
            },
        },
    },
}

GET_HAND_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_player_hand",
        "description": (
            "获取在线玩家当前手持的物品(物品ID与数量), 空手时会说明。"
            "用于回答\"我手上拿的是什么\"、查看别人手里拿着什么。只能查当前在线的玩家。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "player": {"type": "string", "description": "玩家名; 不传则返回所有在线玩家"},
            },
        },
    },
}

GET_BLOCK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_block",
        "description": (
            "读取指定坐标上的方块类型(附带方块状态如朝向/半砖)。"
            "基岩版没有 /data get block(那是 Java 版), 必须用这个工具查方块。"
            "只能查已加载的区块——坐标需在在线玩家附近或常加载区, 否则会报“区块未加载”。"
            "注意: 玩家的 location.y 是脚底高度, “脚下的方块”是 y-1。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X 坐标"},
                "y": {"type": "integer", "description": "Y 坐标(高度)"},
                "z": {"type": "integer", "description": "Z 坐标"},
                "dimension": {
                    "type": "string",
                    "description": "维度: overworld(默认)/nether/the_end",
                },
            },
            "required": ["x", "y", "z"],
        },
    },
}

SCAN_BLOCKS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "scan_blocks",
        "description": (
            "批量读取一个 1 格厚的矩形切面(平面)上每个方块的类型, 一次扫一整片, 比逐个 get_block 快得多。"
            "切面须为 16×16×1 以内: 厚度为 1 的那个轴可以是 X、Y 或 Z。坐标给对角两点(x1y1z1 与 x2y2z2), 顺序不限。"
            "默认只返回非空气方块; 给 filter 则只返回类型含该关键字的方块, 并附上未匹配方块的类型统计——"
            "例如填完草方块后用 filter=grass 扫描, 若 other 里出现 air 就说明有没填满的格子。"
            "只能读已加载的区块(在线玩家附近或常加载区), 未加载的格子计入 unloaded。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "x1": {"type": "integer", "description": "对角点 1 的 X"},
                "y1": {"type": "integer", "description": "对角点 1 的 Y"},
                "z1": {"type": "integer", "description": "对角点 1 的 Z"},
                "x2": {"type": "integer", "description": "对角点 2 的 X"},
                "y2": {"type": "integer", "description": "对角点 2 的 Y"},
                "z2": {"type": "integer", "description": "对角点 2 的 Z"},
                "dimension": {"type": "string",
                              "description": "维度: overworld(默认)/nether/the_end"},
                "filter": {
                    "type": "string",
                    "description": (
                        "只返回类型包含该关键字的方块(如 grass 匹配 grass_block; air 专门找空洞)。"
                        "省略则返回所有非空气方块。"
                    ),
                },
            },
            "required": ["x1", "y1", "z1", "x2", "y2", "z2"],
        },
    },
}

BACKUP_SCHEMA = {
    "type": "function",
    "function": {
        "name": "backup_world",
        "description": (
            "把当前世界存档打包成一个 .7z 备份文件, 返回文件路径与大小。"
            "仅在玩家明确要求备份存档时调用。备份会把世界短暂写盘并压缩一遍, "
            "期间服务器会停顿几十秒, 玩家会感到卡顿, 所以不要与其它改世界的指令同时做。"
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}

SET_MODE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "set_mode",
        "description": (
            "在当前模式允许的目标之间切换运行模式。可选目标由程序按当前模式注入 mode.enum, "
            "未列出的模式不可切换、也不可知。不同模式的思考强度/输出上限/工具轮次/工具白名单不同; "
            "切到创造模式后工作方式会以系统注记给出。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": [],   # 运行时由 tool_schemas 按当前模式填充
                    "description": "目标模式",
                },
                "reason": {"type": "string", "description": "一句话说明为什么切换"},
            },
            "required": ["mode"],
        },
    },
}

RUN_COMMAND_SCHEMA = {
    "type": "function",
    "function": {
        "name": "run_server_command",
        "description": (
            "以服务器控制台身份执行一条 Minecraft 指令(不带斜杠, 基岩版语法), "
            "如 \"tp 玩家名 x y z\"、\"fill x1 y1 z1 x2 y2 z2 stone\"、\"locate structure village\"、\"list\"、\"time query daytime\"。"
            "注意: 这是基岩版, 没有 /data 等 Java 版指令; 指令输出会返回给你。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "指令内容, 不带开头的 /"},
            },
            "required": ["command"],
        },
    },
}

PIN_REGION_SCHEMA = {
    "type": "function",
    "function": {
        "name": "pin_region",
        "description": (
            "把一片矩形区域设为常加载(ticking area), 防止玩家离开或不在线时区块卸载, "
            "导致 fill/setblock/clone 报 0 blocks filled、scan_blocks/get_block 报区块未加载。"
            "施工范围可能超出在线玩家附近(模拟距离只有 4 区块)时, 开工前先调用它覆盖整个施工面。"
            "只需给 x/z 范围: 高度整列加载, 不用管 y。仅限主世界。"
            "仅在创造/执行模式下可用; 生命周期跟随创造/执行模式: 离开这些模式或会话结束时自动移除; "
            "同一回合重复调用会移动区域(先删旧的再设新的)。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "x1": {"type": "integer", "description": "矩形一角 x"},
                "z1": {"type": "integer", "description": "矩形一角 z"},
                "x2": {"type": "integer", "description": "对角 x"},
                "z2": {"type": "integer", "description": "对角 z"},
            },
            "required": ["x1", "z1", "x2", "z2"],
        },
    },
}
