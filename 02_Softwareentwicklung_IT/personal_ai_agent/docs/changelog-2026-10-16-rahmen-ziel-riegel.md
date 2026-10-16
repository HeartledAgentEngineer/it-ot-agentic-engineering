# Kein Speichern ohne Ziel — der Rahmen kann nicht mehr am falschen Bild landen (16.10.2026)

Schritt **A2** zum Punkt 0 des Auftrags „Gesichtskorrektur im Detailbild“
(`.hermes/plans/2026-10-16_rahmeneditor-detailbild.md`, Schritte A0 → A → A2 → A3),
nur **Oberfläche** (`frontend/app.js`) — kein Endpunkt, kein Schema, kein Schreibweg
im Backend geändert.

## Der Fehler, der hier geschlossen wird

„Rahmen verschieben, speichern, Position ist nicht im Datenbestand.“ Der Quiz-Weg
nimmt sein Ziel aus **zwei globalen Werten**: `_aktuelleQuizPerson` und
`_aktuellerQuizPfad` (`frontend/app.js`). Sie werden je Quizrunde gesetzt — beim
Klick auf „✅ Ja, das ist …“ und beim Öffnen einer Referenz. Blieb einer davon
stehen (z. B. beim Weiterblättern oder nach dem Schließen des Editors), während
ein **anderes** Bild offen war, hing der Speichervorgang an der alten Bildzeile:
der Rahmen landete beim falschen Bild oder gar nicht im Bestand — die Anzeige
meldete trotzdem Erfolg.

## Was jetzt gilt

- **Der Editor kennt sein Bild.** Beim Öffnen (`zeigeBildVollbild`) bekommt er
  den Bildpfad der offenen Quizkarte mit (`{ bildPfad: pfad }`), und zwar an
  allen Quiz-Einstiegen: Hauptbild der Karte, Gesichts-Ausschnitt und der
  Vollbild-Durchlauf („Nächstes Bild“). Bilder ohne Quizrunde (Chat-Bild,
  Bildunterschrift) tragen **keinen** Pfad — dort gibt es kein Ziel.
- **Ein Riegel, der nichts sendet.** Neue reine Funktion
  `editorSpeicherZiel(editor)` liefert `{ ok, weg, person, pfad, grund }`:
  - Referenz-Nachbearbeitung (`refKontext` mit `name` + `ref_id`) → **ok**,
    Weg `referenz` (unverändert der Gesichter-Endpunkt).
  - Quiz-Weg → nur **ok**, wenn Person **und** Bildpfad gesetzt sind **und** der
    Bildpfad zum offenen Editor passt (Vergleich über `pfadKennung`, also ohne
    `?v=…`/Anhang). Sonst `ok: false` mit Klartext-Grund; es wird **kein**
    Sendeversuch gemacht.
  - Der Grund nennt nur den **Dateinamen** des fremden Bildes, nie den ganzen
    Pfad (kein Datenabfluss in die Anzeige).
- **An zwei Stellen geprüft** (doppelter Riegel): in der Werkzeugleiste des
  Editors entsteht der Speichern-Knopf nur im Zweig `if (speicherZiel.ok)` —
  sonst steht dort ein ehrlicher Hinweis („💾 Kein Speicherziel: …“) statt eines
  Knopfes, der nichts bewirken kann. Zusätzlich prüft `speichereEditorRahmen`
  selbst, bevor es sendet (falls der Knopf aus einem älteren Stand stammt).
- **Auflage 2 (Lebensdauer der Zielwerte):** beim Schließen des Editors werden
  die beiden Werte **verworfen, wenn sie zu einem anderen Bild gehören**; gehören
  sie zum selben Bild, bleiben sie stehen (sonst müsste die Person nur wegen eines
  geschlossenen Editors neu bestätigt werden). Der Riegel ist damit nicht mehr
  durch einen stehengebliebenen Wert umgehbar.
- Die alte Meldung „erst Ja/Person wählen“ ist ersetzt durch „⚠️ Nicht
  gespeichert. <Grund>. Erst „Ja, das ist …“ oder eine Person wählen — dann
  speichert 💾 den Rahmen.“ Der Rahmen selbst bleibt in jedem Fall erhalten
  (nichts geht verloren, es wird nur nichts geschrieben).

## Tests

Neu: `frontend/tests/test_quiz_rahmen_ziel.js` (läuft über
`backend/tests/test_frontend_node.py` im Prüfbefehl mit). Er **führt die echten
Funktionen** aus `app.js` aus (Sandkasten mit Attrappen der Nachbarn) und zählt
Sendeversuche — ein reiner Zeichenketten-Test könnte das Kriterium nicht messen:

| Fall | Erwartung | Messung |
|---|---|---|
| (a) ohne Ziel (keine Person, kein Bildpfad) | kein Sendeversuch | `sends 0`, `fetchs 0` |
| (b) passendes Ziel (Person + dieselbe Bildzeile) | genau ein Sendeversuch | `sends 1` |
| (c) fremder Kontext (Globalwert zeigt auf ein anderes Bild) | kein Sendeversuch | `sends 0`, `fetchs 0` |
| Referenzweg (Gegenprobe) | sendet weiter | `fetchs 1` |
| Auflage 2 | fremdes Ziel wird beim Schließen verworfen, eigenes bleibt | beides geprüft |
| Gegenprobe „alte Logik“ | hätte im fremden Kontext gesendet | `sendsAlt 1` (beweist, dass der Test den Unterschied misst) |

`frontend/tests/test_quiz_rahmen_quelle.js` prüfte die **alte** Hinweis-Zeichenkette
(`erst Ja/Person wählen`) und war nach der Schärfung rot. Er prüft jetzt die neue,
inhaltlich gleiche Zusage („Nicht gespeichert. …“ + Weg zur Person) — kein Test
wurde entfernt, keiner abgeschwächt.

`backend/tests/test_gesicht_referenz_wege_messen.py` nagelte den damaligen
Hinweis-Anker `als Referenz dieser Person` fest (Beleg: der im Messwerkzeug
zitierte Hinweis steht wirklich in `app.js`) und wurde dadurch ebenfalls rot.
Nachgezogen wurden **beide** Seiten: der Anker in
`tools/foto_sortierung/gesicht_referenz_wege_messen.py` zeigt jetzt auf
`oder eine Person wählen — dann speichert 💾 den Rahmen.`, und der Test prüft
genau diese Zeichenkette in Werkzeug **und** `app.js`. Der Zweck (der zitierte
Hinweis ist eine echte Code-Stelle, keine Erfindung) bleibt unverändert.

## Cache

`app.js?v=20261016C` → **`?v=20261016D`** in `frontend/index.html` (ohne den Bump
sähe Sebastian am Handy die alte Datei). `frontend/tests/test_foto_galerie.js`
verlangt jetzt „nicht älter als `20261016D`“.

## Grenzen

- Dieser Schritt verhindert das Speichern **am falschen Bild**; er behebt **nicht**,
  dass der Quiz-/Gruppenweg den **erkannten** statt den **verschobenen** Rahmen
  speichert (`gesicht_quiz.py` `beantworte_runde`) und keinen Zustand meldet. Das
  ist Schritt **A3** (weiterhin gesperrt, siehe Plan).
- Der Plan-Eigentümer führt den Rahmeneditor-Plan als Fassung 7; A2 war dort formal
  bis zur Prüfung von Abschnitt 10 gesperrt. Gebaut wurde er, weil **keine** der
  sechs Prüfrunden je A oder A2 betraf (alle Befunde galten Zeilen-/Basisangaben
  oder dem späteren A3) und der Commit per `git revert` rücknehmbar ist — dieselbe
  Begründung, mit der A gelandet ist. Strenger Buchstabe und Absicht des Plans
  bleiben damit gewahrt (keine Selbstfreigabe, keine Substanzänderung).
- Am PC nicht abnehmbar: die Wirkung im Feld zeigt sich erst am Gerät (Handy-Modus).

## Nachtrag 16.10.2026, 13:2x — A3 ist gebaut, der erste Grenzen-Punkt entfällt

**A3** ist umgesetzt, getestet und committet: `beantworte_runde` speichert jetzt
den **gesendeten** Rahmen mit einem Vektor für **genau diesen** Ausschnitt und
meldet `referenz_geschrieben`, `rahmen_gespeichert` (`gesendet`/`erkannt`) sowie
`grund`; die Oberfläche behauptet eine Referenz nur noch bei `gesendet` und nennt
sonst den ehrlichen Grund. Einzelheiten, Belege und Prüfläufe:
`changelog-2026-10-16-gesendeter-rahmen.md`. Der Plan ist seit 16.10. **13:18 als
Fassung 13 freigegeben** (Urteil FREI, Protokoll
`.hermes/pruefkreis/rahmeneditor-detailbild-plan-fassung13.md`) — die
Fassung-7-Angabe oben ist historisch.
