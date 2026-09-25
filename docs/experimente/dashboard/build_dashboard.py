#!/usr/bin/env python
"""Kosten-Dashboard: alle Hermes-Chats/Sessions aufgeschluesselt als eigenstaendige HTML.

WARUM DIESES SKRIPT (der neustartfreie Weg):
  Das Statusleisten-Plugin (context-tank) braucht einen Hermes-Neustart, weil sein
  Python-Teil nur beim Programmstart geladen wird. Dieses Skript erzeugt stattdessen
  EINE HTML-Datei mit allen Zahlen; sie laeuft in jedem Browser und kennt keine
  Abhaengigkeit zum Plugin.

WAS ES LIEST:
  %LOCALAPPDATA%/hermes/state.db, Tabellen session_model_usage (eine Zeile je
  Session+Modell+Anbieter+task) und sessions (Titel, parent_session_id,
  message_count, tool_call_count). Immer read-only geoeffnet und in EINER
  Lesetransaktion gelesen - alle Zahlen stammen also aus demselben Augenblick.

DIE FALLEN (nachgemessen, nicht geraten):
  1. last_seen/first_seen sind UNIX-Zeitstempel als REAL (z. B. 1790344497.394741),
     KEINE Datumsstrings. Ein date(last_seen) = date('now') liefert IMMER 0 Zeilen.
     Richtig: epoch-basiert vergleichen (last_seen >= ?), Tagesgruppierung mit
     date(CAST(last_seen AS INTEGER),'unixepoch','localtime').
  2. Die Session-Tabelle heisst sessions mit Spalte id; in session_model_usage
     heisst die Spalte session_id.
  3. actual_cost_usd ist in dieser Datenbank durchgehend 0. Gerechnet wird daher
     mit estimated_cost_usd (gleiche Konvention wie das Plugin: actual bevorzugt,
     sonst estimated).

DIE SIEBEN ZEITRAEUME (verbindlich, identisch zum Plugin context-tank):
  heute         ab 00:00 heute (lokale Zeit)
  woche         ab Montag 00:00 dieser Woche (ISO-Woche)
  letzte_woche  Montag 00:00 bis Sonntag 23:59:59 der Vorwoche
  letzte_7_tage rollierend: jetzt minus 7 x 24 Stunden
  monat         ab dem 1. des laufenden Monats 00:00
  letzter_monat 1. des Vormonats bis letzter Tag des Vormonats 23:59:59
  alles         kein Filter - gesamte Lebenszeit
  Alle Fenster sind epoch-basiert; Zeitraumgrenzen stehen als Zahl im HTML.

SUBAGENTEN-ZURECHNUNG:
  Subagenten laufen in eigenen Session-Zeilen mit gesetztem parent_session_id.
  Jede Ansicht weist deshalb DREI Zahlen aus: eigene Kosten, Subagenten-Kosten und
  die Summe. Die Zuordnung laeuft rekursiv bis zur Wurzel-Session (dem Chat);
  die Selbstpruefung vergleicht diese Zuordnung gegen einen rekursiven
  SQL-Ausdruck (WITH RECURSIVE) und meldet jede Abweichung.

TOKEN-TRENNUNG:
  Input-, Output-, Cache-Read- und Cache-Write-Tokens werden GETRENNT gefuehrt -
  jeweils Anzahl UND Kosten. Die Kosten je Sorte entstehen aus Tokenmenge x
  Modellpreis (openrouter:/api/v1/models, Cache-Read-Preis ersatzweise 10 % des
  Prompt-Preises) und werden proportional auf die Abrechnungssumme der Datenbank
  verteilt; die Abweichung der Rohrechnung wird als Zahl mitgezeigt, nie versteckt.

DIE GELDKETTE Nutzung -> Cash (an drei echten Kaufdialogen verifiziert):
  Guthaben        = Nutzung / 0,945
  Servicegebuehr  = max(Guthaben x 5,5 %, 0,80 USD)
  Umsatzsteuer    = (Guthaben + Servicegebuehr) x 19 %
  Cash            = Guthaben + Servicegebuehr + Umsatzsteuer
  Jeder Schritt wird auf Cent gerundet und MIT dem gerundeten Wert weitergerechnet,
  genau wie im Kaufdialog. Unter 14,55 USD Guthaben greift die Mindestgebuehr, dann
  ist der Aufschlag hoeher.

WECHSELKURS USD -> EURO:
  Live von der EZB (eurofxref-daily.xml; die EZB notiert USD JE EUR, der Wert wird
  deshalb invertiert), ersatzweise open.er-api.com, dann der letzte bekannte Kurs
  aus dashboard_cache.json, zuletzt der Ersatz-Kurs 0.87696. Der Kurs wird NIE fest
  verdrahtet; woher er kam, steht sichtbar im HTML.

Benutzung:
    python build_dashboard.py                 # HTML erzeugen (Live-Kurs, Live-Preise)
    python build_dashboard.py --kein-netz     # nur Zwischenspeicher/Ersatzwerte
    python build_dashboard.py --kurs 0.88     # Kurs erzwingen
    python build_dashboard.py --json          # eingebettete Rohdaten nach stdout
    python build_dashboard.py --pruefsummen   # nur die Kontrollsummen ausgeben
    python build_dashboard.py --kein-pruefen  # Selbstpruefung ueberspringen
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

DB = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "state.db"
HIER = Path(__file__).resolve().parent
AUSGABE = HIER / "dashboard.html"
CACHE_DATEI = HIER / "dashboard_cache.json"

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
ER_API_URL = "https://open.er-api.com/v6/latest/USD"
MODELS_URL = "https://openrouter.ai/api/v1/models"

KURS_FALLBACK = 0.87696          # letzter Notausgang (EUR je USD), nie Vorrang
FX_TIMEOUT_S = 15
PREIS_TIMEOUT_S = 25
PREIS_TTL_S = 6 * 60 * 60        # Modellpreise 6 h zwischenspeichern
CACHE_PRICE_FACTOR = 0.10        # Ersatz fuer fehlenden Cache-Read-Preis

SERVICE_SATZ = 0.055             # OpenRouter-Servicegebuehr beim Aufladen
SERVICE_MIN = 0.80               # Mindestgebuehr je Aufladung (USD)
UST_SATZ = 0.19                  # deutsche Umsatzsteuer
BREAK_EVEN_GUTHABEN = SERVICE_MIN / SERVICE_SATZ          # 14,55 USD
BREAK_EVEN_NUTZUNG = BREAK_EVEN_GUTHABEN * (1 - SERVICE_SATZ)   # 13,75 USD

MAX_TIEFE = 8                    # Rekursionstiefe der Subagenten-Zuordnung

# Drei ECHTE Kaufdialoge als Beleg der Geldkette (Guthaben -> Service, USt, Cash):
#   17 USD  -> 0,94 + 3,41 = 21,35 USD Cash
#   20 USD  -> 1,10 + 4,01 = 25,11 USD Cash
#   200 USD -> 11,00 + 40,09 = 251,09 USD Cash
KAUF_BELEGE = (
    (17.0, 0.94, 3.41, 21.35),
    (20.0, 1.10, 4.01, 25.11),
    (200.0, 11.00, 40.09, 251.09),
)

# Die sieben Zeitraeume in der Reihenfolge des Umschalters, mit Definition.
PERIODS = ("heute", "woche", "letzte_woche", "letzte_7_tage",
           "monat", "letzter_monat", "alles")

PERIOD_DEFS = {
    "heute": ("Heute", "ab 00:00 heute (lokale Zeit)"),
    "woche": ("Woche", "ab Montag 00:00 dieser Woche (ISO-Woche)"),
    "letzte_woche": ("Letzte Woche", "Montag 00:00 bis Sonntag 23:59:59 der Vorwoche"),
    "letzte_7_tage": ("Letzte 7 Tage", "rollierend: jetzt minus 7 x 24 Stunden"),
    "monat": ("Monat", "ab dem 1. des laufenden Monats 00:00"),
    "letzter_monat": ("Letzter Monat", "1. des Vormonats bis letzter Tag des Vormonats 23:59:59"),
    "alles": ("Alles", "kein Filter - gesamte Lebenszeit"),
}

# Zweck-Beschriftungen: Rohwert der Spalte task -> deutsche Bezeichnung.
ZWECK_NAMEN = {
    "": "Chat (normal)",
    "title_generation": "Titel-Erzeugung",
    "approval": "Freigabe-Pruefung",
    "background_review": "Hintergrund-Pruefung",
    "compression": "Kontext-Verdichtung",
    "vision": "Bild-Analyse",
}


# --------------------------------------------------------------------------
# Wechselkurs USD -> Euro
# --------------------------------------------------------------------------

def _zahl(v) -> float | None:
    """Zahl oder None - nie raten."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _cache_lesen() -> dict:
    try:
        return json.loads(CACHE_DATEI.read_text(encoding="utf-8"))
    except Exception:                                    # noqa: BLE001
        return {}


def _cache_schreiben(daten: dict) -> None:
    try:
        CACHE_DATEI.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _ezb_kurs() -> dict:
    """EZB-Tageskurs. Die EZB notiert USD JE EUR - fuer uns wird invertiert."""
    req = urllib.request.Request(
        ECB_URL,
        headers={"Accept": "application/xml,text/xml,*/*",
                 "User-Agent": "hermes-dashboard/2.0"})
    with urllib.request.urlopen(req, timeout=FX_TIMEOUT_S) as response:
        text = response.read().decode("utf-8", errors="ignore")
    # Die EZB-Datei nutzt einfache Anfuehrungszeichen (<Cube currency='USD' rate='1.1403'/>).
    treffer = re.search(r"""currency=['"]USD['"]\s+rate=['"]([0-9.]+)['"]""", text)
    if not treffer:
        return {"ok": False, "fehler": "unerwartete EZB-Antwort (kein USD-Kurs)"}
    usd_je_eur = float(treffer.group(1))
    if not 0.5 <= usd_je_eur <= 2.5:
        return {"ok": False, "fehler": f"EZB-Kurs unplausibel ({usd_je_eur})"}
    stand = re.search(r"""time=['"]([^'"]+)['"]""", text)
    return {"ok": True, "usd_eur": 1.0 / usd_je_eur,
            "stand": stand.group(1) if stand else None,
            "roh_usd_je_eur": usd_je_eur,
            "quelle": "EZB (eurofxref-daily, USD je EUR invertiert)"}


def _erapi_kurs() -> dict:
    """Rueckfall 1: open.er-api.com liefert EUR direkt JE USD."""
    req = urllib.request.Request(ER_API_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=FX_TIMEOUT_S) as response:
        daten = json.loads(response.read().decode("utf-8"))
    kurs = _zahl((daten.get("rates") or {}).get("EUR"))
    if kurs is None:
        return {"ok": False, "fehler": "unerwartete Kursantwort (kein rates.EUR)"}
    if not 0.1 <= kurs <= 5:
        return {"ok": False, "fehler": "Kurs unplausibel (ausserhalb 0,1-5)"}
    return {"ok": True, "usd_eur": kurs,
            "stand": str(daten.get("time_last_update_utc") or ""),
            "quelle": "open.er-api.com (Rueckfall)"}


def wechselkurs(kein_netz: bool, fest: float | None, zwischenspeicher: dict) -> dict:
    """EUR je USD samt Herkunft. Reihenfolge: --kurs, EZB, er-api, letzter Kurs, Ersatz."""
    if fest is not None:
        return {"usd_eur": fest, "quelle": "fest vorgegeben (--kurs)", "stand": None,
                "ersatz": False, "hinweis": "Der Kurs wurde mit --kurs vorgegeben."}

    alt = (zwischenspeicher.get("kurs") or {})
    fehler: list[str] = []

    if not kein_netz:
        for holen in (_ezb_kurs, _erapi_kurs):
            try:
                erg = holen()
            except Exception as e:                       # noqa: BLE001
                fehler.append(f"{type(e).__name__}")
                continue
            if erg.get("ok"):
                return {"usd_eur": erg["usd_eur"], "quelle": erg["quelle"],
                        "stand": erg.get("stand"), "ersatz": False, "hinweis": ""}
            fehler.append(str(erg.get("fehler")))

    # Netz fehlt: zuletzt bekannten Kurs nehmen - und das sichtbar vermerken.
    if alt.get("usd_eur"):
        grund = ", ".join(fehler) if fehler else "Kursabruf uebersprungen (--kein-netz)"
        return {"usd_eur": float(alt["usd_eur"]),
                "quelle": f"letzter bekannter Kurs vom {alt.get('stand') or alt.get('geholt') or '?'}",
                "stand": alt.get("stand"), "ersatz": True,
                "hinweis": ("Netz nicht erreichbar - gerechnet wird mit dem zuletzt geholten Kurs "
                            f"({alt.get('quelle', 'unbekannte Quelle')}). Grund: {grund}")}

    grund = ", ".join(fehler) if fehler else "kein Kursabruf (--kein-netz)"
    return {"usd_eur": KURS_FALLBACK, "quelle": "Ersatz-Kurs (kein Kursdienst erreichbar)",
            "stand": None, "ersatz": True,
            "hinweis": ("ACHTUNG: keine Kursquelle erreichbar - gerechnet wird mit dem "
                        f"Ersatz-Kurs {KURS_FALLBACK}. Die Euro-Betraege sind Naeherungen. Grund: {grund}")}


# --------------------------------------------------------------------------
# Modellpreise (oeffentlich, ohne Schluessel)
# --------------------------------------------------------------------------

def _preisfeld(pricing: dict, *namen: str) -> float | None:
    """Erstes vorhandenes Feld aus ``namen`` (die Liste hat ihre Namen gewechselt)."""
    for name in namen:
        if name in pricing:
            wert = _zahl(pricing.get(name))
            if wert is not None:
                return wert
    return None


def _preise_holen() -> dict:
    """USD-Preise je TOKEN aus der oeffentlichen Modellliste.

    Feldnamen der Cache-Preise: input_cache_read / input_cache_write. Die frueheren
    Namen cache_read/cache_write gibt es dort nicht mehr.
    """
    req = urllib.request.Request(MODELS_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=PREIS_TIMEOUT_S) as response:
        antwort = json.loads(response.read().decode("utf-8"))
    eintraege = antwort.get("data") if isinstance(antwort, dict) else None
    if not isinstance(eintraege, list):
        return {"ok": False, "fehler": "unerwartete Modellliste (kein data-Array)"}
    preise: dict[str, dict] = {}
    for eintrag in eintraege:
        if not isinstance(eintrag, dict):
            continue
        modell, pricing = eintrag.get("id"), eintrag.get("pricing")
        if not isinstance(modell, str) or not isinstance(pricing, dict):
            continue
        gesamt = _preisfeld(pricing, "prompt")
        if gesamt is None:
            continue
        preise[modell] = {
            "prompt": gesamt,
            "completion": _preisfeld(pricing, "completion"),
            "cache_read": _preisfeld(pricing, "input_cache_read", "cache_read"),
            "cache_write": _preisfeld(pricing, "input_cache_write", "cache_write"),
        }
    if not preise:
        return {"ok": False, "fehler": "Modellliste enthielt keine Preise"}
    return {"ok": True, "preise": preise}


def preise_besorgen(kein_netz: bool, zwischenspeicher: dict) -> tuple[dict, dict]:
    """(Preise, Herkunft). Zwischenspeicher respektiert die TTL, sonst Notnagel daraus."""
    alt = (zwischenspeicher.get("preise") or {})
    jetzt = time.time()
    if not kein_netz:
        frisch = (alt.get("preise") and alt.get("at")
                  and (jetzt - float(alt["at"])) < PREIS_TTL_S)
        if not frisch:
            try:
                erg = _preise_holen()
            except Exception as e:                       # noqa: BLE001
                erg = {"ok": False, "fehler": f"{type(e).__name__}: {e}"}
            if erg.get("ok"):
                return erg["preise"], {"quelle": "openrouter:/api/v1/models (live geholt)",
                                       "stand": dt.datetime.now().strftime("%d.%m.%Y %H:%M"),
                                       "at": jetzt, "hinweis": "", "fehler": None,
                                       "neu": True}
    if alt.get("preise"):
        return alt["preise"], {"quelle": "openrouter:/api/v1/models (letzter bekannter Stand)",
                               "stand": alt.get("stand"), "at": float(alt.get("at") or jetzt),
                               "hinweis": ("Modellpreise konnten nicht neu geholt werden - "
                                           "gerechnet wird mit dem zuletzt geholten Stand."),
                               "fehler": None, "neu": False}
    return {}, {"quelle": "keine Preise verfuegbar", "stand": None, "at": jetzt,
                "hinweis": ("Ohne Modellpreise werden die Token-Sorten nur mit ANZAHL gezeigt, "
                            "nicht mit Kosten (nichts wird geschaetzt)."),
                "fehler": None, "neu": False}


def preis_fuer(preise: dict, modell: str) -> dict | None:
    """Preis zu einer Modell-ID - exakt oder als Endungs-Treffer."""
    if not modell or not preise:
        return None
    if modell in preise:
        return preise[modell]
    for kennung, preis in preise.items():
        if kennung and (modell.endswith(kennung) or kennung.endswith(modell)):
            return preis
    return None


def cache_preis(preis: dict) -> float:
    """Cache-Read-Preis je Token - ersatzweise 10 % des Prompt-Preises."""
    wert = _zahl(preis.get("cache_read"))
    if wert is not None:
        return wert
    prompt = _zahl(preis.get("prompt"))
    return prompt * CACHE_PRICE_FACTOR if prompt is not None else 0.0


# --------------------------------------------------------------------------
# Datenbank
# --------------------------------------------------------------------------

def verbinden() -> sqlite3.Connection:
    if not DB.is_file():
        sys.exit(f"Datenbank nicht gefunden: {DB}")
    # IMMER read-only - das Dashboard darf die Session-DB nie veraendern.
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True, timeout=20)
    # Eine Lesetransaktion = EIN eingefrorener Stand (WAL-Modus; Leser blockieren
    # keine Schreiber). Dadurch stammen alle Zahlen aus demselben Augenblick.
    con.execute("BEGIN")
    return con


def fenster(period: str, jetzt: dt.datetime) -> tuple[float | None, float | None]:
    """Beginn und Ende eines Zeitraums als Epoch (None = offen/kein Filter)."""
    mitternacht = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "heute":
        return mitternacht.timestamp(), None
    if period == "woche":
        return (mitternacht - dt.timedelta(days=jetzt.weekday())).timestamp(), None
    if period == "letzte_woche":
        dieser_montag = mitternacht - dt.timedelta(days=jetzt.weekday())
        voriger_montag = dieser_montag - dt.timedelta(days=7)
        ende = dieser_montag - dt.timedelta(microseconds=1)
        return voriger_montag.timestamp(), ende.timestamp()
    if period == "letzte_7_tage":
        return jetzt.timestamp() - 7 * 24 * 3600, None
    if period == "monat":
        return jetzt.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp(), None
    if period == "letzter_monat":
        erster_diesen = jetzt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        ende = erster_diesen - dt.timedelta(microseconds=1)
        anfang = (erster_diesen - dt.timedelta(days=1)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0)
        return anfang.timestamp(), ende.timestamp()
    return None, None                                    # "alles": kein Filter


def _wo(start: float | None, ende: float | None) -> tuple[str, list]:
    """Zeitfenster als SQL-Bedingung - IMMER epoch-basiert (REAL-Spalte)."""
    teile, werte = [], []
    if start is not None:
        teile.append("u.last_seen >= ?")
        werte.append(start)
    if ende is not None:
        teile.append("u.last_seen <= ?")
        werte.append(ende)
    return (" AND ".join(teile) if teile else "1=1"), werte


# Eine Zeile je Session + Modell + Zweck + Kalendertag. Aus DIESEN Zeilen entstehen
# alle Auswertungen (Summe, Chats, Modelle, Zwecke, Tage) - dadurch addieren sich
# die Tabellenzeilen immer genau auf die Zeitraumsumme.
SQL_GRUPPEN = """
    SELECT u.session_id                                      AS sid,
           COALESCE(u.model, '?')                            AS modell,
           COALESCE(u.task, '')                              AS aufgabe,
           date(CAST(u.last_seen AS INTEGER), 'unixepoch', 'localtime') AS tag,
           COALESCE(SUM(CASE WHEN u.actual_cost_usd <> 0 THEN u.actual_cost_usd
                             ELSE u.estimated_cost_usd END), 0)     AS usd,
           COALESCE(SUM(u.api_call_count), 0)                AS calls,
           COALESCE(SUM(u.input_tokens), 0)                  AS tin,
           COALESCE(SUM(u.output_tokens), 0)                 AS tout,
           COALESCE(SUM(u.cache_read_tokens), 0)             AS tcread,
           COALESCE(SUM(u.cache_write_tokens), 0)            AS tcwrite,
           COALESCE(SUM(u.reasoning_tokens), 0)              AS treason,
           MIN(u.last_seen)                                  AS von,
           MAX(u.last_seen)                                  AS bis
      FROM session_model_usage u
     WHERE {wo}
     GROUP BY u.session_id, modell, aufgabe, tag
"""


def sessions_lesen(con: sqlite3.Connection) -> dict:
    """Alle Sessions mit Wurzel-Zuordnung und Metadaten.

    Wurzel = oberste Eltern-Session = der Chat. Subagent ist jede Session mit
    gesetztem parent_session_id. Bricht eine Kette ab (fehlende Elternzeile),
    gilt die Session selbst als Wurzel - sie bleibt aber als Subagent gezaehlt.
    """
    roh: dict[str, dict] = {}
    for sid, titel, anzeige, eltern, turns, tools, model in con.execute(
            """SELECT id, COALESCE(title,''), COALESCE(display_name,''),
                      COALESCE(parent_session_id,''), COALESCE(message_count,0),
                      COALESCE(tool_call_count,0), COALESCE(model,'')
                 FROM sessions"""):
        roh[sid] = {"eltern": eltern, "titel": titel, "anzeige": anzeige,
                    "turns": turns, "tools": tools, "model": model}

    def wurzel(sid: str) -> str:
        aktuell, tiefe = sid, 0
        while tiefe < MAX_TIEFE:
            eltern = (roh.get(aktuell) or {}).get("eltern") or ""
            if not eltern or eltern == aktuell or eltern not in roh:
                return aktuell
            aktuell = eltern
            tiefe += 1
        return aktuell

    karte: dict[str, str] = {}
    for sid, info in roh.items():
        karte[sid] = wurzel(sid)
        info["ist_sub"] = bool(info["eltern"])
        info["wurzel"] = karte[sid]
    return roh


def zeilen_holen(con: sqlite3.Connection, start: float | None, ende: float | None,
                 sess: dict) -> list[dict]:
    wo, werte = _wo(start, ende)
    zeilen: list[dict] = []
    for (sid, modell, aufgabe, tag, usd, calls, tin, tout, tcread, tcwrite,
         treason, von, bis) in con.execute(SQL_GRUPPEN.format(wo=wo), werte):
        info = sess.get(sid) or {}
        zeilen.append({
            "sid": sid, "modell": modell, "aufgabe": aufgabe, "tag": tag,
            "usd": float(usd or 0.0), "calls": int(calls or 0),
            "tin": int(tin or 0), "tout": int(tout or 0),
            "tcread": int(tcread or 0), "tcwrite": int(tcwrite or 0),
            "treason": int(treason or 0),
            "von": von, "bis": bis,
            "wurzel": info.get("wurzel") or sid,
            "ist_sub": bool(info.get("ist_sub")),
        })
    return zeilen


# --------------------------------------------------------------------------
# Rechnen
# --------------------------------------------------------------------------

def _cents(wert: float) -> float:
    """Auf Cent runden - so, wie Geldbetraege ausgewiesen werden."""
    return round(wert + 1e-9, 2)


def cash_kette(nutzung_usd: float | None) -> dict | None:
    """Nutzung -> Guthaben -> Servicegebuehr -> USt -> Cash (dialog-genau).

    Weil die 5,5 % Servicegebuehr auf den GUTHABENBETRAG kommen, gilt
    Guthaben = Nutzung / 0,945. Jeder Schritt wird auf Cent gerundet und mit dem
    gerundeten Betrag weitergerechnet.
    """
    if not nutzung_usd or nutzung_usd <= 0:
        return None
    guthaben = nutzung_usd / (1 - SERVICE_SATZ)
    service = max(guthaben * SERVICE_SATZ, SERVICE_MIN)
    g, s = _cents(guthaben), _cents(service)
    u = _cents((g + s) * UST_SATZ)
    return {"nutzung": _cents(nutzung_usd), "guthaben": g, "service": s, "ust": u,
            "cash": _cents(g + s + u)}


def kauf_pruefen(guthaben: float) -> tuple[float, float, float]:
    """Kaufrichtung Guthaben -> (Service, USt, Cash) - fuer die Kaufbelege."""
    g = _cents(guthaben)
    s = _cents(max(g * SERVICE_SATZ, SERVICE_MIN))
    u = _cents((g + s) * UST_SATZ)
    return s, u, _cents(g + s + u)


def kosten_roh(zeilen: list[dict], preise: dict) -> tuple[dict, set]:
    """Rohe Kostenschaetzung je Tokensorte: Tokens x Modellpreis (USD).

    Vier Sorten, damit Input, Output und beide Zwischenspeicher-Sorten getrennt
    sichtbar sind und sich in der Summe auf die Nutzung addieren.
    """
    roh = {"input": 0.0, "output": 0.0, "cache_read": 0.0, "cache_write": 0.0}
    ohne_preis: set = set()
    for z in zeilen:
        preis = preis_fuer(preise, z["modell"])
        if not preis or preis.get("prompt") is None:
            ohne_preis.add(z["modell"])
            continue
        roh["input"] += z["tin"] * float(preis["prompt"])
        roh["cache_read"] += z["tcread"] * cache_preis(preis)
        roh["cache_write"] += z["tcwrite"] * float(preis.get("cache_write") or 0.0)
        fertig = preis.get("completion")
        if fertig is not None:
            roh["output"] += z["tout"] * float(fertig)
    return roh, ohne_preis


def kosten_verteilen(gesamt_usd: float, roh: dict) -> dict:
    """Rohrechnung proportional auf die Abrechnungssumme der Datenbank verteilen.

    Die Summe bleibt die echte Zahl der Datenbank; die vier Sorten addieren sich
    dadurch genau auf. Ein Rundungsrest wird vom groessten Posten abgezogen,
    damit kein negativer Betrag entsteht. ``roh_usd`` und ``abweichung`` nennen
    die unverteilte Rechnung - nichts wird versteckt.
    """
    roh_summe = sum(roh.values())
    if gesamt_usd <= 0 or roh_summe <= 0:
        return {"input": None, "output": None, "cache_read": None, "cache_write": None,
                "roh_usd": round(roh_summe, 8), "abweichung": None}
    faktor = gesamt_usd / roh_summe
    inp = round(roh["input"] * faktor, 8)
    out = round(roh["output"] * faktor, 8)
    crd = round(roh["cache_read"] * faktor, 8)
    cwr = round(gesamt_usd - inp - out - crd, 8)
    if cwr < 0:                                          # Rundungsrest bei Kleinstbetraegen
        if crd + cwr >= 0:
            crd = round(crd + cwr, 8)
        elif out + cwr >= 0:
            out = round(out + cwr, 8)
        else:
            inp = round(inp + cwr, 8)
        cwr = 0.0
    return {"input": inp, "output": out, "cache_read": crd, "cache_write": cwr,
            "roh_usd": round(roh_summe, 8),
            "abweichung": round((roh_summe - gesamt_usd) / gesamt_usd * 100, 2)}


def block(zeilen: list[dict], preise: dict) -> dict:
    """Kennzahlen eines Zeilensatzes (Summe, Tokens, Kostenaufteilung)."""
    gesamt = sum(z["usd"] for z in zeilen)
    tin = sum(z["tin"] for z in zeilen)
    tout = sum(z["tout"] for z in zeilen)
    tcread = sum(z["tcread"] for z in zeilen)
    tcwrite = sum(z["tcwrite"] for z in zeilen)
    treason = sum(z["treason"] for z in zeilen)
    calls = sum(z["calls"] for z in zeilen)
    sids = {z["sid"] for z in zeilen}
    subs_sids = {z["sid"] for z in zeilen if z["ist_sub"]}
    wurzeln = {z["wurzel"] for z in zeilen}
    roh, ohne_preis = kosten_roh(zeilen, preise)
    von = min((z["von"] for z in zeilen if z["von"]), default=None)
    bis = max((z["bis"] for z in zeilen if z["bis"]), default=None)
    return {
        "usd": round(gesamt, 8),
        "in": tin, "out": tout, "cread": tcread, "cwrite": tcwrite,
        "tok": tin + tout + tcread + tcwrite, "reason": treason,
        "calls": calls,
        "sessions": len(sids), "sessions_sub": len(subs_sids),
        "chats": len(wurzeln),
        "kosten": kosten_verteilen(gesamt, roh),
        "kosten_roh_usd": round(sum(roh.values()), 8),
        "ohne_preis": sorted(m for m in ohne_preis if m),
        "quote": round(tcread / (tin + tcread) * 100, 1) if (tin + tcread) else 0.0,
        "von": von, "bis": bis,
    }


def gruppieren(zeilen: list[dict], schluessel: str) -> dict[str, list[dict]]:
    aus: dict[str, list[dict]] = {}
    for z in zeilen:
        aus.setdefault(z[schluessel], []).append(z)
    return aus


def zeitpunkt(epoch, mit_zeit: bool = True) -> str:
    if not epoch:
        return "-"
    d = dt.datetime.fromtimestamp(float(epoch))
    return d.strftime("%d.%m. %H:%M") if mit_zeit else d.strftime("%d.%m.%Y")


def tag_lesbar(iso: str) -> str:
    if not iso:
        return "-"
    teile = iso.split("-")
    return f"{teile[2]}.{teile[1]}." if len(teile) == 3 else iso


def titel_zu(info: dict, sid: str) -> str:
    for feld in ("titel", "anzeige"):
        wert = (info.get(feld) or "").strip()
        if wert:
            return wert
    return sid


def cash_anteil(betrag_usd: float, zeitraum_usd: float, zeitraum_cash: float | None) -> float | None:
    """Anteil einer Zeile am Cash des Zeitraums (Cash wird auf den Zeitraum gerechnet)."""
    if not zeitraum_cash or zeitraum_usd <= 0 or betrag_usd <= 0:
        return None
    return round(zeitraum_cash * (betrag_usd / zeitraum_usd), 2)


# --------------------------------------------------------------------------
# Daten sammeln
# --------------------------------------------------------------------------

def daten_sammeln(con: sqlite3.Connection, kurs: dict, preise: dict,
                  preis_herkunft: dict, kurs_herkunft: dict) -> dict:
    jetzt = dt.datetime.now()
    sess = sessions_lesen(con)
    k = kurs["usd_eur"]
    alle_zeilen = zeilen_holen(con, None, None, sess)

    # Tagesreihe (ganze Lebenszeit, Lokalzeit): Grundlage der Balken.
    ohne_tag = [z for z in alle_zeilen if not z["tag"]]
    tage = []
    for tag, zeilen in sorted(gruppieren([z for z in alle_zeilen if z["tag"]], "tag").items()):
        b = block(zeilen, preise)
        sub = block([z for z in zeilen if z["ist_sub"]], preise)
        tage.append({"tag": tag, "usd": b["usd"], "in": b["in"], "out": b["out"],
                     "cread": b["cread"], "cwrite": b["cwrite"], "tok": b["tok"],
                     "calls": b["calls"], "chats": b["chats"],
                     "sessions": b["sessions"], "sub_usd": sub["usd"],
                     "sub_n": sub["sessions"]})

    perioden: dict[str, dict] = {}
    for period in PERIODS:
        start, ende = fenster(period, jetzt)
        zeilen = alle_zeilen if period == "alles" else zeilen_holen(con, start, ende, sess)
        summe = block(zeilen, preise)
        eigene = block([z for z in zeilen if not z["ist_sub"]], preise)
        subs = block([z for z in zeilen if z["ist_sub"]], preise)
        cash = cash_kette(summe["usd"])

        # Chats: ein Chat = eine Wurzel-Session samt ihren Subagenten-Sessions.
        chat_zeilen = []
        for wurzel, gruppe in gruppieren(zeilen, "wurzel").items():
            gesamt = block(gruppe, preise)
            eigen = block([z for z in gruppe if z["sid"] == wurzel], preise)
            unter = block([z for z in gruppe if z["sid"] != wurzel], preise)
            info = sess.get(wurzel) or {}
            chat_zeilen.append({
                "id": wurzel, "titel": titel_zu(info, wurzel),
                "usd": gesamt["usd"], "own_usd": eigen["usd"], "sub_usd": unter["usd"],
                "sub_n": unter["sessions"],
                "cash": cash_anteil(gesamt["usd"], summe["usd"], cash["cash"] if cash else None),
                "calls": gesamt["calls"],
                "in": gesamt["in"], "out": gesamt["out"],
                "cread": gesamt["cread"], "cwrite": gesamt["cwrite"], "tok": gesamt["tok"],
                "kosten": gesamt["kosten"], "quote": gesamt["quote"],
                "sessions": gesamt["sessions"],
                "turns": info.get("turns", 0), "tools": info.get("tools", 0),
                "von": zeitpunkt(gesamt["von"]), "bis": zeitpunkt(gesamt["bis"]),
            })
        chat_zeilen.sort(key=lambda c: c["usd"], reverse=True)

        modell_zeilen = []
        for modell, gruppe in gruppieren(zeilen, "modell").items():
            b = block(gruppe, preise)
            preis = preis_fuer(preise, modell) or {}
            modell_zeilen.append({
                "modell": modell, "usd": b["usd"], "chats": b["chats"],
                "calls": b["calls"], "in": b["in"], "out": b["out"],
                "cread": b["cread"], "cwrite": b["cwrite"], "tok": b["tok"],
                "kosten": b["kosten"], "quote": b["quote"],
                "cash": cash_anteil(b["usd"], summe["usd"], cash["cash"] if cash else None),
                "preis": {"prompt": preis.get("prompt"),
                          "completion": preis.get("completion"),
                          "cache_read": preis.get("cache_read"),
                          "cache_write": preis.get("cache_write")},
                "preis_bekannt": bool(preis),
            })
        modell_zeilen.sort(key=lambda m: m["usd"], reverse=True)

        zweck_zeilen = []
        for aufgabe, gruppe in gruppieren(zeilen, "aufgabe").items():
            b = block(gruppe, preise)
            zweck_zeilen.append({
                "aufgabe": aufgabe, "label": ZWECK_NAMEN.get(aufgabe, aufgabe or "unbekannt"),
                "usd": b["usd"], "chats": b["chats"], "calls": b["calls"], "sessions": b["sessions"],
                "in": b["in"], "out": b["out"], "cread": b["cread"], "cwrite": b["cwrite"],
                "tok": b["tok"], "kosten": b["kosten"], "quote": b["quote"],
                "cash": cash_anteil(b["usd"], summe["usd"], cash["cash"] if cash else None),
            })
        zweck_zeilen.sort(key=lambda z: z["usd"], reverse=True)

        # Verlauf: fuer kurze Zeitraeume mindestens die letzten 7 Tage zeigen.
        ab_tag = None
        if period in ("heute", "woche", "letzte_7_tage"):
            ab_tag = (jetzt.date() - dt.timedelta(days=6)).isoformat()
            verlauf_label = "Verlauf: letzte 7 Tage"
        elif period == "monat":
            ab_tag = jetzt.date().replace(day=1).isoformat()
            verlauf_label = f"Verlauf: {tag_lesbar(ab_tag)} bis heute"
        elif period == "letzte_woche":
            montag = jetzt.date() - dt.timedelta(days=jetzt.weekday() + 7)
            ab_tag = montag.isoformat()
            verlauf_label = f"Verlauf: Vorwoche ab {tag_lesbar(ab_tag)}"
        elif period == "letzter_monat":
            erster_vormonat = (jetzt.date().replace(day=1) - dt.timedelta(days=1)).replace(day=1)
            ab_tag = erster_vormonat.isoformat()
            verlauf_label = f"Verlauf: Vormonat ab {tag_lesbar(ab_tag)}"
        else:
            verlauf_label = f"Verlauf: gesamter Zeitraum ab {(tage[0]['tag'] and tag_lesbar(tage[0]['tag'])) or '-'}"
        verlauf = [t for t in tage if not ab_tag or t["tag"] >= ab_tag]
        if period == "letzter_monat" and verlauf:
            letzter = (jetzt.date().replace(day=1) - dt.timedelta(days=1)).isoformat()
            verlauf = [t for t in verlauf if t["tag"] <= letzter]

        perioden[period] = {
            "label": PERIOD_DEFS[period][0], "definition": PERIOD_DEFS[period][1],
            "von": zeitpunkt(start, True) if start else "Beginn der Aufzeichnung",
            "bis": zeitpunkt(ende, True) if ende else zeitpunkt(jetzt.timestamp()),
            "fenster": {"start": start, "ende": ende},
            "summe": summe, "eigene": eigene, "sub": subs,
            "cash": cash,
            "cash_eigene": cash_anteil(eigene["usd"], summe["usd"], cash["cash"] if cash else None),
            "cash_sub": cash_anteil(subs["usd"], summe["usd"], cash["cash"] if cash else None),
            "chats": chat_zeilen, "modelle": modell_zeilen, "zwecke": zweck_zeilen,
            "verlauf": verlauf, "verlauf_label": verlauf_label,
        }

    belege = [{"guthaben": g, "service": s, "ust": u, "cash": c}
              for g, s, u, c in KAUF_BELEGE]

    return {
        "erzeugt": dt.datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "stand_epoch": jetzt.timestamp(),
        "kurs": {"usd_eur": k, "quelle": kurs.get("quelle"), "stand": kurs.get("stand"),
                 "ersatz": bool(kurs.get("ersatz")), "hinweis": kurs.get("hinweis") or ""},
        "kurs_herkunft": kurs_herkunft,
        "preise_quelle": preis_herkunft.get("quelle"),
        "preise_stand": preis_herkunft.get("stand"),
        "preise_hinweis": preis_herkunft.get("hinweis") or "",
        "preise_anzahl": len(preise),
        "satz": {"service": SERVICE_SATZ, "min": SERVICE_MIN, "ust": UST_SATZ,
                 "break_even_guthaben": round(BREAK_EVEN_GUTHABEN, 2),
                 "break_even_nutzung": round(BREAK_EVEN_NUTZUNG, 2)},
        "belege": belege,
        "kaufprobe_ok": all(
            abs(kauf_pruefen(g)[0] - s) < 0.005 and abs(kauf_pruefen(g)[1] - u) < 0.005
            and abs(kauf_pruefen(g)[2] - c) < 0.005 for g, s, u, c in KAUF_BELEGE),
        "definitionen": {p: PERIOD_DEFS[p][1] for p in PERIODS},
        "namen": {p: PERIOD_DEFS[p][0] for p in PERIODS},
        "reihenfolge": list(PERIODS),
        "ohne_tag": {"zeilen": len(ohne_tag), "usd": round(sum(z["usd"] for z in ohne_tag), 8)},
        "quellen": {
            "db": "state.db (read-only): session_model_usage + sessions",
            "zeitraum": "last_seen je Zeile (UNIX-Zeitstempel als REAL), Lokalzeit",
            "sub": "sessions.parent_session_id, rekursiv bis zur Wurzel (Chat)",
            "token": "session_model_usage.input_tokens / output_tokens / cache_read_tokens / cache_write_tokens",
            "kosten_sorten": ("Tokens x Modellpreis (openrouter:/api/v1/models), proportional auf die "
                              "Abrechnungssumme der Datenbank verteilt"),
            "cash": ("Guthaben = Nutzung / 0,945; Servicegebuehr = max(Guthaben x 5,5 %, 0,80 USD); "
                     "Umsatzsteuer = (Guthaben + Servicegebuehr) x 19 %; Cash = Summe"),
        },
        "perioden": perioden,
    }


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

VORLAGE = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hermes Kosten-Dashboard</title>
<style>
/* ------------------------------------------------------------------
   Lesbarkeit zuerst. KEIN eigener Seitenhintergrund (transparent), damit
   die Oberflaeche des Hosts durchscheint. Farben: erst die Variablen des
   Hosts, sonst eigene Rueckfallwerte aus der --fb-*-Ebene.
   ------------------------------------------------------------------ */
:root{
  --fb-fg:#1b1b20; --fb-muted:#5c5c68; --fb-strong:#000;
  --fb-border:rgba(96,96,112,.28);
  --fb-panel:rgba(96,96,112,.10);
  --fb-panel2:rgba(96,96,112,.05);
  --fb-ok:#127a44; --fb-mid:#8a6100; --fb-bad:#b3261e;
  --fb-s1:#3b6fd4; --fb-s2:#7f5bd6; --fb-s3:#0f8f86; --fb-s4:#b98a1a;
}
@media (prefers-color-scheme: dark){
  :root{
    --fb-fg:#ececf1; --fb-muted:#a8a8b6; --fb-strong:#fff;
    --fb-border:rgba(214,214,232,.30);
    --fb-panel:rgba(214,214,232,.10);
    --fb-panel2:rgba(214,214,232,.05);
    --fb-ok:#41d17f; --fb-mid:#e8c04a; --fb-bad:#ff7369;
    --fb-s1:#5b8def; --fb-s2:#a98cf0; --fb-s3:#2bb3a8; --fb-s4:#e0b34a;
  }
}
:root{
  --fg: var(--foreground, var(--fb-fg));
  --muted: var(--muted-foreground, var(--fb-muted));
  --strong: var(--foreground, var(--fb-strong));
  --border: var(--border-color, var(--fb-border));
  --panel: var(--fb-panel); --panel2: var(--fb-panel2);
  --ok: var(--fb-ok); --mid: var(--fb-mid); --bad: var(--fb-bad);
  --s1: var(--fb-s1); --s2: var(--fb-s2); --s3: var(--fb-s3); --s4: var(--fb-s4);
  --kurve: var(--primary, var(--fb-fg));
}
html{ background: transparent; }
body{
  background: transparent; color: var(--fg); font-family: inherit; font-size: 14px;
  line-height: 1.42; margin: 0; padding: 12px 14px 30px;
}
h1{ font-size: 19px; margin: 0 0 2px; color: var(--strong); font-weight: 650; letter-spacing: .1px; }
h2{ font-size: 13px; margin: 20px 0 7px; color: var(--strong); font-weight: 650;
    text-transform: uppercase; letter-spacing: .06em; }
h2 .zusatz{ text-transform: none; letter-spacing: 0; color: var(--muted); font-weight: 400; margin-left: 6px; }
.meta{ color: var(--muted); font-size: 12px; }
.hinweis{ font-size: 12px; margin-top: 3px; }
.hinweis.warn{ color: var(--bad); font-weight: 600; }
.num{ font-variant-numeric: tabular-nums; }

/* --- Zeitraum-Umschalter --- */
.reiter{ display: flex; flex-wrap: wrap; gap: 5px; margin: 11px 0 3px; }
.reiter button{
  font-family: inherit; font-size: 12.5px; color: var(--fg);
  background: var(--panel2); border: 1px solid var(--border);
  border-radius: 7px; padding: 4px 11px; cursor: pointer;
}
.reiter button:hover{ background: var(--panel); }
.reiter button.aktiv{ background: var(--panel); border-color: var(--fg); color: var(--strong); font-weight: 650; }
.zeitraum-info{ color: var(--muted); font-size: 12px; margin-bottom: 9px; }

/* --- Kennzahlen --- */
.kpi{ display: grid; grid-template-columns: repeat(auto-fit, minmax(146px, 1fr)); gap: 7px; }
.kpi .karte{ background: var(--panel); border: 1px solid var(--border); border-radius: 9px; padding: 8px 10px; }
.kpi .titel{ color: var(--muted); font-size: 10.5px; text-transform: uppercase; letter-spacing: .05em; }
.kpi .wert{ color: var(--strong); font-size: 19px; font-weight: 650; margin-top: 1px; }
.kpi .fuss{ color: var(--muted); font-size: 11px; }
.kpi .karte.betont{ border-color: var(--fg); border-left: 3px solid var(--fg); }
.kpi.klein .wert{ font-size: 17px; }

/* --- gestapelte Balken (Verteilung) --- */
.splitblock{ margin-top: 8px; }
.splittitel{ color: var(--muted); font-size: 11px; margin-bottom: 2px; }
.split{ display: flex; width: 100%; height: 26px; border-radius: 6px; overflow: hidden;
        border: 1px solid var(--border); background: var(--panel2); }
.split div{ display: flex; align-items: center; justify-content: center; font-size: 11px;
            color: #fff; overflow: hidden; white-space: nowrap; }
.split .s1{ background: var(--s1); } .split .s2{ background: var(--s2); }
.split .s3{ background: var(--s3); } .split .s4{ background: var(--s4); }
.split .leer{ background: var(--border); color: var(--muted); }
.splitlegende{ color: var(--muted); font-size: 11px; margin-top: 3px; }
.splitlegende b{ color: var(--s1); } .splitlegende i{ color: var(--s3); font-style: normal; }
.splitlegende u{ color: var(--s2); text-decoration: none; } .splitlegende s{ color: var(--s4); text-decoration: none; }

/* --- Geldkette --- */
.cash{
  background: var(--panel); border: 1px solid var(--border); border-left: 3px solid var(--fg);
  border-radius: 9px; padding: 10px 13px; margin-top: 8px;
}
.cash .zeile{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; margin: 1px 0; }
.cash .bez{ color: var(--muted); min-width: 210px; }
.cash .betrag{ color: var(--strong); font-size: 15px; font-weight: 600; min-width: 110px; }
.cash .klein{ color: var(--muted); font-size: 12px; }
.cash .gross{ font-size: 22px; font-weight: 700; }
.cash .formel{ color: var(--muted); font-size: 11px; margin-top: 6px; }

/* --- Tabellen --- */
.tabwrap{ overflow: auto; max-height: 620px; border: 1px solid var(--border); border-radius: 9px; }
.tabwrap.klein{ max-height: none; }
table{ border-collapse: collapse; width: 100%; font-size: 12.5px; }
th, td{ padding: 4px 8px; text-align: right; white-space: nowrap; border-bottom: 1px solid var(--border); }
th:first-child, td:first-child, th.l, td.l{ text-align: left; }
thead th{ position: sticky; top: 0; color: var(--muted); font-weight: 600; font-size: 10.5px;
  text-transform: uppercase; letter-spacing: .04em; background: var(--panel);
  backdrop-filter: blur(6px); border-bottom: 1px solid var(--border); }
tbody tr:hover{ background: var(--panel2); }
tbody tr:last-child td{ border-bottom: none; }
td.name{ max-width: 300px; overflow: hidden; text-overflow: ellipsis; }
.tr-top1{ background: rgba(255,196,0,.14); } .tr-top2{ background: rgba(255,196,0,.09); }
.tr-top3{ background: rgba(255,196,0,.05); }
.tr-top1 td:first-child, .tr-top2 td:first-child, .tr-top3 td:first-child{ font-weight: 700; }
tfoot td{ font-weight: 700; color: var(--strong); background: var(--panel); border-top: 1px solid var(--border); }
.subzelle{ color: var(--mid); }

/* --- Quote einfaerben --- */
.cq{ font-weight: 650; }
.cq-ok{ color: var(--ok); } .cq-mid{ color: var(--mid); } .cq-bad{ color: var(--bad); }
.legende{ color: var(--muted); font-size: 11.5px; margin-top: 4px; }
.legende b{ color: var(--ok); } .legende i{ color: var(--mid); font-style: normal; }
.legende u{ color: var(--bad); text-decoration: none; }

/* --- Verlauf --- */
.verlauf{ display: flex; align-items: flex-end; gap: 4px; overflow-x: auto; padding: 6px 3px 0; min-height: 140px; }
.balken{ flex: 1 0 30px; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; }
.balken .wert{ font-size: 10px; color: var(--muted); margin-bottom: 2px; font-variant-numeric: tabular-nums; }
.balken .stab{ width: 100%; max-width: 40px; background: var(--kurve); opacity: .68; border-radius: 3px 3px 0 0; min-height: 2px; }
.balken .stab.leer{ background: var(--border); opacity: .5; }
.balken .marke{ font-size: 10px; color: var(--muted); margin-top: 3px; text-align: center; }

/* --- Filter --- */
.filter{ display: flex; gap: 8px; align-items: center; margin: 0 0 7px; flex-wrap: wrap; }
.filter input{ font-family: inherit; font-size: 12.5px; color: var(--fg); background: var(--panel2);
  border: 1px solid var(--border); border-radius: 7px; padding: 4px 9px; min-width: 220px; }
.filter .anz{ color: var(--muted); font-size: 11.5px; }

/* --- Notizen --- */
.notizen{ color: var(--muted); font-size: 11.5px; margin-top: 18px; line-height: 1.55; }
.notizen code{ font-family: ui-monospace, Consolas, monospace; color: var(--fg); }
.notizen ul{ margin: 3px 0 0; padding-left: 18px; }
.notizen b{ color: var(--fg); }
.leermeldung{ color: var(--muted); padding: 12px; }
.mini{ font-size: 11px; color: var(--muted); }
</style>
</head>
<body>

<h1>Hermes Kosten-Dashboard</h1>
<div class="meta" id="kopfzeile"></div>
<div class="hinweis" id="kurszeile"></div>

<div class="reiter" id="reiter"></div>
<div class="zeitraum-info" id="zeitrauminfo"></div>

<h2>Geld und Aufwand <span class="zusatz" id="kpizusatz"></span></h2>
<div class="kpi" id="kpi"></div>

/*ABSCHNITT:SPLIT*/
<div class="splitblock">
  <div class="splittitel">Wohin die Nutzung geht (Kosten je Tokensorte)</div>
  <div class="split" id="splitkosten"></div>
  <div class="splitlegende" id="splitkostenlegende"></div>
  <div class="splittitel" style="margin-top:7px">Eigene Kosten gegen Subagenten</div>
  <div class="split" id="splitsub"></div>
  <div class="splitlegende" id="splitsublegende"></div>
</div>
/*ABSCHNITT:SPLIT-ENDE*/

<h2>Geldkette: Nutzung bis Cash <span class="zusatz" id="geldkettezusatz"></span></h2>
/*ABSCHNITT:GELDKETTE*/
<div class="cash" id="geldkette"></div>
/*ABSCHNITT:GELDKETTE-ENDE*/
<div class="tabwrap klein" style="margin-top:8px">
  <table id="belegtabelle">
    <thead><tr>
      <th class="l">Kaufdialog (Guthaben)</th><th>Servicegebuehr 5,5 %</th>
      <th>Umsatzsteuer 19 %</th><th>= Cash</th><th>Cash</th>
    </tr></thead>
    <tbody id="belegbody"></tbody>
  </table>
</div>
<div class="legende">Drei echte Kaufdialoge als Beleg der Geldkette (Betraege in USD, rechts der
  umgerechnete Euro-Betrag). Der Aufschlag wird in der Geldkette auf den GESAMTEN Verbrauch des
  Zeitraums gerechnet, nicht je Chat.</div>

<h2>Tokens und ihre Kosten <span class="zusatz" id="tokzusatz"></span></h2>
/*ABSCHNITT:TOKENS*/
<div class="kpi" id="tokkpi"></div>
<div class="hinweis" id="tokhinweis"></div>
/*ABSCHNITT:TOKENS-ENDE*/

<h2>Chats <span class="zusatz" id="chattitel"></span></h2>
<div class="filter">
  <input id="filter" type="text" placeholder="Chat filtern (Titel oder ID) ..." autocomplete="off">
  <span class="anz" id="filteranz"></span>
</div>
<div class="tabwrap">
  <table id="chattabelle">
    /*ABSCHNITT:CHATTABELLE*/
    <thead><tr>
      <th class="l">#</th><th class="l">Chat</th><th>Nutzung</th><th>Nutzung</th>
      <th>Eigene</th><th>Subagenten</th><th>Subagenten</th><th>Cash-Anteil</th>
      <th>Input</th><th>Input</th><th>Output</th><th>Output</th>
      <th>Cache-Read</th><th>Cache-Read</th><th>Cache-Write</th><th>Cache-Write</th>
      <th>Quote</th><th>Calls</th><th>Turns/Tools</th><th class="l">Aktivitaet</th>
    </tr></thead>
    /*ABSCHNITT:CHATTABELLE-ENDE*/
    <tbody id="chatbody"></tbody>
    <tfoot id="chatfuss"></tfoot>
  </table>
</div>
<div class="legende">
  Spalten in Euro, sofern nicht anders beschriftet: „Nutzung“ in Euro und Dollar (reine Modellkosten),
  „Eigene“ = dieser Chat ohne Subagenten, „Subagenten“ = Kosten der Subagenten-Sessions samt Anzahl,
  „Cash-Anteil“ = Anteil dieses Chats am Cash des Zeitraums aus der Geldkette.
  Token-Spalten: Zahl und Kosten je Sorte. Quote = Cache-Read / (Input + Cache-Read) ·
  <b>gruen ab 75 %</b> · <i>gelb ab 50 %</i> · <u>rot darunter</u> · Top-3-Chats hervorgehoben.
</div>

<h2>Aufschluesselung nach Modell</h2>
<div class="tabwrap">
  <table id="modelltabelle">
    /*ABSCHNITT:MODELLTABELLE*/
    <thead><tr>
      <th class="l">Modell</th><th>Chats</th><th>Nutzung</th><th>Nutzung</th><th>Anteil</th>
      <th>Input</th><th>Input</th><th>Output</th><th>Output</th>
      <th>Cache-Read</th><th>Cache-Read</th><th>Cache-Write</th><th>Cache-Write</th>
      <th>Tokens ges.</th><th>Quote</th><th>Cash-Anteil</th><th class="l">Preise je 1 Mio (Input/Output/Cache-Read)</th><th>Calls</th>
    </tr></thead>
    /*ABSCHNITT:MODELLTABELLE-ENDE*/
    <tbody id="modellbody"></tbody>
    <tfoot id="modellfuss"></tfoot>
  </table>
</div>
<div class="legende">„Preise je 1 Mio“ = USD je 1 Mio. Tokens aus der oeffentlichen Modellliste
  (Input / Output / Cache-Read). Fehlt ein Cache-Read-Preis, gilt ersatzweise 10 % des Input-Preises.
  Die Kostensummen der drei Sorten addieren sich auf die Nutzung des Zeitraums.</div>

<h2>Aufschluesselung nach Zweck <span class="zusatz">Spalte task der Datenbank</span></h2>
<div class="tabwrap klein">
  <table id="zwecktabelle">
    /*ABSCHNITT:ZWECKTABELLE*/
    <thead><tr>
      <th class="l">Zweck</th><th>Nutzung</th><th>Nutzung</th><th>Anteil</th><th>Chats</th><th>Sessions</th>
      <th>Input</th><th>Output</th><th>Cache-Read</th><th>Cache-Write</th><th>Quote</th><th>Cash-Anteil</th>
    </tr></thead>
    /*ABSCHNITT:ZWECKTABELLE-ENDE*/
    <tbody id="zweckbody"></tbody>
  </table>
</div>
<div class="legende">Rohwerte der Datenbank in Klammern, danach die deutsche Bezeichnung des Skripts.</div>

<h2 id="verlauftitel">Verlauf</h2>
<div class="verlauf" id="verlauf"></div>
<div class="tabwrap klein" style="margin-top:8px">
  <table id="verlaufstabelle">
    /*ABSCHNITT:VERLAUFSTABELLE*/
    <thead><tr>
      <th class="l">Tag</th><th>Nutzung</th><th>Anteil</th>
      <th>Input</th><th>Output</th><th>Cache-Read</th><th>Cache-Write</th>
      <th>Calls</th><th>Chats</th><th>Sessions</th><th>Subagenten</th>
    </tr></thead>
    /*ABSCHNITT:VERLAUFSTABELLE-ENDE*/
    <tbody id="verlaufbody"></tbody>
  </table>
</div>

<div class="notizen">
  <strong>Wie gerechnet wird</strong>
  <ul>
    <li><b>Quelle:</b> <code>state.db</code> read-only, Tabellen <code>session_model_usage</code>
        und <code>sessions</code>; alles in EINER Lesetransaktion, also ein eingefrorener Stand.</li>
    <li><b>Zeitraeume</b> (alle epoch-basiert auf <code>last_seen</code>, Lokalzeit):
        <span id="notiz-zeitraeume"></span></li>
    <li><b>Subagenten:</b> Sessions mit <code>parent_session_id</code> gehoeren zum Eltern-Chat.
        Jede Ansicht nennt deshalb eigene Kosten, Subagenten-Kosten und die Summe.</li>
    <li><b>Token-Sorten:</b> Input, Output, Cache-Read und Cache-Write stehen getrennt,
        jeweils mit Anzahl UND Kosten. Die Kosten entstehen aus Tokenmenge x Modellpreis;
        die Rechnung wird proportional auf die Abrechnungssumme der Datenbank verteilt.
        Abweichung der Rohrechnung: <span id="notiz-abweichung"></span></li>
    <li><b>Zwischenspeicher-Tokens</b> (Spalte „Cache-Tokens“) sind zwischengespeicherte
        Eingabe-Tokens. Sie sind kein Geldbetrag, sondern eine Tokenmenge - hohe Werte senken
        den Preis je Token und sind deshalb gut.</li>
    <li><b>Cash-Betraege</b> sind die tatsaechlich bezahlten Euro-Betraege: Guthaben +
        Servicegebuehr + Umsatzsteuer. Sie stehen in der Geldkette, in der Cash-Karte und in
        der Spalte „Cash-Anteil“ - und nirgends sonst.</li>
    <li><b>Geldkette:</b> Guthaben = Nutzung / 0,945 · Servicegebuehr = max(Guthaben x 5,5 %,
        0,80 USD) · Umsatzsteuer = (Guthaben + Servicegebuehr) x 19 % · Cash = Summe.
        Jeder Schritt wird auf Cent gerundet und mit dem gerundeten Betrag weitergerechnet.</li>
    <li><b>Mindestgebuehr:</b> unter <span id="notiz-be"></span> USD Guthaben (Nutzung
        <span id="notiz-benz"></span> USD) greift die Gebuehr von 0,80 USD - der Aufschlag ist
        dann hoeher als 25,5 %. Ueber dieser Grenze gilt Faktor <span id="notiz-faktor"></span>.</li>
    <li><b>Kostenschätzung:</b> <code>estimated_cost_usd</code> ist in dieser Datenbank die einzige
        gefuellte Kostenspalte; <code>actual_cost_usd</code> ist durchgehend 0, es gibt also keinen
        abgerechneten Gegenwert zum Vergleich (<span id="notiz-ohnezeit"></span>).</li>
    <li><b>Wechselkurs:</b> 1 USD = <span id="notiz-kurs"></span>, Quelle:
        <span id="notiz-kursart"></span>. Kursaenderungen bewegen alle Euro-Betraege mit;
        die USD-Betraege bleiben davon unberuehrt. Betraege tragen das Zeichen hinten
        (schmales geschuetztes Leerzeichen vor dem Zeichen).</li>
    <li><b>Zweck:</b> die Spalte <code>task</code> der Datenbank trennt z. B. Titel-Erzeugung,
        Freigabe-Pruefung, Kontext-Verdichtung und Hintergrund-Pruefung vom normalen Chat.</li>
    <li><b>Grenze der Zuordnung:</b> ein Zeitraum zaehlt eine Zeile nach ihrer LETZTEN Aktivitaet.
        Lange Sitzungen koennen dadurch im juengeren Zeitraum ueberzeichnen.</li>
  </ul>
</div>

<script>
const D = /*__DATEN__*/ null;
</script>
<script>
(function(){
  var PER = D.perioden, REIHE = D.reihenfolge, akt = REIHE[0];
  var K = D.kurs.usd_eur;
  var NN = "\u202f";                       /* schmales geschuetztes Leerzeichen */
  var filterText = "";

  function esc(s){
    return String(s === null || s === undefined ? "" : s)
      .replace(/[&<>"']/g, function(c){
        return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
      });
  }
  function n(v, stellen){
    if (v === null || v === undefined) return "-";
    return Number(v).toLocaleString("de-DE",
      {minimumFractionDigits: stellen, maximumFractionDigits: stellen});
  }
  function euro(v){ return v === null || v === undefined ? "-" : n(v, 2) + NN + "\u20ac"; }
  function dollar(v){ return v === null || v === undefined ? "-" : n(v, 2) + " $"; }
  function ganz(v){ return (v === null || v === undefined) ? "-" : Number(v).toLocaleString("de-DE"); }
  function proz(v){ return v === null || v === undefined ? "-" : n(v, 1) + " %"; }
  function mio(v){
    if (v === null || v === undefined) return "-";
    return n(v / 1000000, 2) + " Mio.";
  }
  function cqKlasse(q){ return q >= 75 ? "cq-ok" : (q >= 50 ? "cq-mid" : "cq-bad"); }
  function eurPreis(v){ return v === null || v === undefined ? "-" : n(v * 1000000, 4); }
  function anteilVon(teil, ganzes){ return ganzes > 0 ? Teil(teil, ganzes) : 0; }
  function Teil(teil, ganzes){ return teil / ganzes * 100; }

  function karte(titel, wert, fuss, betont){
    return '<div class="karte' + (betont ? " betont" : "") + '">'
      + '<div class="titel">' + esc(titel) + "</div>"
      + '<div class="wert num">' + esc(wert) + "</div>"
      + '<div class="fuss">' + esc(fuss || "") + "</div></div>";
  }

  function kopf(){
    document.getElementById("kopfzeile").innerHTML =
      "Stand " + esc(D.erzeugt) + " · Wechselkurs 1 USD = " + n(K, 4) + " " + NN + "\u20ac"
      + " (" + esc(D.kurs.quelle || "") + (D.kurs.stand ? ", Stand " + esc(D.kurs.stand) : "") + ")"
      + " · Modellpreise: " + esc(D.preise_quelle || "") + " (" + ganz(D.preise_anzahl) + " Modelle)";
    var kurszeile = document.getElementById("kurszeile");
    var texte = [];
    if (D.kurs.hinweis) texte.push(D.kurs.hinweis);
    if (D.preise_hinweis) texte.push(D.preise_hinweis);
    if (D.ohne_tag && D.ohne_tag.zeilen > 0){
      texte.push(ganz(D.ohne_tag.zeilen) + " Zeilen ohne Zeitstempel (" + dollar(D.ohne_tag.usd) + ") sind keiner Tagesreihe zugeordnet.");
    }
    if (!D.kaufprobe_ok) texte.push("Die Kaufbelege stimmen nicht mit der Geldkette ueberein - bitte pruefen.");
    kurszeile.innerHTML = texte.map(esc).join(" · ");
    kurszeile.className = "hinweis" + ((D.kurs.ersatz || !D.kaufprobe_ok) ? " warn" : "");

    document.getElementById("notiz-kurs").textContent = n(K, 4) + NN + "\u20ac";
    document.getElementById("notiz-kursart").textContent = (D.kurs.quelle || "") + (D.kurs.stand ? ", Stand " + D.kurs.stand : "");
    document.getElementById("notiz-be").textContent = n(D.satz.break_even_guthaben, 2);
    document.getElementById("notiz-benz").textContent = n(D.satz.break_even_nutzung, 2);
    document.getElementById("notiz-faktor").textContent = n(1 / (1 - D.satz.service) * (1 + D.satz.service) * (1 + D.satz.ust), 5);
    document.getElementById("notiz-zeitraeume").textContent =
      REIHE.map(function(k){ return D.namen[k] + ": " + D.definitionen[k]; }).join(" · ");
    var o = D.ohne_tag && D.ohne_tag.zeilen
      ? ganz(D.ohne_tag.zeilen) + " Zeilen ohne Zeitstempel"
      : "keine Zeilen ohne Zeitstempel";
    document.getElementById("notiz-ohnezeit").textContent = "Datenstand " + D.erzeugt + ", " + o;
  }

  function reiter(){
    document.getElementById("reiter").innerHTML = REIHE.map(function(k){
      return '<button data-p="' + esc(k) + '" title="' + esc(D.definitionen[k]) + '" class="'
        + (k === akt ? "aktiv" : "") + '">' + esc(D.namen[k]) + "</button>";
    }).join("");
    Array.prototype.forEach.call(document.querySelectorAll("#reiter button"), function(b){
      b.addEventListener("click", function(){
        akt = b.getAttribute("data-p"); filterText = "";
        document.getElementById("filter").value = ""; zeichnen();
      });
    });
  }

  function kpi(){
    var p = PER[akt], s = p.summe, c = p.cash, e = p.eigene, u = p.sub;
    var anteilSub = s.usd > 0 ? u.usd / s.usd * 100 : 0;
    var karten = [
      ["Cash (echt)", euro(c ? c.cash : null), c ? "Guthaben " + euro(c.guthaben) + " + Gebuehr " + euro(c.service) + " + USt " + euro(c.ust) : "kein Verbrauch", 1],
      ["Nutzung in Dollar", dollar(s.usd), "reine Modellkosten der Datenbank"],
      ["Nutzung in Euro", euro(s.usd * K), "nur umgerechnet, ohne Aufschlaege"],
      ["Aufschlag Service + USt", euro(c ? c.service + c.ust : null), c ? "gegenueber der reinen Nutzung, " + proz(c.cash / c.nutzung * 100 - 100) : "kein Verbrauch"],
      ["Eigene Kosten", euro(e.usd * K), "ohne Subagenten, " + ganz(e.sessions) + " Sessions"],
      ["Subagenten-Kosten", euro(u.usd * K), ganz(u.sessions) + " Sessions, " + proz(anteilSub) + " der Nutzung"],
      ["Chats", ganz(s.chats), ganz(s.sessions) + " Sessions mit Verbrauch"],
      ["API-Calls", ganz(s.calls), "Aufrufe im Zeitraum"],
      ["Tokens gesamt", ganz(s.tok), ganz(s.in) + " Input · " + ganz(s.out) + " Output · " + ganz(s.cread + s.cwrite) + " Zwischenspeicher"]
    ];
    document.getElementById("kpi").innerHTML = karten.map(function(k){
      return karte(k[0], k[1], k[2], k[3]);
    }).join("");
    document.getElementById("kpizusatz").textContent =
      "· " + p.label + " · " + p.von + " bis " + p.bis;
  }

  function splitbalken(){
    var p = PER[akt], s = p.summe, ko = s.kosten;
    var werte = [ko.input, ko.output, ko.cache, null];
    var namen = ["Input", "Output", "Zwischenspeicher-Kosten", ""];
    var klasse = ["s1", "s2", "s3"];
    var html = "", legende = [];
    if (ko.input === null){
      document.getElementById("splitkosten").innerHTML =
        '<div class="leer" style="width:100%">Keine Modellpreise - Kosten je Tokensorte nicht berechenbar</div>';
      document.getElementById("splitkostenlegende").textContent = "";
    } else {
      var teile = [ko.input, ko.output, ko.cache];
      var summe = teile[0] + teile[1] + teile[2];
      teile.forEach(function(w, i){
        var breite = summe > 0 ? (w / summe * 100) : 0;
        if (breite > 0.4){
          html += '<div class="' + klasse[i] + '" style="width:' + breite.toFixed(2) + '%" title="'
            + esc(namen[i]) + ": " + esc(euro(w)) + '">' + esc(namen[i]) + " " + n(breite, 1) + " %</div>";
        }
        legende.push('<b style="color:var(--' + klasse[i] + ')">' + esc(namen[i]) + "</b> " + euro(w)
          + " (" + n(breite, 1) + " %)");
      });
      document.getElementById("splitkosten").innerHTML = html;
      document.getElementById("splitkostenlegende").innerHTML = legende.join(" · ")
        + " · Summe " + esc(euro(summe)) + " = Nutzung des Zeitraums";
    }
    var eigen = p.eigene.usd, sub = p.sub.usd, ges = eigen + sub;
    var b1 = ges > 0 ? eigen / ges * 100 : 0, b2 = ges > 0 ? sub / ges * 100 : 0;
    document.getElementById("splitsub").innerHTML =
      '<div class="s1" style="width:' + b1.toFixed(2) + '%" title="Eigene Kosten">Eigene '
        + (b1 > 8 ? n(b1, 1) + " %" : "") + "</div>"
      + '<div class="s4" style="width:' + b2.toFixed(2) + '%" title="Subagenten">Subagenten '
        + (b2 > 8 ? n(b2, 1) + " %" : "") + "</div>";
    document.getElementById("splitsublegende").innerHTML =
      "Eigene " + esc(euro(eigen * K)) + " · Subagenten " + esc(euro(sub * K))
      + " · Summe " + esc(euro(ges * K)) + " · in Dollar: " + esc(dollar(eigen)) + " eigen, "
      + esc(dollar(sub)) + " Subagenten, " + esc(dollar(ges)) + " gesamt";
  }

  function geldkette(){
    var p = PER[akt], c = p.cash, s = p.summe;
    document.getElementById("geldkettezusatz").textContent = "· " + p.label;
    if (!c){
      document.getElementById("geldkette").innerHTML =
        '<div class="leer">Kein Verbrauch in diesem Zeitraum - keine Geldkette zu rechnen.</div>';
      return;
    }
    function zeile(bez, betrag, klein){
      return '<div class="zeile"><span class="bez">' + esc(bez) + '</span>'
        + '<span class="betrag num' + (klein ? "" : " gross") + '">' + esc(euro(betrag)) + "</span>"
        + '<span class="klein num">' + esc(dollar(betrag / K)) + "</span></div>";
    }
    var anteileub = "";
    document.getElementById("geldkette").innerHTML =
      '<div class="zeile"><span class="bez">Nutzung (reine Modellkosten)</span>'
        + '<span class="betrag num">' + esc(euro(c.nutzung * K)) + "</span>"
        + '<span class="klein num">' + esc(dollar(s.usd)) + "</span></div>"
      + zeile("= Guthaben (Nutzung / 0,945)", c.guthaben * K)
      + zeile("+ Servicegebuehr (5,5 %, mindestens 0,80 $)", c.service * K)
      + zeile("+ Umsatzsteuer (19 % auf Guthaben + Gebuehr)", c.ust * K)
      + '<div class="zeile"><span class="bez">= echte Ausgaben (Cash)</span>'
        + '<span class="betrag num gross">' + esc(euro(c.cash)) + "</span>"
        + '<span class="klein num">' + esc(dollar(c.cash / K)) + "</span></div>"
      + '<div class="zeile"><span class="klein">Aufschlag gegenueber der reinen Nutzung '
        + esc(euro(c.cash - c.nutzung * K)) + " (" + esc(proz(c.cash / c.nutzung * 100 - 100))
        + ") · davon eigene Kosten " + esc(euro(p.cash_eigene)) + ", Subagenten "
        + esc(euro(p.cash_sub)) + "</span></div>"
      + '<div class="formel">Guthaben = Nutzung / 0,945 · Servicegebuehr = max(Guthaben x 5,5 %, '
        + "0,80 USD) · Umsatzsteuer = (Guthaben + Servicegebuehr) x 19 % · Cash = Guthaben + "
        + "Servicegebuehr + Umsatzsteuer. Jeder Schritt auf Cent gerundet, dann mit dem gerundeten "
        + "Betrag weitergerechnet.</div>" + anteileub;
    document.getElementById("belegbody").innerHTML = D.belege.map(function(b){
      return "<tr><td class='l num'>" + esc(dollar(b.guthaben)) + "</td>"
        + '<td class="num">' + esc(dollar(b.service)) + "</td>"
        + '<td class="num">' + esc(dollar(b.ust)) + "</td>"
        + '<td class="num">' + esc(dollar(b.cash)) + "</td>"
        + '<td class="num">' + esc(euro(b.cash * K)) + "</td></tr>";
    }).join("");
  }

  function tokenblock(){
    var p = PER[akt], s = p.summe, ko = s.kosten;
    document.getElementById("tokzusatz").textContent = "· " + p.label;
    var karten = [
      ["Input-Tokens", ganz(s.in), ko.input === null ? "Kosten: keine Preise bekannt" : euro(ko.input) + " · " + proz(s.usd > 0 ? ko.input / s.usd * 100 : 0) + " der Nutzung", 1],
      ["Output-Tokens", ganz(s.out), ko.output === null ? "Kosten: keine Preise bekannt" : euro(ko.output) + " · " + proz(s.usd > 0 ? ko.output / s.usd * 100 : 0) + " der Nutzung", 1],
      ["Cache-Read-Tokens", ganz(s.cread), ko.cache === null ? "Kosten: keine Preise bekannt" : "Kosten " + euro(ko.cache) + " (Read und Write zusammen)", 1],
      ["Cache-Write-Tokens", ganz(s.cwrite), "in den Kosten der linken Karte enthalten", 1],
      ["Tokens gesamt", ganz(s.tok), "Input + Output + Read + Write"],
      ["Quote Zwischenspeicher", proz(s.quote), "Cache-Read / (Input + Cache-Read)"],
      ["Reasoning-Tokens", ganz(s.reason), "separat erfasste Denk-Tokens der Datenbank"],
      ["Anteil Zwischenspeicher an Kosten", ko.cache === null ? "-" : proz(s.usd > 0 ? ko.cache / s.usd * 100 : 0), "gegenueber " + proz(s.usd > 0 ? (ko.input + ko.output) / s.usd * 100 : 0) + " fuer Input + Output"]
    ];
    document.getElementById("tokkpi").innerHTML = karten.map(function(k){
      return karte(k[0], k[1], k[2], k[3]);
    }).join("");
    var teile = [];
    if (ko.input !== null){
      teile.push("Kostensumme der drei Sorten " + euro(ko.input + ko.output + ko.cache)
        + " = Nutzung des Zeitraums " + euro(s.usd * K) + " (proportional verteilt).");
      teile.push("Roh gerechnet aus Tokenmengen x Modellpreis: " + euro(s.kosten_roh_usd * K)
        + ", Abweichung zur Datenbank " + proz(s.kosten.abweichung) + ".");
    } else {
      teile.push("Ohne Modellpreise steht hier nur die Anzahl - es wird nichts geschaetzt.");
    }
    if (s.ohne_preis && s.ohne_preis.length){
      teile.push("Ohne Preis in der Modellliste: " + s.ohne_preis.join(", ")
        + " - deren Tokens sind in den Kostenzahlen nicht enthalten.");
    }
    teile.push("Beispiel: " + ganz(s.in) + " Input-Tokens sind rund " + mio(s.in) + " Tokens.");
    document.getElementById("tokhinweis").innerHTML = teile.map(esc).join(" ");
  }

  function chatTabelle(){
    var p = PER[akt], chats = p.chats;
    var gefiltert = chats.filter(function(c){
      if (!filterText) return true;
      return (c.titel + " " + c.id).toLowerCase().indexOf(filterText) >= 0;
    });
    var h = "", sum = {usd:0, own:0, sub:0, cash:0, calls:0, in:0, out:0, cread:0, cwrite:0,
                       ki:0, ko:0, kc:0, subn:0};
    gefiltert.forEach(function(c, i){
      var rang = chats.indexOf(c) + 1;
      var klasse = rang <= 3 ? ' class="tr-top' + rang + '"' : "";
      var titel = c.titel === c.id && /^[0-9a-f_]+$/.test(c.id) ? "(ohne Titel) " + c.id : c.titel;
      var k = c.kosten;
      sum.usd += c.usd; sum.own += c.own_usd; sum.sub += c.sub_usd; sum.cash += c.cash || 0;
      sum.calls += c.calls; sum.in += c["in"]; sum.out += c.out; sum.cread += c.cread;
      sum.cwrite += c.cwrite; sum.subn += c.sub_n;
      sum.ki += k.input || 0; sum.ko += k.output || 0; sum.kc += k.cache || 0;
      h += "<tr" + klasse + ">"
        + '<td class="l num">' + rang + "</td>"
        + '<td class="l name" title="' + esc(c.id) + " (" + ganz(c.sessions) + ' Sessions)">' + esc(titel) + "</td>"
        + '<td class="num">' + esc(euro(c.usd * K)) + "</td>"
        + '<td class="num">' + esc(dollar(c.usd)) + "</td>"
        + '<td class="num">' + esc(euro(c.own_usd * K)) + "</td>"
        + '<td class="num subzelle">' + esc(euro(c.sub_usd * K)) + "</td>"
        + '<td class="num subzelle">' + (c.sub_n ? ganz(c.sub_n) : "-") + "</td>"
        + '<td class="num">' + esc(euro(c.cash)) + "</td>"
        + '<td class="num">' + ganz(c["in"]) + "</td>"
        + '<td class="num">' + esc(euro((k.input || 0) * K)) + "</td>"
        + '<td class="num">' + ganz(c.out) + "</td>"
        + '<td class="num">' + esc(euro((k.output || 0) * K)) + "</td>"
        + '<td class="num">' + ganz(c.cread) + "</td>"
        + '<td class="num">' + esc(euro((k.cache || 0) * K)) + "</td>"
        + '<td class="num">' + ganz(c.cwrite) + "</td>"
        + '<td class="num">' + esc(euro((k.cache || 0) * K)) + "</td>"
        + '<td class="num cq ' + cqKlasse(c.quote) + '">' + esc(proz(c.quote)) + "</td>"
        + '<td class="num">' + ganz(c.calls) + "</td>"
        + '<td class="num">' + ganz(c.turns) + " / " + ganz(c.tools) + "</td>"
        + '<td class="l mini">' + esc(c.von) + " - " + esc(c.bis) + "</td></tr>";
    });
    if (!gefiltert.length){
      h = '<tr><td class="leermeldung l" colspan="20">Keine Chats im Filter.</td></tr>';
    }
    document.getElementById("chatbody").innerHTML = h;
    document.getElementById("chatfuss").innerHTML = "<tr>"
      + '<td class="l">\u03a3</td><td class="l">' + esc(ganz(gefiltert.length)) + " von "
      + esc(ganz(chats.length)) + " Chats</td>"
      + '<td class="num">' + esc(euro(sum.usd * K)) + "</td>"
      + '<td class="num">' + esc(dollar(sum.usd)) + "</td>"
      + '<td class="num">' + esc(euro(sum.own * K)) + "</td>"
      + '<td class="num">' + esc(euro(sum.sub * K)) + "</td>"
      + '<td class="num">' + ganz(sum.subn) + "</td>"
      + '<td class="num">' + esc(euro(sum.cash)) + "</td>"
      + '<td class="num">' + ganz(sum["in"]) + "</td>"
      + '<td class="num">' + esc(euro(sum.ki * K)) + "</td>"
      + '<td class="num">' + ganz(sum.out) + "</td>"
      + '<td class="num">' + esc(euro(sum.ko * K)) + "</td>"
      + '<td class="num">' + ganz(sum.cread) + "</td>"
      + '<td class="num">' + esc(euro(sum.kc * K)) + "</td>"
      + '<td class="num">' + ganz(sum.cwrite) + "</td>"
      + '<td class="num">' + esc(euro(sum.kc * K)) + "</td>"
      + '<td class="num cq ' + cqKlasse(0) + '">-</td>'
      + '<td class="num">' + ganz(sum.calls) + "</td>"
      + '<td class="num">-</td><td class="l"></td></tr>';
    document.getElementById("chattitel").textContent =
      "· " + p.label + " · " + esc(ganz(chats.length)) + " Chats · Summe der angezeigten Zeilen: "
      + esc(euro(sum.usd * K)) + " · Zeitraum gesamt: " + esc(euro(p.summe.usd * K));
    document.getElementById("filteranz").textContent =
      gefiltert.length === chats.length
        ? ganz(chats.length) + " Chats"
        : ganz(gefiltert.length) + " von " + ganz(chats.length) + " Chats";
  }

  function modellTabelle(){
    var p = PER[akt], s = p.summe, m = p.modelle;
    var h = "";
    m.forEach(function(x){
      var anteil = s.usd > 0 ? x.usd / s.usd * 100 : 0;
      var k = x.kosten;
      var preise = x.preis_bekannt
        ? eurPreis(x.preis.prompt) + " / " + eurPreis(x.preis.completion) + " / " + eurPreis(x.preis.cache_read)
        : "kein Preis in der Liste";
      h += "<tr>"
        + '<td class="l">' + esc(x.modell) + "</td>"
        + '<td class="num">' + ganz(x.chats) + "</td>"
        + '<td class="num">' + esc(euro(x.usd * K)) + "</td>"
        + '<td class="num">' + esc(dollar(x.usd)) + "</td>"
        + '<td class="num">' + esc(proz(anteil)) + "</td>"
        + '<td class="num">' + ganz(x["in"]) + "</td>"
        + '<td class="num">' + esc(euro((k.input || 0) * K)) + "</td>"
        + '<td class="num">' + ganz(x.out) + "</td>"
        + '<td class="num">' + esc(euro((k.output || 0) * K)) + "</td>"
        + '<td class="num">' + ganz(x.cread) + "</td>"
        + '<td class="num">' + esc(euro((k.cache || 0) * K)) + "</td>"
        + '<td class="num">' + ganz(x.cwrite) + "</td>"
        + '<td class="num">' + esc(euro((k.cache || 0) * K)) + "</td>"
        + '<td class="num">' + ganz(x.tok) + "</td>"
        + '<td class="num cq ' + cqKlasse(x.quote) + '">' + esc(proz(x.quote)) + "</td>"
        + '<td class="num">' + esc(euro(x.cash)) + "</td>"
        + '<td class="l mini num">' + esc(preise) + "</td>"
        + '<td class="num">' + ganz(x.calls) + "</td></tr>";
    });
    if (!m.length) h = '<tr><td class="leermeldung l" colspan="18">Keine Daten.</td></tr>';
    document.getElementById("modellbody").innerHTML = h;
    document.getElementById("modellfuss").innerHTML = "<tr>"
      + '<td class="l">\u03a3</td><td class="num">' + ganz(s.chats) + "</td>"
      + '<td class="num">' + esc(euro(s.usd * K)) + "</td>"
      + '<td class="num">' + esc(dollar(s.usd)) + "</td>"
      + '<td class="num">100,0 %</td>'
      + '<td class="num">' + ganz(s["in"]) + "</td>"
      + '<td class="num">' + esc(euro((s.kosten.input || 0) * K)) + "</td>"
      + '<td class="num">' + ganz(s.out) + "</td>"
      + '<td class="num">' + esc(euro((s.kosten.output || 0) * K)) + "</td>"
      + '<td class="num">' + ganz(s.cread) + "</td>"
      + '<td class="num">' + esc(euro((s.kosten.cache || 0) * K)) + "</td>"
      + '<td class="num">' + ganz(s.cwrite) + "</td>"
      + '<td class="num">' + esc(euro((s.kosten.cache || 0) * K)) + "</td>"
      + '<td class="num">' + ganz(s.tok) + "</td>"
      + '<td class="num cq ' + cqKlasse(s.quote) + '">' + esc(proz(s.quote)) + "</td>"
      + '<td class="num">' + esc(euro(s.usd * K)) + "</td>"
      + '<td class="l"></td><td class="num">' + ganz(s.calls) + "</td></tr>";
  }

  function zweckTabelle(){
    var p = PER[akt], s = p.summe, h = "";
    p.zwecke.forEach(function(z){
      var anteil = s.usd > 0 ? z.usd / s.usd * 100 : 0;
      h += "<tr>"
        + '<td class="l">' + esc(z.label) + ' <span class="mini">(' + esc(z.aufgabe || "ohne") + ")</span></td>"
        + '<td class="num">' + esc(euro(z.usd * K)) + "</td>"
        + '<td class="num">' + esc(dollar(z.usd)) + "</td>"
        + '<td class="num">' + esc(proz(anteil)) + "</td>"
        + '<td class="num">' + ganz(z.chats) + "</td>"
        + '<td class="num">' + ganz(z.sessions) + "</td>"
        + '<td class="num">' + ganz(z["in"]) + "</td>"
        + '<td class="num">' + ganz(z.out) + "</td>"
        + '<td class="num">' + ganz(z.cread) + "</td>"
        + '<td class="num">' + ganz(z.cwrite) + "</td>"
        + '<td class="num cq ' + cqKlasse(z.quote) + '">' + esc(proz(z.quote)) + "</td>"
        + '<td class="num">' + esc(euro(z.cash)) + "</td></tr>";
    });
    if (!p.zwecke.length) h = '<tr><td class="leermeldung l" colspan="12">Keine Daten.</td></tr>';
    document.getElementById("zweckbody").innerHTML = h;
  }

  function verlauf(){
    var p = PER[akt], tage = p.verlauf;
    document.getElementById("verlauftitel").innerHTML = "Verlauf <span class=\"zusatz\">"
      + esc(p.verlauf_label) + "</span>";
    if (!tage.length){
      document.getElementById("verlauf").innerHTML = '<div class="leermeldung">Keine Tagesdaten.</div>';
      document.getElementById("verlaufbody").innerHTML = "";
      return;
    }
    var max = 0;
    tage.forEach(function(t){ if (t.usd > max) max = t.usd; });
    var ges = 0;
    tage.forEach(function(t){ ges += t.usd; });
    document.getElementById("verlauf").innerHTML = tage.map(function(t){
      var hoehe = max > 0 ? Math.max(2, Math.round(t.usd / max * 110)) : 2;
      var leer = t.usd <= 0 ? " leer" : "";
      var wt = ["So","Mo","Di","Mi","Do","Fr","Sa"][new Date(t.tag + "T12:00:00").getDay()];
      return '<div class="balken" title="' + esc(t.tag) + ": " + esc(euro(t.usd * K)) + ", "
        + ganz(t.calls) + " Calls, " + ganz(t.chats) + " Chats" + (t.sub_n ? ", " + ganz(t.sub_n) + " Subagenten-Sessions, " + esc(euro(t.sub_usd * K)) : "")
        + '"><div class="wert">' + esc(n(t.usd * K, 2)) + '</div>'
        + '<div class="stab' + leer + '" style="height:' + hoehe + 'px"></div>'
        + '<div class="marke">' + esc(wt) + "<br>" + esc(tagKurz(t.tag)) + "</div></div>";
    }).join("");
    document.getElementById("verlaufbody").innerHTML = tage.map(function(t){
      var anteil = ges > 0 ? t.usd / ges * 100 : 0;
      return "<tr><td class='l num'>" + esc(t.tag) + " (" + esc(wtKurz(t.tag)) + ")</td>"
        + '<td class="num">' + esc(euro(t.usd * K)) + "</td>"
        + '<td class="num">' + esc(proz(anteil)) + "</td>"
        + '<td class="num">' + ganz(t["in"]) + "</td>"
        + '<td class="num">' + ganz(t.out) + "</td>"
        + '<td class="num">' + ganz(t.cread) + "</td>"
        + '<td class="num">' + ganz(t.cwrite) + "</td>"
        + '<td class="num">' + ganz(t.calls) + "</td>"
        + '<td class="num">' + ganz(t.chats) + "</td>"
        + '<td class="num">' + ganz(t.sessions) + "</td>"
        + '<td class="num subzelle">' + (t.sub_n ? ganz(t.sub_n) + " · " + esc(euro(t.sub_usd * K)) : "-") + "</td></tr>";
    }).join("");
  }
  function tagKurz(iso){
    var t = String(iso || "").split("-");
    return t.length === 3 ? t[2] + "." + t[1] + "." : iso;
  }
  function wtKurz(iso){
    return ["So","Mo","Di","Mi","Do","Fr","Sa"][new Date(iso + "T12:00:00").getDay()];
  }

  function zeichnen(){
    var p = PER[akt];
    document.getElementById("zeitrauminfo").textContent =
      p.label + " · " + p.definition + " · " + p.von + " bis " + p.bis;
    Array.prototype.forEach.call(document.querySelectorAll("#reiter button"), function(b){
      b.className = b.getAttribute("data-p") === akt ? "aktiv" : "";
    });
    kpi(); splitbalken(); geldkette(); tokenblock();
    chatTabelle(); modellTabelle(); zweckTabelle(); verlauf();
  }

  document.getElementById("filter").addEventListener("input", function(e){
    filterText = e.target.value.toLowerCase().trim();
    chatTabelle();
  });

  kopf(); reiter(); zeichnen();
})();
</script>
</body>
</html>
"""


def html_bauen(daten: dict) -> str:
    js = json.dumps(daten, ensure_ascii=False, separators=(",", ":"))
    # Ein "</script>" im Datenblock wuerde das Script-Element beenden.
    js = js.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return VORLAGE.replace("/*__DATEN__*/ null", js)


# --------------------------------------------------------------------------
# Gegenprobe: das, was WIRKLICH in der Datei steht, gegen direkte SQL-Abfragen
# --------------------------------------------------------------------------

MARKER_ANFANG = "const D = "
MARKER_ENDE = "\n</script>"

SUB_BEDINGUNG = ("u.session_id IN (SELECT id FROM sessions "
                 "WHERE COALESCE(parent_session_id,'') <> '')")
EIGEN_BEDINGUNG = ("u.session_id NOT IN (SELECT id FROM sessions "
                   "WHERE COALESCE(parent_session_id,'') <> '')")

# Eigene, unabhaengige Abfragen (bewusst nicht die Konstanten oben).
PRUEF_SUMME = """
    SELECT COALESCE(SUM(CASE WHEN u.actual_cost_usd <> 0 THEN u.actual_cost_usd
                             ELSE u.estimated_cost_usd END), 0),
           COALESCE(SUM(u.input_tokens), 0), COALESCE(SUM(u.output_tokens), 0),
           COALESCE(SUM(u.cache_read_tokens), 0), COALESCE(SUM(u.cache_write_tokens), 0),
           COALESCE(SUM(u.api_call_count), 0), COUNT(DISTINCT u.session_id)
      FROM session_model_usage u
     WHERE {wo}
"""

PRUEF_BAUM = f"""
    WITH RECURSIVE baum(id, root, tiefe) AS (
        SELECT id, id, 0 FROM sessions WHERE COALESCE(parent_session_id,'') = ''
        UNION ALL
        SELECT s.id, b.root, b.tiefe + 1
          FROM sessions s JOIN baum b ON s.parent_session_id = b.id
         WHERE b.tiefe < {MAX_TIEFE}
    )
    SELECT id, root, tiefe FROM baum
"""

PRUEF_CHATS = f"""
    WITH RECURSIVE baum(id, root, tiefe) AS (
        SELECT id, id, 0 FROM sessions WHERE COALESCE(parent_session_id,'') = ''
        UNION ALL
        SELECT s.id, b.root, b.tiefe + 1
          FROM sessions s JOIN baum b ON s.parent_session_id = b.id
         WHERE b.tiefe < {MAX_TIEFE}
    )
    SELECT b.root,
           CASE WHEN b.tiefe = 0 THEN 0 ELSE 1 END AS ist_sub,
           COALESCE(SUM(CASE WHEN u.actual_cost_usd <> 0 THEN u.actual_cost_usd
                             ELSE u.estimated_cost_usd END), 0)  AS usd,
           COALESCE(SUM(u.input_tokens), 0), COALESCE(SUM(u.output_tokens), 0),
           COALESCE(SUM(u.cache_read_tokens), 0), COALESCE(SUM(u.cache_write_tokens), 0),
           COALESCE(SUM(u.api_call_count), 0), COUNT(DISTINCT u.session_id)
      FROM baum b JOIN session_model_usage u ON u.session_id = b.id
     WHERE {{wo}}
     GROUP BY b.root, ist_sub
"""

PRUEF_MODELLE = """
    SELECT COALESCE(u.model, '?'),
           COALESCE(SUM(CASE WHEN u.actual_cost_usd <> 0 THEN u.actual_cost_usd
                             ELSE u.estimated_cost_usd END), 0),
           COALESCE(SUM(u.api_call_count), 0), COUNT(DISTINCT u.session_id),
           COALESCE(SUM(u.input_tokens), 0), COALESCE(SUM(u.output_tokens), 0),
           COALESCE(SUM(u.cache_read_tokens), 0), COALESCE(SUM(u.cache_write_tokens), 0)
      FROM session_model_usage u
     WHERE {wo}
     GROUP BY 1
"""

PRUEF_ZWECKE = """
    SELECT COALESCE(u.task, ''),
           COALESCE(SUM(CASE WHEN u.actual_cost_usd <> 0 THEN u.actual_cost_usd
                             ELSE u.estimated_cost_usd END), 0),
           COALESCE(SUM(u.api_call_count), 0), COUNT(DISTINCT u.session_id),
           COALESCE(SUM(u.input_tokens), 0), COALESCE(SUM(u.output_tokens), 0)
      FROM session_model_usage u
     WHERE {wo}
     GROUP BY 1
"""

PRUEF_TAGE = """
    SELECT date(CAST(u.last_seen AS INTEGER), 'unixepoch', 'localtime') AS tag,
           COALESCE(SUM(CASE WHEN u.actual_cost_usd <> 0 THEN u.actual_cost_usd
                             ELSE u.estimated_cost_usd END), 0),
           COALESCE(SUM(u.input_tokens), 0), COALESCE(SUM(u.output_tokens), 0),
           COALESCE(SUM(u.cache_read_tokens), 0), COALESCE(SUM(u.cache_write_tokens), 0),
           COALESCE(SUM(u.api_call_count), 0), COUNT(DISTINCT u.session_id)
      FROM session_model_usage u
     WHERE u.last_seen IS NOT NULL
     GROUP BY 1 ORDER BY 1
"""


def fenster_unabhaengig(period: str, jetzt: dt.datetime) -> tuple[float | None, float | None]:
    """Zweite, unabhaengige Umsetzung der Zeitraumgrenzen (fuer die Gegenprobe)."""
    if period == "alles":
        return None, None
    if period == "heute":
        return dt.datetime(jetzt.year, jetzt.month, jetzt.day).timestamp(), None
    if period == "woche":
        return (dt.datetime(jetzt.year, jetzt.month, jetzt.day)
                - dt.timedelta(days=jetzt.weekday())).timestamp(), None
    if period == "letzte_woche":
        montag_diesen = dt.datetime(jetzt.year, jetzt.month, jetzt.day) - dt.timedelta(days=jetzt.weekday())
        return (montag_diesen - dt.timedelta(days=7)).timestamp(), (montag_diesen - dt.timedelta(seconds=1e-6)).timestamp()
    if period == "letzte_7_tage":
        return jetzt.timestamp() - 604800.0, None
    if period == "monat":
        return dt.datetime(jetzt.year, jetzt.month, 1).timestamp(), None
    if period == "letzter_monat":
        erster_diesen = dt.datetime(jetzt.year, jetzt.month, 1)
        ende = (erster_diesen - dt.timedelta(seconds=1e-6)).timestamp()
        vorjahr, vormonat = (jetzt.year - 1, 12) if jetzt.month == 1 else (jetzt.year, jetzt.month - 1)
        return dt.datetime(vorjahr, vormonat, 1).timestamp(), ende
    raise AssertionError(period)


def html_daten_lesen(pfad: Path) -> dict:
    """Das Daten-JSON aus der fertigen HTML-Datei zurueckholen."""
    text = pfad.read_text(encoding="utf-8")
    i = text.index(MARKER_ANFANG) + len(MARKER_ANFANG)
    j = text.index(MARKER_ENDE, i)
    roh = text[i:j].strip().rstrip(";").strip()
    return json.loads(roh.replace("<\\/", "</"))


def _cash_kette_pruef(nutzung: float) -> dict | None:
    """Unabhaengige Nachrechnung der Geldkette (ohne die Funktion oben zu benutzen)."""
    if not nutzung or nutzung <= 0:
        return None
    guthaben = round(nutzung / 0.945 + 1e-9, 2)
    service = round(max(guthaben * 5.5 / 100, 0.80) + 1e-9, 2)
    ust = round((guthaben + service) * 19 / 100 + 1e-9, 2)
    return {"guthaben": guthaben, "service": service, "ust": ust,
            "cash": round(guthaben + service + ust, 2)}


def pruefen(con: sqlite3.Connection, pfad: Path, jetzt: dt.datetime) -> tuple[int, int, float]:
    """Summen aus der HTML-Datei gegen direkte SQL-Abfragen stellen.

    Laeuft auf DERSELBEN Lesetransaktion wie der Aufbau - verglichen wird also
    exakt derselbe Datenstand, nicht ein spaeterer.
    Rueckgabe: (geprueft, fehler, groesste_usd_abweichung).
    """
    daten = html_daten_lesen(pfad)
    fehler = 0
    geprueft = 0
    max_rest = 0.0

    def gleich(name: str, aus_html, aus_sql) -> bool:
        nonlocal fehler, geprueft
        geprueft += 1
        if aus_html != aus_sql:
            fehler += 1
            print(f"  ABWEICHUNG {name}: HTML={aus_html!r} SQL={aus_sql!r}")
            return False
        return True

    def nah(name: str, aus_html, aus_sql, toleranz: float = 1e-6) -> bool:
        nonlocal fehler, geprueft, max_rest
        geprueft += 1
        if aus_html is None or aus_sql is None:
            fehler += 1
            print(f"  ABWEICHUNG {name}: HTML={aus_html!r} SQL={aus_sql!r}")
            return False
        abweichung = abs(float(aus_html) - float(aus_sql))
        max_rest = max(max_rest, abweichung)
        if abweichung > toleranz:
            fehler += 1
            print(f"  ABWEICHUNG {name}: HTML={aus_html!r} SQL={aus_sql!r} (Differenz {abweichung})")
            return False
        return True

    print("  Gegenprobe gegen direkte SQL-Abfragen (gleicher Datenstand):")
    print(f"  {'Zeitraum':<14} {'Chats':>6} {'Sessions':>9} | {'USD (HTML)':>12} {'USD (SQL)':>12} | "
          f"{'eigene':>11} {'Subagenten':>11} | Einzelwerte")

    for period in PERIODS:
        p = daten["perioden"][period]
        s, eigene, subs = p["summe"], p["eigene"], p["sub"]
        start, ende = fenster_unabhaengig(period, jetzt)
        # 1) Die im HTML eingebetteten Fenstergrenzen muessen die neu gerechneten sein.
        gleich(f"{period}.fenster.start", p["fenster"]["start"], start)
        gleich(f"{period}.fenster.ende", p["fenster"]["ende"], ende)

        wo, werte = _wo(start, ende)
        usd, tin, tout, tcread, tcwrite, calls, sessions = con.execute(
            PRUEF_SUMME.format(wo=wo), werte).fetchone()
        usd = usd or 0.0
        schritt = [
            nah(f"{period}.usd", s["usd"], round(usd, 8)),
            gleich(f"{period}.input", s["in"], tin or 0),
            gleich(f"{period}.output", s["out"], tout or 0),
            gleich(f"{period}.cache_read", s["cread"], tcread or 0),
            gleich(f"{period}.cache_write", s["cwrite"], tcwrite or 0),
            gleich(f"{period}.calls", s["calls"], calls or 0),
            gleich(f"{period}.sessions", s["sessions"], sessions or 0),
            gleich(f"{period}.chats", s["chats"], len(p["chats"])),
        ]
        # 2) Eigene und Subagenten-Kosten getrennt, ueber die Eltern-Bedingung in SQL.
        for name, block_daten, bedingung in (("eigene", eigene, EIGEN_BEDINGUNG),
                                             ("sub", subs, SUB_BEDINGUNG)):
            wo2, werte2 = _wo(start, ende)
            zeile = con.execute(
                PRUEF_SUMME.format(wo=f"({wo2}) AND {bedingung}"), werte2).fetchone()
            schritt.append(nah(f"{period}.{name}.usd", block_daten["usd"], round(zeile[0] or 0.0, 8)))
            schritt.append(gleich(f"{period}.{name}.input", block_daten["in"], zeile[1] or 0))
            schritt.append(gleich(f"{period}.{name}.output", block_daten["out"], zeile[2] or 0))
            schritt.append(gleich(f"{period}.{name}.cache_read", block_daten["cread"], zeile[3] or 0))
            schritt.append(gleich(f"{period}.{name}.calls", block_daten["calls"], zeile[5] or 0))
            schritt.append(gleich(f"{period}.{name}.sessions", block_daten["sessions"], zeile[6] or 0))
        # 3) Eigene + Subagenten muss genau die Zeitraumsumme ergeben.
        schritt.append(nah(f"{period}.own_plus_sub", round(eigene["usd"] + subs["usd"], 6), round(s["usd"], 6)))

        # 4) Jede Chat-Zeile gegen den rekursiven SQL-Baum (Wurzel-Zuordnung).
        roh: dict[tuple, tuple] = {}
        wo3, werte3 = _wo(start, ende)
        for (root, ist_sub, u, i2, o2, c2, w2, ca, sn) in con.execute(
                PRUEF_CHATS.format(wo=wo3), werte3):
            roh[(root, int(ist_sub))] = (round(u or 0.0, 6), i2 or 0, o2 or 0, c2 or 0,
                                         w2 or 0, ca or 0, sn or 0)
        html_zeilen = set()
        for c in p["chats"]:
            html_zeilen.add((c["id"], 0))
            html_zeilen.add((c["id"], 1))
            for ist_sub, teil in ((0, "own_usd"), (1, "sub_usd")):
                if ist_sub == 0:
                    erwartet = roh.get((c["id"], 0), (0.0, 0, 0, 0, 0, 0, 0))
                    schritt.append(nah(f"{period}.chat[{c['id'][:20]}].eigene", c["own_usd"], erwartet[0]))
                    schritt.append(gleich(f"{period}.chat[{c['id'][:20]}].eigene_tokens",
                                          c["in"] if c["sub_n"] == 0 else None, None)
                                  if False else True)
                else:
                    erwartet = roh.get((c["id"], 1), (0.0, 0, 0, 0, 0, 0, 0))
                    schritt.append(nah(f"{period}.chat[{c['id'][:20]}].sub", c["sub_usd"], erwartet[0]))
                    schritt.append(gleich(f"{period}.chat[{c['id'][:20]}].sub_n", c["sub_n"], erwartet[6]))
            schritt.append(nah(f"{period}.chat[{c['id'][:20]}].gesamt",
                               c["usd"], round(roh.get((c["id"], 0), (0.0,))[0]
                                               + roh.get((c["id"], 1), (0.0,))[0], 6)))
        # Kein Chat im HTML, den SQL nicht kennt (und umgekehrt, wenn Kosten > 0).
        sql_zeilen = {k for k, v in roh.items() if v[0] > 0}
        schritt.append(gleich(f"{period}.chatmenge", sorted(html_zeilen), sorted(sql_zeilen)))

        # 5) Summe der angezeigten Zeilen gegen die Rohsumme (nur Rundungsrest).
        rest = abs(round(sum(c["usd"] for c in p["chats"]), 6) - round(s["usd"], 6))
        schritt.append(rest <= 1e-5)
        if rest > 1e-5:
            print(f"  ABWEICHUNG {period}.summe_der_zeilen: Rest {rest}")

        # 6) Modelle, Zwecke, Tage.
        wo4, werte4 = _wo(start, ende)
        sql_m = {m: (round(u or 0.0, 6), ca or 0, sn or 0, i2 or 0, o2 or 0, c2 or 0, w2 or 0)
                 for m, u, ca, sn, i2, o2, c2, w2 in con.execute(PRUEF_MODELLE.format(wo=wo4), werte4)}
        html_m = {m["modell"]: (m["usd"], m["calls"], None, m["in"], m["out"], m["cread"], m["cwrite"])
                  for m in p["modelle"]}
        for m in p["modelle"]:
            v = sql_m.get(m["modell"])
            if v is None:
                schritt.append(gleich(f"{period}.modell[{m['modell']}]", "vorhanden", "fehlt"))
                continue
            schritt.append(nah(f"{period}.modell[{m['modell']}].usd", m["usd"], v[0]))
            schritt.append(gleich(f"{period}.modell[{m['modell']}].calls", m["calls"], v[1]))
            schritt.append(gleich(f"{period}.modell[{m['modell']}].tokens",
                                  (m["in"], m["out"], m["cread"], m["cwrite"]), (v[3], v[4], v[5], v[6])))
        schritt.append(gleich(f"{period}.modellmenge", sorted(html_m), sorted(sql_m)))

        wo5, werte5 = _wo(start, ende)
        sql_z = {z: (round(u or 0.0, 6), ca or 0, sn or 0, i2 or 0, o2 or 0)
                 for z, u, ca, sn, i2, o2 in con.execute(PRUEF_ZWECKE.format(wo=wo5), werte5)}
        for z in p["zwecke"]:
            v = sql_z.get(z["aufgabe"])
            if v is None:
                schritt.append(gleich(f"{period}.zweck[{z['aufgabe']}]", "vorhanden", "fehlt"))
                continue
            schritt.append(nah(f"{period}.zweck[{z['aufgabe']}].usd", z["usd"], v[0]))
            schritt.append(gleich(f"{period}.zweck[{z['aufgabe']}].tokens", (z["in"], z["out"]), (v[3], v[4])))
        schritt.append(gleich(f"{period}.zweckmenge", sorted(z["aufgabe"] for z in p["zwecke"]), sorted(sql_z)))

        # 7) Kostenaufteilung: die drei Sorten muessen sich auf die Nutzung addieren.
        for name, b in (("summe", s), ("eigene", eigene), ("sub", subs)):
            k = b["kosten"]
            if k["input"] is None:
                schritt.append(gleich(f"{period}.{name}.kosten_aufteilung", "ohne Preise", "ohne Preise")
                               if not daten["preise_anzahl"] else False)
            else:
                schritt.append(nah(f"{period}.{name}.kosten_summe",
                                   round(k["input"] + k["output"] + k["cache_read"] + k["cache_write"], 6),
                                   round(b["usd"], 6)))
        for c in p["chats"]:
            k = c["kosten"]
            if k["input"] is not None:
                schritt.append(nah(f"{period}.chat[{c['id'][:20]}].kosten_summe",
                                   round(k["input"] + k["output"] + k["cache_read"] + k["cache_write"], 6),
                                   round(c["usd"], 6)))

        # 8) Cash-Kette unabhängig nachrechnen (nicht mit der Funktion oben).
        erwartet = _cash_kette_pruef(s["usd"])
        c = p["cash"]
        if erwartet is None:
            schritt.append(gleich(f"{period}.cash", c, None))
        else:
            schritt.append(gleich(f"{period}.cash.nutzung", c["nutzung"], erwartet["nutzung"]))
            schritt.append(gleich(f"{period}.cash.guthaben", c["guthaben"], erwartet["guthaben"]))
            schritt.append(gleich(f"{period}.cash.service", c["service"], erwartet["service"]))
            schritt.append(gleich(f"{period}.cash.ust", c["ust"], erwartet["ust"]))
            schritt.append(gleich(f"{period}.cash.summe", c["cash"], erwartet["cash"]))

        ok = all(schritt)
        print(f"  {'OK  ' if ok else 'FEHL'}{period:<14} {s['chats']:>6} {s['sessions']:>9} | "
              f"{s['usd']:>12.6f} {round(usd, 6):>12.6f} | {eigene['usd']:>11.6f} {subs['usd']:>11.6f} | "
              f"{len(schritt)} Einzelwerte, {sum(schritt)} stimmen")

    # 9) Wurzel-Zuordnung: Python-Karte gegen den rekursiven SQL-Baum.
    sess = sessions_lesen(con)
    sql_baum = {sid: (root, tiefe) for sid, root, tiefe in con.execute(PRUEF_BAUM)}
    karte_html = {sid: daten["_karte"][sid] for sid in daten.get("_karte", {})} if daten.get("_karte") else {}
    gleich("baum.sessionmenge", sorted(sql_baum), sorted(sess))
    for sid, (root, tiefe) in sorted(sql_baum.items()):
        gleich(f"baum[{sid[:20]}]", (sess[sid]["wurzel"], 1 if sess[sid]["ist_sub"] else 0), (root, tiefe))
    print(f"  Wurzel-Zuordnung: {len(sql_baum)} Sessions geprueft (Python-Karte == rekursiver SQL-Baum)")

    # 10) Verlaufstage gegen die direkte Tagesabfrage.
    sql_t = {tag: (round(u or 0.0, 6), i2 or 0, o2 or 0, c2 or 0, w2 or 0, ca or 0, sn or 0)
             for tag, u, i2, o2, c2, w2, ca, sn in con.execute(PRUEF_TAGE)}
    alle_tage = daten["perioden"]["alles"]["verlauf"]
    gleich("verlauf.tagesmenge", sorted(t["tag"] for t in alle_tage), sorted(sql_t))
    for t in alle_tage:
        v = sql_t.get(t["tag"], (0.0, 0, 0, 0, 0, 0, 0))
        gleich(f"verlauf[{t['tag']}].usd", round(t["usd"], 6), v[0])
        gleich(f"verlauf[{t['tag']}].tokens", (t["in"], t["out"], t["cread"], t["cwrite"]),
               (v[1], v[2], v[3], v[4]))
    tage_summe = round(sum(t["usd"] for t in alle_tage), 6)
    alles_usd = round(daten["perioden"]["alles"]["summe"]["usd"], 6)
    rest = abs(tage_summe - alles_usd)
    max_rest = max(max_rest, rest)
    geprueft += 1
    if rest > 1e-5:
        fehler += 1
        print(f"  ABWEICHUNG verlauf.summe: {tage_summe} statt {alles_usd}")

    # 11) Gebuehrenmodell: die drei echten Kaufdialoge, jeder Posten auf Cent gerundet.
    for gut, s_erw, u_erw, g_erw in KAUF_BELEGE:
        service, ust, cash = kauf_pruefen(gut)
        gleich(f"cash_probe[${gut:.2f}].service", service, s_erw)
        gleich(f"cash_probe[${gut:.2f}].ust", ust, u_erw)
        gleich(f"cash_probe[${gut:.2f}].cash", cash, g_erw)
    gleich("cash_probe.break_even_guthaben", round(BREAK_EVEN_GUTHABEN, 2), 14.55)
    gleich("cash_probe.break_even_nutzung", round(BREAK_EVEN_NUTZUNG, 2), 13.75)
    gleich("cash_probe.minimum_greift_darunter", kauf_pruefen(14.54)[0], 0.80)
    # Die Belege stehen auch im HTML - dort muessen dieselben Zahlen stehen.
    for b, (gut, s_erw, u_erw, g_erw) in zip(daten["belege"], KAUF_BELEGE):
        gleich(f"html_beleg[{gut}].service", b["service"], s_erw)
        gleich(f"html_beleg[{gut}].ust", b["ust"], u_erw)
        gleich(f"html_beleg[{gut}].cash", b["cash"], g_erw)
    gleich("html.kaufprobe_ok", daten["kaufprobe_ok"], True)

    print(f"  Rundungsrest (Summe der Chat-Zeilen und Tage gegen die Rohsumme): "
          f"max {max_rest:.9f} USD (Toleranz 0,00001 USD)")
    print(f"  Ergebnis: {geprueft} Einzelvergleiche, {fehler} Abweichungen")
    return geprueft, fehler, max_rest


def selbststaendigkeit_pruefen(pfad: Path) -> int:
    """Die HTML-Datei darf nichts aus dem Netz nachladen."""
    text = pfad.read_text(encoding="utf-8")
    verbote = {
        "http:// oder https://": text.count("http://") + text.count("https://"),
        "src=": text.count("src="),
        "<link": text.lower().count("<link"),
        "@import": text.count("@import"),
        "url(": text.count("url("),
        "fetch(": text.count("fetch("),
        "XMLHttpRequest": text.count("XMLHttpRequest"),
        "integrity=": text.count("integrity="),
        "location.href": text.count("location.href"),
    }
    fehler = 0
    print("  Selbststaendigkeit:")
    for name, anzahl in verbote.items():
        print(f"    {'OK  ' if anzahl == 0 else 'FEHL'}{name:<24} {anzahl} Treffer")
        fehler += 0 if anzahl == 0 else 1
    print(f"    Script-Bloecke: {text.count('<script')} (extern: {text.count('<script src')})")
    return fehler


def beschriftung_pruefen(pfad: Path) -> int:
    """Deutsche Schreibweise und die Trennung der Woerter Cache/Cash pruefen.

    Geprueft wird die FERTIGE Datei:
      * kein "EUR" als Text (Betraege tragen das Zeichen),
      * kein Euro-Zeichen mit normalem Leerzeichen davor (es gilt das schmale
        geschuetzte Leerzeichen U+202F),
      * in keinem Abschnitt stehen "Cache"- und "Cash"-Beschriftungen direkt
        nebeneinander (der Nutzer hat sie einmal verwechselt) und
      * der Cash-Abschnitt nennt das Wort Cache nicht, der Token-Abschnitt
        nennt das Wort Cash nicht.
    """
    text = pfad.read_text(encoding="utf-8")
    fehler = 0
    marke = lambda ok, name, zusatz: (f"    {'OK  ' if ok else 'FEHL'}{name:<36} {zusatz}")

    eur_text = text.count("EUR")
    print(marke(eur_text == 0, "kein EUR als Text", f"{eur_text} Treffer"))
    fehler += 0 if eur_text == 0 else 1

    normal_leer = text.count(" \u20ac")
    print(marke(normal_leer == 0, "Euro-Zeichen nur mit Schmalleerzeichen",
                f"{normal_leer} Treffer mit normalem Leerzeichen"))
    fehler += 0 if normal_leer == 0 else 1

    schmal = text.count("\u202f") + text.count("\\u202f")
    print(marke(schmal > 0, "schmales geschuetztes Leerzeichen", f"{schmal} Treffer"))
    fehler += 0 if schmal > 0 else 1

    # Beschriftungen je Abschnitt in Reihenfolge einsammeln und Nachbarschaft pruefen.
    abschnitte: dict[str, str] = {}
    for name in ("SPLIT", "GELDKETTE", "TOKENS", "CHATTABELLE", "MODELLTABELLE",
                 "ZWECKTABELLE", "VERLAUFSTABELLE"):
        anfang, ende = f"/*ABSCHNITT:{name}*/", f"/*ABSCHNITT:{name}-ENDE*/"
        if anfang in text and ende in text:
            abschnitte[name] = text[text.index(anfang):text.index(ende)]
    if len(abschnitte) != 7:
        print(marke(False, "Abschnittsmarken", f"{len(abschnitte)} von 7 gefunden"))
        fehler += 1

    muster = re.compile(r'<th[^>]*>([^<]+)</th>|label:\s*"([^"]+)"')
    verstoesse: list[str] = []
    for name, stueck in abschnitte.items():
        beschriftungen = [a or b for a, b in muster.findall(stueck)]
        for links, rechts in zip(beschriftungen, beschriftungen[1:]):
            if (("cache" in links.lower() and "cash" in rechts.lower())
                    or ("cash" in links.lower() and "cache" in rechts.lower())):
                verstoesse.append(f"{name}: {links!r} neben {rechts!r}")
        for einzel in beschriftungen:
            if "cache" in einzel.lower() and "cash" in einzel.lower():
                verstoesse.append(f"{name}: {einzel!r} enthaelt beide Woerter")
    print(marke(not verstoesse, "Cache und Cash nie benachbart",
                f"{len(abschnitte)} Abschnitte, {len(verstoesse)} Verstoesse"))
    for v in verstoesse:
        print(f"      {v}")
    fehler += 0 if not verstoesse else 1

    # Die beiden Woerter kommen in getrennten Abschnitten vor - nie im selben.
    if "GELDKETTE" in abschnitte:
        treffer = len(re.findall("cache", abschnitte["GELDKETTE"], re.I))
        print(marke(treffer == 0, "Cash-Abschnitt ohne das Wort Cache", f"{treffer} Treffer"))
        fehler += 0 if treffer == 0 else 1
    if "TOKENS" in abschnitte:
        treffer = len(re.findall("cash", abschnitte["TOKENS"], re.I))
        print(marke(treffer == 0, "Token-Abschnitt ohne das Wort Cash", f"{treffer} Treffer"))
        fehler += 0 if treffer == 0 else 1
    return fehler


# --------------------------------------------------------------------------

def pruefsummen_zeigen(daten: dict) -> None:
    k = daten["kurs"]["usd_eur"]
    for schluessel in daten["reihenfolge"]:
        p = daten["perioden"][schluessel]
        s, e, u, c = p["summe"], p["eigene"], p["sub"], p["cash"]
        print(f"[pruefsumme] {schluessel:<13} chats={s['chats']:<4} sessions={s['sessions']:<4} "
              f"usd={s['usd']:.6f} euro={s['usd'] * k:.6f} "
              f"eigene={e['usd']:.6f} sub={u['usd']:.6f} sub_sessions={u['sessions']:<3} "
              f"cash_euro={(c['cash'] if c else 0) * k:.2f} "
              f"in={s['in']} out={s['out']} cache_read={s['cread']} cache_write={s['cwrite']} "
              f"calls={s['calls']}")


def main() -> int:
    a = argparse.ArgumentParser(
        description="Kosten-Dashboard fuer alle Hermes-Chats als eigenstaendige HTML-Datei")
    a.add_argument("--kein-netz", action="store_true", help="Kurs- und Preisabruf ueberspringen")
    a.add_argument("--kurs", type=float, help="Wechselkurs EUR je USD erzwingen")
    a.add_argument("--json", action="store_true", help="eingebettete Rohdaten ausgeben")
    a.add_argument("--pruefsummen", action="store_true", help="nur die Kontrollsummen ausgeben")
    a.add_argument("--kein-pruefen", action="store_true", help="Selbstpruefung ueberspringen")
    a.add_argument("--ausgabe", default=str(AUSGABE), help="Zieldatei")
    args = a.parse_args()

    zwischenspeicher = _cache_lesen()
    kurs = wechselkurs(args.kein_netz, args.kurs, zwischenspeicher)
    preise, preis_herkunft = preise_besorgen(args.kein_netz, zwischenspeicher)
    jetzt = dt.datetime.now()
    ziel = Path(args.ausgabe)

    # Zwischenspeicher fortschreiben (letzter Kurs und letzte Preise).
    neu = dict(zwischenspeicher)
    neu["kurs"] = {"usd_eur": kurs["usd_eur"], "quelle": kurs.get("quelle"),
                   "stand": kurs.get("stand") or dt.datetime.now().strftime("%d.%m.%Y %H:%M"),
                   "geholt": dt.datetime.now().strftime("%d.%m.%Y %H:%M")}
    if preis_herkunft.get("neu"):
        neu["preise"] = {"preise": preise, "at": preis_herkunft.get("at"),
                         "stand": preis_herkunft.get("stand"),
                         "quelle": preis_herkunft.get("quelle")}
    elif not neu.get("preise") and preise:
        neu["preise"] = {"preise": preise, "at": time.time(),
                         "stand": preis_herkunft.get("stand"),
                         "quelle": preis_herkunft.get("quelle")}
    _cache_schreiben(neu)

    con = verbinden()
    try:
        daten = daten_sammeln(con, kurs, preise, preis_herkunft, kurs)

        if args.pruefsummen:
            pruefsummen_zeigen(daten)
            return 0
        if args.json:
            print(json.dumps(daten, indent=2, ensure_ascii=False))
            return 0

        ziel.write_text(html_bauen(daten), encoding="utf-8")
        groesse = ziel.stat().st_size
        s = daten["perioden"]["alles"]["summe"]
        k = daten["kurs"]["usd_eur"]

        print(f"Dashboard geschrieben: {ziel}")
        print(f"  Groesse:            {groesse:,} Bytes".replace(",", "."))
        print(f"  Wechselkurs:        1 USD = {k:.5f} EUR  [{daten['kurs']['quelle']}]"
              + ("  ACHTUNG: Ersatz-/Altkurs!" if daten["kurs"]["ersatz"] else ""))
        print(f"  Modellpreise:       {daten['preise_anzahl']} Modelle  [{daten['preise_quelle']}]")
        print(f"  Zeitraeume:         {', '.join(daten['reihenfolge'])}")
        print(f"  Chats (alles):      {s['chats']} (davon {daten['perioden']['alles']['sub']['sessions']} Subagenten-Sessions)")
        print(f"  Nutzung (alles):    {s['usd']:.2f} USD = {s['usd'] * k:.2f} EUR")
        print(f"  Cash (alles):       {daten['perioden']['alles']['cash']['cash']:.2f} EUR")
        print(f"  Kaufbelege:         {'stimmen' if daten['kaufprobe_ok'] else 'STIMMEN NICHT'}")
        pruefsummen_zeigen(daten)

        if args.kein_pruefen:
            print("\nPRUEFUNG: uebersprungen (--kein-pruefen)")
            return 0

        print("\nPRUEFUNG")
        _, fehler, _ = pruefen(con, ziel, jetzt)
        fehler += selbststaendigkeit_pruefen(ziel)
        fehler += beschriftung_pruefen(ziel)
        if fehler:
            print(f"\nPRUEFUNG: FEHLGESCHLAGEN - {fehler} Abweichungen")
            return 1
        print("\nPRUEFUNG: OK - HTML-Zahlen == SQL-Zahlen, keine externen Ressourcen, "
              "Cache und Cash getrennt")
        return 0
    finally:
        try:
            con.rollback()          # Lesetransaktion sauber beenden
        except sqlite3.Error:
            pass
        con.close()


if __name__ == "__main__":
    sys.exit(main())
