"""Gesichter aus Videos (Schritt E14b, 29.09.2026).

Wozu dieses Werkzeug:
  ``gesicht_erkennen.py`` (N9b) erkennt Gesichter in **Fotos**. Dieses Werkzeug
  macht dasselbe fuer **Videos** aus pCloud: aus jedem Video werden in festem
  Abstand Einzelbilder (Frames) entnommen, jeder Frame geht an dasselbe
  Gesichtsmodell (YuNet + SFace), und je Frame **mit mindestens einem Gesicht**
  entsteht eine Vektorzeile im **gleichen Format** wie bei den Fotos — so liest
  ``personen_cluster.py`` (N9a) sie direkt::

      {"bild_id": "<fileid>#t=<sekunden>", "video_id": "<fileid>",
       "zeit_s": 12.0, "breite": 1920, "hoehe": 1080,
       "gesichter": [{"bbox", "score", "embedding"}, ...],
       "metadaten": {"aufnahme": None, "kamera_hersteller": None,
                     "kamera_modell": None, "gps": None}}

  ``bild_id`` ist die Kennung des Frames (Video-``fileid``, ``#t=`` und die
  Sekunde mit einer Nachkommastelle); ``video_id`` fuehrt zurueck zum Video,
  ``zeit_s`` ist der Zeitpunkt. ``personen_cluster.zeile_pruefen`` ignoriert
  die beiden Zusatzfelder (es baut sein Ergebnis aus den bekannten Feldern).

Metadaten bei Videos:
  ``metadaten`` traegt dieselben Felder wie bei Fotos, aber **alle ``None``**.
  Das Aufnahmedatum steckt bei Videos im Container (MP4/MOV-Atome) und ist mit
  ``cv2.VideoCapture`` nicht lesbar; ``ffprobe`` wird bewusst **nicht**
  vorausgesetzt. Aufnahmedatum und Ort kommen stattdessen aus dem Plan bzw.
  den Dateidaten (Jahr) — die Felder bleiben ehrlich ``None`` statt geraten.

Eingabe:
  Der Sortierplan (``--plan``, wie bei ``gesicht_erkennen``). Gelesen werden
  ``zuege[].fileid``, ``zuege[].jahr`` und der Dateiname ``zuege[].von_name``
  (Ersatz: ``name``/``datei``); **nur** Eintraege mit Video-Endung (mp4, mov,
  3gp, mkv, avi, m4v — Gross/klein egal) werden verarbeitet. ``plan_lesen`` der
  Fotos reicht den Namen nicht durch, deshalb liest ``video_plan_lesen`` ihn
  selbst; Dateinamen werden nie ausgegeben, nur Zahlen.

Was dieses Werkzeug bewusst NICHT tut:
  * **Keine Bilder speichern.** Frames werden in-memory als JPEG-Bytes an das
    Modell gegeben. **Einzige Ausnahme vom „keine Bilder schreiben“-Grundsatz:**
    ``cv2.VideoCapture`` braucht einen **Dateipfad**, kein Byte-Objekt. Das
    Video wird deshalb **fluechtig** in eine Temp-Datei im System-Temp
    geschrieben (``tempfile.NamedTemporaryFile(delete=False)``) und im
    ``finally`` **immer** wieder entfernt — auch bei Fehlern. Es ist die
    einzige Loeschung dieses Moduls und betrifft nur die selbst angelegte
    Temp-Datei. Nie im Repo, nie dauerhaft.
  * **Kein Schreiben ins Repo.** Ziel nur ausserhalb des Repos (gleiche Pruefung
    ``personen_cluster.pruefe_ausserhalb_repo``); Repo-Pfad ergibt Exit 2.
  * **Keine Geheimnisse, keine Namen, keine Pfade in der Ausgabe.** Die Konsole
    zeigt nur Zaehler.

Frames:
  Alle ``--abstand-s`` Sekunden (Standard 2,0) ein Frame, hoechstens
  ``--max-frames`` (Standard 60) je Video; ist das Video laenger, werden die
  Frames gleichmaessig ueber die ganze Laenge verteilt (``zeitpunkte_rechnen``).
  ``cv2`` wird erst in ``frames_entnehmen`` geladen (lazy) — das Modul ist ohne
  OpenCV importierbar; die Tests stecken eine Attrappe ein.

Fortsetzen:
  Es gibt **keine** Abschlusszeile je Video. ``--fortsetzen`` sammelt die
  ``video_id``s der vorhandenen Vektordatei und die Kennungen der kleinen
  Fortschrittsdatei ``<vektoren>.videos_fertig`` (eine ``fileid`` je Zeile,
  anhaengen + flush) und ueberspringt diese Videos. Damit gelten auch Videos
  **ohne** erkanntes Gesicht als erledigt. Ein Video wird erst **nach**
  vollstaendiger Verarbeitung als fertig vermerkt; Fehler und ``zu_gross``
  bleiben offen (ein spaeterer Lauf versucht sie erneut, z. B. mit hoeherem
  ``--max-mb``). Jede Zeile wird sofort geflusht.

Aufruf — Standard ist der Trockenlauf (zaehlt nur die Videos je Jahr)::

    .venv/Scripts/python.exe tools/foto_sortierung/video_gesichter.py \
        --plan ~/foto_sortierung/sortierplan.json

    # wirklich rechnen (Gesichter-venv mit cv2 + onnxruntime!)
    .venv/Scripts/python.exe tools/foto_sortierung/video_gesichter.py \
        --plan ~/foto_sortierung/sortierplan.json \
        --vektoren ~/foto_sortierung/video_vektoren.jsonl \
        --schreiben --fortsetzen --max-videos 20

Als Modul (Tests, Skripte): ``main(argv=[...])``.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import tempfile
import time

HIER = os.path.dirname(os.path.abspath(__file__))

VIDEO_ENDUNGEN = (".mp4", ".mov", ".3gp", ".mkv", ".avi", ".m4v")

STANDARD_MAX_MB = 300
STANDARD_ABSTAND_S = 2.0
STANDARD_MAX_FRAMES = 60
JPEG_QUALITAET = 90

STANDARD_PLAN = os.path.join(os.path.expanduser("~"), "foto_sortierung",
                             "sortierplan.json")
STANDARD_VEKTOREN = os.path.join(os.path.expanduser("~"), "foto_sortierung",
                                 "video_vektoren.jsonl")

FERTIG_ENDUNG = ".videos_fertig"


class VideoFehler(Exception):
    """Fehler dieses Werkzeugs — deutsche Klartextmeldung, kein Absturz."""


_CACHE: dict = {}


def _modul_aus_datei(pfad: str, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    if spez is None or spez.loader is None:
        raise VideoFehler(f"Modul nicht gefunden: {pfad}")
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


def _basis():
    """``gesicht_erkennen.py`` laden — nur importiert, nie veraendert."""
    if "basis" not in _CACHE:
        _CACHE["basis"] = _modul_aus_datei(
            os.path.join(HIER, "gesicht_erkennen.py"), "video_gesicht_basis")
    return _CACHE["basis"]


def _ist_zahl(wert) -> bool:
    if isinstance(wert, bool) or not isinstance(wert, (int, float)):
        return False
    return math.isfinite(float(wert))


# ── 1. Plan: nur Videos ───────────────────────────────────────────────────

def ist_video(name) -> bool:
    """Endet der Dateiname auf eine Video-Endung (Gross/klein egal)?"""
    return isinstance(name, str) and name.strip().lower().endswith(VIDEO_ENDUNGEN)


def video_plan_lesen(pfad: str) -> list:
    """Den Sortierplan lesend einlesen -> ``[{"fileid", "jahr", "endung"}]``, nur Videos.

    Der Dateiname steht im Plan unter ``von_name`` (Ersatz ``name``, ``datei``).
    Eintraege ohne ``fileid`` oder ohne Video-Endung werden uebersprungen. Der
    Name selbst wird nicht weitergegeben, nur die Endung (fuer die Temp-Datei).
    """
    if not isinstance(pfad, str) or not pfad.strip():
        raise VideoFehler("Kein Plan-Pfad angegeben.")
    if not os.path.isfile(pfad):
        raise VideoFehler(f"Sortierplan nicht gefunden: {pfad}")
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except (OSError, ValueError) as problem:
        raise VideoFehler(
            f"Sortierplan nicht lesbar ({problem.__class__.__name__}): {pfad}"
        ) from None
    zuege = daten.get("zuege") if isinstance(daten, dict) else daten
    if not isinstance(zuege, list):
        raise VideoFehler(f"Sortierplan ohne Feld 'zuege': {pfad}")
    eintraege: list = []
    for zug in zuege:
        if not isinstance(zug, dict):
            continue
        fileid = zug.get("fileid")
        if isinstance(fileid, bool) or fileid is None:
            continue
        kennung = str(fileid).strip()
        if not kennung:
            continue
        name = ""
        for feld in ("von_name", "name", "datei"):
            if isinstance(zug.get(feld), str) and zug.get(feld).strip():
                name = zug[feld].strip()
                break
        if not ist_video(name):
            continue
        jahr = zug.get("jahr")
        eintraege.append({"fileid": kennung,
                          "jahr": int(jahr) if _ist_zahl(jahr) else None,
                          "endung": os.path.splitext(name)[1].lower()})
    return eintraege


# ── 2. Frames entnehmen (einsteckbar) ─────────────────────────────────────

def zeitpunkte_rechnen(dauer_s, abstand_s=STANDARD_ABSTAND_S,
                       max_frames=STANDARD_MAX_FRAMES) -> list:
    """Die Zeitpunkte (Sekunden) der Frames rechnen — reine Funktion.

    Alle ``abstand_s`` Sekunden ab 0; ergaebe das mehr als ``max_frames``,
    werden genau ``max_frames`` Zeitpunkte gleichmaessig ueber die Dauer
    verteilt. Unbrauchbare Dauer (``<= 0``) ergibt eine leere Liste.
    """
    if not _ist_zahl(dauer_s) or float(dauer_s) <= 0:
        return []
    abstand = float(abstand_s) if _ist_zahl(abstand_s) and float(abstand_s) > 0 \
        else STANDARD_ABSTAND_S
    grenze = int(max_frames) if _ist_zahl(max_frames) and int(max_frames) > 0 \
        else STANDARD_MAX_FRAMES
    dauer = float(dauer_s)
    anzahl = int(dauer // abstand) + 1
    if anzahl <= grenze:
        return [round(i * abstand, 3) for i in range(anzahl)]
    schritt = dauer / grenze
    return [round(i * schritt, 3) for i in range(grenze)]


def frames_entnehmen(pfad, abstand_s=STANDARD_ABSTAND_S,
                     max_frames=STANDARD_MAX_FRAMES):
    """Frames eines Videos als ``(zeit_s, jpeg_bytes)`` liefern (Generator).

    ``cv2`` wird erst hier geladen. Die Frames entstehen in-memory
    (``cv2.imencode``), es wird nichts gespeichert. Ist das Video nicht
    lesbar, endet der Generator ohne Frame; fehlt ``cv2``, kommt ein
    ``VideoFehler`` mit deutscher Meldung.
    """
    try:
        import cv2
    except Exception as problem:
        raise VideoFehler("Bildbibliothek cv2 nicht verfuegbar "
                          f"({problem.__class__.__name__}).") from None
    aufnahme = cv2.VideoCapture(pfad)
    try:
        if not aufnahme.isOpened():
            return
        fps = float(aufnahme.get(cv2.CAP_PROP_FPS) or 0.0)
        anzahl = float(aufnahme.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        if fps > 0 and anzahl > 0:
            zeiten = zeitpunkte_rechnen(anzahl / fps, abstand_s, max_frames)
        else:
            # Laenge unbekannt: von vorn in festem Abstand, bis das Lesen endet.
            zeiten = [round(i * float(abstand_s), 3)
                      for i in range(int(max_frames))]
        for zeit in zeiten:
            aufnahme.set(cv2.CAP_PROP_POS_MSEC, zeit * 1000.0)
            gelesen, bild = aufnahme.read()
            if not gelesen or bild is None:
                if fps > 0 and anzahl > 0:
                    continue
                break
            ok, kodiert = cv2.imencode(".jpg", bild,
                                       [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITAET])
            if ok:
                yield zeit, bytes(kodiert.tobytes())
    finally:
        aufnahme.release()


# ── 3. Ein Video verarbeiten ──────────────────────────────────────────────

def _metadaten_leer() -> dict:
    return {"aufnahme": None, "kamera_hersteller": None,
            "kamera_modell": None, "gps": None}


def frame_kennung(fileid, zeit_s) -> str:
    """``<fileid>#t=<sekunden>`` (eine Nachkommastelle)."""
    return f"{fileid}#t={float(zeit_s):.1f}"


def _ist_zu_gross(problem) -> bool:
    return problem.__class__.__name__ == "PCloudZuGross"


class VideoLauf:
    """Iterator ueber Videos -> je Frame mit Gesicht eine Vektorzeile.

    Zaehler (``lauf.zaehler``): ``videos_gesamt``, ``videos_geholt``,
    ``zu_gross``, ``fehler``, ``frames_gesamt``, ``frames_mit_gesicht``,
    ``sekunden``. ``fertig`` (Liste) sammelt die Video-Kennungen, die
    vollstaendig verarbeitet wurden; ``fertig_melden`` (falls gesetzt) wird
    dafuer sofort gerufen (Fortschrittsdatei).
    """

    def __init__(self, videos, dienst, modell, max_bytes,
                 abstand_s=STANDARD_ABSTAND_S, max_frames=STANDARD_MAX_FRAMES,
                 frames_fn=None, fertig_melden=None):
        self._videos = list(videos or [])
        self._dienst = dienst
        self._modell = modell
        self._max_bytes = int(max_bytes)
        self._abstand = abstand_s
        self._max_frames = max_frames
        self._frames_fn = frames_fn if callable(frames_fn) else frames_entnehmen
        self._fertig_melden = fertig_melden if callable(fertig_melden) else None
        self.fertig: list = []
        self.zaehler = {"videos_gesamt": len(self._videos), "videos_geholt": 0,
                        "zu_gross": 0, "fehler": 0, "frames_gesamt": 0,
                        "frames_mit_gesicht": 0, "sekunden": 0.0}
        self._start = time.monotonic()

    def __iter__(self):
        try:
            for video in self._videos:
                yield from self._video(video)
        finally:
            self.zaehler["sekunden"] = round(time.monotonic() - self._start, 3)

    def _video(self, video):
        fileid = str(video.get("fileid")).strip() if isinstance(video, dict) else ""
        if not fileid:
            self.zaehler["fehler"] += 1
            return
        try:
            rohdaten = self._dienst.datei_bytes(fileid, self._max_bytes)
        except Exception as problem:
            self.zaehler["zu_gross" if _ist_zu_gross(problem) else "fehler"] += 1
            return
        if not isinstance(rohdaten, (bytes, bytearray)) or not rohdaten:
            self.zaehler["fehler"] += 1
            return
        if len(rohdaten) > self._max_bytes:
            self.zaehler["zu_gross"] += 1
            return
        self.zaehler["videos_geholt"] += 1

        endung = video.get("endung") if isinstance(video, dict) else None
        if not isinstance(endung, str) or endung not in VIDEO_ENDUNGEN:
            endung = ".mp4"
        pfad = None
        vollstaendig = False
        try:
            # cv2.VideoCapture braucht einen Pfad: fluechtige Temp-Datei.
            kopf = tempfile.NamedTemporaryFile(delete=False, suffix=endung,
                                               prefix="videogesicht_")
            pfad = kopf.name
            try:
                kopf.write(bytes(rohdaten))
            finally:
                kopf.close()
            rohdaten = None
            for zeit_s, jpeg in self._frames_fn(pfad, self._abstand,
                                                self._max_frames):
                self.zaehler["frames_gesamt"] += 1
                kennung = frame_kennung(fileid, zeit_s)
                try:
                    zeile = self._modell.gesichter(jpeg, bild_id=kennung)
                    if not isinstance(zeile, dict):
                        raise TypeError("kein Ergebnis")
                except Exception:
                    self.zaehler["fehler"] += 1
                    continue
                if zeile.get("fehler"):
                    self.zaehler["fehler"] += 1
                if not zeile.get("gesichter"):
                    continue
                self.zaehler["frames_mit_gesicht"] += 1
                yield {"bild_id": kennung, "video_id": fileid,
                       "zeit_s": float(zeit_s),
                       "breite": zeile.get("breite", 0),
                       "hoehe": zeile.get("hoehe", 0),
                       "gesichter": zeile.get("gesichter") or [],
                       "metadaten": _metadaten_leer()}
            vollstaendig = True
        except GeneratorExit:
            raise
        except Exception:
            self.zaehler["fehler"] += 1
        finally:
            if pfad is not None:
                try:
                    os.remove(pfad)
                except OSError:
                    pass
        if vollstaendig:
            self.fertig.append(fileid)
            if self._fertig_melden is not None:
                self._fertig_melden(fileid)


# ── 4. Fortsetzen und Schreiben ───────────────────────────────────────────

def fertig_pfad(vektoren: str) -> str:
    return str(vektoren) + FERTIG_ENDUNG


def fertige_videos_lesen(vektoren: str) -> set:
    """``video_id``s der Vektordatei plus Kennungen der Fortschrittsdatei (nur lesend)."""
    ids: set = set()
    if isinstance(vektoren, str) and os.path.isfile(vektoren):
        with open(vektoren, encoding="utf-8", errors="replace") as datei:
            for zeile in datei:
                try:
                    daten = json.loads(zeile)
                except ValueError:
                    continue
                if isinstance(daten, dict):
                    kennung = daten.get("video_id")
                    if isinstance(kennung, (str, int)) \
                            and not isinstance(kennung, bool) \
                            and str(kennung).strip():
                        ids.add(str(kennung).strip())
    pfad = fertig_pfad(vektoren)
    if os.path.isfile(pfad):
        with open(pfad, encoding="utf-8", errors="replace") as datei:
            for zeile in datei:
                if zeile.strip():
                    ids.add(zeile.strip())
    return ids


def _pcloud_dienst():
    """Die echte pCloud-Quelle bauen (dasselbe wie bei den Fotos)."""
    try:
        return _basis()._pcloud_dienst()
    except Exception as problem:
        raise VideoFehler(str(problem)) from None


def jahr_uebersicht(auswahl) -> dict:
    zahlen: dict = {}
    for eintrag in auswahl or []:
        jahr = eintrag.get("jahr") if isinstance(eintrag, dict) else None
        zahlen[jahr] = zahlen.get(jahr, 0) + 1
    return zahlen


def _ausserhalb_repo(pfad: str) -> None:
    basis = _basis()
    basis._personen_cluster().pruefe_ausserhalb_repo(pfad)


def _davor_offen(pfad: str) -> bool:
    return os.path.isfile(pfad) and not _basis()._endet_mit_zeilenende(pfad)


def _schreiben(vektoren, lauf, anhaengen):
    """Zeilen und Fortschritt sofort schreiben + flushen. Rueckgabe: Zeilenzahl."""
    ordner = os.path.dirname(os.path.abspath(vektoren))
    os.makedirs(ordner, exist_ok=True)
    fertig = fertig_pfad(vektoren)
    anzahl = 0
    offen = bool(anhaengen) and _davor_offen(vektoren)
    with open(vektoren, "a" if anhaengen else "w", encoding="utf-8") as ziel, \
            open(fertig, "a" if anhaengen else "w", encoding="utf-8") as spur:
        if offen:
            ziel.write("\n")
            ziel.flush()

        def melden(kennung):
            spur.write(f"{kennung}\n")
            spur.flush()

        lauf._fertig_melden = melden
        for zeile in lauf:
            ziel.write(json.dumps(zeile, ensure_ascii=False) + "\n")
            ziel.flush()
            anzahl += 1
    return anzahl


# ── 5. Kommandozeile ──────────────────────────────────────────────────────

def main(argv=None) -> int:
    """Trockenlauf zaehlen oder Video-Vektorzeilen schreiben (Exit 0 / 2)."""
    zerleger = argparse.ArgumentParser(
        description="E14b: Gesichter aus Videos (pCloud) erkennen und als "
                    "Vektorzeilen fuer personen_cluster schreiben. Standard "
                    "ist der Trockenlauf (kein Download).")
    zerleger.add_argument("--plan", default=STANDARD_PLAN,
                          help="Sortierplan (JSON, nur lesend)")
    zerleger.add_argument("--vektoren", default=STANDARD_VEKTOREN,
                          help="Zieldatei (PFLICHT ausserhalb des Repos)")
    zerleger.add_argument("--jahr", type=int, default=None,
                          help="nur Videos dieses Jahrs")
    zerleger.add_argument("--max-videos", dest="max_videos", type=int,
                          default=None, help="hoechstens so viele Videos")
    zerleger.add_argument("--max-mb", dest="max_mb", type=float,
                          default=STANDARD_MAX_MB,
                          help="Obergrenze je Video in MB (Standard 300); "
                               "groessere zaehlen als zu_gross")
    zerleger.add_argument("--abstand-s", dest="abstand_s", type=float,
                          default=STANDARD_ABSTAND_S,
                          help="Sekunden zwischen zwei Frames (Standard 2,0)")
    zerleger.add_argument("--max-frames", dest="max_frames", type=int,
                          default=STANDARD_MAX_FRAMES,
                          help="hoechstens so viele Frames je Video (60)")
    zerleger.add_argument("--modelle", default=None,
                          help="Ordner der Modelldateien")
    zerleger.add_argument("--fortsetzen", action="store_true",
                          help="fertige Videos ueberspringen und anhaengen")
    zerleger.add_argument("--trocken", action="store_true",
                          help="nichts schreiben (hat Vorrang)")
    zerleger.add_argument("--schreiben", action="store_true",
                          help="wirklich rechnen und schreiben")
    args = zerleger.parse_args(argv)

    schreiben = bool(args.schreiben) and not bool(args.trocken)
    if schreiben:
        _ausserhalb_repo(args.vektoren)

    try:
        videos = video_plan_lesen(args.plan)
        if args.jahr is not None:
            videos = [v for v in videos if v.get("jahr") == args.jahr]
        vorhanden = 0
        if args.fortsetzen:
            ids = fertige_videos_lesen(args.vektoren)
            vorhanden = len(ids)
            videos = [v for v in videos if v["fileid"] not in ids]
        if args.max_videos is not None and args.max_videos >= 0:
            videos = videos[:args.max_videos]

        print("Video-Gesichter E14b — "
              + ("Trockenlauf (es wird NICHTS geholt und NICHTS geschrieben)"
                 if not schreiben else "Schreiben ist eingeschaltet"))
        print(f"Videos im Plan (Auswahl): {len(videos)}")
        if args.fortsetzen:
            print(f"Fortsetzen: bereits fertig: {vorhanden}, "
                  f"noch offen: {len(videos)}")
        uebersicht = jahr_uebersicht(videos)
        for jahr in sorted(uebersicht, key=lambda w: (w is None, w)):
            print(f"  {'ohne Jahr' if jahr is None else jahr}: "
                  f"{uebersicht[jahr]} Video(s)")
        if not schreiben:
            print("Ohne --schreiben wurde NICHTS geholt und NICHTS geschrieben.")
            return 0

        modell = _basis().GesichtsModell(args.modelle)
        laden = getattr(modell, "_laden", None)
        if callable(laden):
            try:
                laden()
            except Exception as problem:
                print("Abbruch: Gesichtsmodell nicht ladbar "
                      f"({problem.__class__.__name__}): {problem}\n"
                      "Richtigen Interpreter nehmen (Gesichter-venv mit cv2 und "
                      "onnxruntime) und die Modelldateien pruefen. "
                      "Es wurde NICHTS geschrieben.")
                return 2
        dienst = _pcloud_dienst()
        lauf = VideoLauf(videos, dienst, modell,
                         max_bytes=int(float(args.max_mb) * 1024 * 1024),
                         abstand_s=args.abstand_s, max_frames=args.max_frames)
        anzahl = _schreiben(args.vektoren, lauf, args.fortsetzen)
        z = lauf.zaehler
        print(f"Videos gesamt: {z['videos_gesamt']}   geholt: {z['videos_geholt']}"
              f"   zu_gross: {z['zu_gross']}   Fehler: {z['fehler']}")
        print(f"Frames gesamt: {z['frames_gesamt']}   "
              f"Frames mit Gesicht: {z['frames_mit_gesicht']}   "
              f"sekunden: {z['sekunden']}")
        print(f"Vektorzeilen geschrieben: {anzahl}")
        return 0
    except VideoFehler as problem:
        print(f"Fehler: {problem}")
        return 2
    except Exception as problem:  # GesichtFehler u. a. der Basis
        print(f"Fehler: {problem}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
