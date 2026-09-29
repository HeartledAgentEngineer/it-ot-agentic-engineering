"""Anzeigenamen-VORSCHLAEGE fuer die Anlaesse, regelbasiert (Nachtlauf N-0929, Schritt 4).

Wozu dieses Werkzeug:
  ``ereignisse.jsonl`` (``ereignisse_bauen.py``) fuehrt je Anlass einen Knoten
  mit Thema und Datum, aber ohne lesbaren Namen. Dieses Werkzeug schlaegt aus
  den vorhandenen Angaben einen **Anzeigenamen** vor, z. B.
  ``"Toskana, Juni 2022 - Urlaub"`` — und markiert, welche Anlaesse vermutlich
  **Reisen** sind (Ort ist nicht der Wohnort), damit die Oberflaeche sie spaeter
  "nach oben" holen kann.

Was dieses Werkzeug bewusst NICHT tut:
  * **Kein Sprachmodell, kein Netz, keine Bilder.** Reine Regeln ueber lokale
    JSONL-Dateien.
  * **ereignisse.jsonl wird NIE geschrieben** (nur gelesen). Die Ausgabe ist
    eine **Ableitung**: sie wird bei ``--schreiben`` komplett neu berechnet und
    **atomar** ersetzt (temp-Datei + ``os.replace``). Ein Vorschlag ist nur ein
    Vorschlag; benannt wird nichts endgueltig.
  * **Kein Schreiben ohne ``--schreiben``.** Standard ist der Trockenlauf.
  * **Keine Ausgabe im Repo:** ein Zielpfad im Repo (oder die Eingabedatei
    selbst) endet mit ``SystemExit(2)``.
  * **Keine Namen/Orte in der Konsole** — nur Zaehler.

Eingaben (Vorgaben unter ``~/foto_sortierung/``):
  * ``ereignisse.jsonl`` (Pflicht): genutzt werden ``kennung``,
    ``datei_kennungen`` (pCloud-fileids, gleich ``bild_id`` als Text),
    ``datum`` (``JJJJ-MM-TT``, Rueckfall fuer den Zeitraum), ``jahr`` (zweiter
    Rueckfall) und ``thema``.
  * ``orte.jsonl`` (optional, ``orte_zuordnen.py``): je ``bild_id`` ``land_code``,
    ``land``, ``region``, ``ort``, ``aufnahme`` (``JJJJ-MM-TTTHH:MM:SS``).
    Fehlt die Datei, entstehen Vorschlaege nur aus Handordner/Zeit/Thema.
  * Handordner-Zuordnung (optional, wird spaeter von Hermes erzeugt), JSONL,
    **je Bild eine Zeile**::

        {"bild_id": "12345", "handordner": "Konzerte_Party/2016"}

    ``bild_id`` ist die pCloud-fileid als Text (oder Zahl). ``handordner`` ist
    der Pfad relativ zum Handy-Ordner mit ``/`` (``\\`` wird toleriert). Ein
    Segment aus vier Ziffern (``19xx``/``20xx``) gilt als **Jahresordner** und
    wird zur Zeitangabe; das letzte uebrige Segment ist der Name
    (Unterstriche werden zu Leerzeichen).

Regeln (Prioritaet von oben nach unten):
  1. **Handordner**: liegt die **Mehrheit** (mehr als die Haelfte) der Bilder
     des Anlasses im selben Handordner, fuehrt dieser Name; ein Jahresordner
     ersetzt den errechneten Zeitraum. ``regel = "handordner"``.
  2. **Ort**: haeufigster ``ort`` der Bilder. Verteilen sich die Bilder auf
     **mindestens 3 verschiedene Orte derselben Region**, steht die **Region**
     (``regel = "region"``); bei mindestens 3 Orten desselben Landes ueber
     mehrere Regionen das **Land** (``regel = "land"``); sonst der **Ort**
     (``regel = "ort"``). Zeitraum aus den Aufnahmedaten ("Juni 2022",
     Monatsgrenze "Juli-August 2014", Jahresgrenze "Dezember 2013-Januar 2014");
     fehlen Aufnahmedaten, dienen ``datum`` bzw. ``jahr`` des Anlasses.
  3. **Thema** nur als Zusatz; "Sonstiges" (und leeres Thema) entfaellt.
  4. Ohne Ort und Handordner bleibt der ehrliche Rueckfall ``"<Zeitraum> - <Thema>"``
     (``regel = "nur_zeit"``); fehlt auch das, steht ``"Anlass ohne Angaben"``.

Format: ``"<Ort/Region/Handordner>, <Zeitraum> - <Thema>"`` (der Gedankenstrich
vor dem Thema ist ein Halbgeviertstrich mit Leerzeichen); fehlende Teile
entfallen samt Trennzeichen.

Heimat und Reise:
  ``heimat_verdacht`` ist ``true``, wenn der haeufigste Ort des Anlasses der
  insgesamt haeufigste Ort ueber **alle** Anlaesse ist (vermutlich Wohnort).
  ``reise`` ist ``true``, wenn das nicht so ist **und** ein Ort oder Land
  bekannt ist.

Ausgabe (JSONL, ``ensure_ascii=True``, ``sort_keys=True``; Standard
``~/foto_sortierung/anlass_namen.jsonl``), je Anlass eine Zeile in der
Reihenfolge der Ereignisdatei::

    {"kennung", "vorschlag", "regel": "handordner"|"ort"|"region"|"land"|"nur_zeit",
     "ort_anteil" (0..1: Anteil der Bilder des Anlasses, die den genannten
     Handordner/Ort/Region/Land tragen), "heimat_verdacht", "reise",
     "version": 1, "erzeugt": ISO}

Aufruf::

    python tools/foto_sortierung/anlass_namen.py               # Trockenlauf
    python tools/foto_sortierung/anlass_namen.py --schreiben

Als Modul: ``haupt(argv=[...])`` sowie ``namen_ableiten``.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from collections import Counter

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_EREIGNISSE = os.path.join(STANDARD_BASIS, "ereignisse.jsonl")
STANDARD_ORTE = os.path.join(STANDARD_BASIS, "orte.jsonl")
STANDARD_HANDORDNER = os.path.join(STANDARD_BASIS, "handordner.jsonl")
STANDARD_AUSGABE = os.path.join(STANDARD_BASIS, "anlass_namen.jsonl")

VERSION = 1
REGELN = ("handordner", "ort", "region", "land", "nur_zeit")
MIN_ORTE_VERDICHTUNG = 3
RUECKFALL_NAME = "Anlass ohne Angaben"
GEDANKENSTRICH = "–"    # Halbgeviertstrich

MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember")

JAHR_MUSTER = re.compile(r"^(?:19|20)\d{2}$")
ZEIT_MUSTER = re.compile(r"^(\d{4})[-:](\d{2})")


# ── Kleine Helfer ────────────────────────────────────────────────────────

def _text(wert) -> str:
    return wert.strip() if isinstance(wert, str) else ""


def _kennung_text(wert) -> str:
    """Bild-/Dateikennung als Text (Zahl oder Text; bool/None/leer -> \"\")."""
    if wert is None or isinstance(wert, bool):
        return ""
    if isinstance(wert, (int, float)):
        return str(int(wert)) if float(wert).is_integer() else ""
    return _text(wert)


def _jsonl_lesen(pfad: str):
    """Liefert ``(zeilen, kaputt)``: gueltige JSON-Objekte und Zahl defekter Zeilen."""
    zeilen, kaputt = [], 0
    with open(pfad, encoding="utf-8") as datei:
        for zeile in datei:
            if not zeile.strip():
                continue
            try:
                eintrag = json.loads(zeile)
            except ValueError:
                kaputt += 1
                continue
            if not isinstance(eintrag, dict):
                kaputt += 1
                continue
            zeilen.append(eintrag)
    return zeilen, kaputt


def _haeufigster(zaehler: Counter):
    """Haeufigster Schluessel; bei Gleichstand der alphabetisch erste (stabil)."""
    if not zaehler:
        return None
    return sorted(zaehler.items(), key=lambda kv: (-kv[1], str(kv[0])))[0][0]


# ── Zeitraum ─────────────────────────────────────────────────────────────

def _jahr_monat(wert):
    """``(jahr, monat)`` aus ``JJJJ-MM...``/``JJJJ:MM...`` oder ``None``."""
    treffer = ZEIT_MUSTER.match(_text(wert))
    if not treffer:
        return None
    jahr, monat = int(treffer.group(1)), int(treffer.group(2))
    if not (1 <= monat <= 12) or jahr < 1800:
        return None
    return (jahr, monat)


def zeitraum_text(monate: list, jahr_rueckfall=None) -> str:
    """Zeitraum aus einer Liste ``(jahr, monat)``; leer -> nur Jahr oder ``""``.

    Ein Monat: ``Juni 2022``; ueber Monatsgrenze im selben Jahr:
    ``Juli-August 2014``; ueber die Jahresgrenze mit beiden Jahren:
    ``Dezember 2013-Januar 2014`` (Halbgeviertstrich ohne Leerzeichen).
    """
    if not monate:
        return str(jahr_rueckfall) if isinstance(jahr_rueckfall, int) and not isinstance(jahr_rueckfall, bool) else ""
    von, bis = min(monate), max(monate)
    if von == bis:
        return f"{MONATE[von[1] - 1]} {von[0]}"
    if von[0] == bis[0]:
        return f"{MONATE[von[1] - 1]}{GEDANKENSTRICH}{MONATE[bis[1] - 1]} {von[0]}"
    return (f"{MONATE[von[1] - 1]} {von[0]}{GEDANKENSTRICH}"
            f"{MONATE[bis[1] - 1]} {bis[0]}")


# ── Handordner ───────────────────────────────────────────────────────────

def handordner_zerlegen(pfad: str) -> tuple:
    """``(name, jahr)`` aus einem Handordner-Pfad; fehlende Teile ``None``."""
    segmente = [s.strip() for s in _text(pfad).replace("\\", "/").split("/") if s.strip()]
    jahr, namen = None, []
    for segment in segmente:
        if JAHR_MUSTER.match(segment):
            jahr = int(segment)
        else:
            namen.append(segment)
    name = re.sub(r"\s+", " ", namen[-1].replace("_", " ")).strip() if namen else None
    return (name or None, jahr)


# ── Lesen ────────────────────────────────────────────────────────────────

def eingaben_lesen(ereignisse: str, orte: str | None, handordner: str | None) -> tuple:
    """Alle Eingaben lesen. Rueckgabe ``(anlaesse, orte_je_bild, hand_je_bild, zahlen)``.

    Fehlende optionale Dateien sind leer (kein Fehler); kaputte Zeilen werden
    gezaehlt. ``anlaesse``: Liste ``{"kennung", "bilder", "datum", "jahr", "thema"}``
    in Dateireihenfolge (Knoten ohne ``kennung`` zaehlen als kaputt).
    """
    zahlen = {"kaputt_ereignisse": 0, "kaputt_orte": 0, "kaputt_handordner": 0,
              "orte_vorhanden": False, "handordner_vorhanden": False}
    zeilen, zahlen["kaputt_ereignisse"] = _jsonl_lesen(ereignisse)
    anlaesse = []
    for zeile in zeilen:
        kennung = _text(zeile.get("kennung"))
        if not kennung:
            zahlen["kaputt_ereignisse"] += 1
            continue
        roh = zeile.get("datei_kennungen")
        bilder, gesehen = [], set()
        for wert in roh if isinstance(roh, (list, tuple)) else []:
            k = _kennung_text(wert)
            if k and k not in gesehen:
                gesehen.add(k)
                bilder.append(k)
        jahr = zeile.get("jahr")
        anlaesse.append({
            "kennung": kennung, "bilder": bilder,
            "datum": _text(zeile.get("datum")),
            "jahr": jahr if isinstance(jahr, int) and not isinstance(jahr, bool) else None,
            "thema": _text(zeile.get("thema")),
        })

    orte_je_bild: dict = {}
    if orte and os.path.isfile(orte):
        zahlen["orte_vorhanden"] = True
        zeilen, zahlen["kaputt_orte"] = _jsonl_lesen(orte)
        for z in zeilen:
            bild = _kennung_text(z.get("bild_id"))
            if not bild:
                zahlen["kaputt_orte"] += 1
                continue
            orte_je_bild.setdefault(bild, {
                "land_code": _text(z.get("land_code")) or None,
                "land": _text(z.get("land")) or None,
                "region": _text(z.get("region")) or None,
                "ort": _text(z.get("ort")) or None,
                "aufnahme": _text(z.get("aufnahme")) or None,
            })

    hand_je_bild: dict = {}
    if handordner and os.path.isfile(handordner):
        zahlen["handordner_vorhanden"] = True
        zeilen, zahlen["kaputt_handordner"] = _jsonl_lesen(handordner)
        for z in zeilen:
            bild = _kennung_text(z.get("bild_id"))
            pfad = _text(z.get("handordner"))
            if not bild or not pfad:
                zahlen["kaputt_handordner"] += 1
                continue
            hand_je_bild.setdefault(bild, pfad.replace("\\", "/").strip("/"))
    return anlaesse, orte_je_bild, hand_je_bild, zahlen


# ── Ableiten ─────────────────────────────────────────────────────────────

def heimat_ort(anlaesse: list, orte_je_bild: dict):
    """Insgesamt haeufigster ``(land_code, ort)`` ueber alle Bilder aller Anlaesse."""
    zaehler: Counter = Counter()
    for anlass in anlaesse:
        for bild in anlass["bilder"]:
            o = orte_je_bild.get(bild)
            if o and o["ort"]:
                zaehler[(o["land_code"], o["ort"])] += 1
    return _haeufigster(zaehler)


def _thema_zusatz(thema: str) -> str:
    return "" if not thema or thema.strip().lower() == "sonstiges" else thema.strip()


def _zusammensetzen(ortsteil: str, zeit: str, thema: str) -> str:
    kopf = ", ".join(t for t in (ortsteil, zeit) if t)
    name = f"{kopf} {GEDANKENSTRICH} {thema}" if kopf and thema else (kopf or thema)
    return name or RUECKFALL_NAME


def _ort_entscheidung(bilder_orte: list) -> tuple:
    """``(regel, name, anzahl_bilder)`` aus den Ortszeilen der Bilder (nur mit ``ort``).

    Region/Land-Verdichtung siehe Modul-Docstring. ``(None, None, 0)`` ohne Orte.
    """
    if not bilder_orte:
        return (None, None, 0)
    # Region: >= 3 verschiedene Orte in derselben (Land, Region).
    je_region: dict = {}
    for o in bilder_orte:
        if o["region"]:
            je_region.setdefault((o["land_code"], o["region"]), []).append(o)
    kandidaten = [(len({x["ort"] for x in liste}), len(liste), schluessel)
                  for schluessel, liste in je_region.items()]
    kandidaten = [k for k in kandidaten if k[0] >= MIN_ORTE_VERDICHTUNG]
    if kandidaten:
        kandidaten.sort(key=lambda k: (-k[1], -k[0], str(k[2])))
        schluessel = kandidaten[0][2]
        return ("region", schluessel[1], kandidaten[0][1])
    # Land: >= 3 verschiedene Orte im selben Land (ueber mehrere Regionen).
    je_land: dict = {}
    for o in bilder_orte:
        name = o["land"] or o["land_code"]
        if name:
            je_land.setdefault(name, []).append(o)
    kandidaten = [(len({x["ort"] for x in liste}), len(liste), name)
                  for name, liste in je_land.items()]
    kandidaten = [k for k in kandidaten if k[0] >= MIN_ORTE_VERDICHTUNG]
    if kandidaten:
        kandidaten.sort(key=lambda k: (-k[1], -k[0], k[2]))
        return ("land", kandidaten[0][2], kandidaten[0][1])
    zaehler = Counter(o["ort"] for o in bilder_orte)
    ort = _haeufigster(zaehler)
    return ("ort", ort, zaehler[ort])


def vorschlag_fuer(anlass: dict, orte_je_bild: dict, hand_je_bild: dict,
                   heimat) -> dict:
    """Vorschlag (ohne ``version``/``erzeugt``) fuer einen Anlass."""
    bilder = anlass["bilder"]
    gesamt = len(bilder)
    ortszeilen = [orte_je_bild[b] for b in bilder if b in orte_je_bild]
    mit_ort = [o for o in ortszeilen if o["ort"]]

    # Zeitraum: Aufnahmedaten, sonst Datum des Anlasses, sonst Jahr.
    monate = [m for m in (_jahr_monat(o["aufnahme"]) for o in ortszeilen) if m]
    if not monate:
        m = _jahr_monat(anlass["datum"])
        monate = [m] if m else []
    zeit = zeitraum_text(monate, anlass["jahr"])

    # Heimat/Reise aus dem haeufigsten Ort des Anlasses.
    haupt_ort = _haeufigster(Counter((o["land_code"], o["ort"]) for o in mit_ort))
    heimat_verdacht = bool(haupt_ort is not None and heimat is not None
                           and haupt_ort == heimat)
    hat_ort_oder_land = bool(mit_ort or any(o["land"] or o["land_code"] for o in ortszeilen))
    reise = bool(not heimat_verdacht and hat_ort_oder_land)

    thema = _thema_zusatz(anlass["thema"])

    # Regel 1: Handordner-Mehrheit.
    if gesamt:
        zaehler = Counter(hand_je_bild[b] for b in bilder if b in hand_je_bild)
        if zaehler:
            pfad = _haeufigster(zaehler)
            if zaehler[pfad] * 2 > gesamt:
                name, jahr = handordner_zerlegen(pfad)
                if name:
                    zeit_h = str(jahr) if jahr is not None else zeit
                    return {"kennung": anlass["kennung"],
                            "vorschlag": _zusammensetzen(name, zeit_h, thema),
                            "regel": "handordner",
                            "ort_anteil": round(zaehler[pfad] / gesamt, 3),
                            "heimat_verdacht": heimat_verdacht, "reise": reise}

    # Regel 2: Ort / Region / Land.
    regel, name, anzahl = _ort_entscheidung(mit_ort)
    if regel:
        return {"kennung": anlass["kennung"],
                "vorschlag": _zusammensetzen(name, zeit, thema),
                "regel": regel,
                "ort_anteil": round(anzahl / gesamt, 3) if gesamt else 0.0,
                "heimat_verdacht": heimat_verdacht, "reise": reise}

    # Rueckfall: nur Zeit (+ Thema).
    return {"kennung": anlass["kennung"],
            "vorschlag": _zusammensetzen("", zeit, thema),
            "regel": "nur_zeit", "ort_anteil": 0.0,
            "heimat_verdacht": heimat_verdacht, "reise": reise}


def namen_ableiten(ereignisse: str, orte: str | None = None,
                   handordner: str | None = None, stand: str | None = None) -> tuple:
    """Vorschlaege fuer alle Anlaesse. Rueckgabe ``(zeilen, zahlen)``; schreibt nichts."""
    anlaesse, orte_je_bild, hand_je_bild, zahlen = eingaben_lesen(ereignisse, orte, handordner)
    heimat = heimat_ort(anlaesse, orte_je_bild)
    erzeugt = stand or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    zeilen = []
    for anlass in anlaesse:
        z = vorschlag_fuer(anlass, orte_je_bild, hand_je_bild, heimat)
        z["version"] = VERSION
        z["erzeugt"] = erzeugt
        zeilen.append(z)
    regeln = Counter(z["regel"] for z in zeilen)
    zahlen.update({
        "anlaesse": len(zeilen),
        "regeln": {r: regeln.get(r, 0) for r in REGELN},
        "reisen": sum(1 for z in zeilen if z["reise"]),
        "heimat": sum(1 for z in zeilen if z["heimat_verdacht"]),
        "ohne_ort": regeln.get("nur_zeit", 0),      # ohne Ort und ohne Handordner
    })
    return zeilen, zahlen


# ── Schreiben ────────────────────────────────────────────────────────────

def _pruefe_ziel(pfad: str, eingaben: list) -> str:
    """Ziel muss AUSSERHALB des Repos liegen und darf keine Eingabe sein (``ValueError``)."""
    if not isinstance(pfad, str) or not pfad.strip():
        raise ValueError("Kein Zielpfad fuer die Anlassnamen angegeben.")
    ziel = os.path.normcase(os.path.abspath(pfad))
    for eingabe in eingaben:
        if eingabe and os.path.normcase(os.path.abspath(eingabe)) == ziel:
            raise ValueError("Zieldatei ist eine Eingabedatei und wird nie ueberschrieben.")
    repo = os.path.normcase(os.path.abspath(REPO))
    try:
        gemeinsam = os.path.commonpath([ziel, repo])
    except ValueError:                        # anderes Laufwerk: nie im Repo
        return pfad
    if gemeinsam == repo:
        raise ValueError(
            f"Zieldatei liegt IM Repo und ist nicht erlaubt: {pfad}\n"
            f"Die Anlassnamen gehoeren ausserhalb des Repos (Standard: {STANDARD_AUSGABE}).")
    return pfad


def zeilen_schreiben(pfad: str, zeilen: list) -> None:
    """Datei komplett neu und atomar schreiben (temp + ``os.replace``)."""
    ordner = os.path.dirname(os.path.abspath(pfad))
    os.makedirs(ordner, exist_ok=True)
    temp = os.path.join(ordner, f".{os.path.basename(pfad)}.{os.getpid()}.tmp")
    try:
        with open(temp, "w", encoding="utf-8", newline="\n") as datei:
            for z in zeilen:
                datei.write(json.dumps(z, ensure_ascii=True, sort_keys=True) + "\n")
            datei.flush()
            os.fsync(datei.fileno())
        os.replace(temp, pfad)
    finally:
        if os.path.exists(temp):
            os.remove(temp)


# ── Kommandozeile ────────────────────────────────────────────────────────

def haupt(argv=None) -> int:
    zerleger = argparse.ArgumentParser(
        description="Anzeigenamen-Vorschlaege fuer Anlaesse, regelbasiert "
                    "(Trockenlauf ist Standard).")
    zerleger.add_argument("--ereignisse", default=STANDARD_EREIGNISSE,
                          help="ereignisse.jsonl (wird nur gelesen)")
    zerleger.add_argument("--orte", default=STANDARD_ORTE, help="orte.jsonl (optional)")
    zerleger.add_argument("--handordner", default=STANDARD_HANDORDNER,
                          help="Handordner-Zuordnung als JSONL (optional)")
    zerleger.add_argument("--ausgabe", default=STANDARD_AUSGABE,
                          help="anlass_namen.jsonl (ausserhalb des Repos)")
    zerleger.add_argument("--stand", default=None, help="Zeitstempel fuer 'erzeugt' (Tests)")
    gruppe = zerleger.add_mutually_exclusive_group()
    gruppe.add_argument("--trocken", action="store_true", help="nur zaehlen (Standard)")
    gruppe.add_argument("--schreiben", action="store_true", help="Ausgabe neu schreiben")
    args = zerleger.parse_args(argv)

    try:
        _pruefe_ziel(args.ausgabe, [args.ereignisse, args.orte, args.handordner])
    except ValueError as fehler:
        print(f"FEHLER: {fehler}", file=sys.stderr)
        raise SystemExit(2)
    if not os.path.isfile(args.ereignisse):
        print(f"FEHLER: Ereignisdatei nicht gefunden: {args.ereignisse}", file=sys.stderr)
        raise SystemExit(2)

    zeilen, z = namen_ableiten(args.ereignisse, args.orte, args.handordner, stand=args.stand)
    print(f"Modus:               {'SCHREIBEN' if args.schreiben else 'Trockenlauf'}")
    print(f"Anlaesse:            {z['anlaesse']}")
    print(f"orte.jsonl:          {'gelesen' if z['orte_vorhanden'] else 'fehlt (ohne Orte)'}")
    print(f"Handordner-Datei:    {'gelesen' if z['handordner_vorhanden'] else 'fehlt'}")
    print(f"kaputte Zeilen:      {z['kaputt_ereignisse'] + z['kaputt_orte'] + z['kaputt_handordner']}"
          f" (Ereignisse {z['kaputt_ereignisse']}, Orte {z['kaputt_orte']},"
          f" Handordner {z['kaputt_handordner']})")
    for regel in REGELN:
        print(f"  Regel {regel + ':':<11} {z['regeln'][regel]}")
    print(f"Reisen:              {z['reisen']}")
    print(f"ohne Ort:            {z['ohne_ort']}")
    if args.schreiben:
        zeilen_schreiben(args.ausgabe, zeilen)
        print(f"geschrieben:         {len(zeilen)} Zeilen")
    else:
        print("Trockenlauf: es wurde nichts geschrieben (--schreiben zum Schreiben).")
    return 0


if __name__ == "__main__":
    raise SystemExit(haupt())
