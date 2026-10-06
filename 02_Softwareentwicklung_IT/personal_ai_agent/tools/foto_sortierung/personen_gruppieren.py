"""Personen gruppieren ueber ALLE Gesichter (Foto-Gedaechtnis, Schritt 1, 30.09.2026).

Wozu:
  Die Gesichtsvektoren liegen fuer alle Bilder vor (Aufgabe 1 + Aufgabe 3,
  dazu Video-Standbilder). ``personen_cluster.py`` gruppiert mit
  Complete-Linkage ueber eine volle n x n-Matrix (``vollstaendig_clustern``) —
  bei rund 30.000 Gesichtern waeren das etwa 7 GB je Matrix und etwa n^3
  Rechenschritte. Dieses Werkzeug gruppiert deshalb ueber **Mittelpunkte**:
  jedes Gesicht wird mit den Mittelpunkten der bisherigen Gruppen verglichen,
  nicht mit allen anderen Gesichtern. Speicher: O(n x 128), keine n x n-Matrix.

Was es von ``personen_cluster`` uebernimmt (unveraendert, per Import):
  Zeilenpruefung (``zeile_pruefen``), die Mengen-Regel (``bild_entscheidung`` —
  Menschenmengen ohne bekannte Person werden nicht gruppiert), die
  Gesichtsbewertung (``gesichter_bewerten``), die Schwellen (``CLUSTER_SCHWELLE``,
  ``ALT_SCHWELLE``, ``CLUSTER_MIN_NACHBAR``), das Kennungsmuster ``Person_%03d``,
  den Repo-Schutz und das Schreiben des Kennungs-Altbestands.

Das Verfahren (``gruppieren``, rein, nur numpy):
  1. **Anlegen:** Gesichter nach Qualitaet (Flaechenanteil x Score) absteigend;
     jedes Gesicht geht an die aehnlichste Gruppe, deren Mittelpunkt es mit
     Cosinus >= ``zuordnung`` trifft — aber **nie** an eine Gruppe, die schon
     ein Gesicht **desselben Bildes** enthaelt (cannot-link: zwei Gesichter auf
     einem Foto sind zwei Menschen). Sonst beginnt es eine neue Gruppe.
  2. **Verfeinern** (``runden`` Mal): alle Gesichter gegen die Mittelpunkte neu
     zuordnen, je Bild ohne Doppelung; Mittelpunkte neu rechnen.
  3. **Verschmelzen:** Gruppen, deren Mittelpunkte Cosinus >= ``verschmelzen``
     haben, werden zusammengelegt — ausser sie teilen sich ein Bild, der Nutzer
     hat sie als verschieden markiert oder sie tragen verschiedene bestaetigte
     Namen. Gleich markierte Gruppen werden zusammengelegt.
  4. **Rauschen:** Gruppen unter ``min_groesse`` Gesichtern bekommen keine Kennung.
  5. **Zwillings-/Doppel-Kandidaten:** Paare verschiedener Gruppen mit
     Mittelpunkt-Cosinus >= ``zwilling`` — aehnlich, aber getrennt geblieben.
     Teilen sie sich Bilder, sind es sicher zwei Menschen (Zwillinge,
     Geschwister); sonst kann es auch dieselbe Person sein. Beides entscheidet
     der Nutzer im Quiz — nie das Werkzeug.

Ausgaben (nur mit ``--schreiben``, nur ausserhalb des Repos, atomar):
  * ``gesicht_zuordnung.jsonl`` — je Gesicht ``bild_id``, ``index``,
    ``kennung`` (``null`` = Rauschen), ``bbox``, ``breite``, ``hoehe``,
    ``anteil``, ``score``, ``aufnahme``, ``video_id``, ``zeit_s``.
    **Ohne Vektoren** — darf ans Handy.
  * ``personen_beispiele.json`` — je Gruppe Groesse, Bilder, Zeitraum,
    bestaetigter Name (falls vorhanden), Zwillings-Kandidaten und bis zu 8
    Beispiel-Gesichter (nur Fotos, beste Qualitaet, ueber die Jahre gestreut)
    fuer das Quiz. **Ohne Vektoren** — darf ans Handy.
  * ``kennungen.json`` — Mittelpunkte je Kennung (stabile Kennungen beim
    naechsten Lauf). **Biometrie — bleibt am PC.**

Bericht: nur Zaehlungen (Dateien, Zeilen, Bilder, Gesichter, Gruppen, Groessen,
Rauschen, Kandidaten-Paare) — nie Namen, nie Vektoren, nie Dateinamen von Fotos.

Aufruf::

    .venv/Scripts/python.exe ../tools/foto_sortierung/personen_gruppieren.py            # Trockenlauf
    .venv/Scripts/python.exe ../tools/foto_sortierung/personen_gruppieren.py --schreiben

Nachtragen (``--nachtragen``, 06.10.2026):
  Neue Gesichter an die **bestehenden** Gruppen haengen, ohne neu zu rechnen.
  Anlass: die Fotobuch-Fotos fehlten in der Gesichtererkennung, und ein voller
  Neu-Lauf bringt die schon benannten Gruppen durcheinander (gemessen: eine
  Gruppe behielt nur 22 % ihrer Gesichter, 27 Gesichter wanderten zu einer
  anderen benannten Person). Deshalb: alte Zuordnungszeilen 1:1 uebernehmen,
  alte Mittelpunkte **nicht** verschieben; jedes neue Gesicht dockt an den
  aehnlichsten alten Mittelpunkt (Cosinus >= ``ZUORDNUNG_AEHNLICH``, nie zwei
  Gesichter desselben Bildes in dieselbe Gruppe, Nutzer-Ausschluesse beachtet).
  Was nicht andockt, gruppiert sich untereinander und bekommt **neue** Kennungen
  hinter der hoechsten Nummer. Vor dem Schreiben werden die drei Dateien als
  ``*.vorher`` gesichert (Rueckweg); ein zweiter Lauf ist idempotent.

    .venv/Scripts/python.exe ../tools/foto_sortierung/personen_gruppieren.py ^
        --nachtragen %USERPROFILE%/foto_sortierung/personen_vektoren_fotobuch.jsonl
    # Schreiben erst nach dem OK auf die Trockenlauf-Zahlen: zusaetzlich --schreiben
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import shutil
import time

import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))


def _nachbar(name: str):
    """Ein Nachbarmodul importieren; im Test-Ladeweg ueber den Dateipfad."""
    try:
        return __import__(name)
    except ImportError:                          # pragma: no cover
        spez = importlib.util.spec_from_file_location(
            name, os.path.join(HIER, name + ".py"))
        if spez is None or spez.loader is None:  # pragma: no cover
            raise
        modul = importlib.util.module_from_spec(spez)
        spez.loader.exec_module(modul)
        return modul


_cluster = _nachbar("personen_cluster")

PersonenFehler = _cluster.PersonenFehler
pruefe_ausserhalb_repo = _cluster.pruefe_ausserhalb_repo

STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_VEKTOREN = [
    os.path.join(STANDARD_BASIS, "personen_vektoren_n0929_voll.jsonl"),
    os.path.join(STANDARD_BASIS, "personen_vektoren_n0929_bildervideos.jsonl"),
    os.path.join(STANDARD_BASIS, "video_vektoren_bildervideos.jsonl"),
]
STANDARD_AUSGABE = os.path.join(STANDARD_BASIS, "personen_gruppen")
STANDARD_BESTAETIGT = os.path.join(STANDARD_BASIS, "personen_bestaetigt.json")
STANDARD_VORGABEN = os.path.join(STANDARD_BASIS, "personen_vorgaben.json")

DATEI_ZUORDNUNG = "gesicht_zuordnung.jsonl"
DATEI_BEISPIELE = "personen_beispiele.json"
DATEI_KENNUNGEN = _cluster.KENNUNGEN_DATEI          # "kennungen.json"

# Cosinus-Aehnlichkeit Gesicht -> Gruppenmittelpunkt. Abgeleitet aus der
# bestehenden Cluster-Grenze (Distanz 0,45 = Aehnlichkeit 0,55), damit beide
# Werkzeuge dieselbe Strenge haben.
ZUORDNUNG_AEHNLICH = 1.0 - _cluster.CLUSTER_SCHWELLE
# Mittelpunkt <-> Mittelpunkt: ab hier ist es dieselbe Person (Mittelpunkte sind
# rauschaermer als Einzelgesichter, deshalb etwas strenger als die Zuordnung).
VERSCHMELZ_AEHNLICH = 0.60
# Aehnlich, aber getrennt geblieben -> Kandidat fuer "gleiche Person?" oder
# "Zwillinge/Geschwister" im Quiz.
ZWILLING_AEHNLICH = 0.45
MIN_GROESSE = _cluster.CLUSTER_MIN_NACHBAR
VERFEINERN_RUNDEN = 2
BEISPIELE_JE_GRUPPE = 8
ZWILLING_KANDIDATEN_JE_GRUPPE = 3
BLOCK = 1024                                        # Gesichter je Rechenblock


# ── Lesen ────────────────────────────────────────────────────────────────

def _json_lesen(pfad, standard):
    """JSON lesen — fehlende Datei = ``standard``, kaputte Datei = Fehler."""
    if not pfad or not os.path.isfile(pfad):
        return standard
    try:
        with open(pfad, encoding="utf-8") as datei:
            return json.load(datei)
    except (OSError, ValueError) as problem:
        raise PersonenFehler(
            f"Datei nicht lesbar ({problem.__class__.__name__}): {pfad}") from None


def bestaetigt_lesen(pfad) -> dict:
    """``{"bestaetigt": {"Person_001": "Name"}}`` -> ``{kennung: name}``."""
    daten = _json_lesen(pfad, {})
    roh = daten.get("bestaetigt") if isinstance(daten, dict) else None
    if not isinstance(roh, dict):
        return {}
    return {str(k): str(v).strip() for k, v in roh.items()
            if isinstance(v, str) and v.strip()}


def vorgaben_lesen(pfad) -> dict:
    """``{"gleich": [[a, b]], "verschieden": [[a, b]], "ausgeschlossen": [...]}`` lesen.

    ``gleich``/``verschieden`` -> Mengen von Kennungs-Paaren. ``ausgeschlossen``
    (02.10.2026, Quiz am Handy: „dieses Gesicht ist nicht diese Person") ->
    Menge von ``(kennung, bild_id, index)``: das Gesicht kommt nie wieder in
    den Vorschlag mit dieser Kennung.
    """
    daten = _json_lesen(pfad, {})
    ergebnis = {"gleich": set(), "verschieden": set(), "ausgeschlossen": set()}
    if not isinstance(daten, dict):
        return ergebnis
    for e in daten.get("ausgeschlossen") or []:
        if (isinstance(e, dict) and isinstance(e.get("kennung"), str) and e["kennung"]
                and str(e.get("bild_id") or "").isdigit()):
            try:
                ergebnis["ausgeschlossen"].add((e["kennung"], str(e["bild_id"]), int(e.get("index") or 0)))
            except (TypeError, ValueError):
                continue
    for art in ("gleich", "verschieden"):
        for paar in daten.get(art) or []:
            if (isinstance(paar, (list, tuple)) and len(paar) == 2
                    and all(isinstance(x, str) and x for x in paar)
                    and paar[0] != paar[1]):
                ergebnis[art].add(tuple(sorted(paar)))
    return ergebnis


def gesichter_lesen(pfade, katalog=None) -> dict:
    """Alle Vektordateien lesen — nur lesend. Rueckgabe siehe unten.

    Je Bild entscheidet die Mengen-Regel aus ``personen_cluster``, ob es
    gruppiert wird. Ein Bild, das schon aus einer frueheren Datei kam
    (gleiche ``bild_id``), zaehlt einmal. Kaputte Zeilen werden gezaehlt,
    nicht geraten; eine fehlende Datei ist ein Fehler (keine stillen Luecken).

    Rueckgabe ``{"gesichter": [...], "vektoren": ndarray (n, 128) float32,
    "dateien": [...], "bilder": int, "bilder_gruppiert": int, "je_grund": {},
    "ungueltig": int, "doppelt": int}``.
    """
    gesichter: list[dict] = []
    vektoren: list[list[float]] = []
    dateien: list[dict] = []
    gesehen: set[str] = set()
    je_grund: dict[str, int] = {}
    bilder = gruppiert = ungueltig_gesamt = doppelt = 0
    for pfad in pfade:
        if not os.path.isfile(pfad):
            raise PersonenFehler(f"Vektordatei nicht gefunden: {pfad}")
        zeilen = ungueltig = 0
        try:
            with open(pfad, encoding="utf-8") as datei:
                for roh in datei:
                    zeilen += 1
                    roh = roh.strip()
                    try:
                        daten = json.loads(roh) if roh else None
                    except ValueError:
                        daten = None
                    geprueft = _cluster.zeile_pruefen(daten)
                    if geprueft is None:
                        ungueltig += 1
                        continue
                    bild_id = geprueft["bild_id"]
                    if bild_id in gesehen:
                        doppelt += 1
                        continue
                    gesehen.add(bild_id)
                    bilder += 1
                    entscheidung = _cluster.bild_entscheidung(geprueft, katalog)
                    grund = entscheidung.get("grund") or "?"
                    je_grund[grund] = je_grund.get(grund, 0) + 1
                    if not entscheidung.get("clustern"):
                        continue
                    gruppiert += 1
                    meta = daten.get("metadaten") if isinstance(daten.get("metadaten"), dict) else {}
                    aufnahme = meta.get("aufnahme") if isinstance(meta.get("aufnahme"), str) else None
                    video_id = daten.get("video_id")
                    zeit_s = daten.get("zeit_s")
                    for g in _cluster.gesichter_bewerten(geprueft["gesichter"],
                                                         geprueft["breite"],
                                                         geprueft["hoehe"]):
                        if not g["nutzbar"]:
                            continue
                        gesichter.append({
                            "bild_id": bild_id,
                            "index": int(g["index"]),
                            "bbox": [round(float(w), 1) for w in g["bbox"]],
                            "breite": geprueft["breite"],
                            "hoehe": geprueft["hoehe"],
                            "anteil": round(float(g["anteil"]), 6),
                            "score": round(float(g["score"]), 4),
                            "aufnahme": aufnahme,
                            "video_id": str(video_id) if video_id not in (None, "") else None,
                            "zeit_s": zeit_s if _cluster._ist_zahl(zeit_s) else None,
                        })
                        vektoren.append(g["embedding"])
        except OSError as problem:
            raise PersonenFehler(
                f"Vektordatei nicht lesbar ({problem.__class__.__name__}): {pfad}") from None
        dateien.append({"pfad": pfad, "zeilen": zeilen, "ungueltig": ungueltig})
        ungueltig_gesamt += ungueltig
    matrix = (np.asarray(vektoren, dtype=np.float32) if vektoren
              else np.zeros((0, _cluster.MERKMAL_LAENGE), dtype=np.float32))
    return {"gesichter": gesichter, "vektoren": einheitsvektoren(matrix),
            "dateien": dateien, "bilder": bilder, "bilder_gruppiert": gruppiert,
            "je_grund": je_grund, "ungueltig": ungueltig_gesamt, "doppelt": doppelt}


# ── Rechnen (rein) ───────────────────────────────────────────────────────

def einheitsvektoren(matrix) -> np.ndarray:
    """Zeilen auf Laenge 1; Nullzeilen bleiben Null (zu nichts aehnlich)."""
    m = np.asarray(matrix, dtype=np.float32)
    if m.ndim != 2 or m.shape[0] == 0:
        return m.reshape(0, m.shape[-1] if m.ndim == 2 else _cluster.MERKMAL_LAENGE)
    laenge = np.linalg.norm(m, axis=1, keepdims=True)
    laenge[laenge == 0] = 1.0
    return m / laenge


def _mittelpunkte(v, label, k) -> tuple[np.ndarray, np.ndarray]:
    """Summen -> normierte Mittelpunkte und Gruppengroessen fuer Labels 0..k-1."""
    summen = np.zeros((k, v.shape[1]), dtype=np.float64)
    gueltig = label >= 0
    np.add.at(summen, label[gueltig], v[gueltig])
    groessen = np.bincount(label[gueltig], minlength=k)
    return einheitsvektoren(summen), groessen


def _kompakt(label) -> tuple[np.ndarray, int]:
    """Labels auf 0..k-1 ohne Luecken bringen (Reihenfolge des ersten Auftretens)."""
    neu = np.full_like(label, -1)
    zuordnung: dict[int, int] = {}
    for i, alt in enumerate(label.tolist()):
        if alt < 0:
            continue
        if alt not in zuordnung:
            zuordnung[alt] = len(zuordnung)
        neu[i] = zuordnung[alt]
    return neu, len(zuordnung)


def _anlegen(v, bild, reihenfolge, schwelle) -> np.ndarray:
    """Schritt 1: Gesichter der Reihe nach an Gruppen haengen (cannot-link je Bild)."""
    n, d = v.shape
    label = np.full(n, -1, dtype=np.int64)
    summen = np.zeros((n, d), dtype=np.float64)
    mitte = np.zeros((n, d), dtype=np.float32)
    bilder_je_gruppe: list[set] = []
    k = 0
    for i in reihenfolge:
        ziel = -1
        if k:
            aehnlich = mitte[:k] @ v[i]
            kandidaten = np.nonzero(aehnlich >= schwelle)[0]
            if kandidaten.size:
                for c in kandidaten[np.argsort(-aehnlich[kandidaten], kind="stable")]:
                    if bild[i] not in bilder_je_gruppe[c]:
                        ziel = int(c)
                        break
        if ziel < 0:
            ziel = k
            k += 1
            bilder_je_gruppe.append(set())
        label[i] = ziel
        summen[ziel] += v[i]
        laenge = np.linalg.norm(summen[ziel])
        mitte[ziel] = summen[ziel] / (laenge if laenge else 1.0)
        bilder_je_gruppe[ziel].add(bild[i])
    return label


def _verfeinern(v, bild, label, schwelle, kandidaten_je_gesicht=5) -> np.ndarray:
    """Schritt 2: alle Gesichter neu zuordnen, je Bild ohne Doppelung."""
    label, k = _kompakt(label)
    if k == 0:
        return label
    mitte, _ = _mittelpunkte(v, label, k)
    n = v.shape[0]
    top = min(kandidaten_je_gesicht, k)
    beste = np.zeros((n, top), dtype=np.int64)
    werte = np.zeros((n, top), dtype=np.float32)
    for start in range(0, n, BLOCK):
        s = v[start:start + BLOCK] @ mitte.T                     # (b, k)
        if top < k:
            idx = np.argpartition(-s, top - 1, axis=1)[:, :top]
        else:
            idx = np.tile(np.arange(k), (s.shape[0], 1))
        w = np.take_along_axis(s, idx, axis=1)
        ordnung = np.argsort(-w, axis=1, kind="stable")
        beste[start:start + BLOCK] = np.take_along_axis(idx, ordnung, axis=1)
        werte[start:start + BLOCK] = np.take_along_axis(w, ordnung, axis=1)
    neu = np.full(n, -1, dtype=np.int64)
    je_bild: dict = {}
    for i, b in enumerate(bild):
        je_bild.setdefault(b, []).append(i)
    for gesichter in je_bild.values():
        paare = sorted(((float(werte[i, j]), i, int(beste[i, j]))
                        for i in gesichter for j in range(top)
                        if werte[i, j] >= schwelle),
                       key=lambda t: (-t[0], t[1], t[2]))
        belegt: set = set()
        for _, i, c in paare:
            if neu[i] >= 0 or c in belegt:
                continue
            neu[i] = c
            belegt.add(c)
        for i in gesichter:                      # nichts passte: eigene Gruppe behalten
            if neu[i] < 0 and label[i] >= 0 and label[i] not in belegt:
                neu[i] = label[i]
                belegt.add(int(label[i]))
    return _kompakt(neu)[0]


def _bilder_je_gruppe(bild, label, k) -> list[set]:
    ergebnis: list[set] = [set() for _ in range(k)]
    for b, c in zip(bild, label.tolist()):
        if c >= 0:
            ergebnis[c].add(b)
    return ergebnis


def _paare_ueber(mitte, schwelle) -> list[tuple[float, int, int]]:
    """Alle Gruppenpaare (a < b) mit Mittelpunkt-Cosinus >= schwelle — blockweise."""
    k = mitte.shape[0]
    paare: list[tuple[float, int, int]] = []
    for start in range(0, k, BLOCK):
        s = mitte[start:start + BLOCK] @ mitte.T
        zeilen, spalten = np.nonzero(s >= schwelle)
        for z, sp in zip(zeilen.tolist(), spalten.tolist()):
            a = start + z
            if a < sp:
                paare.append((float(s[z, sp]), a, sp))
    paare.sort(key=lambda t: (-t[0], t[1], t[2]))
    return paare


def gruppieren(vektoren, bild_ids, qualitaet=None,
               zuordnung: float = ZUORDNUNG_AEHNLICH,
               verschmelzen: float = VERSCHMELZ_AEHNLICH,
               min_groesse: int = MIN_GROESSE,
               runden: int = VERFEINERN_RUNDEN,
               vorab_kennung=None, verschieden=None, gleich=None) -> dict:
    """Das Gruppier-Verfahren (rein). Siehe Moduldoku, Schritte 1–4.

    ``vorab_kennung(mittelpunkte) -> list[str|None]`` ordnet Gruppen VOR dem
    Verschmelzen einer frueheren Kennung zu (fuer Nutzervorgaben); ``verschieden``
    ist eine Funktion ``(kennung_a, kennung_b) -> bool`` (nie verschmelzen),
    ``gleich`` eine Menge von Kennungs-Paaren, die verschmolzen werden.

    Rueckgabe ``{"label": ndarray (n,) mit -1 = Rauschen, "k": int}``; Labels
    sind nach Gruppengroesse absteigend nummeriert (0 = groesste Gruppe).
    """
    v = einheitsvektoren(vektoren)
    n = v.shape[0]
    if n == 0:
        return {"label": np.zeros(0, dtype=np.int64), "k": 0}
    bild = list(bild_ids)
    q = np.zeros(n) if qualitaet is None else np.asarray(qualitaet, dtype=float)
    reihenfolge = np.lexsort((np.arange(n), -q))            # beste zuerst, stabil

    label = _anlegen(v, bild, reihenfolge, zuordnung)
    for _ in range(max(0, int(runden))):
        label = _verfeinern(v, bild, label, zuordnung)

    # Schritt 3: verschmelzen (Union-Find ueber Gruppen, Bedingungen je Paar).
    label, k = _kompakt(label)
    mitte, _ = _mittelpunkte(v, label, k)
    kennung_vorab = list(vorab_kennung(mitte)) if vorab_kennung else [None] * k
    bilder = _bilder_je_gruppe(bild, label, k)
    eltern = list(range(k))

    def wurzel(x):
        while eltern[x] != x:
            eltern[x] = eltern[eltern[x]]
            x = eltern[x]
        return x

    kennungen_je_wurzel = {c: ({kennung_vorab[c]} if kennung_vorab[c] else set())
                           for c in range(k)}

    def darf(a, b) -> bool:
        if bilder[a] & bilder[b]:
            return False
        if verschieden:
            for x in kennungen_je_wurzel[a]:
                for y in kennungen_je_wurzel[b]:
                    if verschieden(x, y):
                        return False
        return True

    def vereinen(a, b):
        a, b = wurzel(a), wurzel(b)
        if a == b or not darf(a, b):
            return
        klein, gross = (a, b) if a > b else (b, a)
        eltern[klein] = gross
        bilder[gross] |= bilder[klein]
        kennungen_je_wurzel[gross] |= kennungen_je_wurzel[klein]

    if gleich:
        nach_kennung: dict[str, int] = {}
        for c, kenn in enumerate(kennung_vorab):
            if kenn and kenn not in nach_kennung:
                nach_kennung[kenn] = c
        for a, b in sorted(gleich):
            if a in nach_kennung and b in nach_kennung:
                vereinen(nach_kennung[a], nach_kennung[b])
    for _, a, b in _paare_ueber(mitte, verschmelzen):
        vereinen(a, b)
    label = np.array([wurzel(int(c)) if c >= 0 else -1 for c in label], dtype=np.int64)

    # Schritt 4: kleine Gruppen sind Rauschen; nach Groesse absteigend nummerieren.
    groessen = np.bincount(label[label >= 0], minlength=k) if k else np.zeros(0, int)
    behalten = [c for c in range(len(groessen)) if groessen[c] >= max(1, int(min_groesse))]
    behalten.sort(key=lambda c: (-int(groessen[c]), c))
    neu_nummer = {c: i for i, c in enumerate(behalten)}
    label = np.array([neu_nummer.get(int(c), -1) for c in label], dtype=np.int64)
    return {"label": label, "k": len(behalten)}


def zwillings_kandidaten(vektoren, bild_ids, label, k,
                         schwelle: float = ZWILLING_AEHNLICH) -> list[dict]:
    """Schritt 5: aehnliche, aber getrennte Gruppen — mit Zahl gemeinsamer Bilder."""
    if k < 2:
        return []
    mitte, _ = _mittelpunkte(einheitsvektoren(vektoren), np.asarray(label), k)
    bilder = _bilder_je_gruppe(list(bild_ids), np.asarray(label), k)
    return [{"a": a, "b": b, "aehnlich": round(w, 3),
             "gemeinsame_bilder": len(bilder[a] & bilder[b])}
            for w, a, b in _paare_ueber(mitte, schwelle)]


def kennungen_vergeben(mitte, altbestand, schwelle: float = _cluster.ALT_SCHWELLE):
    """Stabile Kennungen: Gruppen (in Reihenfolge) auf frühere Mittelpunkte abbilden.

    Wie ``personen_cluster.gruppen_kennungen``, aber vektorisiert: jede fruehere
    Kennung zaehlt je Lauf einmal, die erste (= groesste) passende Gruppe
    gewinnt; neue Kennungen setzen hinter der hoechsten Nummer fort, Nummern
    werden nie wiederverwendet. Rueckgabe je Gruppe ``{kennung, neu, treffer}``.
    """
    alt = _cluster.altbestand_lesen(altbestand)
    hoechste = _cluster._naechste_nummer(sorted(e["kennung"] for e in alt))
    ergebnis = []
    if alt and len(mitte):
        a = einheitsvektoren(np.asarray([e["mittelpunkt"] for e in alt], dtype=np.float32))
        s = einheitsvektoren(mitte) @ a.T
    else:
        s = None
    benutzt: set[int] = set()
    for g in range(len(mitte)):
        kennung, neu, treffer = None, True, None
        if s is not None:
            for j in np.argsort(-s[g], kind="stable").tolist():
                if j in benutzt:
                    continue
                if s[g, j] >= schwelle:
                    kennung, neu, treffer = alt[j]["kennung"], False, round(float(s[g, j]), 4)
                    benutzt.add(j)
                break
        if kennung is None:
            hoechste += 1
            kennung = _cluster.KENNUNG_MUSTER % hoechste
        ergebnis.append({"kennung": kennung, "neu": neu, "treffer": treffer})
    return ergebnis


def beispiele_waehlen(gesichter, anzahl: int = BEISPIELE_JE_GRUPPE) -> list[dict]:
    """Bis zu ``anzahl`` Beispiel-Gesichter: nur Fotos, je Bild eines, ueber die Jahre gestreut.

    Innerhalb eines Jahres gewinnt die beste Qualitaet (Flaechenanteil x Score);
    die Jahre werden reihum bedient (neuestes zuerst), damit das Quiz die Person
    in verschiedenen Lebensphasen zeigt.
    """
    fotos = [g for g in gesichter if not g.get("video_id")]
    je_jahr: dict[str, list[dict]] = {}
    for g in sorted(fotos, key=lambda g: (-(g["anteil"] * g["score"]), g["bild_id"], g["index"])):
        jahr = (g.get("aufnahme") or "")[:4] or "????"
        je_jahr.setdefault(jahr, []).append(g)
    jahre = sorted(je_jahr, reverse=True)
    gewaehlt: list[dict] = []
    bilder: set = set()
    while len(gewaehlt) < anzahl and any(je_jahr[j] for j in jahre):
        for jahr in jahre:
            while je_jahr[jahr]:
                g = je_jahr[jahr].pop(0)
                if g["bild_id"] not in bilder:
                    gewaehlt.append(g)
                    bilder.add(g["bild_id"])
                    break
            if len(gewaehlt) >= anzahl:
                break
    return [{k: g.get(k) for k in ("bild_id", "index", "bbox", "breite", "hoehe",
                                   "anteil", "score", "aufnahme")} for g in gewaehlt]


def lauf_rechnen(eingelesen, altbestand=None, bestaetigt=None, vorgaben=None,
                 zuordnung=ZUORDNUNG_AEHNLICH, verschmelzen=VERSCHMELZ_AEHNLICH,
                 zwilling=ZWILLING_AEHNLICH, min_groesse=MIN_GROESSE,
                 runden=VERFEINERN_RUNDEN) -> dict:
    """Ganzer Lauf ohne Schreiben: gruppieren, Kennungen, Beispiele, Bericht."""
    gesichter = eingelesen["gesichter"]
    v = eingelesen["vektoren"]
    bild_ids = [g["bild_id"] for g in gesichter]
    q = np.array([g["anteil"] * g["score"] for g in gesichter], dtype=float)
    namen = dict(bestaetigt or {})
    vorg = vorgaben or {"gleich": set(), "verschieden": set()}

    def vorab(mitte):
        return [e["kennung"] if not e["neu"] else None
                for e in kennungen_vergeben(mitte, altbestand)] if altbestand else [None] * len(mitte)

    def verschieden(a, b):
        if tuple(sorted((a, b))) in vorg["verschieden"]:
            return True
        return bool(namen.get(a) and namen.get(b) and namen[a] != namen[b])

    start = time.monotonic()
    erg = gruppieren(v, bild_ids, q, zuordnung, verschmelzen, min_groesse, runden,
                     vorab_kennung=vorab, verschieden=verschieden, gleich=vorg["gleich"])
    label, k = erg["label"], erg["k"]
    mitte, groessen = _mittelpunkte(v, label, k)
    kennungen = kennungen_vergeben(mitte, altbestand)
    paare = zwillings_kandidaten(v, bild_ids, label, k, zwilling)

    je_gruppe: list[list[dict]] = [[] for _ in range(k)]
    regeln = vorg.get("ausgeschlossen") or set()
    ausgeschlossen = 0
    for g, c in zip(gesichter, label.tolist()):
        g["kennung"] = kennungen[c]["kennung"] if c >= 0 else None
        if c >= 0 and (g["kennung"], str(g["bild_id"]), int(g.get("index") or 0)) in regeln:
            # Nutzer-Regel: dieses Gesicht gehoert NICHT zu diesem Vorschlag.
            g["kennung"] = None
            ausgeschlossen += 1
            continue
        if c >= 0:
            je_gruppe[c].append(g)
    kandidaten: list[list[dict]] = [[] for _ in range(k)]
    for p in paare:
        for eigen, fremd in ((p["a"], p["b"]), (p["b"], p["a"])):
            if len(kandidaten[eigen]) < ZWILLING_KANDIDATEN_JE_GRUPPE:
                kandidaten[eigen].append({"kennung": kennungen[fremd]["kennung"],
                                          "aehnlich": p["aehnlich"],
                                          "gemeinsame_bilder": p["gemeinsame_bilder"]})
    gruppen = []
    for c in range(k):
        mitglieder = je_gruppe[c]
        daten = sorted(d for d in (m.get("aufnahme") for m in mitglieder) if d)
        gruppen.append({
            "kennung": kennungen[c]["kennung"],
            "neu": kennungen[c]["neu"],
            "name": namen.get(kennungen[c]["kennung"]),
            "groesse": len(mitglieder),
            "bilder": len({m["bild_id"] for m in mitglieder if not m.get("video_id")}),
            "videos": len({m["video_id"] for m in mitglieder if m.get("video_id")}),
            "von": daten[0][:10] if daten else None,
            "bis": daten[-1][:10] if daten else None,
            "zwilling_kandidaten": kandidaten[c],
            "beispiele": beispiele_waehlen(mitglieder),
        })
    rauschen = int((label < 0).sum())
    bericht = {
        "dateien": [{"datei": os.path.basename(d["pfad"]), "zeilen": d["zeilen"],
                     "ungueltig": d["ungueltig"]} for d in eingelesen["dateien"]],
        "bilder": eingelesen["bilder"], "doppelt": eingelesen["doppelt"],
        "bilder_gruppiert": eingelesen["bilder_gruppiert"],
        "je_grund": dict(sorted(eingelesen["je_grund"].items())),
        "gesichter": len(gesichter), "gruppen": k,
        "gesichter_in_gruppen": len(gesichter) - rauschen, "rauschen": rauschen,
        "groessen_top10": [int(x) for x in groessen[:10]],
        "gruppen_ab_50": int((groessen >= 50).sum()) if k else 0,
        "gruppen_ab_10": int((groessen >= 10).sum()) if k else 0,
        "kennungen_neu": sum(1 for e in kennungen if e["neu"]),
        "kennungen_wiederverwendet": sum(1 for e in kennungen if not e["neu"]),
        "namen_bestaetigt": sum(1 for g in gruppen if g["name"]),
        "aehnliche_paare": len(paare),
        "ausgeschlossen_nach_regel": ausgeschlossen,
        "davon_mit_gemeinsamen_bildern": sum(1 for p in paare if p["gemeinsame_bilder"]),
        "sekunden": round(time.monotonic() - start, 1),
    }
    altbestand_neu = [{"kennung": kennungen[c]["kennung"],
                       "mittelpunkt": [float(x) for x in mitte[c]]} for c in range(k)]
    return {"gesichter": gesichter, "gruppen": gruppen, "bericht": bericht,
            "altbestand": altbestand_neu}


# ── Schreiben ────────────────────────────────────────────────────────────

def _atomar(pfad, schreiber):
    pruefe_ausserhalb_repo(pfad)
    os.makedirs(os.path.dirname(os.path.abspath(pfad)), exist_ok=True)
    temp = pfad + ".tmp"
    with open(temp, "w", encoding="utf-8", newline="\n") as datei:
        schreiber(datei)
    os.replace(temp, pfad)
    return pfad


FELDER_ZUORDNUNG = ("bild_id", "index", "kennung", "bbox", "breite", "hoehe",
                    "anteil", "score", "aufnahme", "video_id", "zeit_s")


def schreiben(lauf, ausgabe, stand=None) -> list[str]:
    """Die drei Dateien schreiben (atomar, ausserhalb des Repos)."""
    pruefe_ausserhalb_repo(ausgabe)
    stand = stand or datetime.datetime.now().isoformat(timespec="seconds")

    def zuordnung(datei):
        for g in lauf["gesichter"]:
            datei.write(json.dumps({k: g.get(k) for k in FELDER_ZUORDNUNG},
                                   ensure_ascii=False) + "\n")

    def beispiele(datei):
        json.dump({"stand": stand, "verfahren": "mittelpunkt",
                   "gruppen": lauf["gruppen"]}, datei, ensure_ascii=False, indent=1)
        datei.write("\n")

    def kennungen(datei):
        json.dump({"stand": stand, "kennungen": lauf["altbestand"]}, datei,
                  ensure_ascii=False)
        datei.write("\n")

    return [_atomar(os.path.join(ausgabe, DATEI_ZUORDNUNG), zuordnung),
            _atomar(os.path.join(ausgabe, DATEI_BEISPIELE), beispiele),
            _atomar(os.path.join(ausgabe, DATEI_KENNUNGEN), kennungen)]


def bericht_text(b) -> str:
    zeilen = [f"Datei {d['datei']}: {d['zeilen']} Zeilen, {d['ungueltig']} ungueltig"
              for d in b["dateien"]]
    zeilen += [
        f"Bilder: {b['bilder']} (doppelt uebersprungen: {b['doppelt']}), "
        f"gruppiert: {b['bilder_gruppiert']}",
        "Je Grund: " + ", ".join(f"{k}: {v}" for k, v in b["je_grund"].items()),
        f"Gesichter: {b['gesichter']} -> in Gruppen: {b['gesichter_in_gruppen']}, "
        f"Rauschen: {b['rauschen']}",
        f"Gruppen: {b['gruppen']} (ab 50 Gesichter: {b['gruppen_ab_50']}, ab 10: "
        f"{b['gruppen_ab_10']}), groesste: {', '.join(map(str, b['groessen_top10'])) or '-'}",
        f"Kennungen neu: {b['kennungen_neu']}, wiederverwendet: "
        f"{b['kennungen_wiederverwendet']}, Namen bestaetigt: {b['namen_bestaetigt']}",
        f"Aehnliche, getrennte Gruppenpaare: {b['aehnliche_paare']} "
        f"(davon mit gemeinsamen Bildern = sicher zwei Menschen: "
        f"{b['davon_mit_gemeinsamen_bildern']})",
        f"Nach Nutzer-Regel aus einem Vorschlag genommen: {b.get('ausgeschlossen_nach_regel', 0)} Gesichter",
        f"Rechenzeit: {b['sekunden']} s",
    ]
    return "\n".join(zeilen)


# ── Nachtragen (neue Gesichter an bestehende Gruppen haengen) ────────────
#
# Anlass (06.10.2026): die 842 Fotobuch-Fotos waren nie in der Gesichter-
# erkennung. Ein voller Neu-Lauf bringt die schon benannten Gruppen durchein-
# ander (gemessen: eine Gruppe behielt 22 % ihrer Gesichter, 27 Gesichter
# wanderten zu einer anderen benannten Person). Dieser Weg haengt nur die NEUEN
# Gesichter an; alte Zuordnung und alte Mittelpunkte bleiben unberuehrt.

FELDER_BEISPIEL = ("bild_id", "index", "bbox", "breite", "hoehe",
                   "anteil", "score", "aufnahme")


def zuordnung_zeilen_lesen(pfad) -> list[str]:
    """Die bestehende Zuordnung als ROHE Zeilen lesen — 1:1 weiterreichen."""
    if not os.path.isfile(pfad):
        raise PersonenFehler(f"Zuordnungsdatei nicht gefunden: {pfad}")
    try:
        with open(pfad, encoding="utf-8", newline="") as datei:
            return datei.read().splitlines(keepends=True)
    except OSError as problem:
        raise PersonenFehler(
            f"Zuordnungsdatei nicht lesbar ({problem.__class__.__name__}): {pfad}") from None


def beispiele_lesen(pfad) -> dict:
    """Bestehende Quiz-Beispiele lesen: ``{kennung: gruppe}`` (fehlend = leer)."""
    daten = _json_lesen(pfad, {})
    roh = daten.get("gruppen") if isinstance(daten, dict) else None
    ergebnis: dict[str, dict] = {}
    for gruppe in roh or []:
        if isinstance(gruppe, dict) and isinstance(gruppe.get("kennung"), str):
            ergebnis.setdefault(gruppe["kennung"], gruppe)
    return ergebnis


def _schluessel(gesicht) -> tuple:
    """Der Schluessel eines Gesichts: ``(bild_id, index)`` — wie in der Zuordnung."""
    try:
        index = int(gesicht.get("index") or 0)
    except (TypeError, ValueError):
        index = 0
    return (str(gesicht.get("bild_id")), index)


def _gruppe_bauen(kennung, mitglieder, name=None, neu=True, zwilling=None) -> dict:
    """Eine Gruppe im Format von ``lauf_rechnen`` (fuer Beispiele/Quiz)."""
    daten = sorted(d for d in (m.get("aufnahme") for m in mitglieder) if d)
    return {
        "kennung": kennung,
        "neu": bool(neu),
        "name": name,
        "groesse": len(mitglieder),
        "bilder": len({m["bild_id"] for m in mitglieder if not m.get("video_id")}),
        "videos": len({m["video_id"] for m in mitglieder if m.get("video_id")}),
        "von": daten[0][:10] if daten else None,
        "bis": daten[-1][:10] if daten else None,
        "zwilling_kandidaten": list(zwilling or []),
        "beispiele": beispiele_waehlen(mitglieder),
    }


def _mittelpunkt(vektoren) -> list[float]:
    """Mittelpunkt eines Haufens Gesichtsvektoren (Einheitslaenge, wie kennungen.json)."""
    m = einheitsvektoren(np.asarray(vektoren, dtype=np.float32))
    if m.shape[0] == 0:
        return []
    mitte = einheitsvektoren(m.mean(axis=0, keepdims=True).astype(np.float32))
    return [float(x) for x in mitte[0]]


def _vorher_sichern(ausgabe) -> list[str]:
    """Die drei Dateien VOR dem Schreiben als ``*.vorher`` kopieren (Rueckweg).

    Eine vorhandene Sicherung wird **nicht** ueberschrieben — sie ist der Stand
    vor dem ersten Nachtragen und bleibt als Rueckweg erhalten.
    """
    ergebnis: list[str] = []
    for name in (DATEI_ZUORDNUNG, DATEI_BEISPIELE, DATEI_KENNUNGEN):
        quelle = os.path.join(ausgabe, name)
        ziel = quelle + ".vorher"
        if os.path.isfile(quelle) and not os.path.exists(ziel):
            shutil.copy2(quelle, ziel)
            ergebnis.append(ziel)
    return ergebnis


def nachtrag_rechnen(eingelesen, alte_zeilen, alt_kennungen, beispiele_alt=None,
                     bestaetigt=None, vorgaben=None,
                     zuordnung: float = ZUORDNUNG_AEHNLICH,
                     min_groesse: int = MIN_GROESSE,
                     runden: int = VERFEINERN_RUNDEN) -> dict:
    """Neue Gesichter an BESTEHENDE Gruppen haengen — ohne Neu-Rechnen.

    ``alte_zeilen`` = rohe Zeilen der ``gesicht_zuordnung.jsonl``,
    ``alt_kennungen`` = rohe Liste aus ``kennungen.json`` (beide unveraendert
    weitergereicht), ``beispiele_alt`` = bestehende Gruppen aus
    ``personen_beispiele.json``. Rueckgabe ``{"neu": {stelle: kennung|null},
    "zuwachs": {kennung: [stellen]}, "gruppen_alt": [...], "gruppen_neu": [...],
    "kennungen_neu": [{"kennung", "mittelpunkt"}], "bericht": {...}}``.
    """
    start = time.monotonic()
    gesichter = eingelesen["gesichter"]
    v = einheitsvektoren(eingelesen["vektoren"])
    namen = dict(bestaetigt or {})
    regeln = (vorgaben or {}).get("ausgeschlossen") or set()

    # ── 1) alte Zuordnung auswerten (nur lesend; nichts wird veraendert) ──
    vorhanden: set = set()
    groesse_alt: dict[str, int] = {}
    bilder_je_kennung: dict[str, set] = {}
    fotos_je_kennung: dict[str, set] = {}
    videos_je_kennung: dict[str, set] = {}
    daten_je_kennung: dict[str, list] = {}
    for roh in alte_zeilen:
        try:
            eintrag = json.loads(roh)
        except ValueError:
            continue
        if not isinstance(eintrag, dict) or eintrag.get("bild_id") in (None, ""):
            continue
        schluessel = _schluessel(eintrag)
        vorhanden.add(schluessel)
        kennung = eintrag.get("kennung") or None
        if not kennung:
            continue
        kennung = str(kennung)
        bild = schluessel[0]
        groesse_alt[kennung] = groesse_alt.get(kennung, 0) + 1
        bilder_je_kennung.setdefault(kennung, set()).add(bild)
        if eintrag.get("video_id") in (None, ""):
            fotos_je_kennung.setdefault(kennung, set()).add(bild)
        else:
            videos_je_kennung.setdefault(kennung, set()).add(str(eintrag["video_id"]))
        if isinstance(eintrag.get("aufnahme"), str) and eintrag["aufnahme"]:
            daten_je_kennung.setdefault(kennung, []).append(eintrag["aufnahme"])

    # ── 2) neue Gesichter: schon vorhandene ueberspringen (idempotent) ──
    neue = [i for i, g in enumerate(gesichter) if _schluessel(g) not in vorhanden]
    uebersprungen = len(gesichter) - len(neue)

    # ── 3) andocken: aehnlichster alter Mittelpunkt ueber der Schwelle ──
    alt = _cluster.altbestand_lesen(alt_kennungen)
    kennungen_alt = [e["kennung"] for e in alt]
    m_alt = (einheitsvektoren(np.asarray([e["mittelpunkt"] for e in alt], dtype=np.float32))
             if alt else None)
    ziel: dict[int, str | None] = {}
    neu_bilder: dict[str, set] = {}
    for i in sorted(neue, key=lambda i: -(gesichter[i]["anteil"] * gesichter[i]["score"])):
        bild, index = _schluessel(gesichter[i])
        treffer = None
        if m_alt is not None and m_alt.shape[0]:
            s = m_alt @ v[i]
            kandidaten = np.nonzero(s >= zuordnung)[0]
            for c in kandidaten[np.argsort(-s[kandidaten], kind="stable")].tolist():
                kennung = kennungen_alt[c]
                if bild in bilder_je_kennung.get(kennung, ()) or bild in neu_bilder.get(kennung, ()):
                    continue                    # cannot-link: zwei Gesichter, ein Bild
                if (kennung, bild, index) in regeln:
                    continue                    # Nutzer-Regel „nicht diese Person"
                treffer = kennung
                break
        ziel[i] = treffer
        if treffer:
            neu_bilder.setdefault(treffer, set()).add(bild)
    zuwachs: dict[str, list[int]] = {}
    for i, kennung in ziel.items():
        if kennung:
            zuwachs.setdefault(kennung, []).append(i)
    angedockt = sum(len(x) for x in zuwachs.values())

    # ── 4) Rest untereinander gruppieren — neue Kennungen hinter der hoechsten ──
    rest = [i for i in neue if not ziel.get(i)]
    gruppen_neu: list[dict] = []
    kennungen_neu: list[dict] = []
    mitglieder_neu: dict[str, list[int]] = {}
    if rest:
        rq = np.array([gesichter[i]["anteil"] * gesichter[i]["score"] for i in rest])
        erg = gruppieren(v[rest], [str(gesichter[i]["bild_id"]) for i in rest], rq,
                         zuordnung, VERSCHMELZ_AEHNLICH, min_groesse, runden)
        hoechste = _cluster._naechste_nummer(sorted(kennungen_alt))
        for c in range(erg["k"]):
            stellen = [rest[j] for j in np.nonzero(erg["label"] == c)[0].tolist()]
            hoechste += 1
            kennung = _cluster.KENNUNG_MUSTER % hoechste
            for i in stellen:
                ziel[i] = kennung
            mitglieder_neu[kennung] = stellen
            kennungen_neu.append({"kennung": kennung,
                                  "mittelpunkt": _mittelpunkt(v[stellen])})
            gruppen_neu.append(_gruppe_bauen(kennung, [gesichter[i] for i in stellen],
                                             name=namen.get(kennung), neu=True))

    # ── 5) bestehende Gruppen fortschreiben (nur Zuwachs, nichts verschieben) ──
    alt_gruppen = dict(beispiele_alt or {})
    reihenfolge = list(alt_gruppen) + [k for k in sorted(kennungen_alt) if k not in alt_gruppen]
    gruppen_alt: list[dict] = []
    for kennung in reihenfolge:
        bekannt = alt_gruppen.get(kennung) or {}
        zu_gesichter = [gesichter[i] for i in zuwachs.get(kennung, [])]
        daten = list(daten_je_kennung.get(kennung, []))
        daten += [g["aufnahme"] for g in zu_gesichter
                  if isinstance(g.get("aufnahme"), str) and g["aufnahme"]]
        daten.sort()
        gruppen_alt.append({
            "kennung": kennung,
            "neu": bool(bekannt.get("neu", False)),
            "name": bekannt.get("name") or namen.get(kennung),
            "groesse": groesse_alt.get(kennung, 0) + len(zu_gesichter),
            "bilder": len(fotos_je_kennung.get(kennung, set())
                          | {str(g["bild_id"]) for g in zu_gesichter if not g.get("video_id")}),
            "videos": len(videos_je_kennung.get(kennung, set())
                          | {str(g["video_id"]) for g in zu_gesichter if g.get("video_id")}),
            "von": daten[0][:10] if daten else None,
            "bis": daten[-1][:10] if daten else None,
            "zwilling_kandidaten": list(bekannt.get("zwilling_kandidaten") or []),
            "beispiele": beispiele_waehlen(
                list(bekannt.get("beispiele") or []) + zu_gesichter),
        })

    # Zwillings-Kandidaten der neuen Gruppen (nur markieren, nie zusammenlegen)
    if gruppen_neu:
        m_neu = einheitsvektoren(np.asarray([e["mittelpunkt"] for e in kennungen_neu],
                                            dtype=np.float32))
        for pos, gruppe in enumerate(gruppen_neu):
            kennung = gruppe["kennung"]
            meine = {str(gesichter[i]["bild_id"]) for i in mitglieder_neu[kennung]}
            zwillinge: list[dict] = []
            if m_alt is not None and m_alt.shape[0]:
                s = m_alt @ m_neu[pos]
                for c in np.argsort(-s, kind="stable").tolist():
                    if s[c] < ZWILLING_AEHNLICH:
                        break
                    fremd = kennungen_alt[c]
                    zwillinge.append({
                        "kennung": fremd, "aehnlich": round(float(s[c]), 3),
                        "gemeinsame_bilder": len(meine & bilder_je_kennung.get(fremd, set()))})
            for pos2, andere in enumerate(gruppen_neu):
                if pos2 == pos:
                    continue
                w = float(m_neu[pos2] @ m_neu[pos])
                if w >= ZWILLING_AEHNLICH:
                    fremde_bilder = {str(gesichter[i]["bild_id"])
                                     for i in mitglieder_neu[andere["kennung"]]}
                    zwillinge.append({"kennung": andere["kennung"], "aehnlich": round(w, 3),
                                      "gemeinsame_bilder": len(meine & fremde_bilder)})
            zwillinge.sort(key=lambda k: -k["aehnlich"])
            gruppe["zwilling_kandidaten"] = zwillinge[:ZWILLING_KANDIDATEN_JE_GRUPPE]

    rauschen = sum(1 for i in neue if not ziel.get(i))
    bericht = {
        "alt_zeilen": len(alte_zeilen),
        "alt_gesichter": len(vorhanden),
        "alt_gruppen": len(kennungen_alt),
        "neue_gesichter": len(neue),
        "uebersprungen": uebersprungen,
        "angedockt": angedockt,
        "gruppen_mit_zuwachs": len(zuwachs),
        "neue_gruppen": len(gruppen_neu),
        "neue_kennungen": [e["kennung"] for e in kennungen_neu],
        "rauschen": rauschen,
        "sekunden": round(time.monotonic() - start, 1),
    }
    return {"neu": ziel, "gesichter": gesichter, "zuwachs": zuwachs,
            "gruppen_alt": gruppen_alt, "gruppen_neu": gruppen_neu,
            "kennungen_neu": kennungen_neu, "alt_kennungen": list(alt_kennungen or []),
            "bericht": bericht}


def nachtrag_schreiben(lauf, ausgabe, alte_zeilen, stand=None) -> dict:
    """Zuordnung + Beispiele + Kennungen schreiben (atomar, ausserhalb des Repos).

    Die alten Zeilen kommen **wortgleich** zurueck in die Datei, dahinter die
    neuen; vorher werden die drei Dateien als ``*.vorher`` gesichert (Rueckweg).
    """
    pruefe_ausserhalb_repo(ausgabe)
    stand = stand or datetime.datetime.now().isoformat(timespec="seconds")
    sicherungen = _vorher_sichern(ausgabe)

    neu_zeilen = []
    for i in sorted(lauf["neu"]):
        g = lauf["gesichter"][i]
        eintrag = {k: g.get(k) for k in FELDER_ZUORDNUNG}
        eintrag["index"] = int(g.get("index") or 0)
        eintrag["kennung"] = lauf["neu"][i]
        neu_zeilen.append(json.dumps(eintrag, ensure_ascii=False))

    def zuordnung(datei):
        for roh in alte_zeilen:
            datei.write(roh if roh.endswith("\n") else roh + "\n")
        for zeile in neu_zeilen:
            datei.write(zeile + "\n")

    def beispiele(datei):
        json.dump({"stand": stand, "verfahren": "mittelpunkt-nachtrag",
                   "gruppen": lauf["gruppen_alt"] + lauf["gruppen_neu"]},
                  datei, ensure_ascii=False, indent=1)
        datei.write("\n")

    def kennungen(datei):
        json.dump({"stand": stand,
                   "kennungen": list(lauf["alt_kennungen"]) + lauf["kennungen_neu"]},
                  datei, ensure_ascii=False)
        datei.write("\n")

    geschrieben = [
        _atomar(os.path.join(ausgabe, DATEI_ZUORDNUNG), zuordnung),
        _atomar(os.path.join(ausgabe, DATEI_BEISPIELE), beispiele),
        _atomar(os.path.join(ausgabe, DATEI_KENNUNGEN), kennungen),
    ]
    return {"geschrieben": geschrieben, "sicherungen": sicherungen}


def nachtrag_bericht_text(b) -> str:
    """Bericht des Nachtragens — nur Zahlen, keine Namen, keine Pfade."""
    kennungen = b["neue_kennungen"]
    return "\n".join([
        f"Alte Zuordnung: {b['alt_zeilen']} Zeilen, {b['alt_gesichter']} Gesichter, "
        f"{b['alt_gruppen']} Kennungen (wortgleich uebernommen)",
        f"Neue Gesichter: {b['neue_gesichter']} "
        f"(schon vorhanden, uebersprungen: {b['uebersprungen']})",
        f"Angedockt an bestehende Gruppen: {b['angedockt']} Gesichter in "
        f"{b['gruppen_mit_zuwachs']} Gruppen",
        f"Neue Gruppen: {b['neue_gruppen']}"
        + (f" (Kennungen {kennungen[0]}..{kennungen[-1]})" if kennungen else ""),
        f"Nicht angedockt (Rauschen): {b['rauschen']}",
        f"Rechenzeit: {b['sekunden']} s",
    ])


def _nachtragen_main(args, pfade, schreiben_an) -> int:
    """Der ``--nachtragen``-Weg: lesen, andocken, nur mit ``--schreiben`` schreiben."""
    katalog = _cluster.katalog_lesen(args.katalog) if args.katalog else {}
    kennungen_roh = _json_lesen(os.path.join(args.ausgabe, DATEI_KENNUNGEN), {})
    alt_kennungen = (kennungen_roh.get("kennungen") if isinstance(kennungen_roh, dict)
                     else kennungen_roh) or []
    print("Personen nachtragen — " + ("Schreiben ist eingeschaltet" if schreiben_an
                                      else "Trockenlauf (es wird NICHTS geschrieben)"))
    alte_zeilen = zuordnung_zeilen_lesen(os.path.join(args.ausgabe, DATEI_ZUORDNUNG))
    if not alte_zeilen:
        raise PersonenFehler(
            "Die bestehende Zuordnung ist leer — ohne sie gibt es nichts zum Andocken.")
    if not alt_kennungen:
        raise PersonenFehler(
            "Keine alten Mittelpunkte (kennungen.json) — ohne sie gibt es nichts zum Andocken.")
    eingelesen = gesichter_lesen(pfade, katalog)
    lauf = nachtrag_rechnen(
        eingelesen, alte_zeilen, alt_kennungen,
        beispiele_alt=beispiele_lesen(os.path.join(args.ausgabe, DATEI_BEISPIELE)),
        bestaetigt=bestaetigt_lesen(args.bestaetigt),
        vorgaben=vorgaben_lesen(args.vorgaben),
        zuordnung=args.zuordnung, min_groesse=args.min_groesse)
    print(nachtrag_bericht_text(lauf["bericht"]))
    if not schreiben_an:
        print("Ohne --schreiben wurde NICHTS geschrieben.")
        return 0
    if not lauf["bericht"]["neue_gesichter"]:
        print("Nichts zu tun: alle Gesichter stehen schon in der Zuordnung "
              "(es wurde NICHTS geschrieben).")
        return 0
    ergebnis = nachtrag_schreiben(lauf, args.ausgabe, alte_zeilen)
    for pfad in ergebnis["sicherungen"]:
        print(f"gesichert: {os.path.basename(pfad)}")
    for pfad in ergebnis["geschrieben"]:
        print(f"geschrieben: {os.path.basename(pfad)}")
    return 0


def main(argv=None) -> int:
    zerleger = argparse.ArgumentParser(
        description="Gruppiert alle Gesichter zu Personen (Mittelpunkt-Verfahren, "
                    "cannot-link je Bild) und schreibt Zuordnung + Quiz-Beispiele. "
                    "Loescht nichts, ruft kein Netz, zeigt nur Zahlen.")
    zerleger.add_argument("--vektoren", action="append", default=None,
                          help="Vektordatei (wiederholbar); Standard: die drei "
                               "Dateien aus Aufgabe 1, Aufgabe 3 und Videos")
    zerleger.add_argument("--ausgabe", default=STANDARD_AUSGABE,
                          help="Ausgabeordner (PFLICHT ausserhalb des Repos)")
    zerleger.add_argument("--katalog", default=None, help="Personen-Katalog (optional)")
    zerleger.add_argument("--bestaetigt", default=STANDARD_BESTAETIGT)
    zerleger.add_argument("--vorgaben", default=STANDARD_VORGABEN)
    zerleger.add_argument("--zuordnung", type=float, default=ZUORDNUNG_AEHNLICH)
    zerleger.add_argument("--verschmelzen", type=float, default=VERSCHMELZ_AEHNLICH)
    zerleger.add_argument("--zwilling", type=float, default=ZWILLING_AEHNLICH)
    zerleger.add_argument("--min-groesse", type=int, default=MIN_GROESSE)
    zerleger.add_argument("--nachtragen", action="append", default=None,
                          help="Vektordatei(en) NUR an die bestehenden Gruppen haengen "
                               "(nichts neu rechnen; Trockenlauf ist Standard, "
                               "--schreiben schreibt, vorher *.vorher-Sicherung)")
    zerleger.add_argument("--trocken", action="store_true", help="nichts schreiben (Vorrang)")
    zerleger.add_argument("--schreiben", action="store_true", help="wirklich schreiben")
    args = zerleger.parse_args(argv)

    pruefe_ausserhalb_repo(args.ausgabe)
    nachtragen = list(args.nachtragen or [])
    pfade = args.vektoren or [p for p in STANDARD_VEKTOREN if os.path.isfile(p)]
    schreiben_an = bool(args.schreiben) and not bool(args.trocken)
    try:
        if nachtragen:
            return _nachtragen_main(args, nachtragen, schreiben_an)
        if not pfade:
            raise PersonenFehler("Keine Vektordatei gefunden (Standardpfade fehlen).")
        katalog = _cluster.katalog_lesen(args.katalog) if args.katalog else {}
        altbestand = _cluster.altbestand_lesen_datei(
            os.path.join(args.ausgabe, DATEI_KENNUNGEN))
        print("Personen gruppieren — " + ("Schreiben ist eingeschaltet" if schreiben_an
                                           else "Trockenlauf (es wird NICHTS geschrieben)"))
        eingelesen = gesichter_lesen(pfade, katalog)
        lauf = lauf_rechnen(eingelesen, altbestand=altbestand,
                            bestaetigt=bestaetigt_lesen(args.bestaetigt),
                            vorgaben=vorgaben_lesen(args.vorgaben),
                            zuordnung=args.zuordnung, verschmelzen=args.verschmelzen,
                            zwilling=args.zwilling, min_groesse=args.min_groesse)
        print(bericht_text(lauf["bericht"]))
        if schreiben_an:
            for pfad in schreiben(lauf, args.ausgabe):
                print(f"geschrieben: {os.path.basename(pfad)}")
        else:
            print("Ohne --schreiben wurde NICHTS geschrieben.")
        return 0
    except (PersonenFehler, ValueError) as problem:
        print(f"Fehler: {problem}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
