# Rueckweg Handy -> PC: die am Geraet erzeugten Datendateien bekommen einen Weg (12.10.2026)

## Anlass

Die Uebergabe lief bisher **nur in eine Richtung**: der PC legt Dateien in den
freigegebenen Download-Ordner bzw. in die pCloud, das Handy holt sie
(`tools/handy/uebergabe_uebernehmen.py`, `termux/pcloud-uebernehmen.sh`).

Die Dateien, die die **App am Geraet erzeugt**, hatten dagegen **keinen Weg
zurueck**:

- `geschichten.jsonl` — die eigenen Erzaehlungen zu Anlaessen und Bildern,
- `anlass_umbenennung.jsonl` — die eigenen Anlassnamen.

Beide entstehen am Handy im Termux-Heimordner `$HOME/foto_sortierung`. Der
Nachweis (`tools/foto_sortierung/bestand_pruefen.py`, Abschnitte „Eigene
Geschichten" / „Eigene Titel", Journal 26) kann sie deshalb **nie** vergleichen
— am PC heisst es dauerhaft „noch nicht angelegt". In Journal 26 wurde das
gemessen und als naechster Kandidat benannt; in Journal 31/32 stand er als
„braucht das Geraet am Kabel".

## Gemessen (nur lesend, 12.10.2026)

| Frage | Messung | Ergebnis |
|---|---|---|
| Haengt ein Geraet? | `adb devices` | ja (`ZY22K9RGLQ`, Zustand `device`) |
| Ist der Termux-Heimordner per Kabel lesbar? | `adb shell ls /data/data/com.termux/files/home/foto_sortierung` | **nein** — „Permission denied" |
| Liegen die Dateien irgendwo im lesbaren Bereich? | `adb shell find /sdcard -maxdepth 4 -name geschichten.jsonl -o -name anlass_umbenennung.jsonl` | **nein** — 0 Treffer |
| Gibt es den Bereitstellungsordner schon? | `adb shell ls -la /sdcard/Download/hermes_rueckweg` | nein, noch nicht vorhanden |
| Gibt es einen anderen Rueckweg? | `~/termux-sicherung/` am PC | ja, aber nur als **verschluesselte Komplettsicherung** (`home.tar.age`, drei Staende 08.–10.10.) — erreichbar nur durch Auspacken des ganzen Heims |

Damit ist belegt: **ohne diesen Schritt gibt es keinen Weg fuer diese zwei
Dateien** — und der Grund ist nicht Bequemlichkeit, sondern die App-Sandbox
(der Heimordner ist ueber das Kabel gesperrt).

## Was gebaut wurde

1. **Geraete-Seite: `termux/rueckweg-bereitstellen.sh`**
   Kopiert die Listendateien aus `$HOME/foto_sortierung` in den **freigegebenen**
   Ordner `/sdcard/Download/hermes_rueckweg`.
   - gleiche Groesse im Ziel = `uebersprungen` (schreibt nicht),
   - geaenderte Fassung: die alte wird **zuerst** als `<name>.vorher`
     beiseitegelegt, dann `cp` nach `<name>.teil` und `mv` an den Platz — es
     steht nie eine halbe Datei im Zielordner,
   - am **Quellordner** wird nichts geaendert und nichts geloescht (nur `cp`),
   - fehlende Quelle/Zielordner = ehrliche Zeile, **Exit immer 0** (darf den
     App-Start nie verhindern),
   - die Liste steht **wortgleich** in beiden Teilen (`RUECKWEG_NAMEN`).

2. **Verdrahtung: `termux/start-vorbereiten.sh`, Schritt 5b**
   Der gemeinsame Startweg (App-Knopf **und** Widget) ruft das Skript auf —
   abgesichert mit `|| true` und nur, wenn die Datei da ist. Damit braucht
   Sebastian nichts zu tippen: beim naechsten Start liegen die Dateien im
   Download-Ordner.

3. **PC-Seite: `tools/handy/rueckweg_holen.py`**
   - **Trockenlauf ist der Standard** (ohne `--holen` wird nichts geschrieben),
   - `--holen` laedt je **regulaerer** Datei **aus der Liste**: gleiche Groesse
     → `uebersprungen`; sonst alte Fassung als `.vorher` sichern, `adb pull` in
     eine `.teil`-Datei im Zielordner, `os.replace`, Groessenprobe gegen die
     Geraeteanzeige,
   - **jede geholte Datei bucht eine Manifest-Zeile** (`--manifest`, Standard
     `~/foto_sortierung/rueckweg_manifest.jsonl`): Name, Bytes, sha256, Zeit,
     `richtung: handy->pc` (AGENTS.md, Punkt 5),
   - **alles andere im Download-Ordner wird nicht geholt** — es wird als Zeile
     gemeldet („nicht in der Liste"),
   - **kein Inhalt in der Ausgabe** (eigene Erzaehlungen sind private Texte),
   - Ziel IM Repo → Exit 2; nur `ls` und `pull` am Geraet = **lesend**; keine
     Netz-Bibliothek, nur Standardbibliothek.

## Belege

- **Tests:** neue Datei `backend/tests/test_rueckweg_handy.py`, **20
  Testfunktionen**, Lauf **20 passed**.
  - **Waechter gegen Auseinanderlaufen:** `ERLAUBTE_NAMEN` (Werkzeug) muss
    genau `RUECKWEG_NAMEN` (Shell) sein — sonst hoechstens die halbe Liste.
  - Geraete-Skript: `bash -n` gruen, keine verbotenen Muster (`rm`, `delete`,
    `unlink`, `curl`, `wget`, `--force`), kopiert, endet mit `exit 0`; im
    **echten Lauf** gegen ein `tmp_path`: genau die Listendateien kopiert, eine
    fremde Datei **nicht**, Quellordner byte-gleich, zweiter Lauf schreibt
    nichts, fehlende Quelle kein Fehler, geaenderte Quelle legt `.vorher` an.
  - PC-Werkzeug gegen eine **Attrappen-adb** (kein echtes Geraet, kein Netz):
    Trockenlauf schreibt nichts, `--holen` holt, zweiter Lauf ueberspringt,
    nicht gelistete Datei bleibt liegen, `GEHEIM-TESTTEXT` erscheint **nicht**
    im Bericht, Ziel im Repo → Exit 2, fehlender Geraeteordner → Exit 1 (mit
    `--holen`) bzw. Exit 0 (Trockenlauf), `.vorher` bei geaenderter Fassung,
    Manifest mit passender sha256 und genau einer Zeile je Datei.
  - Dazu: keine echten Namen/Geheimnismuster in den neuen Dateien, kein
    HTTP/pCloud/Sockel im Werkzeug-Code, Vorgaben fuer Ziel und Manifest liegen
    **ausserhalb** des Repos.
- **Pruefbefehl:** siehe Commit (frisch und vollstaendig gefahren).
- **Messung am echten Geraet (nur lesend):**
  `python tools/handy/rueckweg_holen.py` →
  „Ordner auf dem Geraet nicht vorhanden: /sdcard/Download/hermes_rueckweg" +
  Hinweis auf das Bereitstellungsskript, **Exit 0**. Das ist der ehrliche
  Ist-Stand: das Geraet hat noch nichts bereitgestellt, weil es den neuen
  Stand erst beim naechsten Start zieht.

## Ehrlich offen / Grenzen

- **Der Rueckweg ist noch nicht mit echten Daten durchlaufen.** Dafuer muss das
  Handy den neuen Stand ziehen (App oeffnen oder `git pull` + Start), dann
  laeuft Schritt 5b, danach holt der PC. Solange die zwei Dateien am Geraet
  nicht existieren, sagt der Nachweis weiterhin ehrlich „noch nicht angelegt".
  **Ueberholt am 12.10.2026, 21:2x** — siehe Nachtrag unten: das Geraet hatte
  beim App-Start bereitgestellt, der Hol-Lauf ist mit echten Daten gelaufen.
- Der Weg ist **an das Kabel gebunden** (wie `diag_holen.py`). Der kabellose
  Weg (Geraet laedt selbst in die pCloud) waere ein eigener Schritt und ist
  **nicht** gebaut — Entscheidung liegt bei Sebastian.
- Die alternativ vorhandene Komplettsicherung (`~/termux-sicherung`,
  verschluesselt) enthaelt den Heimordner, also auch diese zwei Dateien — sie
  ist aber kein Ersatz fuer den Rueckweg: sie kostet ein ganzes Heim und ist
  ohne Schluessel nicht lesbar.
- **Waehrend der Testarbeit** hat ein erster Testlauf durch die Vorgabe
  `--manifest` vier erfundene Buchungen in die ECHTE Datei
  `~/foto_sortierung/rueckweg_manifest.jsonl` geschrieben. Die Datei enthielt
  ausschliesslich diese vier Testzeilen (geprueft: 4 Zeilen, alle
  `richtung: handy->pc`) und wurde entfernt; die Tests nehmen jetzt ausnahmslos
  ein Manifest unter `tmp_path`, und ein neuer Test haelt fest, dass die
  Vorgaben ausserhalb des Repos liegen.

## Nachtrag (12.10.2026, 21:2x) — der erste echte Hol-Lauf, und ein Fehler darin

**Der Rueckweg ist mit echten Daten gelaufen.** Das Handy hing am Kabel
(`adb devices`: ein Geraet) und hatte beim App-Start bereitgestellt: in
`/sdcard/Download/hermes_rueckweg` lag `geschichten.jsonl`, 3.685 Bytes vom
12.10.2026 20:58. Trockenlauf, dann `--holen`:
„geholt 1 - uebersprungen 0 - nicht in der Liste 0 - Fehler 0“, Ziel
`~/foto_sortierung`, eine Manifest-Zeile. Am Geraet wurde nur `ls` und `pull`
gemacht (lesend), nichts geschrieben, nichts geloescht.

**Die Kette ist damit ganz belegt:** die App erzeugt die Erzaehlungen am Geraet
→ das Geraet stellt sie bereit → das Kabel holt sie → der Nachweis vergleicht
sie. `bestand_pruefen.py` (Exit 0) zeigt die zwei Stufen jetzt zum ersten Mal
von beiden Seiten:

- „Eigene Geschichten: geschichten.jsonl: **5 Geschichten, 3 Anlaesse, 3 zu
  einem Bild**; Quellen: tippen 5“ (vorher: „noch nicht angelegt“),
- „Rueckweg (Handy -> PC): rueckweg_manifest.jsonl: 1 Buchungen, 1 verschiedene
  Dateien (**unversehrt 1**, abweichend 0, am PC fehlt 0)“.
  „Unversehrt“ heisst: Bytes UND sha256 der PC-Kopie stimmen mit der Buchung.

**Der Fehler, den dieser Lauf sofort zeigte:** die gebuchte Zeile trug
`"zeit": ""` — leer. AGENTS.md Punkt 5 verlangt fuer eine schreibende Operation
auf einem fremden System „Quelle → Ziel, Zeit, Kennung“; das Werkzeug selbst
versprach im Modulkopf „Name, Bytes, sha256, Zeit“. Die Uhrzeit fehlte also,
und Quelle/Ziel standen gar nicht drin — aus der Zeile war nicht abzulesen,
wann und von wo nach wo die Datei ging. Ursache: `--zeit` hatte die Vorgabe
`""` und wurde nirgends gefuellt; `--ziel`/`--ordner` kannte die Buchung nicht.

**Behoben** (`tools/handy/rueckweg_holen.py`):

- Ohne `--zeit` wird die **Zeit jetzt** gebucht (ISO mit Zeitzone,
  `datetime.now().astimezone()`); ein **ausdruecklich leerer** Wert wird
  abgelehnt (Exit 2, „Es wird NICHTS geschrieben“) statt stillschweigend zur
  Uhrzeit zu werden — dieselbe Regel wie bei `ereignisse_bauen.py --stand`.
- Jede Buchung traegt **Quelle** (Geraetepfad) und **Ziel** (PC-Pfad) — wie das
  Nachbar-Manifest der Uebergabe PC → Handy (`uebergabe_manifest.jsonl`), das
  beides seit jeher fuehrt.

**Belege:**

- Testdatei `backend/tests/test_rueckweg_handy.py` **20 → 23 Testfunktionen**
  (3 neue: Buchung traegt Zeit in ISO-Form + Quelle + Ziel; `--zeit` setzt den
  Wert wortgleich; leerer `--zeit` = Exit 2 und nichts geschrieben), Lauf der
  Datei **23 passed**.
- **Messung am echten Geraet (nur lesend, Exit 0):** derselbe Hol-Lauf in ein
  Probe-Ziel; die neue Zeile lautet
  `{"bytes": 3685, "name": "geschichten.jsonl", "quelle": "/sdcard/Download/hermes_rueckweg/geschichten.jsonl", "richtung": "handy->pc", "sha256": "5f9fe04…", "zeit": "2026-10-12T21:21:42+02:00", "ziel": "…\\ziel\\geschichten.jsonl"}`
  — die Pruefsumme ist dieselbe wie bei der ersten Kopie. Der Aufruf mit
  leerem `--zeit` endet mit Exit 2 und legt **kein** Ziel an (gemessen).
- **Nicht angefasst:** die erste, zeitlose Buchung in
  `~/foto_sortierung/rueckweg_manifest.jsonl` bleibt als historische Zeile
  stehen (nichts geloescht); sie ist die einzige ohne Zeit und durch diesen
  Nachtrag erklaert.
- `anlass_umbenennung.jsonl` war am Geraet nicht bereitgestellt (die Stufe
  „Eigene Titel“ meldet weiterhin ehrlich „noch nicht angelegt“) — es gibt am
  Geraet offenbar noch keine eigenen Anlassnamen.


Nichts geloescht ausser der genannten eigenen Testdatei, kein Bild-/
Gesichtsdienst, keine pCloud-Schreibzugriffe, keine Geraeteeingaenge (nur
`ls`/`pull`, lesend), keine kostenpflichtigen Massenlaeufe.
