# Änderungsprotokoll 26.10.2026 — Tagesimport im Checks-Fenster (C3)

Plan: `.hermes/plans/2026-10-25_tagesimport-handy.md`, Abschnitt „C3 im Einzelnen“. Vorgänger: `changelog-2026-10-25-tagesimport.md` (C1 + C2).

## Zweck

Der Tagesimport (`tools/handy/tageslauf.py`, standardmäßig aus) lässt sich jetzt in der App sehen und steuern: Schalter, Kamera-Ordner, letzter Bericht je Baustein, Erinnerung an den Gemini-Export.

## Backend

| Datei | Inhalt |
|---|---|
| `backend/app/services/tageslauf_status.py` | Dienst: Stand lesen, Einstellungen ändern. Importiert aus `tools/` nichts; der Schreibhelfer (Zufalls-Temp, `fsync`, `os.replace`, kein symbolischer oder harter Link, nicht im Git-Repo) ist nachgebaut. |
| `backend/app/router/tageslauf.py` | zwei Routen, in `main.py` mit `Depends(auth.require_api_key)` eingehängt |
| `backend/app/router/selbsttest.py` | neuer Block `tageslauf` im Selbsttest (`_tageslauf_info`, wirft nie) |

Datenordner: Umgebungsvariable `TAGESLAUF_DATEN`, sonst `~/foto_sortierung`. Gelesen werden `tageslauf.json`, `tageslauf_bericht.json`, `.tageslauf_stand.json`; geschrieben wird nur `tageslauf.json`. Kein Löschen.

### `GET /api/tageslauf`

Wirft nie, legt nichts an, nennt keinen Pfad des Datenordners. Felder: `ok`, `heute`, `an` (nur echtes `true`), `einstellungen_lesbar`, `kamera_ordner` (`gesetzt`, `wert`), `gemini` (`letzter_export`, `tage_seit_export`, `faellig` bei unbekanntem Datum oder mehr als 60 Tagen), `heute_gelaufen` (Stand `letzter_gesamtlauf` = heute), `bericht_veraltet` (Bericht vorhanden und Datum ≠ heute), `bericht` (`datum`, `zeit`, `exit`, `stand_fortgeschrieben`, `bausteine` mit nur `name`, `status`, `text`; höchstens 10, Texte auf 300 Zeichen gekürzt) oder `null`.

### `POST /api/tageslauf/einstellungen`

Körper `{an?: bool, kamera_ordner?: str, gemini_export_heute?: true}`; mindestens ein Feld, unbekannte Felder werden abgelehnt. Lesen-Ändern-Schreiben: fremde Schlüssel der Datei bleiben stehen. Antwort: derselbe Stand wie beim GET.

| Fall | Status | Datei |
|---|---|---|
| `an` kein echtes Bool; `gemini_export_heute` nicht `true`; leerer/fremder Körper; kein JSON | 400 | unverändert, nichts angelegt |
| `kamera_ordner` unzulässig (kein führendes `/`, nur `/`, `..`, `\`, `//`, Teil mit „crypto“, über 200 Zeichen, Steuerzeichen) | 400 | unverändert |
| Einstellungsdatei vorhanden, aber unlesbar oder kein Objekt | 409 | unverändert |
| Zieldatei ist ein Link (symbolisch oder hart) oder der Datenordner liegt in einem Git-Repo | 403 | unverändert |
| Datenordner nicht beschreibbar | 500 | unverändert |
| ohne gültigen API-Key | 401 | unverändert |

`gemini_export_heute: true` schreibt `gemini_letzter_export` mit dem heutigen Datum. Mehrere Felder in einem Aufruf werden alle oder gar nicht gesetzt.

### Selbsttest

Block `tageslauf`: `an`, `einstellungen_lesbar`, `kamera_gesetzt`, `heute_gelaufen`, `letzter_lauf`, `letzter_exit`, `bericht_veraltet`, `gemini_faellig`, `error`. Im Text eine Zeile „Tagesimport“; fehlt der Block (älteres Backend), entfällt die Zeile.

## Frontend

- `index.html`: neuer Bereich `#tageslauf-block` im Checks-Fenster, hinter `#server-protokoll`, vor `#selbsttest-text`, nicht zugeklappt. Eindeutige IDs: `tageslauf-stand`, `tageslauf-text`, `tageslauf-schalter`, `tageslauf-ordner` (mit Beschriftung), `tageslauf-ordner-speichern`, `tageslauf-gemini`, `tageslauf-status`.
- `app.js`: reine Funktionen `tageslaufText`, `tageslaufSchalterText`, `tageslaufGespeichertText`, `tageslaufFehlerText` (ohne DOM, Klartext ohne Symbole); dahinter `ladeTageslauf` (lädt beim Öffnen und Aktualisieren des Fensters über `ladeSelbsttest`, **kein Polling**) und `speichereTageslauf`. Anzeige nur per `textContent`. Nach jedem Speichern steht eine Rückmeldung („Gespeichert: …“ oder „Nicht gespeichert: <Text vom Server>“); die Knöpfe sind währenddessen gesperrt. Ein gerade getippter Ordner wird beim Neuladen nicht überschrieben. Der Gemini-Baustein des alten Berichts entfällt in der Anzeige, die Gemini-Zeile kommt vom aktuellen Stand.
- `style.css`: Block im dunklen Bestandsdesign, Knöpfe und Eingabefeld mindestens 44 px hoch.
- Cache-Bump: `app.js?v=20261026A`, `style.css?v=20261026A`.

## Tests

| Datei | Umfang |
|---|---|
| `backend/tests/test_tageslauf_status.py` (neu) | 75 Tests (nach Parametrisierung): Lesen, Schreiben, alle Fehlerfälle, Links, Repo-Ziel, Key-Schutz, Selbsttest-Block, Cache-Schlüssel |
| `frontend/tests/test_tageslauf_anzeige.js` (neu) | 86 Prüfungen: reine Funktionen, Verdrahtung, Reihenfolge, IDs, CSS, Cache |
| `frontend/tests/test_selbsttest.js` | +5 Prüfungen für die Tagesimport-Zeile |
| `frontend/tests/test_server_zustand.js` | Reihenfolge um `#tageslauf-block` ergänzt, Cache-Schlüssel auf 20261026A |
| `backend/tests/test_selbsttest.py`, `backend/tests/conftest.py` | Pflichtfeld `tageslauf`; `conftest.py` setzt `TAGESLAUF_DATEN` für jeden Test auf einen tmp-Ordner, damit kein Test das echte `~/foto_sortierung` liest |

Rot zuerst belegt: Backend-Test brach beim Import ab (Modul `tageslauf_status` fehlte), JS-Test mit „Namenstabelle nicht gefunden“. Danach grün (siehe Bericht).

## Offen

- Einschalten und Kamera-Ordner eintragen macht Sebastian jetzt in der App.
- Der erste echte Handylauf (C4) und die Sichtprüfung am Handy sind nicht verifiziert; ein Browserlauf der Oberfläche fand nicht statt.
- Der Kamera-Ordner lässt sich in der App setzen, aber nicht wieder entfernen (leere Eingabe wird mit 400 abgelehnt).
- Im Worktree schlagen drei Quiz-Rahmen-JS-Tests und zwei Shell-Tests in `test_system_update.py` fehl (CRLF-Checkout bzw. bereits im Ausgangsstand rot); sie berühren diese Änderung nicht.
