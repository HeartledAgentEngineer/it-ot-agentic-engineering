"""Tests für die Kontext-Aufteilung im Prompt (Antwort-Relevanz).

Befund 30.09.2026 (Sebastian): „der vergisst irgendwie, kriegt die letzte
Nachricht nicht mehr in Kontext." Ursache im Code: `_kontext_aufteilen` machte
nur die LETZTE Nutzerfrage primär; die vorherige Antwort landete als gedimmter
Hintergrund und wurde dort auf `_HINTERGRUND_LAENGE` (400) Zeichen gekürzt.
Rückfragen („und was davor?") hatten die letzte Runde also nicht mehr.

Diese Tests halten den neuen Stand fest:
  1. Die letzten ZWEI Runden (Frage + Antwort) sind primär und ungekürzt.
  2. Alles davor bleibt gedimmt und gekürzt (Kostenbremse bleibt).
  3. Die laufende Frage steht nicht doppelt im Prompt (sie liegt schon im
     Verlauf, den `chat.py` sofort mitschreibt).

Offline-Tests: keine Netz-Calls, keine Datei-Zugriffe.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.llm_service import (  # noqa: E402
    _HINTERGRUND_LAENGE,
    _ohne_doppelte_frage,
    _kontext_aufteilen,
)

LANG = "X" * (_HINTERGRUND_LAENGE + 250)


def test_rueckfrage_erhaelt_letzte_runde_ungekuerzt():
    """Der Kern des Befunds: die vorherige Antwort kommt vollständig an."""
    hist = [
        {"role": "user", "content": "Was war am 18. Juni 2022?"},
        {"role": "assistant", "content": LANG},
        {"role": "user", "content": "und was war davor?"},
    ]

    primaer, aelterer = _kontext_aufteilen(hist)

    assert [m["content"] for m in primaer] == [hist[0]["content"], LANG, hist[2]["content"]]
    assert len(primaer[1]["content"]) == len(LANG), "Antwort darf nicht gekürzt sein"
    assert aelterer == ""


def test_zwei_runden_primaer_der_rest_gedimmt():
    hist = [
        {"role": "user", "content": "erste Frage"},
        {"role": "assistant", "content": "erste Antwort"},
        {"role": "user", "content": "zweite Frage"},
        {"role": "assistant", "content": "zweite Antwort"},
        {"role": "user", "content": "dritte Frage"},
        {"role": "assistant", "content": "dritte Antwort"},
    ]

    primaer, aelterer = _kontext_aufteilen(hist)

    assert [m["content"] for m in primaer] == [
        "zweite Frage",
        "zweite Antwort",
        "dritte Frage",
        "dritte Antwort",
    ]
    assert "erste Frage" in aelterer and "erste Antwort" in aelterer
    assert "zweite Frage" not in aelterer


def test_hintergrund_bleibt_gekuerzt():
    hist = [
        {"role": "user", "content": "alt"},
        {"role": "assistant", "content": LANG},
        {"role": "user", "content": "neu"},
        {"role": "assistant", "content": "jung"},
        {"role": "user", "content": "laufend"},
    ]

    _, aelterer = _kontext_aufteilen(hist)

    assert LANG[:40] in aelterer
    assert "…" in aelterer, "Hintergrund muss weiter gekürzt werden"
    assert LANG not in aelterer


def test_ohne_nutzerfrage_bleibt_alles_primaer():
    hist = [
        {"role": "assistant", "content": "nur Antwort"},
        {"role": "system", "content": "Hinweis"},
    ]

    primaer, aelterer = _kontext_aufteilen(hist)

    assert primaer == hist
    assert aelterer == ""


def test_leere_history():
    assert _kontext_aufteilen([]) == ([], "")


def test_laufende_frage_nicht_doppelt():
    hist = [
        {"role": "user", "content": "erste Frage"},
        {"role": "assistant", "content": "erste Antwort"},
        {"role": "user", "content": "laufende Frage"},
    ]
    primaer, _ = _kontext_aufteilen(hist)

    gefiltert = _ohne_doppelte_frage(primaer, "laufende Frage")

    assert [m["content"] for m in gefiltert] == ["erste Frage", "erste Antwort"]
    assert len(gefiltert) == len(primaer) - 1


def test_doppelte_frage_mit_umgebungsleerraum_wird_erkannt():
    hist = [
        {"role": "user", "content": "  laufende Frage  "},
    ]
    primaer, _ = _kontext_aufteilen(hist)

    assert _ohne_doppelte_frage(primaer, "laufende Frage") == []


def test_ungleiche_frage_bleibt_stehen():
    hist = [
        {"role": "user", "content": "eine andere Frage"},
    ]
    primaer, _ = _kontext_aufteilen(hist)

    assert _ohne_doppelte_frage(primaer, "laufende Frage") == primaer


def test_ohne_frage_text_aendert_sich_nichts():
    primaer = [{"role": "user", "content": "Text"}]

    assert _ohne_doppelte_frage(primaer, "") == primaer
    assert _ohne_doppelte_frage([], "Frage") == []
    assert _ohne_doppelte_frage([{"role": "assistant", "content": "A"}], "Frage") == [
        {"role": "assistant", "content": "A"}
    ]
