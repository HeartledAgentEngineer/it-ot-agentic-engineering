# Handy-Setup Checkliste (Termux + SSH)

> Folge diesen Schritten **auf deinem Handy**.
> Nach jedem Schritt sagst du mir Bescheid, wie weit du bist.

---

## Schritt 1: F-Droid + Termux installieren

- [ ] **F-Droid** installieren (Store für Open-Source-Apps)
  - Browser öffnen → `https://f-droid.org` → APK herunterladen → installieren
- [ ] **Termux** aus F-Droid installieren
  - F-Droid öffnen → "Termux" suchen → installieren
- [ ] Termux öffnen, warten bis Paketlisten geladen sind

---

## Schritt 2: Pakete installieren

In Termux eingeben:
```bash
pkg update && pkg upgrade -y
pkg install -y python python-pip git openssh tmux
```

- [ ] `pkg update && pkg upgrade -y` ausgeführt
- [ ] `pkg install -y python python-pip git openssh tmux` ausgeführt

---

## Schritt 3: Projekt klonen

```bash
cd ~
git clone https://github.com/HeartledAgentEngineer/it-ot-agentic-engineering.git
cd it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent/backend
```

- [ ] Projekt geklont

---

## Schritt 4: API-Key eintragen

```bash
cp .env.example .env
nano .env
```

Dann in `.env` folgende Werte setzen:
```
OPENROUTER_API_KEY=sk-or-v1-dein-echter-key-hier
```

- [ ] `.env` erstellt und API-Key eingetragen

---

## Schritt 5: Dependencies installieren

```bash
pip install -r requirements.txt
```

- [ ] `pip install` abgeschlossen (dauert auf Handy 5-15 Minuten)

---

## Schritt 6: Backend testen

```bash
cd ~/it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Siehst du `Uvicorn running on http://0.0.0.0:8080`? Dann läuft es!

- [ ] Backend gestartet ✅

---

## Schritt 7: SSH einrichten (Vom PC steuern)

```bash
# In Termux:
sshd
ifconfig
# → IP-Addresse notieren (z.B. 192.168.178.XX)
```

- [ ] `sshd` gestartet
- [ ] IP-Adresse notiert: `________`

---

## Schritt 8: tmux für dauerhaften Betrieb

```bash
# In Termux:
cd ~/it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent/backend
tmux new -s agent
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Dann `Ctrl+B` dann `d` um Session zu trennen.

- [ ] tmux-Session läuft dauerhaft

---

## ✅ Fertig!

Sag mir Bescheid wenn du bei Schritt 1-8 angekommen bist, dann:
- Testen wir die Verbindung vom PC aus per SSH
- Ich passe die URL im Frontend an
- Du öffnest die Chat-Oberfläche auf dem PC und chattest mit deinem Handy