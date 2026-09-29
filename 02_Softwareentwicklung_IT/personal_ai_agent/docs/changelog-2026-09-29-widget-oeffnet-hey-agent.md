# Widget-Tipp öffnet die Hey-Agent-App (29.09.2026)

## Anlass

Erster Test mit der nativen App am Handy: Das Widget „agent“ (`start-termux.sh`) hat
gepullt und den Server gestartet. Danach öffnete es aber die ältere **Chrome-Web-App**
statt der neuen App „Hey Agent“.

## Ursache

`start-termux.sh`, Block „App statt Browser öffnen“: Das Skript suchte nur nach einem
Paket `org.chromium.webapk*` und fiel sonst auf den Browser zurück. Die native App
(`de.sebastian.heyagent`) kannte es nicht.

## Änderung

- Neue Reihenfolge beim Öffnen:
  1. **Hey Agent** (`am start -n de.sebastian.heyagent/.MainActivity`), falls installiert.
  2. Die Chrome-Web-App (wie bisher).
  3. Der Browser (wie bisher).
- Scheitert der Start der App, geht es mit den bisherigen Rückfällen weiter.
- Pull, Serverstart und alle anderen Blöcke des Skripts bleiben unverändert.

## Prüfung

- Neu: `backend/tests/test_start_app_wahl.py` mit 3 Wächter-Tests (offline, liest den
  Skripttext). Vor der Änderung waren 2 davon rot.
- `bash -n start-termux.sh`: Exit 0.
- Prüfbefehl des Projekts: siehe Commit.

## Offen

Die App kann Termux **nicht selbst** starten. Das Play-Store-Termux
(`googleplay.2026.06.21`) hat keinen `RUN_COMMAND`-Dienst (am Handy gemessen:
`Unable to start service … RunCommandService … not found`). Bis zu einer Lösung gilt:
erst das Widget tippen, dann öffnet sich die App von selbst.

## Nachtrag: Öffnen über `heyagent://start`

**Befund am Handy:** Auch nach der ersten Änderung öffnete das Widget den Browser (Comet).
Das Handy-Protokoll zeigt: Termux hat Hey Agent nie aufgerufen. Ursache ist die
Paket-Sichtbarkeit. Termux ist für `targetSdk 37` gebaut und sieht fremde Pakete nur,
wenn es sie ausdrücklich anfragt. `pm list packages` liefert Hey Agent dort nicht, und
`am start -n` fände sie ebenso wenig.

**Änderung:**
- Die App nimmt die eigene Adresse `heyagent://start` an (Intent-Filter im Manifest) und hat
  `launchMode="singleTask"`, damit ein zweiter Aufruf die laufende App nach vorn holt, statt
  eine zweite zu öffnen.
- `start-termux.sh` öffnet die App mit
  `am start -a android.intent.action.VIEW -d "heyagent://start"`. Eine Adresse löst Android
  immer auf, genau wie `http://` beim Browser. Ohne installierte App endet `am` mit Fehler, dann
  folgen wie bisher Web-App und Browser.

**Prüfung:** 4 Wächter-Tests in `backend/tests/test_start_app_wahl.py` (vorher 3 rot).
`assembleDebug` + 12 JUnit grün. Am Handy: `am start … -d heyagent://start` → Exit 0,
`topResumedActivity = de.sebastian.heyagent/.MainActivity`. Dieser Aufruf lief über `adb`,
nicht aus Termux. Der Beleg aus Termux selbst ist der nächste Widget-Tipp.

## Nachtrag 2: nur noch Hey Agent, Einrichtung automatisch, Stand sichtbar

**Anlass:** Sebastian will nichts von Hand in Termux eingeben, und das Widget soll nie mehr den
Browser öffnen. Außerdem war unklar, ob das Handy die neuen Stände überhaupt zieht: Ein
gescheiterter `git pull --ff-only` blieb im Skript bisher **still**.

**Änderung in `start-termux.sh`:**
- Ein gescheiterter Pull meldet sich jetzt mit „⚠️ Pull fehlgeschlagen“ und zeigt die lokalen
  Änderungen (`git status --short`, höchstens 8 Zeilen).
- Nach dem Abgleich steht immer „Stand jetzt: <Commit>“ im Fenster.
- Jeder Widget-Tipp ruft `termux/hey-agent-einrichten.sh` (wiederholbar) und legt damit den
  Starteintrag in `$PREFIX/etc/profile.d` an. Das darf den Serverstart nie verhindern.
- Geöffnet wird nur noch Hey Agent über `heyagent://start`. Web-App- und Browser-Rückfall sind
  entfernt. Scheitert der Start, zeigt das Fenster die Meldung von Android.

**Prüfung:** `backend/tests/test_start_app_wahl.py` jetzt 6 Tests. Die 4 neuen sind nach der
Änderung geschrieben, nicht vorher rot. `bash -n start-termux.sh`: Exit 0.

## Berichtigung (30.09.2026): Das Widget ist `termux/agent-start`, nicht `start-termux.sh`

**Befund am Handy** (Screenshot der Widget-Sitzung, 30.09.2026 00:20): Das Handy stand auf
dem neuesten Commit (`Already up to date.`, `Stand: 09cce66 …`). Trotzdem fehlten alle neuen
Ausgaben, und der Browser ging auf. Die Ausgabe `Already up to date.` und
`Inbox-Daemon gestartet (bidirektionaler Spiegel)` stammt aus **`termux/agent-start`**. Das
Widget „agent“ zeigt also auf dieses Skript, nicht auf `start-termux.sh`. Die Nachträge 1 und 2
oben haben deshalb am Widget **nichts** geändert. `start-termux.sh` bleibt ein eigener Startweg
mit dem dort beschriebenen Verhalten.

Derselbe Irrtum stand im Kommentar von `termux/agent-ensure.sh` („Symlink ~/.shortcuts/agent
zeigt auf start-termux.sh“). Der Projektordner wurde deshalb als `termux/` berechnet, und der
Starteintrag für die App lief ins Leere.

**Änderung:**
- `termux/gemeinsam.sh`, `oberflaeche_oeffnen`: öffnet Hey Agent über `heyagent://start`. Kein
  Browser mehr, keine Web-App. Scheitert der Start, zeigt das Terminal die Meldung von Android.
- `termux/agent-start`: ruft nach dem Pull `hey-agent-einrichten.sh` auf (jeder Tipp, keine
  Eingabe nötig).
- `termux/hey-agent-einrichten.sh`: schreibt den **vollen Pfad** von `agent-ensure.sh` in den
  Starteintrag, statt ihn über die Verknüpfung zu raten.
- `termux/agent-ensure.sh`: findet den Projektordner zuerst über den eigenen Ort. Die Verknüpfung
  dient nur noch als Rückfall, dann mit Elternordner, falls sie in `termux/` zeigt.

**Prüfung:** neu `backend/tests/test_widget_agent_start.py`, 4 Tests, vorher alle rot.
`bash -n` auf allen vier Skripten: Exit 0.
