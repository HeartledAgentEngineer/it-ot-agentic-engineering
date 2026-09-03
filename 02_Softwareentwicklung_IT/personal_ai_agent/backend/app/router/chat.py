"""Chat API routes."""

import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Iterator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.config import settings, BASE_DIR
from app.models import ChatRequest, ChatResponse
from app.services.archiv_service import archiv_service
from app.services.auftrag_service import auftrag_service
from app.services.auftrags_erkennung import ist_auftrag
from app.services.faehigkeiten import stoesst_an_grenze
from app.services.hermes_gateway import hermes_gateway
from app.services.hermes_local import (
    ist_verfuegbar as hermes_local_ist_verfuegbar,
    stream_auftrag as hermes_local_stream_auftrag,
    hermes_registry,
)
from app.services.llm_service import llm_service
from app.services.memory_service import memory_service
from app.services import gesichter_service
from app.services import chat_verlauf
from app.services import sse as sse_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

# Verlauf liegt jetzt im Service (app.services.chat_verlauf) — Refactoring.
# Re-Export, damit der Rest dieser Datei (und alte Nutzer) identisch weiter
# funktionieren. Memory-Extraktion wird hier injected, damit der Service keine
# harten Imports braucht.
conversations = chat_verlauf.conversations

# Flüchtiger Bild-Cache pro Conversation (Option B): das zuletzt gefundene
# Bild (data_url + pfad) bleibt kurz im RAM, damit Folgefragen ("was war noch
# drauf?") OHNE erneutes Suchen anhand des Bildes beantwortet werden können.
# Nichts wird auf Platte gespeichert; nach _BILD_CACHE_DAUER_S verworfen.
_bild_cache: Dict[str, dict] = {}
_BILD_CACHE_DAUER_S = 600  # 10 Minuten
VERLAUF_DATEI = os.path.join(settings.chroma_persist_dir, "conversations.json")

# Service initialisieren (lädt Verlauf von der Platte).
chat_verlauf.init(VERLAUF_DATEI, settings.chroma_persist_dir)

# Memory-Extraktion an den Service anbinden (gleiche wie bisher).
chat_verlauf.setze_memory_extractor(
    memory_service.extract_and_store_memories
)

# Alias für Abwärtskompat im restlichen Code:
_lade_verlauf = chat_verlauf._lade_verlauf
_speichere_verlauf = chat_verlauf._speichere_verlauf
verlauf_nachricht_anhaengen = chat_verlauf.verlauf_nachricht_anhaengen
_get_or_create_conversation = chat_verlauf._get_or_create_conversation
_finish_exchange = chat_verlauf.finish_exchange
_verlauf_sperre = chat_verlauf._verlauf_sperre




_sse = sse_service._sse
_strom_auftrag_live = sse_service.strom_auftrag_live


def _archiv_treffer(frage: str, aktiv: bool) -> List[Dict[str, Any]]:
    """Passende Stellen aus den Chat-Archiven holen.

    Scheitert die Suche, geht die Anfrage trotzdem durch – nur ohne
    Vergangenheitswissen. Ein kaputtes Archiv darf den Chat nicht lahmlegen.
    """
    if not aktiv or not archiv_service.is_available:
        return []
    try:
        return archiv_service.hybrid(frage)
    except Exception as e:
        logger.warning("Archivsuche uebersprungen: %s", e)
        return []


def _wirkt_wie_aufgabe(nachricht: str) -> bool:
    """Kostenkontrolle fuer den LLM-Tool-Use-Decider (braucht_hermes).

    Nur Nachrichten mit System-/Arbeits-Charakter sollen den zusaetzlichen
    LLM-Call ausloesen - reine Plauderei/Wissensfragen nicht (Latenz/Kosten).
    Deterministischer Schnellfilter ueber Kernbegriffe.
    """
    if not nachricht:
        return False
    t = nachricht.lower()
    _ARBEITS_HINWEISE = (
        "schreibe", "baue", "erstelle", "fixe", "ändere", "aendere", "change",
        "code", "datei", "repo", "repository", "server", "api", "endpoint",
        "modul", "funktion", "skript", "script", "installiere", "pip", "npm",
        "git", "commit", "push", "pull", "branch", "merge", "docker", "container",
        "test", "bug", "fehler", "fehlerbehebung", "konfigurier", "starte",
        "dienst", "service", "sps", "terminal", "shell", "befehl", "bereinige",
        "refactor", "schema", "datenbank", "log", "debuggen",
    )
    return any(h in t for h in _ARBEITS_HINWEISE)


def _starte_lokale_hermes(
    auftrag: str,
    hinweis: str,
    kategorie: Optional[str],
    komplexitaet: Optional[str],
    chat_verknuepfung: Optional[str] = None,
    kontext: str = "",
):
    """Track C im Hintergrund: Lokaler Termux-Hermes bearbeitet den Auftrag und
    strahlt seine Gedanken live ins Auftragsbuch.

    Legt den Auftrag als direkt ``laeuft`` an (damit der Watcher ihn nicht
    doppelt claimt), startet den Hermes-Stream in einem Daemon-Thread und
    schreibt jeden Zwischengedanken als Status-Meldung sowie das Endergebnis
    via ``ergebnis_eintragen``. Das Frontend zeigt die Meldungen live als
    Chat-Blasen — inhaltlich 1:1, wie der Agent sie tippt.

    Returns:
        Dict mit der angelegten Auftrags-Äquivalenz (id, status).
    """
    eintrag = auftrag_service.anlegen_als_arbeitender(
        auftrag,
        hinweis=hinweis,
        kategorie=kategorie,
        komplexitaet=komplexitaet,
    )
    auftrag_id = eintrag["id"]

    # Verknuepfung Auftrag <-> Gespraech VOR dem Thread-Start setzen.
    # Wuerde sie erst nach dem Start geschehen, koennte der Worker die
    # allerersten Hermes-Zwischenmeldungen liefern, bevor seine
    # conversation_id in der Datei steht -> verlauf_nachricht_anhaengen
    # wuerde sie verwerfen. So sind alle Hermes-Meldungen ab der ersten
    # an das Gespraech gebunden und landen im persistenten Verlauf.
    if chat_verknuepfung:
        auftrag_service.setze_chat_verknuepfung(auftrag_id, chat_verknuepfung)

    def _worker():
        try:
            try:
                for ereignis in hermes_local_stream_auftrag(
                        auftrag_id, auftrag,
                        # Zwei-Stellen-Steuerung: Ist HERMES_LOCAL_SESSION in
                        # der .env gesetzt, dockt der Auftrag an diese laufende
                        # tmux-Session an statt eine neue zu starten (Sonst:
                        # bestehende_session=None → neue Session je Auftrag).
                        bestehende_session=(
                            settings.hermes_local_session or None
                        ),
                        # Zweitweg (Wunsch Sebastian): HERMES_LOCAL_KANAL=query
                        # nutzt den Einmal-Subprozess statt tmux.
                        nutze_query_modus=(
                            settings.hermes_local_kanal == "query"
                        ),
                        # AKTIV-Kanal (Wunsch): Server -> laufende Termux-
                        # Session ueber Datei-Inbox (kein tmux).
                        nutze_aktiv_modus=(
                            settings.hermes_local_kanal == "aktiv"
                        ),
                        # Kontext dieser Hermes-Session mitgeben, damit der
                        # Ziel-Hermes "weiss, dass er diese Session ist".
                        kontext=kontext,
                    ):
                    art = ereignis.get("art")
                    text = ereignis.get("text", "")
                    if art == "gedanke" and text:
                        auftrag_service.statusmeldung_hinzufuegen(auftrag_id, text)
                        # Auch in den persistenten Chat-Verlauf, falls verknuepft.
                        _reite_an_verlauf(auftrag_id, "assistant", text)
                    elif art == "frage" and text:
                        # Rueckfrage des Agenten: sichtbar machen, aber NICHT
                        # als fertig eintragen. Der Stream bleibt am Leben,
                        # die Session offen, bis der Nutzer per /eingabe
                        # geantwortet hat und eine finale Antwort folgt.
                        auftrag_service.statusmeldung_hinzufuegen(auftrag_id, text)
                        _reite_an_verlauf(auftrag_id, "assistant", text)
                    elif art == "ergebnis":
                        auftrag_service.ergebnis_eintragen(
                            auftrag_id, text, erfolg=bool(text)
                        )
                        if text:
                            _reite_an_verlauf(auftrag_id, "assistant", text)
                    elif art == "fehler":
                        auftrag_service.ergebnis_eintragen(
                            auftrag_id, text, erfolg=False
                        )
                        return
            except Exception as e:
                logger.error("Lokaler Hermes-Job abgebrochen (%s): %s", auftrag_id[:8], e)
                auftrag_service.ergebnis_eintragen(
                    auftrag_id, f"Fehler im lokalen Hermes-Job: {e}", erfolg=False
                )
            finally:
                # Auftrag ist final (ergebnis/fehler eingetragen oder Abbruch):
                # den laufenden Hermes-CLI aus der Registry nehmen. Dadurch
                # loest entferne() -> job.beende() -> tmux kill-session aus und
                # der interaktive Agent wird wirklich beendet. Stattdessen
                # verwaisten vorher jede abgeschlossene Programmierung eine
                # offene tmux-Session (Ressourcenschwund ueber die Tage).
                hermes_registry.entferne(auftrag_id)
        except Exception as e:
            logger.error("Lokaler Hermes-Job-Traeger selbst fehlgeschlagen (%s): %s",
                         auftrag_id[:8], e)

    threading.Thread(target=_worker, daemon=True).start()
    return eintrag


def _reite_an_verlauf(auftrag_id: str, role: str, content: str) -> None:
    """Reicht eine Hermes-Nachricht in den persistenten Chat-Verlauf weiter.

    Der Coding-Auftrag fuehrt eine verknuepfte conversation_id; landet die
    Nachricht nur im Auftragsbuch, ist der Chat-Verlauf nach einem Neuladen
    leer. Hier wird die Verknuepfung gelesen und angehaengt, wenn vorhanden.
    """
    try:
        eingang = auftrag_service.einzeln(auftrag_id)
        conv_id = eingang.get("conversation_id") if eingang else None
        if conv_id:
            auftrag_service._in_verlauf_anhaengen(conv_id, role, content)
    except Exception as e:
        logger.warning("Verlauf-Übergabe fehlgeschlagen (%s): %s", auftrag_id[:8], e)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat message and return the LLM response."""
    try:
        # Weiche: Coding-/Werkzeug-Auftraege weiterleiten. Bei hochgeladenen
        # Dateien (request.files) NICHT als Coding-Auftrag einordnen — ein
        # Dokument-/Bild-Upload ist immer eine Verständnis-/Analyse-Frage an
        # den LLM, kein Programmier-Kommando an Hermes.
        # Zusätzlich zur ist_auftrag()-Heuristik wird die Fähigkeits-Grenze
        # geprüft (Terminal/Datei/System/Tool-Install) — selbst wenn die
        # Heuristik es nicht als Coding einstuft, delegiert der Agent an
        # Hermes (Toolcall).
        ist_auftrag_val = False
        if not request.files and not request.force_agent:
            ist_auftrag_val, begruendung, kategorie, komplexitaet = ist_auftrag(request.message)
            if not ist_auftrag_val and stoesst_an_grenze(request.message):
                ist_auftrag_val = True
                begruendung = "Fähigkeits-Grenze (Terminal/Datei/System) – Hermes als Toolcall"
                kategorie = "feature"
                komplexitaet = "mittel"
            elif not ist_auftrag_val:
                # Sauberer Tool-Use als letzte Stufe: Ein günstiger LLM-Call
                # entscheidet, ob Hermes nötig ist (Wunsch Sebastian 2026-09-01).
                # Nur bei Nachrichten mit System-/Arbeits-Charakter, NICHT bei
                # reiner Plauderei, um Latenz/Kosten zu begrenzen.
                if _wirkt_wie_aufgabe(request.message):
                    bedarf = llm_service.braucht_hermes(request.message)
                    if bedarf.get("braucht_hermes"):
                        ist_auftrag_val = True
                        begruendung = (
                            "LLM-Tool-Use: Hermes nötig ("
                            + (bedarf.get("begruendung") or "System-/Repo-Arbeit")
                            + ")"
                        )
                        kategorie = "feature"
                        komplexitaet = "mittel"
        else:
            begruendung, kategorie, komplexitaet = "", None, None
        if ist_auftrag_val:
            # Die Track-A/C/B-Weiche (PC → lokal → Buch) liegt jetzt im
            # Routing-Service. Er liefert art/reply/conversation_id; hier wird
            # nur noch die ChatResponse daraus gebaut.
            from app.services.chat_routing import route_auftrag
            res = route_auftrag(
                request.message,
                begruendung,
                kategorie,
                komplexitaet,
                finish_exchange=_finish_exchange,
                get_or_create_conversation=lambda _: _get_or_create_conversation(request.conversation_id),
                starte_lokale_hermes=_starte_lokale_hermes,
                kontext=_baue_kontext(request.message),
            )
            return ChatResponse(
                reply=res["reply"],
                conversation_id=res["conversation_id"],
                memories_used=0,
                memories_created=0,
                sources=[],
                archiv_used=0,
                ziel=res.get("ziel"),
            )

        conversation_id = _get_or_create_conversation(request.conversation_id)
        history = conversations[conversation_id]

        # 1. Retrieve relevant memories from vector DB
        memories = memory_service.retrieve_relevant_memories(
            request.message, top_k=5
        )

        # 1b. Passende Stellen aus den Chat-Archiven – das, was den Agenten
        # über die eigene Vergangenheit sprechen lässt.
        archiv = _archiv_treffer(request.message, request.archiv)

        # 1c. Rolling-Summary der älteren Unterhaltung (Ein-Chat). Begrenzt die
        # History auf die letzten 15 + gibt den kompakten Summary als Zusatz-
        # Kontext weiter, damit die Vergangenheit nicht verloren geht / der
        # Prompt nicht explodiert.
        kontext_summary, _ = _hole_kontext_summary(conversation_id, history, request.message)
        begrenzte_history = history[-15:]

        # 1d. Handy-Dateisuche als Tool über Sprache: Wenn die Anfrage einen
        # Datei-Such-Wunsch enthält, wird die Tool-Ausgabe an die user_message
        # gehängt, damit der LLM die Treffer nennt (Stufe A).
        werkzeug_notiz = ""
        datei_tool_bilder = []
        datei_bilder = []
        # 1e. Archiv-Tool über Sprache: 'was weißt du über X aus dem Archiv'.
        # Hat VORRANG vor der Dateisuche — wer nach alten Gesprächen fragt,
        # meint keine lokalen PDFs. Eine Archiv-Frage darf die Handy-
        # Dateisuche NICHT auslösen.
        archiv_notiz = _archiv_tool(request.message)
        werkzeug_notiz = archiv_notiz
        if not werkzeug_notiz:
            werkzeug_notiz, datei_tool_bilder = _datei_tool(request.message)
            # 1f. Verlaufs-Tool über Sprache (Rückblick): 'was haben wir zu X gesagt'.
            if not werkzeug_notiz:
                werkzeug_notiz = _verlauf_tool(request.message)
        user_message_fuer_llm = request.message
        if werkzeug_notiz:
            user_message_fuer_llm = request.message + werkzeug_notiz
        # Bilder aus der Dateisuche an die files-Liste anhängen (Vision-LLM).
        if datei_tool_bilder:
            datei_bilder = datei_tool_bilder
            # Flüchtiger Bild-Cache für die laufende Conversation (Option B):
            # das zuletzt gefundene Bild bleibt für Folgefragen kurz im RAM
            # (10 Min), damit "was war noch drauf?" OHNE erneutes Suchen
            # beantwortet werden kann — nichts wird auf Platte gespeichert.
            _bild_cache[conversation_id] = {
                "bilder": datei_tool_bilder,
                "zeit": time.time(),
            }
        elif (conversation_id in _bild_cache) and not archiv_notiz:
            # Kein neues Bild angefordert: nutze das gecachte (wenn frisch).
            eintrag = _bild_cache[conversation_id]
            if time.time() - eintrag["zeit"] < _BILD_CACHE_DAUER_S:
                if not datei_bilder:
                    datei_bilder = eintrag["bilder"]
                    user_message_fuer_llm += (
                        "\n\n[Fortsetzung: Das zuvor gefundene Bild wird "
                        "mitgeschickt — beantworte die Frage anhand des Bildes.]"
                    )
            else:
                _bild_cache.pop(conversation_id, None)


        # 1g. Gesichter: Wird ein Bild betrachtet (Dateisuche ODER Upload),
        # den Gesichter-Katalog an den Prompt hängen, damit der Vision-LLM
        # bekannte Personen benennt statt zu raten. Deterministisch, kein
        # Extra-LLM-Call: der Katalog-Text ist klein.
        katalog_bilder = []
        bild_aktiv = bool(datei_bilder) or bool(
            request.files and any(f.type == "image" for f in request.files)
        )
        if bild_aktiv:
            katalog = gesichter_service.katalog_kontext()
            if katalog:
                user_message_fuer_llm += katalog
            # Referenz-Miniaturen als Vergleichsbilder mitgeben (falls da):
            # der Vision-LLM kann das aktuelle Foto gegen die eingebetteten
            # Referenzgesichter abgleichen statt nur über die Text-Liste zu
            # raten. pCloud-sicher: das sind die eingebetteten Kopien, nicht
            # die (möglicherweise verschobenen) Originaldateien.
            katalog_bilder = gesichter_service.referenz_bilder()
            if katalog_bilder:
                ref_namen = ", ".join(
                    b.get("person") or "?"
                    for b in katalog_bilder if b.get("person")
                )
                user_message_fuer_llm += (
                    "\n\n[Dem aktuellen Foto sind zusätzlich die bekannten "
                    "Referenzgesichter angehängt (in dieser Reihenfolge): "
                    + (ref_namen or "mehrere Personen")
                    + ". Vergleiche das aktuelle Foto damit und benenne "
                      "bekannte Personen — aber nur, wenn die Übereinstimmung "
                      "überzeugend ist. Erfinde KEINE Zuordnung.]"
                )

        # 1h. Gesichter reaktiv 'merken': Sagt der Nutzer beim Betrachten
        # eines Bildes, WER darauf ist ('das ist Pedi', 'das ist meine Oma
        # Helga'), wird das deterministisch in den Katalog übernommen — der
        # Vision-LLM erkennt die Person künftig auf Fotos. Konservativ: nur
        # bei aktiver Bild-Ansicht + Nenn-Phrase, sonst kein Effekt.
        # Ist gerade ein Bild (Dateisuche ODER Upload) da, wird es als
        # Referenz-Miniatur an die Person gekoppelt (für den späteren
        # Bild-zu-Bild-Abgleich) — wichtig z. B. um Zwillingsbrüder per
        # echtem Vergleichsbild statt nur Namens-Kontext zu unterscheiden.
        aktuelles_bild_data = ""
        if datei_bilder and datei_bilder[0].get("data_url"):
            aktuelles_bild_data = datei_bilder[0]["data_url"]
        elif request.files:
            upload_img = next(
                (f for f in request.files if f.type == "image" and f.data_url),
                None,
            )
            if upload_img:
                aktuelles_bild_data = upload_img.data_url
        merkhinweis = _gesichter_merke(
            request.message, bild_aktiv, str(aktuelles_bild_data or ""),
            embedding=_embedding_aus_data_url(str(aktuelles_bild_data or ""))
            if bild_aktiv and aktuelles_bild_data else None,
        )
        if merkhinweis:
            user_message_fuer_llm += merkhinweis
        # WhatsApp-artiges Antwort-Zitat an den LLM-Kontext (nicht an die
        # Erkennung): der Agent beantwortet primär das konkret Zitierte.

        user_message_fuer_llm += _zitat_anhang(request)
        # SFace-Gesichts-Abgleich (deterministisch, auch fuer hochgeladenes Bild)
        _gesichts_notiz = _gesichtsabgleich_notiz(request, datei_bilder)
        if _gesichts_notiz:
            user_message_fuer_llm += _gesichts_notiz


        # 2. Get LLM response with memory context
        # Vision-Routing: Wird ein Bild aus der Dateisuche mitgeschickt
        # (datei_tool_bilder), braucht es ein VISION-fähiges Modell — ein
        # reines Text-Modell (z. B. DeepSeek Flash) kann das Bild nicht sehen
        # und antwortet "kein Zugriff". Dann nehmen wir automatisch Gemini
        # Flash (günstig + bildfähig), falls der Nutzer kein anderes wählte.
        vision_modell = "google/gemini-2.5-flash"
        modell_fuer_call = request.model or ""
        if datei_tool_bilder and not (modell_fuer_call
                                      and ("gemini" in modell_fuer_call
                                           or "gpt-4o" in modell_fuer_call
                                           or "gpt-5" in modell_fuer_call
                                           or "sonnet" in modell_fuer_call
                                           or "claude" in modell_fuer_call)):
            modell_fuer_call = vision_modell

        reply, quellen = llm_service.chat(
            user_message=user_message_fuer_llm,
            conversation_history=begrenzte_history,
            memories=memories,
            web_search=request.web_search,
            model=modell_fuer_call,
            no_retention=request.no_retention,
            archiv=archiv,
            summary=kontext_summary,
            files=(
                [f.model_dump() for f in request.files] if request.files else []
            ) + (datei_tool_bilder if datei_tool_bilder else []) + (katalog_bilder if katalog_bilder else []),
        )

        # 3./4. Verlauf fortschreiben und Erinnerungen ableiten.
        # Bildpfad des Dateisuche-Bildes mitgeben, damit die flüchtige
        # Vorschau einen Reload überlebt (Frontend lädt ihn nach).
        memories_created = _finish_exchange(
            conversation_id, request.message + _zitat_anhang(request), reply,
            bild_pfad=(
                datei_bilder[0].get("pfad") if datei_bilder else None
            ) or _upload_bild_pfad(request),
        )

        return ChatResponse(
            reply=reply,
            conversation_id=conversation_id,
            memories_used=len(memories),
            memories_created=memories_created,
            sources=quellen,
            archiv_used=len(archiv),
            bild_vorschau=(
                datei_tool_bilder[0]["data_url"] if datei_tool_bilder else None
            ),
            bild_pfad=(
                datei_tool_bilder[0].get("pfad") if datei_tool_bilder else None
            ),
        )

    except Exception as e:
        logger.error("Chat error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


_PERSON_NENN_MUSTER = (
    "das ist", "das ist doch", "das hier ist", "das dort ist", "das ist auf",
    "der ist", "die ist", "das ist die", "das ist der", "das ist meine",
    "das ist mein", "das ist unsere", "das ist unser",
)

# Deutsche Substantive werden ALLE großgeschrieben — die Capitalize-Heuristik
# würde sonst z. B. "das ist die beste Idee" als Person "Idee" speichern. Diese
# konservative Ausschlussliste verhindert das (allgemeine Nicht-Personen-Wörter).
_KEINE_PERSON_ROLLE = {
    # Familienrollen, die NIE der Eigenname sind (Rollen werden separat erkannt).
    "mutter", "oma", "opa", "vater", "tante", "onkel", "mama", "papa",
    "bruder", "schwester", "frau", "mann", "kind", "tochter", "sohn",
    # Allgemeine Nicht-Personen-Substantive (Großschreibung ist in Deutsch ja
    # der Normalfall — nur konkrete Alltagsfälle, die bei Fotos auftauchen).
    "idee", "haus", "auto", "baumschule", "sache", "ding", "bild", "foto",
    "screenshot", "tasse", "buch", "vase", "tisch", "hund", "katze", "straße",
    "plastikmull", "beste", "schönste", "größte", "groesste",
    # Farb-/Eigenschaftswörter (häufig unmittelbar nach "das ist …").
    "blau", "rot", "grün", "gruen", "gelb", "schwarz", "weiß", "weiss",
}


def _nutzer_name() -> str:
    """Vor-/Kosename des Nutzers aus dem lokalen System-Prompt, sonst \"\"."""
    try:
        with open(settings.system_prompt_local_file, "r", encoding="utf-8") as f:
            text = f.read()
        import re as _re
        m = _re.search(r"Name:\s*([A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß \-]*)", text)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return ""


def _zitat_anhang(request: Any) -> str:
    """WhatsApp-artiger Antwort-Kontext: Legt als Text das konkret beantwortete
    Zitat bei, das an die LLM-Nachricht und den persistierten Verlauf geheftet wird.
    """
    try:
        z = (getattr(request, "antwort_auf", "") or "").strip()
        if not z:
            return ""
        if len(z) > 400:
            z = z[:397] + "..."
        kopf = "[Antwort des Nutzers auf diese frühere Nachricht — beziehe dich primär auf DIESES Zitat:]"
        return "\n\n" + kopf + "\n" + z
    except Exception:
        return ""


def _gesichtsabgleich_notiz(request: Any, datei_bilder: Optional[list] = None) -> str:
    """SFace-Gesichts-Tool-abgleich fuer Bilder (auch hochgeladen)."""
    try:
        from app.services import face_service as _face
        if not _face.verfuegbar():
            return ""
        pfad = None
        if datei_bilder and datei_bilder[0].get("pfad"):
            pfad = datei_bilder[0]["pfad"]
        if not pfad:
            pfad = _upload_bild_pfad(request)
        if not pfad or not os.path.exists(pfad):
            return ""
        personen = _face.erkenne_bild_pfad(pfad).get("personen") or []
        namen = []
        for _p in personen:
            for _t in _p.get("treffer", []):
                namen.append(_t.get("name") + (" (sicher)" if _t.get("sicher") else " (unsicher)"))
        if not namen:
            return ""
        return " Erkennung per Gesichts-Embedding: " + "; ".join(sorted(set(namen))) + "."
    except Exception:
        return ""


def _upload_bild_pfad(request: Any) -> Optional[str]:
    """Mappt ein ueber den Upload-Button angehaengtes Bild auf seinen realen
    Platten-Pfad (uploads/<id>.<ext>.

    Damit ein hochgeladenes Bild im persistierten Verlauf einen `bild_pfad`
    bekommt (wie Dateisuche-Bilder schon) und so einen Reload/Neustart
    ueberlebt: Das Frontend laedt es per GET /api/dateien/daten?pfad=
    frisch nach. Es wird NUR der Pfad persistiert, nie die Bild-Datei.
    """
    try:
        if not request.files:
            return None
        import glob
        for f in request.files:
            if not f.type == "image" or not getattr(f, "id", ""):
                continue
            # Robust: echte Datei per wildcard suchen (Upload-ID), weil die
            # tatsaechliche Erweiterung vom Uploader stammt (id.jpg, id.jpeg,
            # id.png ...) und nicht aus dem MIME erraten werden darf.
            base = str(BASE_DIR / "uploads" / f.id)
            treffer = sorted(glob.glob(base + ".*"))
            if treffer and os.path.exists(treffer[0]):
                return treffer[0]
    except Exception as e:
        logger.warning("Upload-Bildpfad-Ableitung fehlgeschlagen: %s", e)
    return None


def _embedding_aus_data_url(data_url: str):
    """Extrahiert aus einer data_url (base64) das erste Gesichts-Embedding.

    Dekodiert das Bild und laesst es in der Debian-Face-Engine (YuNet+SFace)
    detektieren/embedden. Returns: erstes Embedding (list[float]) oder None.
    Robust: Fehler/Schwaechen schlagen den Chat nie fehl.
    """
    try:
        if not data_url or "base64," not in data_url:
            return None
        from app.services import face_service
        if not face_service.verfuegbar():
            return None
        b64 = data_url.split("base64,", 1)[1]
        import base64 as _b, tempfile, os as _os
        roh = _b.b64decode(b64)
        fd, tmp = tempfile.mkstemp(suffix=".png")
        _os.close(fd)
        try:
            with open(tmp, "wb") as f:
                f.write(roh)
            gesichter = face_service.embeddings_fuer_pfad(tmp)
        finally:
            try:
                _os.remove(tmp)
            except OSError:
                pass
        for g in gesichter:
            emb = g.get("embedding")
            if emb:
                return emb
        return None
    except Exception as e:
        logger.warning("Embedding-Extraktion fehlgeschlagen (ignoriert): %s", e)
        return None


def _gesichter_merke(
    frage: str, bild_aktiv: bool, referenz_bild: str = "",
    embedding: Optional[list] = None,
) -> str:
    """Reaktiv 'Gesichter merken' über Sprache (ohne UI).

    Erkennt beim Betrachten eines Bildes die Angabe, WER darauf abgebildet
    ist — z. B. 'das ist Pedi', 'das bin ich', 'das ist mein Zwillingsbruder
    Julian' oder mehrere Personen auf EINEM Bild ('das bin ich und das ist
    Julian') — und speichert jede erkannte Person (Name + ggf. Rolle) in den
    Gesichter-Katalog (`gesichter_service.person_speichern`). Zusätzlich wird
    das gerade betrachtete Bild (`referenz_bild` als data_url) als
    Referenz-Miniatur an jede Person gekoppelt — damit der spätere Abgleich
    per echtem Bild-zu-Bild-Vergleich läuft (entscheidend z. B. um einen
    Zwillingsbruder zu unterscheiden).

    Extraktion: Zuerst agentischer LLM-Aufruf (`extrahiere_gesichts_anlernen`)
    — robust gegen freie Formulierung und Gruppenbilder. Scheitert der (oder
    ist das Modell nicht erreichbar), fällt er auf eine konservative
    deterministische Heuristik für den Einzel-Fall zurück.

    Konservativ: läuft nur bei aktivem Bild (`bild_aktiv`) + Anlern-Signal.
    Ohne Bild wird NICHTS gemerkt (kein versehentliches Speichern, z. B.
    bei 'das ist die beste Idee'). Merken darf den Chat nie brechen.

    Returns: Anweisungs-Text für den LLM (an die user_message anzuhängen),
    oder \"\" wenn nichts zu merken ist.
    """
    if not bild_aktiv or not frage or len(frage.strip()) < 3:
        return ""
    f = frage.lower().strip()
    # Günstiges Gate: nur weiter, wenn ein Personen-Nenn-Signal vorliegt —
    # sonst würde für jede Bild-Frage ein LLM-Call abgehen (teuer + langsam).
    _anlern_signal = False
    if " ich" in f or "bin ich" in f or "ich bin" in f or "auf dem bild" in f:
        _anlern_signal = True
    elif any(m in f for m in _PERSON_NENN_MUSTER):
        _anlern_signal = True
    else:
        # Eigennamen-Signal: ein großgeschriebenes Wort nach einer Nenn-Phrase
        # (ohne das Signal selbst wäre eine normale Rückfrage).
        import re as _re
        if _re.search(r"(das ist|das ist die|das ist der|das ist mein|das ist meine|das ist unser|das ist unsere)\s+[A-ZÄÖÜ]", frage):
            _anlern_signal = True
    if not _anlern_signal:
        return ""

    nutzer_name = _nutzer_name()
    personen = []

    # 1) Agentisch: LLM extrahiert die Person(en) robust.
    try:
        res = llm_service.extrahiere_gesichts_anlernen(frage, nutzer_name)
        if res.get("ist_anlern_wunsch") and res.get("personen"):
            personen = res["personen"]
    except Exception:
        personen = []

    # 2) Fallback: deterministische Heuristik (Einzelperson, kein LLM).
    if not personen:
        p = _gesichter_merke_deterministisch(frage)
        if p:
            personen = [p]

    if not personen:
        return ""

    # Alle Personen speichern (je dieselbe Referenz-Miniatur).
    gespeichert = []
    try:
        for p in personen:
            name = (p.get("name") or "").strip()
            if not name:
                continue
            rolle = (p.get("rolle") or "").strip()
            gesichter_service.person_speichern(
                name=name, rolle=rolle,
                beziehung="",
                beschreibung="",
                referenz_bild_pfad="",
                # Das aktuelle Bild als Referenz einbetten (falls da).
                referenz_bild_miniatur=(referenz_bild or "").strip(),
                # Echtes Gesichts-Embedding (128-dim) für Zwillings-robustes
                # Wiedererkennen; None -> kein Embedding gespeichert.
                embedding=embedding,
            )
            gespeichert.append((name, rolle))
    except Exception:
        # Merken ist Bonus — darf den Chat nie brechen.
        if not gespeichert:
            return ""

    if not gespeichert:
        return ""
    hat_bild = bool((referenz_bild or "").strip())
    namen_text = ", ".join(
        (n + (f" ({r})" if r else "")) for n, r in gespeichert
    )
    hinweis = (
        f"Folgende Person(en) wurde(n) dem Gesichter-Katalog hinzugefügt: "
        f"{namen_text}"
        + (f", jeweils mit diesem Bild als Referenz versehen" if hat_bild else "")
        + ". Sag dem Nutzer kurz, dass du sie gespeichert hast und sie künftig "
        "auf Fotos erkennst (per Bild-Vergleich wenn ein Referenzbild "
        "vorhanden ist). "
        "Achtung bei einander stark ähnlichen Personen (z. B. Zwillingsbrüder): "
        "Wenn zwei Personen verwechselbar aussehen, sage ehrlich, wenn du "
        "unsicher bist, statt zu raten — \"das kann ich nicht zuverlässig "
        "unterscheiden\" ist erlaubt und besser als eine erfundene Zuordnung. "
        "Erfinde KEINE Details."
    )
    return f"\n\n[Hinweis für den Assistenten: {hinweis}]"


def _gesichter_merke_deterministisch(frage: str) -> Optional[dict]:
    """Deterministischer Fallback: erkennt EINE genannte Person (Name+Rolle).

    Konservativ, nur für den Einzel-Fall inkl. 'das bin ich'. Returns dict
    {name, rolle, ist_nutzer} oder None.
    """
    import re as _re
    # 'das bin ich' ohne weiteren Namen → Nutzer.
    if not _re.search(r"das ist|das ist die|das ist der|das ist mein|das ist meine",
                      frage, _re.I) and ("bin ich" in frage.lower() or "ich bin" in frage.lower()):
        return {"name": "", "rolle": "", "ist_nutzer": True}  # Name wird unten befüllt

    m = _re.search(r"(?:das ist|das hier ist|das dort ist|das ist doch|das ist auf)"
                   r"(?: die| der| meine| mein| unsere| unser)?\s+(.+?)\s*[.!?]?\s*$",
                   frage)
    if not m:
        return None
    rest = m.group(1).strip()
    woerter = _re.findall(r"[A-ZÄÖÜ][a-zäöüß]+", rest)
    if not woerter:
        return None
    name = next((w for w in reversed(woerter) if w.lower() not in _KEINE_PERSON_ROLLE), "")
    if not name:
        return None
    rolle = ""
    for w in reversed(woerter):
        if w == name:
            continue
        if w.lower() in _KEINE_PERSON_ROLLE and w.lower() not in _KEINE_NICHT_ROLLE_WORTE:
            rolle = w
            break
    return {"name": name, "rolle": rolle, "ist_nutzer": False}


_KEINE_NICHT_ROLLE_WORTE = {
    "beste", "schönste", "größte", "groesste", "blau", "rot", "grün", "gruen",
    "gelb", "schwarz", "weiß", "weiss", "idee", "haus", "auto", "sache", "ding",
    "bild", "foto", "screenshot", "tasse", "buch", "vase", "tisch", "hund",
    "katze", "straße", "plastikmull",
}


def _baue_kontext(frage: str) -> str:
    """Baut das kompakte Kontext-Paket für die Hermes-Delegation (Variante C).

    Nimmt die letzten max. 6 Chat-Nachrichten der aktuellen Conversation +
    die 3 relevantesten Erinnerungen (semantisch zur Frage) und kürzt sie auf
    eine handliche Textmenge. So weiß Hermes, worum es im Gespräch geht,
    ohne dass der Prompt explodiert (günstig + reichhaltig).
    """
    konv_id = _get_or_create_conversation(None)
    hist = conversations.get(konv_id, [])
    teile: List[str] = []
    # Letzte bis zu 6 Nachrichten (ohne die aktuelle Frage-Duplikate).
    for m in hist[-6:]:
        rolle = m.get("role", "?")
        inhalt = (m.get("content") or "").strip()
        if not inhalt:
            continue
        # Langen Inhalt kürzen (Kontext kompakt halten).
        if len(inhalt) > 500:
            inhalt = inhalt[:500] + "…"
        teile.append(f"{rolle}: {inhalt}")
    # Relevante Erinnerungen (semantisch zur Frage).
    try:
        mems = memory_service.retrieve_relevant_memories(frage, top_k=3)
        for m in mems:
            inhalt = (m.get("content") or m.get("text") or "").strip()
            if inhalt and len(inhalt) < 400:
                teile.append(f"Erinnerung: {inhalt}")
    except Exception:
        pass  # Kontext ist Bonus — nie die Delegation deswegen brechen.
    if not teile:
        return ""
    return "\n".join(teile)


# ── Archiv-Tool über Sprache ────────────────────────────────────────────
# Harte Signale: Wer DAS sagt, meint den Wissensspeicher (alte Chats von
# ChatGPT/Gemini/Claude) — unabhängig davon, ob das Wort „Archiv" fällt.
_ARCHIV_SIGNALE = (
    "aus dem archiv", "aus meinem archiv", "im archiv", "dem archiv", "archiv",
    "alte chats", "alten chats", "alte gespräche", "alten gespräche",
    "alte gespraeche", "alten gespraeche", "alte unterhaltungen",
    "alten unterhaltungen",
)
# Weiche Signale: Erinnerungs-/Wissens-Fragen, die genauso gut den
# lokalen Gesprächsverlauf meinen könnten — Archiv wenn verfügbar,
# sonst stiller Rückfall auf Verlauf/allgemeines Wissen.
_ARCHIV_SIGNALE_WEICH = (
    "was weißt du über", "was weisst du über",
    "erinnerst du dich", "erinnerst du dich noch", "erinnere dich an",
    "weißt du noch", "weisst du noch", "historisch", "chronik",
    "vergangenheit",
)
# Gegenstück: Bild-/Foto-Fragen gehören zur Handy-DATEISUCHE, nie ins
# Archiv — selbst wenn sie „über …" formuliert sind („was weißt du über
# das Foto von gestern?"). Kein False-Positive.
_ARCHIV_AUSSCHLUSS = ("bild", "foto", "screenshot", "aufnahme")
_ARCHIV_STOPWOERTER = {
    "zu", "über", "ueber", "aus", "dem", "den", "der", "die", "das", "des",
    "im", "in", "an", "auf", "von", "vom", "mit", "und", "oder", "noch",
    "auch", "ein", "eine", "einen", "einer", "einem", "eines", "wir",
    "ich", "du", "haben", "hat", "hatte", "hatten", "gesagt", "besprochen",
    "erinnere", "erinnerst", "dich", "dass", "was", "weiß", "weiss",
    "wissen", "archiv", "alte", "alten", "chats", "gespräche", "gespraeche",
    "unterhaltungen", "historisch", "chronik", "vergangenheit", "bitte",
    "mal", "mir", "mich", "nochmal",
}


def _archiv_tool(frage: str, service: Optional[Any] = None) -> str:
    """Archiv-Suche als 'Tool' über Sprache (ohne UI).

    Erkennt Archiv-/Erinnerungs-Signale („aus dem Archiv", „alte Chats",
    „was weißt du über X", „erinnerst du dich an X", „historisch") →
    durchsucht den Wissensspeicher (Chunk-DB der alten ChatGPT/Gemini/
    Claude-Gespräche) → hängt die Treffer mit Quelle + Datum an die
    user_message, damit der LLM daraus zitiert.

    Hat VORRANG vor der Dateisuche: Eine Archiv-Frage darf die Handy-
    Dateisuche NICHT auslösen (der Nutzer meint alte Gespräche, keine
    lokalen PDFs). Deshalb liefert das Tool auch bei leerem oder nicht
    erreichbarem Archiv einen Hinweis statt eines leeren Strings — nur
    weiche Erinnerungs-Signale fallen bei fehlendem Archiv still auf den
    lokalen Gesprächsverlauf (_verlauf_tool) zurück.

    `service` ist injizierbar (Tests); Default ist der Archiv-Service.

    Liefert "" wenn kein Archiv-Wunsch vorliegt (dann läuft die
    Dateisuche/Verlaufssuche ganz normal).
    """
    if service is None:
        service = archiv_service
    f = frage.lower().strip()
    if not f:
        return ""
    # Foto-/Bild-Fragen: Dateisuche, nicht Archiv (False-Positive-Schutz).
    if any(w in f for w in _ARCHIV_AUSSCHLUSS):
        return ""
    trigger = next((s for s in _ARCHIV_SIGNALE if s in f), None)
    weich = False
    if trigger is None:
        trigger = next((s for s in _ARCHIV_SIGNALE_WEICH if s in f), None)
        weich = trigger is not None
    if not trigger:
        return ""
    # Stichwort = Text nach dem Signal, bereinigt um Stoppwörter → der
    # Kern bleibt („EasyBank“ aus „was weißt du über EasyBank aus dem
    # Archiv“).
    stichwort = f[f.find(trigger) + len(trigger):].strip(" ?!,.:")
    teile = [w for w in stichwort.split() if w not in _ARCHIV_STOPWOERTER]
    stichwort = " ".join(teile).strip()
    if not stichwort or len(stichwort) < 3:
        # Nichts herauslösbar (Signal am Satzende) → ganze Frage als
        # Suchanfrage; die FTS-Aufbereitung filtert selbst die Füllwörter.
        stichwort = f
    # Wissensspeicher nicht erreichbar (z. B. PC ohne angebundenes Handy):
    # bei hartem Archiv-Bezug ehrlich sagen (und KEINE Dateisuche starten),
    # bei weichem Erinnerungs-Signal den lokalen Verlauf übernehmen lassen.
    if not service.is_available:
        if weich:
            return ""
        return (
            "\n\n[Der Wissensspeicher/Archiv mit den alten Chats ist gerade "
            "nicht erreichbar. Sag dem Nutzer ehrlich, dass Du dazu gerade "
            "nichts sagen kannst, und schlage vor, es später erneut zu "
            "versuchen — erfinde KEINE Archiv-Fundstellen.]"
        )
    try:
        treffer = service.hybrid(stichwort)
    except Exception as e:
        logger.warning("Archiv-Tool-Suche uebersprungen: %s", e)
        return (
            "\n\n[Die Archiv-Suche ist gerade fehlgeschlagen. Sag dem Nutzer "
            "ehrlich, dass Du dazu gerade nichts sagen kannst — erfinde "
            "KEINE Archiv-Fundstellen.]"
        )
    if not treffer:
        return (
            "\n\n[Im Archiv zu '" + stichwort + "': nichts gefunden. "
            "Beantworte die Frage trotzdem aus deinem allgemeinen Wissen — "
            "erfinde aber KEINE Archiv-Fundstellen.]"
        )
    zeilen = []
    for t in treffer[:5]:
        quelle = t.get("source") or "unbekannt"
        datum = (t.get("beginn") or "")[:10]
        kopf = f"[{quelle}, {datum}]" if datum else f"[{quelle}]"
        text = (t.get("text") or "").strip().replace("\n", " ")[:300]
        zeilen.append(f"{kopf} {text}")
    return (
        "\n\n[Aus dem Archiv zu '" + stichwort + "':]\n"
        + "\n".join(zeilen)
        + "\nZitiere dem Nutzer die relevanten Stellen aus der Vergangenheit "
          "und nenne dabei die Quelle (ChatGPT/Gemini/Claude) und das Datum.]"
    )


def _datei_tool(frage: str) -> tuple:
    """Handy-Dateisuche als 'Tool' über Sprache (ohne UI).

    Stufe A: erkennt Datei-Suchs-Signale → sucht Treffer → LLM nennt sie.
    Stufe B: erkennt Lese-Signale ("lies <datei>", "was steht in <datei>",
    "zeig mir den inhalt von <datei>", "gib mir die <datei>") → liest den
    INHALT der gefundenen/benannten Datei + hängt ihn als Text (oder Bild-
    data_url) an die user_message, damit der LLM zusammenfasst/informiert.

    Returns: (text, bild_files) — text hängt an die user_message, bild_files
    ist eine Liste von {"type":"image","data_url":...} für den Vision-LLM.
    Liefert ("", []) wenn kein Datei-Bezug vorliegt (kein Tool-Trigger).
    """
    # Agentischer LLM-Intent (primär). Ein günstiges Gate entscheidet zuerst,
    # ob hier überhaupt ein Datei-Verdacht vorliegt — so wird nicht jede
    # normale Frage an den LLM geschickt (spart Token). Jahre zählen mit:
    # "letztes Foto aus 2025" hat "foto" (Signal) + "2025".
    f = frage.lower().strip()
    if not f:
        return "", []
    import re as _re
    _jahr_vorhanden = bool(_re.search(r"\b(20)\d{2}\b", f)) or "jahr" in f

    # Schnelles, günstiges Vor-Gate: Nur bei Datei-Verdacht weiter (sonst
    # würde JEDE Nachricht einen LLM-Call auslösen = teuer + langsam). Ein
    # Datei-Signal (Wort) oder eine Jahreszahl öffnet das Tor; danach darf
    # der LLM den Intent agentisch aus dem Satz verstehen.
    _vor_signal = [
        "lies", "lese", "was steht in", "inhalt von", "zeig mir den inhalt",
        "zeig mir den text", "fasse zusammen aus", "gib mir die datei",
        "suche", "finde", "zeig mir", "zeige mir", "datei", "dokument",
        "bild", "foto", "screenshot", "screen", "unterlagen", "download",
        "wo liegt", "hast du eine datei", "was liegt", "aufnahme",
        "heute", "gestern", "vorgestern",
    ]
    if not any(sig in f for sig in _vor_signal) and not _jahr_vorhanden:
        return "", []

    # Agentisch: LLM-Intent (Skill-Gate). Er versteht Jahr/Synonyme/Satzbau
    # UND entscheidet kontextbewusst, ob hier ueberhaupt ein Datei-/Bild-/
    # Inhaltszugriff gewollt ist (aktiv). Das eliminiert Fehltriigger aus
    # losen Woertern wie "zeig mir"/"heute"/"foto", wenn kein Datei-Wunsch.
    try:
        _intent = llm_service.extrahiere_datei_such_intent(frage)
    except Exception:
        _intent = None

    # SKILL-GATE (robust): Das Modell liefert aktiv (kontextuell). Entscheidend
    # ist aber die Kombination aus aktiv UND konkreten Datei-/Lese-Signalen im
    # Intent. Ein False bei aktiv darf ECHTE Dateizugriffe nicht toeten (sonst
    # Fehl-Tiigger der Gegenrichtung); bloße Plauderei (aktiv:false + KEIN
    # Datei-/Lese-Signal) wird abgewehrt.
    _hat_signal = bool(
        _intent is not None
        and (
            _intent.get("suchbegriff")
            or _intent.get("neueste")
            or _intent.get("jahr") is not None
            or _intent.get("ordner")
            or _intent.get("nur_bilder")
            or _intent.get("nur_dokumente")
            or _intent.get("erklaeren")
            or _intent.get("aufnahme_am") is not None
        )
    )
    _aktiv = bool(_intent is not None and _intent.get("aktiv", False))
    if _intent is not None and not _aktiv and not _hat_signal:
        return "", []
    _agent_pfad = bool(_intent is not None) and (_aktiv or _hat_signal)

    if _agent_pfad and _intent:
        reines_stichwort = _intent["suchbegriff"]
        neueste_zuerst = _intent.get("neueste", False)
        jahr = _intent.get("jahr")
        aufnahme_am = _intent.get("aufnahme_am") or None
        ordner_hinweis = _intent.get("ordner", "") or ""
        if _intent.get("nur_bilder"):
            nur_erweiterungen = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
        elif _intent.get("nur_dokumente"):
            nur_erweiterungen = {".pdf", ".doc", ".docx", ".txt", ".md", ".csv", ".xlsx", ".xls"}
        else:
            nur_erweiterungen = None
        lese_wunsch = bool(_intent.get("erklaeren"))
        will_erklaeren = bool(_intent.get("erklaeren"))
        stichwort = reines_stichwort or f
    else:
        # ── Heuristik (Fallback, falls kein LLM / kein plausibler Intent) ──
        # Signale (deutsch). "lies" zuerst für Stufe B.
        signale = [
            "lies", "lese", "was steht in", "inhalt von", "zeig mir den inhalt",
            "zeig mir den text", "fasse zusammen aus", "gib mir die datei",
            "suche", "finde", "zeig mir", "zeige mir", "datei", "dokument",
            "bild", "foto", "screenshot", "unterlagen", "download", "wo liegt",
            "hast du eine datei", "was liegt",
        ]
        trigger = next((s for s in signale if s in f), None)
        if not trigger and not _jahr_vorhanden:
            return "", []

        # "letzte/neueste" → nach Zeit sortieren (neueste zuerst).
        neueste_zuerst = any(w in f for w in ("letzte", "letzten", "neueste", "neuesten"))

        # Such-/Stichwort = Text nach dem Signal (grob bereinigt).
        stichwort = f[f.find(trigger) + len(trigger):].strip(" ?!,.:") if trigger else ""
        # Ein leeres Stichwort ist nur ok, wenn eine "letzte Bild/Screenshot"-
        # Suche läuft. Jahr allein ("Foto von 2025") öffnet den Weg ebenfalls,
        # dann wird ohne Namens-Match nach Zeit + Jahr gefiltert.
        bild_zeit_wunsch = neueste_zuerst and any(w in f for w in ("bild", "foto", "screenshot", "aufnahme"))
        if not stichwort and not bild_zeit_wunsch and not _jahr_vorhanden:
            return "", []
        jahr = None
        m = _re.search(r"\b(20\d{2})\b", f)
        if m:
            jahr = int(m.group(1))
        # relativer Tag (heute/gestern) → Tagesfilter; "vom Mai" bleibt ohne.
        aufnahme_am = None
        if "gestern" in f:
            aufnahme_am = "gestern"
        elif "heute" in f:
            aufnahme_am = "heute"
        elif "vorgestern" in f:
            aufnahme_am = "vorgestern"

        stopwoerter = {
            "das", "die", "der", "den", "dem", "des", "ein", "eine", "einen",
            "letzte", "letzten", "neueste", "neuesten", "aufgenommene",
            "aufgenommen", "bild", "foto", "erkläre", "erkläre", "mir", "ist",
            "und", "was", "da", "drauf", "darauf", "zeig", "zeige", "suche",
            # Füll-/Steuerwörter, die den eigentlichen Suchbegriff verschlucken:
            # "Lies den INHALT MEINER Lebenslauf-Datei" → Suchwort = lebenslauf.
            "inhalt", "inhalte", "meiner", "meine", "meinen", "mein",
            "wichtigsten", "wichtigen", "stationen", "zusammen", "fass",
            "fasse", "den", "die", "der", "und",
        }
        teile = []
        for w in stichwort.split():
            kern = w.strip(" ?!,.:;-_")
            if kern and kern not in stopwoerter:
                teile.append(kern)

        # Dokument-Themenwörter priorisieren.
        dokument_thema = next(
            (tema for tema in (
                "lebenslauf", "lebensläufe", "rechnung", "rechnungen", "vertrag",
                "verträge", "zeugnis", "zeugnisse", "angebot", "angebote",
                "bewerbung", "bewerbungen", "mietvertrag", "arbeitsvertrag",
                "lohnabrechnung", "gehaltsabrechnung", "letter",
            ) if tema in f),
            None,
        )
        if dokument_thema:
            reines_stichwort = dokument_thema
        else:
            reines_stichwort = " ".join(teile[:2]).strip()

        # Bei "letzte/neueste Bild/Foto/Screenshot" → alle nach Zeit sortiert,
        # kein Namens-Match nötig.
        if ("bild" in f or "foto" in f or "screenshot" in f or "aufnahme" in f) and neueste_zuerst:
            reines_stichwort = ""

        # Dateityp-Filter.
        nur_erweiterungen = None
        if "bild" in f or "foto" in f or "screenshot" in f or "aufnahme" in f:
            nur_erweiterungen = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
        elif ("pdf" in f or "dokument" in f or "datei" in f
              or "unterlagen" in f or "lebenslauf" in f or "vertrag" in f
              or "rechnung" in f or "bewerbung" in f):
            nur_erweiterungen = {".pdf", ".doc", ".docx", ".txt", ".md", ".csv", ".xlsx", ".xls"}

        # Stufe B: expliziter Lese-Wunsch → Inhalt lesen.
        lese_wunsch = bool(trigger) and trigger in (
            "lies", "lese", "was steht in", "inhalt von",
            "zeig mir den inhalt", "zeig mir den text",
            "gib mir die datei", "fasse zusammen aus")
        will_erklaeren = (
            "erklär" in f or "erkläre" in f or "drauf ist" in f
            or "was ist darauf" in f or "rate" in f or "welches" in f
            or "was ist das" in f or "was sieht" in f
            or ("bild" in f or "foto" in f or "screenshot" in f)
        )

        # Ordner-Hinweis.
        if "screenshot" in f:
            ordner_hinweis = "screenshot"
        elif "bild" in f or "foto" in f or "aufnahme" in f:
            ordner_hinweis = "kamera"
        else:
            ordner_hinweis = ""

    from app.services.datei_suche import lese_datei_info, suche_dateien

    try:
        treffer = suche_dateien(
            reines_stichwort,
            neueste_zuerst=neueste_zuerst,
            ordner_hinweis=ordner_hinweis,
            nur_erweiterungen=nur_erweiterungen,
            jahr=jahr,
            aufnahme_am=aufnahme_am,
        )
    except Exception:
        return "", []

    if (lese_wunsch or will_erklaeren) and treffer:
        # lese den ersten/passendsten Treffer (Inhalt) — bei "letzter/neueste"
        # nach Zeit sortiert, also das neueste Bild.
        datei = treffer[0]
        info = lese_datei_info(datei["pfad"])
        if info.get("ist_bild"):
            if info.get("data_url"):
                # Bild als Datei für den Vision-LLM (nicht in den Text)…
                # + Pfad mitgeben: in der Notiz SICHTBAR, damit der Nutzer
                # sieht, WELCHES Bild gefunden wurde (und es nachladen kann).
                # WICHTIG: Dateinamen der Kamera kodieren das Aufnahmedatum
                # (IMG_20260829_143240300 = 29.08.2026) — dem LLM explizit
                # sagen, dass es dieses Datum als Aufnahmedatum nennen soll.
                # Sonst parst ein diffuses Modell den Namen falsch („Jahr 5")
                # oder halluziniert ein anderes Datum.
                erkannt_notiz = ""
                try:
                    from app.services import face_service as _face
                    if _face.verfuegbar():
                        personen = (_face.erkenne_bild_pfad(datei["pfad"]).get("personen") or [])
                        namen = []
                        for _p in personen:
                            for _t in _p.get("treffer", []):
                                namen.append(_t["name"] + (" (sicher)" if _t.get("sicher") else " (unsicher)"))
                        if namen:
                            erkannt_notiz = " Erkennung per Gesichts-Embedding: " + "; ".join(sorted(set(namen))) + "."
                except Exception:
                    erkannt_notiz = ""
                return (
                    "\n\n[Datei-Bild zum Ansehen: " + datei["name"]
                    + " | Pfad: " + datei["pfad"] + erkannt_notiz
                    + ". Dieses Bild hat das Aufnahmedatum, das im Dateinamen "
                      "kodiert ist (Muster IMG_JJJJMMTT_HHMMSS oder "
                      "Screenshot_JJJJMMTT-HHMMSS): benenne diesen Zeitpunkt "
                      "als Aufnahmedatum bitte korrekt (JJJJ.JJ.TT …) und "
                      "erfinde KEIN anderes Datum.]",
                    [{"type": "image", "data_url": info["data_url"],
                      "pfad": datei["pfad"]}],
                )
            return f"\n\n[Datei-Bild: {datei['name']} (für Vision verfügbar)]", []
        if info.get("text"):
            return (
                "\n\n[Inhalt der Datei '" + datei["name"]
                + "':]\n" + info["text"][:8000]
                + "\nFasse dem Nutzer den Inhalt verständlich zusammen.]",
                [],
            )
        return f"\n\n[Datei '{datei['name']}' konnte nicht gelesen werden: {info.get('fehler')}]", []

    # Stufe A: nur Treffer-Liste (Name/Art).
    if not treffer:
        return (f"\n\n[Aus der Handy-Dateisuche zu '{reines_stichwort or stichwort}': "
                "KEINE Treffer. Sag dem Nutzer ehrlich, dass nichts gefunden wurde "
                "und erfinde KEINE Dateinamen. Frage nach einem anderen Begriff.]", [])
    zeilen = [f"- {t['name']}  ({t['erweiterung']})" for t in treffer[:10]]
    return (
        "\n\n[Aus der Handy-Dateisuche zu '"
        + (reines_stichwort or stichwort)
        + "':]\n"
        + "\n".join(zeilen)
        + "\nNenne dem Nutzer die gefundenen Dateien und frag, welche er verwenden will.]",
        [],
    )


def _verlauf_tool(frage: str, verlauf: Optional[Dict[str, list]] = None) -> str:
    """Chat-Verlauf-Suche als 'Tool' über Sprache (ohne UI).

    Erkennt Erinnerungs-/Rückblick-Signale ("was haben wir zu X gesagt",
    "erinnere mich an", "was war", "worum ging es bei") → sucht im
    Gesprächsverlauf (Volltext in `conversations`) → hängt die Treffer an die
    user_message, damit der LLM die Vergangenheit zitiert.

    `verlauf` ist injizierbar (Tests); Default ist das globale conversations-Dict.

    Liefert "" wenn kein Rückblick-Wunsch vorliegt.
    """
    if verlauf is None:
        verlauf = conversations
    signale = [
        "was haben wir", "was hatten wir", "erinnere mich an", "erinnerst du dich",
        "was war", "worum ging es", "was haben wir gesagt", "was haben wir besprochen",
        "was haben wir besprochen", "zurückblickend",
    ]
    f = frage.lower().strip()
    if not f:
        return ""
    trigger = next((s for s in signale if s in f), None)
    if not trigger:
        return ""
    # Stichwort = Text nach dem Signal, bereinigt um Stoppwörter ("zu / über /
    # wir / haben / gesagt / besprochen / ...") → nur der Kern bleibt.
    stichwort = f[f.find(trigger) + len(trigger):].strip(" ?!,.:")
    stopwoerter = {
        "zu", "über", "ueber", "wir", "haben", "hatten", "gesagt", "besprochen",
        "auch", "noch", "der", "die", "das", "den", "dem", "des", "ein", "eine",
        "einen", "einer", "und", "oder", "dazu", "mal",
    }
    teile = [w for w in stichwort.split() if w not in stopwoerter]
    stichwort = " ".join(teile).strip()
    if not stichwort or len(stichwort) < 2:
        return ""

    # Volltext-Suche im Verlauf (die eine Conversation).
    treffer = []
    for cid, nachrichten in verlauf.items():
        for n in nachrichten:
            inhalt = (n.get("content") or "")
            if stichwort in inhalt.lower():
                treffer.append({
                    "rolle": n.get("role", "?"),
                    "text": inhalt[:200],
                    "zeit": n.get("zeit") or "",
                })
    treffer.sort(key=lambda t: t.get("zeit") or "", reverse=True)
    if not treffer:
        return f"\n\n[Im Gesprächsverlauf zu '{stichwort}': nichts gefunden.]"
    zeilen = []
    for t in treffer[:5]:
        zeilen.append(f"({t['rolle']}) {t['text']}")
    return (
        "\n\n[Aus dem Gesprächsverlauf zu '"
        + stichwort
        + "':]\n"
        + "\n".join(zeilen)
        + "\nZitiere dem Nutzer die relevanten Stellen aus der Vergangenheit.]"
    )


def _hole_kontext_summary(conversation_id: str, historie: list, frage: str) -> tuple:
    """Holt das Rolling-Summary der Conversation (+ rollt bei Bedarf neu).

    Liefert (summary_text, gerollt). Rollt nur, wenn die Historie über der
    Schwelle liegt UND genug neue Nachrichten seit dem letzten Roll kamen
    (Rate-Limit → günstig). Erhöht den Zähler bei jedem Aufruf.
    """
    from app.services import chat_verlauf, kontext_service
    summary_eintrag = chat_verlauf.summary_holen(conversation_id)
    summary = str(summary_eintrag.get("text") or "")
    anzahl_seit = int(summary_eintrag.get("anzahl_seit_roll") or 0)

    # Kontext-Paket bauen (Rolling-Summary-Logik).
    ergebnis = kontext_service.baue_kontext(
        historie, frage,
        memory_extractor=None,           # Erinnerungen kommen separat in llm_service
        gespeichertes_summary=summary,
        anzahl_seit_roll=anzahl_seit,
    )
    if ergebnis["gerollt"]:
        chat_verlauf.summary_setzen(conversation_id, ergebnis["summary"])
    # Zähler fürs künftige Roll-Limit erhöhen.
    chat_verlauf.summary_erhoehe_zaehler(conversation_id)
    return ergebnis["summary"], ergebnis["gerollt"]


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Wie /chat, liefert die Antwort aber Stück für Stück (Server-Sent Events)."""
    # Gleiche Weiche wie in /chat: Coding-Auftraege weiterleiten. Bei
    # hochgeladenen Dateien (request.files) NICHT als Coding-Auftrag einordnen
    # — ein Dokument-/Bild-Upload ist eine Verständnis-/Analyse-Frage an den
    # LLM. Zusätzlich stößt ein Fähigkeits-Grenzthema (Terminal/Datei/System)
    # an Hermes als Toolcall, auch wenn ist_auftrag es nicht als Coding sieht.
    ist_auftrag_val = False
    begruendung, kategorie, komplexitaet = "", None, None
    # Umlenk-Ziel erzwingt den Track direkt (Umlenk-Buttons):
    #   ziel="pc"    → Track A (PC-Hermes), egal was die Erkennung sagt
    #   ziel="handy" → Track C (lokaler Hermes) direkt
    #   ziel="agent" → lokaler LLM (nie Hermes)
    if request.ziel == "pc" or request.ziel == "handy":
        ist_auftrag_val = True
        begruendung = f"Umlenk-Button (ziel={request.ziel})"
        kategorie = "feature"
        komplexitaet = "mittel"
    elif request.ziel == "agent" or request.force_agent:
        ist_auftrag_val = False
    elif not request.files:
        ist_auftrag_val, begruendung, kategorie, komplexitaet = ist_auftrag(request.message)
        if not ist_auftrag_val and stoesst_an_grenze(request.message):
            ist_auftrag_val = True
            begruendung = "Fähigkeits-Grenze (Terminal/Datei/System) – Hermes als Toolcall"
            kategorie = "feature"
            komplexitaet = "mittel"
    else:
        begruendung, kategorie, komplexitaet = "", None, None
    if ist_auftrag_val:
        # Kontext-Erweiterung: Frage + Gesprächskontext, damit Hermes nicht
        # blind (nur mit der Frage) arbeitet. (Gleiche Logik wie im Router.)
        kontext_paket = _baue_kontext(request.message)
        herm_aufgabe = request.message
        if kontext_paket and kontext_paket.strip():
            herm_aufgabe = (
                f"{request.message}\n\n"
                "[Kontext aus dem Gespräch (vorherige Nachrichten/Erinnerungen):]\n"
                f"{kontext_paket.strip()}"
            )
        # Wie /chat: erst PC-Hermes (Track A), dann lokalen Hermes
        # (Track C). Nur wenn beides nicht verfuegbar ist, geht der
        # Auftrag ins Buch (Track B).
        hermes_antwort = hermes_gateway.sende_auftrag(herm_aufgabe)
        if hermes_antwort is not None:
            conversation_id = _get_or_create_conversation(request.conversation_id)
            _finish_exchange(conversation_id, request.message, hermes_antwort)
            # Auftrag im Buch anlegen (für die Umlenk-Buttons: /wechseln-handy
            # braucht eine auftrag_id; ohne Buch-Eintrag gibt es keine).
            auftrag_id = ""
            try:
                eintrag = auftrag_service.anlegen(
                    herm_aufgabe, begruendung, kategorie, komplexitaet
                )
                auftrag_id = eintrag["id"]
                auftrag_service.setze_chat_verknuepfung(auftrag_id, conversation_id)
            except Exception:
                pass
            def pc_baer_ereignisse():
                yield _sse({"message": hermes_antwort, "ziel": "pc",
                            "auftrag_id": auftrag_id})
                yield _sse({"done": True, "conversation_id": conversation_id,
                            "memories_used": 0, "memories_created": 0,
                            "memory_count": memory_service.get_memory_count(),
                            "archiv_used": 0, "sources": [], "ziel": "pc"})
            return StreamingResponse(
                pc_baer_ereignisse(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        # Track C: Lokaler Hermes startet die Aufgabe im Hintergrund und
        # strahlt Gedanken + Ergebnis live ins Auftragsbuch.
        if hermes_local_ist_verfuegbar():
            # Gespraech ERST anlegen/ermitteln, damit die Verknuepfung
            # vor dem Thread-Start an den Worker geht und das Gespraech
            # im conversations-Dict bereits existiert, wenn die ersten
            # Hermes-Zwischenmeldungen eintreffen.
            conversation_id = _get_or_create_conversation(request.conversation_id)
            eintrag = _starte_lokale_hermes(
                herm_aufgabe,
                hinweis=f"Automatische Erkennung: {begruendung}",
                kategorie=kategorie,
                komplexitaet=komplexitaet,
                chat_verknuepfung=conversation_id,
                kontext=_baue_kontext(request.message),
            )
            reply_text = (
                "🧩 **Hermes-Aufgabe erkannt – erweitertes Werkzeug übernimmt.**\n\n"
                "➡️ **Weitergeleitet an:** Hermes (Handy)\n\n"
                f"📋 **Aufgabe:** {request.message[:150]}…\n\n"
                "Gedanken & Zwischenschritte erscheinen hier live, das "
                "Endergebnis danach.\n"
            )
            _finish_exchange(conversation_id, request.message, reply_text)
            # Verknuepfung Auftrag <-> Gespraech setzt _starte_lokale_hermes
            # bereits VOR dem Thread-Start; kein zweites setzen noetig.

            return StreamingResponse(
                _strom_auftrag_live(eintrag["id"], conversation_id, reply_text),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        eintrag = auftrag_service.anlegen(
            herm_aufgabe,
            hinweis=f"Automatische Erkennung: {begruendung}",
            kategorie=kategorie,
            komplexitaet=komplexitaet,
        )
        reply_text = (
            "🧩 **Hermes-Aufgabe erkannt – wird übernommen.**\n\n"
            "➡️ **Weitergeleitet an:** Hermes\n\n"
            f"📋 **Aufgabe:** {request.message[:150]}…\n\n"
            "Hermes nimmt sich der Aufgabe an. Sobald ein Ergebnis vorliegt, "
            "erscheint es hier.\n"
        )
        conversation_id = _get_or_create_conversation(request.conversation_id)
        _finish_exchange(conversation_id, request.message, reply_text)
        # Auftrag an das Gespraech binden, damit Hermes-Live-Meldungen
        # (Zwischenschritte, Ergebnis) den persistenten Verlauf füllen.
        auftrag_service.setze_chat_verknuepfung(eintrag["id"], conversation_id)

        def auftrag_ereignisse():
            # In zwei Teile zerlegt: erst Text, dann fertig - die UI haengt
            # ihr "fertig"-Handle an das done-Event.
            yield _sse({"message": reply_text, "ziel": "buch"})
            yield _sse({
                "done": True,
                "conversation_id": conversation_id,
                "memories_used": 0,
                "memories_created": 0,
                "memory_count": memory_service.get_memory_count(),
                "archiv_used": 0,
                "sources": [],
                "ziel": "buch",
            })

        return StreamingResponse(
            auftrag_ereignisse(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    conversation_id = _get_or_create_conversation(request.conversation_id)
    history = conversations[conversation_id]
    memories = memory_service.retrieve_relevant_memories(request.message, top_k=5)
    archiv = _archiv_treffer(request.message, request.archiv)

    def ereignisse():
        teile: List[str] = []
        quellen: List[Dict[str, str]] = []
        # Vor dem try initialisieren: Der finally-Zweig (auch bei GeneratorExit /
        # Client-Abbruch mitten in der Verarbeitung) greift auf s_werkzeug_bilder
        # zu, um den Bildpfad in den Verlauf zu schreiben. Ohne Vorab-Init wäre
        # er dort eine ungebundene Variable.
        s_werkzeug_bilder: List[dict] = []
        try:
            # Rolling-Summary + Datei-Tool auch hier (Stream = gleicher Kontext)
            try:
                s_conv_id = _get_or_create_conversation(request.conversation_id)
                s_history = conversations.get(s_conv_id, [])
                s_summary, _ = _hole_kontext_summary(s_conv_id, s_history, request.message)
                s_hist_begrenzt = s_history[-15:]
                # Archiv-Frage hat VORRANG: keine Dateisuche bei Archiv-Ziel
                # (gleiche Kette wie in /chat, damit beide Wege identisch
                # antworten).
                s_werkzeug_text = _archiv_tool(request.message)
                s_werkzeug_bilder = []
                if not s_werkzeug_text:
                    s_werkzeug_text, s_werkzeug_bilder = _datei_tool(request.message)
                    if not s_werkzeug_text:
                        s_werkzeug_text = _verlauf_tool(request.message)
                s_user = (request.message + (s_werkzeug_text or "") + _zitat_anhang(request)
        + _gesichtsabgleich_notiz(request, s_werkzeug_bilder))
                # Live-Status (Fortschritts-Feedback): Zeigt dem Nutzer, was
                # gerade passiert, statt nur "Denke nach...".
                if s_werkzeug_bilder:
                    yield _sse({"status": "🔍 Suche in deinen Dateien/Bildern…"})
                elif s_werkzeug_text and ("Archiv" in s_werkzeug_text
                                          or "Gesprächsverlauf" in s_werkzeug_text):
                    yield _sse({"status": "🔎 Sage ich dir aus dem Archiv/Verlauf…"})
                elif s_werkzeug_text:
                    yield _sse({"status": "🔍 Suche in deinen Dateien…"})
                else:
                    yield _sse({"status": "🤔 Agent überlegt…"})
            except Exception:
                s_werkzeug_bilder = []
                s_summary, s_hist_begrenzt, s_user = "", history, request.message
            # Gesichter reaktiv 'merken' (wie in /chat). Das Frontend nutzt
            # standardmäßig /api/chat/stream — fehlte diese Logik hier, würde
            # 'das ist Pedi' / 'das bin ich' beim normalen Chat NIE gespeichert.
            # Läuft nur bei aktiver Bild-Ansicht (Dateisuche ODER Upload) +
            # Personennenn-Signal; das betrachtete Bild wird als Referenz-
            # Miniatur an die Person gekoppelt.
            s_bild_aktiv = bool(s_werkzeug_bilder) or bool(
                request.files and any(f.type == "image" for f in request.files)
            )
            s_aktuelles_bild = ""
            if s_werkzeug_bilder and s_werkzeug_bilder[0].get("data_url"):
                s_aktuelles_bild = s_werkzeug_bilder[0]["data_url"]
            elif request.files:
                s_upload_img = next(
                    (f for f in request.files if f.type == "image" and f.data_url),
                    None,
                )
                if s_upload_img:
                    s_aktuelles_bild = s_upload_img.data_url
            s_merkhinweis = _gesichter_merke(
                request.message, s_bild_aktiv, str(s_aktuelles_bild or ""),
                embedding=_embedding_aus_data_url(str(s_aktuelles_bild or ""))
                if s_bild_aktiv and s_aktuelles_bild else None,
            )
            if s_merkhinweis:
                s_user += s_merkhinweis
            # Vision-Routing (wie /chat): Bild → vision-fähiges Modell.
            s_modell = request.model or ""
            if s_werkzeug_bilder and not (s_modell and (
                    "gemini" in s_modell or "gpt-4o" in s_modell
                    or "gpt-5" in s_modell or "sonnet" in s_modell
                    or "claude" in s_modell)):
                s_modell = "google/gemini-2.5-flash"
            try:
                for ereignis in llm_service.chat_stream(
                    user_message=s_user,
                    conversation_history=s_hist_begrenzt,
                    memories=memories,
                    web_search=request.web_search,
                    model=s_modell,
                    no_retention=request.no_retention,
                    archiv=archiv,
                    summary=s_summary,
                    files=(
                        [f.model_dump() for f in request.files] if request.files else []
                    ) + (s_werkzeug_bilder if s_werkzeug_bilder else []),
                ):
                    if ereignis.get("sources"):
                        quellen.extend(ereignis["sources"])
                        yield _sse({"sources": ereignis["sources"]})
                        continue
                    stueck = ereignis.get("delta")
                    if stueck:
                        teile.append(stueck)
                        yield _sse({"delta": stueck})
            except Exception as e:
                logger.error("Streaming fehlgeschlagen: %s", e)
                # Übersetzt Ablehnungen wegen der Datenschutz-Einstellungen in
                # einen Satz, der sagt, was zu tun ist.
                yield _sse({"error": llm_service.fehlertext(e)})
        finally:
            # Läuft auch bei Abbruch durch den Client (Bildschirmsperre,
            # Verbindungsverlust). Hier wird bewusst nichts gesendet – ein
            # yield waehrend GeneratorExit wuerde einen Fehler ausloesen.
            anzahl_neu = _finish_exchange(
                            conversation_id, request.message + _zitat_anhang(request), "".join(teile),
                            bild_pfad=(
                                s_werkzeug_bilder[0].get("pfad")
                                if s_werkzeug_bilder else None
                            ) or _upload_bild_pfad(request),
                        )

        # Wird uebersprungen, wenn der Client abgebrochen hat.
        yield _sse({
            "done": True,
            "conversation_id": conversation_id,
            "memories_used": len(memories),
            "memories_created": anzahl_neu,
            "memory_count": memory_service.get_memory_count(),
            "archiv_used": len(archiv),
            # Nochmals gesammelt – falls ein Zwischenereignis verloren ging.
            "sources": quellen,
            # Bild-Vorschau (flüchtig): data_url + Pfad für die Chat-Miniatur.
            "bild_vorschau": (
                s_werkzeug_bilder[0]["data_url"] if s_werkzeug_bilder else None
            ),
            "bild_pfad": (
                s_werkzeug_bilder[0].get("pfad") if s_werkzeug_bilder else None
            ),
        })

    return StreamingResponse(
        ereignisse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # verhindert Pufferung durch Zwischenschichten
        },
    )


@router.delete("/chat/letzte-runde")
async def letzte_runde_entfernen(conversation_id: str = ""):
    """Entfernt die letzte Nutzer-Nachricht samt Antwort aus dem Verlauf.

    **Seit 2026-08-31 gesperrt** (Verlauf ist STRENG append-only,
    Sebastian-Regel): Liefert immer entfernt=false und entfernt nichts.
    Der frühere Bearbeiten-Flow entfernte die letzte Runde; jetzt bleibt die
    alte Runde stehen und neue Formulierung/Antwort werden ANGEHÄNGT.
    Ohne conversation_id gilt die eine durchlaufende Conversation (conv_main).
    """
    cid = conversation_id or chat_verlauf._AKTIVE_CONVERSATION_ID
    entfernt = chat_verlauf.verlauf_runde_entfernen(cid)
    return {"entfernt": entfernt, "conversation_id": cid}


@router.get("/conversations")
async def list_conversations():
    """List all active conversations."""
    return {
        "conversations": [
            {
                "id": cid,
                "message_count": len(msgs),
                "last_message": msgs[-1]["content"][:100] if msgs else "",
            }
            for cid, msgs in conversations.items()
        ],
        "total": len(conversations),
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Liefert die Nachrichten eines Gespraechs.

    Seit Stand 2026-08-30 gibt es NUR EINE durchlaufende Conversation
    (conv_main). Ein alter Einzel-Chat (alte ID im localStorage, z. B. conv_8)
    wird deshalb transparent auf die aktive Conversation umgeleitet statt 404 —
    so sieht der Nutzer nach einem Update weiterhin seinen fortlaufenden Chat,
    statt dass ein leerer/verwaister Chat entsteht.
    """
    # Unbekannte/alte ID → aktive Conversation (conv_main) statt 404.
    if conversation_id not in conversations:
        conversation_id = chat_verlauf._AKTIVE_CONVERSATION_ID
    # Nach dem Mapping fehlt die ID nur noch, wenn selbst conv_main leer fehlt.
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Gespräch nicht gefunden")
    return {
        "id": conversation_id,
        "messages": conversations[conversation_id],
    }


@router.get("/suche")
async def chat_suche(q: str = Query("", max_length=300)):
    """Volltextsuche im Gesprächsverlauf (Ein-Chat).

    Durchsucht alle Nachrichten aller Conversations (in der Regel die eine
    fortlaufende) nach dem Stichwort und liefert Treffer mit Kontext + Uhrzeit.
    Damit kann man „was haben wir zu X gesagt?" beantworten — ohne Handy-Archiv.

    Liefert max. 20 Treffer, sortiert nach dem neuesten zuerst.
    """
    query = q.lower().strip()
    if not query or len(query) < 2:
        return {"treffer": [], "anzahl": 0, "hinweis": "Suchbegriff (>=2 Zeichen) angeben"}

    treffer = []
    for cid, nachrichten in conversations.items():
        for n in nachrichten:
            inhalt = (n.get("content") or "")
            if query in inhalt.lower():
                treffer.append({
                    "conversation": cid,
                    "rolle": n.get("role", "?"),
                    "text": inhalt[:300],
                    "zeit": n.get("zeit") or "",
                })
    treffer.sort(key=lambda t: t.get("zeit") or "", reverse=True)
    return {"treffer": treffer[:20], "anzahl": len(treffer), "hinweis": ""}