# Änderungsprotokoll 07.10.2026 — Eigene Notizen vorlesen und im Chat sichtbar machen

## Was

### 1. Notizen und Geschichten vorlesen (Frontend)
- `frontend/index.html`: neue Kopfzeile mit Vorlese-Knopf über jedem Notizblock
  (`#erzaehl-gruppen-geschichten-kopf` mit `#erzaehl-gruppen-geschichten-vorlesen` in der
  Übersicht, `#erzaehl-geschichten-kopf` mit `#erzaehl-geschichten-vorlesen` beim Einzelbild),
  dazu `#erzaehl-alles-vorlesen` in der Titelzeile.
- `frontend/erzaehlen.js`:
  - neue reine Funktion `erzaehlAllesText(teile)` — Tagebuch-Fassung: Titel, Bildzahl,
    Personen, Notizen in dieser Reihenfolge; leere Teile fallen weg, doppelte nur einmal,
    jeder Teil wird mit einem Punkt abgeschlossen, vorhandene Satzzeichen bleiben.
  - `vorlesenText(sprech)` aus `vorlesen(quelleId)` herausgezogen (Browser-Stimme, sonst
    `POST /api/speak` — die Android-WebView hat keine eigene Stimme).
  - `allesVorlesen()` sammelt die sichtbaren Teile; `geschichtenTextSammeln()` liest nur die
    Notiztexte (nicht die Abschnitts-Köpfe „Zu diesem Bild" / „Zur ganzen Gruppe").
  - Die Kopfzeile erscheint nur, wenn wirklich Notizen da sind (`childElementCount === 0`).
- `frontend/style.css`: `.erzaehl-geschichten-kopf` (+ `[hidden]`-Regel).
- Cache-Kennungen `style.css?v=20261007A` und `erzaehlen.js?v=20261007A`.

### 2. Eigene Notizen für den Chat sichtbar (Backend)
- Neu: `backend/app/services/notizen_service.py`. Liest **nur** und sucht offline:
  - Personen-Profile (`personen_profile.json`) — Beziehung und aktuelle Notizen je Person
    (zurückgenommene zählen nicht);
  - Geschichten (`geschichten.jsonl`) — nur die neueste Fassung (über `ersetzt` verdrängte
    Zeilen fallen weg, dieselbe Regel wie im Erzähl-Dienst).
  - Suche: Kleinschreibung, Umlaute vereinheitlicht (ß → **ss**, weil ß im Deutschen ein
    Doppel-s ist — als einzelnes s wäre „Buße" nicht mehr mit „Busse" auffindbar),
    Wortanfang zählt („Urlaub" findet „Urlaubsbilder"); Begriffe unter 3 Zeichen werden
    nicht gesucht; ein Begriff ohne Treffer wird **ehrlich** gemeldet, samt Angabe, wie
    viele Notizen und Geschichten durchsucht wurden.
  - Keine Koordinaten, keine Kennungen, keine Telefonnummern in der Ausgabe.
- `backend/app/services/werkzeuge.py`: neues Chat-Werkzeug `notizen_suchen` (Argumente
  `frage`, `person`, `anzahl`) mit Beschreibung samt Beispielen („was arbeitet mein Bruder").

## Warum
- Wunsch 07.10.2026: „ich kann mir die Notiz nicht vorlesen, das soll ja Tagebuch sein" —
  bisher ließen sich nur die Personen-Zeilen vorlesen, nicht die Notizen/Geschichten.
- Fehler 07.10.2026: Auf die Frage nach dem Beruf einer notierten Person konnte der Agent
  nicht antworten, obwohl die Angabe in der Personen-Notiz stand. Ursache gemessen:
  `personen_profile.json` wurde von **keinem** Chat-Werkzeug gelesen (`personen_liste` liest
  den Gesichts-Katalog mit Name/Rolle/Beziehung, ohne Notizen; `archiv_suchen` liest nur die
  Chat-Archive, `erinnerungen_suchen` nur den Erinnerungs-Speicher). Die Notiz war also da,
  aber unsichtbar.

## Prüfung
- `cd backend && .venv/Scripts/python -m pytest tests/test_notizen_service.py -q`:
  **14 passed**, Exit 0.
- `cd frontend && node tests/test_erzaehlen.js erzaehlen.js`: alle Prüfungen bestanden
  (neu darunter: acht Prüfungen zu `erzaehlAllesText`, sechs zur Verdrahtung/den Knöpfen).
- Voller Prüfbefehl vor dem Commit: siehe Protokollzeile in `CLAUDE.md`.

## Grenzen
- Die Suche ist eine **Wortsuche**, keine Bedeutungs-Suche: „Beruf" findet keine Notiz, in
  der nur „Tischler" steht. Das ist bewusst so (kein Netz, keine Kosten) — wer sinngemäß
  suchen will, braucht den Vektor-Weg über das Archiv.
- Notizen mit mehr als 400 Zeichen werden für die Suche gekürzt.
- Die Kopfzeile erscheint erst, wenn die Notizen geladen sind; ohne Notizen bleibt sie aus.
- `geschichten.jsonl` wird über den Erzähl-Dienst gelesen — liegt dort keine Datei, ist das
  Ergebnis leer (kein Fehler).
