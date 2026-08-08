"""Cliente DeepSeek (API compatible con OpenAI).

DeepSeek expone un endpoint estilo OpenAI: POST {base_url}/chat/completions con
el header Authorization: Bearer {api_key}. A diferencia del cliente Groq, aca se
usa UNA sola API key (sin rotacion).

Uso:
    client = DeepSeekClient(api_key, base_url, model)
    message = await client.chat(messages, tools=..., temperature=..., max_tokens=...)
    # message == {"role": "assistant", "content": str | None, "tool_calls": [...]?}
"""
import logging

import httpx

logger = logging.getLogger(__name__)


class DeepSeekError(Exception):
    """Error del cliente DeepSeek (status distinto de 200 o fallo de red)."""


class DeepSeekClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
    ):
        if not api_key:
            raise ValueError("Se requiere una API key de DeepSeek")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 1500,
    ) -> dict:
        """Envia una peticion de chat y devuelve el objeto 'message' de la primera choice.

        El dict devuelto tiene la forma:
            {"role": "assistant", "content": str | None, "tool_calls": [...]}
        donde "tool_calls" solo aparece si el modelo decidio invocar herramientas.

        Levanta DeepSeekError si el status no es 200 o si hay un error de red.
        """
        body: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # Solo se incluye 'tools' en el body si el caller paso herramientas.
        if tools is not None:
            body["tools"] = tools

        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                r = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=body,
                )
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                resp = e.response
                status = getattr(resp, "status_code", "desconocido")
                detail = (getattr(resp, "text", "") or "")[:500]
                logger.warning(f"DeepSeek respondio status {status}: {detail}")
                raise DeepSeekError(
                    f"DeepSeek respondio status {status}: {detail}"
                ) from e
            except httpx.RequestError as e:
                logger.warning(f"Error de red con DeepSeek ({type(e).__name__}): {e}")
                raise DeepSeekError(f"Error de red con DeepSeek: {e}") from e

            # Defensa extra: raise_for_status solo cubre 4xx/5xx; cualquier otro
            # codigo que no sea 200 tambien se considera error.
            if r.status_code != 200:
                detail = (getattr(r, "text", "") or "")[:500]
                raise DeepSeekError(
                    f"DeepSeek respondio status {r.status_code}: {detail}"
                )

            data = r.json()
            return data["choices"][0]["message"]
