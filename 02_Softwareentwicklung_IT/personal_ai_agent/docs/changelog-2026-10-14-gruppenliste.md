# Gruppenübersicht (15.10.2026)

Unter „Personen benennen“ gibt es eine paginierte Gruppenübersicht mit den
Statusfiltern Offen, Später, Benannt und Ausgeblendet. Eine Zeile zeigt die
vorhandene Gesichtsanzahl, den gespeicherten Zeitraum und – wenn bestätigt –
den vorhandenen Namen. Die Liste liest diese Metadaten aus
`personen_beispiele.json`; sie wertet dafür keine Gesichtsdaten neu aus.

Ein Eintrag öffnet die gewählte Gruppe direkt mit derselben Beispiel-,
Video-Standbild-, Zwillings- und Verbundenen-Aufbereitung wie das Quiz. Das
Öffnen ändert keinen Status. „Zur Übersicht“ lädt die zuletzt gewählte
Kategorie und Seite erneut. Die Liste kann sich bei Statusänderungen auf
anderen Geräten verschieben; die Oberfläche weist darauf hin und bietet eine
Aktualisierung.

In Später und Ausgeblendet kann eine Gruppe ausdrücklich über „Zurück zu
Offen“ reaktiviert werden. Die bestehende Antwort- und Rückgängig-Protokollierung
speichert die vorherigen Statusmarkierungen. Benannte Gruppen können nicht so
reaktiviert werden. Namen, Gleich-/Verschieden-Vorgaben, Profile, Gesichter und
Gruppierung bleiben von dieser Aktion unberührt.

Die Übersicht fügt `GET /api/gruppen/liste` und `GET
/api/gruppen/detail/{kennung}` hinzu. Listenparameter sind `status`, `seite`
(1–10000) und `je_seite` (1–100, Standard 24); ungültige HTTP-Parameter
antwortet FastAPI mit 422. Ein fehlender Gruppeneintrag liefert wie die
übrigen Gruppenwege `ok: false` mit deutschem Hinweis. Die bestehenden
Benannt-Personenansicht und `/api/gruppen/naechste` bleiben erhalten.

Es findet keine neue Gruppierung, Zusammenführung, Identitätsannahme oder
Cloud-Abnahme statt. Die Funktion wurde ausschließlich mit erfundenen
`tmp_path`-Daten und einer kontrollierten JavaScript-Laufzeit geprüft; eine
Abnahme mit Originaldaten oder am Handy ist damit nicht belegt.

## Ergebnisprüfung Runde 1 – Behebungen

Die erste Ergebnisprüfung fand vier Befunde. Jeder ist mit einem Test belegt,
der vor der Behebung rot war.

1. **Verspätete Quiz-Antwort (hoch).** `laden()` in `frontend/gruppen_quiz.js`
   übernahm eine spät eintreffende `/api/gruppen/naechste`-Antwort ohne Prüfung
   des Ansichtsstands; nach dem Öffnen eines Details konnte so wieder die alte
   Quizgruppe erscheinen und ein folgendes „Später“ die falsche Gruppe treffen.
   Jetzt hat `laden()` eine eigene Sequenznummer (`zustand.quizSequenz`) und
   prüft zusätzlich den Ansichtsstand (siehe Runde 3: `ansichtSequenz`, die jeder
   Ansichtswechsel erhöht). Außerdem wird eine Antwort verworfen, solange
   Detail oder Übersicht aktiv sind. Eine verworfene Antwort ändert weder die
   Oberfläche noch `zustand.gruppe`.
2. **„Alle Gesichter → Zurück“ (mittel).** Bei einer gezielt geöffneten Gruppe
   (`zustand.detailAktiv`) lädt `alleSchliessen()` dieselbe Gruppe frisch über
   `/api/gruppen/detail/{kennung}` (statt `laden()`); „Zur Übersicht“ bleibt
   sichtbar und eine schon erfolgte Statusaktion bleibt vermerkt
   (`gruppeDetailLaden(kennung, true)`). Ohne Detailkontext bleibt es bei
   `laden()`.
3. **Rückkehr nach Statusaktion (mittel).** Der Knopf „← Zur Übersicht“
   (`#gruppen-detail-zurueck`) steht in `frontend/index.html` jetzt vor der Karte
   statt in ihr, damit er auch bei der Backend-Antwort `fertig` (Karte
   ausgeblendet) erreichbar bleibt; die Sichtbarkeit steuern `nurZeigen` und
   `zeigen`. Der allgemeine Knopf „Gruppenübersicht“ lädt nach einer eigenen
   Statusaktion (benennen, später, unbekannt, offen, gleich und Rückgängig dazu)
   die zuletzt genutzte Kategorie ab Seite 1 – wie „Zur Übersicht“ –, sodass keine
   leere Folgeseite erscheint.
4. **Reihenfolge nach Rückgängig (mittel).** `antworten()` in
   `backend/app/services/gruppen_quiz.py` speichert zusätzlich zu `listen_vorher`
   die Position in der jeweiligen Liste (`listen_position`, nur wenn die Gruppe in
   der Liste stand). `rueckgaengig()` fügt sie an dieser Position wieder ein
   (höchstens ans Listenende). Protokolleinträge ohne `listen_position`
   (ältere Läufe) verhalten sich unverändert: Die Gruppe wird ans Listenende
   gehängt. Das gilt für alle Antwortarten, die eine Liste berühren, nicht nur
   für „offen“.

Tests: `backend/tests/test_gruppen_liste.py`
(`test_undo_nach_offen_stellt_reihenfolge_der_liste_wieder_her[spaeter|unbekannt]`,
`test_undo_nach_offen_stellt_beide_listen_in_ihrer_reihenfolge_wieder_her`,
`test_undo_alteintrag_ohne_position_haengt_wie_bisher_ans_ende`) und
`frontend/tests/test_gruppen_liste.js`
(`lateQuizAnswerDoesNotOverwriteDetail`,
`lateQuizAnswerAfterFilterChangeAndCloseIsIgnored`,
`allFacesBackReturnsToTargetedGroup`,
`returnToOverviewAfterStatusActionEvenWhenFertig`). Der JavaScript-Test führt nun
alle Prüfungen aus und meldet jede Verletzung einzeln. Cache-Schlüssel und
`style.css` blieben während der Prüfrunden unverändert (`gruppen_quiz.js?v=20261015A`
lautete der Stand der Prüfvorlage; bei der Übernahme in `main` wurde der Schlüssel
auf `20261016A` erhöht, siehe Abschnitt „Übernahme in `main`“). Weiterhin gilt:
keine Abnahme mit Originaldaten oder am Handy.

## Ergebnisprüfung Runde 2 – Behebungen

Die zweite Prüfung bestätigte die vier Behebungen aus Runde 1 und fand zwei
weitere Befunde.

1. **Verspätete Speicher-/Rückgängig-Antwort (hoch).** `antworten()` und
   `rueckgaengig()` in `frontend/gruppen_quiz.js` übernahmen die Antwort in den
   *aktuellen* Detailkontext: Wer Gruppe A speicherte und währenddessen zur
   Übersicht wechselte und B öffnete, sah danach die Folgegruppe von A statt B,
   und ein weiteres „Später“ hätte die falsche Gruppe getroffen. Beide halten jetzt
   beim Absenden den Ansichtsstand fest (`ansichtMerken()`: Ansichts-, Detail- und
   Listensequenz) und prüfen ihn bei der Antwort (`ansichtVeraltet()`). Ist er
   veraltet, ändert die Antwort weder Karte noch `zustand.gruppe` noch das
   Meldungsfeld; die serverseitig gespeicherte Aktion bleibt gültig. Der
   Fortschritt wird weiter aktualisiert, `zustand.beschaeftigt` wird wie bisher
   im `finally` zurückgesetzt und eine veraltete Statusaktion merkt
   `listeStatusGeaendert` vor, damit die nächste Rückkehr zur Übersicht die
   Kategorie frisch ab Seite 1 lädt. Fehlermeldungen einer veralteten Anfrage
   werden nicht in die neue Ansicht geschrieben.
2. **Detail-Ladestatus unsichtbar (mittel).** `gruppeDetailLaden()` schrieb
   „… lädt Gruppe“ in die Meldung der Listenansicht, die beim Detailaufruf
   verborgen ist. Jetzt steht der Ladestatus im immer sichtbaren Meldungsfeld
   `#gruppen-meldung` und wird nach Erfolg oder Fehler geleert; ein Fehler
   erscheint weiterhin sichtbar in der Listenansicht, in die zurückgekehrt wird.
   „← Zur Übersicht“ leert das Meldungsfeld ebenfalls.

Tests in `frontend/tests/test_gruppen_liste.js`:
`lateSaveAnswerDoesNotReplaceOtherDetail`,
`lateUndoAnswerDoesNotReplaceOtherDetail` (jeweils A öffnen, Aktion absenden,
Übersicht, B öffnen, Antwort eintreffen lassen: B bleibt, "Später" trifft B) und
`detailLoadingIsVisibleAndErrorToo`.

## Ergebnisprüfung Runde 3 – Behebungen

Die dritte Prüfung fand zwei weitere Fälle derselben Klasse (verspätete Antwort
verändert eine inzwischen andere Ansicht). Statt Einzelfällen wurde diesmal
jede `await`-Stelle in `frontend/gruppen_quiz.js` durchgegangen und ein
gemeinsamer Mechanismus überall angewendet, wo nach dem Warten Anzeige oder
Zustand geändert wird.

**Gemeinsamer Mechanismus.** `zustand.ansichtSequenz` zählt jeden Ansichtswechsel:
`nurZeigen` (Detail, Übersicht, Person, Benannt, Alle Gesichter, Reiter/Quiz),
`schliessen`, `alleSchliessen` und den Neuaufbau der Gesichterliste
(`alleVonVorn`, z. B. Sortierwechsel). Eine Anfrage hält ihren Stand beim Absenden
mit `ansichtMerken()` fest (Ansichts-, Detail- und Listensequenz) und fragt nach dem
Warten `ansichtVeraltet()` ab. Ist der Stand veraltet, ändert die Antwort weder
Oberfläche noch Auswahl noch Meldungsfeld; eine serverseitig ausgeführte Aktion
bleibt gültig (nur die Anzeige wird verworfen), `zustand.beschaeftigt` wird in
jedem Fall im `finally` zurückgesetzt, und Fehlermeldungen einer veralteten
Anfrage werden nicht in die neue Ansicht geschrieben. Gleichartige Anfragen
(`personenLaden`, `personOeffnen`, `laden`) tragen zusätzlich eine eigene Nummer,
damit nur die neueste gilt.

1. **Verspätete Personenantwort (mittel).** `personOeffnen()` führte nach dem
   Warten ungeprüft `nurZeigen('person')` aus und versteckte eine inzwischen
   geöffnete Gruppe B. Jetzt verwirft sie eine veraltete Antwort (Rückgabe
   `null`; `true` = gezeigt, `false` = Fehlschlag mit Rückkehr zur Liste). Die
   Aufrufer (Lösen, Rückgängig) zeigen ihre Erfolgsmeldung nur, wenn die Person
   wirklich gezeigt wurde; bei veralteter Antwort wird nur die Personenliste
   aufgefrischt.
2. **Ausschließen und Zuordnen (mittel).** `alleAusschliessen()` und `alleZuordnen()`
   entfernten nach der Antwort die *aktuell* markierten Kacheln und leerten die
   aktuelle Auswahl – auch wenn dort inzwischen die Gesichter einer anderen
   Gruppe standen. Jetzt gilt: veraltete Antwort = keine Änderung an Raster,
   Auswahl, Info oder Meldung. Auch in unveränderter Ansicht entfernt
   `alleMarkierteEntfernen(gids)` nur die abgeschickten Gesichter; währenddessen
   neu Markiertes bleibt markiert.
3. **Weitere Stellen aus der Durchsicht** (gleicher Mechanismus): Gesichterliste
   nachladen (`alleSeiteLaden`: der Besitz des `laedt`-Flags geht beim Neuaufbau
   nicht mehr verloren, keine doppelte Seite nach Schließen und Wiederöffnen),
   Foto-Vollbild (kein verspätetes Einblenden, Objekt-URL wird freigegeben),
   Umbenennen, Profil speichern, Kontakt suchen und verknüpfen, Rückgängig in
   der Personenansicht, Diktat-Meldung im Quiz und Profilhinweis beim Namenfeld.

Tests in `frontend/tests/test_gruppen_liste.js`:
`latePersonAnswerDoesNotHideGroupDetail`,
`lateExcludeAnswerDoesNotTouchOtherFaceList`,
`lateAssignAnswerDoesNotTouchOtherFaceList` und
`markingsAddedDuringExcludeSurvive`. Der Test bricht jetzt auch mit Fehler ab,
wenn eine Prüfung nie endet (hängendes Promise), statt still „grün“ zu enden;
die DOM-Attrappe kennt `lastChild`. Für die in Punkt 3 genannten Stellen gibt es
keine eigenen Laufzeittests.

## Übernahme in `main` (16.10.2026)

Die unabhängige Ergebnisprüfung hatte das Ergebnis mit **FREI** freigegeben
(`.hermes/plans/t2-ergebnisreview-2026-10-15-antwort.md`, Sitzung
`20261015_124512_a4c108`). Der geprüfte Stand lag als unfertige Arbeit in einem
isolierten Arbeitsbaum auf Basis `ce23417`. Übernommen wurde er als
Drei-Wege-Zusammenführung auf den damaligen `main`-Stand (`e8b1020`); geändert
wurden genau die neun T2-Dateien.

- **Überschneidung geprüft, beide Seiten erhalten.** Zwischen Basis und Übernahme
  lag genau ein Commit mit denselben Dateien: `f932d10` („Anzeige nennt den Grund
  für nicht gezeigte Video-Gesichter“). Die Zusammenführung hat die
  T2-Änderungen **und** diesen neueren Stand behalten — `frontend/gruppen_quiz.js`
  (Zeile 182), der Docstring in `backend/app/services/gruppen_quiz.py` und die
  Prüfzeile in `frontend/tests/test_gruppen_quiz.js` tragen weiterhin
  „noch ohne Standbild“. Kein fremder Pfad wurde geändert.
- **Cache-Schlüssel erhöht.** `f932d10` hatte `gruppen_quiz.js?v=20261015A`
  bereits nach `main` gepusht; die T2-Fassung trug denselben Schlüssel für
  anderen Inhalt. Ein bereits im Umlauf befindlicher Schlüssel darf nicht
  unverändert bleiben, sonst behält ein Browser die alte Datei. `frontend/index.html`
  steht deshalb auf `20261016A`; die Prüfung `vQ[1] >= '20261015A'` bleibt gültig —
  sie prüft auf „mindestens“, nicht auf Gleichheit.
- **Befund 1 der Ergebnisprüfung war zunächst verschoben, am 16.10.2026 nachgetragen.**
  Für `.gruppen-liste-filter`, `.gruppen-liste-ansicht`, `.gruppen-liste-seiten` und
  `.gruppen-uebersicht-knopf` fehlten Regeln in `style.css`; die Wirkung ist rein
  optisch, und der Plan stellte die Regeln optional. Der kleinste Korrekturweg stand
  hier: den `.gruppen-reiter`-Selektor um `.gruppen-liste-filter` erweitern und
  `style.css` im selben Schritt mit einem neuen Cache-Schlüssel versehen. Genau das
  ist umgesetzt — Einzelheiten im Abschnitt „Befund 1 nachgetragen“ am Ende.
- **Befund 2 angenommen.** Der Schlüssel `20261015A` statt der Planformulierung
  `20261014B` ist durch `20261016A` überholt.
- **Nachweis.** Voller Prüfbefehl im Arbeitsbaum selbst ausgeführt:
  `backend/.venv/Scripts/python -m pytest tests/ -q` ergibt **4666 passed,
  3 skipped, Exit 0** (648 s; Protokolldatei außerhalb des Repos). Keine Abnahme
  mit Originaldaten, keine Abnahme am Handy.

## Befund 1 nachgetragen (16.10.2026)

Die fehlenden Regeln sind ergänzt — codegenau steht jetzt in `frontend/style.css`:

- `.gruppen-reiter, .gruppen-liste-filter { … }` — **ein** gemeinsamer Selektor statt
  einer zweiten Kopie (die Statusfilter der Liste sind dieselben Knöpfe
  `.gruppen-reiter-knopf`, nur in einem anderen Behälter).
- `.gruppen-liste-ansicht[hidden] { display: none; }` — **notwendig, nicht kosmetisch:**
  die Ansicht wird in `gruppen_quiz.js` über das `hidden`-Attribut ein- und ausgeblendet;
  ein `display: flex` ohne diese Zeile hätte `hidden` ausgehebelt und die Liste dauerhaft
  sichtbar gemacht.
- `.gruppen-liste-ansicht { display: flex; flex-direction: column; gap: 10px; }` —
  dieselbe Spaltenform wie `.gruppen-benannt-ansicht`, weil die Ansicht Geschwister
  der Quiz-Karte ist.
- `.gruppen-uebersicht-knopf { width: 100%; margin-top: 2px; }` und
  `.gruppen-liste-seiten { display: flex; gap: 8px; }` samt
  `.gruppen-liste-seiten .gruppen-knopf { flex: 1 1 45%; min-width: 0; }` —
  „Vorherige"/„Weitere" stehen nebeneinander wie in `.gruppen-alle-leiste`.

**Cache-Schlüssel:** `frontend/index.html` lädt `style.css?v=20261016A` (vorher
`20261014B`). Der genaue Schlüssel ist in `frontend/tests/test_foto_galerie.js`
mitgezogen (`vCss === '20261016A'`), die übrigen Prüfungen bleiben „mindestens“-Vergleiche.

**Regressionstest:** `frontend/tests/test_gruppen_liste.js` prüft die sechs Regeln und
den Cache-Schlüssel (`ansichtIstGestyltUndBleibtVersteckbar`). Gegenprobe ausgeführt:
mit entferntem Regelblock werden die Prüfungen rot — der Test greift also wirklich.

**Ehrliche Grenze:** geprüft ist der Quelltext. Ob die Liste am Handy gut *aussieht*,
sagt erst ein Blick auf dem Gerät; die Wirkung ist rein optisch, Verhalten ändert sich
nicht (der `[hidden]`-Riegel hält das Ausblenden sogar ausdrücklich fest).
