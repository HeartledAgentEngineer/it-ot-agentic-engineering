"""Kurzübersicht für den Chat (`masterwechsel kurz`): Limits, Lage, Themen, Sitzungen in wenigen Zeilen.

Gedacht für die Steuerung über Remote-Sitzungen, in denen das Taskleistensymbol nicht sichtbar ist. Der
Befehl **liest nur**: er misst nicht, schreibt nichts und startet nichts. `zeilen` ist eine reine Funktion
(alle Eingaben als Parameter), `sammeln` liest die Quellen.

Limits erscheinen als **Rest** (100 − Verbrauch, auf 0–100 begrenzt), nie als Verbrauch. Was die Quelle
nicht weiß, steht als „unbekannt“ bzw. „neu, nicht gemessen“ da. Codex-Chat-Kennungen, Chattitel und Pfade
werden nicht ausgegeben; Sitzungskennungen nur gekürzt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo

from . import anzeige, besitz, chat_zuordnung, modi, paare, rollen, signale, status, uebergabe
from .signale import Fenster, Kontingent

MAX_SITZUNGEN = 3
KENNUNG_KURZ = 8
ARBEITET_FRISCH = timedelta(minutes=30)   # älteres „arbeitet“ = Sitzung vermutlich ohne Stop beendet
WARTET = "Wartet worauf: noch keine Statusquelle"
WERKZEUG_NAMEN = {"claude": "Claude", "codex": "Codex", "hermes": "Hermes", "workflow": "Workflow"}


@dataclass(frozen=True)
class Thema:
    name: str
    profil: modi.Profil
    besitzer: str | None        # None = unbekannt
    paar_aktiv: bool | None     # None = kein Paar


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


def rest(prozent: float) -> int:
    """Rest eines Fensters aus dem Verbrauch: 76 % verbraucht ergibt 24 % Rest."""
    return round(max(0.0, min(100.0, 100.0 - prozent)))


def _fenster_text(f: Fenster | None, name: str, jetzt: datetime, zone: tzinfo | None) -> str:
    if f is None or f.prozent is None:
        return f"{name} unbekannt"
    if f.zurueckgesetzt:
        return f"{name} neu, nicht gemessen"
    text = f"{name} {rest(f.prozent)} %"
    return text + (f" (Reset {_uhr(f.reset, jetzt, zone)})" if f.reset else "")


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


def _thema_zeile(t: Thema, automatik_global: bool) -> str:
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
    return f"  {t.name}: Master {master} ({besitz_text}) · Ausführer {ausfuehrer} · {auto}"


def _sitzung_zeile(s: Sitzung, jetzt: datetime, zone: tzinfo | None) -> str:
    zustand = s.zustand
    if zustand == status.ARBEITET and jetzt - s.zeit > ARBEITET_FRISCH:
        zustand = "arbeitet? (veraltet)"
    thema = f" · {s.thema}" if s.thema else " · Thema nicht zugeordnet"
    return (f"Sitzung {WERKZEUG_NAMEN.get(s.werkzeug, s.werkzeug)} {s.kennung[:KENNUNG_KURZ]}{thema}"
            f" · {zustand} · {_uhr(s.zeit, jetzt, zone)}")


def _naechstes(kontingente: list[Kontingent], schwelle: int, jetzt: datetime, zone: tzinfo | None) -> str:
    neu = [k.master for k in kontingente if not k.fehler and any(f.zurueckgesetzt for f in k.fenster)]
    if neu:
        return f"Als Nächstes: jetzt {', '.join(neu)} neu messen (Fenster zurückgesetzt)"
    kandidaten = [(f.reset, k.master, f.name) for k in kontingente if not k.fehler for f in k.fenster
                  if f.prozent is not None and f.prozent >= schwelle and f.reset and f.reset > jetzt]
    if not kandidaten:
        return "Als Nächstes: kein Limitwechsel absehbar"
    reset, master, name = min(kandidaten)
    return f"Als Nächstes: {_uhr(reset, jetzt, zone)} {master} {name} wieder frei (Reset, danach neu messen)"


def zeilen(kontingente: list[Kontingent], themen: list[Thema], sitzungen: list[Sitzung], *,
           schwelle: int, automatik_global: bool, jetzt: datetime, zone: tzinfo | None = None,
           hinweise: tuple[str, ...] = ()) -> list[str]:
    """Die Kurzübersicht als Textzeilen (ohne Tabellen, für schmale Bildschirme)."""
    claude, codex = kontingente
    lage = rollen.lage(claude, codex, schwelle)
    grund = rollen.lage_grund(claude, codex, schwelle)
    kopf = (f"Master-Schalter · {_uhr(jetzt, jetzt, zone)} · Lage {lage or '?'}"
            f" · Automatik {'an' if automatik_global else 'aus'}")
    aus = [kopf, "Rest:"]
    aus += [_limit_zeile(k, jetzt, zone) for k in kontingente]
    aus.append(_rollen_zeile(lage, grund))
    aus.append("Themen:" if themen else "Themen: keine")
    aus += [_thema_zeile(t, automatik_global) for t in sorted(themen, key=lambda t: t.name)]
    neueste = sorted(sitzungen, key=lambda s: s.zeit, reverse=True)[:MAX_SITZUNGEN]
    aus += [_sitzung_zeile(s, jetzt, zone) for s in neueste] or ["Sitzungen: keine gemeldet"]
    aus.append(_naechstes(kontingente, schwelle, jetzt, zone))
    aus.append(WARTET)
    aus += list(hinweise)
    return aus


# --- Quellen lesen -----------------------------------------------------------

def _themen() -> tuple[list[Thema], list[str]]:
    hinweise: list[str] = []
    try:
        profile = modi.lesen()
    except (modi.ModusFehler, OSError):
        profile = {}
        hinweise.append("Hinweis: Themenprofile unlesbar")
    paar_liste = {p.thema: p for p in paare.lesen()}
    try:
        repo = uebergabe.repo_wurzel()
    except uebergabe.UebergabeFehler:
        repo = None
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
        themen.append(Thema(name, profile.get(name, modi.Profil()), besitzer,
                            None if paar is None else paar.aktiv))
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


def sammeln(jetzt: datetime | None = None, zone: tzinfo | None = None) -> list[str]:
    """Alle Quellen lesen (nichts schreiben, nichts messen) und die Kurzübersicht bauen."""
    jetzt = jetzt or datetime.now(timezone.utc)
    themen, hinweise = _themen()
    return zeilen(signale.alle_lesen(jetzt=jetzt), themen, _sitzungen(), schwelle=anzeige.schwelle(),
                  automatik_global=anzeige.automatik_an(), jetzt=jetzt, zone=zone, hinweise=tuple(hinweise))
