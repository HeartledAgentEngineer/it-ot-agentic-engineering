# Datenstand der Fotoquellen in der App (Gesamtplan T0)

18.10.2026, Hermes-Cron. **Der fertige Quellenstatus war gebaut, aber nirgends
sichtbar.** Der Gesamtplan-Abschnitt **T0** („Fotoquellen wirklich bis zum Handy
nachweisen", `backend/.hermes/plans/gesamtplan-foto-erinnerungen-2026-10-11.md`)
nennt als **Ergebnis für den Nutzer**: „Unter ‚Datenstand' eine Statuszeile pro
Quelle: `entpackt → Bildindex → Gesichtserkennung → Gruppenbestand → auf diesem
Handy`." Die Messung dazu steht seit dem 14.10. als Dienst
`backend/app/services/import_status.py` samt 19 eigenen Tests — sie hatte aber
**keine Route und keine Anzeige**: kein Modul in `backend/app` importiert sie
(gemessen per Suche über den ganzen Baum), der Auftrag nennt sie ausdrücklich
„für die **spätere** Appanzeige". Dieser Schritt holt sie in die Oberfläche und
ändert an der Messung selbst nichts.

## Was gemessen ist (Vorbefund, am Baum gemessen)

- `import_status.py` wird von **keiner** Stelle in `backend/app` benutzt (auch
  nicht von `main.py` oder einem Router); es gibt keine Route, keine Anzeige.
- Der Bericht ist vollständig: je Quelle die zehn Felder des Berichtsvertrags
  (`quelle_typ`, `gelesen_am`, `bilder_im_plan`, `bilder_im_index`,
  `bilder_mit_gesichtslauf`, `erkannte_gesichter`,
  `gesichter_im_gruppenbestand`, `offene_gruppen`, `spaeter_gruppen`,
  `handy_stand_geprueft`), dazu `gruppenbestand`, `fehlende_werte` und der
  Hinweis. Fehlender Messwert ist `None`, nicht `0`.
- **Laufzeit ist die eigentliche Frage:** eine volle Messung liest die Plan- und
  Vektordateien. Am PC gemessen (echter Bestand, nur lesend): **10,0 s**; danach
  aus dem Zwischenspeicher **0,000 s**. Auf dem Handy ist die Messung nur
  langsamer, deshalb ändert sie sich nicht.

## Was gebaut ist

1. **Zwischenspeicher** (`import_status.status_gecacht`): EIN gemessener Stand je
   Basis gilt `STANDARD_CACHE_SEKUNDEN` = 600 s; `neu=True` misst frisch,
   `ttl_sekunden=0` schaltet den Speicher ab. Der Schlüssel enthält Basis,
   Quellenliste, Index-/Zuordnungsdatei und `handy_geprueft` — ein anderer Wert
   ist ein anderer Stand. Der Zugriff ist mit `threading.Lock` geschützt (FastAPI
   bedient den Weg in einem Thread). Der gespeicherte Wert ist **derselbe**
   Bericht, den `status()` liefert.
2. **Route** `GET /api/datenstand/fotoquellen` (`backend/app/router/datenstand.py`,
   eingebunden in `main.py`): nur lesend, **Schutz wie beim Server-Protokoll** —
   das Gerät selbst (Loopback) darf immer, fremde Geräte nur über HTTPS.
   `?neu=true` misst frisch. Geliefert werden Bericht, `aus_cache`,
   `dauer_sekunden` (Dauer der Messung, die zu diesem Stand geführt hat) und
   `gemessen_sekunden`.
   **Entscheidung:** `handy_stand_geprueft` geht hier als **`true`** in den
   Bericht — läuft die Route, dann läuft der Server auf dem Gerät und liest
   dessen Dateien; die fünfte Station ist damit wirklich beantwortet und nicht
   geraten. Der Dienst selbst bleibt bei `None` (am PC nicht messbar).
3. **Anzeige** (`frontend/index.html`, `app.js`, `style.css`): Knopf
   **„Datenstand"** im Zustandsstreifen neben „Protokoll", zugeklappter Bereich
   `#datenstand` mit Kopfzeile (`Stand … · Messung … s · aus dem Speicher /
   gerade frisch gemessen`), einer Zeile je Quelle (lesbare Namen: Fotos,
   Bilder und Videos, Papas Album, Neuausrichtung, Fotobuch) und drei
   Zahlenzeilen, dazu Gruppenbestand und die Zahl der nicht gemessenen Werte.
   Knopf „Neu messen" misst ausdrücklich frisch. Cache `app.js?v=20261018O`,
   `style.css?v=20261018E`.
   **Bewusste Entscheidungen:** geschrieben wird mit `textContent`/
   `createElement` (nie `innerHTML`), keine Häkchen- oder Statussymbole
   (Sebastians Regel: Klartext), ein fehlender Wert heißt **„nicht gemessen"**
   statt `0`, und der Bereich steht **flach im Fluss** (kein Kasten über dem
   Chat — derselbe Grund wie bei Punkt 9).

## Belege (in diesem Lauf selbst ausgeführt)

- Neu `backend/tests/test_datenstand_fotoquellen.py` — **11 Tests**: Zwischenspeicher
  (erster Aufruf misst, zweiter liefert aus dem Speicher; `neu` misst frisch;
  `ttl_sekunden=0` schaltet ab; verschiedene Basen teilen sich nichts; ein
  anderer `handy_geprueft`-Wert ist ein anderer Stand), Route (Gerät selbst ohne
  Anmeldung 200 mit vollständigem Bericht; fremd ohne Schlüssel 401, fremd über
  HTTP 403, fremd über HTTPS 200; `?neu=true` kommt an; fehlende Werte bleiben
  `null`), Bericht ohne Pfad/Dateiname/Vektor, Oberfläche (Knopf/Bereich/Route
  verdrahtet, reine Textfunktionen ohne DOM und ohne `innerHTML`, keine Symbole).
  Zusammen mit dem bestehenden `test_import_status.py`: **30 passed**.
- Neu `frontend/tests/test_datenstand.js` — **Exit 0, 45 Prüfungen** (Zahlen
  deutsch mit Tausenderpunkt, `null`/`undefined`/Text/`NaN` = „nicht gemessen",
  Kopfzeile mit Stand/Dauer/Herkunft, vier Zeilen je Quelle, Kürzung bei mehr als
  sechs fehlenden Werten, Unsinn in der Liste wirft nicht, keine Symbole,
  Verdrahtung in `index.html`/`app.js`/`style.css`).
- **Gegenprobe gegen den HEAD-Stand** (Kopie von `app.js` außerhalb des Repos,
  dieselbe Prüfdatei): **Exit 1**, „Namenstabelle nicht gefunden:
  DATENSTAND_QUELLEN_NAMEN" — die Fähigkeit gab es vorher nachweislich nicht.
- **Rendermessung im echten Browser** (Edge headless, echte `index.html` +
  `style.css` + `app.js`, gestellte Antworten; Skript außerhalb des Repos) bei
  **1400 px und 380 px**: zugeklappt → Klick → offen (aria-expanded `true`),
  **14** Zeilen sichtbar (3 Quellen à 4, Gruppenbestand, fehlende Werte);
  1400 px Liste 758 × 272 px, 380 px 340 × 341 px, eigener Rollbereich
  (`overflow auto`, `max-height 360px`), Dokument-Überlauf **0**, kein
  überbreites Element, **keine Überlappung** mit dem Chat, beide Knöpfe im
  Fenster; zweiter Klick → wieder zu. **Und der Weg selbst belegt:** die
  Anfragen lauten nacheinander `/api/datenstand/fotoquellen` und
  `/api/datenstand/fotoquellen?neu=true`; die Kopfzeile wechselt von „aus dem
  Speicher" zu „gerade frisch gemessen".
- **Messung am echten Bestand** (nur lesend, am PC): volle Messung **10,0 s**,
  zweiter Aufruf **aus dem Speicher 0,000 s**; Zahlen je Quelle (Plan / Index /
  Gesichtslauf / Gesichter / im Gruppenbestand): **7.616 / 7.613 / 7.530 /
  20.060 / 6.522** (Fotos), **11.630 / 10.766 / 11.310 / 29.439 / 9.974**
  (Bilder und Videos), **6.336 / 6.336 / 6.336 / 23.246 / 13.048** (Papas
  Album), **2.373 / 2.373 / 2.373 / 4.526 / 1.020** (Neuausrichtung),
  **842 / 840 / 839 / 2.606 / 1.286** (Fotobuch); Gruppenbestand **1.367
  Gruppen, 18 benannt, 30.830 Gesichter**; **keine** fehlenden Werte (am PC
  liegen alle Dateien).

## Ehrliche Grenzen

- **Auf dem Handy fehlen Plan- und Vektordateien auf jedem Übergabeweg** (der
  Nachweis meldet das als eigene Lücke: elf Dateien, die ein Dienst liest und die
  auf keiner Liste stehen). Die Anzeige sagt dort ehrlich **„nicht gemessen"** —
  genau das ist die Antwort auf T0s Frage und der sichtbare Beleg für den
  fehlenden Übergabeweg. **Der Übergabeweg selbst wurde hier bewusst nicht
  geändert** (250 MB an Plan- und Vektordateien in die pCloud; das ist ein eigener
  Schritt mit eigener Entscheidung).
- Die Werte sind **Summen je Quelle** und dürfen **nicht** über die Quellen
  addiert werden (eine Quelle kann Gruppen bilden oder ergänzen) — steht so im
  Hinweis der Anzeige.
- Der **Knopfdruck mit dem Finger am Gerät** bleibt Sebastians Abnahme; gemessen
  ist der Weg am PC im echten Browser, nicht am Handy.
- Der Zwischenspeicher ist **prozessweit** (kein Neustart, kein neues Messen bei
  einem Datenwechsel); „Neu messen" ist der ausdrückliche Weg dazu. Kein
  Verzeichnis-/Dauerhaftigkeitsversprechen.

## Dokumentation

Neu diese Datei; nachgezogen: `.hermes/plans/2026-10-16_todo-naechste-stunden.md`
(eigener Punkt) und das Journal des Nachtlaufs
(`.hermes/plans/2026-10-10_nachtlauf-papas-fotos-und-chat.md`).
