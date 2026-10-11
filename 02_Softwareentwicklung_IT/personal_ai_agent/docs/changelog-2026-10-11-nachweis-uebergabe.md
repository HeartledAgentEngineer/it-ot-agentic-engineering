# Nachtrag 11.10.2026: Der Nachweis kennt jetzt die Uebergabe-Stufe

## Warum

Der Bestandsnachweis (`tools/foto_sortierung/bestand_pruefen.py`, „fertig ist,
was verifiziert ist") zaehlt die gebauten Stufen selbst nach: Plaene, Gesichter,
Beschreibungen, Gruppen, OSM, Bildindex, Neuausrichtung, Anlaesse, Ortsnamen,
Erzaehl-Quellen, Beziehungen, Personen, App-Uebersicht, Doppelten und Sebastians
eigene Erzaehl-Stufen. **Nicht gezaehlt war der Weg, auf dem die gebauten
Ergebnisdateien ueberhaupt aufs Geraet kommen** (Ketten-Schritt 9) — und genau
daran ist am 10.10. ein echter Fehler aufgefallen, den der Nachweis nicht haette
finden koennen:

> Im pCloud-Ordner `/Agent/uebergabe` lag noch die **alte** `bild_index.db`
> (104.251.392 B, 25.352 Bilder). Das Geraet haette beim naechsten Start eine
> unvollstaendige Bildsuche uebernommen. Gefunden wurde das **von Hand**
> (Journal 13), nicht vom Nachweis.

## Die zwei Uebertragungswege (gemessen, nicht behauptet)

| Weg | Was uebertraegt | Wohin | Katalogleiste |
|---|---|---|---|
| **Kabel** | `tools/handy/uebergabe_uebernehmen.py` (holen per `adb`) | `/sdcard/Download` → `~/foto_sortierung` | Namensliste in `termux/start-vorbereiten.sh` (12 Namen) |
| **Kabellos** | `tools/pcloud/uebergabe_hochladen.py` (PC laedt hoch) | pCloud `/Agent/uebergabe` → Geraet holt mit `termux/pcloud-uebernehmen.sh` | der Inhalt des pCloud-Ordners (8 Dateien) |

Jede Uebertragung bucht eine Zeile in `~/foto_sortierung/uebergabe_manifest.jsonl`
(ausserhalb des Repos, je Zeile `zeit`, `name`, `quelle`, `ziel`, `groesse`,
`pruefsumme`, `fileid`). Dieses Manifest stand in **keiner** Pruefzeile.

## Was geaendert wurde

Nur Werkzeug, Test und Doku — **kein Betriebs- oder Anzeigecode**.

1. **Neuer Abschnitt „Uebergabe (Handy)"** in `bestand_pruefen.py` mit dem
   Leser `uebergabe_stand_lesen(basis, manifest_name=STANDARD_UEBERGABE_MANIFEST)`
   und dem Helfer `_sha256_datei(pfad)` (blockweise, nur lesend, `None` wenn
   unlesbar). Neue Konstanten `STANDARD_UEBERGABE_MANIFEST`,
   `UEBERGABE_GLEICH`/`UEBERGABE_GEAENDERT`/`UEBERGABE_FEHLT_LOKAL`, neuer
   Helfer `_namen_kurz(...)` fuer die Berichtszeile. **Beide werfen nie.**
2. **Gezaehlt wird je uebertragener Datei** der Zustand gegen die **juengste
   Buchung** (spaeterer Lauf ueberschreibt): Groesse **und** `sha256`:
   * `gleich` — das Geraet holt nichts Neues;
   * `geaendert` — die lokale Fassung ist anders: das Geraet bekaeme beim
     naechsten Start die **alte** Fassung (der Journal-13-Fall);
   * `fehlt_lokal` — die uebertragene Datei gibt es am PC nicht mehr.
   Die lokale Fassung wird erst flach in `basis` gesucht (so legt die kabellose
   Uebergabe sie ab), dann an der im Manifest gebuchten Stelle.
3. **Ehrlich statt still — vier eigene Pruefungen:**
   * eine **geaenderte** Datei → Luecke („das Geraet holt beim naechsten Start
     die alte Fassung");
   * eine **am PC fehlende** uebertragene Datei → Luecke (Uebergabe nicht
     nachvollziehbar);
   * **kaputte Buchungen** (kein JSON, keine `name`) → Zaehler **und** Luecke;
   * eine Buchung **ohne Pruefsumme** waere nur ueber die Groesse vergleichbar →
     eigene Zeile und Luecke (dieselbe Strenge wie bei den Doppelten).
   Zusaetzlich: eine **nicht lesbare** lokale Fassung wird als solche gemeldet
   (Luecke „Stand nicht pruefbar"), nicht als „geaendert" geraten.
4. **Am PC heisst „nicht vorhanden" ehrlich „noch nicht angelegt"** und ist
   **keine** Luecke — sonst stuende dort dauerhaft ein Fehlalarm, denn der
   kabellose Weg wurde bewusst nur einmal (10.10.) gefahren. Abschaltbar mit
   `pruefen(..., uebergabe=None)`; der Modul-Docstring ist nachgezogen.
5. **Nur Zahlen und die EIGENEN Ergebnis-Dateinamen** — kein Pfad, kein Inhalt,
   keine Pruefsumme (in den Tests mit einem Fantasiepfad `C:/irgendwo` und der
   Zusicherung `str(tmp_path) not in text` festgehalten).
6. **Ehrliche Grenze (im Docstring benannt):** verglichen wird **offline** gegen
   die letzte Buchung. Aendert sich die Datei **im pCloud-Ordner selbst**
   (fremde Hand, zweiter Rechner), sieht dieser Nur-lesend-Abgleich das ohne
   Netzabruf **nicht** — das Werkzeug bleibt damit offline und in Sekunden.

## Belege

* Ein Test der Datei `backend/tests/test_bestand_und_handy_uebergabe.py` ergaenzt
  (4 neue Testfunktionen): Zaehlung/„juengste Buchung gilt" an einem stimmigen
  Manifest, geaendert + lokal fehlend + gleiche Groesse/andere Pruefsumme als
  Luecken, ehrliche Meldung ohne Manifest + Abschaltbarkeit, Leser tolerant bei
  fehlender/kaputter/fremdformatiger Datei. Lauf der Datei: **67 passed**
  (vorher 63).
* Pruefbefehl frisch und vollstaendig: **3820 passed, 2 skipped, Exit 0**
  (202,46 s) — vorher 3816, also genau die vier neuen Tests, keine Nebenwirkung.
* **Messung am echten Bestand (Exit 0, nur lesend):**
  `Uebergabe (Handy): uebergabe_manifest.jsonl: 9 Buchungen, 8 verschiedene
  Dateien (gleich 8, geaendert 0, am PC fehlt 0)` — die Uebergabe ist in allen
  acht Dateien stimmig (kein Befund). Ergebnisliste unveraendert **5 Luecken**.

## Ehrlicher Neben-Befund (gemessen, nicht geaendert)

1. **Zwei Wege, zwei Listen.** Der Kabelweg nennt **12** Dateien
   (`fotos_dateien.json`, `fotos_uebersicht.json`, `ereignisse.jsonl`,
   `beziehungen.jsonl`, `beziehungen.json`, `personen_beispiele.json`,
   `gesicht_zuordnung.jsonl`, `kontakte.json`, `fotobuch_ereignisse.jsonl`,
   `ordner_ereignisse.jsonl`, `bild_beschreibungen.jsonl`, `bild_orte.csv`); im
   pCloud-Ordner liegen dagegen **8** andere (`bild_index.db`, `orte.jsonl`,
   `bild_orte.csv`, `ordner_ereignisse.jsonl`, `bild_beschreibungen_reich.jsonl`,
   `bild_beschreibungen_papa_reich.jsonl`, `gesicht_zuordnung.jsonl`,
   `personen_beispiele.json`). Auf dem kabellosen Weg kommen damit z. B.
   `ereignisse.jsonl`, `fotobuch_ereignisse.jsonl`, `beziehungen.jsonl`,
   `beziehungen.json` und `bild_beschreibungen.jsonl` **nicht** ans Geraet.
   Ob das gewollt ist, entscheidet Sebastian — geaendert wurde nichts.
2. **Kein Backend-Dienst liest die reichen Beschreibungen.** Gemessen im eigenen
   Code (`grep bild_beschreibungen backend/app`): der einzige Leser ist
   `erzaehl_service.BESCHREIBUNGEN_DATEINAME = "bild_beschreibungen.jsonl"`
   (Bild-Info „was ist auf dem Bild, wo entstand es"). Die **reichen** Dateien
   (`bild_beschreibungen_reich.jsonl`, `..._papa_reich.jsonl`,
   `..._rest_reich.jsonl`) liest kein Dienst — sie liegen am Geraet, aber
   ungenutzt; und die knappe Datei, die der Dienst liest, steht nur auf der
   Kabel-Liste. Der Plan haelt die Entscheidung ausdruecklich offen („erst wenn
   Sebastian sie geprueft hat, wird entschieden, ob der alte Bestand ersetzt
   oder als zweite Quelle gefuehrt wird") — deshalb gemessen und benannt, nicht
   umgebaut.

## Ehrlich offen (unveraendert)

5 Luecken: 8 Fotos ohne Beschreibung und 25 Videos ohne Gesichter-Lauf (bezahlte
Netzaufrufe, Sebastians Entscheidung), WhatsApp-Verdrahtung (Geraet) und die
2 Kennungen ohne Gruppe (Journal 23). Nichts geloescht, kein Bild- oder
Gesichtsdienst aufgerufen, keine Geraeteeingaenge, keine kostenpflichtigen
Massenlaeufe.
