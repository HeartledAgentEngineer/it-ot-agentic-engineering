"""
SQLite-Datenbank fuer das persoenliche Biografie- und Foto-Archiv (life_archive.db).

Spezifikation Modul E (30.10.2026):
Tabellen:
  * photos: Einzelbild-Metadaten und KI-Beschreibungen (Standard + Reich)
  * persons: Bestaetigte Personen und Alias-Namen
  * photo_faces: Gesichtsregionen (BBox, Anteil, Erkennungsscore) je Foto
  * stories: Geschichten und Audio-Erzählungen zu Bildern und Ereignissen
  * story_links: Verknuepfungen von Geschichten mit Personen, Orten oder Bildern
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS photos (
    fileid INTEGER PRIMARY KEY,
    datei TEXT NOT NULL,
    jahr INTEGER,
    monat INTEGER,
    tag INTEGER,
    ordner TEXT,
    aufnahme_zeit TEXT,
    breite REAL,
    hoehe REAL,
    beschreibung TEXT,
    beschreibung_reich TEXT,
    modell_basis TEXT,
    modell_reich TEXT,
    kosten_usd REAL,
    bogen_id TEXT,
    import_zeit TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS persons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kennung TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    beziehung TEXT,
    vorname TEXT,
    nachname TEXT,
    spitznamen TEXT,
    erstellt_am TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS photo_faces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    photo_fileid INTEGER NOT NULL REFERENCES photos(fileid) ON DELETE CASCADE,
    person_kennung TEXT,
    face_index INTEGER NOT NULL,
    bbox_x REAL,
    bbox_y REAL,
    bbox_w REAL,
    bbox_h REAL,
    anteil REAL,
    score REAL,
    gid TEXT,
    UNIQUE(photo_fileid, face_index)
);

CREATE TABLE IF NOT EXISTS stories (
    id TEXT PRIMARY KEY,
    ereignis_kennung TEXT,
    datei_kennung INTEGER,
    text TEXT NOT NULL,
    quelle TEXT NOT NULL,
    erstellt_am TEXT NOT NULL,
    ersetzt_id TEXT
);

CREATE TABLE IF NOT EXISTS story_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    UNIQUE(story_id, target_type, target_id)
);

-- Indices fuer schnelle Suche und Joins
CREATE INDEX IF NOT EXISTS idx_photos_jahr ON photos(jahr);
CREATE INDEX IF NOT EXISTS idx_photos_datei ON photos(datei);
CREATE INDEX IF NOT EXISTS idx_photo_faces_person ON photo_faces(person_kennung);
CREATE INDEX IF NOT EXISTS idx_stories_datei ON stories(datei_kennung);
CREATE INDEX IF NOT EXISTS idx_stories_ereignis ON stories(ereignis_kennung);
CREATE INDEX IF NOT EXISTS idx_story_links_target ON story_links(target_type, target_id);
"""


def init_db(db_path: Union[str, Path]) -> sqlite3.Connection:
    """Initialisiert die SQLite-Datenbank mit dem vollständigen Schema und WAL-Modus."""
    pfad = Path(db_path)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(pfad), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    return conn


class LifeArchiveDB:
    """Verwaltet den Zugriff auf die lokale SQLite-Datenbank life_archive.db."""

    def __init__(self, db_path: Union[str, Path]) -> None:
        self.db_path = Path(db_path)
        self.conn = init_db(self.db_path)

    def close(self) -> None:
        """Schliesst die Datenbankverbindung."""
        if self.conn:
            self.conn.close()

    def upsert_photo(self, photo_data: Dict[str, Any]) -> None:
        """Fuegt ein Foto ein oder aktualisiert bestehende Felder (z.B. reiche Beschreibung)."""
        self.upsert_photos_batch([photo_data])

    def upsert_photos_batch(self, photos_list: List[Dict[str, Any]]) -> int:
        """Fuegt Fotos im Stapel ein oder aktualisiert Beschreibungen via UPSERT."""
        if not photos_list:
            return 0

        now_iso = datetime.now(timezone.utc).isoformat()
        sql = """
        INSERT INTO photos (
            fileid, datei, jahr, monat, tag, ordner, aufnahme_zeit,
            breite, hoehe, beschreibung, beschreibung_reich,
            modell_basis, modell_reich, kosten_usd, bogen_id, import_zeit
        ) VALUES (
            :fileid, :datei, :jahr, :monat, :tag, :ordner, :aufnahme_zeit,
            :breite, :hoehe, :beschreibung, :beschreibung_reich,
            :modell_basis, :modell_reich, :kosten_usd, :bogen_id, :import_zeit
        )
        ON CONFLICT(fileid) DO UPDATE SET
            datei = coalesce(excluded.datei, photos.datei),
            jahr = coalesce(excluded.jahr, photos.jahr),
            monat = coalesce(excluded.monat, photos.monat),
            tag = coalesce(excluded.tag, photos.tag),
            ordner = coalesce(excluded.ordner, photos.ordner),
            aufnahme_zeit = coalesce(excluded.aufnahme_zeit, photos.aufnahme_zeit),
            breite = coalesce(excluded.breite, photos.breite),
            hoehe = coalesce(excluded.hoehe, photos.hoehe),
            beschreibung = coalesce(excluded.beschreibung, photos.beschreibung),
            beschreibung_reich = coalesce(excluded.beschreibung_reich, photos.beschreibung_reich),
            modell_basis = coalesce(excluded.modell_basis, photos.modell_basis),
            modell_reich = coalesce(excluded.modell_reich, photos.modell_reich),
            kosten_usd = coalesce(excluded.kosten_usd, photos.kosten_usd),
            bogen_id = coalesce(excluded.bogen_id, photos.bogen_id);
        """

        eintraege = []
        for p in photos_list:
            fid = int(p["fileid"])
            eintraege.append({
                "fileid": fid,
                "datei": p.get("datei") or f"{fid}.jpg",
                "jahr": p.get("jahr"),
                "monat": p.get("monat"),
                "tag": p.get("tag"),
                "ordner": p.get("ordner"),
                "aufnahme_zeit": p.get("aufnahme_zeit") or p.get("aufnahme"),
                "breite": p.get("breite"),
                "hoehe": p.get("hoehe"),
                "beschreibung": p.get("beschreibung"),
                "beschreibung_reich": p.get("beschreibung_reich"),
                "modell_basis": p.get("modell_basis") or (p.get("modell") if not p.get("beschreibung_reich") else None),
                "modell_reich": p.get("modell_reich") or (p.get("modell") if p.get("beschreibung_reich") else None),
                "kosten_usd": p.get("kosten_usd"),
                "bogen_id": p.get("bogen_id"),
                "import_zeit": p.get("import_zeit") or now_iso,
            })

        with self.conn:
            self.conn.executemany(sql, eintraege)
        return len(eintraege)

    def upsert_person(self, person_data: Dict[str, Any]) -> None:
        """Erstellt oder aktualisiert eine Person."""
        now_iso = datetime.now(timezone.utc).isoformat()
        spitz = person_data.get("spitznamen")
        if isinstance(spitz, list):
            spitz = json.dumps(spitz, ensure_ascii=False)

        sql = """
        INSERT INTO persons (kennung, name, beziehung, vorname, nachname, spitznamen, erstellt_am)
        VALUES (:kennung, :name, :beziehung, :vorname, :nachname, :spitznamen, :erstellt_am)
        ON CONFLICT(kennung) DO UPDATE SET
            name = excluded.name,
            beziehung = coalesce(excluded.beziehung, persons.beziehung),
            vorname = coalesce(excluded.vorname, persons.vorname),
            nachname = coalesce(excluded.nachname, persons.nachname),
            spitznamen = coalesce(excluded.spitznamen, persons.spitznamen);
        """
        with self.conn:
            self.conn.execute(sql, {
                "kennung": person_data["kennung"],
                "name": person_data["name"],
                "beziehung": person_data.get("beziehung"),
                "vorname": person_data.get("vorname"),
                "nachname": person_data.get("nachname"),
                "spitznamen": spitz,
                "erstellt_am": person_data.get("erstellt_am") or now_iso,
            })

    def upsert_photo_faces_batch(self, faces_list: List[Dict[str, Any]]) -> int:
        """Speichert Gesichtspositionen je Foto ab."""
        if not faces_list:
            return 0
        sql = """
        INSERT INTO photo_faces (photo_fileid, person_kennung, face_index, bbox_x, bbox_y, bbox_w, bbox_h, anteil, score, gid)
        VALUES (:photo_fileid, :person_kennung, :face_index, :bbox_x, :bbox_y, :bbox_w, :bbox_h, :anteil, :score, :gid)
        ON CONFLICT(photo_fileid, face_index) DO UPDATE SET
            person_kennung = excluded.person_kennung,
            bbox_x = excluded.bbox_x,
            bbox_y = excluded.bbox_y,
            bbox_w = excluded.bbox_w,
            bbox_h = excluded.bbox_h,
            anteil = excluded.anteil,
            score = excluded.score,
            gid = excluded.gid;
        """
        params = []
        for f in faces_list:
            bbox = f.get("bbox") or [None, None, None, None]
            params.append({
                "photo_fileid": int(f["photo_fileid"]),
                "person_kennung": f.get("person_kennung") or f.get("kennung"),
                "face_index": int(f.get("face_index") or f.get("index") or 0),
                "bbox_x": bbox[0] if len(bbox) > 0 else None,
                "bbox_y": bbox[1] if len(bbox) > 1 else None,
                "bbox_w": bbox[2] if len(bbox) > 2 else None,
                "bbox_h": bbox[3] if len(bbox) > 3 else None,
                "anteil": f.get("anteil"),
                "score": f.get("score"),
                "gid": f.get("gid"),
            })
        with self.conn:
            self.conn.executemany(sql, params)
        return len(params)

    def upsert_story(self, story_data: Dict[str, Any]) -> None:
        """Fuegt eine Geschichte oder Erzählung ein."""
        now_iso = datetime.now(timezone.utc).isoformat()
        sql = """
        INSERT INTO stories (id, ereignis_kennung, datei_kennung, text, quelle, erstellt_am, ersetzt_id)
        VALUES (:id, :ereignis_kennung, :datei_kennung, :text, :quelle, :erstellt_am, :ersetzt_id)
        ON CONFLICT(id) DO UPDATE SET
            text = excluded.text,
            ersetzt_id = excluded.ersetzt_id;
        """
        with self.conn:
            self.conn.execute(sql, {
                "id": story_data["id"],
                "ereignis_kennung": story_data.get("ereignis_kennung"),
                "datei_kennung": story_data.get("datei_kennung"),
                "text": story_data["text"],
                "quelle": story_data.get("quelle", "mensch"),
                "erstellt_am": story_data.get("erstellt_am") or now_iso,
                "ersetzt_id": story_data.get("ersetzt_id"),
            })

    def get_photo(self, fileid: int) -> Optional[Dict[str, Any]]:
        """Holt ein Foto anhand seiner fileid."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM photos WHERE fileid = ?", (fileid,))
        row = cur.fetchone()
        if not row:
            return None
        return dict(row)

    def get_stats(self) -> Dict[str, int]:
        """Gibt Zaehler fuer alle Tabellen der Datenbank zurueck."""
        cur = self.conn.cursor()
        tabellen = ["photos", "persons", "photo_faces", "stories", "story_links"]
        stats = {}
        for t in tabellen:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            stats[t] = cur.fetchone()[0]
        return stats


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
    batch_size: int = 1000,
) -> Dict[str, int]:
    """Importiert Standard- und reiche Beschreibungen in life_archive.db."""
    erfolg_basis = 0
    erfolg_reich = 0

    if basis_pfad and basis_pfad.is_file():
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
            if len(stapel) >= batch_size:
                db.upsert_photos_batch(stapel)
                erfolg_basis += len(stapel)
                stapel = []
            if limit and erfolg_basis + len(stapel) >= limit:
                break

        if stapel:
            db.upsert_photos_batch(stapel)
            erfolg_basis += len(stapel)

    if reich_pfad and reich_pfad.is_file():
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
            if len(stapel) >= batch_size:
                db.upsert_photos_batch(stapel)
                erfolg_reich += len(stapel)
                stapel = []
            if limit and erfolg_reich + len(stapel) >= limit:
                break

        if stapel:
            db.upsert_photos_batch(stapel)
            erfolg_reich += len(stapel)

    return {"basis_importiert": erfolg_basis, "reich_importiert": erfolg_reich}

