# Changelog 2026-09-15 — Coding-Chat live stückweise + ehrlicher Neustart

## Auslöser (Sebastian, Sprachdiktat)

„Ich möchte … endgültig, dass auch alle Nachrichten, die hier ausgespuckt
werden, immer vorhanden bleiben und auch nach dem Neuladen noch da sind, bis
auf die letzte, die immer noch kommt. … dass die Gespräche auch weitergeführt
werden können, wenn der Server neu gestartet wird. … diesen Coding-Chat wirklich
aktiv nutzen, als Alternative für Hermes in der Termux-CLI. … dass die Anzeigen,
alle Mechanismen, die Hermes in Termux kann, hier können — Fragen, Interaktion
mit Fragen, Fragen anhängen. … verlässlich, und genug Feedback."

## Fix 1 — Coding-Chat (conv_code) streamt live statt blockierend

`frontend/app.js`, `sendMessage()`:

**Ursache.** Bei aktivem Hermes-Modus (`loopAktiv = true`) nahm *jeder* Chat den
Zweig `POST /api/hermes/chat`. Dieser Endpoint ist **blockierend**: Er sammelt
erst den kompletten Lauf (`list(hermes_local.stream_auftrag_query(...))`) und
liefert danach eine fertige Antwort. Das Frontend tippte sie zusätzlich
künstlich Zeichen für Zeichen nach. Ergebnis: während der Arbeit **kein
Lebenszeichen** („es hängt, kommt nicht in Schwung"), und am Ende „alles auf
einmal".

**Fix.** Der blockierende Zweig schließt `conv_code` jetzt ausdrücklich aus
(`&& state.conversationId !== 'conv_code'`). Der Coding-Chat läuft damit immer
über `POST /api/chat/stream` → Track C → `_strom_auftrag_live(...)`:

- Jeder Zwischengedanke kommt als **eigene Blase** (Backend pollt
  `~/hermes_inbox/status.jsonl` im 1-s-Takt; der Inbox-Daemon flusht alle
  `FLUSH_S = 1.2` s bzw. nach `FLUSH_MAX_ZEILEN = 6` Zeilen).
- Das Ergebnis kommt am Ende in dieselbe Blase.
- Für den Haupt-Chat (`conv_main`) bleibt der blockierende Weg unverändert.

**Beleg.** `frontend/tests/test_conv_code_live_stream.js` — neu 5/5 grün,
gegen den Stand `HEAD` 2/5 rot (also echter Regressionsschutz, kein
Alibi-Test).

## Fix 2 — Unterbrochener Lauf meldet sich ehrlich im Chat

`backend/app/services/auftrag_service.py`, `verwaiste_auftraege_schliessen()`:

**Ursache.** Beim Serverstart wurden zurückgebliebene `laeuft`-Aufträge nur im
Buch bereinigt (Status → `fehler`). Im Chat endete der Verlauf wortlos nach der
letzten Gedankenblase — der Nutzer wartete auf ein Ergebnis, das nie mehr kommt.
Nur die Wahrheit im Buch, keine im Chat.

**Fix.** Für verknüpfte Aufträge (`conversation_id` gesetzt) wird zusätzlich
eine ehrliche Assistant-Blase in **genau dieses** Gespräch geschrieben:

```
⚠️ **Unterbrochen durch Server-Neustart.**
Der Auftrag „…“ wurde nicht zu Ende geführt — es gibt kein Ergebnis.
Der Verlauf davor bleibt erhalten; bitte die Aufgabe erneut senden.
```

Der Verlauf davor bleibt vollständig (append-only) — das Gespräch ist also nach
dem Neustart fortsetzbar. Aufträge **ohne** Chat-Verknüpfung melden nichts;
fremde Verläufe werden nicht geflutet. Bewusst außerhalb der Buch-Sperre
(`_in_verlauf_anhaengen` nimmt die Verlaufs-Sperre).

**Beleg.** `backend/tests/test_verwaiste_auftraege.py::test_verwaister_auftrag_meldet_sich_ehrlich_im_chat`.

## Was bereits Reload-/Neustart-fest ist (geprüft, nicht behauptet)

- **Auswahl-/Frage-Menüs** werden bei *jedem* Rendern neu aus dem Nachrichten-
  text gebaut (`addMessage` → `parseOptionsMenue` → `bauOptionsUi`). Sie hängen
  damit nicht an flüchtigem DOM-Zustand und kommen nach Reload zurück.
- **Verlauf**: `conversations['conv_code']` wird append-only in die
  Verlaufsdatei geschrieben (`_reite_an_verlauf`, mit Rotations-Backups);
  `zeigeGespraech()` baut die Blasen daraus neu auf (letzte 60 sofort, ältere
  per Knopf). Bilder werden lazy nachgeladen.
- **Nur die letzte Blase** (die gerade streamt) ist noch nicht persistiert —
  das entspricht genau dem Wunsch „bis auf die letzte, die noch kommt".

## Verifikation

| Prüfung | Befehl | Stand |
|---|---|---|
| Coding-Chat live (neu) | `node frontend/tests/test_conv_code_live_stream.js frontend/app.js` | 5/5 grün |
| Kontrolle (alter Stand) | `git show HEAD:…/app.js` → derselbe Test | 2/5 rot (erwartet) |
| Diff-Anzeige | `node frontend/tests/test_diff_darstellung.js frontend/app.js` | 11/11 grün |
| Boxen/Verwaiste | `python -m pytest backend/tests/test_cli_ausgabe_boxen.py backend/tests/test_verwaiste_auftraege.py -q` | 10/10 grün |

Cache-Bust: `app.js?v=20260915eB` in `frontend/index.html`.