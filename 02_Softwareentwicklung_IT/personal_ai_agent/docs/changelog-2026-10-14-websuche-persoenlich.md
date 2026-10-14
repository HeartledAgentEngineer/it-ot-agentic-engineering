# Changelog 14.10.2026 – Keine Websuche bei persönlichen Fragen

## Anlass

Am 12.10.2026 abends schrieb Sebastian in den Chat: „Zeig mal eine Diashow mit Bildern von Opa …“.
Im Chat erschienen DSML-Zeilen (DeepSeeks Format für Werkzeugaufrufe), danach startete eine
**Websuche mit dem Namen**. Sein Wunsch: Bei Fragen nach Bildern oder Personen soll nicht im Internet
gesucht werden, außer er fragt ausdrücklich danach.

Ursache im Code:
- Websuche `auto` gab das Suchwerkzeug zusammen mit den eigenen Werkzeugen an das Modell, und nichts
  hielt es bei persönlichen Fragen auf.
- `manual` sucht bei jeder Anfrage.

## Änderung

- **W1 – harte Sperre** (neu `backend/app/services/websuche_schutz.py`, verdrahtet über
  `router/chat.py::_websuche_modus` in `/chat` und `/stream`):
  - **Persönlich** ist ein Text in drei Fällen:
    - Bild- oder Medienwort: foto, bild, diashow, video, galerie, album.
    - Familienwort: opa, oma, mama, schwester … (19 Wörter).
    - Name einer bekannten Person: der ganze Name oder ein Namensteil mit mindestens 3 Buchstaben,
      jeweils als ganzes Wort.
  - **Geprüft wird alles, was das Modell sieht:**
    - die Nachricht samt Werkzeug-Zusätzen,
    - alle Nutzer-Nachrichten des übertragenen Verlaufs,
    - die übertragene Zusammenfassung.

    Ist etwas davon persönlich, wird die Websuche `off`.
  - **Ausnahme** nur bei einem Suchauftrag in der eigenen Nachricht: ein Suchverb zusammen mit einem
    Ort im Netz („Such im Internet nach …“) oder „google“. Die Ausnahme gilt nur ohne Sperrwort wie
    „nicht“, „kein“, „ohne“, „verzichte“, „lass“, „statt“ oder „außer“. Im Zweifel bleibt die Sperre.
  - Im Stream erscheint „🔒 Websuche für diese Frage aus (persönlich)“, wenn die Websuche vorher an
    war.
  - Das Log nennt nur den Grund (`bild`/`familie`/`person`/`verlauf`), nie Text oder Namen.
  - Wirft die Prüfung einen Fehler, ist die Websuche aus.
  - Neuer Helfer `werkzeuge.bekannte_namen()` mit dem gemeinsamen Kern `_bekannte_personen()`: zuerst
    das Personen-Quiz, sonst der alte Gesichtskatalog. `personen_liste` nutzt jetzt dieselbe Quelle.
- **W2 – weicher Riegel:** `werkzeuge.SYSTEM_HINWEIS` verbietet die Internetsuche nach Personen aus
  Sebastians Leben, nach seinen Fotos oder Erinnerungen ohne ausdrücklichen Wunsch.
- **W3a – DSML-Filter** in `werkzeug_schleife.laufe`:
  - Ein Rückhaltepuffer erkennt die Marken `<｜DSML｜` und `<|DSML|`, auch wenn sie über mehrere
    Stücke geteilt ankommen.
  - Ab der Marke wird nichts mehr angezeigt.
  - Kam in der Antwort vorher noch kein Text, wirft die Schleife `DsmlAlsText`, und
    `llm_service.chat_stream` antwortet wie bisher ohne Werkzeuge.
  - Kam schon Text, erscheint die Statuszeile „⚠️ Das Modell hat einen Werkzeugaufruf als Text
    geschickt – er wurde nicht ausgeführt.“
- Doku: `docs/spec-tool-use-v1.md` hat einen neuen Abschnitt „Websuche und persönliche Fragen“.

## Abweichung vom Plan (strenger)

Der Plan prüfte die aktuelle Nachricht und den Verlauf. Zusätzlich wird jetzt auch die Nachricht
**mit ihren Werkzeug-Zusätzen** geprüft (`s_user` bzw. `user_message_fuer_llm`), denn auch das sieht
das Modell. Für die Ausnahme zählt weiterhin nur Sebastians eigener Text.

## Tests

- Neu `backend/tests/test_websuche_schutz.py` mit 43 Tests, offline und mit erfundenen Namen.
  - **Regel:**
    - Bild-, Familien- und Personenfrage ergeben `off`, jeweils aus `auto` und aus `manual`.
    - Eine neutrale Frage behält den Modus.
    - Ein Name zählt nur als ganzes Wort.
    - Eine kaputte Namensliste wirft nicht.
    - Ein Suchauftrag behält den Modus.
    - Fünf Fälle mit Verneinung oder ohne echten Auftrag sperren.
    - Eine Folgefrage an fünfter Stelle im Verlauf sperrt noch.
    - Die Zusammenfassung zählt mit.
    - Das Log enthält keine Namen.
  - **Helfer:** Quiz, Rückfall auf den alten Katalog und Fehlerfall; `personen_liste` nutzt den
    Helfer.
  - **Systemhinweis:** Er enthält die Regel.
  - **Verdrahtung:**
    - `/stream`: Eine Bildfrage ergibt `off` plus Statuszeile, eine neutrale Frage behält den
      Modus, `off` ergibt keine Statuszeile, und die Zusammenfassung sperrt.
    - `/chat`: Eine Personenfrage und die Zusammenfassung sperren; als Gegenprobe behält eine
      neutrale Frage den Modus.
    - Der Verlauf ist in jedem Test abgeschottet, sodass nie der vorhandene Verlauf am Rechner
      mitgelesen wird.
  - **DSML-Filter:**
    - Eine Marke im ersten Stück, eine über drei Stücke geteilte Marke und die ASCII-Schreibweise
      lösen jeweils den Rückfall aus.
    - Nach normalem Text erscheint die Statuszeile.
    - Ein `<` ohne Marke bleibt vollständig erhalten.
    - Die ganze Kette mit `chat_stream` endet im Rückfall.
- Gezielte Läufe: `test_websuche_schutz`, `test_werkzeug_schleife`, `test_tool_use_stream` und
  `test_chat_endpoint` ergaben **67 passed**, `test_personen_werkzeuge_quiz` **23 passed**.

## Prüfung

- Planprüfung durch Codex in vier Runden: R1 bis R3 mit EINWAND, R4 **FREI** (Protokoll
  `.hermes/pruefkreis/websuche-persoenlich-plan.md`).
- Die Hermes-Planprüfung fehlt, weil der Prüfkreis auf eine Nur-Lese-Sperre wartet, die noch nicht
  eingerichtet ist. Sebastian hat am 14.10. entschieden, nur mit der Codex-Freigabe zu bauen.
- Die Ergebnisprüfung steht noch aus.

## Offen

- **W3b:** Messen, warum DSML als Text kommt; es sollen je zwei Läufe mit einem erfundenen Namen
  laufen.
- **Handytest:** Mit der Frage aus dem Anlass muss die 🔒-Zeile erscheinen, und es darf keine
  Fundstellen aus dem Netz geben.
- Bereits gesendete Suchanfragen lassen sich nicht zurückholen.

## Nachtrag: Codex-Ergebnisprüfung, Runde 1 (EINWAND, beide Punkte behoben)

1. **Eine bloße Google-Erwähnung hob die Sperre auf.** Bei einer Nachricht wie „Ida Testmann nutzt
   Google Drive“ blieb die Websuche an.
   - Behoben: „Google“ zählt nur noch als Verb („google mal …“, „googel nach …“, „googeln“), siehe
     `websuche_schutz._GOOGLE`.
2. **Persönliche Werkzeugergebnisse wurden nicht berücksichtigt.** „Welche Personen kennst du?“
   passiert die Eingangssperre, danach liefert `personen_liste` Namen, und die Folgerunde hatte
   weiterhin Suchwerkzeug bzw. Suchplugin.
   - Behoben in `llm_service._chat_stream_mit_werkzeugen`: Sobald im Verlauf ein Werkzeugergebnis
     (`role=tool`) steht, ist die Websuche für alle weiteren Runden aus. Alle eigenen Werkzeuge sind
     persönlich (Personen, Fotos, Archiv, Dateien, Fakten).

Neue Tests in `test_websuche_schutz.py`, insgesamt jetzt 51:
- 3 Fälle, in denen eine bloße Erwähnung von Google sperrt.
- 3 Fälle, in denen Google als Verb ein Auftrag bleibt.
- Für `auto` und `manual`: Die erste Runde hat noch die Websuche, die Runde nach dem
  Werkzeugergebnis nicht mehr.

Gezielter Lauf mit `test_websuche_schutz`, `test_tool_use_stream` und `test_werkzeug_schleife`:
**69 passed**.
