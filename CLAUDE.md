# Workspace Agentic Engineering

@AGENTS.md

## Claude Code

- Session-Kontext: `.claude/memory/CONTEXT.md` (gitignored) bei Bedarf lesen.
- Feature-Arbeit läuft über `/phase`. Ohne Aufruf keine Phasenlogik anwenden.
- Bereichsregeln laden automatisch über `.claude/rules/`, sobald Dateien aus
  dem jeweiligen Bereich gelesen werden.
- Suche und Testläufe an die Subagenten `rechercheur` und `tester` geben, damit
  Suchtreffer und Logs nicht im Hauptkontext landen.
- Fremdprüfung: `node .claude/skills/critic/pruefe.mjs`. Ausschließlich für
  Projekte aus `02_Softwareentwicklung_IT` — SPS-, OT- und Kundencode bleibt
  lokal, solange kein AVV mit EU-Serverstandort und Trainingsausschluss
  vorliegt. Sobald er vorliegt: diese Einschränkung hier und in
  `.claude/rules/ot-sps.md` entfernen.
