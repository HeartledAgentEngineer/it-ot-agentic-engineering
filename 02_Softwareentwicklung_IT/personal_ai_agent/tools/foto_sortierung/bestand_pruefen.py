"""Bestand pruefen — unabhaengiger Nachweis in Zahlen (01.10.2026).

Warum:
  Sebastian will nicht glauben muessen, was ein Agent ueber die Nachtlaeufe
  meldet („ist wirklich alles beschrieben, sind alle Gesichter fertig und
  gruppiert?"). Dieses Werkzeug zaehlt selbst nach — nur lesend, nur Zahlen.

Was verglichen wird (je Sortierplan, Fotos und Videos getrennt):
  * Gesichter Fotos:  Plan-Fotos  <->  Zeilen in den Vektordateien (``bild_id``)
  * Gesichter Videos: Plan-Videos <->  ``*.videos_fertig`` + Video-Vektorzeilen
  * Beschreibungen:   Plan-Fotos  <->  jede Beschreibungsdatei ueber ``fileid``;
                      Standard sind ``bild_beschreibungen.jsonl`` (Altspeicher),
                      ``bild_beschreibungen_papa_reich.jsonl`` (Papas Fotos,
                      reiche Fassung — eigener Lauf, weil Papas Plan andere
                      Feldnamen traegt), ``bild_beschreibungen_reich.jsonl``
                      (reiche Fassung der Sammlung) und
                      ``bild_beschreibungen_rest_reich.jsonl`` (Nachzuegler).
                      Die frueher gemeldeten 3 + 5 Luecken der Einzelplaene sind
                      in Wahrheit versorgt — nur eine Deckung ueber ALLE Quellen
                      sagt, ob wirklich ein Foto fehlt.
  * Gesamtplan:       ``sortierplan_reich_gesamt.json`` (Union aller Plaene)
                      <->  alle Beschreibungsdateien zusammen. Beantwortet die
                      Frage „ist der ganze Bestand beschrieben?" in einer Zeile;
                      der Plan mischt die Feldnamen (``von_name`` bei Sammlung/
                      Sortierplan, ``name`` bei Papas Plan) — hier wird deshalb
                      wie im Beschreibungs-Werkzeug BEIDE Formen gelesen.
                      Fehlende Fotos werden nicht nur gezaehlt, sondern mit
                      Kennung und Grund benannt (``--luecken-details``, Standard
                      20): ``keine Vektorzeile`` (kein Gesichtslauf), ``ohne
                      Bildmasse`` (Vektorzeile ohne Breite/Hoehe — das Bild war
                      beim Beschreibungslauf nicht ladbar) oder ``Bild geladen,
                      kein Beschreibungseintrag`` (offener Rest). Zusaetzlich
                      wird vermerkt, wenn derselbe Dateiname im Plan mehrfach
                      vorkommt (Dublette, nur die Zahl — nie der Name).
                      Seit 12.10.2026 rechnet die Zeile die Kennungen in BILDER
                      um (``bilder_zaehlen``): dasselbe Foto kann unter zwei
                      Kennungen im Plan stehen, und die Zahl vor Sebastians
                      Kostenentscheidung soll Bilder zaehlen, nicht Dateien.
                      Dazu nennt sie die Endungen der nicht ladbaren Dateien
                      (Format, kein Name). **Der Name ist dabei nur ein Hinweis:**
                      dieselbe Zahl wird zusaetzlich auf die Pruefsummen der
                      Duplikat-Pruefung gestuetzt (gleiche Groesse UND gleiche
                      Pruefsumme = derselbe Inhalt, ``duplikate.json``) — nur das
                      ist belegt, und nur das darf sich „dasselbe Bild" nennen.
  * Gruppen:          ``personen_gruppen/personen_beispiele.json`` und
                      ``gesicht_zuordnung.jsonl`` (fehlen sie, lief der
                      Gruppierer nur trocken) — mit Abdeckung: wie viele der
                      groessten Gruppen enthalten 50/80/90 % aller Gesichter.
  * Orte (OSM):       ``bild_orte.csv`` (eine Zeile je Bild, aus den
                      OpenStreetMap-Karten) — Zeilen, Bilder mit/ohne GPS,
                      Bilder im Flug, mit Ortsname/Landmarke/Strasse/Hausnummer,
                      dazu die Zahl der ausgewerteten Kartengebiete
                      (``osm/csv/<gebiet>``). Damit ist der Karten-Zweig
                      (Schritt 3c der Papas-Kette) genauso nachpruefbar wie die
                      uebrigen Stufen — er stand bisher in KEINEM Nachweis.
                      Nur Zahlen: keine Ortsnamen, keine Koordinaten.
  * Bildindex:        ``bild_index.db`` (Bildsuche; Beschreibungen als Vektoren,
                      Ketten-Schritt 7) — Bilder, mit Vektor, mit Beschreibung,
                      Modell/Dimension/Token/Kosten aus dem eigenen ``meta``,
                      dazu der Abgleich gegen die Beschreibungsdateien:
                      „beschrieben, aber ohne Vektor im Index\" ist die eine
                      offene Richtung (die Bildsuche waere unvollstaendig),
                      „im Index, aber nicht beschrieben\" die andere. Nur Zahlen —
                      keine Beschreibungstexte, keine Ordner, keine Vektoren.
                      Der Bildindex stand bisher in KEINEM Nachweis, obwohl er der
                      Schluss der Kette ist.
  * Anlaesse:         ``ordner_ereignisse.jsonl`` (Ketten-Schritt 5: Anlass aus
                      EXIF/Dateiname/Ordnerjahr, Gebuendelung nach >18 h Pause) —
                      Anlaesse, Datei-Kennungen, Videos, wie viele Anlaesse ein
                      Datum tragen und woher es kommt (Quellen-Schluessel aus
                      ``quellen.datum``), die Jahresspanne und die Deckung gegen
                      die Plan-Fotos. Diese Stufe traegt „Anlaesse einer Person"
                      und das Erzaehlen und stand bisher in KEINEM Nachweis. Nur
                      Zahlen — keine Titel, keine Themen, keine Kategorien.
  * Orte (GeoNames): ``orte.jsonl`` (Ketten-Schritt 3b, ``orte_zuordnen.py``:
                      je Bild Land/Region/naechster Ort + Aufnahmedatum, offline;
                      anhaengend und idempotent) — Zeilen, Bilder (Kennungen),
                      doppelte Zeilen (ein nicht-idempotenter Lauf wuerde
                      auffallen), Laender/Regionen/Orte als ANZAHL, Zeilen mit
                      Datum und die Deckung gegen die Plan-Fotos. Diese Stufe
                      traegt die Auskunft „wo war das?" und die Ortsnamen fuer
                      die Erzaehlung und stand bisher in KEINEM Nachweis — wie
                      OSM, Bildindex und Anlaesse. Nur Zahlen: keine Ortsnamen,
                      keine Koordinaten.
  * Erzaehl-Anlaesse: ``ereignisse.jsonl`` (Anlaesse der Sammlung) und
                      ``fotobuch_ereignisse.jsonl`` (Fotobuch-Seiten) — genau die
                      beiden Dateien, die ``erzaehl_service._ereignisse_laden()``
                      zusammen mit ``ordner_ereignisse.jsonl`` liest, um
                      Geschichten anzuhaengen. Nur die dritte hatte bisher einen
                      Nachweis; fehlt eine der beiden, fehlen dem Erzaehlen ihre
                      Anlaesse, ohne dass es auffiele. Gezaehlt werden Anlaesse,
                      Datei-Kennungen, Zeilen ohne Kennung (der Dienst verwirft
                      sie still), Datum + Quellen-Schluessel, Jahresspanne und die
                      Deckung gegen die Plan-Fotos. Nur Zahlen — keine Titel,
                      keine Buchseiten, keine Texte.
  * Beziehungen:      ``beziehungen.jsonl`` (15.051 Aussagen „wer war mit wem
                      wo" — Anlass, Datum, Unterart, beteiligte Personen) und die
                      Uebersicht ``beziehungen.json`` (Kennzahlen). Beide liest
                      der Dienst ``beziehungen_service`` (Antwortstufe N28) — und
                      beide standen in KEINEM Nachweis. Gezaehlt werden Aussagen,
                      Anlaesse, Tage, Unterarten, Personen-Eintraege (bestaetigt /
                      mit Kennung), Kategorien, Datumsspanne; die Uebersicht wird
                      gegen die gemessene Zeilenzahl gestellt (Kennzahlen und
                      Datei muessen zusammenpassen). Nur Zahlen — keine Namen,
                      keine Chat-Namen, keine Themen, keine Ordner.
  * Personen:         ``personen_bestaetigt.json`` (Kennung -> Name), dazu die
                      Vorgaben, die Profile (Beziehung/Notizen/Kontakt), das
                      Telefonbuch ``kontakte.json``, der Quiz-Stand und das
                      Protokoll — genau die Dateien, die ``gruppen_quiz`` fuer die
                      Chat-Werkzeuge ``personen_liste`` / ``person_auskunft`` /
                      ``fotos_mit_person`` liest (Quiz-Quelle statt alter
                      Gesichtskatalog, 10.10.2026). Die Gruppen wurden bisher
                      gezaehlt, die NAMEN nicht: faellt oder halbiert sich die
                      Datei, findet die Personen-Auskunft niemanden mehr, ohne
                      dass es auffiele. Zwei ehrliche Pruefungen: Kennungen OHNE
                      Gruppe (Name ohne Gesichter) und verschiedene Namen. Nur
                      Zahlen — NIE ein Personenname, nie eine Nummer, nie ein
                      Geburtstag.
  * Fotos-Uebersicht: ``fotos_uebersicht.json`` (N11: die Zahlen der App —
                      Events, Jahre, Kategorien, Themen) und ``fotos_dateien.json``
                      (N13a: je Event die Datei-Kennungen fuer die Bildvorschau).
                      Beide leitet das PC-Werkzeug aus ``sortierplan.json`` ab und
                      uebergibt sie ans Handy; gelesen werden sie von
                      ``services/foto_uebersicht.py`` / ``services/foto_bilder.py``
                      (router/fotos.py und das Chat-Werkzeug). KEINE der beiden
                      hatte eine Pruefzeile. Der Nachweis zaehlt je Datei die
                      Kennzahlen und stellt die beiden gegeneinander (Events und
                      Dateien muessen gleich sein) — nur Zahlen, keine Event-Namen,
                      keine Dateinamen, keine Kategorien-Namen.
  * Doppelte:         ``duplikate.json`` (``pcloud_duplikate.py``: Pruefsummen-
                      Vergleich der zwei pCloud-Baeume ``Automatic Upload`` und
                      ``Bilder & Videos`` — nur lesend, es wird nie geloescht) —
                      Duplikat-Gruppen, betroffene Dateien, Groesse aller Kopien
                      und der Loesch-Kandidaten, je Baum die gelesenen Ordner und
                      Dateien samt Vollstaendigkeit (``abgebrochen`` /
                      ``offen_gelassen`` / ``ohne_hash``) und ein Abgleich der
                      Zusammenfassung gegen die wirklich gezaehlten Gruppen
                      (Kennzahlen und Liste muessen zusammenpassen). Diese Datei
                      ist die Entscheidungsgrundlage „was ist doppelt?" und stand
                      bisher in KEINEM Nachweis — dieselbe Luecke wie bei OSM,
                      Bildindex, Anlaessen, Ortsnamen, Erzaehl-Quellen,
                      Beziehungen, Personen und der App-Uebersicht. Nur Zahlen:
                      kein Dateiname, kein Pfad, keine Pruefsumme.
  * Eigene Erzaehl-Stufen: ``geschichten.jsonl`` (Sebastians eigene Erzaehlungen
                      zu einem Anlass oder einem Bild, Schicht „mensch\") und
                      ``anlass_umbenennung.jsonl`` (eigene Anlassnamen; ein leerer
                      Name setzt auf den automatischen Titel zurueck). Beide
                      schreibt die App am GERAET, beide wachsen nur anhaengend und
                      beide liest der Erzaehl- UND der Notizdienst — sie standen in
                      KEINEM Nachweis. Gezaehlt werden Geschichten, Anlaesse,
                      Quellen-Schluessel, abgeloeste Fassungen, Zeilen OHNE
                      brauchbare Kennung (der Dienst verwirft sie STILL), tote
                      ``ersetzt``-Verweise und — der eigentliche Fehlerfall — eigene
                      Texte/Titel, deren Anlass es nicht mehr gibt (sie zeigen ins
                      Leere). Am PC heisst „nicht vorhanden\" ehrlich „noch nicht
                      angelegt\", nicht „Luecke\". Nur Zahlen: NIE ein
                      Geschichtentext, NIE ein eigener Titel.
  * Uebergabe (Handy): ``uebergabe_manifest.jsonl`` — der Weg, auf dem die
                      gebauten Ergebnisdateien aufs GERAET kommen (Ketten-Schritt 9).
                      Zwei Wege bestehen: das Kabel (``tools/handy/
                      uebergabe_uebernehmen.py``, Namensliste in
                      ``termux/start-vorbereiten.sh``) und kabellos ueber pCloud
                      (``tools/pcloud/uebergabe_hochladen.py`` laedt nach
                      ``/Agent/uebergabe``, das Geraet holt sie mit
                      ``termux/pcloud-uebernehmen.sh``). JEDE Uebertragung bucht eine
                      Zeile im Manifest (ausserhalb des Repos) — und dieses Manifest
                      stand in KEINER Pruefzeile, obwohl genau daran am 10.10. ein
                      echter Fehler auffiel: das Geraet haette eine VERALTETE
                      ``bild_index.db`` geholt, weil die frische Fassung noch nicht
                      hochgeladen war (von Hand gefunden, nicht vom Nachweis). Der
                      Nachweis stellt jetzt je uebertragener Datei die lokale Fassung
                      gegen die JUENGSTE Buchung (Groesse UND Pruefsumme): gleich,
                      geaendert (das Geraet holt die alte Fassung) oder lokal nicht
                      mehr vorhanden. Grenze (ehrlich): verglichen wird offline gegen
                      die letzte Buchung — ein spaeterer Wechsel der Datei IM
                      pCloud-Ordner ist ohne Netzabruf nicht sichtbar. Nur Zahlen und
                      die eigenen Ergebnis-Dateinamen, kein Pfad, kein Inhalt.
  * Uebergabe-Listen: die ``--dateien``-Listen der Startskripte
                      (``termux/start-vorbereiten.sh``, ``start-termux.sh``) gegen
                      die Dateinamen gestellt, die der Dienst wirklich liest
                      (``backend/app``, per AST — Zeichenketten, keine
                      Kommentare). Gezaehlt werden die Namen je Liste, ob die
                      mehrfachen Aufrufstellen derselben Liste uebereinstimmen,
                      welche gelesenen Dateien auf KEINER Liste stehen (sie
                      kaemen nie ans Geraet — dieselbe Fehlerklasse wie die
                      fehlende Bildindex-Uebergabe am 10.10.) und welche
                      uebergebenen Dateien KEIN Dienst liest (benannt, keine
                      Luecke). Dateien, die das Geraet selbst erzeugt oder ueber
                      einen eigenen Weg holt, stehen in einer begruendeten
                      Ausnahmeliste (sonst waere jede Quiz-/Postfach-Datei ein
                      Dauerfehlalarm). Ueber ``--uebergabe-listen`` steuerbar
                      (leer = nicht pruefen; die uebrigen Pruefungen bleiben
                      dadurch unveraendert). Nur Zahlen und Dateinamen.
  * Rueckweg (Handy -> PC): ``rueckweg_manifest.jsonl`` — das Gegenstueck zur
                      Uebergabe. Die Dateien, die die APP AM GERAET erzeugt
                      (``geschichten.jsonl`` = eigene Erzaehlungen,
                      ``anlass_umbenennung.jsonl`` = eigene Anlassnamen), liegen
                      im Termux-Heimordner und sind ueber das Kabel NICHT lesbar
                      (gemessen 12.10.: „Permission denied\"). Das Geraet KOPIERT
                      sie mit ``termux/rueckweg-bereitstellen.sh`` in
                      ``/sdcard/Download/hermes_rueckweg``, der PC holt sie mit
                      ``tools/handy/rueckweg_holen.py`` und bucht je Datei eine
                      Manifest-Zeile (Bytes, sha256, Zeit, ``richtung:
                      handy->pc``). Damit sind die beiden Stufen „Eigene
                      Geschichten\"/„Eigene Titel\" die einzigen, die bisher NUR in
                      eine Richtung nachpruefbar waren; der Nachweis stellt jetzt
                      je gebuchter Datei die lokale Fassung gegen die JUENGSTE
                      Buchung: unversehrt (Bytes UND Pruefsumme), abweichend (am
                      PC liegt nicht die geholte Fassung), am PC fehlt. Dazu die
                      Zahl der Namen ohne Rueckweg (Zeile, keine Luecke: welche
                      Datei nur am Geraet lebt, ist eine Entscheidung). Ueber
                      ``--rueckweg`` steuerbar (leer = nicht pruefen). Grenze
                      (ehrlich): was seit dem Holen AM GERAET dazukam, ist ohne
                      Kabel nicht sichtbar. Nur Zahlen und Dateinamen — NIE ein
                      Geschichtentext, NIE ein eigener Titel.
  * pCloud-Operationen: ``manifest.jsonl`` — das Manifest der SCHREIBENDEN
                      Operationen auf dem fremden System pCloud (Ordner anlegen,
                      Archiv entpacken, verschieben, loeschen; Standard
                      ``~/foto_sortierung/manifest.jsonl``, nie im Repo). Es ist
                      die einzige Antwort auf die Frage „wie mache ich das
                      rueckgaengig?" (AGENTS.md: „Jede schreibende Operation auf
                      einem fremden System kommt in ein Manifest […], damit sie
                      zurueckgenommen werden kann") — und stand in KEINER
                      Pruefzeile, obwohl in der Nacht 32 Archive entpackt und
                      Ordner angelegt wurden. Gezaehlt werden Buchungen, nicht
                      lesbare Zeilen, Buchungen ohne Art und ohne Ziel (dann gibt
                      es nichts zurueckzufahren), doppelte Buchungen (ein
                      Rueckroll-Lauf wuerde sie zweimal fahren) und die Arten.
                      Ehrlich getrennt: ZURUECKFAHRBAR sind nur die Arten, die das
                      Rueckroll-Werkzeug wirklich faehrt (``movefile``,
                      ``movefolder`` — Verschiebungen); ``createfolder`` wird nur
                      GEMELDET (das Werkzeug entfernt angelegte Ordner
                      ausdruecklich nicht) und alles Uebrige — z. B.
                      ``extractarchive`` — hat keine Rueckroll-Regel. Die
                      Zeitspanne steht in Tagen. Grenze (ehrlich): offline
                      pruefbar ist nur das Manifest, nicht ob die Operation auf
                      pCloud noch so steht. Nur Zahlen und die technischen
                      Arten-Namen — kein Datei-/Ordnername, kein Pfad, kein
                      Inhalt. Ueber ``--bewegungen`` steuerbar (leer = nicht
                      pruefen).
  * Archiv:           das Chat-/WhatsApp-Archiv (Schwesterordner des Projekts,
                      ueber ``--archiv`` steuerbar; Voreinstellung der Ordner
                      neben dem Projekt, ``--archiv ""`` schaltet es ab) — die
                      Stufe, aus der JEDE Archiv-Antwort im Chat ihre Fundstellen
                      zieht (``archiv_suche``, seit dem 10.10. der Standardweg;
                      der alte Weg ``archiv_service`` liest ``db/memory.db``).
                      Gezaehlt werden die Rohdaten ``normalized/messages.jsonl``
                      (Zeilen, nicht lesbare, ohne Quelle/Text, Quellen als
                      Zahl), der volle Index ``db/archiv_index.db`` (Nachrichten,
                      Gespraeche, Chunks, davon mit Vektor, Vektoren samt Waisen
                      und Modell/Dimension, Volltextindex, Selbstauskunft aus
                      ``meta``) und die Textschicht ``db/memory.db``. Ehrliche
                      Pruefungen, jede wird zur Luecke: Zeilen gegen Nachrichten
                      im Index (die Textschicht gegen beide), eine Quelle ohne
                      Nachricht im Index, Chunks ohne Vektor, Vektoren != Chunks
                      mit Vektor, verwaiste Vektoren, ein unvollstaendiger
                      Volltextindex (die Volltextsuche liefert dann still zu
                      wenig) und eine Selbstauskunft, die der Zaehlung
                      widerspricht. Zeitstempel
                      werden als Jahresspanne gemeldet, dazu die Zahl der
                      Nachrichten vor 1990 und in der Zukunft (Kalendereintraege
                      mit alten Jahren). Nur Zahlen und Quellen-NAMEN — kein
                      Nachrichtentext, kein Titel, kein Gespraechsname.
  Standard-Plaene: ``sortierplan.json``, ``sortierplan_bildervideos.json`` und
  ``sortierplan_papa.json`` (Papas 6.336 Amazon-Fotos); Standard-Vektordateien
  entsprechend inkl. ``personen_vektoren_papa.jsonl``. Ohne Papa in dieser Liste
  blieb sein ganzer Bestand ungeprueft — die fruehere Annahme „erkennt Papa
  ueber die Kennungen automatisch\" traf nicht zu (Befund 10.10.2026).
  Jede Vektor-/Beschreibungsdatei wird ueber die Kennungen SELBST den Plaenen
  zugeordnet — es kommt nicht darauf an, welche Datei zu welchem Plan gehoert.
  Kennungen werden immer als Text verglichen (Plaene: Zahl, Vektorzeilen: Text).

Ausgabe: nur Zaehlungen und Dateinamen (ohne Pfad). Keine Namen, keine
Beschreibungen, keine Koordinaten, keine Vektoren. Es wird nichts geschrieben.

Aufruf:
    python tools/foto_sortierung/bestand_pruefen.py
    python tools/foto_sortierung/bestand_pruefen.py --basis D:/foto_sortierung
Exit-Code 0 (Bericht), 2 = Basisordner fehlt.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
# Papas Plan traegt die Feldnamen name/ordner und fehlte hier ganz — sein
# Bestand (6.336 Fotos) blieb damit ungeprueft (Befund 10.10.2026).
STANDARD_PLAENE = ("sortierplan.json", "sortierplan_bildervideos.json", "sortierplan_papa.json")
STANDARD_FOTO_VEKTOREN = ("personen_vektoren_n0929_voll.jsonl",
                          "personen_vektoren_n0929_bildervideos.jsonl",
                          "personen_vektoren_papa.jsonl")
STANDARD_VIDEO_VEKTOREN = ("video_vektoren_bildervideos.jsonl", "video_vektoren_upload.jsonl")
# Mehrere Beschreibungsquellen: Altspeicher, Papas reiche Fassung (eigener
# Lauf, eigene Datei — der Altspeicher enthaelt Papa nicht), die reiche Fassung
# der Sammlung und der Nachzuegler-Lauf.
STANDARD_BESCHREIBUNGEN = ("bild_beschreibungen.jsonl", "bild_beschreibungen_papa_reich.jsonl",
                           "bild_beschreibungen_reich.jsonl", "bild_beschreibungen_rest_reich.jsonl")
# Union aller Plaene — die einzige Stelle, an der sich „ist wirklich jedes Foto
# beschrieben?" fuer den GESAMTEN Bestand ablesen laesst (10.10.2026).
STANDARD_GESAMTPLAN = "sortierplan_reich_gesamt.json"
# Eine Zeile je Bild, aus den OSM-Karten (orte_aus_karte.py --zuordnen).
STANDARD_BILD_ORTE = "bild_orte.csv"
# Der Bildindex (Ketten-Schritt 7): Beschreibungen als Vektoren fuer die Bildsuche.
# Er stand bisher in keinem Nachweis — und ist der Schluss der Kette.
STANDARD_BILDINDEX = "bild_index.db"
BILDINDEX_TABELLE = "bilder"
# Die Neuausrichtung: gedreht_plan.json listet die Bilder, die neu gedreht und
# neu erkannt wurden (personen_vektoren_gedreht_neu.jsonl). Diese Stufe stand in
# KEINEM Nachweis — 51 Bilder fehlten dort zwei Tage unbemerkt (50 davon ueber
# 8 MB; gleiche Ursache wie bei Papas 24: KACHEL_MAX_BYTES = 8 MB vor dem Fix
# vom 10.10.). Der Nachweis prueft die Stufe jetzt genauso wie die Plaene.
STANDARD_GEDREHT_PLAN = "gedreht_plan.json"
STANDARD_GEDREHT_VEKTOREN = "personen_vektoren_gedreht_neu.jsonl"
# Die Anlaesse (Ketten-Schritt 5): je Anlass ein Datum und die Bild-Kennungen,
# aus EXIF/Dateiname/Ordnerjahr/Planjahr gebuendelt. Sie tragen die Funktionen
# „Anlaesse einer Person" (person_auskunft) und das Erzaehlen. Diese Stufe stand
# in KEINEM Nachweis — gebaut am 10.10. (2.268 Anlaesse ueber den Union-Plan),
# aber niemandem auffaellig, wenn die Datei fehlt oder halb ist. Der Nachweis
# prueft sie jetzt wie die uebrigen Stufen (nur Zahlen, keine Titel).
STANDARD_ANLAESSE = "ordner_ereignisse.jsonl"
# Die Ortsnamen (Ketten-Schritt 3b): je Bild eine Zeile aus den offline
# GeoNames-Daten — Land, Region, naechster Ort, Aufnahmedatum (orte_zuordnen.py,
# anhaengend und idempotent: vorhandene bild_id wird uebersprungen). Diese Stufe
# stand in KEINEM Nachweis, obwohl sie die Auskunft „wo war das?" und die
# Ortsnamen fuer die Erzaehlung traegt — dieselbe Luecke wie bei OSM, Bildindex
# und Anlaessen. Der Nachweis prueft sie jetzt wie die uebrigen Stufen: nur
# Zahlen und Zaehlungen von Land/Region/Ort — keine Namen, keine Koordinaten.
STANDARD_ORTE_NAMEN = "orte.jsonl"
# Die beiden uebrigen Erzaehl-Quellen: ``ereignisse.jsonl`` (Anlaesse der
# Sammlung aus ``ereignisse_bauen.py``, 2.127 Anlaesse) und
# ``fotobuch_ereignisse.jsonl`` (Fotobuch-Seiten aus ``fotobuch_lesen.py``).
# ``erzaehl_service._ereignisse_laden()`` liest genau diese beiden PLUS
# ``ordner_ereignisse.jsonl`` — und nur die dritte hatte einen Nachweis. Fehlt
# ``ereignisse.jsonl``, fehlen dem Erzaehlen 2.127 Anlaesse, und es merkt heute
# niemand (dieselbe Luecke wie bei OSM, Bildindex, Anlaessen und Ortsnamen).
STANDARD_ERZAHL_QUELLEN = ("ereignisse.jsonl", "fotobuch_ereignisse.jsonl")
# Die Beziehungen (N27e/N28): ``beziehungen.jsonl`` (15.051 Aussagen „wer war
# mit wem wo" — je Zeile Anlass, Datum, Unterart und die beteiligten Personen)
# und die kleine ``beziehungen.json`` (Kennzahlen). Beide liest der Dienst
# ``beziehungen_service`` (Antwortstufe N28, ``router/beziehungen.py`` und das
# Chat-Werkzeug) — und BEIDE standen in KEINEM Nachweis. Faellt die Aussagen-
# Datei weg oder halbiert sie sich, schweigt die Auskunft „wer war mit wem wo",
# und es merkt heute niemand (dieselbe Luecke wie bei OSM, Bildindex, Anlaessen,
# Ortsnamen und den Erzaehl-Quellen). Der Nachweis zaehlt sie mit: nur Zahlen —
# keine Namen, keine Chat-Namen, keine Themen, keine Ordner.
STANDARD_BEZEIHUNGEN = "beziehungen.jsonl"
STANDARD_BEZEIHUNGEN_UEBERSICHT = "beziehungen.json"
# Die Personen-Stufe (Ketten-Schritt 3/4, Quiz + Telefonbuch): die Chat-Werkzeuge
# ``personen_liste`` / ``person_auskunft`` / ``fotos_mit_person`` lesen seit dem
# 10.10. die QUIZ-Quelle (``gruppen_quiz.personen()``) statt des alten
# Gesichtskatalogs — bestaetigte Namen (personen_bestaetigt.json), Vorgaben
# (personen_vorgaben.json), Profile mit Beziehung/Notizen/Kontakt
# (personen_profile.json) und das Telefonbuch (kontakte.json). Die ganze Stufe
# stand in KEINEM Nachweis: die Gruppen werden gezaehlt, die NAMEN nicht. Faellt
# oder halbiert sich personen_bestaetigt.json, findet ``personen_liste``
# niemanden mehr und es merkt heute niemand (dieselbe Luecke wie bei OSM,
# Bildindex, Anlaessen, Ortsnamen, Erzaehl-Quellen und Beziehungen). Der
# Nachweis zaehlt sie mit: nur Zahlen — NIE einen Personennamen, nie eine
# Telefonnummer, nie einen Geburtstag.
STANDARD_PERSONEN = "personen_bestaetigt.json"
PERSONEN_VORGABEN = "personen_vorgaben.json"
PERSONEN_PROFILE = "personen_profile.json"
PERSONEN_KONTAKTE = "kontakte.json"
PERSONEN_STAND = "gruppen_quiz_stand.json"
PERSONEN_PROTOKOLL = "gruppen_antworten.jsonl"
# Die abgeleiteten App-Dateien der Fotos-Uebersicht (N11/N13a): ``fotos_uebersicht.json``
# (nur Zahlen und Event-Namen — gelesen von ``services/foto_uebersicht.py``) und
# ``fotos_dateien.json`` (je Event die Datei-Kennungen fuer die Bildvorschau —
# gelesen von ``services/foto_bilder.py``; beide ueber ``router/fotos.py`` und das
# Chat-Werkzeug). Beide entstehen aus ``sortierplan.json`` und werden ans Handy
# uebergeben — und KEINE der beiden hatte eine Pruefzeile. Faellt eine weg oder
# halbiert sie sich, zeigt die App falsche Zahlen oder keine Vorschaubilder, und es
# merkt heute niemand (dieselbe Luecke wie bei OSM, Bildindex, Anlaessen, Ortsnamen,
# Erzaehl-Quellen, Beziehungen und Personen). Der Nachweis zaehlt sie mit: nur
# Zahlen — kein Event-Name, kein Dateiname, kein Kategorien-Name.
STANDARD_APP_UEBERSICHT = "fotos_uebersicht.json"
STANDARD_APP_DATEIEN = "fotos_dateien.json"
# Die Duplikat-Pruefung per Pruefsumme (``tools/pcloud/pcloud_duplikate.py``) —
# Entscheidungsgrundlage „was ist doppelt, was wuerde eine Freigabe bringen?"; die
# Datei liegt ausserhalb des Repos und wird von Sebastian selbst ausgewertet
# (Loeschen ist Handarbeit). Sie stand in KEINER Pruefzeile — dieselbe Luecke wie
# bei OSM, Bildindex, Anlaessen, Ortsnamen, Erzaehl-Quellen, Beziehungen, Personen
# und der App-Uebersicht. Fällt die Datei weg oder halbiert sie sich, faellt die
# Entscheidungsgrundlage weg, ohne dass es auffiele. Der Nachweis zaehlt sie mit:
# nur Zahlen — kein Dateiname, kein Pfad, keine Pruefsumme.
STANDARD_DUPLIKATE = "duplikate.json"
# Die Erzaehl-Stufen, die SEBASTIAN selbst fuellt (Schicht "mensch",
# ``services/erzaehl_service.py``): ``geschichten.jsonl`` (eigene Erzaehlungen zu
# einem Anlass oder einem einzelnen Bild — je Zeile ``id``, ``ersetzt`` fuer die
# abgeloeste Fassung) und ``anlass_umbenennung.jsonl`` (eigene Titel fuer
# Anlaesse; ein leerer Name setzt auf den automatischen Titel zurueck). Beide
# werden vom Erzaehl- UND vom Notizdienst gelesen, beide wachsen **nur
# anhaengend**, und beide entstehen am GERAET (die App schreibt sie) — am PC
# lagen sie damit in KEINEM Nachweis. Faellt eine weg oder zeigt ihre Kennung auf
# einen Anlass, den es nicht mehr gibt, verschwindet Sebastians eigener Text still
# (dieselbe Luecke wie bei OSM, Bildindex, Anlaessen, Ortsnamen, Erzaehl-Quellen,
# Beziehungen, Personen, App-Uebersicht und Doppelten). Der Nachweis zaehlt sie
# mit: nur Zahlen — NIE ein Geschichtentext, NIE ein eigener Titel.
STANDARD_GESCHICHTEN = "geschichten.jsonl"
STANDARD_TITEL = "anlass_umbenennung.jsonl"
# Die Uebergabe-Stufe (Ketten-Schritt 9) — der Weg, auf dem die gebauten
# Ergebnisdateien aufs GERAET kommen. Zwei Wege bestehen: das Kabel
# (``tools/handy/uebergabe_uebernehmen.py``, Namensliste in
# ``termux/start-vorbereiten.sh``) und kabellos ueber pCloud
# (``tools/pcloud/uebergabe_hochladen.py`` laedt nach ``/Agent/uebergabe``, das
# Geraet holt sie mit ``termux/pcloud-uebernehmen.sh``). Jede Uebertragung bucht
# eine Zeile im Manifest (ausserhalb des Repos). Dieses Manifest stand in KEINER
# Pruefzeile — dieselbe Luecke wie bei OSM, Bildindex, Anlaessen, Ortsnamen,
# Erzaehl-Quellen, Beziehungen, Personen, App-Uebersicht, Doppelten und den
# eigenen Erzaehl-Stufen. Genau daran fiel am 10.10. ein echter Fehler auf: das
# Geraet haette eine VERALTETE ``bild_index.db`` geholt (von Hand gefunden). Der
# Nachweis zaehlt jetzt je uebertragener Datei nach, ob die lokale Fassung noch
# zur juengsten Buchung passt. Nur Zahlen und die eigenen Ergebnis-Dateinamen.
STANDARD_UEBERGABE_MANIFEST = "uebergabe_manifest.jsonl"
UEBERGABE_GLEICH = "gleich"
UEBERGABE_GEAENDERT = "geaendert"
UEBERGABE_FEHLT_LOKAL = "fehlt_lokal"
# Die Uebergabe-LISTEN (Deckung der Uebergabe-Stufe): WELCHE Dateien gehen
# ueberhaupt ans Geraet? Die Startskripte nennen die Liste, jedes zweimal (mit
# und ohne ``|| true``) — zwei Stellen, die auseinanderlaufen koennen. Stellen
# sie gegen die Dateinamen, die ``backend/app`` wirklich liest (AST): eine Datei,
# die ein Dienst liest und die auf KEINER Liste steht, kaeme nie ans Geraet —
# dieselbe Fehlerklasse wie die fehlende Bildindex-Uebergabe vom 10.10. Seit dem
# 10.10. gibt es ZWEI Wege: die Kabel-Liste hier und die kabellose Uebergabe
# (pCloud-Ordner ``/Agent/uebergabe``). Der kabellose Weg hat im Baum gar keine
# Liste — was er liefert, steht nur in den Buchungen des Uebergabe-Manifests
# (``STANDARD_UEBERGABE_MANIFEST``); deshalb wird er von dort gelesen und je Weg
# berichtet, was ausschliesslich dort ankommt. Nur Zahlen und die eigenen
# Ergebnis-Dateinamen, kein Pfad, kein Inhalt.
STANDARD_UEBERGABE_LISTEN = ("termux/start-vorbereiten.sh", "start-termux.sh")
# Diese Liste ist PFLICHT (der gemeinsame Startweg fuer App-Knopf und Widget).
STANDARD_UEBERGABE_LISTE_PFLICHT = "termux/start-vorbereiten.sh"
STANDARD_DIENST_ORDNER = os.path.join("backend", "app")
# Ein einfacher Dateiname mit einer dieser Endungen zaehlt als Datenablage.
# Kein Pfadtrenner, kein Leerzeichen, kein Punkt am Anfang — damit fallen
# Textbausteine wie ``".csv"`` (ein Endungs-Rest in ``chat.py``) heraus.
DIENST_DATEI_MUSTER = re.compile(
    r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*\.(?:json|jsonl|db|csv)$")
# Die ``--dateien``-Zeile bis zum Zeilenende, dem Zeilenumbruch ``\`` oder ``||``.
_LISTEN_MUSTER = re.compile(r"--dateien\s+(.+?)(?:\s*\\\s*$|\s*\|\|.*$|\s*$)")
# Dateien, die das GERAET selbst erzeugt oder ueber einen EIGENEN Weg holt — sie
# gehoeren nicht in die ``--dateien``-Liste. Jede Aufnahme braucht einen Grund:
# ohne Grund gehoert die Datei auf die Liste, und ihr Fehlen dort ist ein echter
# Befund (die Zahl „ohne Liste\" in der Pruefzeile).
UEBERGABE_GERAETESEITIG = {
    "archiv_index.db": "Archiv am Geraet (eigener Weg ueber /sdcard/Download)",
    "personen_bestaetigt.json": "Quiz am Geraet (Namen werden dort bestaetigt)",
    "personen_vorgaben.json": "Quiz am Geraet (Vorgaben gleich/verschieden/ausgeschlossen)",
    "personen_profile.json": "Quiz am Geraet (Beziehung/Notizen)",
    "gruppen_quiz_stand.json": "Quiz am Geraet (Stand)",
    "gruppen_antworten.jsonl": "Quiz am Geraet (Protokoll)",
    "quiz_fortschritt.json": "Quiz am Geraet (Fortschritt)",
    "geschichten.jsonl": "App am Geraet (eigene Geschichten)",
    "anlass_umbenennung.jsonl": "App am Geraet (eigene Anlassnamen)",
    "gesichter_katalog.json": "Geraetespeicher (alter Gesichtskatalog, Notnagel)",
    "memory_store.json": "Geraetespeicher (Wissensspeicher/chroma)",
    "klassifikation_lernfaelle.json": "Geraetespeicher (Lernfaelle)",
    "auftraege.json": "Postfach/Steuerung am Geraet",
    "auftraege.jsonl": "Postfach am Geraet (hermes_inbox)",
    "antworten.jsonl": "Postfach am Geraet (hermes_inbox)",
    "status.jsonl": "Postfach am Geraet (Selbsttest)",
    "conversations.json": "Verlauf am Geraet",
    "letzte_nachricht.json": "Zustand am Geraet",
    "ueberlauf.jsonl": "Diagnose des Geraets (Layout-Waechter)",
}
# Der RUECKWEG Handy -> PC: die Dateien, die die APP AM GERAET erzeugt
# (``geschichten.jsonl`` = eigene Erzaehlungen, ``anlass_umbenennung.jsonl`` =
# eigene Anlassnamen), liegen im Termux-Heimordner — der ist ueber das Kabel
# NICHT lesbar (gemessen 12.10.: „Permission denied\", ``find`` ueber /sdcard
# Tiefe 4: 0 Treffer). Das Geraet KOPIERT sie deshalb mit
# ``termux/rueckweg-bereitstellen.sh`` in den freigegebenen Ordner
# ``/sdcard/Download/hermes_rueckweg``, der PC holt sie mit
# ``tools/handy/rueckweg_holen.py`` ab und bucht je Datei eine Manifest-Zeile
# (Name, Bytes, sha256, Zeit, ``richtung: handy->pc\"; Standard
# ``~/foto_sortierung/rueckweg_manifest.jsonl``, nie im Repo). Ohne diesen Weg
# konnte der Nachweis die beiden Stufen („Eigene Geschichten\"/„Eigene Titel\")
# NIE gegen das Geraet stellen — sie waren die einzigen, die nur in eine
# Richtung nachpruefbar waren. Hier wird nachgezaehlt, ob die gebuchte Fassung
# unversehrt am PC liegt. Nur Zahlen, Dateinamen und Zustand — NIE ein
# Geschichtentext, NIE ein eigener Titel.
STANDARD_RUECKWEG_MANIFEST = "rueckweg_manifest.jsonl"
# Die Dateien, die den Rueckweg nehmen duerfen — WORTGLEICH zu ``ERLAUBTE_NAMEN``
# in ``tools/handy/rueckweg_holen.py`` und ``RUECKWEG_NAMEN`` in
# ``termux/rueckweg-bereitstellen.sh``. Der Test
# ``test_rueckweg_liste_spiegelt_das_holwerkzeug`` liest die Konstante per AST
# aus dem Hol-Werkzeug und haelt beide Mengen zusammen — sonst meldete die
# Pruefzeile Buchungen als „ausserhalb der Liste\", die laengst dazugehoeren.
STANDARD_RUECKWEG_NAMEN = ("geschichten.jsonl", "anlass_umbenennung.jsonl",
                           "personen_bestaetigt.json", "personen_vorgaben.json")
# Suffix der Sicherung, die das Hol-Werkzeug vor dem Ersetzen einer vorhandenen
# Zieldatei beiseitelegt (``<name>.vorher``) — liegt sie da, wurde eine aeltere
# Fassung ersetzt und der Rueckweg ist offen.
RUECKWEG_VORHER_SUFFIX = ".vorher"
# Das Manifest der SCHREIBENDEN Operationen auf dem fremden System pCloud
# (``tools/pcloud/pcloud_bewegungen.py`` und die Entpack-/Loesch-Werkzeuge
# buchen hierher; Standard ``~/foto_sortierung/manifest.jsonl``, nie im Repo).
# AGENTS.md verlangt: „Jede schreibende Operation auf einem fremden System
# kommt in ein Manifest […], damit sie zurueckgenommen werden kann. ‚Wie mache
# ich das rueckgaengig?‘ wird VOR der Operation beantwortet." Genau diese eine
# Antwort auf die Rueckhol-Frage stand in KEINER Pruefzeile — obwohl in dieser
# Nacht 32 Archive auf pCloud entpackt und 33 Ordner angelegt wurden (79
# Buchungen). Nur Zahlen und die ARTEN (technische Namen der Operation), kein
# Datei-/Ordnername, kein Pfad, kein Inhalt.
STANDARD_BEWEGUNGEN = "manifest.jsonl"
# Die Arten, die das Rueckroll-Werkzeug kennt (``pcloud_rueckrollen.py``,
# ``AKTIONS_ARTEN``). Der Test
# ``test_bewegungen_arten_spiegeln_das_rueckrollwerkzeug`` liest die Konstante
# per AST aus dem Werkzeug und haelt beide zusammen — sonst driften sie still
# auseinander und die Pruefzeile wuerde eine falsche Rueckholbarkeit melden.
BEWEGUNG_AKTIONS_ARTEN = ("movefile", "movefolder", "createfolder")
# Davon wirklich ZURUECKFAHRBAR: das Werkzeug faehrt nur Verschiebungen zurueck.
# Angelegte Ordner werden ausdruecklich NICHT entfernt (Docstring des
# Werkzeugs: „Angelegte Ordner werden NICHT entfernt — dafuer gibt es hier
# keinen Weg, auch nicht als Schalter").
BEWEGUNG_ZURUECKFAHRBAR = ("movefile", "movefolder")
# Die Buchung einer selbst durchgefuehrten Rueckrollung (kein eigener Vorgang,
# sondern der Beleg, dass zurueckgefahren wurde).
BEWEGUNG_ART_RUECKROLL = "rueckroll"
# Das Chat-/WhatsApp-Archiv (Schwesterordner des Projekts): die Stufe, aus der
# JEDE Archiv-Antwort im Chat ihre Fundstellen zieht (Suchdienst
# ``archiv_suche``, seit dem 10.10. der Standardweg; der alte Weg
# ``archiv_service`` liest ``db/memory.db``). Es besteht aus den Rohdaten
# ``normalized/messages.jsonl``, der Textschicht ``db/memory.db`` und dem vollen
# Index ``db/archiv_index.db`` (Nachrichten, Chunks, Vektoren, Volltextindex) —
# und KEINE dieser Dateien stand in einer Pruefzeile, obwohl genau an dieser
# Stufe am 10.10. ein echter Fehler auffiel (der Chat suchte in einer alten
# Kopie, Journal 3 des Plans). Faellt der Index weg oder ist er halb, findet der
# Chat nichts mehr aus WhatsApp, und es merkt heute niemand (dieselbe Luecke wie
# bei OSM, Bildindex, Anlaessen, Ortsnamen, Erzaehl-Quellen, Beziehungen,
# Personen, App-Uebersicht, Doppelten, eigenen Erzaehl-Stufen und der Uebergabe).
# Nur Zahlen — kein Nachrichtentext, kein Titel, kein Gespraechsname.
STANDARD_ARCHIV_ORDNER = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..",
    "Chats von GPT, GEMINI, Claude"))
ARCHIV_MESSAGES = os.path.join("normalized", "messages.jsonl")
ARCHIV_INDEX_DB = os.path.join("db", "archiv_index.db")
ARCHIV_MEMORY_DB = os.path.join("db", "memory.db")
ARCHIV_VEKTORDATEI = os.path.join("db", "memory.vektoren.f32")
# Vor 1990 kann keine Chat-Nachricht entstanden sein; was aelter ist, kommt aus
# Kalendereintraegen (Geburtstage) und ist ein Datum, keine Nachricht.
ARCHIV_FRUEHESTES_JAHR = "1990"
# Je Gebiet ein Unterordner mit osm_orte.csv + osm_adressen.csv.
KARTEN_CSV_ORDNER = os.path.join("osm", "csv")
KARTEN_ORTE = "osm_orte.csv"
KARTEN_ADRESSEN = "osm_adressen.csv"
GRUPPEN_ORDNER = "personen_gruppen"
VIDEO_ENDUNGEN = (".mp4", ".mov", ".3gp", ".mkv", ".avi", ".m4v")
FERTIG_ENDUNG = ".videos_fertig"


# ── Lesen (nur lesend, nie ein Wurf bei kaputten Zeilen) ─────────────────────

def _kennung(wert: Any) -> str:
    if isinstance(wert, bool) or wert is None:
        return ""
    return str(wert).strip()


def _ganze_zahl(wert: Any) -> int:
    """Wert als ganze Zahl — sonst 0 (nichts geraten, nie ein Wurf)."""
    if isinstance(wert, bool):
        return 0
    try:
        return int(wert)
    except (TypeError, ValueError):
        return 0


def plan_lesen(pfad: str) -> Dict[str, Any]:
    """-> {"fotos": set, "videos": set, "ohne_name": int, "eintraege": int} oder fehlt."""
    if not os.path.isfile(pfad):
        return {"fehlt": True}
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except (OSError, ValueError) as problem:
        return {"fehlt": True, "fehler": problem.__class__.__name__}
    zuege = daten.get("zuege") if isinstance(daten, dict) else daten
    fotos: Set[str] = set()
    videos: Set[str] = set()
    eintraege = 0
    for zug in zuege if isinstance(zuege, list) else []:
        if not isinstance(zug, dict):
            continue
        k = _kennung(zug.get("fileid"))
        if not k:
            continue
        eintraege += 1
        name = zug.get("von_name") or zug.get("name") or ""
        if isinstance(name, str) and name.strip().lower().endswith(VIDEO_ENDUNGEN):
            videos.add(k)
        else:
            fotos.add(k)
    return {"fotos": fotos, "videos": videos, "eintraege": eintraege}


def _jsonl(pfad: str) -> Iterable[Optional[dict]]:
    with open(pfad, encoding="utf-8", errors="replace") as datei:
        for zeile in datei:
            if not zeile.strip():
                continue
            try:
                obj = json.loads(zeile)
            except ValueError:
                yield None
                continue
            yield obj if isinstance(obj, dict) else None


def masse_da(zeile: dict) -> bool:
    """Traegt die Vektorzeile echte Bildmasse?

    0 oder fehlend heisst: das Bild war beim Lauf nicht ladbar (keine Vorschau
    in pCloud, defekte Datei). Genau diese Zeilen erklaeren einen Teil der
    fehlenden Beschreibungen — deshalb wird das je Bild festgehalten.
    """
    def zahl(wert: Any) -> int:
        try:
            return int(wert or 0)
        except (TypeError, ValueError):
            return 0
    return zahl(zeile.get("breite")) > 0 and zahl(zeile.get("hoehe")) > 0


def foto_vektoren_lesen(pfad: str) -> Dict[str, Any]:
    """Foto-Vektorzeilen zaehlen: Bilder, Fehler, Bilder mit Gesicht, Gesichter."""
    if not os.path.isfile(pfad):
        return {"fehlt": True}
    bilder: Set[str] = set()
    mit_gesicht: Set[str] = set()
    mit_fehler: Set[str] = set()
    mit_massen: Set[str] = set()
    gesichter = kaputt = doppelt = video_zeilen = 0
    for z in _jsonl(pfad):
        if z is None:
            kaputt += 1
            continue
        k = _kennung(z.get("bild_id"))
        if not k:
            kaputt += 1
            continue
        if "#t=" in k:
            video_zeilen += 1
            continue
        if k in bilder:
            doppelt += 1
        bilder.add(k)
        g = z.get("gesichter") if isinstance(z.get("gesichter"), list) else []
        if z.get("fehler"):
            mit_fehler.add(k)
        if masse_da(z):
            mit_massen.add(k)
        if g:
            mit_gesicht.add(k)
            gesichter += len(g)
    return {"bilder": bilder, "mit_gesicht": mit_gesicht, "mit_fehler": mit_fehler,
            "mit_massen": mit_massen, "gesichter": gesichter, "kaputt": kaputt,
            "doppelt": doppelt, "video_zeilen": video_zeilen}


def video_vektoren_lesen(pfad: str) -> Dict[str, Any]:
    """Fertige Videos: Fortschrittsdatei + Video-ids aus den Standbild-Zeilen."""
    fertig: Set[str] = set()
    mit_zeilen: Set[str] = set()
    gesichter = 0
    vorhanden = False
    if os.path.isfile(pfad + FERTIG_ENDUNG):
        vorhanden = True
        with open(pfad + FERTIG_ENDUNG, encoding="utf-8", errors="replace") as datei:
            fertig.update(_kennung(z) for z in datei if _kennung(z))
    if os.path.isfile(pfad):
        vorhanden = True
        for z in _jsonl(pfad):
            if z is None:
                continue
            k = _kennung(z.get("bild_id"))
            if "#t=" in k:
                mit_zeilen.add(k.split("#t=", 1)[0])
                g = z.get("gesichter")
                gesichter += len(g) if isinstance(g, list) else 0
    if not vorhanden:
        return {"fehlt": True}
    return {"fertig": fertig | mit_zeilen, "mit_gesicht": mit_zeilen, "gesichter": gesichter}


def beschreibungen_lesen(pfad: str) -> Dict[str, Any]:
    if not os.path.isfile(pfad):
        return {"fehlt": True}
    kennungen: Set[str] = set()
    zeilen = kaputt = leer = 0
    kosten = 0.0
    for z in _jsonl(pfad):
        if z is None:
            kaputt += 1
            continue
        zeilen += 1
        k = _kennung(z.get("fileid"))
        if not k:
            kaputt += 1
            continue
        if not str(z.get("beschreibung") or "").strip():
            leer += 1
            continue
        kennungen.add(k)
        try:
            kosten += float(z.get("kosten_usd") or 0)
        except (TypeError, ValueError):
            pass
    return {"kennungen": kennungen, "zeilen": zeilen, "kaputt": kaputt, "leer": leer,
            "kosten": kosten}


def gesamtplan_lesen(pfad: str) -> Dict[str, Any]:
    """Union-Plan lesen: Fotos, Videos, Eintraege ohne Namen, ohne Kennung.

    Der Gesamtplan mischt die Feldnamen der Quell-Plaene (``von_name``/
    ``von_ordner`` bei Sammlung und Sortierplan, ``name``/``ordner`` bei Papas
    Plan). Wer nur ``von_name`` liest, verliert Papas 6.336 Fotos still — genau
    der Fehler vom 10.10.2026 (Changelog union-plan-feldnamen). Hier wird
    deshalb wie im Beschreibungs-Werkzeug BEIDE Formen gelesen; Eintraege ohne
    Namen (z. B. Fotobuch-Scans) und ohne Kennung werden gezaehlt, nicht
    verschluckt.
    """
    if not os.path.isfile(pfad):
        return {"fehlt": True}
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except (OSError, ValueError) as problem:
        return {"fehlt": True, "fehler": problem.__class__.__name__}
    zuege = daten.get("zuege") if isinstance(daten, dict) else daten
    zuege = zuege if isinstance(zuege, list) else []
    fotos: Set[str] = set()
    videos: Set[str] = set()
    ohne_namen = ohne_kennung = 0
    namen: Dict[str, Set[str]] = {}
    namen_je_kennung: Dict[str, str] = {}
    for zug in zuege:
        if not isinstance(zug, dict):
            continue
        k = _kennung(zug.get("fileid"))
        if not k:
            ohne_kennung += 1
            continue
        name = zug.get("von_name") or zug.get("name") or ""
        if not (isinstance(name, str) and name.strip()):
            ohne_namen += 1
            continue
        namen.setdefault(name.strip().lower(), set()).add(k)
        namen_je_kennung[k] = name.strip().lower()
        (videos if name.strip().lower().endswith(VIDEO_ENDUNGEN) else fotos).add(k)
    # Kennungen, deren Dateiname im Plan mehrfach vorkommt = Dubletten-Kandidaten
    # (derselbe Name in zwei Ordnern, zwei verschiedene fileids). Nur die Zahl
    # bzw. die Kennungen werden gemeldet, nie der Name selbst.
    namen_doppelt: Set[str] = set()
    for kennungen in namen.values():
        if len(kennungen) > 1:
            namen_doppelt |= kennungen
    return {"eintraege": len(zuege), "fotos": fotos, "videos": videos,
            "ohne_namen": ohne_namen, "ohne_kennung": ohne_kennung,
            "namen_doppelt": namen_doppelt, "namen_je_kennung": namen_je_kennung}


def luecken_details(fehlende: Iterable[str], alle_bilder: Set[str], mit_massen: Set[str],
                    namen_doppelt: Optional[Set[str]] = None,
                    max_kennungen: int = 20) -> Tuple[List[str], Dict[str, int]]:
    """Fehlende Fotos mit Kennung und Grund benennen statt nur zu zaehlen.

    Gruende (mechanisch aus den vorhandenen Dateien abgeleitet, nichts geraten):
      * ``keine Vektorzeile``  — kein Gesichtslauf/keine Zeile fuer dieses Bild
      * ``ohne Bildmasse``     — Vektorzeile ohne Breite/Hoehe: das Bild war
                                 nicht ladbar (keine Vorschau, defekte Datei)
      * ``Bild geladen``       — Zeile mit Massen da, aber kein
                                 Beschreibungseintrag (offener Rest)
    Dazu der Hinweis ``Name mehrfach im Plan`` (Dublette), wenn derselbe
    Dateiname bei mehreren Kennungen steht — es wird nur die Kennung genannt,
    nie der Name selbst.

    -> (Zeilen, Zaehler je Grund)
    """
    namen_doppelt = namen_doppelt or set()
    liste = sorted(fehlende)
    zaehler = {"ohne_vektorzeile": 0, "ohne_masse": 0, "kein_eintrag": 0, "name_doppelt": 0}
    zeilen: List[str] = []
    for k in liste:
        if k not in alle_bilder:
            grund = "keine Vektorzeile (kein Gesichtslauf fuer dieses Bild)"
            zaehler["ohne_vektorzeile"] += 1
        elif k not in mit_massen:
            grund = "ohne Bildmasse (Bild nicht ladbar, keine Vorschau)"
            zaehler["ohne_masse"] += 1
        else:
            grund = "Bild geladen, kein Beschreibungseintrag"
            zaehler["kein_eintrag"] += 1
        if k in namen_doppelt:
            grund += "; Name mehrfach im Plan (Dublette)"
            zaehler["name_doppelt"] += 1
        if max_kennungen and len(zeilen) < max_kennungen:
            zeilen.append(f"    {k}: {grund}")
    if max_kennungen and len(liste) > max_kennungen:
        zeilen.append(f"    ... und {_z(len(liste) - max_kennungen)} weitere")
    return zeilen, zaehler


def _grund_zeile(zaehler: Dict[str, int]) -> str:
    return ("Ursachen: " + _z(zaehler["ohne_vektorzeile"]) + " ohne Vektorzeile, "
            + _z(zaehler["ohne_masse"]) + " ohne Bildmasse, "
            + _z(zaehler["kein_eintrag"]) + " ohne Beschreibungseintrag; "
            + _z(zaehler["name_doppelt"]) + " mit mehrfach vorkommendem Namen")


def bilder_zaehlen(fehlende: Iterable[str], namen_je_kennung: Optional[Dict[str, str]] = None,
                   beschrieben: Optional[Set[str]] = None,
                   inhaltsgleich: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
    """Kennungen in BILDER umrechnen: derselbe Dateiname = dasselbe Bild.

    Eine Kennung ist eine Datei, nicht ein Bild: dasselbe Bild kann unter zwei
    Kennungen im Plan stehen (zwei Ordner). Die Zahl „8 Fotos ohne Beschreibung"
    ist deshalb ohne diese Umrechnung zu hoch — und genau davor steht Sebastians
    Kostenentscheidung. Gemessen (12.10.2026): 8 Kennungen = 6 Bilder, weil zwei
    Namen je doppelt vorkommen.

    **Der Name ist ein Hinweis, kein Beleg.** Zwei Dateien mit demselben Namen
    koennen zwei verschiedene Fotos sein (Kameranamen wie ``IMG_20241117…``
    kommen mehrfach vor). Belastbar ist nur: gleiche Groesse UND gleiche
    Pruefsumme = derselbe Inhalt (``duplikate.json``, ``inhaltsgleich``). Deshalb
    trennt diese Funktion beides:
      * Name — ``bilder`` / ``doppelte_kennungen`` / ``anderswo_beschrieben``
        (wie bisher, unveraendert),
      * Inhalt — ``inhaltsgruppen`` / ``inhaltsgleich_kennungen`` /
        ``inhaltsgleich_beschrieben`` und, **nur wenn Pruefsummen vorliegen**,
        ``inhalte`` und ``bilder_ohne_text_belegt``.

    Gezaehlt werden (nur Zahlen, NIE ein Name):
      * ``kennungen`` — die uebergebenen Kennungen,
      * ``bilder`` — verschiedene Namen (+ 1 je Eintrag ohne Namen),
      * ``doppelte_kennungen`` — Kennungen, deren Name bei den Fehlenden mehrfach steht,
      * ``ohne_name`` — Eintraege ohne Namen im Plan (Fotobuch-Scans),
      * ``anderswo_beschrieben`` — Fehlende, deren Name unter einer ANDEREN
        Kennung schon einen Beschreibungstext hat (nur ein NAME-Treffer: ob es
        dasselbe Bild ist, sagt der Name nicht),
      * ``bilder_ohne_text`` — verschiedene Namen ohne irgendwo vorhandenen Text
        (Name-Sicht, unveraendert),
      * ``inhaltsgruppen`` — Zahl der Gruppen gleichen Inhalts unter den Fehlenden,
      * ``inhaltsgleich_kennungen`` — Fehlende mit einer inhaltsgleichen anderen Kennung,
      * ``inhaltsgleich_beschrieben`` — Fehlende, deren Inhalt schon einen Text hat
        (eine Beschreibung deckt beide Kopien ab),
      * ``inhalte`` / ``bilder_ohne_text_belegt`` — verschiedene INHALTE unter den
        Fehlenden und davon ohne Text; ``None`` ohne Pruefsummen-Daten (nichts geraten).

    Ohne ``namen_je_kennung`` (aeltere Aufrufer, abgeschaltete Pruefung) bleibt
    alles 0 — es wird nichts geraten.
    """
    namen_je_kennung = namen_je_kennung or {}
    beschrieben = beschrieben or set()
    inhaltsgleich = inhaltsgleich or {}
    liste = list(fehlende)
    namen_beschrieben = {namen_je_kennung[k] for k in beschrieben if k in namen_je_kennung}
    je_name: Dict[str, int] = {}
    ohne_name = anderswo = 0
    for k in liste:
        name = namen_je_kennung.get(k)
        if not name:
            ohne_name += 1
            continue
        je_name[name] = je_name.get(name, 0) + 1
        if name in namen_beschrieben:
            anderswo += 1
    doppelt = sum(n - 1 for n in je_name.values() if n > 1)
    ohne_text = len([n for n in je_name if n not in namen_beschrieben])
    ergebnis: Dict[str, Any] = {"kennungen": len(liste), "bilder": len(je_name) + ohne_name,
                                "doppelte_kennungen": doppelt, "ohne_name": ohne_name,
                                "anderswo_beschrieben": anderswo,
                                "bilder_ohne_text": ohne_text + ohne_name,
                                "inhaltsgruppen": 0, "inhaltsgleich_kennungen": 0,
                                "inhaltsgleich_beschrieben": 0,
                                "inhalte": None, "bilder_ohne_text_belegt": None}
    if not inhaltsgleich:
        return ergebnis
    # Verbund ueber die Pruefsummen-Partner bilden: je Gruppe gleichen Inhalts
    # eine Wurzel. Nur Kennungen, nie ein Name.
    eltern: Dict[str, str] = {}

    def wurzel(kennung: str) -> str:
        while eltern.get(kennung, kennung) != kennung:
            kennung = eltern[kennung]
        return kennung

    def vereine(a: str, b: str) -> None:
        ra, rb = wurzel(a), wurzel(b)
        if ra != rb:
            eltern[max(ra, rb)] = min(ra, rb)

    for k in liste:
        for partner in (inhaltsgleich.get(k) or ()):
            vereine(k, partner)
    ergebnis["inhaltsgleich_kennungen"] = len([k for k in liste if inhaltsgleich.get(k)])
    # Inhalt-Klassen: alle Kennungen, die ueber Pruefsummen-Gleichheit
    # zusammenhaengen. Gezaehlt werden nur Klassen, in denen eine FEHLENDE
    # Kennung haengt; eine Klasse deckt sich mit einem Text, wenn irgendeine
    # ihrer Kennungen (auch eine nicht fehlende) schon beschrieben ist.
    klassen: Dict[str, Set[str]] = {}
    for k in liste:
        klassen.setdefault(wurzel(k), set()).add(k)
    inhalte = len(klassen)
    mit_text = len([k for k, g in klassen.items() if g & beschrieben])
    ergebnis["inhaltsgruppen"] = len([g for g in klassen.values() if len(g) > 1])
    ergebnis["inhaltsgleich_beschrieben"] = len(
        [k for k in liste if inhaltsgleich.get(k) and beschrieben & set(inhaltsgleich.get(k) or ())])
    ergebnis["inhalte"] = inhalte
    ergebnis["bilder_ohne_text_belegt"] = inhalte - mit_text
    return ergebnis


def endungen_zaehlen(kennungen: Iterable[str], namen_je_kennung: Optional[Dict[str, str]] = None,
                     max_endungen: int = 3) -> List[Tuple[str, int]]:
    """Datei-Endungen (Typ, kein Name) unter den genannten Kennungen zaehlen.

    Zweck: „Bild nicht ladbar" hat oft einen technischen Grund, den die Endung
    verraet — oder ausschliesst. Gemessen 12.10.2026: die drei Fotos ohne
    Bildmasse sind alle ``.jpg``; das Format ist damit NICHT die Ursache (es
    sind die Dateien selbst), und das steht so im Bericht, statt eine Vermutung
    zu wiederholen. Die Endung ist eine Formatangabe, kein Name — der Dateiname
    selbst bleibt draussen.
    """
    namen_je_kennung = namen_je_kennung or {}
    zaehler: Dict[str, int] = {}
    for k in kennungen:
        name = namen_je_kennung.get(k, "")
        endung = os.path.splitext(name)[1].lower() if name else ""
        endung = endung if endung else "(ohne Endung)"
        zaehler[endung] = zaehler.get(endung, 0) + 1
    geordnet = sorted(zaehler.items(), key=lambda p: (-p[1], p[0]))
    return geordnet[:max_endungen] if max_endungen else geordnet


def abdeckung(groessen: List[int], anteile=(0.5, 0.8, 0.9)) -> Dict[float, int]:
    """Wie viele der groessten Gruppen braucht es fuer 50/80/90 % aller Gesichter?"""
    sortiert = sorted((g for g in groessen if g > 0), reverse=True)
    gesamt = sum(sortiert)
    ergebnis: Dict[float, int] = {}
    if not gesamt:
        return {a: 0 for a in anteile}
    summe = 0
    offen = list(anteile)
    for i, g in enumerate(sortiert, 1):
        summe += g
        while offen and summe >= offen[0] * gesamt:
            ergebnis[offen.pop(0)] = i
    return ergebnis


def gruppen_lesen(basis: str) -> Dict[str, Any]:
    ordner = os.path.join(basis, GRUPPEN_ORDNER)
    beispiele = os.path.join(ordner, "personen_beispiele.json")
    zuordnung = os.path.join(ordner, "gesicht_zuordnung.jsonl")
    if not os.path.isfile(beispiele):
        return {"fehlt": True}
    try:
        with open(beispiele, encoding="utf-8") as datei:
            daten = json.load(datei)
    except (OSError, ValueError) as problem:
        return {"fehlt": True, "fehler": problem.__class__.__name__}
    gruppen = [g for g in (daten.get("gruppen") or []) if isinstance(g, dict)]
    groessen = [int(g.get("groesse") or 0) for g in gruppen]
    erg: Dict[str, Any] = {
        "stand": str(daten.get("stand") or "?"), "gruppen": len(gruppen),
        "gesichter_in_gruppen": sum(groessen), "abdeckung": abdeckung(groessen),
        "ab_50": sum(1 for g in groessen if g >= 50), "ab_10": sum(1 for g in groessen if g >= 10),
        "unter_10": sum(1 for g in groessen if g < 10),
        "mit_zwilling": sum(1 for g in gruppen if g.get("zwilling_kandidaten")),
        "benannt": sum(1 for g in gruppen if g.get("name")),
    }
    if os.path.isfile(zuordnung):
        zeilen = mit = 0
        for z in _jsonl(zuordnung):
            if z is None:
                continue
            zeilen += 1
            mit += 1 if z.get("kennung") else 0
        erg.update(zuordnung_zeilen=zeilen, zuordnung_mit_gruppe=mit)
    return erg


# ── Orte (OpenStreetMap) ────────────────────────────────────────────────────

def orte_lesen(pfad: str) -> Dict[str, Any]:
    """``bild_orte.csv`` zaehlen — eine Zeile je Bild, nur Zahlen.

    Der Zuordner schreibt je Bild eine Zeile. Ohne GPS steht dort ehrlich
    ``ohne GPS`` (Bild bleibt drin, statt weggelassen); Bilder aus dem Flugzeug
    tragen die Art ``flug``. Gezaehlt werden nur Zahlen — keine Ortsnamen,
    keine Strassen, keine Koordinaten.
    """
    if not os.path.isfile(pfad):
        return {"fehlt": True}
    zeilen = mit_gps = ohne_gps = flug = 0
    mit_ort = mit_landmarke = mit_strasse = mit_hausnummer = 0
    kaputt = 0
    try:
        with open(pfad, encoding="utf-8-sig", newline="") as datei:
            for satz in csv.DictReader(datei):
                if not isinstance(satz, dict):
                    kaputt += 1
                    continue
                zeilen += 1
                art = (satz.get("landmarke_art") or "").strip().lower()
                hinweis = (satz.get("hinweise") or "").strip().lower()
                if art == "flug":
                    flug += 1
                elif hinweis == "ohne gps":
                    ohne_gps += 1
                else:
                    mit_gps += 1
                if (satz.get("ort_osm") or "").strip():
                    mit_ort += 1
                if (satz.get("landmarke") or "").strip():
                    mit_landmarke += 1
                if (satz.get("adresse") or "").strip():
                    mit_strasse += 1
                if (satz.get("hausnummer") or "").strip():
                    mit_hausnummer += 1
    except (OSError, csv.Error, UnicodeDecodeError) as problem:
        return {"fehlt": True, "fehler": problem.__class__.__name__}
    return {"zeilen": zeilen, "mit_gps": mit_gps, "ohne_gps": ohne_gps,
            "flug": flug, "mit_ort": mit_ort, "mit_landmarke": mit_landmarke,
            "mit_strasse": mit_strasse, "mit_hausnummer": mit_hausnummer,
            "kaputt": kaputt}


def karten_gebiete(ordner: str) -> int:
    """Wie viele Kartengebiete haben beide Tabellen (Orte UND Adressen)?

    Je Gebiet ein Unterordner ``osm/csv/<name>``. Ein Gebiet zaehlt nur, wenn
    BEIDE Tabellen da sind — eine halbe Auswertung ist keine fertige.
    """
    if not os.path.isdir(ordner):
        return 0
    anzahl = 0
    for eintrag in sorted(os.listdir(ordner)):
        pfad = os.path.join(ordner, eintrag)
        if (os.path.isdir(pfad) and os.path.isfile(os.path.join(pfad, KARTEN_ORTE))
                and os.path.isfile(os.path.join(pfad, KARTEN_ADRESSEN))):
            anzahl += 1
    return anzahl


def tabellen_zeilen(pfad: str) -> int:
    """Datenzeilen einer Gesamttabelle (ohne Kopfzeile); 0 wenn sie fehlt."""
    if not os.path.isfile(pfad):
        return 0
    anzahl = 0
    with open(pfad, encoding="utf-8-sig", errors="replace") as datei:
        for _ in datei:
            anzahl += 1
    return max(0, anzahl - 1)


# ── Ortsnamen (GeoNames) ────────────────────────────────────────────────────

def ortsnamen_lesen(pfad: str) -> Dict[str, Any]:
    """``orte.jsonl`` zaehlen — nur Zahlen, keine Ortsnamen, keine Koordinaten.

    Je Bild eine Zeile aus den offline GeoNames-Daten (Ketten-Schritt 3b,
    ``orte_zuordnen.py``): Land, Region, naechster Ort, Aufnahmedatum. Der
    Zuordner haengt an und ueberspringt vorhandene ``bild_id`` — deshalb wird
    hier auch auf Dubletten geprueft (mehr Zeilen als Kennungen = der idempotente
    Lauf wurde umgangen). Gezaehlt werden nur Zahlen sowie die ANZAHL
    verschiedener Laender/Regionen/Orte und Aufnahmetage — nie ein Name.
    """
    e: Dict[str, Any] = {"fehlt": True, "zeilen": 0, "kaputt": 0, "kennungen": set(),
                         "doppelt": 0, "mit_datum": 0, "tage": 0, "laender": 0,
                         "regionen": 0, "orte": 0, "ohne_ort": 0}
    if not os.path.isfile(pfad):
        return e
    e["fehlt"] = False
    gesehen: Set[str] = set()
    laender: Set[str] = set()
    regionen: Set[str] = set()
    orte: Set[str] = set()
    tage: Set[str] = set()
    for zeile in _jsonl(pfad):
        if not isinstance(zeile, dict):
            e["kaputt"] += 1
            continue
        e["zeilen"] += 1
        k = _kennung(zeile.get("bild_id"))
        if k:
            if k in gesehen:
                e["doppelt"] += 1
            gesehen.add(k)
            e["kennungen"].add(k)
        for feld, sammlung in (("land", laender), ("region", regionen), ("ort", orte)):
            wert = str(zeile.get(feld) or "").strip()
            if wert:
                sammlung.add(wert)
        if not str(zeile.get("ort") or "").strip():
            e["ohne_ort"] += 1
        aufnahme = str(zeile.get("aufnahme") or "").strip()
        if aufnahme:
            e["mit_datum"] += 1
            tage.add(aufnahme[:10])
    e.update(laender=len(laender), regionen=len(regionen), orte=len(orte),
             tage=len(tage))
    return e


# ── Anlaesse (Ereignis-Datei) ───────────────────────────────────────────────

def anlaesse_lesen(pfad: str) -> Dict[str, Any]:
    """Anlaesse zaehlen — nur Zahlen und Quellen-Schluessel, nie Titel/Themen.

    Felder: ``fehlt``, ``anlaesse``, ``kaputt``, ``ohne_kennung``, ``kennungen``
    (Datei-Kennungen als Text), ``videos``, ``mit_datum``, ``datum_quellen``
    (Zaehler der Schluessel aus ``quellen.datum``, z. B. ``exif``/``dateiname``)
    sowie ``jahr_min``/``jahr_max``. Kaputte Zeilen zaehlen, statt zu werfen.

    ``ohne_kennung`` zaehlt Zeilen ohne brauchbare ``kennung``: der Erzaehl-Dienst
    (``erzaehl_service._datei_ereignisse_laden``) verwirft solche Zeilen still —
    ein Anlass ohne Kennung verschwindet damit aus den Geschichten, ohne dass es
    auffiele. Dieselbe Datei bedient drei Quellen, deshalb steht die Pruefung hier.
    """
    e: Dict[str, Any] = {"fehlt": True, "anlaesse": 0, "kaputt": 0, "ohne_kennung": 0,
                         "kennungen": set(), "videos": 0, "mit_datum": 0,
                         "datum_quellen": {}, "jahr_min": None, "jahr_max": None}
    if not os.path.isfile(pfad):
        return e
    e["fehlt"] = False
    for zeile in _jsonl(pfad):
        if not isinstance(zeile, dict):
            e["kaputt"] += 1
            continue
        e["anlaesse"] += 1
        if not _kennung(zeile.get("kennung")):
            e["ohne_kennung"] += 1
        for roh in zeile.get("datei_kennungen") or []:
            k = _kennung(roh)
            if k:
                e["kennungen"].add(k)
        try:
            e["videos"] += int(zeile.get("videos") or 0)
        except (TypeError, ValueError):
            pass
        if zeile.get("datum"):
            e["mit_datum"] += 1
        quellen = (zeile.get("quellen") or {}).get("datum")
        if isinstance(quellen, dict):
            schluessel = list(quellen)
        elif isinstance(quellen, str) and quellen.strip():
            # Die Sammlungs-Anlaesse nennen die Quelle als TEXT
            # ("sortierplan.json:anlaesse") statt als Zaehler-Dict. Ohne diesen
            # Zweig stuende dort "keine Quellenangabe", obwohl die Quelle dasteht.
            schluessel = [quellen.split(":")[0].strip()]
        else:
            schluessel = []
        for name in schluessel:
            if name:
                e["datum_quellen"][name] = e["datum_quellen"].get(name, 0) + 1
        jahr_wert = zeile.get("jahr")
        try:
            jahr = int(jahr_wert) if jahr_wert is not None else 0
        except (TypeError, ValueError):
            jahr = 0
        if jahr:
            e["jahr_min"] = jahr if e["jahr_min"] is None else min(e["jahr_min"], jahr)
            e["jahr_max"] = jahr if e["jahr_max"] is None else max(e["jahr_max"], jahr)
    return e


# ── Beziehungen („wer war mit wem wo") ──────────────────────────────────────

def beziehungen_lesen(pfad: str) -> Dict[str, Any]:
    """``beziehungen.jsonl`` zaehlen — nur Zahlen, NIE einen Personennamen.

    Felder: ``fehlt``, ``zeilen``, ``kaputt``, ``anlaesse`` (verschiedene
    ``anlass_id``), ``ereignis_kennungen`` (verschiedene ``ereignis_kennung``),
    ``tage`` (verschiedene ``datum``), ``unterarten`` (Zaehler),
    ``personen_eintraege``, ``personen_bestaetigt``, ``personen_mit_kennung``,
    ``kategorien`` (Anzahl), ``mit_datum``, ``jahr_min``/``jahr_max``.

    Die Datei traegt Namen (``personen[].name``, ``beleg.chat_name``), Themen
    und Zielordner — NICHTS davon wird gelesen oder ausgegeben, nur gezaehlt.
    Eine kaputte Zeile zaehlt, statt zu werfen. ``personen_mit_kennung`` zaehlt
    Eintraege mit brauchbarer ``kennung``: ohne Kennung ist eine Aussage nicht
    an ein Gesicht gebunden.
    """
    e: Dict[str, Any] = {"fehlt": True, "zeilen": 0, "kaputt": 0, "anlaesse": set(),
                         "ereignis_kennungen": set(), "tage": set(), "unterarten": {},
                         "personen_eintraege": 0, "personen_bestaetigt": 0,
                         "personen_mit_kennung": 0, "kategorien": set(),
                         "mit_datum": 0, "jahr_min": None, "jahr_max": None}
    if not os.path.isfile(pfad):
        return e
    e["fehlt"] = False
    for zeile in _jsonl(pfad):
        if not isinstance(zeile, dict):
            e["kaputt"] += 1
            continue
        e["zeilen"] += 1
        anlass = _kennung(zeile.get("anlass_id"))
        if anlass:
            e["anlaesse"].add(anlass)
        ereignis = _kennung(zeile.get("ereignis_kennung"))
        if ereignis:
            e["ereignis_kennungen"].add(ereignis)
        datum = _kennung(zeile.get("datum"))
        if datum:
            e["mit_datum"] += 1
            e["tage"].add(datum)
            jahr = _ganze_zahl(datum[:4])
            if jahr:
                e["jahr_min"] = jahr if e["jahr_min"] is None else min(e["jahr_min"], jahr)
                e["jahr_max"] = jahr if e["jahr_max"] is None else max(e["jahr_max"], jahr)
        unterart = _kennung(zeile.get("unterart"))
        if unterart:
            e["unterarten"][unterart] = e["unterarten"].get(unterart, 0) + 1
        kategorie = _kennung(zeile.get("kategorie"))
        if kategorie:
            e["kategorien"].add(kategorie)
        personen = zeile.get("personen")
        if isinstance(personen, list):
            for person in personen:
                if not isinstance(person, dict):
                    continue
                e["personen_eintraege"] += 1
                if person.get("bestaetigt") is True:
                    e["personen_bestaetigt"] += 1
                if _kennung(person.get("kennung")):
                    e["personen_mit_kennung"] += 1
    return e


def beziehungen_uebersicht_lesen(pfad: str) -> Dict[str, Any]:
    """``beziehungen.json`` lesen — nur Kennzahlen, nie ein Wurf.

    Felder: ``fehlt``, ``kaputt`` (kein lesbares JSON), ``art``, ``anzahl``
    (Zaehler je Unterart), ``summe`` (Summe der Unterarten — die Zahl, die die
    Datei als „Aussagen" meint), ``kontakte``, ``personen_kennungen``,
    ``datum_von``/``datum_bis``, ``stand``. Die Uebersicht traegt keine Namen
    und keine Themen — gelesen werden nur Zahlen und Textfelder wie ``art``.
    """
    leer: Dict[str, Any] = {"fehlt": True, "kaputt": False, "art": None, "anzahl": {},
                            "summe": 0, "kontakte": 0, "personen_kennungen": 0,
                            "datum_von": None, "datum_bis": None, "stand": None}
    if not os.path.isfile(pfad):
        return leer
    daten: Any = None
    try:
        with open(pfad, "r", encoding="utf-8") as datei:
            daten = json.load(datei)
    except (OSError, ValueError):
        daten = None
    if not isinstance(daten, dict):
        return dict(leer, fehlt=False, kaputt=True)
    anzahl_roh = daten.get("anzahl")
    anzahl: Dict[str, int] = {}
    if isinstance(anzahl_roh, dict):
        for name, wert in anzahl_roh.items():
            anzahl[str(name)] = _ganze_zahl(wert)
    return {"fehlt": False, "kaputt": False, "art": _kennung(daten.get("art")) or None,
            "anzahl": anzahl, "summe": sum(anzahl.values()),
            "kontakte": _ganze_zahl(daten.get("anzahl_kontakte")),
            "personen_kennungen": _ganze_zahl(daten.get("anzahl_personen_kennungen")),
            "datum_von": _kennung(daten.get("datum_von")) or None,
            "datum_bis": _kennung(daten.get("datum_bis")) or None,
            "stand": _kennung(daten.get("stand")) or None}


# ── Personen (Quiz + Telefonbuch) ────────────────────────────────────────────

def _quiz_pfad(basis: str, name: str) -> Optional[str]:
    """Wie ``gruppen_quiz._lesepfad``: erst ``personen_gruppen/<name>`` (so
    schreibt der PC), dann ``<name>`` direkt im Ordner (so legt die Uebergabe am
    Handy sie ab). Ohne diesen zweiten Ort meldete der Nachweis Dateien als
    fehlend, die der Dienst sehr wohl liest."""
    for pfad in (os.path.join(basis, GRUPPEN_ORDNER, name), os.path.join(basis, name)):
        if os.path.isfile(pfad):
            return pfad
    return None


def _json_lesen(pfad: Optional[str]) -> Tuple[Any, bool]:
    """JSON lesen -> (Daten, kaputt). Fehlende Datei = (None, False), nie ein Wurf."""
    if not pfad:
        return None, False
    try:
        with open(pfad, "r", encoding="utf-8") as datei:
            return json.load(datei), False
    except (OSError, ValueError):
        return None, True


def personen_lesen(basis: str, namen_datei: str = STANDARD_PERSONEN) -> Dict[str, Any]:
    """Die Personen-Stufe zaehlen (Quiz + Telefonbuch) — nur Zahlen, NIE ein Name.

    Gelesen werden genau die Dateien, die ``gruppen_quiz`` fuer die Chat-Werkzeuge
    liest: ``personen_bestaetigt.json`` (Kennung -> Name), ``personen_vorgaben.json``
    (gleich/verschieden/ausgeschlossen), ``personen_profile.json``
    (Beziehung/Notizen/Kontakt), ``kontakte.json`` (Telefonbuch-Auszug),
    ``gruppen_quiz_stand.json`` (spaeter/unbekannt) und ``gruppen_antworten.jsonl``
    (Protokoll). Ausgegeben werden nur Zaehlungen — Personennamen, Telefonnummern
    und Geburtstage werden NICHT gelesen oder ausgegeben.

    Zwei ehrliche Pruefungen: ``kennungen_ohne_gruppe`` zaehlt bestaetigte
    Kennungen, zu denen es in ``personen_beispiele.json`` keine Gruppe gibt (ein
    Name ohne Gesichter), und ``personen`` zaehlt VERSCHIEDENE Namen (dieselbe
    Person an mehreren Kennungen ist eine Person).

    Die verwaisten Kennungen werden GENAU benannt statt nur gezaehlt: traegt
    derselbe Name an einer ANDEREN Kennung eine lebende Gruppe
    (``ohne_gruppe_doppelt`` — ein verwaister Eintrag, die Person ist nicht
    verloren), oder kommt der Name sonst nirgends vor (``ohne_gruppe_ins_leere``
    — der Name zeigt ins Leere). Ohne diese Trennung sieht ein harmloser
    Doppel-Eintrag wie eine verlorene Person aus.
    """
    e: Dict[str, Any] = {"fehlt": True, "kaputt": False, "kennungen": 0, "personen": 0,
                         "ohne_namen": 0, "kennungen_ohne_gruppe": 0,
                         "ohne_gruppe_doppelt": 0, "ohne_gruppe_ins_leere": 0,
                         "gleich": 0, "verschieden": 0, "ausgeschlossen": 0,
                         "profile": 0, "profile_mit_beziehung": 0, "profile_mit_notiz": 0,
                         "notizen": 0, "profile_mit_kontakt": 0,
                         "kontakte": 0, "kontakte_mit_geburtstag": 0,
                         "spaeter": 0, "unbekannt": 0, "protokoll_zeilen": 0,
                         "fehlende": []}
    pfad = _quiz_pfad(basis, namen_datei)
    if not pfad:
        e["fehlende"].append(namen_datei)
        return e
    daten, kaputt = _json_lesen(pfad)
    if kaputt or not isinstance(daten, dict):
        return dict(e, fehlt=False, kaputt=True, fehlende=[namen_datei])
    e["fehlt"] = False
    namen = daten.get("bestaetigt")
    if not isinstance(namen, dict):
        namen = {}
    personen = set()
    for kennung, name in namen.items():
        if not _kennung(kennung):
            continue
        e["kennungen"] += 1
        sauber = name.strip() if isinstance(name, str) else ""
        if sauber:
            personen.add(sauber.casefold())
        else:
            e["ohne_namen"] += 1
    e["personen"] = len(personen)

    # Kennungen ohne Gruppe: der Name haengt an keiner Gruppe (kein Gesicht).
    beispiele = _quiz_pfad(basis, "personen_beispiele.json")
    gruppen_kennungen: Set[str] = set()
    namen_mit_gruppe: Set[str] = set()
    if beispiele:
        bdaten, _ = _json_lesen(beispiele)
        for gruppe in (bdaten or {}).get("gruppen") or []:
            if not isinstance(gruppe, dict):
                continue
            if _kennung(gruppe.get("kennung")):
                gruppen_kennungen.add(_kennung(gruppe.get("kennung")))
            sauber = _kennung(gruppe.get("name"))
            if sauber:
                namen_mit_gruppe.add(sauber.casefold())
    if gruppen_kennungen:
        verwaist = [k for k in namen if _kennung(k) and _kennung(k) not in gruppen_kennungen]
        e["kennungen_ohne_gruppe"] = len(verwaist)
        # Genau benennen statt nur zaehlen: derselbe Name an einer ANDEREN
        # Kennung mit lebender Gruppe = verwaister (doppelter) Eintrag; sonst
        # zeigt der Name ins Leere. Eine Kennung ohne Namen zaehlt dabei zu
        # „ins Leere\" — an ihr haengt nirgends ein Gesicht.
        for kennung in verwaist:
            wert = namen.get(kennung)
            sauber = wert.strip().casefold() if isinstance(wert, str) else ""
            if sauber and sauber in namen_mit_gruppe:
                e["ohne_gruppe_doppelt"] += 1
            else:
                e["ohne_gruppe_ins_leere"] += 1

    vorgaben_pfad = _quiz_pfad(basis, PERSONEN_VORGABEN)
    if not vorgaben_pfad:
        e["fehlende"].append(PERSONEN_VORGABEN)
    else:
        vdaten, _ = _json_lesen(vorgaben_pfad)
        if isinstance(vdaten, dict):
            for feld, schluessel in (("gleich", "gleich"), ("verschieden", "verschieden"),
                                     ("ausgeschlossen", "ausgeschlossen")):
                wert = vdaten.get(schluessel)
                e[feld] = len(wert) if isinstance(wert, list) else 0
        else:
            e["fehlende"].append(PERSONEN_VORGABEN)

    profil_pfad = _quiz_pfad(basis, PERSONEN_PROFILE)
    if not profil_pfad:
        e["fehlende"].append(PERSONEN_PROFILE)
    else:
        pdaten, _ = _json_lesen(profil_pfad)
        profile = ((pdaten or {}).get("profile") if isinstance(pdaten, dict) else None) or {}
        if not isinstance(profile, dict):
            profile = {}
        for eintrag in profile.values():
            if not isinstance(eintrag, dict):
                continue
            e["profile"] += 1
            if _kennung(eintrag.get("beziehung")):
                e["profile_mit_beziehung"] += 1
            notizen = [n for n in (eintrag.get("notizen") or [])
                       if isinstance(n, dict) and not n.get("zurueckgenommen")]
            if notizen:
                e["profile_mit_notiz"] += 1
                e["notizen"] += len(notizen)
            if isinstance(eintrag.get("kontakt"), dict):
                e["profile_mit_kontakt"] += 1

    kontakte_pfad = _quiz_pfad(basis, PERSONEN_KONTAKTE)
    if not kontakte_pfad:
        e["fehlende"].append(PERSONEN_KONTAKTE)
    else:
        kdaten, _ = _json_lesen(kontakte_pfad)
        liste = kdaten.get("kontakte") if isinstance(kdaten, dict) else None
        for kontakt in liste if isinstance(liste, list) else []:
            if not isinstance(kontakt, dict):
                continue
            e["kontakte"] += 1
            if isinstance(kontakt.get("geburtstag"), str) and kontakt["geburtstag"].strip():
                e["kontakte_mit_geburtstag"] += 1
        if not isinstance(kdaten, dict):
            e["fehlende"].append(PERSONEN_KONTAKTE)

    stand_pfad = _quiz_pfad(basis, PERSONEN_STAND)
    if not stand_pfad:
        e["fehlende"].append(PERSONEN_STAND)
    else:
        sdaten, _ = _json_lesen(stand_pfad)
        if isinstance(sdaten, dict):
            for feld in ("spaeter", "unbekannt"):
                wert = sdaten.get(feld)
                e[feld] = len(wert) if isinstance(wert, list) else 0
        else:
            e["fehlende"].append(PERSONEN_STAND)

    protokoll_pfad = _quiz_pfad(basis, PERSONEN_PROTOKOLL)
    if not protokoll_pfad:
        e["fehlende"].append(PERSONEN_PROTOKOLL)
    else:
        for zeile in _jsonl(protokoll_pfad):
            if zeile is not None:
                e["protokoll_zeilen"] += 1
    return e


# ── Fotos-Uebersicht fuer die App (N11/N13a) ─────────────────────────────────

def _datei_json(pfad: str) -> Tuple[Optional[dict], str]:
    """JSON-Objekt lesen -> (Daten, Zustand). Zustand: ``"fehlt"``, ``"kaputt"``, ``""``.

    Fehlt die Datei, ist das kein Fehler; ist sie da, aber kein lesbares Objekt,
    meldet der Zustand ``"kaputt"``. Nie ein Wurf.
    """
    if not os.path.isfile(pfad):
        return None, "fehlt"
    try:
        with open(pfad, "r", encoding="utf-8") as datei:
            daten = json.load(datei)
    except (OSError, ValueError):
        return None, "kaputt"
    if not isinstance(daten, dict):
        return None, "kaputt"
    return daten, ""


def _zahlenblock(daten: dict) -> Dict[str, int]:
    """Den ``zahlen``-Block als {Schluessel: ganze Zahl} — nur echte Zahlen."""
    zahlen = daten.get("zahlen")
    if not isinstance(zahlen, dict):
        return {}
    return {str(k): _ganze_zahl(v) for k, v in zahlen.items()
            if isinstance(v, (int, float, str)) and not isinstance(v, bool)}


def app_uebersicht_lesen(pfad: str) -> Dict[str, Any]:
    """``fotos_uebersicht.json`` zaehlen (App-Uebersicht, N11) — nur Zahlen.

    Gezaehlt werden die Kennzahlen aus ``zahlen``, die Laengen der Listen
    ``jahre``/``kategorien``/``themen`` und die Event-Zeilen. Die Event-NAMEN,
    Kategorien-Namen und Themen werden NICHT gelesen oder ausgegeben — nur ihre
    Anzahl.
    """
    e: Dict[str, Any] = {"fehlt": True, "kaputt": False, "art": None, "version": None,
                         "stand": None, "zahlen": {}, "events": 0, "events_ohne_name": 0,
                         "jahre": 0, "kategorien": 0, "themen": 0}
    if not os.path.isfile(pfad):
        return e
    daten, zustand = _datei_json(pfad)
    if zustand == "kaputt" or daten is None:
        return dict(e, fehlt=False, kaputt=True)
    e["fehlt"] = False
    e["art"] = daten.get("art")
    e["version"] = daten.get("version")
    e["stand"] = _kennung(daten.get("stand")) or None
    e["zahlen"] = _zahlenblock(daten)
    for feld in ("jahre", "kategorien", "themen"):
        wert = daten.get(feld)
        e[feld] = len(wert) if isinstance(wert, list) else 0
    ev = daten.get("events")
    for eintrag in ev if isinstance(ev, list) else []:
        if not isinstance(eintrag, dict):
            continue
        e["events"] += 1
        if not _kennung(eintrag.get("name")):
            e["events_ohne_name"] += 1
    return e


def app_dateien_lesen(pfad: str) -> Dict[str, Any]:
    """``fotos_dateien.json`` zaehlen (Datei-Kennungen fuer die Vorschau, N13a).

    Gezaehlt werden Events, Datei-Eintraege und die Summe der ``anzahl``-Werte,
    dazu Events ohne Dateien und Dateien ohne Kennung. Die DateiNAMEN der Bilder
    werden NICHT gelesen oder ausgegeben — nur die Zahl der Kennungen.
    """
    e: Dict[str, Any] = {"fehlt": True, "kaputt": False, "art": None, "version": None,
                         "stand": None, "plan_stand": None, "zahlen": {},
                         "events": 0, "datei_eintraege": 0, "anzahl_summe": 0,
                         "events_ohne_event": 0, "events_ohne_dateien": 0,
                         "dateien_ohne_kennung": 0}
    if not os.path.isfile(pfad):
        return e
    daten, zustand = _datei_json(pfad)
    if zustand == "kaputt" or daten is None:
        return dict(e, fehlt=False, kaputt=True)
    e["fehlt"] = False
    e["art"] = daten.get("art")
    e["version"] = daten.get("version")
    e["stand"] = _kennung(daten.get("stand")) or None
    e["plan_stand"] = _kennung(daten.get("plan_stand")) or None
    e["zahlen"] = _zahlenblock(daten)
    ev = daten.get("events")
    for eintrag in ev if isinstance(ev, list) else []:
        if not isinstance(eintrag, dict):
            continue
        e["events"] += 1
        if not _kennung(eintrag.get("event")):
            e["events_ohne_event"] += 1
        dateien = eintrag.get("dateien")
        if not isinstance(dateien, list) or not dateien:
            e["events_ohne_dateien"] += 1
            continue
        e["datei_eintraege"] += len(dateien)
        for bild in dateien:
            if not isinstance(bild, dict) or not _kennung(bild.get("datei_id")):
                e["dateien_ohne_kennung"] += 1
        e["anzahl_summe"] += _ganze_zahl(eintrag.get("anzahl"))
    return e


# ── Doppelte (pCloud, Pruefsumme) ───────────────────────────────────────────

def _zahlen_baum(daten: Any) -> Dict[str, Any]:
    """Einen Zahlen-Teilbaum der Zusammenfassung lesen — nie ein Wurf.

    ``ueber_baeume`` und die zwei Teile unter ``innerhalb`` tragen dieselben vier
    Felder (``gruppen``, ``dateien``, ``mb_alle_kopien``, ``mb_freigabe_kandidaten``).
    """
    if not isinstance(daten, dict):
        return {}
    return {"gruppen": _ganze_zahl(daten.get("gruppen")),
            "dateien": _ganze_zahl(daten.get("dateien")),
            "mb_alle": _zahl_aus(daten.get("mb_alle_kopien")) or 0.0,
            "mb_frei": _zahl_aus(daten.get("mb_freigabe_kandidaten")) or 0.0}


def duplikate_lesen(pfad: str) -> Dict[str, Any]:
    """``duplikate.json`` zaehlen (Pruefsummen-Vergleich, ``pcloud_duplikate.py``).

    Gezaehlt werden die Summen (``zusammenfassung``), die zwei Baeume (Schluessel
    ``upload`` / ``sammlung`` — je Baum Dateien, gelesene Ordner, erreichte Tiefe,
    Vollstaendigkeit ``abgebrochen`` / ``offen_gelassen`` und die Zaehler
    ``ohne_hash`` / ``ohne_groesse`` / ``ohne_kennung`` / ``kaputte_eintraege``),
    die Duplikat-Gruppen (Anzahl, Mitglieder, Zahl je ``art``, Kandidaten je
    Gruppe) und die Kandidaten-Gesamtliste. Die Mitglieder-NAMEN, Pfade und
    Pruefsummen der Gruppen werden NICHT gelesen oder ausgegeben — nur ihre Zahl.

    Zusaetzlich (fuer die Umrechnung Kennung -> Bild): ``inhaltsgleich`` bildet
    je Kennung die Partner-Kennungen derselben Gruppe ab — gleiche Groesse UND
    gleiche Pruefsumme heisst **derselbe Inhalt**, das ist die einzige belastbare
    Gleichheit (der Dateiname ist es nicht). Nur Kennungen, nie ein Name.
    Nie ein Wurf: fehlt/kaputt werden ehrlich gemeldet.
    """
    e: Dict[str, Any] = {
        "fehlt": True, "kaputt": False, "stand": None, "trocken": None,
        "werkzeug": None, "tiefe_grenze": 0, "baeume": {}, "gruppen": 0,
        "arten": {}, "mitglieder": 0, "gruppen_anzahl": 0, "kandidaten_aus_gruppen": 0,
        "kandidaten_dateien": 0, "kandidaten_mb": 0.0, "kandidaten_liste": 0,
        "zahlen": {}, "mb": {}, "ueber_baeume": {}, "innerhalb": {},
        "inhaltsgleich": {}, "inhaltsgleich_kennungen": 0,
    }
    if not os.path.isfile(pfad):
        return e
    daten, zustand = _datei_json(pfad)
    if zustand == "kaputt" or daten is None:
        return dict(e, fehlt=False, kaputt=True)
    e["fehlt"] = False
    e["stand"] = _kennung(daten.get("stand")) or None
    e["trocken"] = daten.get("trocken") if isinstance(daten.get("trocken"), bool) else None
    e["werkzeug"] = _kennung(daten.get("werkzeug")) or None
    e["tiefe_grenze"] = _ganze_zahl(daten.get("tiefe_grenze"))
    baeume = daten.get("baeume")
    for name, baum in (baeume.items() if isinstance(baeume, dict) else []):
        if not isinstance(baum, dict):
            continue
        e["baeume"][str(name)] = {
            "gelesen": bool(baum.get("gelesen")),
            "dateien": _ganze_zahl(baum.get("dateien")),
            "ordner": _ganze_zahl(baum.get("ordner_gelesen")),
            "tiefe": _ganze_zahl(baum.get("tiefe_erreicht")),
            "abgebrochen": bool(baum.get("abgebrochen")),
            "offen": _ganze_zahl(baum.get("offen_gelassen")),
            "ohne_hash": _ganze_zahl(baum.get("ohne_hash")),
            "ohne_groesse": _ganze_zahl(baum.get("ohne_groesse")),
            "ohne_kennung": _ganze_zahl(baum.get("ohne_kennung")),
            "kaputt": _ganze_zahl(baum.get("kaputte_eintraege")),
        }
    gruppen = daten.get("gruppen")
    for gruppe in (gruppen if isinstance(gruppen, list) else []):
        if not isinstance(gruppe, dict):
            continue
        e["gruppen"] += 1
        e["gruppen_anzahl"] += _ganze_zahl(gruppe.get("anzahl"))
        if isinstance(gruppe.get("mitglieder"), list):
            e["mitglieder"] += len(gruppe["mitglieder"])
            # Gleiche Groesse UND gleiche Pruefsumme = derselbe Inhalt. Nur die
            # Kennungen werden verknuepft (nie Name, Pfad oder Pruefsumme).
            kennungen = [k for k in (_kennung(m.get("fileid"))
                                     for m in gruppe["mitglieder"] if isinstance(m, dict)) if k]
            for k in kennungen:
                e["inhaltsgleich"].setdefault(k, set()).update(x for x in kennungen if x != k)
        if isinstance(gruppe.get("loesch_kandidaten"), list):
            e["kandidaten_aus_gruppen"] += len(gruppe["loesch_kandidaten"])
        art = _kennung(gruppe.get("art")) or "ohne_art"
        e["arten"][art] = e["arten"].get(art, 0) + 1
    lk = daten.get("loesch_kandidaten")
    lk = lk if isinstance(lk, dict) else {}
    e["kandidaten_dateien"] = _ganze_zahl(lk.get("dateien"))
    e["kandidaten_mb"] = _zahl_aus(lk.get("mb")) or 0.0
    e["kandidaten_liste"] = len(lk["liste"]) if isinstance(lk.get("liste"), list) else 0
    zus = daten.get("zusammenfassung")
    zus = zus if isinstance(zus, dict) else {}
    for schluessel, wert in zus.items():
        if isinstance(wert, bool) or not isinstance(wert, (int, float)):
            continue
        if isinstance(wert, int):
            e["zahlen"][str(schluessel)] = wert
        else:
            e["mb"][str(schluessel)] = float(wert)
    e["ueber_baeume"] = _zahlen_baum(zus.get("ueber_baeume"))
    innerhalb = zus.get("innerhalb")
    e["innerhalb"] = {str(n): _zahlen_baum(b) for n, b in
                      (innerhalb.items() if isinstance(innerhalb, dict) else [])}
    e["inhaltsgleich"] = {k: tuple(sorted(v)) for k, v in e["inhaltsgleich"].items()}
    e["inhaltsgleich_kennungen"] = len(e["inhaltsgleich"])
    return e


# ── Erzaehl-Stufen, die Sebastian selbst fuellt (Schicht "mensch") ───────────

def anlass_kennungen_sammeln(basis: str,
                             dateien=(STANDARD_ANLAESSE,) + tuple(STANDARD_ERZAHL_QUELLEN)) -> Set[str]:
    """Alle Anlass-Kennungen der drei Erzaehl-Quellen — nur Kennungen, nie Titel.

    Die eigenen Geschichten und Titel zeigen mit ihrer Kennung auf einen Anlass
    (``ereignis_kennung`` bzw. ``kennung``). Verschwindet der Anlass (Neu-Lauf,
    andere Gruppierung), zeigt der eigene Text ins Leere — genau dagegen wird
    geprueft. Fehlende Quellen zaehlen nicht mit (kein stiller Fehlalarm).
    """
    kennungen: Set[str] = set()
    for name in dateien:
        pfad = os.path.join(basis, name)
        if not os.path.isfile(pfad):
            continue
        for zeile in _jsonl(pfad):
            if isinstance(zeile, dict) and _kennung(zeile.get("kennung")):
                kennungen.add(_kennung(zeile.get("kennung")))
    return kennungen


def geschichten_lesen(pfad: str, anlass_kennungen: Optional[Set[str]] = None) -> Dict[str, Any]:
    """``geschichten.jsonl`` zaehlen — nur Zahlen, NIE ein Text.

    Die Datei ist Sebastians eigene Schicht (``erzaehl_service``, Schicht
    "mensch"): je Zeile ``id``, ``ereignis_kennung``, optional ``datei_kennung``
    (Geschichte zu EINEM Bild), ``text``, ``quelle`` (tippen/sprache/import) und
    ``ersetzt`` (Verweis auf die abgeloeste Fassung). Sie wird **nur anhaengend**
    geschrieben — je ``id`` gilt die neueste Zeile, ersetzte Zeilen bleiben als
    Rueckweg stehen.

    Ehrlich statt still: eine Zeile ohne brauchbare ``id`` wird vom Dienst
    **verworfen** (die Geschichte waere unsichtbar), und ein ``ersetzt``-Verweis
    auf eine nicht vorhandene Kennung ist ein toter Verweis. Beides wird
    gezaehlt. Sind ``anlass_kennungen`` bekannt, werden die Geschichten gezaehlt,
    deren Anlass es nicht mehr gibt. Nie ein Wurf; fehlt die Datei, ist das
    ehrlich ``fehlt``.
    """
    e: Dict[str, Any] = {"fehlt": True, "zeilen": 0, "kaputt_zeilen": 0, "eintraege": 0,
                         "ohne_id": 0, "kennungen": set(), "alte_fassungen": 0,
                         "tote_verweise": 0, "ohne_ereignis": 0, "mit_bild": 0,
                         "ohne_text": 0, "quellen": {}, "schichten": {},
                         "ereignis_kennungen": set(), "ohne_anlass": set()}
    if not os.path.isfile(pfad):
        return e
    e["fehlt"] = False
    eintraege: List[dict] = []
    for zeile in _jsonl(pfad):
        if not isinstance(zeile, dict):
            e["kaputt_zeilen"] += 1
            continue
        e["zeilen"] += 1
        kennung = _kennung(zeile.get("id"))
        if not kennung:
            e["ohne_id"] += 1
            continue
        eintraege.append(zeile)
        e["kennungen"].add(kennung)
    e["eintraege"] = len(eintraege)
    ersetzte = {_kennung(z.get("ersetzt")) for z in eintraege if _kennung(z.get("ersetzt"))}
    e["alte_fassungen"] = len(ersetzte & e["kennungen"])
    e["tote_verweise"] = len(ersetzte - e["kennungen"])
    for z in eintraege:
        ereignis = _kennung(z.get("ereignis_kennung"))
        if ereignis:
            e["ereignis_kennungen"].add(ereignis)
        else:
            e["ohne_ereignis"] += 1
        if _kennung(z.get("datei_kennung")):
            e["mit_bild"] += 1
        if not str(z.get("text") or "").strip():
            e["ohne_text"] += 1
        quelle = _kennung(z.get("quelle")) or "ohne_quelle"
        e["quellen"][quelle] = e["quellen"].get(quelle, 0) + 1
        schicht = _kennung(z.get("schicht")) or "ohne_schicht"
        e["schichten"][schicht] = e["schichten"].get(schicht, 0) + 1
    if anlass_kennungen:
        e["ohne_anlass"] = e["ereignis_kennungen"] - anlass_kennungen
    return e


def eigene_titel_lesen(pfad: str, anlass_kennungen: Optional[Set[str]] = None) -> Dict[str, Any]:
    """``anlass_umbenennung.jsonl`` zaehlen — nur Zahlen, NIE ein Titel.

    Je Zeile ``kennung`` (Anlass) und ``name``; nur anhaengend, je Kennung gilt
    die neueste Zeile, und ein **leerer** Name setzt auf den automatischen Titel
    zurueck. Gezaehlt werden Zeilen, kaputte Zeilen, Kennungen, mehrfache Zeilen
    je Kennung (Fassungen), wie viele eigene Namen zuletzt GESETZT bzw.
    zurueckgesetzt waren — und, wenn ``anlass_kennungen`` bekannt sind, Titel
    deren Anlass es nicht mehr gibt. Die Namen selbst werden NICHT gelesen oder
    ausgegeben.
    """
    e: Dict[str, Any] = {"fehlt": True, "zeilen": 0, "kaputt_zeilen": 0, "eintraege": 0,
                         "ohne_kennung": 0, "kennungen": set(), "mehrfach": 0,
                         "gesetzt": 0, "zurueckgesetzt": 0, "ohne_anlass": set()}
    if not os.path.isfile(pfad):
        return e
    e["fehlt"] = False
    letzte: Dict[str, str] = {}
    anzahl_je_kennung: Dict[str, int] = {}
    for zeile in _jsonl(pfad):
        if not isinstance(zeile, dict):
            e["kaputt_zeilen"] += 1
            continue
        e["zeilen"] += 1
        kennung = _kennung(zeile.get("kennung"))
        name = zeile.get("name")
        if not kennung or not isinstance(name, str):
            e["ohne_kennung"] += 1
            continue
        e["eintraege"] += 1
        anzahl_je_kennung[kennung] = anzahl_je_kennung.get(kennung, 0) + 1
        letzte[kennung] = name.strip()
    e["kennungen"] = set(letzte)
    e["mehrfach"] = sum(1 for n in anzahl_je_kennung.values() if n > 1)
    e["gesetzt"] = sum(1 for name in letzte.values() if name)
    e["zurueckgesetzt"] = len(letzte) - e["gesetzt"]
    if anlass_kennungen:
        e["ohne_anlass"] = set(letzte) - anlass_kennungen
    return e


# ── Uebergabe (Handy): was das Geraet beim naechsten Start bekäme ────────────

def _sha256_datei(pfad: str) -> Optional[str]:
    """``sha256`` einer Datei, blockweise und nur lesend; ``None`` wenn unlesbar."""
    pruefer = hashlib.sha256()
    try:
        with open(pfad, "rb") as datei:
            while True:
                stueck = datei.read(65536)
                if not stueck:
                    break
                pruefer.update(stueck)
    except OSError:
        return None
    return pruefer.hexdigest()


def uebergabe_stand_lesen(basis: str,
                          manifest_name: str = STANDARD_UEBERGABE_MANIFEST) -> Dict[str, Any]:
    """Die Uebergabe-Stufe nachzaehlen — **wirft nie**.

    Liest das Manifest (je uebertragener Datei eine Zeile mit ``name``,
    ``quelle``, ``groesse``, ``pruefsumme``), nimmt je Namen die JUENGSTE Zeile
    und stellt sie gegen die lokale Fassung:

    * ``gleich``      — Groesse UND Pruefsumme stimmen (das Geraet holt nichts Neues),
    * ``geaendert``   — die lokale Fassung ist anders: das Geraet wuerde beim
                        naechsten Start die ALTE Fassung aus der pCloud holen,
    * ``fehlt_lokal`` — die uebertragene Datei gibt es am PC nicht mehr.

    Nur Zustand und Zahlen je Datei — nie ein Inhalt, nie ein Pfad. Grenze
    (ehrlich): verglichen wird offline gegen die letzte Buchung; ein spaeterer
    Wechsel der Datei im pCloud-Ordner selbst ist ohne Netzabruf nicht sichtbar.
    """
    pfad = os.path.join(basis, manifest_name)
    if not os.path.isfile(pfad):
        return {"fehlt": True}
    buchungen = 0
    kaputt = 0
    letzte: Dict[str, dict] = {}
    for objekt in _jsonl(pfad):
        if objekt is None:
            kaputt += 1
            continue
        name = _kennung(objekt.get("name"))
        if not name:
            kaputt += 1                      # ohne Namen nicht nachvollziehbar
            continue
        buchungen += 1
        letzte[name] = objekt                 # spaeterer Lauf ueberschreibt
    gleich: List[str] = []
    geaendert: List[str] = []
    fehlt_lokal: List[str] = []
    ohne_pruefsumme: List[str] = []
    unlesbar: List[str] = []
    for name, eintrag in sorted(letzte.items()):
        pruefsumme = eintrag.get("pruefsumme")
        pruefsumme = pruefsumme.strip() if isinstance(pruefsumme, str) else ""
        # Die lokale Fassung: erst flach in ``basis`` (so legt die kabellose
        # Uebergabe sie ab), dann an der im Manifest gebuchten Stelle.
        kandidaten = [os.path.join(basis, name)]
        quelle = eintrag.get("quelle")
        if isinstance(quelle, str) and quelle.strip():
            kandidaten.append(quelle)
        lokal = next((p for p in kandidaten if os.path.isfile(p)), None)
        if lokal is None:
            fehlt_lokal.append(name)
            continue
        if _ganze_zahl(eintrag.get("groesse")) != os.path.getsize(lokal):
            geaendert.append(name)
            continue
        if not pruefsumme:
            ohne_pruefsumme.append(name)
            continue
        ist = _sha256_datei(lokal)
        if ist is None:
            unlesbar.append(name)
        elif ist == pruefsumme:
            gleich.append(name)
        else:
            geaendert.append(name)
    return {"fehlt": False, "buchungen": buchungen, "kaputt": kaputt,
            "namen": set(letzte), "gleich": gleich, "geaendert": geaendert,
            "fehlt_lokal": fehlt_lokal, "ohne_pruefsumme": ohne_pruefsumme,
            "unlesbar": unlesbar}


# ── RUECKWEG Handy -> PC: liegt die geholte Kopie unversehrt am PC ──────────

def rueckweg_lesen(basis: str, manifest_name: str = STANDARD_RUECKWEG_MANIFEST,
                   namen=STANDARD_RUECKWEG_NAMEN) -> Dict[str, Any]:
    """Den Rueckweg Handy -> PC nachzaehlen — **wirft nie**.

    Liest das Manifest (je geholter Datei eine Zeile mit ``name``, ``bytes``,
    ``sha256``, ``zeit``, ``richtung``), nimmt je Namen die JUENGSTE Buchung und
    stellt sie gegen die lokale Fassung (``basis/<name>`` = der Zielordner des
    Hol-Werkzeugs, Standards dieselben wie in ``rueckweg_holen.py``):

    * ``gleich``          — Bytes UND Pruefsumme stimmen: die geholte Kopie liegt
                             unversehrt am PC,
    * ``abweichend``      — lokal ist etwas anderes: die Kopie ist NICHT die
                             gebuchte Fassung,
    * ``fehlt_lokal``     — gebucht, aber am PC nicht (mehr) vorhanden,
    * ``ohne_pruefsumme`` / ``unlesbar`` — nicht vollstaendig vergleichbar.

    Dazu ``unbekannt`` (Buchung ausserhalb der erlaubten Liste), ``mehrfach``
    (mehr als eine Buchung je Name — jeder Lauf bucht, das ist normal) und
    ``vorher`` (zu dem Namen liegt eine ``.vorher``-Sicherung: eine aeltere
    Fassung wurde ersetzt, der Rueckweg ist damit offen). ``letzte`` ist der
    juengste gebuchte Zeitstempel (Textvergleich, ISO-Form).

    Grenze (ehrlich): verglichen wird offline gegen die letzte Buchung. Was seit
    dem Holen AM GERAET dazugekommen ist, ist ohne Kabel nicht sichtbar — und
    ob die Datei am Geraet ueberhaupt neu bereitgestellt wurde, ebenso wenig.
    """
    pfad = os.path.join(basis, manifest_name)
    if not os.path.isfile(pfad):
        return {"fehlt": True}
    satz = {n for n in (namen or ()) if _kennung(n)}
    buchungen = 0
    kaputt = 0
    je_name: Dict[str, dict] = {}
    anzahl: Dict[str, int] = {}
    for objekt in _jsonl(pfad):
        if objekt is None:
            kaputt += 1
            continue
        name = _kennung(objekt.get("name"))
        if not name:
            kaputt += 1                      # ohne Namen nicht nachvollziehbar
            continue
        buchungen += 1
        je_name[name] = objekt               # spaetere Buchung ueberschreibt
        anzahl[name] = anzahl.get(name, 0) + 1
    gleich: List[str] = []
    abweichend: List[str] = []
    fehlt_lokal: List[str] = []
    ohne_pruefsumme: List[str] = []
    unlesbar: List[str] = []
    for name, eintrag in sorted(je_name.items()):
        gebucht_bytes = _ganze_zahl(eintrag.get("bytes"))
        pruefsumme = _kennung(eintrag.get("sha256"))
        lokal = os.path.join(basis, name)
        if not os.path.isfile(lokal):
            fehlt_lokal.append(name)
            continue
        if gebucht_bytes is None or gebucht_bytes != os.path.getsize(lokal):
            abweichend.append(name)
            continue
        if not pruefsumme:
            ohne_pruefsumme.append(name)
            continue
        ist = _sha256_datei(lokal)
        if ist is None:
            unlesbar.append(name)
        elif ist == pruefsumme:
            gleich.append(name)
        else:
            abweichend.append(name)
    vorher = sorted(n for n in je_name
                    if os.path.isfile(os.path.join(basis, n + RUECKWEG_VORHER_SUFFIX)))
    zeiten = [_kennung(e.get("zeit")) for e in je_name.values()]
    return {"fehlt": False, "buchungen": buchungen, "kaputt": kaputt,
            "namen": set(je_name), "unbekannt": sorted(n for n in je_name if n not in satz),
            "mehrfach": sorted(n for n, k in anzahl.items() if k > 1),
            "gleich": gleich, "abweichend": abweichend, "fehlt_lokal": fehlt_lokal,
            "ohne_pruefsumme": ohne_pruefsumme, "unlesbar": unlesbar,
            "vorher": vorher, "letzte": max([z for z in zeiten if z], default="")}


# ── Uebergabe-LISTEN: was geht ueberhaupt ans Geraet ────────────────────────

def uebergabe_listen_lesen(pfad: str) -> Dict[str, Any]:
    """Die ``--dateien``-Liste(n) eines Startskripts lesen — **wirft nie**.

    Rueckgabe: ``{"fehlt": True}`` oder ``{"fehlt": False, "stellen":
    [(Zeile, [Name, ...]), ...], "namen": set}``. Gelesen werden nur Zeilen mit
    ``--dateien`` und daraus die Namen mit einer der ``DIENST_ENDUNGEN``;
    Platzhalter (``"$DATEIEN"``) zaehlen nicht mit. Nur Dateinamen — kein Pfad,
    kein Inhalt.
    """
    stellen: List[Tuple[int, List[str]]] = []
    namen: Set[str] = set()
    if not os.path.isfile(pfad):
        return {"fehlt": True, "stellen": stellen, "namen": namen}
    try:
        with open(pfad, "r", encoding="utf-8", errors="replace") as datei:
            for nummer, roh in enumerate(datei, 1):
                zeile = roh.rstrip("\r\n")
                if "--dateien" not in zeile:
                    continue
                treffer = _LISTEN_MUSTER.search(zeile)
                if not treffer:
                    stellen.append((nummer, []))
                    continue
                hier = [w for w in treffer.group(1).split() if DIENST_DATEI_MUSTER.match(w)]
                stellen.append((nummer, hier))
                namen.update(hier)
    except OSError:
        return {"fehlt": True, "stellen": stellen, "namen": namen}
    return {"fehlt": False, "stellen": stellen, "namen": namen}


def dienst_dateinamen(ordner: str) -> Dict[str, str]:
    """Dateinamen, die der Dienst liest (per AST) — **wirft nie**.

    ``ordner`` wird rekursiv nach ``*.py`` durchsucht (``__pycache__`` bleibt
    aussen vor); je Dateiname die ERSTE Fundstelle als ``Pfad:Zeile``. Gezaehlt
    werden nur einfache Dateinamen (kein Pfadtrenner, kein Leerzeichen, kein
    Punkt am Anfang) mit einer der ``DIENST_ENDUNGEN`` — ein Kommentar ist kein
    Zeichenketten-Literal und zaehlt damit nicht mit.
    """
    gefunden: Dict[str, str] = {}
    if not os.path.isdir(ordner):
        return gefunden
    for wurzel, unterordner, dateien in os.walk(ordner):
        unterordner[:] = [u for u in unterordner if u != "__pycache__"]
        for name in sorted(dateien):
            if not name.endswith(".py"):
                continue
            pfad = os.path.join(wurzel, name)
            try:
                with open(pfad, "r", encoding="utf-8", errors="replace") as datei:
                    baum = ast.parse(datei.read())
            except (OSError, SyntaxError, ValueError):
                continue
            for knoten in ast.walk(baum):
                if not isinstance(knoten, ast.Constant) or not isinstance(knoten.value, str):
                    continue
                wert = knoten.value.strip()
                if not DIENST_DATEI_MUSTER.match(wert):
                    continue
                gefunden.setdefault(wert, f"{os.path.relpath(pfad, ordner)}:{knoten.lineno}")
    return gefunden


def uebergabe_deckung_pruefen(wurzel: str,
                             listen: Sequence[str] = STANDARD_UEBERGABE_LISTEN,
                             app_ordner: str = STANDARD_DIENST_ORDNER,
                             pflicht: str = STANDARD_UEBERGABE_LISTE_PFLICHT,
                             uebergebene: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Die Uebergabe-LISTEN gegen die wirklich gelesenen Dateinamen stellen (**wirft nie**).

    Die Startskripte nennen die Dateien, die ans Geraet gehen — dieselbe Liste
    steht dort mehrfach (mit und ohne ``|| true``), zwei Stellen koennen
    auseinanderlaufen. Geprueft wird:

    * je Skript die Namen und die Aufrufstellen — stimmen sie ueberein?,
    * welche vom Dienst gelesenen Dateien auf KEINEM der beiden Wege ankommen
      (keine Kabel-Liste, nicht kabellos uebergeben) und nicht in
      ``UEBERGABE_GERAETESEITIG`` begruendet sind — sie kaeme nie ans Geraet,
    * **je WEG** (Kabel-Liste gegen kabellose Uebergabe), welche gelesene Datei
      nur auf EINEM der beiden Wege ankommt,
    * welche uebergebenen Dateien (Liste oder Manifest) KEIN Dienst liest.

    Der kabellose Weg hat im Baum GAR KEINE Liste: was er liefert, ist genau
    das, was der PC hochgeladen hat — die Namen des Uebergabe-Manifests. Wird
    dieses Manifest nicht mitgelesen (``uebergebene is None``), bleibt die
    Weg-Frage ehrlich **ungemessen** (``kabellos``/``nur_kabel``/``nur_kabellos``
    = ``None``) statt als Nullwert zu erscheinen.

    Nur Zahlen und Dateinamen — kein Pfad, kein Inhalt.
    """
    skripte: List[Dict[str, Any]] = []
    listen_namen: Set[str] = set()
    for name in listen:
        stand = uebergabe_listen_lesen(os.path.join(wurzel, name))
        stellen = [(z, list(n)) for z, n in stand["stellen"]]
        mengen = {frozenset(n) for _, n in stellen}
        skripte.append({
            "name": name,
            "pflicht": os.path.normpath(name) == os.path.normpath(pflicht),
            "fehlt": bool(stand.get("fehlt")),
            "stellen": stellen,
            "namen": set(stand["namen"]),
            "ungleich": len(mengen) > 1,
        })
        listen_namen |= set(stand["namen"])
    dienst = dienst_dateinamen(os.path.join(wurzel, app_ordner))
    gelesen = set(dienst)
    geraeteseitig = gelesen & set(UEBERGABE_GERAETESEITIG)
    uebergeben = {k for k in (_kennung(n) for n in (uebergebene or ())) if k}
    # Zwei Wege, zwei Mengen: die Kabel-Liste (``listen_namen``) und der
    # kabellose Weg (die Namen im Manifest). Eine vom Dienst gelesene Datei,
    # die nur auf EINEM Weg steht, kommt auf dem anderen Weg NICHT ans Geraet —
    # genau der Neben-Befund aus Journal 27 („zwei Wege, zwei Listen"), hier als
    # dauerhafte, nachzaehlbare Zeile. Bewusst KEINE Luecke: ob ausschliesslich
    # der Kabel- oder der kabellose Weg benutzt wird, entscheidet Sebastian —
    # ein Befund waere sonst ein Dauer-Fehlalarm. „Auf keiner Liste\" (also auf
    # keinem der beiden Wege) bleibt dagegen eine Luecke.
    kabellos = None if uebergebene is None else uebergeben
    if kabellos is None:
        nur_kabel = nur_kabellos = None
    else:
        nur_kabel = (gelesen & listen_namen) - kabellos
        nur_kabellos = (gelesen & kabellos) - listen_namen
    # „Kommt nie ans Geraet\" heisst: auf KEINEM der beiden Wege — eine Datei,
    # die kabellos uebergeben wurde, ist nicht „auf keiner Liste\", sie kommt
    # eben nur ohne Kabel an.
    return {"skripte": skripte, "dienst": dienst, "listen_namen": listen_namen,
            "uebergeben": uebergeben, "geraeteseitig": geraeteseitig,
            "kabellos": kabellos, "nur_kabel": nur_kabel,
            "nur_kabellos": nur_kabellos,
            "ohne_liste": (gelesen - listen_namen - set(UEBERGABE_GERAETESEITIG)
                           - (kabellos or set())),
            "ohne_leser": (listen_namen | uebergeben) - gelesen}


def _projekt_wurzel() -> str:
    """Der Projektordner (dieses Werkzeug liegt in ``tools/foto_sortierung/``)."""
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


# ── pCloud-Operationen (Rueckholbarkeit) ────────────────────────────────────

def bewegungen_lesen(pfad: str) -> Dict[str, Any]:
    """Das Manifest der pCloud-Operationen lesen (wirft nie).

    Gezaehlt werden nur Zahlen: Buchungen, nicht lesbare Zeilen, Buchungen
    ohne Art, die Arten (technische Op-Namen) und je Buchung, ob sie
    ZURUECKFAHRBAR ist. Zurueckfahrbar heisst: das Rueckroll-Werkzeug kann die
    Operation umkehren (``BEWEGUNG_ZURUECKFAHRBAR``). Alles Uebrige wird
    ehrlich getrennt: „nur gemeldet\\" (das Werkzeug kennt die Art, entfernt
    aber nichts — ``createfolder``) und „ohne Rueckroll-Regel\\" (das Werkzeug
    fasst die Art gar nicht an, z. B. ``extractarchive``). Dazu Buchungen ohne
    Ziel (dann gibt es nichts zurueckzufahren), doppelte Buchungen (ein
    Rueckroll-Lauf wuerde sie zweimal fahren), Buchungen einer selbst
    durchgefuehrten Rueckrollung und die Zeitspanne in Tagen.
    """
    stand: Dict[str, Any] = {
        "fehlt": True, "buchungen": 0, "kaputt": 0, "ohne_art": 0,
        "arten": {}, "verschiedene_arten": 0, "rueckholbar": 0,
        "nur_gemeldet": 0, "ohne_regel": 0, "rueckrollungen": 0,
        "ohne_ziel": 0, "doppelt": 0, "tage": 0, "zeit_von": "", "zeit_bis": ""}
    if not os.path.isfile(pfad):
        return stand
    stand["fehlt"] = False
    arten: Dict[str, int] = {}
    gesehen: Set[Tuple[str, str, str]] = set()
    zeiten: Set[str] = set()
    for roh in _jsonl(pfad):
        if roh is None:
            stand["kaputt"] += 1
            continue
        stand["buchungen"] += 1
        art = str(roh.get("art") or "").strip()
        if not art:
            stand["ohne_art"] += 1
        else:
            arten[art] = arten.get(art, 0) + 1
            if art in BEWEGUNG_ZURUECKFAHRBAR:
                stand["rueckholbar"] += 1
            elif art in BEWEGUNG_AKTIONS_ARTEN:
                stand["nur_gemeldet"] += 1
            elif art == BEWEGUNG_ART_RUECKROLL:
                stand["rueckrollungen"] += 1
            else:
                stand["ohne_regel"] += 1
        # Ohne Ziel (Ordner- oder Pfadkennung) gibt es nichts zurueckzufahren.
        if not (roh.get("nach_folderid") or roh.get("nach_pfad")):
            stand["ohne_ziel"] += 1
        schluessel = (art, str(roh.get("name") or ""), str(roh.get("zeit") or ""))
        if schluessel in gesehen:
            stand["doppelt"] += 1
        gesehen.add(schluessel)
        zeit = str(roh.get("zeit") or "")
        if zeit:
            zeiten.add(zeit[:10])
    stand["arten"] = arten
    stand["verschiedene_arten"] = len(arten)
    stand["tage"] = len(zeiten)
    if zeiten:
        stand["zeit_von"], stand["zeit_bis"] = min(zeiten), max(zeiten)
    return stand


# ── Archiv (Chat/WhatsApp) ──────────────────────────────────────────────────

def _ro_verbindung(pfad: str) -> sqlite3.Connection:
    """Eine NUR-LESE-Verbindung (``mode=ro``) — nichts wird geschrieben."""
    return sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)


def _zaehle_sql(verb: sqlite3.Connection, sql: str,
                argumente: Tuple[Any, ...] = ()) -> Optional[int]:
    """Eine Zahl aus SQL — ``None``, wenn die Tabelle/Spalte fehlt (nie ein Wurf)."""
    try:
        zeile = verb.execute(sql, argumente).fetchone()
    except sqlite3.Error:
        return None
    return _ganze_zahl(zeile[0]) if zeile else 0


def _je_quelle(verb: sqlite3.Connection, tabelle: str,
               spalte: str = "source") -> Dict[str, int]:
    """Zeilen je Quelle — leere Antwort, wenn die Tabelle fehlt."""
    try:
        return {(_kennung(q) or "(ohne)"): _ganze_zahl(n) for q, n in
                verb.execute(f"SELECT {spalte}, count(*) FROM {tabelle} "
                             f"GROUP BY {spalte} ORDER BY 2 DESC")}
    except sqlite3.Error:
        return {}


def archiv_jsonl_zaehlen(pfad: str) -> Dict[str, Any]:
    """Die Archiv-Rohdaten zeilenweise zaehlen — **wirft nie**.

    Gelesen wird NUR gezaehlt: Zeilen, nicht lesbare Zeilen, Zeilen ohne Quelle
    und ohne Text, dazu die Quellen als Zahl. Kein Text, kein Titel, kein
    Gespraechsname verlaesst diese Funktion.
    """
    if not os.path.isfile(pfad):
        return {"fehlt": True}
    zeilen = kaputt = ohne_quelle = ohne_text = 0
    quellen: Dict[str, int] = {}
    try:
        with open(pfad, "r", encoding="utf-8", errors="replace") as datei:
            for roh in datei:
                if not roh.strip():
                    continue
                zeilen += 1
                try:
                    objekt = json.loads(roh)
                except (ValueError, TypeError):
                    kaputt += 1
                    continue
                if not isinstance(objekt, dict):
                    kaputt += 1
                    continue
                quelle = _kennung(objekt.get("source") or objekt.get("quelle"))
                if quelle:
                    quellen[quelle] = quellen.get(quelle, 0) + 1
                else:
                    ohne_quelle += 1
                if not _kennung(objekt.get("text")):
                    ohne_text += 1
    except OSError:
        return {"fehlt": True}
    return {"fehlt": False, "zeilen": zeilen, "kaputt": kaputt,
            "ohne_quelle": ohne_quelle, "ohne_text": ohne_text, "quellen": quellen}


def archiv_index_lesen(pfad: str, heute: Optional[str] = None) -> Dict[str, Any]:
    """Den vollen Archiv-Index nachzaehlen (nur lesend) — **wirft nie**.

    Gezaehlt werden Nachrichten (je Quelle, ohne Quelle, ohne Zeitstempel),
    Gespraeche, Chunks (je Quelle, davon mit Vektor), Vektoren (je Modell,
    Dimension, Waisen ohne Chunk), der Volltextindex und die Selbstauskunft in
    ``meta``. ``heute`` (JJJJ-MM-TT) setzt die Grenze fuer „Zeitstempel in der
    Zukunft"; ohne Angabe gilt der heutige Tag. Nur Zahlen — kein Text.
    """
    if not os.path.isfile(pfad):
        return {"fehlt": True}
    try:
        verb = _ro_verbindung(pfad)
    except (sqlite3.Error, OSError):
        return {"nicht_lesbar": True}
    try:
        nachrichten = _zaehle_sql(verb, "SELECT count(*) FROM nachrichten")
        chunks = _zaehle_sql(verb, "SELECT count(*) FROM chunks")
        if nachrichten is None or chunks is None:
            return {"nicht_lesbar": True}
        grenze = (heute or "").strip() or _heute()
        d: Dict[str, Any] = {
            "fehlt": False, "nicht_lesbar": False,
            "nachrichten": nachrichten,
            "nachrichten_je_quelle": _je_quelle(verb, "nachrichten"),
            "ohne_quelle": _zaehle_sql(
                verb, "SELECT count(*) FROM nachrichten "
                      "WHERE source IS NULL OR source = ''") or 0,
            "ohne_zeit": _zaehle_sql(
                verb, "SELECT count(*) FROM nachrichten "
                      "WHERE timestamp IS NULL OR timestamp = ''") or 0,
            "zeit_von": _jahr(verb, "SELECT min(timestamp) FROM nachrichten"),
            "zeit_bis": _jahr(verb, "SELECT max(timestamp) FROM nachrichten"),
            "zu_frueh": _zaehle_sql(
                verb, "SELECT count(*) FROM nachrichten WHERE timestamp < ?",
                (ARCHIV_FRUEHESTES_JAHR,)) or 0,
            "in_der_zukunft": _zaehle_sql(
                verb, "SELECT count(*) FROM nachrichten WHERE timestamp > ?",
                (grenze,)) or 0,
            "chunks": chunks,
            "chunks_mit_vektor": _zaehle_sql(
                verb, "SELECT COALESCE(sum(hat_vektor), 0) FROM chunks") or 0,
            "chunks_je_quelle": _je_quelle(verb, "chunks"),
            "gespraeche": _zaehle_sql(verb, "SELECT count(*) FROM gespraeche"),
            "vektoren": _zaehle_sql(verb, "SELECT count(*) FROM vektoren"),
            "vektoren_ohne_chunk": _zaehle_sql(
                verb, "SELECT count(*) FROM vektoren v WHERE NOT EXISTS "
                      "(SELECT 1 FROM chunks c WHERE c.id = v.chunk_id)") or 0,
            "vektor_modelle": _je_quelle(verb, "vektoren", "modell"),
            "dimensionen": _dimensionen(verb),
            "fts_indexiert": _zaehle_sql(verb, "SELECT count(*) FROM chunks_fts_docsize"),
            "meta": _meta_lesen(verb),
        }
    except sqlite3.Error:
        return {"nicht_lesbar": True}
    finally:
        try:
            verb.close()
        except sqlite3.Error:
            pass
    return d


def _heute() -> str:
    """Der heutige Tag als JJJJ-MM-TT (ohne Zeitzonen-Rechnerei)."""
    import datetime
    return datetime.date.today().isoformat()


def _jahr(verb: sqlite3.Connection, sql: str) -> str:
    """Nur das Jahr aus einem Zeitstempel — nie ein volles Datum, nie ein Fehler."""
    try:
        zeile = verb.execute(sql).fetchone()
    except sqlite3.Error:
        return ""
    wert = _kennung(zeile[0]) if zeile else ""
    return wert[:4] if len(wert) >= 4 and wert[:4].isdigit() else ""


def _dimensionen(verb: sqlite3.Connection) -> List[int]:
    """Die vorkommenden Vektor-Dimensionen (Zahlen) — leer, wenn nicht lesbar."""
    try:
        return sorted({_ganze_zahl(d) for (d,) in
                       verb.execute("SELECT DISTINCT dimension FROM vektoren")})
    except sqlite3.Error:
        return []


def _meta_lesen(verb: sqlite3.Connection) -> Dict[str, str]:
    """Die Schluessel/Wert-Tabelle des Index (Selbstauskunft) — nie ein Wurf."""
    try:
        return {_kennung(k): _kennung(w) for k, w in
                verb.execute("SELECT schluessel, wert FROM meta")}
    except sqlite3.Error:
        return {}


def archiv_memory_lesen(pfad: str) -> Dict[str, Any]:
    """Die Textschicht des alten Weges (``db/memory.db``) nachzaehlen — wirft nie."""
    if not os.path.isfile(pfad):
        return {"fehlt": True}
    try:
        verb = _ro_verbindung(pfad)
    except (sqlite3.Error, OSError):
        return {"nicht_lesbar": True}
    try:
        nachrichten = _zaehle_sql(verb, "SELECT count(*) FROM messages")
        chunks = _zaehle_sql(verb, "SELECT count(*) FROM chunks")
        if nachrichten is None or chunks is None:
            return {"nicht_lesbar": True}
        d = {"fehlt": False, "nicht_lesbar": False, "nachrichten": nachrichten,
             "chunks": chunks,
             "chunks_mit_vektor": _zaehle_sql(
                 verb, "SELECT COALESCE(sum(hat_vektor), 0) FROM chunks") or 0,
             "meta": {}}
        try:
            d["meta"] = {_kennung(k): _kennung(w) for k, w in
                         verb.execute("SELECT schluessel, wert FROM index_meta")}
        except sqlite3.Error:
            pass
    except sqlite3.Error:
        return {"nicht_lesbar": True}
    finally:
        try:
            verb.close()
        except sqlite3.Error:
            pass
    return d


def archiv_vektordatei_stand(ordner: str, vektoren: Optional[int] = None) -> Dict[str, Any]:
    """Liegt die Vektordatei des alten Weges unter dem ERWARTETEN Namen?

    Der alte Weg oeffnet die Vektoren ueber einen festen Dateinamen (und rechnet
    mit 1.024 Werten je Vektor). Liegt die Datei nur unter einem abweichenden
    Namen daneben (z. B. ein Konflikt-Rest der Ablage), findet der alte Weg
    seine Vektoren nicht — die Bedeutungssuche schweigt dann still.

    **Der Name ist ein Hinweis, die Groesse ist der Beleg** (dieselbe Trennung
    wie bei den fehlenden Fotos, Journal 36): passt die Groesse einer daneben
    liegenden Datei genau zur Textschicht (Groesse = Vektoren x Werte je Vektor
    x 4 Byte), ist sie kein beliebiger Rest, sondern die Vektordatei unter
    falschem Namen — dann ist der Ausfall eine Umbenennung, keine fehlende Datei.
    Ohne die Zahl der Vektoren (`vektoren=None`, Datei nicht lesbar) wird das
    NICHT behauptet: dann bleibt es bei der reinen Zaehlung (`geprueft: False`).

    Gemeldet werden nur: da / fehlt, wie viele Dateien mit abweichendem Namen
    daneben liegen, wie viele davon passen und mit wie vielen Werten je Vektor —
    kein Pfad, kein Dateiname, kein Inhalt.
    """
    if not os.path.isdir(ordner):
        return {"ordner_fehlt": True}
    if os.path.isfile(os.path.join(ordner, os.path.basename(ARCHIV_VEKTORDATEI))):
        return {"da": True}
    stamm = os.path.basename(ARCHIV_VEKTORDATEI).rsplit(".", 1)[0]
    try:
        andere = sorted(n for n in os.listdir(ordner)
                        if stamm in n and n.endswith(".f32"))
    except OSError:
        andere = []
    passende: List[int] = []
    if vektoren:
        for n in andere:
            try:
                groesse = os.path.getsize(os.path.join(ordner, n))
            except OSError:
                continue
            if groesse <= 0 or groesse % vektoren:
                continue                     # nicht durch die Zahl der Vektoren teilbar
            werte = groesse // vektoren
            if werte % 4:                    # float32 = 4 Byte je Wert
                continue
            passende.append(werte // 4)
    return {"da": False, "andere": len(andere),
            "geprueft": bool(vektoren), "passende": len(passende),
            "werte_je_vektor": sorted(set(passende))}


def _archiv_kopf(meta: Dict[str, str]) -> str:
    """Eine Zeile aus der Selbstauskunft des Index (Modell, Dimension, Stand, Preis)."""
    teile: List[str] = []
    for schluessel, titel in (("modell", "Modell"), ("dimension", "Dimension"),
                              ("vektor_speicher", "Speicher")):
        wert = _kennung(meta.get(schluessel))
        if wert:
            teile.append(f"{titel} {wert}")
    zeitraum = []
    for schluessel, titel in (("gebaut_am", "gebaut"), ("ergaenzt_am", "ergaenzt")):
        wert = _kennung(meta.get(schluessel))
        if len(wert) >= 10:
            zeitraum.append(f"{titel} {wert[:10]}")
    kosten = _zahl_aus(meta.get("kosten_usd"))
    token = _zahl_aus(meta.get("tokens_gezaehlt"))
    zahlenteil: List[str] = []
    if token:
        zahlenteil.append(f"Token {_z(int(token))}")
    if kosten is not None:
        zahlenteil.append(f"Kosten {_usd(kosten)} USD")
    zeile = ", ".join(teile)
    if zeitraum:
        zeile += ("; " if zeile else "") + ", ".join(zeitraum)
    if zahlenteil:
        zeile += ("; " if zeile else "") + ", ".join(zahlenteil)
    return zeile


def _quellen_kurz(quellen: Dict[str, int], max_: int = 8) -> str:
    """„whatsapp 1.234, chatgpt 56" — nur Quellen-NAMEN (Apps), nie Inhalte."""
    geordnet = sorted(quellen.items(), key=lambda p: (-p[1], p[0]))
    genommen = [f"{name} {_z(zahl)}" for name, zahl in geordnet[:max_]]
    if len(geordnet) > max_:
        genommen.append(f"und {len(geordnet) - max_} weitere")
    return ", ".join(genommen)


# ── Bildindex (Bildsuche) ───────────────────────────────────────────────────

def _zahl_aus(wert: Any) -> Optional[float]:
    """Eine Zahl aus dem ``meta``-Text — oder ``None`` (nichts geraten)."""
    try:
        return float(str(wert).strip())
    except (TypeError, ValueError):
        return None


def bildindex_lesen(pfad: str) -> Dict[str, Any]:
    """``bild_index.db`` zaehlen — nur Zahlen, nur lesend, keine Inhalte.

    Der Index traegt je Bild eine Beschreibung und einen Vektor (Ketten-
    Schritt 7, Grundlage der Bildsuche). Gelesen werden nur ``fileid`` und je
    Bild, ob ein Vektor da ist und ob die Beschreibung nicht leer ist — der
    Text selbst, der Ordner und die Vektoren werden NIE gelesen oder
    ausgegeben. Fehlt die Datei (oder ist sie keine gueltige Datenbank),
    meldet das Ergebnis ehrlich ``fehlt`` statt zu werfen.
    """
    if not os.path.isfile(pfad):
        return {"fehlt": True}
    try:
        verbindung = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    except sqlite3.Error as problem:
        return {"fehlt": True, "fehler": problem.__class__.__name__}
    kennungen: Set[str] = set()
    bilder = mit_vektor = mit_beschreibung = 0
    meta: Dict[str, str] = {}
    try:
        for zeile in verbindung.execute(
                f"SELECT fileid, beschreibung, vektor FROM {BILDINDEX_TABELLE}"):
            kennung = _kennung(zeile[0])
            if not kennung:
                continue
            bilder += 1
            kennungen.add(kennung)
            if zeile[2] is not None:
                mit_vektor += 1
            if str(zeile[1] or "").strip():
                mit_beschreibung += 1
        try:
            meta = {str(z[0]): str(z[1]) for z in
                    verbindung.execute("SELECT schluessel, wert FROM meta")}
        except sqlite3.Error:
            meta = {}
    except sqlite3.Error as problem:
        return {"fehlt": True, "fehler": problem.__class__.__name__}
    finally:
        verbindung.close()
    return {"bilder": bilder, "mit_vektor": mit_vektor,
            "mit_beschreibung": mit_beschreibung, "kennungen": kennungen,
            "meta": meta}


def _bildindex_kopf(meta: Dict[str, str]) -> str:
    """Die ``meta``-Angaben des Index als eine Zeile — nur Zahlen und Namen
    des Modells (kein Inhalt, kein Pfad)."""
    teile: List[str] = []
    if meta.get("modell"):
        teile.append(meta["modell"])
    if meta.get("dimension"):
        teile.append(meta["dimension"] + " Dimensionen")
    token = _zahl_aus(meta.get("tokens_gezaehlt"))
    if token:
        teile.append(_z(int(token)) + " Token")
    kosten = _zahl_aus(meta.get("kosten_usd"))
    if kosten:
        teile.append(_usd(kosten) + " USD")
    if meta.get("stand"):
        teile.append("Stand " + meta["stand"])
    return "; ".join(teile)


# ── Bericht ─────────────────────────────────────────────────────────────────

def _z(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _anteil(teil: int, ganz: int) -> str:
    return f"{(100.0 * teil / ganz):.1f} %".replace(".", ",") if ganz else "–"


def _usd(betrag: float) -> str:
    """USD mit Komma — nur die Zahl, nie der Dateiname (der traegt einen Punkt)."""
    return f"{betrag:.2f}".replace(".", ",")


def _namen_kurz(namen: List[str], max_: int = 8) -> str:
    """Die eigenen Ergebnis-Dateinamen kurz auflisten — nie ein Pfad, nie ein Inhalt."""
    rest = len(namen) - max_
    return ", ".join(namen[:max_]) + (f" ... (+{rest})" if rest > 0 else "")


def _mb(betrag: float) -> str:
    """MegaByte mit Komma und Tausenderpunkt — nur die Zahl."""
    return f"{betrag:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pruefen(basis: str, plaene=STANDARD_PLAENE, foto_vektoren=STANDARD_FOTO_VEKTOREN,
            video_vektoren=STANDARD_VIDEO_VEKTOREN,
            beschreibungen=STANDARD_BESCHREIBUNGEN,
            gesamtplan: Optional[str] = STANDARD_GESAMTPLAN,
            bild_orte: Optional[str] = STANDARD_BILD_ORTE,
            bild_index: Optional[str] = STANDARD_BILDINDEX,
            gedreht_plan: Optional[str] = STANDARD_GEDREHT_PLAN,
            gedreht_vektoren: Optional[str] = STANDARD_GEDREHT_VEKTOREN,
            anlaesse: Optional[str] = STANDARD_ANLAESSE,
            erzaehl_quellen=STANDARD_ERZAHL_QUELLEN,
            orte_namen: Optional[str] = STANDARD_ORTE_NAMEN,
            beziehungen: Optional[str] = STANDARD_BEZEIHUNGEN,
            beziehungen_uebersicht: Optional[str] = STANDARD_BEZEIHUNGEN_UEBERSICHT,
            personen: Optional[str] = STANDARD_PERSONEN,
            app_uebersicht: Optional[str] = STANDARD_APP_UEBERSICHT,
            app_dateien: Optional[str] = STANDARD_APP_DATEIEN,
            duplikate: Optional[str] = STANDARD_DUPLIKATE,
            geschichten: Optional[str] = STANDARD_GESCHICHTEN,
            titel: Optional[str] = STANDARD_TITEL,
            uebergabe: Optional[str] = STANDARD_UEBERGABE_MANIFEST,
            uebergabe_listen: Optional[Sequence[str]] = None,
            rueckweg: Optional[str] = STANDARD_RUECKWEG_MANIFEST,
            bewegungen: Optional[str] = STANDARD_BEWEGUNGEN,
            projekt: Optional[str] = None,
            archiv: Optional[str] = None,
            archiv_heute: Optional[str] = None,
            luecken_details_max: int = 20) -> Tuple[List[str], List[str]]:
    """-> (Berichtszeilen, Luecken). Nur Zahlen, Kennungen und Dateinamen.

    ``luecken_details_max`` = wie viele fehlende Fotos der Gesamtplan mit
    Kennung und Grund benennt (0 = nur zaehlen, wie frueher).

    ``uebergabe_listen`` = die Startskripte mit ``--dateien``-Liste, die gegen
    die im Dienst gelesenen Dateinamen gestellt werden (Voreinstellung ``None``
    = nicht pruefen; die uebrigen Pruefungen bleiben dadurch schnell und
    unveraendert). ``projekt`` = Wurzel des Projekts (Voreinstellung: der
    Projektordner dieses Werkzeugs).

    ``rueckweg`` = das Manifest des Rueckwegs Handy -> PC
    (``rueckweg_manifest.jsonl``, gefuellt von ``tools/handy/rueckweg_holen.py``;
    ``None`` = nicht pruefen). Fehlt die Datei, steht das ehrlich als „noch nicht
    angelegt\" da — kein Dauer-Fehlalarm.

    ``bewegungen`` = das Manifest der schreibenden pCloud-Operationen
    (``manifest.jsonl``, Rueckholbarkeit; ``None`` = nicht pruefen). Fehlt die
    Datei am PC, steht das ehrlich als „noch nicht angelegt\\" da — kein
    Dauer-Fehlalarm.
    """
    zeilen: List[str] = ["Bestandspruefung Fotos - nur Zahlen, nur lesend", ""]
    luecken: List[str] = []

    fv = {n: foto_vektoren_lesen(os.path.join(basis, n)) for n in foto_vektoren}
    vv = {n: video_vektoren_lesen(os.path.join(basis, n)) for n in video_vektoren}
    bq = {n: beschreibungen_lesen(os.path.join(basis, n)) for n in beschreibungen}
    alle_bilder: Set[str] = set().union(*(d["bilder"] for d in fv.values() if not d.get("fehlt")))
    mit_gesicht: Set[str] = set().union(*(d["mit_gesicht"] for d in fv.values() if not d.get("fehlt")))
    mit_fehler: Set[str] = set().union(*(d["mit_fehler"] for d in fv.values() if not d.get("fehlt")))
    mit_massen: Set[str] = set().union(*(d["mit_massen"] for d in fv.values() if not d.get("fehlt")))
    videos_fertig: Set[str] = set().union(*(d["fertig"] for d in vv.values() if not d.get("fehlt")))
    beschrieben: Set[str] = set().union(*(d["kennungen"] for d in bq.values() if not d.get("fehlt")))

    zeilen.append("Dateien:")
    for n, d in fv.items():
        if d.get("fehlt"):
            zeilen.append(f"  {n}: fehlt")
            continue
        zeilen.append(f"  {n}: {_z(len(d['bilder']))} Fotos, {_z(d['gesichter'])} Gesichter, "
                      f"{_z(len(d['mit_fehler']))} mit Fehler, {_z(d['kaputt'])} kaputte Zeilen, "
                      f"{_z(d['doppelt'])} doppelt")
    for n, d in vv.items():
        zeilen.append(f"  {n}: fehlt" if d.get("fehlt") else
                      f"  {n}: {_z(len(d['fertig']))} Videos fertig, {_z(d['gesichter'])} Gesichter")
    for n, d in bq.items():
        zeilen.append(f"  {n}: fehlt" if d.get("fehlt") else
                      f"  {n}: {_z(d['zeilen'])} Zeilen, {_z(len(d['kennungen']))} Fotos, "
                      f"{_z(d['leer'])} leer, {_z(d['kaputt'])} kaputt, Kosten "
                      f"{_usd(d['kosten'])} USD")
    zeilen.append("")

    plan_fotos: Set[str] = set()
    plan_videos: Set[str] = set()
    for name in plaene:
        p = plan_lesen(os.path.join(basis, name))
        if p.get("fehlt"):
            zeilen.append(f"Plan {name}: fehlt")
            continue
        f, v = p["fotos"], p["videos"]
        plan_fotos |= f
        plan_videos |= v
        g_f, g_v, b_f = len(f & alle_bilder), len(v & videos_fertig), len(f & beschrieben)
        zeilen.append(f"Plan {name}: {_z(p['eintraege'])} Eintraege = {_z(len(f))} Fotos + {_z(len(v))} Videos")
        zeilen.append(f"  Gesichter Fotos:  {_z(g_f)} von {_z(len(f))} ({_anteil(g_f, len(f))}), "
                      f"davon {_z(len(f & mit_gesicht))} mit Gesicht, {_z(len(f & mit_fehler))} mit Fehler")
        zeilen.append(f"  Gesichter Videos: {_z(g_v)} von {_z(len(v))} ({_anteil(g_v, len(v))})")
        zeilen.append(f"  Beschreibungen:   {_z(b_f)} von {_z(len(f))} Fotos ({_anteil(b_f, len(f))})")
        if g_f < len(f):
            luecken.append(f"{name}: {_z(len(f) - g_f)} Fotos ohne Gesichtszeile")
        if g_v < len(v):
            luecken.append(f"{name}: {_z(len(v) - g_v)} Videos ohne Gesichter-Lauf")
        if b_f < len(f):
            luecken.append(f"{name}: {_z(len(f) - b_f)} Fotos ohne Beschreibung")
    # Die Duplikat-Pruefung wird EINMAL gelesen: sie traegt die einzige belastbare
    # Gleichheit (gleiche Groesse UND gleiche Pruefsumme = derselbe Inhalt) fuer
    # die Umrechnung Kennung -> Bild weiter unten.
    dp = duplikate_lesen(os.path.join(basis, duplikate)) if duplikate else None
    if gesamtplan:
        gp = gesamtplan_lesen(os.path.join(basis, gesamtplan))
        if gp.get("fehlt"):
            zeilen.append(f"Gesamtplan {gesamtplan}: fehlt - Deckung ueber alle Quellen nicht pruefbar")
        else:
            f = gp["fotos"]
            b_f = len(f & beschrieben)
            ohne = len(f) - b_f
            zeilen.append(f"Gesamtplan {gesamtplan}: {_z(gp['eintraege'])} Eintraege = "
                          f"{_z(len(f))} Fotos + {_z(len(gp['videos']))} Videos + "
                          f"{_z(gp['ohne_namen'])} ohne Namen"
                          f"{' + ' + _z(gp['ohne_kennung']) + ' ohne Kennung' if gp['ohne_kennung'] else ''}")
            zeilen.append(f"  Beschreibungen:   {_z(b_f)} von {_z(len(f))} Fotos ({_anteil(b_f, len(f))}) "
                          f"- in keiner Beschreibungsdatei fehlen {_z(ohne)}")
            if ohne:
                luecken.append(f"{gesamtplan}: {_z(ohne)} Fotos ohne Beschreibung")
                zeilen.append(f"  Fehlende Fotos ({_z(ohne)}), mit Kennung und Grund:")
                detail_zeilen, zaehler = luecken_details(
                    f - beschrieben, alle_bilder, mit_massen,
                    gp.get("namen_doppelt"), luecken_details_max)
                zeilen.extend(detail_zeilen if detail_zeilen else
                              ["    (Einzelheiten abgeschaltet: --luecken-details 0)"])
                zeilen.append("  " + _grund_zeile(zaehler))
                # Kennung ist nicht Bild: dasselbe Foto kann unter zwei
                # Kennungen im Plan stehen. Vor der Kostenentscheidung muss die
                # Zahl die BILDER nennen, nicht die Dateien. Der NAME ist dabei
                # nur ein Hinweis — belastbar ist die Pruefsumme (gleiche Groesse
                # UND gleiche Pruefsumme = derselbe Inhalt, ``duplikate.json``).
                inhaltsgleich = (dp or {}).get("inhaltsgleich") or {}
                bn = bilder_zaehlen(f - beschrieben, gp.get("namen_je_kennung"), beschrieben,
                                    inhaltsgleich)
                if bn["bilder"] != bn["kennungen"] or bn["anderswo_beschrieben"]:
                    zeilen.append(
                        f"  Bilder statt Kennungen: {_z(bn['kennungen'])} Kennungen = "
                        f"{_z(bn['bilder'])} Bilder"
                        + (f" ({_z(bn['doppelte_kennungen'])} Kennungen sind Doppel desselben "
                           f"Namens)" if bn["doppelte_kennungen"] else "")
                        + (f"; {_z(bn['anderswo_beschrieben'])} davon traegt einen Namen, der "
                           f"an einer anderen Kennung schon beschrieben ist (Name ist kein "
                           f"Beleg fuer denselben Inhalt)"
                           if bn["anderswo_beschrieben"] else "")
                        + f" - die Namens-Sicht ergaebe {_z(bn['bilder_ohne_text'])} Bilder "
                          f"ohne Beschreibungstext (nicht belegt)")
                if bn["inhalte"] is not None and (bn["inhaltsgruppen"]
                                                  or bn["inhalte"] != bn["bilder"]):
                    stand_dp = ((dp or {}).get("stand") or "")[:10] or "ohne Stand"
                    zeilen.append(
                        f"  Inhaltsgleich (Pruefsumme, {duplikate} vom {stand_dp}): "
                        f"{_z(bn['inhaltsgleich_kennungen'])} der {_z(bn['kennungen'])} "
                        f"Kennungen haben eine inhaltsgleiche andere Datei, "
                        f"{_z(bn['inhaltsgruppen'])} Gruppe(n) gleichen Inhalts unter den "
                        f"Fehlenden; {_z(bn['inhaltsgleich_beschrieben'])} davon hat schon "
                        f"einen Text - es bleiben {_z(bn['inhalte'])} verschiedene Bilder, "
                        f"{_z(bn['bilder_ohne_text_belegt'])} davon ohne Beschreibungstext "
                        f"(belastbare Zahl fuer die Kostenentscheidung)")
                # Der Grund „nicht ladbar" hat oft eine technische Ursache, die
                # die Endung zeigt (Format, kein Name).
                ohne_masse = [k for k in (f - beschrieben) if k in alle_bilder and k not in mit_massen]
                endungen = endungen_zaehlen(ohne_masse, gp.get("namen_je_kennung"))
                if endungen:
                    zeilen.append(f"  Ohne Bildmasse (nicht ladbar): {_z(len(ohne_masse))} "
                                  f"- Endungen: "
                                  + ", ".join(f"{e} {_z(n)}" for e, n in endungen))
    if gedreht_plan:
        gdp = plan_lesen(os.path.join(basis, gedreht_plan))
        if gdp.get("fehlt"):
            zeilen.append(f"Rotierte Bilder ({gedreht_plan}): fehlt - Neuausrichtung nicht pruefbar")
        else:
            rotiert = gdp["fotos"] | gdp["videos"]
            if not gedreht_vektoren:
                zeilen.append(f"Rotierte Bilder ({gedreht_plan}): {_z(len(rotiert))} Bilder "
                              f"(Vektordatei nicht geprueft)")
            else:
                gdv = foto_vektoren_lesen(os.path.join(basis, gedreht_vektoren))
                if gdv.get("fehlt"):
                    zeilen.append(f"Rotierte Bilder ({gedreht_plan}): {_z(len(rotiert))} Bilder; "
                                  f"{gedreht_vektoren} fehlt - neue Zeilen nicht pruefbar")
                    luecken.append(f"{gedreht_vektoren} fehlt (rotierte Bilder ohne neue Zeile)")
                else:
                    neu = gdv["bilder"]
                    mit = len(rotiert & neu)
                    ohne = len(rotiert - neu)
                    zeilen.append(f"Rotierte Bilder ({gedreht_plan}): {_z(len(rotiert))} Bilder, "
                                  f"davon {_z(mit)} mit neuer Vektorzeile ({_anteil(mit, len(rotiert))}), "
                                  f"ohne {_z(ohne)}")
                    if ohne:
                        luecken.append(f"{gedreht_plan}: {_z(ohne)} Bilder ohne neue Vektorzeile")
    ausserhalb = len(alle_bilder - plan_fotos)
    zeilen.append(f"Vektorzeilen ausserhalb aller Plaene: {_z(ausserhalb)}; "
                  f"Beschreibungen ausserhalb aller Plaene: {_z(len(beschrieben - plan_fotos))}")
    zeilen.append("")

    if anlaesse:
        an = anlaesse_lesen(os.path.join(basis, anlaesse))
        if an.get("fehlt"):
            zeilen.append(f"Anlaesse ({anlaesse}): fehlt - Anlass aus EXIF/Dateiname nicht "
                          f"gebaut (ereignisse_ordner_bauen.py)")
            luecken.append(f"{anlaesse} fehlt (Anlaesse nicht gebaut)")
        else:
            k = an["kennungen"]
            in_anlaessen = len(plan_fotos & k)
            zeilen.append(f"Anlaesse ({anlaesse}): {_z(an['anlaesse'])} Anlaesse, "
                          f"{_z(len(k))} Datei-Kennungen, davon {_z(an['videos'])} Videos"
                          + (f", {_z(an['kaputt'])} kaputte Zeilen" if an["kaputt"] else "")
                          + (f", {_z(an['ohne_kennung'])} ohne Kennung" if an["ohne_kennung"] else ""))
            quellen = ", ".join(f"{name} {_z(n)}" for name, n in sorted(an["datum_quellen"].items()))
            zeilen.append(f"  Datum: {_z(an['mit_datum'])} von {_z(an['anlaesse'])} Anlaessen "
                          f"tragen eines"
                          + (f" ({quellen})" if quellen else " (keine Quellenangabe)"))
            if an["jahr_min"]:
                zeilen.append(f"  Jahre: {an['jahr_min']}-{an['jahr_max']}")
            if plan_fotos:
                zeilen.append(f"  Deckung: {_z(in_anlaessen)} von {_z(len(plan_fotos))} "
                              f"Plan-Fotos liegen in einem Anlass ({_anteil(in_anlaessen, len(plan_fotos))})")
        zeilen.append("")

    if erzaehl_quellen:
        vorhanden = 0
        for name in erzaehl_quellen:
            eq = anlaesse_lesen(os.path.join(basis, name))
            if eq.get("fehlt"):
                zeilen.append(f"Erzaehl-Anlaesse ({name}): fehlt - Anlaesse nicht gebaut "
                              f"(dem Erzaehlen fehlt diese Quelle)")
                luecken.append(f"{name} fehlt (Erzaehl-Anlaesse nicht gebaut)")
                continue
            vorhanden += 1
            k = eq["kennungen"]
            zeilen.append(f"Erzaehl-Anlaesse ({name}): {_z(eq['anlaesse'])} Anlaesse, "
                          f"{_z(len(k))} Datei-Kennungen"
                          + (f", {_z(eq['kaputt'])} kaputte Zeilen" if eq["kaputt"] else "")
                          + (f", {_z(eq['ohne_kennung'])} ohne Kennung (wird nicht erzaehlt)"
                             if eq["ohne_kennung"] else ""))
            if eq["mit_datum"]:
                quellen = ", ".join(f"{q} {_z(n)}" for q, n in sorted(eq["datum_quellen"].items()))
                zeilen.append(f"  Datum: {_z(eq['mit_datum'])} von {_z(eq['anlaesse'])} tragen eines"
                              + (f" ({quellen})" if quellen else " (keine Quellenangabe)"))
            if eq["jahr_min"]:
                zeilen.append(f"  Jahre: {eq['jahr_min']}-{eq['jahr_max']}")
            if plan_fotos:
                drin = len(plan_fotos & k)
                zeilen.append(f"  Deckung: {_z(drin)} von {_z(len(plan_fotos))} Plan-Fotos "
                              f"liegen in einem Anlass ({_anteil(drin, len(plan_fotos))})")
            if eq["ohne_kennung"]:
                luecken.append(f"{name}: {_z(eq['ohne_kennung'])} Anlaesse ohne Kennung "
                               f"(werden nicht erzaehlt)")
        zeilen.append(f"  Erzaehl-Dienst: {_z(vorhanden)} von {_z(len(erzaehl_quellen))} dieser "
                      f"Quellen vorhanden (dazu {anlaesse or 'ordner_ereignisse.jsonl'})")
        if not vorhanden:
            luecken.append("keine Erzaehl-Anlaesse vorhanden (Geschichten ohne Anlass)")
        zeilen.append("")

    if beziehungen:
        bz = beziehungen_lesen(os.path.join(basis, beziehungen))
        if bz.get("fehlt"):
            zeilen.append(f"Beziehungen ({beziehungen}): fehlt - die Auskunft \"wer war mit wem wo\" "
                          f"hat keine Quelle (beziehungen_ableiten.py)")
            luecken.append(f"{beziehungen} fehlt (Beziehungen nicht abgeleitet)")
        else:
            unterarten = ", ".join(f"{name} {_z(n)}" for name, n in sorted(bz["unterarten"].items()))
            zeilen.append(f"Beziehungen ({beziehungen}): {_z(bz['zeilen'])} Aussagen, "
                          f"{_z(len(bz['anlaesse']))} Anlaesse, {_z(len(bz['tage']))} Tage, "
                          f"{_z(len(bz['kategorien']))} Kategorien"
                          + (f", {_z(bz['kaputt'])} kaputte Zeilen" if bz["kaputt"] else ""))
            zeilen.append(f"  Unterarten: {unterarten or 'keine'}")
            zeilen.append(f"  Personen-Eintraege: {_z(bz['personen_eintraege'])}, davon "
                          f"{_z(bz['personen_bestaetigt'])} bestaetigt, "
                          f"{_z(bz['personen_mit_kennung'])} mit Kennung")
            if bz["jahr_min"]:
                zeilen.append(f"  Datum: {_z(bz['mit_datum'])} von {_z(bz['zeilen'])} tragen eines; "
                              f"Jahre {bz['jahr_min']}-{bz['jahr_max']}")
        if beziehungen_uebersicht:
            ub = beziehungen_uebersicht_lesen(os.path.join(basis, beziehungen_uebersicht))
            if ub.get("fehlt"):
                zeilen.append(f"  Uebersicht ({beziehungen_uebersicht}): fehlt - die Kennzahlen der "
                              f"Antwortstufe fehlen")
                luecken.append(f"{beziehungen_uebersicht} fehlt (Beziehungs-Kennzahlen fehlen)")
            elif ub.get("kaputt"):
                zeilen.append(f"  Uebersicht ({beziehungen_uebersicht}): nicht lesbar (kein JSON)")
                luecken.append(f"{beziehungen_uebersicht} nicht lesbar")
            else:
                arten = ", ".join(f"{name} {_z(n)}" for name, n in sorted(ub["anzahl"].items()))
                zeilen.append(f"  Uebersicht ({beziehungen_uebersicht}): nennt {_z(ub['summe'])} "
                              f"Aussagen ({arten or 'keine Arten'}); Kontakte {_z(ub['kontakte'])}, "
                              f"Kennungen {_z(ub['personen_kennungen'])}"
                              + (f"; {ub['datum_von']} bis {ub['datum_bis']}" if ub["datum_von"] else ""))
                if not bz.get("fehlt") and ub["summe"] and ub["summe"] != bz["zeilen"]:
                    zeilen.append(f"    Abweichung: Uebersicht nennt {_z(ub['summe'])}, gemessen "
                                  f"{_z(bz['zeilen'])} - Datei und Kennzahlen passen nicht zusammen")
                    luecken.append(f"{beziehungen}: {_z(bz['zeilen'])} Aussagen, Uebersicht nennt "
                                   f"{_z(ub['summe'])} (nicht reproduzierbar)")
        zeilen.append("")

    if personen:
        pe = personen_lesen(basis, personen)
        if pe.get("fehlt"):
            zeilen.append(f"Personen (Quiz): {personen} fehlt - die Personen-Auskunft hat keine "
                          f"Quelle (personen_gruppieren.py --schreiben, dann uebergeben)")
            luecken.append(f"{personen} fehlt (Personen ohne Namen)")
        elif pe.get("kaputt"):
            zeilen.append(f"Personen (Quiz): {personen} nicht lesbar (kein JSON) - die "
                          f"Personen-Auskunft faellt aus")
            luecken.append(f"{personen} nicht lesbar")
        else:
            zeilen.append(f"Personen (Quiz): {personen}: {_z(pe['kennungen'])} Kennungen mit Namen "
                          f"= {_z(pe['personen'])} Personen"
                          + (f", {_z(pe['ohne_namen'])} ohne Namen" if pe["ohne_namen"] else "")
                          + (f"; {_z(pe['kennungen_ohne_gruppe'])} Kennungen ohne Gruppe "
                             f"(davon {_z(pe['ohne_gruppe_doppelt'])} mit demselben Namen an einer "
                             f"Gruppe, {_z(pe['ohne_gruppe_ins_leere'])} ins Leere)"
                             if pe["kennungen_ohne_gruppe"] else ""))
            zeilen.append(f"  Vorgaben: gleich {_z(pe['gleich'])}, verschieden {_z(pe['verschieden'])}, "
                          f"ausgeschlossen {_z(pe['ausgeschlossen'])}")
            zeilen.append(f"  Profile ({PERSONEN_PROFILE}): {_z(pe['profile'])} Eintraege, davon "
                          f"{_z(pe['profile_mit_beziehung'])} mit Beziehung, "
                          f"{_z(pe['profile_mit_notiz'])} mit Notiz ({_z(pe['notizen'])} Notizen), "
                          f"{_z(pe['profile_mit_kontakt'])} mit Telefonbuch-Kontakt")
            zeilen.append(f"  Telefonbuch ({PERSONEN_KONTAKTE}): {_z(pe['kontakte'])} Kontakte, davon "
                          f"{_z(pe['kontakte_mit_geburtstag'])} mit Geburtstag")
            zeilen.append(f"  Quiz-Stand: spaeter {_z(pe['spaeter'])}, unbekannt {_z(pe['unbekannt'])}; "
                          f"Protokoll {_z(pe['protokoll_zeilen'])} Zeilen")
            if pe["fehlende"]:
                zeilen.append(f"  Noch nicht angelegt: {', '.join(pe['fehlende'])}")
            if pe["kennungen_ohne_gruppe"]:
                luecken.append(f"{personen}: {_z(pe['kennungen_ohne_gruppe'])} Kennungen ohne Gruppe "
                               f"(Namen ohne Gesichter) - {_z(pe['ohne_gruppe_doppelt'])} davon tragen "
                               f"denselben Namen an einer lebenden Gruppe (verwaiste Eintraege), "
                               f"{_z(pe['ohne_gruppe_ins_leere'])} zeigen ins Leere")
        zeilen.append("")

    if app_uebersicht or app_dateien:
        ue = app_uebersicht_lesen(os.path.join(basis, app_uebersicht) if app_uebersicht else "")
        da = app_dateien_lesen(os.path.join(basis, app_dateien) if app_dateien else "")
        if app_uebersicht:
            if ue.get("fehlt"):
                zeilen.append(f"Fotos-Uebersicht (App): {app_uebersicht} fehlt - die App hat keine "
                              f"Zahlen (foto_uebersicht.py)")
                luecken.append(f"{app_uebersicht} fehlt (App-Uebersicht nicht abgeleitet)")
            elif ue.get("kaputt"):
                zeilen.append(f"Fotos-Uebersicht (App): {app_uebersicht} nicht lesbar (kein JSON)")
                luecken.append(f"{app_uebersicht} nicht lesbar")
            else:
                zahlen = ue["zahlen"]
                zeilen.append(f"Fotos-Uebersicht (App): {app_uebersicht}: {_z(ue['events'])} Events, "
                              f"{_z(ue['jahre'])} Jahre, {_z(ue['kategorien'])} Kategorien, "
                              f"{_z(ue['themen'])} Themen"
                              + (f", {_z(ue['events_ohne_name'])} Events ohne Namen"
                                 if ue["events_ohne_name"] else ""))
                kennzahlen = ", ".join(f"{_z(zahlen[k])} {k}" for k in
                                       ("zeilen", "anlaesse", "zuege") if k in zahlen)
                zeilen.append("  zahlen: " + (kennzahlen or "keine Zahlen")
                              + (f"; Stand {ue['stand']}" if ue["stand"] else ""))
                z_events = _ganze_zahl(zahlen.get("events"))
                if ue["events"] and z_events and ue["events"] != z_events:
                    zeilen.append(f"    Abweichung: {_z(ue['events'])} Event-Zeilen, zahlen.events "
                                  f"nennt {_z(z_events)}")
                    luecken.append(f"{app_uebersicht}: {_z(ue['events'])} Event-Zeilen, zahlen.events "
                                   f"{_z(z_events)} (nicht reproduzierbar)")
        if app_dateien:
            if da.get("fehlt"):
                zeilen.append(f"Datei-Kennungen (App): {app_dateien} fehlt - die Bildvorschau hat "
                              f"keine Kennungen (foto_dateien.py)")
                luecken.append(f"{app_dateien} fehlt (Vorschau ohne Datei-Kennungen)")
            elif da.get("kaputt"):
                zeilen.append(f"Datei-Kennungen (App): {app_dateien} nicht lesbar (kein JSON)")
                luecken.append(f"{app_dateien} nicht lesbar")
            else:
                zahlen = da["zahlen"]
                zeilen.append(f"Datei-Kennungen (App): {app_dateien}: {_z(da['events'])} Events, "
                              f"{_z(da['datei_eintraege'])} Datei-Kennungen, Summe anzahl "
                              f"{_z(da['anzahl_summe'])}"
                              + (f", {_z(da['events_ohne_dateien'])} Events ohne Dateien"
                                 if da["events_ohne_dateien"] else "")
                              + (f", {_z(da['dateien_ohne_kennung'])} Dateien ohne Kennung"
                                 if da["dateien_ohne_kennung"] else ""))
                kennzahlen = ", ".join(f"{_z(zahlen[k])} {k}" for k in
                                       ("events", "dateien", "ohne_kennung") if k in zahlen)
                zeilen.append("  zahlen: " + (kennzahlen or "keine Zahlen")
                              + (f"; Stand {da['stand']}" if da["stand"] else "")
                              + (f"; Plan-Stand {da['plan_stand']}" if da["plan_stand"] else ""))
                if da["events_ohne_event"]:
                    luecken.append(f"{app_dateien}: {_z(da['events_ohne_event'])} Events ohne Namen")
                if da["dateien_ohne_kennung"]:
                    luecken.append(f"{app_dateien}: {_z(da['dateien_ohne_kennung'])} Dateien ohne "
                                   f"Kennung (Vorschau nicht ladbar)")
                z_dateien = _ganze_zahl(zahlen.get("dateien"))
                if da["datei_eintraege"] and z_dateien and da["datei_eintraege"] != z_dateien:
                    zeilen.append(f"    Abweichung: {_z(da['datei_eintraege'])} Datei-Eintraege, "
                                  f"zahlen.dateien nennt {_z(z_dateien)}")
                    luecken.append(f"{app_dateien}: {_z(da['datei_eintraege'])} Datei-Eintraege, "
                                   f"zahlen.dateien {_z(z_dateien)} (nicht reproduzierbar)")
        # Abgleich der beiden Dateien: sie stammen aus derselben Quelle
        # (sortierplan.json) und muessen dieselbe Zahl Events/Dateien nennen.
        if (app_uebersicht and app_dateien and not ue.get("fehlt") and not ue.get("kaputt")
                and not da.get("fehlt") and not da.get("kaputt")):
            ue_zuege = _ganze_zahl(ue["zahlen"].get("zuege"))
            zeilen.append(f"  Abgleich: Events {_z(ue['events'])} / {_z(da['events'])}; "
                          f"Dateien {_z(ue_zuege)} / {_z(da['datei_eintraege'])}")
            if ue["events"] != da["events"]:
                luecken.append(f"App-Uebersicht ({_z(ue['events'])} Events) und Datei-Kennungen "
                               f"({_z(da['events'])}) passen nicht zusammen")
            if ue_zuege and da["datei_eintraege"] and ue_zuege != da["datei_eintraege"]:
                luecken.append(f"App-Uebersicht nennt {_z(ue_zuege)} Zuege, Datei-Kennungen "
                               f"{_z(da['datei_eintraege'])} (nicht reproduzierbar)")
        zeilen.append("")

    if duplikate:
        dp = dp if dp is not None else duplikate_lesen(os.path.join(basis, duplikate))
        if dp.get("fehlt"):
            zeilen.append(f"Doppelte (pCloud): {duplikate} fehlt - die Duplikat-Pruefung ist "
                          f"nicht gelaufen (pcloud_duplikate.py, nur lesend, kein Loeschen)")
            luecken.append(f"{duplikate} fehlt (Doppelte nicht geprueft)")
        elif dp.get("kaputt"):
            zeilen.append(f"Doppelte (pCloud): {duplikate} nicht lesbar (kein JSON)")
            luecken.append(f"{duplikate} nicht lesbar")
        else:
            z, mb = dp["zahlen"], dp["mb"]
            arten = ", ".join(f"{name} {_z(n)}" for name, n in sorted(dp["arten"].items()))
            zeilen.append(f"Doppelte (pCloud): {duplikate}: {_z(dp['gruppen'])} Gruppen, "
                          f"{_z(dp['gruppen_anzahl'])} betroffene Dateien, "
                          f"{_z(dp['mitglieder'])} Mitglieder ({arten or 'keine Arten'})")
            for name, baum in sorted(dp["baeume"].items()):
                zeilen.append(f"  Baum {name}: {_z(baum['dateien'])} Dateien in "
                              f"{_z(baum['ordner'])} Ordnern gelesen, Tiefe {_z(baum['tiefe'])}"
                              + (f"; nicht zu Ende gelesen (offen {_z(baum['offen'])})"
                                 if baum["abgebrochen"] or baum["offen"] else "")
                              + (f"; {_z(baum['ohne_hash'])} ohne Pruefsumme"
                                 if baum["ohne_hash"] else ""))
            kennzahlen = ", ".join(f"{_z(z[k])} {k}" for k in
                                   ("gescannte_dateien", "vergleichbare_dateien",
                                    "duplikatgruppen", "betroffene_dateien") if k in z)
            zeilen.append("  Zusammenfassung: " + (kennzahlen or "keine Zahlen"))
            zeilen.append(f"  Groesse: {_mb(mb.get('mb_alle_kopien', 0.0))} MB in allen Kopien, "
                          f"{_mb(dp['kandidaten_mb'])} MB Loesch-Kandidaten "
                          f"({_z(dp['kandidaten_dateien'])} Dateien)")
            ueber, innen = dp["ueber_baeume"], dp["innerhalb"]
            if ueber or innen:
                innen_text = ", ".join(f"{name} {_z(b['gruppen'])}/{_z(b['dateien'])}"
                                       for name, b in sorted(innen.items()))
                zeilen.append(f"  Ueber Baeume: {_z(ueber.get('gruppen', 0))} Gruppen, "
                              f"{_z(ueber.get('dateien', 0))} Dateien"
                              + (f"; innerhalb je Baum (Gruppen/Dateien): {innen_text}"
                                 if innen_text else ""))
            zeilen.append(f"  Abgleich: Gruppen {_z(dp['gruppen'])} / "
                          f"{_z(z.get('duplikatgruppen', 0))}, Dateien {_z(dp['gruppen_anzahl'])} / "
                          f"{_z(z.get('betroffene_dateien', 0))}, Kandidaten "
                          f"{_z(dp['kandidaten_dateien'])} / {_z(dp['kandidaten_liste'])}"
                          + (f"; Stand {dp['stand']}" if dp["stand"] else "")
                          + ("; Trockenlauf (es wurde nichts geloescht)" if dp["trocken"] else ""))
            # Ehrliche Pruefungen: die Kennzahlen muessen zur gezaehlten Liste passen.
            if dp["gruppen"] and z.get("duplikatgruppen") and dp["gruppen"] != z["duplikatgruppen"]:
                luecken.append(f"{duplikate}: {_z(dp['gruppen'])} Gruppen in der Liste, "
                               f"Zusammenfassung nennt {_z(z['duplikatgruppen'])} "
                               f"(nicht reproduzierbar)")
            if dp["gruppen"] and dp["gruppen_anzahl"] != dp["mitglieder"]:
                luecken.append(f"{duplikate}: {_z(dp['gruppen_anzahl'])} betroffene Dateien, "
                               f"aber {_z(dp['mitglieder'])} Mitglieder (nicht reproduzierbar)")
            if (z.get("betroffene_dateien") and dp["gruppen_anzahl"]
                    and z["betroffene_dateien"] != dp["gruppen_anzahl"]):
                luecken.append(f"{duplikate}: {_z(dp['gruppen_anzahl'])} betroffene Dateien, "
                               f"Zusammenfassung nennt {_z(z['betroffene_dateien'])} "
                               f"(nicht reproduzierbar)")
            if dp["kandidaten_dateien"] and (dp["kandidaten_dateien"] != dp["kandidaten_liste"]
                                             or dp["kandidaten_dateien"] != dp["kandidaten_aus_gruppen"]):
                luecken.append(f"{duplikate}: {_z(dp['kandidaten_dateien'])} Loesch-Kandidaten, "
                               f"Liste {_z(dp['kandidaten_liste'])}, in den Gruppen "
                               f"{_z(dp['kandidaten_aus_gruppen'])} (nicht reproduzierbar)")
            if ueber.get("gruppen") is not None and z.get("duplikatgruppen"):
                zusammen = ueber.get("gruppen", 0) + sum(b.get("gruppen", 0) for b in innen.values())
                if zusammen != z["duplikatgruppen"]:
                    luecken.append(f"{duplikate}: ueber Baeume {_z(ueber.get('gruppen', 0))} + "
                                   f"innerhalb {_z(zusammen - ueber.get('gruppen', 0))} Gruppen, "
                                   f"Zusammenfassung nennt {_z(z['duplikatgruppen'])} "
                                   f"(nicht reproduzierbar)")
            # Der Scan selbst muss vollstaendig sein, sonst ist die Zahl nur ein Teil.
            for name, baum in sorted(dp["baeume"].items()):
                if baum["abgebrochen"] or baum["offen"]:
                    luecken.append(f"{duplikate}: Baum {name} nicht zu Ende gelesen "
                                   f"(offen {_z(baum['offen'])}) - Doppeltenzahl unvollstaendig")
                unvergleichbar = baum["ohne_hash"] + baum["ohne_groesse"] + baum["ohne_kennung"]
                if unvergleichbar:
                    luecken.append(f"{duplikate}: Baum {name} {_z(unvergleichbar)} Dateien ohne "
                                   f"Pruefsumme, Groesse oder Kennung (nicht vergleichbar)")
        zeilen.append("")

    if geschichten or titel:
        anlass_kennungen = anlass_kennungen_sammeln(basis)
        if geschichten:
            gs = geschichten_lesen(os.path.join(basis, geschichten), anlass_kennungen)
            if gs.get("fehlt"):
                zeilen.append(f"Eigene Geschichten: {geschichten} noch nicht angelegt - die "
                              f"Schicht 'mensch' entsteht am Geraet (erzaehl_service), am PC "
                              f"nicht pruefbar")
            else:
                quellen = ", ".join(f"{name} {_z(n)}" for name, n in sorted(gs["quellen"].items()))
                zeilen.append(f"Eigene Geschichten: {geschichten}: {_z(gs['eintraege'])} Geschichten, "
                              f"{_z(len(gs['ereignis_kennungen']))} Anlaesse, "
                              f"{_z(gs['mit_bild'])} zu einem Bild"
                              + (f", {_z(gs['ohne_ereignis'])} ohne Anlass-Kennung"
                                 if gs["ohne_ereignis"] else "")
                              + (f", {_z(gs['kaputt_zeilen'])} kaputte Zeilen"
                                 if gs["kaputt_zeilen"] else "")
                              + (f", {_z(gs['ohne_id'])} ohne Kennung" if gs["ohne_id"] else ""))
                zeilen.append("  Quellen: " + (quellen or "keine Quellenangabe")
                              + (f"; {_z(gs['alte_fassungen'])} abgeloeste Fassungen"
                                 if gs["alte_fassungen"] else "")
                              + (f"; {_z(len(gs['ohne_anlass']))} Anlass-Kennungen ohne Anlass"
                                 if gs["ohne_anlass"] else ""))
                if gs["kaputt_zeilen"]:
                    luecken.append(f"{geschichten}: {_z(gs['kaputt_zeilen'])} kaputte Zeilen")
                if gs["ohne_id"]:
                    luecken.append(f"{geschichten}: {_z(gs['ohne_id'])} Zeilen ohne Kennung "
                                   f"(der Dienst verwirft sie still - die Geschichte fehlt)")
                if gs["ohne_text"]:
                    luecken.append(f"{geschichten}: {_z(gs['ohne_text'])} leere Geschichten")
                if gs["tote_verweise"]:
                    luecken.append(f"{geschichten}: {_z(gs['tote_verweise'])} ersetzt-Verweise auf "
                                   f"eine nicht vorhandene Kennung (Fassungskette gebrochen)")
                if gs["ohne_anlass"]:
                    luecken.append(f"{geschichten}: {_z(len(gs['ohne_anlass']))} Geschichten zu einem "
                                   f"Anlass, den es nicht mehr gibt (Text zeigt ins Leere)")
        if titel:
            tt = eigene_titel_lesen(os.path.join(basis, titel), anlass_kennungen)
            if tt.get("fehlt"):
                zeilen.append(f"Eigene Titel: {titel} noch nicht angelegt - die eigenen "
                              f"Anlassnamen entstehen am Geraet, am PC nicht pruefbar")
            else:
                zeilen.append(f"Eigene Titel: {titel}: {_z(len(tt['kennungen']))} Anlaesse umbenannt "
                              f"({_z(tt['gesetzt'])} mit eigenem Namen, "
                              f"{_z(tt['zurueckgesetzt'])} zurueckgesetzt)"
                              + (f", {_z(tt['mehrfach'])} mit mehreren Zeilen (Fassungen)"
                                 if tt["mehrfach"] else "")
                              + (f", {_z(tt['kaputt_zeilen'])} kaputte Zeilen"
                                 if tt["kaputt_zeilen"] else "")
                              + (f", {_z(tt['ohne_kennung'])} ohne Kennung"
                                 if tt["ohne_kennung"] else ""))
                if tt["kaputt_zeilen"]:
                    luecken.append(f"{titel}: {_z(tt['kaputt_zeilen'])} kaputte Zeilen")
                if tt["ohne_kennung"]:
                    luecken.append(f"{titel}: {_z(tt['ohne_kennung'])} Zeilen ohne brauchbare Kennung "
                                   f"(der eigene Name geht verloren)")
                if tt["ohne_anlass"]:
                    luecken.append(f"{titel}: {_z(len(tt['ohne_anlass']))} eigene Titel zu einem Anlass, "
                                   f"den es nicht mehr gibt (Name zeigt ins Leere)")
        zeilen.append("")

    ub_namen: Optional[Set[str]] = None
    if uebergabe:
        ub = uebergabe_stand_lesen(basis, uebergabe)
        if not ub.get("fehlt"):
            ub_namen = set(ub["namen"])
        if ub.get("fehlt"):
            zeilen.append(f"Uebergabe (Handy): {uebergabe} noch nicht angelegt - es wurde noch "
                          f"nichts kabellos uebergeben (uebergabe_hochladen.py)")
        else:
            zeilen.append(f"Uebergabe (Handy): {uebergabe}: {_z(ub['buchungen'])} Buchungen, "
                          f"{_z(len(ub['namen']))} verschiedene Dateien "
                          f"(gleich {_z(len(ub['gleich']))}, geaendert {_z(len(ub['geaendert']))}, "
                          f"am PC fehlt {_z(len(ub['fehlt_lokal']))})"
                          + (f", {_z(ub['kaputt'])} kaputte Zeilen" if ub["kaputt"] else ""))
            if ub["geaendert"]:
                zeilen.append(f"  Seit der letzten Uebergabe geaendert ({_z(len(ub['geaendert']))}) "
                              f"- das Geraet holt die alte Fassung: {_namen_kurz(ub['geaendert'])}")
            if ub["fehlt_lokal"]:
                zeilen.append(f"  Am PC nicht mehr vorhanden ({_z(len(ub['fehlt_lokal']))}): "
                              f"{_namen_kurz(ub['fehlt_lokal'])}")
            if ub["unlesbar"]:
                zeilen.append(f"  Nicht lesbar ({_z(len(ub['unlesbar']))}): "
                              f"{_namen_kurz(ub['unlesbar'])}")
            if ub["ohne_pruefsumme"]:
                zeilen.append(f"  Ohne Pruefsumme gebucht, nur ueber die Groesse verglichen "
                              f"({_z(len(ub['ohne_pruefsumme']))}): "
                              f"{_namen_kurz(ub['ohne_pruefsumme'])}")
            if ub["kaputt"]:
                luecken.append(f"{uebergabe}: {_z(ub['kaputt'])} kaputte Buchungen "
                               f"(Uebergabe nicht nachvollziehbar)")
            if ub["geaendert"]:
                luecken.append(f"{uebergabe}: {_z(len(ub['geaendert']))} Datei(en) seit der letzten "
                               f"Uebergabe geaendert - das Geraet holt beim naechsten Start die "
                               f"alte Fassung")
            if ub["fehlt_lokal"]:
                luecken.append(f"{uebergabe}: {_z(len(ub['fehlt_lokal']))} uebertragene Datei(en) "
                               f"am PC nicht mehr vorhanden (Uebergabe nicht nachvollziehbar)")
            if ub["unlesbar"]:
                luecken.append(f"{uebergabe}: {_z(len(ub['unlesbar']))} uebertragene Datei(en) "
                               f"nicht lesbar (Stand nicht pruefbar)")
            if ub["ohne_pruefsumme"]:
                luecken.append(f"{uebergabe}: {_z(len(ub['ohne_pruefsumme']))} Buchung(en) ohne "
                               f"Pruefsumme (nur ueber die Groesse vergleichbar)")
        zeilen.append("")

    if rueckweg:
        rw = rueckweg_lesen(basis, rueckweg)
        if rw.get("fehlt"):
            zeilen.append(f"Rueckweg (Handy -> PC): {rueckweg} noch nicht angelegt - die am "
                          f"Geraet erzeugten Datendateien sind noch nie an den PC geholt "
                          f"(rueckweg_holen.py; das Geraet stellt sie beim naechsten Start bereit)")
        else:
            zeilen.append(f"Rueckweg (Handy -> PC): {rueckweg}: {_z(rw['buchungen'])} Buchungen, "
                          f"{_z(len(rw['namen']))} verschiedene Dateien "
                          f"(unversehrt {_z(len(rw['gleich']))}, abweichend "
                          f"{_z(len(rw['abweichend']))}, am PC fehlt {_z(len(rw['fehlt_lokal']))})"
                          + (f", letzte {rw['letzte']}" if rw["letzte"] else "")
                          + (f", {_z(rw['kaputt'])} kaputte Zeilen" if rw["kaputt"] else ""))
            if rw["gleich"]:
                zeilen.append(f"  Unversehrt am PC ({_z(len(rw['gleich']))}): "
                              f"{_namen_kurz(rw['gleich'])}")
            if rw["abweichend"]:
                zeilen.append(f"  Nicht die gebuchte Fassung ({_z(len(rw['abweichend']))}): "
                              f"{_namen_kurz(rw['abweichend'])}")
            if rw["fehlt_lokal"]:
                zeilen.append(f"  Gebucht, am PC nicht vorhanden "
                              f"({_z(len(rw['fehlt_lokal']))}): {_namen_kurz(rw['fehlt_lokal'])}")
            if rw["vorher"]:
                zeilen.append(f"  Aeltere Fassung liegt als .vorher beiseite "
                              f"({_z(len(rw['vorher']))}): {_namen_kurz(rw['vorher'])}")
            if rw["mehrfach"]:
                zeilen.append(f"  Mehrfach gebucht ({_z(len(rw['mehrfach']))}): "
                              f"{_namen_kurz(rw['mehrfach'])}")
            if rw["unbekannt"]:
                zeilen.append(f"  Ausserhalb der erlaubten Liste gebucht "
                              f"({_z(len(rw['unbekannt']))}): {_namen_kurz(rw['unbekannt'])}")
            if rw["kaputt"]:
                luecken.append(f"{rueckweg}: {_z(rw['kaputt'])} kaputte Buchungen "
                               f"(Rueckweg nicht nachvollziehbar)")
            if rw["abweichend"]:
                luecken.append(f"{rueckweg}: {_z(len(rw['abweichend']))} geholte Datei(en) weichen "
                               f"von der Buchung ab - am PC liegt nicht die geholte Fassung")
            if rw["fehlt_lokal"]:
                luecken.append(f"{rueckweg}: {_z(len(rw['fehlt_lokal']))} gebuchte Datei(en) am "
                               f"PC nicht vorhanden (Rueckweg nicht nachvollziehbar)")
            if rw["unlesbar"]:
                luecken.append(f"{rueckweg}: {_z(len(rw['unlesbar']))} geholte Datei(en) nicht "
                               f"lesbar (Stand nicht pruefbar)")
            if rw["ohne_pruefsumme"]:
                luecken.append(f"{rueckweg}: {_z(len(rw['ohne_pruefsumme']))} Buchung(en) ohne "
                               f"Pruefsumme (nur ueber die Groesse vergleichbar)")
        # Deckung des Rueckwegs — eine ZEILE, keine Luecke: welche Datei nur am
        # Geraet lebt, ist Sebastians Entscheidung (sonst Dauer-Fehlalarm). Nur
        # Zahlen und Dateinamen.
        ohne_weg = sorted(n for n in UEBERGABE_GERAETESEITIG
                          if n not in set(STANDARD_RUECKWEG_NAMEN))
        zeilen.append(f"  Geraeteseitige Dateien: {_z(len(UEBERGABE_GERAETESEITIG))} bekannt, "
                      f"{_z(len(STANDARD_RUECKWEG_NAMEN))} mit Rueckweg, "
                      f"{_z(len(ohne_weg))} ohne: {_namen_kurz(ohne_weg)}")
        zeilen.append("")

    if uebergabe_listen:
        dl = uebergabe_deckung_pruefen(projekt or _projekt_wurzel(), tuple(uebergabe_listen),
                                       uebergebene=ub_namen)
        teile = []
        for s in dl["skripte"]:
            if s["fehlt"]:
                teile.append(f"{s['name']}: nicht gefunden")
            elif not s["stellen"]:
                teile.append(f"{s['name']}: keine --dateien-Liste")
            else:
                teile.append(f"{s['name']}: {_z(len(s['namen']))} Namen, "
                             f"{_z(len(s['stellen']))} Stellen "
                             f"({'ungleich' if s['ungleich'] else 'gleich'})")
        zeilen.append("Uebergabe-Listen (Deckung): " + "; ".join(teile)
                      if teile else "Uebergabe-Listen (Deckung): keine Liste angegeben")
        zeilen.append(f"  Dienst liest {_z(len(dl['dienst']))} Datendateinamen; auf einer Liste "
                      f"{_z(len(dl['listen_namen']))}, geraeteseitig {_z(len(dl['geraeteseitig']))}, "
                      f"ohne Liste {_z(len(dl['ohne_liste']))}")
        if dl["ohne_liste"]:
            zeilen.append(f"  Auf keinem Weg - kaeme nie ans Geraet "
                          f"({_z(len(dl['ohne_liste']))}): {_namen_kurz(sorted(dl['ohne_liste']))}")
        # Zwei Wege, zwei Mengen: je Weg sagen, was nur dort ankommt (Zeile,
        # keine Luecke - welcher Weg benutzt wird, entscheidet Sebastian).
        if dl["kabellos"] is None:
            zeilen.append("  Kabelloser Weg nicht gemessen (Uebergabe-Manifest nicht gelesen) - "
                          "welche gelesene Datei nur ueber das Kabel ankommt, bleibt offen")
        else:
            zeilen.append(f"  Kabelloser Weg: {_z(len(dl['kabellos']))} Dateien im Manifest "
                          f"(Uebergabe-Liste des Kabels: {_z(len(dl['listen_namen']))}); "
                          f"nur kabelseitig {_z(len(dl['nur_kabel']))}, "
                          f"nur kabellos {_z(len(dl['nur_kabellos']))}")
            if dl["nur_kabel"]:
                zeilen.append(f"  Nur ueber das KABEL ans Geraet - ohne Kabel fehlt sie dem "
                              f"Dienst ({_z(len(dl['nur_kabel']))}): "
                              f"{_namen_kurz(sorted(dl['nur_kabel']))}")
            if dl["nur_kabellos"]:
                zeilen.append(f"  Nur KABELLOS (pCloud) ans Geraet - mit Kabel fehlt sie dem "
                              f"Dienst ({_z(len(dl['nur_kabellos']))}): "
                              f"{_namen_kurz(sorted(dl['nur_kabellos']))}")
        if dl["ohne_leser"]:
            zeilen.append(f"  Uebergeben, aber von keinem Dienst gelesen "
                          f"({_z(len(dl['ohne_leser']))}): {_namen_kurz(sorted(dl['ohne_leser']))}")
        for s in dl["skripte"]:
            if s["fehlt"] and s["pflicht"]:
                luecken.append(f"{s['name']} fehlt (die Uebergabe-Liste ist nicht pruefbar)")
            if s["stellen"] and s["ungleich"]:
                luecken.append(f"{s['name']}: die {_z(len(s['stellen']))} Aufrufstellen der "
                               f"Uebergabe-Liste stimmen nicht ueberein")
        for name in sorted(dl["ohne_liste"]):
            luecken.append(f"{name}: der Dienst liest sie, sie kommt aber auf keinem der "
                           f"beiden Uebergabe-Wege ans Geraet (keine Kabel-Liste, nicht "
                           f"kabellos uebergeben)")
        zeilen.append("")

    if bewegungen:
        bw = bewegungen_lesen(os.path.join(basis, bewegungen))
        if bw.get("fehlt"):
            zeilen.append(f"pCloud-Operationen (Rueckholbarkeit): {bewegungen} noch nicht "
                          f"angelegt - es wurde noch nichts auf pCloud angelegt oder entpackt "
                          f"(pcloud_bewegungen.py)")
        else:
            arten = ", ".join(f"{name} {_z(n)}" for name, n in sorted(bw["arten"].items()))
            zeilen.append(f"pCloud-Operationen (Rueckholbarkeit): {bewegungen}: "
                          f"{_z(bw['buchungen'])} Buchungen, "
                          f"{_z(bw['verschiedene_arten'])} Arten"
                          + (f" ({arten})" if arten else "")
                          + (f", {_z(bw['ohne_art'])} ohne Art" if bw["ohne_art"] else "")
                          + (f", {_z(bw['kaputt'])} kaputte Zeilen" if bw["kaputt"] else "")
                          + (f", {_z(bw['doppelt'])} doppelt" if bw["doppelt"] else "")
                          + (f", {_z(bw['ohne_ziel'])} ohne Ziel" if bw["ohne_ziel"] else ""))
            zeilen.append(f"  Zurueckfahrbar (movefile/movefolder): {_z(bw['rueckholbar'])}; "
                          f"nur gemeldet, nichts entfernt (createfolder): "
                          f"{_z(bw['nur_gemeldet'])}; ohne Rueckroll-Regel (das Werkzeug "
                          f"fasst sie gar nicht an): {_z(bw['ohne_regel'])}"
                          + (f"; Rueckrollungen gebucht: {_z(bw['rueckrollungen'])}"
                             if bw["rueckrollungen"] else ""))
            if bw["zeit_von"]:
                zeilen.append(f"  Stand: {bw['zeit_von']} bis {bw['zeit_bis']} "
                              f"({_z(bw['tage'])} Tag(e))")
            zeilen.append("  Grenze (ehrlich): offline pruefbar ist nur das Manifest - ob die "
                          "Operation auf pCloud noch so steht, zeigt erst ein Netzabruf")
            if bw["kaputt"]:
                luecken.append(f"{bewegungen}: {_z(bw['kaputt'])} nicht lesbare Buchungen "
                               f"(die pCloud-Operationen sind nicht nachvollziehbar)")
            if bw["ohne_art"]:
                luecken.append(f"{bewegungen}: {_z(bw['ohne_art'])} Buchung(en) ohne Art "
                               f"(nicht rueckholbar)")
            if bw["ohne_ziel"]:
                luecken.append(f"{bewegungen}: {_z(bw['ohne_ziel'])} Buchung(en) ohne Ziel "
                               f"(es gibt nichts zurueckzufahren)")
            if bw["doppelt"]:
                luecken.append(f"{bewegungen}: {_z(bw['doppelt'])} doppelte Buchung(en) "
                               f"(ein Rueckroll-Lauf wuerde sie zweimal fahren)")
        zeilen.append("")

    if archiv is not None:
        if not os.path.isdir(archiv):
            zeilen.append("Archiv (Chat/WhatsApp): Archivordner nicht gefunden - das "
                          "Chat-Archiv ist nicht pruefbar")
            luecken.append("Chat-Archiv nicht gefunden (Archiv-Antworten ohne Fundstellen)")
        else:
            aj = archiv_jsonl_zaehlen(os.path.join(archiv, ARCHIV_MESSAGES))
            ai = archiv_index_lesen(os.path.join(archiv, ARCHIV_INDEX_DB),
                                    heute=archiv_heute)
            am = archiv_memory_lesen(os.path.join(archiv, ARCHIV_MEMORY_DB))
            av = archiv_vektordatei_stand(
                os.path.join(archiv, os.path.dirname(ARCHIV_VEKTORDATEI)),
                vektoren=am.get("chunks_mit_vektor"))
            n_roh = os.path.basename(ARCHIV_MESSAGES)
            n_index = os.path.basename(ARCHIV_INDEX_DB)
            n_memory = os.path.basename(ARCHIV_MEMORY_DB)
            n_vektor = os.path.basename(ARCHIV_VEKTORDATEI)
            if aj.get("fehlt"):
                zeilen.append(f"Archiv (Chat/WhatsApp): {n_roh} fehlt - die Rohdaten des "
                              f"Archivs fehlen, der Bestand ist nicht nachzaehlbar")
                luecken.append(f"{n_roh} fehlt (Archiv-Rohdaten fehlen)")
            else:
                zeilen.append(f"Archiv (Chat/WhatsApp): {n_roh}: {_z(aj['zeilen'])} Zeilen"
                              + (f", {_z(aj['kaputt'])} nicht lesbar" if aj["kaputt"] else "")
                              + (f", {_z(aj['ohne_quelle'])} ohne Quelle" if aj["ohne_quelle"] else "")
                              + (f", {_z(aj['ohne_text'])} ohne Text" if aj["ohne_text"] else "")
                              + f" - {_z(len(aj['quellen']))} Quellen")
                zeilen.append(f"  Quellen: {_quellen_kurz(aj['quellen'])}")
                if aj["kaputt"]:
                    luecken.append(f"{n_roh}: {_z(aj['kaputt'])} Zeilen nicht lesbar "
                                   f"(Nachrichten fehlen im Archiv)")
                if aj["ohne_quelle"]:
                    luecken.append(f"{n_roh}: {_z(aj['ohne_quelle'])} Zeilen ohne Quelle "
                                   f"(nicht auffindbar)")
            if ai.get("fehlt"):
                zeilen.append(f"  {n_index} fehlt - der Chat sucht nur im alten Weg; "
                              f"WhatsApp-Bestand nicht im Index (archiv_index_bauen.py)")
                luecken.append(f"{n_index} fehlt (Chat-Suche ohne vollen Bestand)")
            elif ai.get("nicht_lesbar"):
                zeilen.append(f"  {n_index}: nicht lesbar (keine brauchbare SQLite-Datei) - "
                              f"Archiv nicht nachzaehlbar")
                luecken.append(f"{n_index} nicht lesbar (Archiv nicht nachzaehlbar)")
            else:
                zeilen.append(f"  {n_index}: {_z(ai['nachrichten'])} Nachrichten, "
                              f"{_z(ai['gespraeche'])} Gespraeche, {_z(ai['chunks'])} Chunks, "
                              f"{_z(ai['chunks_mit_vektor'])} mit Vektor, "
                              f"{_z(ai['vektoren'])} Vektoren"
                              + (f", {_z(ai['vektoren_ohne_chunk'])} Vektoren ohne Chunk"
                                 if ai["vektoren_ohne_chunk"] else ""))
                kopf = _archiv_kopf(ai.get("meta") or {})
                if kopf:
                    zeilen.append("  " + kopf)
                if ai.get("fts_indexiert") is None:
                    zeilen.append("  Volltextindex: nicht gefunden (kein FTS-Bestand)")
                    luecken.append(f"{n_index}: Volltextindex fehlt (Volltextsuche ohne Treffer)")
                else:
                    zeilen.append(f"  Volltextindex: {_z(ai['fts_indexiert'])} von "
                                  f"{_z(ai['chunks'])} Chunks indexiert")
                    if ai["fts_indexiert"] != ai["chunks"]:
                        luecken.append(f"{n_index}: {_z(abs(ai['chunks'] - ai['fts_indexiert']))} "
                                       f"Chunks nicht im Volltextindex (Volltextsuche unvollstaendig)")
                if ai["dimensionen"]:
                    aufzaehlung = ", ".join(_z(d) for d in ai["dimensionen"])
                    zeilen.append(f"  Vektor-Dimensionen: {_z(len(ai['dimensionen']))}"
                                  + (f" ({aufzaehlung})" if len(ai["dimensionen"]) <= 4 else ""))
                zeilen.append(f"  Zeitstempel: {_z(ai['ohne_zeit'])} ohne"
                              + (f", Jahre {ai['zeit_von']}-{ai['zeit_bis']}"
                                 if ai["zeit_von"] or ai["zeit_bis"] else "")
                              + f"; vor {ARCHIV_FRUEHESTES_JAHR}: {_z(ai['zu_frueh'])}"
                              + (f"; in der Zukunft: {_z(ai['in_der_zukunft'])}"
                                 if ai["in_der_zukunft"] else ""))
                if ai["ohne_quelle"]:
                    luecken.append(f"{n_index}: {_z(ai['ohne_quelle'])} Nachrichten ohne Quelle")
                if ai["ohne_zeit"]:
                    luecken.append(f"{n_index}: {_z(ai['ohne_zeit'])} Nachrichten ohne Zeitstempel")
                if ai["chunks_mit_vektor"] < ai["chunks"]:
                    luecken.append(f"{n_index}: {_z(ai['chunks'] - ai['chunks_mit_vektor'])} "
                                   f"Chunks ohne Vektor (Bedeutungssuche unvollstaendig)")
                if ai["vektoren"] != ai["chunks_mit_vektor"]:
                    luecken.append(f"{n_index}: Vektoren ({_z(ai['vektoren'])}) und Chunks mit "
                                   f"Vektor ({_z(ai['chunks_mit_vektor'])}) passen nicht zusammen "
                                   f"-> nicht reproduzierbar")
                if ai["vektoren_ohne_chunk"]:
                    luecken.append(f"{n_index}: {_z(ai['vektoren_ohne_chunk'])} Vektoren ohne "
                                   f"Chunk (verwaist)")
                if not aj.get("fehlt"):
                    if ai["nachrichten"] != aj["zeilen"]:
                        luecken.append(f"{n_index}: {_z(ai['nachrichten'])} Nachrichten gegen "
                                       f"{_z(aj['zeilen'])} Zeilen in {n_roh} "
                                       f"-> nicht reproduzierbar")
                    fehlend = sorted(set(aj["quellen"]) - set(ai["nachrichten_je_quelle"]))
                    if fehlend:
                        luecken.append(f"{n_index}: Quelle(n) ohne Nachricht im Index: "
                                       f"{_quellen_kurz({q: aj['quellen'][q] for q in fehlend}, 4)}")
                selbst = {k: _ganze_zahl((ai.get("meta") or {}).get(k)) for k in
                          ("nachrichten", "chunks", "gespraeche")}
                abweichung = [k for k, v in selbst.items()
                              if v and v != ai[k]]
                if abweichung:
                    luecken.append(f"{n_index}: Selbstauskunft weicht von der Zaehlung ab "
                                   f"({', '.join(abweichung)}) -> nicht reproduzierbar")
            if am.get("fehlt"):
                zeilen.append(f"  {n_memory} fehlt - der Rueckfallweg hat keine Textschicht")
                luecken.append(f"{n_memory} fehlt (Rueckfallweg der Chat-Suche ohne Text)")
            elif am.get("nicht_lesbar"):
                zeilen.append(f"  {n_memory}: nicht lesbar")
                luecken.append(f"{n_memory} nicht lesbar (Rueckfallweg nicht pruefbar)")
            else:
                zeilen.append(f"  Rueckfallweg {n_memory}: {_z(am['nachrichten'])} Nachrichten, "
                              f"{_z(am['chunks'])} Chunks, davon {_z(am['chunks_mit_vektor'])} mit "
                              f"Vektor (alter Stand)")
                if not aj.get("fehlt") and am["nachrichten"] != aj["zeilen"]:
                    luecken.append(f"{n_memory}: {_z(am['nachrichten'])} Nachrichten gegen "
                                   f"{_z(aj['zeilen'])} Zeilen in {n_roh} "
                                   f"-> nicht reproduzierbar")
            if not av.get("ordner_fehlt"):
                if av.get("da"):
                    zeilen.append(f"  Vektordatei des Rueckfallwegs ({n_vektor}): vorhanden")
                else:
                    zusatz = ""
                    if av.get("andere"):
                        zusatz = (f" ({_z(av['andere'])} Datei(en) mit abweichendem Namen "
                                  f"daneben")
                        if av.get("geprueft"):
                            if av.get("passende"):
                                werte = "/".join(_z(w) for w in av.get("werte_je_vektor") or [])
                                zusatz += (f", davon {_z(av['passende'])} passend zur Textschicht "
                                           f"({_z(am.get('chunks_mit_vektor', 0))} Vektoren zu je "
                                           f"{werte} Werten) - nur der NAME weicht ab, die "
                                           f"Bedeutungssuche des Rueckfallwegs findet sie so nicht")
                            else:
                                zusatz += (f", keine passt zur Textschicht "
                                           f"({_z(am.get('chunks_mit_vektor', 0))} Vektoren) - "
                                           f"es ist keine Vektordatei dieses Weges")
                        zusatz += ")"
                    zeilen.append(f"  Vektordatei des Rueckfallwegs ({n_vektor}): fehlt" + zusatz)
        zeilen.append("")

    if bild_index:
        bi = bildindex_lesen(os.path.join(basis, bild_index))
        if bi.get("fehlt"):
            zeilen.append(f"Bildindex (Bildsuche): {bild_index} fehlt - die Beschreibungen "
                          f"sind nicht eingebettet (bild_index_einbetten.py)")
            luecken.append(f"{bild_index} fehlt (Bildsuche nicht eingebettet)")
        else:
            zeilen.append(f"Bildindex (Bildsuche): {bild_index}: {_z(bi['bilder'])} Bilder, "
                          f"{_z(bi['mit_vektor'])} mit Vektor, "
                          f"{_z(bi['mit_beschreibung'])} mit Beschreibung")
            kopf = _bildindex_kopf(bi.get("meta") or {})
            if kopf:
                zeilen.append("  " + kopf)
            ohne_vektor = beschrieben - bi["kennungen"]
            ohne_eintrag = bi["kennungen"] - beschrieben
            zeilen.append(f"  Beschrieben, aber ohne Vektor im Index: {_z(len(ohne_vektor))}; "
                          f"im Index, aber nicht beschrieben: {_z(len(ohne_eintrag))}")
            if ohne_vektor:
                luecken.append(f"{bild_index}: {_z(len(ohne_vektor))} beschriebene Fotos ohne "
                               f"Vektor (Bildsuche unvollstaendig)")
        zeilen.append("")

    if bild_orte:
        o = orte_lesen(os.path.join(basis, bild_orte))
        gebiete = karten_gebiete(os.path.join(basis, KARTEN_CSV_ORDNER))
        if o.get("fehlt"):
            zeilen.append(f"Orte (OSM): {bild_orte} fehlt - Kartenauswertung nicht zugeordnet "
                          f"(orte_aus_karte.py --zuordnen); Gebiete mit Tabellen: {_z(gebiete)}")
            luecken.append(f"{bild_orte} fehlt (Kartenauswertung nicht zugeordnet)")
        else:
            zeilen.append(f"Orte (OSM): {bild_orte}: {_z(o['zeilen'])} Zeilen (eine je Bild) = "
                          f"{_z(o['mit_gps'])} mit GPS + {_z(o['ohne_gps'])} ohne GPS + "
                          f"{_z(o['flug'])} im Flug")
            zeilen.append(f"  Ortsname {_z(o['mit_ort'])}, Landmarke {_z(o['mit_landmarke'])}, "
                          f"Strasse {_z(o['mit_strasse'])}, Hausnummer {_z(o['mit_hausnummer'])}"
                          + (f", {_z(o['kaputt'])} kaputte Zeilen" if o["kaputt"] else ""))
            zeilen.append(f"  Karten: {_z(gebiete)} Gebiete mit beiden Tabellen (osm/csv)")
            z_orte = tabellen_zeilen(os.path.join(basis, KARTEN_CSV_ORDNER, KARTEN_ORTE))
            z_adr = tabellen_zeilen(os.path.join(basis, KARTEN_CSV_ORDNER, KARTEN_ADRESSEN))
            if z_orte or z_adr:
                zeilen.append(f"  Gesamttabellen: {_z(z_orte)} Orte, {_z(z_adr)} Adressen")
    zeilen.append("")

    if orte_namen:
        on = ortsnamen_lesen(os.path.join(basis, orte_namen))
        if on.get("fehlt"):
            zeilen.append(f"Orte (GeoNames): {orte_namen} fehlt - Ortsnamen nicht zugeordnet "
                          f"(orte_zuordnen.py)")
            luecken.append(f"{orte_namen} fehlt (Ortsnamen nicht zugeordnet)")
        else:
            eintraege = len(on["kennungen"])
            zeilen.append(f"Orte (GeoNames): {orte_namen}: {_z(on['zeilen'])} Zeilen, "
                          f"{_z(eintraege)} Bilder"
                          + (f", {_z(on['doppelt'])} doppelt" if on["doppelt"] else "")
                          + (f", {_z(on['kaputt'])} kaputte Zeilen" if on["kaputt"] else ""))
            zeilen.append(f"  Namen: {_z(on['laender'])} Laender, {_z(on['regionen'])} Regionen, "
                          f"{_z(on['orte'])} Orte; ohne Ortsnamen {_z(on['ohne_ort'])}")
            zeilen.append(f"  Aufnahme: {_z(on['mit_datum'])} von {_z(on['zeilen'])} Zeilen "
                          f"tragen ein Datum ({_z(on['tage'])} verschiedene Tage)")
            if plan_fotos:
                drin = len(plan_fotos & on["kennungen"])
                zeilen.append(f"  Deckung: {_z(drin)} von {_z(len(plan_fotos))} Plan-Fotos "
                              f"haben einen Ortsnamen ({_anteil(drin, len(plan_fotos))})")
            if on["doppelt"]:
                luecken.append(f"{orte_namen}: {_z(on['doppelt'])} doppelte Zeilen "
                               f"(anhaengender Lauf nicht idempotent)")
        zeilen.append("")

    gr = gruppen_lesen(basis)
    if gr.get("fehlt"):
        zeilen.append("Gruppen: personen_gruppen/personen_beispiele.json fehlt - der Gruppierer "
                      "lief nur trocken (Trockenlauf schreibt nichts). Fuer das Quiz: "
                      "personen_gruppieren.py --schreiben")
        luecken.append("Gruppen nicht gespeichert (nur Trockenlauf)")
    else:
        a = gr["abdeckung"]
        zeilen.append(f"Gruppen (Stand {gr['stand']}): {_z(gr['gruppen'])} Gruppen mit "
                      f"{_z(gr['gesichter_in_gruppen'])} Gesichtern, benannt {_z(gr['benannt'])}")
        zeilen.append(f"  Groesse: {_z(gr['ab_50'])} Gruppen >= 50 Gesichter, {_z(gr['ab_10'])} >= 10, "
                      f"{_z(gr['unter_10'])} unter 10; {_z(gr['mit_zwilling'])} mit Zwillingsverdacht")
        zeilen.append(f"  Abdeckung: die groessten {_z(a.get(0.5, 0))} Gruppen = 50 % der Gesichter, "
                      f"{_z(a.get(0.8, 0))} = 80 %, {_z(a.get(0.9, 0))} = 90 %")
        if "zuordnung_zeilen" in gr:
            zeilen.append(f"  Zuordnung: {_z(gr['zuordnung_zeilen'])} Gesichter, davon "
                          f"{_z(gr['zuordnung_mit_gruppe'])} in einer Gruppe "
                          f"({_anteil(gr['zuordnung_mit_gruppe'], gr['zuordnung_zeilen'])}), "
                          f"Rest = Einzelgesichter/Menge")
        else:
            luecken.append("gesicht_zuordnung.jsonl fehlt")
    zeilen.append("")
    zeilen.append("Ergebnis: " + ("alles vollstaendig" if not luecken else f"{len(luecken)} Luecke(n)"))
    zeilen.extend("  - " + l for l in luecken)
    return zeilen, luecken


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Bestand pruefen - nur lesend, nur Zahlen.")
    parser.add_argument("--basis", default=STANDARD_BASIS)
    parser.add_argument("--archiv", default=STANDARD_ARCHIV_ORDNER,
                        help="Ordner des Chat-Archivs (Schwesterordner des Projekts); "
                             "leer lassen = nicht pruefen")
    parser.add_argument("--archiv-heute", default="", dest="archiv_heute",
                        help="Grenze fuer „Zeitstempel in der Zukunft\" (JJJJ-MM-TT; "
                             "leer = heutiger Tag)")
    parser.add_argument("--bewegungen", default=STANDARD_BEWEGUNGEN,
                        help="Manifest der schreibenden pCloud-Operationen "
                             "(Rueckholbarkeit; leer lassen = nicht pruefen)")
    parser.add_argument("--luecken-details", type=int, default=20, dest="luecken_details",
                        help="wie viele fehlende Fotos mit Kennung und Grund benannt werden "
                             "(0 = nur zaehlen)")
    parser.add_argument("--uebergabe-listen", default=",".join(STANDARD_UEBERGABE_LISTEN),
                        dest="uebergabe_listen",
                        help="Startskripte mit --dateien-Liste, mit Komma getrennt "
                             "(leer lassen = nicht pruefen)")
    parser.add_argument("--rueckweg", default=STANDARD_RUECKWEG_MANIFEST,
                        help="Manifest des Rueckwegs Handy -> PC "
                             "(rueckweg_manifest.jsonl; leer lassen = nicht pruefen)")
    args = parser.parse_args(argv)
    if not os.path.isdir(args.basis):
        print(f"Ordner fehlt: {args.basis}")
        return 2
    listen = tuple(t.strip() for t in (args.uebergabe_listen or "").split(",") if t.strip())
    zeilen, _ = pruefen(args.basis, luecken_details_max=args.luecken_details,
                        bewegungen=(args.bewegungen or None),
                        uebergabe_listen=(listen or None),
                        rueckweg=(args.rueckweg or None),
                        archiv=(args.archiv or None),
                        archiv_heute=(args.archiv_heute or None))
    print("\n".join(zeilen))
    return 0


if __name__ == "__main__":
    sys.exit(main())
