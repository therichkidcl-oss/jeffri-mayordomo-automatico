import base64
from src.formatters import (
    format_event,
    truncate,
    escape_md_v2,
    TextMessage,
    PhotoMessage,
)


def test_format_assistant_text():
    event = {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "Hola, soy Claude."}]},
    }
    result = format_event(event)
    assert len(result) == 1
    assert isinstance(result[0], TextMessage)
    assert "Hola, soy Claude" in result[0].text


def test_format_skips_tool_use():
    event = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "src/bot.py"}},
                {"type": "text", "text": "Listo"},
            ]
        },
    }
    result = format_event(event)
    assert len(result) == 1
    assert isinstance(result[0], TextMessage)
    assert result[0].text == "Listo"


def test_format_skips_tool_result_text():
    event = {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "content": "Salida del comando"}
            ]
        },
    }
    result = format_event(event)
    assert result == []


def test_format_extracts_screenshot_from_tool_result():
    fake_png = b"\x89PNG\r\n\x1a\nfake-screenshot-bytes"
    encoded = base64.b64encode(fake_png).decode("ascii")
    event = {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": encoded,
                            },
                        }
                    ],
                }
            ]
        },
    }
    result = format_event(event)
    assert len(result) == 1
    assert isinstance(result[0], PhotoMessage)
    assert result[0].data == fake_png


def test_format_ignores_queue_operations():
    event = {"type": "queue-operation", "operation": "enqueue", "content": "hola"}
    result = format_event(event)
    assert result == []


def test_format_ignores_attachments():
    event = {"type": "attachment", "attachment": {"type": "hook_success"}}
    result = format_event(event)
    assert result == []


def test_truncate_short_text():
    assert truncate("hola", 100) == "hola"


def test_truncate_long_text():
    text = "a" * 5000
    result = truncate(text, 4000)
    assert len(result) <= 4020
    assert "truncado" in result.lower()


def test_escape_md_v2_special_chars():
    result = escape_md_v2("hola_mundo*test")
    assert result == "hola\\_mundo\\*test"


def test_format_assistant_content_as_string():
    event = {
        "type": "assistant",
        "message": {"content": "Texto plano sin bloques"},
    }
    result = format_event(event)
    assert len(result) == 1
    assert isinstance(result[0], TextMessage)
    assert result[0].text == "Texto plano sin bloques"


def test_format_assistant_skips_non_dict_blocks():
    event = {
        "type": "assistant",
        "message": {"content": [None, "string-block", {"type": "text", "text": "ok"}]},
    }
    result = format_event(event)
    assert len(result) == 1
    assert isinstance(result[0], TextMessage)
    assert result[0].text == "ok"


def test_format_assistant_content_none():
    event = {"type": "assistant", "message": {"content": None}}
    result = format_event(event)
    assert result == []
