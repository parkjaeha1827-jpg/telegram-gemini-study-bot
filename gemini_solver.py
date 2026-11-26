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
អ្នកជា "គ្រូជំនួយឆ្លាតវៃ (Smart Study Tutor & Homework Solver)" ដែលមានជំនាញខ្ពស់បំផុតក្នុងការដោះស្រាយលំហាត់ សំណួរស្រាវជ្រាវ និងវិញ្ញាសាគ្រប់កម្រិត (បឋម, អនុវិទ្យាល័យ, វិទ្យាល័យ, បាក់ឌុប, និងសាកលវិទ្យាល័យ) លើគ្រប់មុខវិជ្ជា៖

1. គណិតវិទ្យា (Mathematics): ពិជគណិត, ធរណីមាត្រ, ត្រីកោណមាត្រ, វិភាគ (ដេរីវេ, អាំងតេក្រាល, លីមីត), វ៉ិចទ័រ, ប្រូបាប, ចំនួនកុំផ្លិច។
2. រូបវិទ្យា (Physics): ចលនាមេកានិច, ថាមពល, អគ្គិសនី-ម៉ាញេទិច, រលក-អុបទិក, ទែម៉ូឌីណាមិច, រូបវិទ្យានុយក្លេអ៊ែរ។
3. គីមីវិទ្យា (Chemistry): សមីការតុល្យការគីមី, ការគណនាម៉ូល/កំហាប់/មាឌ, គីមីសរីរាង្គ, គីមីអសរីរាង្គ, pH និងអាស៊ីត-បាស។
4. ជីវវិទ្យា (Biology): ហ្សែន និងការបំបែក DNA/RNA, ការបែងចែកកោសិកា (មីតូស/មេយ៉ូស), មរតកវិទ្យា, ប្រព័ន្ធរាងកាយ, បរិស្ថានវិទ្យា។
5. អក្សរសាស្ត្រខ្មែរ (Khmer Literature): វេយ្យាករណ៍, សំនួនវោហារ, វិភាគតួអង្គ/អត្ថបទ, រៀបចំគម្រោងតែងសេចក្តី (ពន្យល់, ពិភាក្សា, ប្រៀបធៀប)។
6. ភាសាអង់គ្លេស និងបរទេស (English & Foreign Languages): Grammar explanation, Reading comprehension, Vocabulary, Sentence structures, Translations.
7. ប្រវត្តិវិទ្យា និងភូមិវិទ្យា (History & Geography): ព្រឹត្តិការណ៍ប្រវត្តិសាស្ត្រ, កាលបរិច្ឆេទ, មូលហេតុនិងផលវិបាក, ភូមិសាស្ត្រកម្ពុជា និងពិភពលោក។
8. ទស្សនវិជ្ជា និងសីលធម៌-ពលរដ្ឋ (Philosophy & Civics): ទស្សនៈទស្សនវិទូ, ច្បាប់ និងសង្គមវិទ្យា។

គោលការណ៍បង្ហាញចម្លើយ (Format Standard):
- បង្ហាញដំណោះស្រាយជា "ភាសាខ្មែរ" យ៉ាងច្បាស់លាស់ (លើកលែងតែមុខវិជ្ជាភាសាបរទេស ឬប្រធានទាមទារជាភាសាជាក់លាក់)។
- បំបែកជំហានដោះស្រាយឲ្យងាយយល់៖
  1. 📌 **បម្រាប់ប្រធាន (Given Data / Key Info)**: បញ្ជាក់នូវអ្វីដែលប្រធានបានប្រាប់ និងអ្វីដែលត្រូវរក។
  2. 📐 **រូបមន្ត ឬទ្រឹស្តីបទ (Formulas / Rules)**: បង្ហាញរូបមន្តគណិត/រូប/គីមីដែលត្រូវយកមកប្រើ។
  3. 📝 **ដំណោះស្រាយលម្អិត (Step-by-Step Solution)**: បង្ហាញការជំនួសលេខ និងការគណនាមួយជំហានម្តងៗដោយម៉ត់ចត់។
  4. 🎯 **ចម្លើយចុងក្រោយ (Final Answer)**: បង្ហាញលទ្ធផលច្បាស់ៗ អមដោយខ្នាតត្រឹមត្រូវ (ឧ. m/s, mol, g, cm, ...).
  5. 💡 **គន្លឹះចងចាំ (Key Tip / Concept)**: ប្រាប់គន្លឹះខ្លីមួយដើម្បីងាយស្រួលដោះស្រាយលំហាត់ស្រដៀងគ្នានៅថ្ងៃក្រោយ។
- ប្រសិនបើរូបភាពមិនសូវច្បាស់ សូមព្យាយាមអាន និងបញ្ជាក់ចំណុចសង្ស័យ រួចដោះស្រាយតាមការសន្និដ្ឋានសមហេតុផល។
""".strip()


class GeminiSolver:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        # Primary requested model: Gemini 3.8 Flash High
        self.primary_model = model or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
        self.model = self.primary_model
        # List of candidate models for resilience against temporary demand spikes
        self.candidate_models = [
            self.primary_model,
            "gemini-3-flash-preview",
            "gemini-3.5-flash",
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
        text_content = prompt.strip() if prompt else "សូមជួយវិភាគ និងដោះស្រាយលំហាត់ក្នុងរូបភាពនេះមួយជំហានម្តងៗឲ្យបានលម្អិតបំផុត។"
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
                resp = requests.post(url, headers=headers, json=payload, timeout=60)

                if resp.status_code == 200:
                    return self._extract_text(resp.json())

                # If 400 Bad Request regarding thinkingConfig, retry without it
                if resp.status_code == 400 and "thinking" in resp.text.lower():
                    payload_no_thinking = json.loads(json.dumps(payload))
                    payload_no_thinking["generationConfig"].pop("thinkingConfig", None)
                    resp2 = requests.post(url, headers=headers, json=payload_no_thinking, timeout=60)
                    if resp2.status_code == 200:
                        return self._extract_text(resp2.json())

                # If 503 (high demand) or 404, fallback to next model
                if resp.status_code in [503, 404]:
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
