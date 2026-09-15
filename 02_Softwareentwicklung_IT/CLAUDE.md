<!--
  DIESE DATEI WURDE AUTOMATISCH GENERIERT (sync-rules.ps1)
  AENDERUNGEN IN DIESER DATEI WERDEN BEIM NAECHSTEN RUN UEBERSCHRIEBEN!
  Bitte aendere die globale AGENTS.md im Hauptverzeichnis oder die lokale CLAUDE_EXTENDS.md.
-->

> **Basis-Regelwerk:** Es gelten weiterhin die Kernregeln aus `../AGENTS.md` (Workspace-Wurzel).
> Sie sind hier bewusst nicht kopiert, damit es nur eine Quelle gibt. Claude Code zieht sie ueber die Wurzel-CLAUDE.md mit herein, Cline liest sie nativ.

<!-- LOKALE PROJEKT-ERWEITERUNGEN (EXTENDS) -->

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

