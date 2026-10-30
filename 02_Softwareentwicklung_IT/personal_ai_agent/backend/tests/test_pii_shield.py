import sqlite3
import pytest

from app.services.pii_shield import PIIShield


def test_pii_encoding_and_reversibility():
    shield = PIIShield()
    token_seb = shield.register_person("Sebastian Wenck", aliases=["Sebastian", "Basti"])
    token_fab = shield.register_person("Fabia")
    token_hh = shield.register_location("Hamburg")
    token_mama = shield.register_role("Mama")

    assert token_seb == "[PERSON_01]"
    assert token_fab.startswith("[PERSON_")
    assert token_hh == "[LOC_01]"
    assert token_mama == "[ROLE_01]"


    original = "Hallo Sebastian Wenck, deine Mama kommt morgen nach Hamburg und trifft Fabia."
    encoded = shield.encode(original)

    # Sicherstellen, dass keine Klarnamen mehr im encoded Text stehen
    assert "Sebastian Wenck" not in encoded
    assert "Hamburg" not in encoded
    assert "Fabia" not in encoded
    assert "Mama" not in encoded

    assert "[PERSON_01]" in encoded
    assert "[ROLE_01]" in encoded
    assert "[LOC_01]" in encoded
    assert token_fab in encoded


    # Reversibilitaet pruefen
    decoded = shield.decode(encoded)
    assert decoded == original


def test_alias_and_longest_match_first():
    shield = PIIShield()
    shield.register_person("Sebastian Wenck", aliases=["Sebastian"])
    shield.register_person("Sebastian Junior")

    text = "Sebastian Wenck und Sebastian Junior trafen Sebastian im Park."
    encoded = shield.encode(text)

    # Beide spezifischen Namen muessen vollstaendig erfasst sein
    assert "Sebastian Wenck" not in encoded
    assert "Sebastian Junior" not in encoded

    decoded = shield.decode(encoded)
    assert decoded == text


def test_email_and_phone_masking():
    shield = PIIShield()
    text = "Melde dich unter info@beispiel.de oder telefonisch via +49 170 1234567."
    encoded = shield.encode(text)

    assert "info@beispiel.de" not in encoded
    assert "+49 170 1234567" not in encoded
    assert "[EMAIL_01]" in encoded
    assert "[PHONE_01]" in encoded

    decoded = shield.decode(encoded)
    assert decoded == text


def test_stream_decoding_fragments():
    shield = PIIShield()
    shield.register_person("Sebastian")
    shield.register_location("Hamburg")

    # Simulierte Streaming-Chunks mit zerschnittenen Tokens
    chunks = [
        "Guten Tag ",
        "[PERS",
        "ON_01",
        "], herzlich willkommen in ",
        "[LOC",
        "_01]! ",
        "Hier ist eine normale [Klammer] zum Test.",
    ]

    reconstructed = "".join(shield.decode_stream(chunks))
    erwartet = "Guten Tag Sebastian, herzlich willkommen in Hamburg! Hier ist eine normale [Klammer] zum Test."
    assert reconstructed == erwartet


def test_deterministic_fastpath():
    shield = PIIShield()

    # SQLite In-Memory Dummy-DB
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE persons (kennung TEXT, name TEXT);")
    cur.execute("CREATE TABLE photos (fileid INTEGER);")
    cur.execute("CREATE TABLE photo_faces (photo_fileid INTEGER, person_kennung TEXT);")

    cur.execute("INSERT INTO persons VALUES ('Person_001', 'Sebastian');")
    cur.execute("INSERT INTO photos VALUES (1);")
    cur.execute("INSERT INTO photos VALUES (2);")
    cur.execute("INSERT INTO photo_faces VALUES (1, 'Person_001');")
    cur.execute("INSERT INTO photo_faces VALUES (2, 'Person_001');")
    conn.commit()

    # Zaehlanfrage
    antwort = shield.fastpath_statistik("Wie viele Fotos von Sebastian gibt es?", cur)
    assert antwort == "Von Sebastian gibt es 2 Fotos im Archiv."

    # Gesamtanfrage
    antwort_gesamt = shield.fastpath_statistik("Wie viele Fotos haben wir insgesamt?", cur)
    assert antwort_gesamt == "Es sind insgesamt 2 Fotos im Archiv gespeichert."

    # Unbekannte Frage -> Fastpath greift nicht, gibt None zurueck (faellt ans LLM zurueck)
    antwort_unbekannt = shield.fastpath_statistik("Erzähl mir vom Urlaub.", cur)
    assert antwort_unbekannt is None
