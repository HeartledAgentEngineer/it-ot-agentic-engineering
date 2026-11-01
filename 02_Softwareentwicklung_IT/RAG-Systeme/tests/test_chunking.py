"""Tests fuer chunk_text: Absatz-Chunking mit Satzgrenzen und Seitenmarkern (offline, ohne API/DB)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chunking import chunk_text  # noqa: E402


def test_leerer_text_ergibt_keine_chunks():
    assert chunk_text("") == []
    assert chunk_text("\n\n  \n\n") == []


def test_kurze_absaetze_landen_in_einem_chunk():
    chunks = chunk_text("Erster Absatz.\n\nZweiter Absatz.", chunk_size=100)
    assert [c["content"] for c in chunks] == ["Erster Absatz.\n\nZweiter Absatz."]
    assert chunks[0]["page_number"] is None


def test_neuer_chunk_an_der_absatzgrenze():
    a, b = "a" * 60, "b" * 60
    chunks = chunk_text(f"{a}\n\n{b}", chunk_size=100)
    assert [c["content"] for c in chunks] == [a, b]


def test_riesenabsatz_wird_am_satzende_geteilt_nicht_am_komma():
    satz = "Wort, " * 15 + "Ende."          # ~95 Zeichen, Komma ist keine Grenze
    chunks = chunk_text(" ".join([satz] * 3), chunk_size=100)
    assert len(chunks) == 2
    assert all(c["content"].endswith("Ende.") for c in chunks)
    assert chunks[0]["content"].count("Ende.") == 2   # Grenze erst NACH Erreichen der Groesse


def test_seitenmarker_wird_zugeordnet_und_entfernt():
    chunks = chunk_text("[PAGE_NUM: 3]\n\nText auf Seite drei.\n\n[PAGE_NUM: 4] Seite vier.", chunk_size=20)
    assert [(c["content"], c["page_number"]) for c in chunks] == [
        ("Text auf Seite drei.", 3),
        ("Seite vier.", 4),
    ]
