# Changelog 2026-09-09 — UI-Ladeanzeige + Quiz-Vermutungs-Duplikat

## Problem (Auftrag Sebastian)

1. **Zwei konkurrierende Ladeanzeigen gleichzeitig** im Haupt-Chat
   (Screenshot `L3.png`, „Agent liest deine Nachricht…"):
   - die UNTERE animierte Ladeblubble `#loading` („🔍 Agent liest deine Nachricht…")
   - UND eine zweite „Denke nach..."-Bubble direkt IN der Assistenten-Blase,
     ein Überbleibsels aus dem alten Design vor der Migration zur unteren Bubble.
2. **Quiz-Gruppenbild**: Bei einem Gruppenbild hintereinander mehrere
   „Ist das X?"-Vermutungsfragen gestellt, auch dieselbe Person mehrfach;
   außerdem wurde beim Wechsel zum nächsten Gesicht die Antwort-Chip-Liste
   (David, Eileen, …) automatisch wiederholt — das wirkte wie „die gleiche
   Frage wird mehrfach gestellt".
3. **Ständige Bildwiederholungen im Quiz:** Dieselben Bilder kamen immer
   wieder — vor allem stark erkannte/typische Familienfotos („ganze Zeit
   Bildwiederholungen", Wunsch Sebastian 2026-09-09).
4. **„Keine bekannte Person" immer unter Ja/Nein:** Der Skip-Button war nur
   nach „Nein" (bzw. beim Aufklappen) erreichbar, nicht direkt unter der
   Ja/Nein-Vermutungsfrage.

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
- **Keine automatische Chip-Wiederholung pro Gesicht:** Bei einem Gesicht
  OHNE Vermutung wird die Namens-Chip-Liste nicht mehr automatisch angezeigt,
  sondern nur ein dezenter „✏️ Dieses Gesicht benennen"-Knopf (klappt die
  Chips auf Wunsch auf). So bleibt beim Durchgehen mehrerer Gesichter der
  Fortschritt + gelbe Rahmen der Fokus, ohne dass „die gleiche Frage"
  mehrfach wirkt. (Wunsch Sebastian, Gruppenbild-Durchlauf.)
- **„Keine bekannte Person vorhanden" direkt unter Ja/Nein:** In BEIDEN
  Flows (Einzelbild-Vermutung `zeigeQuizKarte` + Gruppenbild
  `baueVermutungsBox`) steht der Skip-Button „🚫 Keine bekannte Person
  vorhanden" jetzt IMMER direkt unter den Ja/Nein-Buttons — nicht erst nach
  „Nein". Einzelbild: überspringt das Bild (`quizUeberspringen`); Gruppenbild:
  springt zum nächsten Gesicht.
- **Keine Bildwiederholungen mehr:** Beim Durchlaufen eines Gruppenbildes
  wurde das Bild am Ende NICHT persistent als „gesehen" markiert, wenn
  nicht jede Person einzeln benannt wurde → es kam nach Neustart wieder.
  Neuer `markiereBildErledigt()` in `starteGruppenQuiz` sendet am letzten
  Gesicht `ueberspringen:true` an `POST /api/gesichter/quiz/antwort`
  (→ Backend `markiere_uebersprungen` persistiert es dauerhaft). So
  erscheint kein durchlaufenes Bild erneut.
- Cache-Bust: `app.js?v=20260909aQ`.
- **Neues Verhalten (Folge-Wunsch):** „Keine Person vorhanden" springt im
  Gruppenbild SOFORT zum nächsten BILD (statt zum nächsten Gesicht) und
  persistiert das Bild als erledigt. Die „Kein erkanntes Gesicht
  vorhanden"-Beschriftung ist überall zu „🚫 Keine Person vorhanden"
  vereinheitlicht.
- **„Neue Person"-Formular entdoppelt:** Das „Beschreibung / Lebensinfos"-
  Feld war doppelt gemoppelt zum „Zusatzkontext". Jetzt gibt es überall
  (Einzelbild-Quiz, Gruppenbild-Quiz, Personen-Verwaltung) NUR EIN Textfeld
  „Infos über die Person — Beziehung + alles, was du weißt" (Name + Rolle
  bleiben eigene Felder). In der Verwaltung wird der bisherige
  `beschreibung`-Wert beim Speichern erhalten (kein Datenverlust).
- Cache-Bust: `app.js?v=20260909bR`.

## Vollbild-Gesichts-Editor + Bildunterschrift (Stand 2026-09-09, Folgewünsche)

- **Vollbild-Rahmen bearbeitbar (Bezug Backend bbox):** Die gelben
  Gesicht-Rahmen im Vollbild sind antippbar, mit dem Finger verschiebbar und
  per „✕"-Markierung löschbar. Änderungen sammeln sich flüchtig in
  `_quizEditor.bbox_live` (Original-Pixel) und werden beim Antworten
  (`quizBeantworten`/`quizBeantwortenSilent`, mit bbox) an
  `POST /api/gesichter/quiz/antwort` gesendet.
- **Backend bbox-Unterstuetzung:** `beantworte_runde(..., bbox=None)` wählt
  das Gesicht, dessen Rahmen am stärksten mit der (korrigierten) bbox
  überlappt (IoU, `_gesicht_zu_bbox`) statt blind das dominante. So landet
  die Referenz am richtig nachjustierten Gesicht und die Erkennung wird
  sauberer. Router `QuizAntwortBody.bbox: list = []` durchgestellt.
- **Bildunterschrift statt nacktem Text:** Nach Beantwortung wird die Karte
  zum Bild + „… das ist [Person]" (Einzelbild) bzw. „… das ist Person1,
  Person2" (Gruppenbild, gesammelte Personen). Die Buttons (Menü/Beenden)
  verschwinden — überflüssig. Die nächste Quizrunde kommt als NEUE
  Chatblase darunter (`naechsteQuizRunde`).
- Cache-Bust: `app.js?v=20260909dT`.

## Personen-Verzeichnis: Bild-Referenzen ansehen & ausschließen (Stand 2026-09-09)

- **Backend:** Jede Referenz speichert jetzt auch `bild_pfad` (das
  Ursprungsbild, `beantworte_runde.neue_ref`). `referenzen_auflisten` gibt
  pro Referenz `bild_pfad` aus, damit das Frontend das Bild laden kann.
- **Frontend:** In `zeigePersonenVerwaltung` hat jede Person-Karte jetzt
  „🖼 Referenzen ansehen/löschen" — klappt die Einzel-Referenzen auf
  (Index + Aufnahmejahr + Bildvorschau via `/api/dateien/daten`) mit je
  einem „✕ ausschließen"-Button, der die Referenz aus dem Embedding der
  Person entfernt (`referenzLoeschen`). So kann man falsch gelernte
  Bild-Referenzen nachträglich aus der Erkennung nehmen.
- Cache-Bust: `app.js?v=20260909eU`.

## Verifikation

- `node --check frontend/app.js` → OK (Exit 0).
- Screenshot `L3.png` bestätigt die alte Doppel-Ladeanzeige; nach Fix nur eine.
- Bei der doppelten „Ist das Eileen?" gibt es keinen auffindbaren wörtlichen
  Duplikat-Screenshot; Quiz-Dedup ist als Härtung eingebaut.

## Hinweis (Nicht-UI-Thema)

Die „Eileen als Vermutung war falsch"-Wahrnehmung liegt an der bewusst lockeren
Erkennungsschwelle (`face_service._SCHWELLE_JA/_UNSICHER`). Das ist kein UI-Bug
und wurde NICHT geändert — eine Kalibrierung gehört getrennt geprüft.