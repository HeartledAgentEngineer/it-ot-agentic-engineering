# Workspace Agentic Engineering

@AGENTS.md

## Claude Code

- Session-Kontext: `.claude/memory/CONTEXT.md` (gitignored) bei Bedarf lesen.
- Feature-Arbeit läuft über `/phase`. Ohne Aufruf keine Phasenlogik anwenden.
- Bereichsregeln stehen in der jeweiligen Bereichs-`CLAUDE.md`. Sie laden, sobald
  eine Datei aus dem Bereich gelesen wird, und werden von `sync-rules.ps1` aus
  der zugehörigen `CLAUDE_EXTENDS.md` erzeugt.
- Suche und Testläufe an die Subagenten `rechercheur` und `tester` geben, damit
  Suchtreffer und Logs nicht im Hauptkontext landen.
- Fremdprüfung: `node .claude/skills/critic/pruefe.mjs`.
  - IT-Code (`02_Softwareentwicklung_IT`): alle Motoren erlaubt.
  - OT-Code (`01_IT-OT_Integration`): **nur** über das OpenRouter-Gateway
    (`--openrouter`, Haiku). Gemini-Direktverbindung und Antigravity sind
    für OT gesperrt.
  - Unabhängig vom Motor gilt weiterhin: Verfahrenstechnisches Prozess-Know-how,
    kundenspezifische Anlagenlogik und alles unter NDA verlassen den Rechner
    nicht — auch nicht über OpenRouter.
