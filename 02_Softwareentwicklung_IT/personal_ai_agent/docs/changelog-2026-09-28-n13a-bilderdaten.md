# Changelog N13a — Bilderdaten (Galerie-Vorstufe), 28.09.2026

> **Auftrag:** `docs/auftrag-n13a-bilderdaten.md` (Feinauftrag, eingefrorenes
> Schema) · **Übergeordneter Plan:** `docs/plan-nachtlauf-2026-09-26.md`,
> Schritt N13 · **Ausgeführt von:** Hermes-Subagent am 28.09.2026
> **Nicht in diesem Schritt:** die Anzeige im Frontend (das ist N13b) und die
> Übertragung der Datei aufs Handy.
> **Kein git-Befehl, kein pCloud-Aufruf, kein Netz, keine Bilddatei.**

## Warum dieser Schritt

Der Nutzer will Bilder **im Chat** am Handy sehen: Frage → Trefferliste →
Kacheln → Antippen = groß. Die Fotos-Übersicht aus N11
(`~/foto_sortierung/fotos_uebersicht.json`) trägt **bewusst keine
Datei-Kennungen** — ohne Kennung lässt sich kein Vorschaubild laden. Genau
diese Lücke schließt N13a: aus dem lokalen `sortierplan.json` entsteht eine
**zweite**, kleine Datei mit den Kennungen je Event. Die N11-Datei bleibt
unangetastet.

## Was gebaut wurde

| Datei | Art | Zeilen |
| --- | --- | --- |
| `tools/foto_sortierung/foto_dateien.py` | Werkzeug (Teil A) | 434 |
| `backend/app/services/foto_bilder.py` | Dienst (Teil B) | 385 |
| `backend/app/router/fotos.py` | **eine** neue Route `GET /api/fotos/bilder` | 188 (vorher 103) |
| `backend/tests/test_foto_dateien.py` | Werkzeugprüfungen | 755, **89 Testfunktionen** |
| `backend/tests/test_foto_bilder_endpunkt.py` | Dienst- und Endpunktprüfungen | 861, **100 Testfunktionen** |
| `docs/changelog-2026-09-28-n13a-bilderdaten.md` | diese Doku | — |

`main.py` wurde **nicht** angefasst: Der Router `app/router/fotos.py` war schon
registriert, die Route hängt damit automatisch in der App und am bestehenden
API-Key-Schutz (`require_api_key`).

**Nicht** angefasst: `backend/app/router/selbsttest.py`. Der Dienst bringt
`status_block()` mit den eingefrorenen Schlüsseln `ok`, `quelle`, `stand`,
`events`, `dateien`, `error` mit, aber das Selbsttest-Blatt nimmt ihn noch
nicht auf: `backend/tests/test_selbsttest.py:373` friert die Feldmenge der
Selbsttest-Antwort ausdrücklich ein (`set(daten.keys()) == PFLICHT_FELDER`).
Ein neuer Block dort wäre eine eigene Änderung mit eigener Prüfung — das
gehört in den Schritt, der die Anzeige baut (N13b), nicht in das
Datenfundament.

## Eingefrorenes Schema der Ausgabedatei (Version 1)

```json
{
  "art": "foto_dateien",
  "version": 1,
  "stand": "2026-09-28T09:40:00+02:00",
  "plan_stand": "2026-09-27T13:49:46+02:00",
  "zahlen": {
    "events": 2098,
    "dateien": 7616,
    "ohne_kennung": 0,
    "kategorien": 11,
    "jahre": 11
  },
  "events": [
    {
      "jahr": 2021,
      "kategorie": "Urlaub",
      "event": "2021_07 Beispiel-Event",
      "anzahl": 42,
      "dateien": [
        {"datei_id": 111111111, "name": "Beispiel-01.jpg"}
      ]
    }
  ]
}
```

* Die Beispieldaten oben sind **erfunden**; die Zahlen im Block `zahlen` sind
  die am 28.09.2026 gemessenen Werte.
* Ein Event = genau ein `(jahr, kategorie, event)`-Tripel — dieselbe
  Definition wie `events` in der N11-Übersicht.
* `dateien` enthält nur Züge mit verwertbarer Kennung; `anzahl` ist deren
  Länge. Nicht aufgenommene Züge (Kennung fehlt/untauglich, oder Jahr nicht
  als ganze Zahl lesbar) zählen in `ohne_kennung` — damit gilt
  `dateien + ohne_kennung == Anzahl der Züge`.
* Feste Sortierung: `events` nach `jahr` **absteigend**, dann `event`
  aufsteigend (Kategorie als dritter Schlüssel, damit die Reihenfolge eindeutig
  ist); `dateien` nach `name` aufsteigend, bei Gleichstand nach `datei_id`
  aufsteigend. Damit ist die Datei reproduzierbar und die Idempotenz prüfbar.
* `stand` = Zeitpunkt des Schreibens, `plan_stand` = `stand` aus dem Plan
  (hier ohne Zeitzonen-Anteil, so wie er im Plan steht).

### Endpunkt `GET /api/fotos/bilder` (eingefrorene Antwort)

Parameter: `jahr` (int), `kategorie` (Text, max. 200), `event` (Text, max.
200), `limit` (Standard 5, geklemmt 1…50), `pro_event` (Standard 40, geklemmt
1…200). **Es gibt bewusst keinen `suche`-Parameter** — der Dienst kennt die
Volltextsuche (`bilder_finden(suche=…)`), der Endpunkt reicht laut Auftrag nur
die fünf Parameter durch; ein mitgeschickter `suche`-Parameter wird von
FastAPI still ignoriert (geprüft in `test_endpunkt_ignoriert_unbekannte_parameter`).

```json
{
  "ok": true,
  "quelle": "fotos_dateien.json",
  "stand": "2026-09-28T09:40:00+02:00",
  "zahlen": {"events": 4, "dateien": 12},
  "events": [
    {"jahr": 2020, "kategorie": "WG", "event": "2020-05-01 Beispiel-Event",
     "anzahl": 3, "dateien": [{"datei_id": 111111111, "name": "Beispiel-01.jpg"}]}
  ],
  "anzahl": 1,
  "error": null
}
```

* Immer HTTP 200, immer dieselben Felder (`ok`, `quelle`, `stand`, `zahlen`,
  `events`, `anzahl`, `error`); fehlt die Datei: `ok: false`, leere
  Listen, `anzahl: 0`, `zahlen: {}`, deutscher `error` — nie ein 500er.
* `zahlen` trägt bewusst **nur** `events` und `dateien` (so steht es im
  Auftrag); `anzahl` ist die Zahl der **zurückgegebenen** Events.
* `pro_event` kürzt die Dateiliste je Event, `anzahl` je Event bleibt die
  **echte Gesamtzahl** („3 Bilder, 1 gezeigt").
* Keine Bilddaten, keine Ablageorte: geprüft mit
  `test_endpunkt_liefert_keine_bilddaten_und_keine_ablageorte` (die Antwort
  enthält weder `ziel_pfad` noch `von_ordner` noch `vorbuchung` noch
  `base64`/`thumbnail`).

## Gefahrene Befehle (echte Ausgabe)

### 1. Prüfbefehl — Basissatz

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
```

```
1876 passed, 3 warnings in 101.80s (0:01:41)
```

**Exit-Code: 0.** Baseline vor der Änderung war **1687 passed** (Exit 0);
dazu kommen 89 + 100 = **189** neue Testfunktionen → 1687 + 189 = **1876**.
Die drei Warnungen sind alt und fremd (`python_multipart`,
zwei Pydantic-V2-Hinweise in `app/config.py` und `app/models.py`).

Zählung je neuer Datei:
`grep -c '^def test_'` → `test_foto_dateien.py` **89**,
`test_foto_bilder_endpunkt.py` **100** (Auftrag: mindestens 35 im
Werkzeugtest).

### 2. Werkzeug — Trockenlauf gegen den echten Plan

```
backend/.venv/Scripts/python tools/foto_sortierung/foto_dateien.py --trocken
```

```
Fotos-Dateikennungen N13a — TROCKENLAUF (es wird nichts geschrieben)
Sortierplan: ...\sortierplan.json
Fotos-Dateikennungen N13a — Stand 2026-09-28T09:42:08+02:00 (Plan-Stand 2026-09-27T13:49:46)
Events: 2.098   Dateien: 7.616   ohne Kennung: 0
Kategorien: 11   Jahre: 11
  ... (erste 5 Events mit ihrer Dateizahl) ...
  ... und 2.093 weitere Events
ohne Bilddaten, nur Kennungen und Namen
Trockenlauf: ...\fotos_dateien.json wurde NICHT geschrieben.
```

**Exit-Code: 0.** Die Zahlen decken sich mit dem eingefrorenen Beispiel:
**2.098 Events, 7.616 Dateien, 0 ohne Kennung, 11 Kategorien, 11 Jahre.**

### 3. Werkzeug — Schreiben in einen tmp-Ordner (Beleg, dass es läuft)

Die Live-Datei `~/foto_sortierung/fotos_dateien.json` hat der **Ausführer**
**absichtlich nicht** erzeugt — das hat der Planer danach getan (Abschnitt
„Live-Beleg des Planers" unten). Geschrieben wurde in einen Arbeitsordner:

```
backend/.venv/Scripts/python tools/foto_sortierung/foto_dateien.py \
    --ausgabe "C:/tmp/n13a_probe/fotos_dateien.json" --schreiben
```

**Exit-Code: 0**, danach im Zielordner **genau eine** Datei (keine `.tmp`-Reste):

```
-rw-r--r-- 1146180  fotos_dateien.json
```

Nachgeprüft am erzeugten Inhalt (nur lesend, mit einem Auswerte-Skript):

* `art` = `foto_dateien`, `version` = 1, `stand` = `2026-09-28T09:42:23+02:00`,
  `plan_stand` = `2026-09-27T13:49:46` (so steht es im Plan).
* `zahlen` = `{"events": 2098, "dateien": 7616, "ohne_kennung": 0,
  "kategorien": 11, "jahre": 11}`.
* **Kennungsabgleich gegen den Plan:** die sortierte Liste aller
  `(datei_id, name)`-Paare aus der Datei ist **identisch** mit der sortierten
  Liste aller `(fileid, von_name)`-Paare aus dem Plan — 7.616 gegen 7.616,
  Vergleichsergebnis `True`. Es sind also echte Werte aus dem Plan, **keine
  erfundenen Kennungen**.
* `summe(anzahl)` = 7.616 = `zahlen.dateien`; `zahlen.events` = 2.098 =
  Länge der Event-Liste.
* Sortierung geprüft: `events` (Jahr absteigend, Event aufsteigend) `True`,
  `dateien` je Event (Name, dann Kennung) `True`.
* Der Plan selbst blieb unberührt: sein Zeitstempel steht weiterhin auf
  `2026-09-27T13:49:47` (Nachtlauf-Zeitpunkt, 5.590.448 Byte), und das
  Werkzeug öffnet ihn nur lesend (auch im Quelltext geprüft). Die Live-Datei
  `~/foto_sortierung/fotos_dateien.json` hat der **Planer** nach diesem Lauf
  angelegt — Zahlen dazu stehen im Abschnitt „Live-Beleg des Planers".

Zweiter Schreiblauf mit unverändertem Plan → dieselben Zahlen
(2.098 / 7.616 / 0 / 11 / 11), wieder keine `.tmp`-Reste. Zwei Läufe mit
**demselben** `stand` ergeben zeichengleiche Nutzlast:

```
zwei Laeufe identisch: True   (Nutzlast 708.561 Zeichen)
```

Die Byte-Gleichheit zweier Läufe ist zusätzlich im Test festgehalten
(`test_schreiben_zweiter_lauf_ist_byte_identisch`,
`test_schreiben_aus_dem_plan_zweimal_ist_byte_identisch`) — mit festem `stand`
sind die Dateien **hashgleich**.

### 4. Was geprüft wurde (Auszug aus dem Testbestand)

* Werkzeug: Schema-Schlüssel und ihre Reihenfolge, `anzahl` = Listenlänge,
  Züge ohne Kennung, Züge ohne Jahr, Kennung als Text, `true` ist keine
  Kennung, nicht-Objekt-Zug, `dateien + ohne_kennung == len(zuege)`,
  Sortierungen, kaputter Plan ohne Wurf, Repo-Ziel → `ValueError`/Exit 2
  (auch im Trockenlauf), atomares Schreiben ohne `.tmp`-Reste, Idempotenz,
  Klartext-Zusammenfassung, und im **Quelltext**: nur Standardbibliothek,
  genau eine Löschung (die eigene temp-Datei), keine Netz-/pCloud-Aufrufe,
  kein Bildzugriff, kein `datetime.now()` außer dem einen injizierbaren.
* Dienst: immer dieselben sechs Rückgabeschlüssel (auch ohne Datei), fremde
  `art`/`version` → `existiert: False` mit deutschem Text, kaputtes JSON,
  Ordner statt Datei, `status_block`-Schlüssel und Rückfall auf die
  Event-Liste, Filter (`jahr`, `kategorie`, `event`, `suche`, Umlaut-Toleranz,
  Vorrang von `event`), Klemmung von `limit` (1…50) und `pro_event` (1…200),
  `anzahl` bleibt die Gesamtzahl, verworfene Einträge ohne Kennung.
* Endpunkt: Route eingehängt, API-Key-Schutz (`require_api_key`), HTTP 200 im
  Erfolgs- **und** Fehlerfall, immer dieselben Felder, `anzahl` =
  Zahl der Events, keine Bilddaten/Ablageorte.
* Netz: beide Testdateien lassen **keine Namensauflösung und keinen
  Verbindungsaufbau** zu; eigene Tests sperren zusätzlich `socket.connect`
  und prüfen, dass Dienst und Endpunkt offline arbeiten.

## Live-Beleg des Planers (28.09.2026, 09:44–09:45)

Der Planer hat den ganzen Weg **am echten Bestand** gefahren (ein Skript
außerhalb des Repos, `~/AppData/Local/hermes/cache/scratch/n13a_probe.py`):

1. **`foto_dateien.py --trocken`** → Exit 0, „Events: 2.098   Dateien: 7.616
   ohne Kennung: 0", Meldung „wurde NICHT geschrieben".
2. **`foto_dateien.py --schreiben`** → Exit 0, danach existiert
   `C:\Users\sebas\foto_sortierung\fotos_dateien.json` mit
   **1.146.180 Bytes**, `art` `foto_dateien`, `version` 1,
   `stand` `2026-09-28T09:44:53+02:00`, `plan_stand` `2026-09-27T13:49:46`,
   `zahlen` `{"events": 2098, "dateien": 7616, "ohne_kennung": 0,
   `"kategorien": 11, "jahre": 11}`; erstes Event der sortierten Liste ist ein
   Anlass aus 2026 in der Kategorie `Konzerte_Party` mit 1 Datei (der echte
   Event-Name steht hier absichtlich **nicht**).
3. **Endpunkt gegen die echte Datei** (FastAPI-TestClient, kein Netz):
   `GET /api/fotos/bilder?limit=3` → **HTTP 200**, Felder
   `anzahl, error, events, ok, quelle, stand, zahlen`, `ok: true`,
   `quelle` = `fotos_dateien.json`, `stand` wie oben, `zahlen` = 2.098 / 7.616,
   `anzahl` = 3, `error` = `null`; je Event stimmt `anzahl` mit der Länge der
   Dateiliste überein (1 / 19 / 1). Ein Filter auf einen **Event-Namen** →
   HTTP 200, 1 Event (der echte Name wird hier **nicht** wiedergegeben).
4. **Kettenschluss bis zum Bild** (ein pCloud-Aufruf, **nur lesend**): für
   eine vom Endpunkt zurückgegebene Kennung lieferte
   `GET /api/cloud/thumb?groesse=120x120` → **HTTP 200, `image/jpeg`,
   4.581 Bytes, Magic-Bytes `ffd8ffe0` (JPEG), `Cache-Control: no-store`.**
   Damit ist belegt, dass die gelieferten Kennungen **wirklich** auf Bilder
   zeigen — die Kennung selbst steht hier absichtlich **nicht**.
5. **Prüfbefehl des Planers:** `cd backend && .venv/Scripts/python -m pytest
   tests/ -q` → **1876 passed, 3 warnings in 80.98s, Exit 0** (Baseline 1687).

Der Planer hat **nichts gelöscht**, keine Bilddatei gespeichert und nur die
lokale Ausgabedatei außerhalb des Repos geschrieben.

## Offene Punkte

1. **Die Datei liegt nur am PC.** `~/foto_sortierung/fotos_dateien.json`
   existiert seit dem Live-Beleg (1.146.180 Byte, 28.09.2026 09:44:53) —
   **nur am PC**. Die Übertragung aufs Handy (der Weg wie bei
   `fotos_uebersicht.json` aus N11) ist **nicht Teil dieses Schritts** und
   wurde nicht ausgeführt (am 28.09. kein Gerät per Kabel angeschlossen).
2. **Die Anzeige ist N13b.** Es gibt noch keine Kacheln, kein Großbild, keine
   Diashow und keine Chat-Anhängung mit Bildern; das Frontend kennt
   `cloud/thumb` weiterhin nicht. Der Chat nutzt für Fotos bisher nur
   `_fotos_uebersicht_tool` (N11, ohne Kennungen).
3. **Selbsttest-Blatt:** `status_block()` ist fertig und getestet, aber noch
   nicht in `selbsttest.py` verdrahtet (Begründung oben — ein Test friert die
   Feldmenge der Selbsttest-Antwort ein).
4. **Aufräum-Notiz (kein Teil des Codes):** Beim Schreibbeleg wurde der
   MSYS-Pfad `/tmp/n13a_probe` an das native Windows-Python gereicht; es hat
   ihn als `C:\tmp\n13a_probe\` gelesen und dort geschrieben (der Ordner
   `C:\tmp` existierte schon als Arbeitsablage). Dort liegt jetzt eine
   Probe-Datei von 1.146.180 Byte. Es wurde **nichts gelöscht**; der Ordner
   kann bei Gelegenheit von Hand entfernt werden.
5. **Nicht gemessen:** die Ladezeit eines Vorschaubilds am Handy, die
   Dateigröße nach einer Kompakt-Schreibweise (die Datei ist mit
   `indent=2` 1,15 MB groß) — beides ist für N13b wichtig, aber hier nicht
   gemessen und deshalb hier nicht behauptet.

## Prüfer-Befund (fremde Modellfamilie)

Prüfer `openai/gpt-5.6-luna` in frischem Kontext, **fünf Runden**:

* **Runde 1: NICHT BESTANDEN, 4 Abweichungen — alle vier betrafen die Doku,
  keine den Code.** Der Prüfer hat den Code ausdrücklich bestätigt (Prüfbefehl
  **1876 / Exit 0** in 77,52 s; Testfunktionen **89 + 100**; Trockenlauf-Zahlen
  2.098 / 7.616 / 0; Kennungsabgleich 7.616 gegen 7.616 `True`; Sortierungen
  `True`; nur eine Löschung im Quelltext = die eigene temp-Datei; `main.py`
  unverändert; N11-Datei unberührt). Beanstandet wurden: der **Eigner-Name**
  in Auftrag und Changelog (2 ×), ein **echter Ortsname** in zwei
  Schema-Beispielen des Auftrags, und die Changelog-Aussage, die Live-Datei
  existiere nicht (sie war zum Prüfzeitpunkt schon angelegt). **Alle vier
  korrigiert:** „Der Nutzer", „2021_07 Beispielort", neuer Abschnitt
  „Live-Beleg des Planers".
* **Runde 2: BESTANDEN, „Abweichungen: keine".** Eigener Lauf des Prüfbefehls:
  **1876 passed, 3 warnings in 92,13 s, Exit 0**. Eigene Nachrechnung: Datei
  **1.146.180 Bytes** (vorhanden), N11-Datei **344.615 Bytes** und Sortierplan
  **5.590.448 Bytes** unverändert; `zahlen` 2.098 / 7.616 / 0 / 11 / 11; Paare
  live gegen den Plan **7.616 gegen 7.616, identisch `True`**; Endpunkt
  `?limit=3` → Status **200**, Felder
  `anzahl, error, events, ok, quelle, stand, zahlen`, `ok`/`quelle` `True`
  `fotos_dateien.json`, `anzahl` 3, `anzahl` je Event = Länge der Dateiliste
  (1, 19, 1); alle Auftragskernpunkte (Schema, Sortierung, Repo-Ziel ⇒ Exit 2,
  `dateien_laden` wirft nie, fremde `art`/`version` ⇒ Fehler, Klemmung
  1…50 und 1…200, `anzahl` = Gesamtzahl) bestätigt. Er hat die fremden,
  nicht zu N13a gehörenden Arbeitsbaum-Änderungen ausdrücklich **nicht**
  angefasst.
* **Runde 3 (Abnahme auf dem committeten Stand `bea270d`): NICHT BESTANDEN,
  1 Abweichung.** Er hat bestätigt: `git show --stat bea270d` = **genau die
  acht** genannten Dateien, **keine** fremde (die uncommitteten
  `live_zahlen`-/`recherche`-Dateien und `tools/whatsapp/` ausdrücklich **nicht**
  im Commit), `0 0` gegen `origin/main`, Prüfbefehl **1876 / Exit 0**
  (104,05 s), `main.py` unverändert, genau eine neue Route `/bilder`,
  Repo-Ziel-Verweigerung (Zeilen 296–300) und die einzige Löschung
  (`os.remove(temp_pfad)`, Zeile 329). **Beanstandet:** im Schema-Beispiel des
  Auftrags stand eine **echte 11-stellige pCloud-Dateikennung** — die
  Beispiele müssen erfunden sein. **Korrigiert:** beide Vorkommen
  (`docs/auftrag-n13a-bilderdaten.md` Zeilen 77 und 143) tragen jetzt die
  erkennbar erfundene Kennung `47110000001`.
* **Runde 4 (Abnahme-Versuch auf `201a9cf`): NICHT BESTANDEN, 8 Abweichungen —
  6 davon „Bestand", 2 berechtigt.** Berechtigt: die Überschrift dieses
  Abschnitts nannte zu wenige Runden, und die Planzeile N13a führte nur die
  Runden 1 und 2. Beides korrigiert. Die übrigen **6 Treffer waren echte
  Dateikennungen in älteren Journal-Einträgen** (N9c/N9e) — sie standen schon
  in der Vorfassung `4c0cb36` und wurden **nicht** von diesem Schritt
  eingeführt (die Datenschutz-Regel „keine Kennung in der Doku" entstand erst
  mit dem N10-Auftrag). **Trotzdem bereinigt:** die Bilder heißen jetzt
  „Bild A/B/C/D" bzw. „Kennung des Bildes bewusst nicht genannt"; eigene
  Gegenprobe `grep -nE "[0-9]{11}"` über die drei Dokumente → **nur noch die
  erfundene Kennung `47110000001`**.
* **Runde 5 (Schlussabnahme auf dem Commit `1b66fa0`): BESTANDEN,
  „Abweichungen: keine".** Eigener Lauf des Prüfbefehls: **1876 passed,
  3 warnings in 127,01 s, Exit 0**; `grep -nE "[0-9]{11}"` über die drei
  Dokumente → **nur noch die erfundene Kennung** (sechs Treffer, alle
  `47110000001`); `git show --stat 1b66fa0` = genau eine Datei; `0 0` gegen
  `origin/main`; beide Pflichtabschnitte („Live-Beleg des Planers",
  „Prüfer-Befund") in der committeten Fassung bestätigt.

## Grenzen (eingehalten)

* Reiner Code: kein Chat-Archiv, keine Fotos, keine Erinnerungen, keine
  `.env`, keine Bewerbungen in Ausgaben oder Dateien.
* `~` und der Sortierplan nur **lesend**; es wurden keine Bilddateien
  geöffnet und keine pCloud-Aufrufe gemacht.
* Keine Datei gelöscht (einzige Löschung im Code: die eigene temp-Datei beim
  atomaren Schreiben).
* Keine Geheimnisse, keine Schlüsselwerte in Ausgaben oder Dateien.
* Kein git-Befehl.
