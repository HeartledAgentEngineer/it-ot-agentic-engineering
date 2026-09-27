"""Ziel-Kategorien fuer das Foto-Sortieren (Nachtlauf-Schritt N6d, 27.09.2026).

Wozu dieses Werkzeug:
  Die Themen-Stufe (``foto_themen_vision.py`` + ``themen_katalog.py``) liefert je
  Anlass EIN Motiv-Thema aus 53 festen Eintraegen. Diese 53 Themen sind aber
  **nicht** die Ziel-Ordner: Sebastian hat in seiner pCloud selbst Kategorien
  angelegt, und dorthin soll spaeter sortiert werden. Damit die beiden Welten
  zusammenpassen, gibt es hier eine **Uebersetzung**:

      Motiv-Thema (53 Eintraege)  ->  Bucket (11 generische Ziel-Eimer)
                                  ->  echter Ordner in der pCloud (oder Neubau)

  Die Zuordnung Thema -> Bucket steht als ``MOTIV_ZU_BUCKET`` fest im Code
  (generisch, committbar). Die Zuordnung Bucket -> echter Ordnername steht
  **nicht** im Code, sondern in einer lokalen Datei ausserhalb des Repos
  (``~/foto_sortierung/kategorie_zuordnung.json``) — die echten Ordnernamen
  gehen das Repository nichts an.

Datenschutz (Regel des Auftrags, hier als Code):
  * Der Bestand (``~/foto_sortierung/kategorien.json``) enthaelt Ordnernamen
    Dritter und Ortsnamen. Er wird NUR gelesen und geschrieben, nie gedruckt
    und nie ins Repo geschrieben. ``bestand_holen`` schreibt ausschliesslich
    den uebergebenen Pfad, und der wird vorher auf "ausserhalb des Repos"
    geprueft (``_pruefe_ziel``).
  * Es gibt in dieser Datei KEINE Loeschfunktion: kein ``delete …``-Aufruf der
    pCloud-API, kein Umbenennen, kein Verschieben. Die einzige Ausnahme ist die
    eigene ``.tmp``-Datei, die beim Scheitern eines atomaren Schreibvorgangs
    aufgeraeumt wird.
  * Gegenueber der pCloud wird NUR gelesen (``service.liste``). Kein ``thumb``,
    kein Download, kein Schreiben — und keine Rekursion: feste Tiefe 2
    (Wurzelordner -> Kategorie -> Unterordner), genau wie der Bestand aussieht.

Der Bestand (Schema von ``kategorien.json``)::

    {
      "stand": "2026-09-27T09:40:53",        # Zeitstempel des Einlesens
      "wurzel": "Bilder & Videos",           # Wurzelordner in der pCloud
      "kategorien": [
        {"name": "<Ordnername>", "folderid": 123456,
         "unterordner": ["<Name>", ...], "dateien_direkt": 42}
      ]
    }

  ``dateien_direkte`` wird beim Lesen als zweite Schreibweise akzeptiert
  (der Auftragstext nennt das Feld so, die vorhandene Bestandsdatei schreibt
  es ``dateien_direkt``); geschrieben wird immer ``dateien_direkt`` — also
  genau die Schreibweise des vorhandenen Bestands, damit die Datei
  kompatibel bleibt.

Die Zuordnungsdatei (Schema von ``kategorie_zuordnung.json``)::

    {"buckets": {"Urlaub": "<Ordnername aus kategorien.json>", "Familie": null}}

  Copy-Vorlage mit ALLEN elf Schluesseln (Werte ersetzt der Mensch; ``null``
  heisst "Ordner noch nicht vorhanden")::

    {"buckets": {"Urlaub": null, "Ausfluege": null, "Familie": null,
                 "Freunde": null, "Konzerte und Partys": null,
                 "Schule und Studium": null, "Hobbys": null,
                 "Screenshots": null, "Rezepte": null,
                 "Alltag und Wohnen": null, "Sonstiges": null}}

  Jeder Bucket-Schluessel MUSS in ``BUCKETS`` stehen. ``null`` heisst: es gibt
  noch keinen Ordner, der wird spaeter neu angelegt (``ziel_kategorie`` gibt
  dann ``None``). Fehlt in der Datei ein Bucket, ist das ein Fehler und keine
  stille Erweiterung: die Datei ist die **Vorlage fuer den Menschen**, sie
  soll vollstaendig sichtbar machen, was noch nicht zugeordnet ist.

Der Bauplan der Zielpfade: ``Agent/Fotos/<Jahr>/<Kategorie>/<Event>``
(``ziel_pfad``) — jeder Teil laeuft durch ``pfad_saeubern``, damit daraus
gueltige Ordner- und Dateinamen werden.

Wiederholbarkeit (warum ``bestand_holen`` nichts aendert, wenn nichts neu ist):
  ``bestand_holen`` baut den Inhalt **ohne** ``stand`` und vergleicht ihn mit
  dem bereits gelesenen Inhalt **ohne** ``stand``. Ist beides gleich, bleibt
  die Datei unangetastet (Meldung "unveraendert") — das Feld ``stand`` wird
  also nur beim ersten Schreiben bzw. bei echter Aenderung neu gesetzt. Ohne
  diesen Vergleich waere jeder Lauf "anders" (nur wegen der Uhrzeit), die
  Datei waere nie byte-identisch und ein Dauerlauf koennte seinen eigenen
  Fortschritt nicht erkennen. Geprueft wird in ``test_foto_kategorien.py``
  per md5 vor/nach dem zweiten Lauf.

Aufruf (Kommandozeile)::

    python tools/foto_sortierung/foto_kategorien.py --zeigen
    python tools/foto_sortierung/foto_kategorien.py --bestand-holen --trocken
    python tools/foto_sortierung/foto_kategorien.py --bestand-holen --schreiben

Als Modul (Tests, Skripte): ``main(argv=[...], service=<Attrappe>)``.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import re

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

# Vorgabepfade: ausserhalb des Repos — dort liegen private Ordnernamen.
STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_KATEGORIEN = os.path.join(STANDARD_BASIS, "kategorien.json")
STANDARD_ZUORDNUNG = os.path.join(STANDARD_BASIS, "kategorie_zuordnung.json")

# Der Wurzelordner in der pCloud, unter dem die Kategorien liegen.
WURZEL_STANDARD = "Bilder & Videos"


def _modul_aus_pfad(pfad: str, name: str):
    """Ein Nachbarmodul per Pfad laden (Muster aus ``foto_themen_vision.py``)."""
    spez = importlib.util.spec_from_file_location(name, pfad)
    if spez is None or spez.loader is None:
        raise RuntimeError(f"Modul nicht gefunden: {pfad}")
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


# Der Themen-Katalog liegt neben dieser Datei und ist rein (kein Netz, kein I/O).
_katalog = _modul_aus_pfad(os.path.join(HIER, "themen_katalog.py"), "themen_katalog")

KATALOG_VERSION = _katalog.KATALOG_VERSION
THEMEN_KATALOG = _katalog.THEMEN_KATALOG
thema_normalisieren_katalog = _katalog.thema_normalisieren_katalog

# ── Die Buckets: generische Ziel-Eimer ─────────────────────────────────────

# Bewusst generisch: die ECHTEN Ordnernamen stehen nur in der lokalen
# Zuordnungsdatei. "Sonstiges" ist der Rueckfall und muss enthalten sein.
SONSTIGES = "Sonstiges"
OHNE_NAME = "Ohne-Name"

BUCKETS: list[str] = [
    "Urlaub",
    "Ausfluege",
    "Familie",
    "Freunde",
    "Konzerte und Partys",
    "Schule und Studium",
    "Hobbys",
    "Screenshots",
    "Rezepte",
    "Alltag und Wohnen",
    SONSTIGES,                      # Rueckfall — MUSS enthalten sein
]

# ── Thema -> Bucket ────────────────────────────────────────────────────────

# Jeder der 53 Katalog-Eintraege aus ``themen_katalog.THEMEN_KATALOG`` wird
# GENAU EINEM Bucket zugeordnet (vollstaendig, keine Luecke, keine Doppelung);
# die Tests pruefen das gegen den Katalog selbst. Die Wahl folgt dem Sinn des
# Motivs, nicht dem Zufall — Faustregeln:
#   * Zuhause/Personen/private Feiern  -> Familie
#   * Weggehen, Reisen, Natur draussen -> Urlaub / Ausfluege
#   * Haushalt, Wohnung, Fahrzeuge, Papierkram -> Alltag und Wohnen
#   * Ausgehen am Abend/Feiern mit Gaesten -> Konzerte und Partys
#   * Selbermachen (Garten, Technik, Sport, Werkzeug) -> Hobbys
#   * Bildschirmfotos -> Screenshots; Essen/Kochen/Backen -> Rezepte
MOTIV_ZU_BUCKET: dict[str, str] = {
    # Personen & Familie
    "Familienfeier Zuhause": "Familie",
    "Kindergeburtstag Zuhause": "Familie",
    "Babybauch Fotoshooting": "Familie",
    "Familienausflug Wochenende": "Familie",
    "Hund im Freien": "Familie",              # das Haustier gehoert dazu
    "Katze Zuhause": "Familie",
    # Haus & Garten (Wohnen) — Gartenarbeit und Blueten sind eher Hobby
    "Haus und Garten": "Alltag und Wohnen",
    "Gartenarbeit im Freien": "Hobbys",
    "Balkon und Terrasse": "Alltag und Wohnen",
    "Blumen im Garten": "Hobbys",
    # Natur & Landschaft
    "Wandern im Schnee": "Ausfluege",
    "Wanderung im Wald": "Ausfluege",
    "See und Fluss": "Urlaub",
    "Berg und Tal": "Urlaub",
    "Strand und Meer": "Urlaub",
    # Tiere (Zoo und Hof sind Ausflugsziele)
    "Tiere im Zoo": "Ausfluege",
    "Tiere auf dem Land": "Ausfluege",
    # Stadt & Reisen
    "Stadtbummel Altstadt": "Ausfluege",
    "Reise und Urlaub": "Urlaub",
    "Ausflug ins Umland": "Ausfluege",
    "Museum und Ausstellung": "Ausfluege",
    "Weihnachtsmarkt Besuch": "Ausfluege",
    "Restaurant Besuch": "Ausfluege",         # Ausgehen, nicht Kochen
    "Zug und Bahnhof": "Ausfluege",           # unterwegs sein
    # Veranstaltungen & Feste
    "Fest und Feier": "Konzerte und Partys",
    "Konzert und Buehne": "Konzerte und Partys",
    "Geburtstag mit Gaesten": "Konzerte und Partys",
    "Abendhimmel und Sonnenuntergang": "Ausfluege",
    "Stadt bei Nacht": "Konzerte und Partys",  # Nachtleben
    # Menschen ohne Anlass
    "Selfie und Portraet": "Freunde",
    "Freunde unterwegs": "Freunde",
    # Oeffentlichkeit: kein eigener Eimer vorhanden -> Rueckfall
    "Demonstration und Politik": SONSTIGES,
    # Arbeit, Technik, Alltag
    "Arbeit am Schreibtisch": "Schule und Studium",
    "Technik und Geraete": "Hobbys",
    "Computer und Bildschirm": "Hobbys",
    # Essen & Trinken
    "Essen und Trinken": "Rezepte",
    "Kochen in der Kueche": "Rezepte",
    "Kuchen und Gebaeck": "Rezepte",
    # Sport & Bewegung
    "Sport und Fitness": "Hobbys",
    "Laufen und Joggen": "Hobbys",
    "Spiel und Bewegung": "Hobbys",
    # Fahrzeuge
    "Auto und Strasse": "Alltag und Wohnen",
    "Fahrrad und Radweg": "Hobbys",
    # Innenraum & Alltag
    "Wohnung und Einrichtung": "Alltag und Wohnen",
    "Aufraeumen Zuhause": "Alltag und Wohnen",
    "Fenster und Licht": "Alltag und Wohnen",
    # Bauen & Handwerk
    "Bauen und Renovieren": "Alltag und Wohnen",
    "Handwerk und Werkzeug": "Hobbys",
    "Baustelle und Geruest": "Alltag und Wohnen",
    # Text, Bildschirm & Papier
    "Text und Screenshot": "Screenshots",
    "Zeitungen und Dokumente": "Alltag und Wohnen",   # Papierkram/Post
    # Dinge & Stillleben
    "Dinge und Stillleben": "Alltag und Wohnen",
    # Rueckfall
    SONSTIGES: SONSTIGES,
}


class KategorienFehler(Exception):
    """Fehler dieses Werkzeugs — deutsche Klartextmeldung, kein Absturz."""


# ── Bucket-Suche ───────────────────────────────────────────────────────────

def bucket_fuer_thema(thema) -> str:
    """Den Bucket zu einem Motiv-Thema finden — sonst ``Sonstiges``.

    Gesucht wird normalisiert (wie ``thema_katalog.thema_normalisieren_katalog``:
    Kleinschreibung, Leerraum zusammengezogen, Rand-Satzzeichen weg), damit
    ``"  see und meer. "`` den Eintrag ``"See und Meer"`` trifft. Unbekannt,
    ``None``, leer oder Nicht-Text: ``Sonstiges``. Diese Funktion wirft NIE
    eine Ausnahme — sie ist die letzte Instanz, wenn ein Thema nicht passt.
    """
    sauber = thema_normalisieren_katalog(thema)
    if not sauber:
        return SONSTIGES
    for eintrag, bucket in MOTIV_ZU_BUCKET.items():
        if thema_normalisieren_katalog(eintrag) == sauber:
            return bucket
    return SONSTIGES


# ── Datei lesen: Bestand und Zuordnung ─────────────────────────────────────

def _json_lesen(pfad: str, was: str):
    """Eine JSON-Datei lesen — fehlend oder kaputt gibt ``KategorienFehler``."""
    if not isinstance(pfad, str) or not pfad:
        raise KategorienFehler(f"Kein Pfad fuer {was} angegeben.")
    if not os.path.isfile(pfad):
        raise KategorienFehler(f"{was} nicht gefunden: {pfad}")
    try:
        with open(pfad, encoding="utf-8") as datei:
            return json.load(datei)
    except ValueError as problem:
        raise KategorienFehler(
            f"{was} ist kein lesbares JSON ({problem.__class__.__name__}): {pfad}"
        ) from None
    except OSError as problem:
        raise KategorienFehler(
            f"{was} nicht lesbar ({problem.__class__.__name__}): {pfad}"
        ) from None


# Pflichtfelder eines Kategorieneintrags. ``dateien_direkt`` ist die Schreibweise
# des vorhandenen Bestands; ``dateien_direkte`` (Auftragstext) wird als zweite
# Schreibweise akzeptiert — eine der beiden MUSS da sein.
PFLICHTFELDER = ("name", "folderid", "unterordner", "dateien_direkte")
_ZAEHL_NAMEN = ("dateien_direkt", "dateien_direkte")


def _als_int(wert) -> int:
    """Zahl tolerant lesen — fehlende/unbrauchbare Werte werden ehrlich 0."""
    try:
        return int(wert)
    except (TypeError, ValueError):
        return 0


def kategorien_laden(pfad: str) -> dict:
    """Den lokalen Bestand lesen und pruefen (Pflichtfelder je Kategorie).

    Erwartet das Schema ``{stand, wurzel, kategorien:[{name, folderid,
    unterordner, dateien_direkte}]}``. Fehlende Datei, kaputtes JSON, fehlende
    Liste oder ein Eintrag ohne Pflichtfeld ergeben eine ``KategorienFehler``
    mit deutscher Klartextmeldung (welcher Eintrag, welches Feld) — es wird
    NICHTS geraten und nichts stillschweigend ergaenzt.

    ``stand`` und ``wurzel`` fehlen zu duerfen waere eine Erfindung; auch sie
    werden verlangt. ``dateien_direkt`` wird als zweite Schreibweise des
    Zaehlfeldes akzeptiert (siehe ``PFLICHTFELDER``).
    """
    daten = _json_lesen(pfad, "Kategorien-Bestand")
    if not isinstance(daten, dict):
        raise KategorienFehler(
            f"Kategorien-Bestand ist kein JSON-Objekt: {os.path.basename(pfad)}")
    for feld in ("wurzel", "kategorien"):
        if feld not in daten:
            raise KategorienFehler(
                f"Kategorien-Bestand ohne Pflichtfeld '{feld}': "
                f"{os.path.basename(pfad)}")
    if not isinstance(daten.get("kategorien"), list):
        raise KategorienFehler(
            f"Kategorien-Bestand: 'kategorien' ist keine Liste: "
            f"{os.path.basename(pfad)}")

    sauber: list[dict] = []
    for nummer, eintrag in enumerate(daten["kategorien"]):
        if not isinstance(eintrag, dict):
            raise KategorienFehler(
                f"Kategorie Nr. {nummer + 1} ist kein JSON-Objekt.")
        for feld in PFLICHTFELDER:
            if feld == "dateien_direkte":
                if not any(name in eintrag for name in _ZAEHL_NAMEN):
                    raise KategorienFehler(
                        f"Kategorie Nr. {nummer + 1} ohne Pflichtfeld "
                        f"'dateien_direkt'.")
                continue
            if feld not in eintrag:
                raise KategorienFehler(
                    f"Kategorie Nr. {nummer + 1} ohne Pflichtfeld '{feld}'.")
        name = eintrag.get("name")
        if not isinstance(name, str) or not name.strip():
            raise KategorienFehler(f"Kategorie Nr. {nummer + 1} hat keinen Namen.")
        unterordner = eintrag.get("unterordner")
        if not isinstance(unterordner, list):
            raise KategorienFehler(
                f"Kategorie '{name}': 'unterordner' ist keine Liste.")
        if not all(isinstance(u, str) for u in unterordner):
            raise KategorienFehler(
                f"Kategorie '{name}': 'unterordner' enthaelt Nicht-Text.")
        zaehler = None
        for schreibweise in _ZAEHL_NAMEN:
            if schreibweise in eintrag:
                zaehler = eintrag[schreibweise]
                break
        if zaehler is not None and not isinstance(zaehler, int):
            raise KategorienFehler(
                f"Kategorie '{name}': 'dateien_direkt' ist keine Zahl.")
        sauber.append({
            "name": name,
            "folderid": eintrag.get("folderid"),
            "unterordner": list(unterordner),
            "dateien_direkt": _als_int(zaehler),
        })
    return {"stand": str(daten.get("stand") or ""),
            "wurzel": str(daten.get("wurzel") or ""),
            "kategorien": sauber}


def _namen(kategorien) -> list[str]:
    """Die Kategoriennamen aus einem geladenen Bestand (leer, wenn keiner)."""
    if not isinstance(kategorien, dict):
        return []
    return [str(e.get("name")) for e in kategorien.get("kategorien") or []
            if isinstance(e, dict) and e.get("name")]


def zuordnung_laden(pfad: str, kategorien) -> dict:
    """Die Zuordnung Bucket -> echter Ordnername lesen und streng pruefen.

    Schema: ``{"buckets": {"Urlaub": "<Ordnername aus kategorien.json>"}}``.
    Regeln, die hier erzwungen werden (kein stilles Erweitern):

      * Die Datei muss es geben (der Mensch legt sie an; es gibt keinen
        sinnvollen Vorgabewert, ohne die echten Namen zu erfinden).
      * Jeder Bucket-Schluessel muss in ``BUCKETS`` stehen — ein erfundener
        Eimer waere ein Ordner, den niemand kennt.
      * WERTE sind ``null`` (= Ordner fehlt noch, spaeter neu anlegen) oder
        ein Name, der WIRKLICH in ``kategorien.json`` steht. Ein unbekannter
        Name ist ein Fehler, der die betroffenen Buckets nennt; dazu kommt der
        erlaubte Namensraum, damit der Fehler ohne Nachsehen zu beheben ist.
      * Fehlt ein Bucket in der Datei, ist das ein Fehler (``KategorienFehler``)
        — die Datei ist die Vorlage, an der der Mensch sieht, was offen ist.

    Rueckgabe: ``{Bucket: Ordnername oder None}`` fuer ALLE Buckets.
    """
    daten = _json_lesen(pfad, "Kategorie-Zuordnung")
    if not isinstance(daten, dict):
        raise KategorienFehler(
            f"Kategorie-Zuordnung ist kein JSON-Objekt: {os.path.basename(pfad)}")
    buckets = daten.get("buckets")
    if not isinstance(buckets, dict):
        raise KategorienFehler(
            "Kategorie-Zuordnung ohne Objekt 'buckets' "
            f"({os.path.basename(pfad)}).")

    unbekannt = [name for name in buckets if name not in BUCKETS]
    if unbekannt:
        raise KategorienFehler(
            "Kategorie-Zuordnung nennt unbekannte Buckets: "
            + ", ".join(sorted(unbekannt))
            + ". Erlaubt sind genau: " + ", ".join(BUCKETS) + ".")

    fehlend = [name for name in BUCKETS if name not in buckets]
    if fehlend:
        raise KategorienFehler(
            "Kategorie-Zuordnung ist unvollstaendig, es fehlen: "
            + ", ".join(fehlend)
            + ". Jeder Bucket muss einen Eintrag haben (null = noch kein "
              "Ordner). Vorlage: " + ", ".join(BUCKETS) + ".")

    bekannt = _namen(kategorien)
    ergebnis: dict[str, str | None] = {}
    falsch: list[str] = []
    for name in BUCKETS:
        wert = buckets.get(name)
        if wert is None:
            ergebnis[name] = None
            continue
        if not isinstance(wert, str) or not wert.strip():
            raise KategorienFehler(
                f"Kategorie-Zuordnung: Bucket '{name}' hat einen unbrauchbaren "
                "Wert — erlaubt sind null oder ein Ordnername als Text.")
        ziel = wert.strip()
        if ziel not in bekannt:
            falsch.append(f"{name} -> {ziel}")
            continue
        ergebnis[name] = ziel
    if falsch:
        raise KategorienFehler(
            "Kategorie-Zuordnung nennt Zielordner, die es im Bestand nicht "
            "gibt: " + "; ".join(falsch)
            + ". Erlaubter Namensraum (Ordnernamen aus kategorien.json): "
            + (", ".join(bekannt) if bekannt else "keine Kategorien geladen")
            + ".")
    return ergebnis


def ziel_kategorie(bucket, zuordnung) -> str | None:
    """Der echte Zielordnername zu einem Bucket — oder ``None``.

    ``None`` heisst: es gibt (noch) keinen Ordner, er muss beim Sortieren neu
    angelegt werden. Unbekannte Buckets, Nicht-Text und leere Werte ergeben
    ebenfalls ``None`` statt eines Fehlers.
    """
    if not isinstance(zuordnung, dict):
        return None
    wert = zuordnung.get(bucket)
    if wert is None:
        # Zweite Chance: derselbe Bucket in anderer Schreibweise.
        klein = thema_normalisieren_katalog(bucket)
        for name, moeglich in zuordnung.items():
            if thema_normalisieren_katalog(name) == klein:
                wert = moeglich
                break
    if not isinstance(wert, str) or not wert.strip():
        return None
    return wert.strip()


# ── Pfad-Bausteine ─────────────────────────────────────────────────────────

# Dieselben verbotenen Zeichen wie im Themen-Werkzeug (Ordnernamen auf Windows
# UND in der pCloud): Schraegstriche, ``: * ? " < > |`` und Steuerzeichen.
VERBOTENE_ZEICHEN = re.compile(r'[/\\:*?"<>|\x00-\x1f]')

# Randzeichen, die als Ordnername unbrauchbar sind: Leerraum und Punkt.
PFAD_RAND_ZEICHEN = " ."

# Ordnergrenze: kurz genug fuer jeden Unterordner, lang genug fuer Klartext.
PFAD_MAX_ZEICHEN = 80

# Der Baum, unter dem der Agent seine Ordner anlegt.
ZIEL_BASIS = "Agent/Fotos"

JAHR_MIN = 1900
JAHR_MAX = 2100


def pfad_saeubern(name) -> str:
    """Einen Text in einen ordner-sicheren Namen verwandeln.

    Verbotene Zeichen (``/ \\ : * ? " < > |``, Steuerzeichen) werden zu
    Leerraum, Mehrfach-Leerraum wird zu einem Leerzeichen zusammengezogen,
    fuehrende/abschliessende Leerzeichen UND Punkte fallen weg, die Laenge wird
    auf ``PFAD_MAX_ZEICHEN`` begrenzt (**Umlaute bleiben erhalten** — es wird
    nichts transliteriert). Ist danach nichts uebrig, kommt ``"Ohne-Name"``
    zurueck: ein leerer Name waere kein Name.
    """
    if not isinstance(name, str):
        return OHNE_NAME
    sauber = VERBOTENE_ZEICHEN.sub(" ", name)
    sauber = re.sub(r"\s+", " ", sauber).strip()
    sauber = sauber.strip(PFAD_RAND_ZEICHEN)
    sauber = sauber[:PFAD_MAX_ZEICHEN]
    sauber = sauber.strip(PFAD_RAND_ZEICHEN).strip()
    return sauber or OHNE_NAME


def _jahr_pruefen(jahr) -> int:
    """Das Jahr pruefen und als int zurueckgeben — sonst ``ValueError``.

    ``bool`` wird abgelehnt (es ist zwar ein int, aber kein Jahr), Text wie
    ``"2025"`` ebenfalls: geraten wird nicht.
    """
    if isinstance(jahr, bool) or not isinstance(jahr, int):
        raise ValueError(
            f"Jahr muss eine ganze Zahl sein (z. B. 2025), war: {jahr!r}.")
    if not JAHR_MIN <= jahr <= JAHR_MAX:
        raise ValueError(
            f"Jahr muss zwischen {JAHR_MIN} und {JAHR_MAX} liegen, war: {jahr}.")
    return jahr


def ziel_pfad(jahr, kategorie, event) -> str:
    """Der Zielpfad ``Agent/Fotos/<Jahr>/<Kategorie>/<Event>``.

    Alle drei Teile laufen durch ``pfad_saeubern``. Das Jahr muss eine ganze
    Zahl zwischen ``JAHR_MIN`` und ``JAHR_MAX`` sein — sonst ``ValueError``
    mit Klartextmeldung (kein stiller Ersatzwert).
    """
    jahr = _jahr_pruefen(jahr)
    return "/".join([ZIEL_BASIS, str(jahr),
                     pfad_saeubern(kategorie), pfad_saeubern(event)])


# ── Bestandsbericht ────────────────────────────────────────────────────────

def _kategorien_liste(kategorien) -> list[dict]:
    """Die Kategorieneintraege aus einem Bestand (Dict ODER Liste) holen."""
    if isinstance(kategorien, dict):
        kategorien = kategorien.get("kategorien")
    if not isinstance(kategorien, list):
        return []
    return [e for e in kategorien if isinstance(e, dict)]


def bestandsbericht(kategorien, zuordnung) -> str:
    """Einen reinen Textbericht zum Bestand bauen (deterministisch).

    Gezaehlt wird ohne Dateizugriff und ohne Netz:

      * Anzahl Kategorien,
      * Anzahl Unterordner (Summe ueber alle Kategorien),
      * Anzahl Kategorien MIT Unterordnern,
      * Buckets gebunden (Name steht im Bestand),
      * Buckets ohne Zielordner (``null``),
      * Buckets ohne Treffer im Bestand (Name gibt es dort nicht) und Buckets,
        die in der Zuordnung ganz fehlen — beides zusammen gezaehlt.

    Die Zahlenreihenfolge ist fest, damit zwei Laeufe denselben Text ergeben.
    """
    eintraege = _kategorien_liste(kategorien)
    bekannt = [str(e.get("name")) for e in eintraege if e.get("name")]
    unterordner = sum(len(e.get("unterordner") or [])
                      for e in eintraege
                      if isinstance(e.get("unterordner"), list))
    mit_unterordnern = sum(
        1 for e in eintraege
        if isinstance(e.get("unterordner"), list) and e.get("unterordner"))

    gebunden = 0
    ohne_ordner = 0
    nicht_vorhanden = 0
    quelle = zuordnung if isinstance(zuordnung, dict) else {}
    for bucket in BUCKETS:
        if bucket not in quelle:
            nicht_vorhanden += 1
            continue
        wert = quelle[bucket]
        if wert is None:
            ohne_ordner += 1
        elif isinstance(wert, str) and wert.strip() and wert.strip() in bekannt:
            gebunden += 1
        else:
            nicht_vorhanden += 1

    return "\n".join([
        f"Kategorien: {len(eintraege)}",
        f"Unterordner: {unterordner}",
        f"Kategorien mit Unterordnern: {mit_unterordnern}",
        f"Buckets: {len(BUCKETS)}",
        f"Buckets gebunden: {gebunden}",
        f"Buckets ohne Zielordner (null): {ohne_ordner}",
        f"Buckets ohne Treffer in kategorien.json: {nicht_vorhanden}",
    ])


# ── Schreiben: nur ausserhalb des Repos, atomar ────────────────────────────

def _pruefe_ziel_ausserhalb_repo(pfad: str) -> str:
    """Sicherstellen, dass die Zieldatei AUSSERHALB des Repos liegt.

    Der Auftrag laesst Ausgaben nur ausserhalb des Repos zu (dort wuerden
    private Ordnernamen liegen). Geprueft wird der absolut aufgeloeste Pfad;
    Gross-/Kleinschreibung und Schraeg-/Rueckwaertsstriche spielen keine Rolle
    (``abspath`` + ``normcase`` + ``commonpath``). Liegt das Ziel im Repo, gibt
    es eine deutsche Klartext-Meldung und SystemExit(2) — es wird dann nichts
    geschrieben. Sonst kommt der Pfad zurueck.
    """
    ziel = os.path.normcase(os.path.abspath(pfad))
    repo = os.path.normcase(os.path.abspath(REPO))
    try:
        gemeinsam = os.path.commonpath([ziel, repo])
    except ValueError:                       # anderes Laufwerk: nie im Repo
        return pfad
    if gemeinsam == repo:
        print(f"Zieldatei liegt IM Repo und ist nicht erlaubt: {pfad}\n"
              f"Der Bestand gehoert ausserhalb des Repos (Standard: "
              f"{STANDARD_KATEGORIEN}); es wird NICHTS geschrieben.")
        raise SystemExit(2)
    return pfad


def _schreibe_atomar(ziel: str, inhalt: dict) -> None:
    """JSON atomar schreiben (temp-Datei im Zielordner + ``os.replace``).

    Nie halbe Dateien: Erst vollstaendig in ``<ziel>.tmp`` schreiben, dann
    ersetzen. Scheitert das Schreiben, wird NUR die eigene temp-Datei wieder
    entfernt (die einzige Loeschung in dieser Datei) — die alte Zieldatei
    bleibt unangetastet.
    """
    ordner = os.path.dirname(os.path.abspath(ziel))
    os.makedirs(ordner, exist_ok=True)
    temp = ziel + ".tmp"
    try:
        with open(temp, "w", encoding="utf-8") as datei:
            json.dump(inhalt, datei, ensure_ascii=False, indent=1)
            datei.write("\n")
        os.replace(temp, ziel)
    except Exception:
        if os.path.exists(temp):
            os.remove(temp)                  # nur die eigene temp-Datei
        raise


def _inhalt_ohne_stand(inhalt) -> dict:
    """Den Bestand ohne das Feld ``stand`` — fuer den Wiederholbarkeitsvergleich."""
    if not isinstance(inhalt, dict):
        return {}
    kopie = {name: wert for name, wert in inhalt.items() if name != "stand"}
    return kopie


# ── Bestand aus der pCloud holen (NUR LESEND) ──────────────────────────────

def _wurzel_ordner(service, wurzelname: str) -> dict:
    """Den Wurzelordner in der pCloud finden — ohne Rekursion, nur ``liste``."""
    for eintrag in service.liste(0):
        if (isinstance(eintrag, dict) and eintrag.get("ist_ordner")
                and str(eintrag.get("name") or "").casefold()
                == str(wurzelname).casefold()):
            return eintrag
    raise KategorienFehler(
        f"Wurzelordner '{wurzelname}' wurde in der pCloud nicht gefunden.")


def bestand_holen(service, kategorien_pfad: str = STANDARD_KATEGORIEN,
                  wurzelname: str = WURZEL_STANDARD,
                  trocken: bool = False) -> dict:
    """Den pCloud-Bestand LESEND einlesen und als ``kategorien.json`` ablegen.

    Liest genau zwei Ebenen (kein Rekursieren, kein ``thumb``, kein Download):

      1. ``service.liste(0)`` — darin den Wurzelordner ``wurzelname`` suchen,
      2. ``service.liste(<folderid der Kategorie>)`` je Kategorie — daraus die
         Unterordner (Namen) und die Zahl der Dateien DIREKT in der Kategorie.

    Kategorien ohne Unterordner bekommen eine LEERE Liste (``[]``) — nicht
    ``None``, denn "hat keine Unterordner" ist eine Aussage, keine Luecke.

    Geschrieben wird atomar und nur, wenn sich inhaltlich etwas geaendert hat:
    Der neue Inhalt OHNE ``stand`` wird mit dem vorhandenen Inhalt OHNE
    ``stand`` verglichen. Sind beide gleich, bleibt die Datei byte-identisch
    (Meldung "unveraendert") und ``stand`` wird NICHT neu gesetzt — sonst
    waere jeder Lauf "anders", nur weil die Uhr weiterlief, und die
    Wiederholbarkeit waere nicht pruefbar. ``trocken=True`` zeigt nur, was
    geschrieben wuerde, und fasst die Platte nicht an.

    Rueckgabe (Klartextzahlen, keine Ordnernamen): ``geschrieben``,
    ``unveraendert``, ``trocken``, ``ziel``, ``kategorien``, ``unterordner``.
    """
    _pruefe_ziel_ausserhalb_repo(kategorien_pfad)

    wurzel = _wurzel_ordner(service, wurzelname)
    kategorien: list[dict] = []
    for eintrag in service.liste(wurzel.get("folderid")):
        if not isinstance(eintrag, dict) or not eintrag.get("ist_ordner"):
            continue                      # Dateien direkt in der Wurzel: nicht Teil des Bestands
        unterordner: list[str] = []
        dateien_direkt = 0
        for kind in service.liste(eintrag.get("folderid")):
            if not isinstance(kind, dict):
                continue
            if kind.get("ist_ordner"):
                unterordner.append(str(kind.get("name") or ""))
            else:
                dateien_direkt += 1
        kategorien.append({
            "name": str(eintrag.get("name") or ""),
            "folderid": eintrag.get("folderid"),
            "unterordner": unterordner,
            "dateien_direkt": dateien_direkt,
        })

    unterordner_gesamt = sum(len(e["unterordner"]) for e in kategorien)

    vorhanden = None
    if os.path.isfile(kategorien_pfad):
        try:
            with open(kategorien_pfad, encoding="utf-8") as datei:
                vorhanden = json.load(datei)
        except (OSError, ValueError):
            vorhanden = None                  # kaputt -> wird ersetzt

    if vorhanden is not None:
        neu_ohne = _inhalt_ohne_stand({"wurzel": str(wurzelname),
                                       "kategorien": kategorien})
        if _inhalt_ohne_stand(vorhanden) == neu_ohne:
            print(f"Bestand unveraendert: {kategorien_pfad} "
                  f"({len(kategorien)} Kategorien, {unterordner_gesamt} "
                  f"Unterordner)")
            return {"geschrieben": False, "unveraendert": True,
                    "trocken": bool(trocken), "ziel": kategorien_pfad,
                    "kategorien": len(kategorien),
                    "unterordner": unterordner_gesamt}

    inhalt = {
        "stand": datetime.datetime.now().isoformat(timespec="seconds"),
        "wurzel": str(wurzelname),
        "kategorien": kategorien,
    }
    if trocken:
        print(f"Trockenlauf: {kategorien_pfad} wuerde geschrieben "
              f"({len(kategorien)} Kategorien, {unterordner_gesamt} "
              f"Unterordner, Wurzel '{wurzelname}').")
        return {"geschrieben": False, "unveraendert": False, "trocken": True,
                "ziel": kategorien_pfad, "kategorien": len(kategorien),
                "unterordner": unterordner_gesamt}

    _schreibe_atomar(kategorien_pfad, inhalt)
    print(f"Bestand geschrieben: {kategorien_pfad} ({len(kategorien)} "
          f"Kategorien, {unterordner_gesamt} Unterordner)")
    return {"geschrieben": True, "unveraendert": False, "trocken": False,
            "ziel": kategorien_pfad, "kategorien": len(kategorien),
            "unterordner": unterordner_gesamt}


def pcloud_service_laden():
    """Den lesenden pCloud-Dienst holen — erst hier, damit der Import leicht bleibt.

    Das Werkzeug liegt ausserhalb des Backends; ein Import auf Modulebene
    wuerde beim Laden der Datei die Backend-Konfiguration mitziehen. Deshalb
    wird ``backend`` erst hier in den Suchpfad gelegt und der Dienst per
    ``importlib`` geholt (Muster: ``app.services.pcloud_service``,
    ausschliesslich LESEND).
    """
    import importlib
    import sys

    backend = os.path.join(REPO, "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    modul = importlib.import_module("app.services.pcloud_service")
    return modul.pcloud_service


# ── Kommandozeile ──────────────────────────────────────────────────────────

def _zeilen_bindungen(zuordnung) -> list[str]:
    """Eine Klartextzeile je Bucket (Zielordner oder Hinweis 'neu anlegen')."""
    zeilen = []
    for bucket in BUCKETS:
        ziel = ziel_kategorie(bucket, zuordnung)
        zeilen.append(f"  {bucket:<22} -> "
                      + (ziel if ziel else "KEIN Ordner (beim Sortieren neu anlegen)"))
    return zeilen


def main(argv=None, service=None) -> int:
    """Kommandozeilen-Teil.

    ``service`` (pCloud-Dienst) ist fuer Tests injizierbar; ohne ihn wird er
    erst bei ``--bestand-holen`` geladen.
    """
    zerleger = argparse.ArgumentParser(
        description="Ziel-Kategorien fuer das Foto-Sortieren: Bestand aus der "
                    "pCloud einlesen und Buckets auf echte Ordner abbilden.")
    zerleger.add_argument("--bestand-holen", dest="bestand_holen",
                          action="store_true",
                          help="den Kategorien-Bestand LESEND aus der pCloud "
                               "einlesen (ohne --schreiben nur anzeigen)")
    zerleger.add_argument("--trocken", action="store_true",
                          help="nur zeigen, was geschrieben wuerde (Standard: "
                               "es wird NICHTS geschrieben)")
    zerleger.add_argument("--schreiben", action="store_true",
                          help="die Bestandsdatei wirklich schreiben "
                               "(atomar, nur bei echter Aenderung)")
    zerleger.add_argument("--kategorien-pfad", dest="kategorien_pfad",
                          default=STANDARD_KATEGORIEN,
                          help="Bestandsdatei (ausserhalb des Repos)")
    zerleger.add_argument("--zuordnung-pfad", dest="zuordnung_pfad",
                          default=STANDARD_ZUORDNUNG,
                          help="Zuordnung Bucket -> Ordner (ausserhalb des Repos)")
    zerleger.add_argument("--zeigen", action="store_true",
                          help="Bestand und Bucket-Bindungen als Klartext anzeigen")
    args = zerleger.parse_args(argv)

    schreiben = bool(args.schreiben) and not bool(args.trocken)

    try:
        if args.bestand_holen:
            print(f"Bestand holen (nur lesend): {args.kategorien_pfad}")
            dienst = service or pcloud_service_laden()
            ergebnis = bestand_holen(dienst, args.kategorien_pfad,
                                     trocken=not schreiben)
            print(f"Kategorien: {ergebnis['kategorien']}   "
                  f"Unterordner: {ergebnis['unterordner']}   "
                  f"geschrieben: {'ja' if ergebnis['geschrieben'] else 'nein'}"
                  + ("   (Trockenlauf, nichts angefasst)"
                     if ergebnis["trocken"] else ""))
            if not schreiben:
                print("Ohne --schreiben wurde NICHTS geschrieben "
                      "(--trocken ist der Standard).")
            return 0

        # Standard (auch mit --zeigen): Bestand und Zuordnung nur anzeigen.
        kategorien = kategorien_laden(args.kategorien_pfad)
        zuordnung = zuordnung_laden(args.zuordnung_pfad, kategorien)
        print(f"Bestand: {args.kategorien_pfad}")
        print(f"Zuordnung: {args.zuordnung_pfad}")
        print(bestandsbericht(kategorien, zuordnung))
        print("Buckets:")
        for zeile in _zeilen_bindungen(zuordnung):
            print(zeile)
        print("Zielpfad-Schema: " + ZIEL_BASIS + "/<Jahr>/<Kategorie>/<Event>")
        print("Es wurde nichts geschrieben.")
        return 0
    except KategorienFehler as problem:
        print(f"Fehler: {problem}")
        return 2
    except SystemExit:
        raise


if __name__ == "__main__":
    raise SystemExit(main())
