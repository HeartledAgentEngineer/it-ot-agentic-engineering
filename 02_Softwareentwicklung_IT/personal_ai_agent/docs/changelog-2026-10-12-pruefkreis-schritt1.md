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

## Nachtrag 12.10.2026: Hermes prüft, wenn Codex gesperrt ist

Sebastians Entscheidung nach dem Limit-Fund: Ist Codex gesperrt, prüft Hermes,
statt zu warten.

- `pruefkreis.py`: Endet Codex mit Exit ≠ 0 und steht in der Fehlerausgabe
  `usage limit`, `rate limit`, `quota` oder `429` (`codex_gesperrt`), startet
  sofort Hermes mit demselben Auftrag. Das Urteil kommt dann von Hermes. Das
  Protokoll vermerkt `Ersatzpruefer: Hermes statt Codex - Codex gesperrt
  (<Meldung>)`. Die Dauer zählt beide Läufe.
- Kein Ersatz bei anderen Codex-Fehlern (Sandbox, Modell) und nicht bei der
  Zeitgrenze. Fehlt das Hermes-Programm, bleibt es bei `fehler` mit Vermerk.
- Regel in `AGENTS.md` (Abschnitt Rollen): Ersatzprüfer Hermes bei
  Codex-Sperre; der Wechsel ist nicht still, er steht im Protokoll.
- Tests: `test_pruefkreis.py` 26 → 33. Neu sind:
  - Ersatzlauf mit FREI,
  - EINWAND von Hermes ergibt Exit 1,
  - kein Hermes vorhanden,
  - drei andere Codex-Fehler ohne Ersatz,
  - Mustergrenzen (Zeitgrenze, `429`, keine Fehlauslösung durch `4290`).

## Nachtrag 12.10.2026: Ergebnisprüfung Runde 2 (Hermes als Ersatz)

- Echter Lauf des Ersatzwegs: Codex war gesperrt („usage limit … try again at
  7:38 PM“). Hermes übernahm (Sitzung `20261012_184825_583867`, DeepSeek v4.1
  Flash, 0,0131 USD, 147 s). Der Arbeitsbaum war vorher und nachher gleich,
  bis auf eine fremde Datei, die ein anderer Agent gestaged hatte.
- Urteil **EINWAND**: Der Plan verlangt im Protokoll auch Modell und
  Planfassung, beides fehlte. Behoben:
  - jede Runde trägt jetzt die Zeile `Modell: … · Planfassung: …`,
  - das Modell ist `gpt-6-astra` bei `--gruendlich`, sonst
    `Codex-App-Standard (Denkstufe high)`, bei Hermes und beim Ersatz das
    Hermes-Modell,
  - die Planfassung kommt aus `--planfassung` oder aus dem ersten `Fassung N`
    der Vorlage, sonst steht dort `nicht angegeben`.
- Tests: 33 → 35.
- Runde 3 (wieder Hermes als Ersatz, Codex weiter gesperrt): **FREI**, Sitzung
  `20261012_185750_08c8d3`, 0,0170 USD. Hermes bestätigt am Code, dass der
  Einwand aus R2 erledigt ist, und findet keinen neuen Fehler. Arbeitsbaum
  vorher/nachher gleich.
