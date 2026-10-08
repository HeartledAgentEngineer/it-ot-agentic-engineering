# Änderungsprotokoll 08.10.2026: Verschlüsselte Termux-Sicherung

## Anlass

Termux wechselt von der Google-Play-Fassung zur F-Droid-Fassung. Nur die F-Droid-Fassung
arbeitet mit Termux:API, Termux:Boot und RUN_COMMAND zusammen. Diese Zusätze braucht der
Agent für Sprachsteuerung und eine engere Einbindung in Android. Hermes am Handy ist dabei
nur ein Zusatz (Entscheidung Sebastian, 08.10.2026).

Beide Fassungen sind unterschiedlich signiert. Die alte muss deinstalliert werden, und
dabei löscht Android **alle** Termux-Daten. Einiges davon liegt nur am Handy: die im
Gruppen-Quiz vergebenen Namen, Geschichten, Erinnerungen, Chatverläufe und der
Archiv-Index. Auch die Debian-Umgebung für die Gesichtserkennung (`/root/facy_venv`) ist
in keinem Einrichtungsskript festgehalten.

## Neu

**`termux/sicherung.sh`** (läuft am Handy):
- Sichert `home/` und `usr/` von Termux als je einen Teil `home.tar.age` und `usr.tar.age`.
  - Mit `tar` gepackt und mit `age` an einen öffentlichen Schlüssel (`age1…`) verschlüsselt.
  - Ausgenommen sind `home/storage` (Verweise auf den Handyspeicher), `home/.cache` und `usr/tmp`.
- Ziel ist `/sdcard/Download/termux-sicherung/<Datum_Uhrzeit>/`.
  - Gibt es den Ordner schon, bricht das Skript ab (Exit 4). Es überschreibt nie.
- Daneben entstehen:
  - `pakete_manuell.txt`: nur Paketnamen
  - `MANIFEST.txt`: je Teil Größe, sha256 und die beim Sichern gezählten Einträge
  - `FERTIG`: wird als Letztes geschrieben
- Der private Schlüssel ist am Handy nicht nötig. Dort kann niemand die Sicherung lesen,
  auch keine andere App mit Zugriff auf den Download-Ordner.
- Exit-Codes: 2 Schlüssel fehlt oder ist ungültig, 3 `age`/`tar` fehlt, 5 Ziel nicht
  anlegbar, 6 ein Teil scheiterte. Exit 1 von `tar` (Datei hat sich beim Lesen geändert)
  ist nur ein Hinweis.

**`tools/handy/sicherung_pruefen.py`** (läuft am PC, liest nur):
- Prüft je Teil:
  - ob `FERTIG` da ist
  - Größe und sha256 gegen das Manifest
  - ob sich der Teil mit dem privaten Schlüssel entschlüsseln lässt (`age -d`)
  - ob das tar-Archiv bis zum Ende lesbar ist und dieselbe Zahl an Einträgen hat
- Entpackt wird nichts. Die Ausgabe enthält keine Dateinamen.
- Exit-Codes: 0 grün, 1 Ordner, Schlüssel oder `age` fehlt, 3 rot.

## Prüfung

`backend/tests/test_termux_sicherung.py` hat 12 Tests.
- Das Skript läuft **wirklich**: in Git Bash auf einem künstlichen Termux-Ordner, mit
  einem Platzhalter-`age`, der den Strom durchreicht. Danach liest der PC-Prüfer genau
  diese Sicherung. Damit ist belegt, dass Manifest und Eintragszahl beider Seiten
  zusammenpassen.
- Weiter geprüft:
  - Ausnahmen greifen
  - zweiter Lauf mit gleichem Stand: Exit 4, nichts verändert
  - ohne oder mit ungültigem Schlüssel: Exit 2, kein Ordner
  - Prüfer rot bei fehlendem `FERTIG`, gekipptem Byte, falscher Eintragszahl und
    unlesbarem Archiv
  - das einzige `rm` im Skript löscht die eigene Zwischendatei
- **Noch nicht belegt:** ein echter Lauf am Handy mit echtem `age` und die
  Wiederherstellung. Das Wiederherstellungs-Skript ist der nächste Schritt.

## Nachtrag: Sicherung auf Auftrag beim Widget-Start (08.10.2026, ~23:00)

Wunsch Sebastian: am Handy nichts tippen. Deshalb:

- **`tools/handy/sicherung_auftrag.py`** (PC). Ein Befehl erledigt alles:
  - Kabel-Check und Prüfung, ob der öffentliche Schlüssel am Handy liegt.
  - Legt `/sdcard/Download/termux-sicherung/AUFTRAG` ab (Inhalt: Kennung) und fordert
    zum Tippen des Agent-Widgets auf.
  - Liest `lauf_<kennung>.log` bis `EXIT=<code>` mit.
  - Holt den Sicherungsordner per `adb pull` nach `~/termux-sicherung/`. Ein schon
    vorhandener Ordner wird nicht erneut geholt.
  - Prüft ihn mit `sicherung_pruefen.py`.
  - Exit-Codes: 0 GRÜN, 1 kein Handy, 2 Schlüssel fehlt, 3 Sicherung am Handy
    gescheitert, 4 Zeit abgelaufen, 5 Prüfung ROT, 6 Auftrag läuft schon.
- **`termux/sicherung-auftrag.sh`** (Handy):
  - Ohne `AUFTRAG` kehrt es sofort zurück.
  - Sonst wird `AUFTRAG` zu `AUFTRAG.laeuft` umbenannt, sodass ein zweiter Widget-Druck
    nicht doppelt sichert. Fehlt `age`, wird es installiert. Dann läuft `sicherung.sh`.
  - Am Ende heißt die Datei `AUFTRAG.erledigt_<kennung>`. Nichts wird gelöscht.
- **`termux/agent-start`** (Widget) ruft das Skript mit `|| true` auf:
  - **nach** dem Beenden von Server und Daemon und nach `git pull`
  - **vor** dem Neustart
  - Ein normaler Start ohne Auftrag verhält sich wie bisher.

Tests: `backend/tests/test_termux_sicherung.py`, jetzt 20.
- Das Auftragsskript läuft echt: ohne Auftrag passiert nichts, mit Auftrag wird einmal
  gesichert und umbenannt, das Log endet mit `EXIT=0`.
- Ein Wächter prüft die Reihenfolge im Widget.
- Der PC-Weg wird mit einer adb-Attrappe geprüft: ganzer Ablauf, kein doppeltes Holen,
  alle Fehler-Exits, Zeitablauf.

## Nachtrag: erster echter Lauf am Handy und Umbau (08.10.2026, ~22:45)

**Lauf 22:35 (Ordner `2026-10-08_2235`):**
- `age` 1.3.1 wurde vom Skript selbst installiert.
- `home` war fertig: 109.904 Einträge, 3.284 MB.
- `usr` brach mit **tar Exit 2** ab. Die Ursache ist nicht sichtbar, weil das Skript die
  Fehlermeldungen von tar nach `/dev/null` schickte. Dieser Ordner hat kein `FERTIG` und
  gilt als unvollständig. Er wird nicht gelöscht.

**Umbau:**
- `usr/` wird **nicht mehr** gesichert. Die Wiederherstellung installiert die Programme
  ohnehin neu aus `pakete_manuell.txt`, weil Play- und F-Droid-Fassung sich darin
  unterscheiden können.
- Gesichert wird stattdessen jede Linux-Umgebung unter
  `usr/var/lib/proot-distro/installed-rootfs/` mit **`proot-distro backup <name>`** als
  `distro_<name>.tar.age`. Darin liegt die Debian-Umgebung der Gesichtserkennung.
  - proot-distro liest sie mit seinen Schein-root-Rechten.
  - Laut README schreibt es ohne `--output` ein unkomprimiertes Archiv auf stdout.
  - `proot-distro restore` liest es später wieder von stdin.
  - Dieser Teil hat im Manifest `eintraege=-1`, weil das Handy nicht zählt.
- Fehlermeldungen von tar und proot-distro landen in einer Zwischendatei. Bei einem
  Abbruch oder einer Warnung erscheinen die ersten 5 Zeilen.
- Der PC-Prüfer liest jetzt auch komprimierte Archive (`r|*`). Bei `eintraege=-1`
  vergleicht er keine Zahl, liest das Archiv aber vollständig.

Tests: 23. Neu sind ein Distro-Fehler mit sichtbarer Meldung und Exit 6, ein Lauf ohne
Linux-Umgebung (nur `home`) und der Prüfer mit gzip ohne Eintragszahl.
