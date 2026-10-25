"""Wechselfenster (Baustein P7a, Plan E7): Themen, „Übergabe starten“, Vorgänge und Protokoll in einem Fenster.

Start: `python -m master_schalter.fenster` (ohne Konsole: `pythonw.exe -m master_schalter.fenster`) oder
`masterwechsel fenster`; die Leiste öffnet es als eigenen Prozess („Übergabe starten …“).

* **Nur eine Instanz:** eine nicht blockierende Sperre `fenster.lock` im Datenordner (`zustand.instanz_sperre`).
  Läuft schon ein Fenster, beendet sich der zweite Start still (Hinweis auf stderr, Exit 0) und holt nichts
  nach vorn.
* **Aktualisierung alle 3 s:** `fenster_modell.aufnehmen()` läuft im Hintergrund-Thread, das Ergebnis geht über
  eine Warteschlange an den Tk-Thread. Dasselbe gilt für die Aktionen („Übergeben“, „Jetzt weiter“,
  „Abbrechen“): nie Dateizugriff oder Wartezeit im Tk-Thread, nie Tk-Aufruf aus einem anderen Thread.
* **Dünne Oberfläche:** Auswahl, Prüfung, Texte und Aktionen liegen in `fenster_modell.py` und sind dort ohne
  Bildschirm getestet. Chat-Titel, Ordner und Kennungen erscheinen nur hier im lokalen Fenster (G9).
* **Bestätigung vor dem Übergeben:** eine Zeile mit der Zusammenfassung und ein Ja/Nein-Dialog (`dialog.frage`,
  Standard **Nein**). Auch „Abbrechen“ eines Vorgangs fragt nach.
"""
from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from datetime import datetime, timezone
from tkinter import ttk
from typing import Callable

from . import anzeige, dialog, zustand
from . import fenster_modell as fm

INSTANZ = "fenster"
TAKT_MS = 3000            # alle 3 s frisch lesen
ABFRAGE_MS = 150          # Warteschlange des Hintergrund-Threads leeren
TITEL = "Master-Schalter – Wechselassistent"
ZIELE = tuple(anzeige.MASTER_NAMEN.items())   # (Rolle, Anzeigename)


class Fenster:
    def __init__(self, root: tk.Tk, *, laden: Callable[[], fm.Momentaufnahme] = fm.aufnehmen,
                 frage: Callable[[str, str], bool] = dialog.frage,
                 uebergeben: Callable[[fm.Auswahl], fm.Ergebnis] = fm.uebergabe_ausfuehren,
                 weiter: Callable[[str], fm.Ergebnis] = fm.weiter,
                 abbrechen: Callable[[str], fm.Ergebnis] = fm.abbrechen,
                 takt_ms: int = TAKT_MS, starten: bool = True) -> None:
        self.root = root
        self._laden, self._frage = laden, frage
        self._uebergeben, self._weiter, self._abbrechen = uebergeben, weiter, abbrechen
        self._takt_ms = takt_ms
        self._queue: queue.Queue = queue.Queue()
        self._snap: fm.Momentaufnahme | None = None
        self._laedt = False
        self._beschaeftigt = False
        self._optionen: dict[str, list[fm.ChatEintrag]] = {"von": [], "nach": []}
        self._wahl: dict[str, tuple | None] = {"von": None, "nach": None}
        self._angefasst = {"von": False, "nach": False}
        self._staende: dict[str, object] = {}
        self._bauen()
        if starten:
            self.root.after(ABFRAGE_MS, self._abfragen)
            self.laden_anstossen()
            self.root.after(self._takt_ms, self._takt)

    # --- Aufbau -------------------------------------------------------------------

    def _bauen(self) -> None:
        wurzel = self.root
        wurzel.title(TITEL)
        wurzel.geometry("1120x780")
        wurzel.minsize(900, 640)
        wurzel.columnconfigure(0, weight=1)
        wurzel.rowconfigure(2, weight=3)
        wurzel.rowconfigure(3, weight=2)

        # 1. Themen
        themen = ttk.LabelFrame(wurzel, text="Themen")
        themen.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        themen.columnconfigure(0, weight=1)
        self.themen_baum = ttk.Treeview(themen, columns=("thema", "master", "kopf", "automatik"),
                                        show="headings", height=4, selectmode="none")
        for spalte, titel, breite in (("thema", "Thema", 200), ("master", "Ist-Master", 220),
                                      ("kopf", "Übergabebereit (Kopfzeile)", 260), ("automatik", "Automatik", 100)):
            self.themen_baum.heading(spalte, text=titel)
            self.themen_baum.column(spalte, width=breite, stretch=spalte == "kopf")
        self.themen_baum.grid(row=0, column=0, sticky="ew", padx=4, pady=4)

        # 2. Übergabe starten
        start = ttk.LabelFrame(wurzel, text="Übergabe starten")
        start.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        start.columnconfigure(1, weight=1)
        start.columnconfigure(3, weight=1)
        self.thema_var, self.ziel_var = tk.StringVar(), tk.StringVar()
        self.von_var, self.nach_var = tk.StringVar(), tk.StringVar()
        ttk.Label(start, text="Thema").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.thema_box = ttk.Combobox(start, textvariable=self.thema_var, state="readonly", values=())
        self.thema_box.grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        ttk.Label(start, text="Ziel").grid(row=0, column=2, sticky="w", padx=4, pady=2)
        self.ziel_box = ttk.Combobox(start, textvariable=self.ziel_var, state="readonly",
                                     values=[name for _, name in ZIELE])
        self.ziel_box.grid(row=0, column=3, sticky="ew", padx=4, pady=2)
        ttk.Label(start, text="Von-Chat (alter Master)").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        self.von_box = ttk.Combobox(start, textvariable=self.von_var, state="readonly", values=())
        self.von_box.grid(row=1, column=1, columnspan=3, sticky="ew", padx=4, pady=2)
        ttk.Label(start, text="Nach-Chat (neuer Master)").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        self.nach_box = ttk.Combobox(start, textvariable=self.nach_var, state="readonly", values=())
        self.nach_box.grid(row=2, column=1, columnspan=3, sticky="ew", padx=4, pady=2)
        self.uebergeben_knopf = ttk.Button(start, text="Übergeben", command=self.uebergeben_klick)
        self.uebergeben_knopf.grid(row=3, column=0, sticky="w", padx=4, pady=(4, 6))
        self.thema_box.bind("<<ComboboxSelected>>", self._thema_oder_ziel_gewaehlt)
        self.ziel_box.bind("<<ComboboxSelected>>", self._thema_oder_ziel_gewaehlt)
        self.von_box.bind("<<ComboboxSelected>>", lambda _e: self._chat_gewaehlt("von"))
        self.nach_box.bind("<<ComboboxSelected>>", lambda _e: self._chat_gewaehlt("nach"))

        # 3. Vorgänge
        vorgaenge = ttk.LabelFrame(wurzel, text="Vorgänge (offene und die letzten 10 abgeschlossenen)")
        vorgaenge.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)
        vorgaenge.columnconfigure(0, weight=1)
        vorgaenge.rowconfigure(0, weight=1)
        self.vorgang_baum = ttk.Treeview(vorgaenge, columns=("thema", "richtung", "phase", "hinweis"),
                                         show="headings", height=6, selectmode="browse")
        for spalte, titel, breite, strecken in (("thema", "Thema", 140, False), ("richtung", "Von → Zu", 140, False),
                                                ("phase", "Phase", 210, False), ("hinweis", "Zustellweg / Hinweis", 560, True)):
            self.vorgang_baum.heading(spalte, text=titel)
            self.vorgang_baum.column(spalte, width=breite, stretch=strecken)
        self.vorgang_baum.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        regler = ttk.Scrollbar(vorgaenge, orient="vertical", command=self.vorgang_baum.yview)
        regler.grid(row=0, column=1, sticky="ns", pady=4)
        self.vorgang_baum.configure(yscrollcommand=regler.set)
        self.vorgang_baum.bind("<<TreeviewSelect>>", lambda _e: self._knoepfe_aktualisieren())
        knoepfe = ttk.Frame(vorgaenge)
        knoepfe.grid(row=1, column=0, columnspan=2, sticky="w", padx=4)
        self.weiter_knopf = ttk.Button(knoepfe, text="Jetzt weiter", command=self.weiter_klick)
        self.abbrechen_knopf = ttk.Button(knoepfe, text="Abbrechen", command=self.abbrechen_klick)
        self.kopieren_knopf = ttk.Button(knoepfe, text="Text kopieren", command=self.kopieren_klick)
        for knopf in (self.weiter_knopf, self.abbrechen_knopf, self.kopieren_knopf):
            knopf.pack(side="left", padx=(0, 6), pady=4)
        self.kopierfeld = tk.Text(vorgaenge, height=3, wrap="word", state="disabled")
        self.kopierfeld.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 4))

        # 4. Protokoll
        protokoll = ttk.LabelFrame(wurzel, text="Protokoll (neueste oben)")
        protokoll.grid(row=3, column=0, sticky="nsew", padx=8, pady=4)
        protokoll.columnconfigure(0, weight=1)
        protokoll.rowconfigure(0, weight=1)
        self.protokoll_liste = tk.Listbox(protokoll, height=7, activestyle="none")
        self.protokoll_liste.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        regler2 = ttk.Scrollbar(protokoll, orient="vertical", command=self.protokoll_liste.yview)
        regler2.grid(row=0, column=1, sticky="ns", pady=4)
        self.protokoll_liste.configure(yscrollcommand=regler2.set)

        # Fuß
        self.status_var, self.hinweis_var = tk.StringVar(), tk.StringVar()
        ttk.Label(wurzel, textvariable=self.status_var, wraplength=1080, justify="left").grid(
            row=4, column=0, sticky="ew", padx=10, pady=(2, 0))
        ttk.Label(wurzel, textvariable=self.hinweis_var, wraplength=1080, justify="left",
                  foreground="#666666").grid(row=5, column=0, sticky="ew", padx=10, pady=(0, 8))
        self._knoepfe_aktualisieren()

    # --- Hintergrund-Lesen -----------------------------------------------------------

    def laden_anstossen(self) -> None:
        """Eine Aufnahme im Hintergrund-Thread starten; läuft schon eine, passiert nichts."""
        if self._laedt:
            return
        self._laedt = True

        def lauf() -> None:
            try:
                snap = self._laden()
            except Exception as fehler:  # noqa: BLE001 - das Fenster darf nie wegen eines Lesefehlers enden
                snap = fm.Momentaufnahme(datetime.now(timezone.utc),
                                         hinweise=(f"Aktualisierung fehlgeschlagen ({type(fehler).__name__})",))
            self._queue.put(("snap", snap))

        threading.Thread(target=lauf, daemon=True).start()

    def _takt(self) -> None:
        self.laden_anstossen()
        self.root.after(self._takt_ms, self._takt)

    def _abfragen(self) -> None:
        """Im Tk-Thread: Ergebnisse der Hintergrund-Threads übernehmen."""
        try:
            while True:
                art, inhalt = self._queue.get_nowait()
                if art == "snap":
                    self._laedt = False
                    self.snapshot_anwenden(inhalt)
                else:
                    self._beschaeftigt = False
                    self._status(inhalt.text, fehler=not inhalt.ok)
                    self._knoepfe_aktualisieren()
                    self.laden_anstossen()
        except queue.Empty:
            pass
        self.root.after(ABFRAGE_MS, self._abfragen)

    # --- Anzeige ---------------------------------------------------------------------

    def _status(self, text: str, *, fehler: bool = False) -> None:
        self.status_var.set(("Fehler: " if fehler else "") + text)

    def snapshot_anwenden(self, snap: fm.Momentaufnahme) -> None:
        self._snap = snap
        self._tabelle("themen", self.themen_baum,
                      [(t.thema, t.thema, t.master, t.kopf, "an" if t.automatik else "aus") for t in snap.themen])
        namen = [t.thema for t in snap.themen]
        if tuple(self.thema_box["values"]) != tuple(namen):
            self.thema_box["values"] = namen
        if self.thema_var.get() not in namen:
            self.thema_var.set("")
            self._wahl = {"von": None, "nach": None}
            self._angefasst = {"von": False, "nach": False}
        self._optionen_neu()
        self._tabelle("vorgaenge", self.vorgang_baum,
                      [(v.id, v.thema, v.richtung, v.phase, v.hinweis) for v in snap.vorgaenge])
        if self._staende.get("protokoll") != snap.protokoll:
            self._staende["protokoll"] = snap.protokoll
            self.protokoll_liste.delete(0, "end")
            for zeile in snap.protokoll:
                self.protokoll_liste.insert("end", zeile)
        self.hinweis_var.set(" · ".join(snap.hinweise))
        self._kopierfeld_aktualisieren()
        self._knoepfe_aktualisieren()

    def _tabelle(self, name: str, baum: ttk.Treeview, zeilen: list[tuple]) -> None:
        """Nur neu schreiben, wenn sich der Inhalt geändert hat (kein Flackern, Auswahl bleibt)."""
        if self._staende.get(name) == zeilen:
            return
        self._staende[name] = zeilen
        auswahl = baum.selection()
        baum.delete(*baum.get_children())
        for kennung, *werte in zeilen:
            baum.insert("", "end", iid=kennung, values=werte)
        if auswahl and baum.exists(auswahl[0]):
            baum.selection_set(auswahl[0])

    # --- Auswahl „Übergabe starten“ -----------------------------------------------------

    @staticmethod
    def _schluessel(eintrag: fm.ChatEintrag) -> tuple:
        return ("leer",) if eintrag.leer else (eintrag.werkzeug, eintrag.kennung)

    def _thema_zeile(self) -> fm.ThemaZeile | None:
        if self._snap is None:
            return None
        return next((t for t in self._snap.themen if t.thema == self.thema_var.get()), None)

    def _ziel_rolle(self) -> str | None:
        return next((rolle for rolle, name in ZIELE if name == self.ziel_var.get()), None)

    def _thema_oder_ziel_gewaehlt(self, _ereignis=None) -> None:
        self._wahl = {"von": None, "nach": None}
        self._angefasst = {"von": False, "nach": False}
        self._optionen_neu()

    def _chat_gewaehlt(self, art: str) -> None:
        eintrag = self._eintrag(art)
        self._wahl[art] = None if eintrag is None else self._schluessel(eintrag)
        self._angefasst[art] = True

    def _eintrag(self, art: str) -> fm.ChatEintrag | None:
        box = self.von_box if art == "von" else self.nach_box
        index = box.current()
        liste = self._optionen[art]
        return liste[index] if 0 <= index < len(liste) else None

    def _optionen_neu(self) -> None:
        """Auswahllisten neu bauen; eine bewusste Wahl bleibt (nach Kennung), sonst gilt der Vorschlag."""
        thema = self.thema_var.get() or None
        zeile = self._thema_zeile()
        chats = self._snap.chats if self._snap else ()
        for art, werkzeug, alt, box, var in (
                ("von", zeile.master_rolle if zeile else None, True, self.von_box, self.von_var),
                ("nach", self._ziel_rolle(), False, self.nach_box, self.nach_var)):
            eintraege, vorbelegt = fm.chat_optionen(chats, werkzeug, thema, alt=alt)
            alt_wahl = self._wahl[art]
            index = None
            if alt_wahl is not None:
                index = next((i for i, e in enumerate(eintraege) if self._schluessel(e) == alt_wahl), None)
            if index is None and not self._angefasst[art]:
                index = vorbelegt
            self._optionen[art] = eintraege
            box["values"] = [e.text for e in eintraege]
            if index is None:
                var.set("")
                box.set("")
                self._wahl[art] = None
            else:
                box.current(index)
                self._wahl[art] = self._schluessel(eintraege[index])

    def auswahl_lesen(self) -> fm.Auswahl:
        zeile = self._thema_zeile()
        return fm.Auswahl(self.thema_var.get() or None, self._ziel_rolle(),
                          zeile.master_rolle if zeile else None, self._eintrag("von"), self._eintrag("nach"))

    # --- Aktionen ----------------------------------------------------------------------

    def _im_hintergrund(self, funktion: Callable[..., fm.Ergebnis], *args) -> None:
        if self._beschaeftigt:
            self._status("Bitte kurz warten – eine Aktion läuft noch.")
            return
        self._beschaeftigt = True
        self._knoepfe_aktualisieren()

        def lauf() -> None:
            try:
                ergebnis = funktion(*args)
            except Exception as fehler:  # noqa: BLE001
                ergebnis = fm.Ergebnis(False, f"Aktion fehlgeschlagen ({type(fehler).__name__})")
            self._queue.put(("ergebnis", ergebnis))

        threading.Thread(target=lauf, daemon=True).start()

    def uebergeben_klick(self) -> None:
        auswahl = self.auswahl_lesen()
        fehler = fm.auswahl_pruefen(auswahl)
        if fehler is not None:
            self._status(fehler, fehler=True)
            return
        if not self._frage("Master-Schalter", fm.zusammenfassung(auswahl) + "\n\nWirklich übergeben?"):
            self._status("Nicht übergeben – nichts geändert.")
            return
        self._status("Übergabe läuft …")
        self._im_hintergrund(self._uebergeben, auswahl)

    def _gewaehlter_vorgang(self) -> fm.VorgangZeile | None:
        auswahl = self.vorgang_baum.selection()
        if not auswahl or self._snap is None:
            return None
        return next((v for v in self._snap.vorgaenge if v.id == auswahl[0]), None)

    def weiter_klick(self) -> None:
        vorgang = self._gewaehlter_vorgang()
        if vorgang is None or not vorgang.offen:
            return
        self._status("Vorgang wird fortgesetzt …")
        self._im_hintergrund(self._weiter, vorgang.id)

    def abbrechen_klick(self) -> None:
        vorgang = self._gewaehlter_vorgang()
        if vorgang is None or not vorgang.kann_abbrechen:
            return
        if not self._frage("Master-Schalter", f"Wechsel {vorgang.thema} ({vorgang.richtung}) wirklich abbrechen?\n\n"
                           "Die Rolle bleibt, wie sie ist; liegende Nachrichten dazu werden ungültig."):
            self._status("Nicht abgebrochen.")
            return
        self._status("Vorgang wird abgebrochen …")
        self._im_hintergrund(self._abbrechen, vorgang.id)

    def kopieren_klick(self) -> None:
        vorgang = self._gewaehlter_vorgang()
        if vorgang is None or not vorgang.kopiertext:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(vorgang.kopiertext)
        self.root.update()                      # Zwischenablage bleibt auch nach dem Schließen erhalten
        self._status("Text in die Zwischenablage kopiert – im Hermes-Chat einfügen.")

    def _kopierfeld_aktualisieren(self) -> None:
        vorgang = self._gewaehlter_vorgang()
        text = vorgang.kopiertext if vorgang is not None and vorgang.kopiertext else ""
        if self._staende.get("kopiertext") == text:
            return
        self._staende["kopiertext"] = text
        self.kopierfeld.configure(state="normal")
        self.kopierfeld.delete("1.0", "end")
        self.kopierfeld.insert("1.0", text)
        self.kopierfeld.configure(state="disabled")

    def _knoepfe_aktualisieren(self) -> None:
        vorgang = self._gewaehlter_vorgang()
        frei = not self._beschaeftigt

        def zustand_von(an: bool) -> str:
            return "normal" if an else "disabled"

        self.uebergeben_knopf.configure(state=zustand_von(frei))
        self.weiter_knopf.configure(state=zustand_von(frei and vorgang is not None and vorgang.offen))
        self.abbrechen_knopf.configure(state=zustand_von(frei and vorgang is not None and vorgang.kann_abbrechen))
        self.kopieren_knopf.configure(state=zustand_von(vorgang is not None and bool(vorgang.kopiertext)))
        self._kopierfeld_aktualisieren()


def main() -> int:
    """Genau ein Fenster: eine zweite Instanz beendet sich still (Exit 0)."""
    with zustand.instanz_sperre(INSTANZ) as frei:
        if not frei:
            print("Das Wechselfenster läuft bereits – nichts neu gestartet.", file=sys.stderr)
            return 0
        try:
            root = tk.Tk()
        except tk.TclError as fehler:
            print(f"Fenster konnte nicht geöffnet werden ({type(fehler).__name__}).", file=sys.stderr)
            return 1
        Fenster(root)
        root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
