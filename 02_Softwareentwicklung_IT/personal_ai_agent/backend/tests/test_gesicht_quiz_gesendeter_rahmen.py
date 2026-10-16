"""A3 (16.10.2026): Der GESENDETE Rahmen gewinnt.

Sebastians Befund: „Rahmen verschieben, speichern — Position ist nicht im
Datenbestand." Ursache war `beantworte_runde`: der Normalzweig uebernahm
Rahmen UND Vektor des **Detektors** (`gesicht_quiz.py:704–705`) und meldete
trotzdem `ok`. Der gesendete Rahmen kam nur im Ausweichzweig zum Zug.

Diese Tests halten die Auflagen der Planpruefung Fassung 13 fest:

(1) Mit gesendetem Rahmen traegt die gespeicherte Referenz
    (a) numerisch GENAU die gesendeten Koordinaten und
    (b) einen Vektor, der zum gesendeten Ausschnitt gehoert (nicht den des
        Detektors) — gemessen an der gefakten Engine, die fuer `embed` und
        `embed_crop` VERSCHIEDENE Vektoren liefert.
(2) Ohne gesendeten Rahmen gilt — und nur dann — `erkannt` (Detektor-Rahmen).
(3) Jeder Ausstiegsgrund meldet `referenz_geschrieben: false` samt Grund; ein
    gruener Fall ohne Datei-Beleg ist damit nicht moeglich.
(4) `ergaenze_person_mit_bbox` meldet den gesendeten Rahmen ebenso.

Alle Tests arbeiten auf tmp_path; Sebastians echter Katalog und Fortschritt
werden nie angefasst.
"""

import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

import pytest  # noqa: E402
from pathlib import Path  # noqa: E402

from app.services import chat_verlauf, face_service, gesicht_quiz, gesichter_service  # noqa: E402

IW, IH = 100, 200
GESENDET = [10.0, 20.0, 30.0, 40.0]        # vom Nutzer bestaetigter Rahmen
DETEKTOR = [60.0, 120.0, 20.0, 40.0]       # Rahmen der Erkennung (andere Stelle)
V_EMBED = [1.0, 0.0, 0.0]                  # Vektor des Detektor-Ausschnitts
V_CROP = [0.25, 0.75, 0.0]                 # Vektor des GESENDETEN Ausschnitts


@pytest.fixture(autouse=True)
def _isoliert(tmp_path, monkeypatch):
    monkeypatch.setattr(gesichter_service, "KATALOG_DATEI",
                        Path(tmp_path) / "gesichter_katalog.json")
    monkeypatch.setattr(gesicht_quiz, "_FORTSCHRITT_OVERRIDE",
                        str(Path(tmp_path) / "quiz_fortschritt.json"))
    monkeypatch.setattr(chat_verlauf, "verlauf_nachricht_anhaengen", lambda *a, **k: None)
    yield


@pytest.fixture()
def bild(tmp_path):
    from PIL import Image
    p = tmp_path / "lieblingsbild.jpg"
    Image.new("RGB", (IW, IH), (30, 30, 30)).save(p, "JPEG")
    return str(p)


def _engine(monkeypatch, *, verfuegbar=True, crop=V_CROP):
    """Gefakte Engine: `embed` (Detektor) und `embed_crop` (Ausschnitt) VERSCHIEDEN.

    Ohne Engine liefert auch die Detektion nichts — wie in echt (der Subprozess
    ist dann nicht gestartet).
    """
    monkeypatch.setattr(face_service, "verfuegbar", lambda: verfuegbar)
    monkeypatch.setattr(face_service, "embeddings_fuer_pfad",
                        lambda pfad: ([{"bbox": list(DETEKTOR), "score": 0.9,
                                        "embedding": list(V_EMBED)}] if verfuegbar else []))
    monkeypatch.setattr(gesicht_quiz, "_gesichter_robust",
                        lambda pfad: ([{"bbox": list(DETEKTOR), "score": 0.9,
                                        "embedding": list(V_EMBED)}] if verfuegbar else []))
    monkeypatch.setattr(face_service, "embedding_fuer_bbox",
                        lambda pfad, bbox: (list(crop) if (crop and list(bbox) == list(GESENDET))
                                            else None))


def _gespeicherte_refs(name):
    p = gesichter_service.person_finden(name)
    return gesichter_service._refs_of(p) if p else []


# ---------------------------------------------------------------------------
# (1) Koordinaten UND Vektor des gesendeten Rahmens
# ---------------------------------------------------------------------------

def test_gesendeter_rahmen_gewinnt_bei_koordinaten_und_vektor(bild, monkeypatch):
    _engine(monkeypatch)
    r = gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=GESENDET)

    assert r["ok"] is True
    assert r["rahmen_gespeichert"] == "gesendet"
    assert r["referenz_geschrieben"] is True
    assert r["grund"] == ""

    refs = _gespeicherte_refs("Anna")
    assert len(refs) == 1
    # (a) Koordinaten: numerisch genau der gesendete Rahmen.
    assert refs[0]["bbox"] == GESENDET
    assert refs[0]["bbox"] != DETEKTOR
    # (b) Vektor: der des GESENDETEN Ausschnitts, nicht der des Detektors.
    assert refs[0]["embedding"] == V_CROP
    assert refs[0]["embedding"] != V_EMBED


def test_vektor_und_koordinaten_gehoeren_zusammen(bild, monkeypatch):
    """Gegenprobe: nur `neue_bbox` auszutauschen wuerde hier rot (Vektor bleibt Detektor)."""
    _engine(monkeypatch, crop=[0.5, 0.5, 0.0])
    gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=GESENDET)
    ref = _gespeicherte_refs("Anna")[0]
    assert ref["bbox"] == GESENDET and ref["embedding"] == [0.5, 0.5, 0.0]
    assert ref["embedding"] != V_EMBED


# ---------------------------------------------------------------------------
# (2) Gegenprobe OHNE gesendeten Rahmen
# ---------------------------------------------------------------------------

def test_ohne_gesendeten_rahmen_gilt_erkannt(bild, monkeypatch):
    _engine(monkeypatch)
    r = gesicht_quiz.beantworte_runde(bild, "Anna", False)

    assert r["ok"] is True
    assert r["rahmen_gespeichert"] == "erkannt"
    assert r["referenz_geschrieben"] is True
    refs = _gespeicherte_refs("Anna")
    assert refs[0]["bbox"] == DETEKTOR
    assert refs[0]["embedding"] == V_EMBED


def test_rueckfall_wird_als_rueckfall_gemeldet(bild, monkeypatch):
    """Gesendeter Rahmen, aber die Ausschnitt-Einbettung scheitert -> Detektor als
    Rueckfall, ehrlich benannt (nicht still als 'gesendet' verkauft)."""
    _engine(monkeypatch, crop=None)
    r = gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=GESENDET)

    assert r["ok"] is True
    assert r["rahmen_gespeichert"] == "erkannt"
    assert "Rueckfall" in r["grund"]
    assert _gespeicherte_refs("Anna")[0]["bbox"] == DETEKTOR


# ---------------------------------------------------------------------------
# (3) Ehrliche Gruende
# ---------------------------------------------------------------------------

def test_engine_fehlt_mit_gesendetem_rahmen_meldet_grund(bild, monkeypatch):
    _engine(monkeypatch, verfuegbar=False)
    r = gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=GESENDET)

    assert r["ok"] is False
    assert r["referenz_geschrieben"] is False
    assert r["rahmen_gespeichert"] is None
    assert "Engine" in r["grund"]
    assert gesichter_service.liste_personen() == []


def test_kein_gesicht_ohne_rahmen_meldet_grund(bild, monkeypatch):
    monkeypatch.setattr(face_service, "verfuegbar", lambda: True)
    monkeypatch.setattr(gesicht_quiz, "_gesichter_robust", lambda pfad: [])
    r = gesicht_quiz.beantworte_runde(bild, "Anna", False)
    assert r["ok"] is False
    assert r["referenz_geschrieben"] is False and r["grund"]


def test_fruehausstieg_meldet_keine_neue_referenz(bild, monkeypatch):
    _engine(monkeypatch)
    gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=GESENDET)
    nochmal = gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=GESENDET)

    assert nochmal["uebersprungen"] is True
    assert nochmal["referenz_geschrieben"] is False
    assert nochmal["rahmen_gespeichert"] is None
    assert "bereits bestaetigt" in nochmal["grund"]
    assert len(_gespeicherte_refs("Anna")) == 1


def test_cosinus_riegel_meldet_keine_neue_referenz(bild, monkeypatch):
    """Identischer Vektor bei anderer Region -> keine neue Referenz, mit Grund."""
    _engine(monkeypatch)
    gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=GESENDET)
    zweiter_rahmen = [70.0, 130.0, 20.0, 40.0]
    monkeypatch.setattr(face_service, "embedding_fuer_bbox",
                        lambda pfad, bbox: list(V_CROP))       # gleicher Vektor
    r = gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=zweiter_rahmen)

    assert r["ok"] is True
    assert r["referenz_geschrieben"] is False
    assert "0,05" in r["grund"]
    assert len(_gespeicherte_refs("Anna")) == 1


# ---------------------------------------------------------------------------
# (4) Der Weg mit selbst gezeichnetem Rahmen
# ---------------------------------------------------------------------------

def test_ergaenze_person_mit_bbox_meldet_gesendeten_rahmen(bild, monkeypatch):
    _engine(monkeypatch)
    r = gesicht_quiz.ergaenze_person_mit_bbox(bild, "Anna", False, bbox=GESENDET)

    assert r["ok"] is True
    assert r["referenz_geschrieben"] is True
    assert r["rahmen_gespeichert"] == "gesendet"
    assert r["grund"] == ""
    ref = _gespeicherte_refs("Anna")[0]
    assert ref["bbox"] == GESENDET and ref["embedding"] == V_CROP


def test_ergaenze_person_ohne_vektor_meldet_grund(bild, monkeypatch):
    _engine(monkeypatch, crop=None)
    r = gesicht_quiz.ergaenze_person_mit_bbox(bild, "Anna", False, bbox=GESENDET)

    assert r["ok"] is False
    assert r["referenz_geschrieben"] is False
    assert r["rahmen_gespeichert"] is None
    assert r["grund"]
    assert gesichter_service.liste_personen() == []


def test_ergaenze_person_ohne_engine_meldet_grund(bild, monkeypatch):
    _engine(monkeypatch, verfuegbar=False)
    r = gesicht_quiz.ergaenze_person_mit_bbox(bild, "Anna", False, bbox=GESENDET)

    assert r["ok"] is False
    assert r["referenz_geschrieben"] is False
    assert "Engine" in r["grund"]
