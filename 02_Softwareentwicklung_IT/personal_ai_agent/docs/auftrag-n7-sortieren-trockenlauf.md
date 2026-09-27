# Feinauftrag N7 — Trockenlauf des Sortierens (`foto_sortieren.py`)

> Planer: Hauptagent · Ausführer: Hermes-Subagent (`deepseek-v4.1-flash`) ·
> Prüfer: `openai/gpt-5.6-luna` (andere Modellfamilie).
> Grundlage: Plan `docs/plan-nachtlauf-2026-09-26.md`, Schritte N7 (Zeile 142)
> mit den Auflagen aus N6b (Rückfallordner) und N6d/N6e (Zielordner = Sebastians
> Kategorien, Event-Wahl über `event_abgleich.vorschlag_fuer`).

## Ziel in einem Satz

Ein Werkzeug, das aus dem fertigen Sortierschlüssel **einen Plan** baut — welche
Ordner unter `Agent/Fotos/<Jahr>/<Kategorie>/<Event>` neu entstehen und welche
Datei wohin zieht — und diesen Plan **ohne jede schreibende pCloud-Operation**
ausgibt. Das eigentliche Sortieren (N8) ist **nicht** Teil dieses Auftrags.

## Datenschutz (hart)

* Keine echten Ordnernamen, Orte, Bands, Personen aus dem Bestand in **Code,
  Tests, Doku** — Tests arbeiten ausschließlich mit **erfundenen** Namen
  (`BeispielKategorie`, `Beispiel-Event`).
* Der Plan und alle Ausgaben liegen **außerhalb** des Repos
  (`~/foto_sortierung/`). Ein Schreibversuch ins Repo wirft einen Fehler.
* Kein Schlüsselwert in Ausgaben oder Dateien.

## Vorgegebene Bausteine (nicht neu erfinden)

* `tools/foto_sortierung/foto_kategorien.py` — `ziel_pfad(jahr, kategorie, event)`,
  `bucket_fuer_thema(thema)`, `ziel_kategorie(bucket, zuordnung)`,
  `pfad_saeubern(name)`, `SONSTIGES`, `OHNE_NAME`, `ZIEL_BASIS`.
* `tools/foto_sortierung/event_abgleich.py` — `vorschlag_fuer(anlass, unterordner,
  auch_schwach=False)` → `{"name","stufe","sicher","ueberlappung","begruendung"}`,
  `unterordner_von(kategorie, bestand)`, `kategorie_fuer_anlass(anlass, zuordnung)`,
  `bestand_und_zuordnung()`, `anlass_datum(anlass)`, `anlass_thema(anlass)`,
  `OHNE_THEMA`.
* `tools/pcloud/pcloud_bewegungen.py` — **nur** für die trockenen Aufrufe
  `zielordner_finden_oder_bauen(...)`, `ordner_anlegen(...)`,
  `datei_verschieben(...)` mit `trocken=True`. **Kein** Schreibaufruf
  (`trocken=False`) in diesem Werkzeug.
* Importe wie in den Nachbarmodulen: die Module liegen unter
  `tools/foto_sortierung/`, die Tests unter `backend/tests/` und laden sie über
  `importlib` per Pfad (Muster aus `backend/tests/test_event_abgleich.py`).

## Eingaben (alle lesend)

1. `~/foto_sortierung/sortierschluessel_themen.csv` — Spalten:
   `jahr,monat,tag,datumquelle,thema,geraet,ordner,datei,motiv,doppelung,bytes,mb,thema_quelle`
   (`thema_quelle` = Anlass-ID, z. B. `2025-06-06_Anlass-03`; `ordner` =
   Quellordner in der Cloud, z. B. `P:/Automatic Upload/<Gerät>/DCIM/Camera`).
   **9.430 Datenzeilen**, 7 verschiedene Quellordner.
2. `~/foto_sortierung/kategorien.json` + `kategorie_zuordnung.json` über
   `bestand_und_zuordnung()`.
3. Nur lesend, nur mit `--mit-ids` (Standard an, wenn ein Schlüssel da ist):
   die 7 Quellordner per `service.liste(<folderid>)` auflisten, um
   Dateiname → `fileid` zuzuordnen. Ohne Schlüssel läuft der Plan mit
   `fileid: null` weiter (kein Abbruch).

## Fachliche Regeln (so umsetzen, nicht anders)

1. **Gruppieren:** Zeilen mit `thema_quelle` werden zu Anlässen gebündelt
   (Reihenfolge der Dateien bleibt die CSV-Reihenfolge; deterministisch).
   Zeilen **ohne** `thema_quelle` werden gezählt und übersprungen.
2. **Doppelungen:** Zeilen mit gefüllter Spalte `doppelung` werden **nicht**
   eingeplant (sie bleiben, wo sie sind — es wird nie gelöscht), sondern als
   `doppelung_uebersprungen` gezählt.
3. **Zielkategorie:** `kategorie_fuer_anlass(anlass, zuordnung)`. Ist das
   Ergebnis `None` **oder fehlt die Kategorie im Bestand**
   (`unterordner_von(kategorie, bestand) is None`), dann gilt:
   Kategorie = `ziel_kategorie(SONSTIGES, zuordnung)`; ist auch das `None`,
   Kategorie = `SONSTIGES`. Der Ordner wird dann als **neu** geplant.
4. **Rückfall für Anlässe ohne Thema** (Auflage aus N6b, Zeile 142):
   Anlass ohne Thema (`thema` leer/None) → Zielordner-Ebene **Event** =
   `event_abgleich.OHNE_THEMA`. **Niemals abbrechen.**
5. **Event-Name:**
   * Liefert `vorschlag_fuer(anlass, unterordner_von(kategorie, bestand))`
     einen Vorschlag mit `sicher: True`, wird **dessen Name** verwendet
     (bestehender Ordner wird wiederverwendet, nichts doppelt gebaut); der
     Vorschlag wird am Anlass als `event_quelle: "vorschlag"` mit `stufe`
     vermerkt.
   * Sonst: neuer Name = `pfad_saeubern(f"{datum} {thema}")`
     (Datum aus `anlass_datum`, Thema aus `anlass_thema`); ohne Thema nur das
     Datum, und das **darf nicht** leer sein → dann `OHNE_THEMA`.
   * **Kollision:** zwei verschiedene Anlässe desselben Jahres **derselben**
     Kategorie mit gleichem Namensvorschlag → deterministisch nach Anlass-ID
     sortiert behält der **erste** den einfachen Namen, jeder weitere bekommt
     den Anlass-Zusatz aus der ID in Klammern (`(02)` aus
     `2022-09-05_Anlass-02`). Gleiche Anlass-ID zweimal = ein Ordner.
6. **Zielpfad:** immer über `foto_kategorien.ziel_pfad(jahr, kategorie, event)`.
   Das Jahr kommt aus dem Anlass (INT-Form des Feldes `jahr`); fehlt es, wird
   das Jahr aus dem Datum gelesen, sonst zählt der Anlass als `ohne_jahr`
   (gezählt, übersprungen, nicht geraten).
7. **Ordner-Bedarf:** der ganze Pfad `Agent/Fotos/<Jahr>/<Kategorie>/<Event>`
   wird als Kette geplant — jeder Teil, der im Bestand **nicht** existiert, wird
   **einmal** als `createfolder` geplant (`art: "neu"`), vorhandene als
   `art: "vorhanden"`. Kein `createfolder` doppelt, auch nicht über Anlässe
   hinweg (Idempotenz).
8. **Züge:** eine Zeile je Datei:
   `{thema_quelle, jahr, kategorie, event, event_quelle, von_ordner, von_name,
   ziel_pfad, fileid}`. Sortiert nach (jahr, kategorie, event, von_name) —
   reproduzierbar.

## Ausgabe

* `--plan` (Standard `~/foto_sortierung/sortierplan.json`), **atomar**, nur
  außerhalb des Repos, nur mit `--schreiben` wirklich geschrieben (sonst nur
  Zahlen auf der Konsole).
* Inhalt: `{"stand", "trocken": true, "anlaesse": [...], "ordner": [...],
  "zuege": [...], "zusammenfassung": {...}}`.
  `zusammenfassung`: `zeilen`, `anlaesse`, `zuege`, `doppelung_uebersprungen`,
  `ohne_thema`, `ohne_jahr`, `ordner_neu`, `ordner_vorhanden`,
  `events_neu`, `events_wiederverwendet`, `je_jahr`, `je_kategorie` (nur Zahlen
  plus Kategorienamen — Kategorienamen sind Sebastians Ordnernamen, sie dürfen
  in Ausgaben, aber **nicht** ins Repo).
* Konsole: die Zahlenübersicht als Klartext (deutsch), z. B.
  „2.134 Anlässe · 9.430 Zeilen · 8.284 Züge · 1.279 Ordner neu · 39 Events
  wiederverwendet" plus `--beispiele N` (Standard 5) Stichproben-Züge und die
  Warnung, wenn `ohne_jahr` > 0 ist.
* **Kein** Manifest-Eintrag, **keine** schreibende pCloud-Operation: Der
  Trockenlauf bucht nichts. Ein Test prüft, dass `manifest.jsonl` nach einem
  Lauf byte-identisch ist.

## Tests (`backend/tests/test_foto_sortieren.py`, ≥ 40 Testfunktionen)

Alles offline, mit `tmp_path` und erfundenen Namen, kein Netz:
Gruppierung · Doppelungen · fehlende `thema_quelle` · Anlass ohne Thema
(Rückfall `Ohne-Thema`) · Kategorie fehlt im Bestand (Neubau) · `Sonstiges`
ungebunden · Vorschlag `sicher` wird wiederverwendet · Vorschlag nur `jahr`
(ohne `--auch-schwach`) wird **nicht** verwendet · Namenskollision → `(02)` ·
Jahr fehlt → `ohne_jahr` · Ordnerkette ohne Doppel-`createfolder` ·
Zielpfad über `ziel_pfad` (Reihenfolge `Agent/Fotos/Jahr/Kategorie/Event`) ·
Schreibschutz Repo · `--ohne-schreiben` schreibt nichts ·
Idempotenz (zweiter Lauf = gleicher Plan) · Quelltext-Test: keine
Löschfunktion (`deletefile`/`deletefolder`) und **kein** `trocken=False`.

## Prüfbefehl (Ausführer führt ihn selbst aus)

```bash
cd backend && .venv/Scripts/python -m pytest tests/ -q
```

Baseline vorher: **760 passed, Exit 0**. Erwartet danach: **≥ 800 passed, Exit 0**.

## Verboten

* `git`-Befehle (committet der Planer).
* Echte Namen aus dem Bestand in Repo-Dateien.
* Reale Schreiboperationen gegen die pCloud, Manifest-Einträge, Download von
  Originalen (Vorschaubilder sind hier gar nicht nötig).
* Änderungen an `sortierschluessel_themen.csv`, `kategorien.json`,
  `kategorie_zuordnung.json`, `themen.jsonl` (nur lesen).
* MSYS-Pfade (`/c/...`) an native Werkzeuge — immer `C:/...`.
