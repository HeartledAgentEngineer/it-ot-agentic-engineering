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
  startet. Ohne `--master` liest das Werkzeug den Besitzer aus der Besitzdatei des Master-Schalters
  `.hermes/uebergabe/laufend/<name>.master` (Umgebungsvariable `PRUEFKREIS_BESITZ_DIR` für Tests). `<name>` ist das
  Thema selbst oder der längste Anfang vor einem Bindestrich: `--thema master-schalter-kurz` nimmt
  `master-schalter.master`, `master-schalterx` nimmt sie nicht. Leere Datei = `claude` (wie `besitz.py` im Schalter).
  Unlesbare Datei, unbekannter Besitzer oder keine Datei ⇒ **Abbruch mit Exit 2**, ohne dass ein Prüfer startet,
  bis `--master` angegeben ist (sonst könnte Codex unbemerkt einen Codex-Master prüfen; Codex-Einwand R1,
  27.10.2026). Ausnahme `--sensibel`: dort prüft ohnehin Hermes. Aus einem Git-Worktree heraus gelten
  Besitzdateien und Protokolle des **Hauptarbeitsbaums** (`.hermes/` ist gitignored und liegt nur dort; aufgelöst
  über `.git` → `gitdir` → `commondir`, ohne Git-Aufruf). Das Protokoll nennt in jeder Runde die Quelle, z. B.
  `Master: codex (master-schalter.master)`; ein ausdrückliches `--master` steht als `(angegeben)` darin und geht
  der Datei vor.
- **Codex laut Messung im Limit ⇒ gleich Hermes** (kein Fehlversuch): Ohne `--pruefer` liest das Werkzeug die
  Codex-Messung des Master-Schalters (`~/.master-schalter/codex-kontingent.json`, `MASTER_SCHALTER_DATEN` hat
  Vorrang). Nur wenn sie höchstens 15 min alt ist und ein Fenster (5h oder Woche) bei 100 % (gültig sind nur 0–100) mit Reset in der
  Zukunft steht, prüft sofort Hermes; Protokoll: `Ersatzpruefer: Hermes statt Codex - Codex 5h 100 % laut Messung
  HH:MM, Reset … (kein Fehlversuch)`. Fehlende, alte oder kaputte Messung (z. B. Prozent außerhalb 0–100, nicht darstellbarer Reset) ⇒ wie bisher Codex mit Ersatz bei
  Sperre. `--pruefer codex` versucht Codex weiterhin ausdrücklich.
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
