# Changelog 2026-09-25 — Erinnerungen endlich sichtbar (Gedächtnis-Blatt im Chat)

**Projekt:** `personal_ai_agent` (02_Softwareentwicklung_IT)
**Stand:** 25.09.2026
**Auslöser:** Befund Sebastian — *„Ich müsste das ganze Gedächtniskonzept noch mal
überdenken, weil die Erinnerungen sind auch ziemlich schlecht. Ich habe einfach nur nix für
Erinnerungen — das müssen wir deutlich verbessern."*
**Konzept dazu:** `docs/konzept-gedaechtnis.md` (Ist-Zustand, Schwächen, Optionen A/B/C,
Empfehlung, offene Fragen)
**Prüfbefehle:** `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **263 passed**;
`node --check app.js` + `for t in frontend/tests/test_*.js; do node $t app.js; done` → 9/9 grün.
**Keine echten Erinnerungsinhalte ausgegeben, kein Bestand verändert.**

---

## 1. Befund — belegt (Datei:Zeile)

### 1.1 Der Verdacht: sind die Erinnerungen überhaupt da?

**Ja.** `GET /api/health` des Handys (über ADB, 25.09.2026, 10:07):

```
{"status":"ok","version":"0.1.0","llm_configured":true,"memory_count":175,
 "lan_ip":"192.168.178.118","lan_url":"http://192.168.178.118:8080"}
```

Zum Vergleich: die Handy-Sicherung vom 13.08.2026
(`chroma_data/sicherung-handy-gedaechtnis-2026-08-13_2004.json`) enthält 70 Einträge. Der
Bestand wächst also — es wird gelernt.

### 1.2 Der Verdacht: kommen sie beim Modell an?

**Ja.** Chat-Pfad `backend/app/router/chat.py:327-329` (`top_k=5`) bzw. `:1746` (Stream),
Übergabe `:1834`/`:490`, in den Prompt über
`backend/app/services/llm_service.py:472-475` + `_build_memory_context()` (`:277-286`).
Nachgemessen gegen die PC-Arbeitskopie:

```
retrieve_relevant_memories -> 3 Eintraege (top_k=5 angefragt)
_build_memory_context -> 403 Zeichen, 3 Eintraege
Blockkopf vorhanden: True
```

### 1.3 **Der Fehler: die Oberfläche zeigte sie nie**

`grep -rn "api/memory" frontend/` → **kein Treffer**. Sichtbar war einzig der Text im Fuß
(`frontend/index.html`, `<span class="footer-note">Gedächtnis aktiv</span>`), den
`app.js:1440-1445` (`updateFooterNote`) zu „N Erinnerungen" umschrieb. Das Backend hielt
Liste, Zähler und **Einzel-Löschen** längst bereit (`backend/app/router/memory.py:16-35`,
`:54-61`, `:115-131`) — aufgerufen hat sie niemand.

Folge: 175 gelernte Fakten waren weder zu sehen noch zu entfernen. Genau das ist „nix für
Erinnerungen".

### 1.4 NebenFund (dokumentiert, **nicht** geändert)

Die Wiederholungs-Prüfung (`memory_service.py:49,98-104`, Zeichenähnlichkeit ≥ 0,90) verwirft
auch **geänderte** Fakten derselben Bauart — gemessen: „seit zehn Jahren" vs. „seit elf
Jahren" = 0,950, „Hund namens Rex" vs. „… Max" = 0,933, „Geburtstag: 3. Mai 1984" vs.
„5. Mai 1985" = 0,905. Eine Korrektur kann also am alten, falschen Eintrag abprallen.
Das ist eine Gedächtnis-Konzeptentscheidung (§2.5 und §7 des Konzepts) und wurde hier
bewusst nur festgehalten, nicht verändert — Test:
`backend/tests/test_memory_api.py::test_gleicher_anfang_gilt_schon_als_wiederholung`.

---

## 2. Änderung (code + docs)

### Frontend
* `frontend/index.html`
  * Der Fuß-Text ist jetzt ein Knopf `#gedaechtnis-btn` (öffnet das Blatt).
  * Neues Blatt `#memory-sheet` mit Liste `#memory-list` und Hinweiszeile `#memory-hint`,
    Aufbau wie das bestehende Modell-/Gesprächs-Blatt.
  * Cache-Bump: `style.css?v=20260925A`, `app.js?v=20260925A`.
* `frontend/app.js`
  * `erinnerungenZahl()` — echte Gesamtzahl aus `GET /api/memory/count`. Nötig, weil die
    Liste bei 200 gedeckelt abgeholt wird und `total` in der Antwort nur die Zahl der
    *gelieferten* Einträge ist (`router/memory.py:32`).
  * `zeichneErinnerungen()` — Liste jüngste zuerst, je Eintrag Text, Art (Fakt/Vorliebe/
    Zusammenhang/Vorhaben) und Datum; Inhalte werden escaped.
  * `loescheErinnerung()` — `DELETE /api/memory/{id}` nach Rückfrage; prüft die Antwort und
    meldet einen Fehlschlag sichtbar („… der Eintrag ist noch da").
  * Öffnen/Schließen: Knopf, ×, Hintergrund-Tippen, Escape.
* `frontend/style.css` — `#memory-sheet` in die Blatt-Gruppe aufgenommen; `.memory-row`,
  `.memory-text`, `.memory-meta`, `.memory-del`; `button.footer-note` auf Text-Aussehen
  zurückgesetzt.

**Bewusst nicht gebaut:** „Alle löschen" (`DELETE /api/memory/clear` bleibt ungenutzt) —
nicht rücknehmbar. Einzel-Löschen löst den Fall (ein falscher Eintrag kostete bisher alles).

### Dokumentation
* `docs/konzept-gedaechtnis.md` — neu: Ist-Zustand mit Datei:Zeile, 9 Schwächen mit Beleg,
  Optionen A/B/C mit Aufwand/Risiko/Wirkung/Grenzen, Empfehlung der Reihenfolge,
  Liste „sofort klein fixbar", offene Fragen.
* `README.md` — Gedächtnis-Zeile und API-Tabelle nachgezogen (siehe unten).

---

## 3. Tests

| Test | Was er sichert |
|---|---|
| `backend/tests/test_memory_api.py` (neu, 10 Tests) | Liste/Anlegen/Zähler über die echten Router-Funktionen; Einzel-Löschen inkl. 404; Dedup; Trockenlauf beim Aufräumen; leerer Speicher erzeugt **keinen** Prompt-Block; kleiner Speicher wandert vollständig; Vektor-Nachrüstung; Ist-Zustand der Ähnlichkeitsregel |
| `frontend/tests/test_gedaechtnis_ui.js` (neu, 41 Prüfungen) | Blatt/Knopf vorhanden; Liste kommt vom echten Endpunkt; Leerfall erklärt; Fehlschläge sichtbar; Löschen prüft die Antwort und sendet nie eine leere ID; kein „Alle löschen"; Escaping; Verdrahtung; Cache-Bump |

Beide Testdateien fassen niemals den echten Bestand an: `test_memory_api.py` biegt
`store_path`/`persist_dir` auf `tmp_path` um und ersetzt `mistral_vektor` (kein Netz-Aufruf).

### Echte Ausgaben

```
$ cd backend && .venv/Scripts/python -m pytest tests/ -q
263 passed in 25.59s          (Baseline vorher: 253 passed)

$ node --check app.js
OK

$ for t in tests/test_*.js; do node $t app.js; done
tests/test_conv_code_live_stream.js           OK
tests/test_diff_darstellung.js                OK
tests/test_gedaechtnis_ui.js                  OK   (neu)
tests/test_options_assistent.js               OK
tests/test_quiz_ende.js                       OK
tests/test_quiz_geo.js                        OK
tests/test_quiz_rahmen_quelle.js              OK
tests/test_ref_loeschen_ui.js                 OK
tests/test_serielles_tippen.js                OK
```

> **Nicht verwechseln (Stand 25.09.2026, 10:20):** Ein **zweiter Strang** arbeitet parallel
> an der Verlaufs-Konsistenz (`backend/app/router/chat.py`, `backend/app/services/chat_verlauf.py`
> geändert; `backend/tests/test_verlauf_konsistenz.py` neu). Dessen vier Tests sind derzeit
> rot. Mit dieser Änderung hat das nichts zu tun; ohne diese Datei läuft die Suite mit
> **263 passed** durch (`--ignore=tests/test_verlauf_konsistenz.py`). Der fremde Strang wurde
> hier nicht angefasst.

Zusätzlich (Arbeitsnachweis außerhalb des Repos): die echten Funktionen aus `app.js` gegen
die echte Antwort eines lokal gestarteten Backends (`--lifespan off`, eigenes
Test-Verzeichnis als Speicher) ausgeführt. Ergebnis: 3 Testeinträge wurden mit Art/Datum
und Entfernen-Knopf gezeichnet, die Löschung sendete die richtige ID, ein erzwungener
HTTP-500-Fehlschlag wurde sichtbar gemeldet (`Entfernen fehlgeschlagen (HTTP 500) … der
Eintrag ist noch da.`), der leere Bestand wurde erklärt statt leer gelassen.

---

## 4. Wirkung auf dem Handy

Nach `git pull` in Termux und Neuladen der App zeigt der Text unten rechts
(„175 Erinnerungen") antippbar das Blatt mit allen Einträgen — der Text ist derselbe, die
Funktion ist neu. Bis 200 Einträge wird alles gezeigt; darüber steht in der Hinweiszeile
„… hier die 200 jüngsten" (ehrlich benannt, siehe `erinnerungenZahl()`).
