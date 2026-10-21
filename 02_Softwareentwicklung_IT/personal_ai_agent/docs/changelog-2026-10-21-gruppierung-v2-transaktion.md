# 21.10.2026 – Gruppierung v2, Schritt 4: Sicherung, transaktionales Schreiben, Rückrollen

Plan: `.hermes/plans/2026-10-20_gruppierung-v2-fassung5.md` (Fassung 5.3, Auflage 4).
Verbindlicher Auftrag: Fassung 4 mit Nachtrag E1–E3 (`.hermes/uebergabe/laufend/personal-ai-agent-auftrag-v2-schritt4.md`).
v1 bleibt Standard und ändert sich nicht. Gilt nur für den v2-Schreibweg
(`personen_gruppieren.py --verfahren v2 --schreiben --freigabe …`).

## Was sich ändert
- **Bereitstellungsordner je Lauf.** v2 schreibt nicht mehr direkt in die Zieldateien
  und legt keine `*.vorher_<stempel>`-Kopien mehr an. Stattdessen entsteht im Zielordner
  `.v2_<stempel>/` mit `vorher/` (Ausgangsstand, sha256 gegen die Quelle geprüft), `neu/`
  und zuletzt `stand.json` (vier Dateien: Zuordnung, Beispiele, Kennungen,
  `aliasmengen.json`, je `vorher_sha256` / `neu_sha256`). Ab `stand.json` heißt der
  Ordner BEREIT.
- **Zweite Prüfung direkt vor dem Einspielen.** Alle vier Ziele werden noch einmal gegen
  `vorher_sha256` geprüft, `vorher/` und `neu/` gegen `stand.json`. Hat sich seit dem
  Bereitstellen etwas geändert: Exit 2, keine Zieldatei geändert, der Ordner bleibt BEREIT.
- **Einspielen Datei für Datei mit Fortschrittsmarken.** Je Datei: tmp-Kopie aus `neu/`
  (Hash geprüft), Marke `.beginn`, `os.replace`, Marke `.eingespielt`. Die tmp-Kopie
  entsteht selbst erst als `<name>.tmp_<stempel>.teil` und wird nach bestandener
  Hashprüfung umbenannt. Ein Absturz mitten im Kopieren hinterlässt nur die `.teil`-Datei;
  sie wird beim nächsten Versuch nach `.teil.verworfen_<k>` verschoben, nie gelöscht.
  Am Ende heißt der Ordner `.v2_<stempel>.fertig`.
- **`--weiter`** vollendet einen abgebrochenen Stand ab dem belegten Schritt und trägt
  fehlende Manifestzeilen nach. Ohne Eingabedateien, ohne Freigabe, wiederholbar.
- **`--rueckrollen <stempel>`** stellt den Ausgangsstand aus `vorher/` exakt wieder her,
  nur für den jüngsten nicht zurückgerollten Stand. Dateien, die es vorher nicht gab,
  werden nach `<name>.verworfen_<stempel>` verschoben. Der Ordner heißt danach
  `.v2_<stempel>.zurueckgerollt`. Ein Abbruch beim Rückrollen wird durch erneuten
  Aufruf vollendet.
- **Abbruch beim Bereitstellen (UNFERTIG, ohne `stand.json`):** Die Ziele sind dann nie
  angefasst. `--weiter` lässt den Ordner mit Hinweiszeile liegen, `--rueckrollen` endet
  mit Exit 2 und Hinweis; erst der nächste schreibende Lauf verschiebt ihn nach
  `.unfertig`.
- **FREMD = Exit 2 ohne Änderung:** veränderte Zieldatei, manipulierte Sicherung, fremde
  tmp-Kopie, belegter Name. Nichts wird je gelöscht oder auf einen belegten Namen
  verschoben.
- **Manifest** `--manifest` (Standard `~/foto_sortierung/sicherungen_manifest.jsonl`) ist
  reines Protokoll: eine Zeile je Ereignis (`eingespielt`, `zurueckgerollt`). Zeilen
  werden streng geprüft; ein fehlendes oder beschädigtes Manifest blockiert keinen Weg,
  es gibt nur eine Warnzeile. Ein Nachtrag prüft keine Zieldateien und meldet
  „Zielzustand ungeprüft (Nachtrag nur Protokoll)“. Für Tests leitet die
  Umgebungsvariable `GRUPPIERUNG_MANIFEST` den Standardpfad um.
- `--schreiben`, `--weiter` und `--rueckrollen` schließen sich gegenseitig aus.
  Ein neuer Stempel muss jünger sein als alle vorhandenen (zwei Läufe in derselben
  Sekunde → Exit 2).
- Der Bericht nennt am Ende den Rückrollbefehl.

## v1 bleibt unverändert
Der v1-Zweig ruft weiter `_stempel_sichern` und `schreiben` auf; es entsteht kein
`.v2_*`-Ordner und keine Manifestzeile (Test). Der Vergleichstest gegen Commit `80a4c69`
bleibt grün.

## Belege
- Neu: `backend/tests/test_gruppierung_v2_transaktion.py` (184 Tests, erfundene Daten in
  `tmp_path`): Rundlauf, erster Lauf in leeren Ordner, Kollisionen, Abbrüche an jedem
  Schritt (auch mitten in einer Kopie) mit `--weiter` und `--rueckrollen`, UNFERTIG,
  FREMD-Fälle, Manipulation vor dem Einspielen, Reihenfolge, Manifest-Fälle,
  Wartungswege über `main()`.
- Angepasst: `test_personen_gruppieren_v2.py` (zwei Tests: Sicherungen liegen jetzt in
  `.v2_<stempel>.fertig/vorher/`; zweiter Lauf mit laufender Uhr statt derselben Sekunde),
  `conftest.py` (autouse-Fixture: Manifest in Tests nie im Heimordner).
- Gezielte Gruppierungstests: 546 passed, Exit 0 (vorher 362). Dazu der volle
  Prüfbefehl im Commit-Haken.
- Planprüfung durch Codex (gpt-6-sol, nur lesend): Runden 1–9 EINWAND, **Runde 10 FREI**.
  Ergebnisprüfung: Runde 1 EINWAND (Absturz mitten im Kopieren, Auslassung in der zweiten
  Prüfung, beschädigtes Manifest konnte blockieren), behoben, **Runde 2 FREI**.
  Protokoll: `.hermes/pruefkreis/gruppierung-v2-schritt4-pruefung-codex.md`.
- Umsetzung durch einen Sonnet-Worker (Codex als Worker war gesperrt, „blocked by
  policy“). Ehrlich vermerkt: In der ersten Runde schrieb der Worker die Tests nach dem
  Implementierungsentwurf und maß den Rotlauf nachträglich; in der Nachbesserung liefen
  die 12 neuen Tests zuerst rot.

## Bekannte Grenzen
- Ändert jemand eine Zieldatei in der Millisekunde zwischen der zweiten Prüfung und dem
  `os.replace`, bleibt das unbemerkt (nur mit Dateisperren lösbar; für einen einzeln
  gestarteten Lauf am eigenen PC vertretbar).
- Ein echter Schreiblauf mit den echten Daten steht noch aus (Sebastian).

## Nächster Schritt
Plan-Schritt 5 der Fassung 5.3.
