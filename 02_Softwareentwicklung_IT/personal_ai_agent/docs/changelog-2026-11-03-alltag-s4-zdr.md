# Changelog 03.11.2026 — Alltagsprotokoll S4: keine Datensammlung in Nebenaufrufen

Plan: `.hermes/plans/alltagsprotokoll.md`, Schritt S4 (Hermes, Runde 1, Punkt C).

## Befund

Fünf OpenRouter-Aufrufe in `llm_service.py` schickten nur `allow_fallbacks` oder gar keine
Anbieter-Vorgabe. OpenRouters Routing durfte dann bei einem Anbieter landen, der Prompts speichert.
In diesen Aufrufen stehen Sebastians eigene Sätze:

| Aufruf | Inhalt |
|---|---|
| `extract_memories` | Nachricht + Antwort (Gedächtnis-Auszug) |
| `extrahiere_gesichts_anlernen` | Anlern-Satz mit Namen |
| `braucht_hermes` | Nachricht (Hermes-Weiche) |
| `extrahiere_datei_such_intent` | Suchfrage |
| `polish_text` | Diktat (maskiert, aber ohne Riegel) |

## Behoben

Alle fünf nutzen jetzt `self._extra_body(no_retention=True)`, also `provider.data_collection = "deny"`
und weiter `allow_fallbacks`. Findet sich kein Anbieter ohne Datensammlung, lehnt OpenRouter ab.
Die Aufrufe fangen das schon heute ab (Standardwert bzw. nächstes Glättungsmodell, sonst Rohtext).

Der Hauptchat bleibt unverändert: Dort entscheidet der Schalter `no_retention` der Anfrage.

## Offen

- **Spracherkennung (`transcribe`)**: Laut OpenRouter-Doku kennt `/audio/transcriptions`
  `provider.data_collection`. Das dokumentierte Beispiel ist aber ein JSON-Body mit `input_audio`.
  Der Code sendet über das OpenAI-SDK multipart (`file=`). Ob das Feld dort ankommt, ist
  ungeprüft. Ohne echten Test mit Audio wird das Diktat nicht umgebaut.

## Nachtrag (Hermes, Runde 1, Einwand 2): kein Diktattext mehr im Log

`transcribe` schrieb die ersten 80 Zeichen des erkannten Textes ins Log. Jetzt stehen dort nur
Modell und Zeichenzahl (Planregel). Test: `test_erkennung_schreibt_keinen_diktattext_ins_log`,
vorher rot.

## Prüfung

- Neu: `test_llm_zdr_alle.py` (5, je Aufrufweg). Vorher 5 rot, jetzt grün.
- Nachbartests (Spracheingabe, Gesichter-Chat, Dateisuche, Sprach-Endpunkt, Gedächtnis): 80 grün.
