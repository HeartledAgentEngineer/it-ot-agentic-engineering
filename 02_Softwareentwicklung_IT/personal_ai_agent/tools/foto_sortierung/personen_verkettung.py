"""Verkettungs-Messwerkzeug der Personen-Stufe (Nachtlauf-Schritt N9f, 27.09.2026).

Wozu dieses Werkzeug:
  Das Dichte-Verfahren aus N9a (``personen_cluster.vektoren_clustern``,
  DBSCAN-artig) verknuepft **transitiv**: Punkt A nah an B, B nah an C — schon
  landen A und C in **einer** Gruppe, obwohl ihre Distanz gross ist (Expansion
  vom Kernpunkt). N9e hat das am echten Bestand **beziffert**: 465 Gesichter,
  bei ``CLUSTER_SCHWELLE = 0.45`` eine Gruppe mit Durchmesser **1,0755** —
  also groesser als die Schwelle selbst.

  Dieses Werkzeug macht die Verkettung messbar und **ersetzbar**. Es stellt dem
  Dichte-Verfahren zwei Verfahren gegenueber, deren Verhalten anders ist:

    * ``vollstaendig_clustern`` — **agglomerative Complete-Linkage**: zwei
      Gruppen verschmelzen nur, wenn das **weiteste** Punktpaar beider Gruppen
      ``<= schwelle`` ist. Damit gilt die **Invariante**: der Durchmesser jeder
      Gruppe ist ``<= schwelle`` (ein Test belegt sie ueber mehrere Saatgueter).
    * ``mittelpunkt_clustern`` — **Mittelpunkt-Verfahren**: jeder Punkt geht zur
      naechsten Gruppe, wenn seine Distanz zu deren **Mittelpunkt** (normierter
      Mittelwert) ``<= schwelle`` ist, sonst neue Gruppe; danach werden die
      Mittelpunkte neu gerechnet und Gruppen mit Mittelpunkt-Abstand
      ``<= schwelle`` zusammengelegt, bis es stabil ist.

  Beide Verfahren sind **deterministisch** (die Eingabereihenfolge bestimmt das
  Ergebnis) und verwerfen **zu kleine Gruppen als Rauschen**, statt sie in eine
  Gruppe zu draengen. ``verfahren_messen`` und ``vergleich_bericht`` stellen die
  Zahlen der drei Verfahren je Schwelle nebeneinander; ``bericht_text`` gibt sie
  als deutschen Klartext aus.

Was dieses Werkzeug bewusst NICHT tut:
  * **Kein Loeschen.** Es gibt im ganzen Modul keinen Loeschaufruf — weder
    gegen eine Datei noch gegen einen Ordner. Tests pruefen die Abwesenheit.
  * **Kein Netz, kein Bild, kein Modell.** Nur ``numpy``; kein Bildpaket,
    keine Modell-Laufzeit, kein Download, kein Dienst-Aufruf. Ein Test prueft
    das (der Quelltext wird auf solche Namen abgesucht).
  * **Kein Schreiben ins Repo.** Der Bericht geht nur in einen Ordner
    **ausserhalb** des Repos; ein Repo-Pfad ergibt eine deutsche Klartextmeldung
    und ``SystemExit(2)``, geschrieben wird dann nichts.
  * **Keine Schluesselwerte, keine echten Namen.** Beschriftungen sind
    Struktur-Kennungen (z. B. Anlass-Namen) aus dem Aufrufer, nie Personennamen;
    Kennungen in Beispielen sind erfundene Platzhalter (``Person_A``).

Eingang: eine Liste ``eintraege`` — jeder Eintrag ist entweder direkt eine
Zahlenliste (``[0.1, -0.2, …]``) oder ein Dict mit dem Feld ``embedding`` (bzw.
``vektor``), so wie es ``gesicht_erkennen.py``/``face_infer.py`` liefern.
Unbrauchbare Eintraege (kein Vektor, falsche Laenge oder Text) werden **nicht**
geraten: sie kommen in keine Gruppe (und stuetzen nichts ab).

Bodenwahrheit (wenn ``beschriftungen`` uebergeben wird): zwei **erkennbare**
Gesichter im **selben** Bild sind **verschiedene** Personen. Daraus bildet
``personen_schwelle.bild_paare`` Paare; jedes Paar in **einer** Gruppe ist eine
belegte Falschaussage des Verfahrens (``verschmelzungsquote``).

Aufruf (Kommandozeile):: Standard ist der **Trockenlauf** (nichts geschrieben).

    .venv/Scripts/python.exe tools/foto_sortierung/personen_verkettung.py \\
        --vektoren ~/foto_sortierung/personen_vektoren_n9d.jsonl

    # Bericht wirklich ablegen (PFLICHT ausserhalb des Repos)
    ... --ausgabe ~/foto_sortierung/n9f_verkettung.json --schreiben

Als Modul (Tests, Skripte): ``main(argv=[...])``.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import math
import os

import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

# Vorgabepfade: ausserhalb des Repos — dort liegen Biometrie und Vektoren.
STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_VEKTOREN = os.path.join(STANDARD_BASIS, "personen_vektoren.jsonl")
STANDARD_AUSGABE = os.path.join(STANDARD_BASIS, "n9f_verkettung_bericht.json")

# ── Verfahren und Messgitter (alle Schwellen hier, keine im Aufrufer) ─────

# Name der drei Verfahren. ``dichte`` ist das N9a-Verfahren zum Vergleich,
# ``vollstaendig`` ist die Complete-Linkage (Durchmesser garantiert),
# ``mittelpunkt`` arbeitet ueber Mittelpunkte (normierte Mittelwerte).
VERFAHREN_DICHTE = "dichte"
VERFAHREN_VOLLSTAENDIG = "vollstaendig"
VERFAHREN_MITTELPUNKT = "mittelpunkt"
VERFAHREN = (VERFAHREN_DICHTE, VERFAHREN_VOLLSTAENDIG, VERFAHREN_MITTELPUNKT)
VERFAHREN_ALLE = "alle"

# Die Vorgabe-Schwelle der Verfahren: derselbe Wert wie ``CLUSTER_SCHWELLE``
# aus N9a (0.45). Sie steht als Zahl hier, damit die Verfahrenssignaturen eine
# lesbare Vorgabe haben; ist ein Argument unbrauchbar, faellt ``_schwelle`` auf
# den **geladenen** N9a-Wert zurueck.
SCHWELLE_STANDARD = 0.45

# Das Messgitter des Auftrags: der heutige Wert (0.45 = ``CLUSTER_SCHWELLE`` aus
# N9a) steht bewusst **mit** drin, damit der Ist-Zustand im Bericht sichtbar
# ist; darunter liegt ein grobes Gitter.
SCHWELLEN_STANDARD = (0.45, 0.40, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10)

# Eine Gruppe braucht mindestens so viele Mitglieder. Zu kleine Gruppen sind
# **Rauschen** und werden verworfen — nicht in eine Gruppe gedraengt.
MIN_GROESSE_STANDARD = 2

# Vergleichstoleranz fuer die Durchmesser-Invariante. Sie steht **nur** fuer
# Gleitkomma-Rauschen: die Distanzen werden einmal als Matrix und einmal als
# Punktpaar gerechnet, das sind zwei Wege zum selben Wert.
TOLERANZ = 1e-9

# Der Satz, der die Verkettung im Bericht erklaert (steht so im Klartext).
VERKETTUNG_HINWEIS = (
    "Das Dichte-Verfahren verknuepft TRANSITIV: ist A nah an B und B nah an C, "
    "landen A und C in einer Gruppe, obwohl ihre Distanz gross ist (Expansion "
    "vom Kernpunkt). Der Durchmesser einer Gruppe kann die Schwelle deshalb "
    "ueberschreiten. Die vollstaendige Verknuepfung verschmilzt nur, wenn das "
    "WEITESTE Punktpaar beider Gruppen <= Schwelle ist - der Durchmesser jeder "
    "Gruppe ist damit garantiert <= Schwelle.")


class VerkettungFehler(Exception):
    """Fehler dieses Werkzeugs — deutsche Klartextmeldung, kein Absturz."""


# ── Nachbarmodule laden (nichts nachbauen, was es schon gibt) ─────────────

_CACHE: dict = {}


def _laden(dateiname: str, modulname: str):
    """Ein Nachbarmodul aus demselben Ordner laden (defensiv, gecacht)."""
    if modulname not in _CACHE:
        pfad = os.path.join(HIER, dateiname)
        spez = importlib.util.spec_from_file_location(modulname, pfad)
        if spez is None or spez.loader is None:
            raise VerkettungFehler(f"{dateiname} nicht gefunden: {pfad}")
        modul = importlib.util.module_from_spec(spez)
        spez.loader.exec_module(modul)
        _CACHE[modulname] = modul
    return _CACHE[modulname]


def _personen_cluster():
    """``personen_cluster.py`` (N9a) laden — Dichte-Verfahren und Grundwerte."""
    return _laden("personen_cluster.py", "verkettung_personen_cluster")


def _personen_schwelle():
    """``personen_schwelle.py`` (N9e) laden — Bodenwahrheit der Bild-Paare."""
    return _laden("personen_schwelle.py", "verkettung_personen_schwelle")


def _ist_zahl(wert) -> bool:
    """Eine endliche Zahl (kein ``bool``) — sonst ``False``."""
    return _personen_cluster()._ist_zahl(wert)


def _liste(wert) -> list:
    """``wert`` als Liste — alles andere wird zur leeren Liste."""
    return _personen_cluster()._liste(wert)


def _text(wert) -> str:
    """Ein Feld als Text lesen — Nicht-Text und ``None`` werden zu ``\"\"``."""
    return _personen_cluster()._text(wert)


def _zahl(n) -> str:
    """Eine Zahl mit deutschen Tausenderpunkten (nur fuer die Ausgabe)."""
    return _personen_cluster()._zahl(n)


def _vektor_von(eintrag):
    """Den Vektor eines Eintrags lesen (Liste oder Dict mit ``embedding``)."""
    return _personen_cluster()._vektor_von(eintrag)


# ── Eingaben pruefen: Zahl oder Vorgabe, nie raten ────────────────────────

def _schwelle(wert) -> float:
    """Eine Schwelle als Zahl — unbrauchbare Werte fallen auf die N9a-Vorgabe."""
    if not _ist_zahl(wert):
        return float(_personen_cluster().CLUSTER_SCHWELLE)
    return max(0.0, float(wert))


def _min_groesse(wert) -> int:
    """Die Mindestgroesse als ganze Zahl ``>= 1`` — sonst die Vorgabe."""
    if not _ist_zahl(wert):
        return MIN_GROESSE_STANDARD
    return max(1, int(wert))


def _schwellen_liste(schwellen) -> list:
    """Die Schwellen als Liste — entdoppelt, unbrauchbare fallen weg.

    Leer oder nur Unbrauchbares ergibt das Standardgitter
    (``SCHWELLEN_STANDARD``) — gemessen wird immer etwas.
    """
    werte: list = []
    if schwellen is not None:
        for wert in _liste(schwellen):
            if not _ist_zahl(wert):
                continue
            zahl = float(wert)
            if zahl in werte:
                continue
            werte.append(zahl)
    return werte or list(SCHWELLEN_STANDARD)


# ── 1. Abstand und brauchbare Eintraege ───────────────────────────────────

def bezugslaenge(eintraege):
    """Die Vektor-Laenge, die die **Mehrheit** der brauchbaren Eintraege hat.

    Alle Verfahren muessen auf **derselben** Bezugslaenge rechnen, sonst waere
    ein einzelner Vektor mit falscher Laenge ein anderer Fall je Verfahren. Die
    Mehrheit ist hier die richtige Wahl (nicht der erste Eintrag): ein einzelner
    krummer Vektor darf nicht den ganzen Bestand unbrauchbar machen. Bei
    Gleichstand gewinnt die zuerst gesehene Laenge — deterministisch. ``None``,
    wenn es keinen brauchbaren Vektor gibt.
    """
    zaehler: dict = {}
    for eintrag in _liste(eintraege):
        vektor = _vektor_von(eintrag)
        if vektor is None:
            continue
        laenge = len(vektor)
        zaehler[laenge] = zaehler.get(laenge, 0) + 1
    bestes = None
    for laenge in zaehler:                     # Einfuegereihenfolge = Eingabe
        if bestes is None or zaehler[laenge] > zaehler[bestes]:
            bestes = laenge
    return bestes


def gueltige_indizes(eintraege) -> list:
    """Die Indizes aller Eintraege mit **brauchbarem** Vektor (Eingabereihenfolge).

    Brauchbar heisst: ``_vektor_von`` liest eine endliche Zahlenliste **und**
    sie hat die Bezugslaenge (``bezugslaenge``). Alles andere (``None``, Text,
    leerer Vektor, Wahrheitswert, **falsche Laenge**) kommt hier nicht vor und
    landet damit in keiner Gruppe — es wird nichts geraten.
    """
    laenge = bezugslaenge(eintraege)
    if laenge is None:
        return []
    ergebnis: list = []
    for nummer, eintrag in enumerate(_liste(eintraege)):
        vektor = _vektor_von(eintrag)
        if vektor is not None and len(vektor) == laenge:
            ergebnis.append(nummer)
    return ergebnis


def _abstand_der_gueltigen(eintraege):
    """``(indizes, matrix)`` der brauchbaren Eintraege — ``None``, wenn leer.

    Die Matrix ist die Cosinus-**Abstands**matrix (``1 - Kosinus``), gebaut
    ueber ``personen_cluster._einheit`` — genau die Rechnung, die
    ``personen_schwelle.distanzpaare`` schon benutzt (kein zweites Verfahren,
    keine zweite Skala).
    """
    pc = _personen_cluster()
    indizes: list = []
    vektoren: list = []
    for nummer in gueltige_indizes(eintraege):
        vektor = pc._vektor_von(_liste(eintraege)[nummer])
        if vektor is None:
            continue
        indizes.append(nummer)
        vektoren.append(vektor)
    if not vektoren:
        return None
    einheit = pc._einheit(vektoren)
    if einheit is None:
        return None
    aehnlich = np.clip(einheit @ einheit.T, -1.0, 1.0)
    return indizes, np.clip(1.0 - aehnlich, 0.0, 2.0)


def abstand_vektoren(a, b) -> float:
    """Cosinus-Distanz zweier Vektoren — ``1.0``, wenn sie nicht rechenbar ist.

    Reicht an ``personen_cluster.cosinus_distanz`` durch: ungleich lange,
    leere oder Null-Vektoren ergeben keine Aehnlichkeit und damit die neutrale
    Antwort ``1.0`` (kein Treffer, kein Absturz).
    """
    return float(_personen_cluster().cosinus_distanz(a, b))


def _einheitsvektor(vektor):
    """Ein Vektor der Laenge 1 — ``None``, wenn das nicht geht (Nullvektor)."""
    if vektor is None:
        return None
    a = np.asarray(vektor, dtype=float)
    if a.ndim != 1 or a.size == 0:
        return None
    laenge = float(np.linalg.norm(a))
    if laenge == 0.0 or not math.isfinite(laenge):
        return None
    return a / laenge


def _mittelpunkt(vektoren):
    """Der **normierte** Mittelwert von Vektoren — ``None``, wenn nicht rechenbar.

    Nur gleich lange Vektoren gehen ein (die Laenge des ersten brauchbaren
    zaehlt) — sonst waere der Mittelwert nicht definiert. Der Mittelwert wird
    normiert, weil die Cosinus-Distanz nur fuer Richtungen sinnvoll ist.
    """
    brauchbar = [vektor for vektor in _liste(vektoren) if vektor is not None]
    if not brauchbar:
        return None
    laenge = len(brauchbar[0])
    passend = [vektor for vektor in brauchbar if len(vektor) == laenge]
    if not passend:
        return None
    return _einheitsvektor(np.mean(np.asarray(passend, dtype=float), axis=0))


def _rauschen_entfernen(gruppen, min_groesse: int) -> list:
    """Zu kleine Gruppen (Rauschen) verwerfen — Indizes je Gruppe aufsteigend.

    Verworfen heisst **nicht** in eine Gruppe gedraengt: ein Einzelpunkt bleibt
    ein Einzelpunkt und verschwindet, statt an eine fremde Gruppe zu fallen.
    """
    sauber: list = []
    for gruppe in _liste(gruppen):
        indizes = sorted(int(index) for index in _liste(gruppe)
                         if _ist_zahl(index))
        if len(indizes) >= min_groesse:
            sauber.append(indizes)
    return sauber


# ── 2. Vollstaendige Verknuepfung (Complete-Linkage) ──────────────────────

def vollstaendig_clustern(eintraege, schwelle: float = SCHWELLE_STANDARD,
                          min_groesse: int = MIN_GROESSE_STANDARD) -> list:
    """Agglomerative **Complete-Linkage** — der Durchmesser ist garantiert.

    Zwei Gruppen werden **nur** verschmolzen, wenn das **weiteste** Punktpaar
    beider Gruppen ``<= schwelle`` ist (Complete-Linkage-Abstand = Maximum der
    Paarabstaende). Daraus folgt die **Invariante** dieses Verfahrens:

        der Durchmesser **jeder** Gruppe ist ``<= schwelle``.

    Der Unterschied zum Dichte-Verfahren ist genau die Verkettung: dort genuegt
    eine Kette naher Nachbarn (A-B nah, B-C nah), hier nicht — A und C kommen
    nur zusammen, wenn auch ``distanz(A, C) <= schwelle`` gilt.

    Ablauf: jeder brauchbare Eintrag startet als eigene Gruppe; dann wird
    solange das **naechste** Paar mit dem kleinsten Complete-Linkage-Abstand
    verschmolzen, wie dieser ``<= schwelle`` ist. Die Auswahl ist
    **deterministisch**: der Scan laeuft in Erzeugungsreihenfolge der Gruppen
    (Zeile zuerst, dann Spalte), der erste kleinste Wert gewinnt; die
    verschmolzene Gruppe bleibt an der Stelle der **ersten** Gruppe stehen.

    Gruppen mit weniger als ``min_groesse`` Mitgliedern sind **Rauschen** und
    werden verworfen. Rueckgabe: Liste von Index-Listen der Eingabe (jede Liste
    aufsteigend sortiert, Gruppen in Erzeugungsreihenfolge).
    """
    alle = _liste(eintraege)
    if not alle:
        return []
    grenze = _schwelle(schwelle)
    kleinste = _min_groesse(min_groesse)
    gebaut = _abstand_der_gueltigen(alle)
    if gebaut is None:
        return []
    gueltig, abstand = gebaut

    gruppen = [[index] for index in gueltig]
    anzahl = len(gruppen)
    # Distanzmatrix zwischen den Gruppen: Start = Punktabstaende (Complete-Linkage).
    distanz = np.array(abstand, dtype=float, copy=True)
    np.fill_diagonal(distanz, np.inf)

    while anzahl > 1:
        # Nur das obere Dreieck zaehlt — sonst waere jedes Paar doppelt da.
        sichtbar = np.where(np.triu(np.ones((anzahl, anzahl), dtype=bool), 1),
                            distanz, np.inf)
        stelle = int(np.argmin(sichtbar))
        a, b = divmod(stelle, anzahl)
        if sichtbar[a, b] > grenze:
            break                                # nichts mehr zu verschmelzen
        gruppen[a] = sorted(gruppen[a] + gruppen[b])
        # Complete-Linkage: das WEITESTE Punktpaar beider Gruppen zaehlt.
        neu = np.maximum(distanz[a, :], distanz[b, :])
        neu[a] = np.inf
        neu[b] = np.inf
        distanz[a, :] = neu
        distanz[:, a] = neu
        gruppen.pop(b)
        distanz = np.delete(np.delete(distanz, b, axis=0), b, axis=1)
        anzahl -= 1

    return _rauschen_entfernen(gruppen, kleinste)


# ── 3. Mittelpunkt-Verfahren ──────────────────────────────────────────────

def mittelpunkt_clustern(eintraege, schwelle: float = SCHWELLE_STANDARD,
                         min_groesse: int = MIN_GROESSE_STANDARD) -> list:
    """Clustern ueber **Mittelpunkte** (normierte Mittelwerte) — deterministisch.

    Zwei Schritte, solange bis es stabil ist:

      1. **Zuordnen** (einmal, in Eingabereihenfolge): jeder Punkt geht zur
         **naechsten** Gruppe, wenn seine Distanz zu deren Mittelpunkt
         ``<= schwelle`` ist — sonst gruendet er eine neue Gruppe. Bei
         Gleichstand gewinnt die **niedrigere** Gruppennummer. Nach jedem
         Zugang wird der Mittelpunkt der Gruppe neu gerechnet.
      2. **Verschmelzen** (bis stabil): liegen die Mittelpunkte zweier Gruppen
         ``<= schwelle`` auseinander, werden die Gruppen zusammengelegt und der
         Mittelpunkt neu gerechnet. Das wiederholt sich, bis kein Paar mehr
         unter der Schwelle liegt.

    Der Mittelpunkt ist der **normierte** Mittelwert der Mitglieder (Cosinus
    braucht Richtungen). Ist ein Mittelpunkt nicht rechenbar (z. B.
    Nullvektoren), gilt der Abstand ``1.0`` — es wird nichts geraten.

    Deterministisch: die Eingabereihenfolge bestimmt Zuordnung und Reihenfolge
    der Gruppen. Gruppen mit weniger als ``min_groesse`` Mitgliedern werden als
    **Rauschen verworfen** (nicht in eine Gruppe gedraengt). Rueckgabe: Liste
    von Index-Listen (jede aufsteigend sortiert, Gruppen in Erzeugungsreihenfolge).
    """
    alle = _liste(eintraege)
    if not alle:
        return []
    grenze = _schwelle(schwelle)
    kleinste = _min_groesse(min_groesse)
    gueltig = gueltige_indizes(alle)
    if not gueltig:
        return []

    gruppen: list = []
    mittel: list = []
    for index in gueltig:
        vektor = _vektor_von(alle[index])
        bester = None
        for nummer, zentrum in enumerate(mittel):
            wert = abstand_vektoren(vektor, zentrum)
            if bester is None or wert < bester[0]:
                bester = (wert, nummer)
        if bester is not None and bester[0] <= grenze:
            nummer = bester[1]
            gruppen[nummer].append(index)
            mittel[nummer] = _mittelpunkt(
                [_vektor_von(alle[mitglied]) for mitglied in gruppen[nummer]])
        else:
            gruppen.append([index])
            mittel.append(_einheitsvektor(vektor))

    # Verschmelzen, bis die Mittelpunkte auseinander genug liegen.
    zusammen = True
    while zusammen:
        zusammen = False
        for a in range(len(gruppen)):
            for b in range(a + 1, len(gruppen)):
                if abstand_vektoren(mittel[a], mittel[b]) > grenze:
                    continue
                gruppen[a] = sorted(gruppen[a] + gruppen[b])
                mittel[a] = _mittelpunkt(
                    [_vektor_von(alle[mitglied]) for mitglied in gruppen[a]])
                gruppen.pop(b)
                mittel.pop(b)
                zusammen = True
                break
            if zusammen:
                break

    return _rauschen_entfernen(gruppen, kleinste)


def gruppen_bilden(eintraege, verfahren: str, schwelle: float = SCHWELLE_STANDARD,
                   min_groesse: int = MIN_GROESSE_STANDARD) -> list:
    """Ein Verfahren auf die Eintraege anwenden — der Verteiler der drei.

    ``dichte`` reicht an ``personen_cluster.vektoren_clustern`` durch (dieselbe
    Rechnung wie N9a; ein Kernpunkt braucht ``min_groesse`` Nachbarn), die
    anderen beiden an ``vollstaendig_clustern``/``mittelpunkt_clustern``. Ein
    unbekannter Name ergibt ``VerkettungFehler`` mit Klartext — es wird nichts
    stillschweigend ersetzt.

    Unterschied bei krummen Vektoren: die beiden eigenen Verfahren messen auf
    der **Mehrheits**-Laenge (``bezugslaenge``); der durchgereichte N9a-Pfad
    benutzt dessen eigene Matrix, die die Laenge des **ersten** brauchbaren
    Vektors nimmt. Ein einzelner Vektor mit falscher Laenge kann den
    Dichte-Lauf dadurch stumm machen — das ist N9a-Verhalten, hier nicht
    umgebaut, und im Vergleich sichtbar.
    """
    name = _text(verfahren) or VERFAHREN_VOLLSTAENDIG
    grenze = _schwelle(schwelle)
    kleinste = _min_groesse(min_groesse)
    if name == VERFAHREN_DICHTE:
        gruppen = _personen_cluster().vektoren_clustern(
            eintraege, grenze, max(1, kleinste))
        sauber = []
        for gruppe in _liste(gruppen):
            indizes = sorted(int(index) for index in _liste(gruppe)
                             if _ist_zahl(index))
            if len(indizes) >= kleinste:
                sauber.append(indizes)
        return sauber
    if name == VERFAHREN_VOLLSTAENDIG:
        return vollstaendig_clustern(eintraege, grenze, kleinste)
    if name == VERFAHREN_MITTELPUNKT:
        return mittelpunkt_clustern(eintraege, grenze, kleinste)
    raise VerkettungFehler(f"Unbekanntes Verfahren: {verfahren}")


# ── 4. Kennzahlen einer Gruppe ────────────────────────────────────────────

def gruppen_durchmesser(gruppen, eintraege) -> dict:
    """Groesster Cosinus-Abstand je Gruppe — Durchmesser aus N9e.

    Reicht an ``personen_schwelle.gruppendurchmesser`` durch (kein zweites
    Verfahren). ``durchmesser_max`` ueber der Schwelle ist der Beleg fuer
    transitives Verketten.
    """
    return _personen_schwelle().gruppendurchmesser(gruppen, eintraege)


def zahlen_je_gruppe(gruppen, eintraege) -> dict:
    """Die Zahlen eines Gruppenergebnisses — rein, ohne I/O.

    ``{"gruppen", "groesste_gruppe", "gesichter_in_gruppen", "groessen",
    "durchmesser_je_gruppe", "durchmesser_max", "durchmesser_mittel"}``.
    Ohne Gruppen sind die Durchmesser ``0.0`` (kein ``None``), damit die
    Reihenfolge ``min <= mittel <= max`` immer lesbar bleibt.
    """
    liste = _liste(gruppen)
    groessen = [len(_liste(gruppe)) for gruppe in liste]
    durchmesser = gruppen_durchmesser(liste, eintraege)
    je_gruppe = [float(wert) for wert in _liste(durchmesser.get("je_gruppe"))]
    return {
        "gruppen": len(liste),
        "groesste_gruppe": max(groessen) if groessen else 0,
        "gesichter_in_gruppen": sum(groessen),
        "groessen": groessen,
        "durchmesser_je_gruppe": je_gruppe,
        "durchmesser_max": max(je_gruppe) if je_gruppe else 0.0,
        "durchmesser_mittel": (float(np.mean(np.asarray(je_gruppe, dtype=float)))
                               if je_gruppe else 0.0),
    }


# ── 5. Ein Verfahren ueber mehrere Schwellen messen ───────────────────────

def _bodenwahrheit_paare(eintraege, beschriftungen):
    """Bild-Paare erkennbarer Gesichter — ``None``, wenn keine Beschriftungen.

    Die **eigentliche** Bodenwahrheit ist eine Bildaussage: zwei erkennbare
    Gesichter im **selben** Bild sind zwei Personen. ``beschriftungen`` schaltet
    den Block ein; die Liste selbst ist ein **Strukturmass** (z. B. Anlass-Name)
    und ausdruecklich **keine** Identitaetsaussage — ein Anlass enthaelt legitim
    viele Personen. Gezaehlt wird sie als ``mit_beschriftung``.
    """
    if beschriftungen is None:
        return None
    return _personen_schwelle().bild_paare(eintraege)


def verfahren_messen(eintraege, verfahren: str, schwellen=None,
                     min_groesse: int = MIN_GROESSE_STANDARD,
                     beschriftungen=None) -> list:
    """Ein Verfahren ueber mehrere Schwellen messen — Liste, je Schwelle ein Dict.

    Je Schwelle (in der Reihenfolge der Schwellen, entdoppelt):
    ``verfahren``, ``schwelle``, ``min_groesse``, ``gruppen``,
    ``groesste_gruppe``, ``gesichter_in_gruppen``, ``verworfen`` (Rauschen),
    ``groessen``, ``durchmesser_max``, ``durchmesser_mittel`` (und
    ``durchmesser_je_gruppe``). ``verworfen`` zaehlt die brauchbaren Eintraege
    **ohne** Gruppe; damit gilt immer:
    ``gesichter_in_gruppen + verworfen == Anzahl brauchbarer Eintraege``.

    Mit ``beschriftungen`` (Liste je Eintrag) kommen die Felder der
    **Bodenwahrheit** dazu: ``personen_paare`` (Bild-Paare erkennbarer
    Gesichter, ``personen_schwelle.bild_paare``), ``verschmolzene_paare``,
    ``verschmelzungsquote`` (Anteil der Paare in **einer** Gruppe — jedes solche
    Paar ist eine belegte Falschaussage) und ``mit_beschriftung``. Die Paare
    werden **einmal** gerechnet und durchgereicht.
    """
    alle = _liste(eintraege)
    kleinste = _min_groesse(min_groesse)
    gueltig = gueltige_indizes(alle)
    paare = _bodenwahrheit_paare(alle, beschriftungen)
    labels = _liste(beschriftungen)
    messungen: list = []
    for grenze in _schwellen_liste(schwellen):
        gruppen = gruppen_bilden(alle, verfahren, grenze, kleinste)
        zahlen = zahlen_je_gruppe(gruppen, alle)
        zeile = {
            "verfahren": _text(verfahren) or VERFAHREN_VOLLSTAENDIG,
            "schwelle": float(grenze),
            "min_groesse": kleinste,
            "gruppen": zahlen["gruppen"],
            "groesste_gruppe": zahlen["groesste_gruppe"],
            "gesichter_in_gruppen": zahlen["gesichter_in_gruppen"],
            "verworfen": len(gueltig) - zahlen["gesichter_in_gruppen"],
            "groessen": zahlen["groessen"],
            "durchmesser_max": zahlen["durchmesser_max"],
            "durchmesser_mittel": zahlen["durchmesser_mittel"],
            "durchmesser_je_gruppe": zahlen["durchmesser_je_gruppe"],
        }
        if paare is not None:
            quote = _personen_schwelle().verschmelzungsquote(paare, gruppen)
            zeile["personen_paare"] = quote["paare"]
            zeile["verschmolzene_paare"] = quote["verschmolzen"]
            zeile["verschmelzungsquote"] = float(quote["quote"])
            zeile["mit_beschriftung"] = sum(1 for label in labels
                                            if label is not None)
        messungen.append(zeile)
    return messungen


# ── 6. Die drei Verfahren vergleichen ─────────────────────────────────────

def vergleich_bericht(eintraege, schwellen=None,
                      min_groesse: int = MIN_GROESSE_STANDARD,
                      beschriftungen=None) -> dict:
    """Die drei Verfahren ueber dieselben Schwellen vergleichen — reine Daten.

    Rueckgabe ``{"verfahren", "schwellen", "min_groesse", "eintraege",
    "gueltige_eintraege", "messungen", "vergleich", "hinweis", "stand"}``:

      * ``messungen`` — ``{verfahren: [Messzeilen aus ``verfahren_messen``]}``;
      * ``vergleich`` — je Schwelle **eine** Zeile mit den drei Verfahren
        (``{"schwelle", "dichte", "vollstaendig", "mittelpunkt"}``), damit der
        Unterschied direkt nebeneinander steht;
      * ``hinweis`` — der deutsche Satz zur Verkettung (``VERKETTUNG_HINWEIS``).

    Alles sind reine Daten (JSON-faehig), ohne Dateizugriff.
    """
    alle = _liste(eintraege)
    kleinste = _min_groesse(min_groesse)
    reihenfolge = _schwellen_liste(schwellen)
    messungen: dict = {}
    for name in VERFAHREN:
        messungen[name] = verfahren_messen(alle, name, reihenfolge, kleinste,
                                           beschriftungen)
    vergleich: list = []
    for nummer, grenze in enumerate(reihenfolge):
        zeile = {"schwelle": float(grenze)}
        for name in VERFAHREN:
            reihe = messungen[name]
            zeile[name] = reihe[nummer] if nummer < len(reihe) else None
        vergleich.append(zeile)
    return {
        "verfahren": list(VERFAHREN),
        "schwellen": [float(wert) for wert in reihenfolge],
        "min_groesse": kleinste,
        "eintraege": len(alle),
        "gueltige_eintraege": len(gueltige_indizes(alle)),
        "messungen": messungen,
        "vergleich": vergleich,
        "hinweis": VERKETTUNG_HINWEIS,
        "stand": datetime.datetime.now().isoformat(timespec="seconds"),
    }


def bericht_text(bericht) -> str:
    """Den Vergleich als deutschen Klartext ausgeben (feste Reihenfolge).

    Nennt zuerst die Verkettungs-Regel, dann die Zahlen: je Schwelle und
    Verfahren Gruppen, groesste Gruppe, Gesichter in Gruppen, verworfenes
    Rauschen und die Durchmesser (max/mittel). Zusaetzlich steht dabei, ob der
    Durchmesser die Schwelle **einhaelt** (``ja``/``nein``) — das ist die
    Invariante der vollstaendigen Verknuepfung. Fehlende oder krumme Daten
    kippen die Ausgabe nicht.
    """
    b = bericht if isinstance(bericht, dict) else {}
    messungen = b.get("messungen")
    if isinstance(messungen, dict):
        reihen = [(name, _liste(messungen.get(name))) for name in VERFAHREN]
    elif isinstance(messungen, list):
        name = _text(b.get("verfahren")) or VERFAHREN_VOLLSTAENDIG
        reihen = [(name, messungen)]
    else:
        reihen = []

    zeilen = [
        "Verkettungs-Messwerkzeug N9f — Dichte, vollstaendig, Mittelpunkt",
        f"Eintraege: {_zahl(b.get('eintraege'))}   "
        f"brauchbar: {_zahl(b.get('gueltige_eintraege'))}   "
        f"min_groesse: {_zahl(b.get('min_groesse'))}",
        "Verkettung: " + (_text(b.get("hinweis")) or VERKETTUNG_HINWEIS),
        "",
        "Schwelle   Verfahren       Gruppen   groesste   Gesichter   "
        "verworfen   Durchmesser max   mittel   Durchmesser <= Schwelle",
    ]
    for name, reihe in reihen:
        for eintrag in reihe:
            if not isinstance(eintrag, dict):
                continue
            grenze = eintrag.get("schwelle")
            gross = eintrag.get("durchmesser_max")
            if not _ist_zahl(gross):
                gross = 0.0
            einhaltung = "ja" if _ist_zahl(grenze) and float(gross) <= \
                float(grenze) + TOLERANZ else "nein"
            mittel = eintrag.get("durchmesser_mittel")
            zeilen.append(
                f"{float(grenze):>7.5f}   {name:<13}   "
                f"{_zahl(eintrag.get('gruppen')):>7}   "
                f"{_zahl(eintrag.get('groesste_gruppe')):>8}   "
                f"{_zahl(eintrag.get('gesichter_in_gruppen')):>9}   "
                f"{_zahl(eintrag.get('verworfen')):>9}   "
                f"{float(gross):>16.4f}   "
                f"{(float(mittel) if _ist_zahl(mittel) else 0.0):>6.4f}   "
                f"{einhaltung}")
            paare = eintrag.get("personen_paare")
            if _ist_zahl(paare):
                zeilen.append(
                    f"          Bodenwahrheit: {_zahl(eintrag.get('verschmolzene_paare'))} "
                    f"von {_zahl(paare)} Bild-Paaren in einer Gruppe   "
                    f"Quote: {100.0 * float(eintrag.get('verschmelzungsquote') or 0.0):.1f} %")
    if not reihen:
        zeilen.append("Keine Messwerte vorhanden.")
    return "\n".join(zeilen)


# ── 7. Schutz: nur ausserhalb des Repos schreiben ─────────────────────────

def pruefe_ausserhalb_repo(pfad: str) -> str:
    """Sicherstellen, dass ein Ausgabeziel AUSSERHALB des Repos liegt.

    Reicht an ``personen_cluster.pruefe_ausserhalb_repo`` durch — dieselbe
    Regel, dieselbe Meldung (kein zweites Verfahren). Ein Repo-Pfad ergibt
    ``SystemExit(2)``.
    """
    return _personen_cluster().pruefe_ausserhalb_repo(pfad)


def bericht_schreiben(pfad: str, bericht) -> str:
    """Den Bericht als JSON schreiben — **atomar**, nur ausserhalb des Repos.

    Geschrieben wird in eine ``.tmp``-Datei neben dem Ziel und dann per
    ``os.replace`` umgehoben: so liegt nie eine halbe Datei am Zielort. Ein
    Repo-Pfad ergibt ``SystemExit(2)``, geschrieben wird dann nichts.
    """
    pruefe_ausserhalb_repo(pfad)
    ordner = os.path.dirname(os.path.abspath(pfad))
    if ordner:
        os.makedirs(ordner, exist_ok=True)
    temp = pfad + ".tmp"
    with open(temp, "w", encoding="utf-8") as datei:
        json.dump(bericht, datei, ensure_ascii=False, indent=1)
        datei.write("\n")
    os.replace(temp, pfad)
    return pfad


# ── 8. Kommandozeile ──────────────────────────────────────────────────────

def _schwellen_aus_text(text):
    """``\"0.45,0.3,0.1\"`` -> ``[0.45, 0.3, 0.1]``; Unbrauchbares faellt weg."""
    if not isinstance(text, str):
        return []
    werte: list = []
    for teil in text.replace(";", ",").split(","):
        teil = teil.strip()
        if not teil:
            continue
        try:
            werte.append(float(teil))
        except ValueError:
            continue
    return werte


def main(argv=None) -> int:
    """Kommandozeilen-Teil: messen, vergleichen, Bericht zeigen (Standard: trocken).

    Standard ist der **Trockenlauf**: die Zahlen werden nur gezeigt, nichts
    geschrieben — und er laeuft **auch ohne** ``--ausgabe``. ``--ausgabe`` ist
    nur zusammen mit ``--schreiben`` Pflicht und muss **ausserhalb** des Repos
    liegen (sonst ``SystemExit(2)``). Geschrieben wird die JSON-Datei atomar.
    """
    zerleger = argparse.ArgumentParser(
        description="Verkettungs-Messwerkzeug N9f: beziffert die transitive "
                    "Verkettung des Dichte-Verfahrens und stellt ihm die "
                    "vollstaendige Verknuepfung (Durchmesser garantiert) und "
                    "das Mittelpunkt-Verfahren gegenueber. Aendert keine "
                    "Schwelle, loescht nichts, ruft kein Netz.")
    zerleger.add_argument("--vektoren", dest="vektoren", required=True,
                          help="Vektordatei (JSONL, ausserhalb des Repos)")
    zerleger.add_argument("--verfahren", dest="verfahren",
                          choices=list(VERFAHREN) + [VERFAHREN_ALLE],
                          default=VERFAHREN_ALLE,
                          help="dichte|vollstaendig|mittelpunkt|alle "
                               "(Standard: alle)")
    zerleger.add_argument("--schwellen", dest="schwellen", default=None,
                          help="Komma-Liste der Mess-Schwellen (Standard: "
                               + ", ".join(str(wert)
                                           for wert in SCHWELLEN_STANDARD) + ")")
    zerleger.add_argument("--min-groesse", dest="min_groesse", type=int,
                          default=MIN_GROESSE_STANDARD,
                          help=f"Mitglieder, ab denen eine Gruppe zaehlt "
                               f"(Standard {MIN_GROESSE_STANDARD}); darunter "
                               "gilt die Gruppe als Rauschen")
    zerleger.add_argument("--ausgabe", dest="ausgabe", default=None,
                          help="Zieldatei des Berichts (PFLICHT zusammen mit "
                               "--schreiben; PFLICHT ausserhalb des Repos)")
    zerleger.add_argument("--trocken", dest="trocken", action="store_true",
                          help="nichts schreiben (hat Vorrang vor --schreiben)")
    zerleger.add_argument("--schreiben", dest="schreiben", action="store_true",
                          help="den Bericht wirklich schreiben")
    args = zerleger.parse_args(argv)

    schreiben = bool(args.schreiben) and not bool(args.trocken)
    if args.ausgabe:
        pruefe_ausserhalb_repo(args.ausgabe)
    if schreiben and not args.ausgabe:
        print("Fehler: --schreiben braucht --ausgabe (ausserhalb des Repos).")
        return 2

    try:
        pc = _personen_cluster()
        eingelesen = pc.zeilen_lesen(args.vektoren)
        entscheidungen = [pc.bild_entscheidung(bild)
                          for bild in eingelesen["bilder"]]
        eintraege = pc.geclusterte_eintraege(eingelesen["bilder"],
                                             entscheidungen)
        schwellen = _schwellen_aus_text(args.schwellen) or list(SCHWELLEN_STANDARD)
        kleinste = _min_groesse(args.min_groesse)

        print("Verkettungs-Messwerkzeug N9f — "
              + ("Trockenlauf (es wird NICHTS geschrieben)" if not schreiben
                 else "Schreiben ist eingeschaltet"))
        print(f"Vektordatei: {args.vektoren}")
        print(f"Zeilen: {len(eingelesen['bilder'])}   "
              f"ungueltige Zeilen: {eingelesen['ungueltige_zeilen']}   "
              f"geclusterte Gesichter: {len(eintraege)}   "
              f"Schwellen: {len(schwellen)}   min_groesse: {kleinste}")

        if args.verfahren == VERFAHREN_ALLE:
            bericht = vergleich_bericht(eintraege, schwellen, kleinste)
        else:
            bericht = {
                "verfahren": args.verfahren,
                "schwellen": [float(wert) for wert in schwellen],
                "min_groesse": kleinste,
                "eintraege": len(eintraege),
                "gueltige_eintraege": len(gueltige_indizes(eintraege)),
                "messungen": verfahren_messen(eintraege, args.verfahren,
                                              schwellen, kleinste),
                "hinweis": VERKETTUNG_HINWEIS,
                "stand": datetime.datetime.now().isoformat(timespec="seconds"),
            }

        print(bericht_text(bericht))

        if schreiben:
            bericht_schreiben(args.ausgabe, bericht)
            print(f"Bericht geschrieben: {args.ausgabe}")
        else:
            if args.ausgabe:
                print(f"Geplant (nicht geschrieben): {args.ausgabe}")
            print("Ohne --schreiben wurde NICHTS geschrieben.")
        return 0
    except VerkettungFehler as problem:
        print(f"Fehler: {problem}")
        return 2
    except _personen_cluster().PersonenFehler as problem:
        print(f"Fehler: {problem}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
