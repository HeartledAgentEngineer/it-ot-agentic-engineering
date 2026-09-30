# Changelog 01.10.2026 (Nacht zum 01.10.) — Wecken-Overlay (Push-to-talk)

## Was gebaut wurde

Neu `frontend/wecken.js` (**216 Zeilen**): ein schwebender runder Knopf
`#wecken-btn` (72 px, unten rechts, feste Position) plus eine große
Zustandsanzeige `#wecken-status`. Ein Tipp löst die **bestehende** Aufnahme aus
— über einen Klick auf den vorhandenen Mikrofon-Knopf `#mic-btn`
(`index.html:122`), nicht über einen eigenen Audio- oder Netzweg. Der Zustand
(„bereit / hört zu / denkt nach / spricht") wird live aus `#mic-status`
gelesen (MutationObserver), also nicht erfunden, sondern aus derselben Quelle
wie die bestehende Anzeige. Doppel-Tipp-Schutz über 700 ms bzw. 3 s, weil
`app.js` `state.isRecording` erst nach `getUserMedia` umstellt — ohne den
Schutz hätte ein zweiter Tipp die Aufnahme sofort wieder gestoppt.

Neu `frontend/tests/test_wecken.js` (**268 Zeilen, 60 Prüfungen**).

Geändert `frontend/index.html` (332 → **336** Zeilen): Kopfkommentar und
Script-Tag `wecken.js?v=20260930D` (A–C waren am Tag schon vergeben, D ist der
nächste Buchstabe; das Skript lädt nach `app.js`).

## Warum

Sebastian will den Agenten am Handy mit einem großen Knopf bedienen, ohne dabei
einen Fremdanbieter für die Spracherkennung zu benutzen. Das dauerhafte Weckwort
(„Hey Agent") kommt später als Hörer-Dienst **in der Android-App**
(Spec `docs/spec-a1-android-hey-agent.md` §5.2, Issue #1) — dort offline mit
openWakeWord. Bis dahin ist der Overlay der bedienbare Zwischenschritt:
Mikrofon **nur** auf ausdrücklichen Klick, kein Dauer-Mithören, kein CDN, kein
Netz außer dem genehmigten Weg über OpenRouter.

## Beweis (frisch gefahren, 01.10.2026)

| Prüfung | Ergebnis |
|---|---|
| `node --check frontend/wecken.js` | keine Ausgabe, Exit 0 |
| `node frontend/tests/test_wecken.js` | „alle Prüfungen grün", Exit 0 |
| `node frontend/tests/test_vollbild_zoom.js` | „alle Prüfungen grün", Exit 0 |
| `pytest tests/test_datenschutz_waechter.py -q` (aus `backend/`) | 66 passed, Exit 0 |
| Prüfbefehl des Projekts (voller Lauf, Merge-Stand `253f389`) | 3269 passed, 1 skipped, Exit 0 |

Zeilenzahlen: `frontend/wecken.js` 216, `frontend/tests/test_wecken.js` 268,
`frontend/index.html` 336.

## Bewusst NICHT gemacht

- `frontend/app.js`, `frontend/style.css`, `frontend/sw.js` unangetastet (kein
  Eingriff in fremde Arbeit, kein Umbau der bestehenden Aufnahme).
- Kein Dauer-Mithören, kein Weckwort im Browser, kein Google, kein Fremdanbieter.
- Kein Test mit Netz: die Testreihe arbeitet mit einer DOM-Attrappe.

## Herkunft

Gebaut in einem abgetrennten Arbeitsgang (Subagent), von Hermes **nachgeprüft**:
Syntax, beide JS-Testreihen, Datenschutz-Wächter und Zeilenzahlen wurden selbst
gefahren, nicht aus dem Bericht des Subagenten übernommen.

## Offen

- Sichtprüfung am Handy durch Sebastian (Tipp auf den Knopf, Zustandsanzeige).
- Weckwort: Android-App, Spec A1c (Issue #1), Cloud bereitet den Dienst vor.
