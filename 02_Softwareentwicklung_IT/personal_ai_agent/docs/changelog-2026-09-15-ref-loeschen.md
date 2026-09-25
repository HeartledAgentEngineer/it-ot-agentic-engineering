# Changelog 2026-09-15 — Einzelne Referenz löschen (auch bei Altdaten ohne `ref_id`)

**Projekt:** `personal_ai_agent` (02_Softwareentwicklung_IT)
**Stand:** 20.09.2026
**Auslöser:** Befund Sebastian — *„Bei den abgespeicherten Ausschnittbildern waren wieder welche ohne Bild. Und: ich wollte EINS löschen, musste aber ALLE löschen."*
**Prüfbefehle:** `backend/tests/test_gesichter_ref_loeschen.py`, `frontend/tests/test_ref_loeschen_ui.js` — beide grün (Ausgaben unten).
**Keine echten Personendaten angefasst** (Tests biegen `KATALOG_DATEI` auf `tmp_path` um).

---

## 1. Befund — belegt am Code (Datei:Zeile)

### 1.1 Verdacht geprüft: fehlt bei Altdaten das `ref_id` in der API?

**Widerlegt.** Die API liefert für **jede** Referenz eine nicht-leere `ref_id` — auch für Altbestand ohne gespeicherte ID:

* `backend/app/services/gesichter_service.py:332` `_refs_of()` hängt an jeden Eintrag eine *effektive* ID: `eintrag["ref_id"] = _ref_id_von(r)` (`:374`). Findet `_ref_id_von` kein gespeichertes `ref_id`, berechnet es den Hash aus dem Embedding (`_ref_id_von` → `_ref_id`, `:247`).
* `gesichter_service.py:382` `referenzen_auflisten()` gibt genau dieses `ref_id` aus (`:403`).
* Router: `backend/app/router/gesichter.py:146` `GET /api/gesichter/referenzen` → `referenzen_auflisten()`.

Messung mit einem nachgestellten Altbestand (2 Referenzen, keine `ref_id` gespeichert, aus `evidenz_ref.py`):

```
VOR  (gespeichert): [{"embedding": [1.0, 0.0, 0.0], "jahr": 2015}, {"embedding": [0.0, 1.0, 0.0], "jahr": 2020}]
API ref_ids       : ['3cffc7a9b3d4', 'c94047323967']
```

→ Kein `undefined`, kein leeres Feld. `encodeURIComponent(undefined)` = `"undefined"` **kann** also im Normalfall gar nicht entstehen.

### 1.2 Verdacht geprüft: schlägt das Einzel-Löschen serverseitig fehl?

**Widerlegt** (im aktuellen Stand). `referenz_entfernen` (`gesichter_service.py:447`) löscht eine Alt-Referenz über die abgeleitete ID korrekt; die Person und die übrigen Referenzen bleiben:

```
Loeschen #0       : {'ok': True, 'name': 'Altperson', 'verbleibend': 1}
Person noch da?   : True | verbleibend: 1
```

### 1.3 **Der eigentliche Fehler (bestätigt): die UI verwarf die Serverantwort**

`frontend/app.js` — Lösch-Knopf in der Vollbild-Referenzliste (*„Referenzen ansehen / Rahmen anpassen"*, `zeile 4907` `zeigeReferenzenVollbild`), **vorher**:

```js
del.addEventListener('click', async () => {
    await fetch(`.../referenzen/${encodeURIComponent(name)}/${encodeURIComponent(r.ref_id)}`, { method: 'DELETE' });
    z.style.opacity = 0.35;
    del.textContent = '✓ gelöscht';   // ← IMMER, egal was der Server antwortete
    del.disabled = true;
});
```

*Status-/Code-Fehler (404 `{"detail": "Referenz nicht gefunden"}`, HTTP 500, Netzabbruch, falsche ID) wurden nicht ausgewertet; der Erfolg wurde vorgetäuscht.*
**Das erklärt den Befund exakt:** Sebastian tippt ✕, sieht „✓ gelöscht", die Referenz ist aber noch da → er greift zum einzigen Knopf, der sichtbar etwas verändert: „🗑 Alle Referenzen löschen" (`app.js:4929`), dessen Schleife über ALLE Referenzen läuft (`app.js:4931`). Genau das hat er berichtet.

Zweitbeleg — derselbe Schleier an zwei weiteren Stellen:
* Sammel-Löschen „🗑 Alle Referenzen löschen": meldete pauschal „✅ Alle Referenzen gelöscht", ohne eine der Antworten zu prüfen (jetzt ehrlich, `app.js:4936–4952`).
* `app.js:4890` (vorher): `if (!window.confirm && typeof confirm === 'function' && !confirm(...))` — die Bedingung ist im Browser **immer** falsch, die Rückfrage lief nie.

### 1.4 Referenzen ohne Ausschnittbild — welcher Schreibpfad

Ein `bild_pfad` fehlt an einer Referenz auf **zwei** Wegen:

1. **Legacy-Normalisierung im Quiz** (der eigentliche „alt gelernt"-Pfad):
   `backend/app/services/gesicht_quiz.py:757–761` — hat eine Person noch keinen `referenzen`-Block, werden die rohen Alt-Vektoren zu `{"embedding": r, "jahr": None}` **ohne** `bild_pfad` normalisiert und über `person_speichern(referenzen=…)` (`:768`, ebenso `:897`) festgeschrieben. Der Datenpfad `_refs_bereinigen` (`gesichter_service.py:130`) nimmt `bild_pfad` nur auf, *wenn er gesetzt ist* (`:140`).
2. **Originaldatei weg** (z. B. pCloud-Umzug): `bild_pfad` ist gesetzt, `/api/dateien/daten` liefert aber `data_url` nicht → Anzeige „(Bild fehlt)" (`app.js:5022` / `:5028`), bzw. „(kein Bild gespeichert)" ohne `bild_pfad` (`app.js:5034`).

**Anzahl der Fälle:** Auf diesem Rechner ist der echte Katalog leer (`gesichter_katalog.json` = `{"personen": []}`), Sebastians Handy-Datenbestand ist von hier aus **nicht zählbar** — bewusst nicht geschätzt. Zählbar ist er nach diesem Fix in der App selbst: jede betroffene Zeile trägt jetzt das Abzeichen **„⚠️ ohne Bild"**. Im synthetischen Testfall waren 2 von 2 Alt-Referenzen ohne Bild.

---

## 2. Fix

### 2.1 Serverseitig: Altdaten abdichten (`backend/app/services/gesichter_service.py`)

| Neu/geändert | Zeile | Wirkung |
|---|---|---|
| `_ref_passt(eintrag, rid)` | `:270` | Eine ID adressiert eine Referenz, wenn sie der **effektiven** ID (`_ref_id_von`) **oder** dem **Embedding-Hash** (`_ref_id`) entspricht. |
| `_ref_ids_ergaenzen(personen)` | `:292` | Migration: ergänzt fehlende `ref_id` — **nur** dieses Feld. Idempotent. |
| `ref_ids_migrieren()` | `:316` | Schreibt die ergänzten IDs atomar zurück (`_speichern`). |
| `referenzen_auflisten()` | `:382` | Ruft die Migration beim **ersten Zugriff** auf (in `try/except`, damit Lesen nie blockiert). |
| `person_speichern()` (Update-Zweig) | `:220` | Migriert zusätzlich **beim Speichern**. |
| `referenz_entfernen()` | `:462` | Löscht über `_ref_passt` (robust gegen alte/abgeleitete IDs). Unbekannte ID → weiterhin `{"ok": false, "fehler": "referenz nicht gefunden"}`, Katalog unverändert. |
| `referenz_bbox_aktualisieren()` | `:496` | Findet die Referenz ebenfalls über `_ref_passt`; übernimmt danach die **stabile** ID der gefundenen Referenz. |

Migration, gemessen (Embedding/jahr unverändert, nur `ref_id` kommt dazu):

```
VOR  (gespeichert): [{"embedding": [1.0, 0.0, 0.0], "jahr": 2015}, {"embedding": [0.0, 1.0, 0.0], "jahr": 2020}]
NACH (gespeichert): [{"embedding": [1.0, 0.0, 0.0], "jahr": 2015, "ref_id": "3cffc7a9b3d4"},
                     {"embedding": [0.0, 1.0, 0.0], "jahr": 2020, "ref_id": "c94047323967"}]
Vektor-Spiegel    : [[0.0, 1.0, 0.0]]      # nach Loeschen von #0: nur der Rest
```

### 2.2 Frontend: Fehler sichtbar, keine leeren IDs (`frontend/app.js`)

| Stelle | Zeile | vorher → nachher |
|---|---|---|
| ✕-Löschen im Referenz-Vollbild | `:5046` (Handler `:5057`, Prüfung `:5070`) | blinde Anfrage + „✓ gelöscht" → Antwort wird gelesen (`await res.json()`), Erfolg nur bei `res.ok && d.ok`; sonst **„⚠️ NICHT gelöscht: …"** (`:5076`/`:5080`) direkt in der Zeile, Knopf bleibt aktiv. |
| ID-Prüfung | `:5058` | `encodeURIComponent(r.ref_id)` → `const rid = (r.ref_id != null) ? String(r.ref_id).trim() : ''`; bei leerer ID keine Anfrage, sondern Hinweis „Referenz hat keine ID — Seite neu laden." (`:5060`) |
| „⚠️ ohne Bild"-Abzeichen | `:5040`–`:5044` | Zeilen ohne `<img>` werden sichtbar gekennzeichnet; die Zeile bleibt bestehen und einzeln löschbar. |
| „🗑 Alle Referenzen löschen" | `:4936`–`:4952` | zählt Erfolge/Fehler, prüft jede Antwort (`if (resp.ok) okCount++`), meldet ehrlich „⚠️ X gelöscht, Y NICHT gelöscht." |
| `referenzLoeschen` (Chat-Blase) | `:4889` | Confirm-Bug behoben (`typeof confirm === 'function' && !confirm(…)`), ID geprüft, Antwort ausgewertet. |

Cache-Bump (Pflicht bei Frontend-Änderungen): `frontend/index.html:204` `app.js?v=20260920A` → `?v=20260920B`. `sw.js` bleibt unverändert (Statik ist dort network-first, `sw.js:78–85`).

---

## 3. Neue Tests

**`backend/tests/test_gesichter_ref_loeschen.py`** (12 Tests) — Fixture schreibt einen Katalog im Stand *vor* dem 15.09.2026 (`referenzen` ohne `ref_id`, dazu der Legacy-`embedding`-Spiegel):

1. Alt-Referenz **einzeln** löschbar; Person + die *andere* Referenz bleiben erhalten → `verbleibend == 1`.
2. Löschen über den **Embedding-Hash** funktioniert auch, wenn eine abweichende `ref_id` gespeichert ist.
3. API liefert für Altdaten eine **nicht-leere** `ref_id`, und zwar **stabil** über zwei Abrufe.
4. Die API-IDs entsprechen exakt den **migrierten** gespeicherten IDs.
5. **Migration ergänzt nur `ref_id`**: Embedding, `bbox`, `bbox_norm`, `jahr`, `bild_pfad` und die Personen-Außenfelder (`embedding`, `referenz_bild_miniatur`) sind vorher == nachher; `set(keys) == alt ∪ {ref_id}`.
6. Migration ist **idempotent** (2. Lauf → `False`, keine Änderung).
7. Auch `person_speichern` (Update-Zweig) trägt die `ref_id` nach.
8. Unbekannte ID → `{"ok": false, "fehler": "referenz nicht gefunden"}`, **Katalog byte-identisch** (Vergleich der Datei vor/nach).
9. Löschen entfernt **auch den Vektor** (Legacy-`embedding`-Spiegel: 2 → 1, nur der Rest bleibt).
10.–12. Router-Ebene: `DELETE /referenzen/{name}/{ref_id}` löscht die Alt-Referenz, antwortet bei unbekannter ID mit **404**, und `GET /referenzen` liefert `ref_id`s.

**`frontend/tests/test_ref_loeschen_ui.js`** (33 Quelltext-Prüfungen, `node tests/test_ref_loeschen_ui.js app.js`) — vier Gruppen:

* **A** Fehlschlag wird sichtbar gemeldet (`delStatus`, `'⚠️ NICHT gelöscht: …'`, `res.ok && d.ok`, `detail/fehler`, `'HTTP ' + res.status`, `Netzwerkfehler`, Knopf bleibt aktiv) — inkl. **Negativprobe**: kein `fetch(…DELETE…)` mehr, auf das direkt ein Erfolgs-Fake folgt.
* **B** Keine leere/undefined ID (`String(r.ref_id).trim()`, `if (!rid)`, URL nutzt `encodeURIComponent(rid)`, **nicht** `r.ref_id`; alter Confirm-Bug darf nicht zurückkommen).
* **C** „⚠️ ohne Bild"-Abzeichen vorhanden, Zeile bleibt sichtbar; die alten Platzhalter bleiben; der alte blinde Lösch-Button ist weg.
* **D** „Alle löschen" zählt Erfolge/Fehler und prüft jede Antwort.

---

## 4. Echte Verifikationsausgaben (frisch ausgeführt, 20.09.2026)

```
$ cd backend && .venv/Scripts/python -m pytest tests/ -q
253 passed, 3 warnings in 24.84s                                     (Exit 0)
      Baseline vor dem Durchgang: 241 passed  →  +12 = 253, Baseline NICHT gesunken.

$ cd frontend && node --check app.js                                 (Exit 0)

$ cd frontend && for f in tests/*.js; do node "$f" app.js; done
tests/test_conv_code_live_stream.js  Exit=0
tests/test_diff_darstellung.js       Exit=0
tests/test_options_assistent.js      Exit=0
tests/test_quiz_ende.js              Exit=0
tests/test_quiz_geo.js               Exit=0
tests/test_quiz_rahmen_quelle.js     Exit=0
tests/test_ref_loeschen_ui.js        Exit=0
tests/test_serielles_tippen.js       Exit=0
```

Auszug `node tests/test_ref_loeschen_ui.js app.js`:

```
A) Ein Fehlschlag wird SICHTBAR gemeldet (Vollbild-Referenzliste)
  OK   Fehlschlag wird als NICHT geloescht gemeldet
  OK   Erfolg erst NACH Pruefung der Antwort
  OK   kein Fake-Erfolg direkt nach blindem fetch
B) Es wird NIE eine leere/undefined ID gesendet
  OK   URL nutzt NICHT das rohe r.ref_id
  OK   kein alter Confirm-Bug (!window.confirm && ...)
C) Referenzen OHNE Ausschnittbild sind gekennzeichnet
  OK   Badge fuer Zeilen ohne Bild
  OK   alter blinder Loesch-Button entfernt
D) "Alle Referenzen löschen" wertet die Antworten aus
  OK   Sammelmeldung nennt NICHT geloeschte

  --> Fehler: 0
```

Geänderte Dateien gesamt: `backend/app/services/gesichter_service.py`, `frontend/app.js`, `frontend/index.html`, **neu** `backend/tests/test_gesichter_ref_loeschen.py`, **neu** `frontend/tests/test_ref_loeschen_ui.js`, diese Datei.

---

## 5. Offene Punkte

1. **Zählung der Referenzen ohne Bild am echten Bestand** — der Katalog dieses Rechners ist leer; die tatsächliche Zahl auf Sebastians Handy ergibt sich beim nächsten Öffnen der Referenzliste (Abzeichen „⚠️ ohne Bild"). Einmal nachsehen.
2. **Migration läuft beim ersten `GET /referenzen`** — sie schreibt die Katalog-Datei neu (nur `ref_id`). Am Gerät prüfen, dass die Referenz-Zahl und die Jahre **unverändert** bleiben und die Log-Zeile „fehlende ref_id nachgetragen (Migration)" einmal erscheint.
3. **Ende-zu-Ende am Handy**: eine einzelne Referenz löschen → Zeile verschwindet nach Neuladen der Liste, **Person und alle anderen Referenzen bleiben**; danach eine ID absichtlich kaputt schicken → es muss sichtbar „⚠️ NICHT gelöscht: …" stehen (kein stiller Erfolg).
4. **„Alle löschen"** meldet jetzt ehrlich — bei einem Testlauf mit absichtlich fehlschlagender Einzel-Anfrage muss „X gelöscht, Y NICHT gelöscht" erscheinen.
5. Weiterhin **bewusst nicht** implementiert: automatisches Aufräumen von Referenzen ohne Bild (sie werden gekennzeichnet und sind einzeln löschbar, aber nicht von selbst entfernt — Personendaten werden nicht autonom gelöscht).
