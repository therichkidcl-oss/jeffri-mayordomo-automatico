import os
from pathlib import Path
import pytest


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_token_123")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "987654321")
    monkeypatch.setenv("CLAUDE_PROJECTS_DIR", "C:\\fake\\path")

    import importlib
    import src.config
    importlib.reload(src.config)

    assert src.config.TELEGRAM_BOT_TOKEN == "fake_token_123"
    assert src.config.ALLOWED_USER_ID == 987654321
    assert src.config.CLAUDE_PROJECTS_DIR == Path("C:\\fake\\path")


def test_config_fails_without_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "987654321")
    monkeypatch.setenv("CLAUDE_PROJECTS_DIR", "C:\\fake\\path")

    import importlib
    import src.config
    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        importlib.reload(src.config)
