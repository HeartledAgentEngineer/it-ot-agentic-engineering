# Feinauftrag N22 — Nächtliche Nachpflege des Archiv-Index (inkrementell, idempotent)

**Auftraggeber:** Planer (Hauptagent, Nachtlauf 29.09.2026)
**Ausführer:** Hermes-Subagent (`deepseek-v4.1-flash`) — Codex ist live geprüft
**gesperrt** („You've hit your usage limit … try again at Oct 15th, 2026").
**Rollen:** Der Ausführer baut **nur** hier (Code + Tests + Changelog), macht
**keine** git-Befehle. Der Prüfer ist ein **frischer** Subagent einer **anderen**
Modellfamilie (`z-ai/glm-5.2`) und führt den Prüfbefehl selbst aus.

---

## 1. Der belegte Befund (vom Planer gemessen, nicht behauptet)

Alles nur lesend (`mode=ro`), am echten Bestand:

| Messung | Wert |
|---|---|
| `Chats von GPT, GEMINI, Claude/db/memory.db` (Quelle) | 230.391.808 B — `messages` **282.029**, `chunks` **52.679** |
| `db/archiv_index.db` (Ziel) | 447.496.192 B — `nachrichten` **282.029**, `chunks` **52.679**, `chunks_fts` **52.679**, `vektoren` **52.679**, `gespraeche` **1.590** |
| Chunks **ohne** Vektor (`hat_vektor = 0`) | **0** |
| `max(id)` in `nachrichten` / `chunks` | 282.028 / **52.679** |
| `meta` u. a. | `modell openai/text-embedding-3-small`, `dimension 1536`, `vektor_speicher float16`, `kosten_usd 0.320717` |

**Damit steht fest:** der Index ist heute **vollständig in Sync** — es gibt
**keinen** Rückstand. Das ist der Grund für diesen Auftrag: Bisher kann der Index
nur **komplett neu gebaut** werden (`backend/scripts/archiv_index_bauen.py`,
8 Minuten, 447 MB, alle Einbettungen neu bezahlt). Sobald das Schwesterprojekt
neue Chats nach `db/memory.db` importiert, fehlt ein **inkrementeller** Weg.

**Der Messwert, der die Prüfung trägt:** Weil heute nichts fehlt, muss die
Wirkung auf **Kopien außerhalb des Repos** nachgewiesen werden (Schritt 5) —
nicht durch einen Lauf auf dem Original.

## 2. Was gebaut wird (genau ein Schritt)

**Neu: `backend/scripts/archiv_nachpflege.py`** — pflegt einen **bestehenden**
Index nach. Grenzen hart:

* **Nur anhängen, nie löschen, nie neu bauen.** Kein `DELETE`, kein `DROP`, kein
  `os.replace`/Neu-Schreiben der ganzen Datei, kein Tabellen-Neuaufbau. Ein Test
  prüft den Quelltext auf die Abwesenheit dieser Wörter (erlaubt sind
  `INSERT`, `UPDATE` auf `gespraeche`/`meta`, `CREATE TABLE IF NOT EXISTS`).
* **Quelle und Ziel nur lesend öffnen, wenn `--trocken`** (Standard): dann wird
  **nichts** geschrieben (Index-`sha256` und `mtime` bleiben gleich).
* **Kein Zugriff auf Bild-/Fotodaten, keine pCloud, kein Löschen, keine
  Geheimnisse in Ausgabe oder Dateien** (Schlüssel nur Länge/Maske).
* **Repo-Ziel wird verweigert:** liegt `--index` innerhalb des Projektordners
  (`personal_ai_agent`), Exit **2** mit deutscher Meldung — nichts geschrieben.

### 2.1 Erkennung „neu" (Kennung statt Zähler)

Nicht über `id`/Ordinal (die kann sich beim Neu-Import verschieben), sondern über
einen **Inhaltsschlüssel** (reine Funktionen, einzeln testbar):

* Nachricht: `schluessel_nachricht(conversation_id, timestamp, role, text)`
  = `sha1("conv\x1ftimestamp\x1frole\x1ftext")[:16]`
* Chunk: `schluessel_chunk(conversation_id, teil, beginn, ende, text)`
  = `sha1("conv\x1fteil\x1fbeginn\x1fende\x1ftext")[:16]`

Der Bestand im Index trägt alle Felder, die für den Schlüssel nötig sind — die
Schlüssel werden also **aus dem Index selbst** gerechnet, kein Schema-Umbau,
keine Zusatztabelle nötig.

### 2.2 Verhalten je Lauf

1. Bestandsschlüssel aus dem Index lesen (`nachrichten`, `chunks`).
2. Quelle (`memory.db`) **nur lesend** öffnen und in **Quellreihenfolge**
   (`ORDER BY id`) durchgehen.
3. **Neue** Nachrichten/Chunks einsammeln (nicht im Bestand) — alles andere
   zählt als `uebersprungen`.
4. Neue Zeilen **anhängen** mit `id = max(bestehende id) + 1` aufsteigend;
   `chunks.hat_vektor = 0`, `quelldatei` aus dem Bestand übernehmen, wenn das
   Gespräch bekannt ist, sonst `NULL` (das ist erlaubt und wird gezählt).
5. Neue Chunks in den **Volltextindex** hängen
   (`INSERT INTO chunks_fts(rowid, text) VALUES (?,?)`) und am Ende
   `INSERT INTO chunks_fts(chunks_fts) VALUES('optimize')`.
6. **Vektoren nur für neue Chunks** — und nur mit `--mit-vektoren` (Einbetter
   injizierbar, wie `archiv_index_bauen.EinbetterOpenRouter`; ohne Netz in Tests
   eine Attrappe). Ohne `--mit-vektoren` bleiben die neuen Chunks ehrlich
   `hat_vektor = 0` und werden im Bericht als „ohne Vektor" gezählt.
7. `gespraeche` **nur für berührte** Gespräche nachziehen
   (`INSERT OR REPLACE` mit den Aggregaten `count(*)`/`min(beginn)`/`max(ende)`
   über **den Index**, damit die Zahlen zum Index passen).
8. `meta` **ergänzen, nie entfernen**: `nachpflege_zuletzt` (ISO-Zeit),
   `nachpflege_lauf` (menschenlesbare Zeile mit den Zahlen), `nachpflege_neu_*`.
9. Bericht (Zahlen, keine Inhalte) als `dict` **und** als Text:
   `neu_nachrichten`, `neu_chunks`, `uebersprungen_nachrichten`,
   `uebersprungen_chunks`, `vektoren_gerechnet`, `ohne_vektor`, `tokens`,
   `kosten_usd`, `gespraeche_beruehrt`, `fehler`, `dauer_s`, `index_mb`.

### 2.3 Kommandozeile

```
cd backend
.venv/Scripts/python -m scripts.archiv_nachpflege --quelle-db <memory.db> --index <archiv_index.db> [--schreiben] [--mit-vektoren] [--stapel 100] [--stand <ISO>]
```

* `--trocken` ist **Standard**; geschrieben wird nur mit `--schreiben`.
* Fehlende Quelle oder fehlender Index → Exit **2**, deutsche Meldung, nichts
  geschrieben.
* `--stand` friert den Zeitstempel ein (für zwei byte-gleiche Läufe im Nachweis).
* **Idempotenz:** zweiter Lauf ohne Änderung → `neu_* = 0`, `vektoren_gerechnet = 0`,
  **kein** Schreibvorgang, Index-`sha256` **unverändert**.

## 3. Tests (offline, Pflicht)

`backend/tests/test_archiv_nachpflege.py` — **mindestens 28 Testfunktionen**,
alles ohne Netz, ohne Schlüssel, ohne echte Daten:

* Quell- und Ziel-Datenbank im `tmp_path` aus `app.services.archiv_suche.SCHEMA_SQL`
  gebaut; **erfundene** Texte („Probe-Nachricht", „Erwin", „Marga").
* Einbetter ist eine **Attrappe**; ein Test zählt die Aufrufe (nur neue Chunks).
* Geprüft werden u. a.: Schlüsselfunktionen (gleicher Inhalt = gleicher
  Schlüssel, geänderter Text = anderer); neue Nachricht wird erkannt; neue Zeile
  hängt **hinten** an (`id > max`); **FTS findet den neuen Text nach dem Lauf**;
  Vektorzeile für den neuen Chunk entsteht (Länge = `dimension * 2` bei float16);
  `hat_vektor` wird 1; `gespraeche`-Zahlen wachsen, `von`/`bis` stimmen;
  `meta` behält **alle** alten Schlüssel; **zweiter Lauf = 0 neu**;
  Trockenlauf schreibt nichts (shas gleich); Repo-Ziel Exit 2; fehlende Quelle
  Exit 2; defekte Zeile in der Quelle wird als `fehler` gezählt statt zu werfen;
  **Quelltext enthält kein `DELETE`/`DROP`** und keine pCloud-/Netz-Funktion;
  großer Bestand (z. B. 500 Nachrichten) läuft in einem Durchgang durch und
  liefert dieselben Zahlen wie ein zweiter Aufruf (Idempotenz).

## 4. Prüfbefehl (Gate)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
```

**Baseline in dieser Runde frisch gemessen (Planer): siehe Journal.**
Erwartung: Baseline + die neuen Testfunktionen, Exit **0**. Kein Commit ohne
grünes Tor — den Commit macht der Planer, nicht der Ausführer.

## 5. Nachweis am echten Bestand (Kopien, außerhalb des Repos)

Der Ausführer führt **nur lesende** Läufe am Original und alle Schreib-Läufe auf
**Kopien** unter `C:/Users/sebas/foto_sortierung/n22_probe/` aus
(Ordner anlegen, **nur kopieren** — die Originale bleiben unberührt, nichts wird
gelöscht oder verschoben):

1. **Original, Trockenlauf:** `--quelle-db <memory.db> --index <archiv_index.db>`
   (ohne `--schreiben`) → Erwartung `neu_nachrichten 0`, `neu_chunks 0`,
   `uebersprungen_*` = 282.029 / 52.679, Dauer nennen, danach **`sha256` des
   Originals vor/nach gleich** (beide Werte in den Changelog).
2. **Kopien** von `memory.db` und `archiv_index.db` anlegen (Größen nennen).
3. In der **Quell-Kopie** 3 erfundene Nachrichten und 1 erfundenen Chunk
   anhängen (eigene, klar als Probe erkennbare Texte).
4. Werkzeug auf die **Kopien** mit `--schreiben --mit-vektoren --stand <fest>`
   → Zahlen nennen: `neu_nachrichten 3`, `neu_chunks 1`, `vektoren_gerechnet 1`,
   Kosten (winzig, echte Zahl aus der API-Antwort), `fehler 0`.
5. **Volltext-Gegenprobe** auf der Index-Kopie: `chunks_fts MATCH` findet den
   Probebegriff (Trefferzahl nennen) — das ist der Plan-Punkt „eine neue
   Nachricht erscheint nach dem Lauf in der Suche".
6. **Zweiter Lauf** auf denselben Kopien → `neu_* 0`, `vektoren_gerechnet 0`,
   `sha256` der Index-Kopie **vor/nach gleich**.
7. `sha256` der **Originale** am Ende erneut prüfen und die Gleichheit nennen.
8. Kopien dürfen liegen bleiben (kein Aufräumen durch den Ausführer — Löschen ist
   tabu).

**Kosten:** 1 Einbettungs-Aufruf, Bruchteile eines Cents. Grenze im Plan:
< 0,05 $ je Lauf — mit der echten Zahl belegen.

## 6. Doku (im selben Schritt)

* `docs/changelog-2026-09-29-n22-archiv-nachpflege.md`: Befund, Werkzeug, Tests,
  Prüfbefehl mit Zahlen, alle Live-Zahlen aus Schritt 5, Kosten, Grenzen
  (nur anhängen, kein Löschen), **ehrlich offen**: solange das Schwesterprojekt
  keine neuen Chats importiert, ist der Erstlauf auf dem Original 0 — die
  Wirkung ist auf Kopien belegt.
* **Keine** echten Chat-Inhalte, keine echten Namen, Orte oder Ereignisse in
  Code, Tests, Doku oder Ausgaben.

## 7. Was der Ausführer **nicht** tut

* Keine git-Befehle (kein `add`, kein `commit`, kein `push`).
* Keine Datei außerhalb der drei genannten anfassen (kein `app.js`, kein
  `index.html`, kein Cache-Bump, keine bestehenden Tests ändern).
* `backend/scripts/archiv_index_bauen.py` bleibt **unverändert** (nur lesen,
  Ideen übernehmen).
* Nichts löschen, nichts verschieben, nichts in die Cloud schreiben.
