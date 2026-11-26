"""
Telegram Webhook Setup Utility
Easily configure, inspect, or delete Telegram Webhook for Vercel deployment.

Usage:
    python setup_webhook.py --set https://your-project.vercel.app/api/webhook
    python setup_webhook.py --info
    python setup_webhook.py --delete
"""

import os
import sys
import argparse
import requests
from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Configure Telegram Webhook for Vercel")
    parser.add_argument("--set", type=str, help="Vercel Webhook URL (e.g. https://your-app.vercel.app/api/webhook)")
    parser.add_argument("--info", action="store_true", help="Get current webhook info")
    parser.add_argument("--delete", action="store_true", help="Delete current webhook")
    parser.add_argument("--secret", type=str, default=None, help="Optional secret token for webhook verification")

    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ Error: TELEGRAM_BOT_TOKEN is not set.")
        print("Please set it in your .env file or environment.")
        sys.exit(1)

    base_url = f"https://api.telegram.org/bot{token}"

    if args.set:
        url = args.set.strip()
        secret = args.secret or os.environ.get("WEBHOOK_SECRET")
        payload = {"url": url}
        if secret:
            payload["secret_token"] = secret

        print(f"🔗 Setting Telegram Webhook to: {url}")
        resp = requests.post(f"{base_url}/setWebhook", json=payload, timeout=15)
        res_data = resp.json()
        if res_data.get("ok"):
            print("✅ Webhook configured successfully!")
            print(f"Details: {res_data.get('description')}")
        else:
            print("❌ Failed to set webhook:")
            print(res_data)

    elif args.delete:
        print("🗑️ Deleting Telegram Webhook...")
        resp = requests.post(f"{base_url}/deleteWebhook", json={"drop_pending_updates": True}, timeout=15)
        res_data = resp.json()
        if res_data.get("ok"):
            print("✅ Webhook deleted successfully!")
        else:
            print("❌ Error deleting webhook:", res_data)

    elif args.info or len(sys.argv) == 1:
        print("ℹ️ Checking Telegram Webhook status...")
        resp = requests.get(f"{base_url}/getWebhookInfo", timeout=15)
        res_data = resp.json()
        if res_data.get("ok"):
            info = res_data.get("result", {})
            print(f"Current Webhook URL: {info.get('url') or '(None / Polling mode)'}")
            print(f"Custom Certificate: {info.get('has_custom_certificate')}")
            print(f"Pending update count: {info.get('pending_update_count', 0)}")
            if info.get("last_error_message"):
                print(f"⚠️ Last error: {info.get('last_error_message')}")
        else:
            print("❌ Failed to get webhook info:", res_data)


if __name__ == "__main__":
    main()
