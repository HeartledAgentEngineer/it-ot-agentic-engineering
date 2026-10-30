"""
Foto- und Beschreibungs-Migrator fuer SQLite (life_archive.db).

Ueberfuehrt:
  - bild_beschreibungen.jsonl (Standard-Beschreibungen, Gemini 2.5 Flash)
  - bild_beschreibungen_reich.jsonl (Reiche Beschreibungen, Gemini 3.8 Flash)
  in die SQLite-Tabelle `photos` von `life_archive.db`.

Eigenschaften:
  - Idempotent (UPSERT): Aktualisiert bestehende Eintraege sauber.
  - Streaming im Stapel (Batch von je 1000 Zeilen): schont den RAM.
  - Fehlerresistent: defekte Zeilen werden protokolliert, nicht abgebrochen.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

# Fuege backend zum Suchpfad hinzu, um LifeArchiveDB zu importieren
PROJEKT_WURZEL = Path(__file__).resolve().parents[2]
BACKEND_ORDNER = PROJEKT_WURZEL / "backend"
if str(BACKEND_ORDNER) not in sys.path:
    sys.path.insert(0, str(BACKEND_ORDNER))

from app.db.life_archive import LifeArchiveDB, migriere_beschreibungen


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


def zeilen_lesen(pfad: Path) -> Generator[Tuple[int, Dict[str, Any]], None, None]:
    """Liest eine JSONL-Datei zeilenweise ein."""
    if not pfad.is_file():
        logger.warning("Datei existiert nicht: %s", pfad)
        return

    with pfad.open("r", encoding="utf-8", errors="replace") as f:
        for nr, zeile in enumerate(f, start=1):
            zeile_s = zeile.strip()
            if not zeile_s:
                continue
            try:
                daten = json.loads(zeile_s)
                if isinstance(daten, dict) and "fileid" in daten:
                    yield nr, daten
            except Exception as e:
                logger.debug("Zeile %d in %s uebersprungen: %s", nr, pfad.name, e)


def migriere_beschreibungen(
    db: LifeArchiveDB,
    basis_pfad: Optional[Path] = None,
    reich_pfad: Optional[Path] = None,
    limit: Optional[int] = None,
) -> Dict[str, int]:
    """Importiert Standard- und reiche Beschreibungen in life_archive.db."""
    erfolg_basis = 0
    erfolg_reich = 0

    # 1. Basis-Beschreibungen importieren
    if basis_pfad and basis_pfad.is_file():
        logger.info("Importiere Basis-Beschreibungen aus %s ...", basis_pfad)
        stapel: List[Dict[str, Any]] = []
        for nr, d in zeilen_lesen(basis_pfad):
            stapel.append({
                "fileid": d["fileid"],
                "datei": d.get("datei"),
                "jahr": d.get("jahr"),
                "monat": d.get("monat"),
                "tag": d.get("tag"),
                "ordner": d.get("ordner"),
                "beschreibung": d.get("beschreibung"),
                "modell_basis": d.get("modell"),
                "kosten_usd": d.get("kosten_usd"),
                "bogen_id": d.get("bogen_id"),
                "import_zeit": d.get("zeit"),
            })
            if len(stapel) >= BATCH_SIZE:
                db.upsert_photos_batch(stapel)
                erfolg_basis += len(stapel)
                stapel = []
                logger.info("Basis-Fortschritt: %d Fotos importiert...", erfolg_basis)
            if limit and erfolg_basis + len(stapel) >= limit:
                break

        if stapel:
            db.upsert_photos_batch(stapel)
            erfolg_basis += len(stapel)

        logger.info("Basis-Import abgeschlossen: %d Fotos eingetragen.", erfolg_basis)

    # 2. Reiche Beschreibungen importieren (Upsert in dasselbe Foto)
    if reich_pfad and reich_pfad.is_file():
        logger.info("Importiere reiche Beschreibungen aus %s ...", reich_pfad)
        stapel = []
        for nr, d in zeilen_lesen(reich_pfad):
            stapel.append({
                "fileid": d["fileid"],
                "datei": d.get("datei"),
                "jahr": d.get("jahr"),
                "monat": d.get("monat"),
                "tag": d.get("tag"),
                "ordner": d.get("ordner"),
                "beschreibung_reich": d.get("beschreibung"),
                "modell_reich": d.get("modell"),
                "kosten_usd": d.get("kosten_usd"),
                "bogen_id": d.get("bogen_id"),
                "import_zeit": d.get("zeit"),
            })
            if len(stapel) >= BATCH_SIZE:
                db.upsert_photos_batch(stapel)
                erfolg_reich += len(stapel)
                stapel = []
                logger.info("Reich-Fortschritt: %d Fotos aktualisiert...", erfolg_reich)
            if limit and erfolg_reich + len(stapel) >= limit:
                break

        if stapel:
            db.upsert_photos_batch(stapel)
            erfolg_reich += len(stapel)

        logger.info("Reich-Import abgeschlossen: %d Fotos aktualisiert.", erfolg_reich)

    return {"basis_importiert": erfolg_basis, "reich_importiert": erfolg_reich}


def main() -> None:
    parser = argparse.ArgumentParser(description="Migriert Bildbeschreibungen in SQLite (life_archive.db)")
    parser.add_argument("--db", default="life_archive.db", help="Pfad zur Zieldatenbank")
    parser.add_argument("--basis", help="Pfad zu bild_beschreibungen.jsonl")
    parser.add_argument("--reich", help="Pfad zu bild_beschreibungen_reich.jsonl")
    parser.add_argument("--limit", type=int, help="Maximal zu verarbeitende Zeilen (Testmodus)")
    args = parser.parse_args()

    db_pfad = Path(args.db).resolve()
    logger.info("Verwende Datenbank: %s", db_pfad)
    db = LifeArchiveDB(db_pfad)

    t0 = time.perf_counter()
    basis_pfad = Path(args.basis).resolve() if args.basis else None
    reich_pfad = Path(args.reich).resolve() if args.reich else None

    ergebnis = migriere_beschreibungen(db, basis_pfad, reich_pfad, limit=args.limit)
    stats = db.get_stats()
    dauer = time.perf_counter() - t0

    logger.info("Migration fertig in %.2f Sekunden.", dauer)
    logger.info("Ergebnis: %s", ergebnis)
    logger.info("Aktueller DB-Stand: %s", stats)


if __name__ == "__main__":
    main()
