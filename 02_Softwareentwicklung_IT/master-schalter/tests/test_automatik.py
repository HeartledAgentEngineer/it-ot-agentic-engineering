"""Tests für die Automatik: Entscheidung, Kopfzeilen-Prüfung und den Ablauf unter der Themensperre."""
import threading
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from master_schalter import (automatik, besitz, codex_senden, modi, paare, signale, uebergabe, vorgaenge,
                             wechsel, zustand)
from master_schalter.auftrag import Auftrag

THREAD = "01a12557-3bb3-7171-a021-53e6ac879534"
JETZT = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
ENDE = JETZT + timedelta(hours=3)
FULL_HEAD = "abcdef1234567890abcdef1234567890abcdef12"
KURZ = "abcdef1"
SCHWELLE = 90


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    monkeypatch.setenv("MASTER_SCHALTER_CODEX_SESSIONS", str(tmp_path / "codex"))
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    monkeypatch.setenv("MASTER_SCHALTER_CODEX", "C:/werkzeuge/codex.exe")
    return repo


def _git(repo, args):
    if args[:2] == ["rev-parse", "--short"]:
        return KURZ + "\n"
    if args[:2] == ["rev-parse", "HEAD"]:
        return FULL_HEAD + "\n"
    if args[:2] == ["rev-list", "--count"]:
        return "42\n"
    if args[0] == "status":
        return ""
    raise AssertionError(args)


def _paar(thema="engineering", aktiv=True):
    return paare.Paar(thema, THREAD, f".hermes/uebergabe/laufend/{thema}.md", aktiv)


def _kontingent(master, fuenf, woche, *, stand=JETZT, reset=ENDE, fehler=None):
    if fehler:
        return signale.Kontingent(master, fehler=fehler)
    return signale.Kontingent(master, (signale.Fenster("5h", fuenf, reset),
                                       signale.Fenster("Woche", woche, reset)), stand=stand)


def _messung(claude_f=95, claude_w=50, codex_f=5, codex_w=5, *, claude_stand=JETZT,
             codex_stand=JETZT, claude_reset=ENDE, codex_reset=ENDE, claude_fehler=None,
             codex_fehler=None, claude_zurueck=False):
    claude = signale.Kontingent("Claude", (
        signale.Fenster("5h", 0.0, claude_reset, zurueckgesetzt=True) if claude_zurueck
        else signale.Fenster("5h", claude_f, claude_reset),
        signale.Fenster("Woche", claude_w, claude_reset)), stand=claude_stand, fehler=claude_fehler)
    return automatik.Messung(claude, _kontingent("Codex", codex_f, codex_w, stand=codex_stand,
                                                 reset=codex_reset, fehler=codex_fehler))


def _entscheiden(messung, *, paare_liste=None, vorgangsliste=(), an=True):
    return automatik.faellige(paare_liste or [_paar()], messung, SCHWELLE, an,
                              list(vorgangsliste), JETZT)


# --- Entscheidung -------------------------------------------------------------

def test_automatik_aus_entscheidet_nichts():
    assert _entscheiden(_messung(), an=False) == []


@pytest.mark.parametrize("fuenf,erwartet", [(89.9, 0), (90, 1), (90.1, 1), (100, 1)])
def test_grenzwerte_der_schwelle(fuenf, erwartet):
    assert len(_entscheiden(_messung(claude_f=fuenf))) == erwartet


def test_woche_loest_ebenso_aus():
    auftraege = _entscheiden(_messung(claude_f=10, claude_w=95))
    assert len(auftraege) == 1


def test_veraltete_claude_messung_entscheidet_nichts():
    assert _entscheiden(_messung(claude_stand=JETZT - timedelta(minutes=11))) == []
    assert len(_entscheiden(_messung(claude_stand=JETZT - timedelta(minutes=9)))) == 1


@pytest.mark.parametrize("kaputt", [
    dict(claude_fehler="keine Daten"),
    dict(claude_stand=None),
    dict(claude_zurueck=True),
    dict(claude_reset=JETZT - timedelta(minutes=1)),
])
def test_kaputte_claude_messung_entscheidet_nichts(kaputt):
    assert _entscheiden(_messung(**kaputt)) == []


@pytest.mark.parametrize("kaputt", [
    dict(codex_f=95),
    dict(codex_w=95),
    dict(codex_fehler="keine Daten"),
    dict(codex_stand=JETZT - timedelta(minutes=11)),
    dict(codex_stand=None),
    dict(codex_reset=JETZT - timedelta(minutes=1)),
])
def test_codex_nicht_gemessen_frei_entscheidet_nichts(kaputt):
    assert _entscheiden(_messung(**kaputt)) == []


@pytest.mark.parametrize("wert", [-5, 100.1, 150, float("nan"), float("inf")])
def test_ungueltige_codex_prozentwerte_entscheiden_nichts(wert):
    """Nur 0–100 ist gültig; negative/über 100/nicht endliche Werte gelten als unbekannt."""
    assert _entscheiden(_messung(codex_f=wert)) == []
    assert _entscheiden(_messung(codex_w=wert)) == []


def test_kennung_enthaelt_das_ausloesende_fenster():
    auftrag = _entscheiden(_messung(claude_f=95))[0]
    assert auftrag.id == f"engineering@{int(ENDE.timestamp())}"
    assert auftrag.lage == "2A"
    assert (auftrag.fuenf, auftrag.woche) == (95.0, 50.0)


@pytest.mark.parametrize("phase", ["sende", "gesendet", "unklar", "fehler", "bestaetigt", "entwertet"])
def test_dieselbe_kennung_wird_nie_erneut_gesendet(phase):
    kennung = f"engineering@{int(ENDE.timestamp())}"
    vorgang = vorgaenge.Vorgang(kennung, "engineering", "lauf-1", phase, JETZT.isoformat())
    assert _entscheiden(_messung(), vorgangsliste=[vorgang]) == []


def test_neues_limitfenster_ergibt_einen_neuen_vorgang():
    alt = vorgaenge.Vorgang(f"engineering@{int(ENDE.timestamp())}", "engineering", "lauf-1",
                            "gesendet", JETZT.isoformat())
    neu = _entscheiden(_messung(claude_reset=ENDE + timedelta(hours=5)), vorgangsliste=[alt])
    assert len(neu) == 1 and neu[0].id != alt.id


def test_inaktives_paar_wird_nie_gesendet():
    assert _entscheiden(_messung(), paare_liste=[_paar(aktiv=False)]) == []


def test_ein_auftrag_je_paar():
    auftraege = _entscheiden(_messung(), paare_liste=[_paar("engineering"), _paar("weiterbildung")])
    assert [a.thema for a in auftraege] == ["engineering", "weiterbildung"]


def test_faellige_filtert_hermes_modus_ohne_kunstauftrag():
    auftraege = automatik.faellige([_paar()], _messung(), SCHWELLE, True, [], JETZT,
                                   modus_mapping={"engineering": modi.HERMES_CODEX})
    assert auftraege == []


# --- Kopfzeile ----------------------------------------------------------------

def _laufend(repo, thema="engineering", bereit="ja", zeit=None, kurz=KURZ, erste=None):
    datei = repo / ".hermes" / "uebergabe" / "laufend" / f"{thema}.md"
    datei.parent.mkdir(parents=True, exist_ok=True)
    zeile = erste if erste is not None else \
        f"Übergabebereit: {bereit} · {(zeit or JETZT - timedelta(minutes=5)).isoformat()} · {kurz}"
    datei.write_text(zeile + "\n# Technischer Inhalt\n", encoding="utf-8")
    return datei


def test_kopfzeile_wird_gelesen(umgebung):
    _laufend(umgebung)
    bereit, zeit, kurz = automatik.kopfzeile_lesen(umgebung / ".hermes/uebergabe/laufend/engineering.md")
    assert bereit == "ja" and kurz == KURZ and zeit == JETZT - timedelta(minutes=5)


@pytest.mark.parametrize("erste", [
    "Übergabebereit: ja · kein-datum · abcdef1",          # keine ISO-Zeit
    "Übergabebereit ja · 2026-10-15T11:00:00+00:00 · abcdef1",   # Präfix kaputt
    "Übergabebereit: ja · 2026-10-15T11:00:00+00:00 · abc1",      # Kurzform zu kurz
    "Übergabebereit: ja · 2026-10-15T11:00:00+00:00 · zzzzzzz",   # keine Hexzeichen
    "",
])
def test_kaputte_kopfzeile_wird_nicht_akzeptiert(umgebung, erste):
    _laufend(umgebung, erste=erste)
    assert automatik.kopfzeile_lesen(umgebung / ".hermes/uebergabe/laufend/engineering.md") is None


def test_uebergabepunkt_akzeptiert_nur_ja_mit_passendem_head(umgebung):
    pfad = _laufend(umgebung)
    assert automatik.uebergabepunkt(pfad, FULL_HEAD, JETZT) == (True, "")


def test_uebergabepunkt_nein(umgebung):
    pfad = _laufend(umgebung, bereit="nein")
    assert automatik.uebergabepunkt(pfad, FULL_HEAD, JETZT) == (False, automatik.STATUS_UEBERGABEPUNKT)


@pytest.mark.parametrize("fall", ["fehlt", "kaputt", "alt", "fremder_commit"])
def test_uebergabepunkt_fail_closed(umgebung, fall):
    pfad = umgebung / ".hermes/uebergabe/laufend/engineering.md"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    if fall == "fehlt":
        pass
    elif fall == "kaputt":
        pfad.write_text("irgendwas\n", encoding="utf-8")
    elif fall == "alt":
        _laufend(umgebung, zeit=JETZT - timedelta(hours=3))
    else:
        _laufend(umgebung)
    head = "9999999999" + FULL_HEAD[10:] if fall == "fremder_commit" else FULL_HEAD
    assert automatik.uebergabepunkt(pfad, head, JETZT) == (False, automatik.STATUS_VERALTET)


def test_head_praefix_vergleich_exakt():
    assert automatik.head_passt("abcdef1", FULL_HEAD) is True
    assert automatik.head_passt("abcdef123456", FULL_HEAD) is True
    assert automatik.head_passt("ABCDEF1", FULL_HEAD) is True
    assert automatik.head_passt("abcdef1234567", FULL_HEAD) is False   # 13 Zeichen sind zu viele
    assert automatik.head_passt("abcdefg", FULL_HEAD) is False    # kein Hexzeichen
    assert automatik.head_passt("abcdef1", "") is False


# --- Ablauf -------------------------------------------------------------------

@pytest.fixture
def transport(monkeypatch):
    """Attrappe statt `codex.exe`; sammelt die Aufrufe."""
    aufrufe = []

    def setzen(verhalten):
        def t(liste, timeout):
            aufrufe.append(liste)
            if isinstance(verhalten, Exception):
                raise verhalten
            if callable(verhalten):
                return verhalten(liste)
            return verhalten
        monkeypatch.setattr(codex_senden, "_transport", t)
        return aufrufe

    return setzen


def _lauf(umgebung, *, paare_liste=None, messung=None, warte=None, head=FULL_HEAD, trocken=False,
          an=True, sender=None, vorgangsliste=None):
    return automatik.lauf(jetzt=JETZT, repo=umgebung, sender=sender, warte=warte or (lambda s: None),
                          head=head, git=_git, trocken=trocken, paare_liste=paare_liste or [_paar()],
                          messung=messung or _messung(), schwelle=SCHWELLE, an=an,
                          vorgangsliste=vorgangsliste, lauf_id="lauf-1")


def _master(umgebung, thema="engineering"):
    return besitz.lesen(besitz.pfad(umgebung, f".hermes/uebergabe/laufend/{thema}.md"))


def test_ohne_claude_aktivitaet_genau_ein_versand(umgebung, transport):
    aufrufe = transport(0)
    _laufend(umgebung)

    staende = _lauf(umgebung)

    assert [s.status for s in staende] == ["gesendet"]
    assert len(aufrufe) == 1
    assert _master(umgebung).startswith("codex ")
    assert vorgaenge.finden(f"engineering@{int(ENDE.timestamp())}").phase == "gesendet"

    # zweiter Lauf: dieselbe Kennung existiert schon -> kein zweiter Versand
    assert len(_lauf(umgebung)) == 1
    assert len(aufrufe) == 1


def test_automatik_aus_sendet_nichts(umgebung, transport):
    aufrufe = transport(0)
    _laufend(umgebung)
    staende = _lauf(umgebung, an=False)
    assert [s.status for s in staende] == [automatik.STATUS_AUS]
    assert aufrufe == []


def test_claude_setzt_nein_vor_der_reservierung(umgebung, transport):
    aufrufe = transport(0)
    _laufend(umgebung, bereit="nein")
    staende = _lauf(umgebung)
    assert staende[0].status == automatik.STATUS_UEBERGABEPUNKT
    assert aufrufe == [] and vorgaenge.lesen() == [] and _master(umgebung) == ""


def test_claude_setzt_nein_zwischen_reservierung_und_nachpruefung(umgebung, transport):
    aufrufe = transport(0)
    datei = _laufend(umgebung)

    def warte(sekunden):
        _laufend(umgebung, bereit="nein")

    staende = _lauf(umgebung, warte=warte)

    assert staende[0].status == automatik.STATUS_CLAUDE_HOERT
    assert aufrufe == [] and vorgaenge.lesen() == []
    assert _master(umgebung).startswith("claude ")     # Reservierung zurückgegeben
    assert datei.is_file()


def test_claude_sieht_waehrend_der_reservierung_reserviert(umgebung, transport):
    transport(0)
    _laufend(umgebung)
    gesehen = {}

    def warte(sekunden):
        assert sekunden == automatik.WARTE_SEKUNDEN
        gesehen["master"] = _master(umgebung)

    _lauf(umgebung, warte=warte)
    assert gesehen["master"].startswith("reserviert lauf-1 ")


def test_fremder_commit_nach_dem_uebergabepunkt_verhindert_den_versand(umgebung, transport):
    aufrufe = transport(0)
    _laufend(umgebung)
    staende = _lauf(umgebung, head="9999999999" + FULL_HEAD[10:])
    assert staende[0].status == automatik.STATUS_VERALTET
    assert aufrufe == [] and vorgaenge.lesen() == []


def test_commit_waehrend_der_wartezeit_verhindert_den_versand(umgebung, transport):
    """Der HEAD wird nach der Wartezeit **frisch** ermittelt – ein Commit währenddessen blockt."""
    aufrufe = transport(0)
    _laufend(umgebung)
    head = {"wert": FULL_HEAD}

    def warte(sekunden):
        assert sekunden == automatik.WARTE_SEKUNDEN
        head["wert"] = "1234567" + FULL_HEAD[7:]   # fremder Commit zwischen Reservierung und Versand

    staende = _lauf(umgebung, warte=warte, head=lambda: head["wert"])

    assert staende[0].status == automatik.STATUS_VERALTET
    assert aufrufe == [] and vorgaenge.lesen() == []
    assert _master(umgebung).startswith("claude ") and "reserviert" not in _master(umgebung)


def test_gleicher_head_nach_der_wartezeit_sendet(umgebung, transport):
    """Gegenprobe: eine HEAD-Funktion ist erlaubt und blockt nicht, wenn sich nichts ändert."""
    aufrufe = transport(0)
    _laufend(umgebung)
    staende = _lauf(umgebung, head=lambda: FULL_HEAD)
    assert [s.status for s in staende] == ["gesendet"]
    assert len(aufrufe) == 1


def test_verwaiste_reservierung_ohne_vorgang_wird_wiederaufgenommen(umgebung, transport):
    aufrufe = transport(0)
    _laufend(umgebung)
    master = besitz.pfad(umgebung, ".hermes/uebergabe/laufend/engineering.md")
    besitz.schreiben(master, f"reserviert alt-lauf {JETZT.isoformat()}")

    staende = _lauf(umgebung)

    assert staende[0].status == "gesendet"
    assert _master(umgebung).startswith("codex ")
    assert len(aufrufe) == 1


def test_reservierungsaufloesung_ist_ein_vergleich_und_setzen(umgebung):
    _laufend(umgebung)
    master = besitz.pfad(umgebung, ".hermes/uebergabe/laufend/engineering.md")
    besitz.schreiben(master, "reserviert alt-lauf 2026-10-15T11:00:00+00:00")

    assert automatik._reservierung_aufloesen(master, JETZT) == \
        f"claude {JETZT.isoformat()} wiederaufnahme alt-lauf"

    # fremde Markierung wird nie angefasst
    besitz.schreiben(master, "codex fremd@1 2026-10-15T11:00:00+00:00")
    assert automatik._reservierung_aufloesen(master, JETZT) == "codex fremd@1 2026-10-15T11:00:00+00:00"


def test_reservierungsaufloesung_mit_vorzustand_codex_stellt_exakt_her(umgebung):
    """v0.3.2: `… vorzustand codex <alte-id>` wird exakt wiederhergestellt (spätes ACK bleibt möglich)."""
    _laufend(umgebung)
    master = besitz.pfad(umgebung, ".hermes/uebergabe/laufend/engineering.md")
    besitz.schreiben(master,
                     f"reserviert rueckgabe-engineering-20261016040000-ab12 {JETZT.isoformat()} "
                     "vorzustand codex alt@1 2026-10-15T10:00:00+00:00")

    assert automatik._reservierung_aufloesen(master, JETZT) == "codex alt@1 2026-10-15T10:00:00+00:00"


def test_reservierungsaufloesung_mit_vorzustand_claude_bleibt_wiederaufnahme(umgebung):
    _laufend(umgebung)
    master = besitz.pfad(umgebung, ".hermes/uebergabe/laufend/engineering.md")
    besitz.schreiben(master,
                     f"reserviert rueckgabe-engineering-20261016040000-ab12 {JETZT.isoformat()} "
                     "vorzustand claude 2026-10-15T09:00:00+00:00")

    assert automatik._reservierung_aufloesen(master, JETZT) == "claude 2026-10-15T09:00:00+00:00"


def test_reservierung_mit_vorhandenem_vorgang_wird_nicht_freigegeben(umgebung, transport):
    aufrufe = transport(0)
    _laufend(umgebung)
    besitz.schreiben(besitz.pfad(umgebung, ".hermes/uebergabe/laufend/engineering.md"),
                     f"reserviert alt-lauf {JETZT.isoformat()}")
    vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang("engineering@1", "engineering", "alt-lauf",
                                                           "sende", JETZT.isoformat())])

    staende = _lauf(umgebung)

    assert staende[0].status == automatik.STATUS_RESERVIERT
    assert aufrufe == []
    assert _master(umgebung).startswith("reserviert alt-lauf")


def test_belegte_themensperre_ueberspringt_das_thema(umgebung, transport):
    aufrufe = transport(0)
    _laufend(umgebung)
    with zustand.thema_sperre("engineering") as frei:
        assert frei is True
        staende = _lauf(umgebung)

    assert "Sperre belegt" in staende[0].status
    assert aufrufe == [] and vorgaenge.lesen() == []


def test_ersetzte_reservierung_verhindert_den_versand(umgebung, transport):
    aufrufe = transport(0)
    _laufend(umgebung)
    master = besitz.pfad(umgebung, ".hermes/uebergabe/laufend/engineering.md")

    def warte(sekunden):
        besitz.schreiben(master, f"reserviert fremd {JETZT.isoformat()}")

    staende = _lauf(umgebung, warte=warte)

    assert staende[0].status == "Reservierung ersetzt – kein Versand"
    assert aufrufe == [] and vorgaenge.lesen() == []


def test_trockenlauf_sendet_nicht(umgebung, transport):
    aufrufe = transport(0)
    _laufend(umgebung)
    staende = _lauf(umgebung, trocken=True)
    assert staende[0].status == "bereit (trocken)" and staende[0].phase.startswith("engineering@")
    assert aufrufe == [] and _master(umgebung) == ""


def test_absturz_nach_sende_ergibt_keinen_zweiten_versand(umgebung, transport, monkeypatch):
    aufrufe = transport(0)
    _laufend(umgebung)
    echt = codex_senden.uebergabe.paket_bauen

    def platzt(*a, **k):
        raise RuntimeError("Absturz im Paketbau")

    monkeypatch.setattr(codex_senden.uebergabe, "paket_bauen", platzt)
    staende = _lauf(umgebung)

    assert staende[0].phase == "sende"
    assert vorgaenge.finden(f"engineering@{int(ENDE.timestamp())}").phase == "sende"
    assert aufrufe == []

    monkeypatch.setattr(codex_senden.uebergabe, "paket_bauen", echt)
    assert len(_lauf(umgebung)) == 1
    assert aufrufe == []   # auch der zweite Lauf sendet nicht: die Kennung steht auf der Platte


def test_codex_im_master_bleibt_unangetastet(umgebung, transport):
    aufrufe = transport(0)
    _laufend(umgebung)
    besitz.schreiben(besitz.pfad(umgebung, ".hermes/uebergabe/laufend/engineering.md"),
                     f"codex fremd@1 {JETZT.isoformat()}")
    staende = _lauf(umgebung)
    assert staende[0].status == automatik.STATUS_CODEX_MASTER
    assert aufrufe == []


def test_hermes_besitz_stoppt_automatik_vor_kopfzeilenlesen(umgebung, transport, monkeypatch):
    paar = _paar()
    paare.setzen(paar.thema, paar.codex_thread, paar.laufend, aktiv=True)
    master = besitz.pfad(umgebung, paar.laufend)
    besitz.schreiben(master, besitz.zeile(besitz.HERMES, JETZT.isoformat(), "bestehend"))
    auftrag = _entscheiden(_messung())[0]
    monkeypatch.setattr(automatik, "uebergabepunkt",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("Handoff wurde gelesen")))

    aufrufe = transport(0)
    stand = automatik._ein_thema(auftrag, repo=umgebung, jetzt=JETZT, warte=lambda _: None,
                                 head_lesen=lambda: FULL_HEAD, sender=codex_senden.senden, git=_git, frist=1)

    assert stand.status == "Hermes führt – Codex nur Ausführer"
    assert aufrufe == []


# --- Bestätigung --------------------------------------------------------------

def _rollout(thread=THREAD, text=None):
    import json
    ordner = signale.codex_ordner() / "2026" / "10" / "15"
    ordner.mkdir(parents=True, exist_ok=True)
    zeile = {"timestamp": (JETZT + timedelta(minutes=1)).isoformat(), "type": "response_item",
             "payload": {"type": "message", "role": "assistant",
                         "content": [{"text": text or f"ACK engineering@{int(ENDE.timestamp())}"}]}}
    with (ordner / f"rollout-x-{thread}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(zeile) + "\n")


def _gesendeten_vorgang(umgebung):
    auftrag = Auftrag("engineering", "lauf-1", f"engineering@{int(ENDE.timestamp())}", THREAD,
                      ".hermes/uebergabe/laufend/engineering.md",
                      ".hermes/uebergabe/laufend/engineering.master", 95.0, 50.0, ENDE, "2A")
    besitz.schreiben(besitz.pfad(umgebung, auftrag.laufend),
                     besitz.zeile("codex", auftrag.id, JETZT.isoformat()))
    vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang(auftrag.id, "engineering", "lauf-1",
                                                           "gesendet", JETZT.isoformat())])
    return auftrag


def test_ack_bestaetigt_und_setzt_den_master_auf_codex(umgebung):
    auftrag = _gesendeten_vorgang(umgebung)
    _rollout()
    ergebnisse = automatik.bestaetigungen_pruefen(JETZT, repo=umgebung, paare_liste=[_paar()])
    assert [e.status for e in ergebnisse] == ["bestätigt"]
    assert vorgaenge.finden(auftrag.id).phase == "bestaetigt"
    assert zustand.lesen().master == "codex"
    # der Besitz bleibt bei Codex – die Bestätigung gibt ihn nicht zurück
    assert besitz.lesen(besitz.pfad(umgebung, auftrag.laufend)).startswith(f"codex {auftrag.id} ")


def test_ohne_ack_keine_bestaetigung(umgebung):
    auftrag = _gesendeten_vorgang(umgebung)
    assert automatik.bestaetigungen_pruefen(JETZT, repo=umgebung, paare_liste=[_paar()]) == []
    assert vorgaenge.finden(auftrag.id).phase == "gesendet"
    assert zustand.lesen().master is None


def test_ack_nach_rueckwechsel_bleibt_ohne_wirkung(umgebung):
    auftrag = _gesendeten_vorgang(umgebung)
    _rollout()
    besitz.schreiben(besitz.pfad(umgebung, auftrag.laufend),
                     besitz.zeile("claude", JETZT.isoformat(), "entwertet", auftrag.id))
    vorgaenge.aendern(lambda alt: [vorgaenge.Vorgang(v.id, v.thema, v.lauf_id, "entwertet", v.zeit)
                                   for v in alt])
    assert automatik.bestaetigungen_pruefen(JETZT, repo=umgebung, paare_liste=[_paar()]) == []
    assert vorgaenge.finden(auftrag.id).phase == "entwertet"
    assert zustand.lesen().master is None


def test_verspaetetes_ack_bei_hermes_modus_wird_vor_rollout_scan_ignoriert(umgebung, monkeypatch):
    paar = _paar()
    paare.setzen(paar.thema, paar.codex_thread, paar.laufend, aktiv=True)
    modi.setzen("engineering", modi.HERMES_CODEX, repo=umgebung)
    auftrag = _gesendeten_vorgang(umgebung)
    aufrufe = []
    monkeypatch.setattr(automatik.ack, "pruefen", lambda *a, **k: aufrufe.append(a) or True)

    staende = automatik.bestaetigungen_pruefen(JETZT, repo=umgebung, paare_liste=[_paar()])

    assert aufrufe == []
    assert staende[0].phase == "entwertet"
    assert vorgaenge.finden(auftrag.id).phase == "gesendet"


def test_status_zeile_zeigt_alle_zustaende():
    thema = "engineering"
    for phase, erwartet in (("bestaetigt", "bestätigt"), ("fehler", "Fehler"),
                            ("unklar", "unklar"), ("sende", "unklar"), ("entwertet", "bereit")):
        liste = [vorgaenge.Vorgang("x@1", thema, "l", phase, JETZT.isoformat())]
        assert automatik.status_zeile(_paar(), liste, JETZT) == erwartet
    assert automatik.status_zeile(_paar(), [], JETZT) == "bereit"

    gesendet = [vorgaenge.Vorgang("x@1", thema, "l", "gesendet", JETZT.isoformat())]
    assert automatik.status_zeile(_paar(), gesendet, JETZT).startswith("gesendet ")
    alt = [vorgaenge.Vorgang("x@1", thema, "l", "gesendet",
                             (JETZT - timedelta(minutes=20)).isoformat())]
    assert automatik.status_zeile(_paar(), alt, JETZT) == "keine Bestätigung"


def test_menue_zeigt_unklare_zustellung():
    liste = [vorgaenge.Vorgang("x@1", "engineering", "l", "unklar", JETZT.isoformat())]
    assert automatik.STATUS_UNKLAR in automatik.menue_zeilen([_paar()], liste, JETZT)


def test_reservierung_ist_keine_gueltige_codex_besitzmarkierung(umgebung):
    """Eine Reservierung zählt für ein ACK nicht als Übernahme durch Codex."""
    auftrag = Auftrag("engineering", "lauf-1", f"engineering@{int(ENDE.timestamp())}", THREAD,
                      ".hermes/uebergabe/laufend/engineering.md",
                      ".hermes/uebergabe/laufend/engineering.master", 95.0, 50.0, ENDE, "2A")
    besitz.schreiben(besitz.pfad(umgebung, auftrag.laufend),
                     f"reserviert lauf-1 {JETZT.isoformat()}")
    vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang(auftrag.id, "engineering", "lauf-1",
                                                           "gesendet", JETZT.isoformat())])
    _rollout()
    assert automatik.bestaetigungen_pruefen(JETZT, repo=umgebung, paare_liste=[_paar()]) == []
    assert vorgaenge.finden(auftrag.id).phase == "gesendet"
    assert zustand.lesen().master is None


def test_ohne_aufloesbares_repo_keine_bestaetigung(umgebung, monkeypatch):
    """Fail-closed: läßt sich der Besitz nicht prüfen, wird nicht bestätigt."""
    auftrag = _gesendeten_vorgang(umgebung)
    _rollout()

    def kaputt():
        raise uebergabe.UebergabeFehler("Repo nicht gefunden")

    monkeypatch.setattr(automatik.uebergabe, "repo_wurzel", kaputt)

    assert automatik.bestaetigungen_pruefen(JETZT, paare_liste=[_paar()]) == []
    assert vorgaenge.finden(auftrag.id).phase == "gesendet"
    assert zustand.lesen().master is None


def _rueckwechsel_nach_der_ack_pruefung(monkeypatch):
    """Rückwechsel genau zwischen ACK-Prüfung und Bestätigung erzwingen."""
    echt = automatik.ack.pruefen

    def pruefen_und_wechseln(*a, **k):
        treffer = echt(*a, **k)
        if treffer:
            wechsel.wechseln("claude", jetzt=JETZT)
        return treffer

    monkeypatch.setattr(automatik.ack, "pruefen", pruefen_und_wechseln)


def test_rueckwechsel_zwischen_pruefung_und_bestaetigung_bleibt_entwertet(umgebung, monkeypatch):
    """Der Besitz ist bereits zurückgegeben – die Bestätigung muss fail-closed abbrechen."""
    paare.setzen("engineering", THREAD, paare.laufend_bilden("engineering"), aktiv=True)
    auftrag = _gesendeten_vorgang(umgebung)
    _rollout()
    _rueckwechsel_nach_der_ack_pruefung(monkeypatch)

    ergebnisse = automatik.bestaetigungen_pruefen(JETZT, repo=umgebung, paare_liste=[_paar()])

    assert ergebnisse == []
    assert vorgaenge.finden(auftrag.id).phase == "entwertet"
    assert zustand.lesen().master != "codex"


def test_bestaetigung_schreibt_nur_bei_phase_gesendet_oder_unklar(umgebung, monkeypatch):
    """Auch ohne Besitzwechsel: die Phase wird unter der Sperre erneut geprüft (atomar)."""
    auftrag = _gesendeten_vorgang(umgebung)
    _rollout()

    # Der Rückwechsel findet kein Paar in paare.json und faßt die Besitzdatei nicht an –
    # die Marke bleibt „codex <id>", nur die Phase wird entwertet.
    _rueckwechsel_nach_der_ack_pruefung(monkeypatch)

    ergebnisse = automatik.bestaetigungen_pruefen(JETZT, repo=umgebung, paare_liste=[_paar()])

    assert ergebnisse == []
    assert vorgaenge.finden(auftrag.id).phase == "entwertet"
    assert besitz.lesen(besitz.pfad(umgebung, ".hermes/uebergabe/laufend/engineering.md")).startswith("codex ")
    assert zustand.lesen().master != "codex"


def test_master_wird_im_gesperrten_abschnitt_gesetzt(umgebung, monkeypatch):
    """Der globale Master darf nur geschrieben werden, während die Themensperre gehalten wird."""
    _gesendeten_vorgang(umgebung)
    _rollout()
    frei_waehrend_master = {}
    echt = automatik._master_codex

    def spion():
        with zustand.thema_sperre("engineering") as frei:
            frei_waehrend_master["frei"] = frei
        echt()

    monkeypatch.setattr(automatik, "_master_codex", spion)

    assert [e.status for e in automatik.bestaetigungen_pruefen(JETZT, repo=umgebung,
                                                               paare_liste=[_paar()])] == ["bestätigt"]
    assert frei_waehrend_master["frei"] is False
    assert zustand.lesen().master == "codex"


def test_rueckwechsel_waehrend_des_bestaetigungsabschnitts_kommt_nicht_durch(umgebung, monkeypatch):
    """Ein Rückwechsel prallt an der Themensperre ab und bleibt danach der letzte Wille."""
    paare.setzen("engineering", THREAD, paare.laufend_bilden("engineering"), aktiv=True)
    auftrag = _gesendeten_vorgang(umgebung)
    _rollout()

    sperre_gehalten = threading.Event()
    versuch_gemacht = threading.Event()
    ergebnis: dict[str, wechsel.Ergebnis] = {}
    frei_waehrend_master = {}
    echt = automatik._master_codex

    def spion():
        with zustand.thema_sperre("engineering") as frei:
            frei_waehrend_master["frei"] = frei
        sperre_gehalten.set()
        assert versuch_gemacht.wait(timeout=15)   # der Rückwechsel-Thread läuft jetzt
        echt()

    monkeypatch.setattr(automatik, "_master_codex", spion)

    def rueckwechsel():
        assert sperre_gehalten.wait(timeout=15)
        ergebnis["waehrend"] = wechsel.wechseln("claude", jetzt=JETZT, themen_frist=0.3)
        versuch_gemacht.set()

    faden = threading.Thread(target=rueckwechsel)
    faden.start()
    try:
        staende = automatik.bestaetigungen_pruefen(JETZT, repo=umgebung, paare_liste=[_paar()])
    finally:
        faden.join(timeout=15)

    assert [s.status for s in staende] == ["bestätigt"]
    # während der Sperre kommt der Rückwechsel nicht durch
    assert ergebnis["waehrend"].art == "fehler"
    assert ergebnis["waehrend"].meldung == wechsel.MELDUNG_SPERRE
    assert frei_waehrend_master["frei"] is False
    assert zustand.lesen().master == "codex"   # die Bestätigung war vollständig

    # danach läuft derselbe Rückwechsel durch und bleibt der letzte Wille
    assert wechsel.wechseln("claude", jetzt=JETZT).art == "gewechselt"
    assert zustand.lesen().master == "claude"
    assert besitz.lesen(besitz.pfad(umgebung, auftrag.laufend)).startswith("claude ")
    assert vorgaenge.finden(auftrag.id).phase == "bestaetigt"   # bestätigt bleibt bestätigt


def test_claude_im_limit_mit_ruhendem_5h_fenster():
    jetzt = datetime(2026, 10, 16, 8, 0, tzinfo=timezone.utc)
    claude = signale.Kontingent("Claude",
                                (signale.Fenster("5h", 0.0, None),
                                 signale.Fenster("Woche", 100.0, jetzt + timedelta(hours=60))),
                                stand=jetzt - timedelta(minutes=2))
    im_limit, ausloeser = automatik._claude_im_limit(claude, 97, jetzt)
    assert im_limit and ausloeser is not None and ausloeser.name == "Woche"


def test_claude_im_limit_ruhendes_fenster_allein_loest_nicht_aus():
    jetzt = datetime(2026, 10, 16, 8, 0, tzinfo=timezone.utc)
    claude = signale.Kontingent("Claude",
                                (signale.Fenster("5h", 0.0, None),
                                 signale.Fenster("Woche", 30.0, jetzt + timedelta(hours=60))),
                                stand=jetzt - timedelta(minutes=2))
    assert automatik._claude_im_limit(claude, 97, jetzt) == (False, None)


# --- F2: Masterübergabe und Worker-Vorgabe sind getrennte Vorgänge (Paket B) ---

@pytest.mark.parametrize("worker,modell", [("claude", None), ("codex", None),
                                           ("hermes", modi.HERMES_MODELL)])
def test_workerauswahl_unterbindet_keine_codex_masteruebergabe(umgebung, transport, worker, modell):
    """master=kontingent mit jedem expliziten Workerprovider erhält die zulässige Codex-Masterübergabe."""
    aufrufe = transport(0)
    paar = _paar()
    paare.setzen(paar.thema, paar.codex_thread, paar.laufend, aktiv=True)
    modi.worker_setzen("engineering", worker, repo=umgebung)
    _laufend(umgebung)
    profil_vorher = modi.datei().read_bytes()

    staende = _lauf(umgebung)

    assert [s.status for s in staende] == ["gesendet"]
    assert len(aufrufe) == 1
    assert aufrufe[0][1] == "queue"                       # genau der Mastertransport – kein Workerstart
    assert modi.profil("engineering") == modi.Profil("kontingent", worker, modell)
    assert modi.datei().read_bytes() == profil_vorher     # Workerkonfiguration unverändert


@pytest.mark.parametrize("master", ["claude", "codex", "hermes"])
def test_fester_master_erhaelt_weiterhin_keinen_mastertransport(umgebung, transport, master):
    aufrufe = transport(0)
    paar = _paar()
    paare.setzen(paar.thema, paar.codex_thread, paar.laufend, aktiv=True)
    modi.master_setzen("engineering", master, repo=umgebung)
    _laufend(umgebung)

    staende = _lauf(umgebung)

    assert aufrufe == [] and vorgaenge.lesen() == []
    assert staende[0].status == "kein fälliges Paar"
    assert modi.geschuetzt("engineering", repo=umgebung)


@pytest.mark.parametrize("master,name", [("claude", "Claude"), ("codex", "Codex"), ("hermes", "Hermes")])
def test_feste_masterrolle_stoppt_vor_dem_handoff_lesen(umgebung, transport, monkeypatch, master, name):
    paar = _paar()
    paare.setzen(paar.thema, paar.codex_thread, paar.laufend, aktiv=True)
    modi.master_setzen("engineering", master, repo=umgebung)
    auftrag = _entscheiden(_messung())[0]
    monkeypatch.setattr(automatik, "uebergabepunkt",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("Handoff wurde gelesen")))
    aufrufe = transport(0)

    stand = automatik._ein_thema(auftrag, repo=umgebung, jetzt=JETZT, warte=lambda _: None,
                                 head_lesen=lambda: FULL_HEAD, sender=codex_senden.senden,
                                 git=_git, frist=1)

    assert stand.status == f"{name} führt – Codex nur Ausführer"
    assert aufrufe == []


@pytest.mark.parametrize("master,name", [("claude", "Claude"), ("codex", "Codex"), ("hermes", "Hermes")])
def test_feste_masterrolle_entwertet_spaete_acks(umgebung, monkeypatch, master, name):
    paar = _paar()
    paare.setzen(paar.thema, paar.codex_thread, paar.laufend, aktiv=True)
    modi.master_setzen("engineering", master, repo=umgebung)
    auftrag = _gesendeten_vorgang(umgebung)
    _rollout()
    ack_aufrufe = []
    monkeypatch.setattr(automatik.ack, "pruefen", lambda *a, **k: ack_aufrufe.append(a) or True)

    staende = automatik.bestaetigungen_pruefen(JETZT, repo=umgebung, paare_liste=[_paar()])

    assert ack_aufrufe == []
    assert staende[0].status == f"{name} führt – später ACK ignoriert"
    assert staende[0].phase == "entwertet"
    assert vorgaenge.finden(auftrag.id).phase == "gesendet"   # fail-closed: nichts bestätigt


# --- F2 Punkt 2: eigene Modus-Zwischenmarke vor jeder Deutung stoppen ----------

def test_aufloeser_laesst_eigene_zwischenmarke_bytegleich(umgebung):
    _laufend(umgebung)
    master = besitz.pfad(umgebung, ".hermes/uebergabe/laufend/engineering.md")
    marke = modi.zwischenmarke("engineering", "hermes", JETZT.isoformat())
    besitz.schreiben(master, marke)

    assert automatik._reservierung_aufloesen(master, JETZT, thema="engineering") == marke
    assert besitz.lesen(master) == marke                      # bytegleich, kein wiederaufnahme
    assert automatik._reservierung_aufloesen(master, JETZT) == marke   # Thema aus dem Dateinamen
    assert besitz.lesen(master) == marke


def test_fremdmarke_mit_falschem_thema_bleibt_normale_reservierung(umgebung):
    """Nur die eigene Marke mit *gleichem* Thema ist geschützt; sonst gilt die bisherige Behandlung."""
    _laufend(umgebung)
    master = besitz.pfad(umgebung, ".hermes/uebergabe/laufend/engineering.md")
    fremd = f"reserviert modus anderes-thema hermes {JETZT.isoformat()}"
    besitz.schreiben(master, fremd)

    assert automatik._reservierung_aufloesen(master, JETZT) == \
        f"claude {JETZT.isoformat()} wiederaufnahme modus"


def test_automatik_stoppt_an_eigener_zwischenmarke_ohne_versand(umgebung, transport, monkeypatch):
    aufrufe = transport(0)
    paar = _paar()
    paare.setzen(paar.thema, paar.codex_thread, paar.laufend, aktiv=True)
    _laufend(umgebung)
    master = besitz.pfad(umgebung, paar.laufend)
    marke = modi.zwischenmarke("engineering", "codex", JETZT.isoformat())
    besitz.schreiben(master, marke)
    monkeypatch.setattr(automatik, "kopfzeile_lesen",
                        lambda *_: (_ for _ in ()).throw(AssertionError("Handoff wurde gelesen")))

    staende = _lauf(umgebung)

    assert aufrufe == [] and vorgaenge.lesen() == []
    assert staende[0].status == "Modusumschaltung führt – Codex nur Ausführer"
    assert besitz.lesen(master) == marke                      # bytegleich
    assert "wiederaufnahme" not in besitz.lesen(master)
    assert "Reservierung" not in besitz.lesen(master)
