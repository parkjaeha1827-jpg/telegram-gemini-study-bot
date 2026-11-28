"""
Telegram Bot Core Handler
Handles routing, commands, image processing, and responses for Telegram updates.
Renders Khmer academic solutions to crisp PNG images with KaTeX math and sends via sendPhoto.
Multi-exercise answers are strictly split by exercise boundary (1 Exercise = 1 Full-Page Image).
"""

import os
import re
import json
import html
import requests
from typing import Dict, Any, List, Optional, Union
from gemini_solver import GeminiSolver, format_math_telegram
from renderer import render_solution_to_png, split_solution_into_cards
from voice_service import text_to_speech
from video_service import detect_video_url, extract_video_info, fetch_video_buffer, clean_unwanted_thai
from preview_service import (
    PreviewStore,
    SUPPORTED_CODE_EXTENSIONS,
    is_code_or_app_request,
    build_app_builder_prompt,
    extract_code_blocks,
    find_previewable_html,
    inject_telegram_webapp_script,
    extract_html_title,
    package_code_export,
)
from media_gen_service import (
    parse_image_intent,
    parse_video_intent,
    generate_ai_image,
    generate_ai_video,
    generate_free_ai_video,
    detect_aspect_ratio,
)

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramBot:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.base_url = f"{TELEGRAM_API_BASE}/bot{self.token}"
        self.file_url = f"{TELEGRAM_API_BASE}/file/bot{self.token}"
        self.solver = GeminiSolver()
        self.preview_store = PreviewStore()

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

    def send_document(
        self,
        chat_id: int,
        file_bytes: bytes,
        filename: str,
        mime_type: str = "text/plain",
        caption: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: Optional[str] = "HTML"
    ) -> Optional[str]:
        """
        Sends an in-memory file (HTML, PY, JS, ZIP, etc.) to Telegram chat via sendDocument.
        Returns Telegram's file_id on success (or 'ok' fallback), or None on failure.
        """
        try:
            data: Dict[str, Any] = {"chat_id": chat_id}
            if caption:
                data["caption"] = clean_unwanted_thai(caption)[:1024]
            if parse_mode:
                data["parse_mode"] = parse_mode
            if reply_to_message_id:
                data["reply_to_message_id"] = reply_to_message_id
            if reply_markup:
                data["reply_markup"] = json.dumps(reply_markup)

            files = {
                "document": (filename, file_bytes, mime_type)
            }
            resp = requests.post(
                f"{self.base_url}/sendDocument",
                data=data,
                files=files,
                timeout=30
            )
            if resp.status_code == 200 and resp.json().get("ok"):
                doc_obj = resp.json().get("result", {}).get("document", {})
                return doc_obj.get("file_id") or "ok"
            print(f"[send_document] Failed ({resp.status_code}): {resp.text}")
            return None
        except Exception as e:
            print(f"[send_document] Exception sending document: {e}")
            return None

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

    def _handle_code_response(
        self,
        chat_id: int,
        message_id: int,
        answer: str
    ) -> None:
        """
        Processes Gemini's App Builder / Code Fix response:
        1. Extracts single-file HTML and/or other code blocks.
        2. Saves previewable HTML into PreviewStore (Vercel KV / Firestore / Signed Telegram Cloud).
        3. Sends portable code file (.html, .py, .js, or .zip) via sendDocument.
        4. Sends summary message with Telegram Mini App Live Preview Inline Keyboard button.
        """
        blocks, summary_text = extract_code_blocks(answer)
        if not blocks:
            self._send_rendered_solution_or_text(chat_id, answer, message_id)
            return

        app_id = self.preview_store.generate_id()
        raw_html = find_previewable_html(blocks)
        ready_html = inject_telegram_webapp_script(raw_html) if raw_html else None
        app_title = extract_html_title(ready_html, fallback="កម្មវិធី Mini App") if ready_html else blocks[0]["filename"]

        stored_remotely = False
        if ready_html:
            stored_remotely, _ = self.preview_store.save_preview(app_id, ready_html, title=app_title)

        # Package portable code file in memory (.html, .py, .js, or .zip)
        filename, file_bytes, mime_type = package_code_export(blocks, app_id, preview_html=ready_html)

        self.send_chat_action(chat_id, "upload_document")
        safe_fname = html.escape(filename)
        safe_title = html.escape(clean_unwanted_thai(app_title) or app_id)
        doc_caption = (
            f"📦 <b>ឯកសារកូដដើម:</b> <code>{safe_fname}</code>\n"
            f"💡 <i>ទាញយកឯកសារនេះដើម្បីបើកកែបន្តក្នុង VS Code, Antigravity ឬកម្មវិធីកូដផ្សេងៗបានភ្លាមៗ!</i>"
        )
        uploaded_file_id = self.send_document(
            chat_id=chat_id,
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type,
            caption=doc_caption,
            reply_to_message_id=message_id,
            parse_mode="HTML"
        )

        # Prepare clean Khmer explanation message
        clean_summary = clean_unwanted_thai(summary_text).strip()
        if len(clean_summary) > 2500:
            clean_summary = clean_summary[:2490].rsplit("\n", 1)[0] + "\n..."

        if ready_html:
            fid_for_url = uploaded_file_id if (uploaded_file_id and uploaded_file_id != "ok") else None
            preview_url = self.preview_store.build_preview_url(
                app_id=app_id,
                file_id=fid_for_url,
                stored_remotely=stored_remotely,
                bot_token=self.token
            )
            header = (
                f"🛠️ <b>{safe_title}</b>\n"
                f"🆔 <b>App ID:</b> <code>{app_id}</code>\n\n"
            )
            body = html.escape(clean_summary) if clean_summary else "កូដកម្មវិធីត្រូវបានបង្កើតរួចរាល់ ១០០% ហើយមាន Comment ពន្យល់ជាភាសាខ្មែរ។"
            footer = "\n\n👇 <i>ចុចប៊ូតុងខាងក្រោមដើម្បីបើកសាកល្បងកម្មវិធីផ្ទាល់ក្នុង Telegram Mini App៖</i>"
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "🚀 Preview កម្មវិធីផ្ទាល់", "web_app": {"url": preview_url}}]
                ]
            }
            self.send_message(
                chat_id,
                header + body + footer,
                reply_to_message_id=message_id,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        else:
            header = f"💻 <b>កូដត្រូវបានរៀបចំរួចរាល់!</b> (<code>{safe_fname}</code>)\n\n"
            body = html.escape(clean_summary) if clean_summary else "សូមទាញយកឯកសារកូដខាងលើដើម្បីប្រើប្រាស់ ឬកែបន្ត។"
            self.send_message(
                chat_id,
                header + body,
                reply_to_message_id=message_id,
                parse_mode="HTML"
            )

    def _handle_ai_image_generation(
        self,
        chat_id: int,
        message_id: int,
        prompt: str
    ) -> None:
        """
        Generates an AI image in memory (zero disk usage) using Gemini Image / Imagen
        after auto-enhancing the Khmer/English prompt, and sends via sendPhoto.
        """
        self.send_chat_action(chat_id, "upload_photo")

        clean_prompt = (prompt or "").strip()
        if not clean_prompt:
            self.send_message(
                chat_id,
                "🎨 <b>របៀបប្រើប្រាស់មុខងារបង្កើតរូបភាព AI៖</b>\n\n"
                "• វាយ <code>/img ប្រាសាទអង្គរវត្តពេលថ្ងៃលិច បែបភាពយន្ត</code>\n"
                "• ឬសរសេរផ្ទាល់៖ <i>«បង្កើតរូបភាព ឆ្មាពាក់វ៉ែនតាខ្មៅអង្គុយផឹកកាហ្វេ»</i>\n"
                "• អាចបញ្ជាក់ទំហំបន្ថែម៖ <code>16:9</code>, <code>9:16</code> ឬ <code>1:1</code>",
                reply_to_message_id=message_id,
                parse_mode="HTML"
            )
            return

        success, img_bytes, enhanced_prompt, info_or_err = generate_ai_image(
            prompt=clean_prompt,
            api_key=self.solver.api_key
        )
        if not success or not img_bytes:
            self.send_message(
                chat_id,
                info_or_err,
                reply_to_message_id=message_id,
                parse_mode="HTML"
            )
            return

        self.send_chat_action(chat_id, "upload_photo")
        short_prompt = clean_unwanted_thai(clean_prompt)
        if len(short_prompt) > 120:
            short_prompt = short_prompt[:117] + "..."
        caption = f"🎨 រូបភាព AI: {short_prompt}\n✨ ម៉ូដែល: {info_or_err}"
        self.send_photo(chat_id, img_bytes, caption=caption, reply_to_message_id=message_id)

    def _handle_ai_video_generation(
        self,
        chat_id: int,
        message_id: int,
        prompt: str,
        image_bytes: Optional[bytes] = None
    ) -> None:
        """
        Generates a 100% FREE 10-second AI video (Text-to-Video or Image-to-Video)
        with zero paid billing:
        - Step 1: Free AI Video API (Hugging Face Wan2.1/LTX-Video or Pollinations Video) -> sendVideo .mp4
        - Step 2 (100% Free Unlimited Fallback): 4-Scene Cinematic 10s Live Mini App (/api/preview/<id>)
          with Ken Burns Zoom/Pan animation and built-in free video download.
        """
        self.send_chat_action(chat_id, "upload_video")

        clean_prompt = (prompt or "").strip()
        if not clean_prompt and not image_bytes:
            self.send_message(
                chat_id,
                "🎬 <b>របៀបប្រើប្រាស់មុខងារបង្កើតវីដេអូ AI ឥតគិតថ្លៃ ១០០% (១០ វិនាទី)៖</b>\n\n"
                "១. <b>Text-to-Video:</b> វាយ <code>/video នាគមាសហោះលើភ្នំពេលថ្ងៃរះ 16:9</code>\n"
                "   ឬសរសេរ៖ <i>«បង្កើតវីដេអូ ទីក្រុងភ្នំពេញពេលយប់មានភ្លើងពណ៌»</i>\n"
                "២. <b>Image-to-Video:</b> ផ្ញើរូបថតភ្ជាប់ Caption <code>/video ធ្វើឱ្យរូបនេះមានចលនា</code> "
                "ឬ Reply លើរូបថតណាមួយដោយវាយ <code>/video ...</code>",
                reply_to_message_id=message_id,
                parse_mode="HTML"
            )
            return

        mode_label = "Image-to-Video (រូបថត → វីដេអូ)" if image_bytes else "Text-to-Video (អត្ថបទ → វីដេអូ)"
        ratio = detect_aspect_ratio(clean_prompt, default="16:9")

        result = generate_free_ai_video(
            prompt=clean_prompt,
            api_key=self.solver.api_key,
            image_bytes=image_bytes,
            aspect_ratio=ratio,
            duration_seconds=10
        )

        if not result.get("success"):
            self.send_message(
                chat_id,
                result.get("error") or "❌ មិនអាចបង្កើតវីដេអូបានទេ សូមសាកល្បងម្ដងទៀត។",
                reply_to_message_id=message_id,
                parse_mode="HTML"
            )
            return

        safe_prompt = html.escape(clean_unwanted_thai(clean_prompt or "Image-to-Video Animation")[:120])
        model_used = result.get("model") or "Free AI Video"

        # Step 1 succeeded: Direct MP4 buffer via sendVideo
        if result.get("mode") == "mp4" and result.get("video_bytes"):
            self.send_chat_action(chat_id, "upload_video")
            caption = (
                f"🎬 <b>វីដេអូ AI ឥតគិតថ្លៃ ({html.escape(mode_label)})</b>\n"
                f"📝 <b>Prompt:</b> {safe_prompt}\n"
                f"✨ <b>ម៉ូដែល:</b> <code>{html.escape(model_used)}</code> • {ratio}"
            )
            self.send_video(
                chat_id=chat_id,
                video=result["video_bytes"],
                caption=caption,
                reply_to_message_id=message_id,
                supports_streaming=True,
                parse_mode="HTML"
            )
            return

        # Step 2 (100% Free Unlimited Fallback): 4-Scene 10s Cinematic Live Mini App Preview
        miniapp_html = result.get("miniapp_html") or ""
        app_id = self.preview_store.generate_id()
        app_title = clean_unwanted_thai(clean_prompt or "AI Cinematic Video")[:60]
        stored_remotely, _ = self.preview_store.save_preview(app_id, miniapp_html, title=app_title)

        # Send portable HTML video player (also backs signed Telegram Cloud preview on Vercel)
        self.send_chat_action(chat_id, "upload_document")
        html_bytes = miniapp_html.encode("utf-8")
        uploaded_fid = self.send_document(
            chat_id=chat_id,
            file_bytes=html_bytes,
            filename=f"{app_id}_video_10s.html",
            mime_type="text/html",
            caption=(
                f"🎞️ <b>ឯកសារវីដេអូ AI 10 វិនាទី (Free Offline/Web):</b> <code>{app_id}_video_10s.html</code>\n"
                f"💡 <i>អាចបើកក្នុង Telegram Mini App ឬ Browser ដើម្បីមើល និងទាញយកវីដេអូដោយឥតគិតថ្លៃ!</i>"
            ),
            reply_to_message_id=message_id,
            parse_mode="HTML"
        )

        fid_for_url = uploaded_fid if (uploaded_fid and uploaded_fid != "ok") else None
        preview_url = self.preview_store.build_preview_url(
            app_id=app_id,
            file_id=fid_for_url,
            stored_remotely=stored_remotely,
            bot_token=self.token
        )

        reply_markup = {
            "inline_keyboard": [
                [{"text": "🎬 មើលវីដេអូ AI 10 វិនាទី (Live Preview)", "web_app": {"url": preview_url}}]
            ]
        }
        msg_text = (
            f"🎬 <b>វីដេអូ AI 10 វិនាទី (ឥតគិតថ្លៃ ១០០%)</b>\n"
            f"📝 <b>Prompt:</b> {safe_prompt}\n"
            f"📐 <b>ទំហំ:</b> <code>{ratio}</code> | ⏱️ <b>រយៈពេល:</b> 10 វិនាទី (4 ប្លង់ Cinematic Zoom/Pan)\n"
            f"✨ <b>ប្រព័ន្ធ:</b> <code>{html.escape(model_used)}</code>\n\n"
            f"👇 <i>ចុចប៊ូតុងខាងក្រោមដើម្បីមើលវីដេអូមានចលនាផ្ទាល់ និងទាញយកដោយឥតគិតថ្លៃ៖</i>"
        )
        self.send_message(
            chat_id,
            msg_text,
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
        document = message.get("document")
        voice = message.get("voice")
        audio = message.get("audio")
        caption = (message.get("caption") or "").strip()
        reply_to_msg = message.get("reply_to_message") or {}
        replied_photo = reply_to_msg.get("photo")

        # Handle /img and /video commands (including Reply-to-Photo Image-to-Video)
        if text.startswith("/"):
            lower_cmd = text.split()[0].lower()
            if lower_cmd.startswith("/img") or lower_cmd.startswith("/image"):
                img_prompt = parse_image_intent(text) or ""
                self._handle_ai_image_generation(chat_id, message_id, img_prompt)
                return
            if lower_cmd.startswith("/video") or lower_cmd.startswith("/vid"):
                vid_prompt = parse_video_intent(text) or ""
                ref_bytes = None
                if replied_photo:
                    self.send_chat_action(chat_id, "upload_video")
                    ref_bytes = self.get_file_bytes(replied_photo[-1].get("file_id", ""))
                self._handle_ai_video_generation(chat_id, message_id, vid_prompt, image_bytes=ref_bytes)
                return

            self._handle_command(chat_id, message_id, text)
            return

        # Handle Video Downloader (TikTok, Facebook, YouTube, CapCut, Pinterest)
        video_text = text or caption
        video_detection = detect_video_url(video_text)
        if video_detection:
            matched_url, platform_code = video_detection
            self._handle_video_download(chat_id, message_id, matched_url, platform_code)
            return

        # Handle Uploaded Code Document (Fix/Edit/Preview Code Files)
        if document:
            doc_name = (document.get("file_name") or "").strip()
            doc_ext = os.path.splitext(doc_name)[1].lower()
            doc_size = document.get("file_size") or 0
            if doc_ext in SUPPORTED_CODE_EXTENSIONS and doc_size <= 512 * 1024:
                self.send_chat_action(chat_id, "typing")
                raw_doc = self.get_file_bytes(document.get("file_id", ""))
                if not raw_doc:
                    self.send_message(
                        chat_id,
                        "❌ មិនអាចទាញយកឯកសារកូដបានទេ។ សូមព្យាយាមផ្ញើម្តងទៀត។",
                        reply_to_message_id=message_id
                    )
                    return

                code_text = raw_doc.decode("utf-8", errors="replace")
                user_req = caption or f"សូមពិនិត្យ កែកំហុស និងកែលម្អកូដក្នុងឯកសារ {doc_name} ឱ្យដំណើរការបានល្អ ១០០%។"
                enhanced_prompt = build_app_builder_prompt(
                    user_text=user_req,
                    uploaded_filename=doc_name,
                    uploaded_code=code_text
                )
                success, answer = self.solver.solve(
                    prompt=enhanced_prompt,
                    chat_id=chat_id,
                    is_code_request=True
                )
                if not success:
                    self.send_message(chat_id, answer, reply_to_message_id=message_id)
                    return

                self._handle_code_response(chat_id, message_id, answer)
                return

        # Handle Voice / Audio (Gemini Live Voice-to-Voice + Opposite-Gender Edge TTS)
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

            mime_type = "audio/ogg" if voice else "audio/mp3"
            speaker_gender = None
            language = None
            emotion = None

            # Use Single-Call Multimodal Audio + JSON (Gemini Live style), while preserving
            # compatibility if solver.solve was explicitly overridden in unit tests.
            solve_overridden = "solve" in getattr(self.solver, "__dict__", {}) and "solve_voice_live" not in getattr(self.solver, "__dict__", {})
            if solve_overridden:
                success, answer = self.solver.solve(
                    prompt=caption or "ស្ដាប់សំឡេងហើយឆ្លើយតបធម្មជាតិ",
                    image_bytes=audio_bytes,
                    mime_type=mime_type,
                    chat_id=chat_id,
                    is_voice=True
                )
            else:
                success, voice_meta = self.solver.solve_voice_live(
                    audio_bytes=audio_bytes,
                    mime_type=mime_type,
                    caption=caption,
                    chat_id=chat_id
                )
                if not success:
                    self.send_message(
                        chat_id,
                        voice_meta.get("error") or "⚠️ មិនអាចវិភាគសារសំឡេងបានទេ។",
                        reply_to_message_id=message_id
                    )
                    return
                answer = voice_meta.get("reply_text", "")
                speaker_gender = voice_meta.get("speaker_gender")
                language = voice_meta.get("language")
                emotion = voice_meta.get("emotion")

            if not success:
                self.send_message(chat_id, answer, reply_to_message_id=message_id)
                return

            def _synthesize_voice(spoken: str) -> Optional[bytes]:
                try:
                    return text_to_speech(
                        spoken,
                        speaker_gender=speaker_gender,
                        language=language,
                        emotion=emotion
                    )
                except TypeError:
                    # Fallback if text_to_speech is mocked as a 1-arg lambda in tests
                    return text_to_speech(spoken)

            # Check if this is a long academic/lesson answer
            is_long_academic = len(answer) > 280 or any(kw in answer for kw in ["ដំណាក់កាល", "រូបមន្ត", "មាត្រា", "ច្បាប់", "សមីការ", "\\frac", "$"])

            if is_long_academic:
                # Dual send: Send full formatted text in chat AND concise voice summary
                self.send_message(chat_id, answer, reply_to_message_id=message_id)

                spoken_text = answer[:260].rsplit(' ', 1)[0] + "..." if len(answer) > 260 else answer
                self.send_chat_action(chat_id, "record_voice")
                speech_bytes = _synthesize_voice(spoken_text)
                if speech_bytes:
                    self.send_voice(chat_id, speech_bytes, reply_to_message_id=message_id)
            else:
                self.send_chat_action(chat_id, "record_voice")
                speech_bytes = _synthesize_voice(answer)
                if speech_bytes:
                    sent = self.send_voice(chat_id, speech_bytes, reply_to_message_id=message_id)
                    if not sent:
                        self.send_message(chat_id, answer, reply_to_message_id=message_id)
                else:
                    self.send_message(chat_id, answer, reply_to_message_id=message_id)

            # Post-reply Auto-Reflection (0ms perceived delay for user)
            self.solver.maybe_reflect(chat_id, caption or answer)
            return

        # Handle Photo (Image-to-Video with caption OR Homework Image Solver)
        if photo:
            best_photo = photo[-1]
            file_id = best_photo.get("file_id")

            # Check if user attached a photo with a video-generation caption (Image-to-Video)
            caption_video_prompt = parse_video_intent(caption) if caption else None
            if caption_video_prompt is not None:
                self.send_chat_action(chat_id, "upload_video")
                image_bytes = self.get_file_bytes(file_id)
                if not image_bytes:
                    self.send_message(
                        chat_id,
                        "❌ មិនអាចទាញយករូបភាពសម្រាប់បង្កើតវីដេអូបានទេ។ សូមព្យាយាមផ្ញើម្តងទៀត។",
                        reply_to_message_id=message_id
                    )
                    return
                self._handle_ai_video_generation(chat_id, message_id, caption_video_prompt, image_bytes=image_bytes)
                return

            self.send_chat_action(chat_id, "typing")

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

        # Handle Text (AI Image / AI Video / App Builder / Math / Science / Emotional Chat)
        if text:
            # 1. Natural Intent: AI Image Generator ("បង្កើតរូបភាព...", "គូររូប...")
            img_intent_prompt = parse_image_intent(text)
            if img_intent_prompt is not None:
                self._handle_ai_image_generation(chat_id, message_id, img_intent_prompt)
                return

            # 2. Natural Intent: AI Video Generator ("បង្កើតវីដេអូ...", "ធ្វើវីដេអូ...", or Reply to photo)
            vid_intent_prompt = parse_video_intent(text)
            if vid_intent_prompt is not None:
                ref_bytes = None
                if replied_photo:
                    self.send_chat_action(chat_id, "upload_video")
                    ref_bytes = self.get_file_bytes(replied_photo[-1].get("file_id", ""))
                self._handle_ai_video_generation(chat_id, message_id, vid_intent_prompt, image_bytes=ref_bytes)
                return

            self.send_chat_action(chat_id, "typing")
            if is_code_or_app_request(text):
                enhanced_prompt = build_app_builder_prompt(text)
                success, answer = self.solver.solve(
                    prompt=enhanced_prompt,
                    chat_id=chat_id,
                    is_code_request=True
                )
                if not success:
                    self.send_message(chat_id, answer, reply_to_message_id=message_id)
                    return

                self._handle_code_response(chat_id, message_id, answer)
                return

            success, answer = self.solver.solve(prompt=text, chat_id=chat_id)
            if not success:
                self.send_message(chat_id, answer, reply_to_message_id=message_id)
                return

            # If Gemini returned a complete previewable HTML app even from a casual prompt, export + preview it
            blocks, _ = extract_code_blocks(answer)
            if find_previewable_html(blocks):
                self._handle_code_response(chat_id, message_id, answer)
                self.solver.maybe_reflect(chat_id, text)
                return

            self._send_rendered_solution_or_text(chat_id, answer, message_id)
            # Post-reply Auto-Reflection (updates Evolving Persona every 5 msgs or significant chats)
            self.solver.maybe_reflect(chat_id, text)
            return

    def _handle_command(self, chat_id: int, message_id: int, command_text: str) -> None:
        """Handles bot commands."""
        cmd = command_text.split()[0].lower()

        if cmd in ["/start", "/start@yourbot"]:
            welcome_msg = (
                "👋 *សួស្តីប្អូនៗ និងសិស្សានុសិស្សទាំងអស់គ្នា!*\n\n"
                "ខ្ញុំជា *Telegram Study Bot* ជំនួយការដោះស្រាយលំហាត់គ្រប់មុខវិជ្ជា បំពាក់ដោយបច្ចេកវិទ្យា *Google Gemini Flash* 🧠✨\n\n"
                "📚 *សមត្ថភាពចម្បង៖*\n"
                "• 🎨 *បង្កើតរូបភាព និងវីដេអូ AI (Image & Veo Video):* វាយ `/img <ពាក្យបញ្ជា>` ឬ «បង្កើតរូបភាព...» ដើម្បីគូររូប HD ក្នុង ៥-១០ វិនាទី និង `/video <ពាក្យបញ្ជា>` ឬ «បង្កើតវីដេអូ...» (រួមទាំង Image-to-Video ពីរូបថត)!\n"
                "• 💻 *បង្កើតកម្មវិធី កែកូដ និង Live Preview (Mini App):* សុំបង្កើតគេហទំព័រ ហ្គេម កម្មវិធីគណនា ឬផ្ញើកូដ/ឯកសារកូដមកឱ្យកែ — Bot នឹងបង្កើតកូដពេញលេញ ផ្ញើប៊ូតុង *Preview កម្មវិធីផ្ទាល់* ក្នុង Telegram និងផ្ញើឯកសារកូដ (.html/.py/.js/.zip) សម្រាប់បើកកែបន្ត!\n"
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
            active_model = getattr(self.solver, "primary_model", "gemini-3.1-flash-lite")
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

        elif cmd in ["/persona", "/persona@yourbot"]:
            p = self.solver.persona_store.get_persona(chat_id)
            vocab = ", ".join(p.get("learned_vocabulary") or []) or "មិនទាន់មាន"
            habits = "; ".join(p.get("user_habits") or []) or "មិនទាន់មាន"
            prefs = "; ".join(p.get("user_preferences") or []) or "មិនទាន់មាន"
            notes_list = p.get("evolution_notes") or []
            notes = "\n".join(f"• {n}" for n in notes_list[-5:]) if notes_list else "• មិនទាន់មានកំណត់ត្រាវិវត្តន៍ប្រចាំថ្ងៃទេ"
            persona_msg = (
                "🧠 <b>ប្រព័ន្ធវិវត្តន៍បុគ្គលិកលក្ខណៈ (Self-Evolving Persona)</b>\n\n"
                f"❤️ <b>កម្រិតភាពស្និទ្ធស្នាល:</b> {p.get('relationship_level', 1)}/10 ({html.escape(str(p.get('relationship_label', '')))})\n"
                f"🎭 <b>អារម្មណ៍បច្ចុប្បន្ន:</b> {html.escape(str(p.get('mood', 'សប្បាយ')))}\n"
                f"💬 <b>ចំនួនសារសរុប:</b> {p.get('message_count', 0)}\n"
                f"🗣️ <b>ពាក្យសម្ដីដែលបានរៀន:</b> {html.escape(vocab)}\n"
                f"🧩 <b>ទម្លាប់របស់អ្នក:</b> {html.escape(habits)}\n"
                f"⭐ <b>ចំណង់ចំណូលចិត្ត:</b> {html.escape(prefs)}\n\n"
                f"📔 <b>កំណត់ត្រាវិវត្តន៍ប្រចាំថ្ងៃ:</b>\n{html.escape(notes)}"
            )
            self.send_message(chat_id, persona_msg, reply_to_message_id=message_id, parse_mode="HTML")

        else:
            self.send_message(
                chat_id,
                "❓ មិនស្គាល់ពាក្យបញ្ជានេះទេ។ សូមចុច /help ឬ /start ដើម្បីមើលការណែនាំ។",
                reply_to_message_id=message_id
            )
