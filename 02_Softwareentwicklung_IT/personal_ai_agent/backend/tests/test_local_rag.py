import tempfile
from pathlib import Path

import numpy as np
import pytest

from app.services.local_rag import LocalRAG, kosinus_aehnlichkeit, text_chunking


def test_kosinus_aehnlichkeit():
    v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    v2 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    v3 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    v0 = np.array([0.0, 0.0, 0.0], dtype=np.float32)

    assert pytest.approx(kosinus_aehnlichkeit(v1, v2)) == 1.0
    assert pytest.approx(kosinus_aehnlichkeit(v1, v3)) == 0.0
    assert kosinus_aehnlichkeit(v1, v0) == 0.0


def test_text_chunking():
    kurz = "Kurzer Text ohne Absaetze."
    assert text_chunking(kurz) == [kurz]

    lang = "Absatz 1: Erinnerungen an den Sommerurlaub.\n\nAbsatz 2: Wanderung auf den Berg im Harz.\n\nAbsatz 3: Konzertbesuch am Abend."
    chunks = text_chunking(lang, chunk_groesse=50, ueberlappung=10)
    assert len(chunks) >= 2
    assert "Absatz 1" in chunks[0]


def test_local_rag_embed_and_search():
    rag = LocalRAG()

    with tempfile.TemporaryDirectory() as tmpdir:
        dummy_file = Path(tmpdir) / "tagebuch.txt"
        dummy_file.write_text(
            "Heute haben wir einen schoenen Ausflug an die Ostsee gemacht. Der Strand war sonnig und das Meer ruhig.\n\n"
            "Gestern habe ich am Computer ein neues Python-Skript fuer lokale Vektoren programmiert.\n\n"
            "Im Supermarkt habe ich Aepfel, Brot und Kaese fuer das Abendessen eingekauft.",
            encoding="utf-8",
        )

        chunks = rag.embed_file(dummy_file, chunk_groesse=120, ueberlappung=20)
        assert len(chunks) >= 2
        for c in chunks:
            assert len(c["embedding"]) == 384

        # Suche nach Strand/Urlaub
        ergebnisse = rag.search("Wo waren wir am Strand und am Meer?", chunks, top_k=1)
        assert len(ergebnisse) == 1
        assert "Ostsee" in ergebnisse[0]["text"]
        assert ergebnisse[0]["score"] > 0.4
