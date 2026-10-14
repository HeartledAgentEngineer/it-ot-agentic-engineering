"""Version in der EXE sichtbar (CI/CD-Plan 14.10.2026, Schritt 1).

Im August 2026 lief wochenlang ein veralteter Build, ohne dass es jemand sehen konnte.
Jetzt trägt die EXE Version und Commit, und die Startzeile im Log nennt sie.
"""
import importlib
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'ci'))

import typefree
import version
import version_schreiben


def test_quellcode_ist_immer_dev_auch_mit_liegengebliebener_builddatei(tmp_path, monkeypatch):
    """Codex 14.10.2026: eine alte `_version_build.py` darf den Quellcodestart nicht färben."""
    version_schreiben.schreiben('1.0.0', 'abcdef1', tmp_path / '_version_build.py')
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop('_version_build', None)
    try:
        neu = importlib.reload(version)
        assert (neu.VERSION, neu.COMMIT) == ('dev', 'lokal')
    finally:
        sys.modules.pop('_version_build', None)
        monkeypatch.undo()
        importlib.reload(version)


def test_spec_schreibt_die_version_bei_jedem_build():
    """Jeder Build-Weg (update_exe-Hinweis, build_installer.cmd, CI) geht über die Spec."""
    spec = (pathlib.Path(__file__).resolve().parents[2] / 'typeFREE.spec').read_text(encoding='utf-8')
    assert 'version_schreiben.schreiben(' in spec.split('a = Analysis(')[0]


def test_startzeile_beginnt_wie_bisher_und_nennt_die_version(monkeypatch):
    monkeypatch.setattr(version, 'VERSION', '1.2.0')
    monkeypatch.setattr(version, 'COMMIT', '85b072b')
    zeile = typefree.startmeldung('Alt + Ä', 'halten', 'alles auf einmal', 'turbo, mai')
    assert zeile.startswith('typeFREE gestartet')        # findstr in update_exe.cmd
    assert 'Version 1.2.0 (85b072b)' in zeile
    assert zeile.endswith('Transkription über: turbo, mai')


@pytest.mark.parametrize('roh, erwartet', [
    ('typefree-v1.2.0', '1.2.0'), ('v0.1.0', '0.1.0'), ('10.0.3', '10.0.3'), ('dev', 'dev')])
def test_version_aus_tag(roh, erwartet):
    assert version_schreiben.version_bereinigen(roh) == erwartet


@pytest.mark.parametrize('roh', ['1.2', 'typefree-v1.2.0-beta', "1.0.0'; import os", ''])
def test_ungueltige_version_wird_abgelehnt(roh):
    with pytest.raises(ValueError):
        version_schreiben.version_bereinigen(roh)


def test_ungueltiger_commit_wird_abgelehnt():
    with pytest.raises(ValueError):
        version_schreiben.commit_pruefen("abc'; x")


def test_exe_liest_die_geschriebene_datei(tmp_path, monkeypatch):
    ziel = version_schreiben.schreiben('typefree-v1.2.0', '85B072BC0FFEE', tmp_path / '_version_build.py')
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    sys.modules.pop('_version_build', None)
    try:
        neu = importlib.reload(version)
        assert (neu.VERSION, neu.COMMIT) == ('1.2.0', '85b072b')
    finally:
        sys.modules.pop('_version_build', None)
        monkeypatch.undo()
        importlib.reload(version)
    assert ziel.name == '_version_build.py'
