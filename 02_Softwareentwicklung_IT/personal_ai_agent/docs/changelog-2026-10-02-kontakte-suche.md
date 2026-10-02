# Änderungsprotokoll 02.10.2026 — Kontakte am Profil + Suche (Issue #3, Teil A/B)

Wunsch Sebastian: Telefonnummern und Geburtstag aus dem Telefonbuch sollen am Profil einer
Person hängen — „damit wir nicht nachher zwei Personendatenbanken haben"; später soll der
Agent auch anrufen können. Entscheidung (Issue #3): **Weg B, PC per Kabel** — am Handy direkt
geht es heute nicht (Termux aus dem Play Store, Termux:API aus F-Droid: verschieden signiert,
`termux-contact-list` antwortet nicht).

## Design: ein Format, austauschbare Quelle

- Quelle der Kontakte bleibt das **Android-Telefonbuch** (mit Google-Kontakte abgeglichen).
  `~/foto_sortierung/kontakte.json` ist nur ein Auszug: `{id, name, nummern[], geburtstag}`
  (`id` = Android `contact_id`, Geburtstag `JJJJ-MM-TT` oder `--MM-TT` ohne Jahr).
- Das Profil einer Person **verweist** per Kennung darauf (`profil.kontakt`, Kopie für die
  Anzeige) — keine zweite Personendatenbank.
- Heute schreibt der PC die Datei (unten); später kann die Hey-Agent-App (Berechtigung
  „Kontakte lesen", ohne Termux:API) **dieselbe** Datei schreiben — Backend und Quiz bleiben.
- Kein MCP-/Google-Zugang über Claude: Kontakte laufen nie durch ein Sprachmodell.

## Teil A — Kontakte

- Neu **`tools/handy/kontakte_aufs_handy.py`**: liest das Telefonbuch per `adb` (`content
  query` mit `contact_id`; Zerleger aus `tools/whatsapp/zuordnung_bauen.py` wiederverwendet),
  fasst je Kontakt-Kennung zusammen, Nummern gesäubert und ohne Doppelte, Geburtstag mit Jahr
  bevorzugt, Jahrestage zählen nicht. Ohne Schalter Trockenlauf (**nur Zahlen**), `--schreiben`
  schreibt (atomar, `.vorher`), `--senden` legt die Datei zusätzlich nach `/sdcard/Download`
  (push + Größenprobe). Ziel im Repo → Exit 2, Telefonbuch nicht lesbar → Exit 3.
- Übergabe: `kontakte.json` in den `--dateien`-Listen von `start-termux.sh` (3 Stellen) und
  `termux/agent-ensure.sh` (2 Stellen); Wächter `test_uebergabe_uebernehmen.py` jetzt **8**
  Dateien, Name aus `gruppen_quiz.KONTAKTE_DATEINAME`.
- `backend/app/services/gruppen_quiz.py`: `kontakte.json` lesen (zwischengespeichert);
  Antwort `name` mit `kontakt_id` verknüpft das Profil (ohne eingegebenen Namen gilt der
  Kontaktname, ein eigener Name bleibt), unbekannte Kennung → Fehler ohne Schreiben;
  Rückgängig nimmt die Verknüpfung ab (`kontakt_vorher`); `profil()` liefert den Kontakt mit.
- **Suche** `GET /api/gruppen/suche?q=&limit=` (≤ 50): zuerst schon benannte Personen, dann
  Kontakte; Treffer am **Wortanfang**, Groß/Klein und Umlaute egal („mül", „muel", „mul" finden
  Müller); ohne Suchwort nur Personen (kein Telefonbuch-Auszug); Kontakte zeigen, ob sie schon
  mit einem Profil verknüpft sind. Rein lokal, kein Sprachmodell.

## Prüfung (Teil A)

- `backend/tests/test_gruppen_quiz.py` +7 (43 passed): Suche Wortanfang/Umlaute/Reihenfolge,
  leere Frage ohne Kontakte, Verknüpfen, eigener Name + Kontakt, unbekannte Kennung, Rückgängig,
  ohne Kontaktdatei, Route.
- `backend/tests/test_bestand_und_handy_uebergabe.py` +5 (14 passed): Zusammenfassen je
  Kennung, Trockenlauf ohne Namen/Nummern in der Ausgabe, Senden (außerhalb des Repos, nie
  `rm`), Repo-Ziel Exit 2, adb-Fehler Exit 3, Säubern.
- Voller Prüfbefehl: siehe Commit.

## Lauf (startet Sebastian, Handy am Kabel)

    backend\.venv\Scripts\python.exe tools\handy\kontakte_aufs_handy.py --senden
