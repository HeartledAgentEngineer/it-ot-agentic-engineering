# ==============================================================================
# BEREICHS-ERWEITERUNG: SOFTWAREENTWICKLUNG (IT)
# ==============================================================================

Dieses Regelwerk erweitert die globalen KI-Direktiven um Richtlinien für responsive, ästhetisch anspruchsvolle Web- und Appentwicklung (Frontend, Backend, Mobile).

---

## 1. DESIGN-AESTHETICS & PREMIUM-LOOK

Jede Benutzeroberfläche (HMI, App, Web-Frontend) muss den Benutzer auf den ersten Blick faszinieren ("Wow-Effekt"). Einfache, standardmäßige Layouts sind nicht akzeptabel.

* **Farbpaletten:** Harmonische, kuratierte HSL-Farben statt Standardfarben. Dunkle Modi (Dark Mode) als Standard, verziert mit dezenten, edlen Farb-Akzenten.
* **Typografie:** Verwendung moderner, runder Google-Fonts (z. B. *Inter*, *Roboto*, *Outfit* oder *Lexend*) anstelle von Systemschriftarten.
* **Details:** Smooth gradients (weiche Verläufe), Glassmorphism-Effekte (transparente Frostglas-Optik) und subtile Schlagschatten für räumliche Tiefe.
* **Animationen:** Verwendung von Mikro-Animationen bei Benutzer-Interaktion (Hover-Effekte, geschmeidige Übergänge bei Button-Klicks, sanftes Einblenden).

---

## 2. WEB- & APP-TECHNOLOGIEN

* **Frontend:** Moderner, modularer Code in HTML/CSS/JS oder modernen Frameworks (Vite, React Native).
* **Mobile (Expo Go):** Lokaler Datenabgleich via `AsyncStorage` auf dem Mobilgerät. Flüssige Performance durch Lazy-Loading von Elementen.
* **Backend:** Flask / Python für asynchrone Logik auf dem PC, Port 5000. Datenhaltung in strukturierten JSON- oder SQL-Datenbanken.

---

## 3. RESPONSIVE LAYOUTS & SEO-BEST-PRACTICES

* **Responsivität:** Jede Web-Anwendung muss sich nahtlos an alle Bildschirmgrößen anpassen (Mobile, Tablet, Desktop).
* **Semantic HTML:** Verwendung von HTML5-Elementen (`<header>`, `<nav>`, `<main>`, `<section>`, `<footer>`) statt reinem `<div>`-Wust.
* **Eindeutige IDs:** Alle interaktiven Elemente (Buttons, Inputs) müssen eindeutige, deskriptive IDs für automatisiertes Testen besitzen.
* **SEO-Richtlinien:** Jede Seite besitzt einen einzigartigen `<title>` und eine aussagekräftige `<meta description>` für Suchmaschinen.

---

## 4. PRÜFBEFEHLE (VERIFIER-GATE)

Ein Schritt gilt als fertig, wenn der Prüfbefehl des Projekts Exit-Code 0 liefert.
Die folgenden Befehle sind verifiziert — sie wurden ausgeführt, nicht abgeschrieben.
Pfade sind relativ zum Projektverzeichnis.

| Projekt | Prüfbefehl (aus dem Projektverzeichnis) | Stand |
|---|---|---|
| `personal_ai_agent` | `backend/.venv/Scripts/python.exe -m pytest tests/ -q` | **208 grün**, Exit 0 (15.09.2026) |
| `concertify` | `.venv/Scripts/python.exe -m pytest tests -q` | **180 grün**, Exit 0 (15.09.2026) |
| `typeFREE` | ⚠️ **blockiert** — kein `.venv` im Repo, globales Python hat `keyboard` nicht → 12 Collection-Errors. Reaktivierung: venv anlegen + `requirements` installieren | offen (15.09.2026) |
| `RAG-Systeme` | **fehlt.** Nur `test_embeddings.py` als Einzelskript, keine Testsuite | — |
| `document_automation` | **fehlt.** Keine Tests vorhanden | — |
| `eichhoernchen_spiel` | **entfällt.** Einzelne HTML-Datei, Rapid-Prototyping-Demo | — |

**Wichtig:** Prüfbefehle müssen **das Projekt-venv** nutzen (`…/.venv/Scripts/python.exe`).
Mit dem globalen `python` schlagen sie an fehlenden Dependencies fehl — das ist
kein Projektfehler, sondern ein Aufruf-Fehler.

**Was daraus folgt:**

* Projekte **mit** grünem Prüfbefehl (`personal_ai_agent`, `concertify`) dürfen
  im Hybrid-Workflow autonom weiterarbeiten: Änderung → Prüfbefehl (Exit 0) →
  „code + docs" in einem Commit.
* Projekte **ohne** funktionierenden Prüfbefehl (`typeFREE`, `RAG-Systeme`,
  `document_automation`) bleiben an der kurzen Leine: jede Änderung wird
  einzeln vorgelegt. Kein Durchlauf ohne maschinelles Gate.
* Fehlt einem Projekt der Prüfbefehl, wird das benannt — nicht ersetzt durch
  „sieht gut aus". Einen Prüfbefehl zu erfinden, der nichts prüft, ist schlimmer
  als keiner.
* Der Prüfbefehl muss **reproduzierbar** sein: mit dem Projekt-venv, aus dem
  Projektverzeichnis, ohne manuelle Vorbereitung.

Prüfläufe gehören an den Subagenten `tester`, damit die Logs nicht im
Hauptkontext landen.

---

## 5. CACHE-BUSTING (PFLICHT bei Frontend-Änderungen)

**Gilt für `personal_ai_agent` (und jedes Web-Frontend im Workspace):**

Bei JEDER Änderung an Frontend-Dateien (`index.html`, `app.js`, `style.css`)
MUSS die `?v=`-Versionsnummer in `index.html` erhöht werden — sonst lädt der
Browser (Comet/Chrome) die alte gecachte Datei und die Änderung ist unsichtbar.

**Schema:** `JJJJMMTT` + laufender Buchstabe für mehrere Änderungen am selben Tag.
- Erste Änderung am 2026-08-24 → `?v=20260824A`
- Zweite am selben Tag → `?v=20260824B` (usw.)

**Regel:** Cache-Bump IMMER im selben Commit wie die Frontend-Änderung.
Niemals annehmen, der Browser lade "schon neu" — hartes Caching ist der
Normalfall (war bereits mehrfach die Fehlerursache).

---

## 6. ARBEITSWEISE — GATES, FOKUS, KONTEXT (verbindlich)

Diese Regeln sind der Kompromiss aus dem Hybrid-Workflow: **Hermes lenkt,
statt dass Sebastian jede Regel einzeln einfordert.**

### 6.1 Verifier-Gate (maschinell erzwungen)

Kein Commit ohne grünen Prüfbefehl. Das ist als **Git-Hook** umgesetzt und gilt
damit für **alle Werkzeuge** (Claude Code, Cline, Hermes) und für Menschen:

```bash
git config core.hooksPath .githooks   # einmalig pro Klon!
```

- Hook: `.githooks/pre-commit` — testet nur das Projekt, dessen **Code** staged
  ist; rote Tests brechen den Commit ab.
- Notfall-Bypass: `git commit --no-verify` (nur bewusst, im Commit begründen).
- Details + Pitfalls: Skill `verifier-gate`.

### 6.2 Grill VOR dem Bauen (nicht danach)

Bei jedem Feature > ~100 Zeilen oder jeder Architektur-Entscheidung **zuerst**
`grillAnAgent` (Brainstorm → Grill → Einigkeit), **dann** implementieren.
Nachträgliches Nachbessern (`fix(fix(...))`-Ketten) ist teurer als 10 Minuten
Grill vorab. Messgröße: Anteil `fix(`-Commits soll **nicht** steigen.

### 6.3 Kontext-Disziplin

- **Ein Fokus pro Session.** Parallel-Ideen nicht im laufenden Chat verfolgen,
  sondern als Kanban-Task parken.
- **Session-Reset bei ~50 %** Kontextfüllung (Auto-Kompression greift dort,
  Ziel-Ratio 0,2) — vorher Zwischenstand in eine Handoff-Datei schreiben.
- Große Archive/Logs gehören in Werkzeuge/`grep`, nicht in den Chat-Kontext
  (4,38 Mrd. Tokens bei ~200k/Request zeigen: Kontext-Ballast ist real).

### 6.4 Parallelarbeit über Kanban

Aufgaben, die parallel laufen sollen, als Kanban-Task mit `--assignee` anlegen
→ der Dispatcher arbeitet sie in **eigenem Kontext/Workspace** ab. Nicht alles
im Chat serialisieren.

### 6.5 Regeln pflegen (eine Quelle)

`AGENTS.md` (Kern) und `CLAUDE_EXTENDS.md` (Bereich) sind die Quellen. Nach
jeder Änderung hier: `sync-rules.ps1` laufen lassen (erzeugt die
Bereichs-`CLAUDE.md`). **Nie** die generierten `CLAUDE.md` direkt editieren —
sie werden überschrieben.

### 6.6 Rollen: Planer → Ausführer → Prüfer (getrennte Kontexte)

Jede größere Aufgabe läuft in **drei Rollen mit getrenntem Kontext** — nie
plant, führt aus und prüft derselbe Kontext:

| Rolle | Wer | Aufgabe | Modell |
|---|---|---|---|
| **Planer** | Hermes (Hauptchat) | Zerlegt die Aufgabe, schreibt den Plan als **Datei**, legt Reihenfolge + Prüfkriterien fest | V4.1 Flash / Terra |
| **Ausführer** | Codex-CLI oder Subagent | Führt **genau einen** Planschritt aus, schreibt Code + Tests | Terra (gratis) / Subagent |
| **Prüfer** | frischer Subagent | Prüft **gegen den Plan**, führt den Prüfbefehl aus, meldet Abweichungen | frischer Kontext |

**Warum getrennt:** Der Ausführende trägt nur seinen Schritt im Kontext (billig,
fokussiert). Der Prüfer hat frischen Kontext und findet, was der Ausführende
übersieht — ein Kontext, der seine eigene Arbeit prüft, findet seine eigenen
Fehler nicht (Kernprinzip aus Skill `requesting-code-review`).

**Verbindlich:** Der Plan liegt als **Datei** vor (`.hermes/plans/<thema>.md`) —
nicht nur im Chat. Sonst kann der Ausführer ihn nicht lesen und der Prüfer
nicht dagegen prüfen. Fertig ist der Schritt erst, wenn der Prüfer ihn
abgenommen hat (Verifier-Gate §6.1).

### 6.7 Shell-Befehle: ankündigen, einfach halten, auf Deutsch erklären

Sebastian sieht bei Freigabe-Dialogen den **rohen Befehl** (Pipes, `&&`,
`python -c "…"`) und kann ihn nicht lesen. Daraus folgt:

1. **Vor jedem Shell-Befehl ein Klartext-Satz** (deutsch), was er tut und wozu —
   *bevor* der Befehl läuft. Kein Befehl ohne Ankündigung.
2. **Einfache Befehle statt langer Ketten.** Kein `curl … | python -c "…"`,
   kein `cmd1 && cmd2 && cmd3` — solche Konstrukte werden vom Sicherheitssystem
   als unklar geflaggt und erzeugen unnötige Rückfragen. Stattdessen: Skript
   schreiben (`write_file`) und mit einem kurzen Aufruf starten.
3. **Nach dem Lauf in Klartext berichten**, was herauskam — nicht die Rohausgabe
   stehen lassen.
4. **Häufige harmlose Befehle** (`git add/commit`, `sync-rules.ps1`,
   Projekt-Tests) gehören in die Allowlist, damit sie nicht jedes Mal fragen:
   `hermes config set command_allowlist '[…]'` — nur mit Sebastians OK.

**Hintergrund:** Freigabe-Dialoge betreffen **ausschließlich Shell-Befehle** —
Datei-Schreibvorgänge (`write_file`, `patch`) lösen nie einen Dialog aus.
Modus: `approvals.mode: smart` (Standard) = harmlos → automatisch, riskant →
abgelehnt, unklar → Rückfrage.

### 6.8 Praxis-Kanon (Everlast-KI-News, Engineering-Team) — belegt

Quelle: Marcel (Engineering-Lead) in den Praxis-Blöcken der KI-News-Videos,
ausgewertet aus 32 Videos (`cache/scratch/everlast/marcel-TEIL-1..4.md`,
Konsolidat: 69 Praktiken). Diese Regeln sind übernommen, weil sie Agenten-Arbeit
nachweislich stabiler machen — nicht als Meinung, sondern als erprobte Praxis.

**Rollen & Modelle**
1. Plan-Ersteller, Plan-Prüfer und Ausführer sind **drei getrennte Sessions mit
   unterschiedlichen Modellen**. Das Prüf-Modell darf nie das Plan-Modell sein —
   sonst prüft es sich selbst.
2. Der **starke Planer** braucht nur wenige Nachrichten (Plan + Abnahme), der
   **Ausführer** viele. Also: teure Modelle für Planung/Prüfung, günstige für die
   Masse. Nicht alles auf das teuerste Modell legen.
3. **Subagenten laufen mit dem günstigen Modell**; das Denken bleibt beim
   Orchestrator.

**Isolation**
4. **Ein Issue = ein Worktree = ein Branch.** Agenten arbeiten nie direkt auf dem
   Haupt-Worktree. Jede Kopie ist wegwerfbar.
5. Unbekannte Modelle/Werkzeuge erst in einer **Sandbox** auf das echte Projekt
   loslassen.

**Auftragsqualität**
6. **Rückfragen vor dem Bau** (vgl. §6.2) sind der Bauvertrag — 200 Rückfragen
   sind billiger als ein falsch gebautes Feature.
7. **Scope-Treue:** Wer „Hero Section" beauftragt, will nicht die ganze Seite.
   Nur der beauftragte Umfang, Extras sind Bonus.
8. **Was nicht im Auftrag steht, wird nicht gebaut.**
9. **Ausgabeformat explizit vorgeben** (Text/Zahl/Datum/Boolean/Liste) — ohne
   Vorgabe kommt Fließtext.
10. Tests **vor** der Implementierung schreiben (müssen rot sein); grün = fertig.
11. **Verifikation gehört in den Auftrag**: der Ausführer testet selbst
    Ende-zu-Ende (jedes Formular, jeder Button, alle Breakpoints).

**Belegpflicht**
12. **Baseline messen, bevor optimiert wird**, Ergebnis gegen die Baseline
    abnehmen. Ohne Vorher/Nachher ist „besser" eine Behauptung (§ „Fertig ist,
    was verifiziert ist").
13. Bei Modell-/Werkzeugvergleichen: **identischer Prompt, leeres Verzeichnis je
    Kandidat**, mehrere Metriken (Dauer, Tokens, Kosten, Qualität) — nie nur eine.

**Hygiene**
14. `AGENTS.md`/`CLAUDE.md` **von Hand und kurz** halten. Belegt: KI-generierte
    Anleitungsdateien → ~3 % schlechtere Ergebnisse, ~20 % höhere Kosten;
    menschlich geschriebene → ~4 % besser. (Deckt sich mit §6.3.)
15. Dokumente agentengerecht als **Markdown** bereitstellen, nicht als PDF/Word.
16. Für jede wiederkehrende Fremd-API **einen Skill** bauen statt Doku im Kontext
    mitzuschleppen.
17. **Nicht pollen** — benachrichtigen lassen und die Wartezeit produktiv nutzen.
18. Leitplanken auf **Repo-Ebene** (Issues, Pull Requests, Branch Protection)
    statt Direkt-Commits auf `main`.
19. Für längere Vorhaben: **Epic + Sub-Issues**, im Auftrag die Issue-Nummer
    referenzieren (adressierbare Spur).

**Vollständiger Kanon:** `MARCEL-KANON.md` (Projekt-Wurzel) mit allen 69
Praktiken und den Video-/Zeitstempel-Quellen.
