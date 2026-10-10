"""Werkzeug-Register fuer Tool Use (Spec: docs/spec-tool-use-v1.md).

Das Modell bekommt diese Werkzeuge als Funktions-Schemata (OpenAI-Format) und
entscheidet selbst, welche es aufruft. Jedes Werkzeug ist eine duenne Huelle um
einen bestehenden Dienst - es gibt hier keinen neuen Datenzugriff.

Regeln (E3/E6/E9 der Spec):
- Nur lesend. Kein Werkzeug schreibt, loescht, sendet oder kostet Geld.
- Ergebnisse sind Text, hoechstens ``MAX_ZEICHEN`` Zeichen; Bilder laufen getrennt
  (``Ergebnis.bilder``), weil Tool-Nachrichten im Chat-Format nur Text tragen.
- Fehler werden nie geworfen, sondern als Text an das Modell zurueckgegeben.
- ``datei_ansehen`` liest nur Dateien mit erlaubter Endung innerhalb der
  freigegebenen Speicherwurzeln (``realpath``-Pruefung gegen Pfad-Ausbruch).

Die Dienste werden erst beim Aufruf importiert: So bleibt das Modul leicht, und
Tests koennen die Dienst-Funktionen gezielt ersetzen.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_ZEICHEN = 6000
MAX_TREFFER = 15

# Kommt an den System-Prompt, wenn Werkzeuge aktiv sind.
SYSTEM_HINWEIS = (
    "\n\n[Werkzeuge] Du hast Werkzeuge für Sebastians Handy-Dateien, sein Gesprächsarchiv, "
    "gemerkte Fakten, seine Fotosammlung, bekannte Personen und Tagesbelege. Wenn eine Frage "
    "davon abhängt, schlage nach, statt zu raten - auch mehrere Werkzeuge nacheinander "
    "(z. B. erst dateien_suchen, dann datei_ansehen, dann archiv_suchen). Für Allgemeinwissen "
    "und Plaudern brauchst du keine Werkzeuge. Findet ein Werkzeug nichts, sag das ehrlich "
    "und erfinde keine Dateien, Fundstellen oder Personen."
)

_BILD_ENDUNGEN = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_DOKU_ENDUNGEN = {".pdf", ".doc", ".docx", ".txt", ".md", ".csv", ".xlsx", ".xls"}


@dataclass
class Ergebnis:
    """Was ein Werkzeug an das Modell zurueckgibt."""

    text: str
    # Bilder fuer das Modell: [{"data_url": "...", "pfad": "..."}]
    bilder: List[Dict[str, str]] = field(default_factory=list)
    ok: bool = True


@dataclass
class Werkzeug:
    name: str
    # Fuer das Modell: WAS das Werkzeug tut und WANN es passt.
    beschreibung: str
    # JSON-Schema der Argumente.
    parameter: Dict[str, Any]
    ausfuehren: Callable[[Dict[str, Any]], Ergebnis]
    # Kurzer Statustext fuer die Oberflaeche.
    status: str = "🔧 arbeitet …"


def _kuerzen(text: str, grenze: int = MAX_ZEICHEN) -> str:
    text = text or ""
    if len(text) <= grenze:
        return text
    return text[:grenze] + f"\n… [gekürzt, {len(text) - grenze} Zeichen mehr]"


def _datum(ts: Any) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(ts)))
    except (TypeError, ValueError, OSError):
        return "?"


def _ganzzahl(wert: Any, standard: int, mini: int, maxi: int) -> int:
    try:
        return max(mini, min(maxi, int(wert)))
    except (TypeError, ValueError):
        return standard


# ── Werkzeug: dateien_suchen ───────────────────────────────────────────────

def _dateien_suchen(args: Dict[str, Any]) -> Ergebnis:
    from app.services import datei_suche

    art = str(args.get("art") or "alle").lower()
    endungen = _BILD_ENDUNGEN if art == "bild" else _DOKU_ENDUNGEN if art == "dokument" else None
    ordner = str(args.get("ordner") or "").lower()
    ordner_hinweis = ordner if ordner in ("kamera", "screenshot") else ""
    jahr = args.get("jahr")
    try:
        jahr = int(jahr) if jahr not in (None, "") else None
    except (TypeError, ValueError):
        jahr = None
    tag = str(args.get("tag") or "").strip() or None
    stichwort = str(args.get("stichwort") or "").strip()
    neueste = bool(args.get("neueste_zuerst", not stichwort))
    anzahl = _ganzzahl(args.get("anzahl"), 10, 1, MAX_TREFFER)

    treffer = datei_suche.suche_dateien(
        stichwort,
        neueste_zuerst=neueste,
        ordner_hinweis=ordner_hinweis,
        nur_erweiterungen=endungen,
        jahr=jahr,
        aufnahme_am=tag,
    )
    if not treffer:
        return Ergebnis("Keine Dateien gefunden (Suche nur im Dateinamen, nicht im Inhalt). "
                        "Tipp: ohne Stichwort, mit neueste_zuerst=true oder mit tag/jahr suchen.")
    zeilen = [
        f"- {t.get('name')} | {t.get('erweiterung')} | "
        f"{round((t.get('groesse_byte') or 0) / 1024)} KB | geändert {_datum(t.get('mtime'))} | "
        f"pfad={t.get('pfad')}"
        for t in treffer[:anzahl]
    ]
    kopf = f"{len(treffer)} Treffer, gezeigt {min(anzahl, len(treffer))}:"
    return Ergebnis(_kuerzen(kopf + "\n" + "\n".join(zeilen)))


# ── Werkzeug: datei_ansehen ────────────────────────────────────────────────

def _erlaubte_wurzeln() -> List[str]:
    from app.services import datei_suche

    roh = [datei_suche._STORAGE_WURZEL, *datei_suche._FALLBACK_WURZELN, "/storage/emulated/0"]
    wurzeln = []
    for w in roh:
        try:
            echt = os.path.realpath(w)
        except OSError:
            continue
        if echt not in wurzeln:
            wurzeln.append(echt)
    return wurzeln


def pfad_erlaubt(pfad: str) -> bool:
    """Nur Dateien mit erlaubter Endung innerhalb der freigegebenen Speicherwurzeln."""
    from app.services import datei_suche

    if not pfad or not isinstance(pfad, str):
        return False
    try:
        echt = os.path.realpath(os.path.expanduser(pfad))
    except (OSError, ValueError):
        return False
    if os.path.splitext(echt)[1].lower() not in datei_suche._ERLAUBTE_EXT:
        return False
    for wurzel in _erlaubte_wurzeln():
        try:
            if os.path.commonpath([echt, wurzel]) == wurzel:
                return True
        except ValueError:  # z. B. verschiedene Laufwerke unter Windows
            continue
    return False


def _datei_ansehen(args: Dict[str, Any]) -> Ergebnis:
    from app.services import datei_suche

    pfad = str(args.get("pfad") or "").strip()
    if not pfad_erlaubt(pfad):
        return Ergebnis("Diese Datei darf ich nicht öffnen: nur Bilder und Dokumente aus den "
                        "freigegebenen Handy-Ordnern, und nur mit einem pfad aus dateien_suchen.",
                        ok=False)
    info = datei_suche.lese_datei_info(pfad, max_zeichen=MAX_ZEICHEN)
    if info.get("fehler"):
        return Ergebnis(f"Datei ließ sich nicht lesen: {info.get('fehler')}", ok=False)
    name = info.get("name") or os.path.basename(pfad)
    if info.get("ist_bild"):
        if not info.get("data_url"):
            return Ergebnis(f"Bild {name} ließ sich nicht laden.", ok=False)
        return Ergebnis(
            f"Bild {name} ist geladen und folgt direkt als Bild. Das Aufnahmedatum steckt oft im "
            "Dateinamen (IMG_JJJJMMTT_HHMMSS); erfinde kein anderes.",
            bilder=[{"data_url": info["data_url"], "pfad": pfad}],
        )
    text = (info.get("text") or "").strip()
    if not text:
        return Ergebnis(f"{name} enthält keinen lesbaren Text.")
    return Ergebnis(_kuerzen(f"Inhalt von {name}:\n{text}"))


# ── Werkzeug: archiv_suchen ────────────────────────────────────────────────

def _archiv_suchen(args: Dict[str, Any]) -> Ergebnis:
    from app.services.archiv_service import archiv_service

    frage = str(args.get("frage") or "").strip()
    if not frage:
        return Ergebnis("Bitte eine Suchfrage angeben.", ok=False)
    if not archiv_service.is_available:
        return Ergebnis("Das Archiv der alten Gespräche ist gerade nicht erreichbar. "
                        "Erfinde keine Fundstellen.", ok=False)
    anzahl = _ganzzahl(args.get("anzahl"), 5, 1, 8)
    treffer = archiv_service.hybrid(frage, top_k=anzahl) or []
    if not treffer:
        return Ergebnis(f"Im Archiv nichts zu „{frage}“ gefunden.")
    zeilen = []
    for t in treffer[:anzahl]:
        quelle = t.get("source") or "unbekannt"
        datum = (t.get("beginn") or "")[:10]
        text = (t.get("text") or "").strip().replace("\n", " ")[:500]
        zeilen.append(f"- [{quelle}{', ' + datum if datum else ''}] {text}")
    return Ergebnis(_kuerzen("Fundstellen (nenne Quelle und Datum):\n" + "\n".join(zeilen)))


# ── Werkzeug: notizen_suchen (07.10.2026) ─────────────────────────────────

def _notizen_suchen(args: Dict[str, Any]) -> Ergebnis:
    """Sebastians eigene App-Notizen: Personen-Notizen und Erzähl-Geschichten.

    Anlass: „was arbeitet mein Bruder?" blieb unbeantwortet, weil die
    Personen-Notiz aus dem Quiz für den Chat unsichtbar war.
    """
    from app.services import notizen_service

    frage = " ".join(str(args.get("frage") or "").split())
    person = " ".join(str(args.get("person") or "").split())
    if not frage and not person:
        return Ergebnis("Bitte eine Frage oder einen Personennamen angeben.", ok=False)
    anzahl = _ganzzahl(args.get("anzahl"), 8, 1, 25)
    text = notizen_service.text_antwort(begriff=frage, person=person, limit=anzahl)
    if not (text or "").strip():
        return Ergebnis("Keine eigenen Notizen gefunden.", ok=False)
    return Ergebnis(_kuerzen(text.strip()))


# ── Werkzeug: erinnerungen_suchen ──────────────────────────────────────────

def _erinnerungen_suchen(args: Dict[str, Any]) -> Ergebnis:
    from app.services.memory_service import memory_service

    frage = str(args.get("frage") or "").strip()
    if not frage:
        return Ergebnis("Bitte eine Suchfrage angeben.", ok=False)
    anzahl = _ganzzahl(args.get("anzahl"), 8, 1, 15)
    treffer = memory_service.retrieve_relevant_memories(frage, top_k=anzahl) or []
    if not treffer:
        return Ergebnis(f"Keine gemerkten Fakten zu „{frage}“.")
    zeilen = []
    for m in treffer[:anzahl]:
        inhalt = str(m.get("content") or "").strip()
        if not inhalt:
            continue
        art = str(m.get("art") or m.get("category") or "fakt")
        datum = m.get("ereignis_datum")
        zeilen.append(f"- {inhalt} ({art}{', ' + str(datum) if datum else ''})")
    return Ergebnis(_kuerzen("Gemerkte Fakten:\n" + "\n".join(zeilen)) if zeilen
                    else f"Keine gemerkten Fakten zu „{frage}“.")


# ── Werkzeuge rund um Fotos und Personen ───────────────────────────────────

def _fotos_uebersicht(args: Dict[str, Any]) -> Ergebnis:
    from app.services import foto_uebersicht

    text = foto_uebersicht.text_antwort(
        jahr=args.get("jahr") or None,
        kategorie=args.get("kategorie") or None,
        suche=args.get("suche") or None,
    )
    if not (text or "").strip():
        return Ergebnis("Die Foto-Übersicht liegt auf diesem Gerät nicht vor.", ok=False)
    return Ergebnis(_kuerzen(text.strip()))


def _fotos_mit_person(args: Dict[str, Any]) -> Ergebnis:
    from app.services import gesicht_fotos

    person = str(args.get("person") or "").strip()
    if not person:
        return Ergebnis("Bitte den Namen der Person angeben (siehe personen_liste).", ok=False)
    tage = args.get("tage")
    try:
        tage = int(tage) if tage not in (None, "") else None
    except (TypeError, ValueError):
        tage = None
    ergebnis = gesicht_fotos.suche_bilder_mit_person(person, tage=tage) or {}
    gefunden = ergebnis.get("gefunden") or []
    if not gefunden:
        zeitraum = f" in den letzten {tage} Tagen" if tage else ""
        return Ergebnis(f"Keine Fotos mit {person}{zeitraum} gefunden.")
    zeilen = [
        f"- {(g.get('pfad') or '').split('/')[-1]} | {g.get('name') or '?'} | "
        f"{'sicher' if g.get('sicher') else 'unsicher'} | pfad={g.get('pfad')}"
        for g in gefunden[:MAX_TREFFER]
    ]
    return Ergebnis(_kuerzen(f"{len(gefunden)} Foto(s) mit {person}:\n" + "\n".join(zeilen)))


def _personen_liste(args: Dict[str, Any]) -> Ergebnis:
    """Bekannte Personen — aus dem Personen-Quiz (dieselbe Quelle, die das Quiz
    führt), nicht mehr aus dem alten Gesichtskatalog.

    Grund (Befund 10.10.2026): Der Chat fand Personen nicht, weil dieser Weg auf
    ``gesichter_service`` (alter Katalog, 10 Personen) baute, während das Quiz in
    ``personen_bestaetigt.json``/``personen_profile.json`` über 100 benannte
    Personen führt. Nur wenn diese Dateien fehlen, greift der alte Katalog als
    Notnagel. Bewusst nur Klartext — nie Vektoren, Miniaturen oder Pfade.
    """
    from app.services import gruppen_quiz

    quiz = gruppen_quiz.personen()
    personen = (quiz.get("personen") or []) if quiz.get("ok") else []
    if not personen:
        from app.services import gesichter_service

        alt = gesichter_service.liste_personen() or []
        if not alt:
            return Ergebnis("Es sind noch keine Personen angelernt.")
        zeilen = []
        for p in alt:
            teile = [str(p.get("name") or "?")]
            for feld in ("rolle", "beziehung"):
                wert = p.get(feld)
                if isinstance(wert, str) and wert.strip():
                    teile.append(wert.strip()[:60])
            zeilen.append("- " + " | ".join(teile))
        return Ergebnis(_kuerzen(f"{len(alt)} bekannte Personen:\n" + "\n".join(zeilen)))
    zeilen = []
    for p in personen:
        teile = [str(p.get("name") or "?")]
        beziehung = str(p.get("beziehung") or "").strip()
        if beziehung:
            teile.append(beziehung[:60])
        teile.append(f"{max(0, int(p.get('gesichter') or 0))} Gesichter")
        zeilen.append("- " + " | ".join(teile))
    return Ergebnis(_kuerzen(f"{len(personen)} bekannte Personen:\n" + "\n".join(zeilen)))


def _person_auskunft(args: Dict[str, Any]) -> Ergebnis:
    """Alles, was das Personen-Quiz über EINE Person weiß: Beziehung, eigene
    Notizen, Geburtstag (aus dem Telefonbuch-Auszug) und die Zahl ihrer Fotos.

    Dieselbe Quelle wie das Quiz (``personen_profile.json`` über
    ``personen_bestaetigt.json``) — deshalb findet der Chat jetzt dieselben
    Personen, die im Quiz bestätigt wurden. Nur Klartext, keine Vektoren,
    keine Bilddaten, keine Pfade.
    """
    from app.services import gruppen_quiz

    name = str(args.get("person") or "").strip()
    if not name:
        return Ergebnis("Bitte den Namen der Person angeben (siehe personen_liste).", ok=False)
    daten = gruppen_quiz.person(name)
    if not daten.get("ok"):
        return Ergebnis(str(daten.get("fehler") or "Diese Person ist nicht bekannt."), ok=False)
    profil_roh = daten.get("profil")
    profil: Dict[str, Any] = profil_roh if isinstance(profil_roh, dict) else {}
    vorschlaege = daten.get("vorschlaege") or []
    fotos = sum(max(0, int(v.get("groesse") or 0))
                for v in vorschlaege if isinstance(v, dict))
    zeilen = [f"Person: {daten.get('name') or name}"]
    beziehung = str(profil.get("beziehung") or "").strip()
    if beziehung:
        zeilen.append(f"Beziehung: {beziehung}")
    kontakt = profil.get("kontakt")
    if isinstance(kontakt, dict) and str(kontakt.get("geburtstag") or "").strip():
        zeilen.append(f"Geburtstag: {str(kontakt['geburtstag']).strip()}")
    zeilen.append(f"Fotos (erkannte Gesichter): {fotos}")
    if len(vorschlaege) > 1:
        zeilen.append(f"Vorschläge (Bildgruppen): {len(vorschlaege)}")
    notizen = [n for n in (profil.get("notizen") or [])
               if isinstance(n, dict) and not n.get("zurueckgenommen")]
    if notizen:
        zeilen.append(f"Notizen ({len(notizen)}):")
        zeilen += [f"- {str(n.get('text') or '').strip()}" for n in notizen[:20]]
    return Ergebnis(_kuerzen("\n".join(zeilen)))


def _wer_war_wann(args: Dict[str, Any]) -> Ergebnis:
    from app.services import beziehungen_service

    roh = str(args.get("datum") or "").strip()
    datum = beziehungen_service.datum_erkennen(roh)
    if not datum:
        return Ergebnis(f"„{roh}“ ist kein gültiges Datum (Format JJJJ-MM-TT).", ok=False)
    text = beziehungen_service.text_antwort(datum)
    if not (text or "").strip():
        return Ergebnis(f"Für {datum} liegen keine Belege vor (oder die Datei fehlt auf dem Gerät).")
    return Ergebnis(_kuerzen(text.strip()))


# ── Register ───────────────────────────────────────────────────────────────

def _obj(eigenschaften: Dict[str, Any], pflicht: Optional[List[str]] = None) -> Dict[str, Any]:
    return {"type": "object", "properties": eigenschaften, "required": pflicht or []}


REGISTER: Dict[str, Werkzeug] = {w.name: w for w in [
    Werkzeug(
        "dateien_suchen",
        "Findet Dateien auf Sebastians Handy (Kamera-Fotos, Screenshots, Downloads, PDFs, "
        "Dokumente). Sucht NUR im Dateinamen, nicht im Inhalt - Kamera-Fotos heißen "
        "IMG_JJJJMMTT_…, deshalb für Fotos besser ohne Stichwort mit neueste_zuerst, tag oder "
        "jahr suchen. Liefert Namen und pfad; ansehen mit datei_ansehen.",
        _obj({
            "stichwort": {"type": "string", "description": "Teil des Dateinamens, leer = alle"},
            "art": {"type": "string", "enum": ["bild", "dokument", "alle"]},
            "ordner": {"type": "string", "enum": ["kamera", "screenshot", "egal"]},
            "neueste_zuerst": {"type": "boolean"},
            "jahr": {"type": "integer", "description": "Aufnahmejahr, z. B. 2025"},
            "tag": {"type": "string", "description": "heute, gestern oder JJJJ-MM-TT"},
            "anzahl": {"type": "integer", "minimum": 1, "maximum": MAX_TREFFER},
        }),
        _dateien_suchen,
        "🔧 durchsucht Handy-Dateien …",
    ),
    Werkzeug(
        "datei_ansehen",
        "Öffnet eine Datei aus dateien_suchen oder fotos_mit_person: liest den Text (PDF, "
        "TXT, …) oder zeigt dir das Bild, damit du es beschreiben kannst. Nur pfad aus "
        "einem Suchergebnis verwenden.",
        _obj({"pfad": {"type": "string"}}, ["pfad"]),
        _datei_ansehen,
        "🔧 öffnet eine Datei …",
    ),
    Werkzeug(
        "archiv_suchen",
        "Durchsucht Sebastians frühere Gespräche mit ChatGPT, Gemini, Claude und andere "
        "archivierte Chats nach Thema. Für: 'was habe ich damals …', 'hatten wir schon …', "
        "Beispiele aus seinem Leben, frühere Entscheidungen.",
        _obj({
            "frage": {"type": "string", "description": "Thema oder Frage in eigenen Worten"},
            "anzahl": {"type": "integer", "minimum": 1, "maximum": 8},
        }, ["frage"]),
        _archiv_suchen,
        "🔧 durchsucht das Gesprächsarchiv …",
    ),
    Werkzeug(
        "notizen_suchen",
        "Liest Sebastians EIGENE Notizen in der App: Notizen an Personen (aus dem "
        "Personen-Quiz, z. B. Beziehung, Beruf, Vorlieben) und Geschichten an "
        "Ereignissen (Erzähl-Ansicht). Dafür: 'was arbeitet mein Bruder', "
        "'was habe ich zu X notiert', 'was weiß ich über Y', 'welche Notiz steht bei Z'. "
        "Mit person=Name kommen alle Notizen dieser Person; mit frage=Stichwort wird in "
        "allen Notizen und Geschichten gesucht.",
        _obj({
            "frage": {"type": "string", "description": "Stichwort, leer = alle Notizen"},
            "person": {"type": "string", "description": "Name der Person (optional)"},
            "anzahl": {"type": "integer", "minimum": 1, "maximum": 25},
        }),
        _notizen_suchen,
        "🔧 sieht in eigenen Notizen nach …",
    ),
    Werkzeug(
        "erinnerungen_suchen",
        "Ruft gemerkte Fakten über Sebastian ab: Vorlieben, Termine, Personen, Projekte.",
        _obj({
            "frage": {"type": "string"},
            "anzahl": {"type": "integer", "minimum": 1, "maximum": 15},
        }, ["frage"]),
        _erinnerungen_suchen,
        "🔧 schaut in die Erinnerungen …",
    ),
    Werkzeug(
        "fotos_uebersicht",
        "Übersicht über Sebastians sortierte Fotosammlung (pCloud): Anlässe, Jahre, Anzahl. "
        "Für 'wie viele Fotos von …', 'welche Anlässe 2019', 'Urlaub in …'.",
        _obj({
            "jahr": {"type": "integer"},
            "kategorie": {"type": "string"},
            "suche": {"type": "string", "description": "Wort im Anlass-Namen"},
        }),
        _fotos_uebersicht,
        "🔧 schaut in die Foto-Übersicht …",
    ),
    Werkzeug(
        "fotos_mit_person",
        "Findet Fotos auf dem Handy, auf denen eine bekannte Person erkannt wurde. Namen "
        "vorher mit personen_liste prüfen.",
        _obj({
            "person": {"type": "string"},
            "tage": {"type": "integer", "description": "nur die letzten N Tage"},
        }, ["person"]),
        _fotos_mit_person,
        "🔧 sucht Fotos mit einer Person …",
    ),
    Werkzeug(
        "personen_liste",
        "Listet die Personen, die der Agent auf Fotos erkennen kann (Name, Rolle).",
        _obj({}),
        _personen_liste,
        "🔧 schaut, wen ich kenne …",
    ),
    Werkzeug(
        "person_auskunft",
        "Alles, was über EINE bekannte Person bekannt ist: Beziehung, eigene Notizen, "
        "Geburtstag (aus dem Telefonbuch) und die Zahl ihrer Fotos. Für 'wer ist X', "
        "'was weiß ich über X', 'wie viele Fotos habe ich von X'. Namen vorher mit "
        "personen_liste prüfen.",
        _obj({"person": {"type": "string"}}, ["person"]),
        _person_auskunft,
        "🔧 sieht nach, was ich über eine Person weiß …",
    ),
    Werkzeug(
        "wer_war_wann",
        "Was ist an einem bestimmten Tag belegt: wer war mit wem zusammen (Fotos, Chats). "
        "Für 'was war am 21.08.2022', 'mit wem war ich an Silvester 2019'.",
        _obj({"datum": {"type": "string", "description": "JJJJ-MM-TT"}}, ["datum"]),
        _wer_war_wann,
        "🔧 schaut in die Tagesbelege …",
    ),
]}


def schemata() -> List[Dict[str, Any]]:
    """Alle Werkzeuge im OpenAI-Format fuer den ``tools``-Parameter."""
    return [
        {
            "type": "function",
            "function": {
                "name": w.name,
                "description": w.beschreibung,
                "parameters": w.parameter,
            },
        }
        for w in REGISTER.values()
    ]


def status_text(name: str) -> str:
    w = REGISTER.get(name)
    return w.status if w else f"🔧 {name} …"


def ausfuehren(name: str, argumente_json: Any) -> Ergebnis:
    """Ein Werkzeug ausfuehren. Wirft nie; Fehler kommen als Text zurueck."""
    werkzeug = REGISTER.get(name)
    if werkzeug is None:
        return Ergebnis(f"Unbekanntes Werkzeug „{name}“. Verfügbar: {', '.join(REGISTER)}.", ok=False)
    try:
        if isinstance(argumente_json, dict):
            args = argumente_json
        else:
            args = json.loads(argumente_json or "{}")
        if not isinstance(args, dict):
            raise ValueError("Argumente sind kein Objekt")
    except (ValueError, TypeError) as e:
        return Ergebnis(f"Argumente für {name} sind kein gültiges JSON-Objekt ({e}).", ok=False)
    try:
        ergebnis = werkzeug.ausfuehren(args)
    except Exception as e:  # Werkzeugfehler duerfen die Antwort nie abbrechen
        logger.warning("Werkzeug %s fehlgeschlagen: %s", name, type(e).__name__)
        return Ergebnis(f"{name} ist fehlgeschlagen ({type(e).__name__}). Sag das ehrlich.", ok=False)
    if not isinstance(ergebnis, Ergebnis):
        return Ergebnis(_kuerzen(str(ergebnis)))
    ergebnis.text = _kuerzen(ergebnis.text)
    return ergebnis
