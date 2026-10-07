"""Orte aus OpenStreetMap-Karten — Adressen und Landmarken, offline ausgewertet.

Wozu dieses Werkzeug:
  ``orte_zuordnen.py`` liefert aus GPS-Daten nur Land/Region/Stadt (GeoNames,
  Nachbarort). Fuer „welche Bilder sind wo entstanden" reicht das nicht:
  Sebastian will **Strassen mit Hausnummer** („Lauenburger Strasse 41"), und
  Landmarken („Nationalpark Plitvicer Seen", „Restaurant", „Fluss", „Berg").
  Diese Angaben stehen in den OpenStreetMap-Karten, nicht bei GeoNames.

  Das Werkzeug hat zwei Betriebsarten:
  1. **Karten auswerten** (``--karte <osm.pbf>``, mehrfach): liest die Karten
     (Geofabrik-Ausschnitte) und schreibt zwei Tabellen als CSV —
     Adressen und benannte Orte (Landmarken). Rein lesend, kein Netz.

     **Standard seit 07.10.2026: nur Orte rund um die Fotos, keine Adressen.**
     Sebastian: „Brauche nicht alle Adressen … Das ist doch crazy." Ganze
     Gebiete als Adresstabellen (Hamburg allein 293.330 Adressen) sind weder
     nötig noch gewollt. Behalten wird ein benannter Ort nur, wenn ein Foto
     (GPS aus ``--vektoren``) in der Nähe liegt — je Art ein eigener Umkreis
     (``UMKREIS_KM``: Restaurant/Sehenswürdigkeit 300 m, Wald/See/Berg 2 km,
     Ortschaft 5 km; Luftlinie). Hausnummern nur mit
     ``--mit-adressen`` (dann ebenfalls nur ~100 m um Fotos). ``--alle`` stellt
     die frühere Vollauswertung wieder her.
     Private Orte (Großeltern, Freunde, Nachbarn) stehen in keiner Karte —
     die kommen von Sebastian: ``~/foto_sortierung/eigene_orte.json`` (siehe
     ``eigene_orte_lesen``), beim Zuordnen mit Vorrang vor der Karte.
  2. **Bilder zuordnen** (``--zuordnen``): liest die Tabellen und die GPS-Daten
     der Bilder, sucht zu jedem Punkt die naechste Adresse und die naechsten
     benannten Orte (je Art der naechste) und schreibt ``bild_orte.csv`` —
     **eine Zeile je Bild**. Ohne GPS bleibt das Bild mit leeren Feldern drin
     (ehrlich statt weggelassen).

Datenschutz (Regeln des Auftrags, hier als Code):
  * **Kein Netz**: die Karten liegen lokal, es wird nichts gesendet.
  * **Keine Koordinaten in Berichten**: die Konsolenausgabe zeigt nur Zahlen
    und Landesnamen. Koordinaten stehen ausschliesslich in den lokalen
    CSV-Dateien AUSSERHALB des Repos (dort sind sie zum Nachschlagen noetig).
  * **Keine Bilder** werden geoeffnet, kopiert oder gespeichert.
  * **Kein Schreiben ohne ``--schreiben``**; ohne den Schalter wird nur
    gezaehlt. Ziele im Repo werden verweigert (``SystemExit(2)``).

Aufruf:
    cd backend && .venv/Scripts/python ../tools/foto_sortierung/orte_aus_karte.py \
        --karte ~/foto_sortierung/osm/schleswig-holstein-latest.osm.pbf \
        --vektoren ~/foto_sortierung/personen_vektoren_n0929_bildervideos.jsonl \
                   ~/foto_sortierung/personen_vektoren_n0929_voll.jsonl \
        --schreiben
    ... --zuordnen --vektoren ~/foto_sortierung/personen_vektoren_n0929_bildervideos.jsonl \
        --schreiben
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))
STANDARD_ORDNER = os.path.join(os.path.expanduser("~"), "foto_sortierung", "osm", "csv")
ADRESS_SPALTEN = ["breite", "laenge", "strasse", "hausnummer", "ort", "region"]
ORT_SPALTEN = ["breite", "laenge", "art", "name", "zusatz"]
BILD_SPALTEN = ["fileid", "aufnahme", "adresse", "hausnummer", "ort_osm", "landmarke",
                "landmarke_art", "hinweise", "abstand_m"]

# Was aus den Karten geholt wird: (Art, Schluessel, Werte). Mehrere Zeilen mit
# derselben Art sind ausdruecklich erlaubt (Wald steht z. B. unter natural UND
# landuse) — als dict wuerde die zweite Zeile die erste stillschweigend
# ueberschreiben.
REGELN = (
    ("restaurant", "amenity", {"restaurant", "cafe", "bar", "pub", "fast_food",
                               "biergarten", "ice_cream"}),
    ("berg", "natural", {"peak", "ridge", "cliff", "saddle"}),
    ("wasser", "natural", {"water", "bay", "beach", "wetland"}),
    ("fluss", "waterway", {"river", "stream", "canal", "riverbank"}),
    ("wald", "natural", {"wood", "scrub"}),
    ("wald", "landuse", {"forest"}),
    ("schutzgebiet", "leisure", {"nature_reserve", "park", "garden"}),
    ("schutzgebiet", "boundary", {"protected_area", "national_park"}),
    ("sehenswuerdigkeit", "tourism", {"attraction", "viewpoint", "museum", "artwork",
                                      "zoo", "theme_park", "gallery"}),
    ("historisch", "historic", {"castle", "monument", "memorial", "ruins", "church",
                                "manor", "archaeological_site"}),
    ("sport", "leisure", {"sports_centre", "pitch", "swimming_pool", "water_park",
                          "dog_park", "stadium"}),
    ("laden", "shop", {"supermarket", "bakery", "convenience", "mall",
                       "department_store", "butcher"}),
    ("kirche", "amenity", {"place_of_worship"}),
    ("haltestelle", "highway", {"bus_stop"}),
    ("bahnhof", "railway", {"station", "halt"}),
    ("flughafen", "aeroway", {"aerodrome", "terminal"}),
)
LANDSCHAFT = ("restaurant", "berg", "wasser", "fluss", "wald", "schutzgebiet",
              "sehenswuerdigkeit", "historisch", "kirche", "sport", "laden",
              "bahnhof", "flughafen", "haltestelle")
ORTE = {"city", "town", "village", "hamlet", "suburb", "neighbourhood", "locality"}
ZELLE = 0.005

# Umkreis je Art um die Fotos (km). Punkte (Restaurant, Museum) muessen nah
# sein, Flaechen (Wald, See, Nationalpark) haben ihren Mittelpunkt oft weit weg,
# Ortschaften noch weiter.
UMKREIS_PUNKT_KM = 0.3
UMKREIS_FLAECHE_KM = 2.0
UMKREIS_ORT_KM = 5.0
UMKREIS_ADRESSE_KM = 0.1
FLAECHEN = ("berg", "wasser", "fluss", "wald", "schutzgebiet", "flughafen")
UMKREIS_KM = {art: (UMKREIS_FLAECHE_KM if art in FLAECHEN else UMKREIS_PUNKT_KM) for art in LANDSCHAFT}
UMKREIS_KM["ort"] = UMKREIS_ORT_KM
STANDARD_VEKTOREN = [os.path.join(os.path.expanduser("~"), "foto_sortierung", n) for n in (
    "personen_vektoren_n0929_bildervideos.jsonl", "personen_vektoren_n0929_voll.jsonl")]
STANDARD_EIGENE_ORTE = os.path.join(os.path.expanduser("~"), "foto_sortierung", "eigene_orte.json")
EIGENER_ORT_RADIUS_M = 100


class FotoNaehe:
    """Liegt ein Kartenpunkt hoechstens ``r`` km (Luftlinie) von einem Foto entfernt?

    Je Umkreis ein Raster mit Zellen von mindestens ``r`` km Kantenlaenge
    (mindestens ``ZELLE``); geprueft werden nur die Fotos der Nachbarzellen,
    dort aber genau. Fotos an praktisch derselben Stelle (4 Nachkommastellen,
    ~11 m) zaehlen einmal — so bleibt die Pruefung auch am Wohnort mit
    Tausenden Fotos schnell.
    """

    def __init__(self, punkte, radien_km):
        eindeutig = {(round(lat, 4), round(lon, 4)) for lat, lon in punkte}
        self.punkte = len(eindeutig)
        self.raster = {}
        for radius in sorted(set(radien_km)):
            zelle = max(ZELLE, radius / 111.0)
            felder = collections.defaultdict(list)
            for lat, lon in eindeutig:
                felder[(int(math.floor(lat / zelle)), int(math.floor(lon / zelle)))].append((lat, lon))
            self.raster[radius] = (zelle, felder)

    def nah(self, lat: float, lon: float, radius_km: float) -> bool:
        zelle, felder = self.raster[radius_km]
        zi, zj = int(math.floor(lat / zelle)), int(math.floor(lon / zelle))
        km_lon = 111.0 * math.cos(math.radians(lat))
        ring_lon = int(math.ceil(1 / max(0.2, math.cos(math.radians(lat)))))
        for i in range(zi - 1, zi + 2):
            for j in range(zj - ring_lon, zj + ring_lon + 1):
                for plat, plon in felder.get((i, j), ()):
                    if math.hypot((plat - lat) * 111.0, (plon - lon) * km_lon) <= radius_km:
                        return True
        return False


def _pruefe_ziel_ausserhalb_repo(pfad: str) -> str:
    """Zieldatei muss AUSSERHALB des Repos liegen (sonst SystemExit(2))."""
    if not isinstance(pfad, str) or not pfad.strip():
        raise ValueError("Kein Zielpfad angegeben.")
    ziel = os.path.normcase(os.path.abspath(pfad))
    repo = os.path.normcase(os.path.abspath(REPO))
    try:
        gemeinsam = os.path.commonpath([ziel, repo])
    except ValueError:                       # anderes Laufwerk: nie im Repo
        return pfad
    if gemeinsam == repo:
        print(f"Zieldatei liegt IM Repo und ist nicht erlaubt: {pfad}", flush=True)
        raise SystemExit(2)
    return pfad


def _zelle(lat: float, lon: float):
    return (int(math.floor(lat / ZELLE)), int(math.floor(lon / ZELLE)))


def _name(tags, feld: str = "name") -> str:
    return (tags.get(feld) or tags.get("name:de") or tags.get("name:en")
            or tags.get("short_name") or "").strip()


def _klassen(tags) -> list[str]:
    treffer = []
    for art, schluessel, werte in REGELN:
        if tags.get(schluessel) in werte and art not in treffer:
            treffer.append(art)
    return treffer


def sammle_karte(pfad: str, mit_wegen: bool = True, fotos: "FotoNaehe | None" = None,
                 mit_adressen: bool = True) -> tuple:
    """Kartendatei lesen -> (adressen, orte). Nur lesend, ohne Netz.

    ``adressen``: (lat, lon, strasse, hausnummer, ort)
    ``orte``:     (lat, lon, art, name, zusatz)

    Mit ``fotos`` bleibt nur, was in der Naehe eines Fotos liegt (je Art
    ``UMKREIS_KM``); weiter weg Liegendes zaehlt als ``ausser_umkreis``.
    ``mit_adressen=False`` laesst Hausnummern ganz weg.
    """
    import osmium

    adressen, orte = [], []
    zaehler = collections.Counter()

    class Sammler(osmium.SimpleHandler):
        def _nimm(self, lat, lon, art, name, zusatz=""):
            if not name:
                return
            if fotos is not None and not fotos.nah(lat, lon, UMKREIS_KM.get(art, UMKREIS_PUNKT_KM)):
                zaehler["ausser_umkreis"] += 1
                return
            orte.append((lat, lon, art, name, zusatz))
            zaehler[art] += 1

        def _adresse(self, lat, lon, tags, mitte=False):
            nummer, strasse = tags.get("addr:housenumber"), tags.get("addr:street")
            if not nummer or not strasse or not mit_adressen:
                return
            if fotos is not None and not fotos.nah(lat, lon, UMKREIS_ADRESSE_KM):
                zaehler["ausser_umkreis"] += 1
                return
            stadt = (tags.get("addr:city") or tags.get("addr:suburb")
                     or tags.get("addr:village") or "")
            adressen.append((lat, lon, strasse, nummer, stadt))
            zaehler["adresse"] += 1

        def node(self, n):
            t = n.tags
            if not n.location.valid():
                return
            lat, lon = n.location.lat, n.location.lon
            for art in _klassen(t):
                self._nimm(lat, lon, art, _name(t))
            if t.get("place") in ORTE:
                self._nimm(lat, lon, "ort", _name(t), t.get("place") or "")
            self._adresse(lat, lon, t)

        def way(self, w):
            t = w.tags
            arten = _klassen(t)
            hat_adresse = bool(t.get("addr:housenumber") and t.get("addr:street")) and mit_adressen
            if not arten and (not hat_adresse or not mit_wegen):
                return
            try:
                punkte = [(k.lat, k.lon) for k in w.nodes]
            except Exception:
                return
            if not punkte:
                return
            lat = sum(p[0] for p in punkte) / len(punkte)
            lon = sum(p[1] for p in punkte) / len(punkte)
            for art in arten:
                self._nimm(lat, lon, art, _name(t))
            self._adresse(lat, lon, t, mitte=True)

    sammler = Sammler()
    sammler.apply_file(pfad, locations=True)
    return adressen, orte, zaehler


def csv_schreiben(pfad: str, spalten: list, zeilen: list) -> str:
    _pruefe_ziel_ausserhalb_repo(pfad)
    os.makedirs(os.path.dirname(os.path.abspath(pfad)), exist_ok=True)
    with open(pfad, "w", newline="", encoding="utf-8") as datei:
        schreiber = csv.writer(datei)
        schreiber.writerow(spalten)
        schreiber.writerows(zeilen)
    return pfad


def csv_lesen(pfad: str) -> list:
    with open(pfad, newline="", encoding="utf-8") as datei:
        return list(csv.DictReader(datei))


def index_bauen(orte: list) -> dict:
    """Gitter-Index {(zi, zj): [(lat, lon, art, name, zusatz), ...]}."""
    index = collections.defaultdict(list)
    for lat, lon, art, name, zusatz in orte:
        index[_zelle(lat, lon)].append((lat, lon, art, name, zusatz))
    return index


def nachbar(index: dict, lat: float, lon: float, art: str | None = None,
            max_km: float = 2.0, ringe: int = 6):
    """Naechster Punkt (der Art) im Umkreis. Rueckgabe (km, art, name, zusatz) oder None."""
    zi, zj = _zelle(lat, lon)
    bester = None
    for ring in range(0, ringe + 1):
        for i in range(zi - ring, zi + ring + 1):
            for j in range(zj - ring, zj + ring + 1):
                for (plat, plon, part, pname, pz) in index.get((i, j), ()):
                    if art and part != art:
                        continue
                    d = math.hypot((plat - lat) * 111.0,
                                   (plon - lon) * 111.0 * math.cos(math.radians(lat)))
                    if d <= max_km and (bester is None or d < bester[0]):
                        bester = (d, part, pname, pz)
        if bester is not None:
            break
    return bester


def gps_aus_vektoren(pfad: str) -> dict:
    """{fileid: (lat, lon, aufnahme)} aus einer Vektorzeilen-Datei."""
    punkte = {}
    with open(pfad, encoding="utf-8") as datei:
        for zeile in datei:
            try:
                e = json.loads(zeile)
            except ValueError:
                continue
            g = (e.get("metadaten") or {}).get("gps") or {}
            lat, lon = g.get("lat"), g.get("lon")
            if lat is None or lon is None:
                punkte[str(e.get("bild_id"))] = (None, None,
                                                 (e.get("metadaten") or {}).get("aufnahme"))
                continue
            punkte[str(e.get("bild_id"))] = (float(lat), float(lon),
                                             (e.get("metadaten") or {}).get("aufnahme"))
    return punkte


def gps_aus_dateien(pfade) -> dict:
    """Wie ``gps_aus_vektoren``, ueber mehrere Dateien (fehlende werden uebersprungen)."""
    punkte = {}
    for pfad in pfade or []:
        if pfad and os.path.isfile(pfad):
            punkte.update(gps_aus_vektoren(pfad))
    return punkte


def eigene_orte_lesen(pfad: str) -> list:
    """Sebastians eigene Orte (Großeltern, Freunde, Nachbarn — stehen in keiner Karte).

    Datei ``eigene_orte.json`` (ausserhalb des Repos)::

        [{"name": "bei Oma", "lat": 53.7, "lon": 10.7, "radius_m": 100}, ...]

    ``radius_m`` ist optional (Standard 100). Kaputte Eintraege werden
    uebersprungen; fehlt die Datei, gibt es keine eigenen Orte. Wirft nie.
    """
    if not pfad or not os.path.isfile(pfad):
        return []
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except (OSError, ValueError):
        return []
    eintraege = daten.get("orte") if isinstance(daten, dict) else daten
    orte = []
    for e in eintraege if isinstance(eintraege, list) else []:
        if not isinstance(e, dict):
            continue
        name = str(e.get("name") or "").strip()
        try:
            lat, lon = float(e.get("lat")), float(e.get("lon"))
            radius = float(e.get("radius_m") or EIGENER_ORT_RADIUS_M)
        except (TypeError, ValueError):
            continue
        if name and -90 <= lat <= 90 and -180 <= lon <= 180 and radius > 0:
            orte.append((lat, lon, name, radius))
    return orte


def eigener_ort(orte: list, lat: float, lon: float):
    """Naechster eigener Ort, in dessen Radius der Punkt liegt: ``(name, abstand_m)`` oder ``None``."""
    bester = None
    for olat, olon, name, radius in orte:
        d = math.hypot((olat - lat) * 111000.0, (olon - lon) * 111000.0 * math.cos(math.radians(lat)))
        if d <= radius and (bester is None or d < bester[1]):
            bester = (name, d)
    return bester


def main(argv=None) -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--karte", action="append", default=[],
                          help="Kartendatei (.osm.pbf oder .osm), mehrfach moeglich")
    zerleger.add_argument("--zuordnen", action="store_true",
                          help="Bilder den Adressen/Orten zuordnen (zweite Betriebsart)")
    zerleger.add_argument("--zusammenfassen", action="store_true",
                          help="Einzel-Tabellen je Gebiet zur Gesamttabelle verbinden")
    zerleger.add_argument("--ordner", default=STANDARD_ORDNER,
                          help="Zielordner fuer die Tabellen")
    zerleger.add_argument("--vektoren", nargs="+", default=STANDARD_VEKTOREN,
                          help="Vektordateien mit GPS je Foto (Umkreis beim Auswerten, Punkte beim Zuordnen)")
    zerleger.add_argument("--alle", action="store_true",
                          help="frühere Vollauswertung: alle Orte und Adressen der Karte, ohne Foto-Umkreis")
    zerleger.add_argument("--mit-adressen", action="store_true",
                          help="Hausnummern mitnehmen (nur ~100 m um Fotos)")
    zerleger.add_argument("--eigene-orte", default=STANDARD_EIGENE_ORTE,
                          help="eigene Orte (JSON), beim Zuordnen mit Vorrang vor der Karte")
    zerleger.add_argument("--bild-orte", default=os.path.join(
        os.path.expanduser("~"), "foto_sortierung", "bild_orte.csv"))
    zerleger.add_argument("--max-km", type=float, default=2.0)
    gruppe = zerleger.add_mutually_exclusive_group()
    gruppe.add_argument("--trocken", action="store_true", help="nur zaehlen (Standard)")
    gruppe.add_argument("--schreiben", action="store_true", help="Tabellen schreiben")
    args = zerleger.parse_args(argv)

    if args.zusammenfassen:
        # Je Gebiet liegt eine eigene Tabelle im Unterordner (<gebiet>/osm_*.csv).
        # Sie werden hier zu EINER Gesamttabelle verbunden — wiederholbar: das
        # Ergebnis wird immer neu aus den Einzeltabellen gebaut.
        unter = sorted(d for d in os.listdir(args.ordner)
                       if os.path.isdir(os.path.join(args.ordner, d)))
        if not unter:
            print(f"Keine Gebiets-Ordner in {args.ordner} gefunden.", flush=True)
            return 2
        adr_zeilen, ort_zeilen = [], []
        for gebiet in unter:
            a = os.path.join(args.ordner, gebiet, "osm_adressen.csv")
            o = os.path.join(args.ordner, gebiet, "osm_orte.csv")
            if not (os.path.exists(a) and os.path.exists(o)):
                print(f"   fehlt (uebersprungen): {gebiet}", flush=True)
                continue
            adr_zeilen.extend([[z[s] for s in ADRESS_SPALTEN] for z in csv_lesen(a)])
            ort_zeilen.extend([[z[s] for s in ORT_SPALTEN] for z in csv_lesen(o)])
            print(f"   {gebiet:24s} {len(adr_zeilen):9d} Adressen  {len(ort_zeilen):9d} Orte",
                  flush=True)
        print(f"Gebiete: {len(unter)} | Adressen: {len(adr_zeilen)} | Orte: {len(ort_zeilen)}",
              flush=True)
        if not args.schreiben:
            print("Trockenlauf: nichts geschrieben (--schreiben zum Schreiben).", flush=True)
            return 0
        print("geschrieben: " + csv_schreiben(os.path.join(args.ordner, "osm_adressen.csv"),
                                             ADRESS_SPALTEN, adr_zeilen), flush=True)
        print("geschrieben: " + csv_schreiben(os.path.join(args.ordner, "osm_orte.csv"),
                                             ORT_SPALTEN, ort_zeilen), flush=True)
        return 0

    if args.zuordnen:
        adr_pfad = os.path.join(args.ordner, "osm_adressen.csv")
        ort_pfad = os.path.join(args.ordner, "osm_orte.csv")
        if not (os.path.exists(adr_pfad) and os.path.exists(ort_pfad)):
            print(f"Tabellen fehlen: {adr_pfad} / {ort_pfad} — erst Karten auswerten.",
                  flush=True)
            return 2
        adressen = [(float(a["breite"]), float(a["laenge"]), a["strasse"],
                     a["hausnummer"], a.get("ort") or "") for a in csv_lesen(adr_pfad)]
        orte = [(float(o["breite"]), float(o["laenge"]), o["art"], o["name"],
                 o.get("zusatz") or "") for o in csv_lesen(ort_pfad)]
        print(f"Tabellen: {len(adressen)} Adressen, {len(orte)} Orte", flush=True)
        o_index = index_bauen(orte)
        a_index = index_bauen([(b, l, "adresse", f"{s}|{h}|{st}", "")
                               for (b, l, s, h, st) in adressen])
        punkte = gps_aus_dateien(args.vektoren)
        mit_gps = sum(1 for v in punkte.values() if v[0] is not None)
        eigene = eigene_orte_lesen(args.eigene_orte)
        print(f"Bilder: {len(punkte)} | mit GPS: {mit_gps} | eigene Orte: {len(eigene)}", flush=True)
        if not args.schreiben:
            print("Trockenlauf: nichts geschrieben (--schreiben zum Schreiben).", flush=True)
            return 0
        zeilen = []
        for fileid, (lat, lon, aufnahme) in punkte.items():
            if lat is None:
                zeilen.append([fileid, aufnahme or "", "", "", "", "", "", "ohne GPS", ""])
                continue
            adr = nachbar(a_index, lat, lon, "adresse", args.max_km)
            ort = nachbar(o_index, lat, lon, "ort", max(3.0, args.max_km))
            fund = []
            for art in LANDSCHAFT:
                t = nachbar(o_index, lat, lon, art, args.max_km)
                if t:
                    fund.append((t[1], t[2], t[0]))
            naechste = min(fund, key=lambda x: x[2]) if fund else None
            privat = eigener_ort(eigene, lat, lon)
            if privat:                       # Sebastians eigener Ort gewinnt vor der Karte
                naechste = ("eigener_ort", privat[0], privat[1] / 1000.0)
            strasse = hausnummer = ""
            if adr:
                teile = adr[2].split("|")
                strasse = teile[0]
                hausnummer = teile[1] if len(teile) > 1 else ""
            zeilen.append([fileid, aufnahme or "", strasse, hausnummer,
                           (ort[2] if ort else ""),
                           naechste[1] if naechste else "",
                           naechste[0] if naechste else "",
                           ";".join(f"{a}:{n}|{d:.2f}" for a, n, d in fund),
                           f"{naechste[2] * 1000:.0f}" if naechste else ""])
        csv_schreiben(args.bild_orte, BILD_SPALTEN, zeilen)
        print(f"geschrieben: {args.bild_orte} ({len(zeilen)} Zeilen)", flush=True)
        return 0

    if not args.karte:
        print("Bitte --karte <datei> angeben (oder --zuordnen).", flush=True)
        return 2
    fotos = None
    if not args.alle:
        punkte = [(v[0], v[1]) for v in gps_aus_dateien(args.vektoren).values() if v[0] is not None]
        if not punkte:
            print("Keine Fotos mit GPS gefunden (--vektoren). Ohne Fotos kein Umkreis - "
                  "--alle wertet die ganze Karte aus.", flush=True)
            return 2
        fotos = FotoNaehe(punkte, list(UMKREIS_KM.values()) + [UMKREIS_ADRESSE_KM])
        print(f"Umkreis um {len(punkte)} Fotos mit GPS | Adressen: "
              f"{'nur nah an Fotos' if args.mit_adressen else 'keine'}", flush=True)
    mit_adressen = args.alle or args.mit_adressen
    alle_adr, alle_ort, zahlen = [], [], collections.Counter()
    for karte in args.karte:
        print(f"=== {os.path.basename(karte)} ===", flush=True)
        adr, orte, z = sammle_karte(karte, fotos=fotos, mit_adressen=mit_adressen)
        print(f"   Adressen: {z.get('adresse', 0)} | Orte: "
              f"{sum(v for k, v in z.items() if k not in ('adresse', 'ausser_umkreis'))}"
              f" | außer Umkreis verworfen: {z.get('ausser_umkreis', 0)}", flush=True)
        for art, n in sorted(z.items()):
            if art not in ("adresse", "ausser_umkreis"):
                print(f"      {art:20s} {n:8d}", flush=True)
        alle_adr.extend(adr)
        alle_ort.extend(orte)
        zahlen.update(z)
    print(f"\nGesamt: {len(alle_adr)} Adressen, {len(alle_ort)} Orte", flush=True)
    if not args.schreiben:
        print("Trockenlauf: nichts geschrieben (--schreiben zum Schreiben).", flush=True)
        return 0
    a = csv_schreiben(os.path.join(args.ordner, "osm_adressen.csv"), ADRESS_SPALTEN,
                      [[f"{b:.6f}", f"{l:.6f}", s, h, st, ""] for (b, l, s, h, st) in alle_adr])
    o = csv_schreiben(os.path.join(args.ordner, "osm_orte.csv"), ORT_SPALTEN,
                      [[f"{b:.6f}", f"{l:.6f}", art, name, z] for (b, l, art, name, z) in alle_ort])
    print(f"geschrieben: {a}\ngeschrieben: {o}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
