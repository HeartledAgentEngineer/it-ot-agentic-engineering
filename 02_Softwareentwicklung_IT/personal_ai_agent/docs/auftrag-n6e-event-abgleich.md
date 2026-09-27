# Feinauftrag N6e — Event-Abgleich (Vorschlag statt Neubau)

> Teil des Nachtlaufs 26./27.09.2026, siehe `docs/plan-nachtlauf-2026-09-26.md`.
> **Rollen:** Planer = Hauptagent · Ausführer = Hermes-Subagent
> (`deepseek-v4.1-flash`; Codex ist gesperrt bis 15.10.2026) ·
> Prüfer = `openai/gpt-5.6-luna` (andere Modellfamilie).

## Warum

Nach N6d steht fest, **wohin** sortiert wird:
`Agent/Fotos/<Jahr>/<Kategorie>/<Event>`. Die Kategorie kommt aus dem Bucket,
der Event-Name bisher aus dem Datums-Block (`2025-01-06_Anlass-01`).

Sebastian hat in seiner eigenen Ablage aber **schon** Event-Ordner, teils seit
2013, nach drei erkennbaren Mustern:

| Muster | Beispiele aus dem Bestand (Musterform, ersetzt durch Platzhalter) |
|---|---|
| `Jahr Ort` | `2013 <Ausflugsziel>`, `2020 <Stadt>` (Urlaub, Ausflüge) |
| `Jahr_Monat[_Tag] Ereignis` | `2018_11_25 <Band>`, `2019_08 <Festival>`, `2018_3 <Party-Name>` |
| `Jahr Person` | `2017 <Vorname>`, `2020+ <Vorname>` (Familie, Freunde) |

Dazu Sonderformen, die der Parser **kennen muss**, weil sie real vorkommen:
Jahresspanne (`2015-2018 …`, `2013_2014 …`), offenes Ende (`2019+ …`,
`2020+ …`), Jahr als Suffix (`Beispiel_2019`), Datum mit Punkten und zwei Ziffern
(`… 10.10.21`), Monatsliste (`2021_08 & 10 …`), Jahr doppelt im Namen,
Ordner **ohne** jedes Jahr (`<Vorname>`, `<Bandname>`, `Spielkonsole`).

Ziel: **vorschlagen, nicht neu bauen.** Findet sich für einen Datums-Block ein
bestehender Event-Ordner derselben Kategorie, wird dieser als Ziel vorgeschlagen
— nur wenn es keinen gibt, entsteht ein neuer Name.

**Wichtig:** Das ist ein **Vorschlag**, keine Ausführung. Es wird in N6e
**nichts** in der pCloud geschrieben und nichts verschoben.

## Was gebaut wird

Neu: `tools/foto_sortierung/event_abgleich.py` (Nachbarmodul, lädt
`foto_kategorien.py` über das vorhandene `_modul_aus_pfad`-Muster).

### Reine Funktionen (kein Netz, kein Dateizugriff)

1. `ordner_datum_lesen(name) -> dict`
   Zerlegt einen vorhandenen Ordnernamen in Datums-Belege:
   `{"jahre": [int, ...], "spanne": bool, "offen_ab": bool, "monat": int|None,
   "tag": int|None, "rest": str}`.
   - Jahre: alle vierstelligen Zahlen 1900–2100 → aufsteigend, ohne Doppelung.
   - `spanne`: zwei Jahre mit `-` oder `_` verbunden (`2015-2018`, `2013_2014`).
   - `offen_ab`: Jahr mit `+` (`2019+` → ab 2019).
   - `monat`/`tag`: aus `JJJJ_MM`, `JJJJ-MM`, `JJJJ_MM_TT`, `JJJJ-MM-TT`,
     `TT.MM.JJ`/`TT.MM.JJJJ`. **Regel gegen Fehltreffer:** eine blanke Zahl
     1–12 gilt nur dann als Monat, wenn sie **direkt an ein Jahr anschließt**
     (Trennzeichen `_`, `-` oder `.`); sonst nicht — `Spiel A 2`, `Spiel B 3`,
     `9.Klasse`, `108` sind **keine** Monate. `tag` nur aus der Dreier-/Punktform.
   - `rest`: der Name ohne die erkannten Datums-Bestandteile, für den
     Wortvergleich. Auch der `rest` wird durch `pfad_saeubern` geschickt.

2. `datum_stufe(anlass, ordner) -> str`
   Vergleicht `(jahr, monat, tag)` eines Anlasses mit dem Gelesenen. Genau eine
   Stufe, Reihenfolge absteigend:
   - `"tag"` — Tag **und** Monat **und** Jahr gleich (stärkster Beleg),
   - `"monat"` — Monat **und** Jahr gleich,
   - `"jahr"` — Jahr enthalten, kein Monat im Namen,
   - `"spanne"` — Jahr liegt in einer Spanne / ab einem offenen Jahr,
   - `"ohne_jahr"` — Name trägt kein Jahr.
   Fehlt am Anlass der Monat oder Tag, werden nur die vorhandenen Teile
   verglichen (nie ein fehlender Wert als „passend" gezählt).

3. `kandidaten(anlass, unterordner) -> list[dict]`
   Alle Unterordner der **Ziel-Kategorie** des Anlasses, sortiert nach Stufe
   (`tag` → `monat` → `jahr` → `spanne`), innerhalb einer Stufe nach
   Wortüberlappung (`rest` gegen die Kachel-Kurzbeschreibungen des Anlasses),
   danach alphabetisch — **deterministisch**, damit zwei Läufe gleich sortieren.
   Rückgabe je Kandidat: `{"name", "stufe", "ueberlappung", "begruendung"}`
   (Begründung = Klartext, z. B. `"Jahr 2019 und Monat 11 gleich"`).

4. `vorschlag_fuer(anlass, unterordner, auch_schwach=False) -> dict|None`
   Der beste Kandidat als Vorschlag.
   **Harte Regeln (verschärft nach der Sichtprobe der Runde 1):**
   - `ohne_jahr` reicht **nie** für einen Vorschlag (ein Ordner `<Vorname>`
     ohne Jahr würde sonst jeden Anlass dieser Kategorie schlucken) → `None`.
   - **Nur `tag` und `monat` ergeben einen Vorschlag** (`STUFEN_VORSCHLAG`).
     Ein bloß gleiches Jahr ist **kein** Vorschlag: die Sichtprobe zeigte, dass
     damit in einer Kategorie mit mehreren Ordnern desselben Jahres reihenweise
     unpassende Ziele entstünden (z. B. ein Tier-Foto → `2019 <Anlass>`) —
     das ist ein falscher Beleg, kein schwacher.
   - `jahr` und `spanne` werden weiter **gezählt und als Hinweis genannt**
     (`schwacher_hinweis`), aber erst mit `auch_schwach=True` (CLI:
     `--auch-schwach`) zum Vorschlag — dann `sicher: false`.

5. `hinweis_text(anlass, unterordner) -> str` — eine Klartextzeile je Anlass
   (`<Datum> <Thema> → Vorschlag '<Ordner>' (Stufe, Beleg)` bzw.
   `→ kein Vorschlag, neuer Ordner`); rein, ohne DOM.

6. `trefferquote(anlaesse, kategorien) -> str` — reiner Zahlenbericht mit
   **festen Zeilen**: Anlässe gesamt · mit Vorschlag · davon `tag` / `monat` ·
   **schwacher Hinweis** (`jahr` / `spanne`, je einzeln) · ohne Vorschlag ·
   Kategorie fehlt im Bestand. Die schwachen Stufen stehen **nicht** in der
   Vorschlagszahl — sonst wäre die Trefferquote eine Behauptung.

7. `vorschlaege_schreiben(pfad, daten, trocken=True)` — schreibt die
   Vorschlagsliste **nur außerhalb des Repos** (dieselbe Schutzfunktion wie
   `foto_kategorien._pruefe_ziel_ausserhalb_repo`), atomar, nur bei echter
   Änderung (Idempotenz: zweiter Lauf schreibt nicht).

### Kommandozeile

`--zeigen` (Standard: nur anzeigen), `--stichprobe N` (N Beispiele mit
Begründung), `--kategorien-pfad`, `--zuordnung-pfad`, `--themen-pfad`,
`--vorschlaege-pfad` (Vorgabe außerhalb des Repos), `--schreiben`.
Ohne `--schreiben` wird **nichts** geschrieben. Kein pCloud-Aufruf in diesem
Werkzeug — es liest ausschließlich die lokalen Dateien
(`kategorien.json`, `kategorie_zuordnung.json`, `themen.jsonl`,
`themen/<Jahr>/<Anlass>.json`).

### Tests

`backend/tests/test_event_abgleich.py`, **ohne Netz, ohne pCloud**.
**Nur erfundene Beispielnamen** in Code, Tests und Doku — Sebastians echte
Ordnernamen dürfen **nicht** ins Repo (die liegen bewusst außerhalb).
Abzudecken sind mindestens: alle Muster der Tabelle oben, jede Stufe von
`datum_stufe`, die Fehltreffer-Regel (blanke Zahl ≠ Monat), `ohne_jahr` ohne
Vorschlag, Sortier-Stabilität, Idempotenz des Schreibens, Repo-Schreibschutz,
und dass das Modul **keine** pCloud-Funktion aufruft (Quelltext-Prüfung).

### Prüfbefehl (muss Exit 0 liefern)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
```

Ausgangsstand: **709 passed, Exit 0** (N6d). Erwartet: 709 + eigene Tests.

### Doku

`docs/changelog-2026-09-27-event-abgleich.md` mit dem neuen Stand; im selben
Commit wie der Code („code + docs").

## Runde 2 — Korrekturen nach Prüfer-Befund und eigener Sichtprobe

Der Prüfer (`openai/gpt-5.6-luna`) urteilte **NICHT BESTANDEN**; zwei Punkte,
beide hier nachgeprüft und bestätigt:

1. **Echte Ordnernamen im Repo.** Vier Namen aus Sebastians Ablage stehen
   wörtlich in den drei Dateien: zwei Spiele-Ordner und zwei Beispielordner mit
   Jahres-Suffix (einer davon war im Feinauftrag selbst als Muster genannt — der
   Fehler stammt also aus dem Auftrag, nicht nur aus der Ausführung).
   **Korrektur:** in allen drei Dateien durch erfundene Platzhalter ersetzen
   (z. B. `Beispiel_2019`, `Spiel A`, `Spiel B`), im Code wie in den Tests wie
   in der Doku. **Kein** echter Ordnername darf danach noch vorkommen —
   Prüfweg: alle Zeichenketten der drei Dateien gegen die Namen aus
   `kategorien.json` vergleichen (Vergleich selbstverständlich ohne Ausgabe der
   echten Namen).
2. **Falsche Zahl in der Doku.** Das Changelog sagt „109 von 113 Unterordnern
   erreichbar". Nachgerechnet und bestätigt: die Summe der Unterordner über die
   10 gebundenen Kategorien ist **112**; der 113. liegt in einer Kategorie ohne
   Bucket-Bindung. **Korrektur:** 112 eintragen, mit der Herleitung
   (10 gebundene Kategorien, Summe ihrer Unterordner = 112, eine Kategorie ohne
   Bindung).

Dazu die eigene Sichtprobe des Planers (18 Vorschläge angesehen): die Stufen
`jahr` und `spanne` erzeugten reihenweise unpassende Vorschläge. Deshalb die
verschärfte Regel in Punkt 4 oben — **nur `tag`/`monat` sind Vorschläge**, alles
andere ist ein Hinweis. Nach der Korrektur müssen die Zahlen des Laufs neu
gemessen und im Changelog **ersetzt** werden (nicht ergänzt).

## Verbote (gelten für den Ausführer)

- **Kein** git-Befehl (committen tut der Planer).
- **Kein** Schreibzugriff auf die pCloud, **kein** Verschieben, **kein** Löschen.
- **Keine** echten Ordnernamen in Repo-Dateien, Ausgaben oder Commit-Texten.
- **Kein** Schlüsselwert in Ausgaben oder Dateien (`.env` bleibt unangetastet).
- Pfade an native Werkzeuge immer als `C:/…`, **nie** als `/c/…`
  (MSYS-Pfade landen sonst unter `C:\c\…` — Lehre aus N6c).
