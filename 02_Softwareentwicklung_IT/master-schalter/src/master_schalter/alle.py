"""Sammelbefehl `alle`: alle Themen auf einmal nach Kontingent und wieder zurück (`masterwechsel alle …`).

`auf_kontingent` stellt jedes Thema auf `master=kontingent`. Vorher merkt es sich – unter der Themensperre, für
genau den Zustand, der umgeschaltet wird – jede feste Rolle `claude|codex` in `<daten>/alle-vorher.json`
(`{"version": 1, "zeit": …, "themen": {thema: master}}`). Ein Eintrag wird nur durch eine feste Rolle ersetzt,
nie durch „kontingent“; ein zweiter Aufruf verliert also nichts.

`zurueck` stellt die gemerkten Rollen wieder her, solange das Thema noch auf Kontingent oder schon auf der
gemerkten Rolle steht (halbfertige Wechsel werden vervollständigt). Eine inzwischen von Hand gesetzte andere Rolle
bleibt. Sind alle Einträge erledigt, wird die Merkdatei nach `alle-vorher.<zeitstempel>.json` verschoben – nie
gelöscht; offene Einträge bleiben für einen erneuten Aufruf stehen.

Hermes bleibt immer unberührt: Hermes-Master, Hermes-Besitz und ein abgebrochener Wechsel zu Hermes (eigene
Zwischenmarke mit Ziel Hermes). Eine Zwischenmarke mit fremdem Ziel wird nie fortgesetzt. Alles läuft unter der
Instanzsperre `alle`; die Reihenfolge ist immer `alle` → Thema (`modi.master_setzen_wenn`).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import besitz, modi, paare, zustand
from .signale import _atomar_schreiben, daten_ordner

FESTE = ("claude", "codex")
HERMES = "hermes"
# Rollen, deren Besitz ein Sammelbefehl nicht überschreibt: `hermes` hält sensible Arbeit, `agy` eine
# ausdrücklich übergebene Antigravity-Sitzung.
GESCHUETZT = ("hermes", "agy")
GESCHUETZT_NAMEN = {"hermes": "Hermes", "agy": "Antigravity"}


class AlleFehler(Exception):
    """Sperre belegt oder Merkdatei ungültig – es wurde nichts geändert."""


class MerkFehler(AlleFehler):
    """Merkdatei unlesbar oder ungültig."""


@dataclass
class Bericht:
    zeilen: list[str] = field(default_factory=list)
    offen: int = 0


def merkdatei() -> Path:
    return daten_ordner() / "alle-vorher.json"


def _themen() -> list[str]:
    return sorted(set(modi.lesen()) | {p.thema for p in paare.lesen()})


def gemerkt(pfad: Path | None = None) -> dict[str, str] | None:
    """Gemerkte feste Rollen je Thema; `None`, wenn keine Merkdatei da ist. Ungültig ⇒ `AlleFehler`."""
    pfad = pfad or merkdatei()
    try:
        text = pfad.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError) as fehler:
        raise MerkFehler(f"Merkdatei unlesbar ({type(fehler).__name__})") from fehler
    try:
        roh = json.loads(text)
    except ValueError as fehler:
        raise MerkFehler("Merkdatei ist kein gültiges JSON") from fehler
    if not isinstance(roh, dict) or roh.get("version") != 1 or not isinstance(roh.get("themen"), dict):
        raise MerkFehler("Merkdatei hat ein unbekanntes Format")
    themen: dict[str, str] = {}
    for thema, master in roh["themen"].items():
        try:
            paare.thema_pruefen(thema)
        except paare.PaarFehler as fehler:
            raise MerkFehler(f"Merkdatei nennt ein ungültiges Thema: {fehler}") from fehler
        if master not in FESTE:
            raise MerkFehler(f"Merkdatei nennt für {thema} keine feste Rolle: {master!r}")
        themen[thema] = master
    return themen


def _merken(pfad: Path, themen: dict[str, str]) -> None:
    _atomar_schreiben(pfad, json.dumps({"version": 1, "zeit": datetime.now(timezone.utc).isoformat(),
                                        "themen": dict(sorted(themen.items()))}, ensure_ascii=False))


def _geschuetzte_rolle(alt: modi.Profil, besitzer: str, zwischenziel: str | None) -> str | None:
    """Name der geschützten Rolle, die dieses Thema gerade hält – sonst `None`."""
    for wert in (alt.master, besitzer, zwischenziel):
        if wert in GESCHUETZT:
            return GESCHUETZT_NAMEN[wert]
    return None


def auf_kontingent(repo: Path | None = None) -> Bericht:
    """Alle Themen (außer Hermes) nach Kontingent; feste Rollen vorher merken."""
    with zustand.instanz_sperre("alle") as frei:
        if not frei:
            raise AlleFehler("Sammelbefehl läuft schon – nichts geändert")
        pfad = merkdatei()
        merk = gemerkt(pfad) or {}
        bericht = Bericht()
        for thema in _themen():
            text: list[str] = []
            offen = False

            def pruefung(alt: modi.Profil, besitzer: str, zwischenziel: str | None) -> bool:
                nonlocal offen
                geschuetzt = _geschuetzte_rolle(alt, besitzer, zwischenziel)
                if geschuetzt is not None:
                    text.append(f"ausgelassen ({geschuetzt})")
                    return False
                if zwischenziel is not None and zwischenziel != besitz.CLAUDE:
                    offen = True
                    text.append(f"offen: unvollständiger Wechsel zu {zwischenziel} – erst abschließen")
                    return False
                if alt.master in FESTE:
                    if merk.get(thema) != alt.master:
                        _merken(pfad, {**merk, thema: alt.master})   # erst gemerkt, dann umgeschaltet
                        merk[thema] = alt.master
                    text.append(f"{alt.master} → Kontingent (gemerkt)")
                elif zwischenziel is not None:
                    text.append("Kontingent (halbfertigen Wechsel abgeschlossen)")
                else:
                    text.append("bleibt Kontingent")
                return True

            try:
                modi.master_setzen_wenn(thema, modi.KONTINGENT, pruefung, repo=repo)
            except modi.ModusFehler as fehler:
                offen = True
                text[:] = [f"offen: {fehler}"]
            bericht.offen += offen
            bericht.zeilen.append(f"{thema}: {text[-1] if text else 'unverändert'}")
        return bericht


def zurueck(repo: Path | None = None) -> Bericht:
    """Gemerkte feste Rollen wiederherstellen; danach Merkdatei archivieren (nie löschen)."""
    with zustand.instanz_sperre("alle") as frei:
        if not frei:
            raise AlleFehler("Sammelbefehl läuft schon – nichts geändert")
        pfad = merkdatei()
        merk = gemerkt(pfad)
        if merk is None:
            return Bericht(["Nichts gemerkt – nichts zu tun."])
        vorhanden = set(_themen())
        bericht = Bericht()
        rest: dict[str, str] = {}
        for thema, ziel in merk.items():
            if thema not in vorhanden:
                bericht.zeilen.append(f"{thema}: übersprungen (Thema nicht mehr vorhanden)")
                continue
            text: list[str] = []
            offen = False

            def pruefung(alt: modi.Profil, besitzer: str, zwischenziel: str | None) -> bool:
                nonlocal offen
                geschuetzt = _geschuetzte_rolle(alt, besitzer, zwischenziel)
                if geschuetzt is not None:
                    offen = True
                    text.append(f"offen: {geschuetzt} hält Besitz – nichts überschrieben")
                    return False
                if zwischenziel is not None and zwischenziel != ziel:
                    offen = True
                    text.append(f"offen: unvollständiger Wechsel zu {zwischenziel} – erst abschließen")
                    return False
                if alt.master not in (modi.KONTINGENT, ziel):
                    text.append(f"bleibt {alt.master} (inzwischen geändert)")
                    return False
                text.append(f"→ {ziel}")
                return True

            try:
                modi.master_setzen_wenn(thema, ziel, pruefung, repo=repo)
            except modi.ModusFehler as fehler:
                offen = True
                text[:] = [f"offen: {fehler}"]
            if offen:
                rest[thema] = ziel
            bericht.zeilen.append(f"{thema}: {text[-1] if text else 'unverändert'}")
        bericht.offen = len(rest)
        if rest:
            _merken(pfad, rest)
        else:
            stempel = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            os.replace(pfad, pfad.with_name(f"alle-vorher.{stempel}.json"))
        return bericht
