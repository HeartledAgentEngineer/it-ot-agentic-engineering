# Änderungsprotokoll 10.10.2026: Wissensdatei (memory.db) im Widget-Start übernehmen

Anlass: Befund des Nachtlaufs vom 10.10.2026 (04:49). Der Chat am Handy sucht die
Wissensdatei standardmäßig unter `~/memory.db` — dort lag eine **alte Kopie**. Das
Startlog vom 10.10. zeigt sie (`Wissensspeicher gefunden:
/data/data/com.termux/files/home/memory.db`, `Vektoren geladen: (30891, 1024)`): 30.891
Vektorzeilen sind exakt der Stand **vor** dem WhatsApp-Vollimport. Beim Fragen kam
deshalb kein einziger WhatsApp-Zusammenhang an, obwohl der Bestand komplett vorliegt.

## Befund mit Zahlen

Die frische Datei liegt unbenutzt in `/sdcard/Download/memory.db` (230,4 MB,
byte-identisch zum PC, md5-gleich; Textschicht mit denselben Zahlen wie der Archiv-Index:
**241.402 WhatsApp-Nachrichten in 481 Gesprächen**, WhatsApp-Anteil 21.788 Abschnitte; der
Archiv-Index trägt dieselben Abschnitte mit Vektor).
**Kein Startweg übernahm sie:** `start-termux.sh` bringt beim Start nur
`archiv_index.db` nach `~/` — das ist eine **andere** Datei (der Index für die neue
`archiv_suche`), nicht die Wissensdatei des alten Dienstes. Der tatsächlich benutzte
Startweg ist das Widget (`~/.shortcuts/agent` → `termux/agent-start`); der kam an der
`memory.db` vorbei. Beim Einbau geprüft: eine `memory.db`-Übernahme gab es in **keinem**
Startskript — die frühere Annahme, sie stehe schon in `start-termux.sh`, trifft nur auf
die `archiv_index.db` zu.

## Was neu ist

**Neu `termux/wissensdatei-uebernehmen.sh`** (184 Zeilen, reine LF-Zeilenenden, nur
`cp/mv/sha256sum/stat/date`; **kein** Netz, kein Cloud-Abruf, keine Zugangsdaten; das
Skript enthält kein `rm`). Verhalten:

1. **Gleiche sha256** (Quelle = Ziel): Es passiert **nichts** — still, kein Kopieren bei
   jedem Start (idempotent). Nur eine Beleg-Zeile ins Protokoll.
2. **Andere/neuere Quelle:** Die vorhandene Ziel-Fassung wird **zuerst** als
   `~/memory.db.vor_<datum>` gesichert (bei mehreren Übernahmen am selben Tag `_2`,
   `_3`, … — eine vorhandene Sicherung wird nie überschrieben), **erst dann** kopiert:
   erst als `<ziel>.teil` im selben Ordner, Prüfsumme vergleichen, dann an ihren Platz
   setzen (es entsteht nie eine halbe Wissensdatei). Es wird **nie etwas gelöscht**; die
   Quelle bleibt in `/sdcard/Download` liegen.
3. **Protokoll:** jede Aktion mit Zeitpunkt, Größe und sha256 **von Quelle und Ziel**,
   ob kopiert oder übersprungen — in
   `/sdcard/Download/hermes_diag/wissensdatei_uebernahme.log` (derselbe kabel-lesbare
   Diagnose-Ordner wie die übrigen Startprotokolle; der Termux-Heimordner ist über das
   Kabel nicht lesbar). Ab mehr als 200 KB bleiben die letzten 500 Zeilen (Muster
   `agent-ensure.sh`).
4. **Fehlertolerant:** fehlende Quelle, nicht gemounteter Speicher, nicht lesbare
   Prüfsumme, misslungene Kopie → klare Zeile ins Protokoll, Ziel unverändert, Exit 0.
   Der Start bricht nie ab (darüber hinaus sichert `|| true` am Aufrufer ab).

**Geändert `termux/agent-start`** — der benutzte Widget-Weg: Der Aufruf steht in
`termux/agent-start:167` (nach dem `git pull`, vor dem Serverstart, mit `|| true`):

```bash
bash "$HIER/wissensdatei-uebernehmen.sh" || true
```

Entscheidung zum Ort (nach dem vorhandenen Aufbau, nicht nach Geschmack): Die Logik der
Uploads/Übernahmen liegt als eigenes Skript vor (`pcloud-schluessel-uebernehmen.sh`,
`schluessel-uebernehmen.sh`, `sicherung-auftrag.sh` — alle aus `agent-start` gerufen;
`start-termux.sh` und `agent-ensure.sh` rufen dieselben Skripte). `termux/gemeinsam.sh`
ist eine reine Hilfsbibliothek ohne Nebenwirkungen beim Einbinden und bleibt dafür frei.
Deshalb: eigene Datei + Aufruf im Widget-Weg.

Bewusst **nicht** angefasst: `start-termux.sh` und `termux/agent-ensure.sh` (der Auftrag
war der tatsächlich benutzte Weg; der Aufruf ist dort je eine Zeile, falls gewünscht),
und die `archiv_index.db`-Übernahme (andere Datei, bleibt wie sie ist).

## Prüfung

- **6 neue Fälle** in `backend/tests/test_wiederherstellung.py` (echte Skriptläufe in
  Git Bash mit erfundenen Dateien, im Muster der Wiederherstellungs-Tests):
  - Syntax: Shebang, reine LF (kein `\r\n`), kein `rm`, kein Netz-Wort
    (`pcloud/curl/wget/adb/http/git`), `bash -n` Exit 0;
  - (a) gleiche Prüfsumme → kein Kopieren: stdout leer, Ziel-mtime unverändert, keine
    Sicherung, keine temp-Datei, Protokoll-Zeile „uebersprungen" mit Größe + sha256;
  - (b) unterschiedliche Datei → Sicherung angelegt UND kopiert; Quelle bleibt liegen;
  - (d) Reihenfolge: die Sicherung trägt den **alten** Inhalt, das Ziel den neuen (am
    Inhalt belegt, nicht nur behauptet), und im Protokoll steht „Sicherung angelegt" vor
    „uebernommen (kopiert)";
  - (c) fehlende Quelle → Exit 0, Ziel unberührt, klare Zeile „Quelle fehlt … Start
    laeuft weiter";
  - Erstlauf ohne Ziel → kopieren ohne Sicherung (`sicherung=keine`); zweiter Lauf
    idempotent (keine zweite Sicherung, Ziel-mtime unverändert).
- **1 Wächter** in `backend/tests/test_widget_agent_start.py`: `termux/agent-start`
  ruft genau einmal auf, mit `|| true`, **nach** dem Pull und **vor** dem Serverstart.
- `bash -n` auf `termux/agent-start` und `termux/wissensdatei-uebernehmen.sh`: Exit 0;
  beide Dateien (und die geänderten Testdateien) auf zeilenendengenau geprüft —
  Shell-Dateien: 0× CRLF.
- Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q` →
  **3654 passed, 2 skipped, Exit 0** (Lauf über die Tor-Sperre, 618,69 s; im selben
  Baum arbeitet parallel ein zweiter Agent — seine Tests sind in der Zahl enthalten).
  Ein erster Lauf war an einer **fremden Dateisperre** rot
  (`test_chat_endpoint.py::test_grenze_delegiert_statt_normalem_chat`, WinError 32 auf
  `auftraege.json.tmp` bei paralleler Arbeit im geteilten Baum); der Test lief isoliert
  **1 passed**, der zweite Gesamtlauf ist grün.
- **Ehrlich offen:** Der erste echte Widget-Tipp am Handy steht aus — erst danach ist
  der Übernahme-Eintrag im `hermes_diag`-Protokoll am Gerät belegbar. Vom PC wurde
  nichts ans Gerät geschickt; am Gerät wurde nichts geändert.
