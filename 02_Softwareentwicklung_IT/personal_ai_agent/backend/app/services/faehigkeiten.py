"""Fähigkeiten-Manifest des Personal-Agents (Selbstbild).

Der Agent soll wissen, was er KANN und was NICHT — und wann eine Anfrage an
seine Grenze stößt (Terminal/Dateien/System → dann Hermes als Toolcall).

Dieses Manifest ist die datengetriebene Grundlage:
- `FAEHIGKEITEN` — was kann / was nicht (für System-Prompt + Explikation).
- `GRENZE_MARKER` — Muster, die auf eine Grenzüberschreitung hindeuten.
- `stösst_an_grenze(text)` — schnelle Heuristik, ob Hermes nötig ist.

Bewusst deterministisch (kein LLM): kostenlos, testbar, nachvollziehbar.
"""

from typing import List

# Was der Agent kann (eigene Fähigkeiten)
FAEHIGKEITEN: dict = {
    "kann": [
        "chat_verstaendnis",      # Normaler Dialog, Fragen beantworten
        "gedaechtnis",            # Persönliches Gedächtnis (ChromaDB) lesen/schreiben
        "websuche",               # Websuche (wenn aktiviert)
        "archiv",                 # Chat-Archive durchsuchen
        "dokument_text",          # Hochgeladene PDFs/Bilder verstehen (via LLM)
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
    "datei anlegen", "datei erstellen", "datei schreiben", "datei ändern",
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


def stösst_an_grenze(text: str) -> bool:
    """True, wenn die Anfrage an eine Fähigkeits-Grenze stößt (→ Hermes).

    Deterministische Heuristik über GRENZE_MARKER. Wird von der Weiche als
    Ergänzung zur ist_auftrag()-Heuristik genutzt.
    """
    if not text:
        return False
    t = text.lower()
    return any(marker in t for marker in GRENZE_MARKER)


def faehigkeits_block() -> str:
    """Baut den Fähigkeiten-/Grenzen-Text für den System-Prompt.

    Wird an den System-Prompt angehängt, damit der Agent begründet weiß,
    was er kann und was an Hermes delegiert wird.
    """
    kann = ", ".join(FAEHIGKEITEN["kann"])
    kann_nicht = ", ".join(FAEHIGKEITEN["kann_nicht"])
    return (
        "\n\n## DEINE FÄHIGKEITEN & GRENZEN (Selbstbild)\n"
        "Du bist der persönliche Assistent. Du kannst:\n"
        f"- {kann}.\n\n"
        "Du kannst NICHT (dafür fehlen dir Tools/Terminal/System-Zugriff):\n"
        f"- {kann_nicht}.\n\n"
        "Wenn eine Anfrage an eine dieser Grenzen stößt (z. B. Terminal-Befehl, "
        "Datei anlegen/ändern, Tool installieren, Git, System-Änderung), sage "
        "deutlich: **'Das übernimmt Hermes.'** und begründe in einem kurzen Satz, "
        "warum es deine Fähigkeiten übersteigt. Versuche es nicht selbst, wenn "
        "du es nicht kannst — Hermes hat Terminal-/Tool-Zugriff."
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
    return stösst_an_grenze(nachricht)
