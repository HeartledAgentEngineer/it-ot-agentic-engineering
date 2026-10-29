"""Datenmodell und Aktionen des Übersichtsfensters (`uebersicht.py`) – ohne Tk, ohne Bildschirm.

`aufnehmen()` liest alle Quellen **nur lesend** (dieselben Bausteine wie `masterwechsel status`: Kontingente,
Themenprofile, Besitz, Wartet-worauf, Sitzungen, Messfehler-Status, Modellkataloge) und liefert eine unveränderliche
Momentaufnahme `Uebersicht`. Die Aktionen (Master, Prüfer, Ausführer, Modell, Arbeitsweise und Auto-Freigabe je Thema,
„Alle nach Kontingent“, „Alle wie vorher“, Hauptschalter Automatik, „Übergabe starten“) sind `Aktion`en mit Rückfragetext
und einer Ausführfunktion; das Fenster fragt (`dialog.frage`) und führt nur bei „Ja“ aus. `modell_liste` baut die
Modellauswahl je Ausführer streng nach `modi.modell_setzen`.

**Ein Repo-Ort für Lesen und Schreiben:** `aufnehmen()` bestimmt je Aufnahme genau einmal
`repo = uebergabe.haupt_wurzel(uebergabe.repo_wurzel())` (wie der Master-Status), liest damit den Besitz und merkt es in der
Momentaufnahme. Jede Schreibaktion nutzt **genau dieses** `repo` (`modi.master_setzen(..., repo=repo)`,
`alle.auf_kontingent(repo=repo)`, `alle.zurueck(repo=repo)`) – nie ein Aufruf ohne `repo`. Geschrieben wird nur,
wenn `repo/.git` ein **Ordner** ist (echter Hauptarbeitsbaum). Ist das Repo nicht bestimmbar oder ist `.git` eine
Datei (die Auflösung über `commondir` ist gescheitert und hat still die Arbeitskopie geliefert), sind alle
Schreibaktionen gesperrt („Hauptarbeitsbaum nicht gefunden – nur Anzeige“). Die Prüfung läuft bei der Aufnahme und
noch einmal unmittelbar vor dem Schreiben.

Nichts Sensibles in der Anzeige: keine Chat-Titel, keine Codex-Chat-Kennungen, keine Pfade (außer wie im Master-Status).
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone, tzinfo
from pathlib import Path
from typing import Callable

from . import (alle, anzeige, arbeitsweise, assistent_vorgaenge as wechsel_vorgaenge, kurz, modelle, modi, paare,
               pruefer_wahl, rollen, rollen_anzeige, signale, symbol, wartet)
from .signale import Fenster, Kontingent

NUR_ANZEIGE = "Hauptarbeitsbaum nicht gefunden – nur Anzeige"
MASTER_WERTE = tuple(wert for _, wert in anzeige.MASTER_AUSWAHL)   # kontingent, claude, codex, hermes
MASTER_TEXTE = dict(anzeige.ROLLEN_NAMEN)
ARBEITSWEISE_WERTE = arbeitsweise.WERTE             # protokoll, vibe
ARBEITSWEISE_TEXTE = arbeitsweise.ANZEIGE           # Protokoll, Vibe, ? (Datei ungültig)
PRUEFER_WERTE = pruefer_wahl.WERTE                  # automatisch, codex, hermes
PRUEFER_TEXTE = pruefer_wahl.ANZEIGE                # Automatisch, Codex, Hermes, ? (Datei ungültig)
AUSFUEHRER_WERTE = modi.WORKER_WERTE                # workflow, claude, codex, hermes
AUSFUEHRER_TEXTE = {"workflow": "Workflow", "claude": "Claude", "codex": "Codex", "hermes": "Hermes", "agy": "Antigravity"}
AUTO_WERTE = (True, False)
AUTO_TEXTE = {True: "An", False: "Aus"}
STANDARD_MODELL = "Standard"
MODELL_GESPERRT_WORKFLOW = "— (nach Matrix aufgelöst)"
KATALOG_NICHT_GEPRUEFT = "Modellkatalog nicht geprüft"
GRAU = "#9ca3af"          # Balkenfarbe bei unbekanntem Verbrauch
TEXT_MAX = 400            # Meldungen aus Ausnahmen werden begrenzt


class AktionAbgelehnt(Exception):
    """Die Aktion ist in diesem Zustand nicht erlaubt (Text für die Statuszeile); es wurde nichts geändert."""


@dataclass(frozen=True)
class Balken:
    """Ein Kontingent-Fenster als Fortschrittsbalken."""

    abo: str                 # „Claude“ / „Codex“
    fenster: str             # „5h“ / „Woche“
    prozent: int             # 0–100 für den Balken; unbekannt = 0
    text: str                # „62 % verbraucht“, „unbekannt“, „neu, nicht gemessen“
    farbe: str               # „#rrggbb“: Grundfarbe, gelb ab 80 %, rot ab Schwelle (wie das Symbol)
    reset: str               # „Reset in 3 h 20 min (14:30)“ oder leer
    bekannt: bool


@dataclass(frozen=True)
class Abo:
    name: str
    balken: tuple[Balken, ...]
    gemessen: str            # „gemessen 12:03“ / „Messzeit unbekannt“
    fehler: str | None       # Kontingent nicht lesbar (fester Text aus `signale`)
    messfehler: str | None   # „Claude-Messung scheitert seit … (letzter Versuch …): …“ aus `messfehler.json`


@dataclass(frozen=True)
class ThemaZeile:
    thema: str
    master: str
    besitz: str
    pruefer: str
    ausfuehrer: str
    auto: str
    master_wert: str         # Masterrolle des Profils: kontingent | claude | codex | hermes
    arbeitsweise: str = arbeitsweise.PROTOKOLL   # protokoll | vibe | ? (Datei ungültig)
    worker_wert: str = modi.WORKFLOW             # Ausführer des Profils: workflow | claude | codex | hermes
    pruefer_wert: str = pruefer_wahl.AUTOMATISCH   # Prüferwahl: automatisch | codex | hermes | ? (Datei ungültig)
    pruefer_warnung: bool = False                # Prüfer aus derselben Familie wie der Master (gelber Hinweis)
    auto_zustand: str = anzeige.AUTO_OHNE_PAAR   # wirksam | wartet | aus | ohne | ? (siehe `anzeige.auto_zustand`)
    paar_aktiv: bool | None = None               # gespeicherte Paarfreigabe; None = kein Codex-Paar
    modell_wert: str | None = None               # gespeichertes Ausführermodell des Profils (None = Standard)
    pk_master: str | None = None                 # Master, den `pruefkreis` liest; None = Besitz unklar


@dataclass(frozen=True)
class KatalogAnsicht:
    """Modellkatalog eines Anbieters (`claude` | `codex`) für die Modellliste – gelesen bei der Aufnahme, nie im Tk-Thread."""

    anbieter: str
    geprueft: bool                           # erfolgreich ermittelt und nicht veraltet (wie `modi._katalog_pruefen`)
    modelle: tuple[tuple[str, str], ...] = ()    # (Kennung, Anzeigename)


@dataclass(frozen=True)
class ModellListe:
    """Auswahl der Modellliste für ein Thema: (Anzeige, Wert) mit Wert `None` = Standard des Werkzeugs."""

    eintraege: tuple[tuple[str, str | None], ...]
    aktuell: str                             # Anzeigetext des gespeicherten Modells
    gesperrt: bool
    hinweis: str = ""


@dataclass(frozen=True)
class Uebersicht:
    zeit: str
    lage: str | None
    lage_text: str
    automatik: bool | None   # None = unbekannt (Lesen gescheitert) ⇒ Umschalten gesperrt
    schwelle: int
    abos: tuple[Abo, ...]
    themen: tuple[ThemaZeile, ...]
    wartet: tuple[str, ...]
    sitzungen: tuple[str, ...]
    hinweise: tuple[str, ...]
    repo: Path | None        # der eine Ort für Lesen und Schreiben dieser Aufnahme
    schreiben: bool          # Schreibaktionen erlaubt (`repo/.git` ist ein Ordner)
    schreib_hinweis: str     # leer oder `NUR_ANZEIGE`
    kataloge: tuple[KatalogAnsicht, ...] = ()   # Modellkataloge claude/codex für die Modellliste
    wechsel_themen: tuple[str, ...] = ()
    wechsel_pruefbar: bool = False


@dataclass(frozen=True)
class Ergebnis:
    ok: bool
    text: str
    bericht: str = ""        # mehrzeiliger Bericht (Sammelbefehle) für das Textfeld


@dataclass(frozen=True)
class Aktion:
    titel: str
    frage: str                               # Text der Ja/Nein-Rückfrage
    ausfuehren: Callable[[], Ergebnis]       # läuft im Hintergrund; ruft nie die Rückfrage auf


# --- Repo-Ort -------------------------------------------------------------------------------------

def schreibbar(repo: Path | None) -> bool:
    """Nur ein echter Hauptarbeitsbaum (`.git` ist ein Ordner) darf beschrieben werden."""
    if repo is None:
        return False
    try:
        return (repo / ".git").is_dir()
    except OSError:
        return False


# --- Aufnehmen --------------------------------------------------------------------------------------

def _hex(farbe: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*farbe)


def _balken(abo: str, name: str, f: Fenster | None, grundfarbe: tuple[int, int, int], schwelle: int,
            jetzt: datetime, zone: tzinfo | None, lesbar: bool) -> Balken:
    if not lesbar or f is None or f.prozent is None:
        return Balken(abo, name, 0, "unbekannt", GRAU, "", False)
    if f.zurueckgesetzt:
        return Balken(abo, name, 0, "neu, nicht gemessen", _hex(grundfarbe),
                      f"zurückgesetzt {kurz._uhr(f.reset, jetzt, zone)}" if f.reset else "", True)
    prozent = kurz.verbraucht(f.prozent)
    reset = f"Reset in {kurz.dauer(f.reset - jetzt)} ({kurz._uhr(f.reset, jetzt, zone)})" if f.reset else ""
    return Balken(abo, name, prozent, f"{prozent} % verbraucht", _hex(symbol.farbe(f.prozent, grundfarbe, schwelle)),
                  reset, True)


def _abo(k: Kontingent, grundfarbe: tuple[int, int, int], schwelle: int, messfehler: dict[str, signale.Messfehler],
         jetzt: datetime, zone: tzinfo | None) -> Abo:
    balken = tuple(_balken(k.master, n, k.fenster_nach_name(n), grundfarbe, schwelle, jetzt, zone, not k.fehler)
                   for n in ("5h", "Woche"))
    gemessen = f"gemessen {kurz._uhr(k.stand, jetzt, zone)}" if k.stand else "Messzeit unbekannt"
    eintrag = messfehler.get(k.master.lower())
    return Abo(k.master, balken, "" if k.fehler else gemessen, k.fehler,
               kurz.messfehler_zeile(k.master, eintrag, jetzt, zone) if eintrag else None)


def aufnehmen(jetzt: datetime | None = None, zone: tzinfo | None = None) -> Uebersicht:
    """Alle Quellen lesen (nichts schreiben, nichts messen). Das Repo wird dabei genau einmal bestimmt."""
    jetzt = jetzt or datetime.now(timezone.utc)
    repo = kurz.repo_bestimmen()
    themen, hinweise = kurz._themen(repo)
    hinweise = kurz._gemerkt_hinweis() + hinweise
    wechsel_pruefbar = False
    wechsel_themen: tuple[str, ...] = ()
    try:
        wechsel = wechsel_vorgaenge.lesen_geprueft()
        wechsel_themen = tuple(sorted({v.thema for v in wechsel if v.phase in wechsel_vorgaenge.WECHSEL_BLOCKIEREND}))
        wechsel_pruefbar = True
    except wechsel_vorgaenge.AssistentFehler:
        hinweise.append("Wechselregister nicht prüfbar – Themenvorauswahl gesperrt.")
    kontingente = signale.alle_lesen(jetzt=jetzt)
    schwelle = anzeige.schwelle()
    automatik = anzeige.automatik_an()
    claude, codex = kontingente[0], kontingente[1]
    lage = rollen.lage(claude, codex, schwelle)
    grund = rollen.lage_grund(claude, codex, schwelle)
    messfehler = signale.messfehler_lesen()
    try:
        gemini = signale.gemini_lesen(jetzt=jetzt)
        alle_k = [*kontingente, gemini]
        farben = (symbol.CLAUDE, symbol.CODEX, symbol.GEMINI)
    except Exception:
        alle_k = kontingente
        farben = (symbol.CLAUDE, symbol.CODEX)
    abos = tuple(_abo(k, farbe, schwelle, messfehler, jetzt, zone)
                 for k, farbe in zip(alle_k, farben))
    zeilen = tuple(_thema_zeile(t, automatik, lage) for t in sorted(themen, key=lambda t: t.name))
    kataloge = tuple(_katalog_ansicht(anbieter, jetzt) for anbieter in modelle.PROVIDER)
    neueste = sorted(kurz._sitzungen(), key=lambda s: s.zeit, reverse=True)[:kurz.MAX_SITZUNGEN]
    erlaubt = schreibbar(repo)
    return Uebersicht(
        zeit=kurz._uhr(jetzt, jetzt, zone), lage=lage,
        lage_text=f"Lage {lage}" if lage else "Lage ?" + (f" – {grund}" if grund else ""),
        automatik=automatik, schwelle=schwelle, abos=abos, themen=zeilen,
        wartet=tuple(kurz._wartet_zeile(m, jetzt, zone) for m in sorted(wartet.alle_lesen(), key=lambda m: m.zeit)),
        sitzungen=tuple(kurz._sitzung_zeile(s, jetzt, zone) for s in neueste),
        hinweise=tuple(hinweise), repo=repo, schreiben=erlaubt, schreib_hinweis="" if erlaubt else NUR_ANZEIGE,
        kataloge=kataloge, wechsel_themen=wechsel_themen, wechsel_pruefbar=wechsel_pruefbar)


def _katalog_ansicht(anbieter: str, jetzt: datetime) -> KatalogAnsicht:
    """Katalog nur lesen (nie abfragen); „geprüft“ wie `modi._katalog_pruefen`: ermittelt, ohne Fehler, nicht veraltet."""
    try:
        katalog = modelle.lesen(anbieter, jetzt=jetzt)
    except Exception:  # noqa: BLE001 - ein defekter Cache macht die Liste nur „nicht geprüft“
        return KatalogAnsicht(anbieter, False)
    if not isinstance(katalog, modelle.Katalog) or katalog.fehler is not None or katalog.veraltet:
        return KatalogAnsicht(anbieter, False)
    return KatalogAnsicht(anbieter, True, tuple((m.id, m.name or m.id) for m in katalog.modelle))


def _thema_zeile(t: kurz.Thema, automatik: bool, lage: str | None = None) -> ThemaZeile:
    master, besitz_text, pruefer, ausfuehrer, auto = kurz.thema_felder(t, automatik, lage)
    return ThemaZeile(t.name, master, besitz_text.removeprefix("Besitz "), pruefer.removeprefix("Prüfer "),
                      ausfuehrer, auto, t.profil.master, t.arbeitsweise, t.profil.worker, t.pruefer_wahl,
                      rollen_anzeige.gleiche_familie(t.pruefkreis_master, t.pruefer_wahl, t.arbeitsweise),
                      anzeige.auto_zustand(automatik, t.paar_aktiv, t.profil.master)[0], t.paar_aktiv,
                      t.profil.modell, t.pruefkreis_master)


def modell_liste(zeile: ThemaZeile, kataloge: tuple[KatalogAnsicht, ...]) -> ModellListe:
    """Modellliste des Ausführers – streng nach `modi.modell_setzen` und `modelle.PROVIDER`.

    * Claude/Codex: „Standard“ (= `None`) plus die Modelle des geprüften Katalogs; ist der Katalog veraltet, fehlerhaft
      oder fehlt, nur „Standard“ und das gespeicherte Modell (eine feste Wahl würde `modi` ohnehin ablehnen) mit dem
      Hinweis „Modellkatalog nicht geprüft“.
    * Hermes: gesperrt, zeigt fest `modi.HERMES_MODELL` (kein „Standard“; `worker_setzen` setzt die Kennung selbst).
    * Workflow: gesperrt, kein festes Modell.
    """
    if zeile.worker_wert == modi.WORKFLOW:
        return ModellListe((), MODELL_GESPERRT_WORKFLOW, True)
    if zeile.worker_wert == "hermes":
        return ModellListe(((rollen_anzeige.HERMES_ANZEIGE, modi.HERMES_MODELL),), rollen_anzeige.HERMES_ANZEIGE, True)
    if zeile.worker_wert == "agy":
        return ModellListe(((STANDARD_MODELL, None),), STANDARD_MODELL, True)
    if zeile.worker_wert not in modelle.PROVIDER:
        return ModellListe((), "?", True)
    katalog = next((k for k in kataloge if k.anbieter == zeile.worker_wert), None)
    eintraege: list[tuple[str, str | None]] = [(STANDARD_MODELL, None)]
    geprueft = katalog is not None and katalog.geprueft
    if geprueft:
        eintraege += [(name, kennung) for kennung, name in katalog.modelle]
    if zeile.modell_wert is not None and all(wert != zeile.modell_wert for _, wert in eintraege):
        eintraege.append((zeile.modell_wert, zeile.modell_wert))          # gespeichert, aber (noch) nicht im Katalog
    aktuell = next((text for text, wert in eintraege if wert == zeile.modell_wert), STANDARD_MODELL)
    return ModellListe(tuple(eintraege), aktuell, False, "" if geprueft else KATALOG_NICHT_GEPRUEFT)


def abo_meldungen(abo: Abo) -> list[str]:
    """Rote Zeilen unter einem Abo: nicht lesbares Kontingent und/oder scheiternde Messung (Grund aus `messfehler.json`)."""
    zeilen = [f"{abo.name}: keine Messdaten ({abo.fehler})"] if abo.fehler else []
    return zeilen + ([abo.messfehler] if abo.messfehler else [])


def leer(hinweis: str, jetzt: datetime | None = None, zone: tzinfo | None = None) -> Uebersicht:
    """Notfall-Aufnahme, wenn das Lesen scheitert: nichts anzeigen, nichts schreiben lassen."""
    jetzt = jetzt or datetime.now(timezone.utc)
    return Uebersicht(zeit=kurz._uhr(jetzt, jetzt, zone), lage=None, lage_text="Lage ?", automatik=None,
                      schwelle=anzeige.STANDARD_SCHWELLE, abos=(), themen=(), wartet=(), sitzungen=(),
                      hinweise=(hinweis,), repo=None, schreiben=False, schreib_hinweis=NUR_ANZEIGE)


# --- Aktionen -------------------------------------------------------------------------------------------

def _begrenzt(text: object) -> str:
    return " ".join(str(text).split())[:TEXT_MAX]


def _schreiben_pruefen(snap: Uebersicht) -> Path:
    if not snap.schreiben or snap.repo is None:
        raise AktionAbgelehnt(NUR_ANZEIGE)
    return snap.repo


def master_aktion(snap: Uebersicht, thema: str, wert: str) -> Aktion:
    """Masterrolle eines Themas auf `wert` stellen (`modi.master_setzen(thema, wert, repo=<Repo der Aufnahme>)`)."""
    repo = _schreiben_pruefen(snap)
    zeile = next((t for t in snap.themen if t.thema == thema), None)
    if zeile is None:
        raise AktionAbgelehnt(f"Thema {thema!r} ist nicht bekannt")
    if wert not in MASTER_WERTE:
        raise AktionAbgelehnt(f"Unbekannte Masterrolle: {wert!r}")
    if wert == zeile.master_wert:
        raise AktionAbgelehnt(f"{thema}: Master ist schon {MASTER_TEXTE[wert]}")
    frage = (f"Master des Themas „{thema}“ von {MASTER_TEXTE.get(zeile.master_wert, zeile.master_wert)} auf "
             f"{MASTER_TEXTE[wert]} stellen?\n\nGespeichert wird die Masterrolle des Themas; "
             "es wird keine Sitzung gestartet.")

    def lauf() -> Ergebnis:
        if not schreibbar(repo):    # unmittelbar vor dem Schreiben noch einmal
            return Ergebnis(False, NUR_ANZEIGE)
        try:
            modi.master_setzen(thema, wert, repo=repo)
        except Exception as fehler:  # noqa: BLE001 - jeder Fehler wird gemeldet, nichts bricht das Fenster
            return Ergebnis(False, f"{thema}: nicht geändert – {_begrenzt(fehler)}")
        return Ergebnis(True, anzeige.master_meldung(thema, wert))

    return Aktion("Master setzen", frage, lauf)


def arbeitsweise_aktion(snap: Uebersicht, thema: str, wert: str) -> Aktion:
    """Arbeitsweise eines Themas auf `wert` (protokoll | vibe) stellen (`modi.vibe_setzen`, nur von Hand).

    Vibe braucht Ausführer Claude und eine lesbare Arbeitsweise-Datei; beides wird hier vorab abgelehnt (die Prüfung
    in `modi` gilt trotzdem noch einmal unter der Themensperre). Geschrieben wird nur der Datenordner, aber wie alle
    Änderungen nur, wenn die Aufnahme einen echten Hauptarbeitsbaum fand (sonst „nur Anzeige“).
    """
    if not snap.schreiben:
        raise AktionAbgelehnt(NUR_ANZEIGE)
    zeile = next((t for t in snap.themen if t.thema == thema), None)
    if zeile is None:
        raise AktionAbgelehnt(f"Thema {thema!r} ist nicht bekannt")
    if wert not in ARBEITSWEISE_WERTE:
        raise AktionAbgelehnt(f"Unbekannte Arbeitsweise: {wert!r}")
    if zeile.arbeitsweise == arbeitsweise.UNBEKANNT:
        raise AktionAbgelehnt(f"{thema}: Arbeitsweise unbekannt (arbeitsweise.json ungültig) – nichts geändert")
    if wert == zeile.arbeitsweise:
        raise AktionAbgelehnt(f"{thema}: Arbeitsweise ist schon {ARBEITSWEISE_TEXTE[wert]}")
    if wert == arbeitsweise.VIBE and zeile.worker_wert != "claude":
        raise AktionAbgelehnt("Vibe braucht Ausführer Claude – erst `masterwechsel worker-setzen "
                              f"{thema} claude`")
    if wert == arbeitsweise.VIBE:
        frage = (f"Arbeitsweise des Themas „{thema}“ auf Vibe stellen?\n\nDann gilt: {arbeitsweise.VIBE_REGEL}.\n\n"
                 "Es wird keine Sitzung gestartet.")
    else:
        frage = (f"Arbeitsweise des Themas „{thema}“ von Vibe auf Protokoll zurückstellen?\n\n"
                 "Die Vibe-Regel entfällt; es wird keine Sitzung gestartet.")

    def lauf() -> Ergebnis:
        if snap.repo is not None and not schreibbar(snap.repo):    # unmittelbar vor dem Schreiben noch einmal
            return Ergebnis(False, NUR_ANZEIGE)
        try:
            modi.vibe_setzen(thema, wert == arbeitsweise.VIBE)
        except Exception as fehler:  # noqa: BLE001 - jeder Fehler wird gemeldet, nichts bricht das Fenster
            return Ergebnis(False, f"{thema}: nicht geändert – {_begrenzt(fehler)}")
        return Ergebnis(True, f"{thema}: Arbeitsweise {ARBEITSWEISE_TEXTE[wert]} gespeichert – keine Sitzung gestartet.")

    return Aktion("Arbeitsweise setzen", frage, lauf)


def _thema_zeile_finden(snap: Uebersicht, thema: str) -> ThemaZeile:
    zeile = next((t for t in snap.themen if t.thema == thema), None)
    if zeile is None:
        raise AktionAbgelehnt(f"Thema {thema!r} ist nicht bekannt")
    return zeile


def pruefer_aktion(snap: Uebersicht, thema: str, wert: str) -> Aktion:
    """Prüfer eines Themas wählen (`pruefer_wahl.setzen`, nur von Hand): automatisch | codex | hermes.

    Gilt für `pruefkreis` ohne `--pruefer`/`--sensibel`, auch für die Familie des Masters. Eine ungültige
    `pruefer.json` wird vorab abgelehnt (sie würde ohnehin nie überschrieben).
    """
    if not snap.schreiben:
        raise AktionAbgelehnt(NUR_ANZEIGE)
    zeile = _thema_zeile_finden(snap, thema)
    if wert not in PRUEFER_WERTE:
        raise AktionAbgelehnt(f"Unbekannter Prüfer: {wert!r}")
    if zeile.pruefer_wert == pruefer_wahl.UNBEKANNT:
        raise AktionAbgelehnt(f"{thema}: Prüferwahl unbekannt (pruefer.json ungültig) – nichts geändert")
    if wert == zeile.pruefer_wert:
        raise AktionAbgelehnt(f"{thema}: Prüfer ist schon {PRUEFER_TEXTE[wert]}")
    if wert == pruefer_wahl.AUTOMATISCH:
        frage = (f"Prüfer des Themas „{thema}“ auf „Automatisch“ stellen?\n\nDann gilt wieder die Regel von pruefkreis "
                 "(Prüfer aus einer anderen Modellfamilie als der Master).\n\nEs wird keine Sitzung gestartet.")
    else:
        frage = (f"Prüfer des Themas „{thema}“ von {PRUEFER_TEXTE[zeile.pruefer_wert]} auf {PRUEFER_TEXTE[wert]} stellen?"
                 f"\n\npruefkreis nutzt künftig {PRUEFER_TEXTE[wert]} für dieses Thema – auch wenn er zur Familie des "
                 "Masters gehört. `--sensibel` prüft weiter immer Hermes, ein ausdrückliches `--pruefer` geht vor.")
        if rollen_anzeige.gleiche_familie(zeile.pk_master, wert, zeile.arbeitsweise):
            frage += "\n\nAchtung: gleiche Familie wie der Master – das weicht von AGENTS.md ab (Ihre Wahl)."
        frage += "\n\nEs wird keine Sitzung gestartet."

    def lauf() -> Ergebnis:
        try:
            pruefer_wahl.setzen(thema, wert)
        except Exception as fehler:  # noqa: BLE001 - jeder Fehler wird gemeldet, nichts bricht das Fenster
            return Ergebnis(False, f"{thema}: nicht geändert – {_begrenzt(fehler)}")
        return Ergebnis(True, f"{thema}: Prüfer {PRUEFER_TEXTE[wert]} gespeichert – keine Sitzung gestartet.")

    return Aktion("Prüfer wählen", frage, lauf)


def ausfuehrer_aktion(snap: Uebersicht, thema: str, wert: str) -> Aktion:
    """Ausführer eines Themas setzen (`modi.worker_setzen(thema, wert, repo=<Repo der Aufnahme>)`).

    Ein Wechsel setzt das Modell zurück (Standard des Werkzeugs, bei Hermes die feste Kennung, bei Workflow keins) –
    die Rückfrage nennt das. Verstöße gegen die Vibe-Regel meldet `modi` als Fehler im Ergebnis.
    """
    repo = _schreiben_pruefen(snap)
    zeile = _thema_zeile_finden(snap, thema)
    if wert not in AUSFUEHRER_WERTE:
        raise AktionAbgelehnt(f"Unbekannter Ausführer: {wert!r}")
    if wert == zeile.worker_wert:
        raise AktionAbgelehnt(f"{thema}: Ausführer ist schon {AUSFUEHRER_TEXTE[wert]}")
    bisher = zeile.modell_wert or STANDARD_MODELL
    if wert == "hermes":
        modell_satz = f"Das Modell wird auf die feste Kennung {rollen_anzeige.HERMES_ANZEIGE} gesetzt (bisher: {bisher})."
    elif wert == modi.WORKFLOW:
        modell_satz = "Das Modell wird zurückgesetzt – bei Workflow gibt es kein festes Modell (nach Matrix aufgelöst)."
    else:
        modell_satz = f"Das Modell wird auf „{STANDARD_MODELL}“ des Werkzeugs zurückgesetzt (bisher: {bisher})."
    frage = (f"Ausführer des Themas „{thema}“ von {AUSFUEHRER_TEXTE.get(zeile.worker_wert, zeile.worker_wert)} auf "
             f"{AUSFUEHRER_TEXTE[wert]} stellen?\n\n{modell_satz}\n\nGespeichert wird die Ausführervorgabe für den "
             "nächsten bereinigten Coding-Auftrag; es wird keine Sitzung gestartet.")

    def lauf() -> Ergebnis:
        if not schreibbar(repo):
            return Ergebnis(False, NUR_ANZEIGE)
        try:
            profil = modi.worker_setzen(thema, wert, repo=repo)
        except Exception as fehler:  # noqa: BLE001
            return Ergebnis(False, f"{thema}: nicht geändert – {_begrenzt(fehler)}")
        return Ergebnis(True, anzeige.ausfuehrer_meldung(thema, wert, getattr(profil, "modell", None)))

    return Aktion("Ausführer setzen", frage, lauf)


def modell_aktion(snap: Uebersicht, thema: str, modell: str | None) -> Aktion:
    """Ausführermodell setzen (`modi.modell_setzen(thema, modell, repo=<Repo der Aufnahme>)`); `None` = Standard.

    Nur für Claude/Codex mit einem Wert aus der Modellliste (`modell_liste`); Hermes und Workflow haben kein wählbares Modell.
    """
    repo = _schreiben_pruefen(snap)
    zeile = _thema_zeile_finden(snap, thema)
    if zeile.worker_wert not in modelle.PROVIDER:
        raise AktionAbgelehnt(f"{thema}: Ausführer {AUSFUEHRER_TEXTE.get(zeile.worker_wert, zeile.worker_wert)} "
                              "hat kein wählbares Modell")
    liste = modell_liste(zeile, snap.kataloge)
    if modell not in [wert for _, wert in liste.eintraege]:
        raise AktionAbgelehnt(f"{thema}: Modell steht nicht im geprüften Katalog – nichts geändert")
    if modell == zeile.modell_wert:
        raise AktionAbgelehnt(f"{thema}: Modell ist schon {liste.aktuell}")
    neu = next(text for text, wert in liste.eintraege if wert == modell)
    frage = (f"Ausführermodell des Themas „{thema}“ von {liste.aktuell} auf {neu} stellen?\n\nGespeichert wird die "
             "Vorgabe für den nächsten bereinigten Coding-Auftrag; es wird keine Sitzung gestartet.")

    def lauf() -> Ergebnis:
        if not schreibbar(repo):
            return Ergebnis(False, NUR_ANZEIGE)
        try:
            profil = modi.modell_setzen(thema, modell, repo=repo)
        except Exception as fehler:  # noqa: BLE001
            return Ergebnis(False, f"{thema}: nicht geändert – {_begrenzt(fehler)}")
        return Ergebnis(True, anzeige.ausfuehrer_meldung(thema, zeile.worker_wert, getattr(profil, "modell", modell)))

    return Aktion("Modell setzen", frage, lauf)


def auto_aktion(snap: Uebersicht, thema: str, an: bool) -> Aktion:
    """Auto-Freigabe des Paares ändern (`paare.aktiv_setzen`) – **nur** die Paarfreigabe.

    Der Hauptschalter Automatik (`automatik_aktion`) bleibt ein eigener Knopf und wird hier nie berührt
    (`anzeige.automatik_setzen` wird nie aufgerufen). Ohne Codex-Paar gibt es nichts zu schalten.
    """
    if not snap.schreiben:
        raise AktionAbgelehnt(NUR_ANZEIGE)
    zeile = _thema_zeile_finden(snap, thema)
    if zeile.paar_aktiv is None:
        raise AktionAbgelehnt(f"{thema}: ohne Codex-Paar – keine Auto-Freigabe möglich")
    if an not in AUTO_WERTE:
        raise AktionAbgelehnt(f"Unbekannte Auto-Freigabe: {an!r}")
    if an == zeile.paar_aktiv:
        raise AktionAbgelehnt(f"{thema}: Auto-Freigabe ist schon {AUTO_TEXTE[an]}")
    if an:
        frage = (f"Auto-Freigabe des Themas „{thema}“ einschalten?\n\nGespeichert wird nur die Freigabe des Paares. Sie "
                 "wirkt erst, wenn der Hauptschalter Automatik an ist und der Master „nach Kontingent“ gilt; der "
                 "Hauptschalter bleibt unverändert.")
    else:
        frage = (f"Auto-Freigabe des Themas „{thema}“ ausschalten?\n\nDie Automatik fasst dieses Thema dann nicht mehr an; "
                 "der Hauptschalter bleibt unverändert.")
    master, schalter = zeile.master_wert, snap.automatik

    def lauf() -> Ergebnis:
        try:
            paare.aktiv_setzen(thema, an)
        except Exception as fehler:  # noqa: BLE001
            return Ergebnis(False, f"{thema}: nicht geändert – {_begrenzt(fehler)}")
        return Ergebnis(True, f"{thema}: Auto-Freigabe {AUTO_TEXTE[an]} gespeichert – "
                              f"{anzeige.auto_zustand(schalter, an, master)[1]}.")

    return Aktion("Auto-Freigabe", frage, lauf)


def _bericht_ergebnis(bericht: alle.Bericht, ueberschrift: str) -> Ergebnis:
    text = ueberschrift + (f" – {bericht.offen} offen" if bericht.offen else "")
    return Ergebnis(bericht.offen == 0, text, "\n".join(bericht.zeilen))


def alle_aktion(snap: Uebersicht, richtung: str) -> Aktion:
    """„Alle nach Kontingent“ (`richtung="kontingent"`) bzw. „Alle wie vorher“ (`"zurueck"`)."""
    repo = _schreiben_pruefen(snap)
    if richtung == "kontingent":
        titel, ueberschrift = "Alle nach Kontingent", "Alle Themen nach Kontingent"
        frage = ("Alle Themen auf „nach Kontingent“ stellen?\n\nFeste Rollen (Claude, Codex) werden vorher "
                 "gemerkt; Hermes-Themen bleiben unberührt.")
        funktion = alle.auf_kontingent
    elif richtung == "zurueck":
        titel, ueberschrift = "Alle wie vorher", "Gemerkte Rollen wiederhergestellt"
        frage = ("Die gemerkten Rollen wiederherstellen?\n\nNur Themen, die noch auf „nach Kontingent“ oder schon "
                 "auf der gemerkten Rolle stehen, werden zurückgestellt.")
        funktion = alle.zurueck
    else:
        raise AktionAbgelehnt(f"Unbekannte Sammelaktion: {richtung!r}")

    def lauf() -> Ergebnis:
        if not schreibbar(repo):
            return Ergebnis(False, NUR_ANZEIGE)
        try:
            bericht = funktion(repo=repo)
        except Exception as fehler:  # noqa: BLE001
            return Ergebnis(False, f"{titel}: nichts geändert – {_begrenzt(fehler)}")
        return _bericht_ergebnis(bericht, ueberschrift)

    return Aktion(titel, frage, lauf)


def automatik_aktion(snap: Uebersicht) -> Aktion:
    """Hauptschalter Automatik umschalten (Datei `einstellungen.json`, kein Repo-Zugriff).

    Ist der Zustand unbekannt (`automatik is None`), wird nichts angeboten: `AktionAbgelehnt`.
    """
    if snap.automatik is None:
        raise AktionAbgelehnt("Automatikzustand unbekannt – erst neu laden.")
    neu = not snap.automatik
    if neu:
        frage = ("Automatik einschalten?\n\nDann dürfen aktive Themen-Paare mit Master „nach Kontingent“ beim "
                 "Limit automatisch übergeben werden.")
    else:
        frage = "Automatik ausschalten?\n\nEs wird dann nichts mehr automatisch übergeben."

    def lauf() -> Ergebnis:
        try:
            anzeige.automatik_setzen(neu)
        except Exception as fehler:  # noqa: BLE001
            return Ergebnis(False, f"Automatik nicht geändert – {_begrenzt(fehler)}")
        return Ergebnis(True, f"Automatik {'an' if neu else 'aus'}.")

    return Aktion("Automatik", frage, lauf)


def entwurf_uebernehmen_aktion(snap: Uebersicht, aenderungen: tuple,
                               nach_thema: Callable[[str], None] | None = None) -> Aktion:
    """Geprüfte Entwurfsänderungen je Thema sicher anwenden."""
    repo = _schreiben_pruefen(snap)
    if not getattr(snap, "wechsel_pruefbar", False):
        raise AktionAbgelehnt("Wechselstatus nicht prüfbar – Übernahme gesperrt")
    if not aenderungen:
        raise AktionAbgelehnt("Keine offenen Entwürfe")
    for a in aenderungen:
        if a.konflikt or a.hinweis:
            raise AktionAbgelehnt(a.hinweis or f"{a.thema}: Konflikt bei {a.feld}")
        if a.thema in getattr(snap, "wechsel_themen", ()):
            raise AktionAbgelehnt(f"Wechsel läuft – Übernahme gesperrt: {a.thema}")
    themen_reihenfolge: list[str] = []
    je_thema: dict[str, dict[str, object]] = {}
    vorschau: list[str] = []
    for a in aenderungen:
        if a.thema not in je_thema:
            themen_reihenfolge.append(a.thema)
            je_thema[a.thema] = {}
        je_thema[a.thema][a.feld] = a.neu
        vorschau.append(f"• {a.thema} · {a.feld}: {a.alt!r} → {a.neu!r}")
    frage = ("Vorgemerkte Änderungen jetzt übernehmen?\n\n"
             + "\n".join(vorschau)
             + "\n\nEs wird keine Sitzung gestartet.")

    def lauf() -> Ergebnis:
        if not schreibbar(repo):
            return Ergebnis(False, NUR_ANZEIGE)
        berichte: list[str] = []
        fehler_anzahl = 0
        for thema in themen_reihenfolge:
            werte = je_thema[thema]
            try:
                if werte.get("arbeitsweise") == arbeitsweise.PROTOKOLL:
                    modi.vibe_setzen(thema, False)
                if "master" in werte:
                    modi.master_setzen(thema, str(werte["master"]), repo=repo)
                if "pruefer" in werte:
                    pruefer_wahl.setzen(thema, str(werte["pruefer"]))
                if "ausfuehrer" in werte:
                    modi.worker_setzen(thema, str(werte["ausfuehrer"]), repo=repo)
                if "modell" in werte:
                    modell_neu = werte["modell"]
                    if "ausfuehrer" not in werte or (modell_neu is not None and modell_neu != modi.HERMES_MODELL):
                        modi.modell_setzen(thema, None if modell_neu is None else str(modell_neu), repo=repo)
                if werte.get("arbeitsweise") == arbeitsweise.VIBE:
                    modi.vibe_setzen(thema, True)
                if "auto" in werte:
                    paare.aktiv_setzen(thema, bool(werte["auto"]))
            except Exception as fehler:  # noqa: BLE001
                fehler_anzahl += 1
                berichte.append(f"{thema}: Fehler – {_begrenzt(fehler)}")
            else:
                berichte.append(f"{thema}: übernommen ({', '.join(werte)})")
                if nach_thema is not None:
                    nach_thema(thema)
        ok = fehler_anzahl == 0
        titel = (f"{len(themen_reihenfolge)} Thema/Themen übernommen."
                 if ok else f"Übernahme mit {fehler_anzahl} Fehler(n).")
        return Ergebnis(ok, titel, "\n".join(berichte))

    return Aktion("Entwürfe übernehmen", frage, lauf)


# --- Fenster als eigener Prozess starten ---------------------------------------------------------------------

def modul_befehl(modul: str) -> list[str]:
    """Befehl, der `master_schalter.<modul>` als eigenen Prozess startet: `pythonw.exe` neben `sys.executable`,
    sonst dieses Python."""
    programm = Path(sys.executable)
    ohne_konsole = programm.with_name("pythonw.exe")
    if ohne_konsole.is_file():
        programm = ohne_konsole
    return [str(programm), "-m", f"master_schalter.{modul}"]


def modul_starten(modul: str) -> None:
    """Fenster-Modul als eigenen Prozess starten (ohne Konsole); eine zweite Instanz beendet sich selbst."""
    paket = str(Path(__file__).resolve().parent.parent)
    umgebung = dict(os.environ)
    umgebung["PYTHONPATH"] = paket + (os.pathsep + umgebung["PYTHONPATH"] if umgebung.get("PYTHONPATH") else "")
    subprocess.Popen(modul_befehl(modul), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, close_fds=True, env=umgebung,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def uebergabe_starten() -> Ergebnis:
    """„Übergabe starten …“: das Wechselfenster (`fenster.py`) öffnen."""
    try:
        modul_starten("fenster")
    except Exception as fehler:  # noqa: BLE001
        return Ergebnis(False, f"Wechselfenster konnte nicht gestartet werden ({type(fehler).__name__})")
    return Ergebnis(True, "Wechselfenster wird geöffnet.")


def thema_anlegen(thema: str, master: str = "kontingent", pruefer: str = "automatisch",
                  worker: str = "workflow", vibe: bool = False, repo: Path | None = None) -> None:
    """Ein neues Thema mit Workflow-Vorgaben sauber anlegen."""
    paare.thema_pruefen(thema)
    paare.setzen(thema, thema, paare.laufend_bilden(thema), aktiv=True)
    modi.master_setzen(thema, master, repo=repo)
    modi.worker_setzen(thema, worker, repo=repo)
    modi.vibe_setzen(thema, vibe, repo=repo)
    pruefer_wahl.setzen(thema, pruefer)
