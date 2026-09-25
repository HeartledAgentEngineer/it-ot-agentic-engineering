#!/usr/bin/env python
"""Live-Zahlen fuer diesen Chat - als JSON und als fertige HTML-Ansicht.

WARUM: Die Statusleiste in der App braucht ein Python-Backend, das nur beim
App-Start geladen wird (kein Reload) - jede Aenderung erzwingt einen Neustart.
Dieses Skript liefert dieselben Zahlen OHNE Neustart.

AUFTEILUNG IST EXAKT: Input/Output/Cache kommen aus dem Plugin-Backend
(plugins/context-tank/dashboard/plugin_api.py), das als Modul geladen wird -
keine zweite, abweichende Rechnung. Ist es nicht ladbar, wird genaehert und das
im Feld "aufteilung_quelle" ausdruecklich gesagt.

AUFRUF:  python live_zahlen.py [session-id]
Erzeugt: live_zahlen.json  und  live_zahlen.html
"""
import importlib.util
import json
import os
import re
import sqlite3
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

DB = Path(os.path.expanduser("~/AppData/Local/hermes/state.db"))
BACKEND = Path(os.path.expanduser("~/AppData/Local/hermes/plugins/context-tank/dashboard/plugin_api.py"))
ZIEL = Path(__file__).with_name("live_zahlen.json")
KURS_FALLBACK = 0.87696
STANDARD_SESSION = "20260828_015944_352e08"
ZEITRAEUME = [
    ("heute", "Heute", "ab 00:00 heute (lokale Zeit)"),
    ("woche", "Woche", "ab Montag 00:00 dieser Woche (ISO-Kalenderwoche)"),
    ("letzte_woche", "Letzte Woche", "Montag bis Sonntag der Vorwoche"),
    ("letzte_7_tage", "Letzte 7 Tage", "rollierend: jetzt minus 7 x 24 Stunden"),
    ("monat", "Monat", "ab dem 1. des laufenden Monats"),
    ("letzter_monat", "Letzter Monat", "1. bis letzter Tag des Vormonats"),
    ("alles", "Alles", "seit der ersten Aufzeichnung"),
]


def backend_laden():
    """Plugin-Backend als Modul laden (liefert die exakte Aufteilung)."""
    if not BACKEND.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("ct_backend", BACKEND)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["ct_backend"] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception as exc:  # noqa: BLE001
        print(f"Hinweis: Backend nicht ladbar ({type(exc).__name__}: {exc})", file=sys.stderr)
        return None


def kurs_holen():
    try:
        with urllib.request.urlopen(
            "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml", timeout=8
        ) as r:
            text = r.read().decode("utf-8", "replace")
        m = re.search(r'currency="USD"[^>]*rate="([0-9.]+)"', text)
        if m:
            return 1.0 / float(m.group(1)), "EZB (live)"
    except Exception:  # noqa: BLE001
        pass
    return KURS_FALLBACK, "letzter bekannter Stand"


def fenster(kennung):
    jetzt = datetime.now()
    mitternacht = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
    if kennung == "heute":
        return mitternacht.timestamp(), None
    if kennung == "woche":
        return (mitternacht - timedelta(days=mitternacht.weekday())).timestamp(), None
    if kennung == "letzte_woche":
        mo = mitternacht - timedelta(days=mitternacht.weekday() + 7)
        return mo.timestamp(), (mo + timedelta(days=7)).timestamp()
    if kennung == "letzte_7_tage":
        return (jetzt - timedelta(days=7)).timestamp(), None
    if kennung == "monat":
        return mitternacht.replace(day=1).timestamp(), None
    if kennung == "letzter_monat":
        erster = mitternacht.replace(day=1)
        return (erster - timedelta(days=1)).replace(day=1).timestamp(), erster.timestamp()
    return 0.0, None


def cash_kette(nutzung_usd):
    """Nutzung -> Cash. Belegt an drei echten Kaufdialogen (17/20/200 USD)."""
    guthaben = nutzung_usd / 0.945
    service = max(round(guthaben * 0.055, 2), 0.80)
    ust = round((guthaben + service) * 0.19, 2)
    return {"guthaben": guthaben, "service": service, "ust": ust,
            "cash": guthaben + service + ust}


def alle_chats(con, start, ende):
    wo, werte = ["u.last_seen >= ?"], [start]
    if ende is not None:
        wo.append("u.last_seen <= ?")
        werte.append(ende)
    sql = f"""SELECT SUM(u.estimated_cost_usd), SUM(u.api_call_count), SUM(u.input_tokens),
                     SUM(u.output_tokens), SUM(u.cache_read_tokens), COUNT(DISTINCT u.session_id)
              FROM session_model_usage u WHERE {' AND '.join(wo)}"""
    usd, calls, ti, to, tc, n = con.execute(sql, werte).fetchone()
    ti, to, tc = ti or 0, to or 0, tc or 0
    return {"usd": usd or 0.0, "calls": calls or 0, "in_tok": ti, "out_tok": to,
            "cache_tok": tc, "sessions": n or 0,
            "cache_quote": (tc / (ti + tc) * 100) if (ti + tc) else None}


def main():
    sess = sys.argv[1] if len(sys.argv) > 1 else STANDARD_SESSION
    kurs, kurs_quelle = kurs_holen()
    backend = backend_laden()
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    ergebnis = {"erzeugt": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                "kurs": kurs, "kurs_quelle": kurs_quelle, "session": sess,
                "aufteilung_quelle": ("exakt (Plugin-Backend, Modellpreise je Modell)"
                                      if backend else "Naeherung (Backend nicht ladbar)"),
                "perioden": {}, "zeitraeume": []}

    for kennung, label, defi in ZEITRAEUME:
        start, ende = fenster(kennung)
        a = alle_chats(con, start, ende)
        ergebnis["zeitraeume"].append({"id": kennung, "label": label, "definition": defi})

        if backend is not None:
            d = backend.status_session(sess, kennung)
            b = d.get("bucket") or {}
            ch = d.get("chat") or {}
            tot = ch.get("total") or {}
            sub = ch.get("subagents") or {}
            in_usd = b.get("cost_input_usd") or 0.0
            out_usd = b.get("cost_output_usd") or 0.0
            cache_usd = b.get("cost_cache_usd") or 0.0
            eigen_usd = b.get("cost_usd") or (in_usd + out_usd + cache_usd)
            sub_usd = sub.get("cost_usd") or 0.0
            tok = {"in": b.get("input_tokens") or 0, "out": b.get("output_tokens") or 0,
                   "cache": b.get("cache_read_tokens") or 0}
            calls, quote = b.get("requests") or 0, b.get("cache_hit_percent")
            gesamt_usd = tot.get("cost_usd") or (eigen_usd + sub_usd)
        else:
            # Naeherung: Kosten im Verhaeltnis der Tokenmengen verteilen
            wo, werte = ["u.last_seen >= ?"], [start]
            if ende is not None:
                wo.append("u.last_seen <= ?")
                werte.append(ende)
            wo.append("(u.session_id = ? OR u.session_id IN (SELECT id FROM sessions WHERE parent_session_id = ?))")
            werte += [sess, sess]
            usd, calls, ti, to, tc = con.execute(
                f"""SELECT SUM(u.estimated_cost_usd), SUM(u.api_call_count), SUM(u.input_tokens),
                           SUM(u.output_tokens), SUM(u.cache_read_tokens)
                    FROM session_model_usage u WHERE {' AND '.join(wo)}""", werte).fetchone()
            usd, ti, to, tc = usd or 0.0, ti or 0, to or 0, tc or 0
            g = ti + to + tc
            in_usd = usd * ti / g if g else 0.0
            out_usd = usd * to / g if g else 0.0
            cache_usd = usd * tc / g if g else 0.0
            eigen_usd = sub_usd = gesamt_usd = usd
            tok = {"in": ti, "out": to, "cache": tc}
            quote = None

        ergebnis["perioden"][kennung] = {
            "label": label, "definition": defi,
            "chat_in_usd": in_usd, "chat_out_usd": out_usd, "chat_cache_usd": cache_usd,
            "chat_in_eur": in_usd * kurs, "chat_out_eur": out_usd * kurs,
            "chat_cache_eur": cache_usd * kurs,
            "chat_eigen_eur": eigen_usd * kurs, "sub_eur": sub_usd * kurs,
            "chat_gesamt_eur": gesamt_usd * kurs, "chat_gesamt_usd": gesamt_usd,
            "chat_in_tok": tok["in"], "chat_out_tok": tok["out"], "chat_cache_tok": tok["cache"],
            "chat_calls": calls, "chat_quote": quote,
            "alle_eur": a["usd"] * kurs, "alle_usd": a["usd"],
            "alle_in_tok": a["in_tok"], "alle_out_tok": a["out_tok"],
            "alle_cache_tok": a["cache_tok"], "alle_calls": a["calls"],
            "alle_sessions": a["sessions"], "alle_quote": a["cache_quote"],
            "cash": cash_kette(a["usd"]),
        }
    con.close()

    ZIEL.write_text(json.dumps(ergebnis, ensure_ascii=False, indent=1), encoding="utf-8")
    ziel_html = ZIEL.with_suffix(".html")
    ziel_html.write_text(HTML.replace("__DATEN__", json.dumps(ergebnis, ensure_ascii=False)),
                         encoding="utf-8")
    print(f"OK -> {ZIEL}")
    print(f"OK -> {ziel_html}")
    print(f"Aufteilung: {ergebnis['aufteilung_quelle']}")
    for k, v in ergebnis["perioden"].items():
        print(f"  {v['label']:<14} Chat {v['chat_gesamt_eur']:>6.2f} EUR "
              f"(in {v['chat_in_eur']:.2f} + out {v['chat_out_eur']:.2f} + cache {v['chat_cache_eur']:.2f} "
              f"+ Sub {v['sub_eur']:.2f})  alle {v['alle_eur']:>6.2f} EUR  "
              f"Cash {v['cash']['cash'] * kurs:>6.2f} EUR")
    return 0


HTML = """<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8">
<title>Kosten dieses Chats</title>
<style>
 .k { --fg: var(--foreground, #1b1b20); --mut: var(--muted-foreground, #5c5c66);
      --bd: var(--border, rgba(120,120,135,.45)); --pan: var(--card, rgba(120,120,135,.10));
      --acc: var(--accent, #4f6bed); color: var(--fg); font-family: inherit;
      font-size: 12px; line-height: 1.45; }
 @media (prefers-color-scheme: dark) {
   .k { --fg: var(--foreground, #ecedf2); --mut: var(--muted-foreground, #a9a9b6);
        --bd: var(--border, rgba(165,165,180,.40)); --pan: var(--card, rgba(165,165,180,.10)); } }
 .k .sw { display:flex; gap:3px; flex-wrap:wrap; margin-bottom:8px; }
 .k button { font:inherit; font-size:11px; padding:2px 8px; border-radius:4px; cursor:pointer;
             background:transparent; color:var(--mut); border:1px solid var(--bd); }
 .k button[aria-pressed="true"] { background:var(--acc); color:#fff; border-color:var(--acc); font-weight:600; }
 .k table { border-collapse:collapse; font-variant-numeric:tabular-nums; }
 .k td, .k th { padding:1px 10px 1px 0; text-align:right; white-space:nowrap; }
 .k th:first-child, .k td:first-child { text-align:left; }
 .k th { color:var(--mut); font-weight:500; border-bottom:1px solid var(--bd); }
 .k .titel { font-weight:600; margin:10px 0 3px; }
 .k .gross { font-size:16px; font-weight:600; }
 .k .summe { border-top:1px solid var(--bd); font-weight:600; }
 .k .hin { color:var(--mut); font-size:10.5px; margin-top:8px; }
 .k .bar { height:7px; border-radius:3px; background:var(--pan); display:inline-block;
           width:90px; vertical-align:middle; overflow:hidden; }
 .k .bar i { display:block; height:100%; background:var(--acc); }
</style></head><body>
<div class="k" id="wurzel">
  <div class="sw" id="schalter"></div>
  <div id="inhalt"></div>
  <div class="hin" id="hinweis"></div>
</div>
<script>
const D = __DATEN__;
const EUR = n => (n == null ? "–" : n.toLocaleString("de-DE", {minimumFractionDigits:2, maximumFractionDigits:2}) + "\\u00a0\\u20ac");
const TOK = n => (n == null ? "–" : (n/1e6).toLocaleString("de-DE", {maximumFractionDigits:1}) + "\\u00a0M");
const KURZ = n => (n == null ? "–" : n.toLocaleString("de-DE", {maximumFractionDigits:0}));
const Q = n => (n == null ? "–" : n.toFixed(0) + " %");
let aktiv = "heute";
const schalter = document.getElementById("schalter");
Object.keys(D.perioden).forEach(id => {
  const b = document.createElement("button");
  b.textContent = D.perioden[id].label;
  b.title = D.perioden[id].definition;
  b.setAttribute("aria-pressed", id === aktiv ? "true" : "false");
  b.onclick = () => { aktiv = id; malen(); };
  schalter.appendChild(b);
});
function malen() {
  const p = D.perioden[aktiv];
  [...schalter.children].forEach(b => b.setAttribute("aria-pressed",
    b.textContent === p.label ? "true" : "false"));
  const anteil = p.alle_eur > 0 ? Math.min(100, p.chat_gesamt_eur / p.alle_eur * 100) : 0;
  document.getElementById("inhalt").innerHTML = `
   <div class="titel">Dieser Chat \\u2014 ${p.label}</div>
   <div class="gross">${EUR(p.chat_gesamt_eur)}</div>
   <table>
     <tr><th>Kostenart</th><th>Betrag</th><th>Tokens</th></tr>
     <tr><td>Input</td><td>${EUR(p.chat_in_eur)}</td><td>${TOK(p.chat_in_tok)}</td></tr>
     <tr><td>Output</td><td>${EUR(p.chat_out_eur)}</td><td>${TOK(p.chat_out_tok)}</td></tr>
     <tr><td>Cache</td><td>${EUR(p.chat_cache_eur)}</td><td>${TOK(p.chat_cache_tok)}</td></tr>
     <tr class="summe"><td>Summe (in + out + cache)</td><td>${EUR(p.chat_eigen_eur)}</td><td>${KURZ(p.chat_calls)} Anfragen</td></tr>
     <tr><td>+ Subagenten</td><td>${EUR(p.sub_eur)}</td><td>geh\\u00f6ren zu diesem Chat</td></tr>
     <tr class="summe"><td>dieser Chat gesamt</td><td>${EUR(p.chat_gesamt_eur)}</td><td>Cache-Treffer ${Q(p.chat_quote)}</td></tr>
   </table>
   <div class="titel">Alle Chats \\u2014 ${p.label}</div>
   <table>
     <tr><th>Posten</th><th>Betrag</th><th>Mengen</th></tr>
     <tr><td>Nutzung (was die Modelle kosteten)</td><td>${EUR(p.alle_eur)}</td><td>${TOK(p.alle_in_tok)} in \\u00b7 ${TOK(p.alle_out_tok)} out</td></tr>
     <tr><td>+ Servicegeb\\u00fchr (5,5 %, mind. 0,80 USD)</td><td>${EUR(p.cash.service * D.kurs)}</td><td>${KURZ(p.alle_sessions)} Sitzungen</td></tr>
     <tr><td>+ Umsatzsteuer 19 %</td><td>${EUR(p.cash.ust * D.kurs)}</td><td>Cache ${TOK(p.alle_cache_tok)} \\u00b7 Treffer ${Q(p.alle_quote)}</td></tr>
     <tr class="summe"><td>= Cash (was vom Konto geht)</td><td>${EUR(p.cash.cash * D.kurs)}</td><td>${KURZ(p.alle_calls)} Anfragen</td></tr>
   </table>
   <div style="margin-top:7px">Anteil dieses Chats an allen: <span class="bar"><i style="width:${anteil.toFixed(1)}%"></i></span> ${anteil.toFixed(1)} %</div>`;
  document.getElementById("hinweis").textContent =
    `Zeitraum: ${p.definition}. Aufteilung: ${D.aufteilung_quelle}. Kurs 1 USD = ${D.kurs.toFixed(4)} EUR (${D.kurs_quelle}). Stand ${D.erzeugt}.`;
}
malen();
</script></body></html>
"""


if __name__ == "__main__":
    sys.exit(main())
