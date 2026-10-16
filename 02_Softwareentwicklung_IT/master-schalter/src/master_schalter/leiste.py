"""Taskleisten-Symbol: zeigt aktiven Master, Lage und die Kontingente von Claude Code und Codex.

* Mauszeiger darüber: kurze Zeile, beginnt mit dem Master („M Claude L1 | …").
* Linksklick: Benachrichtigung mit allen Werten, Rücksetzzeit und Stand.
 * Rechtsklick: Menü mit Master, Lage, Kontingenten, „Master wechseln" (Bestätigungsdialog;
   Ziel Codex stößt die Rückgabe an die Codex-Chats an), „Wechsel-Schwelle", „Chats übergeben",
   „Aktualisieren" (misst frisch und hakt offene Übergaben ab) und „Beenden".
* Ein weißer Punkt über einem Balken zeigt den aktiven Master.

Start ohne Konsolenfenster: `.venv\\Scripts\\pythonw.exe -m master_schalter.leiste`
"""
from __future__ import annotations

import sys
import threading
import time
from datetime import datetime, timezone

import pystray

from . import (anzeige, automatik, claude_messen, dialog, paare, rollen, rueckgabe, signale,
                 symbol, uebergabe, vorgaenge, wechsel, zustand)


TAKT_SEKUNDEN = 60


def _protokoll(text: str) -> None:
    """Messfehler mit Zeitstempel ins Protokoll (stderr → `leiste.log` des Starters)."""
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {text}", file=sys.stderr, flush=True)


class Leiste:
    def __init__(self) -> None:
        self._kontingente: list[signale.Kontingent] = []
        self._zustand = zustand.Zustand()
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
        self._dialog = dialog.frage
        self.icon = pystray.Icon("master-schalter", symbol.bild(None, None, anzeige.STANDARD_SCHWELLE),
                                 "Master-Schalter", menu=pystray.Menu(self._menue))

    # --- Menü ---------------------------------------------------------------

    def _menue(self):
        yield pystray.MenuItem("Details", self._zeigen, default=True, visible=False)
        yield pystray.MenuItem(anzeige.master_menuezeile(self._zustand), None, enabled=False)
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
        yield pystray.MenuItem("Chats übergeben", pystray.Menu(*self._paar_optionen()))
        for zeile in self._automatik_staende_zeilen():
            yield pystray.MenuItem(zeile, None, enabled=False)
        yield pystray.Menu.SEPARATOR
        yield pystray.MenuItem("Aktualisieren", self._aktualisieren_aktion)
        yield pystray.MenuItem("Beenden", self._beenden)

    def _paar_optionen(self):
        liste = paare.lesen()
        vorgangsliste = vorgaenge.lesen()
        if not liste:
            return [pystray.MenuItem("keine Paare angelegt", None, enabled=False)]
        return [pystray.MenuItem(f"{p.thema}: {automatik.status_zeile(p, vorgangsliste)}",
                                 self._paar_umschalten_aktion(p.thema), checked=lambda item, p=p: self._ist_paar_an(p.thema))
                for p in liste]

    def _automatik_staende_zeilen(self) -> list[str]:
        return [s.status if not s.thema else f"{s.thema}: {s.status}" for s in self._automatik_staende]

    def _ist_paar_an(self, thema: str):
        return any(p.thema == thema and p.aktiv for p in paare.lesen())

    def _paar_umschalten_aktion(self, thema: str):
        def aktion() -> None:
            try:
                paare.aktiv_setzen(thema, not self._ist_paar_an(thema))
            except paare.PaarFehler as fehler:
                self.icon.notify(f"Paar nicht geändert: {fehler}"[:anzeige.HINWEIS_MAX], "Master-Schalter")
            self.aktualisieren()

        return aktion

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
            zeilen = [f"\u2022 {p.thema}: {self._kopfzeilen_zustand(p)}"
                      for p in paare.lesen() if p.aktiv]
            liste = "\n".join(zeilen) if zeilen else "keine aktiven Themen"
            return ("Wirklich Master an Codex übergeben?\n\n"
                    "Danach wird jedes aktive Thema an seinen Codex-Chat zurückgegeben – "
                    "es geht je eine Übergabenachricht raus:\n"
                    f"{liste}\n\n"
                    "Ist Codex bereits Master, passiert nichts weiter (erneuter Versand nur per "
                    "Kommandozeile mit --erneut).\n\n"
                    "Die Empfänger bestätigen mit ACK.")
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
        self._kontingente = signale.alle_lesen()
        self._zustand = zustand.lesen()
        schwelle = anzeige.schwelle()
        claude, codex = self._kontingente
        self._lage = rollen.lage(claude, codex, schwelle)
        self._grund = rollen.lage_grund(claude, codex, schwelle)
        fuenf = [(k.fenster_nach_name("5h")) for k in self._kontingente]
        self.icon.icon = symbol.bild(fuenf[0].prozent if fuenf[0] else None,
                                     fuenf[1].prozent if fuenf[1] else None, schwelle, self._zustand.master)
        self.icon.title = anzeige.tooltip(self._kontingente, kopf=anzeige.tooltip_kopf(self._zustand.master, self._lage))
        self.icon.update_menu()

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

    def run(self) -> None:
        self.icon.run(setup=self._start)


def main() -> None:
    Leiste().run()


if __name__ == "__main__":
    main()
