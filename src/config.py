import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Variable de entorno requerida no encontrada: {name}")
    return value


TELEGRAM_BOT_TOKEN: str = _require("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID: int = int(_require("TELEGRAM_ALLOWED_USER_ID"))
CLAUDE_PROJECTS_DIR: Path = Path(_require("CLAUDE_PROJECTS_DIR"))

_groq_keys_raw = os.environ.get("GROQ_API_KEYS", "")
GROQ_API_KEYS: list[str] = [k.strip() for k in _groq_keys_raw.split(",") if k.strip()]

WEB_BIND: str = os.environ.get("WEB_BIND", "127.0.0.1")
WEB_PORT: int = int(os.environ.get("WEB_PORT", "8000"))
WEB_AUTH_TOKEN: str = os.environ.get("WEB_AUTH_TOKEN", "")
