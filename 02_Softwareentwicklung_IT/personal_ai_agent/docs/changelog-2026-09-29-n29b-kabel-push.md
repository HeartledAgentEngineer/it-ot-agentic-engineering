# Changelog 29.09.2026 — N29b: Kabel-Push der Datendateien ans Handy (Vollzug von N29)

## Was gemacht und warum

Der Schritt **N29** hat den Übernahmeweg am Handy fertiggestellt (Dateiliste in
`start-termux.sh`), aber der **Kabel-Übertrag selbst war nicht gefahren** — es
hing kein Gerät an `adb`. Heute hängt das **Motorola Edge 50** am Kabel
(`adb devices` → Zustand `device`), damit ist der offene Schlusspunkt fahrbar.

Ziel des Schritts: die drei vom PC stammenden Datendateien liegen im
freigegebenen Download-Ordner des Handys, **byte-genau belegt**, mit
**Manifest-Einträgen** (Rückholbarkeit) — und der Übernahmeweg ist einmal mit
den **echten** Dateien durchgespielt.

## Ausgangslage, gemessen statt vermutet

Abgleich der fünf Namen zwischen PC (`~/foto_sortierung/`) und Handy
(`/sdcard/Download/`) per `md5`:

| Datei | PC | Handy vorher | Ergebnis |
|---|---|---|---|
| `ereignisse.jsonl` | 1.286.120 B, md5 `a55f254f…` | vorhanden, md5 `a55f254f…` | **schon byte-identisch** — lag bereits dort |
| `beziehungen.jsonl` | 12.601.994 B, md5 `6a5704c7…` | fehlte | **gepusht** |
| `beziehungen.json` | 715 B, md5 `313c11a9…` | fehlte | **gepusht** |
| `fotos_dateien.json` | 1.146.180 B, md5 `6a1fb211…` | vorhanden, md5 gleich | unberührt (Stand N13c) |
| `fotos_uebersicht.json` | 344.615 B, md5 `c0fe0048…` | vorhanden, md5 gleich | unberührt (Stand N13c) |

**Ehrlicher Nebenbefund:** `ereignisse.jsonl` lag bereits im Download-Ordner,
byte-identisch zur PC-Quelle — aber **nicht** im Manifest gebucht (dieses trug
nur die zwei Zeilen aus N13c). Ein früherer Schreibvorgang auf das Gerät war
also undokumentiert. Das ist als **Nachtrag** mit `art: "festgestellt"` ins
Manifest aufgenommen (Nr. `N29b-3`) — es ist **kein** neuer Schreibvorgang
dieses Laufs, und der Text der Zeile sagt das ausdrücklich.

## Der Übertrag

```
adb push ~/foto_sortierung/beziehungen.jsonl /sdcard/Download/beziehungen.jsonl
adb push ~/foto_sortierung/beziehungen.json  /sdcard/Download/beziehungen.json
```

Ergebnis: `1 file pushed, 0 skipped` je Datei, 12.602.709 Bytes zusammen,
104,2 MB/s. Der Dateizeitstempel der Quelle (29.09.2026 01:42) ist am Ziel
**erhalten** — derselbe Weg wie bei N13c.

**Gegenprobe am Gerät** (`adb shell md5sum` / `sha256sum`, direkt nach dem Push):

| Datei | Handy-Messung | PC-Messung | gleich? |
|---|---|---|---|
| `beziehungen.jsonl` | md5 `6a5704c7…` · sha256 `e0d0dc40…` | md5 `6a5704c7…` · sha256 `e0d0dc40…` | ✅ |
| `beziehungen.json` | md5 `313c11a9…` · sha256 `9ec70dc2…` | md5 `313c11a9…` · sha256 `9ec70dc2…` | ✅ |

Damit liegen **alle fünf** Dateien im Download-Ordner; die drei schon
vorhandenen wurden **nicht** angefasst (gleiche Prüfsumme = nichts zu tun).

## Übernahmeweg einmal echt durchgespielt (Wegwerf-Kopie, nichts am Gerät)

Weil der Termux-Heimordner über das Kabel **nicht lesbar** ist (App-Sandbox,
`adb shell` läuft als anderer Benutzer), wurde der Übernahmeweg mit den
**echten** Dateien auf einer Wegwerf-Kopie nachgestellt:
`adb pull` aller fünf Dateien → Übernahmewerkzeug
`tools/handy/uebergabe_uebernehmen.py` mit Quelle = Wegwerf-Download,
Ziel = Wegwerf-Heim.

| Lauf | Ergebnis |
|---|---|
| Trockenlauf (`--trocken`) | `wuerde uebernommen 5` · Fehler 0 · **nichts geschrieben** (Zielordner leer, Quelle unverändert) |
| echter Lauf (`--protokoll`) | `uebernommen 5 · uebersprungen 0 · Fehler 0`, je Datei sha256 gleich, Übergabedatei entfernt |
| zweiter Lauf | `uebernommen 0 · uebersprungen 5 · Fehler 0` — Idempotenz belegt |

Die geholten Dateien trugen dieselben Prüfsummen wie die PC-Originale (auch das
Pull-Gegenstück ist damit belegt). Die im echten Lauf geprüften sha256 sind
dieselben wie in der Tabelle oben — der Prüfsummen-Vergleich des Werkzeugs
greift also mit den heute ausgelieferten Daten.

## Manifest (Rückholbarkeit)

`~/foto_sortierung/manifest_handy.jsonl`: **897 → 2.525 Bytes**, jetzt **5
gültige Zeilen** (2 × `push` aus N13c, 2 × `push` aus diesem Lauf,
1 × `festgestellt`). Je neuer Zeile stehen Zeit, Quelle, Ziel, Größe, sha256,
md5 und der **Rückweg im Klartext**: die Übergabedatei im Download-Ordner
löschen — die PC-Originale bleiben unverändert, es wird nichts gelöscht und
nichts verschoben.

## Schutz (unverändert)

- **Nur kopieren**, nichts gelöscht, nichts verschoben; die PC-Originale sind
  nach dem Lauf byte-identisch (sha256 vor/nach gleich).
- **Keine Überschreibung ohne Sicherung:** beide gepushten Namen waren am Gerät
  noch nicht vorhanden — es wurde also nichts ersetzt. Der Übernahmeweg selbst
  legt bei einer vorhandenen Zieldatei weiterhin eine `*.vorher`-Sicherung an.
- **Keine Geheimnisse:** Dokumentiert sind Dateinamen, Größen und Prüfsummen —
  keine Dateiinhalte, keine Kontakt- oder Personennamen.
- Prüfbefehl `cd backend && .venv/Scripts/python -m pytest tests/ -q` (selbst
  gefahren, vollen Lauf): **2935 passed, 3 warnings, Exit 0** (194,5 s) —
  **derselbe Stand wie der N29-Schlusslauf**, weil dieser Schritt **keinen
  Code** enthält und damit **null eigene Testfunktionen** mitbringt. Der zweite
  Agent arbeitet weiter im selben Arbeitsbaum (Gesichter-Lauf,
  `gesicht_erkennen.py`); seine Testfunktionen sind in den 2.935 enthalten und
  werden hier **nicht** als eigene gezählt.

## Zahlen-Klarstellung (Parallelarbeit)

Der zweite Agent arbeitet weiter im selben Arbeitsbaum (Gesichter-Lauf,
`gesicht_erkennen.py`). Gestaggt wird ausschließlich diese Doku plus die zwei
Plandateien — **kein `git add -A`**, damit seine unfertige Arbeit draußen
bleibt.

## Geänderte Dateien dieses Schritts (kein Code)

| Datei | Art |
|---|---|
| `docs/changelog-2026-09-29-n29b-kabel-push.md` | neu — dieser Bericht |
| `docs/plan-nachtlauf-2026-09-26.md` | Tabellenzeile N29b + Journal-Eintrag |
| `HANDOVER-CLAUDE-CODE.md` | N29-Status **„code done, cable push pending"** → **„done"** (Code N29 + Kabel-Push N29b, Zahlen), Schrittliste „N1...N29" → „N1...N29b" |

Kein Code, kein Frontend, **kein Cache-Bump** (es wurde keine Datei unter
`frontend/` berührt).

## Prüfer (andere Modellfamilie)

`z-ai/glm-5.2`, frische Sitzung, Auftrag gegen die Sollwerte dieses Schritts:
**BESTANDEN, 0 Abweichungen.** Eigene Messungen des Prüfers: die fünf Dateien am
Gerät gegen die PC-Dateien (Größe, md5, sha256), Manifest 2.525 Bytes / 5 gültige
Zeilen mit vollständigen Pflichtfeldern und nachgerechneten Prüfsummen, genau
**eine** Löschstelle im Werkzeug, **kein** Code in diesem Schritt, eigener
Nachbau des Übernahmewegs auf einer Wegwerf-Kopie (Trockenlauf → `uebernommen 5 ·
Fehler 0` → `uebersprungen 5 · Fehler 0`), Prüfbefehl selbst gefahren (**2935
passed, 3 warnings, Exit 0**, 138,6 s — seine Zeit weicht von den 194,5 s des
Planers ab, die Zahl nicht), Datenschutz **0 Treffer** für Seriennummer,
Telefonnummern und echte Personen-/Orts-/Ereignisnamen. Eine **Beobachtung ohne
Abweichungscharakter**: die Änderung an `HANDOVER-CLAUDE-CODE.md` fehlte in der
ersten Fassung dieses Berichts — hier nachgetragen.

## Offen (ehrlich)

- **Der erste Übernahme-Lauf am Handy ist noch nicht passiert.** Er läuft beim
  nächsten Start über das Widget; Beleg ist danach
  `/sdcard/Download/hermes_diag/uebergabe_letzte.txt` (der Ordner existiert
  noch **nicht** — geprüft —, also hat bisher kein Übernahmelauf stattgefunden).
- Danach sind die Datendateien am Handy **verbraucht**: nach erfolgreicher
  Übernahme entfernt das Werkzeug die Übergabedatei, wie vorgesehen.
- **N8** (echtes Sortieren) bleibt gesperrt bis zu Sebastians Blick auf die
  39 sicheren Event-Vorschläge und die 1.146 datumslosen Dateien; die **Namen**
  der 12 Personen warten auf `personen_bestaetigt.json`.
