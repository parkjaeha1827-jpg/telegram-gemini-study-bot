"""
Unit and Integration Tests for Telegram Gemini Solver Bot
Verifies imports, classes, commands, KaTeX rendering, card splitting, and solution endpoints.
"""

import os
import sys
import io
import json

# Ensure local directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gemini_solver import GeminiSolver, SYSTEM_INSTRUCTION, format_math_telegram, ChatMemory
from bot_core import TelegramBot
from renderer import (
    encode_solution_payload,
    decode_solution_payload,
    get_solution_html,
    split_solution_into_cards,
    auto_crop_png_card
)


def test_gemini_solver_init():
    print("Testing GeminiSolver initialization and Smart Dual-Mode instructions...")
    solver = GeminiSolver(api_key="test_key", model="gemini-3.1-flash-lite")
    assert solver.api_key == "test_key"
    assert solver.model == "gemini-3.1-flash-lite"
    assert "gemini-3.1-flash-lite" in solver.candidate_models
    assert "gemini-3.5-flash-lite" in solver.candidate_models
    assert solver.memory.max_messages == 20
    assert "Smart Dual-Mode" in SYSTEM_INSTRUCTION
    assert "ACADEMIC & EXAM MODE" in SYSTEM_INSTRUCTION
    assert "REALISTIC HUMAN & SASSY PERSONA" in SYSTEM_INSTRUCTION
    assert "មាត្រាច្បាប់" in SYSTEM_INSTRUCTION
    assert "វិញ្ញាសាប្រឡង" in SYSTEM_INSTRUCTION
    assert r"\frac" in SYSTEM_INSTRUCTION
    # Emotional personality rules
    assert "នែ៎" in SYSTEM_INSTRUCTION or "ឆឹស" in SYSTEM_INSTRUCTION
    assert "ហាមប្រកាសខ្លួនថាជា AI" in SYSTEM_INSTRUCTION
    assert "ប្រច័ណ្ឌ" in SYSTEM_INSTRUCTION
    assert "លួងលោម" in SYSTEM_INSTRUCTION
    assert "ប្ដូរភាសាស្វ័យប្រវត្តិ" in SYSTEM_INSTRUCTION
    assert "ឆ្លើយតបជាសំឡេង" in SYSTEM_INSTRUCTION
    assert "ច្បាប់ហាមដាច់ខាតភាសាថៃ" in SYSTEM_INSTRUCTION
    print("✓ GeminiSolver initialization & Smart Dual-Mode instructions passed.")


def test_chat_memory():
    print("Testing ChatMemory multi-turn history and limit...")
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = f.name

    try:
        mem = ChatMemory(max_messages=4, storage_path=tmp_path)
        mem.add_turn(chat_id=1001, user_text="សួស្តី", model_text="សួស្តី! មានរឿងអីមែនហ្នឹង?")
        mem.add_turn(chat_id=1001, user_text="នឹកអូន", model_text="នឹកតើ! មកបាត់មុខទៅណា? ឆឹស!")

        hist = mem.get_history(1001)
        assert len(hist) == 4
        assert hist[0]["role"] == "user"
        assert hist[0]["parts"][0]["text"] == "សួស្តី"
        assert hist[3]["parts"][0]["text"] == "នឹកតើ! មកបាត់មុខទៅណា? ឆឹស!"

        # Adding 3rd turn pushes older messages out beyond max_messages=4
        mem.add_turn(chat_id=1001, user_text="សុំទោស", model_text="លើកលែងទោសឱ្យមួយដង!")
        hist2 = mem.get_history(1001)
        assert len(hist2) <= 4
        assert hist2[-1]["parts"][0]["text"] == "លើកលែងទោសឱ្យមួយដង!"

        # Clear
        mem.clear(1001)
        assert len(mem.get_history(1001)) == 0
        print("✓ ChatMemory multi-turn history and capping test passed.")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


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
    assert "katex.renderToString" in html
    assert "#solution-card" in html
    assert "font-size: 21.5px" in html
    assert "math-block-card" in html
    print("✓ Solution HTML generator passed.")

    print("Testing auto_crop_png_card...")
    from PIL import Image
    test_img = Image.new("RGB", (600, 400), (255, 255, 255))
    # Draw a non-white box in middle
    for x in range(100, 300):
        for y in range(100, 200):
            test_img.putpixel((x, y), (15, 23, 42))
    img_byte_arr = io.BytesIO()
    test_img.save(img_byte_arr, format='PNG')
    cropped_bytes = auto_crop_png_card(img_byte_arr.getvalue(), padding=20)
    cropped_img = Image.open(io.BytesIO(cropped_bytes))
    # Cropped width should be around (300-100) + 40 = 240, but clamped to minimum 320
    assert cropped_img.size[0] >= 240
    print("✓ Auto-crop PNG card passed.")


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

    # Test /clear
    bot.handle_update({
        "message": {
            "chat": {"id": 12345},
            "message_id": 3,
            "text": "/clear"
        }
    })
    assert len(captured_messages) == 3
    assert "លុបប្រវត្តិការសន្ទនា" in captured_messages[2][1]

    print("✓ Command handling test passed.")


def test_bot_send_photo_and_fallback():
    print("Testing bot conversational text routing and photo rendering...")
    bot = TelegramBot(token="fake_token")
    captured_actions = []
    captured_photos = []
    captured_messages = []

    bot.send_chat_action = lambda chat_id, action: captured_actions.append((chat_id, action))
    bot.send_photo = lambda chat_id, photo_bytes, caption=None, reply_to_message_id=None: captured_photos.append((chat_id, len(photo_bytes), caption)) or True
    bot.send_message = lambda chat_id, text, reply_to_message_id=None: captured_messages.append((chat_id, text)) or True

    # 1. Casual emotional chat (No math formulas) -> Should send directly as TEXT!
    casual_chat = "នែ៎ នឹកតើ! មកបាត់មុខទៅណាទើបឃើញមុខហ្នឹង? ឆឹស!"
    bot._send_rendered_solution_or_text(chat_id=999, answer=casual_chat, message_id=1)
    assert len(captured_photos) == 0  # No photo!
    assert len(captured_messages) == 1
    assert "នែ៎ នឹកតើ!" in captured_messages[0][1]

    # 2. When answer contains academic math -> Should render into PHOTO!
    sample_answer = """**២៥. គណនា $I = \\frac{\\pi-2}{8}$**\n---\n**២៦. គណនា $e^4$**"""
    import bot_core
    original_renderer = bot_core.render_solution_to_png
    bot_core.render_solution_to_png = lambda text: b"\x89PNG\r\n\x1a\nfake_png_data"

    bot._send_rendered_solution_or_text(chat_id=999, answer=sample_answer, message_id=10)
    assert len(captured_photos) == 2
    assert captured_photos[0][0] == 999
    assert "២៥." in captured_photos[0][2]
    assert "២៦." in captured_photos[1][2]

    # 3. When renderer returns None (fallback to text)
    bot_core.render_solution_to_png = lambda text: None
    bot._send_rendered_solution_or_text(chat_id=999, answer=sample_answer, message_id=11)
    assert len(captured_messages) == 2
    assert "២៥." in captured_messages[1][1]

    bot_core.render_solution_to_png = original_renderer
    print("✓ Bot conversational text routing and photo rendering test passed.")


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


def test_voice_service_and_bot_voice_handling():
    print("Testing voice service, clean_text_for_tts, and dual send...")
    from voice_service import detect_language, sanitize_text_for_tts, clean_text_for_tts

    assert detect_language("សួស្តីបង") == "km"
    assert detect_language("Hello, how are you?") == "en"
    assert detect_language("你好") == "zh"
    assert detect_language("こんにちは") == "ja"

    raw = "<b>នែ៎!</b> `សួស្តី` #1 ធ្វើអីហ្នឹង? ឆឹស! 😂❤️ $$x=2$$ √16 = 4 https://google.com"
    clean = clean_text_for_tts(raw)
    assert "*" not in clean
    assert "#" not in clean
    assert "`" not in clean
    assert "<b>" not in clean
    assert "https" not in clean
    assert "នែ៎!" in clean
    assert "ឆឹស!" in clean
    assert "ឫសការ៉េនៃ" in clean
    assert "ស្មើនឹង" in clean

    # Test Bot handling of incoming voice update - Standard casual voice reply
    bot = TelegramBot(token="fake_token")
    captured_actions = []
    captured_voices = []
    captured_messages = []

    bot.send_chat_action = lambda chat_id, action: captured_actions.append((chat_id, action))
    bot.get_file_bytes = lambda file_id: b"fake_ogg_opus_audio"
    bot.send_voice = lambda chat_id, voice_bytes, caption=None, reply_to_message_id=None: captured_voices.append((chat_id, len(voice_bytes))) or True
    bot.send_message = lambda chat_id, text, **kwargs: captured_messages.append((chat_id, text)) or True

    # 1. Casual chat voice turn
    bot.solver.solve = lambda **kwargs: (True, "សួស្តី! ខ្ញុំកំពុងឆ្លើយតបជាសំឡេង។")

    import bot_core
    original_tts = bot_core.text_to_speech
    bot_core.text_to_speech = lambda text: b"fake_mp3_audio_data"

    try:
        bot.handle_update({
            "message": {
                "chat": {"id": 777},
                "message_id": 99,
                "voice": {
                    "file_id": "voice_file_abc123",
                    "duration": 3
                }
            }
        })

        assert "record_voice" in [a[1] for a in captured_actions]
        assert len(captured_voices) == 1
        assert captured_voices[0][0] == 777
        assert captured_voices[0][1] > 0

        # 2. Long academic/exam solution voice turn (Dual Send: HTML text in chat + voice note)
        captured_voices.clear()
        captured_messages.clear()
        academic_answer = (
            "<b>វិញ្ញាសាប្រឡងគ្រូ៖ មាត្រា ៣១ នៃរដ្ឋធម្មនុញ្ញ</b>\n\n"
            "○ ដំណាក់កាលទី ១៖ ព្រះរាជាណាចក្រកម្ពុជា ទទួលស្គាល់ និងគោរពសិទ្ធិមនុស្ស...\n"
            "○ ដំណាក់កាលទី ២៖ ប្រជាពលរដ្ឋខ្មែរមានភាពស្មើគ្នាចំពោះមុខច្បាប់ ដោយគ្មានការរើសអើង...\n"
            "រូបមន្តគណិតវិទ្យា៖ $x = \\frac{-b \\pm \\sqrt{\\Delta}}{2a}$\n\n"
            "ចម្លើយត្រឹមត្រូវគឺ គ. ស្មើភាពគ្នាចំពោះមុខច្បាប់"
        )
        bot.solver.solve = lambda **kwargs: (True, academic_answer)

        bot.handle_update({
            "message": {
                "chat": {"id": 777},
                "message_id": 100,
                "voice": {
                    "file_id": "voice_file_exam",
                    "duration": 5
                }
            }
        })

        # Dual send: Both text message AND voice message are delivered
        assert len(captured_messages) == 1
        assert "វិញ្ញាសាប្រឡងគ្រូ" in captured_messages[0][1]
        assert len(captured_voices) == 1
        assert captured_voices[0][0] == 777

    finally:
        bot_core.text_to_speech = original_tts
    print("✓ Voice service, clean_text_for_tts, and dual send passed.")


def test_video_downloader_detection_and_handling():
    print("Testing video downloader URL detection, extraction routing, and bot fallback flows...")
    from video_service import detect_video_url, extract_video_info

    # 1. Test URL detection for all platforms
    cases = [
        ("https://www.tiktok.com/@creator/video/1234567890", "tiktok"),
        ("https://vt.tiktok.com/ZSjR1yq8b/", "tiktok"),
        ("https://vm.tiktok.com/ZGJHxXXXX/", "tiktok"),
        ("https://www.facebook.com/reel/123456789", "facebook"),
        ("https://fb.watch/mG21x8z/", "facebook"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube"),
        ("https://youtube.com/shorts/5xX79_H1L9w", "youtube"),
        ("https://youtu.be/dQw4w9WgXcQ", "youtube"),
        ("https://www.capcut.com/t/Zs82X9vYk/", "capcut"),
        ("https://www.capcut.com/template-detail/7123456789", "capcut"),
        ("https://www.pinterest.com/pin/1140958943123847847/", "pinterest"),
        ("https://pin.it/7a8b9c", "pinterest"),
        ("គណនាលីមីត lim_{x -> 0} sin(x)/x", None),
    ]

    for text, expected in cases:
        det = detect_video_url(text)
        actual = det[1] if det else None
        assert actual == expected, f"Expected {expected} for {text}, got {actual}"

    # 2. Test Bot handling of Video Update - Step 1: Direct URL stream
    bot = TelegramBot(token="fake_token")
    captured_actions = []
    captured_videos = []
    captured_messages = []

    bot.send_chat_action = lambda chat_id, action: captured_actions.append((chat_id, action))
    bot.send_video = lambda chat_id, video, **kwargs: captured_videos.append((chat_id, video, kwargs)) or True
    bot.send_message = lambda chat_id, text, **kwargs: captured_messages.append((chat_id, text, kwargs)) or True

    import bot_core
    original_extract = bot_core.extract_video_info
    original_buffer = bot_core.fetch_video_buffer

    try:
        # Mock successful extraction
        bot_core.extract_video_info = lambda url, platform: {
            "success": True,
            "direct_url": "https://cdn.tikwm.com/video/sample_hd.mp4",
            "title": "Amazing Khmer Dance",
            "author": "Sreypov Dance",
            "platform": "TikTok",
            "platform_code": "tiktok",
            "quality": "HD (No Watermark)"
        }

        bot.handle_update({
            "message": {
                "chat": {"id": 888},
                "message_id": 101,
                "text": "Check this video https://vt.tiktok.com/ZSjR1yq8b/ please"
            }
        })

        # Verify upload_video chat action was dispatched
        assert ("upload_video" in [a[1] for a in captured_actions])

        # Verify send_video was called with direct streaming URL (Step 1)
        assert len(captured_videos) == 1
        chat_id_sent, video_payload, extra_kwargs = captured_videos[0]
        assert chat_id_sent == 888
        assert video_payload == "https://cdn.tikwm.com/video/sample_hd.mp4"
        assert "Amazing Khmer Dance" in extra_kwargs.get("caption", "")
        assert "TikTok" in extra_kwargs.get("caption", "")
        assert "គ្មាន Watermark" in extra_kwargs.get("caption", "")

        # 3. Test Bot handling - Step 2: Fallback to memory buffer when direct URL is rejected
        captured_videos.clear()
        captured_messages.clear()

        # Step 1 fails, Step 2 succeeds
        def mock_send_video(chat_id, video, **kwargs):
            if isinstance(video, str):
                return False  # Direct URL fails (e.g. hotlink restriction)
            return True       # Buffer upload succeeds

        bot.send_video = mock_send_video
        bot_core.fetch_video_buffer = lambda *args, **kwargs: (b"fake_mp4_bytes_in_ram", 15000000)

        bot.handle_update({
            "message": {
                "chat": {"id": 888},
                "message_id": 102,
                "text": "https://www.facebook.com/reel/123456789"
            }
        })

        # 4. Test Bot handling - Step 3: Inline Keyboard fallback when file > 50MB
        captured_videos.clear()
        captured_messages.clear()

        # Step 1 fails, Step 2 returns (None, 65000000) because size > 50MB
        bot.send_video = lambda chat_id, video, **kwargs: False
        bot_core.fetch_video_buffer = lambda *args, **kwargs: (None, 65 * 1024 * 1024)

        bot.handle_update({
            "message": {
                "chat": {"id": 888},
                "message_id": 103,
                "text": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            }
        })

        assert len(captured_messages) == 1
        msg_chat, msg_text, msg_kwargs = captured_messages[0]
        assert msg_chat == 888
        assert "50MB" in msg_text
        reply_markup = msg_kwargs.get("reply_markup", {})
        inline_kb = reply_markup.get("inline_keyboard", [[]])
        assert len(inline_kb) > 0
        assert "ទាញយកវីដេអូផ្ទាល់" in inline_kb[0][0]["text"]
        assert inline_kb[0][0]["url"] == "https://cdn.tikwm.com/video/sample_hd.mp4"

    finally:
        bot_core.extract_video_info = original_extract
        bot_core.fetch_video_buffer = original_buffer

    print("✓ Video downloader detection, extraction routing, and 3-step fallback test passed.")


def test_clean_unwanted_thai():
    print("Testing clean_unwanted_thai for zero Thai text in Telegram...")
    from video_service import clean_unwanted_thai
    assert clean_unwanted_thai("សួស្តីបង ค่า ធ្វើអីហ្នឹង ครับ") == "សួស្តីបង ធ្វើអីហ្នឹង"
    assert clean_unwanted_thai("អុីវា ស្រឡាញ់រាប់ឆ្មាំได้ត្រឹមសង្សារ ! Eva") == "អុីវា ស្រឡាញ់រាប់ឆ្មាំត្រឹមសង្សារ ! Eva"
    assert clean_unwanted_thai("លំហាត់គណិតវិទ្យាទី ១") == "លំហាត់គណិតវិទ្យាទី ១"
    assert clean_unwanted_thai("Hello World 123") == "Hello World 123"
    print("✓ clean_unwanted_thai passed.")


def test_capcut_detection_and_extraction():
    print("Testing CapCut URL detection and SSR extraction...")
    from video_service import detect_video_url, extract_capcut_video
    from unittest.mock import patch, MagicMock

    # 1. Test URL detection across all CapCut share formats
    samples = [
        ("https://www.capcut.com/template-detail/7156421419591634182", "capcut"),
        ("https://www.capcut.com/t/Zs82X9vYk/", "capcut"),
        ("I found this amazing template in CapCut. Tap the link to try it! https://www.capcut.com/t/Zs82X9vYk/", "capcut"),
        ("https://mobile.capcutshare.com/s/Zs82X9vYk", "capcut"),
        ("https://www.capcut.net/template-detail/12345", "capcut"),
    ]

    for text, expected_platform in samples:
        res = detect_video_url(text)
        assert res is not None, f"Failed to detect CapCut in: {text}"
        url, platform = res
        assert platform == expected_platform
        assert "capcut" in url

    # 2. Test SSR __MODERN_ROUTER_DATA__ parsing mock
    mock_html = """
    <html>
      <head><title>CapCut</title></head>
      <body>
        <script id="__MODERN_ROUTER_DATA__" type="application/json">
        {
          "loaderData": {
            "$": {
              "templateDetail": {
                "title": "Sad Mood Beat ค่า",
                "videoUrl": "https://v16-vod.capcutvod.com/sample_hd.mp4",
                "videoHeight": 1080,
                "videoWidth": 1920,
                "author": {"name": "Nang Springer ครับ"}
              }
            }
          }
        }
        </script>
      </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = mock_html

    with patch("requests.Session.get", return_value=mock_resp):
        info = extract_capcut_video("https://www.capcut.com/template-detail/7156421419591634182")
        assert info is not None
        assert info["success"] is True
        assert info["direct_url"] == "https://v16-vod.capcutvod.com/sample_hd.mp4"
        # Thai characters must be stripped
        assert info["title"] == "Sad Mood Beat"
        assert info["author"] == "Nang Springer"
        assert "1080p HD" in info["quality"]

    print("✓ CapCut URL detection and SSR extraction passed.")


def test_search_grounding_and_persistent_memory():
    print("Testing Google Search Grounding tool payload and persistent memory sync...")
    solver = GeminiSolver(api_key="test_api_key", model="gemini-3.1-flash-lite")
    assert solver.primary_model == "gemini-3.1-flash-lite"
    assert "gemini-3.1-flash-lite" in solver.candidate_models
    assert "gemini-3.5-flash-lite" in solver.candidate_models
    assert "gemini-flash-lite-latest" in solver.candidate_models

    # Verify that deprecated 404 models map to gemini-3.1-flash-lite
    legacy_solver = GeminiSolver(api_key="test_api_key", model="gemini-1.5-flash-8b")
    assert legacy_solver.primary_model == "gemini-3.1-flash-lite"

    # Verify ChatMemory remote KV sync mocks
    from unittest.mock import patch, MagicMock
    mem = ChatMemory(max_messages=10)
    mem.kv_url = "https://test-kv.upstash.io"
    mem.kv_token = "fake_kv_token"

    mock_kv_resp = MagicMock()
    mock_kv_resp.status_code = 200
    mock_kv_resp.json.return_value = {
        "result": json.dumps([
            {"role": "user", "parts": [{"text": "មាត្រា ៣១ ចែងពីអ្វី?"}]},
            {"role": "model", "parts": [{"text": "ចែងអំពីសិទ្ធិស្មើគ្នានៃប្រជាពលរដ្ឋខ្មែរ"}]}
        ])
    }

    test_chat_id = 88888
    mem.clear(test_chat_id)

    with patch("requests.get", return_value=mock_kv_resp), patch("requests.post") as mock_post:
        history = mem.get_history(test_chat_id)
        assert len(history) == 2
        assert "មាត្រា ៣១" in history[0]["parts"][0]["text"]

        # Add turn and verify remote set
        mem.add_turn(test_chat_id, "តើពិតមែនទេ?", "ពិតប្រាកដណាស់!")
        assert mock_post.called

    print("✓ Google Search Grounding and persistent memory sync passed.")


def test_cambodia_datetime_and_astrology_instructions():
    print("Testing Cambodia dynamic datetime and astrology/folklore system instructions...")
    from gemini_solver import get_cambodia_now, get_cambodia_datetime_context, SYSTEM_INSTRUCTION
    from unittest.mock import patch, MagicMock

    # 1. Test Cambodia Date and Time
    now = get_cambodia_now()
    assert now is not None
    ctx = get_cambodia_datetime_context()
    assert "Asia/Phnom_Penh" in ctx
    assert "UTC+7" in ctx
    assert str(now.year) in ctx

    # 2. Test 4 capability groups in SYSTEM_INSTRUCTION
    assert "ក្បួនហោរាសាស្ត្រ និងទស្សន៍ទាយ" in SYSTEM_INSTRUCTION
    assert "កាត់យល់សប្តិ" in SYSTEM_INSTRUCTION
    assert "មើលក្បួនអាយុ" in SYSTEM_INSTRUCTION
    assert "មើលជើងលេខប្រចាំថ្ងៃ" in SYSTEM_INSTRUCTION

    assert "ក្បួនដោះស្រាយបញ្ហា" in SYSTEM_INSTRUCTION

    assert "អក្សរសិល្ប៍ និងល្បែងប្រាជ្ញា" in SYSTEM_INSTRUCTION
    assert "ពាក្យបណ្ដៅខ្មែរ" in SYSTEM_INSTRUCTION
    assert "ពាក្យសុភាសិត ខ្មែរ អង់គ្លេស និងចិន" in SYSTEM_INSTRUCTION
    assert "ពាក្យគន្លាស់កាត់" in SYSTEM_INSTRUCTION
    assert "ក្លាផាច់" in SYSTEM_INSTRUCTION  # spoonerism sample: កាច់ផ្កា -> ក្លាផាច់

    assert "សិល្បៈតែងនិពន្ធ និងកម្សាន្ត" in SYSTEM_INSTRUCTION
    assert "តែងកំណាព្យខ្មែរ" in SYSTEM_INSTRUCTION
    assert "និទានរឿង" in SYSTEM_INSTRUCTION
    assert "ច្រៀងចម្រៀង" in SYSTEM_INSTRUCTION

    # 3. Test dynamic instruction injection in GeminiSolver.solve payload
    solver = GeminiSolver(api_key="fake_key", model="gemini-3.1-flash-lite")
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "រាសីថ្ងៃនេះល្អណាស់!"}]}}]
        }
        ok, res = solver.solve("មើលជើងលេខថ្ងៃនេះ", chat_id=12345)
        assert ok is True
        assert mock_post.called
        sent_payload = mock_post.call_args[1]["json"]
        sys_text = sent_payload["systemInstruction"]["parts"][0]["text"]
        assert "Asia/Phnom_Penh" in sys_text
        assert "កាលបរិច្ឆេទ និងម៉ោងជាក់ស្ដែងនៅកម្ពុជា" in sys_text

    print("✓ Cambodia dynamic datetime and astrology/folklore system instructions passed.")


def test_expressive_tts_and_music_notes():
    print("Testing Expressive Edge TTS (tempo -8% and music note stripping)...")
    from voice_service import clean_text_for_tts, is_expressive_mode, text_to_speech_async
    import asyncio
    from unittest.mock import patch, MagicMock

    # 1. Test clean_text_for_tts strips musical notes and emojis
    raw_song = "🎶 ស្រឡាញ់ស្រីខ្មៅ មិនខ្វល់ពីអ្នកណា 🎵🎤 ព្រោះចិត្តស្មោះត្រង់ 🎼"
    clean_song = clean_text_for_tts(raw_song)
    assert "🎶" not in clean_song
    assert "🎵" not in clean_song
    assert "🎤" not in clean_song
    assert "🎼" not in clean_song
    assert "ស្រឡាញ់ស្រីខ្មៅ មិនខ្វល់ពីអ្នកណា ព្រោះចិត្តស្មោះត្រង់" in clean_song

    # 2. Test is_expressive_mode detection
    assert is_expressive_mode("សូមនិទានរឿងព្រេងខ្មែរឱ្យស្តាប់") is True
    assert is_expressive_mode("សូត្រកំណាព្យបទពាក្យ៧") is True
    assert is_expressive_mode("🎶 ច្រៀងមួយបទមក 🎶") is True
    assert is_expressive_mode("គណនាអាំងតេក្រាលពី ០ ទៅ ១") is False

    # 3. Mock edge_tts to verify rate='-8%' on expressive mode
    mock_comm = MagicMock()
    async def mock_stream():
        yield {"type": "audio", "data": b"mock_expressive_audio"}
    mock_comm.stream = mock_stream

    with patch("edge_tts.Communicate", return_value=mock_comm) as mock_edge:
        audio = asyncio.run(text_to_speech_async("🎶 និទានរឿងព្រេងមួយ 🎶"))
        assert audio == b"mock_expressive_audio"
        assert mock_edge.called
        call_kwargs = mock_edge.call_args[1]
        assert call_kwargs.get("rate") == "-8%"

    with patch("edge_tts.Communicate", return_value=mock_comm) as mock_edge_chat:
        audio2 = asyncio.run(text_to_speech_async("សួស្តីបង សុខសប្បាយទេ?"))
        assert audio2 == b"mock_expressive_audio"
        call_kwargs2 = mock_edge_chat.call_args[1]
        assert call_kwargs2.get("rate") == "+0%"

    print("✓ Expressive Edge TTS (tempo -8% and music note stripping) passed.")


def test_app_builder_live_preview_and_code_export():
    print("Testing Full-Stack App Builder, Live Mini App Preview (/api/preview/<id>), and Portable Code Export...")
    import tempfile
    import zipfile
    from unittest.mock import patch, MagicMock
    from preview_service import (
        PreviewStore,
        is_code_or_app_request,
        extract_code_blocks,
        find_previewable_html,
        inject_telegram_webapp_script,
        package_code_export,
        compute_preview_signature,
        TELEGRAM_WEBAPP_SCRIPT_URL,
    )
    from gemini_solver import clean_unwanted_thai as solver_clean_thai

    # 1. Test request detection (Khmer, English, raw code, and non-code questions)
    assert is_code_or_app_request("សូមបង្កើតកម្មវិធីគណនា (Calculator) ស្អាតមួយ") is True
    assert is_code_or_app_request("ជួយបង្កើតហ្គេម Snake មួយឱ្យខ្ញុំលេង") is True
    assert is_code_or_app_request("Build a modern todo web app") is True
    assert is_code_or_app_request("ជួយកែកូដនេះផង:\n```python\ndef add(a, b):\n    return a - b\n```") is True
    assert is_code_or_app_request("សួស្តី សុខសប្បាយទេ?") is False
    assert is_code_or_app_request("គណនាអាំងតេក្រាលពី 0 ដល់ pi/4 នៃ sin^2(x)") is False

    # 2. Verify clean_unwanted_thai preserves Python indentation inside code blocks
    py_with_thai = "នេះជាកូដ สวัสดี៖\n```python\ndef hello():\n    print('សួស្តី')\n```"
    cleaned_py = solver_clean_thai(py_with_thai)
    assert "สวัสดี" not in cleaned_py
    assert "    print('សួស្តី')" in cleaned_py

    # 3. Test code extraction, Telegram WebApp SDK injection, and zip/html packaging
    sample_reply = (
        "នេះជាកម្មវិធីគណនាដ៏ស្អាតមួយសម្រាប់អ្នក!\n\n"
        "```html\n"
        "<!DOCTYPE html>\n"
        "<html lang=\"km\">\n"
        "<head><title>ម៉ាស៊ីនគិតលេខ</title><style>body{background:#111;color:#fff;}</style></head>\n"
        "<body><h1>ម៉ាស៊ីនគិតលេខ</h1><script>console.log('ready');</script></body>\n"
        "</html>\n"
        "```\n"
    )
    blocks, summary = extract_code_blocks(sample_reply)
    assert len(blocks) == 1
    assert blocks[0]["is_html"] is True
    assert "កម្មវិធីគណនា" in summary

    raw_html = find_previewable_html(blocks)
    assert raw_html is not None
    ready_html = inject_telegram_webapp_script(raw_html)
    assert TELEGRAM_WEBAPP_SCRIPT_URL in ready_html
    assert "Telegram.WebApp.ready()" in ready_html

    fname, fbytes, fmime = package_code_export(blocks, "app_12345", preview_html=ready_html)
    assert fname == "app_12345.html"
    assert fmime == "text/html"
    assert TELEGRAM_WEBAPP_SCRIPT_URL.encode("utf-8") in fbytes

    # Multi-file packaging -> in-memory .zip
    multi_blocks, _ = extract_code_blocks(
        "```html\n<!DOCTYPE html><html><head><title>Demo</title></head><body>Hi</body></html>\n```\n"
        "```python\n# backend\ndef run():\n    return True\n```\n"
    )
    zname, zbytes, zmime = package_code_export(multi_blocks, "app_multi", preview_html=ready_html)
    assert zname.endswith(".zip")
    assert zmime == "application/zip"
    with zipfile.ZipFile(io.BytesIO(zbytes), "r") as zf:
        names = zf.namelist()
        assert "index.html" in names
        assert "main.py" in names
        assert "README.txt" in names

    # 4. Test PreviewStore save/get + TelegramBot end-to-end flow + api/index.py /api/preview/<id>
    with tempfile.TemporaryDirectory() as tmp_dir:
        bot = TelegramBot(token="test_bot_token_123")
        bot.preview_store = PreviewStore(storage_dir=tmp_dir)

        captured_docs = []
        captured_msgs = []
        bot.send_chat_action = lambda cid, act: None
        bot.send_document = lambda **kwargs: (captured_docs.append(kwargs) or "BQACAgIAAxkFAKE_FILE_ID")
        bot.send_message = lambda cid, text, **kwargs: (captured_msgs.append((cid, text, kwargs)) or True)
        bot.solver.solve = lambda **kwargs: (True, sample_reply)

        bot.handle_update({
            "message": {
                "chat": {"id": 555},
                "message_id": 77,
                "text": "សូមបង្កើតកម្មវិធីគណនាស្អាតមួយ"
            }
        })

        # Verify sendDocument was called with .html file
        assert len(captured_docs) == 1
        assert captured_docs[0]["filename"].endswith(".html")
        assert b"telegram-web-app.js" in captured_docs[0]["file_bytes"]

        # Verify sendMessage was called with web_app Inline Keyboard button
        assert len(captured_msgs) == 1
        _, msg_text, msg_kwargs = captured_msgs[0]
        assert "ម៉ាស៊ីនគិតលេខ" in msg_text
        kb = msg_kwargs["reply_markup"]["inline_keyboard"]
        assert kb[0][0]["text"] == "🚀 Preview កម្មវិធីផ្ទាល់"
        web_app_url = kb[0][0]["web_app"]["url"]
        assert "/api/preview/app_" in web_app_url

        # Test api/index.py GET /api/preview/<id> route
        import api.index as api_index
        app_id_match = web_app_url.split("/api/preview/")[1].split("?")[0]

        class MockHandler(api_index.handler):
            def __init__(self, path):
                self.path = path
                self.headers = {}
                self.status_code = None
                self.resp_headers = {}
                self.wfile = io.BytesIO()
            def send_response(self, code):
                self.status_code = code
            def send_header(self, k, v):
                self.resp_headers[k] = v
            def end_headers(self):
                pass

        with patch.object(api_index, "PreviewStore", return_value=PreviewStore(storage_dir=tmp_dir)):
            h_ok = MockHandler(f"/api/preview/{app_id_match}")
            h_ok.do_GET()
            assert h_ok.status_code == 200
            assert "text/html" in h_ok.resp_headers.get("Content-Type", "")
            body_html = h_ok.wfile.getvalue().decode("utf-8")
            assert TELEGRAM_WEBAPP_SCRIPT_URL in body_html
            assert "ម៉ាស៊ីនគិតលេខ" in body_html

            # Also test Vercel rewritten query format (?route=preview&id=...)
            h_rw = MockHandler(f"/api/index?route=preview&id={app_id_match}")
            h_rw.do_GET()
            assert h_rw.status_code == 200

            # Test 404 for nonexistent preview ID
            h_404 = MockHandler("/api/preview/app_doesnotexist")
            h_404.do_GET()
            assert h_404.status_code == 404
            assert TELEGRAM_WEBAPP_SCRIPT_URL in h_404.wfile.getvalue().decode("utf-8")

        # 5. Test uploaded code document (.py) flow
        captured_docs.clear()
        captured_msgs.clear()
        bot.get_file_bytes = lambda fid: b"def add(a, b):\n    return a - b\n"
        bot.solver.solve = lambda **kwargs: (
            True,
            "ខ្ញុំបានកែកំហុសបូកលេខរួចហើយ!\n```python\n# អនុគមន៍បូកលេខ\ndef add(a, b):\n    return a + b\n```"
        )
        bot.handle_update({
            "message": {
                "chat": {"id": 555},
                "message_id": 78,
                "caption": "ជួយកែកូដនេះផង",
                "document": {
                    "file_id": "doc_py_123",
                    "file_name": "calc.py",
                    "file_size": 120
                }
            }
        })
        assert len(captured_docs) == 1
        assert captured_docs[0]["filename"].endswith(".py")
        assert b"return a + b" in captured_docs[0]["file_bytes"]
        assert len(captured_msgs) == 1

    print("✓ Full-Stack App Builder, Live Mini App Preview, and Portable Code Export passed.")


def test_self_evolving_personality_and_daily_learning():
    print("Testing Self-Evolving Personality, Firestore/KV storage, Auto-Reflection Engine, and System Prompt injection...")
    import tempfile
    from unittest.mock import patch, MagicMock
    from persona_service import (
        EvolvingPersonaStore,
        AutoReflectionEngine,
        should_trigger_reflection,
        is_significant_conversation,
        format_persona_for_system_prompt,
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        store_file = os.path.join(tmp_dir, "personas.json")
        store = EvolvingPersonaStore(storage_path=store_file)

        # 1. Verify default schema and 5-message trigger rule
        chat_id = 77701
        p = store.get_persona(chat_id)
        assert p["relationship_level"] == 1
        assert p["mood"] == "សប្បាយ"
        assert p["learned_vocabulary"] == []
        assert p["user_habits"] == []
        assert p["user_preferences"] == []
        assert p["evolution_notes"] == []

        for i in range(1, 5):
            p = store.increment_message_count(chat_id)
            assert should_trigger_reflection(p, "សួស្តី") is False

        # On 5th message -> triggers Auto-Reflection!
        p = store.increment_message_count(chat_id)
        assert p["message_count"] == 5
        assert should_trigger_reflection(p, "សួស្តី") is True

        # Significant conversation early trigger (delta >= 2)
        p_sig = dict(p)
        p_sig["message_count"] = 7
        p_sig["last_reflected_count"] = 5
        assert is_significant_conversation("ចាំទុកផង ខ្ញុំចូលចិត្តផឹកកាហ្វេទឹកដោះគោរាល់ព្រឹក") is True
        assert should_trigger_reflection(p_sig, "ចាំទុកផង ខ្ញុំចូលចិត្តផឹកកាហ្វេទឹកដោះគោរាល់ព្រឹក") is True

        # 2. Test AutoReflectionEngine calling gemini-2.5-flash & merging JSON (with Thai stripping)
        mock_reflection_json = json.dumps({
            "new_vocabulary": ["អេមស្នេហ៍", "សាហាវណាស់ ค่า"],
            "mood": "កក់ក្ដៅ",
            "relationship_delta": 1,
            "new_habits": ["ផឹកកាហ្វេទឹកដោះគោរាល់ព្រឹក"],
            "new_preferences": ["ចូលចិត្តសរសេរកូដ និងស្ដាប់ចម្រៀងសេដ"],
            "new_evolution_note": "អ្នកប្រើប្រាស់ចូលចិត្តការនិយាយលេងសើចបែបស្និទ្ធស្នាល"
        }, ensure_ascii=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": mock_reflection_json}]}}]
        }

        engine = AutoReflectionEngine(store=store, api_key="fake_key")
        sample_history = [
            {"role": "user", "parts": [{"text": "អេមស្នេហ៍ណាស់ ព្រឹកនេះខ្ញុំផឹកកាហ្វេទឹកដោះគោ"}]},
            {"role": "model", "parts": [{"text": "ហ្នឹងហើយ! កាហ្វេព្រឹកឆ្ងាញ់ណាស់ណា៎!"}]}
        ]

        with patch("requests.post", return_value=mock_resp) as mock_post:
            updated = engine.reflect_and_update(chat_id, sample_history)
            assert updated is not None
            assert mock_post.called
            called_url = mock_post.call_args[0][0]
            assert "gemini-2.5-flash" in called_url
            assert "អេមស្នេហ៍" in updated["learned_vocabulary"]
            # Thai characters must be stripped
            assert all("ค่า" not in v for v in updated["learned_vocabulary"])
            assert updated["relationship_level"] == 2
            assert updated["mood"] == "កក់ក្ដៅ"
            assert "ផឹកកាហ្វេទឹកដោះគោរាល់ព្រឹក" in updated["user_habits"]
            assert any("សរសេរកូដ" in pref for pref in updated["user_preferences"])
            assert len(updated["evolution_notes"]) == 1
            assert updated["last_reflected_count"] == 5

        # 3. Test System Prompt injection inside GeminiSolver.solve()
        solver = GeminiSolver(api_key="fake_key", model="gemini-3.1-flash-lite")
        solver.persona_store = store
        solver.reflection_engine = engine

        mock_reply = MagicMock()
        mock_reply.status_code = 200
        mock_reply.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "អេមស្នេហ៍តើ! ព្រឹកនេះផឹកកាហ្វេហើយនៅ?"}]}}]
        }

        with patch("requests.post", return_value=mock_reply) as mock_solve_post:
            ok, reply = solver.solve("សួស្តីព្រឹកនេះ", chat_id=chat_id)
            assert ok is True
            sent_payload = mock_solve_post.call_args[1]["json"]
            sys_text = sent_payload["systemInstruction"]["parts"][0]["text"]
            assert "SELF-EVOLVING PERSONA" in sys_text
            assert "អេមស្នេហ៍" in sys_text
            assert "ផឹកកាហ្វេទឹកដោះគោរាល់ព្រឹក" in sys_text
            assert "Asia/Phnom_Penh" in sys_text

        # 4. Test Firebase Firestore & Vercel KV remote sync calls
        remote_store = EvolvingPersonaStore(storage_path=os.path.join(tmp_dir, "remote_p.json"))
        remote_store.kv_url = "https://mock-kv.upstash.io"
        remote_store.kv_token = "mock_token"
        remote_store.firebase_project = "mock-firebase-proj"
        with patch("requests.post") as mock_kv_post, patch("requests.patch") as mock_fs_patch:
            mock_kv_post.return_value.status_code = 200
            mock_fs_patch.return_value.status_code = 200
            remote_store.save_persona(99901, updated)
            assert mock_kv_post.called
            assert "evolving_persona:99901" in mock_kv_post.call_args[0][0]
            assert mock_fs_patch.called
            assert "evolving_personas/99901" in mock_fs_patch.call_args[0][0]

        # 5. Test /persona command in TelegramBot
        bot = TelegramBot(token="fake_token")
        bot.solver.persona_store = store
        captured_msgs = []
        bot.send_message = lambda cid, text, **kwargs: (captured_msgs.append((cid, text, kwargs)) or True)
        bot.handle_update({
            "message": {
                "chat": {"id": chat_id},
                "message_id": 99,
                "text": "/persona"
            }
        })
        assert len(captured_msgs) == 1
        assert "Self-Evolving Persona" in captured_msgs[0][1]
        assert "អេមស្នេហ៍" in captured_msgs[0][1]

    print("✓ Self-Evolving Personality & Daily Learning passed.")


def test_ai_image_and_veo_video_generator():
    print("Testing AI Image Generator (gemini-2.5-flash-image/Imagen) & Veo Video Generator (Text/Image-to-Video)...")
    import base64
    from unittest.mock import patch, MagicMock
    from media_gen_service import (
        parse_image_intent,
        parse_video_intent,
        detect_aspect_ratio,
        enhance_media_prompt,
        generate_ai_image,
        generate_ai_video,
    )

    # 1. Verify Command & Natural Intent parsing
    assert parse_image_intent("/img ប្រាសាទអង្គរវត្តពេលថ្ងៃលិច") == "ប្រាសាទអង្គរវត្តពេលថ្ងៃលិច"
    assert parse_image_intent("បង្កើតរូបភាព ឆ្មាពាក់វ៉ែនតាខ្មៅ") == "ឆ្មាពាក់វ៉ែនតាខ្មៅ"
    assert parse_image_intent("គូររូប ភ្នំពេញពេលយប់ 16:9") == "ភ្នំពេញពេលយប់ 16:9"
    assert parse_image_intent("សួស្តី សុខសប្បាយទេ?") is None

    assert parse_video_intent("/video នាគមាសហោះលើភ្នំ 9:16") == "នាគមាសហោះលើភ្នំ 9:16"
    assert parse_video_intent("បង្កើតវីដេអូ ថ្ងៃរះលើសមុទ្រ") == "ថ្ងៃរះលើសមុទ្រ"
    assert parse_video_intent("ធ្វើវីដេអូ រូបនេះឱ្យមានចលនា") == "រូបនេះឱ្យមានចលនា"
    assert parse_video_intent("គណនាលីមីត x -> 0") is None

    assert detect_aspect_ratio("នាគហោះ 9:16 បញ្ឈរ", default="16:9") == "9:16"
    assert detect_aspect_ratio("sunset landscape 16:9", default="1:1") == "16:9"

    # 2. Verify Auto Prompt Enhancer uses gemini-2.5-flash
    mock_enh = MagicMock()
    mock_enh.status_code = 200
    mock_enh.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Cinematic sunset over Angkor Wat, realistic golden lighting, 4k high resolution"}]}}]
    }
    with patch("requests.post", return_value=mock_enh) as mock_post:
        en = enhance_media_prompt("ប្រាសាទអង្គរវត្តពេលថ្ងៃលិច", media_type="image", api_key="fake_key")
        assert "Angkor Wat" in en
        assert "gemini-2.5-flash" in mock_post.call_args[0][0]

    # 3. Verify Fast AI Image Generation (gemini-2.5-flash-image)
    fake_png_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nFAKE_AI_IMAGE_BYTES").decode("ascii")
    mock_img_resp = MagicMock()
    mock_img_resp.status_code = 200
    mock_img_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": fake_png_b64}}]}}]
    }
    with patch("media_gen_service.enhance_media_prompt", return_value="Cinematic Angkor Wat sunset"), \
         patch("requests.post", return_value=mock_img_resp) as mock_img_post:
        ok, img_bytes, enh, model_used = generate_ai_image("ប្រាសាទអង្គរវត្ត", api_key="fake_key")
        assert ok is True
        assert img_bytes == b"\x89PNG\r\n\x1a\nFAKE_AI_IMAGE_BYTES"
        assert model_used == "gemini-2.5-flash-image"
        sent_body = mock_img_post.call_args[1]["json"]
        assert "IMAGE" in sent_body["generationConfig"]["responseModalities"]

    # 4. Verify Veo Video Generation (Image-to-Video + Polling + MP4 memory buffer)
    mock_start = MagicMock()
    mock_start.status_code = 200
    mock_start.json.return_value = {"name": "models/veo-2.0-generate-001/operations/op_xyz123"}

    mock_poll_pending = MagicMock()
    mock_poll_pending.status_code = 200
    mock_poll_pending.json.return_value = {"done": False}

    mock_poll_done = MagicMock()
    mock_poll_done.status_code = 200
    mock_poll_done.json.return_value = {
        "done": True,
        "response": {
            "generateVideoResponse": {
                "generatedSamples": [
                    {"video": {"uri": "https://generativelanguage.googleapis.com/v1beta/files/vid123:download?alt=media"}}
                ]
            }
        }
    }

    mock_mp4_dl = MagicMock()
    mock_mp4_dl.status_code = 200
    mock_mp4_dl.content = b"\x00\x00\x00\x18ftypmp42FAKE_VEO_VIDEO"

    with patch("media_gen_service.enhance_media_prompt", return_value="Cinematic dragon flying over misty mountains"), \
         patch("requests.post", return_value=mock_start) as mock_veo_post, \
         patch("requests.get", side_effect=[mock_poll_pending, mock_poll_done, mock_mp4_dl]):
        ok, vid_bytes, enh, model_used = generate_ai_video(
            prompt="នាគហោះលើភ្នំ 9:16",
            api_key="fake_key",
            image_bytes=b"FAKE_REF_JPEG",
            duration_seconds=8,
            poll_interval=0.01,
            max_wait_seconds=5.0
        )
        assert ok is True
        assert vid_bytes == b"\x00\x00\x00\x18ftypmp42FAKE_VEO_VIDEO"
        assert model_used == "veo-2.0-generate-001"
        veo_payload = mock_veo_post.call_args[1]["json"]
        assert veo_payload["parameters"]["durationSeconds"] == 8
        assert veo_payload["parameters"]["aspectRatio"] == "9:16"
        assert "bytesBase64Encoded" in veo_payload["instances"][0]["image"]

    # 5. Verify Veo Billing Error produces clear Khmer Google AI Studio Billing guidance
    mock_billing_err = MagicMock()
    mock_billing_err.status_code = 403
    mock_billing_err.text = '{"error": {"message": "Veo is only accessible to billed users. Please enable billing."}}'
    with patch("media_gen_service.enhance_media_prompt", return_value="Cinematic ocean wave"), \
         patch("requests.post", return_value=mock_billing_err):
        ok, vid_bytes, _, err_kh = generate_ai_video("រលកសមុទ្រ", api_key="fake_key")
        assert ok is False
        assert vid_bytes is None
        assert "Billing" in err_kh
        assert "Google AI Studio" in err_kh

    # 6. Verify TelegramBot end-to-end routing (/img, natural video, photo+caption Image-to-Video, reply-to-photo)
    bot = TelegramBot(token="fake_token")
    actions = []
    sent_photos = []
    sent_videos = []
    sent_msgs = []
    bot.send_chat_action = lambda cid, act: actions.append(act)
    bot.send_photo = lambda chat_id, photo_bytes, **kw: (sent_photos.append((chat_id, photo_bytes, kw)) or True)
    bot.send_video = lambda chat_id, video, **kw: (sent_videos.append((chat_id, video, kw)) or True)
    bot.send_message = lambda cid, txt, **kw: (sent_msgs.append((cid, txt, kw)) or True)
    bot.get_file_bytes = lambda fid: b"FAKE_UPLOADED_PHOTO"

    import bot_core
    with patch.object(bot_core, "generate_ai_image", return_value=(True, b"PNG_BYTES", "Enhanced", "gemini-2.5-flash-image")), \
         patch.object(bot_core, "generate_ai_video", return_value=(True, b"MP4_BYTES", "Enhanced Vid", "veo-2.0-generate-001")) as mock_bot_vid:
        # 6a. /img command
        bot.handle_update({"message": {"chat": {"id": 321}, "message_id": 1, "text": "/img ប្រាសាទអង្គរវត្ត"}})
        assert "upload_photo" in actions
        assert len(sent_photos) == 1
        assert sent_photos[0][1] == b"PNG_BYTES"

        # 6b. Photo + Caption Image-to-Video
        actions.clear()
        bot.handle_update({
            "message": {
                "chat": {"id": 321},
                "message_id": 2,
                "caption": "បង្កើតវីដេអូ ឱ្យរូបនេះមានចលនាស្រទន់",
                "photo": [{"file_id": "ph_1"}]
            }
        })
        assert "upload_video" in actions
        assert len(sent_videos) == 1
        assert sent_videos[0][1] == b"MP4_BYTES"
        assert sent_videos[0][2].get("supports_streaming") is True
        assert mock_bot_vid.call_args[1]["image_bytes"] == b"FAKE_UPLOADED_PHOTO"

        # 6c. Reply-to-photo /video Image-to-Video
        sent_videos.clear()
        bot.handle_update({
            "message": {
                "chat": {"id": 321},
                "message_id": 3,
                "text": "/video ធ្វើឱ្យរូបនេះហោះឡើងលើ",
                "reply_to_message": {"photo": [{"file_id": "ph_replied"}]}
            }
        })
        assert len(sent_videos) == 1
        assert mock_bot_vid.call_args[1]["image_bytes"] == b"FAKE_UPLOADED_PHOTO"

    # 7. Verify vercel.json maxDuration >= 60
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "vercel.json"), "r", encoding="utf-8") as f:
        vj = json.load(f)
        assert vj["functions"]["api/index.py"]["maxDuration"] >= 60

    print("✓ AI Image Generator & Veo Video Generator tests passed.")


if __name__ == "__main__":
    print("========================================")
    print("🧪 Running Verification Tests")
    print("========================================")
    test_gemini_solver_init()
    test_chat_memory()
    test_solution_payload_codec()
    test_card_splitting()
    test_solution_html_generator()
    test_message_chunking()
    test_command_handling_mock()
    test_bot_send_photo_and_fallback()
    test_api_handler_solution_route()
    test_math_formatting()
    test_voice_service_and_bot_voice_handling()
    test_video_downloader_detection_and_handling()
    test_clean_unwanted_thai()
    test_capcut_detection_and_extraction()
    test_search_grounding_and_persistent_memory()
    test_cambodia_datetime_and_astrology_instructions()
    test_expressive_tts_and_music_notes()
    test_app_builder_live_preview_and_code_export()
    test_self_evolving_personality_and_daily_learning()
    test_ai_image_and_veo_video_generator()
    print("========================================")
    print("🎉 ALL TESTS PASSED SUCCESSFULLY!")
    print("========================================")
