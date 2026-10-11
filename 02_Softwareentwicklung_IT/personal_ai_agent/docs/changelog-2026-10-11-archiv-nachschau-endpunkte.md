# Die Nachschau-Endpunkte zeigten etwas anderes als der Chat

Stand: 11.10.2026, Nachtlauf. Anschluss an
`changelog-2026-10-11-archiv-standard-voller-index.md` (Sebastians Befund Nr. 3,
„WhatsApp fehlt vollständig\").

## Der Fund

Der Standardweg (`services/archiv_standard.py`) wurde am 11.10. an **drei**
Stellen verdrahtet: die Standard-Suche des Chats
(`router/chat._archiv_treffer`), die Archiv-Notiz (`router/chat._archiv_tool`)
und das Modell-Werkzeug `archiv_suchen` (`services/werkzeuge._archiv_suchen`).

Eine **vierte** Stelle griff weiter direkt auf den **alten** Dienst zu:
`router/archiv.py` — die Endpunkte `GET /api/archiv/status` und
`GET /api/archiv/suche` (eingehängt in `app/main.py`, nur lesend, für die
Fehlersuche „ohne Umweg zu sehen, was der Speicher liefert\").

Genau das ist der wunde Punkt: eine Fehlersuche, die den **alten** Stand zeigt,
verdeckt den Fehler, den sie finden soll. Am PC gemessen (nur lesend):

| Aufruf | vorher (alter Dienst) | jetzt (Standardweg) |
|---|---|---|
| `hybrid „Urlaub\"` | **0 Treffer** | 5 Treffer `{google-kalender 2, whatsapp 2, chatgpt 1}` |
| `volltext „Urlaub\"` | (alter Dienst) | 5 Treffer `{whatsapp 4, chatgpt 1}` |
| `semantisch „Geburtstag\"` | (alter Dienst) | 5 Treffer `{google-kalender 5}` |

`alt.is_available` ist am PC `False` (kein `archiv_db_path`) → der Endpunkt
hätte **immer** eine leere Liste geliefert, obwohl der Chat über den vollen
Index WhatsApp findet. Auf dem Handy wäre es derselbe Widerspruch: der Chat
liefert WhatsApp, derselbe Suchbegriff über `/api/archiv/suche` nichts.

## Was geändert wurde

- **`services/archiv_standard.py`** — `StandardArchiv` kann jetzt **alle drei
  Suchwege** über denselben Vorrang fahren, nicht nur `hybrid`:
  * `suche()` (Volltext) → voll: `volltext_suche`, alt: `suche`
  * `semantische_suche()` → beide: `semantische_suche`
  * `hybrid()` → beide: `hybrid` (unverändert im Verhalten)
  Der gemeinsame Kern `_ueber_weg(...)` hält die Regel an **einer** Stelle
  (erst voll, dann alt; Ausnahme/leeres Ergebnis → Rückfall). Fehlt einem
  Dienst die Methode, wird er **übergangen statt zu werfen**.
  Dazu `status()`: der Stand kommt vom **tragenden** Dienst (`status` beim
  alten, `statistik` beim vollen Index) und trägt `quelle` („voll\"/„alt\"/None).
- **`router/archiv.py`** — beide Endpunkte nehmen den Standardweg; die Antwort
  von `/api/archiv/suche` trägt zusätzlich `quelle` („welcher Weg trägt\"), der
  `modus`-Schalter (`hybrid|volltext|semantisch`) bleibt unverändert.
- Die beiden Dienste selbst sind **nicht angefasst**; ohne vollen Index
  verhält sich alles wie vorher. Kein Löschen, keine neuen Daten, kein Netz
  außer der Suchfrage an die Einbettung.

## Belege

- **Tests:** `backend/tests/test_archiv_standard.py` erweitert — **21 Tests**
  (vorher 11). Neu: Volltext fragt den vollen Index und lässt den alten in Ruhe
  (Methodennamen `volltext_suche` vs. `suche`); Rückfall bei fehlendem Index;
  semantische Suche über den vollen Index; fehlende Methode wird übergangen
  statt zu werfen; Status kommt vom vollen Index (aus `statistik`) bzw. vom
  alten (`status`); ehrlicher Zustand ohne erreichbaren Dienst und ohne
  Standmethode; die Nachschau-Endpunkte laufen über den Standardweg (alle drei
  Modi, `quelle` in der Antwort); **Wächter** gegen den Rückfall: `router/archiv.py`
  enthält kein `archiv_service` mehr.
- **Prüfbefehl des Projekts** (`cd backend && .venv/Scripts/python -m pytest tests/ -q`):
  **3781 passed, 2 skipped, Exit 0** (190,6 s).
- **Messung am echten Bestand** (nur lesend, kein Bild-/Gesichtsdienst): siehe
  Tabelle oben — `standard.quelle = voll`, `status.verfuegbar = True`.

## Doku nachgezogen

`README.md`: die Zeilen zu `/api/archiv/status` und `/api/archiv/suche`
beschreiben jetzt den **Standardweg** (voller Index zuerst, sonst der alte
`memory.db`) samt `quelle` — vorher stand dort „Alter Archiv-Zugriff
(`memory.db`)\", was den tatsächlichen Chat-Weg falsch wiedergab.

## Ehrlich offen

- **Am Handy gegengeprüft ist es noch nicht** (kein Gerät am Kabel in dieser
  Runde). Der Weg ist derselbe wie im Chat und über den Rückfall abgesichert;
  ob die Antworten den gewünschten Zusammenhang zeigen, bestätigt nur ein Blick
  am Gerät.
- `eigene_orte.json` (Privatorte), die 8 Fotos ohne Beschreibung und die 25
  Videos ohne Gesichter-Lauf bleiben unverändert offen (kosten- bzw.
  gerätegebunden).
