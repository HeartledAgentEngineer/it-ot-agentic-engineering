---
name: grillAnAgent
description: Einzusetzen zwischen Phase 1 (Brainstorm) und Phase 2 (Alignment). Der Host (DeepSeek V4) lädt einen Kritiker (Haiku) via OpenRouter ein, der den Brainstorm-Entwurf aus rein technischer Architektur-/Engineering-Sicht hinterfragt. Ergebnis: Protokoll mit Einigungs-Quote. Bei vollem Konsens kann Phase 2 übersprungen werden. Bei Uneinigkeit gehen nur die strittigen Punkte mit Vor-/Nachteilen ins grill-me.
---

# grillAnAgent — Host lädt Kritiker ein

## Überblick

Nach dem Brainstorm (Phase 1) liegt eine `brainstorm.md` vor. Bevor Sebastian aufwändig durch `grill-me` gelotst wird, prüft ein **externer Kritiker** den Entwurf:

| Rolle | Wer | Aufgabe |
|---|---|---|
| **Host (Builder)** | DeepSeek V4 (aktiver Agent) | Vertritt den Entwurf konstruktiv |
| **Griller (Kritiker)** | Haiku via OpenRouter | Hinterfragt aus Architektur-/Engineering-Sicht |

Der Kritiker wird über **einen API-Call** eingeladen. Er bekommt einen strikten Prompt: *Nur Technik, Architektur, Best Practices – keine Spekulation über Benutzer oder fachliche Prozesse.*

**Ziel:** Sebastian wird nur bei echten Meinungsverschiedenheiten der Modelle belästigt. Bei Einigkeit reicht einmal Abnicken. Bei Uneinigkeit gibt's eine Vor-/Nachteile-Tabelle als Entscheidungsgrundlage.

## Einordnung in den Workflow

```
Phase 1 (Brainstorm)
    ↓ brainstorm.md
Phase 1b (grillAnAgent)  ← NEU
    ↓ grillAnAgent-protokoll.md
Phase 2 (grill-me)       ← NUR bei Uneinigkeit (Host ≠ Griller)
    ↓
Phase 3 (Planung + critic)
```

## Der Aufruf

```bash
node .claude/skills/grillAnAgent/grillAnAgent.mjs brainstorm.md
```

Das Skript:
1. Liest `brainstorm.md`
2. Ruft Haiku via OpenRouter auf (Prompt: technisches Grillen)
3. Vergleicht Host-Perspektive mit Griller-Perspektive
4. Schreibt `grillAnAgent-protokoll.md` in denselben Ordner

### Beispiel-Ausgabe (stderr)

```
Brainstorm gelesen: brainstorm.md (1240 Zeichen)
[anthropic/claude-haiku-4.5] 520→680 Tokens

=== GRILLANAGENT ZUSAMMENFASSUNG ===
Einigungs-Quote: 75%
Einig: 6 | Strittig: 2
⚠️ 2 strittige Punkte → gehen in Phase 2 (grill-me).
```

### Beispiel-Protokoll (Auszug bei Uneinigkeit)

```markdown
## ⚠️ Strittige Punkte (gehen in Phase 2 – grill-me)

### 1. EMPFEHLUNGEN: SQLite vs. PostgreSQL

| | Position |
|---|---|
| **Host (Builder)** | SQLite reicht für Single-User völlig aus |
| **Griller (Haiku)** | PostgreSQL ist zukunftssicherer |

**Vor-/Nachteile:**

| Kriterium | SQLite | PostgreSQL |
|---|---|---|
| Aufwand | ⏳ | ⏳ |
| Vorteil | kein Server nötig | volles MVCC |
| Nachteil | blockiert bei Schreibzugriff | Setup-Aufwand |
```

### Entscheidungsmatrix für Sebastian

| Ergebnis | Konsequenz |
|---|---|
| **Keine strittigen Punkte** | Phase 2 (grill-me) kann übersprungen werden – einmal abnicken reicht |
| **Strittige Punkte vorhanden** | Nur diese gehen in Phase 2. Host präsentiert Vor-/Nachteile-Tabelle |
| **Host und Griller uneinig** | Sebastian entscheidet als Architect mit der Tabelle als Basis |

## Beschränkung: Keine Spekulation über den Benutzer

Der Griller-Prompt verbietet explizit:
- Spekulation über Benutzer-Anforderungen oder fachliche Prozesse
- Annahmen über Sebastians Arbeitsumfeld oder Wünsche
- Rat, was "der Kunde" oder "der Benutzer" denken könnte

**Erlaubt und erwünscht:**
- Technische Architektur-Diskussion (Framework, Datenhaltung, API-Design)
- Security, Testbarkeit, Deployment, Maintainability
- Best Practices und Anti-Patterns aus Engineering-Sicht

## Wann einsetzen

- **Immer nach Phase 1** – bevor Zeit in grill-me investiert wird
- Auch nach größeren Änderungen an einem bestehenden Plan

## Wann NICHT

- Nicht bei dringenden Hotfixes – da zählt Geschwindigkeit
- Nicht bei trivialen Änderungen (Tippfehler, Formatierung) – da ist kein Brainstorm nötig

## Kosten

Ein API-Call (Haiku) mit ~1200–1800 Tokens. Geschätzt: 0,3–0,5 Cent pro Durchlauf.
Deutlich günstiger als ein ausführliches grill-me mit Sebastian für triviale Punkte.

## Datenschutz

Der API-Call geht über OpenRouter (DSGVO-konform, keine Nutzung für Modell-Training).
Die `brainstorm.md` verlässt deinen Rechner nur für diesen einen Call.

## Dateien

- `grillAnAgent.mjs` — das Skript. Enthält Prompt, API-Aufruf, Vergleichslogik und Protokoll-Generator.
- `SKILL.md` — diese Datei. Beschreibung und Einordnung.

## Verhältnis zu anderen Skills

| Skill | Phase | Zweck |
|---|---|---|
| `grill-me` | Phase 2 | Sokratisches Interview – Sebastian entscheidet |
| `grillAnAgent` | Phase 1b | Host lädt Kritiker ein – spart unnötige Grill-me-Fragen |
| `critic` | Phasen 3/5/7 | Befund-Prüfung durch fremdes Modell (OpenRouter) |

`grillAnAgent` ersetzt kein grill-me – es macht es schlanker. Bei vollem Konsens (Host und Kritiker einig) kann grill-me übersprungen werden, aber das bleibt Sebastians Entscheidung.