# Changelog 03.11.2026 — Beschreibungen für Video-Standbilder (F6)

## Befund

Bilder aus Videos (Standbilder) hatten keine Beschreibung: weder was zu sehen ist noch was
gesagt wird.

## Ursache

`bild_beschreiben.py` kannte zwei Eingänge, die CSV und den Sortierplan. Beide lassen Videos aus.
Die Standbilder liegen aber mit eigener fileid in pCloud (`video_standbilder.jsonl`). Sie kamen
so in keinen Lauf. Das Handy sucht Beschreibungen je fileid und hätte sie sofort gezeigt.

## Behoben (Bild)

- Neuer Eingang `--standbilder <video_standbilder.jsonl>`. Er schließt sich mit `--plan` aus.
- `standbild_zeilen_lesen`: Pro `standbild_fileid` entsteht genau eine Zeile mit dem Namen
  `standbild_<video_id>_<zeit>.jpg` im Ordner `video-standbilder`. Die Karte trägt kein
  Datum, also wird keins geraten. Doppelte, unlesbare Zeilen und Zeilen ohne Standbild werden
  gezählt und ausgelassen.
- Die fileids sind bekannt, deshalb gibt es keine Ordner-Abfrage. Ein zweiter Lauf schickt
  nichts mehr (Abgleich über die fileid).

## Lauf am PC (kostet Geld, Budget-Bremse greift)

```powershell
cd "C:\Users\sebas\Desktop\workspace agentic engineering\02_Softwareentwicklung_IT\personal_ai_agent"
& backend\.venv\Scripts\python.exe tools\foto_sortierung\bild_beschreiben.py --standbilder "$HOME\foto_sortierung\personen_gruppen\video_standbilder.jsonl" --nur-liste
& backend\.venv\Scripts\python.exe tools\foto_sortierung\bild_beschreiben.py --standbilder "$HOME\foto_sortierung\personen_gruppen\video_standbilder.jsonl" --prompt-variante bildgeschichte --jsonl "$HOME\foto_sortierung\bild_beschreibungen_reich.jsonl"
```

Zuerst `--nur-liste`: Sie zeigt die Zahl der offenen Standbilder, ohne Netz.

## Offen

- **Gesprochenes:** Was in einem Video gesagt wird, steht in keinem Standbild. Dafür braucht es
  einen eigenen Weg (Tonspur → Transkript je Video). Das ist ein eigener Folgeschritt.

## Prüfung

- Neu in `test_bild_beschreiben.py` (5): Zeilen aus der Karte, Lauf und Wiederholung,
  Nur-Liste ohne Netz, fehlende Karte, `--plan` und `--standbilder` zusammen.
  Vorher 4 rot, jetzt 60 grün.
