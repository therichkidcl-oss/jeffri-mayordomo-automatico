from src.formatters import format_event, truncate, escape_md_v2


def test_format_assistant_text():
    event = {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "Hola, soy Claude."}]},
    }
    result = format_event(event)
    assert len(result) == 1
    assert "Hola, soy Claude" in result[0]


def test_format_tool_use_read():
    event = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "src/bot.py"}}
            ]
        },
    }
    result = format_event(event)
    assert "📖" in result[0]
    assert "Read" in result[0]
    assert "src/bot.py" in result[0]


def test_format_tool_use_edit():
    event = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "Edit",
                    "input": {
                        "file_path": "src/bot.py",
                        "old_string": "foo",
                        "new_string": "bar",
                    },
                }
            ]
        },
    }
    result = format_event(event)
    assert "✏️" in result[0]
    assert "Edit" in result[0]
    assert "src/bot.py" in result[0]


def test_format_tool_use_bash():
    event = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "npm test"}}
            ]
        },
    }
    result = format_event(event)
    assert "▶️" in result[0]
    assert "npm test" in result[0]


def test_format_tool_result():
    event = {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "content": "Salida del comando"}
            ]
        },
    }
    result = format_event(event)
    assert "Salida del comando" in result[0]


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
