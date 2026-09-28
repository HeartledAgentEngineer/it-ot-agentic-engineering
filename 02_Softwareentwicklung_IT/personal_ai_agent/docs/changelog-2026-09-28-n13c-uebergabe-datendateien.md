# Übergabe der Foto-Datendateien vom PC aufs Handy (N13c)

**Datum:** 28.09.2026 · **Schritt:** N13c (Übergabewerkzeug + Einbau in den Start)
**Status:** gebaut und geprüft (Tests grün, Trockenlauf gefahren)

## Warum

Das Handy braucht zwei Dateien, die am PC entstehen:

| Datei | Größe | Inhalt |
|---|---|---|
| `fotos_dateien.json` | 1.146.180 Bytes | 2.098 Events, 7.616 Dateikennungen, 11 Kategorien, 11 Jahre |
| `fotos_uebersicht.json` | 344.615 Bytes | die Zahlen der Übersicht |

Beide werden vom Backend unter `$HOME/foto_sortierung/` gelesen (Dienste
`foto_bilder.py` und `foto_uebersicht.py`). Auf dem Handy fehlten sie.

Der Weg über Git scheidet aus: die Dateien tragen Dateikennungen und Namen —
also private Angaben, die nicht in ein öffentliches Repo gehören. Und der
Termux-Heimordner ist **über das Kabel nicht beschreibbar** (App-Sandbox:
`adb shell` läuft als anderer Benutzer). Deshalb der Umweg über den
freigegebenen Download-Ordner `/sdcard/Download`: der PC legt die Dateien dort
ab, das Handy holt sie beim Start in den Heimordner. Dasselbe Muster gibt es
im Startskript bereits zweimal (Archiv-Index, pCloud-Schlüssel) — hier kommt es
zum dritten Mal, mit einer Verschärfung: die Prüfsumme wird **hart** verglichen.

## Was gebaut wurde

**Neu: `tools/handy/uebergabe_uebernehmen.py`** — ein Übernahmewerkzeug ohne
Netz, ohne git, ohne Fremdaufruf. Aufruf:

    python tools/handy/uebergabe_uebernehmen.py \
        --quelle ORDNER --ziel ORDNER \
        --dateien a.json b.json [--vorher-suffix .vorher] [--trocken] \
        [--protokoll DATEI]

Je Datei aus `--dateien`, in dieser Reihenfolge:

1. **Übergabedatei fehlt** → Zähler *übersprungen*; kein Fehler, keine
   Ausgabedatei. (Der Normalfall ab dem zweiten Start.)
2. **Zieldatei vorhanden und Prüfsumme gleich** → Zähler *unveraendert*; die
   Übergabedatei wird entfernt — es gibt nichts zu übertragen.
3. **Sonst** → eine vorhandene Zieldatei wird **zuerst** nach
   `ZIEL/NAME.vorher` kopiert, dann wird atomar übertragen (temp-Datei im
   Zielordner + `os.replace`, also nie eine halbe Datei), danach Quelle gegen
   Ziel per `sha256` verglichen. Nur bei Gleichheit: Zähler *uebernommen* und
   die Übergabedatei wird entfernt. Bei Ungleichheit: Zähler *fehler*, die
   Übergabedatei **bleibt liegen**, Exit 1 — nichts wird still als Erfolg
   gemeldet.

Exit-Codes: `0` sauber (auch wenn nichts zu tun war), `1` Übernahmefehler,
`2` Aufruf-/Schutzfehler (fehlendes `--quelle`/`--ziel`, kein `--dateien`,
`--ziel` oder `--protokoll` im Repo).

Die reinen Funktionen (`sha256_datei`, `uebernahme_planen`, `uebernehmen`,
`protokoll_anhaengen`) sind einzeln prüfbar; `main(argv) -> int` ist die
Kommandozeile.

**Geändert: `start-termux.sh`** — neuer Abschnitt *Foto-Datendateien
übernehmen* direkt nach der pCloud-Übernahme, im Stil der beiden bestehenden
Blöcke. Er sucht die Dateien unter `$HOME/storage/downloads` (Rückfall
`/sdcard/Download`), ruft bei Fund das Werkzeug mit dem Ziel
`$HOME/foto_sortierung` auf und schreibt das Protokoll nach
`<Download-Ordner>/hermes_diag/uebergabe_letzte.txt` — derselbe Diagnose-Ordner,
den das Skript weiter unten als `$DIAG` benutzt (wird bei Bedarf angelegt).
Der Block läuft idempotent, fasst nichts anderes an und ist mit `|| true`
abgesichert: er kann den Serverstart **nie** verhindern.

**Neu: `backend/tests/test_uebergabe_uebernehmen.py`** — 69 Prüfungen, alle
offline gegen künstliche Ordner in `tmp_path` mit erfundenen Beispielinhalten.

## Grenzen (gelten hart)

* **Nur kopieren bzw. mit `.vorher` sichern.** Eine vorhandene Zieldatei wird
  nie überschrieben, ohne dass vorher eine Sicherung daneben liegt; der
  Rückweg bleibt damit offen.
* **Nichts Fremdes löschen.** Es gibt genau *eine* Löschstelle im Quelltext
  (`_entferne`): dort fällt die eigene Übergabedatei weg — erst **nach**
  bestandener Prüfsummenprobe — oder die eigene temp-Datei eines abgebrochenen
  Schreibens. Sonst existiert keine Löschfunktion, auch nicht „zur Sicherheit“.
  Ein Test zählt die Löschaufrufe im Quelltext (genau einer).
* **Kein Netz, kein git, keine Cloud, kein Fremdaufruf.** Nur die
  Standardbibliothek (`argparse`, `datetime`, `hashlib`, `os`, `sys`).
* **Keine Geheimnisse.** In Ausgabe und Protokoll stehen nur Dateiname, Größe,
  Prüfsumme und Zustände — keine Dateiinhalte und keine Schlüsselwerte. Das ist
  wichtig, weil das Protokoll im freigegebenen Download-Ordner liegt, wo jede
  App lesen kann.
* **Kein Schreiben ins Repo.** Ziele und Protokolle innerhalb des Repos werden
  mit Exit 2 abgewiesen, bevor irgendetwas angelegt wird.

## Wie der PC die Übernahme später belegt

Der Termux-Heimordner ist über das Kabel nicht lesbar — die Ausgabe des
Startskripts also auch nicht. Deshalb schreibt jeder Lauf seine Zeilen mit
Zeitstempel an:

    /sdcard/Download/hermes_diag/uebergabe_letzte.txt

am PC dann z. B. mit `adb shell cat` bzw. über den Dateimanager zu lesen. Die
Datei wird nur **angehängt**, nie überschrieben: steht dort nach einem Start
eine Zeile `…: uebernommen (… Bytes, sha256 …)`, ist die Übergabe belegt; steht
`uebersprungen`, lag nichts vor; steht `FEHLER Pruefsumme weicht ab`, blieb die
Übergabedatei absichtlich liegen und der Lauf muss wiederholt werden.

## Handlauf (Trockenmodus, ohne Wirkung)

Mit künstlichen Ordnern lässt sich der Weg gefahrlos nachstellen — es wird
nichts geschrieben und nichts entfernt. Achtung: auf Windows die **nativen**
Pfade (`C:/…`) benutzen, nicht `/c/…` oder `/tmp/…` — das Werkzeug ist ein
Windows-Programm und übersetzt MSYS-Pfade nicht.

    PROBE="C:/Users/<name>/AppData/Local/hermes/cache/scratch/ueq_probe"
    mkdir -p "$PROBE/quelle" "$PROBE/ziel"
    printf '{"art":"probe","n":1}' > "$PROBE/quelle/fotos_dateien.json"
    printf '{"art":"probe_alt"}'  > "$PROBE/ziel/fotos_dateien.json"
    cd "C:/Users/…/personal_ai_agent" \
      && backend/.venv/Scripts/python.exe tools/handy/uebergabe_uebernehmen.py \
         --quelle "$PROBE/quelle" --ziel "$PROBE/ziel" \
         --dateien fotos_dateien.json fotos_uebersicht.json --trocken

Erwartet: Exit 0, eine Zeile „wuerde uebernommen“ für die vorhandene Datei,
eine Zeile „uebersprungen“ für die fehlende — und beide Ordner danach
unverändert. Derselbe Aufruf **ohne** `--trocken` übernimmt wirklich und legt
`ziel/fotos_dateien.json.vorher` an; ein zweiter Lauf meldet dann zweimal
„uebersprungen“.

Auf dem Handy ist der Handlauf derselbe Aufruf mit den echten Ordnern (Pfad über
`$PROJEKT`, weil `start-termux.sh` den Projektordner selbst ermittelt):

    python "$PROJEKT/tools/handy/uebergabe_uebernehmen.py" \
        --quelle /sdcard/Download --ziel "$HOME/foto_sortierung" \
        --dateien fotos_dateien.json fotos_uebersicht.json --trocken

## Offene Punkte

* **Auf dem Handy noch nicht gefahren.** Dieser Schritt ist am PC gebaut und
  geprüft; der erste echte Lauf passiert beim nächsten Start über das Widget.
  Erst dann gibt es ein echtes `uebergabe_letzte.txt`.
* **Versionsprobe fehlt.** Übernommen wird nach Prüfsumme, nicht nach
  Schemastand: passt der PC-Stand nicht zum Handy-Erwartungsstand, fällt das
  nicht auf. Eine Prüfung des Feldwerts `stand` wäre ein eigener Schritt.
* **Kein Rückweg automatisiert.** Die `.vorher`-Dateien bleiben liegen und
  müssen von Hand zurückgespielt werden (das ist Absicht, aber es ist Handarbeit).
* **Nur diese zwei Namen.** Weitere PC-Dateien (z. B. `sortierplan.json`) sind
  nicht eingetragen; sie kämen über eine Ergänzung der `--dateien`-Liste im
  Startskript dazu.
* **Größe nicht begrenzt.** Das Werkzeug liest eine Übergabedatei ganz in den
  Arbeitsspeicher; bei den heutigen 1,1 MB unkritisch, bei deutlich größeren
  Dateien wäre ein blockweises Kopieren nachzuziehen.
