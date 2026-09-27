"""Pruefungen fuer foto_kategorien.py (Nachtlauf-Schritt N6d) — alles OHNE Netz.

Kein pCloud-Aufruf: der Dienst ist eine Attrappe (``FakeService``) mit genau
einer Methode ``liste`` — dieselbe Signatur wie ``PCloudService.liste``. Sie
hat KEIN ``thumb`` und KEIN Schreibverfahren, deshalb faellt jeder solche
Aufruf sofort auf. Alle Dateien gehen nach ``tmp_path``; die echten Ordnernamen
aus ``~/foto_sortierung`` kommen hier nicht vor (erfundene Beispielnamen
"Urlaub", "Kategorie A", "Unterordner 1").

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_foto_kategorien.py -q
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

WERKZEUG = (Path(__file__).resolve().parents[2]
            / "tools" / "foto_sortierung" / "foto_kategorien.py")
KATALOG_WERKZEUG = (Path(__file__).resolve().parents[2]
                    / "tools" / "foto_sortierung" / "themen_katalog.py")
REPO = Path(__file__).resolve().parents[2]


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


kat = _laden(WERKZEUG, "foto_kategorien")
katalog = _laden(KATALOG_WERKZEUG, "themen_katalog")

KATALOG = katalog.THEMEN_KATALOG
KATALOG_THEMA = "Wandern im Schnee"          # echter Katalogeintrag
FREIES_THEMA = "Sonnenuntergang am Meer"     # nicht im Katalog
MOTIV = kat.MOTIV_ZU_BUCKET


# ── Attrappen (kein Netz) ──────────────────────────────────────────────────

def _ordner(name, folderid):
    return {"name": name, "ist_ordner": True, "folderid": folderid, "fileid": None}


def _datei(name, fileid):
    return {"name": name, "ist_ordner": False, "folderid": None, "fileid": fileid}


class Stolperfalle:
    """Ein Schreibversuch, der niemals passieren darf (Trockenlauf)."""

    def __call__(self, *args, **kwargs):
        raise AssertionError("Es wurde geschrieben, obwohl nichts geschrieben darf!")


class FakeService:
    """pCloud-Attrappe: NUR ``liste``, wie der lesende Dienst — kein thumb, kein Schreiben.

    ``baum`` bildet folderid -> Eintraege ab. Jeder Aufruf wird mitgeschrieben,
    damit Tests die Zahl der Lesevorgaenge pruefen koennen.
    """

    def __init__(self, baum=None):
        if baum is None:
            baum = {
                0: [_ordner("Bilder & Videos", 100), _datei("notiz.txt", 9)],
                100: [_ordner("Kategorie A", 110), _ordner("Kategorie B", 120)],
                110: [_ordner("Unterordner 1", 111), _ordner("Unterordner 2", 112),
                      _datei("bild1.jpg", 1), _datei("bild2.jpg", 2),
                      _datei("video1.mp4", 3)],
                120: [_datei("einzel.jpg", 4)],
            }
        self.baum = baum
        self.aufrufe = []

    def liste(self, folderid=0):
        self.aufrufe.append(int(folderid))
        return list(self.baum.get(int(folderid), []))


# ── kleine Helfer ──────────────────────────────────────────────────────────

def _kategorie(name="Kategorie A", folderid=110, unterordner=(), dateien_direkt=0):
    return {"name": name, "folderid": folderid,
            "unterordner": list(unterordner), "dateien_direkt": dateien_direkt}


def _bestand(kategorien, stand="2026-09-27T10:00:00", wurzel="Bilder & Videos"):
    return {"stand": stand, "wurzel": wurzel, "kategorien": list(kategorien)}


def _bestand_schreiben(pfad: Path, kategorien) -> str:
    pfad.write_text(json.dumps(_bestand(kategorien), ensure_ascii=False),
                    encoding="utf-8")
    return str(pfad)


def _zuordnung_schreiben(pfad: Path, werte: dict) -> str:
    """Eine Zuordnungsdatei mit ALLEN Buckets schreiben (fehlende = null)."""
    buckets = {name: werte.get(name) for name in kat.BUCKETS}
    pfad.write_text(json.dumps({"buckets": buckets}, ensure_ascii=False),
                    encoding="utf-8")
    return str(pfad)


def _md5(pfad: Path) -> str:
    return hashlib.md5(pfad.read_bytes()).hexdigest()


# ── Laden und Katalog-Abdeckung ───────────────────────────────────────────

def test_werkzeug_laedt_und_bietet_die_schnittstelle():
    """Das Werkzeug ist per Pfad ladbar und hat die oeffentliche Schnittstelle."""
    for name in ("BUCKETS", "MOTIV_ZU_BUCKET", "bucket_fuer_thema",
                 "kategorien_laden", "zuordnung_laden", "ziel_kategorie",
                 "pfad_saeubern", "ziel_pfad", "bestandsbericht",
                 "bestand_holen", "KategorienFehler", "main"):
        assert hasattr(kat, name), name
    assert kat.KATALOG_VERSION == katalog.KATALOG_VERSION == 3


def test_buckets_enthalten_sonstiges_als_rueckfall():
    """Die Buckets sind generisch, ohne Doppelung — 'Sonstiges' muss dabei sein."""
    assert kat.SONSTIGES in kat.BUCKETS
    assert len(set(kat.BUCKETS)) == len(kat.BUCKETS)
    assert len(kat.BUCKETS) == 11
    for bucket in kat.BUCKETS:
        assert isinstance(bucket, str) and bucket.strip() == bucket and bucket


def test_motiv_zu_bucket_ist_vollstaendig_gegen_den_katalog():
    """Jeder der 53 Katalogeintraege hat GENAU einen Bucket aus BUCKETS."""
    assert len(MOTIV) == 53
    assert set(MOTIV) == set(KATALOG), (
        f"fehlt: {sorted(set(KATALOG) - set(MOTIV))}, "
        f"zuviel: {sorted(set(MOTIV) - set(KATALOG))}")
    schraeg = {e: b for e, b in MOTIV.items() if b not in kat.BUCKETS}
    assert schraeg == {}, f"Bucket ausserhalb BUCKETS: {schraeg}"
    # Und die Suche findet auch wirklich den Katalogeintrag (nicht Sonstiges):
    for eintrag in KATALOG:
        assert kat.bucket_fuer_thema(eintrag) == MOTIV[eintrag], eintrag


def test_motiv_zu_bucket_ohne_doppelte_schreibweise():
    """Kein Katalogeintrag kommt zweimal in anderer Schreibweise vor."""
    normalisiert = [katalog.thema_normalisieren_katalog(e) for e in MOTIV]
    assert len(set(normalisiert)) == len(normalisiert)


# ── bucket_fuer_thema ──────────────────────────────────────────────────────

def test_bucket_fuer_thema_katalogtreffer_und_schreibweise():
    """Ein Katalogeintrag trifft seinen Bucket — Schreibweise und Punkt egal."""
    assert kat.bucket_fuer_thema(KATALOG_THEMA) == MOTIV[KATALOG_THEMA]
    assert kat.bucket_fuer_thema(KATALOG_THEMA.upper()) == MOTIV[KATALOG_THEMA]
    assert kat.bucket_fuer_thema("  " + KATALOG_THEMA.lower() + ". ") == \
        MOTIV[KATALOG_THEMA]
    assert kat.bucket_fuer_thema("Sonstiges") == kat.SONSTIGES


def test_bucket_fuer_thema_unbekannt_ist_sonstiges():
    """Alles ausserhalb des Katalogs faellt auf Sonstiges."""
    assert kat.bucket_fuer_thema(FREIES_THEMA) == kat.SONSTIGES
    assert kat.bucket_fuer_thema("Wintermarkt am See") == kat.SONSTIGES
    assert kat.bucket_fuer_thema("Haus Garten") == kat.SONSTIGES


def test_bucket_fuer_thema_leer_und_krumme_typen_ohne_exception():
    """None, leer, Zahlen, Listen und Objekte: immer Sonstiges, nie ein Fehler."""
    for wert in (None, "", "   ", "...", 0, 7, 3.5, ["Wandern"], {"thema": 1}, b"x"):
        assert kat.bucket_fuer_thema(wert) == kat.SONSTIGES, wert


# ── kategorien_laden ───────────────────────────────────────────────────────

def test_kategorien_laden_guter_fall(tmp_path):
    """Ein gueltiger Bestand kommt geprueft und normalisiert zurueck."""
    pfad = _bestand_schreiben(tmp_path / "kategorien.json", [
        _kategorie("Kategorie A", 110, ["Unterordner 1", "Unterordner 2"], 3),
        _kategorie("Kategorie B", 120, [], 1),
    ])
    bestand = kat.kategorien_laden(pfad)
    assert bestand["wurzel"] == "Bilder & Videos"
    assert bestand["stand"] == "2026-09-27T10:00:00"
    assert [k["name"] for k in bestand["kategorien"]] == \
        ["Kategorie A", "Kategorie B"]
    assert bestand["kategorien"][0]["unterordner"] == \
        ["Unterordner 1", "Unterordner 2"]
    assert bestand["kategorien"][1]["unterordner"] == []
    assert bestand["kategorien"][0]["dateien_direkt"] == 3
    assert bestand["kategorien"][0]["folderid"] == 110


def test_kategorien_laden_akzeptiert_beide_zaehl_schreibweisen(tmp_path):
    """'dateien_direkte' (Auftragstext) und 'dateien_direkt' (Bestand) gehen beide."""
    eintrag = {"name": "Kategorie A", "folderid": 110, "unterordner": [],
               "dateien_direkte": 5}
    pfad = tmp_path / "k.json"
    pfad.write_text(json.dumps({"stand": "s", "wurzel": "w",
                                "kategorien": [eintrag]}), encoding="utf-8")
    assert kat.kategorien_laden(str(pfad))["kategorien"][0]["dateien_direkt"] == 5


def test_kategorien_laden_fehlende_datei_ist_klartextfehler(tmp_path):
    """Eine fehlende Datei wird gemeldet, nicht ueberfahren."""
    with pytest.raises(kat.KategorienFehler) as fehler:
        kat.kategorien_laden(str(tmp_path / "gibtsnicht.json"))
    assert "nicht gefunden" in str(fehler.value)
    assert "gibtsnicht.json" in str(fehler.value)


def test_kategorien_laden_kaputtes_json_ist_klartextfehler(tmp_path):
    """Unlesbares JSON ergibt einen deutschen Klartextfehler."""
    kaputt = tmp_path / "k.json"
    kaputt.write_text('{"kategorien": [', encoding="utf-8")
    with pytest.raises(kat.KategorienFehler) as fehler:
        kat.kategorien_laden(str(kaputt))
    assert "kein lesbares JSON" in str(fehler.value)

    keine_liste = tmp_path / "l.json"
    keine_liste.write_text(json.dumps({"stand": "s", "wurzel": "w",
                                       "kategorien": {}}), encoding="utf-8")
    with pytest.raises(kat.KategorienFehler) as fehler:
        kat.kategorien_laden(str(keine_liste))
    assert "'kategorien' ist keine Liste" in str(fehler.value)


def test_kategorien_laden_fehlendes_pflichtfeld_ist_klartextfehler(tmp_path):
    """Fehlt ein Pflichtfeld, nennt die Meldung Eintrag und Feld."""
    faelle = [
        ({"folderid": 110, "unterordner": [], "dateien_direkt": 0}, "name"),
        ({"name": "Kategorie A", "unterordner": [], "dateien_direkt": 0},
         "folderid"),
        ({"name": "Kategorie A", "folderid": 110, "dateien_direkt": 0},
         "unterordner"),
        ({"name": "Kategorie A", "folderid": 110, "unterordner": []},
         "dateien_direkt"),
    ]
    for eintrag, fehlend in faelle:
        pfad = tmp_path / "k.json"
        pfad.write_text(json.dumps({"stand": "s", "wurzel": "w",
                                    "kategorien": [eintrag]}), encoding="utf-8")
        with pytest.raises(kat.KategorienFehler) as fehler:
            kat.kategorien_laden(str(pfad))
        assert fehlend in str(fehler.value), (fehlend, str(fehler.value))
        assert "Pflichtfeld" in str(fehler.value)


def test_kategorien_laden_ohne_wurzel_ist_fehler(tmp_path):
    """Auch 'wurzel' gehoert zum Schema — fehlt sie, ist das ein Fehler."""
    pfad = tmp_path / "k.json"
    pfad.write_text(json.dumps({"stand": "s", "kategorien": []}), encoding="utf-8")
    with pytest.raises(kat.KategorienFehler) as fehler:
        kat.kategorien_laden(str(pfad))
    assert "'wurzel'" in str(fehler.value)


# ── zuordnung_laden ────────────────────────────────────────────────────────

def _bestand_zwei(tmp_path) -> dict:
    return kat.kategorien_laden(_bestand_schreiben(tmp_path / "kategorien.json", [
        _kategorie("Urlaub", 110, ["Unterordner 1"], 2),
        _kategorie("Kategorie A", 120, [], 0),
    ]))


def test_zuordnung_laden_gueltig_mit_null(tmp_path):
    """Gueltige Zuordnung: jeder Bucket steht drin, null ist erlaubt."""
    bestand = _bestand_zwei(tmp_path)
    pfad = _zuordnung_schreiben(tmp_path / "z.json",
                                {"Urlaub": "Urlaub", "Familie": "Kategorie A"})
    zuordnung = kat.zuordnung_laden(pfad, bestand)
    assert set(zuordnung) == set(kat.BUCKETS)
    assert zuordnung["Urlaub"] == "Urlaub"
    assert zuordnung["Familie"] == "Kategorie A"
    assert zuordnung["Rezepte"] is None
    assert kat.ziel_kategorie("Urlaub", zuordnung) == "Urlaub"
    assert kat.ziel_kategorie("Rezepte", zuordnung) is None
    assert kat.ziel_kategorie("Gibtsnicht", zuordnung) is None


def test_zuordnung_laden_unbekannter_zielname_nennt_bucket_und_namensraum(
        tmp_path):
    """Ein Ordner, den es nicht gibt: Fehler nennt Bucket UND erlaubte Namen."""
    bestand = _bestand_zwei(tmp_path)
    pfad = _zuordnung_schreiben(tmp_path / "z.json",
                                {"Urlaub": "Gibt es nicht"})
    with pytest.raises(kat.KategorienFehler) as fehler:
        kat.zuordnung_laden(pfad, bestand)
    meldung = str(fehler.value)
    assert "Urlaub -> Gibt es nicht" in meldung
    assert "Erlaubter Namensraum" in meldung
    assert "Kategorie A" in meldung            # der erlaubte Name steht drin


def test_zuordnung_laden_fehlender_bucket_ist_fehler(tmp_path):
    """Ein fehlender Bucket ist ein Fehler — die Datei ist die Vorlage."""
    bestand = _bestand_zwei(tmp_path)
    teil = {name: None for name in kat.BUCKETS if name != "Hobbys"}
    pfad = tmp_path / "z.json"
    pfad.write_text(json.dumps({"buckets": teil}, ensure_ascii=False),
                    encoding="utf-8")
    with pytest.raises(kat.KategorienFehler) as fehler:
        kat.zuordnung_laden(str(pfad), bestand)
    assert "Hobbys" in str(fehler.value)
    assert "unvollstaendig" in str(fehler.value)


def test_zuordnung_laden_unbekannter_bucket_ist_fehler(tmp_path):
    """Ein erfundener Bucket-Schluessel wird abgelehnt, mit Namensliste."""
    bestand = _bestand_zwei(tmp_path)
    pfad = _zuordnung_schreiben(tmp_path / "z.json", {})
    daten = json.loads(Path(pfad).read_text(encoding="utf-8"))
    daten["buckets"]["Partys Galore"] = None
    Path(pfad).write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(kat.KategorienFehler) as fehler:
        kat.zuordnung_laden(pfad, bestand)
    assert "Partys Galore" in str(fehler.value)
    assert "Erlaubt sind genau" in str(fehler.value)


def test_zuordnung_laden_fehlende_datei_und_kaputte_datei(tmp_path):
    """Fehlende Datei und fehlendes 'buckets' sind Klartextfehler."""
    bestand = _bestand_zwei(tmp_path)
    with pytest.raises(kat.KategorienFehler) as fehler:
        kat.zuordnung_laden(str(tmp_path / "weg.json"), bestand)
    assert "nicht gefunden" in str(fehler.value)

    ohne = tmp_path / "ohne.json"
    ohne.write_text(json.dumps({"Urlaub": None}), encoding="utf-8")
    with pytest.raises(kat.KategorienFehler) as fehler:
        kat.zuordnung_laden(str(ohne), bestand)
    assert "'buckets'" in str(fehler.value)


# ── pfad_saeubern ──────────────────────────────────────────────────────────

def test_pfad_saeubern_verbotene_zeichen_und_raender():
    """Verbotene Zeichen werden Leerraum, Raender (Leerzeichen/Punkt) fallen weg."""
    assert kat.pfad_saeubern("Urlaub/Strand") == "Urlaub Strand"
    assert kat.pfad_saeubern("Oster\\brunch") == "Oster brunch"
    assert kat.pfad_saeubern('Bad:"Spiegel"|putzen?') == "Bad Spiegel putzen"
    assert kat.pfad_saeubern("  Urlaub  ") == "Urlaub"
    assert kat.pfad_saeubern(".Urlaub.") == "Urlaub"
    assert kat.pfad_saeubern("Urlaub . ") == "Urlaub"
    assert kat.pfad_saeubern("Urlaub    am   See") == "Urlaub am See"
    assert kat.pfad_saeubern("Urlaub\nam\tSee") == "Urlaub am See"
    assert kat.pfad_saeubern("Stern*chen<gross>") == "Stern chen gross"


def test_pfad_saeubern_behaelt_umlaute_und_begrenzt_die_laenge():
    """Umlaute bleiben erhalten; zu lange Namen werden auf 80 Zeichen gekappt."""
    assert kat.pfad_saeubern("Grüße aus München") == "Grüße aus München"
    assert kat.pfad_saeubern("Öl für Öfen") == "Öl für Öfen"
    lang = kat.pfad_saeubern("W" * 200)
    assert len(lang) == kat.PFAD_MAX_ZEICHEN == 80
    # Ein Punkt am Ende darf durch das Kappen nicht entstehen/bleiben:
    assert kat.pfad_saeubern("A" * 79 + " .") == "A" * 79


def test_pfad_saeubern_leerer_rest_wird_ohne_name():
    """Ist nichts Brauchbares uebrig, kommt 'Ohne-Name' — kein leerer Name."""
    for wert in ("", "   ", "...", "///", None, 7, 3.5, ["Urlaub"], b"x"):
        assert kat.pfad_saeubern(wert) == kat.OHNE_NAME == "Ohne-Name", wert


# ── ziel_pfad ──────────────────────────────────────────────────────────────

def test_ziel_pfad_baut_den_baum():
    """Der Zielpfad ist Agent/Fotos/<Jahr>/<Kategorie>/<Event>."""
    assert kat.ziel_pfad(2025, "Urlaub", "Strandtag") == \
        "Agent/Fotos/2025/Urlaub/Strandtag"
    assert kat.ziel_pfad(2024, "Kategorie A", "Event/1") == \
        "Agent/Fotos/2024/Kategorie A/Event 1"
    # Alle Teile laufen durch pfad_saeubern (leere Teile werden zu Ohne-Name):
    assert kat.ziel_pfad(2025, "", "") == "Agent/Fotos/2025/Ohne-Name/Ohne-Name"
    assert kat.ziel_pfad(2025, "Grüße", "Ausflug") == \
        "Agent/Fotos/2025/Grüße/Ausflug"


def test_ziel_pfad_ungueltiges_jahr_ist_valueerror():
    """Jahr: ganze Zahl zwischen 1900 und 2100 — sonst ValueError mit Klartext."""
    for jahr in (0, 1899, 2101, "2025", None, 2025.5, True, [2025]):
        with pytest.raises(ValueError) as fehler:
            kat.ziel_pfad(jahr, "Urlaub", "Event")
        assert "Jahr" in str(fehler.value)
    assert kat.JAHR_MIN == 1900 and kat.JAHR_MAX == 2100
    assert kat.ziel_pfad(1900, "a", "b") == "Agent/Fotos/1900/a/b"
    assert kat.ziel_pfad(2100, "a", "b") == "Agent/Fotos/2100/a/b"


# ── bestandsbericht ────────────────────────────────────────────────────────

def test_bestandsbericht_zaehlt_erfundenen_bestand():
    """Die Zahlen im Bericht stimmen fuer einen erfundenen Bestand."""
    bestand = _bestand([
        _kategorie("Kategorie A", 110, ["Unterordner 1", "Unterordner 2"], 3),
        _kategorie("Kategorie B", 120, [], 1),
        _kategorie("Urlaub", 130, ["Unterordner 3"], 0),
    ])
    zuordnung = {name: None for name in kat.BUCKETS}
    zuordnung["Familie"] = "Kategorie A"
    zuordnung["Urlaub"] = "Gibt es nicht"
    bericht = kat.bestandsbericht(bestand, zuordnung)
    assert bericht == "\n".join([
        "Kategorien: 3",
        "Unterordner: 3",
        "Kategorien mit Unterordnern: 2",
        "Buckets: 11",
        "Buckets gebunden: 1",
        "Buckets ohne Zielordner (null): 9",
        "Buckets ohne Treffer in kategorien.json: 1",
    ])
    # Deterministisch: zweimal derselbe Text.
    assert kat.bestandsbericht(bestand, zuordnung) == bericht


def test_bestandsbericht_leer_und_krumme_eingaben():
    """Kein Bestand: ehrliche Nullen, kein Absturz."""
    bericht = kat.bestandsbericht({}, {})
    assert "Kategorien: 0" in bericht
    assert "Unterordner: 0" in bericht
    assert "Buckets ohne Zielordner (null): 0" in bericht
    assert "Buckets ohne Treffer in kategorien.json: 11" in bericht
    assert kat.bestandsbericht(None, None)


# ── bestand_holen (Attrappen-Service, kein Netz) ──────────────────────────

def test_bestand_holen_zaehlt_unterordner_und_direkte_dateien(tmp_path):
    """Zwei Ebenen lesen: Unterordner und Dateien direkt je Kategorie."""
    dienst = FakeService()
    ziel = tmp_path / "kategorien.json"
    ergebnis = kat.bestand_holen(dienst, str(ziel))

    daten = json.loads(ziel.read_text(encoding="utf-8"))
    assert daten["wurzel"] == "Bilder & Videos"
    assert [k["name"] for k in daten["kategorien"]] == \
        ["Kategorie A", "Kategorie B"]
    assert daten["kategorien"][0]["unterordner"] == \
        ["Unterordner 1", "Unterordner 2"]
    assert daten["kategorien"][0]["dateien_direkt"] == 3
    # Kategorie OHNE Unterordner: leere Liste, nicht None.
    assert daten["kategorien"][1]["unterordner"] == []
    assert daten["kategorien"][1]["dateien_direkt"] == 1
    assert ergebnis["kategorien"] == 2 and ergebnis["unterordner"] == 2
    assert ergebnis["geschrieben"] is True and ergebnis["trocken"] is False
    # Nur gelesen: genau die drei erwarteten Ordnerebenen, kein thumb.
    assert dienst.aufrufe == [0, 100, 110, 120]
    assert not hasattr(dienst, "thumb")
    # Der Bestand enthaelt keinen Tokenwert (nur Klartextzahlen/Namen):
    assert "stand" in daten and isinstance(daten["stand"], str)


def test_bestand_holen_zweiter_lauf_laesst_die_datei_byte_identisch(tmp_path):
    """Idempotent: gleicher Bestand -> Datei bleibt byte-identisch (md5)."""
    dienst = FakeService()
    ziel = tmp_path / "kategorien.json"
    kat.bestand_holen(dienst, str(ziel))
    vorher = _md5(ziel)
    alt_stand = json.loads(ziel.read_text(encoding="utf-8"))["stand"]

    zweiter = kat.bestand_holen(FakeService(), str(ziel))

    assert _md5(ziel) == vorher, "die Datei wurde beim zweiten Lauf geaendert"
    assert zweiter["unveraendert"] is True
    assert zweiter["geschrieben"] is False
    assert json.loads(ziel.read_text(encoding="utf-8"))["stand"] == alt_stand
    # Auch ein dritter Lauf aendert nichts.
    assert kat.bestand_holen(FakeService(), str(ziel))["unveraendert"] is True
    assert _md5(ziel) == vorher


def test_bestand_holen_erkennt_echte_aenderung_und_schreibt(tmp_path):
    """Gegenprobe: anderer Bestand -> die Datei wird neu geschrieben."""
    ziel = tmp_path / "kategorien.json"
    kat.bestand_holen(FakeService(), str(ziel))
    vorher = _md5(ziel)

    geaendert = FakeService({
        0: [_ordner("Bilder & Videos", 100)],
        100: [_ordner("Kategorie A", 110)],
        110: [_ordner("Unterordner 1", 111)],
    })
    ergebnis = kat.bestand_holen(geaendert, str(ziel))

    assert ergebnis["geschrieben"] is True and ergebnis["unveraendert"] is False
    assert _md5(ziel) != vorher
    daten = json.loads(ziel.read_text(encoding="utf-8"))
    assert len(daten["kategorien"]) == 1
    assert daten["kategorien"][0]["dateien_direkt"] == 0


def test_bestand_holen_trockenlauf_schreibt_nichts(tmp_path, monkeypatch):
    """--trocken: kein Schreiben — ein Schreibversuch muss auffallen."""
    monkeypatch.setattr(kat, "_schreibe_atomar", Stolperfalle())
    ziel = tmp_path / "kategorien.json"
    ergebnis = kat.bestand_holen(FakeService(), str(ziel), trocken=True)

    assert ergebnis["trocken"] is True
    assert ergebnis["geschrieben"] is False
    assert not ziel.exists(), "es wurde trotz Trockenlauf geschrieben"
    assert not (tmp_path / "kategorien.json.tmp").exists()


def test_bestand_holen_ohne_wurzelordner_ist_klartextfehler(tmp_path):
    """Fehlt der Wurzelordner, gibt es eine deutsche Meldung statt eines Absturzes."""
    dienst = FakeService({0: [_ordner("Anderer Ordner", 100)]})
    with pytest.raises(kat.KategorienFehler) as fehler:
        kat.bestand_holen(dienst, str(tmp_path / "k.json"))
    assert "Bilder & Videos" in str(fehler.value)
    assert "nicht gefunden" in str(fehler.value)
    assert not (tmp_path / "k.json").exists()


def test_bestand_holen_verweigert_das_repo(tmp_path, capsys):
    """Ein Ziel IM Repo wird abgelehnt — es wird nichts angelegt."""
    ziel = WERKZEUG.parent / "tmp-kategorien.json"
    assert not ziel.exists()
    with pytest.raises(SystemExit) as abbruch:
        kat.bestand_holen(FakeService(), str(ziel))
    assert abbruch.value.code == 2
    meldung = capsys.readouterr().out
    assert "IM Repo" in meldung and "NICHTS geschrieben" in meldung
    assert not ziel.exists(), "im Repo wurde trotz Abbruch etwas angelegt"


def test_repo_schutz_erkennt_schreibweise_und_striche(tmp_path, capsys):
    """Vertauschte Trenner/Gross-Klein werden trotzdem als Repo erkannt."""
    verdreht = str(REPO).upper() + "\\tools/foto_sortierung\\TMP.json"
    with pytest.raises(SystemExit) as abbruch:
        kat._pruefe_ziel_ausserhalb_repo(verdreht)
    assert abbruch.value.code == 2
    assert "IM Repo" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        kat._pruefe_ziel_ausserhalb_repo(str(REPO))
    capsys.readouterr()
    # Ausserhalb (tmp_path und der Vorgabepfad) geht unveraendert durch:
    assert kat._pruefe_ziel_ausserhalb_repo(str(tmp_path / "k.json")) == \
        str(tmp_path / "k.json")
    assert kat.STANDARD_KATEGORIEN == kat._pruefe_ziel_ausserhalb_repo(
        kat.STANDARD_KATEGORIEN)
    assert not str(kat.STANDARD_KATEGORIEN).startswith(str(REPO))
    assert not str(kat.STANDARD_ZUORDNUNG).startswith(str(REPO))


# ── Kommandozeile (ohne Netz) ─────────────────────────────────────────────

def test_cli_zeigen_zeigt_bericht_ohne_zu_schreiben(tmp_path, capsys,
                                                    monkeypatch):
    """--zeigen liest Bestand und Zuordnung und schreibt NICHTS."""
    monkeypatch.setattr(kat, "_schreibe_atomar", Stolperfalle())
    kat_pfad = _bestand_schreiben(tmp_path / "kategorien.json", [
        _kategorie("Urlaub", 110, ["Unterordner 1"], 2)])
    zu_pfad = _zuordnung_schreiben(tmp_path / "z.json", {"Urlaub": "Urlaub"})
    vorher = _md5(Path(kat_pfad))

    code = kat.main(["--zeigen", "--kategorien-pfad", kat_pfad,
                     "--zuordnung-pfad", zu_pfad], service=Stolperfalle())

    ausgabe = capsys.readouterr().out
    assert code == 0
    assert "Kategorien: 1" in ausgabe
    assert "Unterordner: 1" in ausgabe
    assert "Buckets gebunden: 1" in ausgabe
    assert "Urlaub" in ausgabe and "KEIN Ordner" in ausgabe
    assert "Es wurde nichts geschrieben." in ausgabe
    assert _md5(Path(kat_pfad)) == vorher


def test_cli_ohne_schreiben_schreibt_nichts(tmp_path, capsys):
    """--bestand-holen ohne --schreiben ist ein Trockenlauf (kein Dienst noetig)."""
    kat_pfad = tmp_path / "kategorien.json"
    code = kat.main(["--bestand-holen", "--kategorien-pfad", str(kat_pfad)],
                    service=FakeService())
    ausgabe = capsys.readouterr().out
    assert code == 0
    assert "Trockenlauf" in ausgabe
    assert "NICHTS geschrieben" in ausgabe
    assert "geschrieben: nein" in ausgabe
    assert not kat_pfad.exists()


def test_cli_mit_schreiben_legt_den_bestand_an(tmp_path, capsys):
    """--bestand-holen --schreiben schreibt den Bestand (Attrappen-Dienst)."""
    kat_pfad = tmp_path / "kategorien.json"
    code = kat.main(["--bestand-holen", "--schreiben",
                     "--kategorien-pfad", str(kat_pfad)], service=FakeService())
    ausgabe = capsys.readouterr().out
    assert code == 0
    assert "geschrieben: ja" in ausgabe
    daten = json.loads(kat_pfad.read_text(encoding="utf-8"))
    assert len(daten["kategorien"]) == 2
    # Zweiter Lauf meldet 'unveraendert' und laesst die Datei in Ruhe.
    vorher = _md5(kat_pfad)
    code = kat.main(["--bestand-holen", "--schreiben",
                     "--kategorien-pfad", str(kat_pfad)], service=FakeService())
    assert code == 0
    assert "unveraendert" in capsys.readouterr().out
    assert _md5(kat_pfad) == vorher


def test_cli_fehlende_dateien_exit_2(tmp_path, capsys):
    """Fehlende Bestands-/Zuordnungsdatei: klare Meldung, Exit 2."""
    code = kat.main(["--zeigen", "--kategorien-pfad", str(tmp_path / "weg.json"),
                     "--zuordnung-pfad", str(tmp_path / "z.json")])
    assert code == 2
    assert "nicht gefunden" in capsys.readouterr().out

    kat_pfad = _bestand_schreiben(tmp_path / "k.json", [_kategorie()])
    code = kat.main(["--zeigen", "--kategorien-pfad", kat_pfad,
                     "--zuordnung-pfad", str(tmp_path / "z-weg.json")])
    assert code == 2
    assert "nicht gefunden" in capsys.readouterr().out


# ── Hygiene: keine Loeschbefehle, nichts im Repo ──────────────────────────

def test_quelle_enthaelt_keine_loeschbefehle():
    """Der Quelltext darf weder deletefile noch deletefolder enthalten."""
    quelle = WERKZEUG.read_text(encoding="utf-8")
    for verboten in ("deletefile", "deletefolder", "delete_file",
                     "delete_folder", "shutil.rmtree", "unlink("):
        assert verboten not in quelle, verboten


def test_bestand_holen_legt_nichts_im_repo_an(tmp_path):
    """Ein Lauf schreibt nur nach dem uebergebenen Pfad — nie ins Repo."""
    werkzeug_ordner = WERKZEUG.parent
    vorher = {str(d): _md5(d) for d in sorted(werkzeug_ordner.rglob("*"))
              if d.is_file()}
    kat.bestand_holen(FakeService(), str(tmp_path / "kategorien.json"))
    nachher = {str(d): _md5(d) for d in sorted(werkzeug_ordner.rglob("*"))
               if d.is_file()}
    assert nachher == vorher
    assert (tmp_path / "kategorien.json").is_file()
