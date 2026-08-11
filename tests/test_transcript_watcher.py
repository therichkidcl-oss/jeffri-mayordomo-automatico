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


@pytest.mark.asyncio
async def test_watcher_recovers_from_partial_write(tmp_path):
    """Regression: partial mid-line write must not lose the line on completion."""
    jsonl = tmp_path / "partial.jsonl"
    jsonl.write_text("")

    received: list[dict] = []

    async def on_event(event: dict):
        received.append(event)

    watcher = TranscriptWatcher(tmp_path, on_event)
    watcher.start()
    watcher.set_active_file(jsonl)

    await asyncio.sleep(0.2)

    # Write half a JSON line and flush — no newline yet
    with open(jsonl, "ab") as f:
        f.write(b'{"type": "assistant", "text": "ho')
        f.flush()

    await asyncio.sleep(0.5)
    assert len(received) == 0, "Partial line should not be parsed yet"

    # Write the rest, completing the line
    with open(jsonl, "ab") as f:
        f.write(b'la"}\n')
        f.flush()

    await asyncio.sleep(1.0)
    watcher.stop()

    assert len(received) == 1
    assert received[0]["text"] == "hola"


@pytest.mark.asyncio
async def test_watcher_skips_malformed_json(tmp_path):
    jsonl = tmp_path / "mixed.jsonl"
    jsonl.write_text("")

    received: list[dict] = []

    async def on_event(event: dict):
        received.append(event)

    watcher = TranscriptWatcher(tmp_path, on_event)
    watcher.start()
    watcher.set_active_file(jsonl)

    await asyncio.sleep(0.2)

    with open(jsonl, "a", encoding="utf-8") as f:
        f.write('{"type": "assistant", "n": 1}\n')
        f.write('this is not json\n')
        f.write('{"type": "assistant", "n": 2}\n')
        f.flush()

    await asyncio.sleep(1.0)
    watcher.stop()

    assert len(received) == 2
    assert received[0]["n"] == 1
    assert received[1]["n"] == 2


@pytest.mark.asyncio
async def test_watcher_multiple_lines_in_one_write(tmp_path):
    jsonl = tmp_path / "multi.jsonl"
    jsonl.write_text("")

    received: list[dict] = []

    async def on_event(event: dict):
        received.append(event)

    watcher = TranscriptWatcher(tmp_path, on_event)
    watcher.start()
    watcher.set_active_file(jsonl)

    await asyncio.sleep(0.2)

    with open(jsonl, "a", encoding="utf-8") as f:
        f.write('{"n": 1}\n{"n": 2}\n{"n": 3}\n')
        f.flush()

    await asyncio.sleep(1.0)
    watcher.stop()

    assert len(received) == 3
    assert [e["n"] for e in received] == [1, 2, 3]


@pytest.mark.asyncio
async def test_watcher_switches_active_file(tmp_path):
    file_a = tmp_path / "a.jsonl"
    file_b = tmp_path / "b.jsonl"
    file_a.write_text("")
    file_b.write_text("")

    received: list[dict] = []

    async def on_event(event: dict):
        received.append(event)

    watcher = TranscriptWatcher(tmp_path, on_event)
    watcher.start()
    watcher.set_active_file(file_a)

    await asyncio.sleep(0.2)

    with open(file_a, "a", encoding="utf-8") as f:
        f.write('{"src": "a"}\n')
        f.flush()
    await asyncio.sleep(0.5)

    # Switch to file_b — events on a should stop
    watcher.set_active_file(file_b)

    with open(file_a, "a", encoding="utf-8") as f:
        f.write('{"src": "a-after-switch"}\n')
        f.flush()
    with open(file_b, "a", encoding="utf-8") as f:
        f.write('{"src": "b"}\n')
        f.flush()

    await asyncio.sleep(1.0)
    watcher.stop()

    sources = [e["src"] for e in received]
    assert "a" in sources
    assert "b" in sources
    assert "a-after-switch" not in sources


@pytest.mark.asyncio
async def test_watcher_no_pierde_eventos_al_volver(tmp_path):
    """Regresion flip-flop: si se escribe en A mientras el watcher mira B, al
    VOLVER a A esos eventos NO se pierden. Antes set_active_file saltaba al final
    (seek-to-end) y descartaba lo escrito antes del cambio -> Jeffri se comia
    respuestas de Claude cuando habia 2 sesiones activas alternandose."""
    file_a = tmp_path / "a.jsonl"
    file_b = tmp_path / "b.jsonl"
    file_a.write_text("")
    file_b.write_text("")

    received: list[dict] = []

    async def on_event(event: dict):
        received.append(event)

    watcher = TranscriptWatcher(tmp_path, on_event)
    watcher.start()
    watcher.set_active_file(file_a)
    await asyncio.sleep(0.2)

    # evento a1 mientras miramos A
    with open(file_a, "a", encoding="utf-8") as f:
        f.write('{"src": "a1"}\n')
        f.flush()
    await asyncio.sleep(0.4)

    # cambiar a B y, MIENTRAS estamos en B, escribir a2 en A
    watcher.set_active_file(file_b)
    with open(file_a, "a", encoding="utf-8") as f:
        f.write('{"src": "a2-escrito-en-b"}\n')
        f.flush()
    await asyncio.sleep(0.3)

    # VOLVER a A: a2 debe reenviarse (no perderse por seek-to-end)
    watcher.set_active_file(file_a)
    with open(file_a, "a", encoding="utf-8") as f:
        f.write('{"src": "a3"}\n')
        f.flush()
    await asyncio.sleep(1.0)
    watcher.stop()

    sources = [e["src"] for e in received]
    assert "a1" in sources
    assert "a2-escrito-en-b" in sources  # lo critico: NO se pierde al volver
    assert "a3" in sources
