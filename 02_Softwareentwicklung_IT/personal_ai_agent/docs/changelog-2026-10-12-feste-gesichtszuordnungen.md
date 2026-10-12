# T1: Feste Einzelzuordnungen im Gruppierlauf

Datum: 12.10.2026. Umsetzung ausschließlich mit synthetischen Fixtures; kein produktiver Gruppierlauf, keine Installation und keine Geräteübertragung.

## Verhalten

- `personen_vorgaben.json` wird im Quiz-Speicherformat gelesen: `zugeordnet` ist ein Array mit `bild_id`, `index`, `name`, `kennung` und `aktion`. `name` ist das bestätigte Ziel; `kennung` bleibt Herkunft. Der letzte gültige Eintrag je `(bild_id, index)` gewinnt. Ungültige Typen, Namen, Bild-IDs und negative Indizes werden ignoriert; `aktion` wird für die Zielauflösung nicht benötigt.
- Zielnamen werden nach den Quiz-Regeln normalisiert und ohne Beachtung der Groß-/Kleinschreibung gegen bestätigte Namen aufgelöst. Bei gleichnamigen bestätigten Gruppen bleibt die Herkunftskennung erhalten, wenn sie selbst zur Zielperson gehört; sonst gewinnt deterministisch die kleinste passende Kennung.
- Im Voll-Lauf überschreibt die feste Entscheidung Ähnlichkeit und Herkunftsausschluss. Ein ausdrücklicher Ausschluss derselben Zielperson oder ein nicht bestätigtes Ziel führt vor dem Schreiben zu einem generischen Fehler. Fehlende Gesicht-Belege werden nur als Anzahl gemeldet.
- Ist die bestätigte Zielgruppe im automatischen Lauf nicht vertreten, wird sie dennoch mit ihrer Kennung veröffentlicht. Ihr Mittelpunkt wird nur aus den ausdrücklich zugeordneten Vektoren berechnet; reservierte Zielkennungen werden bei automatischer Nummerierung übersprungen.
- Der Nachtrag berücksichtigt neue und bereits vorhandene Gesichter. Er korrigiert ausschließlich betroffene `kennung`-Felder, erhält Zusatzfelder und lässt unbetroffene Rohzeilen bytegleich. Gruppenstatistik und Beispiele werden angepasst; alte Mittelpunkte bleiben unverändert. `korrigierte_altgesichter` steuert Writer und CLI-No-op.
- Beim Quiz-Umbenennen werden gespeicherte Einzelzuordnungs-Zielnamen aktualisiert. Das Aktionsprotokoll hält die betroffenen Einträge fest; Rückgängigmachen stellt nur diese Zielnamen wieder her.

## Synthetische Nachweise

- Parser: letztes gültiges Quiz-Array-Element, Zielname getrennt von Herkunft, ungültige Einträge.
- Voll-Lauf: widersprechende Ähnlichkeit, Herkunftsausschluss, casefold, fehlendes Ziel/Beleg und Zielausschluss.
- Bestätigtes Ziel ohne Auto-Cluster: reservierte Kennung, persistierte Gruppe und Mittelpunkt-Referenz.
- Nachtrag: neues Gesicht, altes Gesicht ohne Neuzugang, CLI-Schreiben bei reiner Alt-Korrektur, anschließender No-op, idempotente Wiederholung, bytegleiche unbetroffene Zeilen und Zusatzfelder der betroffenen Zeile.
- Quiz: Umbenennen, Erhalt unbeteiligter Vorgaben sowie Rücknahme einschließlich Zusammenführung.

## Prüfergebnisse

- Vor der Implementierung, drei betroffene Module: `python.exe -m pytest tests/test_personen_gruppieren.py tests/test_personen_gruppieren_nachtragen.py tests/test_gruppen_quiz.py -q` — Exit 1, 5 fehlgeschlagen, 127 bestanden. Die Regressionen waren rot gegen den unveränderten Produktionscode.
- Nach der Implementierung, dieselben drei Module: derselbe Befehl — Exit 0, 141 bestanden.
- Vollständiger Lauf: `python.exe -m pytest tests/ -q` — Exit 1, 3862 bestanden, 3 übersprungen, 3 fehlgeschlagen. Die drei verbleibenden Fehler liegen außerhalb der erlaubten T1-Dateien: ein Archiv-Standardtest findet seinen benötigten Index nicht; zwei Start-/Übergabetests melden CRLF statt LF. Diese Bereiche wurden nicht geändert.

## Unabhängige Abschlussprüfung im gemeinsamen Projektstand

Nach der identischen Übernahme wurde der vollständige Projektprüfbefehl im gemeinsamen Hauptbaum erneut durch Hermes mit `deepseek/deepseek-v4.1-flash` ausgeführt: **3888 passed, 2 skipped, Exit 0**, 319,39 Sekunden. Die fünf betroffenen Python-Dateien waren vor und nach dem Lauf unverändert; der bereinigte maschinelle Beleg liegt lokal außerhalb der Versionshistorie. Die drei Fehler der isolierten Kopie verhinderten im Hauptbaum keinen grünen Abschluss.

Die unabhängige Prüfung meldete keine blockierenden Befunde im T1-Umfang. Zwei bestehende Grenzen bleiben offen: Beim Nachtrag kann ein alter Name aus den gespeicherten Gruppenbeispielen gegenüber dem aktuellen bestätigten Namen bevorzugt werden; ein insgesamt falsch typisierter `zugeordnet`-Container wird noch nicht durch eine generische Formatfehlermeldung abgefangen. Diese Punkte sind nicht als durch T1 behoben zu verstehen.

## Rücknahmegrenze

Die Quiz-Rücknahme stellt eine Zielnamenänderung vor dem Gruppierlauf wieder her. Eine bereits veröffentlichte Zuordnung wird durch das spätere Entfernen der Vorgabe nicht automatisch historisch zurückgesetzt; das wird nicht als umfassende Undo-Funktion behauptet. Unbetroffene Altzeilen bleiben bytegleich, und es wird keine Gesamttransaktion über mehrere Ausgabedateien behauptet.
