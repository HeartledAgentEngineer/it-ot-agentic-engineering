# Änderungsprotokoll 25.10.2026 — Tagesimport am Handy (C1 + C2)

Plan: `.hermes/plans/2026-10-25_tagesimport-handy.md` (Fassung 1), Schritte **C1** (Werkzeug) und **C2** (Einbindung in den Start).

## Zweck

Einmal am Tag sollen die lokalen Quellen des Handys nachgeholt werden: WhatsApp-Bilder in die pCloud, die Kamera-Fotos zählen, Erinnerung an den Gemini-Export. Das Werkzeug ist rein deterministisch (kein Sprachmodell, kein Agent) und läuft ohne Cron: der App-/Widget-Start stößt es an.

## Was neu ist

| Datei | Inhalt |
|---|---|
| `tools/handy/tageslauf.py` | das Tageslauf-Werkzeug (Termux, nur Standardbibliothek plus `whatsapp_bilder_gemeinsam.py`) |
| `termux/start-vorbereiten.sh` | neuer Schritt 10: `tageslauf.py --wenn-faellig` im Hintergrund |
| `backend/tests/test_tageslauf.py` | 83 Tests (offline, erfundene Daten in `tmp_path`) |

## Aufruf

```
python -B tools/handy/tageslauf.py --wenn-faellig   # nur wenn heute noch kein vollständiger Lauf war
python -B tools/handy/tageslauf.py --jetzt          # von Hand, ignoriert die Fälligkeit
python -B tools/handy/tageslauf.py --trocken        # zeigen, nichts schreiben
```

Genau einer der drei Modi ist Pflicht. Weitere Optionen: `--daten-ordner` (Standard `~/foto_sortierung`, Umgebungsvariable `TAGESLAUF_DATEN`), `--log-ordner` (Standard `<Download>/hermes_diag`), `--w1-skript` und `--w1-zeitgrenze` (für Tests; Standard 7200 s).

## Schalter

`~/foto_sortierung/tageslauf.json`. Fehlt die Datei, gilt `{"an": false}`. **Nur ein echtes `true` schaltet ein** (`"true"`, `1`, `"ja"` zählen als aus). Ist der Schalter aus — in jedem Modus —, erscheint die Zeile `Tagesimport: aus`, Exit 0, und **nichts wird geschrieben** (auch kein Datenordner, keine Stand-Datei, kein Log). Eine unlesbare Einstellungsdatei zählt ebenfalls als aus, meldet das und endet mit Exit 3.

Weitere Schlüssel in derselben Datei:

- `kamera_ordner`: pCloud-Pfad des Kamera-Ordners (kein Standardwert; ohne ihn „Kamera: nicht eingerichtet“).
- `gemini_letzter_export`: ISO-Datum des letzten Takeout-Exports.

Beispiel: `{"an": true, "kamera_ordner": "/<pCloud-Pfad>", "gemini_letzter_export": "2026-10-20"}`.

## Fälligkeit und Stand

Fällig ist der Lauf, wenn `~/foto_sortierung/.tageslauf_stand.json` kein `letzter_gesamtlauf` mit dem **heutigen lokalen Datum** enthält (fehlende oder defekte Datei = fällig). Der Stand wird **nur bei vollständigem Erfolg** fortgeschrieben (alle aktiven Bausteine Exit 0 und nicht übersprungen); sonst läuft der nächste Start erneut. Er trägt außerdem das Datum je erfolgreichem Baustein (`wa_bilder`, `kamera`) und die Kamera-Zahl (`kamera_zahl`) für den nächsten Vergleich.

## Bausteine

Jeder Baustein läuft isoliert; ein Fehler (auch eine unerwartete Ausnahme) stoppt die anderen nicht.

1. **WhatsApp-Bilder:** Unterprozess `python -B tools/handy/whatsapp_bilder_hochladen.py --schreiben` (ohne `--max`), Zeitgrenze 2 Stunden (Überschreitung = Fehler). Gelesen werden die W1-Zeilen `hochgeladen N`, `fehler N`, `abgebrochen` und im Trockenlauf `neu N`; der W1-Exit-Code wird übernommen (0 ok, 1 Fehler, 2 Aufruf/Schutz, 3 Voraussetzung fehlt; Exit 0 ohne lesbare Zählzeile gilt als „nicht prüfbar“, Exit 3). Bei W1-Exit 3 und bei überschrittener Zeitgrenze trägt die Zeile den festen Zusatz „W1-Sperre/Manifest prüfen“ (keine Rohausgabe von W1): ein harter Abbruch kann die W1-Sperre oder eine halbe Manifestzeile hinterlassen, dann endet jeder Folgelauf mit Exit 3. Im Trockenlauf läuft W1 **ohne** `--schreiben`. Dies ist der einzige Schreibweg in die pCloud; jede Operation steht im W1-Manifest (`~/foto_sortierung/whatsapp_bilder_manifest.jsonl`) und W1 hat seine eigene Sperre.
2. **WhatsApp-Chats:** Platzhalter, Zeile „WhatsApp-Chats: nicht eingerichtet (W2 Teil B)“, zählt nicht als Fehler.
3. **Kamera zählen (nur lesend):** eine pCloud-Abfrage `listfolder` auf `kamera_ordner` über `whatsapp_bilder_gemeinsam.zugang_aufloesen()` und `uebergabe_hochladen._api_lesen` (deren Positivliste lesender Methoden). Nicht rekursiv: gezählt werden die Dateien direkt im Ordner, keine Unterordner. Die Funktion `_pcloud_lesen` lehnt jede andere Methode als `listfolder` ab. Unzulässige Ordner (kein führendes `/`, `..`, Rückstrich, `//`, ein Pfadteil mit „crypto“) werden nicht gelesen (Exit 2). Ausgabe: „Kamera: N neue Dateien seit letztem Lauf“ bzw. beim ersten Lauf „Kamera: N Dateien (Grundstand)“; ohne Dateinamen.
4. **Gemini:** nur Erinnerung aus `gemini_letzter_export`: fehlt der Wert, ist er ungültig oder liegt er in der Zukunft oder mehr als 60 Tage zurück, steht „Gemini: Takeout-Export fällig (alle 2 Monate)“, sonst „Gemini: ok (letzter Export vor N Tagen)“. Kein Netz, nie ein Fehler.

## Schutz

- **Nie löschen.** Gelöscht wird einzig die eigene Sperrkennung beim Freigeben der Sperre (`os.remove` an genau zwei Stellen, Wächtertest zählt mit).
- **Sperre** `.tageslauf.sperre` im Datenordner (`os.mkdir`, atomar) mit Kennungsdatei (Kennung, PID, Startzeit). Läuft schon ein Lauf (Sperre jünger als 6 Stunden): „Tagesimport: läuft bereits“, Exit 0. Nur eine Sperre mit eigener Kennung und Alter über 6 Stunden gilt als verwaist und wird abgeräumt; eine alte Sperre ohne Kennung bleibt liegen: „Sperre unklar, nicht gestartet“, Exit 3. Im Trockenlauf gibt es keine Sperre. Freigegeben wird nur, wenn die Kennung stimmt (auch nach Ausnahmen).
- **Akku:** ist `termux-battery-status` vorhanden und meldet unter 20 % ohne Laden, wird der schreibende Baustein 1 übersprungen („WhatsApp-Bilder: übersprungen (Akku niedrig)“, Exit 0). Der Tag gilt dann nicht als erledigt (Stand nicht fortgeschrieben). Fehlt der Befehl oder ist die Ausgabe unlesbar: weiter.
- **Stand-, Bericht- und Sperrdatei:** keine symbolischen und keine harten Links (Exit 2), Daten- und Log-Ordner nie in einem Git-Repo (Exit 2), Schreiben atomar (Temp-Datei im selben Ordner, fsync, `os.replace`).
- **Ausgabe:** Zeilen auf stdout, an `<Download>/hermes_diag/tageslauf.log` angehängt (mit Zeitstempel; nur wenn der Download-Ordner existiert; Best Effort) und im letzten Bericht `~/foto_sortierung/tageslauf_bericht.json` (Version, Zeit, Datum, Modus, Exit, `stand_fortgeschrieben`, je Baustein Name/Status/Exit/Text/Zahlen). Es erscheinen **nur Zahlen und feste Texte**: keine Pfade, Namen oder Dateinamen; die Ausgabe des W1-Unterprozesses wird nie weitergereicht. Das Log wird nicht gekürzt (je Tageslauf wenige Zeilen).

## Exit-Code

Schlechtester Exit der Bausteine: 0 ok · 1 Fehler in einem Baustein · 2 Aufruf-/Schutzverstoß · 3 nicht prüfbar. Nicht fällig oder bereits laufend: 0.

## C2: Einbindung in den Start

`termux/start-vorbereiten.sh` (läuft bei jedem App-/Widget-Start, auch mit `--laufend`) hat am Ende einen Schritt 10:

```
if [ -f "$PROJEKT/tools/handy/tageslauf.py" ]; then
    ( cd "$PROJEKT" && nohup python -B tools/handy/tageslauf.py --wenn-faellig --log-ordner "$PROTO_DATEN" >/dev/null 2>&1 & ) || true
fi
```

Er steht nach Sicherung auf Auftrag und Postfach-Daemon, ist entkoppelt (nohup, Ausgabe nach /dev/null) und kann den Start weder blockieren noch scheitern lassen. Die Datei hat durchgehend LF; `bash -n` ist sauber.

## Tests

`backend/tests/test_tageslauf.py`: **83 Tests**, Verlauf rot → grün.

- Vor dem Bau (Werkzeug fehlte, `start-vorbereiten.sh` noch ohne Schritt): `5 failed, 1 passed, 77 errors` (der eine grüne Test prüft, dass der Start auch ohne Werkzeug läuft).
- Nach dem Bau: `83 passed`; nach der Ergebnisprüfung R1 (fester Hinweis bei Exit 3/Zeitgrenze): `84 passed`.

Abgedeckt: Schalter aus (drei Modi, fehlende/explizite/unlesbare Einstellungen, Spion auf alle Schreibwege und den Unterprozess, Momentaufnahme des Verzeichnisses vorher/nachher), Fälligkeit (heute/gestern/defekt, `--jetzt`), Gesamtlauf (Stand, Bericht, Log, keine Reste), Sperre (Doppelstart, verwaist mit Kennung, alt ohne Kennung, jung ohne Kennung, Freigabe nach Ausnahme, keine Sperre im Trockenlauf), Akku (Auswertung der Ausgabe, überspringen, Laden, fehlender Befehl), Baustein-Fehler isoliert (W1-Exit 1/2/3 mit Attrappe, Zeitgrenze, fehlendes Werkzeug, unlesbare Ausgabe, Ausnahmen in Kamera/Baustein), Kamera mit Attrappe des lesenden Weges (nur `listfolder`, Grundstand, neue Dateien, keine Dateinamen, unzulässige Ordner), Gemini-Erinnerung (Grenzfälle 60/61 Tage, Zukunft, ungültig), Bericht ohne Pfade/Namen, Trockenlauf ohne Schreiben, Schutz (Repo, symbolischer und harter Link, atomares Schreiben, kein Löschweg im Quelltext), Exit-Code, Wächter für `start-vorbereiten.sh` (Aufruf, Hintergrund, `|| true`, Reihenfolge, LF, `bash -n`, echter Lauf in Git Bash: Start blockiert nicht, `--wenn-faellig` und `--log-ordner` kommen an, Start läuft auch ohne Werkzeug).

## Offen

- Sebastian schaltet ein (`tageslauf.json` mit `"an": true`).
- Kamera-Ordner eintragen (`kamera_ordner`).
- C3: Anzeige und Schalter im Checks-Fenster der App folgt (Bericht liegt dafür in `tageslauf_bericht.json`).
- Der erste echte Lauf am Handy (C4) ist nicht verifiziert.
- Nach einem harten W1-Abbruch (Zeitgrenze) räumt der Tageslauf die W1-Sperre nicht selbst ab; das bleibt ein Handgriff (Zeile „W1-Sperre/Manifest prüfen“).
- Kamera: Der Plan sah einen Eintrag in eine Aufgabenliste für den PC-Gesichterlauf vor. Eine solche Aufgabenliste gibt es im Projekt nicht; gebaut ist nur die Zählung. Der Gesichterlauf über neue Kamerabilder bleibt ein eigener Schritt am PC.
