"""Messlatte: wie gut ist eine Gruppierung, gemessen an den eigenen Entscheidungen?
(Gruppierung v2, G1, 15.10.2026)

Dieses Werkzeug **misst nur**. Es liest eine Zuordnung (``gesicht_zuordnung.jsonl``-
Form, bei ``personen_gruppieren.py --bewerten`` auch direkt aus dem Speicher) und
die Entscheidungen vom Handy (``personen_bestaetigt.json``,
``personen_vorgaben.json``), rechnet nichts neu, aendert keine Schwelle und
**schreibt nichts**. Bericht nur auf der Konsole, **nur Zahlen** - keine
Bild-IDs, keine Namen, keine Kennungen, keine Pfade.

Die Grundwahrheit sind die Entscheidungen des Nutzers:

* **bestaetigte Namen** (``personen_bestaetigt.json``: Kennung -> Name),
* **feste Zuordnungen** (``zugeordnet``: dieses Gesicht ist Person N),
* **ausgeschlossen** (dieses Gesicht gehoert NICHT in Kennung K),
* **gleich** / **verschieden** (Kennungspaare).

Kennzahlen je Zuordnung:

* **Grundwahrheit zuerst (Kopfzeile):** Anzahl Namen, benannter Kennungen,
  gleich / verschieden / ausgeschlossen / fest, Stand (Aenderungszeit) der beiden
  Regeldateien. Liegt die Grundwahrheit unter der Mindestmenge (``MIN_NAMEN`` = 10
  Namen ODER ``MIN_REGELN`` = 50 Regeln - fehlen BEIDE, gilt sie als zu duenn),
  steht ueber dem Bericht "vorlaeufig - zu wenig Entscheidungen". Ist eine
  Regeldatei aelter als die Zuordnung, steht eine Warnzeile "Entscheidungen vom
  Handy holen (G0)".
* **Namens-Reinheit:** Von den Gesichtern mit bekanntem Namen (fest zugeordnet; im
  Vergleichsmodus zusaetzlich die Gesichter, die in der VORHER-Zuordnung in einer
  benannten Gruppe standen) - wie viele liegen in einer Gruppe desselben Namens,
  in einer Gruppe eines anderen Namens, in einer unbenannten Gruppe, ohne Kennung?
  Dazu die **Streuung**: wie viele Namen sind ueber wie viele Gruppen verteilt.
* **Regelbruch:** ausgeschlossene Gesichter, die wieder in ihrer alten Kennung
  liegen; "verschieden" markierte Kennungspaare, deren Gesichter in derselben
  Gruppe zusammenlaufen (nur im Vergleichsmodus pruefbar - ein einzelner Bericht
  kann nur sagen, ob beide Kennungen noch als getrennte Gruppen existieren).
* **Gruppen ohne sauberes Gesicht**, Groessenverteilung, Anteil ohne Kennung.
* **Wechsel** (nur Vergleichsmodus): wie viele **saubere** Gesichter gegenueber der
  Vorher-Zuordnung die Gruppe wechseln, eine Kennung verlieren oder gewinnen.

Vergleichsmodus: ``--vorher A --nachher B`` druckt beide Spalten nebeneinander.

**Aliasmengen (Auflage 3, 21.10.2026):** Eine Vereinigung per ``gleich`` macht aus
zwei Kennungen eine Gruppe. Ohne Zusatzangabe rechnet das Werkzeug **kennungsgenau**:
ein Gesicht, das von ``Person_002`` nach ``Person_001`` wechselt, zaehlt als Wechsel,
auch wenn der Nutzer beide per ``gleich`` zusammengelegt hat - der Bericht sagt das in
einer Hinweiszeile. Mit ``--aliase <aliasmengen.json>`` (Form
``{"<kennung>": ["<kennung>", ...]}``, geschrieben von ``personen_gruppieren.py``
neben die Kandidaten) gelten alle Kennungen einer Menge - transitiv, auch ueber
Ketten A=B, B=C - als **dieselbe** Gruppe (``_gleiche_gruppe``). Bei
``personen_gruppieren.py --bewerten`` reicht der Lauf die Mengen direkt aus dem
Speicher durch; eine Datei braucht es dafuer nicht.

Aufruf (aus dem Ordner ``backend``)::

    .venv/Scripts/python.exe ../tools/foto_sortierung/gruppierung_bewerten.py
    .venv/Scripts/python.exe ../tools/foto_sortierung/gruppierung_bewerten.py ^
        --vorher A/gesicht_zuordnung.jsonl --nachher B/gesicht_zuordnung.jsonl ^
        --aliase B/aliasmengen.json

Exit 0 = Bericht gedruckt, 2 = Eingabe (auch ``--aliase``) fehlt oder ist nicht lesbar.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))


def _nachbar(name: str):
    """Ein Nachbarmodul importieren; im Test-Ladeweg ueber den Dateipfad."""
    try:
        return __import__(name)
    except ImportError:                          # pragma: no cover
        spez = importlib.util.spec_from_file_location(
            name, os.path.join(HIER, name + ".py"))
        if spez is None or spez.loader is None:  # pragma: no cover
            raise
        modul = importlib.util.module_from_spec(spez)
        spez.loader.exec_module(modul)
        return modul


_phasen = _nachbar("personen_phasen")

STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_ZUORDNUNG = os.path.join(STANDARD_BASIS, "personen_gruppen",
                                  "gesicht_zuordnung.jsonl")
STANDARD_BESTAETIGT = os.path.join(STANDARD_BASIS, "personen_bestaetigt.json")
STANDARD_VORGABEN = os.path.join(STANDARD_BASIS, "personen_vorgaben.json")

# Mindestmenge der Grundwahrheit (Startwert): reicht EINE der beiden Grenzen,
# gilt sie als ausreichend; fehlen beide, steht der Bericht unter "vorlaeufig".
MIN_NAMEN = 10
MIN_REGELN = 50


# ── Aliasmengen (transitive Huelle) ────────────────────────────────────────

def aliase_huelle(aliasmengen) -> dict:
    """Aliasmengen -> ``{kennung: frozenset(alle Kennungen derselben Gruppe)}``.

    ``aliasmengen`` ist ``{kennung: [kennung, ...]}`` (so schreibt es
    ``personen_gruppieren.py``; der Schluessel gehoert immer zur Menge). Mengen,
    die eine Kennung teilen, werden **transitiv** vereint (Union-Find): aus
    ``{A, B}`` und ``{B, C}`` wird ``{A, B, C}`` - kein Paarvergleich. ``None``
    oder leer ergibt ``{}`` (keine Aliasangabe). Eine schon fertige Huelle
    (Werte sind ``frozenset``) laesst sich erneut uebergeben.
    """
    eltern: dict = {}

    def wurzel(x):
        while eltern[x] != x:
            eltern[x] = eltern[eltern[x]]
            x = eltern[x]
        return x

    for kennung, menge in (aliasmengen or {}).items():
        teile = {str(kennung)} | {str(m) for m in (menge or ())}
        for k in teile:
            eltern.setdefault(k, k)
        erste = next(iter(sorted(teile)))
        for k in teile:
            a, b = wurzel(erste), wurzel(k)
            if a != b:
                eltern[max(a, b)] = min(a, b)
    gruppen: dict = {}
    for k in eltern:
        gruppen.setdefault(wurzel(k), set()).add(k)
    return {k: frozenset(gruppen[wurzel(k)]) for k in eltern}


def _gleiche_gruppe(a, b, huelle=None) -> bool:
    """Sind die Kennungen ``a`` und ``b`` dieselbe Gruppe? (EINE Quelle fuer alle Zahlen.)

    Dieselbe Kennung ist immer dieselbe Gruppe; ``None`` (ohne Kennung) ist nie
    eine Gruppe. Mit ``huelle`` (``aliase_huelle``) gelten alle Kennungen einer
    Aliasmenge als dieselbe Gruppe - transitiv. Ohne ``huelle`` bleibt es
    kennungsgenau. Diese Funktion benutzen die Bewertung hier UND die drei
    Sperrzahlen in ``personen_gruppieren.lauf_rechnen_v2`` (kein zweiter Vergleich).
    """
    if a is None or b is None:
        return False
    if a == b:
        return True
    menge = (huelle or {}).get(a)
    return menge is not None and b in menge


def kennung_erhalten(kennung, gruppen_kennungen, huelle=None) -> bool:
    """Lebt die Kennung in einer der Gruppen weiter - als Kennung oder per Aliasmenge?

    ``gruppen_kennungen`` sind die Kennungen der vorhandenen Gruppen (mit
    mindestens einem Gesicht). Eine Kennung ist **erhalten**, wenn sie selbst eine
    Gruppe ist oder ``_gleiche_gruppe`` sie mit einer Gruppenkennung gleichsetzt.
    Grundlage der Sperrzahlen "benannte Kennung ohne Gruppe" und "leere benannte
    Gruppe" (Auflage 3) - dieselbe Gleichsetzung wie bei den Wechseln.
    """
    kandidaten = {kennung} | set((huelle or {}).get(kennung, ()))
    return any(g in gruppen_kennungen and _gleiche_gruppe(kennung, g, huelle)
               for g in kandidaten)


def aliase_lesen(pfad: str) -> dict:
    """``aliasmengen.json`` lesen: ``{kennung: [kennung, ...]}``; sonst ``ValueError``.

    Fehlende Datei, kaputtes JSON oder falsche Form -> ``ValueError`` ohne Pfad
    im Text (der Aufrufer meldet nur "nicht lesbar").
    """
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except (OSError, ValueError):
        raise ValueError("Aliasdatei nicht lesbar.") from None
    if not isinstance(daten, dict):
        raise ValueError("Aliasdatei hat nicht die Form {kennung: [kennungen]}.")
    ergebnis: dict = {}
    for kennung, menge in daten.items():
        if (not isinstance(kennung, str) or not isinstance(menge, list)
                or not all(isinstance(m, str) for m in menge)):
            raise ValueError("Aliasdatei hat nicht die Form {kennung: [kennungen]}.")
        ergebnis[kennung] = list(menge)
    return ergebnis


def _huelle_von(aliase):
    """Aliasangabe (Wörterbuch, fertige Huelle oder ``None``) -> Huelle oder ``None``."""
    if aliase is None:
        return None
    return aliase_huelle(aliase)


def _vertreter(huelle, kennung):
    """Eine feste Vertreter-Kennung je Aliasmenge (die kleinste); sonst die Kennung selbst."""
    if kennung is None:
        return None
    menge = (huelle or {}).get(kennung)
    return min(menge) if menge else kennung


# ── Lesen ────────────────────────────────────────────────────────────────

def zuordnung_lesen(pfad: str) -> tuple:
    """``(zuordnung, ungueltig)`` aus einer ``gesicht_zuordnung.jsonl``.

    ``zuordnung`` ist ``{(bild_id, index): (kennung oder None, sauber)}``. Bei
    doppeltem Schluessel gewinnt die erste Zeile. Kaputte Zeilen werden gezaehlt.
    """
    return zuordnung_aus_zeilen(_zeilen(pfad))


def _zeilen(pfad: str):
    with open(pfad, encoding="utf-8") as datei:
        for zeile in datei:
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                daten = json.loads(zeile)
            except ValueError:
                yield None
                continue
            yield daten if isinstance(daten, dict) else None


def zuordnung_aus_zeilen(zeilen) -> tuple:
    """Wie ``zuordnung_lesen``, aber aus Woerterbuechern (``None`` = kaputte Zeile)."""
    ergebnis: dict = {}
    ungueltig = 0
    for z in zeilen:
        if not isinstance(z, dict) or z.get("bild_id") is None:
            ungueltig += 1
            continue
        index = z.get("index", 0)
        if not isinstance(index, int) or isinstance(index, bool):
            ungueltig += 1
            continue
        schluessel = (str(z["bild_id"]), int(index))
        if schluessel in ergebnis:
            continue
        kennung = z.get("kennung")
        kennung = str(kennung) if kennung not in (None, "") else None
        ergebnis[schluessel] = (kennung, bool(_phasen.sauber(z)))
    return ergebnis, ungueltig


def _stand(pfad):
    """Aenderungszeit einer Datei als Zeitstempel (Sekunden) oder ``None``."""
    try:
        return os.path.getmtime(pfad) if pfad and os.path.isfile(pfad) else None
    except OSError:
        return None


def _name_falten(name) -> str:
    return " ".join(str(name).split()).casefold() if isinstance(name, str) else ""


# ── Grundwahrheit (Kopfzeile) ──────────────────────────────────────────────

def grundwahrheit(bestaetigt: dict, vorgaben: dict, stand_bestaetigt=None,
                  stand_vorgaben=None, stand_zuordnung=None) -> dict:
    """Groesse und Alter der Entscheidungen - nur Zahlen.

    ``stand_*`` sind Aenderungszeiten (Sekunden seit 1970) oder ``None``.
    """
    namen = {_name_falten(n) for n in (bestaetigt or {}).values() if _name_falten(n)}
    regeln = {
        "gleich": len((vorgaben or {}).get("gleich") or ()),
        "verschieden": len((vorgaben or {}).get("verschieden") or ()),
        "ausgeschlossen": len((vorgaben or {}).get("ausgeschlossen") or ()),
        "fest": len((vorgaben or {}).get("zugeordnet") or ()),
    }
    summe = sum(regeln.values())
    vorlaeufig = len(namen) < MIN_NAMEN and summe < MIN_REGELN
    staende = [s for s in (stand_bestaetigt, stand_vorgaben) if s is not None]
    veraltet = bool(staende and stand_zuordnung is not None
                    and min(staende) < stand_zuordnung)
    return {
        "namen": len(namen), "benannte_kennungen": len(bestaetigt or {}),
        "regeln": regeln, "regeln_gesamt": summe,
        "vorlaeufig": vorlaeufig, "veraltet": veraltet,
        "stand_bestaetigt": stand_bestaetigt, "stand_vorgaben": stand_vorgaben,
    }


def wahrheit_bauen(vorgaben: dict, bestaetigt: dict, vorher=None) -> dict:
    """Gesichter mit bekanntem Namen: ``{(bild_id, index): gefalteter Name}``.

    Feste Zuordnungen sind immer dabei. Mit ``vorher`` (eine Zuordnung) kommen
    die Gesichter hinzu, die dort in einer **benannten** Gruppe standen - die
    Benennung ist die Entscheidung des Nutzers; eine feste Zuordnung gewinnt.
    """
    namen_je_kennung = {k: _name_falten(n) for k, n in (bestaetigt or {}).items()
                        if _name_falten(n)}
    wahrheit: dict = {}
    for schluessel, kennung in ((vorher or {}).items()):
        k = kennung[0]
        if k and k in namen_je_kennung:
            wahrheit[schluessel] = namen_je_kennung[k]
    for schluessel, eintrag in ((vorgaben or {}).get("zugeordnet") or {}).items():
        name = _name_falten(eintrag.get("name")) if isinstance(eintrag, dict) else ""
        if name:
            wahrheit[(str(schluessel[0]), int(schluessel[1]))] = name
    return wahrheit


# ── Bewerten (rein) ────────────────────────────────────────────────────────

def _namen_mit_aliasen(namen_je_kennung: dict, huelle) -> dict:
    """Namen je Kennung; eine Aliaskennung ohne eigenen Namen erbt den eindeutigen der Menge.

    Nach einer ``gleich``-Vereinigung heisst die Gruppe nach einer der Kennungen;
    traegt sie keinen Namen, ein Mitglied der Menge aber doch (und alle genannten
    Namen sind gleich), gilt dieser Name auch fuer die Gruppe. Widersprechen sich
    die Namen, bleibt es kennungsgenau.
    """
    if not huelle:
        return namen_je_kennung
    erg = dict(namen_je_kennung)
    for kennung, menge in huelle.items():
        if kennung in erg:
            continue
        namen = {namen_je_kennung[m] for m in menge if m in namen_je_kennung}
        if len(namen) == 1:
            erg[kennung] = next(iter(namen))
    return erg


def bewerten(zuordnung: dict, bestaetigt: dict, vorgaben: dict,
             wahrheit: dict | None = None, vorher: dict | None = None,
             aliase: dict | None = None) -> dict:
    """Alle Kennzahlen einer Zuordnung. ``vorher`` schaltet die Vergleichs-Zahlen zu.

    ``zuordnung`` / ``vorher``: ``{(bild_id, index): (kennung|None, sauber)}``.
    ``aliase`` (``{kennung: [kennungen]}``) macht den Vergleich aliasaequivalent
    (``_gleiche_gruppe``): ausgeschlossene Gesichter, ``verschieden``-Paare und
    Namen folgen der Aliasmenge. Ohne ``aliase`` rechnet die Funktion kennungsgenau.
    """
    huelle = _huelle_von(aliase)
    namen_je_kennung = {k: _name_falten(n) for k, n in (bestaetigt or {}).items()
                        if _name_falten(n)}
    namen_je_kennung = _namen_mit_aliasen(namen_je_kennung, huelle)
    wahrheit = wahrheit if wahrheit is not None else wahrheit_bauen(vorgaben, bestaetigt)

    # Gruppen: Kennung -> [Gesichter, saubere Gesichter]
    gruppen: dict = {}
    ohne = 0
    for kennung, ist_sauber in zuordnung.values():
        if kennung is None:
            ohne += 1
            continue
        eintrag = gruppen.setdefault(kennung, [0, 0])
        eintrag[0] += 1
        eintrag[1] += 1 if ist_sauber else 0
    groessen = sorted((g[0] for g in gruppen.values()), reverse=True)
    gesamt = len(zuordnung)

    # Streuung: Name -> Zahl der vorhandenen Gruppen mit diesem Namen
    gruppen_je_name: dict = {}
    for kennung in gruppen:
        name = namen_je_kennung.get(kennung)
        if name:
            gruppen_je_name[name] = gruppen_je_name.get(name, 0) + 1
    streuung = {"eine": 0, "zwei": 0, "drei_oder_mehr": 0}
    for n in gruppen_je_name.values():
        streuung["eine" if n == 1 else "zwei" if n == 2 else "drei_oder_mehr"] += 1
    alle_namen = set(namen_je_kennung.values())
    kennungen_da = set(gruppen)

    def vorhanden(kennung) -> bool:
        """Gibt es die Kennung als Gruppe - oder lebt sie in einer Aliasmenge weiter?"""
        if kennung in kennungen_da:
            return True
        return any(m in kennungen_da for m in (huelle or {}).get(kennung, ()))

    in_benannten = sum(g[0] for k, g in gruppen.items() if k in namen_je_kennung)

    # Namens-Reinheit gegen die Gesichter mit bekanntem Namen
    rein = {"geprueft": 0, "richtig": 0, "anderer_name": 0, "unbenannt": 0,
            "ohne_kennung": 0, "nicht_in_zuordnung": 0}
    for schluessel, name in wahrheit.items():
        if schluessel not in zuordnung:
            rein["nicht_in_zuordnung"] += 1
            continue
        rein["geprueft"] += 1
        kennung = zuordnung[schluessel][0]
        if kennung is None:
            rein["ohne_kennung"] += 1
        elif kennung not in namen_je_kennung:
            rein["unbenannt"] += 1
        elif namen_je_kennung[kennung] == name:
            rein["richtig"] += 1
        else:
            rein["anderer_name"] += 1

    # Regelbruch: ausgeschlossen
    ausg = (vorgaben or {}).get("ausgeschlossen") or set()
    bruch_ausg = sum(1 for (k, bild, idx) in ausg
                     if _gleiche_gruppe(
                         k, zuordnung.get((str(bild), int(idx)), (None, False))[0], huelle))

    # Regelbruch: verschieden
    verschieden = (vorgaben or {}).get("verschieden") or set()
    verschieden_vereint = None
    kennung_fehlt = 0
    for a, b in verschieden:
        if not vorhanden(a) or not vorhanden(b):
            kennung_fehlt += 1
    if vorher is not None:
        je_kennung_vorher: dict = {}
        for schluessel, (k, _s) in vorher.items():
            if k:
                je_kennung_vorher.setdefault(k, []).append(schluessel)
        verschieden_vereint = 0
        for a, b in verschieden:
            nach_a = {_vertreter(huelle, zuordnung[s][0])
                      for s in je_kennung_vorher.get(a, ())
                      if s in zuordnung and zuordnung[s][0]}
            nach_b = {_vertreter(huelle, zuordnung[s][0])
                      for s in je_kennung_vorher.get(b, ())
                      if s in zuordnung and zuordnung[s][0]}
            if nach_a & nach_b:
                verschieden_vereint += 1

    erg = {
        "gesichter": gesamt, "in_gruppen": gesamt - ohne, "ohne_kennung": ohne,
        "gruppen": len(gruppen),
        "gruppen_ohne_sauberes": sum(1 for g in gruppen.values() if g[1] == 0),
        "groessen_top5": groessen[:5],
        "gruppen_ab_50": sum(1 for g in groessen if g >= 50),
        "gruppen_ab_10": sum(1 for g in groessen if g >= 10),
        "in_benannten_gruppen": in_benannten,
        "namen_mit_gruppe": len(gruppen_je_name),
        "namen_ohne_gruppe": len(alle_namen - set(gruppen_je_name)),
        "streuung": streuung,
        "streuung_max": max(gruppen_je_name.values(), default=0),
        "reinheit": rein,
        "ausgeschlossen_regeln": len(ausg), "ausgeschlossen_bruch": bruch_ausg,
        "verschieden_regeln": len(verschieden),
        "verschieden_kennung_fehlt": kennung_fehlt,
        "verschieden_vereint": verschieden_vereint,
    }
    return erg


def wechsel(vorher: dict, nachher: dict, aliase: dict | None = None) -> dict:
    """Was geschieht mit den **sauberen** Gesichtern zwischen zwei Zuordnungen?

    Gezaehlt wird ueber Gesichter, die in BEIDEN Zuordnungen vorkommen und in der
    Vorher-Zuordnung sauber sind. Kennungen werden als dieselbe Gruppe gelesen,
    wenn sie gleich heissen (die Kennungen sind ueber ``kennungen.json`` stabil) -
    mit ``aliase`` zusaetzlich, wenn sie in derselben Aliasmenge stehen
    (``_gleiche_gruppe``, transitiv).
    """
    huelle = _huelle_von(aliase)
    erg = {"saubere_in_beiden": 0, "gleiche_gruppe": 0, "gruppe_gewechselt": 0,
           "kennung_verloren": 0, "kennung_gewonnen": 0, "bleibt_ohne": 0,
           "nur_vorher": 0, "nur_nachher": 0}
    for schluessel, (alt, ist_sauber) in vorher.items():
        if schluessel not in nachher:
            erg["nur_vorher"] += 1
            continue
        if not ist_sauber:
            continue
        erg["saubere_in_beiden"] += 1
        neu = nachher[schluessel][0]
        if alt and neu:
            erg["gleiche_gruppe" if _gleiche_gruppe(alt, neu, huelle)
                else "gruppe_gewechselt"] += 1
        elif alt and not neu:
            erg["kennung_verloren"] += 1
        elif neu and not alt:
            erg["kennung_gewonnen"] += 1
        else:
            erg["bleibt_ohne"] += 1
    erg["nur_nachher"] = sum(1 for s in nachher if s not in vorher)
    return erg


# ── Bericht (nur Zahlen) ───────────────────────────────────────────────────

def _prozent(teil, ganzes) -> str:
    return f"{100.0 * teil / ganzes:.1f} %" if ganzes else "-"


def _zeit(stempel) -> str:
    if stempel is None:
        return "fehlt"
    return datetime.datetime.fromtimestamp(stempel).strftime("%Y-%m-%d %H:%M")


def kopf_text(g: dict) -> list:
    """Die Kopfzeilen der Grundwahrheit (und ihre Warnungen)."""
    r = g["regeln"]
    zeilen = []
    if g["vorlaeufig"]:
        zeilen.append(f"VORLAEUFIG - zu wenig Entscheidungen (Mindestmenge: "
                      f"{MIN_NAMEN} Namen oder {MIN_REGELN} Regeln)")
    if g["veraltet"]:
        zeilen.append("WARNUNG: Die Regeldateien sind aelter als die Zuordnung - "
                      "Entscheidungen vom Handy holen (G0).")
    zeilen.append(f"Grundwahrheit: {g['namen']} Namen in {g['benannte_kennungen']} "
                  f"benannten Kennungen")
    zeilen.append(f"  Regeln: gleich {r['gleich']} - verschieden {r['verschieden']} - "
                  f"ausgeschlossen {r['ausgeschlossen']} - fest {r['fest']} "
                  f"(zusammen {g['regeln_gesamt']})")
    zeilen.append(f"  Stand: Namen {_zeit(g['stand_bestaetigt'])} - "
                  f"Vorgaben {_zeit(g['stand_vorgaben'])}")
    return zeilen


def _spalten(e: dict, w: dict | None = None) -> list:
    """Die Kennzahlen als ``[(Bezeichnung, Wert), ...]`` - Werte als Text."""
    rein = e["reinheit"]
    zeilen = [
        ("Gesichter", str(e["gesichter"])),
        ("  in Gruppen", f"{e['in_gruppen']} ({_prozent(e['in_gruppen'], e['gesichter'])})"),
        ("  ohne Kennung", f"{e['ohne_kennung']} ({_prozent(e['ohne_kennung'], e['gesichter'])})"),
        ("Gruppen", str(e["gruppen"])),
        ("  davon ohne sauberes Gesicht",
         f"{e['gruppen_ohne_sauberes']} ({_prozent(e['gruppen_ohne_sauberes'], e['gruppen'])})"),
        ("  ab 50 Gesichtern", str(e["gruppen_ab_50"])),
        ("  ab 10 Gesichtern", str(e["gruppen_ab_10"])),
        ("  groesste", ", ".join(map(str, e["groessen_top5"])) or "-"),
        ("Gesichter in benannten Gruppen", str(e["in_benannten_gruppen"])),
        ("Namens-Reinheit (Gesichter mit bekanntem Namen)", ""),
        ("  geprueft", str(rein["geprueft"])),
        ("  in Gruppe desselben Namens",
         f"{rein['richtig']} ({_prozent(rein['richtig'], rein['geprueft'])})"),
        ("  in Gruppe eines anderen Namens", str(rein["anderer_name"])),
        ("  in unbenannter Gruppe", str(rein["unbenannt"])),
        ("  ohne Kennung", str(rein["ohne_kennung"])),
        ("  nicht in der Zuordnung", str(rein["nicht_in_zuordnung"])),
        ("Namen ueber Gruppen verstreut", ""),
        ("  Namen mit mindestens einer Gruppe", str(e["namen_mit_gruppe"])),
        ("  Namen ohne Gruppe", str(e["namen_ohne_gruppe"])),
        ("  in 1 Gruppe", str(e["streuung"]["eine"])),
        ("  in 2 Gruppen", str(e["streuung"]["zwei"])),
        ("  in 3 oder mehr Gruppen", str(e["streuung"]["drei_oder_mehr"])),
        ("  groesste Streuung (Gruppen je Name)", str(e["streuung_max"])),
        ("Regelbruch", ""),
        ("  ausgeschlossene Gesichter wieder in alter Kennung",
         f"{e['ausgeschlossen_bruch']} von {e['ausgeschlossen_regeln']}"),
        ("  verschieden-Paare, Kennung nicht mehr vorhanden",
         f"{e['verschieden_kennung_fehlt']} von {e['verschieden_regeln']}"),
        ("  verschieden-Paare in einer Gruppe vereint",
         "nur im Vergleich pruefbar" if e["verschieden_vereint"] is None
         else f"{e['verschieden_vereint']} von {e['verschieden_regeln']}"),
    ]
    return zeilen


def alias_zeile(aliase) -> str:
    """Die Hinweiszeile zum Vergleich: kennungsgenau oder aliasaequivalent (nur Zahlen)."""
    if aliase is None:
        return ("Aliasmengen: keine angegeben - Kennungen werden kennungsgenau "
                "verglichen (eine per gleich zusammengefuehrte Kennung zaehlt als Wechsel).")
    huelle = aliase_huelle(aliase)
    mengen = {menge for menge in huelle.values() if len(menge) > 1}
    return (f"Aliasmengen: {len(mengen)} Gruppen mit {sum(len(m) for m in mengen)} "
            f"Kennungen - Kennungen derselben Menge gelten als dieselbe Gruppe.")


def bericht_text(kopf: dict, nachher: dict, vorher: dict | None = None,
                 wechsel_zahlen: dict | None = None, aliase=None,
                 alias_hinweis: bool = True) -> str:
    """Der ganze Bericht. Mit ``vorher`` zwei Spalten nebeneinander.

    ``aliase`` (oder ``None`` = kennungsgenau) steht nur als Hinweiszeile im Kopf;
    gerechnet wurde in ``bewerten`` / ``wechsel``. ``alias_hinweis=False`` laesst
    die Zeile weg - fuer v1-Laeufe, deren Bericht wie vor Schritt 3 bleiben muss.
    """
    zeilen = kopf_text(kopf)
    if alias_hinweis:
        zeilen.append(alias_zeile(aliase))
    zeilen.append("")
    if vorher is None:
        for bez, wert in _spalten(nachher):
            zeilen.append(f"{bez}: {wert}" if wert else bez)
    else:
        a, b = _spalten(vorher), _spalten(nachher)
        breite = max(len(bez) for bez, _ in a) + 2
        spalte = max([len(w) for _, w in a] + [len("vorher")]) + 2
        zeilen.append(f"{'Kennzahl':<{breite}}{'vorher':<{spalte}}nachher")
        for (bez, wa), (_bez, wb) in zip(a, b):
            if not wa and not wb:
                zeilen.append(bez)
            else:
                zeilen.append(f"{bez:<{breite}}{wa:<{spalte}}{wb}")
    if wechsel_zahlen is not None:
        w = wechsel_zahlen
        zeilen += [
            "Wechsel der sauberen Gesichter gegenueber vorher",
            f"  saubere Gesichter in beiden Zuordnungen: {w['saubere_in_beiden']}",
            f"  gleiche Gruppe: {w['gleiche_gruppe']} "
            f"({_prozent(w['gleiche_gruppe'], w['saubere_in_beiden'])})",
            f"  Gruppe gewechselt: {w['gruppe_gewechselt']} "
            f"({_prozent(w['gruppe_gewechselt'], w['saubere_in_beiden'])})",
            f"  Kennung verloren: {w['kennung_verloren']}",
            f"  Kennung gewonnen: {w['kennung_gewonnen']}",
            f"  bleibt ohne Kennung: {w['bleibt_ohne']}",
            f"  nur in vorher: {w['nur_vorher']} - nur in nachher: {w['nur_nachher']}",
        ]
    return "\n".join(zeilen)


def vergleich_bericht(vorher: dict, nachher: dict, bestaetigt: dict, vorgaben: dict,
                      stand_bestaetigt=None, stand_vorgaben=None,
                      stand_zuordnung=None, aliase: dict | None = None,
                      alias_hinweis: bool = True) -> str:
    """Bericht vorher gegen nachher - gemeinsame Grundwahrheit (siehe Moduldoku).

    ``aliase`` macht den Vergleich aliasaequivalent; ohne bleibt er kennungsgenau
    und die Hinweiszeile sagt das.
    """
    wahrheit = wahrheit_bauen(vorgaben, bestaetigt, vorher=vorher)
    kopf = grundwahrheit(bestaetigt, vorgaben, stand_bestaetigt, stand_vorgaben,
                         stand_zuordnung)
    return bericht_text(
        kopf,
        bewerten(nachher, bestaetigt, vorgaben, wahrheit, vorher=vorher, aliase=aliase),
        bewerten(vorher, bestaetigt, vorgaben, wahrheit, vorher=vorher, aliase=aliase),
        wechsel(vorher, nachher, aliase), aliase=aliase, alias_hinweis=alias_hinweis)


def einzel_bericht(zuordnung: dict, bestaetigt: dict, vorgaben: dict,
                   stand_bestaetigt=None, stand_vorgaben=None,
                   stand_zuordnung=None, aliase: dict | None = None,
                   alias_hinweis: bool = True) -> str:
    """Bericht einer einzelnen Zuordnung."""
    kopf = grundwahrheit(bestaetigt, vorgaben, stand_bestaetigt, stand_vorgaben,
                         stand_zuordnung)
    return bericht_text(kopf, bewerten(zuordnung, bestaetigt, vorgaben, aliase=aliase),
                        aliase=aliase, alias_hinweis=alias_hinweis)


# ── Kommandozeile ──────────────────────────────────────────────────────────

def _lesen_oder_abbruch(pfad: str):
    if not os.path.isfile(pfad):
        raise FileNotFoundError("Zuordnungsdatei nicht gefunden.")
    return zuordnung_lesen(pfad)[0]


def main(argv=None) -> int:
    zerleger = argparse.ArgumentParser(
        description="Bewertet eine Gruppierung an den eigenen Entscheidungen "
                    "(nur lesend, nur Zahlen, schreibt nichts).")
    zerleger.add_argument("--zuordnung", default=STANDARD_ZUORDNUNG,
                          help="eine einzelne Zuordnung bewerten")
    zerleger.add_argument("--vorher", default=None, help="Zuordnung als Ausgangsstand")
    zerleger.add_argument("--nachher", default=None, help="Zuordnung zum Vergleich")
    zerleger.add_argument("--bestaetigt", default=STANDARD_BESTAETIGT)
    zerleger.add_argument("--vorgaben", default=STANDARD_VORGABEN)
    zerleger.add_argument("--aliase", default=None,
                          help="aliasmengen.json (Auflage 3): per gleich vereinte Kennungen "
                               "gelten als dieselbe Gruppe; ohne die Datei wird "
                               "kennungsgenau verglichen")
    args = zerleger.parse_args(argv)

    if bool(args.vorher) != bool(args.nachher):
        print("Fehler: --vorher und --nachher gehoeren zusammen.", file=sys.stderr)
        return 2
    pg = _nachbar("personen_gruppieren")
    try:
        bestaetigt = pg.bestaetigt_lesen(args.bestaetigt)
        vorgaben = pg.vorgaben_lesen(args.vorgaben)
        stand_b, stand_v = _stand(args.bestaetigt), _stand(args.vorgaben)
        aliase = aliase_lesen(args.aliase) if args.aliase else None
        if args.vorher:
            vorher = _lesen_oder_abbruch(args.vorher)
            nachher = _lesen_oder_abbruch(args.nachher)
            text = vergleich_bericht(vorher, nachher, bestaetigt, vorgaben, stand_b,
                                     stand_v, _stand(args.vorher), aliase)
        else:
            zuordnung = _lesen_oder_abbruch(args.zuordnung)
            text = einzel_bericht(zuordnung, bestaetigt, vorgaben, stand_b, stand_v,
                                  _stand(args.zuordnung), aliase)
    except (OSError, ValueError, pg.PersonenFehler) as problem:
        print(f"Fehler: {problem.__class__.__name__}: Eingabe fehlt oder ist nicht "
              f"lesbar.", file=sys.stderr)
        return 2
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
