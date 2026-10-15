# Umfang der Volltextsuche gemessen — was der Wissensspeicher wirklich durchsucht

Datum: 15.10.2026 · Anlass: **Punkt 6 der Wunschliste** (Sebastian, 14.10.2026:
„Volltextsuche über alles: WhatsApp, Gemini, Claude, Bildbeschreibungen. Anlass: Ein
Rezeptverlauf wurde nur teilweise gefunden."). Dort stehen vier Behauptungen über den
Bestand — sie waren nie gemessen. Dieses Dokument hält die **Messung** fest; gebaut wurde
nichts am Suchweg.

Werkzeug: `tools/archiv/suchumfang_messen.py` (nur lesen, nur Zahlen, kein Netz, kein
Modell, kein Bild, keine Schreibzugriffe). Prüfungen: `backend/tests/test_suchumfang_messen.py`
(14 Tests, erfundene Daten).

## 1. Was durchsucht wird (echter Bestand, wörtliche Zahlen)

`archiv_index.db` (447 MB, nur lesend geöffnet, Stand der Datei 28.09.2026):

| Quelle | Gespräche | Nachrichten | Chunks | Chunks mit Vektor |
|---|---|---|---|---|
| whatsapp | 483 | 241.402 | 21.788 | 21.788 |
| chatgpt | 109 | 19.057 | 19.443 | 19.443 |
| claude-code | 40 | 13.328 | 3.185 | 3.185 |
| gemini | 384 | 4.734 | 4.537 | 4.537 |
| claude-ai | 164 | 3.088 | 3.280 | 3.280 |
| google-kalender | 399 | 405 | 403 | 403 |
| google-notizen | 15 | 15 | 43 | 43 |
| **Summe** | **1.594** | **282.029** | **52.679** | **52.679** |

Alle 52.679 Chunks tragen einen Vektor (der Index ist vollständig eingebettet) — die
Bedeutungssuche ist nirgends blind.

**Quellen mit Bilderbezug: 0.** Kein Eintrag des Suchindex stammt aus einer Bild- oder
Foto-Quelle. Die Bildtexte liegen daneben:

* `bild_index.db`: **26.241 Bilder**, alle mit Vektor, alle mit Beschreibung
  (Stand 10.10.2026 22:30 UTC, `openai/text-embedding-3-small`, 0,019 USD).
* Beschreibungszeilen in den fünf JSONL-Dateien der Bildkette: **44.417**.

Damit ist die vierte Behauptung **bestätigt und präzisiert**: Die Bildbeschreibungen liegen
nicht im Chat-Index — sie liegen in einer **eigenen** Datei, die **kein Dienst des Backends
öffnet** (`grep` über `backend/app/**` findet nur die Statusabfrage `import_status.py`).
Beide Bestände sind groß: der Chat-Index hat 52.679 Chunks, der Bildindex 26.241 Bilder —
eine Suche über „alles" müsste beide zusammenführen.

## 2. Wie viele Fundstellen beim Modell ankommen (Belegt aus dem Code, Datei:Zeile)

| Weg | Zahl | Fundstelle |
|---|---|---|
| Fundstellen im Chat (Standardweg, Voreinstellung) | **5** | `archiv_standard.py:116` |
| Werkzeug `archiv_suchen` (Voreinstellung) | 5 | `werkzeuge.py:219` |
| Werkzeug `archiv_suchen` (Höchstwert) | **8** | `werkzeuge.py:219` |
| Zeichenkürzung je Fundstelle im Prompt | 1.200 | `llm_service.py:630` |
| Nachlesen: Kontextnachrichten (Voreinstellung / Höchstwert) | 1 / **10** | `archiv_wissen.py:85` |
| `/api/archiv/suche` (Höchstwert, Prüfendpunkt) | 20 | `archiv.py:43` |
| `/api/archiv/wissen/frage` (Höchstwert, Prüfendpunkt) | 20 | `archiv_wissen.py:69` |

Die zweite Behauptung („höchstens 8 Fundstellen kommen beim Modell an") trifft **die
Obergrenze des Werkzeugwegs** — der automatische Weg im Chat nimmt **5**. Die Prüfendpunkte
erlauben 20; sie sind Fehlersuche, nicht der Antwortweg. Im Prompt steht jede Fundstelle auf
1.200 Zeichen gekürzt; im Werkzeugweg auf 500 Zeichen.

## 3. „Es gibt keinen Weg, einen Verlauf vollständig zu lesen" — bestätigt

Gemessen an der Gesprächsgröße (nur gezählt): **größtes Gespräch 44.649 Nachrichten**,
Median 4, **473 von 1.594** Gesprächen haben mehr als 21 Nachrichten. 21 ist genau das, was
ein einzelner Leseaufruf hergibt (eine Fundstelle ± 10 Nachrichten,
`/api/archiv/wissen/original`); mehr Nachrichten je Aufruf sieht der Code nicht vor. Der
Chat bekommt 5 Fundstellen à 1.200 Zeichen — für ein Gespräch dieser Länge ist das ein
Ausschnitt, kein Verlauf. **Genau das ist der Boden für Sebastians Beobachtung**
(„Rezeptverlauf nur teilweise gefunden"): Es fehlt nicht die Datenquelle (WhatsApp ist mit
241.402 Nachrichten vollständig im Index), es fehlt ein Weg, einen **Verlauf** zu lesen.

## 4. Was dieses Werkzeug ausdrücklich nicht tut

* kein Bild geöffnet, kein Vision-Aufruf, kein Modellaufruf, kein Netzaufruf (auch keine
  Einbettung — es wird nichts gesucht, nur gezählt),
* kein Schreibzugriff: die Archive werden mit `mode=ro` geöffnet; ein Schreibversuch auf
  dieser Verbindung scheitert (eigener Test hält das fest),
* **kein Archivinhalt im Bericht** — nur Zahlen, Quellennamen und Datei:Zeile (Test mit
  erfundenen Geheimwörtern hält das fest),
* keine `.env`, keine persönlichen Pfade im Bericht, keine Geräteeingriffe.

## 5. Was daraus folgt (noch nicht gebaut)

Der Wunschliste-Punkt 6 verlangt für den Bau **erst einen eigenen Plan und eine Prüfung
durch Codex**. Der Plan liegt jetzt vor: `.hermes/plans/2026-10-15_volltextsuche-alles.md`
(außerhalb des Commits, wie alle Pläne). Er enthält die Antwort auf Sebastians Frage mit den
Zahlen aus diesem Lauf, vier Schritte mit je einem Prüfkriterium und die offenen
Entscheidungen (Sicht: nur Fundstellen oder ganzer Verlauf; Bildtexte mit in die Mischsuche
oder eigener Weg; wie „vollständig" aussieht, wenn ein Gespräch 44.649 Nachrichten hat).

Prüfbefehl, in diesem Lauf ausgeführt: siehe Commit.
