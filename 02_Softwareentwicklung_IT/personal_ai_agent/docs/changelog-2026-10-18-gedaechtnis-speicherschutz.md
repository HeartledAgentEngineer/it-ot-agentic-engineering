# Chat-Gedächtnis: ausfallsicheres Speichern

## Umfang

Erster technischer Schritt für die spätere Verwaltung von Erinnerungen aus
Chats. Keine neuen Chat-Schreibwerkzeuge und keine automatische Bereinigung.
Originalarchive und vorhandene Erinnerungsbestände werden nicht migriert.

## Änderung

- `SimpleMemoryStore.connect()` lädt zunächst einen vorläufigen Bestand und
  übernimmt ihn nur als JSON-Liste mit Objekt-Einträgen, eindeutiger nichtleerer
  String-ID und String-Inhalt. Eine fehlende Datei bleibt ein gültiger neuer
  leerer Speicher. Unbekannte Zusatzfelder gültiger Einträge bleiben erhalten.
- Bei ungültiger Datei oder Lesefehler wird `MemoryStoreError` ausgelöst,
  statt still mit einem leeren Bestand weiterzuarbeiten. Der Speicher bleibt
  ungeladen, weitere Zugriffe versuchen erneut zu laden. Neu eingeführte
  Fehlermeldungen und Fehler-Logs enthalten keine Inhalte oder Dateipfade;
  geloggt wird höchstens der technische Ausnahmetyp.
- Änderungen werden vollständig in eine eigene temporäre Datei im selben
  Verzeichnis geschrieben, mit `flush()` und `os.fsync()` synchronisiert und
  geschlossen. Erst `os.replace()` ersetzt die bestehende Datei.
- Alle fünf öffentlichen Änderungen (Anlegen, Aktualisieren, Vektor setzen,
  einzelnes Löschen, Leeren) sichern ihren vorherigen Arbeitsspeicherstand
  unabhängig. Schlägt das Schreiben fehl, wird dieser wiederhergestellt und
  ein Fehler gemeldet; es gibt dann keine Erfolgsantwort.
- Eigene temporäre Dateien werden bei Fehlern entfernt, keine fremden Dateien.
  Verweigert das Betriebssystem auch das Entfernen, wird dies als separater
  pfadfreier Speicherfehler gemeldet, nicht als Erfolg.
- Nach einem fehlgeschlagenen Laden im laufenden Prozess kann auch `clear_all`
  den beim Laden als beschädigt erkannten Speicher nicht still leeren.
- `GET /api/health` bleibt bei `MemoryStoreError` mit HTTP 200 und `status: ok`
  erreichbar. `memory_available: false` kennzeichnet das nicht verfügbare
  Gedächtnis; die unbekannte `memory_count` wird weggelassen, nicht als null
  oder als angeblich leerer Bestand ausgegeben. Im Normalfall sind
  `memory_available: true` und die tatsächliche Anzahl vorhanden. Übrige
  Gesundheitsfelder bleiben unverändert, andere unerwartete Fehler werden
  nicht pauschal verschluckt. Die bestehende Oberfläche prüft auf vorhandene
  `memory_count` und braucht keine Frontend-Änderung für diesen Fehlerfall.

## Bewusste Grenzen

Kein Schutz gegen konkurrierende Änderungen, auch nicht durch Threads derselben
Instanz oder durch mehrere Prozesse/Speicherinstanzen. Externe Änderungen nach erfolgreichem Laden werden nicht
vor jedem Schreibvorgang neu eingelesen. Damit kann auch eine nachträglich von
außen beschädigte Datei durch einen bereits geladenen Prozess überschrieben
werden. Mehrschreiberschutz bleibt vor automatischer Verwaltung erforderlich.

Kein Versprechen vollständiger Dauerhaftigkeit bei Stromausfall des ganzen
Systems (das Verzeichnis selbst wird nicht synchronisiert). Bei hartem
Prozessabbruch kann eine eigene temporäre Datei übrigbleiben; es gibt keine
automatische Temp-Dateibereinigung oder Reparatur eines defekten Originals.
Der bestehende Startpfad fängt Speicherfehler weiterhin ab und startet die
anderen Funktionen; sein alter Hinweis „unavailable until restart“ ist nicht
die verbindliche Beschreibung des erneuten Ladeversuchs.

## Prüfung

`backend/tests/test_memory_store_sicherheit.py` verwendet ausschließlich echte
Dateioperationen mit erfundenen Daten in `tmp_path`. Abgedeckt werden defekte
Dateien, Strukturfehler, unveränderte Metadaten, fehlgeschlagene Serialisierung,
Ersetzungsfehler bei allen fünf Änderungen einschließlich erfolgreichem
erneutem Versuch, pfad-/inhaltsfreie Ladefehler, unbekannte IDs, Neustart und
die Reihenfolge vollständiges Schreiben → Synchronisieren → Ersetzen.
Zusätzlich prüft ein Request-Test ohne Server-Startup den gültigen und den
defekten temporären Speicher über `/api/health`; die LAN-Abfrage ist ersetzt,
es wird weder ein Gerät gesucht noch ein externer Server kontaktiert.

Fokussierter Prüfbefehl aus `backend/` mit dem vorhandenen Projekt-Interpreter:

```text
python -m pytest tests/test_memory_store_sicherheit.py tests/test_gedaechtnis_qualitaet.py -q
```

Das vollständige Projekt-Gate bleibt `python -m pytest tests/ -q` aus `backend/`.
Ein fokussierter Lauf ersetzt es nicht. Reale Daten wurden für diese Änderung
weder geöffnet noch bereinigt.
