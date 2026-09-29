# Changelog 2026-09-29 — N22: Nächtliche Nachpflege des Archiv-Index

**Auftrag:** `docs/auftrag-n22-archiv-nachpflege.md` (Abschnitte 1–7).
**Ausführer:** Hermes-Subagent. **Keine** git-Befehle ausgeführt (der Planer
committet). Es wurden genau drei Dateien angelegt, keine bestehende geändert.

Angelegt:

| Datei | Zeilen |
|---|---|
| `backend/scripts/archiv_nachpflege.py` | 623 |
| `backend/tests/test_archiv_nachpflege.py` | 697 (51 `test_`-Funktionen) |
| `docs/changelog-2026-09-29-n22-archiv-nachpflege.md` | diese Datei |

---

## 1. Befund (selbst nur lesend, `mode=ro`, am echten Bestand gemessen)

| Messung | Wert |
|---|---|
| Quelle `db/memory.db` | 230.391.808 B — `messages` **282.029**, `chunks` **52.679** |
| Ziel `db/archiv_index.db` | 447.496.192 B — `nachrichten` **282.029**, `chunks` **52.679**, `chunks_fts` **52.679**, `vektoren` **52.679**, `gespraeche` **1.590** |
| Chunks **ohne** Vektor (`hat_vektor = 0`) | **0** |
| `max(id)` | `nachrichten` **282.028**, `chunks` **52.679** |
| `meta` | `modell openai/text-embedding-3-small`, `dimension 1536`, `vektor_speicher float16`, `kosten_usd 0.320717` |

**Der Index ist heute vollständig in Sync — es gibt keinen Rückstand.** Genau
deshalb wurde die Wirkung auf **Kopien außerhalb des Repos** nachgewiesen
(Abschnitt 5), nicht durch einen Lauf auf dem Original.

**Nebenbefund (ehrlich):** Die Quelle `memory.db` enthält **68 Nachrichten mit
leerem Text** (alle aus dem Claude-Export, `role = user`). Diese sind
**zulässig** — sie stehen auch im Index — und werden über Zeitstempel und Rolle
korrekt verschlüsselt. Eine erste Fassung des Werkzeugs zählte sie fälschlich
als „Fehler"; das wurde korrigiert (nur leere `conversation_id`/`role` gelten
jetzt als defekt). Ein Test
(`test_leerer_text_ist_kein_fehler`) hält das fest.

## 2. Werkzeug — `backend/scripts/archiv_nachpflege.py`

Pflegt einen **bestehenden** Index inkrementell und idempotent nach:

* **Erkennung „neu" per Inhaltsschlüssel** (kein `id`/Ordinal):
  `schluessel_nachricht = sha1("conv\x1ftimestamp\x1frole\x1ftext")[:16]`,
  `schluessel_chunk = sha1("conv\x1fteil\x1fbeginn\x1fende\x1ftext")[:16]`.
  Der Bestand wird aus dem **Index selbst** verschlüsselt — kein Schema-Umbau,
  keine Zusatztabelle.
* **Nur anhängen:** neue Zeilen hinten (`id = max + 1` aufsteigend), neue Chunks
  in `chunks_fts` (+ `optimize`), `gespraeche` per `INSERT OR REPLACE` nur für
  **berührte** Gespräche, `meta` **ergänzt** (`nachpflege_*`) und nie entfernt.
* **Vektoren nur für neue Chunks** und nur mit `--mit-vektoren`; ohne bleibt
  `hat_vektor = 0` und wird ehrlich als „ohne Vektor" gezählt. Einbetter
  injizierbar (wie `archiv_index_bauen.EinbetterOpenRouter`).
* **Trockenlauf ist Standard:** Quelle und Index werden nur lesend geöffnet,
  geschrieben wird nur mit `--schreiben`. Repo-Ziel (`personal_ai_agent`) →
  Exit **2**; fehlende Quelle/Index → Exit **2**; defekte Zeile → als `fehler`
  gezählt statt zu werfen.
* `--stand <ISO>` friert den Zeitstempel ein.

Kommandozeile:

```
cd backend
.venv/Scripts/python -m scripts.archiv_nachpflege \
    --quelle-db <memory.db> --index <archiv_index.db> \
    [--schreiben] [--mit-vektoren] [--stapel 100] [--stand <ISO>]
```

## 3. Tests — `backend/tests/test_archiv_nachpflege.py`

**51 Offline-Testfunktionen** (Auftrag: mindestens 28), alles ohne Netz, ohne
Schlüssel, nur **erfundene** Texte („Probe-Nachricht", „Probe-Gespräch",
„probebegriffn22"). Quell- und Zieldatenbank entstehen im `tmp_path` aus
`app.services.archiv_suche.SCHEMA_SQL`; der Einbetter ist eine Attrappe, die
ihre Aufrufe zählt.

Abgedeckt u. a.: Schlüsselfunktionen (gleicher Inhalt = gleicher Schlüssel,
geänderter Text = anderer, Feldgrenzen kollidieren nicht); neue Nachricht/Chunk
erkannt; neue Zeile hängt **hinten** an (`id > max`); bestehende Zeilen
unverändert; **FTS findet den neuen Text** nach dem Lauf; Vektorzeile entsteht
(Länge = `dimension * 2` = 3072 bei 8 Dimensionen in der Attrappe);
`hat_vektor` wird 1; Einbetter nur für neue Chunks; `gespraeche`-Zahlen wachsen,
`von`/`bis` stimmen; neues Gespräch erzeugt Zeile; `meta` behält **alle** alten
Schlüssel; **zweiter Lauf = 0 neu** und `sha256` unverändert; Trockenlauf
schreibt nichts (sha + mtime gleich, kein Journal/WAL); Repo-Ziel Exit 2;
fehlende Quelle/Index Exit 2; defekte Zeile als `fehler`; leerer Text **kein**
Fehler; Quelltext enthält **kein** `DELETE`/`DROP`, kein `os.replace`, keine
pCloud-/Fremdnetz-Funktion; großer Bestand (500 Nachrichten + 500 Chunks,
Index kennt 5) läuft durch und liefert im zweiten Aufruf dieselben Zahlen.

## 4. Prüfbefehl (Gate)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
```

* **Baseline vor der neuen Datei** (`--collect-only`): **2980** Tests gesammelt.
* **Endstand mit der neuen Datei:** `3030 passed, 1 skipped, 3 warnings in
  148.37s` — **Exit 0**. (2980 + 51 = 3031; 3030 bestanden + 1 übersprungen.)

## 5. Nachweis am echten Bestand (Kopien, außerhalb des Repos)

Alle Schreib-Läufe ausschließlich auf Kopien unter
`C:/Users/sebas/foto_sortierung/n22_probe/`; die Originale blieben unberührt.

1. **Original, Trockenlauf** (nur lesend):
   `neu_nachrichten 0`, `neu_chunks 0`, `uebersprungen_nachrichten 282029`,
   `uebersprungen_chunks 52679`, `fehler 0`, **Dauer 12,0 s**.
   `sha256` **vor == nach**:
   * `memory.db`    `2ac72bf3c6b3f6f9e0ddfdf681dd9baaa31ad930d3bd8458a7ae759ae0928878`
   * `archiv_index.db` `61c95c6b8d2680eab6badd8eefee03414566ade43a9eb7492727ca9b7b90a4a7`
2. **Kopien** angelegt (`cp`, nur kopiert): `memory_probe*.db` 230.391.808 B,
   `archiv_index_probe*.db` 447.496.192 B — `sha256` identisch zu den Originalen.
3. In die Quell-Kopie **3 erfundene Nachrichten** (`id 282029–282031`,
   „Probe-Nachricht N22 eins/zwei/drei.") und **1 erfundenen Chunk**
   (`id 52680`, Text enthält `probebegriffn22`) angehängt.
4. **Schreib-Lauf auf den Kopien** (`--schreiben --mit-vektoren
   --stand 2026-09-29T12:00:00+00:00`):
   `neu_nachrichten 3`, `neu_chunks 1`, `vektoren_gerechnet 1`,
   `ohne_vektor 0`, `gespraeche_beruehrt 1`, `fehler 0`, **Dauer 23,5 s**,
   Index-Kopie danach 451.739.648 B (430,8 MiB).
   * `sha256` der Index-Kopie: vor `61c95c6b…` → nach `6ef6610671425ee635298fe2110e18bd664f3ceeec53c116e37b169fecd595a8`.
5. **Volltext-Gegenprobe** auf der Index-Kopie:
   `chunks_fts MATCH 'probebegriffn22'` → **1 Treffer**, `rowid = 52680`.
   Zusätzlich: `hat_vektor = 1`, Vektorlänge **3072** B (= 1536 × 2, float16),
   `dimension 1536`, `modell openai/text-embedding-3-small`;
   `gespraeche` für `probe-n22-nachpflege` = 3 Nachrichten / 1 Chunk,
   `von 2026-09-29T00:00:00+00:00`, `bis 2026-09-29T00:02:00+00:00`.
6. **Zweiter Lauf** auf denselben Kopien → `neu_nachrichten 0`, `neu_chunks 0`,
   `vektoren_gerechnet 0`, `fehler 0`; `sha256` der Index-Kopie
   **vor == nach** `6ef6610671425ee635298fe2110e18bd664f3ceeec53c116e37b169fecd595a8`
   (kein Schreibvorgang).
7. **Originale am Ende erneut geprüft** — `sha256` unverändert, `mtime`
   unverändert (28.09. 12:03 bzw. 12:11).
8. Kopien bleiben liegen (kein Aufräumen durch den Ausführer).

## 6. Kosten

Ein Einbettungs-Aufruf je Schreib-Lauf, je **1 Chunk = 13 Token** (echte Zahl
aus der API-Antwort). Preis `openai/text-embedding-3-small` = 0,02 $/1 Mio
Token:

* **je Lauf: 13 Token = 2,6e-07 $** (0,00000026 $) — deutlich unter der
  Plangrenze von 0,05 $ je Lauf.
* zwei echte Aufrufe im Nachweis insgesamt = 26 Token ≈ 0,00000052 $.

## 7. Grenzen (hart, im Werkzeug verankert)

* **Nur anhängen** — kein Löschen, kein Verwerfen von Tabellen, kein
  Neu-Schreiben der Datei (kein `os.replace`), kein Tabellen-Neuaufbau; der
  Quelltext-Test prüft die Abwesenheit von `DELETE`/`DROP`.
* Trockenlauf ist Standard; ohne `--schreiben` wird nichts geschrieben.
* Repo-Ziel wird mit Exit 2 verweigert; ebenso fehlende Quelle/Index.
* Kein Zugriff auf Bild-/Fotodaten, kein Cloud-Zugriff, kein Löschen; der
  Schlüssel wird nie ausgegeben (nur Länge 73).

## 8. Ehrlich offen

Solange das Schwesterprojekt keine neuen Chats nach `db/memory.db` importiert,
ist der Erstlauf auf dem **Original** `neu_* = 0` — das ist der heutige
Sync-Stand, kein Fehler. Die **Wirkung** (Anhängen, FTS, Vektor, `gespraeche`,
`meta`, Idempotenz) ist ausschließlich auf den **Kopien** belegt
(Abschnitt 5). Der eigentliche Erstlauf auf dem Original steht noch aus, bis
tatsächlich neue Nachrichten importiert sind.
