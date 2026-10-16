"""Taskleisten-Symbol: zeigt aktiven Master, Lage und die Kontingente von Claude Code und Codex.

* Mauszeiger darüber: kurze Zeile, beginnt mit dem Master („M Claude L1 | …").
* Linksklick: Benachrichtigung mit allen Werten, Rücksetzzeit und Stand.
 * Rechtsklick: Menü mit Master, Lage, Kontingenten, „Master wechseln" (Bestätigungsdialog;
   Ziel Codex stößt die Rückgabe an die Codex-Chats an), „Wechsel-Schwelle", „Chats übergeben",
   „Arbeitsmodus je Thema" (je Thema Master, Ausführer, Ausführermodell), „Modelle aktualisieren",
   „Aktualisieren" (misst frisch und hakt offene Übergaben ab) und „Beenden".
* Ein weißer Punkt über einem Balken zeigt den aktiven Master.

Menü und checked/label-Rückrufe arbeiten ausschließlich aus unveränderlichen Momentaufnahmen
(`aktualisieren()`); im Menüklick- oder checked-Faden findet nie eine Datei-, Prozess- oder
Netzabfrage statt. Rollenänderungen laufen im Hintergrund mit nichtblockierender Themensperre;
der Modellkatalog wird im Hintergrund mit Single-Flight-Riegel abgeglichen.

Start ohne Konsolenfenster: `.venv\\Scripts\\pythonw.exe -m master_schalter.leiste`
"""
from __future__ import annotations

import sys
import threading
import time
from datetime import datetime, timezone
from typing import Callable

import pystray

from . import (anzeige, automatik, claude_messen, dialog, modi, modelle, paare, rollen, rueckgabe,
               signale, symbol, uebergabe, vorgaenge, wechsel, zustand)


TAKT_SEKUNDEN = 60
MODELLE_TAKT_SEKUNDEN = 1800   # automatischer Katalogabgleich höchstens alle 30 Minuten


def _protokoll(text: str) -> None:
    """Messfehler mit Zeitstempel ins Protokoll (stderr → `leiste.log` des Starters)."""
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {text}", file=sys.stderr, flush=True)


class Leiste:
    def __init__(self) -> None:
        self._kontingente: list[signale.Kontingent] = []
        self._zustand = zustand.Zustand()
        self._paare_snapshot: list[paare.Paar] = []
        self._vorgaenge_snapshot: list[vorgaenge.Vorgang] = []
        self._modus_snapshot: dict[str, tuple[str, str, bool]] = {}
        self._rollen_snapshot: dict[str, anzeige.Rollenstand] = {}
        self._kataloge: tuple[anzeige.Katalogstand, ...] | None = None
        self._modus_fehler: str | None = None
        self._lage: str | None = None
        self._grund = ""
        self._stopp = threading.Event()
        self._messung_angefordert = threading.Event()
        self._messung_sperre = threading.Lock()
        self._messung_fehler: str | None = None
        self._429_aktiv = False
        self._messung_intervall = anzeige.claude_takt_min() * 60
        self._arbeits_thread = None
        self._automatik_sperre = threading.Lock()
        self._automatik_staende: list[automatik.Stand] = []
        self._bestaetigung_sperre = threading.Lock()
        self._modelle_sperre = threading.Lock()
        self._modellversuch: float | None = None   # monotone Zeit des letzten Katalogabgleichs
        self._dialog = dialog.frage
        self.icon = pystray.Icon("master-schalter", symbol.bild(None, None, anzeige.STANDARD_SCHWELLE),
                                 "Master-Schalter", menu=pystray.Menu(self._menue))

    # --- Menü ---------------------------------------------------------------

    def _menue(self):
        yield pystray.MenuItem("Details", self._zeigen, default=True, visible=False)
        geschuetzt = [t for t, (_, _, sicher) in self._modus_snapshot.items() if sicher]
        kopf = ("Standard-Master (übrige Themen): " + anzeige.MASTER_NAMEN.get(self._zustand.master, "nicht gesetzt")
                if geschuetzt else anzeige.master_menuezeile(self._zustand))
        yield pystray.MenuItem(kopf, None, enabled=False)
        if geschuetzt:
            yield pystray.MenuItem(anzeige.feste_themen_zeile(geschuetzt), None, enabled=False)
        if self._modus_fehler:
            yield pystray.MenuItem(f"Arbeitsmodus: {self._modus_fehler}", None, enabled=False)
        for zeile in anzeige.lage_zeilen(self._lage, self._grund):
            yield pystray.MenuItem(zeile, None, enabled=False)
        yield pystray.Menu.SEPARATOR
        for zeile in anzeige.details(self._kontingente):
            yield pystray.MenuItem(zeile, None, enabled=False)
        if self._messung_fehler:
            yield pystray.MenuItem(f"Claude-Messung: {self._messung_fehler}", None, enabled=False)
        yield pystray.Menu.SEPARATOR
        yield pystray.MenuItem("Master wechseln", pystray.Menu(*self._master_optionen()))
        yield pystray.MenuItem("Wechsel-Schwelle", pystray.Menu(*self._schwellen_optionen()))
        yield pystray.MenuItem("Arbeitsmodus je Thema", pystray.Menu(*self._modus_themen_optionen()))
        for zeile in anzeige.katalog_zeilen(self._kataloge or ()):
            yield pystray.MenuItem(zeile, None, enabled=False)
        yield pystray.MenuItem(anzeige.MODELLE_AKTUALISIEREN, self._modelle_aktualisieren_aktion)
        yield pystray.MenuItem("Chats übergeben", pystray.Menu(*self._paar_optionen()))
        for zeile in self._automatik_staende_zeilen():
            yield pystray.MenuItem(zeile, None, enabled=False)
        yield pystray.Menu.SEPARATOR
        yield pystray.MenuItem("Aktualisieren", self._aktualisieren_aktion)
        yield pystray.MenuItem("Beenden", self._beenden)

    def _paar_optionen(self):
        liste = self._paare_snapshot
        vorgangsliste = self._vorgaenge_snapshot
        if not liste:
            return [pystray.MenuItem("keine Paare angelegt", None, enabled=False)]
        return [pystray.MenuItem(f"{p.thema}: {automatik.status_zeile(p, vorgangsliste)}",
                                 self._paar_umschalten_aktion(p.thema), checked=lambda item, p=p: self._ist_paar_an(p.thema))
                for p in liste]

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
            self._wechseln(master)
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
            ausnahme = ("\nGeschützte Hermes-Themen bleiben unberührt: " + ", ".join(geschuetzt)
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
        if not self._dialog("Master-Schalter", self._wechsel_text(master)):
            return
        ergebnis = None
        try:
            ergebnis = wechsel.wechseln(master)
            text = anzeige.wechsel_hinweis(ergebnis)
        except Exception as fehler:  # noqa: BLE001 - die Leiste darf nie wegen eines Klicks abstürzen
            text = f"Wechsel fehlgeschlagen: {fehler}"[:anzeige.HINWEIS_MAX]
        self.aktualisieren()
        self.icon.notify(text, "Master-Schalter")
        if ergebnis is not None and ergebnis.art == "gewechselt" and master == "codex":
            threading.Thread(target=self._rueckgabe_ausfuehren, daemon=True).start()

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
            self._kataloge = self._kataloge_lesen()
            try:
                self._modus_snapshot = modi.snapshot([p.thema for p in self._paare_snapshot])
                profile = modi.lesen()
                self._rollen_snapshot = {}
                for p in self._paare_snapshot:
                    wert = profile.get(p.thema, modi.Profil())
                    self._rollen_snapshot[p.thema] = anzeige.Rollenstand(
                        wert.master, wert.worker, wert.modell, self._kataloge or ())
                self._modus_fehler = None
            except (modi.ModusFehler, OSError) as fehler:
                self._modus_snapshot = {}
                self._rollen_snapshot = {}
                self._modus_fehler = f"nicht verfügbar: {fehler}"
            self._kontingente = signale.alle_lesen()
            self._zustand = zustand.lesen()
            schwelle = anzeige.schwelle()
            claude, codex = self._kontingente
            self._lage = rollen.lage(claude, codex, schwelle)
            self._grund = rollen.lage_grund(claude, codex, schwelle)
            fuenf = [(k.fenster_nach_name("5h")) for k in self._kontingente]
            self.icon.icon = symbol.bild(fuenf[0].prozent if fuenf[0] else None,
                                         fuenf[1].prozent if fuenf[1] else None, schwelle, self._zustand.master)
            self.icon.title = anzeige.tooltip(
                self._kontingente, kopf=anzeige.tooltip_kopf(self._zustand.master, self._lage))
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

    def _zeigen(self) -> None:
        self.aktualisieren()
        self.icon.notify(anzeige.hinweis(self._kontingente), "Kontingente")

    def _takt(self) -> None:
        letzte_messung = time.monotonic()
        while not self._stopp.is_set():
            angefordert = self._messung_angefordert.wait(TAKT_SEKUNDEN)
            if self._stopp.is_set():
                break
            if angefordert:
                self._messung_angefordert.clear()
            self.aktualisieren()
            intervall_abgelaufen = time.monotonic() - letzte_messung >= self._messung_intervall
            if (angefordert and not self._429_aktiv) or intervall_abgelaufen:
                self._messung_ausfuehren()
                letzte_messung = time.monotonic()
                self.aktualisieren()
                if self._messung_fehler is None:
                    if anzeige.automatik_an():
                        self._automatik_anfordern()   # Prüfung nach jeder erfolgreichen Claude-Messung
                    else:
                        self._bestaetigung_anfordern()   # offene Übergaben abhaken – auch ohne Automatik
            self._modellabgleich_pruefen()   # abgelaufener Modellkatalog wird im Hintergrund erneuert

    def _messung_ausfuehren(self) -> None:
        if not self._messung_sperre.acquire(blocking=False):
            return
        try:
            try:
                claude_messen.messen()
            except claude_messen.MessFehler as fehler:
                self._messung_fehler = str(fehler)
                _protokoll(f"Claude-Messung fehlgeschlagen: {fehler}")
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
        self.aktualisieren()
        self._messung_angefordert.set()
        if self._arbeits_thread is None or not getattr(self._arbeits_thread, "is_alive", lambda: False)():
            self._arbeits_thread = threading.Thread(target=self._takt, daemon=True)
            self._arbeits_thread.start()
        self._modellabgleich_pruefen()   # fehlende/veraltete Modellkataloge gleich im Hintergrund holen

    def run(self) -> None:
        self.icon.run(setup=self._start)


def main() -> None:
    Leiste().run()


if __name__ == "__main__":
    main()
