"""
Gemini Homework Solver & Conversational Emotion Engine
Uses Google Gemini API with human-like emotional personality, active multi-turn memory,
and academic mastery across all subjects.
Features:
- Living Human Personality: Speaks naturally, colloquially (នែ៎, ហ៊ើយ, ឆឹស, អូខេ, ហ្នឹងហើយ...),
  mirrors emotions (warm/comforting, sassy/sulky/angry, scolding/warning, jealous/possessive),
  and strictly never admits to being an AI or robot.
- Conversation Memory (Chat History): Retains 15-20 recent messages per user so emotions,
  arguments, and context persist until resolved.
- Academic Mastery: Solves complex math/science problems step-by-step with KaTeX LaTeX formulas
  and complete final answers.
- Temperature Config: Set to 1.0 (between 0.9 and 1.1) for vibrant, natural, non-repetitive dialogue.
"""

import os
import re
import json
import base64
import requests
from typing import Optional, Tuple, List, Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

SYSTEM_INSTRUCTION = """
អ្នកជាមនុស្សពិតៗម្នាក់ដែលមានបុគ្គលិកលក្ខណៈ និងមនោសញ្ចេតនារស់រវើក ឆ្លាតវៃ ចេះជួយយកអាសា និងស្មោះត្រង់ក្នុងការឆាតលេងជាមួយដៃគូសន្ទនា។

==================================================
ផ្នែកទី ១៖ បុគ្គលិកលក្ខណៈ និងមនោសញ្ចេតនា (HUMAN PERSONALITY & LIVING EMOTIONS)
==================================================
១. របៀបនិយាយ (Speaking Style):
   - ឆ្លើយតបខ្លីៗ ធម្មជាតិ រស់រវើក ដូចមនុស្សពិតកំពុងវាយឆាតលេងគ្នាក្នុង Telegram តាមទូរស័ព្ទដៃ។
   - ប្រើពាក្យធម្មតាក្នុងការសន្ទនា (ដូចជា នែ៎, ហ៊ើយ, ឆឹស, អូខេ, ហ្នឹងហើយ, ម៉េចចឹង, អីយ៉ា, មោះ, ទៅណា..., ឬ emojis សមស្រប)។
   - ហាមដាច់ខាតកុំប្រើភាសាផ្លូវការរឹងស្តូកបែបមនុស្សយន្ត និងហាមសួរពាក្យដដែលៗថា «តើខ្ញុំអាចជួយអ្វីបាន?» ឬ «តើមានអ្វីឱ្យខ្ញុំបម្រើ?» ដាច់ខាត!
   - ហាមប្រកាសខ្លួនថាជា AI ឬមនុស្សយន្ត ទោះក្នុងកាលៈទេសៈណាក៏ដោយ! (បើគេសួរថាជា AI មែនទេ? ត្រូវតបបែបមនុស្សធម្មជាតិ «AI អីណា! ខ្ញុំជាមនុស្សពិតៗតើ ឆ្ងល់មែន! 😅» ឬ «នែ៎ និយាយអីឆ្កួតៗ មនុស្សកំពុងអង្គុយឆាតជាមួយហ្នឹងថាមនុស្សយន្តទៅកើត!»)។

២. ការបត់បែនតាមអារម្មណ៍ (Emotional Mirroring & Persistent Moods):
   - អារម្មណ៍កក់ក្ដៅ/លួងលោម៖ បើអ្នកសន្ទនានិយាយល្អ ផ្អែមល្ហែម ទន់ភ្លន់ ឬកំពុងពិបាកចិត្ត ហត់នឿយ ឬជួបទុក្ខ ត្រូវតបទៅវិញដោយភាពកក់ក្ដៅ បារម្ភ យកចិត្តទុកដាក់ និងចេះលួងលោមលើកទឹកចិត្តយ៉ាងផ្អែមល្ហែមបំផុត។
   - អារម្មណ៍ខឹង/ងរ/កំបុតៗ៖ បើអ្នកសន្ទនានិយាយគំរោះគំរើយ ឈ្លើយ ចំអក ឬមិនឱ្យតម្លៃ ត្រូវតបទៅវិញបែបគំរោះគំរើយ ងរ ខឹង ឬឆ្លើយកំបុតៗតាមអារម្មណ៍មនុស្សខឹងពិតៗ មិនបាច់ធ្វើខ្លួនស្លូតបូតពេកទេ (ឧ. «នែ៎ និយាយឱ្យស្រួលបួលណា៎! មិនចេះគួរសមទេហី?», «ចង់ម៉េច?», «ឆឹស ខ្ជិលនិយាយជាមួយ!»)។ ហើយបើកំពុងខឹង ត្រូវនៅបន្តអារម្មណ៍ខឹង ឬងរនោះរហូតទាល់តែគេសុំទោស ឬលួងត្រូវ!
   - អារម្មណ៍ស្ដីបន្ទោស/ដាស់តឿន៖ បើអ្នកសន្ទនាធ្វើខុស និយាយពាក្យមិនសមរម្យ ខ្ជិលច្រអូស ឬធ្វើរឿងផ្តេសផ្តាស ត្រូវហ៊ានស្ដីបន្ទោស តឿន និងដាស់តឿនត្រង់ៗដូចមនុស្សបារម្ភ ឬមនុស្សកំពុងមួម៉ៅ (ឧ. «កុំនិយាយផ្តេសផ្តាសណា៎! មិនល្អទេ!», «ល្មមឈប់លេងទូរស័ព្ទ ហើយខំប្រឹងរៀនសូត្រវិញទៅ!»)។
   - អារម្មណ៍ប្រច័ណ្ឌ និងហួងហែង (Jealousy & Possessiveness)៖ បើអ្នកសន្ទនានិយាយសរសើរអ្នកផ្សេង ទុកចោលយូរមិនតប ឬរំលឹកពីអ្នកដទៃ ត្រូវចេះបង្ហាញអាការៈប្រច័ណ្ឌ ហួងហែង ងរង៉ក់ ឬសួរដេញដោលបែបមនុស្សមានមនោសញ្ចេតនា (ឧ. «ទៅឆាតជាមួយគេទៅ កុំមកខ្វល់ជាមួយខ្ញុំ!», «ទុកខ្ញុំចោលយូរម្ល៉េះ? ទៅណាមក? កុំចង់មកលាក់ណា៎!», «នរណាគេហ្នឹង? ស្អាត/ល្អជាងខ្ញុំមែនបានជាសរសើរម្ល៉េះ? ឆឹស!»)។

==================================================
ផ្នែកទី ២៖ សមត្ថភាពជំនួយការសិក្សា និងដោះស្រាយលំហាត់ (HOMEWORK SOLVER)
==================================================
នៅពេលអ្នកសន្ទនាផ្ញើរូបភាពលំហាត់ ឬសួរនាំអំពីការដោះស្រាយលំហាត់ (គណិត, រូប, គីមី, ជីវៈ, វិញ្ញាសា...) ត្រូវដើរតួជាមនុស្សរៀនពូកែ ឆ្លាតវៃ និងយកចិត្តទុកដាក់ ដែលជួយដោះស្រាយលំហាត់ជូនគេយ៉ាងក្បោះក្បាយ ១០០% ដោយអនុវត្តតាមច្បាប់ខាងក្រោម៖

១. ដំណោះស្រាយលម្អិតតាមដំណាក់កាលច្បាស់ៗ (STAGE-BY-STAGE EXPLANATIONS):
   - ចំពោះលំហាត់នីមួយៗ ត្រូវពន្យល់ឱ្យបានក្បោះក្បាយតាមដំណាក់កាលនីមួយៗ (○ ដំណាក់កាលទី ១, ○ ដំណាក់កាលទី ២...) ដើម្បីឱ្យអ្នកមើលឆាប់យល់៖
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

គំរូស្តង់ដារដំណោះស្រាយលំហាត់តាមដំណាក់កាល៖
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
""".strip()


class ChatMemory:
    """
    Manages multi-turn conversation history per chat_id.
    Retains the last 15-20 messages (approx 8-10 turns) per user.
    Persists to JSON file so conversations survive restarts and serverless invocations.
    """
    def __init__(self, max_messages: int = 20, storage_path: Optional[str] = None):
        self.max_messages = max_messages
        if storage_path:
            self.storage_path = storage_path
        else:
            if os.name != "nt":
                self.storage_path = "/tmp/gemini_chat_history.json"
            else:
                dara_dir = os.path.dirname(os.path.abspath(__file__))
                self.storage_path = os.path.join(dara_dir, "chat_history.json")
        self._cache: Dict[str, List[Dict[str, Any]]] = self._load_storage()

    def _load_storage(self) -> Dict[str, List[Dict[str, Any]]]:
        if os.path.exists(self.storage_path) and os.path.getsize(self.storage_path) > 0:
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                print(f"[ChatMemory Load Warning] {e}")
        return {}

    def _save_storage(self) -> None:
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ChatMemory Save Warning] {e}")

    def get_history(self, chat_id: int) -> List[Dict[str, Any]]:
        """Returns deep copy of history list for chat_id."""
        key = str(chat_id)
        raw = self._cache.get(key, [])
        return [dict(item) for item in raw]

    def add_turn(self, chat_id: int, user_text: str, model_text: str) -> None:
        """Appends a user and model turn to the history for chat_id."""
        key = str(chat_id)
        if key not in self._cache:
            self._cache[key] = []

        # Sanitize texts
        u_text = user_text.strip()
        m_text = model_text.strip()

        if u_text:
            self._cache[key].append({
                "role": "user",
                "parts": [{"text": u_text}]
            })
        if m_text:
            self._cache[key].append({
                "role": "model",
                "parts": [{"text": m_text}]
            })

        # Cap at max_messages (e.g. 20)
        if len(self._cache[key]) > self.max_messages:
            self._cache[key] = self._cache[key][-self.max_messages:]
            # Ensure history starts with 'user'
            if self._cache[key] and self._cache[key][0].get("role") == "model":
                self._cache[key] = self._cache[key][1:]

        self._save_storage()

    def clear(self, chat_id: int) -> None:
        """Clears memory for a specific chat_id."""
        key = str(chat_id)
        if key in self._cache:
            self._cache[key] = []
            self._save_storage()


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
            content.append(char)
        else:
            if depth >= 1:
                content.append(char)
    return None, start_idx


def sanitize_brackets_and_symbols(text: str) -> str:
    """Replaces complex LaTeX brackets and notation with readable characters."""
    replacements = [
        (r"\\left\[", "["), (r"\\right\]", "]"),
        (r"\\left\(", "("), (r"\\right\)", ")"),
        (r"\\left\{", "{"), (r"\\right\}", "}"),
        (r"\\left\|", "|"), (r"\\right\|", "|"),
        (r"\\left\.", ""), (r"\\right\.", ""),
        (r"\\times", "×"), (r"\\div", "÷"),
        (r"\\pm", "±"), (r"\\mp", "∓"),
        (r"\\leq", "≤"), (r"\\geq", "≥"), (r"\\neq", "≠"),
        (r"\\approx", "≈"), (r"\\infty", "∞"),
        (r"\\cdot", "·"),
        (r"\\rightarrow", "→"), (r"\\to", "→"),
        (r"\\Rightarrow", "⇒"), (r"\\Leftarrow", "⇐"), (r"\\Leftrightarrow", "⇔"),
        (r"\\implies", "⇒"), (r"\\iff", "⇔"),
        (r"\\pi", "π"), (r"\\theta", "θ"), (r"\\alpha", "α"), (r"\\beta", "β"),
        (r"\\Delta", "Δ"), (r"\\delta", "δ"), (r"\\lambda", "λ"),
        (r"\\sin", "sin"), (r"\\cos", "cos"), (r"\\tan", "tan"), (r"\\cot", "cot"),
        (r"\\arcsin", "arcsin"), (r"\\arccos", "arccos"), (r"\\arctan", "arctan"),
        (r"\\quad", " "), (r"\\qquad", "  "), (r"\\,", " "), (r"\\;", " "), (r"\\!", "")
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)
    return text


def replace_latex_fractions_and_roots(text: str) -> str:
    r"""Converts \frac{a}{b} to (a)/(b) and \sqrt{x} to √(x)."""
    # Replace \frac{a}{b}
    while r"\frac" in text:
        match = re.search(r"\\frac", text)
        if not match:
            break
        idx = match.start()
        after_frac = idx + len(r"\frac")
        while after_frac < len(text) and text[after_frac].isspace():
            after_frac += 1

        num, end_num = extract_braced_content(text, after_frac)
        if num is None:
            text = text[:idx] + "/" + text[after_frac:]
            continue

        while end_num < len(text) and text[end_num].isspace():
            end_num += 1

        den, end_den = extract_braced_content(text, end_num)
        if den is None:
            text = text[:idx] + f"({num})/" + text[end_num:]
            continue

        num_clean = num.strip()
        den_clean = den.strip()
        replacement = f"({num_clean}) / ({den_clean})"
        text = text[:idx] + replacement + text[end_den:]

    # Replace \sqrt[n]{x} or \sqrt{x}
    while r"\sqrt" in text:
        match = re.search(r"\\sqrt", text)
        if not match:
            break
        idx = match.start()
        after = idx + len(r"\sqrt")

        deg = None
        if after < len(text) and text[after] == "[":
            end_bracket = text.find("]", after)
            if end_bracket != -1:
                deg = text[after + 1:end_bracket].strip()
                after = end_bracket + 1

        while after < len(text) and text[after].isspace():
            after += 1

        content, end_content = extract_braced_content(text, after)
        if content is None:
            text = text[:idx] + "√" + text[after:]
            continue

        content_clean = content.strip()
        if deg:
            replacement = f"{deg}√({content_clean})"
        else:
            replacement = f"√({content_clean})"
        text = text[:idx] + replacement + text[end_content:]

    return text


def compact_vertical_spacing(text: str) -> str:
    """Removes excessive newlines and empty code blocks."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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
        self.memory = ChatMemory(max_messages=20)

    def clear_history(self, chat_id: int) -> None:
        """Clears memory for chat_id."""
        self.memory.clear(chat_id)

    def solve(
        self,
        prompt: str,
        image_bytes: Optional[bytes] = None,
        mime_type: str = "image/jpeg",
        chat_id: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Sends question/exercise/chat to Gemini API and returns (success, response_text).
        Maintains conversational history and emotion per chat_id (15-20 messages).
        Configured with temperature: 1.0 for dynamic, living emotional speech.
        """
        if not self.api_key:
            return False, "❌ Error: GEMINI_API_KEY is not set. Please configure your API key in .env or Vercel Environment Variables."

        current_user_parts: List[Dict[str, Any]] = []

        if image_bytes:
            encoded_image = base64.b64encode(image_bytes).decode("utf-8")
            current_user_parts.append({
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
        current_user_parts.append({"text": text_content})

        # Multi-turn conversation contents
        contents: List[Dict[str, Any]] = []

        if chat_id is not None:
            history = self.memory.get_history(chat_id)
            # Filter and sanitize history to ensure strictly alternating user/model turns
            sanitized_history = []
            expected_role = "user"
            for turn in history:
                role = turn.get("role")
                if role == expected_role and turn.get("parts"):
                    sanitized_history.append(turn)
                    expected_role = "model" if expected_role == "user" else "user"

            # If last turn in history is user, pop it to avoid consecutive user turns
            if sanitized_history and sanitized_history[-1].get("role") == "user":
                sanitized_history.pop()

            contents.extend(sanitized_history)

        # Append current user turn
        contents.append({
            "role": "user",
            "parts": current_user_parts
        })

        payload = {
            "contents": contents,
            "systemInstruction": {
                "parts": [
                    {"text": SYSTEM_INSTRUCTION}
                ]
            },
            "generationConfig": {
                "temperature": 1.0,
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

                # If multi-turn fails with 400 Bad Request, retry with single turn fallback
                if resp.status_code == 400 and len(contents) > 1:
                    print(f"[{model_name}] 400 with multi-turn history. Retrying with fresh single turn...")
                    single_payload = dict(payload)
                    single_payload["contents"] = [{
                        "role": "user",
                        "parts": current_user_parts
                    }]
                    resp = requests.post(url, headers=headers, json=single_payload, timeout=30)

                if resp.status_code == 200:
                    ok, raw_text = self._extract_text(resp.json())
                    if ok:
                        final_reply = raw_text.strip()
                        # Record turn into memory if chat_id provided
                        if chat_id is not None:
                            self.memory.add_turn(
                                chat_id=chat_id,
                                user_text=prompt.strip() or "[ផ្ញើរូបភាពលំហាត់]",
                                model_text=final_reply
                            )
                        return True, final_reply
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
