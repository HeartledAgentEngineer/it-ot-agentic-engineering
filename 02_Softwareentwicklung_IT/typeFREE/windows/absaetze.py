"""Absätze bei langen Diktaten (Scheibe 4, 20.10.2026).

Reine Funktionen zum Einfügen von Absätzen (\n\n) bei langen Texten.
"""
from __future__ import annotations

import re

# Einteilige oder am Punkt endende Abkürzungen
ABK_PAT = re.compile(
    r'(?:^|[\s,;:(\[\"\'„«])(?:'
    r'z\.\s*b|d\.\s*h|u\.\s*[aä]|o\.\s*ä|u\.\s*u|i\.\s*d\.\s*r|'
    r'usw|bzw|ca|etc|vgl|ggf|evtl|inkl|bspw|sog|nr|dr|prof|hr|fr|st|str|s|abs|jh|mio|mrd|tel|ff'
    r')\.$',
    re.IGNORECASE,
)

# Mehrteilige Abkürzungen, bei denen auch die ersten Punkte nicht als Satzende zählen dürfen
MULTI_ABK_PAT = re.compile(
    r'\b(?:z\.\s*b|d\.\s*h|u\.\s*[aä]|o\.\s*ä|u\.\s*u|i\.\s*d\.\s*r)\.',
    re.IGNORECASE,
)

# Vorhandene Absätze: mindestens zwei Zeilenumbrüche, ggf. mit Leerraum dazwischen
EXISTIERENDE_ABSAETZE_PAT = re.compile(r'((?:[ \t]*\r?\n){2,}[ \t]*)')

# Satzende-Kandidat:
# Satzzeichen [.!?…], gefolgt von optionalen schließenden Anführungszeichen oder Klammern,
# gefolgt von Leerraum (mindestens ein Leerzeichen/Tab/Umbruch),
# gefolgt von Beginn des nächsten Satzes: optionales öffnendes Anführungszeichen/Klammer,
# dann ein Großbuchstabe.
SATZ_ENDE_PAT = re.compile(
    r'([.!?…][")”’‘“»«\]}]*)'      # Gruppe 1: Satzzeichen + schließende Zeichen
    r'(\s+)'                       # Gruppe 2: Leerraum zwischen den Sätzen
    r'(?=[„"“«»\'(\[]?[A-ZÄÖÜ])'   # Lookahead: nächster Satz beginnt groß
)


def _ist_abkuerzung_oder_zahl(abschnitt: str, punkt_pos: int) -> bool:
    """Prüft, ob der Punkt Teil einer Zahl (z. B. 3.) oder einer Abkürzung ist."""
    # Zahl vor dem Punkt: z. B. "3." oder "2."
    if punkt_pos > 0 and abschnitt[punkt_pos - 1].isdigit():
        return True

    # Mehrteilige Abkürzung prüfen (z. B. z. B., u. U., i. d. R.)
    start = max(0, punkt_pos - 12)
    end = min(len(abschnitt), punkt_pos + 12)
    sub = abschnitt[start:end]
    for m in MULTI_ABK_PAT.finditer(sub):
        m_start = start + m.start()
        m_end = start + m.end()
        if m_start <= punkt_pos < m_end:
            return True

    # Einteilige Abkürzungen
    text_bis_punkt = abschnitt[:punkt_pos + 1]
    return bool(ABK_PAT.search(text_bis_punkt))


def _wort_anzahl(text: str) -> int:
    """Zählt Wörter mit mindestens einem alphanumerischen Zeichen."""
    return len([w for w in text.split() if any(c.isalnum() for c in w)])


def _abschnitt_verarbeiten(abschnitt: str) -> tuple[str, int]:
    """Fügt in einen zusammenhängenden Textabschnitt (ohne vorhandene Doppelumbrüche) Absätze ein."""
    if not abschnitt.strip():
        return abschnitt, 0

    # Finde alle echten Satzgrenzen
    grenzen: list[tuple[int, int, int]] = []
    # (satz_ende, leerraum_start, leerraum_ende)

    for m in SATZ_ENDE_PAT.finditer(abschnitt):
        punkt_zeichen = m.group(1)[0]
        if punkt_zeichen == '.':
            punkt_pos = m.start(1)
            if _ist_abkuerzung_oder_zahl(abschnitt, punkt_pos):
                continue
        grenzen.append((m.end(1), m.start(2), m.end(2)))

    if not grenzen:
        return abschnitt, 0

    # Zerlege in Sätze und Leerräume
    saetze: list[str] = []
    leerraeume: list[str] = []

    pos = 0
    for satz_ende, l_start, l_ende in grenzen:
        saetze.append(abschnitt[pos:satz_ende])
        leerraeume.append(abschnitt[l_start:l_ende])
        pos = l_ende
    saetze.append(abschnitt[pos:])

    # Jetzt prüfen, wo Absätze eingefügt werden sollen
    neue_leerraeume: list[str] = list(leerraeume)
    woerter_seit_absatz = 0
    gehaltvoll_seit_absatz = 0
    eingefuegt = 0

    # Wir iterieren über die Sätze bis zum vorletzten Satz
    # (nach dem letzten Satz kommt nie ein Absatz!)
    for i in range(len(saetze) - 1):
        s = saetze[i]
        w = _wort_anzahl(s)
        woerter_seit_absatz += w
        if w >= 5:
            gehaltvoll_seit_absatz += 1

        if woerter_seit_absatz >= 45 or gehaltvoll_seit_absatz >= 4:
            neue_leerraeume[i] = '\n\n'
            woerter_seit_absatz = 0
            gehaltvoll_seit_absatz = 0
            eingefuegt += 1

    # Text wieder zusammenbauen
    ergebnis_teile = []
    for i in range(len(neue_leerraeume)):
        ergebnis_teile.append(saetze[i])
        ergebnis_teile.append(neue_leerraeume[i])
    ergebnis_teile.append(saetze[-1])

    return ''.join(ergebnis_teile), eingefuegt


def absaetze(text: str) -> tuple[str, int]:
    """Fügt bei langen Diktaten Absätze (\n\n) an geeigneten Satzenden ein.

    Regeln:
    - Nur Leerraum wird verändert (Buchstaben, Ziffern und Satzzeichen bleiben unverändert).
    - Vorhandene Absätze (mindestens zwei Zeilenumbrüche) bleiben exakt erhalten.
    - Die Wort- und Satzzählung beginnt nach jedem vorhandenen oder neu eingefügten Absatz neu.
    - Absatz nach einem Satzende, sobald seit dem letzten Absatz >= 45 Wörter oder >= 4 gehaltvolle
      Sätze (je >= 5 Wörter) erreicht sind.
    - Nach dem letzten Satz und vor dem ersten Satz kommt nie ein Absatz.
    """
    if not text:
        return text, 0

    # Aufteilen anhand existierender Absätze (die exakt erhalten bleiben)
    teile = EXISTIERENDE_ABSAETZE_PAT.split(text)
    gesamt_eingefuegt = 0
    ergebnis_teile = []

    for i, teil in enumerate(teile):
        if i % 2 == 1:
            # Das ist ein existierender Trenner (\n\n, \r\n\r\n etc.) -> unverändert übernehmen
            ergebnis_teile.append(teil)
        else:
            # Das ist Textinhalt
            neu_text, n = _abschnitt_verarbeiten(teil)
            ergebnis_teile.append(neu_text)
            gesamt_eingefuegt += n

    return ''.join(ergebnis_teile), gesamt_eingefuegt
