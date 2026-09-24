# Primärquellen: Was Anthropic selbst über den Bau von Agenten schreibt

**Erstellt:** 2026-09-24 · **Autor:** Hermes (Subagent Recherche)
**Zweck:** Die offiziellen Anthropic-Engineering-Quellen zum Agenten-Bau als Zitat-Fundus auswerten — für unser Agentic-Engineering-Setup (Workspace `agentic engineering`).

## Legende

- **Anthropic-Aussage** = wörtliches Zitat aus der jeweiligen Quelle (englisch, mit deutscher Übersetzung). Zitate sind exakt übernommen, Kürzungen sind mit `[…]` markiert.
- **Einordnung** = meine Interpretation/Übertragung. *Nicht* von Anthropic. Von deren Aussage klar getrennt.

## Methode

Alle fünf Seiten wurden als Volltext geladen (Anthropic-Engineering-Seiten: HTML-Artikelinhalt extrahiert; Claude-Code-Doku: Mintlify-Rohmarkdown über `…/best-practices.md`). Es wurden keine Suchmaschinen-Snippets oder Sekundärquellen verwendet. Alle Seiten am 2026-09-24 abgerufen. Publikationsdaten wurden im HTML der Seiten verifiziert.

---

## 1. Building effective agents

- **URL:** https://www.anthropic.com/engineering/building-effective-agents
- **Publikation:** 19. Dezember 2024 (im HTML verifiziert). **Hinweis im Artikel selbst:** „Much of the tooling landscape described in this post has changed since December 2024“ — Anthropic verweist für den aktuellen Ansatz auf „Claude Managed Agents“ (https://www.anthropic.com/engineering/managed-agents). Die Architektur-Prinzipien unten sind davon unberührt, die Tooling-Landschaft ist es nicht.

### Konkrete Empfehlungen

1. **Einfachstes mögliches Muster zuerst, Komplexität nur bei nachgewiesenem Mehrwert.** Nicht automatisch „Agent“ bauen; für viele Anwendungen genügt ein optimierter einzelner LLM-Call mit Retrieval und In-Context-Beispielen.
   > “When building applications with LLMs, we recommend finding the simplest solution possible, and only increasing complexity when needed. This might mean not building agentic systems at all.” — [building-effective-agents, „When (and when not) to use agents“]
2. **Fünf benannte Workflow-Muster statt Framework-Blackbox:** Prompt Chaining (mit programmatischem „Gate“ zwischen Schritten), Routing (einfache Anfragen an billigere Modelle, schwere an fähigere), Parallelisierung (Sectioning = unabhängige Subtasks parallel; Voting = denselben Task mehrfach für Konfidenz), Orchestrator-Workers (Zerlegung erst zur Laufzeit, wenn Subtasks nicht vorhersagbar sind), Evaluator-Optimizer (ein LLM generiert, ein zweites bewertet in Schleife — „effective when we have clear evaluation criteria“).
3. **Drei Kernprinzipien für Agenten-Implementierung:**
   > “Maintain simplicity in your agent's design. Prioritize transparency by explicitly showing the agent’s planning steps. Carefully craft your agent-computer interface (ACI) through thorough tool documentation and testing.” — [building-effective-agents, „Summary“]
4. **Ground Truth aus der Umgebung in jeder Runde + Guardrails und Stop-Bedingungen.**
   > “During execution, it's crucial for the agents to gain “ground truth” from the environment at each step (such as tool call results or code execution) to assess its progress.” — [building-effective-agents, „Agents“]
   Ergänzend dort: Checkpoints für Human-Feedback, Abbruchbedingungen (z. B. maximale Iterationen), und: “We recommend extensive testing in sandboxed environments, along with the appropriate guardrails.”
5. **ACI/Tool-Design ist so wichtig wie der Prompt selbst.** Format wählen, das nah an natürlich vorkommendem Text liegt, ohne Format-Overhead (kein Diff-Buchhalten, kein JSON-Escaping); Tool-Beschreibung wie eine gute Docstring für einen Junior-Entwickler schreiben; Fehlbenutzung durch Parametergestaltung erschweren („Poka-yoke your tools“); Tools mit Beispielen testen.
   > “While building our agent for SWE-bench, we actually spent more time optimizing our tools than the overall prompt.” — [building-effective-agents, „Appendix 2“]
   Konkretes Beispiel dort: relative Pfade führten zu Fehlern → Tool verlangt seitdem **absolute Pfade**, danach fehlerfrei.

**Einordnung:** Punkt 5 ist der Ahnherr unseres „Prüfbefehl-Gates“: Das Umgebungs-Feedback (Testlauf, Exit-Code) ist bei Anthropic explizit als Ground-Truth-Quelle für den Agenten-Loop vorgesehen — nicht nur als nachträgliche Menschen-Kontrolle.

---

## 2. Effective context engineering for AI agents

- **URL:** https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- **Publikation:** 29. September 2025 (im HTML verifiziert; Applied-AI-Team um Prithvi Rajasekaran).

### Konkrete Empfehlungen

1. **Kontext als endliche Ressource behandeln („Attention Budget“, „Context Rot“).** Mit steigender Tokenzahl sinkt die Treffsicherheit der Erinnerung — über alle Modelle hinweg ein Performance-Gradient, keine harte Klippe.
   > “Context, therefore, must be treated as a finite resource with diminishing marginal returns.” — [effective-context-engineering, „Why context engineering is important…“]
   Leitsatz des ganzen Artikels: “find the smallest possible set of high-signal tokens that maximize the likelihood of some desired outcome.”
2. **System-Prompt: richtige „Altitude“ treffen und strukturieren.** Zwei Fehlermodi vermeiden: brittles if-else-Hardcoding (fragil, teuer zu pflegen) vs. vage Hochglanz-Anweisungen ohne konkrete Signale. Struktur-Empfehlung:
   > “We recommend organizing prompts into distinct sections […] and using techniques like XML tagging or Markdown headers to delineate these sections […]” — [ebd., „The anatomy of effective context“]
   (Im Original genannt als Beispiel-Sektionen: `background_information`, `instructions`, `Tool guidance`, `Output description`.)
   Minimal starten, dann gezielt anhand beobachteter Fehlermodi ergänzen; „minimal“ heißt nicht „kurz“.
3. **Tool-Sets minimal und überlappingsfrei halten.** Selbstverständlichkeiten, Robustheit und klare Nutzungsgrenzen wie bei gut designtem Code; desambiguierte Parameter; Input-Parameter sollen die Stärken des Modells bedienen.
   > “If a human engineer can’t definitively say which tool should be used in a given situation, an AI agent can’t be expected to do better.” — [ebd.]
   (Anthropic nennt „bloated tool sets“ als häufigsten Fehlermodus.)
4. **Few-Shot: kuratierte kanonische Beispiele statt Edge-Case-Wäschelisten.**
   > “Instead, we recommend working to curate a set of diverse, canonical examples that effectively portray the expected behavior of the agent. For an LLM, examples are the “pictures” worth a thousand words.” — [ebd.]
5. **Just-in-Time-Retrieval statt Vorab-Laden, wo möglich (hybrid erlaubt).** Leichte Referenzen (Dateipfade, gespeicherte Queries, Links) im Kontext halten und Daten zur Laufzeit per Tool nachladen; Claude Code macht genau das hybrid: CLAUDE.md wird vorab geladen, glob/grep holen Dateien just-in-time.
   > “Rather than pre-processing all relevant data up front, agents built with the “just in time” approach maintain lightweight identifiers (file paths, stored queries, web links, etc.) and use these references to dynamically load data into context at runtime using tools.” — [ebd., „Context retrieval and agentic search“]
6. **Für Langhorizont-Aufgaben drei Techniken — Compaction, Structured Note-Taking, Subagenten.** Compaction: bei drohendem Limit zusammenfassen und mit Zusammenfassung neu starten; in Claude Code bleiben „architectural decisions, unresolved bugs, and implementation details“ erhalten, redundante Tool-Ausgaben fallen weg. Prompt-Tuning-Reihenfolge laut Anthropic: **erst Recall maximieren, dann Präzision erhöhen**; leichteste Form ist Tool-Result-Clearing. Note-Taking: Notizen (To-do-Liste, NOTES.md) außerhalb des Kontexts persistieren und später zurückladen.
   > “Each subagent might explore extensively, using tens of thousands of tokens or more, but returns only a condensed, distilled summary of its work (often 1,000-2,000 tokens).” — [ebd., „Sub-agent architectures“]
   Auswahlregel dort: Compaction = Dialogfluss; Note-Taking = iterative Entwicklung mit Meilensteinen; Multi-Agent = parallele Exploration/Suche.

**Einordnung:** Punkt 1 erklärt, *warum* unser Prüfbefehl-Gate und die Regel „Kontext-Hygiene ab ~60 %“ zusammenpassen: Anthropic begründet Kontextdruck architektonisch (n²-Attention-Beziehungen), nicht als Tool-Schwäche. Punkt 5 stützt „Doku folgt dem Code“: CLAUDE.md/AGENTS.md als Vorab-Kontext funktioniert nur, wenn er klein und aktuell ist — sonst wird er von glob/grep-JIT-Retrieval überstimmt.

---

## 3. Best practices for Claude Code (offizielle Doku)

- **URL:** https://docs.claude.com/en/docs/claude-code/best-practices (Rohmarkdown: `…/best-practices.md`)
- **Art:** lebende Dokumentation (kein Publikationsdatum); Stand des Abrufs: 2026-09-24. Fasst zusammen, was „across Anthropic's internal teams“ funktioniert.

### Konkrete Empfehlungen

1. **Die eine Constraint, auf der fast alles basiert: das Kontextfenster.**
   > “Most best practices are based on one constraint: Claude's context window fills up fast, and performance degrades as it fills.” — [best-practices, Einleitung]
2. **Verifikation ist Pflicht — Claude braucht etwas, das Pass/Fail liefert.** Vier Eskalationsstufen: (a) im Prompt ausführen lassen („run the tests after implementing“), (b) als `/goal`-Bedingung überprüfen lassen, (c) als deterministisches Gate per **Stop-Hook** (blockiert Turn-Ende, bis der Check besteht), (d) als Verifikations-Subagent („a fresh model try to refute the result, so the agent doing the work isn't the one grading it“).
   > “Give Claude a check it can run: tests, a build, a screenshot to compare. It's the difference between a session you watch and one you walk away from.” — [best-practices, „Give Claude a way to verify its work“]
   Zusätzlich: Evidenz statt Behauptung zeigen lassen (“the test output, the command it ran and what it returned”). Und im Fehlerfall-Tabelle: “address the root cause, don't suppress the error”.
3. **Explore → Plan → Implement → Commit als Vier-Phasen-Workflow („plan mode“).**
   > “Separate research and planning from implementation to avoid solving the wrong problem.” — [best-practices, „Explore first, then plan, then code“]
   Wann *nicht* planen: „If you could describe the diff in one sentence, skip the plan.“ Plan editierbar machen (`Ctrl+G`) und gegen den Plan implementieren.
4. **CLAUDE.md radikal kurz halten; Hooks für Nicht-Verhandelbares.**
   > “Keep it concise. For each line, ask: *"Would removing this cause Claude to make mistakes?"* If not, cut it. Bloated CLAUDE.md files cause Claude to ignore your actual instructions!” — [best-practices, „Write an effective CLAUDE.md“]
   > “Unlike CLAUDE.md instructions which are advisory, hooks are deterministic and guarantee the action happens.” — [best-practices, „Set up hooks“]
   Für Domänenwissen, das nur manchmal gilt: Skills statt CLAUDE.md („Claude loads them on demand without bloating every conversation“). CLAUDE.md wie Code behandeln: reviewen, regelmäßig beschneiden, ins Git einchecken.
5. **Adversarial Review im frischen Kontext — aber findings-fokussiert zügeln.**
   > “A fresh context improves code review since Claude won't be biased toward code it just wrote.” — [best-practices, „Run multiple Claude sessions“]
   Reviewer-Anweisung nennt Umfang, Plan und Findings-Definition; Gegen-Warnung: “A reviewer prompted to find gaps will usually report some, even when the work is sound, because that is what it was asked to do.” → Nur Findings melden lassen, die Korrektheit oder Anforderungen betreffen; Rest optional (sonst Over-Engineering).
6. **Parallelisierung & Isolation als Skalierungsweg:** separate CLI-Sessions in isolierten Git-Worktrees (“run separate CLI sessions in isolated git checkouts so edits don't collide”); Writer/Reviewer-Pattern (eine Session schreibt, eine frisch reviewt); Fan-out per `claude -p`-Schleife mit `--allowedTools`; `/batch` verteilt eine Migration auf 5–30 Subagenten, jeder im eigenen Worktree mit eigenem PR.
7. **Fünf benannte Fehlermuster mit Fix:** (a) „kitchen sink session“ → `/clear` zwischen unverbundenen Tasks; (b) „correcting over and over“ → nach **zwei** fehlgeschlagenen Korrekturen `/clear` + besserer Prompt; (c) „over-specified CLAUDE.md“ → radikal kürzen oder in Hook umwandeln; (d) „trust-then-verify gap“ → “If you can't verify it, don't ship it”; (e) „infinite exploration“ → Recherche eng scopen oder in Subagenten auslagern.

**Einordnung:** Das ist die Praxis-Version derselben Prinzipien aus Quelle 1 und 2: „Explore/Plan/Implement“ = Trennung von Recherche und Umsetzung; „Verifikation“ = Prüfbefehl-Gate mit vier Härtungsstufen; Worktrees + Writer/Reviewer = Rollen-Trennung Planer/Worker/Prüfer mit Isolation. Die Aussage, dass Reviewer im frischen Kontext ohne Bias besser reviewen, deckt sich mit unserem „Prüfer darf nicht der Autor sein“ — und die Over-Engineering-Warnung ist die Ergänzung, die wir bisher nicht hatten: Findings müssen gegen Korrektheit gefiltert werden.

---

## 4. Writing effective tools for agents — with agents

- **URL:** https://www.anthropic.com/engineering/writing-tools-for-agents
- **Publikation:** 11. September 2025 (im HTML verifiziert).

### Konkrete Empfehlungen

1. **Tools sind ein Vertrag zwischen deterministischem System und nicht-deterministischem Agenten — für Agenten designen, nicht wie APIs.**
   > “[…] instead of writing tools and MCP servers the way we’d write functions and APIs for other developers or systems, we need to design them for agents.” — [writing-tools, „What is a tool?“]
2. **Wenige, konsolidierte Tools entlang realer Workflows statt dünner API-Wrapper.** Gegenbeispiele von Anthropic: `list_contacts` → besser `search_contacts`/`message_contact`; statt `list_users`+`list_events`+`create_event` besser ein `schedule_event`; statt `read_logs` besser `search_logs`; statt drei Kunden-Lookup-Tools ein `get_customer_context`.
   > “We recommend building a few thoughtful tools targeting specific high-impact workflows, which match your evaluation tasks and scaling up from there.” — [writing-tools, „Choosing the right tools for agents“]
3. **Tool-Antworten: hochsignalarm, token-effizient, keine Low-Level-IDs.** Semantische Namen statt UUIDs („significantly improves Claude's precision in retrieval tasks by reducing hallucinations“); `ResponseFormat`-Enum `concise`/`detailed` je Bedarf; Antworten deckeln per Pagination, Range, Filter, Truncation.
   > “For Claude Code, we restrict tool responses to 25,000 tokens by default.” — [writing-tools, „Optimizing tool responses for token efficiency“]
4. **Fehler- und Truncation-Meldungen sind Prompt-Engineering-Fläche, kein Logging.**
   > “[…] you can prompt-engineer your error responses to clearly communicate specific and actionable improvements, rather than opaque error codes or tracebacks.” — [ebd.]
5. **Tool-Beschreibungen prompt-engineeren, als schriebe man für einen neuen Kollegen.** Erwartete Inputs/Outputs strikt definieren und mit Datenmodellen erzwingen; Parameter eindeutig benennen (`user_id` statt `user`).
   > “Claude Sonnet 3.5 achieved state-of-the-art performance on the SWE-bench Verified evaluation after we made precise refinements to tool descriptions, dramatically reducing error rates and improving task completion.” — [writing-tools, „Prompt-engineering your tool descriptions“]
6. **Evaluationen sind der Hebel: Held-out-Testsets, realistische Daten, Verifikation, Metriken, Agenten als Tool-Optimierer.** Start: schneller Prototyp + lokaler MCP-Server/Claude Code zum Testen. Eval-Tasks aus echten Workflows, mehrere Tool-Calls pro Task möglich („Strong evaluation tasks might require multiple tool calls—potentially dozens“), nicht zu simple Sandboxen. Metriken: Genauigkeit, Laufzeit, Tool-Call-Anzahl, Tokenverbrauch, Tool-Fehler. Transkripte zum Optimieren in Claude Code einfüttern; Held-out-Set schützt vor Overfitting („We relied on held-out test sets to ensure we did not overfit“).

**Einordnung:** Punkt 2/5 sind die beste Begründung, warum unser Prinzip „Baseline messen vor Tool-Bau“ richtig liegt: Anthropic behandelt Tool-Verbesserung als Eval-getriebenen Iterationsprozess mit ausdrücklich kleinen Startproben (siehe auch Quelle 5: ~20 Queries). Punkt 3 schlägt sich in unserem Setup als Standard nieder: Tool-Antworten kürzen/truncaten statt alles in den Kontext zu kippen.

---

## 5. How we built our multi-agent research system

- **URL:** https://www.anthropic.com/engineering/multi-agent-research-system
- **Publikation:** 13. Juni 2025 (im HTML verifiziert). Erfahrungsbericht der „Research“-Funktion (Orchestrator-Worker: LeadResearcher + parallele Subagenten + CitationAgent).

### Konkrete Empfehlungen

1. **Multi-Agent nur bei echtem Parallelisierungsgewinn — mit klaren Zahlen.**
   > “Our internal evaluations show that multi-agent research systems excel especially for breadth-first queries that involve pursuing multiple independent directions simultaneously. We found that a multi-agent system with Claude Opus 4 as the lead agent and Claude Sonnet 4 subagents outperformed single-agent Claude Opus 4 by 90.2% on our internal research eval.” — [multi-agent-research-system, „Benefits of a multi-agent system“]
   Kosten-Seite:
   > “[…] agents typically use about 4× more tokens than chat interactions, and multi-agent systems use about 15× more tokens than chats.” — [ebd.]
   Coding-Tasks seien dagegen oft *weniger* parallelisierbar; Multi-Agent lohne sich bei „heavy parallelization, information that exceeds single context windows, and interfacing with numerous complex tools“.
2. **Delegations-Prompts mit vollständigem Auftrag; Effort skalieren, nicht raten lassen.** Jeder Subagent braucht „an objective, an output format, guidance on the tools and sources to use, and clear task boundaries“ — sonst Duplikate und Lücken (Beispiel im Artikel: zwei Subagenten durchsuchten doppelt dasselbe). Skalierungsregeln direkt in den Prompt:
   > “Simple fact-finding requires just 1 agent with 3-10 tool calls, direct comparisons might need 2-4 subagents with 10-15 calls each, and complex research might use more than 10 subagents with clearly divided responsibilities.” — [ebd., „Prompt engineering and evaluations for research agents“]
3. **Prompting als Heuristik-Framework: erst breit, dann eng; Thinking als steuerbares Scratchpad; Paralleltools.** Breite kurze Queries zuerst, dann verengen. Extended Thinking für den Lead (Planung, Tool-Wahl, Subagenten-Anzahl), Interleaved Thinking bei Subagenten nach Tool-Ergebnissen (Qualität prüfen, Lücken finden, nächste Query schärfen). Parallelität: 3–5 Subagenten parallel, Subagenten mit 3+ Tools parallel — „cut research time by up to 90% for complex queries“.
4. **Agenten eigene Tools verbessern lassen (Tool-Testing-Agent mit messbarem Effekt).**
   > “This process for improving tool ergonomics resulted in a 40% decrease in task completion time for future agents using the new description, because they were able to avoid most mistakes.” — [ebd.]
   Auch das Prompts-Optimieren selbst: „We found that the Claude 4 models can be excellent prompt engineers.“
5. **Evaluation: früh klein anfangen, LLM-Judge mit Rubrik, Human-Check behalten.** Start mit ~20 echten Beispiel-Queries statt auf große Evals zu warten; LLM-as-Judge mit Rubrik (factual accuracy, citation accuracy, completeness, source quality, tool efficiency) — am konsistentesten: ein Judge-Call mit Score 0.0–1.0 + Pass/Fail; Human-Eval fängt, was Automatisierung übersieht (bei Anthropic: Bias zu SEO-Content-Farmen, gefixt per Source-Quality-Heuristik). Für Agenten, die Zustand verändern: **End-State-Evaluation** statt Turn-für-Turn-Prüfung.
6. **Produktions-Lektionen: Fehler compounden, Resume statt Restart, deterministische Sicherungen, Rainbow-Deployments, Tracing.**
   > “[…] we built systems that can resume from where the agent was when the errors occurred. We also use the model’s intelligence to handle issues gracefully: for instance, letting the agent know when a tool is failing and letting it adapt works surprisingly well. We combine the adaptability of AI agents built on Claude with deterministic safeguards like retry logic and regular checkpoints.” — [ebd., „Production reliability and engineering challenges“]
   Und im Appendix (Subagenten → Dateisystem): “[…] implement artifact systems where specialized agents can create outputs that persist independently […] then pass lightweight references back to the coordinator.” — verhindert Informationsverlust, statt alles durch den Lead zu schleusen („game of telephone“).

**Einordnung:** Die 90 %-Zahl ist an Anthropics interne Research-Eval gebunden — kein universeller Agenten-Benchmark. Übertragbar auf unser Setup sind die *Mechanismen*: explizite Effort-Budgets im Delegations-Prompt, End-State-Evaluation für verändernde Agenten, Artefakte statt Konversations-Weiterreichung (deckt sich mit unserer „Übergabe/Changelog“-Regel), und deterministische Sicherungen (Prüfbefehl, Retry) *kombiniert* mit Modell-Adaptivität.

---

## 6. Querschnitt: was über alle fünf Quellen hinweg konstant empfohlen wird

Nur Punkte, die in **mehreren** der fünf Quellen direkt belegt sind:

| Empfehlung | Belege in |
|---|---|
| Einfachstes Muster wählen; Komplexität nur bei messbarem Mehrwert (Framework-Minimalismus) | 1, 3, 5 |
| Kontext ist die knappe Ressource; kuratieren statt anhäufen („high-signal tokens“) | 2, 3, 4 |
| Verifikation durch ausführbare Checks (Tests/Exit-Code/Evidenz) als Agenten-Feedback | 1, 3, 5 |
| Tool-Design ≈ so wichtig wie Prompts; klare, überlappungsfreie Tool-Grenzen | 1, 2, 4, 5 |
| Rollen-/Kontext-Trennung: Recherche bzw. Prüfung in frischen Kontexten (Subagenten) | 2, 3, 5 |
| Evaluationsgetrieben iterieren (erst klein/stichprobenartig, Held-out, Metriken) | 4, 5 |
| Delegations-Prompts brauchen Ziel, Format, Werkzeuge, Grenzen — sonst Duplikate | 5 (explizit), 3 (Reviewer-Prompts) |

## 7. Abgleich mit unseren 69 Praxisregeln (Einordnung)

**Einordnung — kein Anthropic-Zitat.** Mapping auf die im Auftrag genannten Regel-Muster:

- **Rollen-Trennung Planer/Worker/Prüfer:** Anthropic stützt das dreifach — Evaluator-Optimizer (Quelle 1), Adversarial Review im frischen Subagenten-Kontext (Quelle 3: „because the agent doing the work isn't the one grading it“), Evolution „Writer/Reviewer“ mit zwei Sessions (Quelle 3). Neu aus Quelle 3: Reviewer nur Findings gegen Korrektheit/Anforderungen berichten lassen, sonst Review-Over-Engineering.
- **Worktree-Isolation:** Quelle 3 nennt Git-Worktrees als Standard für parallele Sessions und `/batch` (jeder der 5–30 Subagenten im eigenen Worktree mit eigenem PR). Quelle 2 begründet es kontextseitig: isolierte Kontexte pro Subagent.
- **TDD-Gate / „Fertig ist, was verifiziert ist“:** Quelle 3 liefert die schärfste Formulierung: „a test suite, a build exit code, a linter […]“ als Check, Eskalationsstufen Prompt → `/goal` → Stop-Hook → Verifikations-Subagent; „If you can't verify it, don't ship it.“ Quelle 1 ergänzt: Ground Truth vom Environment in jeder Runde.
- **Scope-Treue:** Quelle 3, „Scope the task“ (Datei, Szenario, Testpräferenz nennen), sowie die Reviewer-Anweisung „nothing outside the task's scope changed“ (Quelle 3) und die Abgrenzung „clear task boundaries“ pro Subagent (Quelle 5).
- **Baseline-Messung:** Quelle 4 und 5 konvergieren: Eval mit realistischen Aufgaben, ~20 Fälle als Start (Quelle 5), Held-out-Testset gegen Overfitting (Quelle 4), Metriken auch jenseits Accuracy (Laufzeit, Tool-Calls, Token, Fehler).

Was wir aus Anthropic-Sicht **ergänzen** sollten (Einordnung): (a) Kontextdruck ist architektonisch begründet — die 60 %-Hygieneschwelle ist plausibel, aber kein Anthropic-Wert; (b) Prompt-Recall-vor-Präzision bei Compaction (Quelle 2) als konkrete Tuning-Reihenfolge; (c) „Tool-Result-Clearing“ als leichteste Kontext-Sparmaßnahme; (d) Truncation/Fehlertexte als Prompt-Fläche, nicht Logging.

## 8. Quellenverzeichnis

1. Anthropic Engineering — *Building effective agents* (19.12.2024). https://www.anthropic.com/engineering/building-effective-agents — enthält den Hinweis auf den Nachfolge-Ansatz: https://www.anthropic.com/engineering/managed-agents
2. Anthropic Engineering — *Effective context engineering for AI agents* (29.09.2025). https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
3. Anthropic Docs — *Best practices for Claude Code* (lebende Doku, abgerufen 24.09.2026). https://docs.claude.com/en/docs/claude-code/best-practices (Rohmarkdown: https://docs.claude.com/en/docs/claude-code/best-practices.md)
4. Anthropic Engineering — *Writing effective tools for agents — with agents* (11.09.2025). https://www.anthropic.com/engineering/writing-tools-for-agents
5. Anthropic Engineering — *How we built our multi-agent research system* (13.06.2025). https://www.anthropic.com/engineering/multi-agent-research-system
