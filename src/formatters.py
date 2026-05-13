import base64
from dataclasses import dataclass
from typing import Any, Union

TG_MD_V2_SPECIAL = r"_*[]()~`>#+-=|{}.!"

SCREENSHOT_TOOLS = (
    "mcp__playwright__browser_take_screenshot",
    "mcp__Claude_in_Chrome__gif_creator",
    "mcp__Claude_Preview__preview_screenshot",
    "screenshot",
    "Screenshot",
)


@dataclass
class TextMessage:
    text: str


@dataclass
class PhotoMessage:
    data: bytes
    caption: str | None = None


Message = Union[TextMessage, PhotoMessage]


def escape_md_v2(text: str) -> str:
    return "".join("\\" + c if c in TG_MD_V2_SPECIAL else c for c in text)


def truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... (truncado)"


def _extract_images_from_content(content: Any) -> list[bytes]:
    images: list[bytes] = []
    if not isinstance(content, list):
        return images
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "image":
            continue
        source = block.get("source", {})
        if source.get("type") == "base64" and "data" in source:
            try:
                images.append(base64.b64decode(source["data"]))
            except Exception:
                pass
    return images


def format_event(event: dict) -> list[Message]:
    event_type = event.get("type")

    if event_type in ("queue-operation", "attachment", "summary"):
        return []

    if event_type == "assistant":
        out: list[Message] = []
        content = event.get("message", {}).get("content", [])
        if isinstance(content, str):
            text = content.strip()
            if text:
                out.append(TextMessage(truncate(text, 4000)))
            return out
        if not isinstance(content, list):
            return []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                text = block.get("text", "").strip()
                if text:
                    out.append(TextMessage(truncate(text, 4000)))
        return out

    if event_type == "user":
        out = []
        content = event.get("message", {}).get("content", [])
        if not isinstance(content, list):
            return []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_result":
                continue
            result_content = block.get("content", "")
            for img_bytes in _extract_images_from_content(result_content):
                out.append(PhotoMessage(data=img_bytes, caption="📸 Screenshot del navegador"))
        return out

    return []
