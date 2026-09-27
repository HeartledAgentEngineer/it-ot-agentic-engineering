"""Themen-Stufe Teil 2: EIN Vision-Blick auf den Kontaktbogen -> Thema je Anlass.

Was dieses Werkzeug tut (Nachtlauf-Schritt N6, 27.09.2026):
  Schritt N4 (``foto_themen.py``) hat je Anlass einen **Kontaktbogen** gebaut —
  ein JPEG mit den nummerierten Vorschaubildern eines Anlasses und ein
  Zuordnungs-JSON (Kachel-Nummer -> Datei). Dieses Werkzeug liest diesen
  fertigen Bogen und schickt ihn in **genau einem** Aufruf an OpenRouter
  (Vision-Modell), damit das Modell sagt, worum es bei dem Anlass geht.
  Aus der Antwort entsteht ``thema`` (z. B. "Wanderung im Schnee").

Warum EIN Aufruf je Anlass statt je Bild:
  Hundert Bilder kosten hundert Aufrufe; ein Bogen kostet einen. Das ist die
  Kostengrenze der Themen-Stufe, deshalb gibt es den Bogen ueberhaupt.
  Der Bogen wird als ``data:``-URL base64 im Speicher uebertragen — er wird
  NICHT kopiert, NICHT zwischengespeichert, NICHT in die pCloud gelegt.

Ablauf je Anlass:
  1. Bogen-JPEG + Zuordnungs-JSON lesen (nur lesen, nie schreiben).
  2. Prompt bauen: die Kachelnummern 1..n werden EXPLIZIT genannt, sonst
     antwortet das Modell ueber Kacheln, die es nicht gibt.
  3. POST ``{basis}/chat/completions`` mit content-Array
     (``{"type":"text"}`` + ``{"type":"image_url"}``) — ein Modellaufruf.
  4. Antwort robust zerlegen (```json-Zaeune, Vor-/Nachtext, kaputter Text =
     Fehler, kein Raten) und pruefen: ``thema`` und ``je_kachel``.
  5. Ausgabe nach ``~/foto_sortierung/`` schreiben (nie ins Repo, nie in die
     pCloud — dort liegen private Dateinamen).

Die drei Ausgaben (alle NUR unter ``~/foto_sortierung/``):
  * ``themen/<Jahr>/<Titel>.json`` — Thema, Modell, Tokens, Kosten, Dauer,
    die Kacheln aus der Modellantwort **mit Dateinamen aus dem Bogen-JSON**
    angereichert, plus der Rohtext der Antwort.
  * ``themen.jsonl`` — eine Zeile je erledigtem Anlass, **anhangend**: der
    Fortsetzungspunkt. Steht ein Anlass hier (und die Ausgabedatei existiert),
    wird er uebersprungen (``--wiederholen`` erzwingt). Fehlgeschaefte
    Anlaesse stehen mit ``fehler`` drin (ohne Schluessel) und werden beim
    naechsten Lauf erneut versucht.
  * ``sortierschluessel_themen.csv`` — **vollstaendige Kopie** der Eingabe-CSV
    mit gefuellter Spalte ``thema`` und neuer Spalte ``thema_quelle``
    (Anlass-Titel). Doppelungen (gefuellte Spalte ``doppelung``) erben das
    Thema ihrer Anlass-Geschwisterzeile — der Join laeuft ueber
    ``(ordner, datei)`` UND ueber ``motiv``. Die Original-CSV wird NIE
    ueberschrieben oder geloescht (nur gelesen). Zeigen ``--csv`` und die
    Ausgabe-CSV auf dieselbe Datei (Gross-/Kleinschreibung und Striche egal),
    bricht der Lauf mit deutscher Meldung und SystemExit(2) ab — es wird
    NICHTS geschrieben und NICHTS gesendet (``_pruefe_csv_ziel``).

Was der Code bei der Antwort wirklich tut (codegenau):
  * ``hinweis`` ist OPTIONAL. Fehlt er in der Modellantwort, bleibt das Feld
    im Ergebnis schlicht leer — der Anlass gilt trotzdem als gelungen.
  * Zwei Begriffe, die nicht verwechselt werden duerfen:
      - **unsinnige Eintraege** heissen: Nicht-Objekt, fehlende/erfundene
        Kachelnummer oder eine Kachelnummer, die schon vergeben war
        (Doppelung). Sie werden EINZELN verworfen (Zaehler ``verworfen``),
        solange mindestens ein gueltiger Eintrag uebrig bleibt; das ``thema``
        wird trotzdem gesetzt. Bei einer doppelten Nummer gilt der ERSTE
        Eintrag, jede weitere zaehlt als verworfen.
      - **unbrauchbare Kacheln** heissen: Eintraege mit ``"unbrauchbar": true``.
        Sie werden BEHALTEN und markiert — welches Bild verwackelt/schwarz ist,
        ist Information, kein Muell. Gezaehlt als ``unbrauchbare_kacheln``.
        Eine solche Kachel zaehlt NICHT als fehlend (die Kachel ist da, nur
        unbrauchbar).
    Absicht: eine unvollstaendige Kachelliste soll einen sonst brauchbaren
    Anlass nicht wegwerfen. Nur wenn KEIN gueltiger Eintrag bleibt, ist die
    Antwort unbrauchbar (Fehler, der Anlass wird beim naechsten Lauf erneut
    versucht).
  * Gezaehlt wird in der Ausgabe-JSON (``themen/<Jahr>/<Titel>.json``) UND in
    der Ausgabezeile des Laufs:
      - ``fehlende_kacheln`` (Zahl): Bogenkacheln ohne gueltigen Eintrag.
      - ``unbrauchbare_kacheln`` (Zahl): behaltene Eintraege mit
        ``"unbrauchbar": true``.
      - ``unvollstaendig`` (true/false): true, wenn die Zahl der gueltigen
        Kacheln kleiner ist als die Zahl der Kacheln im Bogen ODER wenn
        mindestens ein unsinniger Eintrag verworfen wurde.

Regeln, die das Werkzeug einhaelt:
  * NUR LESEND gegenueber Bogen und CSV; Schreiben ausschliesslich nach
    ``--ausgabe`` (Standard ``~/foto_sortierung``).
  * Der Ausgabeordner wird VOR jedem Senden und jedem Schreiben geprueft
    (``_pruefe_ausgabe``): liegt ``--ausgabe`` — absolut aufgeloest, Gross-/
    Kleinschreibung und Schraeg-/Rueckwaertsstriche egal — IM Repo, gibt es
    eine deutsche Klartext-Meldung und SystemExit(2); es wird WEDER gesendet
    NOCH geschrieben. Das gilt auch fuer ``--trocken`` und ``--nur-liste``.
    Der Standard ``~/foto_sortierung`` liegt ausserhalb und geht unveraendert
    durch.
  * Der Schluessel bleibt ein Geheimnis: nie ausgegeben, nie geloggt, aus
    jeder Fehlermeldung entfernt (``ohne_schluessel``). Bogeninhalt wird nie
    gedruckt (nur Groessen). Jede Modellantwort wird VOR dem Speichern/Ausgeben
    entschaerft (``geheimnis_entfernen``): der benutzte Schluessel UND
    generische ``sk_``/``sk_or-``-Muster (ab 20 Zeichen) werden durch
    ``<schluessel-entfernt>`` ersetzt — im Rohtext, im ``thema``, ``hinweis``
    und in jeder Kachelbeschreibung.
  * Kein Schluessel auffindbar -> klare deutsche Meldung, Exit-Code 2, es
    wird NICHTS gesendet. ``--trocken`` und ``--nur-liste`` brauchen keinen
    Schluessel und senden nie.
  * Netz-/HTTP-Fehler: hoechstens ``VERSUCHE`` Versuche mit kurzer Pause,
    danach wird der Anlass als fehlerhaft festgehalten und der Lauf geht
    weiter (429 und Zeitueberschreitungen brechen den Lauf nicht ab).
  * Idempotent: zweiter Lauf holt nichts nach.

Aufruf (venv des Backends, enthaelt httpx) — Datei:

    cd backend
    .venv/Scripts/python ../tools/foto_sortierung/foto_themen_vision.py \\
        --jahr 2025 --limit 3 --nur-liste     # nur zeigen (kein Schluessel noetig)
    .venv/Scripts/python ../tools/foto_sortierung/foto_themen_vision.py \\
        --jahr 2025 --limit 3 --trocken       # zeigen, was gesendet wuerde
    .venv/Scripts/python ../tools/foto_sortierung/foto_themen_vision.py \\
        --anlass 2025-01-06_Anlass-01         # EINEN Anlass ansehen

Als Modul (Tests, Skripte): ``main(argv=[...], sende=..., env_pfade=[...])``.
"""

from __future__ import annotations

import argparse
import base64
import csv
import datetime
import json
import os
import re
import time

import httpx

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

# ── Feste Werte ────────────────────────────────────────────────────────────

STANDARD_BOEGEN = os.path.join(os.path.expanduser("~"), "foto_sortierung", "boegen")
STANDARD_AUSGABE = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_CSV = os.path.join(os.path.expanduser("~"), "foto_sortierung",
                            "sortierschluessel.csv")

# Das Vision-Modell des Projekts: guenstig UND bildfaehig. Ein reines
# Text-Modell kann den Bogen nicht sehen (siehe backend/app/router/chat.py).
STANDARD_MODELL = "google/gemini-2.5-flash"
STANDARD_BASIS = "https://openrouter.ai/api/v1"

# Schluessel-Suche: genau dieses Muster wie backend/app/config.py — erst die
# projektueblichen Orte, dann die .env der Workspace-Wurzel als Rueckfall.
SCHLUESSEL_VARIABLE = "OPENROUTER_API_KEY"
WORKSPACE_ENV = os.path.join(os.path.dirname(os.path.dirname(REPO)), ".env")

VERSUCHE = 3
PAUSE_SEKUNDEN = 0.8
TIMEOUT_SEKUNDEN = 90.0
MAX_TOKENS = 4000

# Thema als Ordnername: 2-4 deutsche Woerter, keine Schraegstriche.
THEMA_MAX_ZEICHEN = 60
KURZ_MAX_WOERTER = 8

VERBOTENE_ZEICHEN = re.compile(r'[/\\:*?"<>|\x00-\x1f]')


class FotoVisionFehler(Exception):
    """Fehler dieses Werkzeugs — die Meldung enthaelt nie den Schluessel."""


class FotoVisionNetzfehler(FotoVisionFehler):
    """Netz-/HTTP-Fehler — wird bis zu ``VERSUCHE`` mal wiederholt."""


def ohne_schluessel(text: str, schluessel: str, platzhalter: str = "***") -> str:
    """Den Schluessel aus einem Text entfernen, falls er hineingeraten ist.

    Letzte Verteidigungslinie: Selbst wenn eine fremde Fehlermeldung die
    Anfrage-URL samt Header enthielte, wird sie hier entschaerft.
    ``platzhalter`` ist vorgegeben ``***`` (Laufzeilen unveraendert); fuer
    gespeicherte Modellantworten nutzt ``geheimnis_entfernen`` einen
    sprechenden Platzhalter.
    """
    if schluessel and schluessel in text:
        return text.replace(schluessel, platzhalter)
    return text


# Sprechender Platzhalter fuer gespeicherte/ausgegebene Modellantworten.
GEHEIMNIS_PLATZHALTER = "<schluessel-entfernt>"
# Ein gueltiger Schluessel ist lang; kuerzere Werte sind kein Geheimnis und
# wuerden als Textersatz harmlose Woerter zerreissen (z. B. "k").
GEHEIMNIS_MINDESTLAENGE = 8
# Generische Schluessel-Muster: "sk_or-…" bzw. "sk-…", mindestens 20 Zeichen.
GEHEIMNIS_MUSTER = re.compile(r"sk_or-[A-Za-z0-9_\-]{14,}|sk-[A-Za-z0-9_\-]{17,}")


def geheimnis_entfernen(text, schluessel) -> str:
    """Jeden Text vor dem Speichern/Ausgeben entschaerfen (rein, ohne I/O).

    Ersetzt zuerst den benutzten ``schluessel`` (falls uebergeben und lang
    genug, ``GEHEIMNIS_MINDESTLAENGE``) durch ``GEHEIMNIS_PLATZHALTER`` — auch
    wenn das Modell ihn im Fliesstext wiederholt. Danach werden zusaetzlich
    generische Schluessel-Muster maskiert (``sk_or-…``/``sk-…`` mit mindestens
    20 Zeichen), damit ein anderer, fremder Aufrufschluessel nicht auf Platte
    landet. ``None``/leerer Schluessel und Nicht-Text stuerzen nicht ab.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    if schluessel and len(schluessel) >= GEHEIMNIS_MINDESTLAENGE:
        text = ohne_schluessel(text, schluessel, GEHEIMNIS_PLATZHALTER)
    return GEHEIMNIS_MUSTER.sub(GEHEIMNIS_PLATZHALTER, text)


def _pruefe_csv_ziel(csv_pfad: str, ziel_pfad: str) -> None:
    """Sicherstellen, dass die Ausgabe-CSV NICHT die Eingabe-CSV ist.

    Eingabe- und Ausgabepfad werden absolut aufgeloest verglichen (Gross-/
    Kleinschreibung und Schraeg-/Rueckwaertsstriche egal). Zeigen beide auf
    dieselbe Datei, gibt es eine deutsche Klartext-Meldung und SystemExit(2):
    es wird dann NICHTS geschrieben und NICHTS gesendet. Die Repo-Schutz-
    pruefung ``_pruefe_ausgabe`` bleibt davon unberuehrt.
    """
    eingabe = os.path.normcase(os.path.abspath(csv_pfad))
    ziel = os.path.normcase(os.path.abspath(ziel_pfad))
    if eingabe == ziel:
        print(f"Ausgabe-CSV und Eingabe-CSV sind dieselbe Datei: {csv_pfad}\\n"
              f"Das Original darf nicht ueberschrieben werden — es wird NICHTS "
              f"geschrieben und NICHTS gesendet.")
        raise SystemExit(2)


def _pruefe_ausgabe(pfad: str) -> str:
    """Sicherstellen, dass der Ausgabeordner AUSSERHALB des Repos liegt.

    Der Auftrag laesst Ausgaben nur ausserhalb des Repos zu (dort liegen
    private Dateinamen). Geprueft wird der absolut aufgeloeste Pfad; Gross-/
    Kleinschreibung und Schraeg-/Rueckwaertsstriche spielen keine Rolle
    (``abspath`` + ``normcase`` + ``commonpath``). Liegt der Zielordner im
    Repo, gibt es eine deutsche Klartext-Meldung und SystemExit(2) — es wird
    dann nichts gesendet und nichts geschrieben. Sonst kommt der Pfad zurueck.
    """
    ziel = os.path.normcase(os.path.abspath(pfad))
    repo = os.path.normcase(os.path.abspath(REPO))
    try:
        gemeinsam = os.path.commonpath([ziel, repo])
    except ValueError:                       # anderes Laufwerk: nie im Repo
        return pfad
    if gemeinsam == repo:
        print(f"Ausgabeordner liegt IM Repo und ist nicht erlaubt: {pfad}\n"
              f"Ausgaben gehoeren ausserhalb des Repos (Standard: "
              f"{STANDARD_AUSGABE}); es wird NICHTS geschrieben und NICHTS "
              f"gesendet.")
        raise SystemExit(2)
    return pfad


def _warte(sekunden: float) -> None:
    """Kurze Pause zwischen Wiederholungen (in Tests ersetzt)."""
    time.sleep(sekunden)


def _als_int(wert) -> int:
    """Zahl tolerant lesen — unbrauchbare Werte werden ehrlich 0."""
    try:
        return int(float(wert))
    except (TypeError, ValueError):
        return 0


def _als_float(wert):
    """Zahl tolerant lesen — None, wenn unbrauchbar."""
    try:
        return float(wert)
    except (TypeError, ValueError):
        return None


# ── Schluessel finden (Muster aus backend/app/config.py) ───────────────────

def env_variable_lesen(pfad: str, name: str) -> str:
    """Eine einzelne Variable aus einer .env-Datei lesen — sonst nichts.

    Absichtlich derselbe kleine Leser wie in ``backend/app/config.py``: Aus
    einer fremden Datei (Workspace-Wurzel) wird genau EIN Variablenname
    gelesen. Der Wert wird zurueckgegeben, aber nie geloggt und nie gedruckt.
    Fehlende Datei, fehlender Name oder Lesefehler: leerer String.
    """
    try:
        if not os.path.isfile(pfad):
            return ""
        with open(pfad, encoding="utf-8", errors="replace") as datei:
            for zeile in datei:
                zeile = zeile.strip()
                if not zeile or zeile.startswith("#") or "=" not in zeile:
                    continue
                kennung, _, wert = zeile.partition("=")
                kennung = kennung.strip()
                if kennung.startswith("export "):
                    kennung = kennung[len("export "):].strip()
                if kennung != name:
                    continue
                return wert.strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


def schluessel_pfade() -> list[str]:
    """Wo der OpenRouter-Schluessel liegen darf (Reihenfolge = Vorrang)."""
    return [
        os.environ.get(SCHLUESSEL_VARIABLE, ""),          # Umgebung hat Vorrang
        os.path.join(REPO, "backend", ".env"),            # projektueblich
        os.path.join(REPO, ".env"),                       # projektueblich
        WORKSPACE_ENV,                                    # Rueckfall (Wurzel)
    ]


def schluessel_finden(env_pfade=None) -> str:
    """Den OpenRouter-Schluessel finden — leerer String, wenn keiner da ist.

    ``env_pfade`` darf fuer Tests gesetzt werden (Liste von Dateipfaden).
    Der gefundene Wert wird nie ausgegeben.
    """
    if env_pfade is not None:
        for pfad in env_pfade:
            wert = env_variable_lesen(pfad, SCHLUESSEL_VARIABLE)
            if wert:
                return wert
        return ""
    for ort in schluessel_pfade():
        if not ort:
            continue
        if os.sep in ort or "/" in ort:                   # ein Dateipfad
            wert = env_variable_lesen(ort, SCHLUESSEL_VARIABLE)
        else:                                             # schon ein Wert
            wert = ort.strip()
        if wert:
            return wert
    return ""


# ── Kontaktboegen finden und lesen ─────────────────────────────────────────

def boegen_auflisten(boegen_dir: str, jahr: str = "", anlass: str = "") -> list[dict]:
    """Fertige Kontaktboegen (JPEG + Zuordnungs-JSON) auflisten.

    Ein Bogen zaehlt nur, wenn BEIDE Dateien da sind — ein halber Bogen waere
    nicht ansehbar. Sortiert nach Name (also chronologisch).
    """
    ergebnis: list[dict] = []
    if not os.path.isdir(boegen_dir):
        return ergebnis
    jahre = [jahr] if jahr else sorted(
        e for e in os.listdir(boegen_dir)
        if os.path.isdir(os.path.join(boegen_dir, e)) and e.isdigit())
    for jahr_name in jahre:
        ordner = os.path.join(boegen_dir, str(jahr_name))
        if not os.path.isdir(ordner):
            continue
        for name in sorted(os.listdir(ordner)):
            if not name.lower().endswith(".json"):
                continue
            titel = name[:-len(".json")]
            if anlass and titel != anlass:
                continue
            jpg = os.path.join(ordner, titel + ".jpg")
            if not os.path.isfile(jpg):
                continue
            ergebnis.append({"titel": titel, "jahr": str(jahr_name),
                             "json": os.path.join(ordner, name), "jpg": jpg,
                             "jpg_bytes": os.path.getsize(jpg)})
    return ergebnis


def bogen_lesen(json_pfad: str) -> dict:
    """Zuordnungs-JSON eines Kontaktbogens lesen und grob pruefen."""
    try:
        with open(json_pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except (OSError, ValueError) as problem:
        raise FotoVisionFehler(
            f"Zuordnungs-JSON nicht lesbar ({problem.__class__.__name__}): "
            f"{os.path.basename(json_pfad)}") from None
    if not isinstance(daten, dict) or not isinstance(daten.get("kacheln"), list):
        raise FotoVisionFehler(
            f"Zuordnungs-JSON ohne kacheln: {os.path.basename(json_pfad)}")
    return daten


def kachelzahl(bogen: dict) -> int:
    """Die Anzahl der Kacheln eines Bogens (aus dem JSON, nie geraten)."""
    anzahl = _als_int(bogen.get("anzahl"))
    if anzahl <= 0:
        anzahl = len(bogen.get("kacheln") or [])
    return anzahl


def bild_daten_uri(jpg_pfad: str) -> str:
    """Den Bogen als ``data:``-URL (base64) — NUR im Speicher gelesen.

    Die Datei wird nie kopiert und nie zwischengespeichert; die Bytes leben
    nur in der Anfrage. Der Inhalt wird nie gedruckt oder geloggt.
    """
    try:
        with open(jpg_pfad, "rb") as datei:
            roh = datei.read()
    except OSError as problem:
        raise FotoVisionFehler(
            f"Kontaktbogen nicht lesbar ({problem.__class__.__name__}): "
            f"{os.path.basename(jpg_pfad)}") from None
    if not roh:
        raise FotoVisionFehler(f"Kontaktbogen ist leer: {os.path.basename(jpg_pfad)}")
    return "data:image/jpeg;base64," + base64.b64encode(roh).decode("ascii")


# ── Prompt und Anfrage (reine Funktionen) ──────────────────────────────────

def prompt_bauen(anzahl: int) -> str:
    """Den strengen deutschen Prompt bauen — mit ALLEN Kachelnummern 1..n.

    Die Nummern stehen ausgeschrieben im Text: Ohne sie erfindet das Modell
    Kacheln, die es nicht gibt, und die Zuordnung zur Datei waere geraten.
    ``hinweis`` ist im Prompt ausdruecklich als optional gekennzeichnet — der
    Code behandelt einen fehlenden Hinweis als leeres Feld, nicht als Fehler.
    """
    anzahl = max(1, _als_int(anzahl))
    nummern = ", ".join(str(i) for i in range(1, anzahl + 1))
    return (
        "Du siehst einen Kontaktbogen: nummerierte Miniaturbilder EINES Anlasses.\n"
        f"Der Bogen hat genau {anzahl} Kacheln, nummeriert 1 bis {anzahl}.\n"
        f"Die gueltigen Kachelnummern sind: {nummern}.\n"
        "\n"
        "Aufgabe: Erkenne, worum es bei diesem Anlass geht, und beschreibe jede\n"
        "Kachel in wenigen Worten. Antworte auf Deutsch.\n"
        "\n"
        "Antworte AUSSCHLIESSLICH mit einem einzigen JSON-Objekt, ohne Vor- oder\n"
        "Nachtext, ohne Erklaerung, ohne Markdown. Genau diese Schluessel:\n"
        "  \"thema\":  2 bis 4 deutsche Woerter, die den Anlass benennen; als\n"
        "             Ordnername tauglich, ohne Schraegstriche, ohne Zahlen am Ende.\n"
        "  \"je_kachel\": Liste mit einem Eintrag je Kachel, in der Reihenfolge\n"
        f"             1..{anzahl}; jeder Eintrag:\n"
        "             {\"kachel\": <Nummer 1.." + str(anzahl) + ">, "
        f"\"kurz\": \"<maximal {KURZ_MAX_WOERTER} Woerter>\", "
        "\"unbrauchbar\": <true oder false>}\n"
        "             \"unbrauchbar\" ist true, wenn die Kachel nichts Erkennbares\n"
        "             zeigt (unscharf, dunkel, Bedienoberflaeche, reiner Text).\n"
        "  \"hinweis\": optional ein kurzer Satz, falls etwas unklar bleibt.\n"
        "\n"
        f"Regeln: Nenne nur Kachelnummern von 1 bis {anzahl}. Erfinde keine\n"
        "Kacheln. Lass keinen Eintrag aus und schreibe kein Feld dazu.\n"
        "Wenn du unsicher bist, setze \"unbrauchbar\": true statt zu raten.\n"
        "Das JSON-Objekt ist die gesamte Antwort."
    )


def anfrage_bauen(modell: str, daten_uri: str, anzahl: int,
                  max_tokens: int = MAX_TOKENS) -> dict:
    """Den Anfragekoerper fuer OpenRouter bauen (content-Array mit Bild)."""
    return {
        "model": modell,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_bauen(anzahl)},
                    {"type": "image_url", "image_url": {"url": daten_uri}},
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
    }


# ── Antwort zerlegen (robust, ohne Raten) ──────────────────────────────────

def zaeune_entfernen(text: str) -> str:
    """Markdown-Zaeune (```json … ```) entfernen — der Rest bleibt."""
    if not isinstance(text, str):
        return ""
    sauber = text.strip()
    sauber = re.sub(r"^```[A-Za-z0-9_-]*[ \t]*\r?\n?", "", sauber)
    sauber = re.sub(r"\r?\n?[ \t]*```[ \t]*$", "", sauber)
    return sauber.strip()


def antwort_zerlegen(text: str) -> dict:
    """Rohtext der Modellantwort in ein JSON-Objekt zerlegen.

    Erst Zaeune weg, dann vom ersten ``{`` bis zum letzten ``}`` nehmen, dann
    ``json.loads``. Ist der Text unbrauchbar, gibt es eine klare Meldung —
    es wird NICHTS geraten und kein Ersatzobjekt erfunden.
    """
    sauber = zaeune_entfernen(text)
    if not sauber:
        raise FotoVisionFehler("Modellantwort war leer.")
    anfang = sauber.find("{")
    ende = sauber.rfind("}")
    if anfang < 0 or ende <= anfang:
        raise FotoVisionFehler("Modellantwort enthaelt kein JSON-Objekt.")
    roh = sauber[anfang:ende + 1]
    try:
        daten = json.loads(roh)
    except ValueError as problem:
        raise FotoVisionFehler(
            f"Modellantwort ist kein lesbares JSON ({problem.__class__.__name__})."
        ) from None
    if not isinstance(daten, dict):
        raise FotoVisionFehler("Modellantwort ist kein JSON-Objekt.")
    return daten


def thema_normalisieren(thema) -> str:
    """Thema als Ordnername tauglich machen: Schraegstriche, Leerraum, Laenge.

    Kein Raten: Ist danach nichts uebrig, kommt der leere String zurueck — der
    Aufrufer behandelt das als Fehler, statt einen Namen zu erfinden.
    """
    if not isinstance(thema, str):
        return ""
    sauber = VERBOTENE_ZEICHEN.sub(" ", thema)
    sauber = re.sub(r"\s+", " ", sauber).strip()
    sauber = sauber.strip("._-")
    return sauber[:THEMA_MAX_ZEICHEN].strip()


def kurz_normalisieren(kurz) -> str:
    """Kurzbeschreibung einer Kachel: eine Zeile, hoechstens ~8 Woerter."""
    if not isinstance(kurz, str):
        return ""
    sauber = re.sub(r"\s+", " ", kurz.replace("\n", " ")).strip()
    woerter = sauber.split(" ")
    return " ".join(woerter[:KURZ_MAX_WOERTER])


def kacheln_uebernehmen(daten: dict, bogen: dict) -> list[dict]:
    """``je_kachel`` pruefen und um Dateinamen aus dem Bogen-JSON ergaenzen.

    Nur Kachelnummern, die es im Bogen wirklich gibt, werden uebernommen;
    **unsinnige Eintraege** — Nicht-Objekt, fehlende/erfundene Nummer oder eine
    Nummer, die schon vergeben war (Doppelung) — fallen EINZELN weg, solange
    mindestens ein gueltiger bleibt. Bei einer doppelten Nummer gilt der ERSTE
    Eintrag, jede weitere zaehlt als verworfen. Das Thema ist dann trotzdem
    brauchbar; bleibt keine gueltige Kachel uebrig, ist die Antwort unbrauchbar
    — Fehler statt halber Wahrheit.

    Eintraege mit ``unbrauchbar: true`` werden NICHT verworfen: sie werden
    BEHALTEN und markiert (welches Bild verwackelt/schwarz ist, ist
    Information). Sie zaehlen weder als verworfen noch als fehlend.

    Die Zahl der verworfenen (unsinnigen) Eintraege steht als ``verworfen`` am
    ersten uebernommenen Eintrag; die Zahl der dadurch fehlenden Kacheln
    (``fehlende_kacheln``) und der behaltenen unbrauchbaren Kacheln
    (``unbrauchbare_kacheln``) rechnet ``anlass_verarbeiten`` aus.
    """
    eintraege = daten.get("je_kachel")
    if not isinstance(eintraege, list):
        raise FotoVisionFehler("Modellantwort ohne Liste 'je_kachel'.")
    nach_nummer = {}
    for kachel in bogen.get("kacheln") or []:
        if isinstance(kachel, dict):
            nach_nummer[_als_int(kachel.get("kachel"))] = kachel
    uebernommen: list[dict] = []
    verworfen = 0
    gesehen: set[int] = set()
    for eintrag in eintraege:
        if not isinstance(eintrag, dict):              # unsinnig: kein Objekt
            verworfen += 1
            continue
        nummer = _als_int(eintrag.get("kachel"))
        quelle = nach_nummer.get(nummer)
        if not nummer or quelle is None:               # unsinnig: Nummer fehlt/erfunden
            verworfen += 1
            continue
        if nummer in gesehen:                          # unsinnig: Doppelung
            verworfen += 1                             # der ERSTE Eintrag bleibt
            continue
        gesehen.add(nummer)
        uebernommen.append({
            "kachel": nummer,
            "kurz": kurz_normalisieren(eintrag.get("kurz")),
            "unbrauchbar": bool(eintrag.get("unbrauchbar")),
            "datei": quelle.get("datei", ""),
            "fileid": quelle.get("fileid"),
            "ordner": quelle.get("ordner", ""),
        })
    if not uebernommen:
        raise FotoVisionFehler(
            "Modellantwort nennt keine gueltige Kachelnummer aus dem Bogen.")
    uebernommen.sort(key=lambda k: k["kachel"])
    if verworfen:
        uebernommen[0]["verworfen"] = verworfen
    return uebernommen


def kosten_berechnen(tokens_ein: int, tokens_aus: int,
                     preis_ein, preis_aus):
    """Kosten in USD aus Tokens und Preis je 1 Mio Tokens.

    Ohne Preise kommt ``None`` zurueck — es wird KEINE Kostenzahl erfunden
    (die Modelle sind in Bewegung; geratene Preise waeren schlimmer als keiner).
    """
    if preis_ein is None or preis_aus is None:
        return None
    return round(_als_int(tokens_ein) / 1e6 * float(preis_ein)
                 + _als_int(tokens_aus) / 1e6 * float(preis_aus), 6)


# ── Ein Modellaufruf (Transport, mit Wiederholung) ─────────────────────────

def _antwort_auswerten(daten: dict, modell: str) -> dict:
    """OpenRouter-Antwort lesen: Text und Tokenverbrauch (tolerant)."""
    if not isinstance(daten, dict):
        raise FotoVisionFehler("OpenRouter lieferte kein JSON-Objekt.")
    wahl = daten.get("choices")
    if not isinstance(wahl, list) or not wahl:
        raise FotoVisionFehler("OpenRouter lieferte keine Antwort aus.")
    inhalt = wahl[0].get("message", {}).get("content") if isinstance(wahl[0], dict) else None
    if isinstance(inhalt, list):                       # Teilstuecke zusammenfuegen
        inhalt = "".join(teil.get("text", "") for teil in inhalt
                         if isinstance(teil, dict))
    if not isinstance(inhalt, str) or not inhalt.strip():
        raise FotoVisionFehler("OpenRouter lieferte einen leeren Antworttext.")
    verbrauch = daten.get("usage") or {}
    return {
        "text": inhalt,
        "tokens_ein": _als_int(verbrauch.get("prompt_tokens")),
        "tokens_aus": _als_int(verbrauch.get("completion_tokens")),
        "modell": str(daten.get("model") or modell),
    }


def sende_aufruf(payload: dict, schluessel: str, basis: str = STANDARD_BASIS,
                 versuche: int = VERSUCHE, post=None) -> dict:
    """Den einen OpenRouter-Aufruf machen — mit bis zu ``versuche`` Versuchen.

    429 (zu viele Anfragen) und Zeitueberschreitungen werden wiederholt, denn
    sie sind voruebergehend. Erst nach dem letzten Versuch gibt es einen
    ``FotoVisionNetzfehler``; der Text nennt hoechstens die Klasse oder den
    HTTP-Status, nie den Schluessel und nie den Antwortkoerper.
    """
    if not schluessel:
        raise FotoVisionNetzfehler("Kein OpenRouter-Schluessel gesetzt.")
    pfad = basis.rstrip("/") + "/chat/completions"
    kopf = {"Authorization": f"Bearer {schluessel}",
            "Content-Type": "application/json"}
    aufruf = post or httpx.post
    letzter = "kein Aufruf"
    for versuch in range(1, max(1, versuche) + 1):
        try:
            antwort = aufruf(pfad, json=payload, headers=kopf,
                             timeout=TIMEOUT_SEKUNDEN)
        except Exception as problem:                   # Klasse statt Text
            letzter = problem.__class__.__name__
        else:
            if getattr(antwort, "status_code", 0) == 200:
                try:
                    daten = antwort.json()
                except Exception:
                    raise FotoVisionFehler(
                        "OpenRouter lieferte keine lesbare JSON-Antwort.") from None
                return _antwort_auswerten(daten, str(payload.get("model") or ""))
            letzter = f"HTTP {getattr(antwort, 'status_code', '?')}"
        if versuch < versuche:
            _warte(PAUSE_SEKUNDEN * versuch)
    raise FotoVisionNetzfehler(
        f"OpenRouter nach {versuche} Versuchen nicht erreichbar ({letzter}).")


# ── Ein Anlass: Bogen ansehen und das Ergebnis formen ──────────────────────

def anlass_verarbeiten(bogen: dict, jpg_pfad: str, schluessel: str, sende,
                       modell: str = STANDARD_MODELL,
                       basis: str = STANDARD_BASIS,
                       preis_ein=None, preis_aus=None) -> dict:
    """EINEN Anlass ansehen: eine Anfrage, eine Antwort, ein Ergebnis.

    ``sende`` ist die Transportfunktion (``sende_aufruf`` oder eine Attrappe
    mit derselben Signatur). Rueckgabe enthaelt alles fuer die Ausgabedatei —
    inklusive ``hinweis`` (leer, wenn das Modell keinen lieferte),
    ``fehlende_kacheln`` (Bogenkacheln ohne gueltigen Eintrag),
    ``unbrauchbare_kacheln`` (behaltene Eintraege mit ``unbrauchbar: true`` —
    eine solche Kachel zaehlt NICHT als fehlend) und ``unvollstaendig``
    (true/false; true, wenn gueltige Kacheln fehlen ODER unsinnige Eintraege
    verworfen wurden).
    """
    anfang = time.time()
    anzahl = kachelzahl(bogen)
    daten_uri = bild_daten_uri(jpg_pfad)
    payload = anfrage_bauen(modell, daten_uri, anzahl)
    antwort = sende(payload, schluessel, basis, versuche=VERSUCHE)

    daten = antwort_zerlegen(antwort["text"])
    thema = thema_normalisieren(daten.get("thema"))
    if not thema:
        raise FotoVisionFehler("Modellantwort ohne brauchbares 'thema'.")
    # Jeder Modelltext wird VOR dem Speichern/Ausgeben entschaerft: ein Modell,
    # das den Schluessel (oder ein fremdes sk_-Muster) wiederholt, darf ihn so
    # nicht in die Ergebnisdateien und auf die Laufzeile bringen.
    thema = geheimnis_entfernen(thema, schluessel)
    kacheln = kacheln_uebernehmen(daten, bogen)
    for kachel in kacheln:
        if isinstance(kachel.get("kurz"), str):
            kachel["kurz"] = geheimnis_entfernen(kachel["kurz"], schluessel)
    # Wie viele Kacheln des Bogens bekam das Modell nicht hin? Verworfen wurden
    # nur unsinnige Eintraege (Nicht-Objekt, fehlende/erfundene/doppelte
    # Nummer); einzelne Luecken sind kein Grund, den Anlass wegzuwerfen (das
    # Thema bleibt), sie werden aber ehrlich gezaehlt und ausgewiesen. Kacheln
    # mit dem Flag "unbrauchbar" sind BEHALTEN und zaehlen nur getrennt.
    verworfen = _als_int(kacheln[0].get("verworfen")) if kacheln else 0
    fehlende = max(0, _als_int(anzahl) - len(kacheln))
    unbrauchbare = sum(1 for k in kacheln if k.get("unbrauchbar"))
    tokens_ein = _als_int(antwort.get("tokens_ein"))
    tokens_aus = _als_int(antwort.get("tokens_aus"))
    hinweis = daten.get("hinweis")
    return {
        "titel": bogen.get("titel") or os.path.basename(jpg_pfad)[:-len(".jpg")],
        "jahr": bogen.get("jahr"),
        "datum": bogen.get("datum", ""),
        "thema": thema,
        "modell": antwort.get("modell") or modell,
        "tokens_ein": tokens_ein,
        "tokens_aus": tokens_aus,
        "kosten_usd": kosten_berechnen(tokens_ein, tokens_aus, preis_ein, preis_aus),
        "dauer_s": round(time.time() - anfang, 2),
        "anzahl": anzahl,
        "kacheln": kacheln,
        "unvollstaendig": bool(fehlende > 0 or verworfen > 0),
        "fehlende_kacheln": fehlende,
        "unbrauchbare_kacheln": unbrauchbare,
        "hinweis": geheimnis_entfernen(hinweis, schluessel)
                   if isinstance(hinweis, str) else "",
        "rohtext": geheimnis_entfernen(antwort["text"], schluessel),
    }


# ── Ausgaben: Einzeldatei, Fortsetzungspunkt, CSV-Kopie ────────────────────

def json_schreiben(daten: dict, ziel: str) -> None:
    """JSON atomar schreiben (temp + replace) — nie halbe Dateien."""
    ordner = os.path.dirname(os.path.abspath(ziel))
    os.makedirs(ordner, exist_ok=True)
    temp = ziel + ".tmp"
    with open(temp, "w", encoding="utf-8") as datei:
        json.dump(daten, datei, ensure_ascii=False, indent=1)
    os.replace(temp, ziel)


def erledigthemen(jsonl_pfad: str) -> dict:
    """``themen.jsonl`` lesen: {titel: Zeile} als Fortsetzungspunkt.

    Unlesbare Zeilen werden uebersprungen (eine kaputte Zeile darf den Lauf
    nicht anhalten). Die Reihenfolge ist die Datei-Reihenfolge; die letzte
    Zeile zu einem Titel gewinnt.
    """
    ergebnis: dict[str, dict] = {}
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
            if isinstance(eintrag, dict) and eintrag.get("titel"):
                ergebnis[str(eintrag["titel"])] = eintrag
    return ergebnis


def ist_erledigt(eintrag) -> bool:
    """True, wenn dieser Anlass schon erfolgreich angesehen wurde.

    Eine Zeile mit ``fehler`` ist NICHT erledigt — solche Anlaesse werden
    beim naechsten Lauf erneut versucht (ehrlich statt still).
    """
    if not isinstance(eintrag, dict):
        return False
    return not eintrag.get("fehler") and bool(eintrag.get("thema"))


def jsonl_anhaengen(jsonl_pfad: str, eintrag: dict) -> None:
    """Eine Zeile an ``themen.jsonl`` anhaengen (nur anhaengend, nie ersetzen)."""
    ordner = os.path.dirname(os.path.abspath(jsonl_pfad))
    os.makedirs(ordner, exist_ok=True)
    with open(jsonl_pfad, "a", encoding="utf-8") as datei:
        datei.write(json.dumps(eintrag, ensure_ascii=False) + "\n")


def zeilen_lesen(csv_pfad: str) -> list[dict]:
    """Die Sortier-CSV lesen — je Zeile ein Dict (Spalten wie in Stufe 1)."""
    with open(csv_pfad, newline="", encoding="utf-8") as datei:
        return list(csv.DictReader(datei))


def themen_csv_schreiben(csv_pfad: str, ziel_pfad: str,
                         zuordnungen: list[dict]) -> dict:
    """Kopie der Eingabe-CSV mit gefuellter Spalte ``thema`` schreiben.

    ``zuordnungen``: je Anlass-Kachel ``{thema, titel, ordner, datei}``.
    Der Join laeuft ueber ``(ordner, datei)`` (erst genau, dann ohne
    Gross-/Kleinschreibung). Zeilen mit gefuellter Spalte ``doppelung``
    (Kopien derselben Datei auf einem zweiten Geraet) erben das Thema ihrer
    Geschwisterzeile ueber ``motiv``. Neue Spalte: ``thema_quelle``
    (Anlass-Titel). Die Original-CSV wird nur gelesen, nie veraendert.
    """
    zeilen = zeilen_lesen(csv_pfad)
    felder = list(zeilen[0].keys()) if zeilen else []
    for pflicht in ("thema",):
        if pflicht not in felder and zeilen:
            felder.append(pflicht)
    if felder and "thema_quelle" not in felder:
        felder.append("thema_quelle")

    je_datei: dict[tuple, dict] = {}
    je_datei_klein: dict[tuple, dict] = {}
    for eintrag in zuordnungen:
        schluessel = (eintrag.get("ordner", ""), eintrag.get("datei", ""))
        je_datei.setdefault(schluessel, eintrag)
        je_datei_klein.setdefault(
            (schluessel[0].casefold(), schluessel[1].casefold()), eintrag)

    gefuellt = 0
    je_motiv: dict[str, dict] = {}
    for zeile in zeilen:
        zeile.setdefault("thema", "")
        zeile.setdefault("thema_quelle", "")
        treffer = je_datei.get((zeile.get("ordner", ""), zeile.get("datei", "")))
        if treffer is None:
            treffer = je_datei_klein.get(((zeile.get("ordner") or "").casefold(),
                                          (zeile.get("datei") or "").casefold()))
        if treffer is None:
            continue
        zeile["thema"] = treffer["thema"]
        zeile["thema_quelle"] = treffer.get("titel", "")
        gefuellt += 1
        je_motiv.setdefault((zeile.get("motiv") or "").strip().casefold(), treffer)

    vererbt = 0
    for zeile in zeilen:
        if zeile["thema"]:
            continue
        if not (zeile.get("doppelung") or "").strip():
            continue
        treffer = je_motiv.get((zeile.get("motiv") or "").strip().casefold())
        if treffer is None:
            continue
        zeile["thema"] = treffer["thema"]
        zeile["thema_quelle"] = treffer.get("titel", "")
        vererbt += 1

    ordner = os.path.dirname(os.path.abspath(ziel_pfad))
    os.makedirs(ordner, exist_ok=True)
    temp = ziel_pfad + ".tmp"
    with open(temp, "w", newline="", encoding="utf-8") as datei:
        schreiber = csv.DictWriter(datei, fieldnames=felder)
        schreiber.writeheader()
        for zeile in zeilen:
            schreiber.writerow({name: zeile.get(name, "") for name in felder})
    os.replace(temp, ziel_pfad)
    return {"zeilen": len(zeilen), "gefuellt": gefuellt, "vererbt": vererbt}


def zuordnungen_aus_ergebnis(ergebnis: dict) -> list[dict]:
    """Aus einem Anlass-Ergebnis die CSV-Zuordnungen je Kachel bilden."""
    return [
        {"thema": ergebnis["thema"], "titel": ergebnis["titel"],
         "ordner": kachel.get("ordner", ""), "datei": kachel.get("datei", "")}
        for kachel in ergebnis.get("kacheln") or []
    ]


def zuordnungen_sammeln(ausgabe_dir: str, bekannte: dict, neue: list[dict]) -> list[dict]:
    """Alle bekannten Zuordnungen sammeln: aus themen.jsonl-Erfolgen + diesem Lauf.

    So ist ``sortierschluessel_themen.csv`` auch dann vollstaendig, wenn nur
    drei Anlaesse neu angesehen wurden — die frueheren Themen bleiben drin.
    """
    gesammelt: dict[tuple, dict] = {}
    for titel, eintrag in bekannte.items():
        if not ist_erledigt(eintrag):
            continue
        datei = eintrag.get("datei")
        if not datei or not os.path.isfile(datei):
            continue
        try:
            with open(datei, encoding="utf-8") as quelle:
                inhalt = json.load(quelle)
        except (OSError, ValueError):
            continue
        if not isinstance(inhalt, dict):
            continue
        for eintrag_kachel in zuordnungen_aus_ergebnis(inhalt):
            gesammelt.setdefault(
                (eintrag_kachel["ordner"], eintrag_kachel["datei"]), eintrag_kachel)
    for eintrag_kachel in neue:
        gesammelt[(eintrag_kachel["ordner"], eintrag_kachel["datei"])] = eintrag_kachel
    return list(gesammelt.values())


# ── Kommandozeile ──────────────────────────────────────────────────────────

def _mw(bytes_wert) -> str:
    return f"{_als_int(bytes_wert) / 1e6:.2f} MB"


def _bogen_zeile(bogen: dict, ausgabe_dir: str) -> str:
    ziel = os.path.join(ausgabe_dir, "themen", bogen["jahr"], bogen["titel"] + ".json")
    return (f"{bogen['titel']:<24} {_mw(bogen['jpg_bytes']):>10} Bogen   "
            f"-> {ziel}")


def main(argv=None, sende=None, env_pfade=None) -> int:
    """Kommandozeilen-Teil.

    ``sende`` (Transport) und ``env_pfade`` (Schluessel-Suche) sind fuer Tests
    injizierbar — ohne sie wird der echte Aufruf gebaut.
    """
    zerleger = argparse.ArgumentParser(
        description="Ein Vision-Blick je Kontaktbogen -> Thema je Anlass.")
    zerleger.add_argument("--boegen", default=STANDARD_BOEGEN,
                          help="Ordner der Kontaktboegen (ausserhalb des Repos)")
    zerleger.add_argument("--csv", default=STANDARD_CSV,
                          help="Sortierschluessel (CSV aus Stufe 1)")
    zerleger.add_argument("--ausgabe", default=STANDARD_AUSGABE,
                          help="Zielordner der Ausgaben (ausserhalb des Repos)")
    zerleger.add_argument("--jahr", default="", help="z. B. 2025 (leer = alle Jahre)")
    zerleger.add_argument("--anlass", default="",
                          help="genau ein Anlass, z. B. 2025-01-06_Anlass-01")
    zerleger.add_argument("--limit", type=int, default=3,
                          help="Anzahl Anlaesse, klein halten (0 = alle)")
    zerleger.add_argument("--modell", default=STANDARD_MODELL,
                          help=f"Vision-Modell (Standard {STANDARD_MODELL})")
    zerleger.add_argument("--basis", default=STANDARD_BASIS, help="OpenRouter-Basis-URL")
    zerleger.add_argument("--preis-ein", dest="preis_ein", type=float, default=None,
                          help="USD je 1 Mio Eingabe-Tokens (ohne: keine Kostenzahl)")
    zerleger.add_argument("--preis-aus", dest="preis_aus", type=float, default=None,
                          help="USD je 1 Mio Ausgabe-Tokens")
    zerleger.add_argument("--trocken", action="store_true",
                          help="nur zeigen, was gesendet wuerde (sendet NICHTS)")
    zerleger.add_argument("--nur-liste", dest="nur_liste", action="store_true",
                          help="nur die gefundenen Kontaktboegen auflisten")
    zerleger.add_argument("--wiederholen", action="store_true",
                          help="auch schon erledigte Anlaesse erneut ansehen")
    args = zerleger.parse_args(argv)

    # Zielordner ZUERST pruefen: Ausgaben gehoeren ausserhalb des Repos.
    # Das gilt fuer jeden Modus, auch --trocken und --nur-liste.
    _pruefe_ausgabe(args.ausgabe)

    if not os.path.exists(args.csv):
        print(f"Sortierschluessel nicht gefunden: {args.csv}")
        return 2
    if not os.path.isdir(args.boegen):
        print(f"Ordner der Kontaktboegen nicht gefunden: {args.boegen}")
        return 2

    start = time.time()
    alle = boegen_auflisten(args.boegen, args.jahr, args.anlass)
    auswahl = alle[:args.limit] if args.limit and args.limit > 0 else alle
    themen_jsonl = os.path.join(args.ausgabe, "themen.jsonl")
    csv_ziel = os.path.join(args.ausgabe, "sortierschluessel_themen.csv")
    # Schutz: Die Ausgabe-CSV darf NIE die Eingabe-CSV sein. Sonst wuerde ein
    # Lauf das Original ueberschreiben; hier bricht er sauber ab (nichts
    # gesendet, nichts geschrieben).
    _pruefe_csv_ziel(args.csv, csv_ziel)

    print(f"Kontaktboegen: {args.boegen}"
          + (f"   Jahr {args.jahr}" if args.jahr else "")
          + (f"   Auswahl: {args.anlass}" if args.anlass else ""))
    print(f"Sortierschluessel: {args.csv}")
    print(f"Modell: {args.modell}   Ein Aufruf je Anlass")
    print(f"Ausgabe: {args.ausgabe} (themen/<Jahr>/, themen.jsonl, "
          f"{os.path.basename(csv_ziel)})")
    print(f"Gefunden ({len(auswahl)}"
          + (f" von {len(alle)}, Limit {args.limit}" if len(auswahl) < len(alle) else "")
          + "):")
    for bogen in auswahl:
        print("  " + _bogen_zeile(bogen, args.ausgabe))

    if args.nur_liste:
        print(f"\nNur-Liste: nichts gelesen, nichts gesendet ({time.time() - start:.1f} s).")
        return 0

    erledigt = erledigthemen(themen_jsonl)
    offen = []
    uebersprungen = 0
    for bogen in auswahl:
        ziel = os.path.join(args.ausgabe, "themen", bogen["jahr"],
                            bogen["titel"] + ".json")
        if (not args.wiederholen and ist_erledigt(erledigt.get(bogen["titel"]))
                and os.path.isfile(ziel)):
            uebersprungen += 1
            continue
        offen.append(bogen)

    if args.trocken:
        print()
        for bogen in auswahl:
            ziel = os.path.join(args.ausgabe, "themen", bogen["jahr"],
                                bogen["titel"] + ".json")
            schon = ist_erledigt(erledigt.get(bogen["titel"])) and os.path.isfile(ziel)
            if schon and not args.wiederholen:
                print(f"  {bogen['titel']}: waere uebersprungen (Thema schon ermittelt)")
            else:
                print(f"  {bogen['titel']}: wuerde gesendet -> {ziel} "
                      f"[Bogen {_mw(bogen['jpg_bytes'])}, ein Aufruf]")
        print(f"\nTrockenlauf: nichts gesendet, nichts geschrieben "
              f"({time.time() - start:.1f} s).")
        return 0

    schluessel = schluessel_finden(env_pfade)
    if not schluessel:
        print(f"\nKein {SCHLUESSEL_VARIABLE} gefunden — geprueft wurden "
              f"Umgebungsvariable, {os.path.join(REPO, 'backend', '.env')}, "
              f"{os.path.join(REPO, '.env')} und {WORKSPACE_ENV}. "
              "Es wird NICHTS gesendet. Ohne `--trocken`/`--nur-liste` wird der "
              "Schluessel gebraucht (siehe backend/app/config.py).")
        return 2

    senden = sende or sende_aufruf
    gesehen = 0
    fehlgeschlagen = 0
    neue_zuordnungen: list[dict] = []
    tokens_ein_gesamt = 0
    tokens_aus_gesamt = 0

    print()
    for bogen in offen:
        ziel = os.path.join(args.ausgabe, "themen", bogen["jahr"],
                            bogen["titel"] + ".json")
        eintrag = {"titel": bogen["titel"], "jahr": bogen["jahr"],
                   "datum": "", "thema": None, "datei": ziel,
                   "zeit": datetime.datetime.now().isoformat(timespec="seconds")}
        try:
            daten = bogen_lesen(bogen["json"])
            ergebnis = anlass_verarbeiten(
                daten, bogen["jpg"], schluessel, senden, modell=args.modell,
                basis=args.basis, preis_ein=args.preis_ein, preis_aus=args.preis_aus)
        except FotoVisionFehler as problem:
            meldung = ohne_schluessel(str(problem), schluessel)
            eintrag["fehler"] = meldung
            jsonl_anhaengen(themen_jsonl, eintrag)
            fehlgeschlagen += 1
            print(f"  {bogen['titel']}: FEHLER — {meldung}")
            continue
        except Exception as problem:                    # fremder Fehler: Klasse statt Text
            meldung = ohne_schluessel(
                f"unerwarteter Fehler ({problem.__class__.__name__})", schluessel)
            eintrag["fehler"] = meldung
            jsonl_anhaengen(themen_jsonl, eintrag)
            fehlgeschlagen += 1
            print(f"  {bogen['titel']}: FEHLER — {meldung}")
            continue

        eintrag.update({"datum": ergebnis.get("datum", ""),
                        "thema": ergebnis["thema"],
                        "tokens_ein": ergebnis["tokens_ein"],
                        "tokens_aus": ergebnis["tokens_aus"],
                        "kosten_usd": ergebnis["kosten_usd"]})
        json_schreiben(ergebnis, ziel)
        jsonl_anhaengen(themen_jsonl, eintrag)
        neue_zuordnungen.extend(zuordnungen_aus_ergebnis(ergebnis))
        tokens_ein_gesamt += ergebnis["tokens_ein"]
        tokens_aus_gesamt += ergebnis["tokens_aus"]
        gesehen += 1
        kosten = ergebnis["kosten_usd"]
        print(f"  {bogen['titel']}: \"{ergebnis['thema']}\" "
              f"({len(ergebnis['kacheln'])}/{ergebnis['anzahl']} Kacheln, "
              f"unvollstaendig: "
              f"{'true' if ergebnis['unvollstaendig'] else 'false'}, "
              f"fehlende_kacheln: {ergebnis['fehlende_kacheln']}, "
              f"unbrauchbare_kacheln: {ergebnis['unbrauchbare_kacheln']}, "
              f"{ergebnis['tokens_ein']}+{ergebnis['tokens_aus']} Tokens"
              + (f", {kosten} USD" if kosten is not None else ", Kosten nicht gesetzt")
              + f", {ergebnis['dauer_s']} s) -> {ziel}")

    bekannte = erledigthemen(themen_jsonl)
    zuordnungen = zuordnungen_sammeln(args.ausgabe, bekannte, neue_zuordnungen)
    csv_bericht = themen_csv_schreiben(args.csv, csv_ziel, zuordnungen)

    print()
    print(f"Anlaesse: {len(auswahl)} gefunden   angesehen: {gesehen}   "
          f"uebersprungen: {uebersprungen}   fehlgeschlagen: {fehlgeschlagen}")
    print(f"Tokens: {tokens_ein_gesamt} ein, {tokens_aus_gesamt} aus   "
          f"Fortsetzungspunkt: {themen_jsonl}")
    print(f"CSV-Kopie: {csv_ziel} ({csv_bericht['zeilen']} Zeilen, "
          f"thema gefuellt: {csv_bericht['gefuellt']}, "
          f"von Doppelungen geerbt: {csv_bericht['vererbt']})")
    print(f"Original-CSV unveraendert: {args.csv}")
    print(f"Dauer: {time.time() - start:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
