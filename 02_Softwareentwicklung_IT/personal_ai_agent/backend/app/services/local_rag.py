"""
Lokale Embedding-Pipeline (Zero-Cloud RAG) fuer den Personal AI Agent.

Spezifikation Modul A (30.10.2026):
- 100 % lokale CPU-Vektorisierung ohne externe Cloud-APIs (kein OpenAI/Mistral).
- Nutzt fastembed (ONNX-basiert) mit Standardmodell:
  sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (~110 MB, 384 Dimensionen)
  oder alternative fastembed-Modelle.
- Bietet Chunking fuer Textdateien, Vektorisierung und Kosinus-Aehnlichkeitssuche.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Optional, Sequence, Union

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384


def kosinus_aehnlichkeit(a: Union[np.ndarray, Sequence[float]], b: Union[np.ndarray, Sequence[float]]) -> float:
    """Berechnet die Kosinus-Aehnlichkeit zweier Vektoren (Wertebereich -1.0 bis +1.0)."""
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


def text_chunking(
    text: str,
    chunk_groesse: int = 400,
    ueberlappung: int = 50,
) -> List[str]:
    """Zerlegt einen Text in Chunks mit optionaler Ueberlappung an Absatz-/Satzgrenzen."""
    if not text or not text.strip():
        return []

    bereinigt = text.strip()
    if len(bereinigt) <= chunk_groesse:
        return [bereinigt]

    # Primaer an doppelten Zeilenumbruechen (Absaetzen) trennen
    abschnitte = [a.strip() for a in bereinigt.split("\n\n") if a.strip()]
    chunks: List[str] = []
    aktueller_chunk = ""

    for abschnitt in abschnitte:
        if not aktueller_chunk:
            aktueller_chunk = abschnitt
        elif len(aktueller_chunk) + len(abschnitt) + 2 <= chunk_groesse:
            aktueller_chunk += "\n\n" + abschnitt
        else:
            chunks.append(aktueller_chunk)
            # Ueberlappung beruecksichtigen
            if ueberlappung > 0 and len(aktueller_chunk) > ueberlappung:
                aktueller_chunk = aktueller_chunk[-ueberlappung:] + "\n" + abschnitt
            else:
                aktueller_chunk = abschnitt

    if aktueller_chunk:
        chunks.append(aktueller_chunk)

    return chunks


class LocalRAG:
    """Lokale Embedding- und Retrieval-Engine auf Basis von fastembed."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        cache_dir: Optional[str] = None,
        threads: Optional[int] = None,
    ) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir or os.environ.get("FASTEMBED_CACHE_DIR")
        self.threads = threads
        self._model = None

    @property
    def model(self):
        """Laedt das Fastembed-Modell verzoegert beim ersten Zugriff."""
        if self._model is None:
            from fastembed import TextEmbedding

            kwargs: Dict[str, Any] = {"model_name": self.model_name}
            if self.cache_dir:
                kwargs["cache_dir"] = self.cache_dir
            if self.threads:
                kwargs["threads"] = self.threads

            logger.info("Initialisiere lokales FastEmbed-Modell: %s", self.model_name)
            self._model = TextEmbedding(**kwargs)
        return self._model

    def embed_texts(self, texts: Sequence[str], batch_size: int = 32) -> List[np.ndarray]:
        """Vektorisiert eine Sequenz von Texten rein lokal auf der CPU."""
        if not texts:
            return []
        embed_generator = self.model.embed(texts, batch_size=batch_size)
        return [np.asarray(e, dtype=np.float32) for e in embed_generator]

    def embed_query(self, query: str) -> np.ndarray:
        """Vektorisiert eine einzelne Suchanfrage."""
        ergebnis = self.embed_texts([query])
        if not ergebnis:
            return np.zeros(EMBEDDING_DIM, dtype=np.float32)
        return ergebnis[0]

    def embed_file(
        self,
        file_path: Union[str, Path],
        chunk_groesse: int = 400,
        ueberlappung: int = 50,
    ) -> List[Dict[str, Any]]:
        """Liest eine Datei ein, zerlegt sie in Chunks und berechnet lokale Embeddings."""
        pfad = Path(file_path)
        if not pfad.is_file():
            raise FileNotFoundError(f"Datei nicht gefunden: {pfad}")

        text = pfad.read_text(encoding="utf-8", errors="replace")
        chunks = text_chunking(text, chunk_groesse=chunk_groesse, ueberlappung=ueberlappung)
        if not chunks:
            return []

        vektoren = self.embed_texts(chunks)
        eintraege: List[Dict[str, Any]] = []
        for i, (chunk, vec) in enumerate(zip(chunks, vektoren)):
            eintraege.append({
                "chunk_index": i,
                "text": chunk,
                "embedding": vec,
                "source": str(pfad),
            })
        return eintraege

    def search(
        self,
        query: str,
        kandidaten: Sequence[Dict[str, Any]],
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Sucht aus vorberechneten Chunks die semantisch aehnlichsten Treffer heraus."""
        if not kandidaten:
            return []

        query_vec = self.embed_query(query)
        bewertungen: List[Dict[str, Any]] = []

        for k in kandidaten:
            vec = k.get("embedding")
            if vec is None:
                continue
            score = kosinus_aehnlichkeit(query_vec, vec)
            bewertungen.append({
                "chunk_index": k.get("chunk_index"),
                "text": k.get("text", ""),
                "source": k.get("source", ""),
                "score": round(score, 4),
            })

        bewertungen.sort(key=lambda x: x["score"], reverse=True)
        return bewertungen[:top_k]


def main() -> None:
    """CLI-Testfunktion fuer lokale Embeddings."""
    parser = argparse.ArgumentParser(description="Lokale FastEmbed-Vektorisierung")
    parser.add_argument("--file", help="Pfad zu einer Textdatei zum Vektorisieren")
    parser.add_argument("--query", help="Suchanfrage gegen die Chunks der Datei")
    parser.add_argument("--text", help="Einzelnen Text testen")
    args = parser.parse_args()

    rag = LocalRAG()

    if args.text:
        vec = rag.embed_query(args.text)
        print(f"Erfolg: Text vektorisiert. Vektordimension: {len(vec)}, Norm: {np.linalg.norm(vec):.4f}")

    if args.file:
        chunks = rag.embed_file(args.file)
        print(f"Datei {args.file} in {len(chunks)} Chunks zerlegt und lokal vektorisiert.")
        if args.query:
            results = rag.search(args.query, chunks, top_k=3)
            print(f"\nTop Treffer fuer '{args.query}':")
            for r in results:
                print(f"  [Score: {r['score']}] {r['text'][:120]}...")


if __name__ == "__main__":
    main()
