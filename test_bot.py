"""
Unit and Integration Tests for Telegram Gemini Solver Bot
Verifies imports, classes, commands, KaTeX rendering, card splitting, and solution endpoints.
"""

import os
import sys
import io

# Ensure local directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gemini_solver import GeminiSolver, SYSTEM_INSTRUCTION, format_math_telegram
from bot_core import TelegramBot
from renderer import encode_solution_payload, decode_solution_payload, get_solution_html, split_solution_into_cards


def test_gemini_solver_init():
    print("Testing GeminiSolver initialization...")
    solver = GeminiSolver(api_key="test_key", model="gemini-3.5-flash-lite")
    assert solver.api_key == "test_key"
    assert solver.model == "gemini-3.5-flash-lite"
    assert "ដោះស្រាយលំហាត់" in SYSTEM_INSTRUCTION
    assert r"\frac" in SYSTEM_INSTRUCTION
    print("✓ GeminiSolver initialization passed.")


def test_solution_payload_codec():
    print("Testing solution payload encoding/decoding...")
    sample_solution = "## ២៥. គណនាអាំងតេក្រាល $I = \\int_0^{\\frac{\\pi}{4}} \\sin^2 x dx$\n\n$$\\frac{1 - \\cos 2x}{2}$$"
    encoded = encode_solution_payload(sample_solution)
    assert isinstance(encoded, str)
    assert len(encoded) > 0

    decoded = decode_solution_payload(encoded)
    assert decoded == sample_solution
    print("✓ Solution payload codec passed.")


def test_card_splitting():
    print("Testing card splitting for multi-exercise solutions...")
    multi_ex = """**២៥. គណនាអាំងតេក្រាល $I = \\int_0^{\\frac{\\pi}{4}} \\sin^2 x dx$**

$$I = \\frac{\\pi - 2}{8}$$

---

**២៦. គណនាលីមីត $\\lim_{x \\to +\\infty} x$**

ចម្លើយគឺ $+\\infty$

---

**២៧. ដោះស្រាយសមីការ**

$x = 0$
"""
    cards = split_solution_into_cards(multi_ex)
    assert len(cards) == 3
    assert "២៥. គណនាអាំងតេក្រាល" in cards[0]
    assert "២៦. គណនាលីមីត" in cards[1]
    assert "២៧. ដោះស្រាយសមីការ" in cards[2]

    # Test single exercise
    single_ex = "**២៨. រកម៉ូឌុល** $Z = 2\\sqrt{2}$"
    single_cards = split_solution_into_cards(single_ex)
    assert len(single_cards) == 1
    print("✓ Card splitting test passed.")


def test_solution_html_generator():
    print("Testing solution HTML generator...")
    sample_solution = "**២៨. រកម៉ូឌុល** $Z = \\sqrt{2} + i\\sqrt{6}$"
    html = get_solution_html(sample_solution)
    assert "<!DOCTYPE html>" in html
    assert "Kantumruy Pro" in html
    assert "katex.min.js" in html
    assert "markedKatex" in html
    assert "#solution-card" in html
    assert "font-size: 24px" in html
    print("✓ Solution HTML generator passed.")


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
    assert len("\n".join(chunks)) == len(long_text)
    print(f"✓ Message chunking passed (split into {len(chunks)} chunks).")


def test_command_handling_mock():
    print("Testing command handling logic...")
    bot = TelegramBot(token="fake_token")
    captured_messages = []

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


def test_bot_send_photo_and_fallback():
    print("Testing bot send_photo and fallback mechanism...")
    bot = TelegramBot(token="fake_token")
    captured_actions = []
    captured_photos = []
    captured_messages = []

    bot.send_chat_action = lambda chat_id, action: captured_actions.append((chat_id, action))
    bot.send_photo = lambda chat_id, photo_bytes, caption=None, reply_to_message_id=None: captured_photos.append((chat_id, len(photo_bytes), caption)) or True
    bot.send_message = lambda chat_id, text, reply_to_message_id=None: captured_messages.append((chat_id, text)) or True

    # 1. When renderer returns bytes with multi-exercise
    sample_answer = """**២៥. គណនា $I = \\frac{\\pi-2}{8}$**\n---\n**២៦. គណនា $e^4$**"""
    import bot_core
    original_renderer = bot_core.render_solution_to_png
    bot_core.render_solution_to_png = lambda text: b"\x89PNG\r\n\x1a\nfake_png_data"

    bot._send_rendered_solution_or_text(chat_id=999, answer=sample_answer, message_id=10)
    assert len(captured_photos) == 2
    assert captured_photos[0][0] == 999
    assert "(ភាគ 1/2)" in captured_photos[0][2]
    assert "(ភាគ 2/2)" in captured_photos[1][2]

    # 2. When renderer returns None (fallback to text)
    bot_core.render_solution_to_png = lambda text: None
    bot._send_rendered_solution_or_text(chat_id=999, answer=sample_answer, message_id=11)
    assert len(captured_messages) == 1
    assert "២៥." in captured_messages[0][1]

    bot_core.render_solution_to_png = original_renderer
    print("✓ Bot send_photo and fallback test passed.")


def test_api_handler_solution_route():
    print("Testing api/index.py handler solution GET route...")
    from api.index import handler

    class MockSocket:
        def __init__(self):
            self.data = io.BytesIO()

        def makefile(self, *args, **kwargs):
            return self.data

    class DummyHandler(handler):
        def __init__(self, path):
            self.path = path
            self.headers = {}
            self.wfile = io.BytesIO()
            self.response_code = None
            self.response_headers = {}

        def send_response(self, code):
            self.response_code = code

        def send_header(self, k, v):
            self.response_headers[k] = v

        def end_headers(self):
            pass

    test_payload = encode_solution_payload("## សួស្តី $1+1=2$")
    h = DummyHandler(f"/solution?c={test_payload}")
    h.do_GET()
    assert h.response_code == 200
    assert "text/html" in h.response_headers.get("Content-Type", "")
    html_output = h.wfile.getvalue().decode("utf-8")
    assert "<!DOCTYPE html>" in html_output
    assert "Kantumruy Pro" in html_output

    h_health = DummyHandler("/")
    h_health.do_GET()
    assert h_health.response_code == 200
    assert "application/json" in h_health.response_headers.get("Content-Type", "")

    print("✓ api/index.py handler solution GET route passed.")


def test_math_formatting():
    print("Testing math formatting fallback...")
    raw_latex = r"គណនា $I = \int_0^{\pi/4} \sin^2 x dx$ តាមរូបមន្ត $\frac{1 - \cos 2x}{2}$"
    formatted = format_math_telegram(raw_latex)
    assert "$" not in formatted
    assert r"\frac" not in formatted
    assert r"\sin" not in formatted
    assert r"\cos" not in formatted
    assert "(1 - cos 2x) / (2)" in formatted or "(1 - cos 2x)/2" in formatted
    print("✓ Math formatting fallback test passed.")


if __name__ == "__main__":
    print("========================================")
    print("🧪 Running Verification Tests")
    print("========================================")
    test_gemini_solver_init()
    test_solution_payload_codec()
    test_card_splitting()
    test_solution_html_generator()
    test_message_chunking()
    test_command_handling_mock()
    test_bot_send_photo_and_fallback()
    test_api_handler_solution_route()
    test_math_formatting()
    print("========================================")
    print("🎉 ALL TESTS PASSED SUCCESSFULLY!")
    print("========================================")
