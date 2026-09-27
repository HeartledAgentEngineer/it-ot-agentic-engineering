"""Pruefungen fuer ``gesicht_erkennen.py`` (Nachtlauf-Schritt N9b).

Alles OHNE Netz, OHNE ``cv2`` und OHNE echte Daten: keine pCloud, kein
Download, kein Bild aus dem Bestand, keine echten Ordner-, Personen- oder
Ortsnamen. Detektor und Rekognizer sind **Attrappen** (im Test definiert), die
genau die Steckdosen nachbilden, die im Betrieb ``cv2`` fuellt. Bytes sind
erfundene Zeichenketten bzw. ein im Speicher gebautes Bild; Dateien gehen nach
``tmp_path``.

Aufruf:
    cd backend && .venv/Scripts/python.exe -m pytest tests/test_gesicht_erkennen.py -q
"""

from __future__ import annotations

import ast
import importlib.util
import io
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "gesicht_erkennen.py"
QUELLE = WERKZEUG.read_text(encoding="utf-8")


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


gs = _laden(WERKZEUG, "gesicht_erkennen")

# Erfundene pCloud-Kennungen (nur Ziffern, keine Pfade/Ordner).
BILD_A = "1234567"
BILD_B = "1234568"
BREITE = 20
HOEHE = 10


# ── Attrappen (nur im Test) ───────────────────────────────────────────────

def _zeile(bbox=(1.0, 2.0, 3.0, 4.0), score=0.9, landm=None):
    """Eine YuNet-Zeile mit 15 Werten bauen: bbox + 5 Landmarken + score."""
    landm = landm if landm is not None else [[1.0, 1.0]] * 5
    return list(bbox) + [wert for punkt in landm for wert in punkt] + [score]


def _merkmal(laenge: int = 128, wert: float = 0.1):
    return [wert] * laenge


def _gesicht(bbox=(1.0, 2.0, 3.0, 4.0), score=0.9):
    """Ein vollstaendiges Gesicht-Dict (fuer den Stapel-Lauf)."""
    return {"bbox": list(bbox), "score": score, "landm": [[1.0, 1.0]] * 5,
            "embedding": _merkmal()}


class AttrappeDetektor:
    """Bildet ``cv2.FaceDetectorYN`` nach — mit optionalem Dekodier-Haken."""

    def __init__(self, gesichter=None, bild=None, dekodiere=None,
                 dekodiere_fehler=False, detect_fehler=False):
        self._gesichter = gesichter
        self._bild = bild
        self._dekodiere = dekodiere
        self._dekodiere_fehler = dekodiere_fehler
        self._detect_fehler = detect_fehler
        self.groesse = None

    def dekodiere_bild(self, roh):
        if self._dekodiere_fehler:
            raise ValueError("kaputt")
        if self._dekodiere is not None:
            return self._dekodiere
        return np.zeros((HOEHE, BREITE, 3), np.uint8)

    def setInputSize(self, groesse):
        self.groesse = groesse

    def detect(self, bild):
        if self._detect_fehler:
            raise RuntimeError("detektorkaputt")
        if self._gesichter is None:
            return (True, None)
        return (True, np.asarray(self._gesichter, dtype=float))


class AttrappeRekognizer:
    """Bildet ``cv2.FaceRecognizerSF`` nach."""

    def __init__(self, merkmal=None, fehler=False):
        self._merkmal = merkmal if merkmal is not None else _merkmal()
        self._fehler = fehler

    def alignCrop(self, bild, landm):
        if self._fehler:
            raise RuntimeError("alignkaputt")
        return "ausschnitt"

    def feature(self, ausschnitt):
        if self._fehler:
            raise RuntimeError("merkmlkaputt")
        return np.asarray(self._merkmal, dtype=np.float32).reshape(1, -1)


class AttrappeModell:
    """Bildet ``GesichtsModell.gesichter`` nach (fuer den Stapel-Lauf)."""

    def __init__(self, gesichter=None, fehler=False):
        self._gesichter = gesichter if gesichter is not None else []
        self._fehler = fehler

    def gesichter(self, roh, bild_id=""):
        if self._fehler:
            raise RuntimeError("modellkaputt")
        return {"bild_id": bild_id, "breite": BREITE, "hoehe": HOEHE,
                "gesichter": self._gesichter}


class AttrappeDienst:
    """Bildet einen Dienst mit ``datei_bytes(fileid, max_bytes)`` nach."""

    def __init__(self, antworten=None):
        self._antworten = antworten or {}
        self.aufrufe = []

    def datei_bytes(self, fileid, max_bytes=0):
        self.aufrufe.append((fileid, max_bytes))
        antwort = self._antworten.get(fileid)
        if callable(antwort):
            return antwort()
        return antwort


def _png_bytes(groesse=(24, 24), farbe=(10, 120, 200)) -> bytes:
    puffer = io.BytesIO()
    Image.new("RGB", groesse, farbe).save(puffer, format="PNG")
    return puffer.getvalue()


def _jpeg_mit_orientierung(orientierung: int, groesse=(BREITE, HOEHE)) -> bytes:
    """Echte JPEG-Bytes mit EXIF-Orientierung (fuer die EXIF-Pruefung)."""
    bild = Image.new("RGB", groesse, (30, 60, 90))
    exif = Image.Exif()
    exif[274] = orientierung
    puffer = io.BytesIO()
    bild.save(puffer, format="JPEG", exif=exif)
    return puffer.getvalue()


def _plan_schreiben(pfad: Path, zuege) -> Path:
    pfad.write_text(json.dumps({"zuege": zuege}), encoding="utf-8")
    return pfad


# ── 1. Modellpfade ────────────────────────────────────────────────────────

def test_modell_pfade_mit_dateien_gibt_beide_zurueck(tmp_path):
    for datei in gs.MODELL_DATEIEN.values():
        (tmp_path / datei).write_bytes(b"x")
    pfade = gs.modell_pfade(str(tmp_path))
    assert set(pfade) == {"detektor", "rekognizer"}
    assert pfade["detektor"].endswith(gs.MODELL_DATEIEN["detektor"])
    assert pfade["rekognizer"].endswith(gs.MODELL_DATEIEN["rekognizer"])


def test_modell_pfade_fehlende_datei_nennt_pfad(tmp_path):
    with pytest.raises(gs.GesichtFehler) as fehler:
        gs.modell_pfade(str(tmp_path))
    assert str(tmp_path) in str(fehler.value)
    assert "fehlen" in str(fehler.value)


def test_modell_pfade_ueber_umgebungsvariable(tmp_path, monkeypatch):
    for datei in gs.MODELL_DATEIEN.values():
        (tmp_path / datei).write_bytes(b"x")
    monkeypatch.setenv(gs.UMGEBUNG_MODELLE, str(tmp_path))
    pfade = gs.modell_pfade()
    assert pfade["detektor"].startswith(str(tmp_path))


def test_modell_pfade_argument_schlaegt_umgebung(tmp_path, monkeypatch):
    a = tmp_path / "a"
    b = tmp_path / "b"
    for ordner in (a, b):
        ordner.mkdir()
        for datei in gs.MODELL_DATEIEN.values():
            (ordner / datei).write_bytes(b"x")
    monkeypatch.setenv(gs.UMGEBUNG_MODELLE, str(a))
    pfade = gs.modell_pfade(str(b))
    assert pfade["detektor"].startswith(str(b))


def test_modell_pfade_standardpfad_ohne_argument(monkeypatch):
    monkeypatch.delenv(gs.UMGEBUNG_MODELLE, raising=False)
    monkeypatch.setattr(gs, "STANDARD_MODELLE", "C:/nirgends/ml_models", raising=False)
    with pytest.raises(gs.GesichtFehler) as fehler:
        gs.modell_pfade()
    assert "C:/nirgends/ml_models" in str(fehler.value)


# ── 2. Verfuegbarkeit ─────────────────────────────────────────────────────

def test_verfuegbar_ist_wahrheitswert(tmp_path, monkeypatch):
    monkeypatch.setenv(gs.UMGEBUNG_MODELLE, str(tmp_path))
    assert isinstance(gs.verfuegbar(), bool)


def test_verfuegbar_falsch_ohne_modelle(tmp_path, monkeypatch):
    monkeypatch.setenv(gs.UMGEBUNG_MODELLE, str(tmp_path))
    assert gs.verfuegbar() is False


def test_verfuegbar_falsch_ohne_cv2(tmp_path, monkeypatch):
    for datei in gs.MODELL_DATEIEN.values():
        (tmp_path / datei).write_bytes(b"x")
    monkeypatch.setenv(gs.UMGEBUNG_MODELLE, str(tmp_path))
    monkeypatch.setattr(gs.importlib.util, "find_spec", lambda name: None)
    assert gs.verfuegbar() is False


def test_modulebene_importiert_kein_cv2():
    """Der Import des Moduls darf ``cv2`` NICHT laden (lazy import-Regel)."""
    baum = ast.parse(QUELLE)
    oben = set()
    for knoten in baum.body:
        if isinstance(knoten, ast.Import):
            oben.update(alias.name for alias in knoten.names)
        elif isinstance(knoten, ast.ImportFrom):
            oben.add(knoten.module or "")
    assert "cv2" not in oben
    assert not any(name.startswith("cv2") for name in oben)


def test_verfuegbar_prueft_ohne_cv2_zu_importieren():
    """Nach einem Import-Zyklus ist ``cv2`` weiterhin nicht in ``sys.modules``."""
    import sys
    # ``verfuegbar`` selbst importiert cv2 nicht: findet nichts -> False/True,
    # aber ohne cv2 zu laden. Nur pruefen, wenn cv2 fehlt.
    if importlib.util.find_spec("cv2") is None:
        gs.verfuegbar()
        assert "cv2" not in sys.modules


# ── 3. GesichtsModell (ohne cv2) ──────────────────────────────────────────

def _dummy_modelle(tmp_path: Path) -> Path:
    ordner = tmp_path / "modelle"
    ordner.mkdir()
    for datei in gs.MODELL_DATEIEN.values():
        (ordner / datei).write_bytes(b"kein echtes ONNX")
    return ordner


def test_gesichtsmodell_baut_mit_dummy_modelldateien(tmp_path):
    modell = gs.GesichtsModell(str(_dummy_modelle(tmp_path)))
    assert set(modell.pfade) == {"detektor", "rekognizer"}


def test_gesichtsmodell_ohne_modelle_wirft(tmp_path):
    with pytest.raises(gs.GesichtFehler):
        gs.GesichtsModell(str(tmp_path))


def test_gesichtsmodell_gesichter_ohne_cv2_gibt_fehler(tmp_path):
    modell = gs.GesichtsModell(str(_dummy_modelle(tmp_path)))
    ergebnis = modell.gesichter(b"erfundene-bytes", bild_id=BILD_A)
    assert ergebnis["bild_id"] == BILD_A
    assert ergebnis["gesichter"] == []
    assert "fehler" in ergebnis


def test_gesichtsmodell_version_verhaelt_sich_richtig(tmp_path):
    modell = gs.GesichtsModell(str(_dummy_modelle(tmp_path)))
    if importlib.util.find_spec("cv2") is None:
        with pytest.raises(gs.GesichtFehler):
            modell.version()
    else:
        assert isinstance(modell.version(), str)


def test_gesichtsmodell_schwellen_uebernommen(tmp_path):
    modell = gs.GesichtsModell(str(_dummy_modelle(tmp_path)),
                               score_schwelle=0.7, nms_schwelle=0.2, topk=100)
    assert modell.score_schwelle == 0.7
    assert modell.nms_schwelle == 0.2
    assert modell.topk == 100


# ── 4. gesichter_mit_detektor (reine Funktion) ────────────────────────────

def test_gesichter_mit_detektor_findet_ein_gesicht():
    detektor = AttrappeDetektor([_zeile()])
    ergebnis = gs.gesichter_mit_detektor(b"egal", detektor, AttrappeRekognizer(),
                                         bild_id=BILD_A)
    assert ergebnis["bild_id"] == BILD_A
    assert ergebnis["breite"] == BREITE and ergebnis["hoehe"] == HOEHE
    assert len(ergebnis["gesichter"]) == 1
    gesicht = ergebnis["gesichter"][0]
    assert gesicht["bbox"] == [1.0, 2.0, 3.0, 4.0]
    assert gesicht["score"] == 0.9
    assert len(gesicht["landm"]) == 5
    assert len(gesicht["embedding"]) == gs.MERKMAL_LAENGE


def test_gesichter_mit_detektor_setzt_input_size():
    detektor = AttrappeDetektor([_zeile()])
    gs.gesichter_mit_detektor(b"egal", detektor, AttrappeRekognizer())
    assert detektor.groesse == (BREITE, HOEHE)


def test_gesichter_mit_detektor_ohne_gesicht_ist_leer():
    detektor = AttrappeDetektor(gesichter=None)
    ergebnis = gs.gesichter_mit_detektor(b"egal", detektor, AttrappeRekognizer())
    assert ergebnis["gesichter"] == []
    assert "fehler" not in ergebnis


def test_gesichter_mit_detektor_leere_liste_ist_leer():
    detektor = AttrappeDetektor(gesichter=[])
    ergebnis = gs.gesichter_mit_detektor(b"egal", detektor, AttrappeRekognizer())
    assert ergebnis["gesichter"] == []


def test_gesichter_mit_detektor_kaputter_detektor_gibt_fehler():
    detektor = AttrappeDetektor(detect_fehler=True)
    ergebnis = gs.gesichter_mit_detektor(b"egal", detektor, AttrappeRekognizer())
    assert ergebnis["gesichter"] == []
    assert "fehler" in ergebnis


def test_gesichter_mit_detektor_nicht_dekodierbar():
    detektor = AttrappeDetektor([_zeile()], dekodiere_fehler=True)
    ergebnis = gs.gesichter_mit_detektor(b"egal", detektor, AttrappeRekognizer())
    assert ergebnis["gesichter"] == []
    assert "fehler" in ergebnis


def test_gesichter_mit_detektor_leere_bytes_gibt_fehler():
    ergebnis = gs.gesichter_mit_detektor(b"", AttrappeDetektor([_zeile()]),
                                         AttrappeRekognizer())
    assert "fehler" in ergebnis


def test_gesichter_mit_detektor_ohne_dekodierhaken_ohne_cv2():
    """Ohne Haken und ohne cv2 -> deutsche Meldung, kein Absturz."""
    class Nackt:
        def setInputSize(self, groesse):
            pass

        def detect(self, bild):
            return (True, None)

    if importlib.util.find_spec("cv2") is None:
        ergebnis = gs.gesichter_mit_detektor(b"\xff\xd8\xff", Nackt(),
                                             AttrappeRekognizer())
        assert "fehler" in ergebnis


def test_gesichter_mit_detektor_gesicht_ohne_merkmal_wird_uebersprungen():
    detektor = AttrappeDetektor([_zeile()])
    ergebnis = gs.gesichter_mit_detektor(b"egal", detektor,
                                         AttrappeRekognizer(fehler=True))
    assert ergebnis["gesichter"] == []
    assert ergebnis["ohne_merkmal"] == 1


def test_gesichter_mit_detektor_falsche_merkmal_laenge_wird_uebersprungen():
    detektor = AttrappeDetektor([_zeile()])
    kurz = AttrappeRekognizer(merkmal=_merkmal(laenge=16))
    ergebnis = gs.gesichter_mit_detektor(b"egal", detektor, kurz)
    assert ergebnis["gesichter"] == []


def test_gesichter_mit_detektor_breite_hoehe_uebergeben():
    detektor = AttrappeDetektor([_zeile()])
    ergebnis = gs.gesichter_mit_detektor(b"egal", detektor, AttrappeRekognizer(),
                                         breite=99, hoehe=88)
    assert ergebnis["breite"] == 99 and ergebnis["hoehe"] == 88


def test_gesichter_mit_detektor_array_eingabe():
    detektor = AttrappeDetektor([_zeile()])
    bild = np.zeros((7, 5, 3), np.uint8)
    ergebnis = gs.gesichter_mit_detektor(bild, detektor, AttrappeRekognizer())
    assert ergebnis["breite"] == 5 and ergebnis["hoehe"] == 7


def test_gesichter_mit_detektor_exif_orientierung_wird_angewandt():
    """EXIF 6 dreht das Bild — die Masse kippen, die Anzeige bleibt gleich."""
    rohdaten = _jpeg_mit_orientierung(6, groesse=(BREITE, HOEHE))
    assert gs._face_infer().exif_orientierung(rohdaten) == 6
    detektor = AttrappeDetektor([_zeile()],
                                bild=np.zeros((HOEHE, BREITE, 3), np.uint8))
    ergebnis = gs.gesichter_mit_detektor(rohdaten, detektor, AttrappeRekognizer())
    # gedreht: aus (h=10, w=20) wird (h=20, w=10)
    assert ergebnis["breite"] == HOEHE and ergebnis["hoehe"] == BREITE


def test_gesichter_mit_detektor_ohne_orientierung_bleibt_gleich():
    rohdaten = _jpeg_mit_orientierung(1, groesse=(BREITE, HOEHE))
    detektor = AttrappeDetektor([_zeile()],
                                bild=np.zeros((HOEHE, BREITE, 3), np.uint8))
    ergebnis = gs.gesichter_mit_detektor(rohdaten, detektor, AttrappeRekognizer())
    assert ergebnis["breite"] == BREITE and ergebnis["hoehe"] == HOEHE


def test_gesichter_mit_detektor_nutzt_face_infer_orientierung():
    """Es wird die vorhandene Funktion wiederverwendet, nicht nachgebaut."""
    assert hasattr(gs._face_infer(), "orientiere_bild")
    assert hasattr(gs._face_infer(), "exif_orientierung")


# ── 5. vektoren_fuer_stapel ───────────────────────────────────────────────

def test_stapel_zaehlt_und_liefert_zeilen():
    bilder = [(BILD_A, b"a"), (BILD_B, b"b")]
    lauf = gs.vektoren_fuer_stapel(bilder, AttrappeModell([_zeile()]))
    zeilen = list(lauf)
    assert [zeile["bild_id"] for zeile in zeilen] == [BILD_A, BILD_B]
    assert lauf.zaehler["bilder_gesamt"] == 2
    assert lauf.zaehler["bilder_geholt"] == 2
    assert lauf.zaehler["bilder_ohne_gesicht"] == 0
    assert lauf.zaehler["loecher"] == 0
    assert lauf.zaehler["fehler"] == 0
    assert isinstance(lauf.zaehler["sekunden"], float)


def test_stapel_zeile_hat_genau_die_lesefelder():
    lauf = gs.vektoren_fuer_stapel([(BILD_A, b"a")], AttrappeModell([_zeile()]))
    zeile = list(lauf)[0]
    assert set(zeile) == {"bild_id", "breite", "hoehe", "gesichter"}


def test_stapel_hole_funktion_erst_beim_verarbeiten():
    gerufen = []

    def hole():
        gerufen.append(1)
        return b"a"

    lauf = gs.vektoren_fuer_stapel([(BILD_A, hole)], AttrappeModell([_zeile()]))
    assert gerufen == []            # vor dem Iterieren noch nicht geholt
    list(lauf)
    assert gerufen == [1]


def test_stapel_fehlende_bytes_sind_loecher():
    def hole():
        return None

    lauf = gs.vektoren_fuer_stapel([(BILD_A, hole)], AttrappeModell([_zeile()]))
    zeilen = list(lauf)
    assert zeilen == []
    assert lauf.zaehler["loecher"] == 1
    assert lauf.zaehler["bilder_geholt"] == 0


def test_stapel_leere_bytes_sind_loecher():
    lauf = gs.vektoren_fuer_stapel([(BILD_A, b"")], AttrappeModell())
    list(lauf)
    assert lauf.zaehler["loecher"] == 1


def test_stapel_hole_funktion_wirft_zaehlt_fehler():
    def hole():
        raise RuntimeError("netzkaputt")

    lauf = gs.vektoren_fuer_stapel([(BILD_A, hole)], AttrappeModell())
    list(lauf)
    assert lauf.zaehler["fehler"] == 1
    assert lauf.zaehler["loecher"] == 0


def test_stapel_max_bilder_deckelt():
    bilder = [(str(1000 + i), b"a") for i in range(5)]
    lauf = gs.vektoren_fuer_stapel(bilder, AttrappeModell([_zeile()]),
                                   max_bilder=2)
    zeilen = list(lauf)
    assert len(zeilen) == 2
    assert lauf.zaehler["bilder_gesamt"] == 2


def test_stapel_abbruch_beendet_lauf():
    zustand = {"weiter": True}

    def abbruch():
        return not zustand["weiter"]

    bilder = [(str(1000 + i), b"a") for i in range(5)]
    lauf = gs.vektoren_fuer_stapel(bilder, AttrappeModell([_zeile()]),
                                   abbruch=abbruch)
    it = iter(lauf)
    erste = next(it)
    assert erste["bild_id"] == "1000"
    zustand["weiter"] = False
    rest = list(it)
    assert rest == []


def test_stapel_ohne_gesicht_zaehlt():
    lauf = gs.vektoren_fuer_stapel([(BILD_A, b"a")], AttrappeModell(gesichter=[]))
    list(lauf)
    assert lauf.zaehler["bilder_ohne_gesicht"] == 1


def test_stapel_modell_fehler_zaehlt():
    lauf = gs.vektoren_fuer_stapel([(BILD_A, b"a")], AttrappeModell(fehler=True))
    zeilen = list(lauf)
    assert lauf.zaehler["fehler"] == 1
    assert zeilen[0]["gesichter"] == []


def test_stapel_bild_id_ist_die_fileid():
    lauf = gs.vektoren_fuer_stapel([(BILD_A, b"a")], AttrappeModell([_zeile()]))
    zeile = list(lauf)[0]
    assert zeile["bild_id"] == BILD_A


def test_stapel_leerer_eingang():
    lauf = gs.vektoren_fuer_stapel([], AttrappeModell())
    assert list(lauf) == []
    assert lauf.zaehler["bilder_gesamt"] == 0


def test_stapel_ungueltiger_eintrag_zaehlt_fehler():
    lauf = gs.vektoren_fuer_stapel(["nurtext"], AttrappeModell())
    list(lauf)
    assert lauf.zaehler["fehler"] == 1


def test_stapel_zeile_pruefen_akzeptiert_die_zeile():
    """Die erzeugte Zeile muss das Eingabeformat von N9a erfuellen."""
    pc = gs._personen_cluster()
    lauf = gs.vektoren_fuer_stapel([(BILD_A, b"a")], AttrappeModell([_gesicht()]))
    zeile = list(lauf)[0]
    geprueft = pc.zeile_pruefen(zeile)
    assert geprueft is not None
    assert geprueft["bild_id"] == BILD_A
    assert geprueft["gesichter"][0]["embedding"] == _merkmal()


# ── 6. vektoren_schreiben ─────────────────────────────────────────────────

def test_vektoren_schreiben_nur_die_vektordatei(tmp_path):
    ziel = tmp_path / "vektoren.jsonl"
    vorher = sorted(p.name for p in tmp_path.iterdir())
    lauf = gs.vektoren_fuer_stapel([(BILD_A, b"a")], AttrappeModell([_zeile()]))
    anzahl = gs.vektoren_schreiben(str(ziel), list(lauf))
    nachher = sorted(p.name for p in tmp_path.iterdir())
    assert anzahl == 1
    assert nachher == sorted(vorher + [ziel.name])
    assert ziel.read_text(encoding="utf-8").count("\n") == 1


def test_vektoren_schreiben_im_repo_wird_abgelehnt():
    ziel = REPO / "tools" / "foto_sortierung" / "verboten.jsonl"
    with pytest.raises(SystemExit) as ausstieg:
        gs.vektoren_schreiben(str(ziel), [])
    assert ausstieg.value.code == 2
    assert not ziel.exists()


# ── 7. kachel_quelle ──────────────────────────────────────────────────────

def test_kachel_quelle_holt_bytes():
    dienst = AttrappeDienst({BILD_A: _png_bytes()})
    holen = gs.kachel_quelle(dienst)
    ergebnis = holen({"fileid": BILD_A})
    assert isinstance(ergebnis, bytes) and ergebnis


def test_kachel_quelle_reicht_fileid_durch():
    dienst = AttrappeDienst({BILD_A: _png_bytes()})
    holen = gs.kachel_quelle(dienst)
    holen({"fileid": BILD_A})
    assert dienst.aufrufe[0][0] == BILD_A


def test_kachel_quelle_reicht_max_bytes_durch():
    dienst = AttrappeDienst({BILD_A: _png_bytes()})
    holen = gs.kachel_quelle(dienst, max_bytes=1234)
    holen({"fileid": BILD_A})
    assert dienst.aufrufe[0][1] == 1234


def test_kachel_quelle_none_bei_fehler():
    def kaputt():
        raise RuntimeError("netzkaputt")

    dienst = AttrappeDienst({BILD_A: kaputt})
    holen = gs.kachel_quelle(dienst)
    assert holen({"fileid": BILD_A}) is None


def test_kachel_quelle_none_bei_leerer_antwort():
    dienst = AttrappeDienst({BILD_A: b""})
    holen = gs.kachel_quelle(dienst)
    assert holen({"fileid": BILD_A}) is None


def test_kachel_quelle_none_ohne_fileid():
    dienst = AttrappeDienst({BILD_A: _png_bytes()})
    holen = gs.kachel_quelle(dienst)
    assert holen({"kein": "fileid"}) is None


def test_kachel_quelle_ohne_dienst_gibt_none():
    holen = gs.kachel_quelle(object())
    assert holen({"fileid": BILD_A}) is None


def test_kachel_quelle_nimmt_direkt_eine_fileid():
    dienst = AttrappeDienst({BILD_A: _png_bytes()})
    holen = gs.kachel_quelle(dienst)
    assert holen(BILD_A) is not None


def test_kachel_quelle_verkleinert_in_memory():
    dienst = AttrappeDienst({BILD_A: _png_bytes(groesse=(60, 40))})
    holen = gs.kachel_quelle(dienst, groesse=(10, 10))
    rohdaten = holen({"fileid": BILD_A})
    with Image.open(io.BytesIO(rohdaten)) as bild:
        assert max(bild.size) <= 10


def test_kachel_quelle_ohne_groesse_bleibt_original():
    rohdaten = _png_bytes(groesse=(60, 40))
    dienst = AttrappeDienst({BILD_A: rohdaten})
    holen = gs.kachel_quelle(dienst)
    assert holen({"fileid": BILD_A}) == rohdaten


def test_kachel_quelle_passt_zu_referenzseiten_bauen(tmp_path):
    """Die echte Quelle speist ``referenzseiten_bauen`` ohne Platzhalter-Zwang."""
    pc = gs._personen_cluster()
    dienst = AttrappeDienst({BILD_A: _png_bytes()})
    gruppen = [{"kennung": "Person_001",
                "eintraege": [{"bild_id": BILD_A, "anteil": 0.5, "score": 0.9}]}]
    geschrieben = pc.referenzseiten_bauen(
        gruppen, kachel_holen=gs.kachel_quelle(dienst),
        ausgabe_ordner=str(tmp_path))
    assert len(geschrieben) == 1
    assert (tmp_path / "Person_001_seite_01.jpg").exists()


# ── 7b. Gesichtsausschnitt (kachel_quelle mit ausschnitt=True) ────────────

def _png_zweifarbig() -> bytes:
    """Ein 200x100-Bild: links blau, rechts ein roter Block (x >= 150)."""
    bild = Image.new("RGB", (200, 100), (0, 0, 255))
    for x in range(150, 200):
        for y in range(100):
            bild.putpixel((x, y), (255, 0, 0))
    puffer = io.BytesIO()
    bild.save(puffer, format="PNG")
    return puffer.getvalue()


def test_ausschnitt_rechnen_setzt_rand_je_seite():
    """``rand`` x bbox-Masse je Seite: Breite links/rechts, Hoehe oben/unten."""
    # bbox 100x50 bei (200, 300): 0,45 x 100 = 45, 0,45 x 50 = 22,5
    assert gs.ausschnitt_rechnen([200.0, 300.0, 100.0, 50.0], 1000, 800) == \
        (155, 277, 345, 373)


def test_ausschnitt_rechnen_ohne_rand_ist_die_box():
    assert gs.ausschnitt_rechnen([200.0, 300.0, 100.0, 50.0], 1000, 800,
                                 rand=0.0) == (200, 300, 300, 350)


def test_ausschnitt_rechnen_klemmt_an_die_bildgrenzen():
    assert gs.ausschnitt_rechnen([-20.0, -10.0, 40.0, 20.0], 100, 100) == \
        (0, 0, 38, 19)
    assert gs.ausschnitt_rechnen([95.0, 95.0, 20.0, 20.0], 100, 100) == \
        (86, 86, 100, 100)


def test_ausschnitt_rechnen_gibt_none_bei_entarteter_box():
    assert gs.ausschnitt_rechnen([500.0, 500.0, 10.0, 10.0], 100, 100) is None
    assert gs.ausschnitt_rechnen([10.0, 10.0, 0.0, 10.0], 100, 100) is None
    assert gs.ausschnitt_rechnen([10.0, 10.0, 10.0, -5.0], 100, 100) is None


def test_ausschnitt_rechnen_gibt_none_bei_unbrauchbarer_eingabe():
    assert gs.ausschnitt_rechnen(None, 100, 100) is None
    assert gs.ausschnitt_rechnen([1.0, 2.0, 3.0], 100, 100) is None
    assert gs.ausschnitt_rechnen(["a", 2.0, 3.0, 4.0], 100, 100) is None
    assert gs.ausschnitt_rechnen([1.0, 2.0, True, 4.0], 100, 100) is None
    assert gs.ausschnitt_rechnen([1.0, 2.0, 3.0, 4.0], 0, 100) is None
    assert gs.ausschnitt_rechnen([1.0, 2.0, 3.0, 4.0], 100, -5) is None


def test_ausschnitt_rechnen_unbrauchbarer_rand_faellt_auf_vorgabe():
    box = [200.0, 300.0, 100.0, 50.0]
    vorgabe = gs.ausschnitt_rechnen(box, 1000, 800)
    assert gs.ausschnitt_rechnen(box, 1000, 800, rand="viel") == vorgabe
    assert gs.ausschnitt_rechnen(box, 1000, 800, rand=-1) == vorgabe


def test_ausschnitt_vorgaben_sind_rand_045_und_quadratisch():
    assert gs.AUSSCHNITT_RAND == 0.45
    assert gs.AUSSCHNITT_GROESSE[0] == gs.AUSSCHNITT_GROESSE[1] == 200


def test_ausschnitt_rechnen_ist_rein():
    """Die Geometrie kommt ohne Bild aus: kein PIL, kein cv2, kein I/O."""
    baum = ast.parse(QUELLE)
    rumpf = None
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.FunctionDef) and \
                knoten.name == "ausschnitt_rechnen":
            rumpf = ast.unparse(knoten)
            break
    assert rumpf is not None, "Vorgabefunktion fehlt: ausschnitt_rechnen"
    for verboten in ("cv2", "Image", "open(", "read", "write"):
        assert verboten not in rumpf, f"ausschnitt_rechnen benutzt {verboten}"


def test_ausschnitt_weg_ohne_cv2():
    """Der Ausschnitt entsteht **nur mit PIL** — cv2 kommt dort nicht vor.

    Geprueft wird der ausfuehrbare Code (AST ohne Docstring): die Docstrings
    nennen ``cv2`` nur, um zu sagen, dass es hier **nicht** benutzt wird.
    """
    baum = ast.parse(QUELLE)
    gesehen = 0
    for knoten in ast.walk(baum):
        if not (isinstance(knoten, ast.FunctionDef) and knoten.name in (
                "ausschnitt_rechnen", "_ausschnitt_bytes")):
            continue
        gesehen += 1
        rumpf = [kind for kind in knoten.body if not (
            isinstance(kind, ast.Expr) and isinstance(kind.value, ast.Constant))]
        text = "\n".join(ast.unparse(kind) for kind in rumpf)
        assert "cv2" not in text, f"{knoten.name} benutzt cv2"
        if knoten.name == "_ausschnitt_bytes":
            assert "PIL" in text, "der Ausschnitt muss ueber PIL laufen"
    assert gesehen == 2, "beide Ausschnitt-Funktionen muessen existieren"


def test_kachel_quelle_ausschnitt_liefert_quadratische_kachel():
    dienst = AttrappeDienst({BILD_A: _png_bytes(groesse=(400, 300))})
    holen = gs.kachel_quelle(dienst, ausschnitt=True)
    rohdaten = holen({"fileid": BILD_A, "bbox": [150.0, 100.0, 40.0, 40.0]})
    with Image.open(io.BytesIO(rohdaten)) as bild:
        assert bild.size == (gs.AUSSCHNITT_GROESSE[0], gs.AUSSCHNITT_GROESSE[1])


def test_kachel_quelle_ausschnitt_nimmt_wirklich_das_gesicht():
    """Inhaltlich: der rote Block liegt im Ausschnitt, das Blau nicht mehr."""
    dienst = AttrappeDienst({BILD_A: _png_zweifarbig()})
    holen = gs.kachel_quelle(dienst, ausschnitt=True, groesse=(20, 20))
    rohdaten = holen({"fileid": BILD_A, "bbox": [170.0, 30.0, 20.0, 20.0]})
    with Image.open(io.BytesIO(rohdaten)) as bild:
        links_oben = np.asarray(bild.convert("RGB"))[0, 0]
    rot, _, blau = (int(wert) for wert in links_oben)
    assert rot > 200 and blau < 60, f"kein Gesichtsausschnitt, sondern {links_oben}"


def test_kachel_quelle_ausschnitt_ohne_bbox_faellt_aufs_ganze_foto():
    rohdaten = _png_bytes(groesse=(60, 40))
    dienst = AttrappeDienst({BILD_A: rohdaten})
    holen = gs.kachel_quelle(dienst, ausschnitt=True)
    assert holen({"fileid": BILD_A}) == rohdaten
    assert holen({"fileid": BILD_A, "bbox": None}) == rohdaten
    assert holen({"fileid": BILD_A, "bbox": [1.0, 2.0, 3.0]}) == rohdaten
    assert holen({"fileid": BILD_A, "bbox": "krumm"}) == rohdaten
    assert holen(BILD_A) == rohdaten          # blanke fileid: kein bbox-Feld


def test_kachel_quelle_ausschnitt_kaputte_bytes_werfen_nichts():
    holen = gs.kachel_quelle(AttrappeDienst({BILD_A: b"kein bild"}),
                             ausschnitt=True)
    assert holen({"fileid": BILD_A, "bbox": [1.0, 2.0, 3.0, 4.0]}) == b"kein bild"


def test_kachel_quelle_ausschnitt_ohne_dienst_gibt_none():
    holen = gs.kachel_quelle(object(), ausschnitt=True)
    assert holen({"fileid": BILD_A, "bbox": [1.0, 2.0, 3.0, 4.0]}) is None


def test_kachel_quelle_ausschnitt_schreibt_nichts_ins_repo():
    ordner = REPO / "tools" / "foto_sortierung"
    vorher = sorted(p.name for p in ordner.iterdir())
    dienst = AttrappeDienst({BILD_A: _png_bytes(groesse=(60, 40))})
    holen = gs.kachel_quelle(dienst, ausschnitt=True)
    holen({"fileid": BILD_A, "bbox": [10.0, 10.0, 20.0, 20.0]})
    assert sorted(p.name for p in ordner.iterdir()) == vorher


def test_kachel_quelle_ausschnitt_passt_zu_referenzseiten_bauen(tmp_path):
    """Der echte Ausschnitt speist ``referenzseiten_bauen`` (keine Platzhalter)."""
    pc = gs._personen_cluster()
    dienst = AttrappeDienst({BILD_A: _png_zweifarbig()})
    gruppen = [{"kennung": "Person_001",
                "eintraege": [{"bild_id": BILD_A, "anteil": 0.5, "score": 0.9,
                               "bbox": [170.0, 30.0, 20.0, 20.0]}]}]
    geschrieben = pc.referenzseiten_bauen(
        gruppen, kachel_holen=gs.kachel_quelle(dienst, ausschnitt=True),
        ausgabe_ordner=str(tmp_path))
    assert len(geschrieben) == 1
    assert (tmp_path / "Person_001_seite_01.jpg").exists()


# ── 7c. N9a-Eintraege: bild_id/bbox in der Kachelquelle (N9d) ────────────

def _png_block_weit_rechts() -> bytes:
    """Ein 400x100-Bild: blau, mit einem roten Block nur rechts (x >= 350)."""
    bild = Image.new("RGB", (400, 100), (0, 0, 255))
    for x in range(350, 400):
        for y in range(100):
            bild.putpixel((x, y), (255, 0, 0))
    puffer = io.BytesIO()
    bild.save(puffer, format="PNG")
    return puffer.getvalue()


N9A_EINTRAG = {"bild_id": BILD_A, "bbox": [10, 10, 50, 50]}


def test_fileid_von_liest_bild_id_als_text_und_zahl():
    assert gs._fileid_von({"bild_id": "1234567"}) == "1234567"
    assert gs._fileid_von({"bild_id": 1234567}) == 1234567


def test_fileid_von_lehnt_bool_und_none_ab():
    assert gs._fileid_von({"bild_id": True}) is None
    assert gs._fileid_von({"bild_id": False}) is None
    assert gs._fileid_von({"bild_id": None}) is None
    assert gs._fileid_von({}) is None
    assert gs._fileid_von({"fileid": None}) is None


def test_fileid_von_fileid_hat_vorrang():
    assert gs._fileid_von({"fileid": "111", "bild_id": "222"}) == "111"
    assert gs._fileid_von({"fileid": 111, "bild_id": 222}) == 111
    # fehlendes/unbrauchbares fileid: dann zaehlt bild_id
    assert gs._fileid_von({"fileid": None, "bild_id": BILD_A}) == BILD_A
    assert gs._fileid_von({"fileid": True, "bild_id": BILD_A}) == BILD_A


def test_kachel_quelle_reicht_bild_id_als_kennung_durch():
    dienst = AttrappeDienst({BILD_A: _png_bytes()})
    holen = gs.kachel_quelle(dienst)
    ergebnis = holen({"bild_id": BILD_A, "bbox": [10, 10, 50, 50]})
    assert isinstance(ergebnis, bytes) and ergebnis
    assert dienst.aufrufe[0][0] == BILD_A


def test_kachel_quelle_ausschnitt_schneidet_n9a_eintrag_wirklich():
    """Der N9a-Eintrag ``{bild_id, bbox}`` liefert eine quadratische Kachel.

    Inhaltlich: der rote Block liegt nur rechts aussen (x >= 350); der
    Ausschnitt um die bbox (10, 10, 50, 50) darf ihn **nicht** enthalten.
    """
    dienst = AttrappeDienst({BILD_A: _png_block_weit_rechts()})
    holen = gs.kachel_quelle(dienst, ausschnitt=True)
    rohdaten = holen(N9A_EINTRAG)
    assert isinstance(rohdaten, bytes) and rohdaten
    with Image.open(io.BytesIO(rohdaten)) as bild:
        assert bild.size == (gs.AUSSCHNITT_GROESSE[0], gs.AUSSCHNITT_GROESSE[1])
        bild = bild.convert("RGB")
        links_oben = np.asarray(bild)[0, 0]
        rechts_oben = np.asarray(bild)[0, bild.width - 1]
    assert dienst.aufrufe[0][0] == BILD_A
    assert int(np.asarray(links_oben)[2]) > 200, "links muss das Blau stehen"
    assert int(np.asarray(rechts_oben)[2]) > 200, \
        "der Ausschnitt endet vor dem roten Block rechts"


def test_kachel_quelle_bild_id_ohne_bbox_ganzes_foto():
    rohdaten = _png_bytes(groesse=(60, 40))
    dienst = AttrappeDienst({BILD_A: rohdaten})
    holen = gs.kachel_quelle(dienst, ausschnitt=True)
    assert holen({"bild_id": BILD_A}) == rohdaten
    assert holen({"bild_id": BILD_A, "bbox": None}) == rohdaten
    assert holen({"bild_id": BILD_A, "bbox": [1.0, 2.0, 3.0]}) == rohdaten


def test_kachelquelle_hinweis_ausschnitt_nennt_vektorzeilen_lauf():
    text = gs.kachelquelle_hinweis(True)
    assert isinstance(text, str) and text
    assert "Vektorzeilen-Lauf" in text
    assert "--ausschnitt" in text
    assert "NICHT" in text
    assert "Referenzseiten-Weg" in text
    assert "bbox" in text


def test_kachelquelle_hinweis_ohne_ausschnitt_ganzes_foto():
    text = gs.kachelquelle_hinweis(False)
    assert isinstance(text, str) and text
    assert "ganzes Foto" in text
    assert "kein Gesichtsausschnitt" in text
    assert "--ausschnitt" not in text
    assert "Vektorzeilen-Lauf" not in text


def test_kachelquelle_hinweis_ist_rein():
    """Die Hinweis-Funktion kommt ohne I/O und Zustand aus."""
    baum = ast.parse(QUELLE)
    rumpf = None
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.FunctionDef) and \
                knoten.name == "kachelquelle_hinweis":
            rumpf = ast.unparse(knoten)
            break
    assert rumpf is not None, "Vorgabefunktion fehlt: kachelquelle_hinweis"
    for verboten in ("cv2", "Image", "open(", "write", "print"):
        assert verboten not in rumpf, f"kachelquelle_hinweis benutzt {verboten}"


# ── 8. massen_uebersicht ──────────────────────────────────────────────────

def _menge_zeile(bild_id=BILD_A, anzahl=6) -> dict:
    """Sechs kleine Gesichter -> Menge ohne bekannte Person (N9a-Regel)."""
    gesichter = [{"bbox": [10.0, 10.0, 100.0, 100.0], "score": 0.9,
                  "embedding": _merkmal()} for _ in range(anzahl)]
    return {"bild_id": bild_id, "breite": 4032, "hoehe": 3024,
            "gesichter": gesichter}


def _gruppe_zeile(bild_id=BILD_A) -> dict:
    gesichter = [{"bbox": [10.0, 10.0, 400.0, 400.0], "score": 0.9,
                  "embedding": _merkmal()}]
    return {"bild_id": bild_id, "breite": 4032, "hoehe": 3024,
            "gesichter": gesichter}


def test_massen_uebersicht_leer():
    uebersicht = gs.massen_uebersicht([])
    assert uebersicht["bilder_gesamt"] == 0
    assert uebersicht["mengen_ohne_bekannte_person"] == 0


def test_massen_uebersicht_menge_ohne_person_nicht_geclustert():
    uebersicht = gs.massen_uebersicht([_menge_zeile()])
    assert uebersicht["mengen"] == 1
    assert uebersicht["mengen_ohne_bekannte_person"] == 1
    assert uebersicht["nicht_geclustert"] == 1
    assert uebersicht["geclustert"] == 0


def test_massen_uebersicht_grosses_gesicht_geclustert():
    uebersicht = gs.massen_uebersicht([_gruppe_zeile()])
    assert uebersicht["geclustert"] == 1
    assert uebersicht["mengen"] == 0


def test_massen_uebersicht_zaehlt_beides():
    uebersicht = gs.massen_uebersicht([_menge_zeile(BILD_A), _gruppe_zeile(BILD_B)])
    assert uebersicht["bilder_gesamt"] == 2
    assert uebersicht["mengen_ohne_bekannte_person"] == 1
    assert uebersicht["geclustert"] == 1


def test_massen_uebersicht_ignoriert_nicht_dict():
    uebersicht = gs.massen_uebersicht(["kein dict", 5, None])
    assert uebersicht["bilder_gesamt"] == 0


def test_massen_uebersicht_je_grund_und_je_art():
    uebersicht = gs.massen_uebersicht([_menge_zeile()])
    assert uebersicht["je_art"].get("menge") == 1
    assert uebersicht["je_grund"].get("menge_ohne_bekannte_person") == 1


# ── 9. Plan lesen und auswaehlen ──────────────────────────────────────────

def test_plan_lesen_liefert_fileid_und_jahr(tmp_path):
    pfad = _plan_schreiben(tmp_path / "plan.json",
                           [{"fileid": 1001, "jahr": 2020},
                            {"fileid": 1002, "jahr": 2021}])
    eintraege = gs.plan_lesen(str(pfad))
    assert eintraege == [{"fileid": "1001", "jahr": 2020},
                         {"fileid": "1002", "jahr": 2021}]


def test_plan_lesen_fehlende_datei_wirft(tmp_path):
    with pytest.raises(gs.GesichtFehler):
        gs.plan_lesen(str(tmp_path / "fehlt.json"))


def test_plan_lesen_ohne_zuege_wirft(tmp_path):
    pfad = tmp_path / "plan.json"
    pfad.write_text(json.dumps({"etwas": 1}), encoding="utf-8")
    with pytest.raises(gs.GesichtFehler):
        gs.plan_lesen(str(pfad))


def test_plan_lesen_ueberspringt_ohne_fileid(tmp_path):
    pfad = _plan_schreiben(tmp_path / "plan.json", [{"jahr": 2020},
                                                    {"fileid": 7, "jahr": 2020}])
    assert gs.plan_lesen(str(pfad)) == [{"fileid": "7", "jahr": 2020}]


def test_plan_auswaehlen_jahr_filtert():
    eintraege = [{"fileid": "1", "jahr": 2020}, {"fileid": "2", "jahr": 2021}]
    assert gs.plan_auswaehlen(eintraege, jahr=2021) == [{"fileid": "2",
                                                         "jahr": 2021}]


def test_plan_auswaehlen_je_jahr_deckelt():
    eintraege = [{"fileid": str(i), "jahr": 2020} for i in range(5)]
    gewaehlt = gs.plan_auswaehlen(eintraege, je_jahr=2)
    assert [e["fileid"] for e in gewaehlt] == ["0", "1"]


def test_plan_auswaehlen_max_bilder_deckelt():
    eintraege = [{"fileid": str(i), "jahr": 2020} for i in range(5)]
    assert len(gs.plan_auswaehlen(eintraege, max_bilder=3)) == 3


# ── 10. main (Kommandozeile) ──────────────────────────────────────────────

def test_main_trockenlauf_zaehlt_nur(tmp_path, capsys):
    plan = _plan_schreiben(tmp_path / "plan.json",
                           [{"fileid": 1001, "jahr": 2020},
                            {"fileid": 1002, "jahr": 2021}])
    ziel = tmp_path / "vektoren.jsonl"
    code = gs.main(["--plan", str(plan), "--vektoren", str(ziel)])
    assert code == 0
    ausgabe = capsys.readouterr().out
    assert "Trockenlauf" in ausgabe
    assert "Auswahl: 2 Bild(er)" in ausgabe
    assert not ziel.exists()          # Trockenlauf schreibt nichts


def test_main_trockenlauf_jahr_und_max(tmp_path, capsys):
    plan = _plan_schreiben(tmp_path / "plan.json",
                           [{"fileid": 1001, "jahr": 2020},
                            {"fileid": 1002, "jahr": 2020},
                            {"fileid": 1003, "jahr": 2021}])
    ziel = tmp_path / "vektoren.jsonl"
    code = gs.main(["--plan", str(plan), "--vektoren", str(ziel),
                    "--jahr", "2020", "--max-bilder", "1"])
    assert code == 0
    assert "Auswahl: 1 Bild(er)" in capsys.readouterr().out


def test_main_fehlender_plan_gibt_zwei(tmp_path, capsys):
    ziel = tmp_path / "vektoren.jsonl"
    code = gs.main(["--plan", str(tmp_path / "fehlt.json"),
                    "--vektoren", str(ziel)])
    assert code == 2
    assert "Fehler" in capsys.readouterr().out
    assert not ziel.exists()


def test_main_vektoren_im_repo_exit_zwei(tmp_path):
    plan = _plan_schreiben(tmp_path / "plan.json", [{"fileid": 1, "jahr": 2020}])
    ziel = REPO / "tools" / "foto_sortierung" / "verboten.jsonl"
    with pytest.raises(SystemExit) as ausstieg:
        gs.main(["--plan", str(plan), "--vektoren", str(ziel), "--schreiben"])
    assert ausstieg.value.code == 2
    assert not ziel.exists()


def test_main_trocken_hat_vorrang(tmp_path):
    plan = _plan_schreiben(tmp_path / "plan.json", [{"fileid": 1, "jahr": 2020}])
    ziel = tmp_path / "vektoren.jsonl"
    code = gs.main(["--plan", str(plan), "--vektoren", str(ziel),
                    "--schreiben", "--trocken"])
    assert code == 0
    assert not ziel.exists()


def test_main_ausschnitt_schalter_im_trockenlauf(tmp_path):
    """``--ausschnitt`` ist ein Schalter; der Trockenlauf bleibt unveraendert."""
    plan = _plan_schreiben(tmp_path / "plan.json", [{"fileid": 1, "jahr": 2020}])
    ziel = tmp_path / "vektoren.jsonl"
    code = gs.main(["--plan", str(plan), "--vektoren", str(ziel),
                    "--ausschnitt"])
    assert code == 0
    assert not ziel.exists()
    assert "--ausschnitt" in QUELLE


def test_quelle_nennt_die_kachelquelle_in_klartext():
    """Die Ausgabe nennt den Modus — und behauptet nichts Falsches mehr.

    Geprueft wird der Quelltext: der Schreibzweig braucht pCloud und Modelle
    und ist offline nicht fahrbar — die Klartextzeile ist aber Teil des
    Auftrags (``main`` nennt den Modus ueber ``kachelquelle_hinweis``).
    """
    assert "kachelquelle_hinweis(args.ausschnitt)" in QUELLE
    assert "ganzes Foto je Bild" in QUELLE
    # Keine Behauptung mehr, dass im Vektorzeilen-Lauf je Gesicht geschnitten
    # wuerde: vor dem Download ist dort keine bbox bekannt.
    assert "Gesichtsausschnitt je Gesicht" not in QUELLE


# ── 11. Harte Regeln: Abwesenheit im Quelltext ────────────────────────────

def test_quelle_loescht_nichts():
    for marker in ("os.remove", "os.unlink", "unlink(", "deletefile",
                   "deletefolder", "shutil.rmtree", "rmtree", "truncate"):
        assert marker not in QUELLE, f"Loeschaufruf gefunden: {marker}"


def test_quelle_schreibt_keine_bilder():
    for marker in ('"wb"', "'wb'", "tofile", "imwrite", "imencode",
                   "NamedTemporaryFile", "mkstemp"):
        assert marker not in QUELLE, f"Bildschreibweg gefunden: {marker}"


def test_quelle_keine_geheimnisse():
    # Der Marker wird zusammengesetzt, damit dieses Wort nicht selbst in einer
    # Datei steht, die geprueft wird.
    marker = "to" + "ken"
    assert marker not in QUELLE.lower()
    assert "PCLOUD_" + marker.upper() not in QUELLE


def test_quelle_oeffnet_nur_text_zum_schreiben():
    baum = ast.parse(QUELLE)
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Call) and getattr(knoten.func, "id", "") == "open":
            modus = None
            if len(knoten.args) >= 2 and isinstance(knoten.args[1], ast.Constant):
                modus = knoten.args[1].value
            for wort in knoten.keywords:
                if wort.arg == "mode" and isinstance(wort.value, ast.Constant):
                    modus = wort.value.value
            if modus is not None:
                assert "b" not in modus


def test_oeffentliche_schnittstelle_vorhanden():
    for name in ("GesichtFehler", "modell_pfade", "verfuegbar", "GesichtsModell",
                 "gesichter_mit_detektor", "vektoren_fuer_stapel",
                 "kachel_quelle", "ausschnitt_rechnen", "AUSSCHNITT_RAND",
                 "AUSSCHNITT_GROESSE", "massen_uebersicht", "main"):
        assert hasattr(gs, name), f"fehlt: {name}"
