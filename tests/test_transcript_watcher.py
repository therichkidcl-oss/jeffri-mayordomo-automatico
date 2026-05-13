import asyncio
import json
import time
from pathlib import Path
import pytest

from src.transcript_watcher import TranscriptWatcher


@pytest.mark.asyncio
async def test_watcher_emits_new_lines(tmp_path):
    jsonl = tmp_path / "test.jsonl"
    jsonl.write_text("")

    received: list[dict] = []

    async def on_event(event: dict):
        received.append(event)

    watcher = TranscriptWatcher(tmp_path, on_event)
    watcher.start()
    watcher.set_active_file(jsonl)

    await asyncio.sleep(0.3)

    with open(jsonl, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "text": "hola"}) + "\n")
        f.flush()

    await asyncio.sleep(1.0)

    watcher.stop()

    assert len(received) >= 1
    assert received[0]["type"] == "assistant"
