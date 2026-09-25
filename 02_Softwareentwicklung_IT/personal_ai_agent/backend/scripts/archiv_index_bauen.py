"""
Baut den uebertragbaren Wissensspeicher-Index aus dem Chat-Archiv.

Was hier passiert
=================

Das Schwesterprojekt ``Chats von GPT, GEMINI, Claude`` hat die Rohdaten
(ChatGPT-Export, Gemini-Aktivitaeten, Claude-Exports, Google-Takeout) bereits
in eine Normalform gebracht und in ``db/memory.db`` abgelegt: 40.627
Nachrichten in ``messages``, 30.891 Fundstellen in ``chunks``, dazu ein
FTS5-Volltextindex. **Diese Vorarbeit wird uebernommen, nicht wiederholt** —
neu extrahiert wird nichts.

Was hier neu entsteht, ist eine **einzige Datei** (``archiv_index.db``), die
alles traegt, was das Handy braucht:

  * ``nachrichten`` — der Originaltext jeder Nachricht (zum Nachlesen)
  * ``chunks`` + ``chunks_fts`` — die Fundstellen und der Wortlaut-Index
  * ``vektoren`` — die Bedeutung (float16, OpenRouter-Einbettungen)
  * ``gespraeche`` — Kennzahlen, Zeitraum und Quelldatei je Gespraech
  * ``meta`` — Modell, Dimension, Zeitraum, Kosten

Die alte Vektordatei (``db/memory.vektoren.f32``, 30.891 x 1024,
``mistral-embed``) wird **absichtlich nicht uebernommen**: Sie passt weder zur
Dimension noch zum Modell und lag ausserdem als rohe Neben-Datei neben der
Datenbank. Wer sein Archiv neu berechnet, will eine Datei, keinen Verbund.

Datenschutz
===========

Beim Einbetten geht der **Chunk-Text** an OpenRouter (das ist der eine noetige
LLM-Aufruf). Alles andere bleibt lokal. Der Schluessel wird nie ausgegeben,
nur seine Laenge.

Kosten
======

``openai/text-embedding-3-small`` kostet rund 0,02 $ je 1 Mio Token. Vor dem
Lauf schaetzt das Skript die Token aus der Textlaenge; danach steht die
**tatsaechlich gezaehlte** Zahl aus der API-Antwort in ``meta``.

Aufruf
======

    cd backend
    .venv/Scripts/python -m scripts.archiv_index_bauen \\
        --archiv "C:/.../Chats von GPT, GEMINI, Claude" \\
        --ausgabe "C:/.../archiv_index.db"

Ohne ``--mit-vektoren`` entsteht nur der Volltext-Index (schnell, kostenlos,
zum Ausprobieren).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

# Das Skript liegt in backend/scripts/ — der Importpfad auf backend/ zeigen,
# damit `app.services.archiv_suche` (Schema, Konstanten) gefunden wird.
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.services.archiv_suche import SCHEMA_SQL  # noqa: E402

# Einbetter: nimmt Texte, gibt (Vektoren, verbrauchte Token) zurueck.
Einbetter = Callable[[Sequence[str]], Tuple[List[List[float]], int]]

STANDARD_MODELL = "openai/text-embedding-3-small"
STANDARD_BASIS = "https://openrouter.ai/api/v1"

# Zeichen je Token. Deutsch braucht etwas mehr Token als Englisch; 3,6 ist
# eine vorsichtige Schaetzung, die lieber zu hoch als zu niedrig liegt.
ZEICHEN_JE_TOKEN = 3.6

PREIS_JE_MIO_TOKEN = 0.02  # $ fuer openai/text-embedding-3-small

# Ab wie vielen Fehlversuchen ein Lauf aufgibt (Netzprobleme, Kontingent).
MAX_FEHLVERSUCHE = 5


# ── Quelldatei im Archiv ermitteln ─────────────────────────────────────────
class QuelldateiFinder:
    """Findet zu einem Gespraech die Datei, aus der es stammt.

    Sebastian will jeden Treffer bis ins Original zurueckverfolgen koennen
    (25.09.2026). Der Index kennt die Chat-Kennung und das Nachrichten-Ordinal
    ohnehin; hier kommt der Pfad der Quelldatei dazu.

    Der Finder arbeitet mit den Mustern, die auch die Adapter des
    Schwesterprojekts benutzen, ist aber eigenstaendig — das Backend soll
    nicht von einem zweiten Projekt abhaengen.

    Faellt die Suche aus (Datei umbenannt, Quelle unbekannt), bleibt
    ``normalized/messages.jsonl`` der Zeiger: Dort steht die Nachricht mit
    derselben Ordnungszahl, also ist der Rueckweg immer offen.
    """

    def __init__(self, archiv_wurzel: str):
        self.wurzel = archiv_wurzel
        self._zwischenspeicher: Dict[str, Optional[str]] = {}
        self._chatgpt_karte: Optional[Dict[str, str]] = None
        self._takeout_gefunden: Optional[Dict[str, str]] = None

    # -- ChatGPT: welcher Shard enthaelt das Gespraech? --------------------
    def _chatgpt_shards(self) -> Dict[str, str]:
        """Einmal alle Shards scannen und Kennung -> Datei merken.

        Zwei Durchlaeufe (Byte-Suche, kein JSON-Parsen) sind billiger als
        19.000-mal eine 65-MB-Datei zu oeffnen.
        """
        if self._chatgpt_karte is not None:
            return self._chatgpt_karte
        karte: Dict[str, str] = {}
        muster = os.path.join(self.wurzel, "raw", "chatgpt", "conversations-*.json")
        for pfad in sorted(glob.glob(muster)):
            relativ = self._relativ(pfad)
            try:
                with open(pfad, "rb") as f:
                    roh = f.read()
            except OSError:
                continue
            # Die Gespraechs-Kennungen sind UUIDs; sie im Rohtext zu suchen
            # ist genau genug und spart das Parsen von 65 MB JSON.
            for treffer in _uuid_aus_bytes(roh):
                karte.setdefault(treffer, relativ)
        self._chatgpt_karte = karte
        return karte

    def _takeout_karte(self) -> Dict[str, str]:
        """Welcher Takeout-Zip traegt welche Google-Datei."""
        if self._takeout_gefunden is not None:
            return self._takeout_gefunden
        karte: Dict[str, str] = {}
        import zipfile

        for pfad in sorted(glob.glob(os.path.join(self.wurzel, "raw", "takeout-*.zip"))):
            relativ = self._relativ(pfad)
            try:
                with zipfile.ZipFile(pfad) as z:
                    for name in z.namelist():
                        karte.setdefault(name, relativ)
            except (OSError, zipfile.BadZipFile):
                continue
        self._takeout_gefunden = karte
        return karte

    def _relativ(self, pfad: str) -> str:
        try:
            return os.path.relpath(pfad, self.wurzel).replace("\\", "/")
        except ValueError:
            return pfad.replace("\\", "/")

    def suchen(self, source: str, chat_kennung: str) -> Optional[str]:
        """Pfad der Quelldatei, oder None wenn er sich nicht bestimmen laesst."""
        schluessel = f"{source}|{chat_kennung}"
        if schluessel in self._zwischenspeicher:
            return self._zwischenspeicher[schluessel]
        ergebnis = self._suchen_ungespeichert(source, chat_kennung)
        self._zwischenspeicher[schluessel] = ergebnis
        return ergebnis

    def _suchen_ungespeichert(self, source: str, chat_kennung: str) -> Optional[str]:
        try:
            if source == "chatgpt":
                return self._chatgpt_shards().get(chat_kennung)

            if source == "claude-ai":
                pfad = os.path.join(self.wurzel, "raw", "claude-ai", "conversations.json")
                return self._relativ(pfad) if os.path.isfile(pfad) else None

            if source == "claude-code":
                muster = os.path.join(
                    self.wurzel, "raw", "claude-code", "**", f"{chat_kennung}*.jsonl"
                )
                treffer = sorted(glob.glob(muster, recursive=True))
                return self._relativ(treffer[0]) if treffer else None

            if source == "gemini":
                zip_datei = self._takeout_karte().get(
                    "Takeout/Meine Aktivitäten/Gemini-Apps/MeineAktivitäten.html"
                )
                return f"{zip_datei}::Takeout/Meine Aktivitäten/Gemini-Apps/MeineAktivitäten.html" if zip_datei else None

            if source.startswith("google"):
                karte = self._takeout_karte()
                # Am genauesten: Bei Google-Notizen ist die Kennung der
                # Dateiname ohne Endung. (Kalenderkennungen sind ICS-UIDs —
                # die passen auf keinen Dateinamen.)
                for name, zip_datei in karte.items():
                    if name.rsplit("/", 1)[-1].rsplit(".", 1)[0] == chat_kennung:
                        return f"{zip_datei}::{name}"
                # Sonst die Ebene des Bereichs. Die Takeout-Ordner heissen
                # "Kalender" und "Google Notizen" — nicht "Notizen".
                bereich = "Kalender" if "kalender" in source else "Google Notizen"
                for name, zip_datei in karte.items():
                    if f"/{bereich}/" in name:
                        return f"{zip_datei}::{name}"
                return None
        except Exception as e:  # nie den ganzen Lauf an einem Pfad scheitern lassen
            print(f"  ! Quelldatei nicht ermittelbar ({source}): {e}", flush=True)
        return None


def _uuid_aus_bytes(roh: bytes) -> set:
    """Alle UUID-artigen Zeichenketten aus einem Byte-Block ziehen."""
    import re

    muster = re.compile(rb"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
    return {m.group(0).decode("ascii") for m in muster.finditer(roh)}


# ── Einbetter ueber OpenRouter ─────────────────────────────────────────────
class EinbetterOpenRouter:
    """Chunks bei OpenRouter einbetten (OpenAI-kompatibler Endpunkt).

    Es geht nur der Text der Chunks hinaus. Der Schluessel wird nirgends
    geloggt oder ausgegeben.
    """

    def __init__(
        self,
        schluessel: str,
        modell: str = STANDARD_MODELL,
        basis_url: str = STANDARD_BASIS,
        stapel: int = 100,
        wiederholungen: int = 3,
    ):
        if not schluessel:
            raise ValueError("Kein OPENROUTER_API_KEY vorhanden.")
        self.schluessel = schluessel
        self.modell = modell
        self.basis_url = basis_url.rstrip("/")
        self.stapel = max(1, stapel)
        self.wiederholungen = wiederholungen
        self.token_gesamt = 0
        self.aufrufe = 0

    def __call__(self, texte: Sequence[str]) -> Tuple[List[List[float]], int]:
        import httpx

        letzter_fehler: Optional[Exception] = None
        for versuch in range(self.wiederholungen):
            try:
                antwort = httpx.post(
                    f"{self.basis_url}/embeddings",
                    headers={"Authorization": f"Bearer {self.schluessel}"},
                    json={"model": self.modell, "input": list(texte)},
                    timeout=120,
                )
                if antwort.status_code >= 400 and versuch + 1 < self.wiederholungen:
                    # 429 (Kontingent) und 5xx lohnen einen zweiten Versuch.
                    letzter_fehler = RuntimeError(
                        f"HTTP {antwort.status_code}: {antwort.text[:200]}"
                    )
                    time.sleep(2.0 * (versuch + 1))
                    continue
                antwort.raise_for_status()
                daten = antwort.json()
                eintraege = daten.get("data") or []
                # Reihenfolge sichern: OpenRouter liefert `index`, darauf
                # verlassen wir uns nicht blind.
                eintraege = sorted(eintraege, key=lambda e: e.get("index", 0))
                vektoren = [e["embedding"] for e in eintraege]
                if len(vektoren) != len(texte):
                    raise RuntimeError(
                        f"Antwort mit {len(vektoren)} Vektoren auf {len(texte)} Texte"
                    )
                token = int((daten.get("usage") or {}).get("total_tokens") or 0)
                if not token:
                    token = int(sum(len(t) for t in texte) / ZEICHEN_JE_TOKEN)
                self.token_gesamt += token
                self.aufrufe += 1
                return vektoren, token
            except Exception as e:  # noqa: BLE001 - Netzfehler sind vielfaeltig
                letzter_fehler = e
                time.sleep(1.5 * (versuch + 1))
        raise RuntimeError(f"Einbettung endgueltig fehlgeschlagen: {letzter_fehler}")


# ── Aufbau ─────────────────────────────────────────────────────────────────
def _oeffne_ziel(pfad: str) -> sqlite3.Connection:
    ziel = sqlite3.connect(pfad)
    ziel.row_factory = sqlite3.Row
    # Einmal-Aufbau: Haltbarkeit ist hier unnoetig, Tempo zaehlt.
    ziel.execute("PRAGMA journal_mode = MEMORY")
    ziel.execute("PRAGMA synchronous = OFF")
    ziel.executescript(SCHEMA_SQL)
    return ziel


def _vektor_blob(vektor: Sequence[float]) -> bytes:
    import numpy as np

    return np.asarray(vektor, dtype=np.float16).tobytes()


def _token_schaetzen(texte: Sequence[str]) -> int:
    return int(sum(len(t or "") for t in texte) / ZEICHEN_JE_TOKEN)


def baue_index(
    quelle_db: str,
    ausgabe: str,
    archiv_wurzel: Optional[str] = None,
    einbetter: Optional[Einbetter] = None,
    stapel: int = 100,
    limit: Optional[int] = None,
    ohne_quelldatei_scan: bool = False,
    fortschritt_je: int = 2000,
    ausgabe_strom=None,
) -> Dict[str, Any]:
    """Den Index bauen. Gibt einen Bericht zurueck (Zahlen, keine Inhalte).

    ``einbetter`` ist injizierbar: Tests geben eine Attrappe hinein und
    brauchen so weder Netz noch Schluessel. Ohne ``einbetter`` entsteht ein
    reiner Volltext-Index.
    """
    strom = ausgabe_strom or sys.stdout
    zaehler: Dict[str, Any] = {
        "nachrichten": 0,
        "chunks": 0,
        "gespraeche": 0,
        "vektoren": 0,
        "fehlende_quelldatei": 0,
        "tokens_geschaetzt": 0,
        "tokens_gezaehlt": 0,
        "kosten_usd": 0.0,
        "dauer_s": 0.0,
    }
    start = time.time()

    if not os.path.isfile(quelle_db):
        raise FileNotFoundError(f"Quell-Datenbank nicht gefunden: {quelle_db}")

    ziel_datei = ausgabe + ".tmp"
    if os.path.exists(ziel_datei):
        os.remove(ziel_datei)

    finder = QuelldateiFinder(archiv_wurzel) if archiv_wurzel and not ohne_quelldatei_scan else None

    quelle = sqlite3.connect(f"file:{quelle_db}?mode=ro", uri=True)
    quelle.row_factory = sqlite3.Row
    ziel = _oeffne_ziel(ziel_datei)

    try:
        # 1) Nachrichten uebernehmen (Originaltexte, zum Nachlesen) ----------
        print("→ Nachrichten übernehmen …", file=strom, flush=True)
        stueck = 2000
        versatz = 0
        while True:
            zeilen = quelle.execute(
                "SELECT id, conversation_id, source, timestamp, role, text, title, project "
                "FROM messages ORDER BY id LIMIT ? OFFSET ?",
                (stueck, versatz),
            ).fetchall()
            if not zeilen:
                break
            ziel.executemany(
                "INSERT INTO nachrichten (id, conversation_id, source, timestamp, role, text, title, project) "
                "VALUES (?,?,?,?,?,?,?,?)",
                [tuple(z) for z in zeilen],
            )
            zaehler["nachrichten"] += len(zeilen)
            versatz += stueck
        ziel.commit()
        print(f"  {zaehler['nachrichten']} Nachrichten", file=strom, flush=True)

        # 2) Chunks uebernehmen ---------------------------------------------
        print("→ Fundstellen (Chunks) übernehmen …", file=strom, flush=True)
        chunks: List[sqlite3.Row] = []
        sql_chunks = (
            "SELECT id, conversation_id, source, text, nachricht_ids, beginn, ende, "
            "title, project, teil FROM chunks ORDER BY id"
        )
        if limit:
            sql_chunks += f" LIMIT {int(limit)}"
        for zeile in quelle.execute(sql_chunks):
            chunks.append(zeile)
        zaehler["chunks"] = len(chunks)

        # Quelldatei je Gespraech einmal bestimmen — nicht je Chunk.
        kennungen: Dict[str, Tuple[str, Optional[str]]] = {}
        for z in chunks:
            kid = z["conversation_id"] or ""
            if kid not in kennungen:
                pfad = finder.suchen(z["source"], kid) if finder else None
                if finder and not pfad:
                    zaehler["fehlende_quelldatei"] += 1
                kennungen[kid] = (z["source"], pfad)

        ziel.executemany(
            "INSERT INTO chunks (id, conversation_id, source, text, nachricht_ids, beginn, "
            "ende, title, project, teil, quelldatei, hat_vektor) VALUES (?,?,?,?,?,?,?,?,?,?,?,0)",
            [
                (
                    z["id"], z["conversation_id"], z["source"], z["text"], z["nachricht_ids"],
                    z["beginn"], z["ende"], z["title"], z["project"], z["teil"],
                    kennungen.get(z["conversation_id"] or "", ("", None))[1],
                )
                for z in chunks
            ],
        )
        ziel.commit()
        print(f"  {zaehler['chunks']} Chunks, {len(kennungen)} Gespräche", file=strom, flush=True)

        # 3) Volltextindex ---------------------------------------------------
        print("→ Volltextindex (FTS5) bauen …", file=strom, flush=True)
        ziel.execute("INSERT INTO chunks_fts(rowid, text) SELECT id, text FROM chunks")
        ziel.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('optimize')")
        ziel.commit()

        # 4) Gespraechsuebersicht (Chronik, Statistik) -----------------------
        print("→ Gesprächsübersicht bauen …", file=strom, flush=True)
        ziel.execute(
            """
            INSERT INTO gespraeche (conversation_id, source, title, quelldatei, von, bis,
                                    anzahl_nachrichten, anzahl_chunks)
            SELECT c.conversation_id,
                   min(c.source),
                   max(c.title),
                   max(c.quelldatei),
                   min(c.beginn),
                   max(c.ende),
                   (SELECT count(*) FROM nachrichten n WHERE n.conversation_id = c.conversation_id),
                   count(*)
            FROM chunks c
            GROUP BY c.conversation_id
            """
        )
        ziel.commit()
        zaehler["gespraeche"] = ziel.execute("SELECT count(*) FROM gespraeche").fetchone()[0]

        # 5) Vektoren --------------------------------------------------------
        if einbetter is not None and chunks:
            print("→ Vektoren rechnen (OpenRouter) …", file=strom, flush=True)
            zaehler["tokens_geschaetzt"] = _token_schaetzen([z["text"] for z in chunks])
            fehlversuche = 0
            for anfang in range(0, len(chunks), stapel):
                block = chunks[anfang:anfang + stapel]
                texte = [z["text"] for z in block]
                try:
                    vektoren, _ = einbetter(texte)
                except Exception as e:  # noqa: BLE001
                    fehlversuche += 1
                    print(
                        f"  ! Block {anfang}-{anfang + len(block)} fehlgeschlagen "
                        f"({fehlversuche}/{MAX_FEHLVERSUCHE}): {e}",
                        file=strom, flush=True,
                    )
                    if fehlversuche >= MAX_FEHLVERSUCHE:
                        raise
                    continue
                ziel.executemany(
                    "INSERT INTO vektoren (chunk_id, dimension, modell, vektor) VALUES (?,?,?,?)",
                    [
                        (z["id"], len(v), getattr(einbetter, "modell", STANDARD_MODELL), _vektor_blob(v))
                        for z, v in zip(block, vektoren)
                    ],
                )
                zaehler["vektoren"] += len(block)
                if (anfang // stapel) % max(1, fortschritt_je // stapel) == 0:
                    print(
                        f"    {zaehler['vektoren']}/{len(chunks)} Chunks "
                        f"({time.time() - start:.0f}s)",
                        file=strom, flush=True,
                    )
            ziel.commit()
            ziel.execute(
                "UPDATE chunks SET hat_vektor = 1 WHERE id IN (SELECT chunk_id FROM vektoren)"
            )
            ziel.commit()
            zaehler["tokens_gezaehlt"] = int(getattr(einbetter, "token_gesamt", 0) or 0)
            zaehler["aufrufe"] = int(getattr(einbetter, "aufrufe", 0) or 0)

        # 6) Meta ------------------------------------------------------------
        dimension = 0
        if zaehler["vektoren"]:
            dimension = ziel.execute(
                "SELECT max(dimension) FROM vektoren"
            ).fetchone()[0] or 0
        von, bis = ziel.execute("SELECT min(beginn), max(ende) FROM chunks").fetchone()
        token_fuer_meta = zaehler["tokens_gezaehlt"] or zaehler["tokens_geschaetzt"]
        zaehler["kosten_usd"] = round(token_fuer_meta / 1_000_000 * PREIS_JE_MIO_TOKEN, 6)
        meta = {
            "gebaut_am": datetime.now(timezone.utc).isoformat(),
            "quelle_db": os.path.abspath(quelle_db),
            "quelle_jsonl": "normalized/messages.jsonl",
            "archiv_wurzel": os.path.abspath(archiv_wurzel) if archiv_wurzel else "",
            "modell": getattr(einbetter, "modell", "") if einbetter else "",
            "dimension": str(dimension),
            "vektor_speicher": "float16",
            "nachrichten": str(zaehler["nachrichten"]),
            "chunks": str(zaehler["chunks"]),
            "gespraeche": str(zaehler["gespraeche"]),
            "vektoren": str(zaehler["vektoren"]),
            "zeitraum_von": von or "",
            "zeitraum_bis": bis or "",
            "tokens_gezaehlt": str(zaehler["tokens_gezaehlt"]),
            "tokens_geschaetzt": str(zaehler["tokens_geschaetzt"]),
            "kosten_usd": str(zaehler["kosten_usd"]),
            "preis_je_mio_token_usd": str(PREIS_JE_MIO_TOKEN),
        }
        ziel.executemany(
            "INSERT OR REPLACE INTO meta (schluessel, wert) VALUES (?,?)", list(meta.items())
        )
        ziel.commit()
    finally:
        ziel.close()
        quelle.close()

    # Erst jetzt umbenennen: Ein abgebrochener Lauf laesst keinen halben Index
    # unter dem richtigen Namen liegen.
    if os.path.exists(ausgabe):
        os.remove(ausgabe)
    os.replace(ziel_datei, ausgabe)
    zaehler["dauer_s"] = round(time.time() - start, 1)
    zaehler["datei_mb"] = round(os.path.getsize(ausgabe) / 1024 / 1024, 1)
    return zaehler


def bericht(zaehler: Dict[str, Any]) -> str:
    """Kurzer Abschlussbericht — Zahlen, keine Inhalte."""
    return (
        "\n=== Index gebaut ===\n"
        f"  Nachrichten       : {zaehler['nachrichten']}\n"
        f"  Chunks            : {zaehler['chunks']}\n"
        f"  Gespräche         : {zaehler['gespraeche']}\n"
        f"  Vektoren          : {zaehler['vektoren']}\n"
        f"  ohne Quelldatei   : {zaehler['fehlende_quelldatei']}\n"
        f"  Token (schätz.)   : {zaehler['tokens_geschaetzt']}\n"
        f"  Token (gezählt)   : {zaehler['tokens_gezaehlt']}\n"
        f"  Kosten            : {zaehler['kosten_usd']} $ "
        f"({PREIS_JE_MIO_TOKEN} $/1M Token)\n"
        f"  Dauer             : {zaehler['dauer_s']} s\n"
        f"  Dateigröße        : {zaehler.get('datei_mb', 0)} MB\n"
    )


def quelldatei_nachtragen(
    index_pfad: str, archiv_wurzel: str, ausgabe_strom=None
) -> Dict[str, int]:
    """Fehlende Quelldateien in einem bestehenden Index nachtragen.

    Nur der Zeiger wird ergaenzt — **nicht** neu eingebettet. Gedacht fuer den
    Fall, dass eine Quelle beim Bauen nicht erkannt wurde (etwa ein falsch
    benannter Takeout-Ordner): Der Index ist 240 MB und acht Minuten Rechenzeit
    wert, aber deswegen muss man die Vektoren nicht noch einmal bezahlen.
    """
    strom = ausgabe_strom or sys.stdout
    if not os.path.isfile(index_pfad):
        raise FileNotFoundError(f"Index nicht gefunden: {index_pfad}")

    finder = QuelldateiFinder(archiv_wurzel)
    con = sqlite3.connect(index_pfad)
    try:
        offen = con.execute(
            "SELECT conversation_id, source FROM gespraeche WHERE quelldatei IS NULL"
        ).fetchall()
        getroffen = 0
        for kennung, source in offen:
            pfad = finder.suchen(source, kennung)
            if not pfad:
                continue
            con.execute(
                "UPDATE gespraeche SET quelldatei = ? WHERE conversation_id = ?",
                (pfad, kennung),
            )
            con.execute(
                "UPDATE chunks SET quelldatei = ? WHERE conversation_id = ?",
                (pfad, kennung),
            )
            getroffen += 1
        con.commit()
        rest = con.execute(
            "SELECT count(*) FROM gespraeche WHERE quelldatei IS NULL"
        ).fetchone()[0]
    finally:
        con.close()

    print(
        f"→ Quelldateien nachgetragen: {getroffen} von {len(offen)} offenen "
        f"(weiterhin ohne Quelldatei: {rest} — die fallen auf "
        f"normalized/messages.jsonl zurück)",
        file=strom, flush=True,
    )
    return {"offen": len(offen), "nachgetragen": getroffen, "rest": rest}


def _standard_archiv() -> Optional[str]:
    """Das Archiv neben dem Projekt suchen — fuer den bequemen Aufruf.

    Das Archiv liegt als Geschwisterordner von ``02_Softwareentwicklung_IT``,
    also zwei Ebenen ueber dem Projektordner:

        workspace agentic engineering/
        ├── Chats von GPT, GEMINI, Claude/     <- hier
        └── 02_Softwareentwicklung_IT/personal_ai_agent/backend/   <- wir
    """
    kandidaten = [
        os.path.abspath(os.path.join(BACKEND, "..", "..", "..", "Chats von GPT, GEMINI, Claude")),
        os.path.abspath(os.path.join(BACKEND, "..", "..", "Chats von GPT, GEMINI, Claude")),
    ]
    for k in kandidaten:
        if os.path.isdir(k) and os.path.isfile(os.path.join(k, "db", "memory.db")):
            return k
    return None


def _standard_ausgabe(archiv: Optional[str]) -> str:
    """Wohin der Index gehoert.

    Bewusst **in den Archivordner**, nicht ins Projekt: Der Index enthaelt die
    vollstaendigen Gespraeche und ist rund 200 MB gross. Der Archivordner ist
    per ``.gitignore`` aus dem Repo ausgeschlossen, der Projektordner nicht —
    ein Index im Projekt koennte versehentlich mitcommittet werden. Ausserdem
    liegt er dort neben ``db/memory.db``, aus dem er gebaut wird.
    """
    if archiv:
        return os.path.join(archiv, "db", "archiv_index.db")
    return os.path.join(os.path.dirname(BACKEND), "archiv_index.db")


def main(argv: Optional[Sequence[str]] = None) -> int:
    wahl = argparse.ArgumentParser(
        description="Baut den übertragbaren Wissensspeicher-Index (eine Datei)."
    )
    wahl.add_argument(
        "--archiv",
        default=None,
        help="Wurzel des Archivs (mit db/memory.db und raw/). Standard: neben dem Projekt.",
    )
    wahl.add_argument(
        "--quelle-db", default=None, help="Direkt auf die Quell-Datenbank zeigen."
    )
    wahl.add_argument(
        "--ausgabe",
        default=None,
        help="Zieldatei (Standard: <archiv>/db/archiv_index.db — der Archivordner "
             "ist aus dem Repo ausgeschlossen, der Projektordner nicht).",
    )
    wahl.add_argument(
        "--mit-vektoren",
        action="store_true",
        help="Vektoren über OpenRouter rechnen (kostet Bruchteile eines Cents).",
    )
    wahl.add_argument("--stapel", type=int, default=100, help="Chunks je Einbettungs-Aufruf.")
    wahl.add_argument("--limit", type=int, default=None, help="Nur die ersten N Chunks (Probe).")
    wahl.add_argument(
        "--ohne-quelldatei-scan",
        action="store_true",
        help="Quelldateien nicht suchen (schneller; Zeiger zeigt dann auf normalized/messages.jsonl).",
    )
    wahl.add_argument(
        "--nur-quelldatei",
        action="store_true",
        help="Nur fehlende Quelldateien in einem bestehenden Index nachtragen "
             "(kein Neubau, keine Einbettung) — für den Fall, dass eine Quelle "
             "beim Bauen nicht erkannt wurde.",
    )
    wahl.add_argument("--modell", default=STANDARD_MODELL)
    wahl.add_argument("--basis-url", default=STANDARD_BASIS)
    args = wahl.parse_args(argv)

    archiv = args.archiv or _standard_archiv()
    quelle_db = args.quelle_db or (
        os.path.join(archiv, "db", "memory.db") if archiv else None
    )
    if not quelle_db or not os.path.isfile(quelle_db):
        print("Quell-Datenbank nicht gefunden. Bitte --quelle-db oder --archiv angeben.")
        return 2

    einbetter: Optional[EinbetterOpenRouter] = None
    if args.mit_vektoren:
        schluessel = _schluessel_holen()
        if not schluessel:
            print(
                "Kein OPENROUTER_API_KEY gefunden (backend/.env oder Umgebung). "
                "Ohne Schlüssel nur Volltext-Index — dafür --mit-vektoren weglassen."
            )
            return 3
        einbetter = EinbetterOpenRouter(
            schluessel, modell=args.modell, basis_url=args.basis_url, stapel=args.stapel
        )
        print(
            f"Modell: {args.modell} | Schätzung vorab: "
            f"{ZEICHEN_JE_TOKEN} Zeichen/Token, {PREIS_JE_MIO_TOKEN} $/1M Token"
        )

    ausgabe = args.ausgabe or _standard_ausgabe(archiv)
    print(f"Quelle : {quelle_db}")
    print(f"Ziel   : {ausgabe}")
    print(f"Archiv : {archiv or '(ohne — Quelldatei-Scan aus)'}")

    if args.nur_quelldatei:
        if not archiv:
            print("Für --nur-quelldatei wird das Archiv gebraucht (--archiv).")
            return 2
        quelldatei_nachtragen(ausgabe, archiv)
        return 0

    zaehler = baue_index(
        quelle_db=quelle_db,
        ausgabe=ausgabe,
        archiv_wurzel=archiv,
        einbetter=einbetter,
        stapel=args.stapel,
        limit=args.limit,
        ohne_quelldatei_scan=args.ohne_quelldatei_scan or not archiv,
    )
    print(bericht(zaehler))
    return 0


def _schluessel_holen() -> str:
    """Schluessel aus backend/.env, .env daneben oder der Umgebung. Nie ausgeben."""
    for pfad in (
        os.path.join(BACKEND, ".env"),
        os.path.join(os.path.dirname(BACKEND), ".env"),
    ):
        if not os.path.isfile(pfad):
            continue
        try:
            with open(pfad, encoding="utf-8") as f:
                for zeile in f:
                    if zeile.strip().startswith("OPENROUTER_API_KEY"):
                        wert = zeile.split("=", 1)[-1].strip().strip('"').strip("'")
                        if wert:
                            return wert
        except OSError:
            continue
    return (os.environ.get("OPENROUTER_API_KEY") or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
