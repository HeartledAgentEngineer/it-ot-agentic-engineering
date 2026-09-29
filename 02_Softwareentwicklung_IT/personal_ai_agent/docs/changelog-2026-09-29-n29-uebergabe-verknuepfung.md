# Changelog 29.09.2026 — N29: Übergabe der Verknüpfungs-Dateien ans Handy

## Was wurde geändert und warum

Beim Start auf dem Handy (`start-termux.sh`) werden Datendateien aus dem
freigegebenen Download-Ordner nach `~/foto_sortierung` übernommen (das Muster
„selbstheilende Übernahme“, Werkzeug `tools/handy/uebergabe_uebernehmen.py`).
Bis jetzt nannte die Dateiliste nur zwei Namen:

```sh
            --dateien fotos_dateien.json fotos_uebersicht.json \
            --dateien fotos_dateien.json fotos_uebersicht.json || true
```

Damit fehlten genau die drei Dateien, die die **Dienste am Handy tatsächlich
lesen** für die Verknüpfungs-Oberfläche (Erzähl-Diashow und „was war am
&lt;Datum&gt;?“). Die Dienste liefen ins Leere, obwohl der PC die Daten
bereitstellte. `start-termux.sh` wurde an **allen drei Stellen** derselben Liste
erweitert (Vorbedingungs-Schleife, Aufruf **mit** `--protokoll`, Aufruf
**ohne** `--protokoll`), jeweils in der Reihenfolge nach den beiden bestehenden
Namen:

```sh
            --dateien fotos_dateien.json fotos_uebersicht.json ereignisse.jsonl beziehungen.jsonl beziehungen.json \
            --dateien fotos_dateien.json fotos_uebersicht.json ereignisse.jsonl beziehungen.jsonl beziehungen.json || true
```

Der Kommentarblock darüber wurde auf den Titel **„Foto- und Verknüpfungs-Datendateien übernehmen“**
gezogen und um je einen Halbsatz ergänzt, wozu jede Datei am Handy gebraucht
wird.

## Die drei zusätzlichen Dateien

| Dateiname | Größe am PC | Stand | Zweck | Dienst, der sie liest |
|---|---|---|---|---|
| `ereignisse.jsonl` | 1.286.120 B (ca. 1,29 MB) | 28.09.2026 14:54 | Ereignisliste für die Erzähl-Diashow | `app/services/erzaehl_service.py` (`ERZAEHL_ORDNER`/`EREIGNISSE_DATEINAME`) |
| `beziehungen.jsonl` | 12.601.994 B (ca. 12,60 MB) | 29.09.2026 01:42 | Aussagen-Datei — Antworten auf „was war am &lsaquo;Datum&rsaquo;?“ | `app/services/beziehungen_service.py` (`BEZIEHUNGEN_DATEINAME`) |
| `beziehungen.json` | 715 B | 29.09.2026 01:42 | Übersicht (Zahlen/Tagesindex) für dieselbe Frage | `app/services/beziehungen_service.py` (`UEBERSICHT_DATEINAME`) |

`geschichten.jsonl` ist **nicht** dabei: die schreibt das Handy **selbst**
(`erzaehl_service.py`, nur anhängend) — sie kommt nicht vom PC und wird deshalb
nicht übernommen.

## Beleg: die Liste war vorher unvollständig

Alte Zeilen aus `start-termux.sh` (Zitat):

```sh
for name in fotos_dateien.json fotos_uebersicht.json; do
            --dateien fotos_dateien.json fotos_uebersicht.json \
            --dateien fotos_dateien.json fotos_uebersicht.json || true
```

Die drei von `beziehungen_service.py` und `erzaehl_service.py` gelesenen Namen
kamen darin nicht vor. Abgesichert durch die neuen Wächter-Tests (unten), die
die erwarteten Namen **aus den Dienst-Konstanten** ziehen, nicht aus dem Skript
abschreiben.

## Schutz-Eigenschaften (unverändert erhalten)

- **sha256 hart:** der Vergleich Quelle↔Ziel ist hart; eine Abweichung bricht die
  Übernahme für diese Datei ab (kein stiller Überschreib-Vorgang).
- **`*.vorher`-Sicherung:** eine vorhandene alte Fassung wird als
  `NAME.vorher` beiseitegelegt (Rückweg offen) — es wird nie ohne Sicherung
  überschrieben.
- **Idempotent:** ein zweiter Lauf mit identischem Inhalt ändert nichts
  (Status „unveraendert“).
- **Protokoll:** jeder Lauf schreibt in `$PROTO_DATEN/uebergabe_letzte.txt`
  (= `hermes_diag/uebergabe_letzte.txt` im Download-Ordner; derselbe Ordner wie
  `$DIAG`), nur anhängend (`open(..., "a")`).
- **Nichts löschen:** das Werkzeug entfernt ausschließlich die **eigene
  Übergabedatei** nach erfolgreicher Prüfung — sonst wird nichts angefasst.
- **Kein Serverstart-Blocker:** der ganze Abschnitt bleibt `|| true`-abgefangen;
  fehlt die Übergabedatei (Normalfall ab dem zweiten Start), passiert nichts.

## Tests

Neu in `backend/tests/test_uebergabe_uebernehmen.py` (offline, kein Netz, kein
Schreiben außer `tmp_path`):

- `test_waechter_startskript_uebernimmt_die_gelesenen_datendateien`
- `test_waechter_startskript_nennt_die_dateien_in_beiden_aufrufen`
- `test_waechter_startskript_faellt_durch_bei_fehlendem_ziel_oder_luecke`
- `test_waechter_prueffunktion_weist_pfadanteil_und_leeren_eintrag_ab`
- `test_waechter_erwartete_namen_deckt_alle_gelesenen_datendateien`

Der Wächter zieht **alle fünf** Namen aus den Dienst-Konstanten
(`foto_bilder.DATEIEN_DATEINAME`, `foto_uebersicht.UEBERSICHT_DATEINAME`,
`erzaehl_service.EREIGNISSE_DATEINAME`, `beziehungen_service.BEZIEHUNGEN_DATEINAME`,
`beziehungen_service.UEBERSICHT_DATEINAME`) — nicht nur die drei neuen. Damit
schlägt er auch an, wenn eine spätere Änderung einen der zwei **vorbestehenden**
Namen aus dem Startskript entfernt (Nachtrag nach der ersten Prüfer-Runde, der
genau diesen Punkt als nicht blockierend gemeldet hatte).

Prüfbefehl `cd backend && .venv/Scripts/python -m pytest tests/ -q`:
**2925 passed, 3 warnings, Exit 0** (Baseline vor dieser Änderung: 2920 passed,
Exit 0 — also genau +5 neue Testfunktionen). Neue Testdatei allein:
**74 passed, Exit 0** (vorher 73).

**Zahlen-Klarstellung (Planer, eigener Lauf):** ein zweiter Agent arbeitet im
selben Arbeitsbaum und hat während dieses Schritts `79ca465` gepusht (Anlass-Namen,
2920 auf seinem Stand); seine noch **ungestagte** Arbeit an
`tools/foto_sortierung/gesicht_erkennen.py` / `backend/tests/test_gesicht_erkennen.py`
bringt 10 weitere Testfunktionen mit. Der Schlusslauf des Planers über denselben
Befehl ergab daher **2935 passed, 3 warnings, Exit 0** (167 s) = 2925 aus diesem
Schritt + 10 fremde. Die 5 neuen Funktionen dieses Schritts sind in beiden Läufen
enthalten; gestaggt wird nur diese Schritt-Datei (kein `git add -A`).

## Offen (nicht Teil dieses Schritts)

- **PC-zu-Handy-Push per Kabel (adb) wurde NICHT gefahren** — es war kein
  Gerät angeschlossen. Der eigentliche Transfer der drei Dateien in den
  freigegebenen Download-Ordner steht also noch aus.
- **Manifest-Eintrag fehlt noch** (`manifest_handy.jsonl` ist nicht ergänzt).
- **Erster Lauf am Handy zu beobachten**: beim nächsten Widget-Tipp prüfen, ob
  die Übernahme läuft (Protokoll `hermes_diag/uebergabe_letzte.txt`) und die
  Dienste die Daten finden.
