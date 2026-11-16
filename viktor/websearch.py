"""联网搜索与网页抓取: 走 DeepSeek 自己的 Search & Fetch 接口。

DeepSeek 的接口原生提供两条路(见 api-docs.deepseek.com/guides/web_tools 与 guides/search):
- **服务端工具** `deepseek_web_search` / `deepseek_read_url`: 声明在请求的 tools 里, 由模型自己
  决定何时联网, 搜索、开页、抓取全在服务端完成, 客户端不执行任何工具(还会回引用 citations)。
  默认模型(DeepSeek)走这条, 见 bot_agent._build_payload。
- **独立 REST 接口** `POST /v1/tools/search` 与 `POST /v1/tools/fetch`: 由代码直接调用。

本模块只负责第二条: 切到没有原生联网工具的模型(kimi 等)时, 同名工具退化成这里的调用,
联网能力仍由 DeepSeek 提供(鉴权用 DeepSeek 的 key)。所以这里**不自己抓网页、不解析 HTML、
不做 SSRF 防护**——那些都在 DeepSeek 服务端, 这边只是一个薄客户端。

依赖方向: 叶子模块, 只 import 标准库; 不 import 任何项目内模块。
"""
import base64
import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE = "https://api.deepseek.com"   # 与顶层 api_base 同源; 显式配置可覆盖
DEFAULT_TIMEOUT = 30.0
DEFAULT_COUNT = 8
MAX_COUNT = 20
DEFAULT_MAX_CHARS = 12000       # 单次结果返回给模型的字符上限(搜索列表 / 网页正文)
SUMMARY_CHARS = 800             # 每条搜索结果的摘要上限(接口本身约 600~800 字)
MAX_QUERY_CHARS = 128           # 接口限制: query / ori_question 都是 1~128 字
USER_AGENT = "viktor-mc-bot/0.1 (personal Minecraft Bedrock server bot)"

# 图片直链: DeepSeek 的原生视觉由**服务端**下载图片, 客户端拿不到字节; Kimi 这类只认
# data: URL 的模型只能由本地取一次字节转 base64(见 bot_core._commit_to_context)。
# 所以这里保留一个**只管图片**的最小下载器: 不解析网页、不跟非图片跳转, 并保留 SSRF 闸
# (玩家能在聊天里贴任意地址, 这道闸必须有)。
IMAGE_TIMEOUT = 15.0
IMAGE_MAX_BYTES = 4 * 1024 * 1024   # 超过就放弃(再大 base64 会把请求体撑爆)


class SearchError(RuntimeError):
    """网络/鉴权/额度/抓取失败等一切可控失败(消息直接回给模型)。"""


# ---------- 地址 ----------

# 直接图片地址的常见后缀(DeepSeek vision 支持 JPEG/PNG/GIF/WebP)
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")
_RE_URL = re.compile(r"https?://[^\s<>\"'，。、；：！？）】」』]+", re.I)


def image_urls(text: str, limit: int = 2) -> list[str]:
    """从聊天文本里挑出「直接图片地址」(以 .png/.jpg/.jpeg/.gif/.webp 结尾)。

    玩家发来的图片不靠工具取: 这些地址直接作为 image_url 内容块附进那条用户消息,
    由模型服务端自己下载(见 bot_core._commit_to_context)。只认后缀能看出来的直链 ——
    普通网页地址交给 deepseek_read_url / 联网搜索, 不在这里猜。
    返回去重后的地址(最多 limit 条)。"""
    out: list[str] = []
    for m in _RE_URL.finditer(text or ""):
        url = normalize_url(m.group(0))
        if urllib.parse.urlsplit(url).path.lower().endswith(IMAGE_EXTENSIONS) and url not in out:
            out.append(url)
            if len(out) >= max(1, limit):
                break
    return out


def normalize_url(raw: str) -> str:
    """整理模型/玩家给的地址: 去引号与聊天里的尾部标点, 裸域名补 https://。"""
    url = (raw or "").strip().strip("<>\"'")
    url = url.rstrip("。，、；：！？）》」』】”’")
    if url and not re.match(r"^[a-zA-Z][\w+.-]*://", url):
        if re.match(r"^[\w-]+(\.[\w-]+)+(:\d+)?(/|$|\?)", url):
            url = "https://" + url
    return url


# ---------- 图片直链(取字节) ----------

def _ip_is_public(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip.split("%", 1)[0])
    except ValueError:
        return False
    return not (addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_reserved or addr.is_multicast or addr.is_unspecified)


def _check_image_url(url: str, allow_private: bool) -> None:
    """只放行 http/https 的公网地址(解析后逐个 IP 检查, 防内网/回环/元数据服务)。"""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise SearchError("只支持 http/https 图片地址")
    host = parts.hostname
    if not host:
        raise SearchError("图片地址缺少主机名")
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        raise SearchError("图片地址端口不合法") from None
    if allow_private:
        return
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise SearchError(f"图片域名解析失败({e})") from None
    bad = [info[4][0] for info in infos if not _ip_is_public(info[4][0])]
    if bad:
        raise SearchError(f"拒绝访问内网/保留地址({host} → {bad[0]})")


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """每次跳转都重新做地址校验(否则公网图片 302 到 127.0.0.1 就绕过了)。"""

    def __init__(self, allow_private: bool):
        self.allow_private = allow_private

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_image_url(newurl, self.allow_private)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def sniff_image_mime(data: bytes) -> str:
    """按文件头认图片格式(不信任 Content-Type / 文件名)。认不出返回空串。"""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return ""


def fetch_image(url: str, *, timeout: float | None = None, max_bytes: int | None = None,
                allow_private: bool = False) -> tuple[str, str]:
    """下载一张图片, 返回 (mime, base64)。可控失败抛 SearchError。

    只给**不支持远程图片地址**的模型用(DeepSeek 走服务端原生下载, 这里不会被调用)。"""
    url = normalize_url(url)
    if not url:
        raise SearchError("没有图片地址")
    _check_image_url(url, allow_private)
    timeout = float(timeout or IMAGE_TIMEOUT)
    max_bytes = int(max_bytes or IMAGE_MAX_BYTES)
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "image/png,image/jpeg,image/gif,image/webp,*/*;q=0.5",
    })
    opener = urllib.request.build_opener(_SafeRedirect(allow_private))
    try:
        with opener.open(req, timeout=timeout) as resp:
            data = resp.read(max_bytes + 1)
    except urllib.error.HTTPError as e:
        raise SearchError(f"图片返回 HTTP {e.code}") from None
    except urllib.error.URLError as e:
        raise SearchError(f"连接失败({getattr(e, 'reason', e)})") from None
    except (TimeoutError, OSError) as e:
        raise SearchError(f"下载超时或中断({e})") from None
    if len(data) > max_bytes:
        raise SearchError(f"图片超过 {max_bytes} 字节上限")
    mime = sniff_image_mime(data)
    if not mime:
        raise SearchError("目标不是有效图片(png/jpeg/gif/webp)")
    return mime, base64.b64encode(data).decode("ascii")


# ---------- HTTP ----------

def _endpoint(cfg: dict, path: str) -> str:
    base = str(cfg.get("web_search_api_base") or cfg.get("api_base") or DEFAULT_BASE)
    return base.rstrip("/") + path


def _api_key(cfg: dict) -> str:
    key = str(cfg.get("web_search_api_key") or cfg.get("api_key") or "")
    if not key:
        raise SearchError("没有可用的 DeepSeek API key(联网能力由 DeepSeek 提供, 需在配置里填 key)")
    return key


def _error_message(code: int, body: str) -> str:
    """把 HTTP 错误整理成一句人能读的话: 接口的 error.message 优先, 再补上处置建议。"""
    detail = ""
    try:
        data = json.loads(body)
        err = data.get("error") if isinstance(data, dict) else None
        if isinstance(err, dict):
            detail = str(err.get("message") or err.get("code") or "")
        elif isinstance(err, str):
            detail = err
    except (TypeError, ValueError):
        detail = re.sub(r"\s+", " ", (body or "").strip())
    detail = re.sub(r"\s+", " ", detail)[:200]
    hint = {
        400: "请求参数不合法",
        401: "API key 无效",
        402: "账户余额不足",
        403: "抓取被安全策略拒绝",
        404: "抓不到可用正文(地址不可访问/站点拒绝/内容类型不支持)",
        408: "读取请求超时",
        413: "请求体过大",
        429: "请求过于频繁(QPS 超限), 稍后再试",
        500: "DeepSeek 服务端错误",
        504: "下游请求超时",
    }.get(code, "")
    parts = [p for p in (hint, detail) if p]
    return f"HTTP {code} " + (" · ".join(parts) if parts else "")


def _post(cfg: dict, path: str, payload: dict, timeout: float | None = None) -> dict:
    """POST 一个 JSON 请求, 返回解析后的字典; 可控失败抛 SearchError。"""
    url = _endpoint(cfg, path)
    timeout = float(timeout or cfg.get("web_search_timeout_sec", DEFAULT_TIMEOUT))
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode(),
        method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {_api_key(cfg)}",
                 "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raise SearchError(_error_message(e.code, e.read().decode("utf-8", "replace"))) from None
    except urllib.error.URLError as e:
        raise SearchError(f"连接失败({getattr(e, 'reason', e)})") from None
    except (TimeoutError, OSError) as e:
        raise SearchError(f"请求超时或中断({e})") from None
    except ValueError as e:
        raise SearchError(f"返回了无法解析的内容({e})") from None


# ---------- 文本整理 ----------

def _one_line(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _limit_text(text: str, max_chars: int, note: str = "") -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars] + (note or f"\n…(内容过长, 已截断到 {max_chars} 字符)")


def format_results(query: str, results: list, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """把 /v1/tools/search 的 results 排成模型好读的列表(纯函数, 便于离线自测)。"""
    lines = [f"DeepSeek 联网搜索「{query}」: {len(results)} 条结果"]
    for i, r in enumerate(results, 1):
        if not isinstance(r, dict):
            continue
        title = _one_line(r.get("title")) or "(无标题)"
        url = _one_line(r.get("url"))
        meta = []
        if r.get("site_name"):
            meta.append(_one_line(r["site_name"]))
        if r.get("date"):
            meta.append(str(r["date"])[:10])
        score = r.get("rerank_score")
        if isinstance(score, (int, float)):
            meta.append(f"相关度 {score:.1f}")
        authority = r.get("authority")
        if isinstance(authority, int) and authority >= 0:
            meta.append(f"权威 {authority}")
        body = _one_line(r.get("summary")) or _one_line(r.get("snippet"))
        lines.append(f"[{i}] {title}")
        if meta:
            lines.append("    " + " · ".join(meta))
        if url:
            lines.append(f"    URL: {url}")
        if body:
            lines.append(f"    摘要: {_clip(body, SUMMARY_CHARS)}")
    return _limit_text("\n".join(lines), max_chars)


# ---------- 对外接口 ----------

def search(cfg: dict, query: str, count: int = DEFAULT_COUNT, ori_question: str = "",
           max_chars: int = DEFAULT_MAX_CHARS, timeout: float | None = None) -> str:
    """联网搜索, 返回给模型看的文本报告。失败也返回文本(以「错误:」开头), 不抛异常。"""
    query = _one_line(query)
    if not query:
        return "错误: query 不能为空。"
    query = query[:MAX_QUERY_CHARS]
    try:
        count = max(1, min(int(count or DEFAULT_COUNT), MAX_COUNT))
    except (TypeError, ValueError):
        count = DEFAULT_COUNT
    payload = {"query": query, "count": count}
    question = _one_line(ori_question)[:MAX_QUERY_CHARS]
    if question:
        payload["ori_question"] = question
    try:
        data = _post(cfg, "/v1/tools/search", payload, timeout)
    except SearchError as e:
        return f"错误: 联网搜索失败: {e}"
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list) or not results:
        return (f"联网搜索「{query}」没有结果。换个词(游戏内正式名称/英文), "
                "或用 site: 指定站点(如 site:minecraft.wiki)再试。")
    return format_results(query, results, max_chars)


def fetch(cfg: dict, url: str, max_chars: int = DEFAULT_MAX_CHARS,
          timeout: float | None = None) -> str:
    """抓一个网页, 返回标题 + Markdown 正文。失败也返回文本(以「错误:」开头)。"""
    url = normalize_url(url)
    if not url:
        return "错误: 需要网页地址。"
    if not re.match(r"^https?://", url, re.I):
        return "错误: 只支持 http/https 地址。"
    try:
        data = _post(cfg, "/v1/tools/fetch", {"url": url}, timeout)
    except SearchError as e:
        return f"错误: 读取 {url} 失败: {e}"
    data = data if isinstance(data, dict) else {}
    title = _one_line(data.get("title")) or "(无标题)"
    content = str(data.get("content") or "").strip()
    head = f"[URL] {url}\n[标题] {title}"
    if not content:
        return (head + "\n[内容] 没有可读正文(可能是图片、纯脚本页, 或站点拒绝抓取)。"
                "图片直链会由系统自动附进上下文; 读不到就如实告诉玩家。")
    return _limit_text(head + "\n[内容]\n" + content, max_chars,
                       f"\n…(正文过长, 已截断到 {max_chars} 字符)")
