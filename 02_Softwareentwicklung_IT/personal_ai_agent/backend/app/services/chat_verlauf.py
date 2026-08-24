"""Chat-Verlauf (aus chat.py extrahiert — Refactoring).

Hält die persistente Gesprächs-Historie (JSON neben dem Gedächtnis), mit einem
Lock gegen gleichzeitige Schreibzugriffe (Auftragsbuch/Stream-Thread).

Die Memory-Extraktion ist ein injizierbarer Callback (`setze_memory_extractor`),
damit dieser Service keine harten Imports auf llm/memory braucht und sich
isoliert testen lässt. chat.py verdrahtet den echten Extractor beim Start.
"""

import json
import logging
import os
import threading
from datetime import datetime
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Laufende Gespraeche im Speicher.
conversations: Dict[str, List[Dict]] = {}


def init(verlauf_datei: str, persist_dir: str) -> None:
    """Setzt den Speicherort + lädt den Verlauf. Vom Router beim Import gerufen."""
    global _verlauf_datei, _persist_dir, next_conversation_id
    _verlauf_datei = verlauf_datei
    _persist_dir = persist_dir
    next_conversation_id = 1
    conversations.clear()
    _lade_verlauf()


_verlauf_datei: str = ""
_persist_dir: str = ""
next_conversation_id: int = 1
_verlauf_sperre = threading.Lock()


def _lade_verlauf() -> None:
    """Holt die Gespraeche von der Platte. Fehlt die Datei, faengt es leer an."""
    global next_conversation_id
    try:
        with open(_verlauf_datei, "r", encoding="utf-8") as f:
            daten = json.load(f)
        conversations.update(daten.get("conversations", {}))
        next_conversation_id = int(daten.get("next_id", 1))
        logger.info("Gespraechsverlauf geladen: %d Gespraeche", len(conversations))
    except FileNotFoundError:
        logger.info("Kein gespeicherter Verlauf – erster Start")
    except Exception as e:
        logger.warning("Verlauf nicht lesbar, beginne leer: %s", e)


def _speichere_verlauf() -> None:
    """Schreibt den Verlauf weg. Fehler hier duerfen den Chat nicht abbrechen."""
    try:
        os.makedirs(_persist_dir, exist_ok=True)
        with open(_verlauf_datei, "w", encoding="utf-8") as f:
            json.dump(
                {"next_id": next_conversation_id, "conversations": conversations},
                f,
                ensure_ascii=False,
            )
    except Exception as e:
        logger.warning("Verlauf konnte nicht gespeichert werden: %s", e)


def verlauf_nachricht_anhaengen(conversation_id, role, content) -> None:
    """Haengt eine Agenten-Nachricht an ein Gespraech + schreibt weg.

    Verhalten identisch zur früheren chat.py-Funktion (ohne die Memory-Kopplung).
    """
    try:
        with _verlauf_sperre:
            if not conversation_id or conversation_id not in conversations:
                return
            if not content:
                return
            conversations[conversation_id].append(
                {
                    "role": role,
                    "content": content,
                    "zeit": datetime.now().astimezone().isoformat(timespec="seconds"),
                }
            )
            _speichere_verlauf()
    except Exception as e:
        logger.warning("Live-Nachricht nicht in Verlauf: %s", e)


def _get_or_create_conversation(conversation_id: Optional[str]) -> str:
    """Get existing conversation or create a new one."""
    global next_conversation_id
    if conversation_id and conversation_id in conversations:
        return conversation_id
    new_id = f"conv_{next_conversation_id}"
    next_conversation_id += 1
    conversations[new_id] = []
    return new_id


# Injizierbarer Memory-Extractor (setzt chat.py beim Start).
_memory_extractor: Optional[Callable] = None


def setze_memory_extractor(fn: Optional[Callable]) -> None:
    global _memory_extractor
    _memory_extractor = fn


def finish_exchange(conversation_id: str, user_message: str, reply: str) -> int:
    """Austausch in den Verlauf schreiben + Erinnerungen ableiten.

    Returns: Anzahl neuer Erinnerungen (0, wenn kein Extractor injiziert oder
    die Extraktion fehlschlägt).
    """
    if not reply:
        return 0
    history = conversations[conversation_id]
    with _verlauf_sperre:
        jetzt = datetime.now().astimezone().isoformat(timespec="seconds")
        history.append({"role": "user", "content": user_message, "zeit": jetzt})
        history.append({"role": "assistant", "content": reply, "zeit": jetzt})
        _speichere_verlauf()
    if _memory_extractor is None:
        return 0
    try:
        return len(_memory_extractor(
            user_message=user_message, llm_reply=reply, conversation_id=conversation_id
        ))
    except Exception as e:
        logger.warning("Gedächtnis-Extraktion fehlgeschlagen: %s", e)
        return 0