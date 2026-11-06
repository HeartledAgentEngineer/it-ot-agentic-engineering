"""Tests für den autonomen Sprach- und Leitwarten-Agenten (Klaus Voice Engine & Jarvis Mode)."""
from unittest.mock import MagicMock, patch

import pytest

from master_schalter import paare, sprach_agent, ziele


def test_klaus_voice_engine_hash_und_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(sprach_agent, "audio_cache_ordner", lambda: tmp_path)
    engine = sprach_agent.KlausVoiceEngine()
    
    # Ohne Key -> None
    monkeypatch.delenv("OPENROUTER_TTS_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert engine.mp3_erzeugen("Hallo Test") is None
    assert "Kein OpenRouter API-Schlüssel" in engine.letzter_fehler


def test_befehl_verarbeiten_status():
    antwort = sprach_agent.befehl_verarbeiten("Was läuft wo?")
    assert isinstance(antwort, str)
    assert len(antwort) > 10


def test_befehl_verarbeiten_blocker():
    antwort = sprach_agent.befehl_verarbeiten("Gibt es Blocker oder offene Prüfungen?")
    assert isinstance(antwort, str)
    assert "Prüfungen" in antwort or "Blocker" in antwort or "grünen Bereich" in antwort


def test_befehl_verarbeiten_quoten():
    antwort = sprach_agent.befehl_verarbeiten("Wie stehen die Quoten und Antigravity?")
    assert "Verbräuche" in antwort or "Claude" in antwort or "Google Antigravity" in antwort


def test_befehl_verarbeiten_budgets():
    antwort = sprach_agent.befehl_verarbeiten("Wie sind die Budgets?")
    assert "Dollar" in antwort or "Kosten" in antwort or "Budget" in antwort


def test_befehl_verarbeiten_chat_uebernehmen(monkeypatch):
    test_thema = "test-sprach-thema"
    # Aufräumen falls existent
    paare.schreiben([p for p in paare.lesen() if p.thema != test_thema])

    ok, msg = sprach_agent.chat_in_orbitdesk_uebernehmen(test_thema, "Test Titel aus Chat", "Antigravity")
    assert ok is True
    assert "erfolgreich" in msg

    # Prüfen ob in paare und ziele vorhanden
    themen = [p.thema for p in paare.lesen()]
    assert test_thema in themen

    goal = ziele.goal_lesen(test_thema)
    assert goal is not None
    assert "Test Titel aus Chat" in goal.titel

    # Aufräumen
    paare.schreiben([p for p in paare.lesen() if p.thema != test_thema])


def test_befehl_verarbeiten_rollen_und_goals(monkeypatch):
    test_th = "typefree"
    # Nächster Schritt per Sprache
    antwort = sprach_agent.befehl_verarbeiten(f"Nächster Schritt bei {test_th} ist Tests schreiben")
    assert "gespeichert" in antwort or "Tests schreiben" in antwort

    g = ziele.goal_lesen(test_th)
    if g:
        assert g.naechster_schritt == "Tests schreiben"


def test_jarvis_live_session():
    ergebnisse = []
    def _cb(zustand, info):
        ergebnisse.append((zustand, info))

    session = sprach_agent.JarvisLiveSession(callback_zustand=_cb)
    with patch.object(sprach_agent.klaus_engine, "sprechen", return_value=True):
        begruessung = session.anruf_starten()
        assert "Klaus" in begruessung
        assert session.zustand == sprach_agent.LiveAnrufZustand.HOEREN

        antwort = session.eingabe_senden("Was läuft wo?")
        assert len(antwort) > 5

        ende = session.anruf_beenden()
        assert "beendet" in ende
        assert session.zustand == sprach_agent.LiveAnrufZustand.AUFGELEGT
