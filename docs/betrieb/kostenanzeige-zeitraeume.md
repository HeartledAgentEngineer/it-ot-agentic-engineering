# Kostenanzeige in der Leiste: Zeiträume und eigener Bereich

**Stand:** 06.10.2026 · **Wo:** Hermes-Plugin `context-tank`
(Anzeige `desktop-plugins/context-tank/plugin.js`, Rechnung
`plugins/context-tank/dashboard/plugin_api.py`).

## Die 19 Stufen

Beide Blöcke der Leiste (vorne **Session**, hinten **alle Sessions**) haben je
einen eigenen Schalter. **Ein Klick zählt weiter**, die **Lünette ▾** daneben
öffnet das Menü mit allen Stufen und dem eigenen Bereich.

| Gruppe | Stufen | Fenster |
|---|---|---|
| rollierend | 15 Min · 30 Min · 1 Std · 3 Std · 24 Std · 48 Std · Letzte 7 Tage · 30 Tage · 1 Jahr | jetzt minus n (60 Min = 1 Std, 1 Jahr = 365 × 24 h) |
| kalendarisch | Heute · Gestern · Woche · Vorwoche · Monat · Letzter M. · Vormonat · Jahr · Vorjahr | Heute ab 00:00; Gestern 00:00–24:00; Woche ab Montag 00:00; Vorwoche Montag–Montag; Monat ab 1.; Letzter M. **rollierend** ab gleichem Tag des Vormonats; Vormonat 1.–1.; Jahr ab 1. Januar; Vorjahr 1. Januar–1. Januar |
| sonstiges | Alles | kein Filter |

**Kennungen** (`min15`, `min30`, `stunde`, `std3`, `std24`, `std48`,
`letzte_woche`, `tage30`, `jahr_roll`, `heute`, `gestern`, `woche`, `vorwoche`,
`monat`, `letzter_monat`, `vormonat`, `jahr`, `vorjahr`, `alles`) sind an
**drei** Stellen zeichengleich — eine Abweichung lässt den Abruf ins Leere
laufen und die Anzeige still auf einen Ersatzwert fallen:

1. Anzeige: `desktop-plugins/context-tank/plugin.js` → `PERIODS`
2. Rechnung: `plugins/context-tank/dashboard/plugin_api.py` → `PERIODS`,
   `PERIOD_DEFS`, `_period_window()`
3. Rechenschrift: `docs/experimente/live_zahlen.py` → `ZEITRAEUME`, `fenster()`

**Prüfbefehl für die drei Stellen** (muss 19/19 ohne Abweichung melden):
`fenster()` des Skripts gegen `_period_window()` des Backends über alle
Kennungen vergleichen — Toleranz 90 s, weil „jetzt" zwischen zwei Aufrufen
wandert.

## Eigener Bereich (Custom Range)

Gesetzt wird er **im Menü an der Lünette**: dort steht als letzter Eintrag
**„Benutzerdefinierter Bereich …"**. Er wechselt im selben Menü in eine zweite
Ansicht mit den Feldern **Von / Bis** und „Übernehmen" („← Liste" führt
zurück). Leeres *bis* heißt „bis jetzt". Je Block getrennt gemerkt
(Uhrzeit-Felder in Ortszeit). Die Anzeige schickt das Fenster als
`eigen_von` / `eigen_bis` (Sekunden seit Epoche) an
`/status` bzw. `/status/session/<id>/eigen`; das Backend nimmt die Kennung
`eigen` **nicht** aus `PERIODS`, sondern rechnet genau dieses Fenster.

Im Knopf steht danach das Fenster selbst (`6.10. 9:00-13:53` bzw.
`5.10.-7.10.`). Unbrauchbare Werte (leer, Ende vor Beginn, Text) ergeben
**keinen** eigenen Bereich — dann bleiben die festen Stufen in Kraft, statt ein
falsches Fenster zeigen. Ein eigener Bereich bekommt einen **eigenen
Cache-Schlüssel**; ohne das liefert der Zwischenspeicher beim Wechsel die Zahlen
des vorigen Fensters aus.

Das Menü öffnet **immer nach oben** (`avoidCollisions: false`) und **ohne
Autofokus** (`onOpenAutoFocus` abgeschaltet). Beides gegen Abgeschnittenes: der
Streifen der Statusleiste ist klein, Radix kippt ein zu hohes Menü sonst nach
unten über den Fensterrand — und der Autofokus auf das Datumsfeld scrollte die
Liste selbst nach unten, wodurch der unterste Knopf außerhalb lag. Beide
Eigenschaften reicht die Popover-Komponente der App durch
(`apps/desktop/src/components/ui/popover.tsx`, `...props`).

## Bedienung ohne Sprechblase

Der Chip hat **keine Sprechblase** mehr: die App-Voreinstellung zeichnet sie
weiß auf dunklem Grund (`bg-foreground`, und der kleine Pfeil wird eigens weiß
gefüllt) — von außen nur halb umfärbbar, weil der Pfeil ein eigenes Element ist.
Die Erklärung zur Herkunft der Zahlen steht deshalb als Fußzeile **im Menü an
der Lünette**; eine Backend-Meldung erscheint als kurzes `!` in der Zeile
(Volltext im nativen Tooltip).

## Der Rechenteil wirkt erst nach einem Neustart der App

Python lädt seine Module beim Start; die **Anzeige** wird beim Speichern sofort
neu geladen, der **Rechenteil** nicht. Läuft die App noch mit altem Code,
liefert `/status/session/<id>/heute` **`has_data=false`** → die Zeile sagt
„kein Verbrauch", obwohl Zeilen in der Datenbank stehen. Beweisbarer Merker:
`hermes/kosten/api_calls.jsonl` — solange dort nur die Start-Zeile steht und
keine echten Modell-Aufrufe, läuft die App mit dem Stand von vor dem Neustart.

## Abgleich mit dem OpenRouter-Konto (Logs ↔ Chats)

Werkzeuge (lesen den Management-Schlüssel aus `hermes/.env`, geben ihn nie aus):

| Werkzeug | Aufgabe |
|---|---|
| `hermes/scripts/openrouter_export.py` | holt Aktivität (30 Tage), Schlüssel, Guthaben und schreibt vier CSVs nach `hermes/kosten/` (Zeilen, Tage, Modelle, Schlüssel; USD + EUR + EUR inkl. Aufschlag) |
| `hermes/scripts/kosten_abgleich.py` | Tag für Tag: Konto gegen lokale Datenbank, plus Modell-Bilanz |
| `hermes/scripts/kosten_zuordnung.py` | ein Tag im Detail: Kontozeilen ↔ Chats (Fensterregel des Backends) und Modell-Vergleich |

**Grenzen der Schnittstelle** (gemessen): `/api/v1/activity` liefert nur die
**letzten 30 abgeschlossenen UTC-Tage** — ältere Tage lehnt sie ab
(`Date must be within the last 30 (completed) UTC days`). Einzel-Zeilen
(Tempo, TTFT, Finish-Reason, App, API-Key) gibt der Schlüssel nicht heraus,
diese Sicht existiert nur in der Web-Oberfläche.

**Zuordnung:** die Kontoseite liefert **Tag × Modell** (ohne Chat), Hermes kennt
seine Chats mit Zeitstempeln. Zugeordnet wird daher über das Tagesfenster mit
**derselben** Regel wie die Anzeige (`_where_clause`, `_anteilige_kosten` aus
dem Backend — keine zweite Rechnung). Ergebnis ist auf der Modellebene
prüfbar: deckt sich der Kontobetrag eines Modells mit dem Hermes-Betrag, ist
die Zuordnung belegt; ist das Konto größer, gehört der Rest zu anderen
Schlüsseln/Programmen (erkennbar an Modellen, die Hermes nie benutzt).

Für vergangene Tage bleibt die Hermes-Seite eine **Schätzung** (Fensterregel).
**Exakt** wird sie durch das Aufruf-Protokoll (`docs/betrieb/kosten-protokoll.md`):
es schreibt je Aufruf Chat, Zeit, Modell, Token (inkl. Cache) und Kosten mit —
damit lässt sich jede Kontozeile 1:1 gegen die Aufrufe desselben Tages und
Modells stellen.

### Stundengenau: Kennung je Aufruf (Plugin 1.1.0)

Die Oberfläche zeigt Einzelzeilen (Zeit, App, **API-Key**, Tempo, TTFT, Finish);
der Management-Schlüssel bekommt diese Liste **nicht** (jeder Listen-Endpunkt
antwortet 404). Er bekommt aber die Zeile zu einer **Kennung**:

```
GET /api/v1/generation?id=<kennung>   ->   created_at (UTC, ms), model,
provider_name, tokens_prompt, tokens_completion, native_tokens_cached,
native_tokens_reasoning, total_cost, latency, generation_time, finish_reason
```

Deshalb schreibt das Plugin (`kosten-protokoll`, Fassung **1.1.0**) zu jedem
Aufruf die Kennung (`gen-…`) mit, und `hermes/scripts/kosten_konto_zeilen.py`
holt daraus die Kontozahl: Tabelle `hermes/kosten/konto_zeilen.csv` mit
**Chat, Tag, Stunde, Modell, Anbieter, Input, Output, Cache, Denk-Token,
Kosten in USD / EUR / EUR inkl. Aufschlag, Finish, Dauer, Kennung** — dieselben
Werte wie im Log, nur mit dem Chat verbunden. Ablage je Kennung:
`hermes/kosten/konto_zeilen.json` (idempotent, holt nur Neues).

Gemessen (06.10.2026): der Aufruf `gen-1791303973-…` lieferte 18:26:13 lokal,
Anbieter `Together`, 5/6 Token, 0,0000171 USD, Finish `length`, 158 ms — die
Kontozahl stimmt mit der Antwort des Modells überein. Die Zeile erscheint mit
**Sekunden bis etwa einer Minute Verzögerung** (erster Versuch: 404, danach da).
Weil die Zeit vom Konto kommt, ist die Zuordnung **taggenau und stundengenau**,
ohne Schätzung.

## Tages- und Stundenkurve je Chat (Schätzung)

`hermes/scripts/kosten_chat_tage.py` verteilt die **Lebenszeit-Summe** eines
Chats nach der **echten Aktivität** (Nachrichten je Tag aus `messages`, für den
laufenden Tag je Stunde) — nicht mehr gleichmäßig über die Laufzeit. Das
behebt die Verzerrung der alten Tagesreihe (0,07 USD/Tag, 13,40 USD am 01.10.).

Bearbeitet werden die elf Chats aus Sebastians Liste (Sitzungskennungen im
Skript): agentic enineering optimierungen · Unterschrift in Erklärung ·
PDF für Kühlschrank-Plan · Offene Sessions vom Handy · KI-Datenschutz ·
Fritzbox 4749 · Whiteboard-Screenshots · KI-Beauftragter · Speicherkarte
entlasten · entwicklung my agent · Weiterbildung New Horizons.

Ergebnis: `hermes/kosten/chat_tage.csv` (je Chat und Tag) und
`hermes/kosten/chat_stunden_heute.csv` (je Chat und Stunde, laufender Tag).
Beide Spaltensätze enthalten USD, EUR und EUR inkl. Aufschlag sowie die Spalte
`Art` = `geschätzt`.

**Aufruf `--heute-alle`:** wertet **alle** Chats mit Aktivität heute aus (nicht
nur die feste Liste) und zeigt je Chat die Stundenverteilung — damit fehlt kein
Chat mehr, auch wenn er nicht in der Liste steht (z. B. die
Transkriptions-App). Gemessen am 06.10.2026: Weiterbildung 2,260 € ·
agentic enineering 1,496 € · Type-Free App 0,440 € → **4,196 € von 4,87 €**
des Kontos (86 %). Gegenprobe: keine Sitzung hat heute neu begonnen und es gibt
keine Sitzung mit Verbrauch heute ohne Nachrichten heute — der Rest liegt also
nicht in Hermes' Datenbank (anderer Client am selben Schlüssel oder anderer
Schlüssel des Kontos). In der Datenbank beginnt Hermes' Tag heute um 12:00.

**Grenze:** das bleibt eine Schätzung — die Datenbank kennt je Chat keine
Tagesspalte, das Konto kennt keine Chats. **Exakt** werden Tag und Stunde ab
dem Neustart über die Aufruf-Kennung (Abschnitt oben).

## Getrennte Schlüssel — Handy bekommt eigenen Schlüssel

Am 06.10.2026 angelegt (über die Verwaltungs-Schnittstelle, idempotent — ein
zweiter Lauf legt nichts doppelt an):

| Schlüssel | Verbrauch | Limit | Rolle |
|---|---|---|---|
| **Hermes Agent** | 184,90 USD | keins | **dieser PC** (Prüfsumme abgeglichen) |
| agentic enineering | 19,87 USD | keins | zweite Installation |
| personal_ai_agent | 14,62 USD | keins | Hermes-Erweiterung für den persönlichen AI Agent |
| critic-Skill | 3,47 USD | keins | Prüf-Skill |
| typeFree | 0,39 USD | keins | Sprachtranskription (eigener Zweck) |
| vorlesen-tts | 0,28 USD | **5 USD** | Vorlesen |
| **hermes-handy** | 0,00 USD | keins | **neu** für Hermes auf dem Handy |

**Wert wird nie im Chat ausgegeben.** Er liegt in
`hermes/kosten/uebergabe_hermes_handy.txt` samt Einrichtungsschritten (aufs Handy
bringt ihn **Sebastian selbst** — der Agent legt nichts aufs Handy).
Rücknahme: in OpenRouter unter *Settings → Keys* löschen, im Handy die alte
Zeile eintragen. Jede schreibende Operation steht in
`hermes/kosten/manifest_schluessel.jsonl`.

**Warum:** läuft das Handy-Hermes (oder ein anderes Werkzeug) über denselben
Schlüssel, ist sein Verbrauch nur als Differenz sichtbar. Mit eigenem Schlüssel
ist er auf Schlüsselebene ausgewiesen — genauso getrennt wie `typeFree` und
`vorlesen-tts`.

## Prüfung: deckt sich die Zuordnung mit dem Konto?

`hermes/scripts/kosten_pruefung.py` stellt **jeden** der 30 verfügbaren
Kontotage Modell für Modell gegen die lokale Datenbank. Ergebnis vom 06.10.2026
(23 Tage mit Verbrauch, 77 Modelltage):

| Tag | Konto | lokal | exakte Deckung |
|---|---|---|---|
| 05.–14.09. | 3,95 – 11,45 USD | **je 0,07 USD** | keine |
| 15.09. | 24,18 | 26,36 | keine |
| 22.09. | 0,26 | 1,80 | keine |
| 26.09. | 0,48 | 2,16 | keine |
| **27.09.** | 17,76 | 4,70 | **gpt-5.6-luna, gemini-3.7-flash** |
| 28.09. | 14,18 | 7,54 | keine |
| Summe | **128,21 USD** | **73,88 USD** | **2 von 77** |

**Bedeutung:** die Tageszuordnung aus der Datenbank ist **nicht** taggenau. Sie
liegt an ruhigen Tagen zu hoch (22.09.: 1,80 statt 0,26) und an starken Tagen zu
niedrig (15.09.: 24,18 statt 26,36; 28.09.: 7,54 statt 14,18), weil
`session_model_usage` nur Anfangs- und Endzeitpunkt je Zeile kennt und die
Laufzeit gleichmäßig verteilt. Fremde Modelle sind dagegen sauber erkennbar
(z. B. 27.09. `gemini-2.5-flash` 3,44 USD — in der Datenbank überhaupt nicht
vorhanden).

**Folge:** taggenau je Chat ist **nur** über die Aufruf-Kennung zu bekommen
(Abschnitt oben), also ab dem Neustart. **Stundengenau rückwärts ist nicht
möglich** — die Kontoschnittstelle liefert keine Einzelzeilen mit Uhrzeit, sie
gibt sie nur zu einer bekannten Kennung heraus.

### Tagesreihe korrigiert (06.10.2026)

Die Tagesreihe (`daily`) summierte die **ganze** Laufzeitsumme einer Zeile auf
den Tag von `last_seen` — daher 13,40 USD am 01.10. und 0,07 USD/Tag im
September. Neue Regel, in dieser Reihenfolge:

1. **Tag im Kontofenster** (`hermes/kosten/openrouter_activity.json`, vom
   Auswerter geholt): der **abgerechnete Kontobetrag** gilt (`source: konto`).
   Fehlt der Tag dort, war der Verbrauch **null** — ebenfalls exakt.
2. **Tag außerhalb des Fensters** (heute, ältere Tage): Schätzung nach echter
   **Aktivität** — Lebenszeit-Summe des Chats mal Anteil der Nachrichten genau
   dieses Tages (`source: geschaetzt`). Die frühere Zeitverteilung wurde dabei
   verworfen: sie lieferte an einem stillen Tag 0,88 USD, an dem das Konto 0
   zeigt.

Gemessen nach dem Umbau: 30.09. 5,3221 · 01.10. 3,4358 · 02.10. 0,0549 ·
03.10. 0,0000 · 04.10. 0,0035 (alle `konto`) · 05.10. 0,0000 · **06.10. 3,7115
USD = 4,40 EUR inkl.** (`geschaetzt` — passt zur Schlüsselzahl 5,09 EUR des
Tages, der Rest ist außerhalb von Hermes).

**Zwei eigene Fehler dabei gefunden und behoben:** doppeltes `WHERE` (der
Ausdruck aus `_where_clause` bringt das Wort schon mit) und doppeltes `SUM`
(`_anteilige_kosten` summiert selbst). Beide wurden von einem stillen
`try/except` verschluckt und als 0,00 ausgegeben — deshalb jetzt: erst rechnen,
dann prüfen, nicht schlucken.

## Anzeige erkennt den alten Rechenteil selbst

Jede Antwort des Rechenteils trägt ihre Fassung (`version`) **und** den Zeitraum,
den sie tatsächlich **benutzt** hat (`period`). Die Anzeige prüft beides und
schreibt bei Abweichung gelb in die Zeile:

| Merker | Bedeutung | Werkzeugtip |
|---|---|---|
| **Zeitraum unbekannt** | Die Antwort rechnet `alles`, obwohl ein anderes Fenster gewählt ist — der Rechenteil kennt die Stufe nicht | „kennt der Rechenteil nicht … die Zahl ist NICHT das gewählte Fenster" |
| **Neustart nötig** | `version` der Antwort ≠ `ERWARTETE_RECHENTEIL_VERSION` | beide Fassungsnummern |

Der erste Merker wirkt **sofort**, auch bei einem alten Rechenteil (alle Stände
tragen `period` in der Antwort). Anlass: „24 Std" zeigte 7,49 € — das war die
Lebenszeit des Chats, weil der laufende Rechenteil die Stufe nicht kannte und
stillschweigend auf `alles` zurückfiel.

**Regel:** bei jeder inhaltlichen Änderung am Rechenteil `VERSION` in
`plugin_api.py` erhöhen **und** `ERWARTETE_RECHENTEIL_VERSION` in `plugin.js`
nachziehen — sonst schweigt der zweite Merker. Beide Merker sind im Prüfstand
gegen eine künstlich alte Antwort geprüft (`version 1.5.0`, `period 'alles'`
bei gewähltem `heute`): sie erscheinen, mit Fassungsnummer.

## Zwei Regeln, die aus Fehlern entstanden sind

**1. Eine Zeile zählt, wenn sie das Fenster ÜBERSCHNEIDET** (nicht: wenn sie
darin berührt wurde). Vorher fielen Zeilen heraus, die vor dem Fenster begannen
und danach weiterliefen — „Gestern" stand deshalb auf 0,00 €, obwohl an dem Tag
gearbeitet wurde (nachgemessen: 0,00 → 0,72 €). Die **Höhe** je Zeile bleibt
zeitanteilig (`_anteilige_kosten()`), es ändert sich nur die Auswahl der Zeilen.
Für „Heute" und „Alles" ändert die Regel nichts.

**2. Mitternacht Ortszeit wird ohne UTC-Versatz gerechnet.** `now.replace(...)`
behält den Versatz von **heute**; für ein Datum im Winter ergibt das eine Stunde
Versatz („1. Januar" wurde als 31.12. 23:00 gerechnet, betraf `Jahr` und
`Vorjahr`). Siehe `_epoch_lokal()` im Backend und `_mitternacht_epoch()` im
Skript.

## Was die Zahlen sind — und was nicht

Die lokalen Werte sind **zeitanteilig geschätzt**: eine Kostenzeile trägt nur
den Teil ihrer Laufzeit bei, der ins Fenster fällt. `state.db` hat keine
Tagesspalte. **Exakt** werden die Werte pro Aufruf erst durch das
Aufruf-Protokoll (`docs/betrieb/kosten-protokoll.md`) — es schreibt ab dem
nächsten Start jedes Modell-Aufruf einzeln mit.
