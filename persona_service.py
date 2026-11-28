"""
persona_service.py - Self-Evolving Personality & Daily Learning Engine

Features:
- Per-user Evolving Persona storage (Firebase Firestore REST API, Vercel KV / Upstash Redis REST API,
  and local /tmp persistent JSON fallback):
    * learned_vocabulary: Slang, catchphrases, jokes, and signature words the user loves
    * relationship_level & mood: Intimacy level (1-10) and live emotional state
    * user_habits & user_preferences: User's daily habits, tastes, and important life stories
    * evolution_notes: Daily personality lessons & reflections dated in Cambodia time (Asia/Phnom_Penh)
- Auto-Reflection Engine:
    * Triggers automatically every 5 messages OR during emotionally/personally significant chats
    * Calls Gemini (gemini-2.5-flash primary, with fast fallback to gemini-3.1-flash-lite)
    * Extracts structured JSON updates, strips any unwanted Thai script, deduplicates, and persists
- System Prompt Injector:
    * Formats the user's Evolving Persona + Cambodia date context for injection into every Gemini reply
"""

import os
import re
import json
import datetime
import urllib.parse
from typing import Optional, List, Dict, Any, Tuple
import requests

REFLECTION_MODELS = [
    "gemini-2.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
]

VALID_MOODS = [
    "សប្បាយ",
    "ធម្មតា",
    "ខឹង",
    "ងរ",
    "ប្រច័ណ្ឌ",
    "លួងលោម",
    "កក់ក្ដៅ",
    "ឌឺដង",
]


def _get_cambodia_now() -> datetime.datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Asia/Phnom_Penh"))
    except Exception:
        return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))


def _clean_no_thai(text: str) -> str:
    """Strictly strips Thai script (U+0E00-U+0E7F) and normalizes spaces."""
    if not text:
        return ""
    cleaned = re.sub(r'[\u0E00-\u0E7F]+', '', str(text))
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    return cleaned.strip()


def relationship_label_for_level(level: int) -> str:
    """Returns natural Khmer relationship label for intimacy level 1..10."""
    lv = max(1, min(10, int(level)))
    if lv <= 2:
        return "មិត្តភក្តិថ្មី"
    if lv <= 4:
        return "អ្នកស្គាល់ជិតស្និទ្ធ"
    if lv <= 6:
        return "មិត្តភក្តិជិតស្និទ្ធ"
    if lv <= 8:
        return "មិត្តរួមសុខរួមទុក្ខ (យល់ចិត្តខ្លាំង)"
    return "មនុស្សពិសេសបំផុត (យល់ចិត្តគ្នា ១០០%)"


def default_persona(chat_id: int) -> Dict[str, Any]:
    """Creates a fresh Evolving Persona record for a user."""
    now = _get_cambodia_now()
    return {
        "chat_id": str(chat_id),
        "learned_vocabulary": [],
        "relationship_level": 1,
        "relationship_label": relationship_label_for_level(1),
        "mood": "សប្បាយ",
        "user_habits": [],
        "user_preferences": [],
        "evolution_notes": [],
        "message_count": 0,
        "last_reflected_count": 0,
        "last_reflected_at": "",
        "last_updated_date": now.strftime("%Y-%m-%d"),
    }


def _dedupe_capped(existing: List[str], additions: List[str], max_items: int) -> List[str]:
    """Merges string lists cleanly (no Thai, case-insensitive dedupe, keeps newest within cap)."""
    result: List[str] = []
    seen = set()
    for item in list(existing or []) + list(additions or []):
        clean = _clean_no_thai(item)
        if not clean:
            continue
        key = clean.lower()
        if key not in seen:
            seen.add(key)
            result.append(clean)
    if len(result) > max_items:
        result = result[-max_items:]
    return result


class EvolvingPersonaStore:
    """
    Persistent per-user Evolving Persona storage.
    Backends:
    1. Vercel KV / Upstash Redis REST API (KV_REST_API_URL & KV_REST_API_TOKEN)
    2. Firebase Firestore REST API (FIREBASE_PROJECT_ID / FIRESTORE_PROJECT_ID)
    3. Local JSON / /tmp cache fallback
    """

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path:
            self.storage_path = storage_path
        elif os.name != "nt":
            self.storage_path = "/tmp/evolving_personas.json"
        else:
            dara_dir = os.path.dirname(os.path.abspath(__file__))
            self.storage_path = os.path.join(dara_dir, "evolving_personas.json")

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
        self._cache: Dict[str, Dict[str, Any]] = self._load_local_all()

    def _load_local_all(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.storage_path) and os.path.getsize(self.storage_path) > 0:
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                print(f"[EvolvingPersona Load Warning] {e}")
        return {}

    def _save_local_all(self) -> None:
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[EvolvingPersona Save Warning] {e}")

    def _normalize_persona(self, chat_id: int, raw: Dict[str, Any]) -> Dict[str, Any]:
        base = default_persona(chat_id)
        if not isinstance(raw, dict):
            return base
        base["learned_vocabulary"] = _dedupe_capped([], raw.get("learned_vocabulary", []), 25)
        try:
            lv = max(1, min(10, int(raw.get("relationship_level", 1))))
        except Exception:
            lv = 1
        base["relationship_level"] = lv
        base["relationship_label"] = _clean_no_thai(raw.get("relationship_label")) or relationship_label_for_level(lv)
        base["mood"] = _clean_no_thai(raw.get("mood")) or "សប្បាយ"
        base["user_habits"] = _dedupe_capped([], raw.get("user_habits", []), 20)
        base["user_preferences"] = _dedupe_capped([], raw.get("user_preferences", []), 20)
        base["evolution_notes"] = _dedupe_capped([], raw.get("evolution_notes", []), 15)
        try:
            base["message_count"] = max(0, int(raw.get("message_count", 0)))
        except Exception:
            base["message_count"] = 0
        try:
            base["last_reflected_count"] = max(0, int(raw.get("last_reflected_count", 0)))
        except Exception:
            base["last_reflected_count"] = 0
        base["last_reflected_at"] = str(raw.get("last_reflected_at") or "")
        base["last_updated_date"] = str(raw.get("last_updated_date") or base["last_updated_date"])
        return base

    def _kv_get(self, chat_id: int) -> Optional[Dict[str, Any]]:
        if not (self.kv_url and self.kv_token):
            return None
        try:
            resp = requests.get(
                f"{self.kv_url}/get/evolving_persona:{chat_id}",
                headers={"Authorization": f"Bearer {self.kv_token}"},
                timeout=3.0
            )
            if resp.status_code == 200:
                val = resp.json().get("result")
                if val:
                    parsed = json.loads(val) if isinstance(val, str) else val
                    if isinstance(parsed, dict):
                        return parsed
        except Exception as e:
            print(f"[EvolvingPersona KV Read Warning] {e}")
        return None

    def _kv_set(self, chat_id: int, persona: Dict[str, Any]) -> bool:
        if not (self.kv_url and self.kv_token):
            return False
        try:
            resp = requests.post(
                f"{self.kv_url}/set/evolving_persona:{chat_id}",
                headers={"Authorization": f"Bearer {self.kv_token}"},
                data=json.dumps(persona, ensure_ascii=False).encode("utf-8"),
                timeout=3.0
            )
            return resp.status_code == 200
        except Exception as e:
            print(f"[EvolvingPersona KV Write Warning] {e}")
            return False

    def _firestore_url(self, chat_id: int) -> str:
        url = (
            f"https://firestore.googleapis.com/v1/projects/{self.firebase_project}"
            f"/databases/(default)/documents/evolving_personas/{chat_id}"
        )
        if self.firebase_api_key:
            url += f"?key={urllib.parse.quote(self.firebase_api_key)}"
        return url

    @staticmethod
    def _to_firestore_array(items: List[str]) -> Dict[str, Any]:
        return {"arrayValue": {"values": [{"stringValue": str(x)} for x in items]}}

    @staticmethod
    def _from_firestore_array(field: Dict[str, Any]) -> List[str]:
        vals = field.get("arrayValue", {}).get("values", [])
        return [v.get("stringValue", "") for v in vals if isinstance(v, dict) and v.get("stringValue")]

    def _firestore_get(self, chat_id: int) -> Optional[Dict[str, Any]]:
        if not self.firebase_project:
            return None
        try:
            resp = requests.get(self._firestore_url(chat_id), timeout=3.0)
            if resp.status_code == 200:
                fields = resp.json().get("fields", {})
                if not fields:
                    return None
                return {
                    "chat_id": str(chat_id),
                    "learned_vocabulary": self._from_firestore_array(fields.get("learned_vocabulary", {})),
                    "relationship_level": int(fields.get("relationship_level", {}).get("integerValue", 1)),
                    "relationship_label": fields.get("relationship_label", {}).get("stringValue", ""),
                    "mood": fields.get("mood", {}).get("stringValue", "សប្បាយ"),
                    "user_habits": self._from_firestore_array(fields.get("user_habits", {})),
                    "user_preferences": self._from_firestore_array(fields.get("user_preferences", {})),
                    "evolution_notes": self._from_firestore_array(fields.get("evolution_notes", {})),
                    "message_count": int(fields.get("message_count", {}).get("integerValue", 0)),
                    "last_reflected_count": int(fields.get("last_reflected_count", {}).get("integerValue", 0)),
                    "last_reflected_at": fields.get("last_reflected_at", {}).get("stringValue", ""),
                    "last_updated_date": fields.get("last_updated_date", {}).get("stringValue", ""),
                }
        except Exception as e:
            print(f"[EvolvingPersona Firestore Read Warning] {e}")
        return None

    def _firestore_set(self, chat_id: int, persona: Dict[str, Any]) -> bool:
        if not self.firebase_project:
            return False
        try:
            body = {
                "fields": {
                    "chat_id": {"stringValue": str(chat_id)},
                    "learned_vocabulary": self._to_firestore_array(persona.get("learned_vocabulary", [])),
                    "relationship_level": {"integerValue": str(int(persona.get("relationship_level", 1)))},
                    "relationship_label": {"stringValue": str(persona.get("relationship_label", ""))},
                    "mood": {"stringValue": str(persona.get("mood", "សប្បាយ"))},
                    "user_habits": self._to_firestore_array(persona.get("user_habits", [])),
                    "user_preferences": self._to_firestore_array(persona.get("user_preferences", [])),
                    "evolution_notes": self._to_firestore_array(persona.get("evolution_notes", [])),
                    "message_count": {"integerValue": str(int(persona.get("message_count", 0)))},
                    "last_reflected_count": {"integerValue": str(int(persona.get("last_reflected_count", 0)))},
                    "last_reflected_at": {"stringValue": str(persona.get("last_reflected_at", ""))},
                    "last_updated_date": {"stringValue": str(persona.get("last_updated_date", ""))},
                }
            }
            resp = requests.patch(self._firestore_url(chat_id), json=body, timeout=3.0)
            return resp.status_code in (200, 201)
        except Exception as e:
            print(f"[EvolvingPersona Firestore Write Warning] {e}")
            return False

    def get_persona(self, chat_id: int) -> Dict[str, Any]:
        """Fetches user's Evolving Persona from cache, KV, or Firestore."""
        key = str(chat_id)
        if key not in self._cache:
            remote = self._kv_get(chat_id) or self._firestore_get(chat_id)
            if remote:
                self._cache[key] = self._normalize_persona(chat_id, remote)
                self._save_local_all()
            else:
                self._cache[key] = default_persona(chat_id)
        return dict(self._cache[key])

    def save_persona(self, chat_id: int, persona: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes and saves user's Evolving Persona to local cache and remote DB (KV / Firestore)."""
        key = str(chat_id)
        normalized = self._normalize_persona(chat_id, persona)
        normalized["last_updated_date"] = _get_cambodia_now().strftime("%Y-%m-%d")
        self._cache[key] = normalized
        self._save_local_all()
        self._kv_set(chat_id, normalized)
        self._firestore_set(chat_id, normalized)
        return dict(normalized)

    def increment_message_count(self, chat_id: int) -> Dict[str, Any]:
        """Increments total interaction count for chat_id."""
        persona = self.get_persona(chat_id)
        persona["message_count"] = int(persona.get("message_count", 0)) + 1
        return self.save_persona(chat_id, persona)


def is_significant_conversation(text: str) -> bool:
    """
    Detects emotionally or personally meaningful messages (habits, preferences,
    name/birthday, strong feelings, apologies, compliments, catchphrases) that warrant
    early Auto-Reflection before the standard 5-message interval.
    """
    if not text:
        return False
    lower = text.lower()
    triggers = [
        "ខ្ញុំឈ្មោះ", "ហៅខ្ញុំថា", "ឈ្មោះខ្ញុំ", "ខ្ញុំចូលចិត្ត", "ខ្ញុំអត់ចូលចិត្ត",
        "ខ្ញុំស្អប់", "ទម្លាប់ខ្ញុំ", "រាល់ថ្ងៃខ្ញុំ", "ថ្ងៃកំណើតខ្ញុំ", "ខ្ញុំកើតឆ្នាំ",
        "ចាំទុកផង", "កុំភ្លេច", "ខ្ញុំខឹង", "ខ្ញុំងរ", "ប្រច័ណ្ឌ", "សុំទោស",
        "នឹកណាស់", "នឹកអូន", "នឹកបង", "ស្រឡាញ់", "ពិបាកចិត្ត", "ខូចចិត្ត",
        "ហត់ណាស់", "លួងផង", "កំប្លែង", "ពាក្យប្រចាំ",
        "my name is", "call me", "i love", "i like", "i hate", "remember that",
        "i'm sad", "i am sad", "i'm angry", "sorry", "miss you", "my habit"
    ]
    return any(t in lower for t in triggers)


def should_trigger_reflection(persona: Dict[str, Any], user_text: str = "") -> bool:
    """
    Triggers Auto-Reflection:
    - Every 5 messages (message_count - last_reflected_count >= 5), OR
    - On significant personal/emotional conversation if at least 2 messages elapsed since last reflection.
    """
    msg_count = int(persona.get("message_count", 0))
    last_ref = int(persona.get("last_reflected_count", 0))
    delta = msg_count - last_ref

    if msg_count > 0 and delta >= 5:
        return True
    if msg_count >= 2 and delta >= 2 and is_significant_conversation(user_text):
        return True
    return False


def format_persona_for_system_prompt(persona: Dict[str, Any]) -> str:
    """
    Builds the dynamic Evolving Persona block injected into Gemini's System Instruction
    on every response so the bot feels genuinely alive, attentive, and evolving day by day.
    """
    if not persona:
        return ""

    vocab = persona.get("learned_vocabulary") or []
    habits = persona.get("user_habits") or []
    prefs = persona.get("user_preferences") or []
    notes = persona.get("evolution_notes") or []
    rel_lv = persona.get("relationship_level", 1)
    rel_label = persona.get("relationship_label") or relationship_label_for_level(rel_lv)
    mood = persona.get("mood") or "សប្បាយ"
    msg_count = persona.get("message_count", 0)
    last_date = persona.get("last_updated_date") or _get_cambodia_now().strftime("%Y-%m-%d")

    vocab_str = ", ".join(vocab[-12:]) if vocab else "មិនទាន់រៀនបានពាក្យពិសេសថ្មីទេ (សង្កេតតាមការសន្ទនា)"
    habits_str = "; ".join(habits[-8:]) if habits else "មិនទាន់មានកំណត់ត្រាទម្លាប់ទេ"
    prefs_str = "; ".join(prefs[-8:]) if prefs else "មិនទាន់មានកំណត់ត្រាចំណង់ចំណូលចិត្តទេ"
    notes_str = "\n  • ".join(notes[-6:]) if notes else "កំពុងចាប់ផ្ដើមស្គាល់ និងរៀនសូត្រពីចរិតអ្នកសន្ទនា"

    return (
        f"[ប្រព័ន្ធវិវត្តន៍បុគ្គលិកលក្ខណៈ និងការរៀនសូត្រប្រចាំថ្ងៃ (SELF-EVOLVING PERSONA)]:\n"
        f"❤️ កម្រិតភាពស្និទ្ធស្នាល (Relationship Level): {rel_lv}/10 ({rel_label}) | ចំនួនការសន្ទនា: {msg_count} សារ\n"
        f"🎭 អារម្មណ៍បច្ចុប្បន្ន (Current Mood): {mood}\n"
        f"🗣️ ពាក្យសម្ដី/ពាក្យប្រចាំត្រកូលដែលបានរៀន (Learned Vocabulary): {vocab_str}\n"
        f"🧩 ទម្លាប់អ្នកប្រើប្រាស់ (User Habits): {habits_str}\n"
        f"⭐ ចំណង់ចំណូលចិត្ត និងរឿងរ៉ាវសំខាន់ៗ (Preferences & Stories): {prefs_str}\n"
        f"📔 កំណត់ត្រាវិវត្តន៍ប្រចាំថ្ងៃ (Daily Evolution Notes - គិតត្រឹម {last_date}):\n"
        f"  • {notes_str}\n"
        f"ច្បាប់ប្រើប្រាស់ Evolving Persona៖\n"
        f"- ត្រូវប្រើពាក្យសម្ដី ស្ទីលនិយាយ និងចរិតដែលបានរៀនខាងលើដោយធម្មជាតិ ដូចមនុស្សពិតដែលស្គាល់ និងយល់ចិត្តគ្នាពីមួយថ្ងៃទៅមួយថ្ងៃ។\n"
        f"- បើជាសំណួរមេរៀន/ប្រឡង/ច្បាប់/ពេទ្យ (Academic Mode) ត្រូវរក្សាភាពត្រឹមត្រូវ ១០០% ជាចម្បង ហើយអាចបញ្ចេញចរិតស្និទ្ធស្នាលតែនៅឃ្លាចុងក្រោយបន្តិចប៉ុណ្ណោះ។"
    )


def _extract_json_object(raw_text: str) -> Optional[Dict[str, Any]]:
    """Safely extracts a JSON object from Gemini response text."""
    if not raw_text:
        return None
    cleaned = raw_text.strip()
    # Strip markdown json code fences if present
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # Fallback: locate first { ... } block
    m = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return None


class AutoReflectionEngine:
    """
    Analyzes recent conversations using fast Gemini (gemini-2.5-flash primary with fast fallback)
    and evolves the user's Evolving Persona automatically.
    """

    def __init__(self, store: Optional[EvolvingPersonaStore] = None, api_key: Optional[str] = None):
        self.store = store or EvolvingPersonaStore()
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")

    def reflect_and_update(
        self,
        chat_id: int,
        recent_history: List[Dict[str, Any]],
        api_key: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Runs Auto-Reflection on recent turns (up to last 10 messages) and updates Evolving Persona in DB.
        Returns the updated persona dict, or None if reflection could not run.
        """
        key = api_key or self.api_key or os.environ.get("GEMINI_API_KEY", "")
        if not key or not recent_history:
            return None

        persona = self.store.get_persona(chat_id)
        now = _get_cambodia_now()
        today_str = now.strftime("%Y-%m-%d")

        # Format recent conversation snippet cleanly
        transcript_lines = []
        for turn in recent_history[-10:]:
            role = "អ្នកប្រើ" if turn.get("role") == "user" else "Bot"
            parts = turn.get("parts") or []
            txt = " ".join(p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")).strip()
            if txt:
                # Truncate very long academic/code replies in reflection context
                if len(txt) > 350:
                    txt = txt[:347] + "..."
                transcript_lines.append(f"{role}: {txt}")

        if not transcript_lines:
            return None

        reflection_prompt = (
            f"ថ្ងៃនេះនៅកម្ពុជាគឺ {today_str}។ អ្នកជា Auto-Reflection Engine សម្រាប់វិភាគការសន្ទនាចុងក្រោយ "
            f"ដើម្បីអភិវឌ្ឍបុគ្គលិកលក្ខណៈ (Self-Evolving Persona) របស់ Bot ឱ្យកាន់តែយល់ចិត្តអ្នកប្រើប្រាស់។\n\n"
            f"[ទិន្នន័យ Persona បច្ចុប្បន្ន]:\n{json.dumps(persona, ensure_ascii=False)}\n\n"
            f"[ការសន្ទនាចុងក្រោយ]:\n" + "\n".join(transcript_lines) + "\n\n"
            f"សូមវិភាគហើយឆ្លើយតបជា JSON តែមួយគត់តាមទម្រង់ខាងក្រោម (ជាភាសាខ្មែរសុទ្ធ ហាមដាច់ខាតអក្សរថៃ)៖\n"
            "{\n"
            '  "new_vocabulary": ["ពាក្យស្លោក ពាក្យកំប្លែង ឬពាក្យប្រចាំត្រកូលថ្មីៗដែលអ្នកប្រើនិយាយ (ទទេបើគ្មាន)"],\n'
            '  "mood": "ជ្រើសមួយ: សប្បាយ | ធម្មតា | ខឹង | ងរ | ប្រច័ណ្ឌ | លួងលោម | កក់ក្ដៅ | ឌឺដង",\n'
            '  "relationship_delta": 0 ឬ 1 ឬ -1,\n'
            '  "new_habits": ["ទម្លាប់ថ្មីៗរបស់អ្នកប្រើប្រាស់ (ទទេបើគ្មាន)"],\n'
            '  "new_preferences": ["ចំណង់ចំណូលចិត្ត ឈ្មោះ ឬរឿងរ៉ាវសំខាន់ៗដែលអ្នកប្រើប្រាប់ (ទទេបើគ្មាន)"],\n'
            '  "new_evolution_note": "សង្ខេបខ្លី ១ ប្រយោគអំពីមេរៀនឬរបៀបនិយាយថ្មីដែល Bot រៀនបានពីការសន្ទនានេះ"\n'
            "}"
        )

        payload = {
            "contents": [{"role": "user", "parts": [{"text": reflection_prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 600,
                "responseMimeType": "application/json",
            },
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": key,
        }

        parsed_update: Optional[Dict[str, Any]] = None
        for model_name in REFLECTION_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=7.0)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates") or []
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts") or []
                        raw_text = "\n".join(
                            p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text") and not p.get("thought")
                        ).strip()
                        parsed_update = _extract_json_object(raw_text)
                        if parsed_update:
                            break
                elif resp.status_code in (404, 429, 503):
                    continue
            except Exception as e:
                print(f"[AutoReflection Warning ({model_name})] {e}")
                continue

        if not parsed_update:
            return None

        # Merge structured reflection insights into Evolving Persona
        persona["learned_vocabulary"] = _dedupe_capped(
            persona.get("learned_vocabulary", []),
            parsed_update.get("new_vocabulary", []) if isinstance(parsed_update.get("new_vocabulary"), list) else [],
            max_items=25
        )
        persona["user_habits"] = _dedupe_capped(
            persona.get("user_habits", []),
            parsed_update.get("new_habits", []) if isinstance(parsed_update.get("new_habits"), list) else [],
            max_items=20
        )
        persona["user_preferences"] = _dedupe_capped(
            persona.get("user_preferences", []),
            parsed_update.get("new_preferences", []) if isinstance(parsed_update.get("new_preferences"), list) else [],
            max_items=20
        )

        new_mood = _clean_no_thai(parsed_update.get("mood", ""))
        if new_mood:
            persona["mood"] = new_mood

        try:
            delta = int(parsed_update.get("relationship_delta", 0))
            delta = max(-1, min(1, delta))
        except Exception:
            delta = 0
        new_level = max(1, min(10, int(persona.get("relationship_level", 1)) + delta))
        persona["relationship_level"] = new_level
        persona["relationship_label"] = relationship_label_for_level(new_level)

        note = _clean_no_thai(parsed_update.get("new_evolution_note", ""))
        if note:
            dated_note = f"[{today_str}] {note}" if not note.startswith(f"[{today_str}]") else note
            persona["evolution_notes"] = _dedupe_capped(
                persona.get("evolution_notes", []),
                [dated_note],
                max_items=15
            )

        persona["last_reflected_count"] = int(persona.get("message_count", 0))
        persona["last_reflected_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
        return self.store.save_persona(chat_id, persona)
