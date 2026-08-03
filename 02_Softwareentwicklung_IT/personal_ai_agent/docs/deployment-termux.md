# 📱 Deployment auf Android (Termux) – SSH + tmux

> **Ziel:** Das Backend läuft dauerhaft auf dem Handy als Server.
> PC/Handy-Clients greifen per WLAN (Heimnetz) darauf zu.

---

## 1. 🔧 Voraussetzungen auf dem Handy

### Termux installieren
1. [F-Droid](https://f-droid.org) installieren (nicht aus Play Store – dort ist Termux veraltet)
2. In F-Droid: **Termux** suchen und installieren
3. Öffnen und initiale Pakete laden lassen

### Pakete installieren
```bash
pkg update && pkg upgrade -y
pkg install -y python python-pip git openssh tmux
```

### Projekt klonen
```bash
cd ~
git clone https://github.com/HeartledAgentEngineer/it-ot-agentic-engineering.git
cd it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent/backend
```

### Python-Dependencies installieren
```bash
pip install -r requirements.txt
```

### .env erstellen
```bash
cp .env.example .env
nano .env
# → OPENROUTER_API_KEY hier eintragen!
```

---

## 2. 📡 SSH-Zugriff einrichten (Option B)

### Auf dem Handy (Termux):
```bash
# SSH-Server starten
sshd

# IP-Adresse des Handys finden
ifconfig
# → Notiere die IP (z.B. 192.168.178.XX)
```

### Vom PC aus verbinden:
```bash
ssh -p 8022 <handy-ip>
# Passwort: dein Termux-Passwort (vorher mit `passwd` gesetzt)
```

---

## 3. 🔄 Dauerhafter Betrieb mit tmux (Option D)

### tmux-Session starten (auf dem Handy in Termux):
```bash
cd ~/it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent
tmux new -s agent
```

### Innerhalb der tmux-Session: Backend starten
```bash
# WICHTIG: --app-dir backend ist nötig, damit Python das 'app'-Modul findet
cd ~/it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --app-dir backend
```

### Vom PC aus in die tmux-Session schauen:
```bash
ssh -p 8022 <handy-ip>
cd ~/it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent
tmux attach -t agent
# → Siehst live, was das Backend loggt
```

### Wichtige tmux-Befehle:
| Taste | Funktion |
|-------|----------|
| `Ctrl+B` dann `d` | Session trennen (läuft weiter) |
| `Ctrl+B` dann `c` | Neues Fenster |
| `Ctrl+B` dann `0-9` | Fenster wechseln |
| `tmux ls` | Alle Sessions anzeigen |
| `tmux kill-session -t agent` | Session beenden |

---

## 4. 🌐 Zugriff von PC / Handy-Clients

### Backend läuft auf dem Handy:
| Gerät | URL |
|-------|-----|
| **PC im Heimnetz** | `http://192.168.178.XX:8080` |
| **Handy (lokal, Termux)** | `http://localhost:8080` |
| **API-Docs** | `http://192.168.178.XX:8080/docs` |

### Frontend öffnen:
1. Einfach `frontend/index.html` im Browser öffnen
2. Oder auf einen einfachen HTTP-Server legen:
   ```bash
   # Python-Server für Frontend
   cd frontend && python -m http.server 3000
   ```
3. Adresse im Browser: `http://localhost:3000`

**API_BASE in `frontend/app.js` anpassen:**
```javascript
// Für PC-Entwicklung (Backend läuft auf Handy)
const API_BASE = 'http://192.168.178.XX:8080';
// ODER für lokalen PC-Test (Backend läuft auf PC)
// const API_BASE = 'http://localhost:8080';
```

---

## 5. 🔄 Update-Prozess

### Wenn sich der Code ändert:
```bash
# Vom PC aus:
ssh -p 8022 <handy-ip>
cd ~/it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent
git pull

# Backend neustarten:
tmux attach -t agent
# → Ctrl+C drücken
# → Pfeil Hoch (letzten Befehl) → Enter
# → Ctrl+B dann d (trennen)
```

---

## 6. 🔒 Sicherheitshinweise

| Punkt | Maßnahme |
|-------|----------|
| **API-Key** | Liegt NUR in `.env` auf dem Handy, nie auf dem PC |
| **SSH-Port** | 8022 (nicht der Standard 22) – schwerer zu scannen |
| **Heimnetz** | Backend nur im lokalen Netz (kein Port-Forwarding) |
| **Kein HTTPS** | Im Heimnetz nicht nötig – bei Fernzugriff via VPN |
| **tmux** | Server läuft auch wenn SSH-Verbindung abbricht |
| **Zugriff** | Nur autorisierte Geräte im Heimnetz |