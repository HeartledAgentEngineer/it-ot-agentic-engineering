"""Screenshot-Vorsortierung: EIN Vision-Blick je Screenshot -> Muell oder behalten.

Was dieses Werkzeug tut (27.09.2026, Auftrag "Screenshots: brauchbar oder Muell?"):

  Aus Sebastians pCloud-Ordner ``Bilder & Videos/Screenshots`` (und dessen
  Unterordnern) wird **jeder Screenshot einmal angesehen** und in eine feste,
  kleine Auswahl eingeordnet:

    * ``muell``               — Systemdialog, Fehlermeldung, versehentlich
                                aufgenommen, Statusleiste, leerer Bildschirm,
                                Einstellungen ohne Nutzen
    * ``behalten-nuetzlich``  — Ticket, Termin, Bestaetigung, Rechnung, Adresse,
                                Rezept, Karte, Fahrplan (etwas, das spaeter
                                gebraucht wird)
    * ``behalten-persoenlich``— Chat mit Menschen, Meme, Foto,
                                Sprachnachricht-Screenshot, Profil, wichtiger
                                Moment
    * ``unklar``              — nicht entscheidbar (auch JEDE Antwort, deren
                                Klasse nicht in dieser Liste steht)

  Dazu je Bild ein **Thema** aus fester Liste (``THEMEN``) und ein **Befund**
  (kurze deutsche Beschreibung, hoechstens ``BEFUND_MAX`` Zeichen). Der Prompt
  verlangt ausdruecklich: keine Namen von Personen, keine Adressen, keine
  Telefonnummern.

Rechenweg je Bild (billigste Stufe zuerst):
  1. Ordner per ``listfolder`` finden — Basisordner + Unterordner, je Ebene
     genau EINE Anfrage (kein rekursiver Vollscan; der Baum ist winzig: live
     1 Unterordner).
  2. **Nur das Vorschaubild** holen: ``dienst.thumb(fileid, groesse)`` aus
     ``backend/app/services/pcloud_service.py`` (Standard ``800x800``, die
     groesste Vorschaugroesse des Dienstes; das Original wird NICHT geladen).
     Messgrund fuer 800x800 statt 120x120 (27.09.2026): bei 120x120 blieb ein
     grosser Teil der Screenshots ``unklar`` („Text nicht lesbar"), weil
     Screenshot-Inhalt vor allem Text ist; 800x800 kostet rund 2000 statt 400
     Eingabe-Tokens je Bild — Bruchteile eines Cents (siehe Doku).
  3. Das Bild wird **nur im Arbeitsspeicher** gehalten: Bytes -> base64 ->
     ``data:``-URL in GENAU EINEM ``POST {basis}/chat/completions``
     (Vision-Modell, Standard ``google/gemini-2.5-flash``). Es wird NICHT
     kopiert, NICHT zwischengespeichert, NICHT auf Platte geschrieben und
     NICHT in die pCloud gelegt.
  4. Antwort robust zerlegen (JSON-Zaeune, Vor-/Nachtext; kaputter Text =
     Fehler, kein Raten) und in die feste Auswahl normalisieren:
     unbekannte Klasse -> ``unklar``, unbekanntes Thema -> ``Sonstiges``,
     fehlender Befund -> leerer Text.

Der Aufrufweg zu OpenRouter (Transport ``sende_aufruf`` mit Wiederholungen,
Zerlegung ``antwort_zerlegen``, Entschaerfung ``geheimnis_entfernen``,
Kostenrechnung ``kosten_berechnen``, Schluessel-Suche ``schluessel_finden``)
ist **aus dem Themen-Werkzeug ``foto_themen_vision.py`` wiederverwendet** —
derselbe bewiesene Weg, keine zweite Kopie. Dieses Werkzeug holt sich das
Nachbarmodul ueber seinen Pfad (Muster ``themen_katalog`` dort).

Kostenbremse (``--kosten-obergrenze``, Standard ``0.10`` USD):
  Vor JEDEM Bild wird geprueft, ob die aufgelaufenen Kosten die Obergrenze
  erreicht haben; ist das der Fall, **bricht der Lauf sauber ab** (deutsche
  Meldung mit „Kostenbremse", bereits bearbeitete Bilder stehen vollstaendig
  in der Ausgabe, Exit-Code bleibt 0). Eine Obergrenze von ``0`` oder kleiner
  schaltet die Bremse ausdruecklich ab. Die Kosten je Bild kommen aus
  ``tokens_ein``/``tokens_aus`` der Antwort und den Preisen des Modells
  (``--preis-ein``/``--preis-aus`` je 1 Mio Tokens; Standard sind die live von
  OpenRouter ``/models`` gelesenen Preise von ``google/gemini-2.5-flash``:
  ``0.30`` ein / ``2.50`` aus — Stand 27.09.2026). Bei einem ANDEREN Modell
  ohne eigene Preise wird ausdruecklich gewarnt, dass die Kostenzahl eine
  Annahme ist.

Ausgabe (NUR ausserhalb des Repos — dort liegen private Dateinamen):
  ``~/foto_sortierung/screenshots_triage.jsonl``, **anhangend** (nie
  ueberschrieben), eine JSON-Zeile je Bild, sofort geflusht:
    datei (nur Dateiname), fileid, ordner, klasse, thema, befund,
    tokens (Summe), tokens_ein, tokens_aus, kosten_usd, modell, zeit
  Fehlgeschlagene Bilder stehen als Zeile mit ``fehler`` drin (ohne klasse)
  und werden beim naechsten Lauf erneut versucht — die Datei ist damit der
  Fortsetzungspunkt (``erledigt`` = Zeile ohne ``fehler`` und mit ``klasse``).
  ``--wiederholen`` erzwingt auch fuer erledigte Bilder einen neuen Blick.

Was dieses Werkzeug ausdruecklich NICHT tut:
  * **kein Loeschen und kein Verschieben** — es gibt im Code keinen Befehl
    dafuer (und keine pCloud-Schreibmethode): gegenueber der pCloud wird
    ausschliesslich gelesen (``liste`` + ``thumb``).
  * **keine Datei auf der Platte** — Bilder leben nur im Arbeitsspeicher;
    geschrieben wird genau eine JSONL-Zeile je Bild (Text).
  * kein Download der Originale, kein zweiter Anbieter, kein Codex.
  * der Schluessel bleibt geheim: nie geloggt, nie gedruckt, aus jeder
    Meldung und jeder Modellantwort entfernt (``geheimnis_entfernen``).

Aufruf (venv des Backends, enthaelt httpx/PIL) — Datei:

    cd backend
    .venv/Scripts/python ../tools/foto_sortierung/screenshots_triage.py --trocken
    .venv/Scripts/python ../tools/foto_sortierung/screenshots_triage.py --grenze 25

Als Modul (Tests, Skripte): ``main(argv=[...], dienst=..., sende=..., env_pfade=[...])``.
``dienst`` (pCloud, nur lesend) und ``sende`` (Vision-Transport) sind fuer
Tests injizierbar; ohne sie werden die echten Wege gebaut.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import importlib
import importlib.util
import json
import os
import re
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent


def _modul_aus_pfad(pfad: str, name: str):
    """Ein Nachbarmodul per Pfad laden — funktioniert als Skript UND als Import."""
    spez = importlib.util.spec_from_file_location(name, pfad)
    if spez is None or spez.loader is None:
        raise RuntimeError(f"Modul nicht gefunden: {pfad}")
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


# Der bewiesene OpenRouter-Weg liegt im Themen-Werkzeug daneben; hier wird er
# wiederverwendet statt kopiert (Transport, Zerlegung, Geheimnis-Schutz,
# Kostenrechnung, Schluessel-Suche). Die Ausnahme-Klassen kommen mit.
_vision = _modul_aus_pfad(os.path.join(HIER, "foto_themen_vision.py"),
                          "foto_themen_vision")

FotoVisionFehler = _vision.FotoVisionFehler
FotoVisionNetzfehler = _vision.FotoVisionNetzfehler
sende_aufruf = _vision.sende_aufruf
antwort_zerlegen = _vision.antwort_zerlegen
geheimnis_entfernen = _vision.geheimnis_entfernen
kosten_berechnen = _vision.kosten_berechnen
schluessel_finden = _vision.schluessel_finden
VERSUCHE = _vision.VERSUCHE

# ── Feste Werte ────────────────────────────────────────────────────────────

# Wo die Screenshots liegen (pCloud-Pfad ab der Wurzel) und wo die Ausgabe
# hingehoert: NIE ins Repo (dort liegen private Dateinamen).
STANDARD_PFAD = "Bilder & Videos/Screenshots"
STANDARD_AUSGABE = os.path.join(os.path.expanduser("~"), "foto_sortierung",
                                "screenshots_triage.jsonl")

# Nur diese Dateiendungen gelten als Bild; alles andere (z. B. desktop.ini)
# wird uebergangen.
BILD_ENDUNGEN = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp",
                 ".heic", ".heif", ".tif", ".tiff")

# Die feste, kleine Auswahl — das Modell darf NICHTS anderes waehlen.
KLASSEN = ("muell", "behalten-nuetzlich", "behalten-persoenlich", "unklar")
KLASSE_UNKLAR = "unklar"
THEMEN = ("Chat", "Ticket", "Termin", "Rechnung", "Karte", "Meme",
          "Systemdialog", "Fehlermeldung", "Einkauf", "Rezept", "Foto",
          "Video", "Sonstiges")
THEMA_SONSTIGES = "Sonstiges"

# Befund: eine Zeile, hoechstens so viele Zeichen.
BEFUND_MAX = 100

# Rekursionstiefe beim Sammeln der Dateien (Basisordner = 0). Der Screenshot-
# Baum ist winzig (live: 1 Unterordner); die Grenze schuetzt vor Zyklen.
MAX_TIEFE = 3

# Antwortlaenge des Modells: ein kleines JSON-Objekt, viel Reserve.
MAX_TOKENS = 400

STANDARD_MODELL = "google/gemini-2.5-flash"
STANDARD_BASIS = "https://openrouter.ai/api/v1"

# Vorschaugroessen: genau die, die der pCloud-Dienst erlaubt (sonst bricht er
# mit klarer Meldung ab). Standard ist 800x800 statt 120x120: am 27.09.2026
# gemessen — bei 120x120 blieb ein grosser Teil der Screenshots "unklar", weil
# Text nicht lesbar war; 800x800 (live geprueft, derselbe getthumbs-Endpunkt)
# kostet rund 2000 statt 400 Eingabe-Tokens je Bild, also weiter Bruchteile
# eines Cents. Kein Original, weiterhin nur ein Vorschaubild.
ERLAUBTE_GROESSEN = ("32x32", "120x120", "480x480", "800x800")
STANDARD_GROESSE = "800x800"

# Kostenbremse und Stichprobe.
STANDARD_GRENZE = 25
STANDARD_KOSTEN_OBERGRENZE = 0.10

# Preise je 1 Mio Tokens in USD — live aus OpenRouter ``/models`` gelesen
# (27.09.2026) fuer STANDARD_MODELL. Fuer andere Modelle sind sie eine
# Annahme; das Werkzeug sagt das dann ausdruecklich dazu.
PREIS_EIN_STANDARD = 0.30
PREIS_AUS_STANDARD = 2.50
PREIS_STAND = "27.09.2026"

# Umlaut-schlanke Schreibweise: "Müll" -> "muell", "behalten-nützlich" ->
# "behaltennuetzlich". So findet die Normalisierung auch Antworten, die nicht
# WORT FUER WORT der Vorgabe folgen.
SCHLANK_MUSTER = re.compile(r"[\s_\-]+")
UMLAUTE = (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"))


class ScreenshotFehler(FotoVisionFehler):
    """Fehler dieses Werkzeugs — die Meldung enthaelt nie ein Geheimnis."""


def _schlank(text: str) -> str:
    """Text vergleichbar machen: klein, ohne Trenner, Umlaute ausgeschrieben."""
    sauber = SCHLANK_MUSTER.sub("", str(text or "").casefold())
    for zeichen, ersatz in UMLAUTE:
        sauber = sauber.replace(zeichen, ersatz)
    return sauber


def klasse_normalisieren(wert) -> str:
    """Die feste Klasse aus der Modellantwort — Unbekanntes wird ``unklar``.

    Reihenfolge: genauer Wortlaut, dann schlanke Schreibweise (Gross-/
    Kleinschreibung, Trenner, Umlaute). Passt nichts, ist das Ergebnis
    ``unklar`` — es wird keine Klasse geraten (auch eine Antwort wie "eher
    behalten" wird nicht ausgelegt, sondern ``unklar``).
    """
    if not isinstance(wert, str):
        return KLASSE_UNKLAR
    ziel = _schlank(wert)
    for klasse in KLASSEN:
        if _schlank(klasse) == ziel:
            return klasse
    return KLASSE_UNKLAR


def thema_normalisieren(wert) -> str:
    """Das feste Thema aus der Modellantwort — Unbekanntes wird ``Sonstiges``."""
    if not isinstance(wert, str):
        return THEMA_SONSTIGES
    ziel = _schlank(wert)
    for thema in THEMEN:
        if _schlank(thema) == ziel:
            return thema
    return THEMA_SONSTIGES


def befund_normalisieren(wert) -> str:
    """Befund auf eine Zeile bringen und bei ``BEFUND_MAX`` Zeichen kappen.

    Fehlende oder unbrauchbare Werte ergeben einen leeren Text — der Befund
    ist Zusatzinformation, kein Pflichtfeld.
    """
    if not isinstance(wert, str):
        return ""
    sauber = re.sub(r"\s+", " ", wert.replace("\r", " ").replace("\n", " ")).strip()
    return sauber[:BEFUND_MAX].strip()


def einordnung_uebernehmen(daten: dict, schluessel: str = "") -> dict:
    """Die drei Felder aus der Modellantwort pruefen (rein, ohne I/O).

    Rueckgabe ``{klasse, thema, befund}`` in der festen Auswahl. Vorher laeuft
    der Befund durch ``geheimnis_entfernen``: ein Modell, das den Schluessel
    (oder ein fremdes ``sk_``-Muster) wiederholt, darf ihn so nicht in die
    Ausgabe bringen.
    """
    if not isinstance(daten, dict):
        raise ScreenshotFehler("Modellantwort ist kein JSON-Objekt.")
    return {
        "klasse": klasse_normalisieren(daten.get("klasse")),
        "thema": thema_normalisieren(daten.get("thema")),
        "befund": geheimnis_entfernen(befund_normalisieren(daten.get("befund")),
                                      schluessel),
    }


# ── Schutz: Ausgabe nur ausserhalb des Repos ───────────────────────────────

def _pruefe_ausgabe(pfad: str) -> str:
    """Sicherstellen, dass die Ausgabedatei AUSSERHALB des Repos liegt.

    Geprueft wird der absolut aufgeloeste Pfad; Gross-/Kleinschreibung und
    Schraeg-/Rueckwaertsstriche spielen keine Rolle (``abspath`` +
    ``normcase`` + ``commonpath``). Liegt das Ziel im Repo, gibt es eine
    deutsche Klartext-Meldung und SystemExit(2) — es wird dann nichts geholt,
    nichts gesendet und nichts geschrieben. Das gilt auch fuer ``--trocken``.
    """
    ziel = os.path.normcase(os.path.abspath(pfad))
    repo = os.path.normcase(os.path.abspath(REPO))
    try:
        gemeinsam = os.path.commonpath([ziel, repo])
    except ValueError:                       # anderes Laufwerk: nie im Repo
        return pfad
    if gemeinsam == repo:
        print(f"Ausgabedatei liegt IM Repo und ist nicht erlaubt: {pfad}\n"
              f"Ausgaben gehoeren ausserhalb des Repos (Standard: "
              f"{STANDARD_AUSGABE}); es wird NICHTS geschrieben und NICHTS "
              f"gesendet.")
        raise SystemExit(2)
    return pfad


def pruefe_groesse(groesse: str) -> None:
    """Nur die Vorschaugroessen zulassen, die der pCloud-Dienst kennt."""
    if groesse not in ERLAUBTE_GROESSEN:
        raise ScreenshotFehler(
            "Unbekannte Vorschaugroesse: erlaubt sind "
            + " und ".join(ERLAUBTE_GROESSEN) + ".")


# ── pCloud: nur lesend (listfolder ueber den Dienst + getthumbs) ───────────

def pcloud_dienst_laden():
    """Den lesenden pCloud-Dienst holen — erst hier, damit der Import leicht bleibt.

    Das Werkzeug liegt ausserhalb des Backends; ein Import auf Modulebene
    wuerde beim Laden der Datei die Backend-Konfiguration mitziehen. Deshalb
    kommt ``backend`` erst hier in den Suchpfad (Muster:
    ``tools/foto_sortierung/foto_kategorien.py``, ausschliesslich LESEND).
    """
    backend = os.path.join(REPO, "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    modul = importlib.import_module("app.services.pcloud_service")
    return modul.pcloud_service


def pfad_teile(pfad: str) -> list[str]:
    """'Bilder & Videos/Screenshots' -> ['Bilder & Videos', 'Screenshots']."""
    teile = (pfad or "").replace("\\", "/").split("/")
    return [teil.strip() for teil in teile if teil.strip()]


def _inhalt(dienst, folderid: int) -> list[dict]:
    """Eintraege EINES Ordners — genau EIN ``listfolder`` je Aufruf."""
    return list(dienst.liste(folderid) or [])


def ordner_finden(dienst, teile: list[str]) -> int | None:
    """folderid eines Ordnerpfads ab der Wurzel — None, wenn ein Teil fehlt.

    Erst genauer Name, dann ohne Gross-/Kleinschreibung (Muster aus
    ``foto_themen.py``).
    """
    folderid = 0
    for teil in teile:
        unterordner = [e for e in _inhalt(dienst, folderid) if e.get("ist_ordner")]
        treffer = next((e for e in unterordner if e.get("name") == teil), None)
        if treffer is None:
            treffer = next((e for e in unterordner
                            if str(e.get("name") or "").casefold() == teil.casefold()),
                           None)
        if treffer is None or treffer.get("folderid") is None:
            return None
        folderid = int(treffer["folderid"])
    return folderid


def ist_bild(name: str) -> bool:
    """True, wenn der Dateiname auf eine Bildendung endet."""
    return str(name or "").lower().endswith(BILD_ENDUNGEN)


def screenshots_sammeln(dienst, teile: list[str], max_tiefe: int = MAX_TIEFE) -> list[dict]:
    """Alle Bilddateien im Screenshot-Ordner UND seinen Unterordnern.

    Je Ebene genau ein ``listfolder`` (kein rekursiver Vollscan des Kontos);
    die Tiefe ist begrenzt. Rueckgabe je Datei ``{name, fileid, ordner}`` —
    ``ordner`` ist der Pfad RELATIV zum Basisordner ("" = direkt darin), damit
    gleichnamige Dateien aus verschiedenen Unterordnern unterscheidbar bleiben.
    Nicht-Bilder (z. B. ``desktop.ini``) werden uebergangen. Sortiert nach
    (Ordner, Name) — reproduzierbar, damit ``--grenze`` immer dieselbe
    Stichprobe zieht.

    Fehlt der Basisordner oder ein Unterordner, gibt es eine
    ``ScreenshotFehler`` — es wird nichts erfunden.
    """
    basis = ordner_finden(dienst, teile)
    if basis is None:
        raise ScreenshotFehler(
            "Screenshot-Ordner nicht gefunden: " + "/".join(teile))

    ergebnis: list[dict] = []

    def _sammeln(folderid: int, relativ: str, tiefe: int) -> None:
        for eintrag in _inhalt(dienst, folderid):
            name = str(eintrag.get("name") or "")
            if eintrag.get("ist_ordner"):
                if tiefe < max_tiefe and eintrag.get("folderid") is not None:
                    unter = f"{relativ}/{name}" if relativ else name
                    _sammeln(int(eintrag["folderid"]), unter, tiefe + 1)
                continue
            if not ist_bild(name) or eintrag.get("fileid") is None:
                continue
            ergebnis.append({"name": name, "fileid": int(eintrag["fileid"]),
                             "ordner": relativ})

    _sammeln(basis, "", 0)
    ergebnis.sort(key=lambda e: (e["ordner"].casefold(), e["name"].casefold()))
    return ergebnis


# ── Prompt und Anfrage (reine Funktionen) ──────────────────────────────────

def prompt_bauen() -> str:
    """Den strengen deutschen Prompt bauen — beide festen Listen WORT FUER WORT.

    Die Klassen- und Themenlisten stehen vollstaendig ausgeschrieben im Text
    (dieselben Eintraege wie ``KLASSEN``/``THEMEN``), damit das Modell nur aus
    dem festen Wortschatz waehlen kann. Der Befund ist auf ``BEFUND_MAX``
    Zeichen begrenzt, und personenbezogene Angaben sind ausdruecklich
    ausgeschlossen.
    """
    klasse_block = (
        f'  "klasse":  GENAU EINER dieser vier Werte, WORT FUER WORT:\n'
        f"             " + " | ".join(KLASSEN) + "\n"
        "             muell                = Systemdialog, Fehlermeldung, versehentlich\n"
        "                                    aufgenommen, Statusleiste, leerer\n"
        "                                    Bildschirm, Einstellungen ohne Nutzen\n"
        "             behalten-nuetzlich   = Ticket, Termin, Bestaetigung, Rechnung,\n"
        "                                    Adresse, Rezept, Karte, Fahrplan (etwas,\n"
        "                                    das spaeter gebraucht wird)\n"
        "             behalten-persoenlich = Chat mit Menschen, Meme, Foto,\n"
        "                                    Sprachnachricht-Screenshot, Profil,\n"
        "                                    wichtiger Moment\n"
        "             unklar               = nicht entscheidbar\n"
    )
    thema_block = (
        f'  "thema":   GENAU EINER dieser Werte, WORT FUER WORT:\n'
        f"             " + " | ".join(THEMEN) + "\n"
    )
    return (
        "Du siehst GENAU EINEN Screenshot (Vorschaubild, absichtlich klein).\n"
        "Ordne ihn ein. Antworte auf Deutsch.\n"
        "\n"
        "Antworte AUSSCHLIESSLICH mit einem einzigen JSON-Objekt, ohne Vor- oder\n"
        "Nachtext, ohne Markdown. Genau diese Schluessel:\n"
        + klasse_block + thema_block +
        f'  "befund":  EIN kurzer deutscher Satz, hoechstens {BEFUND_MAX} Zeichen:\n'
        "             was auf dem Screenshot zu sehen ist. KEINE Namen von\n"
        "             Personen, keine Adressen, keine Telefonnummern.\n"
        "\n"
        "Wenn du unsicher bist, nimm die Klasse unklar statt zu raten.\n"
        "Das JSON-Objekt ist die gesamte Antwort."
    )


def medientyp(bild: bytes) -> str:
    """Medientyp aus den ersten Bytes ableiten (wie ``pcloud_service``).

    Unbekanntes bleibt JPEG — das ist die Form, die ``getthumbs`` liefert.
    """
    if bild[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if bild[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if bild[:4] == b"GIF8":
        return "image/gif"
    return "image/jpeg"


def bild_daten_uri(bild: bytes) -> str:
    """Das Vorschaubild als ``data:``-URL (base64) — NUR im Arbeitsspeicher.

    Die Bytes werden nie kopiert, nie zwischengespeichert und nie auf Platte
    geschrieben; der Inhalt wird nie gedruckt.
    """
    if not bild:
        raise ScreenshotFehler("Vorschaubild war leer.")
    return (f"data:{medientyp(bild)};base64,"
            + base64.b64encode(bild).decode("ascii"))


def anfrage_bauen(modell: str, daten_uri: str, max_tokens: int = MAX_TOKENS) -> dict:
    """Den Anfragekoerper fuer OpenRouter bauen (content-Array mit Bild)."""
    return {
        "model": modell,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_bauen()},
                    {"type": "image_url", "image_url": {"url": daten_uri}},
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
    }


# ── Kostenbremse (rein) ────────────────────────────────────────────────────

def bremse_erreicht(kosten_gesamt, obergrenze) -> bool:
    """True, wenn die Kostenobergrenze erreicht ist — sonst False.

    ``0`` oder kleiner schaltet die Bremse ausdruecklich ab; ein fehlender
    Wert (``None``) ebenso. Die Pruefung laeuft VOR jedem Senden.
    """
    if obergrenze is None:
        return False
    try:
        grenze = float(obergrenze)
    except (TypeError, ValueError):
        return False
    if grenze <= 0:
        return False
    try:
        stand = float(kosten_gesamt)
    except (TypeError, ValueError):
        return False
    return stand >= grenze


# ── Ausgabe (JSONL, anhangend) ─────────────────────────────────────────────

def jsonl_anhaengen(jsonl_pfad: str, eintrag: dict) -> None:
    """Eine Zeile an die Ausgabe anhaengen und sofort flushen.

    Nur anhaengend: die Datei wird nie ueberschrieben oder geleert (sie ist
    der Fortsetzungspunkt ueber mehrere Laeufe).
    """
    ordner = os.path.dirname(os.path.abspath(jsonl_pfad))
    os.makedirs(ordner, exist_ok=True)
    with open(jsonl_pfad, "a", encoding="utf-8") as datei:
        datei.write(json.dumps(eintrag, ensure_ascii=False) + "\n")
        datei.flush()


def erledigt_lesen(jsonl_pfad: str) -> dict:
    """``{fileid: letzter Eintrag}`` aus der Ausgabe — der Fortsetzungspunkt.

    Unlesbare Zeilen werden uebersprungen (eine kaputte Zeile darf den Lauf
    nicht anhalten); die letzte Zeile zu einer fileid gewinnt.
    """
    ergebnis: dict[int, dict] = {}
    if not os.path.isfile(jsonl_pfad):
        return ergebnis
    with open(jsonl_pfad, encoding="utf-8", errors="replace") as datei:
        for zeile in datei:
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                eintrag = json.loads(zeile)
            except ValueError:
                continue
            if isinstance(eintrag, dict) and eintrag.get("fileid") is not None:
                try:
                    ergebnis[int(eintrag["fileid"])] = eintrag
                except (TypeError, ValueError):
                    continue
    return ergebnis


def ist_erledigt(eintrag) -> bool:
    """True, wenn dieser Screenshot schon eingeordnet wurde.

    Eine Zeile mit ``fehler`` ist NICHT erledigt — solche Bilder werden beim
    naechsten Lauf erneut versucht (ehrlich statt still).
    """
    if not isinstance(eintrag, dict):
        return False
    return not eintrag.get("fehler") and bool(eintrag.get("klasse"))


def zusammenfassung_zaehlen(ergebnisse: list[dict]) -> dict:
    """Anzahl je Klasse und je Thema (rein — nur die festen Listen).

    Gezaehlt werden nur Einordnungen; Fehlerzeilen tauchen hier nicht auf.
    """
    je_klasse = {klasse: 0 for klasse in KLASSEN}
    je_thema = {thema: 0 for thema in THEMEN}
    for ergebnis in ergebnisse:
        klasse = ergebnis.get("klasse")
        if klasse in je_klasse:
            je_klasse[klasse] += 1
        thema = ergebnis.get("thema")
        if thema in je_thema:
            je_thema[thema] += 1
    return {"je_klasse": je_klasse, "je_thema": je_thema}


def beispiele_je_klasse(ergebnisse: list[dict], anzahl: int = 5) -> dict:
    """Je Klasse bis zu ``anzahl`` Beispiele (Datei, Thema, Befund) — in Reihenfolge."""
    gesammelt: dict[str, list[dict]] = {klasse: [] for klasse in KLASSEN}
    for ergebnis in ergebnisse:
        klasse = ergebnis.get("klasse")
        if klasse in gesammelt and len(gesammelt[klasse]) < anzahl:
            gesammelt[klasse].append({
                "datei": ergebnis.get("datei", ""),
                "ordner": ergebnis.get("ordner", ""),
                "thema": ergebnis.get("thema", ""),
                "befund": ergebnis.get("befund", ""),
            })
    return gesammelt


def fehler_meldung(problem: Exception, schluessel: str = "") -> str:
    """Klartext einer Fehlermeldung — fremde Fehler nur als Klassenname.

    Meldungen aus diesem Werkzeug und aus dem pCloud-Dienst sind bereits ohne
    Geheimnis und werden woertlich genommen; alles Fremde koennte die volle
    URL samt Schluessel tragen und wird deshalb auf den Klassennamen
    eingekuerzt.
    """
    eigene = ("screenshots_triage", "__main__", "foto_themen_vision",
              "pcloud_service", "app.services.pcloud_service")
    if problem.__class__.__module__ in eigene:
        text = str(problem)
    else:
        text = f"unerwarteter Fehler ({problem.__class__.__name__})"
    return geheimnis_entfernen(text, schluessel)


# ── Kommandozeile ──────────────────────────────────────────────────────────

def _dateizeile(eintrag: dict) -> str:
    return f"{eintrag['name']}" + (f"   [{eintrag['ordner']}]"
                                   if eintrag["ordner"] else "")


def main(argv=None, dienst=None, sende=None, env_pfade=None) -> int:
    """Kommandozeilen-Teil.

    ``dienst`` (pCloud, nur lesend) und ``sende`` (Vision-Transport) sowie
    ``env_pfade`` (Schluessel-Suche) sind fuer Tests injizierbar.
    """
    zerleger = argparse.ArgumentParser(
        description="Screenshot-Vorsortierung: EIN Vision-Blick je Screenshot "
                    "-> muell / behalten-nuetzlich / behalten-persoenlich / "
                    "unklar, mit Thema und Befund. Nur lesend: nichts loeschen, "
                    "nichts verschieben, keine Originale laden.")
    zerleger.add_argument("--pfad", default=STANDARD_PFAD,
                          help=f"pCloud-Ordner (Standard: {STANDARD_PFAD})")
    zerleger.add_argument("--ausgabe", default=STANDARD_AUSGABE,
                          help="JSONL-Ziel (ausserhalb des Repos)")
    zerleger.add_argument("--grenze", type=int, default=STANDARD_GRENZE,
                          help=f"Anzahl Bilder (Standard {STANDARD_GRENZE}; "
                               "0 oder kleiner = alle)")
    zerleger.add_argument("--wiederholen", action="store_true",
                          help="auch schon eingeordnete Bilder erneut ansehen")
    zerleger.add_argument("--trocken", action="store_true",
                          help="nur zaehlen und auflisten (sendet NICHTS, "
                               "holt kein Vorschaubild, schreibt nichts)")
    zerleger.add_argument("--kosten-obergrenze", dest="kosten_obergrenze",
                          type=float, default=STANDARD_KOSTEN_OBERGRENZE,
                          help="USD-Grenze; danach sauberer Abbruch "
                               f"(Standard {STANDARD_KOSTEN_OBERGRENZE}; "
                               "0 = keine Bremse)")
    zerleger.add_argument("--groesse", default=STANDARD_GROESSE,
                          help=f"Vorschaugroesse (Standard {STANDARD_GROESSE}; "
                               f"erlaubt: {', '.join(ERLAUBTE_GROESSEN)})")
    zerleger.add_argument("--modell", default=STANDARD_MODELL,
                          help=f"Vision-Modell (Standard {STANDARD_MODELL})")
    zerleger.add_argument("--basis", default=STANDARD_BASIS,
                          help="OpenRouter-Basis-URL")
    zerleger.add_argument("--preis-ein", dest="preis_ein", type=float,
                          default=None,
                          help=f"USD je 1 Mio Eingabe-Tokens (Standard "
                               f"{PREIS_EIN_STANDARD} fuer {STANDARD_MODELL})")
    zerleger.add_argument("--preis-aus", dest="preis_aus", type=float,
                          default=None,
                          help=f"USD je 1 Mio Ausgabe-Tokens (Standard "
                               f"{PREIS_AUS_STANDARD} fuer {STANDARD_MODELL})")
    args = zerleger.parse_args(argv)

    # Ausgabeziel ZUERST pruefen: Ausgaben gehoeren ausserhalb des Repos.
    # Das gilt fuer jeden Modus, auch --trocken.
    _pruefe_ausgabe(args.ausgabe)

    try:
        pruefe_groesse(args.groesse)
    except ScreenshotFehler as problem:
        print(str(problem))
        return 2

    preis_ein = PREIS_EIN_STANDARD if args.preis_ein is None else args.preis_ein
    preis_aus = PREIS_AUS_STANDARD if args.preis_aus is None else args.preis_aus
    preise_aus_standard = (args.preis_ein is None and args.preis_aus is None
                           and args.modell != STANDARD_MODELL)

    start = time.time()
    print(f"Quelle: pCloud '{args.pfad}'   Vorschaugroesse {args.groesse}")
    print(f"Ausgabe: {args.ausgabe}")
    print(f"Modell: {args.modell}   EIN Aufruf je Bild   "
          f"Kostenbremse: "
          + (f"{args.kosten_obergrenze} USD" if args.kosten_obergrenze else "AUS")
          + f"   Preise je 1 Mio Tokens: {preis_ein} ein / {preis_aus} aus")
    if args.modell != STANDARD_MODELL and args.preis_ein is None and args.preis_aus is None:
        print(f"  HINWEIS: die Preise sind die von {STANDARD_MODELL} "
              f"({PREIS_STAND}) — fuer {args.modell} ist die Kostenzahl eine "
              f"Annahme (--preis-ein/--preis-aus setzen).")

    # ── Dateien sammeln (nur lesend: listfolder je Ebene) ──────────────────
    try:
        dienst = dienst or pcloud_dienst_laden()
        alle = screenshots_sammeln(dienst, pfad_teile(args.pfad))
    except Exception as problem:
        print(f"Screenshots konnten nicht gelesen werden: "
              f"{fehler_meldung(problem)}")
        return 2

    auswahl = alle[:args.grenze] if args.grenze and args.grenze > 0 else alle
    print(f"Gefunden: {len(alle)} Bilddateien"
          + (f"   Auswahl: {len(auswahl)} (Grenze {args.grenze})"
             if len(auswahl) < len(alle) else "   Auswahl: alle"))

    if args.trocken:
        print()
        for eintrag in auswahl:
            print("  " + _dateizeile(eintrag))
        print(f"\nTrockenlauf: {len(auswahl)} Bilder wuerden angesehen "
              f"({len(alle)} gefunden) — nichts geholt, nichts gesendet, "
              f"nichts geschrieben ({time.time() - start:.1f} s).")
        return 0

    erledigt = erledigt_lesen(args.ausgabe)
    offen: list[dict] = []
    uebersprungen = 0
    for eintrag in auswahl:
        if not args.wiederholen and ist_erledigt(erledigt.get(eintrag["fileid"])):
            uebersprungen += 1
            continue
        offen.append(eintrag)

    schluessel = schluessel_finden(env_pfade)
    if not schluessel:
        print(f"\nKein {_vision.SCHLUESSEL_VARIABLE} gefunden — geprueft wurden "
              f"Umgebungsvariable, {os.path.join(REPO, 'backend', '.env')}, "
              f"{os.path.join(REPO, '.env')} und {_vision.WORKSPACE_ENV}. "
              f"Es wird NICHTS gesendet (--trocken braucht keinen Schluessel).")
        return 2
    senden = sende or sende_aufruf

    ergebnisse: list[dict] = []
    tokens_ein_gesamt = 0
    tokens_aus_gesamt = 0
    kosten_gesamt = 0.0
    fehlgeschlagen = 0
    abbruch = False

    print()
    for eintrag in offen:
        # Kostenbremse VOR jedem Senden: erst pruefen, dann zahlen.
        if bremse_erreicht(kosten_gesamt, args.kosten_obergrenze):
            abbruch = True
            print(f"Kostenbremse: {kosten_gesamt:.6f} USD erreicht "
                  f"(Grenze {args.kosten_obergrenze} USD) — sauberer Abbruch. "
                  f"Offen: {len(offen) - len(ergebnisse) - fehlgeschlagen} "
                  f"Bilder (beim naechsten Lauf mit --wiederholen "
                  f"weiterzumachen).")
            break
        zeile = {"datei": eintrag["name"], "fileid": eintrag["fileid"],
                 "ordner": eintrag["ordner"],
                 "zeit": datetime.datetime.now().isoformat(timespec="seconds")}
        try:
            bild = dienst.thumb(eintrag["fileid"], args.groesse)
            payload = anfrage_bauen(args.modell, bild_daten_uri(bild))
            antwort = senden(payload, schluessel, args.basis, versuche=VERSUCHE)
            daten = antwort_zerlegen(antwort["text"])
            einordnung = einordnung_uebernehmen(daten, schluessel)
        except Exception as problem:                 # Fehlerzeile, Lauf geht weiter
            meldung = fehler_meldung(problem, schluessel)
            zeile["fehler"] = meldung
            jsonl_anhaengen(args.ausgabe, zeile)
            fehlgeschlagen += 1
            print(f"  {_dateizeile(eintrag)}: FEHLER — {meldung}")
            continue

        tokens_ein = _als_int(antwort.get("tokens_ein"))
        tokens_aus = _als_int(antwort.get("tokens_aus"))
        kosten = kosten_berechnen(tokens_ein, tokens_aus, preis_ein, preis_aus)
        zeile.update({
            "klasse": einordnung["klasse"],
            "thema": einordnung["thema"],
            "befund": einordnung["befund"],
            "tokens": tokens_ein + tokens_aus,
            "tokens_ein": tokens_ein,
            "tokens_aus": tokens_aus,
            "kosten_usd": kosten,
            "modell": antwort.get("modell") or args.modell,
        })
        jsonl_anhaengen(args.ausgabe, zeile)
        ergebnisse.append(dict(zeile))
        tokens_ein_gesamt += tokens_ein
        tokens_aus_gesamt += tokens_aus
        if kosten is not None:
            kosten_gesamt += float(kosten)
        print(f"  {_dateizeile(eintrag)}: {einordnung['klasse']} / "
              f"{einordnung['thema']} — {einordnung['befund']} "
              f"({tokens_ein}+{tokens_aus} Tokens"
              + (f", {kosten} USD" if kosten is not None else ", Kosten nicht gesetzt")
              + ")")

    zahlen = zusammenfassung_zaehlen(ergebnisse)
    print()
    print(f"Angesehen: {len(ergebnisse)}   uebersprungen (schon erledigt): "
          f"{uebersprungen}   fehlgeschlagen: {fehlgeschlagen}"
          + ("   ABBRUCH durch Kostenbremse" if abbruch else ""))
    print("Klassen:")
    for klasse in KLASSEN:
        print(f"  {klasse:<22} {zahlen['je_klasse'][klasse]}")
    print("Themen:")
    for thema in THEMEN:
        if zahlen["je_thema"][thema]:
            print(f"  {thema:<22} {zahlen['je_thema'][thema]}")
    print(f"Tokens: {tokens_ein_gesamt} ein, {tokens_aus_gesamt} aus   "
          f"Kosten: {kosten_gesamt:.6f} USD (Preise je 1 Mio: {preis_ein}/"
          f"{preis_aus}, Stand {PREIS_STAND})")
    print(f"Fortsetzungspunkt: {args.ausgabe}")
    print(f"Dauer: {time.time() - start:.1f} s")

    beispiele = beispiele_je_klasse(ergebnisse, anzahl=5)
    for klasse in KLASSEN:
        gesammelt = beispiele[klasse]
        if not gesammelt:
            continue
        print(f"\nBeispiele {klasse} ({len(gesammelt)} von "
              f"{zahlen['je_klasse'][klasse]}):")
        for beispiel in gesammelt:
            ordner = f"[{beispiel['ordner']}] " if beispiel["ordner"] else ""
            print(f"  {ordner}{beispiel['datei']} [{beispiel['thema']}]: "
                  f"{beispiel['befund']}")
    return 0


def _als_int(wert) -> int:
    """Zahl tolerant lesen — unbrauchbare Werte werden ehrlich 0."""
    try:
        return int(float(wert))
    except (TypeError, ValueError):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
