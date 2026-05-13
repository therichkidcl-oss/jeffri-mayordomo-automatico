import re
from typing import Any

TG_MD_V2_SPECIAL = r"_*[]()~`>#+-=|{}.!"

TOOL_ICONS = {
    "Read": "📖",
    "Write": "📝",
    "Edit": "✏️",
    "Bash": "▶️",
    "Grep": "🔍",
    "Glob": "📂",
    "WebFetch": "🌐",
    "WebSearch": "🌐",
    "TodoWrite": "📋",
    "Task": "🤖",
}


def escape_md_v2(text: str) -> str:
    return "".join("\\" + c if c in TG_MD_V2_SPECIAL else c for c in text)


def truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... (truncado)"


def _format_tool_use(name: str, tool_input: dict) -> str:
    icon = TOOL_ICONS.get(name, "🔧")

    if name == "Read":
        return f"{icon} *{name}*: `{tool_input.get('file_path', '?')}`"
    if name == "Write":
        return f"{icon} *{name}*: `{tool_input.get('file_path', '?')}`"
    if name == "Edit":
        path = tool_input.get("file_path", "?")
        old = tool_input.get("old_string", "")[:200]
        new = tool_input.get("new_string", "")[:200]
        return f"{icon} *{name}*: `{path}`\n```diff\n- {old}\n+ {new}\n```"
    if name == "Bash":
        cmd = tool_input.get("command", "")
        return f"{icon} *Bash*:\n```\n{cmd}\n```"
    if name == "Grep":
        return f"{icon} *Grep*: `{tool_input.get('pattern', '?')}`"
    if name == "Glob":
        return f"{icon} *Glob*: `{tool_input.get('pattern', '?')}`"
    if name in ("WebFetch", "WebSearch"):
        return f"{icon} *{name}*: {tool_input.get('url') or tool_input.get('query', '?')}"

    summary = str(tool_input)[:200]
    return f"{icon} *{name}*: `{summary}`"


def _format_tool_result(content: Any) -> str:
    if isinstance(content, list):
        text = "\n".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
    else:
        text = str(content)
    text = truncate(text, 3500)
    return f"```\n{text}\n```"


def format_event(event: dict) -> list[str]:
    event_type = event.get("type")

    if event_type in ("queue-operation", "attachment", "summary"):
        return []

    if event_type == "assistant":
        out: list[str] = []
        content = event.get("message", {}).get("content", [])
        for block in content:
            block_type = block.get("type")
            if block_type == "text":
                text = block.get("text", "").strip()
                if text:
                    out.append(truncate(text, 4000))
            elif block_type == "tool_use":
                out.append(_format_tool_use(block.get("name", "?"), block.get("input", {})))
        return out

    if event_type == "user":
        out = []
        content = event.get("message", {}).get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    out.append(_format_tool_result(block.get("content", "")))
        return out

    return []
