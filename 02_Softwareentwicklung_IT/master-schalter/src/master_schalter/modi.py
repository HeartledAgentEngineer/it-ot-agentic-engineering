"""Persistente Arbeitsmodi je Thema und fail-closed Besitzwechsel.

Die Auswahl ist eine Routingregel. Sie startet weder eine Sitzung noch einen Transport.
Der Schutz eines Themas bleibt aktiv, solange entweder der gespeicherte Modus Hermes/Codex
ist oder seine geprüfte Besitzdatei Hermes nennt.
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from . import besitz, paare, uebergabe, vorgaenge, zustand
from .signale import _atomar_schreiben, daten_ordner

KONTINGENT = "kontingent"
HERMES_CODEX = "hermes-codex"
WERTE = (KONTINGENT, HERMES_CODEX)
VERSION = 1
GLOBALE_FRIST = 1.0


class ModusFehler(Exception):
    """Modusdatei, Thema, Sperre oder Besitzwechsel ist ungültig."""


def datei() -> Path:
    return daten_ordner() / "themenmodi.json"


def _lesen(datei_pfad: Path | None = None) -> dict[str, str]:
    pfad = datei_pfad or datei()
    try:
        roh = json.loads(pfad.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as fehler:
        raise ModusFehler(f"Modusdatei nicht lesbar: {fehler}") from fehler
    if not isinstance(roh, dict) or roh.get("version") != VERSION or not isinstance(roh.get("themen"), dict):
        raise ModusFehler("Modusdatei hat ein ungültiges Format oder eine unbekannte Version")
    result: dict[str, str] = {}
    for thema, wert in roh["themen"].items():
        try:
            paare.thema_pruefen(thema)
        except paare.PaarFehler as fehler:
            raise ModusFehler(f"Modusdatei enthält ein ungültiges Thema: {fehler}") from fehler
        if wert not in WERTE:
            raise ModusFehler(f"Modusdatei enthält einen unbekannten Modus für {thema!r}")
        result[thema] = wert
    return result


def lesen(datei_pfad: Path | None = None) -> dict[str, str]:
    return _lesen(datei_pfad)


def modus(thema: str, datei_pfad: Path | None = None) -> str:
    try:
        paare.thema_pruefen(thema)
    except paare.PaarFehler as fehler:
        raise ModusFehler(str(fehler)) from fehler
    return _lesen(datei_pfad).get(thema, KONTINGENT)


def _besitzer_lesen(master_datei: Path) -> str:
    """Nur eine fehlende Datei bedeutet Claude; ein echter Lesefehler sperrt fail-closed."""
    try:
        text = master_datei.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return besitz.CLAUDE
    except OSError as fehler:
        raise ModusFehler(f"Besitzstatus nicht lesbar; Thema bleibt geschützt ({fehler})") from fehler
    return besitz.besitzer(text)


def _paar_pruefen(thema: str, repo: Path | None, *, laufend: str | None = None,
                   erforderlich: bool = True) -> tuple[paare.Paar | None, Path | None]:
    try:
        paare.thema_pruefen(thema)
    except paare.PaarFehler as fehler:
        raise ModusFehler(str(fehler)) from fehler
    paar = next((p for p in paare.lesen() if p.thema == thema), None)
    if paar is None and laufend is None and erforderlich:
        raise ModusFehler(f"Thema unbekannt (kein vorhandenes Paar): {thema}")
    if paar is None and laufend is None:
        return None, None
    if repo is None:
        try:
            wurzel = uebergabe.repo_wurzel()
        except uebergabe.UebergabeFehler as fehler:
            raise ModusFehler(str(fehler)) from fehler
    else:
        wurzel = Path(repo).resolve()
        if not wurzel.is_dir() or not (wurzel / ".git").exists():
            raise ModusFehler("Repository-Wurzel ist nicht geprüft")
    laufend = paare.laufend_pruefen(thema, paar.laufend if paar is not None else laufend or "")
    master = besitz.pfad(wurzel, laufend)
    try:
        master.resolve().relative_to(wurzel.resolve())
    except ValueError as fehler:
        raise ModusFehler("Besitzpfad liegt außerhalb des geprüften Repositorys") from fehler
    return paar, master


def geschuetzt(thema: str, *, repo: Path | None = None, datei_pfad: Path | None = None,
               laufend: str | None = None) -> bool:
    """Frische Schutzprüfung; für Aufruf unter der Themensperre vorgesehen."""
    wert = modus(thema, datei_pfad)
    if wert == HERMES_CODEX:
        return True
    paar, master_datei = _paar_pruefen(thema, repo, laufend=laufend, erforderlich=False)
    if paar is None and master_datei is None:
        return False
    return wert == HERMES_CODEX or _besitzer_lesen(master_datei) == besitz.HERMES


def snapshot(themen: list[str], *, repo: Path | None = None,
             datei_pfad: Path | None = None) -> dict[str, tuple[str, str, bool]]:
    """Einmaliger technischer UI-Snapshot: (Modus, Besitz, effektiv geschützt) je Thema."""
    mapping = _lesen(datei_pfad)
    wurzel: Path | None = repo
    if wurzel is None:
        try:
            wurzel = uebergabe.repo_wurzel()
        except uebergabe.UebergabeFehler as fehler:
            raise ModusFehler(str(fehler)) from fehler
    result: dict[str, tuple[str, str, bool]] = {}
    for thema in themen:
        wert = mapping.get(thema, KONTINGENT)
        _, master_datei = _paar_pruefen(thema, wurzel)
        owner = _besitzer_lesen(master_datei)
        if owner not in (besitz.CLAUDE, besitz.CODEX, besitz.RESERVIERT, besitz.HERMES):
            raise ModusFehler(f"Besitzstatus von {thema!r} ist unbekannt")
        result[thema] = (wert, owner, wert == HERMES_CODEX or owner == besitz.HERMES)
    return result


def _speichern(datei_pfad: Path, thema: str, wert: str) -> None:
    with zustand.sperre(GLOBALE_FRIST):
        aktuell = _lesen(datei_pfad)
        aktuell[thema] = wert
        _atomar_schreiben(datei_pfad, json.dumps(
            {"version": VERSION, "themen": aktuell}, ensure_ascii=False, indent=2
        ))


def _offene_entwerten(thema: str, zeit: str) -> None:
    def entwerten(alt: list[vorgaenge.Vorgang]) -> list[vorgaenge.Vorgang]:
        return [
            replace(v, phase="entwertet", zeit=zeit)
            if v.thema == thema and v.phase in vorgaenge.OFFEN else v
            for v in alt
        ]

    vorgaenge.aendern(entwerten, frist=GLOBALE_FRIST)


def _setzen_gesperrt(thema: str, wert: str, datei_pfad: Path | None = None,
                      *, repo: Path | None = None) -> None:
    """Interner Setter für Aufrufer, die die Themensperre bereits halten."""
    try:
        paare.thema_pruefen(thema)
    except paare.PaarFehler as fehler:
        raise ModusFehler(str(fehler)) from fehler
    if wert not in WERTE:
        raise ModusFehler(f"Unbekannter Arbeitsmodus: {wert!r}")
    pfad = datei_pfad or datei()
    # Vor jeder Nebenwirkung alle Eingaben, die Modusdatei und Repository-Pfade prüfen.
    _lesen(pfad)
    paar, master_datei = _paar_pruefen(thema, repo)
    aktuell = _lesen(pfad).get(thema, KONTINGENT)
    owner = _besitzer_lesen(master_datei)
    if owner == besitz.RESERVIERT:
        raise ModusFehler("Thema ist gerade fremd reserviert; Modus wurde nicht geändert")
    if owner not in (besitz.CLAUDE, besitz.CODEX, besitz.HERMES):
        raise ModusFehler("Besitzstatus ist unbekannt; Modus wurde nicht geändert")

    if wert == aktuell and not (
        (wert == HERMES_CODEX and owner != besitz.HERMES)
        or (wert == KONTINGENT and owner == besitz.HERMES)
    ):
        return

    zeit = datetime.now(timezone.utc).isoformat()
    try:
        _offene_entwerten(thema, zeit)
    except (OSError, zustand.SperrFehler) as fehler:
        raise ModusFehler(f"Umschaltung unvollständig – Modus erneut wählen: offene Vorgänge nicht entwertet ({fehler})") from fehler

    if wert == HERMES_CODEX:
        if owner != besitz.HERMES:
            try:
                besitz.schreiben(master_datei, besitz.zeile(besitz.HERMES, zeit, "modus", thema))
            except OSError as fehler:
                raise ModusFehler(f"Umschaltung unvollständig – Modus erneut wählen: offene Vorgänge entwertet; Hermes-Besitzmarke nicht gespeichert, Modusdatei bleibt bei {aktuell} ({fehler})") from fehler
        try:
            _speichern(pfad, thema, wert)
        except (OSError, zustand.SperrFehler, ModusFehler) as fehler:
            raise ModusFehler(f"Umschaltung unvollständig – Modus erneut wählen: offene Vorgänge entwertet; Hermes-Besitzmarke steht, Modusdatei nicht aktualisiert (vorheriger Modus {aktuell}) ({fehler})") from fehler
        return

    # KONTINGENT: zuerst Modus speichern, danach die Hermes/Codex-Besitzmarke zurücksetzen.
    try:
        _speichern(pfad, thema, wert)
    except (OSError, zustand.SperrFehler, ModusFehler) as fehler:
        raise ModusFehler(f"Umschaltung unvollständig – Modus erneut wählen: offene Vorgänge entwertet; Kontingentmodus nicht gespeichert, Besitzmarke {owner} bleibt bestehen ({fehler})") from fehler
    if owner in (besitz.HERMES, besitz.CODEX):
        try:
            besitz.schreiben(master_datei, besitz.zeile(besitz.CLAUDE, zeit, "modus-reset", thema))
        except OSError as fehler:
            raise ModusFehler(f"Umschaltung unvollständig – Modus erneut wählen: offene Vorgänge entwertet; Kontingentmodus gespeichert, Besitzmarke noch nicht zurückgesetzt (weiterhin {owner}; {fehler})") from fehler


def setzen(thema: str, wert: str, datei_pfad: Path | None = None, *, repo: Path | None = None) -> None:
    try:
        paare.thema_pruefen(thema)
    except paare.PaarFehler as fehler:
        raise ModusFehler(str(fehler)) from fehler
    if wert not in WERTE:
        raise ModusFehler(f"Unbekannter Arbeitsmodus: {wert!r}")
    try:
        with zustand.thema_sperre(thema, blockierend=True, frist=GLOBALE_FRIST) as ok:
            if not ok:
                raise zustand.SperrFehler("Themenwechsel ist gerade belegt")
            _setzen_gesperrt(thema, wert, datei_pfad, repo=repo)
    except zustand.SperrFehler as fehler:
        raise ModusFehler(f"Übergabe läuft – Modus gleich erneut wählen: {fehler}") from fehler
