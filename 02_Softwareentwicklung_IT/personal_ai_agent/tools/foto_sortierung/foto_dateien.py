"""Fotos-Dateikennungen fuer das Handy (Nachtlauf-Schritt N13a, Teil A, 28.09.2026).

Warum dieses Werkzeug:
  Die Fotos-Uebersicht aus N11 (``fotos_uebersicht.json``) traegt **bewusst
  keine Datei-Kennungen** — fuer "wie viele Events gab es?" braucht sie
  niemand. Fuer ein Vorschaubild am Handy ist eine Kennung aber
  unverzichtbar: ohne sie kann kein Bild geladen werden. Dieses Werkzeug
  zieht deshalb aus dem lokalen ``sortierplan.json`` (nur lesend) **eine
  kleine Datei** mit den Kennungen: je Event eine Liste aus ``datei_id`` und
  Dateiname. Die N11-Uebersicht bleibt dabei unangetastet.

Was dieses Werkzeug bewusst NICHT tut:
  * **Kein Netz.** Kein pCloud-Aufruf, kein ``httpx``/``requests``, kein
    LLM-Aufruf. Gelesen wird ausschliesslich die lokale Datei
    ``~/foto_sortierung/sortierplan.json``.
  * **Keine Bilder.** Es wird keine Bilddatei geoeffnet, kopiert oder
    gespeichert; die Ausgabe traegt **nur Kennungen und Namen**.
  * **Keine Loeschung** ausser der eigenen temp-Datei beim atomaren Schreiben;
    es gibt keine Loeschfunktion, auch nicht "zur Sicherheit".
  * **Kein Schreiben ohne ``--schreiben``.** Der Standard ist ``--trocken``.

Eingefrorene Schnittstelle:
  Teil A erzeugt ``fotos_dateien.json``, Teil B liest sie. Das Schema
  (Schluesselnamen, Typen, Sortierungen) ist bindend und steht wortgleich im
  Feinauftrag; dieses Modul haelt sich exakt daran::

      {"art": "foto_dateien", "version": 1, "stand": "<ISO>",
       "plan_stand": "<ISO>|null",
       "zahlen": {"events", "dateien", "ohne_kennung", "kategorien", "jahre"},
       "events": [{"jahr", "kategorie", "event", "anzahl",
                   "dateien": [{"datei_id", "name"}]}]}

  Sortierung (fest, damit die Datei reproduzierbar ist):
  ``events`` nach ``jahr`` absteigend, dann ``event`` aufsteigend (die
  Kategorie als dritter Schluessel macht die Reihenfolge eindeutig);
  ``dateien`` nach ``name`` aufsteigend, bei Gleichstand nach ``datei_id``
  aufsteigend.

Zaehlregeln (so umgesetzt, nicht anders):
  1. Ein Event ist genau ein ``(jahr, kategorie, event)``-Tripel — dieselbe
     Definition wie ``events`` in der N11-Uebersicht.
  2. ``dateien`` enthaelt **nur** Zuege mit verwertbarer Kennung; jeder
     aufgenommene Zug zaehlt genau einmal.
  3. ``anzahl`` = Laenge von ``dateien``.
  4. ``ohne_kennung`` zaehlt die Zuege, die **nicht** aufgenommen wurden: die
     Datei-Kennung fehlt oder ist untauglich, oder das Jahr ist nicht als
     ganze Zahl lesbar (dann laesst sich kein Event bilden). Damit gilt
     ``zahlen.dateien + zahlen.ohne_kennung == Anzahl der Zuege`` — keine
     Zeile verschwindet unbemerkt.
  5. ``kategorien``/``jahre`` zaehlen die **verschiedenen** Werte der
     aufgenommenen Events.
  6. ``plan_stand`` ist ``stand`` aus dem Plan, sonst ``null``.

Ausgabe:
  * ``--ausgabe`` (Standard ``~/foto_sortierung/fotos_dateien.json``) wird
    atomar geschrieben (temp-Datei im Zielordner + ``os.replace``) und **nur**
    mit ``--schreiben``. Ein Ziel **im Repo** wird verweigert (deutsche
    Meldung auf ``stderr``, Exit 2) — dort haben private Kennungen nichts zu
    suchen, und der Auftrag erlaubt Ausgaben nur ausserhalb des Repos.
  * ``--trocken`` ist der **Standard**: dieselben Zahlen auf der Konsole,
    keine Datei.

Aufruf (Kommandozeile)::

    python tools/foto_sortierung/foto_dateien.py
    python tools/foto_sortierung/foto_dateien.py --plan C:/.../sortierplan.json
    python tools/foto_sortierung/foto_dateien.py --ausgabe C:/tmp/fotos_dateien.json --schreiben

Als Modul (Tests, Skripte): ``haupt(argv=[...])`` und die reinen Funktionen
``plan_laden``, ``dateien_bauen``, ``dateien_laden``, ``dateien_schreiben``,
``dateien_text``.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

# Vorgabepfade: ausserhalb des Repos — dort liegen private Kennungen und Namen.
STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_PLAN = os.path.join(STANDARD_BASIS, "sortierplan.json")
STANDARD_AUSGABE = os.path.join(STANDARD_BASIS, "fotos_dateien.json")

# Version des Schemas: erhoehen, sobald sich ein Schluessel aendert (Teil B
# liest diese Datei; ein stiller Schemawechsel waere ein Bruch).
DATEIEN_VERSION = 1
DATEIEN_ART = "foto_dateien"

# Die Schluessel des eingefrorenen Schemas — bindend fuer Teil B.
SCHLUESSEL_EVENT = ("jahr", "kategorie", "event", "anzahl", "dateien")
SCHLUESSEL_DATEI = ("datei_id", "name")
ZAHLEN_SCHLUESSEL = ("events", "dateien", "ohne_kennung", "kategorien", "jahre")


# ── Kleine Helfer (tolerant lesen, nie raten) ─────────────────────────────

def _text(wert) -> str:
    """Ein Feld als Text lesen — Nicht-Text und ``None`` werden zu ``""``."""
    return wert.strip() if isinstance(wert, str) else ""


def _als_int(wert):
    """Eine Zahl tolerant lesen — ``None`` statt Ausnahme, ``bool`` zaehlt nicht.

    ``bool`` gilt bewusst NICHT als Zahl: in JSON waere ``true`` sonst
    stillschweigend eine 1 und damit eine erfundene Kennung.
    """
    if isinstance(wert, bool):
        return None
    if isinstance(wert, int):
        return wert
    if isinstance(wert, str) and wert.strip():
        roh = wert.strip()
        try:
            return int(roh)
        except ValueError:
            return None
    return None


def _zahl(n) -> str:
    """Eine Zahl mit deutschen Tausenderpunkten (nur fuer die Ausgabe)."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


# ── 1. Lesen (lokal, nur lesend, kein Netz) ───────────────────────────────

def plan_laden(pfad: str) -> dict:
    """Den Sortierplan von der Platte lesen (nur lesend, kein Netz).

    Fehlender Pfad, fehlende Datei, unlesbares JSON und ein JSON-Kopf, der
    kein Woerterbuch ist, ergeben eine deutsche ``ValueError``-Meldung — es
    wird nichts geraten und nichts stillschweigend zu einem Leerplan gemacht.
    """
    if not isinstance(pfad, str) or not pfad.strip():
        raise ValueError("Kein Pfad fuer den Sortierplan angegeben.")
    if not os.path.isfile(pfad):
        raise ValueError(f"Sortierplan nicht gefunden: {pfad}")
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except json.JSONDecodeError as problem:
        raise ValueError(
            f"Sortierplan ist kein gueltiges JSON ({problem.__class__.__name__}): "
            f"{pfad}") from None
    except OSError as problem:
        raise ValueError(
            f"Sortierplan nicht lesbar ({problem.__class__.__name__}): "
            f"{pfad}") from None
    if not isinstance(daten, dict):
        raise ValueError(f"Sortierplan ist kein Woerterbuch: {pfad}")
    return daten


def dateien_laden(pfad: str) -> dict:
    """Die Datei-Kennungsdatei lesen (Gegenstueck zu ``dateien_schreiben``).

    Nur lesend. Fehlende oder kaputte Datei ergibt eine deutsche
    ``ValueError``-Meldung; ein stiller Leerwert waere hier gefaehrlich, weil
    der Leser (Teil B) sonst "keine Bilder" statt "Datei kaputt" meldet.
    """
    if not isinstance(pfad, str) or not pfad.strip():
        raise ValueError("Kein Pfad fuer die Dateikennungsdatei angegeben.")
    if not os.path.isfile(pfad):
        raise ValueError(f"Dateikennungsdatei nicht gefunden: {pfad}")
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except json.JSONDecodeError as problem:
        raise ValueError(
            "Dateikennungsdatei ist kein gueltiges JSON "
            f"({problem.__class__.__name__}): {pfad}") from None
    except OSError as problem:
        raise ValueError(
            f"Dateikennungsdatei nicht lesbar ({problem.__class__.__name__}): "
            f"{pfad}") from None
    if not isinstance(daten, dict):
        raise ValueError(f"Dateikennungsdatei ist kein Woerterbuch: {pfad}")
    return daten


# ── 2. Die Dateikennungen bauen (rein, ohne I/O) ──────────────────────────

def _plan_pruefen(plan) -> dict:
    """Den Plan auf Brauchbarkeit pruefen — deutsche ``ValueError`` statt Rueckfall.

    Ungueltig ist: kein Woerterbuch, oder ein Woerterbuch ohne den Schluessel
    ``zuege``. Ein solcher Plan ist kein Sortierplan; ihn stillschweigend als
    "null Dateien" auszugeben waere eine Falschaussage am Handy.
    """
    if not isinstance(plan, dict):
        raise ValueError(
            "Kein Sortierplan uebergeben: erwartet wird ein Woerterbuch mit "
            "dem Schluessel 'zuege'.")
    if "zuege" not in plan:
        raise ValueError(
            "Der Sortierplan ist leer: es fehlt der Schluessel 'zuege'.")
    if not isinstance(plan.get("zuege"), list):
        raise ValueError("Der Schluessel 'zuege' im Sortierplan ist keine Liste.")
    return plan


def dateien_bauen(plan: dict, *, stand: str | None = None) -> dict:
    """Aus dem Plan die Dateikennungen bauen — **reine** Funktion ohne Datei/Netz.

    Kein Dateizugriff, kein Netzzugriff, keine Seiteneffekte; der uebergebene
    Plan wird nicht veraendert. ``stand`` ist injizierbar (Tests bleiben
    reproduzierbar); ohne ``stand`` wird der aktuelle Zeitpunkt mit Zeitzone
    gesetzt.

    Rueckgabe: das eingefrorene Schema (siehe Modulkopf).
    """
    plan = _plan_pruefen(plan)
    if stand is not None and (not isinstance(stand, str) or not stand.strip()):
        raise ValueError("Der Stand muss ein nicht-leerer Text sein.")
    if stand is None:
        stand = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

    je_event: dict[tuple, list] = {}
    ohne_kennung = 0

    for zug in plan.get("zuege") or []:
        if not isinstance(zug, dict):
            ohne_kennung += 1
            continue
        jahr = _als_int(zug.get("jahr"))
        datei_id = _als_int(zug.get("fileid"))
        if datei_id is None or jahr is None:
            # Ohne Kennung laesst sich kein Bild laden, ohne Jahr kein Event
            # bilden: der Zug wird gezaehlt und nicht aufgenommen.
            ohne_kennung += 1
            continue
        schluessel = (jahr, _text(zug.get("kategorie")), _text(zug.get("event")))
        je_event.setdefault(schluessel, []).append(
            {"datei_id": datei_id, "name": _text(zug.get("von_name"))})

    events = []
    for schluessel in sorted(je_event, key=lambda s: (-s[0], s[2], s[1])):
        dateien = sorted(je_event[schluessel],
                         key=lambda eintrag: (eintrag["name"], eintrag["datei_id"]))
        events.append({
            "jahr": schluessel[0],
            "kategorie": schluessel[1],
            "event": schluessel[2],
            "anzahl": len(dateien),
            "dateien": dateien,
        })

    zahlen = {
        "events": len(events),
        "dateien": sum(eintrag["anzahl"] for eintrag in events),
        "ohne_kennung": ohne_kennung,
        "kategorien": len({eintrag["kategorie"] for eintrag in events}),
        "jahre": len({eintrag["jahr"] for eintrag in events}),
    }

    return {
        "art": DATEIEN_ART,
        "version": DATEIEN_VERSION,
        "stand": stand,
        "plan_stand": _text(plan.get("stand")) or None,
        "zahlen": {name: zahlen[name] for name in ZAHLEN_SCHLUESSEL},
        "events": events,
    }


# ── 3. Schreiben: atomar, nur ausserhalb des Repos ────────────────────────

def _pruefe_ziel_ausserhalb_repo(pfad: str) -> str:
    """Sicherstellen, dass die Zieldatei AUSSERHALB des Repos liegt.

    Der Auftrag erlaubt Ausgaben nur ausserhalb des Repos. Geprueft wird der
    absolut aufgeloeste Pfad; Gross-/Kleinschreibung und Schraeg-/
    Rueckwaertsstriche spielen keine Rolle (``abspath`` + ``normcase`` +
    ``commonpath``). Liegt das Ziel im Repo, gibt es eine deutsche
    ``ValueError``-Meldung — geschrieben wird dann nichts. Sonst kommt der
    Pfad zurueck.
    """
    if not isinstance(pfad, str) or not pfad.strip():
        raise ValueError("Kein Zielpfad fuer die Dateikennungen angegeben.")
    ziel = os.path.normcase(os.path.abspath(pfad))
    repo = os.path.normcase(os.path.abspath(REPO))
    try:
        gemeinsam = os.path.commonpath([ziel, repo])
    except ValueError:                        # anderes Laufwerk: nie im Repo
        return pfad
    if gemeinsam == repo:
        raise ValueError(
            f"Zieldatei liegt IM Repo und ist nicht erlaubt: {pfad}\n"
            f"Die Dateikennungen gehoeren ausserhalb des Repos (Standard: "
            f"{STANDARD_AUSGABE}); es wird NICHTS geschrieben.")
    return pfad


def dateien_schreiben(pfad: str, daten: dict) -> str:
    """Die Dateikennungen schreiben — atomar und nur ausserhalb des Repos.

    Erst vollstaendig in ``<ziel>.tmp`` im **Zielordner** schreiben, dann per
    ``os.replace`` ersetzen: es entsteht nie eine halbe Datei. Scheitert das
    Schreiben, wird ausschliesslich die eigene temp-Datei wieder entfernt (die
    einzige Loeschung in diesem Modul) — eine vorhandene alte Zieldatei bleibt
    unangetastet. Ein Ziel im Repo ergibt eine deutsche ``ValueError``-Meldung.

    Rueckgabe: der geschriebene Pfad.
    """
    ziel = _pruefe_ziel_ausserhalb_repo(pfad)
    if not isinstance(daten, dict):
        raise ValueError("Keine Dateikennungen zum Schreiben uebergeben "
                         "(erwartet wird ein Woerterbuch).")
    ordner = os.path.dirname(os.path.abspath(ziel))
    os.makedirs(ordner, exist_ok=True)
    temp_pfad = ziel + ".tmp"
    try:
        with open(temp_pfad, "w", encoding="utf-8") as datei:
            json.dump(daten, datei, ensure_ascii=False, indent=2)
            datei.write("\n")
        os.replace(temp_pfad, ziel)
    except Exception:
        if os.path.exists(temp_pfad):
            os.remove(temp_pfad)              # nur die eigene temp-Datei
        raise
    return ziel


# ── 4. Die Zusammenfassung als Klartext (deutsch) ─────────────────────────

def dateien_text(daten: dict) -> str:
    """Die Dateikennungen als mehrzeiliger deutscher Klartext.

    Enthaelt Stand, Plan-Stand, Events, Dateien, Zuege ohne Kennung,
    Kategorien, Jahre und die ersten Events mit ihrer Dateizahl. Fehlende
    Felder ergeben ``0`` statt eines Absturzes — die Funktion ist fuer die
    Konsole gebaut, nicht als Datenquelle (das ist die JSON-Datei). Kennungen
    selbst stehen hier nur als Anzahl, nicht als Wert.
    """
    d: dict = daten if isinstance(daten, dict) else {}
    roh_zahlen = d.get("zahlen")
    zahlen: dict = roh_zahlen if isinstance(roh_zahlen, dict) else {}
    roh_events = d.get("events")
    events: list = roh_events if isinstance(roh_events, list) else []

    def wert(name: str) -> int:
        zahl = _als_int(zahlen.get(name))
        return zahl if zahl is not None else 0

    zeilen = [
        f"Fotos-Dateikennungen N13a — Stand {_text(d.get('stand')) or 'unbekannt'} "
        f"(Plan-Stand {_text(d.get('plan_stand')) or 'unbekannt'})",
        f"Events: {_zahl(wert('events'))}   "
        f"Dateien: {_zahl(wert('dateien'))}   "
        f"ohne Kennung: {_zahl(wert('ohne_kennung'))}",
        f"Kategorien: {_zahl(wert('kategorien'))}   "
        f"Jahre: {_zahl(wert('jahre'))}",
    ]
    for eintrag in events[:5]:
        if not isinstance(eintrag, dict):
            continue
        zeilen.append(
            f"  {_zahl(_als_int(eintrag.get('jahr')) or 0)} · "
            f"{_text(eintrag.get('kategorie')) or 'ohne Kategorie'} · "
            f"{_text(eintrag.get('event')) or 'ohne Event'}: "
            f"{_zahl(_als_int(eintrag.get('anzahl')) or 0)} Dateien")
    if len(events) > 5:
        zeilen.append(f"  ... und {_zahl(len(events) - 5)} weitere Events")
    zeilen.append("ohne Bilddaten, nur Kennungen und Namen")
    return "\n".join(zeilen)


# ── 5. Kommandozeile ─────────────────────────────────────────────────────

def haupt(argv=None) -> int:
    """Kommandozeile: Plan lesen, Zahlen zeigen, nur mit ``--schreiben`` ablegen.

    ``--plan`` (Standard: der echte Sortierplan), ``--ausgabe`` (Standard:
    ``~/foto_sortierung/fotos_dateien.json``), ``--trocken`` (Standard) und
    ``--schreiben``. Ohne ``--schreiben`` ist es ein reiner Trockenlauf:
    dieselben Zahlen auf der Konsole, keine Datei. Ein Ziel im Repo ergibt
    eine deutsche Meldung auf ``stderr`` und Exit 2 — auch im Trockenlauf,
    damit der Fehler frueh auffaellt und nicht erst beim ersten Schreiben.
    """
    zerleger = argparse.ArgumentParser(
        description="Fotos-Dateikennungen N13a: liest NUR den lokalen "
                    "Sortierplan und baut je Event eine Liste aus Kennung und "
                    "Dateiname — ohne Bilder, ohne Netz.")
    zerleger.add_argument("--plan", dest="plan", default=STANDARD_PLAN,
                          help="Sortierplan (JSON, ausserhalb des Repos)")
    zerleger.add_argument("--ausgabe", dest="ausgabe", default=STANDARD_AUSGABE,
                          help="Zieldatei der Kennungen (ausserhalb des Repos)")
    zerleger.add_argument("--trocken", action="store_true",
                          help="nur Zahlen zeigen, nichts schreiben (Standard)")
    zerleger.add_argument("--schreiben", action="store_true",
                          help="die Datei wirklich schreiben (atomar, nur "
                               "ausserhalb des Repos); --trocken hat Vorrang")
    args = zerleger.parse_args(argv)

    schreiben = bool(args.schreiben) and not bool(args.trocken)

    try:
        plan = plan_laden(args.plan)
        daten = dateien_bauen(plan)
        _pruefe_ziel_ausserhalb_repo(args.ausgabe)
    except ValueError as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2

    print("Fotos-Dateikennungen N13a — "
          + ("SCHREIBEN" if schreiben else "TROCKENLAUF (es wird nichts geschrieben)"))
    print(f"Sortierplan: {args.plan}")
    print(dateien_text(daten))

    if not schreiben:
        print(f"Trockenlauf: {args.ausgabe} wurde NICHT geschrieben.")
        return 0

    try:
        ziel = dateien_schreiben(args.ausgabe, daten)
    except ValueError as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2
    print(f"Dateikennungen geschrieben: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(haupt())
