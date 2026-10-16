# Workspace Agentic Engineering — Kernregeln

Gilt werkzeugübergreifend (Claude Code, Cline, Cursor, Codex). Einzige Quelle
der Kernregeln — Änderungen nur hier.

## Wo welche Regeln stehen

| Ebene | Datei | Wann sie gilt |
|---|---|---|
| Kern | `AGENTS.md` (diese Datei) | immer, in jedem Werkzeug |
| Claude-Code-Spezifisches | `CLAUDE.md` | immer, nur in Claude Code |
| Bereich | `01_IT-OT_Integration/CLAUDE.md`, `02_Softwareentwicklung_IT/CLAUDE.md` | sobald Dateien aus dem Bereich gelesen werden |
| Projekt | z. B. `02_Softwareentwicklung_IT/typeFREE/CLAUDE.md` | sobald Dateien des Projekts gelesen werden |

**Bereichs- und Projekt-`CLAUDE.md` erzeugt `sync-rules.ps1` aus der jeweiligen
`CLAUDE_EXTENDS.md`.** Nicht von Hand bearbeiten — Änderungen gehen beim nächsten
Lauf verloren. Stattdessen die `CLAUDE_EXTENDS.md` ändern und das Skript erneut
ausführen.

## Sprache

Antworten auf Deutsch. Fachbegriffe beim ersten Auftreten in einem Halbsatz
erklären.

## Sicherheit: Git

- Autonom erlaubt: lesen, lokal ändern, lokal committen, Tests ausführen.
- **Push: stehende Freigabe (Stand 15.09.2026, auf Sebastians ausdrücklichen
  Wunsch).** Ein Push nach **grünem Prüfbefehl** ist autonom erlaubt — Sebastian
  testet damit direkt am Handy, und ein Push ist jederzeit rücknehmbar
  (`git revert` / Zurücksetzen im Remote). Der Agent pusht **sofort nach** einer
  verifizierten Änderung, ohne jedes Mal nachzufragen.
- **Rückfrage bleibt Pflicht** (es geht um Datenverlust) bei:
  - **rotem/fehlendem Prüfbefehl** — nicht pushen, erst reparieren,
  - **Merge-/Rebase-Konflikten** oder divergierenden Historien,
  - **force-push / Überschreiben fremder Commits**,
  - Änderungen an **OT-/SPS-Code** oder **persönlichen Datenarchiven**
    (dort gilt weiterhin alles manuell).
- **Autonomiegrenze:** Rückfrage außerdem bei allem, was den Rechner verlässt
  oder ein fremdes System erreicht, außer dem erlaubten Push: Deploy, SPS,
  Versand, Veröffentlichung.

## Synchronisation: Pull vor Agentenarbeit

Zu Beginn der Arbeit an einem Repo, noch bevor Dateien gelesen/geladen oder
Commits gemacht werden, holt der Agent den gemeinsamen Stand: `git pull` (ggf.
`--ff-only`). So startet jede Sitzung vom selben Stand, egal ob zuvor per App wie
`start-termux.sh` gepullt wurde, ein anderer Agent/Computer gepusht hat oder das
Repo nur lokal liegt. Schlägt der Pull fehl (z. B. lokale Änderungen, Konflikt),
wird er nicht übergangen, sondern Sebastian gefragt.

## Sicherheit: Persönliche Datenarchive

`Chats von GPT, GEMINI, Claude/` enthält vollständige Chat-Archive und
Google-Takeout-Daten. Die Sperre in `.gitignore` dafür bleibt bestehen. Soll
etwas daraus versioniert werden, wird die Datei außerhalb dieses Ordners neu
angelegt.

## Sicherheit: OT-Systeme

Änderungen an einer laufenden SPS führt Sebastian manuell aus. Der Agent
liefert Code-Blaupausen.

## Arbeitsweise

- Pro Antwort eine Änderung, dann Rückmeldung abwarten.
- Vor jeder Auswahlfrage zuerst dieses Briefing ausgeben:
  **Was** (1–2 Sätze) · **Warum** · **Was bleibt unverändert** ·
  **Risiko** (Keins / Gering / Mittel / Hoch)

## Tüfteln erlaubt, aber strukturiert

Pragmatisches Ausprobieren ist ausdrücklich erlaubt. **Aber:** ohne gelegentliche
Reflexion driftet es ins Chaos um. Deshalb:

- Nach jedem größeren Ad-hoc-Arbeitsblock kurz **innehalten**: Was wurde gebaut?
  Wo ist Code-Wildwuchs? Konsolidieren (Squash/Refactor)? Arbeitsweise
  reflektieren? Das dokumentiert sich in der Übergabe/Changelog.
- Kein dauerhaftes "Feuerwehr von Einsatz zu Einsatz": Wird ein Bereich
  unsauber (Code-Duplikat, fehlende Tests, inkonsistente Muster), wird er
  standardisiert statt weiter darauf zu schustern.
- "Fertig ist, was verifiziert ist" und "Doku folgt dem Code" gelten **immer** —
  auch bei schnellen Tüfteleien.

## Dokumentation folgt dem Code

Jede Änderung an Code/Tools/Konfiguration wird in der zugehörigen Dokumentation
(README, docs, CHANGELOG/Änderungsprotokoll) nachgezogen und gemeinsam
committet. Die Dokumentation ist Teil der Bewerbungsmappe und muss CODEGENAU
sein: sie darf nichts behaupten, was der Code nicht tut.

- Bei jeder signifikanten Änderung: betroffenes README/docs/Protokoll prüfen →
  aktualisieren → ein gemeinsamer Commit („code + docs").
- Doku nie auf "später" verschieben: sie beschreibt den NEUEN Stand.

## Fertig ist, was verifiziert ist

Ein Schritt gilt als fertig, wenn der Prüfbefehl des Projekts Exit-Code 0
liefert. Ohne Prüfbefehl: benennen, welcher fehlt.

Vor jeder Aussage über Fertigstellung — auch vor „läuft", „behoben", „grün":
1. Welcher Befehl belegt sie? 2. Befehl frisch und vollständig ausführen.
3. Ausgabe und Exit-Code lesen. 4. Deckt die Ausgabe die Behauptung?
5. Erst dann die Aussage — zusammen mit dem Beleg.

Wurde der Befehl nicht in dieser Antwort ausgeführt, gilt er als nicht
ausgeführt. Ein früherer Lauf, die Erfolgsmeldung eines Subagenten und
„müsste jetzt gehen" sind keine Belege.

## Automatischer Durchlauf

Der feste Phasen-Workflow (`/phase`) ist **abgelöst**: gearbeitet wird
kontinuierlich und hybrid (Codex für Coding-Blöcke, Hermes für
Qualität/Orchestrierung). Es gelten weiterhin:

1. Das Projekt hat einen Prüfbefehl mit Exit-Code.
2. „code + docs": jede Änderung wird dokumentiert und gemeinsam committet.
3. Es ist kein OT-/SPS-Code (dort bleibt alles manuell bei Sebastian).

Hat ein Projekt **keinen** Prüfbefehl, wird jede Änderung einzeln vorgelegt.

## Rollen und Datenschutz im Agenten-Workflow

Kaskaden-Matrix (Sebastian, 14.10.2026). Die Lage richtet sich danach, welches
Abo im Nutzungslimit ist (Anzeige: `02_Softwareentwicklung_IT/master-schalter`,
Taskleisten-Symbol).

| Lage | Thinker (plant, prüft Ergebnisse gegen den Plan) | Reviewer (Plan- und Ergebnisprüfung) | Worker (setzt um) |
|---|---|---|---|
| 1 Beide Abos frei (0 € extra) | Claude Opus 5.5 (Claude Pro) | GPT-6 Sol (ChatGPT Plus / Codex) | GPT-6 Luna / Claude Sonnet 5.5 (Abos) |
| 2A Claude im Limit | GPT-6 Sol (ChatGPT Plus / Codex) | DeepSeek V4.1 Flash (OpenRouter) | GPT-6 Luna (ChatGPT Plus) |
| 2B ChatGPT im Limit | Claude Opus 5.5 (Claude Pro) | DeepSeek V4.1 Flash (OpenRouter) | Claude Sonnet 5.5 (Claude Pro) / DeepSeek V4.1 Flash (OpenRouter) |
| 3 Beide im Limit | DeepSeek V4.1 Flash (OpenRouter/Hermes) | DeepSeek V4.1 Flash (OpenRouter) | DeepSeek V4.1 Flash (OpenRouter) |

- **Thinker denkt, Worker arbeiten:** Umsetzung läuft über Subagenten bzw. Ausführer mit dem
  günstigeren Worker-Modell, nicht auf der höchsten Stufe. Der Thinker plant und nimmt ab.
- **Reviewer ≠ Thinker-Modellfamilie** — gilt in den Lagen 1, 2A und 2B (dort steht der Prüfer
  ohnehin auf dem anderen Abo bzw. in der Matrix). **Solo-Regel (Sebastian, 16.10.2026): Ist Hermes
  solo (Lage 3, beide Abos im Limit), wird keine zweite Modellfamilie fürs Prüfen angesetzt** —
  Prüfer und Ausführer laufen beide auf DeepSeek V4.1 Flash; die Trennung leisten frischer Kontext
  und Rollentrennung. (GPT-6 Luna als Prüfer ist abgelöst: Input-Preis 5x.)
- Keine Selbstfreigabe durch
  den Ausführerlauf; Ausführer und Prüfer laufen in frischen Kontexten.
- **Kosten:** Lagen 2A, 2B und 3 nutzen OpenRouter-API — das kostet echtes Geld; Kosten
  stehen im Prüfprotokoll.
- **Sensibel:** Ob etwas sensibel oder sicherheitskritisch ist, entscheidet der Thinker und
  schreibt die Einordnung in den Plan. Die Matrix gilt nur für Code; Sensibles siehe unten.
- **Keine stille Wahl** eines Modells außerhalb der Matrix.
- **Automatische Übergabe Claude → Codex: freigegeben (Sebastian 15.10.2026, v0.3.0).**
  Gilt nur für aktivierte Themen-Paare, nur bei frischer Messung an der Schwelle, ein Vorgang je
  Limitfenster; der Rückweg Codex → Claude bleibt manuell. Der abgebende Master hält die laufende
  Übergabe-Datei `.hermes/uebergabe/laufend/<thema>.md` technisch aktuell (Kopfzeile
  `Übergabebereit: ja|nein · <ISO-Zeit> · <HEAD-Kurzform>`) und prüft vor jedem neuen Schritt
  `<thema>.master`.
- **Stand der Werkzeuge (ehrlich):** `tools/pruefkreis/pruefkreis.py` (personal_ai_agent)
  prüft heute mit Codex (App-Standardmodell) und weicht bei Codex-Sperre automatisch auf
  Hermes mit DeepSeek V4.1 Flash aus — das entspricht noch nicht ganz Lage 2B (dort GPT-6 Luna).
  Die Prüferwahl nach Matrix wird im Master-Schalter nachgezogen; bis dahin steht der
  tatsächlich genutzte Prüfer im Prüfprotokoll.

**Alles Sensible bleibt IMMER bei Hermes**, unabhängig davon, wer Master, Planer,
Ausführer oder Prüfer ist. Persönliche Texte, Lebenslaufdaten, Chats, Kontakte,
echte Kennungen, private Pfade, Zugangsschlüssel, Bildinhalte sowie persönliche
Beschreibungen und Vektoren verarbeitet ausschließlich Hermes über den vom Nutzer
freigegebenen Zugang mit Retention-Ausschluss. Codex und Claude Code bearbeiten
Code, Tests, technische Beschreibungen und Architektur. Eine Master- oder
Prüferrolle erteilt ihnen keine zusätzliche Berechtigung für sensible Inhalte.
Benötigte Datenprüfungen laufen bei Hermes; die technischen Agenten erhalten nur
bereinigte Anforderungen und Belege.

**Freigabe und Gegenprüfung:** Der Master erstellt den Plan. Vor der Umsetzung
prüft der zugeordnete andere Prüfer den aktuellen Plan kritisch und gibt den
technischen Umfang frei. Erst danach führt der Ausführer in kleinen, ausdrücklich
zugeordneten Änderungen aus. Anschließend prüft der andere Prüfer die Ergebnisse
anhand eigener Belege. Selbstprüfung ersetzt die Gegenprüfung nicht. Freigabe,
tatsächliches Prüfmodell, Planfassung und offene Blocker werden lokal
dokumentiert. Keine Antwort ist keine Freigabe. Veröffentlichung und sensible
Arbeit bleiben an die gesonderten Nutzergrenzen gebunden.

### Personal AI: Hermes-Master und Codex-Code-Worker

Im Thema `personal-ai-agent` bleibt Hermes der Master für sensible Inhalte,
Planung und Rollenentscheidung. Codex `gpt-6-luna` aus der vorhandenen ChatGPT-
Anmeldung darf ausschließlich bereinigten Code, Tests und technische Dokumente
bearbeiten. Freie Codex-Quota ändert die Masterrolle nicht. Die Themenauswahl im
Master-Schalter legt nur diese Rollenregel fest; sie startet keine Sitzung und
erzeugt kein Empfangs-ACK.

Vor dem Workerstart bestätigt Hermes lokal mit `codex login status` die Anmeldung
`chatgpt`. Die rohe Statusausgabe bleibt lokal und wird weder protokolliert noch
weitergegeben. Bei fehlender ChatGPT-Anmeldung, Limit oder Fehler gibt es keinen
API-Key-, OpenRouter- oder Abrechnungs-Fallback. Der Auftrag enthält keine
Originaltexte, Screenshots, privaten Pfade oder Zugangsdaten; der Worker arbeitet
in einem eigens bereitgestellten technischen Worktree. Für echte Aufträge wird
`--ephemeral` nicht verwendet, damit der Chat fortsetzbar bleibt.

```powershell
$CodexExe = 'C:\Users\sebas\AppData\Local\OpenAI\Codex\bin\e78bad9887fa50cf\codex.exe'
$WorkerWorktree = '<isolierter technischer Worktree>'
$PromptFile = '<bereinigter technischer Auftrag.md>'
$ResultFile = '<technisches Ergebnis.md>'
Get-Content -Raw -LiteralPath $PromptFile | & $CodexExe exec --json --ignore-user-config `
  -c model_provider=openai -c forced_login_method=chatgpt -m gpt-6-luna `
  --sandbox workspace-write -C $WorkerWorktree --output-last-message $ResultFile -
```

Der Aufruf nutzt die Codex-App-Anmeldung, nicht einen API-Schlüssel. Vorher
entfernt Hermes mögliche API-/Provider-Schlüsselvariablen ausschließlich aus
der Worker-Kindprozess-Umgebung. Der Auftrag darf nur den ausdrücklich
bereinigten Projektumfang freigeben; kein Sandbox- oder Freigabe-Bypass.

**Prüfprotokolle zeigen (Sebastian, 14.10.2026):** Sebastian ist „Human in the
Loop" als **Beobachter, nicht als Entscheider**. Nach jeder Prüfrunde — Plan- oder
Ergebnisprüfung, Codex oder Hermes — legt der Master das Protokoll
(`.hermes/pruefkreis/<thema>.md`) sofort als aufklappbare Datei in den Chat
(Claude Code: `SendUserFile`), dazu eine Zeile: Urteil und was der Master daraus
macht. Danach geht die Arbeit ohne Warten weiter; das Zeigen ist keine Rückfrage.
Grund: Codex-Prüfläufe sind flüchtig (`--ephemeral`), Hermes-Prüfsitzungen werden
nach Abschluss geschlossen — sonst sieht Sebastian nicht, was geprüft wurde.

## Lebenszyklus eigener Prüfchats

Festgelegt 10.10.2026: Feedback bleibt im Master; eigene Prüfchats werden nach
Abschluss der zugehörigen Diskussion gelöscht.

- Der Master behält das bereinigte Feedback, die Entscheidung, offene bzw.
  erledigte Befunde und notwendige Prüfbelege. Sensible Originalinhalte bleiben bei
  Hermes und werden nicht in einen Codex-/Claude-Master übernommen.
- Ein beendeter Modelllauf oder das erste Feedback allein ist KEIN Diskussionsabschluss.
  Abgeschlossen ist die Diskussion, wenn alle Befunde entschieden und dokumentiert
  sind oder der Nutzer sie ausdrücklich für abgeschlossen erklärt.
- Erst danach entfernt der Master die Anpinnung und löscht genau die zugehörigen,
  von diesem Workflow angelegten Prüfersitzungen anhand ihrer registrierten exakten
  Sitzungskennungen. Der Nutzer hat diese Bereinigung bereits freigegeben; keine
  erneute Löschrückfrage bei erfüllten Voraussetzungen.
- Master-Chats, Ausführer-Chats, fremde Sitzungen, persönliche Archive und Originaldaten
  sind AUSGESCHLOSSEN. Keine pauschale Bereinigung, kein Löschen nach
  Titelmustern, kein Prune und kein Reparieren oder Neuaufbauen der Sitzungsdatenbank.
- Prüfchats sind während der offenen Diskussion sichtbar und bei Bedarf angepinnt.
  Nach deren Abschluss dürfen sie trotz Anpinnung entfernt werden.
- Vor dem Löschen: Feedback im Master gesichert, Diskussion geschlossen, Besitz/
  Rolle der exakten Sitzungskennung geprüft. Ist etwas unklar, Sitzung behalten und
  den Blocker nennen. Nach dem Löschen nur den technischen Bereinigungsnachweis
  festhalten; keine vollständigen Prüfchat-Exporte als Ersatzkopie anlegen.

## Kontext-Hygiene

Ab etwa 60 % Kontextnutzung: Zwischenstand in die Plandatei schreiben und
`/clear` vorschlagen.

## Dauerlauf / Nachtarbeit (autonom)

Sebastian kann einen **Dauerlauf** beauftragen („arbeite 4–5 Stunden durch, keine
Fragen"). Dann gilt zusätzlich:

1. **Keine Rückfragen.** Entscheidungen selbst treffen und im Planjournal
   begründen — Auswahlfragen werden nicht gestellt, sondern entschieden.
2. **Plan als Datei.** Vor dem Start `.hermes/plans/<thema>.md` anlegen:
   nummerierte Schritte, je Schritt das Prüfkriterium. Erledigtes wird abgehakt,
   Blockiertes landet **mit Grund** im Journal — und es geht mit dem **nächsten**
   Schritt weiter. Nie stehenbleiben, nie auf den Nutzer warten.
3. **Jeder Schritt wird verifiziert und einzeln committet** („code + docs").
   Kein Commit ohne grünen Prüfbefehl; rote Schritte werden nicht umgangen.
4. **NIE löschen — nur kopieren und verschieben.** Gilt für alle fremden Systeme
   (pCloud, Handy, bestehende Ordner). Bei Unsicherheit: nur lesen.
5. **Rückholbarkeit ist Pflicht.** Jede schreibende Operation auf einem fremden
   System kommt in ein **Manifest** (Quelle → Ziel, Zeit, Kennung). „Wie mache ich
   das rückgängig?" wird **vor** der Operation beantwortet, nicht danach.
6. **Idempotent bauen.** Jedes Werkzeug muss mehrfach laufen dürfen, ohne Schaden
   (vorhandenes Ziel = überspringen, nie doppelt anlegen).
7. **Kostengrenze.** Billigste Wege zuerst (Vorschaubilder statt Originale,
   Stapel statt Einzelaufrufe). Teure Wege (Vision über alles) vorher an einer
   Stichprobe messen, nicht ins Blaue fahren.
8. **Wiederaufnahme sichern.** Fortsetzungspunkt festhalten (Plan + Journal),
   damit ein Neustart — neue Sitzung, Cron-Aufruf, anderer Rechner — dort
   weitermacht statt von vorn.

### Mehrere Agenten im selben Arbeitsbaum (Kollisionsschutz)

Arbeitet ein zweiter Agent (andere Sitzung, Cron, Handy) im **selben**
Arbeitsbaum, gilt:

- **Nie `git add -A`, nie `git commit -a`.** Stattdessen
  **`git commit --only <Pfad> <Pfad>`** mit ausdrücklich genannten Dateien —
  so bleiben fremde, halbfertige Änderungen draußen.
- **Neue Dateien und amend (Lehre 15.10.):** `git commit --only` erfasst **keine** neuen
  (untracked) Dateien — neue Dateien vorher mit `git add <Pfad>` vormerken, sonst entsteht ein
  unvollständiger Commit (der Hook bleibt trotzdem grün, weil er den Arbeitsbaum testet).
  `git commit --amend` (ohne Pfade) nimmt den **ganzen** Index mit — vorher
  `git status --short` auf fremde `A `-Einträge prüfen; liegen fremde gestagte Dateien im Index,
  sie mit `git rm --cached <Pfad>` aus dem eigenen Commit nehmen und danach wieder `git add`en
  (Staging-Stand des anderen Strangs wiederherstellen).
- Bei `cannot lock ref 'HEAD'` oder abgelehntem Push: **`git pull --rebase`**,
  dann erneut committen/pushen. **Niemals** `--force`.
- Vor jedem Commit `git log --oneline -3` lesen: hat jemand anders gerade
  gearbeitet, erst einordnen, dann den eigenen Schritt machen.
- Nach dem Push `git rev-list --left-right --count origin/main...HEAD` prüfen
  (`0 0` = lokal und remote gleich).

### Zwei Claude-Modi und Hermes (GitHub-Issues als gemeinsame Tafel)

| | Master-Chat (Claude Code am PC) | Cloud-Sitzung (Claude Code bei Anthropic) |
|---|---|---|
| Wann | 5-Stunden-Limit des Abos frei | Limit erschöpft, PC aus oder unterwegs |
| Sieht | PC, Hermes, Handy per Kabel | nur GitHub (`.hermes/` ist per `.gitignore` gesperrt) |
| Pusht | `main`, nach grünem Prüfbefehl | nur `claude/<thema>`, nie `main` |
| Absprache | GitHub-Issues; Hermes über eigene Sitzungen | GitHub-Issues |
| Issue-Label | `claude-pc` | `cloud` |

Der Agentenbus (`personal_ai_agent/tools/agentbus/`) wird seit 14.10.2026 nicht
mehr benutzt; Hermes-Arbeit läuft über eigene Hermes-Sitzungen
(`tools/pruefkreis/pruefkreis.py`), die der Master startet und schließt.

- **Auf `main` pusht nur der PC** (Master-Chat oder Hermes). Nur dort laufen der
  Windows-Prüfbefehl und der Handytest per Kabel. Das Handy zieht `main` beim Start,
  also bleibt `main` grün.
- **Cloud-Branches führt der PC zusammen:** `git fetch` →
  `git merge origin/claude/<thema>` → Prüfbefehl → Push.
- **Vor Arbeitsbeginn die offenen GitHub-Issues lesen** — beide Modi und Hermes
  (Label `hermes`). Dann Issue anlegen oder übernehmen und mit dem eigenen Label
  belegen. Ist das Thema belegt: nicht anfangen, im Issue nachfragen. Übergabe
  (Branch, Befund, Prüfstand) als Kommentar ins Issue; geschlossen wird nach dem
  Zusammenführen.
- **Moduswechsel:** Wer aufhört, hinterlässt seinen Stand gepusht und im Issue
  kommentiert.
  - Limit wieder frei: Der Master-Chat beginnt mit `git pull`, liest die Issues mit
    Label `cloud` und führt fertige `claude/*`-Branches zusammen.
  - Limit erschöpft: Die Cloud-Sitzung beginnt bei den offenen Issues, nicht beim
    Chatverlauf.
- Für Master-Chat und Hermes im selben Arbeitsbaum gilt zusätzlich der
  Kollisionsschutz oben.
- Leitplanke auf GitHub: Branch Protection für `main` (kein Force-Push, kein Löschen).
  Einrichtung durch Sebastian; Stand ungeprüft.

## Ablenkungen

Neue Ideen während einer laufenden Aufgabe werden als To-do notiert und nach der
Aufgabe aufgegriffen.
