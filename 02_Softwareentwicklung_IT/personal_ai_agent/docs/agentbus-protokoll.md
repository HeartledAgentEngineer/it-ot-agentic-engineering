# Agentenbus — Protokoll für die Zusammenarbeit mehrerer Agenten

Zweck: **Hermes (Daten/Denken) und Claude Code (Code) dürfen nie dieselbe
Aufgabe doppelt anfassen.** Beide Seiten wissen automatisch voneinander, weil
der Bus in den Dateien steht, die jeder Agent beim Start liest.

## Werkzeug

```
python tools/agentbus/agentbus.py <befehl>
```

Ablage: `.hermes/bus/` (lokal, **nicht** im Git — Koordination, keine Daten).
Ein Kanal für alle: `messages.jsonl` (nur anhängend) + `claims/step-<STEP>.json`
(atomar angelegt, O_CREAT|O_EXCL → zwei Agenten können denselben Schritt
**unmöglich** gleichzeitig beanspruchen).

| Befehl | Zweck |
|---|---|
| `init` | Bus anlegen (idempotent) |
| `status` | offene Ansprüche + letzte 8 Nachrichten |
| `read --for <agent>` | ungelesene Nachrichten für mich (markiert sie als gelesen) |
| `read --for <agent> --all` | alle Nachrichten (auch gelesene) |
| `send --from X --to Y\|alle --type T [--step S] [--paths a,b] --text "..."` | Nachricht legen |
| `claim --agent X --step S [--paths a,b] [--text "..."]` | Schritt beanspruchen (schlägt fehl, wenn schon beansprucht) |
| `release --agent X --step S` | freigeben (nur der Inhaber) |
| `verify --agent X --step S --result gruen\|rot --text "..."` | Prüfergebnis festhalten (der **andere** Agent) |

Typen: `task` · `tip` · `frage` · `erledigt` · `blockiert` · `pruefung`

## Rollen (verbindlich)

| Rolle | Wer | Regel |
|---|---|---|
| **Planer** | Hermes (hat den Gesamtstand + Daten) | schreibt `task`-Nachrichten mit Schritt, Pfaden, Prüfkriterium |
| **Arbeiter Code** | Claude Code | nur Code/Tests/Doku, **keine persönlichen Daten** |
| **Arbeiter Daten** | Hermes + OpenRouter (ZDR) | Chats, Fotos, Kontakte, Gesichter |
| **Prüfer** | **immer der andere** als der Arbeiter | `verify` — Selbstprüfung ist gesperrt |

## Ablauf für jeden Schritt

1. **`status` + `read --for <mich>`** — was liegt an? Wer arbeitet was?
2. **`claim`** mit Schritt-ID **und** den Dateipfaden, die angefasst werden.
   Schlägt der Anspruch fehl: **nicht anfassen**, dem anderen per `frage`
   schreiben.
3. Arbeiten — nur in den beanspruchten Pfaden.
4. `send --type erledigt` mit Beleg (Prüfbefehl + Ergebnis, Zahlen).
5. Der **andere** prüft (`verify --result gruen|rot`) oder schreibt `blockiert`
   mit Grund.
6. Erst nach `gruen` committen/pushen — Commit nur mit `--only <Pfade>`.

## Was auf den Bus gehört (und was nicht)

**Ja:** Schritt-IDs, Dateipfade, kurze Sachnotizen, Prüfergebnisse, Blocker,
Fachfragen zur Abstimmung.

**Nein:** Chat-Inhalte, Namen, Nummern, Bilddaten, Tokens/Schlüssel, private
Pfade außerhalb des Repos, lange Logs. Der Bus ist Koordination, kein Archiv.

## Warum beide automatisch davon wissen

| Agent | Wie er es erfährt |
|---|---|
| **Claude Code** | `.claude/settings.json` → `SessionStart`-Hook ruft `agentbus status` auf; die Ausgabe landet in seinem Kontext. Zusätzlich steht die Regel in `CLAUDE.md`. |
| **Hermes** | Die Regel steht in `AGENTS.md`/`CLAUDE.md` und im Hermes-Gedächtnis: vor Daten-/Foto-/Chat-Arbeit erst `status` + `read`, dann `claim`. |

## Dauer-Kanal (beide Richtungen, ohne Sitzungsstart)

| Richtung | Wie | Takt |
|---|---|---|
| **Claude → Hermes** | `tools/agentbus/wache.py` läuft als Windows-Auftrag. **Standard seit 29.09.2026: Modus `melden`** – nur eine Windows-Benachrichtigung „Agentenbus: N Nachricht(en) für Hermes“, **kein Modellaufruf, 0 Tokens**; die Nachrichten bleiben ungelesen, Hermes liest sie, wenn Sebastian ihn anspricht. Modus `zustellen` (`--zustellen` / `WACHE_MODUS=zustellen`) schreibt wie früher per `POST /api/sessions/<id>/chat` in die laufende Sitzung – **teuer**: jede Zustellung schickt den ganzen Sitzungsverlauf mit (29.09.2026 gemessen: bis ~800k Tokens je Aufruf) | jede Minute; `melden`: 0 Tokens · `zustellen`: 1 Modellaufruf mit vollem Verlauf je Zustellung |
| **Hermes → Claude** | Hooks in `.claude/settings.json`: `SessionStart`, **`UserPromptSubmit`** (bei jedem Prompt) und **`Stop`** (nach jedem Durchlauf) zeigen die neuen Bus-Nachrichten | sofort, bei jedem Prompt/Zug |

Sitzungs-ID der Wache: `HERMES_SITZUNG` oder `.hermes/bus/wache.json`
(`{"sitzung": "..."}`), Standard ist Sebastians Desktop-Sitzung.

## Grenzen (ehrlich)

- Der Bus ist **lokal**. Läuft Hermes auf dem Handy und Claude am PC, sehen sie
  sich **nicht** — dann ist die Abstimmung über Git (Commit-Nachrichten) oder
  Telegram zu führen.
- Die Wache liefert nur **zu**, wenn die Hermes-Sitzung lebt; ist der Server aus,
  bleibt die Nachricht ungelesen liegen und wird beim nächsten Lauf zugestellt.
- Ein Anspruch ist eine **Absprache**, keine technische Sperre für Menschen:
  Dateien bleiben für jeden schreibbar. Wer sich nicht an den Bus hält, kann
  weiterhin kollidieren — deshalb ist `git commit --only` Pflicht.