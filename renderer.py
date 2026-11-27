"""
HTML/KaTeX to PNG Image Renderer
Renders rich Khmer academic solutions with KaTeX LaTeX math into crisp, large, full-width PNG images.
Strictly ensures: 1 Exercise = Exactly 1 Complete Image Page (Never truncated or cut off).
"""

import os
import re
import zlib
import base64
import urllib.parse
import requests
from typing import Optional, List

VERCEL_HOST = os.environ.get("VERCEL_HOST", "https://telegram-gemini-study-bot-w6jg.vercel.app")


def encode_solution_payload(markdown_text: str) -> str:
    """Compresses markdown text into a URL-safe base64 string."""
    compressed = zlib.compress(markdown_text.encode("utf-8"))
    return base64.urlsafe_b64encode(compressed).decode("ascii")


def decode_solution_payload(encoded_str: str) -> str:
    """Decodes and decompresses solution text from URL-safe base64 string."""
    try:
        raw = base64.urlsafe_b64decode(encoded_str.encode("ascii"))
        return zlib.decompress(raw).decode("utf-8")
    except Exception:
        return ""


def split_solution_into_cards(markdown_text: str) -> List[str]:
    """
    Splits multi-exercise solutions strictly by exercise boundary.
    Guarantees: 1 Exercise = Exactly 1 Complete Image Page (Never truncated or split in half).
    Each card contains the complete exercise from the title, steps, down to the final answer.
    """
    text = markdown_text.strip()
    if not text:
        return []

    # 1. First split by markdown horizontal rules: ---, ***, ___
    sections = [s.strip() for s in re.split(r'\n\s*[-*_]{3,}\s*\n', text) if s.strip()]

    # 2. If no horizontal rules, check for bold numbered exercise patterns:
    # Matches: **២៥. or **25. or **លំហាត់ទី ២៥ or **លំហាត់ ២៥
    if len(sections) <= 1:
        pattern = r'(?=\n\s*\*\*(?:[០-៩\d]+\s*[\.\:\)]|លំហាត់[ទី\s]*[០-៩\d]+))'
        parts = [p.strip() for p in re.split(pattern, text) if p.strip()]
        if len(parts) > 1:
            sections = parts

    # 3. If still only 1 section, check for markdown headings:
    if len(sections) <= 1:
        pattern = r'(?=\n\s*#{1,3}\s+(?:[០-៩\d]+|លំហាត់))'
        parts = [p.strip() for p in re.split(pattern, text) if p.strip()]
        if len(parts) > 1:
            sections = parts

    return sections if sections else [text]


def get_solution_html(markdown_text: str) -> str:
    """
    Generates high-contrast HTML document with large Kantumruy Pro font,
    crisp KaTeX math, and full-width card layout specifically tailored for mobile screens.
    """
    encoded_b64 = base64.b64encode(markdown_text.encode("utf-8")).decode("ascii")

    return f"""<!DOCTYPE html>
<html lang="km">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ដំណោះស្រាយលំហាត់</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Kantumruy+Pro:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked-katex-extension/lib/index.umd.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #ffffff;
      font-family: 'Kantumruy Pro', -apple-system, BlinkMacSystemFont, sans-serif;
      padding: 16px;
      display: flex;
      justify-content: center;
      align-items: flex-start;
      color: #090d16;
      -webkit-font-smoothing: antialiased;
    }}
    #solution-card {{
      background: #ffffff;
      width: 680px;
      padding: 36px 40px;
      border-radius: 20px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
      border: 1.5px solid #e2e8f0;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: #f0fdf4;
      color: #15803d;
      font-size: 19px;
      font-weight: 700;
      padding: 7px 18px;
      border-radius: 9999px;
      margin-bottom: 22px;
      border: 1.5px solid #86efac;
    }}
    #content-body {{
      font-size: 24px;
      line-height: 1.85;
      color: #0f172a;
      font-weight: 500;
    }}
    #content-body h1, #content-body h2, #content-body h3 {{
      color: #020617;
      margin: 18px 0 12px 0;
      font-size: 27px;
      font-weight: 800;
    }}
    #content-body p {{
      margin-bottom: 12px;
    }}
    #content-body strong {{
      color: #020617;
      font-size: 25px;
      font-weight: 800;
    }}
    #content-body hr {{
      border: none;
      border-top: 2px dashed #cbd5e1;
      margin: 22px 0;
    }}
    #content-body ul, #content-body ol {{
      margin: 10px 0 14px 28px;
    }}
    #content-body li {{
      margin-bottom: 8px;
    }}
    .katex {{
      font-size: 1.35em !important;
    }}
    .katex-display {{
      margin: 18px 0 !important;
      padding: 8px 0;
      font-size: 1.3em !important;
      overflow-x: auto;
      overflow-y: hidden;
    }}
    pre, code {{
      font-family: 'Kantumruy Pro', monospace;
      background: #f8fafc;
      border-radius: 10px;
    }}
    pre {{
      padding: 14px 18px;
      margin: 14px 0;
      border: 1.5px solid #cbd5e1;
      font-size: 21px;
      overflow-x: auto;
    }}
    .footer-watermark {{
      margin-top: 28px;
      padding-top: 14px;
      border-top: 1.5px solid #f1f5f9;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 15px;
      font-weight: 600;
      color: #64748b;
    }}
  </style>
</head>
<body>
  <div id="solution-card">
    <div class="badge">
      <span>✨</span>
      <span>ដំណោះស្រាយលំហាត់ • Telegram Study Bot</span>
    </div>
    <div id="content-body"></div>
    <div class="footer-watermark">
      <span>Bot: @agent123_ai_bot</span>
      <span>Google Gemini AI &amp; KaTeX High-DPI</span>
    </div>
  </div>

  <script>
    document.addEventListener("DOMContentLoaded", function() {{
      try {{
        var b64 = "{encoded_b64}";
        var binStr = atob(b64);
        var bytes = new Uint8Array(binStr.length);
        for (var i = 0; i < binStr.length; i++) {{
          bytes[i] = binStr.charCodeAt(i);
        }}
        var raw = new TextDecoder("utf-8").decode(bytes);

        if (window.markedKatex) {{
          marked.use(markedKatex({{ throwOnError: false, nonStandard: true }}));
        }}
        var contentEl = document.getElementById("content-body");
        contentEl.innerHTML = marked.parse(raw);

        if (window.renderMathInElement) {{
          renderMathInElement(contentEl, {{
            delimiters: [
              {{left: '$$', right: '$$', display: true}},
              {{left: '$', right: '$', display: false}},
              {{left: '\\\\[', right: '\\\\]', display: true}},
              {{left: '\\\\(', right: '\\\\)', display: false}}
            ],
            throwOnError: false
          }});
        }}
      }} catch (e) {{
        console.error("Render error:", e);
      }}
    }});
  </script>
</body>
</html>"""


def render_solution_to_png(markdown_text: str, timeout: int = 25) -> Optional[bytes]:
    """
    Renders solution markdown (Khmer + KaTeX LaTeX) into a high-DPI, full-width PNG image.
    Uses headless Chromium via Microlink API targeting the Vercel solution renderer endpoint.
    """
    try:
        payload = encode_solution_payload(markdown_text)
        solution_url = f"{VERCEL_HOST}/solution?c={payload}"

        microlink_params = {
            "url": solution_url,
            "screenshot": "true",
            "embed": "screenshot.url",
            "element": "#solution-card",
            "viewport.width": "760",
            "viewport.deviceScaleFactor": "2",
            "waitForTimeout": "1000"
        }

        query_string = urllib.parse.urlencode(microlink_params)
        api_url = f"https://api.microlink.io/?{query_string}"

        resp = requests.get(api_url, timeout=timeout)
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/"):
            return resp.content
        print(f"[Renderer Status] {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        print(f"[Renderer Error] {e}")
        return None
