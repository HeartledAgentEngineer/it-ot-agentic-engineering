# 22.10.2026 – WhatsApp W2, Teil A: Vorprüfung, Messprobe, Strukturbeleg

Plan: `.hermes/plans/2026-10-22_whatsapp-w2.md` (Fassung 16, Teil A, Planprüfung R16 FREI).
Teil A bereitet die Entschlüsselung (Teil B) vor. Es entschlüsselt nichts, ändert keine Quelle
und braucht keine neue Abhängigkeit. Die Bibliothek `wa_crypt_tools` wird nie geladen.

## Was neu ist

### W2a – `tools/handy/whatsapp_sicherung_pruefen.py` (Termux)
Nur Standardbibliothek. Alle Meldungen sind feste Texte oder Zahlen, ohne Pfade, Namen und
ohne Schlüsselinhalt. Die Meldungen sind wie bei W1 ASCII (`ae`, `ue`, Bindestrich).

**Normalbetrieb** (`python -B tools/handy/whatsapp_sicherung_pruefen.py`)
- Prüft der Reihe nach, ohne beim ersten Fehler abzubrechen:
  1. Python 3.11 oder neuer.
  2. Der Sicherungsordner ist lesbar (`isdir`, `access`, `listdir`). Standard ist
     `/sdcard/Android/media/com.whatsapp/WhatsApp/Databases`.
  3. Zählt `msgstore*.crypt15` und `msgstore*.crypt14` (nur nach Namen).
  4. `msgstore.db.crypt15` ist eine reguläre Datei (kein Link). Dann folgen Größe (MiB), Alter (Stunden)
     und die Grenze `--max-mib` (Standard 512). Die Sicherung wird nur per `lstat` angesehen, nie geöffnet.
  5. Schlüsseldatei (Standard `~/.config/agent/wa_sicherung.key`):
     - vorhanden;
     - geschützt: kein Link, reguläre Datei, `st_nlink == 1`, Besitzer = aktueller Nutzer, Rechte genau `600`, nicht im Repo
       (angegebener und aufgelöster Pfad); nicht prüfbar zählt als Verstoß;
     - Form: genau 64 Hex-Zeichen, optional ein Zeilenende (`\n` oder `\r\n`). Der Inhalt wird nur gelesen, sofort verworfen und
       nie ausgegeben. Die Form wird erst geprüft, wenn der Schutz erfüllt ist; sonst steht dort „nicht geprueft“.
  6. Bibliothek: `importlib.util.find_spec("wa_crypt_tools")`, ohne Import. Fehlt sie, steht die Zeile
     „Bibliothek: fehlt - erst fuer Teil B noetig“. Das zählt **nicht** für den Exit-Code. Erst `--fuer-teil-b` macht sie zur Pflicht.
- Ausgabe auf stdout (Beispiel):
  ```
  Python: 3.12 (ok)
  Sicherungsordner: lesbar
  crypt15-Dateien: 2 · crypt14-Dateien: 0
  msgstore.db.crypt15: vorhanden ja · Groesse 180.3 MiB · Alter 7.5 Stunden
  Groesse unter Grenze: ja (Grenze 512 MiB)
  Schluesseldatei: vorhanden ja · Schutz erfuellt ja · Form 64 Hex ja
  Bibliothek: fehlt - erst fuer Teil B noetig
  Vorpruefung Teil A: bestanden
  ```
- Jede fehlende Voraussetzung ist eine feste Zeile auf stderr, danach Exit 3. Die Texte stehen als `M_…`-Konstanten im Werkzeug:
  „kein Zugriff auf die WhatsApp-Sicherung (termux-setup-storage)“, „Sicherung ohne Ende-zu-Ende-Schluessel - in WhatsApp die
  Ende-zu-Ende-Sicherung einschalten“ (nur `.crypt14`), „keine WhatsApp-Sicherung gefunden“, „msgstore.db.crypt15 fehlt“,
  „Sicherung ist groesser als die Grenze (--max-mib)“, „Schluesseldatei fehlt / nicht geschuetzt / hat nicht die Form 64
  Hex-Zeichen / nicht lesbar“, „Python 3.11 oder neuer noetig“, „Bibliothek wa_crypt_tools fehlt (noetig mit --fuer-teil-b)“.
- Im Normalbetrieb wird nichts geschrieben: keine Datei, kein Ordner, keine Temp-Datei.

**`--messprobe`** (`python -B tools/handy/whatsapp_sicherung_pruefen.py --messprobe`)
- Voraussetzungen sind nur Python 3.11 und das Modul `resource` (Linux/Termux). Sicherung, Schlüssel und Bibliothek werden
  weder geöffnet noch aufgelistet. Es gibt nur `os.stat` vorher und nachher als Beleg („Unveraendert: Sicherung ja/nein/nicht
  vorhanden · Schluessel …“).
- Optionen: `--stufen 64,256,512,1024` (Standard; aufsteigende ganze Zahlen 1 bis 4096 MiB, höchstens 8), `--arbeitsordner`
  (Standard `~/foto_sortierung`). Mit `--fuer-teil-b` zusammen ist die Messprobe Exit 2.
- Ablauf: Je Stufe baut das Werkzeug eine erfundene SQLite-Datenbank im Speicher (`:memory:`, etwa 1 KiB je Zeile), serialisiert und packt sie
  (`zlib`), entpackt sie in Blöcken zu 16 MiB und öffnet sie per `deserialize`. Danach laufen vier Abfragen, die Zwischenspeicher
  erzwingen: `ORDER BY` über eine nicht indizierte Spalte, `GROUP BY`, `DISTINCT` und eine Unterabfrage mit `IN (SELECT …)`.
  Das geschieht bei **jeder** Stufe, nicht nur bei der größten (Abweichung vom Plan, siehe unten).
- Ausgabe: `SQLite-Version`, `TEMP_STORE=0 gesetzt: ja/nein`, je Stufe `Stufe N MiB: ok - Hoechststand M MiB` (aus
  `resource.getrusage`, Linux liefert KiB) oder `Stufe N MiB: abgebrochen (Speicher|Fehler)`, dann `Obergrenze`,
  `Zwischendatei: keine`, `TMPDIR-Eintraege: vorher n · nachher n` und `Unveraendert: …`.
  Die Stufenzeilen werden sofort ausgegeben (`flush`). Wird der Prozess vom System beendet, ist die zuletzt gemeldete Stufe die Obergrenze.
- **Einzige Schreibzugriffe:** `os.mkdir(…, 0o700)` für `<Arbeitsordner>/whatsapp/` und `<Arbeitsordner>/whatsapp/messprobe_leer/`,
  und nur, wenn sie fehlen. Es gibt genau eine Stelle dafür im Code. `~/foto_sortierung` selbst muss schon bestehen.
  Fehlt es, ist es eine Datei oder ein Link, endet die Probe mit Exit 3 „Arbeitsordner ~/foto_sortierung fehlt“, ohne jede Anlage.
- **Ordnerregel** (`whatsapp/`, `messprobe_leer/`): echter Ordner (`lstat` + `S_ISDIR`), kein Link, nicht im Repo (angegebener und
  aufgelöster Pfad), keine Hartlink-Prüfung. Verstoß ist Exit 2, ohne `mkdir`. Liegt `~/foto_sortierung` im Repo, ist das ebenfalls Exit 2.
- **Zwischendateien:** `SQLITE_TMPDIR` und `TMPDIR` zeigen für die Probe auf `messprobe_leer/`, das Arbeitsverzeichnis wird dorthin gewechselt
  und danach zurückgesetzt (auch bei Fehlern, per `finally`). Der Probeordner muss vorher leer sein (sonst Exit 3 „Probeordner nicht leer“, keine Probe)
  und nachher leer sein (sonst Exit 3 „SQLite legt Zwischendateien an“; die Datei bleibt liegen, es wird nichts gelöscht).
  Ändert sich die Zahl der Einträge im ursprünglichen `TMPDIR` (Standard `/tmp`, in Termux `$PREFIX/tmp`), ist es Exit 3
  „moeglicherweise Zwischendatei ausserhalb des Probeordners“. Kann der ursprüngliche `TMPDIR` nicht gezählt werden, ist es Exit 3 „TMPDIR nicht pruefbar“. Kann der Probeordner vor der Probe oder nach einer Stufe nicht gezählt werden, ist es Exit 3 „Probeordner nicht pruefbar“: es läuft keine weitere Stufe, und „Zwischendatei: keine“ wird nie ausgegeben.
- **Speicherbetrieb vor jeder Abfrage:** Auf jeder Verbindung laufen zuerst nur PRAGMAs (`temp_store=MEMORY`, `temp_store`, `compile_options`).
  Liefert `temp_store` nicht 2 oder enthalten die Kompilieroptionen `TEMP_STORE=0`, endet die Probe mit Exit 3 „SQLite dieses Geraets kann nicht nur im
  Speicher arbeiten“, ohne Abfrage.
- Bricht eine Stufe mit `MemoryError` oder einem anderen Fehler ab, steht `abgebrochen`, und die Probe endet bei der letzten erfolgreichen Stufe (Exit 0).
  Ist schon die erste Stufe nicht erfolgreich, ist es Exit 1 „Messprobe: keine Stufe erfolgreich“.

### A1 – `tools/whatsapp/aufbau_beleg.py` (PC, Handprüfung)
`python -B tools\whatsapp\aufbau_beleg.py <Pfad zur msgstore.db>`
- Öffnet **nur schreibgeschützt**: `sqlite3.connect("file:" + quote(abs_pfad) + "?mode=ro&immutable=1", uri=True)`, dann `PRAGMA query_only=ON`
  und `PRAGMA temp_store=MEMORY`. Es entstehen keine `-wal`-, `-shm`- oder `-journal`-Dateien. Eine Windows-Adresse wird als `file:/C:/…` angegeben.
- Speicherbetrieb wird vor jeder Tabellenabfrage geprüft (`temp_store` = 2, keine Kompilieroption `TEMP_STORE=0`). Sonst Exit 3
  „SQLite dieses Rechners kann nicht nur im Speicher arbeiten“, ohne Tabellenabfrage (auch `table_info` läuft erst danach).
- Gelesen werden nur die fest im Code vorgegebenen Pflichtspalten von `message`, `chat`, `message_media`, `jid` (W2b.4). Alle anderen Spalten werden
  nur gezählt („weitere Spalten“). Namen, Werte, Nummern, Texte, Pfade und Dateinamen erscheinen nie.
- Die Zählung läuft in Python über die rohen Zeilen (Prüfung mit `type(x) is int/str/bytes`, wie in W2b.4a vorgesehen).
- Ausgabezeilen (jeweils `Name: Schlüssel Zahl · …`):
  - `SQLite-Version`, `Speicherbetrieb: temp_store 2 · TEMP_STORE=0 gesetzt: nein`
  - je Tabelle `Tabelle <t>: Zeilen N · weitere Spalten K` (oder `Tabelle <t>: Tabelle fehlt`), darunter je Pflichtspalte `vorhanden: <t>.<spalte>`
    bzw. `fehlt: <t>.<spalte>`
  - `Typen <t>.<spalte>: int · str · bytes · NULL · sonst` für alle 12 vorhandenen Pflichtfelder
  - `Kennungen <t>.<spalte>: kleiner_gleich_0` (7 Kennungsfelder) und `doppelt` (nur bei den vier eindeutigen:
    `message._id`, `chat._id`, `jid._id`, `message_media.message_row_id`; Zahl der Werte, die mehrfach vorkommen)
  - `Zeit message.timestamp: 10_Stellen · 13_Stellen · sonst · ausserhalb` (ausserhalb = Ganzzahlen außerhalb 01.01.2009 …
    heute + 1 Tag, in Millisekunden gerechnet; NULL und Text sind schon unter `sonst`)
  - `from_me: 0 · 1 · sonst`
  - `file_path: absolut_media · absolut_alt · relativ · leer · sonst` und `Images_Unterordner: Ebene-0 · Sent · Private · sonst · ohne_Images`
    (`Sent` in beliebiger Schreibweise; `ohne_Images` = Pfad, der nicht unter `Media/WhatsApp Images/` liegt)
  - `file_hash: leer · base64_32 · sonst` (`base64_32` = streng gültiges base64 mit genau 32 Bytes)
  - `Verknuepfung: ohne_message · chat_abweichend · chat_fehlt · jid_fehlt` (über `message_media.message_row_id = message._id`;
    `chat_abweichend` zählt auch `NULL` auf einer Seite)
- Fehlt eine Pflichtspalte oder eine Tabelle, steht die „fehlt:“-Zeile da, die davon abhängigen Zeilen entfallen, Exit 0.
- Exit-Codes: 0 ok · 1 Datenbank nicht lesbar oder beschädigt (fester Text, nie der Text der Ausnahme) · 2 Aufruffehler (ohne Echo der Eingabe) ·
  3 kein regulärer Dateipfad (Link, Ordner, fehlt; Text ohne Pfad) oder Speicherbetrieb nicht möglich.

### Gemeinsame Startregel
Beide Werkzeuge beginnen nach dem Modul-Docstring mit `import sys` und unmittelbar darauf `sys.dont_write_bytecode = True`, vor jedem weiteren Import.
Sie sind in sich geschlossen (keine eigenen Module), brauchen nur die Standardbibliothek und verwenden `tempfile` und `shutil` nicht.
In beiden Werkzeugen gibt es kein `os.rename`, kein Löschen (`remove`/`unlink`/`rmdir`/`rmtree`) und kein `raise <Ausnahme>` innerhalb eines `except`
(im `except` wird nur eine Marke gesetzt, die feste Ausnahme folgt danach). Hinweis zur Schreibgrenze (`.pyc`): Das Flag verhindert `.pyc`-Dateien für alles, was **nach** ihm importiert wird.
Der Start als Skript (`python tool.py`, mit und ohne `-B`) und der Import mit `-B` (`python -B -c "import <werkzeug>"`) erzeugen weder `__pycache__` noch `.pyc`.
Nur ein Import **ohne** `-B` (wie in pytest) kann das `.pyc` des Werkzeugs selbst anlegen, weil Python die Datei vor dem Lauf des Moduls übersetzt und das Flag dann noch nicht gesetzt ist.

## Tests
- Neu `backend/tests/test_whatsapp_sicherung_pruefen.py` (96 Tests) und `backend/tests/test_aufbau_beleg.py` (38 Tests), offline, nur erfundene Daten.
- Rechte, Besitzer, Links, Python-Version, `resource` und Repo-Pfade werden mit Attrappen (monkeypatch) nachgestellt. Die Werkzeuge haben dafür dünne Hüllfunktionen
  (`_lstat`, `_ist_link`, `_realpath`, `_aktueller_nutzer`, `_python_version`, `_jetzt`, `_verbinden`). So läuft alles auch unter Windows ohne `skipif`.
- Ein Spy auf alle Schreibwege (`open` mit Schreibmodus, `os.open`, `mkdir`/`makedirs`, `replace`, `rename`, `remove`, `tempfile.*`, `shutil.*`) belegt: im Normalbetrieb 0 Aufrufe;
  in der Messprobe nur die zwei `mkdir`. Er zeigt auch, dass Sicherung und Schlüssel nicht geöffnet und nicht verändert werden (Inhalt und `mtime`).
- Die Tests prüfen unter anderem: jede Voraussetzung einzeln fehlend, Schlüsselschutz (Link, Hartlink, Rechte, Besitzer, Form, Repo), Bibliothek ohne Import,
  die Ordnerregel (Link, Datei, Repo, vorhandene Ordner), den Speicherbetrieb mit Attrappen, TMPDIR-Gegenzählung, Umgebung und Arbeitsverzeichnis nach dem Lauf,
  Abbruch einer Stufe, und beim Strukturbeleg jede Zählklasse mit mindestens einem Fall, keinen Wert in der Ausgabe, Unveränderlichkeit der Datenbank.
- Der AST-Wächter prüft den Kopf (`import sys`, danach `sys.dont_write_bytecode = True`), kein `raise` im `except`, keine Schreib- und Löschwege, nur einen `mkdir`
  und `open` nur mit `"rb"`. Ein Frischer-Prozess-Test (je Werkzeug zusätzlich `test_bytecode_grenze_beide_startarten`: Import mit `-B`, Skriptstart mit und ohne `-B`, jeweils aus einer Kopie in einem leeren Ordner, danach nur die Kopie selbst) startet beide Werkzeuge aus einer Kopie in einem leeren Ordner ohne `-B` und ohne `PYTHONDONTWRITEBYTECODE`;
  danach gibt es kein `__pycache__` und keine neue Datei außer den zwei erlaubten Ordnern. Für `resource` nutzt der Prozesstest eine Attrappe auf `PYTHONPATH` (Windows kennt das Modul nicht).
- Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest tests/test_whatsapp_sicherung_pruefen.py tests/test_aufbau_beleg.py tests/test_whatsapp_bilder_zaehlen.py tests/test_whatsapp_bilder_hochladen.py -q -p no:cacheprovider`
  → **404 passed**, 0 skipped, Exit 0 (die zwei W1-Dateien unverändert grün).
- Nicht am PC prüfbar: der echte Höchststand aus `resource.getrusage` und die echte Wirkung von `SQLITE_TMPDIR` auf Termux-SQLite. Das belegt erst der Handylauf von `--messprobe`.

## Nachbesserung nach der Ergebnisprüfung (Codex, zwei sperrende Befunde)

**Befund 1 – Repo-Schutz des Probeordners.** `ordner_status` suchte `.git` nur im Elternbaum des Ordners. Ein bereits vorhandener
Ordner, der selbst die Repo-Wurzel ist (enthält `.git` als Ordner oder als Datei, z. B. `messprobe_leer/` oder `whatsapp/`),
wurde zugelassen; die Probe lief darin an (Ergebnis damals: Exit 3 „Probeordner nicht leer“ statt der geforderten Exit 2).
- Änderung in `tools/handy/whatsapp_sicherung_pruefen.py`: `_im_repo_einer(pfad, ordner_selbst=False)` und `im_repo(pfad, ordner_selbst=False)`
  prüfen mit `ordner_selbst=True` auch den Pfad selbst auf `.git` (`os.path.exists`, also Ordner und Datei), jeweils für den angegebenen und den
  aufgelösten Pfad. `ordner_status` ruft `im_repo(pfad, ordner_selbst=True)` auf; die Dateiprüfung des Schlüssels bleibt unverändert beim Elternbaum.
  Ein Ordner mit `.git` ergibt Status `repo` und damit Exit 2 (für `~/foto_sortierung`: ebenfalls Exit 2), vor jedem `mkdir`.
- `tools/whatsapp/aufbau_beleg.py` braucht die Prüfung nicht: Es öffnet nur eine einzelne Datei (`datei_pruefen`: regulär, kein Link) schreibgeschützt
  und legt keinen Ordner an; der Plan verlangt dort keinen Repo-Schutz. Keine Änderung.
- Neue Tests (`test_whatsapp_sicherung_pruefen.py`): `test_messprobe_vorhandener_ordner_ist_selbst_repo_wurzel_exit_2` (6 Fälle: `arbeit`/`whatsapp`/`probe`
  × `.git` als Ordner/Datei; Exit 2, kein `mkdir`, kein Schreibweg, `_probe_stufe` 0-mal, Ordnerbaum unverändert),
  `test_ordner_status_erkennt_repo_wurzel_im_ordner_selbst`, `test_dateipruefung_schluessel_bleibt_unveraendert_nur_elternordner`.
  Vor der Reparatur rot: die zwei Fälle `probe` (Exit 3 statt 2) und der Status-Test (`ok` statt `repo`); die Fälle `arbeit`/`whatsapp` waren schon grün,
  aus zwei verschiedenen Gründen: bei `arbeit` fand die Prüfung von `whatsapp/` das `.git` in ihrem Elternordner `foto_sortierung`; bei `whatsapp` fand die Prüfung von `messprobe_leer/` das `.git` in ihrem Elternordner `whatsapp/`. Der Fall `probe` (`.git` im vorhandenen Probeordner selbst) endete vorher mit Exit 3 („Probeordner nicht leer“).

**Befund 2 – Schreib-Spion erst nach dem Import (Testlücke).** Der bisherige Spy wurde erst nach dem Import des Werkzeugs installiert.
Der Code war schon sauber (die neuen Tests waren sofort grün), die Überwachung deckte die Importe aber nicht ab.
- Neu `test_audit_hook_vor_dem_import_messprobe_schreibt_nur_die_zwei_ordner` (2 Fälle: Ordner fehlen / vorhanden) in `test_whatsapp_sicherung_pruefen.py`:
  Ein frischer `python -B`-Prozess setzt `sys.addaudithook` **vor** `import whatsapp_sicherung_pruefen`, importiert das Werkzeug aus einer Kopie und führt
  `--messprobe` (Stufen 1,2, erfundene Pfade im temporären Verzeichnis, `resource`-Attrappe) aus. Ereignisse: `open` mit Schreibmodus oder Schreib-Flags,
  `os.mkdir`, `os.rename`, `os.remove`, `os.rmdir`, `os.symlink`, `os.link`, `os.truncate`, `os.chmod`, `os.chown`, `os.utime`, `os.mkfifo`, `tempfile.mkstemp`,
  `tempfile.mkdtemp`, alle `shutil.*`, `sqlite3.connect`. Der Kindprozess gibt JSON aus. Geprüft: 0 Schreibereignisse, 0 sonstige Schreibwege, `os.mkdir` nur auf `whatsapp/`
  und `messprobe_leer/` (bzw. keiner, wenn vorhanden), `sqlite3.connect` nur `:memory:`, `sys.dont_write_bytecode` gesetzt, Kopie ohne `__pycache__`.
  Gegenprobe `test_audit_hook_gegenprobe_erkennt_schreibzugriffe`: derselbe Hook meldet in einem Kindprozess echte `mkdir`/`open("w")`/`os.open`/`rename`-Aufrufe.
- Für `aufbau_beleg.py` (Plan verlangt dort keinen Spy, ergänzt zur Konsistenz): `test_audit_hook_vor_dem_import_strukturbeleg_schreibt_nichts` mit gleichem Aufbau;
  0 Schreib-/mkdir-/sonstige Ereignisse, genau ein `sqlite3.connect` mit `mode=ro` und `immutable=1`, Datenbank byteweise und per `mtime_ns` unverändert, keine Nebendateien.
- Die bisherigen Spy-Tests (`SchreibSpy` nach dem Import) bleiben als Ergänzung bestehen.

**Testzahlen nach der Nachbesserung:** `test_whatsapp_sicherung_pruefen.py` 96 → 107 Tests (+6 Repo-Fälle, +2 Repo-Einzeltests, +2 Audit-Hook-Fälle, +1 Gegenprobe),
`test_aufbau_beleg.py` 38 → 39 Tests. Prüfbefehl (derselbe wie im Abschnitt „Tests“) → **416 passed**, 0 skipped, Exit 0 (vorher 404; die zwei W1-Dateien unverändert grün).

## Abweichungen und Auslegungen
- Meldungen sind ASCII statt mit Umlauten, wie bei W1.
- Die Zwischendatei-Abfragen laufen bei jeder Stufe, nicht nur bei der größten (strenger, kostet nur Zeit).
- `~/foto_sortierung` als Link oder Datei ist Exit 3 (Plan: „muss bestehen und ein echter Ordner sein, sonst Exit 3“). Liegt es im Repo, ist es Exit 2.
- Ein nicht zählbares ursprüngliches `TMPDIR` und ein nicht zählbarer Probeordner (vor der Probe oder nach einer Stufe) sind Exit 3 (vorsichtig, je mit eigener fester Zeile). Ist `TMPDIR` nicht gesetzt, wird `/tmp` gezählt.
- Ist das Kennungsfeld kein Eindeutigkeitsfeld (`chat_row_id`, `sender_jid_row_id`), steht nur `kleiner_gleich_0`, keine Doppelten.
- `msgstore*.crypt15`/`.crypt14` werden nur nach Namen gezählt; als „vorhanden“ gilt `msgstore.db.crypt15` nur als reguläre Datei (kein Link, kein Ordner).

## Befehle für Sebastian
```text
# Termux, im Projektordner personal_ai_agent
python -B tools/handy/whatsapp_sicherung_pruefen.py
python -B tools/handy/whatsapp_sicherung_pruefen.py --messprobe
```
```powershell
# PowerShell am PC
python -B tools\whatsapp\aufbau_beleg.py <Pfad zur entschluesselten msgstore.db>
```
Die Ausgaben bestehen nur aus Zahlen und festen Namen und gehen an Claude zurück. Sie sind die Eingabe für Teil B.
