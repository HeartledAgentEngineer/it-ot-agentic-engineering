# Brainstorm: Ein-Chat-Architektur — Kontext, Erinnerung, Kosten

**Ziel:** Ein einziger, fortlaufender Chat-Thread. Der Agent (Personal AI Agent)
soll bestmögliche Antworten liefern, Kontext + Erinnerungen nutzen, aber **nicht**
den ganzen Chat unbegrenzt mitschicken (Kosten-Effizienz, keine Kontext-
Explosion). Er soll wissen, worum es geht, auch wenn das Gespräch schon lange läuft.

## Die Grundfrage
Wie viel/strukturiert Kontext geht in jede Anfrage, damit die Antwort gut ist,
ohne Token zu verschwenden?

## Ist-Zustand (verifiziert)
- **Volltext-Kontext:** `/api/chat` + `/chat/stream` schicken die gesamte
  `history` der Conversation (in `llm_service`) — bei langem Chat wird das
  unendlich groß/teuer.
- **Erinnerungen:** `memory_service.retrieve_relevant_memories(frage, top_k=5)`
  holt semantisch relevante Vektor-Erinnerungen (ChromaDB) — begrenzt (5).
- **Hermes-Delegation:** bekommt jetzt ein kompaktes Kontext-Paket (C-Variante:
  letzte 6 Nachrichten + 3 Erinnerungen, gekürzt).

## Die Spannung
- **Mehr Kontext** → bessere Antwort, aber teurer + langsamer + Kontext-
  Explosion.
- **Weniger Kontext** → günstig, aber Antwort verliert den Bezug.

## Lösungsrichtungen (zum Grillen)

### Option A — Rollende Zusammenfassung (Rolling Window + Summary)
- Der Thread hält die **letzten N Nachrichten** (z. B. 15) als vollständigen
  Kontext.
- Alles Ältere wird (periodisch) zu einem **kompakten Summary** gerollt
  (einmal pro Konversation, vom kleinen LLM erzeugt).
- Jede Anfrage = [Summary deines bisherigen Gesprächs] + [letzte N] + Frage.
- **Pro:** Kontext bleibt klein, nichts geht völlig verloren, überschaubare
  Kosten.
- **Contra:** Summary verliert Details (kein "wörtlich"). Einen Extra-LLM-Call
  für die Zusammenfassung.

### Option B — Semantische Selektion (Nur Relevantes in den Prompt)
- Statt ganzer Historie: **relevante Nachrichten** via Vektor-/RAG-Suche über
  deinen Chat-Verlauf (ChromaDB) zur aktuellen Frage.
- Kontext = [relevante alte Nachrichten] + [letzte N] + Frage.
- **Pro:** Präzise, nutzt dein Wissen, günstig (nur Relevantes).
- **Contra:** Verknüpfung zu "warum" kann fehlen, wenn die Suche nichts findet.

### Option C — Hybrid (Empfohlenes Konzept)
- **Rolling Summary** für die Struktur (Vergangenheit im Kern) + **relevante
  Erinnerungen/Nachrichten** (semantisch zur Frage) + letzte N Nachrichten.
- Stufenweise: Kurze Fragen → nur letzte N + Erinnerungen. Komplexe/follow-up →
  + Summary.
- **Pro:** Beste Balance aus Genauigkeit + Kosten, skaliert.
- **Contra:** Etwas mehr Aufwand beim Bauen (Zusammenfassung + Selektion).

## Offene Entscheidungen (für grill-me/Grillen)
1. Wann rollen (alle N Nachrichten? bei Thread-Länge > X)?
2. Wie groß darf das Summary werden (Token-Budget)?
3. Wie aggressiv selektiert die semantische Suche (top_k)?
4. Brauchen wir eine "Zusammenfassen"-Schaltfläche im UI (manuell) oder
   automatisch?
5. Speichern wir das Summary persistent (pro Conversation) oder nur in-memory?

## Annahmen
- Personal AI Agent ist Single-User (keine Multi-Tenant).
- Kostenfokus: günstig bleiben (DeepSeek-Flash-Standard); nur Zusammenfassung
  darf kleinen Extra-Call kosten.
- Der eine Thread ersetzt Chat-Switcher (`+`-Button weg).
