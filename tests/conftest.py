"""Test-suite-wide env-var defaults.

Runs at collection time, BEFORE any `import src.config`. Without this, every
test that touches `src.security` (or anything that imports config) would
ImportError on a clean checkout where `.env` is empty.

Precedence: `os.environ.setdefault(...)` only sets if absent. python-dotenv's
`load_dotenv()` defaults to `override=False`, so a real `.env` will NOT
overwrite these defaults during tests. Tests needing specific values must
use `monkeypatch.setenv` (see test_config.py for the pattern).
"""
import os

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("TELEGRAM_ALLOWED_USER_ID", "0")
os.environ.setdefault("CLAUDE_PROJECTS_DIR", "C:\\Users\\Reimo\\.claude\\projects")
