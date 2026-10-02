"""Digitales Fotobuch (CEWE ``.mcf``) -> Seiten für die Erzähl-Diashow (02.10.2026).

Warum:
  Im Ordner „Bilder & Videos/___Photobücher_…" liegt neben ~2.200 Fotos die
  Projektdatei des Fotobuchs (``.mcf``, XML). Gezählt am 02.10.: 159 Seiten,
  860 Bildplätze (alle 852 verwiesenen Dateien im Ordner), 130 Textfelder. Die
  Fotos selbst taugen schlecht zum Ordnen (viele EXIF-Daten = Scan-/Bearbeitungs-
  datum 2013, kaum GPS) — das Buch IST die Ordnung: Seiten = Momente, in der
  damals gewählten Reihenfolge, mit den eigenen Texten.

Was es tut (nur lesend):
  * ``.mcf`` lesen: je Inhaltsseite (``page type=CONTENT``, auch Umschlag) die
    Bilder in Lesereihenfolge (oben→unten, links→rechts) und die Texte (HTML →
    Klartext).
  * Bilder → pCloud-``fileid`` über die vorhandene Ordner-Abfrage
    (``foto_themen.dateien_im_ordner``, ein ``listfolder`` je Unterordner).
  * Ausgabe ``~/foto_sortierung/fotobuch_ereignisse.jsonl`` im Format der
    Erzähl-Diashow (``kennung``, ``titel``, ``datei_kennungen``, ``kategorie``)
    plus ``seite``, ``buch``, ``texte``. Die Diashow zeigt die Seiten oben in
    der Liste; zu jedem Bild kann Sebastian erzählen (``geschichten.jsonl``).

Datenschutz: Konsole nur Zahlen (keine Texte, keine Dateinamen). Ziel im Repo
-> Exit 2. Kein Sprachmodell. ``--senden`` legt die Datei per adb nach
``/sdcard/Download`` (die App übernimmt sie beim Start).
Exit: 0 ok, 2 Aufruf/Schutz, 3 keine .mcf / nicht lesbar, 1 Übertragung.
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from typing import Callable, Dict, List, Tuple

HIER = os.path.dirname(os.path.abspath(__file__))
PROJEKT = os.path.dirname(os.path.dirname(HIER))
STANDARD_ORDNER = "P:/Bilder & Videos/___Photobücher_Buddy_Jule"
STANDARD_AUSGABE = os.path.join(os.path.expanduser("~"), "foto_sortierung", "fotobuch_ereignisse.jsonl")
DATEINAME = "fotobuch_ereignisse.jsonl"
SEITENTYPEN = ("CONTENT", "FULLCOVER")
TITEL_TEXT_MAX = 70


def _themen():
    spez = importlib.util.spec_from_file_location("foto_themen", os.path.join(HIER, "foto_themen.py"))
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)  # type: ignore[union-attr]
    return modul


# ── Reine Funktionen ────────────────────────────────────────────────────────

def html_zu_text(roh: str) -> str:
    """CEWE speichert Texte als HTML: Absätze -> Zeilen, Tags weg, Leerraum ordnen."""
    t = re.sub(r"(?is)<(head|style|script)\b.*?</\1>", " ", roh or "")
    t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    zeilen = [re.sub(r"[ \t\u00a0]+", " ", z).strip() for z in t.splitlines()]
    return "\n".join(z for z in zeilen if z)


def _zahl(wert, standard=0.0) -> float:
    try:
        return float(wert)
    except (TypeError, ValueError):
        return standard


def seiten_lesen(mcf_pfad: str) -> List[Dict]:
    """``.mcf`` -> [{lauf, seite, typ, bilder, texte}] in Buchreihenfolge.

    ``lauf`` = Stelle im Buch (eindeutig, auch bei zwei Umschlagseiten),
    ``seite`` = Seitenzahl nur über Inhaltsseiten (Umschlag = 0).
    """
    wurzel = ET.parse(mcf_pfad).getroot()
    seiten = []
    inhalt = 0
    for lauf, page in enumerate(wurzel.iter("page"), 1):
        typ = (page.get("type") or "").upper()
        if typ not in SEITENTYPEN:
            continue
        if typ == "CONTENT":
            inhalt += 1
        bilder: List[Tuple[float, float, str]] = []
        texte: List[Tuple[float, float, str]] = []
        for area in page.iter("area"):
            oben, links = _zahl(area.get("top")), _zahl(area.get("left"))
            for img in area.findall("image"):
                name = os.path.basename((img.get("filename") or "").replace("\\", "/"))
                if name:
                    bilder.append((oben, links, name))
            for txt in area.findall("text"):
                klar = html_zu_text("".join(txt.itertext()))
                if klar:
                    texte.append((oben, links, klar))
        bilder.sort()
        texte.sort()
        seiten.append({"lauf": lauf, "seite": inhalt if typ == "CONTENT" else 0, "typ": typ,
                       "bilder": [b[2] for b in bilder], "texte": [t[2] for t in texte]})
    return seiten


def titel_bauen(seite: Dict, buch: str) -> str:
    """„Fotobuch Buddy Jule · S. 12 – <Anfang des ersten Textes>“."""
    kopf = f"{buch} · S. {seite['seite']}"
    if seite["typ"] == "FULLCOVER":
        kopf = f"{buch} · Umschlag"
    text = (seite["texte"][0].splitlines()[0] if seite["texte"] else "").strip()
    if len(text) > TITEL_TEXT_MAX:
        text = text[:TITEL_TEXT_MAX - 1].rstrip() + "…"
    return f"{kopf} – {text}" if text else kopf


def ereignisse_bauen(seiten: List[Dict], namen_zu_fileid: Dict[str, int], buch: str,
                     buch_kurz: str) -> Tuple[List[Dict], Dict[str, int]]:
    zahlen = {"seiten": len(seiten), "mit_bildern": 0, "bilder": 0, "gefunden": 0, "texte": 0}
    ereignisse = []
    for s in seiten:
        ids = []
        for name in s["bilder"]:
            zahlen["bilder"] += 1
            fid = namen_zu_fileid.get(name.casefold())
            if fid:
                zahlen["gefunden"] += 1
                ids.append(fid)
        zahlen["texte"] += len(s["texte"])
        if not ids and not s["texte"]:
            continue
        zahlen["mit_bildern"] += 1 if ids else 0
        ereignisse.append({
            "kennung": f"fotobuch-{buch_kurz}-{s['lauf']:03d}",
            # „event" ist das Titelfeld, das die Erzähl-Diashow liest (erzaehl_service._titel_aus).
            "event": titel_bauen(s, buch), "titel": titel_bauen(s, buch), "kategorie": "Fotobuch",
            "datum": None, "jahr": None, "buch": buch, "seite": s["seite"],
            "datei_kennungen": ids, "anzahl_dateien": len(ids), "texte": s["texte"],
        })
    return ereignisse, zahlen


def _kurz(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")[:30] or "buch"


# ── Ein-/Ausgabe ────────────────────────────────────────────────────────────

def fileids_holen(ordner: str, abruf=None) -> Dict[str, int]:
    """{dateiname.casefold(): fileid} über alle Unterordner (je ein listfolder)."""
    th = _themen()
    abruf = abruf or th.echter_api_abruf()
    speicher: dict = {}
    ergebnis: Dict[str, int] = {}
    for wurzel, _, _ in os.walk(ordner):
        for name, info in th.dateien_im_ordner(wurzel.replace("\\", "/"), abruf, speicher).items():
            ergebnis.setdefault(name.casefold(), int(info["fileid"]))
    return ergebnis


def _im_repo(pfad: str) -> bool:
    try:
        return os.path.commonpath([os.path.realpath(pfad), os.path.realpath(PROJEKT)]) == \
            os.path.realpath(PROJEKT)
    except ValueError:
        return False


def _ausfuehren(befehl: List[str]) -> Tuple[int, str]:
    try:
        lauf = subprocess.run(befehl, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as problem:
        return 127, problem.__class__.__name__
    return lauf.returncode, (lauf.stdout or "") + (lauf.stderr or "")


def main(argv=None, abruf=None, ausfuehren: Callable = _ausfuehren) -> int:
    p = argparse.ArgumentParser(description="CEWE-Fotobuch -> Seiten für die Erzähl-Diashow (nur Zahlen).")
    p.add_argument("--ordner", default=STANDARD_ORDNER)
    p.add_argument("--ausgabe", default=STANDARD_AUSGABE)
    p.add_argument("--schreiben", action="store_true")
    p.add_argument("--senden", action="store_true", help="schreiben und per adb nach /sdcard/Download")
    a = p.parse_args(argv)
    if _im_repo(a.ausgabe):
        print("Ziel liegt im Repo - abgelehnt (persönliche Daten gehören nie ins Repo).")
        return 2
    mcf = sorted(os.path.join(w, f) for w, _, fs in os.walk(a.ordner) for f in fs if f.lower().endswith(".mcf"))
    if not mcf:
        print("Keine .mcf-Projektdatei im Ordner gefunden.")
        return 3
    try:
        seiten = seiten_lesen(mcf[0])
    except (ET.ParseError, OSError) as fehler:
        print(f"Fotobuch nicht lesbar ({fehler.__class__.__name__}).")
        return 3
    buch = "Fotobuch " + os.path.splitext(os.path.basename(mcf[0]))[0].replace("_", " ").strip()
    namen = fileids_holen(a.ordner, abruf)
    ereignisse, z = ereignisse_bauen(seiten, namen, buch, _kurz(buch))
    print(f"Seiten: {z['seiten']} · mit Bildern: {z['mit_bildern']} · Bilder: {z['bilder']} "
          f"(in pCloud gefunden: {z['gefunden']}) · Textfelder: {z['texte']}")
    if not (a.schreiben or a.senden):
        print("Trockenlauf - nichts geschrieben. Mit --schreiben bzw. --senden ausführen.")
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(a.ausgabe)), exist_ok=True)
    temp = a.ausgabe + ".tmp"
    with open(temp, "w", encoding="utf-8", newline="\n") as datei:
        for e in ereignisse:
            datei.write(json.dumps(e, ensure_ascii=False) + "\n")
    os.replace(temp, a.ausgabe)
    print(f"geschrieben: {DATEINAME} ({len(ereignisse)} Seiten, außerhalb des Repos)")
    if a.senden:
        groesse = os.path.getsize(a.ausgabe)
        c1, _ = ausfuehren(["adb", "push", a.ausgabe, f"/sdcard/Download/{DATEINAME}"])
        c2, aus = ausfuehren(["adb", "shell", "stat", "-c", "%s", f"/sdcard/Download/{DATEINAME}"])
        if c1 != 0 or c2 != 0 or aus.strip() != str(groesse):
            print("FEHLER: Übertragung aufs Handy fehlgeschlagen (Kabel? USB-Debugging?)")
            return 1
        print("gesendet. Am Handy Widget 'agent' antippen - dann stehen die Seiten in 📖 Erzählen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
