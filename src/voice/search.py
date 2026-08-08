"""Busqueda web via DuckDuckGo (libreria ddgs, sin API key).

Le da al cerebro de Jeffri acceso a informacion fresca de internet. El diseno
es a prueba de fallos: si la busqueda falla (sin red, timeout, cambio de API),
`web_search` devuelve [] en vez de lanzar, para que el cerebro siga respondiendo
aunque sea sin resultados de busqueda.
"""
import logging

from ddgs import DDGS

logger = logging.getLogger(__name__)


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Busca en la web via DuckDuckGo. Devuelve lista de
    {"title": str, "url": str, "snippet": str}. Si falla, devuelve []
    (nunca lanza — el cerebro debe seguir funcionando sin busqueda)."""
    try:
        raw = DDGS().text(query, max_results=max_results)
        results: list[dict] = []
        for item in raw or []:
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("href", ""),
                    "snippet": item.get("body", ""),
                }
            )
        return results
    except Exception as exc:  # sin red, timeout, cambio de API, etc.
        logger.warning(f"Busqueda web fallo para '{query}': {exc}")
        return []


def format_results_for_llm(results: list[dict]) -> str:
    """Formatea los resultados como texto compacto para inyectar al LLM:
    '[1] Titulo\n  snippet\n  url\n[2] ...'. Si vacio, devuelve
    'Sin resultados de busqueda.'"""
    if not results:
        return "Sin resultados de busqueda."
    bloques = []
    for i, r in enumerate(results, start=1):
        titulo = r.get("title", "")
        snippet = r.get("snippet", "")
        url = r.get("url", "")
        bloques.append(f"[{i}] {titulo}\n  {snippet}\n  {url}")
    return "\n".join(bloques)
