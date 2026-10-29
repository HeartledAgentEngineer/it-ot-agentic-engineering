"""Tests für `agy_senden`, `agy_automatik` und die Entwurfs-Übernahme mit `agy`."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from master_schalter import (agy_automatik, agy_senden, anzeige, assistent_vorgaenge as av, automatik,
                             besitz, chat_zuordnung, modi, paare, postfach, pruefer_wahl, signale)
from master_schalter import uebersicht_modell as um
from master_schalter.uebersicht_entwurf import EntwurfsVerwaltung, EntwurfFehler

JETZT = datetime(2026, 10, 29, 15, 0, tzinfo=timezone.utc)
ENDE_CODEX = JETZT + timedelta(hours=3)
ENDE_CLAUDE = JETZT + timedelta(days=3)
THREAD_A = "019a2de5-bb88-71d2-8522-91ba62a9f4b2"
THREAD_B = "019a061c-10ee-7252-a98c-28706e7de957"
NEUER_AGY_A = "aaaaaaaa-1111-4111-8111-111111111111"
NEUER_AGY_B = "bbbbbbbb-2222-4222-8222-222222222222"


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    monkeypatch.setenv("MASTER_SCHALTER_CODEX_SESSIONS", str(tmp_path / "codex"))
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    return repo


def _messung(*, codex_5h: float = 96.0, codex_woche: float = 74.0,
             claude_woche: float = 100.0, claude_stand: datetime | None = None) -> automatik.Messung:
    claude = signale.Kontingent(
        "Claude",
        (
            signale.Fenster("5h", 0.0, None),
            signale.Fenster("Woche", claude_woche, ENDE_CLAUDE),
        ),
        stand=claude_stand or (JETZT - timedelta(hours=20)),
    )
    codex = signale.Kontingent(
        "Codex",
        (
            signale.Fenster("5h", codex_5h, ENDE_CODEX),
            signale.Fenster("Woche", codex_woche, ENDE_CODEX + timedelta(days=4)),
        ),
        stand=JETZT - timedelta(minutes=1),
    )
    return automatik.Messung(claude, codex)


def _codex_thema_anlegen(repo, thema: str, thread: str, *, master_profil: str = "codex", aktiv: bool = True) -> None:
    laufend = paare.laufend_bilden(thema)
    paare.setzen(thema, thread, laufend, aktiv=aktiv)
    pfad = repo / laufend
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text("Übergabebereit: nein · 2026-10-16T08:00:00+00:00 · 1234567\n# Stand\n", encoding="utf-8")
    modi.master_setzen(thema, master_profil, repo=repo)
    besitz.schreiben(besitz.pfad(repo, laufend), f"codex {JETZT.isoformat()} assistent {thema} alt-1")


# --- agy_senden -------------------------------------------------------------------------

def test_umgebung_merken_und_lesen_speichert_nur_erlaubte_schluessel(umgebung, tmp_path):
    datei = tmp_path / "agy-server.json"
    exe = tmp_path / "language_server.exe"
    exe.write_text("stub", encoding="utf-8")
    env = {
        "ANTIGRAVITY_AGENTAPI_EXE": str(exe),
        "ANTIGRAVITY_LS_ADDRESS": "127.0.0.1:4295",
        "ANTIGRAVITY_CSRF_TOKEN": "token-123",
        "ANTIGRAVITY_PROJECT_ID": "proj-1",
        "UNBEKANNT": "geheim",
    }
    assert agy_senden.umgebung_merken(env, datei) is True
    gelesen = agy_senden.umgebung_lesen(datei)
    assert gelesen["ANTIGRAVITY_LS_ADDRESS"] == "127.0.0.1:4295"
    assert gelesen["ANTIGRAVITY_CSRF_TOKEN"] == "token-123"
    assert "UNBEKANNT" not in gelesen


def test_neues_gespraech_und_nachricht_senden_ueber_attrappe(umgebung):
    aufrufe: list[list[str]] = []

    def lauf(befehl: list[str], env: dict[str, str], timeout: int) -> tuple[int, str]:
        aufrufe.append(befehl)
        if "new-conversation" in befehl:
            return 0, json.dumps({"response": {"conversationId": NEUER_AGY_A}})
        return 0, "{}"

    kennung = agy_senden.neues_gespraech("personal-ai-agent", ".hermes/uebergabe/laufend/personal-ai-agent.md",
                                         lauf=lauf)
    assert kennung == NEUER_AGY_A
    assert "--title=Thema: personal-ai-agent" in aufrufe[0]

    erg = agy_senden.nachricht_senden(NEUER_AGY_A, "Übernahme bereit", titel="Master-Schalter", lauf=lauf)
    assert erg == "ok"
    assert aufrufe[1][:3] == ["agentapi", "send-message", "--title"]


# --- agy_automatik ----------------------------------------------------------------------

def test_codex_limit_uebergibt_alle_aktiven_codex_themen_und_legt_neue_agy_chats_an(umgebung):
    _codex_thema_anlegen(umgebung, "personal-ai-agent", THREAD_A, master_profil="codex", aktiv=True)
    _codex_thema_anlegen(umgebung, "typefree", THREAD_B, master_profil="kontingent", aktiv=True)
    anzeige.automatik_setzen(True)

    angelegt: list[str] = []
    karten = {"personal-ai-agent": NEUER_AGY_A, "typefree": NEUER_AGY_B}

    def chat_anlegen(thema: str, laufend: str) -> str | None:
        angelegt.append(thema)
        return karten[thema]

    staende = agy_automatik.lauf(
        JETZT,
        repo=umgebung,
        messung=_messung(codex_5h=95.0),
        schwelle=95,
        an=True,
        chat_anlegen=chat_anlegen,
    )

    assert [s.thema for s in staende] == ["personal-ai-agent", "typefree"]
    assert all(s.phase == "im_postfach" for s in staende)
    assert angelegt == ["personal-ai-agent", "typefree"]

    # Zuordnung in zuordnung.json hinterlegt
    zuordnung = chat_zuordnung.zuordnung_lesen()
    assert zuordnung[f"agy:{NEUER_AGY_A}"] == "personal-ai-agent"
    assert zuordnung[f"agy:{NEUER_AGY_B}"] == "typefree"

    # Besitz und Profil stehen auf agy, Nachrichten liegen im Postfach
    for thema, chat_id in karten.items():
        marke = besitz.lesen(besitz.pfad(umgebung, paare.laufend_bilden(thema)))
        assert besitz.besitzer(marke) == "agy"
        assert modi.profil(thema).master == "agy"
        nachrichten = postfach.abholen("agy", chat_id, repo=umgebung)
        assert len(nachrichten) == 1
        assert thema in nachrichten[0].text

    # Zweiter Lauf im selben Limitfenster löst nichts erneut aus
    zweiter = agy_automatik.lauf(
        JETZT,
        repo=umgebung,
        messung=_messung(codex_5h=98.0),
        schwelle=95,
        an=True,
        chat_anlegen=chat_anlegen,
    )
    assert zweiter == []
    assert len(angelegt) == 2


def test_vorhandener_agy_chat_wird_wiederverwendet_ohne_neuanlage(umgebung):
    _codex_thema_anlegen(umgebung, "personal-ai-agent", THREAD_A, master_profil="codex", aktiv=True)
    chat_zuordnung.bestaetigen("agy", NEUER_AGY_A, "personal-ai-agent")

    def darf_nicht_anlegen(*_a):
        raise AssertionError("Chat existiert bereits in zuordnung.json")

    staende = agy_automatik.lauf(
        JETZT,
        repo=umgebung,
        messung=_messung(codex_5h=95.0),
        schwelle=95,
        an=True,
        chat_anlegen=darf_nicht_anlegen,
    )
    assert len(staende) == 1
    assert staende[0].thema == "personal-ai-agent"
    assert staende[0].phase == "im_postfach"


def test_fehlgeschlagene_chat_anlage_vermerkt_ausloeser_nicht_und_erlaubt_wiederholung(umgebung):
    _codex_thema_anlegen(umgebung, "personal-ai-agent", THREAD_A, master_profil="codex", aktiv=True)

    staende = agy_automatik.lauf(
        JETZT,
        repo=umgebung,
        messung=_messung(codex_5h=95.0),
        schwelle=95,
        an=True,
        chat_anlegen=lambda *_: None,
    )
    assert len(staende) == 1 and staende[0].phase == "fehler"
    assert automatik.ausgeloest_lesen() == frozenset()

    # Beim nächsten Takt klappt die Anlage -> Übergabe läuft durch
    staende_2 = agy_automatik.lauf(
        JETZT,
        repo=umgebung,
        messung=_messung(codex_5h=95.0),
        schwelle=95,
        an=True,
        chat_anlegen=lambda *_: NEUER_AGY_A,
    )
    assert len(staende_2) == 1 and staende_2[0].phase == "im_postfach"


# --- Entwurf & Modellliste für agy ------------------------------------------------------

def test_agy_ausfuehrer_nutzt_standardmodell_und_entwurf_uebernehmen_speichert(umgebung):
    _codex_thema_anlegen(umgebung, "personal-ai-agent", THREAD_A, master_profil="kontingent", aktiv=True)
    zeile = um.ThemaZeile(
        thema="personal-ai-agent",
        master="nach Kontingent",
        besitz="codex",
        pruefer="Automatisch",
        ausfuehrer="Claude",
        auto="An",
        master_wert="kontingent",
        worker_wert="claude",
        pruefer_wert="automatisch",
        paar_aktiv=True,
        modell_wert="claude-a",
    )
    snap = um.Uebersicht(
        zeit="15:00", lage="3", lage_text="Lage 3", automatik=True, schwelle=95,
        abos=(), themen=(zeile,), wartet=(), sitzungen=(), hinweise=(), repo=umgebung,
        schreiben=True, schreib_hinweis="",
        kataloge=(um.KatalogAnsicht("claude", True, (("claude-a", "Claude A"),)),),
        wechsel_themen=(), wechsel_pruefbar=True,
    )
    verwaltung = EntwurfsVerwaltung(snap)
    verwaltung.waehlen("personal-ai-agent", "ausfuehrer", "agy")
    verwaltung.waehlen("personal-ai-agent", "pruefer", "hermes")
    assert verwaltung.zeile("personal-ai-agent").worker_wert == "agy"
    assert verwaltung.zeile("personal-ai-agent").modell_wert is None

    ml = um.modell_liste(verwaltung.zeile("personal-ai-agent"), snap.kataloge)
    assert ml.gesperrt is True and ml.aktuell == um.STANDARD_MODELL

    with pytest.raises(EntwurfFehler, match="Antigravity verwendet den Standard"):
        verwaltung.waehlen("personal-ai-agent", "modell", "claude-a")

    zurueckgesetzt: list[str] = []
    aktion = um.entwurf_uebernehmen_aktion(snap, verwaltung.aenderungen(), nach_thema=zurueckgesetzt.append)
    ergebnis = aktion.ausfuehren()
    assert ergebnis.ok is True
    assert zurueckgesetzt == ["personal-ai-agent"]
    assert modi.profil("personal-ai-agent") == modi.Profil("kontingent", "agy", None)
    assert pruefer_wahl.wahl("personal-ai-agent") == "hermes"
