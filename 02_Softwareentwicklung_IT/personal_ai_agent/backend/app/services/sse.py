"""SSE-Helfer (aus chat.py extrahiert — Refactoring).

- `_sse(payload)` → ein Server-Sent-Events-Datenblock.
- `strom_auftrag_live(...)` → offene Live-Strecke für Track C im Chat-Stream
  (liest das Auftragsbuch periodisch, reicht Zwischenmeldungen als eigene
  `gedanke`-Ereignisse durch, beendet mit `done` + Endergebnis).
"""

import json
import time
from typing import Any, Dict, Iterator, List

from app.services.auftrag_service import auftrag_service
from app.services.memory_service import memory_service


def _sse(payload: Dict[str, Any]) -> str:
    """Ein Ereignis im Server-Sent-Events-Format."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def strom_auftrag_live(auftrag_id, conversation_id, reply_text,
                       ziel: str = "handy") -> Iterator[str]:
    """Offene Live-Strecke für Track C im Chat-Stream.

    Identische Logik wie die frühere _strom_auftrag_live in chat.py. Der
    lokale Hermes schreibt Gedanken als status_meldungen ins Auftragsbuch;
    dieser Generator reicht sie als eigene `gedanke`-Ereignisse durch und
    beendet mit `done` + Endergebnis, sobald der Auftrag fertig/fehlgeschlagen
    ist. Mit Keepalive gegen Browser-/Proxy-Timeouts.

    `ziel` (Default "handy") landet im done-Event, damit das Frontend
    anzeigen kann, wohin delegiert wurde.
    """
    yield _sse({"delta": reply_text, "auftrag_id": auftrag_id})
    # Zwischenmeldungen aus dem Auftragsbuch durchreichen.
    #
    # ACHTUNG (Root-Cause-Fix 2026-09-15): Das Auftragsbuch kappt
    # status_meldungen auf die letzten N Eintraege (auftrag_service). Ein
    # ABSOLUTER Zaehler wie frueher ("gesehen = n", dann meldungen[n:]) laeuft
    # deshalb nach N Meldungen DAUERHAFT leer: der Stream verstummt mitten im
    # Lauf, waehrend der Agent weiterarbeitet. Die Gedanken landen dann nur
    # noch im Verlauf -> der Nutzer sieht erst nach einem Reload wieder etwas
    # ("es hat irgendwann aufgehoert"). Darum den Anschluss ueber den
    # UEBERLAPP der zuletzt gesendeten Eintraege finden, statt zu zaehlen.
    gesendet_puffer: List[str] = []
    letzte_aktivitaet = time.time()
    while True:
        try:
            aktuell = auftrag_service.einzeln(auftrag_id)
        except Exception:
            aktuell = None
        status = (aktuell or {}).get("status")
        meldungen = (aktuell or {}).get("status_meldungen", []) or []

        # Anschluss suchen: so viele Eintraege am ENDE des Puffers wie am
        # ANFANG der aktuellen Liste ueberspringen (vertraegt Kappung UND
        # Laengenaenderungen; findet keinen Ueberlapp, wird neu gesendet
        # statt stumm zu bleiben).
        overlap = 0
        for k in range(min(len(gesendet_puffer), len(meldungen)), 0, -1):
            if gesendet_puffer[-k:] == meldungen[:k]:
                overlap = k
                break

        for meldung in meldungen[overlap:]:
            if meldung:
                yield _sse({"art": "gedanke", "text": meldung})
                letzte_aktivitaet = time.time()
            gesendet_puffer.append(meldung)
        if len(gesendet_puffer) > 40:
            del gesendet_puffer[:-40]

        if status in ("fertig", "fehler"):
            ergebnis = ((aktuell or {}).get("ergebnis") or "").strip()
            kopf = "✅ **Ergebnis:**" if status == "fertig" else "❌ **Fehler:**"
            if ergebnis:
                yield _sse({"delta": f"\n\n{kopf}\n" + ergebnis})
            yield _sse({
                "done": True,
                "auftrag_strecke": True,
                "conversation_id": conversation_id,
                "memories_used": 0, "memories_created": 0,
                "memory_count": memory_service.get_memory_count(),
                "archiv_used": 0, "sources": [],
                "ziel": ziel,
            })
            return

        if time.time() - letzte_aktivitaet >= 15:
            yield ": keepalive\n\n"
            letzte_aktivitaet = time.time()

        time.sleep(1)
