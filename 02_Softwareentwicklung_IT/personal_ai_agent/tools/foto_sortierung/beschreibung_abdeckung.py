"""Beschreibungs-Abdeckung zählen — nur Zahlen (G2, 02.11.2026).

Warum:
  Im Vollbild-Editor war die Bildbeschreibung bei manchen Bildern leer, vor allem bei
  den Seiten des digitalen Fotobuchs. Vermutung (nicht gemessen): ``bild_beschreiben.py``
  arbeitet die Sortier-CSV ab, die Fotobuch-fileids stehen dort wahrscheinlich nicht
  drin. Dieses Werkzeug misst es: Wie viele Bilder haben überhaupt eine Beschreibung,
  und wie viele der fileids im Fotobuch bzw. in den Ereignissen sind darunter?

Was es zählt (nur lesend):
  * je Beschreibungsquelle (``bild_beschreibungen*.jsonl``, ``life_archive.db``) die
    Zeilenzahl, bei der Datenbank zusätzlich die Zeilen mit Text;
  * Bilder mit Beschreibung insgesamt, getrennt nach Herkunft (ki / hand / einzel_ki);
  * fileids im Fotobuch (``fotobuch_pfad()``) und wie viele davon eine Beschreibung haben;
  * dasselbe für ``ereignisse.jsonl`` (``ereignisse_pfad()``).

Die Pfade kommen aus ``backend/app/services/erzaehl_service.py`` (Umgebungsvariablen
``ERZAEHL_EREIGNISSE_PFAD`` / ``ERZAEHL_FOTOBUCH_PFAD`` werden also respektiert) — es gibt
keinen eigenen Pfad im Werkzeug.

Datenschutz: Die Ausgabe enthält NUR Zahlen und die festen Dateinamen der Quellen — nie
eine fileid, nie einen Beschreibungstext, keinen Titel. Das Werkzeug schreibt nichts.
Es ist für den Lauf durch Hermes auf den echten Daten gedacht (``--sensibel``); Tests
laufen nur gegen erfundene Daten in ``tmp_path``.

Aufruf:
    python tools/foto_sortierung/beschreibung_abdeckung.py
Exit: 0 = gezählt (auch wenn Dateien fehlen: dann stehen Nullen da).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from typing import Any, Dict, List, Set

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent
BACKEND = os.path.join(REPO, "backend")


def _dienst():
    """``erzaehl_service`` laden (erst hier, damit der Import nur beim Zählen passiert)."""
    if BACKEND not in sys.path:
        sys.path.insert(0, BACKEND)
    from app.services import erzaehl_service
    return erzaehl_service


def _zeilen_zaehlen(pfad: str) -> int:
    """Nicht leere Zeilen einer Textdatei. Unlesbar -> 0."""
    try:
        with open(pfad, "r", encoding="utf-8", errors="ignore") as datei:
            return sum(1 for z in datei if z.strip())
    except OSError:
        return 0


def _db_zeilen(pfad: str) -> Dict[str, int]:
    """Zeilen der Tabelle ``photos`` und wie viele davon einen Beschreibungstext tragen (nur lesend)."""
    ergebnis = {"zeilen": 0, "mit_text": 0}
    try:
        with sqlite3.connect(f"file:{pfad}?mode=ro", uri=True) as conn:
            cur = conn.cursor()
            cur.execute("SELECT beschreibung, beschreibung_reich FROM photos")
            for basis, reich in cur.fetchall():
                ergebnis["zeilen"] += 1
                if (reich and str(reich).strip()) or (basis and str(basis).strip()):
                    ergebnis["mit_text"] += 1
    except Exception:
        return {"zeilen": 0, "mit_text": 0}
    return ergebnis


def _fileids(es, pfad: str) -> Dict[str, Any]:
    """Seiten/Anlässe und die Menge der verschiedenen fileids einer Ereignisdatei."""
    ereignisse, _defekt = es._datei_ereignisse_laden(pfad)
    ids: Set[int] = set()
    for e in ereignisse:
        ids.update(es._ereignis_datei_kennungen(e))
    return {"seiten": len(ereignisse), "ids": ids}


def zaehlen() -> Dict[str, Any]:
    """Alle Zahlen als Wörterbuch (keine fileids, keine Texte im Ergebnis)."""
    es = _dienst()
    es._BILDINFO_SPEICHER.clear()

    quellen: List[Dict[str, Any]] = []
    for pfad in es.beschreibungen_alle_pfade():
        quellen.append({"name": os.path.basename(pfad), "zeilen": _zeilen_zaehlen(pfad)})
    db_pfad = es.life_archive_pfad()
    if os.path.isfile(db_pfad):
        quellen.append(dict(name=os.path.basename(db_pfad), **_db_zeilen(db_pfad)))

    herkunft_je_bild = es._beschreibungen_mit_herkunft()
    herkunft = {"ki": 0, "hand": 0, "einzel_ki": 0}
    for _text, h in herkunft_je_bild.values():
        herkunft[h] = herkunft.get(h, 0) + 1

    def abdeckung(pfad: str) -> Dict[str, int]:
        info = _fileids(es, pfad)
        mit = sum(1 for i in info["ids"] if i in herkunft_je_bild)
        return {"seiten": info["seiten"], "fileids": len(info["ids"]), "mit_beschreibung": mit}

    return {
        "quellen": quellen,
        "bilder_mit_beschreibung": len(herkunft_je_bild),
        "herkunft": herkunft,
        "fotobuch": abdeckung(es.fotobuch_pfad()),
        "ereignisse": abdeckung(es.ereignisse_pfad()),
    }


def _anteil(mit: int, gesamt: int) -> str:
    return f"{100.0 * mit / gesamt:.1f} %" if gesamt else "-"


def bericht(daten: Dict[str, Any]) -> List[str]:
    """Konsolenzeilen: nur Zahlen und feste Quellnamen."""
    zeilen = ["Beschreibungs-Abdeckung (nur Zahlen)"]
    zeilen.append("Quellen:" if daten["quellen"] else "Quellen: keine Beschreibungsdatei gefunden")
    for q in daten["quellen"]:
        extra = f", davon mit Text {q['mit_text']}" if "mit_text" in q else ""
        zeilen.append(f"  {q['name']}: {q['zeilen']} Zeilen{extra}")
    h = daten["herkunft"]
    zeilen.append(
        f"Bilder mit Beschreibung gesamt: {daten['bilder_mit_beschreibung']} "
        f"(KI {h.get('ki', 0)}, von Hand {h.get('hand', 0)}, KI-Einzelvorschlag {h.get('einzel_ki', 0)})"
    )
    for titel, schluessel in (("Fotobuch", "fotobuch"), ("Ereignisse", "ereignisse")):
        d = daten[schluessel]
        zeilen.append(
            f"{titel}: {d['seiten']} Eintraege, {d['fileids']} verschiedene Bilder, "
            f"davon mit Beschreibung {d['mit_beschreibung']} ({_anteil(d['mit_beschreibung'], d['fileids'])}), "
            f"ohne {d['fileids'] - d['mit_beschreibung']}"
        )
    return zeilen


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Beschreibungs-Abdeckung zaehlen - nur lesend, nur Zahlen.")
    parser.add_argument("--json", action="store_true", help="Zahlen als JSON statt als Text")
    args = parser.parse_args(argv)
    daten = zaehlen()
    if args.json:
        print(json.dumps(daten, ensure_ascii=False, indent=2))
    else:
        print("\n".join(bericht(daten)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
