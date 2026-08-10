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
- `git push` bleibt bei Sebastian. Der Agent schlägt einen Push vor und wartet
  auf die Ausführung durch Sebastian.

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

## Autonomiegrenze

Autonom: lesen, lokal ändern, lokal committen, Tests ausführen.
Rückfrage: alles, was den Rechner verlässt oder ein fremdes System erreicht
(Push, Deploy, SPS, Versand, Veröffentlichung).

## Fertig ist, was verifiziert ist

Ein Schritt gilt als fertig, wenn der Prüfbefehl des Projekts Exit-Code 0
liefert. Ohne Prüfbefehl: benennen, welcher fehlt.

## Automatischer Durchlauf

Feature-Arbeit läuft über den Workflow in `.claude/skills/phase/SKILL.md`,
aufgerufen mit `/phase`. Ein Durchlauf ohne Zwischenfreigaben ist nur erlaubt,
wenn alle drei Punkte zutreffen:

1. Das Projekt hat einen Prüfbefehl mit Exit-Code.
2. Die Regeln stehen in `.claude/settings.json`, nicht nur in dieser Datei.
3. Es ist kein OT-/SPS-Code.

Trifft eines nicht zu, wird jede Änderung einzeln vorgelegt.

## Kontext-Hygiene

Ab etwa 60 % Kontextnutzung oder am Phasenende: Zwischenstand in die
Phasendatei schreiben und `/clear` vorschlagen.

## Ablenkungen

Neue Ideen während einer laufenden Phase werden als To-do notiert und nach der
Phase aufgegriffen.
