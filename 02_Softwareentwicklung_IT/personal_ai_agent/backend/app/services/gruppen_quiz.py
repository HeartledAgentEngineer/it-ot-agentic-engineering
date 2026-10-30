"""Personen benennen im Gruppenmodus (Plan Foto-Gedaechtnis Schritt 2, 01.10.2026).

Warum:
  Das alte Gesichter-Quiz fragt Bild fuer Bild — bei ~30.000 Gesichtern
  undurchfuehrbar. ``tools/foto_sortierung/personen_gruppieren.py`` hat am PC
  alle Gesichter zu Gruppen zusammengefasst (``personen_beispiele.json``: je
  Gruppe Groesse, Zeitraum, bis zu 8 Beispiel-Gesichter, Zwillings-Kandidaten).
  Hier benennt Sebastian ganze Gruppen auf einmal: die groesste offene zuerst
  (die meiste Wirkung je Antwort).

Antworten (``ARTEN``):
  * ``name``        — die Gruppe ist <Name>. Hat schon eine andere Gruppe
                      denselben Namen, kommt zusaetzlich ein ``gleich``-Paar in
                      die Vorgaben (dieselbe Person, beim naechsten PC-Lauf
                      zusammengelegt).
  * ``gleich``      — dieselbe Person wie Gruppe ``ziel`` (Zwillings-Kandidat).
                      Ein Name gilt danach fuer alle so verbundenen Gruppen
                      (auch mehrstufig, nur unbenannte werden ergaenzt); sind
                      beide noch unbenannt, bleibt die Gruppe zum Benennen
                      stehen und zeigt den verbundenen Vorschlag mit an.
  * ``verschieden`` — eine andere Person als Gruppe ``ziel``.
  * ``spaeter``     — jetzt nicht; kommt wieder, wenn alles andere erledigt ist.
  * ``unbekannt``   — kenne ich nicht / fremde Menge; wird nicht mehr gefragt.
  * ``aufloesen``   — die einer Person zugeordnete Gruppe aus der Gruppenliste
                      nehmen (To-do Punkt 14, 18.10.2026): die Kennung kommt in
                      die Stand-Liste ``aufgeloest`` — Bilder, Gesichter und
                      Zuordnungen bleiben unveraendert, die Gesichter bleiben
                      der Person zugeordnet. Automatisch passiert das beim
                      Benennen mit (``name``/``gleich``), damit eine zugeordnete
                      Gruppe nicht als Gruppeneintrag stehen bleibt.
  ``rueckgaengig()`` nimmt die letzte Antwort zurueck (Fehltipp am Handy).

Ablage — genau die Formate, die ``personen_gruppieren.py`` liest
(``bestaetigt_lesen`` / ``vorgaben_lesen``), damit der naechste PC-Lauf die
Namen und Vorgaben uebernimmt:
  * ``personen_bestaetigt.json`` ``{"bestaetigt": {"Person_1003": "Name"}}``
  * ``personen_vorgaben.json``   ``{"gleich": [[a, b]], "verschieden": [[a, b]]}``
  * ``gruppen_quiz_stand.json``  ``{"spaeter": [...], "unbekannt": [...],
                                 "aufgeloest": [...]}``
  * ``gruppen_antworten.jsonl``  Protokoll, nur anhaengend (Grundlage fuer
                                 Rueckgaengig und Nachvollziehbarkeit).
Vor jedem Schreiben wird die alte Fassung als ``*.vorher`` gesichert; geschrieben
wird atomar (temp-Datei + ``os.replace``). Es wird nie etwas geloescht.

Register: ``bilder_mit(namen, modus)`` beantwortet „Bilder mit Leon und/oder
Tim" ueber ``gesicht_zuordnung.jsonl`` + die bestaetigten Namen — am Handy, ohne
Rueckweg zum PC.

Bild-Editor (B1, 26.10.2026): ``bild_korrekturen.json`` (nur Handy) haelt je Bild verschobene
Rahmen, Hand-Gesichter (Index >= 1000, vom Server vergeben), handy-eigene Namen und
entfernte Gesichter. ``gesichter_auf_bild``, ``bilder_mit``, ``bild_kennungen_person`` und
``personen_auf_bildern`` lesen dieselbe zusammengefuehrte Sicht (``_bild_sicht``);
``bild_rahmen`` schreibt sie (Protokollart ``bild_rahmen``, Rueckgaengig je ``aktion``).
In ``personen_vorgaben.json`` landet davon nur, was ``zuordnen``/``ausschliessen`` ohnehin schreiben.

Ort: ``~/foto_sortierung`` (uebersteuerbar mit ``GRUPPEN_QUIZ_BASIS``). Gelesen
wird zuerst ``personen_gruppen/<datei>`` (so schreibt der PC), sonst
``<datei>`` direkt im Ordner (so legt die Uebergabe am Handy sie ab).
Keine Vektoren, kein Netz, kein Modellaufruf — nur lokale Dateien.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import re
import threading
import unicodedata
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

ORDNER = "foto_sortierung"
UNTERORDNER = "personen_gruppen"
BEISPIELE_DATEINAME = "personen_beispiele.json"
ZUORDNUNG_DATEINAME = "gesicht_zuordnung.jsonl"
# Geschrieben von tools/foto_sortierung/video_standbilder.py (Frame -> Standbild in pCloud)
VIDEO_STANDBILDER_DATEINAME = "video_standbilder.jsonl"
BESTAETIGT_DATEINAME = "personen_bestaetigt.json"
VORGABEN_DATEINAME = "personen_vorgaben.json"
STAND_DATEINAME = "gruppen_quiz_stand.json"
PROTOKOLL_DATEINAME = "gruppen_antworten.jsonl"
PROFILE_DATEINAME = "personen_profile.json"
KONTAKTE_DATEINAME = "kontakte.json"   # Telefonbuch-Auszug (tools/handy/kontakte_aufs_handy.py)
# Handy-eigen (Bild-Editor B1, 26.10.2026): wird nie aus pCloud/PC uebernommen und nie hochgeladen
# (Sperrliste in tools/handy/pcloud_dateien_holen.py und tools/pcloud/uebergabe_hochladen.py).
KORREKTUREN_DATEINAME = "bild_korrekturen.json"
BILD_RAHMEN_MAX = 30       # Aenderungen je POST /api/gruppen/bild-rahmen
HAND_INDEX_AB = 1000       # Index >= 1000 = Hand-Gesicht (vergibt nur der Server)
BBOX_MIN = 0.01            # kleinster Rahmen: 1 % von Breite/Hoehe

ARTEN = ("name", "gleich", "verschieden", "spaeter", "unbekannt", "offen", "aufloesen")
# Stand-Listen in ``gruppen_quiz_stand.json``: ``aufgeloest`` = einer Person
# zugeordnete Gruppe, die nicht mehr als Gruppeneintrag in der Liste steht
# (To-do Punkt 14). Es wird nur die Mitgliedschaft vermerkt — nichts geloescht.
STAND_LISTEN = ("spaeter", "unbekannt", "aufgeloest")
MODI = ("alle", "eine", "genau")
NAME_MAX = 60
BEZIEHUNG_MAX = 80
NOTIZ_MAX = 4000
BEISPIELE_MAX = 8
BILDER_LIMIT_MAX = 500
SUCHE_LIMIT_MAX = 50
GESICHTER_JE_SEITE = 48
AUSSCHLUSS_MAX = 200
SPITZNAMEN_MAX = 10        # je Person, nur Anzeige/Suche (20.10.2026)
NAMENSFELD_MAX = 40        # Vorname / Nachname von Hand (20.10.2026)
SPITZNAME_MAX = 30         # ein einzelner Spitzname (20.10.2026)

FEHLT_HINWEIS = ("Die Gruppen-Datei fehlt hier. Am PC "
                 "tools/foto_sortierung/personen_gruppieren.py --schreiben laufen "
                 "lassen und die Dateien per Kabel übergeben (Download-Ordner; "
                 "die App übernimmt sie beim nächsten Start).")

_SCHREIBSPERRE = threading.Lock()
_CACHE: Dict[str, Tuple[Tuple[float, int], Any]] = {}
_PROJEKT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))


class GruppenFehler(Exception):
    """Fehler mit deutschem Text fuer die Oberflaeche."""


# ── Pfade ────────────────────────────────────────────────────────────────────

def basis() -> str:
    ueber = os.environ.get("GRUPPEN_QUIZ_BASIS")
    if ueber and ueber.strip():
        return ueber.strip()
    return os.path.join(os.path.expanduser("~"), ORDNER)


def _lesepfad(name: str) -> Optional[str]:
    """Erst ``personen_gruppen/<name>`` (PC), dann ``<name>`` (Uebergabe am Handy)."""
    for pfad in (os.path.join(basis(), UNTERORDNER, name), os.path.join(basis(), name)):
        if os.path.isfile(pfad):
            return pfad
    return None


def _schreibpfad(name: str) -> str:
    return os.path.join(basis(), name)


def _im_projekt(pfad: str) -> bool:
    try:
        return os.path.commonpath([os.path.realpath(pfad), os.path.realpath(_PROJEKT)]) \
            == os.path.realpath(_PROJEKT)
    except ValueError:      # anderes Laufwerk (Windows)
        return False


# ── Lesen ────────────────────────────────────────────────────────────────────

def _json_lesen(pfad: Optional[str], standard: Any) -> Any:
    if not pfad or not os.path.isfile(pfad):
        return standard
    try:
        with open(pfad, encoding="utf-8") as datei:
            return json.load(datei)
    except (OSError, ValueError) as problem:
        raise GruppenFehler(f"Datei nicht lesbar ({problem.__class__.__name__}): "
                            f"{os.path.basename(pfad)}") from None


def _gemerkt(pfad: str, laden):
    """Ergebnis von ``laden(pfad)`` merken, solange sich Datei-Zeit und -Groesse nicht aendern.

    Gemerkt wird je (Pfad, Lesefunktion): ``gesicht_zuordnung.jsonl`` lesen zwei
    verschiedene Funktionen (Register und Gesichterliste). Mit dem Pfad allein
    bekam die zweite das Ergebnis der ersten (Befund 02.10.2026 im Test).
    """
    try:
        st = os.stat(pfad)
    except OSError:
        return laden(pfad)
    schluessel = (st.st_mtime, st.st_size)
    eintrag = f"{pfad}|{getattr(laden, '__qualname__', id(laden))}"
    alt = _CACHE.get(eintrag)
    if alt and alt[0] == schluessel:
        return alt[1]
    wert = laden(pfad)
    _CACHE[eintrag] = (schluessel, wert)
    return wert


def _gruppen_laden() -> Tuple[List[Dict[str, Any]], str]:
    pfad = _lesepfad(BEISPIELE_DATEINAME)
    if not pfad:
        raise GruppenFehler(FEHLT_HINWEIS)

    def laden(p):
        daten = _json_lesen(p, {})
        gruppen = daten.get("gruppen") if isinstance(daten, dict) else None
        if not isinstance(gruppen, list):
            raise GruppenFehler("personen_beispiele.json hat keine Gruppenliste.")
        sauber = [g for g in gruppen
                  if isinstance(g, dict) and isinstance(g.get("kennung"), str) and g["kennung"]]
        sauber.sort(key=lambda g: (-int(g.get("groesse") or 0), g["kennung"]))
        return sauber, str(daten.get("stand") or "")

    return _gemerkt(pfad, laden)


def bestaetigt_lesen() -> Dict[str, str]:
    daten = _json_lesen(_schreibpfad(BESTAETIGT_DATEINAME), {})
    roh = daten.get("bestaetigt") if isinstance(daten, dict) else None
    if not isinstance(roh, dict):
        return {}
    return {str(k): v.strip() for k, v in roh.items() if isinstance(v, str) and v.strip()}


def vorgaben_lesen() -> Dict[str, List[List[str]]]:
    daten = _json_lesen(_schreibpfad(VORGABEN_DATEINAME), {})
    ergebnis: Dict[str, List[List[str]]] = {"gleich": [], "verschieden": []}
    if isinstance(daten, dict):
        for art in ergebnis:
            for paar in daten.get(art) or []:
                if (isinstance(paar, (list, tuple)) and len(paar) == 2
                        and all(isinstance(x, str) and x for x in paar) and paar[0] != paar[1]):
                    sortiert = sorted(paar)
                    if sortiert not in ergebnis[art]:
                        ergebnis[art].append(sortiert)
    return ergebnis


def _stand_lesen() -> Dict[str, List[str]]:
    daten = _json_lesen(_schreibpfad(STAND_DATEINAME), {})
    stand: Dict[str, List[str]] = {liste: [] for liste in STAND_LISTEN}
    if isinstance(daten, dict):
        for liste in stand:
            stand[liste] = [k for k in daten.get(liste) or [] if isinstance(k, str) and k]
    return stand


# ── Schreiben ────────────────────────────────────────────────────────────────

def _atomar_schreiben(name: str, inhalt: Any) -> None:
    pfad = _schreibpfad(name)
    if _im_projekt(pfad):
        raise GruppenFehler("Schreibziel liegt im Projektordner – abgelehnt "
                            "(persönliche Daten gehören nicht ins Repo).")
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    if os.path.isfile(pfad):
        with open(pfad, "rb") as alt, open(pfad + ".vorher", "wb") as sicherung:
            sicherung.write(alt.read())
    temp = pfad + ".tmp"
    with open(temp, "w", encoding="utf-8", newline="\n") as datei:
        json.dump(inhalt, datei, ensure_ascii=False, indent=1)
        datei.write("\n")
    os.replace(temp, pfad)


def _bestaetigt_schreiben(namen: Dict[str, str]) -> None:
    roh = _json_lesen(_schreibpfad(BESTAETIGT_DATEINAME), {})
    daten = roh if isinstance(roh, dict) else {}
    daten["bestaetigt"] = dict(sorted(namen.items()))
    _atomar_schreiben(BESTAETIGT_DATEINAME, daten)


def _vorgaben_schreiben(vorgaben: Dict[str, List[List[str]]]) -> None:
    roh = _json_lesen(_schreibpfad(VORGABEN_DATEINAME), {})
    daten = roh if isinstance(roh, dict) else {}
    daten["gleich"] = sorted(vorgaben["gleich"])
    daten["verschieden"] = sorted(vorgaben["verschieden"])
    _atomar_schreiben(VORGABEN_DATEINAME, daten)


def _protokoll_lesen() -> List[Dict[str, Any]]:
    pfad = _schreibpfad(PROTOKOLL_DATEINAME)
    eintraege: List[Dict[str, Any]] = []
    if not os.path.isfile(pfad):
        return eintraege
    with open(pfad, encoding="utf-8") as datei:
        for zeile in datei:
            try:
                e = json.loads(zeile)
            except ValueError:
                continue
            if isinstance(e, dict):
                eintraege.append(e)
    return eintraege


def _protokoll_anhaengen(eintrag: Dict[str, Any]) -> None:
    pfad = _schreibpfad(PROTOKOLL_DATEINAME)
    if _im_projekt(pfad):
        raise GruppenFehler("Schreibziel liegt im Projektordner – abgelehnt.")
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad, "a", encoding="utf-8", newline="\n") as datei:
        datei.write(json.dumps(eintrag, ensure_ascii=False) + "\n")
        datei.flush()
        os.fsync(datei.fileno())


# ── Reine Hilfen ─────────────────────────────────────────────────────────────

def name_saeubern(name: Any) -> str:
    """Leerraum zusammenziehen, Steuerzeichen weg; leer oder zu lang -> Fehler."""
    if not isinstance(name, str):
        raise GruppenFehler("Bitte einen Namen eingeben.")
    sauber = re.sub(r"[\x00-\x1f\x7f]", "", name)
    sauber = re.sub(r"\s+", " ", sauber).strip()
    if not sauber:
        raise GruppenFehler("Bitte einen Namen eingeben.")
    if len(sauber) > NAME_MAX:
        raise GruppenFehler(f"Name zu lang (höchstens {NAME_MAX} Zeichen).")
    return sauber


def _paar(a: str, b: str) -> List[str]:
    return sorted([a, b])


def _gleich_komponente(start: str, gleich: Iterable[Iterable[str]]) -> List[str]:
    """Alle Gruppen, die ueber ``gleich``-Paare (auch mehrstufig) mit ``start``
    verbunden sind — ohne ``start`` selbst, sortiert."""
    nachbarn: Dict[str, set] = {}
    for p in gleich:
        p = list(p)
        if len(p) != 2:
            continue
        a, b = str(p[0]), str(p[1])
        nachbarn.setdefault(a, set()).add(b)
        nachbarn.setdefault(b, set()).add(a)
    gesehen, offen = {start}, [start]
    while offen:
        for n in nachbarn.get(offen.pop(), ()):
            if n not in gesehen:
                gesehen.add(n)
                offen.append(n)
    gesehen.discard(start)
    return sorted(gesehen)


def _beispiel_fuer_anzeige(b: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Nur Fotos mit gueltiger Kennung und Rahmen; Videos haben kein Vorschaubild."""
    fileid = str(b.get("bild_id") or "")
    bbox = b.get("bbox")
    if not fileid.isdigit() or not (isinstance(bbox, list) and len(bbox) == 4):
        return None
    return {"fileid": fileid, "index": b.get("index"), "bbox": bbox,
            "breite": b.get("breite"), "hoehe": b.get("hoehe"),
            "aufnahme": (b.get("aufnahme") or "")[:10] or None}


def namen_liste(namen: Dict[str, str]) -> List[str]:
    """Alle bestaetigten Namen, eindeutig (ohne Gross/Klein), alphabetisch."""
    gesehen: Dict[str, str] = {}
    for n in namen.values():
        gesehen.setdefault(n.casefold(), n)
    return sorted(gesehen.values(), key=str.casefold)


# ── Namensfelder: Vorname / Nachname aus dem Namen ableiten (20.10.2026) ────
#
# Wunsch Sebastian (20.10.2026): Personenbuch mit Vorname / Nachname /
# Spitznamen. Der NAME bleibt die Kennung (keine Umbenennung, keine Migration);
# die Felder werden beim LESEN abgeleitet — dabei wird NICHTS geschrieben — und
# von Hand gesetzte Felder im Profil haben Vorrang. Die Ableitung ist eine reine
# Funktion (keine Datei, kein Netz, kein Wurf).

# Namenszusaetze: alles ab dem ersten davon gehoert zum Nachnamen.
NAMENS_ZUSAETZE = frozenset({
    "von", "van", "de", "del", "della", "den", "der", "des", "di", "da", "dos",
    "das", "la", "le", "ten", "ter", "zu", "zur", "zum", "am", "im", "in",
    "of", "mac", "mc", "bin", "bint", "ben", "ap", "o",
})

# Anreden/Rollen: kein Vorname und kein Nachname (Zusatz), solange das
# Familiensignal nicht dagegen spricht.
NAMENS_ROLLEN = frozenset({
    "oma", "opa", "onkel", "tante", "papa", "mama", "vati", "muti", "vater",
    "mutter", "bruder", "schwester", "cousin", "cousine", "neffe", "nichte",
    "enkel", "enkelin", "schwager", "schwaegerin", "kollege", "kollegin",
    "chef", "chefin", "freund", "freundin", "kumpel", "nachbar", "nachbarin",
    "mitarbeiter", "mitarbeiterin", "kind", "sohn", "tochter", "patenonkel",
    "patentante", "schatz",
})

_ZIFFERN_ENDE = re.compile(r"\d+$")
_KUERZEL_ENDE = re.compile(r"^[A-ZÄÖÜ]\.[a-zäöü]?$")
_KLAMMER_ENDE = re.compile(r"\s*\(([^()]*)\)\s*$")


def _namens_wort(wort: str) -> str:
    """Wort ohne Ziffern und Randzeichen, klein — nur zum Vergleichen."""
    if not isinstance(wort, str):
        return ""
    return re.sub(r"\d+$", "", wort).strip(" .,'-’").casefold()


def _namens_teile(name: str) -> List[str]:
    """Woerter eines Namens ohne Klammerzusatz (der ist kein Nachname)."""
    return [w for w in re.split(r"\s+", _KLAMMER_ENDE.sub("", name).strip()) if w]


def familienwoerter(alle_namen: Iterable[Any], ohne: str = "") -> set:
    """Letzte Woerter mehrteiliger Namen im Bestand = vermutete Nachnamen.

    Dieselbe Naherung wie ``websuche_schutz.bestand_bauen`` (dort ab Zeile 93),
    hier fuer die Anzeige. ``ohne`` laesst einen Namen aus, damit er sich nicht
    selbst stuetzt. Wirft nie.
    """
    menge = set()
    for n in alle_namen or ():
        if not isinstance(n, str) or (ohne and n.casefold() == ohne.casefold()):
            continue
        teile = _namens_teile(n)
        if len(teile) >= 2:
            wort = _namens_wort(teile[-1])
            if len(wort) >= 2:
                menge.add(wort)
    return menge


def name_zerlegen(name: Any, alle_namen: Iterable[Any] = ()) -> Dict[str, str]:
    """Vorname/Nachname aus einem Namen ableiten (reine Funktion, wirft nie).

    Reihenfolge der Regeln (Sebastian 20.10.2026: „automatisch trennen, wenn
    Nachname vorhanden\"); die erste passende gewinnt:

    1. Ein Namenszusatz (von, van, den, de la …) macht alles ab dort zum
       Nachnamen („Jan van den Berg\"). Steht er am Ende, gibt es keinen.
    2. Ein Kuerzel am Ende („M.\") ist der Nachname; am Anfang ist dasselbe
       Kuerzel ein Vorname-Kuerzel („M. Beispiel\").
    3. Ein Rollenwort am Anfang (Oma, Kollege …) oder Ziffern am Ende des
       letzten Wortes sind KEIN Nachname — es sei denn, genau dieses Wort steht
       bei einer anderen mehrteiligen Person auch am Ende (Familiensignal).
    4. Sonst ist das letzte Wort bei mindestens zwei Woertern der Nachname; ein
       einzelnes Wort ist der Vorname (bzw. Nachname, wenn das Familiensignal
       ihn stuetzt).

    Ohne Nachname bleibt der ganze Name (samt Klammerzusatz) im Feld
    ``vorname`` — es wird nichts behauptet, was der Name nicht hergibt.
    """
    try:
        vollname = name_saeubern(name)
    except GruppenFehler:
        return {"vorname": "", "nachname": ""}
    woerter = _namens_teile(vollname)
    if not woerter:
        return {"vorname": "", "nachname": ""}
    familien = familienwoerter(alle_namen, ohne=name if isinstance(name, str) else "")
    letztes = _namens_wort(woerter[-1])
    stuetzt = bool(letztes) and letztes in familien
    for i, wort in enumerate(woerter):                     # Regel 1
        if _namens_wort(wort) not in NAMENS_ZUSAETZE:
            continue
        if i == 0:
            return {"vorname": "", "nachname": " ".join(woerter)}
        if i < len(woerter) - 1:
            return {"vorname": " ".join(woerter[:i]), "nachname": " ".join(woerter[i:])}
        return {"vorname": vollname, "nachname": ""}        # Zusatz steht am Ende
    if len(woerter) >= 2 and _KUERZEL_ENDE.match(woerter[-1]):    # Regel 2
        return {"vorname": " ".join(woerter[:-1]), "nachname": woerter[-1]}
    blockiert = (bool(_ZIFFERN_ENDE.search(woerter[-1]))
                 or _namens_wort(woerter[0]) in NAMENS_ROLLEN)
    if len(woerter) == 1:                                  # Regel 3/4
        if stuetzt and _namens_wort(woerter[0]) not in NAMENS_ROLLEN:
            return {"vorname": "", "nachname": woerter[0]}
        return {"vorname": vollname, "nachname": ""}
    if blockiert and not stuetzt:
        return {"vorname": vollname, "nachname": ""}
    return {"vorname": " ".join(woerter[:-1]), "nachname": woerter[-1]}


# ── Profile: Beziehung + Erinnerungen je Person (01.10.2026) ────────────────
#
# Wunsch Sebastian: beim Benennen gleich ein Profil anlegen und zur Person
# etwas reinsprechen (Situationen, Erinnerungen). ``personen_profile.json``:
# {"profile": {"Leon": {"beziehung": "Schulfreund",
#                       "notizen": [{"id", "zeit", "text", "kennung", "quelle"}]}}}
# Notizen werden nur angehaengt; Rueckgaengig markiert eine Notiz als
# ``zurueckgenommen`` statt sie zu loeschen.

def text_saeubern(text: Any, laenge: int, zeilen: bool = False) -> str:
    """Steuerzeichen weg (Zeilenumbrueche nur, wenn erlaubt), getrimmt, Laenge geprueft."""
    if text is None:
        return ""
    if not isinstance(text, str):
        raise GruppenFehler("Ungültige Eingabe.")
    if zeilen:
        sauber = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text.replace("\r\n", "\n"))
        sauber = re.sub(r"\n{3,}", "\n\n", sauber).strip()
    else:
        sauber = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", text)).strip()
    if len(sauber) > laenge:
        raise GruppenFehler(f"Text zu lang (höchstens {laenge} Zeichen).")
    return sauber


def _profile_laden() -> Dict[str, Any]:
    daten = _json_lesen(_schreibpfad(PROFILE_DATEINAME), {})
    if not isinstance(daten, dict):
        daten = {}
    if not isinstance(daten.get("profile"), dict):
        daten["profile"] = {}
    return daten


def _profil_schluessel(profile: Dict[str, Any], name: str) -> str:
    """Vorhandene Schreibweise wiederverwenden (Gross/Klein egal), sonst der neue Name."""
    return next((k for k in profile if k.casefold() == name.casefold()), name)


def namensfelder_saeubern(vorname: Any = None, nachname: Any = None,
                          spitznamen: Any = None) -> Dict[str, Any]:
    """Von Hand gesetzte Namensfelder pruefen (20.10.2026, Namensfelder Schritt 2).

    Nur die uebergebenen Felder kommen zurueck (``None`` = nicht angefasst).
    Eine **leere** Eingabe bedeutet „Felder leeren": das Handfeld wird entfernt
    und die Ableitung greift wieder. Spitznamen duerfen als Liste oder als
    komma-getrennter Text kommen, doppelte fallen weg (Gross/Klein egal).
    Wirft ``GruppenFehler`` bei unbrauchbarer Eingabe — es wird nie etwas
    geschrieben, die Pruefung laeuft vor dem Schreiben.
    """
    felder: Dict[str, Any] = {}
    if vorname is not None:
        felder["vorname"] = text_saeubern(vorname, NAMENSFELD_MAX)
    if nachname is not None:
        felder["nachname"] = text_saeubern(nachname, NAMENSFELD_MAX)
    if spitznamen is not None:
        roh = ([t for t in spitznamen.split(",")] if isinstance(spitznamen, str)
               else list(spitznamen) if isinstance(spitznamen, (list, tuple)) else None)
        if roh is None:
            raise GruppenFehler("Spitznamen bitte als Liste oder mit Komma getrennt.")
        sauber: List[str] = []
        gesehen = set()
        for s in roh:
            if not isinstance(s, str):
                raise GruppenFehler("Ungültige Eingabe.")
            wert = text_saeubern(s, SPITZNAME_MAX)
            if not wert or wert.casefold() in gesehen:
                continue
            gesehen.add(wert.casefold())
            sauber.append(wert)
        if len(sauber) > SPITZNAMEN_MAX:
            raise GruppenFehler(f"Höchstens {SPITZNAMEN_MAX} Spitznamen je Person.")
        felder["spitznamen"] = sauber
    return felder


def _namensfelder(eintrag: Any, name: str, alle_namen: Iterable[Any] = ()) -> Dict[str, Any]:
    """Vorname / Nachname / Spitznamen einer Person fuer Anzeige und Suche.

    Von Hand im Profil gesetzte Felder haben Vorrang; fehlen sie, werden sie aus
    dem Namen ABGELEITET (siehe ``name_zerlegen``). Es wird dabei NICHTS
    geschrieben, und der Name bleibt unveraendert die Kennung. Wirft nie.
    """
    eintrag = eintrag if isinstance(eintrag, dict) else {}
    abgeleitet = name_zerlegen(name, alle_namen)
    gesetzt_vorname = eintrag.get("vorname")
    gesetzt_nachname = eintrag.get("nachname")
    vorname = str(gesetzt_vorname).strip() if isinstance(gesetzt_vorname, str) else ""
    nachname = str(gesetzt_nachname).strip() if isinstance(gesetzt_nachname, str) else ""
    roh = eintrag.get("spitznamen")
    spitznamen = []
    if isinstance(roh, list):
        for s in roh:
            if isinstance(s, str) and s.strip():
                spitznamen.append(s.strip())
            if len(spitznamen) >= SPITZNAMEN_MAX:
                break
    return {"vorname": vorname or abgeleitet["vorname"],
            "nachname": nachname or abgeleitet["nachname"],
            "spitznamen": spitznamen,
            "namensfelder_quelle": "profil" if (vorname or nachname) else "abgeleitet"}


def _profil_ergaenzen(daten: Dict[str, Any], name: str, beziehung: str, notiz: str,
                      kennung: Optional[str], quelle: str,
                      kontakt: Optional[Dict[str, Any]] = None,
                      felder: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    profile = daten["profile"]
    schluessel = _profil_schluessel(profile, name)
    eintrag = profile.setdefault(schluessel, {"beziehung": "", "notizen": []})
    eintrag.setdefault("notizen", [])
    aenderung: Dict[str, Any] = {"name": schluessel, "notiz_id": None}
    if beziehung and beziehung != eintrag.get("beziehung"):
        aenderung["beziehung_vorher"] = eintrag.get("beziehung") or ""
        eintrag["beziehung"] = beziehung
    if kontakt and kontakt != eintrag.get("kontakt"):
        aenderung["kontakt_vorher"] = eintrag.get("kontakt")
        eintrag["kontakt"] = kontakt
    # Namensfelder von Hand (20.10.2026): leer = Handfeld weg, Ableitung greift wieder.
    # Vorher-Stand wird je Feld mitgeschrieben, damit Rueckgaengig genau zurueckstellt.
    for feld, wert in (felder or {}).items():
        if eintrag.get(feld) == wert:
            continue
        aenderung.setdefault("felder_vorher", {})[feld] = eintrag.get(feld)
        if wert in ("", []):
            eintrag.pop(feld, None)
        else:
            eintrag[feld] = wert
    if notiz:
        nid = uuid.uuid4().hex[:12]
        eintrag["notizen"].append({"id": nid, "zeit": datetime.now().isoformat(timespec="seconds"),
                                   "text": notiz, "kennung": kennung, "quelle": quelle})
        aenderung["notiz_id"] = nid
    return aenderung


def profil(name: str) -> Dict[str, Any]:
    """Profil einer Person (ohne zurueckgenommene Notizen). Nie ein Wurf."""
    try:
        sauber = name_saeubern(name)
        daten = _profile_laden()
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    schluessel = _profil_schluessel(daten["profile"], sauber)
    p = daten["profile"].get(schluessel) or {}
    notizen = [n for n in p.get("notizen") or [] if not n.get("zurueckgenommen")]
    try:
        weitere = list(bestaetigt_lesen().values())
    except GruppenFehler:
        weitere = []
    return {"ok": True, "name": schluessel, "beziehung": p.get("beziehung") or "",
            "notizen": notizen, "kontakt": p.get("kontakt"),
            **_namensfelder(p, schluessel, weitere)}


def profil_ergaenzen(name: str, beziehung: Optional[str] = None, notiz: Optional[str] = None,
                     kennung: Optional[str] = None,
                     kontakt_id: Optional[str] = None,
                     vorname: Optional[str] = None, nachname: Optional[str] = None,
                     spitznamen: Optional[Any] = None) -> Dict[str, Any]:
    """Beziehung setzen, Erinnerung anhaengen, Kontakt verknuepfen und/oder die
    Namensfelder von Hand setzen (auch ohne Quiz, z. B. aus „Benannt"). Steht im
    Protokoll, Rueckgaengig nimmt es zurueck. Nie ein Wurf."""
    try:
        sauber = name_saeubern(name)
        b = text_saeubern(beziehung, BEZIEHUNG_MAX)
        n = text_saeubern(notiz, NOTIZ_MAX, zeilen=True)
        kontakt = None
        if kontakt_id:
            kontakt = _kontakte_laden().get(str(kontakt_id).strip())
            if not kontakt:
                raise GruppenFehler("Kontakt nicht (mehr) im Telefonbuch-Auszug.")
        felder = namensfelder_saeubern(vorname, nachname, spitznamen)
        if not b and not n and not kontakt and not felder:
            raise GruppenFehler("Bitte eine Beziehung, eine Erinnerung oder einen Namen eingeben.")
        with _SCHREIBSPERRE:
            daten = _profile_laden()
            aenderung = _profil_ergaenzen(daten, sauber, b, n, kennung, "profil",
                                          dict(kontakt) if kontakt else None, felder)
            _atomar_schreiben(PROFILE_DATEINAME, daten)
            _protokoll_anhaengen({"id": uuid.uuid4().hex[:12],
                                  "zeit": datetime.now().isoformat(timespec="seconds"),
                                  "art": "profil", "kennung": kennung or "", "profil": aenderung})
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    except OSError as fehler:
        logger.error("Profil: Schreiben fehlgeschlagen: %s", fehler)
        return {"ok": False, "fehler": f"Speichern fehlgeschlagen ({fehler.__class__.__name__})."}
    return profil(sauber)


# ── Kontakte + Suche (02.10.2026, Issue #3 Teil A/B) ─────────────────────────
#
# Ein Personenbestand: Quelle der Kontakte bleibt das Telefonbuch (mit Google
# abgeglichen); ``kontakte.json`` ist nur ein Auszug, das Profil verweist per
# Kennung (Android ``contact_id``) darauf und haelt eine Kopie fuer die Anzeige.
# Die Suche laeuft rein lokal (kein Sprachmodell, keine Kosten).

def _kontakte_laden() -> Dict[str, Dict[str, Any]]:
    pfad = _lesepfad(KONTAKTE_DATEINAME)
    if not pfad:
        return {}

    def laden(p):
        daten = _json_lesen(p, {})
        liste = daten.get("kontakte") if isinstance(daten, dict) else None
        ergebnis: Dict[str, Dict[str, Any]] = {}
        for k in liste if isinstance(liste, list) else []:
            if not isinstance(k, dict):
                continue
            kid, name = str(k.get("id") or "").strip(), str(k.get("name") or "").strip()
            if not kid or not name:
                continue
            gb = k.get("geburtstag")
            ergebnis[kid] = {"id": kid, "name": name,
                             "nummern": [str(n) for n in (k.get("nummern") or [])
                                         if isinstance(n, (str, int))][:10],
                             "geburtstag": gb if isinstance(gb, str) and gb else None}
        return ergebnis

    return _gemerkt(pfad, laden)


_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _suchformen(text: str) -> List[str]:
    """Zwei Schreibweisen: Umlaut ausgeschrieben (mueller) und ohne Zeichen (muller)."""
    klein = (text or "").casefold()
    ohne = "".join(c for c in unicodedata.normalize("NFKD", klein)
                   if not unicodedata.combining(c)).replace("ß", "ss")
    return [klein.translate(_UMLAUTE), ohne]


def passt_wortanfang(name: str, frage: str) -> bool:
    """Jedes Suchwort ist der Anfang eines Wortes im Namen (Gross/Klein, Umlaute egal)."""
    teile = [t for t in re.split(r"[\s\-]+", (frage or "").strip()) if t]
    if not teile:
        return False
    namen_woerter = [w for form in _suchformen(name) for w in re.split(r"[\s\-]+", form) if w]
    return all(any(w.startswith(tf) for w in namen_woerter for tf in _suchformen(t) if tf)
               for t in teile)


def suche(q: str, limit: int = 12) -> Dict[str, Any]:
    """Suchfeld im Quiz: zuerst schon benannte Personen, dann Telefonbuch-Kontakte. Nie ein Wurf."""
    try:
        namen = bestaetigt_lesen()
        kontakte = _kontakte_laden()
        profile = _profile_laden()["profile"]
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    limit = max(1, min(int(limit or 12), SUCHE_LIMIT_MAX))
    frage = (q or "").strip()
    alle = namen_liste(namen)

    def durchsuchbar(n: str) -> str:
        """Name plus die Namensfelder — damit findet die Suche auch Vorname,
        Nachname und Spitznamen, nicht nur den Namen selbst (20.10.2026)."""
        p = profile.get(_profil_schluessel(profile, n)) or {}
        f = _namensfelder(p, n)
        return " ".join([n, f["vorname"], f["nachname"], *f["spitznamen"]])

    if frage:
        personen = [n for n in alle if passt_wortanfang(durchsuchbar(n), frage)][:limit]
        treffer = sorted((k for k in kontakte.values() if passt_wortanfang(k["name"], frage)),
                         key=lambda k: (k["name"].casefold(), k["id"]))[:limit]
    else:
        personen, treffer = alle[:limit], []
    verknuepft = {str((p.get("kontakt") or {}).get("id")): n for n, p in profile.items()
                  if isinstance(p, dict) and (p.get("kontakt") or {}).get("id")}

    def person(n: str) -> Dict[str, Any]:
        p = profile.get(_profil_schluessel(profile, n)) or {}
        return {"name": n, "beziehung": p.get("beziehung") or "", "kontakt": bool(p.get("kontakt")),
                **_namensfelder(p, n)}

    return {"ok": True, "frage": frage, "kontakte_vorhanden": bool(kontakte),
            "personen": [person(n) for n in personen],
            "kontakte": [{"id": k["id"], "name": k["name"], "geburtstag": k["geburtstag"],
                          "nummern": len(k["nummern"]), "verknuepft_mit": verknuepft.get(k["id"])}
                         for k in treffer]}


# ── Abfragen ─────────────────────────────────────────────────────────────────

def stand() -> Dict[str, Any]:
    """Ueberblick: wie viele Gruppen, wie viele benannt/offen. Nie ein Wurf."""
    try:
        gruppen, zeitstempel = _gruppen_laden()
        namen = bestaetigt_lesen()
        st = _stand_lesen()
    except GruppenFehler as fehler:
        return {"ok": False, "vorhanden": False, "fehler": str(fehler)}
    kennungen = {g["kennung"] for g in gruppen}
    aufgeloest = {k for k in kennungen if k in set(st["aufgeloest"])}
    benannt = sum(1 for k in kennungen if k in namen)
    unbekannt = sum(1 for k in kennungen if k in set(st["unbekannt"]) and k not in namen)
    spaeter = sum(1 for k in kennungen if k in set(st["spaeter"]) and k not in namen)
    gesichter_benannt = sum(int(g.get("groesse") or 0) for g in gruppen if g["kennung"] in namen)
    return {
        "ok": True, "vorhanden": True, "stand": zeitstempel,
        "gruppen": len(gruppen), "benannt": benannt, "unbekannt": unbekannt,
        "spaeter": spaeter, "offen": len(gruppen) - benannt - unbekannt,
        # Untermenge von „benannt": zugeordnete Gruppen, die nicht mehr als
        # Gruppeneintrag in der Liste stehen (To-do Punkt 14). „benannt" bleibt
        # die volle Zahl — die Person behaelt ihre Gesichter.
        "aufgeloest": len(aufgeloest),
        "gesichter": sum(int(g.get("groesse") or 0) for g in gruppen),
        "gesichter_benannt": gesichter_benannt,
        "namen": namen_liste(namen),
    }


def _gruppen_status(kennung: str, namen: Dict[str, str], st: Dict[str, List[str]]) -> str:
    if kennung in st["aufgeloest"]:
        return "aufgeloest"
    if kennung in namen:
        return "benannt"
    if kennung in st["unbekannt"]:
        return "ausgeblendet"
    if kennung in st["spaeter"]:
        return "spaeter"
    return "offen"


def liste(status: str = "offen", seite: int = 1, je_seite: int = 24) -> Dict[str, Any]:
    """Metadatenliste aus personen_beispiele.json, ohne Gesichtsdateien zu lesen."""
    if (status not in ("offen", "spaeter", "benannt", "ausgeblendet", "aufgeloest")
            or isinstance(seite, bool) or not isinstance(seite, int) or not 1 <= seite <= 10000
            or isinstance(je_seite, bool) or not isinstance(je_seite, int) or not 1 <= je_seite <= 100):
        return {"ok": False, "fehler": "Ungültige Listenparameter."}
    try:
        gruppen, _ = _gruppen_laden()
        namen = bestaetigt_lesen()
        st = _stand_lesen()
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    passend = [g for g in gruppen if _gruppen_status(g["kennung"], namen, st) == status]
    passend.sort(key=lambda g: (-int(g.get("groesse") or 0), g["kennung"]))
    gesamt = len(passend)
    seiten = (gesamt + je_seite - 1) // je_seite
    start = (seite - 1) * je_seite
    sichtbare = [{
        "kennung": g["kennung"], "groesse": g.get("groesse") or 0,
        "bilder": g.get("bilder"), "videos": g.get("videos"),
        "von": g.get("von"), "bis": g.get("bis"), "status": status,
        "name": namen.get(g["kennung"]),
    } for g in passend[start:start + je_seite]]
    return {"ok": True, "status": status, "gruppen": sichtbare, "gesamt": gesamt,
            "seite": seite, "seiten": seiten, "je_seite": je_seite}


def _antwort_fuer_gruppe(gruppe: Dict[str, Any], gruppen: List[Dict[str, Any]],
                         namen: Dict[str, str], vorgaben: Dict[str, List[List[str]]],
                         spaeter: List[str], offen: int,
                         status: Optional[str] = None) -> Dict[str, Any]:
    """Gemeinsame Beispielaufbereitung für `/naechste` und direktes Detail."""
    nach_kennung = {g["kennung"]: g for g in gruppen}

    def erstes_beispiel(g: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        foto = next((b for b in (_beispiel_fuer_anzeige(x)
                                 for x in g.get("beispiele") or []) if b), None)
        if foto:
            return foto
        # Ohne Foto-Beispiel das beste Video-Gesicht (14.10.2026, Video-Gesichter im Quiz).
        video = _video_beispiele(g["kennung"], set(), set(), 1)
        return video[0] if video else None

    # Schon entschiedene Paare (gleich ODER verschieden) nicht noch einmal
    # fragen — sonst zeichnet die Oberflaeche nach dem Klick dieselbe Frage
    # neu, und es sieht aus, als waere nichts passiert (Befund 01.10.2026).
    entschieden = {tuple(p) for art_paar in ("gleich", "verschieden")
                   for p in vorgaben[art_paar]}
    zwillinge = []
    for z in gruppe.get("zwilling_kandidaten") or []:
        if not isinstance(z, dict) or z.get("kennung") not in nach_kennung:
            continue
        if tuple(_paar(gruppe["kennung"], z["kennung"])) in entschieden:
            continue
        andere = nach_kennung[z["kennung"]]
        zwillinge.append({"kennung": z["kennung"], "name": namen.get(z["kennung"]),
                          "aehnlich": z.get("aehnlich"),
                          "gemeinsame_bilder": z.get("gemeinsame_bilder"),
                          "groesse": andere.get("groesse"), "beispiel": erstes_beispiel(andere)})
    # Per „= dieselbe Person" verbundene, noch unbenannte Vorschlaege: Sie
    # bekommen beim Benennen denselben Namen und werden hier mit angezeigt.
    verbunden = []
    for k in _gleich_komponente(gruppe["kennung"], vorgaben["gleich"]):
        if k in nach_kennung and not namen.get(k):
            verbunden.append({"kennung": k, "groesse": nach_kennung[k].get("groesse"),
                              "beispiel": erstes_beispiel(nach_kennung[k])})
    aus = ausgeschlossen_lesen().get(gruppe["kennung"], set())
    beispiele = [b for b in (_beispiel_fuer_anzeige(x) for x in gruppe.get("beispiele") or [])
                 if b and f"{b['fileid']}:{int(b.get('index') or 0)}" not in aus][:BEISPIELE_MAX]
    # Weniger als BEISPIELE_MAX Foto-Beispiele: mit den besten Video-Gesichtern auffuellen.
    beispiele += _video_beispiele(gruppe["kennung"], aus, {b["fileid"] for b in beispiele},
                                  BEISPIELE_MAX - len(beispiele))
    # Videos im Kopf wie im Raster von gesichter(): nur Video-Gesichter OHNE Standbild —
    # die mit Standbild stehen schon unter den Beispielen. Ohne Gesichtsdatei der alte Wert.
    videos = gruppe.get("videos")
    try:
        _, ohne_standbild = _video_teil([gruppe["kennung"]])
    except (GruppenFehler, OSError):
        ohne_standbild = {}
    if gruppe["kennung"] in ohne_standbild:
        videos = ohne_standbild[gruppe["kennung"]]
    ergebnis = {
        "ok": True, "fertig": False, "offen": offen,
        "gruppe": {
            "kennung": gruppe["kennung"], "groesse": gruppe.get("groesse"),
            "bilder": gruppe.get("bilder"), "videos": videos,
            "von": gruppe.get("von"), "bis": gruppe.get("bis"),
            "war_spaeter": gruppe["kennung"] in spaeter,
            "beispiele": beispiele[:BEISPIELE_MAX], "zwillinge": zwillinge,
            "verbunden": verbunden,
        },
        "namen": namen_liste(namen),
    }
    if not namen.get(gruppe["kennung"]):
        from app.services import lebensabschnitte_service
        v_abschnitt = lebensabschnitte_service.vorschlag_fuer_offene_gruppe(gruppe)
        if v_abschnitt:
            ergebnis["gruppe"]["lebensabschnitt_vorschlag"] = v_abschnitt
    if status is not None:
        ergebnis["gruppe"]["status"] = status
        ergebnis["gruppe"]["name"] = namen.get(gruppe["kennung"])
    return ergebnis


def naechste() -> Dict[str, Any]:
    """Die groesste offene Gruppe (unbenannt, nicht 'unbekannt'); 'spaeter' erst zum Schluss."""
    try:
        gruppen, _ = _gruppen_laden()
        namen = bestaetigt_lesen()
        vorgaben = vorgaben_lesen()
        st = _stand_lesen()
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    unbekannt, spaeter = set(st["unbekannt"]), st["spaeter"]
    offen = [g for g in gruppen if g["kennung"] not in namen and g["kennung"] not in unbekannt]
    erst = [g for g in offen if g["kennung"] not in spaeter]
    if erst:
        gruppe = erst[0]
    else:
        reihe = {k: i for i, k in enumerate(spaeter)}
        nach_spaeter = sorted(offen, key=lambda g: reihe.get(g["kennung"], 0))
        gruppe = nach_spaeter[0] if nach_spaeter else None
    if gruppe is None:
        return {"ok": True, "fertig": True, "gruppe": None, "offen": 0,
                "namen": namen_liste(namen)}
    return _antwort_fuer_gruppe(gruppe, gruppen, namen, vorgaben, spaeter, len(offen))


def detail(kennung: str) -> Dict[str, Any]:
    """Eine Gruppe gezielt öffnen, ohne ihren Status oder andere Daten zu ändern."""
    try:
        gruppen, _ = _gruppen_laden()
        namen = bestaetigt_lesen()
        vorgaben = vorgaben_lesen()
        st = _stand_lesen()
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    gruppe = next((g for g in gruppen if g["kennung"] == kennung), None)
    if gruppe is None:
        return {"ok": False, "fehler": f"Gruppe {kennung!r} ist nicht (mehr) in der Gruppen-Datei."}
    offen = sum(1 for g in gruppen
                if g["kennung"] not in namen and g["kennung"] not in st["unbekannt"])
    return _antwort_fuer_gruppe(gruppe, gruppen, namen, vorgaben, st["spaeter"], offen,
                                _gruppen_status(kennung, namen, st))


# ── Alle Gesichter eines Vorschlags + Ausschliessen (02.10.2026) ────────────
#
# Wunsch Sebastian: alle (z. B. 400) Gesichter eines Vorschlags durchsehen und
# falsche antippen („das ist nicht Julian, das bin ich"). Ein ausgeschlossenes
# Gesicht steht als Regel in ``personen_vorgaben.json`` unter
# ``"ausgeschlossen": [{"kennung", "bild_id", "index"}]`` — am Handy wirkt sie
# sofort (Liste, Beispiele, Register), am PC laesst ``personen_gruppieren.py``
# das Gesicht nie wieder in diesen Vorschlag. Rueckgaengig nimmt sie zurueck.

_GID = re.compile(r"^\d+:\d+$")


def _eintrag_gid(eintrag: Any) -> Optional[str]:
    """``"bild_id:index"`` eines Regel-Eintrags (ausgeschlossen/zugeordnet) oder ``None``."""
    if not isinstance(eintrag, dict) or not str(eintrag.get("bild_id") or "").isdigit():
        return None
    try:
        return f"{eintrag['bild_id']}:{int(eintrag.get('index') or 0)}"
    except (TypeError, ValueError):
        return None


def ausgeschlossen_lesen() -> Dict[str, set]:
    """{kennung: {"bild_id:index", ...}} aus personen_vorgaben.json."""
    daten = _json_lesen(_schreibpfad(VORGABEN_DATEINAME), {})
    ergebnis: Dict[str, set] = {}
    for e in (daten.get("ausgeschlossen") if isinstance(daten, dict) else None) or []:
        if isinstance(e, dict) and e.get("kennung") and str(e.get("bild_id") or "").isdigit():
            ergebnis.setdefault(str(e["kennung"]), set()).add(f"{e['bild_id']}:{int(e.get('index') or 0)}")
    return ergebnis


def _gesichter_laden(pfad: str) -> Dict[str, List[Dict[str, Any]]]:
    """``gesicht_zuordnung.jsonl`` -> {kennung: [Gesicht, ...]} (nur Fotos, beste zuerst)."""
    je: Dict[str, List[Dict[str, Any]]] = {}
    with open(pfad, encoding="utf-8") as datei:
        for zeile in datei:
            try:
                z = json.loads(zeile)
            except ValueError:
                continue
            if not isinstance(z, dict) or not z.get("kennung") or z.get("video_id"):
                continue
            bid, bbox = str(z.get("bild_id") or ""), z.get("bbox")
            if not bid.isdigit() or not (isinstance(bbox, list) and len(bbox) == 4):
                continue
            try:
                guete = float(z.get("anteil") or 0) * float(z.get("score") or 0)
            except (TypeError, ValueError):
                guete = 0.0
            je.setdefault(str(z["kennung"]), []).append({
                "gid": f"{bid}:{int(z.get('index') or 0)}", "fileid": bid,
                "index": int(z.get("index") or 0), "bbox": bbox,
                "breite": z.get("breite"), "hoehe": z.get("hoehe"),
                "aufnahme": (str(z.get("aufnahme") or ""))[:10] or None, "_guete": guete})
    for liste in je.values():
        liste.sort(key=lambda g: (-g["_guete"], g["gid"]))
    return je


# ── Video-Gesichter ueber Standbilder (14.10.2026, Plan video-gesichter-im-quiz V2) ──
#
# ``tools/foto_sortierung/video_standbilder.py`` legt fuer ausgewaehlte Video-Frames ein
# Standbild in pCloud ab und schreibt die Karte ``video_standbilder.jsonl``
# (``bild_id`` "<vid>#t=<s>" -> ``standbild_fileid``, ``skala``, Mass). Video-Zeilen der
# Gesichtsdatei und Karte werden GETRENNT gemerkt (je an ihre Datei gebunden) und erst
# beim Aufruf zusammengefuehrt — kommt nur die Karte neu, sieht das Quiz sie sofort.
# Seit 18.10.2026 (S2, Sebastians Befund „Bilder aus Videos lassen sich nicht markieren")
# sind Einzelaktionen auch fuer Video-Gesichter erlaubt: ihre ``gid`` ist
# "<standbild_fileid>:<index>", also dieselbe Form wie bei Fotos. Traegt die Regel das
# Standbild als ``bild_id``, liest :func:`ausgeschlossen_lesen` genau diese ``gid``
# zurueck — Ausschliessen und Zuordnen wirken damit sofort in Liste, Belegen und
# Personenansicht. Der Gruppierlauf am PC kennt Standbilder weiterhin nicht (er trennt
# Video- und Fotozeilen), dort bleibt eine Video-Regel ohne Wirkung.


def _video_zeilen_laden(pfad: str) -> Dict[str, List[Dict[str, Any]]]:
    """``gesicht_zuordnung.jsonl`` -> {kennung: [Video-Zeile, ...]} (nur Video-Gesichter)."""
    je: Dict[str, List[Dict[str, Any]]] = {}
    with open(pfad, encoding="utf-8") as datei:
        for zeile in datei:
            try:
                z = json.loads(zeile)
            except ValueError:
                continue
            if not isinstance(z, dict) or not z.get("kennung") or not z.get("video_id"):
                continue
            bbox = z.get("bbox")
            try:
                guete = float(z.get("anteil") or 0) * float(z.get("score") or 0)
            except (TypeError, ValueError):
                guete = 0.0          # unlesbarer Score: nur ans Ende sortiert, nicht verworfen
            try:
                zeit = float(z.get("zeit_s"))
            except (TypeError, ValueError):
                zeit = None
            if zeit is None or not (isinstance(bbox, list) and len(bbox) == 4
                                    and all(isinstance(w, (int, float)) for w in bbox)):
                # Nicht darstellbar, zaehlt aber weiter als Video-Gesicht ohne Standbild.
                je.setdefault(str(z["kennung"]), []).append({"bild_id": None})
                continue
            je.setdefault(str(z["kennung"]), []).append({
                "bild_id": f"{z['video_id']}#t={zeit:.1f}", "index": int(z.get("index") or 0),
                "bbox": bbox, "zeit_s": zeit,
                "aufnahme": (str(z.get("aufnahme") or ""))[:10] or None, "_guete": guete})
    return je


def _standbilder_laden(pfad: str) -> Dict[str, Dict[str, Any]]:
    """Karte -> {"<vid>#t=<s>": {"fileid", "breite", "hoehe", "skala"}}; kaputte Zeilen fallen weg."""
    karte: Dict[str, Dict[str, Any]] = {}
    with open(pfad, encoding="utf-8") as datei:
        for zeile in datei:
            try:
                z = json.loads(zeile)
            except ValueError:
                continue
            if not isinstance(z, dict):
                continue
            fid, skala = z.get("standbild_fileid"), z.get("skala")
            if not isinstance(fid, int) or isinstance(fid, bool) or fid <= 0:
                continue
            if not isinstance(skala, (int, float)) or not 0 < skala <= 1:
                continue
            # Ohne gueltiges Mass kein Ausschnitt/Rahmen: dann lieber "ohne Standbild" zaehlen.
            if not all(isinstance(z.get(m), (int, float)) and not isinstance(z.get(m), bool)
                       and z.get(m) > 0 for m in ("breite", "hoehe")):
                continue
            try:
                schluessel = f"{z['video_id']}#t={float(z['zeit_s']):.1f}"
            except (KeyError, TypeError, ValueError):
                continue
            karte[schluessel] = {"fileid": str(fid), "breite": z.get("breite"),
                                 "hoehe": z.get("hoehe"), "skala": float(skala)}
    return karte


def _video_karte() -> Dict[str, Dict[str, Any]]:
    """Die Standbild-Karte; fehlt oder klemmt sie, ``{}`` (Quiz laeuft wie ohne Karte)."""
    pfad = _lesepfad(VIDEO_STANDBILDER_DATEINAME)
    if not pfad:
        return {}
    try:
        return _gemerkt(pfad, _standbilder_laden)
    except (OSError, UnicodeDecodeError) as problem:
        logger.warning("Standbild-Karte nicht lesbar (%s) - Video-Gesichter bleiben verborgen.",
                       problem.__class__.__name__)
        return {}


def _video_gesichter(zeilen: List[Dict[str, Any]], karte: Dict[str, Dict[str, Any]]
                     ) -> Tuple[List[Dict[str, Any]], int]:
    """(sichtbare Video-Gesichter wie Foto-Gesichter, Zahl ohne Standbild)."""
    sichtbar, ohne = [], 0
    for z in zeilen:
        bild = karte.get(z["bild_id"]) if z["bild_id"] else None
        if not bild:
            ohne += 1
            continue
        skala = bild["skala"]
        sichtbar.append({
            "gid": f"{bild['fileid']}:{z['index']}", "fileid": bild["fileid"], "index": z["index"],
            "bbox": [round(w * skala) for w in z["bbox"]], "breite": bild["breite"],
            "hoehe": bild["hoehe"], "aufnahme": z["aufnahme"], "video": True,
            "zeit_s": z["zeit_s"], "_guete": z["_guete"]})
    return sichtbar, ohne


def _video_teil(kennungen: Iterable[str]) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, int]]:
    """Fuer mehrere Kennungen: ({kennung: Video-Gesichter}, {kennung: ohne Standbild}).
    Leer, wenn die Gesichtsdatei fehlt."""
    pfad = _lesepfad(ZUORDNUNG_DATEINAME)
    if not pfad:
        return {}, {}
    zeilen = _gemerkt(pfad, _video_zeilen_laden)
    karte = _video_karte()
    sichtbar: Dict[str, List[Dict[str, Any]]] = {}
    ohne: Dict[str, int] = {}
    for k in kennungen:
        sichtbar[k], ohne[k] = _video_gesichter(zeilen.get(k, []), karte)
    return sichtbar, ohne


def _video_beispiele(kennung: str, aus: set, schon: set, anzahl: int) -> List[Dict[str, Any]]:
    """Die besten Video-Gesichter einer Gruppe als Beispiele (je Standbild hoechstens eines)."""
    if anzahl <= 0:
        return []
    liste = sorted(_video_teil([kennung])[0].get(kennung, []), key=lambda g: (-g["_guete"], g["gid"]))
    ergebnis = []
    for g in liste:
        if g["gid"] in aus or g["fileid"] in schon:
            continue
        schon.add(g["fileid"])
        ergebnis.append({k: v for k, v in g.items() if not k.startswith("_") and k != "gid"})
        if len(ergebnis) >= anzahl:
            break
    return ergebnis


def _video_gids_je_kennung(kennungen: Iterable[str]) -> Dict[str, set]:
    """{kennung: {Video-``gid``, …}} — leere Mengen, wenn Gesichtsdatei oder Karte fehlen.

    Die Prüfung „gehört das Gesicht zu diesem Vorschlag?" muss auch Video-Gesichter
    kennen: ihre ``gid`` ist "<standbild_fileid>:<index>" (S2, 18.10.2026)."""
    try:
        teil = _video_teil(kennungen)[0]
    except (GruppenFehler, OSError):
        return {}
    return {k: {g["gid"] for g in liste} for k, liste in teil.items()}


ORDNUNGEN = ("guete", "zeit")


def _ordnen(liste: List[Dict[str, Any]], ordnung: str) -> None:
    """``guete`` (Standard): groesste/sicherste zuerst. ``zeit`` (10.10.2026): nach Aufnahme,
    ohne Datum am Ende - gemischte Kinder-/Zwillingsgruppen zerfallen so in Zeitbloecke."""
    if ordnung == "zeit":
        liste.sort(key=lambda g: (g.get("aufnahme") or "9999", g["gid"]))
    else:
        liste.sort(key=lambda g: (-g["_guete"], g["gid"]))


def _gesichter_je_bild_laden(pfad: str) -> Dict[str, List[Dict[str, Any]]]:
    """``gesicht_zuordnung.jsonl`` -> {bild_id: [Gesicht, ...]} (nur Fotos, mit Rahmen)."""
    je: Dict[str, List[Dict[str, Any]]] = {}
    with open(pfad, encoding="utf-8") as datei:
        for zeile in datei:
            try:
                z = json.loads(zeile)
            except ValueError:
                continue
            if not isinstance(z, dict) or not z.get("kennung") or z.get("video_id"):
                continue
            bid, bbox = str(z.get("bild_id") or ""), z.get("bbox")
            if not bid.isdigit() or not (isinstance(bbox, list) and len(bbox) == 4):
                continue
            index = int(z.get("index") or 0)
            je.setdefault(bid, []).append({
                "gid": f"{bid}:{index}", "index": index, "kennung": str(z["kennung"]),
                "bbox": bbox, "breite": z.get("breite"), "hoehe": z.get("hoehe")})
    return je


# ── Bild-Korrekturen und zusammengefuehrte Gesichtssicht (Bild-Editor B1, 26.10.2026) ──
#
# Zusammenfassung: ``bild_korrekturen.json`` (nur Handy, NICHT im PC-Ordner, nie in
# ``personen_vorgaben.json``) haelt je Bild (fileid)
#   {"rahmen": {"<index>": {"bbox_norm": [x, y, w, h] | null, "quelle": "hand" | "erkennung",
#                           "name": "…" | null, ["breite", "hoehe"]}},
#    "entfernt": ["<index>", …]}
# Index < 1000 = erkanntes Gesicht aus ``gesicht_zuordnung.jsonl`` (verschobener Rahmen
# und/oder handy-eigener Name; ``entfernt`` blendet es aus), Index >= 1000 = Hand-Gesicht
# (vergibt nur der Server). ``bbox_norm`` ist normiert (0..1, links/oben/Breite/Hoehe); bei
# einem erkannten Gesicht nur mit Namen darf es ``null`` sein (Rahmen bleibt der erkannte).
# EINE Sicht (``_bild_sicht``) liest alles zusammen — ``bild-gesichter``, „Bilder mit X“
# und das Erzaehlen (``personen_auf_bildern``) nutzen genau diese Funktion.

def _positiv(wert: Any) -> Optional[float]:
    """Zahl > 0 (kein Wahrheitswert, kein NaN/unendlich), sonst ``None``."""
    if isinstance(wert, bool) or not isinstance(wert, (int, float)):
        return None
    return wert if wert == wert and 0 < wert < float("inf") else None


def _bbox_norm(wert: Any) -> Optional[List[float]]:
    """``[x, y, w, h]`` normiert und gueltig, sonst ``None``.

    Regel: Zahlen (kein Wahrheitswert, kein NaN/unendlich), links/oben >= 0, Breite und
    Hoehe mindestens ``BBOX_MIN`` (1 %), das Rechteck liegt im Bild (Summe <= 1).
    """
    if not isinstance(wert, (list, tuple)) or len(wert) != 4:
        return None
    zahlen: List[float] = []
    for w in wert:
        if isinstance(w, bool) or not isinstance(w, (int, float)) or w != w or abs(w) == float("inf"):
            return None
        zahlen.append(float(w))
    x, y, b, h = zahlen
    if x < 0 or y < 0 or b < BBOX_MIN or h < BBOX_MIN or x + b > 1 + 1e-9 or y + h > 1 + 1e-9:
        return None
    return [round(w, 6) for w in zahlen]


def _korrektur_name(wert: Any) -> Optional[str]:
    return wert.strip() if isinstance(wert, str) and wert.strip() else None


def _korrekturen_roh() -> Dict[str, Any]:
    """Der Inhalt von ``bild_korrekturen.json`` (nur ``basis()``, nie ``personen_gruppen/``)."""
    roh = _json_lesen(_schreibpfad(KORREKTUREN_DATEINAME), {})
    daten = dict(roh) if isinstance(roh, dict) else {}
    bilder = daten.get("bilder")
    daten["version"] = 1
    daten["bilder"] = dict(bilder) if isinstance(bilder, dict) else {}
    return daten


def _korrekturen_lesen() -> Dict[str, Dict[str, Any]]:
    """{fileid: {"rahmen": {index(int): {bbox_norm, quelle, name, breite, hoehe}},
    "entfernt": {index(int), …}}} — tolerant: Kaputtes wird uebergangen, nie geraten."""
    ergebnis: Dict[str, Dict[str, Any]] = {}
    for fileid, e in _korrekturen_roh()["bilder"].items():
        if not (isinstance(fileid, str) and fileid.isdigit() and isinstance(e, dict)):
            continue
        rahmen: Dict[int, Dict[str, Any]] = {}
        roh_rahmen = e.get("rahmen")
        for schluessel, r in (roh_rahmen.items() if isinstance(roh_rahmen, dict) else ()):
            if not (isinstance(schluessel, str) and schluessel.isdigit() and isinstance(r, dict)):
                continue
            index = int(schluessel)
            rahmen[index] = {
                "bbox_norm": _bbox_norm(r.get("bbox_norm")),
                "quelle": "hand" if index >= HAND_INDEX_AB else "erkennung",
                "name": _korrektur_name(r.get("name")),
                "breite": _positiv(r.get("breite")), "hoehe": _positiv(r.get("hoehe"))}
        roh_entfernt = e.get("entfernt")
        entfernt = {int(i) for i in (roh_entfernt if isinstance(roh_entfernt, list) else [])
                    if isinstance(i, (str, int)) and not isinstance(i, bool) and str(i).isdigit()}
        if rahmen or entfernt:
            ergebnis[fileid] = {"rahmen": rahmen, "entfernt": entfernt}
    return ergebnis


def _pixel_aus_norm(norm: List[float], breite: float, hoehe: float) -> List[int]:
    return [round(norm[0] * breite), round(norm[1] * hoehe),
            round(norm[2] * breite), round(norm[3] * hoehe)]


def _norm_aus_pixel(bbox: Any, breite: Any, hoehe: Any) -> Optional[List[float]]:
    b, h = _positiv(breite), _positiv(hoehe)
    if not (b and h and isinstance(bbox, list) and len(bbox) == 4):
        return None
    if any(isinstance(w, bool) or not isinstance(w, (int, float)) or w != w for w in bbox):
        return None
    return [round(bbox[0] / b, 6), round(bbox[1] / h, 6), round(bbox[2] / b, 6), round(bbox[3] / h, 6)]


def _sicht_quellen(korr: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Alles, was die Gesichtssicht braucht — gelesen, nichts geschrieben.
    Wirft ``GruppenFehler`` (fehlende Gruppen-Datei, unlesbare Datei) oder ``OSError``."""
    pfad = _lesepfad(ZUORDNUNG_DATEINAME)
    if not pfad:
        raise GruppenFehler(FEHLT_HINWEIS)
    return {"je_bild": _gemerkt(pfad, _gesichter_je_bild_laden), "namen": bestaetigt_lesen(),
            "aus": ausgeschlossen_lesen(), "zug": zugeordnet_lesen(),
            "fremd": set(_stand_lesen()["unbekannt"]),
            "korr": _korrekturen_lesen() if korr is None else korr}


def _bild_sicht(fileid: str, q: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Die Gesichter eines Fotos, zusammengefuehrt (links nach rechts).

    Erkannte Gesichter wie bisher (Ausgeschlossene und „kenne ich nicht“ fehlen, von Hand
    Zugeordnete bleiben), dazu die Korrekturen: ``entfernt`` blendet aus, ein verschobener
    Rahmen ersetzt den erkannten, Hand-Gesichter kommen dazu. Name: handy-eigen vor
    Einzelzuordnung vor Gruppenname. Die alten Felder (``gid``, ``index``, ``kennung``,
    ``bbox``, ``breite``, ``hoehe``, ``name``) bleiben; neu: ``bbox_norm``, ``name_quelle``
    (``gruppe`` | ``zuordnung`` | ``handy``), ``quelle`` (``erkennung`` | ``hand``).
    """
    je_bild, namen, aus, zug, fremd = q["je_bild"], q["namen"], q["aus"], q["zug"], q["fremd"]
    korr = q["korr"].get(fileid) or {"rahmen": {}, "entfernt": set()}
    rahmen, entfernt = korr["rahmen"], korr["entfernt"]
    alle = je_bild.get(fileid, [])
    erkannt = [g for g in alle
               if g["gid"] in zug or (g["gid"] not in aus.get(g["kennung"], set())
                                      and g["kennung"] not in fremd)]
    masse = next(((_positiv(g.get("breite")), _positiv(g.get("hoehe"))) for g in alle
                  if _positiv(g.get("breite")) and _positiv(g.get("hoehe"))), (None, None))
    sicht: List[Dict[str, Any]] = []
    for g in erkannt:
        if g["index"] in entfernt:
            continue
        r = rahmen.get(g["index"]) or {}
        breite, hoehe = _positiv(g.get("breite")), _positiv(g.get("hoehe"))
        bbox = g["bbox"]
        bbox_norm = r.get("bbox_norm")
        if bbox_norm:
            if breite and hoehe:
                bbox = _pixel_aus_norm(bbox_norm, breite, hoehe)
        else:
            bbox_norm = _norm_aus_pixel(bbox, g.get("breite"), g.get("hoehe"))
        if r.get("name"):
            name, quelle = r["name"], "handy"
        elif g["gid"] in zug:
            name, quelle = zug[g["gid"]]["name"], "zuordnung"
        elif namen.get(g["kennung"]):
            name, quelle = namen[g["kennung"]], "gruppe"
        else:
            name, quelle = None, None
        sicht.append(dict(g, bbox=bbox, name=name, bbox_norm=bbox_norm, name_quelle=quelle,
                          quelle="erkennung"))
    for index in sorted(i for i in rahmen if i >= HAND_INDEX_AB):
        r = rahmen[index]
        if not r["bbox_norm"]:
            continue
        breite, hoehe = r.get("breite") or masse[0], r.get("hoehe") or masse[1]
        sicht.append({
            "gid": f"{fileid}:{index}", "index": index, "kennung": None,
            "bbox": _pixel_aus_norm(r["bbox_norm"], breite, hoehe) if breite and hoehe else None,
            "breite": breite, "hoehe": hoehe, "name": r["name"], "bbox_norm": r["bbox_norm"],
            "name_quelle": "handy" if r["name"] else None, "quelle": "hand"})

    def links(g: Dict[str, Any]) -> float:
        if g["bbox_norm"]:
            return g["bbox_norm"][0]
        x = g["bbox"][0] if isinstance(g.get("bbox"), list) and g["bbox"] else 0
        return x if isinstance(x, (int, float)) else 0

    sicht.sort(key=lambda g: (links(g), g["index"]))
    return sicht


def _sicht_namen(fileid: str, q: Dict[str, Any]) -> Tuple[Dict[str, str], List[str]]:
    """Wer ist auf dem Bild? Aus derselben Sicht wie ``bild-gesichter``.

    Rueckgabe: ({name.casefold(): name}, sortierte Kennungen unbenannter Gesichter);
    ein unbenanntes Hand-Gesicht steht als ``hand:<gid>``. Einzelzuordnungen, deren
    Gesicht es in der Erkennung nicht mehr gibt, zaehlen wie bisher mit.
    """
    benannt: Dict[str, str] = {}
    unbenannt: set = set()
    for g in _bild_sicht(fileid, q):
        if g["name"]:
            benannt.setdefault(g["name"].casefold(), g["name"])
        else:
            unbenannt.add(g["kennung"] or f"hand:{g['gid']}")
    bekannt = {g["gid"] for g in q["je_bild"].get(fileid, [])}
    for gid, e in q["zug"].items():
        if gid.split(":")[0] == fileid and gid not in bekannt:
            benannt.setdefault(e["name"].casefold(), e["name"])
    return benannt, sorted(unbenannt)


def gesichter_auf_bild(fileid: Any) -> Dict[str, Any]:
    """Die Gesichter eines Fotos fuers Erzaehlen und den Bild-Editor. Nie ein Wurf.

    Je Gesicht ``gid`` (bild_id:index), ``kennung`` (``None`` bei Hand-Gesichtern), ``name``
    (bestaetigt, zugeordnet, handy-eigen oder ``None``), ``bbox`` mit ``breite``/``hoehe``
    (Ausschnitt im Browser) — dazu seit 26.10.2026 ``bbox_norm``, ``name_quelle`` und
    ``quelle`` (rein additiv, siehe :func:`_bild_sicht`). Ausgeschlossene Gesichter und als
    „kenne ich nicht" markierte Gruppen fehlen. Reihenfolge: von links nach rechts.
    Benennen und „ist nicht X" laufen ueber die vorhandenen Wege
    (:func:`antworten`, :func:`ausschliessen`), Rahmen und Namen ueber :func:`bild_rahmen`
    — mit Protokoll und Rueckgaengig.
    """
    s = str(fileid).strip() if fileid is not None else ""
    if not s.isdigit():
        return {"ok": False, "fehler": "Ungültige Bildkennung."}
    try:
        gesichter = _bild_sicht(s, _sicht_quellen())
    except (GruppenFehler, OSError) as fehler:
        return {"ok": False, "fehler": str(fehler)}
    return {"ok": True, "fileid": s, "gesichter": gesichter}


def gesichter(kennung: str, seite: int = 1, je_seite: int = GESICHTER_JE_SEITE,
              ordnung: str = "guete") -> Dict[str, Any]:
    """Alle (nicht ausgeschlossenen) Gesichter eines Vorschlags, seitenweise. Nie ein Wurf.
    ``videos``: Gesichter aus Videos OHNE Standbild - die kann die Ansicht nicht
    zeigen (noch kein Bild vorhanden, Stand 15.10.2026)."""
    pfad = _lesepfad(ZUORDNUNG_DATEINAME)
    if not pfad:
        return {"ok": False, "fehler": FEHLT_HINWEIS}
    try:
        alle = _gemerkt(pfad, _gesichter_laden).get(str(kennung), [])
        aus = ausgeschlossen_lesen().get(str(kennung), set())
        video_teil, ohne = _video_teil([str(kennung)])
        videos = ohne.get(str(kennung), 0)
    except (GruppenFehler, OSError) as fehler:
        return {"ok": False, "fehler": str(fehler)}
    sichtbar = ([g for g in alle if g["gid"] not in aus]
                # Video-Gesichter tragen dieselbe Regel-Form (S2, 18.10.2026).
                + [g for g in video_teil.get(str(kennung), []) if g["gid"] not in aus])
    _ordnen(sichtbar, ordnung)
    je_seite = max(1, min(int(je_seite or GESICHTER_JE_SEITE), 200))
    seiten = max(1, (len(sichtbar) + je_seite - 1) // je_seite)
    seite = max(1, min(int(seite or 1), seiten))
    teil = sichtbar[(seite - 1) * je_seite: seite * je_seite]
    return {"ok": True, "kennung": kennung, "gesamt": len(sichtbar), "ausgeschlossen": len(aus),
            "videos": videos, "seite": seite, "seiten": seiten, "ordnung": ordnung,
            "gesichter": [{k: v for k, v in g.items() if not k.startswith("_")} for g in teil]}


def ausschliessen(kennung: str, gids: Iterable[str], *, aufheben: bool = False,
                  _extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Gesichter aus einem Vorschlag nehmen (Regel fuer den naechsten Gruppierlauf). Nie ein Wurf.

    ``aufheben=True`` (Entfernen im Bild-Editor, B1): zuerst alle festen Zuordnungen dieser
    Gesichter aufheben (sonst widerspricht der neue Ausschluss einer festen Zuordnung und der
    PC-Leser bricht ab); sie stehen als ``vorher_zugeordnet`` im Protokoll, Rueckgaengig stellt
    sie wieder her. ``_extra`` kommt ins Protokoll (z. B. die gemeinsame ``aktion``).
    """
    liste = [str(g).strip() for g in (gids or [])]
    if not liste:
        return {"ok": False, "fehler": "Bitte mindestens ein Gesicht antippen."}
    if len(liste) > AUSSCHLUSS_MAX:
        return {"ok": False, "fehler": f"Höchstens {AUSSCHLUSS_MAX} Gesichter auf einmal."}
    if not all(_GID.match(g) for g in liste):
        return {"ok": False, "fehler": "Ungültige Gesichts-Kennung."}
    pfad = _lesepfad(ZUORDNUNG_DATEINAME)
    if not pfad:
        return {"ok": False, "fehler": FEHLT_HINWEIS}
    try:
        with _SCHREIBSPERRE:
            vorhanden = {g["gid"] for g in _gemerkt(pfad, _gesichter_laden).get(str(kennung), [])}
            # Video-Gesichter gehören zur selben Liste (S2, 18.10.2026): ihre gid ist
            # "<standbild_fileid>:<index>" und wird als Regel genauso gespeichert.
            vorhanden |= _video_gids_je_kennung([str(kennung)]).get(str(kennung), set())
            fremd = [g for g in liste if g not in vorhanden]
            if fremd:
                raise GruppenFehler("Gesicht gehört nicht (mehr) zu diesem Vorschlag.")
            aufgehoben: List[Any] = []
            neu = _ausschluss_schreiben([(str(kennung), g) for g in liste], _extra,
                                        liste if aufheben else None, aufgehoben)
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    except OSError as fehler:
        logger.error("Ausschliessen fehlgeschlagen: %s", fehler)
        return {"ok": False, "fehler": f"Speichern fehlgeschlagen ({fehler.__class__.__name__})."}
    rest = gesichter(kennung, 1)
    antwort = {"ok": True, "kennung": kennung, "ausgeschlossen": len(neu),
               "gesamt": rest.get("gesamt", 0)}
    if aufheben:
        antwort["zuordnungen_aufgehoben"] = len(aufgehoben)
    return antwort


def _ausschluss_schreiben(paare: List[Tuple[str, str]], extra: Optional[Dict[str, Any]] = None,
                          aufheben: Optional[List[str]] = None,
                          aufgehoben_aus: Optional[List[Any]] = None) -> List[Tuple[str, str]]:
    """Paare ``(kennung, "bild_id:index")`` als Nutzer-Regel eintragen. Unter ``_SCHREIBSPERRE`` rufen.

    Schon ausgeschlossene Paare zaehlen nicht; geschrieben wird nur, wenn etwas neu ist — dann
    EIN Protokolleintrag (``kennung`` + ``gesichter`` wie bisher; betrifft er mehrere Vorschlaege,
    zusaetzlich ``je_kennung``, damit Rueckgaengig alles in einem Schritt zuruecknimmt).

    ``aufheben`` (B1, 26.10.2026): Gesichter (``"bild_id:index"``), deren feste Zuordnungen
    (``zugeordnet``) in DERSELBEN Schreibung zuerst aufgehoben werden; die entfernten Eintraege
    stehen als ``vorher_zugeordnet`` im Protokoll (und in ``aufgehoben_aus``). Das gilt auch, wenn
    der Ausschluss selbst nicht neu ist.
    """
    roh = _json_lesen(_schreibpfad(VORGABEN_DATEINAME), {})
    daten = roh if isinstance(roh, dict) else {}
    eintraege = daten.get("ausgeschlossen") if isinstance(daten.get("ausgeschlossen"), list) else []
    schon = ausgeschlossen_lesen()
    neu = [(k, g) for (k, g) in dict.fromkeys(paare) if g not in schon.get(k, set())]
    for k, g in neu:
        bid, idx = g.split(":")
        eintraege.append({"kennung": k, "bild_id": bid, "index": int(idx)})
    daten["ausgeschlossen"] = eintraege
    vorher_zugeordnet: List[Any] = []
    if aufheben and isinstance(daten.get("zugeordnet"), list):
        gids = set(aufheben)
        behalten = []
        for e in daten["zugeordnet"]:
            (vorher_zugeordnet if _eintrag_gid(e) in gids else behalten).append(e)
        if vorher_zugeordnet:
            daten["zugeordnet"] = behalten
    if aufgehoben_aus is not None:
        aufgehoben_aus.extend(vorher_zugeordnet)
    if neu or vorher_zugeordnet:
        je_kennung: Dict[str, List[str]] = {}
        for k, g in neu:
            je_kennung.setdefault(k, []).append(g)
        eintrag: Dict[str, Any] = {"id": uuid.uuid4().hex[:12],
                                   "zeit": datetime.now().isoformat(timespec="seconds"),
                                   "art": "ausschliessen", "kennung": (neu or list(paare))[0][0],
                                   "gesichter": [g for _, g in neu]}
        if len(je_kennung) > 1:
            eintrag["je_kennung"] = je_kennung
        if vorher_zugeordnet:
            eintrag["vorher_zugeordnet"] = vorher_zugeordnet
        eintrag.update(extra or {})
        _atomar_schreiben(VORGABEN_DATEINAME, daten)
        _protokoll_anhaengen(eintrag)
    return neu


# ── Alle Gesichter einer Person ueber alle Vorschlaege (07.10.2026) ─────────
# Wunsch Sebastian: bei bekannten Personen mit mehreren Vorschlaegen alle Gesichter
# in EINER Liste durchsehen und Falsche aussortieren — ohne Vorschlag fuer Vorschlag.

def _person_kennungen(name: str) -> Tuple[str, List[str]]:
    """(gespeicherter Name, Kennungen) einer benannten Person; beides leer, wenn unbekannt."""
    sauber = name_saeubern(name)
    namen = bestaetigt_lesen()
    kennungen = sorted(k for k, n in namen.items() if sauber and n.casefold() == sauber.casefold())
    return (namen[kennungen[0]] if kennungen else ""), kennungen


def gesichter_person(name: str, seite: int = 1, je_seite: int = GESICHTER_JE_SEITE,
                     ordnung: str = "guete") -> Dict[str, Any]:
    """Alle (nicht ausgeschlossenen) Gesichter einer Person ueber ALLE ihre Vorschlaege, beste zuerst,
    seitenweise; jedes Gesicht traegt seine ``kennung`` (fuers Ausschliessen). Nie ein Wurf."""
    pfad = _lesepfad(ZUORDNUNG_DATEINAME)
    if not pfad:
        return {"ok": False, "fehler": FEHLT_HINWEIS}
    try:
        echter, kennungen = _person_kennungen(name)
        if not kennungen:
            return {"ok": False, "fehler": "Keine benannte Person mit diesem Namen."}
        je = _gemerkt(pfad, _gesichter_laden)
        aus = ausgeschlossen_lesen()
        zug = zugeordnet_lesen()
    except (GruppenFehler, OSError) as fehler:
        return {"ok": False, "fehler": str(fehler)}
    sichtbar: List[Dict[str, Any]] = []
    ausgeschlossen = 0
    # Auch die Kennungen fremder Zuordnungen mitladen (S2, 18.10.2026): ein von Hand
    # zugeordnetes Video-Standbild soll in der Personenansicht erscheinen.
    fremde = sorted({str(e.get("kennung") or "") for e in zug.values()} - set(kennungen) - {""})
    try:
        video_teil = _video_teil(list(kennungen) + fremde)[0]
    except (GruppenFehler, OSError) as fehler:
        return {"ok": False, "fehler": str(fehler)}
    for k in kennungen:
        weg = aus.get(k, set())
        ausgeschlossen += len(weg)
        # Von Hand einer ANDEREN Person zugeordnet -> gehoert nicht mehr hierher.
        sichtbar += [dict(g, kennung=k) for g in je.get(k, []) if g["gid"] not in weg
                     and (zug.get(g["gid"]) or {}).get("name", echter).casefold() == echter.casefold()]
        sichtbar += [dict(g, kennung=k) for g in video_teil.get(k, []) if g["gid"] not in weg
                     and (zug.get(g["gid"]) or {}).get("name", echter).casefold() == echter.casefold()]
    # Von Hand dieser Person zugeordnete Gesichter aus fremden Vorschlaegen (10.10.2026).
    schon = {g["gid"] for g in sichtbar}
    eigene = {gid: e["kennung"] for gid, e in zug.items()
              if e["name"].casefold() == echter.casefold() and gid not in schon}
    # Foto- UND Video-Gesichter je Kennung (S2, 18.10.2026): auch ein von Hand
    # zugeordnetes Standbild muss in der Personenansicht auftauchen.
    def _alle_je_kennung(k: str) -> List[Dict[str, Any]]:
        return je.get(k, []) + video_teil.get(k, [])

    fehlend = set(eigene)
    for k in set(eigene.values()):
        for g in _alle_je_kennung(k):
            if eigene.get(g["gid"]) == k:
                sichtbar.append(dict(g, kennung=k, zugeordnet=True))
                fehlend.discard(g["gid"])
    if fehlend:     # nach einem neuen PC-Lauf liegt das Gesicht oft unter einer anderen Kennung
        for k in list(je) + [x for x in video_teil if x not in je]:
            for g in _alle_je_kennung(k):
                if g["gid"] in fehlend:
                    sichtbar.append(dict(g, kennung=k, zugeordnet=True))
                    fehlend.discard(g["gid"])
    _ordnen(sichtbar, ordnung)
    je_seite = max(1, min(int(je_seite or GESICHTER_JE_SEITE), 200))
    seiten = max(1, (len(sichtbar) + je_seite - 1) // je_seite)
    seite = max(1, min(int(seite or 1), seiten))
    teil = sichtbar[(seite - 1) * je_seite: seite * je_seite]
    return {"ok": True, "name": echter, "kennungen": kennungen, "gesamt": len(sichtbar),
            "ausgeschlossen": ausgeschlossen, "seite": seite, "seiten": seiten, "ordnung": ordnung,
            "gesichter": [{k: v for k, v in g.items() if not k.startswith("_")} for g in teil]}


def ausschliessen_person(name: str, eintraege: Iterable[Any]) -> Dict[str, Any]:
    """Markierte Gesichter einer Person ausschliessen — auch aus mehreren Vorschlaegen auf einmal.

    ``eintraege`` = ``[{"kennung": "Person_1001", "gid": "123:0"}, …]``. Jede Kennung muss zur
    Person gehoeren, jedes Gesicht zu seiner Kennung. Ein Protokolleintrag fuer alles. Nie ein Wurf.
    """
    paare: List[Tuple[str, str]] = []
    for e in eintraege or []:
        if isinstance(e, dict):
            paare.append((str(e.get("kennung") or "").strip(), str(e.get("gid") or "").strip()))
    if not paare:
        return {"ok": False, "fehler": "Bitte mindestens ein Gesicht antippen."}
    if len(paare) > AUSSCHLUSS_MAX:
        return {"ok": False, "fehler": f"Höchstens {AUSSCHLUSS_MAX} Gesichter auf einmal."}
    if not all(_GID.match(g) for _, g in paare):
        return {"ok": False, "fehler": "Ungültige Gesichts-Kennung."}
    pfad = _lesepfad(ZUORDNUNG_DATEINAME)
    if not pfad:
        return {"ok": False, "fehler": FEHLT_HINWEIS}
    try:
        echter, kennungen = _person_kennungen(name)
        if not kennungen:
            return {"ok": False, "fehler": "Keine benannte Person mit diesem Namen."}
        with _SCHREIBSPERRE:
            je = _gemerkt(pfad, _gesichter_laden)
            video = _video_gids_je_kennung(kennungen)
            vorhanden = {k: {g["gid"] for g in je.get(k, [])} | video.get(k, set())
                         for k in kennungen}
            for k, g in paare:
                if k not in vorhanden:
                    raise GruppenFehler("Gesicht gehört nicht zu dieser Person.")
                if g not in vorhanden[k]:
                    raise GruppenFehler("Gesicht gehört nicht (mehr) zu diesem Vorschlag.")
            neu = _ausschluss_schreiben(paare, {"name": echter})
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    except OSError as fehler:
        logger.error("Ausschliessen (Person) fehlgeschlagen: %s", fehler)
        return {"ok": False, "fehler": f"Speichern fehlgeschlagen ({fehler.__class__.__name__})."}
    rest = gesichter_person(echter, 1)
    return {"ok": True, "name": echter, "ausgeschlossen": len(neu), "gesamt": rest.get("gesamt", 0)}


# ── Gesichter fest einer Person zuordnen (10.10.2026) ───────────────────────
#
# Anlass: gemischte Kinder- und Zwillingsgruppen (Sebastian, sein Zwilling Julian,
# Bruder David), vor allem aus dem Fotobuch. Ausschliessen nahm ein Gesicht nur aus
# dem Vorschlag - danach gehoerte es niemandem. ``zuordnen`` nimmt es aus seinem
# Vorschlag UND haengt es fest an eine schon benannte Person:
# ``personen_vorgaben.json`` -> ``"zugeordnet": [{"bild_id", "index", "name",
# "kennung", "aktion"}]``; ein spaeterer Eintrag fuer dasselbe Gesicht gewinnt.
# Am Handy wirkt das sofort (Person, Register, Erzaehlen); ``personen_gruppieren.py``
# legt das Gesicht beim naechsten Lauf in einen Vorschlag dieser Person.
# Rueckgaengig nimmt beides zurueck (Eintraege mit derselben ``aktion``).

def zugeordnet_lesen() -> Dict[str, Dict[str, str]]:
    """{"bild_id:index": {"name", "kennung"}} - der letzte Eintrag je Gesicht gilt."""
    daten = _json_lesen(_schreibpfad(VORGABEN_DATEINAME), {})
    ergebnis: Dict[str, Dict[str, str]] = {}
    for e in (daten.get("zugeordnet") if isinstance(daten, dict) else None) or []:
        if not isinstance(e, dict) or not str(e.get("bild_id") or "").isdigit():
            continue
        name = name_saeubern(e.get("name"))
        if name:
            ergebnis[f"{e['bild_id']}:{int(e.get('index') or 0)}"] = {
                "name": name, "kennung": str(e.get("kennung") or "")}
    return ergebnis


def _zugeordnet_je_bild(zug: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """{bild_id: {name.casefold(): name}} aus :func:`zugeordnet_lesen`."""
    je: Dict[str, Dict[str, str]] = {}
    for gid, e in zug.items():
        je.setdefault(gid.split(":")[0], {}).setdefault(e["name"].casefold(), e["name"])
    return je


def zuordnen(name: str, eintraege: Iterable[Any], *,
             _extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Markierte Gesichter fest einer benannten Person zuordnen. Nie ein Wurf.

    ``eintraege`` = ``[{"kennung": "Person_1113", "gid": "123:0"}, …]`` - jedes Gesicht
    muss zu seiner Kennung gehoeren (wie beim Ausschliessen). Die Person muss schon
    benannt sein (mindestens ein Vorschlag mit diesem Namen). Ein Protokolleintrag.

    Seit B1 (26.10.2026) hebt die Zuordnung Ausschluesse dieser Gesichter gegen das NEUE Ziel
    (jeder Vorschlag der Person) auf — sonst stuenden Zuordnung und Ausschluss gegen dasselbe Ziel
    nebeneinander (A -> B -> A) und der PC-Leser braeche mit ``PersonenFehler`` ab. Die aufgehobenen
    Eintraege stehen als ``ausschluesse_aufgehoben`` im Protokoll, Rueckgaengig stellt sie wieder her.
    ``_extra`` kommt ins Protokoll (z. B. die gemeinsame ``aktion`` eines ``bild-rahmen``-Aufrufs).
    """
    paare: List[Tuple[str, str]] = []
    for e in eintraege or []:
        if isinstance(e, dict):
            paare.append((str(e.get("kennung") or "").strip(), str(e.get("gid") or "").strip()))
    if not paare:
        return {"ok": False, "fehler": "Bitte mindestens ein Gesicht antippen."}
    if len(paare) > AUSSCHLUSS_MAX:
        return {"ok": False, "fehler": f"Höchstens {AUSSCHLUSS_MAX} Gesichter auf einmal."}
    if not all(_GID.match(g) for _, g in paare):
        return {"ok": False, "fehler": "Ungültige Gesichts-Kennung."}
    pfad = _lesepfad(ZUORDNUNG_DATEINAME)
    if not pfad:
        return {"ok": False, "fehler": FEHLT_HINWEIS}
    try:
        echter, kennungen = _person_kennungen(name)
        if not kennungen:
            return {"ok": False, "fehler": "Diese Person ist noch nicht benannt – erst einen "
                                           "Vorschlag mit diesem Namen benennen."}
        with _SCHREIBSPERRE:
            je = _gemerkt(pfad, _gesichter_laden)
            video = _video_gids_je_kennung(sorted({k for k, _ in paare} | set(kennungen)))
            for k, g in paare:
                if g not in ({x["gid"] for x in je.get(k, [])} | video.get(k, set())):
                    raise GruppenFehler("Gesicht gehört nicht (mehr) zu diesem Vorschlag.")
            aus = ausgeschlossen_lesen()
            zug = zugeordnet_lesen()
            neu = [(k, g) for k, g in dict.fromkeys(paare)
                   if (zug.get(g) or {}).get("name") != echter
                   and not (k in kennungen and g not in aus.get(k, set()) and g not in zug)]
            if not neu:
                return {"ok": True, "name": echter, "zugeordnet": 0}
            aktion = uuid.uuid4().hex[:12]
            roh = _json_lesen(_schreibpfad(VORGABEN_DATEINAME), {})
            daten = roh if isinstance(roh, dict) else {}
            aus_roh, zug_roh = daten.get("ausgeschlossen"), daten.get("zugeordnet")
            aus_liste: List[Any] = aus_roh if isinstance(aus_roh, list) else []
            zug_liste: List[Any] = zug_roh if isinstance(zug_roh, list) else []
            aus_neu = [(k, g) for k, g in neu if k not in kennungen and g not in aus.get(k, set())]
            aufgehoben = [[k2, g] for g in dict.fromkeys(g for _, g in neu)
                          for k2 in kennungen if g in aus.get(k2, set())]
            if aufgehoben:
                weg_aus = {(k2, g) for k2, g in aufgehoben}
                aus_liste[:] = [e for e in aus_liste
                                if not (isinstance(e, dict) and (str(e.get("kennung")), _eintrag_gid(e)) in weg_aus)]
            for k, g in aus_neu:
                bid, idx = g.split(":")
                aus_liste.append({"kennung": k, "bild_id": bid, "index": int(idx)})
            for k, g in neu:
                bid, idx = g.split(":")
                zug_liste.append({"bild_id": bid, "index": int(idx), "name": echter,
                                  "kennung": k, "aktion": aktion})
            daten["ausgeschlossen"] = aus_liste
            daten["zugeordnet"] = zug_liste
            _atomar_schreiben(VORGABEN_DATEINAME, daten)
            protokoll = {"id": aktion, "zeit": datetime.now().isoformat(timespec="seconds"),
                         "art": "zuordnen", "name": echter, "kennung": neu[0][0],
                         "gesichter": [g for _, g in neu],
                         "ausgeschlossen_neu": [[k, g] for k, g in aus_neu]}
            if aufgehoben:
                protokoll["ausschluesse_aufgehoben"] = aufgehoben
            protokoll.update(_extra or {})
            _protokoll_anhaengen(protokoll)
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    except OSError as fehler:
        logger.error("Zuordnen fehlgeschlagen: %s", fehler)
        return {"ok": False, "fehler": f"Speichern fehlgeschlagen ({fehler.__class__.__name__})."}
    return {"ok": True, "name": echter, "zugeordnet": len(neu)}


def _zuordnungen_umbenennen(daten: Dict[str, Any], alt: str, neu: str) -> List[Dict[str, Any]]:
    """Zielnamen exakt an den gespeicherten Einzelzuordnungen aktualisieren."""
    roh = daten.get("zugeordnet")
    if not isinstance(roh, list):
        return []
    vorher = []
    for index, eintrag in enumerate(roh):
        if not isinstance(eintrag, dict) or not isinstance(eintrag.get("name"), str):
            continue
        try:
            name = name_saeubern(eintrag["name"])
        except GruppenFehler:
            continue
        if name.casefold() == alt.casefold():
            vorher.append({"index": index, "name": eintrag["name"]})
            eintrag["name"] = neu
    return vorher


def _zuordnungen_wiederherstellen(daten: Dict[str, Any], vorher: Any, neu: str) -> bool:
    """Nur Eintraege aus dem Umbenennungsprotokoll auf ihren alten Namen setzen."""
    roh = daten.get("zugeordnet")
    if not isinstance(roh, list) or not isinstance(vorher, list):
        return False
    geaendert = False
    for eintrag in vorher:
        if not isinstance(eintrag, dict):
            continue
        index, name = eintrag.get("index"), eintrag.get("name")
        if (type(index) is not int or index < 0 or index >= len(roh)
                or not isinstance(name, str)):
            continue
        aktuell = roh[index]
        if isinstance(aktuell, dict) and aktuell.get("name") == neu:
            aktuell["name"] = name
            geaendert = True
    return geaendert


def _zuordnen_zuruecknehmen(letzte: Dict[str, Any]) -> None:
    """Rueckgaengig fuer ``zuordnen``: eigene Zuordnungen und eigene Ausschluesse entfernen.
    Unter ``_SCHREIBSPERRE`` rufen."""
    roh = _json_lesen(_schreibpfad(VORGABEN_DATEINAME), {})
    daten = roh if isinstance(roh, dict) else {}
    aktion = letzte.get("id")
    daten["zugeordnet"] = [e for e in daten.get("zugeordnet") or []
                           if not (isinstance(e, dict) and e.get("aktion") == aktion)]
    weg = {(str(k), str(g)) for k, g in letzte.get("ausgeschlossen_neu") or []}
    daten["ausgeschlossen"] = [
        e for e in daten.get("ausgeschlossen") or []
        if not (isinstance(e, dict) and (str(e.get("kennung")),
                f"{e.get('bild_id')}:{int(e.get('index') or 0)}") in weg)]
    # B1: Ausschluesse, die diese Zuordnung gegen ihr Ziel aufgehoben hatte, kommen zurueck.
    for k, g in letzte.get("ausschluesse_aufgehoben") or []:
        if isinstance(g, str) and _GID.match(g):
            bid, idx = g.split(":")
            alt = {"kennung": str(k), "bild_id": bid, "index": int(idx)}
            if alt not in daten["ausgeschlossen"]:
                daten["ausgeschlossen"].append(alt)
    _atomar_schreiben(VORGABEN_DATEINAME, daten)


# ── Aenderungen an einem Bild: POST /api/gruppen/bild-rahmen (B1, 26.10.2026) ──
#
# Ablauf (Plan Fassung 8): (1) ALLES pruefen, bei einem Fehler wird nichts geschrieben;
# (2) ``bild_korrekturen.json`` atomar schreiben + Protokollart ``bild_rahmen`` mit dem
# vorherigen Eintrag NUR dieser fileid (``vorher``); (3) danach die Anteile fuer die
# PC-Gruppierung ueber die vorhandenen Wege ``zuordnen`` / ``ausschliessen`` (mit
# eigenen Protokolleintraegen). Alle Eintraege eines Aufrufs tragen dieselbe ``aktion``;
# ein Rueckgaengig nimmt den ganzen Aufruf zurueck. Scheitert (3), bleibt (2) gespeichert
# und die Antwort sagt genau, was nicht uebernommen wurde.

_AENDERUNG_FELDER = ("gid", "neu", "bbox_norm", "entfernen", "name", "breite", "hoehe")
_MASS_MAX = 100000


def _aenderung_pruefen(nr: int, a: Any, fileid: str, sicht: Dict[str, Dict[str, Any]],
                       entfernt: set) -> Dict[str, Any]:
    """Eine Aenderung pruefen und normalisieren. Wirft ``GruppenFehler`` mit deutschem Text."""
    wo = f"Änderung {nr}: "
    if not isinstance(a, dict):
        raise GruppenFehler(wo + "Kein gültiger Eintrag.")
    unbekannt = sorted(str(k) for k in a if k not in _AENDERUNG_FELDER)
    if unbekannt:
        raise GruppenFehler(wo + f"Unbekanntes Feld ({', '.join(unbekannt)}).")
    for feld in ("neu", "entfernen"):
        if feld in a and not isinstance(a[feld], bool):
            raise GruppenFehler(wo + f"„{feld}“ muss wahr oder falsch sein.")
    neu, entfernen = a.get("neu") is True, a.get("entfernen") is True
    bbox_norm = None
    if "bbox_norm" in a:
        bbox_norm = _bbox_norm(a["bbox_norm"])
        if bbox_norm is None:
            raise GruppenFehler(wo + "Der Rahmen liegt nicht im Bild oder ist kleiner als 1 %.")
    name = None
    if "name" in a:
        try:
            name = name_saeubern(a["name"])
        except GruppenFehler as fehler:
            raise GruppenFehler(wo + str(fehler)) from None
    masse: Dict[str, int] = {}
    for feld in ("breite", "hoehe"):
        if feld in a:
            w = a[feld]
            if isinstance(w, bool) or not isinstance(w, int) or not 1 <= w <= _MASS_MAX:
                raise GruppenFehler(wo + f"„{feld}“ muss eine ganze Zahl von 1 bis {_MASS_MAX} sein.")
            masse[feld] = w
    ergebnis: Dict[str, Any] = {"nr": nr, "neu": neu, "gid": None, "index": None, "entfernen": entfernen,
                                "bbox_norm": bbox_norm, "hat_name": "name" in a, "name": name, **masse}
    if neu:
        if "gid" in a:
            raise GruppenFehler(wo + "Neue Gesichter bekommen ihre Kennung vom Server.")
        if entfernen:
            raise GruppenFehler(wo + "Ein neues Gesicht lässt sich nicht gleichzeitig entfernen.")
        if bbox_norm is None:
            raise GruppenFehler(wo + "Ein neues Gesicht braucht einen Rahmen.")
        return ergebnis
    gid = a.get("gid")
    if not isinstance(gid, str) or not _GID.match(gid):
        raise GruppenFehler(wo + "Ungültige Gesichts-Kennung.")
    bild, index_text = gid.split(":")
    if bild != fileid:
        raise GruppenFehler(wo + "Das Gesicht gehört zu einem anderen Bild.")
    index = int(index_text)
    if index in entfernt and gid not in sicht:
        raise GruppenFehler(wo + "Das Gesicht ist schon entfernt.")
    if gid not in sicht:
        raise GruppenFehler(wo + ("Hand-Gesichter vergibt nur der Server." if index >= HAND_INDEX_AB
                                  else "Dieses Gesicht gibt es auf dem Bild nicht."))
    if entfernen and (bbox_norm is not None or name is not None):
        raise GruppenFehler(wo + "Entfernen geht nicht zusammen mit Rahmen oder Namen.")
    if not (entfernen or bbox_norm is not None or name is not None):
        raise GruppenFehler(wo + "Keine Änderung angegeben.")
    ergebnis.update(gid=gid, index=index)
    return ergebnis


def _bild_rahmen_planen(fileid: str, aenderungen: List[Any], q: Dict[str, Any],
                        roh_bild: Any) -> Dict[str, Any]:
    """Alles pruefen und den NEUEN Eintrag der fileid sowie die Gruppen-Anteile berechnen.
    Schreibt nichts. Wirft ``GruppenFehler``."""
    sicht = {g["gid"]: g for g in _bild_sicht(fileid, q)}
    entfernt_bisher = (q["korr"].get(fileid) or {"entfernt": set()})["entfernt"]
    geprueft: List[Dict[str, Any]] = []
    gesehen: set = set()
    for nr, a in enumerate(aenderungen, 1):
        p = _aenderung_pruefen(nr, a, fileid, sicht, entfernt_bisher)
        if p["gid"] is not None:
            if p["gid"] in gesehen:
                raise GruppenFehler(f"Änderung {nr}: Das Gesicht {p['gid']} kommt doppelt vor.")
            gesehen.add(p["gid"])
        geprueft.append(p)

    bild = copy.deepcopy(roh_bild) if isinstance(roh_bild, dict) else {}
    rahmen = bild.get("rahmen") if isinstance(bild.get("rahmen"), dict) else {}
    rahmen = {str(k): dict(v) for k, v in rahmen.items() if isinstance(v, dict)}
    entfernt = [str(i) for i in (bild.get("entfernt") if isinstance(bild.get("entfernt"), list) else [])]
    naechster = max([int(k) for k in rahmen if k.isdigit() and int(k) >= HAND_INDEX_AB]
                    + [HAND_INDEX_AB - 1]) + 1
    zuordnen_je_name: Dict[str, List[Dict[str, str]]] = {}
    ausschliessen_je_kennung: Dict[str, List[str]] = {}
    neue_gids: List[str] = []
    for p in geprueft:
        if p["neu"]:
            eintrag: Dict[str, Any] = {"bbox_norm": p["bbox_norm"], "quelle": "hand", "name": p["name"]}
            eintrag.update({k: p[k] for k in ("breite", "hoehe") if k in p})
            rahmen[str(naechster)] = eintrag
            neue_gids.append(f"{fileid}:{naechster}")
            naechster += 1
            continue
        schluessel, g = str(p["index"]), sicht[p["gid"]]
        if p["index"] >= HAND_INDEX_AB:                        # Hand-Gesicht
            if p["entfernen"]:
                rahmen.pop(schluessel, None)
                continue
            eintrag = rahmen.get(schluessel)
            if not isinstance(eintrag, dict):                  # Index >= 1000 ohne Hand-Eintrag
                raise GruppenFehler("Dieses Gesicht gibt es auf dem Bild nicht.")
            if p["bbox_norm"] is not None:
                eintrag["bbox_norm"] = p["bbox_norm"]
            if p["hat_name"]:
                eintrag["name"] = p["name"]
            eintrag.update({k: p[k] for k in ("breite", "hoehe") if k in p})
            continue
        if p["entfernen"]:                                      # erkanntes Gesicht entfernen
            rahmen.pop(schluessel, None)
            if schluessel not in entfernt:
                entfernt.append(schluessel)
            ausschliessen_je_kennung.setdefault(g["kennung"], []).append(p["gid"])
            continue
        eintrag = rahmen.get(schluessel) or {"bbox_norm": None, "quelle": "erkennung", "name": None}
        eintrag["quelle"] = "erkennung"
        if p["bbox_norm"] is not None:
            eintrag["bbox_norm"] = p["bbox_norm"]
        if p["hat_name"]:
            echter, kennungen = _person_kennungen(p["name"])
            if kennungen:         # schon benannte Person: feste Einzelzuordnung (erreicht den PC)
                zuordnen_je_name.setdefault(echter, []).append({"kennung": g["kennung"], "gid": p["gid"]})
                eintrag["name"] = None
            else:                 # neue Person: nur am Handy, nicht fuer die Gruppierung
                eintrag["name"] = p["name"]
        if eintrag.get("bbox_norm") is None and not eintrag.get("name"):
            rahmen.pop(schluessel, None)
        else:
            rahmen[schluessel] = eintrag
    neu_bild: Optional[Dict[str, Any]] = dict(bild)              # fremde Schluessel bleiben erhalten
    neu_bild["rahmen"] = dict(sorted(rahmen.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0))
    neu_bild["entfernt"] = sorted(dict.fromkeys(entfernt), key=lambda i: int(i) if i.isdigit() else 0)
    if not neu_bild["rahmen"] and not neu_bild["entfernt"] and set(neu_bild) <= {"rahmen", "entfernt"}:
        neu_bild = None
    return {"bild": neu_bild, "neue_gids": neue_gids, "zuordnen": zuordnen_je_name,
            "ausschliessen": ausschliessen_je_kennung}


def _bild_rahmen_zuruecknehmen(letzte: Dict[str, Any]) -> None:
    """Rueckgaengig fuer ``bild_rahmen``: den Eintrag dieser fileid auf ``vorher`` setzen.
    Andere Bilder bleiben unberuehrt. Unter ``_SCHREIBSPERRE`` rufen."""
    fileid = str(letzte.get("fileid") or "")
    if not fileid.isdigit():
        raise GruppenFehler("Eintrag ohne gültige Bildkennung.")
    daten = _korrekturen_roh()
    vorher = letzte.get("vorher")
    if isinstance(vorher, dict):
        daten["bilder"][fileid] = vorher
    else:
        daten["bilder"].pop(fileid, None)
    _atomar_schreiben(KORREKTUREN_DATEINAME, daten)


def bild_rahmen(fileid: Any, aenderungen: Any) -> Dict[str, Any]:
    """Aenderungen an den Gesichtern EINES Bildes speichern (Rahmen, Namen, neue/entfernte
    Gesichter). ``aenderungen``: hoechstens ``BILD_RAHMEN_MAX`` Eintraege
    ``{gid, bbox_norm?, entfernen?, name?}`` oder ``{neu: true, bbox_norm, name?}``. Nie ein Wurf.

    Antwort: ``ok`` (alles uebernommen), ``teilweise`` (ein Teil gespeichert, ein anderer nicht),
    ``geschrieben``, ``aktion``, ``neu`` (vom Server vergebene gids), ``teile`` (je Teil
    ``ok``/``fehler``), ``fehler`` (Klartext), ``gesichter`` (die neue Sicht).
    """
    s = str(fileid).strip() if isinstance(fileid, (str, int)) and not isinstance(fileid, bool) else ""
    if not s.isdigit():
        return {"ok": False, "fehler": "Ungültige Bildkennung.", "geschrieben": False}
    if not isinstance(aenderungen, list) or not aenderungen:
        return {"ok": False, "fehler": "Bitte mindestens eine Änderung angeben.", "geschrieben": False}
    if len(aenderungen) > BILD_RAHMEN_MAX:
        return {"ok": False, "fehler": f"Höchstens {BILD_RAHMEN_MAX} Änderungen auf einmal.",
                "geschrieben": False}
    aktion = uuid.uuid4().hex[:12]
    try:
        with _SCHREIBSPERRE:
            q = _sicht_quellen()
            vorher = _korrekturen_roh()["bilder"].get(s)
            plan = _bild_rahmen_planen(s, aenderungen, q, vorher)             # (1) nur pruefen
            korrigiert = plan["bild"] != vorher
            if korrigiert:                                                     # (2) schreiben
                daten = _korrekturen_roh()
                if plan["bild"] is None:
                    daten["bilder"].pop(s, None)
                else:
                    daten["bilder"][s] = plan["bild"]
                _atomar_schreiben(KORREKTUREN_DATEINAME, daten)
                _protokoll_anhaengen({"id": uuid.uuid4().hex[:12],
                                      "zeit": datetime.now().isoformat(timespec="seconds"),
                                      "art": "bild_rahmen", "aktion": aktion, "fileid": s,
                                      "vorher": copy.deepcopy(vorher), "aenderungen": len(aenderungen)})
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler), "geschrieben": False}
    except OSError as fehler:
        logger.error("Bild-Rahmen fehlgeschlagen: %s", fehler)
        return {"ok": False, "fehler": f"Speichern fehlgeschlagen ({fehler.__class__.__name__}).",
                "geschrieben": False}
    teile: List[Dict[str, Any]] = [{"teil": "korrekturen", "ok": True, "geaendert": korrigiert}]
    nicht_uebernommen: List[str] = []
    for name, eintraege in plan["zuordnen"].items():                           # (3) PC-Anteile
        res = zuordnen(name, eintraege, _extra={"aktion": aktion})
        ok = res.get("ok") is not False
        teil: Dict[str, Any] = {"teil": "zuordnen", "name": name, "ok": ok,
                                "gesichter": [e["gid"] for e in eintraege],
                                "geaendert": ok and int(res.get("zugeordnet") or 0) > 0}
        if not ok:
            teil["fehler"] = res.get("fehler") or "Unbekannter Fehler."
            nicht_uebernommen.append(f"Zuordnung zu „{name}“ ({teil['fehler']})")
        teile.append(teil)
    for kennung, gids in plan["ausschliessen"].items():
        res = ausschliessen(kennung, gids, aufheben=True, _extra={"aktion": aktion})
        ok = res.get("ok") is not False
        teil = {"teil": "ausschliessen", "kennung": kennung, "ok": ok, "gesichter": gids,
                "geaendert": ok and (int(res.get("ausgeschlossen") or 0) > 0
                                     or int(res.get("zuordnungen_aufgehoben") or 0) > 0)}
        if not ok:
            teil["fehler"] = res.get("fehler") or "Unbekannter Fehler."
            nicht_uebernommen.append(f"Entfernen aus dem Vorschlag {kennung} ({teil['fehler']})")
        teile.append(teil)
    alle_ok = all(t["ok"] for t in teile)
    geschrieben = any(t["ok"] and t.get("geaendert") for t in teile)
    antwort: Dict[str, Any] = {"ok": alle_ok, "teilweise": (not alle_ok) and geschrieben,
                               "geschrieben": geschrieben, "fileid": s, "aktion": aktion,
                               "neu": plan["neue_gids"], "teile": teile}
    if nicht_uebernommen:
        antwort["fehler"] = ("Nicht alles gespeichert – wurde nicht übernommen: "
                             + "; ".join(nicht_uebernommen) + ".")
    sicht = gesichter_auf_bild(s)
    antwort["gesichter"] = sicht.get("gesichter", []) if sicht.get("ok") else []
    return antwort


# ── Benannte Personen wieder oeffnen und bearbeiten (02.10.2026) ────────────
#
# Wunsch Sebastian: „aktuell bin ich nur am Sortieren, die alten kann ich nicht
# aufrufen und noch mal bearbeiten." Eine Person = alle Vorschlaege mit
# demselben bestaetigten Namen (Gross/Klein egal).

def _anzeige_beispiele(gruppe: Dict[str, Any], aus: set) -> List[Dict[str, Any]]:
    return [b for b in (_beispiel_fuer_anzeige(x) for x in gruppe.get("beispiele") or [])
            if b and f"{b['fileid']}:{int(b.get('index') or 0)}" not in aus][:BEISPIELE_MAX]


def _personen_gruppen(kennungen: List[str], nach_kennung: Dict[str, Any],
                      aus: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Nur Gruppenmetadaten je Person (Kennung, Groesse, Zeitraum) — keine Bilddaten.

    Grundlage fuer den Gruppenfilter in der Ansicht „Benannt“: die Oberflaeche baut
    daraus die Auswahlliste und ordnet jede Person ihren Gesichtsgruppen zu.
    """
    eintraege = []
    for k in kennungen:
        gruppe = nach_kennung.get(k)
        if not gruppe:
            continue
        eintraege.append({"kennung": k,
                          "groesse": max(0, int(gruppe.get("groesse") or 0) - len(aus.get(k, ()))),
                          "von": gruppe.get("von"), "bis": gruppe.get("bis")})
    eintraege.sort(key=lambda e: (-e["groesse"], e["kennung"]))
    return eintraege


def personen() -> Dict[str, Any]:
    """Alle benannten Personen: Vorschlaege, Gesichter, Beziehung, Kontakt, Beispiel. Nie ein Wurf."""
    try:
        gruppen, _ = _gruppen_laden()
        namen = bestaetigt_lesen()
        profile = _profile_laden()["profile"]
        aus = ausgeschlossen_lesen()
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    nach_kennung = {g["kennung"]: g for g in gruppen}
    je_name: Dict[str, Dict[str, Any]] = {}
    for k, n in sorted(namen.items()):
        e = je_name.setdefault(n.casefold(), {"name": n, "kennungen": [], "gesichter": 0})
        e["kennungen"].append(k)
        if k in nach_kennung:
            e["gesichter"] += max(0, int(nach_kennung[k].get("groesse") or 0) - len(aus.get(k, ())))
    try:
        zug = zugeordnet_lesen()
    except GruppenFehler:
        zug = {}
    for z in zug.values():                  # von Hand zugeordnet (10.10.2026)
        e = je_name.get(z["name"].casefold())
        if e is not None and z["kennung"] not in e["kennungen"]:
            e["gesichter"] += 1
    liste = []
    alle_namen = [x["name"] for x in je_name.values()]
    for e in je_name.values():
        p = profile.get(_profil_schluessel(profile, e["name"])) or {}
        vorhanden = [nach_kennung[k] for k in e["kennungen"] if k in nach_kennung]
        groesste = max(vorhanden, key=lambda g: int(g.get("groesse") or 0), default=None)
        beispiele = _anzeige_beispiele(groesste, aus.get(groesste["kennung"], set())) if groesste else []
        liste.append({"name": e["name"], "vorschlaege": len(e["kennungen"]), "gesichter": e["gesichter"],
                      "beziehung": p.get("beziehung") or "", "kontakt": bool(p.get("kontakt")),
                      "erinnerungen": sum(1 for x in p.get("notizen") or [] if not x.get("zurueckgenommen")),
                      "gruppen": _personen_gruppen(e["kennungen"], nach_kennung, aus),
                      "beispiel": beispiele[0] if beispiele else None,
                      **_namensfelder(p, e["name"], alle_namen)})
    liste.sort(key=lambda e: (-e["gesichter"], e["name"].casefold()))
    return {"ok": True, "personen": liste}


def person(name: str) -> Dict[str, Any]:
    """Eine benannte Person: ihre Vorschlaege (mit Beispielen) und ihr Profil. Nie ein Wurf."""
    try:
        sauber = name_saeubern(name)
        gruppen, _ = _gruppen_laden()
        namen = bestaetigt_lesen()
        aus = ausgeschlossen_lesen()
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    kennungen = sorted(k for k, n in namen.items() if n.casefold() == sauber.casefold())
    if not kennungen:
        return {"ok": False, "fehler": "Keine benannte Person mit diesem Namen."}
    nach_kennung = {g["kennung"]: g for g in gruppen}
    vorschlaege = []
    for k in kennungen:
        g = nach_kennung.get(k) or {"kennung": k}
        vorschlaege.append({"kennung": k,
                            "groesse": max(0, int(g.get("groesse") or 0) - len(aus.get(k, ()))),
                            "von": g.get("von"), "bis": g.get("bis"),
                            "beispiele": _anzeige_beispiele(g, aus.get(k, set()))})
    vorschlaege.sort(key=lambda v: (-v["groesse"], v["kennung"]))
    echter_name = namen[kennungen[0]]
    prof = profil(echter_name)
    from app.services import lebensabschnitte_service
    abschnitte = lebensabschnitte_service.lebensabschnitte_fuer_person(
        echter_name, vorschlaege=vorschlaege, profil_daten=prof
    )
    return {
        "ok": True,
        "name": echter_name,
        "vorschlaege": vorschlaege,
        "profil": prof,
        "lebensabschnitte": abschnitte.get("phasen", []),
        "lebensabschnitte_aussage": abschnitte.get("aussage", ""),
    }


def umbenennen(alt: str, neu: str) -> Dict[str, Any]:
    """Alle Vorschlaege einer Person umbenennen; gibt es den neuen Namen schon, zusammenfuehren."""
    try:
        alt_s, neu_s = name_saeubern(alt), name_saeubern(neu)
        if alt_s == neu_s:
            raise GruppenFehler("Der Name ist unverändert.")
        with _SCHREIBSPERRE:
            namen = bestaetigt_lesen()
            betroffen = sorted(k for k, n in namen.items() if n.casefold() == alt_s.casefold())
            if not betroffen:
                raise GruppenFehler("Keine benannte Person mit diesem Namen.")
            andere = sorted(k for k, n in namen.items()
                            if n.casefold() == neu_s.casefold() and k not in betroffen)
            eintrag: Dict[str, Any] = {
                "id": uuid.uuid4().hex[:12], "zeit": datetime.now().isoformat(timespec="seconds"),
                "art": "umbenennen", "kennung": betroffen[0], "alt": alt_s, "neu": neu_s,
                "namen_vorher": {k: namen[k] for k in betroffen},
                "paare_neu": {"gleich": [], "verschieden": []},
                "paare_weg": {"gleich": [], "verschieden": []}, "profile_vorher": {}}
            for k in betroffen:
                namen[k] = neu_s
            vorgaben = vorgaben_lesen()
            roh_vorgaben = _json_lesen(_schreibpfad(VORGABEN_DATEINAME), {})
            vorgaben_daten = roh_vorgaben if isinstance(roh_vorgaben, dict) else {}
            zugeordnet_vorher = _zuordnungen_umbenennen(vorgaben_daten, alt_s, neu_s)
            if zugeordnet_vorher:
                eintrag["zugeordnet_vorher"] = zugeordnet_vorher
            if andere:                     # gleicher Name = dieselbe Person (wie beim Benennen)
                paar = _paar(betroffen[0], andere[0])
                if paar in vorgaben["verschieden"]:
                    vorgaben["verschieden"].remove(paar)
                    eintrag["paare_weg"]["verschieden"].append(paar)
                if paar not in vorgaben["gleich"]:
                    vorgaben["gleich"].append(paar)
                    eintrag["paare_neu"]["gleich"].append(paar)
            daten = _profile_laden()
            prof = daten["profile"]
            ak, nk = _profil_schluessel(prof, alt_s), _profil_schluessel(prof, neu_s)
            if ak in prof:
                eintrag["profile_vorher"] = {ak: json.loads(json.dumps(prof[ak])),
                                             nk: json.loads(json.dumps(prof[nk])) if nk in prof else None}
                quelle = prof.pop(ak)
                if nk in prof and nk != ak:           # zusammenfuehren
                    ziel = prof[nk]
                    ziel["beziehung"] = ziel.get("beziehung") or quelle.get("beziehung") or ""
                    ziel["notizen"] = (ziel.get("notizen") or []) + (quelle.get("notizen") or [])
                    if not ziel.get("kontakt") and quelle.get("kontakt"):
                        ziel["kontakt"] = quelle["kontakt"]
                    # Namensfelder von Hand (20.10.2026, Auflage aus der Gegenpruefung):
                    # sie muessen mitwandern, sonst geht eine Handeingabe beim
                    # Zusammenfuehren verloren. Das Ziel behaelt Vorrang, Spitznamen
                    # werden vereinigt. Der Rueckweg ist ein vollstaendiger
                    # Schnappschuss (profile_vorher) und stellt alles wieder her.
                    for feld in ("vorname", "nachname"):
                        if not ziel.get(feld) and quelle.get(feld):
                            ziel[feld] = quelle[feld]
                    spitz = [str(s) for s in ziel.get("spitznamen") or [] if isinstance(s, str)]
                    gesehen = {s.casefold() for s in spitz}
                    for s in quelle.get("spitznamen") or []:
                        if isinstance(s, str) and s.casefold() not in gesehen:
                            gesehen.add(s.casefold())
                            spitz.append(s)
                    if spitz:
                        ziel["spitznamen"] = spitz[:SPITZNAMEN_MAX]
                else:
                    prof[neu_s] = quelle
                _atomar_schreiben(PROFILE_DATEINAME, daten)
            _bestaetigt_schreiben(namen)
            paare_geaendert = (eintrag["paare_neu"]["gleich"] or
                               eintrag["paare_weg"]["verschieden"])
            if paare_geaendert:
                vorgaben_daten["gleich"] = sorted(vorgaben["gleich"])
                vorgaben_daten["verschieden"] = sorted(vorgaben["verschieden"])
            if paare_geaendert or zugeordnet_vorher:
                _atomar_schreiben(VORGABEN_DATEINAME, vorgaben_daten)
            _protokoll_anhaengen(eintrag)
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    except OSError as fehler:
        logger.error("Umbenennen fehlgeschlagen: %s", fehler)
        return {"ok": False, "fehler": f"Speichern fehlgeschlagen ({fehler.__class__.__name__})."}
    erg = person(neu_s)
    erg["zusammengefuehrt"] = bool(andere)
    return erg


def loesen(kennung: str) -> Dict[str, Any]:
    """Einen Vorschlag von seiner Person loesen („das ist doch nicht X") - er ist wieder offen."""
    try:
        with _SCHREIBSPERRE:
            namen = bestaetigt_lesen()
            if kennung not in namen:
                raise GruppenFehler("Dieser Vorschlag ist nicht benannt.")
            vorgaben = vorgaben_lesen()
            eintrag: Dict[str, Any] = {
                "id": uuid.uuid4().hex[:12], "zeit": datetime.now().isoformat(timespec="seconds"),
                "art": "loesen", "kennung": kennung, "namen_vorher": {kennung: namen[kennung]},
                "paare_neu": {"gleich": [], "verschieden": []},
                "paare_weg": {"gleich": [p for p in vorgaben["gleich"] if kennung in p],
                              "verschieden": []}}
            # „gleich"-Paare mit diesem Vorschlag wuerden den Namen sonst wieder zurueckbringen.
            vorgaben["gleich"] = [p for p in vorgaben["gleich"] if kennung not in p]
            name = namen.pop(kennung)
            _bestaetigt_schreiben(namen)
            if eintrag["paare_weg"]["gleich"]:
                _vorgaben_schreiben(vorgaben)
            _protokoll_anhaengen(eintrag)
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    except OSError as fehler:
        logger.error("Loesen fehlgeschlagen: %s", fehler)
        return {"ok": False, "fehler": f"Speichern fehlgeschlagen ({fehler.__class__.__name__})."}
    return {"ok": True, "kennung": kennung, "name": name}


def aufloesen(kennung: str, trocken: bool = False) -> Dict[str, Any]:
    """Eine zugeordnete Gruppe aus der Gruppenliste nehmen (To-do Punkt 14). Nie ein Wurf.

    „Auflösen" entfernt **nur den Gruppeneintrag**: die Kennung kommt in die
    Stand-Liste ``aufgeloest`` (genau wie ``spaeter``/``unbekannt``). Bilder,
    Gesichter und Zuordnungen bleiben unveraendert — die Gesichter bleiben der
    Person zugeordnet. Rueckholbar mit :func:`rueckgaengig` oder ``art="offen"``.

    ``trocken=True`` zaehlt nur (Gruppe, Person, Gesichter) und schreibt nichts —
    die Oberflaeche zeigt die Zahl vor dem Schreiben. Erlaubt ist das nur fuer
    Gruppen, die schon einer Person zugeordnet sind.
    """
    try:
        sauber = str(kennung or "").strip()
        if not sauber:
            raise GruppenFehler("Bitte eine Gruppe angeben.")
        gruppen, _ = _gruppen_laden()
        namen = bestaetigt_lesen()
        st = _stand_lesen()
        nach_kennung = {g["kennung"]: g for g in gruppen}
        gruppe = nach_kennung.get(sauber)
        if gruppe is None:
            raise GruppenFehler("Diese Gruppe gibt es nicht (mehr).")
        name = namen.get(sauber)
        if not name:
            raise GruppenFehler("Nur einer Person zugeordnete Gruppen lassen sich auflösen.")
        aus = ausgeschlossen_lesen().get(sauber, set())
        gesichter = max(0, int(gruppe.get("groesse") or 0) - len(aus))
        schon = sauber in st["aufgeloest"]
        bericht: Dict[str, Any] = {
            "ok": True, "kennung": sauber, "name": name, "gesichter": gesichter,
            "gruppen": 0 if schon else 1, "schon_aufgeloest": schon,
            "trocken": bool(trocken),
        }
        if trocken or schon:            # nichts zu tun: nichts schreiben (idempotent)
            return bericht
        with _SCHREIBSPERRE:
            eintrag = _antwort_anwenden(sauber, "aufloesen", None, None)
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    except OSError as fehler:
        logger.error("Aufloesen fehlgeschlagen: %s", fehler)
        return {"ok": False, "fehler": f"Speichern fehlgeschlagen ({fehler.__class__.__name__})."}
    bericht["aufgeloest"] = len(eintrag.get("aufgeloest") or [])
    logger.info("Gruppen-Quiz: Gruppe %s aufgeloest (%s Gesichter bleiben %s zugeordnet)",
                sauber, gesichter, name)
    return bericht


def andocken(trocken: bool = True,
             min_sicherheit: float = 0.85,
             kennungen: Optional[List[str]] = None,
             ziel_name: Optional[str] = None) -> Dict[str, Any]:
    """Dockt offene Gruppen an passende Lebensabschnitte bekannter Personen an (30.10.2026).

    Im Trockenmodus (trocken=True, Standard): Zaehlt nur Kandidaten und Gesichter.
    Im Schreibmodus (trocken=False): Wendet die Zuordnung ueber _antwort_anwenden an (protokolliert, rueckgaengig machbar).
    """
    try:
        from app.services import lebensabschnitte_service
        kandidaten = lebensabschnitte_service.andocken_kandidaten(
            min_sicherheit=min_sicherheit,
            kennungen=kennungen,
            ziel_name=ziel_name,
        )
        if trocken:
            return {
                "ok": True,
                "trocken": True,
                "anzahl": len(kandidaten),
                "gesichter": sum(k["groesse"] for k in kandidaten),
                "kandidaten": kandidaten,
            }

        with _SCHREIBSPERRE:
            zugeordnet: List[str] = []
            for k in kandidaten:
                try:
                    _antwort_anwenden(kennung=k["kennung"], art="name", name=k["name"], ziel=None)
                    zugeordnet.append(k["kennung"])
                except Exception as e:
                    logger.warning("Andocken fuer %s fehlgeschlagen: %s", k["kennung"], e)

            return {
                "ok": True,
                "trocken": False,
                "anzahl": len(zugeordnet),
                "gesichter": sum(k["groesse"] for k in kandidaten if k["kennung"] in zugeordnet),
                "zugeordnet": zugeordnet,
                "kandidaten": kandidaten,
            }
    except Exception as fehler:
        logger.error("Andocken fehlgeschlagen: %s", fehler, exc_info=True)
        return {"ok": False, "fehler": str(fehler)}


# ── Antworten ────────────────────────────────────────────────────────────────

def antworten(kennung: str, art: str, name: Optional[str] = None,
              ziel: Optional[str] = None, beziehung: Optional[str] = None,
              notiz: Optional[str] = None, kontakt_id: Optional[str] = None) -> Dict[str, Any]:
    """Eine Antwort speichern und die naechste Gruppe liefern. Nie ein Wurf.

    Beim Benennen (``art="name"``) koennen ``beziehung`` und ``notiz`` mitkommen —
    sie landen im Profil der Person (``personen_profile.json``). ``kontakt_id``
    verknuepft das Profil mit einem Telefonbuch-Kontakt (ohne Namen gilt dessen Name).
    """
    try:
        with _SCHREIBSPERRE:
            eintrag = _antwort_anwenden(kennung, art, name, ziel, beziehung, notiz, kontakt_id)
        logger.info("Gruppen-Quiz: %s fuer %s gespeichert", art, kennung)
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    except OSError as fehler:
        logger.error("Gruppen-Quiz: Schreiben fehlgeschlagen: %s", fehler)
        return {"ok": False, "fehler": f"Speichern fehlgeschlagen ({fehler.__class__.__name__})."}
    weiter = naechste()
    weiter["gespeichert"] = {"kennung": kennung, "art": art, "name": eintrag.get("name"),
                             "notiz": bool((eintrag.get("profil") or {}).get("notiz_id")),
                             "kontakt": "kontakt_vorher" in (eintrag.get("profil") or {}),
                             "weitere": len([k for k in eintrag["namen_vorher"] if k != kennung])}
    return weiter


def _antwort_anwenden(kennung: str, art: str, name: Optional[str],
                      ziel: Optional[str], beziehung: Optional[str] = None,
                      notiz: Optional[str] = None,
                      kontakt_id: Optional[str] = None) -> Dict[str, Any]:
    if art not in ARTEN:
        raise GruppenFehler(f"Unbekannte Antwort: {art!r}.")
    gruppen, _ = _gruppen_laden()
    kennungen = {g["kennung"] for g in gruppen}
    if kennung not in kennungen:
        raise GruppenFehler(f"Gruppe {kennung!r} ist nicht (mehr) in der Gruppen-Datei.")
    if art in ("gleich", "verschieden"):
        if not ziel or ziel not in kennungen or ziel == kennung:
            raise GruppenFehler("Bitte die Vergleichsgruppe angeben.")

    namen = bestaetigt_lesen()
    vorgaben = vorgaben_lesen()
    st = _stand_lesen()
    if art == "offen" and kennung in namen and kennung not in st["aufgeloest"]:
        raise GruppenFehler("Benannte Gruppen können nicht zurück zu Offen gesetzt werden.")
    eintrag: Dict[str, Any] = {
        "id": uuid.uuid4().hex[:12], "zeit": datetime.now().isoformat(timespec="seconds"),
        "kennung": kennung, "art": art, "ziel": ziel,
        "namen_vorher": {}, "paare_neu": {"gleich": [], "verschieden": []},
        "paare_weg": {"gleich": [], "verschieden": []},
        "listen_vorher": {liste: kennung in st[liste] for liste in STAND_LISTEN},
        # Position in der jeweiligen Liste (nur wenn enthalten): damit stellt
        # Rueckgaengig auch die Reihenfolge wieder her. Eintraege ohne diesen
        # Schluessel (aeltere Protokolle) wandern wie bisher ans Listenende.
        "listen_position": {liste: st[liste].index(kennung)
                            for liste in STAND_LISTEN if kennung in st[liste]},
    }

    def name_setzen(k: str, n: str) -> None:
        if namen.get(k) != n:
            eintrag["namen_vorher"].setdefault(k, namen.get(k))
            namen[k] = n

    def paar_dazu(art_paar: str, a: str, b: str) -> None:
        p = _paar(a, b)
        gegen = "verschieden" if art_paar == "gleich" else "gleich"
        if p in vorgaben[gegen]:
            vorgaben[gegen].remove(p)
            eintrag["paare_weg"][gegen].append(p)
        if p not in vorgaben[art_paar]:
            vorgaben[art_paar].append(p)
            eintrag["paare_neu"][art_paar].append(p)

    kontakt = None
    if art == "name" and kontakt_id:
        kontakt = _kontakte_laden().get(str(kontakt_id).strip())
        if not kontakt:
            raise GruppenFehler("Kontakt nicht (mehr) im Telefonbuch-Auszug.")
        if not (name or "").strip():
            name = kontakt["name"]

    if art == "name":
        sauber = name_saeubern(name)
        eintrag["name"] = sauber
        gleichnamig = sorted(k for k, n in namen.items()
                             if k != kennung and n.casefold() == sauber.casefold())
        name_setzen(kennung, sauber)
        if gleichnamig:
            paar_dazu("gleich", kennung, gleichnamig[0])
        b = text_saeubern(beziehung, BEZIEHUNG_MAX)
        n = text_saeubern(notiz, NOTIZ_MAX, zeilen=True)
        if b or n or kontakt:
            profile = _profile_laden()
            eintrag["profil"] = _profil_ergaenzen(profile, sauber, b, n, kennung, "quiz",
                                                  dict(kontakt) if kontakt else None)
    elif art == "gleich":
        andere = str(ziel)          # oben geprueft: vorhanden und gueltig
        paar_dazu("gleich", kennung, andere)
        if namen.get(andere) and not namen.get(kennung):
            name_setzen(kennung, namen[andere])
            eintrag["name"] = namen[andere]
        elif namen.get(kennung) and not namen.get(andere):
            name_setzen(andere, namen[kennung])
    elif art == "verschieden":
        paar_dazu("verschieden", kennung, str(ziel))

    if art in ("name", "gleich"):
        # Name an alle per „gleich" verbundenen, noch unbenannten Vorschlaege
        # weitergeben (auch mehrstufig). Vorhandene Namen bleiben unberuehrt;
        # jede Aenderung steht in namen_vorher, Rueckgaengig nimmt sie mit.
        bekannt = namen.get(kennung) or (namen.get(str(ziel)) if art == "gleich" else None)
        if bekannt:
            for k in _gleich_komponente(kennung, vorgaben["gleich"]):
                if not namen.get(k):
                    name_setzen(k, bekannt)
        st["spaeter"] = [k for k in st["spaeter"] if k != kennung]
        st["unbekannt"] = [k for k in st["unbekannt"] if k != kennung]
        # Automatisch aufloesen (Sebastian, 16.10.2026: „Die Gruppen sind nicht
        # wichtig nach der Zuordnung."): jede Gruppe, die diese Antwort benannt
        # hat, verschwindet aus der Gruppenliste — die Gesichter bleiben der
        # Person zugeordnet. Nur die Mitgliedschaft wird vermerkt, nichts geloescht.
        for k in sorted(eintrag["namen_vorher"]):
            if k not in st["aufgeloest"]:
                st["aufgeloest"].append(k)
        eintrag["aufgeloest"] = sorted(eintrag["namen_vorher"])
    elif art == "spaeter":
        st["spaeter"] = [k for k in st["spaeter"] if k != kennung] + [kennung]
    elif art == "unbekannt":
        if kennung not in st["unbekannt"]:
            st["unbekannt"].append(kennung)
        st["spaeter"] = [k for k in st["spaeter"] if k != kennung]
    elif art == "offen":
        # Reaktivieren: zurueck in die Gruppenliste — bei einer aufgeloesten,
        # zugeordneten Gruppe ist genau das der Umkehrweg (die Gesichter bleiben).
        st["spaeter"] = [k for k in st["spaeter"] if k != kennung]
        st["unbekannt"] = [k for k in st["unbekannt"] if k != kennung]
        st["aufgeloest"] = [k for k in st["aufgeloest"] if k != kennung]
    elif art == "aufloesen":
        if kennung not in namen:
            raise GruppenFehler("Nur einer Person zugeordnete Gruppen lassen sich auflösen.")
        if kennung not in st["aufgeloest"]:
            st["aufgeloest"].append(kennung)
        st["spaeter"] = [k for k in st["spaeter"] if k != kennung]
        st["unbekannt"] = [k for k in st["unbekannt"] if k != kennung]
        eintrag["aufgeloest"] = [kennung]

    if eintrag["namen_vorher"]:
        _bestaetigt_schreiben(namen)
    if any(eintrag["paare_neu"].values()) or any(eintrag["paare_weg"].values()):
        _vorgaben_schreiben(vorgaben)
    if eintrag.get("profil"):
        _atomar_schreiben(PROFILE_DATEINAME, profile)
    _atomar_schreiben(STAND_DATEINAME, st)
    _protokoll_anhaengen(eintrag)
    return eintrag


ZURUECKNEHMBAR = ARTEN + ("ausschliessen", "zuordnen", "umbenennen", "loesen", "profil", "bild_rahmen")


def _offene_eintraege() -> List[Dict[str, Any]]:
    """Protokolleintraege, die sich zuruecknehmen lassen und noch nicht zurueckgenommen sind (alt -> neu)."""
    eintraege = _protokoll_lesen()
    erledigt = {e.get("bezug") for e in eintraege if e.get("art") == "rueckgaengig"}
    return [e for e in eintraege if e.get("art") in ZURUECKNEHMBAR and e.get("id") not in erledigt]


def rueckgaengig() -> Dict[str, Any]:
    """Die letzte (noch nicht zurueckgenommene) Antwort zuruecknehmen.

    Gehoert der letzte offene Eintrag zu einem ``bild-rahmen``-Aufruf (gleiche ``aktion``),
    nimmt EIN Rueckgaengig alle offenen Eintraege dieser ``aktion`` in umgekehrter Reihenfolge
    zurueck (zuerst ``zuordnen``/``ausschliessen``, zuletzt ``bild_rahmen``) — kein halber Zustand.
    """
    try:
        with _SCHREIBSPERRE:
            offen = _offene_eintraege()
            if not offen:
                return {"ok": False, "fehler": "Es gibt nichts zurückzunehmen."}
            letzte = offen[-1]
            aktion = letzte.get("aktion")
            ids = ([e.get("id") for e in reversed(offen) if e.get("aktion") == aktion]
                   if isinstance(aktion, str) and aktion else [letzte.get("id")])
    except OSError as fehler:
        logger.error("Gruppen-Quiz: Rueckgaengig fehlgeschlagen: %s", fehler)
        return {"ok": False, "fehler": f"Zurücknehmen fehlgeschlagen ({fehler.__class__.__name__})."}
    ergebnis: Dict[str, Any] = {}
    erstes: Any = None
    for zid in ids:
        ergebnis = _rueckgaengig_eintrag(zid)
        if ergebnis.pop("_fehler", False):
            if erstes is not None:
                ergebnis["teilweise"] = True
                ergebnis["fehler"] = "Nur teilweise zurückgenommen: " + str(ergebnis.get("fehler") or "")
            return ergebnis
        if erstes is None:
            erstes = ergebnis.get("zurueckgenommen")
    if len(ids) > 1 and isinstance(erstes, dict):
        ergebnis["zurueckgenommen"] = dict(erstes, eintraege=len(ids), aktion=aktion)
    return ergebnis


def _rueckgaengig_eintrag(ziel_id: Any) -> Dict[str, Any]:
    """Genau EINEN offenen Protokolleintrag zuruecknehmen (``rueckgaengig`` ruft es je Eintrag)."""
    try:
        with _SCHREIBSPERRE:
            letzte = next((e for e in _offene_eintraege() if e.get("id") == ziel_id), None)
            if letzte is None:
                return {"ok": False, "fehler": "Es gibt nichts zurückzunehmen.", "_fehler": True}
            if letzte.get("art") == "bild_rahmen":
                _bild_rahmen_zuruecknehmen(letzte)
                _protokoll_anhaengen({"id": uuid.uuid4().hex[:12],
                                      "zeit": datetime.now().isoformat(timespec="seconds"),
                                      "art": "rueckgaengig", "bezug": letzte.get("id"),
                                      "kennung": letzte.get("kennung")})
                weiter = naechste()
                weiter["zurueckgenommen"] = {"kennung": letzte.get("kennung"), "art": "bild_rahmen",
                                             "fileid": letzte.get("fileid")}
                return weiter
            if letzte.get("art") == "zuordnen":
                _zuordnen_zuruecknehmen(letzte)
                _protokoll_anhaengen({"id": uuid.uuid4().hex[:12],
                                      "zeit": datetime.now().isoformat(timespec="seconds"),
                                      "art": "rueckgaengig", "bezug": letzte.get("id"),
                                      "kennung": letzte.get("kennung")})
                weiter = naechste()
                weiter["zurueckgenommen"] = {"kennung": letzte.get("kennung"), "art": "zuordnen",
                                             "name": letzte.get("name"),
                                             "gesichter": len(letzte.get("gesichter") or [])}
                return weiter
            if letzte.get("art") == "ausschliessen":
                roh = _json_lesen(_schreibpfad(VORGABEN_DATEINAME), {})
                daten = roh if isinstance(roh, dict) else {}
                je_kennung = letzte.get("je_kennung")
                if isinstance(je_kennung, dict) and je_kennung:
                    weg = {(str(k), g) for k, gs in je_kennung.items() for g in gs or []}
                else:
                    weg = {(str(letzte.get("kennung")), g) for g in letzte.get("gesichter") or []}
                daten["ausgeschlossen"] = [
                    e for e in daten.get("ausgeschlossen") or []
                    if not (isinstance(e, dict) and (str(e.get("kennung")),
                            f"{e.get('bild_id')}:{int(e.get('index') or 0)}") in weg)]
                # B1: feste Zuordnungen, die das Entfernen aufgehoben hatte, kommen zurueck.
                wieder = [e for e in letzte.get("vorher_zugeordnet") or [] if isinstance(e, dict)]
                if wieder:
                    zug_liste = daten.get("zugeordnet") if isinstance(daten.get("zugeordnet"), list) else []
                    zug_liste.extend(e for e in wieder if e not in zug_liste)
                    daten["zugeordnet"] = zug_liste
                _atomar_schreiben(VORGABEN_DATEINAME, daten)
                _protokoll_anhaengen({"id": uuid.uuid4().hex[:12],
                                      "zeit": datetime.now().isoformat(timespec="seconds"),
                                      "art": "rueckgaengig", "bezug": letzte.get("id"),
                                      "kennung": letzte.get("kennung")})
                weiter = naechste()
                weiter["zurueckgenommen"] = {"kennung": letzte.get("kennung"), "art": "ausschliessen",
                                             "gesichter": len(letzte.get("gesichter") or [])}
                return weiter
            namen = bestaetigt_lesen()
            vorgaben = vorgaben_lesen()
            roh_vorgaben = _json_lesen(_schreibpfad(VORGABEN_DATEINAME), {})
            vorgaben_daten = roh_vorgaben if isinstance(roh_vorgaben, dict) else {}
            zugeordnet_geaendert = _zuordnungen_wiederherstellen(
                vorgaben_daten, letzte.get("zugeordnet_vorher"), str(letzte.get("neu") or ""))
            st = _stand_lesen()
            for k, vorher in (letzte.get("namen_vorher") or {}).items():
                if vorher:
                    namen[k] = vorher
                else:
                    namen.pop(k, None)
            for art_paar in ("gleich", "verschieden"):
                for p in (letzte.get("paare_neu") or {}).get(art_paar) or []:
                    if sorted(p) in vorgaben[art_paar]:
                        vorgaben[art_paar].remove(sorted(p))
                for p in (letzte.get("paare_weg") or {}).get(art_paar) or []:
                    if sorted(p) not in vorgaben[art_paar]:
                        vorgaben[art_paar].append(sorted(p))
            kennung = str(letzte.get("kennung") or "")
            positionen = letzte.get("listen_position")
            if not isinstance(positionen, dict):
                positionen = {}
            for liste, war in (letzte.get("listen_vorher") or {}).items():
                if liste not in st:
                    continue
                ohne = [k for k in st[liste] if k != kennung]
                position = positionen.get(liste)
                if war and isinstance(position, int) and not isinstance(position, bool) and position >= 0:
                    ohne.insert(min(position, len(ohne)), kennung)   # alte Reihenfolge
                    st[liste] = ohne
                else:
                    st[liste] = ohne + [kennung] if war else ohne
            if letzte.get("profile_vorher"):
                daten = _profile_laden()
                for schluessel, alt_profil in letzte["profile_vorher"].items():
                    if alt_profil is None:
                        daten["profile"].pop(schluessel, None)
                    else:
                        daten["profile"][schluessel] = alt_profil
                if letzte.get("neu") and letzte.get("neu") not in letzte["profile_vorher"]:
                    daten["profile"].pop(letzte["neu"], None)
                _atomar_schreiben(PROFILE_DATEINAME, daten)
            pr = letzte.get("profil") or {}
            if pr:
                daten = _profile_laden()
                p = daten["profile"].get(pr.get("name") or "")
                if p is not None:
                    if "beziehung_vorher" in pr:
                        p["beziehung"] = pr["beziehung_vorher"]
                    if "kontakt_vorher" in pr:
                        if pr["kontakt_vorher"]:
                            p["kontakt"] = pr["kontakt_vorher"]
                        else:
                            p.pop("kontakt", None)
                    # Namensfelder von Hand (20.10.2026): genauen Vorher-Stand
                    # wiederherstellen, fehlende Schluessel wieder entfernen.
                    for feld, wert in (pr.get("felder_vorher") or {}).items():
                        if wert is None:
                            p.pop(feld, None)
                        else:
                            p[feld] = wert
                    for notiz_eintrag in p.get("notizen") or []:
                        if notiz_eintrag.get("id") == pr.get("notiz_id"):
                            notiz_eintrag["zurueckgenommen"] = True
                    _atomar_schreiben(PROFILE_DATEINAME, daten)
            if letzte.get("namen_vorher"):
                _bestaetigt_schreiben(namen)
            paare_geaendert = (any((letzte.get("paare_neu") or {}).values()) or
                               any((letzte.get("paare_weg") or {}).values()))
            if paare_geaendert:
                vorgaben_daten["gleich"] = sorted(vorgaben["gleich"])
                vorgaben_daten["verschieden"] = sorted(vorgaben["verschieden"])
            if paare_geaendert or zugeordnet_geaendert:
                _atomar_schreiben(VORGABEN_DATEINAME, vorgaben_daten)
            _atomar_schreiben(STAND_DATEINAME, st)
            _protokoll_anhaengen({"id": uuid.uuid4().hex[:12],
                                  "zeit": datetime.now().isoformat(timespec="seconds"),
                                  "art": "rueckgaengig", "bezug": letzte.get("id"),
                                  "kennung": kennung})
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler), "_fehler": True}
    except OSError as fehler:
        logger.error("Gruppen-Quiz: Rueckgaengig fehlgeschlagen: %s", fehler)
        return {"ok": False, "fehler": f"Zurücknehmen fehlgeschlagen ({fehler.__class__.__name__})."
                , "_fehler": True}
    weiter = naechste()
    weiter["zurueckgenommen"] = {"kennung": kennung, "art": letzte.get("art")}
    if letzte.get("alt"):                   # Umbenennen: dorthin zurueck, wo die Person jetzt heisst
        weiter["zurueckgenommen"]["name"] = letzte["alt"]
    return weiter


# ── Register: Bilder mit Personen ────────────────────────────────────────────

def _zuordnung_laden(pfad: str) -> Dict[str, Dict[str, Any]]:
    """``gesicht_zuordnung.jsonl`` -> {Bild/Video: {kennungen, aufnahme, art}}."""
    medien: Dict[str, Dict[str, Any]] = {}
    with open(pfad, encoding="utf-8") as datei:
        for zeile in datei:
            try:
                z = json.loads(zeile)
            except ValueError:
                continue
            if not isinstance(z, dict) or not z.get("kennung"):
                continue
            video = z.get("video_id")
            schluessel = str(video) if video else str(z.get("bild_id") or "")
            if not schluessel:
                continue
            m = medien.setdefault(schluessel, {"kennungen": set(), "aufnahme": None,
                                               "art": "video" if video else "bild"})
            m["kennungen"].add(z["kennung"])
            if z.get("aufnahme") and not m["aufnahme"]:
                m["aufnahme"] = str(z["aufnahme"])[:19]
    return medien


def _handy_namen(korr: Dict[str, Dict[str, Any]]) -> set:
    """Alle handy-eigenen Namen (casefold) aus den Bild-Korrekturen."""
    return {r["name"].casefold() for e in korr.values() for r in e["rahmen"].values() if r["name"]}


def _medien_mit_korrekturen(medien: Dict[str, Dict[str, Any]], korr: Dict[str, Dict[str, Any]]):
    """Die Medien des Registers plus Bilder, die nur Korrekturen kennen (reines Hand-Gesicht)."""
    yield from medien.items()
    for fileid in korr:
        if fileid not in medien:
            yield fileid, {"kennungen": set(), "aufnahme": None, "art": "bild"}


def bilder_mit(namen: Iterable[str], modus: str = "alle", limit: int = 100) -> Dict[str, Any]:
    """Fotos/Videos mit diesen Personen. ``modus``: alle | eine | genau. Nie ein Wurf.

    ``genau``: die gefragten Personen sind dabei und KEINE weitere benannte
    Person (unbenannte Gesichter zaehlen nicht — die Menge im Hintergrund).
    """
    gefragt = [n.strip() for n in namen if isinstance(n, str) and n.strip()]
    if not gefragt:
        return {"ok": False, "fehler": "Bitte mindestens einen Namen angeben."}
    if modus not in MODI:
        return {"ok": False, "fehler": f"Unbekannter Modus {modus!r} (alle, eine, genau)."}
    limit = max(1, min(int(limit or 100), BILDER_LIMIT_MAX))
    pfad = _lesepfad(ZUORDNUNG_DATEINAME)
    if not pfad:
        return {"ok": False, "fehler": FEHLT_HINWEIS}
    try:
        bestaetigt = bestaetigt_lesen()
        medien = _gemerkt(pfad, _zuordnung_laden)
        aus_paare = {(k, gid.split(":")[0]) for k, gids in ausgeschlossen_lesen().items() for gid in gids}
        zug_bild = _zugeordnet_je_bild(zugeordnet_lesen())
        korr = _korrekturen_lesen()
        q = _sicht_quellen(korr) if korr else {}
    except (GruppenFehler, OSError) as fehler:
        return {"ok": False, "fehler": str(fehler)}
    person_von: Dict[str, str] = {k: n.casefold() for k, n in bestaetigt.items()}
    gesucht = {n.casefold() for n in gefragt}
    bekannt = set(person_von.values()) | _handy_namen(korr)
    unbekannt = sorted(n for n in gefragt if n.casefold() not in bekannt)
    treffer = []
    for schluessel, m in _medien_mit_korrekturen(medien, korr):
        if schluessel in korr:                              # Bild mit Korrekturen: zusammengefuehrte Sicht
            personen = set(_sicht_namen(schluessel, q)[0])
        else:
            personen = {person_von[k] for k in m["kennungen"]
                        if k in person_von and (k, schluessel) not in aus_paare}
            personen |= set(zug_bild.get(schluessel, {}))   # von Hand zugeordnet
        if modus == "alle":
            passt = gesucht <= personen
        elif modus == "eine":
            passt = bool(gesucht & personen)
        else:
            passt = personen == gesucht
        if passt:
            treffer.append({"fileid": schluessel, "art": m["art"], "aufnahme": m["aufnahme"]})
    treffer.sort(key=lambda t: (t["aufnahme"] or "", t["fileid"]), reverse=True)
    return {
        "ok": True, "namen": gefragt, "modus": modus,
        "anzahl": len(treffer),
        "bilder": sum(1 for t in treffer if t["art"] == "bild"),
        "videos": sum(1 for t in treffer if t["art"] == "video"),
        "treffer": treffer[:limit],
        "unbekannte_namen": unbekannt,
    }


def bild_kennungen_person(name: str) -> Dict[str, Any]:
    """Alle Bild/Video-Kennungen mit dieser Person — ohne Obergrenze.

    Dieselbe Quelle wie :func:`bilder_mit` (``gesicht_zuordnung.jsonl`` +
    bestätigte Namen), aber **kein Limit** — für Verknüpfungen (Anlässe eines
    Menschen) braucht es die volle Menge, nicht nur die 500 neuesten.
    Ausschluss und Handzuordnung zählen wie im Register. Nie ein Wurf.
    """
    person = name_saeubern(name)
    if not person:
        return {"ok": False, "fehler": "Bitte den Namen angeben."}
    pfad = _lesepfad(ZUORDNUNG_DATEINAME)
    if not pfad:
        return {"ok": False, "fehler": FEHLT_HINWEIS}
    try:
        bestaetigt = bestaetigt_lesen()
        medien = _gemerkt(pfad, _zuordnung_laden)
        aus_paare = {(k, gid.split(":")[0]) for k, gids in ausgeschlossen_lesen().items() for gid in gids}
        zug_bild = _zugeordnet_je_bild(zugeordnet_lesen())
        korr = _korrekturen_lesen()
        q = _sicht_quellen(korr) if korr else {}
    except (GruppenFehler, OSError) as fehler:
        return {"ok": False, "fehler": str(fehler)}
    person_von: Dict[str, str] = {k: n.casefold() for k, n in bestaetigt.items()}
    gesucht = person.casefold()
    if gesucht not in set(person_von.values()) | _handy_namen(korr):
        return {"ok": True, "name": person, "kennungen": [], "unbekannt": True}
    kennungen: List[int] = []
    for schluessel, m in _medien_mit_korrekturen(medien, korr):
        if schluessel in korr:                              # Bild mit Korrekturen: zusammengefuehrte Sicht
            personen = set(_sicht_namen(schluessel, q)[0])
        else:
            personen = {person_von[k] for k in m["kennungen"]
                        if k in person_von and (k, schluessel) not in aus_paare}
            personen |= set(zug_bild.get(schluessel, {}))
        if gesucht in personen and schluessel.isdigit():
            kennungen.append(int(schluessel))
    kennungen.sort(reverse=True)
    return {"ok": True, "name": person, "kennungen": kennungen, "unbekannt": False}


PERSONEN_BILDER_MAX = 2000


def personen_auf_bildern(fileids: Any) -> Dict[str, Any]:
    """Wer ist auf diesen Bildern? Fuer das Erzaehlen (06.10.2026). Nie ein Wurf.

    Je Bild die erkannten Personen: benannt (Name aus ``personen_bestaetigt.json``,
    mehrere Vorschlaege mit demselben Namen zaehlen einmal) oder noch ohne Namen
    (Kennung). Ausgeschlossene Gesichter fehlen wie im Register; als „kenne ich
    nicht" markierte Gruppen (fremde Menge) zaehlen nicht mit. Dazu die
    Zusammenfassung ueber alle Bilder: Name -> Zahl der Bilder.
    """
    gefragt: List[str] = []
    for f in fileids if isinstance(fileids, (list, tuple)) else []:
        s = str(f).strip() if f is not None else ""
        if s and s not in gefragt:
            gefragt.append(s)
    gefragt = gefragt[:PERSONEN_BILDER_MAX]
    pfad = _lesepfad(ZUORDNUNG_DATEINAME)
    if not pfad:
        return {"ok": False, "fehler": FEHLT_HINWEIS}
    try:
        namen = bestaetigt_lesen()
        medien = _gemerkt(pfad, _zuordnung_laden)
        aus_paare = {(k, gid.split(":")[0]) for k, gids in ausgeschlossen_lesen().items() for gid in gids}
        zug_bild = _zugeordnet_je_bild(zugeordnet_lesen())
        fremd = set(_stand_lesen()["unbekannt"])
        korr = _korrekturen_lesen()
        q = _sicht_quellen(korr) if korr else {}
    except (GruppenFehler, OSError) as fehler:
        return {"ok": False, "fehler": str(fehler)}
    bilder: Dict[str, Dict[str, Any]] = {}
    je_name: Dict[str, Dict[str, Any]] = {}
    ohne_namen: set = set()
    bilder_ohne_namen = 0
    for fileid in gefragt:
        m = medien.get(fileid)
        if fileid in korr:                  # Bild mit Korrekturen: dieselbe Sicht wie bild-gesichter
            benannt, unbenannt = _sicht_namen(fileid, q)
        elif not m:
            continue
        else:
            benannt = {}
            unbenannt = []
            for k in sorted(m["kennungen"]):
                if (k, fileid) in aus_paare or k in fremd:
                    continue
                if k in namen:
                    benannt.setdefault(namen[k].casefold(), namen[k])
                else:
                    unbenannt.append(k)
            for schl, n in zug_bild.get(fileid, {}).items():      # von Hand zugeordnet
                benannt.setdefault(schl, n)
        if not benannt and not unbenannt:
            continue
        liste = sorted(benannt.values(), key=str.casefold)
        bilder[fileid] = {"namen": liste, "ohne_namen": unbenannt}
        for n in liste:
            e = je_name.setdefault(n.casefold(), {"name": n, "bilder": 0})
            e["bilder"] += 1
        ohne_namen.update(unbenannt)
        bilder_ohne_namen += 1 if unbenannt else 0
    benannt_liste = sorted(je_name.values(), key=lambda e: (-e["bilder"], e["name"].casefold()))
    return {"ok": True, "gesamt": len(gefragt), "mit_personen": len(bilder), "bilder": bilder,
            "benannt": benannt_liste,
            "ohne_namen": {"personen": len(ohne_namen), "bilder": bilder_ohne_namen}}
