# Status: Master-Schalter & OrbitDesk

> **Stand:** v0.6.0 / 06. November 2026  
> **Komponente:** Code-Leitwarte, OrbitDesk Steuerzentrale & Multi-Agenten-Orchestrator (`02_Softwareentwicklung_IT/master-schalter`)  
> **System-Status:** **STABIL & VERIFIZIERT (Alle neuen OrbitDesk-Module getestet, 51/51 Tests grün, alle Module fehlerfrei importierbar)**

---

## 1. Aktive Kernfunktionen (OrbitDesk & Leitwarte)

Die OrbitDesk-Erweiterung baut die schlanke Leitwarte zur autonomen Steuerzentrale für parallele Coding-Projekte und Agenten (**Antigravity**, **Hermes**, **Codex**, **Claude Code**) aus:

* **Versionierte Projekt-Goals & Fortschritt (`ziele.py`):**
  * Datenklasse `Goal` mit Optimistic Locking (CAS / Versionsprüfung) unter `~/.master-schalter/ziele/<thema>.json`.
  * Felder: `titel`, `ziel_text`, `abnahmekriterien`, `entscheidungen`, `offene_aufgaben`, `fortschritt`, `naechster_schritt`, `gewuenschte_rolle`, `tatsaechliche_zustaendigkeit`, `wartegrund`, `status`.
  * Getrennte Nachweise: `zustellung_belegen` (`zustellungs_nachweis` / delivered) und `annahme_quittieren` (`annahme_ack` / accepted) zur Verhinderung doppelter Ausführung.
* **Hermes- & Budgetschutz („Hamster-Einstellungen“, `kosten_budget.py`):**
  * Token-Explosionsschutz für teure Modelle (z. B. GPT-6 Sol / GPT-6.1 Sol).
  * Zwingende Delegationspflicht (`DelegationsPflichtFehler`): Blockiert Sol und Opus bei Dokumenten-Scans, Datei-Durchsuchungen und Routineaufgaben > 15.000 Tokens; erzwingt Delegation an Luna/Flash.
  * Budget-Status mit Warnschwelle (80 %) und Stoppgrenze für Azure Foundry und OpenRouter.
* **OrbitDesk MCP-Server (`mcp_server.py`):**
  * JSON-RPC-MCP-Server über `stdio` für den Personal AI Agent Code-Chat und Desktop-Clients.
  * Tools: `orbitdesk_status`, `orbitdesk_goal_lesen`, `orbitdesk_goal_aktualisieren`, `orbitdesk_chat_wecken`, `orbitdesk_kosten_status`.
* **Sprachsteuerungs-Zentrale („Telefonagent“, `sprach_zentrale.py`):**
  * Text-zu-Sprache-optimierte Aggregationen:
    * `was_laeuft_wo()`: Aktive Worker, Projekte, Rollen und Status.
    * `offene_pruefungen_und_blocker()`: Anstehende Prüfungen und Wartegründe.
    * `fragen_an_sebastian()`: Ungeklärte Fragen und manuelle Entscheidungen.
    * `thema_ansage(thema)`: Kompakte Projektübersicht.
* **Robuster Antigravity-Chat-Weckdienst (`agy_senden.py`, `assistent.py`):**
  * Automatische Erneuerung abgelaufener Port- und Token-Informationen aus der Umgebung (`agy-server.json`).
  * Klare Unterscheidung: `GEWECKT`, `POSTFACH_BEREIT`, `NICHT_ERREICHBAR`, `FEHLER`.
  * Kein stummes Verschlucken von Verbindungsfehlern mehr.
* **Multi-Plattform Limit-Monitor (`signale.py`):**
  * Taktet im 5-Sekunden-Rhythmus alle 4 KI-Plattformen ab.
  * Zeigt rollierende 5h- und Wochenfenster für **Claude Pro** und **OpenAI Codex (ChatGPT Plus)** inklusive exakter Reset-Zeiten.
  * Liest den Status von **Google Antigravity & Argon** dynamisch aus (Argon-Limitierung auf 100 % wird erkannt und auf Gemini 3.8 Flash umgestellt).
  * Zeigt Guthaben und Verfügbarkeit von **OpenRouter (DeepSeek V4.1 Flash)**.
* **Kaskaden-Matrix & Themen-Workflows (`matrix_konfiguration.py`, `modi.py`):**
  * Zuordnung der Rollen *Thinker (Master)*, *Reviewer (Prüfer)* und *Worker (Ausführer)* über die 4 Lagen (Lage 1, 2A, 2B, 3).
  * Presets: *Integrative Maschine* (Claude Opus 5.5 Master / Gemini 3.8 Flash Worker), *Antigravity & Argon*, *Gemini 3.8 Flash Fokus*, *Standard*.
* **Übergabe-Pipeline (`uebergabe.py`):**
  * Schnürt strukturierte, manipulationssichere `.md`-Übergabepakete nach `.hermes/uebergabe/`.
  * Integriert das versionierte Goal-Paket inklusive Fortschritt, Abnahmekriterien und Entscheidungen.
* **Chat-Erkennung (`chat_discovery.py`):**
  * Findet automatisch aktive Sitzungen von Antigravity, Claude Code und Codex und ordnet sie neuen Themen zu.

---

## 2. Ressourcen & Performance-Messung

Gemessene Werte im Produktivbetrieb (Windows 11):

| Komponente | Executable | RAM-Verbrauch | CPU-Last (Idle) | Status |
|---|---|---|---|---|
| **Haupt-Dashboard** | `master-schalter-gui.exe` | **~3,15 MB** | **0,00 %** | Aktiv (`Responding: True`) |
| **Taskleisten-Tray** | `master-leiste-gui.exe` | **~3,56 MB** | **0,00 %** | Aktiv (`Responding: True`) |

* Keine blockierenden Event-Loops: Hintergrundaktualisierungen laufen entkoppelt in Worker-Threads (`uebersicht_modell.py`).
* Instanz-Sperren (`uebersicht.lock`, `leiste.lock`) verhindern Doppelstarts zuverlässig.

---

## 3. Bedienung & Start-Wege

### A. Per Doppelklick (Desktop)
Auf dem Windows-Desktop liegt die Verknüpfung **`Master-Schalter.lnk`**:
* Führt `masterschalter.cmd` aus, räumt alte Locks auf und startet Leiste & Dashboard frisch.

### B. In der PowerShell (`masterschalter.ps1`)
```powershell
# Standard: Startet bzw. startet sauber neu
.\masterschalter.ps1

# Nur Status abfragen (zeigt PIDs und Befehle)
.\masterschalter.ps1 -Status

# Nur Leiste oder nur Übersicht starten
.\masterschalter.ps1 -NurLeiste
.\masterschalter.ps1 -NurUebersicht

# Beenden ohne Neustart
.\masterschalter.ps1 -Stop
```

### C. Im Windows-Autostart (`shell:startup`)
* `Master-Schalter.lnk` -> Startet das Dashboard beim Windows-Login.
* `Master-Schalter-Leiste.lnk` -> Startet das Tray-Symbol beim Windows-Login.

### D. Kommandozeile (`masterwechsel`)
```powershell
masterwechsel status            # Kompakter Terminal-Status
masterwechsel profil <thema>    # Rollenprofil eines Themas anzeigen
masterwechsel master-setzen <thema> <master>  # Master wechseln
masterwechsel goal <thema>      # Versioniertes Goal abfragen
masterwechsel goal-setzen <thema> --titel ... # Goal aktualisieren
masterwechsel kosten [<thema>]  # Budget- und Modellkosten einsehen
masterwechsel sprache [was-laeuft-wo|pruefungen|fragen|ansage] # Sprachausgabe
masterwechsel mcp               # OrbitDesk MCP-Server über stdio starten
```

---

## 4. Modul-Integrität (`src/master_schalter/`)

Alle 52 Module sind aktiv, syntaktisch fehlerfrei und importierbar:
* **Kern:** `zustand.py`, `modi.py`, `matrix_konfiguration.py`
* **Signale:** `signale.py`, `claude_messen.py`, `codex_messen.py`
* **Übergabe:** `uebergabe.py`, `ack.py`, `abgabe_nachweis.py`, `postfach.py`
* **Oberfläche:** `uebersicht.py`, `uebersicht_modell.py`, `uebersicht_tabelle.py`, `leiste.py`, `symbol.py`
* **CLI:** `cli.py`
