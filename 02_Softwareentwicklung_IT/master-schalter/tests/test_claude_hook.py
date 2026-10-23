"""Tests für den Claude-Empfang per Hook (P3a) und das Statusregister (K2): nur Attrappen unter `tmp_path`."""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from master_schalter import assistent_vorgaenge as av
from master_schalter import claude_hook, modi, paare, postfach, status, zustand

THEMA = "engineering"
LAUFEND = paare.laufend_bilden(THEMA)
KENNUNG = "geheime-kennung-4711-xyz"          # auffällige Attrappe: darf nie in einer Ausgabe stehen
T0 = datetime(2026, 10, 23, 12, 0, 0, tzinfo=timezone.utc)


def _ereignis(name: str = "UserPromptSubmit", kennung: object = KENNUNG, **extra: object) -> bytes:
    inhalt = {"hook_event_name": name, "session_id": kennung, "cwd": "C:\\irgendwo", **extra}
    return json.dumps(inhalt).encode("utf-8")


def _lauf(capsys, eingabe: bytes) -> tuple[int, str]:
    """Hook im selben Prozess aufrufen: `(Rückgabewert, stdout)`; stderr muss immer leer bleiben."""
    rueckgabe = claude_hook.main(eingabe)
    ausgabe = capsys.readouterr()
    assert ausgabe.err == ""
    return rueckgabe, ausgabe.out


def _neu_einlegen(umgebung, vorgang_id="v-1", kennung=KENNUNG):
    """Rolle an Claude gesetzt (Marke trägt den Vorgang), Phase wie nach dem Einlegen, `neu` liegt bereit."""
    umgebung.vorbereiten(vorgang_id, ziel="claude", von="hermes")
    umgebung.uebergeben(vorgang_id, "claude")
    av.aktualisieren(vorgang_id, phase="im_postfach")
    postfach.einlegen("claude", kennung, vorgang_id, THEMA, "neu", LAUFEND)


def _abgabe_einlegen(umgebung, vorgang_id="v-1", kennung=KENNUNG):
    """Abgabe läuft: Marke ist noch der Vorzustand (alter Master = Claude), Auftrag liegt bereit."""
    umgebung.vorbereiten(vorgang_id, ziel="hermes", von="claude")
    av.abgabe_beginnen(vorgang_id)
    postfach.einlegen("claude", kennung, vorgang_id, THEMA, "abgabe_auftrag", LAUFEND)


def _dateien(kennung=KENNUNG):
    ordner = postfach.ordner("claude", kennung)
    return sorted(p.name for p in ordner.glob("*.json")) if ordner.is_dir() else []


def _kontext(ausgabe: str, ereignis: str) -> str:
    daten = json.loads(ausgabe)
    assert set(daten) == {"hookSpecificOutput"}
    assert set(daten["hookSpecificOutput"]) == {"hookEventName", "additionalContext"}
    assert daten["hookSpecificOutput"]["hookEventName"] == ereignis
    return daten["hookSpecificOutput"]["additionalContext"]


# --- Empfang ---------------------------------------------------------------------------

@pytest.mark.parametrize("ereignis", ["UserPromptSubmit", "PostToolUse"])
def test_liegende_neu_nachricht_wird_als_zusatzkontext_zugestellt(umgebung, capsys, ereignis):
    _neu_einlegen(umgebung)

    rueckgabe, ausgabe = _lauf(capsys, _ereignis(ereignis))

    assert rueckgabe == 0
    kontext = _kontext(ausgabe, ereignis)
    zeilen = kontext.split("\n")
    assert zeilen[0] == claude_hook.EINLEITUNG == "Nachricht des Master-Schalters:"
    assert zeilen[1:] == [postfach.text("neu", THEMA, LAUFEND, "v-1")]
    assert _dateien() == []                                                   # Postfach leer
    assert (postfach.ordner("claude", KENNUNG) / "erledigt" / "v-1_neu.json").exists()
    assert av.finden("v-1").phase == "im_chat"                                # Abholung, noch keine Übernahme
    assert "decision" not in ausgabe


@pytest.mark.parametrize("ereignis", ["UserPromptSubmit", "PostToolUse"])
def test_zweiter_lauf_gibt_nichts_mehr_aus(umgebung, capsys, ereignis):
    _neu_einlegen(umgebung)
    _lauf(capsys, _ereignis(ereignis))

    assert _lauf(capsys, _ereignis(ereignis)) == (0, "")


@pytest.mark.parametrize("ereignis", ["UserPromptSubmit", "PostToolUse"])
def test_ohne_nachricht_gibt_es_keine_ausgabe(umgebung, capsys, ereignis):
    assert _lauf(capsys, _ereignis(ereignis)) == (0, "")                      # Postfachordner fehlt (schneller Pfad)
    assert not (umgebung.daten / "postfach").exists()                         # der Hook legt kein Postfach an

    postfach.ordner("claude", KENNUNG).mkdir(parents=True)                    # Ordner da, aber leer
    assert _lauf(capsys, _ereignis(ereignis)) == (0, "")


def test_nachricht_einer_anderen_sitzung_wird_nicht_abgeholt(umgebung, capsys):
    _neu_einlegen(umgebung, kennung="andere-sitzung")

    assert _lauf(capsys, _ereignis()) == (0, "")
    assert _dateien("andere-sitzung") == ["v-1_neu.json"]


def test_abgabe_auftrag_wird_zugestellt_und_die_phase_bleibt(umgebung, capsys):
    _abgabe_einlegen(umgebung)

    _, ausgabe = _lauf(capsys, _ereignis("PostToolUse"))

    kontext = _kontext(ausgabe, "PostToolUse")
    assert kontext.split("\n")[1:] == [postfach.text("abgabe_auftrag", THEMA, LAUFEND, "v-1")]
    assert "masterwechsel quittieren v-1 abgabe" in kontext
    vorgang = av.finden("v-1")
    assert vorgang.phase == "abgabe_sende" and vorgang.abgabe_zugestellt is not None
    assert _dateien() == []


def test_abgabe_info_kommt_erst_nach_dem_rollenwechsel(umgebung, capsys):
    _abgabe_einlegen(umgebung)
    av.abgabe_ueberspringen("v-1", "Frist abgelaufen")
    postfach.info_statt_auftrag("claude", KENNUNG, "v-1", THEMA, LAUFEND)

    assert _lauf(capsys, _ereignis()) == (0, "")                              # alter Master führt noch
    assert _dateien() == ["v-1_abgabe_info.json"]

    umgebung.uebergeben("v-1", "hermes")                                       # Rolle gewechselt (G8a)
    _, ausgabe = _lauf(capsys, _ereignis())

    kontext = _kontext(ausgabe, "UserPromptSubmit")
    assert kontext.split("\n")[1:] == [postfach.text("abgabe_info", THEMA, LAUFEND, "v-1")]
    assert _dateien() == []
    assert av.finden("v-1").phase == "abgabe_uebersprungen"


def test_mehrere_nachrichten_stehen_je_zeile_eine(umgebung, capsys, monkeypatch):
    nachrichten = [postfach.Nachricht("v-1", THEMA, "neu", LAUFEND, "erste Zeile"),
                   postfach.Nachricht("v-2", THEMA, "abgabe_info", LAUFEND, "zweite Zeile")]
    vorgemerkt = [postfach.Vorgemerkt(n, Path("nicht-vorhanden.json"), None, {}) for n in nachrichten]
    postfach.ordner("claude", KENNUNG).mkdir(parents=True)
    monkeypatch.setattr(postfach, "vormerken", lambda *args, **kwargs: vorgemerkt)
    monkeypatch.setattr(postfach, "bestaetigen", lambda *args, **kwargs: [])

    _, ausgabe = _lauf(capsys, _ereignis())

    assert _kontext(ausgabe, "UserPromptSubmit") == "Nachricht des Master-Schalters:\nerste Zeile\nzweite Zeile"


def test_ausgabe_enthaelt_weder_kennung_noch_absoluten_pfad(umgebung, capsys, tmp_path):
    _neu_einlegen(umgebung)

    _, ausgabe = _lauf(capsys, _ereignis())

    assert ausgabe and ausgabe.isascii()
    assert KENNUNG not in ausgabe
    assert str(tmp_path) not in ausgabe and tmp_path.as_posix() not in ausgabe
    assert str(tmp_path).replace("\\", "\\\\") not in ausgabe
    kontext = json.loads(ausgabe)["hookSpecificOutput"]["additionalContext"]
    assert re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]", kontext) is None          # kein Laufwerkspfad
    assert "\\" not in kontext and LAUFEND in kontext                          # repo-relativ ist erlaubt
    assert not Path(LAUFEND).is_absolute()


# --- Stop und Statusregister --------------------------------------------------------------

def test_stop_setzt_ruht_blockiert_nie_und_liefert_nicht_aus(umgebung, capsys):
    _neu_einlegen(umgebung)

    assert _lauf(capsys, _ereignis("Stop")) == (0, "")

    assert status.lesen("claude", KENNUNG)[0] == "ruht"
    assert _dateien() == ["v-1_neu.json"]                                      # Stop holt nichts ab
    assert av.finden("v-1").phase == "im_postfach"


def test_status_folgt_den_ereignissen(umgebung, capsys):
    assert status.lesen("claude", KENNUNG) is None                            # unbekannt

    _lauf(capsys, _ereignis("UserPromptSubmit"))
    assert status.lesen("claude", KENNUNG)[0] == "arbeitet"

    _lauf(capsys, _ereignis("Stop"))
    assert status.lesen("claude", KENNUNG)[0] == "ruht"

    _lauf(capsys, _ereignis("PostToolUse"))                                    # Zustandswechsel: sofort, ohne Drossel
    assert status.lesen("claude", KENNUNG)[0] == "arbeitet"


def test_statusdatei_hat_nur_die_vorgesehenen_felder(umgebung, capsys):
    _lauf(capsys, _ereignis("PostToolUse"))

    pfad = umgebung.daten / "status" / f"claude-{KENNUNG}.json"
    inhalt = json.loads(pfad.read_text("utf-8"))
    assert set(inhalt) == {"zustand", "zeit", "ereignis"}
    assert (inhalt["zustand"], inhalt["ereignis"]) == ("arbeitet", "PostToolUse")
    assert datetime.fromisoformat(inhalt["zeit"]).tzinfo is not None
    assert [p.name for p in pfad.parent.iterdir()] == [pfad.name]               # keine tmp-Reste


def test_arbeitet_wird_auf_eine_schreibung_je_minute_gedrosselt(umgebung):
    assert claude_hook.verarbeiten(_ereignis("PostToolUse"), T0) is None
    pfad = status.datei("claude", KENNUNG)
    erster = pfad.read_text("utf-8")

    claude_hook.verarbeiten(_ereignis("PostToolUse"), T0 + timedelta(seconds=30))
    assert pfad.read_text("utf-8") == erster                                   # unter 60 s: nicht neu geschrieben

    claude_hook.verarbeiten(_ereignis("PostToolUse"), T0 + timedelta(seconds=60))
    zweiter = pfad.read_text("utf-8")
    assert zweiter != erster
    assert status.lesen("claude", KENNUNG) == ("arbeitet", T0 + timedelta(seconds=60))

    claude_hook.verarbeiten(_ereignis("Stop"), T0 + timedelta(seconds=61))     # ruht: immer sofort
    assert status.lesen("claude", KENNUNG) == ("ruht", T0 + timedelta(seconds=61))
    claude_hook.verarbeiten(_ereignis("UserPromptSubmit"), T0 + timedelta(seconds=62))
    assert status.lesen("claude", KENNUNG) == ("arbeitet", T0 + timedelta(seconds=62))


def test_schreiben_meldet_ob_gedrosselt_wurde(umgebung):
    assert status.schreiben("claude", KENNUNG, "arbeitet", "PostToolUse", T0) is True
    assert status.schreiben("claude", KENNUNG, "arbeitet", "PostToolUse", T0 + timedelta(seconds=59)) is False
    assert status.schreiben("claude", KENNUNG, "arbeitet", "PostToolUse", T0 + timedelta(seconds=60)) is True


def test_zeit_in_der_zukunft_wird_nicht_als_frisch_gedrosselt(umgebung):
    status.schreiben("claude", KENNUNG, "arbeitet", "PostToolUse", T0 + timedelta(hours=1))

    assert status.schreiben("claude", KENNUNG, "arbeitet", "PostToolUse", T0) is True


def test_lesen_ist_unbekannt_bei_fehlender_oder_kaputter_datei(umgebung):
    pfad = status.datei("claude", KENNUNG)
    assert status.lesen("claude", KENNUNG) is None

    pfad.parent.mkdir(parents=True)
    for kaputt in ("{halb", "[]", '{"zustand": "schlaeft", "zeit": "2026-10-23T12:00:00+00:00"}',
                   '{"zustand": "ruht"}', '{"zustand": "ruht", "zeit": "gestern"}', "x" * 2000):
        pfad.write_text(kaputt, encoding="utf-8")
        assert status.lesen("claude", KENNUNG) is None, kaputt


@pytest.mark.parametrize("werkzeug, kennung", [("claude", "../x"), ("claude", ""), ("claude", "a/b"),
                                               ("claude", None), ("..", KENNUNG), ("grok", KENNUNG)])
def test_unzulaessige_angaben_werden_vom_statusregister_abgelehnt(umgebung, werkzeug, kennung):
    with pytest.raises(status.StatusFehler):
        status.schreiben(werkzeug, kennung, "arbeitet", "PostToolUse", T0)
    assert status.lesen(werkzeug, kennung) is None
    assert not (umgebung.daten / "status").exists()


@pytest.mark.parametrize("stand, ereignis", [("schlaeft", "Stop"), ("ruht", "../Stop"), ("ruht", ""),
                                             ("ruht", "S" * 41), ("ruht", None)])
def test_unzulaessiger_zustand_oder_ereignisname_wird_abgelehnt(umgebung, stand, ereignis):
    with pytest.raises(status.StatusFehler):
        status.schreiben("claude", KENNUNG, stand, ereignis, T0)


# --- Robustheit (K3) ---------------------------------------------------------------------------

GROSS = json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": KENNUNG,
                    "fuell": "x" * claude_hook.MAX_EINGABE}).encode("utf-8")


@pytest.mark.parametrize("eingabe", [
    b"", b"{kaputt", b"[]", b'"text"', b"null", b"\xff\xfe\x00", GROSS,
    json.dumps({"hook_event_name": "UserPromptSubmit"}).encode(),                       # session_id fehlt
    json.dumps({"session_id": KENNUNG}).encode(),                                       # Ereignis fehlt
    _ereignis(kennung="../x"), _ereignis(kennung="..\\..\\x"), _ereignis(kennung="a/b"),
    _ereignis(kennung=""), _ereignis(kennung=None), _ereignis(kennung=123), _ereignis(kennung=["a"]),
    _ereignis(kennung="a" * 81), _ereignis(kennung="x\n"), _ereignis("SessionStart"), _ereignis("Stop", "../x"),
    json.dumps({"hook_event_name": ["Stop"], "session_id": KENNUNG}).encode(),
], ids=lambda e: repr(e)[:40])
def test_ungueltige_eingabe_ergibt_exit_0_ohne_ausgabe_und_ohne_seiteneffekt(umgebung, capsys, eingabe):
    assert _lauf(capsys, eingabe) == (0, "")
    assert not (umgebung.daten / "status").exists()
    assert not (umgebung.daten / "postfach").exists()


def test_stdin_wird_aus_dem_prozess_gelesen_und_begrenzt(umgebung, capsys, monkeypatch):
    _neu_einlegen(umgebung)
    gelesen: list[int] = []

    class Puffer(io.BytesIO):
        def read(self, groesse=-1):
            gelesen.append(groesse)
            return super().read(groesse)

    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(Puffer(_ereignis())))

    assert claude_hook.main() == 0

    assert gelesen == [claude_hook.MAX_EINGABE + 1]
    assert _kontext(capsys.readouterr().out, "UserPromptSubmit")


def test_geschlossenes_stdin_ergibt_exit_0(umgebung, capsys, monkeypatch):
    monkeypatch.setattr(sys, "stdin", None)

    assert claude_hook.main() == 0
    assert capsys.readouterr() == ("", "")


def test_belegte_themensperre_laesst_die_nachricht_liegen(umgebung, capsys, monkeypatch):
    _neu_einlegen(umgebung)
    monkeypatch.setattr(av, "THEMENSPERRE_FRIST", 0.05)

    with zustand.thema_sperre(THEMA, blockierend=True, frist=1.0) as frei:
        assert frei
        assert _lauf(capsys, _ereignis()) == (0, "")

    assert _dateien() == ["v-1_neu.json"]
    assert av.finden("v-1").phase == "im_postfach"
    _, ausgabe = _lauf(capsys, _ereignis())                                     # danach klappt es
    assert _kontext(ausgabe, "UserPromptSubmit")


@pytest.mark.parametrize("ort", ["vormerken", "ordner"])
def test_oserror_im_postfach_ergibt_exit_0_ohne_ausgabe(umgebung, capsys, monkeypatch, ort):
    _neu_einlegen(umgebung)

    def kaputt(*args, **kwargs):
        raise OSError("synthetischer Fehler mit Pfad C:\\geheim")

    monkeypatch.setattr(postfach, ort, kaputt)

    assert _lauf(capsys, _ereignis()) == (0, "")


def test_beliebige_ausnahme_im_postfach_wird_geschluckt(umgebung, capsys, monkeypatch):
    postfach.ordner("claude", KENNUNG).mkdir(parents=True)

    def kaputt(*args, **kwargs):
        raise RuntimeError("Traceback-Kandidat")

    monkeypatch.setattr(postfach, "vormerken", kaputt)

    assert _lauf(capsys, _ereignis()) == (0, "")


def test_statusfehler_verhindert_die_zustellung_nicht(umgebung, capsys, monkeypatch):
    _neu_einlegen(umgebung)

    def kaputt(*args, **kwargs):
        raise OSError("Platte voll")

    monkeypatch.setattr(status, "_atomar_schreiben", kaputt)

    _, ausgabe = _lauf(capsys, _ereignis())

    assert _kontext(ausgabe, "UserPromptSubmit")
    assert status.lesen("claude", KENNUNG) is None


def test_statusfehler_bei_stop_ergibt_exit_0(umgebung, capsys, monkeypatch):
    def kaputt(*args, **kwargs):
        raise OSError("Platte voll")

    monkeypatch.setattr(status, "_atomar_schreiben", kaputt)

    assert _lauf(capsys, _ereignis("Stop")) == (0, "")


# --- Echter Prozess ---------------------------------------------------------------------------------

def _prozess(eingabe: bytes) -> tuple[subprocess.CompletedProcess[bytes], float]:
    umgebung = dict(os.environ)
    src = Path(__file__).resolve().parents[1] / "src"
    umgebung["PYTHONPATH"] = str(src)
    start = time.perf_counter()
    lauf = subprocess.run([sys.executable, "-m", "master_schalter.claude_hook"], input=eingabe,
                          capture_output=True, env=umgebung, timeout=30)
    return lauf, time.perf_counter() - start


def test_aufruf_als_modul_im_eigenen_prozess(umgebung, tmp_path):
    _neu_einlegen(umgebung)

    lauf, dauer = _prozess(_ereignis("PostToolUse"))

    assert lauf.returncode == 0 and lauf.stderr == b""
    assert _kontext(lauf.stdout.decode("ascii"), "PostToolUse").startswith(claude_hook.EINLEITUNG)
    assert KENNUNG.encode() not in lauf.stdout and str(tmp_path).encode() not in lauf.stdout
    assert av.finden("v-1").phase == "im_chat"
    assert status.lesen("claude", KENNUNG)[0] == "arbeitet"
    assert dauer < 10                                                           # Ziel < 2 s; hier großzügig gegen Last

    lauf, _ = _prozess(_ereignis("PostToolUse"))                                # nichts mehr zuzustellen
    assert (lauf.returncode, lauf.stdout, lauf.stderr) == (0, b"", b"")

    lauf, _ = _prozess(_ereignis("Stop"))
    assert (lauf.returncode, lauf.stdout, lauf.stderr) == (0, b"", b"")
    assert status.lesen("claude", KENNUNG)[0] == "ruht"


@pytest.mark.parametrize("eingabe", [b"", b"{kaputt", _ereignis(kennung="../x")])
def test_aufruf_als_modul_mit_ungueltiger_eingabe_ergibt_exit_0(umgebung, eingabe):
    lauf, _ = _prozess(eingabe)

    assert (lauf.returncode, lauf.stdout, lauf.stderr) == (0, b"", b"")
    assert not (umgebung.daten / "status").exists()


# --- Ausgabe vor Zustellung (vormerken / bestaetigen) ----------------------------------------------

def _zwei_nachrichten(umgebung):
    """`v-1_neu` (Marke trägt v-1) und `v-2_abgabe_auftrag` (Vorzustand = Marke von v-1) liegen für dieselbe Sitzung."""
    _neu_einlegen(umgebung, "v-1")
    umgebung.vorbereiten("v-2", ziel="hermes", von="claude")
    av.abgabe_beginnen("v-2")
    postfach.einlegen("claude", KENNUNG, "v-2", THEMA, "abgabe_auftrag", LAUFEND)
    assert _dateien() == ["v-1_neu.json", "v-2_abgabe_auftrag.json"]


def test_scheitert_die_ausgabe_bleibt_die_nachricht_liegen_und_kommt_erneut(umgebung, capsys):
    _neu_einlegen(umgebung)

    def kaputt(text):
        raise OSError("stdout geschlossen")

    claude_hook.verarbeiten(_ereignis(), ausgabe=kaputt)

    assert _dateien() == ["v-1_neu.json"]
    assert not (postfach.ordner("claude", KENNUNG) / "erledigt").exists()
    assert av.finden("v-1").phase == "im_postfach"                             # nicht im_chat
    _, ausgabe = _lauf(capsys, _ereignis())                                     # der nächste Aufruf liefert sie
    assert _kontext(ausgabe, "UserPromptSubmit")
    assert av.finden("v-1").phase == "im_chat" and _dateien() == []


def test_scheitert_stdout_beim_flush_bleibt_die_nachricht_liegen(umgebung, monkeypatch):
    _neu_einlegen(umgebung)

    class Kaputt:
        def write(self, text):
            return len(text)

        def flush(self):
            raise OSError("Pipe geschlossen")

    monkeypatch.setattr(sys, "stdout", Kaputt())

    assert claude_hook.main(_ereignis()) == 0

    assert _dateien() == ["v-1_neu.json"] and av.finden("v-1").phase == "im_postfach"


def test_zugestellt_wird_erst_nach_der_ausgabe(umgebung):
    _neu_einlegen(umgebung)
    ausgegeben: list[str] = []

    def beobachten(text):
        assert _dateien() == ["v-1_neu.json"]                                   # beim Ausgeben noch nichts verschoben
        assert av.finden("v-1").phase == "im_postfach"
        ausgegeben.append(text)

    claude_hook.verarbeiten(_ereignis(), ausgabe=beobachten)

    assert len(ausgegeben) == 1
    assert _dateien() == []
    assert (postfach.ordner("claude", KENNUNG) / "erledigt" / "v-1_neu.json").exists()
    assert av.finden("v-1").phase == "im_chat"


def test_fehler_beim_bestaetigen_ergibt_exit_0_und_die_ausgabe_steht(umgebung, capsys, monkeypatch):
    _neu_einlegen(umgebung)

    def kaputt(*args, **kwargs):
        raise OSError("Platte voll")

    monkeypatch.setattr(postfach, "bestaetigen", kaputt)

    rueckgabe, ausgabe = _lauf(capsys, _ereignis())

    assert rueckgabe == 0 and _kontext(ausgabe, "UserPromptSubmit")
    assert _dateien() == ["v-1_neu.json"]                                       # kommt beim nächsten Mal erneut


def test_vormerken_verschiebt_nichts_und_bestaetigen_stellt_zu(umgebung):
    _neu_einlegen(umgebung)

    vorgemerkt = postfach.vormerken("claude", KENNUNG, umgebung.repo)

    assert [v.nachricht.vorgang for v in vorgemerkt] == ["v-1"]
    assert _dateien() == ["v-1_neu.json"] and av.finden("v-1").phase == "im_postfach"
    erledigt = postfach.bestaetigen(vorgemerkt)
    assert erledigt == [vorgemerkt[0].nachricht]
    assert _dateien() == [] and av.finden("v-1").phase == "im_chat"
    assert postfach.bestaetigen(vorgemerkt) == []                               # Datei fehlt: übergangen


def test_bestaetigen_uebergeht_geaenderte_oder_fehlende_dateien(umgebung):
    _neu_einlegen(umgebung)
    vorgemerkt = postfach.vormerken("claude", KENNUNG, umgebung.repo)
    datei = vorgemerkt[0].datei
    inhalt = json.loads(datei.read_text("utf-8"))
    inhalt["zeit"] = "2026-10-23T13:00:00+00:00"
    datei.write_text(json.dumps(inhalt), encoding="utf-8")                      # Datei wurde ersetzt

    assert postfach.bestaetigen(vorgemerkt) == []

    assert _dateien() == ["v-1_neu.json"] and av.finden("v-1").phase == "im_postfach"
    datei.unlink()
    assert postfach.bestaetigen(vorgemerkt) == []


def test_abholen_bleibt_vormerken_plus_bestaetigen(umgebung):
    _neu_einlegen(umgebung)

    erg = postfach.abholen("claude", KENNUNG, umgebung.repo)

    assert [n.vorgang for n in erg] == ["v-1"] and av.finden("v-1").phase == "im_chat"


# --- Importfehler ----------------------------------------------------------------------------------

def test_claude_hook_importiert_auf_modulebene_nur_die_standardbibliothek():
    quelle = Path(claude_hook.__file__).read_text("utf-8")
    kopf = quelle.split("MAX_EINGABE", 1)[0]
    assert re.findall(r"^(?:from|import) .*$", kopf, flags=re.M) == [
        "from __future__ import annotations", "import json", "import os", "import sys", "import time",
        "from datetime import datetime", "from typing import Callable"]


@pytest.mark.parametrize("name", ["modi", "status", "postfach"])
@pytest.mark.parametrize("ereignis", ["UserPromptSubmit", "PostToolUse", "Stop"])
def test_importfehler_wird_geschluckt(umgebung, capsys, monkeypatch, name, ereignis):
    import master_schalter

    _neu_einlegen(umgebung)
    monkeypatch.delattr(master_schalter, name, raising=False)                 # sonst umgeht `from . import` sys.modules
    monkeypatch.setitem(sys.modules, f"master_schalter.{name}", None)         # Import scheitert mit ImportError

    rueckgabe, ausgabe = _lauf(capsys, _ereignis(ereignis))

    assert rueckgabe == 0
    if name == "status" and ereignis != "Stop":
        # Das Statusregister ist nicht nötig für die Zustellung: ohne es wird trotzdem ausgeliefert.
        assert _kontext(ausgabe, ereignis) and _dateien() == []
    else:
        assert ausgabe == "" and _dateien() == ["v-1_neu.json"]                # nichts zugestellt


# --- Laufzeit-Obergrenze ---------------------------------------------------------------------------

def test_belegte_globale_sperre_haelt_den_hook_nicht_auf(umgebung, capsys):
    _neu_einlegen(umgebung)

    with zustand.sperre(5.0):
        start = time.perf_counter()
        rueckgabe, _ = _lauf(capsys, _ereignis())
        dauer = time.perf_counter() - start

    assert rueckgabe == 0
    assert dauer < 1.5                                                          # Frist 0,3 s, großzügig toleriert
    assert _dateien() == ["v-1_neu.json"] and av.finden("v-1").phase == "im_postfach"
    _, ausgabe = _lauf(capsys, _ereignis())                                     # Sperre frei: kommt (erneut) an
    assert _kontext(ausgabe, "UserPromptSubmit") and av.finden("v-1").phase == "im_chat"


def test_belegte_globale_sperre_im_eigenen_prozess(umgebung):
    _neu_einlegen(umgebung)

    with zustand.sperre(10.0):
        lauf, dauer = _prozess(_ereignis())

    assert lauf.returncode == 0 and lauf.stderr == b""
    assert dauer < 5                                                            # Ziel < 2 s; großzügig gegen Last
    assert _dateien() == ["v-1_neu.json"]


def test_abholen_mit_kurzer_frist_laesst_bei_belegten_sperren_alles_liegen(umgebung):
    _neu_einlegen(umgebung)

    with zustand.sperre(5.0):
        start = time.perf_counter()
        assert postfach.abholen("claude", KENNUNG, umgebung.repo, frist=0.1) == []
        assert time.perf_counter() - start < 1.5
    assert _dateien() == ["v-1_neu.json"]

    with zustand.thema_sperre(THEMA, blockierend=True, frist=1.0) as frei:
        assert frei
        assert postfach.vormerken("claude", KENNUNG, umgebung.repo, frist=0.05) == []
    assert _dateien() == ["v-1_neu.json"]


def _nach_der_ersten_datei_abgelaufen(monkeypatch, folge=(False, True)):
    """`_abgelaufen` antwortet der Reihe nach mit `folge` (danach immer: Budget erreicht)."""
    aufrufe: list[int] = []

    def abgelaufen(bis):
        aufrufe.append(1)
        return folge[len(aufrufe) - 1] if len(aufrufe) <= len(folge) else True

    monkeypatch.setattr(postfach, "_abgelaufen", abgelaufen)


def test_budget_im_vormerken_laesst_die_restlichen_dateien_liegen(umgebung, monkeypatch):
    _zwei_nachrichten(umgebung)
    _nach_der_ersten_datei_abgelaufen(monkeypatch)

    vorgemerkt = postfach.vormerken("claude", KENNUNG, umgebung.repo, bis=time.monotonic() + 100)

    assert [v.nachricht.vorgang for v in vorgemerkt] == ["v-1"]
    assert _dateien() == ["v-1_neu.json", "v-2_abgabe_auftrag.json"]
    assert av.finden("v-2").abgabe_zugestellt is None


def test_abgelaufenes_budget_fasst_nichts_an(umgebung):
    _zwei_nachrichten(umgebung)

    assert postfach.abholen("claude", KENNUNG, umgebung.repo, bis=time.monotonic() - 1) == []

    assert _dateien() == ["v-1_neu.json", "v-2_abgabe_auftrag.json"]
    assert not (postfach.ordner("claude", KENNUNG) / "verworfen").exists()


def test_budget_im_bestaetigen_laesst_die_restlichen_dateien_liegen(umgebung, monkeypatch):
    _zwei_nachrichten(umgebung)
    vorgemerkt = postfach.vormerken("claude", KENNUNG, umgebung.repo)
    assert len(vorgemerkt) == 2
    _nach_der_ersten_datei_abgelaufen(monkeypatch)

    erledigt = postfach.bestaetigen(vorgemerkt, bis=time.monotonic() + 100)

    assert [n.vorgang for n in erledigt] == ["v-1"]
    assert _dateien() == ["v-2_abgabe_auftrag.json"]
    assert av.finden("v-2").abgabe_zugestellt is None


def test_budget_im_hook_stellt_den_rest_beim_naechsten_ereignis_zu(umgebung, capsys, monkeypatch):
    _zwei_nachrichten(umgebung)
    with monkeypatch.context() as m:
        _nach_der_ersten_datei_abgelaufen(m, (False, True, False))
        _, ausgabe = _lauf(capsys, _ereignis())
    assert _kontext(ausgabe, "UserPromptSubmit").split("\n")[1:] == [postfach.text("neu", THEMA, LAUFEND, "v-1")]
    assert _dateien() == ["v-2_abgabe_auftrag.json"]

    _, ausgabe = _lauf(capsys, _ereignis("PostToolUse"))

    assert "masterwechsel quittieren v-2 abgabe" in _kontext(ausgabe, "PostToolUse")
    assert _dateien() == []


# --- G5 zwischen Vormerken und Bestätigen -------------------------------------------------------------

def _grund(name="v-1_neu.json"):
    return json.loads((postfach.ordner("claude", KENNUNG) / "verworfen" / name).read_text("utf-8"))["grund"]


def test_markenwechsel_zwischen_vormerken_und_bestaetigen_verwirft_die_nachricht(umgebung):
    _neu_einlegen(umgebung)
    vorgemerkt = postfach.vormerken("claude", KENNUNG, umgebung.repo)
    assert len(vorgemerkt) == 1
    modi.master_setzen(THEMA, "codex", repo=umgebung.repo)                    # Master wechselt dazwischen

    assert postfach.bestaetigen(vorgemerkt) == []

    assert _dateien() == []
    assert _grund()
    assert av.finden("v-1").phase == "im_postfach"                            # nicht im_chat
    assert not (postfach.ordner("claude", KENNUNG) / "erledigt").exists()


def test_markenwechsel_nach_der_ausgabe_setzt_den_vorgang_nicht_auf_im_chat(umgebung):
    _neu_einlegen(umgebung)
    ausgegeben: list[str] = []

    def ausgeben_und_wechseln(text):
        ausgegeben.append(text)
        modi.master_setzen(THEMA, "codex", repo=umgebung.repo)                # ungültig nach der Ausgabe

    claude_hook.verarbeiten(_ereignis(), ausgabe=ausgeben_und_wechseln)

    assert len(ausgegeben) == 1                                                # sie steht im Chat ...
    assert "beginne keinen Schritt" in ausgegeben[0]                           # ... mit dem Hinweis auf die Quittung
    assert _dateien() == [] and _grund()
    assert av.finden("v-1").phase == "im_postfach"                            # ... zählt aber nicht als abgeholt


def test_bestaetigen_laesst_die_datei_liegen_wenn_die_rolle_noch_nicht_gesetzt_ist(umgebung):
    _neu_einlegen(umgebung)
    vorgemerkt = postfach.vormerken("claude", KENNUNG, umgebung.repo)
    av.aktualisieren("v-1", phase="abgabe_sende")                              # Zustand zurückgesetzt: Rolle nicht gesetzt

    assert postfach.bestaetigen(vorgemerkt) == []

    assert _dateien() == ["v-1_neu.json"] and av.finden("v-1").phase == "abgabe_sende"


# --- Prozessende bei nicht beschreibbarem stdout ---------------------------------------------------------

def _prozess_mit_stdout(eingabe: bytes, stdout) -> subprocess.CompletedProcess[bytes]:
    umgebung = dict(os.environ)
    umgebung["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    return subprocess.run([sys.executable, "-m", "master_schalter.claude_hook"], input=eingabe,
                          stdout=stdout, stderr=subprocess.PIPE, env=umgebung, timeout=30)


def test_prozess_mit_schreibgeschuetztem_stdout_endet_mit_0_ohne_stderr(umgebung, tmp_path):
    _neu_einlegen(umgebung)
    leer = tmp_path / "nur-lesen.txt"
    leer.write_bytes(b"")

    with open(leer, "rb") as nur_lesen:
        lauf = _prozess_mit_stdout(_ereignis(), nur_lesen)

    assert lauf.returncode == 0 and lauf.stderr == b""
    assert _dateien() == ["v-1_neu.json"] and av.finden("v-1").phase == "im_postfach"   # nichts verloren


def test_prozess_mit_geschlossener_pipe_endet_mit_0_ohne_stderr(umgebung):
    _neu_einlegen(umgebung)
    lese, schreibe = os.pipe()
    os.close(lese)                                                              # Leseende zu: Schreiben scheitert
    try:
        lauf = _prozess_mit_stdout(_ereignis(), schreibe)
    finally:
        os.close(schreibe)

    assert lauf.returncode == 0 and lauf.stderr == b""
    assert _dateien() == ["v-1_neu.json"] and av.finden("v-1").phase == "im_postfach"
