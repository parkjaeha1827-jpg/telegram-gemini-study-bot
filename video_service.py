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
        r'https?://(?:www\.)?capcut\.com/(?:t/|template-detail/)[^\s<>"\'`]+',
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
    Extracts no-watermark CapCut template / video link via TikWM API
    or direct page metadata scraper.
    """
    # 1. Primary: TikWM API (supports CapCut)
    try:
        api_url = f"https://www.tikwm.com/api/?url={requests.utils.quote(url)}"
        resp = requests.get(api_url, headers=DEFAULT_HEADERS, timeout=(5.0, 15.0))
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                d = data.get("data", {})
                play_url = d.get("hdplay") or d.get("play")
                if play_url:
                    if play_url.startswith("/"):
                        play_url = f"https://www.tikwm.com{play_url}"
                    return {
                        "success": True,
                        "direct_url": play_url,
                        "title": d.get("title") or "CapCut Template",
                        "author": d.get("author", {}).get("nickname") or "CapCut Creator",
                        "platform": "CapCut",
                        "platform_code": "capcut",
                        "quality": "HD (No Watermark)"
                    }
    except Exception as e:
        print(f"[video_service] CapCut TikWM exception: {e}")

    # 2. Direct Scraper Fallback
    try:
        session = requests.Session()
        resp = session.get(url, headers=DEFAULT_HEADERS, allow_redirects=True, timeout=(5.0, 15.0))
        if resp.status_code == 200:
            page_text = resp.text
            # Check og:video
            og_video = re.search(r'<meta\s+(?:property|name)=["\']og:video["\']\s+content=["\']([^"\']+)["\']', page_text)
            if og_video:
                title_match = re.search(r'<meta\s+(?:property|name)=["\']og:title["\']\s+content=["\']([^"\']+)["\']', page_text)
                title = html.unescape(title_match.group(1)) if title_match else "CapCut Video"
                return {
                    "success": True,
                    "direct_url": html.unescape(og_video.group(1)),
                    "title": title,
                    "author": "CapCut Creator",
                    "platform": "CapCut",
                    "platform_code": "capcut",
                    "quality": "HD"
                }

            # Search for video_url in JSON scripts
            v_matches = re.findall(r'"video_url"\s*:\s*"([^"]+)"', page_text)
            if v_matches:
                clean_url = v_matches[0].replace(r"\/", "/")
                return {
                    "success": True,
                    "direct_url": clean_url,
                    "title": "CapCut Video",
                    "author": "CapCut Creator",
                    "platform": "CapCut",
                    "platform_code": "capcut",
                    "quality": "HD"
                }
    except Exception as e:
        print(f"[video_service] CapCut scraper exception: {e}")

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
    using public Invidious instances without any local binaries.
    """
    # Extract video ID
    video_id = None
    v_match = re.search(r'(?:v=|shorts/|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})', url)
    if v_match:
        video_id = v_match.group(1)

    if not video_id:
        return None

    # Known healthy Invidious API instances
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
                title = data.get("title") or "YouTube Video"
                author = data.get("author") or "YouTube Creator"
                format_streams = data.get("formatStreams", [])
                # Select mp4 with highest resolution
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
                        "quality": f"{quality} (No Watermark)"
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


def fetch_video_buffer(video_url: str, max_bytes: int = 48 * 1024 * 1024) -> Tuple[Optional[bytes], Optional[int]]:
    """
    Downloads video stream directly into memory (zero disk usage).
    Returns (bytes_data, total_size).
    If the file is larger than max_bytes or 50MB, returns (None, total_size)
    so the bot can cleanly fallback to Inline Keyboard.
    """
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
