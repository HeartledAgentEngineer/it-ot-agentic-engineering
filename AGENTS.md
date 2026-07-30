# AGENTS.md — Einstieg für KI-Agenten

Dieser Workspace steuert **alle** KI-Agenten (Claude Code, Codex, Antigravity, Cursor)
über eine einzige Regeldatei:

> ### 👉 [`CLAUDE.md`](CLAUDE.md) in der Workspace-Wurzel
> Das ist die einzige Quelle. Bitte zuerst vollständig lesen, bevor du etwas änderst.

Diese Datei hier ist bewusst nur ein Wegweiser — die Regeln werden **nicht** kopiert,
damit sie nicht an zwei Stellen auseinanderlaufen können.

## Zusätzliche Bereichsregeln

Je nachdem, wo du arbeitest, gilt zusätzlich:

| Bereich | Zusatzregeln |
|---|---|
| `01_IT-OT_Integration/` | [`01_IT-OT_Integration/CLAUDE.md`](01_IT-OT_Integration/CLAUDE.md) — TwinCAT-/SPS-Konventionen |
| `02_Softwareentwicklung_IT/` | [`02_Softwareentwicklung_IT/CLAUDE.md`](02_Softwareentwicklung_IT/CLAUDE.md) — Design- und Web-Richtlinien |

Diese beiden Bereichsdateien werden von [`sync-rules.ps1`](sync-rules.ps1) aus der jeweiligen
`CLAUDE_EXTENDS.md` erzeugt. **Nicht von Hand bearbeiten** — Änderungen gehen beim nächsten
Lauf verloren. Stattdessen die `CLAUDE_EXTENDS.md` ändern und das Skript erneut ausführen.

## Die zwei harten Leitplanken

Hier bewusst wiederholt, damit sie auch ein Agent sieht, der nur diese Datei liest:

1. **Niemals `git push`.** Lokale Commits sind erlaubt. Ein Push wird ausschließlich von
   Sebastian selbst freigegeben (Schutz vor versehentlichem Secrets-Leak).
2. **Keine Online-Änderungen an der SPS.** In `01_IT-OT_Integration` werden nur
   Code-Blaupausen geliefert; Einspielen und Online Change macht Sebastian manuell.

Alles Weitere — Sprache, Arbeitsweise, der 8-Phasen-Workflow — steht in [`CLAUDE.md`](CLAUDE.md).
