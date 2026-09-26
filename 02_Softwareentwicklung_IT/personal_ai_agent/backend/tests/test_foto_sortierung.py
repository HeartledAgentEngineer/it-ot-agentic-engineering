"""Pruefungen fuer den Foto-Sortierschluessel (Stufe B: Jahr/Thema).

Getestet werden die reinen Funktionen — Datum aus dem Dateinamen, Motiv-Name
ohne Doppelungs-Kennzeichen, Zielordner. Kein pCloud-Zugriff, kein Netz.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

WERKZEUG = (Path(__file__).resolve().parents[2]
            / "tools" / "foto_sortierung" / "sortierschluessel.py")


def _laden():
    spez = importlib.util.spec_from_file_location("sortierschluessel", WERKZEUG)
    assert spez is not None and spez.loader is not None, (
        f"Werkzeug nicht gefunden: {WERKZEUG}")
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


_sort = _laden()


def test_datum_aus_android_namen():
    """Motorola- und OnePlus-Schemata tragen das Datum im Namen."""
    assert _sort.datum_aus_name("IMG_20250506_152946176_HDR.jpg") == (2025, 5, 6)
    assert _sort.datum_aus_name("image_20220730_142043_438.jpg") == (2022, 7, 30)
    assert _sort.datum_aus_name("20190209_161112_HDR.jpg") == (2019, 2, 9)
    assert _sort.datum_aus_name("VID20250225185258.mp4") == (2025, 2, 25)


def test_datum_aus_pcloud_umbenennung_mit_strich():
    """pCloud stellt 6 Ziffern voran: 059956_2024-08-09_17-14-43_96.jpg."""
    assert _sort.datum_aus_name("059956_2024-08-09_17-14-43_96.jpg") == (2024, 8, 9)


def test_datum_aus_millisekunden_namen():
    """Empfangene Bilder heissen nur nach ihrem Zeitstempel."""
    assert _sort.datum_aus_name("1768046027646.jpg") == (2026, 1, 10)


def test_kein_raten_bei_unbrauchbaren_namen():
    """Kein Datum heisst kein Datum — nicht irgendwas ableiten."""
    assert _sort.datum_aus_name("Oplus_0.mp4") is None
    assert _sort.datum_aus_name("file_0000000090b06246b47c2039a5a61547.png") is None
    assert _sort.datum_aus_name("ServicePW.jpg") is None
    # Unplausible Werte werden verworfen (Monat 13 gibt es nicht).
    assert _sort.datum_aus_name("IMG_20251332_120000.jpg") is None


def test_motiv_name_entfernt_doppelungen():
    """' (2)' und '_Kopie' sind dasselbe Motiv — sonst ist jede Zahl falsch."""
    assert (_sort.motiv_name("20190413_121818_HDR (2).jpg")
            == _sort.motiv_name("20190413_121818_HDR.jpg"))
    assert (_sort.motiv_name("Foto_Kopie.jpg") == _sort.motiv_name("Foto.jpg"))
    assert _sort.motiv_name("059956_2024-08-09_17-14-43_96.jpg") == "2024-08-09_17-14-43_96.jpg"


def test_zielordner_ist_stufe_b():
    """Zielstruktur: Agent/Fotos/<Jahr>/<Thema>/<Geraet>."""
    assert (_sort.ziel_ordner(2025, "Konzerte", "Motorola edge 50")
            == "Agent/Fotos/2025/Konzerte/Motorola edge 50")
    # Leeres Thema wird benannt, nicht gelassen: eine Luecke sieht spaeter aus
    # wie ein Fehler.
    assert _sort.ziel_ordner(2025, "", "") == "Agent/Fotos/2025/unbestimmt/unbekannt"
    # Kein Schraegstrich im Ordnernamen (waere ein ungewollter Unterordner).
    assert "/" not in _sort.ziel_ordner(2025, "Urlaub/Italien", "Geraet").split("/Fotos/")[1].split("/")[0]


def test_doppelungen_werden_einmal_markiert():
    """Genau eine der beiden wird als Doppelung markiert, mit Zeiger auf die andere."""
    zeilen = [
        {"motiv": "a.jpg", "datei": "a.jpg", "ordner": "P:/x", "bytes": 1},
        {"motiv": "a.jpg", "datei": "a (2).jpg", "ordner": "P:/x", "bytes": 1},
    ]
    for zeile in zeilen:
        zeile.setdefault("doppelung", "")
    _sort.doppelungen_markieren(zeilen)
    markiert = [z for z in zeilen if z["doppelung"]]
    assert len(markiert) == 1, "genau ein Eintrag ist die Doppelung"
    assert markiert[0]["doppelung"] != markiert[0]["datei"]
    assert markiert[0]["doppelung"] in ("a.jpg", "a (2).jpg")


def test_doppelung_ueber_ordner_grenzen():
    """Derselbe Name in zwei Quellordnern ist genau eine Doppelung."""
    zeilen = [
        {"motiv": "b.jpg", "datei": "b.jpg", "ordner": "P:/eins", "bytes": 1},
        {"motiv": "b.jpg", "datei": "b.jpg", "ordner": "P:/zwei", "bytes": 1},
    ]
    for zeile in zeilen:
        zeile.setdefault("doppelung", "")
    _sort.doppelungen_markieren(zeilen)
    assert sum(1 for z in zeilen if z["doppelung"]) == 1
