"""
media_gen_service.py - AI Image Generator & Veo AI Video Generator (Text-to-Video & Image-to-Video)

Features:
- Command & Natural Intent Parsing:
  * Image: /img <prompt>, "បង្កើតរូបភាព...", "គូររូប...", "generate image..."
  * Video: /video <prompt>, "បង្កើតវីដេអូ...", "ធ្វើវីដេអូ..." (supports Text-to-Video & Image-to-Video)
- Auto Prompt Enhancer:
  * Uses gemini-2.5-flash (with fast fallback to gemini-3.1-flash-lite) to translate Khmer/multilingual
    prompts into rich, cinematic English prompts for maximum visual fidelity.
- Fast AI Image Generation (5-10s, zero disk writes):
  * Uses gemini-2.5-flash-image (generateContent with responseModalities: ["TEXT", "IMAGE"])
  * Automatic fallback to imagen-3.0-generate-002 / imagen-4.0-generate-001 (:predict)
  * Returns raw image bytes in memory for Telegram sendPhoto.
- AI Video Generation (5-10s duration, zero disk writes):
  * Uses Veo models (veo-2.0-generate-001 / veo-3.0-generate-001) via :predictLongRunning
  * Supports durationSeconds (8s), aspectRatio (16:9 / 9:16), and Image-to-Video (bytesBase64Encoded)
  * Polls operation status every 4 seconds safely within Vercel's 60s maxDuration
  * Detects missing Google AI Studio Billing and returns clear Khmer instructions.
"""

import os
import re
import time
import json
import html
import random
import base64
import urllib.parse
from typing import Optional, Tuple, Dict, Any, List
import requests

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
POLLINATIONS_IMAGE_BASE = "https://image.pollinations.ai/prompt"
POLLINATIONS_IMAGE_ALT_BASE = "https://pollinations.ai/p"
POLLINATIONS_VIDEO_BASE = "https://video.pollinations.ai/prompt"

HF_FREE_VIDEO_MODELS = [
    "Wan-AI/Wan2.1-T2V-1.3B",
    "Lightricks/LTX-Video",
]

ENHANCER_MODELS = [
    "gemini-2.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
]

GEMINI_IMAGE_MODELS = [
    "gemini-2.5-flash-image",
    "gemini-2.0-flash-preview-image-generation",
]

IMAGEN_MODELS = [
    "imagen-3.0-generate-002",
    "imagen-4.0-generate-001",
]

VEO_VIDEO_MODELS = [
    "veo-2.0-generate-001",
    "veo-3.0-generate-001",
    "veo-3.0-generate-preview",
    "veo-3.1-generate-preview",
]


def _clean_no_thai(text: str) -> str:
    """Strictly removes Thai characters (U+0E00-U+0E7F)."""
    if not text:
        return ""
    cleaned = re.sub(r'[\u0E00-\u0E7F]+', '', str(text))
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    return cleaned.strip()


def detect_aspect_ratio(prompt: str, default: str = "16:9") -> str:
    """Detects requested aspect ratio from prompt text (9:16 vertical vs 16:9 horizontal vs 1:1)."""
    if not prompt:
        return default
    lower = prompt.lower()
    if any(k in lower for k in ["9:16", "បញ្ឈរ", "vertical", "portrait", "tiktok", "shorts", "reels", "story"]):
        return "9:16"
    if any(k in lower for k in ["16:9", "ផ្ដេក", "landscape", "widescreen", "youtube", "cinema"]):
        return "16:9"
    if any(k in lower for k in ["1:1", "ការ៉េ", "square"]):
        return "1:1" if default == "1:1" else "16:9"
    return default


def parse_image_intent(text: str) -> Optional[str]:
    """
    Detects /img command or natural Khmer/English image generation requests.
    Returns the extracted prompt string (may be empty if bare /img command), or None if not an image request.
    """
    if not text:
        return None
    stripped = text.strip()
    lower = stripped.lower()

    # 1. Explicit slash commands: /img, /image
    cmd_match = re.match(r'^/(?:img|image)(?:@[a-zA-Z0-9_]+)?(?:\s+(.*))?$', stripped, re.IGNORECASE | re.DOTALL)
    if cmd_match:
        return (cmd_match.group(1) or "").strip()

    # 2. Natural Khmer image triggers (start of message)
    kh_pattern = re.compile(
        r'^(?:សូម|ជួយ|សូមជួយ)?\s*(?:បង្កើតរូបភាព|បង្កើតរូប|គូររូបភាព|គូររូប|រចនារូបភាព)\s*[:：\-]?\s*(.*)$',
        re.IGNORECASE | re.DOTALL
    )
    m_kh = kh_pattern.match(stripped)
    if m_kh:
        prompt = (m_kh.group(1) or "").strip()
        if prompt:
            return prompt

    # 3. Natural English image triggers
    en_pattern = re.compile(
        r'^(?:please\s+)?(?:generate|create|draw|paint|make)\s+(?:me\s+)?(?:an?\s+)?(?:ai\s+)?(?:image|picture|photo|illustration|artwork)\s*(?:of|:|-)?\s*(.+)$',
        re.IGNORECASE | re.DOTALL
    )
    m_en = en_pattern.match(stripped)
    if m_en:
        return m_en.group(1).strip()

    return None


def parse_video_intent(text: str) -> Optional[str]:
    """
    Detects /video command or natural Khmer/English AI video generation requests.
    Returns the extracted prompt string (may be empty if bare /video command), or None if not a video request.
    """
    if not text:
        return None
    stripped = text.strip()

    # 1. Explicit slash commands: /video, /vid
    cmd_match = re.match(r'^/(?:video|vid)(?:@[a-zA-Z0-9_]+)?(?:\s+(.*))?$', stripped, re.IGNORECASE | re.DOTALL)
    if cmd_match:
        return (cmd_match.group(1) or "").strip()

    # 2. Natural Khmer video triggers
    kh_pattern = re.compile(
        r'^(?:សូម|ជួយ|សូមជួយ)?\s*(?:បង្កើតវីដេអូ|ធ្វើវីដេអូ|បង្កើតវិដេអូ|ធ្វើវិដេអូ|ធ្វើឱ្យរូប(?:នេះ)?មានចលនា|ឱ្យរូប(?:នេះ)?កម្រើក)\s*[:：\-]?\s*(.*)$',
        re.IGNORECASE | re.DOTALL
    )
    m_kh = kh_pattern.match(stripped)
    if m_kh:
        return (m_kh.group(1) or "").strip()

    # 3. Natural English video triggers
    en_pattern = re.compile(
        r'^(?:please\s+)?(?:generate|create|make)\s+(?:me\s+)?(?:an?\s+)?(?:ai\s+)?video\s*(?:of|from|about|:|-)?\s*(.*)$',
        re.IGNORECASE | re.DOTALL
    )
    m_en = en_pattern.match(stripped)
    if m_en:
        return (m_en.group(1) or "").strip()

    if re.match(r'^(?:please\s+)?(?:animate\s+this|image\s+to\s+video)\b', stripped, re.IGNORECASE):
        return stripped

    return None


def enhance_media_prompt(
    user_prompt: str,
    media_type: str = "image",
    api_key: Optional[str] = None,
    has_reference_image: bool = False
) -> str:
    """
    Auto Prompt Enhancer:
    Uses gemini-2.5-flash (with fast fallback) to translate Khmer/other languages into
    vivid, detailed, cinematic English prompts for optimal Image / Veo Video output.
    """
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    clean_raw = (user_prompt or "").strip()
    if not clean_raw:
        if media_type == "video" and has_reference_image:
            return "Smooth cinematic camera movement bringing this scene to life with natural motion, realistic lighting, high resolution, 4k detail."
        return "A breathtaking cinematic scene, ultra-detailed, realistic lighting, high resolution."

    if not key:
        return clean_raw

    if media_type == "video":
        instruction = (
            "You are an expert cinematography prompt engineer for Google Veo AI video generation. "
            "Translate the user's request (Khmer or any language) into ONE concise, vivid English video prompt "
            "(2 to 4 sentences max). Include natural camera movement, realistic lighting, atmospheric depth, "
            "smooth lifelike motion, and cinematic high resolution. "
            + ("The user provided a reference photo for Image-to-Video; describe smooth natural animation continuing from the photo. " if has_reference_image else "")
            + "Output ONLY the final English prompt with no explanations or quotes."
        )
    else:
        instruction = (
            "You are an expert AI art prompt engineer. Translate the user's request (Khmer or any language) "
            "into ONE vivid, detailed English image generation prompt (2 to 3 sentences max). "
            "Include composition, cinematic framing, realistic lighting, rich textures, and high resolution. "
            "Output ONLY the final English prompt with no explanations or quotes."
        )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": f"{instruction}\n\nUser request: {clean_raw}"}]}],
        "generationConfig": {
            "temperature": 0.6,
            "maxOutputTokens": 250,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": key,
    }

    for model_name in ENHANCER_MODELS:
        url = f"{GEMINI_API_BASE}/models/{model_name}:generateContent?key={key}"
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=7.0)
            if resp.status_code == 200:
                candidates = resp.json().get("candidates") or []
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts") or []
                    text = " ".join(
                        p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text") and not p.get("thought")
                    ).strip()
                    if text:
                        return text.strip('"\' ')
            elif resp.status_code in (404, 429, 503):
                continue
        except Exception as e:
            print(f"[media_gen] Prompt enhancer ({model_name}) warning: {e}")
            continue

    return clean_raw


def _is_billing_error(status_code: int, error_text: str) -> bool:
    """Detects Google AI Studio billing / paid-tier restrictions."""
    lower = (error_text or "").lower()
    billing_signals = [
        "billing",
        "paid tier",
        "paid plan",
        "payment",
        "billed users",
        "requires a billed",
        "enable billing",
        "not available on the free tier",
        "only accessible to billed",
        "upgrade your plan",
    ]
    if any(sig in lower for sig in billing_signals):
        return True
    if status_code in (402, 403) and ("permission" in lower or "quota" in lower or "veo" in lower):
        return True
    return False


def build_pollinations_image_url(
    english_prompt: str,
    width: int = 1024,
    height: int = 1024,
    seed: Optional[int] = None,
    use_alt_host: bool = False
) -> str:
    """Builds a 100% free, no-watermark Pollinations AI image URL."""
    s = seed if seed is not None else random.randint(1, 1000000)
    encoded = urllib.parse.quote((english_prompt or "beautiful scenery").strip(), safe="")
    base = POLLINATIONS_IMAGE_ALT_BASE if use_alt_host else POLLINATIONS_IMAGE_BASE
    return f"{base}/{encoded}?width={width}&height={height}&nologo=true&seed={s}"


def _dimensions_for_aspect_ratio(aspect_ratio: str, video: bool = False) -> Tuple[int, int]:
    if aspect_ratio == "16:9":
        return (1024, 576) if video else (1280, 720)
    if aspect_ratio == "9:16":
        return (576, 1024) if video else (720, 1280)
    return (1024, 1024)


def fetch_pollinations_image_bytes(
    english_prompt: str,
    width: int = 1024,
    height: int = 1024,
    seed: Optional[int] = None
) -> Optional[bytes]:
    """
    Downloads a 100% free AI-generated image into memory (zero disk writes)
    from Pollinations AI with automatic retry on transient 502/503 responses.
    """
    s = seed if seed is not None else random.randint(1, 1000000)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    candidate_urls = [
        build_pollinations_image_url(english_prompt, width=width, height=height, seed=s, use_alt_host=False),
        build_pollinations_image_url(english_prompt, width=width, height=height, seed=s + 1, use_alt_host=True),
    ]
    for url in candidate_urls:
        try:
            resp = requests.get(url, headers=headers, timeout=(6.0, 22.0), allow_redirects=True)
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if resp.status_code == 200 and ("image" in ctype or resp.content[:4] in (b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1", b"\x89PNG")) and len(resp.content) > 1000:
                return resp.content
        except Exception as e:
            print(f"[media_gen] Pollinations fetch warning: {e}")
            continue
    return None


def generate_ai_image(
    prompt: str,
    api_key: Optional[str] = None,
    aspect_ratio: Optional[str] = None
) -> Tuple[bool, Optional[bytes], str, str]:
    """
    Generates a 100% FREE unlimited AI image in memory (zero disk usage):
    1. Auto-enhances Khmer/multilingual prompt into detailed English via gemini-2.5-flash.
    2. Primary (100% Free, No Billing): Pollinations AI (image.pollinations.ai).
    3. Fallback: gemini-2.5-flash-image / imagen-3.0-generate-002 (if API key available).

    Returns: (success, image_bytes_or_None, enhanced_prompt, model_or_error_khmer)
    """
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    ratio = aspect_ratio or detect_aspect_ratio(prompt, default="1:1")
    enhanced_prompt = enhance_media_prompt(prompt, media_type="image", api_key=key) if key else (prompt or "").strip()

    # 1. Primary: 100% Free Unlimited Pollinations AI (No Billing Required)
    w, h = _dimensions_for_aspect_ratio(ratio, video=False)
    pollinations_bytes = fetch_pollinations_image_bytes(enhanced_prompt, width=w, height=h)
    if pollinations_bytes:
        return True, pollinations_bytes, enhanced_prompt, "Pollinations AI (Free HD)"

    if not key:
        return (
            False,
            None,
            enhanced_prompt,
            "❌ <b>ប្រព័ន្ធ Pollinations AI កំពុងមមាញឹកបន្តិច</b> សូមព្យាយាមសាកល្បងម្ដងទៀតនៅពេលបន្តិចទៀត។"
        )

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": key,
    }
    last_error = ""
    billing_blocked = False

    # 2. Secondary Fallback: Gemini Native Image Generation (gemini-2.5-flash-image)
    for model_name in GEMINI_IMAGE_MODELS:
        url = f"{GEMINI_API_BASE}/models/{model_name}:generateContent?key={key}"
        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": enhanced_prompt}]}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {
                    "aspectRatio": ratio
                }
            }
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=25.0)
            # Retry without imageConfig if model version rejects imageConfig field
            if resp.status_code == 400 and "imageConfig" in resp.text:
                payload["generationConfig"].pop("imageConfig", None)
                resp = requests.post(url, headers=headers, json=payload, timeout=25.0)

            if resp.status_code == 200:
                candidates = resp.json().get("candidates") or []
                for cand in candidates:
                    parts = cand.get("content", {}).get("parts") or []
                    for part in parts:
                        inline = part.get("inlineData") or part.get("inline_data")
                        if inline and inline.get("data"):
                            img_bytes = base64.b64decode(inline["data"])
                            if img_bytes:
                                return True, img_bytes, enhanced_prompt, model_name
            else:
                if _is_billing_error(resp.status_code, resp.text):
                    billing_blocked = True
                last_error = f"{model_name}: {resp.status_code}"
        except Exception as e:
            last_error = f"{model_name}: {e}"
            continue

    # 2. Fallback: Imagen 3 / Imagen 4 (:predict)
    for model_name in IMAGEN_MODELS:
        url = f"{GEMINI_API_BASE}/models/{model_name}:predict?key={key}"
        payload = {
            "instances": [{"prompt": enhanced_prompt}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": ratio,
            }
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=25.0)
            if resp.status_code == 200:
                predictions = resp.json().get("predictions") or []
                if predictions and predictions[0].get("bytesBase64Encoded"):
                    img_bytes = base64.b64decode(predictions[0]["bytesBase64Encoded"])
                    if img_bytes:
                        return True, img_bytes, enhanced_prompt, model_name
            else:
                if _is_billing_error(resp.status_code, resp.text):
                    billing_blocked = True
                last_error = f"{model_name}: {resp.status_code}"
        except Exception as e:
            last_error = f"{model_name}: {e}"
            continue

    if billing_blocked:
        return (
            False,
            None,
            enhanced_prompt,
            "⚠️ <b>មិនអាចបង្កើតរូបភាពបានទេ (ត្រូវការបើក Billing)</b>\n\n"
            "ម៉ូដែលបង្កើតរូបភាព (Gemini Image / Imagen) តម្រូវឱ្យបើក <b>Billing (Pay-as-you-go)</b> នៅក្នុង Google AI Studio ជាមុនសិន។\n"
            "👉 សូមចូលទៅកាន់ https://aistudio.google.com/ រួចភ្ជាប់ Billing ជាមួយ API Key របស់លោកអ្នក។"
        )

    if "429" in last_error:
        return (
            False,
            None,
            enhanced_prompt,
            "⚠️ <b>ប្រព័ន្ធបង្កើតរូបភាពកំពុងជាប់ Quota / Rate Limit</b>\n"
            "សូមរង់ចាំប្រហែល ៣០ វិនាទី រួចសាកល្បងម្ដងទៀត។"
        )

    return (
        False,
        None,
        enhanced_prompt,
        f"❌ <b>មិនអាចបង្កើតរូបភាពបានទេ</b> ({_clean_no_thai(last_error)})\n"
        "សូមសាកល្បងប្ដូរពាក្យបញ្ជា ឬព្យាយាមម្ដងទៀតនៅពេលបន្តិចទៀត។"
    )


def _extract_video_uri_or_bytes(op_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[bytes]]:
    """Extracts generated MP4 URI or inline base64 bytes from a completed Veo operation payload."""
    response = op_data.get("response") or {}

    # Standard Gemini API Veo path: response.generateVideoResponse.generatedSamples[0].video.uri
    gen_resp = response.get("generateVideoResponse") or {}
    samples = gen_resp.get("generatedSamples") or []
    for sample in samples:
        vid = sample.get("video") or {}
        if vid.get("uri"):
            return vid["uri"], None
        if vid.get("bytesBase64Encoded"):
            return None, base64.b64decode(vid["bytesBase64Encoded"])

    # Alternate SDK/API paths
    gen_vids = response.get("generatedVideos") or response.get("videos") or []
    for item in gen_vids:
        vid = item.get("video") if isinstance(item, dict) and "video" in item else item
        if isinstance(vid, dict):
            if vid.get("uri"):
                return vid["uri"], None
            if vid.get("bytesBase64Encoded"):
                return None, base64.b64decode(vid["bytesBase64Encoded"])

    preds = response.get("predictions") or []
    for pred in preds:
        if isinstance(pred, dict):
            if pred.get("bytesBase64Encoded"):
                return None, base64.b64decode(pred["bytesBase64Encoded"])
            if pred.get("uri"):
                return pred["uri"], None

    return None, None


def generate_ai_video(
    prompt: str,
    api_key: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
    image_mime_type: str = "image/jpeg",
    aspect_ratio: Optional[str] = None,
    duration_seconds: int = 8,
    poll_interval: float = 4.0,
    max_wait_seconds: float = 46.0
) -> Tuple[bool, Optional[bytes], str, str]:
    """
    Generates an AI video (Text-to-Video or Image-to-Video) using Google Veo
    (veo-2.0-generate-001 / veo-3.0-generate-001) in memory (zero disk usage).

    - Starts long-running operation via :predictLongRunning
    - Polls GET /v1beta/{operation_name} every 4 seconds (up to max_wait_seconds inside Vercel 60s budget)
    - Downloads .mp4 directly into memory buffer for Telegram sendVideo
    - Detects missing Billing for Veo and returns clear Khmer instructions.

    Returns: (success, video_bytes_or_None, enhanced_prompt, model_or_error_khmer)
    """
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return False, None, prompt, "❌ មិនទាន់បានកំណត់ GEMINI_API_KEY នៅក្នុងប្រព័ន្ធឡើយ។"

    ratio = aspect_ratio or detect_aspect_ratio(prompt, default="16:9")
    if ratio not in ("16:9", "9:16"):
        ratio = "16:9"
    dur = max(5, min(10, int(duration_seconds)))

    enhanced_prompt = enhance_media_prompt(
        prompt,
        media_type="video",
        api_key=key,
        has_reference_image=bool(image_bytes)
    )

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": key,
    }

    instance_obj: Dict[str, Any] = {"prompt": enhanced_prompt}
    if image_bytes:
        instance_obj["image"] = {
            "bytesBase64Encoded": base64.b64encode(image_bytes).decode("ascii"),
            "mimeType": image_mime_type or "image/jpeg",
        }

    operation_name: Optional[str] = None
    active_model: str = VEO_VIDEO_MODELS[0]
    billing_blocked = False
    last_error = ""

    # 1. Start Veo Long-Running Video Generation Operation
    for model_name in VEO_VIDEO_MODELS:
        url = f"{GEMINI_API_BASE}/models/{model_name}:predictLongRunning?key={key}"
        payload: Dict[str, Any] = {
            "instances": [instance_obj],
            "parameters": {
                "aspectRatio": ratio,
                "durationSeconds": dur,
            },
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15.0)
            # If model caps durationSeconds (e.g. 8s instead of 10s), retry with 8s
            if resp.status_code == 400 and "durationSeconds" in resp.text and dur > 8:
                payload["parameters"]["durationSeconds"] = 8
                resp = requests.post(url, headers=headers, json=payload, timeout=15.0)

            if resp.status_code == 200:
                op_json = resp.json()
                op_name = op_json.get("name")
                if op_name:
                    operation_name = op_name
                    active_model = model_name
                    break
            else:
                if _is_billing_error(resp.status_code, resp.text):
                    billing_blocked = True
                    last_error = f"{model_name}: {resp.status_code}"
                    break
                last_error = f"{model_name}: {resp.status_code}"
                if resp.status_code in (404, 429, 503):
                    continue
        except Exception as e:
            last_error = f"{model_name}: {e}"
            continue

    if billing_blocked:
        return (
            False,
            None,
            enhanced_prompt,
            "⚠️ <b>មិនអាចបង្កើតវីដេអូ AI (Veo) បានទេ — ត្រូវការបើក Billing ជាមុនសិន!</b>\n\n"
            "ម៉ូដែល <b>Google Veo (veo-2.0 / veo-3.0)</b> មិនអាចប្រើលើ Free Tier បានទេ ដោយតម្រូវឱ្យ API Key របស់លោកអ្នកបានបើក "
            "<b>Billing (Pay-as-you-go)</b> នៅក្នុង <b>Google AI Studio</b> ជាមុនសិន។\n\n"
            "📌 <b>វិធីដោះស្រាយ៖</b>\n"
            "១. ចូលទៅកាន់ https://aistudio.google.com/\n"
            "២. ចូលផ្នែក <b>API Keys / Billing</b> រួចភ្ជាប់ Google Cloud Billing Account\n"
            "៣. បន្ទាប់មកសាកល្បងវាយ <code>/video ...</code> ម្ដងទៀត!"
        )

    if not operation_name:
        if "429" in last_error:
            return (
                False,
                None,
                enhanced_prompt,
                "⚠️ <b>Veo API កំពុងជាប់ Quota / Rate Limit</b>\n"
                "សូមរង់ចាំបន្តិច រួចសាកល្បងម្ដងទៀត ឬពិនិត្យ Billing Quota ក្នុង Google AI Studio។"
            )
        return (
            False,
            None,
            enhanced_prompt,
            f"❌ <b>មិនអាចចាប់ផ្ដើមបង្កើតវីដេអូបានទេ</b> ({_clean_no_thai(last_error)})\n"
            "💡 សូមពិនិត្យថា API Key របស់លោកអ្នកបានបើក Billing សម្រាប់ម៉ូដែល Google Veo នៅក្នុង Google AI Studio ហើយឬនៅ។"
        )

    # 2. Poll Operation Status every 4 seconds until done (guarded against Vercel 60s timeout)
    poll_url = (
        operation_name
        if operation_name.startswith("http")
        else f"{GEMINI_API_BASE}/{operation_name.lstrip('/')}?key={key}"
    )
    deadline = time.monotonic() + max_wait_seconds
    finished_data: Optional[Dict[str, Any]] = None

    while time.monotonic() < deadline:
        try:
            poll_resp = requests.get(poll_url, headers={"x-goog-api-key": key}, timeout=10.0)
            if poll_resp.status_code == 200:
                op_data = poll_resp.json()
                if op_data.get("done"):
                    finished_data = op_data
                    break
            elif _is_billing_error(poll_resp.status_code, poll_resp.text):
                return (
                    False,
                    None,
                    enhanced_prompt,
                    "⚠️ <b>ត្រូវការបើក Billing ក្នុង Google AI Studio</b> ដើម្បីដំណើរការបង្កើតវីដេអូ Google Veo។"
                )
        except Exception as e:
            print(f"[media_gen] Veo poll warning: {e}")

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(poll_interval, remaining))

    if not finished_data:
        return (
            False,
            None,
            enhanced_prompt,
            "⏳ <b>វីដេអូកំពុងប្រើពេល Render យូរជាងកំណត់របស់ Vercel (60 វិនាទី)</b>\n"
            "សូមសាកល្បងផ្ញើពាក្យបញ្ជាខ្លីជាងមុន ឬព្យាយាមម្ដងទៀតបន្តិចទៀត។"
        )

    if finished_data.get("error"):
        err_msg = str(finished_data["error"])
        if _is_billing_error(403, err_msg):
            return (
                False,
                None,
                enhanced_prompt,
                "⚠️ <b>ត្រូវការបើក Billing ក្នុង Google AI Studio</b> សម្រាប់ការបង្កើតវីដេអូ Google Veo។"
            )
        return (
            False,
            None,
            enhanced_prompt,
            f"❌ <b>ការ Render វីដេអូមានបញ្ហា៖</b> {_clean_no_thai(err_msg)[:200]}"
        )

    # 3. Extract and download .mp4 directly into memory buffer (zero disk writes)
    video_uri, inline_bytes = _extract_video_uri_or_bytes(finished_data)
    if inline_bytes:
        return True, inline_bytes, enhanced_prompt, active_model

    if not video_uri:
        return (
            False,
            None,
            enhanced_prompt,
            "❌ <b>Veo បាន Render រួចរាល់ តែមិនឃើញឯកសារវីដេអូទេ</b> (អាចជាប់គោលការណ៍សុវត្ថិភាព)។ សូមសាកល្បងពាក្យបញ្ជាផ្សេង។"
        )

    try:
        dl_url = video_uri
        if "key=" not in dl_url and "generativelanguage.googleapis.com" in dl_url:
            sep = "&" if "?" in dl_url else "?"
            dl_url = f"{dl_url}{sep}key={key}"

        dl_resp = requests.get(
            dl_url,
            headers={"x-goog-api-key": key},
            allow_redirects=True,
            timeout=25.0
        )
        if dl_resp.status_code == 200 and dl_resp.content:
            if len(dl_resp.content) > 48 * 1024 * 1024:
                return (
                    False,
                    None,
                    enhanced_prompt,
                    "⚠️ វីដេអូដែលបង្កើតបានមានទំហំធំលើសដែនកំណត់ 50MB របស់ Telegram Bot។"
                )
            return True, dl_resp.content, enhanced_prompt, active_model
        return (
            False,
            None,
            enhanced_prompt,
            f"❌ មិនអាចទាញយកឯកសារវីដេអូ .mp4 ពី Veo បានទេ (HTTP {dl_resp.status_code})។"
        )
    except Exception as e:
        return (
            False,
            None,
            enhanced_prompt,
            f"❌ កំហុសពេលទាញយកវីដេអូ .mp4: {_clean_no_thai(str(e))[:150]}"
        )


def build_cinematic_video_miniapp_html(
    original_prompt: str,
    enhanced_prompt: str,
    scene_urls: List[str],
    aspect_ratio: str = "16:9",
    duration_seconds: int = 10,
    reference_image_b64: Optional[str] = None,
    reference_mime: str = "image/jpeg"
) -> str:
    """
    Builds a self-contained 10-second Cinematic AI Video Player HTML for Telegram Mini App
    (/api/preview/<id>) featuring smooth 60fps Ken Burns Zoom/Pan, crossfade transitions,
    progress timeline, and 1-click free WebM video export via HTML5 Canvas MediaRecorder.
    """
    safe_title = html.escape(_clean_no_thai(original_prompt or "AI Cinematic Video")[:70])
    safe_sub = html.escape((enhanced_prompt or "")[:160])
    sources: List[str] = []
    if reference_image_b64:
        sources.append(f"data:{reference_mime};base64,{reference_image_b64}")
    sources.extend(scene_urls)
    sources = sources[:4]

    is_vertical = aspect_ratio == "9:16"
    cw, ch = (540, 960) if is_vertical else (960, 540)
    sources_json = json.dumps(sources)
    dur_ms = max(5, min(12, int(duration_seconds))) * 1000

    return f"""<!DOCTYPE html>
<html lang="km">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>🎬 {safe_title}</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <script>
    (function(){{try{{if(window.Telegram&&window.Telegram.WebApp){{window.Telegram.WebApp.ready();window.Telegram.WebApp.expand();}}}}catch(e){{}}}})();
  </script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Kantumruy Pro", sans-serif;
      background: radial-gradient(circle at top, #1e293b 0%, #090d16 70%);
      color: #f8fafc;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 14px;
    }}
    .player-shell {{
      width: 100%;
      max-width: {420 if is_vertical else 720}px;
      background: rgba(15, 23, 42, 0.92);
      border: 1px solid rgba(148, 163, 184, 0.22);
      border-radius: 20px;
      overflow: hidden;
      box-shadow: 0 24px 60px rgba(0, 0, 0, 0.65);
    }}
    .stage {{
      position: relative;
      width: 100%;
      aspect-ratio: {'9 / 16' if is_vertical else '16 / 9'};
      background: #020617;
      overflow: hidden;
    }}
    canvas {{
      width: 100%;
      height: 100%;
      display: block;
      object-fit: cover;
    }}
    .badge {{
      position: absolute;
      top: 12px;
      left: 12px;
      background: rgba(15, 23, 42, 0.72);
      backdrop-filter: blur(8px);
      border: 1px solid rgba(56, 189, 248, 0.4);
      color: #38bdf8;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
    }}
    .scene-pill {{
      position: absolute;
      top: 12px;
      right: 12px;
      background: rgba(15, 23, 42, 0.72);
      backdrop-filter: blur(8px);
      color: #e2e8f0;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
    }}
    .loader-overlay {{
      position: absolute;
      inset: 0;
      background: rgba(2, 6, 23, 0.85);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 10px;
      transition: opacity 0.4s ease;
      z-index: 5;
    }}
    .loader-overlay.hidden {{ opacity: 0; pointer-events: none; }}
    .spinner {{
      width: 36px; height: 36px;
      border: 3px solid rgba(56, 189, 248, 0.25);
      border-top-color: #38bdf8;
      border-radius: 50%;
      animation: spin 0.9s linear infinite;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    .controls {{
      padding: 14px 16px 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .title {{ font-size: 16px; font-weight: 700; color: #f8fafc; }}
    .subtitle {{ font-size: 12px; color: #94a3b8; line-height: 1.4; }}
    .progress-wrap {{
      width: 100%;
      height: 6px;
      background: #1e293b;
      border-radius: 999px;
      overflow: hidden;
      cursor: pointer;
    }}
    .progress-bar {{
      width: 0%;
      height: 100%;
      background: linear-gradient(90deg, #38bdf8, #818cf8, #f472b6);
      border-radius: 999px;
    }}
    .btn-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .btn-group {{ display: flex; gap: 8px; }}
    button {{
      border: none;
      border-radius: 10px;
      padding: 9px 14px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: transform 0.15s ease, opacity 0.15s ease;
    }}
    button:active {{ transform: scale(0.96); }}
    .btn-primary {{ background: linear-gradient(135deg, #0ea5e9, #6366f1); color: #fff; }}
    .btn-secondary {{ background: #1e293b; color: #e2e8f0; border: 1px solid #334155; }}
    .btn-download {{ background: linear-gradient(135deg, #10b981, #059669); color: #fff; }}
    .time-label {{ font-size: 12px; color: #cbd5e1; font-variant-numeric: tabular-nums; }}
    .status-note {{ font-size: 12px; color: #38bdf8; min-height: 16px; }}
  </style>
</head>
<body>
  <div class="player-shell">
    <div class="stage">
      <canvas id="vidCanvas" width="{cw}" height="{ch}"></canvas>
      <div class="badge">✨ Free AI 10s Cinematic</div>
      <div class="scene-pill" id="scenePill">ប្លង់ 1 / {len(sources)}</div>
      <div class="loader-overlay" id="loader">
        <div class="spinner"></div>
        <div style="font-size:13px;color:#cbd5e1;">កំពុងផ្ទុកឈុតភាពយន្ត AI ទាំង {len(sources)} ប្លង់...</div>
      </div>
    </div>
    <div class="controls">
      <div class="title">🎬 {safe_title}</div>
      <div class="subtitle">{safe_sub}</div>
      <div class="progress-wrap" id="progressWrap"><div class="progress-bar" id="progressBar"></div></div>
      <div class="btn-row">
        <div class="btn-group">
          <button class="btn-primary" id="playBtn">⏸️ ផ្អាក</button>
          <button class="btn-secondary" id="replayBtn">🔄 លេងម្ដងទៀត</button>
        </div>
        <span class="time-label" id="timeLabel">0.0s / {duration_seconds}.0s</span>
      </div>
      <div class="btn-row">
        <button class="btn-download" id="downloadBtn" style="width:100%;">⬇️ ទាញយកវីដេអូ 10 វិនាទី (Free)</button>
      </div>
      <div class="status-note" id="statusNote"></div>
    </div>
  </div>

  <script>
    const SCENE_URLS = {sources_json};
    const DURATION_MS = {dur_ms};
    const canvas = document.getElementById('vidCanvas');
    const ctx = canvas.getContext('2d');
    const loader = document.getElementById('loader');
    const progressBar = document.getElementById('progressBar');
    const timeLabel = document.getElementById('timeLabel');
    const scenePill = document.getElementById('scenePill');
    const playBtn = document.getElementById('playBtn');
    const replayBtn = document.getElementById('replayBtn');
    const downloadBtn = document.getElementById('downloadBtn');
    const statusNote = document.getElementById('statusNote');

    const loadedImages = [];
    let playing = true;
    let elapsed = 0;
    let lastTs = null;

    // Ken Burns camera motions per scene: [startScale, endScale, startX, endX, startY, endY]
    const MOTIONS = [
      [1.02, 1.16, 0.0, -0.04, 0.0, -0.02],
      [1.14, 1.03, -0.04, 0.04, 0.02, -0.02],
      [1.03, 1.18, 0.03, -0.03, -0.03, 0.03],
      [1.16, 1.04, 0.0, 0.0, 0.03, -0.03]
    ];

    function loadScene(url) {{
      return new Promise((resolve) => {{
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => resolve(img);
        img.onerror = () => {{
          const fallbackImg = new Image();
          fallbackImg.onload = () => resolve(fallbackImg);
          fallbackImg.onerror = () => resolve(null);
          fallbackImg.src = url;
        }};
        img.src = url;
      }});
    }}

    function drawImageCover(img, progress, motionIdx, alpha) {{
      if (!img) return;
      const m = MOTIONS[motionIdx % MOTIONS.length];
      const scale = m[0] + (m[1] - m[0]) * progress;
      const panX = m[2] + (m[3] - m[2]) * progress;
      const panY = m[4] + (m[5] - m[4]) * progress;

      const cw = canvas.width, ch = canvas.height;
      const imgRatio = img.naturalWidth / Math.max(1, img.naturalHeight);
      const canvasRatio = cw / ch;
      let dw, dh;
      if (imgRatio > canvasRatio) {{
        dh = ch * scale;
        dw = dh * imgRatio;
      }} else {{
        dw = cw * scale;
        dh = dw / imgRatio;
      }}
      const dx = (cw - dw) / 2 + panX * cw;
      const dy = (ch - dh) / 2 + panY * ch;

      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.drawImage(img, dx, dy, dw, dh);
      ctx.restore();
    }}

    function renderFrame(ms) {{
      const imgs = loadedImages.filter(Boolean);
      ctx.fillStyle = '#020617';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      if (!imgs.length) return;

      const count = imgs.length;
      const segMs = DURATION_MS / count;
      const idx = Math.min(count - 1, Math.floor(ms / segMs));
      const localP = Math.min(1, (ms - idx * segMs) / segMs);
      const fadeZone = 0.18;

      drawImageCover(imgs[idx], localP, idx, 1.0);
      if (idx + 1 < count && localP > (1 - fadeZone)) {{
        const fadeP = (localP - (1 - fadeZone)) / fadeZone;
        drawImageCover(imgs[idx + 1], fadeP * 0.12, idx + 1, fadeP);
      }}

      // Subtle cinematic vignette
      const grad = ctx.createRadialGradient(
        canvas.width / 2, canvas.height / 2, canvas.width * 0.25,
        canvas.width / 2, canvas.height / 2, canvas.width * 0.72
      );
      grad.addColorStop(0, 'rgba(0,0,0,0)');
      grad.addColorStop(1, 'rgba(0,0,0,0.42)');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      const pct = Math.min(100, (ms / DURATION_MS) * 100);
      progressBar.style.width = pct.toFixed(1) + '%';
      timeLabel.textContent = (ms / 1000).toFixed(1) + 's / ' + (DURATION_MS / 1000).toFixed(1) + 's';
      scenePill.textContent = 'ប្លង់ ' + (idx + 1) + ' / ' + count;
    }}

    function tick(ts) {{
      if (lastTs === null) lastTs = ts;
      const dt = ts - lastTs;
      lastTs = ts;
      if (playing) {{
        elapsed += dt;
        if (elapsed >= DURATION_MS) elapsed = 0;
        renderFrame(elapsed);
      }}
      requestAnimationFrame(tick);
    }}

    playBtn.onclick = () => {{
      playing = !playing;
      playBtn.textContent = playing ? '⏸️ ផ្អាក' : '▶️ លេងបន្ត';
    }};
    replayBtn.onclick = () => {{
      elapsed = 0;
      playing = true;
      playBtn.textContent = '⏸️ ផ្អាក';
    }};
    document.getElementById('progressWrap').onclick = (e) => {{
      const rect = e.currentTarget.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      elapsed = ratio * DURATION_MS;
      renderFrame(elapsed);
    }};

    downloadBtn.onclick = async () => {{
      if (typeof MediaRecorder === 'undefined' || !canvas.captureStream) {{
        statusNote.textContent = '⚠️ កម្មវិធី Browser នេះមិនគាំទ្រការ Record Canvas ដោយផ្ទាល់ទេ។';
        return;
      }}
      try {{
        downloadBtn.disabled = true;
        statusNote.textContent = '🎥 កំពុងថតវីដេអូ 10 វិនាទីជូន សូមរង់ចាំបន្តិច...';
        elapsed = 0;
        playing = true;
        const stream = canvas.captureStream(30);
        const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp9') ? 'video/webm;codecs=vp9' : 'video/webm';
        const recorder = new MediaRecorder(stream, {{ mimeType: mime }});
        const chunks = [];
        recorder.ondataavailable = (ev) => {{ if (ev.data && ev.data.size > 0) chunks.push(ev.data); }};
        recorder.onstop = () => {{
          const blob = new Blob(chunks, {{ type: 'video/webm' }});
          const a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          a.download = 'ai_video_10s.webm';
          a.click();
          statusNote.textContent = '✅ ទាញយកវីដេអូ 10 វិនាទីជោគជ័យ!';
          downloadBtn.disabled = false;
        }};
        recorder.start();
        setTimeout(() => {{ if (recorder.state === 'recording') recorder.stop(); }}, DURATION_MS);
      }} catch (err) {{
        statusNote.textContent = '⚠️ មិនអាចទាញយកដោយផ្ទាល់ក្នុង Mini App បានទេ សូមបើកឯកសារ .html ក្នុង Chrome/Safari។';
        downloadBtn.disabled = false;
      }}
    }};

    Promise.all(SCENE_URLS.map(loadScene)).then((imgs) => {{
      imgs.forEach((im) => {{ if (im) loadedImages.push(im); }});
      loader.classList.add('hidden');
      renderFrame(0);
      requestAnimationFrame(tick);
    }});
  </script>
</body>
</html>"""


def _try_free_hf_video(english_prompt: str, hf_token: str) -> Tuple[Optional[bytes], Optional[str]]:
    """Attempts 100% free video generation via Hugging Face Inference API if HF_TOKEN is configured."""
    if not hf_token:
        return None, None

    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json",
    }
    for model_id in HF_FREE_VIDEO_MODELS:
        for base in (
            f"https://router.huggingface.co/hf-inference/models/{model_id}",
            f"https://api-inference.huggingface.co/models/{model_id}",
        ):
            try:
                resp = requests.post(
                    base,
                    headers=headers,
                    json={"inputs": english_prompt},
                    timeout=(5.0, 24.0)
                )
                ctype = (resp.headers.get("Content-Type") or "").lower()
                if resp.status_code == 200 and ("video" in ctype or resp.content[4:8] == b"ftyp") and len(resp.content) > 4096:
                    return resp.content, f"HuggingFace ({model_id})"
            except Exception as e:
                print(f"[media_gen] HF free video ({model_id}) warning: {e}")
                continue
    return None, None


def _try_pollinations_video(english_prompt: str, duration_seconds: int = 10) -> Tuple[Optional[bytes], Optional[str]]:
    """Attempts free direct video generation via Pollinations video endpoint with short timeout."""
    seed = random.randint(1, 1000000)
    encoded = urllib.parse.quote(english_prompt.strip(), safe="")
    url = f"{POLLINATIONS_VIDEO_BASE}/{encoded}?duration={duration_seconds}&nologo=true&seed={seed}"
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=(4.0, 12.0),
            allow_redirects=True
        )
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if resp.status_code == 200 and ("video" in ctype or resp.content[4:8] == b"ftyp") and len(resp.content) > 4096:
            return resp.content, "Pollinations Video AI (Free)"
    except Exception as e:
        print(f"[media_gen] Pollinations video probe skipped: {e}")
    return None, None


def generate_free_ai_video(
    prompt: str,
    api_key: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
    image_mime_type: str = "image/jpeg",
    aspect_ratio: Optional[str] = None,
    duration_seconds: int = 10
) -> Dict[str, Any]:
    """
    100% Free Unlimited 10-Second AI Video Generator (Zero Paid Billing Required):
    - Auto-enhances Khmer prompt into cinematic English via gemini-2.5-flash.
    - Step 1 (Free AI Video API): Tries Hugging Face Free Inference API (Wan2.1 / LTX-Video if HF_TOKEN
      is set) and Pollinations Video endpoint for direct .mp4 output.
    - Step 2 (100% Free Unlimited Fallback): Generates 4 sequential cinematic AI scenes from
      Pollinations AI and builds a 10-second interactive Cinematic Mini App Player HTML
      (/api/preview/<id>) with Ken Burns Zoom/Pan motion and free browser video download.
    """
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    ratio = aspect_ratio or detect_aspect_ratio(prompt, default="16:9")
    if ratio not in ("16:9", "9:16"):
        ratio = "16:9"
    dur = max(5, min(10, int(duration_seconds)))

    enhanced_prompt = enhance_media_prompt(
        prompt,
        media_type="video",
        api_key=key,
        has_reference_image=bool(image_bytes)
    ) if key else (prompt or "Cinematic breathtaking landscape, realistic lighting, ultra detailed").strip()

    # Step 1a: Hugging Face Free Inference API (if HF_TOKEN is configured and no reference image)
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY") or ""
    if hf_token and not image_bytes:
        hf_bytes, hf_model = _try_free_hf_video(enhanced_prompt, hf_token)
        if hf_bytes:
            return {
                "success": True,
                "mode": "mp4",
                "video_bytes": hf_bytes,
                "enhanced_prompt": enhanced_prompt,
                "model": hf_model,
                "aspect_ratio": ratio,
                "duration_seconds": dur,
            }

    # Step 1b: Pollinations Free Video Endpoint probe (when text-to-video)
    if not image_bytes:
        poll_bytes, poll_model = _try_pollinations_video(enhanced_prompt, duration_seconds=dur)
        if poll_bytes:
            return {
                "success": True,
                "mode": "mp4",
                "video_bytes": poll_bytes,
                "enhanced_prompt": enhanced_prompt,
                "model": poll_model,
                "aspect_ratio": ratio,
                "duration_seconds": dur,
            }

    # Step 2: 100% Free Unlimited Fallback — 4-Scene Cinematic 10s Live Mini App Preview
    w, h = _dimensions_for_aspect_ratio(ratio, video=True)
    base_seed = random.randint(1000, 900000)
    scene_suffixes = [
        "wide establishing cinematic shot, atmospheric golden lighting, ultra detailed",
        "dynamic medium camera angle in smooth motion, rich cinematic lighting, vivid colors",
        "dramatic close-up detail shot, shallow depth of field, photorealistic lighting",
        "epic cinematic finale wide vista, breathtaking lighting, 4k film look",
    ]
    num_pollinations_scenes = 3 if image_bytes else 4
    scene_urls = [
        build_pollinations_image_url(
            f"{enhanced_prompt}, {scene_suffixes[i]}",
            width=w,
            height=h,
            seed=base_seed + i * 17
        )
        for i in range(num_pollinations_scenes)
    ]

    ref_b64 = base64.b64encode(image_bytes).decode("ascii") if image_bytes else None
    miniapp_html = build_cinematic_video_miniapp_html(
        original_prompt=prompt or "វីដេអូ AI 10 វិនាទី",
        enhanced_prompt=enhanced_prompt,
        scene_urls=scene_urls,
        aspect_ratio=ratio,
        duration_seconds=dur,
        reference_image_b64=ref_b64,
        reference_mime=image_mime_type or "image/jpeg",
    )

    return {
        "success": True,
        "mode": "miniapp",
        "miniapp_html": miniapp_html,
        "scene_urls": scene_urls,
        "enhanced_prompt": enhanced_prompt,
        "model": "Pollinations Cinematic 10s (Free Unlimited)",
        "aspect_ratio": ratio,
        "duration_seconds": dur,
    }
