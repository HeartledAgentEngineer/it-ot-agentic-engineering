# Experiment-Register — Agentic Engineering

**Zweck:** Jede Behauptung über Agenten-Arbeit durch eine echte Messung ersetzen.
Kein YouTube-Tipp, keine Benchmarks fremder Anbieter — sondern der eigene Verbrauch.

## Warum

Best Practices für Agentic Engineering sind nicht etabliert — das Feld ist zu jung,
jeder macht es anders. Belastbar ist nur, was **am eigenen Setup gemessen** wurde.
Dieses Register hält die Messungen fest (nach dem Prinzip aus den Everlast-Praxisblöcken):
**Baseline messen → eine Sache ändern → vergleichen.**

## Benutzung

```bash
cd docs/experimente

# 1. Baseline festhalten (Snapshot der Session-DB)
python experiment.py start "Bringt reasoning_effort: high spürbar bessere Ergebnisse?"

# 2. EINE Sache ändern (z. B. hermes config set agent.reasoning_effort high)
#    ... normal weiterarbeiten ...

# 3. Abschließen — die Differenz landet automatisch im Register
python experiment.py ende "Ja, bessere Struktur bei gleicher Dauer" --notiz "3 Läufe"

# Übersicht
python experiment.py liste
```

## Was automatisch gemessen wird

Alle Werte kommen aus der Hermes-Session-DB (`%LOCALAPPDATA%/hermes/state.db`)
und werden als **Differenz** zwischen `start` und `ende` gebildet — es zählt also
nur die Arbeit am Experiment, nicht die Gesamtsitzung.

| Spalte | Quelle |
|---|---|
| Dauer | Zeitstempel |
| Turns/Tools | `message_count` / `tool_call_count` |
| Input / Output / Cache | `input_tokens` / `output_tokens` / `cache_read_tokens` |
| Kosten | `estimated_cost_usd` + `actual_cost_usd` |

> Hinweis: Die Spalte „Turns/Tools" dient auch als **Wiederholungs-Anzeige** —
> viele Tool-Calls bei wenigen Nachrichten bedeuten Trial-and-Error-Schleifen.

## Regeln für saubere Messungen

1. **Nur eine Variable pro Experiment.** Zwei Änderungen gleichzeitig = keine Aussage.
2. **Gleiche Aufgabe, gleiche Länge.** Ein 200-Zeilen-Task und ein 2000-Zeilen-Task
   sind nicht vergleichbar.
3. **Leerer Start.** Vor dem Experiment keine Sitzung mit Altkontext weiterführen
   (verfälscht Cache-Trefferquote und Kosten).
4. **Mehrere Metriken.** Nie nur „hat es funktioniert" — Dauer, Kosten, Turns/Tools
   und Ergebnisqualität zusammen bewerten.
5. **Ergebnisqualität** kurz und konkret notieren (z. B. „3 von 4 Anforderungen erfüllt,
   Nacharbeit nötig").

## Kandidaten für die ersten Messungen

| Frage | Was ändern | Erwartung |
|---|---|---|
| Bringt `reasoning_effort: high` mehr? | medium → high | Mehr Qualität für ~$1,27/Monat |
| Wie stark hilft Session-Disziplin beim Cache? | eine Sitzung, keine Neustarts | Cache-Trefferquote steigt über 86,8 % |
| Lohnt ein Planer-Modellwechsel? | Plan mit starkem Modell, Ausführung mit Flash | Kosten pro Feature sinken |
| Wie gut sind die 19 Kanon-Regeln? | mit/ohne Regelwerk an gleicher Aufgabe | weniger Rückfragen, weniger Nacharbeit |

## Der Kanon, gegen den gemessen wird

`docs/recherche/MARCEL-KANON.md` (69 Praktiken) und
`02_Softwareentwicklung_IT/CLAUDE_EXTENDS.md` §6.8 (19 verbindliche Regeln).

## guthaben.py — was der Verbrauch wirklich kostet

```bash
python guthaben.py              # Guthaben, Verbrauch, Hochrechnung (USD)
python guthaben.py --euro       # dieselben Zahlen in EUR (Live-Wechselkurs)
python guthaben.py --kaufen 25  # was 25 EUR Cash an Guthaben ergeben
python guthaben.py --staffel    # Gebuehren-Staffel: ab wann greift der Prozentsatz?
```

OpenRouter ist **kein Abo, sondern ein Tank**: pro Token abgerechnet, kein Grundpreis.
Der Aufschlag kommt nur beim **Aufladen**:

| Posten | Satz | Bemerkung |
|---|---|---|
| Service fee | 5,5 % | **Minimum $0,80** — unter $14,55 Aufladung wird es teurer |
| Sales Tax / VAT | 19 % | deutsche USt, auf Guthaben + Service fee |
| **Gesamt** | **+25,5 %** | keine Mengenrabatte, keine Staffel |

Verifiziert gegen einen echten Kaufdialog: $17,00 Guthaben = $0,94 Service
+ $3,41 USt = $21,35 Cash.

## chat_kosten.py — was jeder Chat gekostet hat

```bash
python chat_kosten.py                      # heute, Top 10
python chat_kosten.py --zeitraum alles     # seit immer
python chat_kosten.py --zeitraum woche     # diese Woche ab Montag
python chat_kosten.py --chat "agentic"     # Zeitleiste eines Chats
python chat_kosten.py --csv                # fuer Tabellenkalkulation
```

**Warum es das braucht:** Die Statusleiste liest den LIVE-Zaehler der Session, der
beim App-Start bei Null beginnt. Sie zeigt deshalb nur die Aktivitaet seit dem
Start, nicht die Lebenszeit des Chats. Die Datenbank kennt die volle Historie.

**Falle im Code:** `last_seen` in `session_model_usage` ist ein UNIX-Zeitstempel
(REAL), kein Datumsstring. `date(last_seen) = date('now')` liefert immer 0 Zeilen.
Richtig ist `last_seen >= strftime('%s','now',...)`.

## dashboard/ - Kosten-Dashboard fuer alle Chats

`dashboard/build_dashboard.py` liest `state.db` (nur lesend) und erzeugt
`dashboard/dashboard.html` - eine eigenstaendige Datei (0 externe Aufrufe).

Inhalt: alle Chats mit Rang/Titel/Kosten/EUR+USD, getrennte Input-/Output-/
Cache-Tokens, Cache-Trefferquote, Aufschluesselung nach Modell und Tag,
Cash-Betrag inkl. Servicegebuehr und Steuer. Zeitraeume: heute / Woche /
7 Tage / Monat / alles.

Selbstpruefung: das Skript vergleicht seine HTML-Summen gegen direkte
SQL-Abfragen und bricht bei Abweichung ab.

    python dashboard/build_dashboard.py
    # -> dashboard/dashboard.html  (im Browser oeffnen)

Warum eigenes Dashboard: OpenRouter zeigt nur USD *vor* Aufschlag
(Servicegebuehr + USt fehlen) und nur den eigenen Schluessel. Das Dashboard
rechnet in EUR, rechnet den Aufschlag ein und kennt alle lokalen Chats.
