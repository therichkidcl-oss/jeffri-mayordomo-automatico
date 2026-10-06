"""Tests de persistencia del titulo honorifico (TDD).

Jeffri le pregunta al usuario como quiere que lo trate ("Sir Smith", "Jefa",
"Master", lo que sea) en su primer /start y lo persiste. Este modulo maneja
el read/write; el flow de bienvenida vive en bot.py.
"""
import json

import pytest

from src.user_settings import clear_title, load_title, save_title


def test_load_title_devuelve_none_sin_archivo(tmp_path, monkeypatch):
    settings = tmp_path / "no_existe.json"
    monkeypatch.setattr("src.user_settings._SETTINGS_PATH", settings)

    assert load_title() is None


def test_save_y_load_roundtrip(tmp_path, monkeypatch):
    settings = tmp_path / "user_settings.json"
    monkeypatch.setattr("src.user_settings._SETTINGS_PATH", settings)

    save_title("Senora Smith")
    assert load_title() == "Senora Smith"
    assert settings.exists()


def test_save_crea_directorio_si_falta(tmp_path, monkeypatch):
    settings = tmp_path / "data" / "subdir" / "user_settings.json"
    monkeypatch.setattr("src.user_settings._SETTINGS_PATH", settings)

    save_title("Jefa")
    assert settings.exists()
    assert load_title() == "Jefa"


def test_load_json_corrupto_devuelve_none(tmp_path, monkeypatch):
    settings = tmp_path / "user_settings.json"
    settings.write_text("esto no es json valido {{{")
    monkeypatch.setattr("src.user_settings._SETTINGS_PATH", settings)

    assert load_title() is None


def test_load_json_sin_campo_title_devuelve_none(tmp_path, monkeypatch):
    settings = tmp_path / "user_settings.json"
    settings.write_text(json.dumps({"otro_campo": "x"}))
    monkeypatch.setattr("src.user_settings._SETTINGS_PATH", settings)

    assert load_title() is None


def test_save_sobreescribe_titulo_anterior(tmp_path, monkeypatch):
    settings = tmp_path / "user_settings.json"
    monkeypatch.setattr("src.user_settings._SETTINGS_PATH", settings)

    save_title("Sir Smith")
    save_title("Master")
    assert load_title() == "Master"


def test_save_strippea_whitespace(tmp_path, monkeypatch):
    settings = tmp_path / "user_settings.json"
    monkeypatch.setattr("src.user_settings._SETTINGS_PATH", settings)

    save_title("  Sir Smith   \n")
    assert load_title() == "Sir Smith"


def test_save_rechaza_titulo_vacio(tmp_path, monkeypatch):
    settings = tmp_path / "user_settings.json"
    monkeypatch.setattr("src.user_settings._SETTINGS_PATH", settings)

    with pytest.raises(ValueError):
        save_title("")
    with pytest.raises(ValueError):
        save_title("   ")


def test_clear_title_borra_el_archivo(tmp_path, monkeypatch):
    settings = tmp_path / "user_settings.json"
    monkeypatch.setattr("src.user_settings._SETTINGS_PATH", settings)

    save_title("Sir Smith")
    assert settings.exists()

    clear_title()
    assert not settings.exists()
    assert load_title() is None


def test_clear_title_no_falla_si_no_hay_archivo(tmp_path, monkeypatch):
    settings = tmp_path / "no_existe.json"
    monkeypatch.setattr("src.user_settings._SETTINGS_PATH", settings)

    clear_title()  # No debe levantar.


def test_load_title_preserva_tildes_y_caracteres_especiales(tmp_path, monkeypatch):
    """El usuario puede escribir con tildes, enies, etc. Debe sobrevivir el roundtrip."""
    settings = tmp_path / "user_settings.json"
    monkeypatch.setattr("src.user_settings._SETTINGS_PATH", settings)

    save_title("Doña María")
    assert load_title() == "Doña María"
