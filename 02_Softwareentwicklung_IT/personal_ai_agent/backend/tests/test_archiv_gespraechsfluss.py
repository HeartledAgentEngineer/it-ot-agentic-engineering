"""Tests: Gesprächsfluss aus dem Archiv (Antwort-Weg, nicht Index).

Anlass (Sebastian, 10.10.2026): „Kein Gesprächsfluss — die Verweise wirken wie
Striche/Stichpunkte statt wie Rede."

Gemessene Ursache: die Anweisungen im Antwort-Weg sagten selbst „Zitiere dem
Nutzer die Fundstellen … mit Quelle und Datum" und lieferten die Stellen als
Aufzählung — im Werkzeug-Weg sogar mit einem wörtlichen „- " vor jeder Zeile.
Das Modell schrieb die Liste ab. Diese Tests halten fest, dass jetzt EINE
gemeinsame Anweisung (``ARCHIV_FLUSS_ANWEISUNG``) an allen vier Anzeigewegen
steht und der Strich im Werkzeug-Weg weg ist.

Die Tests bauen sich ihre Fake-Dienste selbst; das echte Archiv wird nie
geöffnet oder verändert.
"""

from __future__ import annotations

import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.services.archiv_suche import (  # noqa: E402
    ARCHIV_FLUSS_ANWEISUNG,
    erwaehnungs_text,
)


# ── Die gemeinsame Anweisung ──────────────────────────────────────────────

def test_anweisung_verlangt_fluss_und_keine_strichliste():
    assert "im Fluss" in ARCHIV_FLUSS_ANWEISUNG
    assert "keine Strichliste" in ARCHIV_FLUSS_ANWEISUNG
    # Quelle und Datum bleiben verlangt — nur eben im Satz, nicht als Liste.
    assert "Quelle" in ARCHIV_FLUSS_ANWEISUNG
    assert "Datum" in ARCHIV_FLUSS_ANWEISUNG


# ── Weg 1: Chat-Notiz (router.chat._archiv_tool) ──────────────────────────

class _FakeArchiv:
    is_available = True

    def hybrid(self, frage, top_k=None):
        return [{
            "text": "Die EasyBank hat die Ueberweisung abgelehnt.",
            "source": "chatgpt",
            "beginn": "2026-03-12T10:00:00+00:00",
            "ende": "2026-03-12T10:04:00+00:00",
            "title": "EasyBank",
            "conversation_id": "c1",
        }]


def test_chat_notiz_traegt_die_fluss_anweisung():
    from app.router.chat import _archiv_tool

    ausgabe = _archiv_tool("Was weiss ich ueber EasyBank aus dem Archiv?",
                           service=_FakeArchiv())
    assert ARCHIV_FLUSS_ANWEISUNG in ausgabe
    # Der Beleg-Zeiger (Quelle + Datum) bleibt erhalten.
    assert "[chatgpt, 2026-03-12]" in ausgabe
    # Die alte Aufzählungs-Anweisung ist weg.
    assert "Zitiere dem Nutzer die relevanten Stellen" not in ausgabe


# ── Weg 2: System-Prompt (llm_service._build_archiv_context) ──────────────

def test_prompt_baustein_traegt_die_fluss_anweisung():
    from app.services.llm_service import LLMService

    text = LLMService._build_archiv_context([{
        "text": "Antwort: Der Sprachchef-Teil laeuft wieder.",
        "source": "claude-ai",
        "beginn": "2026-02-11T21:19:51+00:00",
        "ende": "2026-06-13T23:54:23+00:00",
        "title": "TwinCAT Projekt",
    }])
    assert "im Fluss" in text
    assert "keine Strichliste" in text
    # Der Anker bleibt, damit der Prompt weiterhin auffindbar ist.
    assert "AUS DEINEN FRÜHEREN GESPRÄCHEN" in text
    assert "[claude-ai, 2026-02-11–2026-06-13]" in text


# ── Weg 3: Erwähnungs-Notiz (archiv_suche.erwaehnungs_text) ───────────────

def test_erwaehnungs_text_traegt_die_fluss_anweisung():
    text = erwaehnungs_text({
        "name": "Erwin",
        "anzahl": 1,
        "je_quelle": {"whatsapp": 1},
        "eigene_chats": 1,
        "nur_erwaehnungen": False,
        "treffer": [{
            "quelle": "whatsapp", "datum": "2026-03-12",
            "titel": "WhatsApp mit Erwin", "text": "Wir haben telefoniert.",
        }],
    })
    assert ARCHIV_FLUSS_ANWEISUNG in text
    assert "[whatsapp, 2026-03-12]" in text


# ── Weg 4: Modell-Werkzeug (werkzeuge._archiv_suchen) ─────────────────────

def test_werkzeug_archiv_suchen_ohne_strich_und_mit_fluss(monkeypatch):
    # Rueckfall-Weg: voller Index fehlt, der alte Dienst traegt.
    from app.services import archiv_service as modul
    from app.services import archiv_suche as suche_modul
    from app.services import werkzeuge as wz

    class FakeArchiv:
        is_available = True

        def hybrid(self, frage, top_k=None):
            return [{"source": "ChatGPT", "beginn": "2024-03-01T10:00",
                     "text": "Über Momo gesprochen"}]

    class KeinIndex:
        is_available = False

    monkeypatch.setattr(modul, "archiv_service", FakeArchiv())
    monkeypatch.setattr(suche_modul, "archiv_suche", KeinIndex())

    e = wz.ausfuehren("archiv_suchen", {"frage": "Momo"})
    assert e.ok
    # Der Beleg-Zeiger bleibt.
    assert "[ChatGPT, 2024-03-01]" in e.text
    # Die alte Strich-Aufzählung ist weg; die Fluss-Anweisung ist da.
    assert "\n- [" not in e.text
    assert "keine Strichliste" in e.text


# ── Der Prompt selbst (system_prompt.md) ──────────────────────────────────

def test_system_prompt_enthaelt_die_fluss_regel():
    pfad = os.path.join(BACKEND, "system_prompt.md")
    with open(pfad, encoding="utf-8") as f:
        inhalt = f.read()
    assert "Wenn du aus dem Archiv erzählst" in inhalt
    assert "keine Strichliste" in inhalt
