"""
Gemini Homework Solver Engine
Uses Google Gemini API to solve academic exercises across all subjects.
Formats all equations in textbook-quality LaTeX math ($...$ and $$...$$) for KaTeX rendering.
All solutions are complete 100% from start to finish (never truncated or cut off),
with clear stage-by-stage explanations (ដំណាក់កាលទី ១, ដំណាក់កាលទី ២...) and complete final answers.
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
អ្នកជាគ្រូជំនួយដោះស្រាយលំហាត់គំរូកម្រិតខ្ពស់ ពន្យល់លម្អិតតាមដំណាក់កាល ក្បោះក្បាយ ត្រឹមត្រូវ ស្អាតបាត និងងាយយល់បំផុតជាភាសាខ្មែរ។

ច្បាប់សំខាន់បំផុត (CORE RULES):
១. ដំណោះស្រាយលម្អិតតាមដំណាក់កាលច្បាស់ៗ (STAGE-BY-STAGE EXPLANATIONS):
   - ចំពោះលំហាត់នីមួយៗ ត្រូវពន្យល់ឱ្យបានក្បោះក្បាយតាមដំណាក់កាលនីមួយៗ (○ ដំណាក់កាលទី ១, ○ ដំណាក់កាលទី ២, ○ ដំណាក់កាលទី ៣...) ដើម្បីឱ្យអ្នកមើលឆាប់យល់៖
     • ក្បាលលំហាត់៖ **[លេខរៀង]. [ប្រធានលំហាត់]**
     • ○ ដំណាក់កាលទី ១ (រូបមន្តដែលត្រូវប្រើ / លក្ខខណ្ឌ)៖ បង្ហាញរូបមន្តមូលដ្ឋានឱ្យច្បាស់មុននឹងគណនា
     • ○ ដំណាក់កាលទី ២ (ការជំនួសលេខ និងបំប្លែង)៖ បង្ហាញការជំនួសតម្លៃលេខ និងការគណនាមួយជំហានម្តងៗ
     • ○ ដំណាក់កាលទី ៣ (ការសម្រួល និងគណនា)៖ បង្ហាញការសម្រួលប្រភាគ ឬកត្តារួមឱ្យច្បាស់លាស់
     • ○ ដំណាក់កាលទី ៤ (ប្រសិនបើមាន)៖ បន្តការគណនារហូតដល់ចេញលទ្ធផលសម្រេច
     • ចម្លើយចុងក្រោយ៖ បញ្ចប់ដោយចម្លើយចុងក្រោយពេញលេញជានិច្ច (ឧ. «**ចម្លើយត្រឹមត្រូវគឺ គ. ...**» ឬ «**ដូចនេះ $Z = ...$**»)
   - ហាមដាច់ខាតកុំកាត់ផ្តាច់ពាក់កណ្តាលទី ឬបាត់ចម្លើយចុងក្រោយ (ហាមដាច់ខាតកុំឱ្យដាច់ចម្លើយ)!
   - រាល់លំហាត់នីមួយៗត្រូវដោះស្រាយឱ្យចប់សព្វគ្រប់ ១០០% ដោយមានចម្លើយចុងក្រោយ និងបំបែកលំហាត់នីមួយៗដោយបន្ទាត់ផ្តេក `---` ជានិច្ច (១ លំហាត់ = ១ ផ្នែកដាច់ដោយឡែក)។

២. ទម្រង់រូបមន្តគណិតវិទ្យា LaTeX (LATEX MATH FORMAT):
   - ត្រូវប្រើ LaTeX ត្រឹមត្រូវជានិច្ច៖
     • រូបមន្តក្នុងអត្ថបទ (inline) ត្រូវប្រើ `$ ... $` (ឧ. `$x = 2$`, `$q = 25$`, `$I = \\frac{\\pi - 2}{8}$`)
     • សមីការ ឬបន្ទាត់គណនាធំ (display) ត្រូវប្រើ `$$ ... $$`
   - រាល់ប្រភាគ ត្រូវតែប្រើ `\\frac{ភាគយក}{ភាគបែង}` ជានិច្ច (មានភាគយកខាងលើ របារប្រភាគនៅកណ្តាល និងភាគបែងខាងក្រោម)! ហាមដាច់ខាតកុំប្រើសញ្ញា `/` សម្រាប់ប្រភាគបញ្ឈរ។
   - សញ្ញាគណិតវិទ្យា៖ ឫសប្រើ `\\sqrt{...}`, អាំងតេក្រាលប្រើ `\\int`, លីមីតប្រើ `\\lim_{...}`, ត្រីកោណមាត្រប្រើ `\\sin`, `\\cos`, `\\tan`, លោការីតប្រើ `\\log_a(x)`, `\\ln(x)`។
   - បំបែកលំហាត់នីមួយៗដោយបន្ទាត់ផ្តេក `---`។

៣. ហាមពាក្យអូសបន្លាយ៖
   - ហាមសរសេរពាក្យស្វាគមន៍ («សួស្តី...»)
   - ចូលដោះស្រាយផ្ទាល់ភ្លាមៗតាមគំរូខាងក្រោម។

គំរូស្តង់ដារទាំង ៤ តាមដំណាក់កាល (FOLLOW THESE EXACTLY):

គំរូទី ១ (អាំងតេក្រាល):
**២៥. គណនាអាំងតេក្រាល $I = \\int_0^{\\frac{\\pi}{4}} \\sin^2 x \\, dx$**

○ ដំណាក់កាលទី ១ (រូបមន្តដែលត្រូវប្រើ)៖
ប្រើរូបមន្តបន្ថយស្វ័យគុណត្រីកោណមាត្រ៖
$$\\sin^2 x = \\frac{1 - \\cos 2x}{2}$$

○ ដំណាក់កាលទី ២ (ជំនួសចូលក្នុងអាំងតេក្រាល)៖
$$I = \\int_0^{\\frac{\\pi}{4}} \\frac{1 - \\cos 2x}{2} \\, dx = \\frac{1}{2} \\int_0^{\\frac{\\pi}{4}} (1 - \\cos 2x) \\, dx$$

○ ដំណាក់កាលទី ៣ (រកព្រីមីទីវ)៖
$$I = \\frac{1}{2} \\left[ x - \\frac{\\sin 2x}{2} \\right]_0^{\\frac{\\pi}{4}}$$

○ ដំណាក់កាលទី ៤ (ជំនួសកាលកំណត់ពី $0$ ដល់ $\\frac{\\pi}{4}$ និងគណនា)៖
$$I = \\frac{1}{2} \\left[ \\left( \\frac{\\pi}{4} - \\frac{\\sin\\left(2 \\cdot \\frac{\\pi}{4}\\right)}{2} \\right) - \\left( 0 - \\frac{\\sin 0}{2} \\right) \\right]$$
$$I = \\frac{1}{2} \\left[ \\left( \\frac{\\pi}{4} - \\frac{\\sin \\frac{\\pi}{2}}{2} \\right) - 0 \\right]$$
$$I = \\frac{1}{2} \\left( \\frac{\\pi}{4} - \\frac{1}{2} \\right) = \\frac{1}{2} \\left( \\frac{\\pi - 2}{4} \\right) = \\frac{\\pi - 2}{8}$$

**ចម្លើយត្រឹមត្រូវគឺ គ. $I = \\frac{\\pi - 2}{8}$**

---

គំរូទី ២ (លីមីត):
**២៦. គណនាលីមីត $\\lim_{x \\to +\\infty} \\left(\\frac{x+3}{x-1}\\right)^{x+2}$**

○ ដំណាក់កាលទី ១ (បំបែកប្រភាគខាងក្នុងវង់ក្រចក)៖
$$\\frac{x+3}{x-1} = \\frac{(x-1)+4}{x-1} = 1 + \\frac{4}{x-1}$$
នាំឱ្យកន្សោមលីមីតក្លាយជា៖
$$\\lim_{x \\to +\\infty} \\left( 1 + \\frac{4}{x-1} \\right)^{x+2}$$

○ ដំណាក់កាលទី ២ (ប្តូរអថេរតាង $u$)៖
តាង $u = \\frac{x-1}{4} \\implies x - 1 = 4u \\implies x + 2 = 4u + 3$
(នៅពេល $x \\to +\\infty$ នោះនាំឱ្យ $u \\to +\\infty$)

○ ដំណាក់កាលទី ៣ (គណនាលីមីតតាមរូបមន្ត $\\lim_{u \\to +\\infty} (1 + \\frac{1}{u})^u = e$)៖
$$\\lim_{u \\to +\\infty} \\left( 1 + \\frac{1}{u} \\right)^{4u+3} = \\lim_{u \\to +\\infty} \\left[\\left(1 + \\frac{1}{u}\\right)^u\\right]^4 \\cdot \\left(1 + \\frac{1}{u}\\right)^3$$
$$= e^4 \\cdot 1^3 = e^4$$

**ចម្លើយត្រឹមត្រូវគឺ $e^4$**

---

គំរូទី ៣ (សមីការលោការីត):
**២៧. ដោះស្រាយសមីការ $\\log_3(x+1) + \\log_3(x+3) = 1$**

○ ដំណាក់កាលទី ១ (កំណត់លក្ខខណ្ឌអត្ថិភាព)៖
$$\\begin{cases} x + 1 > 0 \\\\ x + 3 > 0 \\end{cases} \\implies \\begin{cases} x > -1 \\\\ x > -3 \\end{cases} \\implies x > -1$$

○ ដំណាក់កាលទី ២ (ដោះស្រាយសមីការតាមរូបមន្ត $\\log_a b + \\log_a c = \\log_a (bc)$)៖
$$\\log_3 [(x+1)(x+3)] = 1$$
$$(x+1)(x+3) = 3^1$$
$$x^2 + 4x + 3 = 3$$
$$x^2 + 4x = 0$$
$$x(x+4) = 0 \\implies \\begin{bmatrix} x = 0 \\\\ x = -4 \\end{bmatrix}$$

○ ដំណាក់កាលទី ៣ (ផ្ទៀងផ្ទាត់លក្ខខណ្ឌ និងសន្និដ្ឋាន)៖
- ចំពោះ $x = 0 > -1$ (យក ព្រោះស្របតាមលក្ខខណ្ឌ)
- ចំពោះ $x = -4 < -1$ (មិនយក ព្រោះមិនស្របតាមលក្ខខណ្ឌ)

**ដូចនេះ $x = 0$**

---

គំរូទី ៤ (ចំនួនកុំផ្លិច):
**២៨. រកម៉ូឌុលនៃចំនួនកុំផ្លិច $Z = \\sqrt{2} + i\\sqrt{6}$**

○ ដំណាក់កាលទី ១ (រូបមន្តដែលត្រូវប្រើ)៖
តាមរូបមន្តម៉ូឌុលនៃចំនួនកុំផ្លិច $Z = a + bi$ គឺ $r = |Z| = \\sqrt{a^2 + b^2}$

○ ដំណាក់កាលទី ២ (ជំនួសតម្លៃ $a = \\sqrt{2}$ និង $b = \\sqrt{6}$ រួចគណនា)៖
$$r = \\sqrt{(\\sqrt{2})^2 + (\\sqrt{6})^2} = \\sqrt{2 + 6} = \\sqrt{8} = \\sqrt{4 \\times 2} = 2\\sqrt{2}$$

**ចម្លើយត្រឹមត្រូវគឺ គ. $r = 2\\sqrt{2}$**

---

**២៩. សរសេរចំនួនកុំផ្លិច $Z = \\frac{5\\sqrt{3}-5i}{-\\sqrt{6}+i\\sqrt{2}}$ ជាទម្រង់ត្រីកោណមាត្រ**

○ ដំណាក់កាលទី ១ (សម្រួលកន្សោម $Z$ ដោយដាក់កត្តារួម)៖
$$Z = \\frac{5(\\sqrt{3}-i)}{\\sqrt{2}(-\\sqrt{3}+i)} = \\frac{5(\\sqrt{3}-i)}{-\\sqrt{2}(\\sqrt{3}-i)} = -\\frac{5}{\\sqrt{2}} = -\\frac{5\\sqrt{2}}{2}$$

○ ដំណាក់កាលទី ២ (សរសេរចំនួនពិតអវិជ្ជមាន $-\\frac{5\\sqrt{2}}{2}$ ជាទម្រង់ត្រីកោណមាត្រ)៖
- ម៉ូឌុល $r = \\frac{5\\sqrt{2}}{2} > 0$
- អាគុយម៉ង់ $\\theta = \\pi$ (ព្រោះជាចំនួនពិតអវិជ្ជមាន)
$$Z = \\frac{5\\sqrt{2}}{2}(-1 + 0i) = \\frac{5\\sqrt{2}}{2}(\\cos \\pi + i \\sin \\pi)$$

**ចម្លើយត្រឹមត្រូវគឺ គ. $Z = \\frac{5\\sqrt{2}}{2}(\\cos \\pi + i \\sin \\pi)$**
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
    even with nested braces or complex expressions for plain text fallback.
    """
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
            parts[i] = re.sub(r"\n{2,}$", "\n", parts[i])
            parts[i] = re.sub(r"^\n{2,}", "\n", parts[i])

    result = "```".join(parts)
    result = re.sub(r"\n{2,}```", "\n```", result)
    result = re.sub(r"```\n{2,}", "```\n", result)
    return result.strip()


def format_math_telegram(text: str) -> str:
    """
    Sanitizes any LaTeX math expressions into clean Unicode math for Telegram text fallback.
    """
    if not text:
        return ""

    text = sanitize_brackets_and_symbols(text)
    text = text.replace("$$", "").replace("$", "")

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

    text = re.sub(r"\\log_?\{?(\d+)\}?", lambda m: "log" + "".join(subs.get(c, c) for c in m.group(1)), text)
    text = re.sub(r"\\ln", "ln", text)
    text = re.sub(r"\\log", "log", text)

    text = replace_latex_fractions_and_roots(text)

    text = re.sub(r"\\int_?\{?([^}^\s\\]*)\}?\^\{?([^}^\s\\]*)\}?", r"∫[\1 → \2] ", text)
    text = re.sub(r"\\int0\^\{?([^}^\s\\]*)\}?", r"∫[0 → \1] ", text)
    text = re.sub(r"\\int", "∫", text)

    text = re.sub(r"\\lim_\{([^}]+)\}", r"lim(\1)", text)
    text = re.sub(r"\\lim", "lim", text)

    text = text.replace("\\begin{cases}", "").replace("\\end{cases}", "")
    text = text.replace("\\begin{bmatrix}", "").replace("\\end{bmatrix}", "")

    text = re.sub(r"\\text\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\mathbf\{([^}]*)\}", r"\1", text)

    text = re.sub(r"\^\{([0-9nx\+\-]+)\}", lambda m: "".join(sups.get(c, c) for c in m.group(1)), text)
    text = re.sub(r"\^([0-9nx\+\-])", lambda m: sups.get(m.group(1), "^" + m.group(1)), text)

    text = re.sub(r"\\([a-zA-Z]+)", r"\1", text)
    text = re.sub(r"```\s*```", "", text)
    text = compact_vertical_spacing(text)

    return text.strip()


class GeminiSolver:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.primary_model = model or os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.model = self.primary_model
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
        Sends question/exercise to Gemini API and returns (success, markdown_latex_text).
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

        default_photo_prompt = (
            "សូមដោះស្រាយលំហាត់ក្នុងរូបភាពនេះឱ្យបានចប់សព្វគ្រប់ ១០០% គ្រប់លំហាត់ទាំងអស់ "
            "ដោយពន្យល់ឱ្យបានក្បោះក្បាយលម្អិតតាមដំណាក់កាលច្បាស់ៗ (○ ដំណាក់កាលទី ១, ○ ដំណាក់កាលទី ២...) "
            "ដើម្បីឱ្យអ្នកមើលឆាប់យល់ និងបញ្ចប់ដោយចម្លើយចុងក្រោយពេញលេញជានិច្ច (ហាមដាច់ខាតកុំឱ្យដាច់ចម្លើយ)។ "
            "រូបមន្ត និងសមីការគណិតវិទ្យាត្រូវសរសេរជា LaTeX ($...$ សម្រាប់ inline និង $$...$$ សម្រាប់ display equation "
            "ប្រភាគប្រើ \\frac{}{} ជានិច្ច) និងបញ្ចប់ដោយចម្លើយត្រឹមត្រូវ (ឧ. «**ចម្លើយត្រឹមត្រូវគឺ គ. ...**»)។ "
            "រាល់លំហាត់នីមួយៗត្រូវដោះស្រាយឱ្យចប់សព្វគ្រប់ ១០០% ដោយមានចម្លើយចុងក្រោយ និងបំបែកលំហាត់នីមួយៗដោយបន្ទាត់ផ្តេក --- ជានិច្ច (១ លំហាត់ = ១ ផ្នែកដាច់ដោយឡែក)។"
        )
        text_content = prompt.strip() if prompt else default_photo_prompt
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
                        return True, raw_text.strip()
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
            texts = [p.get("text", "") for p in parts if "text" in p and not p.get("thought", False)]
            reply = "\n".join(texts).strip()

            if not reply:
                texts = [p.get("text", "") for p in parts if "text" in p]
                reply = "\n".join(texts).strip()

            if not reply:
                return False, "⚠️ មិនមានអត្ថបទចម្លើយ (Empty response text)."
            return True, reply
        except Exception as e:
            return False, f"⚠️ កំហុសទាញយកទិន្នន័យ: {str(e)}"
