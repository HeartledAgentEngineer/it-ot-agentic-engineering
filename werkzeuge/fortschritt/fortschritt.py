#!/usr/bin/env python
"""Fortschritt meiner Arbeit — eine Anzeige, die Sebastian jederzeit ansehen kann.

Warum (Sebastian, 10.10.2026, ca. 05:10):
    "Ich wuerde eher eine Live-Zustandsanzeige haben ... ein Balken, der sich
    bewegt, damit ich ungefaehr weiss, wie lange noch ist und wie viel Prozent,
    wie viele Dateien von wie viel abgehakt haben. Ich brauche ein bisschen
    Kontrolle ueber dich, weil sonst manchmal du einfach abreisst und nicht
    anfaengst."

Aufbau (eine Wahrheit, drei Ansichten):
    * ``status.json``  — die Wahrheit. Wird von der Arbeit selbst gepflegt
      (Schritte, Zaehler). Dieses Skript schreibt NUR die Felder, die es
      messen kann, und laesst alles andere unangetastet.
    * ``--terminal``   — Balken fuer die Konsole, ein Aufruf, keine Abhaengigkeit.
    * ``--html``       — schreibt ``.hermes/widgets/fortschritt.html``. Die Seite
      laedt sich selbst alle 5 s neu; ein stiller Minutenjob haelt die Datei
      frisch. Anzeigen mit ``::preview{file=".hermes/widgets/fortschritt.html"}``.
    * ``--zaehle``     — zaehlt bei Papas Fotos nach (pCloud-API): wie viele
      Zielordner schon Inhalt haben und wie viele Dateien es sind. Nichts wird
      dabei geschrieben ausser den Zahlen in ``status.json``.

Aufruf:
    python werkzeuge/fortschritt/fortschritt.py --terminal
    python werkzeuge/fortschritt/fortschritt.py --zaehle --html
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

HIER = Path(__file__).resolve().parent
STATUS = HIER / "status.json"
WIDGET = HIER.parents[1] / ".hermes" / "widgets" / "fortschritt.html"

# backend/.env des Projekts — Fallback-Quelle fuer den pCloud-Schluessel.
ENV_DATEI = HIER.parents[1] / "02_Softwareentwicklung_IT" / "personal_ai_agent" / "backend" / ".env"
STANDARD_HOST = "eapi.pcloud.com"

# Wo Papas Fotos landen (Sebastians Freigabe 10.10.2026).
PCLOUD_ZIEL = "/Bilder & Videos/Papa (Amazon)"
PCLOUD_QUELLE = "/AmazonPhotosvonPapa"


# ── Schluessel (nie ausgeben) ──────────────────────────────────────────────

def _werte_aus_env(pfad: Path) -> Dict[str, str]:
    werte: Dict[str, str] = {}
    if not pfad.exists():
        return werte
    try:
        for zeile in pfad.read_text(encoding="utf-8", errors="replace").splitlines():
            zeile = zeile.strip()
            if not zeile or zeile.startswith("#") or "=" not in zeile:
                continue
            name, wert = zeile.split("=", 1)
            if name.strip() in ("PCLOUD_TOKEN", "PCLOUD_HOST"):
                werte[name.strip()] = wert.strip().strip('"').strip("'")
    except OSError:
        pass
    return werte


def _pcloud(methode: str, **felder: Any) -> Dict[str, Any]:
    """EIN pCloud-Aufruf (nur lesend genutzt). Parameter heisst ``auth``."""
    env = _werte_aus_env(ENV_DATEI)
    token = (os.environ.get("PCLOUD_TOKEN") or env.get("PCLOUD_TOKEN") or "").strip()
    host = (os.environ.get("PCLOUD_HOST") or env.get("PCLOUD_HOST") or STANDARD_HOST).strip()
    host = host.split("://")[-1].strip("/") or STANDARD_HOST
    if not token:
        raise RuntimeError("Kein PCLOUD_TOKEN gefunden (backend/.env).")
    felder["auth"] = token
    url = f"https://{host}/{methode}?" + urllib.parse.urlencode(felder)
    with urllib.request.urlopen(url, timeout=60) as antwort:
        daten = json.loads(antwort.read().decode())
    if daten.get("result") != 0:
        raise RuntimeError(f"pCloud meldet Fehler {daten.get('result')}: {daten.get('error')}")
    return daten


# ── Zaehlen (der einzige Teil, der echte Zahlen holt) ──────────────────────

def zaehle_papas_fotos() -> Dict[str, Any]:
    """Zielordner mit Inhalt + Dateien gesamt. Reine Lesezugriffe."""
    ziel = _pcloud("listfolder", path=PCLOUD_ZIEL)["metadata"]
    unterordner = sorted([c for c in ziel["contents"] if c.get("isfolder")],
                         key=lambda c: c["name"])
    mit_inhalt, dateien, groesse = 0, 0, 0
    for ordner in unterordner:
        k = _pcloud("listfolder", folderid=ordner["folderid"])["metadata"]["contents"]
        kinder = [x for x in k if not x.get("isfolder")]
        if kinder:
            mit_inhalt += 1
            dateien += len(kinder)
            groesse += sum(x.get("size", 0) for x in kinder)
    return {
        "unterordner": len(unterordner),
        "mit_inhalt": mit_inhalt,
        "dateien": dateien,
        "groesse_mb": round(groesse / 1e6, 1),
    }


# ── Anzeigen ───────────────────────────────────────────────────────────────

def _balken(fertig: int, gesamt: int, breite: int = 34) -> str:
    gesamt = max(gesamt, 1)
    anteil = min(max(fertig / gesamt, 0.0), 1.0)
    voll = int(round(anteil * breite))
    return "[" + "#" * voll + "." * (breite - voll) + f"] {anteil * 100:5.1f} %"


def terminal(daten: Dict[str, Any]) -> str:
    z = daten.get("zaehler") or {}
    zeilen = [f"{daten.get('aufgabe', 'Arbeit')}   Stand {daten.get('stand', '?')}", ""]
    fertig, gesamt = int(z.get("fertig") or 0), int(z.get("gesamt") or 0)
    if gesamt:
        zeilen.append(f"{z.get('titel', 'Fortschritt')}: {fertig} / {gesamt} {z.get('einheit', '')}")
        zeilen.append(_balken(fertig, gesamt))
        if z.get("neben"):
            zeilen.append(f"   {z['neben']}")
    zeilen.append("")
    for s in daten.get("schritte") or []:
        zeichen = {"fertig": "x", "laeuft": ">", "offen": " ", "blockiert": "!"}.get(s.get("lage"), " ")
        zeilen.append(f"  [{zeichen}] {s.get('nr')}. {s.get('text')}")
    if daten.get("hinweis"):
        zeilen += ["", f"Hinweis: {daten['hinweis']}"]
    if daten.get("plan"):
        zeilen += ["", f"Plan: {daten['plan']}"]
    return "\n".join(zeilen)


def html(daten: Dict[str, Any]) -> str:
    """Selbst-aktualisierende Seite im Stil der anderen Widgets (Theme-Variablen)."""
    z = daten.get("zaehler") or {}
    fertig, gesamt = int(z.get("fertig") or 0), int(z.get("gesamt") or 0)
    anteil = min(max(fertig / max(gesamt, 1), 0.0), 1.0) * 100

    def schritt_zeile(s: Dict[str, Any]) -> str:
        lage = s.get("lage") or "offen"
        farbe = {"fertig": "var(--ui-green, #3fb950)", "laeuft": "var(--accent)",
                 "blockiert": "var(--ui-red, #f85149)"}.get(lage, "var(--muted-foreground)")
        zeichen = {"fertig": "erledigt", "laeuft": "laeuft", "offen": "offen",
                   "blockiert": "blockiert"}.get(lage, lage)
        return (f'<li><span class="punkt" style="background:{farbe}"></span>'
                f'<span class="nr">{s.get("nr")}</span> {s.get("text")}'
                f'<span class="lage" style="color:{farbe}">{zeichen}</span></li>')

    schritte = "\n".join(schritt_zeile(s) for s in daten.get("schritte") or [])
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="5">
<title>Fortschritt — {daten.get('aufgabe', 'Arbeit')}</title>
<style>
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: transparent; }}
  body {{ font-family: inherit; color: var(--foreground); font-size: 13px; line-height: 1.5; }}
  .wrap {{ width: 100%; max-width: 760px; }}
  h1 {{ font-size: 14.5px; margin: 0 0 2px; }}
  .sub {{ color: var(--muted-foreground); font-size: 11.5px; margin-bottom: 12px; }}
  .kpi {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }}
  .karte {{ border: 1px solid var(--border); border-radius: 10px; padding: 8px 12px;
            background: color-mix(in srgb, var(--card) 60%, transparent); min-width: 118px; }}
  .karte b {{ display: block; font-size: 17px; line-height: 1.2; font-variant-numeric: tabular-nums; }}
  .karte span {{ color: var(--muted-foreground); font-size: 10.5px; text-transform: uppercase; letter-spacing: .05em; }}
  .leiste {{ height: 14px; border: 1px solid var(--border); border-radius: 999px; overflow: hidden;
             background: color-mix(in srgb, var(--card) 50%, transparent); }}
  .fuell {{ height: 100%; width: {anteil:.1f}%;
            background: linear-gradient(90deg, color-mix(in srgb, var(--accent) 70%, transparent), var(--accent));
            transition: width .4s ease; }}
  .prozent {{ margin-top: 4px; font-size: 11.5px; color: var(--muted-foreground); font-variant-numeric: tabular-nums; }}
  ul {{ list-style: none; margin: 12px 0 0; padding: 0; }}
  li {{ display: flex; align-items: baseline; gap: 7px; padding: 3px 0;
        border-top: 1px solid color-mix(in srgb, var(--border) 60%, transparent); }}
  li:first-child {{ border-top: none; }}
  .punkt {{ width: 7px; height: 7px; border-radius: 50%; flex: none; }}
  .nr {{ color: var(--muted-foreground); font-variant-numeric: tabular-nums; }}
  .lage {{ margin-left: auto; font-size: 11px; }}
  .hinweis {{ margin-top: 12px; color: var(--muted-foreground); font-size: 11.5px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>{daten.get('aufgabe', 'Arbeit')}</h1>
  <div class="sub">Stand {daten.get('stand', '?')} — die Seite aktualisiert sich alle 5 Sekunden</div>
  <div class="kpi">
    <div class="karte"><b>{fertig} / {gesamt}</b><span>{z.get('titel', 'Fortschritt')}</span></div>
    <div class="karte"><b>{z.get('dateien', '—')}</b><span>Dateien im Ziel</span></div>
    <div class="karte"><b>{z.get('groesse_mb', '—')} MB</b><span>uebertragen</span></div>
  </div>
  <div class="leiste"><div class="fuell"></div></div>
  <div class="prozent">{anteil:.1f} % abgehakt</div>
  <ul>
{schritte}
  </ul>
  <div class="hinweis">{daten.get('hinweis', '')}</div>
</div>
</body>
</html>
"""


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Fortschritt anzeigen (Terminal und/oder Dashboard).")
    p.add_argument("--terminal", action="store_true", help="Balken in der Konsole ausgeben")
    p.add_argument("--html", action="store_true", help="Dashboard-Datei neu schreiben")
    p.add_argument("--zaehle", action="store_true", help="Papas Fotos per pCloud nachzaehlen")
    args = p.parse_args(argv)

    daten: Dict[str, Any] = {}
    if STATUS.exists():
        try:
            daten = json.loads(STATUS.read_text(encoding="utf-8"))
        except ValueError:
            daten = {}
    if not isinstance(daten, dict):
        daten = {}

    if args.zaehle:
        try:
            zahlen = zaehle_papas_fotos()
            daten.setdefault("zaehler", {})
            daten["zaehler"]["fertig"] = zahlen["mit_inhalt"]
            daten["zaehler"]["gesamt"] = zahlen["unterordner"]
            daten["zaehler"]["kinder"] = zahlen
            daten["zaehler"]["neben"] = (f"{zahlen['dateien']} Dateien, "
                                         f"{zahlen['groesse_mb']} MB in den fertigen Ordnern")
            # Die Anzeige soll die Dateizahl direkt lesen koennen.
            daten["zaehler"]["dateien"] = zahlen["dateien"]
            daten["zaehler"]["groesse_mb"] = zahlen["groesse_mb"]
            lage = "fertig" if zahlen["mit_inhalt"] >= zahlen["unterordner"] else "laeuft"
            for s in daten.get("schritte") or []:
                if s.get("nr") == 1:
                    s["lage"] = lage
        except Exception as fehler:                     # noqa: BLE001 — Anzeige darf nie abstuerzen
            sys.stderr.write(f"Zaehlen nicht moeglich ({fehler.__class__.__name__}); "
                             "die alten Zahlen bleiben stehen.\n")

    if args.zaehle or args.html or args.terminal:
        daten["stand"] = datetime.now().astimezone().strftime("%d.%m.%Y %H:%M:%S")
        STATUS.write_text(json.dumps(daten, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.html:
        WIDGET.parent.mkdir(parents=True, exist_ok=True)
        WIDGET.write_text(html(daten), encoding="utf-8")
        print(f"Dashboard: {WIDGET}")

    if args.terminal or not (args.html or args.zaehle):
        print(terminal(daten))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
