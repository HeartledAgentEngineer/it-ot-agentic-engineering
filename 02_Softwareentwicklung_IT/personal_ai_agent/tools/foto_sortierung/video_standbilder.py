"""Standbilder der Video-Gesichter fuer das Quiz (Plan video-gesichter-im-quiz, V1, 14.10.2026).

Wozu:
  16.966 Gesichter in ``gesicht_zuordnung.jsonl`` stammen aus Videos (``video_id``,
  ``zeit_s``, ``bbox`` im Frame). Ein Frame existiert nirgends als Bild, deshalb
  zeigt das Quiz diese Gesichter nicht. Dieses Werkzeug holt jedes betroffene Video
  **einmal**, springt an die benoetigten Zeitpunkte, verkleinert den Frame und laedt
  ihn als JPEG in die **eigene** pCloud nach ``/Agent/video_standbilder/``. Die
  Ergebnisdatei ordnet jede Frame-Kennung ihrem Standbild zu::

      {"bild_id": "<vid>#t=4.0", "video_id": "<vid>", "zeit_s": 4.0,
       "standbild_fileid": 123, "breite": 1600, "hoehe": 900, "skala": 0.8333,
       "stand": "2026-10-14T18:00:00+00:00"}

  ``breite``/``hoehe`` sind das Mass des Standbilds; ``bbox × skala`` ist der
  Gesichtsrahmen darin. ``gruppen_quiz`` liest die Datei und zeigt die Gesichter
  ueber den vorhandenen Weg ``/api/cloud/thumb``.

Regeln:
  * Trockenlauf ist Standard: zaehlt Videos, Frames und Gruppen, ohne Netz.
    ``--groessen`` fragt zusaetzlich die Videogroessen ab (``stat``, nur lesend).
  * Erst ``--schreiben`` laedt Videos und laedt Standbilder hoch.
  * Schreiben in pCloud nur ueber ``tools/pcloud/uebergabe_hochladen.py``
    (``createfolderifnotexists`` + ``uploadfile``) und nur unter ``/Agent/``.
    Kein Loeschen, kein Umbenennen.
  * Idempotent: fester Dateiname ``<vid>_t<zeit>.jpg``. Liegt er schon in pCloud,
    wird nicht erneut hochgeladen (Abbruch zwischen Hochladen und Eintrag).
    Eine ``bild_id`` aus der Ergebnisdatei wird uebersprungen; ein Video, dessen
    Frames alle erledigt sind, wird nicht geladen.
  * Jede Ergebniszeile wird sofort geschrieben (flush + fsync).
  * Ergebnisdatei nie im Repo (Exit 2). Das Video liegt nur als fluechtige
    Temp-Datei vor und wird immer entfernt.
  * Konsole nur Zahlen — keine Kennungen, keine Namen, keine Pfade aus den Daten.

Rueckweg: Ordner ``/Agent/video_standbilder/`` in pCloud und die Ergebnisdatei von
Hand entfernen. Das Werkzeug loescht nie.

Aufruf::

    backend/.venv/Scripts/python.exe tools/foto_sortierung/video_standbilder.py
    <gesichter-venv>/python.exe tools/foto_sortierung/video_standbilder.py --schreiben
    ... --schreiben --uebergeben     # danach Ergebnisdatei kabellos ans Handy
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Tuple

HIER = os.path.dirname(os.path.abspath(__file__))
PROJEKT = os.path.dirname(os.path.dirname(HIER))
BACKEND = os.path.join(PROJEKT, "backend")
REPO = os.path.dirname(os.path.dirname(PROJEKT))

ZIELORDNER = "/Agent/video_standbilder"
UMFAENGE = ("nur_video", "alle")
STANDARD_MAX_JE_GRUPPE = 8
STANDARD_MAX_SEITE = 1600
STANDARD_MAX_MB = 300
JPEG_QUALITAET = 85
GRUPPEN_ORDNER = os.path.join(os.path.expanduser("~"), "foto_sortierung", "personen_gruppen")


class StandbildFehler(Exception):
    """Fehler mit deutscher Klartextmeldung."""


def _modul(pfad: str, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


def dateiname_ergebnis() -> str:
    """Gemeinsame Konstante mit dem Quiz (``gruppen_quiz.VIDEO_STANDBILDER_DATEINAME``)."""
    if BACKEND not in sys.path:
        sys.path.insert(0, BACKEND)
    from app.services import gruppen_quiz
    return gruppen_quiz.VIDEO_STANDBILDER_DATEINAME


def zeit_text(zeit_s: Any) -> str:
    return f"{float(zeit_s):.1f}"


def frame_kennung(video_id: Any, zeit_s: Any) -> str:
    return f"{video_id}#t={zeit_text(zeit_s)}"


def standbild_name(video_id: Any, zeit_s: Any) -> str:
    return f"{video_id}_t{zeit_text(zeit_s)}.jpg"


def _jetzt() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── 1. Auswahl (rein, ohne Netz) ──────────────────────────────────────────

def zeilen_lesen(pfad: str) -> List[Dict[str, Any]]:
    """Gesichtszeilen lesen; kaputte Zeilen werden uebersprungen."""
    zeilen = []
    with open(pfad, encoding="utf-8") as datei:
        for roh in datei:
            try:
                z = json.loads(roh)
            except ValueError:
                continue
            if isinstance(z, dict) and z.get("kennung"):
                zeilen.append(z)
    return zeilen


def _guete(z: Dict[str, Any]) -> float:
    try:
        return float(z.get("anteil") or 0) * float(z.get("score") or 0)
    except (TypeError, ValueError):
        return 0.0


def auswaehlen(zeilen: Iterable[Dict[str, Any]], umfang: str = "nur_video",
               max_je_gruppe: int = STANDARD_MAX_JE_GRUPPE) -> Dict[str, Any]:
    """Welche Frames werden gebraucht?

    Rueckgabe: ``{"frames": {video_id: {zeit_text: {"breite", "hoehe"}}}, "gruppen": n,
    "gesichter": n}``. Je Gruppe die besten ``max_je_gruppe`` Video-Gesichter
    (``anteil × score``), je Frame hoechstens eines; ``0`` = alle Gesichter der Gruppe
    (15.10.2026, fuer die vollstaendige Anzeige im Quiz).
    """
    if umfang not in UMFAENGE:
        raise StandbildFehler(f"Unbekannter Umfang: {umfang}")
    je_gruppe: Dict[str, List[Dict[str, Any]]] = {}
    hat_foto: set = set()
    for z in zeilen:
        k = str(z["kennung"])
        if z.get("video_id") and z.get("zeit_s") is not None:
            je_gruppe.setdefault(k, []).append(z)
        else:
            hat_foto.add(k)
    frames: Dict[str, Dict[str, Dict[str, Any]]] = {}
    gruppen = gesichter = 0
    for k in sorted(je_gruppe):
        if umfang == "nur_video" and k in hat_foto:
            continue
        gruppen += 1
        gesehen: set = set()
        # 0 (oder kleiner) = alle Gesichter der Gruppe; Standard bleibt 8 (15.10.2026).
        grenze = max(0, int(max_je_gruppe))
        for z in sorted(je_gruppe[k], key=lambda z: (-_guete(z), str(z.get("bild_id")))):
            if grenze and len(gesehen) >= grenze:
                break
            vid, zt = str(z["video_id"]), zeit_text(z["zeit_s"])
            if (vid, zt) in gesehen:
                continue
            gesehen.add((vid, zt))
            gesichter += 1
            frames.setdefault(vid, {})[zt] = {"breite": z.get("breite"), "hoehe": z.get("hoehe")}
    return {"frames": frames, "gruppen": gruppen, "gesichter": gesichter}


def erledigte_lesen(pfad: str) -> Dict[str, Dict[str, Any]]:
    """{bild_id: Zeile} aus der Ergebnisdatei (fehlt -> leer)."""
    ergebnis: Dict[str, Dict[str, Any]] = {}
    if not os.path.isfile(pfad):
        return ergebnis
    with open(pfad, encoding="utf-8") as datei:
        for roh in datei:
            try:
                z = json.loads(roh)
            except ValueError:
                continue
            if isinstance(z, dict) and z.get("bild_id") and z.get("standbild_fileid"):
                ergebnis[str(z["bild_id"])] = z
    return ergebnis


def offen_rechnen(frames: Dict[str, Dict[str, Any]],
                  erledigt: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Nur Frames, die noch kein Standbild haben; Videos ohne offenen Frame fallen weg."""
    offen: Dict[str, Dict[str, Any]] = {}
    for vid, zeiten in frames.items():
        rest = {zt: m for zt, m in zeiten.items() if frame_kennung(vid, zt) not in erledigt}
        if rest:
            offen[vid] = rest
    return offen


# ── 2. Frames holen (cv2, erst hier geladen) ──────────────────────────────

def massstab(breite: int, hoehe: int, max_seite: int) -> float:
    groesste = max(int(breite), int(hoehe))
    return 1.0 if groesste <= max_seite else max_seite / groesste


def standbilder_entnehmen(pfad: str, zeiten: List[str], max_seite: int = STANDARD_MAX_SEITE
                          ) -> Iterator[Tuple[str, int, int, float, bytes]]:
    """Je Zeitpunkt ``(zeit_text, alt_breite, alt_hoehe, skala, jpeg)``.

    Springt wie beim Erzeugen per ``CAP_PROP_POS_MSEC``. Nicht lesbare Frames
    fehlen in der Ausgabe."""
    try:
        import cv2
    except Exception as problem:
        raise StandbildFehler(f"Bildbibliothek cv2 nicht verfuegbar ({problem.__class__.__name__}).")
    aufnahme = cv2.VideoCapture(pfad)
    try:
        if not aufnahme.isOpened():
            return
        for zt in zeiten:
            aufnahme.set(cv2.CAP_PROP_POS_MSEC, float(zt) * 1000.0)
            gelesen, bild = aufnahme.read()
            if not gelesen or bild is None:
                continue
            hoehe, breite = bild.shape[:2]
            skala = massstab(breite, hoehe, max_seite)
            if skala < 1.0:
                bild = cv2.resize(bild, (round(breite * skala), round(hoehe * skala)),
                                  interpolation=cv2.INTER_AREA)
            ok, kodiert = cv2.imencode(".jpg", bild, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITAET])
            if ok:
                yield zt, int(breite), int(hoehe), skala, bytes(kodiert.tobytes())
    finally:
        aufnahme.release()


def _mass_passt(erwartet: Dict[str, Any], breite: int, hoehe: int) -> bool:
    try:
        return round(float(erwartet.get("breite"))) == breite and \
            round(float(erwartet.get("hoehe"))) == hoehe
    except (TypeError, ValueError):
        return False


# ── 3. Lauf ───────────────────────────────────────────────────────────────

def fortschritt_zeile(fertig: int, gesamt: int, zaehler: Dict[str, int],
                      sekunden: float) -> str:
    """Eine Zeile je fertigem Video - nur Zahlen, keine Kennung, kein Pfad."""
    zeile = (f"Video {fertig}/{gesamt} · Standbilder {zaehler['zeilen']} · "
             f"Fehler {zaehler['fehler'] + zaehler['zu_gross']}")
    if 0 < fertig < gesamt and sekunden > 0:
        rest_min = sekunden / fertig * (gesamt - fertig) / 60
        zeile += f" · noch ca. {rest_min:.0f} min"
    return zeile


class Lauf:
    """Ein Schreiblauf. Alle Aussenwege sind einsetzbar (Tests ohne Netz)."""

    def __init__(self, offen: Dict[str, Dict[str, Any]], *, dienst: Any,
                 vorhandene: Dict[str, int], hochladen: Callable[[str, bytes], Optional[int]],
                 ergebnis: str, max_bytes: int, max_seite: int = STANDARD_MAX_SEITE,
                 entnehmen: Callable[..., Iterable] = standbilder_entnehmen,
                 max_videos: Optional[int] = None,
                 melden: Optional[Callable[[str], None]] = None) -> None:
        self.offen, self.dienst, self.vorhandene = offen, dienst, dict(vorhandene)
        self.hochladen, self.ergebnis = hochladen, ergebnis
        self.max_bytes, self.max_seite, self.entnehmen = max_bytes, max_seite, entnehmen
        self.max_videos = max_videos
        self.melden = melden
        self.zaehler = {"videos_geholt": 0, "zu_gross": 0, "fehler": 0, "hochgeladen": 0,
                        "wiederverwendet": 0, "mass_abweichend": 0, "nicht_lesbar": 0,
                        "zeilen": 0}

    def _zeile_schreiben(self, zeile: Dict[str, Any]) -> None:
        with open(self.ergebnis, "a", encoding="utf-8") as ziel:
            ziel.write(json.dumps(zeile, ensure_ascii=False) + "\n")
            ziel.flush()
            os.fsync(ziel.fileno())
        self.zaehler["zeilen"] += 1

    def _ende_reparieren(self) -> None:
        """Endet die Ergebnisdatei nach einem Abbruch ohne Zeilenumbruch, erst einen anhaengen —
        sonst klebt die naechste gueltige Zeile an der halben und beide gingen verloren."""
        try:
            with open(self.ergebnis, "rb") as datei:
                datei.seek(0, os.SEEK_END)
                if datei.tell() == 0:
                    return
                datei.seek(-1, os.SEEK_END)
                letztes = datei.read(1)
        except OSError:
            return
        if letztes != b"\n":
            with open(self.ergebnis, "a", encoding="utf-8") as ziel:
                ziel.write("\n")
                ziel.flush()
                os.fsync(ziel.fileno())

    def ausfuehren(self) -> Dict[str, int]:
        self._ende_reparieren()
        gesamt = len(self.offen)
        if self.max_videos is not None:
            gesamt = min(gesamt, max(0, self.max_videos))
        start = time.monotonic()
        for nr, vid in enumerate(sorted(self.offen)):
            if nr >= gesamt:
                break
            self._video(vid, self.offen[vid])
            if self.melden:
                self.melden(fortschritt_zeile(nr + 1, gesamt, self.zaehler,
                                              time.monotonic() - start))
        return self.zaehler

    def _video(self, vid: str, zeiten: Dict[str, Any]) -> None:
        try:
            rohdaten = self.dienst.datei_bytes(int(vid), self.max_bytes)
        except Exception as problem:
            self.zaehler["zu_gross" if problem.__class__.__name__ == "PCloudZuGross"
                         else "fehler"] += 1
            return
        if not isinstance(rohdaten, (bytes, bytearray)) or not rohdaten:
            self.zaehler["fehler"] += 1
            return
        self.zaehler["videos_geholt"] += 1
        pfad = None
        try:
            kopf = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4", prefix="standbild_")
            pfad = kopf.name
            try:
                kopf.write(bytes(rohdaten))
            finally:
                kopf.close()
            rohdaten = None
            gelesen = set()
            for zt, breite, hoehe, skala, jpeg in self.entnehmen(
                    pfad, sorted(zeiten, key=float), self.max_seite):
                gelesen.add(zt)
                if not _mass_passt(zeiten[zt], breite, hoehe):
                    self.zaehler["mass_abweichend"] += 1
                    continue
                name = standbild_name(vid, zt)
                fileid = self.vorhandene.get(name)
                if fileid:
                    self.zaehler["wiederverwendet"] += 1
                else:
                    try:
                        fileid = self.hochladen(name, jpeg)
                    except Exception:
                        fileid = None
                    if not fileid:
                        self.zaehler["fehler"] += 1
                        continue
                    self.vorhandene[name] = fileid
                    self.zaehler["hochgeladen"] += 1
                self._zeile_schreiben({
                    "bild_id": frame_kennung(vid, zt), "video_id": vid, "zeit_s": float(zt),
                    "standbild_fileid": int(fileid), "breite": round(breite * skala),
                    "hoehe": round(hoehe * skala), "skala": round(skala, 6), "stand": _jetzt()})
            self.zaehler["nicht_lesbar"] += len(set(zeiten) - gelesen)
        except StandbildFehler:
            raise
        except Exception:
            self.zaehler["fehler"] += 1
        finally:
            if pfad is not None:
                try:
                    os.remove(pfad)
                except OSError:
                    pass


# ── 4. Echte Aussenwege ───────────────────────────────────────────────────

def _uebergabe():
    return _modul(os.path.join(PROJEKT, "tools", "pcloud", "uebergabe_hochladen.py"),
                  "standbild_uebergabe")


def _pcloud_dienst():
    if BACKEND not in sys.path:
        sys.path.insert(0, BACKEND)
    from app.services.pcloud_service import PCloudService
    return PCloudService()


def vorhandene_lesen(dienst: Any, folderid: int) -> Dict[str, int]:
    """Name -> fileid der Standbilder, die schon in pCloud liegen (nur lesend)."""
    return {e["name"]: e["fileid"] for e in dienst.liste(folderid)
            if not e.get("ist_ordner") and isinstance(e.get("fileid"), int)}


def pruefe_ausserhalb_repo(pfad: str) -> None:
    # realpath: auch eine Verknuepfung (Junction/Symlink) auf einen Repo-Ordner faellt auf.
    ziel = os.path.normcase(os.path.realpath(pfad))
    repo = os.path.normcase(os.path.realpath(REPO))
    if ziel == repo or ziel.startswith(repo + os.sep):
        print("Ergebnisdatei liegt im Repo - abgelehnt (persoenliche Daten gehoeren nicht "
              "ins Repo).")
        raise SystemExit(2)


def groessen_summe(dienst: Any, video_ids: Iterable[str]) -> Tuple[int, int]:
    """(Bytes, unbekannt) ueber ``stat`` (nur lesend)."""
    summe = unbekannt = 0
    for vid in video_ids:
        try:
            daten = dienst._api("/stat", fileid=int(vid))
            summe += int((daten.get("metadata") or {}).get("size") or 0)
        except Exception:
            unbekannt += 1
    return summe, unbekannt


# ── 5. Kommandozeile ──────────────────────────────────────────────────────

def _argumente(argv: Optional[List[str]]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Standbilder der Video-Gesichter fuer das Quiz "
                                            "(Trockenlauf ist Standard).")
    p.add_argument("--zuordnung", default=os.path.join(GRUPPEN_ORDNER, "gesicht_zuordnung.jsonl"))
    p.add_argument("--ergebnis", default=None,
                   help="Ergebnisdatei (Standard personen_gruppen/<gemeinsamer Name>)")
    p.add_argument("--umfang", choices=UMFAENGE, default="nur_video")
    p.add_argument("--max-je-gruppe", type=int, default=STANDARD_MAX_JE_GRUPPE,
                   help="Gesichter je Gruppe; 0 = alle (Standard 8)")
    p.add_argument("--max-seite", type=int, default=STANDARD_MAX_SEITE)
    p.add_argument("--max-mb", type=int, default=STANDARD_MAX_MB)
    p.add_argument("--max-videos", type=int, default=None)
    p.add_argument("--groessen", action="store_true", help="Videogroessen abfragen (nur lesend)")
    p.add_argument("--schreiben", action="store_true", help="WIRKLICH laden und hochladen")
    p.add_argument("--uebergeben", action="store_true",
                   help="danach die Ergebnisdatei kabellos ans Handy (uebergabe_hochladen)")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None, *, dienst: Any = None,
         uebergabe: Any = None, entnehmen: Callable[..., Iterable] = standbilder_entnehmen) -> int:
    args = _argumente(argv)
    ergebnis = args.ergebnis or os.path.join(GRUPPEN_ORDNER, dateiname_ergebnis())
    pruefe_ausserhalb_repo(ergebnis)
    if not os.path.isfile(args.zuordnung):
        print("Gesichtsdatei fehlt - nichts zu tun.")
        return 2
    auswahl = auswaehlen(zeilen_lesen(args.zuordnung), args.umfang, args.max_je_gruppe)
    erledigt = erledigte_lesen(ergebnis)
    offen = offen_rechnen(auswahl["frames"], erledigt)
    print(f"Gruppen: {auswahl['gruppen']} · Gesichter gewaehlt: {auswahl['gesichter']} · "
          f"Videos: {len(auswahl['frames'])} · schon erledigt: {len(erledigt)}")
    print(f"Offen: {len(offen)} Videos, {sum(len(z) for z in offen.values())} Standbilder")
    if args.max_videos is not None and args.max_videos < len(offen):
        print(f"Begrenzt mit --max-videos: dieser Lauf nimmt {max(0, args.max_videos)} davon.")
    if args.groessen:
        dienst = dienst or _pcloud_dienst()
        summe, unbekannt = groessen_summe(dienst, offen)
        print(f"Download: {summe / 1e6:.0f} MB (Groesse unbekannt bei {unbekannt} Videos)")
    if not args.schreiben:
        print("Trockenlauf - nichts geladen, nichts hochgeladen. Scharf mit --schreiben.")
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(ergebnis)), exist_ok=True)
    dienst = dienst or _pcloud_dienst()
    uebergabe = uebergabe or _uebergabe()
    folderid = uebergabe.ordner_holen_oder_anlegen(ZIELORDNER)
    lauf = Lauf(offen, dienst=dienst, vorhandene=vorhandene_lesen(dienst, folderid),
                hochladen=lambda name, daten: uebergabe.hochladen(name, daten, folderid),
                ergebnis=ergebnis, max_bytes=args.max_mb * 1024 * 1024,
                max_seite=args.max_seite, entnehmen=entnehmen, max_videos=args.max_videos,
                melden=lambda zeile: print(zeile, flush=True))
    z = lauf.ausfuehren()
    print("Ergebnis: " + " · ".join(f"{k} {v}" for k, v in z.items()))
    if args.uebergeben:
        return int(uebergabe.main(["--dateien", ergebnis, "--schreiben"]) or 0)
    # Kein Pfad auf der Konsole (Benutzername): Platzhalter statt der echten Datei.
    print("Uebergabe ans Handy (erst Trockenlauf, dann mit --schreiben), oder gleich --uebergeben:")
    print("  python tools/pcloud/uebergabe_hochladen.py --dateien <Ergebnisdatei>")
    print(f"  <Ergebnisdatei> = {'--ergebnis' if args.ergebnis else 'personen_gruppen/' + dateiname_ergebnis()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
