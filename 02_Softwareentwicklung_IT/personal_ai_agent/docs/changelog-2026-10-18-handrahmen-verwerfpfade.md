# 18.10.2026 — Messung: Wo ein von Hand gezogener Rahmen verloren gehen kann (Vorbedingung für Schritt E)

**Was das ist:** eine **Messung**, keine Code-Änderung. Dieser Lauf hat **keinen** Produktivcode
geändert. Das Dokument hält den Beleg fest, den Auflage 10 der Planprüfung von Fassung 2 für
Schritt E („Gesichter manuell hinzufügen") verlangt: Die Klausel „vom nächsten automatischen Lauf
nicht gelöscht" ist **gestrichen**, weil sie keinen Pfad nannte und deshalb leer-grün geleuchtet
hätte; stattdessen muss der Pfad, der einen manuell gezogenen Rahmen verwerfen könnte, **mit
Datei:Zeile belegt** und **dann** an den Test gebunden werden.

**Basis der Zeilenangaben:** Arbeitsbaum 18.10.2026, 04:36, HEAD `941d1d0`
(`02_Softwareentwicklung_IT/personal_ai_agent`). Weil Zeilennummern in diesem Projekt schnell
veralten, steht die **Suchzeichenkette** mit dabei — wer das nachmessen will, sucht die Zeichenkette,
nicht die Zahl.

## Die belegten Pfade

| # | Datei · Funktion | Suchzeichenkette | Was verloren geht | Wie belegt |
|---|---|---|---|---|
| 1 | `frontend/app.js` · `baueBildEditor` | `const neu = [], rest = [];` (Z. 3566) … `_quizEditor.bbox_norm_live = neu;` (Z. 3577) | **Rahmen** ohne Server-Eintrag | Code gelesen |
| 1a | derselbe Block | `const gleichesBild = (_quizEditor.src === src);` (Z. 3564–3565) | **die ganze Live-Rahmenliste** bei Bildwechsel | Code gelesen |
| 1b | derselbe Editor, Referenz-Zweig | `if (optionen.refKontext) {` (Z. 3553–3558) | **alle Alt-Rahmen** (Kommentar im Code: „keine Alt-Rahmen der Quizrunde") | Code gelesen |
| 2 | `backend/app/services/gesicht_quiz.py` · `_fortschritt_roh_speichern` | `kurz = {k: v for k, v in list(best.items())[-500:]}` (Z. 392), geschrieben Z. 394 mit `"gesehen": gesehen[-2000:]` | **Bestätigung (Person + Region)** eines Bildes, sobald danach 500 andere Bilder bestätigt wurden | **selbst ausgeführt** (siehe unten) |
| 3 | `tools/foto_sortierung/gesicht_erkennen.py` · Aufruf von `vektoren_schreiben` | `anhaengen=bool(args.fortsetzen)` (Z. 1363–1364), `vektoren_schreiben` öffnet `"w"` (Z. 800, 808, 820) | **Vektoren früherer Läufe** (nicht die Rahmen selbst) | Code gelesen |
| 4 | `backend/app/services/gesicht_quiz.py` · `markiere_uebersprungen` | `def markiere_uebersprungen` (Z. 541) | **nichts** — hängt nur an `gesehen` an, leert keine Bestätigungen | Negativbefund, Code gelesen |

## Pfad 1 im Detail (der harte Fall)

`baueBildEditor` baut die Rahmenliste **ausschließlich über die Serverliste** `gesichter` neu auf:

```
for (let i = 0; i < gesichter.length; i++) { … }
_quizEditor.bbox_norm_live = neu;
```

`neu` hat danach **genau** `gesichter.length` Einträge. Ein von Hand gezogener Rahmen hat keinen
Server-Eintrag — er sitzt auf einem Index **≥** `gesichter.length` und fällt beim nächsten Öffnen des
Editors weg. Zwei Sonderfälle verwerfen noch mehr: der Bildwechsel (Z. 3564–3565 wirft die ganze
Live-Liste weg, Begründung im Code: „Rahmen gehören zum Bild") und der Referenz-Zweig
(Z. 3553–3558 legt den Editor komplett frisch an).

**Folge für Schritt E:** wer die Klausel an diesen Pfad bindet, muss **eine** der beiden Seiten
ändern — den Rahmen beim Speichern serverseitig sichtbar machen (Referenz oder Bestätigung mit
Region) **oder** die Live-Liste über die Serverlänge hinaus erhalten.

## Pfad 2, selbst gemessen (der scharfe Zahlenwert)

Messskript: `fortschritt_messung.py` (Scratch-Verzeichnis des Laufs). Es biegt den Fortschritt über
das im Code vorhandene `_FORTSCHRITT_OVERRIDE` auf eine **temporäre Datei** um — der echte
`quiz_fortschritt.json` (Sebastians Quiz-Reihenfolge) wurde **nicht** angefasst. Es ruft nur
vorhandene Funktionen auf (`bestaetigung_merken` als `_bestaetigung_merken`,
`_bestaetigte_regionen`, `_ist_bestaetigt`).

Ablauf und Ausgabe (Exit 0):

```
nach 1 Eintrag: ziel vorhanden = True
  regionen fuer ziel: [{'person': 'Anna', 'region': '0.10,0.10,0.05,0.05',
                        'bbox': [], 'bbox_norm': [], 'ref_id': ''}]
nach 501 Bildern: anzahl Schluessel = 500
  ziel noch vorhanden = False
  regionen fuer ziel (aus der Datei gelesen): []
  ist 'ziel' noch bestaetigt (ohne Katalog)? False
ERGEBNIS: markierung gefallen
```

**Folge für Schritt E:** für einen Handrahmen **ohne** Vektor ist diese Fortschritts-Markierung die
**einzige** Spur — die zweite Quelle von `_bestaetigte_regionen` (der Katalog über
`referenzen_zu_bild`) ist ohne Vektor leer. Sie überlebt damit nur das 500-Bilder-Fenster. Ein
E-Test, der das Fenster versehentlich überschreitet, würde grün leuchten, obwohl der Rahmen weg ist.

## Pfad 3 — Nebenbefund, nicht Schritt E

`vektoren_schreiben` öffnet **ohne** `anhaengen` mit `"w"`; der Aufruf übergibt
`anhaengen=bool(args.fortsetzen)`. Ein Lauf **ohne** `--fortsetzen` überschreibt also die
Vektordatei mit den eben gerechneten Zeilen. Der im Dateikopf empfohlene Aufruf (Z. 108) nutzt
`--fortsetzen` — der Schalter ist **Pflicht, nicht Kür**.

Gegenprobe zum Rahmenthema (damit die Aussage nicht zu weit greift): die Zuordnungsdatei
`gesicht_zuordnung.jsonl` wird von diesem Werkzeug **nicht** geschrieben. Gegenprobe über alle
`.py`-Dateien des Projekts: nur **lesende** Zugriffe auf diesen Dateinamen, kein Schreibzugriff.
Der nächste automatische Erkennungslauf verwirft dort also **keine** manuell gezogenen Rahmen.

## Das scharfe Prüfkriterium für Schritt E

Bisher stand nur: „Test, dass ein manuell gezogener Rahmen ohne Vektor gespeichert und als
‚unbekannt' angezeigt wird." Dieses Kriterium wird hier um die Pfade ergänzt, die es sonst
leer-grün lassen würden:

- (a) ein von Hand gezogener Rahmen **ohne** Vektor wird gespeichert und als **„unbekannt"**
  angezeigt;
- (b) er ist nach **Schließen und erneutem Öffnen desselben Bildes** noch da (bindet Pfad 1);
- (c) nach einem **Bildwechsel und zurück** ist er noch da (bindet Pfad 1a);
- (d) er ist auch dann noch sichtbar, wenn danach weitere Bilder bestätigt wurden — das
  500er-Fenster wird ausdrücklich geprüft (bindet Pfad 2).

## Was dieser Lauf nicht getan hat

Kein Schreibzugriff auf `frontend/app.js` oder `frontend/index.html` (dort arbeitete während dieser
Messung ein zweiter Strang, uncommittete Änderung 04:27, Commit-Sperre `.git/index.lock` seit 04:29 —
Regel: nie zwei Schreiber in derselben Datei). Kein Schreibzugriff auf echte Daten, kein Löschen,
kein `git add -A`, kein pCloud-Zugriff, keine Geräteeingriffe, kein Bild geöffnet oder gesendet,
kein Modellaufruf. **Kosten: 0 USD.**

**Damit ist Schritt E baureif, aber noch nicht gebaut.** Der Beleg für Pfad 1 und 3 ist Code-Lesen;
der ausgeführte Nachweis der Rahmen-Haltedauer gehört in den E-Test selbst, sobald E gebaut wird.
