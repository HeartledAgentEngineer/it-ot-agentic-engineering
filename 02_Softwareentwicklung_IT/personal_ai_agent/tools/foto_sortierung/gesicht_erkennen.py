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

Die echte Kachelquelle (Bruecke zurueck zu N9a):
  ``kachel_quelle(service, …)`` baut eine ``kachel_holen(eintrag) -> bytes``
  fuer die Referenzseiten von ``personen_cluster``. Die **N9a-Eintraege**
  tragen die Kennung als ``bild_id`` und die Gesichtsbox als ``bbox`` — die
  Kachelquelle arbeitet **direkt** damit (``_fileid_von`` liest ``fileid``,
  sonst ``bild_id``; ``ausschnitt=True`` schneidet mit ``bbox``), es ist **kein
  Um-Mappen** der Felder mehr noetig. Ohne brauchbare ``bbox`` faellt
  ``ausschnitt=True`` aufs ganze Foto zurueck.

Was dieses Werkzeug bewusst NICHT tut:
  * **Kein Speichern von Bildern.** Bilder werden ausschliesslich **in-memory**
    verarbeitet. Geschrieben wird nur die **Vektorzeilen-Datei** (JSONL, Text).
    Kein Schreiben von Bilddaten auf die Platte, kein Zwischenbild, kein
    Binaer-Schreibmodus. Auch der **Gesichtsausschnitt** der Kachelquelle
    (``kachel_quelle(..., ausschnitt=True)``) entsteht in-memory und **nur mit
    PIL** — kein ``cv2``, kein Zwischenbild, kein Netz.
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

Metadaten im selben Durchlauf (N-0929, 29.09.2026):
  Jedes Foto wird nur **einmal** ueber pCloud geladen; aus denselben Bytes
  entstehen die Gesichter **und** die EXIF-Metadaten. ``exif_metadaten(roh)``
  ist eine reine Funktion (nur PIL, kein ``cv2``, kein Netz) mit immer
  denselben Feldern::

      {"aufnahme": "JJJJ-MM-TTTHH:MM:SS" | None,
       "kamera_hersteller": str | None, "kamera_modell": str | None,
       "gps": {"lat": float, "lon": float} | None}

  ``aufnahme`` kommt aus DateTimeOriginal (0x9003), sonst DateTimeDigitized
  (0x9004), sonst DateTime (0x0132); Nulldaten und Kaputtes ergeben ``None``.
  GPS wird aus dem GPS-IFD (0x8825) in Dezimalgrad umgerechnet (S/W negativ,
  6 Nachkommastellen); unplausible Werte (|lat| > 90, |lon| > 180, exakt 0/0)
  ergeben ``None``. Nie eine Ausnahme nach aussen.

  ``StapelLauf`` legt das Ergebnis unter dem Schluessel ``"metadaten"`` in
  jede Vektorzeile (bestehende Felder unveraendert; ``personen_cluster.
  zeile_pruefen`` baut sein Ergebnis aus den bekannten Feldern und ignoriert
  unbekannte Schluessel). Ein Fehler bei den Metadaten verhindert die
  Gesichtszeile nie. Zaehler: ``mit_aufnahme`` und ``mit_gps`` (Anzahl Bilder).

  Pruefung Bytes-Abschnitt/Verkleinerung (Ergebnis): Im Vektorzeilen-Lauf
  werden die **Originalbytes** bis ``max_bytes`` (Standard 8 MiB) geholt und
  **nicht** verkleinert (``groesse`` wird dort nicht gesetzt; ``_verkleinern``
  gilt nur fuer Kacheln). ``exif_metadaten`` liest aus genau diesen Bytes.
  EXIF steht am JPEG-Anfang, PIL liest nur den Kopf - auch abgeschnittene
  Bytes reichen (per Test belegt). GPS ist sensibel: Konsole und Logs zeigen
  nie Koordinaten, nur die beiden Summen.

Aufruf (Kommandozeile) — **Standard ist der Trockenlauf** (kein Download)::

    # Trockenlauf: nur zaehlen/auflisten, was geholt WUERDE
    .venv/Scripts/python.exe tools/foto_sortierung/gesicht_erkennen.py \
        --plan ~/foto_sortierung/sortierplan.json --jahr 2020 --max-bilder 24

    # wirklich rechnen und die Vektorzeilen schreiben
    .venv/Scripts/python.exe tools/foto_sortierung/gesicht_erkennen.py \
        --plan ~/foto_sortierung/sortierplan.json \
        --vektoren ~/foto_sortierung/personen_vektoren.jsonl --schreiben

Fortsetzen nach Abbruch (29.09.2026):
  Ein langer Lauf (~9.400 Bilder, ~2,4 s je Bild) muss nach einem Abbruch
  nicht von vorn beginnen. ``--fortsetzen`` liest die vorhandene
  ``--vektoren``-Datei tolerant ein (``vorhandene_ids_lesen``: eine kaputte
  oder abgeschnittene Zeile wird gezaehlt und ignoriert), sammelt die
  ``bild_id``s, filtert die Plan-Auswahl auf die **noch fehlenden** Bilder
  (``offene_eintraege`` — **vor** ``--max-bilder``, das Limit gilt also fuer
  die offenen) und schreibt im **Anhaengemodus**. Endet die Datei nach einem
  Abbruch mitten in einer Zeile ohne Zeilenende, wird vor dem Anhaengen ein
  ``"\\n"`` gesetzt, damit die naechste Zeile nicht an die halbe klebt (die
  halbe Zeile bleibt als ignorierbare Zeile stehen — es wird nichts
  abgeschnitten oder geloescht). Nach **jeder** Zeile wird geflusht; ein
  Abbruch kostet hoechstens das aktuelle Bild. Ohne ``--fortsetzen`` bleibt
  alles wie bisher (die Datei wird ueberschrieben). Die Konsole nennt zusaetzlich
  ``bereits vorhanden: N, noch offen: M`` (nur Zahlen)::

      # Stapel von 500 noch fehlenden Bildern, beliebig oft wiederholbar
      .venv/Scripts/python.exe tools/foto_sortierung/gesicht_erkennen.py           --plan ~/foto_sortierung/sortierplan.json           --vektoren ~/foto_sortierung/personen_vektoren.jsonl           --schreiben --fortsetzen --max-bilder 500

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

# Rand eines Gesichtsausschnitts: je Seite so viel wie ``rand`` x bbox-Masse
# (Breite fuer links/rechts, Hoehe fuer oben/unten). 0.45 gibt dem Gesicht
# etwas Kopf-/Schulter-Umfeld, ohne zum halben Bild zu werden.
AUSSCHNITT_RAND = 0.45

# Zielgroesse einer Ausschnitt-Kachel, wenn keine ``groesse`` gesetzt ist:
# quadratisch, weil die Kontaktbogen-Kacheln von N9a quadratisch sind.
AUSSCHNITT_GROESSE = (200, 200)

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


def _merkmal(rekognizer, bild, zeile):
    """128-Wert-Merkmal eines Gesichts — ``None``, wenn es nicht entsteht.

    ``zeile`` ist die **volle Detektionszeile** der Detektion, also die 15
    Werte ``[x, y, w, h, <5 Landmarken-Paare>, score]`` — **nicht** nur das
    5x2-Landmarken-Array. Genau diese Zeile erwartet
    ``cv2.FaceRecognizerSF.alignCrop``: die 5 Landmarken-Paare **und** die
    Boxmasse liegen in **einem** ``float32``-Puffer von 60 Byte.

    Warum das noetig ist (gemessen, nicht behauptet): ``alignCrop`` prueft die
    Form seines Arguments **nicht**. Uebergibt man nur das 5x2-Landmarken-Array
    (40 Byte), liest OpenCV 20 Byte **ueber den Puffer hinaus**; die Landmarken
    werden zu Muell und **jedes** Gesicht eines Bildes bekommt denselben
    Ausschnitt und damit **denselben** Vektor. Gemessen an einem Bild mit 6
    Gesichtern: 5x2-Argument -> 6x dieselbe Ausschnitt-Pruefsumme; volle Zeile
    -> 6 verschiedene Pruefsummen und 6 verschiedene Merkmale.
    """
    reihe = np.asarray(zeile, dtype=np.float32).reshape(-1)[:15]
    try:
        ausschnitt = rekognizer.alignCrop(bild, reihe)
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

    Waechter gegen genau den Fehler der Aufrufform (siehe ``_merkmal``):
    kommen bei einem Bild mit **zwei oder mehr** Gesichtern **bit-identische**
    Merkmale heraus, ist das ein Fehlersignal — dann wird die Gesichtsliste
    **geleert** und das Feld ``"fehler"`` gesetzt, es gibt **keinen stillen
    Durchlauf**. Begruendung: ein echter Erkenner schneidet fuer jedes Gesicht
    einen **anderen** Ausschnitt (andere Landmarken) und liefert daher fuer
    verschiedene Ausschnitte **nie** bitgleiche Merkmale. Bitgleiche Merkmale
    koennen nur entstehen, wenn ``alignCrop`` dieselben (falschen) Landmarken
    bekommt — genau das war der Fehler, der zwei Nachtlaeufe lang still
    durchlief und je Bild nur **einen** Vektor fuer alle Gesichter in die
    Vektordatei schrieb.
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
        # Die volle Detektionszeile hat 15 Werte (bbox 4 + 5x2 Landmarken + score).
        # Ohne sie darf alignCrop nicht aufgerufen werden (siehe _merkmal).
        if werte.size < 15:
            ohne_merkmal += 1
            continue
        bbox = [float(v) for v in werte[0:4]]
        score = float(werte[-1])
        landm = werte[4:14].reshape(5, 2)
        zeile = werte[0:15].astype(np.float32)
        merkmal = _merkmal(rekognizer, bild, zeile)
        if merkmal is None:
            ohne_merkmal += 1
            continue
        ergebnis["gesichter"].append({
            "bbox": bbox,
            "score": score,
            "landm": [[float(x), float(y)] for x, y in landm],
            "embedding": merkmal,
        })

    # Waechter: bit-identische Merkmale bei mehreren Gesichtern sind ein Fehler.
    merkmale = [gesicht["embedding"] for gesicht in ergebnis["gesichter"]]
    if len(merkmale) >= 2 and all(merkmal == merkmale[0]
                                  for merkmal in merkmale[1:]):
        anzahl = len(merkmale)
        ergebnis["gesichter"] = []
        ergebnis["fehler"] = (
            f"Waechter: {anzahl} Gesichter im Bild, aber bit-identische "
            "Merkmale. Ein echter Erkenner liefert fuer verschiedene "
            "Ausschnitte nie bitgleiche Merkmale - das ist ein Fehlersignal. "
            "Ursache ist meist die Aufrufform von alignCrop: erwartet wird die "
            "volle Detektionszeile mit 15 Werten (bbox + 5 Landmarken-Paare + "
            "score), nicht nur das 5x2-Landmarken-Array. Ergebnis verworfen "
            "(leere Gesichtsliste) - kein stiller Durchlauf.")
        return ergebnis

    if ohne_merkmal:
        ergebnis["ohne_merkmal"] = ohne_merkmal
    return ergebnis


# ── 2b. EXIF-Metadaten (reine Funktion, nur PIL) ──────────────────────────

_EXIF_IFD = 0x8769
_GPS_IFD = 0x8825
_DATUM_TAGS = (0x9003, 0x9004, 0x0132)   # Original, Digitized, DateTime


def _exif_leer() -> dict:
    """Die Metadaten-Felder ohne Inhalt — immer dieselbe Form."""
    return {"aufnahme": None, "kamera_hersteller": None,
            "kamera_modell": None, "gps": None}


def _exif_text(wert):
    """Einen EXIF-Textwert saeubern (Bytes/Nullbytes/Leerraum) — sonst ``None``."""
    if isinstance(wert, (bytes, bytearray)):
        wert = bytes(wert).decode("utf-8", errors="ignore")
    if not isinstance(wert, str):
        return None
    wert = wert.replace("\x00", "").strip()
    return wert or None


def _exif_datum(wert):
    """``"2014:08:03 14:22:10"`` -> ISO ``"2014-08-03T14:22:10"`` oder ``None``."""
    text = _exif_text(wert)
    if not text:
        return None
    try:
        import datetime
        stempel = datetime.datetime.strptime(text, "%Y:%m:%d %H:%M:%S")
    except (ValueError, TypeError):
        return None
    return stempel.strftime("%Y-%m-%dT%H:%M:%S")


def _exif_grad(werte, bezug, positiv, negativ):
    """Grad/Minuten/Sekunden + Himmelsrichtung -> Dezimalgrad oder ``None``."""
    try:
        teile = [float(v) for v in werte]
    except (TypeError, ValueError):
        return None
    if len(teile) != 3 or not all(math.isfinite(v) for v in teile):
        return None
    richtung = _exif_text(bezug)
    if richtung is None:
        return None
    richtung = richtung.upper()[:1]
    if richtung not in (positiv, negativ):
        return None
    grad = teile[0] + teile[1] / 60.0 + teile[2] / 3600.0
    return -grad if richtung == negativ else grad


def _exif_gps(gps_ifd):
    """GPS-IFD -> ``{"lat", "lon"}`` (Dezimalgrad, 6 Stellen) oder ``None``."""
    if not gps_ifd:
        return None
    lat = _exif_grad(gps_ifd.get(2), gps_ifd.get(1), "N", "S")
    lon = _exif_grad(gps_ifd.get(4), gps_ifd.get(3), "E", "W")
    if lat is None or lon is None:
        return None
    lat, lon = round(lat, 6), round(lon, 6)
    if abs(lat) > 90 or abs(lon) > 180 or (lat == 0 and lon == 0):
        return None
    return {"lat": lat, "lon": lon}


def exif_metadaten(rohdaten: bytes) -> dict:
    """Datum, Kamera und GPS aus dem EXIF eines Bildes lesen — nur PIL.

    Reine Funktion: kein ``cv2``, kein Netz, kein Schreiben. Rueckgabe immer::

        {"aufnahme": "JJJJ-MM-TTTHH:MM:SS" | None,
         "kamera_hersteller": str | None, "kamera_modell": str | None,
         "gps": {"lat": float, "lon": float} | None}

    Jedes Feld wird einzeln und tolerant gelesen; ein Fehler (kein EXIF, PNG,
    kaputte oder abgeschnittene Bytes) laesst die betroffenen Felder ``None``
    und wirft **nie** eine Ausnahme. Koordinaten werden nirgends gedruckt.
    """
    ergebnis = _exif_leer()
    try:
        from PIL import Image
        with Image.open(io.BytesIO(bytes(rohdaten))) as bild:
            exif = bild.getexif()
            if not exif:
                return ergebnis
            try:
                exif_ifd = exif.get_ifd(_EXIF_IFD)
            except Exception:
                exif_ifd = {}
            for tag in _DATUM_TAGS:
                quelle = exif if tag == 0x0132 else exif_ifd
                iso = _exif_datum(quelle.get(tag))
                if iso:
                    ergebnis["aufnahme"] = iso
                    break
            ergebnis["kamera_hersteller"] = _exif_text(exif.get(0x010F))
            ergebnis["kamera_modell"] = _exif_text(exif.get(0x0110))
            try:
                ergebnis["gps"] = _exif_gps(exif.get_ifd(_GPS_IFD))
            except Exception:
                ergebnis["gps"] = None
    except Exception:
        pass
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
      * ``mit_aufnahme`` — geholte Bilder mit EXIF-Aufnahmedatum
      * ``mit_gps`` — geholte Bilder mit plausiblen GPS-Koordinaten
      * ``sekunden`` — Laufzeit bis zum Ende

    Jede Zeile traegt zusaetzlich ``"metadaten"`` (siehe ``exif_metadaten``).
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
            "mit_aufnahme": 0,
            "mit_gps": 0,
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
                metadaten = exif_metadaten(bytes(rohdaten))
                if not isinstance(metadaten, dict):
                    raise TypeError("keine Metadaten")
            except Exception:
                metadaten = _exif_leer()
            if metadaten.get("aufnahme"):
                self.zaehler["mit_aufnahme"] += 1
            if metadaten.get("gps"):
                self.zaehler["mit_gps"] += 1

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
                "metadaten": metadaten,
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


def _endet_mit_zeilenende(pfad: str) -> bool:
    """Sagen, ob die Datei leer ist oder mit ``"\\n"`` endet (nur Text, nur lesend)."""
    groesse = os.path.getsize(pfad)
    if groesse == 0:
        return True
    try:
        with open(pfad, encoding="utf-8", newline="") as datei:
            datei.seek(groesse - 1)
            return datei.read(1) == "\n"
    except (OSError, ValueError):
        return False


def vorhandene_ids_lesen(pfad: str):
    """Die ``bild_id``s einer Vektordatei tolerant lesen -> ``(ids, kaputt)``.

    Nur lesend. Fehlt die Datei, kommt ``(set(), 0)``. Leere Zeilen zaehlen
    nicht; eine Zeile, die kein JSON-Objekt mit nichtleerer ``bild_id`` ist
    (typisch: abgeschnittene letzte Zeile nach einem Abbruch), wird
    **gezaehlt** (``kaputt``) und ignoriert. Kennungen sind Zeichenketten.
    """
    ids: set = set()
    kaputt = 0
    if not isinstance(pfad, str) or not os.path.isfile(pfad):
        return ids, kaputt
    with open(pfad, encoding="utf-8", errors="replace") as datei:
        for zeile in datei:
            if not zeile.strip():
                continue
            try:
                daten = json.loads(zeile)
            except ValueError:
                kaputt += 1
                continue
            kennung = daten.get("bild_id") if isinstance(daten, dict) else None
            if isinstance(kennung, (str, int)) and not isinstance(kennung, bool)                     and str(kennung).strip():
                ids.add(str(kennung).strip())
            else:
                kaputt += 1
    return ids, kaputt


def offene_eintraege(auswahl, vorhandene_ids) -> list:
    """Aus der Plan-Auswahl die Eintraege ohne vorhandene Vektorzeile behalten.

    Reine Funktion; Reihenfolge der Auswahl bleibt. Verglichen wird die
    ``fileid`` als Zeichenkette mit den ``bild_id``s der Vektordatei.
    """
    bekannt = {str(kennung) for kennung in (vorhandene_ids or ())}
    return [eintrag for eintrag in auswahl or []
            if isinstance(eintrag, dict)
            and str(eintrag.get("fileid")) not in bekannt]


def vektoren_schreiben(pfad: str, zeilen, anhaengen: bool = False) -> int:
    """Vektorzeilen als **Text** (JSONL) schreiben — nur **ausserhalb** des Repos.

    Schreibt ausschliesslich die Zeilen selbst (Text, UTF-8); es entstehen
    **keine** Bilddateien. Ein Pfad im Repo ergibt eine deutsche Meldung und
    ``SystemExit(2)`` (ueber ``personen_cluster.pruefe_ausserhalb_repo``).
    Rueckgabe ist die Anzahl geschriebener Zeilen.

    Standard ist Ueberschreiben (``"w"``). Mit ``anhaengen=True`` (Fortsetzen
    nach Abbruch) wird angehaengt; endet eine vorhandene Datei nicht mit
    ``"\\n"`` (abgeschnittene letzte Zeile), wird zuerst ein Zeilenende
    gesetzt, damit die naechste Zeile nicht an die halbe klebt. Nach jeder
    Zeile wird geflusht — ein Abbruch verliert hoechstens das aktuelle Bild.
    """
    _personen_cluster().pruefe_ausserhalb_repo(pfad)
    ordner = os.path.dirname(os.path.abspath(pfad))
    if ordner:
        os.makedirs(ordner, exist_ok=True)
    anzahl = 0
    davor_offen = bool(anhaengen) and os.path.isfile(pfad)         and not _endet_mit_zeilenende(pfad)
    with open(pfad, "a" if anhaengen else "w", encoding="utf-8") as datei:
        if davor_offen:
            datei.write("\n")
            datei.flush()
        for zeile in zeilen:
            datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")
            datei.flush()
            anzahl += 1
    return anzahl


# ── 5. Die echte pCloud-Kachelquelle (eingesteckt, kein Geheimnis hier) ────

def _fileid_von(eintrag):
    """Die Kennung eines Kachel-Eintrags lesen — ``None``, wenn keine da ist.

    Vorrang hat ``fileid`` (so kommt es aus dem Plan). Fehlt es, wird
    ``bild_id`` gelesen — **genau so tragen die N9a-Eintraege**
    (``personen_cluster``) ihre Kennung: ``{"bild_id": …, "bbox": …}``. Damit
    braucht der Referenzseiten-Weg kein Um-Mappen mehr.

    Ein blanker Eintrag (Text/Zahl) gilt als Kennung — das ist der einfache
    Aufruf ``kachel_holen("1234567")``. ``bool`` und ``None`` sind **keine**
    Kennung (``True`` waere sonst die Zahl 1); alles andere ergibt ``None``.
    Zurueckgegeben wird der Wert unveraendert (Text oder Zahl).
    """
    if isinstance(eintrag, dict):
        wert = eintrag.get("fileid")
        if isinstance(wert, bool) or wert is None:
            wert = eintrag.get("bild_id")
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


def ausschnitt_rechnen(bbox, breite, hoehe, rand=AUSSCHNITT_RAND):
    """Die Grenzen eines Gesichtsausschnitts rechnen — ``(x0, y0, x1, y1)|None``.

    **Reine Funktion**, keine Bilddatei, kein PIL — damit die Geometrie ohne
    Bild pruefbar ist.

    ``bbox`` ist ``[x, y, w, h]`` in Pixeln (YuNet-Reihenfolge wie in N9a),
    ``breite``/``hoehe`` sind die Bildmasse. Je Seite kommt ``rand`` x
    bbox-Masse dazu (Breite links/rechts, Hoehe oben/unten), danach wird an die
    Bildgrenzen **geklemmt** (``0 … breite`` bzw. ``0 … hoehe``).

    ``None`` bei allem, was keinen Ausschnitt ergibt: falsche ``bbox``-Laenge,
    Nicht-Zahlen, ``breite``/``hoehe`` ``<= 0``, Breite/Hoehe der Box ``<= 0``
    und ein entarteter Ausschnitt (nach dem Klemmen keine Pixel mehr uebrig,
    z. B. Box ganz ausserhalb des Bildes). Ein unbrauchbares ``rand`` (keine
    Zahl oder negativ) faellt still auf ``AUSSCHNITT_RAND`` zurueck.
    """
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    if any(not _ist_zahl(wert) for wert in bbox):
        return None
    if not _ist_positiv(breite) or not _ist_positiv(hoehe):
        return None
    x, y, b_breite, b_hoehe = (float(wert) for wert in bbox)
    if b_breite <= 0 or b_hoehe <= 0:
        return None
    rand = float(rand) if _ist_zahl(rand) and float(rand) >= 0 \
        else AUSSCHNITT_RAND
    rechts_grenze = int(float(breite))
    unten_grenze = int(float(hoehe))
    links = int(math.floor(x - rand * b_breite))
    oben = int(math.floor(y - rand * b_hoehe))
    rechts = int(math.ceil(x + b_breite + rand * b_breite))
    unten = int(math.ceil(y + b_hoehe + rand * b_hoehe))
    links = max(0, min(links, rechts_grenze))
    oben = max(0, min(oben, unten_grenze))
    rechts = max(0, min(rechts, rechts_grenze))
    unten = max(0, min(unten, unten_grenze))
    if rechts - links < 1 or unten - oben < 1:
        return None
    return (links, oben, rechts, unten)


def _ausschnitt_bytes(rohdaten, bbox, rand, ziel):
    """Einen Gesichtsausschnitt in-memory bauen — Bytes oder ``None``.

    **Nur PIL** (``cv2`` kommt hier nicht vor), kein Netz, **kein** Schreiben
    auf die Platte. Ablauf: Bytes dekodieren -> ``ausschnitt_rechnen`` ->
    ``crop`` -> auf ``ziel`` skalieren -> JPEG in-memory.

    Jeder Fehler ergibt ``None`` (unlesbare Bytes, fehlende/unbrauchbare
    ``bbox``, entarteter Ausschnitt, fehlendes PIL) — der Aufrufer faellt dann
    aufs **ganze Foto** zurueck. Eine Ausnahme dringt nie nach aussen.
    """
    try:
        from PIL import Image
    except Exception:
        return None
    try:
        with Image.open(io.BytesIO(rohdaten)) as quelle:
            bild = quelle.convert("RGB")
            grenzen = ausschnitt_rechnen(bbox, bild.width, bild.height, rand)
            if grenzen is None:
                return None
            bild = bild.crop(grenzen)
            if ziel is not None:
                bild = bild.resize((int(ziel[0]), int(ziel[1])))
            puffer = io.BytesIO()
            bild.save(puffer, format="JPEG", quality=85)
        return puffer.getvalue()
    except Exception:
        return None


def kachel_quelle(service, max_bytes=KACHEL_MAX_BYTES, groesse=None,
                  ausschnitt=False, rand=AUSSCHNITT_RAND):
    """Eine ``kachel_holen(eintrag) -> bytes | None`` aus einem Dienst bauen.

    ``service`` wird **eingesteckt** (Duck-Typing): es genuegt ein Objekt mit
    ``datei_bytes(fileid, max_bytes)`` — z. B. ``PCloudService``. Dieses Modul
    kennt weder Zugangsdaten noch Konfiguration; hinein kommt nur die fertige
    Abruffunktion.

    Die zurueckgegebene Funktion holt fuer einen Eintrag mit ``fileid`` **oder**
    ``bild_id`` (siehe ``_fileid_von`` — die N9a-Eintraege tragen ``bild_id``)
    die Bytes **in-memory**. Fehler, leere oder fehlende Antworten ergeben
    ``None`` (der Platzhalter von ``referenzseiten_bauen`` greift) — **nie** ein
    Abbruch. Ist ``groesse`` ``(breite, hoehe)`` gesetzt, wird die Kachel
    in-memory auf diese Kantenlaenge verkleinert.

    ``ausschnitt=True`` schneidet zusaetzlich **in-memory** um das Gesicht: aus
    der ``bbox`` des Eintrags (``[x, y, w, h]`` — so tragen es die
    **N9a-Eintraege** neben ``bild_id``) wird mit dem Rand ``rand`` x
    bbox-Masse je Seite, an die Bildgrenzen geklemmt, ein Ausschnitt gebildet
    und auf die Ziel-Kachelgroesse skaliert — ``groesse``, sonst
    ``AUSSCHNITT_GROESSE`` (200x200, quadratisch). Das ist reine **PIL**-Arbeit:
    kein ``cv2``, kein Netz, **kein** Schreiben auf die Platte.

    **Rueckfall statt Abbruch:** fehlender oder unbrauchbarer ``bbox``,
    unlesbare Bytes, ein entarteter Ausschnitt oder ein fehlendes PIL ergeben
    das **ganze Foto** wie ohne ``ausschnitt``; eine Ausnahme dringt nie nach
    aussen. Ohne brauchbare ``bbox`` ist ``ausschnitt=True`` also wirkungslos —
    im **Vektorzeilen-Lauf** von ``main`` ist vor dem Download nur die Kennung
    bekannt, deshalb wirkt der Schalter dort nicht (siehe
    ``kachelquelle_hinweis``); im **Referenzseiten-Weg** von
    ``personen_cluster`` tragen die Eintraege ``bild_id`` und ``bbox``, dort
    schneidet die Quelle wirklich je Gesicht.
    """
    holen = getattr(service, "datei_bytes", None)
    ziel = _groesse_lesen(groesse)
    schneiden = bool(ausschnitt)
    ziel_ausschnitt = ziel if ziel is not None else AUSSCHNITT_GROESSE
    randwert = float(rand) if _ist_zahl(rand) and float(rand) >= 0 \
        else AUSSCHNITT_RAND

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
        if schneiden:
            bbox = eintrag.get("bbox") if isinstance(eintrag, dict) else None
            geschnitten = _ausschnitt_bytes(rohdaten, bbox, randwert,
                                            ziel_ausschnitt)
            if geschnitten is not None:
                return geschnitten
            # kein brauchbarer bbox / unlesbare Bytes -> ganzes Foto wie bisher
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


def kachelquelle_hinweis(ausschnitt: bool) -> str:
    """Die Klartextzeile zur Kachelquelle bauen — wahrheitsgemaess, **rein**.

    Reine Funktion (kein I/O, kein Zustand): sie sagt, was in diesem Lauf
    wirklich geschieht. Im **Vektorzeilen-Lauf** von ``main`` wird vor dem
    Download nur die Kennung uebergeben — eine ``bbox`` ist dort erst **nach**
    dem Download bekannt. ``--ausschnitt`` wirkt in diesem Lauf deshalb
    **nicht**; die Kachelquelle faellt aufs ganze Foto zurueck.

    Wirklich je Gesicht geschnitten wird im **Referenzseiten-Weg von
    ``personen_cluster``** (``referenzseiten_bauen``): dort tragen die
    Kachel-Eintraege ``bild_id`` **und** ``bbox``, und ``kachel_holen`` wird je
    Kachel aufgerufen.

    ``ausschnitt=False`` beschreibt den Download des **ganzen Fotos**. Die
    Zeile enthaelt keine Namen, keine Pfade und keine Kennungen.
    """
    if ausschnitt:
        return ("Kachelquelle: ganzer Foto-Download je Bild, in-memory. "
                "--ausschnitt wirkt im Vektorzeilen-Lauf NICHT: hier ist vor "
                "dem Download keine bbox bekannt (nur die Kennung geht hin). "
                "Geschnitten wird je Gesicht nur im Referenzseiten-Weg von "
                "personen_cluster, wo die Eintraege bild_id und bbox tragen "
                f"(Ziel {AUSSCHNITT_GROESSE[0]}x{AUSSCHNITT_GROESSE[1]} px, "
                f"Rand {AUSSCHNITT_RAND} x bbox, nur PIL).")
    return ("Kachelquelle: ganzes Foto je Bild, in-memory verkleinert "
            "(kein Gesichtsausschnitt).")


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
    zerleger.add_argument("--ausschnitt", dest="ausschnitt",
                          action="store_true",
                          help="Kachelquelle schneidet in-memory um das Gesicht "
                               "(nur PIL; ohne bbox bzw. bei Fehlern: ganzes "
                               "Foto). Wirkt nur im Referenzseiten-Weg; im "
                               "Vektorzeilen-Lauf ist vor dem Download keine "
                               "bbox bekannt. Standard: ganzes Foto")
    zerleger.add_argument("--fortsetzen", dest="fortsetzen", action="store_true",
                          help="vorhandene --vektoren-Datei lesen, nur noch "
                               "fehlende Bilder verarbeiten und anhaengen "
                               "(--max-bilder gilt fuer die offenen)")
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
        vorhanden = 0
        offen = 0
        if args.fortsetzen:
            # Erst auf die noch fehlenden Bilder filtern, DANN deckeln.
            ids, kaputt = vorhandene_ids_lesen(args.vektoren)
            alle = plan_auswaehlen(eintraege, jahr=args.jahr,
                                   je_jahr=args.je_jahr, max_bilder=None)
            offene = offene_eintraege(alle, ids)
            vorhanden, offen = len(ids), len(offene)
            auswahl = plan_auswaehlen(offene, max_bilder=args.max_bilder)
        else:
            auswahl = plan_auswaehlen(eintraege, jahr=args.jahr,
                                      je_jahr=args.je_jahr,
                                      max_bilder=args.max_bilder)

        print("Gesichtserkennung N9b — "
              + ("Trockenlauf (es wird NICHTS geholt und NICHTS geschrieben)"
                 if not schreiben else "Schreiben ist eingeschaltet"))
        print(f"Plan: {len(eintraege)} Bild(er)   Auswahl: {len(auswahl)} Bild(er)")
        if args.jahr is not None:
            print(f"gefiltert auf das Jahr {args.jahr}")
        print(f"Vektorzeilen-Ziel: {args.vektoren}")
        if args.fortsetzen:
            print(f"Fortsetzen: bereits vorhanden: {vorhanden}, "
                  f"noch offen: {offen}")
            if kaputt:
                print(f"kaputte Zeilen in der Vektordatei (ignoriert): {kaputt}")
        for jahr in sorted(jahr_uebersicht(auswahl),
                           key=lambda wert: (wert is None, wert)):
            name = "ohne Jahr" if jahr is None else str(jahr)
            print(f"  {name}: {jahr_uebersicht(auswahl)[jahr]} Bild(er)")

        if not schreiben:
            print("Ohne --schreiben wurde NICHTS geholt und NICHTS geschrieben.")
            return 0

        modell = GesichtsModell(args.modelle)
        # Waechter (29.09.2026): Ist das Gesichtsmodell nicht ladbar (falscher
        # Interpreter ohne cv2/onnxruntime, Modelldateien fehlen), wuerde jede
        # Zeile stumm mit leerer Gesichtsliste geschrieben — so geschehen im
        # Nachtlauf N-0929. Deshalb VOR dem ersten Bild laden und sonst abbrechen.
        laden = getattr(modell, "_laden", None)
        if callable(laden):
            try:
                laden()
            except Exception as problem:
                print("Abbruch: Gesichtsmodell nicht ladbar "
                      f"({problem.__class__.__name__}): {problem}\n"
                      "Richtigen Interpreter nehmen (Gesichter-venv mit cv2 und "
                      "onnxruntime) und die Modelldateien pruefen. "
                      "Es wurde NICHTS geschrieben.")
                return 2
        dienst = _pcloud_dienst()
        holen = kachel_quelle(dienst, max_bytes=args.max_bytes,
                              ausschnitt=args.ausschnitt)
        print(kachelquelle_hinweis(args.ausschnitt))

        def hole_fuer(fileid):
            return holen({"fileid": fileid})

        bilder = [(eintrag["fileid"], (lambda f=eintrag["fileid"]: hole_fuer(f)))
                  for eintrag in auswahl]
        lauf = vektoren_fuer_stapel(bilder, modell, max_bilder=args.max_bilder)
        zeilen: list = []

        def gesammelt():
            # Zeile fuer Zeile durchreichen: jede wird sofort geschrieben und
            # geflusht, ein Abbruch verliert hoechstens das aktuelle Bild.
            for zeile in lauf:
                zeilen.append(zeile)
                yield zeile

        anzahl = vektoren_schreiben(args.vektoren, gesammelt(),
                                    anhaengen=bool(args.fortsetzen))
        uebersicht = massen_uebersicht(zeilen)
        zaehler = lauf.zaehler
        print(f"Bilder gesamt: {zaehler['bilder_gesamt']}   "
              f"geholt: {zaehler['bilder_geholt']}   "
              f"ohne Gesicht: {zaehler['bilder_ohne_gesicht']}   "
              f"Loecher: {zaehler['loecher']}   "
              f"Fehler: {zaehler['fehler']}   "
              f"sekunden: {zaehler['sekunden']}")
        print(f"Metadaten: mit Aufnahmedatum: {zaehler['mit_aufnahme']}   "
              f"mit GPS: {zaehler['mit_gps']}")
        print(f"Vektorzeilen geschrieben: {anzahl}")
        print(f"Mengen ohne bekannte Person (nicht geclustert): "
              f"{uebersicht['mengen_ohne_bekannte_person']}")
        return 0
    except GesichtFehler as problem:
        print(f"Fehler: {problem}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
