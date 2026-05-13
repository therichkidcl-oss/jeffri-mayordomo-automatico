import pytest
from src.security import is_destructive


@pytest.mark.parametrize("text", [
    "borra el archivo bot.py",
    "elimina la base de datos",
    "rm -rf /tmp/foo",
    "DELETE FROM users",
    "drop table users",
    "vercel --prod",
    "haz deploy a producción",
    "git push --force",
    "force-push al main",
    "TRUNCATE TABLE users",
    "git reset --hard HEAD~1",
    "git clean -fd",
    "drop database mydb",
    "drop schema public",
])
def test_is_destructive_detects(text):
    assert is_destructive(text) is True


@pytest.mark.parametrize("text", [
    "lee el archivo bot.py",
    "muéstrame los logs",
    "qué hace este código",
    "explícame la función",
    "agrega un test",
    "crea un nuevo endpoint",
    "drop me a message",
    "drop your phone",
    "just drop a hint",
])
def test_is_destructive_safe_strings(text):
    assert is_destructive(text) is False
