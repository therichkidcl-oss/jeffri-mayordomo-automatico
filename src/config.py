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
