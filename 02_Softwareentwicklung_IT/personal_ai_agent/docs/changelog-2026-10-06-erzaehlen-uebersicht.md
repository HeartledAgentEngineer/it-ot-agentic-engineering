# Änderungsprotokoll 06.10.2026 — Erzählen: erst alle Bilder, dann einzeln

Wunsch Sebastian (am Handy, direkt nach dem Fix „Einträge lassen sich wieder öffnen"): von jeder
Gruppe erst **alle Bilder auf einmal** sehen, **zur ganzen Gruppe** etwas erzählen und **zu jedem
einzelnen Bild** per extra Antippen.

## Ausgangslage

- Das Backend konnte das schon: `POST /api/erzaehlen/geschichten` ohne `datei_kennung` speichert
  eine Geschichte zum ganzen Ereignis (`erzaehl_service.geschichte_speichern`), die Detailantwort
  liefert sie mit `datei_kennung: null`.
- Die Oberfläche öffnete ein Ereignis aber direkt als Diashow (ein Bild) und schickte **immer** die
  Kennung des gerade gezeigten Bildes mit — eine Geschichte zur ganzen Gruppe war nicht möglich.

## Änderung (nur Frontend, Backend unverändert)

- **Übersicht** (`#erzaehl-uebersicht`): Antippen eines Ereignisses zeigt zuerst alle Bilder als
  Raster (am Handy 3 je Zeile, am PC so viele, wie passen), darüber „N Bilder · Antippen öffnet
  ein Bild einzeln" und die Geschichten **zur ganzen Gruppe**. Kacheln mit eigener Geschichte
  tragen „✎ n". Das Eingabefeld (mit 🎤 und 💾) klebt unten und speichert hier **ohne** Bild —
  also zur ganzen Gruppe.
- **Einzelansicht** (`#erzaehl-einzel`): Antippen einer Kachel öffnet das Bild groß mit ◀ ▶,
  Wischen und Zähler wie bisher; darunter „Zu diesem Bild" und „Zur ganzen Gruppe". Das Feld
  speichert hier **mit** Bild. „← Alle Bilder" (auch Esc) führt zur Übersicht zurück, an dieselbe
  Scrollstelle.
- **Kein Verrutschen von Text:** halbfertiger Text bleibt je Ansicht stehen — ein angefangener
  Gruppen-Text landet nicht am Bild, das man zwischendurch öffnet (und umgekehrt).
- **Laden schonend:** Kacheln (`480x480` über `/api/cloud/thumb`) laden erst, wenn sie ins Bild
  scrollen (IntersectionObserver), höchstens vier zugleich. Ihre Objekt-URLs werden beim Verlassen
  der Gruppe freigegeben; die Einzelansicht gibt wie bisher ihr Großbild bei jedem Wechsel frei.
- Blättern (◀ ▶, Pfeiltasten, Sprachbefehle „weiter"/„zurück") wirkt nur in der Einzelansicht.
- Neue reine Funktionen in `frontend/erzaehlen.js`: `erzaehlGeschichteKoerper` (Rumpf für das
  Speichern, ohne Bild = Gruppe) und `erzaehlGeschichtenJeBild` (Zähler für das ✎).
- CSS: jede neue Regel mit `display` hat ihr `[hidden]`-Gegenstück (`.erzaehl-uebersicht`,
  `.erzaehl-einzel`, `.erzaehl-back`) — Lehre aus dem Fehler vom selben Tag
  (`changelog-2026-10-06-erzaehlen-antippen.md`).
- Cache-Bump: `style.css?v=20261006B`, `erzaehlen.js?v=20261006A`.

## Prüfung

- `frontend/tests/test_erzaehlen.js`: neue Abschnitte 6–8 (reine Funktionen, Verdrahtung,
  `[hidden]`-Regeln), alle Prüfungen grün; alle 25 Frontend-Testdateien Exit 0.
- Prüfstand im Edge headless mit dem echten Frontend-Code und einer Backend-Attrappe (erfundenes
  Ereignis, 30 farbige Testbilder, keine privaten Daten):
  - Handybreite 375 px: Liste aus, Übersicht mit 30 Kacheln; nach 2,5 s 15 Kacheln geladen
    (nur die sichtbaren plus Vorlauf), nach dem Herunterscrollen 30; Eingabe-Fuß bündig unten
    (791 px = Spaltenende).
  - Kachel 3 antippen → Einzelansicht „3 / 30", Bild sichtbar, „Zu diesem Bild" + „Zur ganzen
    Gruppe"; ▶ → „4 / 30", ◀ → „3 / 30".
  - Speichern in der Einzelansicht → Rumpf mit `datei_kennung: 1003`; zurück zur Übersicht →
    Kachel 3 zeigt „✎ 2", alle 30 Kacheln noch geladen; Speichern in der Übersicht → Rumpf
    **ohne** `datei_kennung`, erscheint unter „Zur ganzen Gruppe".
  - Entwurf: „halbfertig Bild" steht in der Übersicht nicht im Feld, beim erneuten Öffnen des
    Bildes wieder da. Pfeiltaste in der Übersicht ohne Wirkung. „← Ereignisse" → Liste, Kacheln
    freigegeben (0).
  - Desktop 1280 px: Liste links, Raster mit 8 Spalten rechts, alle Abläufe wie oben.
- Prüfbefehl: siehe Commit.
