"""Tests del cliente DeepSeek (TDD).

Se mockea httpx.AsyncClient con un doble (context manager async) para no tocar
la red. Cada test envuelve la corrutina con asyncio.run(...) dentro de una
funcion sync, asi NO dependemos del plugin pytest-asyncio.
"""
import asyncio

import httpx
import pytest

from src.voice.deepseek_client import DeepSeekClient, DeepSeekError


class FakeResponse:
    """Respuesta HTTP falsa con la interfaz minima que usa el cliente."""

    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://api.deepseek.com/chat/completions")
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=request, response=self
            )


def _install_fake_client(monkeypatch, response=None, raise_on_post=None):
    """Reemplaza httpx.AsyncClient por un doble y devuelve el dict `captured`.

    captured guarda url/headers/json de la ultima llamada a .post y los kwargs
    de construccion del cliente. Si `raise_on_post` se pasa, .post levanta esa
    excepcion (para simular un error de red).
    """
    captured: dict = {}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            if raise_on_post is not None:
                raise raise_on_post
            return response

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    return captured


def test_chat_returns_message_content(monkeypatch):
    resp = FakeResponse(
        status_code=200,
        json_data={
            "choices": [
                {"message": {"role": "assistant", "content": "hola"}}
            ]
        },
    )
    _install_fake_client(monkeypatch, response=resp)

    client = DeepSeekClient(api_key="k")
    message = asyncio.run(client.chat([{"role": "user", "content": "hey"}]))

    assert message["content"] == "hola"
    assert message["role"] == "assistant"


def test_chat_returns_tool_calls(monkeypatch):
    tool_calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "buscar", "arguments": "{}"},
        }
    ]
    resp = FakeResponse(
        status_code=200,
        json_data={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": tool_calls,
                    }
                }
            ]
        },
    )
    _install_fake_client(monkeypatch, response=resp)

    client = DeepSeekClient(api_key="k")
    message = asyncio.run(
        client.chat(
            [{"role": "user", "content": "buscame algo"}],
            tools=[{"type": "function", "function": {"name": "buscar"}}],
        )
    )

    assert "tool_calls" in message
    assert message["tool_calls"] == tool_calls
    assert message["content"] is None


def test_chat_omits_tools_when_none(monkeypatch):
    resp = FakeResponse(
        status_code=200,
        json_data={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
    )
    captured = _install_fake_client(monkeypatch, response=resp)
    client = DeepSeekClient(api_key="k")

    # Sin tools -> la clave "tools" NO debe ir en el body.
    asyncio.run(client.chat([{"role": "user", "content": "hola"}]))
    assert "tools" not in captured["json"]

    # Con tools -> la clave "tools" SI debe ir en el body.
    tools = [{"type": "function", "function": {"name": "buscar"}}]
    asyncio.run(client.chat([{"role": "user", "content": "hola"}], tools=tools))
    assert "tools" in captured["json"]
    assert captured["json"]["tools"] == tools


def test_chat_raises_on_error_status(monkeypatch):
    resp = FakeResponse(
        status_code=400,
        json_data={"error": "bad request"},
        text='{"error":"bad request"}',
    )
    _install_fake_client(monkeypatch, response=resp)

    client = DeepSeekClient(api_key="k")
    with pytest.raises(DeepSeekError):
        asyncio.run(client.chat([{"role": "user", "content": "x"}]))


def test_chat_raises_on_network_error(monkeypatch):
    # httpx.ConnectError es subclase de httpx.RequestError.
    err = httpx.ConnectError("sin conexion")
    _install_fake_client(monkeypatch, raise_on_post=err)

    client = DeepSeekClient(api_key="k")
    with pytest.raises(DeepSeekError):
        asyncio.run(client.chat([{"role": "user", "content": "x"}]))
