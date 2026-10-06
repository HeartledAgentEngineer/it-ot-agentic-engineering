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
