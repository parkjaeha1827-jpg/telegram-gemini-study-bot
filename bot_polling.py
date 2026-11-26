"""
Local Long-Polling Runner
Use this script to test the Telegram Bot locally on your computer without Vercel or a public URL!
Run:
    python bot_polling.py
"""

import os
import sys
import time
import requests
from dotenv import load_dotenv

# Load .env file with override=True to guarantee .env values are used
load_dotenv(override=True)

from bot_core import TelegramBot

TELEGRAM_API_BASE = "https://api.telegram.org"


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    if not token:
        print("❌ Error: TELEGRAM_BOT_TOKEN is missing in .env")
        print("Please create .env and set TELEGRAM_BOT_TOKEN=your_token")
        sys.exit(1)

    if not gemini_key:
        print("⚠️ Warning: GEMINI_API_KEY is missing in .env")
        print("Please configure GEMINI_API_KEY in .env before solving questions.")

    bot = TelegramBot(token=token)
    base_url = f"{TELEGRAM_API_BASE}/bot{token}"

    # Delete any existing webhook before starting polling
    print("🔄 Removing any active webhook to enable polling mode...")
    try:
        del_resp = requests.post(f"{base_url}/deleteWebhook", json={"drop_pending_updates": False}, timeout=10)
        print(f"Webhook status: {del_resp.json().get('description', 'OK')}")
    except Exception as e:
        print(f"Notice: {e}")

    # Check bot identity
    try:
        me_resp = requests.get(f"{base_url}/getMe", timeout=10).json()
        if me_resp.get("ok"):
            bot_info = me_resp.get("result", {})
            print(f"🤖 Bot Connected: @{bot_info.get('username')} ({bot_info.get('first_name')})")
        else:
            print(f"❌ Failed to connect to Telegram: {me_resp}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Connection error: {e}")
        sys.exit(1)

    print("🚀 Study Bot is listening for questions on Telegram! Press Ctrl+C to stop.")
    offset = 0

    while True:
        try:
            params = {"offset": offset, "timeout": 30}
            resp = requests.get(f"{base_url}/getUpdates", params=params, timeout=40)
            
            if resp.status_code == 200:
                data = resp.json()
                updates = data.get("result", [])
                for upd in updates:
                    offset = upd["update_id"] + 1
                    print(f"📩 Processing update ID: {upd['update_id']}")
                    bot.handle_update(upd)
            elif resp.status_code == 409:
                print("⚠️ Conflict: Another instance is running or webhook is active. Waiting 5s...")
                time.sleep(5)
            else:
                print(f"⚠️ getUpdates error ({resp.status_code}): {resp.text}")
                time.sleep(3)

        except requests.exceptions.Timeout:
            continue
        except requests.exceptions.ConnectionError:
            print("⚠️ Network connection interrupted. Retrying in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n🛑 Bot stopped by user.")
            break
        except Exception as e:
            print(f"⚠️ Unexpected error: {e}")
            time.sleep(2)


if __name__ == "__main__":
    main()
