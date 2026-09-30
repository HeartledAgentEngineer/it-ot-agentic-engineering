"""Die Werkzeug-Schleife (Harness) fuer Tool Use (Spec: docs/spec-tool-use-v1.md).

Ablauf je Runde: Modell gestreamt aufrufen -> Text-Haeppchen sofort weitergeben,
Werkzeug-Aufrufe (``tool_calls``) einsammeln -> ausfuehren -> Ergebnisse als
``role=tool`` anhaengen -> naechste Runde. Ruft das Modell kein Werkzeug mehr
auf, ist die Antwort fertig. Nach ``max_runden`` Runden mit Werkzeugen folgt ein
letzter Aufruf mit ``tool_choice="none"`` - das Modell muss dann antworten.

Der Modellaufruf ist einsetzbar (``erstellen``), damit die Schleife ohne Netz mit
einem simulierten Modell getestet werden kann. ``erstellen(messages, tool_choice)``
liefert die Stream-Haeppchen im OpenAI-Format (``chunk.choices[0].delta``).

Ereignisse, die die Schleife liefert:
- ``{"delta": str}``    Antworttext
- ``{"sources": list}`` Fundstellen der Websuche (ueber ``quellen_aus``)
- ``{"status": str}``   Statuszeile fuer die Oberflaeche („🔧 …")
- ``{"werkzeug": {...}}`` Protokoll je Aufruf (Name, ok, Dauer, Zeichen)
- ``{"bild": {...}}``   Bild, das ein Werkzeug geladen hat (Vorschau/Verlauf)
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional

from app.services import werkzeuge

logger = logging.getLogger(__name__)

MAX_RUNDEN = 5
MAX_AUFRUFE_JE_RUNDE = 4
MAX_BILDER_JE_RUNDE = 3


def _feld(obj: Any, name: str) -> Any:
    """Feld aus SDK-Objekt oder dict lesen."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _denkteile_mischen(gesammelt: Dict[Any, Dict[str, Any]], teile: Any) -> None:
    """``reasoning_details``-Haeppchen nach (index, type) zusammensetzen.

    Manche Anbieter verlangen, dass die Denk-Bloecke einer Runde mit dem
    Werkzeug-Aufruf zurueckgeschickt werden; sonst lehnen sie die Folgerunde ab.
    """
    for teil in teile or []:
        if isinstance(teil, dict):
            daten = dict(teil)
        elif hasattr(teil, "model_dump"):
            daten = teil.model_dump()
        else:
            continue
        schluessel = (daten.get("index", 0), daten.get("type"))
        ziel = gesammelt.setdefault(schluessel, {})
        for k, v in daten.items():
            if k in ("text", "summary", "data") and isinstance(v, str):
                ziel[k] = (ziel.get(k) or "") + v
            elif v is not None and k not in ziel:
                ziel[k] = v


def laufe(
    erstellen: Callable[[List[Dict[str, Any]], Optional[str]], Iterable[Any]],
    messages: List[Dict[str, Any]],
    ausfuehren: Callable[[str, Any], "werkzeuge.Ergebnis"] = werkzeuge.ausfuehren,
    status_text: Callable[[str], str] = werkzeuge.status_text,
    quellen_aus: Optional[Callable[[Any], List[Dict[str, str]]]] = None,
    max_runden: int = MAX_RUNDEN,
    max_aufrufe: int = MAX_AUFRUFE_JE_RUNDE,
) -> Iterator[Dict[str, Any]]:
    """Schleife ausfuehren; ``messages`` wird dabei fortgeschrieben."""
    gesehen: set = set()
    runde = 0
    while True:
        # Nach max_runden Runden mit Werkzeugen: Antwort erzwingen.
        erzwingen = runde >= max_runden
        text_teile: List[str] = []
        aufrufe: Dict[int, Dict[str, str]] = {}
        denken: Dict[Any, Dict[str, Any]] = {}

        for chunk in erstellen(messages, "none" if erzwingen else None):
            wahl = (_feld(chunk, "choices") or [None])[0]
            delta = _feld(wahl, "delta")
            if delta is None:
                continue
            if quellen_aus is not None:
                neue = [q for q in (quellen_aus(_feld(delta, "annotations")) or [])
                        if q.get("url") not in gesehen]
                if neue:
                    gesehen.update(q.get("url") for q in neue)
                    yield {"sources": neue}
            stueck = _feld(delta, "content")
            if stueck:
                text_teile.append(stueck)
                yield {"delta": stueck}
            _denkteile_mischen(denken, _feld(delta, "reasoning_details"))
            for tc in _feld(delta, "tool_calls") or []:
                idx = _feld(tc, "index")
                idx = idx if isinstance(idx, int) else len(aufrufe)
                eintrag = aufrufe.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                if _feld(tc, "id"):
                    eintrag["id"] = _feld(tc, "id")
                fn = _feld(tc, "function")
                if _feld(fn, "name"):
                    eintrag["name"] = _feld(fn, "name")
                if _feld(fn, "arguments"):
                    eintrag["arguments"] += _feld(fn, "arguments")

        if erzwingen or not aufrufe:
            return

        runde += 1
        liste = [aufrufe[i] for i in sorted(aufrufe)]
        for nr, a in enumerate(liste):
            if not a["id"]:
                a["id"] = f"aufruf_{runde}_{nr}"
        assistent: Dict[str, Any] = {
            "role": "assistant",
            "content": "".join(text_teile) or None,
            "tool_calls": [
                {"id": a["id"], "type": "function",
                 "function": {"name": a["name"], "arguments": a["arguments"] or "{}"}}
                for a in liste
            ],
        }
        if denken:
            assistent["reasoning_details"] = list(denken.values())
        messages.append(assistent)

        bilder: List[Dict[str, str]] = []
        for nr, a in enumerate(liste):
            if nr >= max_aufrufe:
                messages.append({"role": "tool", "tool_call_id": a["id"],
                                 "content": f"Übersprungen: höchstens {max_aufrufe} "
                                            "Werkzeuge je Runde. Bei Bedarf in der "
                                            "nächsten Runde erneut aufrufen."})
                continue
            yield {"status": status_text(a["name"])}
            start = time.monotonic()
            ergebnis = ausfuehren(a["name"], a["arguments"])
            dauer_ms = int((time.monotonic() - start) * 1000)
            logger.info("Werkzeug %s: ok=%s %d ms %d Zeichen %d Bilder", a["name"],
                        ergebnis.ok, dauer_ms, len(ergebnis.text), len(ergebnis.bilder))
            yield {"werkzeug": {"name": a["name"], "ok": ergebnis.ok, "ms": dauer_ms,
                                "zeichen": len(ergebnis.text), "bilder": len(ergebnis.bilder)}}
            messages.append({"role": "tool", "tool_call_id": a["id"], "content": ergebnis.text})
            for b in ergebnis.bilder:
                if len(bilder) < MAX_BILDER_JE_RUNDE and b.get("data_url"):
                    bilder.append(b)
                    yield {"bild": {"data_url": b["data_url"], "pfad": b.get("pfad")}}

        if bilder:
            # Tool-Nachrichten tragen nur Text: die Bilder folgen als eigene Nachricht.
            teile: List[Dict[str, Any]] = [{
                "type": "text",
                "text": "[Bilder aus datei_ansehen: "
                        + ", ".join((b.get("pfad") or "?").split("/")[-1] for b in bilder)
                        + " — beschreibe sie anhand dessen, was du siehst.]",
            }]
            teile += [{"type": "image_url", "image_url": {"url": b["data_url"], "detail": "auto"}}
                      for b in bilder]
            messages.append({"role": "user", "content": teile})
