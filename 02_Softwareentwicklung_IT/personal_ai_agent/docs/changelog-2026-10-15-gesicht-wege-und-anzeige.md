# Gesichtserkennung: Wege und Anzeige gemessen (15.10.2026)

**Anlass.** Auftrag „Gesichter im Detailbild bearbeiten" (Sebastian, 15.10.2026), Punkt 1:
Auf einem Familienfoto mit vier Personen wurde im Bearbeitungsmodus **ein einziges** Gesicht
eingerahmt. Darunter steht die Arbeitsanweisung „Zu klären **(belegt, nicht vermutet)**":
Mit welchen Einstellungen läuft die Erkennung am Handy, wo stehen sie, findet der PC auf
demselben Bild mehr Gesichter, und warum findet das Handy weniger?

**Vorgehen.** Neues Werkzeug `tools/foto_sortierung/gesicht_wege_messen.py` — **nur lesen**:
es liest Code als Text und die gespeicherte Gesichtsdatei Zeile für Zeile, **öffnet kein
Bild**, ruft **kein Netz** und **kein Modell** (keine Kosten), **schreibt nichts** und gibt
**keine Personennamen** aus. Vorher gab es für diese Frage kein Messinstrument; die Angaben
im Auftrag waren Vermutungen.

## Was gemessen wurde (wörtlich aus dem Lauf, Exit 0)

**1. Einstellungen beider Erkennungswege (aus dem Code, Datei:Zeile)**

| Weg | Score | NMS | TopK |
|---|---|---|---|
| Handy/Backend (`backend/face_infer.py`) | 0.6 (`:38`) | 0.3 (`:39`) | 5000 (`:40`) |
| PC, Gesichterlauf (`tools/foto_sortierung/gesicht_erkennen.py`) | 0.6 (`:163`) | 0.3 (`:164`) | 5000 (`:165`) |

Der Handy-Detektor wird mit `FaceDetectorYN.create(..., (320, 320), ...)` gebaut
(`face_infer.py:169`) — **aber diese Voreinstellung ist nicht die wirksame Größe**: direkt vor
der Detektion wird `det.setInputSize((w, h))` auf das **echte Bild** gesetzt
(`face_infer.py:259`); derselbe Weg gilt für den selbst gezeichneten Ausschnitt (`:218`). Der
PC macht es identisch (`gesicht_erkennen.py:396`).

**Befund 1:** Die naheliegende Vermutung „das Handy erkennt nur auf 320×320, deshalb findet es
weniger Gesichter" ist **widerlegt**. Score, NMS, TopK und der Bildraum sind in beiden Wegen
gleich; die Auflösung am Handy ist die des Originalbildes.

**2. Anzeige der Kästchen im Detailbild (aus dem Code, Datei:Zeile)**

| Stelle | Wo |
|---|---|
| Endpunkt | `GET /api/gruppen/bild-gesichter` (`backend/app/router/gruppen.py:138`) |
| Dienst, der die Kästchen auswählt | `gesichter_auf_bild` (`backend/app/services/gruppen_quiz.py:858`) |
| Filter, der Gesichter **verbirgt** | `gruppen_quiz.py:885–886` — ausgeschlossene Gesichter und Gruppen, die als „kenne ich nicht" markiert sind |
| Editor bekommt die **Liste** (Quiz) | `frontend/app.js:4179` |
| Editor bekommt genau **EINEN** Rahmen | `frontend/app.js:4205` — nur die Referenz-Nachbearbeitung (Katalog → Referenz → Rahmen) |

**Befund 2:** Der Einzelrahmen-Pfad (`app.js:4205`) ist Absicht und gehört zur
Referenz-Nachbearbeitung, nicht zum Quiz-Bild. Im Quiz bekommt der Editor die ganze Liste;
fehlende Kästchen entstehen also **nicht** durch eine Beschränkung auf ein Gesicht — sie
entstehen durch die Filter `:885–886` oder weil im Bestand für dieses Bild nur ein Gesicht
steht.

**3. Zahlen am gespeicherten Bestand** (`~/foto_sortierung/personen_gruppen/gesicht_zuordnung.jsonl`)

```
50.282 Gesichter auf 15.551 Bildern
Bilder mit genau einem Gesicht: 5.454 (35,1 %) · zwei: 3.427 · drei: 2.196
  · vier oder mehr: 4.474 · größtes Bild: 106 Gesichter
Rahmenbreite (px): Median 117,7 · 10 % 24,1 · 90 % 364,1
  · schmaler als 64 px: 16.406 (32,6 %) · schmaler als 32 px: 7.642
Score: Median 0,874 · unter 0,80: 14.272 (28,4 %)
ohne Gruppe: 19.452 · aus Videos: 16.966
```

**Befund 3:** „Nur ein Gesicht auf dem Bild" ist im Bestand **kein Ausreißer**: mehr als ein
Drittel aller Bilder trägt genau eines. Aus der Zahl der Kästchen allein lässt sich also
**nicht** schließen, dass die Erkennung etwas übersehen hat.

**4. Ein einzelnes Bild nachprüfbar** (`--bild <kennung>`)

```
Bild 108041949695: 7 Gesichter im Bestand · davon ohne Gruppe: 6
  Rahmenbreite: schmalste 53,4 px · breiteste 232,0 px · schmaler als 64 px: 1
  Von der Anzeige verborgene Gesichter: NICHT zählbar
  — die Filterlisten (ausgeschlossen, gruppen_quiz_stand) liegen nur am Handy
```

## Was ausdrücklich NICHT geändert wurde

Am Such-, Erkennungs- und Anzeigeweg wurde **nichts** gebaut oder umgestellt — dieser Schritt
misst nur. Die fehlenden Filterlisten werden **nicht** geschätzt: fehlen sie am PC, steht
„NICHT zählbar" im Bericht.

## Ehrlich offen

- **Die dritte Frage ist an diesem Bild noch nicht beantwortet.** Welches Familienfoto gemeint
  ist, ist nicht bekannt (Sebastians Verlauf und die Bilder liegen auf dem Handy bzw. in
  pCloud). Sobald seine Kennung bekannt ist, liefert ein Aufruf
  `… gesicht_wege_messen.py --bild <kennung>` in Sekunden, wie viele Gesichter im Bestand
  stehen und wie viele die Anzeige verbirgt. Der PC-Vergleich auf denselben Bilddaten braucht
  das Bild selbst (kostenfreier Lauf von `gesicht_erkennen.py`, kein Modell).
- **Warum weniger Gesichter gefunden werden, ist damit eingegrenzt, nicht erklärt:** die
  Einstellungen scheiden als Ursache aus; es bleiben der Bildinhalt (kleine Gesichter bei
  Gegenlicht/Drehung) und die Filter der Anzeige.

## Belege

- Werkzeug: `tools/foto_sortierung/gesicht_wege_messen.py`
- Tests: `backend/tests/test_gesicht_wege_messen.py` — **16 passed** (erfundene Mini-Dateien:
  Zählung je Bild, Rahmenbreiten, Scores, kaputte Zeile, fehlende Datei, verborgene Gesichter,
  „NICHT zählbar" ohne Filterlisten, kein Personenname im Bericht, keine Schreiböffnung im
  Werkzeug; die Einstellungen werden gegen den **echten** Code geprüft, inklusive Gegenprobe,
  dass ein anderer Score den Vergleich kippt)
- Messlauf am echten Bestand: **Exit 0**, die Zahlen oben stehen wörtlich in der Ausgabe
