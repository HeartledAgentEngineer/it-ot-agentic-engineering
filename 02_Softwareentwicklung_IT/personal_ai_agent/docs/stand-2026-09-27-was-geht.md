# Was geht — was geht nicht (Stand 27.09.2026)

> Für Sebastian, damit der Überblick nicht verloren geht. Belegt aus dem Code und
> der Roadmap, nicht aus dem Gedächtnis. **Legende:** ✅ geht · ⚠️ geht teilweise
> · ❌ geht noch nicht

## Sprache

| Sache | Stand | Beleg / Grenze |
|---|---|---|
| **Mikrofon-Knopf in der App** (tippen, sprechen, Text erscheint) | ✅ | `frontend/app.js`, `POST /api/sprache/transkript` |
| **Zustand sichtbar** („Mikrofon offen → hört zu → denkt nach → spricht") | ✅ | `#mic-status` über der Eingabe |
| **Antwort vorlesen** (Knopf an der Antwort) | ✅ | `/api/speak`, Rückfall: Browser-Stimme |
| **„OK Agent" bei geöffneter App** | ⚠️ | nur als **Knopf** — kein Wake-Word |
| **„OK Agent" bei App im Hintergrund / Bildschirm aus** | ❌ | braucht (a) echte APK, (b) Android-**Assistenten-Rolle**, (c) Keyword-Spotting im Vordergrunddienst. Heute hält Google die Rolle (`…GsaVoiceInteractionService`) |
| **Automatisch vorlesen direkt nach dem Trigger** | ❌ | gehört zu D1/D4, zusammen mit dem Trigger |

**Kurzantwort auf Sebastians Frage:** Im **Hintergrund geht es noch nicht.**
Sprache funktioniert heute nur, wenn die App **offen und im Vordergrund** ist.
Der Weg dahin ist klar (Stufe C: APK + Assistenten-Rolle), aber nicht gebaut.

## Cloud (pCloud)

| Sache | Stand | Beleg |
|---|---|---|
| **Zugang vom PC aus** | ✅ | `userinfo` result 0, `listfolder` 18 Einträge, Konto 2.199 GB / 390,5 GB |
| **Selbstheilung, wenn der Schlüssel stirbt** | ✅ | `tools/pcloud/pcloud_token_erneuern.py` (`--pruefen` / neu holen) |
| **Dienst im Backend** (Status, Liste, Suche, Vorschaubild, Datei) | ✅ | `app/services/pcloud_service.py` + `/api/cloud/*`; **665 Tests grün (27.09.2026)** |
| **Zugang vom Handy** | ⚠️ | Übernahme-Automatik steht in `start-termux.sh` (Übergabedatei → `backend/.env`, danach gelöscht; im Sandkasten geprüft, 24/24) — sie wirkt beim **nächsten Widget-Tipp** |
| **Fotos sortieren / Themen** | ⬜ | Werkzeug steht (Sortierschlüssel, 9.430 Dateien), Sortierung noch nicht gelaufen |
| **Personen clustern** | ⬜ | Kette existiert auf dem Handy (455 Lieblingsbilder), für pCloud noch nicht gestartet |

## App & Verlauf

| Sache | Stand |
|---|---|
| **Verlauf bleibt erhalten** (auch Daemon-Antworten) | ✅ |
| **Selbsttest-Knopf** (zeigt Zustand: Stand, Index, Daemon, Gedächtnis, Sprache, pCloud) | ✅ |
| **Kopfzeile bleibt bei offener Tastatur sichtbar** | ✅ |
| **Text markieren/kopieren per Langdruck** | ✅ |
| **Bilder in den Chat geben** (Bild an Nachricht gebunden) | ✅ |
| **Gedanken erscheinen als Blasen und klappen ein** | ✅ |
| **Widget am Handy** (Code holen → Server → App öffnen → Diagnose) | ✅ |

## Was Sebastian JETZT testen kann

1. **App öffnen → Mikrofon-Knopf → sprechen** → Text erscheint → Antwort → Vorlese-Knopf.
2. **Selbsttest-Knopf** in der Kopfzeile: zeigt, ob Server, Index, Daemon und Sprache leben — und ob der pCloud-Schlüssel liegt („nicht eingerichtet" / „verbunden (Konto …, GB)").
3. **Widget tippen**: zieht den neuen Stand, startet den Server, öffnet die App — und übernimmt beim nächsten Tipp den pCloud-Schlüssel aus `/sdcard/Download/pcloud_token.txt` (zweimal tippen, der laufende Durchgang nutzt noch den alten Skripttext).
4. **Foto in den Chat geben** → Analyse (Bild wird nicht gespeichert).

## Was noch NICHT testbar ist

- „OK Agent" im Hintergrund / auf dem Sperrbildschirm (❌ APK nötig)
- Overlay über anderen Apps (❌, kommt nach dem APK-Gerüst)
- Cloud-Funktionen **vom Handy** (Schlüssel noch nicht dort)
- YouTube-Wissen (Verlauf-Auslesen braucht die Browsersitzung)
- Volle WhatsApp-Historie (Google-Token fehlt, Comet sperrt die Cookie-Datei)
