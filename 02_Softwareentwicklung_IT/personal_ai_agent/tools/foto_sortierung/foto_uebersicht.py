"""Fotos-Uebersicht fuer das Handy (Nachtlauf-Schritt N11, Teil A, 27.09.2026).

Warum dieses Werkzeug:
  Am Handy laesst sich heute nicht fragen "wie viele Events gab es?" oder
  "zeig mir die Urlaube 2021": Der Sortierschluessel, ``themen.jsonl`` und
  ``kategorien.json`` liegen **nur auf dem PC**. ``sortierplan.json`` (N7,
  Trockenlauf) enthaelt aber schon alle Zahlen und Event-Namen. Dieses Werkzeug
  zieht daraus **eine kleine Datei**: Zahlen und Namen — sonst nichts.

Was dieses Werkzeug bewusst NICHT tut:
  * **Kein Netz.** Kein pCloud-Aufruf, kein ``httpx``/``requests``, kein
    LLM-Aufruf. Gelesen wird ausschliesslich die lokale Datei
    ``~/foto_sortierung/sortierplan.json``.
  * **Keine Bilder.** Es wird keine Bilddatei geoeffnet, kopiert oder
    gespeichert; die Uebersicht traegt **nur Zahlen und Namen**.
  * **Keine Datei-Kennungen.** Weder ``fileid`` noch ``folderid`` wandern in die
    Uebersicht — sie braucht niemand, um "wie viele Events gab es?" zu
    beantworten, und Kennungen gehoeren nicht in eine Handy-Antwort.
  * **Keine Loeschung** ausser der eigenen temp-Datei beim atomaren Schreiben.
  * **Kein Schreiben ohne ``--schreiben``.** Der Standard ist der Trockenlauf.

Eingefrorene Schnittstelle:
  Teil A erzeugt ``fotos_uebersicht.json``, Teil B liest sie. Das Schema
  (Schluesselnamen, Typen, Sortierungen) ist bindend und steht wortgleich im
  Feinauftrag; dieses Modul haelt sich exakt daran::

      {"version": 1, "art": "foto_uebersicht", "stand": "<ISO>",
       "quelle": {"plan_stand": "<ISO>", "trocken": true},
       "zahlen": {"zeilen", "anlaesse", "zuege", "events", "events_neu",
                  "events_wiederverwendet", "ordner_neu", "ordner_vorhanden",
                  "themen", "kategorien", "doppelung_gesamt",
                  "doppelung_ohne_anlass", "doppelung_uebersprungen",
                  "ohne_thema", "ohne_jahr", "ohne_datum", "jahre"},
       "jahre": [{"jahr", "anlaesse", "dateien", "events"}],
       "themen": [{"thema", "anlaesse", "dateien"}],
       "kategorien": [{"kategorie", "anlaesse", "dateien", "events"}],
       "events": [{"jahr", "kategorie", "name", "dateien", "quelle"}]}

  Sortierung: ``jahre`` aufsteigend nach ``jahr``; ``themen``/``kategorien``
  absteigend nach ``anlaesse``, bei Gleichstand alphabetisch; ``events``
  aufsteigend nach ``jahr``, dann alphabetisch nach ``name``;
  ``zahlen.jahre`` ist ``len(jahre)``.

Zaehlregeln (so umgesetzt, nicht anders):
  1. ``zeilen``, ``anlaesse``, ``zuege``, ``doppelung_*``, ``ohne_thema``,
     ``ohne_jahr``, ``events_neu``, ``events_wiederverwendet``, ``ordner_neu``
     und ``ordner_vorhanden`` kommen aus ``plan["zusammenfassung"]``; ein
     fehlender oder unbrauchbarer Wert zaehlt als ``0`` (nie ein Absturz).
     ``anlaesse`` wird zusaetzlich gegen ``len(plan["anlaesse"])`` geprueft:
     weicht die Zusammenfassung ab, gewinnt der **echte Listenwert** — ein
     stiller Widerspruch zwischen Kopfzahl und Liste waere schlimmer als eine
     korrigierte Zahl.
  2. ``events`` = Anzahl **verschiedener** ``(jahr, kategorie, event)``-Kombinationen
     — also die Zahl der Ziel-Ordner, nicht die Zahl der Anlaesse. Beides ist
     im echten Plan **nicht** gleich: 2.127 Anlaesse stehen 2.098
     Kombinationen gegenueber, weil **10** wiederverwendete Event-Ordner
     (``event_quelle: "vorschlag"``, **39** Anlaesse darin) je mehrere Anlaesse
     aufnehmen. Bindend ist die Zaehlregel an dieser Stelle.
  3. ``dateien`` je Jahr/Thema/Kategorie/Event = Summe der ``dateien``-Felder
     der Anlaesse dieser Gruppe (das Feld ist im Plan eine Zahl; eine Liste
     wird als ihre Laenge gelesen).
  4. ``jahre`` = Anzahl verschiedener Jahre, ``themen`` = Anzahl verschiedener
     ``thema``-Werte, ``kategorien`` = Anzahl verschiedener ``kategorie``-Werte.
  5. ``ohne_datum = max(0, zeilen - zuege - doppelung_uebersprungen)`` — das
     sind die Zeilen **ohne Datum im Namen**: die Gesamtzahl minus der
     eingeplanten Zuege minus der Doppelungen, die uebersprungen wurden.
     Gegenprobe N7: 9.430 - 7.616 - 668 = **1.146**.

Ausgabe:
  * ``--ausgabe`` (Standard ``~/foto_sortierung/fotos_uebersicht.json``) wird
    atomar geschrieben (temp-Datei im Zielordner + ``os.replace``) und **nur**
    mit ``--schreiben``. Ein Ziel **im Repo** wird verweigert (deutsche
    Meldung auf ``stderr``, Exit 2) — dort haben private Zahlen nichts zu
    suchen, und der Auftrag erlaubt Ausgaben nur ausserhalb des Repos.
  * Ohne ``--schreiben`` laeuft alles als Trockenlauf: dieselben Zahlen auf der
    Konsole, keine Datei.

Aufruf (Kommandozeile)::

    python tools/foto_sortierung/foto_uebersicht.py
    python tools/foto_sortierung/foto_uebersicht.py --plan C:/.../sortierplan.json
    python tools/foto_sortierung/foto_uebersicht.py --schreiben

Als Modul (Tests, Skripte): ``haupt(argv=[...])`` und die reinen Funktionen
``plan_laden``, ``uebersicht_bauen``, ``uebersicht_laden``,
``uebersicht_schreiben``, ``uebersicht_text``.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

# Vorgabepfade: ausserhalb des Repos — dort liegen private Zahlen und Namen.
STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_PLAN = os.path.join(STANDARD_BASIS, "sortierplan.json")
STANDARD_AUSGABE = os.path.join(STANDARD_BASIS, "fotos_uebersicht.json")

# Version des Uebersichts-Schemas: erhoehen, sobald sich ein Schluessel aendert
# (Teil B liest diese Datei; ein stiller Schemawechsel waere ein Bruch).
UEBERSICHT_VERSION = 1
UEBERSICHT_ART = "foto_uebersicht"

# Die Zaehler, die aus ``plan["zusammenfassung"]`` uebernommen werden.
ZAHLSCHLUESSEL = ("zeilen", "anlaesse", "zuege", "doppelung_gesamt",
                  "doppelung_ohne_anlass", "doppelung_uebersprungen",
                  "ohne_thema", "ohne_jahr", "ordner_neu", "ordner_vorhanden",
                  "events_neu", "events_wiederverwendet")

# Die Schluessel der vier Listen — bindend fuer Teil B.
SCHLUESSEL_JAHRE = ("jahr", "anlaesse", "dateien", "events")
SCHLUESSEL_THEMEN = ("thema", "anlaesse", "dateien")
SCHLUESSEL_KATEGORIEN = ("kategorie", "anlaesse", "dateien", "events")
SCHLUESSEL_EVENTS = ("jahr", "kategorie", "name", "dateien", "quelle")


# ── Kleine Helfer (tolerant lesen, nie raten) ─────────────────────────────

def _text(wert) -> str:
    """Ein Feld als Text lesen — Nicht-Text und ``None`` werden zu ``\"\"``."""
    return wert.strip() if isinstance(wert, str) else ""


def _als_int(wert):
    """Eine Zahl tolerant lesen — ``None`` statt Ausnahme, ``bool`` zaehlt nicht."""
    if isinstance(wert, bool):
        return None
    if isinstance(wert, int):
        return wert
    if isinstance(wert, str) and wert.strip():
        try:
            return int(wert.strip())
        except ValueError:
            return None
    return None


def _zaehler(quelle, name) -> int:
    """Einen Zaehler aus einem Woerterbuch lesen — fehlend/unbrauchbar -> ``0``."""
    if not isinstance(quelle, dict):
        return 0
    wert = _als_int(quelle.get(name))
    return wert if wert is not None else 0


def _dateien_zahl(anlass) -> int:
    """Das ``dateien``-Feld eines Anlasses als Zahl (Liste -> ihre Laenge)."""
    if not isinstance(anlass, dict):
        return 0
    wert = anlass.get("dateien")
    if isinstance(wert, bool):
        return 0
    if isinstance(wert, int):
        return wert if wert > 0 else 0
    if isinstance(wert, list):
        return len(wert)
    return 0


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


def uebersicht_laden(pfad: str) -> dict:
    """Die Uebersichtsdatei lesen (Gegenstueck zu ``uebersicht_schreiben``).

    Nur lesend. Fehlende oder kaputte Datei ergibt eine deutsche
    ``ValueError``-Meldung; ein stiller Leerwert waere hier gefaehrlich, weil
    der Leser (Teil B) sonst "keine Events" statt "Datei kaputt" meldet.
    """
    if not isinstance(pfad, str) or not pfad.strip():
        raise ValueError("Kein Pfad fuer die Uebersichtsdatei angegeben.")
    if not os.path.isfile(pfad):
        raise ValueError(f"Uebersichtsdatei nicht gefunden: {pfad}")
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except json.JSONDecodeError as problem:
        raise ValueError(
            "Uebersichtsdatei ist kein gueltiges JSON "
            f"({problem.__class__.__name__}): {pfad}") from None
    except OSError as problem:
        raise ValueError(
            f"Uebersichtsdatei nicht lesbar ({problem.__class__.__name__}): "
            f"{pfad}") from None
    if not isinstance(daten, dict):
        raise ValueError(f"Uebersichtsdatei ist kein Woerterbuch: {pfad}")
    return daten


# ── 2. Die Uebersicht bauen (rein, ohne I/O) ──────────────────────────────

def _plan_pruefen(plan) -> dict:
    """Den Plan auf Brauchbarkeit pruefen — deutsche ``ValueError`` statt Rueckfall.

    Ungueltig ist: kein Woerterbuch, oder ein Woerterbuch ohne **beide**
    Schluessel ``anlaesse`` und ``zusammenfassung``. Ein solcher Plan ist kein
    Sortierplan; ihn stillschweigend als "null Events" auszugeben waere eine
    Falschaussage am Handy.
    """
    if not isinstance(plan, dict):
        raise ValueError(
            "Kein Sortierplan uebergeben: erwartet wird ein Woerterbuch mit "
            "den Schluesseln 'anlaesse' und 'zusammenfassung'.")
    if "anlaesse" not in plan and "zusammenfassung" not in plan:
        raise ValueError(
            "Der Sortierplan ist leer: es fehlen die Schluessel 'anlaesse' "
            "und 'zusammenfassung'.")
    return plan


def uebersicht_bauen(plan: dict, *, stand: str | None = None) -> dict:
    """Aus dem Plan die Uebersicht bauen — **reine** Funktion, ohne Datei/Netz.

    Kein Dateizugriff, kein Netzzugriff, keine Seiteneffekte; der uebergebene
    Plan wird nicht veraendert. ``stand`` ist injizierbar (Tests bleiben
    reproduzierbar); ohne ``stand`` wird der aktuelle Zeitpunkt mit
    Zeitzone gesetzt.

    Rueckgabe: das eingefrorene Schema (siehe Modulkopf). ``quelle.trocken``
    ist nur dann ``True``, wenn der Plan das Feld ``trocken`` wirklich als
    ``True`` traegt — ein Plan ohne dieses Feld ist kein belegter Trockenlauf.
    """
    plan = _plan_pruefen(plan)
    if stand is not None and (not isinstance(stand, str) or not stand.strip()):
        raise ValueError("Der Stand muss ein nicht-leerer Text sein.")
    if stand is None:
        stand = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

    zusammenfassung = plan.get("zusammenfassung")
    zusammenfassung = zusammenfassung if isinstance(zusammenfassung, dict) else {}

    # Zaehler 1: aus der Zusammenfassung — fehlend/unbrauchbar -> 0.
    zahlen = {name: _zaehler(zusammenfassung, name) for name in ZAHLSCHLUESSEL}
    # Zaehler 2: ``anlaesse`` gegen die echte Liste pruefen — die Liste gewinnt.
    liste = plan.get("anlaesse")
    liste = liste if isinstance(liste, list) else None
    if liste is not None:
        zahlen["anlaesse"] = len(liste)
    anlaesse_liste = liste if liste is not None else []

    # Gruppensammlungen (Sets nur fuer die Unterscheidungen, Ausgabe ist Liste).
    je_jahr: dict[int, dict] = {}
    je_thema: dict[str, dict] = {}
    je_kategorie: dict[str, dict] = {}
    je_event: dict[tuple, dict] = {}

    for anlass in anlaesse_liste:
        if not isinstance(anlass, dict):
            continue
        jahr = _als_int(anlass.get("jahr"))
        thema = _text(anlass.get("thema"))
        kategorie = _text(anlass.get("kategorie"))
        event = _text(anlass.get("event"))
        dateien = _dateien_zahl(anlass)

        # Ein Anlass ohne ganzzahliges Jahr kann in keiner Jahresgruppe und in
        # keinem Event stehen (das Schema verlangt ``jahr`` als Zahl) — er
        # zaehlt trotzdem in ``zahlen.anlaesse``, weil er ein Anlass ist.
        if jahr is not None:
            jahresgruppe = je_jahr.setdefault(
                jahr, {"anlaesse": 0, "dateien": 0, "events": set()})
            jahresgruppe["anlaesse"] += 1
            jahresgruppe["dateien"] += dateien
            jahresgruppe["events"].add((kategorie, event))
        # Ein leerer Themennname bzw. Kategoriename ist kein Name: solche
        # Anlaesse bekommen keine Gruppenzeile (der Plan kennt sie nicht als
        # Wert), sie bleiben in ``zahlen.anlaesse`` gezaehlt.
        if thema:
            themengruppe = je_thema.setdefault(
                thema, {"anlaesse": 0, "dateien": 0})
            themengruppe["anlaesse"] += 1
            themengruppe["dateien"] += dateien
        if kategorie:
            kategoriegruppe = je_kategorie.setdefault(
                kategorie, {"anlaesse": 0, "dateien": 0, "events": set()})
            kategoriegruppe["anlaesse"] += 1
            kategoriegruppe["dateien"] += dateien
            kategoriegruppe["events"].add((jahr, event))
        if jahr is not None:
            eventgruppe = je_event.setdefault(
                (jahr, kategorie, event), {"dateien": 0, "quelle": ""})
            eventgruppe["dateien"] += dateien
            if not eventgruppe["quelle"]:
                eventgruppe["quelle"] = _text(anlass.get("event_quelle"))

    # ``jahre``: aufsteigend nach Jahr.
    jahre = [{"jahr": jahr,
              "anlaesse": je_jahr[jahr]["anlaesse"],
              "dateien": je_jahr[jahr]["dateien"],
              "events": len(je_jahr[jahr]["events"])}
             for jahr in sorted(je_jahr)]

    # ``themen``/``kategorien``: absteigend nach Anlaessen, Gleichstand alphabetisch.
    themen = [{"thema": thema,
               "anlaesse": je_thema[thema]["anlaesse"],
               "dateien": je_thema[thema]["dateien"]}
              for thema in sorted(je_thema, key=lambda name: (-je_thema[name]["anlaesse"],
                                                              name))]

    kategorien = [{"kategorie": kategorie,
                   "anlaesse": je_kategorie[kategorie]["anlaesse"],
                   "dateien": je_kategorie[kategorie]["dateien"],
                   "events": len(je_kategorie[kategorie]["events"])}
                  for kategorie in sorted(je_kategorie,
                                          key=lambda name: (-je_kategorie[name]["anlaesse"],
                                                            name))]

    # ``events``: aufsteigend nach Jahr, dann alphabetisch nach Name (die
    # Kategorie als dritter Schluessel macht die Reihenfolge eindeutig).
    events = [{"jahr": schluessel[0],
               "kategorie": schluessel[1],
               "name": schluessel[2],
               "dateien": je_event[schluessel]["dateien"],
               "quelle": je_event[schluessel]["quelle"]}
              for schluessel in sorted(je_event,
                                       key=lambda s: (s[0], s[2], s[1]))]

    # Zaehler 3: die Laengen der Listen — Kopfzahl und Liste bleiben gleich.
    # ``events`` zaehlt die Ziel-Ordner (verschiedene Kombinationen), nicht die
    # Anlaesse: im echten Plan 2.098 gegen 2.127 Anlaesse, weil 10
    # wiederverwendete Event-Ordner (39 Anlaesse) mehrere Anlaesse aufnehmen.
    zahlen["events"] = len(events)
    zahlen["themen"] = len(themen)
    zahlen["kategorien"] = len(kategorien)
    zahlen["jahre"] = len(jahre)
    # Zeilen OHNE Datum im Namen = Gesamtzeilen - eingeplante Zuege - die
    # uebersprungenen Doppelungen. Nie negativ (die drei Zahlen koennen aus
    # einem aelteren Plan inkonsistent sein).
    zahlen["ohne_datum"] = max(
        0, zahlen["zeilen"] - zahlen["zuege"] - zahlen["doppelung_uebersprungen"])

    # Schluesselreihenfolge = Schema-Reihenfolge (Teil B liest die Datei, ein
    # Mensch liest den Text daneben).
    zahlen_geordnet = {
        "zeilen": zahlen["zeilen"],
        "anlaesse": zahlen["anlaesse"],
        "zuege": zahlen["zuege"],
        "events": zahlen["events"],
        "events_neu": zahlen["events_neu"],
        "events_wiederverwendet": zahlen["events_wiederverwendet"],
        "ordner_neu": zahlen["ordner_neu"],
        "ordner_vorhanden": zahlen["ordner_vorhanden"],
        "themen": zahlen["themen"],
        "kategorien": zahlen["kategorien"],
        "doppelung_gesamt": zahlen["doppelung_gesamt"],
        "doppelung_ohne_anlass": zahlen["doppelung_ohne_anlass"],
        "doppelung_uebersprungen": zahlen["doppelung_uebersprungen"],
        "ohne_thema": zahlen["ohne_thema"],
        "ohne_jahr": zahlen["ohne_jahr"],
        "ohne_datum": zahlen["ohne_datum"],
        "jahre": zahlen["jahre"],
    }

    return {
        "version": UEBERSICHT_VERSION,
        "art": UEBERSICHT_ART,
        "stand": stand,
        "quelle": {"plan_stand": _text(plan.get("stand")),
                   "trocken": plan.get("trocken") is True},
        "zahlen": zahlen_geordnet,
        "jahre": jahre,
        "themen": themen,
        "kategorien": kategorien,
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
        raise ValueError("Kein Zielpfad fuer die Uebersicht angegeben.")
    ziel = os.path.normcase(os.path.abspath(pfad))
    repo = os.path.normcase(os.path.abspath(REPO))
    try:
        gemeinsam = os.path.commonpath([ziel, repo])
    except ValueError:                        # anderes Laufwerk: nie im Repo
        return pfad
    if gemeinsam == repo:
        raise ValueError(
            f"Zieldatei liegt IM Repo und ist nicht erlaubt: {pfad}\n"
            f"Die Fotos-Uebersicht gehoert ausserhalb des Repos (Standard: "
            f"{STANDARD_AUSGABE}); es wird NICHTS geschrieben.")
    return pfad


def uebersicht_schreiben(pfad: str, daten: dict) -> str:
    """Die Uebersicht schreiben — atomar und nur ausserhalb des Repos.

    Erst vollstaendig in ``<ziel>.tmp`` im **Zielordner** schreiben, dann per
    ``os.replace`` ersetzen: es entsteht nie eine halbe Datei. Scheitert das
    Schreiben, wird ausschliesslich die eigene temp-Datei wieder entfernt (die
    einzige Loeschung in diesem Modul) — eine vorhandene alte Zieldatei bleibt
    unangetastet. Ein Ziel im Repo ergibt eine deutsche ``ValueError``-Meldung.

    Rueckgabe: der geschriebene Pfad.
    """
    ziel = _pruefe_ziel_ausserhalb_repo(pfad)
    if not isinstance(daten, dict):
        raise ValueError("Keine Uebersichtsdaten zum Schreiben uebergeben "
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

def uebersicht_text(daten: dict) -> str:
    """Die Uebersicht als mehrzeiliger deutscher Klartext.

    Enthaelt Stand, Anlaesse, Events, Dateien, Jahre, Themen, Kategorien,
    Doppelungen (aufgeschluesselt) und die Zeilen ohne Datum. Fehlende Felder
    ergeben ``0`` statt eines Absturzes — die Funktion ist fuer die Konsole
    gebaut, nicht als Datenquelle (das ist die JSON-Datei).
    """
    d = daten if isinstance(daten, dict) else {}
    zahlen = d.get("zahlen") if isinstance(d.get("zahlen"), dict) else {}
    quelle = d.get("quelle") if isinstance(d.get("quelle"), dict) else {}
    jahre = d.get("jahre") if isinstance(d.get("jahre"), list) else []
    # Fehlende oder unbrauchbare Felder zaehlen als 0 (nicht als "None").
    def wert(name: str) -> int:
        return _zaehler(zahlen, name)
    # Dateien gibt es im Schema nur je Gruppe — die Gesamtzahl ist ihre Summe.
    dateien_gesamt = sum(_zaehler(eintrag, "dateien")
                         for eintrag in jahre if isinstance(eintrag, dict))
    trocken = "ja" if quelle.get("trocken") is True else "nein"
    return "\n".join([
        f"Fotos-Uebersicht — Stand {_text(d.get('stand')) or 'unbekannt'} "
        f"(Plan-Stand {_text(quelle.get('plan_stand')) or 'unbekannt'}, "
        f"trocken: {trocken})",
        f"Anlaesse: {_zahl(wert('anlaesse'))}   "
        f"Events: {_zahl(wert('events'))}   "
        f"Dateien: {_zahl(dateien_gesamt)}",
        f"Jahre: {_zahl(wert('jahre'))}   "
        f"Themen: {_zahl(wert('themen'))}   "
        f"Kategorien: {_zahl(wert('kategorien'))}",
        f"Zeilen: {_zahl(wert('zeilen'))}   "
        f"Zuege: {_zahl(wert('zuege'))}",
        f"Events neu: {_zahl(wert('events_neu'))}   "
        f"Events wiederverwendet: {_zahl(wert('events_wiederverwendet'))}",
        f"Ordner neu: {_zahl(wert('ordner_neu'))}   "
        f"Ordner vorhanden: {_zahl(wert('ordner_vorhanden'))}",
        f"Doppelungen: {_zahl(wert('doppelung_gesamt'))} gesamt · "
        f"{_zahl(wert('doppelung_ohne_anlass'))} ohne Anlass-ID · "
        f"{_zahl(wert('doppelung_uebersprungen'))} uebersprungen",
        f"Zeilen ohne Datum: {_zahl(wert('ohne_datum'))}   "
        f"Anlaesse ohne Thema: {_zahl(wert('ohne_thema'))}   "
        f"Anlaesse ohne Jahr: {_zahl(wert('ohne_jahr'))}",
        "ohne Bilddaten, ohne Datei-Kennungen",
    ])


# ── 5. Kommandozeile ─────────────────────────────────────────────────────

def haupt(argv=None) -> int:
    """Kommandozeile: Plan lesen, Uebersicht zeigen, nur mit ``--schreiben`` ablegen.

    ``--plan`` (Standard: der echte Sortierplan), ``--ausgabe`` (Standard:
    ``~/foto_sortierung/fotos_uebersicht.json``) und ``--schreiben``. Ohne
    ``--schreiben`` ist es ein reiner Trockenlauf: dieselben Zahlen auf der
    Konsole, keine Datei. Ein Ziel im Repo ergibt eine deutsche Meldung auf
    ``stderr`` und Exit 2 — auch im Trockenlauf, damit der Fehler frueh
    auffaellt und nicht erst beim ersten Schreiben.
    """
    zerleger = argparse.ArgumentParser(
        description="Fotos-Uebersicht N11: liest NUR den lokalen Sortierplan "
                    "und baut eine kleine Uebersicht (Zahlen und Event-Namen) "
                    "— ohne Bilder, ohne Netz, ohne Datei-Kennungen.")
    zerleger.add_argument("--plan", dest="plan", default=STANDARD_PLAN,
                          help="Sortierplan (JSON, ausserhalb des Repos)")
    zerleger.add_argument("--ausgabe", dest="ausgabe", default=STANDARD_AUSGABE,
                          help="Zieldatei der Uebersicht (ausserhalb des Repos)")
    zerleger.add_argument("--schreiben", action="store_true",
                          help="die Uebersicht wirklich schreiben (atomar, nur "
                               "ausserhalb des Repos)")
    args = zerleger.parse_args(argv)

    try:
        plan = plan_laden(args.plan)
        daten = uebersicht_bauen(plan)
        _pruefe_ziel_ausserhalb_repo(args.ausgabe)
    except ValueError as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2

    print("Fotos-Uebersicht N11 — "
          + ("SCHREIBEN" if args.schreiben else "TROCKENLAUF (es wird nichts geschrieben)"))
    print(f"Sortierplan: {args.plan}")
    print(uebersicht_text(daten))

    if not args.schreiben:
        print(f"Trockenlauf: {args.ausgabe} wurde NICHT geschrieben.")
        return 0

    try:
        ziel = uebersicht_schreiben(args.ausgabe, daten)
    except ValueError as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2
    print(f"Uebersicht geschrieben: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(haupt())
