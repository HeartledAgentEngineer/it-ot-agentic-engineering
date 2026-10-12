# 12.10.2026: Fließtext ist der Standard, Tabellen nur auf Wunsch

## Warum

Sebastian am Handy: Personen kamen im Chat manchmal als Tabelle. Er wünscht
Fließtext, der sich gut vorlesen lässt; Tabellen nur, wenn er danach fragt.
Bei seinen Opas kam schon Fließtext.

Zwei Ursachen, beide im Code belegt:

1. `backend/system_prompt.md` empfahl unter „TON UND FORM“ allgemein „Gut lesbar
   gliedern — Listen, Tabellen, Zwischenüberschriften“.
2. Das Werkzeug `person_auskunft` (`backend/app/services/werkzeuge.py`,
   `_person_auskunft`) lieferte dem Modell „Feld: Wert“-Zeilen, Überschriften
   („Notizen (n):“, „Anlässe (n):“) und Strichlisten („- …“, „ | “). Das Modell
   übernahm diese Form.

## Was geändert wurde

1. **Prompt** (`backend/system_prompt.md`, Abschnitt TON UND FORM): Die alte
   Gliederungsregel ist ersetzt.
   - Standard ist Fließtext in ganzen Sätzen und kurzen Absätzen, ohne Textwände.
   - Werkzeugergebnisse sind Rohdaten. Kommen sie als Liste oder als „Feld:
     Wert“, macht das Modell daraus Sätze und übernimmt nicht ihre Form.
   - Tabellen, Listen und Zwischenüberschriften gibt es nur auf ausdrücklichen
     Wunsch („als Tabelle“, „als Liste“, „Übersicht“, „Stichpunkte“).
   - Die Archiv-Regel „im Fluss, wie Rede“ bleibt unverändert.
2. **Werkzeug** `_person_auskunft` gibt dieselben Angaben jetzt als Sätze in bis
   zu drei Absätzen aus:
   - zuerst Name, Beziehung, Geburtstag und die Zahl der Fotos;
   - dann die Anlässe als ein Satz („Kommt in 2 Anlässen vor: …“);
   - zuletzt „Eigene Notizen: …“.

   Wichtiges steht damit vorn, und die Kürzung bei 6.000 Zeichen trifft nur die
   Notizen.
   - Gleich geblieben sind die Datenquelle, die Grenzen (20 Notizen, 10 Anlässe,
     Abfrage bis 15) und der Schutz (keine Pfade, keine Kennungen).
   - Notiztexte bleiben wörtlich. Nur ein fehlendes Satzende kommt dazu, damit
     zwei Notizen beim Vorlesen nicht ineinanderlaufen.
   - Leere und zurückgenommene Notizen fallen weg.
   - Beginnt ein Anlass-Titel schon mit dem Datum, steht das Datum nicht doppelt.
   - Erreicht die Abfrage ihre Grenze von 15, heißt es „mindestens 15“. Vorher
     stand dort eine scheinbar genaue Zahl.
3. **Unverändert:**
   - Die übrigen Werkzeuge (`personen_liste`, `notizen_suchen`,
     `fotos_uebersicht`) liefern weiter Zeilen, dort trägt nur die Prompt-Regel.
   - Ebenfalls unverändert bleibt das Frontend: `frontend/app.js` liest eine
     bestellte Tabelle weiter als Sätze vor (`tabellenImTextFuerStimme`).

## Tests

- Neu `backend/tests/test_fliesstext_regel.py` mit 5 Tests:
  - Fließtext ist Standard, die Längenregel bleibt.
  - Werkzeugergebnisse gelten als Rohdaten.
  - Tabellen gibt es nur auf Wunsch, mit allen vier Wunschwörtern, und die alte
    Empfehlung ist weg.
  - Die Archiv-Regel bleibt.
  - Der Gesamtprompt wird aus erfundener Basis- und lokaler Datei in `tmp_path`
    gebaut. Die Regel steht dabei vor der persönlichen Ergänzung. Die echte
    `system_prompt.local.md` wird nie gelesen.
- `backend/tests/test_personen_werkzeuge_quiz.py`: Die vier alten Prüfungen sind
  auf die Satzform umgestellt, alle Sachangaben und Fehlerfälle werden weiter
  geprüft. Vier Tests sind neu:
  - Die eigene Rahmung ist Fließtext: keine Zeile beginnt mit „- “ oder endet
    mit „:“, und es gibt kein „ | “.
  - Leere Notizen werden übersprungen.
  - Langfall mit 21 Notizen und 11 Anlässen: Es erscheinen genau 20 und 10.
    Nichts Zurückgenommenes, keine Kennung und kein Pfad kommen vor, nichts wird
    gekürzt, und die Reihenfolge stimmt.
  - Die Abfragegrenze erscheint als „mindestens 15“.

Prüfbefehl siehe Änderungsprotokoll in `CLAUDE.md`.

## Ablauf und Prüfung

- Plan `.hermes/plans/2026-10-12_fliesstext-und-urlaubserzaehlung.md`
  (gitignored).
- Planprüfung Runde 1: Hermes (DeepSeek v4.1 Flash) gab „freigegeben mit
  Auflagen“, Codex (gpt-5.6-terra) „nicht freigegeben“. Der Codex-Befund: Die
  Werkzeugausgabe selbst erzeugt Listen.
- Runde 2 auf Fassung 2: Hermes (Sitzung `20261012_094650_f8b084`) und Codex
  gaben beide „freigegeben mit Auflagen“. Die Auflagen sind umgesetzt.
- Ausgeführt hat Claude Code; das Thema ist nicht sensibel (Prompt-Text,
  Werkzeug-Form, erfundene Testdaten).

## Ehrlich offen

- Wie das Modell wirklich antwortet, lässt sich offline nicht prüfen. Dafür gibt
  es die Handyprüfung nach dem nächsten App-Start:
  - „Erzähl mir von <Person>“ soll Fließtext liefern.
  - „… als Tabelle“ soll eine Tabelle liefern.
  - „Wen kennst du?“ soll Fließtext liefern.
- `system_prompt.local.md` ist persönlich, Claude liest sie nicht. Hermes hat die
  **PC-Fassung** geprüft (Sitzung `20261012_095753_e113cd`): 40 Zeilen, **kein
  Widerspruch**. Ihre Vorgaben betreffen Inhalt und Haltung, nicht das
  Ausgabeformat. Die **Handy-Fassung** ist nicht geprüft, weil kein Kabel
  angeschlossen war.
- Zeigen `personen_liste` & Co. am Handy weiter Listen, folgt dort derselbe
  Umbau.
