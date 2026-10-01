# Änderungsprotokoll 01.10.2026 — Bildbeschreibungen auch für „Bilder & Videos" (`--plan`)

## Befund

`tools/foto_sortierung/bestand_pruefen.py` (am 01.10. von Sebastian gestartet) zeigte:
Beschreibungen für die Upload-Sammlung 6.806 von 6.809 Fotos, für **„Bilder & Videos" 0 von
10.771**. Ursache im Code: `bild_beschreiben.py` liest seine Bildliste ausschließlich aus
`sortierschluessel.csv` (Upload-Sammlung). Für „Bilder & Videos" gibt es nur den Sortierplan
`sortierplan_bildervideos.json` — dafür hatte das Werkzeug keinen Eingang. Der Nachtlauf
(Budget 2,00 USD, Kosten laut Datei 1,55 USD) hat also alles beschrieben, was er sehen konnte.

## Änderung

- **`bild_beschreiben.py --plan <sortierplan.json>`**: neue reine Funktion `plan_zeilen_lesen`
  liest `zuege[]` direkt — fileid ist bekannt (keine `listfolder`-Abfrage), Videos (Endung) und
  Einträge ohne fileid fallen raus, Doppelte ebenso. Datum: `jahr` aus dem Plan, Monat/Tag/Uhrzeit
  nur aus dem Dateinamen, wenn er ein zum Jahr passendes Datum trägt (sonst 0 — nichts geraten);
  Zeilen ohne Datum bleiben drin. Alles andere unverändert: Kontaktbögen, Kostenbremse
  (`--budget`), Idempotenz über fileid, nur anhängend, Ausgabe außerhalb des Repos.
- CSV-Weg (`--csv`) unverändert.

## Prüfung

- `backend/tests/test_bild_beschreiben.py` +3 Tests (Plan-Zeilen: nur Fotos mit Kennung, Datum aus
  dem Namen, nichts geraten; ganzer Lauf ohne Ordner-Abfrage und idempotent; fehlender Plan →
  Exit 2) — 41 passed.
- Kosten-Schätzung aus Hermes' Messung (640 px, 12 je Bogen, `google/gemini-2.5-flash`):
  0,000222 USD je Foto → 10.771 Fotos ≈ 2,39 USD; Lauf mit `--budget 2.60`.

## Lauf (Sebastian startet, Claude verarbeitet keine Fotos)

    backend\.venv\Scripts\python.exe tools\foto_sortierung\bild_beschreiben.py --plan "%USERPROFILE%\foto_sortierung\sortierplan_bildervideos.json" --kachel 640 --kacheln-pro-bogen 12 --spalten 4 --budget 2.60

Nachweis danach: `tools/foto_sortierung/bestand_pruefen.py` → Zeile „Beschreibungen" für
`sortierplan_bildervideos.json`.
