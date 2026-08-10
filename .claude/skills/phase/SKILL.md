---
name: phase
description: Der 8-Phasen-Workflow für Feature-Arbeit in diesem Workspace (nach Thorstensen). Ohne Aufruf gilt keine Phasenlogik.
disable-model-invocation: true
argument-hint: "[Phasennummer, optional; 'auto' für Durchlauf ab Phase 4]"
---

# KI-Coding-Workflow — 8 Phasen

## Aufruf

| Aufruf | Wirkung |
|---|---|
| `/phase` | diese Übersicht anzeigen |
| `/phase 1` | Dialogblock starten (Phase 1–3) |
| `/phase 4` | Ausführungsblock, jede Änderung einzeln vorlegen |
| `/phase 4 auto` | Ausführungsblock als **ein Durchlauf** bis Phase 8 |

## Zwei Blöcke

- **Phase 1–3 (Dialog):** immer im Gespräch mit Sebastian. Ergebnis je Phase
  als Datei sichern: `brainstorm.md`, `alignment.md`, `plan.md`.
- **Phase 4–8 (Ausführung):** läuft als ein Durchlauf ab, sobald `plan.md`
  freigegeben ist. Genau ein Pflichtstopp: nach Phase 4, damit Sebastian die
  Software in Phase 5 selbst bedienen und beurteilen kann.

Der Durchlauf ist nur erlaubt, wenn alle drei Punkte zutreffen:

1. Das Projekt hat einen Prüfbefehl mit Exit-Code.
2. Die Regeln stehen in `.claude/settings.json`, nicht nur in `AGENTS.md`.
3. Es ist kein OT-/SPS-Code.

Trifft eines nicht zu, wird jede Änderung einzeln vorgelegt.

Zusätzlich anhalten und melden, statt weiterzumachen, wenn:

- der Prüfbefehl nach zwei Reparaturversuchen rot bleibt,
- von `plan.md` abgewichen werden müsste,
- über Aussehen oder Bedienbarkeit zu entscheiden wäre.

Der Permission-Modus wird mit `Shift+Tab` gesetzt und gilt für die ganze
Sitzung: `plan` für den Dialogblock, `acceptEdits` für den Ausführungsblock.

## Die Phasen

**Phase 1 — Brainstorm**
Ideen sortieren, als `brainstorm.md` sichern.

**Phase 1b — Pre-Alignment (grillAnAgent)**
`node .claude/skills/grillAnAgent/grillAnAgent.mjs brainstorm.md` ausführen.
Der Host lädt Haiku als Kritiker ein. Bei vollem Konsens einmal abnicken und
Phase 2 überspringen. Bei Uneinigkeit gehen nur die strittigen Punkte weiter.

**Phase 2 — Alignment** *(überspringbar bei Konsens aus Phase 1b)*
„Grill me". Nur noch ungeklärte Punkte klären, als `alignment.md` sichern.

**Phase 3 — Planung**
Vertical Slice (Ende-zu-Ende) wählen, Teststrategie festlegen, als `plan.md`
sichern. Vor Freigabe der Implementierung wird der Plan durch `/critic`
gegengeprüft, Befunde ausgewertet und der Plan angepasst. Erst nach Freigabe
durch Sebastian geht es weiter.

**Phase 4 — Implementierung**
Nur `plan.md` abarbeiten, kein Scope-Creep.

**Phase 5 — Testing** *(Pflichtphase)*
Sebastian bedient die Software selbst und gibt das UX-Urteil ab. Danach
Fremdprüfung durch `/critic`. Befunde werden vorgelegt, Sebastian entscheidet
je Punkt — nie automatisch beheben.

**Phase 6 — Recap**
Erklärung und Diagramm.

**Phase 7 — Refactor** *(Pflichtphase)*
Code vereinfachen und aufräumen. Dokumentation prüfen: READMEs (Root, Bereich,
Projekt) auf Aktualität — Stack, APIs, Architektur, Mermaid-Diagramme — bei
neuen APIs, Architektur-Entscheidungen oder Workflow-Änderungen aktualisieren.
Danach `/critic` als Gegenprobe: Hat das Aufräumen etwas kaputtgemacht?

**Phase 8 — Commit** *(Pflichtphase)*
Atomic Commits lokal. Markdown-Phasendateien löschen. Danach fragen:
„Soll gepusht werden?" — bei Ja führt Sebastian den Push selbst aus.

## Phasen-Disziplin

- **Pflichtphasen sind 5, 7 und 8.** Sie werden nie übersprungen. Phase 2 ist
  die einzige überspringbare Phase, und nur bei Konsens aus Phase 1b.
- **Phasenwechsel** werden über `AskUserQuestion` freigegeben, mit einer kurzen
  Einführung in die anstehende Phase. Ausnahme: der Durchlauf `/phase 4 auto`,
  der nur nach Phase 4 anhält.
- **Themen-Abweichungen** während einer Phase werden als To-do notiert und nach
  der Phase aufgegriffen. Der Fokus der laufenden Phase bleibt geschützt.
- **Am Phasenende** `/clear` vorschlagen und die nächste Phase benennen.
