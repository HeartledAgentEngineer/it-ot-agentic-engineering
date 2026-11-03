# Changelog 03.11.2026 — Alltagsprotokoll S6: Oberfläche

Plan: `.hermes/plans/alltagsprotokoll.md`, Schritt S6. Baut auf S2 bis S5 auf.

## Neu im Frontend

Über den Knopf 📝 in der Kopfzeile öffnet sich ein Blatt (`#alltag-sheet`, neue Datei `alltag.js`):

- **Sprechen** (großer Knopf) und **Tastatur**. Die Aufnahme läuft wie im Chat über
  AudioWorklet und `encodeWav`, dann über `/api/sprache/transkript` und schließlich
  `POST /api/alltag/eintrag`.
- **Rückfragen** gibt es nur für fehlende Felder, einzeln und in fester Reihenfolge
  (Stimmung, Anspannung, Gefühle, Aktivität). Jede lässt sich überspringen und wird per
  `PATCH` gespeichert:
  - Stimmung: fünf Wortknöpfe
  - Anspannung: Regler von 0 bis 100
  - Gefühle: Grundgefühle als Chips, dazu eigene Worte
  - Aktivität: freier Text
- **Schlaf-Schnellknöpfe**: Schlafen, Aufgewacht, Wach gelegen, Wieder eingeschlafen.
- **Tagesablauf** mit ◀ Datum ▶. Jede Zeile hat „Ergänzen/Ändern" und „Löschen" (mit
  Nachfrage). Darüber steht die Nacht der Uhr, falls vorhanden.
- Die Kopfzeile zeigt die offenen Stunden. Der Stand geht an die App, wenn
  `window.HeyAgentAlltag.standSetzen` vorhanden ist (vorbereitet für das Pop-up in S7).
- `?alltag=aufnahme` öffnet das Blatt direkt mit Mikrofon. Das ist der Einsprung für S7.
- Sicherheit:
  - kein `innerHTML`
  - eindeutige IDs
  - `alltag.js` steht in `FRONTEND_DATEIEN`
- Cache: `alltag.js?v=20261103C`, `style.css?v=20261103C`.

## Neu im Backend

- `POST /api/alltag/ereignis` mit `{ereignis}` legt einen Schlaf-Eintrag mit der Zeit
  „jetzt" und der Quelle `knopf` an. Dabei gibt es keinen Modellaufruf. Ein unbekanntes
  Ereignis ergibt 400.
- `GET /api/alltag/vorgaben` liefert Grundgefühle und Stimmungsstufen als Wort und Zahl.
  `alltag_struktur.STIMMUNG` ist dafür jetzt die eine Quelle.
- `alltag_rechnen.letzter_stand`: Haben zwei Einträge dieselbe Zeit, gewinnt der später
  erfasste (`erfasst_um`). Vorher gewann der erste. Zwei Knopfdrücke in derselben Minute
  zeigten deshalb den falschen Stand.

## Stolperstein

Der Datenstand-Test verbietet `position: fixed` im CSS nach `.datenstand`. Die Regel des
Blatts steht deshalb vor `.datenstand`, wie beim Wiederverbinden-Overlay.

## Prüfung

- Neu sind zwei Testdateien:
  - `frontend/tests/test_alltag.js` prüft die reinen Funktionen, die API-Aufrufe und die
    Verdrahtung.
  - `test_alltag_router_s6.py` hat 4 Tests.
- Neuer Test: `test_alltag_rechnen_s2.py::test_stand_bei_gleicher_zeit_gewinnt_der_spaeter_erfasste`
  (vorher rot).
- Browser-Vorschau mit 375 px im Dunkelmodus, mit erfundenen Einträgen:
  - Der Ablauf Tastatur → Eintragen → Stimmung → Anspannung → Gefühl ergab einen
    vollständigen Eintrag.
  - Die Gefühls-Chips zeigen die Auswahl (`aria-pressed`).
