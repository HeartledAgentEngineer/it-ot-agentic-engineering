# Der Rückfall-Wächter gilt jetzt für alle Module

Stand: 11.10.2026, Nachtlauf. Anschluss an
`changelog-2026-10-11-archiv-nachschau-endpunkte.md` (dort wurde der **vierte**
Verbraucher gefunden, der noch direkt auf den alten Dienst griff).

## Warum diese Änderung

Derselbe Fehler ist in dieser Kette **viermal** aufgetreten: die Chat-Suche,
die Archiv-Notiz und das Modell-Werkzeug (drei Verbraucher) und zuletzt die
Nachschau-Endpunkte `router/archiv.py` griffen direkt auf den **alten** Dienst
`archiv_service` zu — jeder zeigte damit den Stand **vor** dem WhatsApp-Import.
Sebastians Befund war genau das: WhatsApp kam nicht an, obwohl die Daten längst
im vollen Index lagen.

Der Wächter von damals prüfte **eine** Datei (`router/archiv.py`). Genau dieser
enge Blick war das Problem: den vierten Fall musste ich von Hand greppen. Eine
Prüfung, die nur die Stelle ansieht, die man schon kennt, findet die nächste
nicht.

## Was geändert wurde

Nur die Testdatei — der Betriebscode ist unangetastet:

- **`backend/tests/test_archiv_standard.py`** — der Rückfall-Wächter gilt jetzt
  **repo-weit**: `_alte_dienst_importe()` läuft über **alle** `*.py` unter
  `app/` und liest die Importe mit dem **AST** (nicht per Textsuche). Ein
  Kommentar, der das Wort `archiv_service` nur nennt, schlägt nicht an; der
  Import des **Dienstes** (`from app.services.archiv_service import archiv_service`)
  schon.
  - Erlaubt sind nur der Standardweg selbst (`archiv_standard.py`) und der
    Dienst selbst (`archiv_service.py`).
  - Der Helfer `zeitraum_kurz` darf weiterhin aus
    `app.services.archiv_service` kommen — er trifft keine Suchaussage und ist
    deshalb **kein** Treffer des Wächters.
- **Selbstprobe** (`test_waechter_faengt_den_rueckfall`): ein Wächter, der nie
  etwas findet, ist eine Behauptung. Ein Test schreibt eine böse und zwei
  unbedenkliche Mini-Dateien in `tmp_path` und belegt, dass genau die böse
  gemeldet wird (und `archiv_standard.py` als erlaubt durchgeht).
- **Positiv-Seite** (`test_alle_suchverbraucher_nennen_den_standardweg`): die
  drei Suchverbraucher (`router/archiv.py`, `router/chat.py`,
  `services/werkzeuge.py`) müssen `StandardArchiv` nennen — der Rückfall ist
  nicht nur verboten, der Standardweg steht auch dort, wo gesucht wird.

## Belege

- **Tests:** `backend/tests/test_archiv_standard.py` jetzt **24 Testfunktionen**
  (26 gesammelt, `test_top_k_wird_durchgereicht` ist dreifach parametrisiert;
  vorher 21 Funktionen / 23 gesammelt). Neu: der repo-weite Wächter, seine
  Selbstprobe, die Positiv-Seite.
- **Prüfbefehl des Projekts** (`cd backend && .venv/Scripts/python -m pytest tests/ -q`):
  **3784 passed, 2 skipped, Exit 0** (203,3 s) — vorher 3781, also genau die drei
  neuen Tests, keine Nebenwirkung.
- **Messung am echten Baum** (nur lesend): der Wächter findet **0** Verstöße —
  nur `archiv_standard.py` holt den Dienst. In `chat.py`, `werkzeuge.py`,
  `llm_service.py` steht `archiv_service` ausschließlich als Herkunft des
  Helfers `zeitraum_kurz` (kein Import des Dienstes).

## Ehrlich offen

Unverändert: am Handy nicht gegengeprüft (kein Gerät am Kabel). Die 8 Fotos
ohne Beschreibung und die 25 Videos ohne Gesichter-Lauf bleiben kosten- bzw.
gerätegebunden; `eigene_orte.json` (Privatorte) bleibt Sebastians Entscheidung.
