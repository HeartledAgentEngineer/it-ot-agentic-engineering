"""Tests für das Entscheidungsprotokoll des Wechselassistenten (`protokoll.jsonl`, G10)."""
from __future__ import annotations

import json

from master_schalter import protokoll


def test_schreiben_und_lesen_roundtrip(umgebung):
    assert protokoll.lesen() == []
    protokoll.schreiben("v-1", "engineering", "angelegt", "claude -> codex")
    protokoll.schreiben("v-1", "engineering", "rolle_gesetzt")

    eintraege = protokoll.lesen()

    assert [(e["vorgang"], e["thema"], e["entscheidung"], e["grund"]) for e in eintraege] == [
        ("v-1", "engineering", "angelegt", "claude -> codex"), ("v-1", "engineering", "rolle_gesetzt", "")]
    assert all(e["zeit"] for e in eintraege) and set(eintraege[0]) == {"zeit", "vorgang", "thema", "entscheidung", "grund"}
    assert protokoll.datei().name == "protokoll.jsonl"
    assert len(protokoll.datei().read_text(encoding="utf-8").splitlines()) == 2


def test_lesen_begrenzt_auf_die_letzten_eintraege_und_ueberspringt_kaputtes(umgebung):
    for nr in range(5):
        protokoll.schreiben(f"v-{nr}", "engineering", "angelegt")
    with open(protokoll.datei(), "a", encoding="utf-8") as f:
        f.write("das ist kein json\n[1, 2]\n")

    assert [e["vorgang"] for e in protokoll.lesen(2)] == ["v-3", "v-4"]
    assert len(protokoll.lesen(100)) == 5
    assert protokoll.lesen(0) == []


def test_schreibfehler_werden_geschluckt(umgebung):
    protokoll.datei().mkdir()                                     # an einen Ordner lässt sich nichts anhängen
    protokoll.schreiben("v-1", "engineering", "angelegt")         # darf nicht werfen
    assert protokoll.lesen() == []


def test_langer_grund_wird_gekuerzt(umgebung):
    protokoll.schreiben("v-1", "engineering", "verworfen", "x" * 1000)
    assert len(json.loads(protokoll.datei().read_text(encoding="utf-8"))["grund"]) == protokoll.MAX_GRUND
