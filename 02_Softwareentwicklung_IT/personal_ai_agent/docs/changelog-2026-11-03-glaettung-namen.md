# Changelog 03.11.2026 — Glättung maskiert Namen wirklich

## Befund

`polish_text` (Glättung des Diktats) baute den `PIIShield` aus `bekannte_namen_streng().volle`.
Das sind **normalisierte** volle Namen („juergen testmueller"). Der Schild sucht ohne Umschrift:

- Namen mit Umlaut („Jürgen") wurden nicht gefunden → Klartext ans Modell.
- Ein Vorname allein wurde nie maskiert (nur volle Namen registriert).

Gefunden beim Bau von Alltagsprotokoll S3/S5; mit erfundenen Namen belegt (Test vorher rot).

## Änderung

- Neu `pii_shield.schild_aus_namen(namen, text)`: registriert Namen **samt Namensteilen ab 3
  Zeichen** in Originalschreibweise; zurück kommt jedes Kürzel in der Schreibweise aus `text`.
- `polish_text` nimmt `werkzeuge.namen_fuer_maskierung()` (Originalschreibweise, aus #18) und
  `schild_aus_namen`. Scheitert der Bau, wird das protokolliert (vorher still verschluckt).
- `alltag_struktur.baue_schild` nutzt dieselbe Funktion — eine Stelle statt zwei.

## Unverändert (bewusst)

Gibt es keine lesbare Namensliste, glättet `polish_text` weiterhin ohne Namensschutz (der
Rohtext enthält dann keine registrierbaren Namen). Ob die Glättung dann ganz ausfallen soll
wie die Websuche, entscheidet Sebastian.

## Prüfung

- Neu: `test_glaettung_namen.py` (3): Vorname mit Umlaut nur maskiert und zurück in der
  gesprochenen Schreibweise, voller Name und Nachname, ohne Namensliste weiter geglättet.
  Vorher 2 rot.
- `test_spracheingabe.py`, `test_pii_shield.py`, `test_llm_zdr_alle.py`, `test_sprache_endpunkt.py`,
  `test_alltag_struktur.py`, `test_alltag_router_eintrag.py` grün (66).
