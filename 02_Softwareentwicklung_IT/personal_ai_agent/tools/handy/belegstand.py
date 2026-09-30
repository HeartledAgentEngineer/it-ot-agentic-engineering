"""Belegstand beim Rundenstart in einer Zeile melden (N24c, 29.09.2026).

Warum dieses Werkzeug:
  Der Belegweg aus N24b schreibt beim Widget-Tipp am Handy ``job_liste.txt``
  in ``hermes_diag/``; ``tools/handy/diag_holen.py`` holt ihn per Kabel. Ob
  dieser Beleg vorliegt, musste der Planer bisher **per Hand** herausfinden
  (Kabel pruefen, ``diag_holen.py`` starten, Ordner ansehen). Die offene Zeile
  „ist die Job-Kennung wirklich registriert?“ blieb damit zwischen den Runden
  liegen.

  Dieses Werkzeug ist ein **Lesewerkzeug fuer den Rundenstart**: es fuehrt
  Geraete-Lage, den lokalen Spiegel (``~/foto_sortierung/handy_diag``) und den
  Job-Beleg zu einem **Belegstand** zusammen und druckt am Ende **genau eine**
  Journal-Zeile zum Kopieren in den Plan. Es schreibt **nicht** in den Plan —
  der Plan ist geteilte Datei, ein zweiter Agent arbeitet im selben Baum.

Verhalten:
  * **Ohne Schalter** wird das Geraet (nur lesend ueber ``adb``) gefragt und
    der lokale Spiegel gelesen. Es wird **nichts** geschrieben, Exit 0.
  * Mit ``--ohne-kabel`` wird **nur** der lokale Spiegel gelesen; ``adb`` wird
    gar nicht aufgerufen.
  * Mit ``--merken`` wird die Journal-Zeile zusaetzlich an
    ``~/foto_sortierung/belegstand.jsonl`` angehaengt — die **einzige**
    Schreibstelle des Werkzeugs, nur ausserhalb des Repos, **idempotent**: ist
    die letzte Zeile der Datei schon gleich, wird nichts geschrieben.

Die Job-Lage wird **nicht neu erfunden**, sondern ueber die bestehende Funktion
  ``job_beleg_deuten`` aus ``tools/handy/diag_holen.py`` bestimmt (eine Quelle,
  kein Duplikat).

Grenzen (hart):
  * **Nur Standardbibliothek.** Kein pip-Paket, kein git.
  * **Nur lesend** ueber ``adb`` — kein ``adb push``, kein Schreibbefehl, kein
    ``rm``, kein Erzwingen. Kein Netz ausser dem **lokalen** ``adb``-Aufruf
    (USB). Kein HTTP, kein pCloud, kein LLM.
  * **Keine Loeschfunktion** — im ganzen Modul gibt es keinen Aufruf, der eine
    Datei oder einen Ordner entfernt (kein Loeschen, kein Abbau von Ordnern).
  * **Kein Schluesselwert** in Ausgaben oder Bericht.
  * **Kein Schreiben ins Repo.** Die Schutzpruefung ``_im_repo`` lehnt einen
    ``--spiegel``-Pfad IM Repo ab.

Exit-Codes: 0 = Aussage erzeugt (auch bei ``kein_geraet``,
  ``nicht_vorhanden``, ``job_1901_belegt=unbekannt`` — das ist das Ergebnis,
  kein Programmfehler), 2 = Aufruf- oder Schutzfehler (z. B. ``--spiegel``
  liegt IM Repo).

Aufruf (Kommandozeile)::

    # Geraet fragen + Spiegel lesen, nichts schreiben:
    python tools/handy/belegstand.py

    # Nur den lokalen Spiegel lesen (kein adb):
    python tools/handy/belegstand.py --ohne-kabel

    # Zeile zusaetzlich in belegstand.jsonl sichern (idempotent):
    python tools/handy/belegstand.py --merken

    # Fuer Tests: eine Attrappen-adb statt des echten Programms:
    python tools/handy/belegstand.py --adb C:/pfad/zur/attrappe-adb

Als Modul (Tests, Skripte): ``main(argv=[...]) -> int`` und die reinen
Funktionen ``spiegel_lesen``, ``letzter_tipp``, ``geraete_lage``,
``belegstand``, ``journal_zeile``, ``merken``.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from datetime import datetime

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

# Vorgaben laut Auftrag.
STANDARD_ORDNER = "/sdcard/Download/hermes_diag"
STANDARD_SPIEGEL = os.path.join(os.path.expanduser("~"), "foto_sortierung",
                                "handy_diag")
STANDARD_ADB = "adb"

# Ablage der gemerkten Journal-Zeilen (ausserhalb des Repos, nur mit --merken).
MERKEN_PFAD = os.path.join(os.path.expanduser("~"), "foto_sortierung",
                           "belegstand.jsonl")

# Die feste Job-Kennung des Nachpflege-Jobs (Quelle:
# termux/nachpflege-einrichten.sh, JOB_ID). Nur fuer das Feld
# ``job_1901_belegt`` und die Journal-Zeile.
JOB_ID = 1901

# Der Dateiname des Beleg-Berichts im Spiegel.
JOB_LISTE_NAME = "job_liste.txt"

# Die erste Kopfzeile des Beleg-Berichts beginnt mit diesen zwei Woertern.
KOPF_WORTE = ("beleg", "job-liste")


# ── Die bestehende Deutung aus diag_holen.py einbinden (eine Quelle) ────────

def _diag_holen_laden():
    """``tools/handy/diag_holen.py`` als Nachbarmodul laden.

    Erst der normale Import (greift, wenn das Werkzeug als Skript laeuft und
    das eigene Verzeichnis auf dem Suchpfad liegt), sonst ueber den Dateipfad
    (Tests laden dieses Modul per ``importlib`` ohne Suchpfad-Eintrag). So gibt
    es genau **eine** Fassung von ``job_beleg_deuten``.
    """
    try:
        import diag_holen as modul                       # Skript-Lauf
        return modul
    except ImportError:
        spez = importlib.util.spec_from_file_location(
            "belegstand_diag_holen", os.path.join(HIER, "diag_holen.py"))
        modul = importlib.util.module_from_spec(spez)
        spez.loader.exec_module(modul)
        return modul


dh = _diag_holen_laden()


# ── Kleine Helfer ──────────────────────────────────────────────────────────

def _text(wert) -> str:
    """Ein Feld als Text lesen — Nicht-Text und ``None`` werden zu ``""``."""
    return wert.strip() if isinstance(wert, str) else ""


def _im_repo(pfad: str) -> bool:
    """Liegt der (aufgeloeste) Pfad IM Repo? Gross/Klein und Trenner egal.

    Gleiches Schutzmuster wie in ``tools/handy/diag_holen.py``.
    """
    ziel = os.path.normcase(os.path.abspath(pfad))
    repo = os.path.normcase(os.path.abspath(REPO))
    try:
        return os.path.commonpath([ziel, repo]) == repo
    except ValueError:                            # anderes Laufwerk: nie im Repo
        return False


def _heute() -> str:
    """Das heutige Datum als ``TT.MM.JJJJ`` (fuer die Journal-Zeile)."""
    return datetime.now().strftime("%d.%m.%Y")


# ── 1. Spiegel lesen (nur lesend, fehlender Ordner ist kein Fehler) ─────────

def spiegel_lesen(ordner: str) -> dict:
    """Den lokalen Spiegel (``~/foto_sortierung/handy_diag``) **nur lesend** lesen.

    Rueckgabe (Woerterbuch)::

        {"vorhanden": bool,
         "dateien": [{"name", "groesse"}, ...],
         "job_liste_vorhanden": bool}

    Ein fehlender Ordner ist **kein Fehler** (``vorhanden=False``), es wird
    nicht geworfen. Unterordner werden nicht aufgefuehrt (nur regulaere
    Dateien); die Groesse wird nicht geraten (``None``, wenn nicht lesbar).
    """
    ordner = _text(ordner)
    if not ordner or not os.path.isdir(ordner):
        return {"vorhanden": False, "dateien": [], "job_liste_vorhanden": False}

    dateien: list = []
    job_liste_vorhanden = False
    for name in sorted(os.listdir(ordner)):
        pfad = os.path.join(ordner, name)
        if not os.path.isfile(pfad):
            continue                                  # nur regulaere Dateien
        try:
            groesse = os.path.getsize(pfad)
        except OSError:
            groesse = None
        dateien.append({"name": name, "groesse": groesse})
        if name == JOB_LISTE_NAME:
            job_liste_vorhanden = True
    return {"vorhanden": True, "dateien": dateien,
            "job_liste_vorhanden": job_liste_vorhanden}


def _spiegel_text(ordner: str, name: str) -> str:
    """Den Inhalt einer Spiegel-Datei als Text lesen (nur fuer den Beleg)."""
    pfad = os.path.join(_text(ordner), name)
    if not os.path.isfile(pfad):
        return ""
    try:
        with open(pfad, "r", encoding="utf-8", errors="replace") as datei:
            return datei.read()
    except OSError:
        return ""


# ── 2. Den Zeitstempel der Kopfzeile lesen (nicht raten) ───────────────────

def letzter_tipp(job_liste_inhalt: str) -> str:
    """Den Zeitstempel der **ersten** Kopfzeile des Beleg-Berichts lesen.

    Erwartet wird die Kopfzeile der Form ``beleg job-liste <ISO-Zeit>``.
    Passt das Muster **nicht**, kommt der leere Text zurueck — es wird nicht
    geraten.
    """
    if not isinstance(job_liste_inhalt, str):
        return ""
    for zeile in job_liste_inhalt.splitlines():
        sauber = zeile.strip()
        if not sauber:
            continue                                  # erste NICHT-leere Zeile
        teile = sauber.split()
        if len(teile) >= 3 and teile[0] == KOPF_WORTE[0] and teile[1] == KOPF_WORTE[1]:
            return teile[2]
        return ""
    return ""


# ── 2b. Geraete-Lage aus der ROHEN adb-Ausgabe deuten (reine Funktion) ─────

def geraete_lage(roh: str) -> str:
    """Aus der **rohen** ``adb``-Ausgabe die Geraete-Lage ableiten — nicht raten.

    Die rohe Ausgabe liefert ``diag_holen.dateiliste`` als Feld ``roh``. Sie
    unterscheidet die zwei Faelle, die sonst gleich aussaehen (Nachtrag des
    Planers, 29.09.2026):

      * nennt sie **keinen Geraetebestand** (``no devices`` / ``device not
        found``), dann ist es ``kein_geraet`` (das Kabel haengt an nichts);
      * nennt sie einen **fehlenden Geraete-Bestand** (``No such file`` o. Ae. —
        der Ordner ``hermes_diag/`` gibt es am Handy noch nicht), dann ist es
        ``geraet_ordner_fehlt`` (das Geraet haengt am Kabel, der Ordner fehlt);
      * sonst bleibt es ehrlich ``unbekannt``.

    Die Pruefung ist gross/klein-egal und nur an den genannten Wortgruppen
    befestigt; es wird **nichts geraten**.
    """
    text = _text(roh).lower()
    if not text:
        return "unbekannt"
    if "no devices" in text or "device not found" in text:
        return "kein_geraet"
    if "no such file" in text or "does not exist" in text:
        return "geraet_ordner_fehlt"
    return "unbekannt"


# ── 3. Belegstand zusammenfuehren ──────────────────────────────────────────

def belegstand(adb: str = STANDARD_ADB, ordner: str = STANDARD_ORDNER,
               spiegel: str = STANDARD_SPIEGEL, ohne_kabel: bool = False) -> dict:
    """Geraete-Lage, Spiegel und Job-Beleg zu einem Belegstand zusammenfuehren.

    Gibt **immer dieselben Felder** zurueck::

        {"geraet": "verbunden"|"geraet_ordner_fehlt"|"kein_geraet"|"unbekannt",
         "device_ordner": "<Pfad>", "device_dateien": <int>,
         "spiegel": "vorhanden"|"nicht_vorhanden",
         "job_liste": "vorhanden"|"fehlt",
         "job_1901_belegt": "ja"|"nein"|"unbekannt",
         "letzter_tipp": "<ISO>"|"",
         "fehler": <None|str>}

    Die Geraete-Lage hat **vier** Werte: ``verbunden`` (Ordner da, Dateien
    gezaehlt), ``geraet_ordner_fehlt`` (Geraet am Kabel, aber ``hermes_diag/``
    gibt es noch nicht) und ``kein_geraet`` (kein Geraet am Kabel) werden an der
    **rohen** ``adb``-Ausgabe (Feld ``roh`` aus ``dateiliste``) unterschieden
    (siehe ``geraete_lage``); sonst ``unbekannt``. Sonst saehen „Geraet haengt
    am Kabel, Ordner fehlt" und „kein Geraet am Kabel" gleich aus und die
    Journal-Zeile waere in einem der beiden Faelle falsch.

    Die Job-Lage kommt aus ``job_beleg_deuten`` (``diag_holen.py``), nicht aus
    einer zweiten Fassung. ``spiegel_lesen`` und ``letzter_tipp`` duerfen werfen
    — hier werden sie gefangen und der Grund landet in ``fehler``. Mit
    ``ohne_kabel=True`` wird ``adb`` gar nicht aufgerufen.
    """
    adb = _text(adb) or STANDARD_ADB
    ordner = _text(ordner)
    spiegel = _text(spiegel)
    stand = {
        "geraet": "unbekannt",
        "device_ordner": ordner,
        "device_dateien": 0,
        "spiegel": "nicht_vorhanden",
        "job_liste": "fehlt",
        "job_1901_belegt": "unbekannt",
        "letzter_tipp": "",
        "fehler": None,
    }
    gruende: list = []

    # --- Spiegel und Job-Beleg ---
    try:
        spiegelstand = spiegel_lesen(spiegel)
        stand["spiegel"] = "vorhanden" if spiegelstand["vorhanden"] else "nicht_vorhanden"
        stand["job_liste"] = ("vorhanden" if spiegelstand["job_liste_vorhanden"]
                              else "fehlt")
        if spiegelstand["job_liste_vorhanden"]:
            inhalt = _spiegel_text(spiegel, JOB_LISTE_NAME)
            stand[f"job_{JOB_ID}_belegt"] = dh.job_beleg_deuten(inhalt)
            stand["letzter_tipp"] = letzter_tipp(inhalt)
    except Exception as problem:                      # noqa: BLE001 - bewusst breit
        gruende.append(f"Spiegel nicht lesbar ({problem.__class__.__name__})")

    # --- Geraete-Lage (nur lesend, nur ohne --ohne-kabel) ---
    if not ohne_kabel:
        try:
            liste = dh.dateiliste(adb, ordner)
        except (OSError, ValueError) as problem:
            stand["geraet"] = "unbekannt"
            gruende.append(f"Geraet nicht erreichbar "
                           f"({problem.__class__.__name__})")
        else:
            if liste.get("ok"):
                stand["geraet"] = "verbunden"
                stand["device_dateien"] = len(
                    [e for e in liste.get("eintraege", []) if e.get("art") == "datei"])
            else:
                # Vierter Wert (Nachtrag): an der ROHEN adb-Ausgabe entscheiden,
                # ob kein Geraet am Kabel haengt oder nur der Geraete-Ordner
                # noch fehlt.
                stand["geraet"] = geraete_lage(liste.get("roh", ""))

    if gruende:
        stand["fehler"] = "; ".join(gruende)
    return stand


# ── 4. Die eine Journal-Zeile (reine Funktion, zum Kopieren) ────────────────

def journal_zeile(stand: dict) -> str:
    """Aus dem Belegstand **genau eine** deutsche Zeile bauen (ohne Namen, ohne IP).

    Form::

        Belegstand <TT.MM.JJJJ>: Geraet=verbunden | Spiegel=vorhanden | job_1901_belegt=ja

    Fehlende Angaben werden zu ``kein_geraet`` / ``nicht_vorhanden`` /
    ``unbekannt``. Diese Zeile ist zum **Kopieren in den Plan** gedacht — das
    Werkzeug schreibt sie **nicht** selbst in den Plan.
    """
    stand = stand if isinstance(stand, dict) else {}
    geraet = _text(stand.get("geraet")) or "unbekannt"
    spiegel = _text(stand.get("spiegel")) or "nicht_vorhanden"
    belegt = _text(stand.get(f"job_{JOB_ID}_belegt")) or "unbekannt"
    return (f"Belegstand {_heute()}: Geraet={geraet} | Spiegel={spiegel} | "
            f"job_{JOB_ID}_belegt={belegt}")


# ── 5. Die einzige Schreibstelle (nur mit --merken, idempotent) ─────────────

def _letzte_zeile(pfad: str) -> str:
    """Die letzte Zeile einer Textdatei lesen (leer, wenn es keine gibt)."""
    if not os.path.isfile(pfad):
        return ""
    try:
        with open(pfad, "r", encoding="utf-8", errors="replace") as datei:
            zeilen = datei.read().splitlines()
    except OSError:
        return ""
    return zeilen[-1] if zeilen else ""


def merken(pfad: str, zeile: str) -> bool:
    """Die Journal-Zeile an ``pfad`` anhaengen — **idempotent**.

    Dies ist die **einzige** Schreibstelle des Werkzeugs. Geschrieben wird nur
    ausserhalb des Repos (Schutzpruefung ``_im_repo``); ein Pfad IM Repo wirft
    einen ``ValueError``. Ist die **letzte** Zeile der Datei schon gleich der
    neuen Zeile, wird **nichts** geschrieben und ``False`` zurueckgegeben — sonst
    wird angehaengt und ``True`` zurueckgegeben.
    """
    pfad = _text(pfad)
    zeile = _text(zeile)
    if not pfad or not zeile:
        raise ValueError("Pfad oder Zeile fehlt (merken).")
    if _im_repo(pfad):
        raise ValueError(f"Pfad liegt IM Repo und ist nicht erlaubt: {pfad}")
    if _letzte_zeile(pfad) == zeile:
        return False                                  # schon vorhanden: nichts tun
    os.makedirs(os.path.dirname(os.path.abspath(pfad)), exist_ok=True)
    with open(pfad, "a", encoding="utf-8") as datei:
        datei.write(zeile + "\n")
    return True


# ── 6. Kommandozeile ──────────────────────────────────────────────────────

def main(argv=None) -> int:
    """Kommandozeile: den Belegstand in einer Zeile melden (nur lesend).

    ``--ordner`` (Standard ``/sdcard/Download/hermes_diag``), ``--spiegel``
    (Standard ``~/foto_sortierung/handy_diag``), ``--adb`` (Standard ``adb``),
    ``--ohne-kabel`` (nur den lokalen Spiegel lesen) und ``--merken`` (Zeile
    zusaetzlich in ``belegstand.jsonl`` sichern, idempotent). Exit 0 = Aussage
    erzeugt, 2 = Aufruf-/Schutzfehler (``--spiegel`` IM Repo).
    """
    zerleger = argparse.ArgumentParser(
        description="Belegstand beim Rundenstart in einer Zeile melden - nur "
                    "lesend ueber adb, kein Netz ausser dem lokalen adb-Aufruf, "
                    "kein Schreiben ins Repo.")
    zerleger.add_argument("--ordner", dest="ordner", default=STANDARD_ORDNER,
                          help=f"Geraete-Ordner (Standard {STANDARD_ORDNER})")
    zerleger.add_argument("--spiegel", dest="spiegel", default=STANDARD_SPIEGEL,
                          help=f"lokaler Spiegel (Standard {STANDARD_SPIEGEL})")
    zerleger.add_argument("--adb", dest="adb", default=STANDARD_ADB,
                          help="adb-Programm (Standard 'adb', fuer Tests durch "
                               "eine Attrappe ersetzbar)")
    zerleger.add_argument("--ohne-kabel", dest="ohne_kabel", action="store_true",
                          help="nur den lokalen Spiegel lesen (adb wird nicht "
                               "aufgerufen)")
    zerleger.add_argument("--merken", dest="merken", action="store_true",
                          help=f"die Journal-Zeile zusaetzlich in {MERKEN_PFAD} "
                               "anhaengen (idempotent)")
    args = zerleger.parse_args(argv)

    spiegel = _text(args.spiegel)
    ordner = _text(args.ordner)
    if not spiegel or not ordner:
        print("Fehler: --ordner und --spiegel duerfen nicht leer sein.",
              file=sys.stderr)
        return 2
    if _im_repo(spiegel):
        print(f"Fehler: --spiegel liegt IM Repo und ist nicht erlaubt: {spiegel}\n"
              f"Es wird NICHTS geschrieben.", file=sys.stderr)
        return 2

    stand = belegstand(adb=_text(args.adb) or STANDARD_ADB, ordner=ordner,
                       spiegel=spiegel, ohne_kabel=args.ohne_kabel)

    print(f"Geraete-Ordner: {stand['device_ordner']}")
    print(f"Geraet: {stand['geraet']} (Dateien im Geraete-Ordner: "
          f"{stand['device_dateien']})")
    print(f"Spiegel: {stand['spiegel']} ({spiegel})")
    print(f"Job-Liste: {stand['job_liste']}")
    print(f"letzter Tipp: {stand['letzter_tipp'] or '-'}")
    if stand["fehler"]:
        print(f"Fehler: {stand['fehler']}", file=sys.stderr)

    zeile = journal_zeile(stand)

    if args.merken:
        try:
            geschrieben = merken(MERKEN_PFAD, zeile)
        except (OSError, ValueError) as problem:
            print(f"Fehler: --merken gescheitert "
                  f"({problem.__class__.__name__}).", file=sys.stderr)
            return 2
        if geschrieben:
            print(f"Gemerkt: {MERKEN_PFAD}")
        else:
            print("Nicht gemerkt: die letzte Zeile ist schon gleich (idempotent).")

    # Die Journal-Zeile ist die letzte Ausgabezeile (zum direkten Uebernehmen).
    print(zeile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
