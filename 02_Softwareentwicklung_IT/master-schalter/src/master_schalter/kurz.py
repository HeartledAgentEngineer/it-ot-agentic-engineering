"""Master-Status für den Chat (`masterwechsel status`, Alias `kurz`): Limits, Lage, Themen, Sitzungen in wenigen Zeilen.

Gedacht für die Steuerung über Remote-Sitzungen, in denen das Taskleistensymbol nicht sichtbar ist. Der
Befehl **liest nur**: er misst nicht, schreibt nichts und startet nichts. `zeilen` ist eine reine Funktion
(alle Eingaben als Parameter), `sammeln` liest die Quellen.

Limits erscheinen als **Verbrauch** („… % verbraucht“, auf 0–100 begrenzt), nie als Rest. Was die Quelle
nicht weiß, steht als „unbekannt“ bzw. „neu, nicht gemessen“ da. Codex-Chat-Kennungen, Chattitel und Pfade
werden nicht ausgegeben; Sitzungskennungen nur gekürzt.
Scheiternde Messungen stehen mit Grund unter den Limitzeilen (`messfehler.json`, ohne Verfallsgrenze). Die Bausteine
(`thema_felder`, `messfehler_zeilen`, `_themen`, `_sitzungen`) nutzt auch das Übersichtsfenster.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path

from . import alle, anzeige, arbeitsweise, besitz, chat_zuordnung, modi, paare, rollen, signale, status, uebergabe, wartet
from .signale import Fenster, Kontingent

MAX_SITZUNGEN = 3
KENNUNG_KURZ = 8
ARBEITET_FRISCH = timedelta(minutes=30)   # älteres „arbeitet“ = Sitzung vermutlich ohne Stop beendet
WARTET = "Wartet worauf: nichts gemeldet"
WARTET_VERALTET = timedelta(hours=24)   # ältere Meldung: vermutlich vergessen, `warte THEMA --fertig`
MASTER_WERTE = ("claude", "codex", "hermes")   # wie `pruefkreis.py`
WERKZEUG_NAMEN = {"claude": "Claude", "codex": "Codex", "hermes": "Hermes", "workflow": "Workflow"}


@dataclass(frozen=True)
class Thema:
    name: str
    profil: modi.Profil
    besitzer: str | None        # None = unbekannt
    paar_aktiv: bool | None     # None = kein Paar
    pruefkreis_master: str | None = None   # was `pruefkreis.py` als Master liest; None = pruefkreis bricht ab
    arbeitsweise: str = "protokoll"   # protokoll | vibe | ? (Datei ungültig)


@dataclass(frozen=True)
class Sitzung:
    werkzeug: str
    kennung: str
    zustand: str
    zeit: datetime
    thema: str | None = None    # nur aus einer von Sebastian bestätigten Zuordnung (`zuordnung.json`)


def _uhr(wert: datetime, jetzt: datetime, zone: tzinfo | None) -> str:
    lokal = wert.astimezone(zone)
    gleicher_tag = lokal.date() == jetzt.astimezone(zone).date()
    return lokal.strftime("%H:%M" if gleicher_tag else "%d.%m. %H:%M")


verbraucht = anzeige.verbraucht   # Verbrauch eines Fensters, auf 0–100 begrenzt (gleiche Regel wie der Symbol-Tooltip)


def dauer(spanne: timedelta) -> str:
    """Restzeit kurz: „38 min“, „3 h 40 min“, „4 T 23 h“ (abgerundet auf Minuten)."""
    minuten = max(0, int(spanne.total_seconds() // 60))
    tage, rest_min = divmod(minuten, 24 * 60)
    stunden, minuten = divmod(rest_min, 60)
    if tage:
        return f"{tage} T {stunden} h"
    return f"{stunden} h {minuten} min" if stunden else f"{minuten} min"


def _fenster_text(f: Fenster | None, name: str, jetzt: datetime, zone: tzinfo | None) -> str:
    if f is None or f.prozent is None:
        return f"{name} unbekannt"
    if f.zurueckgesetzt:
        return f"{name} neu, nicht gemessen"
    text = f"{name} {verbraucht(f.prozent)} % verbraucht"
    if f.reset is None:
        return text
    return text + f" (Reset in {dauer(f.reset - jetzt)}, {_uhr(f.reset, jetzt, zone)})"


def _limit_zeile(k: Kontingent, jetzt: datetime, zone: tzinfo | None) -> str:
    if k.fehler:
        return f"  {k.master}: unbekannt ({k.fehler})"
    teile = [_fenster_text(k.fenster_nach_name(n), n, jetzt, zone) for n in ("5h", "Woche")]
    gemessen = f" · gemessen {_uhr(k.stand, jetzt, zone)}" if k.stand else " · Messzeit unbekannt"
    return f"  {k.master}: " + " · ".join(teile) + gemessen


def _ohne_klammern(text: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", text).strip()


def _rollen_zeile(lage: str | None, grund: str) -> str:
    besetzung = rollen.besetzung(lage)
    if besetzung is None:
        return f"Matrix: Lage unbekannt – {grund or 'Grund unbekannt'}"
    # Matrixspalten Thinker/Reviewer/Worker; „Master“ ist in dieser Ausgabe die Rolle je Thema.
    return (f"Matrix: Planer {_ohne_klammern(besetzung.thinker)} · Prüfer {_ohne_klammern(besetzung.reviewer)}"
            f" · Ausführer {_ohne_klammern(besetzung.worker)}")


def pruefkreis_master(laufend_ordner: Path, thema: str) -> str | None:
    """Master, den `pruefkreis.py` (`master_ermitteln`) für dieses Thema liest – None heißt: pruefkreis bricht ab.

    Gleiche Regel: `<name>.master` mit `<name>` = Thema oder längster Anfang vor einem Bindestrich; leere Datei =
    claude; unlesbar oder unbekanntes erstes Wort = None. Anders als die Besitzanzeige (`modi`) gilt eine fehlende
    Datei hier nicht als claude.
    """
    teile = thema.split("-")
    for laenge in range(len(teile), 0, -1):
        datei = laufend_ordner / f"{'-'.join(teile[:laenge])}.master"
        if not datei.is_file():
            continue
        try:
            text = datei.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            return None
        wer = text.split()[0] if text else "claude"
        return wer if wer in MASTER_WERTE else None
    return None


def pruefer_text(master: str | None) -> str:
    """Wer prüft – dieselbe Regel wie `pruefkreis.py` (Prüfer ≠ Master-Familie); `master` wie `pruefkreis_master`."""
    if master == "codex":
        return "Prüfer Hermes (Master Codex)"
    if master in ("claude", "hermes"):
        return "Prüfer Codex"
    return "Prüfer ? (pruefkreis braucht --master)"


def pruefer_vorschau(thema: str, vorgabe: str) -> list[str]:
    """Zwei Zeilen für `master-setzen`/`profil`: wer heute prüft und wer nach der Übergabe an `vorgabe` prüft.

    Nur lesend; maßgeblich ist wie bei `pruefkreis` der Besitz (`<thema>.master`), nicht die gespeicherte Vorgabe.
    """
    try:
        lokal = uebergabe.repo_wurzel()
        repo = uebergabe.haupt_wurzel(lokal)
        ordner = besitz.pfad(repo, paare.laufend_bilden(thema)).parent
    except (uebergabe.UebergabeFehler, paare.PaarFehler):
        return ["  Prüfer: unbekannt (Repo oder Thema nicht lesbar)"]
    jetzt = pruefkreis_master(ordner, thema)
    zeilen = [f"  Jetzt: {pruefer_text(jetzt)}"]
    if repo != lokal:   # die Schreibwege (`modi`) nutzen `repo_wurzel` – aus einem Worktree also nicht den Hauptbaum
        zeilen.append("  Hinweis: Aufruf aus einem Git-Worktree – master-setzen schreibt die Besitzmarke dort, "
                      "pruefkreis liest den Hauptarbeitsbaum")
    if vorgabe == modi.KONTINGENT:
        zeilen.append("  Nach Kontingent: Prüfer folgt dem Besitzer (Master Codex ⇒ Hermes, sonst Codex)")
    elif vorgabe != jetzt:
        zeilen.append(f"  Sobald {WERKZEUG_NAMEN.get(vorgabe, vorgabe)} den Besitz hat: {pruefer_text(vorgabe)}")
    return zeilen


def thema_felder(t: Thema, automatik_global: bool) -> tuple[str, str, str, str, str]:
    """Die fünf Angaben einer Themenzeile: (Master, Besitz, Prüfer, Ausführer, Auto) – auch für die Übersicht."""
    p = t.profil
    master = "nach Kontingent" if p.master == modi.KONTINGENT else WERKZEUG_NAMEN.get(p.master, p.master)
    besitz_text = f"Besitz {t.besitzer}" if t.besitzer else "Besitz unbekannt"
    ausfuehrer = WERKZEUG_NAMEN.get(p.worker, p.worker) + (f" {p.modell}" if p.modell else "")
    # Wie `automatik.py`: nur ein aktives Paar mit Master-Vorgabe „kontingent“ bei globaler Automatik.
    if t.paar_aktiv is None:
        auto = "kein Paar"
    elif p.master != modi.KONTINGENT:
        auto = "Auto aus (fester Master)"
    else:
        auto = "Auto an" if (t.paar_aktiv and automatik_global) else "Auto aus"
    return master, besitz_text, pruefer_text(t.pruefkreis_master), ausfuehrer, auto


def arbeitsweise_zusatz(wert: str) -> str:
    """Zusatz am Ende der Themenzeile: „ · VIBE“; bei Protokoll nichts, bei ungültiger Datei „ · Arbeitsweise ?“."""
    return {arbeitsweise.VIBE: " · VIBE", arbeitsweise.UNBEKANNT: " · Arbeitsweise ?"}.get(wert, "")


def _thema_zeile(t: Thema, automatik_global: bool) -> str:
    master, besitz_text, pruefer, ausfuehrer, auto = thema_felder(t, automatik_global)
    return (f"  {t.name}: Master {master} ({besitz_text}) · {pruefer} · Ausführer {ausfuehrer} · {auto}"
            + arbeitsweise_zusatz(t.arbeitsweise))


def _sitzung_zeile(s: Sitzung, jetzt: datetime, zone: tzinfo | None) -> str:
    zustand = s.zustand
    if zustand == status.ARBEITET and jetzt - s.zeit > ARBEITET_FRISCH:
        zustand = "arbeitet? (veraltet)"
    thema = f" · {s.thema}" if s.thema else " · Thema nicht zugeordnet"
    return (f"Sitzung {WERKZEUG_NAMEN.get(s.werkzeug, s.werkzeug)} {s.kennung[:KENNUNG_KURZ]}{thema}"
            f" · {zustand} · {_uhr(s.zeit, jetzt, zone)}")


def _wartet_zeile(m: wartet.Meldung, jetzt: datetime, zone: tzinfo | None) -> str:
    veraltet = " (veraltet?)" if jetzt - m.zeit > WARTET_VERALTET else ""
    return f"Wartet worauf: {m.thema}: {m.text} (seit {_uhr(m.zeit, jetzt, zone)}){veraltet}"


def messfehler_zeile(name: str, eintrag: signale.Messfehler, jetzt: datetime, zone: tzinfo | None) -> str:
    """„Claude-Messung scheitert seit 09:12 (letzter Versuch 09:42): <fester Text>“ – ohne Verfallsgrenze."""
    return (f"{name}-Messung scheitert seit {_uhr(eintrag.seit, jetzt, zone)}"
            f" (letzter Versuch {_uhr(eintrag.zuletzt, jetzt, zone)}): {eintrag.text}")


def messfehler_zeilen(messfehler: dict[str, signale.Messfehler], jetzt: datetime, zone: tzinfo | None) -> list[str]:
    return [messfehler_zeile(name, messfehler[quelle], jetzt, zone)
            for quelle, name in (("claude", "Claude"), ("codex", "Codex")) if quelle in messfehler]


def _naechstes(kontingente: list[Kontingent], schwelle: int, jetzt: datetime, zone: tzinfo | None) -> str:
    neu = [k.master for k in kontingente if not k.fehler and any(f.zurueckgesetzt for f in k.fenster)]
    if neu:
        return f"Als Nächstes: jetzt {', '.join(neu)} neu messen (Fenster zurückgesetzt)"
    kandidaten = [(f.reset, k.master, f.name) for k in kontingente if not k.fehler for f in k.fenster
                  if f.prozent is not None and f.prozent >= schwelle and f.reset and f.reset > jetzt]
    if not kandidaten:
        return "Als Nächstes: kein Limitwechsel absehbar"
    reset, master, name = min(kandidaten)
    return (f"Als Nächstes: {_uhr(reset, jetzt, zone)} (in {dauer(reset - jetzt)}) {master} {name} wieder frei"
            " (Reset, danach neu messen)")


def zeilen(kontingente: list[Kontingent], themen: list[Thema], sitzungen: list[Sitzung], *,
           schwelle: int, automatik_global: bool, jetzt: datetime, zone: tzinfo | None = None,
           hinweise: tuple[str, ...] = (), wartet_auf: tuple[wartet.Meldung, ...] = (),
           messfehler: dict[str, signale.Messfehler] | None = None) -> list[str]:
    """Der Master-Status als Textzeilen (ohne Tabellen, für schmale Bildschirme)."""
    claude, codex = kontingente
    lage = rollen.lage(claude, codex, schwelle)
    grund = rollen.lage_grund(claude, codex, schwelle)
    kopf = (f"Master-Status · {_uhr(jetzt, jetzt, zone)} · Lage {lage or '?'}"
            f" · Hauptschalter Automatik {'an' if automatik_global else 'aus'}")
    aus = [kopf, "Kontingent verbraucht:"]
    aus += [_limit_zeile(k, jetzt, zone) for k in kontingente]
    aus += messfehler_zeilen(messfehler or {}, jetzt, zone)
    aus.append(_rollen_zeile(lage, grund))
    aus.append("Themen:" if themen else "Themen: keine")
    aus += [_thema_zeile(t, automatik_global) for t in sorted(themen, key=lambda t: t.name)]
    neueste = sorted(sitzungen, key=lambda s: s.zeit, reverse=True)[:MAX_SITZUNGEN]
    aus += [_sitzung_zeile(s, jetzt, zone) for s in neueste] or ["Sitzungen: keine gemeldet"]
    aus.append(_naechstes(kontingente, schwelle, jetzt, zone))
    aus += [_wartet_zeile(m, jetzt, zone) for m in sorted(wartet_auf, key=lambda m: m.zeit)] or [WARTET]
    aus += list(hinweise)
    return aus


# --- Quellen lesen -----------------------------------------------------------

_OFFEN = object()   # „Repo noch nicht bestimmt“ (None heißt: nicht gefunden)


def repo_bestimmen() -> Path | None:
    """Hauptarbeitsbaum (aus einem Worktree über `commondir`); `None`, wenn das Repo nicht zu finden ist."""
    try:
        return uebergabe.haupt_wurzel(uebergabe.repo_wurzel())
    except uebergabe.UebergabeFehler:
        return None


def _themen(repo: Path | None | object = _OFFEN) -> tuple[list[Thema], list[str]]:
    """Themen mit Besitz; `repo` kann der Aufrufer vorgeben (die Übersicht liest und schreibt am selben Ort)."""
    hinweise: list[str] = []
    try:
        profile = modi.lesen()
    except (modi.ModusFehler, OSError):
        profile = {}
        hinweise.append("Hinweis: Themenprofile unlesbar")
    paar_liste = {p.thema: p for p in paare.lesen()}
    try:
        weisen, weisen_defekt = arbeitsweise.lesen(), False
    except arbeitsweise.ArbeitsweiseFehler:
        weisen, weisen_defekt = {}, True
        hinweise.append("Hinweis: Arbeitsweise-Datei ungültig – Arbeitsweise unbekannt (?)")
    if repo is _OFFEN:
        repo = repo_bestimmen()   # aus einem Worktree: Besitz liegt im Hauptbaum
    if repo is None:
        hinweise.append("Hinweis: Repo nicht gefunden – Besitz unbekannt")
    themen = []
    for name in sorted(set(profile) | set(paar_liste)):
        paar = paar_liste.get(name)
        besitzer = None
        if paar is not None and repo is not None:
            try:   # fehlende Datei = claude, Lesefehler = unbekannt (wie die fail-closed Prüfung in `modi`)
                besitzer = modi._besitzer_lesen(besitz.pfad(repo, paar.laufend))
            except modi.ModusFehler:
                besitzer = None
        # pruefkreis sucht immer im festen Übergabeordner, unabhängig vom Paar.
        pk_master = None if repo is None else pruefkreis_master(
            besitz.pfad(repo, paare.laufend_bilden(name)).parent, name)
        weise = arbeitsweise.UNBEKANNT if weisen_defekt else weisen.get(name, arbeitsweise.PROTOKOLL)
        themen.append(Thema(name, profile.get(name, modi.Profil()), besitzer,
                            None if paar is None else paar.aktiv, pk_master, weise))
    return themen, hinweise


def _sitzungen() -> list[Sitzung]:
    ordner = status.ordner()
    if not ordner.is_dir():
        return []
    zuordnung = chat_zuordnung.zuordnung_lesen()   # fehlt/kaputt ergibt {} – dann „Thema nicht zugeordnet“
    gefunden = []
    for pfad in ordner.glob("*.json"):
        werkzeug, _, kennung = pfad.stem.partition("-")
        stand = status.lesen(werkzeug, kennung)
        if stand is not None:
            gefunden.append(Sitzung(werkzeug, kennung, stand[0], stand[1], zuordnung.get(f"{werkzeug}:{kennung}")))
    return gefunden


def gemerkt_zeile(merk: dict[str, str] | None) -> str | None:
    """Merkstand des Sammelbefehls `alle` (nur Themen und Rollen); `None`, wenn nichts gemerkt ist."""
    if not merk:
        return None
    liste = ", ".join(f"{thema} {rolle}" for thema, rolle in sorted(merk.items()))
    return f"Gemerkt für „alle zurueck“: {liste}"


def _gemerkt_hinweis() -> list[str]:
    try:
        zeile = gemerkt_zeile(alle.gemerkt())
    except alle.MerkFehler:
        return ["Gemerkt: Merkdatei ungültig – `masterwechsel alle zurueck` nennt den Grund"]
    return [zeile] if zeile else []


def sammeln(jetzt: datetime | None = None, zone: tzinfo | None = None) -> list[str]:
    """Alle Quellen lesen (nichts schreiben, nichts messen) und den Master-Status bauen."""
    jetzt = jetzt or datetime.now(timezone.utc)
    themen, hinweise = _themen()
    hinweise = _gemerkt_hinweis() + hinweise
    return zeilen(signale.alle_lesen(jetzt=jetzt), themen, _sitzungen(), schwelle=anzeige.schwelle(),
                  automatik_global=anzeige.automatik_an(), jetzt=jetzt, zone=zone, hinweise=tuple(hinweise),
                  wartet_auf=tuple(wartet.alle_lesen()), messfehler=signale.messfehler_lesen())
