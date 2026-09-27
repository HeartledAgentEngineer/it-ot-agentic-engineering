"""Gesichtserkennung am PC (Nachtlauf-Schritt N9b, 27.09.2026).

Wozu dieses Werkzeug:
  N9a (``personen_cluster.py``) rechnet nur auf **Vektoren**. Dieses Werkzeug
  ist die **Bruecke** von echten Bild-Bytes zu genau dem Vektorformat, das N9a
  liest: je Bild eine Zeile ``{"bild_id", "breite", "hoehe", "gesichter": […]}``
  mit ``bbox`` (x, y, w, h), ``score`` und einem 128-Wert-``embedding``.

  Erkannt wird mit **YuNet** (Detektion) und **SFace** (Merkmal), beide als
  ONNX-Modelle. Das noetige ``cv2``/``onnxruntime`` liegt bewusst in einem
  **eigenen** venv und fehlt im Projekt-venv; dieses Modul laedt ``cv2`` daher
  **erst in den Funktionen** (lazy) und bleibt ohne OpenCV importierbar. Die
  Tests laufen mit einem **eingesteckten** Attrappen-Detektor vollstaendig ohne
  ``cv2``.

Was dieses Werkzeug bewusst NICHT tut:
  * **Kein Speichern von Bildern.** Bilder werden ausschliesslich **in-memory**
    verarbeitet. Geschrieben wird nur die **Vektorzeilen-Datei** (JSONL, Text).
    Kein Schreiben von Bilddaten auf die Platte, kein Zwischenbild, kein
    Binaer-Schreibmodus.
  * **Kein Loeschen.** Im ganzen Modul gibt es keinen Loeschaufruf.
  * **Kein Schreiben ins Repo.** Die Vektorzeilen gehen nur in einen Pfad
    **ausserhalb** des Repos; ein Repo-Pfad ergibt eine deutsche
    Klartextmeldung und ``SystemExit(2)``, geschrieben wird dann nichts.
  * **Keine Geheimnisse.** Dieses Modul liest, speichert und druckt keine
    Zugangsdaten. Die pCloud-Quelle wird **eingesteckt** (Duck-Typing): die
    Kachelquelle braucht nur ein Objekt mit ``datei_bytes(fileid, max_bytes)``.
  * **Keine Namen, keine Pfade in der Ausgabe.** ``bild_id`` ist die
    pCloud-``fileid`` als Zeichenkette; Ordner-, Personen-, Orts- und
    Ereignisnamen kommen nicht vor.

Orientierung (EXIF):
  Damit die ``bbox`` im selben Koordinatenraum liegt wie das spaeter
  angezeigte Bild, wird das Bild **identisch zur Anzeige** gedreht. Dafuer
  werden ``backend/face_infer.py`` -> ``exif_orientierung``/``orientiere_bild``
  **wiederverwendet** (numpy-only, ohne ``cv2`` importierbar) — nicht neu
  gebaut.

Aufruf (Kommandozeile) — **Standard ist der Trockenlauf** (kein Download)::

    # Trockenlauf: nur zaehlen/auflisten, was geholt WUERDE
    .venv/Scripts/python.exe tools/foto_sortierung/gesicht_erkennen.py \
        --plan ~/foto_sortierung/sortierplan.json --jahr 2020 --max-bilder 24

    # wirklich rechnen und die Vektorzeilen schreiben
    .venv/Scripts/python.exe tools/foto_sortierung/gesicht_erkennen.py \
        --plan ~/foto_sortierung/sortierplan.json \
        --vektoren ~/foto_sortierung/personen_vektoren.jsonl --schreiben

Als Modul (Tests, Skripte): ``main(argv=[...])``.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import math
import os
import sys
import time

import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent
BACKEND = os.path.join(REPO, "backend")

# Vorgabepfade: ausserhalb des Repos — dort liegen Modelle und Vektoren.
STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_MODELLE = os.path.join(STANDARD_BASIS, "ml_models")
STANDARD_PLAN = os.path.join(STANDARD_BASIS, "sortierplan.json")
STANDARD_VEKTOREN = os.path.join(STANDARD_BASIS, "personen_vektoren.jsonl")

# Der Ordner der Modelle laesst sich auch ueber eine Umgebungsvariable setzen
# (nur fuer den Modellpfad — hier steht kein Geheimnis).
UMGEBUNG_MODELLE = "GESICHT_MODELLE_DIR"

# Die zwei Modell-Dateien des OpenCV-Zoo (Namen sind oeffentlich).
MODELL_DATEIEN = {
    "detektor": "face_detection_yunet_2023mar.onnx",
    "rekognizer": "face_recognition_sface_2021dec.onnx",
}

# Laenge des SFace-Merkmals (128 Werte) — dieselbe Laenge wie in N9a.
MERKMAL_LAENGE = 128

# Obergrenze fuer einen Kachel-Download (in-memory), damit kein Speicher
# voll laeuft; ``PCloudService.datei_bytes`` bekommt sie durchgereicht.
KACHEL_MAX_BYTES = 8 * 1024 * 1024

# Score-/NMS-Schwellen der Detektion — derselbe Score-Wert wie in face_infer.py.
SCORE_SCHWELLE = 0.6
NMS_SCHWELLE = 0.3
TOPK = 5000


class GesichtFehler(Exception):
    """Fehler dieses Werkzeugs — deutsche Klartextmeldung, kein Absturz."""


# ── Kleine Helfer (tolerant lesen, nie raten) ─────────────────────────────

def _text(wert) -> str:
    """Ein Feld als Text lesen — Nicht-Text und ``None`` werden zu ``""``."""
    return wert.strip() if isinstance(wert, str) else ""


def _ist_zahl(wert) -> bool:
    """Eine endliche Zahl (kein ``bool``) — sonst ``False``."""
    if isinstance(wert, bool):
        return False
    if not isinstance(wert, (int, float)):
        return False
    return math.isfinite(float(wert))


def _ist_positiv(wert) -> bool:
    """Eine Zahl ``> 0`` (kein ``bool``) — sonst ``False``."""
    return _ist_zahl(wert) and float(wert) > 0


def _modul_aus_datei(pfad: str, name: str):
    """Ein Modul aus einer Datei laden (kein Paket-Zwang, einmalig je Name)."""
    spez = importlib.util.spec_from_file_location(name, pfad)
    if spez is None or spez.loader is None:
        raise GesichtFehler(f"Modul nicht gefunden: {pfad}")
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


_CACHE: dict = {}


def _face_infer():
    """``backend/face_infer.py`` laden (numpy-only Teil, ohne cv2)."""
    if "face_infer" not in _CACHE:
        _CACHE["face_infer"] = _modul_aus_datei(
            os.path.join(BACKEND, "face_infer.py"), "gesicht_face_infer")
    return _CACHE["face_infer"]


def _personen_cluster():
    """``personen_cluster.py`` (N9a) laden — fuer die Mengen-Regel am Bild."""
    if "personen_cluster" not in _CACHE:
        _CACHE["personen_cluster"] = _modul_aus_datei(
            os.path.join(HIER, "personen_cluster.py"),
            "gesicht_personen_cluster")
    return _CACHE["personen_cluster"]


# ── 1. Modellpfade und Verfuegbarkeit ─────────────────────────────────────

def modell_pfade(modelle_dir=None) -> dict:
    """Die zwei Modelldateien aufloesen -> ``{"detektor": …, "rekognizer": …}``.

    Reihenfolge der Quellen: Argument ``modelle_dir``, sonst die
    Umgebungsvariable ``GESICHT_MODELLE_DIR``, sonst der Standard
    ``~/foto_sortierung/ml_models``. Fehlt eine der beiden Dateien, gibt es
    eine ``GesichtFehler``-Meldung **mit dem Pfad im Text** — es wird nicht
    geraten und nichts ersetzt.
    """
    basis = modelle_dir or os.environ.get(UMGEBUNG_MODELLE) or STANDARD_MODELLE
    basis = os.path.expanduser(str(basis))
    pfade: dict = {}
    fehlend: list = []
    for name, datei in MODELL_DATEIEN.items():
        pfad = os.path.join(basis, datei)
        pfade[name] = pfad
        if not os.path.isfile(pfad):
            fehlend.append(pfad)
    if fehlend:
        raise GesichtFehler(
            "Modelldatei(en) fehlen: " + ", ".join(fehlend)
            + f" (Modellordner: {basis})")
    return pfade


def verfuegbar() -> bool:
    """Sagen, ob ``cv2`` vorhanden und die Modelle da sind — ohne ``cv2`` zu laden.

    ``cv2`` wird nur **nachgesehen** (``importlib.util.find_spec``), nicht
    importiert. Damit ist die Abfrage billig und das Modul bleibt auch ohne
    OpenCV importierbar.
    """
    try:
        if importlib.util.find_spec("cv2") is None:
            return False
    except (ImportError, ValueError):
        return False
    try:
        modell_pfade()
    except GesichtFehler:
        return False
    return True


# ── 2. Bild -> Gesichter (reine Funktion, Detektor/Rekognizer eingesteckt) ─

def _bild_bereitstellen(roh, detektor):
    """Bild-Bytes -> BGR-Array (EXIF-orientiert) oder ``(None, Meldung)``.

    Ein bereits dekodiertes Array wird durchgereicht. Fuer Bytes gilt: hat der
    eingesteckte ``detektor`` eine Methode ``dekodiere_bild``, wird sie benutzt
    (so bleiben die Tests ohne ``cv2``); sonst dekodiert ``cv2.imdecode``
    (lazy importiert). Die EXIF-Orientierung kommt in **jedem** Fall aus
    ``backend/face_infer.orientiere_bild`` — dieselbe Drehung wie die Anzeige.
    """
    if isinstance(roh, np.ndarray):
        if roh.ndim < 2 or roh.size == 0:
            return None, "Kein Bildarray uebergeben."
        return roh, ""
    if not isinstance(roh, (bytes, bytearray)) or not roh:
        return None, "Keine Bilddaten uebergeben."
    rohdaten = bytes(roh)

    bild = None
    dekodierer = getattr(detektor, "dekodiere_bild", None)
    if callable(dekodierer):
        try:
            bild = dekodierer(rohdaten)
        except Exception as problem:
            return None, f"Bild nicht dekodierbar ({problem.__class__.__name__})."
    else:
        try:
            import cv2
        except Exception:
            return None, "Bild nicht dekodierbar (cv2 nicht verfuegbar)."
        try:
            puffer = np.frombuffer(rohdaten, np.uint8)
            bild = cv2.imdecode(puffer, cv2.IMREAD_COLOR)
        except Exception as problem:
            return None, f"Bild nicht dekodierbar ({problem.__class__.__name__})."
    if bild is None or not isinstance(bild, np.ndarray) or bild.ndim < 2:
        return None, "Bild nicht dekodierbar."
    try:
        bild = _face_infer().orientiere_bild(bild, rohdaten)
    except Exception:
        pass
    return bild, ""


def _merkmal(rekognizer, bild, landm):
    """128-Wert-Merkmal eines Gesichts — ``None``, wenn es nicht entsteht."""
    try:
        ausschnitt = rekognizer.alignCrop(bild, landm)
        merkmal = rekognizer.feature(ausschnitt)
    except Exception:
        return None
    werte = np.asarray(merkmal, dtype=float).reshape(-1)
    if werte.size != MERKMAL_LAENGE:
        return None
    liste = [float(v) for v in werte]
    if not all(math.isfinite(v) for v in liste):
        return None
    return liste


def gesichter_mit_detektor(roh, detektor, rekognizer, bild_id="",
                           breite=None, hoehe=None) -> dict:
    """Gesichter eines Bildes finden — Detektor/Rekognizer **eingesteckt**.

    Reine Funktion ohne eigenen Zustand: ``detektor`` braucht nur
    ``setInputSize``/``detect``, ``rekognizer`` nur ``alignCrop``/``feature``.
    So ist die Funktion vollstaendig offline (ohne ``cv2``) pruefbar.

    Rueckgabe (immer dieselben Felder)::

        {"bild_id": str, "breite": int, "hoehe": int,
         "gesichter": [{"bbox": [x, y, w, h], "score": float,
                        "landm": [[x, y] * 5], "embedding": [128 floats]}]}

    Kein Gesicht, kein dekodierbares Bild oder ein Fehler bei der Detektion
    ergeben **keine** Ausnahme, sondern eine leere Liste plus das Feld
    ``"fehler"`` mit deutschem Text. Ein Gesicht, zu dem kein gueltiges
    Merkmal entsteht, wird **uebersprungen** und unter ``"ohne_merkmal"``
    gezaehlt — so bleibt jede Zeile fuer N9a gueltig.
    """
    kennung = _text(bild_id)
    ergebnis = {"bild_id": kennung, "breite": 0, "hoehe": 0, "gesichter": []}

    bild, fehler = _bild_bereitstellen(roh, detektor)
    if bild is None:
        ergebnis["fehler"] = fehler
        return ergebnis

    hoehe_bild, breite_bild = int(bild.shape[0]), int(bild.shape[1])
    if _ist_positiv(breite) and _ist_positiv(hoehe):
        ergebnis["breite"], ergebnis["hoehe"] = int(breite), int(hoehe)
    else:
        ergebnis["breite"], ergebnis["hoehe"] = breite_bild, hoehe_bild

    try:
        detektor.setInputSize((breite_bild, hoehe_bild))
        _, rohgesichter = detektor.detect(bild)
    except Exception as problem:
        ergebnis["fehler"] = (
            f"Gesichtserkennung fehlgeschlagen ({problem.__class__.__name__}): "
            f"{problem}")
        return ergebnis

    if rohgesichter is None or len(rohgesichter) == 0:
        return ergebnis

    ohne_merkmal = 0
    for gesicht in rohgesichter:
        werte = np.asarray(gesicht, dtype=float).reshape(-1)
        if werte.size < 5:
            ohne_merkmal += 1
            continue
        bbox = [float(v) for v in werte[0:4]]
        score = float(werte[-1])
        landm = werte[4:14].reshape(5, 2)
        merkmal = _merkmal(rekognizer, bild, landm.astype(np.float32))
        if merkmal is None:
            ohne_merkmal += 1
            continue
        ergebnis["gesichter"].append({
            "bbox": bbox,
            "score": score,
            "landm": [[float(x), float(y)] for x, y in landm],
            "embedding": merkmal,
        })
    if ohne_merkmal:
        ergebnis["ohne_merkmal"] = ohne_merkmal
    return ergebnis


# ── 3. Das Modell (laedt cv2/ONNX erst bei Bedarf) ────────────────────────

class GesichtsModell:
    """YuNet + SFace aus den Modelldateien — ``cv2`` wird erst beim Rechnen geladen.

    ``gesichter`` ruft die reine Funktion ``gesichter_mit_detektor`` auf, damit
    Detektion/Merkmal an genau einer Stelle stehen. Fehlt ``cv2`` oder ist das
    Modell nicht ladbar, kommt **kein** Absturz, sondern ein Ergebnisfeld
    ``"fehler"`` (leere Gesichtsliste).
    """

    def __init__(self, modelle_dir=None, score_schwelle=SCORE_SCHWELLE,
                 nms_schwelle=NMS_SCHWELLE, topk=TOPK):
        # Pfade schon hier aufloesen: fehlt eine Modelldatei, ist das ein
        # Konfigurationsfehler und soll sofort auffallen (kein cv2 noetig).
        self.pfade = modell_pfade(modelle_dir)
        self.score_schwelle = float(score_schwelle) if _ist_zahl(score_schwelle) \
            else SCORE_SCHWELLE
        self.nms_schwelle = float(nms_schwelle) if _ist_zahl(nms_schwelle) \
            else NMS_SCHWELLE
        self.topk = int(topk) if _ist_zahl(topk) else TOPK
        self._detektor = None
        self._rekognizer = None

    def _laden(self):
        """Detektor/Rekognizer einmalig bauen (erst hier wird ``cv2`` geladen)."""
        if self._detektor is None or self._rekognizer is None:
            import cv2
            self._detektor = cv2.FaceDetectorYN.create(
                self.pfade["detektor"], "", (320, 320),
                self.score_schwelle, self.nms_schwelle, self.topk)
            self._rekognizer = cv2.FaceRecognizerSF.create(
                self.pfade["rekognizer"], "")
        return self._detektor, self._rekognizer

    def gesichter(self, roh: bytes, bild_id: str = "") -> dict:
        """Ein Bild verarbeiten — siehe ``gesichter_mit_detektor`` fuer die Felder."""
        try:
            detektor, rekognizer = self._laden()
        except Exception as problem:
            return {"bild_id": _text(bild_id), "breite": 0, "hoehe": 0,
                    "gesichter": [],
                    "fehler": "Gesichtsmodell nicht ladbar "
                              f"({problem.__class__.__name__}): {problem}"}
        return gesichter_mit_detektor(roh, detektor, rekognizer,
                                      bild_id=bild_id)

    def version(self) -> str:
        """Die Version der geladenen Bildbibliothek (keine Modellwerte)."""
        try:
            import cv2
        except Exception as problem:
            raise GesichtFehler("Bildbibliothek nicht verfuegbar "
                                f"({problem.__class__.__name__}).") from None
        return str(cv2.__version__)


# ── 4. Stapel: je Bild genau eine Vektorzeile ─────────────────────────────

class StapelLauf:
    """Iterator ueber einen Bild-Stapel, mit Zaehlern.

    Iterieren liefert **je Bild mit Bytes genau eine Zeile** in der Form, die
    ``personen_cluster`` liest. Bilder ohne Bytes werden nur **gezaehlt**
    (``loecher``), nicht geraten — dort entsteht keine Zeile. Nach dem Lauf
    stehen die Zahlen unter ``lauf.zaehler``:

      * ``bilder_gesamt`` — Anzahl betrachteter Eintraege (nach ``max_bilder``)
      * ``bilder_geholt`` — Eintraege, fuer die Bytes vorlagen
      * ``bilder_ohne_gesicht`` — geholte Bilder ohne erkanntes Gesicht
      * ``loecher`` — Eintraege ohne Bytes (fehlende Bytes, gezahlt)
      * ``fehler`` — Verarbeitung Fehlgeschlagenes (Holen/Erkennen)
      * ``sekunden`` — Laufzeit bis zum Ende
    """

    def __init__(self, bilder, modell, max_bilder=None, abbruch=None):
        eintraege = list(bilder) if bilder is not None else []
        if _ist_zahl(max_bilder) and int(max_bilder) >= 0:
            eintraege = eintraege[:int(max_bilder)]
        self._eintraege = eintraege
        self._modell = modell
        self._abbruch = abbruch if callable(abbruch) else None
        self._index = 0
        self._start = time.monotonic()
        self.zaehler = {
            "bilder_gesamt": len(eintraege),
            "bilder_geholt": 0,
            "bilder_ohne_gesicht": 0,
            "fehler": 0,
            "loecher": 0,
            "sekunden": 0.0,
        }

    def __iter__(self):
        return self

    def _bytes_holen(self, zweiter):
        """Bytes eines Eintrags besorgen — eine Funktion wird jetzt erst gerufen."""
        if callable(zweiter):
            return zweiter()
        return zweiter

    def __next__(self):
        while self._index < len(self._eintraege):
            if self._abbruch is not None and self._abbruch():
                self.zaehler["sekunden"] = round(time.monotonic() - self._start, 3)
                raise StopIteration
            eintrag = self._eintraege[self._index]
            self._index += 1

            kennung = ""
            zweiter = None
            if isinstance(eintrag, (tuple, list)) and len(eintrag) >= 2:
                kennung, zweiter = eintrag[0], eintrag[1]
            else:
                self.zaehler["fehler"] += 1
                continue
            kennung = str(kennung).strip() if isinstance(kennung, (str, int)) \
                and not isinstance(kennung, bool) else ""
            if not kennung:
                self.zaehler["fehler"] += 1
                continue

            try:
                rohdaten = self._bytes_holen(zweiter)
            except Exception:
                self.zaehler["fehler"] += 1
                continue
            if not isinstance(rohdaten, (bytes, bytearray)) or not rohdaten:
                self.zaehler["loecher"] += 1
                continue
            self.zaehler["bilder_geholt"] += 1

            try:
                zeile = self._modell.gesichter(bytes(rohdaten), bild_id=kennung)
                if not isinstance(zeile, dict):
                    raise TypeError("Modell lieferte kein Ergebnis-Dict.")
            except Exception:
                self.zaehler["fehler"] += 1
                zeile = {"bild_id": kennung, "breite": 0, "hoehe": 0,
                         "gesichter": []}
            if zeile.get("fehler"):
                self.zaehler["fehler"] += 1
            if not zeile.get("gesichter"):
                self.zaehler["bilder_ohne_gesicht"] += 1
            return {
                "bild_id": _text(zeile.get("bild_id")) or kennung,
                "breite": zeile.get("breite", 0),
                "hoehe": zeile.get("hoehe", 0),
                "gesichter": zeile.get("gesichter") or [],
            }
        self.zaehler["sekunden"] = round(time.monotonic() - self._start, 3)
        raise StopIteration


def vektoren_fuer_stapel(bilder, modell, max_bilder=None, abbruch=None):
    """Iterator ueber ``bilder`` -> je Bild eine Vektorzeile fuer N9a.

    ``bilder`` ist eine Folge ``(bild_id, hole_funktion)`` oder
    ``(bild_id, bytes)``; ``hole_funktion()`` wird **erst beim Verarbeiten**
    des jeweiligen Bildes gerufen (billigster Weg zuerst — es wird nichts
    geholt, was nicht an die Reihe kommt). ``abbruch()`` (falls gesetzt) wird
    vor jedem Bild gefragt und beendet den Lauf, sobald es ``True`` liefert.
    Die Zaehler stehen am zurueckgegebenen Objekt unter ``.zaehler``.
    """
    return StapelLauf(bilder, modell, max_bilder=max_bilder, abbruch=abbruch)


def vektoren_schreiben(pfad: str, zeilen) -> int:
    """Vektorzeilen als **Text** (JSONL) schreiben — nur **ausserhalb** des Repos.

    Schreibt ausschliesslich die Zeilen selbst (Text, UTF-8); es entstehen
    **keine** Bilddateien. Ein Pfad im Repo ergibt eine deutsche Meldung und
    ``SystemExit(2)`` (ueber ``personen_cluster.pruefe_ausserhalb_repo``).
    Rueckgabe ist die Anzahl geschriebener Zeilen.
    """
    _personen_cluster().pruefe_ausserhalb_repo(pfad)
    ordner = os.path.dirname(os.path.abspath(pfad))
    if ordner:
        os.makedirs(ordner, exist_ok=True)
    anzahl = 0
    with open(pfad, "w", encoding="utf-8") as datei:
        for zeile in zeilen:
            datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")
            anzahl += 1
    return anzahl


# ── 5. Die echte pCloud-Kachelquelle (eingesteckt, kein Geheimnis hier) ────

def _fileid_von(eintrag):
    """Die ``fileid`` eines Kachel-Eintrags lesen — ``None``, wenn keine da ist."""
    if isinstance(eintrag, dict):
        wert = eintrag.get("fileid")
    elif isinstance(eintrag, (str, int)) and not isinstance(eintrag, bool):
        wert = eintrag
    else:
        wert = None
    if isinstance(wert, bool) or wert is None:
        return None
    return wert


def _groesse_lesen(groesse):
    """``(breite, hoehe)`` aus einem Groessen-Wunsch lesen — sonst ``None``."""
    if isinstance(groesse, (tuple, list)) and len(groesse) == 2 \
            and _ist_positiv(groesse[0]) and _ist_positiv(groesse[1]):
        return int(groesse[0]), int(groesse[1])
    return None


def _verkleinern(rohdaten, groesse):
    """Bild-Bytes in-memory verkleinern (nur fuer die Kachel) — sonst Original.

    ``groesse`` ist die groesste Kantenlaenge (``thumbnail``). Ausgegeben wird
    ein JPEG in-memory; schlaegt das fehl, kommen die Originalbytes zurueck.
    Es wird **nichts** auf die Platte geschrieben.
    """
    try:
        from PIL import Image
        with Image.open(io.BytesIO(rohdaten)) as quelle:
            klein = quelle.convert("RGB").copy()
        klein.thumbnail((groesse[0], groesse[1]))
        puffer = io.BytesIO()
        klein.save(puffer, format="JPEG", quality=85)
        return puffer.getvalue()
    except Exception:
        return rohdaten


def kachel_quelle(service, max_bytes=KACHEL_MAX_BYTES, groesse=None):
    """Eine ``kachel_holen(eintrag) -> bytes | None`` aus einem Dienst bauen.

    ``service`` wird **eingesteckt** (Duck-Typing): es genuegt ein Objekt mit
    ``datei_bytes(fileid, max_bytes)`` — z. B. ``PCloudService``. Dieses Modul
    kennt weder Zugangsdaten noch Konfiguration; hinein kommt nur die fertige
    Abruffunktion.

    Die zurueckgegebene Funktion holt fuer einen Eintrag mit ``fileid`` die
    Bytes **in-memory**. Fehler, leere oder fehlende Antworten ergeben ``None``
    (der Platzhalter von ``referenzseiten_bauen`` greift) — **nie** ein Abbruch.
    Ist ``groesse`` ``(breite, hoehe)`` gesetzt, wird die Kachel in-memory auf
    diese Kantenlaenge verkleinert.
    """
    holen = getattr(service, "datei_bytes", None)
    ziel = _groesse_lesen(groesse)

    def kachel_holen(eintrag):
        if not callable(holen):
            return None
        fileid = _fileid_von(eintrag)
        if fileid is None:
            return None
        try:
            rohdaten = holen(fileid, max_bytes)
        except Exception:
            return None
        if not isinstance(rohdaten, (bytes, bytearray)) or not rohdaten:
            return None
        rohdaten = bytes(rohdaten)
        if ziel is not None:
            rohdaten = _verkleinern(rohdaten, ziel)
        return rohdaten

    return kachel_holen


# ── 6. Die Mengen-Regel am echten Bild belegbar machen ────────────────────

def massen_uebersicht(zeilen, katalog=None) -> dict:
    """Ueber die Vektorzeilen zaehlen, was N9a als Menge einstuft.

    Fuer jede Zeile faellt die Entscheidung ueber
    ``personen_cluster.bild_entscheidung``. Belegt wird damit die Mengen-Regel
    am **echten** Bild: ``mengen_ohne_bekannte_person`` sind genau die Bilder,
    die N9a **nicht** clustert (``clustern: False``), weil eine Menschenmenge
    ohne bekannte Vordergrund-Person vorliegt.

    Rueckgabe:: ``{"bilder_gesamt", "geclustert", "nicht_geclustert",
    "mengen", "mengen_ohne_bekannte_person", "je_art", "je_grund"}``.
    """
    pc = _personen_cluster()
    gesamt = 0
    geclustert = 0
    nicht_geclustert = 0
    je_art: dict = {}
    je_grund: dict = {}
    for zeile in zeilen:
        if not isinstance(zeile, dict):
            continue
        entscheidung = pc.bild_entscheidung(zeile, katalog=katalog)
        gesamt += 1
        art = entscheidung["art"]
        grund = entscheidung["grund"]
        je_art[art] = je_art.get(art, 0) + 1
        je_grund[grund] = je_grund.get(grund, 0) + 1
        if entscheidung["clustern"]:
            geclustert += 1
        else:
            nicht_geclustert += 1
    return {
        "bilder_gesamt": gesamt,
        "geclustert": geclustert,
        "nicht_geclustert": nicht_geclustert,
        "mengen": je_art.get(pc.ART_MENGE, 0),
        "mengen_ohne_bekannte_person": je_grund.get(pc.GRUND_MENGE_OHNE, 0),
        "je_art": je_art,
        "je_grund": je_grund,
    }


# ── 7. Sortierplan lesen und auswaehlen ───────────────────────────────────

def plan_lesen(pfad: str) -> list:
    """Den Sortierplan **lesend** einlesen -> ``[{"fileid", "jahr"}]``.

    Gelesen werden nur die Felder ``zuege[].fileid`` und ``zuege[].jahr``.
    Eine fehlende oder unlesbare Datei ergibt eine ``GesichtFehler`` mit
    Klartextmeldung; ein Eintrag ohne ``fileid`` wird uebersprungen (gezaehlt
    wird das nicht — es ist keine Bildzeile).
    """
    if not isinstance(pfad, str) or not pfad.strip():
        raise GesichtFehler("Kein Plan-Pfad angegeben.")
    if not os.path.isfile(pfad):
        raise GesichtFehler(f"Sortierplan nicht gefunden: {pfad}")
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except (OSError, ValueError) as problem:
        raise GesichtFehler(
            f"Sortierplan nicht lesbar ({problem.__class__.__name__}): {pfad}"
        ) from None
    if isinstance(daten, dict):
        zuege = daten.get("zuege")
    elif isinstance(daten, list):
        zuege = daten
    else:
        zuege = None
    if not isinstance(zuege, list):
        raise GesichtFehler(f"Sortierplan ohne Feld 'zuege': {pfad}")
    eintraege: list = []
    for zug in zuege:
        if not isinstance(zug, dict):
            continue
        fileid = zug.get("fileid")
        if isinstance(fileid, bool) or fileid is None:
            continue
        kennung = str(fileid).strip()
        if not kennung:
            continue
        jahr = zug.get("jahr")
        jahr = int(jahr) if _ist_zahl(jahr) else None
        eintraege.append({"fileid": kennung, "jahr": jahr})
    return eintraege


def plan_auswaehlen(eintraege, jahr=None, je_jahr=None, max_bilder=None) -> list:
    """Aus den Planeintraegen die zu verarbeitenden auswaehlen (deterministisch).

    Reihenfolge bleibt die des Plans. ``jahr`` filtert auf ein Jahr, ``je_jahr``
    nimmt hoechstens so viele Bilder je Jahr (in Plan-Reihenfolge), und
    ``max_bilder`` deckelt die Gesamtzahl. Es wird nichts geholt — reine Auswahl.
    """
    gewaehlt: list = []
    pro_jahr: dict = {}
    grenze = int(je_jahr) if _ist_zahl(je_jahr) and int(je_jahr) >= 0 else None
    for eintrag in eintraege or []:
        if not isinstance(eintrag, dict):
            continue
        if jahr is not None and eintrag.get("jahr") != jahr:
            continue
        schluessel = eintrag.get("jahr")
        if grenze is not None:
            if pro_jahr.get(schluessel, 0) >= grenze:
                continue
            pro_jahr[schluessel] = pro_jahr.get(schluessel, 0) + 1
        gewaehlt.append(eintrag)
    if _ist_zahl(max_bilder) and int(max_bilder) >= 0:
        gewaehlt = gewaehlt[:int(max_bilder)]
    return gewaehlt


def _pcloud_dienst():
    """Die echte pCloud-Quelle bauen (erst hier — kein Geheimnis in diesem Modul).

    Der Dienst liest seine Konfiguration selbst; dieses Modul sieht ihn nur als
    Objekt mit ``datei_bytes``. Schlaegt der Import fehl, gibt es eine deutsche
    Meldung (kein Absturz).
    """
    if BACKEND not in sys.path:
        sys.path.insert(0, BACKEND)
    try:
        from app.services.pcloud_service import PCloudService
    except Exception as problem:
        raise GesichtFehler(
            "pCloud-Dienst nicht ladbar "
            f"({problem.__class__.__name__}): {problem}") from None
    return PCloudService()


# ── 8. Kommandozeile (Standard: Trockenlauf) ──────────────────────────────

def jahr_uebersicht(auswahl) -> dict:
    """Die ausgewaehlten Eintraege je Jahr zaehlen (fuer die Ausgabe)."""
    zahlen: dict = {}
    for eintrag in auswahl or []:
        jahr = eintrag.get("jahr") if isinstance(eintrag, dict) else None
        zahlen[jahr] = zahlen.get(jahr, 0) + 1
    return zahlen


def main(argv=None) -> int:
    """Kommandozeilen-Teil: Trockenlauf zaehlen oder Vektorzeilen schreiben.

    Standard ist der **Trockenlauf**: es wird nur gezaehlt und aufgelistet, was
    geholt **wuerde** — **kein** Download, **kein** Schreiben. Erst
    ``--schreiben`` holt wirklich (in-memory) und schreibt die Vektorzeilen
    (``--trocken`` hat Vorrang). Die Ausgabe sind deutsche Klartextzeilen mit
    Zahlen; Zugangsdaten, Ordner-, Personen- und Ortsnamen kommen darin nicht vor.
    """
    zerleger = argparse.ArgumentParser(
        description="Gesichtserkennung N9b: erkennt Gesichter in Bildern und "
                    "schreibt Vektorzeilen fuer das Personen-Verfahren N9a. "
                    "Standard ist der Trockenlauf (kein Download).")
    zerleger.add_argument("--plan", dest="plan", default=STANDARD_PLAN,
                          help="Sortierplan (JSON, nur lesend)")
    zerleger.add_argument("--vektoren", dest="vektoren", default=STANDARD_VEKTOREN,
                          help="Zieldatei der Vektorzeilen (PFLICHT ausserhalb "
                               "des Repos)")
    zerleger.add_argument("--jahr", dest="jahr", type=int, default=None,
                          help="nur Bilder dieses Jahrs")
    zerleger.add_argument("--je-jahr", dest="je_jahr", type=int, default=None,
                          help="hoechstens so viele Bilder je Jahr")
    zerleger.add_argument("--max-bilder", dest="max_bilder", type=int, default=24,
                          help="hoechstens so viele Bilder gesamt (Standard 24)")
    zerleger.add_argument("--modelle", dest="modelle", default=None,
                          help="Ordner der Modelldateien (Standard "
                               "~/foto_sortierung/ml_models)")
    zerleger.add_argument("--max-bytes", dest="max_bytes", type=int,
                          default=KACHEL_MAX_BYTES,
                          help="Obergrenze je Bild-Download in Bytes")
    zerleger.add_argument("--trocken", dest="trocken", action="store_true",
                          help="nichts schreiben (hat Vorrang vor --schreiben)")
    zerleger.add_argument("--schreiben", dest="schreiben", action="store_true",
                          help="wirklich rechnen und die Vektorzeilen schreiben")
    args = zerleger.parse_args(argv)

    schreiben = bool(args.schreiben) and not bool(args.trocken)

    # Ein Zielpfad im Repo ist ein Fehler — und zwar VOR jedem Download.
    if schreiben:
        _personen_cluster().pruefe_ausserhalb_repo(args.vektoren)

    try:
        eintraege = plan_lesen(args.plan)
        auswahl = plan_auswaehlen(eintraege, jahr=args.jahr,
                                  je_jahr=args.je_jahr, max_bilder=args.max_bilder)

        print("Gesichtserkennung N9b — "
              + ("Trockenlauf (es wird NICHTS geholt und NICHTS geschrieben)"
                 if not schreiben else "Schreiben ist eingeschaltet"))
        print(f"Plan: {len(eintraege)} Bild(er)   Auswahl: {len(auswahl)} Bild(er)")
        if args.jahr is not None:
            print(f"gefiltert auf das Jahr {args.jahr}")
        print(f"Vektorzeilen-Ziel: {args.vektoren}")
        for jahr in sorted(jahr_uebersicht(auswahl),
                           key=lambda wert: (wert is None, wert)):
            name = "ohne Jahr" if jahr is None else str(jahr)
            print(f"  {name}: {jahr_uebersicht(auswahl)[jahr]} Bild(er)")

        if not schreiben:
            print("Ohne --schreiben wurde NICHTS geholt und NICHTS geschrieben.")
            return 0

        modell = GesichtsModell(args.modelle)
        dienst = _pcloud_dienst()
        holen = kachel_quelle(dienst, max_bytes=args.max_bytes)

        def hole_fuer(fileid):
            return holen({"fileid": fileid})

        bilder = [(eintrag["fileid"], (lambda f=eintrag["fileid"]: hole_fuer(f)))
                  for eintrag in auswahl]
        lauf = vektoren_fuer_stapel(bilder, modell, max_bilder=args.max_bilder)
        zeilen = list(lauf)
        anzahl = vektoren_schreiben(args.vektoren, zeilen)
        uebersicht = massen_uebersicht(zeilen)
        zaehler = lauf.zaehler
        print(f"Bilder gesamt: {zaehler['bilder_gesamt']}   "
              f"geholt: {zaehler['bilder_geholt']}   "
              f"ohne Gesicht: {zaehler['bilder_ohne_gesicht']}   "
              f"Loecher: {zaehler['loecher']}   "
              f"Fehler: {zaehler['fehler']}   "
              f"sekunden: {zaehler['sekunden']}")
        print(f"Vektorzeilen geschrieben: {anzahl}")
        print(f"Mengen ohne bekannte Person (nicht geclustert): "
              f"{uebersicht['mengen_ohne_bekannte_person']}")
        return 0
    except GesichtFehler as problem:
        print(f"Fehler: {problem}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
