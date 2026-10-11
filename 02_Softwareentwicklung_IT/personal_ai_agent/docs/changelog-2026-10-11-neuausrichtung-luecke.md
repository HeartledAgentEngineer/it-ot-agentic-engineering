# Neuausrichtung: die 51 fehlenden Bilder sind geschlossen — und jetzt belegt (11.10.2026)

## Anlass

Die Plandatei fuehrte seit dem 10.10. einen offenen Punkt unter
„Was offen/unbekannt bleibt": *„51 Bilder aus `gedreht_plan.json` fehlen in
`_gedreht_neu` (vermutet: ohne Gesicht) — pruefen."* Die Stufe „Neuausrichtung"
(neu gedrehte und neu erkannte Bilder) stand in **keinem** Nachweis.

## Der Befund — die Vermutung war falsch, gemessen ist es eine Groessengrenze

- Gemessen (nur lesend): `gedreht_plan.json` = **2.373** Kennungen,
  `personen_vektoren_gedreht_neu.jsonl` = **2.322** Zeilen → **51 fehlen**.
- Ueber die Plaene gemessen: **50 der 51 sind Fotos ab 8 MB** (kleinstes
  8.444.313 B, groesstes 14.345.978 B); das 51. ist ein Bild aus
  `sortierplan.json` ohne Groesse im Plan.
- **Ursache damit belegt:** der Erkennungslauf vom 09.10. 02:37 lief noch mit
  `KACHEL_MAX_BYTES = 8 * 1024 * 1024` und verwarf groessere Bilder **still**
  (`kachel_quelle` lieferte `None`; nur die Zahl „Loecher\" blieb uebrig). Das
  ist **dieselbe Ursache** wie bei Papas 24 Bildern (Journal 7, Fix vom 10.10.:
  `kachel_quelle(..., grund_zaehler=)` nennt den Grund und `--max-bytes` holt
  nach). Die Vermutung „ohne Gesicht\" ist **widerlegt**.

## Was geaendert wurde

1. **Luecke geschlossen (Daten, lokal + pCloud-lesend, kostenfrei).** Nachlauf
   ueber genau die 51 offenen Bilder mit groesserer Grenze:
   ```
   gesicht_erkennen.py --plan gedreht_plan.json \
       --vektoren personen_vektoren_gedreht_neu.jsonl \
       --max-bilder 9999 --fortsetzen --max-bytes 25165824 --schreiben
   ```
   Ergebnis: **51 geholt, 0 Loecher, 0 Fehler**, 51 Zeilen geschrieben
   (217 s; davon 23 ohne Gesicht, 18 mit GPS). Zweiter Lauf: **0 offen**
   (idempotent). Es wurden **keine Bilder an ein fremdes Modell** gegeben —
   die Erkennung laeuft lokal (venv_gesicht).
2. **`tools/foto_sortierung/bestand_pruefen.py`** prueft die Stufe jetzt selbst:
   neuer Abschnitt **„Rotierte Bilder (`gedreht_plan.json`)\"** mit
   „N Bilder, davon M mit neuer Vektorzeile (… %), ohne K\" und einer benannten
   Luecke, wenn Zeilen fehlen. Fehlt der Plan oder die Vektordatei, steht das
   ehrlich da (kein Wurf). Abschaltbar mit `gedreht_plan=None`. Der Plan traegt
   nur `fileid` (kein Name) — `plan_lesen` zaehlt ihn trotzdem.

## Belege

- `bestand_pruefen.py` am echten Bestand, Exit 0:
  `Rotierte Bilder (gedreht_plan.json): 2.373 Bilder, davon 2.373 mit neuer
  Vektorzeile (100,0 %), ohne 0` — die Luecke ist zu. Ergebnis weiterhin
  **4 Luecke(n)** (alle kosten- bzw. geraetebunden: 8 Fotos, 25 Videos,
  WhatsApp).
- Testdatei `backend/tests/test_bestand_und_handy_uebergabe.py`: **31 passed**
  (3 neue Tests — Abschnitt vorhanden und Luecke benannt; vollstaendig ohne
  Luecke; fehlender Plan/fehlende Vektordatei ehrlich und abschaltbar).
- Pruefbefehl (Gate): siehe Commit-Nachricht.

## Ehrlich offen

Die vier verbleibenden Luecken sind unveraendert kosten- bzw. geraetebunden:
8 Fotos ohne Beschreibung und 25 Videos ohne Gesichter-Lauf (bezahlte Netzaufrufe
= Sebastians Entscheidung), WhatsApp-Verdrahtung (Geraet), `eigene_orte.json`
(Privatorte). Nichts geloescht, kein Bild an ein fremdes Modell.
