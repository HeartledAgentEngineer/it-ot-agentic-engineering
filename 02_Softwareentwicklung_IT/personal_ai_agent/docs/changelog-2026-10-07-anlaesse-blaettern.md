# Änderungsprotokoll 07.10.2026 — Erzählen: zwischen Anlässen blättern, Zurück-Geste (#18)

Meldung Sebastian: „die Funktion, zwischen den Erzählungen oder Anlässen rechts und links zu
wechseln, geht noch nicht — ziehen wir wieder zurück zur Hauptansicht."

## Ursache

- In der Übersicht eines Anlasses gab es **kein** Blättern: Pfeiltasten und Wischen wirkten nur in
  der Einzelansicht (aufs Bild), gewischt wurde nur auf dem Großbild.
- Ein Wisch vom Bildschirmrand ist bei Android die **Zurück-Geste**. Die App-Hülle
  (`android/…/MainActivity.kt`) ruft dann `webView.goBack()`. Das Erzählen legte keine eigenen
  Verlaufseinträge an — Zurück verließ deshalb das ganze Blatt („zurück zur Hauptansicht").

## Änderung (`frontend/erzaehlen.js`, `index.html`, `style.css`)

- **Blättern zwischen Anlässen** in der Übersicht: Leiste `◀ Anlass 5 von 2.127 ▶` über dem Titel
  (`#erzaehl-anlass-nav`), Pfeiltasten ←/→, **Wischen über die ganze rechte Spalte** und die
  Sprachbefehle „weiter"/„zurück". In der Einzelansicht blättern dieselben Gesten wie bisher das
  Bild. Gemeinsamer Einstieg `blaettern(richtung)`.
- **Über die geladene Seite hinaus:** Am Ende der geladenen Liste (200 je Seite) lädt `▶` erst die
  nächste Seite nach und öffnet dann den nächsten Anlass.
- **Zurück-Geste geht eine Ebene hoch:** Blatt, Anlass und Einzelbild legen je einen
  Verlaufseintrag an (`history.pushState`); Zurück führt Einzelbild → Übersicht → Liste → zu.
  Anlass- und Bildwechsel legen **keinen** Eintrag an (Zurück führt zur Liste, nicht durch alle
  Anlässe). Die Knöpfe „← Ereignisse"/„← Alle Bilder" und Escape gehen denselben Weg; ✕ baut die
  eigenen Einträge ab. Veraltete Einträge heilen sich selbst (reine Funktion
  `erzaehlZurueckEntscheiden`: nie über die Grundseite hinaus).
- **Entwurf je Anlass:** Ein halbfertiger Text bleibt beim Anlass, an dem er getippt wurde, und ist
  beim Zurückblättern wieder da. Vorher wäre er nach einem Wechsel im Feld stehen geblieben und
  beim Speichern am **falschen** Anlass gelandet. Wird während des Speicherns weitergeblättert,
  bleibt das neue Feld unberührt; ein Diktat, das erst nach dem Wechsel fertig wird, landet im
  Entwurf des Anlasses, für den es gesprochen wurde.
- Der offene Anlass ist in der Liste markiert (`.erzaehl-row.aktiv`, am PC nebeneinander sichtbar).
- Kurzes Hereingleiten aus der Wischrichtung (entfällt bei „weniger Bewegung").
- Reine Funktionen: `_erzaehlZahl`, `erzaehlAnlassNav`, `erzaehlWischRichtung` (nur deutlich
  waagerechte Bewegungen ab 50 px — Scrollen blättert nie), `erzaehlZurueckEntscheiden`.
- CSS: `.erzaehl-diashow-spalte { touch-action: pan-y pinch-zoom; }` — senkrechtes Scrollen bleibt,
  waagerecht gehört der Geste. Jede neue `display`-Regel hat ihr `[hidden]`-Gegenstück.
- Cache-Bump: `erzaehlen.js?v=20261007B`, `style.css?v=20261007B`.

## Prüfung

- `frontend/tests/test_erzaehlen.js`: neuer Abschnitt 12 (Nachbarn/Zähler/Nachladen, Wischrichtung,
  Zurück-Entscheidung, Verdrahtung, Entwurf je Anlass, CSS) — alle Prüfungen grün.
- Prüfstand Edge headless, 375 px, echte Touch-Ereignisse (CDP `Input.dispatchTouchEvent`),
  Attrappe mit erfundenen Daten (450 Anlässe, Seiten à 200): **17 von 17** — Wischen links/rechts,
  senkrecht blättert nicht, Pfeiltaste, ◀ ▶ mit Entwurf, Einzelbild-Wischen bleibt beim Bild,
  dreimal `history.back()` (= Android-Zurück): Übersicht → Liste → zu, `▶` über die Seitengrenze
  (Anlass 201, Liste 400), Knopf „← Ereignisse" und ✕ bauen den Verlauf ab.
- `frontend/tests/test_foto_galerie.js`: Versionsabgleich auf `style.css?v=20261007B`.
- Prüfbefehl: siehe Commit.

## Offen

- Am Handy mit dem Finger nachprüfen (die Rand-Geste selbst lässt sich nur am Gerät auslösen).
