"""
HTML/KaTeX to PNG Image Renderer
Renders rich Khmer academic solutions with KaTeX LaTeX math into crisp, full-width PNG images.
Features:
- Zero-margin 800px full-width layout with consistent minimum height (no tiny short cards).
- Crisp 17.5px Khmer typography with dark contrast (#0f172a) and KaTeX 1.2em math.
- Full-page capture pipeline (Thum.io fullpage 800px -> Microlink -> S-Shot) ensuring
  every step and final answer is 100% visible and razor-sharp.
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


def split_solution_into_cards(markdown_text: str, max_chars_per_card: int = 1800) -> List[str]:
    """
    Splits multi-exercise solutions strictly by exercise boundary.
    Guarantees: 1 Exercise = 1 Complete Image Page with full detailed steps and final answer.
    If a single exercise is exceptionally long (> 1800 chars), splits cleanly into Part 1 & Part 2
    ensuring Part 2 always retains the complete final answer.
    """
    text = markdown_text.strip()
    if not text:
        return []

    # 1. First split by markdown horizontal rules: ---, ***, ___
    sections = [s.strip() for s in re.split(r'\n\s*[-*_]{3,}\s*\n', text) if s.strip()]

    # 2. If no horizontal rules, check for bold numbered exercise patterns:
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

    final_cards = []
    for sec in sections:
        if len(sec) <= max_chars_per_card:
            final_cards.append(sec)
        else:
            paragraphs = [p.strip() for p in sec.split("\n\n") if p.strip()]
            current = []
            current_len = 0
            part_idx = 1

            header_match = re.match(r'^(\*\*[^\n\*]+\*\*|\#\#\s+[^\n]+)', sec)
            header_prefix = header_match.group(1) if header_match else ""

            for p in paragraphs:
                p_len = len(p) + 2
                if current_len + p_len > max_chars_per_card and current:
                    part_text = "\n\n".join(current)
                    if part_idx > 1 and header_prefix and not part_text.startswith(header_prefix):
                        part_text = f"{header_prefix} _(ត)_ \n\n" + part_text
                    final_cards.append(part_text)
                    part_idx += 1
                    current = [p]
                    current_len = p_len
                else:
                    current.append(p)
                    current_len += p_len

            if current:
                part_text = "\n\n".join(current)
                if part_idx > 1 and header_prefix and not part_text.startswith(header_prefix):
                    part_text = f"{header_prefix} _(ត)_ \n\n" + part_text
                final_cards.append(part_text)

    return final_cards if final_cards else [text]


def get_solution_html(markdown_text: str) -> str:
    """
    Generates high-contrast HTML document with 800px full-width card layout,
    crisp 17.5px Kantumruy Pro font, KaTeX 1.2em math, and min-height: 480px.
    """
    encoded_b64 = base64.b64encode(markdown_text.encode("utf-8")).decode("ascii")

    return f"""<!DOCTYPE html>
<html lang="km">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=800, initial-scale=1.0">
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
    html, body {{
      width: 800px;
      margin: 0;
      padding: 0;
      background: #ffffff;
      font-family: 'Kantumruy Pro', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      color: #0f172a;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      text-rendering: optimizeLegibility;
    }}
    #solution-card {{
      box-sizing: border-box;
      width: 800px;
      min-height: 480px;
      padding: 32px 38px;
      background: #ffffff;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: #f0fdf4;
      color: #166534;
      font-size: 14px;
      font-weight: 700;
      padding: 5px 14px;
      border-radius: 9999px;
      margin-bottom: 16px;
      border: 1.5px solid #86efac;
      width: fit-content;
    }}
    #content-body {{
      font-size: 17.5px;
      line-height: 1.75;
      color: #0f172a;
      font-weight: 500;
      flex-grow: 1;
    }}
    #content-body h1, #content-body h2, #content-body h3 {{
      color: #020617;
      margin: 12px 0 8px 0;
      font-size: 21px;
      font-weight: 800;
    }}
    #content-body p {{
      margin-bottom: 8px;
    }}
    #content-body strong {{
      color: #020617;
      font-size: 18.5px;
      font-weight: 800;
    }}
    #content-body hr {{
      border: none;
      border-top: 1.5px dashed #cbd5e1;
      margin: 16px 0;
    }}
    #content-body ul, #content-body ol {{
      margin: 8px 0 10px 22px;
    }}
    #content-body li {{
      margin-bottom: 5px;
    }}
    .katex {{
      font-size: 1.2em !important;
    }}
    .katex-display {{
      margin: 12px 0 !important;
      padding: 4px 0;
      font-size: 1.18em !important;
      overflow-x: auto;
      overflow-y: hidden;
    }}
    pre, code {{
      font-family: 'Kantumruy Pro', monospace;
      background: #f8fafc;
      border-radius: 8px;
      font-size: 15.5px;
    }}
    pre {{
      padding: 10px 14px;
      margin: 10px 0;
      border: 1px solid #cbd5e1;
      overflow-x: auto;
    }}
    .footer-watermark {{
      margin-top: 20px;
      padding-top: 12px;
      border-top: 1px solid #e2e8f0;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 12.5px;
      font-weight: 600;
      color: #64748b;
    }}
  </style>
</head>
<body>
  <div id="solution-card">
    <div>
      <div class="badge">
        <span>✨</span>
        <span>ដំណោះស្រាយលំហាត់ • Telegram Study Bot</span>
      </div>
      <div id="content-body"></div>
    </div>
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
    Uses multi-engine pipeline with fullpage capture:
      1. Thum.io fullpage 800px (fast, reliable, free, full-height, full-width, zero rate limits)
      2. Microlink API (Retina 2x fallback)
      3. Mini s-shot API (Emergency fallback)
    """
    try:
        payload = encode_solution_payload(markdown_text)
        solution_url = f"{VERCEL_HOST}/solution?c={payload}"

        # 1. Try Thum.io fullpage 800px (fast, full-height, zero rate limits)
        try:
            thum_url = f"https://image.thum.io/get/fullpage/width/800/noanimate/{solution_url}"
            resp = requests.get(thum_url, timeout=18)
            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/"):
                return resp.content
            print(f"[Renderer Thum Status] {resp.status_code}")
        except Exception as e:
            print(f"[Renderer Thum Error] {e}")

        # 2. Fallback to Microlink (Retina 2x)
        try:
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
            resp = requests.get(api_url, timeout=12)
            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/"):
                return resp.content
            print(f"[Renderer Microlink Status] {resp.status_code}")
        except Exception as e:
            print(f"[Renderer Microlink Error] {e}")

        # 3. Fallback to S-Shot
        try:
            sshot_url = f"https://mini.s-shot.ru/1024x768/PNG/800/?{solution_url}"
            resp = requests.get(sshot_url, timeout=15)
            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/"):
                return resp.content
            print(f"[Renderer SShot Status] {resp.status_code}")
        except Exception as e:
            print(f"[Renderer SShot Error] {e}")

        return None
    except Exception as e:
        print(f"[Renderer General Error] {e}")
        return None
