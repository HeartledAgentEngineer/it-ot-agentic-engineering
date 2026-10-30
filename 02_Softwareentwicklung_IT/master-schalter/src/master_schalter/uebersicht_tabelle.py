"""Direkt bearbeitbare, scrollbare Themenzeilen für das Übersichtsfenster."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass, field
from typing import Callable

from . import anzeige, uebersicht_modell as um, uebersicht_stil as st
from .uebersicht_entwurf import EntwurfsVerwaltung

FELDER = ("master", "pruefer", "ausfuehrer", "modell", "arbeitsweise", "auto")
SPALTEN = (("thema", "Thema", 160), ("master", "Master", 140), ("besitz", "Besitz", 130),
           ("pruefer", "Prüfer", 190), ("ausfuehrer", "Ausführer", 190),
           ("arbeitsweise", "Arbeitsweise", 130), ("auto", "Auto-Freigabe", 130),
           ("aktion", "Aktion", 140))


@dataclass
class ThemaZeilenWidgets:
    thema: str
    frame: ttk.Frame
    felder: dict[str, ttk.Combobox] = field(default_factory=dict)
    details: ttk.Label | None = None
    werte: dict[str, tuple[str | bool | None, ...]] = field(default_factory=dict)
    modell_liste: um.ModellListe | None = None
    aktion_knopf: ttk.Button | None = None


class ThemenTabelle(ttk.Frame):
    """Canvas-Tabelle; Eingaben geben immer Themenkennung, Feld und fachlichen Wert zurück."""

    def __init__(self, master: tk.Misc, *, aendern: Callable[[str, str, str | bool | None], None],
                 uebergabe_anfordern: Callable[[str, str, str], None] | None = None, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._aendern = aendern
        self._uebergabe_anfordern = uebergabe_anfordern
        self.zeilen: dict[str, ThemaZeilenWidgets] = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.ybar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.ybar.grid(row=0, column=1, sticky="ns")
        self.xbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.xbar.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=self.ybar.set, xscrollcommand=self.xbar.set)
        self.inhalt = ttk.Frame(self.canvas)
        self._fenster = self.canvas.create_window((0, 0), window=self.inhalt, anchor="nw")
        self.inhalt.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._kopf = ttk.Frame(self.inhalt)
        self._kopf.grid(row=0, column=0, sticky="ew")
        for col, (key, title, width) in enumerate(SPALTEN):
            self._kopf.columnconfigure(col, minsize=width, weight=1 if key in FELDER else 0)
            ttk.Label(self._kopf, text=title, width=max(10, width // 9), anchor="w").grid(row=0, column=col, sticky="ew")
        self.canvas.bind("<Configure>", self._breite)

    def _breite(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self._fenster, width=max(event.width, sum(c[2] for c in SPALTEN)))

    @staticmethod
    def _auto_text(zeile: um.ThemaZeile) -> str:
        punkt = "●" if zeile.auto_zustand in (anzeige.AUTO_WIRKSAM, anzeige.AUTO_WARTET) else "○"
        return f"{punkt} {zeile.auto}"

    @staticmethod
    def _werte(zeile: um.ThemaZeile, kataloge: tuple[um.KatalogAnsicht, ...]) -> dict[str, tuple[tuple[str, ...], tuple[str | bool | None, ...], str, bool]]:
        ml = um.modell_liste(zeile, kataloge)
        katalog = next((k for k in kataloge if k.anbieter == zeile.worker_wert), None)
        if zeile.worker_wert in ("claude", "codex"):
            gueltig = {kennung for kennung, _ in katalog.modelle} if katalog and katalog.geprueft else set()
            eintraege = tuple((text, wert) for text, wert in ml.eintraege
                              if wert is None or wert in gueltig)
        else:
            eintraege = ml.eintraege
        modelle = tuple(text for text, _ in eintraege)
        modellwerte = tuple(wert for _, wert in eintraege)
        # Pruefer: zeige konkretes Modell/Rolle
        pruefer_aktuell = um.PRUEFER_TEXTE.get(zeile.pruefer_wert, zeile.pruefer_wert)
        pruefer_texte = list(um.PRUEFER_TEXTE[v] for v in um.PRUEFER_WERTE)
        if getattr(zeile, "pruefer", "") and zeile.pruefer not in ("Automatisch", "automatisch"):
            if zeile.pruefer_wert == "automatisch":
                pruefer_label = f"Auto ({zeile.pruefer})"
                pruefer_aktuell = pruefer_label
                if "Automatisch" in pruefer_texte:
                    pruefer_texte[pruefer_texte.index("Automatisch")] = pruefer_label
                elif pruefer_label not in pruefer_texte:
                    pruefer_texte.insert(0, pruefer_label)

        # Ausfuehrer: zeige konkreten Worker / Modell
        ausfuehrer_aktuell = um.AUSFUEHRER_TEXTE.get(zeile.worker_wert, zeile.worker_wert)
        ausfuehrer_texte = list(um.AUSFUEHRER_TEXTE[v] for v in um.AUSFUEHRER_WERTE)
        if getattr(zeile, "ausfuehrer", "") and zeile.ausfuehrer not in ("Workflow", "workflow"):
            if zeile.worker_wert == "workflow":
                wf_label = zeile.ausfuehrer if zeile.ausfuehrer.startswith("Workflow") else f"Workflow ({zeile.ausfuehrer})"
                ausfuehrer_aktuell = wf_label
                if "Workflow" in ausfuehrer_texte:
                    ausfuehrer_texte[ausfuehrer_texte.index("Workflow")] = wf_label
                elif wf_label not in ausfuehrer_texte:
                    ausfuehrer_texte.insert(0, wf_label)

        return {
            "master": (tuple(um.MASTER_TEXTE[v] for v in um.MASTER_WERTE), um.MASTER_WERTE, um.MASTER_TEXTE.get(zeile.master_wert, zeile.master_wert), False),
            "pruefer": (tuple(pruefer_texte), um.PRUEFER_WERTE, pruefer_aktuell, False),
            "ausfuehrer": (tuple(ausfuehrer_texte), um.AUSFUEHRER_WERTE, ausfuehrer_aktuell, False),
            "modell": (modelle, modellwerte, ml.aktuell, ml.gesperrt),
            "arbeitsweise": (tuple(um.ARBEITSWEISE_TEXTE[v] for v in um.ARBEITSWEISE_WERTE), um.ARBEITSWEISE_WERTE, um.ARBEITSWEISE_TEXTE.get(zeile.arbeitsweise, zeile.arbeitsweise), False),
            "auto": (tuple(um.AUTO_TEXTE[v] for v in um.AUTO_WERTE), um.AUTO_WERTE, um.AUTO_TEXTE.get(zeile.paar_aktiv, ""), zeile.paar_aktiv is None),
        }

    def aktualisieren(self, snap: um.Uebersicht, *, entwuerfe: EntwurfsVerwaltung,
                      beschaeftigt: bool = False) -> None:
        vorhanden = {t.thema: t for t in snap.themen}
        for thema in tuple(self.zeilen):
            if thema not in vorhanden:
                self.zeilen.pop(thema).frame.destroy()
        for index, zeile in enumerate(snap.themen, start=1):
            row = self.zeilen.get(zeile.thema)
            if row is None:
                frame = ttk.Frame(self.inhalt)
                row = ThemaZeilenWidgets(zeile.thema, frame)
                row.frame.grid(row=index, column=0, sticky="ew")
                for col, (key, _title, width) in enumerate(SPALTEN):
                    frame.columnconfigure(col, minsize=width, weight=1 if key in FELDER else 0)
                ttk.Label(frame, text=zeile.thema, anchor="w", wraplength=150).grid(row=0, column=0, sticky="ew")
                ttk.Label(frame, text=zeile.besitz, anchor="w", wraplength=160).grid(row=0, column=2, sticky="ew")
                for col, feld in ((1, "master"), (3, "pruefer"), (4, "ausfuehrer"), (5, "arbeitsweise"), (6, "auto")):
                    box = ttk.Combobox(frame, style=st.KOMBI, state="disabled", width=max(10, SPALTEN[col][2] // 10))
                    box.grid(row=0, column=col, sticky="ew", padx=2, pady=2)
                    box.bind("<<ComboboxSelected>>", lambda event, k=feld, r=row: self._auswahl(r, k, event.widget))
                    row.felder[feld] = box
                # Modell bleibt fuer Tests/Backend als Widget erhalten, wird aber nicht gegriddet:
                box_modell = ttk.Combobox(frame, style=st.KOMBI, state="disabled")
                box_modell.bind("<<ComboboxSelected>>", lambda event, k="modell", r=row: self._auswahl(r, k, event.widget))
                row.felder["modell"] = box_modell

                btn = ttk.Button(frame, text="—", style=st.KNOPF_KLEIN, state="disabled")
                btn.grid(row=0, column=7, sticky="ew", padx=2, pady=2)
                row.aktion_knopf = btn
                row.details = ttk.Label(frame, anchor="w", wraplength=1100)
                row.details.grid_remove()
                self.zeilen[zeile.thema] = row
            else:
                row.frame.grid_configure(row=index)
                row.frame.grid()
                row.frame.winfo_children()[0].configure(text=zeile.thema)
                row.frame.winfo_children()[1].configure(text=zeile.besitz)
            gewuenscht = entwuerfe.zeile(zeile.thema)
            einstellungen = self._werte(gewuenscht, snap.kataloge)
            row.modell_liste = um.modell_liste(gewuenscht, snap.kataloge)
            assert row.details is not None
            warnungen = []
            if zeile.pruefer_warnung:
                warnungen.append("Achtung: gleiche Prüferfamilie wie Master")
            if zeile.auto_zustand == anzeige.AUTO_WARTET:
                warnungen.append("Auto-Freigabe aktiv, derzeit nicht wirksam")
            if row.modell_liste and row.modell_liste.hinweis:
                warnungen.append(row.modell_liste.hinweis)
            if thema_wechselt := (zeile.thema in getattr(snap, "wechsel_themen", ())):
                warnungen.append("Wechsel läuft – wartet auf Abschluss")
            if not getattr(snap, "wechsel_pruefbar", False):
                warnungen.append("Wechselstatus nicht prüfbar – Auswahl gesperrt")
            auto_info = self._auto_text(zeile)
            details_text = f"{auto_info}" + ("   ⚠ " + " · ".join(warnungen) if warnungen else "")
            row.details.configure(text=details_text)
            # Im modernen Frontend: kein 2-zeiliger Fließtext mehr unter den Zeilen.
            # Nur bei echten Warnungen (wie Wechsel läuft) dezent einblenden, sonst unsichtbar.
            row.details.configure(text=details_text, style=st.KARTE_WARNUNG if warnungen else st.KARTE_GEDAEMPFT)
            # Tabelle bleibt 100% einzeilig und ruhig ohne gelben Fliesszeilentext:
            row.details.grid_remove()
            for feld in FELDER:
                texte, werte, aktuell, gesperrt = einstellungen[feld]
                box = row.felder[feld]
                offen = box.focus_get() is box
                if not offen:
                    box.configure(values=texte)
                    box.set(aktuell)
                    row.werte[feld] = werte
                elif tuple(box.cget("values")) != texte:
                    # Ein offenes Menü kann keine neuen Indizes bekommen: bis zum nächsten sicheren Refresh sperren.
                    box.configure(state="disabled")
                erlaubt = (snap.schreiben and getattr(snap, "wechsel_pruefbar", False)
                           and not thema_wechselt and not beschaeftigt and not gesperrt)
                if not offen or tuple(box.cget("values")) == texte:
                    box.configure(state="readonly" if erlaubt else "disabled")
            if row.aktion_knopf is not None:
                master_neu = gewuenscht.master_wert
                master_alt = zeile.master_wert
                if master_neu != master_alt and snap.schreiben and not beschaeftigt and not thema_wechselt:
                    row.aktion_knopf.configure(
                        text="Übergabe …", state="normal", style=st.KNOPF_AKZENT,
                        command=lambda t=zeile.thema, a=master_alt, n=master_neu: self._uebergabe_klick(t, a, n))
                else:
                    row.aktion_knopf.configure(text="—", state="disabled", style=st.KNOPF_KLEIN, command=lambda: None)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _auswahl(self, row: ThemaZeilenWidgets, feld: str, box: ttk.Combobox) -> None:
        if row.thema not in self.zeilen or box.current() < 0:
            return
        werte = row.werte.get(feld, ())
        index = box.current()
        if index >= len(werte):
            return
        wert = werte[index]
        self._aendern(row.thema, feld, wert)

    def _uebergabe_klick(self, thema: str, alt: str, neu: str) -> None:
        if self._uebergabe_anfordern:
            self._uebergabe_anfordern(thema, alt, neu)
