"""
HTML/KaTeX to PNG Image Renderer
Renders rich Khmer academic solutions with KaTeX LaTeX math into crisp PNG images.
"""

import os
import zlib
import base64
import urllib.parse
import requests
from typing import Optional

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


def get_solution_html(markdown_text: str) -> str:
    """Generates the full HTML document with Kantumruy Pro font, KaTeX, and Marked."""
    encoded_b64 = base64.b64encode(markdown_text.encode("utf-8")).decode("ascii")

    return f"""<!DOCTYPE html>
<html lang="km">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ដំណោះស្រាយលំហាត់</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Kantumruy+Pro:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap" rel="stylesheet">
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
      color: #0f172a;
      -webkit-font-smoothing: antialiased;
    }}
    #solution-card {{
      background: #ffffff;
      width: 720px;
      padding: 32px 36px;
      border-radius: 16px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
      border: 1px solid #e2e8f0;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: #f0fdf4;
      color: #166534;
      font-size: 13.5px;
      font-weight: 600;
      padding: 5px 14px;
      border-radius: 9999px;
      margin-bottom: 20px;
      border: 1px solid #bbf7d0;
    }}
    #content-body {{
      font-size: 16.5px;
      line-height: 1.8;
      color: #1e293b;
    }}
    #content-body h1, #content-body h2, #content-body h3 {{
      color: #0f172a;
      margin: 16px 0 10px 0;
      font-weight: 700;
    }}
    #content-body p {{
      margin-bottom: 10px;
    }}
    #content-body strong {{
      color: #0f172a;
      font-weight: 700;
    }}
    #content-body hr {{
      border: none;
      border-top: 1px dashed #cbd5e1;
      margin: 20px 0;
    }}
    #content-body ul, #content-body ol {{
      margin: 8px 0 12px 24px;
    }}
    #content-body li {{
      margin-bottom: 6px;
    }}
    .katex {{
      font-size: 1.15em !important;
    }}
    .katex-display {{
      margin: 12px 0 !important;
      padding: 4px 0;
      overflow-x: auto;
      overflow-y: hidden;
    }}
    pre, code {{
      font-family: 'Kantumruy Pro', monospace;
      background: #f8fafc;
      border-radius: 8px;
    }}
    pre {{
      padding: 12px 16px;
      margin: 10px 0;
      border: 1px solid #e2e8f0;
      overflow-x: auto;
    }}
    .footer-watermark {{
      margin-top: 24px;
      padding-top: 12px;
      border-top: 1px solid #f1f5f9;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 12px;
      color: #94a3b8;
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
    Renders solution markdown (Khmer + KaTeX LaTeX) into a high-DPI PNG image.
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
            "viewport.width": "800",
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
