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


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Health check endpoint and KaTeX solution card HTML renderer."""
        parsed = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed.query)

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

        if "test_video" in query_params:
            v_url = query_params["test_video"][0]
            trace_info = []
            from pytubefix import YouTube
            try:
                yt = YouTube(v_url, client='WEB')
                stream = yt.streams.filter(progressive=True, file_extension='mp4').first()
                if stream:
                    trace_info.append(f"WEB: SUCCESS url={stream.url[:60]}")
                else:
                    trace_info.append("WEB: No progressive stream")
            except Exception as e:
                trace_info.append(f"WEB: {type(e).__name__} - {e}")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            res_data = {"test_url": v_url, "trace": trace_info}
            self.wfile.write(json.dumps(res_data, default=str).encode("utf-8"))
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
