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

### Stufe D — Eigener Sprachtrigger („OK Agent") und YouTube-Wissen

**Leitbild (Sebastian, 25.09.2026):** *„Wir bauen quasi unser eigenes Gemini nach, was auch
überall in Apps, auf dem Sperrbildschirm, überall kann. Wenn ich ‚OK Agent' sage, nimmt er mein
Mikrofon auf … und macht dann das, was er gerade soll."* Und: *„mein eigener Memorial
LifeBrain Agent"* — ein wandelndes, sich fortentwickelndes Abbild des eigenen Lebens.

**D1 — Trigger und Wake-Word**

- Der Trigger ist eine **Android-Rolle**, keine Gemini-Funktion: heute hält die Google-App die
  Assistenten-Rolle (`com.google.android.googlequicksearchbox/…GsaVoiceInteractionService`,
  gemessen 25.09.2026). Diese Rolle kann **unsere App** übernehmen → dieselbe Geste
  (Power-Taste lang / Wischen aus der Ecke) startet **unseren** Agenten.
- **Wake-Word „OK Agent"** zusätzlich über **Keyword-Spotting auf dem Gerät** (Foreground-Service
  mit Mikrofon-Berechtigung; Battery-Kosten ehrlich messen). Ob der System-Hotword-Weg der
  Assistenten-Rolle auf dem Edge 50 trägt, ist **zu testen**, nicht anzunehmen.
- **Grenze, die bleibt:** Googles tiefe Systemrechte und Bildschirm-Kontext erben wir **nicht**.
  Wir können handeln (App/Link/YouTube öffnen, Text teilen), aber nicht alles, was Gemini kann.
- **Im Auto bleibt Gemini** (Android Auto/Usability) — bewusste Entscheidung, kein Rückstand.

**D2 — YouTube als Wissensquelle**

- Sebastians Wissen entsteht stark über YouTube → Verlauf, Abos, „Gefällt mir" gehören ins Archiv.
- ⚠️ **Technische Wahrheit:** Die YouTube-API gibt den **Verlauf nicht** heraus (von Google
  entfernt), Takeout enthält ihn ebenfalls nicht mehr. Realistischer Weg: **über die eigene,
  angemeldete Browsersitzung** auslesen (Verlauf, Abos, Playlists) und als Quelle einlesen.
- **Hintergrund-Synchronisation beim Agenten-Start:** läuft sie noch, sagt der Agent es
  ausdrücklich („warte kurz, ich synchronisiere gerade") statt eine veraltete Antwort zu geben.
  Dafür braucht es einen **Sync-Status**, den der Agent vor Verlaufs-Fragen prüft.
- Nur **Metadaten** (Titel, Kanal, Zeit, Dauer) ins Archiv — keine Videos, keine Audiodaten.

**D3 — Sprachbetrieb in der App**

- Zustand sichtbar machen: **„Mikrofon offen / hört zu / denkt nach / spricht"** — man muss sehen,
  wann man sprechen kann.
- Audio → Backend (`POST /api/sprache/transkript`) → Kette (Vokabular, Kostenbuchung) → Glättung →
  Antwort, optional als Sprache zurück.
- **Datenschutz-Regel bleibt:** Audio geht an **OpenRouter** (kein neuer Empfänger), keine
  Speicherung von Audio/Bildern im Agent-Backend.
- **Sofort sprechen:** Nach dem Trigger („OK Agent" / Assistenten-Geste) öffnet sich die App und
  die Antwort wird **direkt vorgelesen** — Text erscheint dazu. Das macht Gemini heute schon so;
  wir bauen **dieselbe** Erfahrung, nur mit unserem Agenten und unseren Daten
  (Korrektur von Sebastian, 25.09.2026 — es ist kein Unterschied, sondern Nachbau).

**Stand 25.09.2026 — gebaut (dieser Teil von D3 läuft):**

- Zustand sichtbar: `#mic-status` über der Eingabe zeigt **„Mikrofon offen" → „hört zu" →
  „denkt nach" → „spricht"** (`frontend/app.js: setMicStatus`, `frontend/index.html`).
  Vorher stand der Zustand nur im Tooltip — am Handy unsichtbar.
- Weg: **`POST /api/sprache/transkript`** (multipart/form-data) → bestehende Kette
  `transcribe()` → `polish_text()`. Der ältere Pfad `/api/transcribe` bleibt bedient;
  es ist dieselbe Funktion, keine zweite Logik. Kein neuer Anbieter.
- Der erkannte Text landet im Eingabefeld und geht von dort raus; die Antwort liest der
  Vorlese-Knopf an der Antwort vor (primär `/api/speak`, Rückfall **Browser-Stimme**).
- Audio lebt **nur im Speicher** und geht ausschließlich an OpenRouter.
- **Noch nicht gebaut aus D3:** Wake-Word „OK Agent", das Öffnen per Assistenten-Geste und
  das automatische Vorlesen beim Start — das sind D1/D4.

**D4 — Overlay und Stimmen („eigenes Gemini" als Erlebnis)**

- **Overlay:** ein schwebendes Fenster über anderen Apps (Android-Recht „Über anderen Apps
  einblenden" + Foreground-Service). Als Assistenten-App auch über dem **Sperrbildschirm**.
  Einschätzung: machbar, aber der **empfindlichste** Teil (Hersteller-Einschränkungen möglich) →
  **erst nach** dem APK-Gerüst, als eigener kleiner Schritt, mit Test auf dem Edge 50.
  Wenn es zickt: nicht verbiegen — dann läuft es eben im eigenen Fenster (App statt Overlay).
- **Stimmen — kostenlos und ohne neues Konto (geprüft 25.09.2026):**
  1. **Stimme des Handys** (`com.google.android.tts` ist installiert): kostenlos, **offline**,
     kein Konto, sofort da — die sichere Voreinstellung.
  2. **edge-tts** (Microsoft-Stimmen, **kostenlos, kein Schlüssel, kein Konto**; auf dem PC bereits
     installiert, Version 7.2.7): natürlichere deutsche Stimmen. Läuft im Backend; braucht Netz.
     Ehrlicher Hinweis: inoffizieller Zugang zu Microsofts Dienst — funktioniert, ohne Zusage.
  3. **Piper** (voll lokal, offline, kostenlos): Modell (~60 MB) nötig, rechnet auf der CPU —
     der Weg, wenn es **ohne Netz** gehen soll.
- **Ausdrücklich nicht:** ElevenLabs oder ein weiterer Anbieter mit Lizenz und Guthaben.
- **Bauweise wie bei der Erkennung:** Stimmen als **Daten** (eine Liste, ein Eintrag je Stimme,
  umschaltbar in der Oberfläche) — kein neuer Codepfad je Anbieter.


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
