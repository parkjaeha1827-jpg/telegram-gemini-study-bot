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
from typing import Optional, Tuple
import edge_tts

# Female neural voices (used when speaker_gender == "male" -> opposite gender)
FEMALE_VOICE_MAP = {
    "km": "km-KH-SreymomNeural",     # Khmer Female
    "en": "en-US-AvaNeural",          # English Female
    "zh": "zh-CN-XiaoxiaoNeural",     # Chinese Female
    "ja": "ja-JP-NanamiNeural",       # Japanese Female
}

# Male neural voices (used when speaker_gender == "female" -> opposite gender)
MALE_VOICE_MAP = {
    "km": "km-KH-PisethNeural",       # Khmer Male
    "en": "en-US-AndrewNeural",       # English Male
    "zh": "zh-CN-YunxiNeural",        # Chinese Male
    "ja": "ja-JP-KeitaNeural",        # Japanese Male
}

# Backward-compatible default voice map
VOICE_MAP = dict(FEMALE_VOICE_MAP)

# Expressive Prosody (rate, pitch) tuned per emotion for Gemini Live realism
EMOTION_PROSODY = {
    "cheerful": ("+5%", "+3Hz"),
    "curious":  ("+5%", "+2Hz"),
    "caring":   ("-5%", "-2Hz"),
    "sassy":    ("+3%", "+2Hz"),
    "angry":    ("+6%", "-2Hz"),
}


def normalize_lang_code(language: Optional[str], fallback_text: str = "") -> str:
    """Normalizes language tag ('km', 'km-KH', 'en-US', 'zh-CN', 'ja-JP') into 'km'|'en'|'zh'|'ja'."""
    if language:
        code = str(language).strip().lower().split("-")[0].split("_")[0]
        if code in ("km", "kh", "khmer"):
            return "km"
        if code in ("en", "eng", "english"):
            return "en"
        if code in ("zh", "cn", "chinese"):
            return "zh"
        if code in ("ja", "jp", "japanese"):
            return "ja"
    return detect_language(fallback_text) if fallback_text else "km"


def select_opposite_gender_voice(
    speaker_gender: Optional[str] = None,
    language: Optional[str] = None,
    text: str = ""
) -> str:
    """
    Opposite-Gender Edge TTS selector:
    - speaker_gender == "male"   -> AI speaks with FEMALE neural voice
    - speaker_gender == "female" -> AI speaks with MALE neural voice
    """
    lang = normalize_lang_code(language, fallback_text=text)
    gender = (speaker_gender or "").strip().lower()
    if gender == "female":
        return MALE_VOICE_MAP.get(lang, "km-KH-PisethNeural")
    return FEMALE_VOICE_MAP.get(lang, "km-KH-SreymomNeural")


def get_emotion_prosody(emotion: Optional[str] = None, text: str = "") -> Tuple[str, str]:
    """
    Computes expressive Edge TTS (rate, pitch) from emotion or narrative/song mode.
    """
    if is_expressive_mode(text):
        return ("-8%", "+0Hz")
    if emotion:
        emo = str(emotion).strip().lower()
        if emo in EMOTION_PROSODY:
            return EMOTION_PROSODY[emo]
    return ("+0%", "+0Hz")


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

    # 7. Remove musical symbols and notes
    cleaned = re.sub(r'[🎶🎵🎤🎼🎻🎸🎹🎺🥁]', '', cleaned)

    # 8. Remove Emojis and decorative symbols
    emoji_pattern = re.compile(
        "[\U00010000-\U0010ffff]|"
        "[\uD800-\uDBFF][\uDC00-\uDFFF]|"
        "[\u2600-\u27BF]|[\u2300-\u23FF]|[\u2B50-\u2B55]|[\u203C-\u2049]|[\u25AA-\u25FE]",
        flags=re.UNICODE
    )
    cleaned = emoji_pattern.sub('', cleaned)

    # 9. Clean redundant hyphens, slashes, or symbols that sound weird when read aloud
    cleaned = re.sub(r'[-–—]{2,}', ' ', cleaned)
    cleaned = re.sub(r'[\r\n\t]+', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned


def is_expressive_mode(text: str) -> bool:
    """
    Detects if the text is a poem, story, song, or expressive narrative
    that should be spoken at a slightly slower, melodious tempo (-8%).
    """
    if not text:
        return False
    expressive_keywords = [
        "កំណាព្យ", "បទពាក្យ", "កាកគតិ", "ពំនោល", "បថ្យាវត្ត", "ព្រហ្មគីតិ",
        "រឿងព្រេង", "និទាន", "កាលពីព្រេងនាយ", "តំណាលថា", "រឿងខ្មោច",
        "ច្រៀង", "ទំនុកច្រៀង", "ចង្វាក់", "កន្ទ្រឹម", "រ៉េប", "ចម្រៀង",
        "🎶", "🎵", "🎤", "🎼", "🎻", "🎸"
    ]
    for kw in expressive_keywords:
        if kw in text:
            return True
    return False


def sanitize_text_for_tts(text: str) -> str:
    """Wrapper ensuring backward compatibility with previous calls."""
    return clean_text_for_tts(text)


async def text_to_speech_async(
    text: str,
    voice: Optional[str] = None,
    rate: Optional[str] = None,
    pitch: Optional[str] = None,
    speaker_gender: Optional[str] = None,
    language: Optional[str] = None,
    emotion: Optional[str] = None
) -> Optional[bytes]:
    """
    Generates natural spoken audio bytes in memory (zero disk writes) using Microsoft Edge TTS.
    Supports:
    - Opposite-gender voice selection (male speaker -> female AI voice; female speaker -> male AI voice)
    - Expressive prosody (rate & pitch dynamically tuned by emotion or poetry/song mode)
    """
    # Compute expressive rate/pitch before stripping musical notes and keywords
    auto_rate, auto_pitch = get_emotion_prosody(emotion=emotion, text=text)
    final_rate = rate if rate is not None else auto_rate
    final_pitch = pitch if pitch is not None else auto_pitch

    clean_text = sanitize_text_for_tts(text)
    if not clean_text:
        return None

    if not voice:
        voice = select_opposite_gender_voice(
            speaker_gender=speaker_gender,
            language=language,
            text=clean_text
        )

    # Deduplicated fallback voice chain preserving gender when possible
    fallback_km = "km-KH-PisethNeural" if (speaker_gender or "").lower() == "female" else "km-KH-SreymomNeural"
    fallback_en = "en-US-AndrewNeural" if (speaker_gender or "").lower() == "female" else "en-US-AvaNeural"
    candidates = list(dict.fromkeys([voice, fallback_km, fallback_en]))

    for target_voice in candidates:
        try:
            kwargs = {"rate": final_rate}
            if final_pitch and final_pitch != "+0Hz":
                kwargs["pitch"] = final_pitch
            communicate = edge_tts.Communicate(clean_text, target_voice, **kwargs)
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


def text_to_speech(
    text: str,
    voice: Optional[str] = None,
    rate: Optional[str] = None,
    pitch: Optional[str] = None,
    speaker_gender: Optional[str] = None,
    language: Optional[str] = None,
    emotion: Optional[str] = None
) -> Optional[bytes]:
    """Synchronous wrapper for text_to_speech_async."""
    try:
        return asyncio.run(
            text_to_speech_async(
                text,
                voice=voice,
                rate=rate,
                pitch=pitch,
                speaker_gender=speaker_gender,
                language=language,
                emotion=emotion
            )
        )
    except Exception as e:
        print(f"[EdgeTTS Error] {e}")
        return None
