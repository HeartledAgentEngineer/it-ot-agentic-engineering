"""Bild-Beschreibungen einbetten -> ``~/foto_sortierung/bild_index.db``.

Was dieses Werkzeug tut (Plan-Schritt N15, 28.09.2026):
  ``bild_beschreiben.py`` hat je Einzelbild eine Beschreibung erzeugt
  (``bild_beschreibungen.jsonl``). Dieses Werkzeug macht daraus die
  **Bildsuche als Textsuche**: jeder Beschreibungstext wird ueber den
  bestehenden Einbettungsweg (OpenRouter, ``openai/text-embedding-3-small``)
  in einen Vektor gerechnet und in eine kleine SQLite-Datenbank gelegt —
  ``bild_index.db`` mit der Tabelle ``bilder`` (fileid, datum, ordner,
  beschreibung, vektor). Vektoren liegen wie im Text-Archiv als float16-BLOB
  (halber Speicher, ausreichend genau fuer die Aehnlichkeitssuche).

Wiederverwendet statt neu erfunden:
  Der Einbetter, die Preis-Konstante (0,02 USD je 1 Mio Token), der
  float16-Pack und die Schluessel-Suche kommen WORTWOERTLICH aus
  ``backend/scripts/archiv_index_bauen.py`` (das Muster des Text-Archivs).
  Es entsteht KEIN zweiter Einbettungsweg.

Abgrenzung (bewusst):
  * Das Text-Archiv (``Chats von GPT, GEMINI, Claude/db/*``) wird NICHT
    angefasst — hier entsteht nur eine unabhaengige Bild-Datenbank.
  * Kein Neuaufbau: es werden nur FEHLENDE fileids eingebettet (Idempotenz).
    Zweiter Lauf -> 0 neue Vektoren.

Kosten:
  ``--budget`` (Standard 1,00 USD) ist die harte Grenze. Vor dem Schreiben
  wird geschaetzt (Zeichen/3,6 = Token) und gegen das Budget geprueft; wird
  die Grenze waehrend des Laufs erreicht, ist Schluss — die bereits
  eingebetteten Buendel bleiben erhalten (derselbe Aufruf macht spaeter
  dort weiter).

Aufruf (venv des Backends):

    cd backend
    .venv/Scripts/python ../tools/foto_sortierung/bild_index_einbetten.py
        # Trockenlauf (Standard): zeigt offene Bilder + Kostenschaetzung
    .venv/Scripts/python ../tools/foto_sortierung/bild_index_einbetten.py --schreiben
        # bettet die offenen Beschreibungen ein
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent
BACKEND = os.path.join(REPO, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

# Der bestehende Einbettungsweg des Projekts (Wort fuer Wort wiederverwendet).
import scripts.archiv_index_bauen as _archiv  # noqa: E402

PREIS_JE_MIO_TOKEN = _archiv.PREIS_JE_MIO_TOKEN          # 0,02 USD je 1 Mio
STANDARD_MODELL = _archiv.STANDARD_MODELL
STANDARD_BASIS = _archiv.STANDARD_BASIS
ZEICHEN_JE_TOKEN = _archiv.ZEICHEN_JE_TOKEN

STANDARD_JSONL = os.path.join(os.path.expanduser("~"), "foto_sortierung",
                              "bild_beschreibungen.jsonl")
STANDARD_DB = os.path.join(os.path.expanduser("~"), "foto_sortierung",
                           "bild_index.db")

STANDARD_BUDGET_USD = 1.00
STANDARD_STAPEL = 128
FORTschritt_JE = 1000
MAX_FEHLVERSUCHE = 5

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS bilder (
    fileid       INTEGER PRIMARY KEY,
    datum        TEXT NOT NULL DEFAULT '',
    ordner       TEXT NOT NULL DEFAULT '',
    beschreibung TEXT NOT NULL DEFAULT '',
    vektor       BLOB
);
CREATE TABLE IF NOT EXISTS meta (
    schluessel TEXT PRIMARY KEY,
    wert       TEXT NOT NULL DEFAULT ''
);
"""


class BildIndexFehler(Exception):
    """Fehler dieses Werkzeugs — die Meldung enthaelt nie den Schluessel."""


class BudgetUeberschritten(RuntimeError):
    """Die geschaetzten Kosten liegen ueber der Grenze — es wird nichts geschrieben."""


def _pruefe_ausserhalb(pfad: str, was: str) -> str:
    """Sicherstellen, dass eine Datei AUSSERHALB des Repos liegt.

    Ausgaben und Datenbanken dieses Werkzeugs gehoeren neben die
    Sortier-Daten (Standard ``~/foto_sortierung``), nicht ins Repo — dort
    liegen private Dateinamen. Verstoss = deutsche Klartext-Meldung +
    SystemExit(2), bevor irgendetwas gelesen oder geschrieben wird.
    """
    ziel = os.path.normcase(os.path.abspath(pfad))
    repo = os.path.normcase(os.path.abspath(REPO))
    try:
        gemeinsam = os.path.commonpath([ziel, repo])
    except ValueError:                       # anderes Laufwerk: nie im Repo
        return pfad
    if gemeinsam == repo:
        print(f"{was} liegt IM Repo und ist nicht erlaubt: {pfad}\n"
              f"Gehoert ausserhalb des Repos (Standard: ~/foto_sortierung); "
              f"es wird NICHTS gelesen und NICHTS geschrieben.")
        raise SystemExit(2)
    return pfad


def _als_int(wert) -> int:
    """Zahl tolerant lesen — unbrauchbare Werte werden ehrlich 0."""
    try:
        return int(float(wert))
    except (TypeError, ValueError):
        return 0


# ── Beschreibungen lesen (reine Funktion) ──────────────────────────────────

def beschreibungen_lesen(jsonl_pfad: str) -> dict:
    """``bild_beschreibungen.jsonl`` lesen: eine Zeile je fileid.

    Rueckgabe ``{"zeilen": [...], "verworfen": n, "dubletten": n}``; je Zeile
    ``{"fileid", "datum", "ordner", "beschreibung"}``. Regeln: eine Zeile ohne
    brauchbare fileid ODER ohne Beschreibung wird verworfen (gezaehlt); eine
    doppelte fileid wird nur EINMAL genommen (die erste; gezaehlt). Kaputte
    JSON-Zeilen werden uebersprungen — eine kaputte Zeile darf den Lauf nicht
    anhalten.
    """
    zeilen: list[dict] = []
    verworfen = 0
    dubletten = 0
    gesehen: set = set()
    if not os.path.isfile(jsonl_pfad):
        raise BildIndexFehler(f"Beschreibungsdatei nicht gefunden: {jsonl_pfad}")
    with open(jsonl_pfad, encoding="utf-8", errors="replace") as datei:
        for roh in datei:
            roh = roh.strip()
            if not roh:
                continue
            try:
                eintrag = json.loads(roh)
            except ValueError:
                verworfen += 1
                continue
            if not isinstance(eintrag, dict):
                verworfen += 1
                continue
            fileid = _als_int(eintrag.get("fileid"))
            beschreibung = eintrag.get("beschreibung")
            if not fileid or not isinstance(beschreibung, str) or not beschreibung.strip():
                verworfen += 1
                continue
            if fileid in gesehen:
                dubletten += 1
                continue
            gesehen.add(fileid)
            jahr = _als_int(eintrag.get("jahr"))
            monat = _als_int(eintrag.get("monat"))
            tag = _als_int(eintrag.get("tag"))
            datum = f"{jahr:04d}-{monat:02d}-{tag:02d}" if jahr else ""
            zeilen.append({
                "fileid": fileid,
                "datum": datum,
                "ordner": str(eintrag.get("ordner") or ""),
                "beschreibung": beschreibung.strip(),
            })
    return {"zeilen": zeilen, "verworfen": verworfen, "dubletten": dubletten}


def token_schaetzen(texte) -> int:
    """Token aus der Textlaenge schaetzen (vorsichtig, lieber zu hoch)."""
    return int(sum(len(t or "") for t in texte) / ZEICHEN_JE_TOKEN)


def datenbank_oeffnen(db_pfad: str) -> sqlite3.Connection:
    """``bild_index.db`` oeffnen und das Schema sicherstellen (anlegend)."""
    ordner = os.path.dirname(os.path.abspath(db_pfad))
    os.makedirs(ordner, exist_ok=True)
    con = sqlite3.connect(db_pfad)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA_SQL)
    return con


def vorhandene_fileids(db_pfad: str) -> set:
    """Fileids, die schon in der Datenbank stehen (nur lesend, ohne Anlegen)."""
    if not os.path.isfile(db_pfad):
        return set()
    con = sqlite3.connect(f"file:{db_pfad}?mode=ro", uri=True)
    try:
        return {_als_int(z[0]) for z in con.execute("SELECT fileid FROM bilder")}
    except sqlite3.Error:                    # leere/kaputte Datei: alles offen
        return set()
    finally:
        con.close()


def _meta_lesen(con: sqlite3.Connection, schluessel: str, vorgabe: str = "0") -> str:
    zeile = con.execute("SELECT wert FROM meta WHERE schluessel = ?",
                        (schluessel,)).fetchone()
    return zeile[0] if zeile else vorgabe


def _meta_setzen(con: sqlite3.Connection, werte: dict) -> None:
    con.executemany("INSERT OR REPLACE INTO meta (schluessel, wert) VALUES (?,?)",
                    [(k, str(v)) for k, v in werte.items()])
    con.commit()


# ── Einbetten ──────────────────────────────────────────────────────────────

def einbetten(jsonl_pfad: str, db_pfad: str, einbetter=None,
              budget_usd: float = STANDARD_BUDGET_USD,
              stapel: int = STANDARD_STAPEL, schreiben: bool = False,
              fortschritt_je: int = FORTschritt_JE, ausgabe_strom=None) -> dict:
    """Fehlende Beschreibungen einbetten und in ``bilder`` ablegen.

    ``einbetter`` ist injizierbar (Tests: Attrappe ohne Netz). Ohne
    ``schreiben`` passiert nichts ausser Zahlen (Trockenlauf) — auch die
    Datenbankdatei wird dann NICHT angelegt.
    """
    strom = ausgabe_strom or sys.stdout
    stapel = max(1, _als_int(stapel))
    zaehler: dict = {
        "zeilen": 0, "verworfen": 0, "dubletten": 0,
        "offen": 0, "schon": 0, "neu": 0,
        "tokens_geschaetzt": 0, "tokens_gezaehlt": 0,
        "kosten_schaetzung_usd": 0.0, "kosten_usd": 0.0,
        "dauer_s": 0.0, "budget_usd": budget_usd, "abgebrochen": False,
        "modell": getattr(einbetter, "modell", STANDARD_MODELL),
    }
    start = time.time()

    gelesen = beschreibungen_lesen(jsonl_pfad)
    zaehler["zeilen"] = len(gelesen["zeilen"])
    zaehler["verworfen"] = gelesen["verworfen"]
    zaehler["dubletten"] = gelesen["dubletten"]

    schon = vorhandene_fileids(db_pfad)
    offen = [z for z in gelesen["zeilen"] if z["fileid"] not in schon]
    zaehler["schon"] = len(gelesen["zeilen"]) - len(offen)
    zaehler["offen"] = len(offen)
    zaehler["tokens_geschaetzt"] = token_schaetzen(
        [z["beschreibung"] for z in offen])
    # Bewusst NICHT gerundet: eine gerundete Schaetzung koennte die Grenze
    # knapp verfehlen (oder knapp reissen) — gerechnet wird genau.
    zaehler["kosten_schaetzung_usd"] = (
        zaehler["tokens_geschaetzt"] / 1_000_000 * PREIS_JE_MIO_TOKEN)

    if einbetter is not None and zaehler["kosten_schaetzung_usd"] > budget_usd:
        raise BudgetUeberschritten(
            f"Schaetzung {zaehler['kosten_schaetzung_usd']:.6f} USD liegt ueber "
            f"dem Budget von {budget_usd} USD - nichts geschrieben.")

    if not schreiben or einbetter is None or not offen:
        zaehler["dauer_s"] = round(time.time() - start, 1)
        return zaehler

    con = datenbank_oeffnen(db_pfad)
    try:
        print(f"→ Einbetten (offen: {len(offen)}, "
              f"Schaetzung {zaehler['kosten_schaetzung_usd']:.6f} USD)",
              file=strom, flush=True)
        fehlversuche = 0
        for anfang in range(0, len(offen), stapel):
            block = offen[anfang:anfang + stapel]
            try:
                vektoren, _ = einbetter([z["beschreibung"] for z in block])
            except Exception as problem:      # noqa: BLE001 — Netz ist vielfaeltig
                fehlversuche += 1
                print(f"  ! Block ab {anfang} fehlgeschlagen ({fehlversuche}/"
                      f"{MAX_FEHLVERSUCHE}): {problem.__class__.__name__}",
                      file=strom, flush=True)
                if fehlversuche >= MAX_FEHLVERSUCHE:
                    raise
                continue
            con.executemany(
                "INSERT OR REPLACE INTO bilder "
                "(fileid, datum, ordner, beschreibung, vektor) VALUES (?,?,?,?,?)",
                [(z["fileid"], z["datum"], z["ordner"], z["beschreibung"],
                  _archiv._vektor_blob(v))
                 for z, v in zip(block, vektoren)],
            )
            con.commit()
            zaehler["neu"] += len(block)
            if (anfang // stapel) % max(1, fortschritt_je // stapel) == 0:
                print(f"    {zaehler['neu']}/{len(offen)} eingebettet "
                      f"({time.time() - start:.0f}s)", file=strom, flush=True)

            # Harte Kostengrenze auch WAEHREND des Laufs.
            verbraucht = int(getattr(einbetter, "token_gesamt", 0) or 0)
            kosten = verbraucht / 1_000_000 * PREIS_JE_MIO_TOKEN
            if kosten > budget_usd:
                zaehler["abgebrochen"] = True
                print(f"  ! Budget {budget_usd} USD erreicht ({kosten:.6f} USD) - "
                      f"{len(offen) - zaehler['neu']} Bilder bleiben offen "
                      f"(wiederholbar).", file=strom, flush=True)
                break

        zaehler["tokens_gezaehlt"] = int(getattr(einbetter, "token_gesamt", 0) or 0)
        zaehler["kosten_usd"] = round(
            zaehler["tokens_gezaehlt"] / 1_000_000 * PREIS_JE_MIO_TOKEN, 6)

        # Meta fortschreiben (kumuliert ueber Laeufe), Zahlen ohne Inhalte.
        alt_tokens = _als_int(_meta_lesen(con, "tokens_gezaehlt", "0"))
        alt_kosten = float(_meta_lesen(con, "kosten_usd", "0") or 0)
        vektor_zeile = con.execute(
            "SELECT vektor FROM bilder WHERE vektor IS NOT NULL LIMIT 1").fetchone()
        dimension = (len(vektor_zeile[0]) // 2) if vektor_zeile else 0
        _meta_setzen(con, {
            "stand": datetime.now(timezone.utc).isoformat(),
            "bilder": con.execute("SELECT count(*) FROM bilder").fetchone()[0],
            "vektoren": con.execute(
                "SELECT count(*) FROM bilder WHERE vektor IS NOT NULL").fetchone()[0],
            "modell": zaehler["modell"],
            "dimension": dimension,
            "vektor_speicher": "float16",
            "preis_je_mio_token_usd": PREIS_JE_MIO_TOKEN,
            "tokens_gezaehlt": alt_tokens + zaehler["tokens_gezaehlt"],
            "kosten_usd": round(alt_kosten + zaehler["kosten_usd"], 6),
        })
    finally:
        con.close()

    zaehler["dauer_s"] = round(time.time() - start, 1)
    return zaehler


# ── Bericht ────────────────────────────────────────────────────────────────

def bericht_text(zaehler: dict, db_pfad: str, modus: str) -> str:
    """Kurzer Abschlussbericht — Zahlen, keine Inhalte."""
    return (
        f"\n=== Bildindex ({modus}) ===\n"
        f"  Beschreibungen gelesen : {zaehler['zeilen']} "
        f"(verworfen: {zaehler['verworfen']}, Dubletten: {zaehler['dubletten']})\n"
        f"  schon im Index        : {zaehler['schon']}\n"
        f"  neu eingebettet       : {zaehler['neu']} von {zaehler['offen']} offenen\n"
        f"  Token (schaetzung)    : {zaehler['tokens_geschaetzt']}\n"
        f"  Token (gezaehlt)      : {zaehler['tokens_gezaehlt']}\n"
        f"  Kosten                : {zaehler['kosten_usd']:.6f} USD "
        f"(Grenze {zaehler['budget_usd']:.2f} USD, "
        f"{PREIS_JE_MIO_TOKEN} USD/1M Token)\n"
        f"  Modell                : {zaehler.get('modell', '')}\n"
        f"  Datenbank             : {db_pfad}\n"
        f"  Dauer                 : {zaehler['dauer_s']} s"
        + ("\n  ! Lauf am Budget abgebrochen - offene Bilder bleiben liegen"
           if zaehler.get("abgebrochen") else "")
    )


# ── Kommandozeile ──────────────────────────────────────────────────────────

def main(argv=None, einbetter=None, env_pfade=None) -> int:
    """Kommandozeilen-Teil (``einbetter`` fuer Tests injizierbar)."""
    zerleger = argparse.ArgumentParser(
        description="Bild-Beschreibungen einbetten -> bild_index.db "
                    "(Tabellen bilder/meta, float16-Vektoren).")
    zerleger.add_argument("--jsonl", default=STANDARD_JSONL,
                          help="Beschreibungsdatei (JSONL)")
    zerleger.add_argument("--db", default=STANDARD_DB,
                          help="Ziel-Datenbank (SQLite, ausserhalb des Repos)")
    zerleger.add_argument("--trocken", action="store_true",
                          help="nur rechnen (Standard ohne --schreiben)")
    zerleger.add_argument("--schreiben", action="store_true",
                          help="wirklich einbetten und schreiben")
    zerleger.add_argument("--budget", type=float, default=STANDARD_BUDGET_USD,
                          help=f"harte Kostengrenze in USD (Standard "
                               f"{STANDARD_BUDGET_USD})")
    zerleger.add_argument("--stapel", type=int, default=STANDARD_STAPEL,
                          help=f"Texte je Einbettungs-Aufruf (Standard "
                               f"{STANDARD_STAPEL})")
    zerleger.add_argument("--modell", default=STANDARD_MODELL,
                          help=f"Einbettungsmodell (Standard {STANDARD_MODELL})")
    zerleger.add_argument("--basis-url", dest="basis_url", default=STANDARD_BASIS,
                          help="OpenRouter-Basis-URL")
    args = zerleger.parse_args(argv)
    if args.trocken and args.schreiben:
        print("Bitte nur eines von --trocken und --schreiben angeben.")
        return 2

    _pruefe_ausserhalb(args.jsonl, "Die Beschreibungsdatei")
    _pruefe_ausserhalb(args.db, "Die Zieldatenbank")

    if not os.path.isfile(args.jsonl):
        print(f"Beschreibungsdatei nicht gefunden: {args.jsonl}\n"
              f"Zuerst bild_beschreiben.py laufen lassen.")
        return 2

    schreiben = bool(args.schreiben)
    modus = "schreiben" if schreiben else "Trockenlauf"
    print(f"Beschreibungen : {args.jsonl}")
    print(f"Datenbank      : {args.db}")
    print(f"Modus          : {modus} | Modell: {args.modell} | "
          f"Budget: {args.budget:.2f} USD")

    rechner = einbetter
    if schreiben and rechner is None:
        schluessel = _archiv._schluessel_holen()
        if not schluessel:
            print("Kein OPENROUTER_API_KEY gefunden (backend/.env oder "
                  "Workspace-.env) - ohne --schreiben laeuft der Trockenlauf.")
            return 3
        rechner = _archiv.EinbetterOpenRouter(
            schluessel, modell=args.modell, basis_url=args.basis_url,
            stapel=args.stapel)

    try:
        zaehler = einbetten(args.jsonl, args.db, einbetter=rechner,
                            budget_usd=args.budget, stapel=args.stapel,
                            schreiben=schreiben)
    except BudgetUeberschritten as problem:
        print(f"\nBudget-Grenze: {problem}")
        return 4
    except BildIndexFehler as problem:
        print(f"\n{problem}")
        return 2

    print(bericht_text(zaehler, args.db, modus))
    if not schreiben:
        print("\nTrockenlauf - nichts geschrieben. Mit --schreiben einbetten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
