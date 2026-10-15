"""Messwerkzeug: Was durchsucht der Wissensspeicher wirklich? (15.10.2026)

Anlass: Punkt 6 der Wunschliste vom 14.10.2026 ("Volltextsuche ueber alles:
WhatsApp, Gemini, Claude, Bildbeschreibungen"). Dort stehen vier Behauptungen
ueber den Bestand - "eine Mischsuche existiert", "hoechstens 8 Fundstellen
kommen beim Modell an", "keinen Weg, einen Verlauf vollstaendig zu lesen", "die
Bildbeschreibungen liegen nicht im Index". **Dieses Werkzeug misst sie.**

Das Werkzeug **misst nur**. Es oeffnet die Archive **nur lesend** (``mode=ro``),
liest **keinen Inhalt** aus ihnen, oeffnet **kein Bild**, ruft **kein Netz** und
**kein Modell** (keine Einbettung, keine Kosten), **schreibt nichts** und gibt
**keinen Archivtext** aus - nur Zahlen, Quellennamen und Datei:Zeile.

Gemessen wird:

* **Umfang des Suchindex** je Quelle: Gespraeche, Nachrichten, Chunks, Chunks mit
  Vektor - damit ist belegt, welche Quellen die Suche ueberhaupt sieht (und ob
  eine Bilder-Quelle darunter ist).
* **Groesse der Gespraeche**: groesstes, mittleres (Median) und wie viele
  Gespraeche mehr Nachrichten haben, als ein Leseaufruf zurueckgeben kann
  (Deckel + 2 x Kontext). Das ist die Zahl hinter "Verlauf nicht vollstaendig
  lesbar".
* **Bildindex** (``bild_index.db``): Bilder, mit Vektor, mit Beschreibung - und
  die Zahl der Beschreibungszeilen in den lokalen JSONL-Dateien. Beides steht
  **ausserhalb** des Suchindex; die Zahlen zeigen, wie viel Suche dort fehlt.
* **Deckel im Antwortweg**, aus dem Code gelesen (Datei:Zeile): Standardweg,
  Werkzeug (Voreinstellung und Hoechstwert), Kontext beim Nachlesen, Zeichenkuerzung.
  Wird eine Zeile nicht gefunden, steht das ehrlich da statt einer geratenen Zahl.

Aufruf (aus dem Projektordner ``personal_ai_agent``)::

    backend\\.venv\\Scripts\\python.exe tools\\archiv\\suchumfang_messen.py

Mit ``--archiv``/``--bildindex``/``--ordner`` lassen sich die Pfade umstellen.
Fehlt eine Datei, wird das ehrlich gemeldet (kein Abbruch).
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import statistics
import sys
from pathlib import Path

PROJEKT = Path(__file__).resolve().parents[2]
# Der Arbeitsbaum (Repo-Wurzel) liegt zwei Ebenen darueber; dort liegen auch die
# Archivordner. Fehlt er, wird das beim Messen ehrlich gemeldet - nie geraten.
REPO = PROJEKT.parent.parent

# Der Archivindex liegt im (per .gitignore gesperrten) Archivordner.
ARCHIV_ORDNER = "Chats von GPT, GEMINI, Claude"
STANDARD_ARCHIV = REPO / ARCHIV_ORDNER / "db" / "archiv_index.db"
STANDARD_BILDINDEX = Path.home() / "foto_sortierung" / "bild_index.db"
STANDARD_ORDNER = Path.home() / "foto_sortierung"

# Beschreibungsdateien der Bildkette - sie stehen in keinem Suchindex.
STANDARD_BESCHREIBUNGEN = (
    "bild_beschreibungen.jsonl",
    "bild_beschreibungen_reich.jsonl",
    "bild_beschreibungen_papa_reich.jsonl",
    "bild_beschreibungen_rest_reich.jsonl",
    "bild_beschreibungen_altbestand_reich.jsonl",
)

# Quellen, die nach einer Bilder-Quelle aussehen (fuer den klaren Befund).
BILD_QUELLEN = ("bild", "bilder", "foto", "fotos", "image", "vision")


def index_oeffnen(pfad: Path) -> sqlite3.Connection:
    """Oeffnet die SQLite-Datei **nur lesend** (``mode=ro``); kein WAL, kein Schreiben."""
    return sqlite3.connect(f"file:{pfad.as_posix()}?mode=ro", uri=True)


def tabellen(con: sqlite3.Connection) -> list[str]:
    """Namen aller Tabellen (Schema-Erkundung, keine Inhalte)."""
    return [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]


def quellen_zaehlen(con: sqlite3.Connection) -> list[dict]:
    """Zahlen je Quelle - bewusst nur ``count(*)``, kein Text.

    Chunks mit Vektor kommen aus ``chunks.hat_vektor`` (0/1), das die
    Bau-Skripte selbst fuehren - kein Vektorblob wird angefasst.
    """
    zeilen = con.execute(
        "SELECT source, COUNT(*), COUNT(DISTINCT conversation_id) FROM nachrichten "
        "GROUP BY source ORDER BY 2 DESC").fetchall()
    gemessen: list[dict] = []
    for source, nachrichten, gespraeche in zeilen:
        chunks = con.execute("SELECT COUNT(*) FROM chunks WHERE source = ?",
                             (source,)).fetchone()[0]
        mit_vektor = con.execute(
            "SELECT COUNT(*) FROM chunks WHERE source = ? AND COALESCE(hat_vektor, 0) = 1",
            (source,)).fetchone()[0]
        gemessen.append({"quelle": source, "gespraeche": gespraeche,
                         "nachrichten": nachrichten, "chunks": chunks,
                         "chunks_mit_vektor": mit_vektor})
    return gemessen


def verlauf_umfang(con: sqlite3.Connection, grenze: int) -> dict:
    """Wie lang sind die Gespraeche, und wie viele passen **nicht** in einen Leseaufruf?

    ``grenze`` ist die Zahl der Nachrichten, die ein einzelner Leseaufruf
    hoechstens liefert (Deckel + 2 x Kontext). Gezaehlt werden nur Zahlen.
    """
    je = con.execute(
        "SELECT conversation_id, COUNT(*) FROM nachrichten GROUP BY conversation_id").fetchall()
    groessen = [n for _, n in je]
    if not groessen:
        return {"gespraeche": 0, "groesstes": 0, "median": 0, "ueber_grenze": 0,
                "nachrichten": 0, "grenze": grenze}
    return {
        "gespraeche": len(groessen),
        "groesstes": max(groessen),
        "median": statistics.median(groessen),
        "ueber_grenze": sum(1 for n in groessen if n > grenze),
        "nachrichten": sum(groessen),
        "grenze": grenze,
    }


def bildindex_zaehlen(pfad: Path) -> dict:
    """Bilder, mit Vektor, mit Beschreibung im Bildindex - nur Zahlen."""
    if not pfad.is_file():
        return {"fehlt": True}
    con = index_oeffnen(pfad)
    try:
        namen = tabellen(con)
        if "bilder" not in namen:
            return {"fehlt": False, "tabelle_fehlt": True, "tabellen": namen}
        spalten = [r[1] for r in con.execute("PRAGMA table_info(bilder)")]
        gesamt = con.execute("SELECT COUNT(*) FROM bilder").fetchone()[0]
        aus: dict = {"fehlt": False, "bilder": gesamt, "spalten": spalten}
        if "vektor" in spalten:
            aus["mit_vektor"] = con.execute(
                "SELECT COUNT(*) FROM bilder WHERE vektor IS NOT NULL AND LENGTH(vektor) > 0"
            ).fetchone()[0]
        if "beschreibung" in spalten:
            aus["mit_beschreibung"] = con.execute(
                "SELECT COUNT(*) FROM bilder WHERE COALESCE(TRIM(beschreibung), '') <> ''"
            ).fetchone()[0]
        if "meta" in namen:
            aus["meta"] = {k: v for k, v in con.execute("SELECT * FROM meta").fetchall()}
        return aus
    finally:
        con.close()


def beschreibungszeilen(ordner: Path, dateien=STANDARD_BESCHREIBUNGEN) -> tuple[int, list[str]]:
    """Zeilen in den lokalen Beschreibungsdateien (nur gezaehlt, nie gelesen)."""
    gesamt = 0
    fehlend: list[str] = []
    for name in dateien:
        pfad = Path(name)
        if not pfad.is_absolute():
            pfad = ordner / name
        if not pfad.is_file():
            fehlend.append(name)
            continue
        with pfad.open(encoding="utf-8") as fh:
            gesamt += sum(1 for zeile in fh if zeile.strip())
    return gesamt, fehlend


def _treffer(pfad: Path, muster: str) -> tuple[int, str] | None:
    """Erste Zahlengruppe eines Musters in einer Quelldatei - mit Datei:Zeile.

    Bewusst Textsuche statt Import: Der gemessene Wert steht im Code, und wenn er
    dort nicht mehr steht, meldet das Werkzeug das **ehrlich** statt einer Zahl,
    die einmal gestimmt hat.
    """
    if not pfad.is_file():
        return None
    for nummer, zeile in enumerate(pfad.read_text(encoding="utf-8").splitlines(), start=1):
        treffer = re.search(muster, zeile)
        if treffer:
            return int(treffer.group(1)), f"{pfad.name}:{nummer}"
    return None


def _alle_treffer(pfad: Path, muster: str) -> tuple[list[int], str] | None:
    """Alle Zahlengruppen eines Musters in einer Zeile (z. B. Voreinstellung, min, max)."""
    if not pfad.is_file():
        return None
    for nummer, zeile in enumerate(pfad.read_text(encoding="utf-8").splitlines(), start=1):
        treffer = re.search(muster, zeile)
        if treffer:
            return [int(g) for g in treffer.groups()], f"{pfad.name}:{nummer}"
    return None


def deckel_lesen() -> list[tuple[str, str, str]]:
    """Deckel im Antwortweg aus dem Code: (was, Wert, Datei:Zeile oder Grund).

    Alle Muster stammen aus dem geltenden Code; die Datei- und Zeilenangabe steht
    im Bericht, damit die Zahl nachpruefbar bleibt.
    """
    dienste = PROJEKT / "backend" / "app" / "services"
    zeilen: list[tuple[str, str, str]] = []

    standard = _treffer(dienste / "archiv_standard.py", r"^\s*k = top_k or (\d+)")
    zeilen.append((
        "Fundstellen im Chat (Standardweg, Voreinstellung)",
        str(standard[0]) if standard else "nicht gefunden",
        standard[1] if standard else "archiv_standard.py: Muster 'k = top_k or N' fehlt",
    ))

    werkzeug = _alle_treffer(
        dienste / "werkzeuge.py",
        r'_ganzzahl\(args\.get\("anzahl"\),\s*(\d+),\s*(\d+),\s*(\d+)\)')
    if werkzeug:
        werte, ort = werkzeug
        zeilen.append(("Fundstellen im Werkzeug archiv_suchen (Voreinstellung)",
                       str(werte[0]), ort))
        zeilen.append(("Fundstellen im Werkzeug archiv_suchen (Hoechstwert)",
                       str(werte[2]), ort))
    else:
        zeilen.append(("Fundstellen im Werkzeug archiv_suchen",
                       "nicht gefunden", "werkzeuge.py: Muster '_ganzzahl(args.get(\"anzahl\"), …)' fehlt"))

    kontext = _alle_treffer(
        PROJEKT / "backend" / "app" / "router" / "archiv_wissen.py",
        r"kontext: int = Query\(default=(\d+), ge=0, le=(\d+)")
    if kontext:
        werte, ort = kontext
        zeilen.append(("Nachlesen: Voreinstellung Kontextnachrichten", str(werte[0]), ort))
        zeilen.append(("Nachlesen: Hoechstwert Kontextnachrichten", str(werte[1]), ort))
    else:
        zeilen.append(("Nachlesen: Kontextgrenze", "nicht gefunden",
                       "archiv_wissen.py: Muster 'kontext: int = Query(default=N, ge=0, le=M)' fehlt"))

    kuerzung = _treffer(PROJEKT / "backend" / "app" / "services" / "llm_service.py",
                        r"^\s*if len\(text\) > (\d+):")
    zeilen.append((
        "Zeichenkuerzung je Fundstelle im Prompt",
        str(kuerzung[0]) if kuerzung else "nicht gefunden",
        kuerzung[1] if kuerzung else "llm_service.py: Muster 'if len(text) > N:' fehlt",
    ))

    # Die Pruef-Endpunkte erlauben mehr als der Antwortweg — das gehoert zur Zahl
    # dazu, sonst liest sich "5" wie eine Grenze des ganzen Systems.
    for name, datei in (("/api/archiv/suche (Hoechstwert)", "archiv.py"),
                        ("/api/archiv/wissen/frage (Hoechstwert)", "archiv_wissen.py")):
        grenze = _treffer(PROJEKT / "backend" / "app" / "router" / datei,
                          r"top_k: int = Query\(default=\d+, ge=1, le=(\d+)\)")
        zeilen.append((
            name,
            str(grenze[0]) if grenze else "nicht gefunden",
            grenze[1] if grenze else f"{datei}: Muster 'top_k: int = Query(default=N, ge=1, le=M)' fehlt",
        ))
    return zeilen


def bericht(archiv: Path, bildindex: Path, ordner: Path, dateien=STANDARD_BESCHREIBUNGEN):
    """Berichtszeilen - nur Zahlen, Quellennamen und Datei:Zeile, kein Inhalt."""
    deckel = deckel_lesen()
    kontext_max = 10
    lesegrenze = 1 + 2 * kontext_max  # eine Fundstelle + Kontext beidseitig
    for was, wert, ort in deckel:
        if was.startswith("Nachlesen: Hoechstwert"):
            try:
                kontext_max = int(wert)
                lesegrenze = 1 + 2 * kontext_max
            except ValueError:
                pass

    yield f"Wissensspeicher: Umfang der Suche (nur Zahlen) · Arbeitsbaum: {REPO.name}"
    yield ""

    yield "Suchindex (archiv_index.db, read-only)"
    bild: list[str] = []
    if not archiv.is_file():
        yield f"  Datei fehlt: {archiv}"
    else:
        con = index_oeffnen(archiv)
        try:
            quellen = quellen_zaehlen(con)
            gesamt = {k: sum(q[k] for q in quellen)
                      for k in ("gespraeche", "nachrichten", "chunks", "chunks_mit_vektor")}
            for q in quellen:
                yield (f"  {q['quelle']}: {q['gespraeche']} Gespraeche · "
                       f"{q['nachrichten']} Nachrichten · {q['chunks']} Chunks · "
                       f"{q['chunks_mit_vektor']} mit Vektor")
            yield (f"  Summe: {gesamt['gespraeche']} Gespraeche · {gesamt['nachrichten']} "
                   f"Nachrichten · {gesamt['chunks']} Chunks · "
                   f"{gesamt['chunks_mit_vektor']} mit Vektor")
            namen = [q["quelle"] for q in quellen]
            bild = [n for n in namen if any(w in n.lower() for w in BILD_QUELLEN)]
            yield (f"  Quellen mit Bilderbezug: {len(bild)}"
                   + (f" ({', '.join(bild)})" if bild else " — keine"))
            umfang = verlauf_umfang(con, lesegrenze)
            yield (f"  Gespraechsgroessen: groesstes {umfang['groesstes']} Nachrichten · "
                   f"Median {umfang['median']} · ueber {umfang['grenze']} Nachrichten: "
                   f"{umfang['ueber_grenze']} von {umfang['gespraeche']}")
        finally:
            con.close()
    yield ""

    yield "Bildindex (bild_index.db, read-only)"
    bildzahlen = bildindex_zaehlen(bildindex)
    if bildzahlen.get("fehlt"):
        yield f"  Datei fehlt: {bildindex}"
    elif bildzahlen.get("tabelle_fehlt"):
        yield f"  Tabelle 'bilder' fehlt (Tabellen: {', '.join(bildzahlen['tabellen'])})"
    else:
        teile = [f"  {bildzahlen['bilder']} Bilder"]
        if "mit_vektor" in bildzahlen:
            teile.append(f"{bildzahlen['mit_vektor']} mit Vektor")
        if "mit_beschreibung" in bildzahlen:
            teile.append(f"{bildzahlen['mit_beschreibung']} mit Beschreibung")
        yield " · ".join(teile)
        meta = bildzahlen.get("meta") or {}
        if meta:
            stand = meta.get("stand") or meta.get("gebaut_am") or "unbekannt"
            yield (f"  Stand: {stand} · "
                   f"Modell {meta.get('modell', 'unbekannt')}")
    zeilen, fehlend = beschreibungszeilen(ordner, dateien)
    yield f"  Beschreibungszeilen in den JSONL-Dateien: {zeilen}"
    if fehlend:
        yield f"  Datei fehlt: {', '.join(fehlend)}"
    yield (f"  Im Suchindex des Chats: {'keine Bilder-Quelle' if not bild else 'siehe oben'}"
           f" · im Bildindex: eigene Datei")
    yield ""

    yield "Deckel im Antwortweg (aus dem Code gelesen, Datei:Zeile)"
    for was, wert, ort in deckel:
        yield f"  {was}: {wert} ({ort})"
    return 0


def main(argv=None) -> int:
    zerleger = argparse.ArgumentParser(
        description="Umfang des Wissensspeichers messen (nur lesen, nur Zahlen, nichts schreiben).")
    zerleger.add_argument("--archiv", default=str(STANDARD_ARCHIV),
                          help="Pfad der archiv_index.db (Standard: Archivordner)")
    zerleger.add_argument("--bildindex", default=str(STANDARD_BILDINDEX),
                          help="Pfad der bild_index.db (Standard: ~/foto_sortierung)")
    zerleger.add_argument("--ordner", default=str(STANDARD_ORDNER),
                          help="Ordner der Beschreibungsdateien (Standard: ~/foto_sortierung)")
    zerleger.add_argument("--beschreibungen", nargs="*", default=None,
                          help="Statt der Voreinstellung: einzelne Beschreibungsdateien")
    args = zerleger.parse_args(argv)

    dateien = (tuple(args.beschreibungen) if args.beschreibungen is not None
               else STANDARD_BESCHREIBUNGEN)
    archiv = Path(args.archiv)
    if not archiv.is_file():
        print(f"Hinweis: Archivindex nicht gefunden ({archiv}) — es wird ohne ihn gemessen.")

    for zeile in bericht(archiv, Path(args.bildindex), Path(args.ordner), dateien):
        print(zeile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
