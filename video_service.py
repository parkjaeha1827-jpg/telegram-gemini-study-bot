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

import os
import io
import re
import json
import time
import html
import hashlib
import urllib.parse
from typing import Optional, Dict, Any, Tuple
import requests

COOKIE_ENV_MAP = {
    "facebook": "FB_COOKIE",
    "youtube": "YT_COOKIE",
    "tiktok": "TT_COOKIE",
}


def get_platform_cookie(platform_code: str) -> str:
    """Reads optional authenticated Cookie string from Vercel Environment Variables."""
    env_name = COOKIE_ENV_MAP.get((platform_code or "").lower(), "")
    if not env_name:
        return ""
    return (os.environ.get(env_name) or "").strip()


def _make_cookie_failure(platform_code: str, cookie_configured: bool, reason: str = "") -> Dict[str, Any]:
    """Returns a structured failure payload so bot_core can show clear Khmer Cookie guidance."""
    env_name = COOKIE_ENV_MAP.get((platform_code or "").lower(), "")
    return {
        "success": False,
        "direct_url": None,
        "platform_code": platform_code.lower(),
        "cookie_env": env_name,
        "cookie_configured": bool(cookie_configured),
        "error_reason": reason or ("cookie_expired" if cookie_configured else "cookie_missing"),
    }


def _build_youtube_sapisidhash(cookie_str: str, origin: str = "https://www.youtube.com") -> Optional[str]:
    """Computes YouTube SAPISIDHASH Authorization header from SAPISID / __Secure-3PAPISID cookie."""
    if not cookie_str:
        return None
    m = re.search(r'(?:^|;\s*)(?:__Secure-3PAPISID|SAPISID)=([^;\s]+)', cookie_str)
    if not m:
        return None
    sapisid = m.group(1).strip()
    ts = str(int(time.time()))
    digest = hashlib.sha1(f"{ts} {sapisid} {origin}".encode("utf-8")).hexdigest()
    return f"SAPISIDHASH {ts}_{digest}"

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
        r'https?://(?:[a-zA-Z0-9-]+\.)?(?:facebook\.com/(?:reel|watch|share|stories|groups/[^/]+/(?:permalink|posts|videos)|[^/]+/videos|video\.php)[^\s<>"\'`]*|fb\.watch/[^\s<>"\'`]+|fb\.com/[^\s<>"\'`]+)',
        re.IGNORECASE
    ),
    "youtube": re.compile(
        r'https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?v=|shorts/|embed/|v/)[^\s<>"\'`]+|youtu\.be/[^\s<>"\'`]+)',
        re.IGNORECASE
    ),
    "capcut": re.compile(
        r'https?://(?:www\.|mobile\.)?(?:capcut\.com|capcutshare\.com|capcut\.net)/(?:t/|tv2/|template-detail|watch/|s/|templates/|@[^\s/]+/video/)[^\s<>"\'`]*',
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

    # 4. Step 2 (Private / Friends-only Fallback via TT_COOKIE)
    tt_cookie = get_platform_cookie("tiktok")
    if tt_cookie:
        priv = extract_tiktok_private_video(url, tt_cookie)
        if priv:
            return priv
        return _make_cookie_failure("tiktok", cookie_configured=True, reason="cookie_expired")

    return _make_cookie_failure("tiktok", cookie_configured=False, reason="cookie_missing")


def extract_tiktok_private_video(url: str, tt_cookie: str) -> Optional[Dict[str, Any]]:
    """
    Extracts Private / Friends-only TikTok video stream using authenticated TT_COOKIE
    by parsing __UNIVERSAL_DATA_FOR_REHYDRATION__ (playAddr / downloadAddr).
    """
    if not tt_cookie:
        return None
    headers = {
        "User-Agent": DEFAULT_HEADERS["User-Agent"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.tiktok.com/",
        "Cookie": tt_cookie,
    }
    try:
        resp = requests.get(url, headers=headers, allow_redirects=True, timeout=(5.0, 12.0))
        if resp.status_code != 200:
            return None
        page_text = resp.text

        # Parse __UNIVERSAL_DATA_FOR_REHYDRATION__ JSON block
        m_univ = re.search(
            r'<script[^>]*id=["\']__UNIVERSAL_DATA_FOR_REHYDRATION__["\'][^>]*>(.*?)</script>',
            page_text,
            re.DOTALL
        )
        if m_univ:
            try:
                data = json.loads(m_univ.group(1))
                default_scope = data.get("__DEFAULT_SCOPE__", {})
                detail = default_scope.get("webapp.video-detail", {})
                item = detail.get("itemInfo", {}).get("itemStruct", {})
                video_obj = item.get("video", {})

                direct_url = video_obj.get("playAddr") or video_obj.get("downloadAddr")
                if not direct_url:
                    bitrates = video_obj.get("bitrateInfo") or []
                    for br in bitrates:
                        url_list = (br.get("PlayAddr") or {}).get("UrlList") or []
                        if url_list:
                            direct_url = url_list[0]
                            break

                if direct_url and isinstance(direct_url, str) and direct_url.startswith("http"):
                    raw_title = item.get("desc") or "TikTok Private Video"
                    author_obj = item.get("author") or {}
                    raw_author = author_obj.get("nickname") or author_obj.get("uniqueId") or "TikTok Creator"
                    return {
                        "success": True,
                        "direct_url": direct_url,
                        "title": clean_unwanted_thai(raw_title) or "TikTok Private Video",
                        "author": clean_unwanted_thai(raw_author) or "TikTok Creator",
                        "platform": "TikTok",
                        "platform_code": "tiktok",
                        "quality": "HD Private (No Watermark)",
                        "is_private": True,
                        "requires_buffer": True,
                        "auth_cookie": tt_cookie,
                        "referer": "https://www.tiktok.com/",
                        "original_url": url,
                    }
            except Exception as e:
                print(f"[video_service] TikTok private JSON parse warning: {e}")

        # Regex fallback for playAddr / downloadAddr in raw page HTML
        for pat in (r'"playAddr"\s*:\s*"([^"]+)"', r'"downloadAddr"\s*:\s*"([^"]+)"'):
            m_addr = re.search(pat, page_text)
            if m_addr:
                raw_u = m_addr.group(1).encode("utf-8").decode("unicode_escape", errors="ignore").replace(r"\/", "/")
                if raw_u.startswith("http"):
                    return {
                        "success": True,
                        "direct_url": raw_u,
                        "title": "TikTok Private Video",
                        "author": "TikTok Creator",
                        "platform": "TikTok",
                        "platform_code": "tiktok",
                        "quality": "HD Private (No Watermark)",
                        "is_private": True,
                        "requires_buffer": True,
                        "auth_cookie": tt_cookie,
                        "referer": "https://www.tiktok.com/",
                        "original_url": url,
                    }
    except Exception as e:
        print(f"[video_service] TikTok private extractor exception: {e}")

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
                    td = {}
                    for val in loader_data.values():
                        if isinstance(val, dict) and "templateDetail" in val:
                            td = val["templateDetail"]
                            break
                    if not td:
                        td = loader_data.get("$", {}).get("templateDetail", {})
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
    via HTML scraper with entity unescaping and mobile fallback.
    """
    fb_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1"
    }

    try:
        session = requests.Session()
        resp = session.get(url, headers=fb_headers, allow_redirects=True, timeout=(4.0, 10.0))
        if resp.status_code == 200:
            page_text = html.unescape(resp.text).replace('&quot;', '"').replace('&amp;', '&').replace(r'\/', '/')
            
            patterns = [
                r'"browser_native_hd_url"\s*:\s*"([^"]+)"',
                r'"playable_url_quality_hd"\s*:\s*"([^"]+)"',
                r'"hd_src_no_ratelimit"\s*:\s*"([^"]+)"',
                r'hd_src\s*:\s*["\']([^"\']+)["\']',
                r'"browser_native_sd_url"\s*:\s*"([^"]+)"',
                r'"playable_url"\s*:\s*"([^"]+)"',
                r'"sd_src_no_ratelimit"\s*:\s*"([^"]+)"',
                r'sd_src\s*:\s*["\']([^"\']+)["\']',
                r'https?://[^\s"\'<>]*(?:video\.[^\s"\'<>]*fbcdn\.net)[^\s"\'<>]*(?:\.mp4)[^\s"\'<>]*',
            ]

            for pat in patterns:
                match = re.search(pat, page_text)
                if match:
                    raw_url = match.group(1) if match.groups() else match.group(0)
                    direct_url = raw_url.encode('utf-8').decode('unicode_escape', errors='ignore').replace(r'\/', '/')
                    if direct_url.startswith("http"):
                        title_match = re.search(r'<meta\s+(?:property|name)=["\']og:title["\']\s+content=["\']([^"\']+)["\']', page_text)
                        raw_title = html.unescape(title_match.group(1)) if title_match else "Facebook Video"
                        title = clean_unwanted_thai(raw_title) or "Facebook Video"
                        if len(title) > 90:
                            title = title[:87] + "..."
                        return {
                            "success": True,
                            "direct_url": direct_url,
                            "title": title,
                            "author": "Facebook Creator",
                            "platform": "Facebook",
                            "platform_code": "facebook",
                            "quality": "HD (No Watermark)" if ("hd" in pat.lower()) else "SD (No Watermark)",
                            "original_url": url
                        }

        # Mobile fallback attempt
        mobile_headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        mobile_url = re.sub(r'https?://(?:www\.|web\.)?facebook\.com', 'https://m.facebook.com', resp.url if 'resp' in locals() else url)
        m_resp = requests.get(mobile_url, headers=mobile_headers, allow_redirects=True, timeout=(4.0, 8.0))
        if m_resp.status_code == 200:
            m_text = html.unescape(m_resp.text).replace('&quot;', '"').replace('&amp;', '&').replace(r'\/', '/')
            for pat in [
                r'"browser_native_hd_url"\s*:\s*"([^"]+)"',
                r'"browser_native_sd_url"\s*:\s*"([^"]+)"',
                r'https?://[^\s"\'<>]*(?:video\.[^\s"\'<>]*fbcdn\.net)[^\s"\'<>]*(?:\.mp4)[^\s"\'<>]*',
            ]:
                match = re.search(pat, m_text)
                if match:
                    raw_url = match.group(1) if match.groups() else match.group(0)
                    direct_url = raw_url.encode('utf-8').decode('unicode_escape', errors='ignore').replace(r'\/', '/')
                    if direct_url.startswith("http"):
                        return {
                            "success": True,
                            "direct_url": direct_url,
                            "title": "Facebook Video",
                            "author": "Facebook Creator",
                            "platform": "Facebook",
                            "platform_code": "facebook",
                            "quality": "HD (No Watermark)",
                            "original_url": url
                        }
    except Exception as e:
        print(f"[video_service] Facebook scraper exception: {e}")

    # Step 2 (Private / Groups / Friends-only Fallback via FB_COOKIE)
    fb_cookie = get_platform_cookie("facebook")
    if fb_cookie:
        priv = extract_facebook_private_video(url, fb_cookie)
        if priv:
            return priv
        return _make_cookie_failure("facebook", cookie_configured=True, reason="cookie_expired")

    return _make_cookie_failure("facebook", cookie_configured=False, reason="cookie_missing")


def extract_facebook_private_video(url: str, fb_cookie: str) -> Optional[Dict[str, Any]]:
    """
    Extracts Private Facebook video (Groups, Reels, Friends-only) using authenticated FB_COOKIE.
    Parses browser_native_hd_url, playable_url_quality_hd, browser_native_sd_url, playable_url, etc.
    """
    if not fb_cookie:
        return None
    fb_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://www.facebook.com/",
        "Cookie": fb_cookie,
    }
    patterns = [
        r'"browser_native_hd_url"\s*:\s*"([^"]+)"',
        r'"playable_url_quality_hd"\s*:\s*"([^"]+)"',
        r'"hd_src_no_ratelimit"\s*:\s*"([^"]+)"',
        r'hd_src\s*:\s*["\']([^"\']+)["\']',
        r'"browser_native_sd_url"\s*:\s*"([^"]+)"',
        r'"playable_url"\s*:\s*"([^"]+)"',
        r'"sd_src_no_ratelimit"\s*:\s*"([^"]+)"',
        r'sd_src\s*:\s*["\']([^"\']+)["\']',
        r'https?://[^\s"\'<>]*(?:video\.[^\s"\'<>]*fbcdn\.net)[^\s"\'<>]*(?:\.mp4)[^\s"\'<>]*',
    ]

    try:
        resp = requests.get(url, headers=fb_headers, allow_redirects=True, timeout=(5.0, 12.0))
        if resp.status_code != 200:
            return None
        # Detect expired cookie login redirect
        if "/login" in (resp.url or "").lower() or "login.php" in (resp.url or "").lower():
            return None

        page_text = html.unescape(resp.text).replace("&quot;", '"').replace("&amp;", "&").replace(r"\/", "/")
        for pat in patterns:
            match = re.search(pat, page_text)
            if match:
                raw_url = match.group(1) if match.groups() else match.group(0)
                direct_url = raw_url.encode("utf-8").decode("unicode_escape", errors="ignore").replace(r"\/", "/")
                if direct_url.startswith("http"):
                    title_match = re.search(r'<meta\s+(?:property|name)=["\']og:title["\']\s+content=["\']([^"\']+)["\']', page_text)
                    raw_title = html.unescape(title_match.group(1)) if title_match else "Facebook Private Video"
                    title = clean_unwanted_thai(raw_title) or "Facebook Private Video"
                    if len(title) > 90:
                        title = title[:87] + "..."
                    return {
                        "success": True,
                        "direct_url": direct_url,
                        "title": title,
                        "author": "Facebook Private",
                        "platform": "Facebook",
                        "platform_code": "facebook",
                        "quality": "HD Private (No Watermark)" if "hd" in pat.lower() else "SD Private",
                        "is_private": True,
                        "requires_buffer": True,
                        "auth_cookie": fb_cookie,
                        "referer": "https://www.facebook.com/",
                        "original_url": url,
                    }
    except Exception as e:
        print(f"[video_service] Facebook private extractor exception: {e}")

    return None


def extract_youtube_video(url: str) -> Optional[Dict[str, Any]]:
    """
    Extracts direct MP4 video stream from YouTube video or Shorts
    using fast public Invidious instances with progressive or adaptive MP4 fallback,
    and pytubefix fallback.
    """
    # Clean URL and extract video ID
    video_id = None
    v_match = re.search(r'(?:v=|shorts/|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})', url)
    if v_match:
        video_id = v_match.group(1)

    if not video_id:
        return None

    canonical_url = f"https://www.youtube.com/watch?v={video_id}"

    # 1. Primary: Fast Invidious API instances
    invidious_instances = [
        "https://yt.chocolatemoo53.com",
        "https://inv.tux.pizza",
        "https://inv.nadeko.net",
        "https://yewtu.be",
        "https://invidious.private.coffee",
    ]

    for inst in invidious_instances:
        try:
            api_url = f"{inst}/api/v1/videos/{video_id}"
            resp = requests.get(api_url, headers=DEFAULT_HEADERS, timeout=(2.5, 4.0))
            if resp.status_code == 200:
                data = resp.json()
                raw_title = data.get("title") or "YouTube Video"
                raw_author = data.get("author") or "YouTube Creator"
                title = clean_unwanted_thai(raw_title) or "YouTube Video"
                author = clean_unwanted_thai(raw_author) or "YouTube Creator"

                # Check 1a: formatStreams (progressive mp4 with audio + video)
                format_streams = data.get("formatStreams", [])
                mp4_streams = [s for s in format_streams if s.get("container") == "mp4" and s.get("url")]
                if mp4_streams:
                    best_stream = mp4_streams[0]
                    stream_url = best_stream.get("url")
                    quality = best_stream.get("qualityLabel") or best_stream.get("resolution") or "360p HD"
                    return {
                        "success": True,
                        "direct_url": stream_url,
                        "title": title,
                        "author": author,
                        "platform": "YouTube",
                        "platform_code": "youtube",
                        "quality": f"{quality} (No Watermark)",
                        "original_url": canonical_url
                    }

                # Check 1b: adaptiveFormats (fallback to highest quality MP4 stream)
                adaptive_formats = data.get("adaptiveFormats", [])
                video_mp4 = [
                    af for af in adaptive_formats
                    if "video/mp4" in af.get("type", "") and af.get("url")
                ]
                if video_mp4:
                    best_af = video_mp4[0]
                    for af in video_mp4:
                        res_str = str(af.get("resolution", ""))
                        if "720" in res_str or "1080" in res_str:
                            best_af = af
                            break
                        elif "480" in res_str or "360" in res_str:
                            best_af = af

                    stream_url = best_af.get("url")
                    quality = best_af.get("resolution") or "HD"
                    return {
                        "success": True,
                        "direct_url": stream_url,
                        "title": title,
                        "author": author,
                        "platform": "YouTube",
                        "platform_code": "youtube",
                        "quality": f"{quality} (No Watermark)",
                        "original_url": canonical_url
                    }
        except Exception as inv_err:
            print(f"[video_service] Invidious ({inst}) exception: {inv_err}")
            continue

    # 2. Secondary fallback: pytubefix (for local/non-datacenter environments)
    try:
        from pytubefix import YouTube
        for client_name in ['ANDROID_VR', 'ANDROID', 'MWEB']:
            try:
                yt = YouTube(canonical_url, client=client_name)
                raw_title = yt.title or "YouTube Video"
                raw_author = yt.author or "YouTube Creator"
                title = clean_unwanted_thai(raw_title) or "YouTube Video"
                author = clean_unwanted_thai(raw_author) or "YouTube Creator"

                stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
                if not stream:
                    stream = yt.streams.get_highest_resolution()

                if stream and stream.url:
                    quality = getattr(stream, 'resolution', None) or "HD"
                    return {
                        "success": True,
                        "direct_url": stream.url,
                        "title": title,
                        "author": author,
                        "platform": "YouTube",
                        "platform_code": "youtube",
                        "quality": f"{quality} (No Watermark)",
                        "original_url": canonical_url
                    }
            except Exception as client_err:
                print(f"[video_service] pytubefix ({client_name}) exception: {client_err}")
    except Exception as e:
        print(f"[video_service] pytubefix import exception: {e}")

    # 3. Step 2 (Private / Unlisted / Member-only Fallback via YT_COOKIE + InnerTube API)
    yt_cookie = get_platform_cookie("youtube")
    if yt_cookie:
        priv = extract_youtube_private_video(canonical_url, video_id, yt_cookie)
        if priv:
            return priv
        return _make_cookie_failure("youtube", cookie_configured=True, reason="cookie_expired")

    return _make_cookie_failure("youtube", cookie_configured=False, reason="cookie_missing")


def _pick_best_yt_format(streaming_data: Dict[str, Any], max_bytes: int = 48 * 1024 * 1024) -> Optional[Dict[str, Any]]:
    """Selects best progressive MP4 (or adaptive MP4) stream under 48MB from InnerTube streamingData."""
    formats = streaming_data.get("formats") or []
    adaptive = streaming_data.get("adaptiveFormats") or []

    def _is_mp4_under_limit(fmt: Dict[str, Any]) -> bool:
        if not fmt.get("url"):
            return False
        mime = (fmt.get("mimeType") or "").lower()
        if "video/mp4" not in mime:
            return False
        cl = fmt.get("contentLength")
        if cl and str(cl).isdigit() and int(cl) > max_bytes:
            return False
        return True

    # Prefer progressive MP4 (combined video + audio), highest height first
    prog_candidates = [f for f in formats if _is_mp4_under_limit(f)]
    if prog_candidates:
        prog_candidates.sort(key=lambda f: int(f.get("height") or 0), reverse=True)
        return prog_candidates[0]

    # Fallback: adaptive MP4 under 48MB (prefer 720p/480p/360p)
    adap_candidates = [f for f in adaptive if _is_mp4_under_limit(f)]
    if adap_candidates:
        adap_candidates.sort(key=lambda f: int(f.get("height") or 0), reverse=True)
        return adap_candidates[0]

    return None


def extract_youtube_private_video(
    canonical_url: str,
    video_id: str,
    yt_cookie: str,
    max_bytes: int = 48 * 1024 * 1024
) -> Optional[Dict[str, Any]]:
    """
    Extracts Private / Unlisted / Age-Restricted / Member-only YouTube video stream
    using authenticated YT_COOKIE via YouTube InnerTube player API + HTML fallback (zero yt-dlp).
    """
    if not yt_cookie:
        return None

    auth_header = _build_youtube_sapisidhash(yt_cookie, origin="https://www.youtube.com")
    base_headers = {
        "User-Agent": DEFAULT_HEADERS["User-Agent"],
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "Origin": "https://www.youtube.com",
        "Referer": canonical_url,
        "Cookie": yt_cookie,
    }
    if auth_header:
        base_headers["Authorization"] = auth_header

    # 1. Authenticated InnerTube /youtubei/v1/player call
    innertube_clients = [
        {"clientName": "WEB", "clientVersion": "2.20260708.00.00"},
        {"clientName": "ANDROID_VR", "clientVersion": "1.65.10", "androidSdkVersion": 32},
    ]
    for client_ctx in innertube_clients:
        try:
            payload = {
                "videoId": video_id,
                "context": {"client": client_ctx},
                "contentCheckOk": True,
                "racyCheckOk": True,
            }
            resp = requests.post(
                "https://www.youtube.com/youtubei/v1/player?prettyPrint=false",
                headers=base_headers,
                json=payload,
                timeout=(4.0, 10.0)
            )
            if resp.status_code == 200:
                data = resp.json()
                status = (data.get("playabilityStatus") or {}).get("status", "")
                if status in ("LOGIN_REQUIRED", "ERROR"):
                    continue
                streaming_data = data.get("streamingData") or {}
                best = _pick_best_yt_format(streaming_data, max_bytes=max_bytes)
                if best and best.get("url"):
                    vd = data.get("videoDetails") or {}
                    title = clean_unwanted_thai(vd.get("title") or "YouTube Private Video") or "YouTube Private Video"
                    author = clean_unwanted_thai(vd.get("author") or "YouTube Creator") or "YouTube Creator"
                    quality = best.get("qualityLabel") or (f"{best.get('height')}p" if best.get("height") else "HD")
                    cl = best.get("contentLength")
                    size_int = int(cl) if cl and str(cl).isdigit() else None
                    return {
                        "success": True,
                        "direct_url": best["url"],
                        "title": title,
                        "author": author,
                        "platform": "YouTube",
                        "platform_code": "youtube",
                        "quality": f"{quality} Private (No Watermark)",
                        "size": size_int,
                        "is_private": True,
                        "requires_buffer": True,
                        "auth_cookie": yt_cookie,
                        "referer": "https://www.youtube.com/",
                        "original_url": canonical_url,
                    }
        except Exception as e:
            print(f"[video_service] YouTube private InnerTube warning: {e}")
            continue

    # 2. Fallback: Authenticated watch HTML page (ytInitialPlayerResponse)
    try:
        html_headers = dict(base_headers)
        html_headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        resp = requests.get(canonical_url, headers=html_headers, timeout=(4.0, 10.0))
        if resp.status_code == 200:
            m_init = re.search(r'var\s+ytInitialPlayerResponse\s*=\s*(\{.*?\});', resp.text, re.DOTALL)
            if m_init:
                data = json.loads(m_init.group(1))
                streaming_data = data.get("streamingData") or {}
                best = _pick_best_yt_format(streaming_data, max_bytes=max_bytes)
                if best and best.get("url"):
                    vd = data.get("videoDetails") or {}
                    title = clean_unwanted_thai(vd.get("title") or "YouTube Private Video") or "YouTube Private Video"
                    author = clean_unwanted_thai(vd.get("author") or "YouTube Creator") or "YouTube Creator"
                    quality = best.get("qualityLabel") or "HD"
                    return {
                        "success": True,
                        "direct_url": best["url"],
                        "title": title,
                        "author": author,
                        "platform": "YouTube",
                        "platform_code": "youtube",
                        "quality": f"{quality} Private (No Watermark)",
                        "is_private": True,
                        "requires_buffer": True,
                        "auth_cookie": yt_cookie,
                        "referer": "https://www.youtube.com/",
                        "original_url": canonical_url,
                    }
    except Exception as e:
        print(f"[video_service] YouTube private HTML fallback warning: {e}")

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
    original_url: Optional[str] = None,
    cookie: Optional[str] = None,
    referer: Optional[str] = None
) -> Tuple[Optional[bytes], Optional[int]]:
    """
    Downloads video stream directly into memory (zero disk usage).
    Supports authenticated Cookie and Referer headers for Private videos.
    Returns (bytes_data, total_size).
    If the file is larger than max_bytes or 50MB, returns (None, total_size)
    so the bot can cleanly notify or fallback to Inline Keyboard.
    """
    req_headers = dict(DEFAULT_HEADERS)
    if cookie:
        req_headers["Cookie"] = cookie
    if referer:
        req_headers["Referer"] = referer
        parsed_ref = urllib.parse.urlparse(referer)
        if parsed_ref.scheme and parsed_ref.netloc:
            req_headers["Origin"] = f"{parsed_ref.scheme}://{parsed_ref.netloc}"

    try:
        resp = requests.get(
            video_url,
            headers=req_headers,
            stream=True,
            allow_redirects=True,
            timeout=(5.0, 22.0)
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
                    return None, total_size or downloaded

        return buffer.getvalue(), downloaded

    except Exception as e:
        print(f"[video_service] Error streaming video into buffer: {e}")
        return None, None
