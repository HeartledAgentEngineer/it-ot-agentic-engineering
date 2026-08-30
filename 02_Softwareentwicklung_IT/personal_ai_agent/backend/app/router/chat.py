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

from app.config import settings
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


def _starte_lokale_hermes(
    auftrag: str,
    hinweis: str,
    kategorie: Optional[str],
    komplexitaet: Optional[str],
    chat_verknuepfung: Optional[str] = None,
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
                for ereignis in hermes_local_stream_auftrag(auftrag_id, auftrag):
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
            request.message, bild_aktiv, str(aktuelles_bild_data or "")
        )
        if merkhinweis:
            user_message_fuer_llm += merkhinweis


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

        # 3./4. Verlauf fortschreiben und Erinnerungen ableiten
        memories_created = _finish_exchange(conversation_id, request.message, reply)

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


def _gesichter_merke(
    frage: str, bild_aktiv: bool, referenz_bild: str = ""
) -> str:
    """Reaktiv 'Gesichter merken' über Sprache (ohne UI, deterministisch).

    Erkennt beim Betrachten eines Bildes die Angabe, WER darauf abgebildet
    ist — z. B. 'das ist Pedi' oder 'das ist meine Oma Helga' — und
    übernimmt die Person (Name + ggf. Rolle) in den Gesichter-Katalog
    (`gesichter_service.person_speichern`). Zusätzlich wird das gerade
    betrachtete Bild (`referenz_bild` als data_url) als Referenz-Miniatur
    an die Person gekoppelt — damit der spätere Abgleich per echtem
    Bild-zu-Bild-Vergleich läuft und nicht nur über den Namens-Kontext
    (entscheidend z. B. um einen Zwillingsbruder zu unterscheiden).

    Konservativ: läuft nur, wenn gerade wirklich ein Bild betrachtet wird
    (`bild_aktiv`), also z. B. aus der Dateisuche angehängt oder hochgeladen
    wurde. Ohne Bild wird NICHTS gemerkt (kein versehentliches Speichern,
    z. B. wenn jemand über ein gedachtes 'das ist die beste Idee' redet).
    Zudem wird nur bei einer Personen-Nenn-Phrase ausgelöst. Die eigentliche
    Bestätigung (Name + Rolle sauber trennen) macht der LLM im Prompt — hier
    wird nur etwas an die user_message gehängt.

    Returns: Anweisungs-Text für den LLM (an die user_message anzuhängen),
    oder "" wenn nichts zu merken ist.
    """
    if not bild_aktiv or not frage or len(frage.strip()) < 3:
        return ""
    f = frage.lower().strip()
    if not any(m in f for m in _PERSON_NENN_MUSTER):
        return ""
    # Nur Personennamen (mit Groß-/Unter-Häufung) nach einem Nenn-Muster.
    import re as _re
    # Große Anfangsbuchstaben = Eigenname. Aus der Nenn-Phrase den eigentlichen
    # Namen (= letztes großgeschriebenes Wort) und ggf. die Rolle davor
    # nehmen: 'das ist Oma Helga' → Rolle: Oma, Name: Helga. 'das ist Pedi'
    # → nur Name Pedi.
    m = _re.search(r"(?:das ist|das hier ist|das dort ist|das ist doch|das ist auf)"
                   r"(?: die| der| meine| mein| unsere| unser)?\s+(.+?)\s*[.!?]?\s*$",
                   frage)
    if not m:
        return ""
    rest = m.group(1).strip()
    woerter = _re.findall(r"[A-ZÄÖÜ][a-zäöüß]+", rest)
    if not woerter:
        return ""
    # Der Name ist das letzte großgeschriebene Wort, das KEIN Familien-/
    # Eigenschaftswort aus der Ausschlussliste ist. 'das ist die beste Idee' →
    # woerter = ["Idee"] (Ausschluss) → Name leer → nichts speichern.
    name = next((w for w in reversed(woerter) if w.lower() not in _KEINE_PERSON_ROLLE), "")
    if not name:
        return ""
    # Rolle = vorletztes Wort, falls es eine bekannte Familienrolle ist
    # ('das ist Oma Helga' → Name Helga, Rolle Oma). Nicht-Familien-Wörter
    # davor werden NICHT als Rolle übernommen.
    rolle = ""
    for w in reversed(woerter):
        if w == name:
            continue
        if w.lower() in _KEINE_PERSON_ROLLE and w.lower() not in (
                "beste", "schönste", "größte", "groesste", "blau", "rot", "grün",
                "gruen", "gelb", "schwarz", "weiß", "weiss",
                "idee", "haus", "auto", "sache", "ding", "bild", "foto",
                "screenshot", "tasse", "buch", "vase", "tisch", "hund", "katze",
                "straße", "plastikmull"):
            rolle = w
            break
    try:
        gesichter_service.person_speichern(
            name=name, rolle=rolle,
            beziehung="",
            beschreibung="",
            referenz_bild_pfad="",
            # Das gerade betrachtete Bild als Referenz-Miniatur einbetten
            # (falls verfügbar). Nur data_url; Original bleibt unangetastet.
            referenz_bild_miniatur=(referenz_bild or "").strip(),
        )
    except Exception:
        # Merken ist Bonus — darf den Chat nie brechen.
        return ""
    hat_bild = bool((referenz_bild or "").strip())
    hinweis = (f"Erkannte Person '{name}'" + (f" (Rolle: {rolle})" if rolle else "")
               + "wurde dem Gesichter-Katalog hinzugefügt"
               + (f" und mit diesem Bild als Referenz versehen" if hat_bild else "")
               + ". Sag dem Nutzer kurz, dass du die Person gespeichert hast und "
               "sie künftig auf Fotos erkennst (per Bild-Vergleich wenn ein "
               "Referenzbild vorhanden ist). "
               "Achtung bei einander stark ähnlichen Personen (z. B. "
               "Zwillingsbrüder): Wenn zwei Personen verwechselbar aussehen, "
               "sage ehrlich, wenn du unsicher bist, statt zu raten — \"das "
               "kann ich nicht zuverlässig unterscheiden\" ist erlaubt und "
               "besser als eine erfundene Zuordnung. Erfinde KEINE Details.")
    return f"\n\n[Hinweis für den Assistenten: {hinweis}]"


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
    ]
    if not any(sig in f for sig in _vor_signal) and not _jahr_vorhanden:
        return "", []

    # Agentisch: LLM-Intent versuchen (versteht Jahr/Synonyme/Satzbau).
    _agent_pfad = None
    try:
        _intent = llm_service.extrahiere_datei_such_intent(frage)
        _agent_pfad = (
            _intent["suchbegriff"] != "" or _intent["neueste"]
            or _intent["jahr"] is not None or _intent["ordner"] != ""
            or _intent["nur_bilder"] or _intent["nur_dokumente"]
            or _intent["erklaeren"]
        )
    except Exception:
        _intent, _agent_pfad = None, False

    if _agent_pfad and _intent:
        reines_stichwort = _intent["suchbegriff"]
        neueste_zuerst = _intent.get("neueste", False)
        jahr = _intent.get("jahr")
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
                return (
                    "\n\n[Datei-Bild zum Ansehen: " + datei["name"]
                    + " | Pfad: " + datei["pfad"]
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
            "🧩 **Hermes-Aufgabe erkannt – wird bearbeitet.**\n\n"
            "➡️ **Weitergeleitet an:** Auftragsbuch\n\n"
            f"📋 **Aufgabe:** {request.message[:150]}…\n\n"
            "Hermes nimmt sich der Aufgabe an. Sobald ein Ergebnis vorliegt, "
            "erscheint es live hier.\n"
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
                s_user = request.message + (s_werkzeug_text or "")
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
                conversation_id, request.message, "".join(teile)
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

    Wird vom „Bearbeiten"-Flow im Frontend genutzt: Legt der Nutzer eine
    User-Nachricht zurück in die Eingabe zum Neu-Formulieren, soll die alte
    Runde dauerhaft aus dem persistenten Verlauf (conv_main) verschwinden —
    sonst tauchte sie nach einem Reload wieder auf. Ohne conversation_id wird
    die eine durchlaufende Conversation (conv_main) verwendet.
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