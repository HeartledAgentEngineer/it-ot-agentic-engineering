# Änderungsprotokoll 06.10.2026 — Erzählen: Anlass-Titel selbst ändern (#14)

Befund Sebastian: Viele automatische Titel sagen ihm nichts — mehrere Konzerte an verschiedenen
Tagen heißen gleich (Name eines vermuteten eigenen Event-Ordners), andere nur „Park" oder
„Sonnenuntergang". Ursache: Die Anlässe sind nach dem Datum im **Dateinamen** gebündelt, das Thema
stammt aus einem einzigen Vision-Blick mit fester 44-Themen-Liste, der Event-Name aus dem Abgleich
mit Ordnernamen. Ort, Personen und Bildinhalt fließen noch nicht ein (dafür #15/#16 im Plan).

**Entscheidung Sebastian:** Sortieren (N8) bleibt gesperrt, bis die Anlässe im Erzählen angesehen
und benannt sind; die eigenen Namen werden später zu den Ordnernamen. Die Erzählen-Ereignisse sind
dieselben Anlässe wie im Sortierplan (2.204 − 77 Fotobuch-Seiten = 2.127).

## Änderung

- **Backend** (`erzaehl_service`): eigene Titel in `anlass_umbenennung.jsonl` (im Ordner der
  Geschichten), **nur anhängend** (`flush` + `fsync`), je Zeile `kennung`, `name`, `zeit`, `vorher`.
  Je Anlass gilt die neueste Zeile; ein leerer Name setzt auf den automatischen Titel zurück; nichts
  wird überschrieben. `titel_setzen()` prüft, dass der Anlass existiert und der Titel höchstens 120
  Zeichen hat (Leerraum wird zusammengezogen). Liste und Detail liefern `titel` (eigener gewinnt),
  `titel_eigen`, `titel_automatisch`; die Suche findet beide Titel; eine neue Geschichte merkt sich
  den gültigen Titel.
- **Route:** `POST /api/erzaehlen/ereignisse/{kennung}/titel` mit `{"name": "…"}` (leer =
  automatisch); HTTP 400 mit deutschem Text bei unbekanntem Anlass oder zu langem Titel.
- **Frontend:** Titelzeile oben im Anlass (Übersicht und Einzelbild) mit ✏️; das Feld ist mit dem
  jetzigen Titel vorbelegt, ✔/Enter speichert, ✕/Escape bricht ab, „↺ Automatisch: …" setzt zurück.
  Die Liste wird sofort mitgezogen. Nebenbei: Pfeiltasten in einem Eingabefeld blättern nicht mehr
  die Diashow. Reine Funktion `erzaehlTitelSaeubern`. `[hidden]`-Regel für das Titelfeld.
- Cache-Bump: `style.css?v=20261006D`, `erzaehlen.js?v=20261006C`.

## Prüfung

- Neu `backend/tests/test_erzaehlen_titel.py` (8 Tests): automatischer Titel ohne eigenen; eigener
  gewinnt in Liste und Detail; Suche über beide; nur anhängend, neuester gilt, leer setzt zurück,
  `vorher` als Rückweg; Grenzen (unbekannt, zu lang → nichts geschrieben); kaputte Zeilen werfen
  nicht; Geschichte merkt sich den gültigen Titel; Route (200, 400, Zurücksetzen).
- `frontend/tests/test_erzaehlen.js` Abschnitt 11; alle 25 Frontend-Testdateien Exit 0.
- Prüfstand Edge headless 375 px, echter Code, Attrappe: ✏️ öffnet das Feld (vorbelegt), Enter
  speichert „Testfestival 2022 mit Freunden" (Leerraum gesäubert) — Titel oben und Listenzeile
  geändert; beim zweiten Öffnen „↺ Automatisch: Testausflug"; Escape schließt nur das Feld;
  Zurücksetzen → „Testausflug"; an die Route gingen genau die zwei erwarteten Namen.
- Prüfbefehl: siehe Commit.
