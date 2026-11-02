"""读取玩家发来的 URL(网页 / 接口 / 图片), 让模型直接"看"外链内容。

给模型的结果分两部分:
- 文本报告: HTTP 状态(404/403/超时等)、类型、大小、网页标题与正文摘要 —— 永远返回;
- 图片: 解码成 base64 交给 capabilities.add_image(), bot_agent 把它作为 tool 消息的
  image_url 内容块回传(与 pi 的 ImageContent 同思路), 模型看到的是真图片, 不是描述。

安全: 只允许 http/https; DNS 解析后只连公网地址(防 SSRF 打内网/元数据服务);
限制跳转、体积与超时。玩家可以在聊天里贴任意地址, 这道闸必须有。

依赖方向: 叶子模块, 只 import 标准库; 不 import 项目内模块。
"""
import base64
import http.client
import html
import json
import re
import socket
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

DEFAULT_UA = "viktor-mc-bot/0.1 (personal Minecraft Bedrock server bot)"
DEFAULT_TIMEOUT = 20.0
DEFAULT_MAX_BYTES = 4 * 1024 * 1024
DEFAULT_MAX_CHARS = 1500
MAX_REDIRECTS = 5
MAX_PIXELS = 20_000_000          # 超过就不附给模型(有些 provider 会直接 400)
IMAGE_MIMES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


class FetchError(RuntimeError):
    """网络/地址/安全校验等一切可控失败(消息直接回给模型)。"""


# ---------- 地址 ----------

def normalize_url(raw: str) -> str:
    """整理模型/玩家给的地址: 去引号与聊天里的尾部标点, 裸域名补 https://。"""
    url = (raw or "").strip().strip("<>\"'")
    url = url.rstrip("。，、；：！？）》」』】”’")
    if url and not re.match(r"^[a-zA-Z][\w+.-]*://", url):
        if re.match(r"^[\w-]+(\.[\w-]+)+(:\d+)?(/|$|\?)", url):
            url = "https://" + url
    return url


def _ip_is_public(ip: str) -> bool:
    import ipaddress
    try:
        addr = ipaddress.ip_address(ip.split("%", 1)[0])
    except ValueError:
        return False
    return not (addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_reserved or addr.is_multicast or addr.is_unspecified)


def _check_url(url: str, allow_private: bool) -> None:
    """只放行 http/https 的公网地址(解析后逐个 IP 检查, 防止内网/回环)。"""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise FetchError("只支持 http/https 地址")
    host = parts.hostname
    if not host:
        raise FetchError("地址缺少主机名")
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        raise FetchError("端口不合法") from None
    if allow_private:
        return
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise FetchError(f"域名解析失败({e})") from None
    ips = {info[4][0] for info in infos}
    if not ips:
        raise FetchError("域名解析失败")
    bad = [ip for ip in ips if not _ip_is_public(ip)]
    if bad:
        raise FetchError(f"拒绝访问内网/保留地址({host} → {bad[0]})")


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """每次跳转都重新做地址校验(否则公网页面 302 到 127.0.0.1 就绕过了)。"""

    def __init__(self, allow_private: bool):
        self.allow_private = allow_private

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl, self.allow_private)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# ---------- HTTP ----------

def fetch(url: str, *, timeout: float = DEFAULT_TIMEOUT,
          max_bytes: int = DEFAULT_MAX_BYTES, allow_private: bool = False,
          user_agent: str = "") -> dict:
    """GET 一个地址, 返回 {url, final_url, status, reason, ctype, data, truncated, elapsed}。
    4xx/5xx 不抛异常: 状态码与响应体交给调用方报告(404 页面上的说明往往有用)。"""
    url = normalize_url(url)
    if not url:
        raise FetchError("没有给地址")
    _check_url(url, allow_private)
    req = urllib.request.Request(url, headers={
        "User-Agent": user_agent or DEFAULT_UA,
        "Accept": "image/*,text/html;q=0.9,application/json;q=0.9,text/plain;q=0.8,*/*;q=0.5",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    })
    opener = urllib.request.build_opener(_SafeRedirect(allow_private))
    started = time.time()
    try:
        resp = opener.open(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        resp = e
    except urllib.error.URLError as e:
        raise FetchError(f"连接失败({getattr(e, 'reason', e)})") from None
    except (TimeoutError, OSError, http.client.HTTPException, ValueError) as e:
        raise FetchError(f"连接超时或中断({e})") from None
    try:
        status = int(getattr(resp, "status", 0) or getattr(resp, "code", 0) or 0)
        reason = str(getattr(resp, "reason", "") or "")
        headers = resp.headers
        ctype = (headers.get("Content-Type", "") if headers else "") or ""
        data = resp.read(max_bytes + 1)
        truncated = len(data) > max_bytes
        data = data[:max_bytes]
        encoding = (headers.get("Content-Encoding", "") if headers else "") or ""
        final_url = resp.geturl() or url
    finally:
        try:
            resp.close()
        except Exception:
            pass
    if not truncated and encoding:
        data = _decompress(data, encoding, max_bytes)
    return {"url": url, "final_url": final_url, "status": status, "reason": reason,
            "ctype": ctype, "data": data, "truncated": truncated,
            "elapsed": time.time() - started}


def _decompress(data: bytes, encoding: str, limit: int) -> bytes:
    encoding = encoding.lower()
    try:
        if "gzip" in encoding:
            out = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(data, limit)
        elif "deflate" in encoding:
            out = zlib.decompressobj().decompress(data, limit)
        else:
            return data
    except zlib.error:
        return data
    return out


# ---------- 图片头解析(不解码像素: 模型自己看图, 这边只要尺寸/格式) ----------

def image_info(data: bytes) -> dict | None:
    """从文件头读图片格式与尺寸: {format, width, height, desc}。认不出返回 None。"""
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            w, h, bits, color, _cm, _fl, interlace = struct.unpack(">IIBBBBB", data[16:29])
            mode = {0: "灰度", 2: "RGB", 3: "索引色", 4: "灰度+透明", 6: "RGBA"}.get(color, "")
            desc = f"{bits}-bit {mode}".strip() + (" · 隔行" if interlace else "")
            return {"format": "PNG", "width": w, "height": h, "desc": desc}
        if data[:6] in (b"GIF87a", b"GIF89a"):
            w, h = struct.unpack("<HH", data[6:10])
            return {"format": "GIF", "width": w, "height": h, "desc": ""}
        if data[:3] == b"\xff\xd8\xff":
            i = 2
            while i + 9 < len(data):
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                    i += 2
                    continue
                if marker == 0xDA:  # 扫描数据, 后面不再有 SOF
                    break
                seg = struct.unpack(">H", data[i + 2:i + 4])[0]
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    h, w = struct.unpack(">HH", data[i + 5:i + 9])
                    progressive = " · 渐进式" if marker == 0xC2 else ""
                    return {"format": "JPEG", "width": w, "height": h,
                            "desc": f"{data[i + 9]} 通道{progressive}"}
                i += 2 + seg
            return {"format": "JPEG", "width": 0, "height": 0, "desc": ""}
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            chunk = data[12:16]
            if chunk == b"VP8 ":
                w, h = struct.unpack("<HH", data[26:30])
                return {"format": "WebP", "width": w & 0x3FFF, "height": h & 0x3FFF,
                        "desc": "有损"}
            if chunk == b"VP8L":
                b = int.from_bytes(data[21:25], "little")
                return {"format": "WebP", "width": (b & 0x3FFF) + 1,
                        "height": ((b >> 14) & 0x3FFF) + 1, "desc": "无损"}
            if chunk == b"VP8X":
                w = int.from_bytes(data[24:27], "little") + 1
                h = int.from_bytes(data[27:30], "little") + 1
                return {"format": "WebP", "width": w, "height": h, "desc": ""}
        if data[:2] == b"BM":
            w, h = struct.unpack("<ii", data[18:26])
            return {"format": "BMP", "width": abs(w), "height": abs(h), "desc": ""}
        if data[:4] == b"\x00\x00\x01\x00":
            w, h = data[6], data[7]
            return {"format": "ICO", "width": w or 256, "height": h or 256, "desc": ""}
    except (struct.error, IndexError, ValueError):
        pass
    return None


def _image_mime(data: bytes, ctype: str) -> str:
    ct = (ctype or "").split(";")[0].strip().lower()
    if ct in IMAGE_MIMES:
        return ct
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return ct


# ---------- 文本/网页 ----------

def _decode(data: bytes, ctype: str) -> str:
    m = re.search(r"charset=([\w.-]+)", ctype or "", re.I)
    for enc in ([m.group(1)] if m else []) + ["utf-8", "gb18030"]:
        try:
            return data.decode(enc, "replace")
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", "replace")


def _html_text(src: str) -> str:
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", src, re.S | re.I)
    if m:
        title = re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()
    body = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", src)
    body = re.sub(r"(?is)<!--.*?-->", " ", body)
    body = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", body)
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    body = re.sub(r"[ \t\r\f\v]+", " ", html.unescape(body))
    body = re.sub(r"\n\s*\n+", "\n", body).strip()
    return f"标题: {title}\n{body}" if title else body


def _preview(data: bytes, ctype: str, max_chars: int) -> str:
    """把响应体变成人/模型能读的文字: 网页给标题+正文, JSON 格式化, 其它给开头。"""
    ct = (ctype or "").lower()
    head = data[:400].lstrip().lower()
    if "html" in ct or head.startswith(b"<!doctype") or head.startswith(b"<html") \
            or b"<html" in head[:200] or b"<svg" in head[:200]:
        text = _html_text(_decode(data, ctype))
    elif "json" in ct or data[:1] in (b"{", b"["):
        try:
            text = json.dumps(json.loads(_decode(data, ctype)), ensure_ascii=False, indent=1)
        except (ValueError, UnicodeDecodeError):
            text = _decode(data, ctype)
    elif ct.startswith("text/") or not ct:
        text = _decode(data, ctype)
    else:
        return (f"[内容] 二进制文件({_size(len(data))}, 开头字节 {data[:8].hex(' ')}), "
                "不是图片也不是文本, 无法读取。")
    text = text.strip()
    if not text:
        return "[内容] 响应体为空。"
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n…(共 {len(text)} 字符, 已截断)"
    return "[内容]\n" + text


def _size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


# ---------- 对外入口 ----------

def read(raw_url: str, *, timeout: float = DEFAULT_TIMEOUT, max_bytes: int = DEFAULT_MAX_BYTES,
         max_chars: int = DEFAULT_MAX_CHARS, allow_private: bool = False,
         user_agent: str = "") -> tuple[str, tuple[str, str] | None]:
    """读取一个 URL, 返回 (给模型的文字报告, (图片mime, base64) 或 None)。
    任何可控失败都写进文字报告(以 [错误] 开头), 不抛异常。"""
    shown = normalize_url(raw_url) or "(空地址)"
    try:
        f = fetch(raw_url, timeout=timeout, max_bytes=max_bytes,
                  allow_private=allow_private, user_agent=user_agent)
    except FetchError as e:
        return f"[错误] 读取 {shown} 失败: {e}", None

    lines = [f"[URL] {f['url']}"]
    if f["final_url"] and f["final_url"] != f["url"]:
        lines.append(f"[跳转] 最终地址 {f['final_url']}")
    size = _size(len(f["data"]))
    lines.append(
        f"[HTTP] {f['status']}{(' ' + f['reason']) if f['reason'] else ''} · "
        f"{f['ctype'] or '未知类型'} · {size}"
        + (" (超过体积上限, 只读取了前段)" if f["truncated"] else "")
        + f" · {f['elapsed']:.2f}s")
    ok = 200 <= f["status"] < 300
    mime = _image_mime(f["data"], f["ctype"])
    info = image_info(f["data"])

    if ok and info and mime in IMAGE_MIMES:
        w, h = info["width"], info["height"]
        lines.append(f"[图片] {info['format']} {w}×{h}"
                     + (f" · {info['desc']}" if info["desc"] else ""))
        if w * h > MAX_PIXELS:
            lines.append("[说明] 图片像素过多, 没有附给模型; 只能依据上面的元数据回答, "
                         "不要描述画面内容。")
            return "\n".join(lines), None
        lines.append("[说明] 图片已附在这条工具结果里(直接看图)。游戏聊天栏显示不了图片, "
                     "用一两句话把主体/颜色/文字转述给玩家。")
        return "\n".join(lines), (mime, base64.b64encode(f["data"]).decode("ascii"))

    if not ok:
        lines.append("[说明] 目标返回错误状态, 没有拿到图片/正文; 下面是响应体开头, "
                     "可以据此说明失败原因。")
    lines.append(_preview(f["data"], f["ctype"], max_chars))
    return "\n".join(lines), None
