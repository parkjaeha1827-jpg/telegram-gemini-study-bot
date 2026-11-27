"""
Gemini Homework Solver Engine
Uses Google Gemini API to solve academic exercises across all subjects.
Formats all equations in clean, textbook-quality math specifically optimized for Telegram.
All solutions are complete 100% from start to finish (never truncated or cut off),
with smart algebraic simplifications, balanced brackets, and clean compact layouts.
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
អ្នកជាគ្រូជំនួយដោះស្រាយលំហាត់គំរូកម្រិតខ្ពស់ ឆ្លើយចំៗ ត្រឹមត្រូវ ស្អាតបាត និងងាយយល់បំផុត។

ច្បាប់ដែកថែបដើម្បីកុំឱ្យដំណោះស្រាយ «ដាច់ក្បាលដាច់កន្ទុយ» ឬ «ពិបាកមើល» (CORE RULES):
១. ដំណោះស្រាយពេញលេញ ១០០% តាំងពីដើមដល់ចប់ (COMPLETE FROM HEAD TO TAIL):
   - រាល់លំហាត់ទាំងអស់ ត្រូវតែមានដំណោះស្រាយពេញលេញតាំងពីដើមរហូតដល់ចុងបញ្ចប់៖
     • ក្បាលលំហាត់៖ **[លេខរៀង]. [ប្រធានលំហាត់]** (ឧ. **២៩. សរសេរចំនួនកុំផ្លិច Z = ... ជាទម្រង់ត្រីកោណមាត្រ**)
     • ជំហានគណនា៖ បង្ហាញលំហូរគណនាច្បាស់ៗមួយៗ
     • ចម្លើយចុងក្រោយ៖ បញ្ចប់ដោយចម្លើយចុងក្រោយពេញលេញជានិច្ច (ឧ. «ចម្លើយត្រឹមត្រូវគឺ គ. ...» ឬ «ដូចនេះ Z = ...»)
   - ហាមដាច់ខាតកុំកាត់ផ្តាច់ពាក់កណ្តាលទី ឬបាត់ចម្លើយចុងក្រោយ (ហាមដាច់ខាតកុំឱ្យដាច់ក្បាលដាច់កន្ទុយ)!

២. ជ្រើសរើសវិធីដោះស្រាយខ្លី ឆ្លាតវៃ និងស្រួលយល់បំផុត (SMART & DIRECT METHODS):
   - បើកន្សោមអាចសម្រួលបាន ត្រូវសម្រួលកត្តារួមជាមុនសិនជានិច្ច!
     ឧទាហរណ៍ជាក់ស្តែង លំហាត់ ២៩៖
     Z = (5√3 - 5i) / (-√6 + i√2)
       = [ 5(√3 - i) ] / [ -√2(√3 - i) ]
       = - 5 / √2
       = - (5√2) / 2
     រួចសរសេរជាទម្រង់ត្រីកោណមាត្រភ្លាមៗ៖
     Z = (5√2)/2 · ( cos π + i sin π )
   - ហាមដាច់ខាតកុំប្រើវិធីគណនាក្បួនវែងអន្លាយ ស្មុគស្មាញ (ដូចជាគណនាប៉ូលែភាគយក រួចគណនាប៉ូលែភាគបែង...) ដែលនាំឱ្យវែងរញ៉េរញ៉ៃ និងកាត់ផ្តាច់ពាក់កណ្តាលទី។

៣. ដំណោះស្រាយមានលំហូររលូន មិនបំបែកជាប្រអប់កូដច្រើនកំប៉ិកកំប៉ុក (UNIFIED FLOW):
   - ក្នុងលំហាត់មួយ ដំណោះស្រាយគណនាត្រូវសរសេរឱ្យមានលំហូរបន្តគ្នាជាប់ជានិច្ច កុំបំបែកជាប្រអប់តូចៗ ៣-៤ ប្រអប់ដែលនាំឱ្យមើលទៅដាច់ក្បាលដាច់កន្ទុយ។
   - បើមានប្រភាគឈរ ត្រូវសរសេរឱ្យស្មើជួរស្អាត មានភាគយក របារប្រភាគ ─── និងភាគបែង។
   - គម្លាតជួរលើក្រោមត្រូវនៅកៀកគ្នាសមល្មម មិនឱ្យឃ្លាតឆ្ងាយពីគ្នាពេក។

៤. ហាមពាក្យអូសបន្លាយ៖
   - ហាមសរសេរពាក្យស្វាគមន៍ («សួស្តី...»)
   - ហាមសរសេរ «**ដំណោះស្រាយ៖**» ឬ «- ដំណោះស្រាយ៖»
   - ហាមសរសេរ «👉 **ចម្លើយចុងក្រោយ៖**» ឬ «👉 **ដូចនេះ៖**»
   - ចូលដោះស្រាយផ្ទាល់ភ្លាមៗតាមគំរូខាងក្រោម។

គំរូស្តង់ដារទាំង ៤ (FOLLOW THESE EXACTLY):

គំរូទី ១ (អាំងតេក្រាល):
**២៥. គណនាអាំងតេក្រាល I = ∫₀^(π/4) sin² x dx**
ប្រើរូបមន្តបន្ថយស្វ័យគុណត្រីកោណមាត្រ sin² x = (1 - cos 2x)/2 គេបាន៖
```
          π/4  1 - cos 2x            1 [        sin 2x ] π/4
I  =   ∫     ──────────── dx  =  ─ [ x  -   ────── ]
          0        2                 2 [          2    ] 0

          1 [ ( π/4 - sin(2 · π/4)/2 ) - ( 0 - sin(0)/2 ) ]
   =  ─
          2

          1   π    sin(π/2)        1   π   1        1   π - 2        π - 2
   =  ─ ( ─  - ──────── )  =  ─ ( ─ - ─ )  =  ─ ( ───── )  =  ─────
          2   4       2            2   4   2        2     4            8
```
ចម្លើយត្រឹមត្រូវគឺ គ. I = (π - 2)/8

គំរូទី ២ (លីមីត):
**២៦. គណនាលីមីត lim_{x→+∞} ((x+3)/(x-1))^(x+2)**
បំបែកប្រភាគខាងក្នុងវង់ក្រចក៖
```
x + 3     (x - 1) + 4           4
─────  =  ───────────  =  1 + ─────
x - 1        x - 1            x - 1
```
គេបាន៖
```
lim_{x→+∞} ( 1 + 4/(x - 1) )^(x+2)
```
តាង u = (x - 1)/4 ⇒ x - 1 = 4u ⇒ x + 2 = 4u + 3 (ពេល x → +∞ នោះ u → +∞) ៖
```
lim_{u→+∞} ( 1 + 1/u )^(4u+3) = lim_{u→+∞} [( 1 + 1/u )^u]⁴ · ( 1 + 1/u )³
                              = e⁴ · 1³ = e⁴
```
ចម្លើយត្រឹមត្រូវគឺ e⁴

គំរូទី ៣ (សមីការលោការីត):
**២៧. ដោះស្រាយសមីការ log₃(x + 1) + log₃(x + 3) = 1**
○ លក្ខខណ្ឌកំណត់៖
```
⎧ x + 1 > 0       ⎧ x > -1
⎨             ⇒   ⎨         ⇒  x > -1
⎩ x + 3 > 0       ⎩ x > -3
```
○ ដោះស្រាយសមីការ៖
```
log₃ [(x + 1)(x + 3)] = 1
(x + 1)(x + 3) = 3¹
x² + 4x + 3 = 3
x² + 4x = 0
x(x + 4) = 0  ⇒  ⎡ x = 0
                 ⎣ x = -4
```
តម្លៃ x = -4 មិនយក (ព្រោះ x > -1)
ដូចនេះ x = 0

គំរូទី ៤ (ចំនួនកុំផ្លិច):
**២៨. រកម៉ូឌុលនៃចំនួនកុំផ្លិច Z = √2 + i√6**
តាមរូបមន្តម៉ូឌុលនៃចំនួនកុំផ្លិច Z = a + bi គឺ r = |Z| = √(a² + b²) ៖
```
r = √((√2)² + (√6)²) = √(2 + 6) = √8 = √(4 × 2) = 2√2
```
ចម្លើយត្រឹមត្រូវគឺ គ. r = 2√2

**២៩. សរសេរចំនួនកុំផ្លិច Z = (5√3 - 5i) / (-√6 + i√2) ជាទម្រង់ត្រីកោណមាត្រ**
សម្រួលកន្សោម Z ជាមុនសិន៖
```
    5(√3 - i)         5(√3 - i)           5       5√2
Z = ───────────  =  ────────────  =  - ─────  =  ─────
    √2(-√3 + i)     -√2(√3 - i)          √2        2
```
សរសេរចំនួនពិតអវិជ្ជមាន - (5√2)/2 ជាទម្រង់ត្រីកោណមាត្រ (ម៉ូឌុល r = (5√2)/2 > 0 និងអាគុយម៉ង់ θ = π) ៖
```
        5√2                          5√2
Z =  - ─────  =  ────── ( -1 + 0i ) = ────── ( cos π + i sin π )
         2          2                    2
```
ចម្លើយត្រឹមត្រូវគឺ គ. Z = (5√2)/2 (cos π + i sin π)
""".strip()


def extract_braced_content(text: str, start_idx: int) -> Tuple[Optional[str], int]:
    """Extracts content within matching { and } starting at start_idx."""
    if start_idx >= len(text) or text[start_idx] != "{":
        return None, start_idx
    depth = 0
    content = []
    for i in range(start_idx, len(text)):
        char = text[i]
        if char == "{":
            depth += 1
            if depth > 1:
                content.append(char)
        elif char == "}":
            depth -= 1
            if depth == 0:
                return "".join(content), i + 1
            else:
                content.append(char)
        else:
            content.append(char)
    return None, start_idx


def replace_latex_fractions_and_roots(text: str) -> str:
    """
    Robustly parses and converts LaTeX \\frac{...}{...} and \\sqrt{...}
    even with nested braces or complex expressions.
    """
    # 1. Parse \frac{num}{den}
    result = []
    i = 0
    while i < len(text):
        if text.startswith(r"\frac", i):
            num, next_i = extract_braced_content(text, i + 5)
            if num is not None:
                while next_i < len(text) and text[next_i] in " \t\r\n":
                    next_i += 1
                den, end_i = extract_braced_content(text, next_i)
                if den is not None:
                    num = replace_latex_fractions_and_roots(num)
                    den = replace_latex_fractions_and_roots(den)
                    # Clean representation
                    result.append(f"({num}) / ({den})")
                    i = end_i
                    continue
        elif text.startswith(r"\sqrt", i):
            content, end_i = extract_braced_content(text, i + 5)
            if content is not None:
                content = replace_latex_fractions_and_roots(content)
                result.append(f"√({content})")
                i = end_i
                continue
        result.append(text[i])
        i += 1

    s = "".join(result)
    # Simplify √(digit) -> √digit (e.g. √(2) -> √2)
    s = re.sub(r"√\((\d+)\)", r"√\1", s)
    s = re.sub(r"√\(([a-zA-Z])\)", r"√\1", s)
    return s


def sanitize_brackets_and_symbols(text: str) -> str:
    """Replaces broken multi-line bracket art characters with clean standard brackets."""
    bad_chars = {
        "": " ", "": " ", "": " ",
        "⎛": " ", "⎜": " ", "⎝": " ",
        "⎞": " ", "⎟": " ", "⎠": " ",
        "┌": "[", "┐": "]", "└": "[", "┘": "]",
        "│": " ", "┃": " ", "║": " "
    }
    for k, v in bad_chars.items():
        text = text.replace(k, v)
    return text


def compact_vertical_spacing(text: str) -> str:
    """
    Eliminates excessive vertical gaps between lines and around code blocks
    so the math display remains compact, tight, and comfortable to read on Telegram.
    """
    if not text:
        return ""

    text = re.sub(r"\n{3,}", "\n\n", text)
    parts = text.split("```")
    for i in range(len(parts)):
        if i % 2 == 1:
            # Inside code block: remove redundant blank lines
            lines = parts[i].split("\n")
            while lines and not lines[0].strip():
                lines.pop(0)
            while lines and not lines[-1].strip():
                lines.pop()
            compact_lines = []
            prev_empty = False
            for line in lines:
                is_empty = not line.strip()
                if is_empty and prev_empty:
                    continue
                compact_lines.append(line)
                prev_empty = is_empty
            parts[i] = "\n" + "\n".join(compact_lines) + "\n"
        else:
            # Outside code block: ensure no excessive gap right before/after ```
            parts[i] = re.sub(r"\n{2,}$", "\n", parts[i])
            parts[i] = re.sub(r"^\n{2,}", "\n", parts[i])

    result = "```".join(parts)
    result = re.sub(r"\n{2,}```", "\n```", result)
    result = re.sub(r"```\n{2,}", "```\n", result)
    return result.strip()


def format_math_telegram(text: str) -> str:
    """
    Sanitizes any remaining raw LaTeX math expressions into clean Unicode math for Telegram.
    Guarantees no raw frac or LaTeX leak, clean vertical fractions, and compact spacing.
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
        ("\\implies", "⇒"), ("\\iff", "⇔"),
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

    # Convert any lingering LaTeX \frac and \sqrt robustly
    text = replace_latex_fractions_and_roots(text)

    # Integrals: \int_0^{\pi/4} -> ∫[0 → π/4]
    text = re.sub(r"\\int_?\{?([^}^\s\\]*)\}?\^\{?([^}^\s\\]*)\}?", r"∫[\1 → \2] ", text)
    text = re.sub(r"\\int0\^\{?([^}^\s\\]*)\}?", r"∫[0 → \1] ", text)
    text = re.sub(r"\\int", "∫", text)

    # Limits: \lim_{x \to +\infty} -> lim(x → +∞)
    text = re.sub(r"\\lim_\{([^}]+)\}", r"lim(\1)", text)
    text = re.sub(r"\\lim", "lim", text)

    # Clean cases environment
    text = text.replace("\\begin{cases}", "").replace("\\end{cases}", "")

    # Clean text{} tags
    text = re.sub(r"\\text\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\mathbf\{([^}]*)\}", r"\1", text)

    # Superscripts: x^2 -> x², x^{10} -> x¹⁰, e^4 -> e⁴
    text = re.sub(r"\^\{([0-9nx\+\-]+)\}", lambda m: "".join(sups.get(c, c) for c in m.group(1)), text)
    text = re.sub(r"\^([0-9nx\+\-])", lambda m: sups.get(m.group(1), "^" + m.group(1)), text)

    # Clean any lingering lone backslashes
    text = re.sub(r"\\([a-zA-Z]+)", r"\1", text)

    # Clean consecutive duplicate code block markers ``` ```
    text = re.sub(r"```\s*```", "", text)

    # Eliminate excessive vertical gaps and tightens spacing
    text = compact_vertical_spacing(text)

    return text.strip()


class GeminiSolver:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.primary_model = model or os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.model = self.primary_model
        # Candidate models with gemini-3.5-flash-lite prioritized for fast 1-2s response and high quota
        self.candidate_models = [
            self.primary_model,
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
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

        default_prompt = (
            "សូមដោះស្រាយលំហាត់ក្នុងរូបភាពនេះឱ្យបានចប់សព្វគ្រប់ ១០០% គ្រប់លំហាត់ទាំងអស់ (មានក្បាលលំហាត់ «**[លេខរៀង]. [ប្រធាន]**», "
            "ដំណោះស្រាយខ្លី ខ្លឹម សម្រួលកត្តារួមឱ្យងាយយល់ និងចម្លើយចុងក្រោយពេញលេញ ហាមដាច់ខាតកុំឱ្យដាច់ក្បាលដាច់កន្ទុយ)។ "
            "រាល់ប្រភាគឈរត្រូវសរសេរមានភាគយក របារប្រភាគ ─── និងភាគបែង ដាក់ក្នុងប្រអប់ Code block (```) "
            "និងបញ្ចប់ដោយចម្លើយត្រឹមត្រូវ (ឧ. «ចម្លើយត្រឹមត្រូវគឺ គ. ...»)។"
        )
        text_content = prompt.strip() if prompt else default_prompt
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
                resp = requests.post(url, headers=headers, json=payload, timeout=30)

                if resp.status_code == 200:
                    ok, raw_text = self._extract_text(resp.json())
                    if ok:
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
