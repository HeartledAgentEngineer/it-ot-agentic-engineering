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

## Nachtrag nach Hermes-Einwand (Runde 1)

- **Fail-closed:** Ist die Namensliste nicht lesbar oder leer, schickt `polish_text` **nichts**
  mehr ans Modell und gibt `None` zurück — der Rohtext wird lokal weiterverwendet. Das gilt
  wie bei Websuche und Alltagsprotokoll genau für den Fall „Handy ohne Namensdateien". Die
  erste Fassung dieses Changelogs nannte das harmlos; das war falsch. **Folge:** Am Handy ohne
  Namensdateien wird das Diktat ungeglättet übernommen.
- **Umschrift:** Steht „Jürgen" in der Liste und „Juergen" im Satz, wird auch die Umschrift
  maskiert (`schild_aus_namen` registriert sie mit).
- **Tests unabhängig vom Rechner:** `test_spracheingabe.py` und `test_llm_zdr_alle.py` hingen
  unbemerkt an den echten Namensdateien dieses PCs (742 lesbare Namen, nur gezählt). Sie
  bekommen jetzt eine erfundene Namensliste.

## Prüfung

- Neu: `test_glaettung_namen.py` (5): Vorname mit Umlaut nur maskiert und zurück in der
  gesprochenen Schreibweise, voller Name und Nachname, Umschrift im Satz, ohne Namensliste und
  bei kaputter Quelle geht nichts raus. Vorher rot (erst 2, nach dem Einwand 3 weitere).
- `test_spracheingabe.py`, `test_pii_shield.py`, `test_llm_zdr_alle.py`, `test_sprache_endpunkt.py`,
  `test_alltag_struktur.py`, `test_alltag_router_eintrag.py` grün; volle Suite siehe PR.
