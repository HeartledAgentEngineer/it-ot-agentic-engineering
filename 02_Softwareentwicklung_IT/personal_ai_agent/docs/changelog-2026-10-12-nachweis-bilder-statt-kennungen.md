# Nachweis: „8 Fotos ohne Beschreibung" sind in Wahrheit 5 Bilder

Datum: 12.10.2026, Nachtlauf. Werkzeug: `tools/foto_sortierung/bestand_pruefen.py`.
Nur lesend, nur Zahlen, kein Bild- oder Gesichtsdienst, keine pCloud-Schreibzugriffe.

## Warum

Die Ergebniszeile des Nachweises nennt seit dem 10.10. „8 Fotos ohne Beschreibung"
(Union-Plan `sortierplan_reich_gesamt.json`, 23.908 von 23.916). Auf genau dieser Zahl
steht die Kostenentscheidung: ein Nachzieh-Lauf mit Vision kostet Geld, und Sebastian
entscheidet, ob er ihn will.

Gemessen (12.10., nur lesend) war die Zahl aber **zu hoch angesetzt**:

- Eine **Kennung ist eine Datei, kein Bild.** Dasselbe Foto kann unter zwei Kennungen im
  Plan stehen (zwei Ordner, derselbe Dateiname).
- Von den 8 fehlenden Kennungen sind zwei **Paare desselben Namens** (2 × `2021 12 26 6.jpg`,
  je 188.817 B; 2 × `IMG_9329.JPEG`, je 1.051.966 B) → 2 Bilder weniger.
- Ein weiteres fehlendes Bild trägt einen Namen, der unter einer **anderen Kennung schon
  beschrieben** ist → auch dafür ist kein zweiter Vision-Aufruf nötig.

Damit bleiben **5 verschiedene Bilder ohne Beschreibungstext** statt 8, und **2 davon sind
Dubletten**, also eigentlich **3 Bilder, für die es noch keinen Text gibt**.

Der technische Grund der drei nicht ladbaren Dateien ist gemessen worden, statt ihn zu
vermuten: alle drei sind `.jpg` — das Format ist also **nicht** die Ursache, es sind die
Dateien selbst. Genau deshalb nennt der Bericht die Endungen.

## Was gebaut wurde

1. `gesamtplan_lesen()` liefert zusätzlich `namen_je_kennung` (Kennung → Dateiname, klein
   geschrieben). Der Name wird **nur intern** zum Bündeln benutzt, nie gedruckt.
2. Neu `bilder_zaehlen(fehlende, namen_je_kennung, beschrieben)` — rechnet Kennungen in
   Bilder um: `kennungen`, `bilder`, `doppelte_kennungen`, `ohne_name`,
   `anderswo_beschrieben`, `bilder_ohne_text`. Ohne Namenskarte bleibt alles 0 (nichts
   geraten).
3. Neu `endungen_zaehlen(kennungen, namen_je_kennung, max_endungen=3)` — Endungen als
   Formatangabe (`.jpg`, `.webp`, `(ohne Endung)`), gedeckelt und zusammengefasst.
4. Der Bericht hat zwei neue Zeilen, **nur wenn sie etwas sagen**:
   - `Bilder statt Kennungen: 8 Kennungen = 6 Bilder (2 Kennungen sind Doppel desselben
     Namens); 1 davon ist unter einer anderen Kennung schon beschrieben - ohne
     Beschreibungstext bleiben 5 Bilder`
   - `Ohne Bildmasse (nicht ladbar): 3 - Endungen: .jpg 3`
   Ohne Doppel-Namen und ohne anderswo beschriebenes Bild erscheint die erste Zeile
   **nicht** — eine Zeile, die immer dasselbe sagt, ist Rauschen.
5. **Die Lücke selbst bleibt die Lücke** (`8 Fotos ohne Beschreibung`): es wird nichts
   schöngerechnet, nur genauer benannt. Der Nachweis hat weiterhin **5 Lücken**.

## Belege

- Tests: `backend/tests/test_bestand_und_handy_uebergabe.py` **93 → 97 Testfunktionen**
  (4 neue: Umrechnung und anderswo beschriebenes Bild, Zeile bleibt aus wenn nichts zu
  bündeln ist, Endungen der nicht ladbaren, beide Zähler tolerant und **ohne Dateinamen**),
  Lauf der Datei **97 passed**.
- Prüfbefehl frisch und vollständig: siehe Commit-Eintrag im Plan-Journal (Exit 0).
- **Messung am echten Bestand (Exit 0, nur lesend):** Ausgabe vor/nach der Änderung
  verglichen — **bis auf die zwei neuen Zeilen zeichengleich**.
- Nur Zahlen, Kennungen, Dateinamen der eigenen Ergebnisdateien und Endungen (Format, kein
  Name) im Bericht; die Tests halten mit `GEHEIMNAME.jpg` fest, dass **kein Dateiname**
  gedruckt wird.

## Ehrlich offen

- Was die 3 Bilder *sind* (Personen, Ort, Anlass), sagt das Werkzeug nicht — dafür bräuchte
  es einen Vision-Aufruf, und der ist Sebastian's Entscheidung (die Cron-Regel verbietet
  Bilddaten an fremde Modelle).
- Ob die 3 nicht ladbaren Dateien in pCloud überhaupt noch existieren, ist **offline nicht
  messbar**; das Werkzeug bleibt damit ohne Netz und in Sekunden.
- Die Zahl „2 Kennungen ohne Gruppe" und die kosten-/gerätegebundenen Punkte (25 Videos,
  WhatsApp-Verdrahtung, `eigene_orte.json`) sind unverändert.
