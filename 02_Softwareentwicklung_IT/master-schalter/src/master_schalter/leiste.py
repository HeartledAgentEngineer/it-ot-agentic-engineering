"""Taskleisten-Symbol: zeigt Lage und die Kontingente von Claude Code und Codex.

* Mauszeiger darüber: kurze Zeile „Lage 1 · Claude 62 % · Codex 1 % verbraucht" (5-Stunden-Fenster).
* Linksklick (Menüeintrag „Übersicht …" mit `default=True`): öffnet das Übersichtsfenster
  (`uebersicht.py`) als eigenen Prozess; eine zweite Instanz beendet sich still.
* Rechtsklick: Menü nach Plan E9. Oben die Stand-Zeilen (Themenzahl je Masterart, Lage, Kontingente),
  „Übersicht …", „Übergabe starten …"
  (öffnet das Wechselfenster als eigenen Prozess), je offenem Wechsel eine deaktivierte Zeile „Wechsel
  <thema>: <Phase>", „Aktualisieren" (misst frisch und hakt offene Übergaben ab), „Einstellungen ▸" und „Beenden".
  Unter „Einstellungen": „Wechsel-Schwelle", „Modelle aktualisieren" (mit Katalogzeilen), „Automatik je Thema"
  (früher „Chats übergeben"), „Automatik-Weg" (alter Weg oder Wechselassistent, Standard alt), „Arbeitsmodus je Thema" (je Thema Master, Ausführer, Ausführermodell) und
  „Standard-Master (übrige Themen)" (früher „Master wechseln"; Bestätigungsdialog, Ziel Codex stößt die
  Rückgabe an die Codex-Chats an).
* Das Symbol zeigt nur die beiden 5-Stunden-Balken; einen globalen Master zeigt es nicht mehr an.

Menü und checked/label-Rückrufe arbeiten ausschließlich aus unveränderlichen Momentaufnahmen
(`aktualisieren()`); im Menüklick- oder checked-Faden findet nie eine Datei-, Prozess- oder
Netzabfrage statt (auch der Fensterstart läuft in einem eigenen Faden). Rollenänderungen laufen im
Hintergrund mit nichtblockierender Themensperre; der Modellkatalog wird im Hintergrund mit
Single-Flight-Riegel abgeglichen.

**Codex-Messung:** Codex-Sitzungsdateien sind nur frisch, solange Codex arbeitet. Deshalb misst der Takt Codex
aktiv (`codex_messen`, kein Tokenverbrauch) – höchstens alle `CODEX_TAKT_SEKUNDEN` (300 s) – und zusätzlich vor
der Automatikprüfung, wenn die frische Claude-Messung die Schwelle erreicht und der Codex-Stand älter als
`CODEX_VOR_ALTER_SEKUNDEN` (120 s) ist. Das läuft im Messfaden (nie im Menü-/Klickfaden); Fehler erscheinen nur
mit ihrer Fehlerklasse im Log.

**Takt des Wechselassistenten:** ein eigener leichter Faden (`ASSISTENT_TAKT_SEKUNDEN` = 10 s), unabhängig vom
60-s-Messtakt, ruft für jeden nicht endgültigen Vorgang `assistent.fortsetzen(id)`. Ein Fehler wird nur mit
seiner Klasse protokolliert und beendet nichts. Danach wird das Menü neu gebaut, wenn sich eine Phase geändert
hat, und es erscheinen Windows-Hinweise – je Vorgang und Ereignis genau einmal (Merker nur im Speicher; ältere
Vorgänge als `fenster_modell.HINWEIS_ALTER` melden nichts). Beim Start ordnet `wiederaufnehmen()` Absturzreste einmal ein
(Ergebnis nur als Zähler im Log).

Start ohne Konsolenfenster: `.venv\\Scripts\\pythonw.exe -m master_schalter.leiste`
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import pystray

from . import (anzeige, assistent, assistent_vorgaenge, automatik, claude_anmeldung, claude_messen, codex_messen, dialog, fenster_modell, modi,
               modelle, paare, rollen, rueckgabe, signale, symbol, uebergabe, uebersicht_modell, vorgaenge, wechsel,
               zustand)


TAKT_SEKUNDEN = 60
ASSISTENT_TAKT_SEKUNDEN = 10   # Wechselassistent: fortsetzen für jeden offenen Vorgang
MODELLE_TAKT_SEKUNDEN = 1800   # automatischer Katalogabgleich höchstens alle 30 Minuten
CODEX_TAKT_SEKUNDEN = 300      # aktive Codex-Messung (`codex_messen`) im Messtakt höchstens alle 5 Minuten
CODEX_VOR_ALTER_SEKUNDEN = 120  # vor der Automatik: Codex-Stand älter als das → vorher frisch messen
FENSTER_NAMEN = {"fenster": "Wechselfenster", "uebersicht": "Übersicht"}
HAUPTSCHALTER_AN = "Hauptschalter Automatik: an"
HAUPTSCHALTER_AUS = "Hauptschalter Automatik: aus – einschalten in der Übersicht …"
# Ein Hinweis zu einem höheren Ereignis macht die niedrigeren desselben Vorgangs überflüssig.
HINWEIS_VERDRAENGT = {"uebernommen": ("rolle",)}


def _protokoll(text: str) -> None:
    """Messfehler mit Zeitstempel ins Protokoll (stderr → `leiste.log` des Starters)."""
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {text}", file=sys.stderr, flush=True)


def fenster_befehl(modul: str = "fenster") -> list[str]:
    """Befehl, der ein Fenster (`fenster` = Wechselfenster, `uebersicht`) als eigenen Prozess startet."""
    return uebersicht_modell.modul_befehl(modul)


class Leiste:
    def __init__(self) -> None:
        self._kontingente: list[signale.Kontingent] = []
        self._zustand = zustand.Zustand()
        self._paare_snapshot: list[paare.Paar] = []
        self._vorgaenge_snapshot: list[vorgaenge.Vorgang] = []
        self._wechsel_snapshot: list[assistent_vorgaenge.Vorgang] = []   # Vorgänge des Wechselassistenten
        self._modus_snapshot: dict[str, tuple[str, str, bool]] = {}
        self._rollen_snapshot: dict[str, anzeige.Rollenstand] = {}
        self._kataloge: tuple[anzeige.Katalogstand, ...] | None = None
        self._modus_fehler: str | None = None
        self._themen_master: list[str] = []   # Masterrolle je Thema (Momentaufnahme für die Menükopfzeile)
        self._automatik_weg = anzeige.STANDARD_WEG   # Momentaufnahme für Haken und Menüzeilen
        self._automatik_global = False   # Momentaufnahme des Hauptschalters (einstellungen.json, Feld `automatik`)
        self._automatik_fehler: str | None = None   # „Automatik nicht geändert (<Klasse>)“ bis zur nächsten Aktualisierung
        self._lage: str | None = None
        self._grund = ""
        self._stopp = threading.Event()
        self._messung_angefordert = threading.Event()
        self._messung_sperre = threading.Lock()
        self._messung_fehler: str | None = None
        self._429_aktiv = False
        self._messung_intervall = anzeige.claude_takt_min() * 60
        self._anmeldung_sperre = threading.Lock()
        self._anmeldung_aktiv = False
        self._anmeldung_prozess = None
        self._codex_sperre = threading.Lock()
        self._codex_letzte: float | None = None   # monotone Zeit des letzten Codex-Messversuchs
        self._arbeits_thread = None
        self._assistent_thread = None
        self._assistent_sperre = threading.Lock()
        self._hinweis_gemeldet: set[tuple[str, str]] = set()   # (Vorgang, Ereignis) – nur im Speicher
        self._automatik_sperre = threading.Lock()
        self._automatik_staende: list[automatik.Stand] = []
        self._bestaetigung_sperre = threading.Lock()
        self._wechsel_sperre = threading.Lock()
        self._modelle_sperre = threading.Lock()
        self._modellversuch: float | None = None   # monotone Zeit des letzten Katalogabgleichs
        self._dialog = dialog.frage
        self.icon = pystray.Icon("master-schalter", symbol.bild(None, None, anzeige.STANDARD_SCHWELLE),
                                 "Master-Schalter", menu=pystray.Menu(self._menue))

    # --- Menü ---------------------------------------------------------------

    def _menue(self):
        geschuetzt = [t for t, (_, _, sicher) in self._modus_snapshot.items() if sicher]
        yield pystray.MenuItem(anzeige.themen_zeile(self._themen_master), None, enabled=False)
        if geschuetzt:
            yield pystray.MenuItem(anzeige.feste_themen_zeile(geschuetzt), None, enabled=False)
        if self._modus_fehler:
            yield pystray.MenuItem(f"Arbeitsmodus: {self._modus_fehler}", None, enabled=False)
        for zeile in anzeige.lage_zeilen(self._lage, self._grund):
            yield pystray.MenuItem(zeile, None, enabled=False)
        yield self._hauptschalter_eintrag()
        if self._automatik_fehler:
            yield pystray.MenuItem(self._automatik_fehler, None, enabled=False)
        yield pystray.Menu.SEPARATOR
        for zeile in anzeige.details(self._kontingente, max_alter=timedelta(minutes=10)):
            yield pystray.MenuItem(zeile, None, enabled=False)
        if self._messung_fehler:
            yield pystray.MenuItem(f"Claude-Messung: {self._messung_fehler}", None, enabled=False)
        for zeile in self._automatik_staende_zeilen():
            yield pystray.MenuItem(zeile, None, enabled=False)
        yield pystray.Menu.SEPARATOR
        yield pystray.MenuItem("Übersicht …", self._uebersicht_aktion, default=True)   # Linksklick
        yield pystray.MenuItem("Anmelden bei Claude …", self._claude_anmelden_aktion)
        yield pystray.MenuItem("Übergabe starten …", self._fenster_aktion)
        for zeile in self._wechsel_zeilen():
            yield pystray.MenuItem(zeile, None, enabled=False)
        yield pystray.Menu.SEPARATOR
        yield pystray.MenuItem("Aktualisieren", self._aktualisieren_aktion)
        yield pystray.MenuItem("Einstellungen ▸", pystray.Menu(*self._einstellungen_optionen()))
        yield pystray.MenuItem("Beenden", self._beenden)

    def _hauptschalter_eintrag(self):
        """Hauptschalter Automatik oben im Menü (Momentaufnahme): „an“ mit Haken, „aus“ ohne Haken und mit Hinweis."""
        an = self._automatik_global
        text = HAUPTSCHALTER_AN if an else HAUPTSCHALTER_AUS
        return pystray.MenuItem(text, self._hauptschalter_aktion, checked=lambda item, an=an: an)

    def _hauptschalter_aktion(self, *_args) -> None:
        """Asymmetrisch sicher: bei „an“ schaltet der Klick sofort **aus** (sichere Richtung); bei „aus“ schaltet er
        nie direkt ein, sondern öffnet die Übersicht (dort Ja/Nein-Rückfrage, Standard Nein).

        Maßgeblich ist der frisch gelesene Zustand, nicht die Momentaufnahme des Menüs. Ein Schreibfehler wird zur
        Menüzeile „Automatik nicht geändert (<Klasse>)“ (nur die Fehlerklasse), nie zum Absturz.
        """
        try:
            an = anzeige.automatik_an()
        except Exception:  # noqa: BLE001 - nicht lesbar heißt wie sonst auch: aus
            an = False
        if not an:
            self._uebersicht_aktion()
            return
        fehler = None
        try:
            anzeige.automatik_setzen(False)
        except Exception as ausnahme:  # noqa: BLE001 - Schreibfehler dürfen die Leiste nicht beenden
            fehler = f"Automatik nicht geändert ({type(ausnahme).__name__})"
            _protokoll(fehler)
        self.aktualisieren()
        if fehler:
            self._automatik_fehler = fehler
            try:
                self.icon.update_menu()
            except Exception:  # noqa: BLE001
                pass

    def _einstellungen_optionen(self):
        """Untermenü „Einstellungen": alle bisherigen Einstellpunkte, in ihrem Verhalten unverändert."""
        optionen = [pystray.MenuItem("Wechsel-Schwelle", pystray.Menu(*self._schwellen_optionen()))]
        for zeile in anzeige.katalog_zeilen(self._kataloge or ()):
            optionen.append(pystray.MenuItem(zeile, None, enabled=False))
        optionen.append(pystray.MenuItem(anzeige.MODELLE_AKTUALISIEREN, self._modelle_aktualisieren_aktion))
        optionen.append(pystray.MenuItem("Automatik je Thema", pystray.Menu(*self._paar_optionen())))
        optionen.append(pystray.MenuItem("Automatik-Weg", pystray.Menu(*self._weg_optionen())))
        optionen.append(pystray.MenuItem("Arbeitsmodus je Thema", pystray.Menu(*self._modus_themen_optionen())))
        optionen.append(pystray.MenuItem("Standard-Master (übrige Themen)", pystray.Menu(*self._master_optionen())))
        return optionen

    def _wechsel_zeilen(self) -> list[str]:
        """Eine Zeile je offenem Wechsel – aus der Momentaufnahme, ohne Dateizugriff."""
        return [f"Wechsel {v.thema}: {fenster_modell.phase_kurz(v.phase)}"
                for v in self._wechsel_snapshot if fenster_modell.offen(v)]

    # --- Wechselfenster -------------------------------------------------------------

    def _fenster_aktion(self, *_args) -> None:
        """Menüklick: das Fenster in einem eigenen Faden starten (kein Prozessstart im Klickfaden)."""
        threading.Thread(target=self._fenster_oeffnen, daemon=True).start()

    def _uebersicht_aktion(self, *_args) -> None:
        """Linksklick bzw. Menüpunkt „Übersicht …“: das Übersichtsfenster in einem eigenen Faden starten."""
        threading.Thread(target=self._fenster_oeffnen, args=("uebersicht",), daemon=True).start()

    def _fenster_oeffnen(self, modul: str = "fenster") -> None:
        """Fenster als eigener Prozess; eine zweite Instanz beendet sich selbst (Sperre `<modul>.lock`)."""
        name = FENSTER_NAMEN.get(modul, modul)
        try:
            uebersicht_modell.modul_starten(modul)
        except Exception as fehler:  # noqa: BLE001 - ein Startfehler darf die Leiste nicht beenden
            _protokoll(f"{name} konnte nicht gestartet werden ({type(fehler).__name__})")
            self._melden(f"{name} konnte nicht gestartet werden")

    def _melden(self, text: str) -> None:
        try:
            self.icon.notify(text[:anzeige.HINWEIS_MAX], "Master-Schalter")
        except Exception:  # noqa: BLE001 - Meldefehler dürfen nichts umwerfen
            _protokoll("Hinweis konnte nicht angezeigt werden")

    def _paar_optionen(self):
        liste = self._paare_snapshot
        vorgangsliste = self._vorgaenge_snapshot
        if not liste:
            return [pystray.MenuItem("keine Paare angelegt", None, enabled=False)]
        return [pystray.MenuItem(f"{p.thema}: {automatik.status_zeile(p, vorgangsliste, weg=self._automatik_weg)}",
                                 self._paar_umschalten_aktion(p.thema), checked=lambda item, p=p: self._ist_paar_an(p.thema))
                for p in liste]

    def _weg_optionen(self):
        """Zwei Auswahlpunkte (Radio) aus der Momentaufnahme; gewechselt wird nur per Klick."""
        return [pystray.MenuItem(text, self._weg_aktion(wert),
                                 checked=lambda item, wert=wert: self._automatik_weg == wert, radio=True)
                for text, wert in anzeige.WEG_AUSWAHL]

    def _weg_aktion(self, wert: str):
        def aktion(*_args) -> None:
            try:
                anzeige.automatik_weg_setzen(wert)
            except (OSError, ValueError) as fehler:
                self.icon.notify(f"Automatik-Weg nicht gespeichert ({type(fehler).__name__})", "Master-Schalter")
            self.aktualisieren()
        return aktion

    def _automatik_staende_zeilen(self) -> list[str]:
        return [s.status if not s.thema else f"{s.thema}: {s.status}" for s in self._automatik_staende]

    def _ist_paar_an(self, thema: str):
        return any(p.thema == thema and p.aktiv for p in self._paare_snapshot)

    def _paar_umschalten_aktion(self, thema: str):
        def aktion() -> None:
            try:
                paare.aktiv_setzen(thema, not self._ist_paar_an(thema))
            except paare.PaarFehler as fehler:
                self.icon.notify(f"Paar nicht geändert: {fehler}"[:anzeige.HINWEIS_MAX], "Master-Schalter")
            self.aktualisieren()

        return aktion

    def _modus_themen_optionen(self):
        if self._modus_fehler:
            return [pystray.MenuItem("Modusdaten nicht lesbar", None, enabled=False)]
        if not self._paare_snapshot:
            return [pystray.MenuItem("keine Themenpaare angelegt", None, enabled=False)]
        return [pystray.MenuItem(p.thema, pystray.Menu(*self._thema_optionen(p.thema)))
                for p in self._paare_snapshot]

    def _thema_optionen(self, thema: str):
        """Drei getrennte Rollengruppen je Thema – ausschließlich aus der Momentaufnahme."""
        stand = self._rollen_snapshot.get(thema, anzeige.Rollenstand())
        return [
            pystray.MenuItem("Master", pystray.Menu(
                *self._eintrag_items(thema, anzeige.master_eintraege(stand), self._master_aktion))),
            pystray.MenuItem("Ausführer", pystray.Menu(
                *self._eintrag_items(thema, anzeige.worker_eintraege(stand), self._worker_aktion))),
            pystray.MenuItem("Ausführermodell", pystray.Menu(
                *self._eintrag_items(thema, anzeige.modell_eintraege(stand), self._modell_aktion))),
        ]

    @staticmethod
    def _eintrag_items(thema: str, eintraege: list[anzeige.Eintrag], bauer) -> list:
        """Menüeinträge aus der Momentaufnahme bauen – keine Datei-/Prozess-/Netzabfrage."""
        items = []
        for eintrag in eintraege:
            if eintrag.hinweis:
                items.append(pystray.MenuItem(eintrag.text, None, enabled=False))
                continue
            checked = lambda item, haken=eintrag.haken: haken
            if not eintrag.aktiv:
                items.append(pystray.MenuItem(eintrag.text, None, checked=checked,
                                              enabled=False, radio=True))
                continue
            items.append(pystray.MenuItem(eintrag.text, bauer(thema, eintrag.wert),
                                          checked=checked, radio=True))
        return items

    def _master_aktion(self, thema: str, master: str):
        def arbeit() -> str:
            modi.master_setzen(thema, master)
            return anzeige.master_meldung(thema, master)

        def aktion(*_args) -> None:
            self._modus_hintergrund(thema, arbeit)
        return aktion

    def _worker_aktion(self, thema: str, worker: str):
        def arbeit() -> str:
            profil = modi.worker_setzen(thema, worker)
            return anzeige.ausfuehrer_meldung(thema, worker, profil.modell)

        def aktion(*_args) -> None:
            self._modus_hintergrund(thema, arbeit)
        return aktion

    def _modell_aktion(self, thema: str, modell: str | None):
        def arbeit() -> str:
            profil = modi.modell_setzen(thema, modell)
            return anzeige.modell_meldung(thema, profil.modell)

        def aktion(*_args) -> None:
            self._modus_hintergrund(thema, arbeit)
        return aktion

    def _modus_hintergrund(self, thema: str, arbeit: Callable[[], str]) -> None:
        """Rollenänderung im eigenen Faden; belegte Themensperre wird ohne Warten gemeldet."""
        def lauf() -> None:
            try:
                with zustand.thema_sperre(thema, blockierend=False, frist=0) as frei:
                    if not frei:
                        self.icon.notify("Übergabe läuft – Modus gleich erneut wählen", "Master-Schalter")
                        return
                meldung = arbeit()
                self.aktualisieren()
                self.icon.notify(meldung[:anzeige.HINWEIS_MAX], "Master-Schalter")
            except Exception as fehler:  # noqa: BLE001 - Klick-/Aktualisierungsfehler dürfen die Leiste nicht beenden
                text = ("Übergabe läuft – Modus gleich erneut wählen"
                        if str(fehler).startswith("Übergabe läuft") else f"Modus nicht geändert: {fehler}")
                try:
                    self.icon.notify(text[:anzeige.HINWEIS_MAX], "Master-Schalter")
                except Exception:
                    _protokoll("Rollenwahl konnte nicht gemeldet werden")

        threading.Thread(target=lauf, daemon=True).start()

    def _bestaetigung_anfordern(self) -> None:
        """Offene Übergaben abhaken – eigener Faden und eigener Riegel (kein Senden)."""
        if not self._bestaetigung_sperre.acquire(blocking=False):
            return

        def abhaken() -> None:
            try:
                staende = automatik.bestaetigungen_pruefen()
                if staende:
                    self._automatik_staende = staende
            except Exception:  # noqa: BLE001 - das Abhaken darf nie etwas umwerfen
                pass
            finally:
                self._bestaetigung_sperre.release()
            try:
                self.aktualisieren()
            except Exception:  # noqa: BLE001
                pass

        threading.Thread(target=abhaken, daemon=True).start()

    # --- Automatik ----------------------------------------------------------

    def _automatik_anfordern(self) -> None:
        """Prüfung in eigenem Faden starten (die 30-Sekunden-Wartezeit darf den Takt nicht blockieren)."""
        if not anzeige.automatik_an():
            return
        threading.Thread(target=self._automatik_ausfuehren, daemon=True).start()

    def _automatik_ausfuehren(self) -> None:
        if not self._automatik_sperre.acquire(blocking=False):
            return
        try:
            try:
                self._automatik_staende = automatik.lauf()
                self._automatik_staende += automatik.bestaetigungen_pruefen()
            except Exception:  # noqa: BLE001 - die Leiste darf nie wegen eines Laufs abstürzen
                self._automatik_staende = [automatik.Stand("", "Automatikprüfung fehlgeschlagen")]
        finally:
            self._automatik_sperre.release()
        try:
            self.aktualisieren()
        except Exception:  # noqa: BLE001
            pass

    def _master_optionen(self):
        return [pystray.MenuItem(anzeige.MASTER_NAMEN[m], self._wechsel_aktion(m),
                                 checked=self._ist_master(m), radio=True) for m in zustand.MASTER]

    def _schwellen_optionen(self):
        return [pystray.MenuItem(f"{s} %", self._schwellen_aktion(s), checked=self._ist_schwelle(s), radio=True)
                for s in anzeige.SCHWELLEN]

    def _ist_master(self, master: str):
        return lambda item: self._zustand.master == master

    def _ist_schwelle(self, wert: int):
        return lambda item: anzeige.schwelle() == wert

    def _wechsel_aktion(self, master: str):
        def aktion() -> None:
            if not self._wechsel_sperre.acquire(blocking=False):
                return
            try:
                threading.Thread(target=self._wechsel_gesperrt, args=(master,), daemon=True).start()
            except Exception as fehler:  # noqa: BLE001 - auch Konstruktion und Start freigebbar halten
                self._wechsel_sperre.release()
                self._wechsel_melden(f"Wechsel konnte nicht gestartet werden: {fehler}"[:anzeige.HINWEIS_MAX])
        return aktion

    def _schwellen_aktion(self, wert: int):
        def aktion() -> None:
            self._schwelle_setzen(wert)
        return aktion

    # --- Aktionen -----------------------------------------------------------

    def _wechsel_text(self, master: str) -> str:
        name = anzeige.MASTER_NAMEN.get(master, master)
        if master == "codex":
            geschuetzt = [p.thema for p in self._paare_snapshot if p.aktiv and
                          self._modus_snapshot.get(p.thema, (None, None, True))[2]]
            uebergebbar = [p for p in self._paare_snapshot if p.aktiv and
                           not self._modus_snapshot.get(p.thema, (None, None, True))[2]]
            zeilen = [f"\u2022 {p.thema}: {self._kopfzeilen_zustand(p)}" for p in uebergebbar]
            liste = "\n".join(zeilen) if zeilen else "keine übergebbaren Themen"
            ausnahme = ("\nGeschützte Themen (Hermes/Antigravity) bleiben unberührt: " + ", ".join(geschuetzt)
                        if geschuetzt else "")
            return ("Wirklich den Standard-Master für übrige Themen an Codex übergeben?\n\n"
                    "Nur diese aktiven, übergebbaren Themen erhalten eine Nachricht:\n"
                    f"{liste}\n\n"
                    f"{ausnahme}\n"
                    "Ist Codex bereits Standard-Master, wird kein neues Übergabepaket erstellt.\n"
                    "Die tatsächliche Zustellung braucht weiterhin ein echtes ACK.")
        return f"Wirklich Master an {name} umstellen?"

    @staticmethod
    def _kopfzeilen_zustand(paar: paare.Paar) -> str:
        """Zustand der laufenden Übergabe für den Dialog (nur lesend, wie `uebergabepunkt`)."""
        try:
            repo = uebergabe.repo_wurzel()
        except uebergabe.UebergabeFehler:
            return "Zustand unbekannt"
        pfad = repo / paar.laufend
        kopf = automatik.kopfzeile_lesen(pfad)
        if kopf is None:
            return "Kopfzeile fehlt/ungültig"
        if kopf[0] != "ja":
            return "steht auf nein"
        bereit, status = automatik.uebergabepunkt(
            pfad, automatik.kopf_hash(repo), datetime.now(timezone.utc))
        if bereit:
            return "bereit"
        if status == automatik.STATUS_UEBERGABEPUNKT:
            return "steht auf nein"
        return "Stand veraltet – wird beim Senden gezogen"

    def _wechseln(self, master: str) -> None:
        if not self._wechsel_sperre.acquire(blocking=False):
            return
        self._wechsel_gesperrt(master)

    def _wechsel_gesperrt(self, master: str) -> None:
        try:
            try:
                bestaetigt = self._dialog("Master-Schalter", self._wechsel_text(master))
            except Exception as fehler:  # noqa: BLE001 - Dialogfehler sichtbar machen und geschlossen bleiben
                self._wechsel_melden(f"Bestätigung fehlgeschlagen: {fehler}"[:anzeige.HINWEIS_MAX])
                return
            if not bestaetigt:
                return
            ergebnis = None
            try:
                ergebnis = wechsel.wechseln(master)
                text = anzeige.wechsel_hinweis(ergebnis)
            except Exception as fehler:  # noqa: BLE001 - die Leiste darf nie wegen eines Klicks abstürzen
                text = f"Wechsel fehlgeschlagen: {fehler}"[:anzeige.HINWEIS_MAX]
            self.aktualisieren()
            self._wechsel_melden(text, "Master-Schalter")
            if ergebnis is not None and ergebnis.art == "gewechselt" and master == "codex":
                threading.Thread(target=self._rueckgabe_ausfuehren, daemon=True).start()
        finally:
            self._wechsel_sperre.release()

    def _wechsel_melden(self, text: str, titel: str = "Master-Schalter") -> None:
        try:
            self.icon.notify(text, titel)
        except Exception:  # noqa: BLE001 - Meldefehler dürfen die Sperrfreigabe nicht verhindern
            _protokoll("Wechselmeldung konnte nicht angezeigt werden")

    def _rueckgabe_ausfuehren(self) -> None:
        try:
            staende = rueckgabe.rueckgabe()
        except Exception as fehler:  # noqa: BLE001
            staende = [automatik.Stand("", f"Rückgabe fehlgeschlagen: {fehler}"[:anzeige.HINWEIS_MAX])]
        if staende:
            self._automatik_staende = staende

    def _schwelle_setzen(self, wert: int) -> None:
        try:
            anzeige.schwelle_setzen(wert)
        except (OSError, ValueError) as fehler:
            self.icon.notify(f"Schwelle nicht gespeichert: {fehler}"[:anzeige.HINWEIS_MAX], "Master-Schalter")
        self.aktualisieren()

    def aktualisieren(self) -> None:
        try:
            self._paare_snapshot = paare.lesen()
            self._vorgaenge_snapshot = vorgaenge.lesen()
            self._wechsel_snapshot = assistent_vorgaenge.lesen()
            self._kataloge = self._kataloge_lesen()
            self._automatik_weg = anzeige.automatik_weg()
            self._automatik_global = anzeige.automatik_an()
            self._automatik_fehler = None
            try:
                self._modus_snapshot = modi.snapshot([p.thema for p in self._paare_snapshot])
                profile = modi.lesen()
                self._rollen_snapshot = {}
                for p in self._paare_snapshot:
                    wert = profile.get(p.thema, modi.Profil())
                    self._rollen_snapshot[p.thema] = anzeige.Rollenstand(
                        wert.master, wert.worker, wert.modell, self._kataloge or ())
                self._themen_master = [profile.get(name, modi.Profil()).master
                                       for name in sorted(set(profile) | {p.thema for p in self._paare_snapshot})]
                self._modus_fehler = None
            except (modi.ModusFehler, OSError) as fehler:
                self._modus_snapshot = {}
                self._rollen_snapshot = {}
                self._themen_master = []
                self._modus_fehler = f"nicht verfügbar: {fehler}"
            self._kontingente = signale.alle_lesen()
            self._zustand = zustand.lesen()
            schwelle = anzeige.schwelle()
            claude, codex = self._kontingente
            self._lage = rollen.lage(claude, codex, schwelle)
            self._grund = rollen.lage_grund(claude, codex, schwelle)
            fuenf = [(k.fenster_nach_name("5h")) for k in self._kontingente]
            self.icon.icon = symbol.bild(fuenf[0].prozent if fuenf[0] else None,
                                         fuenf[1].prozent if fuenf[1] else None, schwelle)
            self.icon.title = anzeige.tooltip_symbol(self._lage, self._kontingente)
            self.icon.update_menu()
        except Exception as fehler:  # noqa: BLE001 - Aktualisierung darf die Leiste nicht beenden
            _protokoll(f"Aktualisierung fehlgeschlagen: {fehler}")

    @staticmethod
    def _kataloge_lesen() -> tuple[anzeige.Katalogstand, ...]:
        """Katalogstände aus dem lokalen Metadatencache – nur lesen, nie abfragen."""
        kataloge = []
        for provider in modelle.PROVIDER:
            try:
                katalog = modelle.lesen(provider)
                kataloge.append(anzeige.Katalogstand(
                    katalog.provider, tuple((m.id, m.name) for m in katalog.modelle),
                    katalog.zeit.isoformat() if katalog.zeit else None,
                    katalog.fehler, katalog.veraltet))
            except Exception as fehler:  # noqa: BLE001 - ein kaputter Katalog blockiert nichts
                _protokoll(f"Modellkatalog {provider} nicht lesbar: {fehler}")
                kataloge.append(anzeige.Katalogstand(provider, (), None, modelle.KEINE_DATEN, True))
        return tuple(kataloge)

    def _modellabgleich_pruefen(self) -> None:
        """Automatischer Hintergrundabgleich, wenn die Momentaufnahme einen veralteten Katalog nennt."""
        kataloge = self._kataloge
        if kataloge is None or not any(k.veraltet for k in kataloge):
            return
        self._modelle_anfordern()

    def _modelle_anfordern(self, *, erzwungen: bool = False) -> None:
        """Hintergrundabgleich anfordern – gedrosselt; der Klickfaden wird nie blockiert."""
        jetzt = time.monotonic()
        if not erzwungen and self._modellversuch is not None and \
                jetzt - self._modellversuch < MODELLE_TAKT_SEKUNDEN:
            return
        self._modellversuch = jetzt
        threading.Thread(target=self._modelle_aktualisieren, daemon=True).start()

    def _modelle_aktualisieren(self) -> None:
        """Beide Kataloge einmalig abgleichen; läuft nie parallel (Single-Flight-Riegel)."""
        if not self._modelle_sperre.acquire(blocking=False):
            return
        try:
            modelle.alle_aktualisieren()
        except Exception as fehler:  # noqa: BLE001 - ein Abgleichfehler darf die Leiste nicht umwerfen
            _protokoll(f"Modellkatalog-Abgleich fehlgeschlagen: {fehler}")
        finally:
            self._modelle_sperre.release()
        try:
            self.aktualisieren()
        except Exception:  # noqa: BLE001
            pass

    def _modelle_aktualisieren_aktion(self, *_args) -> None:
        self._modelle_anfordern(erzwungen=True)

    def _aktualisieren_aktion(self) -> None:
        self.aktualisieren()
        self._messung_angefordert.set()
        self._bestaetigung_anfordern()

    def _claude_anmelden_aktion(self, *_args) -> None:
        """Menüklick: höchstens einen sichtbaren Loginprozess im Hintergrund starten."""
        with self._anmeldung_sperre:
            prozess = self._anmeldung_prozess
            if prozess is not None:
                try:
                    if prozess.poll() is None:
                        prozess_laeuft = True
                    else:
                        self._anmeldung_prozess = None
                        prozess_laeuft = False
                except Exception:
                    prozess_laeuft = True
            else:
                prozess_laeuft = False
            if self._anmeldung_aktiv or prozess_laeuft:
                bereits = True
            else:
                bereits = False
                self._anmeldung_aktiv = True
        if bereits:
            self._melden("Claude-Anmeldung läuft bereits")
            return
        try:
            threading.Thread(target=self._claude_anmelden, daemon=True).start()
        except Exception as fehler:  # noqa: BLE001 - Freigabe auch bei Threadstartfehler
            with self._anmeldung_sperre:
                self._anmeldung_aktiv = False
            _protokoll(f"Claude-Anmeldung konnte nicht gestartet werden ({type(fehler).__name__})")
            self._melden("Claude-Anmeldung konnte nicht gestartet werden")

    def _claude_anmelden(self) -> None:
        """Startet und wartet ausschließlich auf den eigenen interaktiven Loginprozess."""
        prozess = None
        try:
            prozess = claude_anmeldung.login_starten()
            with self._anmeldung_sperre:
                self._anmeldung_prozess = prozess
            self._melden("Claude-Anmeldung geöffnet – bitte im Browser abschließen.")
            try:
                code = prozess.wait(timeout=600)
            except subprocess.TimeoutExpired:
                try:
                    claude_anmeldung.prozessbaum_beenden(prozess)
                except Exception as fehler:  # noqa: BLE001 - Prozessreferenz bleibt als Startriegel
                    _protokoll(f"Claude-Anmeldung konnte nicht beendet werden ({type(fehler).__name__})")
                    self._melden("Claude-Anmeldung Zeitlimit erreicht; Prozess läuft noch")
                else:
                    self._melden("Claude-Anmeldung nach zehn Minuten beendet")
                return
            if code == 0:
                self._429_aktiv = False
                self._messung_intervall = anzeige.claude_takt_min() * 60
                self._messung_angefordert.set()
                self._melden("Claude-Login beendet; neue Messung angefordert")
            else:
                self._melden("Claude-Anmeldung abgebrochen")
        except claude_anmeldung.Anmeldefehler as fehler:
            self._melden(str(fehler))
        except Exception as fehler:  # noqa: BLE001 - keine CLI-Ausgaben oder Details protokollieren
            _protokoll(f"Claude-Anmeldung fehlgeschlagen ({type(fehler).__name__})")
            self._melden(f"Claude-Anmeldung fehlgeschlagen ({type(fehler).__name__})")
        finally:
            with self._anmeldung_sperre:
                self._anmeldung_aktiv = False
                if prozess is not None:
                    try:
                        if prozess.poll() is not None:
                            self._anmeldung_prozess = None
                    except Exception:
                        pass  # Unklarer Prozesszustand sperrt vorsichtshalber einen zweiten Login.

    def _takt(self) -> None:
        letzte_messung = time.monotonic()
        while not self._stopp.is_set():
            angefordert = self._messung_angefordert.wait(TAKT_SEKUNDEN)
            if self._stopp.is_set():
                break
            if angefordert:
                self._messung_angefordert.clear()
            self._codex_takt_pruefen()
            self.aktualisieren()
            intervall_abgelaufen = time.monotonic() - letzte_messung >= self._messung_intervall
            if (angefordert and not self._429_aktiv) or intervall_abgelaufen:
                self._messung_ausfuehren()
                letzte_messung = time.monotonic()
                self.aktualisieren()
                if anzeige.automatik_an():
                    if self._messung_fehler is None:
                        self._codex_vor_automatik()   # Codex ggf. frisch messen, bevor die Automatik ihn liest
                    self._automatik_anfordern()   # eigene Frischegates prüfen auch native Statusline-Werte
                elif self._messung_fehler is None:
                    self._bestaetigung_anfordern()   # offene Übergaben nach erfolgreicher Messung abhaken
            self._modellabgleich_pruefen()   # abgelaufener Modellkatalog wird im Hintergrund erneuert

    # --- Aktive Codex-Messung -----------------------------------------------------------

    def _codex_takt_pruefen(self) -> None:
        """Im Messtakt: Codex höchstens alle `CODEX_TAKT_SEKUNDEN` messen. Wirft nie."""
        letzte = self._codex_letzte
        if letzte is not None and time.monotonic() - letzte < CODEX_TAKT_SEKUNDEN:
            return
        self._codex_messen_ausfuehren()

    def _codex_vor_automatik(self) -> None:
        """Vor der Automatik: bei frischer Claude-Messung ≥ Schwelle und altem Codex-Stand erst frisch messen."""
        try:
            jetzt = datetime.now(timezone.utc)
            im_limit, _ = automatik._claude_im_limit(signale.claude_lesen(jetzt=jetzt), anzeige.schwelle(), jetzt)
            if not im_limit:
                return
            stand = signale.codex_lesen(jetzt=jetzt).stand
            if stand is not None and timedelta(0) <= jetzt - stand <= timedelta(seconds=CODEX_VOR_ALTER_SEKUNDEN):
                return
        except Exception as fehler:  # noqa: BLE001 - die Vorprüfung darf den Takt nie beenden
            _protokoll(f"Codex-Vormessung nicht geprüft ({type(fehler).__name__})")
            return
        self._codex_messen_ausfuehren()

    def _codex_messen_ausfuehren(self) -> None:
        """Eine Codex-Messung; läuft nie parallel zu sich selbst. Im Log nur die feste Fehlerklasse."""
        if not self._codex_sperre.acquire(blocking=False):
            return
        try:
            self._codex_letzte = time.monotonic()
            try:
                kontingent = codex_messen.messen()
            except Exception as fehler:  # noqa: BLE001 - nur die Fehlerklasse, nie Text
                _protokoll(f"Codex-Messung fehlgeschlagen ({type(fehler).__name__})")
                return
            if kontingent.fehler:
                _protokoll(kontingent.fehler)
        finally:
            self._codex_sperre.release()

    # --- Takt des Wechselassistenten --------------------------------------------------

    def _assistent_takt(self) -> None:
        """Eigener leichter Faden: alle `ASSISTENT_TAKT_SEKUNDEN` jeden offenen Vorgang einen Schritt weiter."""
        while not self._stopp.is_set():
            if self._stopp.wait(ASSISTENT_TAKT_SEKUNDEN):
                break
            self._assistent_schritt()

    def _assistent_schritt(self, jetzt: datetime | None = None) -> None:
        """Ein Durchlauf: `fortsetzen` je offenem Vorgang, Menü bei Phasenwechsel, Hinweise. Wirft nie."""
        if not self._assistent_sperre.acquire(blocking=False):
            return
        try:
            jetzt = jetzt or datetime.now(timezone.utc)
            try:
                offene = [v for v in assistent_vorgaenge.lesen() if v.phase not in assistent_vorgaenge.ENDGUELTIG]
            except Exception as fehler:  # noqa: BLE001
                _protokoll(f"Wechselvorgänge nicht lesbar ({type(fehler).__name__})")
                return
            for vorgang in offene:
                try:
                    assistent.fortsetzen(vorgang.id)
                except Exception as fehler:  # noqa: BLE001 - nur die Fehlerklasse, nie Text oder Kennung
                    _protokoll(f"Wechselvorgang nicht fortgesetzt ({type(fehler).__name__})")
            try:
                aktuell = assistent_vorgaenge.lesen()
            except Exception as fehler:  # noqa: BLE001
                _protokoll(f"Wechselvorgänge nicht lesbar ({type(fehler).__name__})")
                return
            self._hinweise_pruefen(aktuell, jetzt)
            if [(v.id, v.phase) for v in aktuell] != [(v.id, v.phase) for v in self._wechsel_snapshot]:
                self._wechsel_snapshot = aktuell
                try:
                    self.icon.update_menu()
                except Exception:  # noqa: BLE001
                    _protokoll("Menü konnte nicht aktualisiert werden")
        finally:
            self._assistent_sperre.release()

    def _hinweise_pruefen(self, liste: list[assistent_vorgaenge.Vorgang], jetzt: datetime) -> None:
        """Windows-Hinweise: je Vorgang und Ereignis genau einmal (Merker nur im Speicher)."""
        for vorgang in liste:
            try:
                treffer = fenster_modell.hinweis_fuer(vorgang, jetzt)
            except Exception as fehler:  # noqa: BLE001
                _protokoll(f"Hinweis nicht ermittelbar ({type(fehler).__name__})")
                continue
            if treffer is None:
                continue
            ereignis, text = treffer
            if (vorgang.id, ereignis) in self._hinweis_gemeldet:
                continue
            self._hinweis_gemeldet.add((vorgang.id, ereignis))
            for niedriger in HINWEIS_VERDRAENGT.get(ereignis, ()):
                self._hinweis_gemeldet.add((vorgang.id, niedriger))
            self._melden(text)

    def _wiederaufnahme_beim_start(self) -> None:
        """Absturzreste einmal ordnen; im Log nur Zähler je Status – keine Kennungen, keine Hinweistexte."""
        try:
            ergebnisse = assistent_vorgaenge.wiederaufnehmen()
        except Exception as fehler:  # noqa: BLE001
            _protokoll(f"Wiederaufnahme der Wechselvorgänge fehlgeschlagen ({type(fehler).__name__})")
            return
        if ergebnisse:
            zaehler = Counter(e.status for e in ergebnisse)
            _protokoll("Wiederaufnahme der Wechselvorgänge: "
                       + ", ".join(f"{status} {anzahl}" for status, anzahl in sorted(zaehler.items())))

    def _messung_ausfuehren(self) -> None:
        if not self._messung_sperre.acquire(blocking=False):
            return
        try:
            try:
                claude_messen.messen()
            except claude_messen.MessFehler as fehler:
                self._messung_fehler = str(fehler)
                # Fehlerart und HTTP-Code (nie Antwort- oder Zugangsdaten), damit Ausfälle später erklärbar sind
                code = f", HTTP {fehler.status}" if fehler.status else ""
                _protokoll(f"Claude-Messung fehlgeschlagen: {fehler} [{fehler.kategorie}{code}]")
                if fehler.status == 429:
                    self._429_aktiv = True
                self._messung_intervall = 300 if self._429_aktiv else anzeige.claude_takt_min() * 60
            except Exception:
                self._messung_fehler = "Claude-Messung konnte nicht gelesen werden"
                _protokoll("Claude-Messung konnte nicht gelesen werden")
                self._messung_intervall = 300 if self._429_aktiv else anzeige.claude_takt_min() * 60
            else:
                self._messung_fehler = None
                self._429_aktiv = False
                self._messung_intervall = anzeige.claude_takt_min() * 60
        finally:
            self._messung_sperre.release()

    def _beenden(self) -> None:
        self._stopp.set()
        self._messung_angefordert.set()
        self.icon.stop()

    def _start(self, icon) -> None:
        icon.visible = True
        self._wiederaufnahme_beim_start()
        self.aktualisieren()
        self._messung_angefordert.set()
        if self._arbeits_thread is None or not getattr(self._arbeits_thread, "is_alive", lambda: False)():
            self._arbeits_thread = threading.Thread(target=self._takt, daemon=True)
            self._arbeits_thread.start()
        if self._assistent_thread is None or not getattr(self._assistent_thread, "is_alive", lambda: False)():
            self._assistent_thread = threading.Thread(target=self._assistent_takt, daemon=True)
            self._assistent_thread.start()
        self._modellabgleich_pruefen()   # fehlende/veraltete Modellkataloge gleich im Hintergrund holen

    def run(self) -> None:
        self.icon.run(setup=self._start)


def main() -> None:
    Leiste().run()


if __name__ == "__main__":
    main()
