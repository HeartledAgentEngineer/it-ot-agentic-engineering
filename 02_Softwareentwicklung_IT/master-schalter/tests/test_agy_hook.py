"""Tests für den Antigravity-Empfang per Hook: nur Attrappen unter `tmp_path`, nie echte Quellen.

Belegt sind hier die Unterschiede zu Claude: der Ereignisname kommt aus der Kommandozeile, die Sitzung
heißt `conversationId`, die Ausgabe ist `injectSteps` bzw. `decision: continue`, und es gibt keine
`stop_hook_active`-Sperre – stattdessen die gezählte Schleifenbremse.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from master_schalter import agy_hook, assistent_vorgaenge as av, paare, postfach, signale, status

THEMA = "engineering"
LAUFEND = paare.laufend_bilden(THEMA)
KENNUNG = "geheime-kennung-4711-xyz"          # auffällige Attrappe: darf nie in einer Ausgabe stehen
T0 = datetime(2026, 10, 29, 12, 0, 0, tzinfo=timezone.utc)
INJIZIEREN = ("SessionStart", "PreInvocation", "PostInvocation")


def _ereignis(kennung: object = KENNUNG, nummer: object = 0, **extra: object) -> bytes:
    """stdin-JSON wie Antigravity es schickt: ohne Ereignisnamen (der steht im Aufruf)."""
    inhalt = {"conversationId": kennung, "workspacePaths": ["C:\\irgendwo"],
              "transcriptPath": "C:\\irgendwo\\transcript.jsonl", "invocationNum": nummer, **extra}
    return json.dumps(inhalt).encode("utf-8")


def _lauf(capsys, ereignis: str, eingabe: bytes | None = None) -> tuple[int, str]:
    """Hook im selben Prozess aufrufen: `(Rückgabewert, stdout)`; stderr muss immer leer bleiben."""
    rueckgabe = agy_hook.main([ereignis], eingabe if eingabe is not None else _ereignis())
    ausgabe = capsys.readouterr()
    assert ausgabe.err == ""
    return rueckgabe, ausgabe.out


def _neu_einlegen(umgebung, vorgang_id: str = "v-1", kennung: str = KENNUNG) -> None:
    """Rolle an Antigravity gesetzt (Marke trägt den Vorgang), Phase wie nach dem Einlegen, `neu` liegt bereit."""
    umgebung.vorbereiten(vorgang_id, ziel="agy", von="claude")
    umgebung.uebergeben(vorgang_id, "agy")
    av.aktualisieren(vorgang_id, phase="im_postfach")
    postfach.einlegen("agy", kennung, vorgang_id, THEMA, "neu", LAUFEND)


def _dateien(kennung: str = KENNUNG) -> list[str]:
    ordner = postfach.ordner("agy", kennung)
    return sorted(p.name for p in ordner.glob("*.json")) if ordner.is_dir() else []


def _bremse(stand: int, kennung: str = KENNUNG) -> None:
    pfad = signale.daten_ordner() / agy_hook.BREMSE_DATEI
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({kennung: {"stand": stand, "zeit": time.time()}}), encoding="utf-8")


def _bremse_stand(kennung: str = KENNUNG) -> dict:
    pfad = signale.daten_ordner() / agy_hook.BREMSE_DATEI
    try:
        return json.loads(pfad.read_text(encoding="utf-8")).get(kennung) or {}
    except (OSError, ValueError):
        return {}


def _stand(kennung: str = KENNUNG) -> str:
    """Gemeldeter Status; `None` (keine Datei) ist hier immer ein Fehler."""
    gelesen = status.lesen(agy_hook.WERKZEUG, kennung)
    assert gelesen is not None, "kein Status gemeldet"
    return gelesen[0]


def _nachricht(ausgabe: str) -> str:
    """Der Text der Injektion aus der Ausgabe."""
    daten = json.loads(ausgabe)
    assert set(daten) == {"injectSteps"}
    (schritt,) = daten["injectSteps"]
    assert set(schritt) == {"systemMessage"}
    assert set(schritt["systemMessage"]) == {"systemMessage"}
    return schritt["systemMessage"]["systemMessage"]


# --- Empfang -------------------------------------------------------------------------

@pytest.mark.parametrize("ereignis", INJIZIEREN)
def test_liegende_nachricht_wird_als_systemnachricht_eingespielt(umgebung, capsys, ereignis):
    _neu_einlegen(umgebung)

    rueckgabe, ausgabe = _lauf(capsys, ereignis)

    assert rueckgabe == 0
    zeilen = _nachricht(ausgabe).split("\n")
    assert zeilen[0] == agy_hook.EINLEITUNG == "Nachricht des Master-Schalters:"
    assert zeilen[1:] == [postfach.text("neu", THEMA, LAUFEND, "v-1")]
    assert _dateien() == []                                                   # Postfach leer
    assert (postfach.ordner("agy", KENNUNG) / "erledigt" / "v-1_neu.json").exists()


@pytest.mark.parametrize("ereignis", INJIZIEREN)
def test_zweiter_lauf_gibt_nichts_mehr_aus(umgebung, capsys, ereignis):
    _neu_einlegen(umgebung)
    _lauf(capsys, ereignis)
    assert _lauf(capsys, ereignis)[1] == ""


@pytest.mark.parametrize("ereignis", INJIZIEREN)
def test_ohne_nachricht_gibt_es_keine_ausgabe(umgebung, capsys, ereignis):
    assert _lauf(capsys, ereignis) == (0, "")


def test_nachricht_einer_anderen_sitzung_wird_nicht_abgeholt(umgebung, capsys):
    _neu_einlegen(umgebung, kennung="eine-andere-sitzung")
    assert _lauf(capsys, "PreInvocation")[1] == ""
    assert _dateien("eine-andere-sitzung") == ["v-1_neu.json"]


def test_ausgabe_enthaelt_weder_kennung_noch_absoluten_pfad(umgebung, capsys, tmp_path):
    _neu_einlegen(umgebung)
    ausgabe = _lauf(capsys, "PreInvocation")[1]

    assert KENNUNG not in ausgabe
    assert str(tmp_path) not in ausgabe
    assert str(Path.home()) not in ausgabe


# --- Stop: weiterarbeiten statt ruhen -------------------------------------------------

def test_stop_ohne_nachricht_gibt_leeres_objekt_und_meldet_ruht(umgebung, capsys):
    rueckgabe, ausgabe = _lauf(capsys, "Stop")

    assert rueckgabe == 0
    assert json.loads(ausgabe) == {}
    assert _stand() == status.RUHT


def test_stop_mit_liegender_nachricht_laesst_sofort_weiterarbeiten(umgebung, capsys):
    _neu_einlegen(umgebung)

    rueckgabe, ausgabe = _lauf(capsys, "Stop")

    daten = json.loads(ausgabe)
    assert rueckgabe == 0
    assert daten["decision"] == "continue"
    assert daten["reason"].split("\n")[1:] == [postfach.text("neu", THEMA, LAUFEND, "v-1")]
    assert _dateien() == []                                                   # verbraucht, kein zweites Mal
    assert _stand() == status.ARBEITET


def test_stop_verbucht_jede_fortsetzung_in_der_bremse(umgebung, capsys):
    _neu_einlegen(umgebung)
    _lauf(capsys, "Stop")
    assert _bremse_stand()["stand"] == 1


def test_erschoepfte_bremse_laesst_die_nachricht_liegen(umgebung, capsys):
    """Schutz vor der Endlosschleife: nach `AGY_STOP_MAX` Fortsetzungen wird nicht mehr gedrängt."""
    _neu_einlegen(umgebung)
    _bremse(agy_hook.AGY_STOP_MAX)

    rueckgabe, ausgabe = _lauf(capsys, "Stop")

    assert rueckgabe == 0
    assert json.loads(ausgabe) == {}
    assert _dateien() == ["v-1_neu.json"]                                     # liegt weiterhin bereit
    assert _stand() == status.RUHT


def test_neuer_auftrag_setzt_die_bremse_zurueck(umgebung, capsys):
    """`invocationNum == 0` ist der Beginn eines neuen Auftrags: danach darf wieder weitergearbeitet werden."""
    _neu_einlegen(umgebung)
    _bremse(agy_hook.AGY_STOP_MAX)

    _lauf(capsys, "PreInvocation", _ereignis(nummer=0))
    assert _bremse_stand() == {}

    _neu_einlegen(umgebung, vorgang_id="v-2")     # ein neuer Auftrag liegt bereit
    rueckgabe, ausgabe = _lauf(capsys, "Stop")
    assert json.loads(ausgabe)["decision"] == "continue"


def test_veralteter_zaehlerstand_blockiert_nicht(umgebung, capsys):
    _neu_einlegen(umgebung)
    pfad = signale.daten_ordner() / agy_hook.BREMSE_DATEI
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({KENNUNG: {"stand": agy_hook.AGY_STOP_MAX,
                                          "zeit": time.time() - agy_hook.BREMSE_VERFALL - 1}}), encoding="utf-8")

    assert json.loads(_lauf(capsys, "Stop")[1])["decision"] == "continue"


def test_kaputte_bremsdatei_erlaubt_das_weiterarbeiten(umgebung, capsys):
    _neu_einlegen(umgebung)
    pfad = signale.daten_ordner() / agy_hook.BREMSE_DATEI
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text("kein json", encoding="utf-8")

    assert json.loads(_lauf(capsys, "Stop")[1])["decision"] == "continue"


# --- Status --------------------------------------------------------------------------

def test_status_folgt_den_ereignissen(umgebung, capsys):
    _lauf(capsys, "PreInvocation")
    assert _stand() == status.ARBEITET


def test_statusfehler_verhindert_die_zustellung_nicht(umgebung, capsys, monkeypatch):
    _neu_einlegen(umgebung)

    def kaputt(*_args, **_kwargs):
        raise status.StatusFehler("kaputt")

    monkeypatch.setattr(status, "schreiben", kaputt)
    ausgabe = _lauf(capsys, "PreInvocation")[1]

    assert postfach.text("neu", THEMA, LAUFEND, "v-1") in _nachricht(ausgabe)


# --- Ungültige Eingaben: immer Exit 0, nichts tun --------------------------------------

@pytest.mark.parametrize("eingabe", [b"", b"kein json", b"[]", b"{}", b'{"conversationId": "../boese"}',
                                     b'{"conversationId": 4711}', b'{"conversationId": "x" * 200}'])
def test_ungueltige_eingabe_ergibt_exit_0_ohne_ausgabe_und_ohne_seiteneffekt(umgebung, capsys, eingabe):
    _neu_einlegen(umgebung)

    rueckgabe, ausgabe = _lauf(capsys, "PreInvocation", eingabe)

    assert rueckgabe == 0
    assert ausgabe == ""
    assert _dateien() == ["v-1_neu.json"]


@pytest.mark.parametrize("ereignis", ["", "PreToolUse", "PostToolUse", "preinvocation", "Unfug"])
def test_unbekannter_ereignisname_tut_nichts(umgebung, capsys, ereignis):
    _neu_einlegen(umgebung)

    rueckgabe, ausgabe = _lauf(capsys, ereignis)

    assert rueckgabe == 0
    assert ausgabe == ""
    assert _dateien() == ["v-1_neu.json"]


def test_zu_grosse_eingabe_wird_ignoriert(umgebung, capsys):
    gross = json.dumps({"conversationId": KENNUNG, "fuellung": "x" * agy_hook.MAX_EINGABE}).encode("utf-8")
    _neu_einlegen(umgebung)

    assert _lauf(capsys, "PreInvocation", gross) == (0, "")
    assert _dateien() == ["v-1_neu.json"]


def test_beliebige_ausnahme_im_postfach_wird_geschluckt(umgebung, capsys, monkeypatch):
    _neu_einlegen(umgebung)

    def kaputt(*_args, **_kwargs):
        raise RuntimeError("C:/geheimer/pfad")

    monkeypatch.setattr(postfach, "vormerken", kaputt)
    assert _lauf(capsys, "PreInvocation") == (0, "")


def test_scheitert_die_ausgabe_bleibt_die_nachricht_liegen(umgebung, capsys):
    _neu_einlegen(umgebung)

    def kaputt(_text: str) -> None:
        raise OSError("stdout zu")

    agy_hook.verarbeiten(_ereignis(), "PreInvocation", ausgabe=kaputt)
    capsys.readouterr()

    assert _dateien() == ["v-1_neu.json"]


# --- Aufruf als Modul (echter Prozess) ---------------------------------------------------

def _test_umgebung():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    return env


def test_aufruf_als_modul_mit_umgebung_im_eigenen_prozess(umgebung, tmp_path):
    """Antigravity ruft `python -m master_schalter.agy_hook EREIGNIS` auf: Rückgabe 0, Ausgabe auf stdout."""
    _neu_einlegen(umgebung)
    lauf = subprocess.run([sys.executable, "-m", "master_schalter.agy_hook", "PreInvocation"],
                          input=_ereignis(), capture_output=True, env=_test_umgebung(), timeout=60)
    assert lauf.returncode == 0
    assert lauf.stderr == b""
    assert json.loads(lauf.stdout.decode("utf-8"))["injectSteps"]


def test_aufruf_als_modul_ohne_ereignisname_ergibt_exit_0(umgebung):
    lauf = subprocess.run([sys.executable, "-m", "master_schalter.agy_hook"],
                          input=b"kein json", capture_output=True, env=_test_umgebung(), timeout=60)
    assert lauf.returncode == 0 and lauf.stdout == b"" and lauf.stderr == b""
