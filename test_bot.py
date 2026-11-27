"""
Unit and Integration Tests for Telegram Gemini Solver Bot
Verifies imports, classes, commands, and chunking without external network calls.
"""

import os
import sys

# Ensure local directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gemini_solver import GeminiSolver, SYSTEM_INSTRUCTION
from bot_core import TelegramBot


def test_gemini_solver_init():
    print("Testing GeminiSolver initialization...")
    solver = GeminiSolver(api_key="test_key", model="gemini-2.5-flash")
    assert solver.api_key == "test_key"
    assert solver.model == "gemini-2.5-flash"
    assert "ដោះស្រាយលំហាត់" in SYSTEM_INSTRUCTION
    print("✓ GeminiSolver initialization passed.")


def test_message_chunking():
    print("Testing message chunking...")
    bot = TelegramBot(token="fake_token")
    short_text = "Hello Khmer!"
    chunks = bot._chunk_message(short_text, max_chars=100)
    assert len(chunks) == 1
    assert chunks[0] == short_text

    long_text = "\n".join([f"Line {i}: ដំណោះស្រាយលំហាត់គណិតវិទ្យា" for i in range(100)])
    chunks = bot._chunk_message(long_text, max_chars=200)
    assert len(chunks) > 1
    # Verify reassembled length matches original
    assert len("\n".join(chunks)) == len(long_text)
    print(f"✓ Message chunking passed (split into {len(chunks)} chunks).")


def test_command_handling_mock():
    print("Testing command handling logic...")
    bot = TelegramBot(token="fake_token")
    captured_messages = []

    # Mock send_message
    bot.send_message = lambda chat_id, text, reply_to_message_id=None: captured_messages.append((chat_id, text))

    # Test /start
    bot.handle_update({
        "message": {
            "chat": {"id": 12345},
            "message_id": 1,
            "text": "/start"
        }
    })
    assert len(captured_messages) == 1
    assert "Google Gemini Flash" in captured_messages[0][1]

    # Test /subjects
    bot.handle_update({
        "message": {
            "chat": {"id": 12345},
            "message_id": 2,
            "text": "/subjects"
        }
    })
    assert len(captured_messages) == 2
    assert "គណិតវិទ្យា" in captured_messages[1][1]
    assert "រូបវិទ្យា" in captured_messages[1][1]
    assert "គីមីវិទ្យា" in captured_messages[1][1]

    print("✓ Command handling test passed.")


def test_vercel_webhook_import():
    print("Testing Vercel Webhook handler module...")
    from api.webhook import handler
    assert hasattr(handler, "do_GET")
    assert hasattr(handler, "do_POST")
    print("✓ Vercel Webhook handler passed.")


def test_math_formatting():
    print("Testing math formatting and fraction wrapping...")
    from gemini_solver import format_math_telegram

    raw_latex = r"គណនា $I = \int_0^{\pi/4} \sin^2 x dx$ តាមរូបមន្ត $\frac{1 - \cos 2x}{2}$"
    formatted = format_math_telegram(raw_latex)
    assert "$" not in formatted
    assert r"\frac" not in formatted
    assert r"\sin" not in formatted
    assert r"\cos" not in formatted
    assert "```" in formatted  # Vertical fraction was wrapped in code block
    assert "───" in formatted

    # Test orphan fraction wrapping
    orphan = "○ **ខ)**\n 35 - q\n ──────\n   5"
    wrapped = format_math_telegram(orphan)
    assert "```" in wrapped
    print("✓ Math formatting and fraction wrapping test passed.")


if __name__ == "__main__":
    print("========================================")
    print("🧪 Running Verification Tests")
    print("========================================")
    test_gemini_solver_init()
    test_message_chunking()
    test_command_handling_mock()
    test_vercel_webhook_import()
    test_math_formatting()
    print("========================================")
    print("🎉 ALL TESTS PASSED SUCCESSFULLY!")
    print("========================================")
