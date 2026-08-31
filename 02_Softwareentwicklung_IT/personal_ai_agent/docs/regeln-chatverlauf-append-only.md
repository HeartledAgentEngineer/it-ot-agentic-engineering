# Regel: Chat-Verlauf ist STRENG append-only

Verbindliche Grundregel für personal_ai_agent (Wunsch Sebastian, 2026-08-31).

## Grundsatz
Der persistierte Chat-Verlauf (`chroma_data/conversations.json`, Service
`backend/app/services/chat_verlauf.py`) ist **append-only**:

- Es werden NUR Nachrichten **angehängt** (`verlauf_nachricht_anhaengen`,
  `finish_exchange`).
- Bestehende Einträge (`role`, `content`, `zeit`, `bild_pfad`) werden
  **nie überschrieben, nie verändert, nie entfernt**.

Der Verlauf ist das Gedächtnis der Unterhaltung — er geht nie verloren und
wird nie stillschweigend korrigiert.

## Was NICHT zählt ("flüchtig")
Interaktive Elemente wie die **Umlenk-Buttons** (wechseln-handy/pc) an
Hermes-Nachrichten sind reine UI-Transporte:

- Sie werden als separate SSE-Message gerendert
  (`data: {"message": …}`, `data: {"done": …}`).
- Sie landen NICHT im persistierten Verlauf.
- Sie dürfen verschwinden oder sich ändern, ohne den gespeicherten Chat
  anzufassen.

## Einzige bewusste Ausnahme
`verlauf_runde_entfernen` (Bearbeiten-Flow) entfernt die letzte User-Runde
samt Antwort — ein EXAKTER, expliziter Nutzer-Wunsch („diese Runde neu
formulieren"). Kein versehentliches/automatisches Überschreiben.

Alles andere, was Runden löscht oder Bestands-Einträge mutiert, ist verboten.

## Technische Regeln beim Codieren
- Beim Anhängen nie `conversations[conv] = [...]` oder `del`/Slice-Zuweisung
  auf Bestandteile — immer `.append(...)`.
- Kein Server mit leerem/kaum gefülltem Stand darf eine intakte Datei mit
  Nachrichten überschreiben (Schutz in `_lade_verlauf`: Restore aus dem
  jüngsten nicht-leeren Backup, falls die Datei leer geladen wird).