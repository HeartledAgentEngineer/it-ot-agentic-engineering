---
name: coding-chat-bild-vision
description: Nutze, wenn ein Hermes-Auftrag die Markierung "[Angehaengte Bild-Datei zur Analyse:" enthaelt. Analysiere das Bild mit dem Vision-Werkzeug (gemini-Vision-Modell), statt nur Text zu verarbeiten. Screenshot/Fehlerbild im Coding-Chat (conv_code).
---

# Coding-Chat Bild-Vision (conv_code)

Wenn die `personal_ai_agent`-App einen Coding-Chat-Auftrag an Hermes
delegiert und dabei eine hochgeladene Bild-Datei (Screenshot, Fehlermeldung,
Foto) anhaengt, steht im Auftrag ein Marker wie:

```
[Angehaengte Bild-Datei zur Analyse: /pfad/zur/datei.png
Lies DIESES Bild mit deinem Vision-Werkzeug (vision_analyze; routet ueber
ein Gemini-Vision-Modell) ein und analysiere es. ...]
```

## Was zu tun ist

1. **Marker erkennen:** Beginnt ein Abschnitt im Auftrag mit
   `[Angehaengte Bild-Datei zur Analyse: <pfad>`, ist ein Bild im Spiel.
   Extrahiere den exakten Pfad bis zum Zeilenende (erste Zeile nach dem
   Marker-Kopf).
2. **Bild einlesen (Vision statt Text):** Beschreibe/beantworte NICHT aus
   dem Gedaechtnis und rate NICHT ueber den Inhalt. Lies die Bild-Datei mit
   deinem Vision-Werkzeug ein:
   - Nutze das Tool `vision_analyze` auf dem angegebenen Pfad (es routet
     automatisch ueber einen gemini/OpenRouter-Vision-Backend). Falls das
     Tool nicht direkt einen lokalen Pfad frisst, lies die Datei als
     `read_file`/Terminal ein und fuehre das Bild einem vision-faehigen
     Modell (z. B. Gemini) zu.
   - Der Pfad steht im Marker — verwende exakt diesen, erzeuge keinen
     anderen.
3. **Antworten:** Beantworte die Frage anhand des TATSÄCHLICHEN
   Bildinhalts, auf Deutsch. Bei Coding-Screenshots: Fehlertext ablesen,
   Ursache benennen, Fix/-code direkt vorschlagen.
4. **Ehrlichkeit:** Hast du das Bild nicht wirklich gesehen (z. B.
   Vision-Backend ohne API-Key nicht erreichbar), sage das klar und
   beschreibe nur, was verlaesslich ist. Nie behaupten, ein Bild gesehen zu
   haben, wenn es nur Text gab.

## Wichtig

- NUR der Bild-Pfad wird uebergeben (keine Base64-Daten-URL im Markt).
  Das Original bleibt unantastbar auf der Platte.
- Es gibt im Projekt KEINEN separaten Vision-API-Key: Bild-Analyse laeuft
  ueber denselben OpenRouter-/gemini-Kanal, den auch das App-Backend nutzt.
- Kontext (vorherige Nachrichten) kann im selben Auftrag stehen — er ergaenzt
  die Bild-Frage, ersetzt sie aber nicht.