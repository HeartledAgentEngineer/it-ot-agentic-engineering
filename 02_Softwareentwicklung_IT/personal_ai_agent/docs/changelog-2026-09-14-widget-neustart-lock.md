# Changelog 2026-09-14 — Widget-Neustart heilt sich selbst (Start-Lock)

## Symptom

Ein Druck auf das Startbildschirm-Widget `agent` startete den Agenten nicht
mehr neu. Stattdessen erschien nur kurz die Meldung
„⚠️ Ein agent-start laeuft gerade (Neustart laeuft). Einen Moment warten.“ —
und es passierte nichts, beliebig oft wiederholbar.

## Ursache

`termux/agent-start` schützt die Kill-/Start-Phase mit einem Verzeichnis-Lock
(`termux/.agent-start.lock`, angelegt per `mkdir`). Der Lock wurde am Ende der
Start-Phase mit `rm -rf` wieder entfernt.

Wurde die Widget-Session **während** dieser Phase abgebrochen — Android
beendet die Termux-Session, Handy-Neustart, Strg+C — lief das Skript nie bis
zum `rm -rf`. Der Lock blieb **für immer** liegen. Jeder weitere Widget-Druck
scheiterte danach an der `mkdir`-Prüfung und beendete sich mit
„laeuft gerade“ — der Agent konnte nur noch per Hand im Terminal gestartet
werden.

Im konkreten Fall lag ein leerer Lock-Ordner vom 2026-09-14 17:04 vor; es lief
kein `agent-start` und kein `uvicorn` mehr.

## Fix

Der Lock ist jetzt **selbstheilend** (`termux/agent-start`):

- Der Lock schreibt die **PID** des haltenden Prozesses (`lock/pid`) und einen
  **Zeitstempel** (`lock/zeit`).
- Beim Betreten wird ein vorhandener Lock als **verwaist** erkannt und
  übernommen, wenn
  - keine PID hinterlegt ist, oder
  - die PID nicht mehr lebt (`kill -0`), oder
  - er älter als 5 Minuten ist (300 s — die Kill-/Start-Phase dauert nie so
    lang).
- Ein `trap` auf `EXIT INT TERM` räumt den Lock bei Abbruch sofort weg.
- Nur ein **echter** paralleler Start (lebende PID, innerhalb des Zeitlimits)
  wird weiterhin abgelehnt.

Damit gilt weiter: Ein Widget-Druck killt genau einen laufenden Server und
startet genau einen frischen; der Lock bleibt ausschließlich während der
Kill-/Start-Phase gehalten, damit der nächste bewusste Neustart möglich ist.

## Verifikation

- `bash -n termux/agent-start` → Exit 0.
- Einzeltest der Lock-Logik (7 Prüfungen, alle grün): frisch nehmen; lebender
  Halter wird abgelehnt; tote PID → übernehmen; **leerer Alt-Lock (exakt der
  Bugfall) → übernehmen**; überaltert → übernehmen; nach Freigabe ist der Lock
  weg; PID-Datei wird geschrieben.
- End-to-End: `agent-start` gestartet → `GET /api/health` liefert
  `{"status":"ok",...}` (174 Erinnerungen, LLM konfiguriert), und der Lock ist
  danach **frei** — der nächste Widget-Druck kann wieder neu starten.

## Notfall (falls je wieder ein Lock hängt)

```bash
rm -rf /data/data/com.termux/files/home/it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent/termux/.agent-start.lock
```

Dann das Widget `agent` erneut antippen. Mit dem Fix ist dieser Handgriff in
der Regel nicht mehr nötig (Selbstheilung).
