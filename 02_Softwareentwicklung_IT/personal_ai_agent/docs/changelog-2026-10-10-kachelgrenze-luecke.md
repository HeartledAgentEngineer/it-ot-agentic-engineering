# Die 8-MB-Kachelgrenze verwarf Papas große Fotos still als „Loch" (10.10.2026)

## Befund (gemessen, nicht vermutet)

Der Gesichtslauf für Papas 6.336 Fotos endete am 10.10. um 14:56 bei **6.311 Zeilen** — der
Prozess war weg, die Datei enthielt keinen Fehler. 25 Fotos fehlten. Zwei Nachläufe mit
`--fortsetzen` meldeten jeweils:

```
Bilder gesamt: 25   geholt: 1   ohne Gesicht: 0   Loecher: 24   Fehler: 0
```

„Löcher" heißt im `StapelLauf`: **für diesen Eintrag kamen keine Bytes** — es entsteht keine
Zeile. Die Zahl nannte aber keinen Grund.

Die Suche nach dem Grund, jeder Schritt belegt:

1. **Die Dateien existieren.** `getfilelink` per API für drei dieser Kennungen: `result=0`,
   Download-Hosts vorhanden. Kein Datenverlust.
2. **Der Download funktioniert.** `PCloudService.datei_bytes(fileid)` direkt aufgerufen:
   9.154.152 / 12.766.453 / 9.885.739 Byte — die Dateien kommen.
3. **Die Ursache ist die Größengrenze.** `KACHEL_MAX_BYTES = 8 * 1024 * 1024` (8 MB).
   Die 24 Fotos sind **9,2 bis 15,2 MB** groß:

   ```
   PCloudZuGross: Datei ist 9.2 MB gross und ueberschreitet die Obergrenze von 8.4 MB.
   ```

   `kachel_holen` fängt jede Ausnahme und gibt `None` zurück — der Grund verschwand.

Zum Vergleich: Die direkt danebenliegenden `sortierplan_papa.json`-Bytes liegen im Median bei
10,9 MB; die anderen 6.311 Papa-Fotos blieben unter der Grenze, deshalb traf es genau 24.

## Fix

`kachel_quelle(...)` bekommt einen optionalen `grund_zaehler`. Bei einer Ausnahme wird der
Grund gezählt:

| Grund | Auslöser |
|---|---|
| `zu_gross` | Ausnahmeklasse **`PCloudZuGross`** (über den Klassennamen geprüft — das Modul steckt den Dienst ein und kennt seine Klassen nicht) |
| `fehler` | jede andere Ausnahme (Netz, Dienst) |
| `leer` | der Dienst liefert leer/`None` |

`main` übergibt ein dict und meldet nach dem Lauf **eine Zeile mit dem Nachholweg**:

```
Nicht geladen: 24   davon ueber der Groessengrenze (8,4 MB): 24   Netz-/Sonstfehler: 0   leere Antworten: 0
  Zu grosse Bilder holt derselbe Lauf mit einem groesseren --max-bytes nach (z. B. --max-bytes 25165824 = 25 MB);
  es entsteht keine Vektorzeile, das Bild gilt sonst als Loch.
```

Die MB-Rechnung ist bewusst dieselbe wie in `pcloud_service` (1 MB = 1e6), damit die Grenze in
beiden Meldungen dieselbe Zahl nennt (8,4 MB).

Ohne `grund_zaehler` ist das Verhalten unverändert (Rückwärtsverträglichkeit).

## Ergebnis: Schritt 1 ist vollständig

Nachlauf mit `--max-bytes 25165824`:

```
Bilder gesamt: 24   geholt: 24   ohne Gesicht: 4   Loecher: 0   Fehler: 0   sekunden: 151.438
Metadaten: mit Aufnahmedatum: 23   mit GPS: 7
Vektorzeilen geschrieben: 24
```

`bestand_pruefen.py` (Exit 0) danach:

```
Plan sortierplan_papa.json: 6.336 Eintraege = 6.336 Fotos + 0 Videos
  Gesichter Fotos:  6.336 von 6.336 (100,0 %), davon 6.090 mit Gesicht, 0 mit Fehler
```

**Damit ist Papas Gesichtserkennung fertig** — das war der Blocker für Schritt 4
(Gruppen andocken), Schritt 5 (Anlässe) und Schritt 6 (Abschlussbericht).

## Lehre

Ein stilles Verwerfen darf nicht als grundlose Zahl enden. „Loecher: 24" sah wie ein
Netzproblem aus und war eine Konstante. Ein Lauf, der etwas **nicht** tut, muss den Grund
nennen und den Weg zum Nachholen — sonst bleibt der Nachweis eine Behauptung.

## Prüfung

- `tests/test_gesicht_erkennen.py`: **153 passed** (vier neue Tests:
  `test_kachel_quelle_zaehlt_grund_zu_gross`, `test_kachel_quelle_zaehlt_netzfehler_und_leere_antwort`,
  `test_kachel_quelle_ohne_zaehler_bleibt_still`, `test_mb_text_mit_komma`).
- Lauf am echten Bestand: 6.336 Zeilen, 24 nachgeholt, 0 Löcher.
