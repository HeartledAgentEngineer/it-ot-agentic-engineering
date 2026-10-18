"""Video-Pruefung — Zahlen statt Schaetzung (To-do Punkt 5, 18.10.2026).

Wozu dieses Werkzeug:
  Sebastian hat drei Fragen zu den Videos gestellt (16.10.2026):
    1. Haben **alle** Videos Standbilder? Welche nicht?
    2. Wie oft wurde **dieselbe Person** in einem Video erkannt?
    3. Sind die Standbilder **brauchbar** (nicht schwarz, nicht doppelt)?
  Dieses Werkzeug beantwortet sie mit **gezaehlten** Zahlen aus den
  vorhandenen Ergebnisdateien — es raet nichts und aendert nichts.

Was gelesen wird (alles nur lesend):
  * Sortierplan (``--plan``, Vorgabe ``sortierplan_bildervideos.json``):
    ``zuege[]`` mit ``fileid`` und ``art`` == ``video`` gilt als Video.
  * ``personen_gruppen/video_standbilder.jsonl`` (``video_standbilder.py``):
    je Zeile ein Standbild zu ``<video_id>#t=<sek>`` mit ``standbild_fileid``,
    ``breite``, ``hoehe``, ``skala``.
  * ``personen_gruppen/gesicht_zuordnung.jsonl`` (Gruppierung): je Zeile ein
    Gesicht mit ``bild_id``, ``index``, ``kennung`` (oder ``null``), ``video_id``.
    Zeilen mit ``video_id`` sind Video-Gesichter, alle anderen Foto-Gesichter.

Drei Mengen, ehrlich getrennt (sie sind **nicht** deckungsgleich, das ist ein
eigener Befund und keine Panne):
  * **Plan-Videos** — was im Plan als Video gefuehrt wird.
  * **Videos mit Gesichtern** — was die Erkennung wirklich gesehen hat.
  * **Videos mit Standbild** — wofuer das Quiz ein Bild zeigen kann.
  Genau **eine** dieser Mengen als "die Videos" auszugeben waere eine
  Schaetzung; genannt werden alle drei und ihre Schnitte.

Brauchbarkeit der Standbilder:
  * **doppelt:** auf Dateiebene ueber ``standbild_fileid`` (zwei Bildstellen
    mit demselben Standbild) — in der Messung waren es 0.
  * **schwarz/leer:** dafuer braucht es **Bildpunkte**. Die gibt es nur, wenn
    die Standbilder von pCloud geholt werden. Das ist ein **Netzzugriff** und
    laeuft deshalb nur mit dem ausdruecklichen Schalter ``--standbild-probe N``
    ueber hoechstens N Bilder (Vorgabe 0 = kein Netz). Gemessen wird je Bild
    die mittlere Helligkeit und die Streuung (PIL, ohne Schreiben); ``dunkel``
    = Mittelwert unter ``DUNKEL_SCHWELLE``. Die Bilder werden **nicht**
    gespeichert und nicht an ein Modell gegeben.

Regeln:
  * Trockenlauf ist Standard: es wird nur gezaehlt und gedruckt.
  * ``--schreiben`` legt den Bericht als JSON neben die Daten
    (``video_pruefung.json``), ``--liste`` zusaetzlich die Kennungen der Videos
    ohne Standbild (``video_ohne_standbild.txt``). Beides idempotent
    (Neuschreibung), im Repo passiert nichts.
  * Keine Namen: ausgegeben werden Kennungen und Zahlen, nie Datei- oder
    Personennamen.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

# Helligkeitsschwelle fuer "schwarz/leer" (Mittelwert 0..255). Ein wirklich
# schwarzer Frame liegt bei ~0-3; 12 laesst auch stark abgedunkelte, aber noch
# sichtbare Bilder durch.
DUNKEL_SCHWELLE = 12.0

STANDARD_ORDNER = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_PLAN = os.path.join(STANDARD_ORDNER, "sortierplan_bildervideos.json")
STANDARD_STANDBILDER = os.path.join(
    STANDARD_ORDNER, "personen_gruppen", "video_standbilder.jsonl")
STANDARD_ZUORDNUNG = os.path.join(
    STANDARD_ORDNER, "personen_gruppen", "gesicht_zuordnung.jsonl")
STANDARD_BERICHT = os.path.join(STANDARD_ORDNER, "video_pruefung.json")
STANDARD_LISTE = os.path.join(STANDARD_ORDNER, "video_ohne_standbild.txt")


# --------------------------------------------------------------------------
# Lesen (nur lesend, wirft nie wegen einer kaputten Zeile)
# --------------------------------------------------------------------------

def zeilen_lesen(pfad: str) -> Iterable[Dict[str, Any]]:
    """Liest eine JSONL-Datei; unlesbare Zeilen werden uebersprungen."""
    if not os.path.isfile(pfad):
        return
    with open(pfad, "r", encoding="utf-8") as f:
        for zeile in f:
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                z = json.loads(zeile)
            except ValueError:
                continue
            if isinstance(z, dict):
                yield z


def video_ids_aus_plan(pfad: str) -> List[str]:
    """Kennungen aller Eintraege mit ``art == 'video'`` (Reihenfolge erhalten)."""
    if not os.path.isfile(pfad):
        return []
    with open(pfad, "r", encoding="utf-8") as f:
        daten = json.load(f)
    zuege = daten.get("zuege") if isinstance(daten, dict) else None
    if not isinstance(zuege, list):
        return []
    out: List[str] = []
    for z in zuege:
        if not isinstance(z, dict):
            continue
        if str(z.get("art", "")).strip().lower() != "video":
            continue
        fid = z.get("fileid")
        if fid is None:
            continue
        out.append(str(fid))
    return out


def standbilder_lesen(pfad: str) -> Dict[str, List[Dict[str, Any]]]:
    """Standbilder je Video-Kennung."""
    out: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for z in zeilen_lesen(pfad):
        vid = z.get("video_id")
        if vid is None:
            continue
        out[str(vid)].append(z)
    return dict(out)


def einzeln_kennungen_lesen(pfad: str) -> Dict[str, List[Dict[str, Any]]]:
    """Gesichtszeilen **je Einzelbild** (``bild_id``) mit Video-Bezug."""
    out: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for z in zeilen_lesen(pfad):
        if not z.get("video_id"):
            continue
        bid = z.get("bild_id")
        if bid is None:
            continue
        out[str(bid)].append(z)
    return dict(out)


def kennungen_zum_video(einzelbilder: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    """Ordnet die Gesichtszeilen dem Video zu (ueber ``video_id`` der Zeile)."""
    out: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for zeilen in einzelbilder.values():
        for z in zeilen:
            vid = z.get("video_id")
            if vid is not None:
                out[str(vid)].append(z)
    return dict(out)


# --------------------------------------------------------------------------
# Reine Auswertungen
# --------------------------------------------------------------------------

def wiederholungen(je_video: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Wie oft dieselbe Person in einem Video erkannt wurde.

    Gezaehlt wird je Video:
      * ``bildstellen`` — verschiedene Einzelbilder mit Gesichtszeilen,
      * ``gesichter`` — alle Gesichtszeilen (mit und ohne Kennung),
      * ``mit_person`` — Gesichtszeilen mit Personen-Kennung,
      * ``personen`` — verschiedene Personen-Kennungen,
      * ``personen_mehrfach`` — Personen, die auf **mehr als einer**
        Bildstelle erkannt wurden (das ist die gesuchte Wiederholung),
      * ``person_auf_mehreren`` — Anzahl solcher Personen (Summe),
      * ``doppel_je_bildstelle`` — Bildstellen, auf denen **dieselbe** Person
        mehr als einmal erkannt wurde (Doppelerkennung im Einzelbild),
      * ``max_person_auf_bildstellen`` — die hoechste Wiederholungszahl.
    """
    je_video_zahlen: Dict[str, Dict[str, int]] = {}
    verteilung: collections.Counter = collections.Counter()
    doppel_bildstellen = 0
    gesamt_mehrfach = 0
    hoechste = 0
    for vid, zeilen in je_video.items():
        bildstellen = set()
        je_stelle: Dict[str, set] = collections.defaultdict(set)
        gesichter = 0
        mit_person = 0
        for z in zeilen:
            gesichter += 1
            bid = str(z.get("bild_id") or f"{vid}#{z.get('index')}")
            bildstellen.add(bid)
            kennung = z.get("kennung")
            if not kennung:
                continue
            mit_person += 1
            je_stelle[bid].add(str(kennung))
        personen = collections.Counter(
            p for namen in je_stelle.values() for p in namen)
        mehrfach = sum(1 for p, n in personen.items() if n > 1)
        # Doppelerkennung: dieselbe Person zweimal AUF EINER Bildstelle kommt
        # ueber die Mengenbildung nicht heraus — deshalb hier die Rohzeilen.
        roh = collections.defaultdict(collections.Counter)
        for z in zeilen:
            if not z.get("kennung"):
                continue
            roh[str(z.get("bild_id") or f"{vid}#{z.get('index')}")][str(z["kennung"])] += 1
        doppelt_hier = sum(1 for c in roh.values() for n in c.values() if n > 1)
        je_video_zahlen[vid] = {
            "bildstellen": len(bildstellen),
            "gesichter": gesichter,
            "mit_person": mit_person,
            "personen": len(personen),
            "personen_mehrfach": mehrfach,
            "doppel_je_bildstelle": doppelt_hier,
        }
        verteilung[mehrfach] += 1
        gesamt_mehrfach += mehrfach
        doppel_bildstellen += doppelt_hier
        hoechste = max(hoechste, max(personen.values()) if personen else 0)
    return {
        "videos": len(je_video_zahlen),
        "videos_mit_wiederholung": sum(
            1 for v in je_video_zahlen.values() if v["personen_mehrfach"] > 0),
        "personen_mehrfach_summe": gesamt_mehrfach,
        "doppel_je_bildstelle": doppel_bildstellen,
        "hoechste_wiederholung": hoechste,
        "verteilung": dict(sorted(verteilung.items())),
        "je_video": je_video_zahlen,
    }


def standbild_zahlen(standbilder: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Zahlen zu den Standbildern selbst (Dubletten, Masse, Skalen)."""
    fids = collections.Counter()
    breiten: collections.Counter = collections.Counter()
    skalen: collections.Counter = collections.Counter()
    zeilen = 0
    ohne_mass = 0
    for vid, liste in standbilder.items():
        for z in liste:
            zeilen += 1
            fid = z.get("standbild_fileid")
            if fid is not None:
                fids[str(fid)] += 1
            b, h = z.get("breite"), z.get("hoehe")
            if not b or not h:
                ohne_mass += 1
            else:
                breiten[int(b)] += 1
            s = z.get("skala")
            if s is not None:
                skalen[round(float(s), 3)] += 1
    doppelte = {k: v for k, v in fids.items() if v > 1}
    je_video = {vid: len(l) for vid, l in standbilder.items()}
    return {
        "videos": len(standbilder),
        "standbilder": zeilen,
        "verschiedene_fids": len(fids),
        "doppelte_fids": len(doppelte),
        "ohne_mass": ohne_mass,
        "breiten": dict(sorted(breiten.items())),
        "skalen": dict(sorted(skalen.items())),
        "min_je_video": min(je_video.values()) if je_video else 0,
        "max_je_video": max(je_video.values()) if je_video else 0,
    }


def helligkeit_messen(bild_bytes: bytes) -> Optional[Dict[str, float]]:
    """Mittlere Helligkeit und Streuung eines Bildes (PIL, nur im Speicher).

    Gibt ``None`` zurueck, wenn PIL fehlt oder das Bild nicht lesbar ist —
    ehrlich statt geraten.
    """
    try:
        from PIL import Image  # noqa: WPS433 (bewusst spaet, PIL ist optional)
    except Exception:
        return None
    import io
    try:
        with Image.open(io.BytesIO(bild_bytes)) as im:
            grau = im.convert("L")
            if grau.width > 320:  # nur grob messen, spart Rechenzeit
                grau = grau.resize((320, max(1, int(grau.height * 320 / grau.width))))
            werte = list(grau.tobytes())
    except Exception:
        return None
    if not werte:
        return None
    mittel = sum(werte) / len(werte)
    var = sum((w - mittel) ** 2 for w in werte) / len(werte)
    return {"mittel": round(mittel, 2), "streuung": round(var ** 0.5, 2)}


def standbild_probe(
    standbilder: Dict[str, List[Dict[str, Any]]],
    anzahl: int,
    leser: Callable[[int], bytes],
    schwelle: float = DUNKEL_SCHWELLE,
) -> Dict[str, Any]:
    """Prueft ``anzahl`` Standbilder auf Helligkeit — ueber einen ``leser``.

    ``leser(fileid) -> bytes`` wird injiziert (pCloud im Betrieb, Attrappe im
    Test). Gezaehlt werden geprueft / nicht lesbar / dunkel; die Einzelwerte
    werden mitgegeben (nur Zahlen, keine Bildinhalte).
    """
    anzahl = max(0, anzahl)
    if anzahl == 0:
        return {"geprueft": 0, "nicht_lesbar": 0, "dunkel": 0,
                "gleich_aussehend": 0, "schwelle": schwelle, "einzelwerte": []}
    kandidaten: List[Dict[str, Any]] = []
    for vid in sorted(standbilder):
        for z in standbilder[vid]:
            fid = z.get("standbild_fileid")
            if fid is None:
                continue
            kandidaten.append(z)
            if len(kandidaten) >= max(0, anzahl):
                break
        if len(kandidaten) >= max(0, anzahl):
            break
    geprueft: List[Dict[str, Any]] = []
    nicht_lesbar = 0
    dunkel = 0
    for z in kandidaten:
        try:
            daten = leser(int(z["standbild_fileid"]))
        except Exception as fehler:  # Netz-/Lesefehler: ehrlich zaehlen
            nicht_lesbar += 1
            geprueft.append({"fileid": z["standbild_fileid"], "fehler": str(fehler)[:80]})
            continue
        mass = helligkeit_messen(daten) if daten else None
        if mass is None:
            nicht_lesbar += 1
            geprueft.append({"fileid": z["standbild_fileid"], "gelesen": len(daten or b""),
                             "fehler": "nicht messbar"})
            continue
        import hashlib
        ist_dunkel = mass["mittel"] < schwelle
        dunkel += 1 if ist_dunkel else 0
        geprueft.append({
            "fileid": z["standbild_fileid"],
            "bytes": len(daten),
            "hash": hashlib.sha256(daten).hexdigest()[:16],
            "mittel": mass["mittel"],
            "streuung": mass["streuung"],
            "dunkel": ist_dunkel,
        })
    hashes = collections.Counter(
        z["hash"] for z in geprueft if z.get("hash"))
    return {
        "geprueft": len(geprueft),
        "nicht_lesbar": nicht_lesbar,
        "dunkel": dunkel,
        "gleich_aussehend": sum(1 for h, n in hashes.items() if n > 1),
        "schwelle": schwelle,
        "einzelwerte": geprueft,
    }


# --------------------------------------------------------------------------
# Gesamtlauf
# --------------------------------------------------------------------------

def pruefen(
    plan: str = STANDARD_PLAN,
    standbilder_datei: str = STANDARD_STANDBILDER,
    zuordnung: str = STANDARD_ZUORDNUNG,
    probe: int = 0,
    leser: Optional[Callable[[int], bytes]] = None,
) -> Dict[str, Any]:
    """Zaehlt alles nach. Ohne ``probe`` und ohne ``leser`` kein Netzzugriff."""
    plan_videos = video_ids_aus_plan(plan)
    plan_set = set(plan_videos)
    standbilder = standbilder_lesen(standbilder_datei)
    stand_set = set(standbilder)
    einzelbilder = einzeln_kennungen_lesen(zuordnung)
    je_video = kennungen_zum_video(einzelbilder)
    video_set = set(je_video)

    ergebnis: Dict[str, Any] = {
        "quellen": {
            "plan": plan,
            "standbilder": standbilder_datei,
            "zuordnung": zuordnung,
        },
        "mengen": {
            "plan_videos": len(plan_set),
            "plan_videos_mit_standbild": len(plan_set & stand_set),
            "plan_videos_ohne_standbild": len(plan_set - stand_set),
            "videos_mit_gesichtern": len(video_set),
            "videos_mit_gesichtern_und_standbild": len(video_set & stand_set),
            "videos_mit_gesichtern_ohne_standbild": len(video_set - stand_set),
            "standbild_videos_ohne_gesichter": len(stand_set - video_set),
            "gesichter_in_videos": sum(len(v) for v in je_video.values()),
            "gesichter_in_videos_mit_person": sum(
                1 for v in je_video.values() for z in v if z.get("kennung")),
        },
        "standbilder": standbild_zahlen(standbilder),
        "wiederholungen": wiederholungen(je_video),
        "ohne_standbild": sorted(video_set - stand_set),
        "plan_ohne_standbild": sorted(plan_set - stand_set),
    }
    if probe and leser is not None:
        ergebnis["probe"] = standbild_probe(standbilder, probe, leser)
    return ergebnis


def bericht(e: Dict[str, Any]) -> str:
    """Klartext-Bericht fuer das Terminal (nur Zahlen, keine Namen)."""
    m = e["mengen"]
    s = e["standbilder"]
    w = e["wiederholungen"]
    zeilen = [
        "Video-Pruefung (nur lesend, nur Zahlen)",
        f"  Plan-Videos:                     {m['plan_videos']}",
        f"  davon mit Standbild:             {m['plan_videos_mit_standbild']}",
        f"  davon ohne Standbild:            {m['plan_videos_ohne_standbild']}",
        f"  Videos mit erkannten Gesichtern: {m['videos_mit_gesichtern']}",
        f"  davon mit Standbild:             {m['videos_mit_gesichtern_und_standbild']}",
        f"  davon ohne Standbild:            {m['videos_mit_gesichtern_ohne_standbild']}",
        f"  Gesichter in Videos:             {m['gesichter_in_videos']}",
        f"  davon mit Personen-Kennung:      {m['gesichter_in_videos_mit_person']}",
        f"  Standbilder:                     {s['standbilder']} "
        f"(verschiedene Kennungen: {s['verschiedene_fids']}, doppelt: {s['doppelte_fids']})",
        f"  Standbilder je Video:            {s['min_je_video']} bis {s['max_je_video']}",
        f"  Standbilder ohne Mass:           {s['ohne_mass']}",
        f"  Videos mit Wiederholung:         {w['videos_mit_wiederholung']} von {w['videos']}",
        f"  Personen mehrfach (Summe):       {w['personen_mehrfach_summe']}",
        f"  hoechste Wiederholung:           {w['hoechste_wiederholung']} Bildstellen",
        f"  Doppelerkennung je Bildstelle:   {w['doppel_je_bildstelle']}",
    ]
    if "probe" in e:
        p = e["probe"]
        zeilen.append(
            f"  Probe: {p['geprueft']} geprueft, {p['dunkel']} dunkel "
            f"(< {p['schwelle']}), {p['gleich_aussehend']} gleich aussehend, "
            f"{p['nicht_lesbar']} nicht lesbar")
        messbar = [z for z in p["einzelwerte"] if "mittel" in z]
        if messbar:
            mittel = sum(z["mittel"] for z in messbar) / len(messbar)
            zeilen.append(
                f"  Helligkeit im Mittel:            {mittel:.1f} von 255 "
                f"(dunkelster {min(z['mittel'] for z in messbar):.1f}, "
                f"hellster {max(z['mittel'] for z in messbar):.1f})")
    return "\n".join(zeilen)


def _pcloud_leser() -> Optional[Callable[[int], bytes]]:
    """Liest Standbild-Bytes von pCloud (nur lesend) — fuer ``--standbild-probe``."""
    hier = os.path.dirname(os.path.abspath(__file__))
    projekt = os.path.dirname(os.path.dirname(hier))
    backend = os.path.join(projekt, "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    try:
        from app.services.pcloud_service import PCloudService  # noqa: WPS433
    except Exception as fehler:
        print(f"pCloud nicht verfuegbar: {fehler}")
        return None
    dienst = PCloudService()

    def lesen(fileid: int) -> bytes:
        return dienst.datei_bytes(fileid)

    return lesen


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Video-Pruefung: Standbilder, Wiederholungen, Brauchbarkeit")
    p.add_argument("--plan", default=STANDARD_PLAN)
    p.add_argument("--standbilder", dest="standbilder_datei",
                   default=STANDARD_STANDBILDER)
    p.add_argument("--zuordnung", default=STANDARD_ZUORDNUNG)
    p.add_argument("--standbild-probe", dest="probe", type=int, default=0,
                   help="so viele Standbilder von pCloud holen und auf "
                        "Helligkeit messen (0 = kein Netzzugriff)")
    p.add_argument("--schreiben", action="store_true",
                   help="Bericht als JSON neben die Daten schreiben")
    p.add_argument("--liste", action="store_true",
                   help="Kennungen der Videos ohne Standbild mitschreiben")
    args = p.parse_args(argv)

    leser = _pcloud_leser() if args.probe > 0 else None
    if args.probe > 0 and leser is None:
        return 2
    e = pruefen(plan=args.plan, standbilder_datei=args.standbilder_datei,
                zuordnung=args.zuordnung, probe=args.probe, leser=leser)
    print(bericht(e))

    if args.schreiben:
        with open(STANDARD_BERICHT, "w", encoding="utf-8") as f:
            json.dump(e, f, ensure_ascii=False, indent=1, sort_keys=True)
        print(f"Bericht geschrieben: {STANDARD_BERICHT}")
    if args.liste:
        with open(STANDARD_LISTE, "w", encoding="utf-8") as f:
            f.write("\n".join(e["ohne_standbild"]) + ("\n" if e["ohne_standbild"] else ""))
        print(f"Liste geschrieben: {STANDARD_LISTE} ({len(e['ohne_standbild'])} Zeilen)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
