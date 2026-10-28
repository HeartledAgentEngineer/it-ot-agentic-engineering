"""Datenmodell und Aktionen des Übersichtsfensters (`uebersicht.py`) – ohne Tk, ohne Bildschirm.

`aufnehmen()` liest alle Quellen **nur lesend** (dieselben Bausteine wie `masterwechsel kurz`: Kontingente,
Themenprofile, Besitz, Wartet-worauf, Sitzungen, Messfehler-Status) und liefert eine unveränderliche
Momentaufnahme `Uebersicht`. Die Aktionen (Master je Thema, „Alle nach Kontingent“, „Alle wie vorher“, Automatik,
„Übergabe starten“) sind `Aktion`en mit Rückfragetext und einer Ausführfunktion; das Fenster fragt (`dialog.frage`)
und führt nur bei „Ja“ aus.

**Ein Repo-Ort für Lesen und Schreiben:** `aufnehmen()` bestimmt je Aufnahme genau einmal
`repo = uebergabe.haupt_wurzel(uebergabe.repo_wurzel())` (wie `kurz`), liest damit den Besitz und merkt es in der
Momentaufnahme. Jede Schreibaktion nutzt **genau dieses** `repo` (`modi.master_setzen(..., repo=repo)`,
`alle.auf_kontingent(repo=repo)`, `alle.zurueck(repo=repo)`) – nie ein Aufruf ohne `repo`. Geschrieben wird nur,
wenn `repo/.git` ein **Ordner** ist (echter Hauptarbeitsbaum). Ist das Repo nicht bestimmbar oder ist `.git` eine
Datei (die Auflösung über `commondir` ist gescheitert und hat still die Arbeitskopie geliefert), sind alle
Schreibaktionen gesperrt („Hauptarbeitsbaum nicht gefunden – nur Anzeige“). Die Prüfung läuft bei der Aufnahme und
noch einmal unmittelbar vor dem Schreiben.

Nichts Sensibles in der Anzeige: keine Chat-Titel, keine Codex-Chat-Kennungen, keine Pfade (außer wie in `kurz`).
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone, tzinfo
from pathlib import Path
from typing import Callable

from . import alle, anzeige, kurz, modi, rollen, signale, symbol, wartet
from .signale import Fenster, Kontingent

NUR_ANZEIGE = "Hauptarbeitsbaum nicht gefunden – nur Anzeige"
MASTER_WERTE = tuple(wert for _, wert in anzeige.MASTER_AUSWAHL)   # kontingent, claude, codex, hermes
MASTER_TEXTE = dict(anzeige.ROLLEN_NAMEN)
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
    kontingente = signale.alle_lesen(jetzt=jetzt)
    schwelle = anzeige.schwelle()
    automatik = anzeige.automatik_an()
    claude, codex = kontingente
    lage = rollen.lage(claude, codex, schwelle)
    grund = rollen.lage_grund(claude, codex, schwelle)
    messfehler = signale.messfehler_lesen()
    abos = tuple(_abo(k, farbe, schwelle, messfehler, jetzt, zone)
                 for k, farbe in zip(kontingente, (symbol.CLAUDE, symbol.CODEX)))
    zeilen = tuple(_thema_zeile(t, automatik) for t in sorted(themen, key=lambda t: t.name))
    neueste = sorted(kurz._sitzungen(), key=lambda s: s.zeit, reverse=True)[:kurz.MAX_SITZUNGEN]
    erlaubt = schreibbar(repo)
    return Uebersicht(
        zeit=kurz._uhr(jetzt, jetzt, zone), lage=lage,
        lage_text=f"Lage {lage}" if lage else "Lage ?" + (f" – {grund}" if grund else ""),
        automatik=automatik, schwelle=schwelle, abos=abos, themen=zeilen,
        wartet=tuple(kurz._wartet_zeile(m, jetzt, zone) for m in sorted(wartet.alle_lesen(), key=lambda m: m.zeit)),
        sitzungen=tuple(kurz._sitzung_zeile(s, jetzt, zone) for s in neueste),
        hinweise=tuple(hinweise), repo=repo, schreiben=erlaubt, schreib_hinweis="" if erlaubt else NUR_ANZEIGE)


def _thema_zeile(t: kurz.Thema, automatik: bool) -> ThemaZeile:
    master, besitz_text, pruefer, ausfuehrer, auto = kurz.thema_felder(t, automatik)
    return ThemaZeile(t.name, master, besitz_text.removeprefix("Besitz "), pruefer.removeprefix("Prüfer "),
                      ausfuehrer, auto, t.profil.master)


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
