# Prüfkreis: automatische Gegenprüfung

Der Master (Claude Code oder Codex) legt einen Plan oder ein Ergebnis als Datei
ab und ruft `pruefen` auf. Das Werkzeug startet einen **frischen** Prüflauf,
liest das Urteil, hängt die Runde an das Diskussionsprotokoll an und gibt sie
für den Master-Chat aus. Der Mensch liest das Protokoll mit, statt Nachrichten
zwischen den Agenten hin- und herzutragen.

Plan: `.hermes/plans/2026-10-12_hermes-auftraege-statt-bus.md` (gitignored).
Rollen: Abschnitt „Rollen und Datenschutz im Agenten-Workflow“ in `AGENTS.md`.

## Aufruf

```bash
python tools/pruefkreis/pruefkreis.py pruefen --vorlage <datei> --thema <kennung> \
    [--pruefer codex|hermes] [--master claude|codex|hermes] [--sensibel] [--gruendlich] [--zeitgrenze 900] [--planfassung N]
```

| Exit | Bedeutung |
|---|---|
| 0 | `URTEIL: FREI` |
| 1 | `URTEIL: EINWAND` |
| 2 | Fehler: Lauf gescheitert, Zeitgrenze, keine Urteilszeile oder unzulässiger Aufruf |

## Regeln im Code

- **`--sensibel`**: Der Prüfer ist immer Hermes. `--pruefer codex --sensibel`
  wird mit Exit 2 abgelehnt, ohne dass ein Prüfer startet. In die Ausgabe und
  ins Protokoll kommen dann nur Urteil, Hermes-Sitzungskennung und Kosten. Die
  Begründung bleibt in der Hermes-Sitzung.
- **Urteilszeile**: Nur `URTEIL: FREI` oder `URTEIL: EINWAND` als **letzte**
  nichtleere Zeile zählt. Fehlt sie, endet der Prüfer mit Exit ≠ 0 oder läuft
  er in die Zeitgrenze, ist der Status `fehler`, nie `frei`.
  Bei einem Fehler steht die letzte `ERROR`-Zeile des Prüfers im Grund
  (z. B. das erreichte Codex-Nutzungslimit), bei `--sensibel` nicht.
- **Codex gesperrt → Hermes prüft** (Sebastian, 12.10.2026): Endet Codex mit
  einer Limit-Meldung (`usage limit`, `rate limit`, `quota`, `429` in der
  Fehlerausgabe), startet sofort Hermes mit demselben Auftrag. Das Protokoll
  vermerkt `Ersatzpruefer: Hermes statt Codex - Codex gesperrt (<Meldung>)`,
  das Urteil kommt dann von Hermes. Andere Codex-Fehler und die Zeitgrenze
  lösen keinen Ersatz aus; ohne Hermes-Programm bleibt es bei `fehler`.
- **Kein Prüfer aus der Familie des Masters** (AGENTS.md, Sebastian 27.10.2026): `--master` nennt den Master
  des geprüften Themas. Bei `--master codex` prüft ohne `--pruefer` Hermes (Protokoll: `Ersatzpruefer: Hermes statt
  Codex - Master ist Codex …`); `--pruefer codex --master codex` wird mit Exit 2 abgelehnt, ohne dass ein Prüfer
  startet. Ohne `--master` bleibt alles wie bisher (Standard Codex). Den Master gibt der aufrufende Agent an.
- **Thema** wird zum Dateinamen und darf nur `a-z`, `0-9` und `-` enthalten
  (höchstens 80 Zeichen).

## Prüfer

| Prüfer | Aufruf | Modell |
|---|---|---|
| Codex (Standard) | neuestes `%LOCALAPPDATA%\OpenAI\Codex\bin\<Kennung>\codex.exe exec --ephemeral -s read-only -o <datei>` | Standardmodell der App mit `model_reasoning_effort=high`; `--gruendlich` → `gpt-6-astra` |
| Hermes | `hermes -z <auftrag> -m deepseek/deepseek-v4.1-flash --usage-file <datei> -t file,todo --in <repo>` | DeepSeek v4.1 Flash; Sitzung und Kosten aus der Nutzungsdatei |

Codex läuft über das Programm der Codex-App. Die npm-CLI 0.145 scheiterte am
12.10.2026 an der Sandbox und kannte `gpt-6.1-sol` nicht. Die Pfade lassen
sich mit `PRUEFKREIS_CODEX` / `PRUEFKREIS_HERMES` überschreiben, den
Protokollordner mit `PRUEFKREIS_DIR`.

## Protokoll

`.hermes/pruefkreis/<thema>.md` (gitignored), je Runde ein Abschnitt
`## Runde N · Zeit · Prüfer · Vorlage` mit Status, Modell, Planfassung,
Ersatzprüfer, Grund, Sitzung, Kosten, Dauer und Antwort. Die Planfassung kommt aus
`--planfassung` oder, wenn nicht angegeben, aus dem ersten `Fassung N` in der Vorlage.

## Stand (12.10.2026, Schritt 1 von 6)

Noch **nicht** gebaut: technische Nur-Lese-Sperre für Hermes (Plugin
`pruefer-nurlesen`, Schritt 2) — bis dahin hält nur der Auftragstext Hermes
vom Schreiben ab, und `-t file,todo` lässt `write_file`/`patch` noch zu.
Ebenfalls offen: Pfadsperren (3), Anpinnen und Register der Prüfsitzungen (4),
Ende-zu-Ende-Probe (5).

Tests: `backend/tests/test_pruefkreis.py` (Prüfer als Attrappen, offline).
