# Rahmen speichern: die Anzeige behauptet nur noch, was wirklich passiert (16.10.2026)

Schritt **A** zum Punkt 0 des Auftrags „Gesichtskorrektur im Detailbild“
(`.hermes/plans/2026-10-16_rahmeneditor-detailbild.md`, Schritte A0 → A → A2 → A3).
Der Server sagt seit **A0** ehrlich, ob die gespeicherte Referenz wirklich einen
neuen Vektor trägt (`vektor_erneuert` + `vektor_grund`, siehe
`changelog-2026-10-16-vektor-erneuert.md`). Bisher nutzte die Oberfläche diese
Angabe **nicht** — sie meldete in beiden Schreibwegen Erfolg, auch wenn der
Vektor alt geblieben war. Genau das war der belegte Feldbefund: „Rahmen
verschieben, speichern, Seite neu laden → die neue Position ist nicht im
Datenbestand“.

## Verhalten (nur die Anzeige, kein Schreibweg geändert)

Beide Meldungen stehen in **einer** Funktion: `speichereEditorRahmen`
(`frontend/app.js`), Text und Zustand an derselben Stelle.

- **Gesichter-/Referenzweg** (`refKontext` vorhanden → `POST
  /api/gesichter/referenzen/{name}/{ref_id}/bbox`): die Erfolgsmeldung
  „✓ Rahmen in der Referenz von … aktualisiert (neuer Vektor gespeichert,
  andere Referenzen bleiben).“ erscheint **nur** im Zweig
  `if (d.vektor_erneuert)`. Ist der Vektor alt geblieben, steht dort stattdessen
  „⚠️ Rahmen gemerkt, aber der Vektor blieb der alte: …“ samt dem Klartext-Grund
  aus `vektor_grund` (Engine antwortet nicht / Ausschnitt-Einbettung
  fehlgeschlagen / Referenz ohne Bildpfad / nicht angefordert).
  Der Rahmen selbst wird in beiden Fällen gespeichert — die Meldung sagt jetzt
  nur, **was** davon neu ist.
- **Gruppen-/Quizweg** (`person && pPfad` → `quizBeantwortenSilent` → `POST
  /api/gesichter/quiz/antwort` **ohne** `manuell_bbox` → `gesicht_quiz.
  beantworte_runde`): dieser Weg gibt **kein** `vektor_erneuert` zurück und kann
  die Frage gar nicht beantworten. Die frühere Behauptung „— Rahmen + Referenz
  gespeichert.“ ist deshalb **entfernt**; dort steht jetzt „✓ … übernommen …
  — Zuordnung gespeichert; ob ein neuer Vektor entstand, meldet dieser Weg
  nicht.“
- Unverändert: Fehlerzweige, Hinweis ohne Ziel-Person, die gespeicherten Daten
  und der Referenz-Endpunkt selbst. Kein Schreibweg, kein Endpunkt, kein Schema
  geändert.

## Tests

Neu: `frontend/tests/test_quiz_rahmen_referenz_ehrlich.js` (läuft im Prüfbefehl
über `backend/tests/test_frontend_node.py` mit). Er liest den **echten**
Quelltext und prüft:

- Gesichter-Weg: die echte Zeichenkette `✓ Rahmen in der Referenz von ` ist
  vorhanden, `if (d.vektor_erneuert)` und `d.vektor_grund` ebenso, und die
  Behauptung steht **hinter** dem Zustand (sie kann also nicht vorher
  behaupten).
- Gruppen-/Quiz-Weg: die alte Zeichenkette `— Rahmen + Referenz gespeichert.`
  und die Wendung `Referenz gespeichert` kommen im Code **nicht** mehr vor, die
  neue ehrliche Meldung schon.
- **Gegenprobe:** dieselbe Prüffunktion wird auf die **alte** Fassung
  angewandt und **muss** sie beanstanden (fehlender A0-Zustand + Referenz-
  Behauptung im Gruppenweg) — sonst wäre der Test grün, egal was im Code steht.
- Cache-Bump: `frontend/index.html` lädt `app.js` mit Muster `JJJJMMTT` +
  Buchstabe und **nicht** älter als `20261016C`.

`frontend/tests/test_foto_galerie.js` nagelte den Cache-Token als Literal fest
(`vApp === '20261016B'`) und wäre bei **jedem** berechtigten Bump rot geworden.
Der Token wird jetzt aus `index.html` gelesen, gegen das Muster geprüft und nur
noch „nicht älter als der letzte Pflicht-Bump“ verlangt; der Zweck (der Bump
passiert wirklich) bleibt erhalten.

## Cache

`app.js?v=20261016B` → **`?v=20261016C`** in `frontend/index.html` (ohne den
Bump sähe Sebastian am Handy die alte Datei).

## Grenzen

- Dieser Schritt macht die **Anzeige** ehrlich; er behebt **nicht**, dass der
  Quiz-/Gruppenweg den **erkannten** statt den **verschobenen** Rahmen speichert
  (`gesicht_quiz.py` `beantworte_runde`: `dom.get("bbox")`) und dass er den
  Zustand nicht meldet. Das sind die Schritte **A2** (kein Speichern ohne Ziel)
  und **A3** (Weg (b) ehrlich machen, dort mit Gegenprobe auf die gespeicherten
  Koordinaten) — beide weiterhin gesperrt, siehe Plan.
- Am PC nicht abnehmbar: die Wirkung im Feld zeigt sich erst am Gerät
  (Handy-Modus), weil die Geräte-Referenzen am PC nur eine leere Hülle sind.

## Nachtrag 16.10.2026, 10:5x — Schritt A2 ist gebaut

Der Satz „A2 bleibt gesperrt“ oben gilt nicht mehr: **A2** („kein Speichern ohne
Ziel“) ist umgesetzt, getestet, committet und gepusht — eigenes Dokument
`changelog-2026-10-16-rahmen-ziel-riegel.md`, Test
`frontend/tests/test_quiz_rahmen_ziel.js`, Cache-Bump auf `?v=20261016D`. Dieser
Schritt ändert **nur** die Oberfläche (`frontend/app.js`): der Speichern-Knopf
entsteht nur bei passendem Ziel, und ohne Ziel wird gar nichts gesendet. Der in
der ersten Fassung dieses Dokuments genannte Fehler (Quiz-Weg speichert den
**erkannten** statt den **verschobenen** Rahmen) bleibt offen und gehört zu
**A3**.

## Nachtrag 16.10.2026, 13:2x — A3 ist gebaut; zwei Sätze oben gelten so nicht mehr

- **„dieser Weg gibt kein `vektor_erneuert` zurück und kann die Frage gar nicht
  beantworten"** gilt nicht mehr: `beantworte_runde` meldet seit A3
  `referenz_geschrieben`, `rahmen_gespeichert` (`gesendet`/`erkannt`) und `grund`
  — und der Quiz-Weg speichert den **gesendeten** Rahmen (nicht mehr den des
  Detektors). Die Meldung lautet „✓ … übernommen … — der verschobene Rahmen liegt
  als Referenz im Datenbestand."
- **„behebt nicht, dass der Quiz-/Gruppenweg den erkannten statt den verschobenen
  Rahmen speichert"** ist damit erledigt (A3).
- Einzelheiten, Belege und Prüfläufe: `changelog-2026-10-16-gesendeter-rahmen.md`.
  Cache-Bump seit A3: `?v=20261016E`.
