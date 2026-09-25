"""Qualität des Gedächtnisses: Korrekturen, Relevanz, Zeitbezug, Migration.

Warum diese Datei neu ist (25.09.2026): Die Diagnose
`docs/konzept-gedaechtnis.md` hat vier Dinge belegt, die hier festgenagelt
werden - damit sie nicht zurückkommen:

1. **Korrekturen wurden weggeworfen.** Die 0,90-Ähnlichkeitsregel hielt
   „seit zehn Jahren" und „seit elf Jahren" für denselben Fakt und
   verwarf die richtige Fassung (dito „Rex"/„Max", Datumskorrekturen).
2. **Der ganze Bestand wanderte in jede Frage** (`ALLES_MITGEBEN_BIS = 300`),
   `top_k` war wirkungslos.
3. **`category` und `importance` waren tote Felder** (immer `fact`, immer 3).
4. **Kein Zeitbezug:** ein Termin blieb auch nach dem Termin „aktuell", und
   ein vergangener Termin war nicht mehr auffindbar.

Sicherheit: Der echte Speicher
(`chroma_data/memory_store.json` mit Sebastians Erinnerungen) wird NIE
angefasst - jede Prüfung läuft in einem `tmp_path`. Und es wird nie wirklich
eingebettet: `openrouter_vektor` ist ersetzt (kein Netz-Aufruf).
"""

import asyncio
import inspect
import os
import sys
from datetime import date
from difflib import SequenceMatcher

import numpy as np
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.db.chroma_client import chroma_client  # noqa: E402
from app.services import memory_service as memory_mod  # noqa: E402
from app.services.llm_service import llm_service  # noqa: E402

HEUTE = date(2026, 9, 25)          # Tag der Entscheidungen - feste Zeitachse
DEFAULT_MAX = llm_service.MEMORY_BLOCK_MAX_ZEICHEN


@pytest.fixture()
def speicher(tmp_path, monkeypatch):
    """Eigener Speicher je Test - nie der echte Bestand, nie das Netz."""
    monkeypatch.setattr(chroma_client, "persist_dir", str(tmp_path))
    monkeypatch.setattr(chroma_client, "store_path",
                        str(tmp_path / "memory_store.json"))
    # Grundfall: keine Vektoren (so sieht es auf dem Handy ohne Schlüssel aus).
    monkeypatch.setattr(memory_mod, "openrouter_vektor", lambda text: None)
    chroma_client._memories = []
    chroma_client._loaded = True
    yield chroma_client
    chroma_client._memories = []
    chroma_client._loaded = False


def _fake_vektor(text: str):
    """Deterministischer Ersatz für die OpenRouter-Einbettung (kein Netz).

    Bag-of-words in 64 Buckets: gleiche Wörter -> gleiche Richtung. Reicht,
    um zu belegen, dass die Auswahl über Bedeutung läuft (und nicht über das
    Alter). Bewusst KEIN Zufall: derselbe Text ergibt immer denselben Vektor.
    """
    vek = np.zeros(64, dtype=np.float32)
    for wort in memory_mod._tokens(text):
        vek[sum(map(ord, wort)) % 64] += 1.0
    norm = float(np.linalg.norm(vek))
    return (vek / norm).tolist() if norm else None


_WORTE = (
    "Alpha Beta Gamma Delta Epsilon Zeta Eta Theta Iota Kappa Lambda My Ny Xi "
    "Omikron Pi Rho Sigma Tau Ypsilon Automatisierung Gedaechtnis Werkstatt "
    "Fahrrad Kaffee Wasser Berge Garten Familie Konzert Python Backend Ordner "
    "Bibliothek Sternwarte Kompass Anker Feder Kreide Tafel Brunnen Laterne "
    "Wolke Wiese Werkzeug Leiter Seil Stein Sand Metall Kupfer Bronze Silber "
    "Kristall Tinte Papier Atlas Globus Landkarte Wueste Insel Hafen "
    "Leuchtturm Mast Segel Ruder Kahn Truhe Schluessel Uhr Kerze Decke"
).split()
assert len(_WORTE) == 72, len(_WORTE)   # 72 Wörter: keine Wortgruppe wiederholt sich


def _testtext(i: int) -> str:
    """Ein Testeintrag, der sich von jedem anderen DEUTLICH unterscheidet.

    Wichtig: Einträge dürfen sich nicht nur in einer Nummer unterscheiden -
    genau das wäre seit dem 25.09.2026 eine Korrektur, und der Bestand bliebe
    bei einem Eintrag stehen. Deshalb besteht jeder Eintrag aus fünf
    verschiedenen Wörtern OHNE gemeinsamen Rahmen; die Tests prüfen mit
    `count()`, dass wirklich alle Einträge getrennt angelegt wurden.
    """
    indizes = (
        (3 * i) % len(_WORTE),
        (5 * i + 7) % len(_WORTE),
        (7 * i + 13) % len(_WORTE),
        (11 * i + 19) % len(_WORTE),
        (13 * i + 23) % len(_WORTE),
    )
    return " ".join(_WORTE[k] for k in indizes) + "."


def _langtext(i: int) -> str:
    """Ein langer Eintrag (~110 Zeichen): drei Wortgruppen ohne gemeinsamen Rahmen.

    Gebraucht für die Zeichenobergrenze des Prompt-Blocks: Kurze Einträge
    passen alle hinein, dann prüfte der Test die Grenze gar nicht.
    """
    return f"{_testtext(i)} {_testtext(i + 24)} {_testtext(i + 48)}"


def _eintragszeilen(block: str):
    """Nur die Erinnerungszeilen - ohne Kopf und ohne Hinweiszeilen."""
    return [
        z for z in block.split("\n")
        if z.startswith("- ") and not z.startswith("- (")
    ]


def _aehnlichkeit(a: str, b: str) -> float:
    """Dieselbe Rechnung wie im Dienst - für die belegten Beispielwerte."""
    return SequenceMatcher(None, memory_mod._normalisiert(a),
                           memory_mod._normalisiert(b)).ratio()


# ── (a) „zehn" -> „elf": Korrektur wird aktiv, alte Fassung bleibt ─────

def test_korrektur_jahreszahl_wird_aktiv_und_alte_fassung_bleibt(speicher):
    alt = "Ich arbeite seit zehn Jahren in der Automatisierung."
    neu = "Ich arbeite seit elf Jahren in der Automatisierung."

    # Beleg, dass der Fall wirklich durch die alte 0,90-Regel gefallen ist:
    assert _aehnlichkeit(alt, neu) >= memory_mod.AEHNLICHKEIT_SCHWELLE
    assert memory_mod._ist_korrektur(alt, neu) is True
    assert memory_mod._ist_doppelung(alt, neu) is False

    id_alt = memory_mod.memory_service.store_memory(content=alt)
    vorher = speicher.get_all_memories(limit=10)[0]
    id_neu = memory_mod.memory_service.store_memory(content=neu)

    assert speicher.count() == 1                # nichts gelöscht, nichts doppelt
    assert id_neu == id_alt                     # dieselbe Erinnerung, neue Fassung
    eintrag = speicher.get_all_memories(limit=10)[0]
    assert eintrag["content"] == neu            # aktive Fassung = Korrektur
    assert eintrag["history"][0]["inhalt"] == alt      # alte Fassung aufbewahrt
    assert eintrag["history"][0]["abgeloest_am"]       # Zeitpunkt der Ablösung
    # Auch der Zeitpunkt, an dem die ALTE Fassung geschrieben wurde, bleibt.
    assert eintrag["history"][0]["geschrieben_am"] == vorher["timestamp"]


# ── (b) „Rex" -> „Max" ebenso ─────────────────────────────────────────

def test_korrektur_name_wird_aktiv_und_alte_fassung_bleibt(speicher):
    alt = "Ich habe einen Hund namens Rex."
    neu = "Ich habe einen Hund namens Max."
    assert _aehnlichkeit(alt, neu) >= memory_mod.AEHNLICHKEIT_SCHWELLE

    memory_mod.memory_service.store_memory(content=alt)
    memory_mod.memory_service.store_memory(content=neu)

    eintrag = speicher.get_all_memories(limit=10)[0]
    assert speicher.count() == 1
    assert eintrag["content"] == neu
    assert [h["inhalt"] for h in eintrag["history"]] == [alt]

    # Der falsche Name ist nicht verloren: er steht im Verlauf und ist dort
    # auffindbar (Transparenz-Endpunkt, ohne LLM).
    erklaerung = memory_mod.memory_service.erklaere_begriff("Rex", heute=HEUTE)
    assert erklaerung["anzahl"] == 1
    assert erklaerung["treffer"][0]["aktiv"] is False
    assert erklaerung["treffer"][0]["historie_von"] == eintrag["id"]


# ── (c) Datumskorrektur ebenso ────────────────────────────────────────

def test_korrektur_datum_wird_aktiv_und_alte_fassung_bleibt(speicher):
    alt = "Testfakt: Geburtstag am 3. Mai 1984."
    neu = "Testfakt: Geburtstag am 5. Mai 1985."
    assert _aehnlichkeit(alt, neu) >= memory_mod.AEHNLICHKEIT_SCHWELLE

    memory_mod.memory_service.store_memory(content=alt)
    memory_mod.memory_service.store_memory(content=neu)

    assert speicher.count() == 1
    eintrag = speicher.get_all_memories(limit=10)[0]
    assert eintrag["content"] == neu
    assert eintrag["history"][0]["inhalt"] == alt
    # Ein Geburtstag ist wiederkehrend - er darf nie „abgelaufen" sein.
    assert eintrag["category"] == "termin"
    assert eintrag["wiederkehrend"] is True
    assert eintrag["ereignis_datum"] is None


# ── (d) echte Doppelung wird zusammengefasst ──────────────────────────

def test_echte_doppelung_wird_zusammengefasst(speicher):
    text = "Testfakt: trinkt morgens Kaffee."
    for _ in range(3):
        memory_mod.memory_service.store_memory(content=text)
    assert speicher.count() == 1        # wortgleich bleibt wortgleich

    # Nur ein Füllwort mehr ("auch") = dieselbe Aussage: keine Korrektur,
    # kein Verlaufseintrag.
    memory_mod.memory_service.store_memory(content="Testfakt: trinkt morgens auch Kaffee.")
    assert speicher.count() == 1
    eintrag = speicher.get_all_memories(limit=10)[0]
    assert eintrag["content"] == text
    assert eintrag["history"] == []


def test_doppelung_und_korrektur_werden_unterschieden():
    """Die Trennlinie als Tabelle - an gemessenen Beispielen."""
    doppelungen = [
        ("Testfakt: trinkt morgens Kaffee.", "Testfakt: trinkt morgens Kaffee."),
        ("Testfakt: trinkt morgens Kaffee.", "Testfakt: trinkt morgens auch Kaffee."),
        ("Ich mag Tee.", "Ich mag Tee"),
    ]
    korrekturen = [
        ("Ich arbeite seit zehn Jahren in der Automatisierung.",
         "Ich arbeite seit elf Jahren in der Automatisierung."),
        ("Ich habe einen Hund namens Rex.", "Ich habe einen Hund namens Max."),
        ("Testfakt: Geburtstag am 3. Mai 1984.", "Testfakt: Geburtstag am 5. Mai 1985."),
        ("Mein Lieblingsgetränk ist Kaffee, das trinke ich jeden Morgen.",
         "Mein Lieblingsgetränk ist Tee, das trinke ich jeden Morgen."),
    ]
    for a, b in doppelungen:
        assert memory_mod._ist_doppelung(a, b) is True, (a, b)
        assert memory_mod._ist_korrektur(a, b) is False, (a, b)
    for a, b in korrekturen:
        assert memory_mod._ist_korrektur(a, b) is True, (a, b)
        assert memory_mod._ist_doppelung(a, b) is False, (a, b)

    # Eine ganz andere Formulierung derselben Sache bleibt ein eigener
    # Eintrag: dafür bräuchte es Bedeutung, nicht Zeichenvergleich.
    assert memory_mod._ist_korrektur("Ich mag Tee.", "Kaffee schmeckt mir nicht.") is False


def test_zustand_wird_von_neuer_fassung_abgeloest(speicher):
    """Veränderliche Details („die sich immer aktualisieren"): neue Fassung gilt."""
    alt = "Mein Lieblingsgetränk ist Kaffee, das trinke ich jeden Morgen."
    neu = "Mein Lieblingsgetränk ist Tee, das trinke ich jeden Morgen."
    memory_mod.memory_service.store_memory(content=alt)
    memory_mod.memory_service.store_memory(content=neu)

    eintrag = speicher.get_all_memories(limit=10)[0]
    assert eintrag["category"] == "zustand"
    assert eintrag["content"] == neu
    assert eintrag["history"][0]["inhalt"] == alt


# ── (e) top_k wirkt, der Promptblock ist hart begrenzt ────────────────

def test_bei_50_eintraegen_landen_nicht_alle_im_prompt(speicher, monkeypatch):
    monkeypatch.setattr(memory_mod, "openrouter_vektor", _fake_vektor)
    for i in range(50):
        memory_mod.memory_service.store_memory(content=_testtext(i), heute=HEUTE)
    assert speicher.count() == 50      # Prämisse: 50 getrennte Einträge

    treffer = memory_mod.memory_service.retrieve_relevant_memories(
        "Werkstatt Bibliothek Kompass", top_k=8, heute=HEUTE
    )
    assert 0 < len(treffer) <= 8       # top_k greift (nicht mehr der Bestand)
    assert all(t["relevanz_quelle"] == "vektor" for t in treffer)

    block = llm_service._build_memory_context(treffer)
    assert len(_eintragszeilen(block)) <= 8
    assert len(block) <= DEFAULT_MAX + 100

    # Gegenprobe: der Eintrag mit den meisten gemeinsamen Wörtern ist dabei
    # (Auswahl über Bedeutung, nicht über das Alter).
    gesucht = "Werkstatt Bibliothek Kompass"
    bester = max(
        speicher.get_all_memories(limit=100),
        key=lambda e: memory_mod._wort_score(gesucht, e["content"]),
    )
    assert memory_mod._wort_score(gesucht, bester["content"]) > 0
    assert bester["id"] in [t["id"] for t in treffer]


def test_zeichenobergrenze_kappt_lange_bloecke(speicher, monkeypatch):
    monkeypatch.setattr(memory_mod, "openrouter_vektor", _fake_vektor)
    for i in range(12):
        memory_mod.memory_service.store_memory(content=_langtext(i), heute=HEUTE)
    assert speicher.count() == 12

    treffer = memory_mod.memory_service.retrieve_relevant_memories(
        "Alpha", top_k=12, heute=HEUTE
    )
    assert len(treffer) == 12          # die Auswahl liefert alle 12
    block = llm_service._build_memory_context(treffer)
    zeilen = _eintragszeilen(block)
    assert len(zeilen) < 12            # der Block nimmt NICHT alle
    assert "weitere Erinnerung(en) ausgelassen" in block
    # Die Eintragszeilen selbst halten die Grenze ein.
    kopf = len("\n## GEMERKTE INFORMATIONEN AUS FRÜHEREN GESPRÄCHEN:")
    assert kopf + sum(len(z) + 1 for z in zeilen) <= DEFAULT_MAX


# ── (f) vergangener Termin: nicht „aktuell", aber auffindbar ──────────

def test_vergangener_termin_ist_nicht_aktuell_aber_auffindbar(speicher):
    memory_mod.memory_service.store_memory(
        content="Zahnarzttermin mit Zahnreinigung am 12.05.2026.", heute=HEUTE
    )
    eintrag = speicher.get_all_memories(limit=10)[0]
    assert eintrag["category"] == "termin"
    assert eintrag["ereignis_datum"] == "2026-05-12"

    # Normale Frage: der vergangene Termin gilt NICHT mehr als aktuell.
    treffer = memory_mod.memory_service.retrieve_relevant_memories(
        "Was steht an?", top_k=8, heute=HEUTE
    )
    assert treffer == []
    assert llm_service._build_memory_context(treffer) == ""

    # Frage nach der Vergangenheit: er kommt mit - sichtbar als Historie.
    treffer = memory_mod.memory_service.retrieve_relevant_memories(
        "War ich 2026 beim Zahnarzt?", top_k=8, heute=HEUTE
    )
    assert len(treffer) == 1
    assert treffer[0]["zeitbezug"]["lage"] == "vergangen"
    block = llm_service._build_memory_context(treffer)
    assert "VERGANGEN" in block and "2026-05-12" in block

    # Und findbar über den Erklären-Weg (Zahnkontrollheft, Bonus beim Zahnersatz).
    erklaerung = memory_mod.memory_service.erklaere_begriff("Zahnarzt", heute=HEUTE)
    assert erklaerung["anzahl"] == 1
    assert erklaerung["treffer"][0]["aktiv"] is True
    assert erklaerung["treffer"][0]["zeitbezug"]["lage"] == "vergangen"
    assert erklaerung["treffer"][0]["zeitbezug"]["datum"] == "2026-05-12"


# ── (g) nahender Termin steht im Prompt ───────────────────────────────

def test_nahender_termin_steht_im_prompt(speicher):
    for i in range(20):
        memory_mod.memory_service.store_memory(content=_testtext(i), heute=HEUTE)
    memory_mod.memory_service.store_memory(
        content="Zahnarzttermin mit Zahnreinigung am 2. November.", heute=HEUTE
    )
    eintrag = speicher.get_all_memories(limit=100)[-1]
    assert eintrag["category"] == "termin"
    assert eintrag["ereignis_datum"] == "2026-11-02"   # nächstes Vorkommen

    treffer = memory_mod.memory_service.retrieve_relevant_memories(
        "Was steht an?", top_k=8, heute=HEUTE
    )
    assert treffer[0]["content"].startswith("Zahnarzttermin")   # naher Termin vorn
    assert treffer[0]["zeitbezug"]["lage"] == "kommend"
    block = llm_service._build_memory_context(treffer)
    assert "Termin am 2026-11-02" in block


def test_termin_zuschlag_haengt_an_der_naehe():
    """Je näher der Termin, desto größer der Zuschlag - und nie ein Ausschluss."""
    nah, _ = memory_mod._termin_wert("termin", "2026-10-01", False, HEUTE)
    mittel, _ = memory_mod._termin_wert("termin", "2026-11-15", False, HEUTE)
    fern, _ = memory_mod._termin_wert("termin", "2027-03-01", False, HEUTE)
    vergangen, lage = memory_mod._termin_wert("termin", "2026-05-12", False, HEUTE)
    assert nah > mittel > fern > 0
    assert vergangen == 0.0 and lage == "vergangen"
    # Wiederkehrend (Geburtstag) läuft nicht ab, wird aber nicht bevorzugt.
    wieder, lage_w = memory_mod._termin_wert("termin", None, True, HEUTE)
    assert 0 < wieder < nah and lage_w == "wiederkehrend"


# ── Ehrlichkeit im Prompt: eingeschränkte Suche wird benannt ──────────

def test_prompt_block_nennt_eine_eingeschraenkte_suche(speicher):
    """Ohne Vektoren ist die Auswahl unschärfer - das muss im Block stehen."""
    memory_mod.memory_service.store_memory(content="Oma Helga ist meine Oma.", heute=HEUTE)
    treffer = memory_mod.memory_service.retrieve_relevant_memories(
        "Wer ist Oma Helga?", top_k=8, heute=HEUTE
    )
    assert treffer[0]["such_modus"] in ("wort", "neuheit")
    block = llm_service._build_memory_context(treffer)
    assert "Suche:" in block and "keine Vektoren" in block


def test_prompt_block_ohne_hinweis_wenn_vektoren_da_sind(speicher, monkeypatch):
    """Gegenprobe: Mit Einbettungen steht kein Einschränkungs-Hinweis im Block."""
    monkeypatch.setattr(memory_mod, "openrouter_vektor", _fake_vektor)
    memory_mod.memory_service.store_memory(content="Oma Helga ist meine Oma.", heute=HEUTE)
    treffer = memory_mod.memory_service.retrieve_relevant_memories(
        "Wer ist Oma Helga?", top_k=8, heute=HEUTE
    )
    assert treffer[0]["such_modus"] == "vektor"
    assert treffer[0]["such_hinweis"] == ""
    assert "Suche:" not in llm_service._build_memory_context(treffer)


def test_ohne_worttreffer_und_ohne_vektoren_greift_der_neuheiten_notbehelf(speicher):
    """Der letzte Ausweg ist sichtbar - und trotzdem begrenzt."""
    for i in range(5):
        memory_mod.memory_service.store_memory(content=_testtext(i), heute=HEUTE)
    treffer = memory_mod.memory_service.retrieve_relevant_memories(
        "xyz", top_k=2, heute=HEUTE
    )
    assert len(treffer) == 2                       # top_k gilt auch hier
    assert treffer[0]["such_modus"] == "neuheit"
    assert "neuesten" in treffer[0]["such_hinweis"]


# ── (h) Migration alten Bestands ──────────────────────────────────────

def test_migration_ergaenzt_art_ohne_inhalt_zu_verlieren(speicher):
    """Alte Einträge (category="fact", importance=3) bekommen Art und Zeitbezug."""
    # Altbestand nachstellen, genau wie er vor dem 25.09.2026 entstand.
    id_termin = speicher.add_memory(
        content="Zahnarzttermin mit Zahnreinigung am 2. November 2026.",
        category="fact", importance=3,
    )
    id_fakt = speicher.add_memory(content="Oma Helga ist meine Oma.", category="fact", importance=3)
    id_vorliebe = speicher.add_memory(
        content="Ich mag Tee statt Kaffee.", category="preference", importance=3
    )
    vorher = speicher.get_all_memories(limit=100)

    bericht = memory_mod.memory_service.migriere_bestand(nur_zeigen=True, heute=HEUTE)
    assert bericht["nur_gezeigt"] is True
    assert bericht["vorher"] == 3 and bericht["nachher"] == 3
    assert bericht["geaendert"] == 3 and bericht["unveraendert"] == 0
    assert speicher.get_all_memories(limit=100) == vorher     # Trockenlauf schreibt nicht

    bericht = memory_mod.memory_service.migriere_bestand(nur_zeigen=False, heute=HEUTE)
    assert bericht["nur_gezeigt"] is False
    nachher = speicher.get_all_memories(limit=100)

    # Vorher/Nachher: gleiche Anzahl, gleiche IDs, gleiche Inhalte (Zeichen
    # für Zeichen) - nichts gelöscht, nichts umgeschrieben.
    assert speicher.count() == 3
    assert [e["id"] for e in nachher] == [e["id"] for e in vorher]
    assert [e["content"] for e in nachher] == [e["content"] for e in vorher]

    nach_id = {e["id"]: e for e in nachher}
    assert nach_id[id_termin]["category"] == "termin"
    assert nach_id[id_termin]["ereignis_datum"] == "2026-11-02"
    assert nach_id[id_fakt]["category"] == "fakt"
    assert nach_id[id_vorliebe]["category"] == "zustand"
    assert all(e["history"] == [] for e in nachher)
    assert all(e["importance"] == 3 for e in nachher)

    # Zweiter Lauf ist ein No-Op (idempotent).
    bericht = memory_mod.memory_service.migriere_bestand(nur_zeigen=True, heute=HEUTE)
    assert bericht["geaendert"] == 0


def test_migration_fuellt_fehlende_felder_ohne_zu_loeschen(speicher):
    """Kaputte/unvollständige Einträge: auffüllen, nie entfernen."""
    speicher._memories = [
        {"id": "a", "content": "Oma Helga ist meine Oma.", "timestamp": "2026-01-01T00:00:00"},
        {"id": "b", "content": "Notiz ohne alles", "category": "context", "importance": 99},
    ]
    bericht = memory_mod.memory_service.migriere_bestand(nur_zeigen=False, heute=HEUTE)
    assert bericht["vorher"] == 2 and bericht["nachher"] == 2
    nach_id = {e["id"]: e for e in speicher.get_all_memories(limit=10)}
    assert nach_id["a"]["category"] == "fakt"
    assert nach_id["a"]["importance"] == 3
    assert nach_id["a"]["history"] == []
    assert nach_id["b"]["category"] == "zustand"
    assert nach_id["b"]["importance"] == 3        # 99 war ungültig


# ── (i) Löschen kommt nirgends automatisch vor ────────────────────────

def test_loeschen_kommt_nirgends_automatisch_vor(speicher):
    """Kein Weg, der beim Chatten läuft, löscht von selbst.

    Geprüft am Quelltext der Wege selbst - plus verhaltensgeprüft: Nach einer
    Korrektur ist nichts verschwunden, und auch das Aufräumen fasst eine
    Korrektur nicht an (sie ist keine Doppelung).
    """
    verboten = ("delete_memory", "clear_all", "clear_memories")
    for name in ("store_memory", "retrieve_relevant_memories",
                 "extract_and_store_memories", "migriere_bestand",
                 "erklaere_begriff", "_loese_ab"):
        quelle = inspect.getsource(getattr(memory_mod.MemoryService, name))
        for wort in verboten:
            assert wort not in quelle, f"{name} enthält {wort}"

    memory_mod.memory_service.store_memory(content="Ich habe einen Hund namens Rex.")
    memory_mod.memory_service.store_memory(content="Ich habe einen Hund namens Max.")
    bericht = memory_mod.memory_service.entferne_wiederholungen(nur_zeigen=False)
    assert bericht["entfernt"] == 0            # eine Korrektur ist keine Doppelung
    assert speicher.count() == 1
    eintrag = speicher.get_all_memories(limit=10)[0]
    assert eintrag["content"] == "Ich habe einen Hund namens Max."
    assert eintrag["history"][0]["inhalt"] == "Ich habe einen Hund namens Rex."

    bericht = memory_mod.memory_service.migriere_bestand(nur_zeigen=False, heute=HEUTE)
    assert speicher.count() == 1
    assert speicher.get_all_memories(limit=10)[0]["history"][0]["inhalt"] == \
        "Ich habe einen Hund namens Rex."
    assert bericht["nachher"] == 1


# ── Sanftes Vergessen (Entscheidung 3): zurücktreten, nie verschwinden ─

def test_alte_eintraege_treten_zurueck_verschwinden_aber_nicht():
    frisch = memory_mod._alter_abzug("2026-09-25T08:00:00", HEUTE)
    mittel = memory_mod._alter_abzug("2026-04-01T08:00:00", HEUTE)
    alt = memory_mod._alter_abzug("2024-01-01T08:00:00", HEUTE)
    assert frisch == 0.0
    assert mittel < 0 and alt < 0
    assert alt >= -memory_mod.ALTER_ABZUG_MAX          # gedeckelt
    assert memory_mod._alter_abzug(None, HEUTE) == 0.0  # ohne Zeitstempel kein Abzug


def test_alter_schiebt_nach_hinten_aber_entfernt_nichts(speicher):
    """Der Effekt in der Auswahl: alt tritt zurück - und ist trotzdem da."""
    for i in range(6):
        memory_mod.memory_service.store_memory(content=_testtext(i), heute=HEUTE)
    alt_id = speicher.get_all_memories(limit=10)[0]["id"]
    speicher.aktualisiere_memory(alt_id, {"timestamp": "2023-01-01T08:00:00"})

    treffer = memory_mod.memory_service.retrieve_relevant_memories("Notiz", top_k=6, heute=HEUTE)
    assert len(treffer) == 6                     # nichts entfernt
    assert treffer[-1]["id"] == alt_id           # der alte Eintrag steht hinten


# ── Einbettung: OpenRouter, kein Netz im Test ─────────────────────────

def test_einbettung_ohne_schluessel_ruft_nichts_auf(monkeypatch):
    """Ohne Schlüssel gibt es keinen Netz-Aufruf - der Aufrufer bekommt None."""
    from app.config import settings

    monkeypatch.setattr(settings, "openrouter_api_key", "")
    assert memory_mod.openrouter_vektor("Testtext") is None

    def _nie(*a, **k):  # pragma: no cover - darf nie laufen
        raise AssertionError("httpx.post wurde ohne Schlüssel aufgerufen")

    monkeypatch.setattr(memory_mod.httpx, "post", _nie)
    assert memory_mod.openrouter_vektor("Testtext") is None


def test_vektoren_anderer_laenge_werden_nicht_falsch_gerechnet(speicher):
    """Zwei Embedding-Modelle mischen sich nicht - lieber überspringen als raten."""
    speicher.add_memory(content="Eintrag mit kleinem Vektor", embedding=[0.1, 0.2, 0.3])
    speicher.add_memory(content="Eintrag mit großem Vektor",
                        embedding=[0.1] * 64)
    score = speicher.vektor_score([0.5] * 64)
    assert list(score.values())[0] > 0
    assert len(score) == 1                      # nur der passende Vektor zählt


# ── Der Weg des Chats: Extraktion vergibt Art und Zeitbezug ───────────

def test_extraktion_vergibt_art_und_datum(speicher, monkeypatch):
    """Der LLM-Auftrag bleibt Sätze-only; die Art erkennt der Dienst danach.

    Damit bekommt ein Termin aus dem echten Chat seinen Zeitbezug - sonst
    bliebe er für immer „aktuell".
    """
    monkeypatch.setattr(
        llm_service, "extract_memories",
        lambda user_message, llm_reply: [
            "Am 2. November Zahnarzttermin mit Zahnreinigung",
            "Oma Helga ist meine Oma.",
        ],
    )
    ids = memory_mod.memory_service.extract_and_store_memories(
        "Ich habe einen Termin", "Notiert.", heute=HEUTE
    )
    assert len(ids) == 2
    eintraege = speicher.get_all_memories(limit=10)
    assert eintraege[0]["category"] == "termin"
    assert eintraege[0]["ereignis_datum"] == "2026-11-02"
    assert eintraege[0]["importance"] == 4        # Termine wiegen mehr
    assert eintraege[1]["category"] == "fakt"
    assert eintraege[1]["importance"] == 3


def test_korrektur_ueber_die_api_legt_keine_zweite_erinnerung_an(speicher):
    """Derselbe Weg wie im Blatt: POST /api/memory zweimal."""
    from app.models import MemoryCreate
    from app.router import memory as memory_router

    for text in ("Ich arbeite seit zehn Jahren in der Automatisierung.",
                 "Ich arbeite seit elf Jahren in der Automatisierung."):
        asyncio.run(memory_router.create_memory(MemoryCreate(content=text)))

    assert speicher.count() == 1
    antwort = asyncio.run(memory_router.list_memories(limit=50))
    assert antwort.total == 1
    eintrag = antwort.memories[0]
    assert eintrag.content.endswith("elf Jahren in der Automatisierung.")
    assert [h.inhalt for h in eintrag.history] == \
        ["Ich arbeite seit zehn Jahren in der Automatisierung."]
    assert eintrag.history[0].abgeloest_am        # wann sie abgelöst wurde
    assert eintrag.history[0].geschrieben_am      # wann sie selbst geschrieben wurde
    assert eintrag.art == eintrag.category == "fakt"
    assert eintrag.art_text == "Fakt"


# ── Arten erkennen (fakt / termin / zustand) ──────────────────────────

def test_arten_werden_aus_dem_inhalt_erkannt():
    """Die drei Arten, die Sebastian unterscheiden will."""
    assert memory_mod.erkenne_art("Oma Helga ist meine Oma.", HEUTE)["art"] == "fakt"
    assert memory_mod.erkenne_art("Meine Schwester heißt Anna.", HEUTE)["art"] == "fakt"

    termin = memory_mod.erkenne_art("Am 2. November Zahnarzttermin mit Zahnreinigung", HEUTE)
    assert termin["art"] == "termin"
    assert termin["ereignis_datum"] == "2026-11-02"
    assert termin["wichtig"] == 4

    dauer = memory_mod.erkenne_art("Geburtstag von Oma Helga: 3. Mai 1948", HEUTE)
    assert dauer["art"] == "termin"
    assert dauer["wiederkehrend"] is True
    assert dauer["ereignis_datum"] is None       # kein Ablaufdatum

    zustand = memory_mod.erkenne_art("Arbeitet an einem eigenen Agenten", HEUTE)
    assert zustand["art"] == "zustand"


def test_datumserkennung_erfindet_nichts():
    """Nur drei Formen werden erkannt; ohne Datum kommt None (kein Raten)."""
    assert memory_mod._erkenne_datum("Termin 2026-11-02", HEUTE) == "2026-11-02"
    assert memory_mod._erkenne_datum("Termin am 02.11.2026", HEUTE) == "2026-11-02"
    assert memory_mod._erkenne_datum("Termin am 2. November 2026", HEUTE) == "2026-11-02"
    # Ohne Jahr: das nächste Vorkommen (dezembergesagt = nächstes Jahr).
    assert memory_mod._erkenne_datum("Zahnarzt am 2. November", HEUTE) == "2026-11-02"
    assert memory_mod._erkenne_datum("Winterdienst am 3. Januar", HEUTE) == "2027-01-03"
    assert memory_mod._erkenne_datum("kein Datum im Text", HEUTE) is None
    assert memory_mod._erkenne_datum("32.13.2026", HEUTE) is None      # unmöglich
