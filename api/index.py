"""
Vercel Serverless Function Entrypoint
File: api/index.py
Handles both GET (health check & /solution card HTML) and POST (Telegram webhook updates).
"""

import os
import sys
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler

# Add root directory to sys.path so imports work seamlessly on Vercel
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from bot_core import TelegramBot
from renderer import decode_solution_payload, get_solution_html
from preview_service import PreviewStore, render_preview_not_found_html


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Health check endpoint, Live Mini App Preview route, and KaTeX solution card renderer."""
        parsed = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed.query)

        # Handle Telegram Mini App Live Preview route: /api/preview/<id> or /preview/<id>
        preview_id = None
        if query_params.get("route") == ["preview"] and query_params.get("id"):
            preview_id = query_params["id"][0]
        else:
            for candidate_path in (
                parsed.path,
                self.headers.get("x-forwarded-uri", ""),
                self.headers.get("x-matched-path", ""),
            ):
                if not candidate_path:
                    continue
                clean_p = urllib.parse.urlparse(candidate_path).path
                if clean_p.startswith("/api/preview/"):
                    preview_id = clean_p[len("/api/preview/"):].strip("/").split("/")[0]
                    break
                if clean_p.startswith("/preview/"):
                    preview_id = clean_p[len("/preview/"):].strip("/").split("/")[0]
                    break

        if preview_id:
            fid_list = query_params.get("fid", [])
            sig_list = query_params.get("sig", [])
            fid = fid_list[0] if fid_list else None
            sig = sig_list[0] if sig_list else None

            store = PreviewStore()
            html_content = store.get_preview(preview_id, file_id=fid, sig=sig)
            if html_content:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "public, max-age=300")
                self.end_headers()
                self.wfile.write(html_content.encode("utf-8"))
                return

            not_found_html = render_preview_not_found_html(preview_id)
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(not_found_html.encode("utf-8"))
            return

        # Handle KaTeX solution HTML render route
        is_solution = (
            parsed.path in ("/solution", "/api/solution")
            or parsed.path.startswith("/solution")
            or "c" in query_params
            or query_params.get("route") == ["solution"]
            or "solution" in self.headers.get("x-matched-path", "")
            or "solution" in self.headers.get("x-forwarded-uri", "")
        )

        if is_solution:
            c_list = query_params.get("c", [])
            payload = c_list[0] if c_list else ""
            markdown_text = decode_solution_payload(payload)
            if not markdown_text:
                markdown_text = "## មិនមានទិន្នន័យដំណោះស្រាយ (No solution content)"

            html = get_solution_html(markdown_text)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return

        # Default Health check response
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()

        status_data = {
            "status": "online",
            "service": "Telegram Gemini Study Bot",
            "model": "gemini-3.1-flash-lite",
            "ready": bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("GEMINI_API_KEY")),
            "message": "Send POST requests with Telegram update payloads to /api/webhook or /"
        }
        self.wfile.write(json.dumps(status_data, indent=2, ensure_ascii=False).encode("utf-8"))

    def do_POST(self):
        """Processes incoming Telegram Webhook updates."""
        # Check optional webhook secret header for security
        webhook_secret = os.environ.get("WEBHOOK_SECRET")
        if webhook_secret:
            token_header = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if token_header != webhook_secret:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b'{"error": "Unauthorized secret token"}')
                return

        # Read JSON body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            update = json.loads(body.decode("utf-8"))
            bot = TelegramBot()
            bot.handle_update(update)
        except Exception as e:
            print(f"[Webhook Error] {e}")

        # Always return 200 OK so Telegram considers the update delivered
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')
