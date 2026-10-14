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
     Ist sie kaputt oder hat sie eine unbekannte Form, wirft die Funktion einen Fehler, und
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
