# Agentic Engineering als Methode — ausführliche Fassung

Dieser Text lag früher komplett in der Root-README und wurde zur Straffung hierher
verschoben. Die Root-README enthält die kurze Zusammenfassung und verlinkt hierher.

## Meine Reise: Von Claude Code zum Multi-Modell-System

| Zeit | Setup | Warum? |
|---|---|---|
| **2025** | Erste Gehversuche: Chatbots personalisiert, System-Prompts mit Ingenieurs-Denkweise optimiert | Prä-Agenten-Ära — den Grundstein für strukturierte Prompt-Architektur gelegt |
| **Januar 2026** | Start mit **Claude Code** (Enterprise-Team-Lizenz, Sonnet, Opus) | Erster KI-Coding-Agent im professionellen Einsatz |
| **März–Mai 2026** | Berufliche Praxis: TwinCAT 3, VB.NET-HMI, IO-Listen-Generierung, Schaltplan-Vergleich | KI als "Experience-Partner" — schneller lernen, nicht langsamer; Vorreiter im Team gegen alte Denkweise |
| **Juni–Juli 2026** | **Antigravity** + Google One (2× 12 €) — Test günstigerer Alternative | Kosten sparen, aber unzufrieden mit Ergebnissen |
| **August 2026** | **Hermes** (Agent, hier auf Termux/Handy + PC) + **OpenRouter** + Multi-Modell | Claude Code-Limits verschärft; DSGVO-konforme, kosteneffiziente Alternative gefunden; Hermes hat sich als Arbeits-Werkzeug durchgesetzt (VS Code + Cline nicht) |
| **August 2026** | Regelumbau: Kernregeln nach `AGENTS.md`, Workflow als Skill, Permission-Riegel, Subagenten | Erkenntnis: nicht die Regelgröße kostet das Kontingent, sondern die **Anzahl der Turns** — jede Phasengrenze verlangte eine Freigabe, ohne ein einziges maschinelles Prüf-Gate |

**Das heutige Setup:** Nicht *ein* Tool, sondern ein orchestriertes System aus Plattformen und Modellen:

| Aufgabe | Werkzeug | Modell |
|---|---|---|
| Planung & Implementierung | **Hermes** (Termux/Handy + PC) | **DeepSeek V4** (kostengünstig) |
| Bildverarbeitung | **Hermes** (Modell-Wechsel) | **Gemini 2.5 Flash** (beste Bild-Interpretation) |
| Fremdprüfung (Critic) | OpenRouter (API-Gateway) | **Anthropic Haiku** (DSGVO-konform, andere Modellfamilie) |
| Alternativ-Plattform | Claude Code | Je nach Verfügbarkeit & Kontingent |

Antigravity wurde nach der Erprobung wieder verworfen — zu wenig Kontrolle über
das, was der Agent tatsächlich anfasst. Der Wechsel zwischen Claude Code und Hermes
kostet heute nichts mehr, weil der Arbeitsstand in Dateien liegt und nicht im
Kontextfenster (siehe *Portabilität* weiter unten).

> **Die Kern-Erkenntnis:** Nicht das Tool entscheidet über Qualität, sondern das **System aus orchestrierten Modellen**, das je nach Aufgabe, Kosten und Compliance das passende Modell wählt.

## Phasenbasierter Entwicklungszyklus

Jedes Feature durchläuft acht Phasen: **Brainstorm → Alignment → Planung → Implementierung → Testing → Recap → Refactor → Commit**. Gearbeitet wird in kleinen vertikalen Slices mit atomaren Commits; am Phasenende wird der Agenten-Kontext geleert, weil Modelle bei wenig und präzisem Kontext am zuverlässigsten arbeiten. Drei Regeln stechen heraus:

* Im *Alignment* werden alle architektonischen Verzweigungen per Interview geklärt, bevor Code entsteht — der Agent trifft keine Gestaltungsentscheidung selbst.
* *Testing*, *Recap* und *Refactor* dürfen nie übersprungen werden.
* In den Phasen *Planung*, *Testing* und *Refactor* prüft ein **fremdes Modell** gegen. In der *Implementierung* ist das ausdrücklich untersagt: Kritik während des Bauens zerfasert die Umsetzung.

**Zwei Blöcke mit unterschiedlichem Charakter.** Die acht Phasen zerfallen in einen Dialog- und einen Ausführungsteil, und nur der erste braucht mich in jedem Schritt:

| Block | Phasen | Warum so | Permission-Modus |
|---|---|---|---|
| **Dialog** | 1–3 | Der Inhalt entsteht erst im Gespräch — hier gibt es nichts abzuarbeiten | `plan` (nur lesen) |
| **Ausführung** | 4–8 | Der Plan steht; der Agent läuft durch, mit **genau einem** Pflichtstopp nach Phase 4 | `acceptEdits` |

Der Pflichtstopp nach Phase 4 fällt bewusst nicht weg: Ob sich eine Oberfläche richtig bedienen lässt, kann kein Test beantworten. Das ist der einzige Punkt im Ausführungsblock, an dem ein Mensch wirklich gebraucht wird — und deshalb der einzige, an dem angehalten wird.

**Warum das ein bewusster Umbau war.** Vorher lag an jeder der sieben Phasengrenzen eine menschliche Freigabe, aber kein einziges maschinelles Prüf-Gate. Kontrolle wurde also mit meiner Zeit bezahlt statt mit Automatik — und genau daran ging das Kontingent kaputt, nicht an der Dateigröße der Regeln. Heute sitzt die Kontrolle an drei Stellen, die ohne mich funktionieren: dem freigegebenen `plan.md`, dem Prüfbefehl des Projekts mit Exit-Code, und den durchgesetzten Permission-Regeln. Ein Durchlauf ohne Zwischenfreigaben ist nur erlaubt, wenn alle drei vorhanden sind und es kein OT-/SPS-Code ist.

## Ein Regelwerk, vier Ebenen

Damit die Regeln nicht an mehreren Stellen auseinanderlaufen, gibt es genau **eine** Quelle — und sie liegt bewusst in der werkzeugneutralen Datei, nicht in der herstellerspezifischen:

| Datei | Rolle | Wann sie gilt |
|---|---|---|
| [AGENTS.md](AGENTS.md) | **Die Quelle:** Sprache, Leitplanken, Autonomiegrenze, Verifikationsregel | immer, in jedem Werkzeug |
| [CLAUDE.md](CLAUDE.md) | Nur das Claude-Code-Spezifische (Skills, Subagenten) + `@AGENTS.md` | immer, nur in Claude Code |
| `CLAUDE_EXTENDS.md` je Bereich | Zusatzregeln der Domäne: SPS-Namenskonventionen (Ungarische Präfixe, Zehner-Schrittketten) in OT, Design- und SEO-Vorgaben in IT | sobald eine Datei des Bereichs gelesen wird |
| [.claude/settings.json](.claude/settings.json) | Die Regeln, die **nicht** verhandelbar sind — durchgesetzt vom Harness, nicht vom Modell | in jedem Permission-Modus |

[sync-rules.ps1](sync-rules.ps1) erzeugt daraus die Bereichs-`CLAUDE.md`: ein Verweis auf die Wurzel-Datei plus die lokale Erweiterung.

**Warum `AGENTS.md` und nicht `CLAUDE.md` die Quelle ist.** Ich arbeite heute mit **Hermes** (Termux/Handy + PC) und bei Bedarf mit Claude Code. Hermes liest `AGENTS.md` nativ. `AGENTS.md` ist die Konvention, auf die sich die Werkzeuge 2026 geeinigt haben — Claude Code zieht sie per Import herein, Hermes liest sie direkt, und beim nächsten Harness-Wechsel funktioniert sie ohne Zutun weiter. Eine Quelle, keine Kopie, kein Auseinanderdriften.

**Der Umbau dahinter:** Ursprünglich kopierte `sync-rules.ps1` das komplette Basis-Regelwerk in jede Bereichsdatei. Das erzeugte zwei Probleme — die Kopien konnten unbemerkt von der Quelle abdriften, und jeder Agent lud dieselben ~130 Zeilen ein zweites Mal in seinen Kontext. Heute steht dort ein zweizeiliger Verweis. Im zweiten Schritt wanderte der 8-Phasen-Workflow aus dem Dauerkontext in einen Skill, der nur auf `/phase` lädt: der permanent sichtbare Ablauf hatte dazu geführt, dass das Modell auf spätere Phasen vorgriff. Der dauerhaft geladene Regelanteil sank dabei von 136 auf 98 Zeilen.

## Bitten und Riegel — der Unterschied, der zählt

Eine Regel in einer Markdown-Datei ist eine **Bitte an das Modell**. Sie beschreibt, was der Agent tun *soll*. Was er tatsächlich *darf*, steht in [.claude/settings.json](.claude/settings.json) und wird vom Harness durchgesetzt — unabhängig davon, was das Modell gerade denkt oder wie ein Prompt formuliert ist.

| Ebene | Inhalt | Wirkung |
|---|---|---|
| `deny` | das private Chat-Archiv | technisch gesperrt, in jedem Modus |
| `ask` | `git push`, `npm publish`, `docker push` | alles, was den Rechner verlässt, braucht meine Freigabe |
| `allow` | git-Lesebefehle, `add`/`commit`, Prüfbefehle, Fremdprüfer | damit ein Durchlauf nicht an jedem Testlauf stehenbleibt |

Die `deny`-Zeile ersetzt eine frühere Absichtserklärung durch eine tatsächliche Sperre; die `ask`-Zeile macht aus „der Agent pusht nicht" einen Riegel. Erst dadurch wird Automatik verantwortbar: Die `allow`-Liste macht den Durchlauf überhaupt möglich, `ask` und `deny` machen ihn vertretbar.

## Das Verifier-Gate: woran „fertig" hängt

Ein Schritt gilt als fertig, wenn der Prüfbefehl des Projekts **Exit-Code 0** liefert — nicht, wenn er plausibel aussieht. Diese Befehle sind ausgeführt, nicht abgeschrieben:

| Projekt | Prüfbefehl | Ergebnis |
|---|---|---|
| typeFREE | `set PYTHONPATH=. && python -m pytest windows/tests -q` | 84 Prüfungen, Exit 0 |
| concertify | `python -m pytest tests -q` | 180 Prüfungen, Exit 0 |
| RAG-Systeme, document_automation | **noch keiner** | — |
| personal_ai_agent | kein pytest; Prüfbeleg = Server läuft + `curl http://localhost:8080/ping` → `{"ping":"pong"}` (Exit 0), Syntax via `python -m py_compile` | Server antwortet |

Daran hängt, wie viel Leine ein Projekt bekommt: Wo ein Gate existiert, läuft der Ausführungsblock durch. Wo keins existiert, wird jede Änderung einzeln vorgelegt — und der fehlende Prüfbefehl wird benannt, statt durch „sieht gut aus" ersetzt zu werden. Einen Befehl zu erfinden, der nichts prüft, wäre schlechter als keiner.

Für den OT-Bereich gibt es dieses Gate **grundsätzlich nicht**: SPS-Code wird manuell eingespielt, ein Testlauf auf einer laufenden Anlage ist keine Option. Dieser Bereich bleibt dauerhaft an der kurzen Leine, und der Agent liefert dort nur Blaupausen.

**Die Belegpflicht dahinter.** Ein Prüfbefehl nützt nichts, wenn „fertig" gesagt wird, ohne ihn auszuführen. Deshalb steht in `AGENTS.md` nicht nur die Regel, sondern das Verfahren: Welcher Befehl belegt die Behauptung? Frisch und vollständig ausführen. Ausgabe und Exit-Code lesen. Deckt die Ausgabe die Behauptung? Erst dann die Aussage — mit dem Beleg. Wurde ein Befehl nicht in derselben Antwort ausgeführt, gilt er als nicht ausgeführt.

Der Punkt, der in der Praxis am häufigsten greift, betrifft die Subagenten:

| Behauptung | Beleg | Reicht **nicht** |
|---|---|---|
| Tests grün | Ausgabe des Prüfbefehls, Exit-Code 0 | ein früherer Lauf |
| Fehler behoben | ursprüngliches Symptom erneut geprüft | „Code geändert, müsste gehen" |
| **Subagent fertig** | **`git diff` zeigt die Änderung** | **die Erfolgsmeldung des Subagenten** |
| Anforderung erfüllt | `plan.md` Punkt für Punkt geprüft | „Tests sind grün" |

`rechercheur` und `tester` melden Erfolg, ohne dass ihr Ergebnis im Hauptkontext sichtbar wäre — genau der Vorteil, der sie nützlich macht, macht ihre Meldung unüberprüfbar. Ungeprüft übernommen ist das eine Behauptung ohne Beleg.

## Kontext als knappe Ressource — gemessen statt geschätzt

Der Auslöser des Regelumbaus war ein schnell aufgebrauchtes Nutzungskontingent. Die naheliegende Vermutung — die Regeldateien seien zu groß — hat sich bei der Messung als **falsch** erwiesen:

| Posten beim Sitzungsstart | Anteil |
|---|---|
| Werkzeuge und System-Prompt der Plattform | 16,5k |
| MCP-Werkzeuge (aktiv) | 7,3k |
| Skills | 4,1k |
| Regeldateien (`AGENTS.md`, `CLAUDE.md`, Gedächtnis) | 4,0k |
| **Gesamt** | **32,1k von 1 Mio — 3 %** |

Bei drei Prozent Auslastung kann die Startlast nicht der Treiber gewesen sein. Der Treiber war die **Anzahl der Turns**: Der ursprüngliche Workflow verlangte an jeder der sieben Phasengrenzen eine menschliche Freigabe, ohne ein einziges maschinelles Prüf-Gate — jede Rückfrage kostet einen vollständigen Durchlauf über den gesamten Kontext.

Zwei Konsequenzen daraus, und beide sind der eigentliche Ertrag dieses Umbaus:

* **Turns einsparen statt Zeichen.** Verifier-Gate und Subagenten ersetzen Bestätigungsklicks durch durchgesetzte Regeln und Prüfbefehle. Das ist der große Hebel; kürzere Regeldateien sind der kleine.
* **Werkzeuge nach Bauart auswählen, nicht nach Thema.** Skill-Beschreibungen liegen in *jedem* Request im Kontext, Commands und Agents laden erst beim Aufruf, MCP-Werkzeuge werden seit Claude Code v2.1.7 verzögert geladen. In diesem Setup sind 55,1k an MCP-Werkzeugen vorhanden, aber nur 7,3k tatsächlich geladen. Fremde Plugins werden deshalb nach der Zahl ihrer Skills ausgewählt — bevorzugt solche mit null.

## Portabilität über Werkzeuggrenzen

Der Zustand einer laufenden Arbeit liegt bei mir **in Dateien, nicht im Kontextfenster**: `brainstorm.md`, `alignment.md`, `plan.md`. Das ist der Grund, warum ein `/clear` nach jeder Phase nichts kostet — und derselbe Grund, warum ein Wechsel des Werkzeugs mitten im Projekt funktioniert.

| Ebene | Portabel? | Inhalt |
|---|---|---|
| `AGENTS.md` | überall | Kernregeln, Autonomiegrenze, Verifikationsregel |
| Übergabedateien | überall — es sind nur Markdown-Dateien im Repo | der Zustand der laufenden Arbeit |
| `.claude/skills`, `.claude/agents`, `.claude/settings.json` | nur Claude Code | Workflow, Subagenten, Permission-Riegel |

Wer mit einem Werkzeug ohne `/phase`-Skill und Subagenten weiterarbeitet, verliert diese — die Kernregeln (`AGENTS.md`) und der Arbeitsstand in den Dateien bleiben.

## Ausführbare Skills statt Prosa-Regeln

Die heikelsten Stellen im Zyklus sind nicht als Merksatz formuliert, sondern als Verfahren mit festem Ablauf, Abbruchkriterium und einer Tabelle typischer Ausreden samt Gegenrede. Fünf Skills liegen im Repository: [`phase`](.claude/skills/phase/SKILL.md) hält den Ablauf selbst vor und lädt nur auf Aufruf, [`grillAnAgent`](.claude/skills/grillAnAgent/SKILL.md) grillt den Brainstorm, [`fehlersuche`](.claude/skills/fehlersuche/SKILL.md) greift bei jedem Fehler von selbst — und die beiden folgenden sind die eigentlichen Qualitätsgrills.

**[`fehlersuche`](.claude/skills/fehlersuche/SKILL.md) — Ursache vor Reparatur.** Vier Phasen mit einer Sperre davor: keine Reparatur ohne benannte Ursache. Der wirksamste Teil ist die Anweisung, bei mehreren beteiligten Bauteilen an *jeder* Grenze auszugeben, was hinein- und was herausgeht, statt am wahrscheinlichsten Verdächtigen herumzuprobieren — danach steht fest, welches Bauteil versagt. Abgebrochen wird nach zwei gescheiterten Versuchen, und dann wird nicht „geht immer noch nicht" gemeldet, sondern der eigentliche Befund: *Wenn jede Reparatur anderswo ein neues Problem aufdeckt, ist nicht der Fehler das Problem, sondern die Annahme über die Architektur.*

**[`grill-me`](.claude/skills/grill-me/SKILL.md) — der Grill *vor* dem Bauen.** Alignment als ausführbares Verfahren: erst ein Register aus 8–15 Annahmen zum Widersprechen, dann sokratische Einzelfragen — eine pro Nachricht, immer mit 2–4 konkreten Optionen und einer begründeten Empfehlung, sodass eine Antwort aus einem Buchstaben bestehen kann. Danach drei Angriffe auf das eigene Ergebnis (*„Das scheitert, wenn …"*), erst dann die `alignment.md`. Die eiserne Regel: keine Datei-Änderung am Zielprojekt, bevor das Alignment freigegeben ist. Zeichnen sich mehr als ~15 Fragen ab, gilt nicht die Fragenzahl als Problem, sondern der Slice — dann wird geteilt.

**[`critic`](.claude/skills/critic/SKILL.md) — der Grill *nach* dem Bauen.** Generator-Critic-Muster über zwei Modellfamilien: ein Modell baut, ein Modell einer anderen Familie prüft, weil beide unterschiedliche blinde Flecken haben. Zwei Konstruktionsprinzipien: Das fremde Modell bekommt den Code im Prompt übergeben — es liest keine Dateien und führt nichts aus. Und es liefert **Befunde, keine Urteile**: entschieden wird je Punkt vom Menschen, nie automatisch behoben. Einstiegspunkt ist [`pruefe.mjs`](.claude/skills/critic/pruefe.mjs), das Prompt, Format und Fehlerbehandlung mitbringt:

| Motor | Aufruf | Kontingent | Einschränkung |
|---|---|---|---|
| **Haiku via OpenRouter** (DSGVO-Standard) | `--openrouter` oder Flag-frei | API-Kosten | DSGVO-konform, Daten nicht zur Produktverbesserung; API-Key per Header |
| Gemini-API (Fallback) | `--gemini` | 1.500 Läufe/Tag | API-Schlüssel nötig, per Header übertragen — nie in der URL |
| Antigravity | `--agy` | 20 Läufe/Tag | kein Schlüssel nötig, max. 30.000 Zeichen |
| Codex (Sonderfall) | explizit | Monatskontingent | schärfer bei Nebenläufigkeit, nur auf ausdrücklichen Wunsch |

## Subagenten: Wegwerf-Kontext bleibt draußen

Ein Skill wird in den *Hauptkontext* geladen und kann mit mir reden. Ein **Subagent** hat ein eigenes Kontextfenster, arbeitet ab und gibt nur eine Zusammenfassung zurück — er kann nicht mit mir reden, spart dafür Tokens auch *während* der Arbeit. Die Entscheidungsregel ist eine einzige Frage: *Erzeugt dieser Schritt Material, das nie wieder gebraucht wird?*

| Subagent | Aufgabe | Was zurückkommt |
|---|---|---|
| [`rechercheur`](.claude/agents/rechercheur.md) | Codesuche in Phase 3 und 7 | Dateipfade mit Zeilennummern, max. zehn Zeilen Zusammenfassung — keine Dateiinhalte |
| [`tester`](.claude/agents/tester.md) | Prüfläufe in Phase 5 und nach jedem Refactoring | Exit-Code, Trefferzahl, je Fehlschlag Datei/Zeile/Meldung — keine Logs |

Beide laufen auf Haiku: Wegwerf-Arbeit darf auch günstig sein. Der `tester` repariert bewusst **nichts** — er meldet und hört auf. Sonst würde die Instanz, die den Fehler gemacht hat, ihr eigenes Ergebnis bewerten.

Testlogs und Suchtreffer sind der größte Wegwerf-Kontext überhaupt. Sie aus dem Hauptgespräch herauszuhalten ist das, was längeres Arbeiten in einer Sitzung überhaupt erst trägt — zusammen mit dem Prüfbefehl je Projekt.

## Was die Fremdprüfung messbar gelehrt hat

1. **Großer Prüfumfang kostet Befunde.** Gleicher Code, gleiches Modell: Bei 27.000 Tokens meldete der Critic einen schweren Befund (Feldzugriff auf ein möglicherweise nicht gesetztes Objekt). Im Wiederholungslauf mit 62.000 Tokens fehlte genau dieser Befund. Konsequenz: lieber drei gezielte Läufe über einzelne Dateien als einer über alles — das Kontingent ist reichlich, die Aufmerksamkeit des Modells ist der Engpass.
2. **Schweregrade sind unzuverlässig.** Dieselbe SQL-Injection kam je nach Modell als *kritisch* oder *hoch* zurück, ein sicherer Absturz als *mittel*. Jeder Befund wird deshalb nachgestuft und die Korrektur kenntlich gemacht, statt das Protokoll durchzureichen.
3. **Ein leeres Protokoll ist keine Freigabe.** Die Fremdprüfung findet andere Dinge als ein Testlauf, nicht dieselben — sie ersetzt die Testphase nicht.
4. **Fehlerausgaben nie unterdrücken.** Wird `stderr` verworfen, ist ein Kontingent- oder Authentifizierungsfehler nicht mehr von einem leeren Ergebnis zu unterscheiden. Genau daran ist der erste Aufbau mehrfach gescheitert.

## DSGVO-konforme Zone: OpenRouter als API-Gateway

Ein zentrales Merkmal der aktuellen Architektur: **OpenRouter dient als DSGVO-konformes API-Gateway**, das die Nutzung von Modellen (z. B. Anthropic Haiku für die Fremdprüfung) ermöglicht, ohne dass Daten zur Produktverbesserung verwendet werden dürfen.

| Aspekt | Umsetzung |
|---|---|
| Datenverarbeitung | OpenRouter verarbeitet Anfragen DSGVO-konform; keine Nutzung der Inhalte für Modell-Training |
| API-Key-Handling | Schlüssel per Header (nie in der URL), zusätzlich abgesichert durch `.env` und `.gitignore` |
| Kostenkontrolle | Pay-per-Use statt Abo — günstiger als Flatrate-Modelle bei geringem Volumen |
| Zukunfts-Roadmap | Concertify soll von direkter Gemini-API auf OpenRouter umgestellt werden |

## Grenze der Fremdprüfung: was das Repository nicht verlässt

Im kostenlosen Tier nutzt ein Anbieter übermittelte Inhalte zur Produktverbesserung. Die Grenze verläuft deshalb **nicht** zwischen den beiden Domänen, sondern zwischen den Motoren und den Inhalten:

| | IT-Code (`02_…`) | OT-Code (`01_…`) | Prozess-Know-how, Kundenlogik, NDA |
|---|---|---|---|
| **OpenRouter / Haiku** | erlaubt | erlaubt | **nie** |
| **Gemini-API direkt, Antigravity** | erlaubt | gesperrt | **nie** |

Der Grund für die mittlere Spalte: OpenRouter verarbeitet als Gateway DSGVO-konform und schließt die Nutzung zum Modell-Training aus — die Direktverbindungen tun das im kostenlosen Tier nicht. Die rechte Spalte kennt dagegen keine Ausnahme, unabhängig vom Motor: **DSGVO-konform heißt nicht automatisch „darf den Rechner verlassen".** Verfahrenstechnisches Wissen und alles unter NDA bleiben lokal.

Festgehalten ist das als Bereichsdirektive in [01_IT-OT_Integration/CLAUDE_EXTENDS.md](01_IT-OT_Integration/CLAUDE_EXTENDS.md) und in der [CLAUDE.md](CLAUDE.md) der Wurzel — an einer Stelle entschieden, nicht als guter Vorsatz.

## Qualitäts-Gates: Architekt & Wächter

Jede größere Änderung durchläuft zwei komplementäre Rollen: Der **Architekt** entwirft (strikte Schichtung `routes → services → domain → repositories`, Dependency Injection über Konstruktoren), der **Wächter** prüft anschließend gegen einen festen Katalog:

| Check | Kriterium |
|---|---|
| Kapselung | Keine Schicht greift an einer anderen vorbei |
| Dependency Injection | Abhängigkeiten über Konstruktor/Abstraktionen, keine versteckten Globals |
| Testbarkeit | Kernlogik testbar ohne echte I/O |
| Komplexität | Methoden kompakt halten, Early Returns statt Verschachtelung |
| Frontend | Event-Delegation statt Inline-Handler |

Angewendet und dokumentiert ist das System im Concertify-Projekt: [dual_engineering_system.md](02_Softwareentwicklung_IT/concertify/docs/dual_engineering_system.md). Sichtbares Ergebnis ist die Testsuite unter [concertify/tests/](02_Softwareentwicklung_IT/concertify/tests/) (Unit-Tests je Schicht: `domain/`, `repositories/`, `services/`).
