"""
Vercel Serverless Function Handler for Telegram Webhook
Route: /api/webhook
"""

import os
import sys
import json
from http.server import BaseHTTPRequestHandler

# Add root directory to sys.path so imports work seamlessly on Vercel
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from bot_core import TelegramBot


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Health check endpoint."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()

        status_data = {
            "status": "online",
            "service": "Telegram Gemini Study Bot",
            "model": os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
            "ready": bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("GEMINI_API_KEY")),
            "message": "Send POST requests with Telegram update payloads to /api/webhook."
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
