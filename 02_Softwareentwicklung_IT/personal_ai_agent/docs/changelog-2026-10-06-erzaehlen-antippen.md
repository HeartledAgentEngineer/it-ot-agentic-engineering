# Änderungsprotokoll 06.10.2026 — Erzählen: Einträge lassen sich am Handy wieder öffnen

Meldung Sebastian: „Ich kann auf keinen Eintrag klicken, dann öffnet sich nichts." (📖 Erzählen,
Liste der Ereignisse und Fotobuch-Seiten).

## Ursache (gemessen, nicht vermutet)

Messung in der laufenden App am Handy über WebView-Debugging (adb, nur Maße und Zustände, keine
Inhalte):

- Server in Ordnung: Liste `GET /api/erzaehlen/ereignisse` → 200, Detail
  `GET /api/erzaehlen/ereignisse/{kennung}` → 200 (Fotobuch-Seite und Ereignis).
- Nach einem Antippen: `#erzaehl-liste-spalte` hatte `hidden = true`, wurde aber **voll angezeigt**
  (`display: flex`, 733 px hoch); `#erzaehl-diashow-spalte` war geöffnet, lag aber **20 px hoch**
  am unteren Rand.
- Grund: `.erzaehl-spalte { display: flex; }` (style.css) ist stärker als das `hidden`-Attribut.
  Am PC stehen die Spalten nebeneinander — dort fiel es nie auf; am Handy (untereinander) schob die
  Liste die Diashow aus dem Bild.

## Änderung

- `style.css`: `.erzaehl-spalte[hidden] { display: none; }` (wie bei den anderen Blättern).
  `style.css?v=20261006A`.
- `tests/test_erzaehlen.js`: Wächter für die Regel und für das Umschalten Liste → Diashow;
  Gegenprobe: am alten Stand wäre die Prüfung rot gewesen. `tests/test_foto_galerie.js`:
  Versionsabgleich.

## Prüfung

- Browser-Prüfstand in Handybreite (375 px, echter Code, Testdaten): vor dem Antippen Diashow
  `display: none`; echter Klick auf einen Eintrag → Liste weg, Diashow 677 px hoch, Zähler „1 / 3",
  Eingabefeld sichtbar; „← Ereignisse" führt zurück.
- Alle 25 Frontend-Testdateien Exit 0; Prüfbefehl über den Commit-Hook.
