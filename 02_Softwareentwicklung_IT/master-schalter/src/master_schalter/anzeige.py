"""Texte für Tooltip, Menü und Benachrichtigung – reine Funktionen ohne Oberfläche.

Enthält zusätzlich die Menüeinträge der Rollenwahl je Thema (Master, Ausführer,
Ausführermodell) und die Texte der Modellkataloge. Alle Einträge werden ausschließlich aus
unveränderlichen Momentaufnahmen (`Rollenstand`, `Katalogstand`) gebaut – hier finden nie
Datei-, Prozess- oder Netzzugriffe statt.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from . import modi, rollen
from .signale import Fenster, Kontingent, _atomar_schreiben, daten_ordner
from .zustand import Zustand

if TYPE_CHECKING:
    from .wechsel import Ergebnis

STANDARD_SCHWELLE = 97
SCHWELLEN = (80, 90, 95, 97, 100)   # Auswahl im Menü „Wechsel-Schwelle"
MASTER_NAMEN = {"claude": "Claude", "codex": "Codex", "hermes": "Hermes", "agy": "Antigravity"}
WARN_AB = 80
TOOLTIP_MAX = 127   # Windows schneidet Tooltips von Taskleisten-Symbolen bei 127 Zeichen ab
HINWEIS_MAX = 255   # Windows-Benachrichtigungen fassen höchstens 255 Zeichen


def _kurz(prozent: float | None) -> str:
    return "–" if prozent is None else f"{round(prozent)}%"


def _lang(prozent: float | None) -> str:
    return "–" if prozent is None else f"{round(prozent)} %"


def _zeit(wert: datetime | None, zone: tzinfo | None) -> str:
    return "?" if wert is None else wert.astimezone(zone).strftime("%d.%m. %H:%M")


def _prozent(k: Kontingent, name: str) -> float | None:
    f = k.fenster_nach_name(name)
    return f.prozent if f else None


def verbraucht(prozent: float) -> int:
    """Verbrauch eines Fensters, auf 0–100 begrenzt: 130 ergibt 100, -5 ergibt 0."""
    return round(max(0.0, min(100.0, prozent)))


def _tooltip_wert(k: Kontingent) -> str:
    """5-Stunden-Verbrauch eines Abos für den Tooltip: „62 %“, „neu“ (Fenster zurückgesetzt) oder „?“."""
    f = None if k.fehler else k.fenster_nach_name("5h")
    if f is None or f.prozent is None:
        return "?"
    return "neu" if f.zurueckgesetzt else f"{verbraucht(f.prozent)} %"


def tooltip_symbol(lage: str | None, kontingente: list[Kontingent]) -> str:
    """Tooltip des Taskleisten-Symbols: „Lage 1 · Claude 62 % · Codex 1 % verbraucht“ (5-Stunden-Fenster, höchstens 127 Zeichen)."""
    werte = " · ".join(f"{k.master} {_tooltip_wert(k)}" for k in kontingente)
    text = f"Lage {lage or '?'} · {werte} verbraucht"
    return text if len(text) <= TOOLTIP_MAX else text[: TOOLTIP_MAX - 1] + "…"


def themen_zeile(master_je_thema: Iterable[str]) -> str:
    """Menükopf: Zahl der Themen je Masterart, z. B. „Themen: 3 fest · 2 nach Kontingent“."""
    masters = list(master_je_thema)
    if not masters:
        return "Themen: keine"
    nach_kontingent = sum(1 for m in masters if m == modi.KONTINGENT)
    return f"Themen: {len(masters) - nach_kontingent} fest · {nach_kontingent} nach Kontingent"


def tooltip(kontingente: list[Kontingent], kopf: str | None = None) -> str:
    """Kurzzeile für `masterwechsel status`: je Abo 5h und Woche (optional mit Kopf), höchstens 127 Zeichen."""
    teile = [kopf] if kopf else []
    for k in kontingente:
        if k.fehler:
            teile.append(f"{k.master}: {k.fehler}")
        else:
            teile.append(f"{k.master} 5h {_kurz(_prozent(k, '5h'))} · Wo {_kurz(_prozent(k, 'Woche'))}")
    text = " | ".join(teile)
    return text if len(text) <= TOOLTIP_MAX else text[: TOOLTIP_MAX - 1] + "…"


def _fenster_zeile(f: Fenster, zone: tzinfo | None) -> str:
    if f.zurueckgesetzt:
        return f"  {f.name}: zurückgesetzt (seit {_zeit(f.reset, zone)})"
    zeile = f"  {f.name}: {_lang(f.prozent)}"
    return zeile + (f" · Reset {_zeit(f.reset, zone)}" if f.reset else "")


def details(kontingente: list[Kontingent], zone: tzinfo | None = None, *,
            max_alter: timedelta | None = None, jetzt: datetime | None = None) -> list[str]:
    zeilen: list[str] = []
    jetzt = jetzt or datetime.now(timezone.utc)
    for k in kontingente:
        zeilen.append(k.master)
        if k.fehler:
            zeilen.append(f"  {k.fehler}")
            continue
        zeilen += [_fenster_zeile(f, zone) for f in k.fenster]
        veraltet = (max_alter is not None and k.stand is not None
                    and not timedelta(0) <= jetzt - k.stand <= max_alter)
        zeilen.append(f"  Stand: {_zeit(k.stand, zone)}" + (" (veraltet)" if veraltet else ""))
    return zeilen


def hinweis(kontingente: list[Kontingent], zone: tzinfo | None = None) -> str:
    zeilen = []
    for k in kontingente:
        if k.fehler:
            zeilen.append(f"{k.master}: {k.fehler}")
        else:
            zeilen.append(f"{k.master}: 5h {_lang(_prozent(k, '5h'))} · Woche {_lang(_prozent(k, 'Woche'))}"
                          f" (Stand {_zeit(k.stand, zone)})")
    return "\n".join(zeilen)[:HINWEIS_MAX]


def stufe(prozent: float | None, schwelle: int) -> str:
    if prozent is None:
        return "unbekannt"
    if prozent >= schwelle:
        return "voll"
    return "warn" if prozent >= WARN_AB else "ok"


def einstellungen_datei() -> Path:
    return daten_ordner() / "einstellungen.json"


def schwelle(datei: Path | None = None) -> int:
    """Schwelle in Prozent (1–100) aus `einstellungen.json`, sonst 97."""
    try:
        roh = json.loads((datei or einstellungen_datei()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return STANDARD_SCHWELLE
    wert = roh.get("schwelle") if isinstance(roh, dict) else None
    if isinstance(wert, bool) or not isinstance(wert, int) or not 1 <= wert <= 100:
        return STANDARD_SCHWELLE
    return wert


def schwelle_setzen(wert: int, datei: Path | None = None) -> None:
    """Schreibt die Schwelle (ganze Zahl 1–100) atomar; andere Felder der Datei bleiben erhalten."""
    if isinstance(wert, bool) or not isinstance(wert, int) or not 1 <= wert <= 100:
        raise ValueError(f"Schwelle muss eine ganze Zahl von 1 bis 100 sein, nicht {wert!r}")
    datei = datei or einstellungen_datei()
    try:
        roh = json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        roh = {}
    if not isinstance(roh, dict):
        roh = {}
    roh["schwelle"] = wert
    _atomar_schreiben(datei, json.dumps(roh, ensure_ascii=False, indent=2))


def claude_takt_min(datei: Path | None = None) -> int:
    """Messintervall in Minuten (1–60) aus `einstellungen.json`, sonst jede Minute."""
    try:
        roh = json.loads((datei or einstellungen_datei()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 1
    wert = roh.get("claude_takt_min") if isinstance(roh, dict) else None
    if isinstance(wert, bool) or not isinstance(wert, int) or not 1 <= wert <= 60:
        return 1
    return wert


def claude_takt_setzen(wert: int, datei: Path | None = None) -> None:
    """Speichert das Claude-Messintervall (ganze Minuten 1–60) und erhält andere Felder."""
    if isinstance(wert, bool) or not isinstance(wert, int) or not 1 <= wert <= 60:
        raise ValueError("Claude-Takt muss eine ganze Zahl von 1 bis 60 sein")
    datei = datei or einstellungen_datei()
    try:
        roh = json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        roh = {}
    if not isinstance(roh, dict):
        roh = {}
    roh["claude_takt_min"] = wert
    _atomar_schreiben(datei, json.dumps(roh, ensure_ascii=False, indent=2))


def automatik_an(datei: Path | None = None) -> bool:
    """Automatik Claude → Codex: aus, solange `einstellungen.json` nichts anderes sagt."""
    try:
        roh = json.loads((datei or einstellungen_datei()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool(roh.get("automatik")) if isinstance(roh, dict) else False


AUTO_WIRKSAM, AUTO_WARTET, AUTO_AUS, AUTO_OHNE_PAAR, AUTO_UNBEKANNT = "wirksam", "wartet", "aus", "ohne", "?"


def auto_paar_zaehlt(paar_aktiv: bool, master: str) -> bool:
    """Die Paar-Bedingung der Automatik: aktives Paar UND Master-Vorgabe „kontingent“.

    Eine Stelle für `automatik.faellige` und die Anzeige (`auto_zustand`) – jede feste Masterrolle bleibt ausgenommen.
    """
    return bool(paar_aktiv) and master == modi.KONTINGENT


def auto_zustand(hauptschalter: bool | None, paar_aktiv: bool | None, master: str) -> tuple[str, str]:
    """Gespeicherte Freigabe ≠ wirksamer Zustand: (Zustand, Text) für die Anzeige.

    Wirksam nur bei Hauptschalter an **und** Paar aktiv **und** Master `kontingent` (Bedingung wie `automatik.faellige`,
    dort zusätzlich Limit und Messung). `paar_aktiv=None` = kein Codex-Paar; `hauptschalter=None` = unbekannt.
    """
    if paar_aktiv is None:
        return AUTO_OHNE_PAAR, "ohne Codex-Paar"
    if not paar_aktiv:
        return AUTO_AUS, "Freigabe aus"
    if hauptschalter is None:
        return AUTO_UNBEKANNT, "Freigabe an – Hauptschalter unbekannt (?)"
    if hauptschalter and auto_paar_zaehlt(True, master):
        return AUTO_WIRKSAM, "Auto an (wirksam)"
    gruende = [] if hauptschalter else ["Hauptschalter aus"]
    if not auto_paar_zaehlt(True, master):
        gruende.append(f"fester Master {MASTER_NAMEN.get(master, master.capitalize())}")
    return AUTO_WARTET, "Freigabe an – wirkt nicht: " + ", ".join(gruende)


def automatik_setzen(an: bool, datei: Path | None = None) -> None:
    """Automatik ein- oder ausschalten; andere Felder der Datei bleiben erhalten."""
    datei = datei or einstellungen_datei()
    try:
        roh = json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        roh = {}
    if not isinstance(roh, dict):
        roh = {}
    roh["automatik"] = bool(an)
    _atomar_schreiben(datei, json.dumps(roh, ensure_ascii=False, indent=2))


WEG_ALT = "alt"
WEG_ASSISTENT = "assistent"
AUTOMATIK_WEGE = (WEG_ALT, WEG_ASSISTENT)
STANDARD_WEG = WEG_ALT
WEG_NAMEN = {WEG_ALT: "Alter Weg (direkt an Codex)", WEG_ASSISTENT: "Über Wechselassistent"}
WEG_AUSWAHL = tuple((WEG_NAMEN[w], w) for w in AUTOMATIK_WEGE)


def automatik_weg(datei: Path | None = None) -> str:
    """Weg der Limit-Automatik: `"alt"` (direkt an Codex) oder `"assistent"`; alles Unbekannte ergibt `"alt"`."""
    try:
        roh = json.loads((datei or einstellungen_datei()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return STANDARD_WEG
    wert = roh.get("automatik_weg") if isinstance(roh, dict) else None
    return wert if isinstance(wert, str) and wert in AUTOMATIK_WEGE else STANDARD_WEG


def automatik_weg_setzen(wert: str, datei: Path | None = None) -> None:
    """Weg atomar speichern; andere Felder bleiben erhalten. Ein ungültiger Wert wird nie wiederholt."""
    if not isinstance(wert, str) or wert not in AUTOMATIK_WEGE:
        raise ValueError(f"Automatik-Weg muss einer von {', '.join(AUTOMATIK_WEGE)} sein")
    datei = datei or einstellungen_datei()
    try:
        roh = json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        roh = {}
    if not isinstance(roh, dict):
        roh = {}
    roh["automatik_weg"] = wert
    _atomar_schreiben(datei, json.dumps(roh, ensure_ascii=False, indent=2))


# --- Master und Lage ---------------------------------------------------------

def master_menuezeile(z: Zustand, zone: tzinfo | None = None) -> str:
    """„Master: Claude (seit 14.10. 21:50)" bzw. „Master: nicht gesetzt"."""
    if z.master is None:
        return "Master: nicht gesetzt"
    zeile = f"Master: {MASTER_NAMEN[z.master]}"
    try:
        seit = datetime.fromisoformat(z.seit) if z.seit else None
    except ValueError:
        seit = None
    return zeile + (f" (seit {_zeit(seit, zone)})" if seit else "")


def lage_zeilen(lage: str | None, grund: str) -> list[str]:
    """Menüzeilen zur Lage: Besetzung bei bekannter Lage, sonst „Lage ? – Grund"."""
    b = rollen.besetzung(lage)
    if b is None:
        return ["Lage ?" + (f" – {grund}" if grund else "")]
    return [f"Lage {lage}: {b.name}", f"  Thinker: {b.thinker}", f"  Reviewer: {b.reviewer}",
            f"  Worker: {b.worker}"]


def master_status_zeile(z: Zustand, lage: str | None, grund: str) -> str:
    """Zeile für `masterwechsel status`: „Master: Claude · Lage 1"."""
    name = MASTER_NAMEN.get(z.master, "nicht gesetzt")
    return f"Master: {name} · " + (f"Lage {lage}" if lage else "Lage ?" + (f" – {grund}" if grund else ""))


def wechsel_hinweis(ergebnis: "Ergebnis") -> str:
    """Text der Windows-Benachrichtigung nach einem Klick auf „Master wechseln“."""
    name = MASTER_NAMEN[ergebnis.master]
    if ergebnis.art == "gewechselt":
        text = f"Standard-Master jetzt {name}. Technisches Übergabepaket: {ergebnis.paket.name}. Geschützte Themen (Hermes/Antigravity) bleiben unverändert."
    elif ergebnis.art == "gleich":
        text = f"Standard-Master ist schon {name}."
    else:
        text = f"Wechsel fehlgeschlagen: {ergebnis.meldung}"
    return text[:HINWEIS_MAX]


# --- Rollen je Thema, Ausführermodelle und Katalogstände (v0.4.0) -------------

MASTER_AUSWAHL = (("Nach Kontingent", "kontingent"), ("Claude Code", "claude"),
                  ("Codex", "codex"), ("Hermes", "hermes"), ("Antigravity", "agy"))
WORKER_AUSWAHL = (("Nach Workflow", "workflow"), ("Claude Code", "claude"),
                  ("Codex", "codex"), ("Hermes", "hermes"), ("Antigravity", "agy"))
ROLLEN_NAMEN = {"kontingent": "Nach Kontingent", "claude": "Claude Code",
                "codex": "Codex", "hermes": "Hermes", "agy": "Antigravity"}
WORKER_NAMEN = {"workflow": "Nach Workflow", **ROLLEN_NAMEN}
HERMES_MODELL_ANZEIGE = "DeepSeek V4.1 Flash"
STANDARD_MODELL = "Standard des Werkzeugs"
MODELLE_AKTUALISIEREN = "Modelle aktualisieren"
AUSFUEHRER_VORGABE = "Ausführervorgabe für den nächsten bereinigten Coding-Auftrag – startet keine Sitzung"
HERKUNFT_ZEILE = ("Claude-Code-Modelle aus dem Claude-Abo · Codex-Modelle aus dem ChatGPT-Abo · "
                  "Hermes über OpenRouter – kostenpflichtig")
PROVIDER_NAMEN = {"claude": "Claude Code", "codex": "Codex", "hermes": "Hermes", "agy": "Antigravity"}
PROVIDER_HERKUNFT = {
    "claude": "Claude-Code-Modelle aus dem Claude-Abo",
    "codex": "Codex-Modelle aus dem ChatGPT-Abo",
    "hermes": "Hermes über OpenRouter – kostenpflichtig",
    "agy": "Antigravity-Modelle aus dem Google-Abo (AI Pro) – ohne Zusatzkosten",
    "workflow": "Das Modell wählt der Workflow beim Auftrag",
}
ROLLEN_HINWEIS = "Rollenvorgabe für den nächsten bereinigten Coding-Auftrag – keine Sitzung gestartet"
SCHUTZ_HINWEIS = "Automatik, manuelle Rückgabe und globaler Masterwechsel lassen dieses Thema aus."
KONTINGENT_HINWEIS = "Kontingentweg offen: Automatik und manuelle Rückgabe dürfen übernehmen."


@dataclass(frozen=True)
class Katalogstand:
    """Unveränderliche Momentaufnahme eines Modellkatalogs (nur Kennung/Name, Fehler, Alter)."""

    provider: str = ""
    modelle: tuple[tuple[str, str], ...] = ()   # (Kennung, Anzeigename)
    zeit: str | None = None                     # ISO-Stand des letzten guten Ergebnisses
    fehler: str | None = None                   # einfache Fehlerkategorie, nie Rohdaten
    veraltet: bool = False


@dataclass(frozen=True)
class Rollenstand:
    """Unveränderliche Momentaufnahme des Rollenprofils eines Themas samt Katalogständen."""

    master: str = modi.KONTINGENT
    worker: str = modi.WORKFLOW
    modell: str | None = None
    kataloge: tuple[Katalogstand, ...] = ()


@dataclass(frozen=True)
class Eintrag:
    """Ein Menüeintrag aus der Momentaufnahme: Hinweiszeile oder wählbare Option."""

    text: str
    wert: str | None = None    # Kennung der Option (bei „Standard des Werkzeugs“ bewusst None)
    aktiv: bool = True         # auswählbar
    haken: bool = False        # Radio-Häkchen
    hinweis: bool = False      # reine Hinweiszeile ohne Aktion


def modell_anzeige(modell: str | None) -> str:
    """Anzeigename eines Ausführermodells; `None` ist der Standard des Werkzeugs."""
    if modell is None:
        return STANDARD_MODELL
    if modell == modi.HERMES_MODELL:
        return HERMES_MODELL_ANZEIGE
    return modell


def _hinweis(text: str) -> Eintrag:
    """Reine Hinweiszeile: sichtbar, aber nicht auswählbar."""
    return Eintrag(text, hinweis=True, aktiv=False)


def master_eintraege(stand: Rollenstand) -> list[Eintrag]:
    """Masterwahl je Thema; Haken aus der Momentaufnahme."""
    return [Eintrag(text, wert, haken=wert == stand.master) for text, wert in MASTER_AUSWAHL]


def worker_eintraege(stand: Rollenstand) -> list[Eintrag]:
    """Ausführervorgabe mit immer sichtbarer Herkunft und Vorgabehinweis."""
    return ([_hinweis(AUSFUEHRER_VORGABE), _hinweis(HERKUNFT_ZEILE)]
            + [Eintrag(text, wert, haken=wert == stand.worker) for text, wert in WORKER_AUSWAHL])


def modell_eintraege(stand: Rollenstand) -> list[Eintrag]:
    """Ausführermodell-Einträge: dynamische Katalogmodelle, Hinweise und gespeicherte Auswahl.

    Regeln: „Nach Workflow“ zeigt nur einen deaktivierten Hinweis; Hermes genau das fest
    freigegebene DeepSeek-Modell. Ein veralteter, fehlerhafter oder fehlender Katalog nennt
    den Grund und deaktiviert neue Modellwahlen (der Standard des Werkzeugs bleibt bewusst
    wählbar). Ein gespeichertes, nicht bestätigtes Modell bleibt sichtbar (Haken), ist aber
    zur Neuauswahl deaktiviert – es wird nie still ersetzt.
    """
    if stand.worker == modi.WORKFLOW:
        return [_hinweis("Nach Workflow – das Modell wählt der Workflow beim Auftrag")]
    if stand.worker == "hermes":
        zeilen = [
            _hinweis(PROVIDER_HERKUNFT["hermes"]),
            Eintrag(HERMES_MODELL_ANZEIGE, wert=modi.HERMES_MODELL,
                    haken=stand.modell == modi.HERMES_MODELL),
        ]
        if stand.modell != modi.HERMES_MODELL:
            zeilen.append(Eintrag(f"{stand.modell or 'kein Modell'} (gespeichert, nicht bestätigt)",
                                  aktiv=False, haken=True))
        return zeilen
    katalog = next((k for k in stand.kataloge if k.provider == stand.worker), None)
    if katalog is None:
        modelle_im_katalog: tuple[tuple[str, str], ...] = ()
        katalog_fehler, katalog_veraltet = None, False
    else:
        modelle_im_katalog = katalog.modelle
        katalog_fehler, katalog_veraltet = katalog.fehler, katalog.veraltet
    kennungen = tuple(kennung for kennung, _ in modelle_im_katalog)
    brauchbar = bool(katalog_fehler is None and not katalog_veraltet and kennungen)
    zeilen = [_hinweis(PROVIDER_HERKUNFT[stand.worker])]
    if not kennungen:
        zeilen.append(_hinweis(f"Kein Katalog – zuerst „{MODELLE_AKTUALISIEREN}“"))
    else:
        if katalog_fehler is not None:
            zeilen.append(_hinweis(f"Katalogfehler: {katalog_fehler} – zuerst "
                                   f"„{MODELLE_AKTUALISIEREN}“"))
        elif katalog_veraltet:
            zeilen.append(_hinweis(f"Katalog veraltet – zuerst „{MODELLE_AKTUALISIEREN}“"))
        zeilen += [Eintrag(name, wert=kennung, aktiv=brauchbar, haken=kennung == stand.modell)
                   for kennung, name in modelle_im_katalog]
    if stand.modell is None:
        zeilen.append(Eintrag(STANDARD_MODELL, wert=None, aktiv=True, haken=True))
    elif stand.modell not in kennungen:
        zeilen.append(Eintrag(f"{stand.modell} (gespeichert, nicht bestätigt)", aktiv=False, haken=True))
    return zeilen


def rollen_zeilen(thema: str, stand: Rollenstand, geschuetzt: bool) -> list[str]:
    """Drei Zeilen für `masterwechsel profil THEMA`: Wahl, Quelle und Vorgabe-/Schutzart."""
    return [
        f"{thema}: Master {ROLLEN_NAMEN[stand.master]} · Ausführer {WORKER_NAMEN[stand.worker]} · "
        f"Ausführermodell {modell_anzeige(stand.modell)}",
        f"  Quelle: {PROVIDER_HERKUNFT[stand.worker]}",
        f"  {ROLLEN_HINWEIS} · " + (SCHUTZ_HINWEIS if geschuetzt else KONTINGENT_HINWEIS),
    ]


def master_meldung(thema: str, master: str) -> str:
    return f"{thema}: Master {ROLLEN_NAMEN[master]} gespeichert – keine Sitzung gestartet."


def ausfuehrer_meldung(thema: str, worker: str, modell: str | None) -> str:
    """Providerwechsel meldet ausdrücklich das dann gesetzte Ausführermodell."""
    return (f"{thema}: Ausführer {WORKER_NAMEN[worker]} gespeichert – "
            f"Ausführermodell {modell_anzeige(modell)} · keine Sitzung gestartet.")


def modell_meldung(thema: str, modell: str | None) -> str:
    return f"{thema}: Ausführermodell {modell_anzeige(modell)} gespeichert – keine Sitzung gestartet."


def feste_themen_zeile(themen: list[str]) -> str:
    """Menüzeile für Themen mit fester Masterrolle – kein Anspruch auf globale Übernahme."""
    return "Feste Themenrollen (bleiben beim globalen Wechsel erhalten): " + ", ".join(sorted(themen))


def katalog_zeilen(kataloge: tuple[Katalogstand, ...]) -> list[str]:
    """Menüzeilen für Katalogprobleme; frische, leere Läufe erzeugen keine Zeile."""
    zeilen: list[str] = []
    for stand in kataloge:
        name = PROVIDER_NAMEN.get(stand.provider, stand.provider)
        if stand.fehler is not None:
            zeilen.append(f"Modellkatalog {name}: {stand.fehler}")
        elif stand.veraltet:
            zeilen.append(f"Modellkatalog {name}: veraltet oder leer – {MODELLE_AKTUALISIEREN}")
    return zeilen


def katalog_ausgabe(stand: Katalogstand) -> list[str]:
    """Mehrzeilige Textausgabe eines Katalogs für `masterwechsel modelle`."""
    zeilen = [f"{PROVIDER_NAMEN.get(stand.provider, stand.provider)}: "
              f"{PROVIDER_HERKUNFT.get(stand.provider, '')}".rstrip()]
    if stand.fehler is not None:
        zeilen.append(f"  Fehler: {stand.fehler}")
    zeilen.append(f"  Stand: {stand.zeit or '–'}")
    if stand.veraltet:
        zeilen.append("  veraltet oder leer – mit --aktualisieren frisch abgleichen")
    if stand.modelle:
        zeilen += [f"  {name}  {kennung}" for kennung, name in stand.modelle]
    else:
        zeilen.append("  keine Modelle ermittelt")
    return zeilen
