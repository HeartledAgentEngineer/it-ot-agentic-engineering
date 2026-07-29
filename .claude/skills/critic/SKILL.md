---
name: critic
description: Einzusetzen, wenn Sebastian "critic" oder "/critic" sagt; ebenso in Phase 5 (Testing) und Phase 7 (Refactor), bevor ein Slice committet wird, sowie bei sicherheitsnahem oder nebenläufigem Code. Holt eine unabhängige Zweitmeinung von einem fremden KI-Modell. Einziger gültiger Aufruf ist `node .claude/skills/critic/pruefe.mjs` — niemals `gemini`, niemals `agy exec`. Nicht während Phase 4 einsetzen.
---

# Critic — Fremdprüfung durch ein zweites Modell

## Überblick

Generator-Critic-Muster über zwei Modellfamilien. Ich baue (Generator), ein fremdes Modell prüft (Critic). Zweck: Modelle haben blinde Flecken in ihrem eigenen Code. Ein Modell einer anderen Familie hat andere.

**Kernprinzip:** Der Critic liefert Befunde, keine Urteile. Sebastian entscheidet, was zählt. Ich ändere aufgrund einer Fremdkritik **nie** eigenmächtig Code.

**Zweites Kernprinzip:** Das fremde Modell darf nichts anfassen. Der zu prüfende Code wird ihm im Prompt übergeben — es liest keine Dateien selbst und führt nichts aus.

## Der Aufruf

```bash
node .claude/skills/critic/pruefe.mjs --diff          # uncommittete Änderungen, Gemini-API
node .claude/skills/critic/pruefe.mjs datei.py        # einzelne Dateien
node .claude/skills/critic/pruefe.mjs --diff --agy    # dasselbe über Antigravity
```

> [!CAUTION]
> **Zwei Aufrufe, die es nicht gibt — beide haben schon Zeit gekostet:**
> - `gemini …` — die Gemini CLI ist seit 18.06.2026 für Privatnutzer abgeschaltet (`IneligibleTierError`). Am 30.07.2026 hielt jemand deshalb den Skill für kaputt.
> - `agy exec …` — dieses Unterkommando existiert nicht. Antigravity nutzt `-p` für Einzelaufträge. Stand am 30.07.2026 fälschlich in dieser Datei.
>
> **Immer `pruefe.mjs` aufrufen, nie ein CLI-Werkzeug direkt.**

### Die zwei Motoren

| | Aufruf | Kontingent | Besonderheit |
|---|---|---|---|
| **Gemini-API** (Standard) | ohne Flag | 1.500/Tag | braucht `GEMINI_API_KEY`, kein Umfangslimit |
| **Antigravity** | `--agy` | 20/Tag | kein Schlüssel nötig, max. 30.000 Zeichen |

Standard ist die API — 75-mal mehr Kontingent. `--agy` als Zweitmeinung, wenn ein Befund strittig ist, oder wenn der API-Schlüssel fehlt.

**Sonderfall Codex** (schärfer bei Nebenläufigkeit, eigenes Monatskontingent):

```bash
export PATH="$PATH:/c/Users/sebas/AppData/Roaming/npm"
codex exec -m gpt-5.6-terra --sandbox read-only -o <AUSGABEDATEI> "<PROMPT>"
```

> [!CAUTION]
> **Codex Free hat ein Monatskontingent, kein Stundenkontingent.** Am 29.07.2026 nach zwei Läufen erschöpft, Sperre bis 27.08.2026. Nur auf ausdrücklichen Wunsch einsetzen und vorher warnen. Eigenheiten: Ausgabe kommt **doppelt** mit vorangestelltem Dateiecho, deshalb `-o <datei>` nutzen; `codex exec review --uncommitted` verträgt **keinen** eigenen Prompt und kennt **kein** `--sandbox`.

### Datenschutz — vor jedem Lauf mitdenken

Im kostenlosen Tier nutzt Google übermittelte Inhalte zur Produktverbesserung. Für private Übungsprojekte unkritisch.

**Nicht** über den Critic schicken: SPS-/OT-Code aus `01_IT-OT_Integration`, Kundendaten, Zugangsdaten, alles unter NDA. So auch in `CLAUDE.md` Zeile 103 festgehalten. Im Zweifel Sebastian fragen, nicht selbst entscheiden.

## Wann einsetzen

- **Phase 3 (Planung) — höchster Wert.** `plan.md` gegen `alignment.md` prüfen lassen: fehlende Voraussetzungen, unbelegte Annahmen, Widersprüche, Tests für Features aus einem anderen Durchgang. Ein gefundener Planungsmangel spart einen ganzen Durchgang; ein gefundener Codefehler nur einen Fix.
- **Phase 5 (Testing)** — nachdem der Slice läuft, bevor UX-Feedback gegeben wird
- **Phase 7 (Refactor)** — als Gegenprobe, ob das Aufräumen etwas kaputt gemacht hat
- Bei allem mit Nebenläufigkeit, Fremdeingaben, Dateisystem oder Netzwerk

## Wann NICHT

- **Nie in Phase 4.** Kritik während des Bauens zerfasert die Implementierung.
- **Nicht in Phase 2.** Dort ist Sebastian die prüfende Instanz — was er *will*, kann kein Modell beurteilen. Dafür ist `grill-me` da.
- Nicht bei **Prosa**-Markdown (README, Doku) oder reinen Umbenennungen. **Wohl aber** bei `plan.md` und `alignment.md` — ein Plan ist Spezifikation, kein Text.
- Nicht als Ersatz für Tests. Der Critic findet andere Dinge als ein Testlauf, nicht dieselben.

## Ablauf

### Schritt 1 · Umfang festlegen

Nur den aktuellen Slice prüfen, nicht das Repo. Bei Unklarheit fragen, welche Dateien gemeint sind — nie „alles" schicken.

> [!IMPORTANT]
> **Großer Umfang kostet Befunde.** Am 29.07.2026 gemessen: Bei 27k Tokens meldete das Modell einen HOCH-Befund (`hotkey['key']` bei `None`). Beim Wiederholungslauf mit 62k Tokens — gleicher Code, gleiches Modell — **fehlte genau dieser Befund**.
>
> Lieber drei gezielte Läufe über einzelne Dateien als einer über alles. Kontingent ist reichlich; Gründlichkeit ist der Engpass.
>
> **Ein sauberer Lauf ist kein Beweis für fehlerfreien Code.** Ein leeres Protokoll nie als Freigabe darstellen.

### Schritt 2 · Aufruf

`pruefe.mjs` bringt Prompt und Format mit — nichts selbst formulieren. Der Schlüssel wird per Header übertragen, nie über die URL; fehlt er in der Session, holt das Skript ihn aus der Windows-Benutzerumgebung.

**Fehlerausgabe niemals nach `/dev/null` schicken.** Sonst ist ein Kontingent- oder Auth-Fehler nicht von einem leeren Ergebnis zu unterscheiden — daran ist der Aufbau am 29.07.2026 dreimal hintereinander gescheitert.

### Schritt 3 · Aufbereiten, nicht durchreichen

1. **Schweregrade nachprüfen.** Die Modelle stufen unzuverlässig und uneinheitlich ein — dieselbe SQL-Injection kam je nach Modell als KRITISCH oder HOCH zurück, ein sicherer Absturz als MITTEL. Falsch Eingestuftes korrigieren und die Korrektur kenntlich machen.
2. **Falsche Befunde streichen** und benennen: *„Punkt 3 hat der Critic falsch gesehen, weil …"*
3. **Nach Schweregrad sortieren**, durchnummerieren.

### Schritt 4 · Sebastian entscheidet

| Sebastian schreibt | Ich mache |
|---|---|
| `1,3,5` | Nur diese Punkte werden behoben |
| `alle` | Alle Punkte werden behoben |
| `keins` | Nichts wird geändert, Protokoll verworfen |
| `später` + Nummern | Wandern in **Offene Punkte** des Slice |

Erst nach dieser Entscheidung wird Code angefasst.

## Rote Flaggen

| Ausrede | Realität |
|---|---|
| „Das andere Modell wird schon recht haben" | Andere Familie heißt anderer blinder Fleck, nicht Allwissenheit. Jeden Befund selbst prüfen. |
| „Ich behebe das schnell, ist ja offensichtlich" | Auch offensichtliche Befunde gehen durch Schritt 4. |
| „Ich schicke einfach das ganze Repo" | Verbrennt Kontingent und ertränkt echte Befunde. |
| „Kritik kam zurück, also war der Code schlecht" | Fremdmodelle finden fast immer *etwas*. Menge ≠ Qualitätsurteil. |
| „Kontingent leer, ich nehme still den anderen Motor" | Motorwechsel ist eine Entscheidung. Melden, nicht schlucken. |
| „Ich lasse Phase 5 weg, der Critic hat ja geprüft" | Der Critic ersetzt keine Tests. Beides. |
| „Der Aufruf klappt nicht, der Skill ist kaputt" | Erst prüfen, ob überhaupt `pruefe.mjs` aufgerufen wurde. Zweimal war das die Ursache. |

## Verhältnis zu anderen Skills

`grill-me` ist der Grill **vor** dem Bauen (Phase 2, Sebastian grillt die Idee). `critic` ist der Grill **nach** dem Bauen (Phase 5/7, ein fremdes Modell grillt den Code). Sie ersetzen einander nicht.

Vorrang vor `superpowers:requesting-code-review` in diesem Workspace.

## Dateien

- `pruefe.mjs` — der einzige Einstiegspunkt. Enthält Prompt, Formatvorgabe, beide Motoren und die Fehlerbehandlung.
- `protokoll-schema.json` — JSON-Schema für Codex' `--output-schema`
