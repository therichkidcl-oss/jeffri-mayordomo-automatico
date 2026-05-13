import logging
import re
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

from src.config import ALLOWED_USER_ID

logger = logging.getLogger(__name__)

# Patrones que disparan confirmación Sí/No antes de enviar el mensaje a Claude.
# Por diseño esta lista prefiere false-positives (botón de más) sobre false-negatives
# (operación destructiva sin confirmar). El plan dice que es expandible (design.md:226).
DESTRUCTIVE_PATTERNS = [
    r"\bborra\b",
    r"\belimina\b",
    r"\brm\s+-rf?\b",
    r"\bdelete\b",
    r"\bdrop\s+(table|database|schema|index|view|user|role|column|constraint|trigger|function|sequence)\b",
    r"\bdeploy\b",
    r"\bvercel\s+--prod\b",
    r"\bgit\s+push\s+(--force|-f)\b",
    r"\bforce[-\s]push\b",
    r"\bproducci[oó]n\b",
    r"\bprod\b",
    r"\btruncate\s+(table\s+)?\w+\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-f\w*\b",
]

_DESTRUCTIVE_RE = re.compile("|".join(DESTRUCTIVE_PATTERNS), re.IGNORECASE)


def is_destructive(text: str) -> bool:
    return bool(_DESTRUCTIVE_RE.search(text))


def requires_whitelist(handler):
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user is None or update.effective_user.id != ALLOWED_USER_ID:
            uid = update.effective_user.id if update.effective_user else "?"
            logger.warning(f"Unauthorized user {uid} tried to access bot")
            return
        return await handler(update, context)
    return wrapper
