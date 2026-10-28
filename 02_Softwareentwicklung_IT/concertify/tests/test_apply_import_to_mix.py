"""
tests/test_apply_import_to_mix.py
=================================
Regression: /apply_import_to_mix griff auf die Variable `today` zu, die in der
Route nie definiert wurde (NameError -> HTTP 500), sobald ein importierter
Kuenstler kein oder ein vergangenes Datum hatte. Gefunden per `ruff --select F821`.
Erwartet: fehlendes/vergangenes Datum wird auf heute gesetzt.
"""

import json
from datetime import date as _date

import app as app_module


def _post(tmp_path, monkeypatch, artists):
    monkeypatch.setattr(app_module, "BASE_DIR", tmp_path)
    client = app_module.app.test_client()
    resp = client.post("/apply_import_to_mix", json={"artists": artists})
    data = json.loads((tmp_path / "concert_data.json").read_text(encoding="utf-8"))
    return resp, data


def test_fehlendes_datum_wird_heute(tmp_path, monkeypatch):
    resp, data = _post(tmp_path, monkeypatch, {"Band A": {"source": "hh"}})
    assert resp.status_code == 200
    assert data["hamburg_artists"]["Band A"]["dates"] == [_date.today().isoformat()]


def test_vergangenes_festivaldatum_wird_heute(tmp_path, monkeypatch):
    resp, data = _post(tmp_path, monkeypatch,
                       {"Band B": {"source": "rip", "date": "2000-01-01"}})
    assert resp.status_code == 200
    assert data["rip_artists"]["Band B"]["dates"] == [_date.today().isoformat()]
