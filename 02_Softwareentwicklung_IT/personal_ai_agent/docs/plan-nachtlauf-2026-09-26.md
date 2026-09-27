# Nachtlauf 26./27.09.2026 — Fotos, Videos, Personen (autonom)

> **Auftrag:** Sebastian (26.09.2026, ~04:30): „Wir wollen eine Langzeit-Session
> bauen … dass du das alles abarbeitest. Ich gehe jetzt für 4–5 Stunden schlafen.
> Arbeite ohne Unterbrechung und komm nicht mit Fragen, sondern entscheide
> selbst. […] Wenn du unsicher bist: **nichts löschen**, nur verschieben,
> sortieren — oder erstmal nur den Upload-Ordner sortieren. Wenn was schiefläuft,
> müssen wir es zurückstellen können."
>
> **Regeln:** `AGENTS.md` → Abschnitt „Dauerlauf / Nachtarbeit (autonom)".
> Kernpunkte: keine Rückfragen, jeder Schritt verifiziert + einzeln committet,
> **nie löschen**, jede Schreib-Operation ins **Manifest** (rückholbar),
> idempotent bauen, billigste Wege zuerst.

## Rollen: Planer → Ausführer → Prüfer (getrennte Kontexte, verbindlich)

Nach `CLAUDE_EXTENDS.md` §6.6 und dem Everlast-Kanon (Punkte 1–3): **nie** plant,
führt aus und prüft derselbe Kontext.

| Rolle | Wer | Aufgabe im Nachtlauf |
|---|---|---|
| **Planer** | Hauptkontext (dieser Chat) | Diesen Plan als Datei schreiben, Reihenfolge + Prüfkriterien festlegen, committen. **Kein** Bauarbeit-Selbstlauf am eigenen Werk. |
| **Ausführer** | je Schritt ein **Subagent** (`delegate_task`) | genau **einen** Planschritt umsetzen, Code + Tests + Doku, **keine** git-Befehle |
| **Prüfer** | **frischer** Subagent, **anderes Modell als der Ausführer** | gegen den Plan prüfen, Prüfbefehl selbst ausführen, Abweichungen benennen, „bestanden/nicht bestanden" |

**Ablauf je Schritt:** Planer beschreibt → Ausführer baut → **Prüfer prüft** →
Planer committet (nur bei „bestanden"). Ein Schritt ohne Prüfer-Abnahme gilt als
**offen**, auch wenn er gebaut ist.

**Warum das im Nachtlauf doppelt zählt:** Ohne getrennten Prüfer bestätigt der
Bauende seine eigene Annahme — im Nachtlauf sieht Sebastian das Ergebnis erst
Stunden später. Fehler, die ein frischer Kontext findet, kosten Minuten; Fehler,
die bis zum Morgen liegen, kosten den ganzen Lauf.

## Modell-Mix (Anmerkung Sebastian: „verschiedene Modelle miteinander kombinieren")

**Befund:** `config.yaml` hat unter `delegation:` nur `max_iterations` — **kein**
Modell gepinnt. Damit erben alle Subagenten das Hauptmodell
(`deepseek/deepseek-v4.1-flash`). Sebastian hat recht: das ist noch keine
Vielfalt. Wird bewusst **pro Rolle** gesetzt:

| Rolle | Modell | Weg | Warum |
|---|---|---|---|
| **Planer (Denken)** | `gpt-5.6-terra` | **nur über die Codex CLI** (ChatGPT-Konto, `codex exec --model gpt-5.6-terra --sandbox read-only`) | stärkstes verfügbares Denken, **keine Token-Rechnung** — nur Volumen. Denken ist selten, teuer darf sein |
| **Ausführer (Masse)** | `deepseek-v4.1-flash` | Hermes-Subagenten | **Cache 0,001 $/Mio** → lange Sitzungen kosten fast nichts |
| **Ausführer (schwerer Coding-Block)** | `gpt-5.6-terra` | Codex CLI, `--sandbox workspace-write` | starke Umsetzung ohne Zusatzkosten über das Konto |
| **Prüfer (andere Familie!)** | `gpt-5.6-luna` (0,20/1,20) oder `z-ai/glm-5.2` (0,65/2,04) | `hermes -z "<Auftrag>" -m <Modell>` | Fehler, die eine Familie macht, findet dieselbe Familie nicht |

**Gemessene Preise (OpenRouter, je 1 Mio Token, 27.09.2026, live abgefragt):**

| Modell | Eingang | Ausgang | Cache | Kontext |
|---|---|---|---|---|
| `deepseek-v4.1-flash` | **0,035** | 0,290 | **0,001** | 1,05 M |
| `deepseek-v4-flash-0731` | **0,021** | 0,320 | 0,016 | 1,31 M |
| `openai/gpt-5.6-luna` | 0,200 | 1,200 | 0,020 | 1,05 M |
| `openai/gpt-5.6-terra` | **2,000** | **12,000** | 0,200 | 1,05 M |
| `google/gemini-3.7-flash` | 0,750 | 3,750 | 0,075 | 1,05 M |
| `z-ai/glm-5.2` | 0,650 | 2,042 | 0,121 | 1,05 M |

**Konsequenz (Sebastians Einwand, bestätigt):** Terra über OpenRouter wäre
**57× teurer im Eingang / 41× teurer im Ausgang** als DeepSeek V4.1 Flash —
für einen Ausführer-Schritt (~200 k rein, ~50 k raus) sind das **≈ 1,00 $ statt
≈ 0,02 $**. Deshalb: **Terra ausschließlich über das ChatGPT-Konto (Codex CLI)**,
niemals über OpenRouter als Ausführer.

**Datenschutz-Grenze (bleibt hart):** Nur **reiner Code** geht an Codex.
Chat-Archiv, Fotos, Erinnerungen, `.env`, Bewerbungen bleiben bei
Hermes/DeepSeek (Skill `ai-datenschutz-regeln`).

## Qualität halten, obwohl billig ausgeführt wird (Sebastians Kernfrage)

Sebastian (27.09.): „Wir sind auf die Ebene DeepSeek V4.1 Flash gegangen — wir
wollen es günstiger machen, aber von der Qualität fast gleich hoch."

**Die Logik:** Qualität kommt **nicht** aus jedem ausgeführten Token, sondern aus
drei Dingen — und die kosten fast nichts:

1. **Guter Plan vom starken Modell.** Terra (Codex-Konto) bzw. Claude Code
   zerlegen die Aufgabe in einen **präzisen Auftrag**: welche Datei, welches
   Verhalten, welches Prüfkriterium. Ein billiger Ausführer mit klarem Auftrag
   liefert fast dasselbe wie ein teurer mit vagem Auftrag.
2. **Prüfer aus einer anderen Familie.** Die teure Fehlerquote entsteht dort, wo
   niemand gegenliest. Ein fremdfamiliärer Prüfer (`gpt-5.6-luna`, `glm-5.2`,
   `codex review`) kostet Cent-Beträge und fängt genau die Fehler, die der
   Ausführer selbst nicht sieht.
3. **Prüfbefehl als Tor.** Kein Commit ohne Exit-Code 0 — die Wahrheit liegt im
   Befehl, nicht im Gefühl des Ausführers.

**Wo NICHT gespart wird (harte Schritte bleiben beim starken Modell):**
Architektur-Entscheidungen, knifflige Bugs (Race Conditions, Datenverlust-Risiko),
Sicherheits-/Datenschutzfragen, Umbauten an bestehender Logik. Diese Aufgaben sind
selten und teuer im Kopf — aber billig in der Rechnung, wenn sie wenige Male laufen.

**Faustregel:** *Denken und Prüfen = stark, Ausführen = billig.* Wer die Ausführung
mit dem starken Modell fährt, zahlt das 40–50-Fache für Arbeit, die der Prüfer
ohnehin nachkontrolliert.

## Entscheidungen, die ich selbst treffe (statt zu fragen)

1. **Zielstruktur:** `Agent/Fotos/<Jahr>/<Thema>/` (Sebastians Vorgabe B) — und
   **verschieben statt kopieren** aus dem Upload-Ordner. Grund: pCloud kann das
   in Millisekunden (nur Metadaten), es spart 45 GB Upload-Verkehr, und es ist
   über das Manifest **umkehrbar** (zurück in den Quellordner).
2. **Erinnerungs-Ablage:** eigene Datei außerhalb des Repos
   (`~/foto_erinnerungen/erinnerungen.jsonl`), getrennt vom Gedächtnis-Dienst,
   Personen über **stabile Kennungen** (`Person_001` …). Text im Wortlaut,
   Versionen über `history`.
3. **Personen-Rechnen:** Rechnung auf dem PC, **Benennen** später auf dem Handy
   im Quiz (dort liegen Katalog, Referenzen und die Fragen).
4. **Kostenschutz:** Vorschaubilder (120×120 über die API) für die Themen-Stufe;
   Gesichtserkennung braucht Originale → **Jahres-Stapel**, erst Stichprobe
   messen, dann Vollauf.

## Sicherheitsnetz (vor der ersten Schreib-Operation fertig)

* **Manifest:** `~/foto_sortierung/manifest.jsonl` — je Zeile
  `{zeit, art: movefolder|movefile|createfolder, von_id, nach_id, name, datei_id}`.
  Damit kann jede Aktion **rückwärts** gefahren werden.
* **Rückroll-Werkzeug:** `tools/pcloud/pcloud_rueckrollen.py`
  (`--zeigen` listet, `--rueckwaerts N` macht die letzten N Aktionen rückgängig).
* **Keine Löschbefehle** im gesamten Werkzeugsatz — `deletefile`/`deletefolder`
  werden nicht implementiert, auch nicht „zur Sicherheit".
* **Probelauf-Schalter:** jedes Schreib-Werkzeug hat `--trocken` (zeigt nur, was
  es täte) und läuft zuerst mit `--trocken`.
* **Crypto Folder** wird nie berührt (im Konto aktiv, tabu).

## Schritte (in dieser Reihenfolge, jeder mit Prüfkriterium)

| # | Schritt | Prüfkriterium | Stand |
|---|---|---|---|
| N1 | Cloud-Service (Hintergrund-Bau) **selbst prüfen** + committen | `pytest tests/ -q` grün; Rauchtest-Zahlen aus dem Bericht nachgefahren | ⬜ |
| N2 | **Selbstheilung + Rollback-Werkzeug** committen (schon gebaut: `pcloud_token_erneuern.py`) | Prüfmodus sagt „gültig"; Rückroll-Tool mit Tests | ⬜ |
| N3 | **Token aufs Handy** (USB) + Selbsttest-Zeile „pCloud" + `start-termux.sh` übernimmt die Datei automatisch | `curl` am Handy liefert `pcloud: verbunden`; JS-Tests grün | ⬜ |
| N4 | **Themen-Stufe Werkzeug**: `tools/foto_sortierung/foto_themen.py` — Ordnerbaum je Ebene, Vorschaubilder in Stapeln, Kontaktbögen bauen | Werkzeug-Tests grün; Kontaktbogen-Datei entsteht (Größe/Kacheln belegt) | ⬜ |
| N5 | **Stichprobe Kosten** (1 Bogen → Vision) → Thema je Anlass | gemessene Kosten pro Bogen notiert, bevor der Vollauf startet | ⬜ |
| N6 | **Themen je Anlass** (Stapel) → Zuordnung im Sortierschlüssel | Anzahl Anlässe je Jahr/Thema; Stichprobe nachgesehen | ⬜ |
| N7 | **Probelauf `--trocken`** des Sortierens (Ordner anlegen + verschieben) | Liste der geplanten Züge, gegengeprüft | ⬜ |
| N8 | **Sortieren echt** (Jahr für Jahr, kleinster Stapel zuerst) | Manifest vollständig; Stichprobe am Zielordner per API geprüft | ⬜ |
| N9 | **Personen-Stufe vorbereiten**: Modelle/OpenCV am PC prüfen, Vektoren + Cluster-Verfahren, unbenannte Gruppen + Referenzseiten | Cluster-Anzahl je Stichprobe; Referenzseiten vorhanden | ⬜ |
| N10 | **Doku + Protokoll + Abschlussbericht** (Changelogs, `CLAUDE.md`, Planjournal) | alles committet, Bericht mit Zahlen | ⬜ |

## Journal (wird fortlaufend ergänzt)

* **26.09. ~04:40** — Regeln in `AGENTS.md` („Dauerlauf / Nachtarbeit")
  verankert; Entscheidungen oben festgehalten; Plan angelegt.
  Der Cloud-Service-Bau (`deleg_1a630b66`) läuft noch im Hintergrund.
  Selbstheilung (`pcloud_token_erneuern.py`) gebaut und **live belegt**
  (Prüfmodus „gültig", Neu-Holen erfolgreich).
