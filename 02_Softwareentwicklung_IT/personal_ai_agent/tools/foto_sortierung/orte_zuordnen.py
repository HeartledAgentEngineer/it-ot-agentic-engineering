"""Orte je Bild aus GPS-Metadaten, OFFLINE (Nachtlauf N-0929, Schritt 3 / E13c).

Wozu dieses Werkzeug:
  ``gesicht_erkennen.py`` legt je Bild eine Vektorzeile mit ``bild_id`` und
  ``metadaten`` (Aufnahmezeit, Kamera, ``gps``) ab. Dieses Werkzeug macht
  daraus **Ortsnamen** (Land, Region, naechste Stadt) — als eigene, schmale
  Datei, die die Verknuepfungsschicht (Ereignisse, "wer war wo") nutzen kann,
  **ohne Koordinaten** weiterzureichen. Die Koordinaten bleiben in der
  Vektordatei.

Was dieses Werkzeug bewusst NICHT tut:
  * **Kein Netz.** Geocoding laeuft offline ueber das Python-Paket
    ``reverse_geocoder`` (GeoNames ``cities1000`` liegt im Paket; der
    Nearest-Neighbour-Index wird lokal gebaut). Kein Nominatim, kein Google.
  * **Keine Koordinaten in der Ausgabe** — nur Ortsnamen. Auch die Konsole
    zeigt weder Koordinaten noch Orte/Staedte, nur Laendernamen mit Anzahl.
  * **Keine Bilder** werden geoeffnet; gelesen wird nur die Vektorzeilen-JSONL.
  * **Kein Ueberschreiben, keine Loeschung.** Die Ausgabe wird angehaengt;
    vorhandene ``bild_id`` werden uebersprungen (idempotent).
  * **Kein Schreiben ohne ``--schreiben``.** Standard ist der Trockenlauf
    (nur zaehlen, auch ohne Geocoder-Aufruf).
  * **Keine Ausgabe im Repo:** ein Zielpfad im Repo endet mit ``SystemExit(2)``.

Abhaengigkeit (Werkzeug-Abhaengigkeit, bewusst NICHT in
``backend/requirements.txt``, weil das Backend sie nicht braucht)::

    backend/.venv/Scripts/python -m pip install reverse_geocoder

  (zieht ``scipy`` nach; getestet mit reverse_geocoder 1.5.1). Fehlt das Paket,
  beendet sich das Werkzeug beim Schreiblauf mit einer deutschen Meldung und
  Exit 2. Der Geocoder ist hinter der einsteckbaren Funktion
  ``suchen(koordinaten_liste) -> liste`` gekapselt; Tests stecken eine
  Attrappe ein.

Eingabe: Vektorzeilen-JSONL (``--eingabe``, Standard
``~/foto_sortierung/personen_vektoren.jsonl``, Vorgabe von gesicht_erkennen.py). Je Zeile ``bild_id`` und optional
``metadaten`` = ``{"aufnahme", "kamera_hersteller", "kamera_modell",
"gps": {"lat", "lon"} | null}``. Zeilen ohne ``metadaten``/GPS werden nur
gezaehlt, nicht verworfen; kaputte JSON-Zeilen werden gezaehlt statt Absturz.

Ausgabe (JSONL, ``ensure_ascii=True``, ``sort_keys=True``; Standard
``~/foto_sortierung/orte.jsonl``), je Bild mit GPS eine Zeile::

    {"abstand_km", "aufnahme", "bild_id", "land", "land_code", "ort",
     "quelle": "offline-geonames", "region", "version": 1}

  ``abstand_km`` ist die Entfernung zur naechsten Stadt (Haversine, auf 1
  Nachkommastelle gerundet). ``land`` kommt aus einer kleinen eingebauten
  Tabelle; fehlt ein Code darin, steht dort der Code selbst.

Aufruf::

    python tools/foto_sortierung/orte_zuordnen.py                # Trockenlauf
    python tools/foto_sortierung/orte_zuordnen.py --schreiben

Als Modul: ``haupt(argv=[...], suchen=attrappe)`` sowie ``orte_zuordnen``.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_EINGABE = os.path.join(STANDARD_BASIS, "personen_vektoren.jsonl")
STANDARD_AUSGABE = os.path.join(STANDARD_BASIS, "orte.jsonl")

QUELLE = "offline-geonames"
VERSION = 1

# Kleine eingebaute Laendertabelle (ISO-3166-1 alpha-2 -> deutscher Name).
LAENDER = {
    "DE": "Deutschland", "AT": "Oesterreich", "CH": "Schweiz", "LI": "Liechtenstein",
    "FR": "Frankreich", "IT": "Italien", "ES": "Spanien", "PT": "Portugal",
    "NL": "Niederlande", "BE": "Belgien", "LU": "Luxemburg", "DK": "Daenemark",
    "SE": "Schweden", "NO": "Norwegen", "FI": "Finnland", "IS": "Island",
    "IE": "Irland", "GB": "Grossbritannien", "PL": "Polen", "CZ": "Tschechien",
    "SK": "Slowakei", "HU": "Ungarn", "SI": "Slowenien", "HR": "Kroatien",
    "BA": "Bosnien und Herzegowina", "RS": "Serbien", "ME": "Montenegro",
    "MK": "Nordmazedonien", "AL": "Albanien", "GR": "Griechenland",
    "BG": "Bulgarien", "RO": "Rumaenien", "MD": "Moldau", "UA": "Ukraine",
    "BY": "Belarus", "LT": "Litauen", "LV": "Lettland", "EE": "Estland",
    "RU": "Russland", "TR": "Tuerkei", "CY": "Zypern", "MT": "Malta",
    "US": "USA", "CA": "Kanada", "MX": "Mexiko", "BR": "Brasilien",
    "AR": "Argentinien", "CL": "Chile", "PE": "Peru", "CO": "Kolumbien",
    "CU": "Kuba", "DO": "Dominikanische Republik", "EG": "Aegypten",
    "MA": "Marokko", "TN": "Tunesien", "ZA": "Suedafrika", "KE": "Kenia",
    "TZ": "Tansania", "IL": "Israel", "JO": "Jordanien", "AE": "Vereinigte Arabische Emirate",
    "IN": "Indien", "TH": "Thailand", "VN": "Vietnam", "ID": "Indonesien",
    "MY": "Malaysia", "SG": "Singapur", "PH": "Philippinen", "CN": "China",
    "HK": "Hongkong", "JP": "Japan", "KR": "Suedkorea", "AU": "Australien",
    "NZ": "Neuseeland", "LK": "Sri Lanka", "MV": "Malediven",
}


# ── Geocoder (einsteckbar) ───────────────────────────────────────────────

def suchen_offline(koordinaten: list) -> list:
    """Stapelweise Rueckwaertssuche ueber ``reverse_geocoder`` (offline).

    ``koordinaten``: Liste von ``(lat, lon)``. Rueckgabe: Liste gleicher Laenge
    mit Woerterbuechern ``{"cc", "admin1", "name", "lat", "lon"}`` (die
    Stadtkoordinate wird nur zur Abstandsberechnung genutzt). ``mode=1``:
    ein Prozess (kein Multiprocessing, unter Windows robust).
    Fehlt das Paket: ``ImportError``.
    """
    import reverse_geocoder  # noqa: PLC0415 — bewusst spaet, Tests laufen ohne
    if not koordinaten:
        return []
    return reverse_geocoder.search(list(koordinaten), mode=1)


# ── Lesen ────────────────────────────────────────────────────────────────

def _zahl(wert):
    """Endliche Gleitkommazahl oder ``None`` (bool/NaN/Text zaehlen nicht)."""
    if isinstance(wert, bool) or not isinstance(wert, (int, float)):
        return None
    wert = float(wert)
    return wert if math.isfinite(wert) else None


def _gps(metadaten) -> tuple | None:
    """``(lat, lon)`` aus den Metadaten, sonst ``None`` (auch ausserhalb des Bereichs)."""
    if not isinstance(metadaten, dict) or not isinstance(metadaten.get("gps"), dict):
        return None
    lat = _zahl(metadaten["gps"].get("lat"))
    lon = _zahl(metadaten["gps"].get("lon"))
    if lat is None or lon is None or not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None
    return (lat, lon)


def eingabe_lesen(pfad: str) -> tuple[list, dict]:
    """Vektorzeilen lesen. Rueckgabe ``(kandidaten, zahlen)``.

    ``kandidaten``: Liste ``{"bild_id", "aufnahme", "gps"}`` der Bilder MIT GPS
    (Reihenfolge der Datei, doppelte ``bild_id`` nur einmal). ``zahlen``:
    ``bilder`` (gueltige Zeilen mit ``bild_id``), ``mit_gps``,
    ``ohne_gps`` (inkl. fehlender ``metadaten``), ``kaputt`` (nicht lesbar oder
    ohne ``bild_id``), ``doppelt``.
    """
    zahlen = {"bilder": 0, "mit_gps": 0, "ohne_gps": 0, "kaputt": 0, "doppelt": 0}
    kandidaten, gesehen = [], set()
    with open(pfad, encoding="utf-8") as datei:
        for zeile in datei:
            if not zeile.strip():
                continue
            try:
                eintrag = json.loads(zeile)
            except ValueError:
                zahlen["kaputt"] += 1
                continue
            bild_id = eintrag.get("bild_id") if isinstance(eintrag, dict) else None
            if not isinstance(bild_id, str) or not bild_id:
                zahlen["kaputt"] += 1
                continue
            if bild_id in gesehen:
                zahlen["doppelt"] += 1
                continue
            gesehen.add(bild_id)
            zahlen["bilder"] += 1
            metadaten = eintrag.get("metadaten")
            gps = _gps(metadaten)
            if gps is None:
                zahlen["ohne_gps"] += 1
                continue
            zahlen["mit_gps"] += 1
            aufnahme = metadaten.get("aufnahme")
            kandidaten.append({"bild_id": bild_id, "gps": gps,
                               "aufnahme": aufnahme if isinstance(aufnahme, str) else None})
    return kandidaten, zahlen


def vorhandene_ids(pfad: str) -> set:
    """``bild_id`` der bereits geschriebenen Ausgabe (fehlende Datei: leer)."""
    ids = set()
    if not os.path.isfile(pfad):
        return ids
    with open(pfad, encoding="utf-8") as datei:
        for zeile in datei:
            try:
                eintrag = json.loads(zeile)
            except ValueError:
                continue
            if isinstance(eintrag, dict) and isinstance(eintrag.get("bild_id"), str):
                ids.add(eintrag["bild_id"])
    return ids


# ── Ableiten ─────────────────────────────────────────────────────────────

def _abstand_km(lat1, lon1, lat2, lon2) -> float:
    """Grosskreisabstand (Haversine) in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(a)))


def ort_zeile(kandidat: dict, treffer: dict) -> dict:
    """Ausgabezeile (ohne Koordinaten) aus Kandidat und Geocoder-Treffer."""
    lat, lon = kandidat["gps"]
    abstand = None
    t_lat, t_lon = _zahl(_als_zahl(treffer.get("lat"))), _zahl(_als_zahl(treffer.get("lon")))
    if t_lat is not None and t_lon is not None:
        abstand = round(_abstand_km(lat, lon, t_lat, t_lon), 1)
    code = str(treffer.get("cc") or "").upper() or None
    return {
        "bild_id": kandidat["bild_id"],
        "aufnahme": kandidat["aufnahme"],
        "land_code": code,
        "land": LAENDER.get(code, code) if code else None,
        "region": treffer.get("admin1") or None,
        "ort": treffer.get("name") or None,
        "abstand_km": abstand,
        "quelle": QUELLE,
        "version": VERSION,
    }


def _als_zahl(wert):
    """Zahl oder Text-Zahl (reverse_geocoder liefert Strings) als float, sonst ``None``."""
    if isinstance(wert, str):
        try:
            return float(wert)
        except ValueError:
            return None
    return wert


def orte_zuordnen(eingabe: str, ausgabe: str, schreiben: bool = False,
                  suchen=None) -> dict:
    """Bilder mit GPS in Orte uebersetzen; im Trockenlauf nur zaehlen.

    Rueckgabe: Zahlenblock ``bilder``, ``mit_gps``, ``ohne_gps``, ``kaputt``,
    ``doppelt``, ``bereits_vorhanden``, ``neu``, ``zugeordnet`` (mit Land),
    ``laender`` (Anzahl), ``top_laender`` (Liste ``(land, anzahl)``, nur
    neu berechnete Zeilen). ``suchen`` ersetzt den Geocoder (Tests).
    """
    ausgabe = _pruefe_ziel_ausserhalb_repo(ausgabe)
    kandidaten, zahlen = eingabe_lesen(eingabe)
    schon = vorhandene_ids(ausgabe)
    neu = [k for k in kandidaten if k["bild_id"] not in schon]
    zahlen["bereits_vorhanden"] = len(kandidaten) - len(neu)
    zahlen["neu"] = len(neu)
    zahlen.update(zugeordnet=0, laender=0, top_laender=[])
    if not schreiben or not neu:
        return zahlen

    treffer = (suchen or suchen_offline)([k["gps"] for k in neu])
    if len(treffer) != len(neu):
        raise RuntimeError("Der Geocoder lieferte eine andere Trefferzahl als angefragt.")
    zeilen = [ort_zeile(k, t) for k, t in zip(neu, treffer)]
    zaehler = Counter(z["land"] for z in zeilen if z["land"])
    zahlen["zugeordnet"] = sum(zaehler.values())
    zahlen["laender"] = len(zaehler)
    zahlen["top_laender"] = zaehler.most_common(10)

    os.makedirs(os.path.dirname(os.path.abspath(ausgabe)), exist_ok=True)
    with open(ausgabe, "a", encoding="utf-8", newline="\n") as datei:
        for z in zeilen:
            datei.write(json.dumps(z, ensure_ascii=True, sort_keys=True) + "\n")
    return zahlen


def _pruefe_ziel_ausserhalb_repo(pfad: str) -> str:
    """Zieldatei muss AUSSERHALB des Repos liegen, sonst ``ValueError``."""
    if not isinstance(pfad, str) or not pfad.strip():
        raise ValueError("Kein Zielpfad fuer die Orte angegeben.")
    ziel = os.path.normcase(os.path.abspath(pfad))
    repo = os.path.normcase(os.path.abspath(REPO))
    try:
        gemeinsam = os.path.commonpath([ziel, repo])
    except ValueError:                        # anderes Laufwerk: nie im Repo
        return pfad
    if gemeinsam == repo:
        raise ValueError(
            f"Zieldatei liegt IM Repo und ist nicht erlaubt: {pfad}\n"
            f"Die Orte gehoeren ausserhalb des Repos (Standard: {STANDARD_AUSGABE}).")
    return pfad


# ── Kommandozeile ────────────────────────────────────────────────────────

def haupt(argv=None, suchen=None) -> int:
    zerleger = argparse.ArgumentParser(
        description="Orte je Bild aus GPS-Metadaten, offline (Trockenlauf ist Standard).")
    zerleger.add_argument("--eingabe", default=STANDARD_EINGABE,
                          help="Vektorzeilen-JSONL von gesicht_erkennen.py")
    zerleger.add_argument("--ausgabe", default=STANDARD_AUSGABE,
                          help="Orte-JSONL (ausserhalb des Repos)")
    gruppe = zerleger.add_mutually_exclusive_group()
    gruppe.add_argument("--trocken", action="store_true", help="nur zaehlen (Standard)")
    gruppe.add_argument("--schreiben", action="store_true", help="Ausgabe anhaengen")
    args = zerleger.parse_args(argv)

    try:
        _pruefe_ziel_ausserhalb_repo(args.ausgabe)
    except ValueError as fehler:
        print(f"FEHLER: {fehler}", file=sys.stderr)
        raise SystemExit(2)
    if not os.path.isfile(args.eingabe):
        print(f"FEHLER: Eingabedatei nicht gefunden: {args.eingabe}", file=sys.stderr)
        raise SystemExit(2)
    if args.schreiben and suchen is None:
        try:
            import reverse_geocoder  # noqa: F401, PLC0415
        except ImportError:
            print("FEHLER: Das Paket 'reverse_geocoder' fehlt (Offline-Geocoding).\n"
                  "Installieren: backend/.venv/Scripts/python -m pip install "
                  "reverse_geocoder", file=sys.stderr)
            raise SystemExit(2)

    z = orte_zuordnen(args.eingabe, args.ausgabe, schreiben=args.schreiben, suchen=suchen)
    print(f"Modus:               {'SCHREIBEN' if args.schreiben else 'Trockenlauf'}")
    print(f"Bilder gesamt:       {z['bilder']}")
    print(f"mit GPS:             {z['mit_gps']}")
    print(f"ohne GPS/Metadaten:  {z['ohne_gps']}")
    print(f"kaputte Zeilen:      {z['kaputt']}")
    print(f"bereits vorhanden:   {z['bereits_vorhanden']}")
    print(f"neu zu berechnen:    {z['neu']}")
    if args.schreiben:
        print(f"zugeordnet:          {z['zugeordnet']}")
        print(f"Anzahl Laender:      {z['laender']}")
        for land, anzahl in z["top_laender"]:
            print(f"  {land}: {anzahl}")
    else:
        print("Trockenlauf: es wurde nichts geschrieben (--schreiben zum Schreiben).")
    return 0


if __name__ == "__main__":
    raise SystemExit(haupt())
