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
    "km": "km-KH-SreymomNeural",     # Khmer (Female: Sreymom / Male: Piseth)
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


def clean_text_for_tts(text: str) -> str:
    """
    Comprehensive cleaner for Text-to-Speech (TTS):
    1. Removes HTML tags (<b>, <i>, <code>, etc.).
    2. Removes Markdown formatting (*, #, `, ~).
    3. Removes emojis and decorative icons.
    4. Converts mathematical formulas and symbols (√, ÷, =, ², etc.)
       into natural spoken Khmer / English words so speech sounds human.
    """
    if not text:
        return ""

    lang = detect_language(text)

    # 1. Remove HTML tags
    cleaned = re.sub(r'<[^>]+>', ' ', text)

    # 2. Remove URLs
    cleaned = re.sub(r'https?://\S+', '', cleaned)

    # 3. Handle LaTeX fractions \frac{A}{B} and roots \sqrt{A}
    cleaned = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r' \1 ចែកនឹង \2 ' if lang == "km" else r' \1 divided by \2 ', cleaned)
    cleaned = re.sub(r'\\sqrt\{([^}]+)\}', r' ឫសការ៉េនៃ \1 ' if lang == "km" else r' square root of \1 ', cleaned)

    # 4. Remove LaTeX wrappers and symbols
    cleaned = cleaned.replace('$$', ' ').replace('$', ' ')
    cleaned = re.sub(r'\\[a-zA-Z]+', ' ', cleaned)

    # 5. Convert Math Symbols to Spoken Words
    if lang == "km":
        math_map = [
            (r'√', ' ឫសការ៉េនៃ '),
            (r'∛', ' ឫសគូបនៃ '),
            (r'÷', ' ចែកនឹង '),
            (r'×', ' គុណនឹង '),
            (r'≠', ' មិនស្មើនឹង '),
            (r'≤', ' តូចជាងឬស្មើ '),
            (r'≥', ' ធំជាងឬស្មើ '),
            (r'±', ' បូកដក '),
            (r'=', ' ស្មើនឹង '),
            (r'²', ' ការ៉េ '),
            (r'³', ' គូប '),
            (r'\^2', ' ការ៉េ '),
            (r'\^3', ' គូប '),
            (r'\+', ' បូក '),
            (r'%', ' ភាគរយ '),
            (r'π', ' ផៃ '),
            (r'∫', ' អាំងតេក្រាលនៃ '),
            (r'\blim\b', ' លីមីត '),
        ]
    else:
        math_map = [
            (r'√', ' square root of '),
            (r'∛', ' cube root of '),
            (r'÷', ' divided by '),
            (r'×', ' times '),
            (r'≠', ' is not equal to '),
            (r'≤', ' is less than or equal to '),
            (r'≥', ' is greater than or equal to '),
            (r'±', ' plus or minus '),
            (r'=', ' equals '),
            (r'²', ' squared '),
            (r'³', ' cubed '),
            (r'\^2', ' squared '),
            (r'\^3', ' cubed '),
            (r'\+', ' plus '),
            (r'%', ' percent '),
            (r'π', ' pi '),
            (r'∫', ' integral of '),
            (r'\blim\b', ' limit of '),
        ]

    for pat, spoken in math_map:
        cleaned = re.sub(pat, spoken, cleaned)

    # 6. Remove Markdown formatting (*, _, #, `, ~)
    cleaned = re.sub(r'[*_#`~]', '', cleaned)

    # 7. Remove Emojis and decorative symbols
    emoji_pattern = re.compile(
        "[\U00010000-\U0010ffff]|"
        "[\uD800-\uDBFF][\uDC00-\uDFFF]|"
        "[\u2600-\u27BF]|[\u2300-\u23FF]|[\u2B50-\u2B55]|[\u203C-\u2049]|[\u25AA-\u25FE]",
        flags=re.UNICODE
    )
    cleaned = emoji_pattern.sub('', cleaned)

    # 8. Clean redundant hyphens, slashes, or symbols that sound weird when read aloud
    cleaned = re.sub(r'[-–—]{2,}', ' ', cleaned)
    cleaned = re.sub(r'[\r\n\t]+', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned


def sanitize_text_for_tts(text: str) -> str:
    """Wrapper ensuring backward compatibility with previous calls."""
    return clean_text_for_tts(text)


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
