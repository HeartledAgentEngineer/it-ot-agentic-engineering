# Changelog 25.09.2026 — Tastatur lässt die Kopfzeile stehen, Text wird auswählbar

## Warum

Zwei gemeldete Störungen am Handy (installierte Web-App, `display=standalone`):

1. **Topleiste verschwindet, wenn die Tastatur aufgeht.** Ursache im Code belegt:
   `#app { height: 100vh }` in `style.css`. Auf Android schrumpft beim Öffnen der
   Tastatur nur der **sichtbare** Ausschnitt (`visualViewport`) — das Layout bleibt
   100vh groß. Damit das Eingabefeld sichtbar wird, schiebt der Browser die Seite
   hoch; die Kopfzeile wandert mit aus dem Bild. Es gab keine Regel, die den Kopf
   abschaltet — die Ursache war die feste Höhe.
2. **Keine Textauswahl per langem Druck.** Es gab **keine einzige `user-select`-Regel**
   im Stylesheet; die Auswahl war allein per JavaScript unterbunden:
   `dom.messages.addEventListener('contextmenu', …)` rief auf **jedem** Blasentext
   `e.preventDefault()`. Genau dieser Aufruf verhindert auf Android die native Auswahl
   (Griffe, Lupe, Kopieren-Menü) — der lange Druck öffnete stattdessen nur das eigene
   Menü der App.

## Was

### 1. Kopfzeile bleibt sichtbar (Tastatur)

| Datei | Änderung |
|---|---|
| `frontend/style.css` | `#app`: `position: fixed`, `top: var(--vv-oben, 0px)`, `height: var(--vv-hoehe, 100dvh)` — **kein `height: 100vh` mehr** (im ganzen Stylesheet kein `100vh` mehr). `#chat-container`: `min-height: 0` + `-webkit-overflow-scrolling: touch` (Scrollcontainer ist die Nachrichtenliste; ohne `min-height: 0` kann ein Flex-Kind nicht unter seine Inhaltshöhe schrumpfen). `#header`: `position: sticky; top: 0; z-index: 200`. Blätter (`#model-sheet`, `#chat-sheet`, `#memory-sheet`, `#selbsttest-sheet`): `z-index` 50 → **900**, damit sie weiter **über** der Kopfzeile liegen (eigenes Kontextmenü bleibt bei 1000, Teil-Kopier-Leiste bei 1100). |
| `frontend/app.js` | Neu `huelleAnSichtbareHoehe()`: liest `visualViewport.height`/`offsetTop` und setzt daraus `--vv-hoehe`/`--vv-oben` auf `documentElement`. Auslöser: `visualViewport` `resize`+`scroll`, `window` `resize`+`orientationchange`, `focusin` (sofort) und `focusout` (150 ms Nachlauf — Android meldet die neue Höhe erst danach). Alle Auslöser laufen über **einen** `requestAnimationFrame` (`huelleNachziehen`), kein Dauerlauf, kein `setInterval`. War die Ansicht unten, bleibt sie unten (`isAtBottom()` → `scrollToBottom(true)`). **Rückfall** ohne `visualViewport`: die Variablen werden entfernt, CSS nutzt `100dvh`. |
| `frontend/index.html` | Viewport-Meta zusätzlich `interactive-widget=resizes-content` (Browser verkleinert das Layout selbst, statt die Seite hochzuschieben) — dort, wo das nicht unterstützt wird, greift die `visualViewport`-Brücke, ohne beides `dvh`. |

Der Kopf ist damit doppelt gesichert: sticky/fixed oben mit `z-index` **und** die Hülle
endet genau an der sichtbaren Kante (Eingabebereich bleibt über der Tastatur).

### 2. Langer Druck startet die native Auswahl

| Datei | Änderung |
|---|---|
| `frontend/style.css` | Neue Regel für `#chat-container, #messages, .message, .message-content, .gedanken-inhalt, .gedanken-kurz, .message-time`: `-webkit-user-select: text; user-select: text; -webkit-touch-callout: default`. Die Auswahl gilt bewusst für den **ganzen Verlauf** (nicht nur je Blase) — nur so läuft sie **über mehrere Nachrichten hinweg** und bricht nicht an einer Nachbargrenze ab. |
| `frontend/app.js` | Im `contextmenu`-Handler der Blasen: Ist das Ziel `.message-content, .gedanken-inhalt, .gedanken-kurz`, wird **kein `preventDefault()`** mehr gerufen und das eigene Menü geschlossen — der Browser übernimmt (Auswahl + sein Kopieren-Menü). Das eigene Menü (Nachricht kopieren / Teil auswählen / bearbeiten) bleibt für die **nicht auswählbaren** Teile der Zeile: Zeitstempel, Vorlese-Knopf, leere Fläche neben schmalen Blasen. |
| `frontend/app.js` | **Kurzer Tipp bleibt unverändert:** Gedanken-Blasen klappen weiter per Tipp auf/zu. Neu ist nur der Auswahl-Schutz: Läuft eine Auswahl (`!selection.isCollapsed`), ändert der Klick die Blase nicht und öffnet auch kein Bild-Vollbild — sonst wäre die gerade gestartete Auswahl sofort wieder weg. |

Die zwei erlaubten `user-select: none`-Stellen bleiben: das **Bild-Vollbild** und das
**eigene Popup-Menü** (dessen Beschriftungen sollen sich nicht markieren lassen) — beides
ist nicht der Chat-Verlauf.

### Cache-Bump

`app.js?v=20260925F` → **`?v=20260925G`**, `style.css?v=20260925E` → **`?v=20260925F`**.
Nachgezogen in `frontend/tests/test_sprachaufnahme.js` und `frontend/tests/test_selbsttest.js`.

## Belege (ausgeführt, nicht behauptet)

| Prüfung | Befehl | Ergebnis |
|---|---|---|
| Neuer Frontend-Test | `cd frontend && node tests/test_tastatur_und_textauswahl.js app.js` | **36 Prüfungen, alle grün, Exit 0** |
| Syntax | `cd frontend && node --check app.js` | OK, Exit 0 |
| Alle Frontend-Tests | `for f in tests/*.js; do node $f app.js; done` | **15 Dateien, alle Exit 0**, zusammen **480 OK-Zeilen** (davon 36 neu) |
| Gegenprobe (Test muss rot werden) | Mutationen im Scratch-Abbild: `user-select: none` im Blasenblock, `preventDefault`-Rückzug entfernt, `#app { height: 100vh }`, `#header` ohne sticky/z-index | **4× Exit 1** (1/4/2/1 rote Prüfungen) — die Zusicherungen greifen |
| Echter Browser (Edge headless, CDP, `file://`-Aufruf der echten `index.html`) | `node probe.js file:///…/frontend/index.html` (Skript außerhalb des Repos, Scratch) | `userSelect` berechnet **„text / text"**, Auswahl über zwei Nachrichten = **„ERSTE-NACHRICHT\n\nZWEITE-NACHRICHT"** (1 Range, beide Blasen); `#header` `position: sticky`, `z-index 200`, Oberkante **0 px**, sichtbar; `#app` `position: fixed`, Höhe **487 px = `visualViewport.height` = `window.innerHeight`**, `--vv-hoehe` von app.js gesetzt = **487px**; Seite selbst scrollt nicht (`documentElement.scrollTop = 0`), die Liste schon (`scrollHeight 3904 / clientHeight 307 / scrollTop 500`); mit nachgestellter Tastaturhöhe (`--vv-hoehe` = 55 % — dieselbe Variable, die der Code setzt): Kopfoberkante **0 px**, Kopf vollständig im sichtbaren Bereich, Eingabebereich unter der sichtbaren Kante |
| Backend (unangetastet, nur zur Kontrolle) | `cd backend && .venv/Scripts/python -m pytest tests/ -q` | **423 passed, 2 failed** — beide Fehler **außerhalb dieser Änderung**: `test_gedaechtnis_erklaeren.py::test_teilwort_findet_den_eintrag` rechnet mit `tage_bis == 38`, ist aber datumsabhängig (`assert 37 == 38`); `test_chat_endpoint.py::test_conv_code_mit_bild_delegiert_an_hermes_statt_vision` läuft **einzeln grün** (1 passed) — reihenfolge-/umgebungsabhängig. Backend-Dateien wurden hier nicht angefasst (parallele Änderungen an `backend/hermes_inbox_daemon.py` lagen schon im Arbeitsstand). |

**Nicht prüfbar in dieser Umgebung:** das echte Auf-/Zugehen der Android-Tastatur in der
installierten Web-App (kein ADB, kein Android-Gerät) und die tatsächliche native
Auswahl-Geste (langer Druck mit Griffen/Lupe). Beides ist hier über die Mechanik
nachgestellt: dieselbe CSS-Variable, die `visualViewport` im Ernstfall setzt, wurde im
echten Browser verkleinert (Kopf bleibt stehen), und die Auswahl wurde im echten Browser
über zwei Nachrichten gezogen (Text kommt vollständig an). `-webkit-touch-callout: default`
steht in der CSS-Regel; **Chromium meldet dafür keinen berechneten Wert** (die Eigenschaft
ist für WebKit/Safari relevant) — geprüft ist also nur, dass sie gesetzt ist.

## Unsicherheiten

* Auf Android Chrome verkleinert `interactive-widget=resizes-content` das Layout bereits;
  die `visualViewport`-Brücke setzt dann denselben Wert. Sollten beide Wege einmal
  gegeneinander laufen, ist der `visualViewport`-Wert der führende (er ist exakt).
* Zieht Sebastian die Auswahl bis an den oberen Rand, bleibt der Kopf sticky — er
  überdeckt dabei die obersten Pixel des Verlaufs (wie jede feste Kopfzeile).
* Das eigene Menü „Nachricht bearbeiten“ ist am Handy jetzt über den **Zeitstempel bzw.
  die Fläche neben der Blase** erreichbar (dort ist kein Text auswählbar), nicht mehr über
  den Text der Blase. Am Desktop (Rechtsklick) unverändert.
