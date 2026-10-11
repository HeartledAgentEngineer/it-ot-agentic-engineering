# WhatsApp kommt im Chat an — der Standardweg in die Archive

Stand: 11.10.2026, Nachtlauf. Sebastians dritter Befund aus dem Chat vom
10.10. um 07:00: „**WhatsApp fehlt vollständig** — es kommt kein einziger
Zusammenhang aus den WhatsApp-Daten, obwohl dort die meiste Historie steckt."
Der Bestand war längst da (241.402 WhatsApp-Nachrichten, 21.788 Chunks mit
echten Vektoren im Archiv-Index) — es fehlte die **Laufzeit-Verbindung**.

## Der Bruch (war schon belegt)

Der Agent hatte zwei Wege in die alten Gespräche:

| Dienst | Quelle | Vektoren |
|---|---|---|
| `services/archiv_suche.py` (**voll**) | Index mit WhatsApp-Vollbestand | in der Datenbank (21.788 WhatsApp-Chunks) |
| `services/archiv_service.py` (**alt**) | derselbe oder der alte Heimindex | externe Datei `archiv_vektor_path`, 30.891 × 1024 = Stand **vor** dem WhatsApp-Import |

Die **Standard-Suche** des Chats (`router/chat._archiv_treffer`), die
**Archiv-Notiz** (`router/chat._archiv_tool`) und das **Modell-Werkzeug**
`archiv_suchen` (`services/werkzeuge.py`) fragten den **alten** Dienst. Auf dem
Handy las der alte Dienst `~/memory.db` — eine Kopie von **vor** dem
WhatsApp-Import. Deshalb: „nicht verknüpft". Der Erwähnungsweg („was habe ich
mit X gemacht") war als einziger schon auf den vollen Index umgestellt.

Warum das bis jetzt liegen blieb: der Umbau galt als „halbgetestet ohne Handy
am Kabel" — die beiden Dienste geben **verschiedene Formen** zurück (Liste vs.
Dict mit `treffer`), und die Handy-Pfad-Frage war am PC nicht abschließend zu
messen. Beides ist inzwischen auflösbar: die Form über einen Adapter, der Pfad
über einen harten Rückfall (und der Handy-Log vom 10.10. belegt, dass der volle
Index auf `/sdcard/Download/archiv_index.db` dort **gefunden und gelesen** wird).

## Was geändert wurde

- **Neu `services/archiv_standard.py`** mit `StandardArchiv` — die eine Stelle,
  die die Wahl trifft: **erst der volle Index, dann der alte.**
  * voller Index vorhanden → er wird gefragt; liefert er Treffer, ist er es.
  * liefert er nichts, wirft er, oder ist er nicht erreichbar → der **alte**
    Dienst trägt (Rückfall, plus zweite Chance bei leerem Ergebnis).
  * ist keiner erreichbar → `is_available` ist ehrlich `False`, `hybrid`
    liefert eine **leere Liste statt einer Ausnahme** (kein Chat wird
    lahmgelegt, nichts wird still verschluckt).
  Beide Rückgabeformen werden **in der Adapter­schicht** auf eine Liste
  gebracht (`_als_liste`) — die Dict-Form (`treffer`/`sicher`/`grund`) leckt
  nicht nach außen. `quelle` sagt „voll"/„alt"/None (nur zum Nachweis).
- **Verdrahtet an drei Stellen** (vorher: alter Dienst):
  `router/chat._archiv_treffer`, `router/chat._archiv_tool` (Default-Dienst)
  und `services/werkzeuge._archiv_suchen`.
- Die beiden alten Dienste selbst sind **nicht angefasst** — kein neuer Pfad,
  kein Datenverlust, keine Löschung. Ohne vollen Index verhält sich alles
  exakt wie vorher.

## Belege

- **Tests:** neue Datei `backend/tests/test_archiv_standard.py` — 11 Tests:
  Form-Übersetzung, Vorrang des vollen Index (der alte wird dann gar nicht
  gefragt), Rückfall bei fehlendem Index, Rückfall bei Ausnahme, zweite Chance
  bei leerem Ergebnis, ehrliches „keiner erreichbar" ohne Ausnahme, Ausnahme
  auch im alten Dienst, Verdrahtung in Chat **und** Werkzeug, `top_k`
  durchgereicht. Die zwei bestehenden Werkzeug-Tests, die nur den alten Dienst
  ersetzten, prüfen jetzt den **Rückfall-Weg** (voller Index aus) — ihr Inhalt
  (Quelle + Datum + Fluss-Anweisung, „nicht erreichbar") bleibt wortgleich.
- **Prüfbefehl des Projekts** (`backend` → `pytest tests/ -q`): siehe Commit
  (Exit 0, Zahlen dort).
- **Messung am echten Bestand** (nur lesend, kein Bild-, kein Gesichtsdienst;
  nach außen geht nur die Suchfrage an die Einbettung, nie ein Inhalt):
  * `voll (archiv_suche) vorhanden: True` → `…\Chats von GPT, GEMINI,
    Claude\db\archiv_index.db`; `alt (archiv_service) vorhanden: False` (am PC
    ist `archiv_db_path` leer) → **Standardweg trägt „voll"**.
  * Standardweg `„Urlaub"`: 5 Treffer, Quellen `{google-kalender: 2,
    whatsapp: 2, chatgpt: 1}` — **WhatsApp kommt an**.
  * Standardweg `„Geburtstag"`: 5 Treffer `{google-kalender: 2, whatsapp: 3}`.
  Vorher lieferte die Standard-Suche am PC **0** Treffer (alter Dienst nicht
  verfügbar) — dieselbe Lücke wie am Handy, nur sichtbarer.

## Doku nachgezogen

`docs/spec-tool-use-v1.md` (Werkzeug `archiv_suchen` → Dienst
`archiv_standard.StandardArchiv.hybrid`, Hinweis „inklusive
WhatsApp-Vollbestand") und `README.md` (Dienst-Baum um `archiv_standard.py`).

## Ehrlich offen

- **Am Handy gegengeprüft ist es noch nicht.** Der Pfad ist über den Rückfall
  abgesichert, und der Handy-Log zeigt, dass der volle Index dort liegt — ob
  die Antworten den gewünschten Zusammenhang zeigen, bestätigt nur ein Blick
  am Gerät.
- Der Erwähnungsweg („was habe ich mit X gemacht") lief schon vorher über den
  vollen Index und ist unverändert.
