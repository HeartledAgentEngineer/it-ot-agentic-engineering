"""Tests für das versionierte Goal- und Fortschritts-Datenmodell (`ziele.py`) und `uebergabe.py`."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from master_schalter import paare, uebergabe, ziele
from master_schalter.ziele import Goal, ZielFehler, ZielKonfliktFehler

THEMA = "orbitdesk"


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    daten = tmp_path / "daten"
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    paare.setzen(THEMA, "019a2de5-bb88-71d2-8522-91ba62a9f4b2", paare.laufend_bilden(THEMA), aktiv=True)
    return repo


def test_goal_erstellung_und_serialisierung():
    g = Goal(
        thema=THEMA,
        revision=1,
        aktualisiert=datetime.now(timezone.utc).isoformat(),
        titel="OrbitDesk Ausbau",
        zieltext="Ausbau des Master-Schalters zu OrbitDesk.",
        abnahmekriterien=["Chat-Wecken reparieren", "Goal-Tracking integrieren"],
        entscheidungen=["Verbindungsrefresh bei agy_senden"],
        offene_aufgaben=["MCP Server anbinden"],
        belegter_fortschritt=["Schritt 1 abgeschlossen"],
        naechster_schritt="Schritt 2 Goal Modell",
        gewuenschte_besetzung={"thinker": "claude", "worker": "codex"},
        tatsaechliche_zustaendigkeit={"master": "agy"},
        laufende_arbeit="Tests schreiben",
        wartegrung=None,
    )
    d = g.als_dict()
    assert d["thema"] == THEMA
    assert d["revision"] == 1
    assert len(d["abnahmekriterien"]) == 2

    wiederhergestellt = Goal.aus_dict(d)
    assert wiederhergestellt.thema == THEMA
    assert wiederhergestellt.abnahmekriterien == ["Chat-Wecken reparieren", "Goal-Tracking integrieren"]
    assert wiederhergestellt.entscheidungen == ["Verbindungsrefresh bei agy_senden"]


def test_goal_speichern_und_lesen(umgebung):
    g = ziele.goal_anlegen_oder_aktualisieren(
        THEMA,
        titel="OrbitDesk Leitwarte",
        zieltext="Steuerung aller Coding-Agenten.",
        abnahmekriterien=["Kriterium 1", "Kriterium 2"],
        naechster_schritt="MCP Anbindung",
    )
    assert g.revision == 1
    assert g.titel == "OrbitDesk Leitwarte"

    gelesen = ziele.goal_lesen(THEMA)
    assert gelesen is not None
    assert gelesen.thema == THEMA
    assert gelesen.revision == 1
    assert gelesen.abnahmekriterien == ["Kriterium 1", "Kriterium 2"]
    assert gelesen.naechster_schritt == "MCP Anbindung"


def test_goal_revision_inkrement(umgebung):
    g1 = ziele.goal_anlegen_oder_aktualisieren(THEMA, titel="Titel 1", zieltext="Text 1")
    assert g1.revision == 1

    g2 = ziele.goal_anlegen_oder_aktualisieren(THEMA, titel="Titel 2", zieltext="Text 2")
    assert g2.revision == 2
    assert g2.titel == "Titel 2"


def test_goal_revisionskonflikt(umgebung):
    g1 = ziele.goal_anlegen_oder_aktualisieren(THEMA, titel="Titel 1", zieltext="Text 1")
    assert g1.revision == 1

    # Aktualisierung mit falscher erwarteter Revision schlägt fehl
    with pytest.raises(ZielKonfliktFehler):
        ziele.goal_anlegen_oder_aktualisieren(
            THEMA, titel="Titel Konflikt", zieltext="Text", erwartete_revision=99
        )


def test_zustellung_und_annahme_getrennt_belegen(umgebung):
    g = ziele.goal_anlegen_oder_aktualisieren(THEMA, titel="Titel", zieltext="Text")
    vorgang_id = "v-20261106-1234"

    # 1. Zustellung belegen (delivered)
    g_zustellung = ziele.zustellung_belegen(THEMA, vorgang_id, empfaenger="agy")
    assert g_zustellung.zustellungs_nachweis is not None
    assert g_zustellung.zustellungs_nachweis["vorgang_id"] == vorgang_id
    assert g_zustellung.zustellungs_nachweis["empfaenger"] == "agy"
    assert g_zustellung.annahme_ack is None  # Noch nicht angenommen!
    assert "Wartet auf Übernahme-ACK" in (g_zustellung.wartegrung or "")

    # 2. Annahme quittieren (accepted / ACK)
    g_annahme = ziele.annahme_quittieren(THEMA, vorgang_id, agent="agy")
    assert g_annahme.zustellungs_nachweis is not None
    assert g_annahme.annahme_ack is not None
    assert g_annahme.annahme_ack["vorgang_id"] == vorgang_id
    assert g_annahme.annahme_ack["quittiert_von"] == "agy"
    assert g_annahme.wartegrung is None  # Nicht mehr wartend!
    assert g_annahme.tatsaechliche_zustaendigkeit["master"] == "agy"


def test_uebergabepaket_enthaelt_goal(umgebung):
    # Goal vorbereiten
    g = ziele.goal_anlegen_oder_aktualisieren(
        THEMA,
        titel="OrbitDesk Mission",
        zieltext="Verlässliche Steuerzentrale",
        abnahmekriterien=["Kriterium Alpha", "Kriterium Beta"],
        belegter_fortschritt=["Fortschritt 1 erreicht"],
        naechster_schritt="Schritt 3 Kostenkontrolle",
    )

    # Übergabepaket mit Thema bauen
    def dummy_git(repo, args):
        if "rev-parse" in args:
            return "abcd123"
        if "rev-list" in args:
            return "42"
        return ""

    paket_pfad = uebergabe.paket_bauen(
        "codex", "agy", "Hinweistext Test",
        repo=umgebung, git=dummy_git, plaene=False, minimal=True, thema=THEMA
    )

    assert paket_pfad.is_file()
    text = paket_pfad.read_text(encoding="utf-8")
    assert "## Goal & Fortschritt" in text
    assert "OrbitDesk Mission" in text
    assert "Kriterium Alpha" in text
    assert "Fortschritt 1 erreicht" in text
    assert "Schritt 3 Kostenkontrolle" in text
