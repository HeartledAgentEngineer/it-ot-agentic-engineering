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
from typing import Callable, Dict, List, Optional, Any

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
    """Holt die Gespraeche von der Platte. Fehlt die Datei, faengt es leer an.

    Datenverlust-Schutz (Stand 2026-08-30, erneuter Vorfall): Wurde die
    Verlaufsdatei von einem Server mit leerem/kaum gefuelltem Stand
    ueberschrieben (z. B. ein zweiter uvicorn startet waehrend ein anderer
    schreibt), soll der Start NICHT mit dem leeren Stand weiterlaufen und ihn
    bei der naechsten Speicherung erneut festschreiben. Deshalb: Ist der
    geladene Stand ohne jegliche Nachrichten, wird stattdessen der juengste
    nicht-leere Rotations-Backup uebernommen (falls vorhanden).
    """
    global next_conversation_id
    try:
        with open(_verlauf_datei, "r", encoding="utf-8") as f:
            daten = json.load(f)
        conversations.update(daten.get("conversations", {}))
        summarys.update(daten.get("summarys", {}))
        next_conversation_id = int(daten.get("next_id", 1))
        logger.info("Gespraechsverlauf geladen: %d Gespraeche", len(conversations))

        # Leerer Stand? Dann aus dem juengsten nicht-leeren Backup restauen,
        # statt leer weiterzumachen (sonst wuerde der leere Stand die Datei
        # beim naechsten Save erneut ueberschreiben).
        if not conversations or not any(
            msgs for msgs in conversations.values() if msgs
        ):
            from_backup = _lade_juengstes_nicht_leeres_backup()
            if from_backup is not None:
                conversations.clear()
                conversations.update(from_backup[0])
                summarys.clear()
                summarys.update(from_backup[1])
                next_conversation_id = int(from_backup[2])
                logger.warning(
                    "Verlauf war leer, juengstes nicht-leeres Backup geladen: "
                    "%d Gespraeche", len(conversations)
                )
    except FileNotFoundError:
        logger.info("Kein gespeicherter Verlauf – erster Start")
    except Exception as e:
        logger.warning("Verlauf nicht lesbar, beginne leer: %s", e)


def _lade_juengstes_nicht_leeres_backup():
    """Liefert (conversations, summarys, next_id) des juengsten Backups mit
    Inhalt, oder None, wenn keins passt."""
    for bkp in _rotierte_backups():
        try:
            with open(bkp, "r", encoding="utf-8") as f:
                daten = json.load(f)
        except Exception:
            continue
        convs = daten.get("conversations", {})
        if not convs or not any(msgs for msgs in convs.values() if msgs):
            continue
        return (
            convs,
            daten.get("summarys", {}),
            daten.get("next_id", 1),
        )
    return None


# Wie viele Rotations-Backups des Verlaufs neben der Hauptdatei gehalten werden.
# Jeder Save sichert VOR dem Ueberschreiben den aktuellen Stand in eine
# Zeitstempel-Backup-Datei. Tritt Datenverlust auf (z. B. ein Server mit leerem
# Verlauf ueberschreibt die Datei), kann der letzte intakte Stand daraus
# zurueckgeholt werden.
_BACKUP_ROTATION = 5


def _rotierte_backups() -> list:
    """Bestehende Zeitstempel-Backups der Verlaufsdatei (neueste zuerst)."""
    import glob
    try:
        return sorted(
            (p for p in glob.glob(_verlauf_datei + ".bak-*") if os.path.getsize(p) > 0),
            key=os.path.getmtime,
            reverse=True,
        )
    except Exception:
        return []


def _speichere_verlauf() -> None:
    """Schreibt den Verlauf weg. Fehler hier duerfen den Chat nicht abbrechen.

    Datenverlust-Schutz (Stand 2026-08-30, conv_8-Vorfall): Vor jedem
    Ueberschreiben wird der aktuelle Plattenstand in eine Zeitstempel-Backup-
    Datei kopiert (Rotation, max. _BACKUP_ROTATION). Das Schreiben selbst ist
    atomar (Temp-Datei + os.replace), damit ein Crash nie eine halb geschriebene
    Datei hinterlaesst. Damit ist selbst dann, wenn ein Server mit leerem/kaum
    gefuelltem Verlauf die Datei ueberschreibt, der alte Zustand aus dem
    Backup wiederherstellbar.
    """
    try:
        os.makedirs(_persist_dir, exist_ok=True)
        # 1) Aktuellen Plattenstand sichern, bevor wir ihn ersetzen.
        if os.path.exists(_verlauf_datei):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            bkp = f"{_verlauf_datei}.bak-{ts}"
            try:
                import shutil
                shutil.copy2(_verlauf_datei, bkp)
            except Exception:
                pass  # Backup-Fehler darf das Speichern nicht blockieren
            # Rotation: aeltere Backups begrenzen.
            for alt in _rotierte_backups()[_BACKUP_ROTATION:]:
                try:
                    os.remove(alt)
                except Exception:
                    pass
        # 2) Atomar schreiben (Temp-Datei + replace) — nie halb geschrieben.
        tmp = _verlauf_datei + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                {"next_id": next_conversation_id, "conversations": conversations,
                 "summarys": summarys},
                f,
                ensure_ascii=False,
            )
        os.replace(tmp, _verlauf_datei)
    except Exception as e:
        logger.warning("Verlauf konnte nicht gespeichert werden: %s", e)


# --------------------------------------------------------------------------
# Rolling-Summary (Ein-Chat): pro Conversation ein kompaktes Summary der
# älteren Unterhaltung + Zähler, wie viele Nachrichten seit dem letzten Roll
# dazukamen (fürs Rate-Limit).
# --------------------------------------------------------------------------
summarys: Dict[str, Dict[str, Any]] = {}


def summary_holen(conversation_id: str) -> Dict[str, Any]:
    """Liefert { "text": str, "anzahl_seit_roll": int } der Conversation."""
    eintrag = summarys.get(conversation_id)
    if eintrag is None:
        return {"text": "", "anzahl_seit_roll": 0}
    return {
        "text": eintrag.get("text", ""),
        "anzahl_seit_roll": int(eintrag.get("anzahl_seit_roll", 0)),
    }


def summary_setzen(conversation_id: str, text: str) -> None:
    """Speichert ein neues Summary + setzt den Roll-Zähler zurück."""
    summarys[conversation_id] = {"text": text, "anzahl_seit_roll": 0}
    _speichere_verlauf()


def summary_erhoehe_zaehler(conversation_id: str) -> None:
    """Zählt eine weitere Nachricht seit dem letzten Roll."""
    eintrag = summarys.setdefault(conversation_id, {"text": "", "anzahl_seit_roll": 0})
    eintrag["anzahl_seit_roll"] = int(eintrag.get("anzahl_seit_roll", 0)) + 1
    summarys[conversation_id] = eintrag


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


def verlauf_runde_entfernen(conversation_id: str) -> bool:
    """Entfernt die letzte Nutzer-Nachricht samt ihrer Antwort (ein Paar).

    Wird vom Bearbeiten-Flow genutzt: Legt der Nutzer eine User-Nachricht
    zurück in die Eingabe zum Neu-Formulieren, soll die alte Runde (User +
    zugehörige Assistant-Antwort) aus dem persistenten Verlauf verschwinden,
    damit nach einem Reload nicht die alte Fassung wieder auftaucht.

    Sucht von hinten die letzte User-Nachricht und entfernt sie samt der
    direkt darauf folgenden Antwort(en). Der Aufrufer will immer die zuletzt
    abgeschickte Runde ersetzen — daher wird ohne Inhalts-Vergleich die letzte
    User-Nachricht nebst ihrer Antwort gelöscht (Owner des Bearbeiten-Flows).

    Returns: True, wenn eine Runde entfernt wurde; sonst False.
    """
    try:
        with _verlauf_sperre:
            if conversation_id not in conversations:
                return False
            hist = conversations[conversation_id]
            if not hist:
                return False
            # Letzte Position einer User-Nachricht von hinten suchen.
            letzter_user_idx = None
            for i in range(len(hist) - 1, -1, -1):
                if hist[i].get("role") == "user":
                    letzter_user_idx = i
                    break
            if letzter_user_idx is None:
                return False
            # User + die direkt folgende(n) Antwort(en) entfernen — die alte
            # Runde ist ab hier obsolet und darf nach Reload nicht wieder da sein.
            del hist[letzter_user_idx:]
            _speichere_verlauf()
            return True
    except Exception as e:
        logger.warning("Verlauf-Runde konnte nicht entfernt werden: %s", e)
        return False


# Die EINZIGE, immer fortgefuehrte Conversation. Das System erzeugt seit
# Stand 2026-08-30 KEINE neuen Conversations-ID mehr: Es gibt genau einen
# durchlaufenden Chat (Wunsch Sebastian), der nie neu beginnt und ueber den
# Verlauf durchsuchbar bleibt. Alle Nachrichten – egal ob mit oder ohne
# conversation_id angefordert – landen in dieser einen Conversation.
# Bewusst KEINE numerische `conv_N`-Vergabe mehr (die vorher bei jedem
# Neustart/ohne ID neue Nummern wie conv_133, conv_134 und damit unsichtbare
# Chat-Unterhaltungen erzeugte).
_AKTIVE_CONVERSATION_ID = "conv_main"


def _get_or_create_conversation(conversation_id: Optional[str]) -> str:
    """Liefert IMMER die eine durchlaufende Conversation (conv_main).

    Absicht (Wunsch Sebastian, 2026-08-30): Es gibt genau EINEN Chat, der nie
    neu beginnt. Eine uebergebene, unbekannte conversation_id wird auf die
    aktive Conversation gemappt statt eine neue anzulegen; ohne id ebenso. Ein
    einzelner durchlaufender Verlauf, durchsuchbar ueber die Gesprächssuche.
    """
    conversations.setdefault(_AKTIVE_CONVERSATION_ID, [])
    return _AKTIVE_CONVERSATION_ID


# Injizierbarer Memory-Extractor (setzt chat.py beim Start).
_memory_extractor: Optional[Callable] = None


def setze_memory_extractor(fn: Optional[Callable]) -> None:
    global _memory_extractor
    _memory_extractor = fn


def finish_exchange(conversation_id: str, user_message: str, reply: str,
                    bild_pfad: Optional[str] = None) -> int:
    """Austausch in den Verlauf schreiben + Erinnerungen ableiten.

    `bild_pfad`: optionaler Pfad eines über die Dateisuche gezeigten Bildes.
    Wird (nur wenn gesetzt) am Assistant-Eintrag mitgespeichert, damit die
    flüchtige Bild-Vorschau ('letzter Screenshot' usw.) einen Reload/eine
    neue Sitzung überlebt: Das Frontend lädt das Bild beim Verlauf-Anzeigen
    über diesen Pfad frisch nach (GET /api/dateien/daten?pfad=). Es wird
    bewusst NUR der Pfad gespeichert, nie die Bild-Datei (Sebastian-Regel).
    Abwärtskompatibel: Ohne Angabe werden Einträge wie zuvor geschrieben.
    Returns: Anzahl neuer Erinnerungen (0, wenn kein Extractor injiziert oder
    die Extraktion fehlschlägt).
    """
    if not reply:
        return 0
    history = conversations[conversation_id]
    with _verlauf_sperre:
        jetzt = datetime.now().astimezone().isoformat(timespec="seconds")
        history.append({"role": "user", "content": user_message, "zeit": jetzt})
        assistant_eintrag = {"role": "assistant", "content": reply, "zeit": jetzt}
        if bild_pfad:
            assistant_eintrag["bild_pfad"] = bild_pfad
        history.append(assistant_eintrag)
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