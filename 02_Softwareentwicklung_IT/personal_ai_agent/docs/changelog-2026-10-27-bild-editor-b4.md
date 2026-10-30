# Bild-Editor B4 (Frontend): Editor Cloud-Weg + Einstieg Gruppen-Quiz — 27.10.2026

Planschritt B4 von „Bild-Editor überall" (nach B1 und B2, beide nur Backend). Der Editor
(`zeigeBildVollbild` in `frontend/app.js`) arbeitet jetzt auch für ein Bild, das nur über seine
pCloud-Kennung (`fileid`) bekannt ist. Das Gruppen-Quiz öffnet ihn so für Foto- und Gesamtansicht.

## Was gebaut ist

### Cloud-Weg im Editor (`frontend/app.js`)

Aktiv, sobald `zeigeBildVollbild(img, gesichter, {fileid, markiere})` eine gültige `fileid` (nur
Ziffern, höchstens 20) bekommt. Ohne `fileid` bleibt alles wie vorher (Quiz-Weg, Referenz-Weg,
Chat-Bilder als reine Ansicht); die `fileid` wird bei jedem Öffnen zurückgesetzt. Die Referenz-
Nachbearbeitung (`refKontext`) geht der `fileid` vor.

- **Speicherziel:** `editorSpeicherZiel` liefert mit `fileid` `{ok:true, weg:'cloud', fileid}`,
  bei ungültiger Kennung `{ok:false, weg:'cloud', grund}`. 💾 erscheint nur mit gültigem Ziel;
  ohne `fileid` gibt es keine Cloud-Bedienelemente. Im Cloud-Weg gibt es keinen „alle speichern"-
  Knopf (ein 💾 schickt alles) und kein „Nächstes Bild" des Handy-Quiz.
- **Zustand:** `bildEditorCloudZustand` baut aus den Gesichtern von `bild-gesichter` je Rahmen
  `bbox_norm_live`, `personen`, `gids` (Kennung des Servers, `''` = neues Gesicht) und `basis`
  (`{bbox_norm, name}` wie geladen; `null` = neu). Das Gruppengesicht (`markiere`: erst `gid`, sonst
  beste Deckung ab 0,5) ist beim Öffnen ausgewählt.
- **💾 Speichern** (`speichereBildCloud`): ein einziger Aufruf `POST /api/gruppen/bild-rahmen`
  mit `{fileid, aenderungen}`. Aus dem Unterschied zur Basis entsteht
  (`bildEditorCloudAenderungen`): verschoben → `{gid, bbox_norm}`, gelöscht → `{gid, entfernen:true}`,
  neuer Name → `{gid, name}`, neuer Rahmen → `{neu:true, bbox_norm, name?}`. Unveränderte Gesichter
  werden nicht geschickt; ein gleichbleibender Name schickt nichts. Rahmen werden für den Server
  auf gültige Werte gebracht (`cloudBboxFuerServer`: im Bild, mindestens 1 %, 6 Stellen). Mehr als
  30 Änderungen: klare Meldung (mit ↩ zurücknehmen), nichts wird gesendet. Ohne Änderung: Meldung,
  kein Aufruf. Ein zweiter Tipp während des Speicherns wird abgewiesen.
- **Meldung aus der Antwort** (`bildEditorCloudMeldung`): Erfolg mit Anzahl, „Server hatte schon
  genau diesen Stand" (`geschrieben:false`), Teilfehler mit Klartext (`teilweise`, `fehler`),
  `ok:false` mit `fehler`; fehlende/unlesbare Antwort und Netzfehler lassen die Eingaben im Editor.
  Nach (teilweisem) Schreiben lädt der Editor die Gesichter über `GET /api/gruppen/bild-gesichter`
  neu (Rückfall: die `gesichter` der Antwort), übernimmt die neuen `gid`s und baut die Rahmen
  neu auf.
- **🔍 Neu erkennen:** im Cloud-Weg ruft der Knopf `POST /api/gruppen/bild-erkennen` (nicht die
  Quiz-Analyse; die bleibt im Quiz-Weg). Die `neu`-Funde erscheinen **gestrichelt** als Vorschlag
  (mit „Vorschlag: <Name>?" aus den Namensvorschlägen); bekannte oder bereits gedeckte Funde
  werden nicht doppelt gezeigt. Bis zum Antippen ändert sich nichts; ein Tipp übernimmt den
  Vorschlag als neuen Rahmen (ohne Person, mit Undo-Schritt). Fehler der Route (HTTP-Status,
  `fehler`) werden als Text gezeigt; die vorhandenen Rahmen bleiben unverändert.
- **Personenmenü:** im Cloud-Weg zeigt es die Namen aus dem Vorschlag des Rahmens, vom Bild und
  aus `GET /api/gruppen/personen` (5 Minuten zwischengespeichert), dazu „➕ Neue Person … (nur am
  Handy)". Die Auswahl öffnet ein Namensfeld mit OK (in der umbrechenden Werkzeugleiste, Breiten
  in `vw`); ein unbekannter Name trägt den Hinweis „wird nur am Handy gespeichert, nicht für die
  Gruppierung am PC". Der Name wird mit 💾 gespeichert.
- **Sicherheit der Anzeige:** Namen, Meldungen und Hinweise gehen nur per `textContent` in die
  Oberfläche, der neue Code benutzt kein `innerHTML`.

Die neuen testbaren Funktionen stehen als eigener Block `// ── Bild-Editor B4` … `// ── Ende
Bild-Editor B4` direkt vor dem „Schritt E"-Block: `cloudFileidGueltig`, `cloudBboxFuerServer`,
`cloudStartAuswahl`, `bildEditorCloudZustand`, `bildEditorCloudAenderungen`,
`bildEditorCloudMeldung`, `cloudGesichterLaden`, `speichereBildCloud`, `cloudErkennenAbrufen`,
`bildEditorCloudErkennung`, `bildEditorCloudVorschlagUebernehmen`, `cloudVorschlagElement`,
`ladeCloudPersonenNamen`, `cloudPersonenNamen`, `cloudNeuePersonOptionText`, `cloudNameHinweis`.
`editorSpeicherZiel` prüft die Kennung bewusst inline, damit die bestehenden Tests ihn ohne weitere
Funktionen ausführen können.

### Einstieg im Gruppen-Quiz (`frontend/gruppen_quiz.js`)

`vollbildOeffnen(fileid, gesicht, beispiel)` wird aus der Fotoansicht (Kachel) und der
Gesamtansicht („Alle Gesichter") mit dem Gesicht aufgerufen. Bei einem Foto mit rein numerischer
Kennung (`gesichtBearbeitbar`) holt es nach geladenem Bild `GET /api/gruppen/bild-gesichter?fileid=`
und öffnet den Editor mit `{fileid, markiere:{gid, bbox_norm}}` und allen Gesichtern des Bildes;
das Gruppengesicht bleibt markiert. Video-Standbilder (`video: true`) und nicht-numerische Kennungen
bleiben reine Ansicht ohne Abruf; ist `bild-gesichter` nicht ladbar, erscheint eine Meldung
(„… — nur Ansicht.") und das Bild öffnet wie bisher mit dem einen Gruppengesicht.

### Cache-Schlüssel

`frontend/index.html`: `app.js?v=20261027A`, `gruppen_quiz.js?v=20261027A`. Zwei bestehende Tests,
die den alten `app.js`-Schlüssel festhielten, vergleichen jetzt nur noch die Version
(`frontend/tests/test_server_zustand.js`, `backend/tests/test_tageslauf_status.py`).

## Prüfung

- Neu `frontend/tests/test_bild_editor_b4.js`: **129 Prüfungen** in 16 Fällen (K1, K2, K3, K3b,
  K3c, K3d, K4, K4b, K4c, K5, K5b, K6, K7, K8, K9, K10), offline, erfundene Kennungen und Namen.
  Aufruf: `node tests/test_bild_editor_b4.js app.js` (im Ordner `frontend`). Zuerst rot
  (40 von 54 Prüfungen der ersten Fassung), dann grün.
- `backend/tests/test_frontend_node.py` nimmt die Datei selbst auf (`test_*.js`), kein Listeneintrag nötig.
- `frontend/tests/test_quiz_suche_vollstaendig.js`: der Wächter „kein zusätzliches ➕ Neue Person“ zählt jetzt
  **3** Stellen (2 Knöpfe der Quiz-Karte + 1 Menüpunkt des Cloud-Editors, `'➕ Neue Person … (nur am Handy)'`)
  statt 2 — offen angepasst, der Text steht als Literal im Code.
- Versionsprüfungen in `frontend/tests/test_server_zustand.js` und `backend/tests/test_tageslauf_status.py`
  (`test_cache_schluessel_mindestens_20261026a`) prüfen jetzt „mindestens“ statt einer festen Nummer.
- Zusätzlich lief die echte `zeigeBildVollbild` einmal mit einer Attrappen-Oberfläche durch
  (Öffnen mit `fileid`, 💾 mit einer Verschiebung, Neuladen, 🔍 Neu erkennen, Vorschlag antippen).

## Bewusst nicht gebaut

- Eine Rückfrage „War: A → jetzt: B?" bei Namensänderungen: der Name wird direkt als Änderung gesammelt.
- Eine eigene Personenanlage im Editor: er sendet den Namen nur als `name` an `bild-rahmen`; der
  Hinweis „nur am Handy" im Menü benennt, dass ein unbekannter Name nicht in die Gruppierung am PC
  eingeht.
