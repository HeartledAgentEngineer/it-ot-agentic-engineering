<!--
  DIESE DATEI WURDE AUTOMATISCH GENERIERT (sync-rules.ps1)
  AENDERUNGEN IN DIESER DATEI WERDEN BEIM NAECHSTEN RUN UEBERSCHRIEBEN!
  Bitte aendere die globale CLAUDE.md im Hauptverzeichnis oder die lokale CLAUDE_EXTENDS.md.
-->

# 🚨 GLOBALE KI-DIREKTIVEN: AGENTEN-BETRIEBSSYSTEM
## Haupt-Workspace — Workspace Agentic Engineering

> [!CAUTION]
> ### 🔴 SICHERHEITS-LEITPLANKE: KONTROLLIERTER GIT-PUSH-WORKFLOW
> * Der KI-Agent darf **niemals autonom** und ohne Rücksprache einen `git push` im Hintergrund ausführen (Schutz vor automatischem Secrets-Leakage).
> * **Erlaubt:** Lokale `git commit`s zur Absicherung von Zwischenschritten.
> * **Vorgehen für Push:** Der Agent darf einen `git push` im Terminal vorschlagen und triggern. Der Befehl muss jedoch zwingend durch den Nutzer über den Bestätigungsdialog des CLI-Tools (Sandbox) manuell geprüft und freigegeben werden. Alternativ kann der Push manuell über TortoiseGit erfolgen.

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
* **Keine Phasen überspringen:** Phasen wie **Testing (Phase 5)**, **Refactor (Phase 7)** und **Commit/Aufräumen (Phase 8)** dürfen **NIEMALS** übersprungen werden. Verifikation, Testen, Verbessern und Aufräumen sind essenziell.
* **Ehrlichkeit bei Fehlern:** Wenn der Agent etwas vergessen hat oder ein Fehler unterlaufen ist, muss er dies offen und direkt kommunizieren ("Ich habe X vergessen...").
* **Kein unstrukturiertes Springen:** Der Agent achtet aktiv darauf, nicht unkontrolliert zwischen Planungen (Phase 3) und Ausführungen (Phase 4) hin- und herzuspringen. Phasenübergänge müssen immer erst per Dialog freigegeben werden.
* **Maximale Einbindung & Alignment-Priorität ("Grill me"):** Der Agent darf architektonische oder gestalterische Entscheidungen niemals selbstständig treffen oder raten. Er muss bei der kleinsten Unklarheit oder an wichtigen Gabelungen sofort ein "Grill-Me"-Alignment (Phase 2) vorschlagen, um dem Nutzer die volle Kontrolle als Architekt/Designer zu lassen.

---

## ⚙️ BEREICHS-SPEZIFISCHE DIREKTIVEN (EXTENDS & OVERRIDE)

* **Wenn in 01_IT-OT_Integration:**
  * **Namenskonventionen:** Präfixe einhalten (`b` für BOOL, `r` für REAL, `i` für INT, `di` für DINT, `ui` für UINT, `udi` für UDINT, `iStep` für Schrittketten).
  * **iStep-Schrittketten:** Zehner-Schritte (10, 20, 30...). Aktionen in Transitionen nur für Latch-Momente (Einfrieren von Encoder-Werten).
  * **Keine Online-Änderungen:** Der Agent liefert nur Code-Blaupausen. Das Einspielen, Kompilieren und der "Online Change" an der SPS erfolgen ausschließlich manuell durch Sebastian.
  
* **Wenn in 02_Softwareentwicklung_IT:**
  * **Aesthetics:** Moderne Designs, vibrant colors, harmonische Paletten, dark modes, Google Fonts. Keine Standard-Browser-Aesthetics.
  * **Technologien:** HTML/JS, Vite, React Native, Expo Go, Flask.
  * **SEO-Best-Practices:** Title-Tags, Meta-Descriptions, semantisches HTML, einzigartige IDs.

---

## 🔄 KI-CODING WORKFLOW (8 PHASEN NACH THORSTENSEN)

Für jedes Feature diesen Zyklus einhalten. Nach jeder Phase `/clear` (Context-Reset) durch den Nutzer!

* **Phase-Wechsel-Freigabe:** Ein Wechsel in eine neue Phase darf **NIEMALS** automatisch geschehen. Der Agent muss den Phasenwechsel explizit vorschlagen, eine kurze Einführung in die anstehende Phase geben (was ansteht und was gemacht werden soll) und dies über einen interaktiven Auswahl-Dialog (mit dem `ask_question` Tool) durch den Nutzer freigeben lassen.

1. **Phase 1 — Brainstorm:** Ideen sortieren, als `brainstorm.md` sichern.
2. **Phase 2 — Alignment:** "Grill me" phase. Alle Unklarheiten klären, als `alignment.md` sichern.
3. **Phase 3 — Planung:** Vertical Slice (Ende-zu-Ende) wählen, Teststrategie festlegen, als `plan.md` sichern.
4. **Phase 4 — Implementierung:** Nur den Plan abarbeiten, kein Scope-Creep.
5. **Phase 5 — Testing:** UX-Feedback geben, Bedienbarkeit prüfen.
6. **Phase 6 — Recap:** Erklärung & Diagramm durch KI (NIEMALS überspringen!).
7. **Phase 7 — Refactor:** Code vereinfachen, aufräumen (NIEMALS überspringen!).
8. **Phase 8 — Commit / PR:** Atomic Commits lokal machen. Markdown-Phasendateien löschen. Feierabend-Push manuell durch Nutzer!


<!-- LOKALE PROJEKT-ERWEITERUNGEN (EXTENDS) -->

# BEREICHS-ERWEITERUNG: AUTOMATISIERUNGSTECHNIK (OT)

Dieses Regelwerk erweitert die globalen KI-Direktiven um hochspezifische Richtlinien für TwinCAT 3 (IEC 61131-3).

---

## 1. BECKHOFF VARIABLEN-NAMENSKONVENTIONEN

Jede Variable muss streng nach Beckhoff-Sicherheits-Konventionen mit dem passenden Typ-Präfix deklariert werden:

* `b`  - BOOL (z. B. `bStart`, `bBereit`)
* `r`  - REAL (z. B. `rSollwert`, `rIstwert`)
* `i`   - INT (z. B. `iZaehler`, `iStep`)
* `di`  - DINT (z. B. `diPosition`, `diWinkelLatch`)
* `ui`  - UINT (z. B. `uiIndex`)
* `udi` - UDINT (z. B. `udiZaehler`)
* `t`  - TIME (z. B. `tVerzoegerung`)
* `s`  - STRING (z. B. `sFehlermeldung`)
* `st` - STRUCT (z. B. `stHMI_Data`)
* `fb` - FUNCTION_BLOCK (z. B. `fbHauptantrieb`)
* `e`  - ENUM (z. B. `eMaschinenZustand`)

---

## 2. ESTEP-SCHRITTKETTEN-KONVENTION (ENUM-BASIERT)

Deine Schrittketten müssen pragmatisch und deterministisch als Enum-Abläufe in `CASE eStep OF` (unter Verwendung von sprechenden Konstanten mit expliziter Zahlenzuweisung) entworfen werden:

* **Datentyp:** `eStep : E_State` (Enum abgeleitet von `DINT` / `INT`).
* **Zehner-Schritte:** Standard-Abläufe mit festen Nummern in 10, 20, 30, 40... deklarieren.
* **Flexibilität:** Lücken freihalten (z. B. 11, 12, 15), um später Zwischenschritte einfügen zu können.
* **Kommentare:** Jeder Schritt MUSS im Code kommentiert werden:
  `eFoerderband_An: (* [10] Förderband läuft *)`

---

## 3. LATCH-ARCHITEKTUR (Wert-Einfrierung)

Der Latch-Mechanismus ist das entscheidende Bindeglied zwischen Steuerfluss und schnellem Datenfluss (Esterel-Prinzip):

* **Das Prinzip:** Encoder- oder Messwerte werden exakt beim Sensor-Trigger eingefroren. Alle weiteren Schritte rechnen mit dem Latch-Wert, nicht mit dem Live-Encoder.
* **Die Ausnahme:** Das Einfrieren des Wertes erfolgt als **"Aktion in der Transition"** direkt im Umschalt-Moment. Das ist ein bewährtes Design-Pattern für schnelle Maschinen (700 Teile/Min):
  ```pascal
  IF bSensor AND NOT bSensorLast THEN
      nWinkelLatch := Encoder.nPosition;   (* Latch-Moment *)
      nNestNr      := NestDetekt.nAktuell;
      iStep        := 20;
  END_IF
  bSensorLast := bSensor;
  ```

---

## 4. DATEI-REGISTRIERUNGS-WORKFLOW (.PLCPROJ XML)

Wenn eine neue `.TcPOU` (Funktionsbaustein) oder `.TcDUT` (Struct/Enum) erstellt wird, muss diese zwingend in der XML-Projektdatei (`.plcproj`) registriert werden, damit sie in der XAE Shell sofort sichtbar ist:

```xml
<Compile Include="POUs\FB_Name.TcPOU">
  <SubType>Code</SubType>
</Compile>
```
*Der Pfad der `.plcproj` liegt im PLC-Unterordner des Maschinenprojekts.*

