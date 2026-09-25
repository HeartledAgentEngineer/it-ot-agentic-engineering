"""Einzelne Referenz loeschen — auch bei Altdaten OHNE `ref_id` (Fix 2026-09-20).

Hintergrund (Befund Sebastian): „Bei den abgespeicherten Ausschnittbildern waren
wieder welche ohne Bild. Und: ich wollte EINS löschen, musste aber ALLE löschen."

Sichert ab:
  (i)   Alt-Referenz OHNE `ref_id` ist einzeln loeschbar; Person + andere
        Referenzen bleiben erhalten.
  (ii)  Die API liefert fuer Altdaten eine NICHT-LEERE, stabile `ref_id`.
  (iii) Die Migration ergaenzt NUR `ref_id` — Embedding/bbox/jahr/bild_pfad
        bleiben vorher==nachher.
  (iv)  Unbekannte ID -> klarer Fehler, Katalog unveraendert.
  (v)   Loeschen entfernt auch den zugehoerigen Vektor.

Alle Tests arbeiten auf tmp_path: Sebastians ECHTER Katalog
(`gesichter_katalog.json`, private Personendaten) wird nie angefasst.
"""

import json
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

import pytest  # noqa: E402
from pathlib import Path  # noqa: E402

from app.services import gesichter_service  # noqa: E402


@pytest.fixture(autouse=True)
def _eigener_katalog(tmp_path, monkeypatch):
    """Eigener Katalog je Test — nie Sebastians echtes Personen-Archiv."""
    monkeypatch.setattr(
        gesichter_service, "KATALOG_DATEI",
        Path(tmp_path) / "gesichter_katalog.json",
    )
    yield


def _altbestand_schreiben(personen=None):
    """Schreibt einen Katalog im STAND VOR dem 15.09.2026 (ohne `ref_id`).

    Genau so sahen Sebastians vorher gespeicherte Referenzen aus: `embedding`
    (Legacy-Spiegel) + `referenzen` OHNE `ref_id`.
    """
    if personen is None:
        personen = [{
            "name": "Altperson",
            "rolle": "Test",
            "referenz_bild_pfad": "",
            "referenz_bild_miniatur": "",
            # Legacy-Spiegel: Vektoren zusaetzlich als Liste auf oberster Ebene.
            "embedding": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            "gelernt_am": "2026-01-01T00:00:00+00:00",
            "referenzen": [
                {"embedding": [1.0, 0.0, 0.0], "jahr": 2015},
                {"embedding": [0.0, 1.0, 0.0], "jahr": 2020},
            ],
        }]
    with open(gesichter_service.KATALOG_DATEI, "w", encoding="utf-8") as f:
        json.dump({"personen": personen}, f, ensure_ascii=False, indent=2)


def _roh():
    with open(gesichter_service.KATALOG_DATEI, "r", encoding="utf-8") as f:
        return json.load(f)


def _person(name):
    return next(
        (p for p in _roh()["personen"]
         if (p.get("name") or "").strip().lower() == name.lower()),
        None,
    )


# ---------------------------------------------------------------------------
# (i) Alt-Referenz ohne ref_id ist EINZELN loeschbar
# ---------------------------------------------------------------------------

def test_alt_referenz_einzeln_loeschbar_person_und_rest_bleiben():
    _altbestand_schreiben()
    liste = gesichter_service.referenzen_auflisten()["personen"]
    assert len(liste) == 1
    assert liste[0]["anzahl"] == 2
    erste = liste[0]["referenzen"][0]

    res = gesichter_service.referenz_entfernen("Altperson", erste["ref_id"])
    assert res["ok"] is True, res
    assert res["verbleibend"] == 1

    # Person lebt weiter (KEIN Loeschen der ganzen Person).
    assert gesichter_service.person_finden("Altperson") is not None
    rest = gesichter_service.referenzen_auflisten()["personen"][0]["referenzen"]
    assert len(rest) == 1
    assert rest[0]["jahr"] == 2020          # die ANDERE Referenz blieb stehen


def test_alt_referenz_ueber_embedding_hash_loeschbar():
    """Robustheit: die aus dem Embedding berechnete ID loescht ebenfalls.

    Deckt den Fall ab, dass eine Referenz inzwischen eine ANDERE gespeicherte
    `ref_id` traegt (z. B. nach einer Rahmen-Anpassung), der Client aber noch
    die alte, abgeleitete ID sendet.
    """
    _altbestand_schreiben()
    # Referenz mit einer gespeicherten (absichtlich abweichenden) ref_id.
    _altbestand_schreiben([{
        "name": "Altperson",
        "embedding": [[1.0, 0.0, 0.0]],
        "referenzen": [{"embedding": [1.0, 0.0, 0.0], "jahr": 2015,
                        "ref_id": "gespeicherte-id"}],
    }])
    hash_id = gesichter_service._ref_id([1.0, 0.0, 0.0])
    assert hash_id != "gespeicherte-id"

    res = gesichter_service.referenz_entfernen("Altperson", hash_id)
    assert res["ok"] is True, res
    assert gesichter_service.referenzen_auflisten()["personen"][0]["anzahl"] == 0
    assert gesichter_service.person_finden("Altperson") is not None


# ---------------------------------------------------------------------------
# (ii) API liefert fuer Altdaten eine stabile, nicht-leere ref_id
# ---------------------------------------------------------------------------

def test_api_liefert_fuer_altdaten_stabile_ref_id():
    _altbestand_schreiben()
    ids1 = [e["ref_id"] for e in
            gesichter_service.referenzen_auflisten()["personen"][0]["referenzen"]]
    assert len(ids1) == 2
    assert all(isinstance(i, str) and i for i in ids1), "ref_id darf NIE leer sein"

    # Zweiter Abruf (jetzt aus dem migrierten Katalog) liefert DIESELBEN IDs.
    ids2 = [e["ref_id"] for e in
            gesichter_service.referenzen_auflisten()["personen"][0]["referenzen"]]
    assert ids1 == ids2, "ref_id muss stabil bleiben"


def test_api_ref_id_entspricht_der_migration():
    _altbestand_schreiben()
    api_ids = [e["ref_id"] for e in
               gesichter_service.referenzen_auflisten()["personen"][0]["referenzen"]]
    gespeichert = _person("Altperson")["referenzen"]
    assert [r["ref_id"] for r in gespeichert] == api_ids


# ---------------------------------------------------------------------------
# (iii) Migration ergaenzt NUR ref_id (Embedding/bbox unveraendert)
# ---------------------------------------------------------------------------

def test_migration_ergaenzt_nur_ref_id():
    vorher_refs = [
        {"embedding": [1.0, 0.0, 0.0], "jahr": 2015,
         "bild_pfad": "/bild/a.jpg", "bbox": [10.0, 20.0, 30.0, 40.0],
         "bbox_norm": [0.1, 0.1, 0.3, 0.2]},
        {"embedding": [0.0, 1.0, 0.0], "jahr": 2020,
         "bbox": [5.0, 6.0, 7.0, 8.0]},
    ]
    _altbestand_schreiben([{
        "name": "Altperson",
        "rolle": "Test",
        "referenz_bild_pfad": "/bild/a.jpg",
        "referenz_bild_miniatur": "data:image/jpeg;base64,AAAA",
        "embedding": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        "gelernt_am": "2026-01-01T00:00:00+00:00",
        "referenzen": json.loads(json.dumps(vorher_refs)),   # tiefe Kopie
    }])
    vorher_person = _person("Altperson")

    assert gesichter_service.ref_ids_migrieren() is True

    nachher_person = _person("Altperson")
    nachher_refs = nachher_person["referenzen"]

    assert len(nachher_refs) == len(vorher_refs)
    assert all(r.get("ref_id") for r in nachher_refs), "ref_id fehlt nach Migration"
    for v, n in zip(vorher_refs, nachher_refs):
        # ALLES ausser ref_id ist byte-identisch (Embedding, bbox, bbox_norm,
        # jahr, bild_pfad).
        assert n["embedding"] == v["embedding"]
        assert n.get("bbox") == v.get("bbox")
        assert n.get("bbox_norm") == v.get("bbox_norm")
        assert n.get("jahr") == v.get("jahr")
        assert n.get("bild_pfad") == v.get("bild_pfad")
        assert set(n.keys()) == set(v.keys()) | {"ref_id"}, "nur ref_id darf dazukommen"
        # Unveraendert gebliebene Personen-Aussenfelder.
        assert nachher_person["embedding"] == vorher_person["embedding"]
        assert nachher_person["referenz_bild_miniatur"] == vorher_person["referenz_bild_miniatur"]


def test_migration_ist_idempotent():
    _altbestand_schreiben()
    assert gesichter_service.ref_ids_migrieren() is True    # 1. Lauf migriert
    assert gesichter_service.ref_ids_migrieren() is False   # 2. Lauf: nichts zu tun


def test_speichern_traegt_ref_id_ebenfalls_nach():
    """Auch der Update-Pfad von `person_speichern` schreibt die ref_id fest."""
    _altbestand_schreiben()
    assert all("ref_id" not in r for r in _person("Altperson")["referenzen"])

    gesichter_service.person_speichern("Altperson", rolle="Test")

    assert all(r.get("ref_id") for r in _person("Altperson")["referenzen"])


# ---------------------------------------------------------------------------
# (iv) Unbekannte ID -> Fehler, Katalog unveraendert
# ---------------------------------------------------------------------------

def test_unbekannte_id_fehler_und_katalog_unveraendert():
    _altbestand_schreiben()
    vorher = _roh()

    res = gesichter_service.referenz_entfernen("Altperson", "gibtsnicht")
    assert res["ok"] is False
    assert res["fehler"] == "referenz nicht gefunden"

    assert _roh() == vorher, "Fehlversuch darf den Katalog nicht schreiben"

    # Unbekannte Person, leere ID -> weiterhin klare Meldung (kein stilles Nichtstun).
    assert gesichter_service.referenz_entfernen("Zoe", "x")["fehler"] == "person nicht gefunden"
    assert gesichter_service.referenz_entfernen("Altperson", "")["ok"] is False


# ---------------------------------------------------------------------------
# (v) Loeschen entfernt auch den Vektor
# ---------------------------------------------------------------------------

def test_loeschen_entfernt_auch_den_vektor():
    _altbestand_schreiben()
    assert len(_person("Altperson")["embedding"]) == 2

    ziel = gesichter_service.referenzen_auflisten()["personen"][0]["referenzen"][0]
    res = gesichter_service.referenz_entfernen("Altperson", ziel["ref_id"])
    assert res["ok"] is True

    p = _person("Altperson")
    assert len(p["embedding"]) == 1
    assert p["embedding"][0] == [0.0, 1.0, 0.0]      # nur der Rest, kein Geister-Vektor
    assert len(p["referenzen"]) == 1


# ---------------------------------------------------------------------------
# Router-Ebene: derselbe Weg, den das Frontend geht
# ---------------------------------------------------------------------------

def test_router_loescht_alt_referenz():
    from app.router import gesichter as router
    _altbestand_schreiben()
    ziel = gesichter_service.referenzen_auflisten()["personen"][0]["referenzen"][0]

    r = router.referenz_loeschen("Altperson", ziel["ref_id"])
    assert r["ok"] is True and r["verbleibend"] == 1
    assert gesichter_service.person_finden("Altperson") is not None


def test_router_antwortet_404_bei_unbekannter_id():
    from fastapi import HTTPException
    from app.router import gesichter as router
    _altbestand_schreiben()
    with pytest.raises(HTTPException) as e:
        router.referenz_loeschen("Altperson", "gibtsnicht")
    assert e.value.status_code == 404


def test_router_referenzen_endpoint_liefert_ref_ids():
    from app.router import gesichter as router
    _altbestand_schreiben()
    payload = router.referenzen_liste()
    refs = payload["personen"][0]["referenzen"]
    assert len(refs) == 2
    assert all(r.get("ref_id") for r in refs)
