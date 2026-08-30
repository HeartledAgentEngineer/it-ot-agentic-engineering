"""Fähigkeiten-Manifest des Personal-Agents (Selbstbild).

Der Agent soll wissen, was er KANN und was NICHT — und wann eine Anfrage an
seine Grenze stößt (Terminal/Dateien/System → dann Hermes als Toolcall).

Dieses Manifest ist die datengetriebene Grundlage:
- `FAEHIGKEITEN` — was kann / was nicht (für System-Prompt + Explikation).
- `GRENZE_MARKER` — Muster, die auf eine Grenzüberschreitung hindeuten.
- `stösst_an_grenze(text)` — schnelle Heuristik, ob Hermes nötig ist.

Bewusst deterministisch (kein LLM): kostenlos, testbar, nachvollziehbar.
"""

import re
from typing import List

# Was der Agent kann (eigene Fähigkeiten)
FAEHIGKEITEN: dict = {
    "kann": [
        "chat_verstaendnis",      # Normaler Dialog, Fragen beantworten
        "gedaechtnis",            # Persönliches Gedächtnis (ChromaDB) lesen/schreiben
        "websuche",               # Websuche (wenn aktiviert)
        "archiv",                 # Chat-Archive durchsuchen
        "dokument_text",          # Hochgeladene PDFs/Bilder verstehen (via LLM)
        "gesichter_merken",       # Personen auf Fotos anlernen/benennen (Gesichter-Katalog)
        "tts_stt",                # Sprachausgabe/Eingabe (falls konfiguriert)
    ],
    "kann_nicht": [
        "terminal",               # Shell-Befehle ausführen
        "dateien_schreiben",      # Dateien im Dateisystem/Repo ändern
        "tool_install",           # Tools/Pakete installieren
        "git",                    # Git-Aktionen (commit/push/pull)
        "system_zugriff",         # Docker, Dienste, System-Änderungen
    ],
}

# Muster, die eine Grenzüberschreitung markieren (→ Hermes delegieren)
GRENZE_MARKER: List[str] = [
    # Terminal / Shell
    "terminal", "shell", "befehl ausführen", "führe aus", "run", "bash",
    # Dateien / Repo
    "datei", "repo", "repository", "code schreiben", "code ändern",
    "projekt ändern",
    # Tools / Pakete
    "installiere", "tool installieren", "paket installieren", "pip install",
    "npm install", "tool bauen", "plugin installieren", "skill installieren",
    # Git
    "git", "commit", "push", "pull", "branchen", "merge",
    # System / SPS / Docker
    "docker", "container", "dienst starten", "service starten", "sps",
    "steuerung programmieren", "automatisierung", "roboter", "hardware",
]

# Reine LESE-Signale: "DATEI LESEN" ist eine Fähigkeit des Agents (Dateisuche/
# Archiv/dokument_text) und KEINE Grenze. Trifft ein solches Signal, wird das
# allgemeine "datei"-Signal unterdrückt — sonst würde z. B. "Lies meine
# Lebenslauf-Datei" fälschlich als Grenze an Hermes delegiert und der Agent
# sagt "musst du hochladen". Git/Terminal/System-Marker bleiben davon unberührt.
_DATEI_LESE_SIGNALE = (
    "lies", "lese", "was steht in", "inhalt von", "zeig mir den inhalt",
    "zeig mir den text", "gib mir die datei", "fasse zusammen aus",
    "durchsuche", "suche nach", "was liegt", "zeig mir",
)


def stoesst_an_grenze(text: str) -> bool:
    """True, wenn die Anfrage an eine Fähigkeits-Grenze stößt (→ Hermes).

    Deterministische Heuristik über GRENZE_MARKER mit Wortgrenzen (Regex),
    damit kurze Marker wie "git" oder "run" nicht in "digital"/"darunter"
    fälschlich treffen (Critic-Befund HOCH). Wird von der Weiche als Ergänzung
    zur ist_auftrag()-Heuristik genutzt.

    Reines Datei-LESEN (Dateisuche/Archiv) stößt bewusst NICHT an die Grenze —
    das kann der Agent. Nur Datei-/System-SCHREIBEN, Git, Terminal u. a. sind
    Grenzthemen.
    """
    if not text:
        return False
    t = text.lower()
    ist_lese = any(sig in t for sig in _DATEI_LESE_SIGNALE)
    for marker in GRENZE_MARKER:
        # Datei-Lesen: das allgemeine "datei"-Wort unterdrücken.
        if ist_lese and marker == "datei":
            continue
        # Phrasen (mit Leerzeichen) an beiden Enden als Ganzes matchen;
        # Einzelwörter mit Wortgrenzen (\b), um Substring-False-Positives zu vermeiden.
        if re.search(r"\b" + re.escape(marker) + r"\b", t):
            return True
    return False


def faehigkeits_block() -> str:
    """Baut den Fähigkeiten-/Grenzen-Text für den System-Prompt.

    Wird an den System-Prompt angehängt, damit der Agent begründet weiß,
    was er kann und was an Hermes delegiert wird. Proaktiv: Der Agent kennt
    Hermes als benutzbares Werkzeug UND die Trigger-Stichworte, an denen die
    Weiche ihn automatisch delegiert — so stellt er bei solchen Anfragen keine
    Rückfrage, sondern formuliert zum Hermes-Auftrag hin.
    """
    kann = ", ".join(FAEHIGKEITEN["kann"])
    kann_nicht = ", ".join(FAEHIGKEITEN["kann_nicht"])
    # Konkrete Stichworte, an denen die Weiche automatisch an Hermes delegiert
    # (gewollt deckungsgleich mit ist_auftrag()/stoesst_an_grenze()). Wenn sie
    # auftauchen, weiß der Agent: Das ist ein Hermes-Job, keine Rückfrage.
    ausloeser = (
        "Terminal/Shell-Befehle ('führe aus', 'run'), "
        "Code/Dateien schreiben oder ändern, Projekt/Repo ändern, "
        "Tool/Paket installieren (pip/npm), Git-Aktionen (commit/push/pull), "
        "Docker/Container/Dienste starten, SPS/Steuerung/OT programmieren, "
        "und allgemein ein Arbeitsverb (erstelle/schreibe/baue/fixe/ändere/"
        "implementiere/programmiere) zusammen mit einem System-Bezug "
        "(Code, Datei, Server, API, Modell, Test, …)."
    )
    return (
        "\n\n## DEINE FÄHIGKEITEN & GRENZEN & HERMES (Selbstbild)\n"
        "Du bist der persönliche Assistent. Du kannst:\n"
        f"- {kann}.\n\n"
        "Du hast auch ein benutzbares Werkzeug: **Hermes** (ein Coding-Agent "
        "mit Terminal-/Dateisystem-/System-Zugriff). Er erledigt alles, was "
        "deine Fähigkeiten übersteigt — du musst es nicht selbst versuchen.\n\n"
        "Zusätzlich hast du die **Handy-Dateisuche** (über Suchbegriff, ohne "
        "dass der Nutzer etwas hochladen muss): Du kannst Bilddateien finden "
        "und als Vorschau anzeigen (z. B. den letzten Screenshot oder ein Foto) "
        "und PDF-/Text-Dokumente vom Gerät lesen und zusammenfassen. Wenn der "
        "Nutzer nach einem Bild, Screenshot, Foto oder einem Dokument auf dem "
        "Gerät fragt (\"zeig/liest den letzten Screenshot\", \"das letzte Foto\", "
        "\"was steht in meiner Rechnung\"), nutze die Dateisuche aktiv per "
        "Suchbegriff und zeige das Ergebnis an — frage NICHT nach einem "
        "Upload oder Rückfragen.\n\n"
        "**Gesichter anlernen/erkennen:** Du kannst Personen auf Fotos "
        "ANLERNEN und (wieder)erkennen. Wenn der Nutzer beim Betrachten eines "
        "Bildes (Foto/Upload) sagt, WER darauf ist — \"das bin ich\", \"das ist "
        "meine Oma Helga\", \"das ist mein Zwillingsbruder Julian\", auch "
        "mehrere Personen auf EINEM Bild (\"das bin ich und das ist Julian\") "
        "— dann SPEICHERE diese Personen (Name + Rolle) und bestätige es kurz. "
        "Einen Zwillingsbruder nach einem Anlernen zu kennen ist ein normaler "
        "Fall, kein Fehler und keine Grenze. Sage NIEMALS \"das kann ich nicht\" "
        "oder \"das geht nicht\" bei einer Personen-Angabe — das ist eine "
        "deiner Fähigkeiten. Bei verwechselbar ähnlichen Personen (z. B. "
        "Zwillingsbrüder) benenne Unsicherheit ehrlich, statt blind zu raten.\n\n"
        "Du kannst NICHT (dafür fehlen dir Tools/Terminal/System-Zugriff):\n"
        f"- {kann_nicht}.\n\n"
        "Eine Anfrage stößt an diese Grenze (und wird automatisch an Hermes "
        f"delegiert), wenn eines davon vorkommt: {ausloeser}\n\n"
        "Wenn so eine Anfrage kommt, **frage NICHT zurück** und erfinde keine "
        "Umwege — sage deutlich und direkt:\n"
        "**'Das übernimmt Hermes.'** und begründe in einem kurzen Satz, warum "
        "es deine Fähigkeiten übersteigt (Terminal/Datei/System/Tool-Install). "
        "Die Weiche schickt den Auftrag dann automatisch an Hermes weiter; "
        "du brauchst ihn nicht selbst auszuführen, nur sauber zu übergeben. "
        "Bei einer reinen Wissens-/Analysefrage (ohne Arbeitsverb und ohne "
        "System-Bezug) beantwortest du sie normal selbst."
    )


def soll_hermes_delegieren(nachricht: str, mit_dateien: bool = False) -> bool:
    """Entscheidet, ob die Anfrage an Hermes delegiert werden soll.

    Kombiniert zwei Signale (deterministisch, ohne LLM):
      - ist_auftrag(): ein erkanntes Coding-/Werkzeug-Kommando,
      - stösst_an_grenze(): ein Fähigkeits-Grenzthema (Terminal/Datei/System),
        selbst wenn ist_auftrag es NICHT als Coding einstuft.

    Bei hochgeladenen Dateien (mit_dateien=True) wird NICHT delegiert — ein
    Dokument-/Bild-Upload ist eine Verständnis-/Analyse-Frage, kein Hermes-Job.
    """
    if mit_dateien:
        return False
    from app.services.auftrags_erkennung import ist_auftrag
    if ist_auftrag(nachricht)[0]:
        return True
    return stoesst_an_grenze(nachricht)
