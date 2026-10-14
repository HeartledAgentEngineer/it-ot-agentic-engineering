"""Taskleisten-Symbol: zeigt die Kontingente von Claude Code und Codex.

* Mauszeiger darüber: kurze Zeile mit beiden Mastern (Tooltip).
* Linksklick: Benachrichtigung mit allen Werten, Rücksetzzeit und Stand.
* Rechtsklick: Menü mit denselben Angaben, „Aktualisieren" und „Beenden".

Start ohne Konsolenfenster: `.venv\\Scripts\\pythonw.exe -m master_schalter.leiste`
"""
from __future__ import annotations

import threading

import pystray

from . import anzeige, signale, symbol

TAKT_SEKUNDEN = 60


class Leiste:
    def __init__(self) -> None:
        self._kontingente: list[signale.Kontingent] = []
        self._stopp = threading.Event()
        self.icon = pystray.Icon("master-schalter", symbol.bild(None, None, anzeige.STANDARD_SCHWELLE),
                                 "Master-Schalter", menu=pystray.Menu(self._menue))

    def _menue(self):
        yield pystray.MenuItem("Details", self._zeigen, default=True, visible=False)
        for zeile in anzeige.details(self._kontingente):
            yield pystray.MenuItem(zeile, None, enabled=False)
        yield pystray.Menu.SEPARATOR
        yield pystray.MenuItem("Aktualisieren", lambda: self.aktualisieren())
        yield pystray.MenuItem("Beenden", self._beenden)

    def aktualisieren(self) -> None:
        self._kontingente = signale.alle_lesen()
        claude, codex = (k.fenster_nach_name("5h") for k in self._kontingente)
        self.icon.icon = symbol.bild(claude.prozent if claude else None, codex.prozent if codex else None,
                                     anzeige.schwelle())
        self.icon.title = anzeige.tooltip(self._kontingente)
        self.icon.update_menu()

    def _zeigen(self) -> None:
        self.aktualisieren()
        self.icon.notify(anzeige.hinweis(self._kontingente), "Kontingente")

    def _takt(self) -> None:
        while not self._stopp.wait(TAKT_SEKUNDEN):
            self.aktualisieren()

    def _beenden(self) -> None:
        self._stopp.set()
        self.icon.stop()

    def _start(self, icon) -> None:
        icon.visible = True
        self.aktualisieren()
        threading.Thread(target=self._takt, daemon=True).start()

    def run(self) -> None:
        self.icon.run(setup=self._start)


def main() -> None:
    Leiste().run()


if __name__ == "__main__":
    main()
