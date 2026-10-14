# Workspace Agentic Engineering — Kernregeln

Diese Datei gilt werkzeugübergreifend (Claude Code, Cline, Cursor, Codex).
Sie ist die einzige Quelle der Kernregeln — Änderungen nur hier.

## Wo welche Regeln stehen

| Ebene | Datei | Wann sie gilt |
|---|---|---|
| Kern | `AGENTS.md` (diese Datei) | immer, in jedem Werkzeug |
| Claude-Code-Spezifisches | `CLAUDE.md` | immer, nur in Claude Code |
| Bereich | `01_IT-OT_Integration/CLAUDE.md`, `02_Softwareentwicklung_IT/CLAUDE.md` | sobald Dateien aus dem Bereich gelesen werden |
| Projekt | z. B. `02_Softwareentwicklung_IT/typeFREE/CLAUDE.md` | sobald Dateien des Projekts gelesen werden |

**Die Bereichs- und Projekt-`CLAUDE.md` werden von `sync-rules.ps1` aus der
jeweiligen `CLAUDE_EXTENDS.md` erzeugt.** Sie sind nicht von Hand zu
bearbeiten — Änderungen gehen beim nächsten Lauf verloren. Stattdessen die
zugehörige `CLAUDE_EXTENDS.md` ändern und das Skript erneut ausführen.

## Sprache

Antworten auf Deutsch. Fachbegriffe beim ersten Auftreten in einem Halbsatz
erklären.

## Sicherheit: Git

- Autonom erlaubt: lesen, lokal ändern, lokal committen.
- **Push: stehende Freigabe (Stand 15.09.2026, auf Sebastians ausdrücklichen
  Wunsch).** Ein Push nach **grünem Prüfbefehl** ist autonom erlaubt — Sebastian
  testet damit direkt am Handy, und ein Push ist jederzeit rücknehmbar
  (`git revert` / Zurücksetzen im Remote), er zerstört also nichts.
  Der Agent pusht **sofort nach** einer verifizierten Änderung, ohne jedes Mal
  nachzufragen.
- **Rückfrage bleibt Pflicht** (hier geht es um Datenverlust, nicht um
  Bequemlichkeit) bei:
  - **rotem/fehlendem Prüfbefehl** — es wird nicht gepusht, sondern erst repariert,
  - **Merge-/Rebase-Konflikten** oder divergierenden Historien,
  - **force-push / Überschreiben fremder Commits**,
  - Änderungen an **OT-/SPS-Code** oder an **persönlichen Datenarchiven**
    (dort gilt weiterhin alles manuell).
- Frühere Regel („nie autonom pushen") ist damit **abgelöst**; sie steht nur
  noch als Historie in diesem Absatz.

## Synchronisation: Pull vor Agentenarbeit

Bevor ein Agent an einem Repo arbeitet, holt er zu Beginn den aktuellen
gemeinsamen Stand: `git pull` (ggf. `--ff-only`). So startet jede Sitzung vom
selben Stand, egal ob zuvor per App wie `start-termux.sh` gepullt wurde, ein
anderer Agent/Computer gepusht hat oder das Repo nur lokal liegt. Der Pull wird
ausgeführt, bevor Dateien gelesen/geladen oder Commits gemacht werden. Der Agent
prüft dabei, ob der Pull sauber durchgeht; schlägt er fehl (z. B. lokale
Änderungen, Konflikt), wird er nicht übergangen, sondern Sebastian gefragt.

## Sicherheit: Persönliche Datenarchive

`Chats von GPT, GEMINI, Claude/` enthält vollständige Chat-Archive und
Google-Takeout-Daten. Die Sperre in `.gitignore` für `Chats von GPT, GEMINI, Claude/` bleibt unverändert
bestehen. Soll etwas daraus versioniert werden, wird die Datei außerhalb dieses
Ordners neu angelegt.

## Sicherheit: OT-Systeme

Änderungen an einer laufenden SPS führt Sebastian manuell aus. Der Agent
liefert Code-Blaupausen.

## Arbeitsweise

- Pro Antwort eine Änderung, dann Rückmeldung abwarten.
- Vor jeder Auswahlfrage zuerst dieses Briefing ausgeben:
  **Was** (1–2 Sätze) · **Warum** · **Was bleibt unverändert** ·
  **Risiko** (Keins / Gering / Mittel / Hoch)

## Tüfteln erlaubt, aber strukturiert

Pragmatisches Ausprobieren/Tüfteln ist ausdrücklich erlaubt — schnelle
Experimente, die Dinge zum Laufen bringen. **Aber:** ohne gelegentliche
Reflexion driftet es ins Chaos um. Deshalb:

- Nach jedem größeren Ad-hoc-Arbeitsblock (viel experimentiert/gefickt)
  kurz **innehalten**: Was wurde gebaut? Wo ist Code-Wildwuchs? Konsolidieren
  (Squash/Refactor)? Arbeitsweise reflektieren? Das dokumentiert sich in der
  Übergabe/Changelog.
- Kein dauerhaftes "Feuerwehr von Einsatz zu Einsatz": Wird ein Bereich
  unsauber (Code-Duplikat, fehlende Tests, inkonsistente Muster), wird er
  standardisiert statt weiter darauf zu schustern.
- Verifikation ("Fertig ist, was verifiziert ist") und "Doku folgt dem Code"
  gelten **immer** — auch bei schnellen Tüfteleien.

## Autonomiegrenze

Autonom: lesen, lokal ändern, lokal committen, Tests ausführen.
Rückfrage: alles, was den Rechner verlässt oder ein fremdes System erreicht
(Push, Deploy, SPS, Versand, Veröffentlichung).

## Dokumentation folgt dem Code

Jede Änderung an Code/Tools/Konfiguration wird auch in der zugehörigen
Dokumentation (README, docs, CHANGELOG/Änderungsprotokoll) nachgezogen und
gemeinsam committet — sonst hinkt die Doku dem Stand hinterher. Die Dokumentation
ist Teil der Bewerbungsmappe und muss CODEGENAU sein: sie darf nichts behaupten,
was der Code nicht tut.

- Bei jeder signifikanten Änderung: prüfen, welches README/docs/Protokoll
  betroffen ist → aktualisieren → mit einem gemeinsamen Commit („code + docs")
  committen.
- Doku nie einfach mitziehen "weil später": sie muss den NEUEN Stand beschreiben.
- Committen (autonom erlaubt); Push bleibt wie oben bei Sebastian.

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

Der frühere feste Phasen-Workflow (`/phase`, 8 Schritte) ist **abgelöst**:
gearbeitet wird kontinuierlich und hybrid (Codex für Coding-Blöcke, Hermes für
Qualität/Orchestrierung), ohne Phase-zu-Phase-Lauf. Die Kerninstrumente gelten
**weiterhin unverändert**:

1. Das Projekt hat einen Prüfbefehl mit Exit-Code („Fertig heißt verifiziert“).
2. „code + docs“: jede Änderung wird dokumentiert und gemeinsam committet.
3. Es ist kein OT-/SPS-Code (dort bleibt alles manuell bei Sebastian).

Hat ein Projekt **keinen** Prüfbefehl, wird jede Änderung einzeln vorgelegt.

## Rollen und Datenschutz im Agenten-Workflow

Vom Nutzer am 10.10.2026 festgelegt. Diese Rollen ersetzen starre Vorgaben,
nach denen Codex ausschließlich planen oder ausschließlich prüfen darf.

| Aktiver Master | Planer | Planprüfung | Technischer Ausführer | Technischer Prüfer | Alles Sensible |
|---|---|---|---|---|---|
| Claude Code | Claude Code | Hermes (DeepSeek v4.1 Flash) **und** Codex | Claude Code; bei sensiblen Daten Hermes | Codex | ausschließlich Hermes |
| Codex | Codex | Hermes mit DeepSeek v4.1 Flash | Hermes mit GPT-6 Luna | Hermes mit DeepSeek v4.1 Flash; Wechsel nur auf ausdrückliche Nutzeranweisung | ausschließlich Hermes |

**Regel ab 12.10.2026 (Sebastian):** Claude Code ist Master, **sobald es erreichbar
ist**. Dann gilt: erst planen, Hermes prüft den Plan, Codex prüft den Plan, danach
führt Claude Code aus. Hat die Arbeit mit sensiblen Daten zu tun, führt Hermes aus.
Ob etwas sensibel oder sicherheitskritisch ist, entscheidet der Master selbst und
schreibt die Einordnung in den Plan.

**Wenn Claude Code im Limit ist:** Codex ist Master (Zeile 2 der Tabelle), wie am
Wochenende 10.–12.10.2026. Dann prüft Hermes den Plan und die technischen
Ergebnisse mit **DeepSeek v4.1 Flash** (`deepseek/deepseek-v4.1-flash`).
Die technische Ausführung übernimmt nach Planfreigabe eine getrennte Hermes-Sitzung
mit GPT-6 Luna (`openai/gpt-6-luna`). Die Ergebnisprüfung übernimmt
eine eigene Hermes-Sitzung mit DeepSeek v4.1 Flash.
Hermes organisiert beide Rollen; Ausführer und Prüfer sind getrennte
Modellfamilien und frische Kontexte. Keine Selbstfreigabe durch den
Ausführerlauf. Sensible Arbeit bleibt ausschließlich bei Hermes.

Keine stille Wahl eines anderen Prüfmodells und kein automatischer
Masterwechsel: Der Nutzer bestimmt die Rollen und deren Wechsel.

**Ersatzprüfer (Sebastian, 12.10.2026):** Ist Codex gesperrt (Nutzungslimit),
prüft Hermes mit DeepSeek v4.1 Flash ersatzweise — es wird nicht gewartet, bis
Codex wieder frei ist. Der Wechsel ist nicht still: Er steht im Prüfprotokoll.
`tools/pruefkreis/pruefkreis.py` (personal_ai_agent) macht das automatisch.

**Alles Sensible bleibt IMMER bei Hermes.** Das gilt unabhängig davon, wer
Master, Planer, Ausführer oder Prüfer ist. Persönliche Texte, Lebenslaufdaten,
Chats, Kontakte, echte Kennungen, private Pfade, Zugangsschlüssel, Bildinhalte
sowie persönliche Beschreibungen und Vektoren verarbeitet ausschließlich
Hermes über den vom Nutzer freigegebenen Zugang mit Retention-Ausschluss.
Codex und Claude Code bearbeiten Code, Tests, technische Beschreibungen und
Architektur. Eine Master- oder Prüferrolle erteilt ihnen keine zusätzliche
Berechtigung für sensible Inhalte. Benötigte Datenprüfungen laufen bei Hermes;
die technischen Agenten erhalten nur bereinigte Anforderungen und Belege.

**Freigabe und Gegenprüfung:** Der Master erstellt den Plan. Vor der
technischen Umsetzung prüft der zugeordnete andere Prüfer den aktuellen Plan
kritisch und gibt den technischen Umfang frei. Erst danach führt der
technische Ausführer in kleinen, ausdrücklich zugeordneten Änderungen aus.
Anschließend prüft der andere Prüfer die Ergebnisse anhand eigener Belege.
Selbstprüfung ersetzt die Gegenprüfung nicht. Freigabe, tatsächliches
Prüfmodell, Planfassung und offene Blocker werden lokal dokumentiert.
Keine Antwort ist keine Freigabe. Veröffentlichung und sensible Arbeit
bleiben an die gesonderten Nutzergrenzen gebunden.

**Prüfprotokolle zeigen (Sebastian, 14.10.2026):** Sebastian ist „Human in the
Loop" als **Beobachter, nicht als Entscheider**. Nach jeder Prüfrunde — Plan- oder
Ergebnisprüfung, Codex oder Hermes — legt der Master das Protokoll
(`.hermes/pruefkreis/<thema>.md`) sofort als aufklappbare Datei in den Chat
(Claude Code: `SendUserFile`), dazu eine Zeile: Urteil und was der Master daraus
macht. Danach geht die Arbeit ohne Warten weiter; das Zeigen ist keine Rückfrage.
Grund: Codex-Prüfläufe sind flüchtig (`--ephemeral`) und erscheinen nicht in der
Codex-App, Hermes-Prüfsitzungen werden nach Abschluss geschlossen — ohne das
Protokoll im Chat sieht Sebastian nicht, was geprüft wurde.

## Lebenszyklus eigener Prüfchats

Vom Nutzer ausdrücklich festgelegt am 10.10.2026: Feedback bleibt im Master;
eigene Prüfchats werden nach Abschluss der zugehörigen Diskussion gelöscht.

- Der Master behält das bereinigte Feedback, die Entscheidung, offene beziehungsweise
  erledigte Befunde und notwendige Prüfbelege. Sensible Originalinhalte bleiben bei
  Hermes und werden nicht in einen Codex-/Claude-Master übernommen.
- Ein beendeter Modelllauf oder das erste Feedback allein ist KEIN Diskussionsabschluss.
  Die Diskussion ist abgeschlossen, wenn alle Befunde entschieden und dokumentiert
  sind oder der Nutzer sie ausdrücklich für abgeschlossen erklärt.
- Erst danach entfernt der Master die Anpinnung und löscht genau die zugehörigen,
  von diesem Workflow angelegten Prüfersitzungen anhand ihrer registrierten exakten
  Sitzungskennungen. Der Nutzer hat diese spätere Bereinigung bereits freigegeben;
  keine erneute Löschrückfrage bei erfüllten Voraussetzungen.
- Master-Chats, Ausführer-Chats, fremde Sitzungen, persönliche Archive und Originaldaten
  sind von dieser Regel AUSGESCHLOSSEN. Keine pauschale Bereinigung, kein Löschen nach
  Titelmustern, kein Prune und kein Reparieren oder Neuaufbauen der Sitzungsdatenbank.
- Prüfchats sind während der offenen Diskussion sichtbar und bei Bedarf angepinnt.
  Nach deren Abschluss dürfen sie trotz vorheriger Anpinnung entfernt werden.
- Vor dem Löschen: Feedback im Master gesichert, Diskussion geschlossen und Besitz/
  Rolle der exakten Sitzungskennung geprüft. Ist etwas unklar, Sitzung behalten und
  den Blocker nennen. Nach dem Löschen nur den technischen Bereinigungsnachweis
  festhalten; keine vollständigen Prüfchat-Exporte als Ersatzkopie anlegen.

## Kontext-Hygiene

Ab etwa 60 % Kontextnutzung oder am Phasenende: Zwischenstand in die
Phasendatei schreiben und `/clear` vorschlagen.

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
   System kommt in ein **Manifest** (Quelle → Ziel, Zeit, Kennung), damit sie
   zurückgenommen werden kann. „Wie mache ich das rückgängig?" wird **vor** der
   Operation beantwortet, nicht danach.
6. **Idempotent bauen.** Jedes Werkzeug muss mehrfach laufen dürfen, ohne Schaden
   (vorhandenes Ziel = überspringen, nie doppelt anlegen).
7. **Kostengrenze.** Billigste Wege zuerst (Vorschaubilder statt Originale,
   Stapel statt Einzelaufrufe). Teure Wege (Vision über alles) werden vorher an
   einer Stichprobe gemessen, nicht ins Blaue gefahren.
8. **Wiederaufnahme sichern.** Bei Dauerläufen wird ein Fortsetzungspunkt
   festgehalten (Plan + Journal), damit ein Neustart — neue Sitzung, Cron-Aufruf,
   anderer Rechner — dort weitermacht statt von vorn.

### Mehrere Agenten im selben Arbeitsbaum (Kollisionsschutz)

Es kann vorkommen, dass ein zweiter Agent (andere Sitzung, Cron, Handy) im
**selben** Arbeitsbaum arbeitet. Am 27.09.2026 passiert: fremde `git add -A`-
Arbeit hat gestagte Dateien eines anderen Agenten mitgenommen (Commit `908cf39`
enthält fremden Code, obwohl er „fix(live_zahlen)" heißt). Dann gilt:

- **Nie `git add -A`, nie `git commit -a`.** Stattdessen
  **`git commit --only <Pfad> <Pfad>`** mit ausdrücklich genannten Dateien —
  damit bleiben fremde, halbfertige Änderungen draußen.
- Bei `cannot lock ref 'HEAD'` oder abgelehntem Push: **`git pull --rebase`**,
  dann erneut committen/pushen. **Niemals** `--force` (fremde Commits bleiben).
- Vor jedem Commit `git log --oneline -3` lesen: hat jemand anders gerade
  gearbeitet, erst einordnen, dann den eigenen Schritt machen.
- Nach dem Push `git rev-list --left-right --count origin/main...HEAD` prüfen
  (`0 0` = lokal und remote gleich).

### Zwei Claude-Modi und Hermes (GitHub-Issues als gemeinsame Tafel)

Festgelegt am 30.09.2026. Anlass: Eine Cloud-Sitzung und der PC-Agent haben am selben
Abend unabhängig voneinander denselben Fehler behoben — doppelte Kosten.

| | Master-Chat (Claude Code am PC) | Cloud-Sitzung (Claude Code bei Anthropic) |
|---|---|---|
| Wann | 5-Stunden-Limit des Abos frei | Limit erschöpft, PC aus oder unterwegs |
| Sieht | PC, Hermes, Handy per Kabel | nur GitHub (`.hermes/` ist per `.gitignore` gesperrt) |
| Pusht | `main`, nach grünem Prüfbefehl | nur `claude/<thema>`, nie `main` |
| Absprache | GitHub-Issues; Hermes über eigene Sitzungen | GitHub-Issues |
| Issue-Label | `claude-pc` | `cloud` |

**Agentenbus abgelöst (Sebastian, 14.10.2026):** Der Agentenbus
(`personal_ai_agent/tools/agentbus/`) wird nicht mehr benutzt — keine Nachrichten
oder Aufträge mehr darüber. Hermes-Arbeit läuft über eigene Hermes-Sitzungen, die
der Master startet und nach Abschluss schließt (`tools/pruefkreis/pruefkreis.py`).
Die Wache `HermesAgentenbusWache` ist abgeschaltet, die Bus-Haken in
`.claude/settings.json` sind entfernt. Bus-Dateien und Protokoll bleiben als Historie.

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

Neue Ideen während einer laufenden Phase werden als To-do notiert und nach der
Phase aufgegriffen.
