# Changelog 03.11.2026 — Diktat nicht mehr im Log

## Befund

Vor dem Bau der Protokoll-Oberfläche (S6), die über `POST /api/sprache/transkript` diktiert:

- `router/transcribe.py` schrieb die ersten 100 Zeichen von Roh- **und** geglättetem Text ins
  Log (`logger.info`).
- `llm_service.polish_text` schrieb 80 Zeichen des geglätteten Texts ins Debug-Log.

Beides stand im S4-Changelog unter „Offen". Mit S6 kämen sonst Sätze aus dem Alltagsprotokoll
ins Log.

## Änderung

Beide Stellen protokollieren nur noch Zeichenzahl (und Modell bzw. „Rohtext").

## Prüfung

- Neu: `test_sprache_endpunkt.py::test_diktat_steht_nicht_im_log` und
  `test_glaettung_namen.py::test_glaettung_schreibt_keinen_text_ins_log` — vorher rot.
- `test_sprache_endpunkt.py`, `test_spracheingabe.py`, `test_glaettung_namen.py`, `test_llm_zdr_alle.py` grün (43).
