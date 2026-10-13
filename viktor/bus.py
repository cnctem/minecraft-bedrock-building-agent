"""ServerBus: 服务端请求总线(协议 v2)。同批 id 化请求一次下发, 回包按 id 路由。

依赖方向: bus → constants(BUS_ROUTE_RE); 不 import bot_*。
"""
import threading
import time
from pathlib import Path

from .constants import BUS_ROUTE_RE


class BusArgError(ValueError):
    """bus 工具参数校验失败: 消息直接作为给模型的错误文本。"""


class Req:
    """一次服务端查询请求: 命令、回包缓存与完成事件。"""

    __slots__ = ("id", "kind", "cmd", "args", "timeout", "lines", "done", "event", "sent_at")

    def __init__(self, rid, kind, cmd, timeout, args):
        self.id = rid
        self.kind = kind
        self.cmd = cmd
        self.args = args
        self.timeout = timeout
        self.lines = []
        self.done = False
        self.event = threading.Event()
        self.sent_at = 0.0


def _bus_terminal(kind: str, body: str) -> bool:
    # block 单行即终止; 其余靠脚本的 DONE 收尾
    if kind == "block":
        return True
    return body.startswith("DONE")


class ServerBus:
    """服务端请求总线: 同一批 id 化请求一次下发, 回包按 id 路由。

    背景: bedrock_server 每 ~0.8-1.0s 才把 stdin 积压行整批读走, 逐个下发要逐个等;
    一批一起下发只付一次轮询延迟。回包靠 [VIKTOR-*] r<id> 前缀路由(见行为包协议 v2)。
    """

    def __init__(self, bridge, log_path: Path, reader_poll: float = 0.05):
        self.bridge = bridge
        self.log_path = Path(log_path)
        self.reader_poll = reader_poll
        self._lock = threading.Lock()
        self._inflight: dict[str, Req] = {}
        self._offset = 0
        self._counter = 0
        self._running = False
        self._reader_thread: threading.Thread | None = None

    def start(self):
        if self._running:
            return
        self._running = True
        try:
            self._offset = self.log_path.stat().st_size
        except FileNotFoundError:
            self._offset = 0
        self._reader_thread = threading.Thread(target=self._reader, daemon=True)
        self._reader_thread.start()

    def stop(self):
        self._running = False
        with self._lock:
            reqs = list(self._inflight.values())
        for r in reqs:
            r.event.set()

    def next_id(self) -> str:
        with self._lock:
            self._counter += 1
            return f"r{self._counter}"

    def submit_many(self, specs) -> list[Req]:
        """specs: [(rid, kind, cmd, timeout, args)]; 登记后一次下发, 返回等长 Req。
        命令由调用方预先构造(这样参数校验失败就不会占用 id/下发)。"""
        if not specs:
            return []
        self.start()
        reqs = [Req(rid, kind, cmd, timeout, args)
                for rid, kind, cmd, timeout, args in specs]
        with self._lock:
            for r in reqs:
                self._inflight[r.id] = r
        try:
            self.bridge.send_commands([r.cmd for r in reqs])
        except Exception:
            with self._lock:
                for r in reqs:
                    self._inflight.pop(r.id, None)
            raise
        now = time.time()
        for r in reqs:
            r.sent_at = now
        return reqs

    def wait(self, req: Req, abort: threading.Event) -> bool:
        deadline = req.sent_at + req.timeout
        while not req.done:
            if abort.is_set():
                self._drop(req.id)
                return False
            if time.time() >= deadline:
                self._drop(req.id)
                return False
            req.event.wait(0.1)
        return True

    def _drop(self, rid: str):
        with self._lock:
            self._inflight.pop(rid, None)

    def _route(self, line: str):
        m = BUS_ROUTE_RE.search(line)
        if not m:
            return
        kind, rid = m.group(1).lower(), m.group(2)
        body = (m.group(3) or "").strip()
        with self._lock:
            req = self._inflight.get(rid)
        if req is None or req.done:
            return
        req.lines.append(body)
        if _bus_terminal(kind, body):
            req.done = True
            req.event.set()
            self._drop(rid)

    def _reader(self):
        while self._running:
            try:
                if not self.log_path.exists():
                    time.sleep(self.reader_poll)
                    continue
                size = self.log_path.stat().st_size
                if size < self._offset:
                    self._offset = 0  # 日志被截断/轮转
                with open(self.log_path, "rb") as f:
                    f.seek(self._offset)
                    data = f.read()
                if data:
                    nl = data.rfind(b"\n")
                    if nl >= 0:  # 只吃完整行, 半行留到下次
                        self._offset += nl + 1
                        for line in data[:nl + 1].decode("utf-8", "replace").splitlines():
                            self._route(line)
            except FileNotFoundError:
                pass
            except Exception:
                pass
            time.sleep(self.reader_poll)

