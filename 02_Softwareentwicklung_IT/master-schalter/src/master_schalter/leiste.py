"""Taskleisten-Symbol: zeigt aktiven Master, Lage und die Kontingente von Claude Code und Codex.

* Mauszeiger darüber: kurze Zeile, beginnt mit dem Master („M Claude L1 | …").
* Linksklick: Benachrichtigung mit allen Werten, Rücksetzzeit und Stand.
* Rechtsklick: Menü mit Master, Lage, Kontingenten, „Master wechseln", „Wechsel-Schwelle",
  „Aktualisieren" und „Beenden".
* Ein weißer Punkt über einem Balken zeigt den aktiven Master.

Start ohne Konsolenfenster: `.venv\\Scripts\\pythonw.exe -m master_schalter.leiste`
"""
from __future__ import annotations

import threading
import time

import pystray

from . import anzeige, automatik, claude_messen, paare, rollen, signale, symbol, vorgaenge, wechsel, zustand


TAKT_SEKUNDEN = 60


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
        yield pystray.MenuItem("Automatik Claude → Codex", self._automatik_umschalten,
                               checked=self._ist_automatik_an)
        yield pystray.MenuItem("Chats übergeben", pystray.Menu(*self._paar_optionen()))
        yield pystray.MenuItem("Jetzt prüfen", self._jetzt_pruefen_aktion)
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

    def _ist_automatik_an(self, item=None):
        return anzeige.automatik_an()

    def _automatik_umschalten(self) -> None:
        anzeige.automatik_setzen(not anzeige.automatik_an())
        self.aktualisieren()

    def _jetzt_pruefen_aktion(self) -> None:
        threading.Thread(target=self._automatik_ausfuehren, daemon=True).start()

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

    def _wechseln(self, master: str) -> None:
        try:
            ergebnis = wechsel.wechseln(master)
            text = anzeige.wechsel_hinweis(ergebnis)
        except Exception as fehler:  # noqa: BLE001 - die Leiste darf nie wegen eines Klicks abstürzen
            text = f"Wechsel fehlgeschlagen: {fehler}"[:anzeige.HINWEIS_MAX]
        self.aktualisieren()
        self.icon.notify(text, "Master-Schalter")

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
                    self._automatik_anfordern()   # Prüfung nach jeder erfolgreichen Claude-Messung

    def _messung_ausfuehren(self) -> None:
        if not self._messung_sperre.acquire(blocking=False):
            return
        try:
            try:
                claude_messen.messen()
            except claude_messen.MessFehler as fehler:
                self._messung_fehler = str(fehler)
                if fehler.status == 429:
                    self._429_aktiv = True
                self._messung_intervall = 300 if self._429_aktiv else anzeige.claude_takt_min() * 60
            except Exception:
                self._messung_fehler = "Claude-Messung konnte nicht gelesen werden"
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
