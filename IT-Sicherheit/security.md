# 🛡️ IT-Sicherheit – Datenschutz & Sicherheitskonzept

> **Übergreifendes Thema** | Stand: 02.08.2026
> Gilt für: persönlichen KI-Agenten, Heimnetz, Geräte (Windows + Android)
> Nächster Schritt: Priorisierung & Umsetzung der offenen Punkte

---

## Übersicht: Drei Sicherheitsebenen

Das gesamte Sicherheitskonzept ist in drei Ebenen unterteilt – von der Netzwerk-Basis bis zur App-Sicherheit.

```
Ebene 1: Netzwerk & Geräte
    Router-Konfiguration · VPN · Norton · Android-Sicherheit
        ↓
Ebene 2: Agent-Sicherheit
    Authentifizierung · Passwort-Manager · Verschlüsselung · Injection-Schutz
        ↓
Ebene 3: Datenhoheit & Compliance
    DSGVO · Server-Standort · Biometrie · Chat-Export · Datenverschlüsselung
```

---

## 🔲 Status-Übersicht (Checkliste)

| # | Thema | Status | Priorität |
|---|---|---|---|
| **1.1** | Router-Konfiguration (Firewall, Ports, WLAN) | 🔴 Offen | Hoch |
| **1.2** | VPN-Strategie (WireGuard zwischen Handy/PC/Server) | 🔴 Offen | Hoch |
| **1.3** | Norton 360 – Einbindung prüfen | 🔴 Offen | Mittel |
| **1.4** | Android-Sicherheit (App-Berechtigungen, Micro/Kamera) | 🟡 Später | Niedrig |
| **2.1** | Authentifizierung (Fingerabdruck, PIN, Gesicht) | 🔴 Offen | Hoch |
| **2.2** | Passwort-Manager-Integration (Bitwarden/KeePass) | 🔴 Offen | Hoch |
| **2.3** | Prompt-Injection-Schutz | 🟡 Später | Mittel |
| **2.4** | Datenverschlüsselung in Vektor-DB (AES-256) | 🟡 Später | Mittel |
| **3.1** | DSGVO-Konformität – welche Daten in Cloud vs. lokal | 🟡 Später | Mittel |
| **3.2** | Chat-Export (ChatGPT, Gemini, Claude → Wissen einlesen) | 🔴 Offen | Hoch |
| **3.3** | Server-Standort (Hetzner DE / Azure Westeuropa) | 🟡 Später | Mittel |
| **3.4** | Biometrie für kritische Aktionen (pCloud, Passwort-Manager) | 🟡 Später | Niedrig |

---

## 1. Netzwerk & Geräte (Basis)

### 1.1 Router-Konfiguration
**Fragen zur Entscheidung:**
- WLAN: WPA3 oder WPA2? (WPA3 wenn Router es unterstützt)
- Firewall: Welche Ports müssen offen sein? (Nur Port 443 (HTTPS) für den Server)
- Gastnetz: IoT-Geräte ins separate WLAN?
- UPnP deaktivieren? (Sicherheitsrisiko)
- Router-Modell/-Hersteller? (Für spezifische Einstellungen)

**Nächster Schritt:** Router-Modell prüfen → Einstellungen dokumentieren → Härten

### 1.2 VPN-Strategie
**Vorschlag: WireGuard**
- Server-Seite: WireGuard auf dem Hetzner VPS (oder später Azure)
- Client-Seite: Handy (WireGuard-App) + PC (WireGuard-Client)
- Effekt: Verschlüsselter Tunnel zwischen allen Geräten, auch aus öffentlichem WLAN
- Vorteil: Open Source, schnell, geringer Akku-Verbrauch auf dem Handy

**Entscheidung nötig:**
- Eigener WireGuard-Server auf dem VPS?
- Oder Norton-VPN als einfachere Lösung?

### 1.3 Norton 360
**Was Norton bietet:**
- ✅ VPN (einfach, aber nicht selbst kontrolliert)
- ✅ Virenschutz (Windows + Android)
- ✅ Passwort-Manager (einfach, aber weniger flexibel als Bitwarden)
- ✅ App-Sicherheit auf Android
- ⚠️ App-Überwachung (kann den Agenten blockieren, wenn nicht konfiguriert)

**Entscheidung nötig:**
- Norton vollständig nutzen (inkl. VPN)?
- Oder Norton nur als Virenschutz + eigenes VPN (WireGuard)?
- Passwort-Manager: Norton oder Bitwarden (Open Source)?

### 1.4 Android-Sicherheit
- App-Berechtigungen: Mikrofon nur bei aktiver Nutzung
- Kamera nur für biometrische Prüfung
- Keine Hintergrund-Audio-Aufnahme ohne Zustimmung
- Android-Fingerabdruck-API für App-Entsperrung

---

## 2. Agent-Sicherheit

### 2.1 Authentifizierung
**Wie weist du dem Agenten nach, dass du es bist?**
- **Fingerabdruck** (Android-biometrisch, erste Wahl)
- **PIN/Passwort** (Fallback)
- **Gesichtserkennung** (optional, schwächer als Fingerabdruck)
- **Sitzungs-Token**: Nach Authentifizierung → Token für X Minuten gültig

**Entscheidung nötig:** Fingerabdruck + PIN-Fallback? Oder nur PIN?

### 2.2 Passwort-Manager-Integration
**Mögliche Integrationen:**
- **Bitwarden** (Open Source, eigene Server möglich, API vorhanden) ← Empfehlung
- **KeePass** (lokal, keine Cloud, aber kein Live-API-Zugriff)
- **Norton Password Manager** (in Norton enthalten)
- **Browser-eigener Manager** (Chrome/Edge – weniger sicher)

**Entscheidung nötig:** Welcher Passwort-Manager? Agent nur lesend oder auch schreibend?

### 2.3 Prompt-Injection-Schutz
- Bevor ein Prompt ans LLM geht: Prüfung auf bekannte Injection-Muster
- System-Prompt hart codiert (nicht überschreibbar durch User-Input)
- Output-Filter: Bevor der Agent eine Aktion ausführt, wird geprüft, ob der Befehl legitim ist
- **Tool-Zugriff**: Jedes Tool (Mail, Cloud, etc.) muss separat autorisiert werden

### 2.4 Datenverschlüsselung
- Vektor-DB: Embeddings + Metadaten verschlüsselt (AES-256-GCM)
- Konversationsverlauf: Optional löschbar nach X Tagen
- Lokale Audiodaten (STT): Bleiben auf dem Handy, nie unverschlüsselt in der Cloud
- Backup in der pCloud: Verschlüsseltes Archiv

---

## 3. Datenhoheit & Compliance

### 3.1 DSGVO-Konformität
**Grundsätze:**
- Keine Daten an US-Cloud-Dienste (OpenAI, Google, Meta)
- OpenRouter: DSGVO-konform (kein Training mit Nutzerdaten)
- Hetzner/Azure Westeuropa: DSGVO-konforme Rechenzentren
- Datenminimierung: Nur das speichern, was der Agent wirklich braucht
- Löschung auf Wunsch: Der Agent muss alle Daten vergessen können

**Entscheidung nötig:** Welche Daten bleiben lokal, welche gehen in die Cloud?

### 3.2 Chat-Export (Wissen einlesen)
**Warum:** Du hast 3 Jahre Chat-Verlauf in ChatGPT, Gemini, Claude – wertvolles Wissen für den Agenten.
**Möglichkeiten:**
- ChatGPT: Datenexport (Einstellungen → Daten exportieren → JSON)
- Gemini: Google Takeout → Gemini-Daten
- Claude: Kein Bulk-Export → manuell oder per Browser-Script
- **Ziel**: Exportierte `.json` in Vektor-DB einlesen → Agent kann auf das Wissen zugreifen

**Entscheidung nötig:** Welche Plattform zuerst exportieren? Browser-Script für Claude?

### 3.3 Server-Standort
- **Hetzner** (Nürnberg/Falkenstein, Deutschland) ← geplant für Phase 1
- **Azure Westeuropa** (Niederlande) ← geplant für später
- Beide DSGVO-konform

### 3.4 Biometrie für kritische Aktionen
- **Fingerabdruck**: Bei Zugriff auf Passwort-Manager, pCloud, Bezahlfunktionen
- **Android Biometric API**: Einfach integrierbar, sicher
- **Windows Hello**: Für PC-Zugriff

---

## 🎯 Nächste Schritte (priorisiert)

| Reihenfolge | Was | Aufwand |
|---|---|---|
| 1️⃣ | **Authentifizierungs-Strategie** – Fingerabdruck/PIN festlegen | ~15 Min |
| 2️⃣ | **VPN-Strategie** – WireGuard vs. Norton-VPN | ~15 Min |
| 3️⃣ | **Router-Konfiguration** prüfen und härten | ~30 Min |
| 4️⃣ | **Passwort-Manager** – Bitwarden oder Norton? | ~15 Min |
| 5️⃣ | **Chat-Export** von ChatGPT/Gemini starten | ~10 Min |
| 6️⃣ | Norton 360-Einbindung prüfen | ~15 Min |

---

## 🔧 Umsetzungs-Reihenfolge (wann)

- **Sofort (vor Agent-Start):** Authentifizierung, VPN, Router
- **Parallel zum Agent-Bau:** Passwort-Manager, Norton
- **Nach Agent-MVP:** Chat-Export, Biometrie, Verschlüsselung
- **Kontinuierlich:** DSGVO-Prüfung, Prompt-Injection-Schutz

---

*Dokumentiert von Cline (Agent) für Sebastian – Sicherheit als übergreifendes Thema*