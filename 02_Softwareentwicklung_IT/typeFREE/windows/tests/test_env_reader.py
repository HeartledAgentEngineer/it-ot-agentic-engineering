"""Der `.env`-Leser muss Schlüssel unverfälscht durchlassen.

Ein Zeichen zu viel im Schlüssel bedeutet einen 401 vom Anbieter — und der
kostete am 29.07.2026 einen Abend Fehlersuche. Deshalb geprüft:
Kommentare am Zeilenende, Anführungszeichen, Vorrang echter Umgebungsvariablen.
"""
import io

import typefree


def _env_schreiben(tmp_path, inhalt):
    pfad = tmp_path / '.env'
    with io.open(pfad, 'w', encoding='utf-8') as f:
        f.write(inhalt)
    return str(pfad)


def test_kommentar_am_zeilenende_gehoert_nicht_zum_schluessel(tmp_path, monkeypatch):
    monkeypatch.delenv('PRUEF_SCHLUESSEL', raising=False)
    pfad = _env_schreiben(tmp_path, 'PRUEF_SCHLUESSEL=sk-abc123 # mein Kommentar\n')
    typefree.load_env_file(pfad)
    import os
    assert os.environ['PRUEF_SCHLUESSEL'] == 'sk-abc123'


def test_raute_ohne_leerzeichen_bleibt_im_wert(tmp_path, monkeypatch):
    """Ein Schlüssel darf ein # enthalten — nur abgesetzte Kommentare zählen."""
    monkeypatch.delenv('PRUEF_RAUTE', raising=False)
    pfad = _env_schreiben(tmp_path, 'PRUEF_RAUTE=abc#def\n')
    typefree.load_env_file(pfad)
    import os
    assert os.environ['PRUEF_RAUTE'] == 'abc#def'


def test_anfuehrungszeichen_werden_entfernt(tmp_path, monkeypatch):
    monkeypatch.delenv('PRUEF_ZITAT', raising=False)
    pfad = _env_schreiben(tmp_path, 'PRUEF_ZITAT="sk-mit-anfuehrung"\n')
    typefree.load_env_file(pfad)
    import os
    assert os.environ['PRUEF_ZITAT'] == 'sk-mit-anfuehrung'


def test_echte_umgebungsvariable_hat_vorrang(tmp_path, monkeypatch):
    """Beim Entwickeln muss man einen anderen Schlüssel vorgeben können."""
    monkeypatch.setenv('PRUEF_VORRANG', 'aus-der-umgebung')
    pfad = _env_schreiben(tmp_path, 'PRUEF_VORRANG=aus-der-datei\n')
    typefree.load_env_file(pfad)
    import os
    assert os.environ['PRUEF_VORRANG'] == 'aus-der-umgebung'


def test_kommentarzeilen_und_leerzeilen_werden_uebersprungen(tmp_path):
    pfad = _env_schreiben(
        tmp_path, '# nur ein Kommentar\n\nPRUEF_LEER=wert\n\n')
    gefunden = typefree.load_env_file(pfad)
    assert gefunden == ['PRUEF_LEER']


def test_installierte_anlage_gewinnt_gegen_die_umgebungsvariable(tmp_path, monkeypatch):
    """Der eigene .env schlägt eine gleichnamige Benutzer-Variable (06.10.2026).

    Anlass: `OPENROUTER_API_KEY` stand in der Windows-Umgebung auf dem Schlüssel
    „critic-Skill". typeFREE buchte jedes Diktat dort, der eigene Schlüssel
    „typeFree" blieb bei 0,00 $ — und die Kosten waren nicht mehr zuzuordnen.
    """
    monkeypatch.setenv('PRUEF_EXE', 'aus-der-umgebung')
    monkeypatch.setattr(typefree, 'FROZEN', True)
    pfad = _env_schreiben(tmp_path, 'PRUEF_EXE=aus-der-datei\n')
    typefree.load_env_file(pfad)
    import os
    assert os.environ['PRUEF_EXE'] == 'aus-der-datei'


def test_quellcode_start_behaelt_die_umgebungsvariable(tmp_path, monkeypatch):
    """Beim Entwickeln bleibt der Terminal-Schlüssel vorn — bewusst so."""
    monkeypatch.setenv('PRUEF_QUELLE', 'aus-der-umgebung')
    monkeypatch.setattr(typefree, 'FROZEN', False)
    pfad = _env_schreiben(tmp_path, 'PRUEF_QUELLE=aus-der-datei\n')
    typefree.load_env_file(pfad)
    import os
    assert os.environ['PRUEF_QUELLE'] == 'aus-der-umgebung'
