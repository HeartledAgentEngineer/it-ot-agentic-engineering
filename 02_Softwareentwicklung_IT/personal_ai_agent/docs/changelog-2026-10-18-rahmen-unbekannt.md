# 18.10.2026 — Schritt E: Rahmen von Hand aufziehen, der Rahmen startet als „unbekannt"

Plan „Rahmeneditor im Detailbild" (Fassung 13), Abschnitt 4, **Schritt E** (Auftragspunkt 2b) aus
dem 16.10.-Auftrag: *„Rahmen von Hand aufziehen, wenn die Erkennung scheitert; der Rahmen startet
als ‚unbekannt' … und lässt sich über das Menü aus Schritt G zuordnen."*

## Was neu ist

| Ort | Neu |
|---|---|
| `frontend/app.js`, `zeigeBildVollbild` (Werkzeugleiste) | Knopf **„＋ Rahmen"** — nicht in der Referenz-Nachbearbeitung (dort gehört der Rahmen zu einer bekannten Referenz) |
| `frontend/app.js`, `rahmenZeichnenStarten()` | Zeichenfeld über der Bildbox: mit dem Finger ein Rechteck ziehen (`pointerdown/move/up`, Abbruch über `pointercancel`). **Nur ohne Anzeige-Drehung** — bei gedrehter Anzeige kommt ein ehrlicher Hinweis statt eines schief sitzenden Rahmens. Zu klein (< 8 px) = ehrliche Meldung, kein Rahmen |
| `frontend/app.js`, `rahmenAusZeichenfeld(x, y, w, h)` | Übernimmt das gezeichnete Rechteck als Rahmen, wählt ihn aus und meldet, dass er als „unbekannt" angezeigt wird |
| `frontend/app.js`, `rahmenUnbekanntAnhaengen(e, pfad, norm)` | Hängt den Rahmen **ohne Person** an den Editor an (`personen[idx] = ''` = ausdrücklich unbekannt) und merkt ihn lokal. **Kein Server-Schreibvorgang** — ohne Person gibt es keine Referenz und keinen Vektor |
| `frontend/app.js`, `rahmenPersonText` / `rahmenUnbekannt` | Anzeigetext: ohne Person „unbekannt". `undefined` (Server-Rahmen, keine Aussage) ist **nicht** „unbekannt" |
| `frontend/app.js`, `unbekannteRahmenLaden/Merken/Vergessen/Schreiben` | Lokaler Browserspeicher (`localStorage`, Schlüssel `quiz_rahmen_unbekannt`, je Bildpfad). Idempotent je Region; Löschen im Editor nimmt den Rahmen auch dort wieder heraus |
| `frontend/app.js`, `rahmenListeVerschmelzen(gesichter, vorNorm)` | Die Rahmen-Verschmelzung ist eine eigene, prüfbare Funktion. **Neu:** Rahmen **hinter** der Serverliste (von Hand gezogen) überleben das erneute Öffnen **desselben** Bildes |
| `frontend/app.js`, `speichereEditorRahmen` | Riegel: ein Rahmen mit `personen[idx] === ''` wird **nicht** gespeichert. Sonst landete er bei der **globalen** Zielperson des Bildes — eine falsche Zuordnung |
| `frontend/app.js`, `resync()` / `rahmenElement(i)` | Rahmen ohne Person sind **gestrichelt** und tragen die Marke **„unbekannt"**. Rahmen-Elemente entstehen jetzt an **einer** Stelle und werden auch für später gezeichnete Rahmen gebaut (inkl. Ziehen/Ziehen der Größe) |
| `frontend/index.html` | Cache-Schlüssel `app.js?v=20261016H` → **`20261018I`** |

## Warum die Verschmelzung geändert werden musste (belegter Verwerf-Pfad)

`baueBildEditor`/`zeigeBildVollbild` baute die Rahmenliste **ausschließlich** über die Serverliste
(`for (let i = 0; i < gesichter.length; i++)`) — ein Rahmen ohne Server-Eintrag fiel beim nächsten
Öffnen weg. Belegt und in Zahlen gemessen in
`docs/changelog-2026-10-18-handrahmen-verwerfpfade.md` (Pfad 1 und Pfad 2; Pfad 2 = die Bestätigungen
im Backend halten nur die letzten **500** Bilder, deshalb hängt ein unbekannter Rahmen am lokalen
Browserspeicher und **nicht** am Server-Fortschritt).

## Belege (in diesem Lauf selbst ausgeführt)

- Neuer Test `frontend/tests/test_quiz_rahmen_unbekannt.js` (6 Abschnitte A–F, führt die echten
  Funktionen aus): **alle Prüfungen bestanden, Exit 0** —
  A „unbekannt" statt erfundener Person;
  B der gezogene Rahmen sitzt hinter der Serverliste, ist als unbekannt markiert, **0 Sendeversuche**,
  **nicht** als bestätigt gemerkt;
  C Pfad 1 gebunden: Live-Änderung gewinnt, gelöscht bleibt gelöscht, der gezogene Rahmen ist noch da,
  **Gegenprobe** zeigt, dass die alte Regel ihn verloren hätte, anderes Bild nimmt nichts mit, Pixel-Rest
  bleibt erhalten;
  D Pfad 2 gebunden: Speicher je Bildpfad, idempotent, Vergessen nimmt genau eine Region, **gesperrter
  Browserspeicher stürzt nicht ab** und meldet ehrlich;
  E der Riegel: kein Sendeversuch für „unbekannt", Meldung mit Grund — **Gegenprobe:** ein normaler
  Server-Rahmen wird weiter gespeichert;
  F die Verdrahtung im Quelltext (Knopf, Zeichenfeld mit `pointercancel`, Elemente über **alle**
  Rahmen, alte Schleife weg, Cache-Schlüssel `I`).
- `test_quiz_rahmen_quelle.js` an **einer** Stelle nachgezogen: das Seeden aus `bbox_norm` steht jetzt
  in `rahmenListeVerschmelzen`; geprüft werden deshalb **zwei** Zusicherungen (Editor ruft die
  Verschmelzung auf **und** die Regel steht in ihr) — zusammen dieselbe Aussage wie vorher.
- Alle Frontend-Tests über den Prüfbefehl: `.venv/Scripts/python.exe -m pytest tests/test_frontend_node.py -q`
  → **43 passed**, Exit 0.
- **Erster Tor-Lauf war rot — und zwar an einem echten Wächter, nicht an der Substanz:**
  `backend/tests/test_system_update.py::test_frontend_hat_update_knopf_rueckmeldung_und_neuen_cache_stand`
  prüfte den **festen** Wert `'app.js?v=20261016' in index` und wurde damit bei jedem Hochziehen des
  Cache-Schlüssels rot (1 failed, 4715 passed). Der Wächter prüft jetzt, was er meint:
  `re.search(r"app\.js\?v=(\d{8}[A-Z]?)", index)` muss treffen **und** der Schlüssel
  `>= "20261016"` sein. Damit bleibt die Zusicherung (kein Laden ohne aktuellen Cache-Schlüssel)
  erhalten und wird nicht mehr bei jeder Erhöhung falsch rot.
- Zweiter Anlauf: `pytest tests/test_system_update.py tests/test_frontend_node.py -q` → **50 passed**,
  Exit 0; volles Tor über den Commit-Haken Exit 0 (Zahlen im Journal/Prüfprotokoll).

## Grenzen (ehrlich)

- **Ohne Person wird nichts gespeichert.** Der Rahmen ist im Editor sichtbar, bleibt über das erneute
  Öffnen desselben Bildes erhalten und ist lokal gemerkt — er wandert aber **nicht** in den
  Datenbestand. Die Zuordnung kommt mit **Schritt G** (Ziel-Personen-Menü je Rahmen).
- Der lokale Speicher ist der **Browserspeicher des Geräts**. Wird er geleert (oder der Browser
  gewechselt), ist ein noch nicht zugeordneter Rahmen weg. Das ist bewusst so: der Server hat keinen
  Platz für einen Rahmen ohne Person, und der Server-Fortschritt vergisst nach 500 Bildern (Pfad 2).
- **Zeichnen nur ohne Anzeige-Drehung.** Bei gedrehter Anzeige kommt ein Hinweis; die Umrechnung eines
  gezeichneten Rechtecks durch die Drehung ist nicht gebaut.
- Die **Wirkung am Handy** ist damit nicht abgenommen — das bleibt Sebastians Abnahme am Gerät.
