"""Ereignis-Knoten je Anlass aus dem Sortierplan (N27 Schritt 1, 28.09.2026).

Warum dieses Werkzeug:
  Der Nutzer hat die **Verknuepfungsschicht** beauftragt: Chats, Bilder und
  Menschen thematisch verbinden. Schritt 1 ist das **Datenfundament** — je
  Anlass ein Knoten mit Datum, Thema, Kategorie, Anzahl Dateien und den
  Datei-Kennungen. Damit hat die spaetere Andockung (Chats, Kalender,
  Personen) einen stabilen Anker: die ``anlass_id`` (``thema_quelle`` aus
  N7). Personen spielen hier bewusst **keine** Rolle.

Was dieses Werkzeug bewusst NICHT tut:
  * **Kein Netz.** Kein pCloud-Aufruf, kein ``httpx``/``requests``, kein
    LLM-Aufruf. Gelesen wird ausschliesslich die lokale Datei
    ``~/foto_sortierung/sortierplan.json``.
  * **Keine Bilder.** Es wird keine Bilddatei geoeffnet, kopiert oder
    gespeichert; die Ausgabe traegt **nur Kennungen und Namen**.
  * **Keine Loeschung** ausser der eigenen temp-Datei beim atomaren Schreiben;
    es gibt keine Loeschfunktion, auch nicht "zur Sicherheit".
  * **Kein Schreiben ohne ``--schreiben``.** Der Standard ist ``--trocken``.

Eingabe (nur lesend):
  Genutzt werden genau die Schluessel ``anlaesse`` (Liste), ``zuege``
  (Liste) und ``stand``. Unbekannte Schluessel werden ignoriert; der Plan
  wird **nicht** veraendert.

Ausgabe (eingefrorenes Schema, JSONL):
  ``--ausgabe`` (Standard ``~/foto_sortierung/ereignisse.jsonl``) ist reine
  JSONL: **je Zeile genau ein Knoten**, kodiert mit ``ensure_ascii=True``
  (ASCII, keine Umlaute) und ``sort_keys=True``. Eine Kopfzeile gibt es
  nicht, und ein ``zahlen``-Block steht **nicht** in der Datei — er wird nur
  auf der Konsole berichtet und im Rueckgabewert von ``ereignisse_bauen``
  gefuehrt::

      {"anlass_id", "anzahl_dateien", "art": "ereignis", "datei_kennungen",
       "datum", "event", "event_quelle", "event_stufe", "jahr", "kategorie",
       "kennung": "E-" + anlass_id, "quellen", "stand", "thema",
       "ziel_ordner"}

Regeln (so umgesetzt, nicht anders):
  1. ``anlass_id`` ist ``thema_quelle`` aus dem Plan (im Bestand eindeutig);
     ``kennung`` = ``"E-" + anlass_id``. Beides haengt **nicht** an der
     Reihenfolge und ist damit stabil.
  2. Sortierung **fest**: ``datum`` aufsteigend, bei Gleichstand ``anlass_id``
     aufsteigend. Anlaesse **ohne** Datum sortieren hinter die datierten
     (Sortierschluessel ``1``) — ebenfalls reproduzierbar.
  3. ``datei_kennungen`` sind die ``fileid`` der Zuege dieses Anlasses als
     ganze Zahlen, aufsteigend; Zuege ohne brauchbare Kennung werden
     gezaehlt (``zuege_ohne_kennung``), nicht aufgenommen.
  4. ``ziel_ordner`` ist der ``ziel_pfad`` der zugeordneten Zuege; gibt es
     keinen brauchbaren, steht dort ehrlich ``null``.
  5. Zuege mit unbekannter ``thema_quelle`` zaehlen als
     ``zuege_ohne_anlass``. Reihenfolge der Pruefung: erst die Kennung, dann
     der Anlass — jeder Zug wird dadurch **genau einmal** gezaehlt.
  6. Anlaesse ohne lesbares ``datum`` werden **trotzdem** als Knoten gefuehrt
     (``datum: null``) und in ``ohne_datum`` gezaehlt; nichts geht verloren.
     Anlaesse ohne brauchbare ``thema_quelle`` koennen keinen stabilen Anker
     tragen und werden uebersprungen (kein erfundener Knoten).

Zaehlregeln (Invarianten, im Code als Zusicherung und im Test belegt):
  * ``zahlen.anlaesse == len(ereignisse)``
  * ``zahlen.dateien == sum(anzahl_dateien)``
  * ``zahlen.dateien + zahlen.zuege_ohne_anlass + zahlen.zuege_ohne_kennung
    == zahlen.zuege`` — keine Zug-Zeile verschwindet unbemerkt.
  * ``zahlen.events_wiederverwendet`` zaehlt jeden Anlass, dessen
    ``event_quelle`` **nicht** ``"neu"`` ist — im Bestand der Wert
    ``"vorschlag"`` (Event-Name kommt aus einem vorhandenen Ordner, N6e).
    Die **volle** Verteilung steht in ``zahlen.event_quellen``, damit kein
    Wert stillschweigend verschluckt wird. *Korrekturhinweis (28.09.):* der
    Feinauftrag nannte hier den Wert ``"ordner"`` — den gibt es im echten
    Plan nicht (gemessen: 2.088 × ``neu``, 39 × ``vorschlag``); gezaehlt wird
    deshalb jeder Wert ausser ``neu``.

Aufruf (Kommandozeile)::

    python tools/foto_sortierung/ereignisse_bauen.py --trocken
    python tools/foto_sortierung/ereignisse_bauen.py --limit 3
    python tools/foto_sortierung/ereignisse_bauen.py --ausgabe C:/tmp/e.jsonl --schreiben

Als Modul (Tests, spaetere Schritte): ``haupt(argv=[...])`` sowie die reinen
Funktionen ``plan_laden``, ``ereignisse_bauen``, ``ereignisse_schreiben``,
``knoten_zeile``, ``zahlen_text``.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

# Vorgabepfade: ausserhalb des Repos — dort liegen private Kennungen und Namen.
STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_PLAN = os.path.join(STANDARD_BASIS, "sortierplan.json")
STANDARD_AUSGABE = os.path.join(STANDARD_BASIS, "ereignisse.jsonl")

# Version des Schemas: erhoehen, sobald sich ein Schluessel aendert (die
# spaeteren Schritte lesen diese Datei; ein stiller Schemawechsel waere ein
# Bruch).
EREIGNISSE_VERSION = 1
EREIGNISSE_ART = "ereignisse"

# Die Schluessel des eingefrorenen Schemas — bindend fuer die Folgeschritte.
KNOTEN_SCHLUESSEL = (
    "anlass_id", "anzahl_dateien", "art", "datei_kennungen", "datum",
    "event", "event_quelle", "event_stufe", "jahr", "kategorie", "kennung",
    "quellen", "stand", "thema", "ziel_ordner",
)
QUELLEN_SCHLUESSEL = ("datum", "dateien", "ziel_ordner")
ZAHLEN_SCHLUESSEL = (
    "anlaesse", "dateien", "zuege", "zuege_ohne_anlass", "zuege_ohne_kennung",
    "ohne_datum", "ohne_thema", "kollisionen", "events_wiederverwendet",
    "event_quellen", "kategorien", "jahre", "themen",
)

# Quelle der Felder: welche Datei/welcher Block hat sie geliefert (Herkunft).
QUELLE_DATUM = "sortierplan.json:anlaesse"
QUELLE_DATEIEN = "sortierplan.json:zuege"

# Lesbares Datum = echte Kalenderangabe in der Form JJJJ-MM-TT (ASCII).
DATUM_MUSTER = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── Kleine Helfer (tolerant lesen, nie raten) ─────────────────────────────

def _text(wert) -> str:
    """Ein Feld als Text lesen — Nicht-Text und ``None`` werden zu ``\"\"``."""
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


def _stufe(wert):
    """``event_stufe`` durchreichen — leerer/untauglicher Wert wird ``None``."""
    text = _text(wert)
    return text or None


def _zahl(n) -> str:
    """Eine Zahl mit deutschen Tausenderpunkten (nur fuer die Ausgabe)."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def _verteilung_text(wert) -> str:
    """Eine Zaehl-Verteilung als deutsche Textzeile (``neu=3, vorschlag=1``).

    Leer oder unbrauchbar ergibt ``"keine"`` — die Konsole soll nie so tun,
    als haette sie Zahlen, die es nicht gibt.
    """
    if not isinstance(wert, dict) or not wert:
        return "keine"
    teile = []
    for name in sorted(wert):
        zahl = _als_int(wert.get(name))
        teile.append(f"{name}={_zahl(zahl if zahl is not None else 0)}")
    return ", ".join(teile)


def _datum_lesen(wert):
    """Ein Datum als ``JJJJ-MM-TT`` lesen — sonst ``None`` (nichts geraten).

    Nur eine echte Kalenderangabe gilt als lesbar. Anlaesse ohne lesbares
    Datum werden trotzdem als Knoten gefuehrt (``datum: null``); sie
    verschwinden nicht, sie werden nur gezaehlt.
    """
    text = _text(wert)
    if not DATUM_MUSTER.match(text):
        return None
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        return None
    return text


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


# ── 2. Die Ereignis-Knoten bauen (rein, ohne I/O) ─────────────────────────

def _plan_pruefen(plan) -> dict:
    """Den Plan auf Brauchbarkeit pruefen — deutsche ``ValueError`` statt Rueckfall.

    Ungueltig ist: kein Woerterbuch, oder ein Woerterbuch ohne die Schluessel
    ``anlaesse`` und ``zuege``. Ein solcher Plan ist kein Sortierplan; ihn
    stillschweigend als "null Ereignisse" auszugeben waere eine Falschaussage.
    """
    if not isinstance(plan, dict):
        raise ValueError(
            "Kein Sortierplan uebergeben: erwartet wird ein Woerterbuch mit "
            "den Schluesseln 'anlaesse' und 'zuege'.")
    for name in ("anlaesse", "zuege"):
        if name not in plan:
            raise ValueError(
                f"Der Sortierplan ist leer: es fehlt der Schluessel '{name}'.")
        if not isinstance(plan.get(name), list):
            raise ValueError(f"Der Schluessel '{name}' im Sortierplan ist keine Liste.")
    return plan


def _sortierschluessel(knoten: dict):
    """Feste Sortierung: ``datum`` aufsteigend, dann ``anlass_id`` aufsteigend.

    Knoten ohne Datum bekommen den Sortierschluessel ``1`` und stehen damit
    hinter den datierten (``0``) — reproduzierbar, ohne ``None``-Vergleich.
    """
    datum = knoten.get("datum")
    anlass_id = knoten.get("anlass_id") or ""
    if isinstance(datum, str) and datum:
        return (0, datum, anlass_id)
    return (1, "", anlass_id)


def ereignisse_bauen(plan: dict, *, stand: str | None = None) -> dict:
    """Aus dem Plan die Ereignis-Knoten bauen — **reine** Funktion ohne Datei/Netz.

    Kein Dateizugriff, kein Netzzugriff, keine Seiteneffekte; der uebergebene
    Plan wird nicht veraendert. ``stand`` ist injizierbar (Tests bleiben
    reproduzierbar); ohne ``stand`` wird der aktuelle Zeitpunkt mit Zeitzone
    gesetzt.

    Jeder Anlass ergibt **genau einen** Knoten (auch ohne Datum); die
    Zaehlregeln des Modulkopfes sind hier als Zusicherung im Code verankert.

    Rueckgabe: das eingefrorene Schema (siehe Modulkopf).
    """
    plan = _plan_pruefen(plan)
    if stand is not None and (not isinstance(stand, str) or not stand.strip()):
        raise ValueError("Der Stand muss ein nicht-leerer Text sein.")
    if stand is None:
        stand = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

    anlaesse = plan.get("anlaesse") or []
    zuege = plan.get("zuege") or []

    # 1. Anlaesse einsammeln: je thema_quelle genau ein Knoten-Kopf.
    kopf: dict = {}
    ohne_datum = 0
    ohne_thema = 0
    kollisionen = 0
    events_wiederverwendet = 0
    event_quellen: dict = {}
    for anlass in anlaesse:
        if not isinstance(anlass, dict):
            continue
        anlass_id = _text(anlass.get("thema_quelle"))
        if not anlass_id or anlass_id in kopf:
            # Ohne stabile Kennung kein Anker; ein zweiter Eintrag derselben
            # Kennung ist derselbe Anlass, kein zweiter Knoten.
            continue
        datum = _datum_lesen(anlass.get("datum"))
        if datum is None:
            ohne_datum += 1
        thema = _text(anlass.get("thema"))
        if not thema:
            ohne_thema += 1
        if anlass.get("kollision"):
            kollisionen += 1
        # "neu" = der Event-Name wird neu gebaut. Jeder andere Wert heisst:
        # der Event-Name kommt aus einem vorhandenen Ordner (im Bestand
        # "vorschlag" aus dem Event-Abgleich N6e). Beides wird gezaehlt, und
        # die volle Verteilung steht in event_quellen — kein Wert wird
        # stillschweigend verschluckt.
        quelle = _text(anlass.get("event_quelle"))
        if quelle:
            event_quellen[quelle] = event_quellen.get(quelle, 0) + 1
        if quelle and quelle != "neu":
            events_wiederverwendet += 1
        kopf[anlass_id] = {
            "datum": datum,
            "thema": thema,
            "jahr": _als_int(anlass.get("jahr")),
            "kategorie": _text(anlass.get("kategorie")),
            "event": _text(anlass.get("event")),
            "event_quelle": _text(anlass.get("event_quelle")),
            "event_stufe": _stufe(anlass.get("event_stufe")),
        }

    # 2. Zuege zuordnen: erst die Kennung pruefen, dann den Anlass.
    datei_kennungen: dict = {name: [] for name in kopf}
    ziel_ordner: dict = {}
    zuege_ohne_anlass = 0
    zuege_ohne_kennung = 0
    for zug in zuege:
        if not isinstance(zug, dict):
            zuege_ohne_kennung += 1
            continue
        kennung = _als_int(zug.get("fileid"))
        if kennung is None:
            zuege_ohne_kennung += 1
            continue
        anlass_id = _text(zug.get("thema_quelle"))
        if anlass_id not in kopf:
            zuege_ohne_anlass += 1
            continue
        datei_kennungen[anlass_id].append(kennung)
        if anlass_id not in ziel_ordner:
            ziel = _text(zug.get("ziel_pfad"))
            if ziel:
                ziel_ordner[anlass_id] = ziel

    # 3. Knoten bauen (Schluessel in der Reihenfolge des Schemas) und sortieren.
    ereignisse = []
    for anlass_id, eintrag in kopf.items():
        liste = sorted(datei_kennungen[anlass_id])
        ereignisse.append({
            "anlass_id": anlass_id,
            "anzahl_dateien": len(liste),
            "art": "ereignis",
            "datei_kennungen": liste,
            "datum": eintrag["datum"],
            "event": eintrag["event"],
            "event_quelle": eintrag["event_quelle"],
            "event_stufe": eintrag["event_stufe"],
            "jahr": eintrag["jahr"],
            "kategorie": eintrag["kategorie"],
            "kennung": "E-" + anlass_id,
            "quellen": {
                "datum": QUELLE_DATUM,
                "dateien": QUELLE_DATEIEN,
                "ziel_ordner": QUELLE_DATEIEN,
            },
            "stand": stand,
            "thema": eintrag["thema"],
            "ziel_ordner": ziel_ordner.get(anlass_id),
        })
    ereignisse.sort(key=_sortierschluessel)

    zahlen = {
        "anlaesse": len(ereignisse),
        "dateien": sum(knoten["anzahl_dateien"] for knoten in ereignisse),
        "zuege": len(zuege),
        "zuege_ohne_anlass": zuege_ohne_anlass,
        "zuege_ohne_kennung": zuege_ohne_kennung,
        "ohne_datum": ohne_datum,
        "ohne_thema": ohne_thema,
        "kollisionen": kollisionen,
        "events_wiederverwendet": events_wiederverwendet,
        "event_quellen": dict(sorted(event_quellen.items())),
        "kategorien": len({knoten["kategorie"] for knoten in ereignisse
                           if knoten["kategorie"]}),
        "jahre": len({knoten["jahr"] for knoten in ereignisse
                      if knoten["jahr"] is not None}),
        "themen": len({knoten["thema"] for knoten in ereignisse
                       if knoten["thema"]}),
    }

    # Zusicherungen: die Zaehlregeln des Modulkopfes halten immer.
    assert zahlen["anlaesse"] == len(ereignisse), "Anlasszahl != Knotenzahl"
    assert zahlen["dateien"] == sum(knoten["anzahl_dateien"]
                                    for knoten in ereignisse), "Dateizahl != Summe"
    assert (zahlen["dateien"] + zahlen["zuege_ohne_anlass"]
            + zahlen["zuege_ohne_kennung"] == zahlen["zuege"]), \
        "Jede Zug-Zeile muss genau einmal gezaehlt werden"

    return {
        "art": EREIGNISSE_ART,
        "version": EREIGNISSE_VERSION,
        "stand": stand,
        "plan_stand": _text(plan.get("stand")) or None,
        "zahlen": {name: zahlen[name] for name in ZAHLEN_SCHLUESSEL},
        "ereignisse": ereignisse,
    }


# ── 3. Eine Knotenzeile (reine Funktion) ──────────────────────────────────

def knoten_zeile(knoten: dict) -> str:
    """Einen Knoten als eine JSONL-Zeile — **rein**, kein Dateizugriff.

    Kodierung ``ensure_ascii=True`` und ``sort_keys=True`` (ASCII, kein
    Umlaut): dieselbe Eingabe ergibt immer dieselbe Zeile — der Text ist
    damit **inhaltlich** reproduzierbar.

    Praezise, gemessen am echten Lauf (28.09.): zwei Laeufe zu
    **verschiedenen** Zeitpunkten unterscheiden sich **ausschliesslich** im
    Feld ``stand`` (der Lauf-Zeitstempel steht in jeder Zeile); ohne
    ``stand`` sind die Dateien **byte-gleich** (Pruefsumme
    ``cfbbe6f68961b142`` ueber beide Laeufe). Ein zweiter Lauf mit
    **demselben** ``stand`` — so wie die Tests ihn vorgeben — ist auch mit
    ``stand`` byte-gleich. Kein Feld ausser ``stand`` ist zeitabhaengig.
    """
    if not isinstance(knoten, dict):
        raise ValueError("Ein Knoten muss ein Woerterbuch sein.")
    return json.dumps(knoten, ensure_ascii=True, sort_keys=True)


# ── 4. Schreiben: atomar als JSONL, nur ausserhalb des Repos ─────────────

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
        raise ValueError("Kein Zielpfad fuer die Ereignis-Knoten angegeben.")
    ziel = os.path.normcase(os.path.abspath(pfad))
    repo = os.path.normcase(os.path.abspath(REPO))
    try:
        gemeinsam = os.path.commonpath([ziel, repo])
    except ValueError:                        # anderes Laufwerk: nie im Repo
        return pfad
    if gemeinsam == repo:
        raise ValueError(
            f"Zieldatei liegt IM Repo und ist nicht erlaubt: {pfad}\n"
            f"Die Ereignis-Knoten gehoeren ausserhalb des Repos (Standard: "
            f"{STANDARD_AUSGABE}); es wird NICHTS geschrieben.")
    return pfad


def ereignisse_schreiben(pfad: str, daten: dict) -> str:
    """Die Ereignis-Knoten als JSONL schreiben — atomar, nur ausserhalb des Repos.

    Erst vollstaendig in ``<ziel>.tmp`` im **Zielordner** schreiben, dann per
    ``os.replace`` ersetzen: es entsteht nie eine halbe Datei. Scheitert das
    Schreiben, wird ausschliesslich die eigene temp-Datei wieder entfernt (die
    einzige Loeschung in diesem Modul) — eine vorhandene alte Zieldatei bleibt
    unangetastet. Ein Ziel im Repo ergibt eine deutsche ``ValueError``-Meldung.

    Die Datei ist reine JSONL: je Zeile genau ein Knoten, ASCII und
    schluesselsortiert; kein Kopfzeilen-Sonderfall, kein ``zahlen``-Block.

    Rueckgabe: der geschriebene Pfad.
    """
    ziel = _pruefe_ziel_ausserhalb_repo(pfad)
    if not isinstance(daten, dict):
        raise ValueError("Keine Ereignis-Knoten zum Schreiben uebergeben "
                         "(erwartet wird ein Woerterbuch).")
    knoten = daten.get("ereignisse")
    if not isinstance(knoten, list):
        raise ValueError("Zum Schreiben fehlt die Knotenliste 'ereignisse'.")
    ordner = os.path.dirname(os.path.abspath(ziel))
    os.makedirs(ordner, exist_ok=True)
    temp_pfad = ziel + ".tmp"
    try:
        with open(temp_pfad, "w", encoding="utf-8") as datei:
            for eintrag in knoten:
                datei.write(knoten_zeile(eintrag))
                datei.write("\n")
        os.replace(temp_pfad, ziel)
    except Exception:
        if os.path.exists(temp_pfad):
            os.remove(temp_pfad)              # nur die eigene temp-Datei
        raise
    return ziel


# ── 5. Der Bericht als Klartext (deutsch) ─────────────────────────────────

def zahlen_text(daten: dict) -> str:
    """Die Zahlen des Laufs als mehrzeiliger deutscher Klartext.

    Enthaelt Stand, Plan-Stand und **alle** Zaehler (Anlaesse, Dateien, Zuege,
    ohne Anlass, ohne Kennung, ohne Datum, ohne Thema, Kollisionen, Events
    wiederverwendet, Event-Quellen (Verteilung), Kategorien, Jahre, Themen).
    Fehlende Felder ergeben ``0``
    statt eines Absturzes — die Funktion ist fuer die Konsole gebaut, nicht als
    Datenquelle (das ist die JSONL-Datei). Kennungen stehen hier nur als Zahl.
    """
    d: dict = daten if isinstance(daten, dict) else {}
    roh_zahlen = d.get("zahlen")
    zahlen: dict = roh_zahlen if isinstance(roh_zahlen, dict) else {}

    def wert(name: str) -> int:
        zahl = _als_int(zahlen.get(name))
        return zahl if zahl is not None else 0

    zeilen = [
        f"Ereignis-Knoten N27 Schritt 1 - Stand "
        f"{_text(d.get('stand')) or 'unbekannt'} "
        f"(Plan-Stand {_text(d.get('plan_stand')) or 'unbekannt'})",
        f"Anlaesse: {_zahl(wert('anlaesse'))}   "
        f"Dateien: {_zahl(wert('dateien'))}   "
        f"Zuege: {_zahl(wert('zuege'))}",
        f"ohne Anlass: {_zahl(wert('zuege_ohne_anlass'))}   "
        f"ohne Kennung: {_zahl(wert('zuege_ohne_kennung'))}   "
        f"ohne Datum: {_zahl(wert('ohne_datum'))}   "
        f"ohne Thema: {_zahl(wert('ohne_thema'))}",
        f"Kollisionen: {_zahl(wert('kollisionen'))}   "
        f"Events wiederverwendet: {_zahl(wert('events_wiederverwendet'))}   "
        f"Event-Quellen: {_verteilung_text(zahlen.get('event_quellen'))}",
        f"Kategorien: {_zahl(wert('kategorien'))}   "
        f"Jahre: {_zahl(wert('jahre'))}   "
        f"Themen: {_zahl(wert('themen'))}",
        "ohne Bilddaten, ohne Personen, nur Kennungen und Zahlen",
    ]
    return "\n".join(zeilen)


# ── 6. Kommandozeile ─────────────────────────────────────────────────────

def haupt(argv=None) -> int:
    """Kommandozeile: Plan lesen, Zahlen zeigen, nur mit ``--schreiben`` ablegen.

    ``--plan`` (Standard: der echte Sortierplan), ``--ausgabe`` (Standard:
    ``~/foto_sortierung/ereignisse.jsonl``), ``--trocken`` (Standard) und
    ``--schreiben``; ``--limit N`` zeigt nur die ersten N Knoten auf der
    Konsole (Standard 5). Ohne ``--schreiben`` ist es ein reiner Trockenlauf:
    dieselben Zahlen auf der Konsole, keine Datei. Ein Ziel im Repo ergibt eine
    deutsche Meldung auf ``stderr`` und Exit 2 — auch im Trockenlauf, damit der
    Fehler frueh auffaellt und nicht erst beim ersten Schreiben.
    """
    zerleger = argparse.ArgumentParser(
        description="Ereignis-Knoten N27 Schritt 1: liest NUR den lokalen "
                    "Sortierplan und baut je Anlass einen Knoten mit Datum, "
                    "Thema und Datei-Kennungen — ohne Bilder, ohne Netz, "
                    "ohne Personen.")
    zerleger.add_argument("--plan", dest="plan", default=STANDARD_PLAN,
                          help="Sortierplan (JSON, ausserhalb des Repos)")
    zerleger.add_argument("--ausgabe", dest="ausgabe", default=STANDARD_AUSGABE,
                          help="Zieldatei der Knoten (JSONL, ausserhalb des Repos)")
    zerleger.add_argument("--trocken", action="store_true",
                          help="nur Zahlen zeigen, nichts schreiben (Standard)")
    zerleger.add_argument("--schreiben", action="store_true",
                          help="die Datei wirklich schreiben (atomar, nur "
                               "ausserhalb des Repos); --trocken hat Vorrang")
    zerleger.add_argument("--limit", dest="limit", type=int, default=5,
                          help="nur die ersten N Knoten auf der Konsole zeigen "
                               "(Standard 5)")
    args = zerleger.parse_args(argv)

    schreiben = bool(args.schreiben) and not bool(args.trocken)
    limit = args.limit

    try:
        if limit < 0:
            raise ValueError("Das Limit muss eine Zahl >= 0 sein.")
        plan = plan_laden(args.plan)
        daten = ereignisse_bauen(plan)
        _pruefe_ziel_ausserhalb_repo(args.ausgabe)
    except ValueError as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2

    print("Ereignis-Knoten N27 Schritt 1 - "
          + ("SCHREIBEN" if schreiben else "TROCKENLAUF (es wird nichts geschrieben)"))
    print(f"Sortierplan: {args.plan}")
    print(zahlen_text(daten))

    knoten = daten["ereignisse"]
    for eintrag in knoten[:limit]:
        print(knoten_zeile(eintrag))
    if limit < len(knoten):
        print(f"... und {_zahl(len(knoten) - limit)} weitere Knoten")

    if not schreiben:
        print(f"Trockenlauf: {args.ausgabe} wurde NICHT geschrieben.")
        return 0

    try:
        ziel = ereignisse_schreiben(args.ausgabe, daten)
    except ValueError as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2
    print(f"Ereignis-Knoten geschrieben: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(haupt())
