# Nachweis: die Rückholbarkeit der pCloud-Operationen (12.10.2026)

## Warum

Der Nachweis (`tools/foto_sortierung/bestand_pruefen.py`) zählt inzwischen jede
Stufe der Foto-Kette selbst nach und seit dem 10.10. auch die Übergabe ans
Gerät (Manifest, Listen, Wege) und das Chat-Archiv. **Eine Stufe fehlte weiter
ganz: das Manifest der schreibenden Operationen auf dem fremden System pCloud**
(`~/foto_sortierung/manifest.jsonl`, außerhalb des Repos).

Es ist die einzige Antwort auf die Frage „wie mache ich das rückgängig?".
`AGENTS.md`, Abschnitt „Dauerlauf / Nachtarbeit", Punkt 5 verlangt sie
ausdrücklich:

> **Rückholbarkeit ist Pflicht.** Jede schreibende Operation auf einem fremden
> System kommt in ein **Manifest** (Quelle → Ziel, Zeit, Kennung), damit sie
> zurückgenommen werden kann. „Wie mache ich das rückgängig?" wird **vor** der
> Operation beantwortet, nicht danach.

In der Nacht zum 10.10. wurde genau so gearbeitet (32 Archive auf pCloud
entpackt, Ordner angelegt, 79 Buchungen) — in einer Prüfzeile stand das nie.
Fällt das Manifest weg oder ist es halb, ist keine dieser Operationen mehr
nachvollziehbar, und niemand merkt es.

## Was jetzt gemessen wird

Neuer Abschnitt **„pCloud-Operationen (Rückholbarkeit)"** mit dem werfreien
Leser `bewegungen_lesen(pfad)`:

* Buchungen, nicht lesbare Zeilen, Buchungen **ohne Art**, **ohne Ziel**
  (kein `nach_folderid`/`nach_pfad` — dann gibt es nichts zurückzufahren) und
  **doppelte** Buchungen (ein Rückroll-Lauf würde sie zweimal fahren),
* die **Arten** (technische Op-Namen) als Zahlen,
* **ehrlich getrennt, was wirklich rückholbar ist** — das ist der Kern:
  * `movefile` / `movefolder` = **zurückfahrbar** (`BEWEGUNG_ZURUECKFAHRBAR`),
  * `createfolder` = vom Rückroll-Werkzeug **nur gemeldet**, nicht entfernt
    (dessen Docstring sagt das ausdrücklich: „Angelegte Ordner werden NICHT
    entfernt"),
  * alles Übrige (z. B. `extractarchive`, `loeschen`) = **ohne Rückroll-Regel**,
  * eine Buchung `rueckroll` ist der Beleg, dass zurückgefahren wurde,
* Zeitspanne in Tagen.

`kaputt`, `ohne_art`, `ohne_ziel` und `doppelt` werden zu **Lücken**. Eine Art
ohne Rückroll-Regel ist eine **Zeile**, keine Lücke — das Werkzeug verhält sich
dort wie dokumentiert, eine Lücke wäre ein Dauer-Fehlalarm.

## Der Wächter gegen das Auseinanderdriften

Die Prüfzeile kennt die Arten nur, wenn sie dieselben sind wie die des
Werkzeugs `tools/pcloud/pcloud_rueckrollen.py` (`AKTIONS_ARTEN`). Der Test
`test_bewegungen_leser_wirft_nie_und_arten_spiegeln_das_rueckrollwerkzeug`
liest die Konstante **per AST** aus dem Werkzeug und hält beide zusammen —
sonst meldete der Nachweis stillschweigend eine falsche Rückholbarkeit.

## Belege (frisch ausgeführt)

* Testdatei `backend/tests/test_bestand_und_handy_uebergabe.py` **79 → 83
  Testfunktionen** (4 neue), Lauf der Datei **83 passed** (22,45 s).
* Prüfbefehl `cd backend && .venv/Scripts/python -m pytest tests/ -q`:
  siehe Journal 31 der Plandatei (Exit 0).
* **Messung am echten Bestand (Exit 0, nur lesend):**
  `pCloud-Operationen (Rueckholbarkeit): manifest.jsonl: 79 Buchungen, 2 Arten
  (createfolder 33, extractarchive 46)`; `Zurueckfahrbar (movefile/movefolder):
  0; nur gemeldet, nichts entfernt (createfolder): 33; ohne Rückroll-Regel: 46`;
  Stand 10.10.2026 (1 Tag), 0 kaputt, 0 doppelt, 0 ohne Art, 0 ohne Ziel.
* Ergebnisliste unverändert **5 Lücken** (vier kosten-/gerätegebunden, die
  fünfte = 2 Kennungen ohne Gruppe aus Journal 23).

## Der Befund (gemessen, nicht geändert)

**Keine der 79 Buchungen dieser Nacht ist über das Werkzeug rückholbar.** Die
Extraktionen (46) kennt es gar nicht, die angelegten Ordner (33) meldet es nur.
Das ist kein Fehler des Werkzeugs — es sagt das selbst —, aber es ist eine
Antwort auf „wie mache ich das rückgängig?", die Sebastian bisher nirgends
lesen konnte. Geändert wurde nichts: ob die Extraktionen oder Ordner
zurückgenommen werden sollen, ist seine Entscheidung.

## Grenze (ehrlich, im Docstring)

Verglichen wird **offline** gegen das Manifest — ob die Operation auf pCloud
noch so steht, zeigt erst ein Netzabruf (das Werkzeug bleibt damit offline und
in Sekunden). Nur Zahlen und die technischen Arten-Namen: **kein**
Datei-/Ordnername, kein Pfad, kein Inhalt; im Test mit dem echten Namen
`Papa (Amazon)` und `str(tmp_path) not in text` festgehalten.

## Nicht angefasst

Nichts gelöscht, kein Bild- oder Gesichtsdienst aufgerufen, keine
Handy-Eingriffe, keine kostenpflichtigen Massenläufe, keine pCloud-Schreib-
oder -Lesezugriffe. Betriebs- und Anzeigecode unverändert (nur Werkzeug, Test
und dieses Dokument); committet wurden ausschließlich eigene Pfade
(`git commit --only`, nie `git add -A`).
