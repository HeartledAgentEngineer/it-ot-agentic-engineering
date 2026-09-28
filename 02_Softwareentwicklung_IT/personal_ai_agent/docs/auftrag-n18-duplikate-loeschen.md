# Feinauftrag N18 — Duplikate löschen (Werkzeug, Trockenlauf ist der Standard)

> **Auftraggeber:** Planer-Kontext des Nachtlaufs · **Datum:** 28.09.2026
> **Vorgänger:** `tools/pcloud/pcloud_duplikate.py` (Bericht, **nur lesend**) —
> dieser liefert die Kandidatenliste, gelöscht hat bisher **nichts**.
> **Dieser Schritt baut ausschließlich das Lösch-Werkzeug.** Der **erste echte
> Löschlauf ist NICHT Teil dieses Auftrags** und bleibt gesperrt, bis der Nutzer
> ihn ausdrücklich freigibt (Plan N18: „Die `upload`-Stufe (17,5 GB) bleibt
> gesperrt, bis … ausdrücklich freigibt").

## 1. Warum es dieses Werkzeug braucht (Befund, belegt)

`docs/abschlussbericht-nachtlauf-2026-09-26.md` (Abschnitt „offene/gesperrte
Punkte"), wörtlich: der zugehörige Lösch-Schritt „war als Plan-Schritt notiert —
**gebaut wurde er nicht**". Der Bericht vom 27.09.2026
(`~/foto_sortierung/duplikate.json`, 3.545.330 Bytes) nennt **2.133
Lösch-Kandidaten**, alle im Baum `upload` (`Automatic Upload`) —
**7.616** Dateien davon wurden in N13a gegengeprüft; **17,5 GB** Freigabe
(Summe `mb_freigabe_kandidaten` = 17.465,7 MB). Ohne Werkzeug bleibt diese
Freigabe liegen.

## 2. Dateien (genau diese, nichts anderes)

| Datei | Inhalt |
|---|---|
| `tools/pcloud/pcloud_duplikate_loeschen.py` | **neu:** das Werkzeug |
| `backend/tests/test_pcloud_duplikate_loeschen.py` | **neu:** Offline-Tests (siehe §6) |
| `docs/changelog-2026-09-28-n18-duplikate-loeschen.md` | **neu:** Doku zum Werkzeug |
| `docs/auftrag-n18-duplikate-loeschen.md` | **vorhanden** (dieser Auftrag) — nur ändern, wenn der Auftrag selbst falsch war, dann die Änderung im Changelog begründen |

**Nicht** anzufassen: `pcloud_duplikate.py` (bleibt streng nur lesend),
`pcloud_bewegungen.py`, `pcloud_rueckrollen.py`, die Plan-Datei
`docs/plan-nachtlauf-2026-09-26.md` (die pflegt der Planer), `CLAUDE.md`, Projekt-
`README.md`, `frontend/*`, alles unter `backend/app/`.

## 3. Harte Regeln (Sicherheitsnetz — jede einzeln testbar)

1. **Trockenlauf ist der Standard.** Ohne den Schalter `--wirklich` wird
   **keine** schreibende API-Methode gesendet. Ein Test beweist, dass im
   Trockenlauf **kein** `deletefile` abgeht.
2. **Nur Kopien im Baum `upload`.** Ein Kandidat aus der Sammlung
   (`Bilder & Videos`) wird **verweigert** — auch dann, wenn er über
   `--nur-dateien` ausdrücklich genannt wird (deutsche Meldung, Exit 2,
   nichts geschrieben). Ein Test deckt genau diesen Fall ab.
3. **Frische Gegenprobe vor jedem Löschen:** Größe **und** pCloud-Prüfsumme
   (`size` **und** `hash`) der Datei werden unmittelbar vor dem Löschen neu
   gelesen und gegen den Bericht verglichen. Abweichung (oder Datei nicht mehr
   auffindbar) ⇒ **Abbruch des ganzen Laufs**, deutsche Meldung, Exit 2,
   **kein** Löschen, **keine** Manifest-Zeile für den abweichenden Eintrag.
   Es wird **nicht** geraten und **nicht** „trotzdem“ gelöscht.
4. **Manifest-Pflicht:** jede Löschung erzeugt **eine** Zeile im Manifest
   (`art: "loeschen"`, `fileid`, `name`, `pfad`, `size`, `hash`, `zeit`) über
   die **bestehende** Funktion `manifest_anhaengen` aus
   `tools/pcloud/pcloud_bewegungen.py` — keine zweite Manifest-Logik. Standard
   `~/foto_sortierung/manifest.jsonl`; ein Pfad **im Git-Repo** wird verweigert
   (dieselbe Prüfung wie im Nachbarmodul).

   > **Korrektur 28.09.2026 (Planer, nachgemessen):** `manifest_anhaengen` prüft
   > die Art gegen seine Positivliste und wies `"loeschen"` als *unbekannte Art*
   > ab. Statt die Art im Lösch-Werkzeug heimlich beim Import nachzutragen, steht
   > sie jetzt **ausdrücklich** in `pcloud_bewegungen.ERLAUBTE_ARTEN` (ein
   > Eintrag, samt Docstring-Zeile und Begründung) — eine bewusste, sichtbare
   > Erweiterung des bestandsführenden Manifests, geprüft durch einen eigenen
   > Test. Eine Laufzeit-Änderung an einer fremden Konstanten wäre von der
   > Importreihenfolge abhängig und damit unsichtbar. Ferner gilt zusätzlich: der
   > Manifest-**Ort** ist vor der ersten Löschung zu prüfen und eine unlesbare
   > Manifestdatei hält den Lauf an — sonst könnte eine Löschung ohne mögliche
   > Buchung passieren (Umsetzung siehe Changelog
   > `docs/changelog-2026-09-28-n18-duplikate-loeschen.md`).
5. **Rückholbarkeit vor der Operation beantworten.** Das Werkzeug nennt in
   Konsole und Changelog den Rückweg im Klartext: pCloud legt gelöschte Dateien
   in den **Papierkorb**; zurückgeholt wird über `trash_list` (anzeigen) und
   `trash_restore` (zurücklegen) — **nur lesend** darf `trash_list` im Trockenlauf
   aufgerufen werden, um den Papierkorb zu **belegen** (Zahl der Einträge). Es
   wird **kein** `trash_restore` implementiert und **kein** `deletefolder`.
6. **Positivliste der API-Methoden** wie im Nachbarmodul, hier:
   `("listfolder", "deletefile", "trash_list")` — `deletefolder` ist **nicht**
   dabei. Ein Test prüft die Positivliste **und** dass kein anderer Methodenname
   im Modul vorkommt.
7. **Grenze je Lauf:** `--grenze` (Standard **25**, hart geklemmt auf 1…200) —
   mehr wird nicht gelöscht, auch wenn mehr Kandidaten da sind; die Restzahl
   wird ehrlich genannt.
8. **Idempotent:** ein zweiter Lauf am selben Stand hat **nichts** zu tun
   (`geloescht: 0`), schreibt **keine** Manifest-Zeile und endet Exit 0.
9. **Keine Geheimnisse:** der Token wird nie ausgegeben, nie geloggt, steht in
   keiner geschriebenen Datei. Fehlermeldungen des Anbieters werden wie im
   Nachbarmodul durch `_ohne_geheimnis` (bzw. eine gleichwertige lokale
   Funktion) bereinigt.
10. **Nichts anderes wird gelöscht oder verschoben:** keine `movefile`-Aufrufe,
    kein `deletefolder`, kein Download, kein Vorschaubild.

## 4. Schnittstelle (eingefroren — der Prüfer prüft dagegen)

```
cd backend
.venv/Scripts/python ../tools/pcloud/pcloud_duplikate_loeschen.py [Schalter]
```

| Schalter | Bedeutung |
|---|---|
| `--bericht PFAD` | Berichtsdatei (Standard `~/foto_sortierung/duplikate.json`, Umgebungsvariable `PCLOUD_DUPLIKATE_ZIEL` wie im Nachbarmodul) |
| `--wirklich` | **schaltet das Löschen frei**; ohne ihn reiner Trockenlauf |
| `--nur-dateien PFAD` | Textdatei mit **einer Dateikennung je Zeile** (Zahlen, `#`-Kommentar erlaubt) — engt den Lauf auf genau diese Kennungen ein (für spätere Teilfreigaben); Kennungen, die nicht im Bericht stehen, werden **verweigert** (Exit 2) |
| `--art ART` | `ueber_baeume` \| `innerhalb_upload` \| `alle` (Standard `alle` innerhalb des Upload-Baums); andere Werte ⇒ deutsche Meldung, Exit 2 |
| `--grenze N` | höchstens N Löschungen (Standard 25, geklemmt 1…200) |
| `--manifest PFAD` | Manifestdatei (Standard `~/foto_sortierung/manifest.jsonl`) |
| `--papierkorb` | im Trockenlauf zusätzlich `trash_list` **lesend** aufrufen und die Zahl der Papierkorb-Einträge nennen |
| `--beispiele N` | wie viele Kandidaten die Konsole nennt (Standard 5) |

**Konsolenausgabe (Klartext, Deutsch, Zahlen zuerst):** Bericht-Stand, Zahl der
geprüften Kandidaten, Zahl der Löschungen, freigegebene MB, die ersten
`--beispiele` Kandidaten (Name + Pfad), die Restzahl, der Modus
(`TROCKENLAUF` / `WIRKLICH`) unübersehbar, und der Rückweg im Klartext.

**Rückgabewerte:** `0` = Trockenlauf gelaufen bzw. Löschungen vollständig
gebucht · `2` = Bedien-/Konfigurationsfehler, Schutzverletzung oder Abbruch
(kein Löschen ohne Manifest, kein Löschen bei Abweichung).

**Reine, ohne Netz prüfbare Funktionen** (Namen sind Vorgabe, weil der Prüfer
sie aufruft):

* `kandidaten_waehlen(bericht, art="alle", nur_dateien=None, grenze=25)` →
  `{"kandidaten": [...], "uebersprungen": [...], "verweigert": [...], "rest": n}`
* `pruefe_kandidat(kandidat, bericht_seite)"` →
  `{"ok": bool, "grund": str}` — vergleicht `size` **und** `hash`
* `manifest_zeile(kandidat, zeit)` → Dict mit genau den Feldern aus §3.4
* `freigabe_mb(kandidaten)` → Zahl (zwei Nachkommastellen)
* `rueckweg_text()` → deutscher Satz mit Papierkorb + `trash_restore`

## 5. Verhalten (Ablauf, in dieser Reihenfolge)

1. Bericht laden; fehlt sie oder ist sie unlesbar ⇒ deutsche Meldung, Exit 2.
2. Kandidaten wählen (§4). Gibt es **keine** ⇒ `geloescht: 0`, Exit 0, ehrliche
   Meldung („nichts zu tun“).
3. Im Trockenlauf: Kandidatenliste + MB ausgeben, **nichts** senden.
   Mit `--wirklich`: je Kandidat frisch gegenprüfen (§3.3), dann `deletefile`,
   dann **sofort** die Manifest-Zeile schreiben (nicht am Ende gesammelt — ein
   Absturz darf keine gelöschte Datei ohne Manifest-Zeile hinterlassen).
4. Abschlusszeile mit Zahlen: geprüft, gelöscht, MB, Fehler, Restzahl.

## 6. Tests (`backend/tests/test_pcloud_duplikate_loeschen.py`)

**Alles offline** (`tmp_path`, Attrappen für die API, **kein** Netz, **keine**
echten Kontodaten, **keine** echten Datei-/Ordnernamen Dritter, keine Kennungen
aus dem echten Bericht). Mindestens **40** Prüfungen, darunter zwingend:

* Trockenlauf sendet **kein** `deletefile` (der Attrappen-Sender protokolliert
  die Methodennamen; erwartet wird nur `listfolder` bzw. leer).
* `--wirklich` + Gegenprobe stimmt ⇒ `deletefile` **und** genau eine
  Manifest-Zeile je Datei mit vollständigen Feldern.
* `--wirklich` + abweichende Größe **oder** abweichender Hash ⇒ **kein**
  `deletefile`, **keine** Manifest-Zeile, Exit 2, deutsche Meldung.
* Sammlungs-Kandidat (auch per `--nur-dateien`) ⇒ verweigert, Exit 2.
* `--nur-dateien` mit unbekannter Kennung ⇒ verweigert, Exit 2.
* Grenze: 30 Kandidaten, `--grenze 25` ⇒ genau 25 Löschungen, `rest` = 5.
* Zweiter Lauf ⇒ 0 Löschungen, 0 neue Manifest-Zeilen, Exit 0.
* Manifest-Pfad im Repo ⇒ verweigert, Exit 2.
* Kein `deletefolder`, kein `movefile`, keine Download-/Thumbnail-Funktion im
  Modul (Suchtest über den Quelltext).
* Jede Zeile des Manifests ist **anhängend** (bestehende Zeilen bleiben
  unverändert — vorher/nachher vergleichen).
* Kein Token in Ausgabe oder Fehlermeldung (Attrappe mit erfundenem Token,
  Ausgabe und Dateien darauf prüfen).

## 7. Prüfbefehl (vom Ausführer **selbst** auszuführen und zu berichten)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
```
Erwartet: **Exit 0**, Zahl **größer** als die Baseline. Baseline zum
Auftragszeitpunkt: **2006 passed** (28.09.2026, N13c) — die Zahl wächst durch
fremde Parallelarbeit im selben Arbeitsbaum; **die eigenen neuen Prüfungen
müssen zusätzlich** sichtbar sein.

## 8. Was der Ausführer **nicht** tut

* **keine git-Befehle** (kein add, commit, push, checkout) — der Planer committet
* **kein echter Löschlauf** — auch nicht „probeweise mit `--wirklich`“ an einer
  Datei; der Live-Trockenlauf gegen den echten Bericht ist Sache des Planers
* kein Anfassen fremder Dateien im Arbeitsbaum (dort arbeitet ein zweiter Agent:
  `tools/whatsapp/`, `backend/scripts/whatsapp_db_import.py`,
  `backend/scripts/archiv_index_ergaenzen.py`, `README.md`, `CLAUDE.md`)
* keine neuen Abhängigkeiten (nur Standardbibliothek + `httpx`, wie die Nachbarn)
* keine Bilder, keine Archive, keine `.env`-Werte in Ausgaben, Tests oder Doku
