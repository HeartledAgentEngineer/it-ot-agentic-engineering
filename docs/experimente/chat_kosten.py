#!/usr/bin/env python
"""Kosten pro Chat aus der Hermes-Datenbank - rueckwirkend, mit Zeitraeumen.

ANLASS: Die Statusleiste zeigt fuer die Session nur wenige Cent, obwohl der Chat
real mehrere Euro gekostet hat. Ursache: die Leiste liest den LIVE-Zaehler
(focusedUsage), der beim App-Start bei Null beginnt. Die Datenbank kennt die
gesamte Lebenszeit des Chats - dieses Skript liest sie direkt.

WICHTIG (die Falle): `last_seen` in session_model_usage ist ein UNIX-Zeitstempel
als Fliesskommazahl (z. B. 1790344497.394741), KEIN Datumsstring.
  falsch:  date(last_seen) = date('now')          -> immer 0 Zeilen
  richtig: last_seen >= strftime('%s','now',...)  -> echte Zahlen

Benutzung:
    python chat_kosten.py                      # alle Zeitraeume, Top 10
    python chat_kosten.py --zeitraum heute     # nur heute
    python chat_kosten.py --zeitraum alles     # seit immer
    python chat_kosten.py --chat "personal"    # ein Chat, Zeitleiste
    python chat_kosten.py --json               # Rohdaten
    python chat_kosten.py --csv                # CSV fuer Tabellenkalkulation
"""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
from pathlib import Path

DB = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "state.db"
KURS_EUR = 0.8787          # EUR je USD; bei Bedarf hier anpassen

# Zeitfenster als SQL-Ausdruck auf den Epoch-Zeitstempel
ZEITRAEUME = {
    "heute":     "strftime('%s','now','start of day','localtime')",
    "woche":     "strftime('%s','now','weekday 1','-7 days','start of day','localtime')",
    "7tage":     "strftime('%s','now','-7 days')",
    "monat":     "strftime('%s','now','start of month','localtime')",
    "alles":     "0",
}


def verbinden() -> sqlite3.Connection:
    if not DB.is_file():
        sys.exit(f"Datenbank nicht gefunden: {DB}")
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def chats(con: sqlite3.Connection, grenze: str, limit: int | None = None) -> list[tuple]:
    """Alle Chats mit Kosten im Zeitraum, absteigend sortiert."""
    q = f"""
        SELECT u.session_id,
               COALESCE(NULLIF(s.title,''), NULLIF(s.display_name,''),
                        substr(u.session_id,1,18)) AS titel,
               SUM(u.estimated_cost_usd)  AS kosten_usd,
               SUM(u.input_tokens)        AS tok_in,
               SUM(u.output_tokens)       AS tok_out,
               SUM(u.cache_read_tokens)   AS tok_cache,
               SUM(u.api_call_count)      AS calls,
               MIN(u.last_seen)           AS von,
               MAX(u.last_seen)           AS bis
        FROM session_model_usage u
        LEFT JOIN sessions s ON s.id = u.session_id
        WHERE u.last_seen >= {grenze}
        GROUP BY u.session_id
        HAVING kosten_usd > 0
        ORDER BY kosten_usd DESC
    """
    if limit:
        q += f" LIMIT {limit}"
    return con.execute(q).fetchall()


def tag(epoch: float | None) -> str:
    if not epoch:
        return "—"
    import datetime
    return datetime.datetime.fromtimestamp(epoch).strftime("%d.%m. %H:%M")


def zeile(rang: int, titel: str, kosten: float, i: int, o: int, c: int,
          calls: int, breite: int) -> str:
    ges = i + o + c
    cq = c / (i + c) * 100 if (i + c) else 0
    return (f"  {rang:>2}. {kosten * KURS_EUR:>7.2f} €  {kosten:>7.2f} $  "
            f"CQ {cq:>3.0f} %  "
            f"in {i:>11,}  out {o:>9,}  cache {c:>12,}  "
            f"{ges:>13,} Tok  {calls:>5} Calls  {titel[:breite]}")


def bericht(con: sqlite3.Connection, zeitraum: str, limit: int, breite: int) -> None:
    grenze = ZEITRAEUME[zeitraum]
    rows = chats(con, grenze, limit)
    if not rows:
        print(f"  [{zeitraum}] keine Daten")
        return
    summe = sum(r[2] or 0 for r in rows)
    s_in = sum(r[3] or 0 for r in rows)
    s_out = sum(r[4] or 0 for r in rows)
    s_cache = sum(r[5] or 0 for r in rows)
    s_calls = sum(r[6] or 0 for r in rows)
    print(f"\n═══ {zeitraum.upper()} — Top {len(rows)} der {len(chats(con, grenze))} Chats ═══")
    print(f"  {'Kosten':>9}  {'USD':>8}  {'Quote':>8}  "
          f"{'Input-Token':>14} {'Output-Token':>13} {'Cache-Token':>15}  "
          f"{'Gesamt':>15}  {'Calls':>6}  Chat")
    print("  " + "─" * (breite + 110))
    for n, (sid, titel, kosten, i, o, c, calls, _v, _b) in enumerate(rows, 1):
        print(zeile(n, titel or "?", kosten or 0, i or 0, o or 0, c or 0, calls or 0, breite))
    print("  " + "─" * (breite + 110))
    cq_ges = s_cache / (s_in + s_cache) * 100 if (s_in + s_cache) else 0
    print(f"  SUM  {summe * KURS_EUR:>7.2f} €  {summe:>7.2f} $  "
          f"CQ {cq_ges:>3.0f} %  "
          f"in {s_in:>11,}  out {s_out:>9,}  cache {s_cache:>12,}  "
          f"{s_in + s_out + s_cache:>13,} Tok  {s_calls:>5} Calls")
    print(f"  → Cash mit Aufschlag (+25,5 %): {summe * KURS_EUR * 1.25545:.2f} €")


def chat_detail(con: sqlite3.Connection, muster: str, breite: int) -> None:
    """Zeitleiste eines einzelnen Chats ueber alle Tage."""
    q = """
        SELECT u.session_id,
               COALESCE(NULLIF(s.title,''), NULLIF(s.display_name,''),
                        substr(u.session_id,1,18)),
               u.model, u.estimated_cost_usd,
               u.input_tokens, u.output_tokens, u.cache_read_tokens,
               u.api_call_count, u.first_seen, u.last_seen
        FROM session_model_usage u
        LEFT JOIN sessions s ON s.id = u.session_id
        WHERE u.session_id LIKE ? OR s.title LIKE ? OR s.display_name LIKE ?
        ORDER BY u.last_seen
    """
    like = f"%{muster}%"
    rows = con.execute(q, (like, like, like)).fetchall()
    if not rows:
        print(f"  Kein Chat zu '{muster}' gefunden.")
        return
    sid = rows[0][0]
    titel = rows[0][1]
    print(f"\n═══ Chat: {titel}  ({sid}) ═══")
    print(f"  {'Zeit':>14}  {'Kosten':>9}  {'USD':>8}  {'Input':>12} {'Output':>10} {'Cache':>13}  {'Calls':>6}  Modell")
    print("  " + "─" * (breite + 96))
    tot = 0.0
    t_in = t_out = t_cache = t_calls = 0
    for (_s, _t, modell, kosten, i, o, c, calls, _f, last) in rows:
        kosten = kosten or 0
        i, o, c, calls = i or 0, o or 0, c or 0, calls or 0
        tot += kosten
        t_in += i; t_out += o; t_cache += c; t_calls += calls
        print(f"  {tag(last):>14}  {kosten * KURS_EUR:>7.2f} €  {kosten:>7.2f} $  "
              f"{i:>12,} {o:>10,} {c:>13,}  {calls:>6}  {(modell or '?')[:24]}")
    cq = t_cache / (t_in + t_cache) * 100 if (t_in + t_cache) else 0
    print("  " + "─" * (breite + 96))
    print(f"  {'SUMME':>14}  {tot * KURS_EUR:>7.2f} €  {tot:>7.2f} $  "
          f"{t_in:>12,} {t_out:>10,} {t_cache:>13,}  {t_calls:>6}  CQ {cq:.1f} %")
    print(f"  → Cash mit Aufschlag (+25,5 %): {tot * KURS_EUR * 1.25545:.2f} €")


def als_csv(con: sqlite3.Connection, zeitraum: str) -> None:
    grenze = ZEITRAEUME[zeitraum]
    w = csv.writer(sys.stdout)
    w.writerow(["session_id", "titel", "kosten_usd", "kosten_eur",
                "input_tokens", "output_tokens", "cache_tokens",
                "cache_quote_pct", "api_calls", "von", "bis"])
    for sid, titel, kosten, i, o, c, calls, von, bis in chats(con, grenze):
        i, o, c = i or 0, o or 0, c or 0
        neu = (c / (i + c) * 100) if (i + c) else 0
        w.writerow([sid, titel, f"{kosten or 0:.6f}", f"{(kosten or 0) * KURS_EUR:.6f}",
                    i, o, c, f"{neu:.1f}", calls, tag(von), tag(bis)])


def als_json(con: sqlite3.Connection, zeitraum: str) -> None:
    import json
    grenze = ZEITRAEUME[zeitraum]
    out = []
    for sid, titel, kosten, i, o, c, calls, von, bis in chats(con, grenze):
        i, o, c = i or 0, o or 0, c or 0
        out.append({
            "session_id": sid, "titel": titel,
            "kosten_usd": round(kosten or 0, 6),
            "kosten_eur": round((kosten or 0) * KURS_EUR, 6),
            "input_tokens": i, "output_tokens": o, "cache_tokens": c,
            "cache_quote_pct": round((c / (i + c) * 100) if (i + c) else 0, 1),
            "api_calls": calls,
            "von": tag(von), "bis": tag(bis),
        })
    print(json.dumps(out, indent=2, ensure_ascii=False))


def main() -> int:
    p = argparse.ArgumentParser(description="Kosten pro Chat aus der Hermes-Datenbank")
    p.add_argument("--zeitraum", default="heute",
                   choices=list(ZEITRAEUME) + ["alle"],
                   help="heute | woche | 7tage | monat | alles")
    p.add_argument("--chat", help="Teil des Chat-Titels oder der Session-ID")
    p.add_argument("--limit", type=int, default=10, help="wie viele Chats (0 = alle)")
    p.add_argument("--breite", type=int, default=44, help="Titelbreite")
    p.add_argument("--json", action="store_true")
    p.add_argument("--csv", action="store_true")
    a = p.parse_args()

    con = verbinden()
    try:
        if a.json:
            als_json(con, a.zeitraum)
        elif a.csv:
            als_csv(con, a.zeitraum)
        elif a.chat:
            chat_detail(con, a.chat, a.breite)
        else:
            limit = a.limit if a.limit > 0 else None
            bericht(con, a.zeitraum, limit or 10**9, a.breite)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
