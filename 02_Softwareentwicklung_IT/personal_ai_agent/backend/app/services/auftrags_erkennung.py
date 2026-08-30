"""Erkennt, ob eine Nachricht ein Coding-Auftrag fuer den Agenten ist.

Zweck: Die Oberflaeche spricht immer in denselben /api/chat-Eingang.
Doch nicht jede Nachricht soll der lokale LLM beantworten - eine
Programmier-/Werkzeugaufgabe gehoert ins Auftragsbuch, damit Hermes sie
uebernimmt. Diese Abgrenzung passiert hier, bewusst ohne LLM: deterministisch,
kostenlos und nachvollziehbar.

Erweiterung:
  - Unterscheidet nach Kategorie (bug, feature, refactor, frage)
  - Schaetzt Komplexitaet (einfach, mittel, komplex)
  - Extrahiert Schluesselwoerter fuer die Vorschau

Warum Heuristik statt LLM: Ein Klassifikations-Aufruf kostet pro Nachricht
Token und kann trotzdem danebenliegen. Wort- und Kontextregeln sind
vorhersehbar und lassen sich testen. Ist die Regel zu straff oder zu locker,
wird nur diese eine Funktion angepasst - die Chat-Route bleibt unberuehrt.
"""
from typing import Tuple, Optional

# Verb, das einen Arbeitsauftrag ausloest.
_AUFTRAGS_VERBEN = (
    # Deutsch
    "erstelle", "schreibe", "baue", "fixe", "aendere",
    "implementiere", "programmiere", "verwende", "ergaenze", "entferne",
    "optimiere", "refaktoriere", "loesche", "aktualisiere",
    "konfiguriere", "richte", "installiere", "setze", "mache",
    "generiere", "fuege", "passe", "verbessere", "korrigiere",
    # Englisch
    "create", "write", "build", "fix", "change", "add", "implement",
    "program", "update", "refactor", "optimize", "delete", "configure",
    "setup", "make", "generate", "improve", "correct",
)

# Gegenstaende, die einen Coding-/Werkzeug-Bezug herstellen.
_OBJEKTE = (
    # Code / Projekt
    "code", "datei", "dateien", "projekt", "funktion", "klasse", "modul",
    "script", "skript", "endpoint", "route", "api", "logik",
    "test", "tests", "backend", "frontend", "app", "programm", "robotik",
    "sps", "steuerung", "library", "bibliothek", "paket", "abhaengigkeit",
    "dependency", "modell", "config", "konfiguration", "model",
    "seite", "seiten", "button", "oberflaeche", "design",
    # Agent / System
    "server", "dienst", "service", "tool",
    "werkzeug", "plugin", "skill", "wissensdatenbank", "datenbank",
    # Aenderungen an vorhandenem
    "bug", "fehler", "syntaxfehler", "behebe",
)

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
    
    # Frage? (kein klares Coding-Verb in Imperativform)
    # Standardmaessig Feature
    return "feature"


def schaetze_komplexitaet(nachricht: str) -> str:
    """Schaetzt die Komplexitaet des Auftrags."""
    text = nachricht.lower()
    
    # Einfach?
    einfachi = sum(1 for s in _EINFACH_SIGNALE if s in text)
    if einfachi >= 2 or any(text.startswith(s) for s in ("klein", "kurz", "schnell")):
        return "einfach"
    
    # Komplex?
    for signal in _KOMPLEX_SIGNALE:
        if signal in text:
            return "komplex"
    
    # Laenge als Indikator
    if len(text) > 200:
        return "mittel"
    if len(text) > 500:
        return "komplex"
    
    return "mittel"


def ist_auftrag(nachricht: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
    """Pruft, ob die Nachricht ein Coding-Auftrag ist.

    Returns:
        (True, begruendung, kategorie, komplexitaet) wenn es ein Auftrag ist,
        (False, "", None, None) sonst.
    """
    if not nachricht:
        return False, "", None, None
    
    text = nachricht.strip().lower()

    # 1. Explizites Signalpraefix -> immer Auftrag.
    for praefix in _SIGNAL_PRAEFIXE:
        if text.startswith(praefix):
            kat = kategorisiere(nachricht)
            kompl = schaetze_komplexitaet(nachricht)
            return True, f"Signalpraefix '{praefix}'", kat, kompl

    # 1b. Meta-/Gesprächs-Heuristik: Sätze, die über den Agenten/die Kommunikation
    # selber reden (Lob, Zustand, "zwischen X und Y"), sind KEINE Coding-Aufträge.
    # Ohne das würde z. B. "Super, du hast was geschafft ... Kommunikation zwischen
    # Hermes und Agenten" fälschlich als Auftrag erkannt und Hermes gerufen.
    _META_SIGNALE = (
        "kommunikation", "zwischen", "du hast", "darüber reden", "gespräch",
        "vorhin", "gerade", "super", "gut gemacht", "danke", "verstehe",
        "wie ist", "wie sieht", "stand", "status", "erzähl", "was ist",
    )
    if any(sig in text for sig in _META_SIGNALE):
        # Nur sperren, wenn KEIN klares Arbeitsverb am Satzanfang steht
        # (z. B. "Baue jetzt die Kommunikation zwischen X und Y" wäre echt).
        if not any(text.startswith(w + " ") for w in _AUFTRAGS_VERBEN):
            return False, "", None, None

    woerter = text.split()

    # 2. Muss ein Auftrags-Verb enthalten.
    # Früher-Bug: über `_AUFTRAGS_VERBEN` iteriert (nicht über die Wörter des
    # Satzes) — `w.rstrip("?!.") in _AUFTRAGS_VERBEN` war dann IMMER wahr
    # (w ist ja bereits ein Verb) => `hat_verb` immer True => jede Nachricht
    # mit einem Objekt-Wort ("datei", "test", …) wurde fälschlich als
    # Coding-Auftrag an Hermes delegiert. Korrekt ist: Ein WORT des Textes
    # ist ein Auftrags-Verb, ODER der Satz beginnt mit einem (Satzanfang).
    hat_verb = (
        any(wort.rstrip("?!.") in _AUFTRAGS_VERBEN for wort in woerter)
        or any(text.startswith(verb + " ") for verb in _AUFTRAGS_VERBEN)
    )
    if not hat_verb:
        return False, "", None, None

    # 3. Und ein Coding-/System-Objekt.
    hat_objekt = any(obj in text for obj in _OBJEKTE)
    if not hat_objekt:
        return False, "", None, None

    kat = kategorisiere(nachricht)
    kompl = schaetze_komplexitaet(nachricht)
    return True, f"Auftrags-Verb + System-Bezug ({kat}, {kompl})", kat, kompl
