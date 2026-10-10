# Änderungsprotokoll 10.10.2026: Ein Startweg — App-Knopf und Widget über dieselbe Ablaufdatei

Anlass: Entscheidung Sebastian (10.10.2026): Künftig gibt es nur noch EINEN Weg, den
Agenten zu starten — den Knopf der eigenen App (Package `de.sebastian.heyagent`). Das
Termux-Widget bleibt funktionsfähig, ist aber nicht mehr der empfohlene Weg. Grund:
„Zwei Wege heißen zwei Stellen, an denen Schritte fehlen können." Genau das drohte: Die
gestern gebaute Wissensdatei-Übernahme (`termux/wissensdatei-uebernehmen.sh`, Commit
307a938) hing im Widget-Weg (`termux/agent-start`) — würde nur der App-Knopf benutzt,
liefe sie nie.

## Die gemeinsame Wahrheit

**Neu `termux/start-vorbereiten.sh`** (162 Zeilen, reine LF, nur `bash`-Standardwerkzeuge):
DIE gemeinsame Ablaufdatei. App-Weg und Widget rufen nur noch sie auf; kein
Übernahme-Schritt steht mehr zweimal irgendwo. Feste Reihenfolge, jeder Schritt einzeln
abgesichert (darf den Start nie verhindern), Exit immer 0 (außer Projektordner fehlt):

1. `git pull --ff-only` (nur Vorspulen: fetch → `merge-base --is-ancestor` → pull;
   eigene Handy-Commits oder lokale Änderungen werden nie überschrieben — dann geht es
   mit dem vorhandenen Stand weiter)
2. `hey-agent-einrichten.sh` (profil.d-Eintrag, Brücke, allow-external-apps — s.u.)
3. pCloud-Schlüssel aus dem Download-Ordner in `backend/.env`
4. Vorlese-Schlüssel (`OPENROUTER_TTS_KEY`) auf demselben Weg
5. Datendateien vom PC (`tools/handy/uebergabe_uebernehmen.py`, gleiche 12er-Liste)
6. Wissensdatei `memory.db` (`termux/wissensdatei-uebernehmen.sh`)
7. Weckruf-Sperre (`termux-wake-lock`)
8. Sicherung auf Auftrag (`termux/sicherung-auftrag.sh`) — **nur ohne `--laufend`**
9. Postfach-Daemon sicherstellen (`hermes_inbox_daemon.py`, guarded — nur einer)

Aufruf: `bash termux/start-vorbereiten.sh [--laufend] [Projektordner]`.

**Geändert `termux/agent-start`** (Widget): ruft nur noch die Ablaufdatei auf
(`agent-start:117`, ohne `--laufend`: Der Widget-Druck beendet oben bereits Server und
Daemon, es folgt gleich ein Start — also läuft auch ein anstehender Sicherungs-Auftrag).
Kill-/Lock-Maschinerie, Wartephase und Sitzungs-Schluss bleiben unverändert; das Widget
ist unverändert benutzbar.

**Geändert `termux/agent-ensure.sh`** (App): ruft dieselbe Datei auf
(`agent-ensure.sh:98`). Kein Übernahme-Schritt doppelt. Neu: die Vorbereitung läuft bei
JEDEM Lauf — auch wenn `/health` schon antwortet (dann mit `--laufend`); übersprungen wird
nur der Serverstart (kein Kill, kein Neustart, kein Rücksprung zur App).

## Entscheidungen (mit Begründung)

**1) Verhalten bei laufendem Server.** Vorher endete `agent-ensure.sh` bei laufendem
Backend sofort („nichts zu tun" — kein Pull, keine Übernahme). Bei dauerhaft laufendem
Server liefen Pull und Wissensdatei-Übernahme also NIE — das widerspricht dem Ziel.
Entschieden: Die Vorbereitung läuft bei jedem Lauf (beides schnell und idempotent: gleiche
sha256 = nichts tun, kein Kopieren), nur der Serverstart selbst wird übersprungen. Kein
unnötiges Neustarten eines laufenden Servers.

**2) Damit das im Alltag greift, stößt die App den Ablauf auch bei laufendem Backend an.**
Sonst hätte die Änderung aus 1) nur beim echten Neustart gewirkt (die App fragt Termux bei
laufendem Backend gar nicht an). Neu: `BackendWaechter` ruft bei bestandenem ersten
Health-Check `starter.stillerAnstoss()`; `TermuxLauncher.stillerAnstoss()` schickt NUR den
unsichtbaren RUN_COMMAND (KEIN sichtbares Termux als Rückfall — nichts öffnet sich).
Scheitert der Anstoß, ist die App trotzdem bereit (er ist ein Extra, kein Blocker).

**3) Kopie-Alterung `~/agent-ensure.sh` (zweite Wahrheit).** Die App ruft den FESTEN Pfad
`/data/data/com.termux/files/home/agent-ensure.sh`; dort lag eine KOPIE des Skripts, die
laut Kommentar „nach Änderungen im Repo erneut kopiert" werden musste — sie lief still
mit alter Logik weiter. Von den zwei vorgeschlagenen Wegen wurde die **einfachere und
robustere** gewählt: `~/agent-ensure.sh` ist jetzt eine **dünne Weiterleitung (Brücke)**
auf `termux/agent-ensure.sh` im Projektordner, die `hey-agent-einrichten.sh` bei jedem
Start neu schreibt. Die Brücke kann nicht veralten; sie macht selbst keine Arbeit.
Eine alte Kopie wird einmalig als `~/agent-ensure.sh.vor_<datum>` gesichert (nie
gelöscht). Sie findet das Projekt über (a) `PROJEKT` aus der Umgebung, (b) den Symlink
`~/.shortcuts/agent`, (c) den beim Einrichten eingebackenen Projektpfad — funktioniert
also auch nach einem frischen Klon, bevor je ein `git pull` lief. Findet sie nichts, gibt
es eine klare Meldung und eine Zeile in `~/agent-ensure.log` (nie ein stiller Fehlschlag).
Schlägt das Brücken-Schreiben fehl, meldet die Einrichtung eine WARNUNG statt eines
falschen „OK".

**4) Sicherung auf Auftrag.** Läuft im Start-Fall (Server nicht erreichbar → er ist aus)
auch im App-Weg — wie bisher im Widget. Beim App-Druck auf einen LAUFENDEN Server
(`--laufend`) ist sie bewusst aus: aus laufendem Betrieb wird nicht gesichert (der
Auftrag wartet auf den nächsten echten Start; dafür bleibt das Widget da, das immer neu
startet). EHRLICH: Solange der Server dauerhaft durchläuft und nur der App-Knopf gedrückt
wird, wartet ein Sicherungs-Auftrag auf den nächsten Neustart.

**5) `start-termux.sh` bewusst NICHT angefasst.** Der Alt-Weg bleibt wie er ist (voller
Abgleich in beide Richtungen + Neustart); er ist nicht Teil dieser Zusammenführung und
funktioniert weiter.

## allow-external-apps — die stille Falle (geprüft)

- **Nötig?** Ja: Das F-Droid-/GitHub-Termux ignoriert `RUN_COMMAND` von fremden Apps,
  solange `allow-external-apps=true` nicht in `~/.termux/termux.properties` steht; dazu
  muss die App die Berechtigung `com.termux.permission.RUN_COMMAND` haben. Ohne die Zeile
  tut der App-Knopf STILL nichts — es sieht wie ein kaputter Agent aus.
- **Wo es dokumentiert war:** `android/README.md` (Einrichtungsschritt), `docs/spec-a1`
  (§5.1), `TermuxLauncher.kt` (Kommentar), Kopf von `agent-ensure.sh`, Fehlertext in
  `BackendStartLogik.kt`. **Gefehlt hat es in jeder Automatik** — die Einrichtung hat die
  Zeile nie gesetzt oder geprüft.
- **Neu:** `termux/hey-agent-einrichten.sh` setzt die Zeile selbst — idempotent (grep;
  hängt nur an, wenn sie fehlt, und entfernt nie etwas) — und ruft
  `termux-reload-settings` (wenn vorhanden). Die Einrichtung läuft bei jedem Start
  (Widget UND App) → selbstheilend. Rettungskette, falls der App-Knopf stumm bleibt:
  einmal das Widget tippen — der Widget-Weg braucht die Einstellung nicht und setzt sie
  selbst. Manuell: `sh termux/hey-agent-einrichten.sh` im Projektordner.

## Was die Einrichtung (`hey-agent-einrichten.sh`) jetzt macht

1. `$PREFIX/etc/profile.d/hey-agent.sh` (unverändert, ruft `--app-zurueck`),
2. Brücke `~/agent-ensure.sh` (neu, mit Sicherung einer alten Kopie),
3. `allow-external-apps=true` (neu, idempotent).

## Prüfung

- **Neu `backend/tests/test_ein_startweg.py` (13 Testfunktionen):** beide Wege rufen
  GENAU EINE gemeinsame Ablaufdatei (und keinen der Schritte doppelt); Reihenfolge in der
  Datei (Pull → Einrichtung → Schlüssel → Datendateien → Wissensdatei → Weckruf →
  Sicherung → Daemon); `--laufend`-Wache liegt nur um die Sicherung; beide Wege rufen die
  Vorbereitung VOR ihrem Serverstart; App-Weg: Health-Flag, `--laufend`, „Serverstart
  übersprungen" vor dem nohup-Start, kein Rücksprung, kein Kill; alle vier Startdateien
  reine LF + Shebang + `bash -n` Exit 0. Dazu ECHTE Läufe in Git Bash (Sandkasten mit
  Attrappen): Reihenfolge im echten Lauf, Fortsetzung trotz gescheitertem `git fetch`
  („darf nie abbrechen"), `--laufend` lässt nur die Sicherung aus, Einrichtung legt Hook +
  Brücke an, sichert die alte Kopie genau einmal, Brücke startet das Projekt-Skript und
  reicht Argumente durch, `PROJEKT`-Vorrang + klare Meldung bei fehlendem Projekt,
  allow-external-apps genau einmal (zweiter Lauf dupliziert nicht).
- **Angepasst** (der Aufruf steht jetzt in der gemeinsamen Datei):
  `test_agent_ensure_app.py` (2), `test_widget_agent_start.py` (3),
  `test_pcloud_schluessel_uebernahme.py`, `test_vorlese_schluessel.py`,
  `test_uebergabe_uebernehmen.py` (Wächter auf den gemeinsamen Ablauf umgestellt),
  `test_termux_sicherung.py`, `test_wiederherstellung.py` (Zeiger).
- **Kotlin:** `BackendWaechter` ruft bei laufendem Backend `stillerAnstoss()` (Standard
  `false`, bestehende Attrappen unverändert); `TermuxLauncher.stillerAnstoss()` = nur
  RUN_COMMAND, kein sichtbares Termux. Neu `BackendWaechterTest.kt` (4 Tests).
  `./gradlew testDebugUnitTest assembleDebug --console=plain` → **BUILD SUCCESSFUL**
  (3m 14s, Exit 0); APK `android/app/build/outputs/apk/debug/app-debug.apk`:
  **9.789.063 Byte, 10.10.2026 10:36** (frisch gebaut, `compileDebugKotlin`/`packageDebug`
  liefen — nicht „up-to-date").
- `bash -n` auf `start-vorbereiten.sh`, `agent-start`, `agent-ensure.sh`,
  `hey-agent-einrichten.sh`: Exit 0; alle vier Dateien **reine LF** (0 CR-Bytes).
- Prüfbefehl (über die Tor-Sperre, die exakt diesen Befehl ausführt):
  `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **3672 passed, 2 skipped,
  Exit 0** (Lauf über die Tor-Sperre, 789 s; im selben Arbeitsbaum arbeiten zwei schwere
  Hintergrundläufe — daher länger als die üblichen 8–10 Minuten). Nur diese betroffenen
  Wächter zusammen: **180 passed, Exit 0** (208 s).

## Ehrlich offen (am Handy; vom PC wurde nichts ans Gerät geschickt)

- Einmal in Termux im Projektordner: `sh termux/hey-agent-einrichten.sh` — legt die
  Brücke an, ersetzt die alte Kopie `~/agent-ensure.sh` (vorher gesichert) und setzt
  `allow-external-apps`.
- Das neue APK installieren (`android/app/build/outputs/apk/debug/app-debug.apk`,
  9.789.063 Byte) — enthält den stillen Anstoß.
- Danach der Beleg am Gerät: App-Knopf bei laufendem Server drücken, dann in
  `/sdcard/Download/hermes_diag/wissensdatei_uebernahme.log` nachsehen, dass die
  Übernahme-Zeile erscheint. Erst danach ist der App-Weg am Gerät belegt.
