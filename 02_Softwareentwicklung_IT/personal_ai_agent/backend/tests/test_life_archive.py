import json
import tempfile
from pathlib import Path

import pytest

from app.db.life_archive import LifeArchiveDB, init_db, migriere_beschreibungen



@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_life_archive.db"
        db = LifeArchiveDB(db_path)
        yield db
        db.close()


def test_schema_initialization(temp_db):
    stats = temp_db.get_stats()
    assert "photos" in stats
    assert "persons" in stats
    assert "photo_faces" in stats
    assert "stories" in stats
    assert "story_links" in stats
    assert stats["photos"] == 0


def test_upsert_and_retrieve_photo(temp_db):
    photo = {
        "fileid": 123456,
        "datei": "urlaub.jpg",
        "jahr": 2024,
        "monat": 7,
        "tag": 15,
        "ordner": "/Fotos/2024",
        "beschreibung": "Strandbild bei Sonnenuntergang.",
        "modell_basis": "google/gemini-2.5-flash",
    }
    temp_db.upsert_photo(photo)

    stored = temp_db.get_photo(123456)
    assert stored is not None
    assert stored["datei"] == "urlaub.jpg"
    assert stored["jahr"] == 2024
    assert stored["beschreibung"] == "Strandbild bei Sonnenuntergang."
    assert stored["beschreibung_reich"] is None

    # Aktualisierung mit reicher Beschreibung
    update = {
        "fileid": 123456,
        "beschreibung_reich": "Detaillierte Szene: Drei Personen sitzen am Sandstrand bei Sonnenuntergang.",
        "modell_reich": "google/gemini-3.8-flash",
    }
    temp_db.upsert_photo(update)

    updated = temp_db.get_photo(123456)
    assert updated["beschreibung"] == "Strandbild bei Sonnenuntergang."
    assert updated["beschreibung_reich"] == "Detaillierte Szene: Drei Personen sitzen am Sandstrand bei Sonnenuntergang."
    assert updated["modell_reich"] == "google/gemini-3.8-flash"


def test_migrator_with_jsonl_fixtures(temp_db):
    with tempfile.TemporaryDirectory() as tmpdir:
        basis_file = Path(tmpdir) / "basis.jsonl"
        reich_file = Path(tmpdir) / "reich.jsonl"

        # Basis JSONL
        basis_data = [
            {"fileid": 101, "datei": "foto1.jpg", "jahr": 2023, "monat": 5, "tag": 10, "beschreibung": "Haus im Gruenen", "modell": "gemini-2.5-flash"},
            {"fileid": 102, "datei": "foto2.jpg", "jahr": 2023, "monat": 6, "tag": 12, "beschreibung": "Konzertbuehne", "modell": "gemini-2.5-flash"},
        ]
        with basis_file.open("w", encoding="utf-8") as f:
            for b in basis_data:
                f.write(json.dumps(b) + "\n")

        # Reich JSONL
        reich_data = [
            {"fileid": 101, "datei": "foto1.jpg", "jahr": 2023, "monat": 5, "tag": 10, "beschreibung": "Ein weisses Einfamilienhaus mit rotem Dach und grossem Garten.", "modell": "gemini-3.8-flash"},
            {"fileid": 103, "datei": "foto3.jpg", "jahr": 2024, "monat": 1, "tag": 1, "beschreibung": "Neujahrsfeuerwerk ueber der Stadt.", "modell": "gemini-3.8-flash"},
        ]
        with reich_file.open("w", encoding="utf-8") as f:
            for r in reich_data:
                f.write(json.dumps(r) + "\n")

        res = migriere_beschreibungen(temp_db, basis_pfad=basis_file, reich_pfad=reich_file)
        assert res["basis_importiert"] == 2
        assert res["reich_importiert"] == 2

        stats = temp_db.get_stats()
        # Gesamt 3 Fotos (101 mit beiden, 102 nur Basis, 103 nur Reich)
        assert stats["photos"] == 3

        p101 = temp_db.get_photo(101)
        assert p101["beschreibung"] == "Haus im Gruenen"
        assert "Einfamilienhaus" in p101["beschreibung_reich"]

        p102 = temp_db.get_photo(102)
        assert p102["beschreibung"] == "Konzertbuehne"
        assert p102["beschreibung_reich"] is None

        p103 = temp_db.get_photo(103)
        assert p103["beschreibung"] is None
        assert p103["beschreibung_reich"] == "Neujahrsfeuerwerk ueber der Stadt."


def test_persons_faces_and_stories(temp_db):
    # Foto anlegen
    temp_db.upsert_photo({"fileid": 555, "datei": "familie.jpg", "jahr": 2020})

    # Person anlegen
    temp_db.upsert_person({
        "kennung": "Person_001",
        "name": "Sebastian",
        "beziehung": "Ich",
        "vorname": "Sebastian",
        "spitznamen": ["Sebi", "Basti"],
    })

    # Gesicht auf Foto verknuepfen
    temp_db.upsert_photo_faces_batch([{
        "photo_fileid": 555,
        "person_kennung": "Person_001",
        "face_index": 0,
        "bbox": [100.0, 150.0, 80.0, 95.0],
        "anteil": 0.05,
        "score": 0.94,
    }])

    # Geschichte anlegen
    temp_db.upsert_story({
        "id": "story-001",
        "ereignis_kennung": "sommer-2020",
        "datei_kennung": 555,
        "text": "Das war der Tag, an dem wir das Zelt aufgebaut haben.",
        "quelle": "mensch",
    })

    stats = temp_db.get_stats()
    assert stats["photos"] == 1
    assert stats["persons"] == 1
    assert stats["photo_faces"] == 1
    assert stats["stories"] == 1
