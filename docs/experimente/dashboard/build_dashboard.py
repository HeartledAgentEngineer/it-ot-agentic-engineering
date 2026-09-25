#!/usr/bin/env python
"""Kosten-Dashboard: alle Hermes-Chats/Sessions aufgeschluesselt als HTML.

WARUM DIESES SKRIPT:
  Die OpenRouter-Activity-Seite zeigt nur die reinen API-Kosten in USD. Sie
  kennt weder den Chat (nur das Modell), noch die echten Ausgaben: auf jede
  Aufladung kommen 5,5 % Servicegebuehr (Minimum $0,80) und 19 % deutsche USt.
  Die tatsaechlich bezahlten Euro stehen nur hier - aus der eigenen Datenbank.

WAS ES LIEST:
  %LOCALAPPDATA%/hermes/state.db, Tabelle session_model_usage (pro Session
  UND Modell) plus sessions (Titel). Immer read-only geoeffnet.

DIE FALLE (schon in chat_kosten.py dokumentiert):
  last_seen/first_seen sind UNIX-Zeitstempel als REAL (z. B. 1790344497.394741),
  KEINE Datumsstrings.
      falsch:  date(last_seen) = date('now')                    -> immer 0 Zeilen
      richtig: last_seen >= strftime('%s','now','start of day','localtime')

DAS GEBUEHRENMODELL (an drei echten Kaufdialogen verifiziert):
  Servicegebuehr 5,5 % des Guthabens, Minimum $0,80 je Aufladung,
  danach 19 % USt auf (Guthaben + Service).
  Gesamtfaktor 1,055 x 1,19 = 1,25545  (+25,5 %).
      $17,00 -> $0,94 + $3,41 = $21,35
      $20,00 -> $1,10 + $4,01 = $25,11
      $200,00 -> $11,00 + $40,09 = $251,09
  Unter $14,55 Aufladung greift das Minimum - der Aufschlag ist dann hoeher.

Benutzung:
    python build_dashboard.py                 # HTML erzeugen (Live-Wechselkurs)
    python build_dashboard.py --kein-netz     # Kurs-API ueberspringen (0.8787)
    python build_dashboard.py --kurs 0.88     # Kurs erzwingen
    python build_dashboard.py --json          # eingebettete Rohdaten nach stdout
    python build_dashboard.py --pruefsummen   # nur die Kontrollsummen ausgeben
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
import urllib.request
from pathlib import Path

DB = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "state.db"
HIER = Path(__file__).resolve().parent
AUSGABE = HIER / "dashboard.html"

KURS_URL = "https://open.er-api.com/v6/latest/USD"
KURS_FALLBACK = 0.8787               # EUR je USD

SERVICE_SATZ = 0.055                 # OpenRouter-Gebuehr beim Aufladen
SERVICE_MIN = 0.80                   # Mindestgebuehr je Aufladung (USD)
UST_SATZ = 0.19                      # deutsche Umsatzsteuer
AUFSCHLAG = (1 + SERVICE_SATZ) * (1 + UST_SATZ)     # 1.25545
BREAK_EVEN = SERVICE_MIN / SERVICE_SATZ             # $14,55

# Zeitraum -> (Beschriftung, SQL-Grenzausdruck auf last_seen, Verlaufsfenster)
ZEITRAEUME = [
    ("heute", "Heute",
     "strftime('%s','now','start of day','localtime')", "letzte7"),
    ("woche", "Woche (ab Montag)",
     "strftime('%s','now','weekday 1','-7 days','start of day','localtime')", "letzte7"),
    ("7tage", "Letzte 7 Tage",
     "strftime('%s','now','-7 days')", "letzte7"),
    ("monat", "Monat",
     "strftime('%s','now','start of month','localtime')", "monat"),
    ("alles", "Alles",
     "0", "alles"),
]

# --- SQL: identische Semantik wie chat_kosten.py (damit die Summen passen) ---

SQL_AGGREGAT = """
    SELECT SUM(u.estimated_cost_usd)                         AS usd,
           SUM(u.input_tokens)                              AS tok_in,
           SUM(u.output_tokens)                             AS tok_out,
           SUM(u.cache_read_tokens)                         AS tok_cread,
           SUM(u.cache_write_tokens)                        AS tok_cwrite,
           SUM(u.api_call_count)                            AS calls,
           COUNT(DISTINCT u.session_id)                     AS chats
    FROM session_model_usage u
    WHERE u.last_seen >= {grenze}
"""

SQL_CHATS = """
    SELECT u.session_id,
           COALESCE(NULLIF(s.title,''), NULLIF(s.display_name,''),
                    substr(u.session_id,1,18))              AS titel,
           SUM(u.estimated_cost_usd)                        AS kosten_usd,
           SUM(u.input_tokens)                              AS tok_in,
           SUM(u.output_tokens)                             AS tok_out,
           SUM(u.cache_read_tokens)                         AS tok_cread,
           SUM(u.cache_write_tokens)                        AS tok_cwrite,
           SUM(u.api_call_count)                            AS calls,
           MIN(u.last_seen)                                 AS von,
           MAX(u.last_seen)                                 AS bis,
           COALESCE(MAX(s.message_count),0)                 AS turns,
           COALESCE(MAX(s.tool_call_count),0)               AS tools
    FROM session_model_usage u
    LEFT JOIN sessions s ON s.id = u.session_id
    WHERE u.last_seen >= {grenze}
    GROUP BY u.session_id
    HAVING kosten_usd > 0
    ORDER BY kosten_usd DESC
"""

SQL_MODELLE = """
    SELECT COALESCE(NULLIF(u.model,''), '?')                 AS modell,
           SUM(u.estimated_cost_usd)                        AS kosten_usd,
           SUM(u.input_tokens)                              AS tok_in,
           SUM(u.output_tokens)                             AS tok_out,
           SUM(u.cache_read_tokens)                         AS tok_cread,
           SUM(u.cache_write_tokens)                        AS tok_cwrite,
           SUM(u.api_call_count)                            AS calls,
           COUNT(DISTINCT u.session_id)                     AS chats
    FROM session_model_usage u
    WHERE u.last_seen >= {grenze}
    GROUP BY modell
    HAVING kosten_usd > 0
    ORDER BY kosten_usd DESC
"""

SQL_TAGE = """
    SELECT date(u.last_seen,'unixepoch','localtime')        AS tag,
           SUM(u.estimated_cost_usd)                        AS kosten_usd,
           SUM(u.input_tokens)                              AS tok_in,
           SUM(u.output_tokens)                             AS tok_out,
           SUM(u.cache_read_tokens)                         AS tok_cread,
           SUM(u.api_call_count)                            AS calls,
           COUNT(DISTINCT u.session_id)                     AS chats
    FROM session_model_usage u
    WHERE u.last_seen >= 0
    GROUP BY tag
    ORDER BY tag
"""


# --------------------------------------------------------------------------
# Daten holen
# --------------------------------------------------------------------------

def wechselkurs(kein_netz: bool, fest: float | None) -> tuple[float, str]:
    """EUR je USD. Live von der Kurs-API, sonst fester Rueckfallwert."""
    if fest is not None:
        return fest, "fest vorgegeben (--kurs)"
    if kein_netz:
        return KURS_FALLBACK, "fest (--kein-netz)"
    try:
        with urllib.request.urlopen(KURS_URL, timeout=12) as r:
            daten = json.load(r)
        kurs = (daten.get("rates") or {}).get("EUR")
        if kurs:
            return float(kurs), "live (open.er-api.com)"
    except Exception as e:                       # noqa: BLE001 - Rueckfall ist gewollt
        return KURS_FALLBACK, f"fest (Kurs-API nicht erreichbar: {type(e).__name__})"
    return KURS_FALLBACK, "fest (kein EUR-Kurs in der Antwort)"


def verbinden() -> sqlite3.Connection:
    if not DB.is_file():
        sys.exit(f"Datenbank nicht gefunden: {DB}")
    # IMMER read-only - das Dashboard darf die Session-DB nie veraendern.
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=20)
    # Eine Lesetransaktion = EIN eingefrorener Stand (die DB laeuft im
    # WAL-Modus, Leser blockieren keine Schreiber). Dadurch stammen alle
    # Zahlen des Dashboards aus demselben Augenblick: wichtig, weil die
    # laufende Sitzung nebenher in dieselbe Tabelle schreibt.
    con.execute("BEGIN")
    return con


def grenze_epoch(con: sqlite3.Connection, ausdruck: str) -> float:
    return float(con.execute(f"SELECT {ausdruck}").fetchone()[0])


def zeitpunkt(epoch: float | None, mit_zeit: bool = True) -> str:
    if not epoch:
        return "—"
    d = dt.datetime.fromtimestamp(epoch)
    return d.strftime("%d.%m. %H:%M") if mit_zeit else d.strftime("%d.%m.%Y")


def hole_chats(con, grenze: str) -> list[dict]:
    out = []
    for (sid, titel, usd, ti, to, tc, tw, calls, von, bis, turns, tools) in \
            con.execute(SQL_CHATS.format(grenze=grenze)):
        usd = usd or 0.0
        ti, to, tc, tw = ti or 0, to or 0, tc or 0, tw or 0
        out.append({
            "id": sid,
            "titel": titel or sid,
            "usd": round(usd, 6),
            "in": ti, "out": to, "cread": tc, "cwrite": tw,
            "tok": ti + to + tc + tw,
            "quote": round(tc / (ti + tc) * 100, 1) if (ti + tc) else 0.0,
            "calls": calls or 0,
            "turns": turns or 0, "tools": tools or 0,
            "von": zeitpunkt(von), "bis": zeitpunkt(bis),
        })
    return out


def hole_modelle(con, grenze: str) -> list[dict]:
    out = []
    for (modell, usd, ti, to, tc, tw, calls, chats) in \
            con.execute(SQL_MODELLE.format(grenze=grenze)):
        usd = usd or 0.0
        ti, to, tc, tw = ti or 0, to or 0, tc or 0, tw or 0
        out.append({
            "modell": modell,
            "usd": round(usd, 6),
            "in": ti, "out": to, "cread": tc, "cwrite": tw,
            "tok": ti + to + tc + tw,
            "quote": round(tc / (ti + tc) * 100, 1) if (ti + tc) else 0.0,
            "calls": calls or 0, "chats": chats or 0,
        })
    return out


def hole_tage(con) -> list[dict]:
    out = []
    for (tag, usd, ti, to, tc, calls, chats) in con.execute(SQL_TAGE):
        out.append({
            "tag": tag, "usd": round(usd or 0.0, 6),
            "in": ti or 0, "out": to or 0, "cread": tc or 0,
            "calls": calls or 0, "chats": chats or 0,
        })
    return out


def summen(aggregat: tuple, chats: list[dict]) -> dict:
    """Kontrollsummen eines Zeitraums.

    Kosten und Token kommen DIREKT aus dem SQL-Aggregat, nicht aus der Summe
    der gerundeten Chat-Zeilen - so zeigt das Dashboard exakt den Wert, den
    auch eine direkte Abfrage der Datenbank liefert. Turns/Tools werden aus den
    Chat-Zeilen addiert (ganze Zahlen, keine Rundung).
    """
    usd, s_in, s_out, s_cread, s_cwrite, s_calls, anzahl = aggregat
    usd = usd or 0.0
    s_in, s_out, s_cread = s_in or 0, s_out or 0, s_cread or 0
    s_cwrite, s_calls, anzahl = s_cwrite or 0, s_calls or 0, anzahl or 0
    return {
        "usd": round(usd, 6),
        "in": s_in, "out": s_out, "cread": s_cread, "cwrite": s_cwrite,
        "tok": s_in + s_out + s_cread + s_cwrite,
        "quote": round(s_cread / (s_in + s_cread) * 100, 1) if (s_in + s_cread) else 0.0,
        "calls": s_calls,
        "turns": sum(c["turns"] for c in chats),
        "tools": sum(c["tools"] for c in chats),
        "chats": len(chats), "anzahl": anzahl,
    }


def kauf_rechnen(guthaben_usd: float) -> tuple[float, float, float]:
    """(Service, USt, Cash) - wie auf der Rechnung: jeder Posten auf Cent gerundet."""
    service = round(max(guthaben_usd * SERVICE_SATZ, SERVICE_MIN), 2)
    ust = round((guthaben_usd + service) * UST_SATZ, 2)
    return service, ust, guthaben_usd + service + ust


def tagesfenster(schluessel: str, tage_alle: list[dict], heute: dt.date) -> tuple[str, str]:
    """(erster Tag ISO, Beschriftung) fuer den Verlauf dieses Zeitraums."""
    if schluessel in ("heute", "woche", "7tage"):
        ab = heute - dt.timedelta(days=6)
        return ab.isoformat(), "Verlauf: letzte 7 Tage"
    if schluessel == "monat":
        ab = heute.replace(day=1)
        return ab.isoformat(), f"Verlauf: {ab.strftime('%d.%m.')} bis heute"
    if tage_alle:
        ab = dt.date.fromisoformat(tage_alle[0]["tag"])
        return ab.isoformat(), f"Verlauf: gesamter Zeitraum ab {ab.strftime('%d.%m.%Y')}"
    return heute.isoformat(), "Verlauf"


def daten_sammeln(con, kurs: float) -> dict:
    heute = dt.date.today()
    alle_tage = hole_tage(con)

    perioden: dict[str, dict] = {}
    for schluessel, label, ausdruck, _fenster in ZEITRAEUME:
        chats = hole_chats(con, ausdruck)
        modelle = hole_modelle(con, ausdruck)
        aggregat = con.execute(SQL_AGGREGAT.format(grenze=ausdruck)).fetchone()
        s = summen(aggregat, chats)

        if schluessel == "alles" and alle_tage:
            von_iso = alle_tage[0]["tag"]
        else:
            von_iso = dt.datetime.fromtimestamp(grenze_epoch(con, ausdruck)).strftime("%Y-%m-%d")
        bis_iso = heute.isoformat()

        ab, verlauf_label = tagesfenster(schluessel, alle_tage, heute)
        verlauf = [t for t in alle_tage if t["tag"] >= ab]

        perioden[schluessel] = {
            "label": label,
            "von": von_iso, "bis": bis_iso,
            "summe": s,
            "chats": chats,
            "modelle": modelle,
            "verlauf": verlauf,
            "verlauf_label": verlauf_label,
        }

    return {
        "erzeugt": dt.datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "kurs": kurs,
        "aufschlag": AUFSCHLAG,
        "service_satz": SERVICE_SATZ,
        "service_min": SERVICE_MIN,
        "ust_satz": UST_SATZ,
        "break_even": BREAK_EVEN,
        "perioden": perioden,
        "reihenfolge": [z[0] for z in ZEITRAEUME],
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
   die Oberflaeche des Hosts durchscheint.
   Farben: erst die Variablen des Hosts, sonst eigene Rueckfallwerte.
   Die Rueckfall-Ebene steht in --fb-* und wird im Dark-Block getauscht;
   dadurch gewinnt IMMER eine vom Host gesetzte Variable, und nur wenn
   keine da ist, greift der passende helle/dunkle Rueckfall.
   ------------------------------------------------------------------ */
:root{
  --fb-fg:#1b1b20; --fb-muted:#5c5c68; --fb-strong:#000;
  --fb-border:rgba(96,96,112,.28);
  --fb-panel:rgba(96,96,112,.10);
  --fb-panel2:rgba(96,96,112,.05);
  --fb-ok:#127a44; --fb-mid:#8a6100; --fb-bad:#b3261e;
}
@media (prefers-color-scheme: dark){
  :root{
    --fb-fg:#ececf1; --fb-muted:#a8a8b6; --fb-strong:#fff;
    --fb-border:rgba(214,214,232,.30);
    --fb-panel:rgba(214,214,232,.10);
    --fb-panel2:rgba(214,214,232,.05);
    --fb-ok:#41d17f; --fb-mid:#e8c04a; --fb-bad:#ff7369;
  }
}
:root{
  --fg: var(--foreground, var(--fb-fg));
  --muted: var(--muted-foreground, var(--fb-muted));
  --strong: var(--foreground, var(--fb-strong));
  --border: var(--border-color, var(--fb-border));
  --panel: var(--fb-panel);
  --panel2: var(--fb-panel2);
  --ok: var(--fb-ok); --mid: var(--fb-mid); --bad: var(--fb-bad);
  --kurve: var(--primary, var(--fb-fg));
}
html{ background: transparent; }
body{
  background: transparent;
  color: var(--fg);
  font-family: inherit;
  font-size: 14px;
  line-height: 1.45;
  margin: 0;
  padding: 14px 16px 34px;
}
h1{ font-size: 19px; margin: 0 0 2px; color: var(--strong); font-weight: 650; letter-spacing: .1px; }
h2{ font-size: 14px; margin: 26px 0 8px; color: var(--strong); font-weight: 650;
    text-transform: uppercase; letter-spacing: .06em; }
h2 .zusatz{ text-transform: none; letter-spacing: 0; color: var(--muted); font-weight: 400; margin-left: 6px; }
.meta{ color: var(--muted); font-size: 12px; }
.num{ font-variant-numeric: tabular-nums; }

/* --- Zeitraum-Umschalter --- */
.reiter{ display: flex; flex-wrap: wrap; gap: 6px; margin: 14px 0 4px; }
.reiter button{
  font-family: inherit; font-size: 13px; color: var(--fg);
  background: var(--panel2); border: 1px solid var(--border);
  border-radius: 7px; padding: 5px 12px; cursor: pointer;
}
.reiter button:hover{ background: var(--panel); }
.reiter button.aktiv{
  background: var(--panel); border-color: var(--fg);
  color: var(--strong); font-weight: 650;
}
.zeitraum-info{ color: var(--muted); font-size: 12px; margin-bottom: 10px; }

/* --- Kennzahlen --- */
.kpi{ display: grid; grid-template-columns: repeat(auto-fit, minmax(148px, 1fr)); gap: 8px; }
.kpi .karte{
  background: var(--panel); border: 1px solid var(--border);
  border-radius: 9px; padding: 9px 11px;
}
.kpi .titel{ color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .05em; }
.kpi .wert{ color: var(--strong); font-size: 20px; font-weight: 650; margin-top: 2px; }
.kpi .fuss{ color: var(--muted); font-size: 11px; }
.kpi .karte.betont{ border-color: var(--fg); }

/* --- Cash-Kasten --- */
.cash{
  background: var(--panel); border: 1px solid var(--border);
  border-left: 3px solid var(--fg); border-radius: 9px;
  padding: 11px 14px; margin-top: 10px;
}
.cash .zeile{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; margin: 2px 0; }
.cash .bez{ color: var(--muted); min-width: 190px; }
.cash .gross{ color: var(--strong); font-size: 22px; font-weight: 700; }
.cash .klein{ color: var(--muted); font-size: 12px; }
.cash .pfeil{ color: var(--muted); }

/* --- Tabellen --- */
.tabwrap{ overflow: auto; max-height: 620px; border: 1px solid var(--border); border-radius: 9px; }
table{ border-collapse: collapse; width: 100%; font-size: 13px; }
th, td{ padding: 5px 9px; text-align: right; white-space: nowrap; border-bottom: 1px solid var(--border); }
th:first-child, td:first-child, th.l, td.l{ text-align: left; }
thead th{
  position: sticky; top: 0; color: var(--muted); font-weight: 600; font-size: 11px;
  text-transform: uppercase; letter-spacing: .04em;
  background: var(--panel); backdrop-filter: blur(6px);
  border-bottom: 1px solid var(--border);
}
tbody tr:hover{ background: var(--panel2); }
tbody tr:last-child td{ border-bottom: none; }
td.name{ max-width: 340px; overflow: hidden; text-overflow: ellipsis; }
.tr-top1{ background: rgba(255,196,0,.14); }
.tr-top2{ background: rgba(255,196,0,.09); }
.tr-top3{ background: rgba(255,196,0,.05); }
.tr-top1 td:first-child, .tr-top2 td:first-child, .tr-top3 td:first-child{ font-weight: 700; }
tfoot td{ font-weight: 700; color: var(--strong); background: var(--panel); border-top: 1px solid var(--border); }

/* --- Cache-Quote einfaerben --- */
.cq{ font-weight: 650; }
.cq-ok{ color: var(--ok); }
.cq-mid{ color: var(--mid); }
.cq-bad{ color: var(--bad); }
.legende{ color: var(--muted); font-size: 12px; margin-top: 5px; }
.legende b{ color: var(--ok); } .legende i{ color: var(--mid); font-style: normal; }
.legende u{ color: var(--bad); text-decoration: none; }

/* --- Verlauf (Balken) --- */
.verlauf{ display: flex; align-items: flex-end; gap: 4px; overflow-x: auto; padding: 8px 4px 0; min-height: 150px; }
.balken{ flex: 1 0 34px; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; }
.balken .wert{ font-size: 10px; color: var(--muted); margin-bottom: 3px; font-variant-numeric: tabular-nums; }
.balken .stab{ width: 100%; max-width: 42px; background: var(--kurve); opacity: .65; border-radius: 3px 3px 0 0; min-height: 2px; }
.balken .stab.leer{ background: var(--border); opacity: .5; }
.balken .marke{ font-size: 10px; color: var(--muted); margin-top: 4px; font-variant-numeric: tabular-nums; }

/* --- Filter --- */
.filter{ display: flex; gap: 8px; align-items: center; margin: 0 0 8px; }
.filter input{
  font-family: inherit; font-size: 13px; color: var(--fg);
  background: var(--panel2); border: 1px solid var(--border);
  border-radius: 7px; padding: 5px 10px; min-width: 230px;
}
.filter .anz{ color: var(--muted); font-size: 12px; }

/* --- Fussnoten --- */
.notizen{ color: var(--muted); font-size: 12px; margin-top: 24px; line-height: 1.6; }
.notizen code{ font-family: ui-monospace, Consolas, monospace; color: var(--fg); }
.notizen ul{ margin: 4px 0 0; padding-left: 20px; }
.leermeldung{ color: var(--muted); padding: 14px; }
</style>
</head>
<body>

<h1>Hermes Kosten-Dashboard</h1>
<div class="meta" id="kopfzeile"></div>

<div class="reiter" id="reiter"></div>
<div class="zeitraum-info" id="zeitrauminfo"></div>

<div class="kpi" id="kpi"></div>
<div class="cash" id="cash"></div>

<h2>Chats <span class="zusatz" id="chattitel"></span></h2>
<div class="filter">
  <input id="filter" type="text" placeholder="Chat filtern (Titel oder ID) ..." autocomplete="off">
  <span class="anz" id="filteranz"></span>
</div>
<div class="tabwrap">
  <table id="chattabelle">
    <thead><tr>
      <th class="l">#</th><th class="l">Chat</th>
      <th>EUR</th><th>USD</th>
      <th>Input</th><th>Output</th><th>Cache-Read</th><th>Cache-Write</th><th>Tokens ges.</th>
      <th>Cache-Quote</th><th>API-Calls</th><th>Turns</th><th>Tools</th>
      <th class="l">von</th><th class="l">bis</th>
    </tr></thead>
    <tbody id="chatbody"></tbody>
    <tfoot id="chatfuss"></tfoot>
  </table>
</div>
<div class="legende">Cache-Quote = Cache-Read / (Input + Cache-Read) ·
  <b>grün ab 75 %</b> · <i>gelb ab 50 %</i> · <u>rot darunter</u> · Top-3-Chats farblich hervorgehoben</div>

<h2>Aufschlüsselung nach Modell</h2>
<div class="tabwrap">
  <table id="modelltabelle">
    <thead><tr>
      <th class="l">Modell</th><th>Chats</th>
      <th>EUR</th><th>USD</th><th>Anteil</th>
      <th>Input</th><th>Output</th><th>Cache-Read</th><th>Cache-Write</th>
      <th>Cache-Quote</th><th>API-Calls</th>
    </tr></thead>
    <tbody id="modellbody"></tbody>
    <tfoot id="modellfuss"></tfoot>
  </table>
</div>

<h2 id="verlauftitel">Verlauf</h2>
<div class="verlauf" id="verlauf"></div>

<div class="notizen">
  <strong>Wie gerechnet wird</strong>
  <ul>
    <li>Quelle: <code>state.db</code>, Tabelle <code>session_model_usage</code> (eine Zeile je
        Session und Modell), Titel aus <code>sessions</code>; read-only geöffnet.
        Zeitraumfilter auf <code>last_seen</code> (UNIX-Zeitstempel als REAL).</li>
    <li>Wechselkurs: 1 USD = <span id="notiz-kurs"></span> EUR, <span id="notiz-kursart"></span>.
        Kursänderungen ändern die EUR-Spalte, nicht die USD-Spalte.</li>
    <li>Die USD-Zahlen sind <code>estimated_cost_usd</code> — die von Hermes berechnete
        Kostenschätzung. <code>actual_cost_usd</code> ist in dieser Datenbank durchgehend 0,
        es gibt also keinen abgerechneten Gegenwert zum Vergleich.</li>
    <li>Cash (echte Ausgaben) = API-Kosten × 1,25545: beim Aufladen kommen
        5,5 % Servicegebühr und danach 19 % USt auf (Guthaben + Service) hinzu.
        Verifiziert an echten Kaufdialogen.</li>
    <li>Unter <span id="notiz-be"></span> USD Aufladung greift die Mindestgebühr von
        0,80 USD — der Aufschlag ist dann höher als 25,5 %. Bezogen auf den
        gesamten Verbrauch gilt der Faktor 1,25545, weil über dieser Grenze aufgeladen wird.</li>
    <li>„Tokens ges." = Input + Output + Cache-Read + Cache-Write.</li>
    <li>Reine API-Kosten vs. Cash: OpenRouter zeigt in seiner Activity-Ansicht die
        reinen API-Kosten in USD und ohne Bezug zum einzelnen Chat — die
        Servicegebühr und die USt tauchen dort nirgends auf.</li>
  </ul>
</div>

<script>
const D = /*__DATEN__*/ null;
</script>
<script>
(function(){
  var PERIODEN = D.perioden, REIHE = D.reihenfolge, A = D.aufschlag;
  var aktuell = REIHE[0];
  var filterText = "";

  function esc(s){
    return String(s === null || s === undefined ? "" : s)
      .replace(/[&<>"']/g, function(c){
        return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
      });
  }
  function n(v, stellen){
    v = v || 0;
    return v.toLocaleString("de-DE", {minimumFractionDigits: stellen, maximumFractionDigits: stellen});
  }
  function eur(v){ return n(v, 2) + " €"; }
  function usd(v){ return n(v, 2) + " $"; }
  function ganz(v){ return (v || 0).toLocaleString("de-DE"); }
  function proz(v){ return n(v, 1) + " %"; }
  function mio(v){ return (v || 0).toLocaleString("de-DE"); }
  function datumKurz(iso){
    var t = String(iso || "").split("-");
    return t.length === 3 ? t[2] + "." + t[1] + "." : iso;
  }
  function cqKlasse(q){ return q >= 75 ? "cq-ok" : (q >= 50 ? "cq-mid" : "cq-bad"); }

  function kopf(){
    document.getElementById("kopfzeile").innerHTML =
      "Stand " + esc(D.erzeugt) + " · Wechselkurs 1 USD = " + n(D.kurs, 4) + " EUR ("
      + esc(D.kurs_quelle || "") + ") · Aufschlag beim Aufladen: ×" + n(A, 5)
      + " (+" + n((A - 1) * 100, 1) + " %)";
    document.getElementById("notiz-kurs").textContent = n(D.kurs, 4);
    document.getElementById("notiz-kursart").textContent = D.kurs_quelle || "";
    document.getElementById("notiz-be").textContent = n(D.break_even, 2);
  }

  function reiter(){
    var h = "";
    REIHE.forEach(function(k){
      h += '<button data-p="' + esc(k) + '" class="' + (k === aktuell ? "aktiv" : "") + '">'
         + esc(PERIODEN[k].label) + "</button>";
    });
    document.getElementById("reiter").innerHTML = h;
    Array.prototype.forEach.call(document.querySelectorAll("#reiter button"), function(b){
      b.addEventListener("click", function(){ aktuell = b.getAttribute("data-p"); filternZuruecksetzen(); zeichnen(); });
    });
  }

  function filternZuruecksetzen(){ filterText = ""; document.getElementById("filter").value = ""; }

  function kpi(){
    var p = PERIODEN[aktuell], s = p.summe;
    var cashEur = s.usd * D.kurs * A;
    var karten = [
      ["API-Kosten (USD)", usd(s.usd), "reine Modellkosten"],
      ["API-Kosten (EUR)", eur(s.usd * D.kurs), "nur umgerechnet"],
      ["Cash (echt, EUR)", eur(cashEur), "inkl. Service + USt", true],
      ["Chats", ganz(s.chats), "von " + ganz(s.anzahl) + " mit Verbrauch"],
      ["Cache-Quote", proz(s.quote), "Cache-Read / (Input + Cache-Read)"],
      ["Tokens gesamt", ganz(s.tok), ganz(s.in) + " in / " + ganz(s.out) + " out"],
      ["API-Calls", ganz(s.calls), "Aufrufe im Zeitraum"],
      ["Aufschlag absolut (EUR)", eur(cashEur - s.usd * D.kurs), "Service + USt"],
    ];
    document.getElementById("kpi").innerHTML = karten.map(function(k){
      return '<div class="karte' + (k[3] ? " betont" : "") + '">'
        + '<div class="titel">' + esc(k[0]) + "</div>"
        + '<div class="wert num">' + esc(k[1]) + "</div>"
        + '<div class="fuss">' + esc(k[2]) + "</div></div>";
    }).join("");
  }

  function cash(){
    var p = PERIODEN[aktuell], s = p.summe;
    var u = s.usd, service = u * D.service_satz, ust = (u + service) * D.ust_satz;
    var cashUsd = u * A, cashEur = cashUsd * D.kurs;
    var aufschlagEur = cashEur - u * D.kurs;
    var q = s.usd > 0 ? aufschlagEur / (u * D.kurs) * 100 : 0;
    document.getElementById("cash").innerHTML =
      '<div class="zeile"><span class="bez">Reine API-Kosten</span>'
        + '<span class="num">' + esc(usd(u)) + "</span>"
        + '<span class="klein num">= ' + esc(eur(u * D.kurs)) + "</span></div>"
      + '<div class="zeile"><span class="bez">+ Servicegebühr (5,5 %)</span>'
        + '<span class="num klein">' + esc(usd(service)) + " = " + esc(eur(service * D.kurs)) + "</span></div>"
      + '<div class="zeile"><span class="bez">+ USt 19 % auf Guthaben + Service</span>'
        + '<span class="num klein">' + esc(usd(ust)) + " = " + esc(eur(ust * D.kurs)) + "</span></div>"
      + '<div class="zeile"><span class="bez">= echte Ausgaben (Cash)</span>'
        + '<span class="gross num">' + esc(eur(cashEur)) + "</span>"
        + '<span class="klein num">= ' + esc(usd(cashUsd)) + "</span></div>"
      + '<div class="zeile"><span class="klein">Aufschlag gegenüber den reinen API-Kosten: '
        + '<span class="num">' + esc(eur(aufschlagEur)) + "</span> (" + esc(n(q, 1)) + " %)"
        + " · Zeitraum " + esc(p.von) + " bis " + esc(p.bis)
        + " · " + esc(ganz(s.chats)) + " Chats, " + esc(ganz(s.calls)) + " API-Calls</span></div>";
  }

  function chatTabelle(){
    var p = PERIODEN[aktuell], s = p.summe, chats = p.chats;
    var gefiltert = chats.filter(function(c){
      if (!filterText) return true;
      return (c.titel + " " + c.id).toLowerCase().indexOf(filterText) >= 0;
    });
    var h = "";
    gefiltert.forEach(function(c, i){
      var rang = chats.indexOf(c) + 1;
      var klasse = rang <= 3 ? ' class="tr-top' + rang + '"' : "";
      var titel = c.titel === c.id && /^[0-9a-f_]+$/.test(c.id) ? "(ohne Titel) " + c.id : c.titel;
      h += "<tr" + klasse + ">"
        + '<td class="l num">' + rang + "</td>"
        + '<td class="l name" title="' + esc(c.id) + '">' + esc(titel) + "</td>"
        + '<td class="num">' + esc(eur(c.usd * D.kurs)) + "</td>"
        + '<td class="num">' + esc(usd(c.usd)) + "</td>"
        + '<td class="num">' + ganz(c["in"]) + "</td>"
        + '<td class="num">' + ganz(c.out) + "</td>"
        + '<td class="num">' + ganz(c.cread) + "</td>"
        + '<td class="num">' + ganz(c.cwrite) + "</td>"
        + '<td class="num">' + ganz(c.tok) + "</td>"
        + '<td class="num cq ' + cqKlasse(c.quote) + '">' + esc(proz(c.quote)) + "</td>"
        + '<td class="num">' + ganz(c.calls) + "</td>"
        + '<td class="num">' + ganz(c.turns) + "</td>"
        + '<td class="num">' + ganz(c.tools) + "</td>"
        + '<td class="l">' + esc(c.von) + "</td>"
        + '<td class="l">' + esc(c.bis) + "</td></tr>";
    });
    if (!gefiltert.length){
      h = '<tr><td class="leermeldung l" colspan="15">Keine Chats im Filter.</td></tr>';
    }
    document.getElementById("chatbody").innerHTML = h;
    document.getElementById("chatfuss").innerHTML = "<tr>"
      + '<td class="l">Σ</td><td class="l">' + esc(ganz(s.chats)) + " Chats im Zeitraum</td>"
      + '<td class="num">' + esc(eur(s.usd * D.kurs)) + "</td>"
      + '<td class="num">' + esc(usd(s.usd)) + "</td>"
      + '<td class="num">' + ganz(s["in"]) + "</td>"
      + '<td class="num">' + ganz(s.out) + "</td>"
      + '<td class="num">' + ganz(s.cread) + "</td>"
      + '<td class="num">' + ganz(s.cwrite) + "</td>"
      + '<td class="num">' + ganz(s.tok) + "</td>"
      + '<td class="num cq ' + cqKlasse(s.quote) + '">' + esc(proz(s.quote)) + "</td>"
      + '<td class="num">' + ganz(s.calls) + "</td>"
      + '<td class="num">' + ganz(s.turns) + "</td>"
      + '<td class="num">' + ganz(s.tools) + "</td>"
      + '<td class="l"></td><td class="l"></td></tr>';
    document.getElementById("chattitel").textContent =
      "· " + (aktuell === "heute" ? "nur heute" : p.von + " bis " + p.bis);
    document.getElementById("filteranz").textContent =
      gefiltert.length === chats.length
        ? ganz(chats.length) + " Chats"
        : ganz(gefiltert.length) + " von " + ganz(chats.length) + " Chats";
  }

  function modellTabelle(){
    var p = PERIODEN[aktuell], s = p.summe, m = p.modelle;
    var h = "";
    m.forEach(function(x){
      var anteil = s.usd > 0 ? x.usd / s.usd * 100 : 0;
      h += "<tr>"
        + '<td class="l">' + esc(x.modell) + "</td>"
        + '<td class="num">' + ganz(x.chats) + "</td>"
        + '<td class="num">' + esc(eur(x.usd * D.kurs)) + "</td>"
        + '<td class="num">' + esc(usd(x.usd)) + "</td>"
        + '<td class="num">' + esc(proz(anteil)) + "</td>"
        + '<td class="num">' + ganz(x["in"]) + "</td>"
        + '<td class="num">' + ganz(x.out) + "</td>"
        + '<td class="num">' + ganz(x.cread) + "</td>"
        + '<td class="num">' + ganz(x.cwrite) + "</td>"
        + '<td class="num cq ' + cqKlasse(x.quote) + '">' + esc(proz(x.quote)) + "</td>"
        + '<td class="num">' + ganz(x.calls) + "</td></tr>";
    });
    if (!m.length) h = '<tr><td class="leermeldung l" colspan="11">Keine Daten.</td></tr>';
    document.getElementById("modellbody").innerHTML = h;
    document.getElementById("modellfuss").innerHTML = "<tr>"
      + '<td class="l">Σ</td><td class="num">' + ganz(s.chats) + "</td>"
      + '<td class="num">' + esc(eur(s.usd * D.kurs)) + "</td>"
      + '<td class="num">' + esc(usd(s.usd)) + "</td>"
      + '<td class="num">100,0 %</td>'
      + '<td class="num">' + ganz(s["in"]) + "</td>"
      + '<td class="num">' + ganz(s.out) + "</td>"
      + '<td class="num">' + ganz(s.cread) + "</td>"
      + '<td class="num">' + ganz(s.cwrite) + "</td>"
      + '<td class="num cq ' + cqKlasse(s.quote) + '">' + esc(proz(s.quote)) + "</td>"
      + '<td class="num">' + ganz(s.calls) + "</td></tr>";
  }

  function verlauf(){
    var p = PERIODEN[aktuell], tage = p.verlauf;
    document.getElementById("verlauftitel").innerHTML =
      "Verlauf <span class=\"zusatz\">" + esc(p.verlauf_label) + "</span>";
    if (!tage.length){
      document.getElementById("verlauf").innerHTML =
        '<div class="leermeldung">Keine Tagesdaten.</div>';
      return;
    }
    var max = 0;
    tage.forEach(function(t){ if (t.usd > max) max = t.usd; });
    var h = "";
    tage.forEach(function(t){
      var hoehe = max > 0 ? Math.max(2, Math.round(t.usd / max * 118)) : 2;
      var leer = t.usd <= 0 ? " leer" : "";
      var wt = ["So","Mo","Di","Mi","Do","Fr","Sa"][new Date(t.tag + "T12:00:00").getDay()];
      h += '<div class="balken" title="' + esc(t.tag) + ": " + esc(eur(t.usd * D.kurs))
         + " · " + ganz(t.calls) + " Calls · " + ganz(t.chats) + ' Chats">'
         + '<div class="wert">' + esc(n(t.usd * D.kurs, 2)) + "</div>"
         + '<div class="stab' + leer + '" style="height:' + hoehe + 'px"></div>'
         + '<div class="marke">' + esc(wt) + "<br>" + esc(datumKurz(t.tag)) + "</div></div>";
    });
    document.getElementById("verlauf").innerHTML = h;
  }

  function zeichnen(){
    var p = PERIODEN[aktuell];
    document.getElementById("zeitrauminfo").textContent =
      p.label + " · " + p.von + " bis " + p.bis;
    Array.prototype.forEach.call(document.querySelectorAll("#reiter button"), function(b){
      b.className = b.getAttribute("data-p") === aktuell ? "aktiv" : "";
    });
    kpi(); cash(); chatTabelle(); modellTabelle(); verlauf();
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
    js = json.dumps(daten, ensure_ascii=False)
    # Ein "</script>" im Datenblock wuerde das Script-Element beenden.
    js = js.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return VORLAGE.replace("/*__DATEN__*/ null", js)


# --------------------------------------------------------------------------
# Gegenprobe: das, was WIRKLICH in der Datei steht, gegen direkte SQL-Abfragen
# --------------------------------------------------------------------------

MARKER_ANFANG = "const D = "
MARKER_ENDE = "\n</script>"

# Eigene, unabhaengige Abfragen (bewusst nicht die Konstanten oben).
PRUEF_SUMME = """
    SELECT SUM(u.estimated_cost_usd), SUM(u.input_tokens), SUM(u.output_tokens),
           SUM(u.cache_read_tokens), SUM(u.cache_write_tokens),
           SUM(u.api_call_count), COUNT(DISTINCT u.session_id)
    FROM session_model_usage u
    WHERE u.last_seen >= {grenze}
"""

PRUEF_CHATS = """
    SELECT u.session_id,
           COALESCE(NULLIF(s.title,''), NULLIF(s.display_name,''),
                    substr(u.session_id,1,18)),
           SUM(u.estimated_cost_usd), SUM(u.input_tokens), SUM(u.output_tokens),
           SUM(u.cache_read_tokens), SUM(u.cache_write_tokens),
           SUM(u.api_call_count)
    FROM session_model_usage u
    LEFT JOIN sessions s ON s.id = u.session_id
    WHERE u.last_seen >= {grenze}
    GROUP BY u.session_id
"""

PRUEF_MODELLE = """
    SELECT u.model, SUM(u.estimated_cost_usd), SUM(u.api_call_count),
           COUNT(DISTINCT u.session_id)
    FROM session_model_usage u
    WHERE u.last_seen >= {grenze}
    GROUP BY u.model
    HAVING SUM(u.estimated_cost_usd) > 0
"""

PRUEF_TAGE = """
    SELECT date(u.last_seen,'unixepoch','localtime'), SUM(u.estimated_cost_usd)
    FROM session_model_usage u
    WHERE u.last_seen >= 0
    GROUP BY 1 ORDER BY 1
"""


def html_daten_lesen(pfad: Path) -> dict:
    """Das Daten-JSON aus der fertigen HTML-Datei zurueckholen."""
    text = pfad.read_text(encoding="utf-8")
    i = text.index(MARKER_ANFANG) + len(MARKER_ANFANG)
    j = text.index(MARKER_ENDE, i)
    roh = text[i:j].strip().rstrip(";").strip()
    return json.loads(roh.replace("<\\/", "</"))


def pruefen(con: sqlite3.Connection, pfad: Path, kurs: float) -> tuple[int, int]:
    """Summen aus der HTML-Datei gegen direkte SQL-Abfragen stellen.

    Laeuft auf DERSELBEN Lesetransaktion wie der Aufbau - die Gegenprobe
    vergleicht also exakt denselben Datenstand, nicht einen spaeteren.
    Rueckgabe: (geprueft, fehler).
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

    print("  Gegenprobe gegen direkte SQL-Abfragen (gleicher Datenstand):")
    print(f"  {'Zeitraum':<8} {'Chats':>6} | {'USD (HTML)':>12} {'USD (SQL)':>12} | "
          f"{'EUR (HTML)':>12} {'EUR (SQL)':>12} | {'Calls HTML/SQL':>16} | Status")

    for schluessel, label, ausdruck, _f in ZEITRAEUME:
        p = daten["perioden"][schluessel]
        s = p["summe"]
        usd, ti, to, tc, tw, calls, anzahl = con.execute(
            PRUEF_SUMME.format(grenze=ausdruck)).fetchone()
        usd, ti, to, tc, tw, calls = usd or 0, ti or 0, to or 0, tc or 0, tw or 0, calls or 0
        anzahl = anzahl or 0

        schritt = [
            gleich(f"{schluessel}.usd", s["usd"], round(usd, 6)),
            gleich(f"{schluessel}.input", s["in"], ti),
            gleich(f"{schluessel}.output", s["out"], to),
            gleich(f"{schluessel}.cache_read", s["cread"], tc),
            gleich(f"{schluessel}.cache_write", s["cwrite"], tw),
            gleich(f"{schluessel}.calls", s["calls"], calls),
            gleich(f"{schluessel}.chats_gesamt", s["anzahl"], anzahl),
            gleich(f"{schluessel}.chats_mit_kosten", s["chats"], len(p["chats"])),
        ]

        # Jede einzelne Chat-Zeile gegen die Rohabfrage.
        roh = {}
        for (sid, titel, u, i2, o2, c2, w2, ca) in con.execute(PRUEF_CHATS.format(grenze=ausdruck)):
            roh[sid] = (titel or "", round(u or 0, 6), i2 or 0, o2 or 0, c2 or 0, w2 or 0, ca or 0)
        html_ids = {c["id"] for c in p["chats"]}
        sql_ids = {sid for sid, v in roh.items() if v[1] > 0}
        schritt.append(gleich(f"{schluessel}.chatmenge", sorted(html_ids), sorted(sql_ids)))
        for c in p["chats"]:
            v = roh.get(c["id"], ("", 0, 0, 0, 0, 0, 0))
            schritt.append(gleich(f"{schluessel}.chat[{c['id'][:20]}].titel", c["titel"], v[0]))
            schritt.append(gleich(f"{schluessel}.chat[{c['id'][:20]}].usd", c["usd"], v[1]))
            schritt.append(gleich(f"{schluessel}.chat[{c['id'][:20]}].in", c["in"], v[2]))
            schritt.append(gleich(f"{schluessel}.chat[{c['id'][:20]}].out", c["out"], v[3]))
            schritt.append(gleich(f"{schluessel}.chat[{c['id'][:20]}].cread", c["cread"], v[4]))
            schritt.append(gleich(f"{schluessel}.chat[{c['id'][:20]}].calls", c["calls"], v[6]))
        # Kontrolle: Summe der ANGEZEIGTEN Chat-Zeilen gegen die Rohsumme.
        # Beide Seiten sind auf 6 Stellen gerundet, es bleibt nur der
        # Rundungsrest - der muss unter einem Hunderttausendstel USD liegen.
        rest = abs(round(sum(c["usd"] for c in p["chats"]), 6) - round(usd, 6))
        max_rest = max(max_rest, rest)
        geprueft += 1
        if rest > 1e-5:
            fehler += 1
            print(f"  ABWEICHUNG {schluessel}.summe_der_zeilen: Rest {rest}")

        # Modelle
        sql_m = {m: (round(u or 0, 6), calls or 0, ch or 0)
                 for m, u, calls, ch in con.execute(PRUEF_MODELLE.format(grenze=ausdruck))}
        html_m = {m["modell"]: (m["usd"], m["calls"], m["chats"]) for m in p["modelle"]}
        schritt.append(gleich(f"{schluessel}.modelle", html_m, sql_m))

        # Verlaufstage: jeder im HTML gezeigte Tag muss roh stimmen.
        sql_t = dict(con.execute(PRUEF_TAGE))
        for t in p["verlauf"]:
            schritt.append(gleich(f"{schluessel}.tag[{t['tag']}]", t["usd"],
                                  round(sql_t.get(t["tag"], 0) or 0, 6)))

        ok = all(schritt)
        print(f"  {'OK  ' if ok else 'FEHL'}{schluessel:<8} {s['chats']:>6} | "
              f"{s['usd']:>12.6f} {round(usd, 6):>12.6f} | "
              f"{s['usd'] * kurs:>12.6f} {round(usd * kurs, 6):>12.6f} | "
              f"{s['calls']:>7} / {calls:<7} | "
              f"{len(schritt)} Einzelwerte, {sum(schritt)} stimmen")

    # Verlaufsmenge komplett
    sql_t = dict(con.execute(PRUEF_TAGE))
    html_t = {t["tag"]: t["usd"] for t in daten["perioden"]["alles"]["verlauf"]}
    gleich("verlauf.tagesmenge", sorted(html_t), sorted(sql_t))
    for tag, wert in html_t.items():
        gleich(f"verlauf[{tag}]", wert, round(sql_t.get(tag, 0) or 0, 6))

    # Gebuehrenmodell: die drei echten Kaufdialoge, jeder Posten auf Cent gerundet.
    for gut, s_erw, u_erw, g_erw in ((17.00, 0.94, 3.41, 21.35),
                                     (20.00, 1.10, 4.01, 25.11),
                                     (200.00, 11.00, 40.09, 251.09)):
        service, ust, cash = kauf_rechnen(gut)
        gleich(f"cash_probe[${gut:.2f}].service", service, s_erw)
        gleich(f"cash_probe[${gut:.2f}].ust", ust, u_erw)
        gleich(f"cash_probe[${gut:.2f}].cash", round(cash, 2), g_erw)
    # Unter $14,55 greift die Mindestgebuehr - dann ist der Aufschlag hoeher.
    gleich("cash_probe.break_even", round(BREAK_EVEN, 2), 14.55)

    print(f"  Rundungsrest (Summe der Chat-Zeilen vs. Rohsumme): max {max_rest:.9f} USD "
          f"(Toleranz 0.00001 USD)")
    print(f"  Ergebnis: {geprueft} Einzelvergleiche, {fehler} Abweichungen")
    return geprueft, fehler


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
    }
    fehler = 0
    print("  Selbststaendigkeit:")
    for name, anzahl in verbote.items():
        print(f"    {'OK  ' if anzahl == 0 else 'FEHL'}{name:<24} {anzahl} Treffer")
        fehler += 0 if anzahl == 0 else 1
    print(f"    Script-Bloecke: {text.count('<script')} (inline: {text.count('<script src') == 0})")
    return fehler


# --------------------------------------------------------------------------

def pruefsummen_zeigen(daten: dict) -> None:
    for k in daten["reihenfolge"]:
        p = daten["perioden"][k]
        s = p["summe"]
        print(f"[pruefsumme] {k:<6} chats={s['chats']:<4} von_gesamt={s['anzahl']:<4} "
              f"usd={s['usd']:.6f} eur={s['usd'] * daten['kurs']:.6f} "
              f"cash_eur={s['usd'] * daten['kurs'] * daten['aufschlag']:.6f} "
              f"in={s['in']} out={s['out']} cache_read={s['cread']} cache_write={s['cwrite']} "
              f"calls={s['calls']}")


def main() -> int:
    a = argparse.ArgumentParser(
        description="Kosten-Dashboard fuer alle Hermes-Chats als eigenstaendige HTML-Datei")
    a.add_argument("--kein-netz", action="store_true", help="Kurs-API ueberspringen")
    a.add_argument("--kurs", type=float, help="Wechselkurs EUR je USD erzwingen")
    a.add_argument("--json", action="store_true", help="eingebettete Rohdaten ausgeben")
    a.add_argument("--pruefsummen", action="store_true", help="nur die Kontrollsummen ausgeben")
    a.add_argument("--kein-pruefen", action="store_true",
                   help="Gegenprobe gegen SQL ueberspringen")
    a.add_argument("--ausgabe", default=str(AUSGABE), help="Zieldatei")
    args = a.parse_args()

    kurs, quelle = wechselkurs(args.kein_netz, args.kurs)
    ziel = Path(args.ausgabe)

    con = verbinden()
    try:
        daten = daten_sammeln(con, kurs)
        daten["kurs_quelle"] = quelle

        if args.pruefsummen:
            pruefsummen_zeigen(daten)
            return 0

        if args.json:
            print(json.dumps(daten, indent=2, ensure_ascii=False))
            return 0

        ziel.write_text(html_bauen(daten), encoding="utf-8")
        groesse = ziel.stat().st_size
        gesamt = daten["perioden"]["alles"]["summe"]

        print(f"Dashboard geschrieben: {ziel}")
        print(f"  Groesse:            {groesse:,} Bytes".replace(",", "."))
        print(f"  Wechselkurs:        1 USD = {kurs:.4f} EUR  [{quelle}]")
        print(f"  Aufschlag:          {AUFSCHLAG:.5f} (+{(AUFSCHLAG - 1) * 100:.1f} %)")
        print(f"  Zeitraeume:         {', '.join(daten['reihenfolge'])}")
        print(f"  Chats (alles):      {gesamt['chats']}")
        print(f"  API-Kosten (alles): {gesamt['usd']:.2f} USD = {gesamt['usd'] * kurs:.2f} EUR")
        print(f"  Cash (alles):       {gesamt['usd'] * kurs * AUFSCHLAG:.2f} EUR")
        pruefsummen_zeigen(daten)

        if args.kein_pruefen:
            print("\nPRUEFUNG: uebersprungen (--kein-pruefen)")
            return 0

        print("\nPRUEFUNG")
        _, fehler = pruefen(con, ziel, kurs)
        fehler += selbststaendigkeit_pruefen(ziel)
        if fehler:
            print(f"\nPRUEFUNG: FEHLGESCHLAGEN - {fehler} Abweichungen")
            return 1
        print("\nPRUEFUNG: OK - HTML-Summen == SQL-Summen, keine externen Ressourcen")
        return 0
    finally:
        try:
            con.rollback()      # Lesetransaktion sauber beenden
        except sqlite3.Error:
            pass
        con.close()


if __name__ == "__main__":
    sys.exit(main())
