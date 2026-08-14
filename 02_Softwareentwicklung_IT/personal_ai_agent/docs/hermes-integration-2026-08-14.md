# Hermes als Coding-Agent anbinden — Befunde vom 14.08.2026

> Ergebnis einer Nacht mit vielen Sackgassen. Der Zweck dieser Datei ist,
> die Sackgassen genauso festzuhalten wie den gangbaren Weg — damit sie
> nicht in zwei Wochen ein zweites Mal durchlaufen werden.

---

## 1. Was Hermes ist

Eine fertige Android-App (`com.hermesagent.android`, Google Play, Entwickler
„Hen Works", seit Mai 2026). Kein Teil dieses Projekts, kein selbst gebauter
Code. Sie bringt einen eigenen Agenten mit: eingebautes Terminal, eigenes
Gedächtnis, eigene Modellanbindung. Läuft hier mit `deepseek-v4-flash-0731`
über denselben OpenRouter-Zugang wie der Agent.

**Rolle im Vorhaben:** Werkzeug zum Bauen, nicht Gesprächspartner. Die
Oberfläche von Hermes ist für den Alltag ungeeignet — Diktieren funktioniert
darin nicht. Bedient werden soll später ausschließlich die eigene Oberfläche.

---

## 2. Der Kernbefund

**Hermes erreicht den laufenden Agent-Server auf `127.0.0.1:8080`.**
Live bestätigt am 14.08.2026: `GET /api/health` liefert die Antwort des
Servers in Hermes' eigener Sitzung.

Das ist die Grundlage für alles Weitere, weil daraus folgt:

* Die **Datenbank muss nicht kopiert werden**. `memory.db` (124 MB) und
  `memory.vektoren.f32` (127 MB) bleiben, wo sie sind. Hermes fragt über
  HTTP: `/api/archiv/suche`, `/api/memory`, `/api/chat`.
* Es gibt weiterhin **eine** Wahrheit statt zwei Kopien, die auseinanderlaufen.
* Der **API-Schlüssel bleibt in Termux**. Hermes braucht `backend/.env` nicht,
  weil es den Server nicht selbst startet, sondern nur mit ihm spricht.
* Der Weg **überlebt den Umzug zu Azure**: Dann ändert sich die URL, sonst nichts.

Android trennt Apps beim **Dateisystem** streng voneinander, beim **lokalen
Netzwerk** aber nicht. Genau diese Asymmetrie trägt das Ganze.

---

## 3. Was Hermes kann und was nicht

Auf direkte Nachfrage genannt:

| Fähigkeit | Vorhanden |
|---|---|
| terminal, file, search, session_search | ja |
| memory, todo, delegation, skills | ja |
| **cronjob** — geplante Jobs, z. B. alle 30 min, je in frischer Sitzung | **ja** |
| **eingehender HTTP-Server / Webhook** | **nein** |

Wörtlich: *„There's no explicit inbound HTTP server tool in my toolset."*

**Folge für die Architektur:** Der eigene Server kann Hermes **nicht** aufrufen.
Nur Hermes kann von sich aus fragen. Jede Lösung muss mit dieser Richtung
arbeiten, nicht gegen sie.

Nebenbefund: Ein zweiter Port (`127.0.0.1:43089`) lauscht auf dem Gerät,
antwortet aber nicht auf HTTP. Nicht weiter verfolgt.

---

## 4. Sackgassen — nicht wiederholen

### 4.1 Dateien zwischen Termux und Hermes kopieren

Gescheitert, endgültig. Der Versuch ging über den geteilten Speicher:

```bash
cp ~/.../backend/.env /storage/emulated/0/Documents/env_temp/dotenv_temp.txt
chmod 644 /storage/emulated/0/Documents/env_temp/dotenv_temp.txt
```

Die Datei entsteht, ist aber für Hermes nicht lesbar. `ls -la` zeigt warum:

```
-rw-rw---- 1 u0_a323 media_rw 457 dotenv_temp.txt
```

**Der `chmod` verpufft wirkungslos.** `/storage/emulated/0` läuft seit
Android 10 über eine FUSE-Schicht (MediaProvider), die eigene Rechte erzwingt
und `chmod` klaglos schluckt, ohne es umzusetzen. Termux schreibt als
`u0_a323`, Hermes liest als `u0_a320` — andere App, kein Zugriff.

Andere Apps sehen den **Verzeichniseintrag** (Name, Größe), können die Datei
aber nicht **öffnen**. Das führt in die Irre: Hermes meldete erst „457 Bytes
gefunden", danach „Verzeichnis leer".

Auch nicht gangbar:
* `~/storage/shared/...` — derselbe Pfad, dieselbe Sperre
* Hermes' eigener `Android/data/`-Ordner — existiert für die App nicht auffindbar
* Windows-Explorer über MTP — sieht private App-Ordner grundsätzlich nicht

**Der einzige offizielle Weg wäre das Share-Sheet (Storage Access Framework),
also Teilen aus einem Dateimanager heraus.** Erfordert Handgriffe am Gerät.
Wurde nicht zu Ende geführt, weil der HTTP-Weg das Bedürfnis vollständig
erledigt: Es muss gar keine Datei transportiert werden.

### 4.2 Bridge-Server bauen lassen

Hermes begann zweimal von sich aus, einen HTTP-Bridge-Server zwischen sich und
Termux zu schreiben — obwohl der Agent-Server auf Port 8080 längst genau das
tut. Beide Male gestoppt. Nichts davon ist installiert oder aktiv.

Reste, falls sie irgendwo auftauchen: `bridge_server.py` und
`memory_store.json` in Hermes' Sandbox unter `Documents/hermes_bridge/`
sowie `~/agent_project/bridge/`. Ohne Belang, aber gut zu wissen.

**Lehre:** Hermes trifft eigenständig Architekturentscheidungen und baut
sofort los. Aufträge müssen die Grenze mitliefern („nur analysieren, nichts
bauen"), sonst entsteht Arbeit, die niemand bestellt hat.

---

## 5. Der Bauplan

```
Diktat in die eigene Oberfläche
        │
        ▼
eigenes Backend legt den Auftrag ab          ← 2 neue Endpunkte
        │
        ▼
Hermes-Cronjob fragt regelmäßig nach          ← Fähigkeit vorhanden
        │
        ▼
Hermes arbeitet im Repo-Klon
        │
        ▼
Ergebnis zurück ans Backend, Anzeige in der eigenen Oberfläche
```

Zu bauen:

| Teil | Was |
|---|---|
| `GET /api/auftraege` | offene Aufträge ausliefern |
| `POST /api/auftraege/{id}/ergebnis` | Rückmeldung entgegennehmen |
| Frontend | Auftrag erfassen, Stand und Ergebnis anzeigen |
| Hermes-Cronjob | in Hermes einrichten, fragt den Server im Takt |

**Der Repo-Klon steht bereits.** Hermes hat ihn selbst geholt:

```
~/agent_project/it-ot-agentic-engineering/
```

Ohne `git`-Binary — Hermes erkannte, dass `dulwich` (Git in reinem Python)
vorhanden ist, und klonte darüber. Stand: `3f5735c`, unverändert, keine
eigenen Commits.

Backend-Code darin unter:
`02_Softwareentwicklung_IT/personal_ai_agent/backend/app/`

---

## 6. Vor dem Bauen bedenken

* **Es gibt keinen Prüfbefehl für dieses Projekt** (siehe Bereichs-`CLAUDE.md`).
  Damit gilt die kurze Leine: jede Änderung einzeln vorlegen. Bei einem Agenten,
  der selbstständig eigenen Code ändert, ist das keine Förmlichkeit.
* **Kosten:** Ein Agent mit Werkzeugschleife verbraucht deutlich mehr als
  reiner Chat — jeder Dateizugriff ist ein eigener Modellaufruf. Ein
  Ausgabelimit bei OpenRouter ist bei 10–20 €/Monat kein Luxus.
* **Was Hermes mitliest:** Sobald Hermes am Repo arbeitet, sieht es dessen
  Inhalt. Das Repo ist öffentlich, insofern unkritisch — aber `.env`,
  `system_prompt.local.md` und `chroma_data/` gehören dort nicht hinein
  und müssen es auch nicht.
* **Qualität ungeprüft:** Ob `deepseek-v4-flash` brauchbaren Code für dieses
  Projekt schreibt, ist noch nicht getestet. Sinnvoll wäre eine kleine echte
  Aufgabe im Klon, bevor Infrastruktur darum herum entsteht.

---

## 7. Nebenbefund: der Log-Spam ist lokal

Offener Punkt aus `stand-2026-08-14.md` („Invalid HTTP request received",
hunderte pro Minute). `netstat` auf dem Gerät zeigt dutzende Verbindungen
`127.0.0.1:<zufällig> → 127.0.0.1:8080` im Zustand `TIME_WAIT`.

**Die Quelle sitzt auf dem Gerät selbst, nicht im Netz.** Eine lokale App
klopft im Dauertakt an Port 8080. Welche, ist offen — `netstat` liefert unter
Android ohne Root keine Programmnamen.

---

## 8. Aufräumen

`Documents/env_temp/dotenv_temp.txt` enthält eine Kopie der `.env` samt
API-Schlüssel und wird nicht mehr gebraucht. Löschen:

```bash
rm /storage/emulated/0/Documents/env_temp/dotenv_temp.txt
```

Das Original in Termux ist davon unberührt.
