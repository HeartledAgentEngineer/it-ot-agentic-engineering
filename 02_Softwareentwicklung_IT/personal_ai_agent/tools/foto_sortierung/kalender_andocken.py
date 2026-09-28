"""Kalender-Andockung der Ereignis-Knoten (N27 Schritt 3, 28.09.2026).

Warum dieses Werkzeug:
  Schritt 1 (``ereignisse_bauen.py``) hat je Anlass einen **Ereignis-Knoten**
  gelegt, Schritt 2 (``chat_andocken.py``) die Chats angebunden. Schritt 3
  dockt den **Kalender** an: zu jedem Ereignis wird gefragt, welche
  Kalender-Termine an genau diesem Tag lagen (inklusive mehrtagiger Termine,
  die den Tag enthalten) und welche Termine nur **+-1 Tag** daneben liegen.
  Spaeter laesst sich ein Tag damit mit den Terminen verbinden, die
  dazugehoeren.

Was dieses Werkzeug bewusst NICHT tut:
  * **Kein Netz.** Kein pCloud-Aufruf, kein ``httpx``/``requests``, kein
    LLM-Aufruf. Gelesen werden ausschliesslich zwei lokale Eingaben.
  * **Keine Bilder.** Es wird keine Bilddatei geoeffnet, kopiert oder
    gespeichert.
  * **Kein Entpacken und kein Kopieren der Eingaben.** Das Takeout-Zip wird
    **ausschliesslich per ``zipfile``** gelesen, nie entpackt, nie kopiert,
    nie veraendert.
  * **Kein weiterer Termin-Text.** Aus der ICS werden nur ``DTSTART``,
    ``DTEND``, ``SUMMARY``, ``RRULE`` und ``UID`` gelesen. ``DESCRIPTION``
    und ``LOCATION`` werden **nicht** uebernommen.
  * **Keine Loeschung** ausser der eigenen temp-Datei beim atomaren Schreiben;
    es gibt keine Loeschfunktion, auch nicht "zur Sicherheit".
  * **Kein Schreiben ohne ``--schreiben``.** Der Standard ist ``--trocken``.
  * **Ziel im Repo wird verweigert** (deutsche Meldung, Exit 2) — auch mit
    ``--schreiben``.

Eingaben (beide **nur lesend**, Pfade per Schalter konfigurierbar):
  1. ``--ereignisse`` (Standard ``~/foto_sortierung/ereignisse.jsonl``): die
     Knoten aus N27a. Genutzt werden genau ``anlass_id`` und ``datum``;
     unbekannte Schluessel werden ignoriert.
  2. ``--zip`` (Standard: das Takeout-Zip ausserhalb des Repos) und
     ``--mitglied`` (Standard: **leer** — dann werden automatisch **alle**
     ``Takeout/Kalender/*.ics`` im Zip gelesen). Ein ausdruecklich genannter
     Eintrag, der fehlt, bleibt ein Klartextfehler. Die ICS wird nur per
     ``zipfile`` **gelesen**.

Ausgabe (eingefrorenes Schema, JSONL), ``--ausgabe`` (Standard
``~/foto_sortierung/kalender_andockung.jsonl``):
  Reine JSONL mit **gleicher Reihenfolge wie die Eingabe**; je Zeile genau ein
  Ereignis, kodiert mit ``ensure_ascii=True`` (ASCII, keine Umlaute) und
  ``sort_keys=True``. Keine Kopfzeile, kein ``zahlen``-Block in der Datei; die
  Zahlen stehen nur auf der Konsole und im Rueckgabewert von ``andocken``.
  Eine Zeile hat genau diese Schluessel::

      {"anlass_id", "anzahl_nah", "anzahl_treffer", "art": "kalender_andockung",
       "datum", "kennung": "K-" + anlass_id, "stand",
       "treffer": [{"beginn", "ende", "ganztags", "quelle": "ics", "titel",
                    "wiederkehrend"}]}

  * ``treffer`` = Termine **am selben Tag** wie der Anlass (auch mehrtagige,
    die diesen Tag enthalten). Sortierung fest: ``beginn`` aufsteigend, dann
    ``titel`` aufsteigend (reproduzierbar).
  * ``anzahl_nah`` = Termine **+-1 Tag**, die **keine** Tag-Treffer sind —
    nur als schwacher Hinweis gezaehlt (Lehre aus N6e: ein bloss benachbartes
    Datum ist kein Beleg). ``--auch-nah`` nimmt sie zusaetzlich in ``treffer``
    auf; Standard = aus. ``anzahl_nah`` bleibt trotzdem die Zahl der
    Nah-Termine.

Regeln (hart):
  1. ``--trocken`` ist der **Standard.** Ohne ``--schreiben`` wird nichts auf
     Platte geschrieben; die Ausgabezeilen werden nur gezaehlt.
  2. Nur Standardbibliothek (``argparse``, ``datetime``, ``json``, ``os``,
     ``re``, ``sys``, ``zipfile``); keine neue Abhaengigkeit.
  3. Keine Loeschfunktion — als einzige Entfernung ist ``os.remove(temp)`` auf
     die **eigene** temp-Datei erlaubt.
  4. Zweiter Lauf = kein Schaden: zweimal ``--schreiben`` mit festem ``stand``
     ergibt **byte-gleiche** Dateien; die Eingaben bleiben unveraendert.
  5. Datenschutz: Die Ausgabedatei liegt **ausserhalb** des Repos und darf
     Termin-Titel tragen (privat). In Code, Tests und Doku stehen **keine**
     echten Termin-, Orts- oder Personennamen.
  6. Ehrlich ausgeben: die Konsole nennt die Zahlen, die wirklich gelten
     (Ereignisse, Treffer-Zeilen, Termine am Tag, Nah-Treffer, wiederkehrende
     Treffer, uebersprungen/unlesbar). Keine geschoente Zahl.

Jaehrliche Wiederkehr (Regel, nicht Auslegung):
  * Termine mit ``RRULE`` und ``FREQ=YEARLY`` (typisch Geburtstage) treffen
    ueber **Tag+Monat**, unabhaengig vom Jahr; ``wiederkehrend: true``,
    ``beginn`` ist das **Anlass-Jahr** + Monat/Tag.
  * Rueckfall, falls **keine** ``RRULE`` gesetzt ist: Termine, deren ``SUMMARY``
    "Geburtstag" oder "Jahrestag" enthaelt **und** die ein vollstaendiges Datum
    haben, gelten ebenfalls als jaehrlich wiederkehrend.
  * Der 29. Februar wird in Nicht-Schaltjahren auf den 28. Februar geklemmt
    (deterministisch, dokumentiert).
  * ``spanne`` eines Termins ist ``max(1, (DTEND - DTSTART).Tage)``; ein
    mehrtagiger Termin enthaelt alle Tage ``[DTSTART, DTEND)``.

ICS-Leser (eigene, kleine Umsetzung — kein neues Paket):
  * Zeilenweise falten aufloesen (Fortsetzungszeilen beginnen mit Leerzeichen
    oder Tab), ``VEVENT``-Bloecke einsammeln, Eigenschaften ``DTSTART``,
    ``DTEND``, ``SUMMARY``, ``RRULE``, ``UID`` lesen.
  * Das Datum wird aus den **ersten 8 Ziffern** eines Werts gelesen
    (``20200315`` und ``20200315T180000Z`` liefern beide ``2020-03-15``);
    Zeitzonen werden **nicht** umgerechnet.
  * Ganztags = ``VALUE=DATE`` oder fehlende Uhrzeit.
  * Fehlende/defekte Bloecke (kein lesbares ``DTSTART``) und ein nicht
    geschlossener Block werden **gezaehlt und gemeldet**, nie still
    verschluckt.

Aufruf (Kommandozeile)::

    python tools/foto_sortierung/kalender_andocken.py --trocken
    python tools/foto_sortierung/kalender_andocken.py --limit 3
    python tools/foto_sortierung/kalender_andocken.py --auch-nah
    python tools/foto_sortierung/kalender_andocken.py --ausgabe C:/tmp/k.jsonl --schreiben

Als Modul (Tests, spaetere Schritte): ``haupt(argv=[...])`` sowie die reinen
Funktionen ``ereignisse_laden``, ``zip_ics_lesen``, ``zeilen_entfalten``,
``bloecke_sammeln``, ``termin_bauen``, ``andocken``, ``knoten_zeile``,
``andockung_schreiben``, ``zahlen_text``.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import zipfile

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

# Vorgabepfade: ausserhalb des Repos — dort liegen private Kennungen und Namen.
STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_EREIGNISSE = os.path.join(STANDARD_BASIS, "ereignisse.jsonl")
STANDARD_AUSGABE = os.path.join(STANDARD_BASIS, "kalender_andockung.jsonl")

# Standard-Takeout-Zip (woertlich so beauftragt, AUSSERHALB des Repos). Gelesen
# wird **nur** per ``zipfile``. Die Vorgabe fuer den Kalender-Eintrag ist leer:
# es werden automatisch **alle** ``*.ics`` unter ``Takeout/Kalender/`` im Zip
# gelesen (so steht kein Kontoname im Repo).
STANDARD_ZIP = (
    r"C:\Users\sebas\Desktop\workspace agentic engineering"
    r"\Chats von GPT, GEMINI, Claude\raw\takeout-20260812T203313Z-3-001.zip"
)
# ``None``/leer = Vorgabe: alle ``*.ics`` unter ``Takeout/Kalender/`` im Zip,
# automatisch gefunden (kein Kontoname im Repo). Ein ausdruecklich genannter,
# aber fehlender Eintrag bleibt ein Klartextfehler.
STANDARD_MITGLIED = None

# Praefix/Suffix der Kalender-Eintraege im Takeout-Zip (fuer die Auto-Vorgabe).
KALENDER_PRAEFIX = "Takeout/Kalender/"
KALENDER_SUFFIX = ".ics"

# Die Ausgabe-Art und die Schluessel des eingefrorenen Schemas.
ANDOCKUNG_ART = "kalender_andockung"
KNOTEN_SCHLUESSEL = (
    "anlass_id", "anzahl_nah", "anzahl_treffer", "art", "datum", "kennung",
    "stand", "treffer",
)
TREFFER_SCHLUESSEL = (
    "beginn", "ende", "ganztags", "quelle", "titel", "wiederkehrend",
)

# Fensterregel (Regel, nicht Auslegung): Treffer = derselbe Tag; nah = +-1 Tag.
NAH_TAGE = 1

# Titel werden auf 120 Zeichen gekuerzt; kein weiterer Termin-Text.
MAX_TITEL = 120
QUELLE_ICS = "ics"

# Jaehrliche Wiederkehr: Schluesselworte im Titel (Rueckfall ohne RRULE).
JAHRES_TITEL = ("geburtstag", "jahrestag")

# Lesbares Datum = echte Kalenderangabe in der Form JJJJ-MM-TT (ASCII).
DATUM_MUSTER = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


def _zahl(n) -> str:
    """Eine Zahl mit deutschen Tausenderpunkten (nur fuer die Ausgabe)."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def _datum_lesen(wert):
    """Ein Datum als ``date`` lesen — sonst ``None`` (nichts geraten)."""
    text = _text(wert)
    if not DATUM_MUSTER.match(text):
        return None
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        return None


def _datum_im_jahr(jahr: int, monat: int, tag: int):
    """``(jahr, monat, tag)`` als Datum; zu grosse Tage werden geklemmt.

    Der 29. Februar wird in einem Nicht-Schaltjahr auf den 28. Februar
    geklemmt — deterministisch statt Ausnahme.
    """
    while tag > 1:
        try:
            return datetime.date(jahr, monat, tag)
        except ValueError:
            tag -= 1
    try:
        return datetime.date(jahr, monat, 1)
    except ValueError:
        return None


# ── 1. Ereignis-Knoten lesen (lokal, nur lesend, kein Netz) ───────────────

def ereignisse_laden(pfad: str) -> list:
    """Die Ereignis-Knoten aus ``ereignisse.jsonl`` lesen (nur lesend).

    Genutzt werden genau ``anlass_id`` und ``datum``. Eine Zeile **ohne**
    ``anlass_id`` traegt keinen stabilen Anker und wird uebersprungen (kein
    erfundener Knoten). Fehlende Datei, unlesbares JSON und eine ungueltige
    Zeile ergeben eine deutsche ``ValueError``-Meldung.
    """
    if not isinstance(pfad, str) or not pfad.strip():
        raise ValueError("Kein Pfad fuer die Ereignisse angegeben.")
    if not os.path.isfile(pfad):
        raise ValueError(f"Ereignisse nicht gefunden: {pfad}")
    ereignisse = []
    try:
        with open(pfad, encoding="utf-8") as datei:
            for nummer, zeile in enumerate(datei, start=1):
                zeile = zeile.strip()
                if not zeile:
                    continue
                try:
                    roh = json.loads(zeile)
                except json.JSONDecodeError:
                    raise ValueError(
                        f"Ereignisse nicht lesbar: Zeile {nummer} ist kein "
                        f"gueltiges JSON ({pfad})") from None
                if not isinstance(roh, dict):
                    continue
                anlass_id = _text(roh.get("anlass_id"))
                if not anlass_id:
                    continue
                ereignisse.append({
                    "anlass_id": anlass_id,
                    "datum": _text(roh.get("datum")),
                })
    except OSError as problem:
        raise ValueError(
            f"Ereignisse nicht lesbar ({problem.__class__.__name__}): "
            f"{pfad}") from None
    return ereignisse


# ── 2. ICS lesen (nur per zipfile, nie entpacken) ─────────────────────────

def _zip_kalender_eintraege(namen) -> list:
    """Alle Eintraege ``Takeout/Kalender/*.ics`` aus einer Namensliste (sortiert).

    Reine Funktion. Nicht-Text und alles ausserhalb von ``Takeout/Kalender/``
    mit Endung ``.ics`` wird uebergangen.
    """
    if not isinstance(namen, (list, tuple)):
        return []
    treffer = [
        name for name in namen
        if isinstance(name, str)
        and name.startswith(KALENDER_PRAEFIX)
        and name.endswith(KALENDER_SUFFIX)
    ]
    return sorted(treffer)


def zip_ics_lesen(zip_pfad: str, mitglied: str | None = None,
                  bericht: dict | None = None) -> str:
    """Den ICS-Text aus dem Takeout-Zip lesen (nur lesend).

    Das Zip wird **ausschliesslich per ``zipfile``** geoeffnet; es wird nichts
    entpackt, kopiert oder veraendert. Ist ``mitglied`` angegeben, wird genau
    dieser Eintrag gelesen — fehlt er, gibt es eine deutsche
    ``ValueError``-Meldung (Klartextfehler wie bisher). Ohne ``mitglied``
    (``None`` oder leer) werden **alle** Eintraege ``Takeout/Kalender/*.ics``
    gelesen und mit Zeilenumbruch aneinandergehaengt; gibt es keinen, gibt es
    eine deutsche ``ValueError``-Meldung. Fehlender Pfad, fehlendes Zip und ein
    unlesbares Zip ergeben ebenfalls eine deutsche ``ValueError``-Meldung.
    Kodierung: zuerst UTF-8, dann Latin-1 als Rueckfall. Wird ``bericht`` (ein
    ``dict``) uebergeben, traegt es ``kalender`` = Anzahl der gelesenen
    Kalenderdateien.
    """
    if not isinstance(zip_pfad, str) or not zip_pfad.strip():
        raise ValueError("Kein Pfad fuer das Takeout-Zip angegeben.")
    if not os.path.isfile(zip_pfad):
        raise ValueError(f"Takeout-Zip nicht gefunden: {zip_pfad}")
    gewaehlt = _text(mitglied)
    if isinstance(bericht, dict):
        bericht["kalender"] = 0
    try:
        with zipfile.ZipFile(zip_pfad) as archiv:
            namen = archiv.namelist()
            if gewaehlt:
                if gewaehlt not in namen:
                    raise ValueError(
                        f"Mitglied nicht im Takeout-Zip: {gewaehlt} ({zip_pfad})")
                auswahl = [gewaehlt]
            else:
                auswahl = _zip_kalender_eintraege(namen)
                if not auswahl:
                    raise ValueError(
                        f"Keine Kalenderdateien ({KALENDER_PRAEFIX}*.ics) im "
                        f"Takeout-Zip gefunden: {zip_pfad}")
            if isinstance(bericht, dict):
                bericht["kalender"] = len(auswahl)
            roh_teile = [archiv.read(eintrag) for eintrag in auswahl]
    except zipfile.BadZipFile as problem:
        raise ValueError(
            f"Takeout-Zip nicht lesbar ({problem.__class__.__name__}): "
            f"{zip_pfad}") from None
    except OSError as problem:
        raise ValueError(
            f"Takeout-Zip nicht lesbar ({problem.__class__.__name__}): "
            f"{zip_pfad}") from None
    texte = []
    for roh in roh_teile:
        try:
            texte.append(roh.decode("utf-8"))
        except UnicodeDecodeError:
            texte.append(roh.decode("latin-1", errors="replace"))
    return "\n".join(texte)


def zeilen_entfalten(text: str) -> list:
    """ICS-Zeilen entfalten: Fortsetzungszeilen (Leerzeichen/Tab) anhaengen.

    Reine Funktion. CRLF, CR und LF gelten alle als Zeilenende.
    """
    if not isinstance(text, str):
        return []
    zeilen = []
    for roh in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if roh[:1] in (" ", "\t") and zeilen:
            zeilen[-1] += roh[1:]
        else:
            zeilen.append(roh)
    return zeilen


def bloecke_sammeln(zeilen: list):
    """``VEVENT``-Bloecke einsammeln — Rueckgabe ``(bloecke, offen)``.

    ``bloecke`` ist eine Liste von Zeilenlisten (je ein VEVENT ohne die
    ``BEGIN``/``END``-Zeilen); ``offen`` ist ``1``, wenn am Ende ein
    ``BEGIN:VEVENT`` ohne ``END:VEVENT`` uebrig bleibt (defekt, nie still
    verschluckt). Reine Funktion.
    """
    bloecke = []
    aktuell = None
    for zeile in zeilen:
        if zeile == "BEGIN:VEVENT":
            aktuell = []
        elif zeile == "END:VEVENT":
            if aktuell is not None:
                bloecke.append(aktuell)
            aktuell = None
        elif aktuell is not None and zeile:
            aktuell.append(zeile)
    return bloecke, (1 if aktuell is not None else 0)


def _eigenschaft(zeile: str):
    """Eine ICS-Eigenschaftszeile in ``(NAME, params, wert)`` zerlegen."""
    if ":" not in zeile:
        return None, "", None
    links, _, wert = zeile.partition(":")
    teile = links.split(";")
    return teile[0].strip().upper(), ";".join(teile[1:]), wert


def _ics_datum(wert: str):
    """``(date, ganztags)`` aus einem ICS-Datumswert — sonst ``(None, False)``.

    Das Datum kommt aus den **ersten 8 Ziffern** des Werts; Zeitzonen werden
    nicht umgerechnet. Ganztags = ``VALUE=DATE`` (siehe ``termin_bauen``) oder
    fehlende Uhrzeit (kein ``T`` im Wert).
    """
    if not isinstance(wert, str):
        return None, False
    ziffern = "".join(zeichen for zeichen in wert if zeichen.isdigit())
    if len(ziffern) < 8:
        return None, False
    kern = ziffern[:8]
    try:
        tag = datetime.date(int(kern[:4]), int(kern[4:6]), int(kern[6:8]))
    except ValueError:
        return None, False
    return tag, ("T" not in wert)


def _titel_saeubern(wert: str) -> str:
    """Einen ICS-Titel von Maskierungen befreien und auf 120 Zeichen kuerzen."""
    if not isinstance(wert, str):
        return ""
    text = (wert.replace("\\n", " ").replace("\\N", " ")
                .replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\"))
    return text.strip()[:MAX_TITEL]


def termin_bauen(block: list):
    """Einen ICS-Block zu einem Termin machen — sonst ``None`` (defekt).

    Gelesen werden genau ``DTSTART``, ``DTEND``, ``SUMMARY``, ``RRULE`` und
    ``UID``. ``DESCRIPTION`` und ``LOCATION`` werden **nicht** gelesen. Ohne
    lesbares ``DTSTART`` ist der Block defekt und ergibt ``None``. Reine
    Funktion.
    """
    dtstart = None
    dtend = None
    summary = ""
    rrules = []
    for zeile in block:
        name, params, wert = _eigenschaft(zeile)
        if name == "DTSTART":
            tag, ganztags = _ics_datum(wert)
            if tag is not None:
                dtstart = (tag, ganztags or "VALUE=DATE" in params.upper())
        elif name == "DTEND":
            dtend, _ = _ics_datum(wert)
        elif name == "SUMMARY":
            summary = wert if wert is not None else ""
        elif name == "RRULE":
            if isinstance(wert, str) and wert.strip():
                rrules.append(wert.strip())
    if dtstart is None:
        return None
    beginn, ganztags = dtstart
    if dtend is None or dtend <= beginn:
        spanne = 1
        ende = None if dtend is None else dtend
    else:
        spanne = (dtend - beginn).days
        ende = dtend
    titel = _titel_saeubern(summary)
    if rrules:
        # Nur ``FREQ=YEARLY`` zaehlt als jaehrliche Wiederkehr; liegt eine
        # RRULE vor, greift der Titel-Rueckfall nicht (so beauftragt).
        jaehrlich = any("FREQ=YEARLY" in r.upper() for r in rrules)
    else:
        jaehrlich = any(wort in titel.lower() for wort in JAHRES_TITEL)
    return {
        "titel": titel,
        "beginn": beginn,
        "ende": ende,
        "ganztags": bool(ganztags),
        "wiederkehrend": bool(jaehrlich),
        "spanne": spanne,
    }


def termine_lesen(ics_text: str) -> dict:
    """Aus dem ICS-Text die Termine lesen — reine Funktion ohne Datei/Netz.

    Rueckgabe ``{\"termine\": [...], \"bloecke\": n, \"defekt\": n,
    \"offen\": n, \"ohne_titel\": n}``. Defekte Bloecke werden gezaehlt und
    gemeldet, nie still verschluckt.
    """
    bloecke, offen = bloecke_sammeln(zeilen_entfalten(ics_text))
    termine = []
    defekt = 0
    ohne_titel = 0
    for block in bloecke:
        termin = termin_bauen(block)
        if termin is None:
            defekt += 1
            continue
        if not termin["titel"]:
            ohne_titel += 1
        termine.append(termin)
    return {
        "termine": termine,
        "anzahl": len(termine),
        "bloecke": len(bloecke),
        "defekt": defekt,
        "offen": offen,
        "ohne_titel": ohne_titel,
    }


# ── 3. Fensterregel: Tag, +-1 Tag, jaehrliche Wiederkehr ──────────────────

def _jaehrlich_enthaelt(beginn, spanne: int, tag) -> bool:
    """Prueft, ob ein jaehrlich wiederkehrender Termin ``tag`` enthaelt.

    Verglichen werden **Tag+Monat**; geprueft werden die Jahre
    ``tag.jahr - 1``, ``tag.jahr`` und ``tag.jahr + 1``, damit der Jahreswechsel
    (29./30./31.12. gegen den 1.1.) korrekt mitzaehlt.
    """
    for jahr in (tag.year - 1, tag.year, tag.year + 1):
        occ = _datum_im_jahr(jahr, beginn.month, beginn.day)
        if occ is None:
            continue
        if occ <= tag < occ + datetime.timedelta(days=spanne):
            return True
    return False


def _termin_trifft(termin: dict, tag) -> bool:
    """Ob ein Termin den Tag ``tag`` enthaelt (Tag-Fenster der Fensterregel)."""
    if termin["wiederkehrend"]:
        return _jaehrlich_enthaelt(termin["beginn"], termin["spanne"], tag)
    beginn = termin["beginn"]
    return beginn <= tag < beginn + datetime.timedelta(days=termin["spanne"])


def _treffer_eintrag(termin: dict, tag) -> dict:
    """Den Ausgabe-Eintrag eines Treffers bauen (nur die Schema-Schluessel).

    Bei jaehrlicher Wiederkehr ist ``beginn`` das **Anlass-Jahr** + Monat/Tag;
    ``ende`` ist ``beginn`` + Spanne. Sonst steht das echte ICS-Datum (bzw.
    ``None`` ohne ``DTEND``). Kein weiterer Termin-Text.
    """
    if termin["wiederkehrend"]:
        beginn = _datum_im_jahr(tag.year, termin["beginn"].month,
                                termin["beginn"].day)
        ende = (beginn + datetime.timedelta(days=termin["spanne"])
                if beginn is not None else None)
    else:
        beginn = termin["beginn"]
        ende = termin["ende"]
    return {
        "beginn": beginn.isoformat() if beginn is not None else None,
        "ende": ende.isoformat() if ende is not None else None,
        "ganztags": termin["ganztags"],
        "quelle": QUELLE_ICS,
        "titel": termin["titel"],
        "wiederkehrend": termin["wiederkehrend"],
    }


def _treffer_sortierschluessel(eintrag: dict):
    """Feste Sortierung der Treffer: ``beginn`` aufsteigend, dann ``titel``."""
    return (eintrag.get("beginn") or "", eintrag.get("titel") or "")


# ── 4. Die Andockung bauen (rein, ohne I/O) ───────────────────────────────

def andocken(ereignisse: list, termine: list, *, stand: str | None = None,
             auch_nah: bool = False) -> dict:
    """Die Kalender-Andockung bauen — **reine** Funktion ohne Datei/Netz.

    Kein Dateizugriff, kein Netzzugriff, keine Seiteneffekte; die uebergebenen
    Strukturen werden nicht veraendert. ``stand`` ist injizierbar (Tests bleiben
    reproduzierbar). Die Reihenfolge der Ausgabe ist **wie die Eingabe**.
    """
    if not isinstance(ereignisse, list):
        raise ValueError("Die Ereignisse muessen eine Liste sein.")
    if not isinstance(termine, list):
        raise ValueError("Die Termine muessen eine Liste sein.")
    if stand is not None and (not isinstance(stand, str) or not stand.strip()):
        raise ValueError("Der Stand muss ein nicht-leerer Text sein.")
    if stand is None:
        stand = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

    knoten_liste = []
    for ereignis in ereignisse:
        if not isinstance(ereignis, dict):
            continue
        anlass_id = _text(ereignis.get("anlass_id"))
        tag = _datum_lesen(ereignis.get("datum"))
        treffer = []
        nah = 0
        if tag is not None:
            nah_delta = datetime.timedelta(days=NAH_TAGE)
            for termin in termine:
                if not isinstance(termin, dict):
                    continue
                if _termin_trifft(termin, tag):
                    treffer.append(_treffer_eintrag(termin, tag))
                elif (_termin_trifft(termin, tag - nah_delta)
                      or _termin_trifft(termin, tag + nah_delta)):
                    nah += 1
                    if auch_nah:
                        treffer.append(_treffer_eintrag(termin, tag))
            treffer.sort(key=_treffer_sortierschluessel)
        knoten_liste.append({
            "anlass_id": anlass_id,
            "anzahl_nah": nah,
            "anzahl_treffer": len(treffer),
            "art": ANDOCKUNG_ART,
            "datum": tag.isoformat() if tag is not None else None,
            "kennung": "K-" + anlass_id,
            "stand": stand,
            "treffer": treffer,
        })

    # Zusicherungen: die Zaehlregeln halten immer.
    for knoten in knoten_liste:
        assert knoten["anzahl_treffer"] == len(knoten["treffer"]), \
            "anzahl_treffer != len(treffer)"

    zahlen = {
        "ereignisse": len(knoten_liste),
        "ohne_datum": sum(1 for k in knoten_liste if k["datum"] is None),
        "mit_treffern": sum(1 for k in knoten_liste if k["anzahl_treffer"] > 0),
        "treffer": sum(k["anzahl_treffer"] for k in knoten_liste),
        "nah": sum(k["anzahl_nah"] for k in knoten_liste),
        "wiederkehrend": sum(1 for k in knoten_liste for t in k["treffer"]
                             if t["wiederkehrend"]),
        "max_treffer": max((k["anzahl_treffer"] for k in knoten_liste), default=0),
    }
    return {
        "art": ANDOCKUNG_ART,
        "stand": stand,
        "zahlen": zahlen,
        "ereignisse": knoten_liste,
    }


# ── 5. Eine Knotenzeile (reine Funktion) ──────────────────────────────────

def knoten_zeile(knoten: dict) -> str:
    """Einen Knoten als eine JSONL-Zeile — **rein**, kein Dateizugriff.

    Kodierung ``ensure_ascii=True`` und ``sort_keys=True`` (ASCII, kein
    Umlaut): dieselbe Eingabe ergibt immer dieselbe Zeile.
    """
    if not isinstance(knoten, dict):
        raise ValueError("Ein Knoten muss ein Woerterbuch sein.")
    return json.dumps(knoten, ensure_ascii=True, sort_keys=True)


# ── 6. Schreiben: atomar als JSONL, nur ausserhalb des Repos ──────────────

def _pruefe_ziel_ausserhalb_repo(pfad: str) -> str:
    """Sicherstellen, dass die Zieldatei AUSSERHALB des Repos liegt.

    Geprueft wird der absolut aufgeloeste Pfad (``abspath`` + ``normcase`` +
    ``commonpath``). Liegt das Ziel im Repo, gibt es eine deutsche
    ``ValueError``-Meldung — geschrieben wird dann nichts.
    """
    if not isinstance(pfad, str) or not pfad.strip():
        raise ValueError("Kein Zielpfad fuer die Kalender-Andockung angegeben.")
    ziel = os.path.normcase(os.path.abspath(pfad))
    repo = os.path.normcase(os.path.abspath(REPO))
    try:
        gemeinsam = os.path.commonpath([ziel, repo])
    except ValueError:                        # anderes Laufwerk: nie im Repo
        return pfad
    if gemeinsam == repo:
        raise ValueError(
            f"Zieldatei liegt IM Repo und ist nicht erlaubt: {pfad}\n"
            f"Die Kalender-Andockung gehoert ausserhalb des Repos (Standard: "
            f"{STANDARD_AUSGABE}); es wird NICHTS geschrieben.")
    return pfad


def andockung_schreiben(pfad: str, daten: dict) -> str:
    """Die Kalender-Andockung als JSONL schreiben — atomar, nur ausserhalb des Repos.

    Erst vollstaendig in ``<ziel>.tmp`` im **Zielordner** schreiben, dann per
    ``os.replace`` ersetzen: es entsteht nie eine halbe Datei. Scheitert das
    Schreiben, wird ausschliesslich die eigene temp-Datei wieder entfernt (die
    einzige Loeschung in diesem Modul) — eine vorhandene alte Zieldatei bleibt
    unangetastet. Ein Ziel im Repo ergibt eine deutsche ``ValueError``-Meldung.

    Rueckgabe: der geschriebene Pfad.
    """
    ziel = _pruefe_ziel_ausserhalb_repo(pfad)
    if not isinstance(daten, dict):
        raise ValueError("Keine Kalender-Andockung zum Schreiben uebergeben "
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


# ── 7. Der Bericht als Klartext (deutsch) ─────────────────────────────────

def zahlen_text(daten: dict, ics: dict | None = None) -> str:
    """Die Zahlen des Laufs als mehrzeiliger deutscher Klartext.

    Enthaelt Stand und **alle** Zaehler der Andockung (Ereignisse, ohne Datum,
    Treffer-Zeilen, Termine am Tag, Nah-Treffer, wiederkehrende Treffer,
    Maximum je Ereignis) sowie — falls ``ics`` uebergeben wird — die Zahlen des
    ICS-Lesers (Termine, Bloecke, defekte Bloecke, ungeschlossene Bloecke, ohne
    Titel). Fehlende Felder ergeben ``0`` statt eines Absturzes. Es stehen hier
    **keine** Termin-Titel.
    """
    d: dict = daten if isinstance(daten, dict) else {}
    roh_zahlen = d.get("zahlen")
    zahlen: dict = roh_zahlen if isinstance(roh_zahlen, dict) else {}

    def wert(name: str, quelle: dict = zahlen) -> int:
        zahl = _als_int(quelle.get(name))
        return zahl if zahl is not None else 0

    zeilen = [
        f"Kalender-Andockung N27 Schritt 3 - Stand "
        f"{_text(d.get('stand')) or 'unbekannt'}",
        f"Ereignisse: {_zahl(wert('ereignisse'))}   "
        f"ohne Datum: {_zahl(wert('ohne_datum'))}   "
        f"Treffer-Zeilen: {_zahl(wert('mit_treffern'))}",
        f"Termine am Tag (Treffer): {_zahl(wert('treffer'))}   "
        f"Nah-Treffer (+-1 Tag): {_zahl(wert('nah'))}   "
        f"davon wiederkehrend: {_zahl(wert('wiederkehrend'))}",
        f"Maximum Treffer je Ereignis: {_zahl(wert('max_treffer'))}",
    ]
    if isinstance(ics, dict):
        zeilen.append(
            f"ICS-Termine: {_zahl(wert('anzahl', ics))}   "
            f"Bloecke: {_zahl(wert('bloecke', ics))}   "
            f"defekte Bloecke: {_zahl(wert('defekt', ics))}   "
            f"ungeschlossen: {_zahl(wert('offen', ics))}   "
            f"ohne Titel: {_zahl(wert('ohne_titel', ics))}")
    zeilen.append("ohne weitere Termin-Texte (kein DESCRIPTION, kein LOCATION), "
                  "ausserhalb des Repos")
    return "\n".join(zeilen)


# ── 8. Kommandozeile ─────────────────────────────────────────────────────

def haupt(argv=None) -> int:
    """Kommandozeile: lesen, Zahlen zeigen, nur mit ``--schreiben`` ablegen.

    ``--ereignisse``/``--zip``/``--mitglied``/``--ausgabe`` haben die
    beauftragten Standardpfade; ``--trocken`` ist der **Standard**,
    ``--schreiben`` legt atomar ab; ``--auch-nah`` nimmt Nah-Termine in
    ``treffer`` auf. ``--limit N`` zeigt nur die ersten N Knoten auf der
    Konsole (Standard 5). Fehlende Eingaben oder ein Ziel im Repo ergeben eine
    deutsche Meldung auf ``stderr`` und Exit 2.
    """
    zerleger = argparse.ArgumentParser(
        description="Kalender-Andockung N27 Schritt 3: liest NUR die lokalen "
                    "Ereignis-Knoten und die ICS aus dem Takeout-Zip (per "
                    "zipfile) und haengt je Ereignis die Termine am Tag "
                    "(und +-1 Tag) an — nur Titel, kein weiterer Text.")
    zerleger.add_argument("--ereignisse", dest="ereignisse",
                          default=STANDARD_EREIGNISSE,
                          help="Ereignis-Knoten aus N27a (JSONL, ausserhalb des Repos)")
    zerleger.add_argument("--zip", dest="zip", default=STANDARD_ZIP,
                          help="Takeout-Zip mit der ICS (wird nur per zipfile gelesen)")
    zerleger.add_argument("--mitglied", dest="mitglied", default=STANDARD_MITGLIED,
                          help="Pfad der ICS innerhalb des Takeout-Zips "
                               "(Standard: leer — dann werden automatisch alle "
                               "Takeout/Kalender/*.ics gelesen)")
    zerleger.add_argument("--ausgabe", dest="ausgabe", default=STANDARD_AUSGABE,
                          help="Zieldatei der Andockung (JSONL, ausserhalb des Repos)")
    zerleger.add_argument("--trocken", action="store_true",
                          help="nur Zahlen zeigen, nichts schreiben (Standard)")
    zerleger.add_argument("--schreiben", action="store_true",
                          help="die Datei wirklich schreiben (atomar, nur "
                               "ausserhalb des Repos); --trocken hat Vorrang")
    zerleger.add_argument("--auch-nah", dest="auch_nah", action="store_true",
                          help="Termine +-1 Tag zusaetzlich in 'treffer' aufnehmen")
    zerleger.add_argument("--stand", dest="stand", default=None,
                          help="fester Zeitstempel fuer 'stand' (Standard: jetzt); "
                               "macht zwei Laeufe byte-gleich")
    zerleger.add_argument("--limit", dest="limit", type=int, default=5,
                          help="nur die ersten N Knoten auf der Konsole zeigen "
                               "(Standard 5)")
    args = zerleger.parse_args(argv)

    schreiben = bool(args.schreiben) and not bool(args.trocken)
    limit = args.limit

    try:
        if limit < 0:
            raise ValueError("Das Limit muss eine Zahl >= 0 sein.")
        _pruefe_ziel_ausserhalb_repo(args.ausgabe)
        ereignisse = ereignisse_laden(args.ereignisse)
        bericht: dict = {}
        ics_text = zip_ics_lesen(args.zip, args.mitglied, bericht)
        ics = termine_lesen(ics_text)
        daten = andocken(ereignisse, ics["termine"], stand=args.stand,
                         auch_nah=bool(args.auch_nah))
    except ValueError as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2

    print("Kalender-Andockung N27 Schritt 3 - "
          + ("SCHREIBEN" if schreiben else "TROCKENLAUF (es wird nichts geschrieben)"))
    print(f"Ereignisse: {args.ereignisse}")
    # Der Eintragsname im Zip ist ein Kontoname und wird NICHT ausgegeben. Bei
    # automatischer Vorgabe nennt die Konsole nur die Anzahl gefundener
    # Kalenderdateien.
    if _text(args.mitglied):
        print(f"Kalender (nur per zipfile): {args.zip} -> {_text(args.mitglied)}")
    else:
        print(f"Kalender (nur per zipfile): {args.zip} -> "
              f"Kalenderdateien: {_zahl(bericht.get('kalender', 0))}")
    if args.auch_nah:
        print("Zusatz: --auch-nah (Nah-Termine in 'treffer')")
    print(zahlen_text(daten, ics))

    knoten = daten["ereignisse"]
    for eintrag in knoten[:limit]:
        print(knoten_zeile(eintrag))
    if limit < len(knoten):
        print(f"... und {_zahl(len(knoten) - limit)} weitere Knoten")

    if not schreiben:
        print(f"Trockenlauf: {args.ausgabe} wurde NICHT geschrieben.")
        return 0

    try:
        ziel = andockung_schreiben(args.ausgabe, daten)
    except ValueError as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2
    print(f"Kalender-Andockung geschrieben: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(haupt())
