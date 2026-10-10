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
    * ``laufende``     — zwei lebende Balken aus den Ergebnisdateien der gerade
      laufenden Arbeiten (reiche Bildbeschreibung, Gesichtserkennung Papas
      Fotos): fertige von geplanten Zeilen, Prozent, Kosten samt Budgetdeckel
      (nur Bildbeschreibung) und die zuletzt bearbeitete Datei mit Uhrzeit.
      Rein lokal und nur lesend, ohne Netzzugriff; fehlertolerant (fehlende
      Datei oder gerade erst halb geschriebene letzte Zeile stuerzen nie ab —
      dann gilt die letzte lesbare Zeile plus Hinweis). Laeuft bei jedem
      Aufruf mit und landet unter ``laufende`` in ``status.json``.

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
from html import escape
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

# Ergebnisdateien der zwei laufenden Arbeiten (Stand 10.10.2026). Gelesen wird
# nur; fehlt eine Datei, zeigt die Anzeige 0 Prozent mit Hinweis statt Fehler.
FOTO_SORTIERUNG = Path("C:/Users/sebas/foto_sortierung")
LAUFENDE_ARBEITEN: List[Dict[str, Any]] = [
    {
        "titel": "Bildbeschreibung reich",
        "auftrag": "489 Boegen zu je 36 Kacheln",
        "datei": FOTO_SORTIERUNG / "bild_beschreibungen_reich.jsonl",
        "gesamt": 17580,
        "einheit": "Bilder",
        "mit_kosten": True,
        "budget_usd": 12.00,
    },
    {
        "titel": "Gesichtserkennung Papas Fotos",
        "auftrag": "",
        "datei": FOTO_SORTIERUNG / "personen_vektoren_papa.jsonl",
        "gesamt": 6336,
        "einheit": "Bilder",
        "mit_kosten": False,
        "budget_usd": None,
    },
]


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


# ── Laufende Arbeiten (lokale Ergebnisdateien, nur lesend) ────────────────

def _prozent(fertig: int, gesamt: int) -> float:
    """Anteil in Prozent, eine Nachkommastelle, nie ueber 100."""
    if gesamt <= 0:
        return 0.0
    return round(min(fertig / gesamt, 1.0) * 100.0, 1)


def _zeit_lesbar(wert: Any) -> str:
    """ISO-Zeit aus einer Ergebniszeile lesbar machen; Unbekanntes bleibt Text."""
    text = str(wert or "").strip()
    if not text:
        return ""
    try:
        zeit = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return zeit.strftime("%d.%m.%Y %H:%M:%S")


def _datei_stand_lesbar(pfad: Path) -> str:
    """Aenderungszeit der Ergebnisdatei — Ersatz-Uhrzeit, wenn die Zeile keine traegt."""
    try:
        return datetime.fromtimestamp(pfad.stat().st_mtime).strftime("%d.%m.%Y %H:%M:%S")
    except OSError:
        return ""


def _kosten_aus_eintrag(eintrag: Dict[str, Any]) -> float:
    try:
        return float(eintrag.get("kosten_usd") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def messe_jsonl(pfad: Path, gesamt: int, mit_kosten: bool = False) -> Dict[str, Any]:
    """Eine fortlaufend wachsende JSONL-Ergebnisdatei messen — fehlertolerant.

    Die Schreiber haengen je Ergebnis eine vollstaendige Zeile an (mit
    Zeilenende). Gezaehlt werden deshalb nur ABGESCHLOSSENE Zeilen, die wie
    ein JSON-Objekt beginnen und enden (Byte-Muster, ohne die Datei zu
    entschluesseln): eine gerade erst halb geschriebene Schlusszeile zaehlt
    noch nicht und wird uebersprungen. Fuer "wo steht er gerade" wird die
    letzte LESBARE Zeile
    genommen; ist die Schlusszeile angebrochen oder unlesbar, wird ein Hinweis
    gesetzt. Fehlende Datei oder Lesefehler ergeben 0 Prozent mit Hinweis —
    diese Funktion wirft nie.

    Rueckgabe (Schluessel): ``datei``, ``fertig``, ``gesamt``, ``prozent``,
    ``kosten_usd`` (nur bei ``mit_kosten``), ``letzte_datei``, ``letzte_zeit``,
    ``zeit_quelle`` ("eintrag" oder "datei"), ``hinweis``.
    """
    pfad = Path(pfad)
    ergebnis: Dict[str, Any] = {
        "datei": str(pfad),
        "fertig": 0,
        "gesamt": max(int(gesamt), 0),
        "prozent": 0.0,
        "kosten_usd": 0.0 if mit_kosten else None,
        "letzte_datei": "",
        "letzte_zeit": "",
        "zeit_quelle": "",
        "hinweis": "",
    }
    if not pfad.is_file():
        ergebnis["hinweis"] = "Ergebnisdatei fehlt noch"
        return ergebnis
    try:
        rohdaten = pfad.read_bytes()
    except OSError as fehler:
        ergebnis["hinweis"] = f"Ergebnisdatei nicht lesbar ({fehler.__class__.__name__})"
        return ergebnis

    # Gezaehlt wird direkt auf den rohen Bytes: Eine Zeile zaehlt, wenn sie wie
    # ein JSON-Objekt BEGINNT und so ENDET. Das sind zwei Byte-Muster-Zaehlungen
    #   * Zeilenanfang: "{" direkt nach einem Zeilenumbruch (bzw. am Dateianfang)
    #   * Zeilenende:   "}" direkt vor dem Zeilenumbruch (LF oder CRLF)
    # Der kleinere der beiden Werte glaettet Sonderfaelle (z. B. eine vom
    # Neustart mit Zeilenende abgeschlossene, aber kaputte Zeile: sie beginnt
    # mit "{" und endet nicht mit "}"). So bleibt die Messung auch bei grossen
    # Vektorzeilen (~12 KB je Zeile) billig, ohne die Datei zu entschluesseln.
    beginnen = rohdaten.count(b"\n{") + (1 if rohdaten[:1] == b"{" else 0)
    # Zeilenende-Konvention einmal an der ersten Zeile ablesen (LF oder CRLF);
    # gemischte Dateien schliessen die Schreiber aus, sonst wird beides gezaehlt.
    probe = rohdaten[:65536]
    probe_pos = probe.find(b"\n")
    if probe_pos > 0 and probe[probe_pos - 1:probe_pos] == b"\r":
        enden = rohdaten.count(b"}\r\n")
    elif probe_pos > 0:
        enden = rohdaten.count(b"}\n")
    else:
        enden = rohdaten.count(b"}\n") + rohdaten.count(b"}\r\n")
    ergebnis["fertig"] = min(beginnen, enden)
    ergebnis["prozent"] = _prozent(ergebnis["fertig"], ergebnis["gesamt"])
    angebrochen = False
    if rohdaten and not rohdaten.endswith(b"\n"):
        angebrochen = bool(rohdaten[rohdaten.rfind(b"\n") + 1:].strip())

    letzter: Optional[Dict[str, Any]] = None
    kaputt = 0
    if mit_kosten:
        # Die Kostensumme braucht jede Zeile — hier wird wirklich geparst
        # (die Bildbeschreibungs-Zeilen sind klein).
        text = rohdaten.decode("utf-8", "replace")
        summe = 0.0
        for zeile in text.split("\n")[:-1]:
            if not zeile.strip():
                continue
            try:
                eintrag = json.loads(zeile)
            except ValueError:
                eintrag = None
            if isinstance(eintrag, dict):
                summe += _kosten_aus_eintrag(eintrag)
                letzter = eintrag
            else:
                kaputt += 1
        ergebnis["kosten_usd"] = round(summe, 6)
    else:
        # Schneller Weg fuer grosse Vektorzeilen: nur das Ende wirklich lesen.
        schwanz = rohdaten[-1_048_576:].decode("utf-8", "replace")
        kandidaten = [z.strip() for z in schwanz.split("\n") if z.strip()]
        for zeile in reversed(kandidaten[-200:]):
            try:
                eintrag = json.loads(zeile)
            except ValueError:
                continue
            if isinstance(eintrag, dict):
                letzter = eintrag
                break

    if isinstance(letzter, dict):
        kennung = letzter.get("datei") or letzter.get("bild_id") or ""
        ergebnis["letzte_datei"] = str(kennung)
        if letzter.get("zeit"):
            ergebnis["letzte_zeit"] = _zeit_lesbar(letzter.get("zeit"))
            ergebnis["zeit_quelle"] = "eintrag"
        else:
            ergebnis["letzte_zeit"] = _datei_stand_lesbar(pfad)
            ergebnis["zeit_quelle"] = "datei"

    if angebrochen:
        ergebnis["hinweis"] = ("Die letzte Zeile ist noch nicht fertig geschrieben — "
                               "angezeigt ist die letzte lesbare Zeile.")
    elif kaputt:
        ergebnis["hinweis"] = f"{kaputt} Zeile(n) waren nicht lesbar und wurden uebersprungen."
    elif ergebnis["fertig"] == 0:
        ergebnis["hinweis"] = "Noch kein fertiger Eintrag in der Ergebnisdatei."
    return ergebnis


def messe_laufende_arbeiten() -> List[Dict[str, Any]]:
    """Die zwei laufenden Arbeiten messen (rein lokal, nur lesend)."""
    ergebnisse: List[Dict[str, Any]] = []
    for eintrag in LAUFENDE_ARBEITEN:
        messwerte = messe_jsonl(eintrag["datei"], eintrag["gesamt"],
                                mit_kosten=bool(eintrag["mit_kosten"]))
        ergebnisse.append({
            "titel": eintrag["titel"],
            "auftrag": eintrag["auftrag"],
            "einheit": eintrag["einheit"],
            "fertig": messwerte["fertig"],
            "gesamt": messwerte["gesamt"],
            "prozent": messwerte["prozent"],
            "kosten_usd": messwerte["kosten_usd"],
            "budget_usd": eintrag["budget_usd"],
            "datei": messwerte["datei"],
            "letzte_datei": messwerte["letzte_datei"],
            "letzte_zeit": messwerte["letzte_zeit"],
            "zeit_quelle": messwerte["zeit_quelle"],
            "hinweis": messwerte["hinweis"],
        })
    return ergebnisse


# ── Anzeigen ───────────────────────────────────────────────────────────────

def _zahl(wert: Any, stellen: int = 0) -> str:
    """Zahl deutsch lesbar machen: Tausenderpunkt, Komma als Dezimaltrenner."""
    try:
        text = f"{float(wert):,.{stellen}f}"
    except (TypeError, ValueError):
        return str(wert)
    return text.replace(",", "§").replace(".", ",").replace("§", ".")


def _balken(fertig: int, gesamt: int, breite: int = 34, komma: bool = False) -> str:
    gesamt = max(gesamt, 1)
    anteil = min(max(fertig / gesamt, 0.0), 1.0)
    voll = int(round(anteil * breite))
    prozent = f"{anteil * 100:5.1f} %"
    if komma:
        prozent = prozent.replace(".", ",")
    return "[" + "#" * voll + "." * (breite - voll) + f"] {prozent}"


def _laufende_zeilen(eintrag: Dict[str, Any]) -> Dict[str, str]:
    """Die Anzeigetexte je laufender Arbeit bauen — EINE Quelle fuer beide Ansichten."""
    fertig = int(eintrag.get("fertig") or 0)
    gesamt = int(eintrag.get("gesamt") or 0)
    einheit = str(eintrag.get("einheit") or "").strip()
    zahlen = f"{_zahl(fertig)} von {_zahl(gesamt)}"
    if einheit:
        zahlen += f" {einheit}"
    kosten = ""
    if eintrag.get("kosten_usd") is not None:
        ausgegeben = float(eintrag.get("kosten_usd") or 0.0)
        deckel = eintrag.get("budget_usd")
        if deckel:
            kosten = (f"Kosten: {_zahl(ausgegeben, 4)} von {_zahl(deckel, 2)} USD "
                      f"({_zahl(ausgegeben / float(deckel) * 100, 1)} % vom Budget)")
        else:
            kosten = f"Kosten: {_zahl(ausgegeben, 4)} USD"
    letzte = ""
    if eintrag.get("letzte_datei") or eintrag.get("letzte_zeit"):
        kennung = str(eintrag.get("letzte_datei") or "?")
        zeit = str(eintrag.get("letzte_zeit") or "?")
        if eintrag.get("zeit_quelle") == "eintrag":
            letzte = f"zuletzt bearbeitet: {kennung} — {zeit}"
        else:
            letzte = f"zuletzt: {kennung} — Datei geaendert {zeit}"
    return {
        "titel": str(eintrag.get("titel") or "Arbeit"),
        "auftrag": str(eintrag.get("auftrag") or ""),
        "zahlen": zahlen,
        "prozent": f"{_zahl(eintrag.get('prozent') or 0, 1)} %",
        "kosten": kosten,
        "letzte": letzte,
        "hinweis": str(eintrag.get("hinweis") or ""),
    }


def terminal(daten: Dict[str, Any]) -> str:
    z = daten.get("zaehler") or {}
    zeilen = [f"{daten.get('aufgabe', 'Arbeit')}   Stand {daten.get('stand', '?')}", ""]
    fertig, gesamt = int(z.get("fertig") or 0), int(z.get("gesamt") or 0)
    if gesamt:
        zeilen.append(f"{z.get('titel', 'Fortschritt')}: {fertig} / {gesamt} {z.get('einheit', '')}")
        zeilen.append(_balken(fertig, gesamt))
        if z.get("neben"):
            zeilen.append(f"   {z['neben']}")
    laufende = daten.get("laufende") or []
    if laufende:
        zeilen.append("")
        zeilen.append("Laufende Arbeiten:")
        for eintrag in laufende:
            teile = _laufende_zeilen(eintrag)
            fertig_l = int(eintrag.get("fertig") or 0)
            gesamt_l = int(eintrag.get("gesamt") or 0)
            kopf = teile["titel"] + (f" ({teile['auftrag']})" if teile["auftrag"] else "")
            zeilen.append(f"  {kopf}")
            zeilen.append(f"    {teile['zahlen']}")
            zeilen.append("    " + _balken(fertig_l, gesamt_l, komma=True))
            if teile["kosten"]:
                zeilen.append(f"    {teile['kosten']}")
            if teile["letzte"]:
                zeilen.append(f"    {teile['letzte']}")
            if teile["hinweis"]:
                zeilen.append(f"    Hinweis: {teile['hinweis']}")
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

    def lauf_block(eintrag: Dict[str, Any]) -> str:
        teile = _laufende_zeilen(eintrag)
        fertig_l = int(eintrag.get("fertig") or 0)
        gesamt_l = int(eintrag.get("gesamt") or 0)
        anteil_l = min(max(fertig_l / max(gesamt_l, 1), 0.0), 1.0) * 100
        teile_html = [
            f'<div class="lauf-kopf"><span class="lauf-titel">{escape(teile["titel"])}</span>'
            f'<span class="lauf-zahlen">{escape(teile["zahlen"])}</span></div>',
        ]
        if teile["auftrag"]:
            teile_html.append(f'<div class="lauf-unter">{escape(teile["auftrag"])}</div>')
        teile_html.append('<div class="leiste"><div class="fuell fuell-lauf" '
                          f'style="width:{anteil_l:.1f}%"></div></div>')
        meta = f'<span class="pct">{escape(teile["prozent"])}</span>'
        if teile["kosten"]:
            meta += f'<span>{escape(teile["kosten"])}</span>'
        teile_html.append(f'<div class="lauf-meta">{meta}</div>')
        if teile["letzte"]:
            teile_html.append(f'<div class="lauf-meta"><span>{escape(teile["letzte"])}</span></div>')
        if teile["hinweis"]:
            teile_html.append(f'<div class="lauf-hinweis">Hinweis: {escape(teile["hinweis"])}</div>')
        return '<div class="lauf">' + "".join(teile_html) + "</div>"

    schritte = "\n".join(schritt_zeile(s) for s in daten.get("schritte") or [])
    laufende = daten.get("laufende") or []
    lauf_html = ""
    if laufende:
        lauf_html = ('<h2 class="lauf-h">Laufende Arbeiten</h2>\n'
                     + "\n".join(lauf_block(e) for e in laufende))
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
  h2.lauf-h {{ font-size: 12px; margin: 16px 0 6px; text-transform: uppercase;
              letter-spacing: .05em; color: var(--muted-foreground); }}
  .lauf {{ border: 1px solid var(--border); border-radius: 10px; padding: 9px 12px; margin-bottom: 10px;
           background: color-mix(in srgb, var(--card) 60%, transparent); }}
  .lauf-kopf {{ display: flex; justify-content: space-between; gap: 10px; align-items: baseline; }}
  .lauf-titel {{ font-weight: 600; }}
  .lauf-zahlen {{ color: var(--muted-foreground); font-variant-numeric: tabular-nums; }}
  .lauf-unter {{ color: var(--muted-foreground); font-size: 11px; margin-top: 1px; }}
  .lauf .leiste {{ height: 10px; margin-top: 6px; }}
  .fuell-lauf {{ background: var(--accent); }}
  .lauf-meta {{ display: flex; justify-content: space-between; gap: 10px; margin-top: 5px;
               color: var(--muted-foreground); font-size: 11.5px; font-variant-numeric: tabular-nums; }}
  .lauf-meta .pct {{ color: var(--foreground); }}
  .lauf-hinweis {{ margin-top: 5px; font-size: 11px; color: var(--muted-foreground); }}
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
  {lauf_html}
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

    # Die zwei laufenden Arbeiten messen (rein lokal, schnell, ohne Netz).
    try:
        daten["laufende"] = messe_laufende_arbeiten()
    except Exception as fehler:                         # noqa: BLE001 — Anzeige darf nie abstuerzen
        sys.stderr.write(f"Messen der laufenden Arbeiten nicht moeglich "
                         f"({fehler.__class__.__name__}); die alten Zahlen bleiben stehen.\n")

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

