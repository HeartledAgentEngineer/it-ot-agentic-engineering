"""Modell-Router: wählt das passende LLM-Modell je nach Aufgaben-Kategorie.

Ziel: immer das günstigste Modell, das die Aufgabe zuverlässig kann —
Qualität wird nur dort teurer, wo die Aufgabe es verlangt (Vision,
Coding, komplexes Reasoning). Die Modell-IDs stammen aus dem
OpenRouter-Katalog und sind verifiziert.

Das Modul ist bewusst eigenständig: nur stdlib, keine Importe aus
anderen App-Modulen, damit es isoliert importierbar und testbar ist.
"""

# ---------------------------------------------------------------------------
# Kategorien (Konstanten)
# ---------------------------------------------------------------------------

EMOTIONAL = "emotional"    # empathischer/psychologischer Kontakt, Gefühle, Beziehung, Familie
ALLTAG = "alltag"          # Kochen, Essen planen, Urlaub planen, organisieren, einfache Fragen
BILDER = "bilder"          # Bilder/Fotos analysieren, Vision, Screenshots, Gesichter
ERINNERUNG = "erinnerung"  # Erinnerungen abrufen, "was haben wir gemacht", Vergangenheit, Archiv
CODING = "coding"          # Programmierung, Code, Debug, Skripte
KOMPLEX = "komplex"        # komplexe Aufgaben, lange Analysen, Planung, Mathematik, Reasoning
SCHNELL = "schnell"        # sehr kurze/schnelle Antworten (Default-Fallback)

# ---------------------------------------------------------------------------
# Modell-Zuordnung (OpenRouter-IDs, verifiziert)
# ---------------------------------------------------------------------------

MODELL_FLASH = "deepseek/deepseek-v4-flash-0731"   # günstig + flink (Standard)
MODELL_VISION = "google/gemini-3.7-flash"          # Vision-fähig
MODELL_CODING = "anthropic/claude-sonnet-5"        # gut für Coding
MODELL_PRO = "deepseek/deepseek-v4-pro"            # mehr Substanz für Komplexes

# Kategorie -> empfohlenes Modell (günstigstes passendes)
_KATEGORIE_MODELL: dict[str, str] = {
    EMOTIONAL: MODELL_FLASH,
    ALLTAG: MODELL_FLASH,
    BILDER: MODELL_VISION,
    ERINNERUNG: MODELL_FLASH,
    CODING: MODELL_CODING,
    KOMPLEX: MODELL_PRO,
    SCHNELL: MODELL_FLASH,
}

# ---------------------------------------------------------------------------
# Signalwort-Heuristik (deutsch, case-insensitive)
# ---------------------------------------------------------------------------

_SIGNALWOERTER: dict[str, tuple[str, ...]] = {
    EMOTIONAL: ("traurig", "glücklich", "gefühle", "psychologisch",
                "beziehung", "familie"),
    ALLTAG: ("kochen", "essen", "rezept", "urlaub", "planen", "wochenende"),
    BILDER: ("bild", "foto", "visuell", "screenshot", "gesicht"),
    ERINNERUNG: ("erinnerst", "erinnerung", "was haben wir",
                 "vergangenheit", "letztes jahr", "archiv"),
    CODING: ("code", "programmieren", "debug", "skript", "fehler in"),
    KOMPLEX: ("komplex", "analysiere", "berechne", "umfassend",
              "detailliert", "strategie"),
}

# Prüfreihenfolge: spezifische Kategorien zuerst, generische danach.
_PRUEFREIHENFOLGE: tuple[str, ...] = (
    BILDER, EMOTIONAL, ERINNERUNG, CODING, KOMPLEX, ALLTAG,
)


def erkenne_kategorie(frage: str) -> str:
    """Erkennt die Aufgaben-Kategorie einer Nutzerfrage per Signalwort-Heuristik.

    Die Prüfung ist case-insensitive (Groß-/Kleinschreibung egal). Spezifische
    Kategorien (bilder, emotional, erinnerung, coding) werden vor generischen
    geprüft, damit z. B. "Foto von unserem Urlaub" als Bildfrage erkannt wird.
    Trifft keine Signalwortliste zu, gilt die Default-Kategorie "schnell".

    Args:
        frage: Die Nutzerfrage (deutsch).

    Returns:
        Eine der Kategorie-Konstanten, z. B. ``BILDER`` oder ``SCHNELL``.
    """
    if not frage:
        return SCHNELL
    text = frage.lower()
    for kategorie in _PRUEFREIHENFOLGE:
        for signalwort in _SIGNALWOERTER[kategorie]:
            if signalwort in text:
                return kategorie
    return SCHNELL


def ist_vision_faehig(modell: str) -> bool:
    """True, wenn das Modell Bilder versteht (Vision-fähig).

    Erkennt bekannte Vision-fähige Modellfamilien am Namen (case-insensitive):
    Gemini, GPT-4o, GPT-5, Claude/Sonnet.
    """
    name = modell.lower()
    return any(marke in name for marke in ("gemini", "gpt-4o", "gpt-5",
                                           "sonnet", "claude"))


def modell_fuer(kategorie: str, aktuelles_modell: str = "") -> str:
    """Liefert das empfohlene Modell für eine Aufgaben-Kategorie.

    Eine bereits gesetzte Nutzer-Modell-Wahl (``aktuelles_modell``) hat
    Vorrang — außer bei Bildern: Ist das gewählte Modell nicht vision-fähig,
    wird auf das Vision-Modell ausgewichen, damit Bildfragen überhaupt
    beantwortbar sind. Unbekannte oder leere Kategorien fallen auf das
    Standard-Modell ("schnell") zurück.

    Args:
        kategorie: Eine der Kategorie-Konstanten (oder unbekannter String).
        aktuelles_modell: Vom Nutzer gewähltes Modell (leer = keine Wahl).

    Returns:
        Die OpenRouter-Modell-ID als String.
    """
    if aktuelles_modell and aktuelles_modell.strip():
        gewaehlt = aktuelles_modell.strip()
        if kategorie == BILDER and not ist_vision_faehig(gewaehlt):
            return MODELL_VISION
        return gewaehlt
    return _KATEGORIE_MODELL.get(kategorie, MODELL_FLASH)