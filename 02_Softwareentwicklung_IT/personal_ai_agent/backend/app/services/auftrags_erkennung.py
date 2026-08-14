"""Erkennt, ob eine Nachricht ein Coding-Auftrag fuer den Agenten ist.

Zweck: Die Oberflaeche spricht immer in denselben /api/chat-Eingang.
Doch nicht jede Nachricht soll der lokale LLM beantworten - eine
Programmier-/Werkzeugaufgabe gehoert ins Auftragsbuch, damit Hermes sie
uebernimmt. Diese Abgrenzung passiert hier, bewusst ohne LLM: deterministisch,
kostenlos und nachvollziehbar.

Warum Heuristik statt LLM: Ein Klassifikations-Aufruf kostet pro Nachricht
Token und kann trotzdem danebenliegen. Wort- und Kontextregeln sind
vorhersehbar und lassen sich testen. Ist die Regel zu straff oder zu locker,
wird nur diese eine Funktion angepasst - die Chat-Route bleibt unberuehrt.

Hinweis: Diese Heuristik ist als austauschbarer erster Schritt gedacht.
Werden die Regeln zu fehleranfaellig, kann sie spaeter durch einen
Mini-LLM-Klassifikator ersetzt werden, ohne die Aufrufer zu aendern.
"""
from typing import Tuple

# Verb, das einen Arbeitsauftrag ausloest. Wird der Text nicht erkannt,
# gilt er als normale Frage.
#
# Bewusst deutsche + englische Imperative: Die Oberflaeche wird auf Deutsch
# bedient, aber Coding-Auftraege enthalten haeufig englische Fachbegriffe.
_AUFTRAGS_VERBEN = (
    # Deutsch
    "erstelle", "schreibe", "baue", "fixe", "aendere", "aendere",
    "implementiere", "programmiere", "verwende", "ergaenze", "entferne",
    "optimiere", "refaktoriere", "loesche", "ergaenze", "aktualisiere",
    "konfiguriere", "richte", "installiere", "setze",
    # Englisch
    "create", "write", "build", "fix", "change", "add", "implement",
    "program", "update", "refactor", "optimize", "delete", "configure",
    "setup", "make", "generate", "implement",
)

# Gegenstaende, die einen Coding-/Werkzeug-Bezug herstellen. Ohne einen
# solchen Bezug ist "erstelle einen Termin" kein Agenten-Auftrag.
_OBJEKTE = (
    # Code / Projekt
    "code", "datei", "dateien", "projekt", "funktion", "klasse", "modul",
    "script", "skript", "endpoint", "route", "api", "funktion", "logik",
    "test", "tests", "backend", "frontend", "app", "programm", "robotik",
    "sps", "steuerung", "library", "bibliothek", "paket", "abhaengigkeit",
    "dependency", "modell", "klasse", "config", "konfiguration", "model",
    # Agent / System
    "agent", "agenten", "hermes", "server", "dienst", "service", "tool",
    "werkzeug", "plugin", "skill", "wissensdatenbank", "datenbank",
    # Aenderungen an vorhandenem
    "bug", "fehler", "syntaxfehler", "behebe", "korrigiere",
)

# Wird eine Nachricht mit einem dieser Signalsaetze begonnen, gilt sie
# bedingungslos als Auftrag - auch ohne Objektliste.
_SIGNAL_PRAEFIXE = (
    "auftrag:", "aufgabe:", "to do:", "todo:", "todo:",
)


def ist_auftrag(nachricht: str) -> Tuple[bool, str]:
    """Pruft, ob die Nachricht ein Coding-Auftrag ist.

    Returns:
        (True, begruendung) wenn es ein Auftrag ist,
        (False, "") sonst.
    """
    if not nachricht:
        return False, ""
    text = nachricht.strip().lower()

    # 1. Explizites Signalpraefix -> immer Auftrag.
    for praefix in _SIGNAL_PRAEFIXE:
        if text.startswith(praefix):
            return True, f"Signalpraefix '{praefix}'"

    woerter = text.split()

    # 2. Muss ein Auftrags-Verb enthalten.
    hat_verb = any(w.rstrip("?!.") in _AUFTRAGS_VERBEN or
                   text.startswith(w + " ") for w in _AUFTRAGS_VERBEN)
    if not hat_verb:
        return False, ""

    # 3. Und ein Coding-/System-Objekt.
    hat_objekt = any(obj in text for obj in _OBJEKTE)
    if not hat_objekt:
        return False, ""

    return True, "Auftrags-Verb + System-/Code-Bezug erkannt"
