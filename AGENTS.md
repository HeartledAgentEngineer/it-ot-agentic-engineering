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
- `git push` **nie autonom**: Der Agent stellt bei jedem anstehenden Push einen
  Bestätigungsschritt (Klick/Enter-Frage) an Sebastian — erst nach dessen OK wird
  gepusht. Immer vorschlagen, nie eigenmächtig pushen.

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
Google-Takeout-Daten. Die Sperre in `.gitignore` (Zeile 112) bleibt unverändert
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

## Kontext-Hygiene

Ab etwa 60 % Kontextnutzung oder am Phasenende: Zwischenstand in die
Phasendatei schreiben und `/clear` vorschlagen.

## Ablenkungen

Neue Ideen während einer laufenden Phase werden als To-do notiert und nach der
Phase aufgegriffen.
