"""Tests: Zitattag in Ortszeit statt UTC-Tag (Chat-Archive).

Anlass (Sebastian, 16.10.2026, To-do-Liste „Ältere offene Punkte": „Datum
(UTC-Tag, 8,7 % betroffen)"): die Belegstellen nannten den **UTC-Tag** des
Abschnitts. Wer abends oder nach Mitternacht Ortszeit geschrieben hat, sah im
Zitat den Vortag.

Am echten Index gemessen (18.10.2026, nur lesend, 447 MB):
52.679 Abschnitte haben einen lesbaren ``beginn``; **3.230 (6,13 %)** liegen auf
einem anderen Orts- als UTC-Tag — ausschliesslich in den UTC-Stunden 22 und 23.
Je Quelle: claude-code 14,5 %, chatgpt 9,6 %, gemini 8,4 %, claude-ai 5,8 %,
whatsapp 1,6 %, google-kalender 0 %. Die in der To-do-Liste genannten „8,7 %"
und „34 %" liessen sich **nicht** reproduzieren (die 42,2 % mehrtaegigen
WhatsApp-Abschnitte entsprechen der Messung vom 10.10.2026).

Zeitzone: Europe/Berlin, gerechnet mit der EU-Sommerzeit-Regel — ohne
``zoneinfo``/``tzdata`` (im Backend nicht installiert) und ohne
``astimezone()`` (scheitert auf Windows an Daten vor 1970; der Index enthaelt
Google-Kalender-Eintraege ab 1940). Damit ist das Ergebnis auf jedem Rechner
und in den Tests dasselbe.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.services.archiv_service import (  # noqa: E402
    ortstag,
    ortszeit_versatz,
    zeitraum_kurz,
)
from app.services.archiv_suche import _datum_kurz  # noqa: E402


# ── Der Versatz (Sommer-/Winterzeit) ───────────────────────────────────────

@pytest.mark.parametrize("zeit,erwartet", [
    (datetime(2026, 6, 12, 12, 0), 2),    # Sommer
    (datetime(2026, 1, 12, 12, 0), 1),    # Winter
    (datetime(2026, 3, 28, 23, 30), 1),   # Tag vor der Umstellung
    (datetime(2026, 3, 29, 0, 30), 1),    # Umstellung 29.03. um 01:00 UTC
    (datetime(2026, 3, 29, 1, 30), 2),
    (datetime(2026, 10, 25, 0, 30), 2),   # Rueckstellung 25.10. um 01:00 UTC
    (datetime(2026, 10, 25, 1, 30), 1),
])
def test_ortszeit_versatz_an_den_umstellungen(zeit, erwartet):
    assert ortszeit_versatz(zeit) == erwartet


# ── Der Tag selbst ─────────────────────────────────────────────────────────

def test_gespraech_nach_mitternacht_bekommt_den_ortstag():
    """Der Kern: 22:30 UTC ist in Hamburg 00:30 des FOLGENDEN Tages."""
    assert ortstag("2026-06-12T22:30:00+00:00") == "2026-06-13"


def test_mittagsstempel_bleibt_am_selben_tag():
    assert ortstag("2026-06-12T12:00:00+00:00") == "2026-06-12"
    assert ortstag("2026-01-12T12:00:00+00:00") == "2026-01-12"


def test_winterzeit_verschiebt_erst_ab_23_uhr_utc():
    assert ortstag("2026-01-12T22:30:00+00:00") == "2026-01-12"
    assert ortstag("2026-01-12T23:30:00+00:00") == "2026-01-13"


def test_umstellungstage_liegen_richtig():
    assert ortstag("2026-03-28T23:30:00+00:00") == "2026-03-29"   # +1 h
    assert ortstag("2026-10-25T23:30:00+00:00") == "2026-10-26"   # +1 h, nach 01:00 UTC
    assert ortstag("2026-10-25T22:30:00+00:00") == "2026-10-25"   # +1 h, noch am selben Tag


def test_daten_vor_1970_werfen_nicht():
    """Der Index enthaelt Google-Kalender-Eintraege ab 1940 (kein `astimezone`)."""
    assert ortstag("1940-09-04T00:00:00+00:00") == "1940-09-04"
    assert ortstag("1965-08-16T23:30:00+00:00") == "1965-08-17"


def test_unlesbare_werte_geben_leer_zurueck_statt_zu_werfen():
    assert ortstag("") == ""
    assert ortstag(None) == ""
    assert ortstag("   ") == ""
    assert ortstag("kein datum") == "kein datum"[:10]
    assert _datum_kurz(None) is None


def test_stempel_ohne_zeitzone_gilt_als_utc():
    """Aeltere Aufrufer und Attrappen tragen oft kein `+00:00` — Verhalten wie vorher."""
    assert ortstag("2026-03-12T10:00:00") == "2026-03-12"


# ── Die beiden Zitat-Wege nennen dasselbe ──────────────────────────────────

def test_zeitraum_kurz_nennt_den_ortstag_der_spanne():
    """Beide Enden der Spanne werden umgerechnet — der letzte Tag rutscht mit."""
    assert zeitraum_kurz("2026-02-11T21:19:51+00:00", "2026-06-13T23:54:23+00:00") == \
        "2026-02-11–2026-06-14"


def test_zeitraum_kurz_gleicher_tag_bleibt_ein_datum():
    assert zeitraum_kurz("2026-03-12T10:00:00+00:00", "2026-03-12T10:04:00+00:00") == "2026-03-12"


def test_zeitraum_kurz_ohne_ende_bleibt_beim_einzeldatum():
    assert zeitraum_kurz("2026-03-12T10:00:00", None) == "2026-03-12"
    assert zeitraum_kurz("", None) == ""
    assert zeitraum_kurz(None, None) == ""


def test_beide_zitat_wege_stimmen_ueberein():
    """Zwei Umsetzungen (Dienst und Suchmodul) duerfen nicht auseinanderlaufen."""
    faelle = [
        ("2026-06-12T22:30:00+00:00", "2026-06-12T22:31:00+00:00"),
        ("2026-06-12T22:30:00+00:00", "2026-06-13T23:54:23+00:00"),
        ("2026-01-12T23:30:00+00:00", None),
        ("1940-09-04T00:00:00+00:00", None),
    ]
    for beginn, ende in faelle:
        assert zeitraum_kurz(beginn, ende) == _datum_kurz(beginn, ende), (beginn, ende)


# ── Verdrahtung: die Wege, die Sebastian liest ─────────────────────────────

def test_chat_notiz_nennt_den_ortstag():
    from app.router.chat import _archiv_tool

    class _FakeArchiv:
        is_available = True

        def hybrid(self, frage, top_k=None):
            return [{"text": "Spaete Antwort.", "source": "claude-code",
                     "beginn": "2026-06-13T23:54:23+00:00",
                     "ende": "2026-06-13T23:54:23+00:00",
                     "title": "Nightshift", "conversation_id": "c9"}]

    ausgabe = _archiv_tool("Was weisst du ueber die Nightshift aus dem Archiv?",
                           service=_FakeArchiv())
    assert "[claude-code, 2026-06-14]" in ausgabe


def test_system_prompt_nennt_den_ortstag():
    from app.services.llm_service import LLMService

    text = LLMService._build_archiv_context([
        {"text": "Spaete Antwort.", "source": "chatgpt",
         "beginn": "2026-06-12T22:30:00+00:00", "ende": "2026-06-12T22:31:00+00:00",
         "title": "Nightshift"},
    ])
    assert "[chatgpt, 2026-06-13]" in text
