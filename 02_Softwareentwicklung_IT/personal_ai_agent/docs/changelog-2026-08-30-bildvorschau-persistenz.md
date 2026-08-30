# Changelog / Änderungsprotokoll

Alle sichtbaren Änderungen am personal_ai_agent, dokumentiert nach dem
Prinzip „Doku folgt dem Code“. Neuere Einträge oben.

## 2026-08-30 — Gesichter merken funktioniert jetzt auch im normalen Chat (Stream)

**Problem:** „das bin ich" / „das ist Pedi" beim Betrachten eines Bildes wurde
entweder nie gespeichert oder der Agent antwortete „Es ist mir nicht
gestattet, reale Personen zu identifizieren" — obwohl die Merk-Logik
(`_gesichter_merke`, LLM-gestützte Personenextraktion) existierte.

**Root Cause:** Das Frontend spricht **standardmäßig `/api/chat/stream`**.
Die Merk-Logik war aber **nur** im Non-Stream-Endpunkt `/api/chat` eingebaut
(der reine Notfall-Fallback). Alle Aufrufe über den normalen Stream-Chat
liefen an der Merk-Logik vorbei — das Bild wurde dem LLM zwar gezeigt, aber
„wer darauf ist" nie in den Gesichter-Katalog geschrieben.

**Fix (`backend/app/router/chat.py`):** Die reaktive Merk-Logik läuft jetzt
identisch auch im Stream-Pfad (`s_bild_aktiv` aus Dateisuche ODER
Upload-Bild, `_gesichter_merke` mit Referenz-Miniatur). Damit griff dein
letzter Versuch (Photo von dir hochladen + „das bin ich") jetzt wirklich.

**Verifikation (real gegen laufenden Server):** Stream-Chat mit hochgeladenem
Bild + „das ist meine Testperson Omega" → `GET /api/gesichter` enthielt Omega
mit `referenz_bild_miniatur`. Danach aufgeräumt (Omega gelöscht, Upload
gelöscht, Verlaufsrunde entfernt). `extrahiere_gesichts_anlernen("das bin
ich", "Sebastian")` liefert korrekt `{"name":"Sebastian","ist_nutzer":true}`.

## 2026-08-30 — Bild-Vorschau (Dateisuche) überlebt Reload

**Problem:** Bilder, die der Agent über die Dateisuche im Chat angezeigt hat
(z. B. „der letzte Screenshot“), waren nur flüchtig (RAM-Cache, 10 min).
Nach einem Reload/einer neuen Sitzung waren sie weg, weil der Verlauf pro
Nachricht nur `role`/`content`/`zeit` speicherte.

**Fix:**
- `chat_verlauf.finish_exchange(..., bild_pfad=None)` speichert den Pfad des
  per Dateisuche gezeigten Bildes am Assistant-Eintrag mit. Es wird bewusst
  NUR der Pfad gespeichert, nie die Bilddatei (Original unantastbar).
- `chat.py` reicht den Bildpfad der Dateisuche an beide Verlauf-Pfade durch
  (`/api/chat` und `/api/chat/stream`).
- Frontend `zeigeGespraech` lädt Nachrichten mit `bild_pfad` über
  `GET /api/dateien/daten?pfad=` frisch nach und zeigt sie wieder an.

**Verifikation:** `python -m pytest tests/test_chat_verlauf.py -q` grün;
`GET /api/conversations/conv_main` liefert den restaurierten Verlauf.