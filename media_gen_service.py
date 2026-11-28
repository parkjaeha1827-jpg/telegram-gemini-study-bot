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
import base64
from typing import Optional, Tuple, Dict, Any
import requests

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

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


def generate_ai_image(
    prompt: str,
    api_key: Optional[str] = None,
    aspect_ratio: Optional[str] = None
) -> Tuple[bool, Optional[bytes], str, str]:
    """
    Generates an AI image in memory (zero disk usage) using:
    1. gemini-2.5-flash-image (generateContent with responseModalities: ["TEXT", "IMAGE"])
    2. Fallback: imagen-3.0-generate-002 / imagen-4.0-generate-001 (:predict)

    Returns: (success, image_bytes_or_None, enhanced_prompt, info_or_error_khmer)
    """
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return False, None, prompt, "❌ មិនទាន់បានកំណត់ GEMINI_API_KEY នៅក្នុងប្រព័ន្ធឡើយ។"

    ratio = aspect_ratio or detect_aspect_ratio(prompt, default="1:1")
    enhanced_prompt = enhance_media_prompt(prompt, media_type="image", api_key=key)

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": key,
    }
    last_error = ""
    billing_blocked = False

    # 1. Primary: Gemini Native Image Generation (gemini-2.5-flash-image)
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
