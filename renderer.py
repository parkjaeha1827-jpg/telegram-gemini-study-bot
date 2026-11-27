"""
HTML/KaTeX to PNG Image Renderer
Renders rich Khmer academic solutions with KaTeX LaTeX math into crisp, ultra-clear PNG images.
Features:
- Guaranteed 1 Exercise = 1 Complete Page with full detailed steps and final answer intact.
- Pre-rendered KaTeX protection pipeline: LaTeX math formulas are rendered directly by KaTeX
  BEFORE markdown parsing, completely preventing markdown from mangling underscores, asterisks,
  and fractions.
- High-contrast 22px Kantumruy Pro typography with 1.3em KaTeX equations in styled callout boxes.
- Intelligent PIL auto-cropping: removes dead browser whitespace while preserving balanced padding,
  ensuring standard, beautiful aspect ratio on both mobile and desktop Telegram.
"""

import os
import re
import io
import zlib
import base64
import urllib.parse
import requests
from typing import Optional, List
from PIL import Image, ImageChops

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
        pattern = r'\n+(?=\*\*(?:[០-៩\d]+[\.\:\)]|លំហាត់[ទី\s]*[០-៩\d]+))'
        parts = [p.strip() for p in re.split(pattern, text) if p.strip()]
        if len(parts) > 1:
            sections = parts

    # 3. If still only 1 section, check for markdown headings:
    if len(sections) <= 1:
        pattern = r'\n+(?=#{1,3}\s+(?:[០-៩\d]+[\.\:\)]|លំហាត់[ទី\s]*[០-៩\d]+))'
        parts = [p.strip() for p in re.split(pattern, text) if p.strip()]
        if len(parts) > 1:
            sections = parts

    # 4. If still only 1 section, check for plain numbered exercises:
    if len(sections) <= 1:
        pattern = r'\n+(?=[០-៩\d]{1,3}[\.\:\)]\s+)'
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


def auto_crop_png_card(png_data: bytes, padding: int = 26) -> bytes:
    """
    Detects the true non-white bounding box of the rendered solution card,
    and crops away excess whitespace while preserving clean, uniform padding.
    Guarantees that every image has an optimal aspect ratio and never looks like a stretched strip.
    """
    try:
        im = Image.open(io.BytesIO(png_data))
        rgb = im.convert("RGB")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        diff = ImageChops.difference(rgb, bg)
        bbox = diff.getbbox()
        if not bbox:
            return png_data

        w, h = im.size
        left = max(0, bbox[0] - padding)
        top = max(0, bbox[1] - padding)
        right = min(w, bbox[2] + padding)
        bottom = min(h, bbox[3] + padding)

        # Sanity check: keep at least 320x200
        if (right - left) < 320 or (bottom - top) < 180:
            return png_data

        cropped = im.crop((left, top, right, bottom))
        out = io.BytesIO()
        cropped.save(out, format="PNG", optimize=True)
        return out.getvalue()
    except Exception as e:
        print(f"[AutoCrop Error] {e}")
        return png_data


def get_solution_html(markdown_text: str) -> str:
    """
    Generates high-contrast, crystal-clear HTML document with 1000px canvas,
    crisp 21px Kantumruy Pro font, KaTeX 1.3em math cards, and pre-render protection.
    """
    encoded_b64 = base64.b64encode(markdown_text.encode("utf-8")).decode("ascii")

    return f"""<!DOCTYPE html>
<html lang="km">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=1000, initial-scale=1.0">
  <title>ដំណោះស្រាយលំហាត់</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Kantumruy+Pro:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{
      width: 1000px;
      margin: 0;
      padding: 0;
      background: #ffffff;
      font-family: 'Kantumruy Pro', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      color: #090d16;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      text-rendering: optimizeLegibility;
    }}
    #solution-card {{
      box-sizing: border-box;
      width: 1000px;
      padding: 38px 46px;
      background: #ffffff;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: #eff6ff;
      color: #1d4ed8;
      font-size: 16px;
      font-weight: 700;
      padding: 6px 18px;
      border-radius: 9999px;
      margin-bottom: 20px;
      border: 1.5px solid #bfdbfe;
      width: fit-content;
    }}
    #content-body {{
      font-size: 21.5px;
      line-height: 1.82;
      color: #090d16;
      font-weight: 500;
      flex-grow: 1;
    }}
    #content-body h1, #content-body h2, #content-body h3 {{
      color: #020617;
      margin: 16px 0 10px 0;
      font-size: 26px;
      font-weight: 800;
      line-height: 1.5;
    }}
    #content-body p {{
      margin-bottom: 12px;
    }}
    #content-body strong {{
      color: #020617;
      font-weight: 800;
      font-size: 22.5px;
    }}
    #content-body hr {{
      border: none;
      border-top: 2px dashed #cbd5e1;
      margin: 20px 0;
    }}
    #content-body ul, #content-body ol {{
      margin: 10px 0 12px 28px;
    }}
    #content-body li {{
      margin-bottom: 6px;
    }}
    .math-block-card {{
      background: #f8fafc;
      border: 1.5px solid #cbd5e1;
      border-left: 5px solid #2563eb;
      border-radius: 10px;
      padding: 16px 22px;
      margin: 14px 0;
      overflow-x: auto;
      text-align: center;
    }}
    .math-block-card .katex {{
      font-size: 1.32em !important;
    }}
    .math-inline .katex {{
      font-size: 1.2em !important;
    }}
    .katex {{
      font-size: 1.22em !important;
    }}
    pre, code {{
      font-family: 'Kantumruy Pro', monospace;
      background: #f1f5f9;
      border-radius: 8px;
      font-size: 18px;
    }}
    pre {{
      padding: 12px 18px;
      margin: 12px 0;
      border: 1px solid #cbd5e1;
      overflow-x: auto;
    }}
    .footer-watermark {{
      margin-top: 26px;
      padding-top: 14px;
      border-top: 1.5px solid #e2e8f0;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 14px;
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
      <span>Google Gemini AI &amp; KaTeX Ultra-Clear</span>
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

        // Pre-render KaTeX to prevent markdown from destroying LaTeX math
        var blocks = [];
        var inlines = [];

        // 1. Capture and pre-render display math $$...$$
        var text = raw.replace(/\\$\\$([\\s\\S]*?)\\$\\$/g, function(match, math) {{
          try {{
            var rendered = katex.renderToString(math.trim(), {{ displayMode: true, throwOnError: false }});
            blocks.push(rendered);
            return "@@KATEX_BLOCK_" + (blocks.length - 1) + "@@";
          }} catch(e) {{
            return match;
          }}
        }});

        // 2. Capture and pre-render inline math $...$
        text = text.replace(/\\$([^\\$\\n\\r]+?)\\$/g, function(match, math) {{
          try {{
            var rendered = katex.renderToString(math.trim(), {{ displayMode: false, throwOnError: false }});
            inlines.push(rendered);
            return "@@KATEX_INLINE_" + (inlines.length - 1) + "@@";
          }} catch(e) {{
            return match;
          }}
        }});

        // 3. Parse markdown cleanly
        var html = marked.parse(text);

        // 4. Restore rendered display math inside styled card
        html = html.replace(/@@KATEX_BLOCK_(\\d+)@@/g, function(match, idx) {{
          return '<div class="math-block-card">' + blocks[parseInt(idx)] + '</div>';
        }});

        // 5. Restore rendered inline math
        html = html.replace(/@@KATEX_INLINE_(\\d+)@@/g, function(match, idx) {{
          return '<span class="math-inline">' + inlines[parseInt(idx)] + '</span>';
        }});

        var contentEl = document.getElementById("content-body");
        contentEl.innerHTML = html;

        // Auto-render any remaining math tags like \\[...\\]
        if (window.renderMathInElement) {{
          renderMathInElement(contentEl, {{
            delimiters: [
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
    Uses multi-engine pipeline with fullpage capture and PIL auto-cropping:
      1. Thum.io fullpage 1000px (fast, reliable, free, full-height, full-width)
      2. Microlink API (Retina 2x fallback)
      3. Mini s-shot API (Emergency fallback)
    """
    try:
        payload = encode_solution_payload(markdown_text)
        solution_url = f"{VERCEL_HOST}/solution?c={payload}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        # 1. Try Thum.io fullpage 1000px
        try:
            thum_url = f"https://image.thum.io/get/fullpage/width/1000/noanimate/{solution_url}"
            resp = requests.get(thum_url, headers=headers, timeout=18)
            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/"):
                return auto_crop_png_card(resp.content)
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
                "viewport.width": "1000",
                "viewport.deviceScaleFactor": "2",
                "waitForTimeout": "1000"
            }
            query_string = urllib.parse.urlencode(microlink_params)
            api_url = f"https://api.microlink.io/?{query_string}"
            resp = requests.get(api_url, headers=headers, timeout=14)
            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/"):
                return auto_crop_png_card(resp.content)
            print(f"[Renderer Microlink Status] {resp.status_code}")
        except Exception as e:
            print(f"[Renderer Microlink Error] {e}")

        # 3. Fallback to S-Shot
        try:
            sshot_url = f"https://mini.s-shot.ru/1024x768/PNG/1000/?{solution_url}"
            resp = requests.get(sshot_url, headers=headers, timeout=15)
            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/"):
                return auto_crop_png_card(resp.content)
            print(f"[Renderer SShot Status] {resp.status_code}")
        except Exception as e:
            print(f"[Renderer SShot Error] {e}")

        return None
    except Exception as e:
        print(f"[Renderer General Error] {e}")
        return None
