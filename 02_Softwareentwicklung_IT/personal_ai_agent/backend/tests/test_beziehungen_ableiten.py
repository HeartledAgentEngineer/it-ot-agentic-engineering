"""Pruefungen fuer ``beziehungen_ableiten.py`` (N27 Schritt 5, 29.09.2026).

Alles OHNE Netz und ohne Bild: das Werkzeug liest nur lokale JSON/JSONL-Dateien
bzw. erfundene Beispieldaten; echte Dateien kommen hier **nicht** vor. Geprueft
werden die drei Aussage-Arten, das eingefrorene Zeilen-Schema, die
Quellenangaben, die ehrlichen Hinweise, die Zaehl-Invarianten der Uebersicht,
der Tages- und Bestaetigungs-Filter, das atomare Schreiben nur ausserhalb des
Repos, die Trockenlauf-Garantien, die Byte-Gleichheit zweier Schreiblaeufe mit
festem ``stand`` und der Quelltext (keine Netz-, Bild-, Loesch- oder
Verschiebefunktion; keine Kandidatenliste).

**Nur erfundene Beispielnamen, Beispielkennungen und Beispieldaten** — echte
Personen-, Orts- und Anlassnamen sowie echte Kennungen liegen ausserhalb des
Repos und kommen hier nicht vor.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_beziehungen_ableiten.py -q
"""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "beziehungen_ableiten.py"

STAND = "2026-09-29T03:00:00+02:00"
DATUM = "2014-03-30"
DATUM_ZWEI = "2016-05-04"

# Erfundene Beispielwerte (keine echten Namen, Orte oder Kennungen).
ANLASS = "2014-03-30_Beispiel-01"
ANLASS_ZWEI = "2016-05-04_Beispiel-02"
KENNUNG = "E-2014-03-30_Beispiel-01"
THEMA = "Beispielthema"
KATEGORIE = "Beispielkategorie"
ZIEL = "Agent/Fotos/2014/Beispielkategorie/2014-03-30 Beispielthema"

P1 = "Person_001"
P2 = "Person_002"
P3 = "Person_003"
P4 = "Person_004"
P5 = "Person_005"

KONTAKT_A = "Beispielkontakt A"
KONTAKT_B = "Beispielkontakt B"
KONTAKT_C = "Beispielkontakt C"
BESTAETIGTER_NAME = "Beispielname"


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


bd = _laden(WERKZEUG, "beziehungen_ableiten")

SCHEMA_SCHLUESSEL = {
    "art", "unterart", "datum", "anlass_id", "ereignis_kennung", "thema",
    "kategorie", "ziel_ordner", "personen", "beleg", "quellen", "hinweis",
    "stand",
}
PERSON_SCHLUESSEL = {"kennung", "name", "bestaetigt", "bilder", "gesichter"}


# ── kleine Helfer (erfundene Daten) ──────────────────────────────────────

def _person(kennung: str = P1, bilder: int = 1, gesichter: int = 1,
            name=None) -> dict:
    return {"kennung": kennung, "bilder": bilder, "gesichter": gesichter,
            "bestaetigt": bool(name), "name": name}


def _andockung_knoten(anlass_id: str = ANLASS, datum=DATUM,
                      personen=None) -> dict:
    return {"art": "personen_andockung", "anlass_id": anlass_id, "datum": datum,
            "kennung": "E-" + anlass_id, "personen": personen or [],
            "stand": STAND}


def _beteiligter(name: str = KONTAKT_A, nachrichten: int = 1) -> dict:
    return {"name": name, "nachrichten": nachrichten}


def _chat(chat_name: str = "Beispielgruppe", art: str = "gruppe",
          beteiligte=None, nachrichten: int = 5) -> dict:
    return {"chat_name": chat_name, "art": art, "nachrichten": nachrichten,
            "beteiligte": beteiligte or []}


def _chat_knoten(anlass_id: str = ANLASS_ZWEI, datum=DATUM_ZWEI,
                 chats=None) -> dict:
    return {"art": "chat_andockung", "anlass_id": anlass_id, "datum": datum,
            "chats": chats or []}


def _ereignis(anlass_id: str = ANLASS, datum=DATUM) -> dict:
    return {"art": "ereignis", "anlass_id": anlass_id, "kennung": "E-" + anlass_id,
            "datum": datum, "thema": THEMA, "kategorie": KATEGORIE,
            "ziel_ordner": ZIEL}


def _schreibe(pfad: Path, knoten) -> Path:
    zeilen = [json.dumps(k, ensure_ascii=False) for k in knoten]
    pfad.write_text("\n".join(zeilen) + ("\n" if zeilen else ""),
                    encoding="utf-8")
    return pfad


def _eingaben(tmp_path: Path, *, andockung=None, chats=None, ereignisse=None,
              bestaetigung=None) -> dict:
    """Erfundene Eingabedateien anlegen und den Pfadsatz zurueckgeben."""
    ordner = tmp_path / "eingabe"
    ordner.mkdir(parents=True, exist_ok=True)
    wege = {
        "andockung": str(_schreibe(ordner / "personen_andockung.jsonl",
                                   andockung if andockung is not None else [])),
        "chats": str(_schreibe(ordner / "chat_andockung.jsonl",
                               chats if chats is not None else [])),
        "ereignisse": str(_schreibe(ordner / "ereignisse.jsonl",
                                    ereignisse if ereignisse is not None else [])),
        "ausgabe": str(tmp_path / "aus" / "beziehungen.jsonl"),
        "uebersicht": str(tmp_path / "aus" / "beziehungen.json"),
    }
    if bestaetigung is not None:
        weg = ordner / "personen_bestaetigt.json"
        weg.write_text(json.dumps(bestaetigung, ensure_ascii=False),
                       encoding="utf-8")
        wege["bestaetigung"] = str(weg)
    else:
        wege["bestaetigung"] = str(ordner / "personen_bestaetigt.json")
    return wege


def _argv(wege: dict, *rest) -> list:
    return ["--andockung", wege["andockung"], "--chat-andockung", wege["chats"],
            "--ereignisse", wege["ereignisse"],
            "--bestaetigung", wege["bestaetigung"],
            "--ausgabe", wege["ausgabe"],
            "--ausgabe-uebersicht", wege["uebersicht"], *rest]


def _quelle() -> str:
    return WERKZEUG.read_text(encoding="utf-8")


def _baum() -> ast.Module:
    return ast.parse(_quelle())


def _funktionen() -> list:
    return [n for n in ast.walk(_baum()) if isinstance(n, ast.FunctionDef)]


def _importe() -> set:
    namen: set = set()
    for n in ast.walk(_baum()):
        if isinstance(n, ast.Import):
            for a in n.names:
                namen.add(a.name.split(".")[0])
        elif isinstance(n, ast.ImportFrom) and n.module:
            namen.add(n.module.split(".")[0])
    return namen


def _aufrufe() -> set:
    namen: set = set()
    for n in ast.walk(_baum()):
        if isinstance(n, ast.Call):
            ziel = n.func
            if isinstance(ziel, ast.Attribute):
                namen.add(ziel.attr)
            elif isinstance(ziel, ast.Name):
                namen.add(ziel.id)
    return namen


# ── Modulkopf, Konstanten, Wiederverwendung ──────────────────────────────

def test_modul_zweitname_haupt_ist_main():
    assert bd.haupt is bd.main


def test_modul_hat_main():
    assert callable(bd.main)


def test_art_konstanten():
    assert bd.ART_AUSSAGE == "beziehung"
    assert bd.ART_UEBERSICHT == "beziehungen"


def test_unterart_namen():
    assert bd.UNTERART_FOTOS == "fotos"
    assert bd.UNTERART_CHAT == "gemeinsam_im_chat"
    assert bd.UNTERART_FOTOS_UND_CHAT == "fotos_und_chat"


def test_unterart_reihenfolge():
    assert bd.UNTERART_REIHENFOLGE == ("fotos", "gemeinsam_im_chat",
                                       "fotos_und_chat")


def test_unterart_rang_fest():
    assert bd.UNTERART_RANG["fotos"] == 0
    assert bd.UNTERART_RANG["gemeinsam_im_chat"] == 1
    assert bd.UNTERART_RANG["fotos_und_chat"] == 2


def test_hinweise_sind_deutsch_und_getrennt():
    assert "Bildbeleg" in bd.HINWEIS_FOTOS
    assert "Mitgliedschaft" in bd.HINWEIS_CHAT
    assert bd.HINWEIS_FOTOS != bd.HINWEIS_CHAT
    assert bd.HINWEIS_FOTOS_UND_CHAT not in (bd.HINWEIS_FOTOS, bd.HINWEIS_CHAT)


def test_hinweis_block_kennt_alle_unterarten():
    for unterart in bd.UNTERART_REIHENFOLGE:
        assert unterart in bd.HINWEIS_JE_UNTERART


def test_aussage_schluessel_sind_das_schema():
    assert set(bd.AUSSAGE_SCHLUESSEL) == SCHEMA_SCHLUESSEL


def test_aussage_person_schluessel():
    assert set(bd.AUSSAGE_PERSON_SCHLUESSEL) == PERSON_SCHLUESSEL


def test_uebersicht_schluessel_konstanten():
    assert set(bd.UEBERSICHT_SCHLUESSEL) == {
        "art", "stand", "anzahl", "anzahl_personen_kennungen",
        "anzahl_namen_bestaetigt", "anzahl_kontakte", "datum_von", "datum_bis",
        "quellen", "hinweis"}


def test_standardpfade_ausserhalb_repo():
    for weg in (bd.STANDARD_EREIGNISSE, bd.STANDARD_ANDOCKUNG,
                bd.STANDARD_CHAT_ANDOCKUNG, bd.STANDARD_BESTAETIGUNG,
                bd.STANDARD_AUSGABE, bd.STANDARD_AUSGABE_UEBERSICHT):
        assert str(REPO) not in weg
        assert "foto_sortierung" in weg


def test_standard_ausgabe_dateinamen():
    assert bd.STANDARD_AUSGABE.endswith("beziehungen.jsonl")
    assert bd.STANDARD_AUSGABE_UEBERSICHT.endswith("beziehungen.json")


def test_kennung_muster_wie_nachbarmodul():
    assert bd.KENNUNG_MUSTER == r"^Person_\d{3}$"


def test_bestaetigung_lesen_ist_wiederverwendet():
    # Wiederverwendung, nicht Nachbau: die Funktion stammt aus dem Nachbarmodul.
    datei = bd.bestaetigung_lesen.__globals__.get("__file__", "")
    assert datei.endswith("personen_andocken.py")
    assert bd.bestaetigung_lesen.__qualname__ == "bestaetigung_lesen"


def test_personenfehler_ist_wiederverwendet():
    assert issubclass(bd.PersonenFehler, Exception)
    assert bd.PersonenFehler.__name__ == "PersonenFehler"


def test_name_unbekannt_konstante():
    assert bd.NAME_UNBEKANNT == "unbekannt"


# ── Quelltext-Waechter ───────────────────────────────────────────────────

def test_quelltext_keine_kandidatenliste():
    verboten = "personen_" + "vorschlaege.json"
    assert verboten not in _quelle()


def test_quelltext_kein_loeschen_ausser_schreiben():
    text = _quelle()
    for fn in _funktionen():
        if fn.name == "schreiben":
            continue
        stelle = ast.get_source_segment(text, fn) or ""
        assert "os.remove" not in stelle, fn.name
        assert "os.unlink" not in stelle, fn.name
        assert "os.rmdir" not in stelle, fn.name
        assert "os.removedirs" not in stelle, fn.name
        assert "rmtree" not in stelle, fn.name


def test_quelltext_keine_loeschfunktion_im_namen():
    for fn in _funktionen():
        assert "loesch" not in fn.name.lower()
        assert "delete" not in fn.name.lower()


def test_quelltext_kein_verschieben():
    text = _quelle()
    for fn in _funktionen():
        if fn.name == "schreiben":
            continue
        stelle = ast.get_source_segment(text, fn) or ""
        assert "os.rename" not in stelle, fn.name
        assert "shutil" not in stelle, fn.name
    assert "shutil.move" not in text


def test_quelltext_kein_netz_import():
    verboten = {"requests", "httpx", "urllib", "urllib3", "socket", "aiohttp",
                "http", "ftplib", "smtplib", "xmlrpc", "pcloud"}
    assert not (_importe() & verboten)


def test_quelltext_kein_bild_import():
    verboten = {"PIL", "cv2", "imageio", "matplotlib", "skimage"}
    assert not (_importe() & verboten)


def test_quelltext_keine_downloadfunktion():
    for name in _aufrufe():
        assert "download" not in name.lower()
        assert "urlopen" not in name.lower()
        assert "retrieve" not in name.lower()


def test_quelltext_liest_keine_nummernmaske():
    assert "nummer_maske" not in _quelle()
    assert "nummern_maske" not in _quelle()


def test_quelltext_nutzt_nachbarmodul():
    text = _quelle()
    assert "personen_andocken" in text
    assert "bestaetigung_lesen" in text


def test_quelltext_liest_keine_nachrichtenkennungen():
    assert "nachrichten_kennungen" not in _quelle()


def test_quelltext_liest_keinen_nachrichtentext():
    for verboten in ("nachricht_text", "text_lesen", "msg_text", "inhalt_lesen"):
        assert verboten not in _quelle()


# ── kleine Helfer ────────────────────────────────────────────────────────

def test_text_liest_nur_text():
    assert bd._text("  hallo ") == "hallo"
    assert bd._text(None) == ""
    assert bd._text(7) == ""
    assert bd._text("") == ""


def test_als_int_ignoriert_bool():
    assert bd._als_int(True) is None
    assert bd._als_int(False) is None


def test_als_int_liest_zahlen():
    assert bd._als_int(5) == 5
    assert bd._als_int(" 7 ") == 7
    assert bd._als_int("x") is None
    assert bd._als_int(None) is None


def test_ist_person_muster():
    assert bd._ist_person("Person_001")
    assert bd._ist_person("Person_999")


def test_ist_person_fremd():
    assert not bd._ist_person("Person_01")
    assert not bd._ist_person("Person_0001")
    assert not bd._ist_person("Beispiel")
    assert not bd._ist_person(None)


def test_ist_maske_sterne():
    assert bd._ist_maske("***1234")
    assert not bd._ist_maske(KONTAKT_A)


def test_ist_maske_ziffern():
    assert bd._ist_maske("491234567")
    assert not bd._ist_maske("Beispiel")


def test_datum_lesen_gueltig():
    assert bd._datum_lesen(DATUM) == DATUM
    assert bd._datum_lesen(" 2020-01-02 ") == "2020-01-02"


def test_datum_lesen_ungueltig():
    assert bd._datum_lesen("30.03.2014") is None
    assert bd._datum_lesen("2014-13-01") is None
    assert bd._datum_lesen("2014-3-1") is None
    assert bd._datum_lesen("") is None
    assert bd._datum_lesen(None) is None


def test_zahl_mit_tausenderpunkten():
    assert bd._zahl(15051) == "15.051"
    assert bd._zahl(23) == "23"


def test_zahl_unbrauchbar():
    assert bd._zahl(None) == "None"


def test_stand_jz_liest_text():
    assert bd._stand_jz(STAND) == STAND


def test_stand_jz_ohne_angabe_setzt_zeit():
    wert = bd._stand_jz(None)
    assert isinstance(wert, str) and len(wert) > 10


# ── Leser ────────────────────────────────────────────────────────────────

def test_lesen_zeilennummern(tmp_path):
    weg = _schreibe(tmp_path / "a.jsonl", [_andockung_knoten(), _andockung_knoten(
        anlass_id=ANLASS_ZWEI, datum=DATUM_ZWEI)])
    gelesen = bd.personen_andockung_lesen(str(weg))
    assert [nummer for nummer, _ in gelesen] == [1, 2]


def test_lesen_dateiname(tmp_path):
    weg = _schreibe(tmp_path / "personen_andockung.jsonl", [_andockung_knoten()])
    gelesen = bd.personen_andockung_lesen(str(weg))
    assert gelesen.dateiname == "personen_andockung.jsonl"


def test_lesen_defekte_zeilen_zaehlen(tmp_path):
    weg = tmp_path / "mit_defekt.jsonl"
    weg.write_text('{"anlass_id": "a"}\n\nkein json\n[1, 2]\n'
                   '{"anlass_id": "b"}\n', encoding="utf-8")
    gelesen = bd.personen_andockung_lesen(str(weg))
    assert len(gelesen) == 2
    assert gelesen.defekt == 3
    assert [nummer for nummer, _ in gelesen] == [1, 5]


def test_lesen_fehlende_datei(tmp_path):
    with pytest.raises(bd.PersonenFehler):
        bd.personen_andockung_lesen(str(tmp_path / "fehlt.jsonl"))


def test_lesen_leerer_pfad():
    with pytest.raises(bd.PersonenFehler):
        bd.chat_andockung_lesen("")


def test_lesen_ohne_pfad_typ():
    with pytest.raises(bd.PersonenFehler):
        bd.ereignisse_lesen(None)


def test_lesen_leere_datei(tmp_path):
    weg = _schreibe(tmp_path / "leer.jsonl", [])
    gelesen = bd.chat_andockung_lesen(str(weg))
    assert list(gelesen) == []
    assert gelesen.defekt == 0


def test_ereignisse_lesen_index(tmp_path):
    weg = _schreibe(tmp_path / "ereignisse.jsonl", [_ereignis()])
    index = bd.ereignisse_lesen(str(weg))
    assert index[ANLASS]["kennung"] == KENNUNG
    assert index[ANLASS]["thema"] == THEMA
    assert index[ANLASS]["kategorie"] == KATEGORIE
    assert index[ANLASS]["ziel_ordner"] == ZIEL


def test_ereignisse_lesen_ohne_anlass_zaehlt_defekt(tmp_path):
    weg = tmp_path / "ereignisse.jsonl"
    weg.write_text('{"art": "ereignis"}\n' +
                   json.dumps(_ereignis(), ensure_ascii=False) + "\n",
                   encoding="utf-8")
    index = bd.ereignisse_lesen(str(weg))
    assert len(index) == 1
    assert index.defekt == 1


def test_ereignisse_lesen_doppelte_zaehlt(tmp_path):
    weg = _schreibe(tmp_path / "ereignisse.jsonl", [_ereignis(), _ereignis()])
    index = bd.ereignisse_lesen(str(weg))
    assert len(index) == 1
    assert index.doppelte == 1


def test_ereignisse_lesen_fehlende_datei(tmp_path):
    with pytest.raises(bd.PersonenFehler):
        bd.ereignisse_lesen(str(tmp_path / "nichts.jsonl"))


def test_ereignis_index_durchreichen():
    index = {ANLASS: {"kennung": KENNUNG, "thema": THEMA, "kategorie": KATEGORIE,
                      "ziel_ordner": ZIEL, "datum": DATUM}}
    assert bd.ereignis_index(index) == index


def test_ereignis_index_aus_liste():
    index = bd.ereignis_index([_ereignis()])
    assert index[ANLASS]["thema"] == THEMA


def test_ereignis_index_leer():
    assert bd.ereignis_index(None) == {}
    assert bd.ereignis_index([]) == {}


def test_ereignis_index_erste_gewinnt():
    a = _ereignis()
    b = _ereignis()
    b["thema"] = "Zweitthema"
    index = bd.ereignis_index([a, b])
    assert index[ANLASS]["thema"] == THEMA


def test_ereignis_index_ignoriert_fremde():
    index = bd.ereignis_index([{"ohne": "anlass"}, "kein dict", 7])
    assert index == {}


# ── Kontaktnamen ─────────────────────────────────────────────────────────

def test_kontaktnamen_liest_namen():
    namen = bd.kontaktnamen(_chat(beteiligte=[_beteiligter(KONTAKT_A, 3),
                                               _beteiligter(KONTAKT_B, 4)]))
    assert dict(namen) == {KONTAKT_A: 3, KONTAKT_B: 4}


def test_kontaktnamen_unbekannt_zaehlt_nicht():
    namen = bd.kontaktnamen(_chat(beteiligte=[_beteiligter("unbekannt", 9),
                                               _beteiligter(KONTAKT_A, 1)]))
    assert dict(namen) == {KONTAKT_A: 1}
    assert namen.uebersprungen == 1


def test_kontaktnamen_leer_zaehlt_nicht():
    namen = bd.kontaktnamen(_chat(beteiligte=[_beteiligter("", 2),
                                               _beteiligter("   ", 2)]))
    assert dict(namen) == {}
    assert namen.uebersprungen == 2


def test_kontaktnamen_maske_zaehlt_nicht():
    namen = bd.kontaktnamen(_chat(beteiligte=[_beteiligter("***1234", 2),
                                               _beteiligter("4912345", 2)]))
    assert dict(namen) == {}
    assert namen.uebersprungen == 2


def test_kontaktnamen_doppelte_summiert():
    namen = bd.kontaktnamen(_chat(beteiligte=[_beteiligter(KONTAKT_A, 2),
                                               _beteiligter(KONTAKT_A, 3)]))
    assert dict(namen) == {KONTAKT_A: 5}
    assert namen.doppelte == 1


def test_kontaktnamen_nicht_dict_zaehlt():
    namen = bd.kontaktnamen(_chat(beteiligte=["kein dict", 7]))
    assert dict(namen) == {}
    assert namen.uebersprungen == 2


def test_kontaktnamen_ohne_nachrichten():
    namen = bd.kontaktnamen({"beteiligte": [{"name": KONTAKT_A}]})
    assert dict(namen) == {KONTAKT_A: 0}


def test_kontaktnamen_leerer_chat():
    namen = bd.kontaktnamen({})
    assert dict(namen) == {}


# ── Unterart fotos ───────────────────────────────────────────────────────

def test_fotos_drei_personen_drei_paare():
    knoten = _andockung_knoten(personen=[_person(P1), _person(P2), _person(P3)])
    assert len(bd.fotos_aussagen([knoten], {}, None, STAND)) == 3


def test_fotos_fuenf_personen_zehn_paare():
    personen = [_person(k) for k in (P1, P2, P3, P4, P5)]
    knoten = _andockung_knoten(personen=personen)
    assert len(bd.fotos_aussagen([knoten], {}, None, STAND)) == 10


def test_fotos_eine_person_kein_paar():
    knoten = _andockung_knoten(personen=[_person(P1)])
    assert bd.fotos_aussagen([knoten], {}, None, STAND) == []


def test_fotos_ohne_person():
    knoten = _andockung_knoten(personen=[])
    assert bd.fotos_aussagen([knoten], {}, None, STAND) == []


def test_fotos_art_und_unterart():
    knoten = _andockung_knoten(personen=[_person(P1), _person(P2)])
    aussage = bd.fotos_aussagen([knoten], {}, None, STAND)[0]
    assert aussage["art"] == "beziehung"
    assert aussage["unterart"] == "fotos"


def test_fotos_name_null_ohne_bestaetigung():
    knoten = _andockung_knoten(personen=[_person(P1), _person(P2)])
    aussage = bd.fotos_aussagen([knoten], {}, {}, STAND)[0]
    for person in aussage["personen"]:
        assert person["name"] is None
        assert person["bestaetigt"] is False


def test_fotos_name_gesetzt_mit_bestaetigung():
    knoten = _andockung_knoten(personen=[_person(P1), _person(P2)])
    aussage = bd.fotos_aussagen([knoten], {}, {P1: BESTAETIGTER_NAME}, STAND)[0]
    namen = {p["kennung"]: p["name"] for p in aussage["personen"]}
    assert namen == {P1: BESTAETIGTER_NAME, P2: None}
    bestaetigt = {p["kennung"]: p["bestaetigt"] for p in aussage["personen"]}
    assert bestaetigt == {P1: True, P2: False}


def test_fotos_beleg_summen():
    knoten = _andockung_knoten(personen=[_person(P1, 3, 4), _person(P2, 2, 1)])
    beleg = bd.fotos_aussagen([knoten], {}, None, STAND)[0]["beleg"]
    assert beleg == {"bilder": 5, "gesichter": 5}


def test_fotos_paar_enthaelt_beide_kennungen():
    knoten = _andockung_knoten(personen=[_person(P1), _person(P2)])
    aussage = bd.fotos_aussagen([knoten], {}, None, STAND)[0]
    assert [p["kennung"] for p in aussage["personen"]] == [P1, P2]


def test_fotos_ereignisfelder():
    knoten = _andockung_knoten(personen=[_person(P1), _person(P2)])
    index = {ANLASS: {"kennung": KENNUNG, "thema": THEMA, "kategorie": KATEGORIE,
                      "ziel_ordner": ZIEL, "datum": DATUM}}
    aussage = bd.fotos_aussagen([knoten], index, None, STAND)[0]
    assert aussage["ereignis_kennung"] == KENNUNG
    assert aussage["thema"] == THEMA
    assert aussage["kategorie"] == KATEGORIE
    assert aussage["ziel_ordner"] == ZIEL


def test_fotos_ohne_ereignis_null():
    knoten = _andockung_knoten(personen=[_person(P1), _person(P2)])
    aussage = bd.fotos_aussagen([knoten], {}, None, STAND)[0]
    assert aussage["ereignis_kennung"] is None
    assert aussage["thema"] == ""
    assert aussage["ziel_ordner"] is None


def test_fotos_hinweis():
    knoten = _andockung_knoten(personen=[_person(P1), _person(P2)])
    aussage = bd.fotos_aussagen([knoten], {}, None, STAND)[0]
    assert aussage["hinweis"] == bd.HINWEIS_FOTOS


def test_fotos_stand_durchgereicht():
    knoten = _andockung_knoten(personen=[_person(P1), _person(P2)])
    aussage = bd.fotos_aussagen([knoten], {}, None, STAND)[0]
    assert aussage["stand"] == STAND


def test_fotos_quellen_zeilennummer(tmp_path):
    weg = _schreibe(tmp_path / "personen_andockung.jsonl",
                    [_andockung_knoten(personen=[_person(P1), _person(P2)])])
    gelesen = bd.personen_andockung_lesen(str(weg))
    aussage = bd.fotos_aussagen(gelesen, {}, None, STAND)[0]
    assert aussage["quellen"] == {"andockung": "personen_andockung.jsonl:1"}


def test_fotos_doppelte_kennung_fasst_zusammen():
    knoten = _andockung_knoten(personen=[_person(P1, 1, 1), _person(P1, 2, 2),
                                         _person(P2, 1, 1)])
    aussagen = bd.fotos_aussagen([knoten], {}, None, STAND)
    assert len(aussagen) == 1
    personen = {p["kennung"]: p for p in aussagen[0]["personen"]}
    assert personen[P1]["bilder"] == 3
    assert personen[P1]["gesichter"] == 3


def test_fotos_ohne_anlass_id_trotzdem_aussage():
    knoten = _andockung_knoten(anlass_id="", personen=[_person(P1), _person(P2)])
    aussagen = bd.fotos_aussagen([knoten], {}, None, STAND)
    assert len(aussagen) == 1
    assert aussagen[0]["anlass_id"] == ""


def test_fotos_datum_uebernommen():
    knoten = _andockung_knoten(personen=[_person(P1), _person(P2)])
    assert bd.fotos_aussagen([knoten], {}, None, STAND)[0]["datum"] == DATUM


def test_fotos_unlesbares_datum_wird_null():
    knoten = _andockung_knoten(datum="30.03.2014",
                               personen=[_person(P1), _person(P2)])
    assert bd.fotos_aussagen([knoten], {}, None, STAND)[0]["datum"] is None


# ── Unterart gemeinsam_im_chat ───────────────────────────────────────────

def _chats_mit(*chat_listen):
    return _chat_knoten(chats=list(chat_listen))


def test_chat_zwei_kontakte_ein_paar():
    knoten = _chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A),
                                           _beteiligter(KONTAKT_B)]))
    assert len(bd.chat_aussagen([knoten], {}, STAND)) == 1


def test_chat_drei_kontakte_drei_paare():
    knoten = _chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A),
                                           _beteiligter(KONTAKT_B),
                                           _beteiligter(KONTAKT_C)]))
    assert len(bd.chat_aussagen([knoten], {}, STAND)) == 3


def test_chat_vier_kontakte_sechs_paare():
    knoten = _chats_mit(_chat(beteiligte=[_beteiligter(n)
                                           for n in (KONTAKT_A, KONTAKT_B,
                                                     KONTAKT_C, "Beispielkontakt D")]))
    assert len(bd.chat_aussagen([knoten], {}, STAND)) == 6


def test_chat_ein_kontakt_kein_paar():
    knoten = _chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A)]))
    assert bd.chat_aussagen([knoten], {}, STAND) == []


def test_chat_unbekannt_zaehlt_nicht_als_kontakt():
    knoten = _chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A),
                                           _beteiligter("unbekannt")]))
    assert bd.chat_aussagen([knoten], {}, STAND) == []


def test_chat_beleg_nachrichten_summe():
    knoten = _chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A, 3),
                                           _beteiligter(KONTAKT_B, 4)]))
    beleg = bd.chat_aussagen([knoten], {}, STAND)[0]["beleg"]
    assert beleg["nachrichten"] == 7


def test_chat_beleg_chat_name_und_art():
    knoten = _chats_mit(_chat(chat_name="Beispielrunde", art="einzel",
                              beteiligte=[_beteiligter(KONTAKT_A),
                                          _beteiligter(KONTAKT_B)]))
    beleg = bd.chat_aussagen([knoten], {}, STAND)[0]["beleg"]
    assert beleg["chat_name"] == "Beispielrunde"
    assert beleg["chat_art"] == "einzel"


def test_chat_unterart_und_art():
    knoten = _chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A),
                                           _beteiligter(KONTAKT_B)]))
    aussage = bd.chat_aussagen([knoten], {}, STAND)[0]
    assert aussage["unterart"] == "gemeinsam_im_chat"
    assert aussage["art"] == "beziehung"


def test_chat_kontakt_ohne_kennung():
    knoten = _chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A),
                                           _beteiligter(KONTAKT_B)]))
    aussage = bd.chat_aussagen([knoten], {}, STAND)[0]
    for person in aussage["personen"]:
        assert person["kennung"] is None
        assert person["bilder"] == 0
        assert person["gesichter"] == 0


def test_chat_kontakt_traegt_namen():
    knoten = _chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A),
                                           _beteiligter(KONTAKT_B)]))
    aussage = bd.chat_aussagen([knoten], {}, STAND)[0]
    assert sorted(p["name"] for p in aussage["personen"]) == \
        [KONTAKT_A, KONTAKT_B]


def test_chat_kontakte_nach_namen_sortiert():
    knoten = _chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_C),
                                           _beteiligter(KONTAKT_A)]))
    aussage = bd.chat_aussagen([knoten], {}, STAND)[0]
    assert [p["name"] for p in aussage["personen"]] == [KONTAKT_A, KONTAKT_C]


def test_chat_hinweis():
    knoten = _chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A),
                                           _beteiligter(KONTAKT_B)]))
    assert bd.chat_aussagen([knoten], {}, STAND)[0]["hinweis"] == bd.HINWEIS_CHAT


def test_chat_zwei_chats_getrennt():
    knoten = _chats_mit(
        _chat(beteiligte=[_beteiligter(KONTAKT_A), _beteiligter(KONTAKT_B)]),
        _chat(beteiligte=[_beteiligter(KONTAKT_A), _beteiligter(KONTAKT_C)]))
    aussagen = bd.chat_aussagen([knoten], {}, STAND)
    assert len(aussagen) == 2
    paare = sorted(tuple(sorted(p["name"] for p in a["personen"]))
                   for a in aussagen)
    assert paare == [(KONTAKT_A, KONTAKT_B), (KONTAKT_A, KONTAKT_C)]


def test_chat_quellen_zeilennummer(tmp_path):
    weg = _schreibe(tmp_path / "chat_andockung.jsonl", [_chats_mit(
        _chat(beteiligte=[_beteiligter(KONTAKT_A), _beteiligter(KONTAKT_B)]))])
    gelesen = bd.chat_andockung_lesen(str(weg))
    aussage = bd.chat_aussagen(gelesen, {}, STAND)[0]
    assert aussage["quellen"] == {"chat": "chat_andockung.jsonl:1"}


def test_chat_leerer_anlass():
    knoten = _chat_knoten(chats=[])
    assert bd.chat_aussagen([knoten], {}, STAND) == []


def test_chat_ohne_personenliste_noch_aussage():
    knoten = _chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A),
                                           _beteiligter(KONTAKT_B)]))
    aussage = bd.chat_aussagen([knoten], {}, STAND)[0]
    assert aussage["anlass_id"] == ANLASS_ZWEI
    assert aussage["datum"] == DATUM_ZWEI


# ── Unterart fotos_und_chat ──────────────────────────────────────────────

def test_fc_eine_person_zwei_kontakte():
    andockung = [_andockung_knoten(personen=[_person(P1, 2, 3)])]
    chats = [_chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A, 4),
                                          _beteiligter(KONTAKT_B, 5)]))]
    # Anlass-IDs muessen zusammenpassen.
    chats[0]["anlass_id"] = ANLASS
    chats[0]["datum"] = DATUM
    aussagen = bd.fotos_und_chat_aussagen(andockung, chats, {}, None, STAND)
    assert len(aussagen) == 2


def test_fc_zwei_personen_zwei_kontakte():
    andockung = [_andockung_knoten(personen=[_person(P1), _person(P2)])]
    chats = [_chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A),
                                          _beteiligter(KONTAKT_B)]))]
    chats[0]["anlass_id"] = ANLASS
    chats[0]["datum"] = DATUM
    aussagen = bd.fotos_und_chat_aussagen(andockung, chats, {}, None, STAND)
    assert len(aussagen) == 4


def test_fc_ohne_person():
    andockung = [_andockung_knoten(personen=[])]
    chats = [_chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A),
                                          _beteiligter(KONTAKT_B)]))]
    chats[0]["anlass_id"] = ANLASS
    assert bd.fotos_und_chat_aussagen(andockung, chats, {}, None, STAND) == []


def test_fc_ohne_kontakt():
    andockung = [_andockung_knoten(personen=[_person(P1), _person(P2)])]
    chats = [_chats_mit(_chat(beteiligte=[_beteiligter("unbekannt")]))]
    chats[0]["anlass_id"] = ANLASS
    assert bd.fotos_und_chat_aussagen(andockung, chats, {}, None, STAND) == []


def test_fc_beleg_aus_beiden_quellen():
    andockung = [_andockung_knoten(personen=[_person(P1, 2, 3)])]
    chats = [_chats_mit(_chat(chat_name="Beispielrunde", art="gruppe",
                              beteiligte=[_beteiligter(KONTAKT_A, 4)]))]
    chats[0]["anlass_id"] = ANLASS
    chats[0]["datum"] = DATUM
    aussage = bd.fotos_und_chat_aussagen(andockung, chats, {}, None, STAND)[0]
    assert aussage["beleg"]["bilder"] == 2
    assert aussage["beleg"]["gesichter"] == 3
    assert aussage["beleg"]["nachrichten"] == 4
    assert aussage["beleg"]["chat_name"] == "Beispielrunde"
    assert aussage["beleg"]["chat_art"] == "gruppe"


def test_fc_quellen_beide_dateien(tmp_path):
    andock = _schreibe(tmp_path / "personen_andockung.jsonl",
                       [_andockung_knoten(personen=[_person(P1)])])
    chat = _schreibe(tmp_path / "chat_andockung.jsonl", [_chats_mit(
        _chat(beteiligte=[_beteiligter(KONTAKT_A)]))])
    gelesen_a = bd.personen_andockung_lesen(str(andock))
    gelesen_c = bd.chat_andockung_lesen(str(chat))
    # Anlass-IDs angleichen (der erfundene Chat-Knoten traegt eine andere).
    gelesen_c[0][1]["anlass_id"] = ANLASS
    gelesen_c[0][1]["datum"] = DATUM
    aussage = bd.fotos_und_chat_aussagen(gelesen_a, gelesen_c, {}, None,
                                         STAND)[0]
    assert aussage["quellen"] == {"andockung": "personen_andockung.jsonl:1",
                                  "chat": "chat_andockung.jsonl:1"}


def test_fc_unterart_und_hinweis():
    andockung = [_andockung_knoten(personen=[_person(P1)])]
    chats = [_chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A)]))]
    chats[0]["anlass_id"] = ANLASS
    aussage = bd.fotos_und_chat_aussagen(andockung, chats, {}, None, STAND)[0]
    assert aussage["unterart"] == "fotos_und_chat"
    assert aussage["hinweis"] == bd.HINWEIS_FOTOS_UND_CHAT


def test_fc_kontakte_ueber_chats_zusammengefuehrt():
    andockung = [_andockung_knoten(personen=[_person(P1)])]
    chats = [_chats_mit(
        _chat(beteiligte=[_beteiligter(KONTAKT_A, 2)]),
        _chat(beteiligte=[_beteiligter(KONTAKT_A, 3)]))]
    chats[0]["anlass_id"] = ANLASS
    chats[0]["datum"] = DATUM
    aussagen = bd.fotos_und_chat_aussagen(andockung, chats, {}, None, STAND)
    assert len(aussagen) == 1
    assert aussagen[0]["beleg"]["nachrichten"] == 5


def test_fc_personen_behalten_namen_regel():
    andockung = [_andockung_knoten(personen=[_person(P1)])]
    chats = [_chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A)]))]
    chats[0]["anlass_id"] = ANLASS
    aussage = bd.fotos_und_chat_aussagen(andockung, chats, {}, {P1: BESTAETIGTER_NAME},
                                         STAND)[0]
    eintraege = {p["kennung"]: p for p in aussage["personen"]}
    assert eintraege[P1]["name"] == BESTAETIGTER_NAME
    assert eintraege[None]["name"] == KONTAKT_A
    assert eintraege[None]["bestaetigt"] is True


def test_fc_andere_anlaesse_bleiben_getrennt():
    andockung = [_andockung_knoten(personen=[_person(P1)])]
    chats = [_chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A)]))]
    chats[0]["anlass_id"] = ANLASS_ZWEI
    chats[0]["datum"] = DATUM_ZWEI
    assert bd.fotos_und_chat_aussagen(andockung, chats, {}, None, STAND) == []


# ── beziehungen_bauen ────────────────────────────────────────────────────

def _beispielbestand():
    andockung = [_andockung_knoten(personen=[_person(P1), _person(P2)]),
                 _andockung_knoten(anlass_id=ANLASS_ZWEI, datum=DATUM_ZWEI,
                                   personen=[_person(P3)])]
    chats = [_chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A),
                                          _beteiligter(KONTAKT_B)]))]
    chats[0]["anlass_id"] = ANLASS
    chats[0]["datum"] = DATUM
    return andockung, chats


def test_bauen_fuehrt_drei_unterarten():
    andockung, chats = _beispielbestand()
    aussagen = bd.beziehungen_bauen(andockung, chats, {}, None, STAND)
    unterarten = {a["unterart"] for a in aussagen}
    assert unterarten == {"fotos", "gemeinsam_im_chat", "fotos_und_chat"}


def test_bauen_summe():
    andockung, chats = _beispielbestand()
    aussagen = bd.beziehungen_bauen(andockung, chats, {}, None, STAND)
    # fotos: 1 Paar · chat: 1 Paar · fotos+chat: 2 Personen x 2 Kontakte = 4
    assert len(aussagen) == 6


def test_bauen_reihenfolge_stabil():
    andockung, chats = _beispielbestand()
    a = bd.beziehungen_bauen(andockung, chats, {}, None, STAND)
    b = bd.beziehungen_bauen(andockung, chats, {}, None, STAND)
    assert a == b


def test_bauen_stand_durchgereicht():
    andockung, chats = _beispielbestand()
    aussagen = bd.beziehungen_bauen(andockung, chats, {}, None, STAND)
    assert all(a["stand"] == STAND for a in aussagen)


def test_bauen_defekt_zaehlt(tmp_path):
    andock = tmp_path / "personen_andockung.jsonl"
    andock.write_text("kein json\n", encoding="utf-8")
    chat = _schreibe(tmp_path / "chat_andockung.jsonl", [])
    gelesen_a = bd.personen_andockung_lesen(str(andock))
    gelesen_c = bd.chat_andockung_lesen(str(chat))
    aussagen = bd.beziehungen_bauen(gelesen_a, gelesen_c, {}, None, STAND)
    assert aussagen.defekt == 1


def test_bauen_veraendert_eingaben_nicht():
    andockung, chats = _beispielbestand()
    vorher_a = json.dumps(andockung, sort_keys=True)
    vorher_c = json.dumps(chats, sort_keys=True)
    bd.beziehungen_bauen(andockung, chats, {}, None, STAND)
    assert json.dumps(andockung, sort_keys=True) == vorher_a
    assert json.dumps(chats, sort_keys=True) == vorher_c


def test_bauen_ordnung_nach_datum():
    andockung = [_andockung_knoten(anlass_id=ANLASS_ZWEI, datum=DATUM_ZWEI,
                                   personen=[_person(P1), _person(P2)]),
                 _andockung_knoten(anlass_id=ANLASS, datum=DATUM,
                                   personen=[_person(P3), _person(P4)])]
    aussagen = bd.beziehungen_bauen(andockung, [], {}, None, STAND)
    assert [a["datum"] for a in aussagen] == [DATUM, DATUM_ZWEI]


def test_bauen_leer():
    aussagen = bd.beziehungen_bauen([], [], {}, None, STAND)
    assert list(aussagen) == []
    assert aussagen.defekt == 0


def test_bauen_jede_zeile_hat_das_schema():
    andockung, chats = _beispielbestand()
    for aussage in bd.beziehungen_bauen(andockung, chats, {}, None, STAND):
        assert set(aussage) == SCHEMA_SCHLUESSEL
        for person in aussage["personen"]:
            assert set(person) == PERSON_SCHLUESSEL


# ── Filter ───────────────────────────────────────────────────────────────

def test_filtern_datum():
    andockung, chats = _beispielbestand()
    alle = bd.beziehungen_bauen(andockung, chats, {}, None, STAND)
    nur = bd.aussagen_filtern(alle, DATUM)
    assert nur and all(a["datum"] == DATUM for a in nur)


def test_filtern_unbekanntes_datum_leer():
    andockung, chats = _beispielbestand()
    alle = bd.beziehungen_bauen(andockung, chats, {}, None, STAND)
    assert bd.aussagen_filtern(alle, "1999-01-01") == []


def test_filtern_ungueltiges_datum_fehler():
    with pytest.raises(bd.PersonenFehler):
        bd.aussagen_filtern([], "30.03.2014")


def test_filtern_ohne_datum_aendert_nichts():
    andockung, chats = _beispielbestand()
    alle = bd.beziehungen_bauen(andockung, chats, {}, None, STAND)
    assert len(bd.aussagen_filtern(alle)) == len(alle)


def test_filtern_nur_bestaetigt_ohne_bestaetigung_leer():
    andockung, chats = _beispielbestand()
    alle = bd.beziehungen_bauen(andockung, chats, {}, None, STAND)
    assert bd.aussagen_filtern(alle, None, True) == []


def test_filtern_nur_bestaetigt_behaelt_fotos():
    andockung, chats = _beispielbestand()
    alle = bd.beziehungen_bauen(andockung, chats, {}, {P1: BESTAETIGTER_NAME},
                                STAND)
    nur = bd.aussagen_filtern(alle, None, True)
    assert nur
    assert {a["unterart"] for a in nur} <= {"fotos", "fotos_und_chat"}


def test_filtern_nur_bestaetigt_entfernt_ohne_treffer():
    andockung = [_andockung_knoten(personen=[_person(P1), _person(P2)])]
    alle = bd.beziehungen_bauen(andockung, [], {}, {P3: BESTAETIGTER_NAME},
                                STAND)
    assert bd.aussagen_filtern(alle, None, True) == []


def test_filtern_nur_bestaetigt_laesst_gemeinsam_weg():
    andockung = [_andockung_knoten(personen=[_person(P1)])]
    chats = [_chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A),
                                          _beteiligter(KONTAKT_B)]))]
    chats[0]["anlass_id"] = ANLASS
    alle = bd.beziehungen_bauen(andockung, chats, {}, {P1: BESTAETIGTER_NAME},
                                STAND)
    nur = bd.aussagen_filtern(alle, None, True)
    assert all(a["unterart"] != "gemeinsam_im_chat" for a in nur)


def test_filtern_ignoriert_fremde_elemente():
    assert bd.aussagen_filtern(["kein dict", 7, None], None) == []


# ── Uebersicht ───────────────────────────────────────────────────────────

def _beispielaussagen():
    andockung, chats = _beispielbestand()
    return bd.beziehungen_bauen(andockung, chats, {}, None, STAND)


def test_uebersicht_schluessel():
    doc = bd.uebersicht_bauen(_beispielaussagen(), {}, STAND)
    assert set(doc) == {"art", "stand", "anzahl", "anzahl_personen_kennungen",
                        "anzahl_namen_bestaetigt", "anzahl_kontakte",
                        "datum_von", "datum_bis", "quellen", "hinweis"}


def test_uebersicht_art_und_stand():
    doc = bd.uebersicht_bauen(_beispielaussagen(), {}, STAND)
    assert doc["art"] == "beziehungen"
    assert doc["stand"] == STAND


def test_uebersicht_anzahl_je_unterart():
    doc = bd.uebersicht_bauen(_beispielaussagen(), {}, STAND)
    assert doc["anzahl"] == {"fotos": 1, "gemeinsam_im_chat": 1,
                             "fotos_und_chat": 4}


def test_uebersicht_personen_kennungen():
    doc = bd.uebersicht_bauen(_beispielaussagen(), {}, STAND)
    assert doc["anzahl_personen_kennungen"] == 2


def test_uebersicht_kontakte():
    doc = bd.uebersicht_bauen(_beispielaussagen(), {}, STAND)
    assert doc["anzahl_kontakte"] == 2


def test_uebersicht_namen_bestaetigt_null():
    doc = bd.uebersicht_bauen(_beispielaussagen(), {}, STAND)
    assert doc["anzahl_namen_bestaetigt"] == 0


def test_uebersicht_namen_bestaetigt_zaehlt():
    andockung = [_andockung_knoten(personen=[_person(P1), _person(P2)])]
    aussagen = bd.beziehungen_bauen(andockung, [], {}, {P1: BESTAETIGTER_NAME},
                                    STAND)
    doc = bd.uebersicht_bauen(aussagen, {}, STAND)
    assert doc["anzahl_namen_bestaetigt"] == 1


def test_uebersicht_namen_bestaetigt_nicht_doppelt():
    andockung = [_andockung_knoten(personen=[_person(P1), _person(P2), _person(P3)])]
    aussagen = bd.beziehungen_bauen(andockung, [], {}, {P1: BESTAETIGTER_NAME},
                                    STAND)
    doc = bd.uebersicht_bauen(aussagen, {}, STAND)
    assert doc["anzahl_namen_bestaetigt"] == 1


def test_uebersicht_datum_spanne():
    doc = bd.uebersicht_bauen(_beispielaussagen(), {}, STAND)
    assert doc["datum_von"] == DATUM
    assert doc["datum_bis"] == DATUM


def test_uebersicht_datum_spanne_leer():
    doc = bd.uebersicht_bauen([], {}, STAND)
    assert doc["datum_von"] is None
    assert doc["datum_bis"] is None


def test_uebersicht_leer_zaehlt_null():
    doc = bd.uebersicht_bauen([], {}, STAND)
    assert doc["anzahl"] == {"fotos": 0, "gemeinsam_im_chat": 0,
                             "fotos_und_chat": 0}
    assert doc["anzahl_personen_kennungen"] == 0
    assert doc["anzahl_kontakte"] == 0


def test_uebersicht_hinweis_deutsch():
    doc = bd.uebersicht_bauen(_beispielaussagen(), {}, STAND)
    assert "keine Namen" in doc["hinweis"]
    assert "keine Anwesenheit" in doc["hinweis"]


def test_uebersicht_quellen_durchgereicht():
    doc = bd.uebersicht_bauen([], {"andockung": "personen_andockung.jsonl"},
                              STAND)
    assert doc["quellen"] == {"andockung": "personen_andockung.jsonl"}


def test_uebersicht_quellen_ohne_angabe():
    assert bd.uebersicht_bauen([], None, STAND)["quellen"] == {}


# ── Bericht ──────────────────────────────────────────────────────────────

def test_bericht_nennt_gesamt():
    text = bd.bericht_bauen({"stand": STAND,
                            "anzahl": {"fotos": 23, "gemeinsam_im_chat": 14902,
                                       "fotos_und_chat": 126},
                            "personen_kennungen": 12,
                            "namen_bestaetigt": 0, "kontakte": 253,
                            "datum_von": DATUM, "datum_bis": DATUM})
    assert "Aussagen gesamt: 15.051" in text


def test_bericht_einzelzeilen():
    text = bd.bericht_bauen({"stand": STAND,
                             "anzahl": {"fotos": 23, "gemeinsam_im_chat": 14902,
                                        "fotos_und_chat": 126}})
    assert "Aussagen fotos: 23" in text
    assert "gemeinsam_im_chat: 14.902" in text
    assert "fotos_und_chat: 126" in text


def test_bericht_ohne_daten_kein_absturz():
    text = bd.bericht_bauen({})
    assert "Aussagen gesamt: 0" in text
    assert "Datum von: -" in text
    assert "Stand unbekannt" in text


def test_bericht_ohne_klarnamen():
    text = bd.bericht_bauen({"stand": STAND,
                             "anzahl": {"fotos": 1},
                             "personen_kennungen": 1, "namen_bestaetigt": 0,
                             "kontakte": 1})
    assert BESTAETIGTER_NAME not in text
    assert P1 not in text
    assert KONTAKT_A not in text


# ── Schreiben und Repo-Schutz ────────────────────────────────────────────

def test_pruefe_ausserhalb_repo_ok(tmp_path):
    weg = str(tmp_path / "a.jsonl")
    assert bd.pruefe_ausserhalb_repo(weg) == weg


def test_pruefe_ausserhalb_repo_leer():
    with pytest.raises(bd.PersonenFehler):
        bd.pruefe_ausserhalb_repo("")


def test_pruefe_ausserhalb_repo_im_repo():
    with pytest.raises(bd.PersonenFehler):
        bd.pruefe_ausserhalb_repo(str(REPO / "beziehungen.jsonl"))


def test_schreiben_jsonl(tmp_path):
    ziel = str(tmp_path / "b.jsonl")
    weg = bd.schreiben(ziel, [{"b": 1, "a": 2}, {"a": 3}])
    assert weg == ziel
    zeilen = Path(ziel).read_text(encoding="utf-8").splitlines()
    assert zeilen == ['{"a": 2, "b": 1}', '{"a": 3}']


def test_schreiben_json(tmp_path):
    ziel = str(tmp_path / "b.json")
    bd.schreiben(ziel, {"art": "beziehungen", "stand": STAND})
    daten = json.loads(Path(ziel).read_text(encoding="utf-8"))
    assert daten["art"] == "beziehungen"


def test_schreiben_keine_tmp_reste(tmp_path):
    ziel = tmp_path / "c.jsonl"
    bd.schreiben(str(ziel), [{"a": 1}])
    assert not (tmp_path / "c.jsonl.tmp").exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["c.jsonl"]


def test_schreiben_im_repo_verweigert():
    with pytest.raises(bd.PersonenFehler):
        bd.schreiben(str(REPO / "verboten.jsonl"), [{"a": 1}])
    assert not (REPO / "verboten.jsonl").exists()


def test_schreiben_falscher_typ(tmp_path):
    with pytest.raises(bd.PersonenFehler):
        bd.schreiben(str(tmp_path / "x.jsonl"), "nur text")


def test_schreiben_ersetzt_vorhandene_datei(tmp_path):
    ziel = tmp_path / "d.jsonl"
    ziel.write_text("alt\n", encoding="utf-8")
    bd.schreiben(str(ziel), [{"neu": 1}])
    assert json.loads(ziel.read_text(encoding="utf-8")) == {"neu": 1}


# ── Kommandozeile ────────────────────────────────────────────────────────

def test_main_trocken_exit0(tmp_path):
    wege = _eingaben(tmp_path)
    assert bd.main(_argv(wege, "--trocken")) == 0


def test_main_trocken_keine_datei(tmp_path):
    wege = _eingaben(tmp_path)
    bd.main(_argv(wege, "--trocken"))
    assert not Path(wege["ausgabe"]).exists()
    assert not Path(wege["uebersicht"]).exists()


def test_main_standard_ist_trocken(tmp_path):
    wege = _eingaben(tmp_path)
    assert bd.main(_argv(wege)) == 0
    assert not Path(wege["ausgabe"]).exists()


def test_main_trocken_hat_vorrang(tmp_path):
    wege = _eingaben(tmp_path)
    assert bd.main(_argv(wege, "--schreiben", "--trocken")) == 0
    assert not Path(wege["ausgabe"]).exists()


def test_main_schreiben_beide_dateien(tmp_path):
    wege = _eingaben(tmp_path, andockung=[
        _andockung_knoten(personen=[_person(P1), _person(P2)])],
        ereignisse=[_ereignis()])
    assert bd.main(_argv(wege, "--schreiben", "--stand", STAND)) == 0
    assert Path(wege["ausgabe"]).is_file()
    assert Path(wege["uebersicht"]).is_file()


def test_main_schreiben_jsonl_inhalt(tmp_path):
    wege = _eingaben(tmp_path, andockung=[
        _andockung_knoten(personen=[_person(P1), _person(P2)])])
    bd.main(_argv(wege, "--schreiben", "--stand", STAND))
    zeilen = [json.loads(z) for z in
              Path(wege["ausgabe"]).read_text(encoding="utf-8").splitlines()]
    assert len(zeilen) == 1
    assert zeilen[0]["unterart"] == "fotos"
    assert set(zeilen[0]) == SCHEMA_SCHLUESSEL


def test_main_schreiben_uebersicht_inhalt(tmp_path):
    wege = _eingaben(tmp_path, andockung=[
        _andockung_knoten(personen=[_person(P1), _person(P2)])])
    bd.main(_argv(wege, "--schreiben", "--stand", STAND))
    doc = json.loads(Path(wege["uebersicht"]).read_text(encoding="utf-8"))
    assert doc["art"] == "beziehungen"
    assert doc["anzahl"]["fotos"] == 1
    assert doc["anzahl_namen_bestaetigt"] == 0


def test_main_schreiben_zeilenzahl(tmp_path):
    andockung = [_andockung_knoten(personen=[_person(P1), _person(P2),
                                             _person(P3)])]
    wege = _eingaben(tmp_path, andockung=andockung)
    bd.main(_argv(wege, "--schreiben", "--stand", STAND))
    zeilen = Path(wege["ausgabe"]).read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 3


def test_main_repo_ziel_exit2(tmp_path, capsys):
    wege = _eingaben(tmp_path)
    wege["ausgabe"] = str(REPO / "beziehungen.jsonl")
    assert bd.main(_argv(wege)) == 2
    assert "Fehler" in capsys.readouterr().err


def test_main_repo_ziel_uebersicht_exit2(tmp_path, capsys):
    wege = _eingaben(tmp_path)
    wege["uebersicht"] = str(REPO / "beziehungen.json")
    assert bd.main(_argv(wege)) == 2
    assert "IM Repo" in capsys.readouterr().err


def test_main_repo_ziel_schreibt_keine_datei(tmp_path):
    wege = _eingaben(tmp_path)
    wege["ausgabe"] = str(REPO / "beziehungen.jsonl")
    bd.main(_argv(wege, "--schreiben"))
    assert not (REPO / "beziehungen.jsonl").exists()


def test_main_repo_ziel_auch_im_trockenlauf_exit2(tmp_path):
    wege = _eingaben(tmp_path)
    wege["ausgabe"] = str(REPO / "beziehungen.jsonl")
    assert bd.main(_argv(wege, "--trocken")) == 2


def test_main_fehlende_eingabe_exit2(tmp_path, capsys):
    wege = _eingaben(tmp_path)
    wege["andockung"] = str(tmp_path / "fehlt.jsonl")
    assert bd.main(_argv(wege)) == 2
    assert "Fehler" in capsys.readouterr().err


def test_main_fehlende_chat_eingabe_exit2(tmp_path):
    wege = _eingaben(tmp_path)
    wege["chats"] = str(tmp_path / "fehlt.jsonl")
    assert bd.main(_argv(wege)) == 2


def test_main_fehlende_ereignisse_exit2(tmp_path):
    wege = _eingaben(tmp_path)
    wege["ereignisse"] = str(tmp_path / "fehlt.jsonl")
    assert bd.main(_argv(wege)) == 2


def test_main_ungueltiges_datum_exit2(tmp_path, capsys):
    wege = _eingaben(tmp_path)
    assert bd.main(_argv(wege, "--datum", "30.03.2014")) == 2
    assert "gueltiges Datum" in capsys.readouterr().err


def test_main_datum_filter(tmp_path):
    andockung = [_andockung_knoten(personen=[_person(P1), _person(P2)]),
                 _andockung_knoten(anlass_id=ANLASS_ZWEI, datum=DATUM_ZWEI,
                                   personen=[_person(P3), _person(P4)])]
    wege = _eingaben(tmp_path, andockung=andockung)
    bd.main(_argv(wege, "--schreiben", "--stand", STAND, "--datum", DATUM))
    zeilen = [json.loads(z) for z in
              Path(wege["ausgabe"]).read_text(encoding="utf-8").splitlines()]
    assert len(zeilen) == 1
    assert zeilen[0]["datum"] == DATUM


def test_main_datum_ohne_treffer_schreibt_leere_datei(tmp_path):
    wege = _eingaben(tmp_path, andockung=[
        _andockung_knoten(personen=[_person(P1), _person(P2)])])
    bd.main(_argv(wege, "--schreiben", "--stand", STAND, "--datum", "1999-01-01"))
    assert Path(wege["ausgabe"]).read_text(encoding="utf-8") == ""


def test_main_nur_bestaetigt_leer_ohne_bestaetigung(tmp_path):
    wege = _eingaben(tmp_path, andockung=[
        _andockung_knoten(personen=[_person(P1), _person(P2)])])
    bd.main(_argv(wege, "--schreiben", "--stand", STAND, "--nur-bestaetigt"))
    assert Path(wege["ausgabe"]).read_text(encoding="utf-8") == ""


def test_main_nur_bestaetigt_behaelt_treffer(tmp_path):
    wege = _eingaben(
        tmp_path,
        andockung=[_andockung_knoten(personen=[_person(P1), _person(P2)])],
        bestaetigung={"bestaetigt": {P1: BESTAETIGTER_NAME}})
    bd.main(_argv(wege, "--schreiben", "--stand", STAND, "--nur-bestaetigt"))
    zeilen = [json.loads(z) for z in
              Path(wege["ausgabe"]).read_text(encoding="utf-8").splitlines()]
    assert len(zeilen) == 1
    namen = {p["kennung"]: p["name"] for p in zeilen[0]["personen"]}
    assert namen[P1] == BESTAETIGTER_NAME


def test_main_bestaetigung_erscheint_genau_richtig(tmp_path):
    andockung = [_andockung_knoten(personen=[_person(P1), _person(P2)]),
                 _andockung_knoten(anlass_id=ANLASS_ZWEI, datum=DATUM_ZWEI,
                                   personen=[_person(P3), _person(P4)])]
    wege = _eingaben(tmp_path, andockung=andockung,
                     bestaetigung={"bestaetigt": {P1: BESTAETIGTER_NAME}})
    bd.main(_argv(wege, "--schreiben", "--stand", STAND))
    zeilen = [json.loads(z) for z in
              Path(wege["ausgabe"]).read_text(encoding="utf-8").splitlines()]
    mit_name = [z for z in zeilen
                if any(p["name"] == BESTAETIGTER_NAME for p in z["personen"])]
    assert mit_name
    for zeile in mit_name:
        assert any(p["kennung"] == P1 for p in zeile["personen"])
    for zeile in zeilen:
        if not any(p["kennung"] == P1 for p in zeile["personen"]):
            assert not any(p["name"] == BESTAETIGTER_NAME
                           for p in zeile["personen"])


def test_main_bestaetigung_zaehlt_in_uebersicht(tmp_path):
    wege = _eingaben(
        tmp_path,
        andockung=[_andockung_knoten(personen=[_person(P1), _person(P2)])],
        bestaetigung={"bestaetigt": {P1: BESTAETIGTER_NAME}})
    bd.main(_argv(wege, "--schreiben", "--stand", STAND))
    doc = json.loads(Path(wege["uebersicht"]).read_text(encoding="utf-8"))
    assert doc["anzahl_namen_bestaetigt"] == 1


def test_main_zwei_schreiblaeufe_byte_gleich(tmp_path):
    andockung = [_andockung_knoten(personen=[_person(P1), _person(P2)]),
                 _andockung_knoten(anlass_id=ANLASS_ZWEI, datum=DATUM_ZWEI,
                                   personen=[_person(P3), _person(P4)])]
    chats = [_chats_mit(_chat(beteiligte=[_beteiligter(KONTAKT_A),
                                          _beteiligter(KONTAKT_B)]))]
    chats[0]["anlass_id"] = ANLASS
    chats[0]["datum"] = DATUM
    wege = _eingaben(tmp_path, andockung=andockung, chats=chats,
                     ereignisse=[_ereignis()])
    ordner_a = tmp_path / "a"
    ordner_b = tmp_path / "b"
    wege_a = dict(wege, ausgabe=str(ordner_a / "beziehungen.jsonl"),
                  uebersicht=str(ordner_a / "beziehungen.json"))
    wege_b = dict(wege, ausgabe=str(ordner_b / "beziehungen.jsonl"),
                  uebersicht=str(ordner_b / "beziehungen.json"))
    bd.main(_argv(wege_a, "--schreiben", "--stand", STAND))
    bd.main(_argv(wege_b, "--schreiben", "--stand", STAND))
    for name in ("beziehungen.jsonl", "beziehungen.json"):
        assert (ordner_a / name).read_bytes() == (ordner_b / name).read_bytes()


def test_main_stand_in_jeder_zeile(tmp_path):
    wege = _eingaben(tmp_path, andockung=[
        _andockung_knoten(personen=[_person(P1), _person(P2)])])
    bd.main(_argv(wege, "--schreiben", "--stand", STAND))
    zeilen = [json.loads(z) for z in
              Path(wege["ausgabe"]).read_text(encoding="utf-8").splitlines()]
    assert all(z["stand"] == STAND for z in zeilen)


def test_main_zeilen_sortiert_geschrieben(tmp_path):
    wege = _eingaben(tmp_path, andockung=[
        _andockung_knoten(personen=[_person(P1), _person(P2)])])
    bd.main(_argv(wege, "--schreiben", "--stand", STAND))
    rohtext = Path(wege["ausgabe"]).read_text(encoding="utf-8")
    zeilen = [json.loads(z) for z in rohtext.splitlines()]
    assert rohtext == "".join(json.dumps(z, ensure_ascii=True, sort_keys=True) +
                              "\n" for z in zeilen)


def test_main_bericht_auf_der_konsole(tmp_path, capsys):
    wege = _eingaben(tmp_path, andockung=[
        _andockung_knoten(personen=[_person(P1), _person(P2)])])
    bd.main(_argv(wege, "--trocken", "--stand", STAND))
    aus = capsys.readouterr().out
    assert "TROCKENLAUF" in aus
    assert "Aussagen gesamt: 1" in aus


def test_main_keine_datei_im_repo_angelegt(tmp_path):
    wege = _eingaben(tmp_path, andockung=[
        _andockung_knoten(personen=[_person(P1), _person(P2)])])
    bd.main(_argv(wege, "--schreiben", "--stand", STAND))
    assert not (REPO / "tools" / "foto_sortierung" / "beziehungen.jsonl").exists()


def test_main_leere_eingaben_exit0(tmp_path):
    wege = _eingaben(tmp_path)
    assert bd.main(_argv(wege, "--trocken", "--stand", STAND)) == 0


def test_main_defekte_zeilen_zaehlt_aber_kein_abbruch(tmp_path, capsys):
    wege = _eingaben(tmp_path)
    Path(wege["andockung"]).write_text("kein json\n", encoding="utf-8")
    assert bd.main(_argv(wege, "--trocken", "--stand", STAND)) == 0
    assert "defekte Zeilen: 1" in capsys.readouterr().out
