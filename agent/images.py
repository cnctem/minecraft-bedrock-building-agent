"""图片直链识别与规范化；图片由 DeepSeek 服务端读取。"""
import re
import urllib.parse

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
