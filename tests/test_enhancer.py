"""Tests de PromptEnhancer (TDD).

Mockea httpx.AsyncClient con un doble (context manager async) para no tocar la
red. Cada test envuelve la corrutina con asyncio.run(...) dentro de una funcion
sync, siguiendo el mismo patron de test_deepseek_client.py.
"""
import asyncio

import httpx
import pytest

from src.enhancer import PromptEnhancer, EnhancerError


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


def _ok_response(content="resultado"):
    return FakeResponse(
        status_code=200,
        json_data={
            "choices": [
                {"message": {"role": "assistant", "content": content}}
            ]
        },
    )


def test_init_falla_con_api_key_vacia():
    with pytest.raises(ValueError):
        PromptEnhancer(api_key="")


def test_enhance_default_source_es_texto(monkeypatch):
    captured = _install_fake_client(monkeypatch, response=_ok_response())
    enhancer = PromptEnhancer(api_key="k")
    asyncio.run(enhancer.enhance("arregla el bug"))

    # El prompt de texto es el DEFAULT — sin source, se usa MEJORADOR DE PROMPTS.
    system = captured["json"]["messages"][0]
    assert system["role"] == "system"
    assert "MEJORADOR DE PROMPTS" in system["content"]


def test_enhance_texto_usa_prompt_de_texto(monkeypatch):
    captured = _install_fake_client(monkeypatch, response=_ok_response())
    enhancer = PromptEnhancer(api_key="k")
    asyncio.run(enhancer.enhance("mensaje escrito", source="texto"))

    system = captured["json"]["messages"][0]
    assert "MEJORADOR DE PROMPTS" in system["content"]
    # NO debe usar el prompt de voz.
    assert "LIMPIADOR Y ESTRUCTURADOR" not in system["content"]


def test_enhance_voz_usa_prompt_de_voz(monkeypatch):
    captured = _install_fake_client(monkeypatch, response=_ok_response())
    enhancer = PromptEnhancer(api_key="k")
    asyncio.run(enhancer.enhance("eh este bueno arregla el bug", source="voz"))

    system = captured["json"]["messages"][0]
    assert "LIMPIADOR Y ESTRUCTURADOR" in system["content"]
    assert "MEJORADOR DE PROMPTS" not in system["content"]


def test_enhance_apaga_thinking_mode(monkeypatch):
    """DeepSeek V4.1-Flash tiene thinking mode ON por default; un enhancer NO lo quiere."""
    captured = _install_fake_client(monkeypatch, response=_ok_response())
    enhancer = PromptEnhancer(api_key="k")
    asyncio.run(enhancer.enhance("algo"))

    body = captured["json"]
    assert "thinking" in body
    assert body["thinking"] == {"type": "disabled"}


def test_enhance_usa_modelo_configurado(monkeypatch):
    captured = _install_fake_client(monkeypatch, response=_ok_response())
    enhancer = PromptEnhancer(api_key="k", model="deepseek-flash")
    asyncio.run(enhancer.enhance("algo"))

    assert captured["json"]["model"] == "deepseek-flash"


def test_enhance_manda_temperature_y_max_tokens(monkeypatch):
    captured = _install_fake_client(monkeypatch, response=_ok_response())
    enhancer = PromptEnhancer(api_key="k")
    asyncio.run(enhancer.enhance("algo"))

    body = captured["json"]
    assert body["temperature"] == 0.3
    assert body["max_tokens"] == 1024


def test_enhance_pasa_texto_como_user_message(monkeypatch):
    captured = _install_fake_client(monkeypatch, response=_ok_response())
    enhancer = PromptEnhancer(api_key="k")
    asyncio.run(enhancer.enhance("arregla el login", source="texto"))

    messages = captured["json"]["messages"]
    assert len(messages) == 2
    assert messages[1] == {"role": "user", "content": "arregla el login"}


def test_enhance_devuelve_content_stripped(monkeypatch):
    _install_fake_client(monkeypatch, response=_ok_response(content="  resultado limpio  \n"))
    enhancer = PromptEnhancer(api_key="k")
    result = asyncio.run(enhancer.enhance("algo"))

    assert result == "resultado limpio"


def test_enhance_url_apunta_a_chat_completions(monkeypatch):
    captured = _install_fake_client(monkeypatch, response=_ok_response())
    enhancer = PromptEnhancer(api_key="k", base_url="https://api.deepseek.com")
    asyncio.run(enhancer.enhance("algo"))

    assert captured["url"] == "https://api.deepseek.com/chat/completions"


def test_enhance_manda_bearer_token(monkeypatch):
    captured = _install_fake_client(monkeypatch, response=_ok_response())
    enhancer = PromptEnhancer(api_key="sk-test-123")
    asyncio.run(enhancer.enhance("algo"))

    assert captured["headers"]["Authorization"] == "Bearer sk-test-123"


def test_enhance_raises_on_http_error(monkeypatch):
    resp = FakeResponse(
        status_code=500,
        json_data={"error": "server error"},
        text='{"error":"server error"}',
    )
    _install_fake_client(monkeypatch, response=resp)

    enhancer = PromptEnhancer(api_key="k")
    with pytest.raises(EnhancerError):
        asyncio.run(enhancer.enhance("algo"))


def test_enhance_raises_on_network_error(monkeypatch):
    _install_fake_client(monkeypatch, raise_on_post=httpx.ConnectError("sin conexion"))

    enhancer = PromptEnhancer(api_key="k")
    with pytest.raises(EnhancerError):
        asyncio.run(enhancer.enhance("algo"))


def test_enhance_source_desconocido_cae_a_texto(monkeypatch):
    """Un source distinto de 'voz' debe usar el prompt de texto (comportamiento defensivo)."""
    captured = _install_fake_client(monkeypatch, response=_ok_response())
    enhancer = PromptEnhancer(api_key="k")
    asyncio.run(enhancer.enhance("algo", source="imagen"))

    system = captured["json"]["messages"][0]
    assert "MEJORADOR DE PROMPTS" in system["content"]
