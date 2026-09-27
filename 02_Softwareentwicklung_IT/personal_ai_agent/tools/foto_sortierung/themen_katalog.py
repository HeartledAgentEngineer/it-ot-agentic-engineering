"""Fester Themen-Katalog fuer das Foto-Themen-Werkzeug (Schritt N6c, 27.09.2026).

Wozu dieser Katalog:
  Der Vision-Blick je Anlass (``foto_themen_vision.py``) durfte sein Thema
  bisher **frei erfinden**. Der Massenlauf N6b hat gezeigt, wohin das fuehrt:
  **155 verschiedene Themen bei 161 Anlaessen = 96 % Einzelstuecke** — als
  Ordnerbaum ``Agent/Fotos/<Jahr>/<Thema>/`` untauglich, weil jedes Foto
  faktisch einen eigenen Ordner bekaeme und dasselbe Motiv zerstreut laege.

  Deshalb waehlt das Modell sein Thema jetzt aus dieser **festen Liste**
  (hoechstens 44 Eintraege je Jahr); alles, was nicht Wort fuer Wort passt,
  faellt auf ``Sonstiges``. Der Ordnerbaum unter ``Agent/Fotos/<Jahr>/`` bleibt
  dadurch **beschraenkt** (harte Obergrenze statt offener Wortliste) — genau
  das ist der Zweck des Katalogs.

Warum diese Regeln fuer die Eintraege gelten (sie sind Ordnernamen):
  * 2 bis 4 deutsche Woerter — kurz genug fuer Ordner, klar genug zum Sortieren.
  * kein ``/`` und ``\\``, keine verbotenen Zeichen (``: * ? " < > |``),
    hoechstens 60 Zeichen, kein fuehrendes/abschliessendes Sonderzeichen.
  * keine Doppelungen, nicht rein numerisch.
  * ``Sonstiges`` als LETZTER Eintrag faengt alles Unklare (der Rueckfall),
    damit wirklich **jeder** Anlass einen Ordner bekommt und der Baum trotzdem
    beschraenkt bleibt.

Aenderungen an der Liste hochziehen:
  **Wer ``THEMEN_KATALOG`` aendert, erhoeht ``KATALOG_VERSION``.** Die Version
  benennt den Stand des Wortschatzes; Themen aus verschiedenen Staenden sind
  nicht vergleichbar (dieselbe Antwort kann vorher ``Sonstiges`` gewesen sein
  und danach ein Treffer).

Dieses Modul ist **rein**: kein Netz, kein Dateizugriff, kein Zufall. Es wird
von ``foto_themen_vision.py`` per Pfad geladen (das Werkzeug liegt ausserhalb
des Backends) und ist auch einzeln importierbar::

    from themen_katalog import THEMEN_KATALOG, thema_zuordnen, katalog_text
"""

from __future__ import annotations

import re

# Stand des Wortschatzes (siehe Docstring: bei Aenderungen hochziehen).
KATALOG_VERSION = 2

# Der Rueckfall: alles, was keinem Eintrag WORT FUER WORT entspricht.
SONSTIGES = "Sonstiges"

# Rand-Satzzeichen, die beim Vergleichen abgestreift werden (Gross/Klein und
# ein Punkt am Satzende duerfen den Treffer nicht kaputt machen).
RAND_SATZZEICHEN = ".,;:!?\"'`-_"

# Beim Abstreifen zaehlt Leerraum mit (nach dem Zusammenziehen ist nur noch
# einfacher Leerraum uebrig).
_RAND_ZEICHEN = RAND_SATZZEICHEN + " "

# Derselbe Zeichenvorrat wie VERBOTENE_ZEICHEN in foto_themen_vision.py:
# Ordnernamen auf Windows und in der pCloud.
VERBOTENE_ZEICHEN = re.compile(r'[/\\:*?"<>|\x00-\x1f]')

# Ordnername-Grenze wie THEMA_MAX_ZEICHEN in foto_themen_vision.py.
KATALOG_MAX_ZEICHEN = 60

# Wortzahl je Eintrag (Sonstiges ist der einzige einwortige Rueckfall).
WOERTER_MIN = 2
WOERTER_MAX = 4

# Der Katalog: feste Themen, gruppiert nach Lebensbereichen. Reihenfolge ist
# die Ausgabereihenfolge in ``katalog_text()`` und im Prompt. Genau 44
# Eintraege, der letzte ist ``Sonstiges``.
THEMEN_KATALOG: list[str] = [
    # Personen & Familie
    "Familienfeier Zuhause",
    "Kindergeburtstag Zuhause",
    "Babybauch Fotoshooting",
    "Familienausflug Wochenende",
    # Haus & Garten
    "Haus und Garten",
    "Gartenarbeit im Freien",
    "Balkon und Terrasse",
    "Blumen im Garten",
    # Natur & Landschaft
    "Wandern im Schnee",
    "Wanderung im Wald",
    "See und Fluss",
    "Berg und Tal",
    "Strand und Meer",
    # Tiere
    "Hund im Freien",
    "Katze Zuhause",
    "Tiere im Zoo",
    # Stadt & Reisen
    "Stadtbummel Altstadt",
    "Reise und Urlaub",
    "Ausflug ins Umland",
    "Museum und Ausstellung",
    # Veranstaltungen & Feste
    "Fest und Feier",
    "Weihnachtsmarkt Besuch",
    "Konzert und Buehne",
    "Geburtstag mit Gaesten",
    # Arbeit & Technik
    "Arbeit am Schreibtisch",
    "Technik und Geraete",
    "Computer und Bildschirm",
    # Essen & Trinken
    "Essen und Trinken",
    "Kochen in der Kueche",
    "Restaurant Besuch",
    "Kuchen und Gebaeck",
    # Sport & Bewegung
    "Sport und Fitness",
    "Laufen und Joggen",
    "Spiel und Bewegung",
    # Fahrzeuge
    "Auto und Strasse",
    "Fahrrad und Radweg",
    "Zug und Bahnhof",
    # Innenraum & Alltag
    "Wohnung und Einrichtung",
    "Aufraeumen Zuhause",
    "Fenster und Licht",
    # Bauen & Handwerk
    "Bauen und Renovieren",
    "Handwerk und Werkzeug",
    "Baustelle und Geruest",
    # Rueckfall (MUSS der letzte Eintrag sein)
    SONSTIGES,
]


def thema_normalisieren_katalog(text) -> str:
    """Einen Themen-Text fuer den Vergleich mit dem Katalog vereinheitlichen.

    Nicht-String und leer ergeben ``""`` (kein Raten). Sonst: Kleinschreibung,
    Mehrfach-Leerraum zu einem Leerzeichen, Rand-Leerraum UND Rand-Satzzeichen
    (``.,;:!?"'`-_``) abstreifen. Damit trifft ``"  See   und Meer.  "`` den
    Eintrag ``"See und Meer"``.
    """
    if not isinstance(text, str):
        return ""
    sauber = re.sub(r"\s+", " ", text.lower()).strip()
    return sauber.strip(_RAND_ZEICHEN)


def thema_zuordnen(antwort) -> str:
    """Den Katalog-Eintrag zu einer Modellantwort finden — sonst ``Sonstiges``.

    Nach der Normalisierung muss es ein **exakter** Treffer sein; zurueck kommt
    der Katalog-Eintrag im **Original-Wortlaut** (so landet nie eine
    abgewandelte Schreibweise im Ordnerbaum). Kein Treffer, kein String oder
    leer: ``Sonstiges``.
    """
    sauber = thema_normalisieren_katalog(antwort)
    if not sauber:
        return SONSTIGES
    for eintrag in THEMEN_KATALOG:
        if thema_normalisieren_katalog(eintrag) == sauber:
            return eintrag
    return SONSTIGES


def im_katalog(antwort) -> bool:
    """True NUR bei einem echten Katalogeintrag — nicht beim Sonstiges-Rueckfall.

    Anders gesagt: Wahr ist es, wenn die Antwort (nach Normalisierung) irgendwo
    in ``THEMEN_KATALOG`` steht. ``Sonstiges`` selbst ist ein Katalogeintrag und
    damit wahr; alles Fremde (z. B. ``"Drache ueber Hamburg"``) ist falsch.
    """
    sauber = thema_normalisieren_katalog(antwort)
    if not sauber:
        return False
    return any(thema_normalisieren_katalog(eintrag) == sauber
               for eintrag in THEMEN_KATALOG)


def katalog_text() -> str:
    """Alle Eintraege mit ``" | "`` verbunden, in Katalog-Reihenfolge.

    Genau diese Zeichenkette steht ausgeschrieben im Prompt — das Modell darf
    nur hieraus waehlen.
    """
    return " | ".join(THEMEN_KATALOG)
