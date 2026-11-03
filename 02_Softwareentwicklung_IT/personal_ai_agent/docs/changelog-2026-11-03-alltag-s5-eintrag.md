# Changelog 03.11.2026 — Alltagsprotokoll S5 (Teil 2): Satz eintragen

Plan: `.hermes/plans/alltagsprotokoll.md`, Schritt S5. Baut auf S3 (`alltag_struktur`) auf.

## Neu

`POST /api/alltag/eintrag` mit `{text, quelle}` (hinter dem API-Key):

1. Namen holen: `werkzeuge.namen_fuer_maskierung()` — Personen- und Kontaktnamen in
   **Originalschreibweise** (gleiche Quellen und Strenge wie `bekannte_namen_streng`).
2. Satz über `alltag_struktur.strukturieren` in einen Eintrag wandeln und speichern.
3. Antwort `{ok, eintrag, fehlt, modell, kosten_usd}`.

Klappt die Struktur nicht (kein Schlüssel, Netz, unbrauchbare Antwort), wird **nur** ein
Stunden-Eintrag mit den Originalworten für die letzte Stunde gesichert — nichts Geratenes. Die
Antwort ist dann `{ok: false, grund, eintrag, fehlt}`; die Oberfläche (S6) fragt die fehlenden
Felder nach.

Ist die Namensliste nicht lesbar oder leer, geht der Satz **gar nicht** ans Modell (wie beim
Namensverbot der Websuche).

Leerer Text oder kein Objekt ergibt 400, und es wird nichts gespeichert.

## Warum eine eigene Namensfunktion

`bekannte_namen_streng` liefert normalisierte Wörter („juergen"). Der `PIIShield` sucht im Text
ohne Umschrift und hätte „Jürgen" so nicht gefunden.

## Prüfung

- Neu: `test_alltag_router_eintrag.py` (8): Satz strukturiert und gespeichert (Name nicht im
  Aufruf), Schlaf-Satz, ohne Schlüssel nur Originalworte, ohne Namensliste kein Aufruf,
  unbrauchbare Antwort, 400 ohne Speichern, Namensfunktion behält Umlaute, sperrt bei Fehler
  und Leere. Vorher rot (6 Fehler, 2 neu ergänzt).
- `test_alltag_router.py`, `test_alltag_router_s5.py`, `test_alltag_struktur.py` grün.
