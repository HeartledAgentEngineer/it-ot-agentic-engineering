# N18 — Lösch-Werkzeug für Duplikate (`pcloud_duplikate_loeschen.py`)

**Datum:** 28.09.2026 · **Plan:** `docs/plan-nachtlauf-2026-09-26.md`, Schritt N18 ·
**Feinauftrag:** `docs/auftrag-n18-duplikate-loeschen.md`

## Was gebaut wurde

`tools/pcloud/pcloud_duplikate_loeschen.py` (**1.226 Zeilen**) legt die
Lösch-Kandidaten aus dem Duplikate-Bericht in den pCloud-**Papierkorb** — die
Kopien im Upload-Baum `Automatic Upload`, nie die Sammlung. **Trockenlauf ist
der Standard**; erst `--wirklich` schaltet das Löschen frei.

Tests: `backend/tests/test_pcloud_duplikate_loeschen.py` (**1.173 Zeilen**,
**64 Testfunktionen**, **206 `assert`-Prüfungen**), alles offline mit
`tmp_path` und API-Attrappen — kein Netz, keine echten Kontokennungen, keine
Kennung/Namen aus dem echten Bericht.

Der Bericht von `pcloud_duplikate.py` bleibt **streng nur lesend** und wurde
nicht angefasst; gebucht wird ausschließlich über die bestehende Funktion
`manifest_anhaengen` aus `pcloud_bewegungen.py` (keine zweite Manifest-Logik).
In `pcloud_bewegungen.py` ist dafür **eine** Zeile dazugekommen: die Manifest-Art
`"loeschen"` steht jetzt in `ERLAUBTE_ARTEN` (samt Docstring-Zeile) — Begründung
im Abschnitt „Abweichung vom Auftrag“ unten.

## Schnittstelle (wie im Feinauftrag, eingefroren)

```
cd backend
.venv/Scripts/python ../tools/pcloud/pcloud_duplikate_loeschen.py [Schalter]
```

`--bericht PFAD` (Standard `~/foto_sortierung/duplikate.json`, Umgebungsvariable
`PCLOUD_DUPLIKATE_ZIEL`) · `--wirklich` · `--nur-dateien PFAD` · `--art
ueber_baeume|innerhalb_upload|alle` · `--grenze N` (Standard 25, geklemmt
1…200) · `--manifest PFAD` · `--papierkorb` (im Trockenlauf zusätzlich
`trash_list` **lesend** und die Zahl der Papierkorb-Einträge) · `--beispiele N`
(Standard 5).

Rückgabewerte: **0** = Trockenlauf gelaufen bzw. Löschungen vollständig gebucht ·
**2** = Bedien-/Konfigurationsfehler, Schutzverletzung oder Abbruch.

Reine, ohne Netz prüfbare Funktionen (Namen wie im Auftrag):
`kandidaten_waehlen(bericht, art, nur_dateien, grenze)` ·
`pruefe_kandidat(kandidat, bericht_seite)` · `manifest_zeile(kandidat, zeit)` ·
`freigabe_mb(kandidaten)` · `rueckweg_text()`. Dazu im Werkzeug:
`bericht_laden`, `kennungen_aus_datei`, `ordner_eintraege`, `papierkorb_zahl`,
`LivePruefer`, `manifest_ort_pruefen`, `schon_geloescht`, `manifest_buchen`,
`fuehre_aus`, `trocken_zeilen`, `ergebnis_zeilen`, `main`.

## Regeln (Kurzform, jede in den Tests einzeln belegt)

1. **Trockenlauf ist der Standard:** ohne `--wirklich` geht **kein** `deletefile`
   ab (Test mit Stolperfalle: kein einziger Netz-Aufruf).
2. **Nur Kopien im Baum `upload`.** Ein Kandidat aus der Sammlung wird
   verweigert — auch über `--nur-dateien` (deutsche Meldung, Exit 2, nichts
   geschrieben).
3. **Frische Gegenprobe vor jedem Löschen:** Größe **und** Prüfsumme werden
   unmittelbar vorher live per `listfolder` neu gelesen (Weg des Berichts vom
   Baum-Ordner nach unten, Datei über `fileid`). Abweichung oder „nicht mehr
   auffindbar“ ⇒ **Abbruch des ganzen Laufs**, Exit 2, kein weiteres Löschen,
   **keine** Manifest-Zeile für den abweichenden Eintrag (bereits erfolgte
   Buchungen bleiben).
4. **Manifest-Pflicht:** der Manifest-**Ort** wird geprüft, **bevor** die erste
   Datei angefasst wird; jede Löschung erzeugt **sofort** ihre Zeile (`art:
   "loeschen"`, `fileid`, `name`, `pfad`, `size`, `hash`, `zeit`) — nicht am
   Ende gesammelt. Ein Pfad im Git-Repo wird verweigert (Exit 2, nichts
   gelöscht). Ein unlesbares Manifest hält den Lauf an.
5. **Rückholbarkeit im Klartext:** Konsole und Doku nennen den Rückweg
   (`trash_list` zeigt, `trash_restore` legt zurück). `trash_restore` wird
   **nie** aufgerufen, ganzen Ordner werden **nie** entfernt.
6. **Positivliste:** `("listfolder", "deletefile", "trash_list")`. Ein Test
   prüft die Liste **und** per AST, dass im Quelltext jeder gesendete
   Methodenname ein fester Text aus dieser Liste ist.
7. **Grenze je Lauf:** Standard 25, hart geklemmt 1…200; die Restzahl wird
   ehrlich genannt (Test: 30 Kandidaten, `--grenze 25` ⇒ genau 25 Löschungen,
   `Rest 5`).
8. **Idempotent:** was im Manifest schon als `loeschen` gebucht ist, wird
   übersprungen — zweiter Lauf am selben Stand: `geloescht 0`, **keine** neue
   Zeile, Exit 0, kein einziger Netz-Aufruf.
9. **Keine Geheimnisse:** der Token wird nie ausgegeben/geloggt und steht in
   keiner geschriebenen Datei; Anbieter-Fehlertexte werden über
   `_ohne_geheimnis` bereinigt (Test mit erfundenem Token in Ausgabe, Manifest
   und Fehlertext).
10. **Nichts anderes:** kein Verschieben, kein Umbenennen, kein Kopieren, kein
    Download, kein Vorschaubild, kein Entfernen ganzer Ordner — zusätzlich per
    Quelltext-Suchtest belegt.

## Prüfung (eigene Läufe, 28.09.2026)

* **Prüfbefehl selbst gefahren (Planer, nach beiden Korrekturen):**
  `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  → **2070 passed, 3 warnings, Exit 0** in 128,6 s.
  **Baseline des Auftrags: 2006 passed** (28.09.2026, N13c). Die Differenz
  **+64** sind **genau** die neuen Prüfungen dieses Schritts (aus der fremden
  Parallelarbeit im selben Arbeitsbaum kam in diesem Lauf keine zusätzliche
  Zahl hinzu). Erster Lauf des Ausführers: 2068 passed, Exit 0.
* Nur die neue Datei: `pytest tests/test_pcloud_duplikate_loeschen.py -q`
  → **64 passed, Exit 0**.
* **Live-Trockenlauf gegen den echten Bericht** (nur lesend, Planer):
  `… --beispiele 3` → Exit 0, **25 geprüfte Kandidaten, 0 gelöscht,
  3.970,66 MB**, **Rest 2.108**; Konsole unübersehbar im Modus `TROCKENLAUF`;
  `… --papierkorb --grenze 1` → **1.836 Papierkorb-Einträge nur gelesen**,
  nichts zurückgelegt. Der Bericht ist **byte-gleich** geblieben
  (`md5 ba9ed672d3dd7b0de5b898162e4d8923`), `~/foto_sortierung/manifest.jsonl`
  **existiert nicht** — es wurde nichts gebucht.

### Prüfer-Runde 1 (`openai/gpt-5.6-luna`, frischer Kontext): NICHT BESTANDEN

Er hat den Prüfbefehl selbst gefahren (**2068 / Exit 0**, neue Datei 62 / Exit 0)
und bestätigt: Trockenlauf sendet nichts, Ausgabe ohne Token, `grep -nE
"[0-9]{11}"` über die vier Dateien **0 Treffer**, die Positivliste der
API-Methoden in `pcloud_bewegungen.py` unverändert
(`createfolder, renamefile, renamefolder, listfolder`), Sammlungsschutz-Test
grün, `manifest.jsonl` fehlt zu Recht. **Zwei Abweichungen, beide berechtigt:**

1. **Die Gegenprobe war nicht überall frisch.** Der `LivePruefer` hielt
   Ordnerinhalte in einem Zwischenspeicher — für zwei Kandidaten im **selben**
   Ordner kam der zweite Stand aus dem Cache. Damit war die Zusage
   „frische Gegenprobe vor **jeder** Löschung“ im Code **unwahr**. Behoben: der
   Zwischenspeicher ist entfernt, **jede** Gegenprobe liest die Ordner frisch
   (je Kandidat **ein** `listfolder` pro Ordner auf dem Weg vom Baum-Ordner bis
   zur Datei — bei Pfaden direkt im Baum-Ordner sind das **zwei** Aufrufe, bei
   tieferen Pfaden entsprechend mehr; eine Obergrenze „immer zwei“ gilt **nicht**).
   Zwei neue Tests nageln es fest: zwei Kandidaten im selben
   Ordner ergeben **zwei** `listfolder`-Aufrufe, und eine **zwischen zwei
   Kandidaten geänderte Prüfsumme** lässt den Lauf anhalten (mit Cache wäre die
   Änderung unsichtbar und die zweite Datei trotzdem gelöscht worden).
2. **Falsche Zeilenzahl im Changelog** (1.229 statt 1.226) — korrigiert, samt
   Testdatei (1.173), Testfunktionen (64) und `assert`-Prüfungen (206).

### Prüfer-Runde 3 (`openai/gpt-5.6-luna`, frische Sitzung, Abnahme auf dem Commit `cc32997`): BESTANDEN, 0 Abweichungen

Er hat selbst gefahren: Prüfbefehl **2070 / Exit 0**; `git show --stat cc32997` =
**genau die sechs** genannten Dateien, **keine** fremde; `0 0` gegen `origin/main`;
den Live-Trockenlauf (Exit 0, **25 / 0 / 3.970,66 MB / Rest 2.108**, Modus
`TROCKENLAUF`); Bericht-md5 unverändert, `manifest.jsonl` **nicht vorhanden**; die
Zahlen nachgerechnet (1.226 / 1.173 / 64 / 206 / +64); die API-Positivliste des
Nachbarmoduls unverändert; im neuen Werkzeug **keine** Ordner-Löschung, kein
Verschieben/Umbenennen, kein Download, `trash_restore` nur als manueller Rückweg
erwähnt (nie aufgerufen); keine 11-stelligen Kennungen und kein Token in den neuen
Zeilen; die Plandatei trägt N18 mit Zahlen und behauptet **keinen** echten
Löschlauf. Sein einziger Restpunkt: die unfertige **Parallelarbeit eines zweiten
Agenten** im Arbeitsbaum — ausdrücklich **nicht** Teil dieses Commits (dasselbe
Muster wie bei N6e und N13b: fremder Bestand ist kein Schritt-Fehler).

## Abweichung vom Auftrag (eine Stelle, vom Planer entschieden)

Der Auftrag verlangt in §3.4 eine Manifest-Zeile mit `art: "loeschen"` **über
die bestehende Funktion** `manifest_anhaengen` — und verbot in §2 zunächst,
`tools/pcloud/pcloud_bewegungen.py` anzufassen. Das passt nicht zusammen:
`manifest_anhaengen` prüft die Art gegen seine Positivliste
`ERLAUBTE_ARTEN = ("movefile", "movefolder", "createfolder", "rueckroll")`
und wies `"loeschen"` mit *„Unbekannte Manifest-Art“* ab (in den Tests
nachgeprüft).

Der Ausführer hat das zuerst **im Lösch-Werkzeug** gelöst: es trug die Art beim
Import in die fremde Konstante nach (`bewegen.ERLAUBTE_ARTEN = tuple(…) +
("loeschen",)`). **Der Planer hat das ersetzt** — eine Laufzeit-Änderung an
einer fremden Konstanten ist von der Importreihenfolge abhängig und für den
Leser unsichtbar.

Gewählter Weg (sichtbar statt heimlich):

* `ERLAUBTE_ARTEN` in `pcloud_bewegungen.py` trägt `"loeschen"` jetzt
  **ausdrücklich** (ein Eintrag, zwei Zeilen Kommentar, Docstring-Zeile
  mitgezogen). Damit ist die Art Teil der einen Manifest-Wahrheit.
* Das Lösch-Werkzeug bucht weiterhin ausschließlich über `manifest_anhaengen` —
  **eine** Manifest-Logik, **keine** zweite. Es verändert kein fremdes Modul.
* Ein Test hält das fest: `MANIFEST_ART in pcloud_bewegungen.ERLAUBTE_ARTEN`.
* `pcloud_rueckrollen.py` bleibt unberührt: `"loeschen"` steht nicht in
  `AKTIONS_ARTEN`, wird in der Zählung nicht als Rückrollung geführt und ändert
  nichts am Offen-Status der Verschiebungen.
* Die Auftragsdatei wurde entsprechend korrigiert (§3.4). Die eingefrorene
  **Schnittstelle** (Schalter, Rückgabewerte, Funktionsnamen, Exit-Codes) ist
  unverändert geblieben.

Die Alternativen wären schlechter gewesen: die geforderte Art still in eine
bereits erlaubte (z. B. `movefile`) umzubenennen, hieße, eine Löschung als
Verschiebung ins Manifest zu schreiben — `pcloud_rueckrollen.py` würde dann
versuchen, sie „zurückzufahren“.

## Zahlen und Offenes

* **Kein echter Löschlauf** (auch nicht probeweise): er bleibt gesperrt, bis der
  Nutzer ihn ausdrücklich freigibt. **Gelaufen ist der Trockenlauf** (Standard)
  — der verändert nichts. Zahlen aus Offline-Tests und Zahlen aus dem
  Live-Trockenlauf sind im Abschnitt „Prüfung“ getrennt benannt.
* Der **Ausführer** hat den Bericht (`~/foto_sortierung/duplikate.json`) nicht
  gelesen und **nicht** als Testdaten verwendet; in seinen Tests stehen nur
  erfundene Kennungen und Namen, im Werkzeug der Standardpfad als Zeichenkette.
  Gelesen wurde der Bericht ausschließlich im **Live-Trockenlauf des Planers**
  (nur lesend, ohne Netz-Schreibweg). Keine Kennung, kein Name und keine Größe
  aus dem echten Bericht steht in Repo-Dateien; die Konsole nennt Namen, weil
  der Nutzer sonst nicht wüsste, was gelöscht würde.
* Der Rückweg steht im Klartext auf der Konsole (`rueckweg_text()`).
* Berührt wurden nur: dieses Werkzeug, seine Tests, diese Changelog-Datei und
  der Korrektur-Hinweis im Feinauftrag. Keine `git`-Befehle.
