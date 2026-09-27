"""Pruefungen fuer ``foto_sortieren.py`` (Nachtlauf-Schritt N7, TROCKENLAUF).

Alles OHNE Netz: der pCloud-Dienst ist, wo er ueberhaupt gebraucht wird, eine
Attrappe mit genau einer Methode (``liste``). Dateien gehen nach ``tmp_path``.

**Nur erfundene Beispielnamen** — Sebastians echte Ordnernamen liegen bewusst
ausserhalb des Repos und kommen hier nicht vor: ``BeispielKategorie``,
``Beispiel-Event``, ``Beispiel-Geraet``, ``Beispiel-Cloud``, ``Beispielplatz``.
Das Motiv-Thema ist ein Katalogeintrag (generisch, kein Bestandsname).

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_foto_sortieren.py -q
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "foto_sortieren.py"
KATEGORIEN_WERKZEUG = REPO / "tools" / "foto_sortierung" / "foto_kategorien.py"
EVENT_WERKZEUG = REPO / "tools" / "foto_sortierung" / "event_abgleich.py"


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


fs = _laden(WERKZEUG, "foto_sortieren")
kat = _laden(KATEGORIEN_WERKZEUG, "foto_kategorien")
ev = _laden(EVENT_WERKZEUG, "event_abgleich")

# Erfundene Beispielnamen. Das Thema ist ein echter Katalogeintrag, damit die
# Kette Thema -> Bucket -> Kategorie pruefbar ist.
THEMA = "Konzert und Buehne"
BUCKET = "Konzerte und Partys"
THEMA_KUCHEN = "Kuchen und Gebaeck"
BUCKET_KUCHEN = "Rezepte"
KATEGORIE = "BeispielKategorie"
KATEGORIE_ZWEI = "BeispielKategorie-Zwei"
KATEGORIE_SONSTIGES = "Beispiel-Sonstiges"
ORDNER_A = "P:/Beispiel-Cloud/Beispiel-Geraet/DCIM/Camera"
ORDNER_B = "P:/Beispiel-Cloud/Beispiel-Zweitgeraet/DCIM/Camera"
EVENT_NAME = "2019-11-25 Beispiel-Event"
ANLASS_A = "2019-11-25_Anlass-01"
ANLASS_B = "2019-11-25_Anlass-02"


# ── Attrappen (kein Netz) ──────────────────────────────────────────────────

def _ordner(name, folderid):
    return {"name": name, "ist_ordner": True, "folderid": folderid, "fileid": None}


def _datei(name, fileid):
    return {"name": name, "ist_ordner": False, "folderid": None, "fileid": fileid}


class FakeService:
    """pCloud-Attrappe: NUR ``liste``, wie der lesende Dienst — nichts anderes."""

    def __init__(self, baum=None):
        if baum is None:
            baum = {
                0: [_ordner("Beispiel-Cloud", 10)],
                10: [_ordner("Beispiel-Geraet", 11)],
                11: [_ordner("DCIM", 12)],
                12: [_ordner("Camera", 13)],
                13: [_datei("bild1.jpg", 4242), _datei("video1.mp4", 4243)],
            }
        self.baum = baum
        self.aufrufe = []

    def liste(self, folderid=0):
        self.aufrufe.append(int(folderid))
        return list(self.baum.get(int(folderid), []))


class Schreiber:
    """Ein Aufruf, der niemals passieren darf (es wird nichts geschrieben)."""

    def __call__(self, *args, **kwargs):
        raise AssertionError("Es wurde geschrieben, obwohl nichts geschrieben darf!")


# ── kleine Helfer ──────────────────────────────────────────────────────────

def _zeile(anlass_id=ANLASS_A, datei="bild1.jpg", ordner=ORDNER_A, thema=THEMA,
           jahr="2019", monat="11", tag="25", doppelung="", **rest):
    zeile = {"jahr": jahr, "monat": monat, "tag": tag,
             "datumquelle": "dateiname", "thema": thema,
             "geraet": "Beispiel-Geraet", "ordner": ordner, "datei": datei,
             "motiv": "Beispiel-Motiv", "doppelung": doppelung,
             "bytes": "1234", "mb": "0.001", "thema_quelle": anlass_id}
    zeile.update(rest)
    return zeile


def _zeilen(*zeilen):
    return list(zeilen)


def _csv_schreiben(pfad: Path, zeilen) -> str:
    with open(pfad, "w", encoding="utf-8", newline="") as datei:
        schreiber = csv.DictWriter(datei, fieldnames=list(fs.SPALTEN),
                                   extrasaction="ignore")
        schreiber.writeheader()
        for zeile in zeilen:
            schreiber.writerow(zeile)
    return str(pfad)


def _anlass(anlass_id=ANLASS_A, thema=THEMA, jahr=2019, dateien=("bild1.jpg",),
            **rest):
    anlass = {"id": anlass_id, "titel": anlass_id, "jahr": jahr, "monat": None,
              "tag": None, "thema": thema,
              "dateien": [{"von_ordner": ORDNER_A, "von_name": name}
                          for name in dateien]}
    anlass.update(rest)
    return anlass


def _kategorie(name=KATEGORIE, folderid=110, unterordner=(), dateien_direkt=0):
    return {"name": name, "folderid": folderid,
            "unterordner": list(unterordner), "dateien_direkt": dateien_direkt}


def _bestand(kategorien=None) -> dict:
    return {"stand": "2026-09-27T10:00:00", "wurzel": "Beispiel-Wurzel",
            "kategorien": list(kategorien if kategorien is not None
                               else [_kategorie()])}


def _zuordnung(werte=None) -> dict:
    """Bucket-Bindung mit ALLEN Buckets (nicht genannte bleiben ``null``)."""
    werte = werte or {}
    return {name: werte.get(name) for name in kat.BUCKETS}


def _umgebung(tmp_path: Path, zeilen, kategorien=None, werte=None) -> dict:
    """CSV, Bestand und Zuordnung als Dateien anlegen (alles unter tmp_path)."""
    csv_pfad = tmp_path / "sortierschluessel.csv"
    _csv_schreiben(csv_pfad, zeilen)
    bestand_pfad = tmp_path / "kategorien.json"
    bestand_pfad.write_text(
        json.dumps(_bestand(kategorien), ensure_ascii=False), encoding="utf-8")
    zuordnung_pfad = tmp_path / "kategorie_zuordnung.json"
    zuordnung_pfad.write_text(
        json.dumps({"buckets": _zuordnung(werte)}, ensure_ascii=False),
        encoding="utf-8")
    return {"csv": csv_pfad, "bestand": bestand_pfad,
            "zuordnung": zuordnung_pfad, "plan": tmp_path / "sortierplan.json"}


def _lauf(umgebung: dict, zusatz=()):
    return fs.main(["--csv", str(umgebung["csv"]),
                    "--kategorien-pfad", str(umgebung["bestand"]),
                    "--zuordnung-pfad", str(umgebung["zuordnung"]),
                    "--plan", str(umgebung["plan"]), "--ohne-ids", *zusatz])


def _plan(zeilen, bestand=None, zuordnung=None, **rest) -> dict:
    return fs.plan_bauen(zeilen, bestand if bestand is not None else _bestand(),
                         zuordnung if zuordnung is not None
                         else _zuordnung({BUCKET: KATEGORIE}), **rest)


def _datei_hash(pfad: Path) -> str:
    return hashlib.md5(pfad.read_bytes()).hexdigest()


# ── CSV lesen ──────────────────────────────────────────────────────────────

def test_zeilen_lesen_gibt_alle_zeilen(tmp_path):
    pfad = _csv_schreiben(tmp_path / "s.csv", [_zeile(), _zeile(datei="bild2.jpg")])
    zeilen = fs.zeilen_lesen(pfad)
    assert len(zeilen) == 2
    assert zeilen[0]["thema_quelle"] == ANLASS_A
    assert zeilen[0]["datei"] == "bild1.jpg"
    assert zeilen[1]["datei"] == "bild2.jpg"


def test_zeilen_lesen_fehlende_datei_ist_klartextfehler(tmp_path):
    with pytest.raises(fs.SortierFehler) as fehler:
        fs.zeilen_lesen(str(tmp_path / "gibtsnicht.csv"))
    assert "nicht gefunden" in str(fehler.value)


def test_zeilen_lesen_ohne_pfad_ist_klartextfehler():
    with pytest.raises(fs.SortierFehler):
        fs.zeilen_lesen("")


def test_zeilen_lesen_pflichtspalte_fehlt(tmp_path):
    pfad = tmp_path / "krumm.csv"
    pfad.write_text("thema,datei\nBeispiel,bild1.jpg\n", encoding="utf-8")
    with pytest.raises(fs.SortierFehler) as fehler:
        fs.zeilen_lesen(str(pfad))
    assert "thema_quelle" in str(fehler.value)


def test_zeilen_lesen_vertraegt_bom_im_kopf(tmp_path):
    pfad = tmp_path / "bom.csv"
    _csv_schreiben(pfad, [_zeile()])
    pfad.write_text("\ufeff" + pfad.read_text(encoding="utf-8"), encoding="utf-8")
    zeilen = fs.zeilen_lesen(str(pfad))
    assert len(zeilen) == 1
    assert zeilen[0]["ordner"] == ORDNER_A


# ── Buendeln (Regeln 1 und 2) ──────────────────────────────────────────────

def test_buendeln_ein_anlass_je_id():
    ergebnis = fs.anlaesse_buendeln([_zeile(), _zeile(datei="bild2.jpg")])
    assert len(ergebnis["anlaesse"]) == 1
    assert len(ergebnis["anlaesse"][0]["dateien"]) == 2


def test_buendeln_behaelt_csv_reihenfolge():
    ergebnis = fs.anlaesse_buendeln([
        _zeile(anlass_id=ANLASS_B, datei="spaeter.jpg"),
        _zeile(anlass_id=ANLASS_A, datei="frueher.jpg")])
    assert [a["id"] for a in ergebnis["anlaesse"]] == [ANLASS_B, ANLASS_A]


def test_buendeln_dateien_in_csv_reihenfolge():
    ergebnis = fs.anlaesse_buendeln([
        _zeile(datei="c.jpg"), _zeile(datei="a.jpg"), _zeile(datei="b.jpg")])
    assert [d["von_name"] for d in ergebnis["anlaesse"][0]["dateien"]] == \
        ["c.jpg", "a.jpg", "b.jpg"]


def test_buendeln_ohne_thema_quelle_wird_gezaehlt():
    ergebnis = fs.anlaesse_buendeln([_zeile(), _zeile(thema_quelle="")])
    assert ergebnis["ohne_thema_quelle"] == 1
    assert len(ergebnis["anlaesse"]) == 1


def test_buendeln_doppelung_wird_gezaehlt():
    ergebnis = fs.anlaesse_buendeln([_zeile(), _zeile(doppelung="IMG_2025 (2)")])
    assert ergebnis["doppelung_uebersprungen"] == 1


def test_buendeln_doppelung_landet_nicht_im_anlass():
    ergebnis = fs.anlaesse_buendeln([_zeile(), _zeile(datei="kopie.jpg",
                                                     doppelung="doppelt")])
    namen = [d["von_name"] for d in ergebnis["anlaesse"][0]["dateien"]]
    assert namen == ["bild1.jpg"]


def test_buendeln_gleiche_id_zweimal_ist_ein_anlass():
    ergebnis = fs.anlaesse_buendeln([_zeile(datei="a.jpg"), _zeile(datei="b.jpg")])
    assert len(ergebnis["anlaesse"]) == 1


def test_buendeln_thema_kommt_aus_der_zeile():
    ergebnis = fs.anlaesse_buendeln([_zeile(thema="")])
    assert ergebnis["anlaesse"][0]["thema"] == ""


def test_buendeln_thema_aus_zweiter_zeile():
    ergebnis = fs.anlaesse_buendeln([_zeile(thema="", datei="a.jpg"),
                                     _zeile(thema=THEMA, datei="b.jpg")])
    assert ergebnis["anlaesse"][0]["thema"] == THEMA


def test_buendeln_jahr_als_zahl_aus_der_csv():
    ergebnis = fs.anlaesse_buendeln([_zeile(jahr="2019")])
    assert ergebnis["anlaesse"][0]["jahr"] == 2019


def test_buendeln_ohne_zeilen_ist_leer():
    ergebnis = fs.anlaesse_buendeln([])
    assert ergebnis["anlaesse"] == []
    assert ergebnis["ohne_thema_quelle"] == 0


def test_quellordner_auflisten_in_reihenfolge():
    ordner = fs.quellordner_auflisten([_zeile(ordner=ORDNER_B),
                                       _zeile(ordner=ORDNER_A, datei="x.jpg"),
                                       _zeile(ordner=ORDNER_B, datei="y.jpg")])
    assert ordner == [ORDNER_B, ORDNER_A]


# ── Jahr (Regel 6) ─────────────────────────────────────────────────────────

def test_anlass_jahr_aus_dem_feld():
    assert fs.anlass_jahr(_anlass(jahr=2019)) == 2019


def test_anlass_jahr_aus_dem_datum_wenn_feld_leer():
    assert fs.anlass_jahr(_anlass(jahr=None)) == 2019


def test_anlass_jahr_ohne_angabe_ist_none():
    assert fs.anlass_jahr(_anlass(anlass_id="Anlass-07", jahr=None)) is None


def test_anlass_jahr_unbrauchbar_ist_none():
    assert fs.anlass_jahr(_anlass(anlass_id="Anlass-07", jahr="keine Zahl")) is None


def test_anlass_jahr_ausserhalb_des_bereichs_ist_none():
    assert fs.anlass_jahr(_anlass(anlass_id="Anlass-07", jahr=1500)) is None


def test_plan_zaehlt_anlaesse_ohne_jahr():
    plan = _plan([_zeile(anlass_id="Anlass-07", jahr="")])
    assert plan["zusammenfassung"]["ohne_jahr"] == 1
    assert plan["zusammenfassung"]["anlaesse"] == 0
    assert plan["zuege"] == []


def test_anlass_ohne_jahr_taucht_nicht_im_plan_auf():
    plan = _plan([_zeile(anlass_id="Anlass-07", jahr="")])
    assert plan["anlaesse"] == []


# ── Zielkategorie (Regel 3) ────────────────────────────────────────────────

def test_kategorie_aus_thema_ueber_bucket():
    kategorie, neu = fs.ziel_kategorie_und_neu(
        _anlass(), _bestand([_kategorie()]), _zuordnung({BUCKET: KATEGORIE}))
    assert kategorie == KATEGORIE
    assert neu is False


def test_kategorie_fehlt_im_bestand_faellt_auf_sonstiges():
    kategorie, neu = fs.ziel_kategorie_und_neu(
        _anlass(), _bestand([_kategorie(KATEGORIE_ZWEI)]),
        _zuordnung({BUCKET: KATEGORIE}))
    assert kategorie == kat.SONSTIGES
    assert neu is True


def test_sonstiges_ungebunden_bleibt_literal_sonstiges():
    kategorie, neu = fs.ziel_kategorie_und_neu(
        _anlass(), _bestand([_kategorie(KATEGORIE_ZWEI)]),
        _zuordnung({BUCKET: KATEGORIE}))
    assert kategorie == kat.SONSTIGES
    assert neu is True


def test_sonstiges_gebunden_und_im_bestand_ist_nicht_neu():
    kategorie, neu = fs.ziel_kategorie_und_neu(
        _anlass(), _bestand([_kategorie(KATEGORIE_SONSTIGES)]),
        _zuordnung({BUCKET: KATEGORIE, kat.SONSTIGES: KATEGORIE_SONSTIGES}))
    assert kategorie == KATEGORIE_SONSTIGES
    assert neu is False


def test_kategorie_ohne_thema_geht_auf_sonstiges():
    kategorie, neu = fs.ziel_kategorie_und_neu(
        _anlass(thema=""), _bestand(), _zuordnung({BUCKET: KATEGORIE}))
    assert kategorie == kat.SONSTIGES
    assert neu is True


def test_plan_plant_unbekannte_kategorie_als_neuen_ordner():
    # Die Kategorie des Themas ("BeispielKategorie") fehlt im Bestand -> der
    # Rueckfall "Sonstiges" wird geplant, und sein Ordner ist neu.
    plan = _plan([_zeile()], bestand=_bestand([_kategorie(KATEGORIE_ZWEI)]))
    assert plan["anlaesse"][0]["kategorie"] == kat.SONSTIGES
    assert plan["anlaesse"][0]["kategorie_neu"] is True
    pfade = [eintrag["pfad"] for eintrag in plan["ordner"]]
    assert f"Agent/Fotos/2019/{kat.SONSTIGES}" in pfade
    assert plan["zusammenfassung"]["ordner_neu"] == 5
    assert plan["zusammenfassung"]["ordner_vorhanden"] == 0


# ── Event-Wahl (Regeln 4 und 5) ────────────────────────────────────────────

def test_event_ohne_thema_ist_der_rueckfall():
    assert fs.event_basisname(_anlass(thema="")) == ev.OHNE_THEMA


def test_event_name_aus_datum_und_thema():
    name = fs.event_basisname(_anlass())
    assert name.startswith("2019-11-25")
    assert "Konzert" in name


def test_event_name_bleibt_ordner_sicher():
    name = fs.event_basisname(_anlass(thema='Konzert: "Buehne"/2020?'))
    assert not re.search(r'[/\\:*?"<>|]', name)


def test_event_vorschlag_sicher_wird_wiederverwendet():
    bestand = _bestand([_kategorie(unterordner=["2019-11-25 Beispiel-Event"])])
    wahl = fs.event_waehlen(_anlass(), KATEGORIE, bestand)
    assert wahl["event"] == "2019-11-25 Beispiel-Event"
    assert wahl["event_quelle"] == "vorschlag"
    assert wahl["event_stufe"] == "tag"


def test_event_vorschlag_schwach_wird_nicht_verwendet():
    bestand = _bestand([_kategorie(unterordner=["2019 Beispiel-Jahr"])])
    wahl = fs.event_waehlen(_anlass(), KATEGORIE, bestand)
    assert wahl["event_quelle"] == "neu"
    assert wahl["event"] != "2019 Beispiel-Jahr"


def test_event_vorschlag_jahr_stufe_ist_nicht_sicher():
    vorschlag = ev.vorschlag_fuer(_anlass(), ["2019 Beispiel-Jahr"])
    assert vorschlag is None


def test_event_ohne_bestand_ist_neu():
    wahl = fs.event_waehlen(_anlass(), KATEGORIE, _bestand())
    assert wahl["event_quelle"] == "neu"
    assert wahl["event_stufe"] is None


def test_event_ohne_thema_ausser_vorschlag_ist_rueckfall():
    wahl = fs.event_waehlen(_anlass(thema=""), KATEGORIE, _bestand())
    assert wahl["event"] == ev.OHNE_THEMA
    assert wahl["event_quelle"] == "neu"


def test_plan_zaehlt_anlaesse_ohne_thema():
    plan = _plan([_zeile(thema="")])
    assert plan["zusammenfassung"]["ohne_thema"] == 1


def test_plan_zaehlt_wiederverwendete_events():
    bestand = _bestand([_kategorie(unterordner=["2019-11-25 Beispiel-Event"])])
    plan = _plan([_zeile()], bestand=bestand)
    assert plan["zusammenfassung"]["events_wiederverwendet"] == 1
    assert plan["zusammenfassung"]["events_neu"] == 0


# ── Kollision (Regel 5) ────────────────────────────────────────────────────

def test_kollision_zweiter_anlass_bekommt_zusatz():
    ziele = [
        {"id": "2022-09-05_Anlass-01", "jahr": 2022, "kategorie": KATEGORIE,
         "event": "2022-09-05 Beispiel-Event", "event_quelle": "neu"},
        {"id": "2022-09-05_Anlass-02", "jahr": 2022, "kategorie": KATEGORIE,
         "event": "2022-09-05 Beispiel-Event", "event_quelle": "neu"},
    ]
    fs.kollisionen_aufloesen(ziele)
    assert ziele[0]["event"] == "2022-09-05 Beispiel-Event"
    assert ziele[1]["event"] == "2022-09-05 Beispiel-Event (02)"


def test_kollision_ordnet_nach_anlass_id():
    ziele = [
        {"id": "2022-09-05_Anlass-05", "jahr": 2022, "kategorie": KATEGORIE,
         "event": "Gleicher Name", "event_quelle": "neu"},
        {"id": "2022-09-05_Anlass-02", "jahr": 2022, "kategorie": KATEGORIE,
         "event": "Gleicher Name", "event_quelle": "neu"},
    ]
    fs.kollisionen_aufloesen(ziele)
    assert ziele[0]["event"] == "Gleicher Name (05)"
    assert ziele[1]["event"] == "Gleicher Name"


def test_kollision_nur_im_gleichen_jahr():
    ziele = [
        {"id": "2021-01-01_Anlass-01", "jahr": 2021, "kategorie": KATEGORIE,
         "event": "Gleicher Name", "event_quelle": "neu"},
        {"id": "2022-01-01_Anlass-01", "jahr": 2022, "kategorie": KATEGORIE,
         "event": "Gleicher Name", "event_quelle": "neu"},
    ]
    fs.kollisionen_aufloesen(ziele)
    assert [ziel["event"] for ziel in ziele] == ["Gleicher Name", "Gleicher Name"]


def test_kollision_nur_in_der_gleichen_kategorie():
    ziele = [
        {"id": "2022-01-01_Anlass-01", "jahr": 2022, "kategorie": KATEGORIE,
         "event": "Gleicher Name", "event_quelle": "neu"},
        {"id": "2022-01-01_Anlass-02", "jahr": 2022, "kategorie": KATEGORIE_ZWEI,
         "event": "Gleicher Name", "event_quelle": "neu"},
    ]
    fs.kollisionen_aufloesen(ziele)
    assert [ziel["event"] for ziel in ziele] == ["Gleicher Name", "Gleicher Name"]


def test_kollision_trifft_wiederverwendete_vorschlaege_nicht():
    ziele = [
        {"id": "2022-01-01_Anlass-01", "jahr": 2022, "kategorie": KATEGORIE,
         "event": "Bestehender Ordner", "event_quelle": "vorschlag"},
        {"id": "2022-01-01_Anlass-02", "jahr": 2022, "kategorie": KATEGORIE,
         "event": "Bestehender Ordner", "event_quelle": "vorschlag"},
    ]
    fs.kollisionen_aufloesen(ziele)
    assert [ziel["event"] for ziel in ziele] == ["Bestehender Ordner",
                                                 "Bestehender Ordner"]
    assert not any(ziel.get("kollision") for ziel in ziele)


def test_anlass_zusatz_liest_die_letzten_ziffern():
    assert fs.anlass_zusatz("2022-09-05_Anlass-02") == "02"
    assert fs.anlass_zusatz("Anlass-123") == "123"


def test_anlass_zusatz_ohne_ziffern_ist_leer():
    assert fs.anlass_zusatz("Beispiel-Anlass") == ""


def test_kollision_ohne_ziffern_nutzt_laufende_nummer():
    ziele = [
        {"id": "Beispiel-A", "jahr": 2022, "kategorie": KATEGORIE,
         "event": "Gleicher Name", "event_quelle": "neu"},
        {"id": "Beispiel-B", "jahr": 2022, "kategorie": KATEGORIE,
         "event": "Gleicher Name", "event_quelle": "neu"},
    ]
    fs.kollisionen_aufloesen(ziele)
    assert ziele[1]["event"] == "Gleicher Name (02)"


def test_plan_macht_kollisionen_eindeutig():
    zeilen = [_zeile(anlass_id="2022-09-05_Anlass-01"),
              _zeile(anlass_id="2022-09-05_Anlass-02")]
    plan = _plan(zeilen)
    namen = [anlass["event"] for anlass in plan["anlaesse"]]
    assert len(set(namen)) == len(namen) == 2


# ── Ordnerkette (Regel 7) ──────────────────────────────────────────────────

def test_ordnerkette_hat_fuenf_teile_in_reihenfolge():
    kette = fs.ordnerkette(2019, KATEGORIE, EVENT_NAME, _bestand())
    assert [teil["pfad"] for teil in kette] == [
        "Agent", "Agent/Fotos", "Agent/Fotos/2019",
        f"Agent/Fotos/2019/{KATEGORIE}", f"Agent/Fotos/2019/{KATEGORIE}/{EVENT_NAME}"]


def test_ordnerkette_ebenen_sind_benannt():
    kette = fs.ordnerkette(2019, KATEGORIE, EVENT_NAME, _bestand())
    assert [teil["ebene"] for teil in kette] == [
        "basis", "basis", "jahr", "kategorie", "event"]


def test_ordnerkette_endet_auf_dem_zielpfad():
    kette = fs.ordnerkette(2019, KATEGORIE, EVENT_NAME, _bestand())
    assert kette[-1]["pfad"] == kat.ziel_pfad(2019, KATEGORIE, EVENT_NAME)


def test_ordnerkette_kennt_eltern_pfade():
    kette = fs.ordnerkette(2019, KATEGORIE, EVENT_NAME, _bestand())
    assert kette[0]["eltern"] == ""
    assert kette[1]["eltern"] == "Agent"
    assert kette[2]["eltern"] == "Agent/Fotos"


def test_ordnerkette_neue_kategorie_ist_neu():
    kette = fs.ordnerkette(2019, KATEGORIE, EVENT_NAME,
                           _bestand([_kategorie(KATEGORIE_ZWEI)]))
    assert kette[3]["art"] == "neu"
    assert kette[4]["art"] == "neu"


def test_ordnerkette_vorhandener_event_ist_vorhanden():
    bestand = _bestand([_kategorie(unterordner=[EVENT_NAME])])
    kette = fs.ordnerkette(2019, KATEGORIE, EVENT_NAME, bestand)
    assert kette[3]["art"] == "vorhanden"
    assert kette[4]["art"] == "vorhanden"


def test_ordnerkette_findet_event_ohne_gross_klein():
    bestand = _bestand([_kategorie(unterordner=[EVENT_NAME.upper()])])
    kette = fs.ordnerkette(2019, KATEGORIE, EVENT_NAME, bestand)
    assert kette[4]["art"] == "vorhanden"


def test_ordnerkette_basis_hat_wurzel_kennung():
    kette = fs.ordnerkette(2019, KATEGORIE, EVENT_NAME, _bestand())
    assert kette[0]["eltern_id"] == fs.PCLOUD_WURZEL_ID
    assert kette[0]["createfolder"]["art"] == "createfolder"
    assert kette[0]["createfolder"]["nach_folderid"] == fs.PCLOUD_WURZEL_ID
    assert kette[0]["createfolder"]["trocken"] is True


def test_ordnerkette_ohne_kennung_keine_erfundene_vorbuchung():
    kette = fs.ordnerkette(2019, KATEGORIE, EVENT_NAME, _bestand())
    assert kette[1]["createfolder"] is None
    assert "hinweis" in kette[1]


def test_ordnerkette_nutzt_ziel_ids_fuer_eltern():
    bestand = _bestand([_kategorie(unterordner=[EVENT_NAME])])
    ziel_ids = {"Agent/Fotos": 555, "Agent/Fotos/2019": 556,
                f"Agent/Fotos/2019/{KATEGORIE}": 557}
    kette = fs.ordnerkette(2019, KATEGORIE, EVENT_NAME, bestand,
                           ziel_ids=ziel_ids)
    assert kette[2]["eltern_id"] == 555
    assert kette[2]["createfolder"]["nach_folderid"] == 555
    assert kette[4]["eltern_id"] == 557
    assert kette[4]["art"] == "vorhanden"          # Event steht im Bestand
    assert kette[3]["art"] == "vorhanden"          # Kategorie steht im Bestand


def test_ordnerkette_event_vorbuchung_ist_finden_oder_bauen():
    ziel_ids = {f"Agent/Fotos/2019/{KATEGORIE}": 777}
    kette = fs.ordnerkette(2019, KATEGORIE, EVENT_NAME,
                           _bestand([_kategorie(KATEGORIE_ZWEI)]),
                           ziel_ids=ziel_ids)
    vorbuchung = kette[4]["createfolder"]
    assert vorbuchung["art"] == "createfolder"
    assert vorbuchung["name"] == EVENT_NAME
    assert vorbuchung["nach_folderid"] == 777
    assert vorbuchung["trocken"] is True


def test_plan_ohne_createfolder_doppelt():
    zeilen = [_zeile(anlass_id="2022-09-05_Anlass-01"),
              _zeile(anlass_id="2022-09-05_Anlass-02")]
    plan = _plan(zeilen)
    pfade = [eintrag["pfad"] for eintrag in plan["ordner"]]
    assert len(pfade) == len(set(pfade))


def test_plan_ordnerliste_ist_sortiert():
    zeilen = [_zeile(anlass_id="2022-09-05_Anlass-01"),
              _zeile(anlass_id="2021-09-05_Anlass-01")]
    plan = _plan(zeilen)
    pfade = [eintrag["pfad"] for eintrag in plan["ordner"]]
    assert pfade == sorted(pfade)


def test_plan_zaehlt_ordner_neu_und_vorhanden():
    bestand = _bestand([_kategorie(unterordner=[EVENT_NAME])])
    plan = _plan([_zeile()], bestand=bestand)
    assert plan["zusammenfassung"]["ordner_vorhanden"] == 2      # Kategorie+Event
    assert plan["zusammenfassung"]["ordner_neu"] == 3            # Agent, Fotos, Jahr


# ── Zuege (Regel 8) ───────────────────────────────────────────────────────

def test_zug_hat_alle_felder():
    zug = _plan([_zeile()])["zuege"][0]
    for feld in ("thema_quelle", "jahr", "kategorie", "event", "event_quelle",
                 "von_ordner", "von_name", "ziel_pfad", "fileid"):
        assert feld in zug


def test_zug_zielpfad_kommt_aus_ziel_pfad():
    zug = _plan([_zeile()])["zuege"][0]
    assert zug["ziel_pfad"] == kat.ziel_pfad(2019, KATEGORIE, zug["event"])


def test_zug_ohne_ids_hat_fileid_null():
    zug = _plan([_zeile()])["zuege"][0]
    assert zug["fileid"] is None


def test_zug_ohne_ids_hat_keine_vorbuchung():
    zug = _plan([_zeile()])["zuege"][0]
    assert zug["vorbuchung"] is None
    assert "unbekannt" in zug["hinweis"]


def test_zug_mit_ids_hat_fileid():
    ids = {ORDNER_A: {"folderid": 13, "dateien": {"bild1.jpg": 4242}}}
    zug = _plan([_zeile()], ids=ids)["zuege"][0]
    assert zug["fileid"] == 4242


def test_zug_mit_zielkennung_hat_trockene_vorbuchung():
    # Bestehender Event-Ordner im Bestand -> der Zug zielt genau dorthin,
    # die Ziel-Kennung ist ueber ziel_ids bekannt -> trockene Vorbuchung.
    bestand = _bestand([_kategorie(unterordner=[EVENT_NAME])])
    ids = {ORDNER_A: {"folderid": 13, "dateien": {"bild1.jpg": 4242}}}
    ziel_ids = {kat.ziel_pfad(2019, KATEGORIE, EVENT_NAME): 888}
    zug = _plan([_zeile()], bestand=bestand, ids=ids,
                ziel_ids=ziel_ids)["zuege"][0]
    assert zug["event"] == EVENT_NAME
    assert zug["vorbuchung"]["trocken"] is True
    assert zug["vorbuchung"]["fileid"] == 4242
    assert zug["vorbuchung"]["von_folderid"] == 13
    assert zug["vorbuchung"]["nach_folderid"] == 888
    assert zug["hinweis"] == ""


def test_zuege_sind_reproduzierbar_sortiert():
    zeilen = [_zeile(anlass_id="2021-01-01_Anlass-01", datei="z.jpg",
                     ordner=ORDNER_B),
              _zeile(anlass_id="2019-11-25_Anlass-01", datei="b.jpg"),
              _zeile(anlass_id="2019-11-25_Anlass-01", datei="a.jpg")]
    zuege = _plan(zeilen)["zuege"]
    schluessel = [(z["jahr"], z["kategorie"], z["event"], z["von_name"])
                  for z in zuege]
    assert schluessel == sorted(schluessel)


def test_zuege_ein_zug_je_eingeplanter_datei():
    plan = _plan([_zeile(datei="a.jpg"), _zeile(datei="b.jpg"),
                  _zeile(datei="kopie.jpg", doppelung="doppelt")])
    assert len(plan["zuege"]) == 2


def test_datei_kennung_findet_auch_andere_schreibweise():
    ids = {ORDNER_A: {"folderid": 13, "dateien": {"Bild1.JPG": 4242}}}
    assert fs.datei_kennung(ids, ORDNER_A, "bild1.jpg") == 4242


def test_datei_kennung_ohne_ids_ist_none():
    assert fs.datei_kennung({}, ORDNER_A, "bild1.jpg") is None
    assert fs.datei_kennung(None, ORDNER_A, "bild1.jpg") is None


# ── Kennungen lesend holen ─────────────────────────────────────────────────

def test_pfad_teile_entfernt_laufwerk():
    assert fs.pfad_teile(ORDNER_A) == ["Beispiel-Cloud", "Beispiel-Geraet",
                                       "DCIM", "Camera"]


def test_ordner_kennung_findet_ordner():
    dienst = FakeService()
    assert fs.ordner_kennung(dienst, ORDNER_A) == 13


def test_ordner_kennung_unbekannter_ordner_ist_none():
    assert fs.ordner_kennung(FakeService(), "P:/Beispiel-Cloud/Gibtsnicht") is None


def test_ordner_kennung_ohne_dienst_ist_none():
    assert fs.ordner_kennung(None, ORDNER_A) is None


def test_ordner_kennung_vertraegt_fehler_des_dienstes():
    class Kaputt:
        def liste(self, folderid=0):
            raise RuntimeError("Beispiel-Fehler")

    assert fs.ordner_kennung(Kaputt(), ORDNER_A) is None


def test_service_ids_holen_liest_die_quellordner():
    ids = fs.service_ids_holen(FakeService(), [ORDNER_A, ORDNER_B])
    assert ids[ORDNER_A]["folderid"] == 13
    assert ids[ORDNER_A]["dateien"]["bild1.jpg"] == 4242
    assert ids[ORDNER_B]["folderid"] is None


def test_service_ids_holen_ist_nur_lesend():
    dienst = FakeService()
    fs.service_ids_holen(dienst, [ORDNER_A])
    assert dienst.aufrufe[0] == fs.PCLOUD_WURZEL_ID


def test_service_ids_holen_ohne_ordner_leer():
    assert fs.service_ids_holen(FakeService(), []) == {}


# ── Plan, Idempotenz, Schreiben ────────────────────────────────────────────

def test_plan_ist_trocken():
    assert _plan([_zeile()])["trocken"] is True


def test_plan_zusammenfassung_hat_alle_zaehler():
    zusammenfassung = _plan([_zeile()])["zusammenfassung"]
    assert set(zusammenfassung) == {
        "zeilen", "anlaesse", "zuege", "doppelung_gesamt",
        "doppelung_ohne_anlass", "doppelung_uebersprungen", "ohne_thema",
        "ohne_jahr", "ordner_neu", "ordner_vorhanden", "events_neu",
        "events_wiederverwendet", "je_jahr", "je_kategorie"}


def test_plan_zaehlt_zeilen_anlaesse_und_zuege():
    zusammenfassung = _plan([_zeile(), _zeile(datei="b.jpg")])["zusammenfassung"]
    assert zusammenfassung["zeilen"] == 2
    assert zusammenfassung["anlaesse"] == 1
    assert zusammenfassung["zuege"] == 2


def test_plan_zaehlt_je_jahr():
    zeilen = [_zeile(anlass_id="2019-11-25_Anlass-01", jahr="2019"),
              _zeile(anlass_id="2021-01-01_Anlass-01", datei="b.jpg",
                     jahr="2021", monat="1", tag="1")]
    je_jahr = _plan(zeilen)["zusammenfassung"]["je_jahr"]
    assert je_jahr == {"2019": 1, "2021": 1}


def test_plan_zaehlt_je_kategorie():
    zeilen = [_zeile(anlass_id="2019-11-25_Anlass-01"),
              _zeile(anlass_id="2019-11-26_Anlass-01", datei="b.jpg",
                     thema=THEMA_KUCHEN)]
    bestand = _bestand([_kategorie(), _kategorie(KATEGORIE_ZWEI, folderid=120)])
    je_kategorie = _plan(zeilen, bestand=bestand,
                         zuordnung=_zuordnung({BUCKET: KATEGORIE,
                                               BUCKET_KUCHEN: KATEGORIE_ZWEI})
                         )["zusammenfassung"]["je_kategorie"]
    assert je_kategorie == {KATEGORIE: 1, KATEGORIE_ZWEI: 1}


def test_plan_zaehlt_doppelungen():
    plan = _plan([_zeile(), _zeile(datei="kopie.jpg", doppelung="doppelt")])
    assert plan["zusammenfassung"]["doppelung_uebersprungen"] == 1


# ── Doppelungen aufgeschluesselt (gesamt / ohne Anlass-ID / uebersprungen) ─

def test_doppelung_mit_anlass_id_zaehlt_in_gesamt_und_uebersprungen():
    plan = _plan([_zeile(datei="a.jpg"),
                  _zeile(datei="kopie.jpg", doppelung="IMG (2)")])
    z = plan["zusammenfassung"]
    assert z["doppelung_gesamt"] == 1
    assert z["doppelung_uebersprungen"] == 1
    assert z["doppelung_ohne_anlass"] == 0


def test_doppelung_ohne_anlass_id_zaehlt_in_gesamt_und_ohne_anlass():
    plan = _plan([_zeile(datei="a.jpg"),
                  _zeile(anlass_id="", datei="ortslos.jpg",
                         doppelung="IMG (2)")])
    z = plan["zusammenfassung"]
    assert z["doppelung_gesamt"] == 1
    assert z["doppelung_ohne_anlass"] == 1
    assert z["doppelung_uebersprungen"] == 0
    assert z["anlaesse"] == 1


def test_doppelung_aufschluesselung_summiert_sich_nicht_doppelt():
    plan = _plan([_zeile(),
                  _zeile(datei="kopie.jpg", doppelung="doppelt"),
                  _zeile(anlass_id="", datei="ortslos.jpg",
                         doppelung="doppelt")])
    z = plan["zusammenfassung"]
    assert z["doppelung_gesamt"] == 2
    assert (z["doppelung_uebersprungen"] + z["doppelung_ohne_anlass"]
            == z["doppelung_gesamt"])


def test_buendeln_zaehlt_doppelung_aufgeschluesselt():
    ergebnis = fs.anlaesse_buendeln([
        _zeile(),
        _zeile(datei="kopie.jpg", doppelung="doppelt"),
        _zeile(anlass_id="", datei="ortslos.jpg", doppelung="doppelt")])
    assert ergebnis["doppelung_gesamt"] == 2
    assert ergebnis["doppelung_uebersprungen"] == 1
    assert ergebnis["doppelung_ohne_anlass"] == 1
    assert ergebnis["ohne_thema_quelle"] == 1


def test_doppelung_ohne_anlass_aendert_die_zuege_nicht():
    ohne = _plan([_zeile(datei="a.jpg"), _zeile(datei="b.jpg")])
    mit = _plan([_zeile(datei="a.jpg"), _zeile(datei="b.jpg"),
                 _zeile(anlass_id="", datei="ortslos.jpg",
                        doppelung="doppelt")])
    assert len(mit["zuege"]) == len(ohne["zuege"]) == 2
    assert mit["zusammenfassung"]["zuege"] == ohne["zusammenfassung"]["zuege"]
    assert mit["zuege"] == ohne["zuege"]
    assert mit["anlaesse"] == ohne["anlaesse"]


def test_main_nennt_beide_doppelungszahlen(tmp_path, capsys):
    umgebung = _umgebung(tmp_path, [
        _zeile(),
        _zeile(datei="kopie.jpg", doppelung="doppelt"),
        _zeile(anlass_id="", datei="ortslos.jpg", doppelung="doppelt")])
    assert _lauf(umgebung) == 0
    ausgabe = capsys.readouterr().out
    assert "Doppelungen: 2 in der CSV" in ausgabe
    assert "davon 1 ohne Anlass-ID (ohnehin uebersprungen)" in ausgabe
    assert "1 in geplanten Anlaessen uebersprungen" in ausgabe


def test_uebersicht_text_nennt_die_doppelungs_aufschluesselung():
    text = fs.uebersicht_text({"doppelung_gesamt": 1534,
                               "doppelung_ohne_anlass": 866,
                               "doppelung_uebersprungen": 668})
    assert "Doppelungen: 1.534 in der CSV" in text
    assert "davon 866 ohne Anlass-ID (ohnehin uebersprungen)" in text
    assert "668 in geplanten Anlaessen uebersprungen" in text


def test_plan_zweiter_lauf_ist_gleich():
    zeilen = [_zeile(), _zeile(anlass_id="2021-01-01_Anlass-01", datei="b.jpg")]
    erst = json.dumps(_plan(zeilen), ensure_ascii=False, sort_keys=True)
    zweit = json.dumps(_plan(list(zeilen)), ensure_ascii=False, sort_keys=True)
    assert erst == zweit


def test_plan_schreiben_trocken_schreibt_nichts(tmp_path):
    plan = _plan([_zeile()])
    ziel = tmp_path / "sortierplan.json"
    ergebnis = fs.plan_schreiben(str(ziel), plan, schreiben=False)
    assert ergebnis["geschrieben"] is False
    assert ergebnis["trocken"] is True
    assert not ziel.exists()


def test_plan_schreiben_legt_die_datei_an(tmp_path):
    plan = _plan([_zeile()])
    ziel = tmp_path / "sortierplan.json"
    ergebnis = fs.plan_schreiben(str(ziel), plan, schreiben=True)
    assert ergebnis["geschrieben"] is True
    daten = json.loads(ziel.read_text(encoding="utf-8"))
    assert daten["trocken"] is True
    assert "stand" in daten
    assert len(daten["zuege"]) == 1


def test_plan_schreiben_zweiter_lauf_bleibt_byte_identisch(tmp_path):
    plan = _plan([_zeile()])
    ziel = tmp_path / "sortierplan.json"
    fs.plan_schreiben(str(ziel), plan, schreiben=True)
    vorher = _datei_hash(ziel)
    ergebnis = fs.plan_schreiben(str(ziel), plan, schreiben=True)
    assert ergebnis["unveraendert"] is True
    assert _datei_hash(ziel) == vorher


def test_plan_schreiben_im_repo_wird_abgelehnt():
    plan = _plan([_zeile()])
    with pytest.raises(SystemExit):
        fs.plan_schreiben(str(REPO / "sortierplan.json"), plan, schreiben=True)


# ── Kommandozeile ──────────────────────────────────────────────────────────

def test_main_ohne_schreiben_schreibt_nichts(tmp_path):
    umgebung = _umgebung(tmp_path, [_zeile()])
    assert _lauf(umgebung) == 0
    assert not umgebung["plan"].exists()


def test_main_mit_schreiben_legt_den_plan_an(tmp_path):
    umgebung = _umgebung(tmp_path, [_zeile()])
    assert _lauf(umgebung, ["--schreiben"]) == 0
    assert umgebung["plan"].exists()


def test_main_ohne_schreiben_schlaegt_schreiben(tmp_path):
    umgebung = _umgebung(tmp_path, [_zeile()])
    assert _lauf(umgebung, ["--schreiben", "--ohne-schreiben"]) == 0
    assert not umgebung["plan"].exists()


def test_main_zeigt_die_zahlenuebersicht(tmp_path, capsys):
    umgebung = _umgebung(tmp_path, [_zeile()])
    _lauf(umgebung)
    ausgabe = capsys.readouterr().out
    assert "TROCKENLAUF" in ausgabe
    assert "Ordner neu:" in ausgabe
    assert "Events wiederverwendet:" in ausgabe


def test_main_warnt_bei_anlaessen_ohne_jahr(tmp_path, capsys):
    umgebung = _umgebung(tmp_path, [_zeile(anlass_id="Anlass-07", jahr="")])
    _lauf(umgebung)
    ausgabe = capsys.readouterr().out
    assert "ohne Jahr" in ausgabe


def test_main_meldet_fehlende_csv(tmp_path, capsys):
    umgebung = _umgebung(tmp_path, [_zeile()])
    umgebung["csv"].unlink()
    assert _lauf(umgebung) == 2
    assert "Fehler" in capsys.readouterr().out


def test_main_mit_ids_nutzt_den_dienst(tmp_path, capsys):
    umgebung = _umgebung(tmp_path, [_zeile()])
    dienst = FakeService()
    assert fs.main(["--csv", str(umgebung["csv"]),
                    "--kategorien-pfad", str(umgebung["bestand"]),
                    "--zuordnung-pfad", str(umgebung["zuordnung"]),
                    "--plan", str(umgebung["plan"]), "--mit-ids"],
                   service=dienst) == 0
    assert 13 in dienst.aufrufe


def test_main_ohne_schreiben_meldet_es(tmp_path, capsys):
    umgebung = _umgebung(tmp_path, [_zeile()])
    _lauf(umgebung)
    assert "NICHTS geschrieben" in capsys.readouterr().out


def test_main_beispiele_sind_begrenzt(tmp_path, capsys):
    zeilen = [_zeile(datei=f"bild{nummer}.jpg") for nummer in range(4)]
    umgebung = _umgebung(tmp_path, zeilen)
    _lauf(umgebung, ["--beispiele", "2"])
    ausgabe = capsys.readouterr().out
    assert "Stichprobe (2):" in ausgabe
    assert ausgabe.count("->") == 2


# ── Ausgabe-Helfer ─────────────────────────────────────────────────────────

def test_zahlenzeile_hat_deutsche_punkte():
    text = fs.zahlenzeile({"anlaesse": 2134, "zeilen": 9430, "zuege": 8284,
                           "ordner_neu": 1279, "events_wiederverwendet": 39})
    assert "2.134 Anlaesse" in text
    assert "9.430 Zeilen" in text
    assert "1.279 Ordner neu" in text


def test_uebersicht_text_nennt_alle_zaehler():
    text = fs.uebersicht_text(_plan([_zeile()])["zusammenfassung"])
    for stichwort in ("Zeilen:", "Doppelungen:", "in geplanten Anlaessen uebersprungen",
                      "Anlaesse ohne Thema:", "Anlaesse ohne Jahr:", "Ordner neu:",
                      "Ordner vorhanden:", "Events neu:", "Events wiederverwendet:",
                      "Je Jahr:"):
        assert stichwort in text


def test_uebersicht_text_nennt_zeilen_ohne_anlass_id():
    text = fs.uebersicht_text({}, ohne_thema_quelle=7)
    assert "Zeilen ohne Anlass-ID (uebersprungen): 7" in text


def test_beispiele_zeilen_sind_begrenzt():
    plan = _plan([_zeile(datei="a.jpg"), _zeile(datei="b.jpg"),
                  _zeile(datei="c.jpg")])
    assert len(fs.beispiele_zeilen(plan, 2)) == 2
    assert fs.beispiele_zeilen(plan, 0) == []


def test_beispiele_zeilen_zeigen_den_zielpfad():
    zeile = fs.beispiele_zeilen(_plan([_zeile()]), 1)[0]
    assert "->" in zeile
    assert "bild1.jpg" in zeile


# ── Trockenlauf-Garantien (Quelltext und Nebenwirkungen) ──────────────────

def test_quelltext_hat_keine_loeschfunktion():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    for verboten in ("deletefile", "deletefolder", "os.remove", "os.unlink",
                     "shutil.rmtree"):
        assert verboten not in quelle, f"Loeschfunktion im Quelltext: {verboten}"


def test_quelltext_hat_keinen_echten_schreibaufruf():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert "trocken=False" not in quelle
    assert "manifest_anhaengen" not in quelle


def test_quelltext_nutzt_ziel_pfad_aus_dem_nachbarmodul():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert "ziel_pfad(" in quelle
    assert "pfad_saeubern(" in quelle


def test_lauf_laesst_manifest_unberuehrt(tmp_path, capsys):
    umgebung = _umgebung(tmp_path, [_zeile()])
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text('{"art": "movefile", "name": "bild1.jpg"}\n',
                        encoding="utf-8")
    vorher = _datei_hash(manifest)
    assert _lauf(umgebung, ["--schreiben"]) == 0
    assert _datei_hash(manifest) == vorher
    assert manifest.read_text(encoding="utf-8").count("\n") == 1
    assert "nicht angeruehrt" in capsys.readouterr().out


def test_lauf_legt_kein_manifest_an(tmp_path):
    umgebung = _umgebung(tmp_path, [_zeile()])
    _lauf(umgebung, ["--schreiben"])
    assert list(tmp_path.glob("manifest*.jsonl")) == []


def test_schreiben_im_repo_ist_gesperrt(tmp_path, capsys):
    umgebung = _umgebung(tmp_path, [_zeile()])
    ziel_im_repo = REPO / "sortierplan.json"
    assert not ziel_im_repo.exists(), "Vorbedingung: die Datei gibt es nicht"
    with pytest.raises(SystemExit) as ausstieg:
        fs.main(["--csv", str(umgebung["csv"]),
                 "--kategorien-pfad", str(umgebung["bestand"]),
                 "--zuordnung-pfad", str(umgebung["zuordnung"]),
                 "--plan", str(ziel_im_repo),
                 "--ohne-ids", "--schreiben"])
    ausgabe = capsys.readouterr().out
    # Der genaue Wortlaut aus foto_kategorien._pruefe_ziel_ausserhalb_repo.
    assert "Zieldatei liegt IM Repo und ist nicht erlaubt" in ausgabe
    assert "es wird NICHTS geschrieben" in ausgabe
    assert ausstieg.value.code == 2
    assert not ziel_im_repo.exists(), "im Repo darf nichts entstanden sein"
