# Änderungsprotokoll 2026-09-14 — Quiz: Ja/Nein zuerst bei JEDEM Gesicht auf jedem Bild

## Wunsch (Sebastian)
> „bitte immer bei jeder Person auf jedem Bild erst die Ist-das-Frage, nach Nein erst
> Auswahl mit Namen — die Antwortauswahl in der Namenssuche sollte nach allen Namen
> im Katalog suchen; ‚oma helga' oder ‚helga' sollte ‚Oma Helga' suchbar machen."

Nachgefragt: Es gilt **ohne Ausnahme** — auch wenn dieselbe Person auf dem Bild
schon gefragt wurde und auch bei Gesichtern ohne ML-Vermutung.

## Umsetzung (Frontend `frontend/app.js`, Cache-Bust `bX`)

### 1. Gruppenbild: jedes Gesicht bekommt seine Ja/Nein-Frage
Datei: `frontend/app.js`, Funktion `starteGruppenQuiz`.

- **Entfernt:** das `Set` `geseheneVermutungen`. Früher wurde dieselbe Person pro
  Bild nur EINMAL als „🔎 Ist das X?"-Frage gestellt; ein zweites Gesicht
  derselben Person sprang direkt in die Namensauswahl (ohne Frage). Das ist mit
  dem neuen Wunsch abgelöst.
- **Entfernt:** der Aufklapp-Knopf „✏️ Dieses Gesicht benennen" für Gesichter
  OHNE Vermutung — der zeigte die Namensauswahl ebenfalls ohne vorherige Frage.
- **Neu:** `baueKeinePersonGate()` — dasselbe Gate wie im Einzelbild-Flow
  (`zeigeQuizKarte`), nur pro Gesicht:
  - „👤 Keine Person gefunden?"
  - `✅ Ja → Person einzeichnen` (Rahmen per Finger zeichnen, `zeigeEinzeichnen`)
  - `❌ Nein → nächstes Gesicht` (`weiter()`; letztes Gesicht → nächstes Bild)
  - `👤 Person direkt benennen` → erst danach die Namensauswahl.

Damit ist der Ablauf auf jedem Bild einheitlich: **erst Frage, dann Auswahl**.

### 2. Namens-Suche über den ganzen Katalog (verifiziert, keine Codeänderung)
Die Suchauswahl (`baueSuchMitVorschlaegen`) bekommt bereits die **komplette**
Katalogliste (`_optionen_sortiert` liefert alle Personen, nur nach
Wahrscheinlichkeit sortiert) und filtert per Teiltreffer
(`name.toLowerCase().indexOf(q) !== -1`). Verifiziert am laufenden Server:

```
GET /api/gesichter (X-API-Key) -> 30 Personen
"helga"      -> ["Oma Helga"]
"oma helga"  -> ["Oma Helga"]
"HELGA"      -> ["Oma Helga"]
"oma"        -> ["Oma Helga"]
```

Wortstellung und Groß-/Kleinschreibung sind egal.

## Verifikation
- `node --check frontend/app.js` → Exit-Code 0.
- Servierter Stand: `curl -s http://127.0.0.1:8080/app.js | grep -c baueKeinePersonGate` → 2
  (Definition + Aufruf); `index.html` liefert `app.js?v=20260914bX`.
- Katalog-Suche wie oben am Endpunkt belegt.

## Unverändert
Bilder, Kacheln-Reihenfolge (Top 5), Speichern/Skip, Persistenz (`ui`-Feld),
Backend und Endpunkte. Cache-Bust-Version in `frontend/index.html`: `bW` → `bX`.
