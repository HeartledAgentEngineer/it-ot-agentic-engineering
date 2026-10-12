# Changelog 12.10.2026: Prüfkreis, Schritt 1 (`pruefkreis.py pruefen`)

## Anlass

Bisher trug Sebastian Pläne und Ergebnisse von Hand zwischen Claude Code,
Codex und Hermes hin und her, oder der Agentenbus weckte Hermes. Gewünscht ist:
Der Master lässt automatisch gegenprüfen, und das Diskussionsprotokoll steht
zum Nachlesen im Master-Chat. Plan in Fassung 4, von Codex und Hermes
freigegeben: `.hermes/plans/2026-10-12_hermes-auftraege-statt-bus.md`.

## Was neu ist

- `tools/pruefkreis/pruefkreis.py`, Unterbefehl `pruefen`:
  - startet einen frischen Prüfer, Codex über das Programm der Codex-App mit
    `--ephemeral -s read-only` oder Hermes über `-z` mit DeepSeek v4.1 Flash,
  - liest das Urteil nur aus der letzten Zeile (`URTEIL: FREI|EINWAND`),
  - wertet Absturz, Zeitgrenze und fehlende Urteilszeile als `fehler`,
  - hängt die Runde an `.hermes/pruefkreis/<thema>.md` an und gibt sie aus,
  - Exit 0/1/2 = frei/einwand/fehler,
  - nimmt bei einem Fehler die letzte `ERROR`-Zeile des Prüfers in den Grund
    auf, bei `--sensibel` nicht.
- `--sensibel` erzwingt Hermes und lehnt Codex ab. Durch Ausgabe und Protokoll
  gehen dann nur Urteil, Sitzungskennung und Kosten.
- `tools/pruefkreis/README.md`.

## Prüfung

- `backend/tests/test_pruefkreis.py`: 26 Tests, offline, Prüfer als Attrappen.
  Abgedeckt sind:
  - FREI und EINWAND,
  - Rundenzählung,
  - vier Formen ohne gültige Urteilszeile,
  - Absturz, Zeitgrenze (auch mit einem echten Schlafprozess),
  - Ablehnung von sensibel + Codex (Funktion und Kommandozeile),
  - kein Durchsickern der Begründung bei sensibel (mit `GEHEIMNAME` festgehalten),
  - kaputte Nutzungsdatei, `--gruendlich`,
  - strenges Thema, fehlende Vorlage, fehlendes Programm,
  - Fehlergrund im Protokoll, bei sensibel verschwiegen, Startfehler,
  - Exit-Codes, Auftragstext, Wahl des neuesten `codex.exe`.
- Datei allein: 26 passed.

## Ehrlich offen

- Die Nur-Lese-Sperre für Hermes fehlt noch (Schritt 2). Bis dahin hält nur der
  Auftragstext Hermes vom Schreiben ab.
- Ein echter Lauf mit beiden Prüfern ist Schritt 5.
- Erster echter Lauf (Ergebnisprüfung durch Codex, 12.10.2026 18:08): Status
  `fehler`, Exit 1 nach 5,8 s, weil das Codex-Nutzungslimit erreicht war
  („try again at 7:38 PM“). Das Werkzeug hat das richtig nicht als `frei`
  gewertet, den Grund aber noch verschluckt. Deshalb wird die `ERROR`-Zeile
  jetzt übernommen. Die Ergebnisprüfung durch Codex wird nach dem Limit
  nachgeholt.
