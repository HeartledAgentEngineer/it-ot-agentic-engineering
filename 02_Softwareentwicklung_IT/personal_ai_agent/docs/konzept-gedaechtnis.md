# Konzept: Gedächtnis (Erinnerungen) — Ist-Zustand, Schwächen, Optionen

**Projekt:** `personal_ai_agent` (02_Softwareentwicklung_IT)
**Stand:** 25.09.2026
**Auslöser (Sebastian, sinngemäß):** *„Ich müsste das ganze Gedächtniskonzept noch mal
überdenken, weil die Erinnerungen sind auch ziemlich schlecht. Ich habe einfach nur nix
für Erinnerungen — das müssen wir deutlich verbessern."*
**Ziel des Dokuments:** Entscheidungsgrundlage. Kein großer Umbau — erst Befund, dann
Reihenfolge. Ein offensichtlicher Fehler (Erinnerungen waren in der Oberfläche nicht
sichtbar, obwohl sie existieren) ist unten unter „§6 Minimal gefixt" belegt behoben.

**Prüfbefehle (Stand dieses Dokuments, beide grün):**
- Backend: `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **263 passed** (vorher 253)
- Frontend: `node --check app.js` + `for t in tests/test_*.js; do node $t app.js; done` → **9/9 grün**
  (vorher 8, neu: `tests/test_gedaechtnis_ui.js`)

**Keine echten Erinnerungsinhalte in diesem Dokument.** Es stehen nur Zahlen, Feldnamen
und Strukturen darin. Alle Tests laufen in `tmp_path`, nie gegen den echten Bestand.

---

## 1. Ist-Zustand (belegt am Code und am laufenden System)

### 1.1 Wo Erinnerungen ERZEUGT werden — und ob das im Chat läuft

| Schritt | Ort | Was passiert |
|---|---|---|
| Auslöser | `backend/app/services/chat_verlauf.py:342-402` | `finish_exchange()` schreibt den Austausch in den Verlauf und ruft danach den injizierten Extraktor (`:394-399`). Er läuft bei **jedem** Austausch — auch wenn die Antwort von Hermes kam (`backend/app/router/chat.py:1634`). |
| Verdrahtung | `backend/app/router/chat.py:53-56` | `chat_verlauf.setze_memory_extractor(memory_service.extract_and_store_memories)` |
| Was gilt als erinnerungswürdig | `backend/app/services/llm_service.py:655-735` | Ein **LLM-Aufruf je Austausch** entscheidet. Der Prompt (`:678-706`) ist bewusst streng: „Der Prüfstein ist die Haltbarkeit, nicht die Wichtigkeit", nichts aus der Assistenten-Antwort, nichts Erschlossenes, höchstens 3 Einträge, `[]` ist ausdrücklich erlaubt. |
| Ablage | `backend/app/services/memory_service.py:255-274` | Jeder Fakt ≥ 11 Zeichen wird gespeichert — fest `category="fact"`, `importance=3`. |
| Zweiter Schreiber | `backend/app/router/auftraege.py:174-186` | Kommentare an einen laufenden Hermes-Auftrag, **nur** wenn `hermes_hat_mehrwert(text)` sie für persönlich wertvoll hält. |

**Läuft das?** Ja, messbar. `GET /api/health` des Handys (25.09.2026, 10:07, über ADB):
`{"status":"ok","llm_configured":true,"memory_count":175}`.
Am 13.08.2026 waren es 70 (`chroma_data/sicherung-handy-gedaechtnis-2026-08-13_2004.json`) —
der Bestand wächst also, die Extraktion arbeitet.

### 1.2 Wo sie GESPEICHERT werden

- **Kein ChromaDB.** `backend/app/db/chroma_client.py:1` — „Simple JSON-based memory store
  (drop-in replacement for ChromaDB on ARM)". Der Name `chroma_client` ist historisch.
- Pfad: `settings.chroma_persist_dir` (`backend/app/config.py:87`) = `BASE_DIR / "chroma_data"`
  (`config.py:12`) → Datei `memory_store.json` (`chroma_client.py:24`).
- Format: JSON-Liste, Eintrag =
  `{id, content, category, importance, timestamp, embedding, conversation_id?}`
  (`chroma_client.py:62-72`). `embedding` ist eine Liste aus Fließkommazahlen oder `null`.
- Geschrieben wird atomar über eine Temp-Datei? **Nein** — `_persist()` (`:160-164`) schreibt
  direkt in die Datei. (Für später relevant: ein Absturz mitten im Schreiben kostet den
  Bestand; der Chat-Verlauf hat dafür Backups, das Gedächtnis nicht.)

**Bestände, die ich sehen kann:**

| Ort | Umfang | Anmerkung |
|---|---|---|
| Handy (Termux, echt) | **175** Erinnerungen | aus `GET /api/health`; die Datei selbst ist app-privat (`/data/data/com.termux/...`, `Permission denied`), bewusst nicht angefasst |
| PC-Arbeitskopie | 3 Erinnerungen | `chroma_data/memory_store.json`, alle mit Vektor, Zeitraum 13.08.2026 |
| Handy-Sicherung 13.08.2026 | 70 Einträge | 59 verschiedene Normalformen → **11 wortgleiche Dubletten (16 %)**, entstanden vor dem Dedup-Fix vom 13.08. |

Kategorien im Bestand: **nur `fact`**. `importance`: **nur 3**. Das Modell erlaubt
`fact|preference|context|project` und `importance 1-5` (`backend/app/models.py:93-101`) —
drei Kategorien und vier von fünf Stufen sind toter Code.

### 1.3 Wo sie GELESEN werden

- Chat (nicht-streamend): `backend/app/router/chat.py:327-329` `retrieve_relevant_memories(..., top_k=5)`
- Chat (streamend, der Weg des Handys): `chat.py:1746` dito; Übergabe an das Modell `chat.py:1834`
- Antwortfeld: `memories_used=len(memories)` (`chat.py:515`, `:1874`)
- Hermes-Delegation: `chat.py:941-949` (`top_k=3`) und `kontext_service.py:85-92`
- **In den Prompt:** `backend/app/services/llm_service.py:472-475` + `_build_memory_context()`
  (`llm_service.py:277-286`) → Block `## GEMERKTE INFORMATIONEN AUS FRÜHEREN GESPRÄCHEN:`
  mit je `- <Inhalt> (Kategorie: <Kategorie>)`.

**Nachgemessen** (Lese-Probe gegen die PC-Arbeitskopie, nur Aggregate ausgegeben):
```
Speicherdatei: .../chroma_data/memory_store.json
Anzahl Erinnerungen: 3
retrieve_relevant_memories -> 3 Eintraege (top_k=5 angefragt)
_build_memory_context -> 403 Zeichen, 3 Eintraege
Blockkopf vorhanden: True
```
→ Die Erinnerungen kommen **nachweislich** im Prompt an. Das war nicht die Lücke.

**Wichtige Eigenschaft** (`memory_service.py:207-251`, `ALLES_MITGEBEN_BIS = 300` in `:54`):
Bei ≤ 300 Einträgen wird **nicht ausgewählt** — es wandert der *ganze* Bestand in jeden
Prompt, `top_k` ist wirkungslos (im Test festgehalten). Bei 175 Einträgen sind das grob
11.000 Zeichen ≈ 2.500 Token **je Frage** — unabhängig vom Thema der Frage.

### 1.4 Die Oberfläche — der Kern des Befunds

- **Das Frontend ruft `/api/memory` nie auf.** `grep -rn "api/memory" frontend/` → **kein Treffer**.
- Einziges sichtbares Element war ein Text im Fuß: `frontend/index.html` `<span class="footer-note">Gedächtnis aktiv</span>`,
  von `app.js` (`updateFooterNote`) zu **„N Erinnerungen"** umgeschrieben — eine Zahl, sonst nichts.
- Das Backend hielt dagegen alles bereit (`backend/app/router/memory.py`):
  `GET /api/memory` (Liste, `:16-35`), `POST /api/memory` (`:38-51`), `GET /api/memory/count` (`:54-61`),
  `POST /api/memory/vektoren` (`:64-75`), `POST /api/memory/wiederholungen` (`:78-95`, Trockenlauf),
  `DELETE /api/memory/clear` (`:98-110`), `DELETE /api/memory/{id}` (`:115-131`).

**Das ist der Kern von „ich habe einfach nur nix für Erinnerungen":** Der Agent lernte 175
Dinge über Sebastian, und kein einziges davon war in der App zu sehen oder zu entfernen.

### 1.5 Suche und der 0-Treffer-Fall

- **Keine Vektordatenbank.** `search_memories()` (`chroma_client.py:77-111`) rechnet mit
  `numpy` die Kosinus-Ähnlichkeit über alle gespeicherten `embedding`-Felder und nimmt die
  Top-k. Reihung, kein Index — bei 175 Einträgen unkritisch.
- **Lokale Embeddings fehlen auf beiden Geräten.** `memory_service.py:22-32` lädt
  `sentence-transformers` in einem `try/except`; Messung am PC: „Embedding model NOT
  available (No module named 'sentence_transformers')". Auf ARM-Android ist das derselbe
  verlorene Kampf wie im Wissensspeicher (`docs/embeddings-auf-termux.md`).
- **Fallback 1:** `mistral_vektor()` (`memory_service.py:57-88`) bettet über die
  Mistral-API ein — **braucht `MISTRAL_API_KEY`**. Fehlt der Schlüssel, bleibt
  `embedding = null`.
- **Fallback 2 (der harte Rand):** Trägt kein Eintrag einen Vektor, liefert
  `search_memories` leer, und `retrieve_relevant_memories` nimmt **„die neuesten"**
  (`:249-251`). Das ist der Zustand, den der Kommentar in `:207-221` beschreibt: *„Bei 16
  Erinnerungen sah der Agent elf davon nie."*
- **0 Erinnerungen / 0 Treffer:** sauber. `count()==0` → `[]` (`:222-224`); `_build_memory_context([])`
  → leerer String, kein leerer Block im Prompt (nachgemessen: `True`).
- **Nachrüsten** geht nur von Hand: `POST /api/memory/vektoren` (`memory_service.py:286-306`).
  Ohne Oberfläche ist dieser Weg für Sebastian unerreichbar — ein Knopf dafür istKleinigkeit.

### 1.6 Personen ↔ Erinnerungen: keine Brücke

`backend/app/services/gesichter_service.py` importiert `memory_service` **nicht** (Importe
`gesichter_service.py:21-28`). Der Personen-Katalog geht als Text-Block direkt in den Prompt
(`backend/app/router/chat.py:393-423`). Umgekehrt entsteht aus dem Lernen einer Person
**keine** Erinnerung. Zwei Gedächtnisse, die nichts voneinander wissen.

---

## 2. Schwächen — mit Beleg

1. **Keine Anzeige (Kern).** Frontend ruft `/api/memory` nie auf; einzige Anzeige war der
   Zähler im Fuß (`app.js:1440-1445`). Folge: 175 gelernte Fakten waren unsichtbar. — *behoben, §6*
2. **Keine Pflege in der Oberfläche.** Einzelnes Löschen gab es nur als HTTP-Aufruf
   (`router/memory.py:115-131`), im UI unmöglich; der einzige erreichbare Weg war `/clear`
   — alles oder nichts. Das ist genau das Muster, das beim Gesichter-Katalog schon einmal
   weh tat (`docs/changelog-2026-09-15-ref-loeschen.md`). — *Einzel-Löschen jetzt im Blatt, §6*
3. **Alles oder nichts im Prompt.** `ALLES_MITGEBEN_BIS = 300` (`memory_service.py:54`):
   bei 175 Einträgen wandert der komplette Bestand in *jede* Frage, `top_k=5` ist
   wirkungslos (Test `test_kleiner_speicher_wandert_vollstaendig_in_den_prompt`). Kein Bezug
   zur Frage, keine Gewichtung. Bei 175 Einträgen ≈ 2.500 Token pro Frage — und im Text
   stehen auch Einträge, die mit der Frage nichts zu tun haben.
4. **Keine Kategorien, keine Wichtigkeit, kein Alter.** Alles wird als `fact` mit
   `importance=3` gespeichert (`memory_service.py:262-269`); `importance` wird **nirgends
   gelesen** (nur geschrieben und durchgereicht: `chroma_client.py:66,107`, `models.py:98,110`);
   `timestamp` taucht nur in der API-Antwort auf (`router/memory.py:27`). Kein Verfall, keine
   Rangfolge, keine Gruppierung.
5. **Die Wiederholungs-Prüfung schluckt echte Änderungen.** `AEHNLICHKEIT_SCHWELLE = 0.90`
   auf Zeichenähnlichkeit (`memory_service.py:49,98-104`). Gemessen an konstruierten Paaren,
   die die Regel als **dieselbe** Tatsache verwirft:
   | Paar | Ähnlichkeit | Folge |
   |---|---|---|
   | „… seit **zehn** Jahren in der Automatisierung" vs. „seit **elf** Jahren" | 0,950 | neue Fassung wird verworfen |
   | „Ich habe einen Hund namens **Rex**" vs. „… **Max**" | 0,933 | dito |
   | „Der Nutzer trinkt morgens **Kaffee**" vs. „… **Tee**" | 0,918 | dito |
   | „Meine Schwester heißt **Anna**" vs. „… **Maria**" | 0,906 | dito |
   | „Geburtstag: **3.** Mai **1984**" vs. „**5.** Mai **1985**" | 0,905 | dito |
   | „Mein Lieblingsessen ist **Pizza**" vs. „**Pasta**" | 0,897 | bleibt gespeichert (unter der Schwelle) |

   (Alle sechs Werte gemessen mit derselben Funktion wie im Dienst:
   `difflib.SequenceMatcher(None, normalisiert(a), normalisiert(b)).ratio()`.)

   Im echten Altbestand (Sicherung 13.08.) betrifft das 2 von 59 verschiedenen Fakten — also
   real, aber selten. **Die Wirkung ist trotzdem unangenehm:** Eine *Korrektur* (richtiger
   Name, richtiges Datum) prallt am alten, falschen Eintrag ab. Der Test
   `test_gleicher_anfang_gilt_schon_als_wiederholung` hält den Ist-Zustand fest.
   Der Kommentar in `memory_service.py:45-48` sagt ausdrücklich *„Lieber eine Dublette zu
   viel als ein Fakt zu wenig"* — die Schwelle tut derzeit das Gegenteil.
6. **Kein Bezug zu Personen, Orten, Daten.** Ein Eintrag ist ein freier String
   (`chroma_client.py:62-72`). Kein `person_id`, kein Ort, kein Bezugsdatum, keine Quelle
   (welches Gespräch, welcher Tag). Ohne Quelle lässt sich ein Eintrag nicht nachprüfen —
   Vertrauen entsteht so nicht. Und: keine Brücke zum Gesichter-Katalog (§1.6).
7. **Keine Bestätigung durch den Nutzer.** Das Modell legt an, ändert und verwirft
   (`memory_service.py:125-128`), Sebastian sah davon nichts. Er kann weder „stimmt" noch
   „stimmt nicht" sagen — bis heute.
8. **Kein Lebens-Log, kein Import.** Erinnerungen entstehen nur aus dem *Moment* eines
   Austauschs. Der eigene Verlauf (`chroma_data/conversations.json`, append-only,
   `chat_verlauf.py:166`) und der Wissensspeicher (Schwesterprojekt, 35.893 Nachrichten /
   26.354 Chunks laut `docs/embeddings-auf-termux.md`) sind **nicht** angebunden. Seine
   Vergangenheit liegt da — das Gedächtnis weiß nichts davon.
9. **Nachrüsten/Reparieren nur per HTTP.** `POST /api/memory/vektoren` und
   `POST /api/memory/wiederholungen` (Trockenlauf!) existieren, aber ohne Oberfläche nur mit
   `curl` erreichbar.

---

## 3. Konzept-Optionen

Aufwände sind **Schätzungen des Agenten** (nichts davon ist gemessen, außer dem unter §6
bereits Gebauten). Risiko = Gefahr für Bestandsdaten/Alltag, nicht Aufwand.

### Option A — Sichtbarkeit sofort (klein)

**Was:** Erinnerungen im Chat zeigen (Blatt/Zeitstrahl), Einzel-Löschen, später Bearbeiten,
Bestätigen, Filtern.

| Teil | Aufwand | Status |
|---|---|---|
| A1 Blatt im Chat + Einzel-Löschen + Tests | ~1,5 h | **gebaut (25.09.), §6** |
| A2 Text eines Eintrags bearbeiten (Backend-Route fehlt: `PATCH /api/memory/{id}`) | 2–3 h | offen |
| A3 „Stimmt / stimmt nicht" als Knopf am Eintrag (Rückmeldung wandert als Feld in den Eintrag) | 3–4 h | offen |
| A4 Zeitstrahl: nach Monat gruppiert, Filter Kategorie/Person | 3–4 h | offen |
| A5 Kopfzeile mit Zahlen (je Kategorie, ältester/neuester) | ~1 h | offen |

**Wirkung im Alltag:** Groß. Er sieht zum ersten Mal, was der Agent über ihn glaubt — und
kann Falsches wegnehmen. Das ist die Voraussetzung für Vertrauen in alles Weitere.
**Risiko:** Gering (nur Lesen + Einzel-Löschen, kein „Alle löschen").
**Was NICHT geht:** Macht die Einträge nicht *besser*. Zeigt nur, was da ist. Ein falscher
Eintrag, den man nicht liest, bleibt falsch. Und: Ohne Vektoren (Handy!) kann das Blatt
nicht nach Bedeutung suchen — es listet nur.
**Nicht Teil von A:** Ob ein Eintrag *stimmt*, entscheidet weiter der Nutzer per Blick.

### Option B — Qualität / Festigung (mittel)

**Was:** bessere Extraktion, entschärftes Dedup, Kategorien/Wichtigkeit, Relevanz statt
„alles oder nichts", Brücke Personen ↔ Erinnerungen.

| Teil | Aufwand | Wirkung |
|---|---|---|
| B1 Extraktions-Prompt: Kategorien (`preference`/`project`/`context`) wirklich nutzen, Ort/Datum/Person mitgeben, `importance` schätzen lassen | 2–3 h | Einträge werden sortierbar und später filterbar |
| B2 Dedup-Regel: Ähnlichkeit entschärfen (oder nur noch Zeichen-Gleichheit + Tippfehler-Nähe), Korrekturen **immer** durchlassen; Trockenlauf-Bericht im Blatt | 2–3 h | **behebt die stille Datenlücke aus §2.5** |
| B3 Wichtigkeit/Alterung: `importance` in der Reihenfolge nutzen, „Vergessen" (Alter × Wichtigkeit) | 3–4 h | kurzer Prompt, Wichtiges bleibt |
| B4 Relevanz statt Vollbestand: Vektoren sicherstellen (Mistral-Key nötig — Frage verlässt das Gerät!) + Wortsuche als zweiter Weg, damit es auch ohne Netz nicht auf „die neuesten" zurückfällt | 4–6 h | **verhindert den 300er-Absturz (§1.5)** |
| B5 Brücke Personen ↔ Erinnerungen: Katalog-Erkenntnisse schreiben Erinnerungen („Person gelernt: …"), und Einträge nennen Personen | 3–4 h | der Agent verknüpft Menschen mit Geschichte |
| B6 Qualitäts-Set: 20 Beispielsätze → was wird gespeichert/verworfen, als Testdatei + Bericht | 3–4 h | macht Qualität messbar statt gefühlt |

**Summe B ≈ 17–24 h.**
**Risiko:** Mittel. Jede Änderung an der Extraktion verändert, was künftig gespeichert wird;
Bestandsdaten bleiben unberührt. B4 berührt die Datenschutzgrenze (Frage zu Mistral).
**Was NICHT geht:** Fehlerfrei wird es nie — ein LLM entscheidet, was ein Fakt ist. Dedup
über *Bedeutung* (statt Zeichen) braucht Embeddings; ohne Schlüssel bleibt es beim
Zeichenvergleich. Personenbezug gilt nur für **neue** Einträge — die 175 alten tragen keinen
Personenverweis (nur über eine vorsichtige Nachrüstung, wenn Sebastian das will).

### Option C — Lebens-Log / Import (groß)

**Was:** Zeitstrahl aus Chat-Verläufen, Bildern, später WhatsApp/pCloud; durchsuchbare
Historie; „zweites Gehirn".

| Teil | Aufwand | Anmerkung |
|---|---|---|
| C1 Import aus dem eigenen Verlauf (`conversations.json`, append-only) in Chargen mit Fortschritt + Kostenbremse | 4–6 h | technisch direkt machbar, Verlauf liegt lokal |
| C2 Import aus dem Wissensspeicher (35.893 Nachrichten, SQLite im Schwesterprojekt) | 6–10 h | Chunking, Dubletten, Beleg-Zitat je Eintrag |
| C3 Zeitstrahl-Ansicht (Jahre/Monate, Themen, Personen, Orte) + Suche | 6–8 h | braucht A4 + B3 vorher |
| C4 Bilder/pCloud (Personen, Orte) | 8–12 h | **heikel**: Gesichter + Personen ohne Einwilligung; nur mit Sebastians ausdrücklicher Entscheidung |
| C5 WhatsApp (Export) / pCloud-Anbindung | 8–16 h | Format, Aufwand, Recht — offene Fragen |

**Summe C ≈ 32–52 h.**
**Risiko:** Hoch, wenn es ohne B geht (siehe unten). Mit B: mittel.
**Was NICHT geht:**
- **Der 300er-Absturz:** Ab 300 Einträgen schaltet das Gedächtnis auf Auswahl um. Fehlen
  dann Vektoren (kein lokaler Embedder, kein Mistral-Key), greift der Rückfall „die
  neuesten" (`memory_service.py:249-251`) — dann **erreicht der importierte Lebenslauf den
  Prompt nie**, weil er alt ist. Ein Lebens-Log ohne B4 ist ein Datenlager, kein Gedächtnis.
- **Kosten/Zeit beim Import:** Ein Import über tausende Nachrichten heißt einen
  LLM-Extraktionsaufruf **je Nachricht** (heute schon einer je Chat-Runde). Das braucht eine
  Kostenbremse (Chargen, Limit, Fortschrittsanzeige) — sonst läuft es unbemerkt lange.
- **Rückwirkende Extraktion ist schwerer als im Moment:** Heute urteilt das Modell über
  einen frischen Austausch; über einen Verlauf von 2023 muss es ohne Kontext entscheiden.
  Erwartbar: mehr Fehleinträge → deshalb A/B vorher.
- **Bilder/WhatsApp:** Personen- und Fremddaten. Das ist keine Technik-, sondern eine
  Entscheidungsfrage (siehe §7).

---

## 4. Empfehlung (Reihenfolge)

1. **A1 ist gebaut** — Sebastian soll es zuerst ansehen (Handy: `git pull`, App neu laden).
   Ohne diesen Blick ist jede weitere Qualitätsdebatte abstrakt.
2. **Dann B1, B2, B4, B3** (in dieser Reihenfolge), **dann B5**.
   Grund: B2 behebt eine *stille* Datenlücke (Korrekturen verschwinden), B4 entfernt die
   Klippe bei 300 Einträgen. Beides muss **vor** dem Import stehen — sonst wird das
   Lebens-Log in einen Speicher geschüttet, der entweder alles oder das Falsche mitnimmt.
3. **Dann C1** (Import des eigenen Verlaufs) — der billigste Teil des Lebens-Logs, lokal
   vorhanden, mit sofort sichtbarem Ergebnis im Blatt.
4. **Dann C3/C2**, zuletzt und nur nach Entscheidung C4/C5.
5. **A2/A3/A4** sind kleine, jederzeit einschiebbare Scheiben (je 1–4 h) — A3 („stimmt /
   stimmt nicht") ist der wirksamste Vertrauens-Baustein und kann vorgezogen werden.

**Kurz:** Sichtbarkeit → Korrigierbarkeit → Qualität → Menge. Nicht umgekehrt.
Ein Lebens-Log über 175 ungeprüfte Einzeiler multipliziert nur das Misstrauen.

---

## 5. Sofort klein fixbar (jeweils eigenständig, kein Konzept nötig)

| # | Sache | Aufwand | Status |
|---|---|---|---|
| 1 | Erinnerungen ansehen (Blatt im Chat) | ~1 h | **erledigt (§6)** |
| 2 | Einzelnen Eintrag entfernen | ~0,5 h | **erledigt (§6)** |
| 3 | Knopf „Dubletten aufräumen" im Blatt (Backend `POST /api/memory/wiederholungen` mit Trockenlauf existiert) | ~1 h | offen |
| 4 | Knopf „Vektoren nachrüsten" (Backend `POST /api/memory/vektoren` existiert; braucht Mistral-Key) | ~0,5 h | offen |
| 5 | Filter „nur Vorlieben / nur Vorhaben" — Datenfeld existiert, wird nur nie gefüllt (kommt mit B1) | 1–2 h | offen |
| 6 | Bearbeiten eines Eintrags (Backend-Route fehlt) | 2–3 h | offen |
| 7 | Wichtigkeit im Blatt setzen (Modell erlaubt 1–5, Extraktion schreibt immer 3) | 2–3 h | offen |

---

## 6. Minimal gefixt am 25.09.2026 (mit Begründung)

**Befund:** Erinnerungen existieren (175 auf dem Handy), sie gehen nachweislich in den
Prompt (§1.3) — aber die Oberfläche rief `/api/memory` **nie** auf (§1.4). Sichtbar war
eine Zahl. Das ist der offensichtliche Fehler, den Sebastian als „ich habe einfach nur nix
für Erinnerungen" beschreibt; er ist ohne Konzeptentscheidung behebbar, weil das Backend
alles bereitstellt.

**Änderung (Frontend, `code + docs`):**
- `frontend/index.html`: Der Fuß-Text „Gedächtnis aktiv" ist jetzt ein **Knopf**
  (`#gedaechtnis-btn`, Zeile 142) und öffnet ein Blatt `#memory-sheet` (Zeile 170-179, Liste
  `#memory-list` Zeile 176, Hinweis `#memory-hint` Zeile 177) nach
  dem Muster des Modell-/Gesprächs-Blatts. Cache-Bump: `app.js?v=20260925A`,
  `style.css?v=20260925A`.
- `frontend/app.js`: `zeichneErinnerungen()` (Liste, jüngste zuerst, Art + Datum),
  `erinnerungenZahl()` (echte Gesamtzahl aus `/api/memory/count` — die Liste ist bei 200
  gedeckelt und `total` in der Antwort ist nur die Zahl der *gelieferten* Einträge),
  `loescheErinnerung()` (DELETE, mit Rückfrage), Öffnen/Schließen über Knopf, ×,
  Hintergrund und Escape.
- **Bewusst NICHT gebaut:** „Alle löschen". Ein Fehlgriff wäre nicht rücknehmbar; das
  Einzel-Löschen löst genau Sebastians Problem (ein falscher Eintrag kostete bisher alles).
- **Fehler werden sichtbar gemeldet** — Lade- und Löschfehler landen als Text in der
  Hinweiszeile („… der Eintrag ist noch da"). Das ist die Lehre aus dem Referenz-Löschen
  vom 20.09.2026 (`docs/changelog-2026-09-15-ref-loeschen.md`): eine UI, die Erfolg
  vortäuscht, zwingt zum Rundumschlag.
- Inhalte werden escaped (`escapeHtml`) — Erinnerungstexte sind Nutzerdaten und dürfen kein
  HTML werden.

**Tests dazu:**
- `backend/tests/test_memory_api.py` (neu, 10 Tests): Liste/Anlegen/Zähler über die echten
  Router-Funktionen, Einzel-Löschen inkl. 404, Dedup, Trockenlauf beim Aufräumen, leerer
  Speicher erzeugt keinen Prompt-Block, kleiner Speicher wandert vollständig, Vektor-Nachrüstung.
  Ein Test hält den Ist-Zustand aus §2.5 fest (`test_gleicher_anfang_gilt_schon_als_wiederholung`).
- `frontend/tests/test_gedaechtnis_ui.js` (neu, 41 Prüfungen): Blatt/Knopf vorhanden, Liste
  vom echten Endpunkt, Leerfall erklärt, Fehlschläge sichtbar, Löschen prüft die Antwort,
  kein „Alle löschen", Escaping, Verdrahtung, Cache-Bump.
- Laufzeit-Nachweis (außerhalb des Repos, Arbeitsdatei): die echten Funktionen aus `app.js`
  gegen die echte Antwort des laufenden Backends ausgeführt — 3 Testeinträge wurden mit
  Art/Datum/Entfernen-Knopf gezeichnet, der Löschfehler (HTTP 500) wurde sichtbar gemeldet,
  der leere Bestand erklärt.

**Echte Testausgaben (in dieser Sitzung ausgeführt):**
```
cd backend && .venv/Scripts/python -m pytest tests/ -q      →  263 passed in 25.59s
   (ohne die neue Datei eines PARALLEL laufenden Strangs, siehe Hinweis unten)
node --check app.js                                          →  OK
for t in tests/test_*.js; do node $t app.js; done            →  9/9 OK
  (neu: tests/test_gedaechtnis_ui.js  →  → Fehler: 0)
```
Baseline vorher: **253 passed** — gesunken ist nichts.

> **Hinweis zum Gesamtlauf (25.09.2026, 10:20):** Während dieser Arbeit hat ein **zweiter
> Strang** im selben Repo an der Verlaufs-Konsistenz gearbeitet (`backend/app/router/chat.py`,
> `backend/app/services/chat_verlauf.py` geändert, `backend/tests/test_verlauf_konsistenz.py`
> neu). Dessen vier Tests sind derzeit **rot** (Doppelte User-Nachricht wird noch nicht in
> allen Fällen erkannt; Fehlerdetails eines unbekannten Chats enthalten fremden Verlauf).
> Mit dieser Arbeit hat das nichts zu tun — ohne die Datei des Parallel-Strangs läuft die
> Suite mit **263 passed** durch (`--ignore=tests/test_verlauf_konsistenz.py`). Die roten
> Tests gehören dem anderen Strang und wurden hier bewusst **nicht** angefasst.

**Nicht angefasst:** `backend/app/services/memory_service.py`, `chroma_client.py`,
Extraktion, Dedup, Prompt-Zusammenbau. Kein Bestand gelöscht oder verändert. Alle Tests
laufen in `tmp_path`; der echte Speicher wurde nur gelesen (Probe) und die echten
Erinnerungen wurden nirgends im Klartext ausgegeben.

---

## 7. Offene Fragen an Sebastian

1. **Datenschutzgrenze Suche:** Sollen Erinnerungen nach *Bedeutung* durchsucht werden
   können? Dafür muss die **Frage** das Gerät verlassen (Mistral-Embeddings) — die
   gefundenen Inhalte nicht. Ohne das bleibt es beim Zeichenvergleich bzw. „die neuesten".
2. **Bestätigen vor oder nach dem Speichern?** Künftig erst fragen („soll ich mir das
   merken?") kostet Reibung im Alltag, danach fragen (wie heute, mit Blatt + Löschen)
   kostet Vertrauen. Was ist dir lieber?
3. **Personen im Gedächtnis:** Sollen Erinnerungen an Personen gebunden werden (Pedi,
   Julian …)? Dann stehen Personennamen dauerhaft im Erinnerungstext — gewollt, oder soll
   der Bezug nur über den Katalog laufen?
4. **Import-Umfang und Kostenbremse:** Der Verlauf/Archiv-Import bedeutet einen
   LLM-Aufruf je Nachricht. Wie viel darf das kosten, und soll er nachts laufen (Termux-Job)
   oder angestoßen mit Fortschrittsanzeige?
5. **Vergessen:** Sollen alte, unwichtige Einträge verfallen (Alter × Wichtigkeit) oder soll
   alles für immer bleiben?
6. **Korrektur-Regel (§2.5):** Soll eine geänderte Fassung („richtiges Geburtsdatum")
   den alten Eintrag künftig **ersetzen**, oder soll beides stehen bleiben (dann sichtbar
   als „alt/neu" im Blatt)?
7. **Bilder/WhatsApp/pCloud:** Sollen Fotos (Personen/Orte) und Chat-Exporte überhaupt ins
   Lebens-Log? Das sind Daten über andere Menschen — hier entscheidest du, nicht der Code.
