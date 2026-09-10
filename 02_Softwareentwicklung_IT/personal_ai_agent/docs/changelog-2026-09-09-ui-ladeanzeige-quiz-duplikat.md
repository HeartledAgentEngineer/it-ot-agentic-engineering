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

## Quiz-Feinschliff (Stand 2026-09-10, drei Folgewünsche)

1. **Namens-Chips nach 'Nein' nach Wahrscheinlichkeit sortiert:** Neues
   Backend `_optionen_sortiert(bild_pfad)` in `gesicht_quiz` berechnet für das
   dominante Gesicht des aktuellen Bilds die beste SFace-Cosinus-Distanz (+
   Aufnahmejahr-Bonus) zu jeder Katalog-Person und liefert die Namen
   wahrscheinlichste zuerst. Der Router nutzt es für `optionen` im
   `quiz_start` — damit erscheinen die Namens-Chips nach 'Nein' plausibel
   geordnet statt in Katalog-Reihenfolge.
2. **Vollbild zwei-Finger-zoombar:** Der Rahmen-Drag stört den nativen
   Browser-Pinch nicht mehr — `touch-action:manipulation` auf den Rahmen (statt
   `none`), und der Drag-Ingress respektiert Eingaben mit mehreren Fingern
   (`mev.buttons`-Check). Zwei-Finger-Zoom bleibt möglich.
3. **Kästen stimmen trotz Hoch-/Querformatwechsel:** Die Gesichts-Rahmen
   hängen jetzt an einer `position:relative`-`bildBox`, die exakt an die
   GERICHTETE Bildgröße gekoppelt wird (`getBoundingClientRect`), und `resync()`
   skaliert die nativen bbox-Werte auf die aktuelle Anzeige. Ein
   `resize`/`orientationchange`-Listener + 250ms-Nachlauf positionieren die
   Kästen nach jedem Formatwechsel neu.
- Cache-Bust: `app.js?v=20260910aV`.

## Quiz: Bild sofort + alle Chat-Fotos maximierbar (Stand 2026-09-10)

1. **Bild SOFORT anzeigen (kein Warten auf Gesichtserkennung):**
   - Backend `start_runde` liefert das nächste Quiz-Bild jetzt sofort
     (wahl ohne SFace-Sync), Feld `analyse_ausstehend: true`.
   - Neuer Endpunkt `POST /api/gesichter/quiz/analysiere` (body `{bild_pfad}`)
     führt die Gesichts-Analyse nach und liefert `gesichter`/`anzahl_gesichter`/
     `vermutung`.
   - Frontend `naechsteQuizRunde`: zeigt das Bild sofort, direkt darunter die
     „🧠 Quiz lädt – prüfe Gesichter…"-Animation und ersetzt die Animation
     durch die **Ja/Nein-Frage**, sobald die Analyse fertig ist.
2. **JEDES im Chat sichtbare Foto per Klick maximierbar:** Globaler
   `<img>`-Klick-Handler auf `#messages` (capture-Phase) öffnet jedes
   Hochladen-/Dateisuche-/Verlauf-Bild im Vollbild (`zeigeBildVollbild`).
   Quiz-Bilder (dataset.quizKarte) werden durchgelassen, damit ihr eigener
   Antipper mit den Gesicht-Kästen wirkt.
- Cache-Bust: `app.js?v=20260910bW`.

## Autonomer Nachtjob (termux/hermes-nacht-job.sh, Stand 2026-09-10)

- **Ziel (Wunsch Sebastian):** Nach einer festgelegten Zeit (Cron) soll der
  Coding-Agent ohne User-Eingriff einen echten offenen Programmier-Auftrag
  abarbeiten — inklusive **Gemini-Vision-Bildlesen** (auch wenn sein Gehirn
  DeepSeek ist) — und lokal committen.
- **Ablauf des Skripts:** `git pull --ff-only` → Server-Health (ggf.
  `agent-start`) → offene/`laeuft`/`fehler`-Programmier-Aufträge filtern
  (kein Test/Cron/erledigt, Coding-Stichworte) → EINEN wählen → Auftrag in
  `~/hermes_inbox/auftraege.jsonl` schreiben (Kanal `aktiv`) → Inbox-Daemon
  (einmal) anstoßen → auf Antwort in `antworten.jsonl` warten → lokal
  committen → Auftrag per API `/ergebnis erfolg:true` schließen.
- **Vision-Hinweis im Kontext:** Der Inbox-Payload aktiviert den Skill
  `coding-chat-bild-vision` (Bilder via Gemini-Vision lesen), damit der
  Nacht-Coding-Agent auch Screenshots/Bilder versteht.
- **Ehrenkodex:** Commit NUR lokal (kein push — bleibt bei Sebastian); ist der
  Auftrag bereits umgesetzt, meldet der Agent das ehrlich, und das Skript
  schließt den Buch-Eintrag entsprechend.
- **Erwartung zum Buch-Status:** Viele `offen`/`laeuft`/`fehler`-Aufträge sind
  längst im Code, nur nicht als `fertig` markiert (`_verwaiste_freigeben`).
  Das Skript beschränkt sich deshalb auf plausible Coding-Aufträge und nutzt
  die Git-Prüfung des Agenten statt blind zu „lösen".

## Verifikation

- `node --check frontend/app.js` → OK (Exit 0).
- Screenshot `L3.png` bestätigt die alte Doppel-Ladeanzeige; nach Fix nur eine.
- Bei der doppelten „Ist das Eileen?" gibt es keinen auffindbaren wörtlichen
  Duplikat-Screenshot; Quiz-Dedup ist als Härtung eingebaut.

## Hinweis (Nicht-UI-Thema)

Die „Eileen als Vermutung war falsch"-Wahrnehmung liegt an der bewusst lockeren
Erkennungsschwelle (`face_service._SCHWELLE_JA/_UNSICHER`). Das ist kein UI-Bug
und wurde NICHT geändert — eine Kalibrierung gehört getrennt geprüft.