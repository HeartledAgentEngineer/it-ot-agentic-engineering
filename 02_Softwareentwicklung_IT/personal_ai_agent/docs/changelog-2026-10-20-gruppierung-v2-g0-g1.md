# Gruppierung v2 — G0/G1 fail-closed (Plan-Fassung 5.3, Auflage 2)

Datum: 20.10.2026 (autonomer Cron-Lauf). Projekt: `02_Softwareentwicklung_IT/personal_ai_agent`.
Vorgänger: `docs/changelog-2026-10-20-gruppierung-v2-fail-closed.md` (Auflage 1 + Schreib-Tor,
Plan-Schritt 1). Dieser Schritt baut **Auflage 2** der Fassung
`.hermes/plans/2026-10-20_gruppierung-v2-fassung5.md` (in R9 = **FREI** freigegeben).

## Warum

Zwei Lücken waren im Ist-Stand belegt:

* Eine **fehlende** Regeldatei (`personen_bestaetigt.json`, `personen_vorgaben.json`) galt als
  **leerer Bestand** — v2 hätte auf einer unbekannten Grundlage gerechnet und geschrieben.
* Eine **halb übertragene** Datei fiel niemandem auf: es gab keine Messung, die die Kopie am PC
  gegen die Datei am Handy hält. Und der Zustand `vorlaeufig`/`veraltet`
  (`gruppierung_bewerten.grundwahrheit`) wurde nur **angezeigt** — er stoppte nichts.

## Was jetzt gilt (codegenau)

**G0 — Pflichtquellen und Vollständigkeitsnachweis** (`tools/foto_sortierung/personen_gruppieren.py`):

* `bestaetigt_lesen(pfad, pflicht=True)` / `vorgaben_lesen(pfad, pflicht=True)`: fehlt die Datei,
  kommt ein `PersonenFehler` statt eines leeren Bestands. `main()` liest beide **vor jedem Rechnen**
  so, sobald `--verfahren v2` gesetzt ist; der Text nennt nur den **Dateinamen**.
* Neu `geraetestand_lesen(pfad)`: liest den Gerätestand; fehlt er → `None` (= kein Gerät),
  vorhanden aber unlesbar → `PersonenFehler` (fail-closed, kein „dann eben ohne Gerät“).
* Neu `entscheidungen_pruefen(bestaetigt, vorgaben, geraetestand, stand_zuordnung)`: vergleicht je
  Pflichtquelle **sha256**, **Bytezahl** und die **durchgezählten Einträge** der PC-Datei gegen die
  Angaben des Gerätestands, dazu den **Stand** des Geräts gegen die bestehende Zuordnung. Rückgabe
  `{erbracht, abweichung, gruende, zeilen}` — **nur Dateinamen und Zahlen**, kein Pfad, kein Inhalt.
  Der Eintrag wird erst unter dem Namen der verglichenen Datei gesucht, dann unter dem Standardnamen
  des Geräts (ein umbenannter Pfad geht damit nicht still durch).
* Neu `g0_pruefen(args, schreiben_an)`: fasst G0 **und** G1 zusammen und läuft in `main()` vor jedem
  Rechnen. Ergebnis:
  * **Abweichung** (sha256/Bytezahl/Zahl/Stand) → **Exit 2**, kein Rechnen, kein Schreiben.
  * **Nachweis nicht erbracht** (kein Gerätestand oder ohne Zählung) → ohne
    `--ohne-geraetenachweis` **Exit 2**; mit dem Schalter nur eine **Trockenmessung** (Warnzeile);
    zusammen mit `--schreiben` **Exit 2**.
  * **G1:** `vorlaeufig` oder `veraltet` → `--schreiben` **Exit 3** (auch für den Kandidatenordner);
    die Trockenmessung bleibt erlaubt (Sebastians Weg bleibt derselbe: Trockenlauf mit `--bewerten`).
* Neue Schalter: `--geraetestand <datei.json>` (Standard `~/foto_sortierung/geraetestand.json`) und
  `--ohne-geraetenachweis`. Der Widerspruch `--nachtragen` + v2 wird jetzt **vor** G0 gemeldet
  (reine Argumentprüfung), damit die Meldung dieselbe bleibt.

**Gerätestand am Handy** (`termux/rueckweg-bereitstellen.sh`):

* `RUECKWEG_PFLICHT` (die zwei Pflichtdateien): fehlt eine **oder der Quellordner**, endet das Skript
  mit **Exit 1** und nennt sie — und **kopiert nichts**. Der App-Start bleibt unberührt, weil der
  Aufrufer (`termux/start-vorbereiten.sh`) das Skript mit `|| true` startet.
* Neu wird `geraetestand.json` **erzeugt** (kein Kopiervorgang): `stand` (UTC), je Pflichtdatei
  `bytes`, `sha256` und `zaehler`. Die Zählregeln sind dieselben wie auf dem PC (benannte Kennungen +
  Namen bzw. die vier Listenlängen). Ohne `sha256sum`/`date` oder ohne **benutzbares** Python
  (`python3`/`python`, wirklich aufrufbar — die Windows-Store-Attrappe fällt durch) wird **kein**
  Gerätestand erzeugt und das ehrlich gemeldet; der Nachweis gilt dann als nicht erbracht.

**Weg des Gerätestands zum PC** (`tools/handy/rueckweg_holen.py`):

* `GERAETESTAND = "geraetestand.json"`, `GEHOLT_NAMEN = ERLAUBTE_NAMEN + (GERAETESTAND,)` — geholt
  wird der Stand zusätzlich. Gegenüber dem letzten Commit wächst `ERLAUBTE_NAMEN` von **2 auf 4**
  Namen (die zwei Entscheidungsdateien; Rest vom 15.10. „G0, Inhalt statt Größe“, jetzt
  mitcommittet); der Gerätestand kommt als eigene Holdatei (`GEHOLT_NAMEN`) dazu, nicht in diese Liste.
* Die Nachweisdatei wird **nicht ins Manifest gebucht** (eigene Berichtszeile „Nachweis des Geraets,
  wird nicht ins Manifest gebucht“, Zähler `nachweis`). Grund: das Manifest belegt geholte **Daten**
  und speist die Rückweg-Prüfzeile in `bestand_pruefen.py`, deren Liste
  (`STANDARD_RUECKWEG_NAMEN`) dieselbe ist wie `ERLAUBTE_NAMEN`; eine Buchung ohne jene Liste
  erschiene dort als Buchung „außerhalb der Liste“. Der Gerätestand ist eine **Nachweisdatei, kein
  Datenbestand** (so steht es im Code-Kommentar in `rueckweg_holen.py`) und gehört deshalb nicht ins
  Manifest. `STANDARD_RUECKWEG_NAMEN` in `bestand_pruefen.py` wird in diesem Commit von 2 auf **4 Namen**
  gebracht (genau dieser eine Hunk, mit dem passenden Test-Hunk in
  `test_bestand_und_handy_uebergabe.py`); der übrige Teil beider Dateien (Fremdstrang „ausgelieferte
  Frontend-Dateien“) bleibt ein eigener, offener Strang und ist **nicht** Teil dieses Commits.

Der Commit enthält außerdem den 15.10.-Rest „G0, Inhalt statt Größe“ (`rueckweg-bereitstellen.sh`:
`gleicher_inhalt`; `rueckweg_holen.py`: sha256-Vergleich; Tests `g0_stufe1`/`g0_stufe2`), dessen
Beschreibung schon in `docs/changelog-2026-10-14-gruppierung-v2.md` steht.

## Belege (in diesem Lauf selbst ausgeführt)

| Prüfung | Ergebnis |
|---|---|
| neue Datei `backend/tests/test_gruppierung_v2_g0_g1.py` | **30 Prüfungen** grün (Tabelle unten) |
| `test_gruppierung_v2_fail_closed.py` + `test_personen_gruppieren_v2.py` + `test_gruppierung_bewerten.py` + `test_personen_gruppieren.py` | **144 passed** |
| `test_rueckweg_handy.py` + `test_bestand_und_handy_uebergabe.py` | **146 passed** — Lauf auf dem **Arbeitsbaum inklusive des offenen Fremdstrangs** (Frontend-Teil), nicht auf dem Commit-Stand allein |
| Bash-Sandkasten | Pflichtdatei fehlt → **Exit 1**, nichts kopiert; alle vier Dateien → **Exit 0**; Gerätestand geschrieben (sha256/Bytes/Zählung nachgerechnet) **und** von `entscheidungen_pruefen` akzeptiert (`erbracht: True`) |
| voller Prüfbefehl | siehe Commit (Haken) |

Die zehn Fälle des Prüfkriteriums der Auflage 2, je einzeln:

1. fehlende `personen_bestaetigt.json` → Exit 2 (kein Rechnen), 2. fehlende `personen_vorgaben.json`
→ Exit 2, 3. v1 ohne die Dateien bleibt erlaubt (Exit 0), 4. Trockenlauf ohne Nachweis → Exit 2 mit
Hinweis auf `--ohne-geraetenachweis`, 5. Trockenmessung mit Schalter → Exit 0 + Warnzeile, nichts
geschrieben, 6. `--ohne-geraetenachweis` + `--schreiben` → Exit 2, 7. gültiger Nachweis + volle
Grundwahrheit → Schreiben in den **Kandidatenordner** (produktiv unberührt), 8. sha256-Abweichung →
Exit 2, 9. **Zahl weicht ab → Exit 2** (sechs Felder einzeln geprüft, dazu Bytezahl und fehlende
PC-Datei = „vorhanden, aber halb übertragen“), 10. Gerätestand älter als die Zuordnung bzw. unlesbare
Standzeit → Exit 2; G1: `vorlaeufig` → Exit 3, `veraltet` → Exit 3, je ohne Datei, Trockenmessung
erlaubt.

## Ehrliche Grenzen

* Gebaut sind **Auflage 2** und der Handy-Weg dazu. **Nicht** gebaut: Auflage 3 (Aliasmengen — im
  Gerätestand und in `entscheidungen_pruefen` gibt es keine Aliase, die Sperrzahlen (a)/(b) sind
  weiterhin dieselbe Zahl), Auflage 4 (transaktionales Schreiben, `--rueckrollen`/`--weiter`),
  Auflage 5 (Basisschnappschuss) und die Pass/Fail-Zeilen 3/8.
* Der Stand-Vergleich hat eine **Uhren-Toleranz** von 120 s (`STAND_TOLERANZ`): Handy- und PC-Uhr
  laufen nicht sekundengenau gleich. Ein Zweitlauf nach einem Schreiben gilt deshalb als **veraltet**,
  bis die Entscheidungen frisch vom Handy geholt sind — genau die gewollte Sperre; das steht in den
  Tests als eigener Fall.
* Die **Zählregeln** stehen zweimal (Bash/Python auf dem Gerät, Python am PC). Sie sind inhaltlich
  festgelegt und durch die drei Handy-Tests gegengeprüft (Gerätestand → PC-Prüfung `erbracht`); ein
  eigener Cross-Test für alle Sonderformen fehlt.
* Der Gerätestand wird **nicht gebucht** (siehe oben) — er ist Nachweisdatei, kein Datenbestand.
* Kein Bild-, Vision- oder pCloud-Zugriff, keine `.env` gelesen, keine Geräteeingriffe, keine echten
  Personennamen in Berichten, nichts gelöscht, kein `git add -A`. **Kosten 0 USD** (keine
  Modellaufrufe, alle Prüfungen offline).

## Nächster Schritt

Plan-Schritt 3 der Fassung 5.3: **Aliasmengen + Konflikte (Auflage 3)** — dieselbe Stelle, an der die
Sperrzahlen (a)/(b) getrennt werden.
