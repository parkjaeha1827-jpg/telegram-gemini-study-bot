"""
Telegram Bot Core Handler
Handles routing, commands, image processing, and responses for Telegram updates.
Renders Khmer academic solutions to crisp PNG images with KaTeX math and sends via sendPhoto.
Multi-exercise answers are strictly split by exercise boundary (1 Exercise = 1 Full-Page Image).
"""

import os
import re
import html
import requests
from typing import Dict, Any, List, Optional, Union
from gemini_solver import GeminiSolver, format_math_telegram
from renderer import render_solution_to_png, split_solution_into_cards
from voice_service import text_to_speech
from video_service import detect_video_url, extract_video_info, fetch_video_buffer, clean_unwanted_thai

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
        reply_to_message_id: Optional[int] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: Optional[str] = "Markdown"
    ) -> bool:
        """
        Sends message to Telegram chat.
        Automatically splits messages longer than 4000 chars.
        Tries specified parse_mode first; if entity parsing fails, falls back to plain text.
        Guarantees no unwanted Thai language mixes with Khmer.
        """
        text = clean_unwanted_thai(text)
        chunks = self._chunk_message(text, max_chars=3900)
        total_chunks = len(chunks)

        for idx, chunk in enumerate(chunks):
            header = f"*(ភាគ {idx+1}/{total_chunks})*\n\n" if total_chunks > 1 and parse_mode == "Markdown" else ""
            msg_text = header + chunk

            payload = {
                "chat_id": chat_id,
                "text": msg_text,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if reply_to_message_id and idx == 0:
                payload["reply_to_message_id"] = reply_to_message_id
            if reply_markup and idx == (total_chunks - 1):
                payload["reply_markup"] = reply_markup

            try:
                resp = requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=20)
                if resp.status_code != 200:
                    # Retry without formatting if Telegram entity parsing failed
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

    def send_voice(
        self,
        chat_id: int,
        voice_bytes: bytes,
        caption: Optional[str] = None,
        reply_to_message_id: Optional[int] = None
    ) -> bool:
        """Sends an audio file as a playable voice message via sendVoice."""
        try:
            data = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption
            if reply_to_message_id:
                data["reply_to_message_id"] = reply_to_message_id

            files = {
                "voice": ("voice.mp3", voice_bytes, "audio/mpeg")
            }

            resp = requests.post(
                f"{self.base_url}/sendVoice",
                data=data,
                files=files,
                timeout=35
            )
            if resp.status_code == 200:
                return True
            print(f"Error sending voice ({resp.status_code}): {resp.text}")
            return False
        except Exception as e:
            print(f"Exception sending voice: {e}")
            return False

    def send_video(
        self,
        chat_id: int,
        video: Union[str, bytes],
        caption: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
        supports_streaming: bool = True,
        parse_mode: Optional[str] = "HTML"
    ) -> bool:
        """
        Sends video to Telegram chat via sendVideo.
        Supports direct video URL (zero-RAM streaming) or bytes (memory buffer).
        """
        try:
            if isinstance(video, str):
                # Step 1: Direct URL passing (Telegram downloads directly from source, 0 RAM on Vercel)
                payload: Dict[str, Any] = {
                    "chat_id": chat_id,
                    "video": video,
                    "supports_streaming": supports_streaming
                }
                if caption:
                    payload["caption"] = caption
                if parse_mode:
                    payload["parse_mode"] = parse_mode
                if reply_to_message_id:
                    payload["reply_to_message_id"] = reply_to_message_id
                if reply_markup:
                    payload["reply_markup"] = reply_markup

                resp = requests.post(f"{self.base_url}/sendVideo", json=payload, timeout=30)
                if resp.status_code == 200 and resp.json().get("ok"):
                    return True
                print(f"[send_video] Direct URL failed ({resp.status_code}): {resp.text}")
                return False
            else:
                # Step 2: In-memory video buffer upload via multipart/form-data (< 48MB)
                data: Dict[str, Any] = {
                    "chat_id": chat_id,
                    "supports_streaming": "true" if supports_streaming else "false"
                }
                if caption:
                    data["caption"] = caption
                if parse_mode:
                    data["parse_mode"] = parse_mode
                if reply_to_message_id:
                    data["reply_to_message_id"] = reply_to_message_id
                if reply_markup:
                    data["reply_markup"] = json.dumps(reply_markup)

                files = {
                    "video": ("video.mp4", video, "video/mp4")
                }
                resp = requests.post(f"{self.base_url}/sendVideo", data=data, files=files, timeout=60)
                if resp.status_code == 200 and resp.json().get("ok"):
                    return True
                print(f"[send_video] Buffer upload failed ({resp.status_code}): {resp.text}")
                return False
        except Exception as e:
            print(f"[send_video] Exception sending video: {e}")
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

    def _is_academic_math_or_exercise(self, text: str) -> bool:
        """Detects if text contains LaTeX math equations or structured exercise stages."""
        if "$$" in text or r"\frac" in text or r"\int" in text or r"\sqrt" in text:
            return True
        if re.search(r'\$[^\$\n]{2,}\$', text):
            return True
        if "○ ដំណាក់កាល" in text or "ដំណាក់កាលទី" in text or "ចម្លើយត្រឹមត្រូវគឺ" in text:
            return True
        if re.search(r'\*\*(?:(?:លំហាត់|វិញ្ញាសា|[០-៩\d]+[\.\:\)]))', text):
            return True
        return False

    def _send_rendered_solution_or_text(
        self,
        chat_id: int,
        answer: str,
        message_id: Optional[int] = None,
        force_photo: bool = False
    ) -> None:
        """
        Sends conversational chat messages directly as natural text.
        For academic exercises or LaTeX math, renders into high-DPI KaTeX images (1 card per exercise)
        and sends via sendPhoto. Falls back to formatted Telegram text if rendering fails.
        """
        # If it's natural conversation (not homework/math), reply immediately with clean text
        if not force_photo and not self._is_academic_math_or_exercise(answer):
            self.send_message(chat_id, answer, reply_to_message_id=message_id)
            return

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

    def _handle_video_download(
        self,
        chat_id: int,
        message_id: int,
        video_url: str,
        platform_code: str
    ) -> None:
        """
        Handles video downloading for TikTok, Facebook, YouTube, CapCut, Pinterest.
        Features zero-disk serverless streaming, fallback memory buffer, and inline keyboard.
        """
        self.send_chat_action(chat_id, "upload_video")

        info = extract_video_info(video_url, platform_code)
        if not info or not info.get("direct_url"):
            self.send_message(
                chat_id,
                "❌ <b>មិនអាចទាញយកវីដេអូបានទេ</b>\n\n"
                "សូមពិនិត្យមើលថាតើតំណភ្ជាប់វីដេអូនេះជាសាធារណៈ (Public) ឬយ៉ាងណា "
                "ហើយព្យាយាមសាកល្បងម្ដងទៀត។",
                reply_to_message_id=message_id,
                parse_mode="HTML"
            )
            return

        direct_url = info["direct_url"]
        platform_names = {
            "tiktok": "TikTok",
            "facebook": "Facebook",
            "youtube": "YouTube",
            "capcut": "CapCut",
            "pinterest": "Pinterest"
        }
        p_name = platform_names.get(platform_code.lower(), platform_code.capitalize())
        raw_title = info.get("title") or f"វីដេអូ {p_name}"
        clean_title = clean_unwanted_thai(re.sub(r'[\r\n\t]+', ' ', raw_title)).strip()
        if len(clean_title) > 85:
            clean_title = clean_title[:82] + "..."
        safe_title = html.escape(clean_title)
        safe_author = html.escape(clean_unwanted_thai(info.get("author")) or "N/A")

        if platform_code.lower() == "capcut":
            quality_text = "Original Template HD"
        else:
            quality_text = "គ្មាន Watermark (No Logo) • HD"

        caption = (
            f"🎬 <b>{safe_title}</b>\n"
            f"👤 <b>អ្នកបង្កើត:</b> {safe_author}\n"
            f"📌 <b>ប្រភព:</b> {p_name}\n"
            f"✨ <b>កម្រិត:</b> {quality_text}\n\n"
            f"🤖 <i>ទាញយកដោយជោគជ័យតាមរយៈ Telegram Study Bot</i>"
        )

        # Step 1: Direct URL Streaming (Zero RAM on Vercel)
        self.send_chat_action(chat_id, "upload_video")
        if self.send_video(chat_id, direct_url, caption=caption, reply_to_message_id=message_id, parse_mode="HTML"):
            return

        # Step 2: In-Memory Buffer Fallback (< 48MB)
        self.send_chat_action(chat_id, "upload_video")
        video_bytes, total_size = fetch_video_buffer(direct_url, max_bytes=48 * 1024 * 1024, original_url=video_url)
        if video_bytes:
            if self.send_video(chat_id, video_bytes, caption=caption, reply_to_message_id=message_id, parse_mode="HTML"):
                return

        # Step 3: Inline Keyboard Button Fallback (if >50MB or if direct transfer fails)
        size_str = f"{total_size / (1024 * 1024):.1f} MB" if total_size else "> 50 MB"
        button_caption = (
            f"🎬 <b>{safe_title}</b>\n"
            f"👤 <b>អ្នកបង្កើត:</b> {safe_author}\n"
            f"📌 <b>ប្រភព:</b> {p_name}\n"
            f"📦 <b>ទំហំ:</b> {size_str}\n"
            f"✨ <b>កម្រិត:</b> {quality_text}\n\n"
            f"⚡ <i>ដោយសារទំហំវីដេអូធំ (Telegram Bot កំណត់ផ្ញើត្រឹម 50MB) សូមចុចប៊ូតុងខាងក្រោមដើម្បីទាញយកផ្ទាល់បានលឿនបំផុត៖</i>"
        )
        reply_markup = {
            "inline_keyboard": [
                [{"text": "⬇️ ទាញយកវីដេអូផ្ទាល់ (HD)", "url": direct_url}]
            ]
        }
        self.send_message(
            chat_id,
            button_caption,
            reply_to_message_id=message_id,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

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
        voice = message.get("voice")
        audio = message.get("audio")
        caption = (message.get("caption") or "").strip()

        # Handle Commands
        if text.startswith("/"):
            self._handle_command(chat_id, message_id, text)
            return

        # Handle Video Downloader (TikTok, Facebook, YouTube, CapCut, Pinterest)
        video_text = text or caption
        video_detection = detect_video_url(video_text)
        if video_detection:
            matched_url, platform_code = video_detection
            self._handle_video_download(chat_id, message_id, matched_url, platform_code)
            return

        # Handle Voice / Audio (Voice-to-Voice Conversation)
        if voice or audio:
            self.send_chat_action(chat_id, "record_voice")

            media_obj = voice or audio
            file_id = media_obj.get("file_id")

            audio_bytes = self.get_file_bytes(file_id)
            if not audio_bytes:
                self.send_message(
                    chat_id,
                    "❌ មិនអាចទាញយកសារសំឡេងបានទេ។ សូមព្យាយាមផ្ញើម្តងទៀត។",
                    reply_to_message_id=message_id
                )
                return

            voice_prompt = caption or (
                "ស្ដាប់ និងបំប្លែងសំឡេង (ភាសាខ្មែរ ឬភាសាបរទេស) ឱ្យបានគ្រប់ម៉ាត់ជាមុនសិន "
                "រួចវិភាគថាតើអ្នកសួរកំពុងសួរមេរៀន/ច្បាប់/ពេទ្យ/វិញ្ញាសាប្រឡង ឬកំពុងជជែកលេង៖\n"
                "១. បើជាសំណួរមេរៀន ច្បាប់ ពេទ្យ ឬវិញ្ញាសាប្រឡង៖ ត្រូវឆ្លើយឱ្យបានត្រឹមត្រូវ ១០០% ច្បាស់លាស់ តាមជំហាន គ្មានការស្មានឡើយ។\n"
                "២. បើជាការជជែកលេងទូទៅ៖ ឆ្លើយតបខ្លីៗ ធម្មជាតិ រស់រវើក មានអារម្មណ៍ដូចមនុស្សពិតៗ (ចេះលួងលោម ឌឺដង ឬស្ដីបន្ទោសតាមសមរម្យ)។\n"
                "៣. ច្បាប់ភាសា៖ បើអ្នកនិយាយនិយាយភាសាខ្មែរ ត្រូវតបជាភាសាខ្មែរ។ បើនិយាយភាសាបរទេស ត្រូវតបជាភាសាបរទេសនោះវិញភ្លាមៗ។\n"
                "៤. សំខាន់បំផុត៖ ហាមប្រើសញ្ញា Markdown (*, #, `) ឬ Emoji ក្នុងចម្លើយដាច់ខាត ដើម្បីកុំឱ្យម៉ាស៊ីនអានសំឡេងអានឈ្មោះសញ្ញាទាំងនោះ។"
            )

            mime_type = "audio/ogg" if voice else "audio/mp3"
            success, answer = self.solver.solve(
                prompt=voice_prompt,
                image_bytes=audio_bytes,
                mime_type=mime_type,
                chat_id=chat_id,
                is_voice=True
            )

            if not success:
                self.send_message(chat_id, answer, reply_to_message_id=message_id)
                return

            # Check if this is a long academic/lesson answer
            is_long_academic = len(answer) > 280 or any(kw in answer for kw in ["ដំណាក់កាល", "រូបមន្ត", "មាត្រា", "ច្បាប់", "សមីការ", "\\frac", "$"])

            if is_long_academic:
                # Dual send: Send full formatted text in chat AND concise voice summary
                self.send_message(chat_id, answer, reply_to_message_id=message_id)

                # Create a clean spoken text for voice audio
                spoken_text = answer[:260].rsplit(' ', 1)[0] + "..." if len(answer) > 260 else answer
                self.send_chat_action(chat_id, "record_voice")
                speech_bytes = text_to_speech(spoken_text)
                if speech_bytes:
                    self.send_voice(chat_id, speech_bytes, reply_to_message_id=message_id)
            else:
                self.send_chat_action(chat_id, "record_voice")
                speech_bytes = text_to_speech(answer)
                if speech_bytes:
                    sent = self.send_voice(chat_id, speech_bytes, reply_to_message_id=message_id)
                    if not sent:
                        self.send_message(chat_id, answer, reply_to_message_id=message_id)
                else:
                    self.send_message(chat_id, answer, reply_to_message_id=message_id)
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
                "សូមដោះស្រាយលំហាត់ក្នុងរូបភាពនេះឱ្យបានចប់សព្វគ្រប់ ១០០% គ្រប់លំហាត់ទាំងអស់ "
                "ដោយពន្យល់ឱ្យបានក្បោះក្បាយលម្អិតតាមដំណាក់កាលច្បាស់ៗ (○ ដំណាក់កាលទី ១, ○ ដំណាក់កាលទី ២...) "
                "ដើម្បីឱ្យអ្នកមើលឆាប់យល់ និងបញ្ចប់ដោយចម្លើយចុងក្រោយពេញលេញជានិច្ច (ហាមដាច់ខាតកុំឱ្យដាច់ចម្លើយ)។ "
                "រូបមន្ត និងសមីការគណិតវិទ្យាត្រូវសរសេរជា LaTeX ($...$ សម្រាប់ inline និង $$...$$ សម្រាប់ display equation "
                "ប្រភាគប្រើ \\frac{}{} ជានិច្ច) និងបញ្ចប់ដោយចម្លើយត្រឹមត្រូវ (ឧ. «**ចម្លើយត្រឹមត្រូវគឺ គ. ...**»)។ "
                "រាល់លំហាត់នីមួយៗត្រូវដោះស្រាយឱ្យចប់សព្វគ្រប់ ១០០% ដោយមានចម្លើយចុងក្រោយ និងបំបែកលំហាត់នីមួយៗដោយបន្ទាត់ផ្តេក --- ជានិច្ច (១ លំហាត់ = ១ ផ្នែកដាច់ដោយឡែក)។"
            )

            success, answer = self.solver.solve(
                prompt=caption or default_photo_prompt,
                image_bytes=image_bytes,
                mime_type="image/jpeg",
                chat_id=chat_id
            )
            if not success:
                self.send_message(chat_id, answer, reply_to_message_id=message_id)
                return

            self._send_rendered_solution_or_text(chat_id, answer, message_id, force_photo=True)
            return

        # Handle Text (Written Question / Math / Science Exercise / Emotional Chat)
        if text:
            self.send_chat_action(chat_id, "typing")
            success, answer = self.solver.solve(prompt=text, chat_id=chat_id)
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
                "📚 *សមត្ថភាពចម្បង៖*\n"
                "• 🎬 *ទាញយកវីដេអូគ្មាន Logo (HD Video Downloader):* គ្រាន់តែផ្ញើ Link មកពី TikTok, Facebook (Reels/Watch), YouTube (Shorts/Video), CapCut ឬ Pinterest នោះ Bot នឹងទាញយកវីដេអូ .mp4 គ្មាន Watermark កម្រិត HD ជូនភ្លាមៗ!\n"
                "• 🎙️ *សន្ទនាដោយសំឡេង (Voice-to-Voice):* ផ្ញើសារសំឡេង (Voice message) មកទីនេះ Bot នឹងស្ដាប់យល់ និងឆ្លើយតបជាសំឡេងមនុស្សពិតៗភ្លាមៗ (គាំទ្រទាំងភាសាខ្មែរ និងភាសាបរទេស)!\n"
                "• 📸 *ផ្ញើរូបភាពលំហាត់* (ថតរូបពីសៀវភៅ ឬក្រដាសប្រឡង)\n"
                "• ✍️ *សរសេរសំណួរ ឬសមីការ* ផ្ទាល់ចូលក្នុងប្រអប់សារ\n"
                "• 🎨 *Render ចម្លើយជារូបភាព HD (KaTeX):* ១ លំហាត់ = ១ រូបភាពពេញទំព័រធំច្បាស់ រូបមន្តគណិតវិទ្យាមានភាគយក របារប្រភាគ និងភាគបែងត្រឹមត្រូវ ១០០%\n"
                "• 🔬 ដោះស្រាយគ្រប់មុខវិជ្ជា៖ គណិត, រូប, គីមី, ជីវៈ, អក្សរសាស្ត្រខ្មែរ, អង់គ្លេស, ប្រវត្តិ, ភូមិ...\n"
                "• 💡 បង្ហាញរូបមន្ត គន្លឹះ និងជំហានដោះស្រាយច្បាស់ៗមួយជំហានម្តងៗ ព្រមទាំងចម្លើយចុងក្រោយពេញលេញ\n\n"
                "🚀 *របៀបប្រើ៖* ផ្ញើ Link វីដេអូ, ផ្ញើសារសំឡេង, ថតរូបលំហាត់ ឬវាយអត្ថបទសំណួរផ្ញើមកទីនេះភ្លាមៗ!\n\n"
                "បញ្ជាបន្ថែម៖ /subjects (មុខវិជ្ជា) | /clear (លុបប្រវត្តិ) | /help (ជំនួយ) | /about (ព័ត៌មាន Bot)"
            )
            self.send_message(chat_id, welcome_msg, reply_to_message_id=message_id)

        elif cmd in ["/help", "/help@yourbot"]:
            help_msg = (
                "📖 *របៀបប្រើប្រាស់ Bot ឲ្យទទួលបានលទ្ធផលល្អបំផុត៖*\n\n"
                "1️⃣ *ទាញយកវីដេអូគ្មាន Logo (HD):*\n"
                "• ចម្លង Link ពី TikTok, Facebook (Reels/Watch), YouTube (Shorts/Video), CapCut ឬ Pinterest រួចផ្ញើចូលក្នុងប្រអប់សារ\n"
                "• Bot នឹងទាញយកវីដេអូ .mp4 គ្មាន Watermark កម្រិត HD ជូនដោយស្វ័យប្រវត្តិ!\n\n"
                "2️⃣ *ដោះស្រាយតាមរូបភាព (Photo):*\n"
                "• ថតរូបលំហាត់ឲ្យចំ ត្រង់ និងមានពន្លឺគ្រប់គ្រាន់\n"
                "• អាចសរសេរ Caption បន្ថែមប្រសិនបើចង់ឲ្យដោះស្រាយតែសំណួរណាជាក់លាក់ (ឧ. «ដោះស្រាយតែលំហាត់លេខ ៣»)\n\n"
                "3️⃣ *សន្ទនាដោយសំឡេង (Voice-to-Voice):*\n"
                "• ចុច Record Voice និយាយសំណួរ ឬជជែកលេងជាភាសាខ្មែរ ឬភាសាបរទេស នោះ Bot នឹងឆ្លើយតបជាសំឡេងមនុស្សពិតៗមកវិញ\n\n"
                "4️⃣ *ដោះស្រាយតាមអត្ថបទ (Text):*\n"
                "• វាយប្រធានលំហាត់ ឬសំណួរចូលដោយផ្ទាល់\n"
                "• អាចសួរបញ្ជាក់ចំណុចមិនយល់បន្ថែមបាន\n\n"
                "5️⃣ *ទម្រង់រូបភាព Rendered HD:*\n"
                "• Bot នឹង Render ចម្លើយ ១ លំហាត់ = ១ រូបភាពកាតពណ៌សធំច្បាស់ពេញទំព័រ ដោយមានក្បាលលំហាត់ ជំហានដោះស្រាយ និងចម្លើយចុងក្រោយពេញលេញ មិនដាច់ពាក់កណ្តាលទីឡើយ!\n\n"
                "💡 *ចំណាំ:* Bot ត្រូវបានរចនាឡើងដើម្បីពន្យល់ឲ្យយល់ និងជួយសម្រួលដល់ការសិក្សាស្រាវជ្រាវ!"
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

        elif cmd in ["/clear", "/reset", "/clear@yourbot", "/reset@yourbot"]:
            self.solver.clear_history(chat_id)
            self.send_message(
                chat_id,
                "🧹 អូខេ! ខ្ញុំបានលុបប្រវត្តិការសន្ទនាមុនៗអស់ហើយ! តោះ ចាប់ផ្ដើមនិយាយគ្នាសារថ្មី 😊",
                reply_to_message_id=message_id
            )

        else:
            self.send_message(
                chat_id,
                "❓ មិនស្គាល់ពាក្យបញ្ជានេះទេ។ សូមចុច /help ឬ /start ដើម្បីមើលការណែនាំ។",
                reply_to_message_id=message_id
            )
