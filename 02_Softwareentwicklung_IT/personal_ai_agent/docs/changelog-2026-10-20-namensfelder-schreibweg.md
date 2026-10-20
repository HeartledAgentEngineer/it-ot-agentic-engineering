# Namensfelder: Vorname / Nachname / Spitznamen von Hand setzen (Schritt 2 von 3)

20.10.2026, Hermes-Cron. Fortsetzung von
`docs/changelog-2026-10-20-namensfelder-abgeleitet.md` (Schritt 1: Ableitung nur
beim Lesen). Grundlage: `.hermes/plans/2026-10-20_personen-namensfelder.md` und
die dort festgehaltene Gegenprüfung (EINWAND, neun belegte Befunde).

## Was dieser Schritt baut

**Schreibweg** (`backend/app/services/gruppen_quiz.py`):

- **`namensfelder_saeubern(vorname, nachname, spitznamen)`** — reine
  Prüffunktion, die **vor** dem Schreiben läuft. Nur übergebene Felder kommen
  zurück (`None` = nicht angefasst), leere Eingabe heißt „Handfeld entfernen".
  Spitznamen dürfen als Liste oder als komma-getrennter Text kommen; doppelte
  fallen weg (Groß/Klein gleich), Nicht-Text und zu lange Werte werden
  abgelehnt (`NAMENSFELD_MAX = 40`, `SPITZNAME_MAX = 30`, höchstens
  `SPITZNAMEN_MAX = 10` je Person).
- **`profil_ergaenzen(..., vorname, nachname, spitznamen)`** nimmt die Felder
  an und legt sie im Profil ab. Das Profil ist die Wahrheit: ist ein Handfeld
  gesetzt, hat es Vorrang vor der Ableitung; wird es geleert, greift die
  Ableitung aus Schritt 1 wieder. Die Beziehungs-/Erinnerungs-Prüfung gilt
  jetzt auch für Namen („Bitte eine Beziehung, eine Erinnerung oder einen Namen
  eingeben.").
- **Rückweg:** Jedes geänderte Feld schreibt seinen Vorher-Wert mit
  (`felder_vorher`). `rueckgaengig()` stellt damit den **genauen** Vorher-Stand
  her — auch ein vorher nicht vorhandenes Feld wird wieder entfernt (Auflage aus
  der Gegenprüfung: kein Datenverlust).
- **Zusammenführen mit Wandern der Handfelder (harter Befund 1 der Prüfung):**
  `umbenennen()` auf einen vorhandenen Namen führt die Profile zusammen und
  nahm bisher nur `beziehung`, `notizen` und `kontakt` mit. Jetzt wandern
  `vorname`/`nachname` mit (das Ziel behält Vorrang) und die Spitznamen beider
  Profile werden **vereinigt** (ohne Dubletten, begrenzt). Der Rückweg von
  `umbenennen` ist weiterhin ein vollständiger Schnappschuss (`profile_vorher`)
  und stellt auch diese Felder wieder her.
- **Suche:** `suche(q)` durchsucht jetzt Name **plus** Vorname, Nachname und
  Spitznamen und liefert die Felder je Treffer mit (`vorname`, `nachname`,
  `spitznamen`, `namensfelder_quelle`) — damit kann die Oberfläche sie zeigen
  und die Personensuche nach Spitznamen finden.

**Route** (`backend/app/router/gruppen.py`): `POST /api/gruppen/profil` nimmt
zusätzlich `vorname`, `nachname` und `spitznamen` (Liste) an und reicht sie
durch. Der Kopfkommentar der Datei ist nachgezogen.

## Belege (in diesem Lauf selbst gefahren)

- Neu `backend/tests/test_namensfelder_schreiben.py`: **24 Prüfungen** (nur
  erfundene Namen in `tmp_path`) — Säubern der Eingabe (Kommatext, Dubletten,
  Groß/Klein, zu viele/zu lange, Nicht-Text), Speichern, „nur ein Feld ändert
  sich", Leeren gibt die Ableitung zurück, kein Schreiben ohne Angabe,
  Rückgängig in beiden Richtungen, **Zusammenführen der Handfelder** und
  Rückgängig dazu, Suche über Spitzname/Vorname/Nachname, Route über
  `TestClient`.
  Lauf: `.venv/Scripts/python -m pytest tests/test_namensfelder_schreiben.py -q`
  → **24 passed** (2,07 s).
- Nachbardateien zusammen (`test_namensfelder_schreiben`, `test_name_zerlegen`,
  `test_gruppen_quiz`, `test_gruppen_quiz_video`, `test_gruppen_liste`,
  `test_gruppen_aufloesen`, `test_gruppen_diagnose`,
  `test_personen_werkzeuge_quiz`, `test_werkzeuge`, `test_erzaehlen_personen`)
  → **275 passed, Exit 0** (17,82 s).
- Voller Prüfbefehl im Hauptbaum: siehe Journal des Laufs.

## Was dieser Schritt bewusst NICHT macht (ehrlich)

- **Keine Oberfläche.** Die drei Eingabefelder und die sichtbare Suche sind
  Schritt 3 (Schritt 3 trifft `frontend/gruppen_quiz.js`; der frühere
  Fremdstrang dort ist als `9b6d879` in main, damit ist die Datei frei).
  → **Schritt 3 ist gebaut:** `docs/changelog-2026-10-20-namensfelder-oberflaeche.md`.
- **Keine Migration, keine Umbenennung.** Der Name bleibt die Kennung; die
  Felder sind Zusatz. Alte Profile ohne Felder bleiben unverändert lesbar.
- **Die Ableitung bleibt eine Näherung.** Ohne Familienbezug wird weiterhin kein
  Nachname behauptet; „M." als Nachname-Kürzel, Ziffernnamen und Rollenwörter
  sind bewusst vorsichtig behandelt.
- Alle Prüfungen nutzen **erfundene** Namen; echte Namen wurden weder gelesen
  noch berichtet, kein Bild-/Gesichtsdatensatz berührt, kein Modellaufruf
  (Kosten 0 USD).
