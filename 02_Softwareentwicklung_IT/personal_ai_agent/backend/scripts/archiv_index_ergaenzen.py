#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ergaenzt Archiv-Index und Einbettungen INKREMENTELL um neue Zeilen.

Warum es dieses Skript gibt
===========================

``scripts/archiv_index_bauen.py`` baut den Index aus ``db/memory.db`` — immer
vollstaendig, mit Einbettung des ganzen Bestands. Das ist richtig, wenn der
Index neu entsteht, aber falsch, wenn nur ein Schwung Nachrichten dazukommt:
Der Text wuerde erneut kopiert und **jeder** Vektor erneut bezahlt.

Dieses Skript haengt stattdessen an:

  1. ``db/memory.db``  — neue Nachrichten und Chunks (Textschicht, kostenlos),
     ueber die Werkzeuge des Archivs (``src.normalform``, ``src.filter``,
     ``src.chunker``, ``src.speicher``) — dieselbe Zerlegung wie beim Bau.
  2. ``db/archiv_index.db`` — neue Nachrichten, neue Chunks, FTS-Zeilen und
     **nur** die fehlenden Vektoren (OpenRouter, ``openai/text-embedding-3-small``).

Bestehende Zeilen werden nicht angefasst: keine Nachricht, kein Chunk, kein
Vektor wird geaendert oder geloescht, es kommen nur Zeilen dazu.

Kosten
======

Vor dem Einbetten wird geschaetzt und gegen ``--budget`` (Standard 1,00 USD)
geprueft; wird die Grenze **vor** dem Lauf ueberschritten, bricht das Skript
ohne Schreibzugriff ab. Auch waehrend des Laufs wird nach jedem Buendel
nachgerechnet — gerechnete Buendel bleiben erhalten, der Rest wird nicht mehr
angefasst (derselbe Aufruf macht spaeter dort weiter).

Aufruf
======

    cd backend
    .venv/Scripts/python -m scripts.archiv_index_ergaenzen --trocken
    .venv/Scripts/python -m scripts.archiv_index_ergaenzen --schreiben --mit-vektoren

Ohne ``--schreiben`` passiert nichts (nur Zahlen). Ohne ``--mit-vektoren``
werden Text und FTS erweitert, aber nichts eingebettet.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from scripts.archiv_index_bauen import (  # noqa: E402
    PREIS_JE_MIO_TOKEN,
    STANDARD_BASIS,
    STANDARD_MODELL,
    ZEICHEN_JE_TOKEN,
    Einbetter,
    EinbetterOpenRouter,
    QuelldateiFinder,
    _schluessel_holen,
    _standard_archiv,
    _vektor_blob,
)

MAX_FEHLVERSUCHE = 5


# ── Werkzeuge des Archivs laden ─────────────────────────────────────────────

def lade_archiv_module(archiv: str) -> Dict[str, Any]:
    """Die vorhandenen Archive-Werkzeuge importieren (nichts neu erfinden).

    ``src.filter``, ``src.chunker``, ``src.speicher`` und ``src.normalform``
    sind dieselben Bausteine, mit denen ``db/memory.db`` gebaut wurde. Nur so
    entsteht dieselbe Zerlegung — ein eigener Chunker wuerde andere Chunks
    erzeugen und den Bestand spalten.
    """
    if archiv not in sys.path:
        sys.path.insert(0, archiv)
    module = {
        "normalform": importlib.import_module("src.normalform"),
        "filter": importlib.import_module("src.filter"),
        "chunker": importlib.import_module("src.chunker"),
        "speicher": importlib.import_module("src.speicher"),
    }
    return module


# ── 1) Textschicht: memory.db erweitern ─────────────────────────────────────

def neue_nummerierte(quelle: str, ab_nummer: int, normalform) -> List[Tuple[int, Any]]:
    """Die Zeilen ab ``ab_nummer`` (Ordinal = Zeilennummer in der JSONL).

    ``normalized/messages.jsonl`` waechst nur am Ende; alles ab der bisherigen
    Anzahl ist neu. Das Ordinal ist zugleich die ``id`` in ``messages``.
    """
    return [(nr, n) for nr, n in enumerate(normalform.lies_jsonl(quelle)) if nr >= ab_nummer]


def memory_db_erweitern(
    memory_db: str,
    quelle: str,
    module: Dict[str, Any],
    schreiben: bool = True,
) -> Dict[str, Any]:
    """Neue Nachrichten und Chunks in ``memory.db`` ablegen (kein Vektor)."""
    speicher_mod = module["speicher"]
    zaehler: Dict[str, Any] = {}

    speicher = speicher_mod.Speicher(memory_db)
    try:
        vorher_nachrichten = speicher.anzahl("messages")
        vorher_chunks = speicher.anzahl("chunks")
        zaehler["nachrichten_vorher"] = vorher_nachrichten
        zaehler["chunks_vorher"] = vorher_chunks

        neue = neue_nummerierte(quelle, vorher_nachrichten, module["normalform"])
        zaehler["neue_nachrichten"] = len(neue)
        if not neue:
            zaehler["neue_chunks"] = 0
            zaehler["chunks_nachher"] = vorher_chunks
            zaehler["nachrichten_nachher"] = vorher_nachrichten
            return zaehler

        if schreiben:
            speicher.schreibe_nachrichten(neue)

        behalten, bericht = module["filter"].filtere_nummeriert(
            neue, module["filter"].LEICHT
        )
        zaehler["behalten"] = bericht.get("behalten", 0)
        for k in sorted(k for k in bericht if k.startswith("verworfen_")):
            zaehler[k] = bericht[k]

        # Chunk-Dubletten ausschliessen: gleicher Text -> gleicher Chunk.
        # Das macht den Lauf wiederholbar (zweiter Aufruf haengt nichts an).
        bekannt = {
            speicher_mod._fingerabdruck(z["text"])
            for z in speicher.db.execute("SELECT text FROM chunks")
        }
        chunks = []
        for c in module["chunker"].chunke(behalten):
            if speicher_mod._fingerabdruck(c.text) in bekannt:
                zaehler["chunk_dubletten"] = zaehler.get("chunk_dubletten", 0) + 1
                continue
            bekannt.add(speicher_mod._fingerabdruck(c.text))
            chunks.append(c)

        zaehler["neue_chunks"] = len(chunks)
        zaehler["neue_chunk_zeichen"] = sum(len(c.text) for c in chunks)
        if schreiben and chunks:
            speicher.schreibe_chunks(chunks)
            speicher.baue_volltextindex()

        zaehler["nachrichten_nachher"] = speicher.anzahl("messages")
        zaehler["chunks_nachher"] = speicher.anzahl("chunks")
        zaehler["ohne_vektor"] = speicher.anzahl("chunks") - speicher.anzahl_mit_vektor()
    finally:
        speicher.schliesse()
    return zaehler


# ── 2) Index erweitern (Text, FTS, Vektoren) ────────────────────────────────

def _zaehle(con: sqlite3.Connection, tabelle: str, bedingung: str = "") -> int:
    return con.execute(f"SELECT count(*) FROM {tabelle} {bedingung}").fetchone()[0]


def _gespraeche_auffrischen(con: sqlite3.Connection, kennungen: Sequence[str]) -> int:
    """Kennzahlen der betroffenen Gespraeche neu rechnen (nur diese)."""
    for kid in kennungen:
        zeile = con.execute(
            "SELECT min(source) AS source, max(title) AS title, max(quelldatei) AS quelldatei, "
            "       (SELECT min(timestamp) FROM nachrichten WHERE conversation_id = ?) AS von, "
            "       (SELECT max(timestamp) FROM nachrichten WHERE conversation_id = ?) AS bis, "
            "       (SELECT count(*) FROM nachrichten WHERE conversation_id = ?) AS n, "
            "       count(*) AS c "
            "FROM chunks WHERE conversation_id = ?",
            (kid, kid, kid, kid),
        ).fetchone()
        if zeile is None or not zeile["c"]:
            continue
        con.execute(
            "INSERT INTO gespraeche (conversation_id, source, title, quelldatei, von, bis,"
            " anzahl_nachrichten, anzahl_chunks) VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(conversation_id) DO UPDATE SET "
            " source=excluded.source, title=excluded.title, quelldatei=excluded.quelldatei,"
            " von=excluded.von, bis=excluded.bis,"
            " anzahl_nachrichten=excluded.anzahl_nachrichten, anzahl_chunks=excluded.anzahl_chunks",
            (kid, zeile["source"], zeile["title"], zeile["quelldatei"], zeile["von"],
             zeile["bis"], zeile["n"], zeile["c"]),
        )
    return len(kennungen)


def _meta_setzen(con: sqlite3.Connection, werte: Dict[str, str]) -> None:
    con.executemany(
        "INSERT OR REPLACE INTO meta (schluessel, wert) VALUES (?,?)", list(werte.items())
    )


def _meta_lesen(con: sqlite3.Connection, schluessel: str, vorgabe: str = "") -> str:
    zeile = con.execute(
        "SELECT wert FROM meta WHERE schluessel = ?", (schluessel,)
    ).fetchone()
    return zeile[0] if zeile else vorgabe


def index_erweitern(
    index_pfad: str,
    memory_db: str,
    archiv_wurzel: Optional[str],
    schreiben: bool = True,
    einbetter: Optional[Einbetter] = None,
    budget_usd: float = 1.0,
    stapel: int = 100,
    fortschritt_je: int = 500,
    ausgabe_strom=None,
    vorschau: Optional[Tuple[int, int, int]] = None,
) -> Dict[str, Any]:
    """Neue Nachrichten/Chunks in den Index haengen und fehlende Vektoren rechnen.

    ``vorschau`` = (Nachrichten, Chunks, Zeichen) aus einem Trockenlauf der
    Textschicht. Im Trockenlauf steht das Neue noch nicht in ``memory.db``, der
    Index kann es also nicht selbst nachzaehlen — dann gilt die Vorschau.
    """
    strom = ausgabe_strom or sys.stdout
    zaehler: Dict[str, Any] = {
        "neue_nachrichten": 0, "neue_chunks": 0, "neue_vektoren": 0,
        "tokens_gezaehlt": 0, "tokens_geschaetzt": 0, "kosten_usd": 0.0,
        "dauer_s": 0.0, "budget_usd": budget_usd,
    }
    start = time.time()

    if not os.path.isfile(index_pfad):
        raise FileNotFoundError(f"Index nicht gefunden: {index_pfad}")
    if not os.path.isfile(memory_db):
        raise FileNotFoundError(f"Quell-Datenbank nicht gefunden: {memory_db}")

    quelle = sqlite3.connect(f"file:{memory_db}?mode=ro", uri=True)
    quelle.row_factory = sqlite3.Row
    ziel = sqlite3.connect(index_pfad)
    ziel.row_factory = sqlite3.Row
    finder = QuelldateiFinder(archiv_wurzel) if archiv_wurzel else None
    sicherung = None
    abgebrochen = False

    try:
        roh_nachricht = ziel.execute("SELECT max(id) FROM nachrichten").fetchone()[0]
        ab_nachricht = -1 if roh_nachricht is None else int(roh_nachricht)

        neue_nachrichten = quelle.execute(
            "SELECT id, conversation_id, source, timestamp, role, text, title, project "
            "FROM messages WHERE id > ? ORDER BY id", (ab_nachricht,),
        ).fetchall()

        # Chunks: alles, was im Index fehlt — nicht nur „groesser als das
        # hoechste" (Chunks koennen Luecken haben, wenn ein Lauf abbrach).
        vorhandene = {z[0] for z in ziel.execute("SELECT id FROM chunks")}
        fehlende_ids = [
            z[0] for z in quelle.execute("SELECT id FROM chunks ORDER BY id")
            if z[0] not in vorhandene
        ]
        neue_chunks: List[sqlite3.Row] = []
        for anfang in range(0, len(fehlende_ids), 900):
            block = fehlende_ids[anfang:anfang + 900]
            neue_chunks.extend(quelle.execute(
                "SELECT id, conversation_id, source, text, nachricht_ids, beginn, ende, "
                "       title, project, teil FROM chunks WHERE id IN (%s) ORDER BY id"
                % ",".join("?" * len(block)), block,
            ).fetchall())
        zaehler["neue_nachrichten"] = len(neue_nachrichten)
        zaehler["neue_chunks"] = len(neue_chunks)
        if vorschau is not None and not schreiben:
            zaehler["neue_nachrichten"], zaehler["neue_chunks"], zeichen = vorschau
            zaehler["tokens_geschaetzt"] = int(zeichen / ZEICHEN_JE_TOKEN)
        else:
            zaehler["tokens_geschaetzt"] = int(
                sum(len(z["text"] or "") for z in neue_chunks) / ZEICHEN_JE_TOKEN
            )
        zaehler["kosten_schaetzung_usd"] = round(
            zaehler["tokens_geschaetzt"] / 1_000_000 * PREIS_JE_MIO_TOKEN, 4
        )

        # Offene Vektoren: Chunks ohne Vektor. Vor dem Anhaengen sind das die
        # alten Luecken, nach dem Anhaengen zusaetzlich die neuen Chunks.
        vorher_offen = _zaehle(ziel, "chunks", "WHERE hat_vektor = 0")
        zaehler["offene_vorher"] = vorher_offen
        if vorschau is not None and not schreiben:
            zeichen_offen = vorschau[2]
            zaehler["offene_vektoren"] = vorher_offen + vorschau[1]
        else:
            zeichen_offen = (
                sum(len(z["text"] or "") for z in ziel.execute(
                    "SELECT text FROM chunks WHERE hat_vektor = 0"))
                + sum(len(z["text"] or "") for z in neue_chunks)
            )
            zaehler["offene_vektoren"] = vorher_offen + len(neue_chunks)
        tokens_offen = int(zeichen_offen / ZEICHEN_JE_TOKEN)
        zaehler["tokens_offen_geschaetzt"] = tokens_offen
        kosten_offen_exakt = tokens_offen / 1_000_000 * PREIS_JE_MIO_TOKEN
        zaehler["kosten_offen_schaetzung_usd"] = round(kosten_offen_exakt, 4)

        if not schreiben:
            zaehler["dauer_s"] = round(time.time() - start, 1)
            return zaehler

        # Harte Kostengrenze: lieber vorher abbrechen als blind ausgeben.
        if einbetter is not None and kosten_offen_exakt > budget_usd:
            raise BudgetUeberschritten(
                f"Schaetzung {kosten_offen_exakt:.6f} USD liegt ueber dem "
                f"Budget von {budget_usd} USD - nichts geschrieben."
            )

        sicherung = index_pfad.replace(
            ".db", f"_vor_ergaenzung_{datetime.now().strftime('%Y%m%d-%H%M')}.db"
        )
        if not os.path.exists(sicherung):
            shutil.copy2(index_pfad, sicherung)
        zaehler["sicherung"] = sicherung

        # 1) Nachrichten, Chunks und FTS-Zeilen anhaengen (nur neue ids) ------
        if neue_nachrichten:
            ziel.executemany(
                "INSERT OR REPLACE INTO nachrichten (id, conversation_id, source, timestamp,"
                " role, text, title, project) VALUES (?,?,?,?,?,?,?,?)",
                [tuple(z) for z in neue_nachrichten],
            )
        kennungen: List[str] = []
        gesehen = set()
        for z in list(neue_chunks) + list(neue_nachrichten):
            kid = z["conversation_id"] or ""
            if kid not in gesehen:
                gesehen.add(kid)
                kennungen.append(kid)
        if neue_chunks:
            ziel.executemany(
                "INSERT OR REPLACE INTO chunks (id, conversation_id, source, text, nachricht_ids,"
                " beginn, ende, title, project, teil, quelldatei, hat_vektor)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,0)",
                [
                    (
                        z["id"], z["conversation_id"], z["source"], z["text"], z["nachricht_ids"],
                        z["beginn"], z["ende"], z["title"], z["project"], z["teil"],
                        (finder.suchen(z["source"], z["conversation_id"] or "")
                         if finder else None),
                    )
                    for z in neue_chunks
                ],
            )
            ids_neu = [z["id"] for z in neue_chunks]
            for anfang in range(0, len(ids_neu), 900):
                block = ids_neu[anfang:anfang + 900]
                ziel.execute(
                    "INSERT INTO chunks_fts (rowid, text) "
                    "SELECT id, text FROM chunks WHERE id IN (%s)" % ",".join("?" * len(block)),
                    block,
                )
            ziel.execute("INSERT INTO chunks_fts (chunks_fts) VALUES ('optimize')")
        if kennungen:
            _gespraeche_auffrischen(ziel, kennungen)
        ziel.commit()
        print(f"  angehaengt: {len(neue_nachrichten)} Nachrichten, {len(neue_chunks)} Chunks",
              file=strom, flush=True)

        # 2) Fehlende Vektoren rechnen (nur offene Chunks) --------------------
        offene: List[Tuple[int, str]] = [
            (z["id"], z["text"])
            for z in ziel.execute("SELECT id, text FROM chunks WHERE hat_vektor = 0 ORDER BY id")
        ]
        if einbetter is not None and offene:
            print(f"→ Vektoren rechnen (OpenRouter): {len(offene)} offen, "
                  f"Schaetzung {zaehler['kosten_offen_schaetzung_usd']:.4f} USD",
                  file=strom, flush=True)
            fehlversuche = 0
            for anfang in range(0, len(offene), stapel):
                block = offene[anfang:anfang + stapel]
                try:
                    vektoren, _ = einbetter([t for _, t in block])
                except Exception as e:  # noqa: BLE001
                    fehlversuche += 1
                    print(f"  ! Block ab {anfang} fehlgeschlagen ({fehlversuche}/"
                          f"{MAX_FEHLVERSUCHE}): {e}", file=strom, flush=True)
                    if fehlversuche >= MAX_FEHLVERSUCHE:
                        raise
                    continue
                ziel.executemany(
                    "INSERT OR REPLACE INTO vektoren (chunk_id, dimension, modell, vektor)"
                    " VALUES (?,?,?,?)",
                    [(z[0], len(v), getattr(einbetter, "modell", STANDARD_MODELL),
                      _vektor_blob(v)) for z, v in zip(block, vektoren)],
                )
                ziel.execute(
                    "UPDATE chunks SET hat_vektor = 1 WHERE id IN (%s)"
                    % ",".join("?" * len(block)), [z[0] for z in block],
                )
                ziel.commit()
                zaehler["neue_vektoren"] += len(block)
                if (anfang // stapel) % max(1, fortschritt_je // stapel) == 0:
                    print(f"    {zaehler['neue_vektoren']}/{len(offene)} Chunks "
                          f"({time.time() - start:.0f}s)", file=strom, flush=True)

                # Kostengrenze auch waehrend des Laufs einhalten.
                verbraucht = int(getattr(einbetter, "token_gesamt", 0) or 0)
                kosten = verbraucht / 1_000_000 * PREIS_JE_MIO_TOKEN
                if kosten > budget_usd:
                    abgebrochen = True
                    rest = len(offene) - zaehler["neue_vektoren"]
                    print(f"  ! Budget {budget_usd} USD erreicht ({kosten:.4f} USD) - "
                          f"abgebrochen, {rest} Chunks bleiben offen (wiederholbar).",
                          file=strom, flush=True)
                    break

        # 3) Meta ------------------------------------------------------------
        zaehler["tokens_gezaehlt"] = int(getattr(einbetter, "token_gesamt", 0) or 0)
        zaehler["kosten_usd"] = round(
            zaehler["tokens_gezaehlt"] / 1_000_000 * PREIS_JE_MIO_TOKEN, 6
        )
        alt_kosten = float(_meta_lesen(ziel, "kosten_usd", "0") or 0)
        alt_tokens = int(_meta_lesen(ziel, "tokens_gezaehlt", "0") or 0)
        dimension = ziel.execute("SELECT max(dimension) FROM vektoren").fetchone()[0] or 0
        _meta_setzen(ziel, {
            "ergaenzt_am": datetime.now(timezone.utc).isoformat(),
            "nachrichten": str(_zaehle(ziel, "nachrichten")),
            "chunks": str(_zaehle(ziel, "chunks")),
            "vektoren": str(_zaehle(ziel, "vektoren")),
            "gespraeche": str(_zaehle(ziel, "gespraeche")),
            "dimension": str(dimension),
            "tokens_gezaehlt": str(alt_tokens + zaehler["tokens_gezaehlt"]),
            "kosten_usd": str(round(alt_kosten + zaehler["kosten_usd"], 6)),
            "kosten_ergaenzung_usd": str(zaehler["kosten_usd"]),
        })
        ziel.commit()
        zaehler["nachrichten_gesamt"] = _zaehle(ziel, "nachrichten")
        zaehler["chunks_gesamt"] = _zaehle(ziel, "chunks")
        zaehler["vektoren_gesamt"] = _zaehle(ziel, "vektoren")
        zaehler["gespraeche_gesamt"] = _zaehle(ziel, "gespraeche")
    finally:
        quelle.close()
        ziel.close()

    zaehler["abgebrochen"] = abgebrochen
    zaehler["dauer_s"] = round(time.time() - start, 1)
    return zaehler


class BudgetUeberschritten(RuntimeError):
    """Die geschaetzten Kosten liegen ueber der Grenze — es wird nichts geschrieben."""


# ── Bericht ─────────────────────────────────────────────────────────────────

def _z(n: Any) -> str:
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def bericht_text(memory_z: Optional[Dict[str, Any]], index_z: Optional[Dict[str, Any]],
                 modus: str) -> str:
    zeilen: List[str] = [f"=== Archiv inkrementell ergaenzen ({modus}) ==="]
    if memory_z is not None:
        zeilen.append("memory.db (Textschicht, ohne Vektoren):")
        zeilen.append(f"  Nachrichten        {_z(memory_z.get('nachrichten_vorher'))} "
                      f"-> {_z(memory_z.get('nachrichten_nachher'))}")
        zeilen.append(f"  Chunks             {_z(memory_z.get('chunks_vorher'))} "
                      f"-> {_z(memory_z.get('chunks_nachher'))}")
        zeilen.append(f"  neu                {_z(memory_z.get('neue_nachrichten'))} Nachrichten, "
                      f"{_z(memory_z.get('neue_chunks'))} Chunks")
        if memory_z.get("behalten") is not None:
            zeilen.append(f"  Filter behalten    {_z(memory_z.get('behalten'))}")
        zeilen.append(f"  Chunk-Dubletten    {_z(memory_z.get('chunk_dubletten', 0))}")
        zeilen.append(f"  Chunks ohne Vektor {_z(memory_z.get('ohne_vektor', 0))}")
    if index_z is not None:
        zeilen.append("archiv_index.db (Text, FTS, Vektoren):")
        zeilen.append(f"  neue Nachrichten   {_z(index_z.get('neue_nachrichten'))}")
        zeilen.append(f"  neue Chunks        {_z(index_z.get('neue_chunks'))}")
        zeilen.append(f"  neue Vektoren      {_z(index_z.get('neue_vektoren'))}")
        zeilen.append(f"  offen              {_z(index_z.get('offene_vektoren', 0))}")
        zeilen.append(f"  Token (Schaetzung) {_z(index_z.get('tokens_offen_geschaetzt'))}")
        zeilen.append(f"  Token (gezaehlt)   {_z(index_z.get('tokens_gezaehlt'))}")
        zeilen.append(f"  Kosten             {index_z.get('kosten_usd', 0):.4f} $ "
                      f"(Grenze {index_z.get('budget_usd')} $)")
        if index_z.get("nachrichten_gesamt") is not None:
            zeilen.append(f"  Bestand danach     {_z(index_z.get('nachrichten_gesamt'))} Nachrichten, "
                          f"{_z(index_z.get('chunks_gesamt'))} Chunks, "
                          f"{_z(index_z.get('vektoren_gesamt'))} Vektoren, "
                          f"{_z(index_z.get('gespraeche_gesamt'))} Gespraeche")
        if index_z.get("sicherung"):
            zeilen.append(f"  Sicherung          {os.path.basename(index_z['sicherung'])}")
        if index_z.get("abgebrochen"):
            zeilen.append("  ! Lauf am Budget abgebrochen - offene Chunks bleiben liegen")
        zeilen.append(f"  Dauer              {index_z.get('dauer_s', 0)} s")
    return "\n".join(zeilen)


# ── Hauptlauf ───────────────────────────────────────────────────────────────

def main(argv: Optional[Sequence[str]] = None) -> int:
    wahl = argparse.ArgumentParser(
        description="Ergaenzt Archiv-Index und Einbettungen inkrementell um neue Zeilen."
    )
    wahl.add_argument("--archiv", default=None, help="Archivwurzel (Standard: neben dem Projekt)")
    wahl.add_argument("--quelle", default=None, help="normalized/messages.jsonl")
    wahl.add_argument("--memory-db", default=None)
    wahl.add_argument("--index", default=None)
    wahl.add_argument("--trocken", action="store_true", help="nur rechnen (Standard)")
    wahl.add_argument("--schreiben", action="store_true", help="wirklich anhaengen")
    wahl.add_argument("--mit-vektoren", action="store_true",
                      help="fehlende Vektoren ueber OpenRouter rechnen")
    wahl.add_argument("--budget", type=float, default=1.0, help="harte Kostengrenze in USD")
    wahl.add_argument("--stapel", type=int, default=100, help="Chunks je Einbettungs-Aufruf")
    wahl.add_argument("--modell", default=STANDARD_MODELL)
    wahl.add_argument("--basis-url", default=STANDARD_BASIS)
    wahl.add_argument("--nur-memory", action="store_true", help="nur die Textschicht erweitern")
    wahl.add_argument("--nur-index", action="store_true",
                      help="nur den Index erweitern (memory.db ist schon aktuell)")
    args = wahl.parse_args(argv)
    if args.trocken and args.schreiben:
        print("Bitte nur eines von --trocken und --schreiben angeben.")
        return 2

    archiv = args.archiv or _standard_archiv()
    if not archiv:
        print("Archiv nicht gefunden - bitte --archiv angeben.")
        return 2
    quelle = args.quelle or os.path.join(archiv, "normalized", "messages.jsonl")
    memory_db = args.memory_db or os.path.join(archiv, "db", "memory.db")
    index = args.index or os.path.join(archiv, "db", "archiv_index.db")
    schreiben = bool(args.schreiben)
    modus = "schreiben" if schreiben else "Trockenlauf"

    print(f"Archiv : {archiv}")
    print(f"Quelle : {quelle}")
    print(f"memory : {memory_db}")
    print(f"Index  : {index}")
    print(f"Modus  : {modus} | Vektoren: {'ja' if args.mit_vektoren else 'nein'} "
          f"| Budget: {args.budget} $")

    einbetter: Optional[Einbetter] = None
    if args.mit_vektoren:
        schluessel = _schluessel_holen()
        if not schluessel:
            print("Kein OPENROUTER_API_KEY gefunden - ohne --mit-vektoren laufen lassen "
                  "oder Schluessel in backend/.env bzw. workspace/.env eintragen.")
            return 3
        einbetter = EinbetterOpenRouter(
            schluessel, modell=args.modell, basis_url=args.basis_url, stapel=args.stapel
        )

    memory_z: Optional[Dict[str, Any]] = None
    index_z: Optional[Dict[str, Any]] = None

    try:
        if not args.nur_index:
            try:
                module = lade_archiv_module(archiv)
            except ImportError as e:
                print(f"Archive-Werkzeuge (src.*) nicht gefunden: {e} — bitte --archiv pruefen.")
                return 2
            memory_z = memory_db_erweitern(memory_db, quelle, module, schreiben=schreiben)
        if not args.nur_memory:
            vorschau = None
            if memory_z is not None and not schreiben:
                vorschau = (
                    memory_z.get("neue_nachrichten", 0),
                    memory_z.get("neue_chunks", 0),
                    memory_z.get("neue_chunk_zeichen", 0),
                )
            index_z = index_erweitern(
                index, memory_db, archiv, schreiben=schreiben, einbetter=einbetter,
                budget_usd=args.budget, stapel=args.stapel, vorschau=vorschau,
            )
    except BudgetUeberschritten as e:
        print(f"\nBudget-Grenze: {e}")
        print(bericht_text(memory_z, None, modus))
        return 4

    print(bericht_text(memory_z, index_z, modus))
    if not schreiben:
        print("\nTrockenlauf - nichts geschrieben. Mit --schreiben anhaengen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
