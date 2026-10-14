"""
T0 — der datensparsame Quellenstatus (``app.services.import_status``).

Auftrag: ``.hermes/plans/gesamtplan-foto-erinnerungen-2026-10-11.md``, Abschnitt
T0 („Fotoquellen wirklich bis zum Handy nachweisen"). Diese Tests halten die zwei
harten Regeln des Auftrags fest, die man leicht verliert:

1. **Nur Summen.** Der Bericht darf keinen Pfad, keinen Namen, keinen Ortswert,
   keine Bild-ID und keinen Vektor tragen — nachgeprüft am fertigen Bericht.
2. **Fehlender Messwert ist ``None``, nicht ``0``.** Fehlende, kaputte und
   gültige Dateien müssen unterscheidbar bleiben.

Alle Vorrichtungen hier sind synthetisch (erfundene Kennungen, erfundene Namen),
kein echter Bestand, kein Netz, kein Gerät.
"""

from __future__ import annotations

import datetime as _zeit
import json
import os
import sqlite3
from pathlib import Path

import pytest

from app.services import gruppen_quiz, import_status
from app.services.import_status import VERTRAGSFELDER

ZEIT = _zeit.datetime(2026, 10, 14, 12, 0, 0, tzinfo=_zeit.timezone.utc)

NAME = "Ida Testmann"          # erfundener Name: darf im Bericht NICHT auftauchen


# ── Vorrichtungen ────────────────────────────────────────────────────────────

def _plan(basis: Path, name: str, kennungen, feld: str = "fileid") -> Path:
    pfad = basis / name
    pfad.write_text(json.dumps({"zuege": [{feld: k} for k in kennungen]}), encoding="utf-8")
    return pfad


def _vektoren(basis: Path, name: str, bilder) -> Path:
    """``bilder`` = {kennung: Zahl der Gesichter}; ``#t=``-Zeilen sind Videos."""
    pfad = basis / name
    with open(pfad, "w", encoding="utf-8") as datei:
        for kennung, zahl in bilder:
            datei.write(json.dumps({"bild_id": kennung, "breite": 100, "hoehe": 200,
                                    "gesichter": [{"score": 0.9}] * zahl}) + "\n")
    return pfad


def _index(basis: Path, name: str, kennungen) -> Path:
    pfad = basis / name
    verbindung = sqlite3.connect(pfad)
    verbindung.execute("CREATE TABLE bilder (fileid INTEGER PRIMARY KEY, vektor BLOB)")
    verbindung.executemany("INSERT INTO bilder (fileid, vektor) VALUES (?, ?)",
                           [(int(k), b"x") for k in kennungen])
    verbindung.commit()
    verbindung.close()
    return pfad


def _zuordnung(basis: Path, zeilen) -> Path:
    """``zeilen`` = [(bild_id, kennung|None)]."""
    ordner = basis / import_status.UNTERORDNER
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / import_status.ZUORDNUNG_DATEINAME
    with open(pfad, "w", encoding="utf-8") as datei:
        for kennung, gruppe in zeilen:
            datei.write(json.dumps({"bild_id": kennung, "index": 0, "kennung": gruppe,
                                    "score": 0.9}) + "\n")
    return pfad


def _gruppen_quiz_basis(basis: Path, gruppen, bestaetigt, spaeter=(), unbekannt=()) -> None:
    """Synthetischer Gruppenbestand für den Quizdienst (nur Zahlen erwartet)."""
    ordner = basis / import_status.UNTERORDNER
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / gruppen_quiz.BEISPIELE_DATEINAME).write_text(
        json.dumps({"gruppen": [{"kennung": k, "groesse": g} for k, g in gruppen],
                    "stand": "2026-10-14"}), encoding="utf-8")
    (basis / gruppen_quiz.BESTAETIGT_DATEINAME).write_text(
        json.dumps({"bestaetigt": bestaetigt}), encoding="utf-8")
    (basis / gruppen_quiz.STAND_DATEINAME).write_text(
        json.dumps({"spaeter": list(spaeter), "unbekannt": list(unbekannt)}), encoding="utf-8")


def _quiz_basis_umlenken(monkeypatch, basis: Path) -> None:
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(basis))


# ── Die zwei Regeln ──────────────────────────────────────────────────────────

def test_bericht_traegt_genau_die_felder_des_vertrags(tmp_path, monkeypatch):
    _plan(tmp_path, "sortierplan_papa.json", ["1", "2"])
    _vektoren(tmp_path, "personen_vektoren_papa.jsonl", [("1", 2)])
    _index(tmp_path, import_status.INDEX_DATEINAME, ["1"])
    _zuordnung(tmp_path, [("1", "Person_001")])
    _quiz_basis_umlenken(monkeypatch, tmp_path)

    bericht = import_status.status(basis=str(tmp_path), zeitpunkt=ZEIT)

    assert set(bericht["quellen"][0]) == set(VERTRAGSFELDER)
    assert bericht["gelesen_am"] == ZEIT.astimezone().isoformat(timespec="seconds")


def test_zaehlt_die_vier_stationen_getrennt(tmp_path, monkeypatch):
    """Plan, Index, Gesichtslauf und Gruppenbestand werden über dieselbe Kennung verglichen."""
    _plan(tmp_path, "sortierplan_papa.json", ["1", "2", "3"])
    _vektoren(tmp_path, "personen_vektoren_papa.jsonl", [("1", 2), ("2", 1)])
    _index(tmp_path, import_status.INDEX_DATEINAME, ["1", "2", "99"])
    _zuordnung(tmp_path, [("1", "Person_001"), ("2", None), ("77", "Person_002")])
    _quiz_basis_umlenken(monkeypatch, tmp_path)

    bericht = import_status.status(basis=str(tmp_path), zeitpunkt=ZEIT)
    zeile = next(z for z in bericht["quellen"] if z["quelle_typ"] == "papas_album")

    assert zeile["bilder_im_plan"] == 3
    assert zeile["bilder_im_index"] == 2          # "3" fehlt im Index, "99" ist fremd
    assert zeile["bilder_mit_gesichtslauf"] == 2
    assert zeile["erkannte_gesichter"] == 3
    assert zeile["gesichter_im_gruppenbestand"] == 1   # nur die Zeile MIT Gruppe dieser Quelle


def test_fehlende_datei_ist_null_und_wird_genannt(tmp_path, monkeypatch):
    """Regel 2: fehlt die Datei, steht dort null — nicht 0 („nichts gefunden")."""
    _quiz_basis_umlenken(monkeypatch, tmp_path)

    bericht = import_status.status(basis=str(tmp_path), zeitpunkt=ZEIT)
    zeile = bericht["quellen"][0]

    assert zeile["bilder_im_plan"] is None
    assert zeile["bilder_im_index"] is None
    assert zeile["bilder_mit_gesichtslauf"] is None
    assert zeile["erkannte_gesichter"] is None
    assert "papas_album.bilder_im_plan" in bericht["fehlende_werte"]


def test_leerer_plan_ist_null_und_nicht_null_zeilen(tmp_path, monkeypatch):
    """Ein Plan ohne Züge ist gemessen: 0 Bilder — und das ist etwas anderes als „fehlt"."""
    _plan(tmp_path, "sortierplan_papa.json", [])
    _quiz_basis_umlenken(monkeypatch, tmp_path)

    zeile = import_status.quelle_status(
        "papas_album", ("sortierplan_papa.json",), (),
        basis=str(tmp_path), index_datei=None, zuordnung_datei=None)

    assert zeile["bilder_im_plan"] == 0
    assert zeile["bilder_im_index"] is None       # ohne Index nicht messbar, nicht 0


def test_kaputte_dateien_werfen_nicht_und_bleiben_null(tmp_path, monkeypatch):
    (tmp_path / "sortierplan_papa.json").write_text("{kaputt", encoding="utf-8")
    (tmp_path / import_status.INDEX_DATEINAME).write_text("kein sqlite", encoding="utf-8")
    _vektoren(tmp_path, "personen_vektoren_papa.jsonl", [("1", 1)])
    with open(tmp_path / "personen_vektoren_papa.jsonl", "a", encoding="utf-8") as datei:
        datei.write("{kaputt\n[]\n{}\n")
    _zuordnung(tmp_path, [("1", "Person_001")])
    _quiz_basis_umlenken(monkeypatch, tmp_path)

    bericht = import_status.status(basis=str(tmp_path), zeitpunkt=ZEIT)
    zeile = next(z for z in bericht["quellen"] if z["quelle_typ"] == "papas_album")

    assert zeile["bilder_im_plan"] is None        # kaputter Plan = nicht gemessen
    assert zeile["bilder_im_index"] is None       # kaputte Datenbank = nicht gemessen
    assert zeile["bilder_mit_gesichtslauf"] == 1  # die gültige Zeile zählt trotzdem
    assert zeile["erkannte_gesichter"] == 1
    assert zeile["gesichter_im_gruppenbestand"] is None   # ohne Plan keine Zuordnung möglich


def test_video_standbilder_zaehlen_nicht_als_bild(tmp_path):
    _vektoren(tmp_path, "personen_vektoren_papa.jsonl",
              [("1", 2), ("1#t=4.0", 1), ("2", 0)])
    zahlen = import_status.vektoren_zaehlen(str(tmp_path / "personen_vektoren_papa.jsonl"))

    assert zahlen["bilder"] == 2                 # das Video-Standbild ist kein Bild
    assert zahlen["gesichter"] == 2
    assert zahlen["video_zeilen"] == 1


def test_doppelte_kennung_zaehlt_einmal(tmp_path):
    _plan(tmp_path, "sortierplan_papa.json", ["1", "1", 1.0, "2"])
    _vektoren(tmp_path, "personen_vektoren_papa.jsonl", [("1", 1), ("1", 3)])

    assert import_status.plan_kennungen(str(tmp_path / "sortierplan_papa.json")) == {"1", "2"}
    assert import_status.vektoren_zaehlen(
        str(tmp_path / "personen_vektoren_papa.jsonl"))["gesichter"] == 4


def test_plan_als_liste_und_mit_bild_id(tmp_path):
    (tmp_path / "gedreht_plan.json").write_text(
        json.dumps([{"fileid": "5"}, {"bild_id": "6"}, "7", {}, None]), encoding="utf-8")

    assert import_status.plan_kennungen(str(tmp_path / "gedreht_plan.json")) == {"5", "6", "7"}


def test_station_ohne_index_ist_null(tmp_path):
    """Ohne ``index_datei`` ist die Index-Station NICHT gemessen — nicht 0."""
    _plan(tmp_path, "sortierplan_papa.json", ["1"])
    zeile = import_status.quelle_status("papas_album", ("sortierplan_papa.json",), (),
                                        basis=str(tmp_path))

    assert zeile["bilder_im_index"] is None
    assert zeile["bilder_im_plan"] == 1


# ── Gruppenbestand: Bestand, kein Zuwachs ────────────────────────────────────

def test_gruppen_je_quelle_getrennt_und_ohne_namen(tmp_path, monkeypatch):
    _plan(tmp_path, "sortierplan_papa.json", ["1", "2"])
    _plan(tmp_path, "sortierplan.json", ["8", "9"])
    _vektoren(tmp_path, "personen_vektoren_papa.jsonl", [("1", 1)])
    _vektoren(tmp_path, "personen_vektoren_n0929_voll.jsonl", [("8", 1)])
    _index(tmp_path, import_status.INDEX_DATEINAME, ["1", "8"])
    _zuordnung(tmp_path, [("1", "Person_001"), ("8", "Person_001"), ("9", None)])
    _gruppen_quiz_basis(tmp_path,
                        gruppen=[("Person_001", 2), ("Person_002", 5), ("Person_003", 1)],
                        bestaetigt={"Person_001": NAME},
                        spaeter=["Person_002"], unbekannt=["Person_003"])
    _quiz_basis_umlenken(monkeypatch, tmp_path)

    bericht = import_status.status(basis=str(tmp_path), zeitpunkt=ZEIT)
    nach_typ = {z["quelle_typ"]: z for z in bericht["quellen"]}

    assert nach_typ["papas_album"]["gesichter_im_gruppenbestand"] == 1
    assert nach_typ["fotos"]["gesichter_im_gruppenbestand"] == 1
    assert bericht["gruppenbestand"] == {"gruppen": 3, "benannt": 1, "offen": 1,
                                         "spaeter": 1, "gesichter": 8}
    # Der Stand gilt für den GANZEN Bestand und steht deshalb in jeder Zeile gleich.
    assert nach_typ["fotos"]["offene_gruppen"] == nach_typ["papas_album"]["offene_gruppen"] == 1
    assert nach_typ["fotos"]["spaeter_gruppen"] == 1
    assert NAME not in json.dumps(bericht, ensure_ascii=False)


def test_gruppenstand_ohne_dateien_ist_null(tmp_path, monkeypatch):
    _quiz_basis_umlenken(monkeypatch, tmp_path)

    stand = import_status.gruppen_stand_lesen()
    bericht = import_status.status(basis=str(tmp_path), zeitpunkt=ZEIT)

    assert stand == {"gruppen": None, "benannt": None, "offen": None,
                     "spaeter": None, "gesichter": None}
    assert "gruppenbestand.offen" in bericht["fehlende_werte"]


# ── Datensparsamkeit, Gerätestation, Wiederholbarkeit ────────────────────────

def test_bericht_traegt_keinen_pfad_und_keine_kennung(tmp_path, monkeypatch):
    _plan(tmp_path, "sortierplan_papa.json", ["108863662523"])
    _vektoren(tmp_path, "personen_vektoren_papa.jsonl", [("108863662523", 7)])
    _index(tmp_path, import_status.INDEX_DATEINAME, ["108863662523"])
    _zuordnung(tmp_path, [("108863662523", "Person_001")])
    _quiz_basis_umlenken(monkeypatch, tmp_path)

    bericht = import_status.status(basis=str(tmp_path), zeitpunkt=ZEIT)
    roh = json.dumps(bericht, ensure_ascii=False)

    for verboten in ("108863662523", str(tmp_path), "/", "\\", ".json", ".jsonl", ".db"):
        assert verboten not in roh, f"{verboten!r} darf nicht im Bericht stehen"


def test_geraetestation_ist_null_ohne_messung(tmp_path, monkeypatch):
    """Die fünfte Station ist am PC nicht messbar — ohne Messung null, nicht False."""
    _plan(tmp_path, "sortierplan_papa.json", ["1"])
    _quiz_basis_umlenken(monkeypatch, tmp_path)

    ohne = import_status.status(basis=str(tmp_path), zeitpunkt=ZEIT)
    mit = import_status.status(basis=str(tmp_path), handy_geprueft=True, zeitpunkt=ZEIT)

    assert ohne["handy_stand_geprueft"] is None
    assert all(z["handy_stand_geprueft"] is None for z in ohne["quellen"])
    assert "papas_album.handy_stand_geprueft" in ohne["fehlende_werte"]
    assert all(z["handy_stand_geprueft"] is True for z in mit["quellen"])


def test_liest_nur_und_ist_wiederholbar(tmp_path, monkeypatch):
    _plan(tmp_path, "sortierplan_papa.json", ["1", "2"])
    _vektoren(tmp_path, "personen_vektoren_papa.jsonl", [("1", 2)])
    _index(tmp_path, import_status.INDEX_DATEINAME, ["1"])
    _zuordnung(tmp_path, [("1", "Person_001")])
    _gruppen_quiz_basis(tmp_path, gruppen=[("Person_001", 2)], bestaetigt={})
    _quiz_basis_umlenken(monkeypatch, tmp_path)

    vorher = {p.name: p.stat().st_mtime_ns for p in tmp_path.rglob("*") if p.is_file()}
    erster = import_status.status(basis=str(tmp_path), zeitpunkt=ZEIT)
    zweiter = import_status.status(basis=str(tmp_path), zeitpunkt=ZEIT)
    nachher = {p.name: p.stat().st_mtime_ns for p in tmp_path.rglob("*") if p.is_file()}

    assert erster == zweiter
    assert vorher == nachher
    assert sorted(nachher) == sorted(vorher)     # nichts angelegt


@pytest.mark.parametrize("leer", [None, {}, "text"])
def test_leere_oder_fremde_planform_ist_null(tmp_path, leer):
    (tmp_path / "sortierplan_papa.json").write_text(json.dumps(leer), encoding="utf-8")

    assert import_status.plan_kennungen(str(tmp_path / "sortierplan_papa.json")) is None


def test_plan_ohne_zuege_ist_gemessen_null(tmp_path):
    """Eine leere Zugliste ist gemessen (0 Bilder) — etwas anderes als eine fremde Form."""
    (tmp_path / "sortierplan_papa.json").write_text("[]", encoding="utf-8")

    assert import_status.plan_kennungen(str(tmp_path / "sortierplan_papa.json")) == set()


def test_basis_ist_uebersteuerbar_und_standard_bleibt_lesbar():
    assert os.path.basename(import_status.STANDARD_BASIS) == "foto_sortierung"
    assert import_status.QUELLEN and all(len(q) == 3 for q in import_status.QUELLEN)
