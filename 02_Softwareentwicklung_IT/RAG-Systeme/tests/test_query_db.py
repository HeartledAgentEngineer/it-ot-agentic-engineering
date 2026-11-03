"""Tests fuer query_db: Embedding-Aufruf, Hybrid-Suche und LLM-Fallback-Kette (offline, Netz und DB als Attrappen)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import query_db  # noqa: E402


class Antwort:
    def __init__(self, status, daten=None, text=""):
        self.status_code, self._daten, self.text = status, daten, text

    def json(self):
        return self._daten


class Cursor:
    def __init__(self, zeilen):
        self.zeilen, self.aufrufe, self.geschlossen = zeilen, [], False

    def execute(self, sql, parameter):
        self.aufrufe.append((sql, parameter))

    def fetchall(self):
        return self.zeilen

    def close(self):
        self.geschlossen = True


class Verbindung:
    def __init__(self, cursor):
        self._cursor, self.geschlossen = cursor, False

    def cursor(self):
        return self._cursor

    def close(self):
        self.geschlossen = True


@pytest.fixture
def ohne_schluessel(monkeypatch):
    for name in ("MISTRAL_API_KEY", "GEMINI_API_KEY", "SUPABASE_CONNECTION_STRING"):
        monkeypatch.setattr(query_db, name, None)
    monkeypatch.setattr(query_db, "USE_LOCAL_LLM", False)


def test_embedding_ohne_schluessel_bricht_vor_dem_netz_ab(ohne_schluessel, monkeypatch):
    monkeypatch.setattr(query_db.requests, "post", lambda *a, **k: pytest.fail("kein Netzaufruf erwartet"))
    with pytest.raises(ValueError, match="MISTRAL_API_KEY"):
        query_db.generate_query_embedding("Frage")


def test_embedding_hat_eine_zeitgrenze(ohne_schluessel, monkeypatch):
    # Ohne timeout haengt die ganze Abfrage, wenn die Mistral-API nicht antwortet.
    aufrufe = []
    monkeypatch.setattr(query_db, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(query_db.requests, "post",
                        lambda url, **k: aufrufe.append(k) or Antwort(200, {"data": [{"embedding": [0.1, 0.2]}]}))
    assert query_db.generate_query_embedding("Frage") == [0.1, 0.2]
    assert aufrufe[0]["json"] == {"model": "mistral-embed", "input": ["Frage"]}
    assert aufrufe[0].get("timeout")


def test_embedding_fehlerstatus_wird_gemeldet(ohne_schluessel, monkeypatch):
    monkeypatch.setattr(query_db, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(query_db.requests, "post", lambda url, **k: Antwort(401, text="unauthorized"))
    with pytest.raises(Exception, match="unauthorized"):
        query_db.generate_query_embedding("Frage")


def test_suche_ohne_verbindung_bricht_ab(ohne_schluessel):
    with pytest.raises(ValueError, match="SUPABASE_CONNECTION_STRING"):
        query_db.search_db("Frage")


def test_suche_ruft_hybrid_search_und_formt_die_treffer(ohne_schluessel, monkeypatch):
    cursor = Cursor([("Text A", {"file_name": "a.pdf"}, 0.9, 0.03)])
    verbindung = Verbindung(cursor)
    monkeypatch.setattr(query_db, "SUPABASE_CONNECTION_STRING", "postgresql://attrappe")
    monkeypatch.setattr(query_db, "generate_query_embedding", lambda text: [0.5, 0.5])
    monkeypatch.setattr(query_db.psycopg2, "connect", lambda dsn: verbindung)

    treffer = query_db.search_db("Frage", match_count=3)

    assert treffer == [{"content": "Text A", "metadata": {"file_name": "a.pdf"}, "similarity": 0.9, "rrf_score": 0.03}]
    sql, parameter = cursor.aufrufe[0]
    assert "hybrid_search" in sql and parameter == ("Frage", [0.5, 0.5], 3)
    assert cursor.geschlossen and verbindung.geschlossen


def _abfangen(monkeypatch):
    """Faengt den Prompt des Mistral-Rueckfalls ab und liefert eine feste Antwort."""
    gesehen = {}

    def post(url, **k):
        gesehen["url"], gesehen["prompt"] = url, k["json"]["messages"][0]["content"]
        return Antwort(200, {"choices": [{"message": {"content": "Antwort [1]"}}]})

    monkeypatch.setattr(query_db, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(query_db.requests, "post", post)
    return gesehen


def test_quellen_im_kontext_kurs_vor_dateiname(ohne_schluessel, monkeypatch):
    gesehen = _abfangen(monkeypatch)
    chunks = [{"content": "Inhalt 1", "metadata": {"course": "AI-901", "module": "Modul 2"}},
              {"content": "Inhalt 2", "metadata": {"file_name": "handbuch.pdf"}},
              {"content": "Inhalt 3", "metadata": {}}]
    assert query_db.generate_answer("Frage?", chunks) == "Antwort [1]"
    prompt = gesehen["prompt"]
    assert "--- DOKUMENT 1 (Quelle: AI-901 -> Modul 2) ---\nInhalt 1" in prompt
    assert "--- DOKUMENT 2 (Quelle: handbuch.pdf) ---" in prompt
    assert "--- DOKUMENT 3 (Quelle: Unbekannt) ---" in prompt
    assert prompt.rstrip().endswith("Frage:\nFrage?\n\nANTWORT:")


def test_lokales_modell_faellt_auf_mistral_zurueck(ohne_schluessel, monkeypatch):
    urls = []
    monkeypatch.setattr(query_db, "USE_LOCAL_LLM", True)
    monkeypatch.setattr(query_db, "MISTRAL_API_KEY", "test-key")

    def post(url, **k):
        urls.append(url)
        if url == query_db.LOCAL_LLM_URL:
            return Antwort(500, text="ollama aus")
        return Antwort(200, {"choices": [{"message": {"content": "von Mistral"}}]})

    monkeypatch.setattr(query_db.requests, "post", post)
    assert query_db.generate_answer("Frage", [{"content": "x", "metadata": {}}]) == "von Mistral"
    assert urls == [query_db.LOCAL_LLM_URL, "https://api.mistral.ai/v1/chat/completions"]


def test_ohne_jedes_modell_klare_fehlermeldung(ohne_schluessel, monkeypatch):
    monkeypatch.setattr(query_db.requests, "post", lambda *a, **k: pytest.fail("kein Netzaufruf erwartet"))
    with pytest.raises(ValueError, match="alle Fallbacks fehlgeschlagen"):
        query_db.generate_answer("Frage", [])
