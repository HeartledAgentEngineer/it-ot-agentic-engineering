"""Pflegt einen BESTEHENDEN Archiv-Index inkrementell und idempotent nach.

Warum es dieses Skript gibt
===========================

``scripts/archiv_index_bauen.py`` kennt genau zwei Wege: einen kompletten
Neubau (acht Minuten, ~447 MB, **jede** Einbettung erneut bezahlt) oder das
Nachtragen fehlender Quelldateien (``--nur-quelldatei``). Sobald das
Schwesterprojekt neue Chats nach ``db/memory.db`` importiert, fehlt ein
**inkrementeller** Weg: nur das Neue anhaengen, nichts Altes anfassen.

Dieses Skript schliesst genau diese Luecke. Es

  1. liest die Bestands-Kennungen aus dem **Index selbst** (kein id-Ordinal!),
  2. oeffnet die Quelle ``memory.db`` **nur lesend** und geht sie in
     Quellreihenfolge durch,
  3. haengt **nur die neuen** Nachrichten/Chunks hinten an, vergibt
     ``id = max(bestehende id) + 1`` aufsteigend,
  4. haengt neue Chunks in den Volltextindex (``chunks_fts``),
  5. rechnet **nur fuer neue Chunks** Vektoren — und nur mit
     ``--mit-vektoren``,
  6. zieht ``gespraeche`` nur fuer **beruehrte** Gespraeche nach,
  7. **ergaenzt** ``meta`` (``nachpflege_*``) und entfernt nie einen Eintrag.

Grenzen (hart)
==============

* **Nur anhaengen.** Kein Loeschen, kein Verwerfen von Tabellen, kein
  Neu-Schreiben der Datei, kein Tabellen-Neuaufbau. Erlaubt sind nur
  ``INSERT``/``UPDATE`` und das Anlegen fehlender Tabellen (``CREATE TABLE IF
  NOT EXISTS``) fuer den Fall eines aelteren Schemastands.
* **Standard ist Trockenlauf** (``--trocken``): Quelle und Index werden nur
  lesend geoeffnet, geschrieben wird **nichts** (Index-``sha256`` und ``mtime``
  bleiben gleich). Schreiben nur mit ``--schreiben``.
* **Repo-Ziel wird verweigert:** liegt ``--index`` im Projektordner
  (``personal_ai_agent``), endet der Lauf mit Exit **2** und deutscher Meldung
  — es wird nichts geschrieben.
* **Kein Netz ausser der Einbettung**, kein Zugriff auf Bild-/Fotodaten, kein
  Cloud-Zugriff, kein Loeschen. Der Schluessel wird nie ausgegeben (nur Laenge).

Erkennung „neu" per Inhaltsschluessel
=====================================

Nicht ueber ``id``/Ordinal (das kann sich beim Neu-Import verschieben),
sondern ueber einen aus dem Inhalt gerechneten Schluessel:

  * Nachricht: ``sha1("conv\\x1ftimestamp\\x1frole\\x1ftext")[:16]``
  * Chunk:     ``sha1("conv\\x1fteil\\x1fbeginn\\x1fende\\x1ftext")[:16]``

Der Index traegt alle Felder, die fuer den Schluessel noetig sind — die
Bestands-Schluessel werden also **aus dem Index selbst** gerechnet. Kein
Schema-Umbau, keine Zusatztabelle.

Aufruf
======

    cd backend
    .venv/Scripts/python -m scripts.archiv_nachpflege \\
        --quelle-db <memory.db> --index <archiv_index.db> \\
        [--schreiben] [--mit-vektoren] [--stapel 100] [--stand <ISO>]

Ohne ``--schreiben`` passiert nichts (nur Zahlen). Ohne ``--mit-vektoren``
bleiben neue Chunks ehrlich ``hat_vektor = 0`` und werden im Bericht als
„ohne Vektor" gezaehlt.

Kosten
======

``openai/text-embedding-3-small`` kostet rund 0,02 $ je 1 Mio Token. Fuer eine
Handvoll neuer Chunks sind das Bruchteile eines Cents. Die tatsaechlich
gezaehlte Zahl aus der API-Antwort steht im Bericht.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

# Das Skript liegt in backend/scripts/ — der Importpfad auf backend/ zeigen,
# damit `app.services.archiv_suche` und `scripts.archiv_index_bauen` gefunden
# werden.
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.services.archiv_suche import SCHEMA_SQL  # noqa: E402
from scripts.archiv_index_bauen import (  # noqa: E402
    PREIS_JE_MIO_TOKEN,
    STANDARD_BASIS,
    STANDARD_MODELL,
    ZEICHEN_JE_TOKEN,
    Einbetter,
    EinbetterOpenRouter,
    _schluessel_holen,
    _vektor_blob,
)

# Ordnername des Projekts — ein Index darunter gilt als „im Repo" und wird
# verweigert (er koennte sonst versehentlich mitcommittet werden).
PROJEKT_ORDNER = "personal_ai_agent"

# Der Projektwurzelpfad: BACKEND ist .../personal_ai_agent/backend.
PROJEKT_WURZEL = os.path.dirname(BACKEND)

# Trennzeichen zwischen den Schluessel-Feldern. \x1f (Unit Separator) kommt in
# normalem Text nicht vor, kann also keinen Schluessel verwechseln.
TRENNER = "\x1f"


# ── Reine Funktionen: Inhaltsschluessel ────────────────────────────────────
def _schluessel(teile: Sequence[Any]) -> str:
    """sha1 ueber die mit ``\\x1f`` verbundenen Felder, auf 16 Hex-Zeichen."""
    roh = TRENNER.join("" if t is None else str(t) for t in teile)
    return hashlib.sha1(roh.encode("utf-8")).hexdigest()[:16]


def schluessel_nachricht(
    conversation_id: Any, timestamp: Any, role: Any, text: Any
) -> str:
    """Inhaltsschluessel einer Nachricht (kein id-Ordinal)."""
    return _schluessel([conversation_id, timestamp, role, text])


def schluessel_chunk(
    conversation_id: Any, teil: Any, beginn: Any, ende: Any, text: Any
) -> str:
    """Inhaltsschluessel einer Fundstelle (kein id-Ordinal)."""
    return _schluessel([conversation_id, teil, beginn, ende, text])


# ── Zielsicherheit: kein Index im Projekt ──────────────────────────────────
def ist_im_repo(pfad: str) -> bool:
    """Liegt ``pfad`` innerhalb des Projektordners ``personal_ai_agent``?

    Der Index enthaelt die vollstaendigen Gespraeche und ist ~450 MB gross; im
    Repo koennte er versehentlich mitcommittet werden. Deshalb ist ein
    Repo-Ziel ein harter Fehler (Exit 2), kein Hinweis.
    """
    ziel = os.path.abspath(pfad)
    wurzel = os.path.abspath(PROJEKT_WURZEL)
    try:
        gemeinsam = os.path.commonpath([ziel, wurzel])
    except ValueError:
        return False
    if os.path.normcase(gemeinsam) != os.path.normcase(wurzel):
        return False
    # Zusaetzlich der Ordnername, falls das Projekt einmal verschoben wird.
    return PROJEKT_ORDNER in os.path.normcase(ziel)


# ── Bestand aus dem Index lesen ────────────────────────────────────────────
def _zeile_fehlt(*werte: Any) -> bool:
    """True, wenn eine strukturelle Pflichtangabe leer/None ist.

    Geprueft wird nur, was einen stabilen Inhaltsschluessel unmoeglich macht
    (leere ``conversation_id`` oder leere ``role``). Ein **leerer Text** ist
    dagegen zulaessig und kommt im echten Bestand vor (68 leere Nachrichten aus
    dem Claude-Export) — er traegt ueber Zeitstempel und Rolle trotzdem einen
    eindeutigen Schluessel und darf nicht als Fehler zaehlen.
    """
    return any(w is None or (isinstance(w, str) and not w.strip()) for w in werte)


def bestand_lesen(con: sqlite3.Connection) -> Dict[str, Any]:
    """Alle Bestands-Schluessel, Hoechstnummern und Quelldateien aus dem Index.

    Rein lesend. Die Schluessel werden aus den im Index gespeicherten Feldern
    gerechnet — es gibt keine Zusatztabelle und keinen Schema-Umbau.
    """
    nachrichten_schluessel: Set[str] = set()
    for cid, ts, role, text in con.execute(
        "SELECT conversation_id, timestamp, role, text FROM nachrichten"
    ):
        nachrichten_schluessel.add(schluessel_nachricht(cid, ts, role, text))

    chunk_schluessel: Set[str] = set()
    for cid, teil, beginn, ende, text in con.execute(
        "SELECT conversation_id, teil, beginn, ende, text FROM chunks"
    ):
        chunk_schluessel.add(schluessel_chunk(cid, teil, beginn, ende, text))

    max_nachricht = con.execute(
        "SELECT coalesce(max(id), -1) FROM nachrichten"
    ).fetchone()[0]
    max_chunk = con.execute("SELECT coalesce(max(id), 0) FROM chunks").fetchone()[0]

    # Quelldatei je Gespraech — damit neue Zeilen den Zeiger uebernehmen
    # koennen, wenn das Gespraech schon bekannt ist.
    quelldatei: Dict[str, Optional[str]] = {}
    for cid, pfad in con.execute(
        "SELECT conversation_id, max(quelldatei) FROM chunks GROUP BY conversation_id"
    ):
        if pfad:
            quelldatei[cid] = pfad
    for cid, pfad in con.execute(
        "SELECT conversation_id, quelldatei FROM gespraeche"
    ):
        if pfad and not quelldatei.get(cid):
            quelldatei[cid] = pfad

    return {
        "nachrichten_schluessel": nachrichten_schluessel,
        "chunk_schluessel": chunk_schluessel,
        "max_nachricht": int(max_nachricht),
        "max_chunk": int(max_chunk),
        "quelldatei": quelldatei,
    }


# ── Quelle nur lesend durchgehen, Neue einsammeln ──────────────────────────
def neue_nachrichten_sammeln(
    quelle: sqlite3.Connection,
    bestand: Dict[str, Any],
    fehler: List[str],
) -> List[Dict[str, Any]]:
    """Neue Nachrichten in Quellreihenfolge (``ORDER BY id``) einsammeln."""
    neu: List[Dict[str, Any]] = []
    for zeile in quelle.execute(
        "SELECT id, conversation_id, source, timestamp, role, text, title, project "
        "FROM messages ORDER BY id"
    ):
        cid, source, ts, role, text = (
            zeile["conversation_id"], zeile["source"], zeile["timestamp"],
            zeile["role"], zeile["text"],
        )
        if _zeile_fehlt(cid, role):
            fehler.append(f"Nachricht id={zeile['id']}: Pflichtfeld leer — uebersprungen")
            continue
        schluessel = schluessel_nachricht(cid, ts, role, text)
        if schluessel in bestand["nachrichten_schluessel"]:
            continue
        neu.append({
            "conversation_id": cid, "source": source or "", "timestamp": ts,
            "role": role, "text": text,
            "title": zeile["title"], "project": zeile["project"],
        })
    return neu


def neue_chunks_sammeln(
    quelle: sqlite3.Connection,
    bestand: Dict[str, Any],
    fehler: List[str],
) -> List[Dict[str, Any]]:
    """Neue Chunks in Quellreihenfolge (``ORDER BY id``) einsammeln."""
    neu: List[Dict[str, Any]] = []
    for zeile in quelle.execute(
        "SELECT id, conversation_id, source, text, nachricht_ids, beginn, ende, "
        "title, project, teil FROM chunks ORDER BY id"
    ):
        cid, text = zeile["conversation_id"], zeile["text"]
        if _zeile_fehlt(cid):
            fehler.append(f"Chunk id={zeile['id']}: Pflichtfeld leer — uebersprungen")
            continue
        schluessel = schluessel_chunk(
            cid, zeile["teil"], zeile["beginn"], zeile["ende"], text
        )
        if schluessel in bestand["chunk_schluessel"]:
            continue
        neu.append({
            "conversation_id": cid, "source": zeile["source"] or "",
            "text": text, "nachricht_ids": zeile["nachricht_ids"],
            "beginn": zeile["beginn"], "ende": zeile["ende"],
            "title": zeile["title"], "project": zeile["project"],
            "teil": zeile["teil"],
        })
    return neu


# ── Kern ───────────────────────────────────────────────────────────────────
def nachpflegen(
    quelle_db: str,
    index_pfad: str,
    schreiben: bool = False,
    einbetter: Optional[Einbetter] = None,
    stapel: int = 100,
    stand: Optional[str] = None,
    ausgabe_strom=None,
) -> Dict[str, Any]:
    """Einen bestehenden Index inkrementell nachpflegen.

    Ohne ``schreiben=True`` passiert nichts ausser Lesen (Trockenlauf).
    ``einbetter`` ist injizierbar (Tests: Attrappe, kein Netz). Ohne
    ``einbetter`` bleiben neue Chunks ``hat_vektor = 0``.
    """
    strom = ausgabe_strom or sys.stdout
    start = time.time()
    fehler: List[str] = []

    zaehler: Dict[str, Any] = {
        "neu_nachrichten": 0,
        "neu_chunks": 0,
        "uebersprungen_nachrichten": 0,
        "uebersprungen_chunks": 0,
        "vektoren_gerechnet": 0,
        "ohne_vektor": 0,
        "tokens": 0,
        "kosten_usd": 0.0,
        "gespraeche_beruehrt": 0,
        "fehler": 0,
        "dauer_s": 0.0,
        "index_mb": 0.0,
    }

    if not os.path.isfile(quelle_db):
        raise FileNotFoundError(f"Quell-Datenbank nicht gefunden: {quelle_db}")
    if not os.path.isfile(index_pfad):
        raise FileNotFoundError(f"Index nicht gefunden: {index_pfad}")
    if ist_im_repo(index_pfad):
        raise ValueError(
            f"Index-Ziel liegt im Projektordner ({PROJEKT_ORDNER}) und wird "
            "verweigert. Der Index gehoert neben db/memory.db ausserhalb des "
            "Repos."
        )

    # Index lesend oeffnen (Trockenlauf und Schreiblauf lesen zuerst gleich).
    index_ro = sqlite3.connect(f"file:{index_pfad}?mode=ro", uri=True)
    index_ro.row_factory = sqlite3.Row
    try:
        bestand = bestand_lesen(index_ro)
    finally:
        index_ro.close()

    quelle = sqlite3.connect(f"file:{quelle_db}?mode=ro", uri=True)
    quelle.row_factory = sqlite3.Row
    try:
        neue_na = neue_nachrichten_sammeln(quelle, bestand, fehler)
        neue_ch = neue_chunks_sammeln(quelle, bestand, fehler)

        gesamt_na = quelle.execute("SELECT count(*) FROM messages").fetchone()[0]
        gesamt_ch = quelle.execute("SELECT count(*) FROM chunks").fetchone()[0]
    finally:
        quelle.close()

    zaehler["neu_nachrichten"] = len(neue_na)
    zaehler["neu_chunks"] = len(neue_ch)
    zaehler["uebersprungen_nachrichten"] = max(0, int(gesamt_na) - len(neue_na))
    zaehler["uebersprungen_chunks"] = max(0, int(gesamt_ch) - len(neue_ch))
    zaehler["fehler"] = len(fehler)

    beruehrte: Set[str] = {n["conversation_id"] for n in neue_na}
    beruehrte |= {c["conversation_id"] for c in neue_ch}
    zaehler["gespraeche_beruehrt"] = len(beruehrte)

    etwas_zu_tun = bool(neue_na or neue_ch)

    if not (schreiben and etwas_zu_tun):
        # Trockenlauf oder nichts Neues: kein Schreibzugriff, Datei unberuehrt.
        zaehler["ohne_vektor"] = len(neue_ch)
        zaehler["dauer_s"] = round(time.time() - start, 1)
        zaehler["index_mb"] = round(os.path.getsize(index_pfad) / 1024 / 1024, 1)
        if fehler:
            for f in fehler:
                print(f"  ! {f}", file=strom, flush=True)
        return zaehler

    # ── Schreibpfad: nur anhaengen ─────────────────────────────────────────
    ziel = sqlite3.connect(index_pfad)
    ziel.row_factory = sqlite3.Row
    try:
        ziel.execute("PRAGMA journal_mode = MEMORY")

        # 1) Neue Nachrichten anhaengen ------------------------------------
        naechste = bestand["max_nachricht"] + 1
        ziel.executemany(
            "INSERT INTO nachrichten (id, conversation_id, source, timestamp, role, "
            "text, title, project) VALUES (?,?,?,?,?,?,?,?)",
            [
                (naechste + i, n["conversation_id"], n["source"], n["timestamp"],
                 n["role"], n["text"], n["title"], n["project"])
                for i, n in enumerate(neue_na)
            ],
        )

        # 2) Neue Chunks anhaengen (quelldatei aus dem Bestand, sonst NULL) -
        naechste_chunk = bestand["max_chunk"] + 1
        chunk_ids: List[int] = []
        quelldatei_karte = bestand["quelldatei"]
        for i, c in enumerate(neue_ch):
            cid = naechste_chunk + i
            chunk_ids.append(cid)
            ziel.execute(
                "INSERT INTO chunks (id, conversation_id, source, text, "
                "nachricht_ids, beginn, ende, title, project, teil, quelldatei, "
                "hat_vektor) VALUES (?,?,?,?,?,?,?,?,?,?,?,0)",
                (
                    cid, c["conversation_id"], c["source"], c["text"],
                    c["nachricht_ids"], c["beginn"], c["ende"], c["title"],
                    c["project"], c["teil"],
                    quelldatei_karte.get(c["conversation_id"]),
                ),
            )

        # 3) Neue Chunks in den Volltextindex ---------------------------------
        if chunk_ids:
            ziel.executemany(
                "INSERT INTO chunks_fts(rowid, text) VALUES (?, ?)",
                [(cid, c["text"]) for cid, c in zip(chunk_ids, neue_ch)],
            )
            ziel.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('optimize')")

        # 4) Vektoren nur fuer neue Chunks ------------------------------------
        tokens_gezaehlt = 0
        if einbetter is not None and neue_ch:
            for anfang in range(0, len(neue_ch), max(1, stapel)):
                block = neue_ch[anfang:anfang + max(1, stapel)]
                texte = [c["text"] for c in block]
                vektoren, token = einbetter(texte)
                tokens_gezaehlt += int(token or 0)
                ziel.executemany(
                    "INSERT INTO vektoren (chunk_id, dimension, modell, vektor) "
                    "VALUES (?,?,?,?)",
                    [
                        (chunk_ids[anfang + k], len(v),
                         getattr(einbetter, "modell", STANDARD_MODELL),
                         _vektor_blob(v))
                        for k, v in enumerate(vektoren)
                    ],
                )
            ziel.executemany(
                "UPDATE chunks SET hat_vektor = 1 WHERE id = ?",
                [(cid,) for cid in chunk_ids],
            )
            zaehler["vektoren_gerechnet"] = len(neue_ch)
            zaehler["ohne_vektor"] = 0
        else:
            zaehler["ohne_vektor"] = len(neue_ch)

        if not tokens_gezaehlt:
            tokens_gezaehlt = int(
                sum(len(c["text"] or "") for c in neue_ch) / ZEICHEN_JE_TOKEN
            )
        zaehler["tokens"] = tokens_gezaehlt
        zaehler["kosten_usd"] = round(
            tokens_gezaehlt / 1_000_000 * PREIS_JE_MIO_TOKEN, 8
        )

        # 5) gespraeche nur fuer beruehrte Gespraeche nachziehen --------------
        for cid in sorted(beruehrte):
            nach = ziel.execute(
                "SELECT count(*) FROM nachrichten WHERE conversation_id = ?", (cid,)
            ).fetchone()[0]
            spur = ziel.execute(
                "SELECT source, title, quelldatei, min(beginn) AS von, "
                "max(ende) AS bis, count(*) AS anzahl FROM chunks "
                "WHERE conversation_id = ?",
                (cid,),
            ).fetchone()
            if spur and spur["anzahl"]:
                source = spur["source"] or ""
                title = spur["title"]
                quelldatei = spur["quelldatei"]
                von, bis = spur["von"], spur["bis"]
                anzahl_chunks = int(spur["anzahl"])
            else:
                zeile = ziel.execute(
                    "SELECT source, title, min(timestamp) AS von, "
                    "max(timestamp) AS bis FROM nachrichten WHERE conversation_id = ?",
                    (cid,),
                ).fetchone()
                source = (zeile["source"] if zeile else "") or ""
                title = zeile["title"] if zeile else None
                quelldatei = quelldatei_karte.get(cid)
                von = zeile["von"] if zeile else None
                bis = zeile["bis"] if zeile else None
                anzahl_chunks = 0
            ziel.execute(
                "INSERT OR REPLACE INTO gespraeche (conversation_id, source, title, "
                "quelldatei, von, bis, anzahl_nachrichten, anzahl_chunks) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (cid, source, title, quelldatei, von, bis, int(nach), anzahl_chunks),
            )

        # 6) meta ergaenzen, nie entfernen ------------------------------------
        jetzt = stand or datetime.now(timezone.utc).isoformat()
        lauf = (
            f"neu {len(neue_na)} Nachrichten, {len(neue_ch)} Chunks, "
            f"{zaehler['vektoren_gerechnet']} Vektoren, "
            f"{zaehler['uebersprungen_nachrichten']} uebersprungen"
        )
        meta = {
            "nachpflege_zuletzt": jetzt,
            "nachpflege_lauf": lauf,
            "nachpflege_neu_nachrichten": str(len(neue_na)),
            "nachpflege_neu_chunks": str(len(neue_ch)),
            "nachpflege_neu_vektoren": str(zaehler["vektoren_gerechnet"]),
        }
        ziel.executemany(
            "INSERT OR REPLACE INTO meta (schluessel, wert) VALUES (?,?)",
            list(meta.items()),
        )

        ziel.commit()
    finally:
        ziel.close()

    zaehler["dauer_s"] = round(time.time() - start, 1)
    zaehler["index_mb"] = round(os.path.getsize(index_pfad) / 1024 / 1024, 1)
    if fehler:
        for f in fehler:
            print(f"  ! {f}", file=strom, flush=True)
    return zaehler


def bericht(zaehler: Dict[str, Any]) -> str:
    """Kurzer Abschlussbericht — Zahlen, keine Inhalte."""
    return (
        "\n=== Archiv-Index nachgepflegt ===\n"
        f"  neu (Nachrichten)     : {zaehler['neu_nachrichten']}\n"
        f"  neu (Chunks)          : {zaehler['neu_chunks']}\n"
        f"  uebersprungen (Nachr.): {zaehler['uebersprungen_nachrichten']}\n"
        f"  uebersprungen (Chunks): {zaehler['uebersprungen_chunks']}\n"
        f"  Vektoren gerechnet    : {zaehler['vektoren_gerechnet']}\n"
        f"  ohne Vektor           : {zaehler['ohne_vektor']}\n"
        f"  Token                 : {zaehler['tokens']}\n"
        f"  Kosten                : {zaehler['kosten_usd']} $ "
        f"({PREIS_JE_MIO_TOKEN} $/1M Token)\n"
        f"  Gespraeche beruehrt   : {zaehler['gespraeche_beruehrt']}\n"
        f"  Fehler                : {zaehler['fehler']}\n"
        f"  Dauer                 : {zaehler['dauer_s']} s\n"
        f"  Indexgroesse          : {zaehler['index_mb']} MB\n"
    )


def _standard_quelle() -> Optional[str]:
    """Die Quell-Datenbank neben dem Projekt suchen (bequemer Aufruf)."""
    kandidaten = [
        os.path.join(PROJEKT_WURZEL, "..", "..", "..", "Chats von GPT, GEMINI, Claude", "db", "memory.db"),
        os.path.join(PROJEKT_WURZEL, "..", "..", "Chats von GPT, GEMINI, Claude", "db", "memory.db"),
    ]
    for k in kandidaten:
        k = os.path.abspath(k)
        if os.path.isfile(k):
            return k
    return None


def _standard_index(quelle_db: Optional[str]) -> Optional[str]:
    """Der Index neben der Quelle (im Archivordner, nicht im Repo)."""
    if quelle_db:
        return os.path.join(os.path.dirname(quelle_db), "archiv_index.db")
    return None


def main(argv: Optional[Sequence[str]] = None) -> int:
    wahl = argparse.ArgumentParser(
        description="Pflegt einen bestehenden Archiv-Index inkrementell nach "
                    "(nur anhaengen, idempotent)."
    )
    wahl.add_argument("--quelle-db", default=None, help="Quell-Datenbank (memory.db).")
    wahl.add_argument("--index", default=None, help="Bestehender Archiv-Index (archiv_index.db).")
    wahl.add_argument(
        "--schreiben", action="store_true",
        help="Wirklich schreiben (Standard: Trockenlauf — nichts wird geschrieben).",
    )
    wahl.add_argument(
        "--mit-vektoren", action="store_true",
        help="Vektoren fuer neue Chunks ueber OpenRouter rechnen (kostet Bruchteile eines Cents).",
    )
    wahl.add_argument("--stapel", type=int, default=100, help="Chunks je Einbettungs-Aufruf.")
    wahl.add_argument(
        "--stand", default=None,
        help="Zeitstempel einfrieren (ISO) — fuer zwei byte-gleiche Laeufe.",
    )
    wahl.add_argument("--modell", default=STANDARD_MODELL)
    wahl.add_argument("--basis-url", default=STANDARD_BASIS)
    args = wahl.parse_args(argv)

    quelle_db = args.quelle_db or _standard_quelle()
    index_pfad = args.index or _standard_index(quelle_db)

    if not quelle_db or not os.path.isfile(quelle_db):
        print("Quell-Datenbank nicht gefunden. Bitte --quelle-db angeben.")
        return 2
    if not index_pfad or not os.path.isfile(index_pfad):
        print("Index nicht gefunden. Bitte --index angeben.")
        return 2
    if ist_im_repo(index_pfad):
        print(
            f"Index-Ziel liegt im Projektordner ({PROJEKT_ORDNER}) und wird "
            "verweigert — er gehoert neben db/memory.db ausserhalb des Repos. "
            "Nichts geschrieben."
        )
        return 2

    einbetter = None
    if args.mit_vektoren and args.schreiben:
        schluessel = _schluessel_holen()
        if not schluessel:
            print(
                "Kein OPENROUTER_API_KEY gefunden. Ohne Schluessel bleiben neue "
                "Chunks ohne Vektor — dafuer --mit-vektoren weglassen."
            )
            return 3
        einbetter = EinbetterOpenRouter(
            schluessel, modell=args.modell, basis_url=args.basis_url, stapel=args.stapel
        )
        print(f"Modell: {args.modell} | Schluessel-Laenge: {len(schluessel)}")

    print(f"Quelle : {quelle_db}")
    print(f"Index  : {index_pfad}")
    print(f"Modus  : {'SCHREIBEN' if args.schreiben else 'Trockenlauf (nichts wird geschrieben)'}")

    zaehler = nachpflegen(
        quelle_db=quelle_db,
        index_pfad=index_pfad,
        schreiben=args.schreiben,
        einbetter=einbetter,
        stapel=args.stapel,
        stand=args.stand,
    )
    print(bericht(zaehler))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
