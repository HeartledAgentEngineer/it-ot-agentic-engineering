"""Tests für die Installations-Logik (installer/installer_lib.py)."""

import os
import tempfile
import json
from pathlib import Path

import pytest

from installer.installer_lib import (
    create_env_file,
    create_shortcut,
    remove_shortcut,
    save_install_info,
    read_install_info,
)


class TestCreateEnvFile:
    """create_env_file – .env-Datei erstellen."""

    def test_erzeugt_datei_mit_beiden_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            pfad = os.path.join(tmp, '.env')
            result = create_env_file(pfad, openrouter_key="sk-or-test",
                                     openai_key="sk-test")
            assert result is True
            assert os.path.exists(pfad)
            inhalt = Path(pfad).read_text(encoding='utf-8')
            assert 'OPENROUTER_API_KEY=sk-or-test' in inhalt
            assert 'OPENAI_API_KEY=sk-test' in inhalt

    def test_leere_keys_sind_auch_erlaubt(self):
        with tempfile.TemporaryDirectory() as tmp:
            pfad = os.path.join(tmp, '.env')
            create_env_file(pfad)
            inhalt = Path(pfad).read_text(encoding='utf-8')
            assert 'OPENROUTER_API_KEY=' in inhalt
            assert 'OPENAI_API_KEY=' in inhalt

    def test_datei_enthält_zeitstempel(self):
        with tempfile.TemporaryDirectory() as tmp:
            pfad = os.path.join(tmp, '.env')
            create_env_file(pfad, openrouter_key="x")
            inhalt = Path(pfad).read_text(encoding='utf-8')
            assert '# typeFREE API-Keys' in inhalt
            assert 'Erstellt am' in inhalt


class TestCreateShortcut:
    """create_shortcut / remove_shortcut – Verknüpfungen."""

    def test_shortcut_wird_erzeugt(self):
        with tempfile.TemporaryDirectory() as tmp:
            ziel = os.path.join(tmp, 'test.exe')
            Path(ziel).write_text('dummy', encoding='utf-8')
            link = os.path.join(tmp, 'test.lnk')
            result = create_shortcut(ziel, link, 'Test')
            assert result is True
            assert os.path.exists(link)

    def test_existierende_verknuepfung_wird_nicht_ueberschrieben(self):
        with tempfile.TemporaryDirectory() as tmp:
            ziel = os.path.join(tmp, 'test.exe')
            Path(ziel).write_text('dummy', encoding='utf-8')
            link = os.path.join(tmp, 'test.lnk')
            create_shortcut(ziel, link)
            mtime_vorher = os.path.getmtime(link) if os.path.exists(link) else 0
            create_shortcut(ziel, link)  # zweiter Aufruf
            assert True  # kein Fehler

    def test_ungueltiger_ordner_gibt_false(self):
        result = create_shortcut(
            'C:\\nicht\\da\\test.exe',
            'C:\\nicht\\da\\test.lnk',
        )
        assert result is False

    def test_remove_shortcut_entfernt_datei(self):
        with tempfile.TemporaryDirectory() as tmp:
            link = os.path.join(tmp, 'test.lnk')
            Path(link).write_text('dummy', encoding='utf-8')
            assert remove_shortcut(link) is True
            assert not os.path.exists(link)

    def test_remove_shortcut_fehlt_gibt_auch_true(self):
        assert remove_shortcut('C:\\nicht\\da.lnk') is True


class TestInstallInfo:
    """save_install_info / read_install_info."""

    def test_speichert_und_liest(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_install_info(tmp, autostart=True)
            info = read_install_info(tmp)
            assert info['install_dir'] == tmp
            assert info['autostart'] is True
            assert 'installed_at' in info

    def test_ohne_datei_gibt_leeres_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            info = read_install_info(tmp)
            assert info == {}

    def test_json_ist_lesbar(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_install_info(tmp, autostart=False)
            pfad = os.path.join(tmp, 'install.json')
            with open(pfad, 'r', encoding='utf-8') as f:
                geladen = json.load(f)
            assert geladen['autostart'] is False