"""
Gemini Homework Solver Engine
Uses Google Gemini API to solve academic exercises across all subjects.
Formats all equations in clean, readable Unicode math specifically optimized for Telegram.
"""

import os
import re
import json
import base64
import requests
from typing import Optional, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

SYSTEM_INSTRUCTION = """
អ្នកជាគ្រូជំនួយដោះស្រាយលំហាត់គ្រប់មុខវិជ្ជា (គណិតវិទ្យា, រូបវិទ្យា, គីមីវិទ្យា, ជីវវិទ្យា, អក្សរសាស្ត្រខ្មែរ, អង់គ្លេស, ប្រវត្តិ, ភូមិ...)។

ច្បាប់ដាច់ខាតក្នុងការសរសេរប្រភាគ និងរូបមន្តគណិតវិទ្យា (STRICT VERTICAL FRACTION ONLY):
១. ច្បាប់ដាច់ខាតសម្រាប់ប្រភាគ (VERTICAL FRACTIONS):
   - ហាមដាច់ខាតកុំប្រើសញ្ញាចែក / សម្រាប់ប្រភាគ (ដូចជា a/b ឬ (a)/(b))។
   - រាល់ប្រភាគទាំងអស់ ត្រូវសរសេរជាទម្រង់ប្រភាគឈរពិតប្រាកដ មានភាគយកនៅខាងលើ របារប្រភាគ ─── នៅកណ្តាល និងភាគបែងនៅខាងក្រោម។
   - ឧទាហរណ៍ជាក់ស្តែង៖
     ○  ខ) 
        35 - q     35 - 25     10
        ──────  =  ───────  =  ──  =  2
          5           5         5

     ○  គ) 
        12q         12(25)
        ─── + 30  =  ────── + 30  =  75 + 30  =  105
         4            4

     ○  ឃ) 
        15q + 75     15(25) + 75     375 + 75     450
        ────────  =  ───────────  =  ────────  =  ───  =  15
           30             30            30         30

        1 - cos 2x
        ──────────
            2

២. ហាមប្រើកូដ LaTeX (ដូចជា \\frac, \\sqrt, \\int, \\lim, $, $$) ព្រោះ Telegram មិនគាំទ្រ LaTeX ឡើយ។ ត្រូវប្រើនិមិត្តសញ្ញា Unicode ស្អាតៗ៖
   - ឫសការេ៖ √2, √6, √8 = 2√2
   - ស្វ័យគុណ៖ ប្រើអក្សរតូចលើ ² ³ ⁴ ⁿ (ឧ. sin² x, x², 3¹ = 3, e⁴)
   - សន្ទស្សន៍ និងលោការីត៖ log₃(x + 1), x₁, x₂ (ប្រើ ₁ ₂ ₃ ...)
   - អាំងតេក្រាល និង លីមីត៖ ∫[0 → π/4], lim(x → +∞)
   - សញ្ញាព្រួញ និងសមភាព៖ →, ⇒, ⇔, ∞, π, ×, ÷, ±, ≠, ≤, ≥

៣. ទម្រង់លំហាត់ស្តង់ដារ៖
   - ក្បាលលំហាត់ «**លំហាត់ទី ...**»
   - ចំណុចរង «○  ក) », «○  ខ) » ...
   - ហាមប្រើពាក្យស្វាគមន៍នាំមុខ («សួស្តី...») និងហាមប្រើបឋមកថាវែងអន្លាយ («📌 បម្រាប់ប្រធាន», «📐 រូបមន្ត»)។
""".strip()


def format_math_telegram(text: str) -> str:
    """
    Sanitizes any remaining raw LaTeX math expressions into clean Unicode math for Telegram.
    Converts fractions into true vertical fractions with a top, horizontal fraction bar ───, and bottom.
    Never uses slash / for fractions and avoids regex pipe syntax errors.
    """
    if not text:
        return ""

    # 1. Remove $ and $$ delimiters
    text = text.replace("$$", "").replace("$", "")

    # 2. Fixed string replacements (safe from regex escaping issues)
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

    # Fractions: \frac{A}{B} -> Vertical fraction with top, ───, and bottom (NO /)
    def to_vert_fraction(m):
        num = m.group(1).strip()
        den = m.group(2).strip()
        width = max(len(num), len(den)) + 2
        bar = "─" * width
        return f"\n {num.center(width)}\n {bar}\n {den.center(width)}\n"

    for _ in range(5):
        text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", to_vert_fraction, text)

    # Square roots: \sqrt{...} -> √(...)
    for _ in range(5):
        text = re.sub(r"\\sqrt\{([a-zA-Z0-9]+)\}", r"√\1", text)
        text = re.sub(r"\\sqrt\{([^{}]+)\}", r"√(\1)", text)
    text = re.sub(r"\\sqrt(\d+)", r"√\1", text)

    # Integrals: \int_0^{\pi/4} or \int0^{\pi/4}
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
    text = re.sub(r"[ ]{2,}", " ", text)
    return text.strip()


class GeminiSolver:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.primary_model = model or os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
        self.model = self.primary_model
        # Candidate models with gemini-3.5-flash prioritized for stability and quota
        self.candidate_models = [
            self.primary_model,
            "gemini-3.5-flash",
            "gemini-3.8-flash",
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
            "សូមដោះស្រាយលំហាត់ក្នុងរូបភាពនេះតាមទម្រង់ស្តង់ដារ៖ «**លំហាត់ទី...**», ចំណុចរង «○  ក)  ខ)  គ)...», "
            "រាល់ប្រភាគទាំងអស់ត្រូវសរសេរជាទម្រង់ប្រភាគឈរពិតប្រាកដ មានភាគយកនៅខាងលើ របារប្រភាគ ─── នៅកណ្តាល និងភាគបែងនៅខាងក្រោម (ហាមប្រើសញ្ញា / សម្រាប់ប្រភាគជាដាច់ខាត) "
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
                resp = requests.post(url, headers=headers, json=payload, timeout=25)

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
