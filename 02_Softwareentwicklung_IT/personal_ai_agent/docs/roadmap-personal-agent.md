# Roadmap – Personal AI Agent als „Second Brain"

> **Quelle:** Sebastians Nachricht vom 25.09.2026 (wörtlich in der Session).
> **Zweck:** Diese Datei ist die Richtungsvorgabe. Jede Session liest sie, bevor sie
> neue Features plant — damit nichts gebaut wird, was nicht hierher führt.
> **Stand:** 25.09.2026.

## Leitbild (Sebastians Worte)

> „Dieser Chatbot soll einfach der Second Brain von mir sein, soll mein Leben
> assistieren, soll auch vielleicht so eine Art Archiv von meiner Persönlichkeit
> sein, von meinen Werten, von meinen Erlebnissen — und quasi auch eine Biografie."

Daraus folgt: Der Agent wird **profilorientiert** — er kennt **Menschen**, **Zeiträume**
und **Phasen**. Nicht eine Suchmaschine, sondern ein Begleiter, der weiß, wer wann
wichtig war und was wann passiert ist.

**Kein Training:** Es wird nichts nachtrainiert. Verbessert wird das **Zusammenspiel**:
Umgebung (Archiv, Gedächtnis, Bilder, Personen) plus **Werkzeug-Griff** des Modells
darauf.

## Was bereits trägt (Stand 25.09.2026)

| Baustein | Stand |
|---|---|
| Archiv-Index durchsuchbar | 82.774 Nachrichten · 33.312 Chunks · 1.111 Gespräche · 33.312 Vektoren · 262,7 MB; WhatsApp 42.147 Nachrichten (16.02.2020–12.08.2026) enthalten („Fabia" 735 Treffer) |
| Zwei-Stufen-Suche | Treffer → Zeiger → Originaltext nachlesen; bei Unsicherheit **Frage statt Behauptung** |
| Bewusstseins-Baustein | 506 Zeichen Metadaten im Prompt („du hast ein Archiv — erst hier suchen, dann Web") |
| Gedächtnis-Qualität | Korrekturen ersetzen (alte Fassung bleibt in `history`), `top_k=8`, Arten `fakt/termin/zustand`, sanftes Vergessen |
| WhatsApp-Weg | 64-stelliger Schlüssel gesichert, E2E-Backup 3,1 GB in Drive (14:08); Download offen (Google-Token) |
| Destillation (Biografie-Schicht) | Werkzeug `src/destillieren.py` vorhanden: Episoden / Themen / Fakten → `distilled/*.jsonl`; bisher nur `startbestand.jsonl` (58 KB). Trockenlauf: 602 Gespräche, 20,5 Mio. Zeichen ≈ 3,34 $ |

## Richtung in Stufen

### Stufe B1 — Medien sortieren (Videos zuerst)

- **WhatsApp-Videos triagen.** Kategorien: **Müll · Witz/Fun · behalten**. Konzert- und
  Veranstaltungsvideos sind ausdrücklich **behalten**.
- Modul mit **Vorschlag + menschlicher Entscheidung** (der Agent schlägt vor, Sebastian
  entscheidet) — Liste mit Dauer, Datum (EXIF/Dateizeit), Größe, Vorschaubild, Vorschlag.
- Warum: Videos sind seit dem 25.09. **nicht mehr im Google-Backup** (Speicher war voll,
  Videos ausgeschlossen) — sie liegen also **nur noch auf dem Handy** und müssen dort
  bewertet und danach ausgelagert werden.
- **Handy-Speicher reduzieren:** Bewertung → Auslagerung → Löschen auf dem Gerät.

### Stufe B2 — pCloud als Zuhause für Bilder und Videos

- **pCloud ersetzt die lokale Festplatte** als Ablage. Begründung (Sebastian): jederzeit
  Zugriff, jederzeit Sicherung; physische Backup-Festplatte ist **nicht** mehr wichtig.
- **pCloud-Anbindung in den Agenten** integrieren (Plan liegt: `docs/plan-pcloud-anbindung.md`).
- **Bestandsaufnahme zuerst:** Wie sind Bilder/Videos in pCloud geordnet? Ordnerstruktur,
  Anzahl, Zeitraum, Dateitypen, Dubletten.
- ⚠️ **Regel bleibt:** Bilder werden **nicht** ins Agent-Backend kopiert — nur
  **in-memory** für den Analyse-Aufruf, danach verworfen. Bei Bedarf frisch von pCloud holen.

### Stufe B3 — Bilder zu Erinnerungen machen

- **Personen zuordnen:** Wer ist auf den Bildern, wer ist wichtig (Familie, Umfeld) —
  Anbindung an den vorhandenen Gesichter-Katalog und die Personen-Daten.
- **Eingabe per Sprache:** Erzählungen zum Bild/Event werden **transkribiert** (Handy) und
  dem Bild/an der Person zugeordnet.
- **Erinnerungsstil:** Erlebnisse **pro Person · pro Ausflug · pro Event · pro Urlaub**
  gruppiert speichern (Clustern statt Ablage in einem Ordner).
- **Grundlage sind echte Metadaten** (Aufnahmedatum/EXIF) — **nicht** der Dateiname
  (Lehre vom 22.09.2026).

### Stufe C — Der Agent wird ein Handy-Begleiter

- **Eigene App statt Browser-Tabs:** eine WebView-(Web-App-)Hülle, die die Oberfläche
  innerhalb einer selbst erzeugten App aufruft — Tab-Wildwuchs weg, Konstanz über die Zeit.
- **Chats trennen und wechseln:** Programmier-Chat und normaler Chat umschaltbar.
- **Sprachnutzung auf dem Handy:** mit dem Agenten **sprechen** (Diktat rein, Antwort als
  Sprache/TTS raus).
- **Weitere Fähigkeiten:** Inhalte anzeigen, Links im Browser öffnen, **YouTube**
  einbinden, Wissen über eigene **Social-Media-Konten** und Feeds, **Konzerte**,
  **EXIF-/Aufnahmedaten** von Bildern.
- **Smartphone-Nutzung optimieren:** der Agent soll das Handy bedienen können
  (Phone-Use), nicht nur auf dem PC funktionieren.

## Arbeitsweise für diese Stufen

- **Ein Fokus pro Stufe.** Parallel nur, was sich **nicht** in die Quere kommt
  (getrennte Dateien/Bereiche); **Commit und Push macht ausschließlich der Hauptagent.**
- **Prüfbefehl vor Behauptung:** `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  (Stand 25.09.2026: 358 grün), Frontend `node --check app.js` + JS-Tests.
- **Cache-Bump** (`?v=JJJJMMTT…`) bei jeder Frontend-Änderung.
- **Doku folgt dem Code** — Changelog + diese Roadmap gemeinsam committen.
- **Datenschutz:** Archivinhalte, Bilder und Chats bleiben **privat** — nichts davon in
  Repo, Logs oder Antworten; nur Zahlen und Themen-Stichworte.

## Offene Punkte (bewusst nicht vergessen)

1. **Google-Token** für den Vault-Download (Comet sperrt die Cookie-Datei) —
   sonst sind Gruppen- und archivierte Chats noch nicht im Archiv.
2. **Destillation** über den Bestand laufen lassen (Probeprofil zuerst) → Biografie-Schicht.
3. **Werkzeug-Griff des LLM:** dass das Modell **selbst** entscheidet, das Archiv zu
   durchsuchen (Werkzeug-Aufruf), statt Fundstellen untergeschoben zu bekommen.
4. **Anruflisten** als Quelle aufnehmen (Zeit + Art; Nummern kommen maskiert an).
5. **Profil-Baustein** im Prompt: Werte, Phasen, Menschen — heute stehen dort nur Metadaten.
