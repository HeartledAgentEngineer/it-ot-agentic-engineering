# 14.10.2026 – Websuche mit Namensverbot (ersetzt die Themensperre)

**Anlass.** Die Themensperre aus `b09c5cf`/`3431526` schaltete die Websuche bei jedem Bild- oder
Familienwort ab. Sebastian: Wetter, Orte und „wie lange brauche ich zu Oma und Opa“ sollen ohne
Zusatzsatz gesucht werden. Verboten sein sollen nur **Personennamen** aus seinem Leben.
Öffentliche Personen, die nicht in seinem Bestand sind, dürfen gesucht werden.

**Plan:** `.hermes/plans/2026-10-14_websuche-namensverbot.md`, Fassung 7.
Codex hat ihn in Runde 7 freigegeben (FREI). Hermes hat ihn in Fassung 4 geprüft.

## Was sich ändert

- **Ein einziger Weg ins Netz:** neu `backend/app/services/web_suche.py::suchen(anfrage,
  nutzer_nachricht)`.
  - Zuerst kommt die Namensprüfung.
  - Danach folgt ein eigener, kontextfreier OpenRouter-Aufruf. Er enthält genau eine Nachricht,
    nämlich den Suchtext. Dazu kommen das Plugin `web` und `data_collection: deny`.
  - Die Funktion wirft nie einen Fehler.
- **Der Hauptaufruf sucht nie selbst:** `llm_service._extra_body` setzt kein Such-Plugin und kein
  `openrouter:web_search` mehr.
- **`auto`:** Das Modell bekommt das neue Werkzeug `web_suche(anfrage)`. Damit hat das Register
  11 Werkzeuge.
  - Bei `off` und `manual` fehlt es im Schema.
  - Ruft das Modell es trotzdem auf, kommt „Websuche ist aus.“ zurück.
  - Ergebnisse liefern Quellen und bei Ablehnung eine Statuszeile. Beide reicht
    `werkzeug_schleife` weiter.
- **`manual`:** `router/chat.py::_websuche_vorab` sucht vorab, und zwar mit Sebastians eigenem
  Satz.
  - Treffer hängen als „[Websuche zu deiner Frage]“ an der Nachricht.
  - Bei einem Namen erscheint „🔒 Websuche ohne Namen – für diese Frage aus“.
- **Namensprüfung (`websuche_schutz.py`, neu geschrieben):**
  - Personen kommen aus dem Quiz, mit dem alten Katalog als Rückfall. Dazu kommen WhatsApp-Kontakte
    mit mindestens zwei Wörtern (`werkzeuge.bekannte_namen_streng`, 5-Minuten-Cache).
  - Ist die Liste nicht lesbar, wird nicht gesucht.
  - Umlaute werden umgeschrieben, Groß- und Kleinschreibung ist egal, Endungen mit `s` werden
    erkannt.
  - Freigaben kommen nur aus Sebastians eigener Nachricht und nur bei einem Suchauftrag.
  - Ins Log kommen nur Zähler.
- **Systemhinweis:** „Suche im Internet nie nach Personennamen aus Sebastians Leben. Allgemeines,
  Orte und Adressen darfst du mit web_suche suchen.“
- **Entfernt:** `wirksamer_modus`, `nutzertexte`, `_websuche_modus` und die Regel „Websuche nach
  dem ersten Werkzeugergebnis aus“.
  - Die Regel entfällt, weil der Suchaufruf jetzt ohne Kontext läuft.
  - Der DSML-Filter bleibt unverändert.

## Grenzen (bewusst)

- Namen, die nur im Archiv oder in den Erinnerungen stehen, sind nicht geschützt.
- Vornamen allein aus Kontakten werden nicht erkannt.
- Andere Umschriften („Myller“) werden nicht erkannt.
- Das Modell kann einen Namen umschreiben oder erfinden. Die Suchmaschine formuliert ihre Anfrage
  selbst, kennt aber nur den Suchtext.
- `auto` sucht auf Wegen ohne Werkzeuge nicht.
- Eine bewusste eigene Freigabe geht durch, zum Beispiel „Such im Internet nach Ida Geburtstag“.

## Prüfung

- `backend/tests/test_websuche_schutz.py` ist neu geschrieben: 63 Tests, nur erfundene Namen. Die
  DSML-Tests sind übernommen.
- `test_werkzeuge.py`: 11 Werkzeuge.
- `test_tool_use_stream.py`: Statt `openrouter:web_search` steht jetzt `web_suche` im Schema.
- Gezielte Läufe: 140 passed. Den vollen Prüfbefehl erzwingt der Commit-Hook.
- Messung am Handy steht noch aus: Hermes ruft `bekannte_namen_streng()` am PC und am Handy auf und
  meldet nur Zahlen.

## Nachtrag: Ergebnisprüfung Codex, Runde 1 (EINWAND, behoben)

1. **Ein kaputter alter Katalog ließ die Suche offen.**
   - Ursache: `gesichter_service.liste_personen()` liefert bei einem Lesefehler still `[]`.
   - Behebung: Neu ist `werkzeuge._katalog_personen_streng()`. Fehlt die Datei, ergibt das `[]`.
     Ist sie kaputt oder hat sie eine unbekannte Form, wirft die Funktion einen Fehler (beschädigte Einträge erst seit Runde 2), und
     `bekannte_namen_streng()` liefert `None`. Die Suche ist damit gesperrt.
2. **Beschädigte Kontaktfelder ließen die Suche offen.**
   - Ursache: Stand bei `telefonbuch_namen` ein Text statt einer Liste, wurden einzelne Buchstaben
     gelesen.
   - Behebung: `_kontakt_namen()` prüft jetzt jeden Feldtyp. Eine Liste, die keine Liste ist,
     sperrt. Dasselbe gilt für Einträge, die kein Text sind, und für Teilnehmer, die kein Objekt
     sind.
   - Leere Felder und `None` bleiben erlaubt.

**Tests:** 11 neue Fälle in `test_websuche_schutz.py`. Der Rückfalltest liest jetzt eine echte
Katalogdatei statt einer Attrappe. Die Datei hat damit 74 Tests.

## Nachtrag: Ergebnisprüfung Codex, Runde 2 (EINWAND, behoben)

**Was Codex gefunden hat.** Die Behebung aus Runde 1 war unvollständig: Zwei Quellen sortierten
beschädigte Einträge weiterhin still aus.

- `gruppen_quiz.personen()` lieferte aus `{"bestaetigt": [...]}` eine leere Liste, und zwar mit
  `ok=True`.
- Der alte Katalog übersprang Einträge, die kein Objekt sind.

**Behebung.** Neu ist `werkzeuge._personen_namen_streng()`. Die Funktion liest die vier
Personenquellen direkt und streng, nicht mehr über die Quiz-Übersicht:

- `personen_bestaetigt.json`
- `personen_vorgaben.json` mit dem Feld `zugeordnet`
- `personen_profile.json`, daraus die Profilnamen
- `gesichter_katalog.json`

Eine fehlende Datei ist kein Fehler. Eine vorhandene Datei mit falscher Form oder einem Eintrag
falschen Typs ergibt `None`, die Suche ist dann gesperrt.

**Der alte Katalog zählt jetzt immer mit**, nicht mehr nur als Rückfall. Mit den Profilnamen sind
außerdem mehr Namen geschützt als vorher.

**Tests.** Der Abschnitt zu den Namensquellen arbeitet jetzt nur noch mit echten Dateien in
`tmp_path`. Auch der Katalogpfad wird dorthin umgebogen, die echten Dateien werden also nie
gelesen. Er enthält 15 Fälle für beschädigte Personenquellen, 7 für beschädigte Kontaktfelder und
3 für eine kaputte Kontaktdatei.

## Nachtrag: Ergebnisprüfung Codex, Runde 3 (EINWAND, behoben)

**Befund:** Eine vorhandene Namensdatei, die nur `null` enthält, sah aus wie eine fehlende Datei.
Die Namensliste galt dann als gültig, die Suche blieb offen. Betroffen waren der Katalog und die
drei Quiz-Dateien.

**Behebung:** `werkzeuge._json_streng()` wertet `null` jetzt als beschädigt. Die Namensliste wird
damit `None`, und die Suche ist gesperrt.

**Tests:** 5 neue Fälle, viermal Personenquellen und einmal Kontaktdatei. Die Datei hat jetzt
92 Tests.

**Hinweise von Hermes, bewusst unverändert:**
- Die Länge des Suchtexts ist nicht begrenzt. Plan F7 verlangt das nicht.
- Ein leerer Bestand löst keine Meldung aus. Das ist bei fehlenden Dateien erlaubt.

Die Messung der Namensliste am Handy bleibt offen.

## Nachtrag: Ergebnisprüfung Hermes (EINWAND, beide Befunde behoben)

Hermes hat das Namensverbot parallel zu Codex eigenständig geprüft. Der Bericht steht in
`docs/changelog-2026-10-14-websuche-namensverbot-ergebnispruefung-hermes.md`.

1. **Der Suchtext hatte keine Obergrenze.**
   - Gemessen: 3.479 Zeichen persönlicher Fließtext gingen vollständig ins Netz.
   - Behebung: Suchanfragen, die das Modell selbst formuliert (Werkzeug `web_suche`), sind auf
     `web_suche.MAX_ANFRAGE_MODELL = 200` Zeichen begrenzt. Längere Anfragen gehen nicht ins
     Netz, das Modell bekommt den Hinweis, kürzer zu fragen.
   - Die Werkzeugbeschreibung verlangt jetzt ausdrücklich: kurz und ohne persönliche Details.
   - Sebastians eigener Satz im Modus `manual` bleibt ohne Grenze.
2. **Ein leerer Bestand galt als „nichts zu schützen“.**
   - Fehlen alle Namensquellen, zum Beispiel am Handy, wenn die Dateien nie übergeben wurden,
     lief jede Suche durch.
   - Behebung: Ist der Bestand insgesamt leer, liefert `bekannte_namen_streng()` jetzt `None`.
     Die Suche ist dann gesperrt, im Log steht „Namensliste leer“.
   - **Folge am Handy:** Ohne Namensdateien gibt es dort keine Websuche, bis die Dateien
     ankommen.

**Tests:** 6 neue oder geänderte Fälle. Die Datei `test_websuche_schutz.py` hat jetzt 96 gesammelte
Testfälle (nachgemessen am 14.10.2026: `.venv/Scripts/python -m pytest tests/test_websuche_schutz.py
--collect-only -q` → „96 tests collected“; die frühere Angabe „97“ war um eins zu hoch angesetzt — die
Datei trägt 47 Testfunktionen, der Rest ist parametrisiert).
