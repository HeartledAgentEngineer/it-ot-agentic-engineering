---
name: fehlersuche
description: Einzusetzen bei jedem Fehler, fehlgeschlagenen Test, Absturz oder unerwarteten Verhalten — bevor eine Reparatur vorgeschlagen wird. Erzwingt Ursachensuche vor Symptombehandlung. Besonders dann, wenn der Fehler simpel wirkt, Zeitdruck herrscht oder schon ein Reparaturversuch gescheitert ist.
---

# Fehlersuche

**Grundsatz:** Erst die Ursache finden, dann reparieren. Eine Symptombehandlung
ist kein Erfolg, sondern eine verschobene Fehlersuche.

## Die eine Regel

> Keine Reparatur ohne benannte Ursache.

Ist Phase 1 nicht abgeschlossen, wird kein Fix vorgeschlagen — auch kein
naheliegender.

## Phase 1 — Ursache finden

1. **Fehlermeldung vollständig lesen.** Nicht überfliegen. Stacktrace bis zum
   Ende, Zeilennummern und Dateipfade notieren. Oft steht die Lösung darin.
2. **Zuverlässig reproduzieren.** Welche Schritte genau? Tritt es immer auf?
   Nicht reproduzierbar heißt: mehr Daten sammeln, nicht raten.
3. **Letzte Änderungen prüfen.** `git diff`, die letzten Commits, neue
   Abhängigkeiten, geänderte Konfiguration.
4. **Bei mehreren Komponenten: messen statt vermuten.** Wenn mehr als ein
   Bauteil beteiligt ist (Frontend → API → Datenbank, Hook → Skript → Programm),
   an **jeder Grenze** ausgeben, was hinein- und was herausgeht. Einmal laufen
   lassen, dann steht fest, *welches* Bauteil versagt — erst dieses wird
   untersucht.
5. **Datenfluss rückwärts verfolgen.** Wo entsteht der falsche Wert? Wer hat mit
   diesem Wert aufgerufen? Weiter nach oben, bis die Quelle gefunden ist. An der
   Quelle reparieren, nicht an der Stelle, wo es auffällt.

## Phase 2 — Muster erkennen

1. **Funktionierendes Gegenstück suchen.** Gibt es im selben Projekt ähnlichen
   Code, der läuft?
2. **Unterschiede auflisten** — alle, auch die vermeintlich belanglosen.
   „Das kann nicht daran liegen" ist keine Analyse.
3. **Abhängigkeiten klären.** Welche Konfiguration, welche Umgebung, welche
   Annahmen setzt der Code voraus?

## Phase 3 — Hypothese bilden und prüfen

1. **Eine** Hypothese formulieren, ausgeschrieben: „Ich vermute X als Ursache,
   weil Y." Konkret, nicht vage.
2. **Kleinstmöglich testen.** Eine Variable, eine Änderung. Nicht mehrere
   Vermutungen gleichzeitig prüfen — sonst ist hinterher unklar, was gewirkt hat.
3. **Bestätigt?** Dann Phase 4. **Nicht bestätigt?** Neue Hypothese bilden —
   **keine** zweite Reparatur auf die erste draufsetzen.
4. **Wenn etwas unklar ist:** „Ich verstehe X nicht" sagen und nachfragen.
   Verstehen vortäuschen kostet später mehr.

## Phase 4 — Reparieren

1. **Zuerst den fehlschlagenden Test schreiben.** Die einfachste Reproduktion,
   automatisiert wenn möglich. Der Test muss **vor** der Reparatur rot sein —
   sonst prüft er nicht das, was kaputt war.
2. **Eine einzige Reparatur.** Kein „wenn ich schon mal hier bin", kein
   gebündeltes Refactoring.
3. **Verifizieren nach der Regel aus `AGENTS.md`:** Prüfbefehl frisch ausführen,
   Exit-Code lesen, ursprüngliches Symptom erneut prüfen. Erst dann „behoben"
   sagen.

## Abbruch — wann Schluss ist

`AGENTS.md` gilt: **nach zwei gescheiterten Reparaturversuchen wird gemeldet,
nicht weitergebastelt.** Zu melden ist dann aber nicht „geht immer noch nicht",
sondern der eigentliche Befund:

> Wenn jeder Fix an anderer Stelle ein neues Problem aufdeckt, ist nicht der
> Fehler das Problem, sondern die Annahme über die Architektur.

Anzeichen dafür: Jede Reparatur legt neue Kopplung oder neuen geteilten Zustand
frei; ein Fix wäre nur mit „größerem Umbau" machbar; jede Reparatur erzeugt
anderswo ein neues Symptom. Das ist keine gescheiterte Hypothese, sondern ein
falscher Aufbau — und darüber entscheidet Sebastian, nicht der Agent.

## Sofort anhalten bei diesen Gedanken

- „Erstmal schnell reparieren, Ursache später"
- „Einfach mal X ändern und schauen"
- „Ist wahrscheinlich X, das mache ich schnell"
- „Verstehe ich nicht ganz, aber das könnte klappen"
- „Noch ein Versuch" — nachdem bereits zwei gescheitert sind
- Lösungen nennen, bevor der Datenfluss verfolgt wurde

## Typische Ausreden

| Ausrede | Gegenrede |
|---|---|
| „Der Fehler ist simpel, das braucht kein Verfahren" | Auch simple Fehler haben Ursachen. Bei simplen Fehlern ist das Verfahren schnell durch. |
| „Keine Zeit, es eilt" | Systematisch ist schneller als raten und wieder aufmachen. |
| „Erst probieren, dann untersuchen" | Der erste Fix setzt das Muster. |
| „Test schreibe ich, wenn der Fix läuft" | Ungetestete Reparaturen halten nicht. |
| „Mehrere Änderungen auf einmal spart Zeit" | Dann ist unklar, welche gewirkt hat. |
| „Ich sehe das Problem doch" | Das Symptom sehen ist nicht die Ursache verstehen. |

## Wenn wirklich keine Ursache auffindbar ist

Dann dokumentieren, was untersucht wurde, eine angemessene Behandlung einbauen
(Wiederholung, Zeitgrenze, verständliche Fehlermeldung) und eine Protokollierung
für den nächsten Fall ergänzen. Zu wissen: Die meisten Fälle von „keine Ursache
auffindbar" sind unvollständige Untersuchungen.

## Zusammenspiel

- Suchen im Projekt geht an den Subagenten `rechercheur`, Prüfläufe an `tester` —
  damit Treffer und Logs nicht den Hauptkontext füllen.
- Ist der Fehler behoben, gilt für die Erfolgsmeldung die Belegpflicht aus
  `AGENTS.md`.
