"""Die Hotkey-Konfiguration muss dort gelesen werden, wo sie auch liegt.

Zwei Betriebsarten mit zwei verschiedenen richtigen Orten:
  fertige EXE  → config.json neben der EXE (wanderungsfähig, Entscheidung 6)
  Quellcode    → windows/config.json, die versionierte Datei

`_base` zeigt beim Quellcode-Start auf den Projektordner — richtig für die
`.env` und die Logdatei, falsch für die Konfiguration. Wird das verwechselt,
greift stillschweigend der Notfall-Standard und jede gespeicherte Wahl landet
in einer unversionierten Streudatei.
"""
import pathlib

import typefree


def test_konfiguration_liegt_neben_dem_skript():
    erwartet = pathlib.Path(typefree.__file__).resolve().parent / 'config.json'
    assert pathlib.Path(typefree.CONFIG_PATH).resolve() == erwartet


def test_konfigurationsdatei_ist_wirklich_vorhanden():
    """Fehlt sie, greift unbemerkt der Notfall-Standard."""
    assert pathlib.Path(typefree.CONFIG_PATH).exists()


def test_pfade_enthalten_keine_rueckwaertsschritte():
    """Ein „..\" mitten im Pfad steht sonst in jeder Protokollzeile."""
    for pfad in (typefree.LOG_PATH, typefree.VERBRAUCH_PATH, typefree._base):
        assert '..' not in pfad, pfad


def test_gespeicherte_wahl_wird_auch_gelesen():
    """Was load_hotkey_config liefert, muss zum Inhalt der Datei passen."""
    import json
    with open(typefree.CONFIG_PATH, encoding='utf-8') as f:
        index = json.load(f)['hotkey_index']
    assert typefree.load_hotkey_config() is typefree.HOTKEY_OPTIONS[index]
