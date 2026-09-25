"""
Wissensspeicher-Suche: Hybridsuche auf dem Archiv-Index.

Was das hier ist
================

Sebastians Chat-Archive (ChatGPT, Gemini, Claude, Google) sind in einem
Index aufbereitet, den das Skript ``backend/scripts/archiv_index_bauen.py``
aus dem Schwesterprojekt ``Chats von GPT, GEMINI, Claude`` erzeugt. Dieser
Dienst liest **nur** — geschrieben wird ausschliesslich beim Bauen.

Gefunden wird auf zwei Wegen, die zusammen mehr taugen als jeder allein:

  **Volltext (FTS5)** findet Woerter. Exakte Begriffe, Eigennamen,
  Fachvokabular. Braucht kein Netz, keinen Schluessel, kostet nichts und
  antwortet in Millisekunden.

  **Vektoren** finden Bedeutung. "Was hat mich beruflich umgetrieben?" steht
  so in keinem Gespraech; trotzdem gibt es Dutzende dazu. Das findet nur die
  semantische Suche. Preis: ein Einbettungs-Aufruf je Frage (die Chunks sind
  laengst gerechnet). Dabei verlaesst **nur die Frage** das Geraet, niemals
  der gefundene Inhalt.

Zwei-Stufen-Suche: Treffer -> Original
======================================

Das ist Sebastians Kernwunsch (25.09.2026) und die wichtigste Eigenschaft
dieses Dienstes:

  Stufe 1 — **mathematischer Treffer**: Vektorvergleich bzw. Volltextfilter
  liefert *Fundstellen* (Chunks). Das ist eine Aehnlichkeitsrechnung, kein
  Beweis. Jeder Treffer traegt deshalb einen **Zeiger ins Original**:
  Quelldatei im Archiv, Chat-Kennung, Nachrichten-Ordinal, Datum, Titel.

  Stufe 2 — **Original nachlesen**: :meth:`ArchivSuche.original` liefert den
  **unveraenderten Originaltext** der Fundstelle samt Kontextfenster
  (eine Nachricht davor/danach). Es wird gelesen, nie umgeschrieben und nie
  zusammengefasst.

Die Reihenfolge ist bewusst so: erst rechnen, dann nachlesen. Der Treffer
zeigt *wo*, das Original sagt *was*.

Nie erfinden — unsicher heisst Rueckfrage
=========================================

Jedes Suchergebnis traegt ``sicher: true|false`` und einen ``grund``.
Bei ``sicher: false`` behauptet der Dienst **nichts**, sondern liefert die
gefundenen *Kandidaten* (mit Zeigern) und eine fertige Rueckfrage an
Sebastian. Seine Erinnerung ist die Wahrheitsquelle, das Archiv die Stuetze.
Die Schwellwerte stehen als Zahlen in den Konstanten unten und in
``docs/konzept-wissensspeicher.md`` — nachpruefbar, kein Bauchgefuehl.

Sicherheit
==========

  - Nur lesender Zugriff (``mode=ro``): Ein Tippfehler im Pfad legt sonst
    eine leere Datenbank an und die Suche liefert stumm null Treffer.
  - Die Inhalte bleiben auf dem Geraet. Nach aussen geht nur die Frage
    (Einbettung) — und auch die nur, wenn die semantische Suche laeuft.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import unicodedata
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import httpx
import numpy as np

logger = logging.getLogger(__name__)

# ── Schwellwerte (Zahlen, absichtlich hier oben und nicht versteckt) ────────
#
# Kosinus-Aehnlichkeit zweier Texte aus `openai/text-embedding-3-small`.
# Erfahrungswerte: sinngleiche Texte liegen typisch bei 0,45–0,75; thematisch
# verwandte bei 0,30–0,45; Unverwandtes deutlich darunter.
AEHNLICH_STARK = 0.45    # ab hier gilt ein Vektor-Treffer als belastbar
AEHNLICH_SCHWACH = 0.30  # darunter zaehlt er gar nicht mehr als Treffer

# Zwei belastbare Vektor-Treffer aus *verschiedenen* Gespraechen, deren
# Aehnlichkeit weniger als das auseinanderliegt, konkurrieren gleich stark.
# Das ist eine Naeherung fuer "mehrere widerspruechliche Fundstellen" — keine
# Wahrheit. Deshalb fuehrt genau dieser Fall zur Rueckfrage statt zur Antwort.
WETTBEWERB_ABSTAND = 0.03

# Wie viel Originaltext ein Treffer als Kurzfassung mitbringt. Nur fuer die
# Anzeige; das Original kommt ueber `original()` und ist ungekuerzt.
AUSSCHNITT_MAX = 400

# Wieviele Nachrichten Kontext `original()` standardmaessig mitliefert.
KONTEXT_STANDARD = 1

MODELLE_VOLLTEXT = ("volltext", "vektor", "hybrid")

# Woerter, die in einer FTS5-Anfrage nur Rauschen erzeugen.
STOPWORTE = {
    "der", "die", "das", "und", "oder", "aber", "ist", "sind", "war", "waren",
    "ein", "eine", "einen", "einem", "eines", "den", "dem", "des", "im", "in",
    "an", "auf", "fuer", "für", "mit", "von", "zu", "zum", "zur", "bei", "aus",
    "wie", "was", "wer", "wann", "wo", "warum", "welche", "welcher", "welches",
    "ich", "du", "er", "sie", "es", "wir", "ihr", "mir", "mich", "dir", "dich",
    "hab", "habe", "hatte", "haben", "hat", "kann", "koennen", "können",
    "nicht", "noch", "schon", "auch", "mal", "denn", "doch", "nur", "so",
    "mein", "meine", "meinen", "damals", "frueher", "früher", "alte", "alten",
}

MIN_LAENGE = 3

# ── Schemas des Index ──────────────────────────────────────────────────────
#
# Eine Datei, alles drin: Original-Nachrichten (zum Nachlesen), Chunks (die
# Fundstellen), FTS5-Volltextindex und die Vektoren als float16-Blobs.
# float16 statt float32 halbiert die Datei (95 statt 190 MB bei 30.891
# Chunks × 1536 Dimensionen); fuer eine Rangfolge reicht die Genauigkeit
# voellig, gerechnet wird danach in float32.
SCHEMA_SQL = """
CREATE TABLE meta (
    schluessel TEXT PRIMARY KEY,
    wert       TEXT
);

CREATE TABLE gespraeche (
    conversation_id    TEXT PRIMARY KEY,
    source             TEXT NOT NULL,
    title              TEXT,
    quelldatei         TEXT,
    von                TEXT,
    bis                TEXT,
    anzahl_nachrichten INTEGER NOT NULL DEFAULT 0,
    anzahl_chunks      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX gespraeche_zeit  ON gespraeche(von);
CREATE INDEX gespraeche_quelle ON gespraeche(source);

CREATE TABLE nachrichten (
    id              INTEGER PRIMARY KEY,   -- Ordinal: Zeile in normalized/messages.jsonl
    conversation_id TEXT NOT NULL,
    source          TEXT NOT NULL,
    timestamp       TEXT,
    role            TEXT NOT NULL,
    text            TEXT NOT NULL,
    title           TEXT,
    project         TEXT
);
CREATE INDEX nachrichten_gespraech ON nachrichten(conversation_id, id);
CREATE INDEX nachrichten_zeit      ON nachrichten(timestamp);

CREATE TABLE chunks (
    id              INTEGER PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    source          TEXT NOT NULL,
    text            TEXT NOT NULL,
    nachricht_ids   TEXT NOT NULL,          -- JSON-Liste, Rueckweg zu nachrichten
    beginn          TEXT,
    ende            TEXT,
    title           TEXT,
    project         TEXT,
    teil            INTEGER NOT NULL DEFAULT 0,
    quelldatei      TEXT,
    hat_vektor      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX chunks_zeit     ON chunks(beginn);
CREATE INDEX chunks_gespraech ON chunks(conversation_id);

CREATE VIRTUAL TABLE chunks_fts USING fts5(
    text,
    content='chunks',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TABLE vektoren (
    chunk_id  INTEGER PRIMARY KEY,
    dimension INTEGER NOT NULL,
    modell    TEXT,
    vektor    BLOB NOT NULL                 -- float16, Laenge = dimension * 2
);
"""

TABELLEN = (
    "meta", "gespraeche", "nachrichten", "chunks", "chunks_fts", "vektoren",
)

# Was im Ergebnis steht, wenn der Bedeutungs-Weg nicht traegt. Ein fehlender
# Hinweis waere hier die unehrlichste Variante: Die Suche wirkt vollstaendig,
# ist sie aber nicht. "aus" (bewusst nur Volltext gesucht) hat keinen Eintrag.
VEKTOR_HINWEIS = {
    "kein_vektorindex": (
        "Der Index enthält keine Vektoren — gesucht wurde nur nach Wortlaut. "
        "Sinngemäße Formulierungen können dadurch fehlen."
    ),
    "kein_schluessel": (
        "Kein Einbettungs-Schlüssel gesetzt (OPENROUTER_API_KEY) — gesucht "
        "wurde nur nach Wortlaut. Sinngemäße Formulierungen können fehlen."
    ),
    "einbettung_fehlgeschlagen": (
        "Die Suchfrage konnte nicht eingebettet werden (Netz oder Modell) — "
        "gesucht wurde nur nach Wortlaut. Ein zweiter Versuch kann helfen."
    ),
    "vektorfehler": (
        "Die Vektorsuche ist gescheitert — gesucht wurde nur nach Wortlaut."
    ),
    "lesefehler": (
        "Die Treffer ließen sich nicht auflösen — gesucht wurde nur nach Wortlaut."
    ),
}


# ── Hilfen ─────────────────────────────────────────────────────────────────
def _normalisiere(wort: str) -> str:
    """Wort auf die Form bringen, die auch FTS5 vergleicht.

    FTS5 laeuft mit ``remove_diacritics 2``: Umlaute und Akzente fallen weg.
    Wer Begriffe selbst zaehlen will, muss dieselbe Form herstellen — sonst
    gilt „frisör" als nicht gefunden, obwohl FTS5 es gefunden hat.
    """
    klein = (wort or "").lower()
    zerlegt = unicodedata.normalize("NFKD", klein)
    return "".join(c for c in zerlegt if not unicodedata.combining(c))


def ausschnitt(text: str, laenge: int = AUSSCHNITT_MAX) -> str:
    """Erste Zeilen eines Chunks, Whitespace geglaettet — nur zur Anzeige."""
    sauber = re.sub(r"\s+", " ", (text or "").strip())
    if len(sauber) <= laenge:
        return sauber
    return sauber[:laenge].rstrip() + " …"


def nachricht_ids(chunk_zeile: sqlite3.Row) -> List[int]:
    """Die Nachrichten-Ordinale eines Chunks, robust gegen kaputtes JSON."""
    try:
        roh = json.loads(chunk_zeile["nachricht_ids"] or "[]")
    except (TypeError, ValueError):
        return []
    return [int(x) for x in roh if isinstance(x, (int, float, str)) and str(x).lstrip("-").isdigit()]


def _datum_kurz(wert: Optional[str]) -> Optional[str]:
    """ISO-Zeitstempel auf den Tag kuerzen — Chroniken brauchen keine Uhrzeit."""
    return (wert or "")[:10] or None


class ArchivSuche:
    """Durchsucht den Archiv-Index (Hybrid) und liest Originale nach."""

    def __init__(
        self,
        pfad: Optional[str] = None,
        frage_einbetter: Optional[Callable[[str], Optional[Sequence[float]]]] = None,
    ):
        # Pfad injizierbar — Tests bauen sich einen winzigen Index im tmp_path
        # und fassen das echte Archiv nie an.
        #
        # `frage_einbetter` ist der Weg, die *Frage* in einen Vektor zu
        # verwandeln. Ohne Angabe laeuft er ueber OpenRouter; Tests geben eine
        # Attrappe hinein und brauchen so weder Netz noch Schluessel.
        self._pfad_ausdruecklich = pfad
        self._pfad_geprueft = False
        self._pfad: Optional[str] = None
        self._frage_einbetter = frage_einbetter
        self._vektoren_cache: Optional[Tuple[np.ndarray, np.ndarray]] = None
        self._vektoren_geprueft = False

    # ── Verfügbarkeit ────────────────────────────────────────────────────
    @property
    def pfad(self) -> Optional[str]:
        """Pfad zum Index, oder None wenn er nicht erreichbar ist."""
        if self._pfad_ausdruecklich is not None:
            return self._pfad_ausdruecklich if os.path.isfile(self._pfad_ausdruecklich) else None
        if not self._pfad_geprueft:
            self._pfad_geprueft = True
            for kandidat in self._pfad_kandidaten():
                if kandidat and os.path.isfile(kandidat):
                    self._pfad = kandidat
                    logger.info("Wissensspeicher-Index gefunden: %s", kandidat)
                    break
            else:
                logger.warning(
                    "Wissensspeicher-Index nicht gefunden (Kandidaten: %s)",
                    ", ".join(self._pfad_kandidaten()) or "keine",
                )
        return self._pfad

    @staticmethod
    def _pfad_kandidaten() -> List[str]:
        """Wo der Index liegen darf — in dieser Reihenfolge.

        ``settings.archiv_index_path`` (Standard in ``app/config.py``: der
        vorhandene Archivpfad ``Chats von GPT, GEMINI, Claude/db/archiv_index.db``;
        per ``.env`` überschreibbar) → Umgebungsvariable ``ARCHIV_INDEX_PATH``
        → übliche Ablageorte im Projekt → Handy-Pfade (Termux).

        Die Reihenfolge ist eine *Kandidatenliste*, keine Festlegung: Der erste
        Kandidat, der wirklich als Datei da ist, gewinnt. Ein gesetzter, aber
        nicht vorhandener Pfad fällt also ehrlich durch auf den nächsten —
        ``is_available`` wird dann ggf. False statt zu crashen.
        """
        kandidaten: List[str] = []
        try:
            from app.config import settings  # spaet importiert: Tests bleiben frei

            wert = getattr(settings, "archiv_index_path", "") or ""
            if wert.strip():
                kandidaten.append(wert.strip())
        except Exception:  # pragma: no cover - Settings sind immer da
            pass

        aus_umgebung = (os.environ.get("ARCHIV_INDEX_PATH") or "").strip()
        if aus_umgebung:
            kandidaten.append(aus_umgebung)

        hier = os.path.dirname(os.path.abspath(__file__))
        projekt = os.path.abspath(os.path.join(hier, "..", "..", ".."))
        kandidaten += [
            os.path.join(projekt, "archiv_index.db"),
            os.path.join(projekt, "backend", "archiv_index.db"),
            # Im Archivordner selbst: Dort ist er vor einem versehentlichen
            # Commit sicher (der Ordner steht in der .gitignore) und liegt
            # neben db/memory.db, aus dem er gebaut wird. Das Archiv liegt als
            # Geschwister von 02_Softwareentwicklung_IT, also zwei Ebenen über
            # dem Projektordner.
            os.path.abspath(
                os.path.join(projekt, "..", "..", "Chats von GPT, GEMINI, Claude",
                             "db", "archiv_index.db")
            ),
            # Handy (Termux), nach dem Verschieben per adb:
            "/sdcard/Download/archiv_index.db",
            "/data/data/com.termux/files/home/archiv_index.db",
        ]
        return kandidaten

    @property
    def is_available(self) -> bool:
        return self.pfad is not None

    def _ro(self) -> sqlite3.Connection:
        verbindung = sqlite3.connect(f"file:{self.pfad}?mode=ro", uri=True)
        verbindung.row_factory = sqlite3.Row
        return verbindung

    def _meta(self, db: sqlite3.Connection) -> Dict[str, str]:
        try:
            return {
                z["schluessel"]: z["wert"]
                for z in db.execute("SELECT schluessel, wert FROM meta")
            }
        except sqlite3.Error:
            return {}

    # ── Anfrage aufbereiten ──────────────────────────────────────────────
    @staticmethod
    def _fts_begriffe(frage: str) -> List[str]:
        """Die Suchbegriffe einer natuerlichen Frage herausziehen."""
        woerter = re.findall(r"[\wäöüßÄÖÜ]+", (frage or "").lower())
        return [w for w in woerter if len(w) >= MIN_LAENGE and w not in STOPWORTE][:12]

    @classmethod
    def _fts_anfrage(cls, frage: str) -> Optional[str]:
        """Aus einer natuerlichen Frage eine FTS5-Anfrage bauen.

        Ein rohes ``MATCH "Was hatte ich über TwinCAT gesagt?"`` waere ein
        Syntaxfehler. Deshalb: auf Wortstaemme reduzieren, Stoppwoerter weg,
        mit OR verbinden.
        """
        begriffe = cls._fts_begriffe(frage)
        if not begriffe:
            return None
        # Anführungszeichen um jeden Begriff: sonst stolpert FTS5 ueber
        # Woerter, die zufaellig wie Operatoren aussehen (etwa "near").
        return " OR ".join(f'"{w}"' for w in begriffe)

    @staticmethod
    def _passende_begriffe(text: str, begriffe: Sequence[str]) -> int:
        """Wie viele der Suchbegriffe stehen *wirklich* im Text?

        Notwendig, weil FTS5 die Begriffe mit **OR** verknuepft: Ein Chunk,
        der von fuenf Suchwoertern nur *eines* enthaelt, kaeme sonst als
        vollwertiger Treffer zurueck. Auf einem Bestand von 30.891 Chunks
        findet jedes beliebige Wort irgendetwas — ohne diese Zaehlung wirkte
        auch eine sinnfreie Anfrage „belastbar". Gezaehlt wird auf derselben
        Normalform, die FTS5 vergleicht.
        """
        if not begriffe:
            return 0
        im_text = {
            _normalisiere(w)
            for w in re.findall(r"[\wäöüßÄÖÜ]+", (text or "").lower())
        }
        gesucht = {_normalisiere(b) for b in begriffe}
        return len(im_text & gesucht)

    # ── Stufe 1a: Volltext ───────────────────────────────────────────────
    def volltext_suche(self, frage: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Nach Wortlaut suchen. Findet Eigennamen zuverlaessig.

        Ein Treffer gilt nur dann als **belastbar** (``stark``), wenn er
        mindestens zwei Suchbegriffe enthaelt — bei einer Ein-Wort-Anfrage
        genuegt naturgemaess der eine.
        """
        if not self.is_available:
            return []
        begriffe = self._fts_begriffe(frage)
        anfrage = self._fts_anfrage(frage)
        if not begriffe or not anfrage:
            return []
        try:
            with self._ro() as db:
                # bm25() ist FTS5s eingebaute Rangfolge: kleinere Werte sind
                # bessere Treffer. Ohne ORDER BY kaeme Einfuegereihenfolge.
                zeilen = db.execute(
                    """
                    SELECT c.*, bm25(chunks_fts) AS rang
                    FROM chunks_fts f
                    JOIN chunks c ON c.id = f.rowid
                    WHERE chunks_fts MATCH ?
                    ORDER BY bm25(chunks_fts)
                    LIMIT ?
                    """,
                    (anfrage, max(top_k * 4, 20)),
                ).fetchall()
        except sqlite3.Error as e:
            logger.warning("Volltextsuche fehlgeschlagen (%s): %s", anfrage[:60], e)
            return []

        noetig = min(2, len(begriffe))
        treffer: List[Tuple[int, float, Dict[str, Any]]] = []
        for z in zeilen:
            t = self._chunk_zu_treffer(z, weg="volltext")
            if not t:
                continue
            passend = self._passende_begriffe(z["text"], begriffe)
            t["passende_begriffe"] = passend
            t["stark"] = passend >= noetig
            treffer.append((passend, z["rang"], t))

        # Mehr passende Begriffe zuerst, bei Gleichstand die bm25-Rangfolge.
        treffer.sort(key=lambda x: (-x[0], x[1]))
        return [t for _, _, t in treffer][:top_k]

    # ── Frage einbetten (OpenRouter) ─────────────────────────────────────
    def _schluessel(self) -> str:
        try:
            from app.config import settings

            return (
                getattr(settings, "openrouter_api_key", "")
                or os.environ.get("OPENROUTER_API_KEY", "")
            ).strip()
        except Exception:  # pragma: no cover
            return (os.environ.get("OPENROUTER_API_KEY") or "").strip()

    def _modell(self) -> str:
        try:
            from app.config import settings

            return (getattr(settings, "openrouter_embed_model", "") or "openai/text-embedding-3-small").strip()
        except Exception:  # pragma: no cover
            return "openai/text-embedding-3-small"

    def _basis_url(self) -> str:
        try:
            from app.config import settings

            return (getattr(settings, "openrouter_base_url", "") or "https://openrouter.ai/api/v1").rstrip("/")
        except Exception:  # pragma: no cover
            return "https://openrouter.ai/api/v1"

    def frage_einbetten(self, frage: str) -> Optional[np.ndarray]:
        """Die Frage in einen Vektor verwandeln (OpenRouter).

        Nur die Frage verlaesst das Geraet — ein kurzer Satz, kein Archiv.
        Gibt None zurueck, wenn kein Schluessel da ist oder der Aufruf
        scheitert; die Suche faellt dann ehrlich auf Volltext zurueck.
        """
        if not (frage or "").strip():
            return None

        # Injizierter Weg (Tests): keine HTTP-Anfrage, kein Schluessel.
        if self._frage_einbetter is not None:
            try:
                roh = self._frage_einbetter(frage.strip())
                if roh is None:
                    return None
                vektor = np.asarray(roh, dtype=np.float32)
            except Exception as e:
                logger.warning("Frage-Einbettung (injiziert) fehlgeschlagen: %s", e)
                return None
            norm = float(np.linalg.norm(vektor))
            return vektor / norm if norm else None

        schluessel = self._schluessel()
        if not schluessel:
            return None
        try:
            antwort = httpx.post(
                f"{self._basis_url()}/embeddings",
                headers={"Authorization": f"Bearer {schluessel}"},
                json={"model": self._modell(), "input": [frage.strip()]},
                timeout=20,
            )
            antwort.raise_for_status()
            daten = antwort.json().get("data") or []
            if not daten:
                return None
            vektor = np.asarray(daten[0]["embedding"], dtype=np.float32)
            norm = float(np.linalg.norm(vektor))
            return vektor / norm if norm else None
        except Exception as e:
            logger.warning("Frage-Einbettung fehlgeschlagen: %s", e)
            return None

    def vektor_weg(self) -> str:
        """Ist der Bedeutungs-Weg begehbar — und wenn nicht, woran liegt es?

        Die Unterscheidung ist der Ehrlichkeit wegen da: "kein Vektor-Index"
        und "Frage liess sich nicht einbetten" fuehlen sich fuer den Nutzer
        gleich an, sind aber verschiedene Probleme, und nur eines davon
        verschwindet beim naechsten Versuch von selbst.
        """
        if self.vektoren is None:
            return "kein_vektorindex"
        if self._frage_einbetter is None and not self._schluessel():
            return "kein_schluessel"
        return "ok"

    # ── Vektoren laden ───────────────────────────────────────────────────
    @property
    def vektoren(self) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """``(chunk_ids, matrix)`` — Matrix als float16, oder None.

        95 MB bei vollem Archiv. Einmal geladen und behalten: Das Handy soll
        nicht bei jeder Frage 95 MB von der Karte lesen.
        """
        if self._vektoren_geprueft:
            return self._vektoren_cache
        self._vektoren_geprueft = True
        if not self.is_available:
            return None

        try:
            with self._ro() as db:
                zeilen = db.execute(
                    "SELECT chunk_id, dimension, vektor FROM vektoren ORDER BY chunk_id"
                ).fetchall()
        except sqlite3.Error as e:
            logger.warning("Vektoren nicht lesbar: %s", e)
            return None

        if not zeilen:
            return None

        dim = int(zeilen[0]["dimension"] or 0)
        if dim <= 0:
            return None
        try:
            ids = np.asarray([z["chunk_id"] for z in zeilen], dtype=np.int64)
            roh = b"".join(bytes(z["vektor"]) for z in zeilen)
            matrix = np.frombuffer(roh, dtype=np.float16)
            if matrix.size != ids.size * dim:
                logger.error(
                    "Vektorblob passt nicht zu %d Dimensionen (%d Werte, %d Zeilen)",
                    dim, matrix.size, ids.size,
                )
                return None
            matrix = matrix.reshape(-1, dim)
        except Exception as e:
            logger.error("Vektormatrix nicht aufbaubar: %s", e)
            return None

        # Normieren in float32, dann zurueck auf float16: Die Kosinus-Aehnlich-
        # keit ist damit das blosse Skalarprodukt — auf dem Handy zaehlt jede
        # gesparte Rechenoperation.
        try:
            in_f32 = matrix.astype(np.float32)
            normen = np.linalg.norm(in_f32, axis=1, keepdims=True)
            normen[normen == 0] = 1.0
            matrix = (in_f32 / normen).astype(np.float16)
        except Exception as e:
            logger.warning("Vektoren nicht normierbar (%s) — nutze sie roh", e)

        self._vektoren_cache = (ids, matrix)
        logger.info("Vektoren geladen: %s", (matrix.shape,))
        return self._vektoren_cache

    # ── Stufe 1b: Bedeutung ──────────────────────────────────────────────
    def semantische_suche(self, frage: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Nach Bedeutung suchen statt nach Wortlaut (nur die Treffer)."""
        return self._semantisch_mit_status(frage, top_k)[0]

    def _semantisch_mit_status(
        self, frage: str, top_k: int = 5
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Wie ``semantische_suche``, sagt aber *warum* nichts kam.

        Der Status wandert bis ins Suchergebnis: Der Agent soll unterscheiden
        koennen, ob das Archiv keine Vektoren hat (dann hilft nur Nachrechnen)
        oder ob gerade die Frage nicht eingebettet werden konnte (dann hilft
        ein zweiter Versuch).
        """
        status = self.vektor_weg()
        if status != "ok" or not self.is_available:
            return [], status
        geladen = self.vektoren
        if geladen is None:
            return [], "kein_vektorindex"
        ids, matrix = geladen
        frage_vektor = self.frage_einbetten(frage)
        if frage_vektor is None:
            return [], "einbettung_fehlgeschlagen"

        try:
            # Blockweise in float32: Die 95-MB-Matrix bleibt float16, nur der
            # gerade gerechnete Block wird breit. Das spart auf dem Handy
            # rund 100 MB Spitzenlast.
            n = matrix.shape[0]
            werte = np.empty(n, dtype=np.float32)
            block = 4096
            for start in range(0, n, block):
                ende = min(start + block, n)
                werte[start:ende] = matrix[start:ende].astype(np.float32) @ frage_vektor
        except Exception as e:
            logger.error("Vektorsuche fehlgeschlagen: %s", e)
            return [], "vektorfehler"

        # Kandidaten ueber der Schwelle, schlechteste vorher wegwerfen.
        gueltig = np.flatnonzero(werte >= AEHNLICH_SCHWACH)
        if gueltig.size == 0:
            return [], "ok"
        if gueltig.size > top_k:
            beste = gueltig[np.argpartition(-werte[gueltig], top_k - 1)[:top_k]]
        else:
            beste = gueltig
        beste = beste[np.argsort(-werte[beste])]

        treffer: List[Dict[str, Any]] = []
        try:
            with self._ro() as db:
                for stelle in beste:
                    zeile = db.execute(
                        "SELECT * FROM chunks WHERE id = ?", (int(ids[int(stelle)]),)
                    ).fetchone()
                    if zeile is None:
                        continue
                    t = self._chunk_zu_treffer(zeile, weg="vektor")
                    if t:
                        t["aehnlichkeit"] = round(float(werte[int(stelle)]), 4)
                        t["stark"] = t["aehnlichkeit"] >= AEHNLICH_STARK
                        treffer.append(t)
        except sqlite3.Error as e:
            logger.error("Treffer nicht aufloesbar: %s", e)
            return [], "lesefehler"

        logger.info("Vektorsuche '%s' → %d Treffer", (frage or "")[:50], len(treffer))
        return treffer, "ok"

    # ── Treffer bauen (immer MIT Zeiger) ─────────────────────────────────
    def _chunk_zu_treffer(self, zeile: sqlite3.Row, weg: str) -> Optional[Dict[str, Any]]:
        """Aus einer Chunk-Zeile einen Treffer mit Zeiger ins Original machen.

        Ein Treffer ohne Zeiger ist wertlos (Sebastian, 25.09.2026) — deshalb
        baut jeder Treffer seinen Zeiger mit, und was keinen bekommt, fliegt
        raus statt still als Volltext ohne Herkunft zu erscheinen.
        """
        ids = nachricht_ids(zeile)
        conversation_id = zeile["conversation_id"] or ""
        if not conversation_id or not ids:
            logger.warning(
                "Chunk %s ohne Zeiger (Gespraech/Ordinal fehlt) — verworfen",
                zeile["id"],
            )
            return None

        quelldatei = zeile["quelldatei"] or "normalized/messages.jsonl"
        return {
            "text": ausschnitt(zeile["text"]),
            "laenge": len(zeile["text"] or ""),
            "source": zeile["source"],
            "datum": _datum_kurz(zeile["beginn"]),
            "beginn": zeile["beginn"],
            "ende": zeile["ende"],
            "title": zeile["title"],
            "gefunden_ueber": weg,
            "stark": weg == "volltext",
            "aehnlichkeit": None,
            "passende_begriffe": None,
            # Der Zeiger ins Original — Stufe 2 holt damit den Volltext.
            "zeiger": {
                "quelldatei": quelldatei,
                "messages_jsonl": "normalized/messages.jsonl",
                "chat_kennung": conversation_id,
                "ordinal": ids[0],
                "ordinale": ids,
                "titel": zeile["title"],
                "datum": _datum_kurz(zeile["beginn"]),
            },
        }

    # ── Stufe 1: Hybrid + Urteil ─────────────────────────────────────────
    def hybrid(self, frage: str, top_k: int = 5, modus: str = "hybrid") -> Dict[str, Any]:
        """Beide Wege gehen, zusammenfuehren, zeitlich sortieren, ehrlich urteilen.

        Returns:
            Ein Ergebnis-Dict — nie eine nackte Trefferliste. Es traegt immer
            ``sicher``/``grund`` und bei Unsicherheit eine ``rueckfrage``.
        """
        if modus not in MODELLE_VOLLTEXT:
            modus = "hybrid"

        if not self.is_available:
            return self._ergebnis_ohne_index(frage)

        volltext_treffer = self.volltext_suche(frage, top_k * 2) if modus in ("volltext", "hybrid") else []
        if modus in ("vektor", "hybrid"):
            vektor_treffer, vektor_status = self._semantisch_mit_status(frage, top_k * 2)
        else:
            vektor_treffer, vektor_status = [], "aus"

        treffer = self._zusammenfuehren(volltext_treffer, vektor_treffer, top_k)

        # Zeitlich sortieren: Die Frage lautet "was war damals", also ist die
        # Chronologie die richtige Achse — nicht die Aehnlichkeit.
        treffer.sort(key=lambda t: (t["beginn"] or t["ende"] or "9999", t["zeiger"]["ordinal"]))

        vektor_weg_ok = vektor_status == "ok"
        urteil = self._urteilen(treffer, vektor_weg_ok)
        zeitraum, durchsucht = self._umfang()

        ergebnis: Dict[str, Any] = {
            "frage": frage,
            "modus": modus,
            "treffer": treffer,
            "anzahl": len(treffer),
            "sortierung": "zeit",
            "wege": {"volltext": True, "vektor": vektor_weg_ok, "vektor_status": vektor_status},
            "zeitraum": zeitraum,
            "durchsucht": durchsucht,
            **urteil,
        }
        hinweis = VEKTOR_HINWEIS.get(vektor_status)
        if hinweis:
            ergebnis["hinweis"] = hinweis
        logger.info(
            "Archivsuche '%s' → %d Treffer, sicher=%s (%s)",
            (frage or "")[:50], len(treffer), urteil["sicher"], urteil["grund"],
        )
        return ergebnis

    @staticmethod
    def _zusammenfuehren(
        volltext: Sequence[Dict[str, Any]],
        vektor: Sequence[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Doppelte raus, beide Wege angemessen beteiligt.

        Ohne festes Kontingent fuellt die semantische Suche alle Plaetze und
        der Volltext kommt nie zum Zug — dann fehlen genau die Eigennamen und
        Fachbegriffe, fuer die er da ist.
        """
        gesehen: Dict[Tuple[str, int], Dict[str, Any]] = {}

        def einreihen(liste: Sequence[Dict[str, Any]], hoechstens: int) -> int:
            genommen = 0
            for t in liste:
                schluessel = treffer_schluessel(t)
                if schluessel in gesehen:
                    # Schon da: den zweiten Weg vermerken statt doppelt zeigen.
                    vorhanden = gesehen[schluessel]
                    if t["gefunden_ueber"] not in vorhanden["gefunden_ueber"]:
                        vorhanden["gefunden_ueber"] += "+" + t["gefunden_ueber"]
                    if t.get("aehnlichkeit") is not None:
                        vorhanden["aehnlichkeit"] = t["aehnlichkeit"]
                        vorhanden["stark"] = vorhanden["stark"] or t["stark"]
                    continue
                gesehen[schluessel] = t
                genommen += 1
                if genommen >= hoechstens:
                    break
            return genommen

        haelfte = max(1, top_k // 2)
        genommen = einreihen(vektor, haelfte)
        genommen += einreihen(volltext, top_k - genommen)
        if genommen < top_k:
            einreihen(vektor, top_k - genommen)
        return list(gesehen.values())[:top_k]

    def _urteilen(self, treffer: Sequence[Dict[str, Any]], vektor_weg_ok: bool) -> Dict[str, Any]:
        """Sicher oder Rueckfrage — mit Zahl und Begruendung, nicht mit Gefuehl."""
        if not treffer:
            return {
                "sicher": False,
                "grund": "keine_treffer",
                "begruendung": (
                    "Zu dieser Frage gibt es im Archiv keinen Treffer — weder "
                    "nach Wortlaut noch nach Bedeutung."
                ),
                "rueckfrage": (
                    "Ich habe im Archiv nichts dazu gefunden. Kannst du dich "
                    "erinnern, ob und wann das war?"
                ),
                "kandidaten": 0,
            }

        starke = [t for t in treffer if t.get("stark")]
        if not starke:
            bestes = max((t.get("aehnlichkeit") or 0.0) for t in treffer)
            return {
                "sicher": False,
                "grund": "nur_schwache_aehnlichkeit",
                "begruendung": (
                    f"Nur schwache Fundstellen (beste Ähnlichkeit {bestes:.2f}, "
                    f"belastbar erst ab {AEHNLICH_STARK:.2f})."
                ),
                "rueckfrage": (
                    "Ich habe im Archiv nur vage Anklänge gefunden — nichts, "
                    "worauf ich mich festlegen würde. Kannst du dich erinnern, "
                    "wie das genau war?"
                ),
                "kandidaten": len(treffer),
                "beste_aehnlichkeit": round(bestes, 4),
            }

        # Widerspruch: zwei belastbare Vektor-Treffer aus verschiedenen
        # Gespraechen, praktisch gleich stark. Naeherung — deshalb Rueckfrage.
        vektor_starke = sorted(
            (t for t in starke if (t.get("aehnlichkeit") or 0) >= AEHNLICH_STARK),
            key=lambda t: -(t.get("aehnlichkeit") or 0),
        )
        if len(vektor_starke) >= 2:
            erste, zweite = vektor_starke[0], vektor_starke[1]
            if (
                erste["zeiger"]["chat_kennung"] != zweite["zeiger"]["chat_kennung"]
                and (erste["aehnlichkeit"] - zweite["aehnlichkeit"]) < WETTBEWERB_ABSTAND
            ):
                return {
                    "sicher": False,
                    "grund": "widerspruechliche_fundstellen",
                    "begruendung": (
                        "Zwei Fundstellen aus verschiedenen Gesprächen passen "
                        f"fast gleich gut ({erste['aehnlichkeit']:.2f} gegen "
                        f"{zweite['aehnlichkeit']:.2f}, Abstand unter "
                        f"{WETTBEWERB_ABSTAND:.2f}) — welche gemeint ist, ist offen."
                    ),
                    "rueckfrage": (
                        "Ich habe zwei Stellen gefunden, die beide passen könnten, "
                        "und kann nicht entscheiden, welche du meinst. Kannst du "
                        "die Erinnerung eingrenzen — Zeitraum oder Zusammenhang?"
                    ),
                    "kandidaten": len(treffer),
                }

        return {
            "sicher": True,
            "grund": "eindeutig",
            "begruendung": (
                f"{len(starke)} belastbare Fundstelle(n); keine konkurrierende "
                "Stelle mit gleich starker Ähnlichkeit."
            ),
            "rueckfrage": None,
            "kandidaten": len(treffer),
        }

    def _umfang(self) -> Tuple[Dict[str, Any], Dict[str, int]]:
        """Zeitraum und Umfang des Index — fuer die ehrliche Leermeldung."""
        if not self.is_available:
            return {}, {}
        try:
            with self._ro() as db:
                von, bis = db.execute(
                    "SELECT min(beginn), max(ende) FROM chunks"
                ).fetchone()
                chunks = db.execute("SELECT count(*) FROM chunks").fetchone()[0]
                gespraeche = db.execute("SELECT count(*) FROM gespraeche").fetchone()[0]
                nachrichten = db.execute("SELECT count(*) FROM nachrichten").fetchone()[0]
        except sqlite3.Error:
            return {}, {}
        return (
            {"von": von, "bis": bis},
            {"chunks": chunks, "gespraeche": gespraeche, "nachrichten": nachrichten},
        )

    def _ergebnis_ohne_index(self, frage: str) -> Dict[str, Any]:
        return {
            "frage": frage,
            "modus": "hybrid",
            "treffer": [],
            "anzahl": 0,
            "sortierung": "zeit",
            "wege": {"volltext": False, "vektor": False},
            "zeitraum": {},
            "durchsucht": {},
            "sicher": False,
            "grund": "kein_index",
            "begruendung": "Der Archiv-Index ist nicht erreichbar.",
            "rueckfrage": (
                "Ich habe gerade keinen Zugriff auf das Archiv — ich kann dazu "
                "nichts sagen und erfinde nichts. Kannst du dich erinnern?"
            ),
            "kandidaten": 0,
            "hinweis": "Archiv-Index nicht erreichbar.",
        }

    # ── Stufe 2: Original nachlesen ──────────────────────────────────────
    def original(
        self,
        chat_kennung: str,
        ordinal: int,
        kontext: int = KONTEXT_STANDARD,
    ) -> Dict[str, Any]:
        """Den **unveraenderten** Originaltext einer Fundstelle liefern.

        Das ist Stufe 2 der Zwei-Stufen-Suche: Der mathematische Treffer zeigt
        *wo*, hier wird nachgelesen *was*. Es wird nichts gekuerzt, nichts
        umgeschrieben, nichts zusammengefasst.

        Args:
            chat_kennung: ``conversation_id`` aus dem Zeiger.
            ordinal: ``Nachrichten-Ordinal`` aus dem Zeiger.
            kontext: Wie viele Nachrichten davor/danach mitkommen.
        """
        if not self.is_available:
            return {
                "gefunden": False,
                "grund": "kein_index",
                "hinweis": "Archiv-Index nicht erreichbar.",
            }
        try:
            ordinal = int(ordinal)
        except (TypeError, ValueError):
            return {"gefunden": False, "grund": "ordinal_ungueltig"}

        kontext = max(0, min(int(kontext or 0), 10))
        try:
            with self._ro() as db:
                fund = db.execute(
                    "SELECT * FROM nachrichten WHERE id = ? AND conversation_id = ?",
                    (ordinal, chat_kennung),
                ).fetchone()
                if fund is None:
                    return {
                        "gefunden": False,
                        "grund": "ordinal_unbekannt",
                        "hinweis": (
                            f"Zum Ordinal {ordinal} in Gespräch {chat_kennung} "
                            "steht nichts im Index."
                        ),
                    }
                davor = db.execute(
                    "SELECT * FROM nachrichten WHERE conversation_id = ? AND id < ? "
                    "ORDER BY id DESC LIMIT ?",
                    (chat_kennung, ordinal, kontext),
                ).fetchall()[::-1]
                danach = db.execute(
                    "SELECT * FROM nachrichten WHERE conversation_id = ? AND id > ? "
                    "ORDER BY id ASC LIMIT ?",
                    (chat_kennung, ordinal, kontext),
                ).fetchall()
                gespraech = db.execute(
                    "SELECT * FROM gespraeche WHERE conversation_id = ?",
                    (chat_kennung,),
                ).fetchone()
        except sqlite3.Error as e:
            logger.error("Original nicht lesbar: %s", e)
            return {"gefunden": False, "grund": "lesefehler", "hinweis": str(e)}

        def zeile(z: sqlite3.Row, ist_fundstelle: bool) -> Dict[str, Any]:
            # `text` wird durchgereicht wie gespeichert — kein strip(), keine
            # Kuerzung: Das Original ist das Original.
            return {
                "ordinal": z["id"],
                "role": z["role"],
                "timestamp": z["timestamp"],
                "text": z["text"],
                "ist_fundstelle": ist_fundstelle,
            }

        return {
            "gefunden": True,
            "chat_kennung": chat_kennung,
            "titel": fund["title"] or (gespraech["title"] if gespraech else None),
            "source": fund["source"],
            "datum": fund["timestamp"],
            "ordinal": fund["id"],
            "quelldatei": (gespraech["quelldatei"] if gespraech else None)
            or "normalized/messages.jsonl",
            "zeiger": {
                "quelldatei": (gespraech["quelldatei"] if gespraech else None)
                or "normalized/messages.jsonl",
                "messages_jsonl": "normalized/messages.jsonl",
                "chat_kennung": chat_kennung,
                "ordinal": fund["id"],
                "titel": fund["title"],
                "datum": _datum_kurz(fund["timestamp"]),
            },
            "kontext_vor": [zeile(z, False) for z in davor],
            "fundstelle": zeile(fund, True),
            "kontext_nach": [zeile(z, False) for z in danach],
            "unveraendert": True,
        }

    # ── Statistik ────────────────────────────────────────────────────────
    def statistik(self) -> Dict[str, Any]:
        """Anzahl Gespraeche/Nachrichten je Quelle, Zeitraum, Themen-Haeufigkeit."""
        if not self.is_available:
            return {"verfuegbar": False, "pfad": self._pfad_kandidaten()[:2]}
        try:
            with self._ro() as db:
                quellen = []
                for z in db.execute(
                    """
                    SELECT source,
                           count(*)                        AS gespraeche,
                           sum(anzahl_nachrichten)         AS nachrichten,
                           sum(anzahl_chunks)              AS chunks,
                           min(von)                        AS von,
                           max(bis)                        AS bis
                    FROM gespraeche
                    GROUP BY source
                    ORDER BY nachrichten DESC
                    """
                ):
                    quellen.append({
                        "source": z["source"],
                        "gespraeche": z["gespraeche"],
                        "nachrichten": z["nachrichten"],
                        "chunks": z["chunks"],
                        "von": z["von"],
                        "bis": z["bis"],
                    })
                gesamt = {
                    "gespraeche": db.execute("SELECT count(*) FROM gespraeche").fetchone()[0],
                    "nachrichten": db.execute("SELECT count(*) FROM nachrichten").fetchone()[0],
                    "chunks": db.execute("SELECT count(*) FROM chunks").fetchone()[0],
                    "vektoren": db.execute("SELECT count(*) FROM vektoren").fetchone()[0],
                }
                von, bis = db.execute("SELECT min(beginn), max(ende) FROM chunks").fetchone()
                # Themen aus den Gespraechstiteln: Der Titel ist die kuerzeste
                # ehrliche Zusammenfassung, die es gibt — er stammt aus dem
                # Export selbst, nicht aus einer Deutung.
                themen: Dict[str, int] = {}
                for (titel,) in db.execute("SELECT title FROM gespraeche WHERE title IS NOT NULL"):
                    for wort in re.findall(r"[\wäöüßÄÖÜ]{4,}", (titel or "").lower()):
                        if wort in STOPWORTE:
                            continue
                        themen[wort] = themen.get(wort, 0) + 1
                je_jahr = [
                    {"jahr": z[0], "gespraeche": z[1]}
                    for z in db.execute(
                        "SELECT substr(von,1,4) AS jahr, count(*) FROM gespraeche "
                        "WHERE von IS NOT NULL GROUP BY jahr ORDER BY jahr"
                    )
                ]
        except sqlite3.Error as e:
            logger.error("Statistik nicht lesbar: %s", e)
            return {"verfuegbar": False, "fehler": str(e)}

        return {
            "verfuegbar": True,
            "quellen": quellen,
            "gesamt": gesamt,
            "zeitraum": {"von": von, "bis": bis},
            "je_jahr": je_jahr,
            "themen_haeufigkeit": sorted(
                ({"thema": k, "anzahl": v} for k, v in themen.items()),
                key=lambda x: (-x["anzahl"], x["thema"]),
            )[:30],
            "hinweis_themen": (
                "Themen-Häufigkeit aus den Gesprächsttiteln der Exporte — "
                "keine Deutung."
            ),
        }

    # ── Chronik ──────────────────────────────────────────────────────────
    def chronik(self, richtung: str = "alt", limit: int = 10) -> Dict[str, Any]:
        """Aelteste oder neueste Gespraeche: Datum, Quelle, Titel, Zeiger."""
        if not self.is_available:
            return {"verfuegbar": False, "gespraeche": []}
        richtung = "neu" if str(richtung).lower() in ("neu", "neueste", "latest") else "alt"
        sortierung = "DESC" if richtung == "neu" else "ASC"
        limit = max(1, min(int(limit or 10), 200))
        try:
            with self._ro() as db:
                zeilen = db.execute(
                    f"""
                    SELECT conversation_id, source, title, quelldatei, von, bis,
                           anzahl_nachrichten, anzahl_chunks
                    FROM gespraeche
                    WHERE von IS NOT NULL
                    ORDER BY von {sortierung}, conversation_id
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                gesamt = db.execute("SELECT count(*) FROM gespraeche").fetchone()[0]
                von, bis = db.execute("SELECT min(von), max(bis) FROM gespraeche").fetchone()
        except sqlite3.Error as e:
            logger.error("Chronik nicht lesbar: %s", e)
            return {"verfuegbar": False, "fehler": str(e), "gespraeche": []}

        return {
            "verfuegbar": True,
            "richtung": richtung,
            "limit": limit,
            "gesamt_gespraeche": gesamt,
            "zeitraum": {"von": von, "bis": bis},
            "gespraeche": [
                {
                    "datum": _datum_kurz(z["von"]),
                    "bis": _datum_kurz(z["bis"]),
                    "source": z["source"],
                    "thema": z["title"],
                    "nachrichten": z["anzahl_nachrichten"],
                    "chunks": z["anzahl_chunks"],
                    "zeiger": {
                        "quelldatei": z["quelldatei"] or "normalized/messages.jsonl",
                        "chat_kennung": z["conversation_id"],
                        "titel": z["title"],
                        "datum": _datum_kurz(z["von"]),
                    },
                }
                for z in zeilen
            ],
        }

    # ── Bewusstsein: „was mein Agent weiss" ──────────────────────────────
    def ueberblick_kurz(self) -> str:
        """Der **kompakte** Bewusstseins-Baustein fuer jeden System-Prompt.

        Steht bei *jedem* Chat im Prompt — auch wenn die Suche nichts liefert.
        Nur so weiss der Agent, dass er ein Archiv hat (Sebastian, 25.09.2026:
        „Er weiss, er hat eine Wissensdatenbank — er muesste es wissen.").

        Eigenschaften, die der Test absichert:

          - **kurz**: Ziel <= 600 Zeichen (ein Prompt-Baustein, keine Prosa),
          - **nur Metadaten**: Zahlen, Quellen, Zeitraum und die Nutzungsregel —
            keine Gespraechsinhalte, keine Titel, keine Zitate,
          - **ehrlich**: ohne Einbettungs-Schluessel steht ausdruecklich dabei,
            dass nur nach Wortlaut gesucht wird.

        Fasst die Vektormatrix **nicht** an (auf dem Handy 95 MB) — geprueft
        wird nur, ob ein Schluessel da ist.
        """
        if not self.is_available:
            return (
                "WISSENSSPEICHER (persönliches Chat-Archiv): gerade NICHT "
                "angebunden. Zu Fragen nach früheren Gesprächen nichts behaupten "
                "— lieber nachfragen."
            )

        st = self.statistik()
        if not st.get("verfuegbar"):
            return (
                "WISSENSSPEICHER (persönliches Chat-Archiv): derzeit nicht lesbar. "
                "Zu Fragen nach früheren Gesprächen nichts behaupten — lieber "
                "nachfragen."
            )

        gesamt = st.get("gesamt", {})
        zeitraum = st.get("zeitraum", {})
        quellen_liste = [q for q in st.get("quellen", []) if q.get("gespraeche")]
        quellen = ", ".join(f"{q['source']} ({q['gespraeche']})" for q in quellen_liste[:8])
        if len(quellen_liste) > 8:
            quellen += f", +{len(quellen_liste) - 8} weitere"

        teile = [
            "WISSENSSPEICHER (persönliches Chat-Archiv): "
            f"{gesamt.get('gespraeche', 0)} Gespräche, "
            f"{gesamt.get('nachrichten', 0)} Nachrichten, "
            f"Zeitraum {_datum_kurz(zeitraum.get('von'))} bis "
            f"{_datum_kurz(zeitraum.get('bis'))}. "
            f"Quellen: {quellen or 'keine'}.",
            "NUTZUNG: Fragen zu meiner Vergangenheit/meinen Chats ZUERST hier "
            "suchen (Hybridsuche: Stichwort + Bedeutung) und den Treffer über "
            "seinen Zeiger als Original nachlesen — NICHT im Web, das weiß nichts "
            "davon. Bei unsicher (sicher=false) Rückfrage an Sebastian statt "
            "Behauptung.",
        ]
        # Ehrlicher Hinweis statt stillem Ausfall: Ohne Schluessel kann die
        # Frage nicht eingebettet werden, also findet nur der Wortlaut.
        if self._frage_einbetter is None and not self._schluessel():
            teile.append(
                "Bedeutungssuche aus: kein Schlüssel — nur Wortlaut."
            )
        return " ".join(teile)

    def ueberblick(self) -> Dict[str, Any]:
        """Kompakter Ueberblick ueber den Wissensspeicher — zum Einhaengen
        in den System-Prompt (siehe ``docs/konzept-wissensspeicher.md``).

        Zweck: Der Agent soll **wissen, dass er ein Archiv hat**, und bei
        Fragen der Form „was habe ich damals besprochen" zuerst hier suchen
        statt im Web. Enthaelt bewusst keine Inhalte, nur Kennzahlen und die
        Regeln — der Baustein darf bedenkenlos im Prompt stehen.
        """
        if not self.is_available:
            return {
                "vorhanden": False,
                "text": (
                    "WISSENSSPEICHER: Derzeit nicht angebunden. Zu Fragen nach "
                    "früheren Gesprächen kannst du nichts sagen — erfinde keine "
                    "Fundstellen."
                ),
                "regeln": _REGELN,
            }

        st = self.statistik()
        quellen = st.get("quellen", [])
        zeitraum = st.get("zeitraum", {})
        gesamt = st.get("gesamt", {})

        je_quelle = ", ".join(
            f"{q['source']} {q['gespraeche']}" for q in quellen if q.get("gespraeche")
        )
        themen = ", ".join(t["thema"] for t in st.get("themen_haeufigkeit", [])[:12])

        text = (
            "WISSENSSPEICHER (persönliches Chat-Archiv): "
            f"{gesamt.get('gespraeche', 0)} Gespräche, "
            f"{gesamt.get('nachrichten', 0)} Nachrichten, "
            f"Zeitraum {_datum_kurz(zeitraum.get('von'))} bis {_datum_kurz(zeitraum.get('bis'))}. "
            f"Quellen: {je_quelle or 'keine'}. "
            f"Häufige Themen: {themen or 'keine'}. "
            "NUTZUNG: Bei Fragen nach früheren Gesprächen, eigenen Entscheidungen, "
            "Erlebnissen oder „was habe ich damals gesagt“ ZUERST hier suchen "
            "(Hybridsuche: Stichwort + Bedeutung) — NICHT im Web. Das Web weiss "
            "nichts über dieses Archiv. Für Rückblicksfragen („was war ganz am "
            "Anfang / zu Beginn der Aufzeichnungen“) zuerst die CHRONIK ansehen "
            "(älteste Gespräche mit Datum und Titel) und von dort ins Original "
            "gehen — eine gewöhnliche Suche findet solche Meta-Fragen nicht "
            "zuverlässig. Ist die Suche unsicher (sicher=false), frage Sebastian "
            "nach seiner Erinnerung, statt eine Antwort zu behaupten."
        )

        return {
            "vorhanden": True,
            "gespraeche": gesamt.get("gespraeche", 0),
            "nachrichten": gesamt.get("nachrichten", 0),
            "chunks": gesamt.get("chunks", 0),
            "vektoren": gesamt.get("vektoren", 0),
            "zeitraum": zeitraum,
            "quellen": quellen,
            "je_quelle": je_quelle,
            "themenbereiche": [t["thema"] for t in st.get("themen_haeufigkeit", [])[:12]],
            "suchwege": {
                "volltext": True,
                "vektor": self.vektoren is not None and self._schluessel() != "",
            },
            "schwellwerte": {
                "stark_ab": AEHNLICH_STARK,
                "schwach_ab": AEHNLICH_SCHWACH,
                "wettbewerb_abstand": WETTBEWERB_ABSTAND,
            },
            "regeln": _REGELN,
            "text": text,
        }


# Regeln, die mit dem Ueberblick in den Prompt wandern. Kurz, imperativ,
# maschinenlesbar — ein Prompt-Baustein, keine Prosa.
_REGELN = {
    "zuerst_archiv": (
        "Fragen nach früheren Gesprächen/Erlebnissen/Entscheidungen zuerst im "
        "Wissensspeicher suchen, nicht im Web."
    ),
    "dann_original": (
        "Treffer sind Fundstellen, kein Beweis: über den Zeiger (chat_kennung + "
        "ordinal) das Original nachlesen, bevor etwas behauptet wird."
    ),
    "nie_erfinden": (
        "Bei sicher=false nichts behaupten. Die Kandidaten plus Rückfrage an "
        "Sebastian geben — seine Erinnerung ist die Wahrheitsquelle."
    ),
    "nichts_nach_aussen": (
        "Archivinhalte verlassen das Gerät nicht; nach außen geht nur die Frage "
        "zur Einbettung."
    ),
}


def treffer_schluessel(treffer: Dict[str, Any]) -> Tuple[str, int]:
    """Eindeutiger Schluessel eines Treffers fuer die Dublettenpruefung.

    Bewusst *beides* — Chat-Kennung und Ordinal: Zwei Gespraeche koennten
    sonst ueber dieselbe Ordnungszahl zusammenfallen.
    """
    zeiger = treffer["zeiger"]
    return (str(zeiger["chat_kennung"]), int(zeiger["ordinal"]))


# Ein Dienst fuer die Anwendung. Der Pfad kommt aus den Settings oder der
# Umgebungsvariablen; Tests bauen sich mit `ArchivSuche(pfad=...)` einen
# eigenen — das echte Archiv wird in Tests nie angefasst.
archiv_suche = ArchivSuche()


def prompt_baustein(kurz: bool = False) -> str:
    """Fertiger Text fuer den System-Prompt.

    ``kurz=True`` liefert die **kompakte** Fassung (<= 600 Zeichen, nur
    Metadaten, siehe :meth:`ArchivSuche.ueberblick_kurz`) — die steht bei
    jedem Chat im Prompt (Einbauort: ``llm_service._build_messages``).
    Ohne Argument kommt die ausfuehrliche Fassung.

    Bewusst eine Funktion und kein Modul-Level-String: Der Ueberblick wird zur
    Laufzeit gebildet, damit er den aktuellen Index beschreibt.
    """
    if kurz:
        return archiv_suche.ueberblick_kurz()
    return archiv_suche.ueberblick()["text"]
