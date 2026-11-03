# Changelog 03.11.2026 — Anlass-Filter, Mini-Gesichter, Umbenennen (F1, F2, F5)

## F1 — Zeitfilter der Anlässe wirkte nicht

- **Ursache:** Jahr- und Suchfeld riefen `ereignislisteLaden` direkt als Event-Handler auf.
  Das Event-Objekt kam als `anhaengen` an (immer wahr): Die Liste wurde nie geleert, sondern
  bekam Treffer ab Versatz 200 angehängt. Dazu filterten Tipp-Zwischenstände („20" als Jahr)
  und ältere Antworten konnten neuere überschreiben.
- **Behoben:** Handler rufen `ereignislisteLaden(false)` nach 300 ms Tipp-Pause; reine Funktion
  `erzaehlListenParameter` (Jahr erst vierstellig); Anfragezähler verwirft veraltete Antworten.
- **Neu:** Knopf `#erzaehl-reihenfolge` „↓ Neueste zuerst / ↑ Älteste zuerst" (gemerkt unter
  `gp_erzaehl_neueste_zuerst`, Standard: neueste zuerst); Backend `neueste_zuerst=true` dreht die
  Reihenfolge vor dem Blättern.

## F2 — Haken „Nur Gesichter ≥ 50 px" entfernt

- Das Backend filtert jetzt immer (`MIN_GESICHT_PX = 50` als Vorgabe von `/naechste` und `/liste`;
  `min_px=0` schaltet ab). Haken und zugehöriger Code im Quiz sind weg.
- **Mitbehoben (Befund zu F3):** Der Größencheck las nur Foto-Beispiele. Reine Video-Gruppen
  fielen deshalb immer heraus. Jetzt zählt auch ein darstellbares Video-Gesicht (Standbild).

## F5 — Umbenennen im Kontaktbuch

- **Ursache 1:** Rahmen-Namen aus dem Bild-Editor (`bild_korrekturen.json`, Quelle „handy")
  haben in Bildersicht und Bildersuche Vorrang. `umbenennen()` liess sie unverändert, deshalb
  zeigten Rahmen und Suche weiter den alten Namen.
  **Behoben:** Rahmen-Namen werden mit umbenannt (Groß/Klein egal), Rückgängig stellt genau
  die protokollierten Rahmen wieder her (`rahmen_vorher`).
- **Ursache 2:** „✓ Profil speichern" las das Namensfeld nie, der Name hatte einen eigenen Knopf.
  **Behoben:** Ein geänderter Name wird beim Profil-Speichern über `umbenennen()` mitgespeichert;
  die übrigen Felder werden vorher gelesen und gehen nicht verloren.

## Prüfung

- Neu: `test_erzaehlen_reihenfolge.py` (4), `test_gruppen_mindestgroesse.py` (6),
  `test_umbenennen_rahmen.py` (5), `test_erzaehlen_filter.js`, `test_gruppen_ohne_groessenhaken.js`,
  `test_gruppen_profil_name.js`.
- Angepasst: zwei Router-Tests mit 40-px-Testgesichtern rufen jetzt ausdrücklich `min_px=0`.
- Cache: `erzaehlen.js?v=20261103B`, `gruppen_quiz.js?v=20261103A`, `style.css?v=20261103A`.
