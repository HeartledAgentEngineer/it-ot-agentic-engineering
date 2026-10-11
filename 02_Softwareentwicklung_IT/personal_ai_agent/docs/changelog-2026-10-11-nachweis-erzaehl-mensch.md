# Nachtrag 11.10.2026: Der Nachweis kennt jetzt Sebastians eigene Erzaehl-Stufen

## Warum

Der Bestandsnachweis (`tools/foto_sortierung/bestand_pruefen.py`, „fertig ist,
was verifiziert ist") zaehlt die gebauten Stufen selbst nach: Plaene, Gesichter,
Beschreibungen, Gruppen, OSM, Bildindex, Neuausrichtung, Anlaesse, Ortsnamen,
Erzaehl-Quellen, Beziehungen, Personen, App-Uebersicht und Doppelten. Es fehlten
die **eigenen Erzaehl-Stufen** — die einzigen Dateien im Erzaehl-Pfad, die
Sebastian SELBST fuellt (Schicht „mensch", geschrieben von der App am Geraet).

| Datei | Inhalt | Gelesen von | Nachweis vorher |
|---|---|---|---|
| `geschichten.jsonl` | Sebastians eigene Erzaehlungen: je Zeile `id`, `ereignis_kennung`, optional `datei_kennung` (Geschichte zu EINEM Bild), `text`, `quelle` (tippen/sprache/import), `ersetzt` (Verweis auf die abgeloeste Fassung). **Nur anhaengend**, je `id` gilt die neueste Zeile | `erzaehl_service` (Erzaehl-Ansicht) **und** `notizen_service` (Notizsuche im Chat), beide ueber `router/chat.py` | keiner |
| `anlass_umbenennung.jsonl` | eigene Anlassnamen: je Zeile `kennung` (Anlass) und `name`; ein **leerer** Name setzt auf den automatischen Titel zurueck. Nur anhaengend, je Kennung gilt die neueste Zeile | `erzaehl_service.eigene_titel()` (Titel in Liste und Erzaehlung) | keiner |

Beide Dateien existieren am PC **nicht** (gemessen: weder in
`~/foto_sortierung` noch sonst unter `C:\Users\sebas`) — sie entstehen am Handy,
sobald im Erzaehl-Bereich eine Geschichte geschrieben oder ein Anlass umbenannt
wird. Faellt eine weg, zeigt ihre Kennung auf einen Anlass, den es nicht mehr
gibt, oder verliert eine Zeile ihre Kennung, **verschwindet Sebastians eigener
Text still** — und es faellt heute niemandem auf. Das ist derselbe blinde Fleck
wie bei OSM (Journal 8), beim Bildindex (Journal 12), bei den Anlaessen
(Journal 19), bei den Ortsnamen (Journal 20), bei den Erzaehl-Quellen
(Journal 21), bei den Beziehungen (Journal 22), bei den Personen (Journal 23),
bei der App-Uebersicht (Journal 24) und bei den Doppelten (Journal 25).

## Was geaendert wurde

Nur Werkzeug, Test und Doku — **kein Betriebs- oder Anzeigecode**.

1. **Neuer Abschnitt „Eigene Geschichten" und „Eigene Titel"** in
   `bestand_pruefen.py` mit drei neuen Namen:
   `anlass_kennungen_sammeln(basis)` (liest die Anlass-Kennungen der drei
   Erzaehl-Quellen — nur Kennungen, nie Titel), `geschichten_lesen(pfad,
   anlass_kennungen=None)` und `eigene_titel_lesen(pfad, anlass_kennungen=None)`.
   Beide Leser werfen nie und geben **nur Zahlen** aus.
2. **Geschichten gezaehlt:** Geschichten (`id` vorhanden — genau das, was der
   Dienst benutzt), verschiedene Anlaesse, Geschichten zu einem Bild, Quellen
   als Zaehler (`tippen`/`sprache`/`import`), Schichten, wie viele Fassungen
   abgeloest sind (`ersetzt`), kaputte Zeilen.
3. **Eigene Titel gezaehlt:** Kennungen mit eigenem Namen, mehrfache Zeilen je
   Kennung (Fassungen), zuletzt **gesetzt** bzw. **zurueckgesetzt**, Zeilen ohne
   brauchbare Kennung.
4. **Ehrlich statt still — vier eigene Pruefungen:**
   * eine Zeile **ohne brauchbare `id`** wird von `erzaehl_service` **verworfen**
     (die Geschichte waere unsichtbar) → Luecke;
   * ein **`ersetzt`-Verweis auf eine nicht vorhandene Kennung** (Fassungskette
     gebrochen) → Luecke;
   * eine Geschichte **ohne Text** → Luecke;
   * **Geschichten und eigene Titel, deren Anlass es im Anlass-Bestand nicht
     mehr gibt** (verwaiste Kennung — der Text zeigt ins Leere) → Luecke. Genau
     das ist der Fehlerfall: er entsteht bei jedem Neu-Lauf der Anlaesse, ohne
     dass jemand die eigenen Texte mitzieht. (In Journal 23 gab es den analogen
     Befund „2 Kennungen ohne Gruppe".)
   Am PC heisst „Datei nicht vorhanden" dagegen ehrlich **„noch nicht
   angelegt"** und **nicht** „Luecke" — sonst stuende dort dauerhaft ein
   Fehlalarm fuer etwas, das die App erst am Geraet erzeugt.
5. **Nur Zahlen:** NIE ein Geschichtentext, NIE ein eigener Titel, keine
   Kennung im Bericht. In den Tests mit Fantasieworten festgehalten
   (`TEXT_DARF_NICHT_ERSCHEINEN`, `TITEL_DARF_NICHT_ERSCHEINEN`).
6. **Abschaltbar** mit `pruefen(..., geschichten=None, titel=None)`, neue
   Konstanten `STANDARD_GESCHICHTEN` / `STANDARD_TITEL`, Modul-Docstring
   nachgezogen (neuer Aufzaehlungspunkt „Eigene Erzaehl-Stufen").

## Belege

* **Tests:** `backend/tests/test_bestand_und_handy_uebergabe.py` von 59 auf
  **63 Testfunktionen** (4 neue: Zaehlung/Quellen/Fassungen an stimmigen
  Dateien; keine Texte/Titel + verwaiste Kennung, gebrochene Fassungskette,
  Zeile ohne Kennung und leere Geschichte als Luecken; ehrliche Meldung bei
  fehlenden Dateien + Abschaltbarkeit; beide Leser tolerant bei fehlender,
  kaputter und fremdformatiger Datei). Lauf der Datei: **63 passed**.
* **Pruefbefehl** frisch und vollstaendig: `cd backend && .venv/Scripts/python -m
  pytest tests/ -q` → **3816 passed, 2 skipped, Exit 0** (195,29 s) — vorher
  3812, also genau die vier neuen Tests, keine Nebenwirkung.
* **Messung am echten Bestand (Exit 0, nur lesend):** `anlass_umbenennung.jsonl`
  und `geschichten.jsonl` sind am PC **noch nicht angelegt** (auch nicht sonst
  unter `C:\Users\sebas`, gemessen) — der Bericht nennt sie ehrlich so, ohne
  Luecke. Die Anlass-Kennungen fuer den Abgleich kommen aus den drei
  Erzaehl-Quellen (2.268 + 2.127 + 78 Zeilen, vorhanden). Ergebnisliste
  **unveraendert 5 Luecken** (vier kosten-/geraetebunden, die fuenfte der
  Personen-Befund aus Journal 23).

## Ehrlicher Neben-Befund (nicht behoben)

Der Abgleich der eigenen Texte gegen den Anlass-Bestand kann erst **greifen,
wenn die beiden Dateien vom Geraet auf dem PC liegen** — und dafür fehlt der
Weg. Gemessen (nicht behauptet): die bestehende Übergabeliste (12 Namen, u. a.
`ordner_ereignisse.jsonl`, `bild_orte.csv`) steht in `termux/start-vorbereiten.sh`
(der gemeinsamen Vorbereitung, zwei Stellen) und noch in der alten
`start-termux.sh` — sie läuft aber **PC → Handy**
(`uebergabe_uebernehmen.py` holt Dateien aus `/sdcard/Download` in den
Termux-Heimordner). `geschichten.jsonl` und `anlass_umbenennung.jsonl` entstehen
am Handy; sie bräuchten den **Rückweg Handy → PC**, den es heute nicht gibt. Ein
Eintrag in die vorhandene Liste wäre die falsche Richtung. Ein Gerät hing in
dieser Runde nicht an `adb` (gemessen: „List of devices attached" leer), also
auch keine Leseprobe. Gemessen und benannt, nicht geändert.

## Ehrlich offen

Am Handy nichts gegengeprueft, kein Bild-/Gesichtsdienst aufgerufen, nichts
geloescht, keine Handy-Eingaenge. Nur eigene Pfade committet (nie `git add -A`);
fremde Aenderungen im Arbeitsbaum (AGENTS.md, typeFREE, docs/experimente,
agentbus-protokoll.md, Rechercheseiten, status.json, `pcloud_agent_schreiber.py`)
blieben unangetastet. `status.json` nicht angefasst (Papa-Zaehler 6.336
unveraendert = nichts nachzutragen).
