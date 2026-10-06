"""Persistencia del titulo honorifico que el usuario eligio.

Jeffri es un mayordomo: cuando el usuario arranca el bot por primera vez,
Jeffri le pregunta en tono sumiso como desea que se le dirija (Sir Smith,
Jefa, Master, Doctor, etc.). La respuesta se guarda aqui y persiste entre
reinicios.

Formato en disco: `data/user_settings.json`

```json
{"title": "Sir Smith"}
```

El archivo es local-user y esta gitignoreado — nunca llega al repo publico.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Modificable por tests via monkeypatch — en produccion siempre es este path.
_SETTINGS_PATH: Path = Path("data/user_settings.json")


def load_title() -> str | None:
    """Devuelve el titulo guardado, o None si no hay nada / archivo invalido."""
    path = _SETTINGS_PATH
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"user_settings.json invalido ({e}); se ignora")
        return None
    title = data.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return None


def save_title(title: str) -> None:
    """Persiste el titulo. Rechaza strings vacios o solo whitespace."""
    cleaned = (title or "").strip()
    if not cleaned:
        raise ValueError("El titulo no puede estar vacio")

    path = _SETTINGS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"title": cleaned}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Titulo del usuario guardado: {cleaned!r}")


def clear_title() -> None:
    """Borra el archivo de settings. Si no existe, no hace nada."""
    path = _SETTINGS_PATH
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError as e:
        logger.warning(f"No pude borrar user_settings.json ({e})")
