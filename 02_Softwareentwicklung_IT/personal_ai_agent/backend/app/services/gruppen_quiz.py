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
  ``rueckgaengig()`` nimmt die letzte Antwort zurueck (Fehltipp am Handy).

Ablage — genau die Formate, die ``personen_gruppieren.py`` liest
(``bestaetigt_lesen`` / ``vorgaben_lesen``), damit der naechste PC-Lauf die
Namen und Vorgaben uebernimmt:
  * ``personen_bestaetigt.json`` ``{"bestaetigt": {"Person_1003": "Name"}}``
  * ``personen_vorgaben.json``   ``{"gleich": [[a, b]], "verschieden": [[a, b]]}``
  * ``gruppen_quiz_stand.json``  ``{"spaeter": [...], "unbekannt": [...]}``
  * ``gruppen_antworten.jsonl``  Protokoll, nur anhaengend (Grundlage fuer
                                 Rueckgaengig und Nachvollziehbarkeit).
Vor jedem Schreiben wird die alte Fassung als ``*.vorher`` gesichert; geschrieben
wird atomar (temp-Datei + ``os.replace``). Es wird nie etwas geloescht.

Register: ``bilder_mit(namen, modus)`` beantwortet „Bilder mit Leon und/oder
Tim" ueber ``gesicht_zuordnung.jsonl`` + die bestaetigten Namen — am Handy, ohne
Rueckweg zum PC.

Ort: ``~/foto_sortierung`` (uebersteuerbar mit ``GRUPPEN_QUIZ_BASIS``). Gelesen
wird zuerst ``personen_gruppen/<datei>`` (so schreibt der PC), sonst
``<datei>`` direkt im Ordner (so legt die Uebergabe am Handy sie ab).
Keine Vektoren, kein Netz, kein Modellaufruf — nur lokale Dateien.
"""
from __future__ import annotations

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
BESTAETIGT_DATEINAME = "personen_bestaetigt.json"
VORGABEN_DATEINAME = "personen_vorgaben.json"
STAND_DATEINAME = "gruppen_quiz_stand.json"
PROTOKOLL_DATEINAME = "gruppen_antworten.jsonl"
PROFILE_DATEINAME = "personen_profile.json"
KONTAKTE_DATEINAME = "kontakte.json"   # Telefonbuch-Auszug (tools/handy/kontakte_aufs_handy.py)

ARTEN = ("name", "gleich", "verschieden", "spaeter", "unbekannt")
MODI = ("alle", "eine", "genau")
NAME_MAX = 60
BEZIEHUNG_MAX = 80
NOTIZ_MAX = 4000
BEISPIELE_MAX = 8
BILDER_LIMIT_MAX = 500
SUCHE_LIMIT_MAX = 50
GESICHTER_JE_SEITE = 48
AUSSCHLUSS_MAX = 200

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
    stand = {"spaeter": [], "unbekannt": []}
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


def _profil_ergaenzen(daten: Dict[str, Any], name: str, beziehung: str, notiz: str,
                      kennung: Optional[str], quelle: str,
                      kontakt: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
    return {"ok": True, "name": schluessel, "beziehung": p.get("beziehung") or "",
            "notizen": notizen, "kontakt": p.get("kontakt")}


def profil_ergaenzen(name: str, beziehung: Optional[str] = None, notiz: Optional[str] = None,
                     kennung: Optional[str] = None,
                     kontakt_id: Optional[str] = None) -> Dict[str, Any]:
    """Beziehung setzen, Erinnerung anhaengen und/oder Kontakt verknuepfen (auch ohne
    Quiz, z. B. aus „Benannt"). Steht im Protokoll, Rueckgaengig nimmt es zurueck. Nie ein Wurf."""
    try:
        sauber = name_saeubern(name)
        b = text_saeubern(beziehung, BEZIEHUNG_MAX)
        n = text_saeubern(notiz, NOTIZ_MAX, zeilen=True)
        kontakt = None
        if kontakt_id:
            kontakt = _kontakte_laden().get(str(kontakt_id).strip())
            if not kontakt:
                raise GruppenFehler("Kontakt nicht (mehr) im Telefonbuch-Auszug.")
        if not b and not n and not kontakt:
            raise GruppenFehler("Bitte eine Beziehung oder eine Erinnerung eingeben.")
        with _SCHREIBSPERRE:
            daten = _profile_laden()
            aenderung = _profil_ergaenzen(daten, sauber, b, n, kennung, "profil",
                                          dict(kontakt) if kontakt else None)
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
    if frage:
        personen = [n for n in alle if passt_wortanfang(n, frage)][:limit]
        treffer = sorted((k for k in kontakte.values() if passt_wortanfang(k["name"], frage)),
                         key=lambda k: (k["name"].casefold(), k["id"]))[:limit]
    else:
        personen, treffer = alle[:limit], []
    verknuepft = {str((p.get("kontakt") or {}).get("id")): n for n, p in profile.items()
                  if isinstance(p, dict) and (p.get("kontakt") or {}).get("id")}

    def person(n: str) -> Dict[str, Any]:
        p = profile.get(_profil_schluessel(profile, n)) or {}
        return {"name": n, "beziehung": p.get("beziehung") or "", "kontakt": bool(p.get("kontakt"))}

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
    benannt = sum(1 for k in kennungen if k in namen)
    unbekannt = sum(1 for k in kennungen if k in set(st["unbekannt"]) and k not in namen)
    spaeter = sum(1 for k in kennungen if k in set(st["spaeter"]) and k not in namen)
    gesichter_benannt = sum(int(g.get("groesse") or 0) for g in gruppen if g["kennung"] in namen)
    return {
        "ok": True, "vorhanden": True, "stand": zeitstempel,
        "gruppen": len(gruppen), "benannt": benannt, "unbekannt": unbekannt,
        "spaeter": spaeter, "offen": len(gruppen) - benannt - unbekannt,
        "gesichter": sum(int(g.get("groesse") or 0) for g in gruppen),
        "gesichter_benannt": gesichter_benannt,
        "namen": namen_liste(namen),
    }


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
    nach_kennung = {g["kennung"]: g for g in gruppen}

    def erstes_beispiel(g: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return next((b for b in (_beispiel_fuer_anzeige(x)
                                 for x in g.get("beispiele") or []) if b), None)

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
                 if b and f"{b['fileid']}:{int(b.get('index') or 0)}" not in aus]
    return {
        "ok": True, "fertig": False, "offen": len(offen),
        "gruppe": {
            "kennung": gruppe["kennung"], "groesse": gruppe.get("groesse"),
            "bilder": gruppe.get("bilder"), "videos": gruppe.get("videos"),
            "von": gruppe.get("von"), "bis": gruppe.get("bis"),
            "war_spaeter": gruppe["kennung"] in spaeter,
            "beispiele": beispiele[:BEISPIELE_MAX], "zwillinge": zwillinge,
            "verbunden": verbunden,
        },
        "namen": namen_liste(namen),
    }


# ── Alle Gesichter eines Vorschlags + Ausschliessen (02.10.2026) ────────────
#
# Wunsch Sebastian: alle (z. B. 400) Gesichter eines Vorschlags durchsehen und
# falsche antippen („das ist nicht Julian, das bin ich"). Ein ausgeschlossenes
# Gesicht steht als Regel in ``personen_vorgaben.json`` unter
# ``"ausgeschlossen": [{"kennung", "bild_id", "index"}]`` — am Handy wirkt sie
# sofort (Liste, Beispiele, Register), am PC laesst ``personen_gruppieren.py``
# das Gesicht nie wieder in diesen Vorschlag. Rueckgaengig nimmt sie zurueck.

_GID = re.compile(r"^\d+:\d+$")


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


def gesichter(kennung: str, seite: int = 1, je_seite: int = GESICHTER_JE_SEITE) -> Dict[str, Any]:
    """Alle (nicht ausgeschlossenen) Gesichter eines Vorschlags, seitenweise. Nie ein Wurf."""
    pfad = _lesepfad(ZUORDNUNG_DATEINAME)
    if not pfad:
        return {"ok": False, "fehler": FEHLT_HINWEIS}
    try:
        alle = _gemerkt(pfad, _gesichter_laden).get(str(kennung), [])
        aus = ausgeschlossen_lesen().get(str(kennung), set())
    except (GruppenFehler, OSError) as fehler:
        return {"ok": False, "fehler": str(fehler)}
    sichtbar = [g for g in alle if g["gid"] not in aus]
    je_seite = max(1, min(int(je_seite or GESICHTER_JE_SEITE), 200))
    seiten = max(1, (len(sichtbar) + je_seite - 1) // je_seite)
    seite = max(1, min(int(seite or 1), seiten))
    teil = sichtbar[(seite - 1) * je_seite: seite * je_seite]
    return {"ok": True, "kennung": kennung, "gesamt": len(sichtbar), "ausgeschlossen": len(aus),
            "seite": seite, "seiten": seiten,
            "gesichter": [{k: v for k, v in g.items() if not k.startswith("_")} for g in teil]}


def ausschliessen(kennung: str, gids: Iterable[str]) -> Dict[str, Any]:
    """Gesichter aus einem Vorschlag nehmen (Regel fuer den naechsten Gruppierlauf). Nie ein Wurf."""
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
            fremd = [g for g in liste if g not in vorhanden]
            if fremd:
                raise GruppenFehler("Gesicht gehört nicht (mehr) zu diesem Vorschlag.")
            roh = _json_lesen(_schreibpfad(VORGABEN_DATEINAME), {})
            daten = roh if isinstance(roh, dict) else {}
            eintraege = daten.get("ausgeschlossen") if isinstance(daten.get("ausgeschlossen"), list) else []
            schon = ausgeschlossen_lesen().get(str(kennung), set())
            neu = [g for g in dict.fromkeys(liste) if g not in schon]
            for g in neu:
                bid, idx = g.split(":")
                eintraege.append({"kennung": str(kennung), "bild_id": bid, "index": int(idx)})
            daten["ausgeschlossen"] = eintraege
            if neu:
                _atomar_schreiben(VORGABEN_DATEINAME, daten)
                _protokoll_anhaengen({"id": uuid.uuid4().hex[:12],
                                      "zeit": datetime.now().isoformat(timespec="seconds"),
                                      "art": "ausschliessen", "kennung": str(kennung),
                                      "gesichter": neu})
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    except OSError as fehler:
        logger.error("Ausschliessen fehlgeschlagen: %s", fehler)
        return {"ok": False, "fehler": f"Speichern fehlgeschlagen ({fehler.__class__.__name__})."}
    rest = gesichter(kennung, 1)
    return {"ok": True, "kennung": kennung, "ausgeschlossen": len(neu),
            "gesamt": rest.get("gesamt", 0)}


# ── Benannte Personen wieder oeffnen und bearbeiten (02.10.2026) ────────────
#
# Wunsch Sebastian: „aktuell bin ich nur am Sortieren, die alten kann ich nicht
# aufrufen und noch mal bearbeiten." Eine Person = alle Vorschlaege mit
# demselben bestaetigten Namen (Gross/Klein egal).

def _anzeige_beispiele(gruppe: Dict[str, Any], aus: set) -> List[Dict[str, Any]]:
    return [b for b in (_beispiel_fuer_anzeige(x) for x in gruppe.get("beispiele") or [])
            if b and f"{b['fileid']}:{int(b.get('index') or 0)}" not in aus][:BEISPIELE_MAX]


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
    liste = []
    for e in je_name.values():
        p = profile.get(_profil_schluessel(profile, e["name"])) or {}
        vorhanden = [nach_kennung[k] for k in e["kennungen"] if k in nach_kennung]
        groesste = max(vorhanden, key=lambda g: int(g.get("groesse") or 0), default=None)
        beispiele = _anzeige_beispiele(groesste, aus.get(groesste["kennung"], set())) if groesste else []
        liste.append({"name": e["name"], "vorschlaege": len(e["kennungen"]), "gesichter": e["gesichter"],
                      "beziehung": p.get("beziehung") or "", "kontakt": bool(p.get("kontakt")),
                      "erinnerungen": sum(1 for x in p.get("notizen") or [] if not x.get("zurueckgenommen")),
                      "beispiel": beispiele[0] if beispiele else None})
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
    return {"ok": True, "name": echter_name, "vorschlaege": vorschlaege, "profil": profil(echter_name)}


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
                else:
                    prof[neu_s] = quelle
                _atomar_schreiben(PROFILE_DATEINAME, daten)
            _bestaetigt_schreiben(namen)
            if eintrag["paare_neu"]["gleich"] or eintrag["paare_weg"]["verschieden"]:
                _vorgaben_schreiben(vorgaben)
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
    eintrag: Dict[str, Any] = {
        "id": uuid.uuid4().hex[:12], "zeit": datetime.now().isoformat(timespec="seconds"),
        "kennung": kennung, "art": art, "ziel": ziel,
        "namen_vorher": {}, "paare_neu": {"gleich": [], "verschieden": []},
        "paare_weg": {"gleich": [], "verschieden": []},
        "listen_vorher": {"spaeter": kennung in st["spaeter"],
                          "unbekannt": kennung in st["unbekannt"]},
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
    elif art == "spaeter":
        st["spaeter"] = [k for k in st["spaeter"] if k != kennung] + [kennung]
    elif art == "unbekannt":
        if kennung not in st["unbekannt"]:
            st["unbekannt"].append(kennung)
        st["spaeter"] = [k for k in st["spaeter"] if k != kennung]

    if eintrag["namen_vorher"]:
        _bestaetigt_schreiben(namen)
    if any(eintrag["paare_neu"].values()) or any(eintrag["paare_weg"].values()):
        _vorgaben_schreiben(vorgaben)
    if eintrag.get("profil"):
        _atomar_schreiben(PROFILE_DATEINAME, profile)
    _atomar_schreiben(STAND_DATEINAME, st)
    _protokoll_anhaengen(eintrag)
    return eintrag


def rueckgaengig() -> Dict[str, Any]:
    """Die letzte (noch nicht zurueckgenommene) Antwort zuruecknehmen."""
    try:
        with _SCHREIBSPERRE:
            eintraege = _protokoll_lesen()
            erledigt = {e.get("bezug") for e in eintraege if e.get("art") == "rueckgaengig"}
            offen = [e for e in eintraege
                     if e.get("art") in ARTEN + ("ausschliessen", "umbenennen", "loesen", "profil")
                     and e.get("id") not in erledigt]
            if not offen:
                return {"ok": False, "fehler": "Es gibt nichts zurückzunehmen."}
            letzte = offen[-1]
            if letzte.get("art") == "ausschliessen":
                roh = _json_lesen(_schreibpfad(VORGABEN_DATEINAME), {})
                daten = roh if isinstance(roh, dict) else {}
                weg = {(str(letzte.get("kennung")), g) for g in letzte.get("gesichter") or []}
                daten["ausgeschlossen"] = [
                    e for e in daten.get("ausgeschlossen") or []
                    if not (isinstance(e, dict) and (str(e.get("kennung")),
                            f"{e.get('bild_id')}:{int(e.get('index') or 0)}") in weg)]
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
            for liste, war in (letzte.get("listen_vorher") or {}).items():
                if liste not in st:
                    continue
                ohne = [k for k in st[liste] if k != kennung]
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
                    for notiz_eintrag in p.get("notizen") or []:
                        if notiz_eintrag.get("id") == pr.get("notiz_id"):
                            notiz_eintrag["zurueckgenommen"] = True
                    _atomar_schreiben(PROFILE_DATEINAME, daten)
            if letzte.get("namen_vorher"):
                _bestaetigt_schreiben(namen)
            if any((letzte.get("paare_neu") or {}).values()) or \
                    any((letzte.get("paare_weg") or {}).values()):
                _vorgaben_schreiben(vorgaben)
            _atomar_schreiben(STAND_DATEINAME, st)
            _protokoll_anhaengen({"id": uuid.uuid4().hex[:12],
                                  "zeit": datetime.now().isoformat(timespec="seconds"),
                                  "art": "rueckgaengig", "bezug": letzte.get("id"),
                                  "kennung": kennung})
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    except OSError as fehler:
        logger.error("Gruppen-Quiz: Rueckgaengig fehlgeschlagen: %s", fehler)
        return {"ok": False, "fehler": f"Zurücknehmen fehlgeschlagen ({fehler.__class__.__name__})."}
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
    except (GruppenFehler, OSError) as fehler:
        return {"ok": False, "fehler": str(fehler)}
    person_von: Dict[str, str] = {k: n.casefold() for k, n in bestaetigt.items()}
    gesucht = {n.casefold() for n in gefragt}
    unbekannt = sorted(n for n in gefragt if n.casefold() not in set(person_von.values()))
    treffer = []
    for schluessel, m in medien.items():
        personen = {person_von[k] for k in m["kennungen"]
                    if k in person_von and (k, schluessel) not in aus_paare}
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
