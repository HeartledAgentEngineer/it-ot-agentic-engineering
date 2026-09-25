# Changelog 25.09.2026 — Antwort war leer: Daemon lieferte nur einen Hinweis

## Der Befund (Live-Test Sebastian, 25.09.2026, 18:01)

Im Chat auf dem Handy standen die **Gedanken** sauber da — und darunter nur
**„✅ Hermes hat geantwortet."** ohne inhaltliche Antwort. Das Bildschirmfoto vom Gerät
zeigte: Der **echte Antworttext war komplett vorhanden**, aber als **🧠 Gedanke**-Blasen
ausgegeben, nicht als Antwort.

## Ursache (belegt in `hermes_inbox_daemon.py`)

Wird der Antwort-Kasten der Hermes-CLI (`╭─⚕ Hermes ╮`) nicht erkannt, greift
`_roh_fallback()`. Diese Funktion hat den Rohtext zwar als **Zwischenmeldungen**
gestreamt (`block_writer` → im Chat die Gedanken-Blasen), **zurückgegeben** hat sie aber
nur den Hinweis:

> „📄 Rohausgabe vollstaendig: N Zeilen, oben in K Bloecken gestreamt."

Dieser Hinweis landete in `antworten.jsonl` — also war die **Antwort** inhaltlich leer,
obwohl der Text sichtbar war. Ein Widerspruch, der wie ein Fehler aussah: „hat
geantwortet" ohne Antwort.

## Die Reparatur

`_roh_fallback()` gibt jetzt den **vollständigen Text** zurück (`kopf + alle nutzbaren
Zeilen`). Die Block-Zwischenmeldungen bleiben unverändert bestehen — man kann also
weiterhin in Häppchen mitlesen **und** hat am Ende die ganze Antwort als Nachricht.
Die Regel „lange Rohausgabe nicht kürzen" bleibt damit gewahrt.

## Prüfung

| Befehl | Ergebnis |
|---|---|
| `.venv/Scripts/python -m pytest tests/test_daemon_ausgabe.py -q` | **9 passed** |
| `.venv/Scripts/python -m pytest tests/ -q` (voller Prüfbefehl) | **388 passed, Exit 0** (116,08 s) |

Zwei Tests sichern das Verhalten ab:

1. `test_fallback_mit_bloecken_liefert_den_vollen_text_als_antwort` (neu) — die Antwort
   trägt den Inhalt selbst, enthält **nicht** „gestreamt", und die Zwischenmeldungen
   existieren weiterhin.
2. `test_fallback_streamt_in_zeitbloecken` (angepasst) — prüfte vorher die alte
   Hinweis-Zeile und wäre sonst grün geblieben, obwohl die Antwort leer war.

## Nachtrag: Diagnose-Ablage (aus demselben Anlass)

Weil der Termux-Heimatordner über das Kabel **nicht** lesbar ist (`adb shell` läuft als
anderer Benutzer), legt `start-termux.sh` bei jedem Start die letzten 200 Zeilen des
Inbox-Protokolls plus letzte Antworten/Status/Aufträge in
`/sdcard/Download/hermes_diag/` ab. Ohne diese Ablage war die Ursache nicht sichtbar.

## Offen (Sebastians Wunsch, 25.09.2026, geht an den Frontend-Bau)

- **Gedanken-Blasen einklappen:** nach dem vollständigen Anzeigen sanft zuklappen
  (Bubble für Bubble), eingeklappt eine schmale Zeile mit Zeit + 🧠 + Kurzfassung,
  antippbar zum Aufklappen.
- **Keine leeren Blasen:** Zeitstempel und 🧠-Symbol erst rendern, wenn Text da ist —
  vorher erschienen zwei Zeitstempel vor dem ersten Text.
