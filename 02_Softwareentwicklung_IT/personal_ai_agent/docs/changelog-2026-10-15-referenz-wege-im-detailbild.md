# Referenz-Wege im Detailbild — belegt statt vermutet (15.10.2026)

**Anlass.** Der Auftrag `.hermes/plans/2026-10-15_gesichter-im-detailbild.md` (Sebastian,
15.10.2026) verlangt vor dem Bau zwei Klärungen „belegt, nicht vermutet". Der vorige Messlauf
hatte Abschnitt 1 (Erkennungseinstellungen, Kästchenzahl) abgearbeitet. Offen waren zwei
Punkte, die am PC kostenfrei messbar sind:

* **Abschnitt 3:** „Ein Abschnitt im Plan beantwortet, ob das Handy Gesichtsvektoren selbst
  rechnen kann — mit Beleg (Datei:Zeile oder Messung)."
* **Abschnitt 4.1:** der behauptete Widerspruch zwischen dem Hinweistext der App
  („als Referenz dieser Person") und dem Befund, Benennen erzeuge keinen Referenzvektor.

**Neues Werkzeug** `tools/foto_sortierung/gesicht_referenz_wege_messen.py` — nur lesen: Code
als Text, lokale Zählung in den Benennungs-Dateien; kein Bild, kein Netz, kein Modell, kein
Schreibzugriff, keine Personennamen im Bericht.

## 1. Kann das Handy Gesichtsvektoren selbst rechnen? — JA, belegt

Die Einbettung läuft auf dem Gerät, in einer proot-Debian-Distro als Subprozess:

| Was | Stelle |
|---|---|
| Inferenz-Skript auf dem Gerät | `backend/app/services/face_service.py:31` |
| Subprozess-Aufruf | `backend/app/services/face_service.py:32` |
| Bereitschaftsprüfung (`ping`) | `backend/app/services/face_service.py:72` |
| Einbettung eines Ausschnitts (`bbox`) | `backend/app/services/face_service.py:137` |
| Einbettung eines ganzen Bildes | `backend/app/services/face_service.py:116` |
| Aufruf der Ausschnitts-Einbettung (`embed_crop`) | `backend/app/services/face_service.py:149` |
| Einbettungs-Einstieg im Inferenz-Skript | `backend/face_infer.py:245` (`op_embed`) |
| Ausschnitts-Einstieg im Inferenz-Skript | `backend/face_infer.py:304` (`op_embed_crop`) |
| Verteiler der Operationen | `backend/face_infer.py:348` |

Der Vektorrechner ist damit am Handy **nicht nur vorhanden, sondern aufrufbar** — die Frage aus
Abschnitt 3 des Auftrags ist beantwortet.

## 2. Erzeugt „Benennen/Speichern im Detailbild" eine Referenz? — JA, über den Gesichter-Weg

Der Editor speichert den Rahmen über den **Gesichter-Weg**, und der bettet den Ausschnitt ein:

* Hinweistext der App: `frontend/app.js:4106` („den Rahmen als Referenz dieser Person")
* Speicherfunktion des Detailbildes: `frontend/app.js:4031` (`speichereEditorRahmen`)
* Endpunkt-Aufruf aus dem Editor: `frontend/app.js:4152` (still) bzw. `:4052`
  (Referenz-Nachbearbeitung)
* Endpunkt `POST /api/gesichter/quiz/antwort`: `backend/app/router/gesichter.py:123`
* Weg des selbst gezeichneten Rahmens: `backend/app/router/gesichter.py:135`
  (`ergaenze_person_mit_bbox`)
* Weg des erkannten Gesichts: `backend/app/router/gesichter.py:139` (`beantworte_runde`)
* Einbettung beim Speichern des Referenz-Rahmens: `backend/app/router/gesichter.py:190`
  (`face_service.embedding_fuer_bbox`)
* Dienst der Quiz-Antwort: `backend/app/services/gesicht_quiz.py:667`
* übernimmt die Einbettung des erkannten Gesichts: `backend/app/services/gesicht_quiz.py:704`
* Einbettung des bestätigten Rahmens (Rückfall für den gezogenen Rahmen):
  `backend/app/services/gesicht_quiz.py:713` und `:851`

**Befund:** Der Hinweistext der App ist **nicht** zu viel versprochen — dieser Weg legt eine
Referenz an, und zwar mit Vektor: erst die Einbettung des erkannten Gesichts, sonst der
Rückfall auf den bestätigten Rahmen (`embed_crop` auf dem Gerät).

## 3. Der zweite Weg — Gruppen-Benennen erzeugt KEINEN Vektor

Derselbe Nachweis für den Namensweg:

* Endpunkt `POST /api/gruppen/antwort`: `backend/app/router/gruppen.py:87`
* Endpunkt `POST /api/gruppen/umbenennen`: `backend/app/router/gruppen.py:171`
* Dienst, der die Antwort speichert: `backend/app/services/gruppen_quiz.py:1423`
* Anwenden der Antwort: `backend/app/services/gruppen_quiz.py:1449`
* schreibt die Namen: `backend/app/services/gruppen_quiz.py:229`
* schreibt die Vorgaben: `backend/app/services/gruppen_quiz.py:236`

**Gemessen: 0 Vorkommen von `embedding`/`vektor` in `gruppen_quiz.py`.** Dieser Weg speichert
Namen und Vorgaben, keinen Vektor. Das ist der Kern des behaupteten Widerspruchs: es sind
**zwei verschiedene Wege** — der Detailbild-Editor speichert über den Gesichter-Weg (mit
Vektor), das Benennen in der Gruppenliste über den Gruppen-Weg (ohne Vektor). Aus der
Beobachtung „Benennen erzeugt keinen Vektor" folgt deshalb **kein** Widerspruch in der Anzeige;
sie beschreibt nur den anderen Weg.

## 4. Die Benennungs-Dateien (nur Zahlen, keine Namen)

| Datei | Form | Einträge | Vektor-Schlüssel |
|---|---|---|---|
| `personen_bestaetigt.json` | dict | `bestaetigt`: 20 · zusammen 20 | keine (0) |
| `personen_vorgaben.json` | dict | `ausgeschlossen`: 40 · `gleich`: 14 · `verschieden`: 5 · zusammen 59 | keine (0) |

Beide Dateien zusammen: **79 Einträge, 0 Vektor-Schlüssel** — passt zum Nullbefund aus
`gruppen_quiz.py`.

**Ehrliche Grenze:** Der eigentliche Referenzspeicher `gesichter_katalog.json` liegt **am
Gerät**; am PC fehlt die Datei. Die Zahl der vorhandenen Referenzen ist am PC deshalb
**NICHT zählbar** — der Bericht schreibt das ausdrücklich hin, statt eine Zahl zu schätzen.

## 5. Was das für den Plan bedeutet

* **Abschnitt 3** kann mit Beleg geschlossen werden: Das Handy rechnet Gesichtsvektoren selbst
  (proot-Debian, `face_service` → `face_infer`), und ein einzelner Ausschnitt lässt sich
  einbetten (`embed_crop`). Ein „Erkennung nur für dieses Bild neu starten" ist technisch kein
  neuer Rechner, sondern ein neuer Aufruf.
* **Abschnitt 4.1** ist **kein Widerspruch, sondern eine Weichenstellung**: soll ein
  verrücktes/umbenanntes Kästchen die Referenz ändern, muss es über den **Gesichter-Weg**
  gespeichert werden. Wird es über den Gruppen-Weg benannt, entsteht kein Referenzvektor —
  die Anzeige dürfte dann keine Referenz behaupten.

## Belege

* Werkzeug: `tools/foto_sortierung/gesicht_referenz_wege_messen.py` (nur lesen).
* Testdatei: `backend/tests/test_gesicht_referenz_wege_messen.py` — **12 passed**
  (die tragenden Stellen werden gegen den **echten** Code geprüft, mit Gegenprobe: ein echter
  Vektor-Schlüssel wird gefunden, ein Namensweg ohne Vektor bleibt bei 0; fehlende und kaputte
  Dateien werden gemeldet statt geworfen; kein Personenname im Bericht; keine Schreib-,
  Netz- oder Prozessaufrufe im Werkzeug).
* Messlauf am echten Bestand: Exit 0, Ausgabe wörtlich oben übernommen.
* Grenzen: kein fremder Code angefasst, nichts gelöscht, kein Bild geöffnet oder gesendet,
  kein Vision- und kein Websuche-Aufruf, keine Modellkosten, kein Netzaufruf, kein
  pCloud-Schreibzugriff, keine Geräteeingriffe, keine Personennamen im Bericht oder Dokument.
