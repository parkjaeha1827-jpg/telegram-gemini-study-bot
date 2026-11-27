"""
Telegram Bot Core Handler
Handles routing, commands, image processing, and responses for Telegram updates.
Renders Khmer academic solutions to crisp PNG images with KaTeX math and sends via sendPhoto.
Multi-exercise answers are strictly split by exercise boundary (1 Exercise = 1 Full-Page Image).
"""

import os
import re
import requests
from typing import Dict, Any, List, Optional
from gemini_solver import GeminiSolver, format_math_telegram
from renderer import render_solution_to_png, split_solution_into_cards

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramBot:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.base_url = f"{TELEGRAM_API_BASE}/bot{self.token}"
        self.file_url = f"{TELEGRAM_API_BASE}/file/bot{self.token}"
        self.solver = GeminiSolver()

    def send_chat_action(self, chat_id: int, action: str = "typing") -> None:
        """Sends chat action indicator (typing, upload_photo) to let user know bot is working."""
        try:
            requests.post(
                f"{self.base_url}/sendChatAction",
                json={"chat_id": chat_id, "action": action},
                timeout=5
            )
        except Exception:
            pass

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_message_id: Optional[int] = None
    ) -> bool:
        """
        Sends message to Telegram chat.
        Automatically splits messages longer than 4000 chars.
        Tries Markdown first; if entity parsing fails, falls back to plain text.
        """
        chunks = self._chunk_message(text, max_chars=3900)
        total_chunks = len(chunks)

        for idx, chunk in enumerate(chunks):
            header = f"*(ភាគ {idx+1}/{total_chunks})*\n\n" if total_chunks > 1 else ""
            msg_text = header + chunk

            payload = {
                "chat_id": chat_id,
                "text": msg_text,
                "parse_mode": "Markdown"
            }
            if reply_to_message_id and idx == 0:
                payload["reply_to_message_id"] = reply_to_message_id

            try:
                resp = requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=20)
                if resp.status_code != 200:
                    # Retry without Markdown formatting if Telegram entity parsing failed
                    payload.pop("parse_mode", None)
                    plain_header = f"(ភាគ {idx+1}/{total_chunks})\n\n" if total_chunks > 1 else ""
                    payload["text"] = plain_header + chunk
                    requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=20)
            except Exception as e:
                print(f"Error sending message chunk: {e}")
                return False

        return True

    def send_photo(
        self,
        chat_id: int,
        photo_bytes: bytes,
        caption: Optional[str] = None,
        reply_to_message_id: Optional[int] = None
    ) -> bool:
        """
        Sends high-DPI photo to Telegram chat via multipart form-data (sendPhoto).
        """
        try:
            data = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption
            if reply_to_message_id:
                data["reply_to_message_id"] = reply_to_message_id

            files = {
                "photo": ("solution.png", photo_bytes, "image/png")
            }

            resp = requests.post(
                f"{self.base_url}/sendPhoto",
                data=data,
                files=files,
                timeout=30
            )
            if resp.status_code == 200:
                return True
            print(f"Error sending photo ({resp.status_code}): {resp.text}")
            return False
        except Exception as e:
            print(f"Exception sending photo: {e}")
            return False

    def get_file_bytes(self, file_id: str) -> Optional[bytes]:
        """Downloads photo file from Telegram servers."""
        try:
            resp = requests.get(f"{self.base_url}/getFile", params={"file_id": file_id}, timeout=15)
            if resp.status_code != 200:
                return None
            file_path = resp.json().get("result", {}).get("file_path")
            if not file_path:
                return None

            download_url = f"{self.file_url}/{file_path}"
            file_resp = requests.get(download_url, timeout=30)
            if file_resp.status_code == 200:
                return file_resp.content
            return None
        except Exception as e:
            print(f"Error downloading file: {e}")
            return None

    def _chunk_message(self, text: str, max_chars: int = 3900) -> List[str]:
        """
        Splits long text into clean chunks at line breaks.
        Maintains open code block (```) state across chunks so Markdown parsing never fails.
        """
        if len(text) <= max_chars:
            return [text]

        chunks = []
        current = []
        current_len = 0
        in_code_block = False

        for line in text.split("\n"):
            is_code_toggle = line.strip().startswith("```")
            line_len = len(line) + 1

            if current_len + line_len > max_chars:
                if current:
                    chunk_text = "\n".join(current)
                    if in_code_block:
                        chunk_text += "\n```"
                    chunks.append(chunk_text)

                    if in_code_block:
                        current = ["```", line]
                        current_len = 4 + line_len
                    else:
                        current = [line]
                        current_len = line_len
                else:
                    chunks.append(line[:max_chars])
                    current = [line[max_chars:]]
                    current_len = len(current[0])
            else:
                current.append(line)
                current_len += line_len

            if is_code_toggle:
                in_code_block = not in_code_block

        if current:
            chunk_text = "\n".join(current)
            if in_code_block:
                chunk_text += "\n```"
            chunks.append(chunk_text)

        return chunks

    def _send_rendered_solution_or_text(
        self,
        chat_id: int,
        answer: str,
        message_id: Optional[int] = None
    ) -> None:
        """
        Attempts to render the solution into high-DPI KaTeX images (strictly 1 card per exercise)
        and sends via sendPhoto so each exercise is 1 complete page with head and final answer intact.
        Falls back to formatted Telegram text message if rendering fails or times out.
        """
        self.send_chat_action(chat_id, "upload_photo")
        cards = split_solution_into_cards(answer)
        total_cards = len(cards)

        sent_photos = 0
        for idx, card in enumerate(cards):
            png_bytes = render_solution_to_png(card)
            if png_bytes:
                # Extract clean exercise title if available
                title_match = re.search(r'\*\*(?:(?:លំហាត់ទី\s*)?([០-៩\d]+[\.\:\)]\s*[^\n\*]+))\*\*', card)
                if title_match:
                    clean_title = title_match.group(1).strip()
                    caption = f"📐 លំហាត់ {clean_title}"
                    if len(caption) > 100:
                        caption = caption[:97] + "..."
                elif total_cards > 1:
                    caption = f"📐 ដំណោះស្រាយលំហាត់ (ភាគ {idx+1}/{total_cards})"
                else:
                    caption = "📐 ដំណោះស្រាយលំហាត់ (Google Gemini AI & KaTeX)"

                reply_id = message_id if idx == 0 else None
                if self.send_photo(chat_id, png_bytes, caption=caption, reply_to_message_id=reply_id):
                    sent_photos += 1

        # If photo rendering failed completely, fallback to text
        if sent_photos == 0:
            fallback_text = format_math_telegram(answer)
            self.send_message(chat_id, fallback_text, reply_to_message_id=message_id)

    def handle_update(self, update: Dict[str, Any]) -> None:
        """Processes an incoming Telegram Update dictionary."""
        message = update.get("message") or update.get("edited_message")
        if not message:
            return

        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")
        if not chat_id:
            return

        text = (message.get("text") or "").strip()
        photo = message.get("photo")
        caption = (message.get("caption") or "").strip()

        # Handle Commands
        if text.startswith("/"):
            self._handle_command(chat_id, message_id, text)
            return

        # Handle Photo (Homework Image)
        if photo:
            self.send_chat_action(chat_id, "typing")

            # Select highest resolution photo (last in the list)
            best_photo = photo[-1]
            file_id = best_photo.get("file_id")

            self.send_message(
                chat_id,
                "🔍 *កំពុងពិនិត្យរូបភាព និងគិតដោះស្រាយយ៉ាងម៉ត់ចត់...*\n_សូមរង់ចាំបន្តិច ប្រព័ន្ធ Gemini Flash High Reasoning កំពុងវិភាគ និង Render រូបមន្ត KaTeX (១ លំហាត់ = ១ ទំព័រ)... ⏳_",
                reply_to_message_id=message_id
            )

            image_bytes = self.get_file_bytes(file_id)
            if not image_bytes:
                self.send_message(
                    chat_id,
                    "❌ មិនអាចទាញយករូបភាពបានទេ។ សូមព្យាយាមផ្ញើរូបភាពម្តងទៀត។",
                    reply_to_message_id=message_id
                )
                return

            default_photo_prompt = (
                "សូមដោះស្រាយលំហាត់ក្នុងរូបភាពនេះឱ្យបានចប់សព្វគ្រប់ ១០០% គ្រប់លំហាត់ទាំងអស់ (មានក្បាលលំហាត់ «**[លេខរៀង]. [ប្រធាន]**», "
                "ដំណោះស្រាយខ្លី ខ្លឹម សម្រួលកត្តារួមឱ្យងាយយល់ និងចម្លើយចុងក្រោយពេញលេញ ហាមដាច់ខាតកុំឱ្យដាច់ក្បាលដាច់កន្ទុយ)។ "
                "រូបមន្ត និងសមីការគណិតវិទ្យាត្រូវសរសេរជា LaTeX ($...$ សម្រាប់ inline និង $$...$$ សម្រាប់ display equation "
                "ប្រភាគប្រើ \\frac{}{} ជានិច្ច) និងបញ្ចប់ដោយចម្លើយត្រឹមត្រូវ (ឧ. «**ចម្លើយត្រឹមត្រូវគឺ គ. ...**»)។ "
                "រាល់លំហាត់នីមួយៗត្រូវដោះស្រាយឱ្យចប់សព្វគ្រប់ ១០០% ដោយមានចម្លើយចុងក្រោយ និងបំបែកលំហាត់នីមួយៗដោយបន្ទាត់ផ្តេក --- ជានិច្ច (១ លំហាត់ = ១ ផ្នែកដាច់ដោយឡែក)។"
            )

            success, answer = self.solver.solve(
                prompt=caption or default_photo_prompt,
                image_bytes=image_bytes,
                mime_type="image/jpeg"
            )
            if not success:
                self.send_message(chat_id, answer, reply_to_message_id=message_id)
                return

            self._send_rendered_solution_or_text(chat_id, answer, message_id)
            return

        # Handle Text (Written Question / Math / Science Exercise)
        if text:
            self.send_chat_action(chat_id, "typing")
            success, answer = self.solver.solve(prompt=text)
            if not success:
                self.send_message(chat_id, answer, reply_to_message_id=message_id)
                return

            self._send_rendered_solution_or_text(chat_id, answer, message_id)
            return

    def _handle_command(self, chat_id: int, message_id: int, command_text: str) -> None:
        """Handles bot commands."""
        cmd = command_text.split()[0].lower()

        if cmd in ["/start", "/start@yourbot"]:
            welcome_msg = (
                "👋 *សួស្តីប្អូនៗ និងសិស្សានុសិស្សទាំងអស់គ្នា!*\n\n"
                "ខ្ញុំជា *Telegram Study Bot* ជំនួយការដោះស្រាយលំហាត់គ្រប់មុខវិជ្ជា បំពាក់ដោយបច្ចេកវិទ្យា *Google Gemini Flash* 🧠✨\n\n"
                "📚 *សមត្ថភាពដោះស្រាយលំហាត់៖*\n"
                "• 📸 *ផ្ញើរូបភាពលំហាត់* (ថតរូបពីសៀវភៅ ឬក្រដាសប្រឡង)\n"
                "• ✍️ *សរសេរសំណួរ ឬសមីការ* ផ្ទាល់ចូលក្នុងប្រអប់សារ\n"
                "• 🎨 *Render ចម្លើយជារូបភាព HD (KaTeX):* ១ លំហាត់ = ១ រូបភាពពេញទំព័រធំច្បាស់ រូបមន្តគណិតវិទ្យាមានភាគយក របារប្រភាគ និងភាគបែងត្រឹមត្រូវ ១០០%\n"
                "• 🔬 ដោះស្រាយគ្រប់មុខវិជ្ជា៖ គណិត, រូប, គីមី, ជីវៈ, អក្សរសាស្ត្រខ្មែរ, អង់គ្លេស, ប្រវត្តិ, ភូមិ...\n"
                "• 💡 បង្ហាញរូបមន្ត គន្លឹះ និងជំហានដោះស្រាយច្បាស់ៗមួយជំហានម្តងៗ ព្រមទាំងចម្លើយចុងក្រោយពេញលេញ\n\n"
                "🚀 *របៀបប្រើ៖* គ្រាន់តែថតរូបលំហាត់ ឬវាយអត្ថបទសំណួរផ្ញើមកទីនេះភ្លាមៗ!\n\n"
                "បញ្ជាបន្ថែម៖ /subjects (មើលមុខវិជ្ជា) | /help (ជំនួយ) | /about (ព័ត៌មាន Bot)"
            )
            self.send_message(chat_id, welcome_msg, reply_to_message_id=message_id)

        elif cmd in ["/help", "/help@yourbot"]:
            help_msg = (
                "📖 *របៀបប្រើប្រាស់ Bot ឲ្យទទួលបានលទ្ធផលល្អបំផុត៖*\n\n"
                "1️⃣ *ដោះស្រាយតាមរូបភាព (Photo):*\n"
                "• ថតរូបលំហាត់ឲ្យចំ ត្រង់ និងមានពន្លឺគ្រប់គ្រាន់\n"
                "• អាចសរសេរ Caption បន្ថែមប្រសិនបើចង់ឲ្យដោះស្រាយតែសំណួរណាជាក់លាក់ (ឧ. «ដោះស្រាយតែលំហាត់លេខ ៣»)\n\n"
                "2️⃣ *ដោះស្រាយតាមអត្ថបទ (Text):*\n"
                "• វាយប្រធានលំហាត់ ឬសំណួរចូលដោយផ្ទាល់\n"
                "• អាចសួរបញ្ជាក់ចំណុចមិនយល់បន្ថែមបាន\n\n"
                "3️⃣ *ទម្រង់រូបភាព Rendered HD:*\n"
                "• Bot នឹង Render ចម្លើយ ១ លំហាត់ = ១ រូបភាពកាតពណ៌សធំច្បាស់ពេញទំព័រ ដោយមានក្បាលលំហាត់ ជំហានដោះស្រាយ និងចម្លើយចុងក្រោយពេញលេញ មិនដាច់ពាក់កណ្តាលទីឡើយ!\n\n"
                "💡 *ចំណាំ:* Bot ត្រូវបានរចនាឡើងដើម្បីពន្យល់ឲ្យយល់ មិនមែនគ្រាន់តែបង្ហាញចម្លើយរួចស្រេចនោះទេ!"
            )
            self.send_message(chat_id, help_msg, reply_to_message_id=message_id)

        elif cmd in ["/subjects", "/subjects@yourbot"]:
            subjects_msg = (
                "📚 *បញ្ជីមុខវិជ្ជាដែលគាំទ្រ (All Supported Subjects):*\n\n"
                "1. 📐 *គណិតវិទ្យា (Math):* ពិជគណិត, ធរណីមាត្រ, ដេរីវេ, អាំងតេក្រាល, លីមីត, ប្រូបាប, វ៉ិចទ័រ\n"
                "2. ⚡ *រូបវិទ្យា (Physics):* មេកានិច, អគ្គិសនី, ម៉ាញេទិច, រលក, អុបទិក, ទែម៉ូឌីណាមិច\n"
                "3. 🧪 *គីមីវិទ្យា (Chemistry):* សមីការគីមី, គណនាម៉ូល, អាស៊ីត-បាស, គីមីសរីរាង្គ\n"
                "4. 🧬 *ជីវវិទ្យា (Biology):* ហ្សែន/DNA, ការបែងចែកកោសិកា, មរតកវិទ្យា, ប្រព័ន្ធអេកូឡូស៊ី\n"
                "5. 🇰🇭 *អក្សរសាស្ត្រខ្មែរ (Khmer):* តែងសេចក្តី, វិភាគអក្សរសិល្ប៍, វេយ្យាករណ៍ខ្មែរ\n"
                "6. 🇬🇧 *ភាសាអង់គ្លេស (English):* Grammar, Translation, Reading comprehension, Vocabulary\n"
                "7. 🏛 *ប្រវត្តិវិទ្យា (History):* ព្រឹត្តិការណ៍ប្រវត្តិសាស្ត្រជាតិ និងអន្តរជាតិ\n"
                "8. 🌍 *ភូមិវិទ្យា (Geography):* ភូមិសាស្ត្ររូបវន្ត សេដ្ឋកិច្ច និងប្រជាសាស្ត្រ\n"
                "9. ⚖️ *ទស្សនវិជ្ជា និងពលរដ្ឋវិទ្យា (Philosophy & Civics)*\n\n"
                "👉 ផ្ញើលំហាត់មុខវិជ្ជាណាមួយមកឥឡូវនេះ!"
            )
            self.send_message(chat_id, subjects_msg, reply_to_message_id=message_id)

        elif cmd in ["/about", "/about@yourbot"]:
            active_model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
            about_msg = (
                "🤖 *អំពី Telegram Study Bot:*\n\n"
                f"• *ម៉ូដែល AI:* Google {active_model} (High Reasoning)\n"
                "• *បច្ចេកវិទ្យា:* Vercel Serverless + Google Gemini Vision API + KaTeX High-DPI Renderer\n"
                "• *សមត្ថភាព:* ដោះស្រាយលំហាត់ សំណួរស្រាវជ្រាវ និងវិញ្ញាសាគ្រប់មុខវិជ្ជា (១ លំហាត់ = ១ ទំព័រ)\n"
                "• *ស្ថានភាព Server:* កំពុងដំណើរការ 🟢 (Online)\n\n"
                "បង្កើតឡើងដើម្បីជួយសម្រួលដល់ការសិក្សារបស់សិស្សានុសិស្សកម្ពុជា! 🇰🇭❤️"
            )
            self.send_message(chat_id, about_msg, reply_to_message_id=message_id)

        else:
            self.send_message(
                chat_id,
                "❓ មិនស្គាល់ពាក្យបញ្ជានេះទេ។ សូមចុច /help ឬ /start ដើម្បីមើលការណែនាំ។",
                reply_to_message_id=message_id
            )
