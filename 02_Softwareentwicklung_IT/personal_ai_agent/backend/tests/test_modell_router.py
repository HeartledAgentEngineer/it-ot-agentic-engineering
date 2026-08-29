"""Tests für den Modell-Router (Kategorie-Erkennung & Modell-Wahl)."""
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services.modell_router import (  # noqa: E402
    ALLTAG,
    BILDER,
    CODING,
    EMOTIONAL,
    ERINNERUNG,
    KOMPLEX,
    MODELL_CODING,
    MODELL_FLASH,
    MODELL_PRO,
    MODELL_VISION,
    SCHNELL,
    erkenne_kategorie,
    ist_vision_faehig,
    modell_fuer,
)


# --- Positivbeispiele: jede Kategorie wird erkannt ---------------------------

@pytest.mark.parametrize("frage", [
    "Ich bin heute traurig und brauche Zuspruch.",
    "Wie können wir unsere Beziehung verbessern?",
])
def test_erkenne_kategorie_emotional(frage):
    """Sätze über Gefühle/Beziehung/Familie landen in 'emotional'."""
    assert erkenne_kategorie(frage) == EMOTIONAL


@pytest.mark.parametrize("frage", [
    "Was können wir am Wochenende kochen?",
    "Hilf mir, den Urlaub zu planen.",
])
def test_erkenne_kategorie_alltag(frage):
    """Kochen/Urlaub/Planen landet in 'alltag'."""
    assert erkenne_kategorie(frage) == ALLTAG


@pytest.mark.parametrize("frage", [
    "Schau dir diesen Screenshot an und beschreibe ihn.",
    "Was siehst du auf dem Foto?",
])
def test_erkenne_kategorie_bilder(frage):
    """Bild-/Foto-/Screenshot-Fragen landen in 'bilder'."""
    assert erkenne_kategorie(frage) == BILDER


@pytest.mark.parametrize("frage", [
    "Was haben wir letztes Jahr gemacht?",
    "Erinnerst du dich an unseren Urlaub in Italien?",
])
def test_erkenne_kategorie_erinnerung(frage):
    """Rückblicke/Vergangenheit landen in 'erinnerung'."""
    assert erkenne_kategorie(frage) == ERINNERUNG


@pytest.mark.parametrize("frage", [
    "Kannst du diesen Code debuggen?",
    "Schreib mir ein Skript, das Dateien sortiert.",
])
def test_erkenne_kategorie_coding(frage):
    """Programmier-/Debug-Fragen landen in 'coding'."""
    assert erkenne_kategorie(frage) == CODING


@pytest.mark.parametrize("frage", [
    "Analysiere die Strategie umfassend.",
    "Berechne das detailliert mit allen Zwischenschritten.",
])
def test_erkenne_kategorie_komplex(frage):
    """Komplexe Analysen/Mathematik landen in 'komplex'."""
    assert erkenne_kategorie(frage) == KOMPLEX


@pytest.mark.parametrize("frage", [
    "Wie spät ist es?",
    "Danke, das reicht.",
])
def test_erkenne_kategorie_schnell_fallback(frage):
    """Fragen ohne Signalwörter fallen auf 'schnell' zurück."""
    assert erkenne_kategorie(frage) == SCHNELL


def test_erkenne_kategorie_leere_eingabe():
    """Leere Eingaben sind kein Fehler und fallen auf 'schnell' zurück."""
    assert erkenne_kategorie("") == SCHNELL


def test_erkenne_kategorie_ignoriert_gross_kleinschreibung():
    """Die Erkennung ist unabhängig von Groß-/Kleinschreibung."""
    assert erkenne_kategorie("KANNST DU DIESEN CODE DEBUGGEN?") == CODING


def test_erkenne_kategorie_bilder_vor_alltag():
    """'Foto von unserem Urlaub' ist eine Bildfrage, keine Alltagsfrage."""
    assert erkenne_kategorie("Analysiere das Foto von unserem Urlaub.") == BILDER


def test_erkenne_kategorie_erinnerung_vor_alltag():
    """'Erinnerst du dich an den Urlaub' ist Erinnerung, nicht Alltag."""
    assert erkenne_kategorie("Erinnerst du dich an unseren Urlaub?") == ERINNERUNG


# --- Negativbeispiele: fremde Themen bleiben außen vor -----------------------

@pytest.mark.parametrize("frage", [
    "Wann fährt der nächste Bus ab?",
])
def test_erkenne_kategorie_nicht_emotional(frage):
    """Sachliche Alltagsfragen sind keine Gefühlsfragen."""
    assert erkenne_kategorie(frage) != EMOTIONAL


@pytest.mark.parametrize("frage", [
    "Wie funktioniert ein Elektromotor?",
])
def test_erkenne_kategorie_nicht_alltag(frage):
    """Technische Fragen sind keine Alltagsfragen."""
    assert erkenne_kategorie(frage) != ALLTAG


@pytest.mark.parametrize("frage", [
    "Was ist die Hauptstadt von Frankreich?",
])
def test_erkenne_kategorie_nicht_bilder(frage):
    """Wissensfragen ohne Bildbezug sind keine Bildfragen."""
    assert erkenne_kategorie(frage) != BILDER


@pytest.mark.parametrize("frage", [
    "Wie wird das Wetter morgen?",
])
def test_erkenne_kategorie_nicht_erinnerung(frage):
    """Zukunfts-/Wetterfragen sind keine Erinnerungsfragen."""
    assert erkenne_kategorie(frage) != ERINNERUNG


@pytest.mark.parametrize("frage", [
    "Soll ich die Blumen gießen?",
])
def test_erkenne_kategorie_nicht_coding(frage):
    """Alltägliche Aufgaben ohne Code-Bezug sind kein Coding."""
    assert erkenne_kategorie(frage) != CODING


@pytest.mark.parametrize("frage", [
    "Wie spät ist es?",
])
def test_erkenne_kategorie_nicht_komplex(frage):
    """Kurze Sachfragen sind keine komplexen Aufgaben."""
    assert erkenne_kategorie(frage) != KOMPLEX


# --- Modell-Wahl pro Kategorie ------------------------------------------------

@pytest.mark.parametrize("kategorie,erwartet", [
    (EMOTIONAL, MODELL_FLASH),
    (ALLTAG, MODELL_FLASH),
    (BILDER, MODELL_VISION),
    (ERINNERUNG, MODELL_FLASH),
    (CODING, MODELL_CODING),
    (KOMPLEX, MODELL_PRO),
    (SCHNELL, MODELL_FLASH),
    ("", MODELL_FLASH),          # leere Kategorie -> Standard
    ("unbekannt", MODELL_FLASH),  # unbekannte Kategorie -> Standard
])
def test_modell_fuer_empfehlung(kategorie, erwartet):
    """Jede Kategorie bekommt das günstigste passende Modell."""
    assert modell_fuer(kategorie) == erwartet


# --- Nutzer-Modell-Wahl gewinnt ------------------------------------------------

@pytest.mark.parametrize("kategorie,gewaehlt", [
    (KOMPLEX, "openai/gpt-5"),
    (CODING, "deepseek/deepseek-v4-flash-0731"),
    (EMOTIONAL, "anthropic/claude-sonnet-5"),
    (ALLTAG, "openai/gpt-4o-mini"),
])
def test_modell_fuer_nutzerwahl_gewinnt(kategorie, gewaehlt):
    """Ein gesetztes Nutzer-Modell wird immer respektiert."""
    assert modell_fuer(kategorie, gewaehlt) == gewaehlt


def test_modell_fuer_nutzerwahl_mit_leerzeichen():
    """Umgebungs-Leerzeichen in der Nutzerwahl werden gestrippt."""
    assert modell_fuer(ALLTAG, "  openai/gpt-5  ") == "openai/gpt-5"


# --- Vision-Override bei Bildfragen -------------------------------------------

def test_modell_fuer_bilder_ueberschreibt_ohne_vision():
    """Nicht-vision-fähiges Nutzer-Modell wird bei Bildern überschrieben."""
    assert modell_fuer(BILDER, "deepseek/deepseek-v4-flash-0731") == MODELL_VISION


@pytest.mark.parametrize("gewaehlt", [
    "google/gemini-2.5-flash",
    "openai/gpt-4o-mini",
    "openai/gpt-5",
    "anthropic/claude-sonnet-5",
])
def test_modell_fuer_bilder_behaelt_vision_faehige_wahl(gewaehlt):
    """Vision-fähige Nutzer-Modelle bleiben bei Bildfragen erhalten."""
    assert modell_fuer(BILDER, gewaehlt) == gewaehlt


def test_modell_fuer_bilder_vision_check_case_insensitive():
    """Der Vision-Check ignoriert Groß-/Kleinschreibung."""
    assert modell_fuer(BILDER, "OpenAI/GPT-4O-MINI") == "OpenAI/GPT-4O-MINI"


# --- Vision-Fähigkeits-Check ----------------------------------------------------

@pytest.mark.parametrize("modell", [
    "google/gemini-2.5-flash",
    "openai/gpt-4o-mini",
    "openai/gpt-5",
    "anthropic/claude-sonnet-5",
])
def test_ist_vision_faehig_true(modell):
    """Gemini, GPT-4o, GPT-5 und Claude/Sonnet können Bilder sehen."""
    assert ist_vision_faehig(modell) is True


@pytest.mark.parametrize("modell", [
    "deepseek/deepseek-v4-flash-0731",
    "deepseek/deepseek-v4-pro",
])
def test_ist_vision_faehig_false(modell):
    """DeepSeek-Modelle sind reine Textmodelle (kein Vision)."""
    assert ist_vision_faehig(modell) is False