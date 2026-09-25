"""Simple JSON-based memory store (drop-in replacement for ChromaDB on ARM)."""

import json
import logging
import uuid
import os
import numpy as np
from datetime import datetime
from typing import List, Optional, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)


class SimpleMemoryStore:
    """File-based vector memory store using numpy + JSON.
    
    Drop-in replacement for ChromaDB that works on ARM/Android.
    Persists to a JSON file. Can be migrated to ChromaDB later.
    """

    def __init__(self):
        self.persist_dir = settings.chroma_persist_dir
        self.store_path = os.path.join(self.persist_dir, "memory_store.json")
        self._memories: List[Dict[str, Any]] = []
        self._loaded = False

    def connect(self) -> None:
        """Load or create the memory file."""
        os.makedirs(self.persist_dir, exist_ok=True)
        if os.path.exists(self.store_path):
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    self._memories = json.load(f)
                logger.info("Memory store loaded: %d items", len(self._memories))
            except Exception as e:
                logger.warning("Could not load memory store, starting fresh: %s", e)
                self._memories = []
        else:
            self._memories = []
            logger.info("Memory store created (empty)")
        self._loaded = True

    def count(self) -> int:
        """Number of stored items."""
        if not self._loaded:
            self.connect()
        return len(self._memories)

    def add_memory(
        self,
        content: str,
        embedding: Optional[List[float]] = None,
        category: str = "fakt",
        importance: int = 3,
        conversation_id: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        ereignis_datum: Optional[str] = None,
        wiederkehrend: bool = False,
    ) -> str:
        """Add a memory entry.

        ``history`` traegt die abgeloesten Fassungen (Korrekturen), siehe
        ``memory_service._loese_ab``. ``ereignis_datum`` (ISO) und
        ``wiederkehrend`` gehoeren zum Zeitbezug eines Termins. Fehlende
        Angaben sind ausdruecklich in Ordnung - ein Eintrag ohne Vektor oder
        ohne Datum ist weiterhin gueltig.
        """
        if not self._loaded:
            self.connect()
        memory_id = str(uuid.uuid4())
        entry: Dict[str, Any] = {
            "id": memory_id,
            "content": content,
            "category": category,
            "importance": importance,
            "timestamp": datetime.utcnow().isoformat(),
            "embedding": embedding,
            # Immer vorhanden (auch leer): Damit ist auf einen Blick klar,
            # dass es einen Verlauf gibt und nichts geloescht wird.
            "history": list(history or []),
        }
        if conversation_id:
            entry["conversation_id"] = conversation_id
        if ereignis_datum:
            entry["ereignis_datum"] = ereignis_datum
        if wiederkehrend:
            entry["wiederkehrend"] = True
        self._memories.append(entry)
        self._persist()
        logger.debug("Added memory: %s... (id=%s)", content[:50], memory_id)
        return memory_id

    def vektor_score(self, query_embedding: List[float]) -> Dict[str, float]:
        """Kosinus-Aehnlichkeit je Eintrag: ``{id: wert}``.

        Eintraege ohne Vektor fehlen im Ergebnis (der Aufrufer entscheidet,
        wie er sie ersatzweise bewertet). Vektoren mit anderer Laenge werden
        uebersprungen statt still falsch gerechnet: Zwei verschiedene
        Embedding-Modelle liefern nicht vergleichbare Vektoren, und numpy
        wuerde bei gemischten Laengen nicht einmal einen Fehler werfen.
        """
        if not self._loaded:
            self.connect()
        q = np.asarray(query_embedding, dtype=np.float32)
        q_norm = float(np.linalg.norm(q))
        if not q_norm:
            return {}

        ergebnis: Dict[str, float] = {}
        uebersprungen = 0
        for m in self._memories:
            vek = m.get("embedding")
            if not vek:
                continue
            if len(vek) != q.shape[0]:
                uebersprungen += 1
                continue
            v = np.asarray(vek, dtype=np.float32)
            v_norm = float(np.linalg.norm(v))
            if not v_norm:
                continue
            ergebnis[m["id"]] = float(np.dot(v, q) / (v_norm * q_norm))
        if uebersprungen:
            logger.warning(
                "%d Eintraege haben einen Vektor anderer Laenge (anderes "
                "Embedding-Modell) und wurden nicht bewertet.",
                uebersprungen,
            )
        return ergebnis

    def search_memories(
        self, query_embedding: List[float], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Cosine-similarity search over stored embeddings."""
        if not self._loaded:
            self.connect()
        if not self._memories:
            return []

        score = self.vektor_score(query_embedding)
        if not score:
            return []

        top_ids = sorted(score, key=lambda i: score[i], reverse=True)[:top_k]
        nach_id = {m["id"]: m for m in self._memories}
        results = []
        for memory_id in top_ids:
            m = nach_id[memory_id]
            results.append({
                "id": m["id"],
                "content": m["content"],
                "category": m.get("category", "fakt"),
                "importance": m.get("importance", 3),
                "timestamp": m.get("timestamp", ""),
                "distance": float(1.0 - score[memory_id]),
            })
        return results

    def aktualisiere_memory(self, memory_id: str, felder: Dict[str, Any]) -> bool:
        """Traegt Felder in einen vorhandenen Eintrag nach.

        Nur die uebergebenen Felder werden gesetzt - wer ``content`` nicht
        mitschickt, laesst ihn unberuehrt. Geloescht wird hier nie etwas;
        ``memory_service`` legt abgeloeste Fassungen in ``history`` ab.
        """
        if not self._loaded:
            self.connect()
        for m in self._memories:
            if m["id"] == memory_id:
                for schluessel, wert in felder.items():
                    if schluessel == "id":
                        continue
                    m[schluessel] = wert
                self._persist()
                return True
        return False


    def get_all_memories(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return stored memories (without embeddings)."""
        if not self._loaded:
            self.connect()
        return [
            {k: v for k, v in m.items() if k != "embedding"}
            for m in self._memories[-limit:]
        ]

    def eintraege_ohne_vektor(self) -> List[Dict[str, Any]]:
        """Eintraege, die noch nicht eingebettet sind - id und Inhalt."""
        if not self._loaded:
            self.connect()
        return [
            {"id": m["id"], "content": m.get("content", "")}
            for m in self._memories
            if not m.get("embedding")
        ]

    def setze_vektor(self, memory_id: str, embedding: List[float]) -> bool:
        """Traegt einen nachtraeglich berechneten Vektor ein."""
        if not self._loaded:
            self.connect()
        for m in self._memories:
            if m["id"] == memory_id:
                m["embedding"] = embedding
                self._persist()
                return True
        return False

    def delete_memory(self, memory_id: str) -> bool:
        """Remove a memory by ID."""
        if not self._loaded:
            self.connect()
        before = len(self._memories)
        self._memories = [m for m in self._memories if m["id"] != memory_id]
        if len(self._memories) < before:
            self._persist()
            return True
        return False

    def clear_all(self) -> None:
        """Delete all memories."""
        self._memories = []
        self._persist()
        logger.info("Memory store cleared")

    def _persist(self) -> None:
        """Write memory store to disk."""
        os.makedirs(self.persist_dir, exist_ok=True)
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(self._memories, f, indent=2, ensure_ascii=False)


# Singleton – same name as before, so imports stay compatible
chroma_client = SimpleMemoryStore()