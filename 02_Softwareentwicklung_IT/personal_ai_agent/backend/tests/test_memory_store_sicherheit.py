"""Speicherschutz mit echten Dateien in tmp_path, ohne Netz oder Originaldaten."""
import builtins
from copy import deepcopy
import json
from pathlib import Path

import pytest

from app.db import chroma_client as store_mod


def _speicher(tmp_path):
    store = store_mod.SimpleMemoryStore()
    store.persist_dir = str(tmp_path)
    store.store_path = str(tmp_path / "memory_store.json")
    return store


def _bestand(tmp_path):
    store = _speicher(tmp_path)
    memory_id = store.add_memory(
        "Erfundener Testfakt", embedding=[1.0, 0.0],
        history=[{"content": "Erfundene Vorfassung"}],
    )
    return store, memory_id


def _mutieren(store, action, memory_id="alt"):
    if action == "add":
        return store.add_memory("Neuer Testfakt")
    if action == "update":
        return store.aktualisiere_memory(memory_id, {
            "content": "Geänderter Testfakt", "history": [{"content": "Andere Vorfassung"}],
        })
    if action == "vector":
        return store.setze_vektor(memory_id, [0.0, 1.0])
    if action == "delete":
        return store.delete_memory(memory_id)
    if action == "clear":
        return store.clear_all()
    raise AssertionError("Unbekannter Testfall")


@pytest.mark.parametrize("action", ["add", "update", "vector", "delete", "clear"])
def test_defekte_datei_wird_nicht_als_leerer_speicher_ueberschrieben(tmp_path, action):
    store = _speicher(tmp_path)
    path = Path(store.store_path)
    original = b'[{"id": "alt", "content": "PRIVATER_TESTINHALT"'
    path.write_bytes(original)
    with pytest.raises(RuntimeError):
        store.connect()
    with pytest.raises(RuntimeError):
        _mutieren(store, action)
    assert not store._loaded
    assert path.read_bytes() == original
    # Derselbe Prozess kann nach manueller Wiederherstellung wieder laden.
    path.write_text('[]', encoding="utf-8")
    assert store.count() == 0


@pytest.mark.parametrize("data", [
    {}, [1], [{}], [{"id": "", "content": "x"}],
    [{"id": 42, "content": "x"}], [{"id": "a", "content": None}],
    [{"id": "a"}], [{"id": "a", "content": "x"}, {"id": "a", "content": "y"}],
])
def test_falsche_struktur_wird_abgelehnt(tmp_path, data):
    store = _speicher(tmp_path)
    path = Path(store.store_path)
    path.write_text(json.dumps(data), encoding="utf-8")
    original = path.read_bytes()
    with pytest.raises(RuntimeError):
        store.connect()
    assert not store._loaded
    assert path.read_bytes() == original


def test_fehlende_datei_und_gueltige_altdatei_bleiben_kompatibel(tmp_path):
    store, memory_id = _bestand(tmp_path)
    assert memory_id
    path = Path(store.store_path)
    old = [{
        "id": "alt", "content": "Erfundener äöü-Testfakt", "embedding": [1.0, 0.0],
        "history": [{"content": "Vorher"}], "category": "termin", "importance": 5,
        "ereignis_datum": "2026-10-18", "wiederkehrend": True,
        "conversation_id": "test-chat", "zusatz": {"erhalten": True},
    }]
    path.write_text(json.dumps(old), encoding="utf-8")
    fresh = _speicher(tmp_path)
    fresh.connect()
    fresh.add_memory("Ein anderer erfundener Fakt")
    restarted = _speicher(tmp_path)
    assert restarted.count() == 2
    assert json.loads(path.read_text(encoding="utf-8"))[0] == old[0]
    assert restarted.vektor_score([1.0, 0.0])["alt"] == pytest.approx(1.0)


def test_serialisierungsfehler_erhaelt_datei_und_arbeitsspeicher(tmp_path):
    store, memory_id = _bestand(tmp_path)
    path = Path(store.store_path)
    original = path.read_bytes()
    before = deepcopy(store._memories)
    other = tmp_path / "nicht-entfernen.tmp"
    other.write_text("unbeteiligte Testdatei", encoding="utf-8")
    with pytest.raises(Exception):
        store.aktualisiere_memory(memory_id, {"zusatz": object()})
    assert path.read_bytes() == original
    assert store._memories == before
    assert set(tmp_path.iterdir()) == {path, other}


@pytest.mark.parametrize("action", ["add", "update", "vector", "delete", "clear"])
def test_ersetzungsfehler_rollt_jede_mutation_zurueck(tmp_path, monkeypatch, action):
    store, memory_id = _bestand(tmp_path)
    path = Path(store.store_path)
    original = path.read_bytes()
    before = deepcopy(store._memories)

    def blocked_replace(src, dst):
        raise OSError("Erfundene Schreibsperre")

    with monkeypatch.context() as patch:
        patch.setattr(store_mod.os, "replace", blocked_replace)
        with pytest.raises(RuntimeError):
            _mutieren(store, action, memory_id)
    assert path.read_bytes() == original
    assert store._memories == before
    assert set(tmp_path.iterdir()) == {path}
    _mutieren(store, action, memory_id)
    fresh = _speicher(tmp_path)
    if action in ("delete", "clear"):
        assert fresh.count() == 0
    elif action == "add":
        assert fresh.count() == 2
    elif action == "update":
        assert fresh.get_all_memories()[0]["content"] == "Geänderter Testfakt"
        assert fresh.get_all_memories()[0]["id"] == memory_id
    else:
        assert fresh.vektor_score([0.0, 1.0])[memory_id] == pytest.approx(1.0)


def test_neustart_sieht_vollstaendigen_neuen_stand(tmp_path):
    store, memory_id = _bestand(tmp_path)
    assert store.aktualisiere_memory(memory_id, {"content": "Geprüfte Neufassung"})
    fresh = _speicher(tmp_path)
    assert fresh.get_all_memories()[0]["id"] == memory_id
    assert fresh.get_all_memories()[0]["content"] == "Geprüfte Neufassung"
    assert fresh.get_all_memories()[0]["history"] == [{"content": "Erfundene Vorfassung"}]


@pytest.mark.parametrize("action", ["update", "vector", "delete"])
def test_unbekannte_id_schreibt_nicht(tmp_path, monkeypatch, action):
    store, _ = _bestand(tmp_path)
    path = Path(store.store_path)
    original = path.read_bytes()

    def blocked_replace(src, dst):
        raise AssertionError("Kein Speichern für eine unbekannte ID")

    monkeypatch.setattr(store_mod.os, "replace", blocked_replace)
    assert _mutieren(store, action, "unbekannt") is False
    assert path.read_bytes() == original


@pytest.mark.parametrize("kind", ["os", "unicode", "json"])
def test_ladefehler_enthaelt_weder_inhalt_noch_pfad(tmp_path, monkeypatch, kind):
    store = _speicher(tmp_path)
    path = Path(store.store_path)
    marker = "PRIVATE_TEST_MARKIERUNG"
    original = (marker if kind == "json" else '[]').encode("utf-8")
    path.write_bytes(original)
    original_open = builtins.open

    def blocked_open(file, *args, **kwargs):
        if str(file) == str(path):
            if kind == "os":
                raise OSError(13, marker, str(path))
            if kind == "unicode":
                raise UnicodeDecodeError("utf-8", marker.encode(), 0, 1, marker)
        return original_open(file, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", blocked_open)
        with pytest.raises(RuntimeError) as error:
            store.connect()
    assert str(path) not in str(error.value)
    assert marker not in str(error.value)
    assert not store._loaded
    assert path.read_bytes() == original


def test_tempdatei_ist_vor_ersetzung_vollstaendig_und_synchronisiert(tmp_path, monkeypatch):
    store, memory_id = _bestand(tmp_path)
    path = Path(store.store_path)
    original = path.read_bytes()
    synced = []
    original_fsync = store_mod.os.fsync
    original_replace = store_mod.os.replace

    def fsync(fd):
        original_fsync(fd)
        synced.append(True)

    def replace(src, dst):
        assert synced == [True]
        assert Path(src).parent == path.parent
        assert Path(src) != path
        assert Path(dst) == path
        assert path.read_bytes() == original
        assert json.loads(Path(src).read_text(encoding="utf-8"))[0]["content"] == "Neue Fassung"
        original_replace(src, dst)

    monkeypatch.setattr(store_mod.os, "fsync", fsync)
    monkeypatch.setattr(store_mod.os, "replace", replace)
    assert store.aktualisiere_memory(memory_id, {"content": "Neue Fassung"})
    assert synced == [True]
    assert set(tmp_path.iterdir()) == {path}


@pytest.mark.parametrize("damaged", [False, True])
def test_health_bleibt_erreichbar_und_meldet_gedaechtniszustand(tmp_path, monkeypatch, damaged):
    from fastapi.testclient import TestClient
    from app import main

    store = _speicher(tmp_path)
    path = Path(store.store_path)
    original = b'[{"id":' if damaged else b'[{"id":"test","content":"Erfundener Fakt"}]'
    path.write_bytes(original)
    monkeypatch.setattr(main, "chroma_client", store)
    monkeypatch.setattr(main, "_lan_ip", lambda: None)
    monkeypatch.setattr(main.settings, "api_key", "")
    # Kein lifespan/startup: nur der gezielt geprüfte Request mit tmp_path-Store.
    client = TestClient(main.app, raise_server_exceptions=False)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["memory_available"] is (not damaged)
    if damaged:
        assert "memory_count" not in data
    else:
        assert data["memory_count"] == 1
    assert path.read_bytes() == original
    assert str(path) not in response.text
