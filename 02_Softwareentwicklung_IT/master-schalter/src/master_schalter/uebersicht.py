"""Übersichtsfenster des Master-Schalters mit lokaler Themenvorauswahl.

Start: `python -m master_schalter.uebersicht` (ohne Konsole: `pythonw.exe -m master_schalter.uebersicht`); die Leiste
öffnet es per Linksklick auf das Taskleistensymbol als eigenen Prozess.

* **Nur eine Instanz:** eine nicht blockierende Sperre `uebersicht.lock` im Datenordner
  (`zustand.instanz_sperre`). Läuft schon ein Fenster, beendet sich der zweite Start still (Hinweis auf stderr,
  Exit 0).
* **Aktualisierung alle 5 s:** `uebersicht_modell.aufnehmen()` läuft im Hintergrund-Thread, das Ergebnis geht über
  eine Warteschlange an den Tk-Thread. Dasselbe gilt für alle Aktionen: nie Dateizugriff oder Wartezeit im
  Tk-Thread, nie Tk-Aufruf aus einem anderen Thread.
* **Themenvorauswahl:** sechs Dropdowns pro Themenzeile ändern nur den zentralen lokalen Entwurf. „Änderungen prüfen …“ zeigt
  Werte und Konflikte; „Zurücksetzen“ verwirft sie. Die produktive Übernahme bleibt bis zur sicheren Übergabeanbindung gesperrt.
* **Hintergrundaktionen:** Sammelwechsel und der Hauptschalter Automatik verwenden weiterhin geprüfte Aktionen aus
  `uebersicht_modell.py`; vor diesen tatsächlichen Aktionen fragt `dialog.frage` mit Standard **Nein**.
* **Nur Anzeige:** Findet die Aufnahme keinen echten Hauptarbeitsbaum, sind die Schreibknöpfe gesperrt.
* **Aussehen:** dunkel, flach, Farben und Stile an einer Stelle (`uebersicht_stil.py`, nur Bordmittel).
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
from . import uebersicht_stil as st
from .uebersicht_entwurf import EntwurfsVerwaltung, EntwurfFehler
from .uebersicht_tabelle import ThemenTabelle

INSTANZ = "uebersicht"
TAKT_MS = 5000            # alle 5 s frisch lesen
ABFRAGE_MS = 150          # Warteschlange des Hintergrund-Threads leeren
TITEL = "Master-Schalter – Übersicht"
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
        self._entwuerfe = EntwurfsVerwaltung()
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

    def _karte(self, eltern: tk.Misc, titel: str | None = None) -> ttk.Frame:
        """Eine Karte (hellere Fläche). Mit Titel steht dieser in Zeile 0, der Inhalt beginnt in Zeile 1."""
        karte = ttk.Frame(eltern, style=st.KARTE, padding=st.ABSTAND)
        karte.columnconfigure(0, weight=1)
        if titel:
            ttk.Label(karte, text=titel, style=st.KARTE_TITEL).grid(row=0, column=0, sticky="w", pady=(0, 6))
        return karte

    def _bauen(self) -> None:
        wurzel = self.root
        wurzel.title(TITEL)
        wurzel.geometry("1240x900")
        wurzel.minsize(1000, 700)
        self._stil, self._schrift = st.anwenden(wurzel)
        feld = dict(background=st.FLAECHE, foreground=st.TEXT, relief="flat", highlightthickness=0,
                    font=(self._schrift, 10))
        wurzel.columnconfigure(0, weight=1)
        rand = st.ABSTAND_GROSS
        wurzel.rowconfigure(2, weight=1)

        # 1. Kopf: Titel · Uhrzeit · Lage-Pille · … · Hauptschalter Automatik · Aktualisieren
        kopf = ttk.Frame(wurzel, style=st.KOPF, padding=(st.ABSTAND, 10))
        kopf.grid(row=0, column=0, sticky="ew", padx=rand, pady=(rand, 6))
        kopf.columnconfigure(3, weight=1)
        ttk.Label(kopf, text="Master-Schalter", style=st.TITEL).grid(row=0, column=0, sticky="w")
        self.zeit_var, self.lage_var, self.lage_grund_var = tk.StringVar(), tk.StringVar(value="Lage ?"), tk.StringVar()
        ttk.Label(kopf, textvariable=self.zeit_var, style=st.KARTE_GEDAEMPFT).grid(row=0, column=1, padx=(12, 8))
        self.lage_pille = ttk.Label(kopf, textvariable=self.lage_var, style=st.PILLE_UNBEKANNT)
        self.lage_pille.grid(row=0, column=2, padx=(0, 8))
        self.automatik_var = tk.StringVar(value="Automatik: …")
        ttk.Label(kopf, textvariable=self.automatik_var, style=st.KARTE_LABEL).grid(row=0, column=4, padx=(8, 8))
        self.automatik_knopf = ttk.Button(kopf, text="Automatik umschalten", style=st.KNOPF, command=self.automatik_klick)
        self.automatik_knopf.grid(row=0, column=5, padx=(0, 8))
        self.aktualisieren_knopf = ttk.Button(kopf, text="↻ Aktualisieren", style=st.KNOPF_KLEIN,
                                              command=self.laden_anstossen)
        self.aktualisieren_knopf.grid(row=0, column=6)
        ttk.Label(kopf, textvariable=self.lage_grund_var, style=st.KARTE_GEDAEMPFT, wraplength=1100,
                  justify="left").grid(row=1, column=0, columnspan=7, sticky="w")

        # 2. Kontingent: je Abo eine Karte
        kont = ttk.Frame(wurzel)
        kont.grid(row=1, column=0, sticky="ew", padx=rand, pady=6)
        self._balken: list[tuple[ttk.Label, ttk.Progressbar, tk.StringVar, tk.StringVar]] = []
        self._abo_info: list[tuple[tk.StringVar, tk.StringVar]] = []   # (gemessen-Zeile, Fehlertext) je Abo
        for spalte, (abo, farbe) in enumerate((("Claude", st.AKZENT_CLAUDE), ("Codex", st.AKZENT_CODEX))):
            kont.columnconfigure(spalte, weight=1, uniform="abo")
            karte = self._karte(kont)
            karte.grid(row=0, column=spalte, sticky="nsew", padx=(0, 6) if spalte == 0 else (6, 0))
            karte.columnconfigure(0, weight=0)
            karte.columnconfigure(1, weight=1)
            ttk.Label(karte, text=f"●  {abo}", style=st.KARTE_TITEL, foreground=farbe).grid(row=0, column=0, sticky="w")
            info = tk.StringVar()
            ttk.Label(karte, textvariable=info, style=st.KARTE_GEDAEMPFT).grid(row=0, column=1, columnspan=2, sticky="e")
            zeile = 1
            for fenster in ("5h", "Woche"):
                name = ttk.Label(karte, text=fenster, width=6, style=st.KARTE_LABEL)
                name.grid(row=zeile, column=0, sticky="w", pady=(8, 0))
                balken = ttk.Progressbar(karte, orient="horizontal", mode="determinate", maximum=100, length=200,
                                         style=self._stil_fuer(st.GRAU))
                balken.grid(row=zeile, column=1, sticky="ew", padx=8, pady=(8, 0))
                text, reset = tk.StringVar(), tk.StringVar()
                ttk.Label(karte, textvariable=text, width=19, style=st.KARTE_LABEL).grid(row=zeile, column=2, sticky="w",
                                                                                         pady=(8, 0))
                ttk.Label(karte, textvariable=reset, style=st.KARTE_GEDAEMPFT).grid(row=zeile + 1, column=1, columnspan=2,
                                                                                    sticky="w", padx=8)
                self._balken.append((name, balken, text, reset))
                zeile += 2
            fehler = tk.StringVar()
            ttk.Label(karte, textvariable=fehler, style=st.KARTE_FEHLER, wraplength=480, justify="left").grid(
                row=zeile, column=0, columnspan=3, sticky="w", pady=(6, 0))
            self._abo_info.append((info, fehler))

        # 3. Themen und Bericht/Sitzungen: Höhe über die Trennkante verteilbar
        paned = ttk.Panedwindow(wurzel, orient="vertical")
        paned.grid(row=2, column=0, sticky="nsew", padx=rand, pady=6)
        themen = self._karte(paned, "Themen – Einstellungen direkt in jeder Zeile")
        themen.rowconfigure(2, weight=1)
        themen.columnconfigure(0, weight=1)
        entwurf_leiste = ttk.Frame(themen)
        entwurf_leiste.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self.entwurf_anzahl_var = tk.StringVar(value="Keine offenen Entwürfe")
        ttk.Label(entwurf_leiste, textvariable=self.entwurf_anzahl_var, style=st.KARTE_LABEL).pack(side="left", padx=(0, 10))
        self.entwurf_pruefen_knopf = ttk.Button(entwurf_leiste, text="Änderungen prüfen …", style=st.KNOPF,
                                                 command=self.entwurf_pruefen)
        self.entwurf_pruefen_knopf.pack(side="left", padx=(0, 6))
        self.entwurf_zuruecksetzen_knopf = ttk.Button(entwurf_leiste, text="Zurücksetzen", style=st.KNOPF,
                                                      command=self.entwurf_zuruecksetzen)
        self.entwurf_zuruecksetzen_knopf.pack(side="left", padx=(0, 10))
        self.entwurf_uebernehmen_knopf = ttk.Button(entwurf_leiste, text="Übernehmen …",
                                                     state="disabled", style=st.KNOPF,
                                                     command=self.entwurf_uebernehmen)
        self.entwurf_uebernehmen_knopf.pack(side="left")
        self.themen_tabelle = ThemenTabelle(themen, aendern=self._themenwert_aendern)
        self.themen_tabelle.grid(row=2, column=0, sticky="nsew")
        paned.add(themen, weight=4)
        unten_pane = ttk.Frame(paned)
        unten_pane.columnconfigure(0, weight=1)
        unten_pane.rowconfigure(1, weight=1)
        paned.add(unten_pane, weight=2)

        # 4. Knöpfe
        knoepfe = ttk.Frame(unten_pane)
        knoepfe.grid(row=0, column=0, sticky="ew", pady=(4, 6))
        self.kontingent_knopf = ttk.Button(knoepfe, text="Alle nach Kontingent", style=st.KNOPF_AKZENT,
                                           command=lambda: self.alle_klick("kontingent"))
        self.zurueck_knopf = ttk.Button(knoepfe, text="Alle wie vorher", style=st.KNOPF,
                                        command=lambda: self.alle_klick("zurueck"))
        self.uebergabe_knopf = ttk.Button(knoepfe, text="Übergabe starten …", style=st.KNOPF, command=self.uebergabe_klick)
        for knopf in (self.kontingent_knopf, self.zurueck_knopf, self.uebergabe_knopf):
            knopf.pack(side="left", padx=(0, 8))
        self.sperre_var = tk.StringVar()
        ttk.Label(knoepfe, textvariable=self.sperre_var, style=st.LABEL_FEHLER).pack(side="left", padx=8)

        # 5. Bericht
        bericht = self._karte(unten_pane, "Bericht der letzten Sammelaktion")
        bericht.grid(row=1, column=0, sticky="nsew", pady=(0, 4))
        bericht.rowconfigure(1, weight=1)
        self.bericht_feld = tk.Text(bericht, height=4, wrap="word", state="disabled", **feld)
        self.bericht_feld.grid(row=1, column=0, sticky="nsew")

        # 6. Wartet worauf + Sitzungen
        unten = self._karte(unten_pane, "Wartet worauf · Sitzungen")
        unten.grid(row=2, column=0, sticky="nsew", pady=(4, 0))
        unten.rowconfigure(1, weight=1)
        self.unten_liste = tk.Listbox(unten, height=4, activestyle="none", selectbackground=st.FLAECHE2,
                                      selectforeground=st.TEXT, **feld)
        self.unten_liste.grid(row=1, column=0, sticky="nsew")

        # Fuß
        self.status_var, self.hinweis_var = tk.StringVar(), tk.StringVar()
        ttk.Label(wurzel, textvariable=self.status_var, wraplength=1180, justify="left", style=st.LABEL).grid(
            row=7, column=0, sticky="ew", padx=rand + 2, pady=(4, 0))
        ttk.Label(wurzel, textvariable=self.hinweis_var, wraplength=1180, justify="left",
                  style=st.LABEL_GEDAEMPFT).grid(row=8, column=0, sticky="ew", padx=rand + 2, pady=(0, rand))
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
        """Ein ttk-Stil je Balkenfarbe (nur nach Bedarf angelegt): schmal, flach, ohne 3D-Rand."""
        name = self._stile.get(farbe)
        if name is None:
            name = st.balken_stil(self._stil, farbe)
            self._stile[farbe] = name
        return name

    def snapshot_anwenden(self, snap: um.Uebersicht) -> None:
        self._snap = snap
        self.zeit_var.set(snap.zeit)
        lage_kurz, _, grund = snap.lage_text.partition(" – ")
        self.lage_var.set(lage_kurz)
        self.lage_grund_var.set(grund)
        self.lage_pille.configure(style=st.PILLE if snap.lage else st.PILLE_UNBEKANNT)
        if snap.automatik is None:
            self.automatik_var.set("Automatik: unbekannt")
            self.automatik_knopf.configure(text="Automatik umschalten …", style=st.KNOPF)
        else:
            self.automatik_var.set(f"Automatik: {'an' if snap.automatik else 'aus'}")
            self.automatik_knopf.configure(text="Automatik ausschalten …" if snap.automatik else "Automatik einschalten …",
                                           style=st.KNOPF_AKZENT if snap.automatik else st.KNOPF)
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
        self._entwuerfe.aktualisieren(snap)
        self.themen_tabelle.aktualisieren(snap, entwuerfe=self._entwuerfe, beschaeftigt=self._beschaeftigt)
        zeilen = list(snap.wartet) or [kurz.WARTET]
        zeilen += list(snap.sitzungen) or ["Sitzungen: keine gemeldet"]
        if self._staende.get("unten") != zeilen:
            self._staende["unten"] = zeilen
            self.unten_liste.delete(0, "end")
            for z in zeilen:
                self.unten_liste.insert("end", z)
        self.sperre_var.set(snap.schreib_hinweis)
        self.hinweis_var.set(" · ".join(snap.hinweise))
        self._entwurf_anzahl_aktualisieren()
        self._knoepfe_aktualisieren()

    def _bericht_setzen(self, text: str) -> None:
        self.bericht_feld.configure(state="normal")
        self.bericht_feld.delete("1.0", "end")
        self.bericht_feld.insert("1.0", text)
        self.bericht_feld.configure(state="disabled")

    # --- Themenauswahl und Auswahllisten ------------------------------------------------------------

    def _themenwert_aendern(self, thema: str, feld: str, wert: str | bool | None) -> None:
        if self._snap is None or self._beschaeftigt:
            return
        try:
            self._entwuerfe.waehlen(thema, feld, wert)
        except EntwurfFehler as fehler:
            self._status(str(fehler), fehler=True)
            erfolgreich = False
        else:
            erfolgreich = True
        self.themen_tabelle.aktualisieren(self._snap, entwuerfe=self._entwuerfe,
                                          beschaeftigt=self._beschaeftigt)
        self._entwurf_anzahl_aktualisieren()
        if erfolgreich:
            self._status(f"Entwurf für {thema} ({feld}) vorgemerkt – noch nicht übernommen.")

    def _entwurf_anzahl_aktualisieren(self) -> None:
        aenderungen = self._entwuerfe.aenderungen()
        anzahl = len(aenderungen)
        self.entwurf_anzahl_var.set("Keine offenen Entwürfe" if anzahl == 0
                                    else f"{anzahl} offene Änderung{'en' if anzahl != 1 else ''}")
        zustand = "normal" if anzahl and not self._beschaeftigt else "disabled"
        self.entwurf_pruefen_knopf.configure(state=zustand)
        self.entwurf_zuruecksetzen_knopf.configure(state=zustand)
        uebernehmbar = (
            anzahl > 0
            and not self._beschaeftigt
            and self._snap is not None
            and self._snap.schreiben
            and self._snap.repo is not None
            and getattr(self._snap, "wechsel_pruefbar", False)
            and not any(a.konflikt or a.hinweis or a.thema in getattr(self._snap, "wechsel_themen", ())
                        for a in aenderungen)
        )
        self.entwurf_uebernehmen_knopf.configure(
            state="normal" if uebernehmbar else "disabled",
            style=st.KNOPF_AKZENT if uebernehmbar else st.KNOPF,
        )

    def entwurf_uebernehmen(self) -> None:
        if self._snap is None:
            return
        try:
            aktion = um.entwurf_uebernehmen_aktion(
                self._snap, self._entwuerfe.aenderungen(),
                nach_thema=self._entwuerfe.zuruecksetzen,
            )
        except um.AktionAbgelehnt as fehler:
            self._status(str(fehler), fehler=True)
            return
        self._ausfuehren(aktion)

    def entwurf_zuruecksetzen(self) -> None:
        self._entwuerfe.zuruecksetzen()
        if self._snap is not None:
            self.themen_tabelle.aktualisieren(self._snap, entwuerfe=self._entwuerfe,
                                              beschaeftigt=self._beschaeftigt)
        self._entwurf_anzahl_aktualisieren()
        self._status("Lokale Entwürfe zurückgesetzt – gespeicherte Einstellungen unverändert.")

    def entwurf_pruefen(self) -> None:
        """Änderungen zeigen. Es gibt absichtlich noch keinen produktiven Übernahmeweg."""
        aenderungen = self._entwuerfe.aenderungen()
        if not aenderungen:
            self._status("Keine offenen Entwürfe.")
            return
        fenster = tk.Toplevel(self.root)
        fenster.title("Änderungen prüfen")
        fenster.transient(self.root)
        fenster.minsize(600, 360)
        rahmen = ttk.Frame(fenster, padding=12)
        rahmen.pack(fill="both", expand=True)
        ttk.Label(rahmen, text="Vorgemerkte Änderungen – noch nichts gespeichert",
                  style=st.KARTE_TITEL).pack(anchor="w", pady=(0, 8))
        textfeld = tk.Text(rahmen, wrap="word", state="normal", height=14)
        textfeld.pack(fill="both", expand=True)
        for a in aenderungen:
            zeile = f"{a.thema} · {a.feld}: {a.alt!r} → {a.neu!r}"
            if a.konflikt:
                zeile += "\n  Konflikt: " + (a.hinweis or "Thema geändert oder entfernt")
            elif a.hinweis:
                zeile += "\n  Hinweis: " + a.hinweis
            textfeld.insert("end", zeile + "\n\n")
        textfeld.configure(state="disabled")
        unten = ttk.Frame(rahmen)
        unten.pack(fill="x", pady=(8, 0))
        ttk.Button(unten, text="Schließen", style=st.KNOPF, command=fenster.destroy).pack(side="right")
        ttk.Label(unten, text="Sichere Übernahme noch nicht angebunden", style=st.KARTE_GEDAEMPFT).pack(side="left")
        self.root.wait_window(fenster)

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
        if self._snap is not None:
            self.themen_tabelle.aktualisieren(self._snap, entwuerfe=self._entwuerfe,
                                              beschaeftigt=not frei or not schreiben)
            self._entwurf_anzahl_aktualisieren()


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
