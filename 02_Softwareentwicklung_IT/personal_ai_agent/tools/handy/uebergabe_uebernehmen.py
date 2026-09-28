"""Uebergabedateien vom PC aufs Handy uebernehmen (Nachtlauf-Schritt N13c, 28.09.2026).

Warum dieses Werkzeug:
  Zwei Dateien entstehen am PC und werden am Handy gebraucht:
  ``fotos_dateien.json`` (Datei-Kennungen fuer die Bildvorschau) und
  ``fotos_uebersicht.json`` (die Zahlen der Uebersicht). Das Backend liest sie
  unter ``$HOME/foto_sortierung/``. Ueber die Leitung kommt man dort NICHT hin:
  der Termux-Heimordner ist ueber das Kabel nicht beschreibbar (App-Sandbox).
  Deshalb legt der PC die Dateien per Kabel in den **freigegebenen
  Download-Ordner** (``/sdcard/Download``) — und dieses Werkzeug holt sie beim
  Start in den Heimordner. Es ist der Zwilling der beiden Uebernahmen im
  Startskript (Archiv-Index, Einstellungsdatei), mit **einer** Verscharfung:
  hier wird die Pruefsumme HART verglichen, und eine unbrauchbare Uebertragung
  bleibt liegen, statt still eine halbe Datei zu hinterlassen.

Verhalten je Datei (in der Reihenfolge von ``--dateien``):
  1. Uebergabedatei fehlt  -> Zaehler ``uebersprungen``; kein Fehler, keine
     Ausgabedatei. (Der Normalfall ab dem zweiten Start.)
  2. Zieldatei vorhanden und gleiche ``sha256``  -> Zaehler ``unveraendert``;
     die Uebergabedatei wird entfernt (es gibt nichts zu uebertragen).
  3. Sonst: eine vorhandene Zieldatei wird **zuerst** nach
     ``ZIEL/NAME+--vorher-suffix`` kopiert (Rueckweg, es wird nichts
     ueberschrieben ohne Sicherung), dann wird uebertragen — temp-Datei im
     Zielordner plus ``os.replace``, damit nie eine halbe Datei entsteht.
     Danach wird die Pruefsumme der Quelle gegen die des Ziels gehalten:
     nur bei Gleichheit zaehlt ``uebernommen`` UND die Uebergabedatei wird
     entfernt. Bei Ungleichheit zaehlt ``fehler``, die Uebergabedatei bleibt
     liegen und der Aufruf endet mit Exit 1.

Grenzen (hart):
  * **Kein Netz.** Keine HTTP-Bibliothek, kein Sockel-Zugriff, kein
    Cloud-Abruf, kein LLM — es wird nur das lokale Dateisystem gelesen.
  * **Kein git, kein Fremdaufruf.** Es wird keine Shell gestartet und nichts
    geladen; die einzigen Dateien sind Quelle, Ziel, Sicherung, temp-Datei
    und das Protokoll.
  * **Keine Loeschung** ausser an **einer** Stelle im Quelltext
    (``_entferne``): dort faellt die eigene Uebergabedatei nach bestandener
    Pruefung weg oder die eigene temp-Datei eines abgebrochenen Schreibens.
    Sonst gibt es keine Loeschfunktion, auch nicht "zur Sicherheit".
  * **Kein Schluesselwert in Ausgaben oder Protokoll.** Gemeldet werden nur
    Dateiname, Groesse, Pruefsumme und Zustaende — nichts davon ist geheim,
    und das Protokoll liegt im freigegebenen Download-Ordner.

Exit-Codes: 0 = sauber (auch wenn nichts zu tun war), 1 = Fehler bei einer
Uebernahme, 2 = Aufruf- oder Schutzfehler (fehlendes ``--quelle``/``--ziel``,
kein ``--dateien``, ``--ziel`` oder ``--protokoll`` im Repo).

Aufruf (Kommandozeile)::

    python tools/handy/uebergabe_uebernehmen.py \
        --quelle /sdcard/Download --ziel $HOME/foto_sortierung \
        --dateien fotos_dateien.json fotos_uebersicht.json \
        --protokoll /sdcard/Download/hermes_diag/uebergabe_letzte.txt

Als Modul (Tests, Skripte): ``main(argv=[...]) -> int`` und die Funktionen
``sha256_datei``, ``uebernahme_planen``, ``uebernehmen``.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

# Vorgabe-Suffix der Sicherung: eine vorhandene alte Fassung des Ziels liegt
# danach als "<name>.vorher" daneben — der Rueckweg bleibt offen.
STANDARD_VORHER_SUFFIX = ".vorher"

# Endung der eigenen temp-Datei beim atomaren Schreiben (wird nie dauerhaft).
TEMP_SUFFIX = ".teil"

# Zustaende einer Datei im Uebernahmeplan.
ZUSTAND_FEHLT = "fehlt"
ZUSTAND_UNVERAENDERT = "unveraendert"
ZUSTAND_UEBERNEHMEN = "uebernehmen"

# Namen der Zaehler (deutsch, stehen so im Bericht und im Protokoll).
ZAEHLER_UEBERNOMMEN = "uebernommen"
ZAEHLER_UNVERAENDERT = "unveraendert"
ZAEHLER_UEBERSPRUNGEN = "uebersprungen"
ZAEHLER_FEHLER = "fehler"
ZAEHLER_NAMEN = (ZAEHLER_UEBERNOMMEN, ZAEHLER_UNVERAENDERT,
                 ZAEHLER_UEBERSPRUNGEN, ZAEHLER_FEHLER)


# ── Kleine Helfer (tolerant lesen, nie raten) ─────────────────────────────

def _text(wert) -> str:
    """Ein Feld als Text lesen — Nicht-Text und ``None`` werden zu ``\"\"``."""
    return wert.strip() if isinstance(wert, str) else ""


def _zahl(n) -> str:
    """Eine Zahl mit deutschen Tausenderpunkten (nur fuer die Ausgabe)."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def _kurz(pruefsumme) -> str:
    """Die ersten Stellen einer Pruefsumme fuer den Bericht (nie der ganze Wert)."""
    return pruefsumme[:12] if isinstance(pruefsumme, str) and pruefsumme else "-"


# ── 1. Lesen: Pruefsumme, sonst nichts ────────────────────────────────────

def sha256_datei(pfad: str) -> str:
    """Die ``sha256``-Pruefsumme einer Datei bilden (nur lesend, blockweise).

    Blockweise (64 KiB), damit auch eine grosse Datei nicht komplett in den
    Arbeitsspeicher muss. Fehlender Pfad oder unlesbare Datei ergeben eine
    deutsche ``ValueError``-Meldung — es wird nicht geraten und nichts
    stillschweigend als leer behandelt.
    """
    if not _text(pfad):
        raise ValueError("Kein Pfad fuer die Pruefsumme angegeben.")
    if not os.path.isfile(pfad):
        raise ValueError(f"Datei fuer die Pruefsumme nicht gefunden: {pfad}")
    pruefer = hashlib.sha256()
    try:
        with open(pfad, "rb") as datei:
            while True:
                stueck = datei.read(65536)
                if not stueck:
                    break
                pruefer.update(stueck)
    except OSError as problem:
        raise ValueError(
            f"Datei nicht lesbar ({problem.__class__.__name__}): {pfad}") from None
    return pruefer.hexdigest()


# ── 2. Planen (reine Funktion: liest nur, schreibt nichts) ────────────────

def _pruefe_namen(roh) -> str:
    """Einen Namen aus ``--dateien`` pruefen und zurueckgeben.

    Erlaubt ist **nur ein reiner Dateiname** ohne Pfadanteil. Waere ein Pfad
    erlaubt, koennte ein Aufruf ausserhalb des Zielordners schreiben — die
    Uebergabe soll genau im Zielordner landen und nirgends sonst.
    """
    name = _text(roh)
    if not name:
        raise ValueError("Ein Eintrag in --dateien ist leer.")
    if name in (".", "..") or "/" in name or "\\" in name:
        raise ValueError(
            f"Ungueltiger Name in --dateien (nur ein Dateiname, kein Pfad): {roh}")
    return name


def uebernahme_planen(quelle: str, ziel: str, dateien,
                      *, vorher_suffix: str = STANDARD_VORHER_SUFFIX) -> list:
    """Den Uebernahmeplan bauen — **rein**: es wird gelesen, nichts geschrieben.

    Je Name aus ``dateien`` entsteht ein Eintrag mit Name, Quell- und
    Zielpfad, dem Pfad der Sicherung, dem Zustand (``fehlt`` /
    ``unveraendert`` / ``uebernehmen``), der Groesse und, soweit vorhanden,
    den Pruefsummen von Quelle und Ziel. Es wird keine Datei angelegt,
    geaendert oder entfernt; ein Aufruf zweimal hintereinander liefert
    denselben Plan.

    ``ValueError`` (deutsch) bei fehlender Quelle/Ziel-Angabe, leerer
    Dateiliste, untauglichem Namen oder leerem Vorher-Suffix.
    """
    if not _text(quelle) or not _text(ziel):
        raise ValueError("Quelle und Ziel muessen beide angegeben sein.")
    if not dateien:
        raise ValueError("Es wurde keine Uebergabedatei angegeben (--dateien).")
    if not _text(vorher_suffix):
        raise ValueError("Das Vorher-Suffix darf nicht leer sein.")

    plan = []
    for roh in dateien:
        name = _pruefe_namen(roh)
        quelle_pfad = os.path.join(quelle, name)
        ziel_pfad = os.path.join(ziel, name)
        eintrag = {
            "name": name,
            "quelle": quelle_pfad,
            "ziel": ziel_pfad,
            "vorher": ziel_pfad + vorher_suffix,
            "zustand": ZUSTAND_FEHLT,
            "groesse": None,
            "sha256_quelle": None,
            "sha256_ziel": None,
        }
        if not os.path.isfile(quelle_pfad):
            plan.append(eintrag)                 # nichts zu uebertragen
            continue
        eintrag["groesse"] = os.path.getsize(quelle_pfad)
        eintrag["sha256_quelle"] = sha256_datei(quelle_pfad)
        if os.path.exists(ziel_pfad):
            if os.path.isfile(ziel_pfad):
                eintrag["sha256_ziel"] = sha256_datei(ziel_pfad)
            eintrag["zustand"] = (
                ZUSTAND_UNVERAENDERT
                if eintrag["sha256_ziel"] == eintrag["sha256_quelle"]
                else ZUSTAND_UEBERNEHMEN)
        else:
            eintrag["zustand"] = ZUSTAND_UEBERNEHMEN
        plan.append(eintrag)
    return plan


# ── 3. Die eine Loeschstelle und das atomare Schreiben ────────────────────

def _entferne(pfad: str) -> None:
    """Die **einzige** Loeschstelle dieses Moduls.

    Warum hier und nur hier: Geloescht werden darf ausschliesslich die eigene
    Uebergabedatei — und zwar erst, nachdem ihre Pruefsumme mit der Zieldatei
    verglichen wurde (Zustand ``uebernommen`` bzw. ``unveraendert``). Ausserdem
    faellt hier die eigene temp-Datei weg, falls ein Schreiben abgebrochen ist,
    damit kein Rest im Zielordner liegen bleibt. Fremde Dateien werden nie
    angefasst; es gibt keine Loeschfunktion fuer Ordner oder Altbestaende.
    """
    os.remove(pfad)


def _kopiere_bytes(quelle: str, ziel: str) -> str:
    """Bytes von ``quelle`` nach ``ziel`` kopieren (vorhandenes ``ziel`` ersetzen).

    Bewusst nicht die temp-Variante: dies ist der Rueckweg der Sicherung, dort
    ist ein einfaches Schreiben richtig. Fuer die eigentliche Uebergabe gilt
    ``_kopiere_atomar``.
    """
    with open(quelle, "rb") as ein:
        daten = ein.read()
    ordner = os.path.dirname(os.path.abspath(ziel))
    os.makedirs(ordner, exist_ok=True)
    with open(ziel, "wb") as aus:
        aus.write(daten)
    return ziel


def _kopiere_atomar(quelle: str, ziel: str) -> str:
    """Die Uebergabedatei atomar in den Zielordner schreiben.

    Erst vollstaendig in ``<ziel>.teil`` im **Zielordner** schreiben, dann per
    ``os.replace`` ersetzen: es entsteht nie eine halbe Zieldatei. Bricht das
    Schreiben ab, wird ausschliesslich die eigene temp-Datei entfernt; eine
    vorhandene Zieldatei bleibt unangetastet (sie wurde zuvor schon gesichert).
    """
    ordner = os.path.dirname(os.path.abspath(ziel))
    os.makedirs(ordner, exist_ok=True)
    temp_pfad = ziel + TEMP_SUFFIX
    try:
        with open(quelle, "rb") as ein:
            daten = ein.read()
        with open(temp_pfad, "wb") as aus:
            aus.write(daten)
        os.replace(temp_pfad, ziel)
    except Exception:
        if os.path.exists(temp_pfad):
            _entferne(temp_pfad)                 # nur die eigene temp-Datei
        raise
    return ziel


# ── 4. Uebernehmen (fuehrt den Plan aus) ──────────────────────────────────

def uebernehmen(plan, *, trocken: bool = False) -> dict:
    """Den Plan ausfuehren und Bericht, Zaehler und Fehlerlage zurueckgeben.

    Rueckgabe (Woerterbuch)::

        {"zaehler": {"uebernommen", "unveraendert", "uebersprungen", "fehler"},
         "zeilen":  ["<name>: ...", ...],
         "fehler":  bool,          # True, sobald eine Datei scheitert
         "trocken": bool}

    Ablauf je Eintrag siehe Modulkopf. Mit ``trocken=True`` wird **nichts**
    geschrieben und **nichts** entfernt; die Zaehler zeigen dann, was ein
    echter Lauf taete, und die Zeilen sind entsprechend gekennzeichnet.
    """
    zaehler = {name: 0 for name in ZAEHLER_NAMEN}
    zeilen: list = []
    fehler = False

    for eintrag in plan or []:
        name = eintrag["name"]
        zustand = eintrag["zustand"]

        if zustand == ZUSTAND_FEHLT:
            zaehler[ZAEHLER_UEBERSPRUNGEN] += 1
            zeilen.append(f"{name}: uebersprungen (Uebergabedatei fehlt)")
            continue

        if zustand == ZUSTAND_UNVERAENDERT:
            zaehler[ZAEHLER_UNVERAENDERT] += 1
            zeilen.append(
                f"{name}: unveraendert (Pruefsumme gleich, "
                f"{_zahl(eintrag['groesse'])} Bytes, sha256 "
                f"{_kurz(eintrag['sha256_quelle'])}) – "
                + ("Uebergabedatei wuerde entfernt"
                   if trocken else "Uebergabedatei entfernt"))
            if not trocken:
                _entferne(eintrag["quelle"])
            continue

        # Zustand uebernehmen
        if trocken:
            zaehler[ZAEHLER_UEBERNOMMEN] += 1
            zeilen.append(
                f"{name}: wuerde uebernommen ({_zahl(eintrag['groesse'])} Bytes, "
                f"sha256 {_kurz(eintrag['sha256_quelle'])})"
                + (", vorherige Fassung wuerde gesichert"
                   if os.path.exists(eintrag["ziel"]) else ""))
            continue

        try:
            gesichert = os.path.exists(eintrag["ziel"])
            if gesichert:
                _kopiere_bytes(eintrag["ziel"], eintrag["vorher"])
            _kopiere_atomar(eintrag["quelle"], eintrag["ziel"])
            pruefsumme_ziel = sha256_datei(eintrag["ziel"])
        except (OSError, ValueError) as problem:
            zaehler[ZAEHLER_FEHLER] += 1
            fehler = True
            zeilen.append(
                f"{name}: FEHLER bei der Uebernahme "
                f"({problem.__class__.__name__}) – Uebergabedatei bleibt liegen")
            continue

        if pruefsumme_ziel != eintrag["sha256_quelle"]:
            zaehler[ZAEHLER_FEHLER] += 1
            fehler = True
            zeilen.append(
                f"{name}: FEHLER Pruefsumme weicht ab (Quelle "
                f"{_kurz(eintrag['sha256_quelle'])}, Ziel {_kurz(pruefsumme_ziel)}) "
                f"– Uebergabedatei bleibt liegen")
            continue

        zaehler[ZAEHLER_UEBERNOMMEN] += 1
        _entferne(eintrag["quelle"])             # erst nach bestandener Pruefung
        zeilen.append(
            f"{name}: uebernommen ({_zahl(eintrag['groesse'])} Bytes, sha256 "
            f"{_kurz(eintrag['sha256_quelle'])})"
            + (f", vorherige Fassung gesichert als {os.path.basename(eintrag['vorher'])}"
               if gesichert else "")
            + ", Uebergabedatei entfernt")

    return {"zaehler": zaehler, "zeilen": zeilen, "fehler": fehler,
            "trocken": bool(trocken)}


# ── 5. Protokoll und Ausgabe (Klartext deutsch) ───────────────────────────

def zaehler_text(zaehler) -> str:
    """Die Zaehler als eine deutsche Zeile (fuer Konsole und Protokoll)."""
    d = zaehler if isinstance(zaehler, dict) else {}
    return "uebernommen " + _zahl(d.get(ZAEHLER_UEBERNOMMEN, 0)) \
        + " · unveraendert " + _zahl(d.get(ZAEHLER_UNVERAENDERT, 0)) \
        + " · uebersprungen " + _zahl(d.get(ZAEHLER_UEBERSPRUNGEN, 0)) \
        + " · Fehler " + _zahl(d.get(ZAEHLER_FEHLER, 0))


def protokoll_anhaengen(pfad: str, zeilen) -> str:
    """Berichtzeilen mit Zeitstempel an das Protokoll **anhaengen**.

    Der Ordner wird angelegt, die Datei aber nur ergaenzt (Modus ``a``) — ein
    frueherer Lauf wird nie ueberschrieben. So kann der PC ueber das Kabel
    nachsehen, ob und wann eine Uebernahme lief. Es landen nur Dateiname,
    Groesse, Pruefsumme und Zustaende in der Datei, keine Schluesselwerte.
    """
    if not _text(pfad):
        raise ValueError("Kein Pfad fuer das Protokoll angegeben.")
    ordner = os.path.dirname(os.path.abspath(pfad))
    os.makedirs(ordner, exist_ok=True)
    stempel = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    with open(pfad, "a", encoding="utf-8") as datei:
        for zeile in zeilen:
            datei.write(f"{stempel} {zeile}\n")
    return pfad


def _im_repo(pfad: str) -> bool:
    """Liegt der (aufgeloeste) Pfad IM Repo? Gross/Klein und Trenner egal."""
    ziel = os.path.normcase(os.path.abspath(pfad))
    repo = os.path.normcase(os.path.abspath(REPO))
    try:
        return os.path.commonpath([ziel, repo]) == repo
    except ValueError:                            # anderes Laufwerk: nie im Repo
        return False


def _pruefe_ausserhalb_repo(pfad: str, was: str) -> None:
    """Schutzfehler (deutsch) werfen, wenn ``pfad`` IM Repo liegt.

    Weder die Datendateien noch das Protokoll gehoeren ins Repo — dort liegen
    die Ausgaben (und spaeter die Nachschau) nichts zu suchen. Geprueft wird
    **vor** dem ersten Schreiben, damit nichts halb angelegt wird.
    """
    if _im_repo(pfad):
        raise ValueError(
            f"{was} liegt IM Repo und ist nicht erlaubt: {pfad}\n"
            f"Es wird NICHTS angelegt und NICHTS uebernommen.")


# ── 6. Kommandozeile ─────────────────────────────────────────────────────

def main(argv=None) -> int:
    """Kommandozeile: Uebergabedateien uebernehmen, Pruefsumme hart vergleichen.

    ``--quelle``, ``--ziel``, ``--dateien`` (alle Pflicht), dazu
    ``--vorher-suffix`` (Standard ``.vorher``), ``--trocken`` und
    ``--protokoll``. Exit 0 = sauber, 1 = Uebernahmefehler, 2 = Aufruf- oder
    Schutzfehler.
    """
    zerleger = argparse.ArgumentParser(
        description="Uebergabedateien vom freigegebenen Download-Ordner in den "
                    "Zielordner uebernehmen — byte-genau geprueft (sha256), "
                    "idempotent, vorhandene Fassung wird als Sicherung "
                    "beiseitegelegt. Kein Netz, kein git.")
    zerleger.add_argument("--quelle", dest="quelle", default=None,
                          help="Ordner mit der Uebergabedatei (z. B. der "
                               "freigegebene Download-Ordner)")
    zerleger.add_argument("--ziel", dest="ziel", default=None,
                          help="Zielordner (wird bei Bedarf angelegt)")
    zerleger.add_argument("--dateien", dest="dateien", nargs="+", default=None,
                          help="Namen der zu uebernehmenden Dateien, in dieser "
                               "Reihenfolge")
    zerleger.add_argument("--vorher-suffix", dest="vorher_suffix",
                          default=STANDARD_VORHER_SUFFIX,
                          help="Suffix der Sicherung einer vorhandenen "
                               f"Zieldatei (Standard {STANDARD_VORHER_SUFFIX})")
    zerleger.add_argument("--trocken", action="store_true",
                          help="nichts schreiben, nichts entfernen — nur "
                               "berichten, was ein echter Lauf taete")
    zerleger.add_argument("--protokoll", dest="protokoll", default=None,
                          help="Datei, an die derselbe Bericht mit Zeitstempel "
                               "angehaengt wird (fuer die Nachschau vom PC)")
    args = zerleger.parse_args(argv)

    quelle = _text(args.quelle)
    ziel = _text(args.ziel)
    if not quelle:
        print("Fehler: --quelle fehlt (Ordner mit der Uebergabedatei).",
              file=sys.stderr)
        return 2
    if not ziel:
        print("Fehler: --ziel fehlt (Zielordner).", file=sys.stderr)
        return 2
    if not args.dateien:
        print("Fehler: --dateien fehlt (mindestens ein Dateiname).",
              file=sys.stderr)
        return 2
    if not _text(args.vorher_suffix):
        print("Fehler: --vorher-suffix darf nicht leer sein.", file=sys.stderr)
        return 2

    trocken = bool(args.trocken)
    try:
        _pruefe_ausserhalb_repo(ziel, "Der Zielordner")
        if args.protokoll:
            _pruefe_ausserhalb_repo(_text(args.protokoll), "Das Protokoll")
        plan = uebernahme_planen(quelle, ziel, args.dateien,
                                 vorher_suffix=_text(args.vorher_suffix))
    except ValueError as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2

    print("Uebergabe uebernehmen — "
          + ("TROCKENLAUF (es wird nichts geschrieben, nichts entfernt)"
             if trocken else "UEBERNAHME"))
    print(f"Quelle: {quelle}")
    print(f"Ziel:   {ziel}")

    try:
        ergebnis = uebernehmen(plan, trocken=trocken)
    except OSError as problem:
        print(f"Fehler: Uebernahme abgebrochen ({problem.__class__.__name__}): "
              f"{problem}", file=sys.stderr)
        return 1

    zeilen = list(ergebnis["zeilen"])
    zusammenfassung = "Zusammenfassung: " + zaehler_text(ergebnis["zaehler"])
    for zeile in zeilen:
        print("  " + zeile)
    print(zusammenfassung)

    if args.protokoll and not trocken:
        try:
            protokoll_anhaengen(
                _text(args.protokoll),
                [f"Quelle: {quelle}", f"Ziel:   {ziel}"] + zeilen
                + [zusammenfassung])
        except (OSError, ValueError) as problem:
            # Ohne Protokoll ist die Uebernahme selbst nicht gescheitert; der
            # Nutzer sieht es aber, damit die Nachschau nicht still fehlt.
            print(f"  ⚠ Protokoll konnte nicht geschrieben werden "
                  f"({problem.__class__.__name__}): {args.protokoll}",
                  file=sys.stderr)
    elif args.protokoll and trocken:
        print(f"Trockenlauf: Protokoll {_text(args.protokoll)} wurde NICHT "
              f"geschrieben.")

    if ergebnis["fehler"]:
        print("Fehler: mindestens eine Uebergabe ist gescheitert — die "
              "Uebergabedatei bleibt liegen, erneut starten.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
