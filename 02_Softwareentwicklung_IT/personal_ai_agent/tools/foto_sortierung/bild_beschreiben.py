"""Einzelbild-Stufe: eine Inhaltsbeschreibung JE BILD -> bild_beschreibungen.jsonl.

Was dieses Werkzeug tut (Plan-Schritt N15, 28.09.2026):
  Die Themen-Stufe hat JE ANLASS ein Thema erzeugt (``themen.jsonl``) — damit
  ist bekannt, worum es bei einem Anlass geht, aber nicht, was auf dem
  EINZELNEN Bild zu sehen ist. Dieses Werkzeug holt das nach: Aus
  Vorschaubildern der pCloud werden **Kontaktboegen im Arbeitsspeicher** gebaut
  (bis zu 36 Kacheln je Bogen, nummeriert) und in **einem** Vision-Aufruf je
  Bogen vom Modell beschrieben. Jede Kachel wird zu genau einer Zeile in
  ``~/foto_sortierung/bild_beschreibungen.jsonl`` — damit wird die Bildsuche
  spaeter zu einer Textsuche („rothaarige Saengerin, Buehne, Menge").

Warum Kontaktboegen statt Einzelbilder:
  Ein Aufruf je Bild kostet einen Aufruf je Bild. Der Bogen packt bis zu 36
  Bilder in EINEN Aufruf — N5 hat bestanden: Nummern 1–36 sicher lesbar,
  Thema je Bogen erkannt. Die Bogen-Geometrie hier ist dieselbe wie dort
  (8 Spalten, 160-px-Kacheln -> 1382x872 bei 36 Kacheln).

Wiederverwendet statt neu erfunden (alles per Pfad geladen):
  * ``foto_themen.py``  — CSV lesen, Dateizeit aus dem Namen, fileid-Aufloesung
    ueber listfolder, Vorschaubilder in Stapeln (getthumbs), ``bogen_bauen``
    (Kacheln + Nummern). Die Boegen entstehen hier NUR IM ARBEITSSPEICHER —
    es wird kein Bogen-JPEG auf Platte geschrieben oder kopiert.
  * ``foto_themen_vision.py`` — Transport (``sende_aufruf`` mit Wiederholung),
    Antwort-Zerlegung (``antwort_zerlegen``), Schluessel-Suche, Kostenrechnung,
    Geheimnis-Entschaerfung.
  * Fuer die Einbettung der Beschreibungstexte gibt es das Schwester-Werkzeug
    ``bild_index_einbetten.py`` (nutzt ``backend/scripts/archiv_index_bauen.py``).

Ablauf eines Laufs:
  1. Sortierschluessel lesen; Zeilen ohne Datum werden uebersprungen.
  2. fileid je Datei aufloesen (ein listfolder je Ordner, mit Zwischenspeicher).
  3. Bereits beschriebene Dateien fallen raus (Idempotenz ueber fileid UND
     (ordner, datei)); der Rest wird chronologisch sortiert und in Boegen zu je
     ``--kacheln-pro-bogen`` (Standard 36) gepackt. Die Bogen-ID ist
     ``bogen-<fileid der ersten Kachel>``.
  4. Je Bogen: Vorschaubilder holen (Kacheln OHNE Vorschau fallen aus dem Bogen
     und bleiben fuer den naechsten Lauf offen), Bogen im Speicher bauen, EIN
     Aufruf an OpenRouter, Antwort zerlegen.
  5. Je gueltiger Kachel eine Zeile an die JSONL anhaengen. Felder: fileid,
     datei, jahr, monat, tag, ordner, beschreibung, bogen_id, modell,
     kosten_usd, zeit. **Keine Bilddaten, kein base64** — nur Text.
     ``kosten_usd`` ist der Anteil der Aufruf-Kosten an dieser Kachel
     (Summe ueber alle Zeilen eines Bogens = tatsaechliche Aufruf-Kosten).

Kostenbremse (harte Grenze):
  ``--budget`` (Standard 1,00 USD) ist die Obergrenze. Vor jedem Aufruf wird
  geprueft: bereits ausgegeben + erwartete Kosten des naechsten Bogens
  (Durchschnitt der gemessenen Aufrufe) > Budget -> Stopp mit Bericht. Nach den
  ersten 3 Boegen (= Messung) werden Dauer und Kosten je Bogen gedruckt und auf
  den Rest hochgerechnet; danach laeuft es in Stapeln (``--stapel``, Standard
  25) mit Fortschritt weiter. Preise: gemessen am Referenzlauf (N5/N6) —
  0,30 USD je 1 Mio Eingabe-Tokens, 2,50 USD je 1 Mio Ausgabe-Tokens
  (``--preis-ein``/``--preis-aus``).

Idempotent und fortsetzbar:
  ``fileid`` ist der Schluessel; zusaetzlich wirkt ``(ordner, datei)`` als
  Sicherheitsnetz. Ein zweiter Lauf ueberspringt jede bereits beschriebene
  Datei und fuegt 0 Zeilen hinzu; ein abgebrochener Lauf macht beim naechsten
  Aufruf genau dort weiter, wo er aufgehoert hat (offen = fehlende fileid).
  Fehlgeschlagene Boegen schreiben nichts — ihre fileids bleiben offen und
  werden erneut versucht (ehrlich statt still).

Regeln, die das Werkzeug einhaelt:
  * NUR LESEND gegenueber der pCloud (listfolder + getthumbs); kein Schreiben,
    kein Loeschen, kein Verschieben, keine Aenderung an pCloud-Inhalten.
  * Bilder leben nur im Arbeitsspeicher (Vorschau-Bytes -> Bogen-Bytes ->
    base64 in der Anfrage); es wird NICHTS auf Platte kopiert.
  * Ausgabe nur ausserhalb des Repos (``--ausgabe``, Standard
    ``~/foto_sortierung``) — dort liegen private Dateinamen. Liegt der
    Zielordner im Repo, bricht der Lauf VOR jedem Senden ab (SystemExit 2).
  * Schluessel und Token bleiben Geheimnisse: nie gedruckt, nie geloggt, aus
    jeder Fehlermeldung entfernt; Modellantworten werden vor dem Speichern
    entschaerft (``geheimnis_entfernen``).
  * ``--trocken`` und ``--nur-liste`` holen nichts und senden nichts
    (kein Schluessel noetig).

Aufruf (venv des Backends — dort liegen httpx und Pillow):

    cd backend
    .venv/Scripts/python ../tools/foto_sortierung/bild_beschreiben.py --nur-liste
    .venv/Scripts/python ../tools/foto_sortierung/bild_beschreiben.py --trocken
    .venv/Scripts/python ../tools/foto_sortierung/bild_beschreiben.py --limit 3
    .venv/Scripts/python ../tools/foto_sortierung/bild_beschreiben.py
        # Vollauf mit Kostenbremse 1,00 USD; Abbruch jederzeit wiederholbar

Als Modul (Tests, Skripte): ``main(argv=[...], sende=..., api_abruf=...,
thumb_abruf=..., env_pfade=[...])``.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import importlib.util
import json
import os
import re
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


# ── Bestehende Bausteine wiederverwenden (nichts neu erfinden) ─────────────
#
# foto_themen.py:        CSV, Dateizeit, fileids (listfolder), Vorschaubilder
#                        (getthumbs, Stapel), Kontaktbogen-Bau (Kacheln + Nummern).
# foto_themen_vision.py: Transport zum Vision-Modell, Antwort-Zerlegung,
#                        Schluessel-Suche, Kostenrechnung, Entschaerfung.
_themen = _modul_aus_pfad(os.path.join(HIER, "foto_themen.py"), "foto_themen")
_vision = _modul_aus_pfad(os.path.join(HIER, "foto_themen_vision.py"),
                          "foto_themen_vision")

# Namen, die dieses Werkzeug direkt aus den Nachbarn benutzt (klare Herkunft):
zeilen_lesen = _themen.zeilen_lesen
datum_teile = _themen.datum_teile
zeit_aus_name = _themen.zeit_aus_name
dateien_im_ordner = _themen.dateien_im_ordner
vorschau_stapel = _themen.vorschau_stapel
bogen_bauen = _themen.bogen_bauen
STANDARD_GROESSE = _themen.STANDARD_GROESSE
echter_api_abruf = _themen.echter_api_abruf
echter_thumb_abruf = _themen.echter_thumb_abruf

antwort_zerlegen = _vision.antwort_zerlegen
sende_aufruf = _vision.sende_aufruf
schluessel_finden = _vision.schluessel_finden
geheimnis_entfernen = _vision.geheimnis_entfernen
kosten_berechnen = _vision.kosten_berechnen
SCHLUESSEL_VARIABLE = _vision.SCHLUESSEL_VARIABLE

# ── Feste Werte ────────────────────────────────────────────────────────────

STANDARD_CSV = os.path.join(os.path.expanduser("~"), "foto_sortierung",
                            "sortierschluessel.csv")
STANDARD_AUSGABE = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_JSONL_NAME = "bild_beschreibungen.jsonl"

# Dasselbe Vision-Modell wie die Themen-Stufe (Referenzlauf N5/N6, gemessen).
STANDARD_MODELL = "google/gemini-2.5-flash"
STANDARD_BASIS = "https://openrouter.ai/api/v1"

# Gemessen am Referenzlauf (27./28.09.2026) aus den usage-Zahlen:
# 0,30 USD je 1 Mio Eingabe-Tokens, 2,50 USD je 1 Mio Ausgabe-Tokens.
STANDARD_PREIS_EIN = 0.30
STANDARD_PREIS_AUS = 2.50

# Harte Kostengrenze des Auftrags (Parameter, Standard).
STANDARD_BUDGET_USD = 1.00

# Bogen-Geometrie wie im bestandenen N5-Bogen: 36 Kacheln, 8 Spalten,
# 160 px je Kachel (1382x872).
KACHELN_JE_BOGEN = 36
SPALTEN = 8
KACHEL = 160

# Messung: die ersten Boegen werden einzeln berichtet und hochgerechnet;
# danach Fortschrittsmeldungen je Stapel.
MESSUNG_BOEGEN = 3
STAPEL_BOEGEN = 25

# Beschreibung je Kachel: eine Zeile, hoechstens so viele Woerter.
BESCHREIBUNG_MAX_WOERTER = 14

VERSUCHE = 3

# Ausgabegrenze: je Kachel ein JSON-Objekt; Grundwert + Kopfraum, gedeckelt.
MAX_TOKENS_GRUND = 600
MAX_TOKENS_JE_KACHEL = 60
MAX_TOKENS_DECKEL = 8000

# Zeilen ohne Uhrzeit im Namen bekommen diese Uhrzeit — sie stehen damit wie in
# der Themen-Stufe am Tagesende.
OHNE_UHRZEIT = (23, 59, 59)


class BildBeschreibenFehler(Exception):
    """Fehler dieses Werkzeugs — die Meldung enthaelt nie Schluessel oder Token."""


def _als_int(wert) -> int:
    """Zahl tolerant lesen — unbrauchbare Werte werden ehrlich 0."""
    try:
        return int(float(wert))
    except (TypeError, ValueError):
        return 0


def max_tokens_fuer(anzahl: int) -> int:
    """Ausgabegrenze passend zur Kachelzahl (rein, ohne Nebenwirkung)."""
    wunsch = MAX_TOKENS_GRUND + MAX_TOKENS_JE_KACHEL * max(1, _als_int(anzahl))
    return max(MAX_TOKENS_GRUND, min(MAX_TOKENS_DECKEL, wunsch))


def _dauer_seit(start: float) -> float:
    """Sekunden seit ``start`` — kleine Hilfe fuer Meldungen."""
    return time.time() - start


# ── Ausgabeschutz: Ausgaben gehoeren ausserhalb des Repos ──────────────────

def _pruefe_ausgabe(pfad: str) -> str:
    """Sicherstellen, dass der Ausgabeordner AUSSERHALB des Repos liegt.

    Wie in ``foto_themen_vision.py``: absolut aufgeloest, Gross-/
    Kleinschreibung und Schraeg-/Rueckwaertsstriche egal. Liegt der Zielordner
    im Repo, gibt es eine deutsche Klartext-Meldung und SystemExit(2) — es
    wird dann NICHTS geholt, gesendet oder geschrieben.
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
              f"{STANDARD_AUSGABE}); es wird NICHTS geholt, gesendet oder "
              f"geschrieben.")
        raise SystemExit(2)
    return pfad


# ── Planung: Zeilen vorbereiten, sortieren, Boegen packen (reine Funktionen) ─

def zeilen_vorbereiten(zeilen: list[dict]) -> list[dict]:
    """CSV-Zeilen mit Datum anreichern (``zeit`` aus dem Dateinamen, sonst None).

    Zeilen ohne brauchbares Datum fallen raus (der Aufrufer zaehlt sie
    ehrlich). Jede uebrige Zeile bekommt ``jahr``/``monat``/``tag`` als ints
    und ``zeit`` ((h, m, s) oder None) — es wird nichts geraten.
    """
    ergebnis: list[dict] = []
    for zeile in zeilen:
        teile = datum_teile(zeile)
        if teile is None:
            continue
        kopie = dict(zeile)
        kopie["jahr"], kopie["monat"], kopie["tag"] = teile
        kopie["zeit"] = zeit_aus_name(str(zeile.get("datei") or ""), teile)
        ergebnis.append(kopie)
    return ergebnis


def sortierschluessel_sortieren(zeilen: list[dict]) -> list[dict]:
    """Chronologisch sortieren — deterministisch, ohne die CSV anzufassen.

    Schluessel: (Jahr, Monat, Tag, Uhrzeit (ohne Uhrzeit = Tagesende), Ordner,
    Dateiname in Kleinschreibung). Zweimal sortieren ergibt dieselbe
    Reihenfolge — darauf ist die Bogen-Packung aufgebaut.
    """
    return sorted(zeilen, key=lambda z: (
        _als_int(z.get("jahr")), _als_int(z.get("monat")), _als_int(z.get("tag")),
        z.get("zeit") or OHNE_UHRZEIT,
        str(z.get("ordner") or "").casefold(),
        str(z.get("datei") or "").casefold()))


def _bogen_kennung(block: list[dict]) -> str:
    """Bogen-ID aus der ersten brauchbaren fileid des Blocks (sonst bogen-0)."""
    erste = next((_als_int(z.get("fileid")) for z in block
                  if _als_int(z.get("fileid"))), 0)
    return f"bogen-{erste}"


def boegen_planen(zeilen: list[dict],
                  kacheln_je_bogen: int = KACHELN_JE_BOGEN) -> list[dict]:
    """Offene Zeilen in Boegen zu je ``kacheln_je_bogen`` packen.

    Rueckgabe: Liste von Boegen ``{"bogen_id", "zeilen"}``. Die Bogen-ID ist
    ``bogen-<fileid der ersten Kachel>`` — stabiler Bezug fuer die
    Ausgabezeilen (eine bereits beschriebene fileid beginnt nie einen Bogen).
    """
    if kacheln_je_bogen < 1:
        raise BildBeschreibenFehler("--kacheln-pro-bogen muss mindestens 1 sein.")
    boegen: list[dict] = []
    for anfang in range(0, len(zeilen), kacheln_je_bogen):
        block = zeilen[anfang:anfang + kacheln_je_bogen]
        if not block:
            continue
        boegen.append({"bogen_id": _bogen_kennung(block), "zeilen": block})
    return boegen


# ── Idempotenz: Erledigtes lesen, Zeilen anhaengen ─────────────────────────

def erledigtes_lesen(jsonl_pfad: str) -> dict:
    """Was steht schon in der JSONL? ``{"fileids": set, "dateien": set}``.

    ``dateien`` enthaelt ``(ordner.casefold(), datei.casefold())`` — das
    Sicherheitsnetz neben der fileid (auch ohne Netz pruefbar). Unlesbare
    Zeilen werden uebersprungen: eine kaputte Zeile darf den Lauf nicht
    anhalten und keine Datei erfinden.
    """
    ergebnis: dict = {"fileids": set(), "dateien": set()}
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
            if not isinstance(eintrag, dict):
                continue
            fileid = _als_int(eintrag.get("fileid"))
            if fileid:
                ergebnis["fileids"].add(fileid)
            schluessel = (str(eintrag.get("ordner") or "").casefold(),
                          str(eintrag.get("datei") or "").casefold())
            if schluessel[1]:
                ergebnis["dateien"].add(schluessel)
    return ergebnis


def ist_erledigt(zeile: dict, erledigt: dict) -> bool:
    """True, wenn diese Zeile schon eine Beschreibung hat (fileid oder Datei)."""
    fileid = _als_int(zeile.get("fileid"))
    if fileid and fileid in erledigt["fileids"]:
        return True
    schluessel = (str(zeile.get("ordner") or "").casefold(),
                  str(zeile.get("datei") or "").casefold())
    return bool(schluessel[1]) and schluessel in erledigt["dateien"]


def zeilen_anhaengen(jsonl_pfad: str, eintraege: list[dict]) -> int:
    """Zeilen an die JSONL anhaengen (nur anhaengend, nie ersetzen).

    Geschrieben wird EINMAL je Aufruf (eine Liste) — ein abgebrochener Lauf
    hinterlaesst so keine halbe Zeile. Rueckgabe: Zahl der geschriebenen Zeilen.
    """
    if not eintraege:
        return 0
    ordner = os.path.dirname(os.path.abspath(jsonl_pfad))
    os.makedirs(ordner, exist_ok=True)
    with open(jsonl_pfad, "a", encoding="utf-8") as datei:
        for eintrag in eintraege:
            datei.write(json.dumps(eintrag, ensure_ascii=False) + "\n")
    return len(eintraege)


# ── Prompt und Anfrage (reine Funktionen) ──────────────────────────────────

def prompt_bauen(anzahl: int) -> str:
    """Den strengen deutschen Beschreibungs-Prompt bauen (Kacheln 1..n).

    Die Nummern stehen ausgeschrieben im Text: Ohne sie erfindet das Modell
    Kacheln, die es nicht gibt, und die Zuordnung waere geraten. Verlangt wird
    eine kurze, gegenstaendliche Zeile je Kachel (fuer die Textsuche), ohne
    Personennamen — die Beschreibung liegt ausserhalb des Repos, aber private
    Namen haben in Suchtexten nichts verloren.
    """
    anzahl = max(1, _als_int(anzahl))
    nummern = ", ".join(str(i) for i in range(1, anzahl + 1))
    return (
        "Du siehst einen Kontaktbogen: nummerierte Miniaturbilder, meist aus "
        "einem Fotoalbum.\n"
        f"Der Bogen hat genau {anzahl} Kacheln, nummeriert 1 bis {anzahl}.\n"
        f"Die gueltigen Kachelnummern sind: {nummern}.\n"
        "\n"
        "Aufgabe: Beschreibe JEDE Kachel so, dass man das Bild spaeter ueber "
        "eine Textsuche wiederfindet — was ist zu sehen (Personen ohne Namen, "
        "Ort, Situation, Gegenstaende, lesbarer Text). Antworte auf Deutsch.\n"
        "\n"
        "Antworte AUSSCHLIESSLICH mit einem einzigen JSON-Objekt, ohne Vor- "
        "oder Nachtext, ohne Markdown. Genau diese Schluessel:\n"
        "  \"je_kachel\": Liste mit einem Eintrag je Kachel, in der Reihenfolge\n"
        f"             1..{anzahl}; jeder Eintrag:\n"
        "             {\"kachel\": <Nummer 1.." + str(anzahl) + ">, "
        "\"beschreibung\": \"<ein Satz, 4 bis "
        f"{BESCHREIBUNG_MAX_WOERTER} Woerter>\", "
        "\"unbrauchbar\": <true oder false>}\n"
        "             \"beschreibung\" ist Pflicht und beschreibt NUR, was "
        "wirklich zu sehen ist; keine Personennamen, keine Kennzeichen, keine "
        "Adressen.\n"
        "             \"unbrauchbar\" ist true, wenn die Kachel nichts "
        "Erkennbares zeigt (unscharf, schwarz, leere Flaeche) — dann nennt\n"
        "             \"beschreibung\" kurz den Grund.\n"
        "\n"
        f"Regeln: Nenne nur Kachelnummern von 1 bis {anzahl}. Erfinde keine "
        "Kacheln. Lass keinen Eintrag aus und schreibe kein Feld dazu. Wenn du "
        "unsicher bist, beschreibe nur, was sicher erkennbar ist.\n"
        "Das JSON-Objekt ist die gesamte Antwort."
    )


def anfrage_bauen(modell: str, daten_uri: str, anzahl: int,
                  max_tokens: int | None = None) -> dict:
    """Den Anfragekoerper fuer OpenRouter bauen (content-Array mit Bild)."""
    if max_tokens is None:
        max_tokens = max_tokens_fuer(anzahl)
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


def bild_daten_uri(bogen_bytes: bytes) -> str:
    """Bogen-Bytes als ``data:``-URL — NUR im Speicher, nie auf Platte.

    Der Bogen entsteht im Arbeitsspeicher (``bogen_bauen``); hier kommt nur
    die base64-Uebertragung in die Anfrage. Der Inhalt wird nie gedruckt.
    """
    if not bogen_bytes:
        raise BildBeschreibenFehler("Kontaktbogen ist leer.")
    return "data:image/jpeg;base64," + base64.b64encode(bogen_bytes).decode("ascii")


# ── Antwort zerlegen (robust, ohne Raten) ──────────────────────────────────

def beschreibung_normalisieren(text) -> str:
    """Kurzbeschreibung einer Kachel: eine Zeile, hoechstens 14 Woerter."""
    if not isinstance(text, str):
        return ""
    sauber = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
    woerter = sauber.split(" ")
    return " ".join(woerter[:BESCHREIBUNG_MAX_WOERTER])


def beschreibungen_uebernehmen(daten: dict, anzahl: int) -> list[dict]:
    """``je_kachel`` pruefen — dieselben Regeln wie in der Themen-Stufe.

    Nur Kachelnummern, die es im Bogen wirklich gibt (1..anzahl), werden
    uebernommen; **unsinnige Eintraege** — Nicht-Objekt, fehlende/erfundene
    Nummer, Doppelung (der ERSTE gilt) oder leerer Beschreibungstext — fallen
    EINZELN weg, solange mindestens ein gueltiger bleibt. Bleibt keine gueltige
    Kachel uebrig, ist die Antwort unbrauchbar (Fehler statt halber Wahrheit —
    die Dateien bleiben dann offen fuer den naechsten Lauf).

    Eintraege mit ``unbrauchbar: true`` werden BEHALTEN (welches Bild
    verwackelt/schwarz ist, ist Information). Die Zahl der verworfenen
    Eintraege steht als ``verworfen`` am ersten uebernommenen Eintrag.
    """
    eintraege = daten.get("je_kachel")
    if not isinstance(eintraege, list):
        raise BildBeschreibenFehler("Modellantwort ohne Liste 'je_kachel'.")
    anzahl = max(1, _als_int(anzahl))
    uebernommen: list[dict] = []
    verworfen = 0
    gesehen: set = set()
    for eintrag in eintraege:
        if not isinstance(eintrag, dict):              # unsinnig: kein Objekt
            verworfen += 1
            continue
        nummer = _als_int(eintrag.get("kachel"))
        if not nummer or not 1 <= nummer <= anzahl:    # unsinnig: Nummer fehlt/erfunden
            verworfen += 1
            continue
        if nummer in gesehen:                          # unsinnig: Doppelung
            verworfen += 1                             # der ERSTE Eintrag bleibt
            continue
        beschreibung = beschreibung_normalisieren(eintrag.get("beschreibung"))
        if not beschreibung:                           # unsinnig: leerer Text
            verworfen += 1
            continue
        gesehen.add(nummer)
        uebernommen.append({
            "kachel": nummer,
            "beschreibung": beschreibung,
            "unbrauchbar": bool(eintrag.get("unbrauchbar")),
        })
    if not uebernommen:
        raise BildBeschreibenFehler(
            "Modellantwort nennt keine gueltige Kachel mit Beschreibung.")
    uebernommen.sort(key=lambda k: k["kachel"])
    if verworfen:
        uebernommen[0]["verworfen"] = verworfen
    return uebernommen


# ── Kostenbremse (reine Funktionen) ────────────────────────────────────────

def budget_stoppt(ausgegeben: float, naechste_schaetzung: float,
                  budget: float) -> bool:
    """True, wenn der naechste Aufruf das Budget voraussichtlich ueberschreitet.

    ``naechste_schaetzung`` ist der Durchschnitt der bisher gemessenen Aufrufe
    (0, solange noch keiner gemessen ist — der erste Aufruf startet immer).
    Die Grenze ist hart gedacht: es wird kein Aufruf begonnen, nach dem die
    bereits ausgegebene Summe plus die erwarteten Kosten die Grenze reissen
    wuerde.
    """
    return (float(ausgegeben) + max(0.0, float(naechste_schaetzung))
            > float(budget))


def messung_bericht(aufrufe: int, bilder: int, kosten: float, dauer: float,
                    rest_boegen: int, rest_bilder: int,
                    budget: float) -> str:
    """Die Messung der ersten Boegen als Text (Zahlen, hochgerechnet)."""
    je_bogen = (kosten / aufrufe) if aufrufe else 0.0
    je_bild = (kosten / bilder) if bilder else 0.0
    sek_je_bogen = (dauer / aufrufe) if aufrufe else 0.0
    rest_kosten = je_bogen * rest_boegen
    gesamt = kosten + rest_kosten
    zeilen = [
        f"=== Messung (erste {aufrufe} Boegen) ===",
        f"  Aufrufe: {aufrufe}   Bilder: {bilder}   Dauer: {dauer:.1f} s "
        f"({sek_je_bogen:.1f} s je Bogen)",
        f"  Kosten: {kosten:.6f} USD ({je_bogen:.6f} je Bogen, "
        f"{je_bild:.6f} je Bild)",
        f"  Hochrechnung Rest ({rest_boegen} Boegen, {rest_bilder} Bilder): "
        f"~{rest_kosten:.4f} USD -> Gesamt ~{gesamt:.4f} USD "
        f"von Budget {budget:.2f} USD",
    ]
    if gesamt > budget:
        zeilen.append("  Hinweis: Die Hochrechnung liegt ueber dem Budget — "
                      "der Lauf stoppt an der harten Grenze mit Bericht "
                      "(wiederholbar; der Rest bleibt offen).")
    else:
        zeilen.append(f"  Weiter in Stapeln von {STAPEL_BOEGEN} Boegen.")
    return "\n".join(zeilen)


# ── Einen Bogen ansehen ────────────────────────────────────────────────────

def bogen_verarbeiten(zeilen: list[dict], schluessel: str, sende,
                      thumb_abruf=None, modell: str = STANDARD_MODELL,
                      basis: str = STANDARD_BASIS,
                      preis_ein=STANDARD_PREIS_EIN,
                      preis_aus=STANDARD_PREIS_AUS) -> dict:
    """EINEN Bogen ansehen: eine Anfrage, eine Antwort, je Kachel eine Zeile.

    Holt die Vorschaubilder; Kacheln OHNE Vorschau fallen aus dem Bogen (sie
    bleiben offen und werden beim naechsten Lauf erneut versucht). Der Bogen
    entsteht NUR im Arbeitsspeicher (``bogen_bauen``), gesendet wird genau ein
    Aufruf. Rueckgabe: ``{"gesendet", "bilder", "ohne_vorschau", "eintraege",
    "tokens_ein", "tokens_aus", "kosten_usd", "dauer_s", "modell", "verworfen",
    "unbrauchbar"}`` — die ``eintraege`` tragen ``kachel``, ``beschreibung``
    (entschaerft), ``unbrauchbar`` und die Quellzeile ``zeile``; die fertigen
    JSONL-Zeilen baut der Aufrufer (``jsonl_zeilen_bauen``).
    """
    anfang = time.time()
    ids = [z["fileid"] for z in zeilen if _als_int(z.get("fileid"))]
    vorschauen = vorschau_stapel(ids, STANDARD_GROESSE, abruf=thumb_abruf)
    sendbare = [z for z in zeilen if vorschauen.get(_als_int(z.get("fileid")))]
    ohne_vorschau = len(zeilen) - len(sendbare)
    if not sendbare:
        return {"gesendet": False, "bilder": 0, "ohne_vorschau": ohne_vorschau,
                "eintraege": [], "tokens_ein": 0, "tokens_aus": 0,
                "kosten_usd": 0.0, "dauer_s": round(time.time() - anfang, 2),
                "modell": modell, "verworfen": 0, "unbrauchbar": 0}

    bogen_bytes = bogen_bauen({"zeilen": sendbare}, vorschauen,
                              spalten=SPALTEN, kachel=KACHEL)
    daten_uri = bild_daten_uri(bogen_bytes)
    payload = anfrage_bauen(modell, daten_uri, len(sendbare))
    antwort = sende(payload, schluessel, basis, versuche=VERSUCHE)

    daten = antwort_zerlegen(antwort["text"])
    kacheln = beschreibungen_uebernehmen(daten, len(sendbare))
    verworfen = _als_int(kacheln[0].get("verworfen")) if kacheln else 0
    eintraege: list[dict] = []
    for kachel in kacheln:
        quelle = sendbare[kachel["kachel"] - 1]
        eintraege.append({
            "kachel": kachel["kachel"],
            "beschreibung": geheimnis_entfernen(kachel["beschreibung"], schluessel),
            "unbrauchbar": kachel["unbrauchbar"],
            "zeile": quelle,
        })
    tokens_ein = _als_int(antwort.get("tokens_ein"))
    tokens_aus = _als_int(antwort.get("tokens_aus"))
    return {
        "gesendet": True,
        "bilder": len(sendbare),
        "ohne_vorschau": ohne_vorschau,
        "eintraege": eintraege,
        "tokens_ein": tokens_ein,
        "tokens_aus": tokens_aus,
        "kosten_usd": kosten_berechnen(tokens_ein, tokens_aus,
                                       preis_ein, preis_aus),
        "dauer_s": round(time.time() - anfang, 2),
        "modell": antwort.get("modell") or modell,
        "verworfen": verworfen,
        "unbrauchbar": sum(1 for k in eintraege if k["unbrauchbar"]),
    }


def jsonl_zeilen_bauen(eintraege: list[dict], bogen_id: str, modell: str,
                       kosten_usd, zeit: str) -> list[dict]:
    """Die fertigen JSONL-Zeilen eines Bogens bauen (reine Funktion).

    Genau die vereinbarten Felder: fileid, datei, jahr, monat, tag, ordner,
    beschreibung, bogen_id, modell, kosten_usd, zeit. KEINE Bilddaten.
    ``kosten_usd`` je Zeile = Aufruf-Kosten geteilt durch die Zahl der Zeilen
    (Summe ueber die Zeilen eines Bogens = tatsaechliche Aufruf-Kosten).
    """
    anzahl = len(eintraege)
    anteil = round(float(kosten_usd or 0.0) / anzahl, 8) if anzahl else 0.0
    zeilen: list[dict] = []
    for eintrag in eintraege:
        quelle = eintrag["zeile"]
        zeilen.append({
            "fileid": _als_int(quelle.get("fileid")),
            "datei": str(quelle.get("datei") or ""),
            "jahr": _als_int(quelle.get("jahr")),
            "monat": _als_int(quelle.get("monat")),
            "tag": _als_int(quelle.get("tag")),
            "ordner": str(quelle.get("ordner") or ""),
            "beschreibung": eintrag["beschreibung"],
            "bogen_id": bogen_id,
            "modell": modell,
            "kosten_usd": anteil,
            "zeit": zeit,
        })
    return zeilen


# ── Kommandozeile ──────────────────────────────────────────────────────────

def _kosten_anzeige(kosten) -> str:
    if kosten is None:
        return "Kosten nicht gesetzt"
    return f"{float(kosten):.6f} USD"


def main(argv=None, sende=None, api_abruf=None, thumb_abruf=None,
         env_pfade=None) -> int:
    """Kommandozeilen-Teil.

    ``sende`` (Vision-Transport), ``api_abruf`` (listfolder) und
    ``thumb_abruf`` (getthumbs) sind fuer Tests injizierbar — ohne sie werden
    die echten, tokenbehafteten Abrufe gebaut. ``--trocken``/``--nur-liste``
    brauchen keinen Schluessel und beruehren kein Netz.
    """
    zerleger = argparse.ArgumentParser(
        description="Beschreibung je Einzelbild ueber Kontaktboegen -> "
                    "bild_beschreibungen.jsonl (nur lesend).")
    zerleger.add_argument("--csv", default=STANDARD_CSV,
                          help="Sortierschluessel (CSV aus Stufe 1)")
    zerleger.add_argument("--ausgabe", default=STANDARD_AUSGABE,
                          help="Zielordner der Ausgaben (ausserhalb des Repos)")
    zerleger.add_argument("--jsonl", default="",
                          help="Zieldatei der Beschreibungen (Standard: "
                               "<ausgabe>/bild_beschreibungen.jsonl)")
    zerleger.add_argument("--limit", type=int, default=0,
                          help="hoechstens so viele Boegen senden (0 = alle)")
    zerleger.add_argument("--budget", type=float, default=STANDARD_BUDGET_USD,
                          help="harte Kostengrenze in USD (Standard "
                               f"{STANDARD_BUDGET_USD})")
    zerleger.add_argument("--kacheln-pro-bogen", dest="kacheln_pro_bogen",
                          type=int, default=KACHELN_JE_BOGEN,
                          help=f"Kacheln je Kontaktbogen (Standard {KACHELN_JE_BOGEN})")
    zerleger.add_argument("--spalten", type=int, default=SPALTEN,
                          help=f"Kacheln je Reihe (Standard {SPALTEN})")
    zerleger.add_argument("--kachel", type=int, default=KACHEL,
                          help=f"Kachelgroesse in Pixeln (Standard {KACHEL})")
    zerleger.add_argument("--stapel", type=int, default=STAPEL_BOEGEN,
                          help=f"Fortschritt je Stapel (Standard {STAPEL_BOEGEN})")
    zerleger.add_argument("--modell", default=STANDARD_MODELL,
                          help=f"Vision-Modell (Standard {STANDARD_MODELL})")
    zerleger.add_argument("--basis", default=STANDARD_BASIS,
                          help="OpenRouter-Basis-URL")
    zerleger.add_argument("--preis-ein", dest="preis_ein", type=float,
                          default=STANDARD_PREIS_EIN,
                          help=f"USD je 1 Mio Eingabe-Tokens (gemessen: "
                               f"{STANDARD_PREIS_EIN})")
    zerleger.add_argument("--preis-aus", dest="preis_aus", type=float,
                          default=STANDARD_PREIS_AUS,
                          help=f"USD je 1 Mio Ausgabe-Tokens (gemessen: "
                               f"{STANDARD_PREIS_AUS})")
    zerleger.add_argument("--trocken", action="store_true",
                          help="nur zeigen, was geplant ist (holt und sendet nichts)")
    zerleger.add_argument("--nur-liste", dest="nur_liste", action="store_true",
                          help="nur die Planung auflisten (kein Netz, kein Schluessel)")
    args = zerleger.parse_args(argv)

    # Zielordner ZUERST pruefen: Ausgaben gehoeren ausserhalb des Repos.
    # Das gilt fuer jeden Modus, auch --trocken und --nur-liste.
    _pruefe_ausgabe(args.ausgabe)

    if not os.path.exists(args.csv):
        print(f"Sortierschluessel nicht gefunden: {args.csv}")
        return 2
    if args.kacheln_pro_bogen < 1:
        print("--kacheln-pro-bogen muss mindestens 1 sein.")
        return 2

    start = time.time()
    jsonl = args.jsonl or os.path.join(args.ausgabe, STANDARD_JSONL_NAME)
    zeilen = zeilen_lesen(args.csv)
    vorbereitet = zeilen_vorbereiten(zeilen)
    ohne_datum = len(zeilen) - len(vorbereitet)
    erledigt = erledigtes_lesen(jsonl)
    ohne_netz_offen = [z for z in vorbereitet if not ist_erledigt(z, erledigt)]

    print(f"Sortierschluessel: {args.csv}")
    print(f"Zeilen: {len(zeilen)}   ohne Datum: {ohne_datum}   "
          f"schon beschrieben (Dateiabgleich): "
          f"{len(vorbereitet) - len(ohne_netz_offen)}")
    print(f"Boegen: je {args.kacheln_pro_bogen} Kacheln   "
          f"Modell: {args.modell}   Budget: {args.budget:.2f} USD")
    print(f"Ausgabe: {args.ausgabe}   JSONL: {jsonl}")

    if args.nur_liste:
        geschaetzte_boegen = ((len(ohne_netz_offen) + args.kacheln_pro_bogen - 1)
                              // args.kacheln_pro_bogen)
        print(f"\nVoraussichtlich offen: {len(ohne_netz_offen)} Dateien "
              f"(~{geschaetzte_boegen} Boegen, noch ohne fileid-Abgleich).")
        print(f"Nur-Liste: nichts geholt, nichts gesendet "
              f"({_dauer_seit(start):.1f} s).")
        return 0

    if args.trocken:
        geschaetzte_boegen = ((len(ohne_netz_offen) + args.kacheln_pro_bogen - 1)
                              // args.kacheln_pro_bogen)
        print(f"\nVoraussichtlich offen: {len(ohne_netz_offen)} Dateien "
              f"(~{geschaetzte_boegen} Boegen — der fileid-Abgleich laeuft erst "
              f"im echten Lauf).")
        print("Trockenlauf: nichts geholt, nichts gesendet, nichts geschrieben "
              f"({_dauer_seit(start):.1f} s).")
        return 0

    schluessel = schluessel_finden(env_pfade)
    if not schluessel:
        print(f"\nKein {SCHLUESSEL_VARIABLE} gefunden — geprueft wurden "
              f"Umgebungsvariable, {os.path.join(REPO, 'backend', '.env')} und "
              f"Workspace-.env. Es wird NICHTS gesendet. Ohne --trocken/"
              f"--nur-liste wird der Schluessel gebraucht.")
        return 2

    abruf_api = api_abruf or echter_api_abruf()
    abruf_thumb = thumb_abruf or echter_thumb_abruf()
    speicher: dict = {}
    ohne_kennung = 0
    try:
        for zeile in vorbereitet:
            index = dateien_im_ordner(zeile.get("ordner") or "", abruf_api,
                                      speicher)
            gefunden = index.get(str(zeile.get("datei") or ""))
            zeile["fileid"] = gefunden["fileid"] if gefunden else None
            if not gefunden:
                ohne_kennung += 1
    except Exception as problem:                      # Klasse statt Text
        print(f"\npCloud-Abfrage fehlgeschlagen "
              f"({problem.__class__.__name__}): es wird NICHTS gesendet. "
              f"Erneut versuchen, sobald die Verbindung steht.")
        return 2

    schon_beschrieben = 0
    offen: list[dict] = []
    for zeile in vorbereitet:
        if not _als_int(zeile.get("fileid")):
            continue
        if ist_erledigt(zeile, erledigt):
            schon_beschrieben += 1
            continue
        offen.append(zeile)
    offen = sortierschluessel_sortieren(offen)
    boegen = boegen_planen(offen, args.kacheln_pro_bogen)
    if args.limit and args.limit > 0:
        boegen = boegen[:args.limit]

    print(f"\nOhne Bildkennung (nicht in pCloud gefunden): {ohne_kennung}")
    print(f"Schon beschrieben (uebersprungen): {schon_beschrieben}")
    print(f"Offen fuer Vision: {len(offen)} Dateien -> {len(boegen)} Boegen"
          + (f" (Limit {args.limit})" if args.limit and args.limit > 0 else "")
          + ".")

    senden = sende or sende_aufruf
    ausgegeben = 0.0
    aufrufe = 0
    dauer_aufrufe = 0.0
    bilder = 0
    unbrauchbar_gesamt = 0
    zeilen_neu = 0
    fehlgeschlagen = 0
    leer_uebersprungen = 0
    messung_gedruckt = False
    stoppgrund = ""
    abgebrochen = False

    print()
    try:
        for nummer, bogen in enumerate(boegen, start=1):
            # Kostenbremse VOR dem Aufruf: kein Aufruf, der die Grenze reissen
            # wuerde (Schaetzung = Durchschnitt der bisherigen Aufrufe).
            schaetzung = (ausgegeben / aufrufe) if aufrufe else 0.0
            if budget_stoppt(ausgegeben, schaetzung, args.budget):
                stoppgrund = ("Kostenbremse: "
                              f"{ausgegeben:.6f} USD ausgegeben + ~{schaetzung:.6f} "
                              f"USD naechster Bogen > Budget {args.budget:.2f} USD")
                print(f"\n! {stoppgrund}")
                break

            try:
                ergebnis = bogen_verarbeiten(
                    bogen["zeilen"], schluessel, senden, abruf_thumb,
                    modell=args.modell, basis=args.basis,
                    preis_ein=args.preis_ein, preis_aus=args.preis_aus)
            except Exception as problem:              # entschaerfen, weiter
                roh = str(problem)
                meldung = geheimnis_entfernen(
                    f"{problem.__class__.__name__}: {roh}" if roh
                    else problem.__class__.__name__, schluessel)
                fehlgeschlagen += 1
                print(f"  {bogen['bogen_id']}: FEHLER — {meldung} "
                      f"(Dateien bleiben offen)")
                continue

            if not ergebnis["gesendet"]:
                leer_uebersprungen += 1
                print(f"  {bogen['bogen_id']}: uebersprungen — keine Vorschau "
                      f"({ergebnis['ohne_vorschau']} Kacheln ohne Bild)")
                continue

            zeit = datetime.datetime.now().isoformat(timespec="seconds")
            neue = jsonl_zeilen_bauen(ergebnis["eintraege"], bogen["bogen_id"],
                                      ergebnis["modell"],
                                      ergebnis["kosten_usd"], zeit)
            anzahl_geschrieben = zeilen_anhaengen(jsonl, neue)
            zeilen_neu += anzahl_geschrieben
            kosten = float(ergebnis["kosten_usd"] or 0.0)
            ausgegeben += kosten
            aufrufe += 1
            dauer_aufrufe += float(ergebnis["dauer_s"])
            bilder += ergebnis["bilder"]
            unbrauchbar_gesamt += ergebnis["unbrauchbar"]
            print(f"  {bogen['bogen_id']}: {anzahl_geschrieben}/"
                  f"{ergebnis['bilder']} Kacheln beschrieben, "
                  f"{ergebnis['tokens_ein']}+{ergebnis['tokens_aus']} Tokens, "
                  f"{_kosten_anzeige(ergebnis['kosten_usd'])}, "
                  f"{ergebnis['dauer_s']} s"
                  + (f", verworfen: {ergebnis['verworfen']}"
                     if ergebnis["verworfen"] else "")
                  + (f", unbrauchbar: {ergebnis['unbrauchbar']}"
                     if ergebnis["unbrauchbar"] else "")
                  + (f", ohne Vorschau: {ergebnis['ohne_vorschau']}"
                     if ergebnis["ohne_vorschau"] else ""))

            if (not messung_gedruckt and aufrufe == MESSUNG_BOEGEN
                    and len(boegen) > MESSUNG_BOEGEN):
                rest_boegen = len(boegen) - nummer
                rest_bilder = round(rest_boegen * (bilder / aufrufe))
                print()
                print(messung_bericht(aufrufe, bilder, ausgegeben,
                                      dauer_aufrufe, rest_boegen, rest_bilder,
                                      args.budget))
                print()
                messung_gedruckt = True
            elif args.stapel > 0 and nummer % args.stapel == 0:
                print(f"  -- Stapel {nummer // args.stapel}/"
                      f"{(len(boegen) + args.stapel - 1) // args.stapel}: "
                      f"{nummer} Boegen, {bilder} Bilder, "
                      f"{ausgegeben:.4f} USD, {_dauer_seit(start):.0f} s --")
    except KeyboardInterrupt:
        abgebrochen = True
        stoppgrund = ("Abbruch durch Strg+C — die JSONL ist bis hier "
                      "vollstaendig; erneuter Aufruf setzt fort")
        print(f"\n! {stoppgrund}")

    dauer = _dauer_seit(start)
    print()
    print("=== Bericht ===")
    print(f"  Boegen geplant      : {len(boegen)}")
    print(f"  gesendet            : {aufrufe}   fehlgeschlagen: {fehlgeschlagen}   "
          f"ohne Vorschau uebersprungen: {leer_uebersprungen}")
    print(f"  beschrieben (neu)   : {zeilen_neu} Zeilen")
    print(f"  Bilder in Boegen    : {bilder}   davon unbrauchbar markiert: "
          f"{unbrauchbar_gesamt}")
    print(f"  Kosten (Vision)     : {ausgegeben:.6f} USD von Budget "
          f"{args.budget:.2f} USD")
    print(f"  Dauer               : {dauer:.1f} s")
    print(f"  JSONL               : {jsonl}")
    if stoppgrund:
        print(f"  Stopp               : {stoppgrund}")
    print("  Fortsetzen          : erneuter Aufruf macht mit den offenen "
          "Dateien weiter (bereits Beschriebenes wird uebersprungen).")
    return 130 if abgebrochen else 0


if __name__ == "__main__":
    raise SystemExit(main())
