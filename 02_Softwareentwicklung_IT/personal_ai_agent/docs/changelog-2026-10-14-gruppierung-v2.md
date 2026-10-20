# Änderungsprotokoll 14./15.10.2026: Gruppierung v2 – sauberer Kern, Lebensabschnitte, Andocken

Plan: `.hermes/plans/2026-10-14_gruppierung-lebensabschnitte.md` (Fassung 4, Planprüfung Codex R4 FREI).
Stand dieser Datei: Umsetzung G0–G3 durch den Worker (15.10.2026). **G4 (echter Messlauf) steht aus** –
alle Schwellen unten sind **Startwerte**, keine gemessenen Werte.

## Anlass

Die Gruppierung (`personen_gruppieren.py`, ab hier „v1“) beschreibt jede Person durch **einen**
Mittelpunkt. Eine Person, deren Gesicht sich über die Jahre ändert (Kind), zerfällt in mehrere Gruppen;
unsichere oder grob aufgelöste Gesichter verrauschen die Mittelpunkte (Messung:
`docs/changelog-2026-10-14-mittelpunkte-rauschen.md`). v2 gruppiert nur saubere Gesichter, beschreibt
jede Gruppe über Lebensabschnitte (Phasen) und hängt die übrigen Gesichter danach an. **Der Standard
bleibt v1**, v2 läuft nur mit `--verfahren v2`.

## G0 – Rückweg der Namensarbeit (Handy → PC) mit Inhaltsvergleich

Vorbedingung für G1/G4: Die Regeldateien `personen_bestaetigt.json` und `personen_vorgaben.json`
(die Namensarbeit am Handy) müssen am PC aktuell sein.

- `termux/rueckweg-bereitstellen.sh`: `RUECKWEG_NAMEN` jetzt
  `geschichten.jsonl anlass_umbenennung.jsonl personen_bestaetigt.json personen_vorgaben.json`.
  Statt „gleiche Größe = schon da“ entscheidet die neue Funktion `gleicher_inhalt()`: erst `cmp -s`,
  sonst `sha256sum` (Vergleich der ersten Spalte), sonst – ohne Vergleichswerkzeug – **immer kopieren**.
  Übersprungen wird nur bei gleichem Inhalt (Meldung „schon bereitgestellt (gleicher Inhalt, N Bytes)“).
  Die `.vorher`-Sicherung der alten Fassung bleibt unverändert.
- `tools/handy/rueckweg_holen.py`: `ERLAUBTE_NAMEN` um dieselben zwei Namen erweitert; neu
  `_geraete_sha256(adb, pfad)` (`adb shell sha256sum`, nur 64 Hex-Zeichen werden anerkannt, sonst `""`).
  Übersprungen wird nur bei **gleicher sha256** („uebersprungen (gleicher Inhalt, …)“); kann das Gerät
  keine Prüfsumme liefern, wird **immer** geholt. Nach dem `pull` vergleicht eine Prüfsummenprobe die
  Kopie mit der Gerätesumme („FEHLER Pruefsumme der Kopie weicht von der des Geraets ab“ → zählt als
  Fehler, **keine** Buchung). Manifest, `.vorher`, `.teil`/`os.replace` und „nur die Liste“ unverändert.
- Der Wächter gegen Auseinanderlaufen (Shell-Liste = Python-Liste) bleibt in `test_rueckweg_handy.py`.
- Tests: `backend/tests/test_rueckweg_handy.py` **35 Tests**. Neu (Auswahl): `test_regel1_liste_enthaelt_die_namensarbeit_vom_handy`,
  `test_g0_stufe1_*` (gleich großer **anderer** Inhalt wird kopiert und gesichert; gleicher Inhalt wird
  übersprungen; alle vier Dateien; nur `sha256sum` im Suchpfad; ohne Vergleichswerkzeug immer kopiert) und
  `test_g0_stufe2_*` (alle vier geholt und gebucht; gleich großer anderer Inhalt geholt; gleicher Inhalt
  übersprungen ohne `.vorher`; Gerät ohne Prüfsumme holt immer; Deutung der `sha256sum`-Ausgabe;
  Prüfsummenprobe der Kopie).
- **Geänderte Alttests (inhaltlich nicht abgeschwächt):** Kopfdokumentation und die Attrappen-`adb`
  (kennt jetzt `sha256sum`, abschaltbar über `pruefsumme=False`); der Listentest erlaubt `.json` **und**
  `.jsonl`; `test_regel5_…` verglich mit `set(rh.ERLAUBTE_NAMEN)` (jetzt vier Namen, die Attrappe liefert
  drei Dateien) und vergleicht nun mit `set(INHALT) - {"fremd.jsonl"}` – dieselbe Aussage („jede geholte
  Datei bucht genau eine Zeile“) ohne Abhängigkeit von der Listenlänge.
- **Folge außerhalb dieses Auftrags (nicht angefasst, gehört einem anderen Strang):**
  `tools/foto_sortierung/bestand_pruefen.py` (`STANDARD_RUECKWEG_NAMEN`, Zeile 518) kennt noch die zwei
  alten Namen; der Test `test_rueckweg_liste_spiegelt_das_holwerkzeug` in
  `backend/tests/test_bestand_und_handy_uebergabe.py` meldet deshalb den Unterschied, bis diese Liste
  nachgezogen ist. Das ist eine reine Nachführung der Namensliste, kein Fehler von G0.
- Doku zum älteren Verhalten: Nachtrag in `docs/changelog-2026-10-12-rueckweg-handy-pc.md`.

## G1 – Messlatte: `tools/foto_sortierung/gruppierung_bewerten.py` (neu)

Misst eine Zuordnung an den eigenen Entscheidungen. **Rein lesend, nur Zahlen** (keine Bild-IDs, Namen,
Kennungen, Pfade); ändert keine Schwelle, rechnet nichts neu.

- Kopfzeile „Grundwahrheit“: Namen, benannte Kennungen, gleich / verschieden / ausgeschlossen / fest,
  Stand der beiden Regeldateien. Unter der Mindestmenge (`MIN_NAMEN = 10` **oder** `MIN_REGELN = 50`,
  Startwerte) steht „vorläufig – zu wenig Entscheidungen“; ist eine Regeldatei älter als die Zuordnung,
  steht die Warnzeile „Entscheidungen vom Handy holen (G0)“.
- Kennzahlen: Namens-Reinheit (gleicher Name / anderer Name / unbenannte Gruppe / ohne Kennung),
  Streuung (Namen über Gruppen verteilt), Regelbruch (ausgeschlossen wieder in der alten Kennung;
  „verschieden“ in derselben Gruppe), Gruppen ohne sauberes Gesicht, Größenverteilung, Anteil ohne
  Kennung; im Vergleichsmodus zusätzlich **Wechsel** der sauberen Gesichter.
- Aufruf: einzeln (`--zuordnung`) oder vergleichend (`--vorher`/`--nachher`); fehlende oder unlesbare
  Eingabe = Exit 2 ohne Pfadausgabe.
- Tests: `backend/tests/test_gruppierung_bewerten.py` (23), Szenen mit bekannter Lösung.

## G2 – Phasen und Andocken: `tools/foto_sortierung/personen_phasen.py` (neu, rein, nur numpy)

- `sauber(gesicht)`: `score ≥ 0,90` **und** Ausschnittbreite `bbox[2] ≥ 64 px`. Die Grenzen stehen nur in
  `mittelpunkt_rauschen_messen.py` (`MIN_SCORE`, `MIN_BREITE`) und werden von dort importiert.
- `phasen_bilden`: Jahresmittelpunkte aufsteigend; ein Jahr bleibt in der laufenden Phase, solange seine
  Cosinus-Distanz zum **laufenden Phasen-Mittelpunkt** höchstens `PHASE_BRUCH` beträgt; zu kleine Phasen
  (`< PHASE_MIN`) gehen an den ähnlicheren Nachbarn; Deckel `PHASE_MAX` (ähnlichstes Nachbarpaar wird
  vereint); undatierte Gesichter bilden die **Gesamtphase** `(None, None, Mittelpunkt, Anzahl)`.
- `vergleichen` / `gruppen_vergleich` / `beste_gruppen`: Cosinus zum besten **passenden** Phasen-Mittelpunkt
  (Jahr in der Phase oder höchstens `PHASE_TOLERANZ` Jahre daneben; ohne Datum: beste aller Phasen; die
  Gesamtphase zählt für datierte Gesichter nur, wenn die Gruppe keine datierten Phasen hat). Blockweise
  (`BLOCK` Gesichter × alle Phasen, `np.maximum.reduceat`) – **nie eine n×n-Matrix**.
- `verschmelz_paare`: Gruppenpaare, die sich **Phase gegen Phase** treffen (nur Phasenpaare, deren
  Jahreslücke ≤ `PHASE_TOLERANZ`); so finden Kindheits- und Erwachsenen-Gruppe über die Jahre dazwischen
  zusammen, Geschwister mit verschiedenen Jahrgängen nicht.
- `andocken`: ein Gesicht dockt an die beste Gruppe, wenn die Ähnlichkeit `≥ ANDOCK_SCHWELLE` **und** der
  Vorsprung vor dem besten **anderen Namen** `≥ ANDOCK_ABSTAND` ist (gleichnamige Kennungen konkurrieren
  nicht gegeneinander), die Gruppe kein Gesicht desselben Bildes enthält und die Kennung nicht
  ausgeschlossen ist. Zähler: `angedockt`, `keine_passende_phase`, `unter_schwelle`, `zu_knapp`, `gleiches_bild`.
- **Startwerte der Konstanten (von G4 zu prüfen, nicht gemessen):**

  | Konstante | Wert | Begründung |
  |---|---|---|
  | `PHASE_BRUCH` | 0,10 (Distanz) | knapp 4× die größte gemessene Verschiebung eines Phasen-Mittelpunkts durch Rauschen (0,026, `changelog-2026-10-14-mittelpunkte-rauschen.md`) und gut ein Fünftel unter der Gruppierungsgrenze (Distanz 0,45): echtes Älterwerden zeigt sich als neue Phase, Rauschen nicht |
  | `PHASE_MIN` | 10 | Überschlag (nicht gemessen): der Mittelwert aus 10 Gesichtern liegt ≈ 0,03 Distanz neben dem wahren Mittelpunkt; das Messwerkzeug nutzt für seine Statistik strenger 20 |
  | `PHASE_TOLERANZ` | 2 Jahre | große Lücken schließt das Verschmelzen über die Jahre dazwischen, nicht eine große Toleranz |
  | `PHASE_MAX` | 8 | der Bestand umfasst rund ein Jahrzehnt; mehr wäre feiner als ein Jahr je Phase und treibt nur die Rechenzeit (k × P Vergleiche) |
  | `ANDOCK_SCHWELLE` | 0,65 | strenger als die Zuordnung sauberer Gesichter (0,55), weil unsichere Funde verrauschter sind (Aufschlag +0,10) |
  | `ANDOCK_ABSTAND` | 0,05 | ein Drittel der Spanne zwischen Verschmelzgrenze (0,60) und Zwillingsgrenze (0,45) |

  Die Konstanten stehen mit Kommentar im Code (`personen_phasen.py`); keine wird ohne Zahl aus G4 geändert.
- Tests: `backend/tests/test_personen_phasen.py` (27).

## G3 – Gruppieren v2 in `personen_gruppieren.py`

Schalter: `--verfahren {v1,v2}` (Standard **v1**), `--bewerten` (Bewertung vorher/nachher, nur Zahlen,
schreibt nichts). `--nachtragen` kennt nur v1 (Kombination mit v2 oder `--bewerten` = Fehler, Exit 2).

**Refactor (v1-Verhalten unverändert):** `gruppieren()` benutzt jetzt die geteilten Helfer
`_verschmelzen` (Union-Find mit `gleich`, `verschieden`, cannot-link „selbes Bild“) und `_aussortieren`
(Rauschen, Nummerierung nach Größe); `lauf_rechnen()` ruft den geteilten Abschluss `_lauf_abschluss()`
(Kennungen auf die Gesichter legen, Zwillings-Kandidaten, Beispiele, Altbestand, Bericht). `_anlegen`
bekam den optionalen Parameter `vorab_label`, `kennungen_vergeben` den optionalen Parameter `zaehlung`
(beides ohne Wirkung für v1). Belegt: `gruppieren` (12 Szenen, mit und ohne `vorab_kennung`/`verschieden`/
`gleich`) und `lauf_rechnen` (6 Szenen mit Namen, Regeln, Altbestand) liefern **identische** Ergebnisse
gegen die Fassung aus `HEAD` (Vergleichslauf mit erfundenen Vektoren); die bestehenden v1-Tests
(`test_personen_gruppieren.py`, `test_personen_gruppieren_nachtragen.py`) laufen unverändert grün.

**Ablauf v2** (`lauf_rechnen_v2`, Kern `gruppieren_v2`):

1. **Vorbilder:** je bestätigt benannte Kennung eine Startgruppe aus ihren festen Zuordnungen
   (diese Gesichter sind in der Gruppe fixiert) und – falls `gesicht_zuordnung.jsonl` im Ausgabeordner
   vorliegt – den Gesichtern, die ihr dort zugeordnet waren (ohne ausgeschlossene; nur saubere).
2. **Kern:** nur **saubere** Gesichter; Anlegen wie v1 (nach Qualität, cannot-link), mit den Vorbildern
   als Start; danach `VERFEINERN_RUNDEN` (2) Runden `_verfeinern_phasen`: je Runde werden die Phasen aller
   Gruppen **einmal** neu berechnet, dann alle sauberen Gesichter per Phasenvergleich neu zugeordnet
   (je Bild ohne Doppelung).
3. **Verschmelzen** Phase gegen Phase (`verschmelz_paare`) über `_verschmelzen`: `gleich` vereint (der
   einzige Weg, auf dem es wirkt), `verschieden` und verschiedene Namen trennen, benannte Gruppen
   verschmelzen **nie** über Ähnlichkeit (weder mit unbenannten noch mit anderen benannten); unbenannte
   Gruppen, die einer benannten ähneln, werden nur **gezählt** („aehneln_benannten“). Bei durch `gleich`
   vereinten benannten Gruppen trägt die Gruppe die **kleinste** der beteiligten Kennungen; die andere
   bleibt mit ihrem Namen in `personen_bestaetigt.json` und ihrem Mittelpunkt im Altbestand stehen.
4. **Rauschen:** Gruppen unter `MIN_GROESSE` fallen weg – **ausgenommen benannte**.
5. **Kennungen:** benannte Gruppen behalten ihre Kennung; unbenannte werden über `kennungen_vergeben`
   gegen den **um benannte Kennungen bereinigten** Altbestand stabil vergeben (eine unbenannte Gruppe
   übernimmt nie eine benannte Kennung); neue Nummern setzen hinter der höchsten bekannten (auch
   benannten) fort. Benannte Kennungen **ohne** Gruppe bleiben mit ihrem Mittelpunkt im Altbestand
   (Bericht: „Benannte Kennungen ohne Gruppe“). Der Mittelpunkt einer Gruppe im Altbestand wird aus den
   **sauberen** Gesichtern gerechnet.
6. **Andocken:** alle Gesichter ohne Kern-Gruppe (unsichere, grobe, aus kleinen Gruppen gefallene) über
   `andocken`; Gesichter allein gründen **nie** eine Gruppe; eine feste Zuordnung wird nicht angedockt,
   sondern gilt direkt.
7. **Abschluss** wie v1 (`_lauf_abschluss`): feste Zuordnung vor automatischer Gruppe, Ausschlussregel
   nimmt ein Gesicht aus der Gruppe, Zwillings-Kandidaten, Beispiele.

**Ausgabe** in derselben Form wie v1 (Handy unverändert lesbar). Zusätzlich: `personen_beispiele.json`
trägt je Gruppe `phasen: [{von, bis, anzahl}]` (aus den **sauberen** Mitgliedern, ohne Vektoren) und
`verfahren: "mittelpunkt_phasen"` (v1: `"mittelpunkt"`). Der Bericht (`bericht_text`) hängt bei v2 Zahlen an:
saubere/unsichere Gesichter, Vorbilder, Kern-Gruppen, Phasen gesamt, durch `gleich` vereinte Gruppen,
Gruppen, die einer benannten ähneln, angedockt / nicht angedockt (je Grund), benannte Kennungen ohne
Gruppe – nur Zahlen. **Trockenlauf ist Standard** (ohne `--schreiben` wird nichts geschrieben, Test dazu);
geschrieben wird nur ausserhalb des Repos; vor dem Schreiben sichert **`_stempel_sichern`** (Zeitstempel-
Weg des Neulaufs, nicht `_vorher_sichern`): zwei Schreibläufe → zwei getrennte Sicherungen (Test mit
festgelegter Uhr).

**Tests:** `backend/tests/test_personen_gruppieren_v2.py` (siehe Prüfstand). Sie decken ab: v1 bleibt
Standard; Kind bleibt **eine** Gruppe mit mehreren Phasen (v1 zerreißt dieselbe Szene); Geschwister mit
verschiedenen Jahrgängen werden nicht vereint; Gesicht ohne Datum; unsichere gründen nie; Andocken mit
Abstand zwischen Namen und gleichnamigen Kennungen; `gleich` vereint und der Name bleibt, gleicher Name
**ohne** `gleich` bleibt zwei Gruppen, verschiedene Namen nie; benannt/unbenannt nur Vorschlag-Zählung;
`verschieden`, `ausgeschlossen` (auch beim Andocken), feste Zuordnung gewinnt; Kennungen stabil, nie auf
benannte Kennungen, benannte ohne Gruppe bleiben im Altbestand; Vorbild aus alter Zuordnung; Speicher
ohne n×n (tracemalloc); Trockenlauf, zwei Sicherungen, `--bewerten`; **die v2-Ausgabe läuft durch die
Lesefunktionen von `gruppen_quiz`** (`stand`, `naechste`, `gesichter`, `antworten`).

## Bekannte Grenzen (ehrlich)

- Die **Gründung** läuft wie v1 mit einem laufenden Mittelpunkt und ist **nicht jahresbewusst**. Sehr
  ähnliche Personen (in Probeläufen mit erfundenen Vektoren: Cosinus der Mittelpunkte ≈ 0,7) werden schon
  beim Anlegen zu einer Gruppe; die Phasen verhindern das Zusammenlegen erst bei Gruppen, die nach dem
  Anlegen/Verfeinern getrennt sind (die Tests nutzen Cosinus 0,64–0,65). Ob das im echten Bestand genügt,
  zeigt G4.
- Die Verfeinerung behält ein Gesicht in seiner Gruppe, wenn es zu keiner Gruppe passt (wie v1).
- Alle Schwellen sind Startwerte (Tabelle oben), die Mindestmenge der Grundwahrheit in G1 ebenfalls.
- Die Vorbilder aus der bestehenden Zuordnung übernehmen auch deren Fehler (eine gemischte benannte
  Gruppe liefert gemischte Vorbilder); Gegenmittel sind die festen Zuordnungen und Ausschlüsse.

## Messlauf (G4, durch den Nutzer)

Aus dem Ordner `backend` in PowerShell (Trockenlauf, schreibt nichts):

```powershell
& ".venv\Scripts\python.exe" "..\tools\foto_sortierung\personen_gruppieren.py" --verfahren v2 --bewerten
```

Die Bewertung vergleicht die bestehende `gesicht_zuordnung.jsonl` (vorher) mit dem v2-Lauf im Speicher
(nachher) gegen die Entscheidungen aus `personen_bestaetigt.json` / `personen_vorgaben.json`. Vorher die
Entscheidungen vom Handy holen (G0: `python tools\handy\rueckweg_holen.py --holen`). Erst nach Durchsicht
der Zahlen: `--verfahren v2 --schreiben` (sichert vorher mit Zeitstempel).

## Nachtrag 20.10.2026: fail-closed-Kern (Plan-Fassung 5.3, Schritt 1)

Der Schreibweg von v2 ist seit dem 20.10.2026 **fail-closed**: Regel B (Bestandsschutz benannter
Gesichter, auch unsicherer) mit getrennt gezählten genehmigten Wechseln, `wechsel_unerlaubt` als
Sperrzahl, ein **Kandidatenordner** (`--ausgabe-kandidat`, Standard `~/foto_sortierung/kandidat_v2`)
statt direktem Schreiben in den produktiven Bestand, `--produktiv` als eigener Schalter und ein
**Schreib-Tor** über `--freigabe <datei.json>` (Snapshot-hash, Parameter, Urteil, drei Sperrzahlen;
jede Verletzung → Exit 3, keine Datei). Die vier Schreibprüfungen dieses Strangs laufen deshalb über
`--verfahren v2 --schreiben --produktiv --freigabe …`. Einzelheiten, Belege und die bewusst noch
offenen Auflagen 2–5: `docs/changelog-2026-10-20-gruppierung-v2-fail-closed.md`.

Der obere Abschnitt „Erst nach Durchsicht der Zahlen: `--verfahren v2 --schreiben`“ ist damit
überholt — ohne `--freigabe` schreibt v2 **gar nichts** mehr.
