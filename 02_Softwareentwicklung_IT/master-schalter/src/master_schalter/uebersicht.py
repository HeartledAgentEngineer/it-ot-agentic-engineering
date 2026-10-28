"""Übersichtsfenster des Master-Schalters: dieselben Daten wie `masterwechsel status`, aufgeräumt und mit Klick-Aktionen.

Start: `python -m master_schalter.uebersicht` (ohne Konsole: `pythonw.exe -m master_schalter.uebersicht`); die Leiste
öffnet es per Linksklick auf das Taskleistensymbol als eigenen Prozess.

* **Nur eine Instanz:** eine nicht blockierende Sperre `uebersicht.lock` im Datenordner
  (`zustand.instanz_sperre`). Läuft schon ein Fenster, beendet sich der zweite Start still (Hinweis auf stderr,
  Exit 0).
* **Aktualisierung alle 5 s:** `uebersicht_modell.aufnehmen()` läuft im Hintergrund-Thread, das Ergebnis geht über
  eine Warteschlange an den Tk-Thread. Dasselbe gilt für alle Aktionen: nie Dateizugriff oder Wartezeit im
  Tk-Thread, nie Tk-Aufruf aus einem anderen Thread.
* **Dünne Oberfläche:** Daten, Repo-Prüfung, Rückfragetexte und Aktionen liegen in `uebersicht_modell.py` und sind dort
  ohne Bildschirm getestet. Jede Änderung (Master und Arbeitsweise je Thema, „Alle nach Kontingent“, „Alle wie vorher“, Automatik)
  fragt vorher per Ja/Nein-Dialog (`dialog.frage`, Standard **Nein**); bei „Nein“ wird nichts geändert.
* **Nur Anzeige:** Findet die Aufnahme keinen echten Hauptarbeitsbaum, sind die Schreibknöpfe gesperrt.
"""
from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable

from . import dialog, kurz, zustand
from . import uebersicht_modell as um

INSTANZ = "uebersicht"
TAKT_MS = 5000            # alle 5 s frisch lesen
ABFRAGE_MS = 150          # Warteschlange des Hintergrund-Threads leeren
TITEL = "Master-Schalter – Übersicht"
RINNE = "#e5e7eb"         # Balkenhintergrund
FEHLERFARBE = "#b91c1c"
MASTER_ANZEIGE = tuple(um.MASTER_TEXTE[wert] for wert in um.MASTER_WERTE)   # in der Reihenfolge von MASTER_WERTE
ARBEITSWEISE_ANZEIGE = tuple(um.ARBEITSWEISE_TEXTE[wert] for wert in um.ARBEITSWEISE_WERTE)   # Protokoll, Vibe
SPALTEN = (("thema", "Thema", 150, False), ("master", "Master", 110, False), ("besitz", "Besitz", 120, False),
           ("pruefer", "Prüfer", 190, False), ("ausfuehrer", "Ausführer", 150, False),
           ("arbeitsweise", "Arbeitsweise", 100, False), ("auto", "Auto", 150, True))


class Fenster:
    def __init__(self, root: tk.Tk, *, laden: Callable[[], um.Uebersicht] = um.aufnehmen,
                 frage: Callable[[str, str], bool] = dialog.frage,
                 uebergabe: Callable[[], um.Ergebnis] = um.uebergabe_starten,
                 takt_ms: int = TAKT_MS, starten: bool = True) -> None:
        self.root = root
        self._laden, self._frage, self._uebergabe = laden, frage, uebergabe
        self._takt_ms = takt_ms
        self._queue: queue.Queue = queue.Queue()
        self._snap: um.Uebersicht | None = None
        self._laedt = False
        self._beschaeftigt = False
        self._staende: dict[str, object] = {}
        self._stile: dict[str, str] = {}
        self._bauen()
        if starten:
            self.root.after(ABFRAGE_MS, self._abfragen)
            self.laden_anstossen()
            self.root.after(self._takt_ms, self._takt)

    # --- Aufbau -------------------------------------------------------------------

    def _bauen(self) -> None:
        wurzel = self.root
        wurzel.title(TITEL)
        wurzel.geometry("980x800")
        wurzel.minsize(820, 640)
        wurzel.columnconfigure(0, weight=1)
        wurzel.rowconfigure(2, weight=3)
        wurzel.rowconfigure(4, weight=1)
        wurzel.rowconfigure(5, weight=1)
        self._stil = ttk.Style(wurzel)
        try:
            self._stil.theme_use("clam")   # nur dieses Thema erlaubt eigene Balkenfarben
        except tk.TclError:
            pass

        # 1. Kopf
        kopf = ttk.Frame(wurzel)
        kopf.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        kopf.columnconfigure(0, weight=1)
        self.kopf_var = tk.StringVar(value="Master-Schalter")
        ttk.Label(kopf, textvariable=self.kopf_var, font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky="w")
        self.automatik_var = tk.StringVar(value="Automatik: …")
        ttk.Label(kopf, textvariable=self.automatik_var).grid(row=0, column=1, sticky="e", padx=(8, 8))
        self.automatik_knopf = ttk.Button(kopf, text="Automatik umschalten", command=self.automatik_klick)
        self.automatik_knopf.grid(row=0, column=2, sticky="e")

        # 2. Kontingent
        kont = ttk.LabelFrame(wurzel, text="Kontingent (verbraucht)")
        kont.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        kont.columnconfigure(2, weight=1)
        self._balken: list[tuple[ttk.Label, ttk.Progressbar, tk.StringVar, tk.StringVar]] = []
        self._abo_info: list[tuple[tk.StringVar, tk.StringVar]] = []   # (gemessen-Zeile, Fehlertext) je Abo
        zeile = 0
        for abo in ("Claude", "Codex"):
            ttk.Label(kont, text=abo, font=("Segoe UI", 10, "bold")).grid(row=zeile, column=0, sticky="w",
                                                                           padx=(8, 4), pady=(6, 0))
            info = tk.StringVar()
            ttk.Label(kont, textvariable=info, foreground="#666666").grid(row=zeile, column=1, columnspan=3,
                                                                          sticky="w", padx=4, pady=(6, 0))
            zeile += 1
            for fenster in ("5h", "Woche"):
                name = ttk.Label(kont, text=fenster, width=6)
                name.grid(row=zeile, column=0, sticky="w", padx=(24, 4), pady=1)
                balken = ttk.Progressbar(kont, orient="horizontal", mode="determinate", maximum=100, length=320)
                balken.grid(row=zeile, column=1, columnspan=2, sticky="ew", padx=4, pady=1)
                text, reset = tk.StringVar(), tk.StringVar()
                ttk.Label(kont, textvariable=text, width=22).grid(row=zeile, column=3, sticky="w", padx=4)
                ttk.Label(kont, textvariable=reset).grid(row=zeile, column=4, sticky="w", padx=4)
                self._balken.append((name, balken, text, reset))
                zeile += 1
            fehler = tk.StringVar()
            ttk.Label(kont, textvariable=fehler, foreground=FEHLERFARBE, wraplength=900, justify="left").grid(
                row=zeile, column=0, columnspan=5, sticky="w", padx=(24, 4), pady=(0, 2))
            self._abo_info.append((info, fehler))
            zeile += 1

        # 3. Themen
        themen = ttk.LabelFrame(wurzel, text="Themen")
        themen.grid(row=2, column=0, sticky="nsew", padx=10, pady=4)
        themen.columnconfigure(0, weight=1)
        themen.rowconfigure(0, weight=1)
        self.themen_baum = ttk.Treeview(themen, columns=[s[0] for s in SPALTEN], show="headings", height=7,
                                        selectmode="browse")
        for spalte, titel, breite, strecken in SPALTEN:
            self.themen_baum.heading(spalte, text=titel)
            self.themen_baum.column(spalte, width=breite, stretch=strecken)
        self.themen_baum.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        regler = ttk.Scrollbar(themen, orient="vertical", command=self.themen_baum.yview)
        regler.grid(row=0, column=1, sticky="ns", pady=4)
        self.themen_baum.configure(yscrollcommand=regler.set)
        self.themen_baum.bind("<<TreeviewSelect>>", lambda _e: self._auswahl_geaendert())
        wahl = ttk.Frame(themen)
        wahl.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 6))
        self.wahl_var, self.master_var = tk.StringVar(value="Thema in der Tabelle wählen"), tk.StringVar()
        self.arbeitsweise_var = tk.StringVar()
        ttk.Label(wahl, textvariable=self.wahl_var).pack(side="left")
        ttk.Label(wahl, text="  Master:").pack(side="left")
        self.master_box = ttk.Combobox(wahl, textvariable=self.master_var, state="disabled",
                                       values=list(MASTER_ANZEIGE), width=18)
        self.master_box.pack(side="left", padx=6)
        self.master_box.bind("<<ComboboxSelected>>", lambda _e: self.master_klick())
        ttk.Label(wahl, text="  Arbeitsweise:").pack(side="left")
        self.arbeitsweise_box = ttk.Combobox(wahl, textvariable=self.arbeitsweise_var, state="disabled",
                                             values=list(ARBEITSWEISE_ANZEIGE), width=12)
        self.arbeitsweise_box.pack(side="left", padx=6)
        self.arbeitsweise_box.bind("<<ComboboxSelected>>", lambda _e: self.arbeitsweise_klick())

        # 4. Knöpfe
        knoepfe = ttk.Frame(wurzel)
        knoepfe.grid(row=3, column=0, sticky="ew", padx=10, pady=4)
        self.kontingent_knopf = ttk.Button(knoepfe, text="Alle nach Kontingent",
                                           command=lambda: self.alle_klick("kontingent"))
        self.zurueck_knopf = ttk.Button(knoepfe, text="Alle wie vorher", command=lambda: self.alle_klick("zurueck"))
        self.uebergabe_knopf = ttk.Button(knoepfe, text="Übergabe starten …", command=self.uebergabe_klick)
        self.aktualisieren_knopf = ttk.Button(knoepfe, text="Aktualisieren", command=self.laden_anstossen)
        for knopf in (self.kontingent_knopf, self.zurueck_knopf, self.uebergabe_knopf, self.aktualisieren_knopf):
            knopf.pack(side="left", padx=(0, 6))
        self.sperre_var = tk.StringVar()
        ttk.Label(knoepfe, textvariable=self.sperre_var, foreground=FEHLERFARBE).pack(side="left", padx=8)

        # 5. Bericht
        bericht = ttk.LabelFrame(wurzel, text="Bericht der letzten Sammelaktion")
        bericht.grid(row=4, column=0, sticky="nsew", padx=10, pady=4)
        bericht.columnconfigure(0, weight=1)
        bericht.rowconfigure(0, weight=1)
        self.bericht_feld = tk.Text(bericht, height=5, wrap="word", state="disabled")
        self.bericht_feld.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        # 6. Wartet worauf + Sitzungen
        unten = ttk.LabelFrame(wurzel, text="Wartet worauf · Sitzungen")
        unten.grid(row=5, column=0, sticky="nsew", padx=10, pady=4)
        unten.columnconfigure(0, weight=1)
        unten.rowconfigure(0, weight=1)
        self.unten_liste = tk.Listbox(unten, height=5, activestyle="none")
        self.unten_liste.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        # Fuß
        self.status_var, self.hinweis_var = tk.StringVar(), tk.StringVar()
        ttk.Label(wurzel, textvariable=self.status_var, wraplength=940, justify="left").grid(
            row=6, column=0, sticky="ew", padx=12, pady=(2, 0))
        ttk.Label(wurzel, textvariable=self.hinweis_var, wraplength=940, justify="left",
                  foreground="#666666").grid(row=7, column=0, sticky="ew", padx=12, pady=(0, 8))
        self._knoepfe_aktualisieren()

    # --- Hintergrund-Lesen -------------------------------------------------------------

    def laden_anstossen(self) -> None:
        """Eine Aufnahme im Hintergrund-Thread starten; läuft schon eine, passiert nichts."""
        if self._laedt:
            return
        self._laedt = True

        def lauf() -> None:
            try:
                snap = self._laden()
            except Exception as fehler:  # noqa: BLE001 - das Fenster darf nie wegen eines Lesefehlers enden
                snap = um.leer(f"Aktualisierung fehlgeschlagen ({type(fehler).__name__})")
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
                    if inhalt.bericht:
                        self._bericht_setzen(inhalt.bericht)
                    self._knoepfe_aktualisieren()
                    self.laden_anstossen()
        except queue.Empty:
            pass
        self.root.after(ABFRAGE_MS, self._abfragen)

    # --- Anzeige -----------------------------------------------------------------------------

    def _status(self, text: str, *, fehler: bool = False) -> None:
        self.status_var.set(("Fehler: " if fehler else "") + text)

    def _stil_fuer(self, farbe: str) -> str:
        """Ein ttk-Stil je Balkenfarbe (nur nach Bedarf angelegt)."""
        name = self._stile.get(farbe)
        if name is None:
            name = f"F{farbe.lstrip('#')}.Horizontal.TProgressbar"
            self._stil.configure(name, background=farbe, troughcolor=RINNE, bordercolor=RINNE,
                                 lightcolor=farbe, darkcolor=farbe)
            self._stile[farbe] = name
        return name

    def snapshot_anwenden(self, snap: um.Uebersicht) -> None:
        self._snap = snap
        self.kopf_var.set(f"Master-Schalter · {snap.zeit} · {snap.lage_text}")
        if snap.automatik is None:
            self.automatik_var.set("Automatik: unbekannt")
            self.automatik_knopf.configure(text="Automatik umschalten …")
        else:
            self.automatik_var.set(f"Automatik: {'an' if snap.automatik else 'aus'}")
            self.automatik_knopf.configure(text="Automatik ausschalten …" if snap.automatik else "Automatik einschalten …")
        for index, (info, fehler) in enumerate(self._abo_info):
            abo = snap.abos[index] if index < len(snap.abos) else None
            if abo is None:
                # Lesen gescheitert: alte Werte nicht stehen lassen, sondern ausdrücklich „unbekannt“ zeigen
                info.set("")
                fehler.set("keine aktuellen Messdaten (Aktualisierung fehlgeschlagen)")
            else:
                info.set(abo.gemessen)
                fehler.set("\n".join(um.abo_meldungen(abo)))
            for k in range(2):
                _, leiste, text, reset = self._balken[index * 2 + k]
                balken = abo.balken[k] if abo is not None and k < len(abo.balken) else None
                if balken is None:
                    leiste.configure(value=0, style=self._stil_fuer(um.GRAU))
                    text.set("unbekannt")
                    reset.set("")
                else:
                    leiste.configure(value=balken.prozent, style=self._stil_fuer(balken.farbe))
                    text.set(balken.text)
                    reset.set(balken.reset)
        self._tabelle("themen", self.themen_baum,
                      [(t.thema, t.thema, t.master, t.besitz, t.pruefer, t.ausfuehrer,
                        um.ARBEITSWEISE_TEXTE.get(t.arbeitsweise, t.arbeitsweise), t.auto) for t in snap.themen])
        zeilen = list(snap.wartet) or [kurz.WARTET]
        zeilen += list(snap.sitzungen) or ["Sitzungen: keine gemeldet"]
        if self._staende.get("unten") != zeilen:
            self._staende["unten"] = zeilen
            self.unten_liste.delete(0, "end")
            for z in zeilen:
                self.unten_liste.insert("end", z)
        self.sperre_var.set(snap.schreib_hinweis)
        self.hinweis_var.set(" · ".join(snap.hinweise))
        self._auswahl_geaendert()
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

    def _bericht_setzen(self, text: str) -> None:
        self.bericht_feld.configure(state="normal")
        self.bericht_feld.delete("1.0", "end")
        self.bericht_feld.insert("1.0", text)
        self.bericht_feld.configure(state="disabled")

    # --- Themenauswahl und Master -----------------------------------------------------------------

    def _gewaehltes_thema(self) -> um.ThemaZeile | None:
        auswahl = self.themen_baum.selection()
        if not auswahl or self._snap is None:
            return None
        return next((t for t in self._snap.themen if t.thema == auswahl[0]), None)

    def _auswahl_geaendert(self) -> None:
        """Aufklappmenüs auf den gespeicherten Master und die Arbeitsweise des gewählten Themas stellen."""
        zeile = self._gewaehltes_thema()
        if zeile is None:
            self.wahl_var.set("Thema in der Tabelle wählen")
            self.master_var.set("")
            self.arbeitsweise_var.set("")
        else:
            self.wahl_var.set(f"Thema {zeile.thema}")
            self.master_var.set(um.MASTER_TEXTE.get(zeile.master_wert, zeile.master_wert))
            self.arbeitsweise_var.set(um.ARBEITSWEISE_TEXTE.get(zeile.arbeitsweise, zeile.arbeitsweise))
        self._knoepfe_aktualisieren()

    def master_klick(self) -> None:
        zeile = self._gewaehltes_thema()
        index = self.master_box.current()
        if zeile is None or self._snap is None or not 0 <= index < len(um.MASTER_WERTE):
            self._auswahl_geaendert()
            return
        try:
            aktion = um.master_aktion(self._snap, zeile.thema, um.MASTER_WERTE[index])
        except um.AktionAbgelehnt as fehler:
            self._status(str(fehler), fehler=True)
            self._auswahl_geaendert()
            return
        self._ausfuehren(aktion)
        self._auswahl_geaendert()          # bei „Nein“ springt das Aufklappmenü auf den alten Wert zurück

    def arbeitsweise_klick(self) -> None:
        zeile = self._gewaehltes_thema()
        index = self.arbeitsweise_box.current()
        if zeile is None or self._snap is None or not 0 <= index < len(um.ARBEITSWEISE_WERTE):
            self._auswahl_geaendert()
            return
        try:
            aktion = um.arbeitsweise_aktion(self._snap, zeile.thema, um.ARBEITSWEISE_WERTE[index])
        except um.AktionAbgelehnt as fehler:
            self._status(str(fehler), fehler=True)
            self._auswahl_geaendert()
            return
        self._ausfuehren(aktion)
        self._auswahl_geaendert()          # bei „Nein“ springt das Aufklappmenü auf den alten Wert zurück

    # --- Aktionen -----------------------------------------------------------------------------------

    def _im_hintergrund(self, funktion: Callable[[], um.Ergebnis]) -> None:
        self._beschaeftigt = True
        self._knoepfe_aktualisieren()

        def lauf() -> None:
            try:
                ergebnis = funktion()
            except Exception as fehler:  # noqa: BLE001
                ergebnis = um.Ergebnis(False, f"Aktion fehlgeschlagen ({type(fehler).__name__})")
            self._queue.put(("ergebnis", ergebnis))

        threading.Thread(target=lauf, daemon=True).start()

    def _ausfuehren(self, aktion: um.Aktion) -> None:
        """Rückfrage im Tk-Thread; nur bei „Ja“ läuft die Aktion im Hintergrund."""
        if self._beschaeftigt:
            self._status("Bitte kurz warten – eine Aktion läuft noch.")
            return
        if not self._frage("Master-Schalter", aktion.frage):
            self._status("Nicht geändert – nichts verändert.")
            return
        self._status(f"{aktion.titel} läuft …")
        self._im_hintergrund(aktion.ausfuehren)

    def alle_klick(self, richtung: str) -> None:
        if self._snap is None:
            return
        try:
            aktion = um.alle_aktion(self._snap, richtung)
        except um.AktionAbgelehnt as fehler:
            self._status(str(fehler), fehler=True)
            return
        self._ausfuehren(aktion)

    def automatik_klick(self) -> None:
        if self._snap is None:
            return
        try:
            aktion = um.automatik_aktion(self._snap)
        except um.AktionAbgelehnt as fehler:
            self._status(str(fehler), fehler=True)
            return
        self._ausfuehren(aktion)

    def uebergabe_klick(self) -> None:
        if self._beschaeftigt:
            self._status("Bitte kurz warten – eine Aktion läuft noch.")
            return
        self._status("Wechselfenster wird geöffnet …")
        self._im_hintergrund(self._uebergabe)

    def _knoepfe_aktualisieren(self) -> None:
        frei = not self._beschaeftigt
        schreiben = self._snap is not None and self._snap.schreiben

        def zustand_von(an: bool) -> str:
            return "normal" if an else "disabled"

        self.kontingent_knopf.configure(state=zustand_von(frei and schreiben))
        self.zurueck_knopf.configure(state=zustand_von(frei and schreiben))
        self.uebergabe_knopf.configure(state=zustand_von(frei))
        self.automatik_knopf.configure(state=zustand_von(frei and self._snap is not None
                                                         and self._snap.automatik is not None))
        wahl_frei = frei and schreiben and self._gewaehltes_thema() is not None
        self.master_box.configure(state="readonly" if wahl_frei else "disabled")
        self.arbeitsweise_box.configure(state="readonly" if wahl_frei else "disabled")


def main() -> int:
    """Genau ein Fenster: eine zweite Instanz beendet sich still (Exit 0)."""
    with zustand.instanz_sperre(INSTANZ) as frei:
        if not frei:
            print("Die Übersicht läuft bereits – nichts neu gestartet.", file=sys.stderr)
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
