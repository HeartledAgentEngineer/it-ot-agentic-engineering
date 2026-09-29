# Feinauftrag N19 — Archiv-Suche auf Erwähnungen erweitern

**Auftraggeber:** Planer (Hauptagent, Nachtlauf 29.09.2026)
**Ausführer:** Hermes-Subagent (`deepseek-v4.1-flash`) — Codex ist live geprüft
**gesperrt** („You've hit your usage limit … try again at Oct 15th, 2026").
**Rollen:** Ausführer baut **nur** hier; Prüfer ist ein **frischer** Subagent einer
**anderen** Modellfamilie (glm-5.2) und führt den Prüfbefehl selbst aus.

---

## 1. Der belegte Befund (vom Planer gemessen, nicht behauptet)

Sebastians Frage: „was habe ich mit X gemacht?" findet heute **nichts**, obwohl
das Archiv die Person **113 ×** enthält.

Gemessen am echten Index (`Chats von GPT, GEMINI, Claude/db/archiv_index.db`,
nur lesend, `mode=ro`):

| Messung | Wert |
|---|---|
| `chunks` / `chunks_fts` | 52.679 / 52.679 (Index vollständig) |
| `nachrichten` / `gespraeche` | 282.029 / 1.590 |
| Quellen (Gespräche) | whatsapp 481, google-kalender 399, gemini 384, claude-ai 162, chatgpt 109, claude-code 40, google-notizen 15 |
| Volltext-Treffer für den **vollen Namen** (`chunks_fts MATCH …`) | **113** |
| Rohtext-Treffer (`LIKE '%…%'` in `chunks.text`) | whatsapp 108, chatgpt 4, google-kalender 2 |
| Chats, **deren Titel** die Person trägt | **0** (es gibt keinen eigenen Chat mit ihr) |

**Die Ursache ist die Verdrahtung, nicht der Index:** `_archiv_tool` in
`backend/app/router/chat.py` (Zeile ~1038) feuert nur auf `_ARCHIV_SIGNALE`
(„archiv", „alte chats" …) und `_ARCHIV_SIGNALE_WEICH` („was weißt du über",
„erinnerst du dich" …). Eine Frage wie „was habe ich mit X gemacht?" enthält
**kein** Signal → das Werkzeug gibt `""` zurück → kein Archiv-Blick, obwohl die
Fundstellen mit Datum und Quelle im Index liegen. Der Prüfplan nennt genau das:
„Die Suche fragt heute nur nach dem *Gegenüber*, nicht nach **Erwähnungen**."

## 2. Was gebaut wird (Umfang genau so, nichts darüber hinaus)

### 2.1 Dienst: Erwähnungssuche in `backend/app/services/archiv_suche.py`

Neue, **rein lesende** Funktionen (Namen sind bindend):

1. `erwaehnung_treffer(name: str, top_k: int = 8) -> Dict[str, Any]`
   Volltextsuche (FTS5, derselbe Weg wie `volltext_suche`) nach dem **Namen**
   über **alle** Quellen — **ohne** Filter auf den Gesprächs-Titel.
   Rückgabe (immer dieselben Felder, nie ein Wurf):
   - `name` (so wie gesucht), `treffer` (Liste von Fundstellen),
   - `je_quelle: Dict[str, int]` (Quelle → Anzahl, absteigend sortiert),
   - `anzahl` (Gesamtzahl der Fundstellen),
   - `eigene_chats: int` (wie viele `gespraeche.title` den Namen tragen),
   - `eigene_chat_titel: List[str]` (höchstens 5),
   - `nur_erwaehnungen: bool` (`anzahl > 0 and eigene_chats == 0`),
   - `hinweis` (deutscher Klartextsatz, s. u.),
   - `fehler: None | str` (z. B. Index nicht erreichbar).
   Jede Fundstelle trägt: `quelle`, `datum` (JJJJ-MM-TT, aus `beginn`),
   `titel` (Gesprächs-Titel oder `None`), `text` (Ausschnitt),
   `im_eigenen_chat: bool`, `conversation_id`, `chunk_id`.

2. `erwaehnungs_text(ergebnis: Dict[str, Any], hoechstens: int = 5) -> str`
   **Reine** Funktion (ohne Index, ohne Netz, ohne DOM) — baut den Notiztext für
   das Chat-Werkzeug:
   - Kopfzeile mit dem Namen und den Zahlen: „X kommt N × im Archiv vor
     (WhatsApp a, ChatGPT b, …). Ein eigener Chat mit X: ja/nein."
   - darunter höchstens `hoechstens` Fundstellen als
     `[Quelle, Datum] Titel — Ausschnitt`.
   - **Bei `nur_erwaehnungen` zusätzlich der Satz im Klartext:** „Es gibt keinen
     eigenen Chat mit dieser Person; die Fundstellen sind **Erwähnungen in
     anderen Gesprächen** — sie belegen, *dass* über sie gesprochen wurde, nicht
     dass sie dabei war."
   - Nie leere Behauptungen: bei 0 Fundstellen ein ehrlicher Satz statt einer
     erfundenen Fundstelle.

3. **Keine neue Suchlogik doppeln:** die FTS-Aufbereitung von `volltext_suche`
   (`_fts_begriffe` / `_fts_anfrage`) **wiederverwenden**. Wenn dort ein
   Titel-Filter o. Ä. im Weg steht, wird er als Parameter geöffnet — nicht kopiert.

**Grenze unverändert:** nur lesen (`mode=ro`), kein Netz (Volltext braucht keine
Einbettung), nichts schreiben, keine Inhalte ins Repo.

### 2.2 Verdrahtung in `backend/app/router/chat.py`

1. Neue Konstante `_ERWAEHNUNG_SIGNALE` (harte Personen-Signale), mindestens:
   `"was habe ich mit"`, `"was hab ich mit"`, `"was war mit"`, `"was war da mit"`,
   `"wo war ich mit"`, `"mit wem war ich"`, `"wen kenne ich"`, `"was weiß ich über"`,
   `"was weiss ich über"`.
2. Neue **reine** Funktion `_erwaehnung_name(frage: str) -> Optional[str]`
   (offline prüfbar): nimmt den Text **nach** dem Signal, schneidet Satzzeichen ab,
   verwirft `_ARCHIV_STOPWOERTER` und weitere Füllwörter, verlangt mindestens 3
   Zeichen und **genau ein übrig bleibendes Wort** — sonst `None` (lieber nichts
   tun als die ganze Frage falsch als Namen durchsuchen). Beispiele, die im Test
   stehen müssen: „was habe ich mit Erwin gemacht?" → `Erwin`;
   „mit wem war ich in Hamburg?" → `None` (zwei Wörter / kein Name);
   „was habe ich mit gemacht?" → `None`.
3. In `_archiv_tool`, **nach** dem `_ARCHIV_AUSSCHLUSS`-Tor (Bild-/Foto-Fragen
   bleiben beim Datei-/Gesichts-Weg — ein „zeig mir Fotos mit X" darf **nicht**
   in die Erwähnungssuche laufen) und **vor** der bestehenden Signalprüfung:
   ist `_erwaehnung_name` erfolgreich → Erwähnungssuche ausführen und
   `erwaehnungs_text(...)` als Notiz zurückgeben. Der Rückgabewert muss wie die
   anderen Zweige die Form „`\n\n[…Hinweis an das Modell…]`" behalten.
   Ist der Dienst nicht erreichbar → wie bisher ehrlich sagen, dass dazu gerade
   nichts gesagt werden kann (kein stiller Rückfall, keine Erfindung).
4. **Beide Ketten** bedienen (derselbe Aufruf wie `_archiv_tool`, es gibt zwei
   Stellen — Zeile ~370 und ~1910 in `chat.py`). Nichts anderes umbauen.

### 2.3 Tests (`backend/tests/`, alles offline)

Neue Datei `backend/tests/test_erwaehnungssuche.py` — **kein** Netz, **keine**
echten Namen, **keine** echten Chats: ein winziger Index im `tmp_path`
(Tabellen `nachrichten`, `chunks`, `chunks_fts`, `gespraeche`, `meta`) mit
**erfundenen** Namen (z. B. „Erwin", „Marga"). Pflichtfälle:

| Nr. | Testfall | Erwartung |
|---|---|---|
| 1 | Person nur als Erwähnung in fremden Chats | `anzahl > 0`, `eigene_chats == 0`, `nur_erwaehnungen is True`, `hinweis` nennt „Erwähnung" |
| 2 | Person mit eigenem Chat | `eigene_chats > 0`, `nur_erwaehnungen is False` |
| 3 | Person ohne jede Fundstelle | `anzahl == 0`, ehrlicher Text, kein leeres Feld, **kein** erfundener Treffer |
| 4 | Index fehlt / kein Pfad | `fehler` gesetzt, kein Wurf, `erwaehnungs_text` trotzdem benutzbar |
| 5 | Jede Fundstelle trägt `quelle` **und** `datum` | im Test einzeln geprüft |
| 6 | `je_quelle`-Summe == `anzahl` | Arithmetik geprüft |
| 7 | `_erwaehnung_name` — die drei Beispiele aus 2.2 plus Groß-/Kleinschreibung | wie dort |
| 8 | False-Positive-Schutz: „zeig mir Fotos mit Erwin" | `_archiv_tool` gibt `""` (Bild-Tor greift), Archiv-Suche läuft nicht |
| 9 | Kein Signal („wie ist das Wetter?") | `""` |
| 10 | Bestehende Archiv-Signale unverändert („was weißt du über Erwin", „alte chats") | Verhalten wie vorher |
| 11 | Erwähnungssuche berührt den Index nicht | `mtime`/`sha256` der Test-DB vor und nach dem Lauf gleich |
| 12 | Kein Schreib-/Netzweg | Quelltext-Prüfung der neuen Funktionen auf `INSERT`/`UPDATE`/`DELETE`/`requests`/`httpx` |

Die Testdatei zählt die Prüfungen selbst (Anzahl im Bericht).

### 2.4 Doku (Teil des Commits)

- `docs/changelog-2026-09-29-n19-erwaehnungssuche.md` — Befund mit den
  Messzahlen aus Abschnitt 1, Umsetzung, Prüfbefehl mit Zahlen, ehrlich offen.
- `docs/plan-nachtlauf-2026-09-26.md` — neue Zeile `N19` in der Schritt-Tabelle
  (Stand ✅) **und** ein Journal-Eintrag mit Zahlen.
- `HANDOVER-CLAUDE-CODE.md` — Zeile `N19` in „Open steps" auf done/step done
  ziehen (englisch).

## 3. Verbote (bindend)

- **Kein** `git add -A`, **kein** `git commit -a`, **kein** `git commit` überhaupt
  — der Planer committet. Der Ausführer fasst **keine** git-Befehle an.
- **Keine** echten Personen-, Orts- oder Ereignisnamen, **keine** Chat-Inhalte,
  **keine** Telefonnummern, Kennungen oder Prüfsummen des echten Archivs in Code,
  Tests, Doku oder Ausgaben. Im Bericht steht nur die Zahl 113 / 108 / 4 / 2.
- **Nichts löschen, nichts verschieben.** Der echte Index wird **nur** gelesen.
- Keine Schwellenwerte erfinden; keine Änderung an `_ARCHIV_AUSSCHLUSS`,
  `_ARCHIV_SIGNALE`, `_ARCHIV_SIGNALE_WEICH` außer der neuen Konstante.
- Keine Änderung an `AGENTS.md`/`CLAUDE.md`-Semantik, kein Frontend-Umbau,
  **kein** Cache-Bump.
- Dateien, die dem zweiten Agenten gehören (`tools/agentbus/*`,
  `docs/experimente/*`, `docs/spec-a1-android-hey-agent.md`,
  `tools/foto_sortierung/gesicht_erkennen.py`, `personen_vektoren_*`) **nicht
  anfassen**.

## 4. Prüfkriterium (Lieferung gilt erst damit)

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q
```

Ablauf: **zuerst** Baseline fahren und die Zahl notieren, **dann** bauen, **dann**
erneut fahren → Exit 0. Bericht enthält: Baseline-Zahl, neue Zahl, Dauer,
Testfunktionen der neuen Datei, und **einen** echten Lauf gegen den echten Index
(nur lesend, nur Zahlen ausgeben: `anzahl`, `je_quelle`, `eigene_chats`,
`nur_erwaehnungen`) für eine Person, für die es **keinen** eigenen Chat gibt —
ohne deren Namen zu nennen.
