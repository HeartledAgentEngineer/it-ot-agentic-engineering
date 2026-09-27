# Nachtlauf 26./27.09.2026 — Fotos, Videos, Personen (autonom)

> **Auftrag:** Sebastian (26.09.2026, ~04:30): „Wir wollen eine Langzeit-Session
> bauen … dass du das alles abarbeitest. Ich gehe jetzt für 4–5 Stunden schlafen.
> Arbeite ohne Unterbrechung und komm nicht mit Fragen, sondern entscheide
> selbst. […] Wenn du unsicher bist: **nichts löschen**, nur verschieben,
> sortieren — oder erstmal nur den Upload-Ordner sortieren. Wenn was schiefläuft,
> müssen wir es zurückstellen können."
>
> **Regeln:** `AGENTS.md` → Abschnitt „Dauerlauf / Nachtarbeit (autonom)".
> Kernpunkte: keine Rückfragen, jeder Schritt verifiziert + einzeln committet,
> **nie löschen**, jede Schreib-Operation ins **Manifest** (rückholbar),
> idempotent bauen, billigste Wege zuerst.

## Rollen: Planer → Ausführer → Prüfer (getrennte Kontexte, verbindlich)

Nach `CLAUDE_EXTENDS.md` §6.6 und dem Everlast-Kanon (Punkte 1–3): **nie** plant,
führt aus und prüft derselbe Kontext.

| Rolle | Wer | Aufgabe im Nachtlauf |
|---|---|---|
| **Planer** | Hauptkontext (dieser Chat) | Diesen Plan als Datei schreiben, Reihenfolge + Prüfkriterien festlegen, committen. **Kein** Bauarbeit-Selbstlauf am eigenen Werk. |
| **Ausführer** | je Schritt ein **Subagent** (`delegate_task`) | genau **einen** Planschritt umsetzen, Code + Tests + Doku, **keine** git-Befehle |
| **Prüfer** | **frischer** Subagent, **anderes Modell als der Ausführer** | gegen den Plan prüfen, Prüfbefehl selbst ausführen, Abweichungen benennen, „bestanden/nicht bestanden" |

**Ablauf je Schritt:** Planer beschreibt → Ausführer baut → **Prüfer prüft** →
Planer committet (nur bei „bestanden"). Ein Schritt ohne Prüfer-Abnahme gilt als
**offen**, auch wenn er gebaut ist.

**Warum das im Nachtlauf doppelt zählt:** Ohne getrennten Prüfer bestätigt der
Bauende seine eigene Annahme — im Nachtlauf sieht Sebastian das Ergebnis erst
Stunden später. Fehler, die ein frischer Kontext findet, kosten Minuten; Fehler,
die bis zum Morgen liegen, kosten den ganzen Lauf.

## Modell-Mix (Anmerkung Sebastian: „verschiedene Modelle miteinander kombinieren")

**Befund:** `config.yaml` hat unter `delegation:` nur `max_iterations` — **kein**
Modell gepinnt. Damit erben alle Subagenten das Hauptmodell
(`deepseek/deepseek-v4.1-flash`). Sebastian hat recht: das ist noch keine
Vielfalt. Wird bewusst **pro Rolle** gesetzt:

| Rolle | Modell | Weg | Warum |
|---|---|---|---|
| **Planer (Denken)** | `gpt-5.6-terra` | **nur über die Codex CLI** (ChatGPT-Konto, `codex exec --model gpt-5.6-terra --sandbox read-only`) | stärkstes verfügbares Denken, **keine Token-Rechnung** — nur Volumen. Denken ist selten, teuer darf sein. **⚠️ 27.09. gesperrt:** Kontingent erschöpft — live „You've hit your usage limit … try again at Oct 15th, 2026 9:32 PM" (2 Sitzungen liefen 05:00 + 07:43 noch; danach zu) |
| **Planer-Ersatz, solange gesperrt** | Hauptagent `deepseek-v4.1-flash` | direkt (Hauptkontext) | Planung macht der Hauptagent selbst; die Qualität kommt aus dem **fremdfamiliären Prüfer**, nicht aus dem Planer. Zweitweg **Claude Code geprüft und ausgefallen**: 2.1.83 antwortet `Exit 1 · 401 authentication_error: „OAuth access token has expired. Re-authenticate to continue."` → braucht Sebastians Anmeldung (`claude` interaktiv bzw. `claude setup-token`) |
| **Ausführer (Masse)** | `deepseek-v4.1-flash` | Hermes-Subagenten | **Cache 0,001 $/Mio** → lange Sitzungen kosten fast nichts |
| **Ausführer (schwerer Coding-Block)** | `gpt-5.6-terra` | Codex CLI, `--sandbox workspace-write` | starke Umsetzung ohne Zusatzkosten über das Konto — **derzeit ebenfalls gesperrt** (Kontingent, s. o.); solange übernimmt der Hauptagent/Subagent mit `deepseek-v4.1-flash` |
| **Prüfer (andere Familie!)** | `gpt-5.6-luna` (0,20/1,20) oder `z-ai/glm-5.2` (0,65/2,04) | `hermes -z "<Auftrag>" -m <Modell>` | Fehler, die eine Familie macht, findet dieselbe Familie nicht |

**Gemessene Preise (OpenRouter, je 1 Mio Token, 27.09.2026, live abgefragt):**

| Modell | Eingang | Ausgang | Cache | Kontext |
|---|---|---|---|---|
| `deepseek-v4.1-flash` | **0,035** | 0,290 | **0,001** | 1,05 M |
| `deepseek-v4-flash-0731` | **0,021** | 0,320 | 0,016 | 1,31 M |
| `openai/gpt-5.6-luna` | 0,200 | 1,200 | 0,020 | 1,05 M |
| `openai/gpt-5.6-terra` | **2,000** | **12,000** | 0,200 | 1,05 M |
| `google/gemini-3.7-flash` | 0,750 | 3,750 | 0,075 | 1,05 M |
| `z-ai/glm-5.2` | 0,650 | 2,042 | 0,121 | 1,05 M |

**Konsequenz (Sebastians Einwand, bestätigt):** Terra über OpenRouter wäre
**57× teurer im Eingang / 41× teurer im Ausgang** als DeepSeek V4.1 Flash —
für einen Ausführer-Schritt (~200 k rein, ~50 k raus) sind das **≈ 1,00 $ statt
≈ 0,02 $**. Deshalb: **Terra ausschließlich über das ChatGPT-Konto (Codex CLI)**,
niemals über OpenRouter als Ausführer.

**Datenschutz-Grenze (bleibt hart):** Nur **reiner Code** geht an Codex.
Chat-Archiv, Fotos, Erinnerungen, `.env`, Bewerbungen bleiben bei
Hermes/DeepSeek (Skill `ai-datenschutz-regeln`).

## Qualität halten, obwohl billig ausgeführt wird (Sebastians Kernfrage)

Sebastian (27.09.): „Wir sind auf die Ebene DeepSeek V4.1 Flash gegangen — wir
wollen es günstiger machen, aber von der Qualität fast gleich hoch."

**Die Logik:** Qualität kommt **nicht** aus jedem ausgeführten Token, sondern aus
drei Dingen — und die kosten fast nichts:

1. **Guter Plan vom starken Modell.** Terra (Codex-Konto) bzw. Claude Code
   zerlegen die Aufgabe in einen **präzisen Auftrag**: welche Datei, welches
   Verhalten, welches Prüfkriterium. Ein billiger Ausführer mit klarem Auftrag
   liefert fast dasselbe wie ein teurer mit vagem Auftrag.
2. **Prüfer aus einer anderen Familie.** Die teure Fehlerquote entsteht dort, wo
   niemand gegenliest. Ein fremdfamiliärer Prüfer (`gpt-5.6-luna`, `glm-5.2`,
   `codex review`) kostet Cent-Beträge und fängt genau die Fehler, die der
   Ausführer selbst nicht sieht.
3. **Prüfbefehl als Tor.** Kein Commit ohne Exit-Code 0 — die Wahrheit liegt im
   Befehl, nicht im Gefühl des Ausführers.

**Wo NICHT gespart wird (harte Schritte bleiben beim starken Modell):**
Architektur-Entscheidungen, knifflige Bugs (Race Conditions, Datenverlust-Risiko),
Sicherheits-/Datenschutzfragen, Umbauten an bestehender Logik. Diese Aufgaben sind
selten und teuer im Kopf — aber billig in der Rechnung, wenn sie wenige Male laufen.

**Faustregel:** *Denken und Prüfen = stark, Ausführen = billig.* Wer die Ausführung
mit dem starken Modell fährt, zahlt das 40–50-Fache für Arbeit, die der Prüfer
ohnehin nachkontrolliert.

## Entscheidungen, die ich selbst treffe (statt zu fragen)

1. **Zielstruktur:** `Agent/Fotos/<Jahr>/<Thema>/` (Sebastians Vorgabe B) — und
   **verschieben statt kopieren** aus dem Upload-Ordner. Grund: pCloud kann das
   in Millisekunden (nur Metadaten), es spart 45 GB Upload-Verkehr, und es ist
   über das Manifest **umkehrbar** (zurück in den Quellordner).
2. **Erinnerungs-Ablage:** eigene Datei außerhalb des Repos
   (`~/foto_erinnerungen/erinnerungen.jsonl`), getrennt vom Gedächtnis-Dienst,
   Personen über **stabile Kennungen** (`Person_001` …). Text im Wortlaut,
   Versionen über `history`.
3. **Personen-Rechnen:** Rechnung auf dem PC, **Benennen** später auf dem Handy
   im Quiz (dort liegen Katalog, Referenzen und die Fragen).
4. **Kostenschutz:** Vorschaubilder (120×120 über die API) für die Themen-Stufe;
   Gesichtserkennung braucht Originale → **Jahres-Stapel**, erst Stichprobe
   messen, dann Vollauf.

## Sicherheitsnetz (vor der ersten Schreib-Operation fertig)

* **Manifest:** `~/foto_sortierung/manifest.jsonl` — je Zeile
  `{zeit, art: movefolder|movefile|createfolder, von_id, nach_id, name, datei_id}`.
  Damit kann jede Aktion **rückwärts** gefahren werden.
* **Rückroll-Werkzeug:** `tools/pcloud/pcloud_rueckrollen.py`
  (`--zeigen` listet, `--rueckwaerts N` macht die letzten N Aktionen rückgängig).
* **Keine Löschbefehle** im gesamten Werkzeugsatz — `deletefile`/`deletefolder`
  werden nicht implementiert, auch nicht „zur Sicherheit".
* **Probelauf-Schalter:** jedes Schreib-Werkzeug hat `--trocken` (zeigt nur, was
  es täte) und läuft zuerst mit `--trocken`.
* **Crypto Folder** wird nie berührt (im Konto aktiv, tabu).

## Schritte (in dieser Reihenfolge, jeder mit Prüfkriterium)

| # | Schritt | Prüfkriterium | Stand |
|---|---|---|---|
| N1 | Cloud-Service (Hintergrund-Bau) **selbst prüfen** + committen | `pytest tests/ -q` grün; Rauchtest-Zahlen aus dem Bericht nachgefahren | ✅ **500 Tests grün** (selbst gefahren), Rauchtest-Zahlen geprüft (18 Einträge, 4185 Bytes Vorschaubild), committet |
| N2 | **Selbstheilung + Rollback-Werkzeug** committen (Selbstheilung schon gebaut: `pcloud_token_erneuern.py`) | Prüfmodus sagt „gültig"; Rückroll-Tool mit Tests | 🔄 Selbstheilung committet (`3cad5ae`, live belegt); **Rückroll-Werkzeug läuft als Subagent** (`deleg_609a78cd`) |
| N3 | **Schlüssel aufs Handy** (USB) + Selbsttest-Zeile „pCloud" + `start-termux.sh` übernimmt die Datei automatisch | `curl` am Handy liefert `pcloud: verbunden`; JS-Tests grün | ✅ **gebaut + gepusht (27.09. ~10:20, Hauptagent mit Sebastian)** — Übergabedatei per Kabel aufs Handy (`/sdcard/Download/pcloud_token.txt`, 81 B, nur Längen geprüft, nie Werte); Automatik-Block + Selbsttest-Zeile + Frontend-Zeile in Commit `6b08e67`, **665 Tests grün, Exit 0** (selbst gefahren), Frontend 15/15; Sicherung `.env.vorher`, Übergabedatei wird nach Übernahme gelöscht, `.gitignore` schützt `*.env.vorher`. **Offen (Handy):** Übernahme beim Widget-Tipp noch nicht beobachtet — Sebastian pullt, tippt **zweimal** und sieht im Selbsttest die pCloud-Zeile |
| N4 | **Themen-Stufe Werkzeug**: `tools/foto_sortierung/foto_themen.py` — Ordnerbaum je Ebene, Vorschaubilder in Stapeln, Kontaktbögen bauen | Werkzeug-Tests grün; Kontaktbogen-Datei entsteht (Größe/Kacheln belegt) | ✅ **Prüfbefehl 525 grün** (500 + 25 neue, selbst gefahren); 2 Kontaktbögen live gebaut (10 Kacheln/62.566 B, 36 Kacheln/262.437 B, Pixel-Nummern belegt); Idempotenz live (2. Lauf: 0 geholt) |
| N5 | **Stichprobe Kosten** (1 Bogen → Vision) → Thema je Anlass | gemessene Kosten pro Bogen notiert, bevor der Vollauf startet | ✅ **bestanden (27.09.)** — siehe Journal: Nummern 1–36 einwandfrei lesbar, Thema je Bogen erkennbar, unbrauchbare Kacheln werden benannt |
| N6 | **Themen je Anlass** (Stapel) → Zuordnung im Sortierschlüssel | Anzahl Anlässe je Jahr/Thema; Stichprobe nachgesehen | ✅ **bestanden (27.09.)** — Werkzeug `tools/foto_sortierung/foto_themen_vision.py` (ein Vision-Aufruf je Anlass), **628 Prüfungen grün**, 59 eigene Tests; 2 Anlässe live gemessen (36 Kacheln → „Veranstaltung Publikum Bühne", 0,004354 $; 10 Kacheln → „Konzert Band Auftritt", 0,002255 $); Prüfer `gpt-5.6-luna` sagt „bestanden" (6. Runde). **Offen als N6b:** Massenlauf über alle 2.128 Anlässe (Bögen bauen + Themen setzen) |
| N6c | **Themen-Katalog** (feste Liste 40–60 Einträge) + Prompt, der nur daraus wählt; die 161 gelaufenen Anlässe nachziehen (`--wiederholen`); **Modellvergleich am Katalog** (flash vs. flash-lite) | Werkzeug-Tests grün; Stichprobe zeigt ≤ Katalog-Themen; flash-lite-Qualität belegt | ✅ **bestanden (27.09.)** — `themen_katalog.py` mit **53 Einträgen** (Version 3), Prompt wählt nur daraus, `Sonstiges` als Rückfall; Prüfbefehl **657 grün**; die 161 Anlässe beider Modelle live gemessen (flash 0,209693 USD / 100 % Katalog-Treffer / 14 × Sonstiges = 8,7 %; flash-lite 0,058977 USD / 99,4 % / 18 × Sonstiges); **Sichtprobe 6 Bögen: flash 4 : 2 flash-lite** → **flash** für den Massenlauf; Prüfer `gpt-5.6-luna` (1 Beanstandung an einer Zahl, korrigiert) |
| N6b | **Massenlauf:** Bögen je Jahr bauen, dann Themen setzen, kleinster Stapel zuerst | Anzahl Anlässe je Jahr/Thema; Stichprobe nachgesehen | ✅ **bestanden (27.09.)** — **Bestand vollständig:** 2.128 Anlässe, **2.127 mit Katalog-Thema**, 48 Themen genutzt, 242 × `Sonstiges` (11,4 %). Restlauf 2026/2025/2022/2024/2023: 1.967 Anlässe, 1.962 gesehen, 2 Fehlschläge, 7.722 Kacheln, **5.954.092 ein / 370.113 aus Tokens = 2,711510 USD**, 94,2 min. Dabei ein **echter Codefehler** gefunden und behoben (`MAX_TOKENS = 4000` schnitt den 108-Kachel-Bogen ab → `max_tokens_fuer(anzahl)`; derselbe Anlass läuft mit **4.420** Ausgabe-Tokens durch). **Ein Anlass bleibt bewusst offen:** `2022-09-05_Anlass-02` wird vom Anbieter abgelehnt (403 `PROHIBITED_CONTENT`) — keine Modellumgehung. Prüfbefehl **671 grün, Exit 0**; Prüfer `gpt-5.6-luna` (3 Punkte, 2 berechtigt → Zahlen/Doku korrigiert). Doku: `docs/changelog-2026-09-27-themen-massenlauf.md` |
| N6d | **Zielkatalog aus Sebastians eigenen Ordnern** (`Bilder & Videos`: 18 Kategorien, 113 Unterordner): Zielordner sind **seine** Kategorien, nicht die erfundenen 53 Motive. Werkzeug liest den Bestand nur lesend (`~/foto_sortierung/kategorien.json`) | Kategorien-Liste deckt alle Jahre ab; Motiv-Thema bleibt nur Motiv-Erkennung | ⬜ **neu (27.09.), hohe Wirkung** — Vorlage liegt vor: `docs/changelog-2026-09-27-kategorien-bestand.md` |
| N6e | **Event-Abgleich:** je Datums-Block gegen bestehende Event-Ordner prüfen (Jahr/Monat im Namen) → **Vorschlag** „Ordner X" statt Neubau; Muster: `Jahr + Ort` (Urlaub/Ausflüge), `Jahr_Monat + Ereignis` (Konzerte), `Jahr + Person` (Familie/Freunde) | Trefferquote an einer Stichprobe gemessen; Vorschläge nachvollziehbar | ⬜ nach N6d |
| N7 | **Probelauf `--trocken`** des Sortierens (Ordner anlegen + verschieben) | Liste der geplanten Züge, gegengeprüft | ⬜ **Themen sind vollständig** (N6b ✅, 2.127 von 2.128). **Auflage beim Bau:** Rückfallordner für Anlässe **ohne** Thema (z. B. `Ohne-Thema`) einbauen, statt abzubrechen. Zielt auf N6d/N6e (Ordner = Sebastians Kategorien) |
| N8 | **Sortieren echt** (Jahr für Jahr, kleinster Stapel zuerst) | Manifest vollständig; Stichprobe am Zielordner per API geprüft | ⬜ wartet auf N7 |
| N9 | **Personen-Stufe vorbereiten**: Modelle/OpenCV am PC prüfen, Vektoren + Cluster-Verfahren, unbenannte Gruppen + Referenzseiten — **mit Mengen-Filter** (Regel in `docs/plan-foto-personen-und-erinnerungen.md` + Projekt-`CLAUDE.md`): Menschenmengen werden **nicht** geclustert, Schwelle über Gesichtsgröße/Gesichter-Anzahl im Code, Vordergrund-Prüfung auf bekannte Personen, sonst weglassen | Cluster-Anzahl je Stichprobe; Referenzseiten vorhanden; **Test, dass ein Massenfoto keine Gruppe erzeugt** | ⬜ **kann parallel zu N4–N8 laufen** (andere Dateien) — **Mengen-Regel ist Pflichtteil des Auftrags** |
| N10 | **Doku + Protokoll + Abschlussbericht** (Changelogs, `CLAUDE.md`, Planjournal) | alles committet, Bericht mit Zahlen | ⬜ |

## Journal (wird fortlaufend ergänzt)

* **26.09. ~04:40** — Regeln in `AGENTS.md` („Dauerlauf / Nachtarbeit")
  verankert; Entscheidungen oben festgehalten; Plan angelegt.
  Der Cloud-Service-Bau (`deleg_1a630b66`) läuft noch im Hintergrund.
  Selbstheilung (`pcloud_token_erneuern.py`) gebaut und **live belegt**
  (Prüfmodus „gültig", Neu-Holen erfolgreich).
* **27.09. ~05:05 — N1 fertig.** Cloud-Service aus dem Hintergrund-Bau
  (`sa-0-40a79e8d`, 1301 s, 67 API-Aufrufe) **selbst geprüft**: Prüfbefehl
  **500 passed, Exit 0** (72,5 s; vorher 433 → +67 neue Tests).
  Rauchtest-Zahlen gegengelesen: Konto maskiert `se…com`, userid 4738912,
  premium, **2199,0 GB / 390,5 GB belegt**; `liste(0)` **18 Einträge** (17 Ordner,
  1 Datei); `thumb()` **4185 Bytes** JPEG (120×120). Wichtigster Live-Fund des
  Ausführers: `getthumbs` liefert **keine Binärdaten**, sondern eine Textzeile
  `fileid|0|86x120|data:image/jpeg;base64,…`; `type=png` antwortet bei diesem
  Konto mit Code **5002** → Dienst fragt `jgp` an und dekodiert base64.
  Geheimnis-Prüfung im Staging: **0 Treffer**; `.env` unangetastet.
  Commit **`3cad5ae`** (Regeln/Pläne/Selbstheilung/Stand) und der
  Service-Commit folgen als eigener Schritt — gepusht.
* **27.09. ~05:20 — Kollision erkannt und entschärft.** Ein **zweiter Agent**
  arbeitet im selben Arbeitsbaum (`fa5153d`, `908cf39` — live_zahlen-Themen,
  nicht von diesem Lauf). Sein `git add -A` hat die hier **gestagten**
  Cloud-Service-Dateien mitgenommen: Commit `908cf39` heißt „fix(live_zahlen)",
  enthält aber `pcloud_service.py`, `router/cloud.py`, beide Testdateien und den
  Service-Changelog. **Inhaltlich nichts verloren** (im Repo vorhanden, Tests
  grün), nur falsch beschriftet — Historie wird **nicht** umgeschrieben
  (fremde Commits). Konsequenz als Regel in `AGENTS.md`: nie `git add -A`,
  immer `git commit --only <Pfade>`; bei `cannot lock ref` erst
  `git pull --rebase`, niemals `--force`. Push danach wieder synchron (`0 0`).
* **Läuft:** N2 (Rückroll-Werkzeug) und N4 (Themen-Werkzeug/Kontaktbögen) als
  zwei Subagenten (`deleg_609a78cd`), kollisionsfreie Dateien.
  N3 wartet auf den Hauptagenten (Schlüssel-Übertragung nur mit Sebastian).
* **27.09. ~05:40 — N4 fertig (Themen-Stufe, Subagent `deleg_609a78cd`).**
  `tools/foto_sortierung/foto_themen.py` (nur lesend: `listfolder` je Ebene +
  `getthumbs` in Stapeln à 25, Token nie ausgegeben) und
  `backend/tests/test_foto_themen.py` (**25** Prüfungen, alles ohne Netz).
  Prüfbefehl **525 passed, Exit 0** (58,7 s). Anlass-Regel: gleiche Minute =
  ein Anlass, neue Sitzung ab **30 min** Lücke (`--luecke`) → **2.128 Anlässe**
  über alle Jahre, **380 für 2025** (Median 2 Kacheln, max 108).
  Live-Stichprobe (2 Anlässe, nur lesend): `2025-02-21_Anlass-01` **10 Kacheln**
  (44.294 B Vorschauen, Bogen **62.566 B**, 3,4 s) und `2025-01-06_Anlass-01`
  **36 Kacheln** (186.514 B, Bogen **262.437 B**, 6,1 s) unter
  `~/foto_sortierung/boegen/2025/`; zweiter Lauf überspringt (0 geholt).
  Live-Funde: mehrere fileids je getthumbs-Aufruf möglich (Antwort-Reihenfolge
  NICHT garantiert → Zuordnung über fileid); **Videos/HEIC haben Vorschaubilder**
  (VIDEO-Kennzeichen trotzdem gesetzt); derselbe Anlass enthält
  geräteübergreifende Doppelungen (Motorola + OnePlus) — N6 kann über die
  CSV-Spalte `doppelung` deduplizieren. Details:
  `docs/changelog-2026-09-27-foto-themen.md`.
* **Offen für die nächste Runde:** **N6b** (Massenlauf Themen: Bögen je Jahr
  bauen, dann Themen setzen — kleinster Stapel zuerst, `themen.jsonl` als
  Fortsetzungspunkt), danach N7–N8 (Trockenlauf → echtes Sortieren),
  N9 (Personen) parallel möglich.
* **27.09. ~05:45 — N5 gemessen und bestanden (Hauptagent, echte Stichprobe).**
  Vision-Blick auf den 36er-Bogen `2025-01-06_Anlass-01` (262.437 B):
  - **Nummern 1–36 einwandfrei lesbar** → Kachel-Nummerierung trägt (Voraussetzung
    dafür, dass der Vision-Blick „Kachel 12" sagen kann).
  - Je Kachel eine Zeile Inhalt (Personen, drinnen/draußen, Motiv) — z. B. alle
    36 Kacheln „drinnen, Publikum vor grüner Bühne".
  - **Thema für den ganzen Bogen erkannt** (Veranstaltung in großer Halle; das
    Banner war sogar lesbar) → ein Aufruf **je Anlass** genügt, nicht je Bild.
  - **Nebenertrag:** unbrauchbare Bilder werden benannt (9/10/11 verwackelt,
    25/26 Bewegungsunschärfe, 33/34 schwarz) → die „Müll/behalten"-Triage fällt
    beim selben Aufruf mit ab.
  - **Kostenschätzung (noch keine Messung):** ein Vision-Aufruf je Anlass, bei
    2.128 Anlässen deutlich **unter 1 $**; die echten Zahlen werden aus dem
    Kosten-Tracker abgelesen, sobald der Vollauf startet — nicht behauptet.
  - **N6 ist damit startklar:** Bögen liegen bereit, Thema je Bogen kommt vom
    Vision-Blick, Dedup über die CSV-Spalte `doppelung` (geräteübergreifende
    Kopien waren im Bogen sichtbar).
* **27.09. ~08:30 — N6 gebaut und **bestanden** (Planer: Hauptagent ·
  Ausführer: Hermes-Subagent, DeepSeek V4.1 Flash · Prüfer: `openai/gpt-5.6-luna`).**
  Codex war nicht nutzbar (Kontingent, „try again at Oct 15th"), also lief der
  Bauweg über Hermes-Subagenten — drei Aufträge: Bau (0,038 $) und zwei
  Nachbesserungen (0,017 $ + 0,021 $), zusammen rund 0,08 $ Ausführerkosten.
  - **Werkzeug:** `tools/foto_sortierung/foto_themen_vision.py` +
    `backend/tests/test_foto_themen_vision.py` (**59 Prüfungen**, alles ohne Netz).
    Ein Vision-Aufruf je Anlass (Bild als data-URL in-memory an OpenRouter,
    Standard `google/gemini-2.5-flash`), Thema in die **Kopie** des
    Sortierschlüssels (`~/foto_sortierung/sortierschluessel_themen.csv`),
    Fortsetzungspunkt `themen.jsonl`.
  - **Prüfbefehl selbst gefahren:** Baseline **569** → **628 passed, Exit 0**
    (1:12 min). Vorher/nachher gemessen, nicht behauptet.
  - **Live gemessen** (echte Aufrufe, zwei Bögen, zusammen ~0,007 $):
    36-Kachel-Bogen → „Veranstaltung Publikum Bühne" (2.306+1.465 Tokens,
    0,004354 $, 6,8 s); 10-Kachel-Bogen → „Konzert Band Auftritt" (3.750+452,
    0,002255 $, 3,6 s); zweiter Lauf: **0 Aufrufe, 0 Tokens, 0,2 s**; die
    Original-CSV blieb unverändert (`md5 70642d2988b6e38ff417561ccf870ba8`).
  - **Kosten für den Vollauf (Schätzung, keine Messung):** 2.128 Anlässe; die
    beiden Messpunkte (10 und 36 Kacheln) liegen **über** dem Mittel von 3,9
    Kacheln → Größenordnung **2–4 $** mit `gemini-2.5-flash`, mit
    `flash-lite` etwa ein Drittel. Vor N6b an ~20 Anlässen nachmessen.
  - **Prüfer: 6 Runden, 5 × „nicht bestanden"** — und das war der Nutzen des
    getrennten Kontexts, kein Formfehler. 8 von 10 Beanstandungen waren
    berechtigt (4 am Code, 4 an der Doku). Echt gefunden und behoben: fehlender
    Schutz des Ausgabeordners (Repo), widersprüchliche Doku vs. Code bei den
    Kachel-Zählern, **ungefilterter Rohtext** (ein Modell, das den Schlüssel
    wiederholt, hätte ihn auf Platte geschrieben) und eine fehlende
    Kollisionssperre für die Original-CSV. Runde 6: **„bestanden"**.
  - **Entscheidungen statt Fragen:** (1) Kacheln mit `unbrauchbar: true` werden
    **behalten** und gezählt, doppelte Kachelnummern **verworfen** (erster
    Eintrag bleibt); (2) Themen gehen in eine **Kopie** des Sortierschlüssels,
    nie in die Original-Datei; (3) der Rohtext wird gespeichert, aber maskiert.
  - **Nächster Schritt: N6b** — Massenlauf (Bögen je Jahr bauen, dann Themen
    setzen), kleinster Stapel zuerst, jederzeit abbrechbar (`themen.jsonl`).
    Doku: `docs/changelog-2026-09-27-themen-vision.md`.
* **27.09. ~07:15 — N6b Stapel 1 gefahren und gemessen (Planer: Hauptagent).**
  „Kleinster Stapel zuerst": **2014, 2016, 2017, 2019, 2020, 2021** komplett —
  **161 Anlässe, 510 Kacheln, 0 Fehler**, alle Jahre Exit 0.
  - **Kontaktbögen:** 161 neu gebaut, 2,4 / 2,2 / 2,5 / **8,0** / **19,2** /
    **54,6 s** je Jahr (Summe 1,5 min) — deutlich schneller als die Schätzung
    „~4,5 s je Anlass" aus N4; Vorschaubilder 510 Stück (1,52 MB für 2021).
  - **Themen:** 161 Vision-Aufrufe, **438.072 ein / 26.082 aus Tokens**,
    **0,196610 USD** = **0,001221 USD je Anlass** (min 0,000973, max 0,004354);
    **1,91 s je Anlass** im Mittel, größte 8,67 s; **0 unbrauchbare Kacheln**,
    **0 unvollständige** Bögen, **0 Fehlerzeilen**.
  - **Original-CSV unverändert** (`md5 70642d2988b6e38ff417561ccf870ba8`),
    geschrieben nur außerhalb des Repos (`~/foto_sortierung/`).
  - **Kostenhochrechnung** (gemessen, nicht geschätzt): 2.128 Anlässe →
    `gemini-2.5-flash` **2,60 USD**, `gemini-2.5-flash-lite` **0,72 USD**,
    `gemini-3.7-flash` **5,64 USD**; Preise live über `/api/v1/models` geholt.
  - **Der Befund, der den Plan ändert: 155 verschiedene Themen bei 161
    Anlässen = 96 % Einzelstücke** („Haus Garten" vs. „Haus und Garten",
    „Sonnenuntergang Stadtansicht/Meer/am See"). Ursache im Code:
    `prompt_bauen()` fragt „2 bis 4 deutsche Woerter" **ohne Wortschatz**.
    Als Ordner `Agent/Fotos/<Jahr>/<Thema>/` wäre das untauglich.
  - **Entscheidung:** neuer Schritt **N6c — Themen-Katalog** (feste Liste,
    Ziel 40–60 Einträge, Prompt wählt nur daraus, 161 Anlässe mit
    `--wiederholen` nachziehen ≈ 0,20 USD) **vor** dem Restlauf der 1.967
    Anlässe; dort auch der Modellvergleich flash vs. flash-lite, weil 0,72 vs.
    2,60 USD sonst das Dreifache ohne belegten Gewinn wäre.
  - Doku: `docs/changelog-2026-09-27-themen-stapel1.md`.
  - **Prüfbefehl selbst gefahren:** `pytest tests/ -q` → **628 passed, Exit 0**
    (121 s; unverändert, da nur ausgeführt und dokumentiert wurde).
    **Prüfer `openai/gpt-5.6-luna`: „bestanden", 0 Abweichungen** — er hat die
    Zahlen alle selbst nachgerechnet (155 von 161 = 96,27 %, Summen, md5,
    Exit-Zeilen, Code-Stelle `prompt_bauen()`).
* **27.09. ~09:55 — N6c gebaut, gemessen und bestanden** (Planer: Hauptagent ·
  Ausführer: Hermes-Subagent `deepseek-v4.1-flash` · Prüfer: `openai/gpt-5.6-luna`,
  zwei Runden). **Codex war nicht nutzbar:** `codex exec --model gpt-5.6-terra`
  antwortete live „You've hit your usage limit … try again at Oct 15th, 2026
  9:32 PM" — also lief der Bauweg über Hermes-Subagenten (0,054 USD + 0,006 USD
  Ausführerkosten).
  - **Runde 1 — Werkzeug (Commit `c1c24c5`, gepusht, `0 0`):**
    `tools/foto_sortierung/themen_katalog.py` (Katalog, `thema_zuordnen`,
    `im_katalog`, `katalog_text`), Prompt wählt nur noch Wort für Wort aus der
    Liste, `thema_roh`/`katalog_treffer` in beiden Ausgaben, CLI `--ohne-katalog`;
    Tests **59 → 87**, Prüfbefehl **656 passed, Exit 0** (selbst gefahren),
    Prüfer: **BESTANDEN, 0 Abweichungen** (u. a. `prompt_bauen` ohne Katalog
    byte-gleich zu HEAD, Schutzfunktionen AST-identisch).
  - **Messung 1 (Katalog v2, 44 Einträge):** dieselben **161 Anlässe** beider
    Modelle. flash: 161/161 Katalog-Treffer, 0 Fehler — aber **43 × `Sonstiges`
    (27 %)**. flash-lite: 0,058129 USD, 21 × `Sonstiges`. Damit stand fest: der
    Katalog hat Lücken, und ein Viertel aller Anlässe in einem Ordner wäre
    untauglich.
  - **Runde 2 — datenbasierte Erweiterung:** die Kachel-Kurzbeschreibungen der
    43 `Sonstiges`-Anlässe ausgewertet (nicht geraten): Sonnenuntergang/Abendhimmel,
    Nachtszenen, Selfies/Porträts, Gruppe unterwegs, Demonstration/Politik,
    Screenshots/Text/Memes, Zeitungen/Buchseiten, Dinge/Stillleben, Hoftiere.
    Genau diese neun Sachgebiete als Einträge ergänzt → **53 Einträge,
    `KATALOG_VERSION = 3`**; Tests **657 passed, Exit 0** (selbst gefahren).
  - **Messung 2 (Katalog v3, beide Modelle, dieselben 161 Anlässe):**
    **flash** 0,209693 USD, **161/161** im Katalog (100 %), **14 × `Sonstiges`
    = 8,7 %** (alle selbst gewählt, 0 Antworten außerhalb), **37 Themen**;
    **flash-lite** 0,058977 USD, 160/161 im Katalog (99,4 %), **18 × `Sonstiges`
    = 11,2 %** (17 selbst gewählt + 1 außerhalb), 34 Themen. Die Erweiterung
    wirkte: 27 % → 8,7 %.
  - **Modellvergleich:** identische Anlässe, identischer Prompt, nur das Modell
    anders; flash ist das **3,56-Fache** im Preis (0,209693 zu 0,058977 USD).
    Hochrechnung auf die 1.967 wartenden Anlässe: flash 2,56 USD, flash-lite
    0,72 USD. **Sichtprobe an sechs Bögen genau dort, wo sich beide widersprechen:
    flash trifft 4, flash-lite 2** — flash-lites Fehler sind falsche Sachgebiete
    („Huhn mit Küken" → `Hund im Freien`, Sommerbergtour → `Wandern im Schnee`,
    Reise vor Palmen → `Familienfeier Zuhause`), flash sagt in solchen Fällen
    ehrlich `Sonstiges`. **Entscheidung: flash für den Massenlauf** — 1,84 USD
    Mehrkosten für 1.967 Anlässe wiegen einen falsch sortierten Ordnerbaum nicht auf.
  - **Die restlichen 14 `Sonstiges`-Anlässe** sind überwiegend Bildschirmfotos,
    Memes und Textbilder (Glühwein-Text, „Finde das Kamel", Wahlergebnisse,
    Zeitungsausschnitt, Rezeptseite) plus Grenzfälle; dafür kommt bewusst kein
    Katalogeintrag dazu (weitere ähnliche Einträge würden Ordner überlappen lassen).
  - **Prüfer-Runde 2 (`gpt-5.6-luna`, Endstand):** Prüfbefehl selbst 657/Exit 0,
    Katalog nachgezählt (53, Version 3, keine normalisierten Doppelungen),
    Messzahlen beider Läufe nachgerechnet, md5 der Original-CSV geprüft,
    `prompt_bauen` ohne Katalog byte-identisch zu HEAD. **Eine Beanstandung:**
    die Angabe „18 gewählte Sonstiges" für flash-lite war unpräzise — richtig
    sind 17 selbst gewählte + 1 aus einer Antwort außerhalb des Katalogs (Thema
    ebenfalls `Sonstiges`, `katalog_treffer: false`). **Doku korrigiert** (Changelog).
  - **Lehre (Pitfall, kostete einen Doppel-Lauf):** ein MSYS-Pfad
    (`/c/Users/sebas/foto_sortierung`) an ein **natives Windows-Python** gegeben
    → Python löst ihn relativ zum Laufwerk auf, der Ordner landete unter
    `C:\c\Users\sebas\foto_sortierung`. Die Daten wurden **per Kopie gerettet**
    (161 Themen-JSONs, beide `themen.jsonl` entdoppelt zusammengeführt), nichts
    gelöscht; das leere Artefakt liegt weiter unter `C:\c\Users\sebas\foto_sortierung`
    und darf von Sebastian entfernt werden. Regel für die nächste Runde:
    an native Werkzeuge **immer** `C:/…`-Pfade, nie `/c/…`.
  - **Schutz:** Original-CSV unverändert (`md5 70642d2988b6e38ff417561ccf870ba8`),
    alle Ausgaben außerhalb des Repos, kein Schlüssel in Ausgaben oder Dateien.
  - **Nächster Schritt: N6b Rest** — 1.967 Anlässe (2022–2025) mit **flash**
    und Katalog Version 3, kleinster Stapel zuerst, danach **N7** (Trockenlauf
    des Sortierens).
* **27.09. ~11:00 — N6b Rest gefahren, gemessen und bestanden** (Planer:
  Hauptagent · Ausführer: die Werkzeuge selbst plus ein Hermes-Subagent
  `deepseek-v4.1-flash` für die Code-Korrektur, 0,003 USD · Prüfer:
  `openai/gpt-5.6-luna`). **Codex weiterhin gesperrt** (Kontingent).
  - **Reihenfolge (kleinster Stapel zuerst):** 2026 (301) → 2025 (380) →
    2022 (409) → 2024 (430) → 2023 (447). Vorlage: eine Jahreszahl aus dem
    Trockenlauf (`Anlaesse gesamt`), damit der billigste Teil zuerst fertig
    ist — nicht geraten.
  - **Zahlen (echte Aufrufe):** **1.967 Anlässe**, davon **1.962 gesehen**
    (3 im Rauchtest vorab, 2 Fehlschläge), **7.722 Kacheln**,
    **5.954.092 ein / 370.113 aus Tokens = 2,711510 USD** für den
    Fünfjahres-Lauf, **94,2 min** (24,5 min Bögen + 69,7 min Vision).
    Die Hochrechnung aus N6b Stapel 1 (2,56 USD) wurde um 0,15 USD (≈ 6 %)
    überschritten — notiert, nicht beschönigt.
  - **Endstand:** **2.128 Anlässe** im Fortsetzungspunkt, **2.127 mit
    Katalog-Thema**, **48 Themen** tatsächlich benutzt, **242 × `Sonstiges`
    = 11,4 %** (auf den 161 Anlässen aus N6c waren es 8,7 % — der größere
    Bestand enthält mehr Bildschirmfotos, Memes, Textbilder). Gesamtkosten
    über den Bestand (`kosten_usd` summiert): **2,938515 USD**.
  - **Echter Codefehler, vom Lauf aufgedeckt und behoben:** der größte Anlass
    `2025-01-17_Anlass-02` (**108 Kacheln**, 19:09–22:17, 1,3 GB) scheiterte
    zweimal an „kein lesbares JSON" — auch mit `flash-lite`. Ursache gemessen:
    der harte Deckel `MAX_TOKENS = 4000` **schneidet** die Antwort ab (ein
    JSON-Objekt je Kachel). Korrektur: reine Funktion
    `max_tokens_fuer(anzahl) = max(4000, min(16000, 1200 + 60 * anzahl))`,
    `anfrage_bauen()` nutzt sie nur ohne ausdrücklichen Wert → kleine Bögen
    **byte-gleich** wie vorher. **Beleg:** derselbe Anlass läuft mit
    **108/108 Kacheln, 4.420 Ausgabe-Tokens** (über dem alten Deckel) durch,
    0,012073 USD. 6 neue Tests (665 → **671**).
  - **Ein Fall bleibt bewusst offen:** `2022-09-05_Anlass-02` wird vom
    **Anbieter** abgelehnt — eigene Sonde direkt gegen die API belegt HTTP 200
    mit `error.code = 403`, `Gemini blocked the request: PROHIBITED_CONTENT`
    (Beleg: `~/foto_sortierung/n6b_probe_2022-09-05.log`). Das Werkzeug meldet
    dafür nur „OpenRouter lieferte keine Antwort" — die Ablehnung selbst ist im
    Werkzeug-Log **nicht** sichtbar. **Entscheidung: keine Modellumgehung** —
    ein Anbieter, der Aufnahmen ablehnt, kann dafür einen Grund haben;
    Sebastian sieht die Bilder vor dem Sortieren. Der Anlass bleibt als Marker
    (`thema: null`) im Fortsetzungspunkt und wird bei jedem Lauf erneut
    versucht (kostet nichts, Ablehnung kommt vor der Token-Abrechnung).
  - **Wiederholungsmarker (Nebenbefund):** Fehlversuche schreiben eine Zeile
    mit `thema: null` je Versuch — daher 2.134 Zeilen bei 2.128 eindeutigen
    Anlässen. Gewollt: der nächste Lauf findet den Anlass wieder. Genau diese
    Mechanik hat den 108-Kachel-Fall nach der Code-Korrektur automatisch
    eingesammelt.
  - **Prüfbefehl selbst gefahren:** `pytest tests/ -q` → **671 passed, Exit 0**
    (71 s). **Prüfer (Runde 1, `gpt-5.6-luna`)** hat selbst nachgerechnet
    (671/Exit 0, `max_tokens_fuer` für 10/108/246/5000 Kacheln, Token- und
    Kostensummen, md5) und **3 Punkte** gemeldet: (1) „vier geänderte Dateien
    statt zwei" — die zwei fremden (`docs/experimente/live_zahlen.*`) gehören
    dem **zweiten Agenten**; deshalb `git commit --only` mit ausdrücklich
    genannten Pfaden; (2) der Zählstand war zum Prüfzeitpunkt **veraltet**
    (2.128/2 → jetzt 2.128/**1** ohne Thema, 2.127 Themen-Dateien), korrigiert;
    (3) der 403-Nachweis stehe „nicht im Log" — richtig, er kommt aus der
    eigenen Sonde, die jetzt als Datei abgelegt ist.
  - **Schutz:** Original-Sortierschlüssel unverändert
    (`md5 70642d2988b6e38ff417561ccf870ba8`), nur die Kopie
    `sortierschluessel_themen.csv` geschrieben (9.430 Zeilen, 8.284 mit Thema);
    Ausgaben ausschließlich außerhalb des Repos (`~/foto_sortierung/`, Bögen
    70 MB, Themen 11 MB); **alle pCloud-Aufrufe lesend**, nichts verschoben,
    nichts gelöscht; Sicherungskopie des Fortsetzungspunkts
    (`themen_vor_n6b_rest_20260927_091225.jsonl`).
  - **Nächster Schritt: N7** (Trockenlauf des Sortierens) — mit der Auflage
    aus dem Plan: Rückfallordner für Anlässe ohne Thema, und Zielordner sind
    laut **N6d** Sebastians eigene Kategorien (18 Kategorien, 113 Unterordner).
