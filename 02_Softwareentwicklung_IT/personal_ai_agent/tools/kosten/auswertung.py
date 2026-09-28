"""Kostenauswertung: OpenRouter + lokale Hermes-Sitzungsdatenbank.

NUR aggregierte Zahlen. Keine Nachrichtentexte, keine Sitzungstitel, keine
Namen - die Sitzungsdatenbank wird ausschliesslich ueber Zahlen-Spalten
ausgelesen, und gedruckt werden nur Summen.

Schluessel werden zur Laufzeit aus backend/.env gelesen und nie ausgegeben.

Aufruf:  python tools/kosten/auswertung.py [--ausgabe PFAD]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

HIER = Path(__file__).resolve().parent
REPO = HIER.parents[1]
ENV = REPO / "backend" / ".env"
BUS = REPO.parents[1] / ".hermes" / "bus"
URLAUB_VON = date(2026, 8, 30)
URLAUB_BIS = date(2026, 9, 13)
HEUTE = date(2026, 9, 28)


def schluessel(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    if ENV.is_file():
        for zeile in ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
            if zeile.startswith(name + "="):
                return zeile.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def hole(pfad: str, key: str) -> dict:
    req = urllib.request.Request(f"https://openrouter.ai/api/v1{pfad}",
                                 headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=45) as antwort:
            return json.loads(antwort.read().decode("utf-8"))
    except urllib.error.HTTPError as fehler:
        return {"_fehler": f"HTTP {fehler.code}: {fehler.read().decode('utf-8', 'ignore')[:180]}"}
    except Exception as fehler:
        return {"_fehler": f"{type(fehler).__name__}: {fehler}"}


def activity_zeilen(daten: dict) -> list[dict]:
    roh = daten.get("data") if isinstance(daten, dict) else None
    if not isinstance(roh, list):
        return []
    aus = []
    for e in roh:
        if not isinstance(e, dict):
            continue
        aus.append({
            "datum": str(e.get("date") or "")[:10],
            "modell": str(e.get("model") or "?"),
            "usage": float(e.get("usage") or 0.0),
            "requests": int(e.get("requests") or 0),
            "prompt": int(e.get("prompt_tokens") or 0),
            "completion": int(e.get("completion_tokens") or 0),
        })
    return aus


KANDIDATEN = ("started_at", "created_at", "updated_at", "timestamp")
MODELLE = ("model", "model_name", "model_id")
QUELLEN = ("source", "origin", "channel", "client")
EIN = ("input_tokens", "prompt_tokens", "tokens_in")
AUS = ("output_tokens", "completion_tokens", "tokens_out")
KOSTEN = ("estimated_cost", "cost", "cost_usd", "total_cost")


def db_dateien() -> list[Path]:
    gefunden: list[Path] = []
    for basis in (Path(os.environ.get("LOCALAPPDATA", "")) / "hermes", Path.home() / ".hermes"):
        if basis.is_dir():
            for muster in ("*.db", "*.sqlite", "*.sqlite3", "*/*.db", "*/*/*.db"):
                gefunden.extend(p for p in basis.glob(muster) if p.is_file())
    return sorted(set(gefunden))


def spalte(conn: sqlite3.Connection, tabelle: str, namen: tuple[str, ...]) -> str | None:
    try:
        felder = {r[1] for r in conn.execute(f"PRAGMA table_info({tabelle})")}
    except sqlite3.Error:
        return None
    for n in namen:
        if n in felder:
            return n
    return None


def sitzungs_summen() -> list[dict]:
    aus: list[dict] = []
    for datei in db_dateien():
        try:
            conn = sqlite3.connect(f"file:{datei}?mode=ro", uri=True)
        except sqlite3.Error:
            continue
        try:
            tabellen = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")]
            for t in tabellen:
                zeit = spalte(conn, t, KANDIDATEN)
                if not zeit:
                    continue
                ein = spalte(conn, t, EIN)
                ausg = spalte(conn, t, AUS)
                modell = spalte(conn, t, MODELLE)
                quelle = spalte(conn, t, QUELLEN)
                kosten = spalte(conn, t, KOSTEN)
                if not (ein or ausg or kosten):
                    continue
                felder = [f"{zeit} AS zeit"]
                for feld, name in ((modell, "modell"), (quelle, "quelle"),
                                   (ein, "ein"), (ausg, "aus"), (kosten, "kosten")):
                    if feld:
                        agg = "MIN" if name == "modell" else "SUM"
                        felder.append(f"{agg}({feld}) AS {name}")
                felder.append("COUNT(*) AS anzahl")
                try:
                    for z in conn.execute(
                            f"SELECT {', '.join(felder)} FROM {t} GROUP BY {zeit}"):
                        eintrag = {"datei": datei.name, "tabelle": t, "zeit": z[0]}
                        namen = ["zeit"]
                        for feld, name in ((modell, "modell"), (quelle, "quelle"),
                                           (ein, "ein"), (ausg, "aus"), (kosten, "kosten")):
                            if feld:
                                namen.append(name)
                        namen.append("anzahl")
                        for name, wert in zip(namen[1:], z[1:]):
                            eintrag[name] = wert
                        aus.append(eintrag)
                except sqlite3.Error:
                    continue
        finally:
            conn.close()
    return aus


def woche(datum: str) -> str:
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            d = datetime.strptime(str(datum)[:19], fmt).date()
            return f"{d.isocalendar()[0]}-KW{d.isocalendar()[1]:02d}"
        except (ValueError, TypeError):
            continue
    return "?"


def im_urlaub(tag: str) -> bool:
    try:
        d = datetime.strptime(tag, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return False
    return URLAUB_VON <= d <= URLAUB_BIS


def bericht() -> str:
    nutz = schluessel("OPENROUTER_API_KEY")
    mgmt = schluessel("OPENROUTER_MANAGEMENT_KEY")
    z: list[str] = ["# Kostenauswertung — aggregierte Zahlen", "",
                    f"Erstellt: {HEUTE.isoformat()} (Hermes) · Zeitraum: letzte ~3 Monate", ""]
    z += ["## 1) OpenRouter-Guthaben", ""]
    if nutz:
        c = hole("/credits", nutz)
        d = c.get("data", c)
        if "_fehler" in c:
            z.append(f"- Abfrage: {c['_fehler']}")
        else:
            z.append(f"- Gesamt aufgeladen: **{d.get('total_credits', '?')} $**")
            z.append(f"- Verbraucht: **{d.get('total_usage', '?')} $**")
            try:
                rest = float(d.get("total_credits", 0)) - float(d.get("total_usage", 0))
                z.append(f"- Rechnerisch übrig: **{rest:.4f} $**")
            except (TypeError, ValueError):
                pass
    else:
        z.append("- kein OPENROUTER_API_KEY gefunden")
    z += ["", "## 2) OpenRouter-Aktivität (letzte 30 Tage)", ""]
    if mgmt:
        akt = hole("/activity", mgmt)
        quelle = "Management-Key"
    elif nutz:
        akt = hole("/activity", nutz)
        quelle = "normaler Key"
    else:
        akt, quelle = {"_fehler": "kein Schlüssel"}, "-"
    rows = activity_zeilen(akt)
    if not rows:
        z.append(f"- keine Aktivitätsdaten ({quelle}): {akt.get('_fehler', 'leere Antwort')}")
    else:
        pro_modell: dict[str, dict] = defaultdict(lambda: {"usage": 0.0, "req": 0, "prompt": 0, "completion": 0})
        pro_tag: dict[str, float] = defaultdict(float)
        for r in rows:
            m = pro_modell[r["modell"]]
            m["usage"] += r["usage"]
            m["req"] += r["requests"]
            m["prompt"] += r["prompt"]
            m["completion"] += r["completion"]
            pro_tag[r["datum"]] += r["usage"]
        gesamt = sum(m["usage"] for m in pro_modell.values())
        z.append(f"- Summe: **{gesamt:.4f} $** über {sum(m['req'] for m in pro_modell.values())} Anfragen (Quelle: {quelle})")
        urlaub = sum(k for t, k in pro_tag.items() if im_urlaub(t))
        z.append(f"- davon im Urlaubsfenster {URLAUB_VON:%d.%m.}–{URLAUB_BIS:%d.%m.%Y}: **{urlaub:.4f} $**")
        z += ["", "| Modell | Kosten ($) | Anfragen | Prompt-Tokens | Completion-Tokens |", "|---|---|---|---|---|"]
        for modell, m in sorted(pro_modell.items(), key=lambda x: -x[1]["usage"]):
            z.append(f"| `{modell}` | {m['usage']:.4f} | {m['req']} | {m['prompt']:,} | {m['completion']:,} |")
        z += ["", "| Tag | Kosten ($) | Urlaub |", "|---|---|---|"]
        for tag, kosten in sorted(pro_tag.items()):
            z.append(f"| {tag} | {kosten:.4f} | {'ja' if im_urlaub(tag) else ''} |")
    z += ["", "## 3) Lokale Hermes-Sitzungsdatenbank (nur Zahlen)", ""]
    summen = sitzungs_summen()
    if not summen:
        z.append("- keine passende Tabelle gefunden")
    else:
        pro_woche: dict[str, dict] = defaultdict(lambda: {"kosten": 0.0, "anzahl": 0, "ein": 0, "aus": 0})
        for s in summen:
            k = woche(s["zeit"])
            pro_woche[k]["kosten"] += float(s.get("kosten") or 0)
            pro_woche[k]["ein"] += int(s.get("ein") or 0)
            pro_woche[k]["aus"] += int(s.get("aus") or 0)
            pro_woche[k]["anzahl"] += int(s.get("anzahl") or 0)
        z += ["| Woche | Einträge | Kosten ($) | Tokens ein | Tokens aus |", "|---|---|---|---|---|"]
        for w, d in sorted(pro_woche.items()):
            z.append(f"| {w} | {d['anzahl']} | {d['kosten']:.4f} | {d['ein']:,} | {d['aus']:,} |")
        z.append("")
        z.append(f"- gelesen aus: {', '.join(sorted({s['datei'] for s in summen}))}")
        z.append(f"- Tabellen: {', '.join(sorted({s['tabelle'] for s in summen}))}")
    z += ["", "## 4) Kosten des Coding-Chats im Backend", "",
          "- **nicht getrennt verfügbar**: das Backend führt keine eigene Kostenspalte; "
          "diese Kosten stecken in der Gesamtaktivität (Punkt 2).", "",
          "## 5) Einordnung", "",
          f"- Urlaubsfenster (Handy-Coding) getrennt ausgewiesen: **{URLAUB_VON:%d.%m.} bis {URLAUB_BIS:%d.%m.%Y}**",
          "- Quellen: OpenRouter-API (Schlüssel nur zur Laufzeit, nie ausgegeben) und lokale "
          "Hermes-Sitzungsdatenbank (ausschließlich Zahlen-Spalten).",
          "- Keine Nachrichtentexte, keine Titel, keine Namen, keine Kontaktdaten."]
    return "\n".join(z) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kostenauswertung (nur Zahlen)")
    ap.add_argument("--ausgabe", default=str(BUS / "auswertung-kosten.md"))
    a = ap.parse_args(argv)
    text = bericht()
    ziel = Path(a.ausgabe)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(text, encoding="utf-8")
    print(f"geschrieben: {ziel} ({len(text)} Zeichen)")
    for zeile in text.splitlines():
        if zeile.startswith(("- Gesamt aufgeladen", "- Verbraucht", "- Rechnerisch",
                             "- Summe:", "- davon im Urlaub")):
            print("  " + zeile[2:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())