# Primärquellen: Was OpenAI selbst über Agenten-Bau und Codex schreibt

**Stand:** 24.09.2026 · **Zweck:** Offizielle OpenAI-Quellen zu Agenten-Bau, Codex und
Agentic Engineering auswerten — als Ergänzung/Abgleich zu den 69 Praxisregeln aus
YouTube-Videos. Nur Quellen mit URL; OpenAI-Aussage und eigene Einordnung sind
getrennt gekennzeichnet. Zitate sind wörtlich (englisch, wie im Original).

**Hinweis zur Quellenlage (beobachtet am 24.09.2026):** Die Doku ist teilweise von
`platform.openai.com/docs` bzw. `cookbook.openai.com` auf `developers.openai.com`
umgezogen; `learn.chatgpt.com/docs` ist der ChatGPT/Codex-Einstieg und liefert zu
jeder Seite eine Markdown-Fassung (`.md` an die URL anhängen). Das offizielle
AGENTS.md-Format wird unter <https://agents.md> referenziert (verlinkt aus der
AGENTS.md-Anleitung).

---

## 1. ChatGPT/Codex-Doku-Hub: learn.chatgpt.com/docs

URL: <https://learn.chatgpt.com/docs> · Index: <https://learn.chatgpt.com/llms.txt>

**Wichtigste Punkte:**

- Der Hub ist ein Einstieg mit Zielauswahl („Explore and understand code“, „Build a
  new feature…“, „Review code and suggest changes“, „Fix issues and failures“) —
  Codex wird als Coding-Agent für genau diese vier Grundaufgaben positioniert.
- Jede Doku-Seite hat eine maschinenlesbare Markdown-Zwilling: „Each page has a
  Markdown twin at `/docs/<slug>.md` for direct ingestion.“ (llms.txt-Header)
- Es gibt einen kombinierten Export `docs/llms-full.txt` und ein kondensiertes
  „Codex manual“ (`docs/codex-manual.md`) — nützlich, um Agenten die Doku selbst
  lesen zu lassen.

**Einordnung (Interpretation):** Für ein eigenes Agenten-Setup sind die `.md`-
Zwillinge und `llms-full.txt` der günstigste Weg, Referenzwissen ohne Scraping in
den Kontext eines Agenten zu holen.

---

## 2. Cookbook-Themenseite „Agents“ (cookbook.openai.com/topic/agents)

URL: <https://cookbook.openai.com/topic/agents> · Spiegel mit Beschreibungen:
<https://developers.openai.com/cookbook/topic/agents>

**Wichtigste Punkte:**

- 68 Rezepte (Stand 24.09.2026), thematisch sortiert; Definition dort: „Agents are
  systems that independently accomplish tasks on your behalf. Agents use an LLM to
  execute instructions and make decisions.“
- Klarer Schwerpunkt auf **Evals und Verbesserungs-Schleifen**: u. a. „Macro Evals
  for Agentic Systems“, „Build an Agent Improvement Loop with Traces, Evals, and
  Codex“, „Build iterative repair loops with Codex“.
- **Kontext-Management** als eigenes Thema: „Building Reliable Agents with Memory
  and Compaction“, „Context Engineering – Short-Term Memory Management with
  Sessions“, „Context Engineering for Personalization“.
- **Long-Running-Work**: „Using PLANS.md for multi-hour problem solving“, „Using
  Goals in Codex“, „Iterating Development Workflows with Codex“.
- **Sandboxing** wird als Pattern gezeigt: „Migrate a Legacy Codebase with Sandbox
  Agents“, „Computer Use Agents in Daytona Sandboxes“.

**Einordnung (Interpretation):** Die Rezept-Titel sind eine gute Checkliste für
Bausteine, die ein ernsthaftes Agenten-Setup braucht: Traces → Evals → Harness-
Änderung, Memory/Kompaktierung, Sandbox, Skills.

---

## 3. PDF: „A practical guide to building agents“ (OpenAI Business Guide)

URL: <https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf>

**Wichtigste Punkte:**

- **Drei Kernkomponenten** eines Agenten: Model, Tools, Instructions; ein Agent ist
  eine Schleife („run“) bis zu einer Exit-Bedingung (Final-Output-Tool, Antwort ohne
  Tool-Call, Fehler, maximale Turns).
- **Modellwahl als Stufenplan mit Baseline:** „Set up evals to establish a
  performance baseline“ — erst mit dem stärksten Modell den Prototyp bauen, dann
  kleinere Modelle testen, wo sie noch ausreichen.
- **Erst Single-Agent maximieren:** „Our general recommendation is to maximize a
  single agent’s capabilities first.“ Aufteilen in mehrere Agenten nur bei
  komplexer Verzweigungslogik oder Tool-Überladung: „The issue isn’t solely the
  number of tools, but their similarity or overlap.“
- **Multi-Agent-Muster:** „Manager (agents as tools)“ (zentraler Manager delegiert
  per Tool-Calls, ein Agent hat Zugriff auf den Nutzer) vs. „Decentralized (agents
  handing off to agents)“ (Triage-/Handoff-Muster).
- **Guardrails als Schichten:** „Think of guardrails as a layered defense
  mechanism.“ Konkret: Relevance-Classifier, Safety-Classifier (Jailbreak/Prompt-
  Injection), PII-Filter, Moderation, Output-Validierung, deterministische
  Regel-Schutzschichten (Blocklisten, Längenlimits, Regex).
- **Tool-Risiko-Rating:** Werkzeuge nach Risiko bewerten — „based on factors like
  read-only vs. write access, reversibility, required account permissions, and
  financial impact“ — und High-Risk-Aktionen vor Ausführung prüfen/einem Menschen
  vorlegen.
- **Menschliche Übergabe (Human Intervention):** zwei Auslöser — Fehlerschwellen
  überschritten; „Actions that are sensitive, irreversible, or have high stakes
  should trigger human oversight until confidence in the agent’s reliability
  grows.“
- **Instruktionen:** aus vorhandenen SOPs/Dokumenten ableiten, Aufgaben in kleine
  explizite Schritte zerlegen, jede Routine mit konkreter Aktion/Ausgabe verknüpfen,
  Edge-Cases als bedingte Zweige erfassen; Prompt-Template mit Policy-Variablen
  statt vieler Einzelprompts.

**Einordnung (Interpretation):** Das PDF stützt mehrere der 69 Regeln direkt:
Baseline-Messung vor Optimierung, Scope klein halten, Guardrails statt Vertrauen,
menschliche Freigabe bei irreversiblen Aktionen (= „Push/Deploy manuell“).

---

## 4. Platform Docs: Agents SDK (platform.openai.com/docs/guides/agents)

URL: <https://platform.openai.com/docs/guides/agents>

**Wichtigste Punkte:**

- Definition: „Agents are applications that plan, call tools, collaborate across
  specialists, and keep enough state to complete multi-step work.“
- Empfohlene Lesereihenfolge für den Bau: Quickstart → Agent definitions („Define
  one specialist cleanly“) → Models/providers → Running agents (Loop/State) →
  Sandbox agents → Orchestration and handoffs („decide who owns the reply“) →
  Guardrails and human review → Results/state → Tools/MCP → Observability/Eval →
  Voice.
- **Sandbox-Agenten** als eigene Kategorie: „Use this when the agent needs files,
  commands, packages, snapshots, mounts, or provider links.“
- **Guardrails/Human Review:** „Use this when the workflow should block or pause
  before risky work continues.“
- **Debugging vor Evaluation:** „Use traces for debugging first, then move into
  evaluation loops.“

**Einordnung (Interpretation):** Die Reihenfolge „erst ein Spezialist sauber, dann
Orchestrierung“ spiegelt die PDF-Empfehlung „single agent first“ auf API-Ebene.

---

## 5. Codex CLI (learn.chatgpt.com/docs/codex/cli)

URL: <https://learn.chatgpt.com/docs/codex/cli>

**Wichtigste Punkte:**

- Kernbefehle direkt beim Start: „`/init` – create an AGENTS.md file with
  instructions for Codex“, `/status`, `/permissions`, `/model`, `/review`.
- **Git-Checkpoints als Standard:** „Create Git checkpoints before and after a task
  so you can revert changes.“
- **Review als eigener Modus:** „Run a dedicated review against uncommitted changes,
  a commit, or a base branch. Codex reports prioritized findings without modifying
  your working tree.“
- **Nicht-interaktiv für CI:** „Use Codex interactively or call `codex exec` from
  repeatable workflows and pipelines.“
- **Rechte vor jedem Lauf klären:** „Choose when Codex can edit files or run
  commands without asking, and inspect the active sandbox and writable roots before
  you continue.“
- Subagenten (`/agent`-Threads), MCP (`codex mcp`), Cloud (`codex cloud`) und
  Bild-Kontext (`codex --image`) sind erstklassige CLI-Features.

**Einordnung (Interpretation):** „Review ohne Working-Tree-Änderung“ und
Checkpoints liefern out-of-the-box, was die Video-Regeln „Prüfer-Rolle“ und
„Worktree-Isolation“ verlangen — der Prüfer muss nichts schreiben dürfen.

---

## 6. AGENTS.md-Anleitung (Custom instructions with AGENTS.md)

URL: <https://learn.chatgpt.com/docs/agent-configuration/agents-md>
(Spiegel: <https://developers.openai.com/codex/guides/agents-md>)

**Wichtigste Punkte (die konkrete Mechanik):**

- Ladereihenfolge und -regeln: „Codex reads `AGENTS.md` files before doing any
  work.“ Global (`~/.codex/AGENTS.md`, `AGENTS.override.md` gewinnt) → Projekt
  (Wurzel bis CWD, pro Verzeichnis genau eine Datei) → Merge von oben nach unten:
  „Files closer to your current directory override earlier guidance because they
  appear later in the combined prompt.“
- **Harte Grenze:** „Codex skips empty files and stops adding files once the
  combined size reaches the limit defined by `project_doc_max_bytes` (32 KiB by
  default).“ Überschreitung → `project_doc_max_bytes` erhöhen oder aufteilen.
- **Fallback-Namen** möglich (`project_doc_fallback_filenames = ["TEAM_GUIDE.md",
  ".agents.md"]` in `config.toml`) — bestehende Team-Dateien werden so zu
  Instruktionsdateien.
- **Verifikation der Einrichtung** (Prüfbefehl-Muster):
  `codex --ask-for-approval never "Summarize the current instructions."` und
  `codex --cd subdir --ask-for-approval never "Show which instruction files are active."`
  Audit: Log via `codex -c log_dir=./.codex-log` bzw. `session-*.jsonl`.
- **Code-Review-Regeln in AGENTS.md:** Abschnitt `## Code Review Rules` in der
  Datei, die dem Code am nächsten liegt; „Keep rules concise, explain the behavior
  to flag and any safe path or exception, and reserve formatting and lint checks
  for CI.“

**Einordnung (Interpretation):** Das ist die belastbarste Primärquelle für den
Aufbau einer Regel-Datei-Hierarchie: eine Kern-Datei + bereichsspezifische
Overrides — genau das Muster, das dieses Workspace-Repo (AGENTS.md +
CLAUDE_EXTENDS.md) bereits nutzt. Neu daraus: ein byte-Limit und ein Prüfbefehl,
der belegt, welche Dateien tatsächlich geladen wurden.

---

## 7. Codex Best Practices (learn.chatgpt.com/guides/best-practices)

URL: <https://learn.chatgpt.com/guides/best-practices>

**Wichtigste Punkte:**

- **Prompt-Grundgerüst (vier Teile):** Goal (was ändern/bauen) · Context (welche
  Dateien/Doku/Fehler zählen) · Constraints (Standards, Architektur, Sicherheit) ·
  Done when — „What should be true before the task is complete, such as tests
  passing, behavior changing, or a bug no longer reproducing?“
- **Planen vor Implementieren** bei komplexen/unklaren Aufgaben: Plan-Modus
  (`/plan`, Shift+Tab), Codex interviewen lassen, oder `PLANS.md`-Template für
  längere Arbeit.
- **AGENTS.md-Inhalte:** Repo-Layout, Build/Test/Lint-Befehle, Konventionen,
  PR-Erwartungen, Verbote, „What done means and how to verify work“; kurz halten:
  „A short, accurate `AGENTS.md` is more useful than a long file full of vague
  rules.“ Und: „When Codex makes the same mistake twice, ask it for a retrospective
  and update `AGENTS.md`.“
- **Rechte-Default:** „Keep approval and sandboxing tight by default, then loosen
  permissions only for trusted repos or specific workflows once the need is clear.“
- **Testen/Reviewen als Teil der Aufgabe:** Tests schreiben/aktualisieren, die
  richtigen Suiten laufen lassen, Lint/Typen prüfen, Diff reviewen; `/review` für
  Base-Branch-, Uncommitted- oder Commit-Review; „At OpenAI, Codex reviews 100% of
  PRs.“
- **MCP/Skills/Scheduled Tasks:** Werkzeuge nur ergänzen, wenn sie einen echten
  manuellen Loop ersetzen; wiederkehrende Workflows als Skill (`SKILL.md`,
  `$HOME/.agents/skills` persönlich, `.agents/skills` im Repo geteilt); „A useful
  rule is that skills define the method and scheduled tasks define the schedule.“
- **Chat-Hygiene:** „Keep one chat per coherent unit of work.“ Für parallele Arbeit
  Git-Worktrees nutzen — sonst bläht sich der Kontext auf („Common mistakes“-Liste
  nennt u. a. „Running live tasks on the same files without using Git worktrees“).
- „Many quality issues are really setup issues“ (falsches Arbeitsverzeichnis,
  fehlende Schreibrechte, falsche Model-Defaults).

**Einordnung (Interpretation):** Diese Seite ist die dichteste Fundstelle für den
Nutzer: die „Done when“-Formel, „Retrospektive nach dem zweiten Fehler“ und
„ein Chat pro Arbeitseinheit“ sind direkt in eigene Regeln übertragbar.

---

## 8. Subagenten (learn.chatgpt.com/docs/agent-configuration/subagents)

URL: <https://learn.chatgpt.com/docs/agent-configuration/subagents>

**Wichtigste Punkte:**

- Begründung für Subagenten = Kontext-Hygiene: „If you flood the main chat (where
  you’re defining requirements, constraints, and decisions) with noisy intermediate
  output such as exploration notes, test logs, stack traces, and command output,
  the session can become less reliable over time.“ (Begriffe: Context Pollution,
  Context Rot.)
- Arbeitsteilung: „Keep the main agent focused on requirements, decisions, and
  final outputs“; Subagenten geben Zusammenfassungen statt Rohoutput zurück.
- **Parallelitäts-Regel:** „use parallel agents for read-heavy tasks such as
  exploration, tests, triage, and summarization. Be more careful with parallel
  write-heavy workflows, because agents editing code at once can create conflicts
  and increase coordination overhead.“
- **Custom Agents als TOML-Dateien** (`.codex/agents/*.toml`) mit eigenem `model`,
  `model_reasoning_effort`, `sandbox_mode` und `developer_instructions`. Beispiel
  „reviewer“: `sandbox_mode = "read-only"`, `model_reasoning_effort = "high"`,
  Instruktion u. a. „Review code like an owner. Prioritize correctness, security,
  behavior regressions, and missing test coverage.“
- Beispiel-Prompt für paralleles Review: „Spawn one subagent for security risks,
  one for test gaps, and one for maintainability. Wait for all three, then
  summarize the findings by category with file references.“

**Einordnung (Interpretation):** Das ist die offizielle Umsetzung von
Rollen-Trennung (Explorer/Reviewer read-only, Worker schreibend) und die Bestätigung
der Worktree-Regel: parallele Schreiber erzeugen Konflikte und Koordinationslast.

---

## 9. Sandboxing, Approvals & Security (agent-approvals-security)

URL: <https://learn.chatgpt.com/docs/agent-approvals-security>

**Wichtigste Punkte:**

- **Zwei Schichten:** Sandbox-Modus (was technisch möglich ist — Schreiborte,
  Netzwerk) + Approval-Policy (wann gefragt wird). Default: „By default, the agent
  runs with network access turned off“; OS-erzwungene Sandbox, Schreibrechte
  typischerweise auf das aktuelle Workspace begrenzt.
- **Netzwerk-Policy allowlist-first:** „deny always wins over allow, and global `*`
  is only valid for allow rules.“ Lokale/private Ziele sind per Default blockiert
  (`allow_local_binding = false`); DNS-/Loopback-Schutz, `dangerously_*`-Flags nur
  in kontrollierten Umgebungen.
- **Tool-Calls zählen wie Shell-Kommandos:** „Destructive app/MCP tool calls always
  require approval when the tool advertises a destructive annotation.“
- **Cloud-Trennung:** Setup-Phase (darf Netz) läuft vor der Agenten-Phase (offline
  per Default); „Secrets configured for cloud environments are available only during
  setup and are removed before the agent phase starts.“
- **Telemetrie-Datenschutz:** „Keep `log_user_prompt = false` unless policy
  explicitly permits storing prompt contents.“; Events u. a. `codex.tool_decision`
  (approved/denied) und `codex.tool_result`.

**Einordnung (Interpretation):** Der Default „Netz aus + Schreiben nur im
Workspace + destruktive Tool-Calls fragen immer“ ist die offizielle Fassung von
„Autonomiegrenze“: lokal frei, alles nach außen hinter Freigaben.

---

## 10. Rules (Befehls-Policies vor Ausführung)

URL: <https://learn.chatgpt.com/docs/agent-configuration/rules>

**Wichtigste Punkte:**

- `.rules`-Dateien (Starlark) definieren `prefix_rule()` mit `pattern`,
  `decision` (`allow` / `prompt` / `forbidden`) und `justification`. Auflösung:
  „Codex applies the most restrictive decision when more than one rule matches
  (forbidden > prompt > allow).“
- **Testbare Regeln:** `match` / `not_match` als „inline unit tests“ mit
  Beispiel-Kommandos; Testlauf per
  `codex execpolicy check --pretty --rules ~/.codex/rules/default.rules -- <cmd>`.
- **Compound-Kommandos werden sicher zerlegt:** einfache Ketten (`&&`, `||`, `;`,
  `|`) werden per tree-sitter in Einzelkommandos gesplittet und jedes einzeln
  bewertet — „Even if you allow `pattern=["git","add"]`, Codex won‘t auto allow
  `git add . && rm -rf /`“. Komplexe Skripte (Redirections, Substitutionen,
  Variablen, Wildcards) werden konservativ als ein Kommando behandelt.
- Shell-Interception: Beim Allow im TUI schreibt Codex die Regel in
  `~/.codex/rules/default.rules`; Admins können per `requirements.toml`
  einschränken.

**Einordnung (Interpretation):** „Regeln mit eingebauten Beispiel-Tests + strikteste
Entscheidung gewinnt“ ist ein Muster, das sich 1:1 auf eigene Gate-Skripte
(Prüfbefehl-Gate) übertragen lässt.

---

## 11. Codex Prompting Guide (Cookbook)

URL: <https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide>

**Wichtigste Punkte:**

- **Autonomie/Persistenz** ist der wichtigste Prompt-Hebel: „The most critical
  snippets are those covering autonomy and persistence, codebase exploration, tool
  use, and frontend quality.“ Ziel der Standard-Prompts: „Default expectation:
  deliver working code, not just a plan.“
- **Plan-Disziplin:** Plan-Tool bei den einfachsten ~25 % der Aufgaben überspringen
  („Skip using the planning tool for straightforward tasks (roughly the easiest
  25%).“); „Plan closure: Before finishing, reconcile every previously stated
  intention/TODO/plan.“ — kein Turn darf mit offenen Punkten enden.
- **Git-Sicherheit im Prompt verankert:** „NEVER use destructive commands like
  `git reset --hard` or `git checkout --` unless specifically requested or approved
  by the user.“; fremde Änderungen im Worktree nie zurücksetzen; bei unerwarteten
  Änderungen sofort stoppen und fragen.
- **Parallelität als Regel:** „Always maximize parallelism. Never read files
  one-by-one unless logically unavoidable.“
- **Harness > Prompt:** „Update your tools, including our apply_patch
  implementation and other best practices below. This is a major lever for getting
  the most performance.“
- **Metaprompting zur Selbstverbesserung:** Am Ende eines schwachen Turns das Modell
  fragen, welche Instruktionsänderung es künftig schneller/besser machen würde;
  wiederkehrende Muster generalisieren und als Eval absichern.

**Einordnung (Interpretation):** „Plan Closure“ und „Deliver working code“ sind die
Prompt-Fassung von „Fertig ist, was verifiziert ist“ — plus die Ergänzung, offene
Punkte explizit zu schließen statt stehenzulassen.

---

## 12. Cookbook: „Iterating development workflows with Codex“ (Harness-Muster)

URL: <https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex>

**Wichtigste Punkte:**

- **Harness-Struktur als Datei-Konvention:** `AGENTS.md` (+ optional `GOALS.md`,
  `PLANS.md`, `PROMPTS.md`) und `harness/build/phase-XX-*.md`, `harness/build-log.md`,
  `harness/code_review/`. „For plan execution, creating a `PLANS.md` file as a
  source of truth is considered a useful, optional convention.“
- **Phasen-Dateien mit Pflichtfeldern:** Ziel, In-Scope, explizite Non-Goals,
  Abhängigkeiten, Approval-Gate, „Red, green, refactor, and verification plan“,
  Verifikationskommandos, Akzeptanzkriterien und „Evidence that must be recorded
  before the phase can be considered complete“.
- **Menschliche Gates statt Volldampf:** „Require a read-only preflight before
  implementation“ · „Require an approval summary before repository writes“ · „Keep
  commits, pushes, deployments, credentials, and external writes behind separate
  explicit approval“ · „Stop after the selected phase rather than beginning the
  next one automatically“.
- **Kleinere Phasen = prüfbare Historie:** „Creating smaller build files not only
  improves readability but supports human gating to manually review code quality
  and other outputs“ — „prevents agent drift“.
- **Retrospektive mit P0–P3-Backlog:** „P0: Unsafe or materially incorrect
  workflow behavior / P1: Repeated failures, approval gaps, or misleading evidence
  / P2: Meaningful efficiency or clarity improvements / P3: Optional polish“.
- **Forward-Testing:** neue/geänderte Skills in frischen, unabhängigen Kontexten
  testen, ohne die erwartete Lösung zu verraten; „Do not declare the workflow
  improved solely because the skill passes structural validation. Require evidence
  from realistic use.“

**Einordnung (Interpretation):** Das ist die konkrete Blaupause für das, was die
Video-Regeln „Planer/Worker/Prüfer“, „TDD-Gate“ und „Scope-Treue“ nennen — inklusive
Dateiformaten, die man wörtlich übernehmen kann.

---

## 13. Cookbook: „Using PLANS.md for multi-hour problem solving“ (ExecPlans)

URL: <https://developers.openai.com/cookbook/articles/codex_exec_plans>

**Wichtigste Punkte:**

- ExecPlans sind „thorough design documents, and ‚living documents‘“, die der Nutzer
  vor dem Start langer Implementierungen reviewen kann; ein solcher Plan „has
  enabled Codex to work for more than seven hours from a single prompt“.
- Aktivierung über AGENTS.md-Marker, z. B.:
  `When writing complex features or significant refactors, use an ExecPlan (as described in .agent/PLANS.md) from design to implementation.`
- **Selbstgenügsame Pläne:** „Treat the reader as a complete beginner to this
  repository: they have only the current working tree and the single ExecPlan file
  you provide. There is no memory of prior plans and no external context.“
- **Kein Nachfragen mitten im Plan:** „When implementing an executable
  specification (ExecPlan), do not prompt the user for ‚next steps‘; simply proceed
  to the next milestone.“ Fortschritt/Abschnitte laufend aktualisieren.
- Regel aus der Best-Practices-Seite dazu: wenn AGENTS.md zu groß wird, Hauptdatei
  schlank halten und auf aufgabenbezogene Markdown-Dateien (Planung, Review,
  Architektur) verweisen.

**Einordnung (Interpretation):** „Plan als lebendes Dokument mit Milestones“ liefert
die fehlende Schnittstelle zwischen Planer- und Worker-Rolle: der Plan ist das
Übergabeartefakt, nicht der Chatverlauf.

---

## 14. Ergänzend: Long-running work / Goals und Worktrees

URLs: <https://learn.chatgpt.com/docs/long-running-work> ·
<https://learn.chatgpt.com/docs/environments/git-worktrees>

**Wichtigste Punkte:**

- **Abschlusskriterien erzwingen:** „Write a goal that lets ChatGPT verify its own
  progress“ — Ziel-Zielbild: Outcome + Constraints + Verification („Add tests,
  measurements, or review criteria that prove the work is complete.“).
- „The goal text becomes both the first prompt and the completion criteria for the
  task.“ (`/goal` in App, CLI, IDE; `/plan` für unklare Ausgangslage).
- Unabhängige Aufgaben in getrennte Chats; **niemals zwei Aufgaben mit Schreibzugriff
  auf dieselbe Quelle** („avoid giving two tasks write access to the same connected
  source“).
- **Worktree-Begründung:** „Worktrees let Codex run multiple independent chats in
  the same project without interfering with each other.“ Managed Worktrees laufen
  im detached HEAD; Handoff bewegt einen Chat zwischen Local und Worktree.
- Goals-Cookbook (nur teilweise abrufbar, Stand 24.09.2026): Beispiel „Turning a
  weak Goal into a strong one“ — „The second Goal gives Codex something it can
  inspect: a page, a build command, and command behavior.“

**Einordnung (Interpretation):** „Zwei Schreiber nie auf derselben Quelle“ ist eine
härtere, klarere Formulierung als die reine Worktree-Regel — sie gilt auch für
Nicht-Git-Quellen.

---

## Gesamtbild: Was OpenAI wiederholt und nachdrücklich sagt (Querschnitt)

1. **Ein Agent zuerst, dann aufteilen** — erst Tools/Instruktionen maximieren, bei
   Verzweigungslogik oder Tool-Überladung (Ähnlichkeit!) trennen. (PDF; Platform-Docs)
2. **Baseline vor Optimierung** — erst Evals/Baseline mit dem stärksten Modell,
   dann kleinere Modelle prüfen. (PDF)
3. **Fertig heißt verifiziert** — „Done when“ im Prompt, Verification-Sektion im
   Goal, Evidence vor Phasenabschluss, Review ohne Working-Tree-Änderung.
   (Best Practices; Long-running work; Cookbook-Workflows)
4. **Kontext ist die knappste Ressource** — ein Chat pro Arbeitseinheit,
   Subagenten für laute Zwischenarbeit, Compaction, AGENTS.md ≤ 32 KiB.
   (Best Practices; Subagents; AGENTS.md-Doku)
5. **Rechte klein halten, dann lockern** — Sandbox + Approval-Policy getrennt,
   Netz aus per Default, destruktive Tool-Calls immer mit Freigabe, Regeln mit
   eingebauten Tests und „strikteste gewinnt“. (Security; Rules)
6. **Parallel nur lesend** — parallele Reader/Reviewer ja, parallele Schreiber nur
   mit Isolation (Worktrees), nie zwei Schreiber auf derselben Quelle.
   (Subagents; Worktrees)
7. **Aus Fehlern Regeln machen** — Retrospektive nach dem zweiten Fehler →
   AGENTS.md/Skill aktualisieren; Skills für wiederkehrende Abläufe, Schedules erst
   nach manueller Verlässlichkeit. (Best Practices; Cookbook-Workflows)
8. **Grenzen der Quellenlage:** Die genannten OpenAI-Dokumente beschreiben Techniken
   und Defaults, aber keine Pflicht-Organisation (es gibt dort keine formale
   „Planer/Worker/Prüfer“-Vorschrift — am nächsten kommen Subagenten-Rollen,
   Review-Modi und Approval-Gates). Das ist eine Einordnung, keine OpenAI-Aussage.
