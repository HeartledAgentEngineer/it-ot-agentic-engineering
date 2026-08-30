"""Tests für die Auftragserkennung (Fehlklassifikation von Meta-Gesprächen)."""
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services.auftrags_erkennung import ist_auftrag  # noqa: E402


def test_meta_kommunikation_ist_kein_auftrag():
    """Meta-Gespräch (Lob über Hermes/Agent) darf NICHT als Coding erkannt werden."""
    msg = "Super, du hast was geschafft. Das sieht doch gut aus. Da ist quasi immer noch ein kleines Problem mit der Kommunikation zwischen Hermes und diesem Agenten hier."
    ok, _, _, _ = ist_auftrag(msg)
    assert ok is False, "Meta-Gespräch wurde fälschlich als Coding-Auftrag erkannt"


def test_frage_nach_zustand_kein_auftrag():
    ok, _, _, _ = ist_auftrag("Wie ist der aktuelle Stand des Projekts?")
    assert ok is False


def test_echter_coding_auftrag_erkannt():
    ok, _, kat, _ = ist_auftrag("Baue einen neuen /health-Endpoint in der FastAPI-App")
    assert ok is True
    assert kat in ("feature", "bug", "refactor", "frage")


def test_lese_frage_ohne_arbeitsverb_kein_auftrag():
    """'Lies den Inhalt meiner Lebenslauf-Datei' ist EINE FRAGE (Datei lesen),
    kein Coding-Auftrag. Regression: Der Tautologie-Bug (hat_verb immer True)
    delegierte sie früher fälschlich an Hermes − der Agent fand die Datei in
    seiner Umgebung nicht und sagte 'musst du hochladen'."""
    ok, _, _, _ = ist_auftrag(
        "Lies den Inhalt meiner Lebenslauf-Datei und fasse die wichtigsten Stationen zusammen."
    )
    assert ok is False
    ok, _, _, _ = ist_auftrag("Was steht in meinem Lebenslauf?")
    assert ok is False


def test_auftrags_verb_erkennen_echt():
    """Ein Auftrags-Verb im Satz (nicht Satzanfang) wird erkannt.
    'bitte baue' beginnt nicht mit dem Verb, das `startswith`-Signal greift
    also nicht — der Wort-Check muss das Verb 'baue' trotzdem finden."""
    ok, _, _, _ = ist_auftrag("Bitte baue einen Test im Backend.")
    assert ok is True
