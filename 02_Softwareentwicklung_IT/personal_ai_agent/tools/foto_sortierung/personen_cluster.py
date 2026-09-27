"""Personen-Verfahren der Foto-Personen-Stufe (Nachtlauf-Schritt N9a, 27.09.2026).

Wozu dieses Werkzeug:
  Die Vorstufen haben den Bild-Bestand thematisch sortierbar gemacht. Offen ist
  die Personen-Ebene: Gesichter finden, zu Gruppen buendeln, unbenannte Gruppen
  mit stabilen Kennungen (``Person_001`` …) versehen und je Gruppe eine
  Referenzseite (Kontaktbogen) bauen, auf der der Nutzer die Gruppe wiedererkennt
  und spaeter benennen kann.

  **Dieses Werkzeug rechnet nur auf Zahlen.** Eingabe sind Vektoren, wie sie
  ``backend/face_infer.py`` schon liefert (YuNet-``bbox`` + 128-dim
  SFace-``embedding``). Es oeffnet kein Bild, laedt nichts herunter und ruft
  keine pCloud an. Damit haengt N9a nicht an OpenCV/onnxruntime (beide fehlen im
  PC-venv, die Modelldateien liegen auf dem Handy) und ist vollstaendig offline
  pruefbar. Die echte Erkennung ist Schritt N9b.

Was dieses Werkzeug bewusst NICHT tut:
  * **Kein Loeschen.** Es gibt im ganzen Modul keinen Loeschaufruf — weder
    gegen die pCloud noch gegen eine Datei. Ein Test prueft die Abwesenheit.
  * **Kein pCloud-Aufruf, kein Download.** Die Kacheln kommen ueber die
    eingesteckte Funktion ``kachel_holen(eintrag) -> bytes | None`` herein.
    Ohne echte Kachelquelle entstehen beschriftete Platzhalter — die
    Referenzseiten bleiben trotzdem lesbar und das Verfahren bleibt offline.
  * **Kein Schreiben ins Repo.** Ausgaben gehen nur in einen Ordner
    **ausserhalb** des Repos; ein Repo-Pfad ergibt eine deutsche Klartextmeldung
    und ``SystemExit(2)``, geschrieben wird dann nichts.
  * **Keine Namen.** Kennungen sind ``Person_001`` … Ein Name aus dem Katalog
    darf gelesen werden (Feld ``name``), wird aber **nie** auf die Konsole
    geschrieben und nie ins Repo gelegt.

Die Mengen-Regel (der Kern des Plans, hier als Code):
  Aufnahmen mit **vielen kleinen Gesichtern** (Menschenmenge weit weg, niemand
  erkennbar) werden **nicht** geclustert und **nicht** angelernt — dort gaebe es
  nur Rauschen. Eine Ausnahme gibt es: ist im **Vordergrund** eine **bekannte**
  Person aus dem Katalog, ist es ein normales Foto mit Beiwerk und wird ganz
  normal behandelt. Die Entscheidung faellt ``bild_art`` ueber den
  Flaechenanteil des Gesichts (nicht ueber die Pixelzahl — so gilt dieselbe
  Schwelle fuer 12-MP-Handyfotos und fuer Scans) und ``bild_entscheidung``
  macht daraus ``clustern: True/False`` samt Klartext-Grund.

Eingabe-Format (genau so, wie ``face_infer.py op_embed`` antwortet):

  JSONL, eine Zeile je Bild::

      {"bild_id": "1234567", "breite": 4032, "hoehe": 3024,
       "gesichter": [
         {"bbox": [1200.0, 800.0, 420.0, 420.0], "score": 0.93,
          "embedding": [0.01, -0.2, ... 128 Werte ...]}
       ]}

  * ``bild_id`` ist die pCloud-``fileid`` als Zeichenkette (oder ein Hash) —
    Pfade, Ordnernamen und echte Namen kommen hier nicht vor.
  * ``bbox`` ist ``[x, y, w, h]`` in absoluten Pixeln relativ zum vollen Bild
    (Reihenfolge wie bei YuNet/``face_infer.py``).
  * ``embedding`` hat 128 Werte (SFace). Andere Laengen machen die **Zeile**
    ungueltig — sie wird gezaehlt, nicht geraten, und nie bricht etwas ab.

  Katalog (optional, fuer die Vordergrund-Pruefung), JSON::

      {"personen": [{"kennung": "Person_001", "name": null,
                     "vektoren": [[... 128 ...]]}]}

  ``name: null`` ist der Normalfall (unbenannt).

Aufruf (Kommandozeile)::

    # Trockenlauf (Standard): nur zeigen, was entstuende
    .venv/Scripts/python.exe tools/foto_sortierung/personen_cluster.py \
        --vektoren ~/foto_sortierung/personen_vektoren.jsonl \
        --ausgabe  ~/foto_sortierung/personen_probe

    # wirklich schreiben (Referenzseiten + Kennungs-Altbestand)
    .venv/Scripts/python.exe tools/foto_sortierung/personen_cluster.py \
        --vektoren ~/foto_sortierung/personen_vektoren.jsonl \
        --ausgabe  ~/foto_sortierung/personen_probe --katalog ~/foto_sortierung/personen_katalog.json --schreiben

Als Modul (Tests, Skripte): ``main(argv=[...])``.
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

# Vorgabepfade: ausserhalb des Repos — dort liegen Biometrie und Vektoren.
STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_VEKTOREN = os.path.join(STANDARD_BASIS, "personen_vektoren.jsonl")
STANDARD_AUSGABE = os.path.join(STANDARD_BASIS, "personen_probe")
STANDARD_KATALOG = os.path.join(STANDARD_BASIS, "personen_katalog.json")
STANDARD_KENNUNGEN = os.path.join(STANDARD_BASIS, "personen_kennungen.json")

# Name des Kennungs-Altbestands im Ausgabeordner (macht Kennungen stabil).
KENNUNGEN_DATEI = "kennungen.json"

# ── Schwellen (alle hier, keine Schwellen im Aufrufer) ─────────────────────
#
# Warum Flaechenanteil statt Pixelzahl: dieselbe Regel soll fuer 12-MP-Handyfotos
# (4032x3024), fuer eingescannte Abzuege (andere Aufloesung) und fuer Crops
# gelten. Ein Anteil der Bildflaeche ist von der Aufloesung unabhaengig — eine
# Pixelgrenze waere bei jedem Geraet eine andere Entscheidung.

# Score-Grenze der Gesichtserkennung — derselbe Wert wie in ``face_infer.py``.
MIN_SCORE = 0.6

# Flaechen-Tor gegen **entartete Boxen** — nicht gegen Rauschen.
#
# Dieses Tor war nie das Rausch-Tor: das ist MIN_SCORE = 0.6 (der Score der
# Detektion). Hier wird nur noch verworfen, was keine Gesichtsflaeche sein
# kann, weil die Box gegen null geht (Breite/Hoehe ~ 0 nach NMS-Resten).
#
# Herleitung (gemessen, nicht behauptet):
#   * 0,00001 der Bildflaeche sind bei 4032x3024 = 12,2 MP rund 122 px, also
#     etwa 11x11 px — praktisch YuNets eigene Mindest-Box (10x10 px). Kleiner
#     wird von der Detektion ohnehin nichts geliefert.
#   * Der alte Wert 0,0005 (= 0,05 %, rund 23x23 px) verwarf dagegen **echte**
#     Funde: die kleinste echte Detektion der Vormessung hat einen
#     Flaechenanteil von 0,000145 (13 kleine Gesichter auf 4032x3456), die
#     kleinste echte Detektion des Nachtlaufs N9b einen von 0,000022
#     (16x22 px auf 4608x3456). Beide fielen unter das Tor — deshalb erreichte
#     die Mengen-Regel den Zweig ``menge`` nicht, sondern nur ``leer``.
#   * Ab 0,0001 ist der Zweig ``menge`` am echten Foto erreicht und die
#     Verteilung aendert sich bei weiterer Absenkung nicht mehr; 0,00001 liegt
#     darunter und damit auf der sicheren Seite, ohne je ein echtes Gesicht
#     wegzuwerfen.
#
# Keine andere Schwelle ist davon beruehrt (MIN_SCORE, ANTEIL_ERKENNBAR,
# MENGE_ANZAHL, KATALOG_SCHWELLE, CLUSTER_SCHWELLE, CLUSTER_MIN_NACHBAR,
# ALT_SCHWELLE bleiben wertgleich).
ANTEIL_MIN = 0.00001

# "Erkennbar" heisst: das Gesicht fuellt mindestens 0,5 % der Bildflaeche.
# 4032x3024 -> rund 70x70 Pixel; erst dort traegt ein SFace-Embedding
# verlaesslich, und erst dort ist von einem Vordergrund-Gesicht zu reden.
ANTEIL_ERKENNBAR = 0.005

# Ab so vielen nutzbaren Gesichtern ohne erkennbares ist es eine Menschenmenge.
MENGE_ANZAHL = 6

# Cosinus-Grenze fuer einen Katalog-Treffer. 0.363 ist der von OpenCV fuer
# SFace dokumentierte Standardwert (``FaceRecognizerSF``, cosine >= 0.363 =
# dieselbe Person).
KATALOG_SCHWELLE = 0.363

# Cosinus-**Distanz** (``1 - cosinus``) fuer das Clustern: 0.45 entspricht
# einer Cosinus-Aehnlichkeit von 0.55 — strenger als der Katalog-Treffer, weil
# beim Clustern aus vielen Vektoren entschieden wird und eine zu lockere Grenze
# fremde Personen zusammenlegen wuerde.
CLUSTER_SCHWELLE = 0.45

# Die Untergrenze je Gruppe: beim Dichte-Verfahren braucht ein Kernpunkt
# mindestens so viele Nachbarn (sich selbst mitgezaehlt), beim vollstaendigen
# Verfahren ist es die Mindestgruppengroesse. Mit 2 waeren schon Paare eine
# Gruppe (fast jedes Rauschpaar); 3 verlangt eine kleine Mehrheit, bevor daraus
# eine Referenzseite entsteht.
CLUSTER_MIN_NACHBAR = 3

# Die zwei Verknuepfungs-Verfahren des Clusterns.
# ``dichte`` ist das Bestandsverfahren (DBSCAN-artig, Expansion vom Kernpunkt).
# ``vollstaendig`` ist die agglomerative Complete-Linkage (Verschmelzen nur,
# wenn das weiteste Punktpaar beider Gruppen <= Schwelle ist).
VERFAHREN_DICHTE = "dichte"
VERFAHREN_VOLLSTAENDIG = "vollstaendig"
VERFAHREN = (VERFAHREN_DICHTE, VERFAHREN_VOLLSTAENDIG)

# Produktionsstandard ist die **vollstaendige Verknuepfung**: das Dichte-
# Verfahren verknuepft transitiv (A nah an B, B nah an C — schon liegen A und C
# zusammen) und bildet bei Schwelle 0,45 gemessen eine Gruppe mit Durchmesser
# 0.9032 = 2 x Schwelle; die vollstaendige Verknuepfung garantiert dagegen
# Durchmesser <= Schwelle (gemessen 0.4417). Deshalb steht hier NICHT mehr das
# Dichte-Verfahren — es bleibt nur als Mess- und Vergleichsweg erhalten.
CLUSTER_VERFAHREN = VERFAHREN_VOLLSTAENDIG

# Cosinus-Grenze, ab der eine neue Gruppe auf einen Altbestand passt (stabile
# Kennung). Derselbe SFace-Standardwert wie beim Katalog-Treffer.
ALT_SCHWELLE = KATALOG_SCHWELLE

# Laenge eines SFace-Embeddings. Andere Laengen sind ungueltig.
MERKMAL_LAENGE = 128

# Kacheln der Referenzseite.
KACHELN_JE_SEITE = 8
KACHEL_BREITE = 200
KACHEL_HOEHE = 200
KACHEL_SPALTEN = 4
BESCHRIFTUNG_HOEHE = 18

# Die Menge betreffenden Schwellen als benannte Konstanten-Sammlung (der
# Auftrag verlangt ``MENGEN_PARAMS``). ``bild_art``/``bild_entscheidung``
# nehmen optional ein ``params``-Dict und ueberschreiben damit einzelne Werte —
# im Normalfall bleibt es bei dieser Sammlung.
MENGEN_PARAMS = {
    "min_score": MIN_SCORE,
    "anteil_min": ANTEIL_MIN,
    "anteil_erkennbar": ANTEIL_ERKENNBAR,
    "menge_anzahl": MENGE_ANZAHL,
    "katalog_schwelle": KATALOG_SCHWELLE,
}

# Die vier Arten eines Bildes.
ART_LEER = "leer"
ART_GRUPPE = "gruppe"
ART_MENGE = "menge"
ART_UNKLAR = "unklar"
ARTEN = (ART_LEER, ART_GRUPPE, ART_MENGE, ART_UNKLAR)

# Klartext-Gruende der Entscheidung (stehen so im Bericht).
GRUND_LEER = "leer"
GRUND_UNKLAR = "unklar"
GRUND_GRUPPE = "gruppe"
GRUND_MENGE_OHNE = "menge_ohne_bekannte_person"
GRUND_MENGE_MIT = "menge_mit_bekannter_person"
GRUENDE = (GRUND_LEER, GRUND_UNKLAR, GRUND_GRUPPE, GRUND_MENGE_OHNE,
           GRUND_MENGE_MIT)

# Kennungs-Muster: ``Person_001`` … (drei Stellen, damit die Sortierung als
# Text und als Zahl dieselbe bleibt).
KENNUNG_MUSTER = "Person_%03d"
KENNUNG_REGEX = r"^Person_(\d+)$"

# Beschriftung einer Kachel ohne echtes Kachelbild.
PLATZHALTER_TEXT = "keine Kachel"
PLATZHALTER_FARBE = (200, 200, 200)
PLATZHALTER_RAND = (120, 120, 120)
TEXT_FARBE = (32, 32, 32)
SEITEN_HINTERGRUND = (255, 255, 255)


class PersonenFehler(Exception):
    """Fehler dieses Werkzeugs — deutsche Klartextmeldung, kein Absturz."""


# ── Kleine Helfer (tolerant lesen, nie raten) ─────────────────────────────

def _ist_zahl(wert) -> bool:
    """Eine Zahl (int/float, kein ``bool``, endlich) — sonst ``False``.

    ``bool`` zaehlt ausdruecklich **nicht** als Zahl: ``True`` waere sonst die
    Zahl 1 und ein Wahrheitswert wuerde stillschweigend zu einer Koordinate.
    """
    if isinstance(wert, bool):
        return False
    if not isinstance(wert, (int, float)):
        return False
    return math.isfinite(float(wert))


def _zahl(n) -> str:
    """Eine Zahl mit deutschen Tausenderpunkten (nur fuer die Ausgabe)."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def _text(wert) -> str:
    """Ein Feld als Text lesen — Nicht-Text und ``None`` werden zu ``""``."""
    return wert.strip() if isinstance(wert, str) else ""


def _params(params) -> dict:
    """Die Menge-Schwellen als Dict — Vorgaben aus ``MENGEN_PARAMS``.

    Ein ``params``-Dict darf einzelne Werte ersetzen; nur brauchbare Zahlen
    (``>= 0``) werden uebernommen, alles andere faellt still auf die Vorgabe
    zurueck. So kann kein Aufrufer eine Schwelle "aus Versehen" ausschalten.
    """
    werte = dict(MENGEN_PARAMS)
    if isinstance(params, dict):
        for name in MENGEN_PARAMS:
            wert = params.get(name)
            if _ist_zahl(wert) and float(wert) >= 0:
                werte[name] = float(wert)
    return werte


def _vektor_von(eintrag):
    """Den Vektor eines Eintrags lesen — Liste oder Dict mit ``embedding``.

    Akzeptiert direkt eine Zahlenliste (``[0.1, -0.2, …]``) oder ein Dict mit
    dem Feld ``embedding`` (so kommt es aus ``face_infer.py``; ``vektor`` ist
    als zweiter Name erlaubt). Unbrauchbare Werte ergeben ``None`` — es wird
    nicht geraten.
    """
    if isinstance(eintrag, dict):
        gewaehlt = None
        for name in ("embedding", "vektor"):
            wert = eintrag.get(name)
            if isinstance(wert, (list, tuple, np.ndarray)):
                gewaehlt = wert
                break
        if gewaehlt is None:
            return None
        eintrag = gewaehlt
    if isinstance(eintrag, np.ndarray):
        if eintrag.ndim != 1 or eintrag.size == 0:
            return None
        eintrag = eintrag.tolist()
    if not isinstance(eintrag, (list, tuple)) or not eintrag:
        return None
    werte = []
    for wert in eintrag:
        if not _ist_zahl(wert):
            return None
        werte.append(float(wert))
    return werte


def _einheit(vektoren) -> np.ndarray | None:
    """Vektoren als Matrix mit Laenge 1 je Zeile — ``None``, wenn unbrauchbar.

    Nullvektoren bleiben Nullvektoren (ihre Aehnlichkeit ist dann 0, nicht
    "zufaellig 1") — das ist der ehrlichere Wert.
    """
    if not vektoren:
        return None
    try:
        matrix = np.asarray(vektoren, dtype=float)
    except (TypeError, ValueError):
        return None
    if matrix.ndim != 2 or matrix.size == 0:
        return None
    laengen = np.linalg.norm(matrix, axis=1, keepdims=True)
    laengen[laengen == 0] = 1.0
    return matrix / laengen


def cosinus(a, b) -> float:
    """Cosinus-Aehnlichkeit zweier Vektoren — ``0.0`` bei unbrauchbarer Eingabe.

    ``0.0`` ist die neutrale Antwort: ungleich lange Vektoren, Nullvektoren und
    Nicht-Zahlen ergeben keine Aehnlichkeit, aber auch keinen Absturz. Damit
    gilt: ein Treffer braucht wirklich einen Wert ueber der Schwelle.
    """
    links = _vektor_von(a)
    rechts = _vektor_von(b)
    if links is None or rechts is None or len(links) != len(rechts):
        return 0.0
    m = _einheit([links, rechts])
    if m is None:
        return 0.0
    wert = float(np.dot(m[0], m[1]))
    if not math.isfinite(wert):
        return 0.0
    return max(-1.0, min(1.0, wert))


def cosinus_distanz(a, b) -> float:
    """Cosinus-Distanz ``1 - cosinus`` — das Mass des Clusterns."""
    return 1.0 - cosinus(a, b)


def cosinus_matrix(eintraege) -> np.ndarray | None:
    """Die Cosinus-Ähnlichkeitsmatrix aller Eintraege — ``None``, wenn leer.

    Unbrauchbare Eintraege (Dict ohne ``embedding``, Nicht-Zahlen) bekommen
    eine Nullzeile/-spalte: sie sind zu nichts aehnlich und landen damit
    zuverlaessig im Rauschen, statt in irgendeine Gruppe zu rutschen.
    """
    vektoren = [_vektor_von(eintrag) for eintrag in _liste(eintraege)]
    if not vektoren:
        return None
    laenge = None
    for vektor in vektoren:
        if vektor:
            laenge = len(vektor)
            break
    if laenge is None:
        return None
    brauchbar = [vektor if vektor and len(vektor) == laenge else None
                 for vektor in vektoren]
    matrix = _einheit([vektor if vektor else [0.0] * laenge
                       for vektor in brauchbar])
    if matrix is None:
        return None
    aehnlich = matrix @ matrix.T
    for nummer, vektor in enumerate(brauchbar):
        if vektor is None:
            aehnlich[nummer, :] = 0.0
            aehnlich[:, nummer] = 0.0
    return np.clip(aehnlich, -1.0, 1.0)


def _liste(wert) -> list:
    """``wert`` als Liste — alles andere wird zur leeren Liste."""
    return list(wert) if isinstance(wert, (list, tuple)) else []


def _bezugslaenge(eintraege):
    """Die Vektor-Laenge, die die **Mehrheit** der brauchbaren Eintraege hat.

    Brauchbar heisst: ``_vektor_von`` liest eine endliche Zahlenliste. Die
    Mehrheit ist hier die richtige Wahl (nicht der erste Eintrag): ein
    einzelner Vektor mit falscher Laenge darf nicht alle anderen aus dem
    Verfahren kippen. Bei Gleichstand gewinnt die in der Eingabe zuerst
    gesehene Laenge — deterministisch. ``None``, wenn es keinen brauchbaren
    Vektor gibt.
    """
    zaehler: dict = {}
    for eintrag in _liste(eintraege):
        vektor = _vektor_von(eintrag)
        if vektor is None:
            continue
        laenge = len(vektor)
        zaehler[laenge] = zaehler.get(laenge, 0) + 1
    bestes = None
    for laenge in zaehler:                     # Einfuegereihenfolge = Eingabe
        if bestes is None or zaehler[laenge] > zaehler[bestes]:
            bestes = laenge
    return bestes


def _verfahren_waehlen(verfahren) -> str:
    """Den Verfahrensnamen aufloesen — leer/``None`` ergibt ``CLUSTER_VERFAHREN``.

    Ein unbekannter Name ist ein **Fehler** (``ValueError``, deutsche Meldung
    mit den erlaubten Verfahren): es wird nichts stillschweigend auf ein
    anderes Verfahren umgebogen.
    """
    if verfahren is None:
        return CLUSTER_VERFAHREN
    name = _text(verfahren)
    if not name:
        return CLUSTER_VERFAHREN
    if name not in VERFAHREN:
        raise ValueError(f"Unbekanntes Verfahren: {name!r} — erlaubt sind "
                         f"{VERFAHREN_DICHTE!r} und {VERFAHREN_VOLLSTAENDIG!r}.")
    return name


# ── 1. Gesichtsflaeche relativ zum Bild ───────────────────────────────────

def gesichts_anteil(bbox, breite, hoehe) -> float:
    """Anteil der Bildflaeche, den eine ``bbox`` einnimmt (0.0 … 1.0).

    ``bbox`` ist ``[x, y, w, h]`` in absoluten Pixeln. Ungueltige Werte —
    fehlende ``bbox``, falsche Laenge, nicht-numerische Koordinaten/Breite/Hoehe,
    nicht-positive Breite/Hoehe, Bildmasse ``<= 0`` — ergeben ``0.0``. Es wird
    nie geteilt und nie geworfen: ein Foto ohne brauchbare Masse hat einfach
    kein Gesicht, das zaehlt (kein ``ZeroDivisionError``).

    Der Wert wird bei 1.0 gedeckelt: mehr als das ganze Bild kann ein Gesicht
    nicht ausfuellen, auch wenn eine kaputte Box groesser waere.
    """
    if not _ist_zahl(breite) or not _ist_zahl(hoehe):
        return 0.0
    breite = float(breite)
    hoehe = float(hoehe)
    if breite <= 0 or hoehe <= 0:
        return 0.0
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return 0.0
    if any(not _ist_zahl(wert) for wert in bbox):
        return 0.0
    _, _, bbox_breite, bbox_hoehe = bbox
    bbox_breite = float(bbox_breite)
    bbox_hoehe = float(bbox_hoehe)
    if bbox_breite <= 0 or bbox_hoehe <= 0:
        return 0.0
    return min((bbox_breite * bbox_hoehe) / (breite * hoehe), 1.0)


def gesichter_bewerten(gesichter, breite, hoehe, params=None) -> list[dict]:
    """Alle Gesichter eines Bildes anreichern (rein, ohne I/O).

    Je brauchbarem Gesicht ein Eintrag mit ``index`` (Stelle in der Eingabe),
    ``score``, ``anteil``, ``bbox``, ``embedding``, ``nutzbar`` und
    ``erkennbar`` — dazu das Original unter ``gesicht``. Unbrauchbare Eintraege
    (kein Dict, kein Score, keine ``bbox``) fallen weg; es wird nichts geraten.

    ``nutzbar`` = ``score >= min_score`` **und** ``anteil >= anteil_min``
    (``anteil_min`` verwirft nur **entartete** Boxen, nicht Rauschen — das
    Rausch-Tor ist ``min_score``),
    ``erkennbar`` = ``nutzbar`` **und** ``anteil >= anteil_erkennbar``.
    """
    p = _params(params)
    ergebnis: list[dict] = []
    for nummer, gesicht in enumerate(_liste(gesichter)):
        if not isinstance(gesicht, dict):
            continue
        score = gesicht.get("score")
        if not _ist_zahl(score):
            continue
        bbox = gesicht.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        if any(not _ist_zahl(wert) for wert in bbox):
            continue
        anteil = gesichts_anteil(bbox, breite, hoehe)
        nutzbar = (float(score) >= p["min_score"]
                   and anteil >= p["anteil_min"])
        ergebnis.append({
            "index": nummer,
            "score": float(score),
            "anteil": anteil,
            "bbox": [float(wert) for wert in bbox],
            "embedding": gesicht.get("embedding"),
            "nutzbar": nutzbar,
            "erkennbar": nutzbar and anteil >= p["anteil_erkennbar"],
            "gesicht": gesicht,
        })
    ergebnis.sort(key=lambda eintrag: (eintrag["index"],))
    return ergebnis


# ── 2. Die Art eines Bildes: leer / gruppe / menge / unklar ───────────────

def bild_art(gesichter, breite, hoehe, params=None) -> str:
    """``"leer" | "gruppe" | "menge" | "unklar"`` — die Mengen-Entscheidung.

    Regel (jede Grenze ist eine benannte Konstante in diesem Modul):

      * ``nutzbar`` = ``score >= MIN_SCORE`` und ``anteil >= ANTEIL_MIN``;
      * ``erkennbar`` = ``nutzbar`` und ``anteil >= ANTEIL_ERKENNBAR``;
      * ``leer`` = **kein** nutzbares Gesicht (auch bei kaputter Bildmasse);
      * ``gruppe`` = mindestens **ein** erkennbares Gesicht — ein
        Vordergrund-Gesicht macht das Bild zu einem Personen-Foto;
      * ``menge`` = ``anzahl >= MENGE_ANZAHL`` nutzbare Gesichter **und kein**
        erkennbares — die Menschenmenge weit weg;
      * ``unklar`` = alles andere (z. B. drei kleine Gesichter): **wird nicht
        geclustert**. Die Regel des Auftrags heisst "im Zweifel weglassen,
        nichts anlernen" — deshalb ist ``unklar`` keine vierte Gruppe, sondern
        ein Nicht-Ergebnis.

    Warum der Flaechenanteil und nicht die Pixelzahl: siehe die Konstanten
    oben — dieselbe Schwelle soll fuer 12-MP-Handyfotos, Scans und Crops gelten.
    """
    p = _params(params)
    bewertet = gesichter_bewerten(gesichter, breite, hoehe, p)
    nutzbar = [eintrag for eintrag in bewertet if eintrag["nutzbar"]]
    if not nutzbar:
        return ART_LEER
    if any(eintrag["erkennbar"] for eintrag in nutzbar):
        return ART_GRUPPE
    if len(nutzbar) >= p["menge_anzahl"]:
        return ART_MENGE
    return ART_UNKLAR


def vordergrund_gesichter(gesichter, breite, hoehe, params=None) -> list[dict]:
    """Die **erkennbaren** Gesichter, absteigend nach Flaechenanteil.

    Das ist die "Vordergrund"-Definition der Mengen-Regel: erkennbar gross.
    Sortiert wird nach ``(-anteil, -score, index)`` — zuerst das groesste
    Gesicht, bei gleicher Flaeche das sichere, bei Gleichstand die Reihenfolge
    der Eingabe. Damit ist die Liste reproduzierbar.
    """
    p = _params(params)
    erkennbar = [eintrag for eintrag in gesichter_bewerten(gesichter, breite,
                                                           hoehe, p)
                 if eintrag["erkennbar"]]
    erkennbar.sort(key=lambda eintrag: (-eintrag["anteil"], -eintrag["score"],
                                        eintrag["index"]))
    return erkennbar


def nutzbare_gesichter(gesichter, breite, hoehe, params=None) -> list[dict]:
    """Die nutzbaren Gesichter (``score``/``anteil`` reichen) — Eingabereihenfolge."""
    p = _params(params)
    return [eintrag for eintrag in gesichter_bewerten(gesichter, breite, hoehe, p)
            if eintrag["nutzbar"]]


# ── 3. Katalog-Treffer (ist eine bekannte Person im Vordergrund?) ─────────

def katalog_personen(katalog) -> list[dict]:
    """Die Personen eines Katalogs lesen und pruefen — nur brauchbare bleiben.

    Akzeptiert ``{"personen": [...]}`` oder direkt eine Liste. Je Person:
    ``kennung`` (nicht leerer Text), ``name`` (Text oder ``None``) und
    ``vektoren`` (Liste von Vektoren; ein einzelnes Feld ``vektor`` gilt als
    Ein-Element-Liste). Personen ohne brauchbaren Vektor fallen weg — es wird
    nichts geraten.
    """
    if isinstance(katalog, dict):
        personen = katalog.get("personen")
    else:
        personen = katalog
    ergebnis: list[dict] = []
    for person in _liste(personen):
        if not isinstance(person, dict):
            continue
        kennung = _text(person.get("kennung"))
        if not kennung:
            continue
        roh = person.get("vektoren")
        if roh is None and person.get("vektor") is not None:
            roh = [person.get("vektor")]
        vektoren = [vektor for vektor in (_vektor_von(eintrag)
                                          for eintrag in _liste(roh))
                    if vektor is not None]
        if not vektoren:
            continue
        name = person.get("name")
        ergebnis.append({"kennung": kennung,
                         "name": name if isinstance(name, str) and name.strip()
                         else None,
                         "vektoren": vektoren})
    return ergebnis


def katalog_treffer(gesichter, katalog, schwelle: float = KATALOG_SCHWELLE) -> list[dict]:
    """Wen aus dem Katalog zeigen diese Gesichter? — ``[{kennung, name, score}]``.

    Verglichen wird per Cosinus-Aehnlichkeit gegen **alle** Katalog-Vektoren;
    je Person zaehlt der **beste** Treffer. Standard-Schwelle ist
    ``KATALOG_SCHWELLE`` (0.363 — der OpenCV-Standardwert fuer SFace: Cosinus
    ab 0.363 gilt als dieselbe Person).

    Ergebnis: am aehnlichsten zuerst (``-score``, dann ``kennung``), je
    ``kennung`` hoechstens ein Eintrag. Der ``name`` wird mitgeliefert, aber
    nie auf die Konsole geschrieben und nie gespeichert.
    """
    personen = katalog_personen(katalog)
    if not personen:
        return []
    if not _ist_zahl(schwelle):
        schwelle = KATALOG_SCHWELLE
    schwelle = float(schwelle)
    gesichts_vektoren = [vektor for vektor in (_vektor_von(eintrag)
                                               for eintrag in _liste(gesichter))
                         if vektor is not None]
    if not gesichts_vektoren:
        return []

    beste_je_kennung: dict[str, dict] = {}
    for person in personen:
        bestwert = None
        for katalog_vektor in person["vektoren"]:
            for gesichts_vektor in gesichts_vektoren:
                if len(katalog_vektor) != len(gesichts_vektor):
                    continue
                wert = cosinus(gesichts_vektor, katalog_vektor)
                if bestwert is None or wert > bestwert:
                    bestwert = wert
        if bestwert is None or bestwert < schwelle:
            continue
        vorher = beste_je_kennung.get(person["kennung"])
        if vorher is not None and vorher["score"] >= bestwert:
            continue
        beste_je_kennung[person["kennung"]] = {"kennung": person["kennung"],
                                               "name": person["name"],
                                               "score": bestwert}

    treffer = list(beste_je_kennung.values())
    treffer.sort(key=lambda eintrag: (-eintrag["score"], eintrag["kennung"]))
    return treffer


# ── 4. Die Kernentscheidung je Bild ───────────────────────────────────────

def bild_entscheidung(bild, katalog=None, params=None) -> dict:
    """Clustern: ja oder nein? — die Entscheidung je Bild, mit Klartext-Grund.

    Rueckgabe (immer dieselben Felder, **ohne** Nebenwirkung — kein Dateizugriff)::

        {"bild_id", "art", "anzahl_nutzbar", "anzahl_erkennbar",
         "clustern", "personen", "grund"}

    Regelwerk (so umgesetzt, nicht anders):

      * ``menge`` **ohne** bekannten Vordergrund -> ``clustern: False``,
        ``grund: "menge_ohne_bekannte_person"`` — die Pflichtpruefung des
        Plans: Menschenmengen werden nicht angelernt.
      * ``menge`` **mit** bekannter Vordergrund-Person -> ``clustern: True``,
        ``personen: [<bekannt>]``, ``grund: "menge_mit_bekannter_person"``.
      * ``gruppe`` -> ``clustern: True``, ``grund: "gruppe"``.
      * ``unklar``/``leer`` -> ``clustern: False``.

    ``personen`` sind die Kennungen aus dem Katalog, die im **Vordergrund**
    gefunden wurden — nie Namen. Bei ``art == "menge"`` wird der Katalog gegen
    **alle nutzbaren** Gesichter geprueft (nicht nur die erkennbaren): genau das
    ist die Vordergrund-Pruefung der Mengen-Regel — erkennt der Katalog eine
    bekannte Person in der Aufnahme, ist es ein Foto dieser Person und keine
    namenlose Menge. Ohne Katalog-Treffer bleibt die Menge unangelernt.
    """
    daten = bild if isinstance(bild, dict) else {}
    p = _params(params)
    bild_id = daten.get("bild_id")
    bild_id = str(bild_id).strip() if isinstance(bild_id, (str, int)) \
        and not isinstance(bild_id, bool) else ""
    breite = daten.get("breite")
    hoehe = daten.get("hoehe")
    gesichter = daten.get("gesichter")

    art = bild_art(gesichter, breite, hoehe, p)
    bewertet = gesichter_bewerten(gesichter, breite, hoehe, p)
    anzahl_nutzbar = sum(1 for eintrag in bewertet if eintrag["nutzbar"])
    vordergrund = [eintrag for eintrag in bewertet if eintrag["erkennbar"]]
    if art == ART_MENGE:
        pruefflaeche = [eintrag for eintrag in bewertet if eintrag["nutzbar"]]
    else:
        pruefflaeche = vordergrund
    treffer = katalog_treffer(pruefflaeche, katalog, p["katalog_schwelle"])
    personen = [eintrag["kennung"] for eintrag in treffer]

    if art == ART_MENGE:
        if personen:
            clustern = True
            grund = GRUND_MENGE_MIT
        else:
            clustern = False
            grund = GRUND_MENGE_OHNE
    elif art == ART_GRUPPE:
        clustern = True
        grund = GRUND_GRUPPE
    elif art == ART_LEER:
        clustern = False
        grund = GRUND_LEER
    else:
        clustern = False
        grund = GRUND_UNKLAR

    return {
        "bild_id": bild_id,
        "art": art,
        "anzahl_nutzbar": anzahl_nutzbar,
        "anzahl_erkennbar": len(vordergrund),
        "clustern": bool(clustern),
        "personen": personen,
        "grund": grund,
    }


# ── 5. Clustern ohne sklearn (nur numpy) ─────────────────────────────────

def vollstaendig_clustern(eintraege, schwelle: float = CLUSTER_SCHWELLE,
                          min_groesse: int = CLUSTER_MIN_NACHBAR) -> list[list[int]]:
    """Agglomerative **Complete-Linkage** — nur mit numpy, ohne sklearn.

    **Invariante dieses Verfahrens:** der Durchmesser **jeder** zurueck-
    gegebenen Gruppe ist ``<= schwelle`` (Durchmesser = groesster Cosinus-
    Abstand zweier Mitglieder).

    Ablauf: jeder **brauchbare** Eintrag startet als eigene Gruppe; dann wird
    solange das Paar mit dem kleinsten **Complete-Linkage-Abstand** verschmolzen,
    wie dieser ``<= schwelle`` ist. Der Complete-Linkage-Abstand zweier Gruppen
    ist das **Maximum** der Punktabstaende aller Paare ueber beide Gruppen — es
    zaehlt also das weiteste Punktpaar, nicht das naechste. Genau das verbietet
    die Verkettung des Dichte-Verfahrens: dort genuegt eine Kette naher
    Nachbarn (A-B nah, B-C nah), hier kommen A und C nur zusammen, wenn auch
    ``distanz(A, C) <= schwelle`` gilt.

    **Determinismus:** die Gruppen starten in Eingabereihenfolge; gesucht wird
    zeilenweise (Zeile zuerst, dann Spalte) nach dem ersten kleinsten Wert —
    der erste kleinste gewinnt. Die verschmolzene Gruppe bleibt an der Stelle
    der **ersten** beteiligten Gruppe stehen. Zweimal derselbe Aufruf ergibt
    dieselbe Liste.

    ``min_groesse``: Gruppen mit weniger Mitgliedern sind **Rauschen** und
    werden verworfen (nicht in eine fremde Gruppe gedraengt). Brauchbar heisst:
    der Eintrag hat einen Vektor in der **Mehrheits**-Laenge
    (``_bezugslaenge``); alles andere kommt in keiner Gruppe vor.

    Rueckgabe: Liste von Index-Listen der Eingabe (jede Liste aufsteigend
    sortiert, Gruppen in Erzeugungsreihenfolge). Leerer Eingang oder keine
    brauchbaren Vektoren -> ``[]``.
    """
    alle = _liste(eintraege)
    if not alle:
        return []
    if not _ist_zahl(schwelle):
        schwelle = CLUSTER_SCHWELLE
    grenze = max(0.0, float(schwelle))
    if not _ist_zahl(min_groesse):
        min_groesse = CLUSTER_MIN_NACHBAR
    kleinste = max(1, int(min_groesse))

    laenge = _bezugslaenge(alle)
    if laenge is None:
        return []
    indizes: list[int] = []
    vektoren: list[list[float]] = []
    for nummer, eintrag in enumerate(alle):
        vektor = _vektor_von(eintrag)
        if vektor is None or len(vektor) != laenge:
            continue
        indizes.append(nummer)
        vektoren.append(vektor)
    if not vektoren:
        return []
    einheit = _einheit(vektoren)
    if einheit is None:
        return []
    aehnlich = np.clip(einheit @ einheit.T, -1.0, 1.0)
    abstand = np.clip(1.0 - aehnlich, 0.0, 2.0)

    gruppen = [[nummer] for nummer in indizes]
    anzahl = len(gruppen)
    # Distanzmatrix der Gruppen: am Anfang sind das die Punktabstaende.
    distanz = np.array(abstand, dtype=float, copy=True)
    np.fill_diagonal(distanz, np.inf)

    while anzahl > 1:
        # Nur das obere Dreieck zaehlt — sonst waere jedes Paar doppelt da.
        sichtbar = np.where(np.triu(np.ones((anzahl, anzahl), dtype=bool), 1),
                            distanz, np.inf)
        stelle = int(np.argmin(sichtbar))
        a, b = divmod(stelle, anzahl)
        if sichtbar[a, b] > grenze:
            break                                # nichts mehr zu verschmelzen
        gruppen[a] = sorted(gruppen[a] + gruppen[b])
        # Complete-Linkage: das WEITESTE Punktpaar beider Gruppen zaehlt.
        neu = np.maximum(distanz[a, :], distanz[b, :])
        neu[a] = np.inf
        neu[b] = np.inf
        distanz[a, :] = neu
        distanz[:, a] = neu
        gruppen.pop(b)
        distanz = np.delete(np.delete(distanz, b, axis=0), b, axis=1)
        anzahl -= 1

    return [gruppe for gruppe in gruppen if len(gruppe) >= kleinste]


def vektoren_clustern(eintraege, schwelle: float = CLUSTER_SCHWELLE,
                      min_nachbarn: int = CLUSTER_MIN_NACHBAR,
                      verfahren: str | None = None) -> list[list[int]]:
    """Vektoren zu Gruppen buendeln — Dichte-Verfahren oder Complete-Linkage.

    ``verfahren`` waehlt das Verfahren: ``"dichte"`` ist das Bestandsverfahren
    (DBSCAN-artig, Expansion vom Kernpunkt), ``"vollstaendig"`` ist die
    agglomerative Complete-Linkage (:func:`vollstaendig_clustern`). Ohne Angabe
    (``None`` oder ``""``) gilt der Produktionsstandard ``CLUSTER_VERFAHREN`` —
    die **vollstaendige Verknuepfung**.

    ``min_nachbarn`` meint in **beiden** Verfahren dieselbe **Untergrenze**,
    wirkt aber unterschiedlich:

      * ``dichte``: ein **Kernpunkt** braucht mindestens so viele Nachbarn im
        Abstand ``<= schwelle`` (sich selbst mitgezaehlt); nur von Kernpunkten
        wird expandiert.
      * ``vollstaendig``: dieselbe Zahl ist die **Mindestgruppengroesse** —
        kleinere Gruppen sind Rauschen und werden verworfen. Die Dichte-Grenze
        steckt hier allein in ``schwelle`` (Complete-Linkage).

    Ein unbekanntes Verfahren ergibt ``ValueError`` mit deutscher Meldung; es
    faellt nichts still auf ein anderes Verfahren zurueck.

    Gemeinsam fuer beide Verfahren: Abstand ist die Cosinus-Distanz
    (``1 - cosinus``); **Rauschpunkte** landen in keiner Gruppe, statt in eine
    hineingedraengt zu werden (aus Rauschen soll keine Referenzseite
    entstehen). Determinismus: die Eingabereihenfolge bestimmt die
    Gruppen-Reihenfolge, eine Gruppe enthaelt die **Indizes der Eingabe**,
    aufsteigend sortiert. Leerer Eingang oder zu wenige Vektoren -> ``[]``.

    Beim **vollstaendigen** Verfahren gilt zusaetzlich die Invariante: der
    Durchmesser jeder Gruppe ist ``<= schwelle``. Das **dichte** Verfahren
    verknuepft transitiv und kann die Schwelle reissen (gemessen bei Schwelle
    0,45: Durchmesser bis 0.9032 = 2 x Schwelle) — deshalb ist es nicht mehr
    der Produktionsstandard.
    """
    alle = _liste(eintraege)
    gewaehlt = _verfahren_waehlen(verfahren)
    if not alle:
        return []
    if not _ist_zahl(schwelle):
        schwelle = CLUSTER_SCHWELLE
    schwelle = float(schwelle)
    if not _ist_zahl(min_nachbarn):
        min_nachbarn = CLUSTER_MIN_NACHBAR
    min_nachbarn = max(1, int(min_nachbarn))

    if gewaehlt == VERFAHREN_VOLLSTAENDIG:
        # Complete-Linkage: ``min_nachbarn`` ist hier die Mindestgruppengroesse.
        return [list(gruppe) for gruppe in
                vollstaendig_clustern(alle, schwelle, min_nachbarn)]

    aehnlich = cosinus_matrix(alle)
    if aehnlich is None:
        return []
    abstand = 1.0 - aehnlich

    # Nur Eintraege mit brauchbarem Vektor kommen als Punkt infrage.
    gueltig = [nummer for nummer, eintrag in enumerate(alle)
               if _vektor_von(eintrag) is not None]
    if len(gueltig) < min_nachbarn:
        return []

    nachbarn: dict[int, list[int]] = {}
    kernpunkte: list[int] = []
    for nummer in gueltig:
        umgebung = [andere for andere in gueltig
                    if abstand[nummer, andere] <= schwelle]
        nachbarn[nummer] = umgebung
        if len(umgebung) >= min_nachbarn:
            kernpunkte.append(nummer)

    besucht: set[int] = set()
    gruppen: list[list[int]] = []
    for start in kernpunkte:
        if start in besucht:
            continue
        besucht.add(start)
        gruppe = [start]
        warteschlange = list(nachbarn[start])
        while warteschlange:
            punkt = warteschlange.pop(0)
            if punkt in besucht:
                continue
            besucht.add(punkt)
            gruppe.append(punkt)
            if punkt in nachbarn and len(nachbarn[punkt]) >= min_nachbarn:
                for weiterer in nachbarn[punkt]:
                    if weiterer not in besucht:
                        warteschlange.append(weiterer)
        gruppen.append(sorted(gruppe))
    return gruppen


# ── 6. Stabile Kennungen gegen den Altbestand ─────────────────────────────

def altbestand_lesen(altbestand) -> list[dict]:
    """Den Kennungs-Altbestand lesen — ``[{kennung, mittelpunkt}]``.

    Akzeptiert eine Liste oder ``{"kennungen": [...]}``. Je Eintrag muessen
    ``kennung`` (Text) und ``mittelpunkt`` (brauchbarer Vektor) da sein;
    unbrauchbare Eintraege fallen weg. Mehrfach genannte Kennungen zaehlen
    einmal (der erste Eintrag gewinnt) — eine Kennung ist eine Person.
    """
    if isinstance(altbestand, dict):
        eintraege = altbestand.get("kennungen")
    else:
        eintraege = altbestand
    gesehen: set[str] = set()
    ergebnis: list[dict] = []
    for eintrag in _liste(eintraege):
        if not isinstance(eintrag, dict):
            continue
        kennung = _text(eintrag.get("kennung"))
        mittelpunkt = _vektor_von({"embedding": eintrag.get("mittelpunkt")})
        if not kennung or mittelpunkt is None or kennung in gesehen:
            continue
        gesehen.add(kennung)
        ergebnis.append({"kennung": kennung, "mittelpunkt": mittelpunkt})
    return ergebnis


def _naechste_nummer(kennungen) -> int:
    """Die hoechste vergebene Nummer — neue Kennungen setzen dahinter fort.

    Nummern werden **nie wiederverwendet** (Luecken sind erlaubt): selbst eine
    verschwundene Kennung bleibt in der Zaehlung, damit ihre Nummer nicht an
    eine andere Gruppe faellt.

    Erwartet eine **Liste** (der Aufrufer uebergibt eine sortierte Liste, nicht
    das ``set`` — eine Mengen-Reihenfolge waere hier zwar fuer das Maximum
    egal, aber der Aufruf soll lesbar bleiben).
    """
    hoechste = 0
    for kennung in _liste(kennungen):
        if not isinstance(kennung, str):
            continue
        if kennung.startswith("Person_"):
            rest = kennung[len("Person_"):]
            if rest.isdigit():
                hoechste = max(hoechste, int(rest))
    return hoechste


def gruppen_kennungen(gruppen, eintraege, altbestand=None,
                      schwelle: float = ALT_SCHWELLE) -> list[dict]:
    """Jeder Gruppe eine **stabile** Kennung geben — ``Person_001`` … .

    Fuer jede Gruppe wird der Mittelpunkt (Schwerpunkt der Vektoren) gebildet
    und per Cosinus gegen den **Altbestand** geprueft: passt er (``>= schwelle``)
    auf eine vorhandene Kennung, **bleibt** diese Kennung. Sonst vergibt das
    Werkzeug die naechste freie ``Person_<NNN>`` — Nummern werden nie
    wiederverwendet, Luecken sind erlaubt.

    **Idempotenz:** zweimal mit demselben Altbestand aufgerufen kommt dieselbe
    Kennung heraus. Dafuer zaehlt jede Kennung nur **einmal** je Lauf (die erste
    passende Gruppe gewinnt); die Gruppen werden in der uebergebenen Reihenfolge
    abgearbeitet — beides deterministisch.

    Rueckgabe je Gruppe: ``{"kennung", "neu", "gruppe", "groesse", "treffer",
    "mittelpunkt", "indizes"}``. ``mittelpunkt`` ist genau das, was der
    naechste Lauf als Altbestand braucht (siehe ``altbestand_bauen``).
    """
    alle = _liste(eintraege)
    if not _ist_zahl(schwelle):
        schwelle = ALT_SCHWELLE
    schwelle = float(schwelle)
    bekannt = altbestand_lesen(altbestand)
    vergeben = {eintrag["kennung"] for eintrag in bekannt}
    hoechste = _naechste_nummer(sorted(vergeben))
    benutzt: set[str] = set()              # Altbestand-Kennungen dieses Laufs

    ergebnis: list[dict] = []
    for nummer, gruppe in enumerate(_liste(gruppen)):
        indizes = [int(index) for index in _liste(gruppe)
                   if _ist_zahl(index) and 0 <= int(index) < len(alle)]
        if not indizes:
            continue
        vektoren = [vektor for vektor in (_vektor_von(alle[index])
                                          for index in indizes)
                    if vektor is not None]
        if not vektoren:
            continue
        laenge = len(vektoren[0])
        passend = [vektor for vektor in vektoren if len(vektor) == laenge]
        mittelpunkt = np.mean(np.asarray(passend, dtype=float), axis=0)
        treffer_wert = None
        beste_kennung = None
        eigen = [float(wert) for wert in mittelpunkt]
        for eintrag in bekannt:
            if eintrag["kennung"] in benutzt:
                continue                      # je Lauf nur einmal vergeben
            if len(eintrag["mittelpunkt"]) != len(mittelpunkt):
                continue
            wert = cosinus(eigen, eintrag["mittelpunkt"])
            if beste_kennung is None or wert > treffer_wert:
                beste_kennung = eintrag["kennung"]
                treffer_wert = wert
        if beste_kennung is not None and treffer_wert >= schwelle:
            kennung = beste_kennung
            benutzt.add(kennung)
            neu = False
        else:
            hoechste += 1
            kennung = KENNUNG_MUSTER % hoechste
            neu = True
        vergeben.add(kennung)
        ergebnis.append({
            "kennung": kennung,
            "neu": bool(neu),
            "gruppe": nummer,
            "groesse": len(indizes),
            "treffer": treffer_wert,
            "mittelpunkt": [float(wert) for wert in mittelpunkt],
            "indizes": indizes,
        })
    return ergebnis


def altbestand_bauen(kennungen) -> list[dict]:
    """Aus ``gruppen_kennungen`` den Altbestand fuer den naechsten Lauf bauen."""
    ergebnis: list[dict] = []
    for eintrag in _liste(kennungen):
        if not isinstance(eintrag, dict):
            continue
        kennung = _text(eintrag.get("kennung"))
        mittelpunkt = _vektor_von({"embedding": eintrag.get("mittelpunkt")})
        if not kennung or mittelpunkt is None:
            continue
        ergebnis.append({"kennung": kennung, "mittelpunkt": mittelpunkt})
    return ergebnis


# ── 7. Eintraege einer Gruppe fuer die Referenzseite ──────────────────────

def gruppen_eintraege_bauen(gruppen, eintraege, kennungen) -> list[dict]:
    """``[{kennung, eintraege}]`` je Gruppe — die Eingabe der Referenzseiten.

    Die Zuordnung laeuft ueber ``kennungen[i]["gruppe"]`` (nicht ueber die
    Reihenfolge), damit sie auch bei gefilterten Gruppen stimmt. Je Gruppe
    kommen die Veraenderungen (Kacheln) in der Reihenfolge der Eintraege — die
    Auswahl der besten Kacheln macht ``referenzseiten_bauen``.
    """
    alle = _liste(eintraege)
    nach_gruppe: dict[int, str] = {}
    for eintrag in _liste(kennungen):
        if isinstance(eintrag, dict) and _ist_zahl(eintrag.get("gruppe")):
            nach_gruppe[int(eintrag["gruppe"])] = _text(eintrag.get("kennung"))
    ergebnis: list[dict] = []
    for nummer, gruppe in enumerate(_liste(gruppen)):
        kennung = nach_gruppe.get(nummer)
        if not kennung:
            continue
        gewaehlt = [alle[index] for index in _liste(gruppe)
                    if _ist_zahl(index) and 0 <= int(index) < len(alle)]
        ergebnis.append({"kennung": kennung, "eintraege": gewaehlt})
    return ergebnis


def _kachel_rang(eintrag) -> tuple:
    """Sortierschluessel einer Kachel: groesster Flaechenanteil, dann Score."""
    anteil = eintrag.get("anteil") if isinstance(eintrag, dict) else None
    score = eintrag.get("score") if isinstance(eintrag, dict) else None
    bild_id = eintrag.get("bild_id") if isinstance(eintrag, dict) else None
    return (-(anteil if _ist_zahl(anteil) else 0.0),
            -(score if _ist_zahl(score) else 0.0),
            str(bild_id or ""))


def kacheln_sortieren(eintraege) -> list[dict]:
    """Die Eintraege einer Gruppe fuer die Seite ordnen (beste Kachel zuerst).

    Reihenfolge des Auftrags: **groesster Flaechenanteil**, dann **Score**,
    dann ``bild_id`` (macht die Reihenfolge bei Gleichstand reproduzierbar).
    """
    return sorted([eintrag for eintrag in _liste(eintraege)
                   if isinstance(eintrag, dict)], key=_kachel_rang)


def seiten_dateiname(kennung, seite: int = 1) -> str:
    """Der Dateiname einer Referenzseite: ``Person_001_seite_01.jpg``."""
    return f"{_text(kennung) or 'Person_000'}_seite_{max(1, int(seite)):02d}.jpg"


# ── 8. Schutz: nur ausserhalb des Repos schreiben ─────────────────────────

def pruefe_ausserhalb_repo(pfad: str) -> str:
    """Sicherstellen, dass ein Ausgabeziel AUSSERHALB des Repos liegt.

    Biometrie (Vektoren, Katalog, Referenzseiten) gehoert nie ins Repo — und
    ein Repo-Schreibversuch ist ein Fehler, kein stiller Schreibvorgang. Geprueft
    wird der absolut aufgeloeste Pfad (Gross-/Kleinschreibung und Schraeg-/
    Rueckwaertsstriche ohne Bedeutung). Liegt das Ziel im Repo, gibt es eine
    deutsche Klartextmeldung und ``SystemExit(2)``.
    """
    if not isinstance(pfad, str) or not pfad.strip():
        raise PersonenFehler("Kein Ausgabeordner angegeben.")
    ziel = os.path.normcase(os.path.abspath(pfad))
    repo = os.path.normcase(os.path.abspath(REPO))
    try:
        gemeinsam = os.path.commonpath([ziel, repo])
    except ValueError:                       # anderes Laufwerk: nie im Repo
        return pfad
    if gemeinsam == repo:
        print(f"Ausgabe liegt IM Repo und ist nicht erlaubt: {pfad}\n"
              "Vektoren, Katalog und Referenzseiten gehoeren ausserhalb des "
              f"Repos (Standard: {STANDARD_BASIS}); es wird NICHTS geschrieben.")
        raise SystemExit(2)
    return pfad


# ── 9. Referenzseiten (eingesteckte Kachelquelle) ─────────────────────────

def _kachelbild(hoehe, breite):
    return Image.new("RGB", (int(breite), int(hoehe)), PLATZHALTER_FARBE)


def _platzhalter(kennung, breite, hoehe) -> Image.Image:
    """Ein beschrifteter Platzhalter, wenn ``kachel_holen`` ``None`` liefert.

    Er traegt bewusst **keine** Nummer und Kennung: die stehen unter der Kachel
    (dort auch bei einem echten Kachelbild). So ist die Beschriftung einer Seite
    an genau einer Stelle und nicht doppelt.
    """
    bild = _kachelbild(hoehe, breite)
    zeichner = ImageDraw.Draw(bild)
    zeichner.rectangle([0, 0, int(breite) - 1, int(hoehe) - 1],
                       outline=PLATZHALTER_RAND)
    schrift = ImageFont.load_default()
    zeichner.text((6, 6), PLATZHALTER_TEXT, fill=TEXT_FARBE, font=schrift)
    zeichner.text((6, 24), kennung, fill=TEXT_FARBE, font=schrift)
    return bild


def _kachel_pruefen(rohdaten, breite, hoehe):
    """Rohdaten (Bytes) zu einem Kachelbild in Seitengroesse — sonst ``None``."""
    if not isinstance(rohdaten, (bytes, bytearray)) or not rohdaten:
        return None
    try:
        with Image.open(io.BytesIO(bytes(rohdaten))) as quelle:
            return quelle.convert("RGB").resize((int(breite), int(hoehe)))
    except Exception:
        return None


def referenzseiten_planen(gruppen_eintraege, ausgabe_ordner=None,
                          kacheln_je_seite: int = KACHELN_JE_SEITE,
                          erneut: bool = False) -> list[str]:
    """Die Dateien nennen, die ``referenzseiten_bauen`` anlegen wuerde (rein).

    Fuer den Trockenlauf: dieselben Namen, dieselbe Auswahl, aber **ohne** I/O
    und ohne Zwischenspeicher — hier wird nichts geschrieben und nichts geholt.
    Bereits vorhandene Dateien stehen nur mit ``erneut=True`` in der Liste.
    """
    ordner = ausgabe_ordner if isinstance(ausgabe_ordner, str) else ""
    namen: list[str] = []
    for gruppe in _liste(gruppen_eintraege):
        if not isinstance(gruppe, dict):
            continue
        kennung = _text(gruppe.get("kennung"))
        if not kennung:
            continue
        anzahl = len(kacheln_sortieren(gruppe.get("eintraege")))
        if anzahl <= 0:
            continue
        seiten = max(1, math.ceil(anzahl / max(1, int(kacheln_je_seite))))
        for seite in range(1, seiten + 1):
            pfad = os.path.join(ordner, seiten_dateiname(kennung, seite))
            if not erneut and ordner and os.path.isfile(pfad):
                continue
            namen.append(pfad)
    return namen


def referenzseiten_bauen(gruppen_eintraege, kachel_holen=None,
                         ausgabe_ordner=None,
                         kacheln_je_seite: int = KACHELN_JE_SEITE,
                         erneut: bool = False,
                         kachel_breite: int = KACHEL_BREITE,
                         kachel_hoehe: int = KACHEL_HOEHE,
                         spalten: int = KACHEL_SPALTEN) -> list[str]:
    """Je Gruppe eine Kontaktseite bauen — gibt die geschriebenen Dateien zurueck.

    ``gruppen_eintraege`` ist ``[{kennung, eintraege}]`` (siehe
    ``gruppen_eintraege_bauen``). Die besten Kacheln kommen in der Reihenfolge
    "groesster Flaechenanteil, dann Score"; je Seite sind es
    ``kacheln_je_seite`` (Standard 8) in ``spalten`` Spalten. Jede Kachel ist
    mit **Nummer und Kennung** beschriftet, damit der Nutzer die Gruppe
    wiedererkennt und benennen kann.

    ``kachel_holen(eintrag) -> bytes | None`` ist **eingesteckt**: die Funktion
    holt das Kachelbild (spaeter pCloud-Download bzw. Handy-Crop, in Tests
    synthetische Bytes). Liefert sie ``None`` (oder kippt sie um, oder sind die
    Bytes kein lesbares Bild), entsteht ein beschrifteter **Platzhalter** —
    kein Abbruch. Ohne ``kachel_holen`` besteht die Seite ganz aus Platzhaltern;
    so bleibt das Verfahren auch ohne Bildquelle benutzbar und offline pruefbar.

    **Idempotent:** eine vorhandene Datei wird uebersprungen (nicht neu
    geschrieben), ausser ``erneut=True``. Geschrieben wird nur **ausserhalb**
    des Repos (``pruefe_ausserhalb_repo``).
    """
    if not isinstance(ausgabe_ordner, str) or not ausgabe_ordner.strip():
        raise PersonenFehler("Kein Ausgabeordner angegeben.")
    pruefe_ausserhalb_repo(ausgabe_ordner)
    holen = kachel_holen if callable(kachel_holen) else None
    je_seite = max(1, int(kacheln_je_seite)) if _ist_zahl(kacheln_je_seite) \
        else KACHELN_JE_SEITE
    spalten = max(1, int(spalten)) if _ist_zahl(spalten) else KACHEL_SPALTEN
    kachel_breite = int(kachel_breite) if _ist_zahl(kachel_breite) and \
        kachel_breite >= 1 else KACHEL_BREITE
    kachel_hoehe = int(kachel_hoehe) if _ist_zahl(kachel_hoehe) and \
        kachel_hoehe >= 1 else KACHEL_HOEHE
    gesamt_hoehe = kachel_hoehe + BESCHRIFTUNG_HOEHE

    os.makedirs(ausgabe_ordner, exist_ok=True)
    geschrieben: list[str] = []

    for gruppe in _liste(gruppen_eintraege):
        if not isinstance(gruppe, dict):
            continue
        kennung = _text(gruppe.get("kennung"))
        if not kennung:
            continue
        besetzung = kacheln_sortieren(gruppe.get("eintraege"))
        if not besetzung:
            continue
        seiten = max(1, math.ceil(len(besetzung) / je_seite))
        for seite in range(1, seiten + 1):
            pfad = os.path.join(ausgabe_ordner, seiten_dateiname(kennung, seite))
            if not erneut and os.path.isfile(pfad):
                continue                      # zweiter Lauf: nichts zu tun
            scheibe = besetzung[(seite - 1) * je_seite:seite * je_seite]
            zeilen = max(1, math.ceil(len(scheibe) / spalten))
            seite_bild = Image.new(
                "RGB", (spalten * kachel_breite, zeilen * gesamt_hoehe),
                SEITEN_HINTERGRUND)
            for nummer, eintrag in enumerate(scheibe, start=1):
                rohdaten = None
                if holen is not None:
                    try:
                        rohdaten = holen(eintrag)
                    except Exception:
                        rohdaten = None       # eine kaputte Kachel bricht nichts
                kachel = _kachel_pruefen(rohdaten, kachel_breite, kachel_hoehe)
                if kachel is None:
                    kachel = _platzhalter(kennung, kachel_breite, kachel_hoehe)
                spalte = (nummer - 1) % spalten
                zeile = (nummer - 1) // spalten
                links = spalte * kachel_breite
                oben = zeile * gesamt_hoehe
                seite_bild.paste(kachel, (links, oben))
                zeichner = ImageDraw.Draw(seite_bild)
                zeichner.text((links + 4, oben + kachel_hoehe + 2),
                              f"{nummer}. {kennung}", fill=TEXT_FARBE,
                              font=ImageFont.load_default())
            seite_bild.save(pfad, format="JPEG", quality=88)
            geschrieben.append(pfad)
    return geschrieben


# ── 10. Vektordatei und Katalog lesen ────────────────────────────────────

def zeile_pruefen(zeile) -> dict | None:
    """Eine JSONL-Zeile pruefen — brauchbares Bild-Dict oder ``None``.

    Erwartet genau das Eingabe-Format des Auftrags: ``bild_id`` (Text/Zahl),
    ``breite``/``hoehe`` (Zahlen ``> 0``), ``gesichter`` (Liste), je Gesicht
    ``bbox`` mit vier Zahlen und positiver Breite/Hoehe, ``score`` als Zahl und
    ``embedding`` mit ``MERKMAL_LAENGE`` Werten. Fehlt oder krumm ist etwas
    davon, kommt ``None`` zurueck — die Zeile wird gezaehlt, nicht geraten.
    """
    if not isinstance(zeile, dict):
        return None
    kennung = zeile.get("bild_id")
    if isinstance(kennung, bool) or not isinstance(kennung, (str, int)):
        return None
    bild_id = str(kennung).strip()
    if not bild_id:
        return None
    breite = zeile.get("breite")
    hoehe = zeile.get("hoehe")
    if not _ist_zahl(breite) or not _ist_zahl(hoehe):
        return None
    if float(breite) <= 0 or float(hoehe) <= 0:
        return None
    gesichter = zeile.get("gesichter")
    if not isinstance(gesichter, list):
        return None
    geprueft: list[dict] = []
    for gesicht in gesichter:
        if not isinstance(gesicht, dict):
            return None
        bbox = gesicht.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            return None
        if any(not _ist_zahl(wert) for wert in bbox):
            return None
        if float(bbox[2]) <= 0 or float(bbox[3]) <= 0:
            return None
        score = gesicht.get("score")
        if not _ist_zahl(score):
            return None
        merkmale = _vektor_von(gesicht)
        if merkmale is None or len(merkmale) != MERKMAL_LAENGE:
            return None
        geprueft.append({"bbox": [float(wert) for wert in bbox],
                         "score": float(score),
                         "embedding": merkmale})
    return {"bild_id": bild_id,
            "breite": float(breite),
            "hoehe": float(hoehe),
            "gesichter": geprueft}


def zeilen_lesen(pfad: str = STANDARD_VEKTOREN) -> dict:
    """Die Vektordatei (JSONL) lesen — nur lesend, kein Netz.

    Rueckgabe ``{"bilder", "zeilen_gesamt", "ungueltige_zeilen", "leere_zeilen"}``.
    Fehlende Datei ist ein ``PersonenFehler`` mit Klartextmeldung; **krumme
    Zeilen** sind kein Fehler: sie werden gezaehlt und uebersprungen, der Rest
    wird gelesen (kein Abbruch bei einer kaputten Zeile).
    """
    if not isinstance(pfad, str) or not pfad.strip():
        raise PersonenFehler("Kein Pfad fuer die Vektordatei angegeben.")
    if not os.path.isfile(pfad):
        raise PersonenFehler(f"Vektordatei nicht gefunden: {pfad}")
    bilder: list[dict] = []
    gesamt = 0
    ungueltig = 0
    leer = 0
    try:
        with open(pfad, encoding="utf-8") as datei:
            for zeile in datei:
                gesamt += 1
                roh = zeile.strip()
                if not roh:
                    leer += 1
                    ungueltig += 1
                    continue
                try:
                    daten = json.loads(roh)
                except ValueError:
                    ungueltig += 1
                    continue
                geprueft = zeile_pruefen(daten)
                if geprueft is None:
                    ungueltig += 1
                    continue
                bilder.append(geprueft)
    except OSError as problem:
        raise PersonenFehler(
            f"Vektordatei nicht lesbar ({problem.__class__.__name__}): {pfad}"
        ) from None
    return {"bilder": bilder, "zeilen_gesamt": gesamt,
            "ungueltige_zeilen": ungueltig, "leere_zeilen": leer}


def katalog_lesen(pfad: str) -> dict:
    """Den Personen-Katalog lesen — nur lesend, nur ausserhalb des Repos sinnvoll.

    Fehlende Datei, kein JSON oder ein unlesbarer Katalog sind ein
    ``PersonenFehler`` (hier wird nichts geraten: ein falsch gelesener Katalog
    wuerde falsche Personen zuordnen).
    """
    if not isinstance(pfad, str) or not pfad.strip():
        raise PersonenFehler("Kein Pfad fuer den Katalog angegeben.")
    if not os.path.isfile(pfad):
        raise PersonenFehler(f"Katalog nicht gefunden: {pfad}")
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except OSError as problem:
        raise PersonenFehler(
            f"Katalog nicht lesbar ({problem.__class__.__name__}): {pfad}"
        ) from None
    except ValueError as problem:
        raise PersonenFehler(
            f"Katalog ist kein gueltiges JSON ({problem.__class__.__name__}): {pfad}"
        ) from None
    if not isinstance(daten, (dict, list)):
        raise PersonenFehler(f"Katalog hat kein lesbares Format: {pfad}")
    return daten if isinstance(daten, dict) else {"personen": daten}


def altbestand_lesen_datei(pfad: str) -> list[dict]:
    """Den Kennungs-Altbestand aus einer Datei lesen — fehlend heisst leer.

    Im Unterschied zum Katalog ist ein **fehlender** Altbestand kein Fehler: der
    erste Lauf hat noch keinen, und dann werden eben alle Kennungen neu
    vergeben. Eine vorhandene, aber kaputte Datei ist ein ``PersonenFehler``.
    """
    if not isinstance(pfad, str) or not pfad.strip() or not os.path.isfile(pfad):
        return []
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except OSError as problem:
        raise PersonenFehler(
            f"Kennungs-Datei nicht lesbar ({problem.__class__.__name__}): {pfad}"
        ) from None
    except ValueError as problem:
        raise PersonenFehler(
            f"Kennungs-Datei ist kein gueltiges JSON ({problem.__class__.__name__}): {pfad}"
        ) from None
    return altbestand_lesen(daten)


# ── 11. Die geclusterten Gesichter einsammeln ────────────────────────────

def geclusterte_eintraege(bilder, entscheidungen) -> list[dict]:
    """Alle Gesichter der zum Clustern freigegebenen Bilder einsammeln.

    Jeder Eintrag traegt ``bild_id``, ``bbox``, ``score``, ``anteil`` und
    ``embedding`` — genau die Felder, die Clustern und Kachelauswahl brauchen.
    Die Reihenfolge ist die Reihenfolge der Bilder und ihrer Gesichter
    (deterministisch, das ist die Grundlage des Clusterns).
    """
    freigabe = {eintrag.get("bild_id") for eintrag in _liste(entscheidungen)
                if isinstance(eintrag, dict) and eintrag.get("clustern")}
    ergebnis: list[dict] = []
    for bild in _liste(bilder):
        if not isinstance(bild, dict) or bild.get("bild_id") not in freigabe:
            continue
        for eintrag in gesichter_bewerten(bild.get("gesichter"),
                                          bild.get("breite"),
                                          bild.get("hoehe")):
            if not eintrag["nutzbar"]:
                continue
            ergebnis.append({"bild_id": bild.get("bild_id"),
                             "bbox": eintrag["bbox"],
                             "score": eintrag["score"],
                             "anteil": eintrag["anteil"],
                             "embedding": eintrag["embedding"],
                             "index": eintrag["index"]})
    return ergebnis


# ── 12. Der Bericht ──────────────────────────────────────────────────────

def bericht_bauen(entscheidungen, ungueltige_zeilen: int = 0,
                  gruppen=None, kennungen=None, kacheln=None,
                  jahreszeit: str = "") -> dict:
    """Die Zahlen des Laufs als Dict — **rein**, ohne Dateizugriff.

    Felder: ``bilder_gelesen``, ``zeilen_gesamt``, ``ungueltige_zeilen``,
    ``je_art`` (alle vier Arten, auch die mit 0), ``geclusterte_bilder``,
    ``bilder_mit_bekannter_person``, ``gruppen``, ``gruppen_groessen``,
    ``kennungen_neu``, ``kennungen_wiederverwendet``, ``kacheln_geschrieben``
    und ``stand``.
    """
    liste = [eintrag for eintrag in _liste(entscheidungen)
             if isinstance(eintrag, dict)]
    je_art = {art: 0 for art in ARTEN}
    je_grund: dict[str, int] = {}
    geclustert = 0
    mit_bekannter: int = 0
    for eintrag in liste:
        art = eintrag.get("art")
        if art in je_art:
            je_art[art] += 1
        if eintrag.get("clustern"):
            geclustert += 1
        if _liste(eintrag.get("personen")):
            mit_bekannter += 1
        grund = eintrag.get("grund")
        if isinstance(grund, str) and grund:
            je_grund[grund] = je_grund.get(grund, 0) + 1
    gruppen_liste = [gruppe for gruppe in _liste(gruppen)
                     if isinstance(gruppe, (list, tuple))]
    kennungs_liste = [eintrag for eintrag in _liste(kennungen)
                      if isinstance(eintrag, dict)]
    kachel_liste = _liste(kacheln)
    ungueltig = int(ungueltige_zeilen) if _ist_zahl(ungueltige_zeilen) else 0
    return {
        "bilder_gelesen": len(liste),
        "zeilen_gesamt": len(liste) + ungueltig,
        "ungueltige_zeilen": ungueltig,
        "je_art": je_art,
        "je_grund": {name: je_grund[name] for name in sorted(je_grund)},
        "geclusterte_bilder": geclustert,
        "bilder_mit_bekannter_person": mit_bekannter,
        "gruppen": len(gruppen_liste),
        "gruppen_groessen": [len(gruppe) for gruppe in gruppen_liste],
        "kennungen_neu": sum(1 for eintrag in kennungs_liste
                             if eintrag.get("neu")),
        "kennungen_wiederverwendet": sum(1 for eintrag in kennungs_liste
                                         if not eintrag.get("neu")),
        "kacheln_geschrieben": len(kachel_liste),
        "stand": jahreszeit or datetime.datetime.now().isoformat(
            timespec="seconds"),
    }


def bericht_text(bericht) -> str:
    """Den Bericht als Klartext-Deutsch aufbereiten (feste Reihenfolge)."""
    b = bericht if isinstance(bericht, dict) else {}
    je_art = b.get("je_art") if isinstance(b.get("je_art"), dict) else {}
    je_grund = b.get("je_grund") if isinstance(b.get("je_grund"), dict) else {}
    groessen = b.get("gruppen_groessen") if isinstance(
        b.get("gruppen_groessen"), list) else []
    zeilen = [
        f"Bilder gelesen: {_zahl(b.get('bilder_gelesen'))}   "
        f"Zeilen gesamt: {_zahl(b.get('zeilen_gesamt'))}   "
        f"ungueltige Zeilen: {_zahl(b.get('ungueltige_zeilen'))}",
        "Je Bild-Art: " + "   ".join(
            f"{art}: {_zahl(je_art.get(art, 0))}" for art in ARTEN),
        f"Geclusterte Bilder: {_zahl(b.get('geclusterte_bilder'))}   "
        f"mit bekannter Person: {_zahl(b.get('bilder_mit_bekannter_person'))}   "
        f"Gruppen: {_zahl(b.get('gruppen'))}   "
        f"Groessen: {', '.join(str(_zahl(wert)) for wert in groessen) or '-'}",
        f"Kennungen neu: {_zahl(b.get('kennungen_neu'))}   "
        f"Kennungen wiederverwendet: {_zahl(b.get('kennungen_wiederverwendet'))}   "
        f"Kacheln geschrieben: {_zahl(b.get('kacheln_geschrieben'))}",
    ]
    if je_grund:
        zeilen.append("Gruende: " + "   ".join(
            f"{name}: {_zahl(je_grund[name])}" for name in sorted(je_grund)))
    return "\n".join(zeilen)


# ── 13. Einen ganzen Lauf rechnen (rein, keine Schreibvorgaenge) ─────────

def lauf_rechnen(bilder, katalog=None, params=None,
                 altbestand=None, schwelle: float = CLUSTER_SCHWELLE,
                 min_nachbarn: int = CLUSTER_MIN_NACHBAR,
                 kacheln_je_seite: int = KACHELN_JE_SEITE,
                 verfahren: str | None = None) -> dict:
    """Den ganzen Durchlauf rechnen — **ohne** Schreiben, ohne Netz, ohne Bild.

    Ablauf: je Bild entscheiden -> die freigegebenen Gesichter einsammeln ->
    clustern -> Kennungen gegen den Altbestand vergeben -> Kachel-Eintraege je
    Gruppe bauen. Rueckgabe ``{"entscheidungen", "eintraege", "gruppen",
    "kennungen", "gruppen_eintraege", "altbestand", "bericht"}`` — alles reine
    Daten, der Aufrufer entscheidet ueber Referenzseiten und Dateien.

    ``verfahren`` wird **nur** durchgereicht, wenn es ausdruecklich gesetzt ist;
    ohne Angabe gilt der Produktionsstandard ``CLUSTER_VERFAHREN``.
    """
    entscheidungen = [bild_entscheidung(bild, katalog, params)
                      for bild in _liste(bilder)]
    eintraege = geclusterte_eintraege(bilder, entscheidungen)
    # Produktionsaufruf: **ohne** ``verfahren`` — es gilt der Standard
    # ``CLUSTER_VERFAHREN`` (vollstaendige Verknuepfung, Durchmesser <= Schwelle).
    # Nur die Kommandozeile schaltet ausdruecklich um.
    if verfahren is None:
        gruppen = vektoren_clustern(eintraege, schwelle, min_nachbarn)
    else:
        gruppen = vektoren_clustern(eintraege, schwelle, min_nachbarn, verfahren)
    kennungen = gruppen_kennungen(gruppen, eintraege, altbestand, ALT_SCHWELLE)
    gruppen_eintraege = gruppen_eintraege_bauen(gruppen, eintraege, kennungen)
    bericht = bericht_bauen(entscheidungen, gruppen=gruppen,
                            kennungen=kennungen)
    bericht["kacheln_je_seite"] = int(kacheln_je_seite) \
        if _ist_zahl(kacheln_je_seite) else KACHELN_JE_SEITE
    return {"entscheidungen": entscheidungen,
            "eintraege": eintraege,
            "gruppen": gruppen,
            "kennungen": kennungen,
            "gruppen_eintraege": gruppen_eintraege,
            "altbestand": altbestand_bauen(kennungen),
            "bericht": bericht}


def kennungen_schreiben(pfad: str, kennungen) -> str:
    """Den Kennungs-Altbestand schreiben — atomar, nur ausserhalb des Repos.

    Ohne diese Datei waeren die Kennungen beim naechsten Lauf weg. Geschrieben
    wird ``{"kennungen": [{kennung, mittelpunkt}], "stand": …}``; die
    Schreibweise ist atomar (temp-Datei + ``os.replace``), damit nie eine halbe
    Datei liegen bleibt. Ein Repo-Pfad ergibt ``SystemExit(2)``.
    """
    pruefe_ausserhalb_repo(pfad)
    inhalt = {"stand": datetime.datetime.now().isoformat(timespec="seconds"),
              "kennungen": altbestand_bauen(kennungen)}
    ordner = os.path.dirname(os.path.abspath(pfad))
    os.makedirs(ordner, exist_ok=True)
    temp = pfad + ".tmp"
    with open(temp, "w", encoding="utf-8") as datei:
        json.dump(inhalt, datei, ensure_ascii=False, indent=1)
        datei.write("\n")
    os.replace(temp, pfad)
    return pfad


# ── 14. Kommandozeile ────────────────────────────────────────────────────

def main(argv=None) -> int:
    """Kommandozeilen-Teil: entscheiden, clustern, Kennungen, Referenzseiten.

    Standard ist der **Trockenlauf**: gezeigt werden die Berichtszahlen und die
    Dateinamen, die entstuenden — geschrieben wird nichts. Geschrieben wird nur
    mit ``--schreiben`` (und ``--trocken`` hat Vorrang). Ein Ausgabeordner
    **innerhalb** des Repos ist ein Fehler (``SystemExit(2)``).
    """
    zerleger = argparse.ArgumentParser(
        description="Personen-Verfahren N9a: entscheidet je Bild, ob geclustert "
                    "wird (Menschenmenge ohne bekannte Person: nein), clustert "
                    "die Vektoren, vergibt stabile Kennungen Person_001… und "
                    "baut Referenzseiten. Loescht nichts, ruft keine pCloud an.")
    zerleger.add_argument("--vektoren", dest="vektoren", required=True,
                          help="Vektordatei (JSONL, ausserhalb des Repos)")
    zerleger.add_argument("--ausgabe", dest="ausgabe", required=True,
                          help="Ausgabeordner (PFLICHT ausserhalb des Repos)")
    zerleger.add_argument("--katalog", dest="katalog", default=None,
                          help="Personen-Katalog (JSON, optional)")
    zerleger.add_argument("--altbestand", dest="altbestand", default=None,
                          help="Kennungs-Datei des letzten Laufs (Standard: "
                               "kennungen.json im Ausgabeordner)")
    zerleger.add_argument("--schwelle", dest="schwelle", type=float,
                          default=CLUSTER_SCHWELLE,
                          help="Cosinus-Distanz-Grenze des Clusters "
                               f"(Standard {CLUSTER_SCHWELLE})")
    zerleger.add_argument("--min-nachbarn", dest="min_nachbarn", type=int,
                          default=CLUSTER_MIN_NACHBAR,
                          help="Untergrenze je Gruppe: Nachbarn fuer einen "
                               "Kernpunkt (Verfahren dichte) bzw. "
                               "Mindestgruppengroesse (Verfahren vollstaendig) "
                               f"(Standard {CLUSTER_MIN_NACHBAR})")
    zerleger.add_argument("--verfahren", dest="verfahren",
                          choices=list(VERFAHREN), default=CLUSTER_VERFAHREN,
                          help="Verknuepfung der Vektoren: "
                               f"{VERFAHREN_DICHTE!r} (Bestandsverfahren, kann "
                               "die Schwelle reissen) oder "
                               f"{VERFAHREN_VOLLSTAENDIG!r} (Complete-Linkage, "
                               "Durchmesser <= Schwelle) "
                               f"(Standard {CLUSTER_VERFAHREN!r})")
    zerleger.add_argument("--kacheln-je-seite", dest="kacheln_je_seite",
                          type=int, default=KACHELN_JE_SEITE,
                          help=f"Kacheln je Referenzseite (Standard {KACHELN_JE_SEITE})")
    zerleger.add_argument("--erneut", dest="erneut", action="store_true",
                          help="vorhandene Referenzseiten ueberschreiben")
    zerleger.add_argument("--trocken", dest="trocken", action="store_true",
                          help="nichts schreiben (hat Vorrang vor --schreiben)")
    zerleger.add_argument("--schreiben", dest="schreiben", action="store_true",
                          help="Referenzseiten und Kennungs-Datei wirklich schreiben")
    args = zerleger.parse_args(argv)

    pruefe_ausserhalb_repo(args.ausgabe)
    schreiben = bool(args.schreiben) and not bool(args.trocken)

    try:
        eingelesen = zeilen_lesen(args.vektoren)
        katalog = katalog_lesen(args.katalog) if args.katalog else {}
        kennungs_pfad = args.altbestand or os.path.join(args.ausgabe,
                                                        KENNUNGEN_DATEI)
        altbestand = altbestand_lesen_datei(kennungs_pfad)

        print("Personen-Verfahren N9a — "
              + ("Trockenlauf (es wird NICHTS geschrieben)" if not schreiben
                 else "Schreiben ist eingeschaltet"))
        print(f"Vektordatei: {args.vektoren}")
        print(f"Ausgabeordner: {args.ausgabe}")
        print(f"Katalog: {'ja' if args.katalog else 'nein (keine Vordergrund-Pruefung)'}"
              f"   Altbestand: {len(altbestand)} Kennung(en)")

        gewaehlt = _verfahren_waehlen(args.verfahren)
        print(f"Verfahren: {gewaehlt}   Schwelle: {args.schwelle}   "
              f"Untergrenze je Gruppe: {args.min_nachbarn}")

        lauf = lauf_rechnen(eingelesen["bilder"], katalog=katalog,
                            altbestand=altbestand, schwelle=args.schwelle,
                            min_nachbarn=args.min_nachbarn,
                            kacheln_je_seite=args.kacheln_je_seite,
                            verfahren=gewaehlt)
        bericht = bericht_bauen(lauf["entscheidungen"],
                                ungueltige_zeilen=eingelesen["ungueltige_zeilen"],
                                gruppen=lauf["gruppen"],
                                kennungen=lauf["kennungen"])

        if schreiben:
            kacheln = referenzseiten_bauen(lauf["gruppen_eintraege"],
                                           ausgabe_ordner=args.ausgabe,
                                           kacheln_je_seite=args.kacheln_je_seite,
                                           erneut=args.erneut)
            bericht["kacheln_geschrieben"] = len(kacheln)
            if lauf["altbestand"]:
                kennungen_schreiben(kennungs_pfad, lauf["kennungen"])
            print(f"Referenzseiten geschrieben: {len(kacheln)}")
        else:
            geplant = referenzseiten_planen(lauf["gruppen_eintraege"],
                                            args.ausgabe,
                                            args.kacheln_je_seite,
                                            erneut=args.erneut)
            bericht["kacheln_geschrieben"] = 0
            print("Geplante Referenzseiten (nicht geschrieben):")
            for name in geplant:
                print(f"  {name}")
            if not geplant:
                print("  keine (nichts zu clustern oder schon vorhanden)")

        print(bericht_text(bericht))
        print(f"Kennungen: {', '.join(eintrag['kennung'] for eintrag in lauf['kennungen']) or 'keine'}")
        if not schreiben:
            print("Ohne --schreiben wurde NICHTS geschrieben.")
        return 0
    except (PersonenFehler, ValueError) as problem:
        print(f"Fehler: {problem}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
