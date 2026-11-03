# Alltagsprotokoll S14 — Wochenübersicht in der Oberfläche

**Datum:** 03.11.2026 · **Projekt:** `02_Softwareentwicklung_IT/personal_ai_agent`
**Plan:** `.hermes/plans/alltag-s14-woche.md` · **Zweig:** `feat/alltag-s14-woche` (Basis S12)

## Wunsch (Sebastian)

„Ich kann noch keine Wochenübersicht bis jetzt sehen." Die Woche gab es bisher nur über den
Chat (`alltag_abfragen`) — in der App selbst fehlte sie.

## Neu

**Backend** — `GET /api/alltag/woche?bis=JJJJ-MM-TT` (Standard: heute), registriert wie die
übrigen Routen der Gruppe:

- sieben Tage bis `bis`, je Tag `datum`, `wochentag` (Mo–So), `eintraege`, `stimmung` und
  `anspannung` als Tagesschnitt, `gefuehle` (nur Grundgefühle), `schlaf_min`, `einschlafen`,
  `aufwachen` der Nacht zum Tag (von der Uhr);
- `schnitt` über die Woche (Stimmung, Anspannung, Schlaf);
- `erkenntnisse`: die Zusammenhangstexte wie im Chat (Schlaf ↔ Stimmung, Einschlafzeit,
  Gefühle nach dem Schlaf, Schlafqualität, Tageszeit) — erst ab genug Tagen.
  **Nicht dabei: der Baustein „Wochentag"** — er verlangt je Wochentag mindestens zwei Tage
  (`MIN_TAGE_WOCHENTAG`), ein Fenster aus sieben aufeinanderfolgenden Tagen enthält jeden
  Wochentag aber genau einmal. Im Chat (beliebiger Zeitraum) bleibt er unverändert.

**Kern der Rechnung** ist eine neue reine Funktion `alltag_auswertung.woche(stunden, naechte, bis)`.
Sie löst aus dem Bestand `_naechte_je_tag` heraus: eine Nacht je Aufwachtag, überlappende
Uhr-Sitzungen zählen einmal (`_ohne_doppelte`), unterbrochene Nächte werden addiert
(`_nacht_zusammen`), Nickerchen zählen nicht. `_nacht_und_tag` nutzt dieselbe Funktion — keine
zweite Rechenlogik.

**Kein Freitext:** keine Tätigkeit, keine Originalworte, keine Namen. Kein Sprachmodell, alles
bleibt auf dem Gerät.

**Oberfläche** (`frontend/alltag.js`, `index.html`, `style.css`):

- unter dem Tagesablauf der Abschnitt „Woche": sieben antippbare Zeilen mit Wochentag + Datum,
  Stimmungsbalken, Schlafdauer und Anzahl Einträge;
- darunter die Schnittzeile und die Erkenntnisse; ohne genug Tage steht dort der ehrliche
  Hinweis „Zusammenhänge erscheinen ab 4 Tagen mit Stimmung und Uhr-Nacht.";
- die Woche endet am gewählten Tag und blättert mit ◀ ▶ mit (`zustand.wocheBis`);
- Antippen einer Zeile setzt den Tagesablauf auf diesen Tag und scrollt dorthin; die Woche
  bleibt dabei stehen;
- Aufbau ausschließlich über `createElement`/`textContent` (kein `innerHTML`), Balkenbreite als
  Prozentwert über eine reine Funktion `alltagStimmungProzent` (1 → 8 %, 5 → 100 %).

## Geändert

- `alltag_auswertung.py`: `_naechte_je_tag` aus `_nacht_und_tag` herausgezogen; neu `woche`,
  `WOCHE_TAGE`, `WOCHENTAGE_KURZ`.
- `router/alltag.py`: neu `GET /woche` — kaputtes `bis` ergibt **400**, ein Lesefehler eine
  ehrliche Meldung, **nie 500** (wie im Modul üblich, mit `logger.warning`).
- `index.html`: Abschnitt `#alltag-woche` mit `#alltag-woche-liste`, `#alltag-woche-schnitt`,
  `#alltag-woche-erkenntnisse`; Cache-Bump `style.css?v=20261103E`, `alltag.js?v=20261103F`.

## Bewusst nicht

Keine Diagramm-Bibliothek, kein Export, keine Monatsansicht (Entscheidung im Plan).
Der Wochen-PDF-Export aus dem Tagesprotokoll-Plan (T5) bleibt ein eigener Schritt.

## Tests

- `backend/tests/test_alltag_woche.py` (neu, 11 Testfunktionen): sieben Tage auch ohne Daten;
  Tag mit Stimmung, Grundgefühlen und Nacht; überlappende und unterbrochene Nächte plus
  Nickerchen; Schnitt über die Tage; kein Freitext in der Antwort; Erkenntnisse ab genug Tagen
  inklusive „kein Beweis"; Router (Daten, Standard heute, kaputtes Datum → 400);
  Nacht am Fensterrand (beginnt vor `von`, endet am ersten Fenstertag); der Baustein
  „Wochentag" taucht in der Woche nicht auf.
- `frontend/tests/test_alltag.js`: reine Funktionen (`alltagSchlafKurz`, `alltagStimmungProzent`,
  `alltagKomma`, `alltagWochenTagText`, `alltagWochenWerte`, `alltagWochenSchnittText`), die vier
  IDs in `index.html`, der Aufruf `/api/alltag/woche?bis=`, das Stehenbleiben der Woche und der
  Balken im Stil.

Nur erfundene Daten; die Tests schreiben in `tmp_path` (Umgebungsvariable
`ALLTAGSPROTOKOLL_PFAD`), nie in echte Einträge.

## Prüfrunde (03.11.2026)

Ergebnisprüfung durch Hermes (DeepSeek V4.1 Flash, `.hermes/pruefkreis/alltag-s14.md`):
Runde 1 **EINWAND** mit drei Befunden, alle eingearbeitet.

1. **mittel — „Wochentag" konnte in der Woche nie erscheinen, war aber als geliefert
   dokumentiert.** `wochentag_text` verlangt je Wochentag mindestens zwei Tage
   (`MIN_TAGE_WOCHENTAG`), das Wochenfenster enthält jeden Wochentag genau einmal. Der Aufruf
   ist aus `woche()` entfernt (der Baustein bleibt für den Chat unverändert), Plan, Changelog
   und Änderungsprotokoll sind richtiggestellt. Neuer Test
   `test_kein_wochentag_baustein_in_der_woche`.
2. **leicht — Fensterrand unbelegt.** Neuer Test `test_nacht_am_fensterrand_zaehlt_zum_ersten_tag`:
   eine Nacht, die vor `von` beginnt und am ersten Fenstertag endet, zählt zu diesem Tag
   (Zuordnung über das Ende).
3. **leicht — toter Pfadverweis im Master-Plan.** Korrigiert.

Die vier übrigen Fragen der Prüfung waren ohne Befund: Rechnung, verhaltensgleicher Refactor
von `_naechte_je_tag`, Datenschutz (nur Zahlen, Kürzel, Grundgefühle, kein Modellaufruf),
Router (400 statt 500, Schlüssel-Schutz) und Oberfläche (nur `createElement`/`textContent`,
Cache-Bump, IDs).
