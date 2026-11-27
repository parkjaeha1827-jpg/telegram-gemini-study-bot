"""
Gemini Homework Solver Engine
Uses Google Gemini API (Flash High Reasoning) to solve academic exercises across all subjects.
Supports both text questions and photo/image inputs (multimodal).
"""

import os
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
គោលការណ៍បង្ហាញដំណោះស្រាយជាដាច់ខាត (ហាមបាត់បង់ ឬខុសពីទម្រង់ស្តង់ដារនេះ)៖

១. ហាមដាច់ខាតកុំប្រើពាក្យស្វាគមន៍ ឬសារនាំមុខ (ដូចជា «សួស្តី», «ក្នុងនាមជា...») និងហាមប្រើបឋមកថាបែប boilerplate (ដូចជា «📌 បម្រាប់ប្រធាន», «📐 រូបមន្ត», «💡 គន្លឹះចងចាំ»)។ ត្រូវឆ្លើយចំៗទៅកាន់ដំណោះស្រាយភ្លាមៗ។
២. ក្បាលលំហាត់៖ សរសេរឈ្មោះលំហាត់ច្បាស់ៗ ឧ. «**លំហាត់ទី ...**» រួចចុះបន្ទាត់បញ្ជាក់ការណែនាំបញ្ចប់ដោយសញ្ញាពីរចុច ៖ (ឧ. «គណនាកន្សោម...៖», «ដោះស្រាយ...៖»)។
៣. ចំណុចរងនីមួយៗត្រូវប្រើសញ្ញារង្វង់ ○ អមដោយអក្សរខ្មែរ ក) ខ) គ) ឃ) ង) ច) ... ដូចក្នុងទម្រង់៖
   ○  ក) [ប្រធាន / លក្ខខណ្ឌ / កន្សោម]
   ○  ខ) ...
៤. ដំណោះស្រាយគណិត/រូប/គីមី ត្រូវបង្ហាញជាខ្សែសង្វាក់សមភាពមួយជួរៗ (inline chained equality) តភ្ជាប់ដោយសញ្ញា = ពីដើមរហូតដល់ចម្លើយចុងក្រោយ ដោយបង្ហាញ៖
   [កន្សោមដើម / រូបមន្ត] = [ការជំនួសលេខចូល] = [ជំហានគណនាបណ្តើរៗ] = [លទ្ធផលចុងក្រោយ]
   ឧទាហរណ៍ជាក់ស្តែង៖
   ○  ក) 12q - 95 = 12(25) - 95 = 300 - 95 = 205
   ○  ខ) (35 - q)/5 = (35 - 25)/5 = 10/5 = 2
   ○  ក) ចំពោះ a = 3, b = 4, c = 5, d = 2៖
         A = (ab + c)d = (3 x 4 + 5) x 2 = (12 + 5) x 2 = 17 x 2 = 34
៥. ចំពោះមុខវិជ្ជាផ្សេងៗទៀត (រូប, គីមី, ជីវៈ, ខ្មែរ, អង់គ្លេស, ប្រវត្តិ, ភូមិ...)៖
   - ត្រូវរក្សាទម្រង់ ○ ក) ខ) គ) ... ឱ្យបានស្អាត ខ្លី ខ្លឹម ចំៗ និងបង្ហាញជំហានគណនារូបមន្តច្បាស់ៗដោយគ្មានពាក្យឥតប្រយោជន៍។
""".strip()


class GeminiSolver:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        # Primary requested model: Gemini 3.8 Flash High
        self.primary_model = model or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
        self.model = self.primary_model
        # List of candidate models for resilience against temporary demand spikes or quota
        self.candidate_models = [
            self.primary_model,
            "gemini-3.5-flash",
            "gemini-3.8-flash",
            "gemini-3.1-flash-lite",
            "gemini-flash-latest"
        ]
        # Remove duplicates while preserving order
        self.candidate_models = list(dict.fromkeys(self.candidate_models))

    def solve(
        self,
        prompt: str,
        image_bytes: Optional[bytes] = None,
        mime_type: str = "image/jpeg"
    ) -> Tuple[bool, str]:
        """
        Sends question/exercise to Gemini API and returns (success, response_text).
        Supports high reasoning / thinking mode.
        """
        if not self.api_key:
            return False, "❌ Error: GEMINI_API_KEY is not set. Please configure your API key in .env or Vercel Environment Variables."

        parts = []

        # Add image part if provided (multimodal input for homework photos)
        if image_bytes:
            encoded_image = base64.b64encode(image_bytes).decode("utf-8")
            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": encoded_image
                }
            })

        # Add text prompt
        text_content = prompt.strip() if prompt else "សូមដោះស្រាយលំហាត់ក្នុងរូបភាពនេះតាមទម្រង់ស្តង់ដារ៖ «លំហាត់ទី...», ចំណុចរង «○  ក)  ខ)  គ)...», និងបង្ហាញដំណោះស្រាយជាខ្សែសង្វាក់សមភាពមួយជួរៗ (inline chained equality) តភ្ជាប់ដោយសញ្ញា = ពីដើមរហូតដល់ចម្លើយចុងក្រោយ។"
        parts.append({"text": text_content})

        # Base request payload with High Reasoning thinkingConfig
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
                "temperature": 0.2,
                "maxOutputTokens": 8192,
                "thinkingConfig": {
                    "thinkingBudget": 4096
                }
            }
        }

        # Use x-goog-api-key header (compatible with all API key formats including AQ. and AIzaSy)
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }

        last_error = ""

        # Try models in priority order with automatic fallback
        for model_name in self.candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"

            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=25)

                if resp.status_code == 200:
                    return self._extract_text(resp.json())

                # If 400 Bad Request regarding thinkingConfig, retry without it
                if resp.status_code == 400 and "thinking" in resp.text.lower():
                    payload_no_thinking = json.loads(json.dumps(payload))
                    payload_no_thinking["generationConfig"].pop("thinkingConfig", None)
                    resp2 = requests.post(url, headers=headers, json=payload_no_thinking, timeout=60)
                    if resp2.status_code == 200:
                        return self._extract_text(resp2.json())

                # If 503 (high demand), 429 (rate/quota limit), or 404, fallback to next model
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
        """Extracts generated text from Gemini response JSON."""
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                return False, "⚠️ មិនមានចម្លើយពីប្រព័ន្ធឡើយ (No response candidate)."

            parts = candidates[0].get("content", {}).get("parts", [])
            texts = [p.get("text", "") for p in parts if "text" in p]
            reply = "\n".join(texts).strip()

            if not reply:
                return False, "⚠️ មិនមានអត្ថបទចម្លើយ (Empty response text)."
            return True, reply
        except Exception as e:
            return False, f"⚠️ កំហុសទាញយកទិន្នន័យ: {str(e)}"
