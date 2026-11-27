"""
Gemini Homework Solver Engine
Uses Google Gemini API to solve academic exercises across all subjects.
Formats all equations in clean, textbook-quality math specifically optimized for Telegram.
All vertical fractions and multi-line equations are enclosed in Monospace code blocks (```)
to guarantee perfect alignment on all mobile devices.
"""

import os
import re
import json
import base64
import requests
from typing import Optional, Tuple, List

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

SYSTEM_INSTRUCTION = """
អ្នកជាគ្រូជំនួយដោះស្រាយលំហាត់គ្រប់មុខវិជ្ជា (គណិតវិទ្យា, រូបវិទ្យា, គីមីវិទ្យា, ជីវវិទ្យា, អក្សរសាស្ត្រខ្មែរ, អង់គ្លេស, ប្រវត្តិ, ភូមិ...)។

ច្បាប់ដាច់ខាតក្នុងការបង្ហាញរូបមន្ត និងប្រភាគសម្រាប់ Telegram (TELEGRAM CLEAN MATH RULES):
១. ហាមប្រើ LaTeX commands (ដូចជា \\frac, \\sqrt, \\int, \\lim, $, $$) ជាដាច់ខាត ព្រោះ Telegram មិនគាំទ្រ LaTeX ឡើយ។
២. ច្បាប់ដាច់ខាតសម្រាប់ប្រភាគ (VERTICAL FRACTIONS):
   - ហាមដាច់ខាតកុំប្រើសញ្ញា / សម្រាប់ប្រភាគ (ដូចជា a/b ឬ (a)/(b))។
   - ត្រូវសរសេរជាទម្រង់ប្រភាគឈរពិតប្រាកដ មានភាគយកនៅខាងលើ របារប្រភាគ ─── នៅកណ្តាល និងភាគបែងនៅខាងក្រោម។
   - រាល់ប្រភាគឈរ និងសមីការគណនាជាជួរ ត្រូវតែដាក់ក្នុងប្រអប់ Code block (```) ជានិច្ច ដើម្បីកុំឱ្យខូចជួរលើទូរស័ព្ទដៃ Telegram!
   - ឧទាហរណ៍ជាក់ស្តែង៖
     ○ **ក)**
     ```
     12q - 95 = 12(25) - 95 = 300 - 95 = 205
     ```
     ○ **ខ)**
     ```
     35 - q     35 - 25     10
     ──────  =  ───────  =  ──  =  2
       5           5         5
     ```
     ○ **គ)**
     ```
     12q         12(25)
     ─── + 30 =  ────── + 30 = 75 + 30 = 105
      4            4
     ```
     ○ **ឃ)**
     ```
     15q + 75     15(25) + 75     375 + 75     450
     ────────  =  ───────────  =  ────────  =  ───  =  15
        30             30            30         30
     ```

៣. សម្រាប់លំហាត់អាំងតេក្រាល លីមីត ឬដេរីវេ (CALCULUS & ALGEBRA):
   - ដាក់រូបមន្ត និងជំហានគណនាទាំងអស់ក្នុងប្រអប់ Code block (```) មួយៗយ៉ាងស្អាត។
   - ហាមគូរតង្កៀបកម្ពស់ច្រើនជួរ (ដូចជា    ឬ ┌ │ └) ព្រោះវានឹងរត់ខុសជួរលើទូរស័ព្ទដៃ។ ត្រូវប្រើតង្កៀប [ ... ] ឬ ( ... ) ធម្មតា។
   - ឧទាហរណ៍ជាក់ស្តែង៖
     **លំហាត់ទី ២៥**
     គណនាអាំងតេក្រាល I = ∫[0 → π/4] sin²(x) dx

     **ដំណោះស្រាយ៖**
     តាមរូបមន្តបន្ថយដឺក្រេ៖
     ```
               1 - cos 2x
     sin²(x) = ──────────
                   2
     ```
     នាំឱ្យ៖
     ```
           π/4  1 - cos 2x
     I = ∫     ──────────── dx
           0        2

         1   π/4
       = ─ ∫     (1 - cos 2x) dx
         2   0

         1 [        sin 2x ] π/4
       = ─ [ x  -   ────── ]
         2 [          2    ] 0
     ```
     ជំនួសព្រំដែន [0 → π/4]៖
     ```
         1 [ ( π      sin(2 × π/4) )   (      sin 0 ) ]
       = ─ [ ( ─  -   ──────────── ) - ( 0  - ───── ) ]
         2 [ ( 4           2       )   (        2   ) ]

         1 [ ( π      sin(π/2) ) ]
       = ─ [ ( ─  -   ──────── ) ]
         2 [ ( 4         2     ) ]

         1 [ π   1 ]
       = ─ [ ─ - ─ ]
         2 [ 4   2 ]

         1 [ π - 2 ]
       = ─ [ ───── ]
         2 [   4   ]

         π - 2
       = ─────
           8
     ```
     👉 **ដូចនេះ៖**
     ```
         π - 2
     I = ─────
           8
     ```

៤. ទម្រង់លំហាត់ស្តង់ដារ៖
   - ក្បាលលំហាត់ «**លំហាត់ទី ...**»
   - ចំណុចរង «○ **ក)** », «○ **ខ)** » ...
   - អត្ថបទពន្យល់ និងចំណងជើងជាភាសាខ្មែរធម្មតា នៅក្រៅប្រអប់ Code block ដើម្បីងាយស្រួលអាន។
   - ហាមប្រើពាក្យស្វាគមន៍នាំមុខ («សួស្តី...») ចូលដោះស្រាយភ្លាមៗ។
""".strip()


def sanitize_brackets_and_symbols(text: str) -> str:
    """Replaces broken multi-line bracket art characters with clean standard brackets."""
    bad_chars = {
        "": "(", "": " ", "": ")",
        "⎛": "(", "⎜": " ", "⎝": ")",
        "⎞": ")", "⎟": " ", "⎠": ")",
        "┌": "[", "┐": "]", "└": "[", "┘": "]",
        "│": " ", "┃": " ", "║": " "
    }
    for k, v in bad_chars.items():
        text = text.replace(k, v)
    return text


def wrap_orphan_fraction_blocks(text: str) -> str:
    """
    Ensures any vertical fraction lines (containing ───) outside of code blocks
    are properly wrapped in ``` code blocks so Telegram renders them in monospace.
    """
    if "───" not in text and "───" not in text:
        return text

    parts = text.split("```")
    for idx in range(len(parts)):
        # Even indices are outside code blocks
        if idx % 2 == 0:
            lines = parts[idx].split("\n")
            new_lines = []
            j = 0
            while j < len(lines):
                line = lines[j]
                if "───" in line or "───" in line:
                    # Gather block: 1-2 lines before, current line, 1-2 lines after
                    block = []
                    # Previous non-header line as numerator/expression
                    if new_lines and new_lines[-1].strip() and not any(k in new_lines[-1] for k in ["លំហាត់", "ដំណោះស្រាយ", "○", "👉", "**"]):
                        block.append(new_lines.pop())
                    block.append(line)
                    # Next line as denominator
                    if j + 1 < len(lines) and lines[j+1].strip() and not any(k in lines[j+1] for k in ["លំហាត់", "ដំណោះស្រាយ", "○", "👉", "**"]):
                        block.append(lines[j+1])
                        j += 1
                    new_lines.append("```\n" + "\n".join(block) + "\n```")
                else:
                    new_lines.append(line)
                j += 1
            parts[idx] = "\n".join(new_lines)

    return "```".join(parts)


def format_math_telegram(text: str) -> str:
    """
    Sanitizes any remaining raw LaTeX math expressions into clean Unicode math for Telegram.
    Enforces clean vertical fractions in monospace blocks, eliminating broken proportional-font ASCII art.
    """
    if not text:
        return ""

    # 1. Clean multi-line bracket art
    text = sanitize_brackets_and_symbols(text)

    # 2. Remove $ and $$ delimiters
    text = text.replace("$$", "").replace("$", "")

    # 3. Fixed string replacements for LaTeX
    string_replacements = [
        ("\\left(", "("), ("\\right)", ")"),
        ("\\left[", "["), ("\\right]", "]"),
        ("\\left{", "{"), ("\\right}", "}"),
        ("\\left|", "|"), ("\\right|", "|"),
        ("\\left\\|", "|"), ("\\right\\|", "|"),
        ("\\left.", ""), ("\\right.", ""),
        ("\\to", "→"), ("\\infty", "∞"),
        ("\\times", "×"), ("\\div", "÷"),
        ("\\pm", "±"), ("\\mp", "∓"),
        ("\\neq", "≠"), ("\\leq", "≤"), ("\\geq", "≥"),
        ("\\approx", "≈"), ("\\sim", "~"),
        ("\\cdot", "·"),
        ("\\Rightarrow", "⇒"), ("\\Leftarrow", "⇐"), ("\\Leftrightarrow", "⇔"),
        ("\\pi", "π"), ("\\theta", "θ"), ("\\alpha", "α"), ("\\beta", "β"),
        ("\\gamma", "γ"), ("\\Delta", "Δ"), ("\\delta", "δ"),
        ("\\sin", "sin"), ("\\cos", "cos"), ("\\tan", "tan"), ("\\cot", "cot"),
        ("\\arcsin", "arcsin"), ("\\arccos", "arccos"), ("\\arctan", "arctan"),
        ("\\quad", " "), ("\\qquad", "  "), ("\\,", " "), ("\\;", " "), ("\\!", "")
    ]
    for s_from, s_to in string_replacements:
        text = text.replace(s_from, s_to)

    subs = {"0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉"}
    sups = {
        "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
        "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
        "n": "ⁿ", "x": "ˣ", "+": "⁺", "-": "⁻", "y": "ʸ"
    }

    # Logarithms: \log_3 or \log3
    text = re.sub(r"\\log_?\{?(\d+)\}?", lambda m: "log" + "".join(subs.get(c, c) for c in m.group(1)), text)
    text = re.sub(r"\\ln", "ln", text)
    text = re.sub(r"\\log", "log", text)

    # Fractions: \frac{A}{B} -> Vertical fraction wrapped in code block
    def to_vert_fraction(m):
        num = m.group(1).strip()
        den = m.group(2).strip()
        width = max(len(num), len(den)) + 2
        bar = "─" * width
        return f"\n```\n{num.center(width)}\n{bar}\n{den.center(width)}\n```\n"

    for _ in range(5):
        text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", to_vert_fraction, text)

    # Square roots: \sqrt{...} -> √(...)
    for _ in range(5):
        text = re.sub(r"\\sqrt\{([a-zA-Z0-9]+)\}", r"√\1", text)
        text = re.sub(r"\\sqrt\{([^{}]+)\}", r"√(\1)", text)
    text = re.sub(r"\\sqrt(\d+)", r"√\1", text)

    # Integrals: \int_0^{\pi/4} -> ∫[0 → π/4]
    text = re.sub(r"\\int_?\{?([^}^\s\\]*)\}?\^\{?([^}^\s\\]*)\}?", r"∫[\1 → \2] ", text)
    text = re.sub(r"\\int0\^\{?([^}^\s\\]*)\}?", r"∫[0 → \1] ", text)
    text = re.sub(r"\\int", "∫", text)

    # Limits: \lim_{x \to +\infty} -> lim(x → +∞)
    text = re.sub(r"\\lim_\{([^}]+)\}", r"lim(\1)", text)
    text = re.sub(r"\\lim", "lim", text)

    # Clean text{} tags
    text = re.sub(r"\\text\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\mathbf\{([^}]*)\}", r"\1", text)

    # Superscripts: x^2 -> x², x^{10} -> x¹⁰, e^4 -> e⁴
    text = re.sub(r"\^\{([0-9nx\+\-]+)\}", lambda m: "".join(sups.get(c, c) for c in m.group(1)), text)
    text = re.sub(r"\^([0-9nx\+\-])", lambda m: sups.get(m.group(1), "^" + m.group(1)), text)

    # Clean any lingering lone backslashes
    text = re.sub(r"\\([a-zA-Z]+)", r"\1", text)

    # Ensure any raw multi-line fractions outside code blocks get wrapped in ```
    text = wrap_orphan_fraction_blocks(text)

    # Clean consecutive duplicate code block markers ``` ```
    text = re.sub(r"```\s*```", "", text)

    return text.strip()


class GeminiSolver:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.primary_model = model or os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
        self.model = self.primary_model
        # Candidate models with gemini-3.5-flash prioritized for stability, reasoning, and quota
        self.candidate_models = [
            self.primary_model,
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-flash-latest"
        ]
        self.candidate_models = list(dict.fromkeys(self.candidate_models))

    def solve(
        self,
        prompt: str,
        image_bytes: Optional[bytes] = None,
        mime_type: str = "image/jpeg"
    ) -> Tuple[bool, str]:
        """
        Sends question/exercise to Gemini API and returns (success, formatted_clean_math_text).
        """
        if not self.api_key:
            return False, "❌ Error: GEMINI_API_KEY is not set. Please configure your API key in .env or Vercel Environment Variables."

        parts = []

        if image_bytes:
            encoded_image = base64.b64encode(image_bytes).decode("utf-8")
            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": encoded_image
                }
            })

        text_content = prompt.strip() if prompt else (
            "សូមដោះស្រាយលំហាត់ក្នុងរូបភាពនេះតាមទម្រង់ស្តង់ដារ៖ «**លំហាត់ទី...**», ចំណុចរង «○  **ក)**  **ខ)**  **គ)**...», "
            "រាល់ប្រភាគ និងការគណនាសមីការទាំងអស់ត្រូវសរសេរជាទម្រង់ប្រភាគឈរពិតប្រាកដ មានភាគយកនៅខាងលើ របារប្រភាគ ─── នៅកណ្តាល និងភាគបែងនៅខាងក្រោម "
            "ហើយត្រូវដាក់ក្នុងប្រអប់ Code block (```) ជានិច្ច ដើម្បីកុំឱ្យរត់ខុសជួរលើទូរស័ព្ទ (ហាមប្រើសញ្ញា / សម្រាប់ប្រភាគជាដាច់ខាត) "
            "និងប្រើរូបមន្តនិមិត្តសញ្ញា Unicode ស្អាតៗ (ហាមប្រើ LaTeX commands ដូចជា \\frac, \\sqrt, \\int, $, $$)។"
        )
        parts.append({"text": text_content})

        payload = {
            "contents": [
                {
                    "parts": parts
                }
            ],
            "systemInstruction": {
                "parts": [
                    {"text": SYSTEM_INSTRUCTION}
                ]
            },
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 8192
            }
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }

        last_error = ""

        for model_name in self.candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"

            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=45)

                if resp.status_code == 200:
                    ok, raw_text = self._extract_text(resp.json())
                    if ok:
                        # Post-process through math formatter for 100% clean Telegram rendering
                        return True, format_math_telegram(raw_text)
                    return False, raw_text

                # Fallback to next model if quota limit (429), high demand (503), or not found (404)
                if resp.status_code in [429, 503, 404]:
                    last_error = f"{model_name}: {resp.status_code}"
                    continue

                if "API_KEY_INVALID" in resp.text or "API key not valid" in resp.text:
                    return False, "⚠️ Google Gemini API Key មិនត្រឹមត្រូវឡើយ។ សូមពិនិត្យមើល API Key ឡើងវិញ។"

                last_error = f"{model_name} ({resp.status_code}): {resp.text}"

            except requests.exceptions.Timeout:
                last_error = f"{model_name} timed out"
                continue
            except Exception as e:
                last_error = str(e)
                continue

        return False, f"⚠️ Gemini API កំពុងមានបញ្ហាឆ្លើយតប: {last_error}"

    def _extract_text(self, data: dict) -> Tuple[bool, str]:
        """Extracts final answer text, filtering out internal thought tokens."""
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                return False, "⚠️ មិនមានចម្លើយពីប្រព័ន្ធឡើយ (No response candidate)."

            parts = candidates[0].get("content", {}).get("parts", [])
            # Filter out thinking parts so only actual answer is presented
            texts = [p.get("text", "") for p in parts if "text" in p and not p.get("thought", False)]
            reply = "\n".join(texts).strip()

            if not reply:
                # If all parts were thought or empty, grab any text
                texts = [p.get("text", "") for p in parts if "text" in p]
                reply = "\n".join(texts).strip()

            if not reply:
                return False, "⚠️ មិនមានអត្ថបទចម្លើយ (Empty response text)."
            return True, reply
        except Exception as e:
            return False, f"⚠️ កំហុសទាញយកទិន្នន័យ: {str(e)}"
