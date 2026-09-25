"""Tests: Der Sprach-Endpunkt POST /api/sprache/transkript.

Der Pfad ist der in der Roadmap (Stufe D3) zugesagte Weg — Audio rein, Text
raus. Er wird hier über **echtes HTTP** gegen die echte App geprüft, aber mit
Attrappe für die Transkription und die Glättung: kein Netz-Call, kein
API-Key, kein Verbrauch. Zusätzlich hängt im Client eine Stolperfalle, die
jeden echten Aufruf sofort auffliegen lässt.

Geprüft wird außerdem, dass die Audiodaten **nur im Speicher** leben: Der
Router kennt kein `tempfile` und schreibt nichts auf die Platte.

Aufruf: cd backend && .venv/Scripts/python -m pytest tests/test_sprache_endpunkt.py -q
"""
from contextlib import contextmanager
import os
import sys
from unittest import mock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.config import settings  # noqa: E402
from app.services.llm_service import llm_service  # noqa: E402

# Gültiger WAV-Kopf — mehr braucht der Endpunkt nicht zu erkennen.
WAV = b"RIFF" + b"\x00" * 400
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 400

NEUER_PFAD = "/api/sprache/transkript"
ALTER_PFAD = "/api/transcribe"


class KeinNetz:
    """Stolperfalle: Jeder Zugriff auf den echten LLM-Client fliegt auf."""

    def __getattr__(self, name):
        raise AssertionError(f"Echter Netz-Call versucht: {name}")


@pytest.fixture()
def client(monkeypatch):
    """TestClient gegen die echte App, ohne API-Key-Schutz der .env."""
    from fastapi.testclient import TestClient

    from app.main import app

    # Der Key-Schutz haengt an der .env des Rechners; fuer den Test wird er
    # ausdruecklich ausgeschaltet, damit die Aussage nicht vom Rechner abhaengt.
    monkeypatch.setattr(settings, "api_key", None)
    return TestClient(app)


@contextmanager
def _gemockt(rohtext, geglaettet):
    """Transkription + Glättung durch Attrappen ersetzen (kein Netz).

    Liefert die beiden Attrappen, damit ein Test nachsehen kann, was
    tatsächlich gerufen wurde.
    """
    with mock.patch.object(llm_service, "transcribe", return_value=rohtext) as m_trans, \
            mock.patch.object(llm_service, "polish_text", return_value=geglaettet) as m_polish, \
            mock.patch.object(llm_service, "client", KeinNetz()):
        yield m_trans, m_polish


def _post(client, pfad, daten, name="audio.wav", typ="audio/wav"):
    return client.post(pfad, files={"file": (name, daten, typ)})


# ── Verdrahtung ──────────────────────────────────────────────────────────────

def _route(pfad):
    from app.main import app

    for route in app.routes:
        if getattr(route, "path", None) == pfad and "POST" in getattr(route, "methods", set()):
            return route
    return None


def test_route_ist_eingehaengt():
    """Der zugesagte Pfad existiert und nimmt POST an."""
    assert _route(NEUER_PFAD) is not None, f"{NEUER_PFAD} fehlt in der App"


def test_route_haengt_am_api_key_schutz():
    """Wie die übrigen /api-Routen: ohne gültigen Key kein Zugriff."""
    route = _route(NEUER_PFAD)
    assert route is not None
    namen = [getattr(d.call, "__name__", "") for d in route.dependant.dependencies]
    assert "require_api_key" in namen, f"Key-Schutz fehlt (Abhängigkeiten: {namen})"


# ── Der Sprachweg selbst ─────────────────────────────────────────────────────

def test_transkript_laeuft_ueber_die_bestehende_kette(client):
    """Audio rein → Kette (transcribe + polish) → bereinigter Text raus."""
    m_trans, m_polish = None, None
    with _gemockt("ähm der commit ist durch", "Der Commit ist durch.") as (m_trans, m_polish):
        antwort = _post(client, NEUER_PFAD, WAV)

    assert antwort.status_code == 200
    assert antwort.json() == {"text": "Der Commit ist durch."}
    # Die Bytes gehen UNVERÄNDERT an die bestehende Kette (nichts neu erfunden).
    m_trans.assert_called_once()
    assert m_trans.call_args[0][0] == WAV
    # Die Glättung bekommt den Rohtext, nicht das Audio.
    m_polish.assert_called_once_with("ähm der commit ist durch")


def test_rohtext_bleibt_wenn_die_glaettung_ausfaellt(client):
    """Scheitert die Glättung, ist der Rohtext besser als gar kein Text."""
    with _gemockt("Der Commit ist durch.", None):
        antwort = _post(client, NEUER_PFAD, WAV)

    assert antwort.status_code == 200
    assert antwort.json() == {"text": "Der Commit ist durch."}


def test_keine_sprache_erkannt_wird_ehrlich_gemeldet(client):
    """Liefert die Kette nichts, kommt kein erfundener Text zurück."""
    with _gemockt(None, None):
        antwort = _post(client, NEUER_PFAD, WAV)

    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["text"] is None
    assert daten["error"] == "Transkription fehlgeschlagen"


def test_leere_datei_wird_abgelehnt(client):
    antwort = _post(client, NEUER_PFAD, b"")
    assert antwort.status_code == 400


def test_zu_grosse_datei_wird_abgelehnt(client, monkeypatch):
    """Die Grenze greift, ohne 25 MB durch die Leitung zu schicken."""
    import app.router.transcribe as transcribe_mod

    monkeypatch.setattr(transcribe_mod, "MAX_FILE_SIZE", 10)
    antwort = _post(client, NEUER_PFAD, WAV)
    assert antwort.status_code == 413


def test_webm_geht_ebenso_durch(client):
    """Das Frontend schickt WAV; WebM ist der zweite erkannte Weg."""
    with _gemockt("Text.", "Text."):
        antwort = _post(client, NEUER_PFAD, WEBM, name="audio.webm", typ="audio/webm")
    assert antwort.status_code == 200
    assert antwort.json()["text"] == "Text."


def test_alter_pfad_antwortet_weiterhin(client):
    """`/api/transcribe` bleibt bedient — kein Aufrufer bricht."""
    with _gemockt("Rohtext.", "Text."):
        antwort = _post(client, ALTER_PFAD, WAV)
    assert antwort.status_code == 200
    assert antwort.json()["text"] == "Text."


# ── Datenschutz: Audio nur im Speicher ───────────────────────────────────────

def test_router_schreibt_das_audio_nicht_auf_die_platte():
    """Kein tempfile, kein Datei-Schreibzugriff im Router — Audio bleibt im RAM."""
    with open(os.path.join(BACKEND, "app", "router", "transcribe.py"), encoding="utf-8") as f:
        quelle = f.read()
    # Nur CODE prüfen, nicht die Kommentare: Der Hinweis „kein tempfile" im
    # Modulkopf ist erwünscht und darf hier nicht anschlagen.
    for verboten in ("import tempfile", "tempfile.", "open(", ".write(", ".write_text(", ".write_bytes("):
        assert verboten not in quelle, f"Router schreibt Dateien: {verboten}"


def test_audio_puffer_bleibt_im_arbeitsspeicher():
    """Der Weg zum Anbieter läuft über einen BytesIO-Puffer, nicht über eine Datei."""
    with open(os.path.join(BACKEND, "app", "services", "llm_service.py"), encoding="utf-8") as f:
        quelle = f.read()
    assert "io.BytesIO" in quelle
    assert "def _audio_puffer" in quelle
