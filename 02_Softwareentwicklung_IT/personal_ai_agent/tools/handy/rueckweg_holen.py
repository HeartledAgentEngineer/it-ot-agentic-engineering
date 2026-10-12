"""Rueckweg Handy -> PC: eigene Datendateien per Kabel holen (12.10.2026).

Warum dieses Werkzeug:
  Die Uebergabe laeuft bisher NUR in eine Richtung: der PC legt Dateien in den
  freigegebenen Download-Ordner (bzw. in die pCloud), das Handy holt sie
  (``tools/handy/uebergabe_uebernehmen.py``, ``termux/pcloud-uebernehmen.sh``).
  Die Dateien, die die **App am Handy erzeugt**, haben dagegen **keinen Weg
  zurueck**: ``geschichten.jsonl`` (die eigenen Erzaehlungen zu Anlaessen und
  ``anlass_umbenennung.jsonl`` (eigene Anlassnamen) liegen im Termux-Heimordner
  ``$HOME/foto_sortierung`` — der ist ueber das Kabel NICHT lesbar (gemessen:
  ``adb shell ls`` auf diesen Pfad endet mit „Permission denied\\\").

  Deshalb stellt das Handy diese Dateien mit ``termux/rueckweg-bereitstellen.sh``
  in den **freigegebenen** Ordner ``/sdcard/Download/hermes_rueckweg``
  (kopieren, nie verschieben) — dieses Werkzeug holt sie von dort ab und legt
  sie an ihren PC-Platz, wo der Nachweis (``bestand_pruefen.py``, Abschnitte
  „Eigene Geschichten\\\" / „Eigene Titel\\\") und der Dienst sie erwarten.

Verhalten:
  * **Trockenlauf ist der Standard.** Ohne ``--holen`` wird nur die Dateiliste
    des Geraets gezeigt — es wird **nichts** geschrieben, Exit 0. Fehlt der
    Ordner auf dem Geraet, kommt eine ehrliche Zeile („Ordner auf dem Geraet
    nicht vorhanden\\\") und Exit 0 (Trockenlauf) bzw. Exit 1 (mit ``--holen``).
  * Mit ``--holen`` wird je **regulaerer** Datei aus der **Liste**
    (``ERLAUBTE_NAMEN``) geholt:
      1. Ziel vorhanden und **gleiche Groesse** wie am Geraet -> ``uebersprungen``.
      2. Sonst: eine vorhandene Zieldatei wird **zuerst** als ``<name>.vorher``
         gesichert (Rueckweg), dann per ``adb pull`` in eine temp-Datei IM
         Zielordner geladen und danach per ``os.replace`` an ihren Platz
         gesetzt — es entsteht nie eine halbe Zieldatei. Die Groesse der Kopie
         wird gegen die Anzeige des Geraets gehalten; Ungleichheit zaehlt
         ``fehler`` und der Aufruf endet mit Exit 1.
      3. Jede wirklich geholte Datei bucht **eine** Zeile in das Manifest
         (``--manifest``, Standard ``~/foto_sortierung/rueckweg_manifest.jsonl``):
         Name, Bytes, sha256, Zeit. Das Manifest ist der Beleg, was den Weg
         genommen hat (AGENTS.md, Punkt 5: Rueckholbarkeit).
  * **Nur die Liste wird geholt.** Jede andere Datei im Geraete-Ordner wird
    als Zeile gemeldet („nicht in der Liste, wird nicht geholt\\\") und
    **nicht** angefasst — der Ordner ist ein Download-Ordner, da liegt alles
    Moegliche.

Bericht (wird gedruckt): je Datei Name, Bytes und Zeit. **Der Inhalt** der
  Dateien wird NIE ausgegeben (eigene Erzaehlungen = private Texte); es
  erscheinen nur Name, Groesse, Zeit und — im Manifest — die Pruefsumme.

Grenzen (hart):
  * **Kein Netz** ausser dem **lokalen** ``adb``-Aufruf (USB). Kein HTTP, keine
    pCloud, kein LLM, kein Sockel.
  * **Kein Verteilen auf fremde Systeme:** das Ziel liegt in ``~/``, ein
    ``--ziel`` IM Repo wird mit Exit 2 abgelehnt.
  * **Keine Loeschfunktion** ausser dem Entfernen der **eigenen** temp-Datei
    eines abgebrochenen Ladens. Auf dem Geraet wird **nichts** geschrieben oder
    geloescht (nur ``ls`` und ``pull`` = lesend).
  * **Nur die Standardbibliothek.** Kein pip-Paket, kein git.

Exit-Codes: 0 = sauber (auch wenn nichts zu holen war), 1 = Fehler beim Holen
  (oder bei ``--holen`` fehlt der Ordner auf dem Geraet), 2 = Aufruf- oder
  Schutzfehler (``--ziel`` liegt IM Repo).

Aufruf (Kommandozeile)::

    # Nur nachsehen, was das Handy bereitgestellt hat (schreibt nichts):
    python tools/handy/rueckweg_holen.py

    # Wirklich holen und ins Manifest buchen:
    python tools/handy/rueckweg_holen.py --holen

    # Fuer Tests: eine Attrappen-adb statt des echten Programms:
    python tools/handy/rueckweg_holen.py --adb /pfad/zur/attrappe-adb --holen

Als Modul (Tests, Skripte): ``main(argv=[...]) -> int`` und die Funktionen
``dateiliste``, ``auswahl``, ``holen``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

# Vorgaben (Geraeteordner = derselbe Name, den termux/rueckweg-bereitstellen.sh
# fuellt).
STANDARD_ORDNER = "/sdcard/Download/hermes_rueckweg"
STANDARD_ZIEL = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_MANIFEST = os.path.join(os.path.expanduser("~"), "foto_sortierung",
                                 "rueckweg_manifest.jsonl")
STANDARD_ADB = "adb"

# Die Dateien, die den Rueckweg nehmen duerfen: das sind die von der APP AM
# GERÄT erzeugten Datendateien, die der PC fuer den Nachweis und den Dienst
# braucht. Die Liste steht WORTGLEICH auch in termux/rueckweg-bereitstellen.sh
# (RUECKWEG_NAMEN) — ein Waechter-Test haelt beide Mengen zusammen, damit sie
# nicht auseinanderlaufen.
ERLAUBTE_NAMEN = ("geschichten.jsonl", "anlass_umbenennung.jsonl")

# Endung der eigenen temp-Datei beim atomaren Laden (wird nie dauerhaft).
TEMP_SUFFIX = ".teil"

# Suffix der Sicherung: eine vorhandene alte Ziel-Fassung liegt danach als
# "<name>.vorher" daneben — der Rueckweg bleibt offen.
VORHER_SUFFIX = ".vorher"


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


def _sha256_datei(pfad: str) -> str:
    """Die sha256 einer Datei blockweise lesen (nur lesend, wirft nie)."""
    try:
        kasten = hashlib.sha256()
        with open(pfad, "rb") as datei:
            for block in iter(lambda: datei.read(1024 * 1024), b""):
                kasten.update(block)
        return kasten.hexdigest()
    except OSError:
        return ""


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


# ── 2. Auswahl: nur die Liste ──────────────────────────────────────────────

def auswahl(eintraege, erlaubte=ERLAUBTE_NAMEN) -> dict:
    """Aus der Geraeteliste die erlaubten von den uebrigen trennen.

    Rueckgabe ``{"erlaubt": [...], "ignoriert": [...]}``. ``ignoriert`` sind die
    Namen der regulaeren Dateien, die **nicht** in der Liste stehen — sie werden
    gemeldet, aber nie geholt. Unterordner und Verknuepfungen erscheinen in
    keiner der beiden Listen (sie werden ohnehin nicht angefasst).
    """
    satz = {n for n in (erlaubte or ()) if _text(n)}
    erlaubt: list = []
    ignoriert: list = []
    for eintrag in eintraege or []:
        if not isinstance(eintrag, dict) or eintrag.get("art") != "datei":
            continue
        name = _text(eintrag.get("name"))
        if not name:
            continue
        (erlaubt if name in satz else ignoriert).append(eintrag)
    return {"erlaubt": erlaubt, "ignoriert": ignoriert}


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


# ── 4. Manifest (der Beleg) ────────────────────────────────────────────────

def _buchung(name: str, ziel: str, zeit: str = "") -> dict:
    """Eine Manifest-Zeile fuer eine geholte Datei bauen (nur Zahlen + Name)."""
    return {
        "name": name,
        "bytes": os.path.getsize(ziel) if os.path.isfile(ziel) else None,
        "sha256": _sha256_datei(ziel),
        "zeit": zeit or "",
        "richtung": "handy->pc",
    }


def _manifest_anhaengen(pfad: str, buchungen) -> str:
    """Buchungen als je eine JSON-Zeile anhaengen (nur anhaengend, wirft nie).

    Gibt ``""`` zurueck, wenn nichts gebucht wurde, sonst den Pfad. Fehlt der
    Zielordner, wird er angelegt; schlaegt das Schreiben fehl, kommt eine
    leere Zeichenkette zurueck (der Bericht nennt es dann ehrlich).
    """
    if not buchungen:
        return ""
    try:
        ordner = os.path.dirname(os.path.abspath(pfad))
        if ordner:
            os.makedirs(ordner, exist_ok=True)
        with open(pfad, "a", encoding="utf-8") as datei:
            for buchung in buchungen:
                datei.write(json.dumps(buchung, ensure_ascii=False, sort_keys=True))
                datei.write("\n")
        return pfad
    except OSError:
        return ""


# ── 5. Holen (fuehrt den Plan aus) ─────────────────────────────────────────

def holen(adb: str, ordner: str, zielordner: str, eintraege,
          manifest: str | None = None, zeit: str = "") -> dict:
    """Die erlaubten regulaeren Dateien aus ``eintraege`` in den Zielordner holen.

    Rueckgabe (Woerterbuch)::

        {"zaehler": {"geholt", "uebersprungen", "ignoriert", "fehler"},
         "zeilen":  ["<name>: ...", ...],
         "buchungen": [<Manifest-Zeile>, ...],
         "manifest": "<Pfad oder ''>",
         "fehler":  bool}

    Ablauf je Datei siehe Modulkopf (gleiche Groesse -> ``uebersprungen``;
    sonst Sicherung als ``.vorher``, temp-Datei, ``os.replace``, Groessenprobe,
    Buchung). Alles, was nicht in der Liste steht, zaehlt ``ignoriert`` und
    bleibt unangetastet.
    """
    zaehler = {"geholt": 0, "uebersprungen": 0, "ignoriert": 0, "fehler": 0}
    zeilen: list = []
    buchungen: list = []
    fehler = False
    ordner = _text(ordner).rstrip("/")
    geteilt = auswahl(eintraege)
    os.makedirs(zielordner, exist_ok=True)

    for eintrag in geteilt["ignoriert"]:
        zaehler["ignoriert"] += 1        # gemeldet wird das schon in der Liste

    for eintrag in geteilt["erlaubt"]:
        name = _text(eintrag.get("name"))
        groesse_geraet = eintrag.get("groesse")
        zeit_geraet = eintrag.get("zeit") or "-"
        ziel = os.path.join(zielordner, name)
        if (os.path.isfile(ziel) and isinstance(groesse_geraet, int)
                and os.path.getsize(ziel) == groesse_geraet):
            zaehler["uebersprungen"] += 1
            zeilen.append(f"{name}: uebersprungen (gleiche Groesse "
                          f"{_bytes(groesse_geraet)} Bytes, {zeit_geraet})")
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
        zeilen.append(f"{name}: geholt ({_bytes(laenge)} Bytes, {zeit_geraet})")
        buchungen.append(_buchung(name, ziel, zeit))

    gebucht = _manifest_anhaengen(manifest, buchungen) if manifest else ""
    return {"zaehler": zaehler, "zeilen": zeilen, "buchungen": buchungen,
            "manifest": gebucht, "fehler": fehler}


# ── 6. Ausgabe (Klartext deutsch) ──────────────────────────────────────────

def _bericht_drucken(ergebnis: dict, zielordner: str) -> None:
    """Den Bericht drucken: je Datei Name + Bytes + Zeit, nie ein Inhalt."""
    for zeile in ergebnis["zeilen"]:
        print("  " + zeile)
    z = ergebnis["zaehler"]
    print(f"Zusammenfassung: geholt {z['geholt']} - uebersprungen "
          f"{z['uebersprungen']} - nicht in der Liste {z['ignoriert']} - "
          f"Fehler {z['fehler']}")
    print(f"Ziel: {zielordner}")
    if ergebnis["manifest"]:
        print(f"Manifest: {ergebnis['manifest']} "
              f"({len(ergebnis['buchungen'])} Buchung(en))")


# ── 7. Kommandozeile ───────────────────────────────────────────────────────

def main(argv=None) -> int:
    """Kommandozeile: Rueckweg-Dateien vom Handy holen (Trockenlauf als Standard).

    ``--ordner`` (Standard ``/sdcard/Download/hermes_rueckweg``), ``--ziel``
    (Standard ``~/foto_sortierung``), ``--manifest``,
    ``--adb`` (Standard ``adb``) und ``--holen`` (ohne diesen Schalter wird
    **nichts** geschrieben). Exit 0 = sauber, 1 = Fehler beim Holen oder
    fehlender Geraete-Ordner mit ``--holen``, 2 = Schutzfehler (``--ziel``
    IM Repo).
    """
    zerleger = argparse.ArgumentParser(
        description="Rueckweg Handy -> PC: die von der App am Geraet erzeugten "
                    "Datendateien per Kabel holen - nur lesend am Geraet, kein "
                    "Netz ausser dem lokalen adb-Aufruf, Inhalte werden nie "
                    "gezeigt, Ziel IM Repo wird abgelehnt.")
    zerleger.add_argument("--ordner", dest="ordner", default=STANDARD_ORDNER,
                          help=f"Geraete-Ordner (Standard {STANDARD_ORDNER})")
    zerleger.add_argument("--ziel", dest="ziel", default=STANDARD_ZIEL,
                          help=f"Zielordner am PC (Standard {STANDARD_ZIEL})")
    zerleger.add_argument("--manifest", dest="manifest", default=STANDARD_MANIFEST,
                          help=f"Manifest der Buchungen (Standard {STANDARD_MANIFEST})")
    zerleger.add_argument("--adb", dest="adb", default=STANDARD_ADB,
                          help="adb-Programm (Standard 'adb', fuer Tests "
                               "durch eine Attrappe ersetzbar)")
    zerleger.add_argument("--holen", dest="holen", action="store_true",
                          help="wirklich holen; ohne diesen Schalter nur die "
                               "Dateiliste zeigen (Trockenlauf)")
    zerleger.add_argument("--zeit", dest="zeit", default="",
                          help="Zeitstempel fuer das Manifest (leer = keiner)")
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
        print("  (Das Handy stellt ihn mit termux/rueckweg-bereitstellen.sh bereit.)")
        return 1 if args.holen else 0

    geteilt = auswahl(liste["eintraege"])
    print(f"Rueckweg-Ordner: {ordner}")
    print(f"Dateien auf dem Geraet ({len(geteilt['erlaubt'])} aus der Liste, "
          f"{len(geteilt['ignoriert'])} andere):")
    for e in geteilt["erlaubt"]:
        print(f"  {e['name']}: {_bytes(e['groesse'])} Bytes ({e['zeit']})")
    for e in geteilt["ignoriert"]:
        print(f"  {e['name']}: nicht in der Liste, wird nicht geholt")

    if not args.holen:
        print("Trockenlauf (Standard): es wurde nichts geschrieben. "
              "Zum Holen --holen setzen.")
        return 0

    ergebnis = holen(adb, ordner, ziel, liste["eintraege"],
                     manifest=args.manifest, zeit=args.zeit)
    _bericht_drucken(ergebnis, ziel)
    if ergebnis["fehler"]:
        print("Fehler: mindestens eine Datei ist gescheitert.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
