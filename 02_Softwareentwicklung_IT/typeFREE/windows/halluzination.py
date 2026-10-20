"""Erfundenen Text erkennen: Abspänne und Höflichkeitsfloskeln aus der Stille.

Nach cmagnussen/blitztext-app, HallucinationFilter.swift, MIT (Idee und
Phrasenlisten übernommen, Logik nach Python übertragen).

Whisper-artige Modelle erfinden bei Stille oder Rauschen Texte aus ihren
Trainingsdaten: Untertitel-Abspänne („Untertitel im Auftrag des ZDF, 2021") und
Höflichkeitsfloskeln („Vielen Dank.", „Thank you."). Die Wahrscheinlichkeit
„keine Sprache" taugt als Schranke nicht, weil die Modelle sie für diese Fälle
mit 0 melden. Stattdessen wird gemessen, wie viel der Aufnahme laut genug für
Sprache ist (`stimm_sekunden`).

Nur reine Funktionen, keine Abhängigkeit zu typefree.
"""
import numpy as np

# Abspänne und Verabschiedungen, die nie als Diktat gemeint sind.
# Normalisiert (siehe `schluessel`), ohne Jahreszahlen.
ABSPANN = frozenset({
    "untertitel im auftrag des zdf",
    "untertitel im auftrag des zdf für funk",
    "untertitelung im auftrag des zdf",
    "untertitelung des zdf",
    "untertitel des zdf",
    "untertitel der amara org community",
    "untertitel von der amara org community",
    "untertitel von amara org",
    "untertitel von stephanie geiges",
    "copyright wdr",
    "copyright swr",
    "vielen dank fürs zuschauen",
    "vielen dank für s zuschauen",
    "danke fürs zuschauen",
    "danke für s zuschauen",
    "abonniert den kanal",
    "bitte abonnieren",
    "abonniere meinen kanal",
    "subtitles by the amara org community",
    "subtitles by amara org",
    "thanks for watching",
    "thank you for watching",
    "thank you so much for watching",
    "please subscribe",
    "like and subscribe",
    "please like and subscribe",
})

# Kurze Wendungen, die Menschen wirklich sagen: Sie gelten nur dann als
# erfunden, wenn die Aufnahme kaum Sprache enthält.
ZWEIFELHAFT = frozenset({
    "vielen dank", "danke", "danke schön", "dankeschön", "tschüss", "tschüs",
    "bis zum nächsten mal", "bis bald", "bis dann", "das war s", "ende",
    "thank you", "thanks", "thank you very much", "you", "bye", "bye bye",
    "okay", "ok", "ja", "hmm", "hm", "mhm",
    "musik", "music", "applaus", "applause", "lachen",
    "swr", "wdr", "zdf", "ard",
})

# Weniger Sprache als das, und eine zweifelhafte Wendung gilt als erfunden.
MINDEST_STIMM_SEKUNDEN = 0.3

# Rahmenlänge und Pegelschwelle für „klingt nach Sprache" (ca. -40 dBFS).
_RAHMEN_SEKUNDEN = 0.03
_RMS_SCHWELLE = 0.01

_SATZENDE = '.!?…'


def normalisieren(text):
    """Klein, nur Buchstaben und Ziffern; alles andere wird ein Leerzeichen.

    Mehrere Trennzeichen hintereinander werden zu einem, am Rand bleibt keins.
    """
    teile = []
    wort = []
    for zeichen in (text or '').lower():
        if zeichen.isalnum():
            wort.append(zeichen)
        elif wort:
            teile.append(''.join(wort))
            wort = []
    if wort:
        teile.append(''.join(wort))
    return ' '.join(teile)


def schluessel(text):
    """Wie `normalisieren`, aber ohne reine Zahlwörter.

    So treffen „ZDF, 2021" und „ZDF 2017" beide den Eintrag „zdf".
    """
    return ' '.join(w for w in normalisieren(text).split(' ')
                    if w and not w.isnumeric())


def stimm_sekunden(daten, rate=16000):
    """Sekunden, die laut genug für Sprache sind: 30-ms-Rahmen mit RMS > 0,01.

    `daten` darf eindimensional oder (n, 1) sein (so liefert es das Mikrofon).
    Nur volle Rahmen zählen; der Rest am Ende fällt weg. Vektorisiert, damit
    auch lange Aufnahmen kein Python-Schleifen je Sample brauchen.
    """
    flach = np.asarray(daten, dtype=np.float32).reshape(-1)
    rahmen = max(1, int(rate * _RAHMEN_SEKUNDEN))
    anzahl = flach.size // rahmen
    if anzahl == 0:
        return 0.0
    block = flach[:anzahl * rahmen].reshape(anzahl, rahmen)
    rms = np.sqrt(np.mean(block * block, axis=1))
    laut = int(np.count_nonzero(rms > _RMS_SCHWELLE))
    return laut * rahmen / rate


def ist_erfunden(text, stimm_sek):
    """Ist der ganze Text ein Abspann oder (bei kaum Sprache) eine Floskel?

    Leerer Text ist nicht „erfunden" — das prüft der Aufrufer selbst.
    """
    schl = schluessel(text)
    if not schl:
        return False
    if schl in ABSPANN:
        return True
    return stimm_sek < MINDEST_STIMM_SEKUNDEN and schl in ZWEIFELHAFT


def _satzanfaenge(text):
    """Index 0 und jede Stelle nach „.!?…" plus Leerraum oder nach Zeilenumbruch.

    „Amara.org" bleibt ein Satz. Ein Anfang zählt nur, wenn danach noch Text kommt.
    """
    anfaenge = [0]
    ende = len(text)
    for i, zeichen in enumerate(text):
        folgt = i + 1
        if folgt >= ende:
            continue
        if zeichen in '\r\n':
            anfaenge.append(folgt)
        elif zeichen in _SATZENDE and text[folgt].isspace():
            anfaenge.append(folgt)
    return anfaenge


def _abspann_start(text):
    """Beginn des letzten bis drittletzten Satzes, wenn er ein Abspann ist."""
    if not text:
        return None
    for start in reversed(_satzanfaenge(text)[-3:]):
        if schluessel(text[start:]) in ABSPANN:
            return start
    return None


def abspann_entfernen(text):
    """Schneidet Abspänne am Textende ab („… bis morgen. Untertitel im Auftrag
    des ZDF, 2021." → „… bis morgen.").

    Geprüft werden die letzten ein bis drei Satzanfänge, vom spätesten zum
    frühesten; das Abschneiden wiederholt sich, bis nichts mehr passt. Arbeitet
    auf dem Text jedes Anbieters, deckt also jede Kette ab.
    """
    ergebnis = (text or '').strip()
    while True:
        start = _abspann_start(ergebnis)
        if start is None:
            return ergebnis
        ergebnis = ergebnis[:start].strip()
