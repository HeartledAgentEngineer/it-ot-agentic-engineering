"""Arbeitsweise je Thema: `protokoll` (Standard) oder `vibe` – gespeichert in `arbeitsweise.json`.

Format: `{"version": 1, "themen": {"<thema>": "vibe"}}`. Ein fehlendes Thema (oder eine fehlende Datei) heißt
`protokoll`. Die Datei ist bewusst **nicht** Teil des strengen Profilformats `themenmodi.json`: Profil-Leser und
-Sperren bleiben unberührt. Gelesen wird streng – unbekannte Werte, Schlüssel oder Versionen und kaputtes JSON ergeben
`ArbeitsweiseFehler` (die Anzeige zeigt dann „?“); eine kaputte Datei wird nie überschrieben.

Geschrieben wird nur von Hand (`masterwechsel vibe THEMA an|aus` über `modi.vibe_setzen`, bzw. das Übersichtsfenster):
Kein Automatikpfad ruft `setzen` auf. Schreiben ist atomar und läuft unter der kurzen globalen Sperre.

Dieses Modul kennt `modi` nicht (es ist umgekehrt: `modi` prüft beim Schreiben eines Profils die Vorrangregel
„Vibe nur mit Ausführer Claude“). Die Regel selbst steht in `modi._vibe_pruefen`.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import paare, zustand
from .signale import _atomar_schreiben, daten_ordner

PROTOKOLL, VIBE = "protokoll", "vibe"
WERTE = (PROTOKOLL, VIBE)
UNBEKANNT = "?"               # nur Anzeige: Datei nicht lesbar oder ungültig
VERSION = 1
GLOBALE_FRIST = 1.0
VIBE_REGEL = (
    "Claude-Subagent baut (Modell laut Profil; bei `modell_standard` wählt der Master Sonnet oder Haiku); "
    "Master gibt Auftrag und nimmt per Kurzprüfung ab (Diff lesen, Prüfbefehl selbst ausführen); "
    "keine Codex-/Hermes-Gegenprüfung; Prüfbefehl Pflicht vor Commit und Push; Sensibles nur Hermes; "
    "kein OT/SPS-Code; kein force-push, kein Löschen")
ANZEIGE = {PROTOKOLL: "Protokoll", VIBE: "Vibe", UNBEKANNT: "?"}


class ArbeitsweiseFehler(Exception):
    """Datei unlesbar oder ungültig, oder das Thema ist nicht zulässig."""


def datei() -> Path:
    return daten_ordner() / "arbeitsweise.json"


def neben(profil_pfad: Path | None) -> Path:
    """Die Arbeitsweise-Datei neben der Profildatei (`themenmodi.json`); ohne Angabe die im Datenordner."""
    return datei() if profil_pfad is None else Path(profil_pfad).with_name("arbeitsweise.json")


def lesen(datei_pfad: Path | None = None) -> dict[str, str]:
    """Alle Themen mit ihrer Arbeitsweise; fehlende Datei ⇒ `{}`, ungültige Datei ⇒ `ArbeitsweiseFehler`."""
    pfad = datei_pfad or datei()
    try:
        roh = json.loads(pfad.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as fehler:     # ValueError deckt JSON- und UnicodeDecodeError ab
        raise ArbeitsweiseFehler(f"Arbeitsweise-Datei nicht lesbar ({type(fehler).__name__})") from fehler
    if (not isinstance(roh, dict) or set(roh) != {"version", "themen"} or roh["version"] != VERSION
            or not isinstance(roh["themen"], dict)):
        raise ArbeitsweiseFehler("Arbeitsweise-Datei hat ein ungültiges Format oder eine unbekannte Version")
    ergebnis: dict[str, str] = {}
    for thema, wert in roh["themen"].items():
        try:
            paare.thema_pruefen(thema)
        except paare.PaarFehler as fehler:
            raise ArbeitsweiseFehler(f"Arbeitsweise-Datei enthält ein ungültiges Thema: {fehler}") from fehler
        if not isinstance(wert, str) or wert not in WERTE:
            raise ArbeitsweiseFehler(f"Arbeitsweise-Datei enthält einen unbekannten Wert für {thema!r}")
        ergebnis[thema] = wert
    return ergebnis


def arbeitsweise(thema: str, datei_pfad: Path | None = None) -> str:
    """`protokoll` oder `vibe`; ungültige Datei ⇒ `ArbeitsweiseFehler`."""
    try:
        paare.thema_pruefen(thema)
    except paare.PaarFehler as fehler:
        raise ArbeitsweiseFehler(str(fehler)) from fehler
    return lesen(datei_pfad).get(thema, PROTOKOLL)


def anzeige_wert(thema: str, datei_pfad: Path | None = None) -> str:
    """Wie `arbeitsweise`, aber für die Anzeige: ein Lesefehler ergibt „?“ statt einer Ausnahme."""
    try:
        return arbeitsweise(thema, datei_pfad)
    except ArbeitsweiseFehler:
        return UNBEKANNT


def setzen(thema: str, vibe: bool, datei_pfad: Path | None = None) -> bool:
    """Arbeitsweise setzen; `True`, wenn geschrieben wurde, `False`, wenn sie schon so stand (idempotent).

    Der Aufrufer (`modi.vibe_setzen`) prüft Thema und Ausführer unter der Themensperre. Eine ungültige Datei wird
    nie überschrieben (`ArbeitsweiseFehler`). Aus wird zu: der Eintrag fällt weg; ohne Datei entsteht keine.
    """
    try:
        paare.thema_pruefen(thema)
    except paare.PaarFehler as fehler:
        raise ArbeitsweiseFehler(str(fehler)) from fehler
    pfad = datei_pfad or datei()
    try:
        with zustand.sperre(GLOBALE_FRIST):
            aktuell = lesen(pfad)
            if (aktuell.get(thema) == VIBE) == vibe:
                return False
            if vibe:
                aktuell[thema] = VIBE
            else:
                del aktuell[thema]
            _atomar_schreiben(pfad, json.dumps({"version": VERSION, "themen": dict(sorted(aktuell.items()))},
                                               ensure_ascii=False, indent=2))
            return True
    except zustand.SperrFehler as fehler:
        raise ArbeitsweiseFehler(f"Arbeitsweise-Datei gerade belegt: {fehler}") from fehler


def profil_zeilen(wert: str) -> list[str]:
    """Zeilen für `masterwechsel profil THEMA` (Text): Arbeitsweise und bei Vibe die feste Regel."""
    if wert == VIBE:
        return ["  Arbeitsweise: Vibe", f"  Vibe-Regel: {VIBE_REGEL}"]
    if wert == UNBEKANNT:
        return ["  Arbeitsweise: ? (arbeitsweise.json ungültig – Datei prüfen)"]
    return ["  Arbeitsweise: Protokoll"]
