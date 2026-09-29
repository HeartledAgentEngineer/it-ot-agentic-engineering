"""Diagnose-Ordner vom Handy per Kabel holen und auswerten (N24b, 29.09.2026).

Warum dieses Werkzeug:
  Der Nachpflege-Job (``termux/nachpflege-job.sh``) und die Einrichtung
  (``termux/nachpflege-einrichten.sh``) legen ihre Berichte in den
  **freigegebenen Download-Ordner** ``hermes_diag/``. Der Termux-Heimordner ist
  ueber das Kabel NICHT lesbar (App-Sandbox) — der freigegebene Ordner aber
  schon. Dieses Werkzeug holt den Diagnose-Ordner herunter und wertet ihn aus;
  es ist die PC-Gegenstelle zum neuen Beleg-Block in ``start-termux.sh``.

Die eigentliche Frage, die bisher offen war: **Steht die feste Job-Kennung
wirklich in der Job-Liste von Android?** Der Beleg-Block am Handy schreibt
genau das nach ``job_liste.txt``; dieses Werkzeug liest es aus und meldet eine
Zeile ``job_1901_belegt=ja|nein|unbekannt``.

Verhalten:
  * **Trockenlauf ist der Standard.** Ohne ``--holen`` wird nur die Dateiliste
    des Geraets ausgegeben (``adb shell ls -la <ordner>``) — es wird **nichts**
    geschrieben, Exit 0. Fehlt der Ordner auf dem Geraet, kommt eine ehrliche
    Zeile („Ordner auf dem Geraet nicht vorhanden\") und trotzdem Exit 0.
  * Mit ``--holen`` wird je **regulaerer** Datei (keine Unterordner) geholt:
      1. Ziel vorhanden und **gleiche Groesse** wie am Geraet -> ``uebersprungen``,
         es wird nichts geladen.
      2. Sonst: eine vorhandene Zieldatei wird **zuerst** als ``<name>.vorher``
         gesichert (Rueckweg), dann per ``adb pull`` in eine temp-Datei IM
         Zielordner geladen und danach per ``os.replace`` an ihren Platz
         gesetzt — es entsteht nie eine halbe Datei. Die Groesse der Kopie wird
         gegen die Anzeige des Geraets gehalten: Ungleichheit zaehlt ``fehler``
         und der Aufruf endet mit Exit 1.

Bericht (wird gedruckt): je Datei Name, Bytes und Zeit. **Der Inhalt** wird
  NUR von den beiden **technischen Berichten** ``job_liste.txt`` und
  ``nachpflege_letzte.txt`` ausgegeben (je auf 40 Zeilen gekappt); dazu die
  Zeile ``job_1901_belegt=ja|nein|unbekannt``. Der Inhalt von
  ``antworten_letzte.jsonl``, ``auftraege_letzte.jsonl``,
  ``status_letzte.jsonl`` und ``daemon_letzte.txt`` wird **NIE** ausgegeben
  (private Chat-/Auftragsinhalte) — von diesen Dateien erscheinen nur Name und
  Groesse. Diese Regel gilt hart und wird in ``test_belegweg_handy.py``
  geprueft.

Grenzen (hart):
  * **Kein Netz** ausser dem **lokalen** ``adb``-Aufruf (USB). Keine
    Netz-Bibliothek, kein Cloud-Abruf, kein LLM.
  * **Keine Loeschfunktion** ausser dem Ersetzen der **eigenen** temp-Datei
    eines abgebrochenen Ladens. Fremde Dateien werden nie geloescht.
  * **Kein Schluesselwert in Ausgaben oder Bericht** — der Inhalt privater
    Dateien wird gar nicht erst gelesen.
  * **Nur die Standardbibliothek.** Kein pip-Paket, kein git, kein Fremdaufruf
    ausser ``adb``.

Exit-Codes: 0 = sauber (auch wenn nichts zu holen war), 1 = Fehler beim Holen
  (oder bei ``--holen`` fehlt der Ordner auf dem Geraet), 2 = Aufruf- oder
  Schutzfehler (``--ziel`` liegt IM Repo).

Aufruf (Kommandozeile)::

    # Nur nachsehen, was auf dem Handy liegt (schreibt nichts):
    python tools/handy/diag_holen.py

    # Wirklich holen und auswerten:
    python tools/handy/diag_holen.py --holen

    # Fuer Tests: eine Attrappen-adb statt des echten Programms:
    python tools/handy/diag_holen.py --adb /pfad/zur/attrappe-adb --holen

Als Modul (Tests, Skripte): ``main(argv=[...]) -> int`` und die Funktionen
``dateiliste``, ``holen``, ``job_beleg_deuten``.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

# Vorgaben laut Auftrag.
STANDARD_ORDNER = "/sdcard/Download/hermes_diag"
STANDARD_ZIEL = os.path.join(os.path.expanduser("~"), "foto_sortierung",
                             "handy_diag")
STANDARD_ADB = "adb"

# Endung der eigenen temp-Datei beim atomaren Laden (wird nie dauerhaft).
TEMP_SUFFIX = ".teil"

# Suffix der Sicherung: eine vorhandene alte Ziel-Fassung liegt danach als
# "<name>.vorher" daneben — der Rueckweg bleibt offen.
VORHER_SUFFIX = ".vorher"

# Die beiden Dateien, deren INHALT gezeigt werden darf: technische Berichte,
# keine privaten Chat-/Auftragsinhalte.
TECHNISCHE_BERICHTE = ("job_liste.txt", "nachpflege_letzte.txt")

# Die feste Job-Kennung des Nachpflege-Jobs (Quelle:
# termux/nachpflege-einrichten.sh, JOB_ID). Nur fuer die Beleg-Zeile.
JOB_ID = 1901

# Hoechstzahl der gezeigten Inhaltszeilen je technischem Bericht.
INHALT_MAX_ZEILEN = 40


# ── Kleine Helfer ──────────────────────────────────────────────────────────

def _text(wert) -> str:
    """Ein Feld als Text lesen — Nicht-Text und ``None`` werden zu ``""``."""
    return wert.strip() if isinstance(wert, str) else ""


def _bytes(n) -> str:
    """Eine Byte-Zahl als Text (nur fuer die Ausgabe, nie geraten)."""
    return str(n) if isinstance(n, int) else "?"


def _im_repo(pfad: str) -> bool:
    """Liegt der (aufgeloeste) Pfad IM Repo? Gross/Klein und Trenner egal."""
    ziel = os.path.normcase(os.path.abspath(pfad))
    repo = os.path.normcase(os.path.abspath(REPO))
    try:
        return os.path.commonpath([ziel, repo]) == repo
    except ValueError:                            # anderes Laufwerk: nie im Repo
        return False


def _adb_aufruf(adb: str, argumente: list) -> subprocess.CompletedProcess:
    """Einen **lokalen** ``adb``-Aufruf machen und die Ausgabe einsammeln.

    Es wird ausser ``adb`` nichts gestartet (kein Shell-Interpreter, kein
    Netz-Werkzeug). Fehlt das Programm, kommt eine ``FileNotFoundError`` nach
    oben — der Aufrufer meldet sie ehrlich.
    """
    return subprocess.run([adb] + list(argumente),
                          capture_output=True, text=True)


# ── 1. Lesen: die Dateiliste des Geraets ───────────────────────────────────

def dateiliste(adb: str, ordner: str) -> dict:
    """Die Dateiliste eines Geraete-Ordners holen (nur lesend).

    Ruft ``adb shell ls -la <ordner>`` und deutet die Zeilen aus. Rueckgabe::

        {"ok": bool,            # False, wenn der Ordner auf dem Geraet fehlt
         "eintraege": [{"name", "groesse", "art", "zeit"}, ...],
         "roh": "<Ausgabe>"}

    ``art`` ist ``datei`` (regulaer), ``ordner`` oder ``verknuepfung``. Es wird
    nichts geschrieben und nichts geaendert; ein fehlender Ordner ist kein
    Programmfehler, sondern ein Ergebnis (``ok=False``).
    """
    adb = _text(adb) or STANDARD_ADB
    ordner = _text(ordner)
    if not ordner:
        raise ValueError("Kein Geraete-Ordner angegeben (--ordner).")
    ergebnis = _adb_aufruf(adb, ["shell", "ls", "-la", ordner])
    roh = (ergebnis.stdout or "") + (ergebnis.stderr or "")
    if ergebnis.returncode != 0 or "No such file" in roh:
        return {"ok": False, "eintraege": [], "roh": roh.strip()}

    eintraege: list = []
    for zeile in (ergebnis.stdout or "").splitlines():
        if not zeile or zeile[0] not in "-dl":
            continue                                  # "total N" und Kopfzeilen
        felder = zeile.split()
        if len(felder) < 8:
            continue                                  # kein regulaeres ls -la
        name = felder[-1]
        if not name or name in (".", ".."):
            continue
        art = {"d": "ordner", "l": "verknuepfung"}.get(zeile[0], "datei")
        try:
            groesse = int(felder[4])
        except (TypeError, ValueError):
            groesse = None
        eintraege.append({"name": name, "groesse": groesse, "art": art,
                          "zeit": f"{felder[-3]} {felder[-2]}"})
    return {"ok": True, "eintraege": eintraege, "roh": (ergebnis.stdout or "").strip()}


# ── 2. Deuten: steht die Job-Kennung im Beleg? ─────────────────────────────

def job_beleg_deuten(inhalt: str) -> str:
    """Aus dem Inhalt von ``job_liste.txt`` die Lage der Job-Kennung ableiten.

    Rueckgabe ``ja`` (Kennung steht in der Liste), ``nein`` (steht nicht drin)
    oder ``unbekannt`` (keine Aussage moeglich). Gesucht wird die Zeile
    ``JOB_ID_GEFUNDEN=...``, die der Beleg-Block am Handy schreibt; fehlt sie,
    wird **nicht geraten**.
    """
    if not isinstance(inhalt, str):
        return "unbekannt"
    for zeile in inhalt.splitlines():
        sauber = zeile.strip()
        if sauber.startswith("JOB_ID_GEFUNDEN="):
            wert = sauber.split("=", 1)[1].strip().lower()
            if wert in ("ja", "nein", "unbekannt"):
                return wert
    return "unbekannt"


# ── 3. Die eine Loeschstelle und das atomare Laden ─────────────────────────

def _entferne(pfad: str) -> None:
    """Die **einzige** Loeschstelle dieses Moduls — nur die eigene temp-Datei.

    Geloescht wird ausschliesslich die eigene temp-Datei eines abgebrochenen
    Ladens, damit kein Rest im Zielordner liegen bleibt. Eine vorhandene
    Zieldatei wird nie geloescht (sie wurde zuvor als ``.vorher`` gesichert).
    """
    if os.path.exists(pfad):
        os.remove(pfad)


def _sichere_vorher(ziel: str) -> str:
    """Eine vorhandene Zieldatei als ``<ziel>.vorher`` beiseitelegen.

    Bewusst ein einfaches Schreiben: dies ist der Rueckweg, dort ist eine
    Kopie richtig. Gibt den Pfad der Sicherung zurueck.
    """
    sicherung = ziel + VORHER_SUFFIX
    with open(ziel, "rb") as ein:
        daten = ein.read()
    with open(sicherung, "wb") as aus:
        aus.write(daten)
    return sicherung


def _hole_eine(adb: str, quelle: str, ziel: str) -> str:
    """Eine Geraetedatei atomar in den Zielordner laden.

    Erst per ``adb pull`` in ``<ziel>.teil`` IM Zielordner, dann ``os.replace``:
    es entsteht nie eine halbe Zieldatei. Bricht das Laden ab, wird
    ausschliesslich die eigene temp-Datei entfernt. Gibt den Zielpfad zurueck.
    """
    temp_pfad = ziel + TEMP_SUFFIX
    os.makedirs(os.path.dirname(os.path.abspath(ziel)), exist_ok=True)
    ergebnis = _adb_aufruf(adb, ["pull", quelle, temp_pfad])
    if ergebnis.returncode != 0 or not os.path.isfile(temp_pfad):
        _entferne(temp_pfad)
        roh = (ergebnis.stderr or ergebnis.stdout or "").strip()
        raise OSError(f"adb pull fehlgeschlagen ({roh or 'keine Ausgabe'})")
    os.replace(temp_pfad, ziel)
    return ziel


# ── 4. Holen (fuehrt den Plan aus) ─────────────────────────────────────────

def holen(adb: str, ordner: str, zielordner: str, eintraege) -> dict:
    """Die regulaeren Dateien aus ``eintraege`` in den Zielordner holen.

    Rueckgabe (Woerterbuch)::

        {"zaehler": {"geholt", "uebersprungen", "fehler"},
         "zeilen":  ["<name>: ...", ...],
         "fehler":  bool}

    Ablauf je Datei siehe Modulkopf (gleiche Groesse -> ``uebersprungen``;
    sonst Sicherung als ``.vorher``, temp-Datei, ``os.replace``, Groessenprobe).
    Unterordner und Verknuepfungen werden nicht angefasst.
    """
    zaehler = {"geholt": 0, "uebersprungen": 0, "fehler": 0}
    zeilen: list = []
    fehler = False
    ordner = _text(ordner).rstrip("/")
    os.makedirs(zielordner, exist_ok=True)

    for eintrag in eintraege or []:
        name = eintrag.get("name")
        art = eintrag.get("art")
        groesse_geraet = eintrag.get("groesse")
        zeit = eintrag.get("zeit") or "-"
        if not name:
            continue
        if art != "datei":
            zeilen.append(f"{name}: uebersprungen (keine regulaere Datei, art={art})")
            zaehler["uebersprungen"] += 1
            continue

        ziel = os.path.join(zielordner, name)
        if (os.path.isfile(ziel) and isinstance(groesse_geraet, int)
                and os.path.getsize(ziel) == groesse_geraet):
            zaehler["uebersprungen"] += 1
            zeilen.append(f"{name}: uebersprungen (gleiche Groesse "
                          f"{_bytes(groesse_geraet)} Bytes, {zeit})")
            continue

        quelle = f"{ordner}/{name}"
        try:
            if os.path.exists(ziel):
                _sichere_vorher(ziel)             # Rueckweg zuerst
            _hole_eine(adb, quelle, ziel)
        except OSError as problem:
            zaehler["fehler"] += 1
            fehler = True
            zeilen.append(f"{name}: FEHLER beim Laden "
                          f"({problem.__class__.__name__}) - temp-Datei entfernt")
            continue

        laenge = os.path.getsize(ziel)
        if isinstance(groesse_geraet, int) and laenge != groesse_geraet:
            zaehler["fehler"] += 1
            fehler = True
            zeilen.append(f"{name}: FEHLER Groesse weicht ab (Geraet "
                          f"{_bytes(groesse_geraet)}, Kopie {_bytes(laenge)} Bytes)")
            continue

        zaehler["geholt"] += 1
        zeilen.append(f"{name}: geholt ({_bytes(laenge)} Bytes, {zeit})")

    return {"zaehler": zaehler, "zeilen": zeilen, "fehler": fehler}


# ── 5. Ausgabe (Klartext deutsch) ──────────────────────────────────────────

def _inhalt_text(zielordner: str, name: str) -> str:
    """Den Inhalt eines Berichts als Text lesen (nur fuer technische Berichte)."""
    pfad = os.path.join(zielordner, name)
    if not os.path.isfile(pfad):
        return ""
    try:
        with open(pfad, "r", encoding="utf-8", errors="replace") as datei:
            return datei.read()
    except OSError:
        return ""


def _inhalt_zeigen(zielordner: str, name: str) -> list:
    """Den Inhalt eines **technischen** Berichts als gekappte Zeilenliste.

    Nur fuer ``TECHNISCHE_BERICHTE`` gedacht. Fehlt die Datei, kommt eine
    ehrliche Zeile zurueck, keine leere Ausgabe.
    """
    pfad = os.path.join(zielordner, name)
    if not os.path.isfile(pfad):
        return [f"({name}: nicht vorhanden)"]
    text = _inhalt_text(zielordner, name)
    if not text:
        return [f"({name}: leer oder nicht lesbar)"]
    return text.splitlines()[-INHALT_MAX_ZEILEN:]


def _bericht_drucken(ergebnis: dict, zielordner: str) -> None:
    """Den Bericht drucken: je Datei Name + Bytes + Zeit, Inhalt nur technisch."""
    for zeile in ergebnis["zeilen"]:
        print("  " + zeile)
    z = ergebnis["zaehler"]
    print(f"Zusammenfassung: geholt {z['geholt']} - uebersprungen "
          f"{z['uebersprungen']} - Fehler {z['fehler']}")

    print("Inhalt der technischen Berichte (gekappt auf "
          f"{INHALT_MAX_ZEILEN} Zeilen):")
    for name in TECHNISCHE_BERICHTE:
        print(f"--- {name} ---")
        for zeile in _inhalt_zeigen(zielordner, name):
            print("  " + zeile)

    beleg = job_beleg_deuten(_inhalt_text(zielordner, "job_liste.txt"))
    print(f"job_{JOB_ID}_belegt={beleg}")


# ── 6. Kommandozeile ─────────────────────────────────────────────────────

def main(argv=None) -> int:
    """Kommandozeile: Diagnose-Ordner vom Handy holen (Trockenlauf als Standard).

    ``--ordner`` (Standard ``/sdcard/Download/hermes_diag``), ``--ziel``
    (Standard ``~/foto_sortierung/handy_diag``), ``--adb`` (Standard ``adb``)
    und ``--holen`` (ohne diesen Schalter wird **nichts** geschrieben).
    Exit 0 = sauber, 1 = Fehler beim Holen oder fehlender Geraete-Ordner,
    2 = Schutzfehler (``--ziel`` IM Repo).
    """
    zerleger = argparse.ArgumentParser(
        description="Diagnose-Ordner vom Handy per Kabel holen und auswerten - "
                    "nur lesend, kein Netz ausser dem lokalen adb-Aufruf, "
                    "Inhalte privater Dateien werden nie gezeigt.")
    zerleger.add_argument("--ordner", dest="ordner", default=STANDARD_ORDNER,
                          help=f"Geraete-Ordner (Standard {STANDARD_ORDNER})")
    zerleger.add_argument("--ziel", dest="ziel", default=STANDARD_ZIEL,
                          help=f"Zielordner am PC (Standard {STANDARD_ZIEL})")
    zerleger.add_argument("--adb", dest="adb", default=STANDARD_ADB,
                          help="adb-Programm (Standard 'adb', fuer Tests "
                               "durch eine Attrappe ersetzbar)")
    zerleger.add_argument("--holen", dest="holen", action="store_true",
                          help="wirklich holen; ohne diesen Schalter nur die "
                               "Dateiliste zeigen (Trockenlauf)")
    args = zerleger.parse_args(argv)

    ordner = _text(args.ordner)
    ziel = _text(args.ziel)
    adb = _text(args.adb) or STANDARD_ADB
    if not ordner or not ziel:
        print("Fehler: --ordner und --ziel duerfen nicht leer sein.",
              file=sys.stderr)
        return 2
    if _im_repo(ziel):
        print(f"Fehler: --ziel liegt IM Repo und ist nicht erlaubt: {ziel}\n"
              f"Es wird NICHTS geschrieben.", file=sys.stderr)
        return 2

    try:
        liste = dateiliste(adb, ordner)
    except (OSError, ValueError) as problem:
        print(f"Fehler: Geraet nicht erreichbar ({problem.__class__.__name__}) - "
              f"haengt das Kabel und laeuft adb?", file=sys.stderr)
        return 1

    if not liste["ok"]:
        print(f"Ordner auf dem Geraet nicht vorhanden: {ordner}")
        if liste["roh"]:
            print("  " + liste["roh"].splitlines()[-1])
        return 1 if args.holen else 0

    regulaer = [e for e in liste["eintraege"] if e["art"] == "datei"]
    print(f"Diagnose-Ordner: {ordner}")
    print(f"Dateien auf dem Geraet ({len(regulaer)} regulaere):")
    for e in liste["eintraege"]:
        kennung = "" if e["art"] == "datei" else f" [{e['art']}]"
        print(f"  {e['name']}{kennung}: {_bytes(e['groesse'])} Bytes ({e['zeit']})")

    if not args.holen:
        print("Trockenlauf (Standard): es wurde nichts geschrieben. "
              "Zum Holen --holen setzen.")
        print(f"job_{JOB_ID}_belegt=unbekannt (Trockenlauf: Inhalt nicht gelesen)")
        return 0

    ergebnis = holen(adb, ordner, ziel, liste["eintraege"])
    print(f"Ziel: {ziel}")
    _bericht_drucken(ergebnis, ziel)
    if ergebnis["fehler"]:
        print("Fehler: mindestens eine Datei ist gescheitert.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
