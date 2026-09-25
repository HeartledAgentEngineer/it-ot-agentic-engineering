"""Tests für die Erinnerungs-API (/api/memory).

Warum diese Datei neu ist (2026-09-25): Die Oberfläche zeigte Erinnerungen
bisher GAR NICHT an - sichtbar war nur die Zahl im Fuß. Genau diese Endpunkte
(GET-Liste, Einzel-Löschen, Zähler) hängen jetzt das Erinnerungs-Blatt im
Frontend. Vorher hatte KEIN Test sie abgedeckt: im ganzen tests/-Ordner kam
"memory" nur als Attrappe (mock) vor.

Sicherheit: Der echte Speicher (chroma_data/memory_store.json mit Sebastians
Erinnerungen) wird NIE angefasst - jede Prüfung läuft in einem tmp_path.
Und es wird nie wirklich eingebettet: `mistral_vektor` ist ersetzt, sonst
liefe der Test in einen echten Netz-Aufruf (dieselbe Lehre wie die roten
Tests vom 15.09.2026).
"""

import asyncio
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from fastapi import HTTPException  # noqa: E402

from app.db.chroma_client import chroma_client  # noqa: E402
from app.models import MemoryCreate  # noqa: E402
from app.router import memory as memory_router  # noqa: E402
from app.services import memory_service as memory_mod  # noqa: E402
from app.services.llm_service import llm_service  # noqa: E402


@pytest.fixture()
def speicher(tmp_path, monkeypatch):
    """Eigener Speicher je Test - nie der echte Bestand."""
    monkeypatch.setattr(chroma_client, "persist_dir", str(tmp_path))
    monkeypatch.setattr(chroma_client, "store_path",
                        str(tmp_path / "memory_store.json"))
    # Kein Einbetten: kein lokales Modell, kein Mistral-Aufruf.
    monkeypatch.setattr(memory_mod, "mistral_vektor", lambda text: None)
    chroma_client._memories = []
    chroma_client._loaded = True
    yield chroma_client
    chroma_client._memories = []
    chroma_client._loaded = False


def _lade_liste(limit=50):
    antwort = asyncio.run(memory_router.list_memories(limit=limit))
    return antwort.memories, antwort.total


def test_leerer_speicher_liefert_leere_liste(speicher):
    memories, total = _lade_liste()
    assert memories == []
    assert total == 0
    assert asyncio.run(memory_router.memory_count())["count"] == 0


def test_anlegen_und_lesen_ueber_die_api(speicher):
    """Der Weg, den das Erinnerungs-Blatt geht: schreiben, dann auflisten."""
    antwort = asyncio.run(memory_router.create_memory(MemoryCreate(
        content="Testfakt: arbeitet an einem Agenten.", category="fact",
    )))
    assert antwort["status"] == "created"
    assert antwort["id"]

    memories, total = _lade_liste()
    assert total == 1
    eintrag = memories[0]
    assert eintrag.id == antwort["id"]
    assert eintrag.content == "Testfakt: arbeitet an einem Agenten."
    assert eintrag.category == "fact"
    assert eintrag.importance == 3
    # Das Blatt zeigt das Datum an - ohne Zeitstempel bliebe die Zeile leer.
    assert eintrag.timestamp


def test_derselbe_fakt_wird_nicht_zweimal_gespeichert(speicher):
    """Ohne diese Prüfung füllte jedes Gespräch denselben Fakt neu an."""
    for _ in range(3):
        memory_service_id = memory_mod.memory_service.store_memory(
            content="Testfakt: trinkt morgens Kaffee."
        )
        assert memory_service_id
    assert speicher.count() == 1


def test_einzelner_eintrag_laesst_sich_loeschen(speicher):
    """Sebastians Kernwunsch: EIN falscher Eintrag darf weg - ohne alle."""
    ids = [
        memory_mod.memory_service.store_memory(content="Testfakt: eins."),
        memory_mod.memory_service.store_memory(content="Testfakt: zwei."),
    ]
    ergebnis = asyncio.run(memory_router.einzelne_erinnerung_loeschen(ids[0]))
    assert ergebnis["status"] == "geloescht"
    assert speicher.count() == 1
    memories, _ = _lade_liste()
    assert [m.content for m in memories] == ["Testfakt: zwei."]

    # Ein zweiter Löschversuch findet nichts mehr - und sagt das auch.
    with pytest.raises(HTTPException) as fehler:
        asyncio.run(memory_router.einzelne_erinnerung_loeschen(ids[0]))
    assert fehler.value.status_code == 404


def test_zaehler_passt_zur_liste(speicher):
    # Bewusst klar verschiedene Sätze: Die Wiederholungs-Prüfung verwirft
    # schon fast gleiche Wortlaute (siehe test_gleicher_anfang_gilt_als_
    # wiederholung) - der Test prüft den Zähler, nicht die Ähnlichkeitsregel.
    for text in ("Testfakt: mag Tee.", "Testfakt: fährt Rad.", "Testfakt: liest gern."):
        memory_mod.memory_service.store_memory(content=text)
    assert asyncio.run(memory_router.memory_count())["count"] == 3


def test_gleicher_anfang_gilt_schon_als_wiederholung(speicher):
    """BELEGTER NEBENWIRKUNG der Wiederholungs-Prüfung (Befund 25.09.2026).

    `_ist_wiederholung` vergleicht Zeichen (difflib) mit Schwelle 0.90. Zwei
    Sätze mit gleichem Anfang und EINER geänderten Stelle erreichen das
    bereits - gemessen u. a.:
        „Ich arbeite seit zehn Jahren in der Automatisierung."
        vs. „… seit elf Jahren …"                    -> 0.95 (gilt als gleich)
        „Ich habe einen Hund namens Rex." vs. „… Max." -> 0.93
        „Geburtstag: 3. Mai 1984" vs. „5. Mai 1985"     -> 0.91
    Der zweite Fakt wird dann NICHT gespeichert (store_memory gibt die ID des
    alten Eintrags zurück). Folge: Eine KORREKTUR (richtiges Geburtsdatum,
    richtiger Name) kann am alten, falschen Eintrag abprallen.

    Dieser Test hält den Ist-Zustand fest, damit die geplante Änderung an der
    Regel (Konzept `docs/konzept-gedaechtnis.md`, Option B) sichtbar wird.
    """
    alt = "Testfakt: arbeitet seit zehn Jahren in der Automatisierung."
    neu = "Testfakt: arbeitet seit elf Jahren in der Automatisierung."
    id_alt = memory_mod.memory_service.store_memory(content=alt)
    id_neu = memory_mod.memory_service.store_memory(content=neu)

    assert speicher.count() == 1          # nur der erste bleibt stehen
    assert id_neu == id_alt               # der zweite bekommt die alte ID
    inhalt = speicher.get_all_memories(limit=10)[0]["content"]
    assert inhalt == alt                  # die Korrektur ist verloren


def test_wiederholungen_aufraeumen_trockenlauf_loescht_nichts(speicher):
    """Erst zeigen, dann löschen - gelöscht ist nicht wiederherstellbar."""
    for _ in range(2):
        speicher.add_memory(content="Testfakt: dieselbe Zeile.")
    bericht = asyncio.run(memory_router.wiederholungen_aufraeumen(ausfuehren=False))
    assert bericht["nur_gezeigt"] is True
    assert bericht["entfernt"] == 1
    assert bericht["vorher"] == 2
    assert speicher.count() == 2          # nichts angefasst

    bericht = asyncio.run(memory_router.wiederholungen_aufraeumen(ausfuehren=True))
    assert bericht["nachher"] == 1
    assert speicher.count() == 1


# ── Was in den Prompt wandert ──────────────────────────────────────────

def test_leerer_speicher_erzeugt_keinen_promptblock(speicher):
    """Der 0-Treffer-Fall: kein leerer Block, kein erfundener Kontext."""
    treffer = memory_mod.memory_service.retrieve_relevant_memories("Wer bin ich?", top_k=5)
    assert treffer == []
    assert llm_service._build_memory_context(treffer) == ""


def test_kleiner_speicher_wandert_vollstaendig_in_den_prompt(speicher):
    """Bewusst so (ALLES_MITGEBEN_BIS=300): Bei einem kleinen Bestand wird
    nicht ausgewählt. Ohne lokalen Embedder lieferte die Auswahl sonst die
    neuesten statt der passenden Einträge (siehe memory_service.py)."""
    for text in ("Testfakt: mag Tee.", "Testfakt: fährt Rad.", "Testfakt: liest gern."):
        memory_mod.memory_service.store_memory(content=text)
    treffer = memory_mod.memory_service.retrieve_relevant_memories("Frage", top_k=1)
    assert len(treffer) == 3      # top_k ist bei kleinem Bestand wirkungslos

    block = llm_service._build_memory_context(treffer)
    assert "GEMERKTE INFORMATIONEN" in block
    assert block.count("\n- ") == 3


def test_eintraege_ohne_vektor_werden_gefunden(speicher):
    """Ohne Vektor (Handy-Normalfall) muss die Nachrüstung sie sehen."""
    speicher.add_memory(content="Testfakt: ohne Vektor.")
    offen = speicher.eintraege_ohne_vektor()
    assert len(offen) == 1
    assert offen[0]["content"] == "Testfakt: ohne Vektor."

    assert speicher.setze_vektor(offen[0]["id"], [0.1, 0.2, 0.3]) is True
    assert speicher.eintraege_ohne_vektor() == []
