"""Zuordnung von Chats zu Projekten (Themen): Vorschläge und von Sebastian bestätigte Zuordnungen.

* `projekte.json` im Datenordner: Liste `{"thema", "ordner": [Präfixe], "stichwoerter": [Wörter]}`.
* `zuordnung.json` im Datenordner: Objekt `{"<werkzeug>:<kennung>": "<thema>"}` – nur Bestätigtes,
  nur für Claude- und Hermes-Chats.
* Für **Codex-Chats** ist allein das Paar (`paare.json`) die Bestätigung: `bestaetigen` setzt das
  Paar, schreibt nichts in `zuordnung.json`, und Codex-Einträge dort werden ignoriert. So gibt es
  für Codex nur eine Quelle der Wahrheit, die nicht halb geschrieben auseinanderlaufen kann.

Der Vorschlag für einen Chat folgt dieser Rangfolge: (1) bestätigte Zuordnung (Claude/Hermes) bzw.
Paar (Codex), (2) längstes passendes Ordnerpräfix (case-insensitiv, `\\` und `/`
gleich, nur ganze Pfadsegmente; bei Gleichstand verschiedener Themen kein Treffer), (4) Stichwort
als ganzes Wort im Titel (case-insensitiv) – nur, wenn genau ein Projekt passt.

Datenschutz (Regel G9): Titel und Ordner werden nur lokal ausgewertet und nie weitergegeben.
Gesperrt wird mit der Sperre des Zustands (`zustand.sperre`); `paare.setzen` sperrt nicht selbst
und läuft bei Codex-Chats unter dieser Sperre.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import chat_register, paare, zustand
from .chat_register import Chat
from .signale import _atomar_schreiben, daten_ordner

WERKZEUGE = ("claude", "codex", "hermes", "agy")
ORDNER_MAX = 500
STICHWORT_MAX = 80
LISTE_MAX = 50

GRUND_BESTAETIGT = "bestätigt"
GRUND_PAAR = "Paar"
GRUND_ORDNER = "Ordner"
GRUND_STICHWORT = "Stichwort"
GRUND_UNBEKANNT = "unbekannt"


class ZuordnungFehler(Exception):
    """Thema, Werkzeug, Kennung oder Projektangabe ist nicht zulässig."""


@dataclass(frozen=True)
class Projekt:
    thema: str
    ordner: tuple[str, ...] = ()
    stichwoerter: tuple[str, ...] = ()


def projekte_datei() -> Path:
    return daten_ordner() / "projekte.json"


def zuordnung_datei() -> Path:
    return daten_ordner() / "zuordnung.json"


# --- Prüfungen -----------------------------------------------------------------

def _thema(thema: object) -> str:
    try:
        return paare.thema_pruefen(thema)  # type: ignore[arg-type]
    except paare.PaarFehler as fehler:
        raise ZuordnungFehler(str(fehler)) from None


def _schluessel(werkzeug: object, kennung: object) -> str:
    if werkzeug not in WERKZEUGE:
        raise ZuordnungFehler(f"Werkzeug unbekannt (erlaubt: {', '.join(WERKZEUGE)}): {werkzeug!r}")
    if not isinstance(kennung, str) or chat_register.KENNUNG_MUSTER.fullmatch(kennung) is None:
        raise ZuordnungFehler("Chat-Kennung unzulässig (erlaubt: A-Z, a-z, 0-9, _ und -, 1–80 Zeichen)")
    return f"{werkzeug}:{kennung}"


def _liste(werte: object, name: str, grenze: int) -> tuple[str, ...]:
    if isinstance(werte, str) or not isinstance(werte, (list, tuple)):
        raise ZuordnungFehler(f"{name} muss eine Liste von Texten sein")
    if len(werte) > LISTE_MAX:
        raise ZuordnungFehler(f"{name}: höchstens {LISTE_MAX} Einträge")
    sauber: list[str] = []
    for wert in werte:
        if not isinstance(wert, str) or not wert.strip():
            raise ZuordnungFehler(f"{name}: nur nichtleere Texte erlaubt")
        text = wert.strip()
        if len(text) > grenze:
            raise ZuordnungFehler(f"{name}: Eintrag länger als {grenze} Zeichen")
        if text not in sauber:
            sauber.append(text)
    return tuple(sauber)


# --- Projekte -------------------------------------------------------------------

def _projekt(roh: object) -> Projekt | None:
    if not isinstance(roh, dict):
        return None
    try:
        return Projekt(_thema(roh.get("thema")), _liste(roh.get("ordner", []), "ordner", ORDNER_MAX),
                       _liste(roh.get("stichwoerter", []), "stichwoerter", STICHWORT_MAX))
    except ZuordnungFehler:
        return None


def projekte_lesen() -> list[Projekt]:
    """Fehlende oder kaputte Datei ergibt eine leere Liste; unbrauchbare Einträge werden übersprungen."""
    try:
        roh = json.loads(projekte_datei().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(roh, list):
        return []
    projekte: dict[str, Projekt] = {}
    for eintrag in roh:
        projekt = _projekt(eintrag)
        if projekt is not None:
            projekte[projekt.thema] = projekt
    return sorted(projekte.values(), key=lambda p: p.thema)


def projekt_setzen(thema: str, ordner: list[str] | tuple[str, ...],
                   stichwoerter: list[str] | tuple[str, ...]) -> Projekt:
    """Projekt anlegen oder ersetzen (atomar unter der Sperre)."""
    neu = Projekt(_thema(thema), _liste(ordner, "ordner", ORDNER_MAX),
                  _liste(stichwoerter, "stichwoerter", STICHWORT_MAX))
    with zustand.sperre():
        alt = [p for p in projekte_lesen() if p.thema != neu.thema]
        inhalt = [{"thema": p.thema, "ordner": list(p.ordner), "stichwoerter": list(p.stichwoerter)}
                  for p in sorted([*alt, neu], key=lambda p: p.thema)]
        _atomar_schreiben(projekte_datei(), json.dumps(inhalt, ensure_ascii=False, indent=2))
    return neu


# --- Bestätigte Zuordnung ----------------------------------------------------------

def zuordnung_lesen() -> dict[str, str]:
    """Fehlende oder kaputte Datei ergibt `{}`; ungültige Einträge werden übersprungen."""
    try:
        roh = json.loads(zuordnung_datei().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(roh, dict):
        return {}
    sauber: dict[str, str] = {}
    for schluessel, thema in roh.items():
        werkzeug, _, kennung = str(schluessel).partition(":")
        try:
            sauber[_schluessel(werkzeug, kennung)] = _thema(thema)
        except ZuordnungFehler:
            continue
    return sauber


def _zuordnung_schreiben(inhalt: dict[str, str]) -> None:
    _atomar_schreiben(zuordnung_datei(), json.dumps(dict(sorted(inhalt.items())), ensure_ascii=False, indent=2))


def bestaetigen(chat_werkzeug: str, kennung: str, thema: str) -> str:
    """Zuordnung als von Sebastian bestätigt speichern; gibt den Schlüssel zurück.

    Bei einem Codex-Chat ist das Paar die Bestätigung: unter der Sperre wird nur das Paar des Themas
    auf diesen Chat gesetzt (`paare.setzen`, `aktiv` bleibt erhalten), `zuordnung.json` bleibt
    unberührt. Ob die Kennung als Paar-UUID taugt und nicht schon zu einem anderen Thema gehört,
    wird **vor** dem Schreiben geprüft.
    """
    schluessel, thema = _schluessel(chat_werkzeug, kennung), _thema(thema)
    if chat_werkzeug == "codex":
        try:
            thread = paare.thread_pruefen(kennung)
        except paare.PaarFehler as fehler:
            raise ZuordnungFehler(str(fehler)) from None
        fremd = next((p for p in paare.lesen() if p.codex_thread == thread and p.thema != thema), None)
        if fremd is not None:
            raise ZuordnungFehler(f"Kennung gehört schon zum Paar des Themas {fremd.thema!r}")
    with zustand.sperre():
        if chat_werkzeug == "codex":
            try:
                paare.setzen(thema, kennung, paare.laufend_bilden(thema))
            except paare.PaarFehler as fehler:
                raise ZuordnungFehler(f"Paar nicht gesetzt: {fehler}") from None
            return schluessel
        inhalt = zuordnung_lesen()
        inhalt[schluessel] = thema
        _zuordnung_schreiben(inhalt)
    return schluessel


def aufheben(werkzeug: str, kennung: str) -> bool:
    """Bestätigung entfernen; `True`, wenn es eine gab. Ein vorhandenes Paar bleibt unberührt
    (für Codex-Chats gibt es keine Bestätigung außerhalb des Paars)."""
    schluessel = _schluessel(werkzeug, kennung)
    with zustand.sperre():
        inhalt = zuordnung_lesen()
        if schluessel not in inhalt:
            return False
        del inhalt[schluessel]
        _zuordnung_schreiben(inhalt)
    return True


# --- Vorschlag ---------------------------------------------------------------------

def _pfad(text: str) -> str:
    return text.replace("\\", "/").strip().rstrip("/").casefold()


def _ordner_treffer(ordner: str, projekte: list[Projekt]) -> str | None:
    """Thema mit dem längsten passenden Präfix (ganze Segmente); bei Gleichstand mehrerer Themen `None`."""
    pfad = _pfad(ordner)
    if not pfad:
        return None
    beste = 0
    themen: set[str] = set()
    for projekt in projekte:
        for praefix in projekt.ordner:
            kurz = _pfad(praefix)
            if not kurz or not (pfad == kurz or pfad.startswith(kurz + "/")):
                continue
            if len(kurz) > beste:
                beste, themen = len(kurz), {projekt.thema}
            elif len(kurz) == beste:
                themen.add(projekt.thema)
    return next(iter(themen)) if len(themen) == 1 else None


def _stichwort_treffer(titel: str, projekte: list[Projekt]) -> str | None:
    if not titel:
        return None
    passend = {p.thema for p in projekte for wort in p.stichwoerter
               if re.search(rf"(?<!\w){re.escape(wort)}(?!\w)", titel, re.IGNORECASE)}
    return next(iter(passend)) if len(passend) == 1 else None


def vorschlag(chat: Chat, projekte: list[Projekt] | None = None, paare_liste: list[paare.Paar] | None = None,
              zuordnung: dict[str, str] | None = None) -> tuple[str | None, str]:
    """Thema-Vorschlag mit Grund (`bestätigt`, `Paar`, `Ordner`, `Stichwort`) oder `(None, "unbekannt")`."""
    projekte = projekte_lesen() if projekte is None else projekte
    paare_liste = paare.lesen() if paare_liste is None else paare_liste
    zuordnung = zuordnung_lesen() if zuordnung is None else zuordnung
    bestaetigt = None if chat.werkzeug == "codex" else zuordnung.get(f"{chat.werkzeug}:{chat.kennung}")
    if bestaetigt:
        return bestaetigt, GRUND_BESTAETIGT
    if chat.werkzeug == "codex":
        paar = next((p for p in paare_liste if p.codex_thread.lower() == chat.kennung.lower()), None)
        if paar is not None:
            return paar.thema, GRUND_PAAR
    thema = _ordner_treffer(chat.ordner, projekte)
    if thema is not None:
        return thema, GRUND_ORDNER
    thema = _stichwort_treffer(chat.titel, projekte)
    if thema is not None:
        return thema, GRUND_STICHWORT
    return None, GRUND_UNBEKANNT


def uebersicht_mit_quellen(jetzt: datetime | None = None) -> tuple[chat_register.Ergebnis,
                                                                     list[tuple[Chat, str | None, str]]]:
    """Register samt Quellenstatus und je Chat ein Vorschlag (Projekte, Paare, Zuordnung einmal gelesen)."""
    ergebnis = chat_register.lesen(jetzt)
    projekte, paare_liste, zuordnung = projekte_lesen(), paare.lesen(), zuordnung_lesen()
    zeilen = [(chat, *vorschlag(chat, projekte, paare_liste, zuordnung)) for chat in ergebnis.chats]
    return ergebnis, zeilen


def uebersicht(jetzt: datetime | None = None) -> list[tuple[Chat, str | None, str]]:
    """Register plus Vorschläge (für Fenster und Befehlszeile)."""
    return uebersicht_mit_quellen(jetzt)[1]
