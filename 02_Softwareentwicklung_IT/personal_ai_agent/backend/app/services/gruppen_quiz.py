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

ARTEN = ("name", "gleich", "verschieden", "spaeter", "unbekannt")
MODI = ("alle", "eine", "genau")
NAME_MAX = 60
BEZIEHUNG_MAX = 80
NOTIZ_MAX = 4000
BEISPIELE_MAX = 8
BILDER_LIMIT_MAX = 500

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
    """Ergebnis von ``laden(pfad)`` merken, solange sich Datei-Zeit und -Groesse nicht aendern."""
    try:
        st = os.stat(pfad)
    except OSError:
        return laden(pfad)
    schluessel = (st.st_mtime, st.st_size)
    alt = _CACHE.get(pfad)
    if alt and alt[0] == schluessel:
        return alt[1]
    wert = laden(pfad)
    _CACHE[pfad] = (schluessel, wert)
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
                      kennung: Optional[str], quelle: str) -> Dict[str, Any]:
    profile = daten["profile"]
    schluessel = _profil_schluessel(profile, name)
    eintrag = profile.setdefault(schluessel, {"beziehung": "", "notizen": []})
    eintrag.setdefault("notizen", [])
    aenderung: Dict[str, Any] = {"name": schluessel, "notiz_id": None}
    if beziehung and beziehung != eintrag.get("beziehung"):
        aenderung["beziehung_vorher"] = eintrag.get("beziehung") or ""
        eintrag["beziehung"] = beziehung
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
            "notizen": notizen}


def profil_ergaenzen(name: str, beziehung: Optional[str] = None, notiz: Optional[str] = None,
                     kennung: Optional[str] = None) -> Dict[str, Any]:
    """Beziehung setzen und/oder eine Erinnerung anhaengen (auch ohne Quiz). Nie ein Wurf."""
    try:
        sauber = name_saeubern(name)
        b = text_saeubern(beziehung, BEZIEHUNG_MAX)
        n = text_saeubern(notiz, NOTIZ_MAX, zeilen=True)
        if not b and not n:
            raise GruppenFehler("Bitte eine Beziehung oder eine Erinnerung eingeben.")
        with _SCHREIBSPERRE:
            daten = _profile_laden()
            _profil_ergaenzen(daten, sauber, b, n, kennung, "profil")
            _atomar_schreiben(PROFILE_DATEINAME, daten)
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    except OSError as fehler:
        logger.error("Profil: Schreiben fehlgeschlagen: %s", fehler)
        return {"ok": False, "fehler": f"Speichern fehlgeschlagen ({fehler.__class__.__name__})."}
    return profil(sauber)


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
    beispiele = [b for b in (_beispiel_fuer_anzeige(x) for x in gruppe.get("beispiele") or []) if b]
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


# ── Antworten ────────────────────────────────────────────────────────────────

def antworten(kennung: str, art: str, name: Optional[str] = None,
              ziel: Optional[str] = None, beziehung: Optional[str] = None,
              notiz: Optional[str] = None) -> Dict[str, Any]:
    """Eine Antwort speichern und die naechste Gruppe liefern. Nie ein Wurf.

    Beim Benennen (``art="name"``) koennen ``beziehung`` und ``notiz`` mitkommen —
    sie landen im Profil der Person (``personen_profile.json``).
    """
    try:
        with _SCHREIBSPERRE:
            eintrag = _antwort_anwenden(kennung, art, name, ziel, beziehung, notiz)
        logger.info("Gruppen-Quiz: %s fuer %s gespeichert", art, kennung)
    except GruppenFehler as fehler:
        return {"ok": False, "fehler": str(fehler)}
    except OSError as fehler:
        logger.error("Gruppen-Quiz: Schreiben fehlgeschlagen: %s", fehler)
        return {"ok": False, "fehler": f"Speichern fehlgeschlagen ({fehler.__class__.__name__})."}
    weiter = naechste()
    weiter["gespeichert"] = {"kennung": kennung, "art": art, "name": eintrag.get("name"),
                             "notiz": bool((eintrag.get("profil") or {}).get("notiz_id")),
                             "weitere": len([k for k in eintrag["namen_vorher"] if k != kennung])}
    return weiter


def _antwort_anwenden(kennung: str, art: str, name: Optional[str],
                      ziel: Optional[str], beziehung: Optional[str] = None,
                      notiz: Optional[str] = None) -> Dict[str, Any]:
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
        if b or n:
            profile = _profile_laden()
            eintrag["profil"] = _profil_ergaenzen(profile, sauber, b, n, kennung, "quiz")
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
                     if e.get("art") in ARTEN and e.get("id") not in erledigt]
            if not offen:
                return {"ok": False, "fehler": "Es gibt nichts zurückzunehmen."}
            letzte = offen[-1]
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
            pr = letzte.get("profil") or {}
            if pr:
                daten = _profile_laden()
                p = daten["profile"].get(pr.get("name") or "")
                if p is not None:
                    if "beziehung_vorher" in pr:
                        p["beziehung"] = pr["beziehung_vorher"]
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
    except (GruppenFehler, OSError) as fehler:
        return {"ok": False, "fehler": str(fehler)}
    person_von: Dict[str, str] = {k: n.casefold() for k, n in bestaetigt.items()}
    gesucht = {n.casefold() for n in gefragt}
    unbekannt = sorted(n for n in gefragt if n.casefold() not in set(person_von.values()))
    treffer = []
    for schluessel, m in medien.items():
        personen = {person_von[k] for k in m["kennungen"] if k in person_von}
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
