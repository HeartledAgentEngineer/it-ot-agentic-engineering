"""Tagesimport am Handy: ``tools/handy/tageslauf.py`` und die Einbindung in den Start (25.10.2026).

Plan: ``.hermes/plans/2026-10-25_tagesimport-handy.md`` (Fassung 1, Schritte C1 und C2).

Offline, nur erfundene Daten in ``tmp_path``: kein Netz, kein Sprachmodell, keine echten Namen.
Die pCloud-Lesefunktion, ``termux-battery-status`` und das Datum sind Attrappen; der
W1-Unterprozess ist ein kleines Python-Skript, das Ausgabe und Exit-Code vorgibt und
seine Aufrufargumente in eine Spurdatei ausserhalb des Datenordners schreibt.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pytest

PROJEKT = Path(__file__).resolve().parents[2]
PFAD_TAGESLAUF = PROJEKT / "tools" / "handy" / "tageslauf.py"
SHARED = PROJEKT / "termux" / "start-vorbereiten.sh"

HEUTE = date(2026, 10, 25)
SENSIBEL = ("Zaunstein", "Anna-Zaunstein", "boesewicht", "GEHEIMTOKEN")

W1_OK = (
    "WhatsApp-Bilder -> pCloud: HOCHLADEN\n"
    "Bilder gefunden: 1.234 (empfangen 1.000, gesendet 234)\n"
    "neu 12 · erledigt 1.222 · fehlt_in_cloud 0 · unklar 0 · unklar_begonnen 0 · bytes 5\n"
    "nicht_bilder 0 · leer 0 · fehler 0\n"
    "hochgeladen 12 · zurueckgestellt 0\n"
    "Datei IMG-Zaunstein.jpg wurde angefasst\n"          # darf nirgends erscheinen
)
W1_FEHLER = (
    "WhatsApp-Bilder -> pCloud: HOCHLADEN\n"
    "neu 3 · erledigt 0\n"
    "nicht_bilder 0 · leer 0 · fehler 3\n"
    "hochgeladen 2 · zurueckgestellt 0\n"
    "abgebrochen: Zielordner nicht anlegbar, keine weiteren Uploads.\n"
    "Fehlerarten: abgelehnt 2002 x3\n"
)


# ── Hilfen ───────────────────────────────────────────────────────────────────

class Umgebung:
    def __init__(self, t, tmp_path: Path) -> None:
        self.t = t
        self.wurzel = tmp_path
        self.daten = tmp_path / "daten"
        self.diag = tmp_path / "diag"
        self.spur_ordner = tmp_path / "spur"
        self.spur_ordner.mkdir()
        self.spur = self.spur_ordner / "w1_aufrufe.txt"
        self.skript = tmp_path / "w1_attrappe.py"
        self.w1(0, W1_OK)

    def w1(self, exit_code: int, ausgabe: str, schlaf: float = 0.0) -> None:
        self.skript.write_text(
            "import sys, time\n"
            f"open({str(self.spur)!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
            f"time.sleep({schlaf!r})\n"
            f"sys.stdout.write({ausgabe!r})\n"
            f"sys.stderr.write('Datei IMG-Zaunstein.jpg Fehler boesewicht\\n')\n"
            f"sys.exit({exit_code!r})\n", encoding="utf-8")

    def w1_aufrufe(self) -> list:
        return self.spur.read_text(encoding="utf-8").splitlines() if self.spur.exists() else []

    def einstellungen(self, **werte) -> None:
        self.daten.mkdir(parents=True, exist_ok=True)
        (self.daten / "tageslauf.json").write_text(json.dumps(werte), encoding="utf-8")

    def stand(self, **werte) -> None:
        self.daten.mkdir(parents=True, exist_ok=True)
        (self.daten / ".tageslauf_stand.json").write_text(json.dumps(werte), encoding="utf-8")

    def stand_lesen(self) -> dict:
        return json.loads((self.daten / ".tageslauf_stand.json").read_text(encoding="utf-8"))

    def bericht_lesen(self) -> dict:
        return json.loads((self.daten / "tageslauf_bericht.json").read_text(encoding="utf-8"))

    def log_text(self) -> str:
        pfad = self.diag / "tageslauf.log"
        return pfad.read_text(encoding="utf-8") if pfad.exists() else ""

    def lauf(self, *modus: str, extra=()) -> int:
        modus = modus or ("--wenn-faellig",)
        return self.t.main(["--daten-ordner", str(self.daten), "--log-ordner", str(self.diag),
                            "--w1-skript", str(self.skript), *modus, *extra])


def momentaufnahme(wurzel: Path) -> list:
    return sorted((str(p.relative_to(wurzel)), p.stat().st_size if p.is_file() else -1)
                  for p in wurzel.rglob("*"))


@pytest.fixture
def t(monkeypatch):
    spec = importlib.util.spec_from_file_location("tageslauf_unter_test", PFAD_TAGESLAUF)
    modul = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "tageslauf_unter_test", modul)   # @dataclass braucht das
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture
def env(t, tmp_path, monkeypatch):
    umg = Umgebung(t, tmp_path)
    monkeypatch.setattr(t, "_heute", lambda: HEUTE)
    monkeypatch.setattr(t, "_akku_ausgabe", lambda: None)

    def kein_netz(methode, felder):
        raise AssertionError("pCloud-Aufruf ohne eingerichteten Kamera-Ordner")
    monkeypatch.setattr(t, "_pcloud_lesen", kein_netz)
    return umg


def alles_ausgabe(capsys) -> str:
    gelesen = capsys.readouterr()
    return gelesen.out + gelesen.err


# ── Aufruf ───────────────────────────────────────────────────────────────────

def test_ohne_modus_ist_aufrauffehler(env, capsys):
    assert env.t.main(["--daten-ordner", str(env.daten)]) == 2


def test_modi_schliessen_sich_aus(env):
    assert env.t.main(["--daten-ordner", str(env.daten), "--jetzt", "--trocken"]) == 2


# ── Schalter aus: kein Schreibvorgang ────────────────────────────────────────

def _spione(t, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("Schreibweg oder Unterprozess trotz ausgeschaltetem Tagesimport")
    for name in ("_atomar_schreiben", "_sperre_nehmen", "_log_schreiben"):
        monkeypatch.setattr(t, name, boom)
    monkeypatch.setattr(t.subprocess, "run", boom)


@pytest.mark.parametrize("modus", ["--wenn-faellig", "--jetzt", "--trocken"])
def test_standard_ist_aus_und_schreibt_nichts(env, t, monkeypatch, capsys, modus):
    env.daten.mkdir()                                    # Ordner da, aber keine Einstellungsdatei
    vorher = momentaufnahme(env.wurzel)
    _spione(t, monkeypatch)
    assert env.lauf(modus) == 0
    assert "Tagesimport: aus" in alles_ausgabe(capsys)
    assert momentaufnahme(env.wurzel) == vorher           # auch keine Stand-Datei, kein Log


def test_ohne_datenordner_wird_auch_keiner_angelegt(env, t, monkeypatch, capsys):
    vorher = momentaufnahme(env.wurzel)
    _spione(t, monkeypatch)
    assert env.lauf("--jetzt") == 0
    assert not env.daten.exists() and not env.diag.exists()
    assert momentaufnahme(env.wurzel) == vorher


def test_ausdruecklich_aus_schreibt_nichts(env, t, monkeypatch, capsys):
    env.einstellungen(an=False)
    vorher = momentaufnahme(env.wurzel)
    _spione(t, monkeypatch)
    assert env.lauf() == 0
    assert "Tagesimport: aus" in alles_ausgabe(capsys)
    assert momentaufnahme(env.wurzel) == vorher


def test_nur_echtes_true_schaltet_ein(env, t, monkeypatch, capsys):
    for wert in ("true", 1, "ja", None):
        env.einstellungen(an=wert)
        _spione(t, monkeypatch)
        assert env.lauf() == 0
    assert env.w1_aufrufe() == []


def test_unlesbare_einstellungen_sind_aus_und_nicht_pruefbar(env, t, monkeypatch, capsys):
    env.daten.mkdir()
    (env.daten / "tageslauf.json").write_text("{kaputt", encoding="utf-8")
    vorher = momentaufnahme(env.wurzel)
    _spione(t, monkeypatch)
    assert env.lauf() == 3
    assert "Tagesimport: aus" in alles_ausgabe(capsys)
    assert momentaufnahme(env.wurzel) == vorher


# ── Faelligkeit ──────────────────────────────────────────────────────────────

def test_nicht_faellig_wenn_heute_schon_gelaufen(env, t, monkeypatch, capsys):
    env.einstellungen(an=True)
    env.stand(letzter_gesamtlauf=HEUTE.isoformat())
    vorher = momentaufnahme(env.wurzel)
    _spione(t, monkeypatch)
    assert env.lauf("--wenn-faellig") == 0
    ausgabe = alles_ausgabe(capsys)
    assert len([z for z in ausgabe.splitlines() if z.strip()]) == 1
    assert "heute schon" in ausgabe
    assert momentaufnahme(env.wurzel) == vorher


@pytest.mark.parametrize("stand", [
    {"letzter_gesamtlauf": (HEUTE - timedelta(days=1)).isoformat()},
    {"letzter_gesamtlauf": "kein-datum"},
    {},
])
def test_faellig_wenn_nicht_heute(env, capsys, stand):
    env.einstellungen(an=True)
    env.stand(**stand)
    assert env.lauf("--wenn-faellig") == 0
    assert len(env.w1_aufrufe()) == 1


def test_defekte_stand_datei_gilt_als_faellig(env, capsys):
    env.einstellungen(an=True)
    env.daten.joinpath(".tageslauf_stand.json").write_text("[kaputt", encoding="utf-8")
    assert env.lauf("--wenn-faellig") == 0
    assert env.stand_lesen()["letzter_gesamtlauf"] == HEUTE.isoformat()


def test_jetzt_ignoriert_die_faelligkeit(env, capsys):
    env.einstellungen(an=True)
    env.stand(letzter_gesamtlauf=HEUTE.isoformat())
    assert env.lauf("--jetzt") == 0
    assert len(env.w1_aufrufe()) == 1


# ── Erfolgreicher Gesamtlauf ─────────────────────────────────────────────────

def test_gesamtlauf_schreibt_stand_bericht_und_log(env, capsys):
    env.einstellungen(an=True)
    assert env.lauf() == 0
    ausgabe = alles_ausgabe(capsys)
    assert "WhatsApp-Bilder: 12 hochgeladen" in ausgabe
    assert "WhatsApp-Chats: nicht eingerichtet (W2 Teil B)" in ausgabe
    assert "Kamera: nicht eingerichtet" in ausgabe
    assert "Gemini: Takeout-Export fällig (alle 2 Monate)" in ausgabe
    assert env.w1_aufrufe() == ["--schreiben"]           # ohne --max
    stand = env.stand_lesen()
    assert stand["letzter_gesamtlauf"] == HEUTE.isoformat()
    assert stand["bausteine"]["wa_bilder"] == HEUTE.isoformat()
    bericht = env.bericht_lesen()
    assert bericht["exit"] == 0 and bericht["stand_fortgeschrieben"] is True
    assert [b["name"] for b in bericht["bausteine"]] == [
        "wa_bilder", "wa_chats", "kamera", "gemini"]
    assert bericht["bausteine"][0]["zahlen"]["hochgeladen"] == 12
    assert "WhatsApp-Bilder: 12 hochgeladen" in env.log_text()
    # nichts Liegengebliebenes: keine Temp-Dateien, Sperre freigegeben
    namen = sorted(p.name for p in env.daten.iterdir())
    assert namen == [".tageslauf_stand.json", "tageslauf.json", "tageslauf_bericht.json"]


def test_zweiter_start_am_selben_tag_startet_nichts(env, capsys):
    env.einstellungen(an=True)
    assert env.lauf() == 0
    assert env.lauf() == 0
    assert len(env.w1_aufrufe()) == 1


def test_w1_zahlen_werden_deutsch_gelesen(t):
    z = t.w1_auswerten("hochgeladen 1.234 · zurueckgestellt 0\nnicht_bilder 0 · fehler 5\n")
    assert z["hochgeladen"] == 1234 and z["fehler"] == 5
    assert t.w1_auswerten("nix")["hochgeladen"] is None


# ── Sperre ───────────────────────────────────────────────────────────────────

def _sperre(env: Umgebung, alter_s: float, mit_kennung: bool = True) -> Path:
    sperre = env.daten / ".tageslauf.sperre"
    sperre.mkdir(parents=True)
    if mit_kennung:
        (sperre / "kennung.json").write_text(
            json.dumps({"kennung": "abcdef123456", "pid": 1, "start": time.time() - alter_s}),
            encoding="utf-8")
    alt = time.time() - alter_s
    os.utime(sperre, (alt, alt))
    return sperre


def test_doppelstart_wird_verhindert(env, capsys):
    env.einstellungen(an=True)
    sperre = _sperre(env, alter_s=60)
    assert env.lauf() == 0
    assert "läuft bereits" in alles_ausgabe(capsys)
    assert env.w1_aufrufe() == []
    assert sperre.is_dir() and (sperre / "kennung.json").exists()      # fremde Sperre bleibt
    assert not (env.daten / ".tageslauf_stand.json").exists()


def test_verwaiste_eigene_sperre_wird_abgeraeumt_und_lauf_startet(env, capsys):
    env.einstellungen(an=True)
    _sperre(env, alter_s=7 * 3600)
    assert env.lauf() == 0
    assert len(env.w1_aufrufe()) == 1
    assert not (env.daten / ".tageslauf.sperre").exists()


def test_alte_sperre_ohne_kennung_wird_nicht_angefasst(env, capsys):
    env.einstellungen(an=True)
    sperre = _sperre(env, alter_s=7 * 3600, mit_kennung=False)
    assert env.lauf() == 3
    assert "Sperre unklar" in alles_ausgabe(capsys)
    assert env.w1_aufrufe() == []
    assert sperre.is_dir()


def test_junge_sperre_ohne_kennung_gilt_als_laufend(env, capsys):
    env.einstellungen(an=True)
    _sperre(env, alter_s=60, mit_kennung=False)
    assert env.lauf() == 0
    assert "läuft bereits" in alles_ausgabe(capsys)
    assert env.w1_aufrufe() == []


def test_sperre_wird_auch_nach_ausnahme_freigegeben(env, t, monkeypatch, capsys):
    env.einstellungen(an=True)

    def kaputt(*a, **k):
        raise RuntimeError("Zaunstein")
    monkeypatch.setattr(t, "baustein_gemini", kaputt)
    env.lauf()
    assert not (env.daten / ".tageslauf.sperre").exists()


def test_trocken_nimmt_keine_sperre(env, t, monkeypatch, capsys):
    env.einstellungen(an=True)

    def boom(*a, **k):
        raise AssertionError("Sperre im Trockenlauf")
    monkeypatch.setattr(t, "_sperre_nehmen", boom)
    assert env.lauf("--trocken") == 0


# ── Akku ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,niedrig", [
    (json.dumps({"percentage": 15, "status": "DISCHARGING", "plugged": "UNPLUGGED"}), True),
    (json.dumps({"percentage": 19, "status": "NOT_CHARGING", "plugged": "UNPLUGGED"}), True),
    (json.dumps({"percentage": 15, "status": "CHARGING", "plugged": "PLUGGED_AC"}), False),
    (json.dumps({"percentage": 15, "status": "FULL", "plugged": "PLUGGED_USB"}), False),
    (json.dumps({"percentage": 20, "status": "DISCHARGING", "plugged": "UNPLUGGED"}), False),
    (json.dumps({"percentage": 80, "status": "DISCHARGING", "plugged": "UNPLUGGED"}), False),
    ("kein json", False),
    ("", False),
    (None, False),
])
def test_akku_deuten(t, text, niedrig):
    assert t.akku_niedrig(text) is niedrig


def test_niedriger_akku_ueberspringt_den_schreibenden_baustein(env, t, monkeypatch, capsys):
    env.einstellungen(an=True)
    monkeypatch.setattr(t, "_akku_ausgabe", lambda: json.dumps(
        {"percentage": 10, "status": "DISCHARGING", "plugged": "UNPLUGGED"}))
    assert env.lauf() == 0
    ausgabe = alles_ausgabe(capsys)
    assert "Akku niedrig" in ausgabe
    assert env.w1_aufrufe() == []
    assert "Gemini:" in ausgabe                             # lesende Bausteine laufen weiter
    assert not (env.daten / ".tageslauf_stand.json").exists()   # nicht vollständig: morgen/nächster Start


def test_laden_trotz_niedrigem_akku_laeuft(env, t, monkeypatch, capsys):
    env.einstellungen(an=True)
    monkeypatch.setattr(t, "_akku_ausgabe", lambda: json.dumps(
        {"percentage": 10, "status": "CHARGING", "plugged": "PLUGGED_AC"}))
    assert env.lauf() == 0
    assert len(env.w1_aufrufe()) == 1


def test_akku_ausgabe_ohne_befehl_ist_none(t, monkeypatch):
    monkeypatch.setattr(t.shutil, "which", lambda name: None)
    assert t._akku_ausgabe() is None


# ── Fehler eines Bausteins stoppt die anderen nicht ──────────────────────────

@pytest.mark.parametrize("w1_exit,erwartet", [(1, 1), (2, 2), (3, 3)])
def test_w1_fehler_ist_isoliert_und_exit_spiegelt_ihn(env, t, monkeypatch, capsys, w1_exit, erwartet):
    env.einstellungen(an=True, kamera_ordner="/Kamera")
    env.w1(w1_exit, W1_FEHLER)
    aufrufe = []

    def lesen(methode, felder):
        aufrufe.append(methode)
        return {"metadata": {"contents": [{"isfolder": False}, {"isfolder": False}]}}
    monkeypatch.setattr(t, "_pcloud_lesen", lesen)
    assert env.lauf() == erwartet
    ausgabe = alles_ausgabe(capsys)
    assert "Kamera: 2 Dateien (Grundstand)" in ausgabe          # Baustein 3 lief trotzdem
    assert "Gemini:" in ausgabe                                 # Baustein 4 lief trotzdem
    assert aufrufe == ["listfolder"]
    assert not (env.daten / ".tageslauf_stand.json").exists()   # Stand nicht fortgeschrieben
    bericht = env.bericht_lesen()
    assert bericht["exit"] == erwartet and bericht["stand_fortgeschrieben"] is False
    assert not (env.daten / ".tageslauf.sperre").exists()


def test_w1_fehlerzeile_nennt_nur_zahlen(env, capsys):
    env.einstellungen(an=True)
    env.w1(1, W1_FEHLER)
    assert env.lauf() == 1
    ausgabe = alles_ausgabe(capsys)
    assert "WhatsApp-Bilder: 2 hochgeladen, 3 Fehler" in ausgabe
    assert "abgebrochen" in ausgabe


def test_fehler_laesst_bisherigen_stand_unveraendert(env, capsys):
    gestern = (HEUTE - timedelta(days=1)).isoformat()
    env.einstellungen(an=True)
    env.stand(letzter_gesamtlauf=gestern, kamera_zahl=7)
    env.w1(1, W1_FEHLER)
    assert env.lauf() == 1
    assert env.stand_lesen() == {"letzter_gesamtlauf": gestern, "kamera_zahl": 7}


def test_w1_zeitgrenze_ist_ein_fehler(env, capsys):
    env.einstellungen(an=True)
    env.w1(0, W1_OK, schlaf=30)
    assert env.lauf(extra=("--w1-zeitgrenze", "1")) == 1
    assert "Zeitgrenze" in alles_ausgabe(capsys)
    assert not (env.daten / ".tageslauf_stand.json").exists()


def test_w1_exit3_und_zeitgrenze_nennen_festen_hinweis(env, capsys):
    # Hermes R1-1: nach hartem Abbruch bleibt die W1-Sperre liegen -> jeder Folgelauf Exit 3.
    # Ohne Hinweis stuende im Log keine Ursache; ein fester Text, keine Rohausgabe von W1.
    env.einstellungen(an=True)
    env.w1(3, "Sperre /geheim/pfad belegt\n")
    assert env.lauf() == 3
    ausgabe = alles_ausgabe(capsys)
    assert "WhatsApp-Bilder: Voraussetzung fehlt (Exit 3; W1-Sperre/Manifest prüfen)" in ausgabe
    assert "/geheim/pfad" not in ausgabe
    env.w1(0, W1_OK, schlaf=30)
    assert env.lauf(extra=("--w1-zeitgrenze", "1")) == 1
    assert "Zeitgrenze überschritten (W1-Sperre/Manifest prüfen)" in alles_ausgabe(capsys)


def test_fehlendes_w1_werkzeug_ist_nicht_pruefbar(env, capsys):
    env.einstellungen(an=True)
    env.skript.unlink()
    assert env.lauf() == 3
    assert "Gemini:" in alles_ausgabe(capsys)


def test_w1_exit_null_ohne_lesbare_ausgabe_ist_nicht_pruefbar(env, capsys):
    env.einstellungen(an=True)
    env.w1(0, "irgendwas\n")
    assert env.lauf() == 3


def test_unerwartete_ausnahme_in_einem_baustein_ist_isoliert(env, t, monkeypatch, capsys):
    env.einstellungen(an=True, kamera_ordner="/Kamera")

    def kaputt(methode, felder):
        raise RuntimeError("Anna-Zaunstein /privat/pfad")
    monkeypatch.setattr(t, "_pcloud_lesen", kaputt)
    assert env.lauf() == 1
    ausgabe = alles_ausgabe(capsys)
    assert "Kamera: Zählung fehlgeschlagen (RuntimeError)" in ausgabe
    assert "Gemini:" in ausgabe and "WhatsApp-Bilder: 12 hochgeladen" in ausgabe
    assert "Zaunstein" not in ausgabe + env.log_text() + json.dumps(env.bericht_lesen())


def test_ausnahme_in_der_baustein_funktion_selbst_wird_gefangen(env, t, monkeypatch, capsys):
    env.einstellungen(an=True)

    def kaputt(*a, **k):
        raise ValueError("Anna-Zaunstein")
    monkeypatch.setattr(t, "baustein_kamera", kaputt)
    assert env.lauf() == 1
    ausgabe = alles_ausgabe(capsys)
    assert "Kamera: unerwarteter Fehler (ValueError)" in ausgabe
    assert "Gemini:" in ausgabe and "Zaunstein" not in ausgabe


# ── Kamera zaehlen (nur lesend) ──────────────────────────────────────────────

def _pcloud_attrappe(t, monkeypatch, zaehler: list, dateien: int, ordner: int = 1):
    def lesen(methode, felder):
        zaehler.append((methode, dict(felder)))
        inhalt = [{"isfolder": False, "name": f"IMG-Zaunstein-{i}.jpg"} for i in range(dateien)]
        inhalt += [{"isfolder": True, "name": "Anna-Zaunstein"} for _ in range(ordner)]
        return {"result": 0, "metadata": {"contents": inhalt}}
    monkeypatch.setattr(t, "_pcloud_lesen", lesen)


def test_kamera_grundstand_und_dann_neue_dateien(env, t, monkeypatch, capsys):
    aufrufe: list = []
    env.einstellungen(an=True, kamera_ordner="/Automatic Upload")
    _pcloud_attrappe(t, monkeypatch, aufrufe, dateien=3)
    assert env.lauf("--jetzt") == 0
    assert "Kamera: 3 Dateien (Grundstand)" in alles_ausgabe(capsys)
    assert env.stand_lesen()["kamera_zahl"] == 3
    _pcloud_attrappe(t, monkeypatch, aufrufe, dateien=8)
    assert env.lauf("--jetzt") == 0
    assert "Kamera: 5 neue Dateien seit letztem Lauf" in alles_ausgabe(capsys)
    assert env.stand_lesen()["kamera_zahl"] == 8
    # ausschliesslich lesende Methode, Pfad unveraendert, nicht rekursiv
    assert {m for m, _ in aufrufe} == {"listfolder"}
    assert all(f == {"path": "/Automatic Upload"} for _, f in aufrufe)


def test_kamera_weniger_dateien_sind_null_neue(env, t, monkeypatch, capsys):
    env.einstellungen(an=True, kamera_ordner="/Kamera")
    env.stand(letzter_gesamtlauf="2026-10-01", kamera_zahl=10)
    _pcloud_attrappe(t, monkeypatch, [], dateien=4)
    assert env.lauf() == 0
    assert "Kamera: 0 neue Dateien seit letztem Lauf" in alles_ausgabe(capsys)


def test_kamera_gibt_keine_dateinamen_aus(env, t, monkeypatch, capsys):
    env.einstellungen(an=True, kamera_ordner="/Kamera")
    _pcloud_attrappe(t, monkeypatch, [], dateien=3)
    assert env.lauf() == 0
    text = alles_ausgabe(capsys) + env.log_text() + json.dumps(env.bericht_lesen())
    assert "Zaunstein" not in text and "IMG-" not in text


@pytest.mark.parametrize("pfad", [
    "/Crypto Folder", "/Privat/crypto folder/x", "Kamera/../Anderes", "/a\\b", "//x", "", 5,
])
def test_kamera_unzulaessiger_ordner_wird_nicht_gelesen(env, t, monkeypatch, capsys, pfad):
    env.einstellungen(an=True, kamera_ordner=pfad)

    def boom(methode, felder):
        raise AssertionError("pCloud trotz unzulaessigem Ordner")
    monkeypatch.setattr(t, "_pcloud_lesen", boom)
    rc = env.lauf()
    ausgabe = alles_ausgabe(capsys)
    if pfad in ("", 5):
        assert "Kamera: nicht eingerichtet" in ausgabe
    else:
        assert rc == 2 and "Kamera: Ordner nicht zulässig" in ausgabe


def test_kamera_voraussetzung_fehlt_ist_nicht_pruefbar(env, t, monkeypatch, capsys):
    env.einstellungen(an=True, kamera_ordner="/Kamera")

    def fehlt(methode, felder):
        raise t.gemeinsam.Voraussetzung("Voraussetzung fehlt: Zaunstein")
    monkeypatch.setattr(t, "_pcloud_lesen", fehlt)
    assert env.lauf() == 3
    ausgabe = alles_ausgabe(capsys)
    assert "Kamera: Voraussetzung fehlt" in ausgabe and "Zaunstein" not in ausgabe


def test_kamera_unlesbare_antwort_ist_ein_fehler(env, t, monkeypatch, capsys):
    env.einstellungen(an=True, kamera_ordner="/Kamera")
    monkeypatch.setattr(t, "_pcloud_lesen", lambda m, f: {"result": 0})
    assert env.lauf() == 1


def test_pcloud_lesen_kennt_nur_lesende_methoden(t):
    for methode in ("uploadfile", "createfolderifnotexists", "deletefile", "renamefile",
                    "copyfile", "extractarchive"):
        with pytest.raises(ValueError):
            t._pcloud_lesen(methode, {})


# ── Gemini-Erinnerung ────────────────────────────────────────────────────────

@pytest.mark.parametrize("wert,faellig,text", [
    (None, True, "Gemini: Takeout-Export fällig (alle 2 Monate)"),
    ("kein-datum", True, "Gemini: Takeout-Export fällig (alle 2 Monate)"),
    (5, True, "Gemini: Takeout-Export fällig (alle 2 Monate)"),
    ((HEUTE - timedelta(days=61)).isoformat(), True, "Gemini: Takeout-Export fällig (alle 2 Monate)"),
    ((HEUTE - timedelta(days=60)).isoformat(), False, "Gemini: ok (letzter Export vor 60 Tagen)"),
    ((HEUTE - timedelta(days=10)).isoformat(), False, "Gemini: ok (letzter Export vor 10 Tagen)"),
    (HEUTE.isoformat(), False, "Gemini: ok (letzter Export vor 0 Tagen)"),
    ((HEUTE + timedelta(days=3)).isoformat(), True, "Gemini: Takeout-Export fällig (alle 2 Monate)"),
])
def test_gemini_erinnerung(t, monkeypatch, wert, faellig, text):
    monkeypatch.setattr(t, "_heute", lambda: HEUTE)
    ergebnis = t.baustein_gemini({"gemini_letzter_export": wert})
    assert ergebnis.text == text
    assert ergebnis.exit == 0 and ergebnis.vollstaendig is True      # nur Erinnerung


def test_gemini_ohne_netz_und_ohne_unterprozess(env, t, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("Netz oder Unterprozess im Gemini-Baustein")
    monkeypatch.setattr(t.subprocess, "run", boom)
    monkeypatch.setattr(t, "_pcloud_lesen", boom)
    t.baustein_gemini({})


# ── Bericht: nur Zahlen und feste Texte ──────────────────────────────────────

def test_bericht_enthaelt_keine_pfade_oder_namen(env, t, monkeypatch, capsys):
    env.einstellungen(an=True, kamera_ordner="/Anna-Zaunstein/Kamera",
                      gemini_letzter_export=(HEUTE - timedelta(days=3)).isoformat())
    _pcloud_attrappe(t, monkeypatch, [], dateien=2)
    assert env.lauf() == 0
    gesamt = "\n".join([alles_ausgabe(capsys), env.log_text(),
                        (env.daten / "tageslauf_bericht.json").read_text(encoding="utf-8")])
    for wort in SENSIBEL + ("IMG-", "Kamera/", "/Anna", "Automatic"):
        assert wort not in gesamt, wort
    assert str(env.wurzel) not in gesamt
    assert str(env.wurzel).replace("\\", "/") not in gesamt
    assert "Kamera: 2 Dateien (Grundstand)" in gesamt


def test_log_wird_angehaengt(env, capsys):
    env.einstellungen(an=True)
    env.lauf("--jetzt")
    erste = env.log_text()
    env.lauf("--jetzt")
    zweite = env.log_text()
    assert zweite.startswith(erste) and len(zweite) > len(erste)


# ── Trockenlauf ──────────────────────────────────────────────────────────────

def test_trocken_zeigt_aber_schreibt_nichts(env, t, monkeypatch, capsys):
    env.einstellungen(an=True, kamera_ordner="/Kamera")
    _pcloud_attrappe(t, monkeypatch, [], dateien=3)
    env.w1(0, "neu 4 · erledigt 0\nnicht_bilder 0 · leer 0 · fehler 0\n")
    vorher = momentaufnahme(env.daten)
    assert env.lauf("--trocken") == 0
    ausgabe = alles_ausgabe(capsys)
    assert "Kamera: 3 Dateien (Grundstand)" in ausgabe
    assert "4 neu" in ausgabe
    assert env.w1_aufrufe() == [""]                      # kein --schreiben
    assert not env.diag.exists()
    assert momentaufnahme(env.daten) == vorher


# ── Schutz ───────────────────────────────────────────────────────────────────

def test_datenordner_im_git_repo_ist_schutzverstoss(env, t, capsys, tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    rc = t.main(["--daten-ordner", str(repo / "daten"), "--log-ordner", str(env.diag),
                 "--w1-skript", str(env.skript), "--jetzt"])
    assert rc == 2
    assert not (repo / "daten").exists()
    assert env.w1_aufrufe() == []


def test_logordner_im_git_repo_ist_schutzverstoss(env, t, capsys, tmp_path):
    repo = tmp_path / "repo2"
    (repo / ".git").mkdir(parents=True)
    env.einstellungen(an=True)
    assert t.main(["--daten-ordner", str(env.daten), "--log-ordner", str(repo / "diag"),
                   "--w1-skript", str(env.skript), "--jetzt"]) == 2
    assert env.w1_aufrufe() == []


def test_stand_als_symbolischer_link_ist_schutzverstoss(env, capsys, tmp_path):
    env.einstellungen(an=True)
    ziel = tmp_path / "fremd.json"
    ziel.write_text("{}", encoding="utf-8")
    try:
        os.symlink(ziel, env.daten / ".tageslauf_stand.json")
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks nicht erlaubt")
    assert env.lauf() == 2
    assert env.w1_aufrufe() == []
    assert ziel.read_text(encoding="utf-8") == "{}"


def test_stand_mit_hartem_link_wird_nicht_beschrieben(env, t, tmp_path):
    env.einstellungen(an=True)
    fremd = tmp_path / "fremd2.json"
    fremd.write_text("{}", encoding="utf-8")
    ziel = env.daten / "tageslauf_bericht.json"
    try:
        os.link(fremd, ziel)
    except (OSError, NotImplementedError):
        pytest.skip("harte Links nicht erlaubt")
    assert env.lauf() == 2
    assert fremd.read_text(encoding="utf-8") == "{}"


def test_schreiben_ist_atomar_ueber_replace(env, t, monkeypatch, tmp_path):
    ziel = tmp_path / "x.json"
    ziel.write_text("alt", encoding="utf-8")
    gesehen = []
    echt = os.replace

    def spion(quelle, ziel_pfad):
        gesehen.append((os.path.exists(quelle), Path(ziel_pfad).name))
        return echt(quelle, ziel_pfad)
    monkeypatch.setattr(t.os, "replace", spion)
    t._atomar_schreiben(str(ziel), "neu")
    assert gesehen == [(True, "x.json")]
    assert ziel.read_text(encoding="utf-8") == "neu"
    assert [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")] == []


def test_werkzeug_hat_keinen_loeschweg_und_keinen_schreibenden_pcloud_aufruf():
    quelltext = PFAD_TAGESLAUF.read_text(encoding="utf-8")
    for verboten in ("rmtree", "unlink", "shutil.move", "os.rename", "uploadfile",
                     "deletefile", "renamefile", "copyfile", "createfolder", "extractarchive",
                     "--max"):
        assert verboten not in quelltext, verboten
    # os.remove nur fuer die eigene Sperrkennung
    assert quelltext.count("os.remove(") <= 2


# ── Exit-Code: der schlechteste Baustein ─────────────────────────────────────

def test_gesamt_exit_ist_der_schlechteste(t):
    E = t.Ergebnis
    liste = [E("a", "ok", 0, "x", {}, True), E("b", "fehler", 1, "x", {}, False),
             E("c", "nicht_pruefbar", 3, "x", {}, False), E("d", "aufruf", 2, "x", {}, False)]
    assert t.schlechtester_exit(liste) == 3
    assert t.schlechtester_exit(liste[:2]) == 1
    assert t.schlechtester_exit([]) == 0


# ── C2: Einbindung in den Start ──────────────────────────────────────────────

def _bash():
    bash = shutil.which("bash")
    if not bash or "system32" in bash.lower():
        pytest.skip("Git Bash nicht vorhanden")
    return bash


def _posix(p: Path) -> str:
    return str(p).replace("\\", "/")


def test_start_vorbereiten_ruft_tageslauf_im_hintergrund_auf():
    text = SHARED.read_text(encoding="utf-8")
    zeilen = [z for z in text.splitlines()
              if "tageslauf.py" in z and "nohup" in z and not z.lstrip().startswith("#")]
    assert len(zeilen) == 1, zeilen
    zeile = zeilen[0]
    assert "--wenn-faellig" in zeile
    assert "nohup" in zeile and ">/dev/null 2>&1" in zeile
    # im Hintergrund (' & ' in einer Unterhuelle) und mit '|| true' abgesichert
    assert re.search(r"&\s*\)\s*\|\|\s*true\s*$", zeile), zeile
    assert 'python -B tools/handy/tageslauf.py' in zeile


def test_tageslauf_steht_nach_sicherung_und_daemon():
    AUFRUF = "python -B tools/handy/tageslauf.py"
    text = SHARED.read_text(encoding="utf-8")
    assert text.index('bash "$HIER/sicherung-auftrag.sh" || true') < text.index(AUFRUF)
    assert text.index('_daemon_skript="hermes_inbox_daemon.py"') < text.index(AUFRUF)
    assert text.index(AUFRUF) < text.rindex("exit 0")


def test_start_vorbereiten_ist_reine_lf_und_syntaktisch_sauber():
    roh = SHARED.read_bytes()
    assert b"\r" not in roh, "start-vorbereiten.sh: reine LF verlangt"
    ergebnis = subprocess.run([_bash(), "-n", _posix(SHARED)], capture_output=True, text=True)
    assert ergebnis.returncode == 0, ergebnis.stderr


def test_start_blockiert_nicht_und_startet_tageslauf_mit_log_ordner(tmp_path):
    bash = _bash()
    sb = tmp_path / "projekt"
    (sb / "termux").mkdir(parents=True)
    (sb / "backend").mkdir()
    (sb / "tools" / "handy").mkdir(parents=True)
    shutil.copy(SHARED, sb / "termux" / "start-vorbereiten.sh")
    (sb / "tools" / "handy" / "tageslauf.py").write_text("# Attrappe\n", encoding="utf-8")
    heim = tmp_path / "heim"
    (heim / "storage" / "downloads").mkdir(parents=True)
    bin_ordner = tmp_path / "bin"
    bin_ordner.mkdir()
    marke = tmp_path / "marke.txt"
    (bin_ordner / "python").write_bytes((
        '#!/bin/sh\n'
        'case "$*" in\n'
        f'  *tageslauf.py*) echo "$*" >> "{_posix(marke)}"; sleep 12 ;;\n'
        'esac\n'
        'exit 0\n').encode())
    umgebung = dict(os.environ, HOME=_posix(heim),
                    PATH=_posix(bin_ordner) + os.pathsep + os.environ.get("PATH", ""))
    for v in ("MSYS2_ARG_CONV_EXCL", "MSYS_NO_PATHCONV", "PROJEKT"):
        umgebung.pop(v, None)
    start = time.monotonic()
    with open(tmp_path / "start_aus.txt", "wb") as aus:          # Datei statt Pipe: kein Warten
        lauf = subprocess.run([bash, _posix(sb / "termux" / "start-vorbereiten.sh")],
                              env=umgebung, stdout=aus, stderr=subprocess.STDOUT, timeout=60)
    dauer = time.monotonic() - start
    assert lauf.returncode == 0, (tmp_path / "start_aus.txt").read_text(errors="replace")
    assert dauer < 10, f"Start hat auf den Tageslauf gewartet ({dauer:.1f} s)"
    for _ in range(100):
        if marke.exists() and marke.read_text(encoding="utf-8").strip():
            break
        time.sleep(0.1)
    aufruf = marke.read_text(encoding="utf-8")
    assert "-B" in aufruf and "tools/handy/tageslauf.py" in aufruf
    assert "--wenn-faellig" in aufruf
    assert "--log-ordner" in aufruf and "hermes_diag" in aufruf


def test_start_laeuft_auch_ohne_tageslauf_werkzeug(tmp_path):
    bash = _bash()
    sb = tmp_path / "projekt"
    (sb / "termux").mkdir(parents=True)
    (sb / "backend").mkdir()
    shutil.copy(SHARED, sb / "termux" / "start-vorbereiten.sh")
    heim = tmp_path / "heim"
    (heim / "storage" / "downloads").mkdir(parents=True)
    bin_ordner = tmp_path / "bin"
    bin_ordner.mkdir()
    (bin_ordner / "python").write_bytes(b"#!/bin/sh\nexit 1\n")          # sogar Fehlschlag
    umgebung = dict(os.environ, HOME=_posix(heim),
                    PATH=_posix(bin_ordner) + os.pathsep + os.environ.get("PATH", ""))
    for v in ("MSYS2_ARG_CONV_EXCL", "MSYS_NO_PATHCONV", "PROJEKT"):
        umgebung.pop(v, None)
    lauf = subprocess.run([bash, _posix(sb / "termux" / "start-vorbereiten.sh")],
                          env=umgebung, capture_output=True, text=True, encoding="utf-8",
                          timeout=60)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
