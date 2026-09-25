"""Transparenz: „Was weißt du über X?" (GET /api/memory/erklaeren).

Warum diese Datei neu ist (25.09.2026): Sebastian will verstehen, was sein
Agent sich merkt - und ob ein Eintrag aktiv ist oder eine abgelöste Fassung.
Der Endpunkt ist bewusst LESEND: kein LLM, kein Netzaufruf, keine Änderung am
Bestand. Genau das wird hier geprüft (Struktur, Historie, Nur-Lesen,
Offline-Tauglichkeit, Registrierung der Route).

Sicherheit: eigener Speicher in `tmp_path`, `openrouter_vektor` ersetzt -
der echte Bestand und das Netz bleiben unberührt.
"""

import asyncio
import inspect
import os
import sys
from datetime import date

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.db.chroma_client import chroma_client  # noqa: E402
from app.router import memory as memory_router  # noqa: E402
from app.services import memory_service as memory_mod  # noqa: E402

HEUTE = date(2026, 9, 25)


@pytest.fixture()
def speicher(tmp_path, monkeypatch):
    monkeypatch.setattr(chroma_client, "persist_dir", str(tmp_path))
    monkeypatch.setattr(chroma_client, "store_path",
                        str(tmp_path / "memory_store.json"))
    monkeypatch.setattr(memory_mod, "openrouter_vektor", lambda text: None)
    chroma_client._memories = []
    chroma_client._loaded = True
    yield chroma_client
    chroma_client._memories = []
    chroma_client._loaded = False


def _erklaeren(begriff: str, top_k: int = 10):
    return asyncio.run(memory_router.erklaeren(begriff=begriff, top_k=top_k))


def test_erklaerung_zeigt_art_zeitbezug_und_historie(speicher):
    """Der Kern: Treffer + Art + Zeitbezug + aktiv/Historie."""
    memory_mod.memory_service.store_memory(
        content="Oma Helga ist meine Oma.", heute=HEUTE
    )
    alt = "Zahnarzttermin mit Zahnreinigung am 12.05.2026."
    neu = "Zahnarzttermin mit Zahnreinigung am 19.05.2026."
    memory_mod.memory_service.store_memory(content=alt, heute=HEUTE)
    memory_mod.memory_service.store_memory(content=neu, heute=HEUTE)

    antwort = _erklaeren("Zahnarzt")

    assert antwort["begriff"] == "Zahnarzt"
    assert antwort["suchweise"] == "wortgleichheit"
    # Zwei Treffer: die aktive Fassung UND die abgelöste (sie ist Historie,
    # kein gelöschter Eintrag - deshalb taucht sie als eigener Treffer auf).
    assert antwort["anzahl"] == 2
    assert antwort["aktiv"] == 1 and antwort["historie"] == 1

    treffer = antwort["treffer"][0]        # aktive Fassung steht vorn
    assert treffer["inhalt"] == neu
    assert treffer["aktiv"] is True
    assert treffer["art"] == "termin" and treffer["art_text"] == "Termin"
    assert treffer["zeitbezug"]["lage"] == "vergangen"
    assert treffer["zeitbezug"]["datum"] == "2026-05-19"
    assert treffer["wichtig"] == 4
    assert treffer["seit"]
    # Die abgelöste Fassung ist im Verlauf sichtbar (nichts gelöscht).
    assert treffer["historie"][0]["inhalt"] == alt
    assert treffer["historie"][0]["abgeloest_am"]

    historie = antwort["treffer"][1]
    assert historie["aktiv"] is False
    assert historie["inhalt"] == alt
    assert historie["historie_von"] == treffer["id"]
    assert historie["abgeloest_am"]


def test_abgeloeste_fassung_ist_als_historie_auffindbar(speicher):
    """Der falsche Name ist nicht weg - er wird als Historie gemeldet."""
    memory_mod.memory_service.store_memory(content="Ich habe einen Hund namens Rex.")
    memory_mod.memory_service.store_memory(content="Ich habe einen Hund namens Max.")
    eintrag = speicher.get_all_memories(limit=10)[0]

    alt_treffer = _erklaeren("Rex")
    assert alt_treffer["anzahl"] == 1
    assert alt_treffer["aktiv"] == 0 and alt_treffer["historie"] == 1
    alt = alt_treffer["treffer"][0]
    assert alt["inhalt"] == "Ich habe einen Hund namens Rex."
    assert alt["aktiv"] is False
    assert alt["historie_von"] == eintrag["id"]
    assert alt["abgeloest_am"]

    neu_treffer = _erklaeren("Max")
    assert neu_treffer["treffer"][0]["aktiv"] is True
    assert neu_treffer["treffer"][0]["historie"][0]["inhalt"].endswith("Rex.")


def test_teilwort_findet_den_eintrag(speicher):
    """„Zahnarzt" muss „Zahnarzttermin" finden (Wortlaut, kein Stammbaum)."""
    memory_mod.memory_service.store_memory(
        content="Am 2. November Zahnarzttermin mit Zahnreinigung", heute=HEUTE
    )
    antwort = _erklaeren("Zahnarzt")
    assert antwort["anzahl"] == 1
    assert antwort["treffer"][0]["art"] == "termin"
    assert antwort["treffer"][0]["zeitbezug"]["lage"] == "kommend"
    assert antwort["treffer"][0]["zeitbezug"]["tage_bis"] == 38


def test_ohne_treffer_keine_erfindung(speicher):
    """Kein Treffer heißt: leere Liste + Hinweis - und keine Vermutung."""
    memory_mod.memory_service.store_memory(content="Oma Helga ist meine Oma.")
    antwort = _erklaeren("Weltraum")
    assert antwort["treffer"] == []
    assert antwort["anzahl"] == 0
    assert "Weltraum" in antwort["hinweis"]
    assert "Wortlaut" in antwort["hinweis"]

    leer = _erklaeren("")
    assert leer["treffer"] == []
    assert leer["hinweis"] == "Kein Suchbegriff angegeben."


def test_erklaeren_aendert_nichts_am_bestand(speicher):
    """Nur lesen: Zeichen für Zeichen derselbe Bestand vorher/nachher."""
    memory_mod.memory_service.store_memory(content="Oma Helga ist meine Oma.", heute=HEUTE)
    memory_mod.memory_service.store_memory(
        content="Am 2. November Zahnarzttermin mit Zahnreinigung", heute=HEUTE
    )
    vorher = speicher.get_all_memories(limit=100)
    zahl = speicher.count()

    for begriff in ("Oma", "Zahnarzt", "Weltraum"):
        _erklaeren(begriff)

    assert speicher.get_all_memories(limit=100) == vorher
    assert speicher.count() == zahl


def test_erklaeren_ohne_netz_und_ohne_llm(speicher, monkeypatch):
    """Kein HTTP-Aufruf, kein Modell - der Weg läuft auch ohne Schlüssel."""
    memory_mod.memory_service.store_memory(content="Oma Helga ist meine Oma.", heute=HEUTE)

    aufrufe = []

    def _kein_netz(*args, **kwargs):
        aufrufe.append(args)
        raise RuntimeError("Netz-Aufruf im Erklären-Endpunkt")

    monkeypatch.setattr(memory_mod.httpx, "post", _kein_netz)

    antwort = _erklaeren("Oma")
    assert antwort["anzahl"] == 1
    assert aufrufe == []

    # Strukturell: der Weg fasst weder den LLM-Dienst noch dessen Client an.
    quelle = inspect.getsource(memory_mod.MemoryService.erklaere_begriff)
    assert "llm_service" not in quelle
    assert "chat.completions" not in quelle


def test_route_ist_registriert():
    """/api/memory/erklaeren muss als GET in der App hängen (nicht nur als Funktion)."""
    from app.main import app

    routen = [
        (getattr(r, "path", ""), set(getattr(r, "methods", set()) or set()))
        for r in app.routes
    ]
    treffer = [m for p, m in routen if p == "/api/memory/erklaeren"]
    assert treffer, "Route /api/memory/erklaeren fehlt"
    assert "GET" in treffer[0]
