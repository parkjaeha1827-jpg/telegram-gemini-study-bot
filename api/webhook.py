"""
Vercel Serverless Function Handler for Telegram Webhook
Route: /api/webhook
"""

from api.index import handler

__all__ = ["handler"]
