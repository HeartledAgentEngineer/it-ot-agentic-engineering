"""Tests: Was und wo je Bild im Erzählen (07.10.2026).

Erfundene Beschreibungen, Orte und Kennungen in ``tmp_path``. Geprüft: Dienst
``erzaehl_service.bilder_info`` (letzte Beschreibung gilt, keine Hausnummern,
häufigste Orte, fehlende Dateien), Zwischenspeicher, Route und der Sender mit
eigener Dateiliste.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
PROJEKT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.router import erzaehlen as erzaehlen_router  # noqa: E402
from app.services import erzaehl_service  # noqa: E402


def _jsonl(pfad: Path, zeilen):
    pfad.write_text("\n".join(z if isinstance(z, str) else json.dumps(z, ensure_ascii=False) for z in zeilen) + "\n",
                    encoding="utf-8")


def _orte(pfad: Path, zeilen):
    with open(pfad, "w", newline="", encoding="utf-8") as datei:
        schreiber = csv.writer(datei)
        schreiber.writerow(["fileid", "aufnahme", "adresse", "hausnummer", "ort_osm", "landmarke",
                            "landmarke_art", "hinweise", "abstand_m"])
        schreiber.writerows(zeilen)


def _umgebung(tmp_path, monkeypatch, mit_dateien=True):
    _jsonl(tmp_path / "ereignisse.jsonl", [
        {"kennung": "E-1", "event": "Testausflug", "datum": "2015-06-01", "datei_kennungen": [1, 2, 3, 4]},
    ])
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(tmp_path / "ereignisse.jsonl"))
    monkeypatch.setenv("ERZAEHL_GESCHICHTEN_PFAD", str(tmp_path / "geschichten.jsonl"))
    monkeypatch.delenv("ERZAEHL_FOTOBUCH_PFAD", raising=False)
    monkeypatch.delenv("ERZAEHL_ORDNER_EREIGNISSE_PFAD", raising=False)
    if mit_dateien:
        _jsonl(tmp_path / "bild_beschreibungen.jsonl", [
            {"fileid": 1, "beschreibung": "Alte Fassung"},
            {"fileid": 1, "beschreibung": "Zwei Personen   am\nSteg, Abendlicht"},   # letzte gilt, Leerraum geordnet
            {"fileid": 2, "beschreibung": ""},
            {"fileid": 9, "beschreibung": "fremdes Bild"},
            "kaputt",
        ])
        _orte(tmp_path / "bild_orte.csv", [
            [1, "", "Teststrasse", "41", "Testdorf", "Gasthaus am See", "restaurant", "", "40"],
            [2, "", "", "", "Testdorf", "Gasthaus am See", "restaurant", "", "55"],
            [3, "", "", "", "Testdorf", "", "", "", ""],
            [4, "", "", "", "", "", "", "ohne GPS", ""],
        ])


def test_bilder_info_beschreibung_ort_und_haeufigste_orte(tmp_path, monkeypatch):
    _umgebung(tmp_path, monkeypatch)
    info = erzaehl_service.bilder_info("E-1")
    assert set(info["bilder"]) == {"1", "2", "3"}                 # Bild 4: weder Ort noch Text
    assert info["bilder"]["1"]["beschreibung"] == "Zwei Personen am Steg, Abendlicht"
    assert info["bilder"]["1"]["ort"] == {"landmarke": "Gasthaus am See", "art": "restaurant", "ort": "Testdorf"}
    assert "Teststrasse" not in json.dumps(info) and "41" not in json.dumps(info["bilder"]["1"])  # keine Hausnummern
    assert info["bilder"]["2"]["beschreibung"] is None
    assert info["bilder"]["3"]["ort"] == {"landmarke": None, "art": None, "ort": "Testdorf"}
    assert info["orte"] == ["Gasthaus am See", "Testdorf"]
    assert (info["mit_beschreibung"], info["mit_ort"]) == (1, 3)
    assert info["beschreibungen_vorhanden"] and info["orte_vorhanden"]
    assert erzaehl_service.bilder_info("gibt-es-nicht") is None


def test_ohne_dateien_leer_statt_fehler(tmp_path, monkeypatch):
    _umgebung(tmp_path, monkeypatch, mit_dateien=False)
    info = erzaehl_service.bilder_info("E-1")
    assert info["bilder"] == {} and info["orte"] == []
    assert not info["beschreibungen_vorhanden"] and not info["orte_vorhanden"]


def test_zwischenspeicher_liest_geaenderte_datei_neu(tmp_path, monkeypatch):
    _umgebung(tmp_path, monkeypatch)
    assert erzaehl_service.bilder_info("E-1")["bilder"]["1"]["beschreibung"].startswith("Zwei")
    pfad = tmp_path / "bild_beschreibungen.jsonl"
    with open(pfad, "a", encoding="utf-8") as datei:
        datei.write(json.dumps({"fileid": 1, "beschreibung": "Neue Fassung"}) + "\n")
    stand = os.stat(pfad)
    os.utime(pfad, (stand.st_atime, stand.st_mtime + 5))       # sicher neue Zeit, auch bei grober Uhr
    assert erzaehl_service.bilder_info("E-1")["bilder"]["1"]["beschreibung"] == "Neue Fassung"


def test_route_bilder_info(tmp_path, monkeypatch):
    _umgebung(tmp_path, monkeypatch)
    app = FastAPI()
    app.include_router(erzaehlen_router.router)
    client = TestClient(app)
    antwort = client.get("/api/erzaehlen/ereignisse/E-1/bilder-info").json()
    assert antwort["ok"] is True and antwort["info"]["orte"][0] == "Gasthaus am See"
    fehlt = client.get("/api/erzaehlen/ereignisse/X-9/bilder-info").json()
    assert fehlt["ok"] is False and "nicht gefunden" in fehlt["error"]


# ── Sender mit eigener Dateiliste ────────────────────────────────────────────

def _sender():
    spez = importlib.util.spec_from_file_location(
        "gruppen_aufs_handy", PROJEKT / "tools" / "handy" / "gruppen_aufs_handy.py")
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


class _Adb:
    def __init__(self, basis):
        self.basis, self.befehle = basis, []

    def __call__(self, befehl):
        self.befehle.append(befehl)
        if befehl[1] == "devices":
            return 0, "List of devices attached\nX\tdevice\n"
        if befehl[1] == "shell":
            name = befehl[-1].rsplit("/", 1)[-1]
            return 0, str(os.path.getsize(os.path.join(self.basis, name)))
        return 0, ""


def test_sender_mit_eigener_dateiliste(tmp_path):
    gh = _sender()
    (tmp_path / "bild_beschreibungen.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "bild_orte.csv").write_text("fileid\n", encoding="utf-8")
    adb = _Adb(str(tmp_path))
    code, zeilen = gh.senden(str(tmp_path), "/sdcard/Download", adb, wirklich=True,
                             dateien=["bild_beschreibungen.jsonl", "bild_orte.csv"])
    assert code == 0
    gepusht = [b[-1] for b in adb.befehle if b[1] == "push"]
    assert gepusht == ["/sdcard/Download/bild_beschreibungen.jsonl", "/sdcard/Download/bild_orte.csv"]
    code, zeilen = gh.senden(str(tmp_path), "/sdcard/Download", adb, wirklich=True, dateien=["fehlt.csv"])
    assert code == 2 and "personen_gruppieren" not in zeilen[0]   # Hinweis nur für die Gruppen-Dateien
    assert gh.senden(str(tmp_path), "/sdcard/Download", adb, wirklich=False, dateien=["../geheim"])[0] == 2
    assert gh.main(["--basis", str(tmp_path), "--dateien", "bild_orte.csv"]) == 0       # Trockenlauf
