"""
preview_service.py - Full-Stack App Builder, Live Telegram Mini App Preview & Portable Code Export

Features:
- Detects coding, debugging, web app, game, and calculator creation requests (Khmer & English).
- Extracts single-file HTML and multi-file source code blocks from Gemini responses.
- Injects Telegram Web App SDK (<script src="https://telegram.org/js/telegram-web-app.js"></script>)
  for smooth native Mini App rendering on Telegram mobile & desktop.
- Multi-tier Serverless Storage for /api/preview/<id>:
  1. Vercel KV / Upstash Redis REST API (KV_REST_API_URL & KV_REST_API_TOKEN)
  2. Firebase Firestore REST API (FIREBASE_PROJECT_ID / FIRESTORE_PROJECT_ID)
  3. Local /tmp ephemeral cache (warm Vercel lambdas & local dev)
  4. HMAC-signed Telegram Cloud File fallback (zero-config 100% cold-start persistence)
- Zero-disk in-memory packaging (.html, .py, .js, or .zip via io.BytesIO) for sendDocument.
"""

import os
import re
import io
import hmac
import json
import uuid
import time
import hashlib
import zipfile
import urllib.parse
from typing import Optional, List, Dict, Any, Tuple
import requests

TELEGRAM_API_BASE = "https://api.telegram.org"
DEFAULT_VERCEL_HOST = "https://telegram-gemini-study-bot-w6jg.vercel.app"

# Supported code document extensions that users can upload for fixing/editing
SUPPORTED_CODE_EXTENSIONS = {
    ".html", ".htm", ".css", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".py", ".json", ".sql", ".php", ".java", ".c", ".cpp", ".h", ".cs",
    ".go", ".rs", ".rb", ".sh", ".bat", ".cmd", ".xml", ".yaml", ".yml",
    ".md", ".txt", ".vue", ".svelte", ".dart", ".kt", ".swift"
}

LANG_TO_EXT = {
    "html": ".html",
    "htm": ".html",
    "css": ".css",
    "javascript": ".js",
    "js": ".js",
    "typescript": ".ts",
    "ts": ".ts",
    "jsx": ".jsx",
    "tsx": ".tsx",
    "python": ".py",
    "py": ".py",
    "json": ".json",
    "sql": ".sql",
    "php": ".php",
    "java": ".java",
    "cpp": ".cpp",
    "c++": ".cpp",
    "c": ".c",
    "csharp": ".cs",
    "cs": ".cs",
    "go": ".go",
    "rust": ".rs",
    "rs": ".rs",
    "ruby": ".rb",
    "rb": ".rb",
    "bash": ".sh",
    "sh": ".sh",
    "shell": ".sh",
    "xml": ".xml",
    "yaml": ".yaml",
    "yml": ".yml",
    "vue": ".vue",
    "svelte": ".svelte",
    "dart": ".dart",
    "kotlin": ".kt",
    "swift": ".swift",
    "markdown": ".md",
    "md": ".md",
}

LANG_DEFAULT_NAME = {
    "html": "index.html",
    "css": "style.css",
    "javascript": "script.js",
    "js": "script.js",
    "typescript": "index.ts",
    "ts": "index.ts",
    "python": "main.py",
    "py": "main.py",
    "json": "data.json",
    "sql": "schema.sql",
}

TELEGRAM_WEBAPP_SCRIPT_URL = "https://telegram.org/js/telegram-web-app.js"
TELEGRAM_WEBAPP_SNIPPET = (
    '<script src="https://telegram.org/js/telegram-web-app.js"></script>\n'
    '<script>'
    '(function(){try{if(window.Telegram&&window.Telegram.WebApp){'
    'window.Telegram.WebApp.ready();window.Telegram.WebApp.expand();'
    '}}catch(e){}})();'
    '</script>'
)


def get_public_base_url() -> str:
    """Resolves the HTTPS base URL of the Vercel deployment."""
    explicit = os.environ.get("VERCEL_HOST") or os.environ.get("PUBLIC_BASE_URL")
    if explicit:
        url = explicit.strip().rstrip("/")
        return url if url.startswith("http") else f"https://{url}"

    prod_url = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL")
    if prod_url:
        url = prod_url.strip().rstrip("/")
        return url if url.startswith("http") else f"https://{url}"

    vercel_url = os.environ.get("VERCEL_URL")
    if vercel_url:
        url = vercel_url.strip().rstrip("/")
        return url if url.startswith("http") else f"https://{url}"

    return DEFAULT_VERCEL_HOST


def is_code_or_app_request(text: str) -> bool:
    """
    Detects if the user is asking to build a web app, game, calculator, tool,
    or write/fix/debug programming code.
    """
    if not text:
        return False

    lower = text.lower()

    # Strong Khmer coding/app creation triggers
    khmer_triggers = [
        "បង្កើតគេហទំព័រ", "បង្កើតវេបសាយ", "ធ្វើវេបសាយ", "ធ្វើគេហទំព័រ",
        "បង្កើតកម្មវិធី", "ធ្វើកម្មវិធី", "បង្កើតហ្គេម", "ធ្វើហ្គេម",
        "សរសេរកូដ", "កែកូដ", "ជួសជុលកូដ", "ជួយកែកូដ", "ពិនិត្យកូដ",
        "បង្កើត app", "បង្កើត web", "បង្កើត game", "បង្កើតហ្គេម",
        "កម្មវិធីគណនា", "ម៉ាស៊ីនគិតលេខ", "ប្រព័ន្ធគ្រប់គ្រង", "ទំព័រ web",
        "ទំព័រដើម", "បង្កើត mini app", "preview កម្មវិធី", "កូដ html",
        "កូដ python", "កូដ javascript", "កូដ css", "កូដ js", "បង្កើតតារាងគ្រប់គ្រង"
    ]
    if any(kw in lower for kw in khmer_triggers):
        return True

    # Strong English app/code triggers
    english_patterns = [
        r'\b(?:build|create|make|generate|develop|design)\s+(?:[\w\-]+\s+){0,4}'
        r'(?:web\s*app|website|web\s*page|webpage|mini\s*app|game|calculator|app|application|'
        r'dashboard|landing\s*page|portfolio|to-?do|timer|clock|quiz|form|ui|tool|script|bot)\b',
        r'\b(?:write|fix|debug|refactor|edit|update|improve)\s+(?:[\w\-]+\s+){0,3}'
        r'(?:code|script|html|css|js|javascript|python|function|program|bug|error|app|website)\b',
        r'\bsingle[- ]file\s+html\b',
        r'\bhtml\s*(?:\+|and|,)\s*css\b',
    ]
    for pat in english_patterns:
        if re.search(pat, lower):
            return True

    # User pasted raw code directly
    if "```" in text:
        return True
    if re.search(r'<!doctype\s+html|<html\b|<script\b|<style\b', lower):
        return True
    if re.search(r'^\s*(?:def\s+\w+\(|class\s+\w+[:\(]|function\s+\w+\(|const\s+\w+\s*=|import\s+\w+)', text, re.MULTILINE):
        return True

    return False


def build_app_builder_prompt(
    user_text: str,
    uploaded_filename: Optional[str] = None,
    uploaded_code: Optional[str] = None
) -> str:
    """
    Wraps user's app-building or code-fixing request with clear formatting instructions
    so Gemini returns complete, runnable code with Khmer comments and a single-file HTML preview.
    """
    parts = [user_text.strip() if user_text else "សូមពិនិត្យ និងកែលម្អកូដនេះឱ្យដើរបានល្អប្រសើរ។"]

    if uploaded_filename and uploaded_code:
        parts.append(
            f"\n[ឯកសារកូដដែលអ្នកប្រើប្រាស់បានផ្ញើមក៖ `{uploaded_filename}`]\n"
            f"```\n{uploaded_code[:24000]}\n```"
        )

    parts.append(
        "\n\n[ការណែនាំពិសេសសម្រាប់មុខងារ Full-Stack App Builder & Live Preview]:\n"
        "១. សរសេរកូដពេញលេញ ១០០% ដែលអាចដំណើរការបានពិតប្រាកដភ្លាមៗ (ហាមកាត់កូដ ហាមដាក់ `// ... rest of code` ឬទុកចន្លោះ)។\n"
        "២. បន្ថែម Comment ពន្យល់ជាភាសាខ្មែរត្រឹមត្រូវនៅក្នុងកូដ (ហាមប្រើអក្សរថៃដាច់ខាត)។\n"
        "៣. បើសំណើជាគេហទំព័រ ហ្គេម កម្មវិធីគណនា Dashboard ឧបករណ៍ ឬ UI ណាមួយ៖ "
        "ត្រូវរៀបចំកូដរួមបញ្ចូលគ្នាជា Single-file HTML មួយច្បាប់ពេញលេញក្នុងប្លុក ```html (ចាប់ផ្ដើមពី `<!DOCTYPE html>` "
        "ដោយដាក់ `<style>` និង `<script>` នៅខាងក្នុងតែមួយ) រចនាឱ្យស្អាតទំនើប Responsive ល្អលើទូរស័ព្ទ និង Telegram Mini App។\n"
        "៤. បើអ្នកប្រើប្រាស់ស្នើសុំកូដភាសាផ្សេង (ដូចជា Python, Node.js, SQL...) សូមផ្ដល់កូដពេញលេញក្នុងប្លុកភាសានោះ (ឧ. ```python) "
        "ហើយបើអាចបង្ហាញជា UI Demo បាន សូមបន្ថែមប្លុក ```html សម្រាប់ Preview ផងដែរ។\n"
        "៥. សរសេរការពន្យល់ខ្លីៗជាភាសាខ្មែរនៅខាងលើកូដអំពីមុខងារ និងរបៀបប្រើប្រាស់។"
    )
    return "\n".join(parts)


def _guess_filename(lang: str, code: str, index: int, used_names: set) -> str:
    """Determines a clean filename for an extracted code block."""
    # Check first 3 lines for an explicit filename comment
    first_lines = "\n".join(code.splitlines()[:3])
    m_name = re.search(
        r'(?:file(?:name)?|path)\s*[:=]\s*([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)',
        first_lines,
        re.IGNORECASE
    )
    if m_name:
        candidate = os.path.basename(m_name.group(1).strip())
        if candidate and candidate not in used_names:
            return candidate

    base = LANG_DEFAULT_NAME.get(lang)
    if not base:
        ext = LANG_TO_EXT.get(lang, ".txt")
        base = f"code_{index + 1}{ext}"

    if base not in used_names:
        return base

    stem, ext = os.path.splitext(base)
    counter = 2
    while f"{stem}_{counter}{ext}" in used_names:
        counter += 1
    return f"{stem}_{counter}{ext}"


def extract_code_blocks(response_text: str) -> Tuple[List[Dict[str, str]], str]:
    """
    Extracts all fenced code blocks from Gemini's Markdown response.
    Returns (blocks_list, clean_summary_text).
    Each block dict: {"lang": str, "ext": str, "filename": str, "code": str, "is_html": bool}
    """
    if not response_text:
        return [], ""

    pattern = re.compile(r'```([a-zA-Z0-9_+\-\.]*)[ \t]*\r?\n(.*?)```', re.DOTALL)
    blocks: List[Dict[str, str]] = []
    used_names = set()

    for idx, match in enumerate(pattern.finditer(response_text)):
        raw_lang = (match.group(1) or "").strip().lower()
        code = match.group(2).strip()
        if not code:
            continue

        # Detect HTML even if language tag was omitted
        code_lower = code.lower()
        is_html = (
            raw_lang in ("html", "htm")
            or "<!doctype html" in code_lower
            or ("<html" in code_lower and "</html>" in code_lower)
        )
        lang = "html" if is_html else (raw_lang or "txt")
        ext = LANG_TO_EXT.get(lang, ".txt")
        filename = _guess_filename(lang, code, idx, used_names)
        used_names.add(filename)

        blocks.append({
            "lang": lang,
            "ext": ext,
            "filename": filename,
            "code": code,
            "is_html": is_html,
        })

    # Build a concise summary by stripping out the fenced code blocks
    summary = pattern.sub("", response_text)
    summary = re.sub(r'\n{3,}', '\n\n', summary).strip()
    return blocks, summary


def find_previewable_html(blocks: List[Dict[str, Any]]) -> Optional[str]:
    """
    Returns the best single-file HTML string from extracted blocks for Live Preview.
    If separate HTML + CSS + JS blocks were returned, merges CSS/JS into the HTML automatically!
    """
    if not blocks:
        return None

    html_blocks = [b for b in blocks if b.get("is_html")]
    if not html_blocks:
        return None

    # Prefer the longest/most complete HTML block (likely the single-file full app)
    primary_html = max(html_blocks, key=lambda b: len(b["code"]))["code"]

    # If the model also emitted standalone CSS/JS blocks not already inlined, combine cleanly
    extra_css = [
        b["code"] for b in blocks
        if b.get("lang") == "css" and b["code"][:40] not in primary_html
    ]
    extra_js = [
        b["code"] for b in blocks
        if b.get("lang") in ("js", "javascript") and b["code"][:40] not in primary_html
    ]

    if extra_css:
        css_tag = "<style>\n" + "\n\n".join(extra_css) + "\n</style>"
        if re.search(r'</head>', primary_html, re.IGNORECASE):
            primary_html = re.sub(r'</head>', lambda _: css_tag + "\n</head>", primary_html, count=1, flags=re.IGNORECASE)
        else:
            primary_html = css_tag + "\n" + primary_html

    if extra_js:
        js_tag = "<script>\n" + "\n\n".join(extra_js) + "\n</script>"
        if re.search(r'</body>', primary_html, re.IGNORECASE):
            primary_html = re.sub(r'</body>', lambda _: js_tag + "\n</body>", primary_html, count=1, flags=re.IGNORECASE)
        else:
            primary_html = primary_html + "\n" + js_tag

    return primary_html


def inject_telegram_webapp_script(html_code: str) -> str:
    """
    Ensures the HTML document includes:
    - UTF-8 charset and mobile-friendly viewport
    - <script src="https://telegram.org/js/telegram-web-app.js"></script>
    - Telegram.WebApp.ready() & expand() initialization
    """
    if not html_code:
        return ""

    result = html_code.strip()

    # Wrap HTML fragment into a full document if needed
    if "<html" not in result.lower():
        result = (
            "<!DOCTYPE html>\n"
            "<html lang=\"km\">\n"
            "<head>\n"
            "  <meta charset=\"UTF-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            "  <title>Telegram Mini App Preview</title>\n"
            f"  {TELEGRAM_WEBAPP_SNIPPET}\n"
            "</head>\n"
            "<body>\n"
            f"{result}\n"
            "</body>\n"
            "</html>"
        )
        return result

    # Ensure <head> exists
    if not re.search(r'<head\b', result, re.IGNORECASE):
        result = re.sub(
            r'(<html[^>]*>)',
            r'\1\n<head>\n  <meta charset="UTF-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n</head>',
            result,
            count=1,
            flags=re.IGNORECASE
        )

    # Ensure UTF-8 charset
    if "charset" not in result.lower():
        result = re.sub(
            r'(<head[^>]*>)',
            r'\1\n  <meta charset="UTF-8">',
            result,
            count=1,
            flags=re.IGNORECASE
        )

    # Inject Telegram Web App SDK script if not already present
    if TELEGRAM_WEBAPP_SCRIPT_URL not in result:
        result = re.sub(
            r'</head>',
            lambda _: f"  {TELEGRAM_WEBAPP_SNIPPET}\n</head>",
            result,
            count=1,
            flags=re.IGNORECASE
        )

    return result


def extract_html_title(html_code: str, fallback: str = "Mini App") -> str:
    """Extracts <title> from HTML code if present."""
    if not html_code:
        return fallback
    m = re.search(r'<title[^>]*>(.*?)</title>', html_code, re.IGNORECASE | re.DOTALL)
    if m:
        title = re.sub(r'\s+', ' ', m.group(1)).strip()
        if title:
            return title[:80]
    return fallback


def package_code_export(
    blocks: List[Dict[str, Any]],
    app_id: str,
    preview_html: Optional[str] = None
) -> Tuple[str, bytes, str]:
    """
    Packages extracted code blocks in memory (zero disk writes) for Telegram sendDocument.
    Returns (filename, file_bytes, mime_type).
    - Single HTML app -> <app_id>.html
    - Single non-HTML file -> <filename> (e.g. main.py, script.js)
    - Multi-file project -> <app_id>_project.zip
    """
    if len(blocks) == 1:
        b = blocks[0]
        if b.get("is_html") and preview_html:
            return f"{app_id}.html", preview_html.encode("utf-8"), "text/html"
        fname = b["filename"]
        # Give HTML single files the unique app_id name for easy tracking
        if b.get("is_html"):
            fname = f"{app_id}.html"
        return fname, b["code"].encode("utf-8"), "text/plain"

    # Multi-file project -> package as in-memory .zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        added_names = set()
        if preview_html:
            zf.writestr("index.html", preview_html.encode("utf-8"))
            added_names.add("index.html")

        for b in blocks:
            fname = b["filename"]
            if fname in added_names:
                if b.get("is_html") and preview_html:
                    continue
                stem, ext = os.path.splitext(fname)
                counter = 2
                while f"{stem}_{counter}{ext}" in added_names:
                    counter += 1
                fname = f"{stem}_{counter}{ext}"
            zf.writestr(fname, b["code"].encode("utf-8"))
            added_names.add(fname)

        readme = (
            f"Project ID: {app_id}\n"
            f"Files included: {', '.join(sorted(added_names))}\n\n"
            "Open this folder in VS Code, Antigravity, or any code editor to continue editing.\n"
            "Double-click index.html to preview locally in your browser.\n"
        )
        zf.writestr("README.txt", readme.encode("utf-8"))

    return f"{app_id}_project.zip", buf.getvalue(), "application/zip"


def compute_preview_signature(app_id: str, file_id: str, secret: str) -> str:
    """Computes a short HMAC-SHA256 signature binding app_id and Telegram file_id."""
    key = (secret or "preview_fallback_key").encode("utf-8")
    msg = f"{app_id}:{file_id}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:16]


class PreviewStore:
    """
    Serverless storage for generated HTML Mini Apps.
    Supports:
    1. Vercel KV / Upstash Redis REST API (KV_REST_API_URL & KV_REST_API_TOKEN)
    2. Firebase Firestore REST API (FIREBASE_PROJECT_ID / FIRESTORE_PROJECT_ID)
    3. Local /tmp ephemeral storage (warm lambda & local testing)
    4. HMAC-signed Telegram file_id cloud retrieval (zero-config cold-start fallback)
    """

    def __init__(self, storage_dir: Optional[str] = None):
        if storage_dir:
            self.storage_dir = storage_dir
        elif os.name != "nt":
            self.storage_dir = "/tmp/preview_apps"
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.storage_dir = os.path.join(base_dir, ".preview_cache")

        self.kv_url = (
            os.environ.get("KV_REST_API_URL")
            or os.environ.get("UPSTASH_REDIS_REST_URL")
            or ""
        ).rstrip("/")
        self.kv_token = (
            os.environ.get("KV_REST_API_TOKEN")
            or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
            or ""
        )
        self.firebase_project = (
            os.environ.get("FIREBASE_PROJECT_ID")
            or os.environ.get("FIRESTORE_PROJECT_ID")
            or ""
        ).strip()
        self.firebase_api_key = os.environ.get("FIREBASE_API_KEY", "").strip()
        self._mem_cache: Dict[str, str] = {}

    @staticmethod
    def generate_id() -> str:
        """Generates a unique short preview ID like app_8f2a9c1d."""
        return f"app_{uuid.uuid4().hex[:8]}"

    def _local_path(self, app_id: str) -> str:
        safe_id = re.sub(r'[^a-zA-Z0-9_\-]', '', app_id)
        return os.path.join(self.storage_dir, f"{safe_id}.json")

    def _save_local(self, app_id: str, html_code: str, title: str) -> None:
        self._mem_cache[app_id] = html_code
        try:
            os.makedirs(self.storage_dir, exist_ok=True)
            payload = {"id": app_id, "title": title, "html": html_code, "ts": int(time.time())}
            with open(self._local_path(app_id), "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception as e:
            print(f"[PreviewStore Local Save Warning] {e}")

    def _load_local(self, app_id: str) -> Optional[str]:
        if app_id in self._mem_cache:
            return self._mem_cache[app_id]
        path = self._local_path(app_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    html_val = data.get("html")
                    if html_val:
                        self._mem_cache[app_id] = html_val
                        return html_val
            except Exception as e:
                print(f"[PreviewStore Local Read Warning] {e}")
        return None

    def _save_kv(self, app_id: str, html_code: str, title: str) -> bool:
        if not (self.kv_url and self.kv_token):
            return False
        try:
            payload = json.dumps({"id": app_id, "title": title, "html": html_code, "ts": int(time.time())})
            resp = requests.post(
                f"{self.kv_url}/set/preview_app:{app_id}",
                headers={"Authorization": f"Bearer {self.kv_token}"},
                data=payload.encode("utf-8"),
                timeout=4.0
            )
            return resp.status_code == 200
        except Exception as e:
            print(f"[PreviewStore KV Write Warning] {e}")
            return False

    def _load_kv(self, app_id: str) -> Optional[str]:
        if not (self.kv_url and self.kv_token):
            return None
        try:
            resp = requests.get(
                f"{self.kv_url}/get/preview_app:{app_id}",
                headers={"Authorization": f"Bearer {self.kv_token}"},
                timeout=4.0
            )
            if resp.status_code == 200:
                val = resp.json().get("result")
                if val:
                    parsed = json.loads(val) if isinstance(val, str) else val
                    if isinstance(parsed, dict) and parsed.get("html"):
                        return parsed["html"]
                    if isinstance(parsed, str) and "<" in parsed:
                        return parsed
        except Exception as e:
            print(f"[PreviewStore KV Read Warning] {e}")
        return None

    def _save_firestore(self, app_id: str, html_code: str, title: str) -> bool:
        if not self.firebase_project:
            return False
        try:
            url = (
                f"https://firestore.googleapis.com/v1/projects/{self.firebase_project}"
                f"/databases/(default)/documents/previews/{app_id}"
            )
            if self.firebase_api_key:
                url += f"?key={urllib.parse.quote(self.firebase_api_key)}"

            body = {
                "fields": {
                    "id": {"stringValue": app_id},
                    "title": {"stringValue": title},
                    "html": {"stringValue": html_code},
                    "ts": {"integerValue": str(int(time.time()))}
                }
            }
            resp = requests.patch(url, json=body, timeout=4.0)
            return resp.status_code in (200, 201)
        except Exception as e:
            print(f"[PreviewStore Firestore Write Warning] {e}")
            return False

    def _load_firestore(self, app_id: str) -> Optional[str]:
        if not self.firebase_project:
            return None
        try:
            url = (
                f"https://firestore.googleapis.com/v1/projects/{self.firebase_project}"
                f"/databases/(default)/documents/previews/{app_id}"
            )
            if self.firebase_api_key:
                url += f"?key={urllib.parse.quote(self.firebase_api_key)}"

            resp = requests.get(url, timeout=4.0)
            if resp.status_code == 200:
                fields = resp.json().get("fields", {})
                html_val = fields.get("html", {}).get("stringValue")
                if html_val:
                    return html_val
        except Exception as e:
            print(f"[PreviewStore Firestore Read Warning] {e}")
        return None

    def _load_from_telegram_cloud(self, app_id: str, file_id: str, sig: str, bot_token: str) -> Optional[str]:
        """Retrieves preview HTML from an HMAC-signed Telegram document file_id."""
        if not (file_id and sig and bot_token):
            return None
        expected = compute_preview_signature(app_id, file_id, bot_token)
        if not hmac.compare_digest(expected, sig):
            return None

        try:
            base_url = f"{TELEGRAM_API_BASE}/bot{bot_token}"
            file_url = f"{TELEGRAM_API_BASE}/file/bot{bot_token}"
            resp = requests.get(f"{base_url}/getFile", params={"file_id": file_id}, timeout=8)
            if resp.status_code != 200:
                return None
            file_path = resp.json().get("result", {}).get("file_path")
            if not file_path:
                return None

            raw_resp = requests.get(f"{file_url}/{file_path}", timeout=15)
            if raw_resp.status_code != 200:
                return None

            raw_bytes = raw_resp.content
            # If the uploaded document was a ZIP archive, extract index.html or first .html file
            if file_path.lower().endswith(".zip") or raw_bytes[:2] == b"PK":
                with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as zf:
                    names = zf.namelist()
                    target = "index.html" if "index.html" in names else next(
                        (n for n in names if n.lower().endswith(".html") or n.lower().endswith(".htm")),
                        None
                    )
                    if target:
                        return zf.read(target).decode("utf-8", errors="replace")
                return None

            return raw_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            print(f"[PreviewStore Telegram Cloud Read Warning] {e}")
            return None

    def save_preview(self, app_id: str, html_code: str, title: str = "Mini App") -> Tuple[bool, str]:
        """
        Saves the HTML app (with Telegram Web App SDK injected) to all configured backends.
        Returns (stored_in_remote_db, backend_label).
        """
        ready_html = inject_telegram_webapp_script(html_code)
        self._save_local(app_id, ready_html, title)

        if self._save_kv(app_id, ready_html, title):
            return True, "vercel_kv"
        if self._save_firestore(app_id, ready_html, title):
            return True, "firestore"
        return False, "local"

    def get_preview(
        self,
        app_id: str,
        file_id: Optional[str] = None,
        sig: Optional[str] = None,
        bot_token: Optional[str] = None
    ) -> Optional[str]:
        """Retrieves preview HTML by ID from local cache, Vercel KV, Firestore, or signed Telegram cloud."""
        if not app_id or not re.match(r'^[a-zA-Z0-9_\-]{3,64}$', app_id):
            return None

        # 1. Warm local cache
        html_code = self._load_local(app_id)
        if html_code:
            return inject_telegram_webapp_script(html_code)

        # 2. Vercel KV / Upstash Redis
        html_code = self._load_kv(app_id)
        if html_code:
            self._save_local(app_id, html_code, app_id)
            return inject_telegram_webapp_script(html_code)

        # 3. Firebase Firestore
        html_code = self._load_firestore(app_id)
        if html_code:
            self._save_local(app_id, html_code, app_id)
            return inject_telegram_webapp_script(html_code)

        # 4. Signed Telegram Cloud fallback
        token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if file_id and sig and token:
            html_code = self._load_from_telegram_cloud(app_id, file_id, sig, token)
            if html_code:
                self._save_local(app_id, html_code, app_id)
                return inject_telegram_webapp_script(html_code)

        return None

    def build_preview_url(
        self,
        app_id: str,
        file_id: Optional[str] = None,
        stored_remotely: bool = False,
        bot_token: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> str:
        """Builds the HTTPS URL for Telegram Inline Keyboard web_app button."""
        root = (base_url or get_public_base_url()).rstrip("/")
        url = f"{root}/api/preview/{urllib.parse.quote(app_id)}"
        if not stored_remotely and file_id:
            token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
            sig = compute_preview_signature(app_id, file_id, token)
            query = urllib.parse.urlencode({"fid": file_id, "sig": sig})
            url = f"{url}?{query}"
        return url


def render_preview_not_found_html(app_id: str) -> str:
    """Renders a clean Khmer/English 404 Mini App page when a preview ID is not found."""
    safe_id = re.sub(r'[^a-zA-Z0-9_\-]', '', app_id or "unknown")
    return f"""<!DOCTYPE html>
<html lang="km">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Preview Not Found</title>
  {TELEGRAM_WEBAPP_SNIPPET}
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0f172a;
      color: #f8fafc;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
      padding: 24px;
      box-sizing: border-box;
      text-align: center;
    }}
    .card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 16px;
      padding: 28px 24px;
      max-width: 420px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.4);
    }}
    h1 {{ font-size: 20px; margin: 0 0 12px; color: #38bdf8; }}
    p {{ font-size: 14px; line-height: 1.6; color: #cbd5e1; margin: 0; }}
    code {{ background: #0f172a; padding: 2px 6px; border-radius: 6px; color: #fbbf24; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>រកមិនឃើញទំព័រ Preview ទេ</h1>
    <p>លេខសម្គាល់កម្មវិធី <code>{safe_id}</code> អាចផុតកំណត់ ឬមិនមានក្នុងប្រព័ន្ធ។ សូមត្រឡប់ទៅ Telegram Bot ហើយស្នើសុំបង្កើតកម្មវិធីម្ដងទៀត ឬបើកឯកសារកូដដែល Bot បានផ្ញើជូន។</p>
  </div>
</body>
</html>"""
