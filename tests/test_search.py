"""Tests para src.voice.search (busqueda web via DuckDuckGo).

Se mockea DDGS para no depender de la red. El patron sigue test_stt.py:
monkeypatch sobre el simbolo importado en el modulo (src.voice.search.DDGS).
"""
from src.voice.search import web_search, format_results_for_llm


class _FakeDDGS:
    """Doble de DDGS: .text() devuelve lo que se le configure en la clase."""

    _results: list[dict] = []

    def text(self, query, max_results=5):
        return self._results


def test_web_search_maps_fields(monkeypatch):
    class Fake(_FakeDDGS):
        _results = [{"title": "T", "href": "http://x", "body": "B"}]

    monkeypatch.setattr("src.voice.search.DDGS", Fake)
    assert web_search("q") == [{"title": "T", "url": "http://x", "snippet": "B"}]


def test_web_search_returns_empty_on_error(monkeypatch):
    class Boom:
        def text(self, query, max_results=5):
            raise RuntimeError("sin red")

    monkeypatch.setattr("src.voice.search.DDGS", Boom)
    assert web_search("q") == []  # nunca lanza: el cerebro sigue sin busqueda


def test_format_results_numbered():
    results = [
        {"title": "Titulo Uno", "url": "http://uno", "snippet": "resumen uno"},
        {"title": "Titulo Dos", "url": "http://dos", "snippet": "resumen dos"},
    ]
    out = format_results_for_llm(results)
    assert "[1]" in out
    assert "[2]" in out
    assert "Titulo Uno" in out
    assert "resumen uno" in out
    assert "http://uno" in out


def test_format_empty():
    assert format_results_for_llm([]) == "Sin resultados de busqueda."
