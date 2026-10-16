"""Schritt B (16.10.2026): Einzelnen Rahmen neu vektorisieren — mit Protokoll.

Auftrag aus der Planfassung 13 des Rahmeneditors (Abschnitt 4, Schritt B):

  „Dienst ruft `embed_crop` fuer den (verschobenen) Rahmen, speichert den Vektor
   als Referenz ueber den Gesichter-Weg, protokolliert die Cosinus-Distanz."

Pruefkriterium (wortgetreu aus dem Plan):

  (1) erfundene Vektoren: unter 0,05 **keine** neue Referenz, darueber **eine**;
  (2) zweiter Aufruf mit demselben Rahmen aendert nichts (idempotent);
  (3) Fremdaufruf-Nachweis scharf: der Zaehler auf **externen/Netz-Aufrufen** muss
      **0** sein (Bilddaten verlassen das Geraet nicht), der **Engine-/Subprozess-
      Aufruf** ist der gewollte Aufruf und muss **>= 1** zaehlen.

Die Tests fahren den ECHTEN Weg (`beantworte_runde` / `ergaenze_person_mit_bbox` ->
`face_service.embedding_fuer_bbox` -> `face_service._infer`); nur der Subprozess
selbst ist gefakt — er liefert je Rahmen einen erfundenen Vektor. Alles laeuft auf
`tmp_path`; Sebastians echter Katalog, Fortschritt und Bilder werden nie angefasst.
"""

import os
import socket
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

import pytest  # noqa: E402
from pathlib import Path  # noqa: E402

from app.services import chat_verlauf, face_service, gesicht_quiz, gesichter_service  # noqa: E402

IW, IH = 100, 200

# Zwei verschiedene Rahmen desselben Bildes (absolute Pixel) -> verschiedene Regionen.
RAHMEN_1 = [10.0, 20.0, 30.0, 40.0]
RAHMEN_2 = [60.0, 120.0, 20.0, 40.0]

# Erfundene Vektoren (3-dim, Cosinus genuegt):
V_A = [1.0, 0.0, 0.0]          # erste Referenz der Person
V_NAH = [1.0, 0.005, 0.0]      # Distanz zu V_A ~1,25e-05  -> UNTER 0,05
V_FERN = [0.5, 0.866, 0.0]     # Distanz zu V_A = 0,5      -> UEBER 0,05


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


@pytest.fixture()
def netz(monkeypatch):
    """Scharfer Fremdaufruf-Nachweis: jeder Netz-Aufruf faellt auf und wird gezaehlt."""
    aufrufe = []

    def verboten(*a, **k):
        aufrufe.append(a)
        raise AssertionError("Netzaufruf im Gesichts-Weg - Bilddaten duerfen das Geraet nicht verlassen")

    monkeypatch.setattr(socket.socket, "connect", verboten, raising=True)
    monkeypatch.setattr(socket, "create_connection", verboten, raising=True)
    return aufrufe


def _engine(monkeypatch, *, vektor_je_rahmen, verfuegbar=True):
    """Fakt nur den Debian-Subprozess (`_infer`) und zaehlt seine Aufrufe.

    Der Zaehler `engine_ops` steht auf den **Engine**-Aufrufen (gewollt, >= 1);
    ein getrennter Zaehler steht auf den Detektor-Aufrufen (`embed`).
    """
    zaehler = {"engine_ops": [], "detektor_ops": []}

    def fake_infer(payload):
        op = payload.get("op")
        zaehler["engine_ops"].append(op)
        if not verfuegbar:
            return {"ok": False, "fehler": "face-engine nicht verfuegbar"}
        if op == "embed_crop":
            key = tuple(payload.get("bbox") or [])
            v = vektor_je_rahmen(key)
            if v is None:
                return {"ok": False, "fehler": "kein Gesicht im Ausschnitt"}
            return {"ok": True, "embedding": list(v)}
        if op == "embed":
            zaehler["detektor_ops"].append(op)
            return {"ok": True, "gesichter": [{"bbox": list(RAHMEN_2), "score": 0.9,
                                               "embedding": list(V_FERN)}]}
        if op == "ping":
            return {"ok": True}
        return {"ok": False, "fehler": "unbekannte op"}

    monkeypatch.setattr(face_service, "verfuegbar", lambda: verfuegbar)
    monkeypatch.setattr(face_service, "_infer", fake_infer)
    return zaehler


def _refs(name):
    p = gesichter_service.person_finden(name)
    return gesichter_service._refs_of(p) if p else []


def _vektoren(name):
    return [r["embedding"] for r in _refs(name)]


# ---------------------------------------------------------------------------
# (1) Schwelle: unter 0,05 keine neue Referenz, darueber eine
# ---------------------------------------------------------------------------

def test_darueber_erzeugt_neue_referenz_und_meldet_distanz(bild, monkeypatch, netz):
    """Der verschobene Rahmen (anderer Ausschnitt) liegt ueber 0,05 -> +1 Referenz."""
    z = _engine(monkeypatch, vektor_je_rahmen=lambda key: V_A)
    erster = gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=RAHMEN_1)
    assert erster["referenz_geschrieben"] is True
    assert erster["cosinus_distanz"] is None          # erste Referenz: kein Vergleich
    assert len(_refs("Anna")) == 1

    # zweiter Rahmen, Vektor klar ueber der Schwelle (0,5)
    z2 = _engine(monkeypatch, vektor_je_rahmen=lambda key: V_FERN)
    r = gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=RAHMEN_2)

    assert r["ok"] is True
    assert r["referenz_geschrieben"] is True
    assert r["hinzugefuegt"] is True
    assert r["cosinus_distanz"] is not None and r["cosinus_distanz"] > 0.05
    assert r["cosinus_distanz"] == pytest.approx(0.5, abs=1e-6)
    assert len(_refs("Anna")) == 2
    assert _vektoren("Anna") == [V_A, V_FERN]

    # Fremdaufruf-Nachweis: Engine >= 1 (der gewollte Aufruf), Netz = 0
    assert z["engine_ops"], "Engine wurde bei B gar nicht aufgerufen"
    assert "embed_crop" in z["engine_ops"]
    assert len(z2["engine_ops"]) == 1 and z2["engine_ops"] == ["embed_crop"]
    assert netz == [], "es wurde ein Netzaufruf versucht"


def test_unter_schwelle_keine_neue_referenz_und_distanz_gemeldet(bild, monkeypatch, netz):
    """Fast identischer Ausschnitt (Distanz ~1e-05) -> KEINE neue Referenz, Grund + Zahl."""
    z = _engine(monkeypatch, vektor_je_rahmen=lambda key: V_A)
    gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=RAHMEN_1)

    z2 = _engine(monkeypatch, vektor_je_rahmen=lambda key: V_NAH)
    r = gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=RAHMEN_2)

    assert r["ok"] is True
    assert r["referenz_geschrieben"] is False
    assert r["hinzugefuegt"] is False
    assert r["cosinus_distanz"] is not None and r["cosinus_distanz"] < 0.05
    assert "0,05" in r["grund"]
    assert len(_refs("Anna")) == 1
    assert _vektoren("Anna") == [V_A]                 # Bestand unveraendert
    assert z["engine_ops"] and netz == []


def test_erster_aufruf_neuer_person_meldet_keine_distanz(bild, monkeypatch, netz):
    """Ehrlich: ohne vorhandene Referenz gibt es nichts zu vergleichen (None)."""
    _engine(monkeypatch, vektor_je_rahmen=lambda key: V_FERN)
    r = gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=RAHMEN_1)

    assert r["ok"] is True and r["ist_neu"] is True
    assert r["cosinus_distanz"] is None
    assert netz == []


# ---------------------------------------------------------------------------
# (2) Idempotenz: derselbe Rahmen zweimal aendert nichts
# ---------------------------------------------------------------------------

def test_zweiter_aufruf_desselben_rahmens_aendert_nichts(bild, monkeypatch, netz):
    z = _engine(monkeypatch, vektor_je_rahmen=lambda key: V_A)
    erst = gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=RAHMEN_1)
    assert erst["referenz_geschrieben"] is True
    nach_erst = _vektoren("Anna")

    z2 = _engine(monkeypatch, vektor_je_rahmen=lambda key: V_FERN)   # fremder Vektor
    nochmal = gesicht_quiz.beantworte_runde(bild, "Anna", False, bbox=RAHMEN_1)

    assert nochmal["uebersprungen"] is True
    assert nochmal["referenz_geschrieben"] is False
    assert nochmal["cosinus_distanz"] is None            # Fruehausstieg vor der Erkennung
    assert _vektoren("Anna") == nach_erst, "der zweite Aufruf hat den Bestand veraendert"
    assert len(_refs("Anna")) == 1
    # der Fruehausstieg spart den Engine-Aufruf wirklich ein
    assert z2["engine_ops"] == []
    assert z["engine_ops"] == ["embed_crop"] and netz == []


# ---------------------------------------------------------------------------
# (3) Der zweite Weg mit selbst gezeichnetem Rahmen meldet ebenso
# ---------------------------------------------------------------------------

def test_ergaenze_person_meldet_distanz_und_schwelle(bild, monkeypatch, netz):
    _engine(monkeypatch, vektor_je_rahmen=lambda key: V_A)
    gesicht_quiz.ergaenze_person_mit_bbox(bild, "Anna", False, bbox=RAHMEN_1)

    _engine(monkeypatch, vektor_je_rahmen=lambda key: V_NAH)
    nah = gesicht_quiz.ergaenze_person_mit_bbox(bild, "Anna", False, bbox=RAHMEN_2)
    assert nah["cosinus_distanz"] is not None and nah["cosinus_distanz"] < 0.05
    assert nah["referenz_geschrieben"] is False

    rahmen_3 = [60.0, 20.0, 20.0, 40.0]
    _engine(monkeypatch, vektor_je_rahmen=lambda key: V_FERN)
    fern = gesicht_quiz.ergaenze_person_mit_bbox(bild, "Anna", False, bbox=rahmen_3)
    assert fern["cosinus_distanz"] == pytest.approx(0.5, abs=1e-6)
    assert fern["referenz_geschrieben"] is True
    assert len(_refs("Anna")) == 2
    assert netz == []
