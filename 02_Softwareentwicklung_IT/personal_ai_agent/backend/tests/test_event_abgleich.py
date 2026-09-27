"""Pruefungen fuer event_abgleich.py (Nachtlauf-Schritt N6e) — alles OHNE Netz.

Kein pCloud-Aufruf, kein Dienst, keine Attrappe noetig: das Werkzeug liest
ausschliesslich lokale Dateien. Alle Dateien gehen nach ``tmp_path``.

**Nur erfundene Beispielnamen** — Sebastians echte Ordnernamen liegen bewusst
ausserhalb des Repos und kommen hier nicht vor (Mustersee, Beispielstadt,
Bandname, Festival, Musterperson, Beispiel_2019, Spielkonsole, Spiel A 2 …).

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_event_abgleich.py -q
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

WERKZEUG = (Path(__file__).resolve().parents[2]
            / "tools" / "foto_sortierung" / "event_abgleich.py")
KATEGORIEN_WERKZEUG = (Path(__file__).resolve().parents[2]
                       / "tools" / "foto_sortierung" / "foto_kategorien.py")
REPO = Path(__file__).resolve().parents[2]


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


ev = _laden(WERKZEUG, "event_abgleich")
kat = _laden(KATEGORIEN_WERKZEUG, "foto_kategorien")

# Erfundene Beispielnamen. Das Thema ist ein echter Katalogeintrag, damit die
# Kette Thema -> Bucket -> Kategorie pruefbar ist.
THEMA_KONZERT = "Konzert und Buehne"
BUCKET_KONZERT = "Konzerte und Partys"
ORDNER_BAND = "2019_11 Bandname"
ORDNER_ALBUM = "2019 Album"
ORDNER_FESTIVAL = "2019_08 Festival"
ORDNER_ZEITRAUM = "2018-2021 Zeitraum"
ORDNER_PERSON = "Musterperson"


# ── kleine Helfer ──────────────────────────────────────────────────────────

def _anlass(datum="2019-11-25", thema=THEMA_KONZERT, kacheln=(),
            titel=None, **rest):
    anlass = {"titel": titel or f"{datum}_Anlass-01", "datum": datum,
              "thema": thema, "kacheln": [{"kurz": k} for k in kacheln]}
    anlass.update(rest)
    return anlass


def _kategorie(name="Kategorie A", unterordner=(), dateien_direkt=0,
               folderid=110):
    return {"name": name, "folderid": folderid,
            "unterordner": list(unterordner), "dateien_direkt": dateien_direkt}


def _bestand_schreiben(pfad: Path, kategorien) -> str:
    pfad.write_text(json.dumps({"stand": "2026-09-27T10:00:00",
                                "wurzel": "Bilder & Videos",
                                "kategorien": list(kategorien)},
                               ensure_ascii=False), encoding="utf-8")
    return str(pfad)


def _zuordnung_schreiben(pfad: Path, werte: dict) -> str:
    """Zuordnungsdatei mit ALLEN Buckets schreiben (fehlende = null)."""
    buckets = {name: werte.get(name) for name in kat.BUCKETS}
    pfad.write_text(json.dumps({"buckets": buckets}, ensure_ascii=False),
                    encoding="utf-8")
    return str(pfad)


def _jsonl_schreiben(pfad: Path, anlaesse) -> str:
    zeilen = []
    for anlass in anlaesse:
        zeile = {name: wert for name, wert in anlass.items() if name != "kacheln"}
        zeilen.append(json.dumps(zeile, ensure_ascii=False))
    pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return str(pfad)


def _md5(pfad: Path) -> str:
    return hashlib.md5(pfad.read_bytes()).hexdigest()


class Stolperfalle:
    """Ein Schreibversuch, der niemals passieren darf."""

    def __call__(self, *args, **kwargs):
        raise AssertionError("Es wurde geschrieben, obwohl nichts geschrieben darf!")


def _umgebung(tmp_path, unterordner=(ORDNER_BAND, ORDNER_ALBUM, ORDNER_PERSON),
              anlaesse=None):
    """Bestand + Zuordnung + themen.jsonl im tmp-Ordner anlegen."""
    kat_pfad = _bestand_schreiben(tmp_path / "kategorien.json", [
        _kategorie("Kategorie A", unterordner),
        _kategorie("Kategorie B", [], folderid=120),
    ])
    zu_pfad = _zuordnung_schreiben(tmp_path / "zuordnung.json",
                                   {BUCKET_KONZERT: "Kategorie A"})
    themen_pfad = _jsonl_schreiben(tmp_path / "themen.jsonl",
                                   anlaesse if anlaesse is not None
                                   else [_anlass()])
    return kat_pfad, zu_pfad, themen_pfad


# ── Laden und Schnittstelle ────────────────────────────────────────────────

def test_werkzeug_laedt_und_bietet_die_schnittstelle():
    """Das Werkzeug ist per Pfad ladbar und hat die oeffentliche Schnittstelle."""
    for name in ("ordner_datum_lesen", "datum_stufe", "kandidaten",
                 "vorschlag_fuer", "hinweis_text", "trefferquote",
                 "vorschlaege_schreiben", "anlaesse_laden", "unterordner_von",
                 "kategorie_fuer_anlass", "vorschlaege_bauen",
                 "bestand_und_zuordnung", "anlass_teile", "anlass_datum",
                 "anlass_thema", "main", "EventFehler", "KategorienFehler",
                 "STUFEN", "SICHERE_STUFEN", "STUFEN_VORSCHLAG",
                 "STUFEN_SCHWACH"):
        assert hasattr(ev, name), name
    assert ev.STUFEN == ["tag", "monat", "jahr", "spanne", "ohne_jahr"]
    assert ev.SICHERE_STUFEN == ("tag", "monat")
    # Verschaerfte Regel der Runde 2: nur tag/monat sind Vorschlaege.
    assert ev.STUFEN_VORSCHLAG == ("tag", "monat")
    assert ev.STUFEN_SCHWACH == ("jahr", "spanne")
    assert ev.EventFehler is not ev.KategorienFehler
    # Die Vorgabepfade liegen ausserhalb des Repos (private Namen).
    for pfad in (ev.STANDARD_KATEGORIEN, ev.STANDARD_ZUORDNUNG,
                 ev.STANDARD_THEMEN, ev.STANDARD_VORSCHLAEGE):
        assert not str(pfad).startswith(str(REPO)), pfad


# ── ordner_datum_lesen: die drei Muster ────────────────────────────────────

def test_ordner_datum_lesen_muster_jahr_ort():
    """``Jahr Ort`` (Reise/Ausfluege): ein Jahr, kein Monat, Rest = Ort."""
    belege = ev.ordner_datum_lesen("2013 Mustersee")
    assert belege["jahre"] == [2013]
    assert belege["spanne"] is False and belege["offen_ab"] is False
    assert belege["monat"] is None and belege["tag"] is None
    assert belege["rest"] == "Mustersee"
    belege = ev.ordner_datum_lesen("2020 Beispielstadt")
    assert belege["jahre"] == [2020] and belege["rest"] == "Beispielstadt"


def test_ordner_datum_lesen_muster_jahr_monat_tag_ereignis():
    """``Jahr_Monat[_Tag] Ereignis`` (Konzerte/Feste): Monat und Tag lesbar."""
    belege = ev.ordner_datum_lesen("2019_11_25 Bandname")
    assert belege["jahre"] == [2019] and belege["monat"] == 11
    assert belege["tag"] == 25 and belege["rest"] == "Bandname"
    belege = ev.ordner_datum_lesen(ORDNER_BAND)          # ohne Tag
    assert belege["jahre"] == [2019] and belege["monat"] == 11
    assert belege["tag"] is None and belege["rest"] == "Bandname"
    belege = ev.ordner_datum_lesen("2019_08 Festival")
    assert belege["monat"] == 8 and belege["tag"] is None
    assert belege["rest"] == "Festival"
    belege = ev.ordner_datum_lesen("2018-11-25 Bandname")
    assert belege["monat"] == 11 and belege["tag"] == 25
    belege = ev.ordner_datum_lesen("2018_3 Party-Name")
    assert belege["jahre"] == [2018] and belege["monat"] == 3
    assert belege["rest"] == "Party-Name"


def test_ordner_datum_lesen_muster_jahr_person():
    """``Jahr Person`` (Verwandte/Bekannte): nur das Jahr, Person bleibt Rest."""
    belege = ev.ordner_datum_lesen("2017 Musterperson")
    assert belege["jahre"] == [2017] and belege["monat"] is None
    assert belege["rest"] == "Musterperson"


def test_ordner_datum_lesen_sonderformen_spanne_offen_suffix():
    """Jahresspanne, offenes Ende und Jahr als Suffix."""
    belege = ev.ordner_datum_lesen("2015-2018 Ausflug")
    assert belege["jahre"] == [2015, 2018] and belege["spanne"] is True
    assert belege["offen_ab"] is False and belege["rest"] == "Ausflug"
    belege = ev.ordner_datum_lesen("2013_2014 Ding")
    assert belege["jahre"] == [2013, 2014] and belege["spanne"] is True
    belege = ev.ordner_datum_lesen("2019+ Festival")
    assert belege["jahre"] == [2019] and belege["offen_ab"] is True
    assert belege["spanne"] is False and belege["rest"] == "Festival"
    belege = ev.ordner_datum_lesen("2020+ Vorname")
    assert belege["offen_ab"] is True and belege["rest"] == "Vorname"
    belege = ev.ordner_datum_lesen("Beispiel_2019")
    assert belege["jahre"] == [2019] and belege["rest"] == "Beispiel"


def test_ordner_datum_lesen_punktdatum_und_monatsliste():
    """``… 10.10.21`` ist ein volles Datum, ``2021_08 & 10`` nur ein Monat."""
    belege = ev.ordner_datum_lesen("Ausflug 10.10.21")
    assert belege["jahre"] == [2021]
    assert belege["monat"] == 10 and belege["tag"] == 10
    assert belege["rest"] == "Ausflug"
    belege = ev.ordner_datum_lesen("Ausflug 10.10.2021")
    assert belege["jahre"] == [2021] and belege["tag"] == 10
    # Monatsliste: nur die ans Jahr angedockte Zahl ist ein Monat, die zweite
    # bleibt im Rest stehen (sie wird NICHT als Monat geraten).
    belege = ev.ordner_datum_lesen("2021_08 & 10 Ding")
    assert belege["jahre"] == [2021] and belege["monat"] == 8
    assert belege["tag"] is None
    assert belege["rest"] == "& 10 Ding"


def test_ordner_datum_lesen_jahr_doppelt_wird_einmal_gezaehlt():
    """Jahr doppelt im Namen: ein Jahr, aber als Spanne gelesen."""
    belege = ev.ordner_datum_lesen("2019_2019 Festival")
    assert belege["jahre"] == [2019]
    assert belege["spanne"] is True
    assert belege["rest"] == "Festival"
    assert ev.ordner_datum_lesen("2019 Fest 2019")["jahre"] == [2019]


def test_ordner_datum_lesen_ohne_jahr():
    """Ordner ohne jedes Jahr: leere Jahre, Name bleibt als Rest."""
    for name in (ORDNER_PERSON, "Bandname", "Spielkonsole", "Beispiel"):
        belege = ev.ordner_datum_lesen(name)
        assert belege["jahre"] == [], name
        assert belege["spanne"] is False and belege["offen_ab"] is False
        assert belege["monat"] is None and belege["tag"] is None, name
        assert belege["rest"] == name, name


def test_ordner_datum_lesen_blanke_zahl_ist_kein_monat():
    """Fehltreffer-Regel: eine blanke Zahl 1-12 ist nur direkt am Jahr ein Monat."""
    for name in ("Spiel A 2", "Spiel B 3", "9.Klasse", "108", "2 Wochen",
                 "Ausflug 12", "Kurs 11"):
        belege = ev.ordner_datum_lesen(name)
        assert belege["monat"] is None, name
        assert belege["tag"] is None, name
    # Gegenprobe: direkt angedockt ist es ein Monat.
    assert ev.ordner_datum_lesen("2018_2 Wochen")["monat"] == 2
    assert ev.ordner_datum_lesen("2018-12 Kurs")["monat"] == 12
    # Eine Zahl groesser 12 direkt am Jahr ist kein Monat (und kein Tag).
    belege = ev.ordner_datum_lesen("2018_13 Ding")
    assert belege["monat"] is None and belege["tag"] is None
    assert belege["jahre"] == [2018]


def test_ordner_datum_lesen_jahr_nur_1900_bis_2100():
    """1899 und 2101 sind keine Jahre — der Bereich ist hart begrenzt."""
    assert ev.ordner_datum_lesen("1899 Alt")["jahre"] == []
    assert ev.ordner_datum_lesen("2101 Neu")["jahre"] == []
    assert ev.ordner_datum_lesen("1900 Alt")["jahre"] == [1900]
    assert ev.ordner_datum_lesen("2100 Neu")["jahre"] == [2100]
    assert ev.JAHR_MIN == 1900 and ev.JAHR_MAX == 2100


def test_ordner_datum_lesen_rest_wird_gesaeubert():
    """Der Rest laeuft durch pfad_saeubern (verbotene Zeichen, Raender)."""
    belege = ev.ordner_datum_lesen("2019_08 Fes/tival")
    assert belege["rest"] == "Fes tival"
    belege = ev.ordner_datum_lesen("2019_08 Band:*?")
    assert belege["rest"] == "Band"
    assert ev.ordner_datum_lesen("2019")["rest"] == ev.OHNE_NAME


def test_ordner_datum_lesen_krumme_eingaben_ohne_exception():
    """None, Zahlen, Listen: leere Belege statt eines Absturzes."""
    for wert in (None, "", "   ", 7, 3.5, ["2019"], {"name": "2019"}, b"2019"):
        belege = ev.ordner_datum_lesen(wert)
        assert belege["jahre"] == [], wert
        assert belege["monat"] is None and belege["tag"] is None, wert
        assert belege["rest"] == ev.OHNE_NAME, wert


# ── datum_stufe ────────────────────────────────────────────────────────────

def test_datum_stufe_jede_stufe():
    """Jede der fuenf Stufen wird genau einmal getroffen."""
    anlass = _anlass("2019-11-25")
    assert ev.datum_stufe(anlass, "2019_11_25 Bandname") == "tag"
    assert ev.datum_stufe(anlass, "2019_11 Bandname") == "monat"
    assert ev.datum_stufe(anlass, "2019 Album") == "jahr"
    assert ev.datum_stufe(anlass, "2018-2021 Zeitraum") == "spanne"
    assert ev.datum_stufe(anlass, "2019+ Festival") == "jahr"      # Randjahr
    assert ev.datum_stufe(anlass, "2018+ Festival") == "spanne"    # offen ab
    assert ev.datum_stufe(anlass, ORDNER_PERSON) == "ohne_jahr"
    assert ev.datum_stufe(anlass, "Beispiel_2019") == "jahr"


def test_datum_stufe_fremdes_jahr_ist_ohne_jahr():
    """Ein Name mit anderem Jahr hat keinen Jahres-Bezug -> ohne_jahr."""
    anlass = _anlass("2019-11-25")
    assert ev.datum_stufe(anlass, "2018 Album") == "ohne_jahr"
    assert ev.datum_stufe(anlass, "2011-2014 Zeitraum") == "ohne_jahr"
    assert ev.datum_stufe(anlass, "2021+ Spaeter") == "ohne_jahr"


def test_datum_stufe_fehlender_teil_zaehlt_nie_als_treffer():
    """Fehlt am Anlass Monat oder Tag, sinkt die Stufe — nichts wird geraten."""
    nur_jahr = {"jahr": 2019}
    assert ev.datum_stufe(nur_jahr, "2019_11_25 Bandname") == "jahr"
    assert ev.datum_stufe(nur_jahr, "2019_11 Bandname") == "jahr"
    assert ev.datum_stufe(nur_jahr, "2019 Album") == "jahr"
    # Ohne Monat am Anlass gibt es kein "monat", selbst wenn der Name passt.
    ohne_monat = {"jahr": 2019, "tag": 25}
    assert ev.datum_stufe(ohne_monat, "2019_11_25 Bandname") == "jahr"
    # Ohne Jahr am Anlass gibt es gar keine Jahres-Stufe.
    assert ev.datum_stufe({"monat": 11, "tag": 25}, "2019_11_25 Bandname") \
        == "ohne_jahr"
    assert ev.datum_stufe({}, "2019 Album") == "ohne_jahr"


def test_datum_stufe_monat_im_namen_weicht_ab():
    """Gleiches Jahr, anderer Monat: Stufe 'jahr' mit Hinweis in der Begruendung."""
    anlass = _anlass("2019-05-02")
    assert ev.datum_stufe(anlass, "2019_11 Bandname") == "jahr"
    assert ev.datum_stufe(anlass, "2019_05 Bandname") == "monat"
    assert ev.datum_stufe(anlass, "2019_05_02 Bandname") == "tag"


def test_datum_stufe_spanne_grenzen():
    """Innerhalb der Spanne ja, ausserhalb nein; Randjahre sind 'jahr'."""
    anlass = _anlass("2016-07-01")
    assert ev.datum_stufe(anlass, "2015-2018 Ausflug") == "spanne"
    assert ev.datum_stufe(anlass, "2013_2014 Ding") == "ohne_jahr"
    assert ev.datum_stufe(anlass, "2018 Ding") == "ohne_jahr"
    assert ev.datum_stufe(_anlass("2015-07-01"), "2015-2018 Ausflug") == "jahr"
    assert ev.datum_stufe(_anlass("2018-07-01"), "2015-2018 Ausflug") == "jahr"


def test_datum_stufe_nimmt_auch_gelesene_belege():
    """Ein Beleg-Dict aus ordner_datum_lesen und ein Name fuehren zum Gleichen."""
    anlass = _anlass("2019-11-25")
    belege = ev.ordner_datum_lesen("2019_11 Bandname")
    assert ev.datum_stufe(anlass, belege) == ev.datum_stufe(
        anlass, "2019_11 Bandname") == "monat"


# ── kandidaten ─────────────────────────────────────────────────────────────

def test_kandidaten_sortiert_nach_stufe():
    """Stufen absteigend: tag, monat, jahr, spanne, ohne_jahr."""
    anlass = _anlass("2019-11-25")
    unterordner = [ORDNER_PERSON, ORDNER_ZEITRAUM, ORDNER_ALBUM,
                   ORDNER_FESTIVAL, ORDNER_BAND, "2019_11_25 Bandname"]
    stufen = [k["stufe"] for k in ev.kandidaten(anlass, unterordner)]
    assert stufen == ["tag", "monat", "jahr", "jahr", "spanne", "ohne_jahr"]


def test_kandidaten_sortiert_ueberlappung_dann_alphabetisch():
    """Gleiche Stufe: mehr Worttreffer zuerst, dann alphabetisch."""
    anlass = _anlass("2019-11-25", kacheln=["Festival Besuch am See"])
    unterordner = ["2019 Album Zwei", "2019 Album", "2019 Zzzz",
                   "2019 Festival"]
    namen = [k["name"] for k in ev.kandidaten(anlass, unterordner)]
    # "2019 Festival" hat einen Worttreffer und steht vorn; danach alphabetisch.
    assert namen[0] == "2019 Festival"
    assert namen[1:] == ["2019 Album", "2019 Album Zwei", "2019 Zzzz"]
    assert [k["ueberlappung"] for k in ev.kandidaten(anlass, unterordner)] \
        == [1, 0, 0, 0]


def test_kandidaten_sind_deterministisch():
    """Zwei Laeufe sortieren gleich (gleiche Liste, gleiche Reihenfolge)."""
    anlass = _anlass("2019-11-25", kacheln=["Band auf der Buehne"])
    unterordner = [ORDNER_PERSON, ORDNER_ZEITRAUM, ORDNER_ALBUM,
                   ORDNER_FESTIVAL, ORDNER_BAND]
    erster = ev.kandidaten(anlass, unterordner)
    zweiter = ev.kandidaten(anlass, list(reversed(unterordner)))
    assert erster == zweiter
    assert json.dumps(erster, ensure_ascii=False) == \
        json.dumps(zweiter, ensure_ascii=False)


def test_kandidaten_felder_und_begruendung():
    """Jeder Kandidat hat Name, Stufe, Ueberlappung und Klartext-Begruendung."""
    anlass = _anlass("2019-11-25")
    kandidat = ev.kandidaten(anlass, [ORDNER_BAND])[0]
    assert sorted(kandidat) == ["begruendung", "name", "stufe", "ueberlappung"]
    assert kandidat["name"] == ORDNER_BAND and kandidat["stufe"] == "monat"
    assert isinstance(kandidat["ueberlappung"], int)
    assert kandidat["begruendung"] == "Monat 11 und Jahr 2019 gleich"
    # Jede Stufe hat eine nicht leere Begruendung.
    for name in ("2019_11_25 Bandname", "2019 Album", "2018-2021 Zeitraum",
                 ORDNER_PERSON):
        begruendung = ev.kandidaten(anlass, [name])[0]["begruendung"]
        assert begruendung.strip(), name


def test_kandidaten_leere_und_krumme_eingaben():
    """Keine Unterordner, None und Nicht-Text: leere Liste, kein Absturz."""
    anlass = _anlass()
    assert ev.kandidaten(anlass, []) == []
    assert ev.kandidaten(anlass, None) == []
    assert ev.kandidaten(anlass, "2019 Album") == []
    assert [k["name"] for k in ev.kandidaten(anlass, [None, 7, "", "  "])] == []


# ── vorschlag_fuer ─────────────────────────────────────────────────────────

def test_vorschlag_fuer_ohne_jahr_ist_none():
    """Die harte Regel: ohne_jahr reicht nie fuer einen Vorschlag."""
    anlass = _anlass("2019-11-25")
    assert ev.vorschlag_fuer(anlass, [ORDNER_PERSON, "Bandname", "Spielkonsole"]) is None
    assert ev.vorschlag_fuer(anlass, []) is None
    assert ev.vorschlag_fuer(anlass, ["2018 Album"]) is None


def test_vorschlag_fuer_sicher_und_unsicher():
    """ohne auch_schwach nur tag/monat; jahr/spanne sind kein Vorschlag."""
    anlass = _anlass("2019-11-25")
    sicher = ev.vorschlag_fuer(anlass, [ORDNER_BAND, ORDNER_ALBUM])
    assert sicher["name"] == ORDNER_BAND and sicher["stufe"] == "monat"
    assert sicher["sicher"] is True
    Tag = ev.vorschlag_fuer(anlass, ["2019_11_25 Bandname", ORDNER_BAND])
    assert Tag["stufe"] == "tag" and Tag["sicher"] is True
    # Verschaerfte Regel: ein bloss gleiches Jahr ist KEIN Vorschlag mehr.
    assert ev.vorschlag_fuer(anlass, [ORDNER_ALBUM]) is None
    assert ev.vorschlag_fuer(anlass, [ORDNER_ZEITRAUM]) is None
    assert ev.vorschlag_fuer(_anlass("2019-07-01"), [ORDNER_ZEITRAUM]) is None
    # Ohne_jahr bleibt ebenfalls ohne Vorschlag.
    assert ev.vorschlag_fuer(anlass, [ORDNER_PERSON]) is None


def test_vorschlag_fuer_auch_schwach_gibt_jahr_und_spanne_unsicher():
    """Mit auch_schwach werden jahr/spanne ein Vorschlag, aber sicher=False."""
    anlass = _anlass("2019-11-25")
    jahr = ev.vorschlag_fuer(anlass, [ORDNER_ALBUM], auch_schwach=True)
    assert jahr["name"] == ORDNER_ALBUM and jahr["stufe"] == "jahr"
    assert jahr["sicher"] is False
    spanne = ev.vorschlag_fuer(_anlass("2019-07-01"), [ORDNER_ZEITRAUM],
                               auch_schwach=True)
    assert spanne["stufe"] == "spanne" and spanne["sicher"] is False
    assert "Spanne" in spanne["begruendung"]
    # Eine sichere Stufe bleibt auch mit auch_schwach sicher.
    sicher = ev.vorschlag_fuer(anlass, [ORDNER_BAND], auch_schwach=True)
    assert sicher["stufe"] == "monat" and sicher["sicher"] is True
    # ohne_jahr wird auch mit auch_schwach NICHT vorgeschlagen (harte Regel).
    assert ev.vorschlag_fuer(anlass, [ORDNER_PERSON], auch_schwach=True) is None
    assert ev.vorschlag_fuer(anlass, ["2018 Album"], auch_schwach=True) is None


def test_vorschlag_fuer_traegt_die_felder_des_kandidaten():
    """Der Vorschlag nennt Ordner, Stufe, Sicherheit und Beleg."""
    anlass = _anlass("2019-11-25", kacheln=["Bandname live"])
    vorschlag = ev.vorschlag_fuer(anlass, [ORDNER_BAND])
    assert sorted(vorschlag) == ["begruendung", "name", "sicher", "stufe",
                                "ueberlappung"]
    assert vorschlag["name"] == ORDNER_BAND
    assert vorschlag["ueberlappung"] == 1
    assert "Worttreffer" in vorschlag["begruendung"]


# ── hinweis_text ───────────────────────────────────────────────────────────

def test_hinweis_text_mit_und_ohne_vorschlag():
    """Je Anlass eine Klartextzeile: Datum, Thema, Vorschlag oder Neubau."""
    anlass = _anlass("2019-11-25")
    mit = ev.hinweis_text(anlass, [ORDNER_BAND, ORDNER_PERSON])
    assert mit == ("2019-11-25 Konzert und Buehne \u2192 Vorschlag "
                   "'2019_11 Bandname' (monat, Monat 11 und Jahr 2019 gleich)")
    ohne = ev.hinweis_text(anlass, [ORDNER_PERSON])
    assert ohne == ("2019-11-25 Konzert und Buehne \u2192 kein Vorschlag, "
                    "neuer Ordner")
    assert ev.hinweis_text(anlass, []) .endswith("kein Vorschlag, neuer Ordner")


def test_hinweis_text_ohne_datum_und_thema():
    """Fehlendes Datum/Thema wird benannt, nicht verschluckt (N7-Auflage)."""
    zeile = ev.hinweis_text({"thema": None, "datum": ""}, [])
    assert zeile == "? Ohne-Thema \u2192 kein Vorschlag, neuer Ordner"
    assert ev.OHNE_THEMA == "Ohne-Thema"
    assert ev.hinweis_text({"datum": "2019-11-25", "thema": None}, []) \
        == "2019-11-25 Ohne-Thema \u2192 kein Vorschlag, neuer Ordner"


def test_hinweis_text_jahr_ist_kein_vorschlag_ausser_mit_auch_schwach():
    """Ein reiner Jahr-Ordner ist kein Vorschlag — erst mit auch_schwach."""
    anlass = _anlass("2019-11-25")
    assert ev.hinweis_text(anlass, [ORDNER_ALBUM]) == (
        "2019-11-25 Konzert und Buehne \u2192 kein Vorschlag, neuer Ordner")
    zeile = ev.hinweis_text(anlass, [ORDNER_ALBUM], auch_schwach=True)
    assert "\u2192 Vorschlag '2019 Album' (jahr," in zeile
    # Ein Ordner ohne Jahr bleibt in beiden Faellen ohne Vorschlag.
    for auch_schwach in (False, True):
        assert ev.hinweis_text(anlass, [ORDNER_PERSON],
                               auch_schwach=auch_schwach).endswith(
            "kein Vorschlag, neuer Ordner")


# ── trefferquote ───────────────────────────────────────────────────────────

def test_trefferquote_feste_zeilen_und_zahlen():
    """Der Bericht hat feste Zeilen und stimmt fuer eine erfundene Menge."""
    bestand = {"kategorien": [
        _kategorie("Kategorie A", [ORDNER_BAND, ORDNER_ALBUM, ORDNER_PERSON]),
        _kategorie("Kategorie B", [], folderid=120),
    ]}
    zuordnung = {name: None for name in kat.BUCKETS}
    zuordnung[BUCKET_KONZERT] = "Kategorie A"
    anlaesse = [
        _anlass("2019-11-25"),     # -> Bandname (monat)
        _anlass("2019-11-25", titel="2019-11-25_Anlass-02"),   # -> Bandname
        _anlass("2016-07-01"),     # kein Kandidat -> ohne Vorschlag
    ]
    bericht = ev.trefferquote(anlaesse, bestand, zuordnung)
    assert bericht == "\n".join([
        "Anlaesse gesamt: 3",
        "Mit Vorschlag: 2",
        "Vorschlag Stufe tag: 0",
        "Vorschlag Stufe monat: 2",
        "Schwacher Hinweis Stufe jahr: 0",
        "Schwacher Hinweis Stufe spanne: 0",
        "Mit schwachem Hinweis: 0",
        "Ohne Vorschlag: 1",
        "Kategorie fehlt im Bestand: 0",
    ])
    # Deterministisch: zweimal derselbe Text.
    assert ev.trefferquote(anlaesse, bestand, zuordnung) == bericht


def test_trefferquote_trennt_vorschlag_und_schwachen_hinweis():
    """jahr/spanne stehen NICHT in der Vorschlagszahl, sondern als Hinweis."""
    bestand = {"kategorien": [
        _kategorie("Kategorie A", [ORDNER_BAND, ORDNER_ALBUM]),
    ]}
    zuordnung = {name: None for name in kat.BUCKETS}
    zuordnung[BUCKET_KONZERT] = "Kategorie A"
    anlaesse = [
        _anlass("2019-11-25"),     # -> Bandname (monat): Vorschlag
        _anlass("2019-05-02"),     # Monat weicht ab -> ORDNER_ALBUM (jahr)
    ]
    bericht = ev.trefferquote(anlaesse, bestand, zuordnung)
    assert bericht == "\n".join([
        "Anlaesse gesamt: 2",
        "Mit Vorschlag: 1",          # nur der monat-Treffer
        "Vorschlag Stufe tag: 0",
        "Vorschlag Stufe monat: 1",
        "Schwacher Hinweis Stufe jahr: 1",
        "Schwacher Hinweis Stufe spanne: 0",
        "Mit schwachem Hinweis: 1",
        "Ohne Vorschlag: 1",         # der jahr-Fall ist (streng) ohne Vorschlag
        "Kategorie fehlt im Bestand: 0",
    ])
    # Mit auch_schwach kommt eine zusaetzliche Zeile, die beide zusammen nennt.
    mit_schwach = ev.trefferquote(anlaesse, bestand, zuordnung,
                                  auch_schwach=True)
    assert "Mit Vorschlag (auch schwach): 2" in mit_schwach
    assert "Mit Vorschlag: 1\n" in mit_schwach + "\n"


def test_trefferquote_zaehlt_spanne_als_schwachen_hinweis():
    """Eine Spanne ohne Jahres-Treffer ist ein schwacher Hinweis, kein Vorschlag."""
    bestand = {"kategorien": [
        _kategorie("Kategorie A", [ORDNER_ZEITRAUM, ORDNER_ALBUM]),
    ]}
    zuordnung = {name: None for name in kat.BUCKETS}
    zuordnung[BUCKET_KONZERT] = "Kategorie A"
    anlaesse = [
        _anlass("2020-03-01"),     # 2020 in 2018-2021 -> spanne (schwach)
        _anlass("2019-11-25"),     # -> ORDNER_ALBUM (jahr)
    ]
    bericht = ev.trefferquote(anlaesse, bestand, zuordnung)
    assert "Mit Vorschlag: 0" in bericht
    assert "Schwacher Hinweis Stufe jahr: 1" in bericht
    assert "Schwacher Hinweis Stufe spanne: 1" in bericht
    assert "Mit schwachem Hinweis: 2" in bericht
    assert "Ohne Vorschlag: 2" in bericht


def test_trefferquote_zaehlt_fehlende_kategorie():
    """Ohne passende Kategorie im Bestand zaehlt der Anlass als 'fehlt'."""
    bestand = {"kategorien": [_kategorie("Kategorie B", [], folderid=120)]}
    zuordnung = {name: None for name in kat.BUCKETS}
    zuordnung[BUCKET_KONZERT] = None          # kein Zielordner gebunden
    bericht = ev.trefferquote([_anlass()], bestand, zuordnung)
    assert "Anlaesse gesamt: 1" in bericht
    assert "Mit Vorschlag: 0" in bericht
    assert "Ohne Vorschlag: 1" in bericht
    assert "Kategorie fehlt im Bestand: 1" in bericht
    # Ohne Zuordnung ist die Kategorie nicht bestimmbar -> ehrlich gezaehlt.
    bericht = ev.trefferquote([_anlass()], bestand)
    assert "Kategorie fehlt im Bestand: 1" in bericht
    # Leere Eingabe: ehrliche Nullen.
    leer = ev.trefferquote([], {})
    assert "Anlaesse gesamt: 0" in leer and "Ohne Vorschlag: 0" in leer


# ── anlaesse_laden ─────────────────────────────────────────────────────────

def test_anlaesse_laden_aus_jsonl_mit_nachgelesenen_kacheln(tmp_path):
    """themen.jsonl lesen und die Kacheln aus der Anlass-Datei nachholen."""
    themen_ordner = tmp_path / "themen" / "2019"
    themen_ordner.mkdir(parents=True)
    anlass_datei = themen_ordner / "2019-11-25_Anlass-01.json"
    anlass_datei.write_text(json.dumps({
        "datum": "2019-11-25", "jahr": 2019, "titel": "2019-11-25_Anlass-01",
        "thema": THEMA_KONZERT,
        "kacheln": [{"kurz": "Bandname auf der Buehne"}, {"kurz": "Beifall"}],
    }, ensure_ascii=False), encoding="utf-8")
    pfad = _jsonl_schreiben(tmp_path / "themen.jsonl", [
        {"datum": "2019-11-25", "jahr": "2019", "thema": THEMA_KONZERT,
         "titel": "2019-11-25_Anlass-01", "datei": str(anlass_datei)}])

    anlaesse = ev.anlaesse_laden(pfad)

    assert len(anlaesse) == 1
    assert anlass_datei.name.endswith(".json")
    assert ev.anlass_datum(anlaesse[0]) == "2019-11-25"
    assert ev.anlass_thema(anlaesse[0]) == THEMA_KONZERT
    assert [k["kurz"] for k in anlaesse[0]["kacheln"]] == \
        ["Bandname auf der Buehne", "Beifall"]


def test_anlaesse_laden_aus_ordner_sortiert_nach_datum(tmp_path):
    """Auch themen/<Jahr>/*.json geht — sortiert nach Datum, deterministisch."""
    for jahr, tag in (("2020", "05"), ("2019", "25")):
        d = tmp_path / "themen" / jahr
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{jahr}-11-{tag}_Anlass-01.json").write_text(json.dumps({
            "datum": f"{jahr}-11-{tag}", "jahr": int(jahr), "thema": THEMA_KONZERT,
            "titel": f"{jahr}-11-{tag}_Anlass-01", "kacheln": [],
        }, ensure_ascii=False), encoding="utf-8")
    anlaesse = ev.anlaesse_laden(str(tmp_path / "themen"))
    assert [ev.anlass_datum(a) for a in anlaesse] == ["2019-11-25", "2020-11-05"]
    assert ev.anlaesse_laden(str(tmp_path / "themen")) == anlaesse


def test_anlaesse_laden_fehlender_pfad_ist_klartextfehler(tmp_path):
    """Ein fehlender Pfad ergibt eine deutsche Meldung statt eines Absturzes."""
    with pytest.raises(ev.EventFehler) as fehler:
        ev.anlaesse_laden(str(tmp_path / "gibtsnicht.jsonl"))
    assert "nicht gefunden" in str(fehler.value)
    with pytest.raises(ev.EventFehler):
        ev.anlaesse_laden("")
    # Kaputte Zeilen werden uebergangen und gezaehlt, nicht verschluckt.
    pfad = tmp_path / "themen.jsonl"
    pfad.write_text("{kaputt\n" + json.dumps(_anlass()), encoding="utf-8")
    anlaesse = ev.anlaesse_laden(str(pfad))
    assert len(anlaesse) == 1


# ── Kategorie eines Anlasses ───────────────────────────────────────────────

def test_kategorie_fuer_anlass_ueber_thema_und_bucket(tmp_path):
    """Thema -> Bucket -> echter Ordner ueber die Zuordnung."""
    kat_pfad, zu_pfad, _ = _umgebung(tmp_path)
    bestand, zuordnung = ev.bestand_und_zuordnung(kat_pfad, zu_pfad)
    assert ev.bucket_fuer_thema(THEMA_KONZERT) == BUCKET_KONZERT
    assert ev.kategorie_fuer_anlass(_anlass(), zuordnung) == "Kategorie A"
    # Ein ausdrueckliches Feld am Anlass hat Vorrang.
    assert ev.kategorie_fuer_anlass({"kategorie": "Kategorie B"}, zuordnung) \
        == "Kategorie B"
    # Ohne Thema keine Kategorie (nicht geraten).
    assert ev.kategorie_fuer_anlass({"thema": None}, zuordnung) is None
    assert ev.kategorie_fuer_anlass(_anlass(), None) is None
    assert ev.unterordner_von("Kategorie A", bestand) == [
        ORDNER_BAND, ORDNER_ALBUM, ORDNER_PERSON]
    assert ev.unterordner_von("Kategorie B", bestand) == []
    assert ev.unterordner_von("Gibtsnicht", bestand) is None
    assert ev.unterordner_von(None, bestand) is None


# ── vorschlaege_schreiben ──────────────────────────────────────────────────

def test_vorschlaege_schreiben_repo_schutz(tmp_path, capsys):
    """Ein Ziel IM Repo wird verweigert — es wird nichts angelegt."""
    ziel = WERKZEUG.parent / "tmp-vorschlaege.json"
    assert not ziel.exists()
    with pytest.raises(SystemExit) as abbruch:
        ev.vorschlaege_schreiben(str(ziel), [], trocken=False)
    assert abbruch.value.code == 2
    meldung = capsys.readouterr().out
    assert "IM Repo" in meldung and "NICHTS geschrieben" in meldung
    assert not ziel.exists(), "im Repo wurde trotz Abbruch etwas angelegt"
    # Vertauschte Trenner/Gross-Klein werden trotzdem als Repo erkannt.
    verdreht = str(REPO).upper() + "\\tools\\foto_sortierung\\TMP.json"
    with pytest.raises(SystemExit) as abbruch:
        ev.vorschlaege_schreiben(verdreht, [])
    assert abbruch.value.code == 2
    capsys.readouterr()


def test_vorschlaege_schreiben_und_idempotenz(tmp_path, capsys):
    """Schreiben ausserhalb des Repos; zweiter Lauf laesst die Datei byte-identisch."""
    ziel = tmp_path / "vorschlaege.json"
    daten = [{"anlass": "2019-11-25_Anlass-01", "vorschlag": ORDNER_BAND}]

    erster = ev.vorschlaege_schreiben(str(ziel), daten, trocken=False)
    assert erster["geschrieben"] is True and erster["unveraendert"] is False
    assert erster["anzahl"] == 1 and erster["ziel"] == str(ziel)
    vorher = _md5(ziel)
    inhalt = json.loads(ziel.read_text(encoding="utf-8"))
    assert inhalt["vorschlaege"] == daten and "stand" in inhalt

    zweiter = ev.vorschlaege_schreiben(str(ziel), daten, trocken=False)
    assert zweiter["geschrieben"] is False and zweiter["unveraendert"] is True
    assert _md5(ziel) == vorher, "die Datei wurde beim zweiten Lauf geaendert"
    assert "unveraendert" in capsys.readouterr().out
    # Der Zeitstempel bleibt stehen (nur die Uhr darf die Datei nicht aendern).
    assert json.loads(ziel.read_text(encoding="utf-8"))["stand"] == inhalt["stand"]


def test_vorschlaege_schreiben_erkennt_echte_aenderung(tmp_path):
    """Gegenprobe: anderer Inhalt -> die Datei wird neu geschrieben."""
    ziel = tmp_path / "vorschlaege.json"
    ev.vorschlaege_schreiben(str(ziel), [{"anlass": "a"}], trocken=False)
    vorher = _md5(ziel)
    ergebnis = ev.vorschlaege_schreiben(str(ziel), [{"anlass": "b"}],
                                       trocken=False)
    assert ergebnis["geschrieben"] is True
    assert _md5(ziel) != vorher
    assert json.loads(ziel.read_text(encoding="utf-8"))["vorschlaege"] == \
        [{"anlass": "b"}]


def test_vorschlaege_schreiben_trockenlauf_schreibt_nichts(tmp_path, monkeypatch):
    """trocken=True (Standard): kein Schreiben — ein Schreibversuch muss auffallen."""
    monkeypatch.setattr(ev, "_schreibe_atomar", Stolperfalle())
    ziel = tmp_path / "vorschlaege.json"
    ergebnis = ev.vorschlaege_schreiben(str(ziel), [{"anlass": "a"}])
    assert ergebnis["trocken"] is True and ergebnis["geschrieben"] is False
    assert not ziel.exists(), "es wurde trotz Trockenlauf geschrieben"
    assert not (tmp_path / "vorschlaege.json.tmp").exists()


# ── vorschlaege_bauen und CLI ──────────────────────────────────────────────

def test_vorschlaege_bauen_je_anlass_eine_zeile(tmp_path):
    """Je Anlass eine Vorschlagszeile, sortiert nach Datum und Anlass."""
    kat_pfad, zu_pfad, _ = _umgebung(tmp_path)
    bestand, zuordnung = ev.bestand_und_zuordnung(kat_pfad, zu_pfad)
    anlaesse = [_anlass("2020-11-05"), _anlass("2019-11-25"),
                _anlass("2019-11-25", titel="2019-11-25_Anlass-02"),
                _anlass("2016-07-01")]
    zeilen = ev.vorschlaege_bauen(anlaesse, bestand, zuordnung)
    assert [z["datum"] for z in zeilen] == ["2016-07-01", "2019-11-25",
                                           "2019-11-25", "2020-11-05"]
    assert zeilen[0]["vorschlag"] is None and zeilen[0]["stufe"] is None
    assert zeilen[1]["vorschlag"] == ORDNER_BAND and zeilen[1]["sicher"] is True
    assert zeilen[1]["kategorie"] == "Kategorie A"
    assert zeilen[1]["kategorie_im_bestand"] is True
    for zeile in zeilen:
        assert zeile["thema"] and zeile["begruendung"].strip()


def test_cli_zeigen_zeigt_bericht_ohne_zu_schreiben(tmp_path, capsys,
                                                    monkeypatch):
    """--zeigen liest die lokalen Dateien und schreibt NICHTS."""
    monkeypatch.setattr(ev, "_schreibe_atomar", Stolperfalle())
    kat_pfad, zu_pfad, themen_pfad = _umgebung(tmp_path)
    ziel = tmp_path / "vorschlaege.json"
    code = ev.main(["--zeigen", "--stichprobe", "2",
                    "--kategorien-pfad", kat_pfad, "--zuordnung-pfad", zu_pfad,
                    "--themen-pfad", themen_pfad,
                    "--vorschlaege-pfad", str(ziel)])
    ausgabe = capsys.readouterr().out
    assert code == 0
    assert "Kategorien im Bestand: 2" in ausgabe
    assert "Unterordner gesamt: 3" in ausgabe
    assert "Anlaesse gesamt: 1" in ausgabe
    assert "Mit Vorschlag: 1" in ausgabe
    assert "Vorschlag Stufe monat: 1" in ausgabe
    assert f"\u2192 Vorschlag '{ORDNER_BAND}'" in ausgabe
    assert "Ohne --schreiben wurde NICHTS geschrieben." in ausgabe
    assert not ziel.exists()


def test_cli_mit_schreiben_legt_die_vorschlagsliste_an(tmp_path, capsys):
    """--schreiben schreibt die Liste (atomar) und ist beim zweiten Lauf still."""
    kat_pfad, zu_pfad, themen_pfad = _umgebung(tmp_path)
    ziel = tmp_path / "vorschlaege.json"
    args = ["--schreiben", "--stichprobe", "0",
            "--kategorien-pfad", kat_pfad, "--zuordnung-pfad", zu_pfad,
            "--themen-pfad", themen_pfad, "--vorschlaege-pfad", str(ziel)]

    code = ev.main(list(args))
    ausgabe = capsys.readouterr().out
    assert code == 0
    assert "Zeilen in der Vorschlagsliste: 1" in ausgabe
    daten = json.loads(ziel.read_text(encoding="utf-8"))
    assert len(daten["vorschlaege"]) == 1
    assert daten["vorschlaege"][0]["vorschlag"] == ORDNER_BAND

    vorher = _md5(ziel)
    code = ev.main(list(args))
    assert code == 0
    assert "unveraendert" in capsys.readouterr().out
    assert _md5(ziel) == vorher


def test_vorschlaege_bauen_jahr_nur_mit_auch_schwach(tmp_path):
    """Ohne auch_schwach kein Vorschlag fuer einen Jahr-Ordner; mit, unsicher."""
    kat_pfad, zu_pfad, _ = _umgebung(tmp_path, unterordner=(ORDNER_ALBUM,))
    bestand, zuordnung = ev.bestand_und_zuordnung(kat_pfad, zu_pfad)
    anlaesse = [_anlass("2019-11-25")]

    streng = ev.vorschlaege_bauen(anlaesse, bestand, zuordnung)
    assert streng[0]["vorschlag"] is None and streng[0]["stufe"] is None
    assert streng[0]["sicher"] is False

    schwach = ev.vorschlaege_bauen(anlaesse, bestand, zuordnung,
                                   auch_schwach=True)
    assert schwach[0]["vorschlag"] == ORDNER_ALBUM
    assert schwach[0]["stufe"] == "jahr" and schwach[0]["sicher"] is False


def test_cli_auch_schwach_schaltet_schwache_stufen_frei(tmp_path, capsys):
    """--auch-schwach macht aus dem schwachen Hinweis einen (unsicheren) Vorschlag."""
    kat_pfad, zu_pfad, themen_pfad = _umgebung(tmp_path,
                                               unterordner=(ORDNER_ALBUM,))
    gemeinsam = ["--kategorien-pfad", kat_pfad, "--zuordnung-pfad", zu_pfad,
                 "--themen-pfad", themen_pfad, "--stichprobe", "1"]

    assert ev.main(["--zeigen"] + gemeinsam) == 0
    streng = capsys.readouterr().out
    assert "Mit Vorschlag: 0" in streng
    assert "Schwacher Hinweis Stufe jahr: 1" in streng
    assert "kein Vorschlag, neuer Ordner" in streng
    assert "auch schwach" not in streng

    assert ev.main(["--auch-schwach", "--zeigen"] + gemeinsam) == 0
    schwach = capsys.readouterr().out
    assert "Mit Vorschlag: 0" in schwach              # die strenge Zahl bleibt
    assert "Mit Vorschlag (auch schwach): 1" in schwach
    assert f"\u2192 Vorschlag '{ORDNER_ALBUM}' (jahr," in schwach


def test_cli_fehlende_dateien_exit_2(tmp_path, capsys):
    """Fehlende Bestands-/Zuordnungs-/Themendatei: klare Meldung, Exit 2."""
    kat_pfad, zu_pfad, themen_pfad = _umgebung(tmp_path)
    code = ev.main(["--zeigen", "--kategorien-pfad", str(tmp_path / "weg.json"),
                    "--zuordnung-pfad", zu_pfad, "--themen-pfad", themen_pfad])
    assert code == 2
    assert "nicht gefunden" in capsys.readouterr().out

    code = ev.main(["--zeigen", "--kategorien-pfad", kat_pfad,
                    "--zuordnung-pfad", str(tmp_path / "z-weg.json"),
                    "--themen-pfad", themen_pfad])
    assert code == 2
    assert "nicht gefunden" in capsys.readouterr().out

    code = ev.main(["--zeigen", "--kategorien-pfad", kat_pfad,
                    "--zuordnung-pfad", zu_pfad,
                    "--themen-pfad", str(tmp_path / "t-weg.jsonl")])
    assert code == 2
    assert "nicht gefunden" in capsys.readouterr().out


# ── Hygiene: keine pCloud-Funktion, kein Loeschen, nichts im Repo ──────────

def test_quelle_ruft_keine_pcloud_funktion_auf():
    """Der Quelltext enthaelt keinen pCloud-Aufruf und keinen Loeschbefehl."""
    quelle = WERKZEUG.read_text(encoding="utf-8")
    for verboten in ("pcloud_service", "service.liste", "listfolder",
                     "getthumbs", "thumb(", "deletefile", "deletefolder",
                     "delete_file", "delete_folder", "shutil.rmtree",
                     "unlink(", "os.remove", "os.rename", "shutil.move"):
        assert verboten not in quelle, verboten
    # Und die Gegenprobe: das Nachbarmodul liefert die Schutzfunktionen.
    assert "_pruefe_ziel_ausserhalb_repo" in quelle
    assert "_schreibe_atomar" in quelle


def test_lauf_legt_nichts_im_repo_an(tmp_path, capsys):
    """Ein ganzer CLI-Lauf schreibt nur nach tmp_path — nie ins Repo."""
    werkzeug_ordner = WERKZEUG.parent
    vorher = {str(d): _md5(d) for d in sorted(werkzeug_ordner.rglob("*"))
              if d.is_file()}
    kat_pfad, zu_pfad, themen_pfad = _umgebung(tmp_path)
    ziel = tmp_path / "vorschlaege.json"
    code = ev.main(["--schreiben", "--stichprobe", "1",
                    "--kategorien-pfad", kat_pfad, "--zuordnung-pfad", zu_pfad,
                    "--themen-pfad", themen_pfad,
                    "--vorschlaege-pfad", str(ziel)])
    capsys.readouterr()
    nachher = {str(d): _md5(d) for d in sorted(werkzeug_ordner.rglob("*"))
               if d.is_file()}
    assert code == 0
    assert nachher == vorher
    assert ziel.is_file()


def test_testdatei_benutzt_nur_tmp_pfade():
    """Keine echten Datenpfade in der Testdatei (Privat-Regel des Auftrags)."""
    quelle = Path(__file__).read_text(encoding="utf-8")
    assert "tmp_path" in quelle
    # Der private Datenordner des Nutzers wird hier nicht genannt; alle Pfade
    # kommen aus tmp_path. Geprueft wird auf die Windows-Benutzerwurzel.
    wurzel = "C:" + chr(92) + "Users"
    assert wurzel not in quelle, wurzel
    assert wurzel.replace(chr(92), "/") not in quelle
