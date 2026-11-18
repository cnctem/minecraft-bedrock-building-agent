"""ScreenBridge: 经 screen 向服务器控制台注入命令, 并把回复 tellraw 到游戏内。

依赖方向: bridge → paths(log); 不 import bot_* / session / bus。
"""
import json
import re
import subprocess
import time

from .paths import log


class ScreenBridge:
    """通过 screen 与服务器控制台交互。"""

    def __init__(self, session: str, agent_name: str = "agent"):
        self.session = session
        self.agent_name = agent_name

    def send_command(self, cmd: str):
        # screen 的 stuff 会解释反斜杠转义, 先把字面反斜杠转义掉, 末尾 \r 表示回车
        safe = cmd.replace("\\", "\\\\")
        subprocess.run(
            ["screen", "-S", self.session, "-p", "0", "-X", "stuff", safe + "\\r"],
            check=False,
        )

    def send_commands(self, cmds):
        """一次 stuff 注入多条控制台命令(多条以回车分行), 整批只付一次 stdin 轮询延迟。"""
        cmds = [c for c in cmds if c]
        if not cmds:
            return
        payload = "\\r".join(c.replace("\\", "\\\\") for c in cmds) + "\\r"
        subprocess.run(
            ["screen", "-S", self.session, "-p", "0", "-X", "stuff", payload],
            check=False,
        )

    def sync_player_count(self) -> None:
        self.send_command("list")

    def say_as_agent(self, text: str, max_len: int, max_chunks: int, system: bool = False):
        # 系统回执使用独立标签，模型发言使用配置的名称。
        text = self._clean_chat(text)
        prefix = "§7[系统]§f " if system else f"§e<{self.agent_name}>§f "
        # 日志标签与游戏内前缀保持一致: 系统消息记 [系统], 而不是笼统混作 [发言]
        self._emit(text, max_len, max_chunks, prefix, "系统" if system else "发言")

    def say_side(self, label: str, text: str, max_len: int, max_chunks: int):
        """旁路转发(正文/工具): 只发到聊天供玩家观察 Agent 状态, 不进上下文。"""
        self._emit(self._clean_chat(text), max_len, max_chunks, f"§7{label}§f ",
                   label.strip("[]") or "转发")

    @staticmethod
    def _clean_chat(text: str) -> str:
        # 去掉换行与控制字符, 防止一条回复里夹带命令
        text = re.sub(r"[\r\n\x00-\x1f]", " ", text).strip()
        # 上下文格式是 [时间] 名字: 内容, 模型有时会照样模仿, 剥掉这类前缀
        while True:
            stripped = re.sub(r"^\[\d{1,2}:\d{2}(:\d{2})?\]\s*[^\s:：]{1,20}[:：]\s*", "", text)
            if stripped == text:
                break
            text = stripped
        return text

    def _emit(self, text: str, max_len: int, max_chunks: int, prefix: str, tag: str):
        if not text:
            return
        chunks = []
        while text and len(chunks) < max_chunks:
            chunks.append(text[:max_len])
            text = text[max_len:]
        for chunk in chunks:
            payload = json.dumps(f"{prefix}{chunk}", ensure_ascii=False)
            self.send_command(f'tellraw @a {{"rawtext":[{{"text":{payload}}}]}}')
            log(f"[{tag}] {chunk}")  # 记下真实发言, 便于事后排查
            time.sleep(0.4)
