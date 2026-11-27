"""
video_service.py - Lightweight Serverless HD Video Downloader (No-Watermark)

Supports:
- TikTok (vm.tiktok.com, vt.tiktok.com, tiktok.com/@user/video/...)
- Facebook (Reels, Watch, Video, fb.watch)
- YouTube (Shorts, Video, youtu.be)
- CapCut (capcut.com/t/..., template-detail)
- Pinterest (pin.it/..., pinterest.com/pin/...)

Constraints:
- Pure Python, zero disk writes (no fs.writeFile / no temp files)
- No yt-dlp, no ffmpeg
- Zero-RAM direct streaming URLs with memory buffer fallback (<48MB)
"""

import io
import re
import json
import html
import urllib.parse
from typing import Optional, Dict, Any, Tuple
import requests

# Standard browser headers to avoid anti-bot blocks
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def clean_unwanted_thai(text: str) -> str:
    """
    Strips unwanted Thai characters (Unicode range U+0E00 - U+0E7F)
    to ensure no Thai script mixes with Khmer in Telegram.
    """
    if not text:
        return ""
    # Strip any characters from the Thai unicode block
    cleaned = re.sub(r'[\u0E00-\u0E7F]+', '', text)
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    return cleaned.strip()

# Regex patterns for supported platforms
URL_PATTERNS = {
    "tiktok": re.compile(
        r'https?://(?:www\.|vt\.|vm\.|v\.)?tiktok\.com/[^\s<>"\'`]+',
        re.IGNORECASE
    ),
    "facebook": re.compile(
        r'https?://(?:www\.|web\.|m\.)?(?:facebook\.com/(?:reel|watch|share|[^/]+/videos)/[^\s<>"\'`]+|fb\.watch/[^\s<>"\'`]+)',
        re.IGNORECASE
    ),
    "youtube": re.compile(
        r'https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/|embed/)[^\s<>"\'`]+|youtu\.be/[^\s<>"\'`]+)',
        re.IGNORECASE
    ),
    "capcut": re.compile(
        r'https?://(?:www\.|mobile\.)?(?:capcut\.com|capcutshare\.com|capcut\.net)/(?:t/|tv2/|template-detail/|watch/|s/|templates/)[^\s<>"\'`]+',
        re.IGNORECASE
    ),
    "pinterest": re.compile(
        r'https?://(?:www\.|[a-z]{2}\.)?pinterest\.com/pin/[^\s<>"\'`]+|https?://pin\.it/[^\s<>"\'`]+',
        re.IGNORECASE
    ),
}


def detect_video_url(text: str) -> Optional[Tuple[str, str]]:
    """
    Detects if the incoming text contains a supported video URL.
    Returns (matched_url, platform_code) or None.
    """
    if not text:
        return None

    # Check platforms in prioritized order
    for platform, pattern in URL_PATTERNS.items():
        match = pattern.search(text)
        if match:
            clean_url = match.group(0).rstrip(".,;!?)")
            return clean_url, platform

    return None


def extract_tiktok_video(url: str) -> Optional[Dict[str, Any]]:
    """
    Extracts no-watermark HD TikTok video link using TikWM API,
    with Tiklydown and Lovetik fallbacks.
    """
    # 1. Primary: TikWM API
    try:
        api_url = f"https://www.tikwm.com/api/?url={requests.utils.quote(url)}&hd=1"
        resp = requests.get(api_url, headers=DEFAULT_HEADERS, timeout=(5.0, 15.0))
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                d = data.get("data", {})
                play_url = d.get("hdplay") or d.get("play")
                if play_url:
                    if play_url.startswith("/"):
                        play_url = f"https://www.tikwm.com{play_url}"
                    author_nick = d.get("author", {}).get("nickname") or d.get("author", {}).get("unique_id") or "TikTok Creator"
                    return {
                        "success": True,
                        "direct_url": play_url,
                        "title": d.get("title") or "TikTok Video",
                        "author": author_nick,
                        "platform": "TikTok",
                        "platform_code": "tiktok",
                        "quality": "HD (No Watermark)",
                        "size": d.get("hd_size") or d.get("size")
                    }
    except Exception as e:
        print(f"[video_service] TikWM exception: {e}")

    # 2. Fallback: Tiklydown API
    try:
        t_api = f"https://api.tiklydown.eu.org/api/download?url={requests.utils.quote(url)}"
        resp = requests.get(t_api, headers=DEFAULT_HEADERS, timeout=(5.0, 12.0))
        if resp.status_code == 200:
            data = resp.json()
            video_data = data.get("video", {})
            direct_url = video_data.get("noWatermark") or video_data.get("watermark")
            if direct_url:
                author_name = data.get("author", {}).get("name") or "TikTok Creator"
                return {
                    "success": True,
                    "direct_url": direct_url,
                    "title": data.get("title") or "TikTok Video",
                    "author": author_name,
                    "platform": "TikTok",
                    "platform_code": "tiktok",
                    "quality": "HD (No Watermark)"
                }
    except Exception as e:
        print(f"[video_service] Tiklydown exception: {e}")

    # 3. Fallback: Lovetik API
    try:
        resp = requests.post(
            "https://lovetik.com/api/ajax/search",
            data={"query": url},
            headers=DEFAULT_HEADERS,
            timeout=(5.0, 12.0)
        )
        if resp.status_code == 200:
            data = resp.json()
            links = data.get("links", [])
            for item in links:
                if item.get("a"):
                    return {
                        "success": True,
                        "direct_url": item.get("a"),
                        "title": data.get("desc") or "TikTok Video",
                        "author": data.get("author") or "TikTok Creator",
                        "platform": "TikTok",
                        "platform_code": "tiktok",
                        "quality": "HD (No Watermark)"
                    }
    except Exception as e:
        print(f"[video_service] Lovetik exception: {e}")

    return None


def extract_pinterest_video(url: str) -> Optional[Dict[str, Any]]:
    """
    Extracts direct HD MP4 video link from Pinterest pin or pin.it shortlink
    via direct HTML scraping and metadata parsing.
    """
    try:
        # Resolve shortlink if needed
        session = requests.Session()
        resp = session.get(url, headers=DEFAULT_HEADERS, allow_redirects=True, timeout=(5.0, 15.0))
        if resp.status_code != 200:
            return None

        page_text = resp.text

        # Extract title
        title_match = re.search(r'<meta\s+(?:property|name)=["\']og:title["\']\s+content=["\']([^"\']+)["\']', page_text)
        title = html.unescape(title_match.group(1)) if title_match else "Pinterest Video"

        # 1. Search for direct v1.pinimg.com mp4 video streams
        mp4_matches = re.findall(r'https://v1\.pinimg\.com/videos/[^\s"\'<>]+\.mp4', page_text)
        if mp4_matches:
            # Prefer 720p or highest quality stream
            best_mp4 = mp4_matches[0]
            for m in mp4_matches:
                if "720p" in m.lower():
                    best_mp4 = m
                    break
            return {
                "success": True,
                "direct_url": best_mp4,
                "title": title,
                "author": "Pinterest",
                "platform": "Pinterest",
                "platform_code": "pinterest",
                "quality": "HD"
            }

        # 2. Check JSON data in script tags (__PWS_DATA__)
        pws_matches = re.findall(r'<script[^>]*id="__PWS_DATA__"[^>]*>(.*?)</script>', page_text)
        for block in pws_matches:
            # Search for video URLs inside JSON
            urls = re.findall(r'https:\\?/\\?/[^\s"\'<>]+\.mp4', block)
            if urls:
                clean_url = urls[0].replace(r"\/", "/")
                return {
                    "success": True,
                    "direct_url": clean_url,
                    "title": title,
                    "author": "Pinterest",
                    "platform": "Pinterest",
                    "platform_code": "pinterest",
                    "quality": "HD"
                }

        # 3. Check og:video meta tag
        og_video = re.search(r'<meta\s+(?:property|name)=["\']og:video["\']\s+content=["\']([^"\']+)["\']', page_text)
        if og_video:
            return {
                "success": True,
                "direct_url": html.unescape(og_video.group(1)),
                "title": title,
                "author": "Pinterest",
                "platform": "Pinterest",
                "platform_code": "pinterest",
                "quality": "HD"
            }
    except Exception as e:
        print(f"[video_service] Pinterest exception: {e}")

    return None


def extract_capcut_video(url: str) -> Optional[Dict[str, Any]]:
    """
    Extracts no-watermark HD CapCut template / video link via direct
    SSR data parsing (__MODERN_ROUTER_DATA__, RENDER_DATA, or regex),
    with TikWM and secondary API fallbacks.
    """
    # 1. Primary: Direct CapCut SSR page extraction (Pure Python, fast, HD)
    try:
        session = requests.Session()
        resp = session.get(
            url,
            headers=DEFAULT_HEADERS,
            allow_redirects=True,
            timeout=(5.0, 15.0)
        )
        if resp.status_code == 200:
            page_text = resp.text

            # 1a. Parse __MODERN_ROUTER_DATA__ (Standard CapCut template-detail state)
            m_modern = re.search(r'<script[^>]*id=["\']__MODERN_ROUTER_DATA__["\'][^>]*>(.*?)</script>', page_text, re.DOTALL)
            if m_modern:
                try:
                    data = json.loads(m_modern.group(1))
                    loader_data = data.get("loaderData", {})
                    root = loader_data.get("$", {}) or {}
                    td = root.get("templateDetail", {})
                    sd = td.get("structuredData") or {}

                    direct_url = td.get("videoUrl") or sd.get("contentUrl")
                    if direct_url:
                        raw_title = td.get("title") or sd.get("name") or "CapCut Template"
                        author_obj = td.get("author") or sd.get("creator") or {}
                        raw_author = author_obj.get("name") if isinstance(author_obj, dict) else "CapCut Creator"

                        title = clean_unwanted_thai(raw_title) or "CapCut Template"
                        author = clean_unwanted_thai(raw_author) or "CapCut Creator"

                        height = td.get("videoHeight") or sd.get("height")
                        quality = f"{height}p HD (No Watermark)" if height else "HD (No Watermark)"

                        return {
                            "success": True,
                            "direct_url": direct_url,
                            "title": title.strip(),
                            "author": author.strip(),
                            "platform": "CapCut",
                            "platform_code": "capcut",
                            "quality": quality,
                            "cover_url": td.get("coverUrl") or sd.get("thumbnailUrl"),
                        }
                except Exception as e:
                    print(f"[video_service] CapCut __MODERN_ROUTER_DATA__ parse error: {e}")

            # 1b. Parse RENDER_DATA (URL-encoded JSON format)
            m_render = re.search(r'<script[^>]*id=["\']RENDER_DATA__["\'][^>]*>(.*?)</script>', page_text, re.DOTALL)
            if m_render:
                try:
                    raw_json = urllib.parse.unquote(m_render.group(1).strip())
                    data = json.loads(raw_json)

                    def find_video_url(d):
                        if isinstance(d, dict):
                            for key in ("video_url", "play_url", "videoUrl", "contentUrl"):
                                if d.get(key) and isinstance(d[key], str) and d[key].startswith("http"):
                                    return d[key]
                            for v in d.values():
                                res = find_video_url(v)
                                if res:
                                    return res
                        elif isinstance(d, list):
                            for item in d:
                                res = find_video_url(item)
                                if res:
                                    return res
                        return None

                    direct_url = find_video_url(data)
                    if direct_url:
                        title_match = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', page_text)
                        raw_title = html.unescape(title_match.group(1)) if title_match else "CapCut Template"
                        return {
                            "success": True,
                            "direct_url": direct_url,
                            "title": clean_unwanted_thai(raw_title) or "CapCut Template",
                            "author": "CapCut Creator",
                            "platform": "CapCut",
                            "platform_code": "capcut",
                            "quality": "HD (No Watermark)"
                        }
                except Exception as e:
                    print(f"[video_service] CapCut RENDER_DATA parse error: {e}")

            # 1c. Regex search for contentUrl or videoUrl attributes
            matches = re.findall(r'"(?:contentUrl|videoUrl)"\s*:\s*"([^"]+)"', page_text)
            for m in matches:
                clean = m.encode('utf-8').decode('unicode_escape').replace(r'\/', '/')
                if clean.startswith("http") and ("capcutvod.com" in clean or "ibytedtos.com" in clean or "bytecdn" in clean or ".mp4" in clean):
                    title_match = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', page_text)
                    raw_title = html.unescape(title_match.group(1)) if title_match else "CapCut Template"
                    return {
                        "success": True,
                        "direct_url": clean,
                        "title": clean_unwanted_thai(raw_title) or "CapCut Template",
                        "author": "CapCut Creator",
                        "platform": "CapCut",
                        "platform_code": "capcut",
                        "quality": "HD (No Watermark)"
                    }

            # 1d. Check og:video
            og_video = re.search(r'<meta\s+(?:property|name)=["\']og:video["\']\s+content=["\']([^"\']+)["\']', page_text)
            if og_video:
                title_match = re.search(r'<meta\s+(?:property|name)=["\']og:title["\']\s+content=["\']([^"\']+)["\']', page_text)
                title = clean_unwanted_thai(html.unescape(title_match.group(1))) if title_match else "CapCut Video"
                return {
                    "success": True,
                    "direct_url": html.unescape(og_video.group(1)),
                    "title": title or "CapCut Video",
                    "author": "CapCut Creator",
                    "platform": "CapCut",
                    "platform_code": "capcut",
                    "quality": "HD"
                }
    except Exception as e:
        print(f"[video_service] CapCut direct scraper exception: {e}")

    # 2. Fallback: TikWM API
    try:
        api_url = f"https://www.tikwm.com/api/?url={requests.utils.quote(url)}"
        resp = requests.get(api_url, headers=DEFAULT_HEADERS, timeout=(5.0, 12.0))
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                d = data.get("data", {})
                play_url = d.get("hdplay") or d.get("play")
                if play_url:
                    if play_url.startswith("/"):
                        play_url = f"https://www.tikwm.com{play_url}"
                    raw_title = d.get("title") or "CapCut Template"
                    raw_author = d.get("author", {}).get("nickname") or "CapCut Creator"
                    return {
                        "success": True,
                        "direct_url": play_url,
                        "title": clean_unwanted_thai(raw_title) or "CapCut Template",
                        "author": clean_unwanted_thai(raw_author) or "CapCut Creator",
                        "platform": "CapCut",
                        "platform_code": "capcut",
                        "quality": "HD (No Watermark)"
                    }
    except Exception as e:
        print(f"[video_service] CapCut TikWM exception: {e}")

    return None


def extract_facebook_video(url: str) -> Optional[Dict[str, Any]]:
    """
    Extracts direct HD/SD MP4 video stream from Facebook Reel or Video
    via HTML scraper and parameter extraction.
    """
    try:
        # Fetch page with desktop headers
        resp = requests.get(url, headers=DEFAULT_HEADERS, allow_redirects=True, timeout=(5.0, 15.0))
        if resp.status_code == 200:
            page_text = resp.text

            # Patterns Facebook uses for direct video streams
            patterns = [
                r'"browser_native_hd_url"\s*:\s*"([^"]+)"',
                r'"playable_url_quality_hd"\s*:\s*"([^"]+)"',
                r'"browser_native_sd_url"\s*:\s*"([^"]+)"',
                r'"playable_url"\s*:\s*"([^"]+)"',
                r'hd_src\s*:\s*["\']([^"\']+)["\']',
                r'sd_src\s*:\s*["\']([^"\']+)["\']',
            ]

            for pat in patterns:
                match = re.search(pat, page_text)
                if match:
                    raw_url = match.group(1)
                    # Unescape unicode and slashes
                    direct_url = raw_url.encode('utf-8').decode('unicode_escape').replace(r"\/", "/")
                    if direct_url.startswith("http"):
                        # Extract title
                        title_match = re.search(r'<meta\s+(?:property|name)=["\']og:title["\']\s+content=["\']([^"\']+)["\']', page_text)
                        title = html.unescape(title_match.group(1)) if title_match else "Facebook Video"
                        if len(title) > 90:
                            title = title[:87] + "..."
                        return {
                            "success": True,
                            "direct_url": direct_url,
                            "title": title,
                            "author": "Facebook Creator",
                            "platform": "Facebook",
                            "platform_code": "facebook",
                            "quality": "HD" if "hd" in pat else "SD"
                        }
    except Exception as e:
        print(f"[video_service] Facebook scraper exception: {e}")

    return None


def extract_youtube_video(url: str) -> Optional[Dict[str, Any]]:
    """
    Extracts direct MP4 video stream from YouTube video or Shorts
    using pytubefix (pure Python) with Invidious/Cobalt fallbacks.
    """
    # 1. Primary: pytubefix (pure Python with Android client)
    try:
        from pytubefix import YouTube
        yt = YouTube(url, client='ANDROID')
        raw_title = yt.title or "YouTube Video"
        raw_author = yt.author or "YouTube Creator"
        title = clean_unwanted_thai(raw_title) or "YouTube Video"
        author = clean_unwanted_thai(raw_author) or "YouTube Creator"

        # Prioritize progressive mp4 (video + audio in single stream)
        stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        if not stream:
            stream = yt.streams.get_highest_resolution()

        if stream and stream.url:
            quality = stream.resolution or "HD"
            filesize = getattr(stream, 'filesize', None)
            return {
                "success": True,
                "direct_url": stream.url,
                "title": title,
                "author": author,
                "platform": "YouTube",
                "platform_code": "youtube",
                "quality": f"{quality} (No Watermark)",
                "size": filesize,
                "original_url": url
            }
    except Exception as e:
        print(f"[video_service] pytubefix exception: {e}")

    # 2. Fallback: Extract video ID & query Invidious instances
    video_id = None
    v_match = re.search(r'(?:v=|shorts/|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})', url)
    if v_match:
        video_id = v_match.group(1)

    if video_id:
        invidious_instances = [
            "https://inv.nadeko.net",
            "https://yewtu.be",
            "https://invidious.nerdvpn.de",
            "https://invidious.private.coffee",
        ]

        for inst in invidious_instances:
            try:
                api_url = f"{inst}/api/v1/videos/{video_id}"
                resp = requests.get(api_url, headers=DEFAULT_HEADERS, timeout=(4.0, 10.0))
                if resp.status_code == 200:
                    data = resp.json()
                    title = clean_unwanted_thai(data.get("title") or "YouTube Video")
                    author = clean_unwanted_thai(data.get("author") or "YouTube Creator")
                    format_streams = data.get("formatStreams", [])
                    mp4_streams = [s for s in format_streams if s.get("container") == "mp4" and s.get("url")]
                    if mp4_streams:
                        best_stream = mp4_streams[0]
                        stream_url = best_stream.get("url")
                        quality = best_stream.get("qualityLabel") or "HD"
                        return {
                            "success": True,
                            "direct_url": stream_url,
                            "title": title,
                            "author": author,
                            "platform": "YouTube",
                            "platform_code": "youtube",
                            "quality": f"{quality} (No Watermark)",
                            "original_url": url
                        }
            except Exception:
                continue

    return None


def extract_video_info(url: str, platform_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Unified extraction router: identifies platform and delegates to the appropriate extractor.
    Returns standard dictionary or None on failure.
    """
    if not platform_code:
        detection = detect_video_url(url)
        if detection:
            url, platform_code = detection
        else:
            return None

    platform_code = platform_code.lower()

    if platform_code == "tiktok":
        return extract_tiktok_video(url)
    elif platform_code == "facebook":
        return extract_facebook_video(url)
    elif platform_code == "pinterest":
        return extract_pinterest_video(url)
    elif platform_code == "capcut":
        return extract_capcut_video(url)
    elif platform_code == "youtube":
        return extract_youtube_video(url)

    return None


def fetch_video_buffer(
    video_url: str,
    max_bytes: int = 48 * 1024 * 1024,
    original_url: Optional[str] = None
) -> Tuple[Optional[bytes], Optional[int]]:
    """
    Downloads video stream directly into memory (zero disk usage).
    Returns (bytes_data, total_size).
    If the file is larger than max_bytes or 50MB, returns (None, total_size)
    so the bot can cleanly fallback to Inline Keyboard.
    """
    # Check if target is YouTube - use pytubefix streaming buffer for 100% reliability
    yt_url = original_url if (original_url and ("youtube.com" in original_url or "youtu.be" in original_url)) else None
    if not yt_url and ("youtube.com" in video_url or "youtu.be" in video_url):
        yt_url = video_url

    if yt_url:
        try:
            from pytubefix import YouTube
            yt = YouTube(yt_url, client='ANDROID')
            stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
            if not stream:
                stream = yt.streams.get_highest_resolution()
            if stream:
                filesize = getattr(stream, 'filesize', 0)
                if filesize and filesize > 50 * 1024 * 1024:
                    return None, filesize
                buffer = io.BytesIO()
                stream.stream_to_buffer(buffer)
                val = buffer.getvalue()
                if len(val) > max_bytes:
                    return None, len(val)
                return val, len(val)
        except Exception as e:
            print(f"[video_service] pytubefix stream_to_buffer error: {e}")

    try:
        # Check Content-Length first via HEAD or streaming GET
        resp = requests.get(
            video_url,
            headers=DEFAULT_HEADERS,
            stream=True,
            timeout=(6.0, 30.0)
        )
        if resp.status_code != 200:
            return None, None

        content_length_str = resp.headers.get("Content-Length")
        total_size = int(content_length_str) if content_length_str and content_length_str.isdigit() else None

        # If Content-Length exceeds Telegram Bot limit (50MB), abort memory buffer
        if total_size and total_size > 50 * 1024 * 1024:
            return None, total_size

        buffer = io.BytesIO()
        downloaded = 0

        for chunk in resp.iter_content(chunk_size=128 * 1024):
            if chunk:
                buffer.write(chunk)
                downloaded += len(chunk)
                if downloaded > max_bytes:
                    # Video exceeded memory buffer limit
                    return None, total_size or downloaded

        return buffer.getvalue(), downloaded

    except Exception as e:
        print(f"[video_service] Error streaming video into buffer: {e}")
        return None, None
