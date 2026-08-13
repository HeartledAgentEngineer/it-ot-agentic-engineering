"""
Zugriff auf den persoenlichen Wissensspeicher (Chat-Archive).

Die Datenbank entsteht im Schwesterprojekt `Chats von GPT, GEMINI, Claude`
und wird hier nur **gelesen**. Geschrieben wird dort, nie hier — deshalb
oeffnet dieser Dienst sie ausdruecklich schreibgeschuetzt.

Zwei Suchwege, die zusammen mehr taugen als jeder allein:

  **Volltext (FTS5)** findet Woerter. Exakte Begriffe, Eigennamen,
  Fachvokabular — "TwinCAT", "Fabia", "Bildungsgutschein". Braucht kein Netz,
  keinen Schluessel, kostet nichts und antwortet in Millisekunden.

  **Vektoren** finden Bedeutung. "Was hat mich beruflich umgetrieben?" steht
  so in keinem Gespraech; trotzdem gibt es Dutzende dazu. Das findet nur die
  semantische Suche. Preis: ein Mistral-Aufruf je Frage, um die Frage selbst
  einzubetten (die Chunks sind laengst gerechnet).

  Beides zusammengefuehrt ist als "Hybrid Search" der uebliche Weg in
  ernsthaften RAG-Systemen. Vektoren allein verfehlen zuverlaessig genau die
  Eigennamen, nach denen man oft sucht; Volltext allein verfehlt alles, was
  man umschreibt statt zu benennen.

Faellt ein Weg aus — kein Schluessel, keine Vektordatei, kein Netz —, liefert
der andere weiter. Die Suche wird dann schlechter, aber nie leer.

Sicherheit:
  - Nur lesender Zugriff (`mode=ro`)
  - Die Datenbank enthaelt persoenliche Gespraeche. Sie verlaesst das Geraet
    nicht; nur die wenigen Treffer wandern in den Prompt. Bei aktiver
    Vektorsuche verlaesst allerdings die **Frage** das Geraet (an Mistral),
    nicht aber der gefundene Inhalt.
"""

import logging
import os
import re
import sqlite3
from typing import Any, Dict, List, Optional

import httpx
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

# Woerter, die in einer FTS5-Anfrage nur Rauschen erzeugen. Bewusst kurz
# gehalten: Zu viel Filtern kostet Treffer, zu wenig kostet Genauigkeit.
STOPWORTE = {
    "der", "die", "das", "und", "oder", "aber", "ist", "sind", "war", "waren",
    "ein", "eine", "einen", "einem", "eines", "den", "dem", "des", "im", "in",
    "an", "auf", "fuer", "für", "mit", "von", "zu", "zum", "zur", "bei", "aus",
    "wie", "was", "wer", "wann", "wo", "warum", "welche", "welcher", "welches",
    "ich", "du", "er", "sie", "es", "wir", "ihr", "mir", "mich", "dir", "dich",
    "hab", "habe", "hatte", "haben", "hat", "kann", "koennen", "können",
    "nicht", "noch", "schon", "auch", "mal", "denn", "doch", "nur", "so",
}

MIN_LAENGE = 3


class ArchivService:
    """Durchsucht den Wissensspeicher per Volltext."""

    def __init__(self):
        self._pfad: Optional[str] = None
        self._geprueft = False
        self._vektoren: Optional[np.ndarray] = None
        self._vektoren_geprueft = False

    # ── Verfügbarkeit ────────────────────────────────────────────────────
    @property
    def pfad(self) -> Optional[str]:
        """Pfad zur Datenbank, oder None wenn sie nicht erreichbar ist."""
        if not self._geprueft:
            roh = (settings.archiv_db_path or "").strip()
            if roh and os.path.isfile(roh):
                self._pfad = roh
                logger.info("Wissensspeicher gefunden: %s", roh)
            elif roh:
                logger.warning("Wissensspeicher nicht gefunden unter: %s", roh)
            self._geprueft = True
        return self._pfad

    @property
    def is_available(self) -> bool:
        return self.pfad is not None

    def _verbindung(self) -> sqlite3.Connection:
        # mode=ro statt einfachem connect(): Ein Tippfehler im Pfad legt sonst
        # eine leere Datenbank an, und die Suche liefert stumm null Treffer –
        # statt zu sagen, dass die Datei fehlt.
        return sqlite3.connect(f"file:{self.pfad}?mode=ro", uri=True)

    # ── Anfrage aufbereiten ──────────────────────────────────────────────
    @staticmethod
    def _fts_anfrage(frage: str) -> Optional[str]:
        """Aus einer natuerlichen Frage eine FTS5-Anfrage bauen.

        Die Frage kommt aus dem Chat und enthaelt Satzzeichen und Fuellwoerter,
        mit denen FTS5 nichts anfangen kann – ein rohes `match "Was hatte ich
        über TwinCAT gesagt?"` waere sogar ein Syntaxfehler. Deshalb: auf
        Wortstaemme reduzieren, Stoppwoerter weg, mit OR verbinden.
        """
        woerter = re.findall(r"[\wäöüßÄÖÜ]+", frage.lower())
        begriffe = [
            w for w in woerter
            if len(w) >= MIN_LAENGE and w not in STOPWORTE
        ]
        if not begriffe:
            return None
        # Anführungszeichen um jeden Begriff: sonst stolpert FTS5 über
        # Wörter, die zufällig wie Operatoren aussehen (etwa "near").
        return " OR ".join(f'"{w}"' for w in begriffe[:12])

    # ── Suche ────────────────────────────────────────────────────────────
    def suche(self, frage: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Passende Ausschnitte aus dem Archiv finden.

        Returns:
            Liste mit `text`, `source`, `beginn`, `title` – oder leer, wenn
            die Datenbank fehlt oder nichts passt.
        """
        if not self.is_available:
            return []

        anfrage = self._fts_anfrage(frage)
        if not anfrage:
            return []

        try:
            with self._verbindung() as db:
                db.row_factory = sqlite3.Row
                # bm25() ist FTS5s eingebaute Rangfolge: kleinere Werte sind
                # bessere Treffer. Ohne ORDER BY käme die Reihenfolge der
                # Einfügung zurück, also praktisch Zufall.
                zeilen = db.execute(
                    """
                    SELECT c.text, c.source, c.beginn, c.title, c.conversation_id
                    FROM chunks_fts f
                    JOIN chunks c ON c.id = f.rowid
                    WHERE chunks_fts MATCH ?
                    ORDER BY bm25(chunks_fts)
                    LIMIT ?
                    """,
                    (anfrage, top_k),
                ).fetchall()
        except sqlite3.OperationalError as e:
            # Trotz Aufbereitung kann die Anfrage FTS5 nicht schmecken.
            # Kein Grund, den Chat scheitern zu lassen.
            logger.warning("Archivsuche fehlgeschlagen (%s): %s", anfrage[:60], e)
            return []
        except Exception as e:
            logger.error("Archivsuche unerwartet fehlgeschlagen: %s", e)
            return []

        treffer = [
            {
                "text": z["text"],
                "source": z["source"],
                "beginn": z["beginn"],
                "title": z["title"],
                "conversation_id": z["conversation_id"],
            }
            for z in zeilen
        ]
        logger.info("Archivsuche '%s' → %d Treffer", frage[:50], len(treffer))
        return treffer

    # ── Semantische Suche ────────────────────────────────────────────────
    @property
    def vektoren(self) -> Optional[np.ndarray]:
        """Die Chunk-Vektoren als (n, 1024)-Matrix, oder None.

        Wird per ``memmap`` geoeffnet: Die Datei ist 120 MB, und auf einem
        Handy will man die nicht am Stueck in den Arbeitsspeicher heben. So
        liest das Betriebssystem nur die Seiten, die tatsaechlich gebraucht
        werden.
        """
        if self._vektoren is not None or self._vektoren_geprueft:
            return self._vektoren
        self._vektoren_geprueft = True

        pfad = (settings.archiv_vektor_path or "").strip()
        if not pfad or not os.path.isfile(pfad):
            if pfad:
                logger.warning("Vektordatei nicht gefunden: %s", pfad)
            return None

        try:
            roh = np.memmap(pfad, dtype=np.float32, mode="r")
            dim = 1024  # steht als index_meta.dimension in der Datenbank
            if roh.size % dim:
                logger.error(
                    "Vektordatei passt nicht zu %d Dimensionen (%d Werte)",
                    dim, roh.size,
                )
                return None
            self._vektoren = roh.reshape(-1, dim)
            logger.info("Vektoren geladen: %s", self._vektoren.shape)
        except Exception as e:
            logger.error("Vektordatei nicht lesbar: %s", e)
        return self._vektoren

    def _frage_einbetten(self, frage: str) -> Optional[np.ndarray]:
        """Die Frage bei Mistral in einen Vektor verwandeln.

        Nur die Frage verlaesst das Geraet – ein kurzer Satz, kein Archiv.
        """
        schluessel = (settings.mistral_api_key or "").strip()
        if not schluessel:
            return None
        try:
            antwort = httpx.post(
                "https://api.mistral.ai/v1/embeddings",
                headers={"Authorization": f"Bearer {schluessel}"},
                json={"model": settings.mistral_embed_model, "input": [frage]},
                timeout=15,
            )
            antwort.raise_for_status()
            vek = np.asarray(antwort.json()["data"][0]["embedding"], dtype=np.float32)
            norm = np.linalg.norm(vek)
            return vek / norm if norm else None
        except Exception as e:
            logger.warning("Frage-Einbettung fehlgeschlagen: %s", e)
            return None

    def semantische_suche(self, frage: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Nach Bedeutung suchen statt nach Wortlaut."""
        matrix = self.vektoren
        if matrix is None or not self.is_available:
            return []
        frage_vek = self._frage_einbetten(frage)
        if frage_vek is None:
            return []

        # Die gespeicherten Vektoren sind bereits normiert, deshalb genuegt
        # das Skalarprodukt – die Kosinus-Aehnlichkeit ohne die Division.
        try:
            aehnlich = matrix @ frage_vek
            # argpartition statt argsort: Wir brauchen die besten k, nicht
            # eine vollstaendige Sortierung von 30.891 Werten.
            k = min(top_k, aehnlich.shape[0])
            beste = np.argpartition(-aehnlich, k - 1)[:k]
            beste = beste[np.argsort(-aehnlich[beste])]
        except Exception as e:
            logger.error("Vektorsuche fehlgeschlagen: %s", e)
            return []

        # Zeile n der Matrix gehoert zum n-ten Chunk mit Vektor, nach id
        # geordnet – so hat das Schwesterprojekt sie geschrieben.
        try:
            with self._verbindung() as db:
                db.row_factory = sqlite3.Row
                ids = [
                    z[0] for z in db.execute(
                        "SELECT id FROM chunks WHERE hat_vektor = 1 ORDER BY id"
                    )
                ]
                if len(ids) != matrix.shape[0]:
                    logger.error(
                        "Vektoren (%d) und Chunks mit Vektor (%d) passen nicht zusammen",
                        matrix.shape[0], len(ids),
                    )
                    return []
                treffer = []
                for zeile in beste:
                    z = db.execute(
                        "SELECT text, source, beginn, title, conversation_id "
                        "FROM chunks WHERE id = ?",
                        (ids[int(zeile)],),
                    ).fetchone()
                    if z:
                        treffer.append({
                            "text": z["text"],
                            "source": z["source"],
                            "beginn": z["beginn"],
                            "title": z["title"],
                            "conversation_id": z["conversation_id"],
                            "aehnlichkeit": round(float(aehnlich[zeile]), 4),
                        })
        except Exception as e:
            logger.error("Treffer nicht aufloesbar: %s", e)
            return []

        logger.info("Vektorsuche '%s' → %d Treffer", frage[:50], len(treffer))
        return treffer

    def hybrid(self, frage: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Beide Wege gehen und die Ergebnisse zusammenfuehren.

        Volltext faengt Eigennamen und Fachbegriffe, Vektoren fangen
        Umschreibungen. Faellt ein Weg aus, traegt der andere allein.
        Doppelte Treffer fliegen ueber den Text-Anfang raus.
        """
        k = top_k or settings.archiv_top_k
        gesehen = set()

        def neue(liste: List[Dict[str, Any]], hoechstens: int) -> List[Dict[str, Any]]:
            raus = []
            for t in liste:
                schluessel = (t.get("text") or "")[:120]
                if schluessel and schluessel not in gesehen:
                    gesehen.add(schluessel)
                    raus.append(t)
                    if len(raus) >= hoechstens:
                        break
            return raus

        # Beide Wege bekommen ein festes Kontingent. Ohne das fuellt die
        # semantische Suche alle Plaetze, und der Volltext kommt nie zum Zug –
        # dann fehlen genau die Eigennamen und Fachbegriffe, fuer die er da ist.
        haelfte = max(1, k // 2)
        semantisch = neue(self.semantische_suche(frage, k), haelfte)
        volltext = neue(self.suche(frage, k), k - len(semantisch))

        # Faellt ein Weg aus, fuellt der andere die freien Plaetze auf.
        gefunden = semantisch + volltext
        if len(gefunden) < k:
            gefunden += neue(self.semantische_suche(frage, k), k - len(gefunden))

        return gefunden[:k]

    # ── Kennzahlen ───────────────────────────────────────────────────────
    def status(self) -> Dict[str, Any]:
        """Was steckt im Archiv? Fuer Anzeige und Fehlersuche."""
        if not self.is_available:
            return {"verfuegbar": False, "pfad": settings.archiv_db_path or None}

        try:
            with self._verbindung() as db:
                chunks = db.execute("SELECT count(*) FROM chunks").fetchone()[0]
                nachrichten = db.execute("SELECT count(*) FROM messages").fetchone()[0]
                quellen = {
                    zeile[0]: zeile[1]
                    for zeile in db.execute(
                        "SELECT source, count(*) FROM chunks GROUP BY source ORDER BY 2 DESC"
                    )
                }
                zeitraum = db.execute("SELECT min(beginn), max(ende) FROM chunks").fetchone()
        except Exception as e:
            logger.error("Archiv-Status nicht lesbar: %s", e)
            return {"verfuegbar": False, "fehler": str(e)}

        return {
            "verfuegbar": True,
            "chunks": chunks,
            "nachrichten": nachrichten,
            "quellen": quellen,
            "von": zeitraum[0],
            "bis": zeitraum[1],
            # Beide Wege einzeln ausweisen: Fehlt einer, sucht der Agent
            # schlechter – und man soll sehen, warum.
            "volltext": True,
            "semantisch": self.vektoren is not None and bool(settings.mistral_api_key),
            "vektoren_geladen": self.vektoren is not None,
            "schluessel_vorhanden": bool((settings.mistral_api_key or "").strip()),
        }


archiv_service = ArchivService()
