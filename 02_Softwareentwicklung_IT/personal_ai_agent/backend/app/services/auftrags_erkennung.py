"""Erkennt, ob eine Nachricht ein Coding-Auftrag fuer den Agenten ist.

Zweck: Die Oberflaeche spricht immer in denselben /api/chat-Eingang.
Doch nicht jede Nachricht soll der lokale LLM beantworten - eine
Programmier-/Werkzeugaufgabe gehoert ins Auftragsbuch, damit Hermes sie
uebernimmt.

Wie entschieden wird (18.08.2026 umgebaut):

  1. Signalpraefix ("Auftrag:", "Aufgabe:", ...) - sofort Auftrag, ohne
     Rueckfrage ans Modell. Kostenlos und unmissverstaendlich.
  2. Sonst entscheidet das Sprachmodell.
  3. Faellt das Modell aus, greift die Wortheuristik als Notnagel.

Warum nicht mehr allein die Heuristik: Sie hat am 17.08. die Frage
"Ich mache gerade Roggensteaks ... wie lange muss ich die von jeder Seite
braten?" als "feature, mittel" ins Auftragsbuch gelegt. Zwei Ursachen, beide
im alten Code nachweisbar:

  * Die Verbpruefung lief ueber die Verbliste statt ueber die Woerter der
    Nachricht (`for w in _AUFTRAGS_VERBEN` bei gleichzeitigem
    `w in _AUFTRAGS_VERBEN`) und war damit immer wahr. Die daneben
    berechnete Wortliste wurde nie benutzt.
  * Die Objektpruefung suchte Teilzeichenketten. In "von jeder Seite"
    steckt "seite".

Beides ist unten repariert. Trotzdem bleibt die Heuristik nur der Notnagel:
Auftraege werden hier frei diktiert ("das soll geaendert werden", "achtet
darauf, dass die Versionierung angepasst werden muss"), und solche Saetze
enthalten selten das Wort, auf das eine Liste wartet. Wortregeln koennen das
nicht - ein Modell kann es.
"""
import json
import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Verb, das einen Arbeitsauftrag ausloest.
_AUFTRAGS_VERBEN = frozenset((
    # Deutsch
    "erstelle", "schreibe", "baue", "fixe", "aendere", "ändere",
    "implementiere", "programmiere", "verwende", "ergaenze", "ergänze",
    "entferne", "optimiere", "refaktoriere", "loesche", "lösche",
    "aktualisiere", "konfiguriere", "richte", "installiere", "setze",
    "generiere", "fuege", "füge", "passe", "verbessere", "korrigiere",
    "behebe", "repariere",
    # Englisch
    "create", "write", "build", "fix", "change", "add", "implement",
    "program", "update", "refactor", "optimize", "delete", "configure",
    "setup", "make", "generate", "improve", "correct",
))

# Gegenstaende, die einen Coding-/Werkzeug-Bezug herstellen.
#
# "seite"/"seiten" stehen bewusst nicht mehr darin: Der Gewinn (jemand meint
# eine Webseite) wiegt den Fehlalarm nicht auf (Seite eines Steaks, Seite
# eines Buches). Wer eine Webseite meint, schreibt fast immer auch
# "frontend", "html" oder "oberflaeche" dazu.
_OBJEKTE = frozenset((
    # Code / Projekt
    "code", "datei", "dateien", "projekt", "funktion", "klasse", "modul",
    "script", "skript", "endpoint", "route", "api", "logik",
    "test", "tests", "backend", "frontend", "app", "programm", "robotik",
    "sps", "steuerung", "library", "bibliothek", "paket", "abhaengigkeit",
    "dependency", "modell", "config", "konfiguration", "model",
    "button", "oberflaeche", "oberfläche", "design", "html", "css",
    "cache", "commit", "repo", "repository", "versionierung",
    # Agent / System
    "agent", "agenten", "hermes", "server", "dienst", "service", "tool",
    "werkzeug", "plugin", "skill", "wissensdatenbank", "datenbank",
    # Aenderungen an vorhandenem
    "bug", "syntaxfehler",
))

# Signalsaetze fuer bedingungslose Auftraege
_SIGNAL_PRAEFIXE = (
    "auftrag:", "aufgabe:", "to do:", "todo:", "task:",
)

# Woerter, die auf einen Bug hinweisen
_BUG_SIGNALE = (
    "bug", "fehler", "kaputt", "defekt", "stuerzt", "absturz",
    "crasht", "broken", "error", "falsch", "nicht richtig",
    "funktioniert nicht", "geht nicht", "exception", "traceback",
)

# Woerter, die auf Refactoring hinweisen
_REFACTOR_SIGNALE = (
    "refaktor", "umbau", "umstellen", "neu organisieren",
    "clean up", "aufraeumen", "verbessern", "optimieren",
    "schneller", "performance", "wartbar",
)

# Komplexitaetssignale
_KOMPLEX_SIGNALE = (
    "datenbank", "multi", "parallel", "thread", "async",
    "verschluesselung", "authentifizierung", "oauth", "api",
    "microservice", "container", "docker", "komplex",
)

_EINFACH_SIGNALE = (
    "klein", "kurz", "einfach", "schnell", "minimal",
    "typo", "rechtschreibung", "farbe", "text",
)

# Zerlegt einen Text in Woerter. Die Zeichenklasse laesst Umlaute stehen,
# die Listen oben fuehren beide Schreibweisen.
_WORT = re.compile(r"[^\W\d_]+", re.UNICODE)


def _woerter(text: str) -> frozenset:
    """Die Woerter einer Nachricht, klein geschrieben, ohne Satzzeichen."""
    return frozenset(_WORT.findall(text.lower()))


def kategorisiere(nachricht: str) -> str:
    """Bestimmt die Kategorie des Auftrags."""
    text = nachricht.lower()

    # Bug? (Prioritaet)
    for signal in _BUG_SIGNALE:
        if signal in text:
            return "bug"

    # Refactor?
    for signal in _REFACTOR_SIGNALE:
        if signal in text:
            return "refactor"

    # Standardmaessig Feature
    return "feature"


def schaetze_komplexitaet(nachricht: str) -> str:
    """Schaetzt die Komplexitaet des Auftrags.

    Wird seit 18.08.2026 nirgends mehr angezeigt - der Wert landet nur noch
    als Feld im Auftragsbuch. Als Zeitansage im Chat war er eher
    irrefuehrend als hilfreich.
    """
    text = nachricht.lower()

    einfachi = sum(1 for s in _EINFACH_SIGNALE if s in text)
    if einfachi >= 2 or any(text.startswith(s) for s in ("klein", "kurz", "schnell")):
        return "einfach"

    for signal in _KOMPLEX_SIGNALE:
        if signal in text:
            return "komplex"

    # Reihenfolge umgedreht: Vorher stand die 200er-Schwelle zuerst und
    # verschluckte die 500er - laengere Texte wurden nie "komplex".
    if len(text) > 500:
        return "komplex"
    if len(text) > 200:
        return "mittel"

    return "mittel"


# ---------------------------------------------------------------------------
# Notnagel: Wortheuristik
# ---------------------------------------------------------------------------

def heuristik_ist_auftrag(nachricht: str) -> bool:
    """Wortregeln - nur noch Rueckfallebene, wenn das Modell ausfaellt.

    Verlangt beides: ein Auftrags-Verb als eigenstaendiges Wort UND einen
    Gegenstand mit System-Bezug, ebenfalls als Wort. Beide Pruefungen waren
    vorher unwirksam (siehe Modulkopf).
    """
    woerter = _woerter(nachricht)
    if not woerter & _AUFTRAGS_VERBEN:
        return False
    if not woerter & _OBJEKTE:
        return False
    return True


# ---------------------------------------------------------------------------
# Entscheider: Sprachmodell
# ---------------------------------------------------------------------------

_ANWEISUNG = """Du sortierst eingehende Nachrichten fuer einen Coding-Agenten.

AUFTRAG bedeutet: Der Nutzer will, dass an SEINER Software etwas getan wird -
Code, Oberflaeche, Server, Konfiguration, Tests, Dokumentation, Repository.
Das gilt auch, wenn der Wunsch frei gesprochen und wirr formuliert ist
("das soll geaendert werden", "achtet darauf, dass die Versionierung
angepasst wird", "die Blase sieht bloed aus, mach das anders").

GESPRAECH bedeutet: alles andere. Wissensfragen, Alltag, Kochen, Rechnen,
Termine, Erklaerungen, Fragen ueber den Agenten selbst, Smalltalk - auch
dann, wenn technische Woerter darin vorkommen.

Beispiele:
- "Wie lange muss ich ein 3 cm dickes Steak von jeder Seite braten?" -> GESPRAECH
- "Erklaer mir, wie ein Vektorspeicher funktioniert" -> GESPRAECH
- "Was kostet DeepSeek pro Million Token?" -> GESPRAECH
- "Der Ladebalken im Frontend ruckelt, bau das um" -> AUFTRAG
- "Wir brauchen noch Tests fuer den Auftrags-Service" -> AUFTRAG
- "achte drauf dass der Cache-Buster hochgezaehlt wird" -> AUFTRAG

Antworte mit genau einem JSON-Objekt, ohne Text davor oder danach:
{"auftrag": true, "grund": "kurze Begruendung"}"""


def _modell_entscheidet(nachricht: str) -> Optional[Tuple[bool, str]]:
    """Fragt das Sprachmodell. None heisst: keine verwertbare Antwort.

    Bewusst kein Weiterreichen der Ausnahme: Faellt OpenRouter aus, soll der
    Chat weiterlaufen und die Heuristik uebernehmen - nicht die ganze
    Nachricht scheitern.
    """
    try:
        from app.services.llm_service import llm_service
    except Exception as fehler:            # pragma: no cover - Importschutz
        logger.warning("LLM-Dienst nicht ladbar: %s", fehler)
        return None

    if not getattr(llm_service, "is_configured", False):
        return None

    try:
        antwort = llm_service.client.chat.completions.create(
            model=llm_service.model,
            messages=[
                {"role": "system", "content": _ANWEISUNG},
                {"role": "user", "content": nachricht[:2000]},
            ],
            temperature=0,
            # Grosszuegig bemessen, weil bei Reasoning-Modellen die
            # Denk-Token mit unter dieses Dach fallen. Zu knapp kommt eine
            # leere Antwort zurueck - ohne Fehlermeldung.
            max_tokens=512,
            timeout=12.0,
        )
        inhalt = (antwort.choices[0].message.content or "").strip()
    except Exception as fehler:
        logger.warning("Auftragserkennung: Modell nicht erreichbar (%s)", fehler)
        return None

    if not inhalt:
        logger.warning("Auftragserkennung: leere Antwort des Modells")
        return None

    # Modelle packen JSON gern in einen Codeblock.
    treffer = re.search(r"\{.*\}", inhalt, re.DOTALL)
    if not treffer:
        logger.warning("Auftragserkennung: kein JSON in %r", inhalt[:120])
        return None

    try:
        daten = json.loads(treffer.group(0))
        return bool(daten["auftrag"]), str(daten.get("grund", "")).strip()
    except (ValueError, KeyError, TypeError) as fehler:
        logger.warning("Auftragserkennung: Antwort unlesbar (%s): %r",
                       fehler, inhalt[:120])
        return None


# ---------------------------------------------------------------------------
# Einstieg
# ---------------------------------------------------------------------------

def ist_auftrag(nachricht: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
    """Prueft, ob die Nachricht ein Coding-Auftrag ist.

    Returns:
        (True, begruendung, kategorie, komplexitaet) wenn es ein Auftrag ist,
        (False, "", None, None) sonst.
    """
    if not nachricht or not nachricht.strip():
        return False, "", None, None

    text = nachricht.strip().lower()

    # 1. Explizites Signalpraefix -> immer Auftrag, ohne Modell zu fragen.
    for praefix in _SIGNAL_PRAEFIXE:
        if text.startswith(praefix):
            return (True, f"Signalpraefix '{praefix}'",
                    kategorisiere(nachricht), schaetze_komplexitaet(nachricht))

    # 2. Das Modell entscheidet.
    urteil = _modell_entscheidet(nachricht)
    if urteil is not None:
        auftrag, grund = urteil
        if not auftrag:
            return False, "", None, None
        begruendung = f"Modell: {grund}" if grund else "Modell erkannte einen Auftrag"
        return (True, begruendung,
                kategorisiere(nachricht), schaetze_komplexitaet(nachricht))

    # 3. Notnagel.
    if heuristik_ist_auftrag(nachricht):
        return (True, "Wortheuristik (Modell nicht erreichbar)",
                kategorisiere(nachricht), schaetze_komplexitaet(nachricht))
    return False, "", None, None
