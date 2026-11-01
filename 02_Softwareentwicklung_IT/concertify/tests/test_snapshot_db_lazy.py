"""
tests/test_snapshot_db_lazy.py
==============================
Die Snapshot-DB entsteht erst beim ersten Zugriff — im dann gueltigen BASE_DIR.
Frueher legte schon `import app` die Datei concertify.db an (Seiteneffekt beim
Import: jeder Testlauf und jede CI-Kopie bekam eine DB-Datei).
"""

import app as app_module


def test_snapshot_db_entsteht_erst_beim_ersten_zugriff(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "BASE_DIR", tmp_path)
    monkeypatch.setattr(app_module, "_snapshot_service_cache", None)
    assert not (tmp_path / "concertify.db").exists()

    resp = app_module.app.test_client().get("/snapshots/list?artist=Band")

    assert resp.get_json() == {"ok": True, "snapshots": []}
    assert (tmp_path / "concertify.db").exists()
