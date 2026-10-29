"""Prüfer je Thema: `automatisch` (Standard) oder `codex` | `hermes` – gespeichert in `pruefer.json`.

Format: `{"version": 1, "themen": {"<thema>": "codex"|"hermes"}}`. Ein fehlendes Thema (oder eine fehlende Datei) heißt
`automatisch` – dann gilt die Regel von `pruefkreis.py` (Prüfer ≠ Modellfamilie des Masters). Eine Wahl gilt völlig frei,
auch für die Familie des Masters (Sebastian, 28.10.2026); `--sensibel` (immer Hermes) und `--pruefer` auf der Kommandozeile
von `pruefkreis` gehen ihr vor. Die Datei ist bewusst **nicht** Teil des Profilformats `themenmodi.json`.

Gelesen wird streng – unbekannte Werte, Schlüssel oder Versionen und kaputtes JSON ergeben `PrueferWahlFehler` (die
Anzeige zeigt dann „?“, `pruefkreis` nutzt die Regel und vermerkt es); eine kaputte Datei wird nie überschrieben.

Geschrieben wird nur von Hand (`masterwechsel pruefer-setzen THEMA …` bzw. das Übersichtsfenster): Kein Automatikpfad ruft
`setzen` auf. Schreiben ist atomar und läuft unter der kurzen globalen Sperre; das Thema muss existieren (Profil oder Paar).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import modi, paare, zustand
from .signale import _atomar_schreiben, daten_ordner

AUTOMATISCH, CODEX, HERMES = "automatisch", "codex", "hermes"
WERTE = (AUTOMATISCH, CODEX, HERMES)          # was `setzen` annimmt
GESPEICHERT = (CODEX, HERMES)                 # was in der Datei stehen darf
UNBEKANNT = "?"                               # nur Anzeige: Datei nicht lesbar oder ungültig
VERSION = 1
GLOBALE_FRIST = 1.0
ANZEIGE = {AUTOMATISCH: "Automatisch", CODEX: "Codex", HERMES: "Hermes", UNBEKANNT: "?"}


class PrueferWahlFehler(Exception):
    """Datei unlesbar oder ungültig, oder das Thema ist nicht zulässig."""


def datei() -> Path:
    return daten_ordner() / "pruefer.json"


def lesen(datei_pfad: Path | None = None) -> dict[str, str]:
    """Alle gewählten Themen mit ihrem Prüfer; fehlende Datei ⇒ `{}`, ungültige Datei ⇒ `PrueferWahlFehler`."""
    pfad = datei_pfad or datei()
    try:
        roh = json.loads(pfad.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as fehler:     # ValueError deckt JSON- und UnicodeDecodeError ab
        raise PrueferWahlFehler(f"Prüfer-Datei nicht lesbar ({type(fehler).__name__})") from fehler
    if (not isinstance(roh, dict) or set(roh) != {"version", "themen"} or roh["version"] != VERSION
            or not isinstance(roh["themen"], dict)):
        raise PrueferWahlFehler("Prüfer-Datei hat ein ungültiges Format oder eine unbekannte Version")
    ergebnis: dict[str, str] = {}
    for thema, wert in roh["themen"].items():
        try:
            paare.thema_pruefen(thema)
        except paare.PaarFehler as fehler:
            raise PrueferWahlFehler(f"Prüfer-Datei enthält ein ungültiges Thema: {fehler}") from fehler
        if not isinstance(wert, str) or wert not in GESPEICHERT:
            raise PrueferWahlFehler(f"Prüfer-Datei enthält einen unbekannten Wert für {thema!r}")
        ergebnis[thema] = wert
    return ergebnis


def wahl(thema: str, datei_pfad: Path | None = None) -> str:
    """`automatisch`, `codex` oder `hermes`; ungültige Datei ⇒ `PrueferWahlFehler`."""
    try:
        paare.thema_pruefen(thema)
    except paare.PaarFehler as fehler:
        raise PrueferWahlFehler(str(fehler)) from fehler
    return lesen(datei_pfad).get(thema, AUTOMATISCH)


def anzeige_wert(thema: str, datei_pfad: Path | None = None) -> str:
    """Wie `wahl`, aber für die Anzeige: ein Lesefehler ergibt „?“ statt einer Ausnahme."""
    try:
        return wahl(thema, datei_pfad)
    except PrueferWahlFehler:
        return UNBEKANNT


def _thema_existiert(thema: str) -> None:
    try:
        bekannt = thema in modi.lesen() or any(p.thema == thema for p in paare.lesen())
    except (modi.ModusFehler, OSError) as fehler:
        raise PrueferWahlFehler(f"Themenprofile nicht lesbar: {fehler}") from fehler
    if not bekannt:
        raise PrueferWahlFehler(f"Thema unbekannt (weder Profil noch Paar): {thema}")


def setzen(thema: str, wert: str, datei_pfad: Path | None = None) -> bool:
    """Prüferwahl setzen; `True`, wenn geschrieben wurde, `False`, wenn sie schon so stand (idempotent).

    `automatisch` entfernt den Eintrag (ohne Datei entsteht keine). Eine ungültige Datei wird nie überschrieben
    (`PrueferWahlFehler`); ein unbekanntes Thema oder ein unbekannter Wert ändern nichts.
    """
    try:
        paare.thema_pruefen(thema)
    except paare.PaarFehler as fehler:
        raise PrueferWahlFehler(str(fehler)) from fehler
    if not isinstance(wert, str) or wert not in WERTE:
        raise PrueferWahlFehler(f"Unbekannter Prüfer: {wert!r} (erlaubt: {', '.join(WERTE)})")
    _thema_existiert(thema)
    pfad = datei_pfad or datei()
    try:
        with zustand.sperre(GLOBALE_FRIST):
            aktuell = lesen(pfad)
            if aktuell.get(thema, AUTOMATISCH) == wert:
                return False
            if wert == AUTOMATISCH:
                del aktuell[thema]
            else:
                aktuell[thema] = wert
            _atomar_schreiben(pfad, json.dumps({"version": VERSION, "themen": dict(sorted(aktuell.items()))},
                                               ensure_ascii=False, indent=2))
            return True
    except zustand.SperrFehler as fehler:
        raise PrueferWahlFehler(f"Prüfer-Datei gerade belegt: {fehler}") from fehler
