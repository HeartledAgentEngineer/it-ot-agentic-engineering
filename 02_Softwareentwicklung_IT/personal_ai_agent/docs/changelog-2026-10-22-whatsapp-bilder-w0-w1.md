# 22.10.2026 – WhatsApp-Bilder, W0 + W1: zählen und in die pCloud kopieren

Plan: `.hermes/plans/2026-10-21_whatsapp-bilder.md` (Fassung 5, Planprüfung R5 FREI).
To-do: Punkt 18 in `.hermes/plans/2026-10-20_todo-gesamt.md` (N26).
Beide Werkzeuge laufen am Handy in Termux. Ohne `--schreiben` lesen sie nur.

## Was neu ist

### W0 – `tools/handy/whatsapp_bilder_zaehlen.py`
- Zählt die WhatsApp-Bilder je Unterordner, Jahr und Dateityp:
  - `empfangen` ist der Medienordner selbst,
  - `gesendet` ist `Sent`.
- Gibt nur Anzahl und Gesamtgröße aus. Datei-, Ordner- und Chatnamen erscheinen nie, ebenso keine Pfade. Unbekannte Endungen heißen „andere“, `Private` wird nur gezählt.
- Fehlt der Medienordner oder ist er nicht lesbar, endet das Werkzeug mit **Exit 3** und einem Hinweis auf `termux-setup-storage`. Eine Null meldet es nur bei einem lesbaren Ordner. Steht `Sent` in der Auflistung, wird es immer streng gelesen. Ist es kein lesbarer Ordner (Datei, nicht prüfbar, `stat` oder Auflisten scheitert), endet W0 wie W1 ebenfalls mit Exit 3. „gesendet: 0“ erscheint nur, wenn `Sent` ganz fehlt.
- `--voraussetzungen` prüft der Reihe nach und endet bei der ersten Lücke mit Exit 3:
  1. `httpx` ist da.
  2. Ein Token ist vorhanden (nur ja/nein).
  3. Der Host ist `eapi.pcloud.com`. Jeder andere Host endet vor jeder Netzanfrage.
  4. Eine nur lesende pCloud-Abfrage (`userinfo`) klappt.

### Gemeinsam – `tools/handy/whatsapp_bilder_gemeinsam.py`
- `zugang_aufloesen()` liest Token und Host zuerst aus der Umgebung, dann aus `backend/.env`. Es gibt keine Werte aus. Erlaubt ist nur `eapi.pcloud.com`.
- Jeder Fehler beim Lesen des Zugangs (auch eine beschädigte `.env` mit ungültigem UTF-8) und beim Laden von `uebergabe_hochladen.py` wird zu einer festen Zeile mit Exit 3, ohne Ursache und ohne Inhalt.
- Dazu kommen die Dateiauswahl (`.jpg/.jpeg/.png/.webp`), die Jahresbestimmung und `fehlerart()`.
- `fehlerart()` gibt nur feste Fehlerarten oder den Klassennamen aus, nie den Text einer Ausnahme.

### W1 – `tools/handy/whatsapp_bilder_hochladen.py`
- Kopiert nach `/Agent/whatsapp_bilder/<empfangen|gesendet>/<JJJJ>/`.
- Ein Ziel außerhalb von `/Agent/` ergibt Exit 2. Ein Manifest im Repo ergibt ebenfalls Exit 2.
- Beide Prüfungen laufen über die Hüllen `ziel_pruefen()` und `manifest_im_repo()`. Jeder Fehler daraus wird zu `AufrufFehler` mit fester Zeile (Exit 2), ohne Pfad, ohne Ursache und ohne Kontext.
- **Schutz vor Links:**
  - Manifest und Sperre werden vor jedem Zugang, Netzaufruf und Lesen geprüft, auch im Trockenlauf.
  - Ist die Datei selbst ein symbolischer Link (auch ein toter), endet der Lauf mit Exit 2.
  - Ein vorhandenes Manifest mit mehreren Namen (harter Link, `st_nlink > 1`) ergibt ebenfalls Exit 2. Der Schreiber prüft das zusätzlich direkt vor jedem Anhängen und bei der Reparatur vor der Kopie und vor `os.replace`; schlägt die Prüfung dort an, stoppt der Lauf mit Exit 1 ohne weiteren Upload.
  - Ebenso, wenn der angegebene oder der vollständig aufgelöste Pfad (`os.path.realpath`) im Repo liegt. So kann auch ein Ordner-Link außerhalb des Repos nicht ins Repo führen.
  - Ein Ordner-Link, der nach außen zeigt, bleibt erlaubt (Termux-Speicherpfade).
  - Danach arbeitet das Werkzeug nur noch mit dem aufgelösten Manifestpfad.
- **Trockenlauf ist Standard.** Er nimmt keine Sperre, schreibt kein Manifest, legt keinen Ordner an und lädt nichts hoch. Er nutzt nur `listfolder`, `stat` und `checksumfile`.
- **Am Handy ändert sich nichts.** Die Bilder werden nur gelesen.
- **In der pCloud wird nie überschrieben.** Der Upload läuft mit `renameifexists=1` und `nopartial=1`.
- **Eigene Kennung je Upload.** Der Cloud-Name ist `<stamm>_wa<k>.<endung>`, wobei `k` aus 12 zufälligen Hex-Zeichen besteht.
- **Vorab-Zeile vor jedem Upload.** Die Zeile `upload_begonnen` wird geschrieben und per fsync gesichert. Erst danach startet der Upload. `hochgeladen` folgt nur, wenn der **Eigentumsbeleg** besteht. Den prüft `stat` per fileid:
  - Der Zielordner stimmt.
  - Die eigene Kennung steht im aktuellen Namen.
  - Die Cloud-Prüfsumme sha256 stimmt mit den gelesenen Bytes überein.
- Jede Datei wird einmal gelesen. Prüfsumme und Upload kommen aus denselben Bytes.
- **Zustände im Manifest:** `upload_begonnen`, `hochgeladen`, `fehlt_in_cloud`, `unklar` und `unklar_begonnen`.
  - Das Manifest liegt unter `~/foto_sortierung/whatsapp_bilder_manifest.jsonl`. Es enthält Dateinamen und bleibt deshalb nur am Handy.
  - Ist eine Datei in der Cloud verschoben, umbenannt oder verändert worden, heißt sie `unklar`. Sie wird nicht neu hochgeladen.
  - `fehlt_in_cloud` mit neuem Upload gibt es nur, wenn `stat` selbst „nicht gefunden“ meldet. Findet `stat` die Datei, `checksumfile` aber nicht oder ohne gültige Prüfsumme, heißt sie `unklar` (kein Upload, auch nicht im Folgelauf). Andere Fehler von `checksumfile` werden als Fehlerart gezählt und lösen keinen Upload aus.
  - Gibt es eine Vorab-Zeile ohne belegten Treffer, heißt sie `unklar_begonnen`. Diese Fälle lädt das Werkzeug nicht von selbst neu hoch. Das geht nur bewusst mit `--offene-neu` zusammen mit `--schreiben`.
- **Strenges Manifest:**
  - Jede Zeile muss einen bekannten Zustand und die dazu nötigen Felder mit richtigem Typ tragen (`PFLICHTFELDER`).
  - Eine kaputte, unvollständige oder unbekannte Zeile ergibt Exit 3, noch vor jedem Upload. Das gilt auch im Trockenlauf. Die Meldung nennt nur die Zeilennummer. Nichts wird still übersprungen.
  - Auch eine leere oder nur aus Leerzeichen bestehende Zeile ist ein Fehler (eine leer gewordene Vorab-Zeile könnte sonst eine Dublette auslösen). Erlaubt ist nur das leere Ende hinter dem letzten Zeilenumbruch. Zeilen mit Windows-Zeilenende (`\r\n`) werden gültig gelesen; der Inhalt wird trotzdem vollständig geprüft.
  - Eine unlesbare letzte Zeile ohne Zeilenumbruch ergibt ebenfalls Exit 3 vor jedem Upload, auch im Trockenlauf. Ein Schreibabbruch und eine Beschädigung lassen sich daran nicht unterscheiden. Das Manifest bleibt dabei unverändert. Die Meldung nennt die Zeilennummer und den Ausweg.
  - Ausweg nur nach einem bekannten Abbruch: `--schreiben --letzte-zeile-verwerfen`. Die beschädigte Zeile bleibt stehen. Die Reparatur ist atomar: Zuerst entsteht die Kopie `<manifest>.vor_verwerfen_<stempel>`. Dann wird eine eigene Temp-Datei `<manifest>.verwerfen_<stempel>.tmp` geschrieben (alte Bytes unverändert, Zeilenumbruch, Markierung `vorab_abgebrochen` mit der Zeilennummer) und mit fsync gesichert. Kopie und Temp-Datei liegen im Ordner des aufgelösten Manifests und werden exklusiv angelegt (`xb`); ist ein Name belegt, wählt das Werkzeug einen neuen und überschreibt nie. Erst danach ersetzt `os.replace` das Manifest. Danach steht entweder der alte Stand im Manifest (der Ausweg geht erneut) oder der fertige neue (wieder streng lesbar, ohne Leerzeile). Eine Temp-Datei aus einem abgebrochenen Versuch bleibt unverändert liegen. Das Werkzeug benennt nichts um und löscht nichts (Wächtertest gegen `os.rename`/`shutil.move`). Jeder Fehler dabei stoppt den Lauf mit Exit 1 ohne Upload. Die Datei dieser Zeile gilt danach als neu und wird mit einer neuen Vorab-Zeile hochgeladen. Hatte der abgebrochene Lauf sie doch schon hochgeladen, liegt sie dann zweimal in der Cloud; deshalb gibt es diesen Weg nur mit ausdrücklicher Zustimmung. Ohne `--schreiben` ergibt die Option Exit 2; bei unauffälliger letzter Zeile hat sie keine Wirkung, und eine Ausgabezeile sagt das.
  - Scheitert das Aufbereiten, Schreiben oder fsync einer Manifestzeile (jede Ausnahme, auch Kodierungsfehler), startet kein weiterer Upload, und der Lauf endet mit Exit 1.
- **Ordner anlegen** läuft über die Hülle `ordner_holen_sicher()`. Der bestehende Ordnerweg bleibt unverändert. Jede Ausnahme daraus wird zu einer festen Fehlerart ohne Text und ohne Pfad.
- **Nur ein Schreiber gleichzeitig.** Mit `--schreiben` nimmt der Lauf den Sperr-Ordner `~/foto_sortierung/.whatsapp_hochladen.sperre`. Liegt die Sperre schon, endet er mit Exit 3. Wurde der Lauf hart abgebrochen, bleibt sie liegen. Die Meldung nennt dann den Sperrnamen, und der Ausweg ist, den Ordner von Hand zu entfernen.
- Weitere Optionen sind `--letzte-zeile-verwerfen` (siehe oben), `--max N` (höchstens N Uploads) sowie für Tests `--ordner`, `--ziel`, `--manifest` und `--sperre`.
- **Die Ausgabe enthält nur Zahlen.** Fehler erscheinen als Fehlerart mit Zähler, zum Beispiel `abgelehnt 2000 x5`.
- **Rückweg:** `entfernbare_fileids()` nennt nur Dateien mit eigener Kennung im Zustand `hochgeladen`. `unklar` und `unklar_begonnen` werden nie freigegeben. Das Werkzeug selbst entfernt nichts. Ein späteres Werkzeug zum Entfernen muss den Eigentumsbeleg vorher erneut in der Cloud prüfen (`stat`: Zielordner, eigene Kennung im Namen, Prüfsumme).
- Exit-Codes:
  - 0 = alles in Ordnung,
  - 1 = mindestens ein Fehler,
  - 2 = Aufruf- oder Schutzfehler,
  - 3 = Voraussetzung fehlt (Zugang, Host, Medienordner, Sperre, beschädigtes Manifest).

### Ergänzung – `tools/pcloud/uebergabe_hochladen.py` (nur Zusätze)
- Neue lesende Methoden laufen über `_api_lesen` mit der eigenen Positivliste `ERLAUBTE_LESE_METHODEN`.
- Neue Funktionen: `userinfo_pruefen`, `stat_datei`, `pruefsumme_cloud` und `ordner_auflisten`.
- Dazu kommt `hochladen_ohne_ueberschreiben()`. Sie gibt `(fileid, name_in_cloud)` zurück.
- `_zugang_lesen()` kapselt die bestehenden Zugangsleser für die neuen Funktionen: jeder Fehler wird zu `PCloudFehler("konfig")`.
- `PCloudFehler(art, code=None)` hat eine feste Meldung. `art` kommt nur aus einer festen Liste (`netz`, `http`, `json`, `abgelehnt`, `nicht_gefunden`, `antwort`, `konfig`, `aufruf`). Der Code ist nur eine geprüfte Ganzzahl von 0 bis 99999. Fehlertexte von pCloud, Token und Pfade stehen nie in einer Ausnahme. In allen neuen Fehlerwegen wird die neue Ausnahme erst nach dem `except`-Block geworfen, deshalb sind `__cause__` und `__context__` leer und die ursprüngliche Ausnahme bleibt nicht daran hängen. Das gilt in den drei Werkzeugdateien und im neuen Teil von `uebergabe_hochladen.py`; ein Wächtertest (per `ast`) prüft es.
- `hochladen()`, `_api_get` und `ERLAUBTE_METHODEN` bleiben unverändert.

## Vor dem ersten echten Hochladen (Sebastian, am Handy)
1. `python tools/handy/whatsapp_bilder_zaehlen.py --voraussetzungen` muss mit Exit 0 enden. Dieser echte Lauf steht noch aus, und ohne ihn wird W1 nicht mit `--schreiben` gestartet.
2. Danach zählt `python tools/handy/whatsapp_bilder_zaehlen.py`.
3. Dann folgt `python tools/handy/whatsapp_bilder_hochladen.py` als Trockenlauf.
4. Erst danach startet `… --schreiben`, zuerst mit `--max 20`.

## Belege
- Neu: `backend/tests/test_whatsapp_bilder_zaehlen.py` und `backend/tests/test_whatsapp_bilder_hochladen.py`.
  - Zusammen sind es 270 Tests mit erfundenen Daten in `tmp_path`.
  - Eine pCloud-Attrappe ersetzt das Netz.
  - Abgedeckt sind:
    - Abbruch vor und nach dem Upload,
    - verschobene und veränderte Cloud-Dateien,
    - `--offene-neu`,
    - beschädigtes Manifest (mittlere Zeile, ungültiges UTF-8, halbe letzte Zeile, fehlende Pflichtfelder, falsche Typen, unbekannter Zustand, Leerzeilen, Windows-Zeilenenden, beschädigte letzte Vorab-Zeile mit NUL, BOM, U+2028, abgeschnitten oder ungültigem UTF-8 ohne und mit `--letzte-zeile-verwerfen`, Abbruch der Reparatur vor und nach `os.replace`, halb geschriebene und verwaiste Temp-Datei, Namenskollision bei Temp-Datei und Kopie),
    - widersprüchliche Antworten von `stat` und `checksumfile`,
    - fsync-, Schreib- und Kodierungsfehler,
    - feindliche pCloud-Antworten, auch beim Ordneranlegen, mit erfundenem Dateinamen und Token, `result` als Text, bool, Fließkommazahl oder riesige Zahl,
    - Sperre und Ausgabe nur in Zahlen,
    - symbolische Links für Manifest und Sperre (Link auf eine Datei im Repo, Link nach außen, toter Link, Ordner-Link ins Repo: Exit 2, Ziel byteweise unverändert; Ordner-Link nach außen erlaubt; Reparatur über einen Ordner-Link im aufgelösten Ordner). Dazu kommen harte Links (Exit 2, Ziel unverändert) und ein Linkzähler, der erst vor dem Anhängen oder bei der Reparatur auf 2 springt (Exit 1, kein weiterer Upload, Manifest unverändert). Hier unter Windows ließen sich beide Linkarten anlegen; ohne Rechte dafür würden diese Tests übersprungen.
    - `Sent` vorhanden, aber nicht lesbar (als Datei, `isdir` falsch, `stat` scheitert): Exit 3 in W0 und W1 ohne Upload; `Sent` fehlt: „gesendet 0“,
    - Reparatur löscht nichts: Kopie und verwaiste Temp-Datei eines früheren Versuchs sind vor und nach dem Lauf byteweise gleich,
    - Ausnahmen ohne angehängte Ursache (`__cause__`/`__context__` leer) und ein Wächter gegen `raise` innerhalb von `except`,
    - beschädigte `.env` mit erfundenem Token (W0 und W1 Exit 3, nichts in der Ausgabe) und gekapselte Repo- und Zielprüfung (Exit 2, nichts in der Ausgabe, leere Ausnahmekette),
    - eine Bestandsliste der genutzten Altcode-Funktionen. Sie ist kein Verhaltensbeleg, sondern eine Merkliste: Kommt ein neuer Aufruf dazu oder fällt einer weg, wird der Test rot, und jedem Namen ist der Test zugeordnet, der seine Kapselung prüft.
- Rotlauf: Vor der Umsetzung waren 78 von 79 neuen Tests rot. Vor Nachbesserung 1 waren 20 Tests rot, vor Nachbesserung 2 waren 39 rot, vor Nachbesserung 3 waren 8 rot, vor Nachbesserung 4 waren 12 rot, vor Nachbesserung 5 waren 8 rot, vor Nachbesserung 6 waren 14 rot, vor Nachbesserung 7 waren 25 rot, vor Nachbesserung 8 waren 11 rot, vor Nachbesserung 9 waren 6 rot, vor Nachbesserung 10 waren 15 rot, vor Nachbesserung 11 waren 12 rot.
- Gezielter Lauf über 9 Testdateien: 538 passed, 1 skipped, Exit 0. Dazu kommt der volle Prüfbefehl im Commit-Haken.
- Planprüfung durch Codex (gpt-6-sol, nur lesend): Runden 1 bis 4 EINWAND, **Runde 5 FREI**.
- Ergebnisprüfung: In Runde 1 EINWAND (beschädigtes Manifest, Fehlertexte von pCloud in Ausnahmen, echter Handy-Lauf offen). Behoben bzw. als Vorbedingung eingeordnet. In Runde 2 EINWAND (unvollständige Manifestzeilen, Schreibfehler außer OSError, Ordnerweg mit Fehlertext). Behoben. In Runde 3 EINWAND (Ursache blieb als `__context__` an der Ausnahme). Behoben. In Runde 4 EINWAND (beschädigte `.env` reichte einen Dekodierfehler mit Dateiinhalt durch). Behoben. In Runde 5 EINWAND (Manifestpfad konnte in einer Ausnahme der Repo-Prüfung stehen). Behoben. In Runde 6 EINWAND (leere Manifestzeilen wurden übersprungen). Behoben. In Runde 7 EINWAND (eine beschädigte letzte Zeile wurde von selbst als Abbruch gewertet). Behoben durch Stopp mit ausdrücklichem Ausweg. In Runde 8 EINWAND (widersprüchliche pCloud-Antworten lösten einen Neu-Upload aus; der Ausweg konnte nach einem Teilabbruch festhängen). Behoben. In Runde 9 EINWAND (Umbenennen verwaister Temp-Dateien konnte bei einer Namenskollision überschreiben). Behoben, das Werkzeug benennt nichts mehr um. In Runde 10 EINWAND (ein Manifest-Link außerhalb des Repos konnte auf eine Datei im Repo zeigen). Behoben durch den Link-Schutz für Manifest und Sperre. In Runde 11 EINWAND (harte Links am Manifest; ein unlesbares `Sent` galt still als leer). Behoben. **Runde 12 FREI.**
- Protokoll: `.hermes/pruefkreis/whatsapp-bilder-pruefung-codex.md`.
- Umsetzung durch einen Sonnet-Worker, weil Codex als Worker gesperrt war („blocked by policy“).

## Bekannte Grenzen
- Die Fehlerart beim Ordneranlegen wird aus dem festen Meldungsanfang des unveränderten Altcodes abgeleitet. Ändert sich dieser, fällt sie sicher auf `abgelehnt` zurück.
- Jeder Lauf prüft jede erledigte Datei mit `stat` und `checksumfile`. Bei rund 4.000 Bildern sind das etwa 8.000 Aufrufe, auch im Trockenlauf.
- Videos sind nicht enthalten. Die Entscheidung dazu steht noch aus.

## Nächster Schritt
W2: Aufnahmezeit und Anlass aus der WhatsApp-Datenbank (auf Hermes-Seite). Danach W3 bis W5 (Gesichter, Beschreibungen, Anzeige).
