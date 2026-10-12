# 12.10.2026: App gegen Zugriff von außen absichern (P0)

Plan: `.hermes/plans/2026-10-12_p0-sicherheit-app.md` (Workspace-Wurzel, nicht im Repo),
Fassung 5. Planprüfung: Hermes (DeepSeek v4.1 Flash), fünf Runden, Runde 5 „FREI“
(Sitzung `20261012_181837_3953c2`). Codex und Astra entfallen für P0 auf Sebastians
Entscheidung (ChatGPT-Abo im Limit); die Ergebnisprüfung macht Hermes in einer frischen
Sitzung.

P0 kommt in zwei Commits. Dieser Eintrag beschreibt **Teil 1: Skript-Einschleusung über
Antworten (XSS) und Frontend-Tests im Prüfbefehl**. Teil 2 (Herkunftsprüfung, Host-Liste,
CORS, Schlüssel im HTML statt `/api/konfig`, Sicherheitskopfzeilen, Positivliste,
`hermes_status`, Service Worker, Termux-Skripte) folgt als eigener Abschnitt.

## Warum

Befund B5 (gemessen am 12.10. mit dem echten Quelltext, `p0-belege/xss_probe.js`):

- `parseMarkdown` setzte Modellantworten **unmaskiert** in `innerHTML`. Ein
  `<img src=x onerror=…>` in einer Antwort lief als Skript. Weil das Frontend den
  API-Schlüssel kennt, hätte ein solches Skript ihn abgreifen und alle Daten lesen können.
  Der Weg dorthin ist kurz: Webseiten, Chat-Archive und Bildtexte gelangen über Werkzeuge in
  die Antworten (Prompt-Injection).
- `escapeHtml` maskierte keine Anführungszeichen. Ein Link wie
  `[x](https://a"onmouseover=…)` brach aus dem `href`-Attribut aus.
- Über den `localStorage`-Eintrag `api_base` ließ sich die Backend-Adresse umbiegen. Ein
  eingeschleustes Skript hätte damit alle Anfragen samt Schlüssel an einen fremden Server
  schicken können.
- Die 27 Frontend-Tests liefen nur von Hand. Ein Umbau an `app.js` konnte sie brechen,
  ohne dass der Prüfbefehl rot wurde.

## Was geändert wurde (Teil 1)

1. **`escapeHtml`** (`frontend/app.js`) ist ein reiner Zeichenersatz für `& < > " '`, ohne
   DOM. Damit taugt die Funktion auch für Attributwerte. Eine zusätzliche Hilfsfunktion gibt
   es bewusst nicht, weil `test_diff_darstellung.js` die Funktionen wörtlich ausschneidet.
2. **`parseMarkdown`** maskiert alles außer Codeblöcken, **bevor** daraus HTML entsteht:
   - Zuerst werden die Codeblöcke geparkt. `codeBlockZuHtml` maskiert sie selbst.
   - Dann wird der ganze übrige Text maskiert.
   - Erst danach entstehen Tabellen, Fett, Kursiv, Code, Links, Listen und Absätze.
   - Das Nullzeichen (der Platzhalter-Rand) wird aus der Eingabe entfernt, damit kein Text
     einen Platzhalter fälschen kann.
3. **`inlineMarkdown`** erwartet maskierten Text. Eine URL endet an jeder Entität außer
   `&amp;`. Ein maskiertes `"` oder `'` kann so nie in ein `href` geraten.
   - Roh-URL: `(?:[^\s&\u0000]|&amp;)+`. Die Klasse erlaubt `)`, damit Wiki-Links wie
     `…/X_(Y)` heil bleiben.
   - Markdown-Link: `(?:[^\s&)\u0000]|&amp;)+`. Hier schließt `)` die Adresse ab.
   - Links bleiben auf `http(s)` beschränkt; `javascript:` wird nie ein Link.
   - Wer `&lt;` wörtlich tippt, bekommt `&amp;lt;` in der URL. Das ist eine treue Wiedergabe
     und keine Lücke.
4. **Weitere Senken (P0.7):**
   - Die zwei Rückfallzweige ohne `parseMarkdownPartial` maskieren mit `escapeHtml`.
   - Die Nachrichtenzahl in der Gesprächsliste steht als Zahl im HTML
     (`Number(c.message_count) || 0`).
   - Der Knopf „Tab jetzt schließen“ im Abschalt-Bild hat kein `onclick`-Attribut mehr,
     sondern einen `addEventListener`. Die Inhaltsrichtlinie aus Teil 2 sperrt Inline-Skripte.
5. **Backend-Adresse:** `app.js`, `erzaehlen.js` und `gruppen_quiz.js` nehmen immer
   `location.origin`.
   - `app.js` löscht einen alten `api_base`-Eintrag beim Start.
   - Der Name `API_BASE` bleibt, weil Tests ihn prüfen.
   - Der Kommentar mit der Beispiel-IP ist entfernt.
6. **Cache-Kennungen:** `app.js`, `erzaehlen.js` und `gruppen_quiz.js` stehen auf
   `?v=20261012A`.

## Tests

- **Neu `backend/tests/test_frontend_node.py`:** Alle `frontend/tests/test_*.js` laufen jetzt
  im Prüfbefehl, je Datei ein Testfall, im Ordner `frontend/`.
  - Zuordnung der Argumente: `test_erzaehlen.js` → `erzaehlen.js`, `test_gruppen_quiz.js` →
    `gruppen_quiz.js`, `test_wecken.js` → `wecken.js`, alle übrigen → `app.js`.
  - Ein Wächter prüft, dass mindestens 27 Tests gefunden werden und jede Zuordnung auf
    vorhandene Dateien zeigt.
  - Fehlt `node`, werden die Tests übersprungen. Der Grund im Bericht lautet
    „Frontend-Tests NICHT verifiziert: node fehlt“.
  - Grundlinie vor dem Umbau: 28 passed (27 Frontend-Tests + Wächter).
- **Neu `frontend/tests/test_markdown_sicherheit.js`** (gegen den echten Quelltext, ohne
  DOM):
  - Diese Eingaben werden **nicht** zu HTML: `<img onerror>`, `<script>`, ein Ausbruch aus
    einem Link-Attribut (Markdown-Link und Roh-URL, mit `"` und `'`), ein
    `javascript:`-Link, HTML in einer Tabellenzelle, ein gefälschter Platzhalter, HTML in
    einem offenen Codeblock (Stream) und in einem geschlossenen.
  - Gegenprobe: Fett, Kursiv, Code, Liste, Tabelle, Diff, Markdown-Link, `?a=1&b=2`,
    `x.de's`, eine URL mit Klammern und eine `www.`-Adresse funktionieren weiter.
  - Die P0.7-Stellen sind als Quelltextmuster abgesichert.
  - Gegen die alte `app.js` ist der Test rot (Exit 1).
- **Wächter `backend/tests/test_datenschutz_waechter.py`:**
  - `test_regel_frontend_urls_nur_lokal` (vorher `…_oder_api_base`) kennt keine Ausnahme
    mehr.
  - `test_regel_frontend_app_js_hat_api_base_zeile` ist ersetzt durch zwei neue Regeln:
    `test_regel_frontend_liest_kein_api_base` (keine der drei Dateien liest
    `getItem('api_base')`) und `test_regel_frontend_app_js_raeumt_api_base_auf`.
- **Versionsprüfungen nachgezogen:**
  - `test_foto_galerie.js` und `test_erzaehlen.js` prüfen genau die neue Kennung.
  - `test_gruppen_quiz.js` und `test_vollbild_marke.js` prüfen jetzt „diese Fassung oder
    neuer“. Vorher brach jede Erhöhung der Kennung diese beiden Tests.

**Prüfbefehl** (`cd backend && .venv/Scripts/python -m pytest tests/ -q`):
**3969 passed, 2 skipped, Exit 0** (373,89 s). Darin stecken die 29 Fälle aus
`test_frontend_node.py` (28 Frontend-Tests und der Wächter). Während des Laufs liefen zwei fremde
Gesamtläufe im selben Arbeitsbaum parallel; der Lauf blieb trotzdem grün.

## Teil 2: Herkunft, Host, Schlüssel im HTML

### Warum

Befunde B1–B4 (Plan, Fassung 5):

- **B1:** `/api/konfig` gab den Schlüssel ohne Prüfung als Skript heraus. Jede Webseite
  konnte ihn mit `<script src="http://127.0.0.1:8080/api/konfig">` abholen, und jedes Gerät
  im selben WLAN mit einem einfachen Abruf.
- **B2:** CORS stand auf `*` mit Zugangsdaten.
- **B3:** Der Server prüfte den `Host`-Kopf nicht. Über DNS-Rebinding hätte eine fremde Seite
  unter eigenem Namen mit dem Server sprechen können.
- **B4:** Es gab keine Sicherheitskopfzeilen (CSP, Rahmen, Sniffing).

### Was geändert wurde

1. **Neu `backend/app/sicherheit.py`** (242 Zeilen) mit einer reinen ASGI-Middleware
   `SicherheitsMiddleware`. Sie puffert nichts, Streaming bleibt also unberührt.
   - **Host-Prüfung auf allen Pfaden:** Erlaubt sind `localhost`, IP-Adressen und die Namen
     aus `ERLAUBTE_HOSTS` (Komma-Liste, z. B. der Tailscale-Name). Andere Hosts bekommen 400.
   - **Herkunftsprüfung** für `/api/*`, `/health`, `/ping`, `/status`: Bei
     `Sec-Fetch-Site: cross-site` oder `same-site` oder einem fremden `Origin` antwortet der
     Server mit 403. Die eigene Herkunft ergibt sich aus Schema und geprüftem Host.
     Ausnahmen gibt es nur über `CORS_HERKUNFT`.
   - Jede Abweisung wird mit ihrem Grund gezählt (`host`, `cross-site`, `same-site`,
     `origin`) und geloggt, ohne Kopfzeilen-Inhalte.
   - **Sicherheitskopfzeilen** an jeder Antwort:
     - eine CSP ohne Inline-Skripte (Stile dürfen inline bleiben);
     - `nosniff`, `no-referrer`, `X-Frame-Options: DENY`,
       `Cross-Origin-Resource-Policy: same-origin`.
2. **Schlüssel im HTML statt `/api/konfig`:**
   - `index.html` und `hermes_status.html` tragen ein leeres Meta-Feld `agent-schluessel`.
     Der Server setzt den Schlüssel beim Ausliefern ein (maskiert, `html.escape`).
   - `/api/konfig` ist entfernt.
   - Die Dokumentations-Seiten (`/docs`, `/redoc`, `/openapi.json`) sind abgeschaltet.
3. **Positivliste für statische Dateien:**
   - Ausgeliefert werden nur die zwölf Dateien aus `FRONTEND_DATEIEN`. `/` liefert
     `index.html`, alles andere 404.
   - Verglichen wird über `realpath` und `normcase`. Damit kommen weder Test-Dateien noch
     Sicherungen (`*.bak`) noch Pfade mit `..` oder anderer Schreibweise durch.
4. **CORS:** Ohne `CORS_HERKUNFT` gibt es keine CORS-Middleware mehr. Mit dem Eintrag gilt
   nur diese Liste, ohne `*` und ohne Zugangsdaten. Die Änderung wirkt nach einem Neustart.
5. **Schlüsselvergleich** in `router/auth.py` mit `hmac.compare_digest` (zeitkonstant).
6. **Selbsttest:** Das neue Feld `abgewiesen` zählt die Abweisungen seit dem Start je Grund.
   Die App zeigt es als Zeile „Abgewiesen seit Start“.
7. **`hermes_status.html`:**
   - Das Inline-Skript ist nach `hermes_status.js` umgezogen, weil die CSP Inline-Skripte
     sperrt. Ausgabe nur über `textContent`; Klassen nur aus einer festen Liste.
   - **Abweichung vom Plan:** Der Stilblock bleibt inline, weil die CSP Stile erlaubt.
8. **Service Worker v18:**
   - `/` und `/index.html` stehen nicht mehr in der Vorab-Liste.
   - HTML kommt nur ohne Schlüssel in den Cache (`schluesselEntfernen`).
9. **Termux-Skripte:**
   - `hermes-nacht-job.sh`, `konversation_paket.sh` und `stream_an_frontend.sh` lesen den
     Schlüssel über das neue `termux/api-schluessel.sh` aus der Einstellungsdatei
     (`backend/` zuerst, dann der Projektordner). Das Hilfsskript liest nur die Zeile
     `API_KEY`, ohne `source`, und gibt nur deren Wert aus.
   - Ein fehlender Schlüssel ergibt eine Warnzeile statt eines stillen Abbruchs.
   - Der Nachtjob bestimmt seinen Projektordner jetzt aus dem eigenen Ort. Der alte feste
     Pfad bleibt als Rückfall.
10. **Doku:**
    - `backend/.env.example`: `HOST_BIND`, `API_KEY`, `ERLAUBTE_HOSTS`, `CORS_HERKUNFT`,
      dazu der Hinweis auf unverschlüsseltes HTTP.
    - `CLAUDE.md`: Netzregel und Architekturzeile.
    - `android/README.md` und der Kommentar in `MainActivity.kt`.

### Tests

- **Neu `backend/tests/test_sicherheit_herkunft.py`** (25 Testfunktionen):
  - Herkunft: cross-site, same-site, fremde und ähnliche Origins → 403; eigene Herkunft → 200.
  - Host: fremd → 400; `localhost`, IP-Adressen und `ERLAUBTE_HOSTS` werden zur Laufzeit
    angenommen.
  - CORS-Vorabanfrage → 403; Kopfzeilen an allen Antwortarten; Zähler und Selbsttest-Feld.
  - Positivliste: 200 für die Liste, 404 u. a. für `/tests/…`, `/%74ests/…`, `/Tests/…`,
    `/app.js.bak`, `/api/konfig`, `/../backend/…`, `/docs`.
  - Der Schlüssel steht maskiert im Meta-Feld beider Seiten und in keiner anderen Datei.
  - Wächter: Jede Datei, die `index.html`, `hermes_status.html`, `sw.js`, `app.js` und
    `manifest.json` laden, steht in der Positivliste.
- **Neu `backend/tests/test_termux_schluessel_aus_env.py`** (7 Testfunktionen):
  - Kein Skript nutzt mehr `api/konfig`, und keines gibt den Schlüssel aus.
  - `bash -n` ist grün.
  - Das Hilfsskript wurde an erfundenen Dateien geprüft: `export`, Anführungszeichen, CRLF,
    leerer Wert, fehlende Datei, fremde Schlüssel bleiben draußen.
- **Neu `frontend/tests/test_sw_schluessel.js`:** gegen den alten `sw.js` rot (Exit 1).
- **`backend/tests/conftest.py`** erlaubt den Testclient-Host `testserver`.
- **Wächter `test_datenschutz_waechter.py`:**
  - Die Ausnahmeliste hat jetzt vier statt fünf offene Routen.
  - Neu: Es gibt kein `/api/konfig` mehr, und keine offene Route gibt den Schlüssel heraus
    (geprüft mit einem Attrappen-Schlüssel).

**Prüfbefehl Teil 2** (`cd backend && .venv/Scripts/python -m pytest tests/ -q`):
**4085 passed, 2 skipped, Exit 0** (456,13 s). Kein fremder Lauf parallel. Die gezielten Dateien
(Sicherheit, Wächter, Termux-Schlüssel, Selbsttest, Frontend) liefen vorher allein:
236 passed.

## Offen

- Ergebnisprüfung durch Hermes (frische Sitzung, DeepSeek v4.1 Flash).
- **P0.10 am Handy über Hermes, vor dem Push:**
  - Ist `HOST_BIND` gesetzt, und ist `API_KEY` gesetzt?
  - Unter welcher Adresse wird die App am PC aufgerufen? Falls über Tailscale, muss der Name
    in `ERLAUBTE_HOSTS`.
  - Welche Dateien außerhalb des Repos nennen noch `api/konfig`?

  P0 gilt erst als erledigt, wenn am Handy ein `API_KEY` gesetzt ist.
