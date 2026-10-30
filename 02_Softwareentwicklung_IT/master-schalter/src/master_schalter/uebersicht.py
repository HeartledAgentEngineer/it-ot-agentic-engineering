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
        for spalte, (abo, farbe) in enumerate((("Claude", st.AKZENT_CLAUDE), ("Codex", st.AKZENT_CODEX), ("Gemini", st.AKZENT_GEMINI))):
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

        # 3. Themen: Vollbild-Tabelle ohne störenden unteren Bereich
        themen = self._karte(wurzel, "Themen – Einstellungen direkt in jeder Zeile")
        themen.grid(row=2, column=0, sticky="nsew", padx=rand, pady=6)
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
                                                     state="disabled", style=st.KNOPF_AKZENT,
                                                     command=self.entwurf_uebernehmen)
        # Oberes "Übernehmen ..." ist im modernen UI entfernt (Steuerung pro Zeile via Übergabe ...):
        self.thema_anlegen_knopf = ttk.Button(entwurf_leiste, text="+ Thema anlegen …", style=st.KNOPF,
                                              command=self.thema_anlegen_dialog)
        self.thema_anlegen_knopf.pack(side="left", padx=(0, 6))
        self.matrix_knopf = ttk.Button(entwurf_leiste, text="⚙ Matrix & Workflow …", style=st.KNOPF,
                                       command=self.matrix_konfigurieren_dialog)
        self.matrix_knopf.pack(side="left", padx=(0, 6))
        self.limits_knopf = ttk.Button(entwurf_leiste, text="📊 Limits & Verbräuche …", style=st.KNOPF,
                                       command=self.limits_dialog_oeffnen)
        self.limits_knopf.pack(side="left")
        self.themen_tabelle = ThemenTabelle(themen, aendern=self._themenwert_aendern,
                                           uebergabe_anfordern=self.uebergabe_dialog_oeffnen)
        self.themen_tabelle.grid(row=2, column=0, sticky="nsew")
        unten_pane = ttk.Frame(wurzel)
        unten_pane.columnconfigure(0, weight=1)
        unten_pane.rowconfigure(1, weight=1)

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
                info_text = abo.gemessen
                if abo.name == "Gemini" and abo.gemessen and "Argon" not in info_text:
                    info_text = f"{abo.gemessen} · Argon: OK"
                info.set(info_text)
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



    def thema_anlegen_dialog(self) -> None:
        """Dialog zum Anlegen eines neuen Themas mit automatischen Workflow-Vorgaben und Master-Rotation."""
        top = tk.Toplevel(self.root)
        top.title("Neues Thema anlegen")
        top.configure(background=st.GRUND)
        top.transient(self.root)
        top.resizable(False, False)
        top.grab_set()

        frame = ttk.Frame(top, padding=st.ABSTAND_GROSS, style=st.KARTE)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Neues Thema anlegen", style=st.TITEL).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        # Automatische Chat-Erkennung (Antigravity, Codex etc.)
        try:
            from . import chat_discovery
            bestehend = {t.thema for t in getattr(self._snap, "themen", ())} if hasattr(self, "_snap") and self._snap else set()
            vorschlaege = chat_discovery.neue_themen_vorschlaege(bestehend)
        except Exception:
            vorschlaege = []

        zeile_nr = 1
        name_var = tk.StringVar(value="")
        master_var = tk.StringVar(value="Antigravity")

        if vorschlaege:
            ttk.Label(frame, text="Erkannte neue Chats:", style=st.KARTE_TITEL).grid(row=zeile_nr, column=0, sticky="w", pady=4)
            chat_labels = [f"[{v.quelle}] {v.titel}" for v in vorschlaege]
            chat_var = tk.StringVar(value=chat_labels[0])
            chat_box = ttk.Combobox(frame, textvariable=chat_var, style=st.KOMBI, state="readonly", values=chat_labels, width=32)
            chat_box.grid(row=zeile_nr, column=1, sticky="ew", pady=4, padx=(8, 0))

            def _chat_auswaehlen(event=None):
                idx = chat_box.current()
                if 0 <= idx < len(vorschlaege):
                    v = vorschlaege[idx]
                    name_var.set(v.thema)
                    master_var.set(v.quelle)

            chat_box.bind("<<ComboboxSelected>>", _chat_auswaehlen)
            _chat_auswaehlen()
            zeile_nr += 1

        ttk.Label(frame, text="Themaname:", style=st.KARTE_TITEL).grid(row=zeile_nr, column=0, sticky="w", pady=4)
        name_entry = ttk.Entry(frame, textvariable=name_var, width=30)
        name_entry.grid(row=zeile_nr, column=1, sticky="ew", pady=4, padx=(8, 0))
        name_entry.focus()
        zeile_nr += 1

        # Erst-Master (Standard dort wo das Thema entsteht: Antigravity)
        ttk.Label(frame, text="Erst-Master:", style=st.KARTE_TITEL).grid(row=zeile_nr, column=0, sticky="w", pady=4)
        master_box = ttk.Combobox(frame, textvariable=master_var, style=st.KOMBI, state="readonly",
                                  values=("Antigravity", "Codex", "Hermes", "Claude", "Nach Kontingent"))
        master_box.grid(row=zeile_nr, column=1, sticky="ew", pady=4, padx=(8, 0))
        zeile_nr += 1

        # Master-Rotation
        ttk.Label(frame, text="Master-Rotation:", style=st.KARTE_TITEL).grid(row=zeile_nr, column=0, sticky="w", pady=4)
        rotation_var = tk.StringVar(value="Antigravity ➔ Hermes ➔ Codex")
        rot_box = ttk.Combobox(frame, textvariable=rotation_var, style=st.KOMBI, state="readonly",
                               values=("Antigravity ➔ Hermes ➔ Codex",
                                       "Codex ➔ Antigravity ➔ Hermes",
                                       "Hermes ➔ Antigravity ➔ Codex",
                                       "Claude ➔ Codex ➔ Antigravity",
                                       "Standard (nach globalem Kontingent)"))
        rot_box.grid(row=zeile_nr, column=1, sticky="ew", pady=4, padx=(8, 0))
        zeile_nr += 1

        # Prüfer
        ttk.Label(frame, text="Prüfer:", style=st.KARTE_TITEL).grid(row=zeile_nr, column=0, sticky="w", pady=4)
        pruefer_var = tk.StringVar(value="Automatisch")
        pruefer_box = ttk.Combobox(frame, textvariable=pruefer_var, style=st.KOMBI, state="readonly",
                                   values=("Automatisch", "Codex", "Hermes"))
        pruefer_box.grid(row=zeile_nr, column=1, sticky="ew", pady=4, padx=(8, 0))
        zeile_nr += 1

        # Ausführer
        ttk.Label(frame, text="Ausführer:", style=st.KARTE_TITEL).grid(row=zeile_nr, column=0, sticky="w", pady=4)
        ausf_var = tk.StringVar(value="Workflow")
        ausf_box = ttk.Combobox(frame, textvariable=ausf_var, style=st.KOMBI, state="readonly",
                                values=("Workflow", "Antigravity", "Codex", "Hermes", "Claude"))
        ausf_box.grid(row=zeile_nr, column=1, sticky="ew", pady=4, padx=(8, 0))
        zeile_nr += 1

        # Arbeitsweise
        ttk.Label(frame, text="Arbeitsweise:", style=st.KARTE_TITEL).grid(row=zeile_nr, column=0, sticky="w", pady=4)
        arb_var = tk.StringVar(value="Protokoll")
        arb_box = ttk.Combobox(frame, textvariable=arb_var, style=st.KOMBI, state="readonly",
                               values=("Protokoll", "Direkt", "Vibe"))
        arb_box.grid(row=zeile_nr, column=1, sticky="ew", pady=4, padx=(8, 0))
        zeile_nr += 1

        fehler_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=fehler_var, style=st.KARTE_FEHLER).grid(row=zeile_nr, column=0, columnspan=2, sticky="w", pady=(6, 4))
        zeile_nr += 1

        knopfreihe = ttk.Frame(frame, style=st.KARTE)
        knopfreihe.grid(row=zeile_nr, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        def anlegen() -> None:
            thema = name_var.get().strip()
            if not thema:
                fehler_var.set("Bitte einen Themanamen eingeben.")
                return
            try:
                from . import paare, modi, pruefer_wahl
                paare.thema_pruefen(thema)
            except Exception as e:
                fehler_var.set(f"Themaname unzulässig ({type(e).__name__})")
                return

            # Fachliche Werte
            master_map = {"Antigravity": "agy", "Codex": "codex", "Hermes": "hermes", "Claude": "claude", "Nach Kontingent": "kontingent"}
            m_wert = master_map.get(master_var.get(), "kontingent")
            p_wert = "automatisch" if pruefer_var.get() == "Automatisch" else pruefer_var.get().lower()
            w_wert = "workflow" if ausf_var.get() == "Workflow" else ausf_var.get().lower()
            vibe_wert = arb_var.get() == "Vibe"

            try:
                um.thema_anlegen(thema, master=m_wert, pruefer=p_wert, worker=w_wert, vibe=vibe_wert)
            except Exception as e:
                fehler_var.set(f"Fehler beim Anlegen ({type(e).__name__})")
                return

            top.destroy()
            self._status(f"Thema {thema} erfolgreich angelegt.")
            self.laden_anstossen()

        ttk.Button(knopfreihe, text="Thema anlegen", style=st.KNOPF_AKZENT, command=anlegen).pack(side="left", padx=(0, 8))
        ttk.Button(knopfreihe, text="Abbrechen", style=st.KNOPF, command=top.destroy).pack(side="right")



    def limits_dialog_oeffnen(self) -> None:
        """Modaler Dialog zur Anzeige aller Limits, Zeitfenster und Verbräuche (Gemini/Argon, ChatGPT, Claude, OpenRouter)."""
        from . import signale
        limits = signale.alle_limits_lesen()

        top = tk.Toplevel(self.root)
        top.title("Multi-Plattform Limits & Verbräuche")
        top.configure(background=st.GRUND)
        top.transient(self.root)
        top.resizable(True, True)
        top.geometry("740x600")
        top.grab_set()

        frame = ttk.Frame(top, padding=st.ABSTAND_GROSS, style=st.KARTE)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Kontingente & Nutzungslimits aller KI-Plattformen", style=st.TITEL).pack(anchor="w", pady=(0, 10))

        tabs_frame = ttk.Frame(frame, style=st.KARTE)
        tabs_frame.pack(fill="both", expand=True, pady=(0, 10))

        farben = {
            "Claude": st.AKZENT_CLAUDE,
            "Codex": st.AKZENT_CODEX,
            "Gemini": st.AKZENT_GEMINI,
            "OpenRouter": st.AKZENT_PRIMAR,
        }

        for platt in limits:
            karte = ttk.Frame(tabs_frame, style=st.KARTE, padding=st.ABSTAND)
            karte.pack(fill="x", pady=4)
            farbe = farben.get(platt.anbieter, st.TEXT)
            ttk.Label(karte, text=f"●  {platt.titel}", style=st.KARTE_TITEL, foreground=farbe).pack(anchor="w")

            grid_f = ttk.Frame(karte, style=st.KARTE)
            grid_f.pack(fill="x", padx=12, pady=4)
            for i, (k, v) in enumerate(platt.details.items()):
                ttk.Label(grid_f, text=f"{k}:", style=st.KARTE_LABEL, width=20).grid(row=i, column=0, sticky="w", pady=1)
                ttk.Label(grid_f, text=v, style=st.KARTE_GEDAEMPFT).grid(row=i, column=1, sticky="w", pady=1)

            if platt.fehler:
                ttk.Label(karte, text=f"Hinweis: {platt.fehler}", style=st.KARTE_FEHLER).pack(anchor="w", padx=12, pady=(2, 0))

        knopfreihe = ttk.Frame(frame, style=st.KARTE)
        knopfreihe.pack(fill="x", pady=(8, 0))
        ttk.Button(knopfreihe, text="Schließen", style=st.KNOPF_AKZENT, command=top.destroy).pack(side="right")

    def matrix_konfigurieren_dialog(self) -> None:
        """Konfigurationsdialog fuer die Workflow- und Kaskaden-Matrix (Nach Kontingent)."""
        from . import matrix_konfiguration as mk
        cfg = mk.matrix_lesen()

        top = tk.Toplevel(self.root)
        top.title("Workflow- & Kaskaden-Matrix (Nach Kontingent)")
        top.configure(background=st.GRUND)
        top.transient(self.root)
        top.resizable(True, True)
        top.geometry("820x640")
        top.grab_set()

        frame = ttk.Frame(top, padding=st.ABSTAND_GROSS, style=st.KARTE)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Kaskaden-Matrix & Workflow-Profile (AGENTS.md)", style=st.TITEL).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        # 1. Preset-Auswahl oben
        ttk.Label(frame, text="Matrix-Vorlage / Preset:", style=st.KARTE_TITEL).grid(row=1, column=0, sticky="w", padx=4, pady=6)
        preset_namen = list(mk.PRESETS.keys()) + ["Benutzerdefiniert"]
        aktuelles_preset = cfg.get("preset", mk.DEFAULT_PRESET_NAME)
        if aktuelles_preset not in preset_namen:
            aktuelles_preset = "Benutzerdefiniert"
        preset_var = tk.StringVar(value=aktuelles_preset)
        preset_box = ttk.Combobox(frame, textvariable=preset_var, style=st.KOMBI, state="readonly",
                                  values=preset_namen, width=32)
        preset_box.grid(row=1, column=1, columnspan=2, sticky="w", padx=4, pady=6)

        # Tabellen-Ueberschriften
        ttk.Label(frame, text="Lage", style=st.KARTE_TITEL).grid(row=2, column=0, sticky="w", padx=4, pady=6)
        ttk.Label(frame, text="Thinker (Master)", style=st.KARTE_TITEL).grid(row=2, column=1, sticky="w", padx=4, pady=6)
        ttk.Label(frame, text="Reviewer (Pruefer)", style=st.KARTE_TITEL).grid(row=2, column=2, sticky="w", padx=4, pady=6)
        ttk.Label(frame, text="Worker (Ausfuehrer)", style=st.KARTE_TITEL).grid(row=2, column=3, sticky="w", padx=4, pady=6)

        lagen_keys = [("lage_1", "Lage 1 (Beide Abos frei)"),
                      ("lage_2a", "Lage 2A (Claude im Limit)"),
                      ("lage_2b", "Lage 2B (ChatGPT im Limit)"),
                      ("lage_3", "Lage 3 (Beide im Limit)")]

        widgets = {}
        for r, (lkey, lname) in enumerate(lagen_keys, start=3):
            l_cfg = cfg.get(lkey, {})
            ttk.Label(frame, text=lname, style=st.KARTE_LABEL).grid(row=r, column=0, sticky="w", padx=4, pady=4)

            # Master Combobox
            m_var = tk.StringVar(value=l_cfg.get("master", "Claude Opus 5.5"))
            m_box = ttk.Combobox(frame, textvariable=m_var, style=st.KOMBI, state="readonly",
                                 values=mk.VERFUEGBARE_MASTER, width=22)
            m_box.grid(row=r, column=1, sticky="ew", padx=4, pady=4)

            # Pruefer Combobox
            p_var = tk.StringVar(value=l_cfg.get("pruefer", "GPT-6 Sol"))
            p_box = ttk.Combobox(frame, textvariable=p_var, style=st.KOMBI, state="readonly",
                                 values=mk.VERFUEGBARE_PRUEFER, width=22)
            p_box.grid(row=r, column=2, sticky="ew", padx=4, pady=4)

            # Worker Combobox
            w_var = tk.StringVar(value=l_cfg.get("worker", "GPT-6 Luna"))
            w_box = ttk.Combobox(frame, textvariable=w_var, style=st.KOMBI, state="readonly",
                                 values=mk.VERFUEGBARE_WORKER, width=22)
            w_box.grid(row=r, column=3, sticky="ew", padx=4, pady=4)

            def _markiere_benutzerdefiniert(*_):
                preset_var.set("Benutzerdefiniert")

            m_box.bind("<<ComboboxSelected>>", _markiere_benutzerdefiniert)
            p_box.bind("<<ComboboxSelected>>", _markiere_benutzerdefiniert)
            w_box.bind("<<ComboboxSelected>>", _markiere_benutzerdefiniert)

            widgets[lkey] = (m_var, p_var, w_var)

        def _preset_gewaehlt(event=None):
            gewaehlt = preset_var.get()
            if gewaehlt in mk.PRESETS:
                p_data = mk.PRESETS[gewaehlt]
                for lkey in ("lage_1", "lage_2a", "lage_2b", "lage_3"):
                    if lkey in p_data and lkey in widgets:
                        m_v, p_v, w_v = widgets[lkey]
                        m_v.set(p_data[lkey].get("master", m_v.get()))
                        p_v.set(p_data[lkey].get("pruefer", p_v.get()))
                        w_v.set(p_data[lkey].get("worker", w_v.get()))
                if "antigravity" in p_data:
                    agy_var.set(p_data["antigravity"].get("rolle", agy_var.get()))
                    agy_mod_var.set(p_data["antigravity"].get("modell", agy_mod_var.get()))

        preset_box.bind("<<ComboboxSelected>>", _preset_gewaehlt)

        # Gemini / Antigravity Einstellungen
        ttk.Label(frame, text="Gemini / Antigravity Rolle:", style=st.KARTE_TITEL).grid(
            row=8, column=0, sticky="w", padx=4, pady=(16, 4))
        agy_var = tk.StringVar(value=cfg.get("antigravity", {}).get("rolle", "Master / Thinker"))
        agy_box = ttk.Combobox(frame, textvariable=agy_var, style=st.KOMBI, state="readonly",
                               values=("Master / Thinker", "Reviewer / Pruefer", "Worker / Ausfuehrer"), width=22)
        agy_box.grid(row=8, column=1, sticky="w", padx=4, pady=(16, 4))

        ttk.Label(frame, text="Bevorzugtes Antigravity-Modell:", style=st.KARTE_TITEL).grid(
            row=8, column=2, sticky="w", padx=4, pady=(16, 4))
        agy_mod_var = tk.StringVar(value=cfg.get("antigravity", {}).get("bevorzugtes_modell", "Claude Opus 5.5"))
        agy_mod_box = ttk.Combobox(frame, textvariable=agy_mod_var, style=st.KOMBI, state="readonly",
                                   values=("Claude Opus 5.5", "Argon (Antigravity)", "Gemini 3.8 Flash", "DeepSeek V4.1 Flash"), width=22)
        agy_mod_box.grid(row=8, column=3, sticky="w", padx=4, pady=(16, 4))

        knopfreihe = ttk.Frame(frame, style=st.KARTE)
        knopfreihe.grid(row=9, column=0, columnspan=4, sticky="ew", pady=(20, 0))

        def speichern():
            for lkey, (m_v, p_v, w_v) in widgets.items():
                if lkey not in cfg:
                    cfg[lkey] = {}
                cfg[lkey]["master"] = m_v.get().strip()
                cfg[lkey]["pruefer"] = p_v.get().strip()
                cfg[lkey]["worker"] = w_v.get().strip()
            if "antigravity" not in cfg:
                cfg["antigravity"] = {}
            cfg["antigravity"]["rolle"] = agy_var.get()
            cfg["antigravity"]["bevorzugtes_modell"] = agy_mod_var.get()
            cfg["preset"] = preset_var.get()
            mk.matrix_schreiben(cfg)
            top.destroy()
            self._status("Matrix-Konfiguration erfolgreich gespeichert.")

        def standard():
            cfg.clear()
            cfg.update(json.loads(json.dumps(mk.DEFAULT_MATRIX)))
            mk.matrix_schreiben(cfg)
            preset_var.set(mk.DEFAULT_PRESET_NAME)
            _preset_gewaehlt()
            self._status("Matrix-Konfiguration auf Standard zurueckgesetzt.")

        ttk.Button(knopfreihe, text="Speichern & Anwenden", style=st.KNOPF_AKZENT, command=speichern).pack(side="left", padx=(0, 8))
        ttk.Button(knopfreihe, text="Standard (AGENTS.md)", style=st.KNOPF, command=standard).pack(side="left", padx=(0, 8))
        ttk.Button(knopfreihe, text="Abbrechen", style=st.KNOPF, command=top.destroy).pack(side="right")

    def uebergabe_dialog_oeffnen(self, thema: str, alt_master: str, neu_master: str) -> None:
        """Modales Dialogfenster für gezielten Masterwechsel: Sofort unterbrechen oder in Warteschlange einreihen."""
        top = tk.Toplevel(self.root)
        top.title(f"Masterwechsel – {thema}")
        top.configure(background=st.GRUND)
        top.transient(self.root)
        top.resizable(False, False)
        top.grab_set()

        frame = ttk.Frame(top, padding=st.ABSTAND_GROSS, style=st.KARTE)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=f"Masterwechsel für Thema: {thema}", style=st.TITEL).pack(anchor="w", pady=(0, 6))

        alt_text = um.MASTER_TEXTE.get(alt_master, alt_master)
        neu_text = um.MASTER_TEXTE.get(neu_master, neu_master)
        ttk.Label(frame, text=f"Aktueller Master:  {alt_text}   ➔   Neuer Master:  {neu_text}",
                  style=st.KARTE_TITEL, foreground=st.AKZENT_PRIMAR).pack(anchor="w", pady=(0, 12))

        ttk.Label(frame, text="Wie soll die Übergabe erfolgen?", style=st.KARTE_LABEL).pack(anchor="w", pady=(0, 16))

        knopfreihe = ttk.Frame(frame, style=st.KARTE)
        knopfreihe.pack(fill="x", pady=(4, 0))

        def ausfuehren(modus: str) -> None:
            top.destroy()
            self._uebergabe_direkt_starten(thema, neu_master, modus=modus)

        # 1. Jetzt aktuellen Master unterbrechen (sofort)
        ttk.Button(knopfreihe, text="Jetzt aktuellen Master unterbrechen", style=st.KNOPF_AKZENT,
                   command=lambda: ausfuehren("sofort")).pack(side="left", padx=(0, 8))

        # 2. In Warteschlange geben (geordnet mit Warten auf Abgabe)
        ttk.Button(knopfreihe, text="In Warteschlange geben", style=st.KNOPF,
                   command=lambda: ausfuehren("warten")).pack(side="left", padx=(0, 8))

        # 3. Abbrechen
        ttk.Button(knopfreihe, text="Abbrechen", style=st.KNOPF_KLEIN,
                   command=top.destroy).pack(side="right")

    def _uebergabe_direkt_starten(self, thema: str, ziel: str, modus: str) -> None:
        """Führt den Masterwechsel im Hintergrund aus (sofort oder mit geordnetem Warten)."""
        if self._beschaeftigt:
            self._status("Aktion läuft noch – bitte warten.")
            return

        def aktion() -> um.Ergebnis:
            try:
                from . import assistent
                abgabe_modus = "warten" if modus == "warten" else "frist"
                vorgang = assistent.uebergeben(thema, ziel, abgabe_modus=abgabe_modus)
                return um.Ergebnis(
                    ok=True,
                    text=f"Übergabe für {thema} an {ziel} gestartet ({vorgang.id}, Modus: {modus}).",
                    bericht=""
                )
            except Exception as fehler:
                return um.Ergebnis(ok=False, text=f"Übergabe fehlgeschlagen ({type(fehler).__name__})", bericht=str(fehler))

        self._im_hintergrund(aktion)

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
