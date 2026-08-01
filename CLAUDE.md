# 🚨 GLOBALE KI-DIREKTIVEN: AGENTEN-BETRIEBSSYSTEM
## Haupt-Workspace — Workspace Agentic Engineering

> [!CAUTION]
> ### 🔴 SICHERHEITS-LEITPLANKE: KONTROLLIERTER GIT-PUSH-WORKFLOW
> * Der KI-Agent darf **niemals autonom** und ohne Rücksprache einen `git push` im Hintergrund ausführen (Schutz vor automatischem Secrets-Leakage).
> * **Erlaubt:** Lokale `git commit`s zur Absicherung von Zwischenschritten.
> * **Vorgehen für Push:** Der Agent darf einen `git push` ausschließlich vorschlagen — nie selbst triggern oder ausführen. Sebastian entscheidet, ob er den Push manuell (z. B. über TortoiseGit oder `git push` im Terminal) durchführt oder den Agenten per expliziter Aufforderung damit beauftragt. Der Bestätigungsdialog des CLI-Tools (Sandbox) dient dabei der Sicherheitsprüfung, ersetzt aber nicht die manuelle Entscheidung.

---
---

## 🏛️ ARCHITEKTUR & WORKSPACE-KONSTRUKT

Dieser Workspace teilt sich in zwei Hauptbereiche auf deinem lokalen PC:

```
 workspace agentic engineering\
  ├── 01_IT-OT_Integration\             <-- BEREICH 1: IT-OT Schnittstelle & Digital Twin (TwinCAT & Node.js)
  │    └── TwinCAT Projekts\            <-- SPS-Code & Node.js ADS-WebSocket-Bridge
  │
  └── 02_Softwareentwicklung_IT\        <-- BEREICH 2: Reine IT Software-Entwicklungen
       ├── concertify\                  <-- Concertify Web App (Flask)
       ├── Concertify Android Prototyp\ <-- Concertify Mobile App (React Native Prototyp)
       ├── typeFREE\                    <-- typeFREE App (Windows Client & Android Companion)
       ├── RAG-Systeme\                 <-- RAG Wissensdatenbank (Python/pgvector)
       ├── document_automation\         <-- PDF-Dokumentengenerator (Node.js)
       └── eichhoernchen_spiel\         <-- Canvas-Spaßprojekt (Party-Quick-Prototype)
```

---

## 🛡️ ANTIGRAVITY-SICHERHEITSPROTOKOLL (SOP) FÜR DATEIZUGRIFFE

Vor jedem Zugriff auf Dateien muss dem Nutzer im Chat folgendes Protokoll vorgelegt und freigegeben werden:

### 1. Datei lesen (Reading)
* **Warum:** Welcher Erkenntnisgewinn für die aktuelle Teilaufgabe?
* **Wie:** Genauer Pfad der Datei.
* **Weshalb:** Warum reichen bisher eingelesene Daten nicht aus?
* **Wie sicher:** Bestätigung, dass es ein reiner, risikofreier Lesevorgang (Read-Only) ist.

### 2. Datei bearbeiten / neu erstellen (Writing)
* **Warum:** Was bewirkt die Änderung/neue Datei und welches Problem löst sie?
* **Wie:** Genaue Zeilen und zu ersetzender Code vorab als Diff präsentieren.
* **Weshalb:** Warum ist dieser Eingriff die sauberste Lösung (Vermeidung von Code-Bloat)?
* **Wie sicher:** Genaue Risikobewertung (z. B. Gefahr von Syntax- oder Speicherfehlern).

---

## 🧭 AGENTEN-VERHALTENSREGELN (Interaktion, Sprache & Kontext)

> Diese Regeln gelten für alle Unterprojekte dieses Workspaces und für alle Coding-Tools (Claude Code, Antigravity, Cursor, Codex).

### Sprache
- Immer auf **Deutsch** antworten.
- Erklärungen einfach halten — kein Fach-Jargon ohne Erklärung.

### Arbeitsweise
- Jeden Schritt erst erklären, dann ausführen.
- Nie mehrere große Änderungen auf einmal ohne Rückfrage.

### Vor jeder Entscheidungsfrage (Pflicht-Briefing)

Bevor ich eine Auswahl präsentiere (Ja/Nein, Option A/B, Bestätigung), MUSS ich zuerst folgendes ausgeben — ohne Ausnahme:

**🔍 Was wird gemacht?** — Konkrete Beschreibung der geplanten Aktion (1–2 Sätze)
**🎯 Warum wird es gemacht?** — Welches Problem wird gelöst / welches Ziel erreicht
**🚫 Was wird NICHT gemacht?** — Was bleibt unverändert, was wird nicht angefasst
**🛡️ Sicherheitsprinzipien:** kein `git push` · keine Online-SPS-Änderung · Risikobewertung (Keins / Gering / Mittel / Hoch)

Erst DANACH die eigentliche Auswahlfrage stellen.

### Workflow-Disziplin (Kontext-Hygiene)

Am Ende jeder Workflow-Phase (siehe 8-Phasen-Workflow unten) **immer** folgendes ausgeben:

---
✅ **Phase abgeschlossen.**
👉 Bitte jetzt `/clear` ausführen, um den Kontext sauber zu halten.
📌 Nächste Phase: [Name] — Slice so klein wie möglich halten!
---

- Slices immer so klein wie möglich schneiden: lieber 2 kleine Aufgaben als 1 große.
- Ziel: Kontext schlank halten — am stärksten arbeiten die Modelle bei wenig, präzisem Kontext.

### Phasen-Disziplin & Umgang mit Ablenkungen/Abweichungen

* **Themen-Abweichungen abfangen:** Wenn der Nutzer während einer Phase vom Thema abweicht oder neue Ideen einbringt, darf der Agent nicht sofort mitspringen. Stattdessen wird ein neuer To-Do- oder Brainstorming-Punkt erstellt, um später darauf zurückzukehren. Der Fokus der aktuellen Phase bleibt geschützt.
* **Keine Phasen überspringen:** Phasen wie **Testing (Phase 5)**, **Refactor (Phase 7)** und **Commit/Aufräumen (Phase 8)** dürfen **NIEMALS** übersprungen werden. Verifikation, Testen, Verbessern und Aufräumen sind essenziell. Dazu zählt die Fremdprüfung durch `/critic` — ein sauberes Protokoll ist kein Ersatz für Tests, und ein leeres Protokoll ist keine Freigabe.
* **Ehrlichkeit bei Fehlern:** Wenn der Agent etwas vergessen hat oder ein Fehler unterlaufen ist, muss er dies offen und direkt kommunizieren ("Ich habe X vergessen...").
* **Kein unstrukturiertes Springen:** Der Agent achtet aktiv darauf, nicht unkontrolliert zwischen Planungen (Phase 3) und Ausführungen (Phase 4) hin- und herzuspringen. Phasenübergänge müssen immer erst per Dialog freigegeben werden.
* **Maximale Einbindung & Alignment-Priorität ("Grill me"):** Der Agent darf architektonische oder gestalterische Entscheidungen niemals selbstständig treffen oder raten. Er muss bei der kleinsten Unklarheit oder an wichtigen Gabelungen sofort ein "Grill-Me"-Alignment (Phase 2) vorschlagen, um dem Nutzer die volle Kontrolle als Architekt/Designer zu lassen.

---

## ⚙️ BEREICHS-SPEZIFISCHE DIREKTIVEN (EXTENDS & OVERRIDE)

* **Wenn in 01_IT-OT_Integration:**
  * **Namenskonventionen:** Präfixe einhalten (`b` für BOOL, `r` für REAL, `i` für INT, `di` für DINT, `ui` für UINT, `udi` für UDINT, `iStep` für Schrittketten).
  * **iStep-Schrittketten:** Zehner-Schritte (10, 20, 30...). Aktionen in Transitionen nur für Latch-Momente (Einfrieren von Encoder-Werten).
  * **Keine Online-Änderungen:** Der Agent liefert nur Code-Blaupausen. Das Einspielen, Kompilieren und der "Online Change" an der SPS erfolgen ausschließlich manuell durch Sebastian.
  * **Kein Fremdmodell für SPS-Code:** `/critic` schickt Code an Google. Im kostenlosen Tier nutzt Google die Inhalte zur Produktverbesserung. **SPS-, OT- und Kundencode wird niemals über `/critic` geprüft** — nur Projekte aus `02_Softwareentwicklung_IT`.
  
* **Wenn in 02_Softwareentwicklung_IT:**
  * **Aesthetics:** Moderne Designs, vibrant colors, harmonische Paletten, dark modes, Google Fonts. Keine Standard-Browser-Aesthetics.
  * **Technologien:** HTML/JS, Vite, React Native, Expo Go, Flask.
  * **SEO-Best-Practices:** Title-Tags, Meta-Descriptions, semantisches HTML, einzigartige IDs.

---

## 🔄 KI-CODING WORKFLOW (8 PHASEN NACH THORSTENSEN)

Für jedes Feature diesen Zyklus einhalten. Nach jeder Phase `/clear` (Context-Reset) durch den Nutzer!

* **Phase-Wechsel-Freigabe:** Ein Wechsel in eine neue Phase darf **NIEMALS** automatisch geschehen. Der Agent muss den Phasenwechsel explizit vorschlagen, eine kurze Einführung in die anstehende Phase geben (was ansteht und was gemacht werden soll) und dies über einen interaktiven Auswahl-Dialog (mit dem `ask_question` Tool) durch den Nutzer freigeben lassen.

1. **Phase 1 — Brainstorm:** Ideen sortieren, als `brainstorm.md` sichern.
1b. **Phase 1b — Pre-Alignment (grillAnAgent):** `node .claude/skills/grillAnAgent/grillAnAgent.mjs brainstorm.md` ausführen. Der Host lädt Haiku als Kritiker ein. Bei vollem Konsens (keine strittigen Punkte) → einmal abnicken, Phase 2 überspringen. Bei Uneinigkeit → nur die strittigen Punkte gehen in Phase 2.
2. **Phase 2 — Alignment:** "Grill me" phase. Nur noch ungeklärte Punkte aus grillAnAgent klären, als `alignment.md` sichern.
3. **Phase 3 — Planung:** Vertical Slice (Ende-zu-Ende) wählen, Teststrategie festlegen, als `plan.md` sichern. **Vor Freigabe der Implementierung (Phase 4) muss der Plan durch `/critic` (Fremdprüfung) gegengeprüft werden. Befunde auswerten, Plan ggf. anpassen. Erst nach Freigabe durch Sebastian geht es in Phase 4.**
4. **Phase 4 — Implementierung:** Nur den Plan abarbeiten, kein Scope-Creep.
5. **Phase 5 — Testing:** UX-Feedback geben, Bedienbarkeit prüfen. Danach Fremdprüfung durch ein zweites KI-Modell via `/critic`. Befunde werden vorgelegt, Sebastian entscheidet je Punkt — nie automatisch beheben.
6. **Phase 6 — Recap:** Erklärung & Diagramm durch KI (NIEMALS überspringen!).
7. **Phase 7 — Refactor:** Code vereinfachen, aufräumen (NIEMALS überspringen!). **Dokumentation prüfen: READMEs (Root, Bereich, Projekt) auf Aktualität – Stack, APIs, Architektur, Mermaid-Diagramme – bei relevanten Änderungen (neue APIs, Architektur-Entscheidungen, Workflow-Änderungen) aktualisieren.** Danach `/critic` als Gegenprobe: Hat das Aufräumen etwas kaputtgemacht?
8. **Phase 8 — Commit / PR:** Atomic Commits lokal machen. Markdown-Phasendateien löschen. **Nach dem Commit zwingend fragen: „Soll ich pushen (ja/nein)?" — bei 'ja' führt Sebastian den Push selbst aus (z. B. `git push` im Terminal oder TortoiseGit), da der Agent keinen autonomen Push ausführen darf.**
