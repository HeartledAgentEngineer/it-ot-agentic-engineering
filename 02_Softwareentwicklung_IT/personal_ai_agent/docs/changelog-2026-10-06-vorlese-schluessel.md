# Änderungsprotokoll 06.10.2026 — eigener OpenRouter-Schlüssel fürs Vorlesen

Wunsch Sebastian: Fürs Vorlesen gibt es einen eigenen OpenRouter-Schlüssel (über die
Management-Stelle angelegt, Hermes nutzt ihn bereits). OpenRouter weist die Kosten je Schlüssel
aus — so ist sichtbar, was das Vorlesen kostet, bei Hermes wie beim Agenten. Ist er nicht
vorhanden, liest wie bisher der Hauptschlüssel vor (kein Entweder-oder).

## Ausgangslage

- Hermes hat den Schlüssel als `OPENROUTER_TTS_KEY` in `%LOCALAPPDATA%\hermes\.env` (nur der
  Variablenname wurde gelesen, nie der Wert).
- Der Agent las bisher mit dem Hauptclient vor (`llm_service.speak` → `self.client`).

## Änderung

- **Agent:** neue Einstellung `openrouter_tts_key` (Umgebungsvariable `OPENROUTER_TTS_KEY`, gleicher
  Name wie bei Hermes). `LLMService._vorlese_client()` baut bei gesetztem Schlüssel einen eigenen
  Client (einmal, wiederverwendet), sonst gilt der Hauptclient. `speak()` nutzt ihn; das Log nennt
  nur „Schlüssel: eigener|haupt", nie den Wert.
- **Selbsttest:** `sprache.vorlese_schluessel` = `eigener` | `haupt` (nur die Art).
- **Handy:** gemeinsames Skript `termux/schluessel-uebernehmen.sh <env> <übergabe> <titel> <PFLICHT>
  [WEITERE]` — die Logik der pCloud-Übernahme, jetzt mit Namen als Parameter.
  `termux/pcloud-schluessel-uebernehmen.sh` ruft es nur noch mit den pCloud-Namen auf (eine Logik
  statt zwei). Alle drei Startwege (`start-termux.sh`, `termux/agent-start`,
  `termux/agent-ensure.sh`) übernehmen zusätzlich `vorlese_schluessel.txt` → `OPENROUTER_TTS_KEY`
  — nach dem Git-Abgleich, vor dem Serverstart, mit `|| true`. Nur die genannten Namen werden
  übernommen, `<env>.vorher` sichert den alten Stand, die Übergabedatei wird nach erfolgreicher
  Übernahme gelöscht, Werte werden nie ausgegeben.
- **PC:** `tools/handy/vorlese_schluessel_senden.py` liest genau `OPENROUTER_TTS_KEY` aus der
  Hermes-.env (prüft, dass er wie ein OpenRouter-Schlüssel aussieht), legt ihn per `adb push` als
  `/sdcard/Download/vorlese_schluessel.txt` ab, prüft die Größe am Handy und entfernt die lokale
  Zwischendatei in jedem Fall. Trockenlauf ist Standard; `--senden --neustart` startet Termux über
  die App neu und wartet, bis die Übergabedatei verschwunden (= übernommen) ist. Der Wert erscheint
  nirgends in der Ausgabe.
- `backend/.env.example`: `OPENROUTER_TTS_KEY=` (leer, optional).

## Bedienung (Sebastian, ein Befehl am PC, Handy am Kabel)

```
backend/.venv/Scripts/python.exe tools/handy/vorlese_schluessel_senden.py --senden --neustart
```

Danach zeigt der Selbsttest in der App bei „Sprache" den eigenen Schlüssel; die Kosten stehen bei
OpenRouter unter dem Vorlese-Schlüssel.

## Prüfung

- Neu `backend/tests/test_vorlese_schluessel.py` (16 Tests, erfundene Werte): Rückfall auf den
  Hauptclient, eigener Client einmal gebaut, `speak` nutzt ihn und loggt den Wert nicht,
  Selbsttest nur mit der Art; Skript übernimmt nur erlaubte Namen, sichert, löscht die Übergabe,
  lässt sie ohne Pflichtzeile liegen, gibt keine Werte aus; jeder Startweg ruft es genau einmal
  (`|| true`, nach dem Pull, vor dem Serverstart); PC-Werkzeug: Trockenlauf ohne Wert in der
  Ausgabe, Exit 2 bei fehlender/unplausibler Quelle, genau eine Zeile übertragen, Zwischendatei
  auch bei Fehlern weg, Neustart wartet auf die Übernahme.
- Bestehende `test_pcloud_schluessel_uebernahme.py` (9) unverändert grün — gleiche Wirkung über
  das gemeinsame Skript.
- Prüfbefehl: siehe Commit.
