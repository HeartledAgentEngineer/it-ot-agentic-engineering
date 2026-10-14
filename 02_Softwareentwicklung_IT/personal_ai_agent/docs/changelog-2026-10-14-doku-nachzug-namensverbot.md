# Doku-Nachzug Websuche-Namensverbot: die zwei fehlenden Regeln in der Spezifikation, eine Zahl berichtigt

Datum: 14.10.2026 · Art: **reine Dokumentation** (kein Code, keine Tests, keine Läufe)
Anlass: offene Doku-Hinweise aus der Hermes-Ergebnisprüfung Runde 3
(`.hermes/pruefkreis/websuche-namensverbot-ergebnis.md`, Freigabe des Codes am 14.10. gegen 18:30) —
sie waren damals dem Master zugeordnet und lagen zwei Stunden später unverändert offen.

Zwei Kernregeln stehen seit 14.10. im Code, aber **nicht** in der Spezifikation
`docs/spec-tool-use-v1.md`. Die Spezifikation ist die verbindliche Schnittstellenbeschreibung; eine
Schutzregel, die dort fehlt, ist für den nächsten Leser nicht vorhanden. Nachgezogen, codegenau und
mit Datei:Zeile belegt:

1. **Leerer Namensbestand sperrt (nicht nur „nicht lesbar“).**
   Vorher stand in der Spezifikation nur „Liste nicht lesbar (`None`) → keine Suche“. Gemessen:
   `werkzeuge.bekannte_namen_streng()` (`backend/app/services/werkzeuge.py:559–584`) liefert `None`
   auch dann, wenn **alle** Quellen formal gültig, aber insgesamt leer sind („ein leerer Bestand ist
   von ‚nichts zu schützen‘ nicht zu unterscheiden“), und `websuche_schutz.enthaelt_namen`
   (`backend/app/services/websuche_schutz.py:126`) sperrt jede Suche bei `None`. Die Spezifikation
   nennt jetzt alle drei Fälle: unlesbar, beschädigt, leer.

2. **Längengrenze für den Suchtext des Modells.**
   `backend/app/services/web_suche.py:30–36`: `MAX_ZEICHEN = 4000` kürzt die **Antwort**;
   `MAX_ANFRAGE_MODELL = 200` begrenzt den **Suchtext**, den das Modell formuliert (Meldung
   „Suchanfrage zu lang (über 200 Zeichen) – nicht gesucht“). Der eigene Satz aus Sebastians
   Nachricht (Modus `manual`, `router/chat.py`) bleibt ohne diese Grenze. Beides stand bisher in
   keiner Zeile der Spezifikation.

Dazu eine **Zahl berichtigt, nicht geschönt:**

- `docs/changelog-2026-10-14-websuche-namensverbot.md` behauptete „97 Tests“.
  Nachgemessen am 14.10.2026: `cd backend && .venv/Scripts/python -m pytest
  tests/test_websuche_schutz.py --collect-only -q` → **96 tests collected** (die Datei trägt 47
  Testfunktionen, der Rest ist parametrisiert). Die Angabe lautet jetzt 96, samt Messbefehl.
- `02_Softwareentwicklung_IT/personal_ai_agent/CLAUDE.md` (Zeile der Websuche mit Namensverbot)
  nannte „`test_websuche_schutz.py` neu (63)“ ohne Fortschreibung und führte die Ergebnisprüfungen
  noch als **offen**, obwohl Codex (Runden 1, 2 und 4: EINWAND, Behebungen `a82549b` und `28e37b9`)
  und Hermes (Runde 2 EINWAND, Runde 3 **FREI für den Code** mit genau diesen drei Doku-Hinweisen)
  gefahren sind. Jetzt steht der gemessene Prüfstand dort; die 63 bleibt als Erstellungsstand
  stehen, mit dem gemessenen Wert 96 daneben.

## Belege (in diesem Lauf ausgeführt)

- `grep -n` in `backend/app/services/web_suche.py`, `websuche_schutz.py`, `werkzeuge.py` — die
  zitierten Zeilen und Konstanten.
- `… pytest tests/test_websuche_schutz.py --collect-only -q` → „96 tests collected in 0.63s“.
- `grep -c "^def test_" backend/tests/test_websuche_schutz.py` → 47.
- `.hermes/pruefkreis/websuche-namensverbot-ergebnis.md` (letzte Runde: Hermes, 18:3x, FREI für den
  Code) und `.hermes/pruefkreis/websuche-namensverbot-plan.md` — Quellen für den Prüfstand.

## Grenzen dieses Laufs

Keine Code-Änderung, kein Testlauf über den Bestand, kein Netz-, Modell- oder Vision-Aufruf, kein
Bild geöffnet oder gesendet, kein pCloud-Zugriff, keine Geräteeingriffe, nichts gelöscht, keine
`.env` geöffnet, keine persönlichen Dateiinhalte gelesen. Nur eigene Dokumentpfade committet
(`git commit --only`, nie `git add -A`).

**Ehrlich:** Der Arbeitsbaum ist rot — nicht durch diese Änderung, sondern durch die **uncommittete,
fremde** H2-Arbeit an `backend/app/router/auth.py`. In diesem Lauf selbst gemessen
(`pytest tests/test_datenschutz_waechter.py -q -k "offene_routen or geschuetzte_route"`): die
Wächter-Regel „Ausnahmeliste“ findet drei neue offene Routen `/api/auth/anmelden`,
`/api/auth/abmelden`, `/api/auth/sitzung`, und `/api/auth/abmelden` hat keinen
`require_api_key`-Import — genau die zwei Fehler. Die Testdatei selbst ist **nicht** geändert
(`git status`: unmodifiziert), die Ursache liegt also ausschließlich in der fremden Änderung; sie
muss bewusst in `ERWARTETE_OFFENE_ROUTEN` eingetragen oder geschützt werden (Sache des Besitzers).
Der **volle Prüfbefehl** im Arbeitsbaum, in diesem Lauf gefahren: `cd backend && .venv/Scripts/python
-m pytest tests/ -q` → **2 failed, 4321 passed, 3 skipped (305,67 s) — ROT**, und zwar genau diese
zwei Fehler. (Diese Arbeit selbst ist reine Dokumentation; der Hook führt bei Doku-Commits keine
Tests aus — die Zahl beschreibt den Zustand des fremden Baumstands, nicht sie.) Nach `AGENTS.md`
wird bei rotem Prüfbefehl nicht gepusht; der Commit bleibt lokal, bis der
Besitzer dieser Arbeit sie abgeschlossen und den Baum wieder grün hat.

**Noch offen (nicht von mir, gehört dem Master):** die Handymessung der Namensliste (lesend nicht
erhältlich) und der Handytest.
