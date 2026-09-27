# Themen-Stufe Teil 2: Thema je Anlass per Vision-Blick (N6)

> **Datum:** 27.09.2026 · **Auftrag:** Nachtlauf N6 („Themen je Anlass (Stapel)
> → Zuordnung im Sortierschlüssel"). Plan: `docs/plan-nachtlauf-2026-09-26.md`.
> Rahmen: `docs/plan-foto-personen-und-erinnerungen.md` (Stufe 2).
> Baut auf N4 auf (`docs/changelog-2026-09-27-foto-themen.md`, Kontaktbögen).

## Warum es diesen Schritt gibt

N4 konnte Kontaktbögen bauen (ein Bogen je Anlass, Kacheln mit Nummern) — aber
niemand hatte hineingesehen. Für die Zielstruktur `Agent/Fotos/<Jahr>/<Thema>/`
fehlt genau eine Angabe: **welches Thema** ein Anlass hat. N5 hat an einem echten
Bogen gemessen, dass EIN Vision-Blick je Anlass genügt (Nummern 1–36 lesbar,
Thema erkennbar, unbrauchbare Bilder fallen mit ab). N6 macht daraus ein
Werkzeug, das diese Erkenntnis wiederholbar und wiederaufsetzbar anwendet.

## Was gebaut wurde

| Datei | Inhalt |
|---|---|
| `tools/foto_sortierung/foto_themen_vision.py` | Bogen + Zuordnungs-JSON lesen, EIN Vision-Aufruf je Anlass, Thema in die Kopie des Sortierschlüssels schreiben |
| `backend/tests/test_foto_themen_vision.py` | **59 Prüfungen** — alles ohne Netz (httpx ersetzt, Schlüssel erfunden, Ausgaben in `tmp_path`) |

**Ablauf je Anlass:** Kontaktbogen-JPEG (`~/foto_sortierung/boegen/<Jahr>/`) →
base64 **in-memory** als `data:`-URL in `POST {basis}/chat/completions`
(content-Array: `text` + `image_url`), Standardmodell
`google/gemini-2.5-flash` (dasselbe Vision-Modell, das der Chat benutzt) →
Antwort wird über JSON-Zäune/Vor-Nachtext/erstes `{` bis letztes `}` zerlegt →
`thema`, `je_kachel` (Kurzzeile + `unbrauchbar`), `hinweis`.

**Ausgaben ausschließlich außerhalb des Repos** (dort liegen private Namen):

* `~/foto_sortierung/themen/<Jahr>/<Titel>.json` — je Anlass: `thema`, `modell`,
  `tokens_ein`, `tokens_aus`, `kosten_usd` (nur wenn Preise gesetzt sind, sonst
  `null`), `dauer_s`, `kacheln` (Modell-Aussage + Dateiname/fileid aus dem
  Zuordnungs-JSON), `rohtext` (Nachvollziehbarkeit).
* `~/foto_sortierung/themen.jsonl` — **Fortsetzungspunkt**, eine Zeile je
  erledigtem Anlass; Fehlerzeilen werden beim nächsten Lauf wiederholt.
* `~/foto_sortierung/sortierschluessel_themen.csv` — **Kopie** der Eingabe-CSV
  mit gefüllter Spalte `thema` + neuer Spalte `thema_quelle` (Anlass-Titel).

**Regeln, die das Werkzeug einhält:**

* **Original-CSV wird nie angefasst** (nur gelesen) — geschrieben wird die Kopie,
  und `_pruefe_csv_ziel()` bricht zusätzlich mit Exit 2 ab, wenn Eingabe- und
  Ausgabe-CSV auf denselben Pfad zeigen (Groß-/Kleinschreibung und Schräg-/
  Rückwärtsstrich egal) — die Zusicherung hängt also nicht nur an der Namenswahl.
  Prüfbar: die Originaldatei blieb über alle Live-Läufe hinweg unverändert
  (`md5 70642d2988b6e38ff417561ccf870ba8`, Zeitstempel 20:13).
* **Kein Bild wird kopiert oder gespeichert** — das JPEG wird als Bytes gelesen,
  base64-kodiert und im selben Prozess verworfen (Sebastians Bild-Regel). Der
  Bogen selbst ist das N4-Erzeugnis und liegt außerhalb des Repos.
* **Ausgabeziel wird geprüft** — `_pruefe_ausgabe()` bricht mit deutscher
  Klartext-Meldung und Exit 2 ab, wenn der Ausgabeordner **im Repo** liegt
  (Groß-/Kleinschreibung und Schräg-/Rückwärtsstrich egal); die Prüfung läuft vor
  jedem Senden/Schreiben, auch bei `--trocken`/`--nur-liste`. Live belegt:
  `--ausgabe ../tools/foto_sortierung/tmp-ausgabe` → Exit 2, nichts angelegt.
* **Antwort des Modells wird ehrlich verbucht** — die Begriffe sind streng
  getrennt: **unsinnige Einträge** (kein Objekt, Nummer fehlt, Nummer erfindet
  eine Bogenkachel, Nummer doppelt — der erste Eintrag bleibt) werden **verworfen**
  und mitgezählt, solange mindestens eine gültige Kachel bleibt; bleibt keine
  gültige, gilt die Antwort als unbrauchbar (Fehler statt halber Wahrheit).
  **Unbrauchbare Kacheln** (Modell setzt `unbrauchbar: true`) werden dagegen
  **behalten** und als `unbrauchbare_kacheln` gezählt — sie zählen **nicht** als
  fehlend, denn die Kachel ist ja da. `unvollstaendig: true` gilt, wenn gültige
  Kacheln < Bogenkacheln **oder** mindestens ein unsinniger Eintrag verworfen
  wurde; `fehlende_kacheln` ist die Zahl der Bogenkacheln ohne gültigen Eintrag.
  Ein fehlendes `hinweis` bleibt einfach leer. Das Thema wird auch bei
  unvollständiger Liste gesetzt — ein unvollständiger Bogen soll einen brauchbaren
  Anlass nicht wegwerfen. Alle diese Aussagen stehen sinngemäß genauso im
  Modul-Docstring (codegenau; vom fremden Prüfer Zeile für Zeile gegengelesen).
* **Kein Löschen** — es gibt keinen Löschbefehl; nichts wird umbenannt.
* **Nur OpenRouter** als einziger Fremdweg; kein zweiter Anbieter, kein Codex,
  keine pCloud-Anfrage (dieses Werkzeug spricht pCloud gar nicht an).
* **Idempotent** — ein **erfolgreich erledigter** Anlass (Eintrag in
  `themen.jsonl` **und** vorhandene Ergebnisdatei) wird übersprungen;
  **Fehlerzeilen** werden beim nächsten Lauf bewusst **erneut** versucht (dort hat
  die Liste nichts gekostet), `--wiederholen` erzwingt auch für erfolgreiche
  Anlässe einen neuen Blick.
* **Schlüssel bleibt geheim** — er geht nie in den Prompt, wird nie ausgegeben
  oder geloggt, und **jeder Modelltext wird vor dem Speichern maskiert**
  (`geheimnis_entfernen()` auf `thema`, `kurz`, `hinweis` und `rohtext`; zusätzlich
  generische `sk-…`/`sk_or-…`-Muster). Live-Test: eine Attrappen-Antwort, die den
  Schlüssel wiederholt, hinterlässt ihn in **keiner** geschriebenen Datei und in
  keiner Konsolenzeile. Fehlt der Schlüssel, gibt es eine deutsche Meldung +
  Exit 2, ohne zu senden.
* **Doppelungen erben** — Zeilen mit gefüllter Spalte `doppelung` (dieselbe Datei
  auf zweitem Gerät) bekommen das Thema ihrer Geschwisterzeile.
* `--trocken` und `--nur-liste` senden NICHTS, schreiben NICHTS, brauchen keinen
  Schlüssel.

**Aufruf** (venv des Backends — dort liegen `httpx` und `Pillow`):

```bash
cd backend
.venv/Scripts/python ../tools/foto_sortierung/foto_themen_vision.py --nur-liste
.venv/Scripts/python ../tools/foto_sortierung/foto_themen_vision.py --jahr 2025 --limit 3 --trocken
.venv/Scripts/python ../tools/foto_sortierung/foto_themen_vision.py \
    --jahr 2025 --anlass 2025-01-06_Anlass-01 --preis-ein 0.30 --preis-aus 2.50
```

## Gemessen — echte Aufrufe, echte Zahlen (27.09.2026)

Die zwei vorhandenen Bögen wurden **live** durchgerechnet (kein Trockenlauf):

| Anlass | Kacheln | Thema des Bogens | Tokens (ein/aus) | Kosten | Dauer |
|---|---|---|---|---|---|
| `2025-01-06_Anlass-01` | 36 | „Veranstaltung Publikum Bühne" | 2.306 / 1.465 | **0,004354 $** | 6,8 s |
| `2025-02-21_Anlass-01` | 10 | „Konzert Band Auftritt" | 3.750 / 452 | **0,002255 $** | 3,6 s |

Beide Themen decken sich mit dem, was N5 beim Sehen notiert hatte
(„Veranstaltung in großer Halle", „Publikum vor grüner Bühne").

**Idempotenz live:** zweiter Lauf (beide Anlässe) → `angesehen: 0`,
`uebersprungen: 2`, **0 Tokens**, 0,2 s. Die CSV-Kopie trug danach
`thema gefuellt: 46` (= 36 + 10, exakt die Dateien der beiden Anlässe).

**Erzwungener zweiter Blick (`--wiederholen`, nach dem Umbau der Zähler):**
derselbe Bogen, dieselbe Antwort, dieselben Kosten —
`"Veranstaltung Publikum Bühne" (36/36 Kacheln, unvollstaendig: false,
fehlende_kacheln: 0, unbrauchbare_kacheln: 2, 2.306+1.465 Tokens,
0,004354 USD, 6,13 s)`. Die Laufzeile trägt die Zähler also wirklich; das Modell
selbst hatte 2 Kacheln als unbrauchbar markiert, alle 36 waren vorhanden.

**Preise (live über `/api/v1/models` abgefragt, je 1 Mio Token):**
`google/gemini-2.5-flash` 0,30 ein / 2,50 aus · `google/gemini-2.5-flash-lite`
0,10 / 0,40 · `deepseek/deepseek-v4.1-flash` 0,035 / 0,29 (kein eigener Bildpreis
ausgewiesen). Das Werkzeug rechnet **nur** mit den übergebenen Preisen —
ohne `--preis-ein/--preis-aus` steht `kosten_usd: null`, es wird keine Zahl
erfunden.

**Hochrechnung (Schätzung, ausdrücklich keine Messung):** der Bestand hat
**2.128 Anlässe**; die beiden Messpunkte liegen mit 10 und 36 Kacheln **über**
dem Mittel von 3,9 Kacheln, sind also eher eine Obergrenze. Größenordnung für
den Vollauf: **2–4 $** mit `gemini-2.5-flash`, mit `flash-lite` etwa ein Drittel.
Vor dem Massenlauf wird an einer Stichprobe von ~20 Anlässen gemessen, nicht
gerechnet.

## Prüfbefehl

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
→ 628 passed, Exit 0   (Baseline vor der Änderung: 569 → +59 neue)

nur die neuen: .venv/Scripts/python -m pytest tests/test_foto_themen_vision.py -q
→ 59 passed, Exit 0
```

Abgedeckt u. a.: Prompt nennt die Kachelnummern; JSON-Zerlegung mit Zaun, mit
Vor-/Nachtext, mit kaputtem Text (Fehler statt Ratens); Trockenlauf/Nur-Liste
lösen keinen Aufruf aus (Stolperfalle); `themen.jsonl`-Fortsetzung und
`--wiederholen`; Fehler nach drei Versuchen wird festgehalten statt Absturz;
429 wird wiederholt; fehlender Schlüssel → Exit 2; Schlüssel taucht in keiner
Ausgabe auf; kein Bild/kein Bogen landet im Repo; CSV-Kopie füllt `thema`,
Doppelungen erben; **Original-CSV byte-gleich** nach dem Lauf; Ausgabeordner im
Repo → Exit 2 (auch mit vertauschten Schrägstrichen und anderer Groß-/Kleinschreibung);
fehlende Kacheln werden gezählt statt still verschluckt.

## Prüfrunden — was der fremde Prüfer gefunden hat

Rollen-Regel: gebaut hat ein Hermes-Subagent (DeepSeek V4.1 Flash), geprüft hat
`openai/gpt-5.6-luna` (`hermes -z`, andere Modellfamilie, führt den Prüfbefehl
selbst aus).

* **Runde 1: „nicht bestanden"** (4 Beanstandungen). Berechtigt und behoben:
  (a) `--ausgabe` war frei wählbar und wurde ungeprüft zum Schreiben benutzt →
  jetzt `_pruefe_ausgabe()` mit Abbruch vor jedem Schreiben; (b) die Doku war nicht
  codegenau (optionaler `hinweis`, tolerierte Kachellücken) → ausdrücklich im
  Docstring plus ehrliche Zählung. **Unbegründet** und nicht „wegrepariert":
  `hinweis` war im Auftrag ausdrücklich optional, und die zusätzlich gefundenen
  Dateien im Arbeitsbaum gehören dem zweiten Agenten bzw. sind die Doku dieses
  Schrittes.
* **Runde 2: „nicht bestanden"** (1 Beanstandung, berechtigt): die Doku behauptete,
  doppelte Kachelnummern würden verworfen — der Code tat es nicht. Der Planer
  entschied: Duplikate werden verworfen (erster Eintrag bleibt), Einträge mit
  `unbrauchbar: true` werden dagegen **behalten** und gezählt. Runde 3 bestätigte
  den Code danach als stimmig.
* **Runde 3: „nicht bestanden"** (1 Beanstandung, berechtigt): **meine eigene**
  Änderungsdoku verwendete „unbrauchbare Kachel-Einträge" noch im Zusammenhang mit
  „verworfen" — also veraltet gegenüber der neuen Entscheidung. Korrigiert.
* **Runde 4: „nicht bestanden"** (1 Beanstandung, berechtigt): die Doku trug noch
  die **Zahlen** aus der Zeit vor den Umbrüchen (48/617 statt 53/622) und
  behauptete „wortgleich", wo es sinngemäß ist. Zahlen und Wortwahl korrigiert.
* **Runde 5: „nicht bestanden"** (3 Beanstandungen, alle berechtigt): zwei
  **absolute Zusicherungen waren nicht durch Code gedeckt** — (a) der Rohtext der
  Modellantwort wurde ungefiltert gespeichert (ein Modell, das den Schlüssel
  wiederholt, hätte ihn auf Platte geschrieben) → jetzt `geheimnis_entfernen()`
  auf allen Modelltexten plus generische `sk-…`-Muster; (b) die Ausgabe-CSV konnte
  bei gleichem Pfad die Original-CSV überschreiben → jetzt `_pruefe_csv_ziel()`
  mit Exit 2. Dazu (c) eine **zu pauschale Doku-Aussage** zur Idempotenz (es
  werden nur *erfolgreiche* Anlässe übersprungen, Fehlerzeilen bewusst erneut
  versucht) — Wortlaut korrigiert.

* **Runde 6: „bestanden".** Der Prüfer führte die Suite selbst aus (**628 passed**,
  **59** in der neuen Datei, `628 − 59 = 569` = Baseline), prüfte jede Zusicherung
  Zeile für Zeile — inklusive eigener netzfreier Mini-Probe zur Maskierung — und
  fand **keine Abweichung** mehr. Wortlaut des Prüfers: „Die drei Beanstandungen
  aus Runde 5 sind behoben … bestanden" (Protokoll:
  `…/hermes/cache/scratch/pruefer-n6-runde6.log`).

**Was das zeigt:** von zehn Beanstandungen in fünf Runden waren **acht berechtigt
— vier am Code, vier an der Dokumentation**. Muster: solange gebaut wird, wächst
der Code schneller als seine Beschreibung; jede Nachbesserung zieht Wortwahl und
Zahlen nach. Deshalb gilt hier: die Doku wird erst fertig, wenn der Code steht.
Zweite Lehre: ein Auftrag, der etwas **zusichert** („Ausgaben nie im Repo", „der
Schlüssel bleibt geheim", „die Originaldatei wird nie geschrieben"), muss diese
Zusicherung als **eigenen Prüfpunkt mit Abbruch** im Code verlangen — sonst ist es
eine Konvention, keine Garantie.

## Was dieser Schritt NICHT getan hat

* **Kein Massenlauf.** Angesehen sind die zwei vorhandenen Bögen — für alle
  2.128 Anlässe müssen die Bögen erst noch gebaut werden (N4-Werkzeug, je Anlass
  ein `listfolder` + Vorschaubilder in Stapeln).
* **Nichts in die pCloud geschrieben**, nichts sortiert, nichts verschoben.
* **Keine Gesichtserkennung** (Stufe 3) — die Personen-Stufe ist N9.
* **Keine Themen in die Original-CSV geschrieben** — bewusst nur in die Kopie,
  damit der Sortierschlüssel aus Stufe 1 unverändert nachprüfbar bleibt.

## Nächste Schritte

1. **N6b (Massenlauf):** Bögen für ein Jahr bauen (kleinster Stapel zuerst,
   z. B. 2025 mit 380 Anlässen), dann Themen setzen; Fortsetzungspunkt ist
   `themen.jsonl`, Abbruch ist jederzeit ohne Verlust möglich. Vorher Stichprobe
   ~20 Anlässe zur Kostenmessung (auch mit `flash-lite` und
   `deepseek-v4.1-flash` als billigeren Wegen).
2. **N7:** Probelauf `--trocken` des Sortierens (Ordner anlegen + verschieben),
   Grundlage ist `sortierschluessel_themen.csv`.
3. **N9:** Personen-Stufe (parallel möglich, andere Dateien).
