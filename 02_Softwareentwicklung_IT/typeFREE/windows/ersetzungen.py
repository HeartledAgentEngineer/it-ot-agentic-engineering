"""Feste Ersetzungen (Scheibe 3, 20.10.2026).

Wiederkehrende Verhörer („klod kode" statt „Claude Code", „n acht n" statt
„n8n") sollen immer gleich korrigiert werden — ohne Modellaufruf. Die Regeln
stehen in `ersetzungen.txt` neben der `config.json`, eine je Zeile:

    gesprochen => geschrieben

Alles hier sind reine Funktionen plus ein kleiner Lader; `typefree` ruft sie nur
über `ersetzen()` auf und fängt jeden Fehler ab (ein Diktat darf nie an den
Ersetzungen scheitern). Die Logzeilen enthalten nie Diktattext oder Regelwörter,
nur Anzahlen.
"""
import functools
import logging
import os
import re

log = logging.getLogger('typefree')

# Zwischen den gesprochenen Wörtern: beliebig viele Leerzeichen oder Bindestriche
# („n acht n", „N-acht-N", „n  acht   n" sind dieselbe Regel).
_TRENNER = r'[\s\-]+'

VORLAGE = """\
# Feste Ersetzungen für typeFREE
#
# Eine Regel je Zeile:   gesprochen => geschrieben
#
# - Ganze Wörter, Groß-/Kleinschreibung egal. Zwischen den gesprochenen Wörtern
#   dürfen beliebig viele Leerzeichen oder Bindestriche stehen.
# - Längere Regeln gehen vor kürzeren; es wird in einem Durchgang ersetzt
#   (kein Ergebnis wird erneut ersetzt).
# - Steht rechts nichts, wird das Wort gelöscht.
# - Zeilen mit # am Anfang sind Kommentare, Leerzeilen werden übersprungen.
# - Kommt eine gesprochene Form doppelt vor, gilt die untere Zeile.
# - Die Datei wird bei jeder Änderung von selbst neu gelesen.
#
# Beispiele (zum Aktivieren das # am Anfang entfernen):
#
# n acht n => n8n
# klod kode => Claude Code
# typ frei => typeFREE
"""


def _woerter(gesprochen):
    """Die Wörter einer gesprochenen Form, getrennt an Leerraum und Bindestrichen."""
    return [w for w in re.split(_TRENNER, gesprochen) if w]


def _schluessel(woerter):
    """Normalform für den Vergleich doppelter Regeln."""
    return ' '.join(woerter).lower()


def einlesen(text):
    """Parst den Dateitext → `(regeln, kaputt)`.

    `regeln` ist eine Liste `(gesprochen, geschrieben)` in Dateireihenfolge,
    `kaputt` die Zahl der übersprungenen Zeilen (kein `=>`, leere linke Seite).
    Kaputte Zeilen werden gezählt, nie geworfen.
    """
    regeln, kaputt = [], 0
    for zeile in (text or '').lstrip('\ufeff').splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith('#'):
            continue
        links, pfeil, rechts = zeile.partition('=>')
        links, rechts = links.strip(), rechts.strip()
        if not pfeil or not _woerter(links):
            kaputt += 1
            continue
        regeln.append((links, rechts))
    return regeln, kaputt


@functools.lru_cache(maxsize=8)
def _vorbereiten(regeln):
    """`(Muster, Ersätze)` zu einem Regel-Tupel; das Muster wird so einmal gebaut.

    Doppelte gesprochene Formen: die spätere Zeile gewinnt. Längere Formen
    stehen in der Alternation zuerst (Zeichenlänge der Normalform, dann
    alphabetisch — stabil), denn `re` nimmt die erste passende Alternative.
    Jede Alternative ist eine eigene Gruppe; `lastindex` des Treffers sagt,
    welche Regel getroffen hat.
    """
    je_form = {}
    for gesprochen, geschrieben in regeln:
        woerter = _woerter(gesprochen)
        if woerter:
            je_form[_schluessel(woerter)] = (woerter, geschrieben)
    if not je_form:
        return None, ()
    formen = sorted(je_form, key=lambda k: (-len(k), k))
    alternativen, ersaetze = [], []
    for form in formen:
        woerter, geschrieben = je_form[form]
        alternativen.append('(' + _TRENNER.join(re.escape(w) for w in woerter) + ')')
        ersaetze.append(geschrieben)
    # (?<!\w)/(?!\w) statt \b: gilt auch für Regeln mit Satzzeichen am Rand, und
    # Umlaute/ß zählen als Wortzeichen (Unicode-\w).
    muster = re.compile(r'(?<!\w)(?:' + '|'.join(alternativen) + r')(?!\w)',
                        re.IGNORECASE)
    return muster, tuple(ersaetze)


def muster(regeln):
    """EIN kompilierter Ausdruck für alle Regeln (`None` bei leerer Liste)."""
    return _vorbereiten(tuple(regeln))[0]


def anwenden_gezaehlt(text, regeln):
    """Ersetzt alle Treffer in einem Durchgang → `(neuer_text, anzahl_treffer)`.

    Keine Überlappung und keine Kette (ein Ersatz wird nicht erneut geprüft);
    der Ersatz wird wörtlich eingesetzt (kein `\\1`). Löscht eine Regel (rechte
    Seite leer), wird der dadurch entstandene doppelte Leerraum an genau dieser
    Stelle zusammengezogen — fremde doppelte Leerzeichen bleiben stehen. Ein
    Satzzeichen direkt hinter der Lücke („gut äh.") zieht das Leerzeichen davor
    nicht mit.
    """
    if not text:
        return text, 0
    pat, ersaetze = _vorbereiten(tuple(regeln))
    if pat is None:
        return text, 0
    teile, pos, treffer = [], 0, 0
    for m in pat.finditer(text):
        teile.append(text[pos:m.start()])
        ersatz = ersaetze[m.lastindex - 1]
        pos = m.end()
        treffer += 1
        if ersatz:
            teile.append(ersatz)
            continue
        letztes = next((t for t in reversed(teile) if t), '')
        if not letztes or letztes[-1].isspace():
            while pos < len(text) and text[pos].isspace():
                pos += 1
    teile.append(text[pos:])
    return ''.join(teile), treffer


def anwenden(text, regeln):
    """Wie `anwenden_gezaehlt`, gibt nur den Text zurück."""
    return anwenden_gezaehlt(text, regeln)[0]


class Ersetzungen:
    """Die Regeldatei, bei Änderung (mtime/Größe) neu gelesen.

    - Datei fehlt → leere Liste, kein Fehler.
    - Lesefehler (gesperrt, kein UTF-8) → die letzte gültige Liste bleibt; geloggt
      wird einmal je Dateistand, damit ein Dauerfehler das Log nicht flutet.
    """

    def __init__(self, pfad):
        self.pfad = pfad
        self.kaputt = 0
        self._stand = None          # (mtime_ns, größe), nach dem Lesen oder "fehlt"
        self._regeln = []
        self._fehler_stand = None   # Stand, für den der Lesefehler schon geloggt ist

    def regeln(self):
        try:
            info = os.stat(self.pfad)
        except FileNotFoundError:
            self._stand, self._regeln, self.kaputt = 'fehlt', [], 0
            return list(self._regeln)
        except OSError:
            return self._lesefehler('fehlt-nicht-lesbar')
        stand = (info.st_mtime_ns, info.st_size)
        if stand == self._stand:
            return list(self._regeln)
        try:
            with open(self.pfad, 'rb') as f:
                text = f.read().decode('utf-8-sig')
        except (OSError, ValueError):
            return self._lesefehler(stand)
        self._regeln, self.kaputt = einlesen(text)
        self._stand = stand
        self._fehler_stand = None
        log.info('Ersetzungen geladen: %d Regeln, %d Zeilen übersprungen',
                 len(self._regeln), self.kaputt)
        return list(self._regeln)

    def _lesefehler(self, stand):
        if self._fehler_stand != stand:
            self._fehler_stand = stand
            log.warning('Ersetzungen: Datei nicht lesbar — letzte gültige Regeln '
                        'bleiben (%d)', len(self._regeln))
        return list(self._regeln)

    def anwenden(self, text):
        """`(neuer_text, anzahl_treffer)` mit den aktuellen Regeln."""
        return anwenden_gezaehlt(text, self.regeln())


def anlegen_falls_fehlt(pfad):
    """Schreibt die Vorlage, wenn die Datei fehlt — überschreibt nie."""
    try:
        with open(pfad, 'x', encoding='utf-8') as f:
            f.write(VORLAGE)
    except FileExistsError:
        pass
