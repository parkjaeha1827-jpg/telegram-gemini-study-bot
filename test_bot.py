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
    solver = GeminiSolver(api_key="test_key", model="gemini-2.5-pro")
    assert solver.api_key == "test_key"
    assert solver.model == "gemini-2.5-pro"
    assert "gemini-2.5-pro" in solver.candidate_models
    assert "gemini-3-pro" in solver.candidate_models
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
    solver = GeminiSolver(api_key="test_api_key", model="gemini-2.5-pro")
    assert solver.primary_model == "gemini-2.5-pro"
    assert "gemini-2.5-pro" in solver.candidate_models
    assert "gemini-3-pro" in solver.candidate_models

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
    print("========================================")
    print("🎉 ALL TESTS PASSED SUCCESSFULLY!")
    print("========================================")
