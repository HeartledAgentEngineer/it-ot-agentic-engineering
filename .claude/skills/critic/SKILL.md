---
name: critic
description: Einzusetzen, wenn Sebastian "critic" oder "/critic" sagt; ebenso in Phase 5 (Testing) und Phase 7 (Refactor), bevor ein Slice committet wird, sowie bei sicherheitsnahem oder nebenläufigem Code. Holt eine unabhängige Zweitmeinung von einem fremden KI-Modell über die Gemini-Developer-API mittels `pruefe.mjs` — NICHT über die Gemini CLI, die für Privatnutzer abgeschaltet ist. Bereitet die Befunde als Prüfprotokoll auf. Nicht während Phase 4 einsetzen.
---

# Critic — Fremdprüfung durch ein zweites Modell

## Überblick

Generator-Critic-Muster über zwei Modellfamilien. Ich baue (Generator), ein fremdes Modell prüft (Critic). Zweck: Modelle haben blinde Flecken in ihrem eigenen Code. Ein Modell einer anderen Familie hat andere.

**Kernprinzip:** Der Critic liefert Befunde, keine Urteile. Sebastian entscheidet, was zählt. Ich ändere aufgrund einer Fremdkritik **nie** eigenmächtig Code.

**Zweites Kernprinzip:** Das fremde Modell darf nichts anfassen. Es liest und schreibt ein Protokoll. Kein Schreibzugriff, keine Befehlsausführung, kein Commit.

## Wann einsetzen

- **Phase 5 (Testing)** — nachdem der Slice läuft, bevor UX-Feedback gegeben wird
- **Phase 7 (Refactor)** — als Gegenprobe, ob das Aufräumen etwas kaputt gemacht hat
- Bei allem, was mit Nebenläufigkeit, Eingabedaten von außen, Dateisystem oder Netzwerk zu tun hat

## Wann NICHT

- **Nie in Phase 4.** Kritik während des Bauens zerfasert die Implementierung.
- Nicht bei Markdown, Konfiguration oder reinen Umbenennungen — verbrennt Kontingent ohne Ertrag.
- Nicht als Ersatz für Tests. Der Critic findet andere Dinge als ein Testlauf, nicht dieselben.

## Modellkette

> [!CAUTION]
> **Niemals `gemini` oder `gemini-cli` aufrufen.** Google hat die CLI am 18.06.2026 für Privatnutzer abgeschaltet — der Aufruf endet in `IneligibleTierError: This client is no longer supported`. Wer nur „Gemini" liest und zur CLI greift, hält den Skill fälschlich für kaputt. Genau das ist am 30.07.2026 passiert.
>
> **Der einzige gültige Aufruf ist `node .claude/skills/critic/pruefe.mjs`.**

**Primär: Gemini über die Developer-API.** Kein CLI-Werkzeug beteiligt.

```bash
node .claude/skills/critic/pruefe.mjs --diff
node .claude/skills/critic/pruefe.mjs pfad/zur/datei.py
node .claude/skills/critic/pruefe.mjs --diff --modell gemini-3-flash-preview
```

Standardmodell ist `gemini-flash-latest` — ein Alias, der immer auf die neueste Flash-Version zeigt. Kontingent: 1.500 Anfragen/Tag, ein Lauf kostet je nach Umfang 3.000–30.000 Tokens.

> [!NOTE]
> **Warum nicht die Gemini CLI?** Google hat sie am 18.06.2026 für Privatnutzer abgeschaltet (Umstieg auf Antigravity). Die API-Ebene darunter blieb kostenlos. Die Antigravity CLI wäre die Alternative, hat aber nur 20 Agenten-Anfragen/Tag statt 1.500. `gemini-3.6-flash` existiert in der Developer-API **nicht** — nur in der App und in Antigravity.

**Sonderfall: Codex** — schärfer bei Nebenläufigkeit, nur für heikle Slices.

```bash
export PATH="$PATH:/c/Users/sebas/AppData/Roaming/npm"
codex exec -m gpt-5.6-terra --sandbox read-only -o <AUSGABEDATEI> "<PROMPT>"
```

> [!CAUTION]
> **Codex Free hat ein Monatskontingent, kein Stundenkontingent.** Es war am 29.07.2026 nach zwei Läufen erschöpft — Sperre bis 27.08.2026. Codex nur einsetzen, wenn Sebastian es ausdrücklich verlangt, und vorher darauf hinweisen, dass der Lauf das Monatsbudget verbrauchen kann. Der PATH-Export ist dabei Pflicht.

### Datenschutz — vor jedem Lauf mitdenken

Im **kostenlosen** Gemini-Tier nutzt Google die übermittelten Inhalte zur Produktverbesserung. Für private Übungsprojekte unkritisch.

**Nicht** über den Critic schicken: SPS-/OT-Code aus `01_IT-OT_Integration`, Kundendaten, Zugangsdaten, alles unter NDA. Im Zweifel Sebastian fragen, nicht selbst entscheiden.

### Wenn das Primärmodell ausfällt

Erkennungsmerkmale: Exit-Code ≠ 0, `usage limit`, `quota`, `Please set an Auth method`.

Dann **nicht still umschwenken**, sondern melden: welches Modell ausgefallen ist, warum, und was der Ersatz kostet. Sebastian entscheidet, ob der Ersatzlauf stattfindet.

## Ablauf

### Schritt 1 · Umfang festlegen

Nur den aktuellen Slice prüfen lassen, nicht das Repo. Bei Unklarheit fragen, welche Dateien gemeint sind — nie „alles" schicken.

```bash
git diff --stat
```

> [!IMPORTANT]
> **Großer Umfang kostet Befunde.** Am 29.07.2026 gemessen: Bei 27k Tokens meldete Flash einen HOCH-Befund (`hotkey['key']` bei `None`). Beim Wiederholungslauf mit 62k Tokens — gleicher Code, gleiches Modell — **fehlte genau dieser Befund**.
>
> Daraus folgt: Lieber drei gezielte Läufe über einzelne Dateien als ein Lauf über alles. Das Kontingent von 1.500 Anfragen/Tag ist reichlich; Gründlichkeit ist der Engpass, nicht die Anzahl.
>
> Zweite Folge: **Ein sauberer Lauf ist kein Beweis für fehlerfreien Code.** Ein leeres Protokoll nie als Freigabe darstellen.

### Schritt 2 · Aufruf

`pruefe.mjs` bringt Prompt und Format mit — nichts selbst formulieren. Das Skript liest den Key aus `GEMINI_API_KEY`, per Header, nie über die URL. Ist er in der Session nicht sichtbar, holt es ihn über PowerShell aus der Windows-Benutzerumgebung.

**Bekannte Eigenheiten:**
- Fehlerausgabe **niemals** nach `/dev/null` schicken. Sonst ist ein Kontingent- oder Auth-Fehler nicht von einem leeren Ergebnis zu unterscheiden — genau daran ist der Aufbau am 29.07.2026 dreimal hintereinander gescheitert.
- Der Key darf nie im Chat, in einer Projektdatei oder in einer URL landen.
- Codex-Eigenheiten, falls doch verwendet: Ergebnis kommt **doppelt** und mit vorangestelltem Dateiecho — deshalb `-o <datei>` nutzen und die Datei lesen. `codex exec review --uncommitted` verträgt **keinen** eigenen Prompt und kennt **kein** `--sandbox`.

### Schritt 3 · Aufbereiten, nicht durchreichen

Rohausgabe nie ungefiltert in den Chat. Stattdessen:

1. **Schweregrade nachprüfen.** Fremdmodelle stufen unzuverlässig ein — ein sicherer Absturz kam im Test als `MITTEL` zurück. Falsch eingestufte Punkte korrigieren und die Korrektur kenntlich machen.
2. **Falsche Befunde streichen** und das benennen: *„Punkt 3 hat der Critic falsch gesehen, weil …"*
3. **Nach Schweregrad sortieren**, durchnummerieren.

### Schritt 4 · Sebastian entscheidet

Protokoll vorlegen, dann pro Punkt eine Entscheidung einholen:

| Sebastian schreibt | Ich mache |
|---|---|
| `1,3,5` | Nur diese Punkte werden behoben |
| `alle` | Alle Punkte werden behoben |
| `keins` | Nichts wird geändert, Protokoll wird verworfen |
| `später` + Nummern | Wandern in **Offene Punkte** des Slice |

Erst nach dieser Entscheidung wird Code angefasst.

## Rote Flaggen

| Ausrede | Realität |
|---|---|
| „Das andere Modell wird schon recht haben" | Andere Familie heißt anderer blinder Fleck, nicht Allwissenheit. Jeden Befund selbst prüfen. |
| „Ich behebe das schnell, ist ja offensichtlich" | Auch offensichtliche Befunde gehen durch Schritt 4. |
| „Ich schicke einfach das ganze Repo" | Verbrennt Kontingent und ertränkt echte Befunde in Rauschen. |
| „Kritik kam zurück, also war der Code schlecht" | Fremdmodelle finden fast immer *etwas*. Menge ≠ Qualitätsurteil. |
| „Kontingent leer, ich nehme still das andere Modell" | Modellwechsel ist eine Entscheidung. Melden, nicht schlucken. |
| „Ich lasse Phase 5 weg, der Critic hat ja geprüft" | Der Critic ersetzt keine Tests. Beides. |

## Verhältnis zu anderen Skills

`grill-me` ist der Grill **vor** dem Bauen (Phase 2, Sebastian grillt die Idee). `critic` ist der Grill **nach** dem Bauen (Phase 5/7, ein fremdes Modell grillt den Code). Sie ersetzen einander nicht.

Vorrang vor `superpowers:requesting-code-review` in diesem Workspace.

## Dateien

- `pruefe.mjs` — der Prüfaufruf. Enthält Prompt, Formatvorgabe und Fehlerbehandlung.
- `protokoll-schema.json` — JSON-Schema für Codex' `--output-schema`, erzwingt die Protokollform
