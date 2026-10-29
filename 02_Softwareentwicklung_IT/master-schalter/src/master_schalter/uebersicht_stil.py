"""Modernes dunkles Aussehen der Übersicht – nur Bordmittel (tkinter/ttk, kein neues Paket).

Angelehnt an Claude Code und Codex: warmes Dunkelgrau als Grund, etwas hellere Karten, zurückhaltende Textfarben, Akzent
Claude (orange) und Codex (grün), gelb für „wirkt nicht / Hinweis“, rot für Fehler. **Alle Farben stehen als Konstanten an
dieser einen Stelle**; `uebersicht.py` benutzt nur diese Namen. `anwenden` legt auf dem Thema „clam“ eigene ttk-Stile an
(flache Knöpfe, schmale Fortschrittsbalken ohne 3D-Rand, Tabelle ohne Gitter mit Zeilenabstand und Auswahl in Akzentfarbe,
Aufklappmenüs, Pillen). Tests prüfen nur, dass die Stile existieren und die Werte stimmen, nicht Pixel.
"""
from __future__ import annotations

from typing import Iterable
from tkinter import ttk

# --- Farben (eine Stelle) ---------------------------------------------------------------------------------------
GRUND = "#1f1e1d"             # Fensterhintergrund
FLAECHE = "#262624"           # Karten
FLAECHE2 = "#30302e"          # Knöpfe, Eingabefelder, Balkenrinne, Tabellenkopf
LINIE = "#3d3d3a"             # feine Trennlinien
TEXT = "#ececec"
TEXT_GEDAEMPFT = "#a3a3a0"
AKZENT_CLAUDE = "#d97757"
AKZENT_CODEX = "#10a37f"
WARNUNG = "#eab308"
FEHLER = "#ef4444"
AUF_AKZENT = "#1f1e1d"        # Schrift auf Akzentflächen
GRAU = "#9ca3af"              # Balken bei unbekanntem Verbrauch

# --- Schrift ----------------------------------------------------------------------------------------------------
SCHRIFTEN = ("Segoe UI Variable", "Segoe UI")
SCHRIFT_ERSATZ = "TkDefaultFont"

# --- Abstände (px) -------------------------------------------------------------------------------------------------
ABSTAND = 12
ABSTAND_GROSS = 16
ZEILENHOEHE = 30
BALKEN_DICKE = 6

# --- Stilnamen ------------------------------------------------------------------------------------------------------
KARTE = "Karte.TFrame"
KOPF = "Kopf.TFrame"
LABEL = "Grund.TLabel"
LABEL_GEDAEMPFT = "GrundGedaempft.TLabel"
LABEL_FEHLER = "GrundFehler.TLabel"
KARTE_LABEL = "Karte.TLabel"
KARTE_GEDAEMPFT = "KarteGedaempft.TLabel"
KARTE_TITEL = "KarteTitel.TLabel"
KARTE_FEHLER = "KarteFehler.TLabel"
KARTE_WARNUNG = "KarteWarnung.TLabel"
KARTE_GUT = "KarteGut.TLabel"
TITEL = "Titel.TLabel"
PILLE = "Pille.TLabel"
PILLE_UNBEKANNT = "PilleUnbekannt.TLabel"
KNOPF = "Flach.TButton"
KNOPF_KLEIN = "Klein.TButton"
KNOPF_AKZENT = "Akzent.TButton"
KOMBI = "Dunkel.TCombobox"
TABELLE = "Tabelle.Treeview"
TABELLENKOPF = "Tabelle.Treeview.Heading"
REGLER = "Dunkel.Vertical.TScrollbar"
BALKEN_BASIS = "Horizontal.TProgressbar"

# Stil → Hintergrund, den `anwenden` setzt (für den Test „Stile existieren“; Tabellen/Regler/Kombi prüft der Test getrennt).
STILE: dict[str, str] = {
    KARTE: FLAECHE, KOPF: FLAECHE, LABEL: GRUND, LABEL_GEDAEMPFT: GRUND, LABEL_FEHLER: GRUND, KARTE_LABEL: FLAECHE,
    KARTE_GEDAEMPFT: FLAECHE, KARTE_TITEL: FLAECHE, KARTE_FEHLER: FLAECHE, KARTE_WARNUNG: FLAECHE,
    KARTE_GUT: FLAECHE, TITEL: FLAECHE, PILLE: AKZENT_CLAUDE, PILLE_UNBEKANNT: FLAECHE2, KNOPF: FLAECHE2, KNOPF_KLEIN: FLAECHE2,
    KNOPF_AKZENT: AKZENT_CLAUDE,
}


def schrift_waehlen(familien: Iterable[str]) -> str:
    """Erste vorhandene Schrift aus `SCHRIFTEN` (Groß-/Kleinschreibung egal), sonst `TkDefaultFont`."""
    vorhanden = {f.lower() for f in familien}
    return next((name for name in SCHRIFTEN if name.lower() in vorhanden), SCHRIFT_ERSATZ)


def balken_stil_name(farbe: str) -> str:
    """Name des Balkenstils zu einer Farbe, z. B. `Fd97757.Horizontal.TProgressbar`."""
    return f"F{farbe.lstrip('#')}.{BALKEN_BASIS}"


def balken_stil(stil: ttk.Style, farbe: str) -> str:
    """Schmaler flacher Balken in `farbe` (Rinne `FLAECHE2`, kein 3D-Rand); legt den Stil bei Bedarf an."""
    name = balken_stil_name(farbe)
    stil.configure(name, background=farbe, troughcolor=FLAECHE2, bordercolor=FLAECHE, lightcolor=farbe,
                   darkcolor=farbe, thickness=BALKEN_DICKE, borderwidth=0)
    return name


def anwenden(wurzel, stil: ttk.Style | None = None) -> tuple[ttk.Style, str]:
    """Stile auf `wurzel` anwenden; liefert (Style, gewählte Schriftfamilie)."""
    import tkinter.font as tkfont

    stil = stil or ttk.Style(wurzel)
    try:
        stil.theme_use("clam")        # nur dieses Thema erlaubt eigene Farben
    except Exception:                 # noqa: BLE001 - ohne clam bleibt es beim Standardthema
        pass
    try:
        familie = schrift_waehlen(tkfont.families(wurzel))
    except Exception:                 # noqa: BLE001
        familie = SCHRIFT_ERSATZ
    normal, klein, fett, gross = ((familie, 10), (familie, 9), (familie, 10, "bold"), (familie, 14, "bold"))

    wurzel.configure(background=GRUND)
    wurzel.option_add("*TCombobox*Listbox.background", FLAECHE2)
    wurzel.option_add("*TCombobox*Listbox.foreground", TEXT)
    wurzel.option_add("*TCombobox*Listbox.selectBackground", AKZENT_CLAUDE)
    wurzel.option_add("*TCombobox*Listbox.selectForeground", AUF_AKZENT)
    wurzel.option_add("*TCombobox*Listbox.font", normal)

    stil.configure(".", background=GRUND, foreground=TEXT, font=normal, bordercolor=LINIE, focuscolor=GRUND,
                   lightcolor=GRUND, darkcolor=GRUND, troughcolor=FLAECHE2)
    stil.configure("TFrame", background=GRUND)
    stil.configure(KARTE, background=FLAECHE)
    stil.configure(KOPF, background=FLAECHE)
    stil.configure("TLabel", background=GRUND, foreground=TEXT, font=normal)
    stil.configure(LABEL, background=GRUND, foreground=TEXT, font=normal)
    stil.configure(LABEL_GEDAEMPFT, background=GRUND, foreground=TEXT_GEDAEMPFT, font=klein)
    stil.configure(LABEL_FEHLER, background=GRUND, foreground=FEHLER, font=klein)
    stil.configure(KARTE_LABEL, background=FLAECHE, foreground=TEXT, font=normal)
    stil.configure(KARTE_GEDAEMPFT, background=FLAECHE, foreground=TEXT_GEDAEMPFT, font=klein)
    stil.configure(KARTE_TITEL, background=FLAECHE, foreground=TEXT, font=fett)
    stil.configure(KARTE_FEHLER, background=FLAECHE, foreground=FEHLER, font=klein)
    stil.configure(KARTE_WARNUNG, background=FLAECHE, foreground=WARNUNG, font=klein)
    stil.configure(KARTE_GUT, background=FLAECHE, foreground=AKZENT_CODEX, font=klein)
    stil.configure(TITEL, background=FLAECHE, foreground=TEXT, font=gross)
    stil.configure(PILLE, background=AKZENT_CLAUDE, foreground=AUF_AKZENT, font=fett, padding=(10, 2))
    stil.configure(PILLE_UNBEKANNT, background=FLAECHE2, foreground=TEXT_GEDAEMPFT, font=fett, padding=(10, 2))

    flach = dict(relief="flat", borderwidth=0, focusthickness=0, focuscolor=FLAECHE2)
    stil.configure(KNOPF, background=FLAECHE2, foreground=TEXT, padding=(14, 7), font=normal, **flach)
    stil.map(KNOPF, background=[("disabled", FLAECHE), ("pressed", LINIE), ("active", LINIE)],
             foreground=[("disabled", TEXT_GEDAEMPFT)])
    stil.configure(KNOPF_KLEIN, background=FLAECHE2, foreground=TEXT, padding=(10, 4), font=klein, **flach)
    stil.map(KNOPF_KLEIN, background=[("disabled", FLAECHE), ("pressed", LINIE), ("active", LINIE)],
             foreground=[("disabled", TEXT_GEDAEMPFT)])
    stil.configure(KNOPF_AKZENT, background=AKZENT_CLAUDE, foreground=AUF_AKZENT, padding=(14, 7), font=fett, **flach)
    stil.map(KNOPF_AKZENT, background=[("disabled", FLAECHE2), ("pressed", "#c4664a"), ("active", "#e38a6c")],
             foreground=[("disabled", TEXT_GEDAEMPFT)])

    stil.configure(KOMBI, fieldbackground=FLAECHE2, background=FLAECHE2, foreground=TEXT, arrowcolor=TEXT,
                   bordercolor=FLAECHE2, lightcolor=FLAECHE2, darkcolor=FLAECHE2, padding=(8, 5),
                   selectbackground=FLAECHE2, selectforeground=TEXT)
    stil.map(KOMBI, fieldbackground=[("readonly", FLAECHE2), ("disabled", FLAECHE)],
             foreground=[("disabled", TEXT_GEDAEMPFT)], arrowcolor=[("disabled", TEXT_GEDAEMPFT)],
             selectbackground=[("readonly", FLAECHE2)], selectforeground=[("readonly", TEXT)])

    stil.configure(TABELLE, background=FLAECHE, fieldbackground=FLAECHE, foreground=TEXT, rowheight=ZEILENHOEHE,
                   borderwidth=0, relief="flat", font=normal)
    stil.map(TABELLE, background=[("selected", AKZENT_CLAUDE)], foreground=[("selected", AUF_AKZENT)])
    stil.configure(TABELLENKOPF, background=FLAECHE2, foreground=TEXT_GEDAEMPFT, relief="flat", borderwidth=0,
                   padding=(8, 6), font=fett)
    stil.map(TABELLENKOPF, background=[("active", LINIE)])
    stil.layout(TABELLE, [("Treeview.treearea", {"sticky": "nswe"})])      # ohne Gitterrahmen

    stil.configure(REGLER, background=FLAECHE2, troughcolor=FLAECHE, bordercolor=FLAECHE, arrowcolor=TEXT_GEDAEMPFT,
                   lightcolor=FLAECHE2, darkcolor=FLAECHE2, relief="flat", gripcount=0)
    stil.map(REGLER, background=[("active", LINIE)])
    return stil, familie
