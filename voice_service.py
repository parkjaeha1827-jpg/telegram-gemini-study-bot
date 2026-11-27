"""
Voice Service for Telegram Bot
Handles Language Detection, Text-to-Speech (TTS) via edge-tts, and audio sanitization.
Features:
- Auto language detection: Khmer, English, Chinese, Japanese, and multilingual fallback.
- Microsoft Edge TTS integration: Natural neural voices (km-KH-SreymomNeural, en-US-AvaNeural, etc.).
- Audio sanitization: Strips Markdown symbols (*, #, `) and emojis so TTS never reads symbol names.
"""

import re
import asyncio
from typing import Optional
import edge_tts

# Voice mapping based on user requirements
VOICE_MAP = {
    "km": "km-KH-SreymomNeural",     # Khmer (Female)
    "en": "en-US-AvaNeural",          # English (US)
    "zh": "zh-CN-XiaoxiaoNeural",     # Chinese (Mandarin)
    "ja": "ja-JP-NanamiNeural"        # Japanese
}


def detect_language(text: str) -> str:
    """
    Detects primary language of text based on Unicode character ranges.
    Returns: 'km', 'ja', 'zh', or 'en'
    """
    if re.search(r'[\u1780-\u17ff]', text):
        return "km"
    if re.search(r'[\u3040-\u30ff]', text):
        return "ja"
    if re.search(r'[\u4e00-\u9fff]', text):
        return "zh"
    return "en"


def sanitize_text_for_tts(text: str) -> str:
    """
    Strips Markdown formatting (*, #, `), URLs, LaTeX delimiters ($), and emojis
    so that TTS speaks naturally without reading out symbols or punctuation.
    """
    # Remove markdown bold/italic/code/headers
    text = re.sub(r'[*_#`~]', '', text)
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove LaTeX markers
    text = text.replace('$$', '').replace('$', '')
    # Remove emojis and special icons
    emoji_pattern = re.compile(
        "[\U00010000-\U0010ffff]|"
        "[\uD800-\uDBFF][\uDC00-\uDFFF]|"
        "[\u2600-\u27BF]|[\u2300-\u23FF]|[\u2B50-\u2B55]|[\u203C-\u2049]|[\u25AA-\u25FE]",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub('', text)
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


async def text_to_speech_async(text: str, voice: Optional[str] = None) -> Optional[bytes]:
    """Generates natural spoken audio bytes using Microsoft Edge TTS."""
    clean_text = sanitize_text_for_tts(text)
    if not clean_text:
        return None

    if not voice:
        lang = detect_language(clean_text)
        voice = VOICE_MAP.get(lang, "km-KH-SreymomNeural")

    # Try selected voice with fallback
    for target_voice in [voice, "km-KH-SreymomNeural", "en-US-AvaNeural"]:
        try:
            communicate = edge_tts.Communicate(clean_text, target_voice)
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            if audio_data:
                return audio_data
        except Exception as e:
            print(f"[EdgeTTS Warning] Voice {target_voice} failed: {e}")
            continue

    return None


def text_to_speech(text: str, voice: Optional[str] = None) -> Optional[bytes]:
    """Synchronous wrapper for text_to_speech_async."""
    try:
        return asyncio.run(text_to_speech_async(text, voice))
    except Exception as e:
        print(f"[EdgeTTS Error] {e}")
        return None
