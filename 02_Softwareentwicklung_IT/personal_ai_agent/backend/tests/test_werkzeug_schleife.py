"""Tests: Werkzeug-Schleife (Harness) fuer Tool Use (Spec docs/spec-tool-use-v1.md).

Das Modell ist simuliert: ``Drehbuch`` liefert je Aufruf vorbereitete
Stream-Haeppchen im OpenAI-Format (als dicts). Kein Netz, keine Kosten.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_werkzeug_schleife.py -q
"""
from __future__ import annotations

import json
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import werkzeug_schleife as ws  # noqa: E402
from app.services.werkzeuge import Ergebnis  # noqa: E402


def text(t):
    return {"choices": [{"delta": {"content": t}}]}


def aufruf(idx, name=None, args=None, id_=None):
    fn = {}
    if name:
        fn["name"] = name
    if args is not None:
        fn["arguments"] = args
    tc = {"index": idx, "function": fn}
    if id_:
        tc["id"] = id_
    return {"choices": [{"delta": {"tool_calls": [tc]}}]}


class Drehbuch:
    """Simuliertes Modell: je Aufruf die naechste Liste von Haeppchen."""

    def __init__(self, *runden):
        self.runden = list(runden)
        self.aufrufe = []  # (Kopie der messages, tool_choice)

    def __call__(self, messages, tool_choice):
        self.aufrufe.append((json.loads(json.dumps(messages)), tool_choice))
        return iter(self.runden.pop(0) if self.runden else [text("(Ende)")])


def ausfuehrer(protokoll, antworten=None):
    def f(name, args):
        protokoll.append((name, json.loads(args or "{}")))
        return (antworten or {}).get(name, Ergebnis(f"Ergebnis von {name}"))
    return f


def ereignisse(modell, messages=None, **kw):
    msgs = messages if messages is not None else [{"role": "user", "content": "Frage"}]
    return list(ws.laufe(modell, msgs, **kw)), msgs


def test_ohne_werkzeug_nur_text():
    modell = Drehbuch([text("Hallo "), text("Sebastian")])
    evs, msgs = ereignisse(modell, ausfuehren=ausfuehrer([]))
    assert "".join(e.get("delta", "") for e in evs) == "Hallo Sebastian"
    assert len(modell.aufrufe) == 1 and modell.aufrufe[0][1] is None
    assert len(msgs) == 1  # nichts angehaengt


def test_ein_werkzeug_dann_antwort():
    protokoll = []
    modell = Drehbuch(
        # Argumente kommen in Stuecken, id und Name nur im ersten Haeppchen.
        [aufruf(0, "dateien_suchen", '{"art": ', "c1"), aufruf(0, args='"bild"}')],
        [text("Dein letztes Foto zeigt eine Tabelle.")],
    )
    evs, msgs = ereignisse(modell, ausfuehren=ausfuehrer(protokoll))
    assert protokoll == [("dateien_suchen", {"art": "bild"})]
    assert any(e.get("status") for e in evs)
    assert any(e.get("werkzeug", {}).get("name") == "dateien_suchen" for e in evs)
    assert msgs[1]["role"] == "assistant" and msgs[1]["tool_calls"][0]["id"] == "c1"
    assert msgs[1]["tool_calls"][0]["function"]["arguments"] == '{"art": "bild"}'
    assert msgs[2] == {"role": "tool", "tool_call_id": "c1", "content": "Ergebnis von dateien_suchen"}
    # Die zweite Runde sieht das Werkzeug-Ergebnis.
    assert modell.aufrufe[1][0][2]["role"] == "tool"
    assert "Tabelle" in "".join(e.get("delta", "") for e in evs)


def test_zwei_werkzeuge_in_einer_runde_der_reihe_nach():
    protokoll = []
    modell = Drehbuch(
        [aufruf(1, "archiv_suchen", '{"frage":"Momo"}', "b"),
         aufruf(0, "erinnerungen_suchen", '{"frage":"Momo"}', "a")],
        [text("fertig")],
    )
    evs, msgs = ereignisse(modell, ausfuehren=ausfuehrer(protokoll))
    assert [p[0] for p in protokoll] == ["erinnerungen_suchen", "archiv_suchen"]  # nach index
    assert [m["tool_call_id"] for m in msgs if m["role"] == "tool"] == ["a", "b"]


def test_fehlende_id_wird_ergaenzt():
    modell = Drehbuch([aufruf(0, "personen_liste", "{}")], [text("ok")])
    _, msgs = ereignisse(modell, ausfuehren=ausfuehrer([]))
    tc_id = msgs[1]["tool_calls"][0]["id"]
    assert tc_id and msgs[2]["tool_call_id"] == tc_id


def test_obergrenze_aufrufe_je_runde():
    protokoll = []
    viele = [aufruf(i, "personen_liste", "{}", f"id{i}") for i in range(6)]
    modell = Drehbuch(viele, [text("ok")])
    _, msgs = ereignisse(modell, ausfuehren=ausfuehrer(protokoll), max_aufrufe=4)
    assert len(protokoll) == 4
    tools = [m for m in msgs if m["role"] == "tool"]
    assert len(tools) == 6  # jeder Aufruf bekommt eine Antwort, sonst lehnt der Anbieter ab
    assert "Übersprungen" in tools[5]["content"]


def test_obergrenze_runden_erzwingt_antwort():
    protokoll = []
    endlos = [[aufruf(0, "personen_liste", "{}", f"r{i}")] for i in range(10)]
    modell = Drehbuch(*endlos)
    ereignisse(modell, ausfuehren=ausfuehrer(protokoll), max_runden=2)
    assert len(protokoll) == 2
    assert len(modell.aufrufe) == 3
    assert modell.aufrufe[-1][1] == "none"  # letzter Aufruf: Werkzeuge aus


def test_bild_aus_werkzeug_folgt_als_bildnachricht():
    bild = Ergebnis("Bild geladen", bilder=[{"data_url": "data:image/jpeg;base64,AAAA",
                                              "pfad": "/sdcard/DCIM/IMG_1.jpg"}])
    modell = Drehbuch([aufruf(0, "datei_ansehen", '{"pfad":"/sdcard/DCIM/IMG_1.jpg"}', "x")],
                      [text("Ich sehe eine Tabelle.")])
    evs, msgs = ereignisse(modell, ausfuehren=ausfuehrer([], {"datei_ansehen": bild}))
    assert msgs[2]["role"] == "tool" and "AAAA" not in msgs[2]["content"]
    assert msgs[3]["role"] == "user"
    teile = msgs[3]["content"]
    assert teile[1] == {"type": "image_url",
                        "image_url": {"url": "data:image/jpeg;base64,AAAA", "detail": "auto"}}
    assert "IMG_1.jpg" in teile[0]["text"]
    assert [e["bild"]["pfad"] for e in evs if "bild" in e] == ["/sdcard/DCIM/IMG_1.jpg"]


def test_text_vor_werkzeug_bleibt_im_verlauf():
    modell = Drehbuch([text("Ich schaue nach. "), aufruf(0, "personen_liste", "{}", "p")],
                      [text("Fertig.")])
    evs, msgs = ereignisse(modell, ausfuehren=ausfuehrer([]))
    assert msgs[1]["content"] == "Ich schaue nach. "
    assert "".join(e.get("delta", "") for e in evs) == "Ich schaue nach. Fertig."


def test_denkbloecke_werden_zurueckgegeben():
    denk1 = {"choices": [{"delta": {"reasoning_details": [
        {"type": "reasoning.text", "index": 0, "text": "Ich brauche "}]}}]}
    denk2 = {"choices": [{"delta": {"reasoning_details": [
        {"type": "reasoning.text", "index": 0, "text": "die Dateien."}]}}]}
    modell = Drehbuch([denk1, denk2, aufruf(0, "dateien_suchen", "{}", "d")], [text("ok")])
    _, msgs = ereignisse(modell, ausfuehren=ausfuehrer([]))
    assert msgs[1]["reasoning_details"] == [
        {"type": "reasoning.text", "index": 0, "text": "Ich brauche die Dateien."}]


def test_quellen_der_websuche_ohne_doppelte():
    def quellen_aus(annotations):
        return [{"url": a} for a in (annotations or [])]
    modell = Drehbuch([
        {"choices": [{"delta": {"annotations": ["u1"], "content": "a"}}]},
        {"choices": [{"delta": {"annotations": ["u1", "u2"], "content": "b"}}]},
    ])
    evs, _ = ereignisse(modell, ausfuehren=ausfuehrer([]), quellen_aus=quellen_aus)
    assert [q["url"] for e in evs if "sources" in e for q in e["sources"]] == ["u1", "u2"]


def test_leere_haeppchen_stoeren_nicht():
    modell = Drehbuch([{"choices": []}, {"choices": [{"delta": None}]}, text("ok")])
    evs, _ = ereignisse(modell, ausfuehren=ausfuehrer([]))
    assert [e["delta"] for e in evs if "delta" in e] == ["ok"]
