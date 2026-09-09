# Changelog 2026-09-09 — UI-Ladeanzeige + Quiz-Vermutungs-Duplikat

## Problem (Auftrag Sebastian)

1. **Zwei konkurrierende Ladeanzeigen gleichzeitig** im Haupt-Chat
   (Screenshot `L3.png`, „Agent liest deine Nachricht…"):
   - die UNTERE animierte Ladeblubble `#loading` („🔍 Agent liest deine Nachricht…")
   - UND eine zweite „Denke nach..."-Bubble direkt IN der Assistenten-Blase,
     ein Überbleibsels aus dem alten Design vor der Migration zur unteren Bubble.
2. **Quiz-Gruppenbild**: Bei einem Gruppenbild hintereinander mehrere
   „Ist das X?"-Vermutungsfragen gestellt, auch dieselbe Person mehrfach.

## Ursache

- In `sendMessage` (frontend/app.js) wurden zwei unabhängige Ladeanzeigen
  eingeblendet: `setzeTutZeile`/`setLoading` (untere `#loading`-Bubble) UND
  zusätzlich eine `typing-indicator`-Bubble in der leeren Assistenten-Blase
  (Zeile, die seit v20260817 per Kommentar den Weg zur unteren Bubble gehen
  sollte, aber die Stream-Blase trotzdem füllte).
- Im Gruppenbild-Flow (`starteGruppenQuiz`) wird für JEDES Gesicht eine eigene
  Vermutungs-/Antwort-Sektion gebaut; gleiche Person auf mehreren Boxen →
  Frage mehrfach.

## Fix

- **Eine Ladeanzeige:** Die „Denke nach..."-Bubble aus der Assistenten-Blase
  entfernt. Der Arbeitszustand läuft jetzt NUR noch in der unteren animierten
  `#loading`-Bubble (WhatsApp-Stil, gesetzt via `setzeTutZeile`). CSS-Kommentar
  in style.css korrigiert (nicht mehr „unused").
- **Quiz-Dedup:** In `starteGruppenQuiz` ein `Set` bereits gestellter
  Vermutungen; dieselbe Person wird pro Bild nur EINMAL gefragt, danach geht
  es direkt zur Antwortauswahl. Vermutungs-Ja/Nein-Box in die eigene Funktion
  `baueVermutungsBox` extrahiert.

## Verifikation

- `node --check frontend/app.js` → OK (Exit 0).
- Screenshot `L3.png` bestätigt die alte Doppel-Ladeanzeige; nach Fix nur eine.
- Bei der doppelten „Ist das Eileen?" gibt es keinen auffindbaren wörtlichen
  Duplikat-Screenshot; Quiz-Dedup ist als Härtung eingebaut.

## Hinweis (Nicht-UI-Thema)

Die „Eileen als Vermutung war falsch"-Wahrnehmung liegt an der bewusst lockeren
Erkennungsschwelle (`face_service._SCHWELLE_JA/_UNSICHER`). Das ist kein UI-Bug
und wurde NICHT geändert — eine Kalibrierung gehört getrennt geprüft.