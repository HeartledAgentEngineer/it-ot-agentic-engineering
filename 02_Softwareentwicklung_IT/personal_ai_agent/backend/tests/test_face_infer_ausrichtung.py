"""Pruefungen fuer die Gesichts-Ausrichtung in ``backend/face_infer.py``.

Hier wird **nur** die Aufrufform von ``alignCrop`` geprueft — und der Waechter
gegen bit-identische Merkmale. Alles OHNE ``cv2``, OHNE Netz und OHNE echte
Bilder: die Bildbibliothek wird durch Attrappen ersetzt (``_lazy_load`` und
``dekodiere_bild`` werden im Modul ausgetauscht), die Vektoren sind erfundene
Zahlen.

Hintergrund (gemessen, nicht behauptet): ``cv2.FaceRecognizerSF.alignCrop``
erwartet die **volle** YuNet-Zeile mit 15 Werten (``x, y, w, h, 5 Landmarken-
Paare, score`` = 60 Byte float32). Wird nur das 5x2-Landmarken-Array (40 Byte)
uebergeben, prueft OpenCV die Form nicht und liest 20 Byte ueber den Puffer
hinaus — alle Gesichter eines Bildes bekommen denselben Ausschnitt und damit
denselben Vektor.

Aufruf:
    cd backend && .venv/Scripts/python.exe -m pytest tests/test_face_infer_ausrichtung.py -q
"""

from __future__ import annotations

import base64
import importlib.util
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
QUELLE_DATEI = REPO / "backend" / "face_infer.py"
QUELLE = QUELLE_DATEI.read_text(encoding="utf-8")


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


fi = _laden(QUELLE_DATEI, "face_infer_ausrichtung")

LAENGE = 128
# Erfundene pCloud-Kennung (nur Ziffern, kein Pfad).
BILD_A = "1234567"


def _zeile(i: int) -> list:
    """Eine volle YuNet-Zeile mit 15 Werten — Landmarken hängen von ``i`` ab."""
    bbox = [float(i), 2.0, 3.0, 4.0]
    landm = [[float(1 + i), 1.0], [float(2 + i), 1.0], [float(1 + i), 2.0],
             [float(1 + i), 3.0], [float(2 + i), 3.0]]
    return bbox + [wert for punkt in landm for wert in punkt] + [0.9]


class AttrappeRec:
    """Bildet ``FaceRecognizerSF`` nach und merkt sich die Argumentform."""

    def __init__(self, merkmale=None):
        self._merkmale = list(merkmale) if merkmale else None
        self.aufrufe: list = []
        self._zaehler = 0

    def alignCrop(self, bild, zeile):
        reihe = np.asarray(zeile)
        self.aufrufe.append((reihe.shape, str(reihe.dtype)))
        return f"ausschnitt-{self._zaehler}"

    def feature(self, ausschnitt):
        if self._merkmale:
            werte = self._merkmale[self._zaehler % len(self._merkmale)]
        else:
            self._zaehler += 1
            werte = [0.05 * (self._zaehler % 9) + 0.02] * LAENGE
        if self._merkmale:
            self._zaehler += 1
        return np.asarray(werte, dtype=np.float32).reshape(1, -1)


class AttrappeDet:
    """Bildet ``FaceDetectorYN`` nach (liefert fertige Zeilen)."""

    def __init__(self, gesichter=None, fehler=False):
        self._gesichter = gesichter
        self._fehler = fehler
        self.groesse = None

    def setInputSize(self, groesse):
        self.groesse = groesse

    def detect(self, bild):
        if self._fehler:
            raise RuntimeError("detektorkaputt")
        if self._gesichter is None:
            return (True, None)
        return (True, np.asarray(self._gesichter, dtype=float))


def _lazy(monkeypatch, det, rec):
    """``_lazy_load`` durch die Attrappen ersetzen (kein cv2)."""
    monkeypatch.setattr(fi, "_lazy_load", lambda: (det, rec))


def _bild_array(hoehe=10, breite=20):
    return np.zeros((hoehe, breite, 3), np.uint8)


# ── 1. _align_face: die volle Zeile geht an alignCrop ─────────────────────

def test_align_face_gibt_die_volle_zeile_weiter(monkeypatch):
    rec = AttrappeRec()
    _lazy(monkeypatch, AttrappeDet(), rec)
    fi._align_face(_bild_array(), np.arange(15, dtype=float))
    assert len(rec.aufrufe) == 1
    form, art = rec.aufrufe[0]
    assert form == (15,), "alignCrop braucht die 15-Werte-Zeile, nicht 5x2"
    assert "float32" in art


def test_align_face_mit_einer_5x2_maske_ergibt_nur_zehn_werte(monkeypatch):
    """Eine hereingereichte 5x2-Maske hat nur 10 Werte — genau der Fehler.

    Der echte ``alignCrop`` erwartet 15. Deshalb muss der Aufrufer die **volle**
    Detektionszeile liefern (``test_quelle_uebergibt_die_zeile``); diese
    Pruefung zeigt die kaputte Form ausdruecklich als Gegenstueck.
    """
    rec = AttrappeRec()
    _lazy(monkeypatch, AttrappeDet(), rec)
    fi._align_face(_bild_array(), np.zeros((5, 2), dtype=float))
    assert rec.aufrufe[0][0] == (10,)


# ── 2. _embed_crop_pixels: auch hier die volle Zeile ──────────────────────

def test_embed_crop_pixels_uebergibt_die_volle_zeile(monkeypatch):
    rec = AttrappeRec()
    det = AttrappeDet([_zeile(1)])
    _lazy(monkeypatch, det, rec)
    bild = _bild_array(40, 60)
    ergebnis = fi._embed_crop_pixels(bild, [5, 5, 20, 20])
    assert ergebnis is not None
    assert rec.aufrufe, "alignCrop muss gerufen worden sein"
    assert rec.aufrufe[0][0] == (15,)


def test_embed_crop_pixels_fallback_ohne_gesicht(monkeypatch):
    """Ohne Detektion im Ausschnitt greift der Skalier-Rueckfall.

    Der Rueckfall braucht ``cv2``; fehlt es (dieses venv), kommt ehrlich
    ``None`` zurueck — und es wurde **kein** ``alignCrop`` gerufen.
    """
    import importlib.util
    rec = AttrappeRec()
    _lazy(monkeypatch, AttrappeDet(None), rec)
    bild = _bild_array(40, 60)
    ergebnis = fi._embed_crop_pixels(bild, [5, 5, 20, 20])
    assert rec.aufrufe == [], "ohne Gesicht kein alignCrop"
    if importlib.util.find_spec("cv2") is None:
        assert ergebnis is None
    else:
        assert ergebnis is not None


# ── 3. op_embed: Aufrufform + Waechter ────────────────────────────────────

def _payload(anzahl, bbox=None):
    return {"bild_base64": base64.b64encode(b"erfunden").decode(),
            "max_faces": anzahl, "bbox": bbox}


def test_op_embed_gibt_die_volle_zeile_und_getrennte_vektoren(monkeypatch):
    rec = AttrappeRec()
    det = AttrappeDet([_zeile(0), _zeile(4)])
    _lazy(monkeypatch, det, rec)
    monkeypatch.setattr(fi, "dekodiere_bild", lambda roh: _bild_array(10, 20))
    ergebnis = fi.op_embed(_payload(2))
    assert ergebnis["ok"] is True
    assert len(ergebnis["gesichter"]) == 2
    assert all(aufruf[0] == (15,) for aufruf in rec.aufrufe)
    merkmale = [gesicht["embedding"] for gesicht in ergebnis["gesichter"]]
    assert merkmale[0] != merkmale[1]


def test_op_embed_waechter_bei_bit_identischen_merkmalen(monkeypatch):
    rec = AttrappeRec(merkmale=[[0.5] * LAENGE, [0.5] * LAENGE])
    det = AttrappeDet([_zeile(0), _zeile(4)])
    _lazy(monkeypatch, det, rec)
    monkeypatch.setattr(fi, "dekodiere_bild", lambda roh: _bild_array(10, 20))
    ergebnis = fi.op_embed(_payload(2))
    assert ergebnis["ok"] is False
    assert "Waechter" in ergebnis["fehler"]


def test_op_embed_ohne_gesicht_ist_ok_leer(monkeypatch):
    rec = AttrappeRec()
    _lazy(monkeypatch, AttrappeDet(None), rec)
    monkeypatch.setattr(fi, "dekodiere_bild", lambda roh: _bild_array(10, 20))
    ergebnis = fi.op_embed(_payload(0))
    assert ergebnis["ok"] is True
    assert ergebnis["gesichter"] == []


def test_op_embed_ein_gesicht_kein_waechter(monkeypatch):
    rec = AttrappeRec(merkmale=[[0.5] * LAENGE])
    _lazy(monkeypatch, AttrappeDet([_zeile(0)]), rec)
    monkeypatch.setattr(fi, "dekodiere_bild", lambda roh: _bild_array(10, 20))
    ergebnis = fi.op_embed(_payload(1))
    assert ergebnis["ok"] is True
    assert len(ergebnis["gesichter"]) == 1


# ── 4. Quelltext: kein alignCrop mehr mit den Landmarken allein ───────────

def test_quelle_uebergibt_die_zeile():
    assert "alignCrop(crop, landm)" not in QUELLE
    assert "alignCrop(img, landm)" not in QUELLE
    assert "alignCrop(img_bgr, landm" not in QUELLE
    assert "alignCrop(img_bgr, reihe)" in QUELLE or "_align_face(img, f)" in QUELLE


def test_quelle_hat_den_waechter():
    assert "Waechter" in QUELLE


def test_quelle_importiert_kein_cv2_oben():
    """Der Import bleibt lazy — das Modul ist ohne cv2 importierbar."""
    import ast
    baum = ast.parse(QUELLE)
    oben = set()
    for knoten in baum.body:
        if isinstance(knoten, ast.Import):
            oben.update(alias.name for alias in knoten.names)
        elif isinstance(knoten, ast.ImportFrom):
            oben.add(knoten.module or "")
    assert "cv2" not in oben
