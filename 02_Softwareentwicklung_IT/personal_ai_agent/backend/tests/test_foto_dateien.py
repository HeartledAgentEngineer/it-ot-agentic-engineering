"""Pruefungen fuer ``foto_dateien.py`` (Nachtlauf-Schritt N13a, Teil A, 28.09.2026).

Alles OHNE Netz und ohne Bild: das Werkzeug liest nur den lokalen Sortierplan
bzw. erfundene Plandaten; Dateien gehen nach ``tmp_path``. Geprueft wird das
eingefrorene Schema der Kennungsdatei, die Zaehlregeln, die feste Sortierung,
das atomare Schreiben (nur ausserhalb des Repos), die Idempotenz und die
Trockenlauf-Garantien im Quelltext.

**Nur erfundene Beispielnamen und erfundene Kennungen** — die echten Event-,
Ordner- und Dateinamen sowie die echten Kennungen liegen ausserhalb des Repos
und kommen hier nicht vor.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_foto_dateien.py -q
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "foto_dateien.py"

STAND = "2026-09-28T09:40:00+02:00"
PLAN_STAND = "2026-09-27T13:49:46+02:00"

# Erfundene Beispielwerte.
KATEGORIE = "Beispiel-Kategorie"
KATEGORIE_ZWEI = "Beispiel-Kategorie-Zwei"
EVENT = "2021_07 Beispiel-Event"
EVENT_ZWEI = "2020_03 Beispiel-Event-Zwei"
NAME = "Beispiel-01.jpg"
NAME_ZWEI = "Beispiel-02.jpg"
KENNUNG = 111111111
KENNUNG_ZWEI = 222222222


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


fd = _laden(WERKZEUG, "foto_dateien")

# Die Schluessel des eingefrorenen Schemas (Teil B verlaesst sich darauf).
SCHEMA_SCHLUESSEL = ("art", "version", "stand", "plan_stand", "zahlen", "events")
ZAHLEN_SCHLUESSEL = {"events", "dateien", "ohne_kennung", "kategorien", "jahre"}
EVENT_SCHLUESSEL = {"jahr", "kategorie", "event", "anzahl", "dateien"}
DATEI_SCHLUESSEL = {"datei_id", "name"}


# ── kleine Helfer ──────────────────────────────────────────────────────────

def _zug(jahr=2021, kategorie=KATEGORIE, event=EVENT, von_name=NAME,
         fileid=KENNUNG, **rest) -> dict:
    zug = {"thema_quelle": "2021-07-01_Anlass-01", "jahr": jahr,
           "kategorie": kategorie, "event": event, "event_quelle": "neu",
           "von_ordner": "P:/Beispiel/Ordner", "von_name": von_name,
           "ziel_pfad": "Agent/Fotos/2021/Beispiel", "fileid": fileid,
           "vorbuchung": None}
    zug.update(rest)
    return zug


def _plan(zuege=(), stand=PLAN_STAND, **rest) -> dict:
    plan = {"trocken": True, "anlaesse": [], "ordner": [], "zuege": list(zuege),
            "zusammenfassung": {}, "stand": stand}
    plan.update(rest)
    return plan


def _bauen(zuege=(), **rest) -> dict:
    return fd.dateien_bauen(_plan(zuege, **rest), stand=STAND)


def _plan_datei(tmp_path: Path, plan=None) -> Path:
    pfad = tmp_path / "sortierplan.json"
    pfad.write_text(json.dumps(plan if plan is not None else _plan([_zug()]),
                               ensure_ascii=False), encoding="utf-8")
    return pfad


def _datei_hash(pfad: Path) -> str:
    return hashlib.md5(pfad.read_bytes()).hexdigest()


def _alle_kennungen(daten: dict) -> list:
    return sorted(datei["datei_id"] for eintrag in daten["events"]
                  for datei in eintrag["dateien"])


class Schreiber:
    """Ein Aufruf, der niemals passieren darf (reine Funktion ohne I/O)."""

    def __call__(self, *args, **kwargs):
        raise AssertionError("Es wurde eine Datei geoeffnet, obwohl nichts "
                             "geoeffnet werden darf!")


# ── Schema und Konstanten ──────────────────────────────────────────────────

def test_version_und_art_sind_fest():
    assert fd.DATEIEN_VERSION == 1
    assert fd.DATEIEN_ART == "foto_dateien"


def test_standard_ausgabe_zeigt_auf_die_kennungsdatei():
    assert fd.STANDARD_AUSGABE.endswith("fotos_dateien.json")
    assert "foto_sortierung" in fd.STANDARD_AUSGABE


def test_standard_plan_zeigt_auf_den_sortierplan():
    assert fd.STANDARD_PLAN.endswith("sortierplan.json")


def test_bauen_liefert_die_schema_schluessel():
    assert set(_bauen([_zug()])) == set(SCHEMA_SCHLUESSEL)


def test_schema_schluessel_reihenfolge_ist_fest():
    assert tuple(_bauen([_zug()])) == SCHEMA_SCHLUESSEL


def test_zahlen_hat_genau_die_schema_schluessel():
    assert set(_bauen([_zug()])["zahlen"]) == ZAHLEN_SCHLUESSEL


def test_event_zeile_hat_die_schema_schluessel():
    assert set(_bauen([_zug()])["events"][0]) == EVENT_SCHLUESSEL


def test_datei_eintrag_hat_die_schema_schluessel():
    eintrag = _bauen([_zug()])["events"][0]["dateien"][0]
    assert set(eintrag) == DATEI_SCHLUESSEL


def test_exportierte_schluessel_konstanten_passen_zum_schema():
    assert fd.SCHLUESSEL_EVENT == ("jahr", "kategorie", "event", "anzahl", "dateien")
    assert fd.SCHLUESSEL_DATEI == ("datei_id", "name")
    assert fd.ZAHLEN_SCHLUESSEL == ("events", "dateien", "ohne_kennung",
                                    "kategorien", "jahre")


def test_listen_schluessel_stimmen_mit_den_konstanten():
    daten = _bauen([_zug()])
    assert tuple(daten["events"][0]) == fd.SCHLUESSEL_EVENT
    assert tuple(daten["events"][0]["dateien"][0]) == fd.SCHLUESSEL_DATEI


def test_version_und_art_stehen_in_der_ausgabe():
    daten = _bauen([_zug()])
    assert daten["version"] == 1
    assert daten["art"] == "foto_dateien"


# ── Stand ──────────────────────────────────────────────────────────────────

def test_stand_wird_uebernommen():
    assert _bauen([_zug()])["stand"] == STAND


def test_stand_ohne_angabe_wird_gefuellt():
    daten = fd.dateien_bauen(_plan([_zug()]))
    assert isinstance(daten["stand"], str)
    assert daten["stand"].strip()
    assert "T" in daten["stand"]


def test_stand_muss_text_sein():
    with pytest.raises(ValueError):
        fd.dateien_bauen(_plan([_zug()]), stand=12345)


def test_leerer_stand_ist_fehler():
    with pytest.raises(ValueError):
        fd.dateien_bauen(_plan([_zug()]), stand="   ")


def test_plan_stand_wird_uebernommen():
    assert _bauen([_zug()])["plan_stand"] == PLAN_STAND


def test_plan_stand_fehlt_dann_null():
    daten = _bauen([_zug()], stand=None)
    assert daten["plan_stand"] is None


def test_plan_stand_ist_kein_text_dann_null():
    daten = _bauen([_zug()], stand=1234)
    assert daten["plan_stand"] is None


# ── Reine Funktion (kein Datei-, kein Netzzugriff) ─────────────────────────

def test_bauen_oeffnet_keine_datei(monkeypatch, capsys):
    verboten = Schreiber()
    monkeypatch.setattr("builtins.open", verboten)
    daten = fd.dateien_bauen(_plan([_zug()]), stand=STAND)
    assert daten["zahlen"]["dateien"] == 1
    assert capsys.readouterr().out == ""


def test_bauen_oeffnet_keine_datei_ohne_monkeypatch(monkeypatch):
    verboten = Schreiber()
    monkeypatch.setattr("builtins.open", verboten)
    daten = fd.dateien_bauen(_plan([_zug()]), stand=STAND)
    assert daten["zahlen"]["dateien"] == 1


def test_bauen_veraendert_den_plan_nicht():
    plan = _plan([_zug(), _zug(fileid=KENNUNG_ZWEI, von_name=NAME_ZWEI)])
    vorher = json.dumps(plan, ensure_ascii=False, sort_keys=True)
    fd.dateien_bauen(plan, stand=STAND)
    assert json.dumps(plan, ensure_ascii=False, sort_keys=True) == vorher


def test_bauen_zweimal_ist_gleich():
    plan = _plan([_zug(), _zug(jahr=2020, event=EVENT_ZWEI, fileid=KENNUNG_ZWEI)])
    erst = json.dumps(fd.dateien_bauen(plan, stand=STAND), sort_keys=True)
    zweit = json.dumps(fd.dateien_bauen(plan, stand=STAND), sort_keys=True)
    assert erst == zweit


# ── Zaehlregeln ────────────────────────────────────────────────────────────

def test_zug_mit_gueltiger_kennung_wird_aufgenommen():
    daten = _bauen([_zug()])
    assert daten["zahlen"]["events"] == 1
    assert daten["zahlen"]["dateien"] == 1
    assert daten["zahlen"]["ohne_kennung"] == 0
    assert daten["events"][0]["dateien"][0] == {"datei_id": KENNUNG, "name": NAME}


def test_zug_ohne_kennung_wird_gezaehlt_nicht_aufgenommen():
    daten = _bauen([_zug(), _zug(fileid=None, von_name=NAME_ZWEI)])
    assert daten["zahlen"]["dateien"] == 1
    assert daten["zahlen"]["ohne_kennung"] == 1
    assert _alle_kennungen(daten) == [KENNUNG]


def test_zug_ohne_jahr_wird_gezaehlt():
    daten = _bauen([_zug(jahr=None)])
    assert daten["zahlen"]["dateien"] == 0
    assert daten["zahlen"]["ohne_kennung"] == 1
    assert daten["events"] == []


def test_kennung_als_text_wird_gelesen():
    daten = _bauen([_zug(fileid="987654321")])
    assert daten["events"][0]["dateien"][0]["datei_id"] == 987654321


def test_bool_ist_keine_kennung():
    daten = _bauen([_zug(fileid=True)])
    assert daten["zahlen"]["ohne_kennung"] == 1
    assert daten["zahlen"]["dateien"] == 0


def test_unsinnige_kennung_wird_gezaehlt():
    daten = _bauen([_zug(fileid="keine Zahl")])
    assert daten["zahlen"]["ohne_kennung"] == 1


def test_nicht_woerterbuch_zug_wird_gezaehlt():
    daten = _bauen([_zug(), "kaputt", 42, None])
    assert daten["zahlen"]["dateien"] == 1
    assert daten["zahlen"]["ohne_kennung"] == 3


def test_dateien_plus_ohne_kennung_ist_die_zugzahl():
    zuege = [_zug(), _zug(fileid=KENNUNG_ZWEI, von_name=NAME_ZWEI),
             _zug(fileid=None), _zug(jahr="x")]
    daten = _bauen(zuege)
    assert daten["zahlen"]["dateien"] + daten["zahlen"]["ohne_kennung"] == len(zuege)


def test_anzahl_ist_die_laenge_der_liste():
    daten = _bauen([_zug(), _zug(fileid=KENNUNG_ZWEI, von_name=NAME_ZWEI)])
    for eintrag in daten["events"]:
        assert eintrag["anzahl"] == len(eintrag["dateien"])


def test_events_zaehlt_verschiedene_tripel():
    zuege = [_zug(), _zug(fileid=KENNUNG_ZWEI, von_name=NAME_ZWEI)]
    daten = _bauen(zuege)
    assert daten["zahlen"]["events"] == 1
    assert daten["events"][0]["anzahl"] == 2


def test_gleicher_eventname_in_anderem_jahr_ist_ein_neues_event():
    daten = _bauen([_zug(jahr=2021), _zug(jahr=2020, fileid=KENNUNG_ZWEI)])
    assert daten["zahlen"]["events"] == 2


def test_gleicher_eventname_in_anderer_kategorie_ist_ein_neues_event():
    daten = _bauen([_zug(kategorie=KATEGORIE),
                    _zug(kategorie=KATEGORIE_ZWEI, fileid=KENNUNG_ZWEI)])
    assert daten["zahlen"]["events"] == 2


def test_gleiche_kennung_zweimal_zaehlt_zweimal():
    """Jeder Zug zaehlt: zwei Zuege derselben Datei sind zwei Eintraege."""
    daten = _bauen([_zug(), _zug()])
    assert daten["events"][0]["anzahl"] == 2
    assert _alle_kennungen(daten) == [KENNUNG, KENNUNG]


def test_kategorien_und_jahre_zaehlen_verschiedene_werte():
    zuege = [_zug(kategorie=KATEGORIE, jahr=2021),
             _zug(kategorie=KATEGORIE_ZWEI, jahr=2020, fileid=KENNUNG_ZWEI),
             _zug(kategorie=KATEGORIE_ZWEI, jahr=2020, event=EVENT_ZWEI,
                  fileid=123)]
    daten = _bauen(zuege)
    assert daten["zahlen"]["kategorien"] == 2
    assert daten["zahlen"]["jahre"] == 2


def test_kennungen_werden_nicht_erfunden():
    zuege = [_zug(), _zug(fileid=KENNUNG_ZWEI, von_name=NAME_ZWEI),
             _zug(fileid=555)]
    daten = _bauen(zuege)
    assert _alle_kennungen(daten) == sorted([KENNUNG, KENNUNG_ZWEI, 555])


def test_leerer_plan_ergibt_null_zahlen():
    daten = _bauen([])
    assert daten["events"] == []
    assert daten["zahlen"] == {"events": 0, "dateien": 0, "ohne_kennung": 0,
                               "kategorien": 0, "jahre": 0}


# ── Sortierung (macht die Datei reproduzierbar) ────────────────────────────

def test_events_sind_nach_jahr_absteigend_dann_nach_event():
    zuege = [_zug(jahr=2019, event="2019-01 B-Event"),
             _zug(jahr=2021, event="2021-01 Z-Event", fileid=KENNUNG_ZWEI),
             _zug(jahr=2019, event="2019-01 A-Event", fileid=333)]
    daten = _bauen(zuege)
    assert [(e["jahr"], e["event"]) for e in daten["events"]] == [
        (2021, "2021-01 Z-Event"),
        (2019, "2019-01 A-Event"),
        (2019, "2019-01 B-Event"),
    ]


def test_dateien_sind_nach_name_sortiert():
    zuege = [_zug(von_name="Beispiel-B.jpg", fileid=3),
             _zug(von_name="Beispiel-A.jpg", fileid=1),
             _zug(von_name="Beispiel-C.jpg", fileid=2)]
    daten = _bauen(zuege)
    assert [d["name"] for d in daten["events"][0]["dateien"]] == [
        "Beispiel-A.jpg", "Beispiel-B.jpg", "Beispiel-C.jpg"]


def test_dateien_gleichstand_wird_nach_kennung_sortiert():
    zuege = [_zug(von_name=NAME, fileid=99), _zug(von_name=NAME, fileid=11)]
    daten = _bauen(zuege)
    assert [d["datei_id"] for d in daten["events"][0]["dateien"]] == [11, 99]


# ── Ungueltiger Plan ──────────────────────────────────────────────────────

def test_plan_ohne_zuege_ist_fehler():
    with pytest.raises(ValueError) as fehler:
        fd.dateien_bauen({}, stand=STAND)
    assert "zuege" in str(fehler.value)


def test_plan_kein_woerterbuch_ist_fehler():
    for wert in (None, [], "Plan", 42):
        with pytest.raises(ValueError):
            fd.dateien_bauen(wert, stand=STAND)


def test_zuege_keine_liste_ist_fehler():
    with pytest.raises(ValueError) as fehler:
        fd.dateien_bauen({"zuege": {"a": 1}}, stand=STAND)
    assert "Liste" in str(fehler.value)


def test_minimaler_plan_ist_erlaubt():
    daten = fd.dateien_bauen({"zuege": []}, stand=STAND)
    assert daten["zahlen"]["dateien"] == 0
    assert daten["plan_stand"] is None


# ── Plan lesen ────────────────────────────────────────────────────────────

def test_plan_laden_liest_das_woerterbuch(tmp_path):
    plan = fd.plan_laden(str(_plan_datei(tmp_path)))
    assert plan["zuege"][0]["fileid"] == KENNUNG


def test_plan_laden_fehlende_datei_ist_klartextfehler(tmp_path):
    with pytest.raises(ValueError) as fehler:
        fd.plan_laden(str(tmp_path / "gibtsnicht.json"))
    assert "nicht gefunden" in str(fehler.value)


def test_plan_laden_ohne_pfad_ist_klartextfehler():
    with pytest.raises(ValueError) as fehler:
        fd.plan_laden("")
    assert "Kein Pfad" in str(fehler.value)


def test_plan_laden_kaputtes_json_ist_klartextfehler(tmp_path):
    pfad = tmp_path / "krumm.json"
    pfad.write_text("{das ist kein json", encoding="utf-8")
    with pytest.raises(ValueError) as fehler:
        fd.plan_laden(str(pfad))
    assert "gueltiges JSON" in str(fehler.value)


def test_plan_laden_liste_ist_klartextfehler(tmp_path):
    pfad = tmp_path / "liste.json"
    pfad.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError) as fehler:
        fd.plan_laden(str(pfad))
    assert "Woerterbuch" in str(fehler.value)


# ── Kennungsdatei lesen und schreiben ─────────────────────────────────────

def test_dateien_laden_liest_zurueck(tmp_path):
    ziel = tmp_path / "d.json"
    fd.dateien_schreiben(str(ziel), _bauen([_zug()]))
    daten = fd.dateien_laden(str(ziel))
    assert daten["art"] == "foto_dateien"
    assert daten["zahlen"]["dateien"] == 1


def test_dateien_laden_fehlende_datei_ist_klartextfehler(tmp_path):
    with pytest.raises(ValueError) as fehler:
        fd.dateien_laden(str(tmp_path / "gibtsnicht.json"))
    assert "nicht gefunden" in str(fehler.value)


def test_dateien_laden_ohne_pfad_ist_klartextfehler():
    with pytest.raises(ValueError) as fehler:
        fd.dateien_laden("   ")
    assert "Kein Pfad" in str(fehler.value)


def test_schreiben_legt_die_datei_an_und_gibt_den_pfad_zurueck(tmp_path):
    ziel = tmp_path / "d.json"
    zurueck = fd.dateien_schreiben(str(ziel), _bauen([_zug()]))
    assert zurueck == str(ziel)
    assert ziel.is_file()


def test_schreiben_laesst_keine_temp_datei_zurueck(tmp_path):
    ziel = tmp_path / "d.json"
    fd.dateien_schreiben(str(ziel), _bauen([_zug()]))
    assert list(tmp_path.glob("*.tmp")) == []


def test_schreiben_inhalt_ist_gueltiges_json_mit_schema(tmp_path):
    ziel = tmp_path / "d.json"
    fd.dateien_schreiben(str(ziel), _bauen([_zug()]))
    daten = json.loads(ziel.read_text(encoding="utf-8"))
    assert set(daten) == set(SCHEMA_SCHLUESSEL)
    assert daten["zahlen"]["events"] == 1
    assert daten["events"][0]["dateien"][0]["datei_id"] == KENNUNG


def test_schreiben_zweiter_lauf_ist_byte_identisch(tmp_path):
    """Idempotenz: derselbe Plan, derselbe Stand -> dieselbe Datei."""
    ziel = tmp_path / "d.json"
    daten = _bauen([_zug(), _zug(fileid=KENNUNG_ZWEI, von_name=NAME_ZWEI)])
    fd.dateien_schreiben(str(ziel), daten)
    vorher = _datei_hash(ziel)
    fd.dateien_schreiben(str(ziel), daten)
    assert _datei_hash(ziel) == vorher


def test_schreiben_aus_dem_plan_zweimal_ist_byte_identisch(tmp_path):
    """Auch wenn der Plan zweimal frisch gebaut wird: gleiche Bytes."""
    ziel = tmp_path / "d.json"
    plan = _plan([_zug(), _zug(jahr=2022, fileid=KENNUNG_ZWEI)])
    fd.dateien_schreiben(str(ziel), fd.dateien_bauen(plan, stand=STAND))
    vorher = _datei_hash(ziel)
    fd.dateien_schreiben(str(ziel), fd.dateien_bauen(plan, stand=STAND))
    assert _datei_hash(ziel) == vorher


def test_schreiben_im_repo_wird_mit_valueerror_verweigert(tmp_path):
    ziel = REPO / "fotos_dateien.json"
    assert not ziel.exists(), "Vorbedingung: die Datei gibt es nicht"
    with pytest.raises(ValueError) as fehler:
        fd.dateien_schreiben(str(ziel), _bauen([_zug()]))
    assert "IM Repo" in str(fehler.value)
    assert "NICHTS geschrieben" in str(fehler.value)
    assert not ziel.exists()


def test_schreiben_in_den_werkzeugordner_wird_verweigert():
    ziel = WERKZEUG.parent / "fotos_dateien.json"
    assert not ziel.exists(), "Vorbedingung: die Datei gibt es nicht"
    with pytest.raises(ValueError):
        fd.dateien_schreiben(str(ziel), {})
    assert not ziel.exists()


def test_schreiben_ohne_daten_ist_klartextfehler(tmp_path):
    with pytest.raises(ValueError) as fehler:
        fd.dateien_schreiben(str(tmp_path / "d.json"), None)
    assert "Dateikennungen" in str(fehler.value)
    assert not (tmp_path / "d.json").exists()


def test_schreiben_ohne_zielpfad_ist_klartextfehler():
    with pytest.raises(ValueError) as fehler:
        fd.dateien_schreiben("", {})
    assert "Kein Zielpfad" in str(fehler.value)


def test_schreiben_scheitert_nicht_zerstoerend(tmp_path):
    ziel = tmp_path / "d.json"
    fd.dateien_schreiben(str(ziel), _bauen([_zug()]))
    vorher = _datei_hash(ziel)
    with pytest.raises(TypeError):
        # Nicht serialisierbar -> es darf keine halbe Datei entstehen und die
        # alte Datei muss unangetastet bleiben.
        fd.dateien_schreiben(str(ziel), {"kaputt": object()})
    assert _datei_hash(ziel) == vorher
    assert list(tmp_path.glob("*.tmp")) == []


def test_schreiben_legt_den_zielordner_an(tmp_path):
    ziel = tmp_path / "neu" / "tiefer" / "d.json"
    fd.dateien_schreiben(str(ziel), _bauen([_zug()]))
    assert ziel.is_file()


# ── Klartext ──────────────────────────────────────────────────────────────

def test_text_nennt_stand_und_zahlen():
    text = fd.dateien_text(_bauen([_zug(), _zug(fileid=KENNUNG_ZWEI,
                                                von_name=NAME_ZWEI)]))
    assert STAND in text
    assert "Events: 1" in text
    assert "Dateien: 2" in text
    assert "ohne Kennung: 0" in text


def test_text_nennt_plan_stand_und_unbekannt():
    assert PLAN_STAND in fd.dateien_text(_bauen([_zug()]))
    assert "unbekannt" in fd.dateien_text({})


def test_text_haelt_fehlende_felder_aus():
    text = fd.dateien_text({})
    assert "Events: 0" in text
    assert "ohne Kennung: 0" in text


def test_text_ist_mehrzeilig_und_deutsch():
    text = fd.dateien_text(_bauen([_zug()]))
    assert len(text.splitlines()) >= 4
    assert "ohne Bilddaten" in text


def test_text_zeigt_hoechstens_fuenf_events():
    zuege = [_zug(jahr=2000 + i, event=f"Beispiel-Event-{i:02d}", fileid=i)
             for i in range(1, 8)]
    text = fd.dateien_text(_bauen(zuege))
    assert "weitere Events" in text


# ── Kommandozeile ─────────────────────────────────────────────────────────

def test_haupt_trockenlauf_schreibt_nichts(tmp_path, capsys):
    plan = _plan_datei(tmp_path)
    ziel = tmp_path / "d.json"
    assert fd.haupt(["--plan", str(plan), "--ausgabe", str(ziel)]) == 0
    assert not ziel.exists()
    ausgabe = capsys.readouterr().out
    assert "TROCKENLAUF" in ausgabe
    assert "wurde NICHT geschrieben" in ausgabe


def test_haupt_trockenlauf_zeigt_die_zahlen(tmp_path, capsys):
    plan = _plan_datei(tmp_path)
    fd.haupt(["--plan", str(plan), "--ausgabe", str(tmp_path / "d.json")])
    ausgabe = capsys.readouterr().out
    assert "Sortierplan:" in ausgabe
    assert "Events: 1" in ausgabe
    assert "Dateien: 1" in ausgabe


def test_haupt_expliziter_trockenlauf_schlaegt_schreiben(tmp_path, capsys):
    plan = _plan_datei(tmp_path)
    ziel = tmp_path / "d.json"
    assert fd.haupt(["--plan", str(plan), "--ausgabe", str(ziel),
                     "--trocken", "--schreiben"]) == 0
    assert not ziel.exists()
    assert "TROCKENLAUF" in capsys.readouterr().out


def test_haupt_mit_schreiben_legt_die_datei_an(tmp_path):
    plan = _plan_datei(tmp_path)
    ziel = tmp_path / "d.json"
    assert fd.haupt(["--plan", str(plan), "--ausgabe", str(ziel),
                     "--schreiben"]) == 0
    daten = json.loads(ziel.read_text(encoding="utf-8"))
    assert daten["art"] == "foto_dateien"
    assert daten["events"][0]["dateien"][0]["datei_id"] == KENNUNG


def test_haupt_schreiben_ist_wiederholbar(tmp_path):
    plan = _plan_datei(tmp_path)
    ziel = tmp_path / "d.json"
    fd.haupt(["--plan", str(plan), "--ausgabe", str(ziel), "--schreiben"])
    vorher = json.loads(ziel.read_text(encoding="utf-8"))["events"]
    fd.haupt(["--plan", str(plan), "--ausgabe", str(ziel), "--schreiben"])
    assert json.loads(ziel.read_text(encoding="utf-8"))["events"] == vorher


def test_haupt_repo_ziel_ergibt_exit_2(tmp_path, capsys):
    plan = _plan_datei(tmp_path)
    ziel = REPO / "fotos_dateien.json"
    assert not ziel.exists(), "Vorbedingung: die Datei gibt es nicht"
    assert fd.haupt(["--plan", str(plan), "--ausgabe", str(ziel),
                     "--schreiben"]) == 2
    fehler = capsys.readouterr().err
    assert "IM Repo" in fehler
    assert not ziel.exists()


def test_haupt_repo_ziel_ergibt_auch_im_trockenlauf_exit_2(tmp_path, capsys):
    plan = _plan_datei(tmp_path)
    assert fd.haupt(["--plan", str(plan),
                     "--ausgabe", str(REPO / "docs" / "d.json")]) == 2
    assert "IM Repo" in capsys.readouterr().err


def test_haupt_fehlender_plan_ergibt_exit_2(tmp_path, capsys):
    assert fd.haupt(["--plan", str(tmp_path / "gibtsnicht.json"),
                     "--ausgabe", str(tmp_path / "d.json")]) == 2
    assert "Fehler" in capsys.readouterr().err


def test_haupt_kaputter_plan_ergibt_exit_2(tmp_path, capsys):
    pfad = tmp_path / "krumm.json"
    pfad.write_text("kein json", encoding="utf-8")
    assert fd.haupt(["--plan", str(pfad), "--ausgabe",
                     str(tmp_path / "d.json")]) == 2
    assert "Fehler" in capsys.readouterr().err


def test_haupt_plan_ohne_zuege_ergibt_exit_2(tmp_path, capsys):
    pfad = tmp_path / "leer.json"
    pfad.write_text("{}", encoding="utf-8")
    assert fd.haupt(["--plan", str(pfad), "--ausgabe",
                     str(tmp_path / "d.json")]) == 2
    assert "zuege" in capsys.readouterr().err


# ── Quelltext: keine Loesch-, Netz- oder pCloud-Funktion ──────────────────

def _baum():
    return ast.parse(WERKZEUG.read_text(encoding="utf-8"))


def test_quelltext_importiert_nur_standardbibliothek():
    erlaubt = {"argparse", "datetime", "json", "os", "sys", "__future__"}
    namen: set = set()
    for knoten in ast.walk(_baum()):
        if isinstance(knoten, ast.Import):
            for eintrag in knoten.names:
                namen.add(eintrag.name.split(".")[0])
        elif isinstance(knoten, ast.ImportFrom):
            namen.add((knoten.module or "").split(".")[0])
    assert namen <= erlaubt, f"unerlaubter Import: {namen - erlaubt}"


def test_quelltext_ohne_loesch_und_systemaufrufe():
    verboten = {"deletefile", "deletefolder", "rmtree", "removefile",
                "removefolder", "renametree", "system", "popen", "unlink"}
    for knoten in ast.walk(_baum()):
        if isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Attribute):
            assert knoten.func.attr not in verboten, knoten.func.attr


def test_quelltext_loescht_nur_die_eigene_temp_datei():
    aufrufe = [knoten for knoten in ast.walk(_baum())
               if isinstance(knoten, ast.Call)
               and isinstance(knoten.func, ast.Attribute)
               and knoten.func.attr == "remove"]
    assert len(aufrufe) == 1, "genau eine Loeschung: die eigene temp-Datei"
    argument = aufrufe[0].args[0]
    assert isinstance(argument, ast.Name) and argument.id == "temp_pfad"
    assert isinstance(aufrufe[0].func.value, ast.Name)
    assert aufrufe[0].func.value.id == "os"


def test_quelltext_hat_keine_loeschfunktion():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    for verboten in ("def loeschen", "def delete", "def entfernen",
                     "shutil", "rmdir", "rm("):
        assert verboten not in quelle, f"Loeschfunktion im Quelltext: {verboten}"


def test_quelltext_hat_keinen_netzaufruf():
    # Gesucht werden echte Aufrufe/Importe, nicht das Wort in der Begruendung
    # des Modulkopfes ("kein httpx/requests").
    quelle = WERKZEUG.read_text(encoding="utf-8")
    for verboten in ("import requests", "requests.", "import httpx", "httpx.",
                     "import urllib", "urllib.", "import socket", "socket.",
                     "urlopen(", "http://", "https://", "pcloud_service",
                     "pcloud_bewegungen", "import subprocess", "subprocess."):
        assert verboten not in quelle, f"Netz-/Fremdaufruf im Quelltext: {verboten}"


def test_quelltext_oeffnet_keine_bilder():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    for verboten in ("PIL", "cv2", "imageio", ".jpg", ".jpeg", ".png", ".heic",
                     ".webp", '"rb"', "'rb'"):
        assert verboten not in quelle, f"Bildzugriff im Quelltext: {verboten}"


def test_quelltext_schreibt_atomar():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert "os.replace(" in quelle
    assert ".tmp" in quelle


def test_quelltext_prueft_das_repo_ziel():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert "_pruefe_ziel_ausserhalb_repo" in quelle
    assert "IM Repo" in quelle


def test_quelltext_ohne_datetime_now_in_der_reinen_funktion():
    # ``datetime.now()`` darf nur ueber den injizierbaren ``stand`` laufen: die
    # reine Funktion ``dateien_bauen`` muss ohne ``stand`` selbst den
    # Zeitstempel setzen, aber deterministisch pruefbar bleiben — deshalb
    # genau ein Aufruf von ``now`` im Modul.
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert quelle.count("datetime.datetime.now(") == 1


def test_quelltext_liest_den_plan_nur_lesend():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert 'open(pfad, encoding="utf-8")' in quelle
    assert '"r"' not in quelle
