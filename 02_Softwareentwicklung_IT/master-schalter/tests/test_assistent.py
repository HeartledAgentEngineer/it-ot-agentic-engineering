"""Tests für den Ablauf des Wechselassistenten (`assistent.py`): übergeben, fortsetzen, Zustellung.

Alles mit Attrappen-Transport und `tmp_path`: `codex.exe` wird nie gestartet, es werden keine echten Chats,
Kennungen oder Titel gelesen. Die auffälligen Kennungen `K_ALT`/`K_NEU` dienen dem Nachweis, dass sie nie
in Nachrichtentexten oder im Protokoll auftauchen.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from master_schalter import assistent, besitz, codex_senden, modi, paare, postfach, protokoll, zustand
from master_schalter import assistent_vorgaenge as av
from master_schalter.assistent import ChatRef

THEMA = "engineering"
K_ALT = "GEHEIM-ALT-4711"
K_NEU = "GEHEIM-NEU-0815"
CODEX_MARKE = besitz.zeile(besitz.CODEX, "20261001T000000Z-abcd1234", "2026-10-01T00:00:00+00:00")


class Attrappe:
    """Transport-Attrappe: merkt sich die Aufrufe, wirft optional, ruft optional vorher einen Haken."""

    def __init__(self, rc: int = 0, fehler: BaseException | None = None, vorher=None) -> None:
        self.rc, self.fehler, self.vorher = rc, fehler, vorher
        self.aufrufe: list[list[str]] = []

    def __call__(self, liste: list[str], timeout: int) -> int:
        self.aufrufe.append(list(liste))
        assert timeout == codex_senden.TIMEOUT_SEKUNDEN
        if self.vorher is not None:
            self.vorher(liste)
        if self.fehler is not None:
            raise self.fehler
        return self.rc

    @property
    def texte(self) -> list[str]:
        return [aufruf[5] for aufruf in self.aufrufe]


@pytest.fixture(autouse=True)
def _codex_attrappe(tmp_path, monkeypatch):
    """`programm()` findet nur diese Attrappe; ein echtes `codex.exe` wird nie gesucht oder gestartet."""
    monkeypatch.setenv("MASTER_SCHALTER_CODEX", str(tmp_path / "codex-attrappe.exe"))


def _uebergeben(umgebung, ziel, von=None, nach=None, transport=None, **extra):
    if von is not None and von.werkzeug == "codex" and not umgebung.marke():
        umgebung.marke_setzen(CODEX_MARKE)                        # der alte Master ist dann auch wirklich Codex
    return assistent.uebergeben(THEMA, ziel, von_chat=von, nach_chat=nach, repo=umgebung.repo,
                                transport=transport, **extra)


def _fortsetzen(umgebung, vorgang_id, transport=None, **extra):
    return assistent.fortsetzen(vorgang_id, repo=umgebung.repo, transport=transport, **extra)


def _marke_von(umgebung, vorgang_id, rolle):
    marke = besitz.assistent_marke(umgebung.marke())
    assert marke == (rolle, THEMA, vorgang_id)


def _alle_postfachtexte() -> str:
    return "".join(d.read_text(encoding="utf-8") for d in postfach.wurzel().rglob("*.json")) \
        if postfach.wurzel().exists() else ""


# --- Glücksfälle ----------------------------------------------------------------------------------

def test_gluecksfall_codex_zu_claude(umgebung):
    umgebung.marke_setzen(CODEX_MARKE)
    t = Attrappe()

    v = _uebergeben(umgebung, "claude", ChatRef("codex", K_ALT), ChatRef("claude", K_NEU), t)

    assert v.phase == "abgabe_angefragt" and v.von == "codex" and v.vorzustand_marke == CODEX_MARKE
    assert len(t.aufrufe) == 1
    programm, queue, thread_arg, kennung, nachricht_arg, text = t.aufrufe[0]
    assert (queue, thread_arg, kennung, nachricht_arg) == ("queue", "--thread", K_ALT, "--message")
    assert text == postfach.text("abgabe_auftrag", THEMA, paare.laufend_bilden(THEMA), v.id)
    assert umgebung.marke() == CODEX_MARKE                       # während der Abgabe gehört die Marke dem alten Master

    av.quittieren(v.id, "abgabe", umgebung.repo)                  # der alte Codex-Chat gibt ab
    v = _fortsetzen(umgebung, v.id, t)

    assert v.phase == "im_postfach" and v.abgabe == "abgegeben"
    _marke_von(umgebung, v.id, "claude")
    assert modi.profil(THEMA).master == "claude"
    assert len(t.aufrufe) == 1                                    # an Claude geht es über das Postfach
    nachrichten = postfach.abholen("claude", K_NEU, umgebung.repo)
    assert [(n.vorgang, n.rolle) for n in nachrichten] == [(v.id, "neu")]
    assert postfach.ZUSATZ_ABGABE_FEHLTE not in nachrichten[0].text
    assert av.finden(v.id).phase == "im_chat"
    assert av.quittieren(v.id, "neu", umgebung.repo).phase == "bestaetigt"


def test_gluecksfall_claude_zu_codex(umgebung):
    t = Attrappe()

    v = _uebergeben(umgebung, "codex", ChatRef("claude", K_ALT), ChatRef("codex", K_NEU), t)

    assert v.phase == "abgabe_angefragt" and v.von == "claude"
    assert t.aufrufe == []                                        # an Claude geht der Auftrag über das Postfach
    gelegt = [n for n in postfach.abholen("claude", K_ALT, umgebung.repo)]
    assert [(n.vorgang, n.rolle) for n in gelegt] == [(v.id, "abgabe_auftrag")]

    av.quittieren(v.id, "abgabe", umgebung.repo)
    v = _fortsetzen(umgebung, v.id, t)

    assert v.phase == "gesendet"
    _marke_von(umgebung, v.id, "codex")
    assert len(t.aufrufe) == 1 and t.aufrufe[0][1:4] == ["queue", "--thread", K_NEU]
    assert t.texte == [postfach.text("neu", THEMA, paare.laufend_bilden(THEMA), v.id)]
    assert av.quittieren(v.id, "neu", umgebung.repo).phase == "bestaetigt"


def test_gleiche_rolle_claude_zu_anderem_claude_chat(umgebung):
    t = Attrappe()
    v = _uebergeben(umgebung, "claude", ChatRef("claude", K_ALT), ChatRef("claude", K_NEU), t)
    av.quittieren(v.id, "abgabe", umgebung.repo)

    v = _fortsetzen(umgebung, v.id, t)

    assert v.phase == "im_postfach"
    _marke_von(umgebung, v.id, "claude")
    assert (postfach.ordner("claude", K_NEU) / f"{v.id}_neu.json").is_file()


def test_zwei_von_vier_themen_wechseln_die_anderen_bleiben_bytegleich(umgebung):
    andere = ["thema-b", "thema-c", "thema-d"]
    for nr, thema in enumerate(andere):
        paare.setzen(thema, f"00000000-0000-4000-8000-0000000000b{nr}", paare.laufend_bilden(thema), aktiv=True)
    umgebung.marke_setzen("claude 2026-10-01T00:00:00+00:00 fehlgeschlagen x", "thema-c")
    modi.worker_setzen("thema-d", "codex", repo=umgebung.repo)
    vorher = {t: (umgebung.master_datei(t).read_bytes() if umgebung.master_datei(t).exists() else None,
                  modi.profil(t)) for t in andere}

    erstes = assistent.uebergeben(THEMA, "codex", nach_chat=ChatRef("codex", K_NEU), repo=umgebung.repo,
                                  transport=Attrappe())
    zweites = assistent.uebergeben("thema-b", "hermes", nach_chat=ChatRef("hermes", K_NEU), repo=umgebung.repo)

    assert erstes.phase == "gesendet" and zweites.phase == "im_postfach"
    assert modi.profil(THEMA).master == "codex" and modi.profil("thema-b").master == "hermes"
    for thema in ("thema-c", "thema-d"):
        datei = umgebung.master_datei(thema)
        assert (datei.read_bytes() if datei.exists() else None) == vorher[thema][0]
        assert modi.profil(thema) == vorher[thema][1]


def test_ohne_alten_chat_wird_die_abgabe_sofort_uebersprungen_und_vermerkt(umgebung):
    t = Attrappe()

    v = _uebergeben(umgebung, "codex", None, ChatRef("codex", K_NEU), t)

    assert v.phase == "gesendet" and v.abgabe == "uebersprungen" and v.fehler == "kein alter Chat gewählt"
    _marke_von(umgebung, v.id, "codex")
    assert t.texte == [postfach.text("neu", THEMA, paare.laufend_bilden(THEMA), v.id, True)]
    assert postfach.ZUSATZ_ABGABE_FEHLTE in t.texte[0] and "git status" in t.texte[0]


def test_ohne_alten_chat_vermerk_im_postfachtext_ohne_neues_inhaltsfeld(umgebung):
    v = _uebergeben(umgebung, "hermes", None, ChatRef("hermes", K_NEU))

    assert v.phase == "im_postfach"
    datei = postfach.ordner("hermes", K_NEU) / f"{v.id}_neu.json"
    assert set(json.loads(datei.read_text(encoding="utf-8"))) == postfach.FELDER      # G6: kein neues Feld
    nachrichten = postfach.abholen("hermes", K_NEU, umgebung.repo)
    assert len(nachrichten) == 1 and postfach.ZUSATZ_ABGABE_FEHLTE in nachrichten[0].text


def test_ohne_neuen_chat_bleibt_es_bei_rolle_gesetzt(umgebung):
    t = Attrappe()

    v = _uebergeben(umgebung, "codex", None, None, t)
    nochmal = _fortsetzen(umgebung, v.id, t)

    assert v.phase == nochmal.phase == "rolle_gesetzt" and t.aufrufe == []
    _marke_von(umgebung, v.id, "codex")


# --- Frist und Info -------------------------------------------------------------------------------

def test_frist_vor_ablauf_nichts_nach_ablauf_uebersprungen_mit_vermerk(umgebung):
    t = Attrappe()
    v = _uebergeben(umgebung, "codex", ChatRef("claude", K_ALT), ChatRef("codex", K_NEU), t)
    jetzt = datetime.now(timezone.utc)

    frueh = _fortsetzen(umgebung, v.id, t, jetzt=jetzt + timedelta(minutes=9))
    assert frueh.phase == "abgabe_angefragt" and t.aufrufe == []
    assert not (postfach.ordner("claude", K_ALT) / f"{v.id}_abgabe_info.json").exists()

    spaet = _fortsetzen(umgebung, v.id, t, jetzt=jetzt + timedelta(minutes=11))

    assert spaet.phase == "gesendet" and spaet.abgabe == "uebersprungen" and spaet.fehler == "Frist abgelaufen"
    assert t.texte == [postfach.text("neu", THEMA, paare.laufend_bilden(THEMA), v.id, True)]
    ordner = postfach.ordner("claude", K_ALT)
    assert (ordner / f"{v.id}_abgabe_info.json").is_file()
    assert (ordner / postfach.VERWORFEN / f"{v.id}_abgabe_auftrag.json").is_file()   # Auftrag durch Info ersetzt


def test_frist_info_an_codex_genau_einmal(umgebung):
    t = Attrappe()
    v = _uebergeben(umgebung, "claude", ChatRef("codex", K_ALT), ChatRef("claude", K_NEU), t)
    assert len(t.aufrufe) == 1                                    # der Abgabe-Auftrag
    spaeter = datetime.now(timezone.utc) + timedelta(minutes=11)

    _fortsetzen(umgebung, v.id, t, jetzt=spaeter)
    _fortsetzen(umgebung, v.id, t, jetzt=spaeter + timedelta(minutes=1))
    ende = _fortsetzen(umgebung, v.id, t, jetzt=spaeter + timedelta(minutes=2))

    assert len(t.aufrufe) == 2 and t.aufrufe[1][3] == K_ALT
    assert t.texte[1] == postfach.text("abgabe_info", THEMA, paare.laufend_bilden(THEMA), v.id)
    assert ende.phase == "im_postfach" and ende.abgabe == "uebersprungen"
    nachrichten = postfach.abholen("claude", K_NEU, umgebung.repo)
    assert len(nachrichten) == 1 and postfach.ZUSATZ_ABGABE_FEHLTE in nachrichten[0].text


def test_paralleles_fortsetzen_sendet_info_und_zustellung_genau_einmal(umgebung):
    from concurrent.futures import ThreadPoolExecutor

    t = Attrappe()
    v = _uebergeben(umgebung, "claude", ChatRef("codex", K_ALT), ChatRef("claude", K_NEU), t)
    spaeter = datetime.now(timezone.utc) + timedelta(minutes=11)

    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(_fortsetzen, umgebung, v.id, t, jetzt=spaeter) for _ in range(4)]
        for job in jobs:
            try:
                job.result(timeout=60)
            except assistent.AssistentFehler:
                pass                                              # ein Takt darf an der Themensperre scheitern

    _fortsetzen(umgebung, v.id, t, jetzt=spaeter)
    assert len(t.aufrufe) == 2                                    # Abgabe-Auftrag + genau eine Info
    assert t.texte[1] == postfach.text("abgabe_info", THEMA, paare.laufend_bilden(THEMA), v.id)
    assert av.finden(v.id).phase == "im_postfach"
    assert [p.name for p in postfach.ordner("claude", K_NEU).glob("*.json")] == [f"{v.id}_neu.json"]


def test_frist_info_an_claude_genau_eine_datei_und_fehler_der_info_haelt_nichts_auf(umgebung, monkeypatch):
    t = Attrappe()
    v = _uebergeben(umgebung, "codex", ChatRef("claude", K_ALT), ChatRef("codex", K_NEU), t)

    def kaputt(*args, **kwargs):
        raise OSError("Platte voll")

    monkeypatch.setattr(postfach, "info_statt_auftrag", kaputt)
    ende = _fortsetzen(umgebung, v.id, t, jetzt=datetime.now(timezone.utc) + timedelta(minutes=11))

    assert ende.phase == "gesendet"                               # der Ablauf geht trotz Info-Fehler weiter
    assert [e["entscheidung"] for e in protokoll.lesen() if e["entscheidung"].startswith("info")] == \
        ["info_fehlgeschlagen"]


def test_frist_aus_abgabe_fehler_wird_ebenfalls_uebersprungen(umgebung):
    t = Attrappe(fehler=FileNotFoundError())
    v = _uebergeben(umgebung, "claude", ChatRef("codex", K_ALT), ChatRef("claude", K_NEU), t)
    assert v.phase == "abgabe_fehler"
    assert _fortsetzen(umgebung, v.id, t, jetzt=datetime.now(timezone.utc) + timedelta(minutes=5)).phase == "abgabe_fehler"

    ende = _fortsetzen(umgebung, v.id, t, jetzt=datetime.now(timezone.utc) + timedelta(minutes=11))

    assert ende.phase == "im_postfach" and ende.abgabe == "uebersprungen"


# --- Geänderter Stand -----------------------------------------------------------------------------

def test_marke_zwischen_abgabe_und_rolle_umgestellt_verwirft_ohne_zustellung(umgebung):
    t = Attrappe()
    v = _uebergeben(umgebung, "codex", ChatRef("claude", K_ALT), ChatRef("codex", K_NEU), t)
    av.quittieren(v.id, "abgabe", umgebung.repo)
    fremd = "hermes 2026-10-22T11:00:00+00:00 modus fremd"
    umgebung.marke_setzen(fremd)                                  # jemand hat zwischendurch gewechselt

    ende = _fortsetzen(umgebung, v.id, t)

    assert ende.phase == "verworfen" and ende.fehler == "Stand geändert"
    assert umgebung.marke() == fremd and modi.profil(THEMA).master == "kontingent"
    assert t.aufrufe == []
    assert _fortsetzen(umgebung, v.id, t).phase == "verworfen" and t.aufrufe == []


def test_marke_nach_rollensetzen_von_spaeterem_wechsel_ueberholt_keine_zustellung(umgebung):
    t = Attrappe()
    v = _uebergeben(umgebung, "codex", None, None, t)
    nach_chat = {"werkzeug": "codex", "kennung": K_NEU}
    av.aktualisieren(v.id, nach_chat=nach_chat)
    modi.master_setzen(THEMA, "hermes", repo=umgebung.repo)       # späterer Wechsel überschreibt die Marke

    ende = _fortsetzen(umgebung, v.id, t)

    assert ende.phase == "verworfen" and t.aufrufe == []


# --- Doppelklick und Sperre -----------------------------------------------------------------------

def test_doppelklick_zweites_uebergeben_sendet_nichts_mehr(umgebung):
    t = Attrappe()
    v = _uebergeben(umgebung, "claude", ChatRef("codex", K_ALT), ChatRef("claude", K_NEU), t)

    with pytest.raises(assistent.AssistentFehler, match="Wechsel läuft bereits"):
        _uebergeben(umgebung, "claude", ChatRef("codex", K_ALT), ChatRef("claude", K_NEU), t)

    assert len(t.aufrufe) == 1 and [x.id for x in av.lesen()] == [v.id]


def test_belegte_themensperre_ist_ein_fehler_ohne_nebenwirkung(umgebung):
    t = Attrappe()
    with zustand.thema_sperre(THEMA) as frei:
        assert frei
        with pytest.raises(assistent.AssistentFehler, match="Thema gerade belegt"):
            _uebergeben(umgebung, "codex", ChatRef("claude", K_ALT), ChatRef("codex", K_NEU), t)

    assert av.lesen() == [] and t.aufrufe == [] and not postfach.wurzel().exists()


@pytest.mark.parametrize("phase", sorted(av.WECHSEL_BLOCKIEREND))
def test_blockierende_phasen_lehnen_einen_zweiten_wechsel_ab(umgebung, phase):
    t = Attrappe()
    _vorgang(umgebung, "v-alt", phase)

    with pytest.raises(assistent.AssistentFehler, match="Wechsel läuft bereits"):
        _uebergeben(umgebung, "codex", None, ChatRef("codex", K_NEU), t)

    assert [v.id for v in av.lesen()] == ["v-alt"] and t.aufrufe == []


@pytest.mark.parametrize("phase", ["rolle_gesetzt", "gesendet", "im_postfach", "im_chat", "unklar", "fehler",
                                   "bestaetigt", "verworfen"])
def test_ab_rolle_gesetzt_blockiert_ein_alter_vorgang_nicht_mehr(umgebung, phase):
    t = Attrappe()
    _vorgang(umgebung, "v-alt", phase)

    neu = _uebergeben(umgebung, "codex", None, ChatRef("codex", K_NEU), t)

    assert neu.phase == "gesendet"
    alt = av.finden("v-alt")
    if phase in av.UEBERHOLBAR:
        assert (alt.phase, alt.fehler) == ("verworfen", "überholt")
    else:
        assert alt.phase == phase                                 # endgültige Vorgänge bleiben unangetastet


def test_wechsel_ueber_einen_unquittierten_wechsel_hinweg_verwirft_den_alten_und_leert_sein_postfach(umgebung):
    t = Attrappe()
    erster = _uebergeben(umgebung, "claude", None, ChatRef("claude", K_NEU), t)       # A -> B, nie quittiert
    assert erster.phase == "im_postfach"

    zweiter = _uebergeben(umgebung, "codex", ChatRef("claude", K_NEU), ChatRef("codex", K_ALT), t)   # B -> C
    assert zweiter.phase == "abgabe_angefragt"
    av.quittieren(zweiter.id, "abgabe", umgebung.repo)
    zweiter = _fortsetzen(umgebung, zweiter.id, t)

    assert zweiter.phase == "gesendet"
    alt = av.finden(erster.id)
    assert (alt.phase, alt.fehler) == ("verworfen", "überholt")
    assert postfach.abholen("claude", K_NEU, umgebung.repo) == []          # weder neu noch Abgabe-Auftrag gelten noch
    eintraege = [(e["vorgang"], e["entscheidung"], e["grund"]) for e in protokoll.lesen(200)]
    assert (erster.id, "verworfen", "überholt") in eintraege


def test_doppelklick_waehrend_abgabe_angefragt_wird_abgelehnt(umgebung):
    t = Attrappe()
    v = _uebergeben(umgebung, "claude", ChatRef("codex", K_ALT), ChatRef("claude", K_NEU), t)
    assert v.phase == "abgabe_angefragt"

    with pytest.raises(assistent.AssistentFehler, match="Wechsel läuft bereits"):
        _uebergeben(umgebung, "hermes", ChatRef("codex", K_ALT), ChatRef("hermes", K_NEU), t)

    assert len(av.lesen()) == 1 and len(t.aufrufe) == 1


def test_nach_endgueltigem_vorgang_ist_ein_neuer_wechsel_moeglich(umgebung):
    t = Attrappe()
    v = _uebergeben(umgebung, "codex", None, ChatRef("codex", K_NEU), t)
    av.quittieren(v.id, "neu", umgebung.repo)                     # bestaetigt = endgültig

    zweiter = _uebergeben(umgebung, "hermes", ChatRef("codex", K_NEU), ChatRef("hermes", K_ALT), t)

    assert zweiter.id != v.id and zweiter.von == "codex" and zweiter.phase == "abgabe_angefragt"


# --- Transportfälle -------------------------------------------------------------------------------

FEHLERFAELLE = [
    pytest.param(dict(rc=0), "ok", id="rc0"),
    pytest.param(dict(rc=1), "unklar", id="rc1"),
    pytest.param(dict(fehler=FileNotFoundError()), "fehler", id="nicht-gefunden"),
    pytest.param(dict(fehler=PermissionError()), "fehler", id="zugriff"),
    pytest.param(dict(fehler=NotADirectoryError()), "fehler", id="kein-ordner"),
    pytest.param(dict(fehler=subprocess.TimeoutExpired("codex", 60)), "unklar", id="timeout"),
    pytest.param(dict(fehler=RuntimeError("boom")), "unklar", id="laufzeitfehler"),
    pytest.param(dict(fehler=OSError("irgendwas")), "unklar", id="anderer-oserror"),
]


@pytest.mark.parametrize("wirkung, erwartung", FEHLERFAELLE)
def test_codex_abgabe_transport_einordnung(umgebung, wirkung, erwartung):
    t = Attrappe(**wirkung)

    v = _uebergeben(umgebung, "claude", ChatRef("codex", K_ALT), ChatRef("claude", K_NEU), t)

    assert v.phase == {"ok": "abgabe_angefragt", "fehler": "abgabe_fehler", "unklar": "abgabe_unklar"}[erwartung]
    assert len(t.aufrufe) == 1


@pytest.mark.parametrize("wirkung, erwartung", FEHLERFAELLE)
def test_codex_neu_transport_einordnung(umgebung, wirkung, erwartung):
    t = Attrappe(**wirkung)

    v = _uebergeben(umgebung, "codex", None, ChatRef("codex", K_NEU), t)

    assert v.phase == {"ok": "gesendet", "fehler": "fehler", "unklar": "unklar"}[erwartung]
    assert len(t.aufrufe) == 1
    _marke_von(umgebung, v.id, "codex")                           # die Rolle bleibt gesetzt, auch bei Fehlern
    assert _fortsetzen(umgebung, v.id, t).phase == v.phase and len(t.aufrufe) == 1   # nie automatisch neu


def test_fehlendes_programm_ist_nachweislich_nicht_gestartet(umgebung, tmp_path, monkeypatch):
    monkeypatch.delenv("MASTER_SCHALTER_CODEX")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "leer"))
    t = Attrappe()

    abgabe = _uebergeben(umgebung, "claude", ChatRef("codex", K_ALT), ChatRef("claude", K_NEU), t)

    assert abgabe.phase == "abgabe_fehler" and t.aufrufe == []


def test_fehlendes_programm_bei_neu_ist_fehler(umgebung, tmp_path, monkeypatch):
    monkeypatch.delenv("MASTER_SCHALTER_CODEX")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "leer"))
    t = Attrappe()

    v = _uebergeben(umgebung, "codex", None, ChatRef("codex", K_NEU), t)

    assert v.phase == "fehler" and t.aufrufe == []


def test_postfach_ausnahme_ergibt_abgabe_fehler_bzw_fehler(umgebung, monkeypatch):
    def kaputt(*args, **kwargs):
        raise postfach.PostfachFehler("kaputt")

    monkeypatch.setattr(postfach, "einlegen", kaputt)

    abgabe = _uebergeben(umgebung, "hermes", ChatRef("claude", K_ALT), ChatRef("hermes", K_NEU))
    assert abgabe.phase == "abgabe_fehler"
    av.abgabe_ueberspringen(abgabe.id, "Test")
    assert _fortsetzen(umgebung, abgabe.id).phase == "fehler"


# --- Quittung schon während des Transports --------------------------------------------------------

def test_codex_quittiert_abgabe_waehrend_des_transports_phase_bleibt_abgegeben(umgebung, monkeypatch):
    monkeypatch.setattr(assistent, "fortsetzen", lambda vorgang_id, **kw: av.finden(vorgang_id))
    t = Attrappe(vorher=lambda liste: av.quittieren(av.lesen()[0].id, "abgabe", umgebung.repo))

    v = _uebergeben(umgebung, "claude", ChatRef("codex", K_ALT), ChatRef("claude", K_NEU), t)

    assert v.phase == "abgegeben" and v.abgabe == "abgegeben"     # das Transportergebnis überschreibt nichts


def test_codex_quittiert_neu_waehrend_des_transports_phase_bleibt_bestaetigt(umgebung):
    t = Attrappe(vorher=lambda liste: av.quittieren(av.lesen()[0].id, "neu", umgebung.repo))

    v = _uebergeben(umgebung, "codex", None, ChatRef("codex", K_NEU), t)

    assert v.phase == "bestaetigt"


def test_transporte_laufen_weder_unter_themen_noch_unter_dateisperre(umgebung):
    belegt = []

    def pruefen(liste):
        with zustand.thema_sperre(THEMA) as frei:                 # nicht blockierend: unter Sperre wäre das False
            belegt.append(("thema", frei))
        try:
            with zustand.sperre(frist=0.2, takt=0.02):
                belegt.append(("datei", True))
        except zustand.SperrFehler:
            belegt.append(("datei", False))

    umgebung.marke_setzen(CODEX_MARKE)
    t = Attrappe(vorher=pruefen)
    v = _uebergeben(umgebung, "codex", ChatRef("codex", K_ALT), ChatRef("codex", K_NEU), t)   # Abgabe-Transport
    av.quittieren(v.id, "abgabe", umgebung.repo)
    _fortsetzen(umgebung, v.id, t)                                                              # Zustellungs-Transport

    assert len(t.aufrufe) == 2
    assert belegt == [("thema", True), ("datei", True)] * 2


# --- Abstürze: nie doppelt senden -----------------------------------------------------------------

def _vorgang(umgebung, vorgang_id, phase, ziel="codex", von="claude", von_chat=None, nach_chat=None):
    """Vorgang wie nach einem Absturz in `phase` hinterlassen (Vorzustand = aktueller Stand)."""
    umgebung.vorbereiten(vorgang_id, ziel=ziel, von=von, phase=phase)
    av.aktualisieren(vorgang_id, von_chat=von_chat, nach_chat=nach_chat)
    return vorgang_id


def test_absturz_im_abgabe_transport_nie_neu_senden(umgebung):
    t = Attrappe(fehler=RuntimeError("Absturz"))
    v = _uebergeben(umgebung, "claude", ChatRef("codex", K_ALT), ChatRef("claude", K_NEU), t)
    assert v.phase == "abgabe_unklar"

    for _ in range(3):
        assert _fortsetzen(umgebung, v.id, t).phase == "abgabe_unklar"
    assert [w.status for w in av.wiederaufnehmen(umgebung.repo)] == ["abgabe_offen"]

    assert len(t.aufrufe) == 1


def test_abbruch_nach_abgabe_sende_wiederaufnahme_und_fortsetzen_senden_nie(umgebung):
    t = Attrappe()
    ident = _vorgang(umgebung, "v-abgabe", "vorbereitet", von_chat={"werkzeug": "claude", "kennung": K_ALT},
                     nach_chat={"werkzeug": "codex", "kennung": K_NEU})
    av.abgabe_beginnen(ident)                                     # Prozess stirbt vor dem Transport

    assert _fortsetzen(umgebung, ident, t).phase == "abgabe_sende"
    assert [w.status for w in av.wiederaufnehmen(umgebung.repo)] == ["unklar"]
    assert _fortsetzen(umgebung, ident, t).phase == "abgabe_unklar"
    assert t.aufrufe == [] and not postfach.wurzel().exists()

    ende = _fortsetzen(umgebung, ident, t, jetzt=datetime.now(timezone.utc) + timedelta(minutes=11))

    assert ende.phase == "gesendet"                               # nach der Frist geht es ohne Abgabe weiter
    assert len(t.aufrufe) == 1 and t.aufrufe[0][3] == K_NEU       # nur die Zustellung, nie ein zweiter Abgabe-Auftrag


def test_abbruch_nach_rolle_gesetzt_sendet_genau_einmal(umgebung):
    t = Attrappe()
    ident = _vorgang(umgebung, "v-rolle", "rolle_gesetzt", nach_chat={"werkzeug": "codex", "kennung": K_NEU})
    umgebung.uebergeben(ident, "codex")

    assert [w.status for w in av.wiederaufnehmen(umgebung.repo)] == ["nachholbar"]
    assert _fortsetzen(umgebung, ident, t).phase == "gesendet"
    assert _fortsetzen(umgebung, ident, t).phase == "gesendet"
    assert len(t.aufrufe) == 1


def test_abbruch_nach_sende_wird_unklar_und_nie_neu_gesendet(umgebung):
    t = Attrappe()
    ident = _vorgang(umgebung, "v-sende", "sende", nach_chat={"werkzeug": "codex", "kennung": K_NEU})
    umgebung.uebergeben(ident, "codex")

    assert _fortsetzen(umgebung, ident, t).phase == "sende"
    assert [w.status for w in av.wiederaufnehmen(umgebung.repo)] == ["unklar"]
    assert _fortsetzen(umgebung, ident, t).phase == "unklar"
    assert t.aufrufe == []


def test_abbruch_zwischen_rollensetzen_und_phase_setzt_die_rolle_nicht_ein_zweites_mal(umgebung):
    t = Attrappe()
    ident = _vorgang(umgebung, "v-luecke", "abgegeben", nach_chat={"werkzeug": "codex", "kennung": K_NEU})
    umgebung.uebergeben(ident, "codex")                           # Marke steht schon, die Phase noch nicht
    vorher = umgebung.master_datei().read_bytes()

    ende = _fortsetzen(umgebung, ident, t)

    assert ende.phase == "gesendet" and len(t.aufrufe) == 1
    assert umgebung.master_datei().read_bytes() == vorher         # keine zweite Marke


def test_eigene_zwischenmarke_eines_abgebrochenen_rollensetzens_wird_fortgesetzt(umgebung):
    t = Attrappe()
    ident = _vorgang(umgebung, "v-zwischen", "abgegeben", nach_chat={"werkzeug": "codex", "kennung": K_NEU})
    umgebung.marke_setzen(modi.zwischenmarke(THEMA, "codex", "2026-10-22T10:00:00+00:00"))

    ende = _fortsetzen(umgebung, ident, t)

    assert ende.phase == "gesendet"
    _marke_von(umgebung, ident, "codex")


def test_fortsetzen_laesst_andere_phasen_unveraendert(umgebung):
    t = Attrappe()
    for nr, phase in enumerate(("im_postfach", "gesendet", "unklar", "fehler", "im_chat", "bestaetigt", "verworfen",
                                "vorbereitet")):
        _vorgang(umgebung, f"v-{nr}", phase, nach_chat={"werkzeug": "codex", "kennung": K_NEU})
    vorher = av.lesen()

    for vorgang in vorher:
        assert _fortsetzen(umgebung, vorgang.id, t) == vorgang

    assert av.lesen() == vorher and t.aufrufe == []


def test_fortsetzen_unbekannte_oder_ungueltige_id(umgebung):
    with pytest.raises(assistent.AssistentFehler, match="unbekannt"):
        assistent.fortsetzen("v-gibtsnicht", repo=umgebung.repo)
    with pytest.raises(assistent.AssistentFehler) as info:
        assistent.fortsetzen("../PRIVAT_4711", repo=umgebung.repo)
    assert "PRIVAT_4711" not in str(info.value)                      # R6/1: Eingabe nie wiederholen
    with pytest.raises(assistent.AssistentFehler) as info:
        assistent.uebergeben("../PRIVAT_4711", "codex", repo=umgebung.repo)
    assert "PRIVAT_4711" not in str(info.value)


# --- Ungültige Eingaben: Fehler ohne Nebenwirkung -------------------------------------------------

def _ohne_nebenwirkung(umgebung, t, marke_vorher):
    assert av.lesen() == [] and t.aufrufe == [] and not postfach.wurzel().exists()
    assert umgebung.marke() == marke_vorher and modi.profil(THEMA).master == "kontingent"
    assert not protokoll.datei().exists()


def test_von_chat_ist_nicht_der_besitzer_der_marke(umgebung):
    t = Attrappe()
    umgebung.marke_setzen(CODEX_MARKE)                            # Besitzer ist Codex, der Aufrufer nennt einen Claude-Chat
    with pytest.raises(assistent.AssistentFehler, match="alte Chat gehört nicht"):
        _uebergeben(umgebung, "hermes", ChatRef("claude", K_ALT), ChatRef("hermes", K_NEU), t)
    _ohne_nebenwirkung(umgebung, t, CODEX_MARKE)


def test_nach_chat_gehoert_nicht_zur_zielrolle(umgebung):
    t = Attrappe()
    with pytest.raises(assistent.AssistentFehler, match="neue Chat gehört nicht zur Zielrolle"):
        _uebergeben(umgebung, "hermes", ChatRef("claude", K_ALT), ChatRef("codex", K_NEU), t)
    _ohne_nebenwirkung(umgebung, t, "")


def test_alter_und_neuer_chat_dasselbe_ist_ein_fehler(umgebung):
    t = Attrappe()
    with pytest.raises(assistent.AssistentFehler, match="derselbe"):
        _uebergeben(umgebung, "claude", ChatRef("claude", K_ALT), ChatRef("claude", K_ALT), t)
    _ohne_nebenwirkung(umgebung, t, "")


@pytest.mark.parametrize("werkzeug, kennung", [
    ("claude", "../x"), ("claude", ""), ("claude", "a b"), ("claude", "k" * 81), ("claude", "k\n"),
    ("claude", "ab/cd"), ("gemini", "GEHEIM-9"), ("", "GEHEIM-9"), ("kontingent", "GEHEIM-9")])
def test_unzulaessige_chatreferenz_nennt_die_kennung_nicht(werkzeug, kennung):
    with pytest.raises(assistent.AssistentFehler) as fehler:
        ChatRef(werkzeug, kennung)
    assert kennung.strip() == "" or kennung not in str(fehler.value)


@pytest.mark.parametrize("ziel", ["kontingent", "gemini", "", None])
def test_unzulaessiges_ziel(umgebung, ziel):
    t = Attrappe()
    with pytest.raises(assistent.AssistentFehler, match="Zielrolle"):
        _uebergeben(umgebung, ziel, None, None, t)
    _ohne_nebenwirkung(umgebung, t, "")


def test_unbekanntes_oder_ungueltiges_thema(umgebung):
    with pytest.raises(assistent.AssistentFehler):
        assistent.uebergeben("Gross Geschrieben", "codex", repo=umgebung.repo)
    with pytest.raises(assistent.AssistentFehler, match="Thema unbekannt"):
        assistent.uebergeben("gibtsnicht", "codex", repo=umgebung.repo)
    assert av.lesen() == []


def test_reservierte_marke_wird_nicht_uebergeben(umgebung):
    t = Attrappe()
    reserviert = besitz.zeile(besitz.RESERVIERT, "lauf-1", "2026-10-22T10:00:00+00:00")
    umgebung.marke_setzen(reserviert)
    with pytest.raises(assistent.AssistentFehler, match="nicht übergebbar"):
        _uebergeben(umgebung, "codex", None, ChatRef("codex", K_NEU), t)
    assert av.lesen() == [] and t.aufrufe == [] and umgebung.marke() == reserviert


def test_unbekannte_marke_nennt_den_dateiinhalt_nicht(umgebung):
    # R5/1: `besitz.besitzer` liefert das erste Wort der Datei – das darf nie in die Meldung.
    t = Attrappe()
    umgebung.marke_setzen("C:/PRIVAT_4711 irgendwas")
    with pytest.raises(assistent.AssistentFehler) as info:
        _uebergeben(umgebung, "codex", None, ChatRef("codex", K_NEU), t)
    assert str(info.value) == "Thema ist gerade nicht übergebbar (Besitz: unbekannt)"
    assert av.lesen() == [] and t.aufrufe == []


def test_keine_chatreferenz_als_text(umgebung):
    with pytest.raises(assistent.AssistentFehler):
        assistent.uebergeben(THEMA, "codex", von_chat="claude:abc", repo=umgebung.repo)  # type: ignore[arg-type]
    assert av.lesen() == []


# --- Keine Kennungen in Texten, Postfachdateien und Protokoll -------------------------------------

def test_kennungen_stehen_nur_in_assistent_json_nie_in_texten_oder_protokoll(umgebung):
    t = Attrappe()
    # Weg 1: Codex alt -> Claude neu, mit Frist (Info) und Zustellung
    v1 = _uebergeben(umgebung, "claude", ChatRef("codex", K_ALT), ChatRef("claude", K_NEU), t)
    _fortsetzen(umgebung, v1.id, t, jetzt=datetime.now(timezone.utc) + timedelta(minutes=11))
    abgeholt = postfach.abholen("claude", K_NEU, umgebung.repo)
    av.quittieren(v1.id, "neu", umgebung.repo)
    # Weg 2: Claude alt -> Codex neu
    v2 = _uebergeben(umgebung, "codex", ChatRef("claude", K_ALT), ChatRef("codex", K_NEU), t)
    abgeholt += postfach.abholen("claude", K_ALT, umgebung.repo)
    av.quittieren(v2.id, "abgabe", umgebung.repo)
    _fortsetzen(umgebung, v2.id, t)

    gesendet = "\n".join(arg for aufruf in t.aufrufe for arg in (aufruf[0], aufruf[1], aufruf[2], aufruf[4], aufruf[5]))
    assert len(t.aufrufe) >= 3
    for kennung in (K_ALT, K_NEU):
        assert kennung not in gesendet
        assert kennung not in "\n".join(n.text for n in abgeholt)
        assert kennung not in _alle_postfachtexte()
        assert kennung not in protokoll.datei().read_text(encoding="utf-8")
        assert kennung not in str(protokoll.lesen())
    assert K_ALT in av.datei().read_text(encoding="utf-8")        # nur hier stehen sie (G9)
    assert {e["vorgang"] for e in protokoll.lesen(200)} == {v1.id, v2.id}


def test_protokoll_haelt_die_wichtigen_entscheidungen_fest(umgebung):
    t = Attrappe()
    v = _uebergeben(umgebung, "claude", ChatRef("codex", K_ALT), ChatRef("claude", K_NEU), t)
    _fortsetzen(umgebung, v.id, t, jetzt=datetime.now(timezone.utc) + timedelta(minutes=11))

    entscheidungen = [e["entscheidung"] for e in protokoll.lesen(200)]

    assert entscheidungen == ["angelegt", "abgabe_zustellweg", "abgabe_ergebnis", "abgabe_uebersprungen",
                              "rolle_gesetzt", "info_gesendet", "neu_zustellweg", "neu_ergebnis"]
    eintraege = {e["entscheidung"]: e for e in protokoll.lesen(200)}
    assert eintraege["abgabe_uebersprungen"]["grund"] == "Frist abgelaufen"
    assert eintraege["abgabe_ergebnis"]["grund"] == "abgabe_angefragt"
    assert eintraege["neu_ergebnis"]["grund"] == "im_postfach"
    assert all(e["thema"] == THEMA and e["zeit"] for e in eintraege.values())


def test_protokoll_verworfen_nennt_den_grund(umgebung):
    t = Attrappe()
    v = _uebergeben(umgebung, "codex", ChatRef("claude", K_ALT), ChatRef("codex", K_NEU), t)
    av.quittieren(v.id, "abgabe", umgebung.repo)
    umgebung.marke_setzen("hermes 2026-10-22T11:00:00+00:00 modus fremd")

    _fortsetzen(umgebung, v.id, t)

    letzter = protokoll.lesen()[-1]
    assert (letzter["entscheidung"], letzter["grund"]) == ("verworfen", "Stand geändert")


# --- Keine Ausnahmetexte in Protokoll und Vorgangsdatei -------------------------------------------

PFADTEXT = "C:/Users/GEHEIM-PFAD-4711/geheim.master"


def test_modusfehler_mit_pfadtext_landet_weder_im_protokoll_noch_in_assistent_json(umgebung, monkeypatch):
    def kaputt(*args, **kwargs):
        raise modi.ModusFehler(f"Besitzdatei nicht schreibbar ({PFADTEXT})")

    monkeypatch.setattr(modi, "master_uebergeben_gesperrt", kaputt)
    t = Attrappe()

    # über uebergeben: der Fehler wird geschluckt, der Vorgang steht in `abgegeben`
    v = _uebergeben(umgebung, "codex", None, ChatRef("codex", K_NEU), t)
    assert v.phase == "abgabe_uebersprungen" and t.aufrufe == []
    # direkt über fortsetzen: AssistentFehler nennt nur die Fehlerklasse, die Ursache hängt an der Kette
    with pytest.raises(assistent.AssistentFehler) as fehler:
        _fortsetzen(umgebung, v.id, t)

    assert PFADTEXT not in str(fehler.value) and "ModusFehler" in str(fehler.value)
    assert isinstance(fehler.value.__cause__, modi.ModusFehler) and PFADTEXT in str(fehler.value.__cause__)
    assert "GEHEIM-PFAD" not in protokoll.datei().read_text(encoding="utf-8")
    assert "GEHEIM-PFAD" not in av.datei().read_text(encoding="utf-8")
    assert ("fortsetzen_fehlgeschlagen", "ModusFehler") in         [(e["entscheidung"], e["grund"]) for e in protokoll.lesen(200)]


def test_nicht_pruefbare_marke_bei_der_zustellung_nennt_nur_die_fehlerklasse(umgebung, monkeypatch):
    t = Attrappe()
    v = _uebergeben(umgebung, "codex", None, None, t)
    av.aktualisieren(v.id, nach_chat={"werkzeug": "codex", "kennung": K_NEU})

    def kaputt(*args, **kwargs):
        raise modi.ModusFehler(f"Besitzstatus nicht lesbar ({PFADTEXT})")

    monkeypatch.setattr(av, "marke_pruefen", kaputt)
    with pytest.raises(assistent.AssistentFehler) as fehler:
        _fortsetzen(umgebung, v.id, t)

    assert PFADTEXT not in str(fehler.value) and "ModusFehler" in str(fehler.value) and t.aufrufe == []


def test_verwerfungsgrund_bei_ueberholter_marke_zitiert_keinen_dateiinhalt(umgebung):
    t = Attrappe()
    v = _uebergeben(umgebung, "codex", None, None, t)
    av.aktualisieren(v.id, nach_chat={"werkzeug": "codex", "kennung": K_NEU})
    umgebung.marke_setzen(besitz.assistent_zeile("GEHEIM-WER", "2026-10-22T11:00:00+00:00", THEMA, v.id))

    ende = _fortsetzen(umgebung, v.id, t)

    assert ende.phase == "verworfen" and "GEHEIM-WER" not in (ende.fehler or "")
    assert "GEHEIM-WER" not in protokoll.datei().read_text(encoding="utf-8")


# --- R1-Nachbesserung: Info erst nach dem Rollenwechsel ---------------------------------------------

def _frist_vorbei():
    return datetime.now(timezone.utc) + timedelta(minutes=11)


def test_frist_allein_sendet_keine_info_scheitert_das_rollensetzen_bleibt_sie_aus(umgebung, monkeypatch):
    t = Attrappe()
    v = _uebergeben(umgebung, "claude", ChatRef("codex", K_ALT), ChatRef("claude", K_NEU), t)
    echt = modi.master_uebergeben_gesperrt

    def kaputt(*args, **kwargs):
        raise modi.ModusFehler("Besitzdatei nicht schreibbar")

    monkeypatch.setattr(modi, "master_uebergeben_gesperrt", kaputt)
    with pytest.raises(assistent.AssistentFehler):
        _fortsetzen(umgebung, v.id, t, jetzt=_frist_vorbei())

    assert av.finden(v.id).phase == "abgabe_uebersprungen"        # die Frist wirkt, die Rolle fehlt noch
    assert len(t.aufrufe) == 1                                    # nur der Abgabe-Auftrag, keine Info
    assert not any(e["entscheidung"].startswith("info") for e in protokoll.lesen(200))

    monkeypatch.setattr(modi, "master_uebergeben_gesperrt", echt)  # nächster Takt: Rolle gelingt -> genau eine Info
    ende = _fortsetzen(umgebung, v.id, t, jetzt=_frist_vorbei())
    _fortsetzen(umgebung, v.id, t, jetzt=_frist_vorbei())

    assert ende.phase == "im_postfach" and len(t.aufrufe) == 2
    assert t.texte[1] == postfach.text("abgabe_info", THEMA, paare.laufend_bilden(THEMA), v.id)
    assert [e["entscheidung"] for e in protokoll.lesen(200)].count("info_gesendet") == 1


def test_belegte_themensperre_haelt_rollensetzen_und_info_zurueck(umgebung):
    t = Attrappe()
    v = _uebergeben(umgebung, "claude", ChatRef("codex", K_ALT), ChatRef("claude", K_NEU), t)

    with zustand.thema_sperre(THEMA) as frei:
        assert frei
        belegt = _fortsetzen(umgebung, v.id, t, jetzt=_frist_vorbei())

    assert belegt.phase == "abgabe_uebersprungen" and len(t.aufrufe) == 1
    assert besitz.assistent_marke(umgebung.marke()) is None       # Rolle noch nicht gesetzt
    assert _fortsetzen(umgebung, v.id, t, jetzt=_frist_vorbei()).phase == "im_postfach"
    assert len(t.aufrufe) == 2


def test_info_geht_ausserhalb_der_themensperre_an_codex_und_nur_bei_uebersprungener_abgabe(umgebung):
    belegt = []

    def pruefen(liste):
        with zustand.thema_sperre(THEMA) as frei:
            belegt.append(frei)

    t = Attrappe(vorher=pruefen)
    v = _uebergeben(umgebung, "claude", ChatRef("codex", K_ALT), ChatRef("claude", K_NEU), t)
    _fortsetzen(umgebung, v.id, t, jetzt=_frist_vorbei())
    assert len(t.aufrufe) == 2 and belegt == [True, True]

    # regulär abgegeben: nie eine Info
    av.quittieren(v.id, "neu", umgebung.repo)
    t2 = Attrappe()
    w = _uebergeben(umgebung, "hermes", ChatRef("claude", K_NEU), ChatRef("hermes", K_ALT), t2)
    av.quittieren(w.id, "abgabe", umgebung.repo)
    _fortsetzen(umgebung, w.id, t2)
    assert not (postfach.ordner("claude", K_NEU) / f"{w.id}_abgabe_info.json").exists()


# --- R1-Nachbesserung: Zustellung unter der Themensperre, Rollensetzen wartet auf `sende` ---------------

def test_markenpruefung_und_sende_gewinn_laufen_unter_der_themensperre(umgebung, monkeypatch):
    import threading

    t = Attrappe()
    v = _uebergeben(umgebung, "codex", None, None, t)
    av.aktualisieren(v.id, nach_chat={"werkzeug": "codex", "kennung": K_NEU})
    echt = av.marke_pruefen
    ergebnis = {}

    def pruefen(*args, **kwargs):
        grund = echt(*args, **kwargs)
        if "sperre_frei" in ergebnis:                             # nur der erste Aufruf (unter der Sperre) zählt
            return grund
        with zustand.thema_sperre(THEMA) as frei:                 # nicht blockierend
            ergebnis["sperre_frei"] = frei

        def zweiter():                                            # ein zweiter Wechsel will jetzt seine Marke schreiben
            try:
                modi.master_setzen(THEMA, "hermes", repo=umgebung.repo)
                ergebnis["zweiter"] = "gesetzt"
            except modi.ModusFehler as fehler:
                ergebnis["zweiter"] = type(fehler).__name__

        faden = threading.Thread(target=zweiter)
        faden.start()
        faden.join(timeout=30)
        return grund

    monkeypatch.setattr(av, "marke_pruefen", pruefen)
    ende = _fortsetzen(umgebung, v.id, t)

    assert ergebnis == {"sperre_frei": False, "zweiter": "ModusFehler"}
    assert ende.phase == "gesendet" and len(t.aufrufe) == 1
    _marke_von(umgebung, v.id, "codex")                           # die Marke blieb die des ersten Vorgangs


def test_vorgang_in_sende_haelt_das_rollensetzen_eines_anderen_zurueck(umgebung):
    t = Attrappe()
    erster = _vorgang(umgebung, "v-1", "sende", ziel="codex", nach_chat={"werkzeug": "codex", "kennung": K_NEU})
    umgebung.uebergeben(erster, "codex")                          # seine Marke steht, die Nachricht geht gerade raus
    marke = umgebung.marke()
    zweiter = _vorgang(umgebung, "v-2", "abgegeben", ziel="hermes", von="codex",
                       nach_chat={"werkzeug": "hermes", "kennung": K_ALT})

    wartet = _fortsetzen(umgebung, zweiter, t)

    assert wartet.phase == "abgegeben" and umgebung.marke() == marke and modi.profil(THEMA).master == "codex"
    assert not postfach.wurzel().exists()

    av.aktualisieren(erster, phase="gesendet")                    # Ergebnis ist da
    ende = _fortsetzen(umgebung, zweiter, t)

    assert ende.phase == "im_postfach"
    _marke_von(umgebung, zweiter, "hermes")
    assert (av.finden(erster).phase, av.finden(erster).fehler) == ("verworfen", "überholt")


def test_veraltete_zustellung_nach_ueberholendem_wechsel_sendet_nicht(umgebung):
    t = Attrappe()
    v = _uebergeben(umgebung, "codex", None, None, t)
    av.aktualisieren(v.id, nach_chat={"werkzeug": "codex", "kennung": K_NEU})
    veraltet = av.finden(v.id)                                    # der Takt hat diesen Stand gelesen ...
    modi.master_setzen(THEMA, "hermes", repo=umgebung.repo)       # ... da schreibt ein zweiter Wechsel seine Marke

    ende = assistent._zustellen(veraltet, repo=umgebung.repo, jetzt=datetime.now(timezone.utc), transport=t)

    assert ende.phase == "verworfen" and t.aufrufe == []


# --- R1-Nachbesserung: keine Pfade in Fehlermeldungen --------------------------------------------------

def test_oserror_mit_pfad_beim_lesen_der_besitzdatei_taucht_nirgends_auf(umgebung, capsys, tmp_path):
    from master_schalter import cli

    umgebung.master_datei().parent.mkdir(parents=True, exist_ok=True)
    umgebung.master_datei().mkdir()                               # Lesen schlägt mit OSError samt Pfad fehl
    with pytest.raises(modi.ModusFehler) as roh:
        modi._besitz_text_lesen(umgebung.master_datei())
    assert "engineering.master" in str(roh.value)                 # Vorbedingung: modi.py zitiert den Pfad wirklich

    with pytest.raises(assistent.AssistentFehler) as fehler:
        _uebergeben(umgebung, "codex", None, ChatRef("codex", K_NEU), Attrappe())
    assert "Besitz- oder Datendatei nicht lesbar" in str(fehler.value) and "Error)" in str(fehler.value)
    assert str(tmp_path) not in str(fehler.value) and "engineering.master" not in str(fehler.value)
    assert isinstance(fehler.value.__cause__, modi.ModusFehler)

    assert cli.main(["uebergeben", THEMA, "codex", "--nach", f"codex:{K_NEU}"]) == 1
    ausgabe = capsys.readouterr()
    assert str(tmp_path) not in ausgabe.err + ausgabe.out and "engineering.master" not in ausgabe.err
    assert not protokoll.datei().exists() or str(tmp_path) not in protokoll.datei().read_text(encoding="utf-8")


def test_assistentfehler_helfer_uebernimmt_nie_fremden_text():
    pruef = modi.ModusFehler("Thema unbekannt (kein vorhandenes Paar): x")
    assert str(assistent._assistentfehler(pruef, vorspann="Wechsel nicht gestartet")) == \
        "Wechsel nicht gestartet (ModusFehler)"

    ursache = PermissionError(13, "Zugriff", "C:/geheim/pfad.master")
    kette = modi.ModusFehler("Besitzstatus nicht lesbar (C:/geheim/pfad.master)")
    kette.__cause__ = ursache
    text = str(assistent._assistentfehler(kette, vorspann="Rolle nicht gesetzt"))
    assert text == "Rolle nicht gesetzt: Besitz- oder Datendatei nicht lesbar (PermissionError)"

    sperre = str(assistent._assistentfehler(zustand.SperrFehler("Sperre auf x.lock blieb 1 s belegt")))
    assert sperre == "Sperre gerade belegt (SperrFehler)"
    assert str(assistent._assistentfehler(ValueError("C:/x"), vorspann="Marke")) == "Marke (ValueError)"


# --- R2-Nachbesserung: Restfenster vor dem Transport, Info nach Rückwechsel, bereinigte Ausnahmen ---------

@pytest.mark.parametrize("ziel, ziel_marke_wechsel", [("codex", "hermes"), ("claude", "codex"), ("hermes", "claude")])
def test_marke_wechselt_zwischen_sende_gewinn_und_transport_nichts_wird_gesendet(umgebung, monkeypatch, ziel,
                                                                                   ziel_marke_wechsel):
    t = Attrappe()
    v = _uebergeben(umgebung, ziel, None, None, t)
    av.aktualisieren(v.id, nach_chat={"werkzeug": ziel, "kennung": K_NEU})
    echt = postfach.text

    def text_und_wechsel(art, *args, **kwargs):
        if art == "neu":                                          # genau zwischen `sende`-Gewinn und Transport
            modi.master_setzen(THEMA, ziel_marke_wechsel, repo=umgebung.repo)
        return echt(art, *args, **kwargs)

    monkeypatch.setattr(postfach, "text", text_und_wechsel)
    ende = _fortsetzen(umgebung, v.id, t)

    assert ende.phase == "verworfen" and ende.fehler == "Marke gehört nicht mehr zu diesem Vorgang"
    assert t.aufrufe == [] and not (postfach.ordner("claude", K_NEU).exists() if ziel == "claude" else False)
    assert not postfach.wurzel().exists() or not list(postfach.wurzel().rglob("*_neu.json"))
    assert ("neu_entfallen", "verworfen") in [(e["entscheidung"], e["grund"]) for e in protokoll.lesen(200)]
    assert _fortsetzen(umgebung, v.id, t).phase == "verworfen" and t.aufrufe == []


def test_nicht_pruefbare_marke_vor_dem_transport_sendet_nichts_und_endet_auf_fehler(umgebung, monkeypatch):
    t = Attrappe()
    v = _uebergeben(umgebung, "codex", None, None, t)
    av.aktualisieren(v.id, nach_chat={"werkzeug": "codex", "kennung": K_NEU})
    echt = av.marke_pruefen
    aufrufe = []

    def zweites_mal_kaputt(*args, **kwargs):
        aufrufe.append(1)
        if len(aufrufe) > 1:
            raise modi.ModusFehler("Besitzstatus nicht lesbar (C:/GEHEIM-PFAD)")
        return echt(*args, **kwargs)

    monkeypatch.setattr(av, "marke_pruefen", zweites_mal_kaputt)
    ende = _fortsetzen(umgebung, v.id, t)

    assert ende.phase == "fehler" and t.aufrufe == [] and "GEHEIM-PFAD" not in (ende.fehler or "")


def test_neu_text_nennt_die_quittung_als_voraussetzung(umgebung):
    t = Attrappe()
    v = _uebergeben(umgebung, "codex", None, ChatRef("codex", K_NEU), t)
    assert "Schlägt die Quittung fehl, beginne keinen Schritt – die Nachricht gilt dann nicht mehr." in t.texte[0]


@pytest.mark.parametrize("alt", ["codex", "claude"])
def test_wechselt_jemand_zwischen_rolle_und_info_zurueck_entfaellt_die_info(umgebung, monkeypatch, alt):
    t = Attrappe()
    v = _uebergeben(umgebung, "hermes", ChatRef(alt, K_ALT), ChatRef("hermes", K_NEU), t)
    echt = assistent._info_senden

    def zurueck_dann_info(vorgang, ref, transport, repo=None):
        modi.master_setzen(THEMA, alt, repo=umgebung.repo)         # schneller Rückwechsel an den alten Master
        return echt(vorgang, ref, transport, repo)

    monkeypatch.setattr(assistent, "_info_senden", zurueck_dann_info)
    _fortsetzen(umgebung, v.id, t, jetzt=_frist_vorbei())

    assert len(t.aufrufe) == (1 if alt == "codex" else 0)           # nur der Abgabe-Auftrag an Codex, keine Info
    assert not (postfach.ordner("claude", K_ALT) / f"{v.id}_abgabe_info.json").exists() if alt == "claude" else True
    entscheidungen = [(e["entscheidung"], e["grund"]) for e in protokoll.lesen(200)]
    assert ("info_entfallen", "Marke gehört nicht mehr zu diesem Vorgang") in entscheidungen
    assert not any(e[0] in ("info_gesendet", "info_fehlgeschlagen") for e in entscheidungen)


def test_info_entfaellt_auch_bei_verworfenem_vorgang(umgebung, monkeypatch):
    t = Attrappe()
    v = _uebergeben(umgebung, "hermes", ChatRef("codex", K_ALT), ChatRef("hermes", K_NEU), t)
    echt = assistent._info_senden

    def verwerfen_dann_info(vorgang, ref, transport, repo=None):
        av.aktualisieren(vorgang.id, phase="verworfen")
        return echt(vorgang, ref, transport, repo)

    monkeypatch.setattr(assistent, "_info_senden", verwerfen_dann_info)
    _fortsetzen(umgebung, v.id, t, jetzt=_frist_vorbei())

    assert len(t.aufrufe) == 1
    assert ("info_entfallen", "Vorgang verworfen") in [(e["entscheidung"], e["grund"]) for e in protokoll.lesen(200)]


def test_info_text_verweist_auf_besitzmarke_und_profil(umgebung):
    t = Attrappe()
    v = _uebergeben(umgebung, "claude", ChatRef("codex", K_ALT), ChatRef("claude", K_NEU), t)
    _fortsetzen(umgebung, v.id, t, jetzt=_frist_vorbei())

    assert t.texte[1].endswith(f"Maßgeblich ist die Besitzmarke; prüfe im Zweifel `masterwechsel profil {THEMA}`.")


def test_oserror_aus_abgabe_ergebnis_wird_bereinigt_phase_bleibt_abgabe_sende(umgebung, monkeypatch, capsys):
    from master_schalter import cli

    umgebung.marke_setzen(CODEX_MARKE)
    t = Attrappe()
    monkeypatch.setattr(codex_senden, "_transport", t)
    pfad = "C:/GEHEIM-PFAD-4711/assistent.json"

    def kaputt(*args, **kwargs):
        raise PermissionError(13, "Zugriff verweigert", pfad)

    monkeypatch.setattr(av, "abgabe_ergebnis", kaputt)
    with pytest.raises(assistent.AssistentFehler) as fehler:
        _uebergeben(umgebung, "claude", ChatRef("codex", K_ALT), ChatRef("claude", K_NEU), t)

    assert "GEHEIM-PFAD" not in str(fehler.value) and "PermissionError" in str(fehler.value)
    assert isinstance(fehler.value.__cause__, PermissionError)
    vorgang = av.lesen()[0]
    assert vorgang.phase == "abgabe_sende" and len(t.aufrufe) == 1    # Phase steht Write-ahead, gesendet wurde einmal
    assert [w.status for w in av.wiederaufnehmen(umgebung.repo)] == ["unklar"]
    assert _fortsetzen(umgebung, vorgang.id, t).phase == "abgabe_unklar" and len(t.aufrufe) == 1   # nie neu senden

    # CLI: neuer Vorgang für ein anderes Thema ist nicht nötig - ein weiterer Versuch wird als „läuft bereits" abgelehnt
    assert cli.main(["uebergeben", THEMA, "claude", "--von", f"codex:{K_ALT}"]) == 1
    ausgabe = capsys.readouterr()
    assert "GEHEIM-PFAD" not in ausgabe.out + ausgabe.err and len(t.aufrufe) == 1


def test_cli_gibt_bei_oserror_nach_dem_anlegen_keinen_pfad_aus(umgebung, monkeypatch, capsys):
    from master_schalter import cli

    monkeypatch.setattr(codex_senden, "_transport", Attrappe())

    def kaputt(*args, **kwargs):
        raise PermissionError(13, "Zugriff verweigert", "C:/GEHEIM-PFAD-4711/assistent.json")

    monkeypatch.setattr(av, "abgabe_ergebnis", kaputt)
    assert cli.main(["uebergeben", THEMA, "claude", "--von", f"claude:{K_ALT}", "--nach", f"claude:{K_NEU}"]) == 1

    ausgabe = capsys.readouterr()
    assert "GEHEIM-PFAD" not in ausgabe.out + ausgabe.err and "PermissionError" in ausgabe.err
    assert not protokoll.datei().exists() or "GEHEIM-PFAD" not in protokoll.datei().read_text(encoding="utf-8")


def test_beliebige_ausnahme_in_fortsetzen_wird_zum_bereinigten_assistentfehler(umgebung, monkeypatch):
    v = _uebergeben(umgebung, "codex", None, None, Attrappe())

    def kaputt(*args, **kwargs):
        raise ValueError("C:/GEHEIM-PFAD-4711")

    monkeypatch.setattr(av, "finden", kaputt)
    with pytest.raises(assistent.AssistentFehler) as fehler:
        _fortsetzen(umgebung, v.id)

    assert str(fehler.value) == "Vorgang gerade nicht bearbeitbar (ValueError)"


@pytest.mark.parametrize("text", [r"Repository-Wurzel fehlt: C:\Users\geheim\repo",
                                  "Wurzel /home/geheim/repo fehlt", "Repository-Wurzel fehlt: PRIVAT_geheim_4711"])
def test_fremder_text_wird_nie_uebernommen(text):
    meldung = str(assistent._assistentfehler(modi.ModusFehler(text)))
    assert "geheim" not in meldung
    assert "ModusFehler" in meldung


def test_uebergeben_nennt_einen_relativen_repo_ordner_nicht(umgebung, monkeypatch):
    # R3/R4: `MASTER_SCHALTER_REPO` zeigt auf einen fehlenden relativen Ordner; `uebergabe.repo_wurzel`
    # zitiert ihn im Fehlertext, `modi._paar_pruefen` reicht ihn weiter.
    monkeypatch.setenv("MASTER_SCHALTER_REPO", "PRIVAT_geheim_4711")
    with pytest.raises(assistent.AssistentFehler) as info:
        assistent.uebergeben(THEMA, "codex")
    assert "PRIVAT_geheim_4711" not in str(info.value)
    assert av.lesen() == []


def test_uebergeben_meldet_unbekanntes_thema_mit_eigenem_text(umgebung):
    with pytest.raises(assistent.AssistentFehler, match=r"^Thema unbekannt \(kein vorhandenes Paar\): gibtsnicht$"):
        assistent.uebergeben("gibtsnicht", "codex", repo=umgebung.repo)
