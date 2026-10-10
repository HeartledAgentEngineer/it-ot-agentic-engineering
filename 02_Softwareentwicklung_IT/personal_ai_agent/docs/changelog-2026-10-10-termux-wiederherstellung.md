# Änderungsprotokoll 10.10.2026: Termux nach dem Umzug wiederherstellen

Anlass: Termux soll von der Play-Fassung auf die F-Droid-Fassung umziehen. Dabei wird die alte
Fassung deinstalliert, und Android löscht alle Termux-Daten. Die verschlüsselte Sicherung
(`termux/sicherung.sh`, 08.10.2026) gab es schon, ein Weg zurück fehlte noch.

## Das Schlüsselproblem und die Lösung

Die Sicherung ist mit Sebastians Hauptschlüssel verschlüsselt. Dessen privater Teil liegt nur
am PC und soll nie aufs Handy. Einfach entschlüsselt in den Download-Ordner legen geht auch
nicht: Dort könnten andere Apps mitlesen, und die Sicherung enthält unter anderem die `.env`
mit den Zugangsschlüsseln.

Deshalb gibt es einen **Einmal-Schlüssel**:

1. **Handy, neues Termux** (`termux/wiederherstellen.sh vorbereiten`):
   - erzeugt `~/.wiederherstellung_einmal.key` im privaten Termux-Ordner,
   - legt nur dessen öffentlichen Teil nach `/sdcard/Download/termux-sicherung/einmal_empfaenger.txt`.
2. **PC** (`tools/handy/wiederherstellung_senden.py`):
   - Jeder Teil läuft als Strom: `age -d` mit dem Hauptschlüssel, dann `age -r` mit dem
     Einmal-Schlüssel, dann `adb exec-in "cat > …"` aufs Handy.
   - Klartext gibt es nur im Arbeitsspeicher des PCs.
   - Unterwegs wird die sha256 der Quelle gegen `MANIFEST.txt` geprüft, am Ende die sha256 der
     Datei auf dem Handy.
   - Danach werden `MANIFEST.txt`, `EMPFAENGER.txt`, die Paketlisten und zuletzt `FERTIG`
     geschrieben.
3. **Handy** (`termux/wiederherstellen.sh einspielen`):
   - Prüfsummen prüfen.
   - Pakete aus `pakete_manuell.txt` einzeln installieren. Dazu `python-numpy` und
     `python-pillow` als fertige Termux-Pakete.
   - Heimordner auspacken mit `tar --skip-old-files`. Vorhandene Dateien bleiben unberührt.
   - Linux-Umgebung mit `proot-distro restore` zurückspielen. Gibt es sie schon, wird sie
     nicht angefasst, denn `restore` würde sie sonst ohne Rückfrage leeren
     (README proot-distro, geprüft 10.10.2026).
   - Python-Pakete aus `backend/requirements.txt` installieren und fehlende Pakete aus
     `pip_alt.txt` einzeln nachziehen.

**Nie überschreiben:** Gibt es den Zielordner auf dem Handy schon, entsteht
`wiederherstellung_<stand>_2`. Liegt für denselben Einmal-Schlüssel schon eine vollständige
Sendung da, tut das Werkzeug nichts.

**Befund nebenbei:** Die Python-Pakete des Agenten (FastAPI, uvicorn usw.) lagen im
Systemteil `usr/`, und den sichert `sicherung.sh` bewusst nicht. Deshalb schreibt
`sicherung.sh` jetzt zusätzlich `pip_alt.txt` (`pip freeze`, nur Paketnamen und Versionen).
Für die Sicherung vom 10.10. legt Sebastian die Liste vor dem Deinstallieren einmal von Hand an.

## Prüfung

- Neu `backend/tests/test_wiederherstellung.py`, 12 Tests, offline mit erfundenen Daten. Die
  Tests decken ab:
  - den Strom mit Prüfsummen und den Abbruch bei einer fehlerhaften Stufe,
  - einen Probelauf mit echtem `age`: Der Inhalt bleibt gleich, und der Hauptschlüssel öffnet
    die Sendung nicht mehr,
  - die Idempotenz und den neuen Ordner bei anderem Schlüssel,
  - die Erkennung einer beschädigten Sicherung,
  - fehlendes Handy und fehlenden Einmal-Schlüssel,
  - die Syntax des Skripts (ohne `rm`),
  - den **ganzen Umzug in Git Bash**: vorbereiten, senden, einspielen. Eine vorhandene Datei
    und eine vorhandene Linux-Umgebung bleiben dabei unberührt.
  - Bei falscher Prüfsumme wird nichts ausgepackt.
- **Probelauf mit der echten Sicherung vom 10.10.2026** in einen Ordner am PC statt aufs Handy:
  - beide Teile umgeschlüsselt, Prüfsummen ok,
  - mit dem Einmal-Schlüssel geöffnet: **109.653 Einträge** im Heimordner, gleich wie in der
    Sicherung; Debian bis zum Ende lesbar (48.136 Einträge).
- `adb exec-in` überträgt Binärdaten unverändert, geprüft mit 300 KB Zufallsdaten, sha256 gleich.
- **Am Handy noch nicht gelaufen.** Das passiert beim echten Umzug.

## Nachtrag 10.10.2026, ca. 03:45: Senden in Stücken

Beim echten Umzug riss die USB-Verbindung zweimal mitten in `home.tar.age` ab: nach 51 s bei
1.864 MB und nach 46 s bei 1.678 MB.
- Belegt ist das im logcat von `adbd` mit `UsbFfs: connection terminated … Connection reset
  by peer`.
- `distro_debian.tar.age` (1.433 MB, ~38 s) kam beide Male heil an.
- `adb exec-in` meldet so einen Abriss nicht als Fehler. Erkannt hat ihn nur der
  sha256-Vergleich am Ziel. Deshalb gab es Exit 5, kein `FERTIG` und nichts wurde ausgepackt.

Neu in `tools/handy/wiederherstellung_senden.py`:
- `StueckAblage`: Der Strom geht in Stücken zu 128 MB nach `<sendung>/teile/`.
  - Jedes Stück wird am Handy per sha256 geprüft.
  - Kommt es nicht heil an, wird es unter neuem Namen (`.v2`, `.v3`) wiederholt, bis zu
    dreimal. Danach bricht das Werkzeug mit Exit 6 ab.
  - Ein Abriss kostet so nur ein Stück.
- `zusammensetzen`: Das Handy fügt die Stücke selbst mit `cat` zusammen, ohne Daten über das
  Kabel. Danach wird wie bisher die sha256 der ganzen Datei geprüft.
- Behebt nebenbei einen alten Fehler: Fiel das Ziel aus, staute sich der Strom, und das
  Werkzeug konnte hängen. Jetzt werden die beiden age-Prozesse beendet.
- Die Stücke bleiben in `teile/` liegen (das Werkzeug löscht nichts). Wenn die
  Wiederherstellung gelaufen ist, kann Sebastian sie löschen, ebenso die beiden
  unvollständigen Sendeordner ohne `FERTIG`.

Tests: `backend/tests/test_wiederherstellung.py` +2:
- Ein Stück kommt halb an und wird unter neuem Namen wiederholt. Der Inhalt stimmt danach.
- Es kommt nie heil an: Nach 3 Versuchen bricht das Werkzeug ab, ohne zu hängen.

## Ablauf für den Umzug

1. Im alten Termux: `pip freeze > /sdcard/Download/termux-sicherung/pip_alt.txt`.
2. Am PC: `tools/handy/wiederherstellung_senden.py --nur-skript`. Das legt das Skript aufs Handy.
3. Alte Termux-Fassung deinstallieren. F-Droid-Fassungen installieren: Termux, Termux:API,
   Termux:Widget und Termux:Boot.
4. Im neuen Termux: `termux-setup-storage`, `pkg install age`,
   `bash /sdcard/Download/termux-sicherung/wiederherstellen.sh vorbereiten`.
5. Am PC: `tools/handy/wiederherstellung_senden.py`.
6. Im neuen Termux: `bash /sdcard/Download/termux-sicherung/wiederherstellen.sh einspielen`,
   danach `termux/einrichten.sh` und das Widget neu ablegen.
