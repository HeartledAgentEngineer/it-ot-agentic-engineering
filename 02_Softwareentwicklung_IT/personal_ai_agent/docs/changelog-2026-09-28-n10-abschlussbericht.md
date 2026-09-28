# Changelog 28.09.2026 — N10: Abschlussbericht des Nachtlaufs + zwei Doku-Zeilen

> **Schritt:** N10 („Doku + Protokoll + Abschlussbericht") aus
> `docs/plan-nachtlauf-2026-09-26.md` · **Rolle:** Ausführer (ein Subagent) —
> **nur Dokumentation**, keine git-Befehle, kein Löschen, kein Code-Änderung,
> die Plan-Datei blieb unverändert (das macht der Planer).
> **Auftrag als Datei:** `docs/auftrag-n10-abschlussbericht.md`.

## Was neu ist

| Datei | Art | Inhalt |
|---|---|---|
| `docs/abschlussbericht-nachtlauf-2026-09-26.md` | **neu** | Eine Seite mit dem Stand des Nachtlaufs in Zahlen: Auftrag/Rahmen, Tabelle „Was fertig ist" (17 Schritte mit Prüfer-Befund), Kosten, der gefundene `alignCrop`-Fehler, gesperrte/offene Punkte, Sicherheitsnetz, Lehren, Prüfbefehl, Quellen |
| `docs/changelog-2026-09-28-n10-abschlussbericht.md` | **neu** | Diese Doku |
| `CLAUDE.md` | geändert | **eine** neue Zeile im Abschnitt „📋 Änderungsprotokoll", Datum `28.09.2026` |
| `../CLAUDE_EXTENDS.md` | geändert | Prüfbefehls-Tabelle, Zeile `personal_ai_agent`: **1687 grün, Exit 0 (28.09.2026)** statt „304 grün (25.09.2026)" |

## Wie der Bericht die Zahlen behandelt

* **Jede Zahl** im Bericht hat eine im Bericht genannte Quelldatei (Journal
  `docs/plan-nachtlauf-2026-09-26.md` oder ein Changelog). Es wurde **nichts
  nachgerechnet, gerundet, hochgerechnet oder geschätzt** — außer den **vier**
  Stellen, die ausdrücklich als „Hochrechnung" (N6b Stapel 1, N6c) bzw.
  „Schätzung" (N6 Vollauf; Ausführerkosten-Summe N6 „≈ 0,08 $") gekennzeichnet
  sind.
* **Keine eigene Messung:** kein Netz-, pCloud- oder Bildaufruf, kein
  Prüfbefehl, keine Teständerung, keine Zahl selbst erhoben.
* Fehlte eine Angabe in den Quellen, steht das ausdrücklich so im Bericht —
  z. B. beim Schritt N6d ist die **Rundenzahl des Prüfers nicht genannt**
  (dort steht „bestanden, Rundenzahl im Journal nicht genannt"), und für N1,
  N4 und N5 ist kein **getrennter** Prüfer belegt (dort steht „Selbstprüfung
  durch den Planer bzw. kein getrennter Prüfer belegt").

## Widersprüche in den Quellen und wie der Bericht sie auflöst

Regel des Auftrags: **der neuere Stand gilt** (Journal-Eintrag schlägt älteren
Changelog), und der Widerspruch wird hier genannt.

1. **N9b und N9d sind ungültig markiert.** `changelog-2026-09-27-gesicht-erkennen.md`
   und `changelog-2026-09-27-n9d-verdrahtung.md` berichten noch die alten
   Personen-Messzahlen („72 Gesichter", „2 Gruppen (6 und 40)", „6
   Referenzseiten"; „465 Gesichter → 72 Vektorwerte"). Der jüngere Journal-Eintrag
   N9e (`docs/changelog-2026-09-27-n9e-aligncrop-fehler.md`) weist diese als
   Messung **eines Fehlers** aus. Der Bericht führt sie in der Tabelle mit ⚠️
   **als ungültig** und nennt die korrigierten Zahlen aus N9e/N9f/N9g.
2. **`changelog-2026-09-27-rueckrollwerkzeug.md` ist selbst als ÜBERHOLT
   gekennzeichnet** (erste, parallele Fassung des Rückroll-Werkzeugs). Gültig ist
   `changelog-2026-09-27-rueckroll-sicherung.md` (`pcloud_bewegungen.py` +
   `pcloud_rueckrollen.py`, Trockenlauf als Standard, Positivliste). Der Bericht
   stützt Abschnitt 6 auf die jüngere Fassung.
3. **Prüfbefehls-Zahlen laufen über die Changelogs auseinander** (545, 574, 671,
   1316 … 1687). Der Bericht nennt den **neuesten belegten Stand**: **1687
   passed, Exit 0** (Plan-Zeile N11), Baseline **1503**.
4. **N6c-Zählung:** die Plan-Tabelle schreibt „18 × `Sonstiges`" für flash-lite;
   der Journal-Eintrag präzisiert **17 selbst gewählt + 1 aus einer Antwort
   außerhalb des Katalogs**. Der Bericht nennt die präzise Fassung.
5. **N9e-Beleg-Prüfsummen:** die Plan-Zeile N9e nennt `e06d30ef365c`, das
   Changelog `…n9e-aligncrop-fehler.md` dieselbe Größe — hier liegt **kein**
   Widerspruch vor; der Bericht nennt den Wert aus dem Changelog.

## Datenschutz

Der Bericht nennt **keine Personennamen** (auch nicht den Eigner-Namen — dort
steht „der Nutzer"), **keine Ortsnamen**, **keine echten pCloud-Ordnernamen**,
**keine Datei-Kennungen** und **keine Schlüsselwerte**. Die Begriffe, die
vorkommen, sind generisch (z. B. `Konzert und Buehne`, `Sonstiges`, `Urlaub`)
oder blanke Kalenderjahre. Der Übersichtsdatei-/Ordnername
`~/foto_sortierung/fotos_uebersicht.json` steht so auch im Plan und enthält
keine privaten Bestandteile.

## Was dieser Schritt NICHT getan hat

* Kein git-Befehl (kein `add`, `commit`, `push`, `status`) — der Planer committet.
* Nichts gelöscht, nichts umbenannt, kein Code geändert, keine Tests geändert.
* Die Plan-Datei `docs/plan-nachtlauf-2026-09-26.md` blieb **unangetastet**
  (der Planer pflegt dort die Journal-Zeile für N10).
* **Fremde Dateien des zweiten Agenten wurden NICHT angefasst.** Die vier
  fremden Dateien waren schon **vor** dieser N10-Runde geändert im Arbeitsbaum;
  die Zeitstempel belegen es: `docs/experimente/live_zahlen.html` und `.json`
  → **2026-09-28 08:43:00** (vom **zweiten Agenten während dieses Laufs**
  geschrieben), `docs/recherche/datenkontrolle-anbieter.html` → **2026-09-25
  12:58:55**, `docs/recherche/ki-training-schutzformen.html` → **2026-09-25
  12:17:07**. Dieser Schritt hat **keinen** git-Befehl ausgeführt und keine
  dieser Dateien angefasst.

## Prüfbefehl

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
```

Vom Planer für diesen Stand gefahren: **1687 passed, Exit 0** (Baseline 1503).
Der Prüfbefehl wurde in diesem Schritt **nicht** erneut gefahren (reine
Dokumentationsänderung); die zwei genannten Doku-Zeilen tragen genau diesen
Stand.
