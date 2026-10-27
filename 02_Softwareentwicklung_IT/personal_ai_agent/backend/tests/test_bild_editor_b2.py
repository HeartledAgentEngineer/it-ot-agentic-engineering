"""Tests: Bild-Editor B2 „Erkennung für fileid" — ``POST /api/gruppen/bild-erkennen``.

Offline, nur erfundene Kennungen und Namen („Person A", fileid 111 ...) in ``tmp_path``
(``GRUPPEN_QUIZ_BASIS``). pCloud und die Gesichtserkennung (Debian/proot) sind Attrappen
(``monkeypatch``) — es wird nie ein Netz oder ein Subprozess benutzt, nie
``~/foto_sortierung`` gelesen oder geschrieben. Keine echten Vektoren.

Pruefkriterien des Auftrags B2 (Nummer = Nummer im Auftrag):
  1. EXIF-Orientierung 6: die Erkennung bekommt das Bild in Anzeige-Ausrichtung
  2. Verkleinerung auf hoechstens 1600 px, Quelle ``original_1600``
  3. ohne Pillow: pCloud-Vorschau 800x800, Quelle ``vorschau_800``, kein ``datei_bytes``
  4. nichts auf Platte
  5. ``max_faces = 30`` und ``timeout_s = 45``; alle alten Aufrufer von ``_infer`` behalten 30 s
  6. IoU >= 0,5 = bekannt (+ gid), sonst neu
  7. Namensvorschlaege: nur Name + Abstand, keine Embeddings
  8. ehrliche Fehler + HTTP-Status
  9. gleicher Schutz wie die uebrigen ``/api/gruppen``-Routen

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_bild_editor_b2.py -q
"""
from __future__ import annotations

import builtins
import io
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from PIL import Image

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.config import settings  # noqa: E402
from app.router import auth  # noqa: E402
from app.router import gruppen as gruppen_router  # noqa: E402
from app.services import bild_erkennen as be  # noqa: E402
from app.services import face_service  # noqa: E402
from app.services import gruppen_quiz as gq  # noqa: E402
from app.services.pcloud_service import (  # noqa: E402
    MAX_DATEI_BYTES, PCloudFehler, PCloudNichtKonfiguriert, PCloudZuGross)

GEHEIM = 0.123456789          # Kennzeichen eines „Embeddings": darf nirgends auftauchen


# ── Hilfen: Daten, Bilder, Attrappen ───────────────────────────────────────

def _gruppe(kennung, groesse=10):
    return {"kennung": kennung, "groesse": groesse, "bilder": groesse, "videos": 0,
            "von": None, "bis": None, "zwilling_kandidaten": [], "beispiele": []}


def _zeile(bild, index, kennung, bbox, breite=1000, hoehe=800):
    return {"bild_id": str(bild), "index": index, "kennung": kennung, "bbox": bbox,
            "breite": breite, "hoehe": hoehe, "anteil": 0.05, "score": 0.95}


# Bild 111: Gesicht 0 = Person A (bbox_norm 0.1/0.1/0.2/0.2), Gesicht 1 unbenannt.
ZEILEN = [
    _zeile(111, 0, "Person_2001", [100, 80, 200, 160]),
    _zeile(111, 1, "Person_2003", [600, 80, 100, 100]),
]


@pytest.fixture
def basis(tmp_path, monkeypatch):
    daten = tmp_path / "daten"
    daten.mkdir()
    heim = tmp_path / "heim"
    heim.mkdir()
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(daten))
    monkeypatch.setenv("HOME", str(heim))
    monkeypatch.setenv("USERPROFILE", str(heim))
    gq._CACHE.clear()
    ordner = daten / gq.UNTERORDNER
    ordner.mkdir()
    (ordner / gq.BEISPIELE_DATEINAME).write_text(
        json.dumps({"stand": "2026-10-27T01:00:00", "verfahren": "mittelpunkt",
                    "gruppen": [_gruppe("Person_2001", 40), _gruppe("Person_2003", 20)]}),
        encoding="utf-8")
    (ordner / gq.ZUORDNUNG_DATEINAME).write_text(
        "\n".join(json.dumps(z) for z in ZEILEN) + "\n", encoding="utf-8")
    gq._CACHE.clear()
    assert gq.antworten("Person_2001", "name", "Person A")["ok"] is not False
    yield daten
    gq._CACHE.clear()
    assert list(heim.iterdir()) == []                  # nichts im Heimordner angelegt


def _jpeg(breite, hoehe, orientierung=None, farbe=(200, 120, 60)):
    bild = Image.new("RGB", (breite, hoehe), farbe)
    puffer = io.BytesIO()
    if orientierung:
        exif = Image.Exif()
        exif[274] = orientierung
        bild.save(puffer, format="JPEG", exif=exif)
    else:
        bild.save(puffer, format="JPEG")
    return puffer.getvalue()


class FakePCloud:
    """Attrappe fuer ``pcloud_service`` — zeichnet die Aufrufe auf."""

    def __init__(self, original=b"", vorschau=b"", fehler_original=None, fehler_vorschau=None):
        self.original, self.vorschau = original, vorschau
        self.fehler_original, self.fehler_vorschau = fehler_original, fehler_vorschau
        self.aufrufe = []

    def datei_bytes(self, fileid, max_bytes=MAX_DATEI_BYTES):
        self.aufrufe.append(("datei_bytes", fileid, max_bytes))
        if self.fehler_original:
            raise self.fehler_original
        return self.original

    def thumb(self, fileid, groesse="120x120"):
        self.aufrufe.append(("thumb", fileid, groesse))
        if self.fehler_vorschau:
            raise self.fehler_vorschau
        return self.vorschau


class Erkennung:
    """Attrappe fuer ``face_service._infer`` — merkt sich Nutzlast und Bilddaten."""

    def __init__(self, gesichter=None, antwort=None):
        self.gesichter = gesichter if gesichter is not None else []
        self.antwort = antwort
        self.aufrufe = []

    def __call__(self, payload, timeout_s=None):
        import base64
        self.aufrufe.append({"payload": payload, "timeout_s": timeout_s,
                             "bild": base64.b64decode(payload.get("bild_base64", ""))})
        if self.antwort is not None:
            return self.antwort
        return {"ok": True, "gesichter": [
            {"bbox": g, "score": 0.9, "embedding": [GEHEIM] * 4} for g in self.gesichter]}


@pytest.fixture
def umgebung(basis, monkeypatch):
    """pCloud-Attrappe + Erkennungs-Attrappe + leerer Handy-Katalog (kein Namensvorschlag)."""
    pc = FakePCloud(original=_jpeg(400, 300))
    erkennung = Erkennung()
    monkeypatch.setattr(be, "pcloud_service", pc)
    monkeypatch.setattr(face_service, "verfuegbar", lambda: True)
    monkeypatch.setattr(face_service, "_infer", erkennung)
    monkeypatch.setattr(face_service, "erkenne_personen", lambda emb: [])
    return type("Umgebung", (), {"pc": pc, "erkennung": erkennung, "basis": basis})


def _client():
    app = FastAPI()
    app.include_router(gruppen_router.router)
    return TestClient(app)


def _post(fileid="111"):
    return _client().post("/api/gruppen/bild-erkennen", json={"fileid": fileid})


# ── 1: EXIF-Orientierung ───────────────────────────────────────────────────

def test_k1_exif_6_erkennung_bekommt_bild_in_anzeige_ausrichtung(umgebung):
    umgebung.pc.original = _jpeg(120, 80, orientierung=6)          # Rohdaten quer, Anzeige hochkant
    roh = Image.open(io.BytesIO(umgebung.pc.original))
    assert roh.size == (120, 80) and roh.getexif().get(274) == 6
    umgebung.erkennung.gesichter = [[8.0, 12.0, 40.0, 60.0]]       # Pixel im 80x120-Bild

    r = be.bild_erkennen("111")

    assert r["ok"] is True and r["quelle"] == "original_1600"
    gesehen = Image.open(io.BytesIO(umgebung.erkennung.aufrufe[0]["bild"]))
    assert gesehen.size == (80, 120)                               # Breite/Hoehe vertauscht
    assert gesehen.getexif().get(274) in (None, 1)                 # Drehung nicht ein zweites Mal
    assert r["gesichter"][0]["bbox_norm"] == [0.1, 0.1, 0.5, 0.5]  # relativ zu 80x120
    assert r["breite"] == 80 and r["hoehe"] == 120


# ── 2: Verkleinerung ───────────────────────────────────────────────────────

def test_k2_grosses_original_wird_auf_1600_verkleinert(umgebung):
    umgebung.pc.original = _jpeg(4000, 3000)
    umgebung.erkennung.gesichter = [[160.0, 120.0, 320.0, 240.0]]

    r = be.bild_erkennen("111")

    gesehen = Image.open(io.BytesIO(umgebung.erkennung.aufrufe[0]["bild"]))
    assert max(gesehen.size) == 1600 and gesehen.size == (1600, 1200)
    assert r["quelle"] == "original_1600" and (r["breite"], r["hoehe"]) == (1600, 1200)
    assert r["gesichter"][0]["bbox_norm"] == [0.1, 0.1, 0.2, 0.2]
    assert umgebung.pc.aufrufe == [("datei_bytes", 111, MAX_DATEI_BYTES)]


def test_k2_kleines_original_wird_nicht_hochgerechnet(umgebung):
    umgebung.pc.original = _jpeg(800, 600)
    be.bild_erkennen("111")
    assert Image.open(io.BytesIO(umgebung.erkennung.aufrufe[0]["bild"])).size == (800, 600)


# ── 3: ohne Pillow ─────────────────────────────────────────────────────────

def test_k3_ohne_pillow_vorschau_800_und_kein_datei_bytes(umgebung, monkeypatch):
    monkeypatch.setattr(be, "_pillow_nutzbar", lambda: False)
    umgebung.pc.vorschau = _jpeg(800, 600)
    umgebung.erkennung.gesichter = [[80.0, 60.0, 160.0, 120.0]]

    r = be.bild_erkennen("111")

    assert r["ok"] is True and r["quelle"] == "vorschau_800"
    assert umgebung.pc.aufrufe == [("thumb", 111, "800x800")]       # datei_bytes NICHT aufgerufen
    assert (r["breite"], r["hoehe"]) == (800, 600)
    assert r["gesichter"][0]["bbox_norm"] == [0.1, 0.1, 0.2, 0.2]
    assert umgebung.erkennung.aufrufe[0]["bild"] == umgebung.pc.vorschau


def test_k3_pillow_probe_erkennt_fehlendes_pillow(monkeypatch):
    assert be._pillow_nutzbar() is True
    monkeypatch.setitem(sys.modules, "PIL", None)                   # import PIL -> ImportError
    monkeypatch.delitem(sys.modules, "PIL.Image", raising=False)
    monkeypatch.delitem(sys.modules, "PIL.ImageOps", raising=False)
    assert be._pillow_nutzbar() is False


def test_k3_vorschau_hochkant_mit_exif_6_masse_in_anzeige_ausrichtung(umgebung, monkeypatch):
    """Ohne Pillow zaehlt die Anzeige-Ausrichtung auch fuer die Masse (Erkennung dreht selbst)."""
    monkeypatch.setattr(be, "_pillow_nutzbar", lambda: False)
    umgebung.pc.vorschau = _jpeg(120, 80, orientierung=6)
    umgebung.erkennung.gesichter = [[8.0, 12.0, 40.0, 60.0]]
    r = be.bild_erkennen("111")
    assert (r["breite"], r["hoehe"]) == (80, 120)
    assert r["gesichter"][0]["bbox_norm"] == [0.1, 0.1, 0.5, 0.5]


def test_k3_vorschau_png_masse(umgebung, monkeypatch):
    monkeypatch.setattr(be, "_pillow_nutzbar", lambda: False)
    puffer = io.BytesIO()
    Image.new("RGB", (50, 40)).save(puffer, format="PNG")
    umgebung.pc.vorschau = puffer.getvalue()
    umgebung.erkennung.gesichter = [[5.0, 4.0, 10.0, 8.0]]
    r = be.bild_erkennen("111")
    assert (r["breite"], r["hoehe"]) == (50, 40)


def test_k3_vorschau_ohne_lesbare_masse_meldet_bild_nicht_lesbar(umgebung, monkeypatch):
    monkeypatch.setattr(be, "_pillow_nutzbar", lambda: False)
    umgebung.pc.vorschau = b"das ist kein Bild"
    r = be.bild_erkennen("111")
    assert r["ok"] is False and r["grund"] == "bild_unlesbar"
    assert umgebung.erkennung.aufrufe == []


# ── 4: nichts auf Platte ───────────────────────────────────────────────────

def _baum(wurzel):
    return sorted((str(p.relative_to(wurzel)), p.stat().st_size, p.stat().st_mtime_ns)
                  for p in Path(wurzel).rglob("*"))


def test_k4_bild_erkennen_schreibt_nichts_auf_platte(umgebung, tmp_path, monkeypatch):
    umgebung.pc.original = _jpeg(2000, 1500, orientierung=6)
    umgebung.erkennung.gesichter = [[100.0, 100.0, 300.0, 300.0]]
    gq.gesichter_auf_bild("111")                                    # Lese-Cache vorwaermen
    vorher = _baum(tmp_path)
    schreibend = []
    echtes_open, echtes_replace = builtins.open, os.replace

    def spion_open(datei, modus="r", *a, **k):
        if isinstance(modus, str) and any(c in modus for c in "wax+"):
            schreibend.append(("open", str(datei), modus))
        return echtes_open(datei, modus, *a, **k)

    def spion_replace(*a, **k):
        schreibend.append(("replace", a))
        return echtes_replace(*a, **k)

    monkeypatch.setattr(builtins, "open", spion_open)
    monkeypatch.setattr(os, "replace", spion_replace)
    for name in ("write_text", "write_bytes", "mkdir", "touch", "rename", "unlink"):
        monkeypatch.setattr(Path, name, lambda self, *a, _n=name, **k: schreibend.append((_n, str(self))))

    r = be.bild_erkennen("111")
    r2 = _post("111")

    assert r["ok"] is True and r2.status_code == 200
    assert schreibend == []
    monkeypatch.undo()
    assert _baum(tmp_path) == vorher                                # leer/unveraendert wie vorher


def test_k4_vorschau_pfad_schreibt_ebenfalls_nichts(umgebung, tmp_path, monkeypatch):
    monkeypatch.setattr(be, "_pillow_nutzbar", lambda: False)
    umgebung.pc.vorschau = _jpeg(800, 600)
    umgebung.erkennung.gesichter = [[80.0, 60.0, 160.0, 120.0]]
    vorher = _baum(tmp_path)
    assert be.bild_erkennen("111")["ok"] is True
    assert _baum(tmp_path) == vorher


# ── 5: max_faces / timeout_s ───────────────────────────────────────────────

def test_k5_aufruf_enthaelt_max_faces_30_und_timeout_45(umgebung):
    umgebung.erkennung.gesichter = [[10.0, 10.0, 40.0, 40.0]]
    be.bild_erkennen("111")
    aufruf = umgebung.erkennung.aufrufe[0]
    assert aufruf["payload"]["op"] == "embed" and aufruf["payload"]["max_faces"] == 30
    assert aufruf["timeout_s"] == 45
    assert (be.MAX_GESICHTER, be.ERKENNUNG_TIMEOUT_S) == (30, 45)


def _lauf_attrappe(monkeypatch, gemerkt):
    def lauf(befehl, **k):
        gemerkt.append(k.get("timeout"))
        return subprocess.CompletedProcess(befehl, 0, stdout='{"ok": true, "gesichter": []}\n', stderr="")
    monkeypatch.setattr(face_service, "verfuegbar", lambda: True)
    monkeypatch.setattr(face_service.subprocess, "run", lauf)


def test_k5_bisherige_aufrufer_von_infer_behalten_30_sekunden(tmp_path, monkeypatch):
    zeiten = []
    _lauf_attrappe(monkeypatch, zeiten)
    bild = tmp_path / "x.jpg"
    bild.write_bytes(_jpeg(40, 30))
    assert face_service.embeddings_fuer_pfad(str(bild)) == []
    face_service.embedding_fuer_bbox(str(bild), [1, 1, 10, 10])
    face_service._infer({"op": "ping"})
    assert zeiten == [30, 30, 30]


def test_k5_infer_nimmt_timeout_s_entgegen_und_meldet_zeitgrenze(monkeypatch):
    zeiten = []
    _lauf_attrappe(monkeypatch, zeiten)
    assert face_service._infer({"op": "ping"}, timeout_s=45)["ok"] is True
    assert zeiten == [45]

    def zu_langsam(befehl, **k):
        raise subprocess.TimeoutExpired(befehl, k.get("timeout"))
    monkeypatch.setattr(face_service.subprocess, "run", zu_langsam)
    assert face_service._infer({"op": "ping"}, timeout_s=45) == {"ok": False, "fehler": "timeout"}


# ── 6: IoU-Abgleich ────────────────────────────────────────────────────────

def test_k6_deckungsgleicher_rahmen_ist_bekannt_mit_gid_und_name(umgebung):
    umgebung.erkennung.gesichter = [[100.0, 60.0, 200.0, 120.0]]   # 1000x? -> siehe Masse unten
    umgebung.pc.original = _jpeg(1000, 600)
    r = be.bild_erkennen("111")
    g = r["gesichter"][0]
    assert g["bbox_norm"] == [0.1, 0.1, 0.2, 0.2]
    assert g["status"] == "bekannt" and g["gid"] == "111:0" and g["name"] == "Person A"


def _mit_versatz(umgebung, dx):
    umgebung.pc.original = _jpeg(1000, 1000)
    umgebung.erkennung.gesichter = [[(0.1 + dx) * 1000, 100.0, 200.0, 200.0]]
    return be.bild_erkennen("111")["gesichter"][0]


def test_k6_knapp_ueber_halber_deckung_ist_bekannt(umgebung):
    g = _mit_versatz(umgebung, 0.06)                                # IoU ~ 0,54
    assert g["status"] == "bekannt" and g["gid"] == "111:0"


def test_k6_knapp_unter_halber_deckung_ist_neu(umgebung):
    g = _mit_versatz(umgebung, 0.07)                                # IoU ~ 0,48
    assert g["status"] == "neu" and "gid" not in g


def test_k6_iou_genau_halb_zaehlt_als_bekannt_und_rechnung_stimmt():
    assert be._iou([0, 0, 0.5, 0.5], [0, 0, 0.5, 0.25]) == 0.5
    assert be._iou([0, 0, 0.1, 0.1], [0.5, 0.5, 0.1, 0.1]) == 0.0
    erkannt = [[0, 0, 0.5, 0.25]]
    vorhanden = [{"gid": "7:0", "bbox_norm": [0, 0, 0.5, 0.5], "name": None}]
    assert be._abgleichen(erkannt, vorhanden) == [vorhanden[0]]


def test_k6_ein_vorhandenes_gesicht_wird_nur_einmal_vergeben(umgebung):
    umgebung.pc.original = _jpeg(1000, 1000)
    umgebung.erkennung.gesichter = [[100.0, 100.0, 200.0, 200.0], [110.0, 100.0, 200.0, 200.0]]
    gesichter = be.bild_erkennen("111")["gesichter"]
    assert [g["status"] for g in gesichter] == ["bekannt", "neu"]    # bester Treffer gewinnt


def test_k6_sicht_enthaelt_hand_und_verschobene_rahmen(umgebung):
    """Abgleich laeuft gegen die zusammengefuehrte Sicht (B1), nicht gegen die Rohdaten."""
    assert gq.bild_rahmen("111", [{"gid": "111:0", "bbox_norm": [0.5, 0.5, 0.2, 0.2]}])["ok"]
    umgebung.pc.original = _jpeg(1000, 1000)
    umgebung.erkennung.gesichter = [[500.0, 500.0, 200.0, 200.0], [100.0, 100.0, 200.0, 200.0]]
    g = be.bild_erkennen("111")["gesichter"]
    assert (g[0]["status"], g[0]["gid"]) == ("bekannt", "111:0")
    assert g[1]["status"] == "neu"


def test_k6_ohne_gruppendatei_wird_trotzdem_erkannt_alles_neu(umgebung):
    (umgebung.basis / gq.UNTERORDNER / gq.ZUORDNUNG_DATEINAME).unlink()
    gq._CACHE.clear()
    umgebung.erkennung.gesichter = [[10.0, 10.0, 40.0, 40.0]]
    r = be.bild_erkennen("111")
    assert r["ok"] is True and r["abgleich"] is False
    assert r["gesichter"][0]["status"] == "neu"


def test_k6_rahmen_ausserhalb_wird_auf_das_bild_begrenzt_zu_kleine_fallen_weg(umgebung):
    umgebung.pc.original = _jpeg(400, 300)
    umgebung.erkennung.gesichter = [[-20.0, -10.0, 100.0, 80.0],     # ragt links/oben hinaus
                                    [399.0, 299.0, 100.0, 100.0],    # fast ganz draussen -> unter 1 %
                                    [10.0, 10.0, 2.0, 2.0]]          # winzig
    r = be.bild_erkennen("111")
    assert [g["bbox_norm"] for g in r["gesichter"]] == [[0.0, 0.0, 0.2, round(70 / 300, 6)]]


# ── 7: Namensvorschlaege ───────────────────────────────────────────────────

def test_k7_vorschlaege_nur_name_und_abstand_keine_embeddings(umgebung, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    gesehen = []

    def personen(emb):
        gesehen.append(emb)
        return [{"name": "Person B", "rolle": "Freund", "distanz": 0.31, "sicher": True},
                {"name": "Person C", "rolle": "", "distanz": 0.5, "sicher": False}]
    monkeypatch.setattr(face_service, "erkenne_personen", personen)
    umgebung.erkennung.gesichter = [[10.0, 10.0, 40.0, 40.0]]

    r = be.bild_erkennen("111")
    antwort = _post("111")

    assert gesehen and gesehen[0] == [GEHEIM] * 4                    # der Katalog bekommt das Embedding
    g = r["gesichter"][0]
    assert g["vorschlaege"] == [{"name": "Person B", "abstand": 0.31},
                                {"name": "Person C", "abstand": 0.5}]
    for text in (json.dumps(r), antwort.text, caplog.text):
        assert str(GEHEIM) not in text and "embedding" not in text
    assert set(g) == {"bbox_norm", "status", "vorschlaege"}


def test_k7_katalogfehler_gibt_leere_vorschlaege_statt_wurf(umgebung, monkeypatch):
    def kaputt(emb):
        raise RuntimeError("Katalog kaputt")
    monkeypatch.setattr(face_service, "erkenne_personen", kaputt)
    umgebung.erkennung.gesichter = [[10.0, 10.0, 40.0, 40.0]]
    assert be.bild_erkennen("111")["gesichter"][0]["vorschlaege"] == []


def test_k7_gesicht_ohne_embedding_bleibt_mit_leeren_vorschlaegen(umgebung):
    umgebung.erkennung.antwort = {"ok": True, "gesichter": [
        {"bbox": [10.0, 10.0, 40.0, 40.0], "score": 0.9, "fehler": "x"}]}
    g = be.bild_erkennen("111")["gesichter"][0]
    assert g["vorschlaege"] == [] and g["status"] == "neu"


def test_k7_hoechstens_drei_vorschlaege(umgebung, monkeypatch):
    monkeypatch.setattr(face_service, "erkenne_personen", lambda emb: [
        {"name": f"Person {i}", "rolle": "", "distanz": 0.1 * i, "sicher": False} for i in range(1, 6)])
    umgebung.erkennung.gesichter = [[10.0, 10.0, 40.0, 40.0]]
    assert len(be.bild_erkennen("111")["gesichter"][0]["vorschlaege"]) == 3


# ── 8: ehrliche Fehler + HTTP-Status ───────────────────────────────────────

def test_k8_pcloud_nicht_erreichbar_502(umgebung):
    umgebung.pc.fehler_original = PCloudFehler("Download von pCloud fehlgeschlagen (ConnectError).")
    r = _post("111")
    assert r.status_code == 502
    assert r.json() == {"ok": False, "grund": "pcloud_nicht_erreichbar",
                        "fehler": "pCloud nicht erreichbar."}
    assert umgebung.erkennung.aufrufe == []


def test_k8_vorschau_pfad_pcloud_nicht_erreichbar_502(umgebung, monkeypatch):
    monkeypatch.setattr(be, "_pillow_nutzbar", lambda: False)
    umgebung.pc.fehler_vorschau = PCloudFehler("pCloud antwortete mit HTTP 500.")
    r = _post("111")
    assert r.status_code == 502 and r.json()["grund"] == "pcloud_nicht_erreichbar"


def test_k8_pcloud_nicht_konfiguriert_503(umgebung):
    umgebung.pc.fehler_original = PCloudNichtKonfiguriert("PCLOUD_TOKEN fehlt in der .env.")
    r = _post("111")
    assert r.status_code == 503
    assert r.json() == {"ok": False, "grund": "pcloud_nicht_konfiguriert",
                        "fehler": "pCloud ist nicht konfiguriert."}


def test_k8_bild_ueber_25_mb_ist_zu_gross_413(umgebung):
    umgebung.pc.fehler_original = PCloudZuGross("Datei ist 30.0 MB gross")
    r = _post("111")
    assert r.status_code == 413
    assert r.json() == {"ok": False, "grund": "bild_zu_gross", "fehler": "Bild zu groß (über 25 MB)."}


def test_k8_erkennung_nicht_verfuegbar_503_ohne_pcloud_zugriff(umgebung, monkeypatch):
    monkeypatch.setattr(face_service, "verfuegbar", lambda: False)
    r = _post("111")
    assert r.status_code == 503
    assert r.json() == {"ok": False, "grund": "erkennung_nicht_verfuegbar",
                        "fehler": "Erkennung nicht verfügbar."}
    assert umgebung.pc.aufrufe == [] and umgebung.erkennung.aufrufe == []


def test_k8_zeitgrenze_504(umgebung):
    umgebung.erkennung.antwort = {"ok": False, "fehler": "timeout"}
    r = _post("111")
    assert r.status_code == 504
    assert r.json()["grund"] == "zeitgrenze" and "Zeitgrenze" in r.json()["fehler"]
    assert "45" in r.json()["fehler"]


def test_k8_sonstiger_erkennungsfehler_502_ohne_innere_meldung(umgebung):
    umgebung.erkennung.antwort = {"ok": False, "fehler": "keine JSON-Ausgabe: /root/geheim/pfad"}
    r = _post("111")
    assert r.status_code == 502 and r.json()["grund"] == "erkennung_fehlgeschlagen"
    assert "geheim" not in r.text


def test_k8_engine_verschwindet_zwischen_pruefung_und_lauf_503(umgebung):
    umgebung.erkennung.antwort = {"ok": False, "fehler": "face-engine nicht verfuegbar"}
    r = _post("111")
    assert r.status_code == 503 and r.json()["grund"] == "erkennung_nicht_verfuegbar"


def test_k8_unlesbares_original_422(umgebung):
    umgebung.pc.original = b"kein Bild"
    r = _post("111")
    assert r.status_code == 422 and r.json()["grund"] == "bild_unlesbar"


def test_k8_dekompressionsbombe_ist_zu_gross_413(umgebung, monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)             # 400x300 = 120000 > 2 * 1000
    r = _post("111")
    assert r.status_code == 413 and r.json()["grund"] == "bild_zu_gross"


@pytest.mark.parametrize("fileid", ["", "abc", "-5", "0", "1.5", "12 3", " ", "1" * 21, None, True, [], {}, -3, 0])
def test_k8_ungueltige_fileid_400(umgebung, fileid):
    r = _client().post("/api/gruppen/bild-erkennen", json={"fileid": fileid})
    assert r.status_code == 400
    assert r.json() == {"ok": False, "grund": "fileid_ungueltig", "fehler": "Ungültige Bildkennung."}
    assert umgebung.pc.aufrufe == [] and umgebung.erkennung.aufrufe == []


def test_k8_fehlende_fileid_ist_422(umgebung):
    assert _client().post("/api/gruppen/bild-erkennen", json={}).status_code == 422


def test_k8_fileid_als_zahl_und_mit_fuehrenden_nullen(umgebung):
    umgebung.erkennung.gesichter = [[10.0, 10.0, 40.0, 40.0]]
    assert _client().post("/api/gruppen/bild-erkennen", json={"fileid": 111}).status_code == 200
    assert _client().post("/api/gruppen/bild-erkennen", json={"fileid": "0111"}).status_code == 200
    assert all(a[1] == 111 for a in umgebung.pc.aufrufe)


def test_k8_alle_gruende_haben_einen_status():
    assert be.STATUS_JE_GRUND == {
        "fileid_ungueltig": 400, "pcloud_nicht_konfiguriert": 503, "pcloud_nicht_erreichbar": 502,
        "bild_zu_gross": 413, "bild_unlesbar": 422, "erkennung_nicht_verfuegbar": 503,
        "zeitgrenze": 504, "erkennung_fehlgeschlagen": 502}


def test_erfolg_antwort_form(umgebung):
    umgebung.erkennung.gesichter = []
    r = _post("111")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "fileid": "111", "quelle": "original_1600", "breite": 400,
                        "hoehe": 300, "abgleich": True, "gesichter": []}


# ── 9: Schutz wie die uebrigen /api/gruppen-Routen ──────────────────────────

def test_k9_main_haengt_den_gruppen_router_hinter_den_schluessel():
    quelle = open(os.path.join(BACKEND, "app", "main.py"), encoding="utf-8").read()
    assert ("app.include_router(gruppen.router, dependencies=[Depends(auth.require_api_key)])"
            in quelle)


def test_k9_route_ohne_schluessel_401_mit_schluessel_200(umgebung, monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-schluessel-erfunden")
    app = FastAPI()
    app.include_router(gruppen_router.router, dependencies=[Depends(auth.require_api_key)])
    c = TestClient(app)
    assert c.post("/api/gruppen/bild-erkennen", json={"fileid": "111"}).status_code == 401
    assert umgebung.pc.aufrufe == []
    ok = c.post("/api/gruppen/bild-erkennen", json={"fileid": "111"},
                headers={"X-API-Key": "test-schluessel-erfunden"})
    assert ok.status_code == 200 and ok.json()["ok"] is True


def test_k9_route_ist_im_router_eingetragen():
    pfade = {(r.path, tuple(sorted(r.methods))) for r in gruppen_router.router.routes}
    assert ("/api/gruppen/bild-erkennen", ("POST",)) in pfade
    quelle = open(os.path.join(BACKEND, "app", "router", "gruppen.py"), encoding="utf-8").read()
    assert "POST /api/gruppen/bild-erkennen" in quelle.split('"""')[1]       # Docstring-Liste oben
