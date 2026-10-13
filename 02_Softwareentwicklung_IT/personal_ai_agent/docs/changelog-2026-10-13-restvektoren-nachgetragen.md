# 13.10.2026 — die restlichen Vektordateien waren nie angedockt (und der Hinweis, der das künftig sagt)

Reine Daten- und Dokuarbeit am PC plus eine kleine Werkzeug-Ergänzung. Kein Bild geöffnet oder
gesendet, kein Vision-Aufruf, keine Kosten, keine Geräteeingriffe, keine pCloud-Löschung.

## Der Fund (gemessen, nicht geraten)

Die personen-Bezogene Stufe „Videogesichter angedockt" vom selben Tag (Journal 43) hatte
`video_vektoren_bildervideos.jsonl` erwischt. Beim Prüfen der übrigen Vektordateien zeigte ein
Trockenlauf von `personen_gruppieren.py --nachtragen`, dass weitere Dateien **nie** einen Lauf
bekommen hatten — ihre Gesichter lagen vollständig vor und erreichten den Personenkatalog nicht:

| Vektordatei | Gesichter in Datei | davon für die Gruppierung geeignet | davon **ohne** Zuordnungszeile |
|---|---|---|---|
| `video_vektoren_upload.jsonl` | 18.450 | 7.307 | **7.307 (alle)** |
| `personen_vektoren_gedreht_neu.jsonl` | 3.010 | 1.019 | 1.019 |
| `personen_vektoren_fotobuch.jsonl` | 1.934 | 337 | 337 |

Zusammen: **8.656 Gesichter ohne Zuordnungszeile** (2.459 waren schon vorhanden). Beim Upload-Video
waren **0 von 7.307** vorhanden — die Datei wurde also als Ganzes nie angedockt (dieselbe Familie
wie die 5.060 Videogesichter aus Journal 43: eine gebaute Stufe ohne Verbraucher).

**Ursache belegt:** `STANDARD_VEKTOREN` in `personen_gruppieren.py` nennt nur drei Dateien
(n0929_voll, n0929_bildervideos, video_bildervideos); ein `--nachtragen` fährt immer **nur** die
ausdrücklich genannten Dateien. Was niemand nennt, bleibt still liegen.

## Was geschrieben wurde

Sicherungen **zuerst als Kopien** (nichts gelöscht, keine Datei überschrieben):
`gesicht_zuordnung.jsonl`, `personen_beispiele.json`, `kennungen.json` →
`*.vorher_vektoren_rest-20261013_1520`; zusätzlich die alten `*.vorher` als `*.vorher_alt-20261013_1520`
erhalten (der Lauf legt seine eigene `*.vorher`-Sicherung an und hätte sie sonst ersetzt).

Lauf mit allen drei Dateien, `--schreiben`:

```
Neue Gesichter: 8656 (schon vorhanden, uebersprungen: 2459)
Angedockt an bestehende Gruppen: 2882 Gesichter in 357 Gruppen
Neue Gruppen: 197 (Kennungen Person_1682..Person_1878)
Nicht angedockt (Rauschen): 4350
Rechenzeit: 3.0 s
```

**Idempotenz gemessen:** derselbe Aufruf erneut (Trockenlauf) → `Neue Gesichter: 0 … 0 Gruppen`
(50.282 Zeilen, 11.115 übersprungen).

## Belege nach dem Lauf

`bestand_pruefen.py` (Exit 0):

- Gruppen **1.170 → 1.367**, Gesichter in Gruppen **26.524 → 30.830**
- Zuordnung **41.626 → 50.282 Gesichter** (63,7 % → 61,3 %; der Anteil sinkt ehrlich, weil
  Videogesichter teils Einzelgesichter bleiben)
- Ergebnis: **4 Lücken** (die fünfte — „2 Dateien seit der letzten Übergabe geändert" — ist mit
  der Übergabe unten geschlossen)

## Der neue Stand ist am Handy bereitgestellt

Trockenlauf über die acht Dateien der Übergabeliste: **6 × übersprungen (Prüfsumme gleich), 2 ×
würde hochgeladen** (genau die zwei geänderten). Dann `--schreiben`:

- `gesicht_zuordnung.jsonl` 11.987.674 B, sha256 `5c5c405f4176…`, fileid 108912351235
- `personen_beispiele.json` 1.798.614 B, sha256 `e3c3afa3659e…`, fileid 108912352107

Je eine Manifest-Zeile (jetzt 15 Buchungen / 8 Dateien). **Unabhängige Gegenprobe** statt
Erfolgsmeldung: beide Dateien frisch über `getfilelink` geladen und örtlich nachgerechnet —
Größe und sha256 **byte-gleich**. Nachweis danach: „Uebergabe (Handy): … gleich 8, geaendert 0".
Schreiben nur unter `/Agent/`, nichts gelöscht; das Gerät holt sie beim nächsten Start selbst.

## Die Werkzeug-Ergänzung (Doku folgt dem Code)

`personen_gruppieren.py` nennt im `--nachtragen`-Lauf jetzt, **welche bekannten Vektordateien
vorliegen, aber nicht Teil dieses Laufs waren** — genau der Zustand, der oben still blieb:

- neu `STANDARD_VEKTOREN_KATALOG` (die sieben bekannten Gesichts-Vektordateien, ohne Probe- und
  Altdateien) und `fehlende_vektoren(pfade, basis=None)` — nur ein Hinweis, keine Rechnung;
- die Zeile erscheint nur, wenn es solche Dateien gibt, und nennt **nur Dateinamen, keine Pfade**;
- die Liste des **vollen** Laufs (`STANDARD_VEKTOREN`) bleibt bewusst unverändert — ein voller
  Neu-Lauf zerreist benannte Gruppen und ist ohnehin gesperrt.

**Tests:** `backend/tests/test_personen_gruppieren_nachtragen.py` **22 → 25 Testfunktionen**
(3 neue: Hinweis nennt die vorliegende Datei ohne Pfad; Hinweis schweigt, wenn die Datei Teil des
Laufs ist; `fehlende_vektoren` meldet nur Vorhandenes, reihenfolgetreu, Katalog vollständig).
Dazu eine autouse-Vorrichtung, die `STANDARD_BASIS` in jedem Test auf ein leeres Ersatzverzeichnis
zeigt — kein Test liest Sebastians Foto-Ordner.

## Ehrlich offen (nicht angefasst)

- **`personen_vektoren_n0929_voll.jsonl` nennt 4.205 für die Gruppierung geeignete Gesichter ohne
  Zuordnungszeile** — die Basis-Gruppierung (vor dem 13.10.) hat sie nicht geschrieben. Ursache
  nicht abschließend belegt (Auswahl-/Schwellenunterschied zwischen vollem Lauf und Nachtrag);
  **nicht nachgefahren**, weil ein Nachfahren dieser Datei allein kein sauberes Ergebnis garantiert.
- Die kleinen **Altdateien** von Ende September (`personen_vektoren.jsonl` 20, `n9d` 65, `n9e` 65,
  `n9e_burst` 5, `n9g` 125 geeignete Gesichter ohne Zeile) sind bewusst **nicht** im Katalog —
  sie sind Teilstände, keine eigenen Stufen. Ein erneuter einzelner Trockenlauf von `gedreht_neu`
  nennt 6 solcher Gesichter (Bild-Ausschlussregel, kein eigener Stand).
- Der Nachweis erkennt diesen Fall **noch nicht selbst** (er zählt Zuordnungen, nicht Vektorzeilen
  gegen Zuordnungszeilen); die Prüfzeile dafür gehört in `bestand_pruefen.py` — dieses Werkzeug und
  seine Testdatei liegen derzeit **fremd halbfertig im Arbeitsbaum** und wurden deshalb nicht
  angefasst.
