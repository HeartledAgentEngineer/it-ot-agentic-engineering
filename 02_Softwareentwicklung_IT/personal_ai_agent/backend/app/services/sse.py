"""SSE-Helfer (aus chat.py extrahiert — Refactoring).

- `_sse(payload)` → ein Server-Sent-Events-Datenblock.
- `strom_auftrag_live(...)` → offene Live-Strecke für Track C im Chat-Stream
  (liest das Auftragsbuch periodisch, reicht Zwischenmeldungen als eigene
  `gedanke`-Ereignisse durch, beendet mit `done` + Endergebnis).
"""

import json
import time
from typing import Any, Dict, Iterator

from app.services.auftrag_service import auftrag_service
from app.services.memory_service import memory_service


def _sse(payload: Dict[str, Any]) -> str:
    """Ein Ereignis im Server-Sent-Events-Format."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def strom_auftrag_live(auftrag_id, conversation_id, reply_text) -> Iterator[str]:
    """Offene Live-Strecke für Track C im Chat-Stream.

    Identische Logik wie die frühere _strom_auftrag_live in chat.py. Der
    lokale Hermes schreibt Gedanken als status_meldungen ins Auftragsbuch;
    dieser Generator reicht sie als eigene `gedanke`-Ereignisse durch und
    beendet mit `done` + Endergebnis, sobald der Auftrag fertig/fehlgeschlagen
    ist. Mit Keepalive gegen Browser-/Proxy-Timeouts.
    """
    yield _sse({"delta": reply_text})
    gesehen = 0
    letzte_aktivitaet = time.time()
    while True:
        try:
            aktuell = auftrag_service.einzeln(auftrag_id)
        except Exception:
            aktuell = None
        status = (aktuell or {}).get("status")
        meldungen = (aktuell or {}).get("status_meldungen", []) or []

        for meldung in meldungen[gesehen:]:
            gesehen += 1
            if meldung:
                yield _sse({"art": "gedanke", "text": meldung})
                letzte_aktivitaet = time.time()

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
            })
            return

        if time.time() - letzte_aktivitaet >= 15:
            yield ": keepalive\n\n"
            letzte_aktivitaet = time.time()

        time.sleep(1)
