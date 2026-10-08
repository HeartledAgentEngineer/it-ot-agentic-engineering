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
