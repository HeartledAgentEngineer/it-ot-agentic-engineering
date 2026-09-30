"""Pruefungen fuer ``personen_andocken.py`` (N27 Schritt 4, Personen-Andockung, 29.09.2026).

Alles OHNE Netz und ohne Bild und **ohne echten Bestand**: das Werkzeug wird
ueber den Dateipfad geladen, alle Eingaben sind erfundene JSON/JSONL-Dateien im
``tmp_path``. Geprueft werden das eingefrorene Ausgabeschema, die Kernregel
„Vorschlag ist kein Name" (ein Vorschlag bestaetigt sich nie selbst), die
Zaehlungen, das atomare Schreiben nur **ausserhalb** des Repos, der
Repo-Ziel-Exit 2, die Kommandozeile und der Quelltext (kein Nachrichteninhalt,
keine Nummern-Maske, kein Netz, kein Bild, keine Loeschfunktion ausser der
eigenen temp-Datei).

**Nur erfundene Beispielnamen und erfundene Kennungen** — echte Anlass-IDs,
Orte, Kennungen und Personen liegen ausserhalb des Repos und kommen hier nicht
vor.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_personen_andockung.py -q
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "personen_andocken.py"

STAND = "2026-09-29T02:00:00+02:00"

# Erfundene Beispielwerte (keine echten Namen/Kennungen/Orte).
ANLASS = "2014-11-22_Beispiel-01"
ANLASS_ZWEI = "2016-05-04_Beispiel-02"
KENNUNG = "E-" + ANLASS
KENNUNG_ZWEI = "E-" + ANLASS_ZWEI
BILD = "BILD-1"
BILD_ZWEI = "BILD-2"
BILD_FREMD = "BILD-9"
NAME = "Beispielname"
NAME_ZWEIT = "Beispiel-Zweit"
NAME_DRITT = "Beispiel-Dritt"
PERSON = "Person_001"
PERSON_ZWEI = "Person_002"
MASKE = "*" * 3 + "1234"                 # nur als Negativ-Beispiel gebaut

SCHEMA_KNOTEN = {"art", "anlass_id", "kennung", "datum", "personen", "quellen",
                 "stand"}
SCHEMA_PERSON = {"kennung", "bilder", "gesichter", "bestaetigt", "name"}
SCHEMA_VORSCHLAG = {"anzahl_anlaesse", "anzahl_bilder", "anzahl_gesichter",
                    "bestaetigt", "bestaetigter_name", "bis", "kennung",
                    "namen", "von", "vorschlag"}
SCHEMA_VORSCHLAEGE = {"art", "stand", "anzahl_personen", "anzahl_bestaetigt",
                      "hinweis", "personen"}


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


pa = _laden(WERKZEUG, "personen_andocken")


# ── kleine Helfer (erfundene Daten) ───────────────────────────────────────

def _embedding(wert: float = 0.1) -> list:
    return [wert] * 128


def _gesicht(bbox=(0.0, 0.0, 50.0, 50.0), score: float = 0.9,
             wert: float = 0.1) -> dict:
    return {"bbox": list(bbox), "score": score, "embedding": _embedding(wert)}


def _vektorzeile(bild_id: str, *gesichter) -> dict:
    return {"bild_id": bild_id, "breite": 100.0, "hoehe": 100.0,
            "gesichter": list(gesichter) or [_gesicht()]}


def _ereignis(anlass_id: str = ANLASS, kennung: str = KENNUNG,
              datum: str = "2014-11-22", dateien=(BILD,)) -> dict:
    return {"art": "ereignis", "anlass_id": anlass_id, "kennung": kennung,
            "datum": datum, "datei_kennungen": list(dateien),
            "thema": "Beispiel"}


def _chat(knoten_id: str, *chats) -> dict:
    return {"anlass_id": knoten_id, "art": "chat_andockung",
            "chats": list(chats)}


def _chat_eintrag(chat_name: str = NAME, *beteiligte) -> dict:
    return {"art": "einzel", "chat_name": chat_name, "chat_row_id": 1,
            "beteiligte": list(beteiligte), "nachrichten": 2, "von_mir": 0,
            "von_anderen": 2, "medien": 0}


def _beteiligter(name: str = NAME_ZWEIT) -> dict:
    return {"name": name, "nummer_maske": MASKE, "nachrichten": 2}


def _andockung_zeile(anlass_id: str = ANLASS, kennung: str = KENNUNG,
                     datum: str = "2014-11-22", personen=None) -> dict:
    return {"anlass_id": anlass_id, "kennung": kennung, "datum": datum,
            "personen": personen if personen is not None
            else [{"kennung": PERSON, "bilder": 1, "gesichter": 2}],
            "quellen": {"personen": pa.QUELLE_PERSONEN,
                        "anlass": pa.QUELLE_ANLASS}}


def _andocken(personen_bilder=None, index=None):
    werte = personen_bilder if personen_bilder is not None else {PERSON: [BILD]}
    idx = index if index is not None else {BILD: _ereignis()}
    return pa.andocken(werte, idx)


def _json(datei: Path, daten) -> Path:
    datei.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    return datei


def _jsonl(datei: Path, zeilen) -> Path:
    datei.write_text("\n".join(json.dumps(z, ensure_ascii=False)
                               for z in zeilen) + "\n", encoding="utf-8")
    return datei


def _datei_hash(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def _als_text(wert) -> str:
    return json.dumps(wert, ensure_ascii=False, sort_keys=True, default=str)


class Oeffner:
    """Ein Aufruf, der niemals passieren darf (reine Funktion ohne I/O)."""

    def __call__(self, *args, **kwargs):
        raise AssertionError("Es wurde eine Datei geoeffnet, obwohl nichts "
                             "geoeffnet werden darf!")


# ── Konstanten und eingefrorenes Schema ──────────────────────────────────

def test_art_knoten_ist_fest():
    assert pa.ART_KNOTEN == "personen_andockung"


def test_art_vorschlaege_ist_fest():
    assert pa.ART_VORSCHLAEGE == "personen_vorschlaege"


def test_hinweis_ist_woertlich():
    assert pa.HINWEIS_VORSCHLAEGE == ("Namen nur nach Bestaetigung; "
                                      "Vorschlaege sind Vorschlaege.")


def test_namen_je_person_standard_ist_fuenf():
    assert pa.NAMEN_JE_PERSON == 5


def test_knoten_schluessel_sind_fest():
    assert pa.KNOTEN_SCHLUESSEL == ("art", "anlass_id", "kennung", "datum",
                                    "personen", "quellen", "stand")


def test_person_schluessel_sind_fest():
    assert pa.KNOTEN_PERSON_SCHLUESSEL == ("kennung", "bilder", "gesichter",
                                           "bestaetigt", "name")


def test_vorschlag_schluessel_sind_fest():
    assert set(pa.VORSCHLAG_SCHLUESSEL) == SCHEMA_VORSCHLAG


def test_vorschlaege_dokument_schluessel_sind_fest():
    assert set(pa.VORSCHLAEGE_DOKUMENT_SCHLUESSEL) == SCHEMA_VORSCHLAEGE


def test_standard_ausgabepfade_liegen_ausserhalb_des_repos():
    for pfad in (pa.STANDARD_AUSGABE_KNOTEN, pa.STANDARD_AUSGABE_VORSCHLAEGE):
        assert "foto_sortierung" in pfad
        assert pa.pruefe_ausserhalb_repo(pfad) == pfad


def test_standard_eingabepfade_sind_benannt():
    assert pa.STANDARD_EREIGNISSE.endswith("ereignisse.jsonl")
    assert pa.STANDARD_CHAT_ANDOCKUNG.endswith("chat_andockung.jsonl")
    assert pa.STANDARD_BESTAETIGUNG.endswith("personen_bestaetigt.json")
    assert pa.STANDARD_ALT_KENNUNGEN.endswith("kennungen.json")
    assert len(pa.STANDARD_VEKTOREN) == 2
    assert all(p.endswith(".jsonl") for p in pa.STANDARD_VEKTOREN)


def test_modul_reicht_personen_cluster_durch():
    # Wiederverwendung statt Nachbau: der Repo-Schutz kommt woertlich aus dem
    # Nachbarmodul.
    assert pa.pruefe_ausserhalb_repo is \
        pa._personen_cluster.pruefe_ausserhalb_repo


# ── Kleine Helfer ────────────────────────────────────────────────────────

def test_text_liest_nur_text():
    assert pa._text("  Name ") == "Name"
    assert pa._text(None) == ""
    assert pa._text(5) == ""


def test_zahl_setzt_deutsche_tausenderpunkte():
    assert pa._zahl(151) == "151"
    assert pa._zahl(2414) == "2.414"


def test_als_int_liest_zahlen_aber_kein_bool():
    assert pa._als_int(5) == 5
    assert pa._als_int("7") == 7
    assert pa._als_int(True) is None
    assert pa._als_int("krumm") is None


def test_ist_person_kennt_das_muster():
    assert pa._ist_person("Person_001") is True
    assert pa._ist_person("Person_01") is False
    assert pa._ist_person("Person_0001") is False
    assert pa._ist_person("Beispielname") is False
    # Ab der 1.000. Gruppe vergibt personen_cluster "Person_1000" (Person_%03d);
    # bis 30.09.2026 wurde das still ignoriert.
    assert pa._ist_person("Person_1000") is True
    assert pa._ist_person("Person_12345") is True
    assert pa._ist_person("Person_01000") is False


def test_stand_jz_ohne_angabe_wird_gefuellt():
    assert isinstance(pa._stand_jz(), str) and "T" in pa._stand_jz()


def test_stand_jz_mit_angabe_bleibt():
    assert pa._stand_jz(STAND) == STAND


# ── vektoren_lesen ───────────────────────────────────────────────────────

def test_vektoren_lesen_liest_eine_datei(tmp_path):
    pfad = _jsonl(tmp_path / "v.jsonl", [_vektorzeile(BILD)])
    ergebnis = pa.vektoren_lesen(str(pfad))
    assert len(ergebnis["zeilen"]) == 1
    assert ergebnis["zeilen"][0]["bild_id"] == BILD
    assert ergebnis["defekt"] == 0


def test_vektoren_lesen_liest_mehrere_dateien_in_reihenfolge(tmp_path):
    a = _jsonl(tmp_path / "a.jsonl", [_vektorzeile(BILD)])
    b = _jsonl(tmp_path / "b.jsonl", [_vektorzeile(BILD_ZWEI)])
    ergebnis = pa.vektoren_lesen([str(a), str(b)])
    assert [z["bild_id"] for z in ergebnis["zeilen"]] == [BILD, BILD_ZWEI]
    assert ergebnis["dateien"] == [str(a), str(b)]


def test_vektoren_lesen_zaehlt_kaputte_zeile_und_liest_weiter(tmp_path):
    pfad = tmp_path / "v.jsonl"
    pfad.write_text("{kein json\n" + json.dumps(_vektorzeile(BILD)) + "\n",
                    encoding="utf-8")
    ergebnis = pa.vektoren_lesen(str(pfad))
    assert ergebnis["defekt"] == 1
    assert len(ergebnis["zeilen"]) == 1


def test_vektoren_lesen_zaehlt_nicht_objekt_zeile(tmp_path):
    pfad = tmp_path / "v.jsonl"
    pfad.write_text("[1, 2, 3]\n", encoding="utf-8")
    assert pa.vektoren_lesen(str(pfad))["defekt"] == 1


def test_vektoren_lesen_zaehlt_leere_zeile(tmp_path):
    pfad = tmp_path / "v.jsonl"
    pfad.write_text("\n\n", encoding="utf-8")
    assert pa.vektoren_lesen(str(pfad))["defekt"] == 2


def test_vektoren_lesen_fehlende_datei_ist_klartextfehler(tmp_path):
    with pytest.raises(pa.PersonenFehler) as fehler:
        pa.vektoren_lesen(str(tmp_path / "gibtsnicht.jsonl"))
    assert "nicht gefunden" in str(fehler.value)


def test_vektoren_lesen_einzelner_pfad_ist_erlaubt(tmp_path):
    pfad = _jsonl(tmp_path / "v.jsonl", [_vektorzeile(BILD)])
    assert len(pa.vektoren_lesen(str(pfad))["zeilen"]) == 1


def test_vektoren_lesen_leere_liste_ist_leer():
    ergebnis = pa.vektoren_lesen([])
    assert ergebnis["zeilen"] == [] and ergebnis["defekt"] == 0


def test_vektoren_lesen_falscher_typ_ist_klartextfehler():
    with pytest.raises(pa.PersonenFehler):
        pa.vektoren_lesen(5)


def test_vektoren_lesen_leerer_pfad_ist_klartextfehler():
    with pytest.raises(pa.PersonenFehler):
        pa.vektoren_lesen([""])


# ── ereignisse_lesen ─────────────────────────────────────────────────────

def test_ereignisse_lesen_nur_art_ereignis(tmp_path):
    pfad = _jsonl(tmp_path / "e.jsonl",
                  [_ereignis(), {"art": "chat_andockung", "anlass_id": ANLASS}])
    ereignisse = pa.ereignisse_lesen(str(pfad))
    assert len(ereignisse) == 1
    assert ereignisse[0]["anlass_id"] == ANLASS
    assert ereignisse.defekt == 1


def test_ereignisse_lesen_zaehlt_kaputtes_json(tmp_path):
    pfad = tmp_path / "e.jsonl"
    pfad.write_text("{krumm\n" + json.dumps(_ereignis()) + "\n",
                    encoding="utf-8")
    ereignisse = pa.ereignisse_lesen(str(pfad))
    assert len(ereignisse) == 1 and ereignisse.defekt == 1


def test_ereignisse_lesen_behaelt_die_reihenfolge(tmp_path):
    pfad = _jsonl(tmp_path / "e.jsonl",
                  [_ereignis(), _ereignis(ANLASS_ZWEI, KENNUNG_ZWEI,
                                          "2016-05-04", (BILD_ZWEI,))])
    assert [e["anlass_id"] for e in pa.ereignisse_lesen(str(pfad))] == \
        [ANLASS, ANLASS_ZWEI]


def test_ereignisse_lesen_fehlende_datei_ist_klartextfehler(tmp_path):
    with pytest.raises(pa.PersonenFehler) as fehler:
        pa.ereignisse_lesen(str(tmp_path / "gibtsnicht.jsonl"))
    assert "nicht gefunden" in str(fehler.value)


def test_ereignisse_lesen_ohne_pfad_ist_klartextfehler():
    with pytest.raises(pa.PersonenFehler) as fehler:
        pa.ereignisse_lesen("")
    assert "Kein Pfad" in str(fehler.value)


def test_ereignisse_lesen_ohne_art_zaehlt_als_defekt(tmp_path):
    pfad = _jsonl(tmp_path / "e.jsonl", [{"anlass_id": ANLASS}])
    ereignisse = pa.ereignisse_lesen(str(pfad))
    assert len(ereignisse) == 0 and ereignisse.defekt == 1


# ── ereignis_index ───────────────────────────────────────────────────────

def test_ereignis_index_schluesselt_nach_datei_kennung_als_text():
    index = pa.ereignis_index([_ereignis(dateien=(123, 456))])
    assert sorted(index) == ["123", "456"]
    assert index["123"]["anlass_id"] == ANLASS


def test_ereignis_index_erste_zuordnung_gewinnt():
    zweites = _ereignis(ANLASS_ZWEI, KENNUNG_ZWEI, "2016-05-04", (BILD,))
    index = pa.ereignis_index([_ereignis(dateien=(BILD,)), zweites])
    assert index[BILD]["anlass_id"] == ANLASS


def test_ereignis_index_zaehlt_kollisionen():
    zweites = _ereignis(ANLASS_ZWEI, KENNUNG_ZWEI, "2016-05-04", (BILD,))
    index = pa.ereignis_index([_ereignis(dateien=(BILD,)), zweites])
    assert index.kollisionen == 1


def test_ereignis_index_ohne_datei_kennungen_ist_leer():
    assert pa.ereignis_index([{"art": "ereignis", "anlass_id": ANLASS}]) == {}


def test_ereignis_index_ohne_liste_ist_leer():
    assert pa.ereignis_index("keine Liste") == {}


def test_ereignis_index_uebergeht_bool_und_none():
    index = pa.ereignis_index([_ereignis(dateien=(None, True, BILD))])
    assert sorted(index) == [BILD]


# ── personen_je_bild ─────────────────────────────────────────────────────

def test_personen_je_bild_bildet_indizes_auf_bild_id_ab():
    lauf = {"kennungen": [{"kennung": PERSON, "indizes": [0, 1]}],
            "eintraege": [{"bild_id": BILD}, {"bild_id": BILD}]}
    assert pa.personen_je_bild(lauf) == {PERSON: [BILD, BILD]}


def test_personen_je_bild_haelt_mehrere_gesichter_je_bild():
    # Drei Gesichter derselben Person in EINEM Bild: drei Eintraege — nur so
    # lassen sich spaeter Bilder und Gesichter unterscheiden.
    lauf = {"kennungen": [{"kennung": PERSON, "indizes": [0, 1, 2]}],
            "eintraege": [{"bild_id": BILD}] * 3}
    ergebnis = pa.personen_je_bild(lauf)
    assert ergebnis[PERSON].count(BILD) == 3
    assert len(set(ergebnis[PERSON])) == 1


def test_personen_je_bild_sortiert_die_bilder():
    lauf = {"kennungen": [{"kennung": PERSON, "indizes": [0, 1]}],
            "eintraege": [{"bild_id": BILD_ZWEI}, {"bild_id": BILD}]}
    assert pa.personen_je_bild(lauf)[PERSON] == sorted([BILD_ZWEI, BILD])


def test_personen_je_bild_uebergeht_index_ausserhalb():
    lauf = {"kennungen": [{"kennung": PERSON, "indizes": [0, 9, "x"]}],
            "eintraege": [{"bild_id": BILD}]}
    assert pa.personen_je_bild(lauf)[PERSON] == [BILD]


def test_personen_je_bild_uebergeht_eintrag_ohne_bild_id():
    lauf = {"kennungen": [{"kennung": PERSON, "indizes": [0, 1]}],
            "eintraege": [{"bbox": [0, 0, 1, 1]}, {"bild_id": BILD}]}
    assert pa.personen_je_bild(lauf)[PERSON] == [BILD]


def test_personen_je_bild_ohne_angabe_ist_leer():
    assert pa.personen_je_bild({}) == {}
    assert pa.personen_je_bild(None) == {}


def test_personen_je_bild_uebergeht_kennung_ohne_text():
    lauf = {"kennungen": [{"kennung": "", "indizes": [0]}],
            "eintraege": [{"bild_id": BILD}]}
    assert pa.personen_je_bild(lauf) == {}


# ── andocken ─────────────────────────────────────────────────────────────

def test_andocken_ein_anlass_mit_einer_person():
    knoten = _andocken()
    assert len(knoten) == 1
    assert knoten[0]["anlass_id"] == ANLASS
    assert knoten[0]["kennung"] == KENNUNG
    assert knoten[0]["personen"] == [{"kennung": PERSON, "bilder": 1,
                                      "gesichter": 1}]


def test_andocken_zaehlt_bilder_und_gesichter():
    knoten = pa.andocken({PERSON: [BILD, BILD]}, {BILD: _ereignis()})
    assert knoten[0]["personen"][0]["bilder"] == 1
    assert knoten[0]["personen"][0]["gesichter"] == 2


def test_andocken_sortiert_nach_anlass_id():
    zweites = _ereignis(ANLASS_ZWEI, KENNUNG_ZWEI, "2016-05-04", (BILD_ZWEI,))
    knoten = pa.andocken({PERSON: [BILD_ZWEI, BILD]},
                         {BILD: _ereignis(), BILD_ZWEI: zweites})
    assert [k["anlass_id"] for k in knoten] == [ANLASS, ANLASS_ZWEI]


def test_andocken_sortiert_personen_nach_kennung():
    knoten = pa.andocken({PERSON_ZWEI: [BILD], PERSON: [BILD]},
                         {BILD: _ereignis()})
    assert [p["kennung"] for p in knoten[0]["personen"]] == [PERSON,
                                                            PERSON_ZWEI]


def test_andocken_nur_anlaesse_mit_mindestens_einer_person():
    knoten = pa.andocken({PERSON: []}, {BILD: _ereignis()})
    assert list(knoten) == []


def test_andocken_zaehlt_bilder_ohne_anlass():
    knoten = pa.andocken({PERSON: [BILD, BILD_FREMD]}, {BILD: _ereignis()})
    assert knoten.ohne_anlass == 1
    assert knoten.personen_ohne_anlass == 0


def test_andocken_zaehlt_personen_ohne_anlass():
    knoten = pa.andocken({PERSON: [BILD_FREMD]}, {BILD: _ereignis()})
    assert knoten.personen_ohne_anlass == 1
    assert knoten.ohne_anlass == 1


def test_andocken_quellen_nennen_die_herkunft():
    knoten = _andocken()
    assert knoten[0]["quellen"] == {"personen": pa.QUELLE_PERSONEN,
                                    "anlass": pa.QUELLE_ANLASS}


def test_andocken_oeffnet_keine_datei(monkeypatch):
    monkeypatch.setattr("builtins.open", Oeffner())
    assert len(_andocken()) == 1


def test_andocken_veraendert_die_eingaben_nicht():
    personen = {PERSON: [BILD]}
    index = {BILD: _ereignis()}
    vorher = _als_text([personen, index])
    pa.andocken(personen, index)
    assert _als_text([personen, index]) == vorher


def test_andocken_ohne_index_ist_leer():
    assert list(pa.andocken({PERSON: [BILD]}, None)) == []


# ── kandidaten_je_person ────────────────────────────────────────────────

def test_kandidaten_nehmen_den_chat_namen():
    kandidaten = pa.kandidaten_je_person(
        _andocken(), [_chat(ANLASS, _chat_eintrag(NAME))])
    assert kandidaten[PERSON] == {NAME: 1}


def test_kandidaten_zaehlen_jeden_chat():
    chats = [_chat(ANLASS, _chat_eintrag(NAME), _chat_eintrag(NAME),
                   _chat_eintrag(NAME_DRITT))]
    kandidaten = pa.kandidaten_je_person(_andocken(), chats)
    assert kandidaten[PERSON] == {NAME: 2, NAME_DRITT: 1}


def test_kandidaten_sortieren_absteigend_dann_alphabetisch():
    # NAME zweimal, die anderen je einmal: NAME zuerst (hoehere Zahl), dann die
    # beiden Gleichstand-Namen alphabetisch ("-" vor Buchstaben).
    chats = [_chat(ANLASS, _chat_eintrag(NAME), _chat_eintrag(NAME),
                   _chat_eintrag(NAME_ZWEIT), _chat_eintrag(NAME_DRITT))]
    kandidaten = pa.kandidaten_je_person(_andocken(), chats)
    assert list(kandidaten[PERSON]) == [NAME, NAME_DRITT, NAME_ZWEIT]


def test_kandidaten_nutzen_beteiligte_wenn_chat_name_leer():
    chats = [_chat(ANLASS, _chat_eintrag("", _beteiligter(NAME_ZWEIT)))]
    kandidaten = pa.kandidaten_je_person(_andocken(), chats)
    assert kandidaten[PERSON] == {NAME_ZWEIT: 1}


def test_kandidaten_ohne_chat_knoten_sind_leer():
    assert pa.kandidaten_je_person(_andocken(), []) == {PERSON: {}}


def test_kandidaten_nehmen_chat_knoten_auch_als_dict():
    knoten = {ANLASS: _chat(ANLASS, _chat_eintrag(NAME))}
    assert pa.kandidaten_je_person(_andocken(), knoten)[PERSON] == {NAME: 1}


def test_kandidaten_uebergehen_fremden_anlass():
    kandidaten = pa.kandidaten_je_person(
        _andocken(), [_chat(ANLASS_ZWEI, _chat_eintrag(NAME))])
    assert kandidaten[PERSON] == {}


def test_kandidaten_nehmen_jede_person_des_anlasses():
    personen = [{"kennung": PERSON, "bilder": 1, "gesichter": 1},
                {"kennung": PERSON_ZWEI, "bilder": 1, "gesichter": 1}]
    andockung = [_andockung_zeile(personen=personen)]
    kandidaten = pa.kandidaten_je_person(
        andockung, [_chat(ANLASS, _chat_eintrag(NAME))])
    assert kandidaten == {PERSON: {NAME: 1}, PERSON_ZWEI: {NAME: 1}}


def test_kandidaten_lesen_keinen_nachrichteninhalt():
    geheim = "Beispiel-Inhalt-darf-nicht-auftauchen"
    chat = _chat_eintrag(NAME)
    chat["inhalt"] = geheim
    chat["kennungen_des_inhalts"] = [geheim]
    kandidaten = pa.kandidaten_je_person(_andocken(), [_chat(ANLASS, chat)])
    assert geheim not in _als_text(kandidaten)


# ── vorschlaege_bauen ───────────────────────────────────────────────────

def test_vorschlaege_haben_die_schema_schluessel():
    vorschlaege = pa.vorschlaege_bauen(_andocken(), {PERSON: {NAME: 2}})
    assert set(vorschlaege[0]) == SCHEMA_VORSCHLAG


def test_vorschlaege_sind_nach_kennung_sortiert():
    vorschlaege = pa.vorschlaege_bauen(
        [_andockung_zeile(personen=[{"kennung": PERSON_ZWEI, "bilder": 1,
                                     "gesichter": 1},
                                    {"kennung": PERSON, "bilder": 1,
                                     "gesichter": 1}])], {})
    assert [v["kennung"] for v in vorschlaege] == [PERSON, PERSON_ZWEI]


def test_vorschlag_ist_nicht_bestaetigt():
    vorschlaege = pa.vorschlaege_bauen(_andocken(), {PERSON: {NAME: 2}})
    assert vorschlaege[0]["bestaetigt"] is False
    assert vorschlaege[0]["bestaetigter_name"] is None
    assert vorschlaege[0]["vorschlag"] == NAME


def test_vorschlag_ohne_namen_ist_none():
    vorschlaege = pa.vorschlaege_bauen(_andocken(), {})
    assert vorschlaege[0]["vorschlag"] is None
    assert vorschlaege[0]["namen"] == []


def test_vorschlaege_zaehlen_anlaesse_bilder_gesichter():
    andockung = [_andockung_zeile(personen=[{"kennung": PERSON, "bilder": 3,
                                             "gesichter": 4}])]
    vorschlaege = pa.vorschlaege_bauen(andockung, {})
    assert vorschlaege[0]["anzahl_anlaesse"] == 1
    assert vorschlaege[0]["anzahl_bilder"] == 3
    assert vorschlaege[0]["anzahl_gesichter"] == 4


def test_vorschlaege_nennen_von_und_bis():
    andockung = [_andockung_zeile(personen=[{"kennung": PERSON, "bilder": 1,
                                             "gesichter": 1}]),
                 _andockung_zeile(ANLASS_ZWEI, KENNUNG_ZWEI, "2016-05-04",
                                  [{"kennung": PERSON, "bilder": 1,
                                    "gesichter": 1}])]
    vorschlaege = pa.vorschlaege_bauen(andockung, {})
    assert vorschlaege[0]["von"] == "2014-11-22"
    assert vorschlaege[0]["bis"] == "2016-05-04"
    assert vorschlaege[0]["anzahl_anlaesse"] == 2


def test_vorschlaege_begrenzen_die_namen():
    zaehler = {f"Beispiel-{nummer:02d}": 100 - nummer for nummer in range(9)}
    unbegrenzt = pa.vorschlaege_bauen(_andocken(), {PERSON: zaehler})
    assert len(unbegrenzt[0]["namen"]) == pa.NAMEN_JE_PERSON == 5
    begrenzt = pa.vorschlaege_bauen(_andocken(), {PERSON: zaehler},
                                    namen_je_person=3)
    assert len(begrenzt[0]["namen"]) == 3


def test_vorschlaege_namen_tragen_name_und_anzahl():
    vorschlaege = pa.vorschlaege_bauen(_andocken(), {PERSON: {NAME: 7}})
    assert vorschlaege[0]["namen"][0] == {"name": NAME, "anzahl": 7}


def test_vorschlaege_nehmen_auch_personen_ohne_anlass():
    vorschlaege = pa.vorschlaege_bauen([], {PERSON_ZWEI: {NAME: 1}})
    assert [v["kennung"] for v in vorschlaege] == [PERSON_ZWEI]
    assert vorschlaege[0]["anzahl_anlaesse"] == 0
    assert vorschlaege[0]["von"] is None


# ── bestaetigung_lesen ───────────────────────────────────────────────────

def test_bestaetigung_fehlende_datei_ist_leer(tmp_path):
    assert pa.bestaetigung_lesen(str(tmp_path / "gibtsnicht.json")) == {}


def test_bestaetigung_ohne_pfad_ist_leer():
    assert pa.bestaetigung_lesen("") == {}


def test_bestaetigung_liest_den_bestaetigt_block(tmp_path):
    pfad = _json(tmp_path / "b.json",
                 {"hinweis": "Nur hier eingetragene Namen werden verwendet.",
                  "bestaetigt": {PERSON: NAME}})
    assert pa.bestaetigung_lesen(str(pfad)) == {PERSON: NAME}


def test_bestaetigung_liest_auch_eine_flache_datei(tmp_path):
    pfad = _json(tmp_path / "b.json", {PERSON: NAME})
    assert pa.bestaetigung_lesen(str(pfad)) == {PERSON: NAME}


def test_bestaetigung_zaehlt_fremde_schluessel(tmp_path):
    pfad = _json(tmp_path / "b.json",
                 {"bestaetigt": {PERSON: NAME, "Beispielname": NAME}})
    ergebnis = pa.bestaetigung_lesen(str(pfad))
    assert ergebnis == {PERSON: NAME}
    assert ergebnis.fremde == 1


def test_bestaetigung_uebergeht_leeren_namen(tmp_path):
    pfad = _json(tmp_path / "b.json", {"bestaetigt": {PERSON: "   "}})
    ergebnis = pa.bestaetigung_lesen(str(pfad))
    assert ergebnis == {}
    assert ergebnis.leer == 1


def test_bestaetigung_streift_den_namen(tmp_path):
    pfad = _json(tmp_path / "b.json", {"bestaetigt": {PERSON: f" {NAME} "}})
    assert pa.bestaetigung_lesen(str(pfad))[PERSON] == NAME


def test_bestaetigung_kaputtes_json_ist_klartextfehler(tmp_path):
    pfad = tmp_path / "b.json"
    pfad.write_text("{krumm", encoding="utf-8")
    with pytest.raises(pa.PersonenFehler) as fehler:
        pa.bestaetigung_lesen(str(pfad))
    assert "gueltiges JSON" in str(fehler.value)


def test_bestaetigung_ohne_woerterbuch_ist_klartextfehler(tmp_path):
    pfad = _json(tmp_path / "b.json", ["kein", "Dict"])
    with pytest.raises(pa.PersonenFehler):
        pa.bestaetigung_lesen(str(pfad))


# ── bestaetigung_anwenden ────────────────────────────────────────────────

def test_bestaetigung_anwenden_setzt_nur_aus_der_datei():
    vorschlaege = pa.vorschlaege_bauen(_andocken(), {PERSON: {NAME: 2}},
                                       )
    angewendet = pa.bestaetigung_anwenden(vorschlaege, {})
    assert angewendet[0]["bestaetigt"] is False
    assert angewendet[0]["bestaetigter_name"] is None


def test_bestaetigung_anwenden_setzt_die_bestaetigte_person():
    vorschlaege = pa.vorschlaege_bauen(_andocken(), {PERSON: {NAME: 2}})
    angewendet = pa.bestaetigung_anwenden(vorschlaege, {PERSON: NAME_DRITT})
    assert angewendet[0]["bestaetigt"] is True
    assert angewendet[0]["bestaetigter_name"] == NAME_DRITT


def test_vorschlag_bestaetigt_sich_nie_selbst():
    # Der Vorschlag (NAME) und der bestaetigte Name (NAME_DRITT) sind
    # verschieden — der Vorschlag bleibt unangetastet.
    vorschlaege = pa.vorschlaege_bauen(_andocken(), {PERSON: {NAME: 2}})
    angewendet = pa.bestaetigung_anwenden(vorschlaege, {PERSON: NAME_DRITT})
    assert angewendet[0]["vorschlag"] == NAME
    assert angewendet[0]["bestaetigter_name"] == NAME_DRITT


def test_bestaetigung_anwenden_laesst_andere_unbestaetigt():
    personen = [{"kennung": PERSON, "bilder": 1, "gesichter": 1},
                {"kennung": PERSON_ZWEI, "bilder": 1, "gesichter": 1}]
    vorschlaege = pa.vorschlaege_bauen([_andockung_zeile(personen=personen)],
                                       {})
    angewendet = pa.bestaetigung_anwenden(vorschlaege, {PERSON: NAME})
    nach_kennung = {v["kennung"]: v for v in angewendet}
    assert nach_kennung[PERSON]["bestaetigt"] is True
    assert nach_kennung[PERSON_ZWEI]["bestaetigt"] is False
    assert nach_kennung[PERSON_ZWEI]["bestaetigter_name"] is None


def test_bestaetigung_anwenden_ohne_liste_ist_leer():
    assert pa.bestaetigung_anwenden(None, {}) == []


def test_bestaetigung_anwenden_veraendert_die_eingabe_nicht():
    vorschlaege = pa.vorschlaege_bauen(_andocken(), {PERSON: {NAME: 2}})
    vorher = _als_text(vorschlaege)
    pa.bestaetigung_anwenden(vorschlaege, {PERSON: NAME})
    assert _als_text(vorschlaege) == vorher


# ── knotenzeilen_bauen ───────────────────────────────────────────────────

def test_knotenzeilen_haben_die_schema_schluessel():
    zeilen = pa.knotenzeilen_bauen(_andocken(), {}, STAND)
    assert set(zeilen[0]) == SCHEMA_KNOTEN
    assert set(zeilen[0]["personen"][0]) == SCHEMA_PERSON


def test_knotenzeilen_ohne_bestaetigung_ohne_namen():
    zeilen = pa.knotenzeilen_bauen(_andocken(), {}, STAND)
    assert zeilen[0]["personen"][0]["name"] is None
    assert zeilen[0]["personen"][0]["bestaetigt"] is False


def test_knotenzeilen_mit_bestaetigung_tragen_den_namen():
    zeilen = pa.knotenzeilen_bauen(_andocken(), {PERSON: NAME}, STAND)
    assert zeilen[0]["personen"][0]["name"] == NAME
    assert zeilen[0]["personen"][0]["bestaetigt"] is True


def test_knotenzeilen_nur_die_bestaetigte_person_traegt_einen_namen():
    personen = [{"kennung": PERSON, "bilder": 1, "gesichter": 1},
                {"kennung": PERSON_ZWEI, "bilder": 1, "gesichter": 1}]
    andockung = [_andockung_zeile(personen=personen)]
    zeilen = pa.knotenzeilen_bauen(andockung, {PERSON: NAME}, STAND)
    nach_kennung = {p["kennung"]: p for p in zeilen[0]["personen"]}
    assert nach_kennung[PERSON]["name"] == NAME
    assert nach_kennung[PERSON_ZWEI]["name"] is None


def test_knotenzeilen_tragen_art_kennung_datum_und_stand():
    zeilen = pa.knotenzeilen_bauen(_andocken(), {}, STAND)
    assert zeilen[0]["art"] == pa.ART_KNOTEN
    assert zeilen[0]["kennung"] == KENNUNG
    assert zeilen[0]["datum"] == "2014-11-22"
    assert zeilen[0]["stand"] == STAND


def test_knotenzeilen_stand_ohne_angabe_wird_gefuellt():
    zeilen = pa.knotenzeilen_bauen(_andocken(), {})
    assert isinstance(zeilen[0]["stand"], str) and "T" in zeilen[0]["stand"]


def test_knotenzeilen_uebernehmen_quellen_von_andocken():
    zeilen = pa.knotenzeilen_bauen(_andocken(), {}, STAND)
    assert zeilen[0]["quellen"] == {"personen": pa.QUELLE_PERSONEN,
                                    "anlass": pa.QUELLE_ANLASS}


def test_knotenzeilen_ohne_liste_sind_leer():
    assert pa.knotenzeilen_bauen(None, {}, STAND) == []


# ── vorschlaege_dokument ────────────────────────────────────────────────

def test_vorschlaege_dokument_hat_die_schema_schluessel():
    dokument = pa.vorschlaege_dokument([], {}, STAND)
    assert set(dokument) == SCHEMA_VORSCHLAEGE


def test_vorschlaege_dokument_zaehlt_personen_und_bestaetigte():
    vorschlaege = pa.vorschlaege_bauen(_andocken(), {PERSON: {NAME: 2}})
    vorschlaege = pa.bestaetigung_anwenden(vorschlaege, {PERSON: NAME})
    dokument = pa.vorschlaege_dokument(vorschlaege, {}, STAND)
    assert dokument["art"] == pa.ART_VORSCHLAEGE
    assert dokument["anzahl_personen"] == 1
    assert dokument["anzahl_bestaetigt"] == 1
    assert dokument["hinweis"] == pa.HINWEIS_VORSCHLAEGE


# ── schreiben ───────────────────────────────────────────────────────────

def test_schreiben_einer_liste_ist_jsonl(tmp_path):
    ziel = tmp_path / "p.jsonl"
    zurueck = pa.schreiben(str(ziel), pa.knotenzeilen_bauen(_andocken(), {},
                                                            STAND))
    assert zurueck == str(ziel)
    zeilen = ziel.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 1
    assert set(json.loads(zeilen[0])) == SCHEMA_KNOTEN


def test_schreiben_eines_dicts_ist_json(tmp_path):
    ziel = tmp_path / "p.json"
    pa.schreiben(str(ziel), pa.vorschlaege_dokument([], {}, STAND))
    daten = json.loads(ziel.read_text(encoding="utf-8"))
    assert daten["art"] == pa.ART_VORSCHLAEGE


def test_schreiben_ist_ascii_und_sortiert(tmp_path):
    ziel = tmp_path / "p.jsonl"
    pa.schreiben(str(ziel), pa.knotenzeilen_bauen(_andocken(), {}, STAND))
    roh = ziel.read_text(encoding="utf-8")
    assert roh.isascii()
    for zeile in roh.splitlines():
        assert zeile == json.dumps(json.loads(zeile), ensure_ascii=True,
                                   sort_keys=True)


def test_schreiben_laesst_keine_temp_datei_zurueck(tmp_path):
    pa.schreiben(str(tmp_path / "p.jsonl"),
                 pa.knotenzeilen_bauen(_andocken(), {}, STAND))
    assert list(tmp_path.glob("*.tmp")) == []


def test_schreiben_zweiter_lauf_ist_byte_gleich(tmp_path):
    ziel = tmp_path / "p.jsonl"
    zeilen = pa.knotenzeilen_bauen(_andocken(), {}, STAND)
    pa.schreiben(str(ziel), zeilen)
    vorher = _datei_hash(ziel)
    pa.schreiben(str(ziel), zeilen)
    assert _datei_hash(ziel) == vorher


def test_schreiben_legt_den_zielordner_an(tmp_path):
    ziel = tmp_path / "neu" / "tief" / "p.jsonl"
    pa.schreiben(str(ziel), [])
    assert ziel.is_file()


def test_schreiben_im_repo_ist_exit_2():
    ziel = REPO / "personen_andockung.jsonl"
    assert not ziel.exists(), "Vorbedingung: die Datei gibt es nicht"
    with pytest.raises(SystemExit) as fehler:
        pa.schreiben(str(ziel), [])
    assert fehler.value.code == 2
    assert not ziel.exists()


def test_schreiben_im_werkzeugordner_ist_exit_2():
    ziel = WERKZEUG.parent / "personen_vorschlaege.json"
    assert not ziel.exists(), "Vorbedingung: die Datei gibt es nicht"
    with pytest.raises(SystemExit) as fehler:
        pa.schreiben(str(ziel), {})
    assert fehler.value.code == 2
    assert not ziel.exists()


def test_schreiben_falscher_inhalt_ist_klartextfehler(tmp_path):
    ziel = tmp_path / "p.jsonl"
    with pytest.raises(pa.PersonenFehler):
        pa.schreiben(str(ziel), "kein Inhalt")
    assert not ziel.exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_schreiben_ohne_pfad_ist_klartextfehler():
    with pytest.raises(pa.PersonenFehler):
        pa.schreiben("", [])


def test_schreiben_scheitert_nicht_zerstoerend(tmp_path):
    ziel = tmp_path / "p.jsonl"
    pa.schreiben(str(ziel), pa.knotenzeilen_bauen(_andocken(), {}, STAND))
    vorher = _datei_hash(ziel)
    with pytest.raises(pa.PersonenFehler):
        pa.schreiben(str(ziel), 5)
    assert _datei_hash(ziel) == vorher
    assert list(tmp_path.glob("*.tmp")) == []


# ── bericht_bauen ───────────────────────────────────────────────────────

def _zahlen_beispiel(**rest) -> dict:
    zahlen = {
        "stand": STAND, "vektorzeilen": 151, "defekte_zeilen": 0,
        "je_art": {"gruppe": 41, "leer": 64, "menge": 11, "unklar": 35},
        "personen": 12, "kennungen_neu": 2, "kennungen_wiederverwendet": 10,
        "gruppen_groessen": [11, 10, 10, 5, 4, 4, 4, 4, 4, 3, 3, 3],
        "personen_ohne_anlass": 0, "ohne_anlass": 0,
        "anlaesse_mit_person": 5, "andockung_personen": 12,
        "personen_mit_kandidaten": 12, "namen_verschieden": 34,
        "kandidaten_groessen": [24, 19, 12, 12, 10, 10, 10, 10, 8, 8, 8, 8],
        "namen_bestaetigt": 0, "namen_ausgabe": 0, "fremde_schluessel": 0,
    }
    zahlen.update(rest)
    return zahlen


def test_bericht_nennt_die_sollwert_zeilen():
    text = pa.bericht_bauen(_zahlen_beispiel())
    for wort in ("Vektorzeilen gelesen: 151",
                 "Bilder-Arten: gruppe: 41   leer: 64   menge: 11   unklar: 35",
                 "Personen (Gruppen): 12   davon 2 neu, 10 wiederverwendet",
                 "Gruppengroessen: 11, 10, 10, 5, 4, 4, 4, 4, 4, 3, 3, 3",
                 "Personen ohne Anlass-Zuordnung: 0",
                 "Anlaesse mit mindestens einer Person: 5",
                 "Personen mit Kandidatennamen: 12 von 12",
                 "verschiedene Kandidatennamen gesamt: 34",
                 "Kandidaten je Person (groesste zuerst): "
                 "24, 19, 12, 12, 10, 10, 10, 10, 8, 8, 8, 8"):
        assert wort in text, wort


def test_bericht_haelt_fehlende_felder_aus():
    text = pa.bericht_bauen({})
    assert "unbekannt" in text
    assert "Vektorzeilen gelesen: 0" in text
    assert "Gruppengroessen: -" in text


def test_bericht_ist_mehrzeilig():
    assert len(pa.bericht_bauen(_zahlen_beispiel()).splitlines()) >= 8


def test_bericht_spricht_nicht_von_loeschen():
    text = pa.bericht_bauen(_zahlen_beispiel())
    for verboten in ("loesch", "Loesch", "geloescht", "delete", "entfernt"):
        assert verboten not in text


# ── Kommandozeile ───────────────────────────────────────────────────────

def _cli_dateien(tmp_path: Path, mit_anlass: bool = True):
    """Erfundene Eingabedateien fuer die Kommandozeile bauen.

    Drei gleiche Gesichter in EINEM Bild ergeben eine Gruppe (Mindestgroesse 3)
    und damit genau eine Person.
    """
    zeile = _vektorzeile(BILD, _gesicht(), _gesicht(), _gesicht())
    vektoren = _jsonl(tmp_path / "vektoren.jsonl", [zeile])
    ereignisse = _jsonl(tmp_path / "ereignisse.jsonl",
                        [_ereignis()] if mit_anlass else [])
    chats = _jsonl(tmp_path / "chats.jsonl",
                   [_chat(ANLASS, _chat_eintrag(NAME, _beteiligter()))])
    return vektoren, ereignisse, chats


def _argumente(tmp_path: Path, vektoren, ereignisse, chats, **rest) -> list:
    return ["--vektoren", str(vektoren), "--ereignisse", str(ereignisse),
            "--chat-andockung", str(chats),
            "--alt-kennungen", str(tmp_path / "keine_kennungen.json"),
            "--bestaetigung", str(rest.get("bestaetigung",
                                           tmp_path / "keine.json")),
            "--ausgabe-knoten", str(rest.get("knoten",
                                             tmp_path / "p.jsonl")),
            "--ausgabe-vorschlaege", str(rest.get("vorschlaege",
                                                  tmp_path / "p.json")),
            "--stand", STAND]


def test_main_trockenlauf_schreibt_nichts(tmp_path, capsys):
    vektoren, ereignisse, chats = _cli_dateien(tmp_path)
    knoten = tmp_path / "p.jsonl"
    vorschlaege = tmp_path / "p.json"
    assert pa.main(_argumente(tmp_path, vektoren, ereignisse, chats)) == 0
    assert not knoten.exists() and not vorschlaege.exists()
    ausgabe = capsys.readouterr().out
    assert "TROCKENLAUF" in ausgabe
    assert "wurden NICHT geschrieben" in ausgabe


def test_main_trockenlauf_zeigt_die_zahlen(tmp_path, capsys):
    vektoren, ereignisse, chats = _cli_dateien(tmp_path)
    pa.main(_argumente(tmp_path, vektoren, ereignisse, chats))
    ausgabe = capsys.readouterr().out
    assert "Vektorzeilen gelesen: 1" in ausgabe
    assert "Anlaesse mit mindestens einer Person: 1" in ausgabe
    assert "Personen mit Kandidatennamen: 1 von 1" in ausgabe


def test_main_schreiben_legt_beide_dateien_an(tmp_path):
    vektoren, ereignisse, chats = _cli_dateien(tmp_path)
    knoten = tmp_path / "p.jsonl"
    vorschlaege = tmp_path / "p.json"
    assert pa.main(_argumente(tmp_path, vektoren, ereignisse, chats)
                   + ["--schreiben"]) == 0
    assert knoten.is_file() and vorschlaege.is_file()
    zeilen = knoten.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 1
    assert json.loads(zeilen[0])["art"] == pa.ART_KNOTEN


def test_main_schreiben_ist_byte_gleich_wiederholbar(tmp_path):
    vektoren, ereignisse, chats = _cli_dateien(tmp_path)
    knoten = tmp_path / "p.jsonl"
    vorschlaege = tmp_path / "p.json"
    args = _argumente(tmp_path, vektoren, ereignisse, chats) + ["--schreiben"]
    pa.main(args)
    vorher = _datei_hash(knoten), _datei_hash(vorschlaege)
    pa.main(args)
    assert (_datei_hash(knoten), _datei_hash(vorschlaege)) == vorher
    assert list(tmp_path.glob("*.tmp")) == []


def test_main_ohne_bestaetigung_enthaelt_keine_namen(tmp_path):
    vektoren, ereignisse, chats = _cli_dateien(tmp_path)
    knoten = tmp_path / "p.jsonl"
    vorschlaege = tmp_path / "p.json"
    pa.main(_argumente(tmp_path, vektoren, ereignisse, chats)
            + ["--schreiben"])
    for zeile in knoten.read_text(encoding="utf-8").splitlines():
        for person in json.loads(zeile)["personen"]:
            assert person["name"] is None
            assert person["bestaetigt"] is False
    dokument = json.loads(vorschlaege.read_text(encoding="utf-8"))
    assert dokument["anzahl_bestaetigt"] == 0
    assert all(p["bestaetigter_name"] is None for p in dokument["personen"])
    # Der Vorschlag bleibt ein Vorschlag — er wird nie zum Namen.
    assert dokument["personen"][0]["vorschlag"] == NAME


def test_main_mit_probe_bestaetigung_nennt_genau_eine_person(tmp_path):
    vektoren, ereignisse, chats = _cli_dateien(tmp_path)
    bestaetigung = _json(tmp_path / "b.json",
                         {"bestaetigt": {"Person_001": NAME}})
    knoten = tmp_path / "p.jsonl"
    vorschlaege = tmp_path / "p.json"
    pa.main(_argumente(tmp_path, vektoren, ereignisse, chats,
                       bestaetigung=bestaetigung) + ["--schreiben"])
    zeile = json.loads(knoten.read_text(encoding="utf-8").splitlines()[0])
    personen = zeile["personen"]
    assert personen[0]["kennung"] == "Person_001"
    assert personen[0]["name"] == NAME
    assert personen[0]["bestaetigt"] is True
    assert all(p["name"] is None for p in personen[1:])
    dokument = json.loads(vorschlaege.read_text(encoding="utf-8"))
    assert dokument["anzahl_bestaetigt"] == 1


def test_main_zaehlt_fremde_bestaetigungs_schluessel(tmp_path, capsys):
    vektoren, ereignisse, chats = _cli_dateien(tmp_path)
    bestaetigung = _json(tmp_path / "b.json",
                         {"bestaetigt": {"Beispielname": NAME}})
    pa.main(_argumente(tmp_path, vektoren, ereignisse, chats,
                       bestaetigung=bestaetigung))
    assert "fremde Bestaetigungs-Schluessel: 1" in capsys.readouterr().out


def test_main_trocken_schlaegt_schreiben(tmp_path, capsys):
    vektoren, ereignisse, chats = _cli_dateien(tmp_path)
    knoten = tmp_path / "p.jsonl"
    assert pa.main(_argumente(tmp_path, vektoren, ereignisse, chats)
                   + ["--trocken", "--schreiben"]) == 0
    assert not knoten.exists()
    assert "TROCKENLAUF" in capsys.readouterr().out


def test_main_namen_je_person_begrenzt(tmp_path):
    vektoren, ereignisse, chats = _cli_dateien(tmp_path)
    vorschlaege = tmp_path / "p.json"
    pa.main(_argumente(tmp_path, vektoren, ereignisse, chats)
            + ["--namen-je-person", "1", "--schreiben"])
    dokument = json.loads(vorschlaege.read_text(encoding="utf-8"))
    assert len(dokument["personen"][0]["namen"]) == 1


def test_main_negative_namen_je_person_ist_exit_2(tmp_path, capsys):
    vektoren, ereignisse, chats = _cli_dateien(tmp_path)
    assert pa.main(_argumente(tmp_path, vektoren, ereignisse, chats)
                   + ["--namen-je-person", "0"]) == 2
    assert "Fehler" in capsys.readouterr().err


def test_main_repo_ziel_ist_exit_2(tmp_path):
    vektoren, ereignisse, chats = _cli_dateien(tmp_path)
    ziel = REPO / "personen_andockung.jsonl"
    assert not ziel.exists(), "Vorbedingung: die Datei gibt es nicht"
    with pytest.raises(SystemExit) as fehler:
        pa.main(_argumente(tmp_path, vektoren, ereignisse, chats,
                           knoten=ziel) + ["--schreiben"])
    assert fehler.value.code == 2
    assert not ziel.exists()


def test_main_repo_ziel_ist_auch_im_trockenlauf_exit_2(tmp_path):
    vektoren, ereignisse, chats = _cli_dateien(tmp_path)
    with pytest.raises(SystemExit) as fehler:
        pa.main(_argumente(tmp_path, vektoren, ereignisse, chats,
                           vorschlaege=REPO / "docs" / "p.json"))
    assert fehler.value.code == 2


def test_main_fehlende_ereignisse_ist_exit_2(tmp_path, capsys):
    vektoren, _, chats = _cli_dateien(tmp_path)
    assert pa.main(_argumente(tmp_path, vektoren,
                              tmp_path / "gibtsnicht.jsonl", chats)) == 2
    assert "Fehler" in capsys.readouterr().err


def test_main_fehlende_vektoren_ist_exit_2(tmp_path, capsys):
    _, ereignisse, chats = _cli_dateien(tmp_path)
    assert pa.main(_argumente(tmp_path, tmp_path / "gibtsnicht.jsonl",
                              ereignisse, chats)) == 2
    assert "Fehler" in capsys.readouterr().err


def test_main_ohne_anlass_zaehlt_bilder_ohne_zuordnung(tmp_path, capsys):
    vektoren, _, chats = _cli_dateien(tmp_path)
    ereignisse = _jsonl(tmp_path / "leer.jsonl", [])
    pa.main(_argumente(tmp_path, vektoren, ereignisse, chats))
    ausgabe = capsys.readouterr().out
    assert "Bilder ohne Anlass-Zuordnung: 1" in ausgabe


# ── Quelltext: kein Netz, kein Bild, kein Nachrichteninhalt ──────────────

def _quelle() -> str:
    return WERKZEUG.read_text(encoding="utf-8")


def _baum():
    return ast.parse(_quelle())


def _namen_im_quelltext() -> set:
    namen: set = set()
    for knoten in ast.walk(_baum()):
        if isinstance(knoten, ast.Name):
            namen.add(knoten.id)
        elif isinstance(knoten, ast.Attribute):
            namen.add(knoten.attr)
        elif isinstance(knoten, ast.Import):
            for eintrag in knoten.names:
                namen.add(eintrag.name.split(".")[0])
        elif isinstance(knoten, ast.ImportFrom):
            namen.add((knoten.module or "").split(".")[0])
    return namen


def test_quelltext_importiert_nur_standardbibliothek_und_personen_cluster():
    erlaubt = {"argparse", "datetime", "importlib", "json", "os", "sys",
               "personen_cluster", "__future__"}
    importe: set = set()
    for knoten in ast.walk(_baum()):
        if isinstance(knoten, ast.Import):
            for eintrag in knoten.names:
                importe.add(eintrag.name.split(".")[0])
        elif isinstance(knoten, ast.ImportFrom):
            importe.add((knoten.module or "").split(".")[0])
    assert importe <= erlaubt, f"unerlaubter Import: {importe - erlaubt}"


def test_quelltext_ohne_netz_und_llm_namen():
    verboten = {"httpx", "requests", "socket", "subprocess", "aiohttp",
                "urlopen"}
    assert _namen_im_quelltext() & verboten == set()


def test_quelltext_ohne_url_und_ohne_schluessel():
    for verboten in ("http://", "https://", "urlopen(", "sk-", "token"):
        assert verboten not in _quelle(), f"Netz-/Schluesselspur: {verboten}"


def test_quelltext_oeffnet_keine_bilder():
    for verboten in ("cv2", "imageio", ".jpg", ".jpeg", ".png", ".heic",
                     "\"rb\"", "'rb'"):
        assert verboten not in _quelle(), f"Bildzugriff im Quelltext: {verboten}"


def test_quelltext_liest_keinen_nachrichteninhalt():
    for verboten in ("\"message\"", "'message'", "nachrichten_kennungen",
                     "nummer_maske", "nachrichtentext"):
        assert verboten not in _quelle(), f"Inhaltsfeld im Quelltext: {verboten}"


def test_quelltext_baut_keine_nummern_maske():
    quelle = _quelle()
    assert "*" * 3 not in quelle
    assert '"' + "*" * 3 + '"' not in quelle


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
    for verboten in ("def loeschen", "def delete", "def entfernen", "shutil",
                     "rmdir", "rm("):
        assert verboten not in _quelle(), f"Loeschfunktion im Quelltext: {verboten}"


def test_quelltext_schreibt_atomar():
    quelle = _quelle()
    assert "os.replace(" in quelle
    assert ".tmp" in quelle


def test_quelltext_verwaltet_keine_kennungen():
    # Kein Altbestand wird geschrieben — sonst verschoeben sich die Kennungen.
    assert "kennungen_schreiben" not in _quelle()


def test_quelltext_prueft_das_repo_ziel():
    quelle = _quelle()
    assert "pruefe_ausserhalb_repo" in quelle
    assert "personen_cluster" in quelle


def test_quelltext_setzt_nur_einen_zeitstempel():
    assert _quelle().count("datetime.datetime.now(") == 1


# ── Eingefrorene Funktionsnamen ──────────────────────────────────────────

def test_eingefrorene_funktionsnamen_sind_da():
    for name in ("vektoren_lesen", "ereignisse_lesen", "ereignis_index",
                 "personen_je_bild", "andocken", "kandidaten_je_person",
                 "vorschlaege_bauen", "bestaetigung_lesen",
                 "bestaetigung_anwenden", "knotenzeilen_bauen", "schreiben",
                 "bericht_bauen"):
        assert callable(getattr(pa, name)), name


def test_kommandozeilen_einstieg_ist_da():
    assert callable(pa.main) and callable(pa.haupt)
