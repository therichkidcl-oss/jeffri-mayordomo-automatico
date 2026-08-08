import asyncio
import json

from src.voice.brain import Brain, BrainResponse, is_affirmative, is_negative


class FakeClient:
    """Cliente DeepSeek falso: devuelve respuestas encoladas."""
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def chat(self, messages, tools=None, **kw):
        self.calls.append({"messages": list(messages), "tools": tools})
        return self._responses.pop(0)


def _content(text):
    return {"role": "assistant", "content": text}


def _tool_call(name, args):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "c1", "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args)}}],
    }


def _run(coro):
    return asyncio.run(coro)


# --- deteccion si/no ---

def test_is_affirmative():
    for w in ["si", "sí", "dale", "hazlo", "mandalo", "confirmo", "correcto", "ok"]:
        assert is_affirmative(w), w
    assert not is_affirmative("no")


def test_is_negative():
    for w in ["no", "cancela", "espera", "mejor no"]:
        assert is_negative(w), w
    assert not is_negative("si")


# --- charla / opinion ---

def test_plain_conversation_speaks_and_no_dispatch():
    client = FakeClient([_content("Opino que Redis es buena idea, Sir Rich.")])
    b = Brain(client, search_fn=lambda q, max_results=5: [])
    r = _run(b.handle_user_turn("que opinas de usar redis?"))
    assert isinstance(r, BrainResponse)
    assert "Redis" in r.speech
    assert r.dispatch_prompt is None
    # el turno queda en el historial
    assert any("redis" in m.get("content", "").lower() for m in b.history)


# --- busqueda web ---

def test_web_search_tool_then_final_answer():
    # 1ra respuesta: pide buscar; 2da: responde con lo encontrado
    client = FakeClient([
        _tool_call("web_search", {"query": "precio bitcoin hoy"}),
        _content("Segun lo que encontre, ronda los 100k, Sir Rich."),
    ])
    captured = {}
    def fake_search(q, max_results=5):
        captured["q"] = q
        return [{"title": "BTC", "url": "http://x", "snippet": "100k"}]
    b = Brain(client, search_fn=fake_search)
    r = _run(b.handle_user_turn("cuanto vale el bitcoin?"))
    assert captured["q"] == "precio bitcoin hoy"
    assert "100k" in r.speech
    assert r.dispatch_prompt is None


# --- despacho a Claude con confirmacion ---

def test_dispatch_asks_confirmation_first():
    client = FakeClient([
        _tool_call("dispatch_to_claude", {"prompt": "Arregla el bug del login."}),
    ])
    b = Brain(client, search_fn=lambda q, max_results=5: [])
    r = _run(b.handle_user_turn("arregla el login"))
    assert r.dispatch_prompt is None  # todavia NO se manda
    assert b.state == "awaiting_confirmation"
    assert "Arregla el bug del login." in r.speech  # propone el prompt
    assert b._pending_prompt == "Arregla el bug del login."


def test_confirmation_yes_dispatches():
    client = FakeClient([
        _tool_call("dispatch_to_claude", {"prompt": "Arregla el login."}),
    ])
    b = Brain(client, search_fn=lambda q, max_results=5: [])
    _run(b.handle_user_turn("arregla el login"))
    r = _run(b.handle_user_turn("si, dale"))
    assert r.dispatch_prompt == "Arregla el login."  # AHORA se manda
    assert b.state == "idle"
    assert b._pending_prompt is None


def test_confirmation_no_reconverses():
    client = FakeClient([
        _tool_call("dispatch_to_claude", {"prompt": "Arregla el login."}),
        _content("Ok, dime como lo quieres entonces."),
    ])
    b = Brain(client, search_fn=lambda q, max_results=5: [])
    _run(b.handle_user_turn("arregla el login"))
    r = _run(b.handle_user_turn("no, espera"))
    assert r.dispatch_prompt is None
    assert b.state != "awaiting_confirmation"
    assert b._pending_prompt is None


# --- resumen de Claude ---

def test_summarize_claude():
    client = FakeClient([_content("Claude arreglo el login y corrio los tests.")])
    b = Brain(client, search_fn=lambda q, max_results=5: [])
    r = _run(b.summarize_claude("[texto largo y tecnico de Claude...]"))
    assert "login" in r.lower()
