# Eigenes Agent-Harness fuers Programmieren — Machbarkeitsanalyse

**Stand:** 17.08.2026
**Anlass:** Die Kette Agent → Auftragsbuch → Hermes laeuft nicht vollautomatisch.
Frage: Wie schwer ist es, ein eigenes Programmier-Harness zu bauen, das wirklich
gut funktioniert — und laesst sich etwas Bestehendes uebernehmen?

---

## Kurzfassung

Drei Befunde, die die Ausgangslage veraendern:

1. **Das Modell ist nicht der Engpass.** DeepSeek V4 Flash liegt bei **79,0 %
   SWE-bench Verified** — rund 1,6 Punkte hinter V4 Pro, MIT-lizenziert. Die
   Wahl war richtig, nicht ein Kompromiss aus Sparsamkeit.

2. **Das Harness ist der Hebel — und zwar messbar gross.** Dasselbe Modell
   erreichte in einer Untersuchung von Cursor **46 % im einen und 80 % im
   anderen Harness**. Auf SWE-bench Pro: 23 % → 52 % (GLM-5.2), 15 % → 36 %
   (Gemma 4 26B). Der Abstand zwischen gutem und schlechtem Geruest ist
   groesser als der zwischen billigem und teurem Modell.

3. **Die Android-Sackgasse verschwindet, wenn der Coding-Agent kein
   Android-Programm ist.** Hermes laesst sich von aussen nicht beauftragen
   (gemessen: nur `MAIN`/`LAUNCHER`, keine Intent-Extras). Ein
   Kommandozeilen-Agent in Termux hat dieses Problem gar nicht erst — der
   Watcher kann ihn direkt aufrufen. **Das ist der eigentliche Ausweg.**

**Empfehlung:** Nicht bei null anfangen, aber auch nicht blind klonen. Zuerst
einen Termux-tauglichen Kommandozeilen-Agenten anbinden (Tagesaufwand), damit
die Kette ueberhaupt durchlaeuft. Ein eigenes Harness ist danach eine bewusste
Entscheidung, keine Notwendigkeit.

---

## 1. Warum das Modell nicht das Problem ist

| Kennzahl | DeepSeek V4 Flash |
|---|---|
| SWE-bench Verified | **79,0 %** (V4 Pro: 80,6 %) |
| Lizenz | MIT, offene Gewichte |
| Architektur | ~284 Mrd. Parameter MoE, ~13 Mrd. aktiv |
| Kontext | 1 Mio. Token |
| Verbreitung | 70 % des agentischen Token-Verkehrs von DeepSeek auf OpenRouter, einen Monat nach Erscheinen |

Die Fassung vom 31.07.2026 schlug die eigene Spitzenversion V4 Pro auf **allen
neun** veroeffentlichten Agenten-Benchmarks. Auf DeepSWE stieg dasselbe Modell
von 7,3 auf 54,4 — ein Sprung um 645 %, allein durch Nachtraining auf
agentisches Arbeiten.

Das deckt sich mit deiner eigenen Beobachtung: Gemini 2.5 Flash Lite war im
Agentenbetrieb deutlich schlechter als DeepSeek V4 Flash. Das war kein
Zufall — Flash ist ausdruecklich fuer Werkzeuggebrauch nachtrainiert, viele
andere Sparmodelle sind es nicht.

**Folgerung:** Ein Wechsel auf ein teureres Modell wuerde wenig bringen. Die
Luft nach oben liegt woanders.

---

## 2. Was ein Harness ausmacht — und warum Klonen allein nicht reicht

Die Streuung ist erheblich: dasselbe Modell, zwei Geruest, 46 % gegen 80 %.

Ein Fallstrick steckt allerdings in den Zahlen: **Harness-Rangfolgen
uebertragen sich kaum zwischen Modellen** (Rangkorrelation −0,05). Ein Geruest,
das mit Claude glaenzt, kann mit DeepSeek mittelmaessig sein — und umgekehrt.

> Deshalb ist „wir kopieren einfach Claude Code" kein Plan. Es waere ein
> Geruest, das auf ein anderes Modell hin abgestimmt wurde. Uebernehmen ja,
> aber mit Messung am eigenen Modell.

Aus demselben Grund lassen sich veroeffentlichte Punktzahlen nicht
nebeneinanderlegen: Es gibt inzwischen Fachliteratur mit dem Titel *„Stop
Comparing LLM Agents Without Disclosing the Harness"*. Die 79 % von Flash und
die 68,4 %, die OpenHands mit Claude Opus 4.6 erreichte, stammen aus
verschiedenen Geruesten und sagen nichts ueber „Flash schlaegt Opus".

### Die tatsächlich schwierigen Teile

Die Schleife selbst — Modell rufen, Werkzeug ausfuehren, Ergebnis
zurueckgeben — ist an einem Nachmittag geschrieben. Schwierig ist alles
darum herum:

| Teil | Warum es schwierig ist |
|---|---|
| **Kontextverwaltung** | Der eigentliche Unterschied. Wann wird verdichtet, was bleibt, was fliegt raus. Ein Agent, der sein Fenster vollmuellt, wird ab Minute zehn dumm. |
| **Werkzeugzuschnitt** | Ein Bearbeiten-Werkzeug muss bei unpassender Fundstelle **laut scheitern**, nicht irgendwo hinpatchen. Genau die Klasse Fehler, die wir heute im Auftragsbuch hatten. |
| **Fehlererholung** | Was passiert nach einem fehlgeschlagenen Werkzeugaufruf? Naiv: Endlosschleife. |
| **Abbruchbedingungen** | Wann ist der Agent fertig, wann steckt er fest? |
| **Rechte und Sicherheit** | Shell-Zugriff auf dem Geraet, auf dem auch dein API-Schluessel liegt. |
| **Verifikation** | Der Agent muss pruefen koennen, ob er recht hat. **Voraussetzung dafuer ist ein Pruefbefehl — den hat dieses Projekt seit heute.** |

Der letzte Punkt ist kein Nebensatz. Ohne maschinelles Gate meldet jeder
Agent „fertig", sobald er aufhoert zu tippen.

---

## 3. Was auf deinem Handy tatsächlich läuft

Das ist das entscheidende Auswahlkriterium — und es siebt hart aus.

| Kandidat | Auf Termux/ARM64? | Anmerkung |
|---|---|---|
| **OpenHands** | **Nein** | Braucht Docker fuer die Sandbox; Docker laeuft unter Termux nicht. Nur ueber die Cloud im Browser. |
| **Aider** | **Ja**, mit Haken | Python, git-nativ, automatischer Commit je Schritt. Bei `pip install` gibt es ein aarch64-Wheel-Problem. |
| **opencode-termux** | **Ja** | Ausdruecklich fuer Android/Termux quergebaut (Bun + JSC fuer aarch64). |
| **codex-termux** | **Ja** | Leichtgewichtiger Agent fuer die Termux-Kommandozeile. |
| **droid-harness** | **Ja** | Sammelprojekt: Claude Code, Codex, OpenCode, Aider und lokale Modelle via llama.cpp auf Snapdragon-Geraeten. |
| **Claude Agent SDK** | Technisch ja | Umhuellt die Claude-Code-Kommandozeile als Unterprozess, braucht also Node. **Bindet an ein Claude-Abo** (seit 15.06.2026 eigenes monatliches SDK-Guthaben: 20 $ Pro / 100 $ Max5x / 200 $ Max20x). Passt weder zum OpenRouter-Weg noch zum Souveraenitaetsziel. |

**Der Punkt, der alles aendert:** Alle brauchbaren Kandidaten sind
**Kommandozeilenprogramme**. Damit faellt das Android-Problem ersatzlos weg.
Der Watcher muss keine App aufwecken und keinen Menschen antippen lassen — er
ruft ein Programm auf und liest dessen Ausgabe. Die Luecke zwischen „App ist
offen" und „Agent arbeitet" existiert dann nicht mehr.

---

## 4. Drei Wege, ehrlich bewertet

### Weg A — Kommandozeilen-Agent in Termux anbinden
**Aufwand:** ein Tag. **Risiko:** gering.

Der Watcher holt den Auftrag und uebergibt ihn direkt an den Agenten, statt
eine App zu oeffnen. Rueckmeldung geht ueber die bestehenden Endpunkte
`/status` und `/ergebnis` — die stehen bereits und funktionieren seit heute
auch mit der Kurz-ID.

* **Dafuer:** loest die Autonomie-Luecke vollstaendig; nichts Neues zu bauen;
  DeepSeek V4 Flash ueber OpenRouter bleibt das Modell; sofort ueberpruefbar.
* **Dagegen:** fremdes Werkzeug im kritischen Pfad; Abstimmung auf das eigene
  Modell nur begrenzt moeglich.
* **Offen:** Welcher der drei Termux-Kandidaten auf dem Motorola edge 50
  wirklich laeuft. Das ist eine Messung, keine Diskussion.

### Weg B — Eigenes schlankes Harness im Backend
**Aufwand:** ein bis zwei Wochen bis brauchbar. **Risiko:** mittel.

Eine Auftrags-Schleife im FastAPI-Backend: Werkzeuge fuer Datei lesen,
schreiben, suchen, Shell, git — plus Kontextverdichtung und das Pruefbefehl-Gate.

* **Dafuer:** volle Kontrolle ueber Modell, Kosten, Werkzeuge und Rechte;
  auf DeepSeek V4 Flash abstimmbar, was laut Forschungslage genau der Hebel
  ist; passt zum Souveraenitaetsziel; Hermes faellt ganz aus der Kette.
* **Dagegen:** Kontextverwaltung und Fehlererholung sind die Stellen, an denen
  Eigenbauten ueblicherweise scheitern. Ein Nachmittag reicht fuer die
  Schleife, nicht fuer die Qualitaet.
* **Voraussetzung:** Pruefbefehl — vorhanden seit heute.

### Weg C — Bei Hermes bleiben
**Aufwand:** gering. **Risiko:** die Luecke bleibt.

Der Watcher startet Hermes zuverlaessig (seit heute repariert), aber der
Auftrag muss weiterhin von innen abgeholt werden. Von aussen ist das
nachweislich nicht loesbar — es gibt keinen Intent-Kanal.

* Der einzige denkbare Ausbau: die Sitzung `auftrag-bearbeiter` als
  Dauerlaeufer, der von sich aus pollt. Ob Hermes eine Sitzung wirklich
  autonom schleifen laesst, ist **ungeprueft** und nur in der App selbst
  festzustellen.

---

## 5. Empfehlung

**Weg A zuerst, Weg B als Ziel.**

Begruendung: Weg A macht die Kette in einem Tag vollautomatisch und kostet
nichts an Optionen — die Endpunkte, das Auftragsbuch und der Watcher bleiben
unveraendert. Erst wenn die Kette laeuft, laesst sich ueberhaupt beurteilen,
wie gut ein fremdes Harness mit DeepSeek V4 Flash arbeitet. Diese Messung ist
die Grundlage fuer die Entscheidung ueber Weg B — vorher waere sie geraten.

Was gegen sofortigen Eigenbau spricht, ist nicht der Aufwand, sondern die
Reihenfolge: Ohne Vergleichspunkt weisst du nicht, ob dein Harness gut ist.

### Nächste Schritte

1. Auf dem Handy pruefen, welcher Kandidat laeuft — `opencode-termux` zuerst,
   weil ausdruecklich fuer aarch64 gebaut. **Messung, keine Annahme.**
2. Kleinen Testauftrag durchlaufen lassen und mitschreiben: Wie viele Token,
   wie lange, wie oft richtig?
3. Watcher um einen Aufruf des Agenten erweitern statt `am start`.
4. Erst danach entscheiden, ob Weg B sich lohnt.

---

## Quellen

* [DeepSeek V4 Flash 0423 — Preise und Benchmarks, OpenRouter](https://openrouter.ai/deepseek/deepseek-v4-flash)
* [DeepSeek V4 gewinnt agentischen Token-Anteil, OpenRouter Blog](https://openrouter.ai/blog/insights/deepseek-v4-adoption/)
* [DeepSeek-Nachtraining schlaegt eigenes Spitzenmodell auf neun Agenten-Benchmarks, TechTimes](https://www.techtimes.com/articles/322513/20260731/deepseek-retrained-v4-flash-beats-its-flagship-pro-nine-agent-benchmarks.htm)
* [Warum das Geruest mehr zaehlt als das Modell, MindStudio](https://www.mindstudio.ai/blog/agent-harness-scaffolding-matters-more-than-model)
* [Coding Agent Harness Benchmarks — warum das Harness die Punktzahl aendert, Future AGI](https://futureagi.com/blog/coding-agent-harness-benchmark/)
* [Stop Comparing LLM Agents Without Disclosing the Harness (arXiv)](https://arxiv.org/pdf/2605.23950)
* [Inside the Scaffold — Quelltext-Taxonomie von Coding-Agent-Architekturen (arXiv)](https://arxiv.org/pdf/2604.03515)
* [OpenHands auf dem Telefon betreiben, Cosyra](https://cosyra.com/guides/openhands-on-phone.html)
* [KI-Coding-Agenten auf dem Telefon, Cosyra](https://cosyra.com/guides/ai-coding-agents-mobile.html)
* [opencode-termux (GitHub)](https://github.com/guysoft/opencode-termux)
* [codex-termux (GitHub)](https://github.com/DioNanos/codex-termux)
* [droid-harness (GitHub)](https://github.com/eibragaa/droid-harness)
* [Claude Agent SDK in Python, Augment Code](https://www.augmentcode.com/guides/claude-agent-sdk-python)
* [Verzeichnis terminal-nativer Coding-Agenten (GitHub)](https://github.com/bradAGI/awesome-cli-coding-agents)

---

# Nachtrag: Werkzeugvergleich für Termux (17.08.2026)

Der Abschnitt oben empfahl pauschal „einen Kommandozeilen-Agenten". Diese
Empfehlung war zu grob. Nach genauerer Pruefung faellt die Auswahl deutlich
enger aus — und ein Kriterium fehlte in der ersten Fassung ganz.

## Das übersehene Kriterium

**Der Agent muss sich vom Watcher aufrufen lassen, ohne dass jemand tippt.**

Das ist kein Komfortmerkmal, sondern der ganze Zweck der Uebung. Ein Werkzeug,
das nur im Dialog arbeitet, loest das Problem nicht — es verschiebt es nur von
Hermes auf ein anderes Programm. Genau diese Falle war der Fehler in der
ersten Empfehlung.

## Bewertungsmaßstäbe

| # | Maßstab | Warum er zählt |
|---|---|---|
| 1 | **Nicht-interaktiv aufrufbar** | Ohne das ist alles andere egal |
| 2 | **Laeuft auf Termux/aarch64 ohne Fremd-Fork** | Fremder Nachbau bekommt Shell-Zugriff neben dem API-Schluessel |
| 3 | **Pruefbefehl-Anbindung** | Ohne maschinelles Gate meldet jeder Agent „fertig" |
| 4 | **OpenRouter + DeepSeek V4 Flash** | Bestehendes Konto, bestehende ZDR-Einstellung |
| 5 | **Datenverhalten** | Telemetrie, lokale Ablage |
| 6 | **Rueckholbarkeit** | Der Agent arbeitet unbeaufsichtigt im Repo |

## Vergleich

| | **Aider** | **Codex CLI** | **OpenCode** | **Goose** | **Eigenbau** |
|---|---|---|---|---|---|
| Nicht-interaktiv | `--message` + `--yes-always` ✅ | `codex exec` ✅ | ✅ | Rezepte, CI-tauglich ✅ | nach Bauart ✅ |
| Termux ohne Fork | **ja, Originalpaket** ✅ | **nein** ❌ offizielles Paket bricht mit `Unknown platform: android` | **nein** ❌ braucht Bun (fehlt), Portierung noetig | **nein** ❌ keine Android-Binaries, offener Wunsch im Projekt | entfaellt ✅ |
| Pruefbefehl | **`--auto-test --test-cmd`** ✅✅ behebt Testfehler selbst | ueber Prompt | ueber Prompt | ueber Rezept | selbst zu bauen |
| OpenRouter | `openrouter/deepseek/deepseek-v4-flash` ✅ | `config.toml`, `wire_api="responses"` ✅ | ✅ | 400+ Modelle ✅ | ✅ |
| Telemetrie | `--no-analytics` ✅ | **an OpenAI, standardmaessig an** ⚠️ | unklar | unklar | keine ✅ |
| Lokale Ablage | schlank | Sitzungslogs bis **700 MB–2 GB** ⚠️ | — | — | selbst bestimmt |
| Rueckholbarkeit | **git-nativ, Commit je Schritt** ✅✅ | manuell | manuell | manuell | selbst zu bauen |
| Aufwand | Installationsgefummel | npm, sofort | Bun nachruesten | `cargo build` auf dem Telefon | 1–2 Wochen |

**Nicht weiter betrachtet:** Gemini CLI (Datenverhalten passt nicht zum
Souveraenitaetsziel), Claude Code / Agent SDK (bindet an ein Claude-Abo mit
eigenem Guthaben, 20–200 $/Monat), OpenHands (braucht Docker, laeuft unter
Termux nicht), Cline (Editor-Erweiterung, keine Kommandozeile).

## Ergebnis: Aider

Aider gewinnt nicht knapp, sondern auf den beiden Maßstaeben, die hier zaehlen:

**Es ist das Originalprojekt.** Alle anderen brauchbaren Kandidaten erfordern
auf Termux einen Nachbau von Privatpersonen — mit Shell-Zugriff auf dem Geraet,
auf dem der API-Schluessel liegt, teils mit ausgetauschter TLS-Pruefung. Aider
kommt per `pip` vom Projekt selbst.

**Es schliesst den Kreis zum Pruefbefehl.** `--auto-test --test-cmd` laesst den
Agenten die Tests laufen und Fehlschlaege selbst beheben. Das ist genau das
Gate, das dieses Projekt seit heute hat — und der Unterschied zwischen einem
Agenten, der behauptet fertig zu sein, und einem, der es belegt.

Dazu: git-nativ mit einem Commit je Schritt. Bei einem Agenten, der
unbeaufsichtigt im Repo arbeitet, ist das die wichtigste Sicherheitsleine —
jeder Schritt einzeln ruecknehmbar.

### Der ehrliche Haken

Die Installation ist nicht geschenkt. Bekannte Huerden auf Termux:

* `jiter` (Abhaengigkeit von `openai`) braucht maturin/Rust zum Uebersetzen —
  `rustc` und `cargo` sind vorhanden, `pkg install binutils` wird zusaetzlich
  gebraucht.
* tree-sitter: ueber `pkg install libtreesitter` verfuegbar, laeuft auf aarch64.
* Playwright hat keine Android-Wheels — betrifft nur die optionale
  Web-Funktion, nicht das Programmieren.

Python 3.13.13 ist frisch, fehlende Wheels sind also wahrscheinlich. Mit
`clang`, `make`, `rustc` und `cargo` ist der Selbstbau moeglich, kostet aber
Zeit.

**Das ist eine Messung, keine Diskussion:** Installationsversuch mit fester
Zeitgrenze. Klappt er, ist die Sache entschieden. Klappt er nicht, ist der
Codex-Fork der Rueckfallweg — dann aber mit offenen Augen, was das
Vertrauensmodell angeht.

## Quellen des Nachtrags

* [Scripting aider — `--message`, Automatisierung](https://aider.chat/docs/scripting.html)
* [aider mit OpenRouter](https://aider.chat/docs/llms/openrouter.html)
* [Headless-Nutzung `--message` + `--auto-test` (Aider-AI/aider #4923)](https://github.com/Aider-AI/aider/issues/4923)
* [Offizielles Codex-Paket scheitert auf Termux (openai/codex #2951)](https://github.com/openai/codex/issues/2951)
* [Codex CLI mit OpenRouter — config.toml](https://openrouter.ai/blog/tutorials/codex-cli-openrouter/)
* [Codex-Sitzungslogs wachsen auf 700 MB–2 GB (openai/codex #24948)](https://github.com/openai/codex/issues/24948)
* [Goose: Termux/aarch64-Unterstuetzung offen (#6592)](https://github.com/aaif-goose/goose/issues/6592)
* [OpenCode: Android-aarch64-Binaries offen (#11689)](https://github.com/anomalyco/opencode/issues/11689)
* [Playwright unterstuetzt Android nicht (microsoft/playwright #6105)](https://github.com/microsoft/playwright/issues/6105)

---

# Nachtrag 2: Der Installationsversuch — gemessen statt vermutet (17.08.2026)

Der Vergleich oben empfahl Aider. **Diese Empfehlung ist widerlegt.** Der
Versuch am Geraet (Motorola edge 50, Termux googleplay.2026.06.21) hat jeden
Kandidaten durchfallen lassen, der ohne Fremd-Nachbau auskommt. Die Gruende
sind technisch eindeutig und im Folgenden festgehalten, damit sie niemand
noch einmal herausfinden muss.

## Aider — gescheitert an Python 3.13

```
Neueste Fassung   : aider-chat 0.86.2
Python-Anforderung: <3.13,>=3.10
```

Termux liefert ausschliesslich **Python 3.13.13**; aeltere Fassungen gibt es
im Repo nicht (geprueft: 3.10, 3.11, 3.12 — alle nicht vorhanden). Pip hat
deshalb korrekt alle 174 modernen Fassungen aussortiert und ist bis 0.16.0
von 2023 zurueckgelaufen, aus der Zeit vor solchen Angaben. Deren gepinntes
`numpy==1.24.3` baut auf 3.13 nicht:

```
AttributeError: module 'pkgutil' has no attribute 'ImpImporter'
ERROR: Failed to build 'numpy' when getting requirements to build wheel
```

`uv` ist im Termux-Repo verfuegbar und wurde als Ausweg geprueft — es kann
aber kein Python 3.12 fuer Android liefern:

```
error: No download found for request: cpython-3.12-linux-aarch64-none
```

Es gibt schlicht keine Android-Fassungen bei python-build-standalone. Bliebe,
Python 3.12 aus dem Quelltext zu bauen: Stunden Arbeit fuer einen wackligen
Unterbau, auf dem dann unbeaufsichtigt ein Agent laufen soll. Nicht sinnvoll.

## Offizielles Codex — gescheitert an Bionic

Das npm-Paket `@openai/codex` 0.147.0 liefert Plattform-Pakete fuer
linux-x64/arm64, win32 und darwin. Kein Android — aber die linux-arm64-Fassung
enthaelt **`aarch64-unknown-linux-musl`**-Binaerdateien, was zunaechst
vielversprechend aussah. Der Ausfuehrungsversuch:

```
codex: has unexpected e_type: 2
rg:    executable's TLS segment is underaligned: alignment is 8,
       needs to be at least 64 for ARM64 Bionic
```

`e_type: 2` ist ET_EXEC — statisch gelinkt, aber **ohne Positionsunabhaengigkeit**.
Android verlangt seit Version 5 zwingend PIE und weist das ab. Das mitgelieferte
ripgrep scheitert zusaetzlich an Bionics TLS-Ausrichtung.

Beides sind musl-gegen-Bionic-Konflikte. **Damit ist auch belegt, warum die
Gemeinschafts-Portierungen existieren:** Sie bauen gegen `aarch64-linux-android`
neu. Das ist technisch notwendig, kein Selbstzweck.

## OpenCode und Goose — gescheitert an fehlenden Binärdateien

`bun` ist nicht im Termux-Repo (geprueft), OpenCode braucht es. Goose hat keine
Android-Binaerdateien, nur einen offenen Wunsch im Projekt.

## Ergebnis: Weg A ist tot, Weg B ist der Weg

| Kandidat | Ergebnis | Ursache |
|---|---|---|
| Aider | ❌ | Python <3.13 gefordert, Termux hat nur 3.13, kein Android-3.12 beschaffbar |
| Codex offiziell | ❌ | musl-Binaerdatei ist non-PIE, Bionic weist ab |
| Codex-Portierung | ✅ technisch | fremder Nachbau mit Shell-Zugriff neben dem API-Schluessel |
| OpenCode | ❌ | Bun fehlt im Repo |
| Goose | ❌ | keine Android-Binaerdateien |
| **Eigenes Harness** | ✅ | Python 3.13 laeuft, Backend steht bereits |

**Die Voraussetzung von Weg A war „schnell etwas Fertiges uebernehmen". Diese
Voraussetzung ist am Geraet gescheitert.** Uebrig bleibt entweder ein
Fremd-Nachbau mit Vertrauensfrage oder der Eigenbau.

Fuer den Eigenbau spricht nach dieser Messung mehr als vorher:

* **Python 3.13 ist kein Hindernis** — nur fremde Projekte hinken hinterher.
  Eigener Code laeuft.
* **Der halbe Weg steht schon:** OpenRouter-Anbindung, Auftragsbuch,
  Rueckmelde-Endpunkte, und seit heute ein Pruefbefehl.
* **Kein fremdes Programm** bekommt Shell-Zugriff neben dem API-Schluessel.
* **Volle Kontrolle** ueber Modell, Kosten und Werkzeuge — passt zum
  Souveraenitaetsziel.

### Was am Gerät zurückblieb

Aufgeraeumt: `~/aider-venv` (21 MB) und der Codex-Test (373 MB) sind geloescht.
Absichtlich behalten: `uv` und `binutils` — beide nuetzlich, per
`pkg uninstall` entfernbar.
