# Feinauftrag N27d — Personen-Andockung (Verknüpfungsschicht N27, Schritt 4 von 5)

> **Planer:** Hauptkontext (Hermes). **Ausführer:** Hermes-Subagent
> (`deepseek-v4.1-flash`) — Codex ist gesperrt (live geprüft: „You've hit your
> usage limit … try again at Oct 15th, 2026"). **Prüfer:** `openai/gpt-5.6-luna`
> (andere Modellfamilie).
> **Sprache:** Code, Kommentare und Doku auf **Deutsch** (Workspace-Regel:
> Skripte englisch — Ausnahme gilt hier für die Foto-Werkzeuge, die durchgehend
> deutsche Kommentare tragen; die bestehenden Nachbarmodule sind deutsch).

## Warum dieser Schritt

Die Verknüpfungsschicht N27 hat drei Andockungen: Ereignis-Knoten (N27a),
Chats (N27b), Kalender (N27c). Es fehlt die **Personen-Andockung**: welcher
Anlass zeigt welche Gesichts-Cluster, und welcher **Name** passt dazu. Der Plan
sagt wörtlich: „Gesichts-Cluster (neu gerechnet) + im Chat genannte Namen +
**Bestätigung des Nutzers** → die Kennung `Person_00x` bekommt einen Namen."

**Kernregel dieses Schritts (nicht verhandelbar):** Das Werkzeug **schlägt vor**,
es **benennt nicht**. Ein Name erscheint nur, wenn er in der
Bestätigungsdatei steht, die **der Nutzer** pflegt. Ein Vorschlag darf sich
niemals selbst bestätigen.

## Was schon steht (nicht neu bauen)

| Baustein | Datei / Ablage | Was es liefert |
|---|---|---|
| Ereignis-Knoten | `~/foto_sortierung/ereignisse.jsonl` (2.127 Zeilen) | `anlass_id`, `kennung` (`E-…`), `datum`, `datei_kennungen` (Liste) |
| Chat-Andockung | `~/foto_sortierung/chat_andockung.jsonl` (2.127 Zeilen) | je Anlass `chats[]` mit `chat_name`, `beteiligte[]`, `art`, `nachrichten` — **kein** Nachrichtentext |
| Gesichts-Clustering | `tools/foto_sortierung/personen_cluster.py` | `lauf_rechnen(bilder, katalog, altbestand)` → `eintraege`, `gruppen`, `kennungen` (mit `indizes`), `bericht`; `altbestand_lesen_datei`, `pruefe_ausserhalb_repo` |
| Vektoren | `~/foto_sortierung/personen_vektoren_n9e.jsonl` (92) und `…_burst.jsonl` (59) | je Zeile `{bild_id, breite, hoehe, gesichter:[{bbox, score, landm, embedding[128]}]}` |
| Kennungs-Altbestand | `~/foto_sortierung/personen_n9f/kennungen.json` (12 Kennungen) | stabile `Person_001…` samt Mittelpunkt |

**Nicht** in diesem Schritt: Gesichter über alle 9.430 Fotos rechnen (das ist ein
eigener Massenlauf — 192 Bilder kosteten 1.086 s, hochgerechnet ~15 h; braucht
eigene Entscheidung und eigene Messung). Dieser Schritt baut das
**Zusammenführen** und misst es auf den **vorhandenen** Vektoren (151 Zeilen).

## Was NICHT passieren darf (jedes Verbot mit Prüfung und Test)

1. **Kein Nachrichtentext.** Gelesen und ausgegeben werden nur `chat_name` und
   `beteiligte` aus `chat_andockung.jsonl` — nie `message`, nie `nachrichten_kennungen`.
2. **Keine Rufnummern.** Ausgabe enthält keinen Nummern-Maskentext (Sternchen-Muster
   in der Form, die das Telefonbuch liefert) und
   keine Ziffernfolge ≥ 7 Zeichen außer Kennungen/Zeitstempeln.
3. **Kein Bild, kein Netz.** Kein `cv2`, kein `requests`/`urllib`, kein pCloud-Aufruf,
   kein Datei-Download. Nur Standardbibliothek + `numpy` (über `personen_cluster`).
4. **Kein Schreiben ins Repo.** Ausgabepfad im Repo ⇒ deutsche Meldung + `SystemExit(2)`.
   Verwendung: `personen_cluster.pruefe_ausserhalb_repo`.
5. **Kein Löschen.** Einzige Entfernung im Quelltext: `os.remove(temp)` auf die
   **eigene** temp-Datei beim atomaren Schreiben.
6. **Keine Kennungs-Verwaltung.** Das Werkzeug schreibt **keinen** Altbestand
   (`kennungen_schreiben` wird nicht aufgerufen) — sonst verschieben sich Kennungen.

## Was gebaut wird

**Werkzeug:** `tools/foto_sortierung/personen_andocken.py` (Richtwert 600–850 Zeilen)
**Tests:** `backend/tests/test_personen_andockung.py` (Richtwert 60–90 Testfunktionen, alles offline, `tmp_path`, erfundene Daten)

Eingaben (überschreibbar per CLI), alle **nur lesend**, alle außerhalb des Repos:

```
EREIGNISSE      = ~/foto_sortierung/ereignisse.jsonl
VEKTOREN        = [~/foto_sortierung/personen_vektoren_n9e.jsonl,
                   ~/foto_sortierung/personen_vektoren_n9e_burst.jsonl]
ALT_KENNUNGEN   = ~/foto_sortierung/personen_n9f/kennungen.json
CHAT_ANDOCKUNG  = ~/foto_sortierung/chat_andockung.jsonl
BESTAETIGUNG    = ~/foto_sortierung/personen_bestaetigt.json   (darf fehlen)
AUSGABE_KNOTEN  = ~/foto_sortierung/personen_andockung.jsonl
AUSGABE_VORSCHL = ~/foto_sortierung/personen_vorschlaege.json
```

### Öffentliche Funktionen (Namen wörtlich, je eine Aufgabe, rein)

| Funktion | Aufgabe |
|---|---|
| `vektoren_lesen(pfade) -> dict` | JSONL-Zeilen lesen; `{"zeilen": [...], "defekt": n}` — kaputte Zeile zählt, bricht nichts ab |
| `ereignisse_lesen(pfad) -> list[dict]` | nur Zeilen mit `art == "ereignis"`; defekte Zeilen zählen |
| `ereignis_index(ereignisse) -> dict` | `str(datei_kennung) -> ereignis` (erste Zuordnung gewinnt, Kollisionen zählen) |
| `personen_je_bild(lauf) -> dict` | aus `lauf["kennungen"]` + `lauf["eintraege"]`: `Person_00x -> [bild_id, …]`, sortiert |
| `andocken(personen_bilder, ereignis_index) -> list[dict]` | je **Anlass** mit ≥ 1 Person: `{anlass_id, kennung, datum, personen: [{kennung, bilder, gesichter}], quellen}` — sortiert nach `anlass_id`; Bilder ohne Anlass-Zuordnung werden **gezählt** (`ohne_anlass`), nie stillschweigend verworfen |
| `kandidaten_je_person(andockung, chat_knoten) -> dict` | `Person_00x -> {name: anzahl}` aus den Chats **ihrer** Anlässe: Name = **`chat_name`** des Chats; die `beteiligte` werden **nur als Rückfall** gelesen, wenn `chat_name` leer ist (Nachtrag des Planers, siehe unten). Namen mit Zählung, absteigend, alphabetisch als Zweitschlüssel |
| `vorschlaege_bauen(andockung, kandidaten, namen_je_person=5) -> list[dict]` | je Person: `kennung`, `anzahl_anlaesse`, `anzahl_bilder`, `anzahl_gesichter`, `von`, `bis`, `namen` (Top-N), `vorschlag` (stärkster Name oder `None`), `bestaetigt: false`, `bestaetigter_name: null` |
| `bestaetigung_lesen(pfad) -> dict` | toleranter Leser; fehlende Datei ⇒ `{}`; nur Schlüssel im Muster `Person_\d{3}` zählen, fremde Schlüssel werden gezählt und gemeldet |
| `bestaetigung_anwenden(vorschlaege, bestaetigung) -> list[dict]` | setzt `bestaetigt`/`bestaetigter_name` **nur** aus der Datei; `vorschlag` bleibt unverändert (Vorschlag ≠ Name) |
| `knotenzeilen_bauen(andockung, bestaetigung, stand) -> list[dict]` | Ausgabezeilen mit Schema unten; ohne Bestätigung **kein** `name` |
| `schreiben(pfad, inhalt)` | atomar (temp + `os.replace`), Repo-Pfad ⇒ Exit 2, keine `.tmp`-Reste |
| `bericht_bauen(zahlen) -> str` | deutscher Bericht (mehrzeilig, Zahlen wie unten) |

### Ausgabeschema (fest, wird geprüft)

`personen_andockung.jsonl` — eine Zeile je Anlass mit Personen:

```json
{"art": "personen_andockung", "anlass_id": "2014-11-22_Beispiel-01",
 "kennung": "E-2014-11-22_Beispiel-01", "datum": "2014-11-22",
 "personen": [{"kennung": "Person_001", "bilder": 3, "gesichter": 4,
               "bestaetigt": false, "name": null}],
 "quellen": {"personen": "personen_vektoren_*.jsonl+personen_cluster.lauf_rechnen",
             "anlass": "ereignisse.jsonl"},
 "stand": "2026-09-29T02:00:00+02:00"}
```

`personen_vorschlaege.json` — Übersicht für das Handy (die Bestätigung trägt der Nutzer dort ein):

```json
{"art": "personen_vorschlaege", "stand": "…",
 "anzahl_personen": 12, "anzahl_bestaetigt": 0,
 "hinweis": "Namen nur nach Bestaetigung; Vorschlaege sind Vorschlaege.",
 "personen": [{"kennung": "Person_001", "anzahl_anlaesse": 2, "anzahl_bilder": 5,
               "anzahl_gesichter": 6, "von": "2019-04-06", "bis": "2020-08-15",
               "namen": [{"name": "Beispielname", "anzahl": 7}],
               "vorschlag": "Beispielname", "bestaetigt": false,
               "bestaetigter_name": null}]}
```

**Beispiele sind erfunden** (`Beispiel-01`, `Beispielname`) — keine echten
Anlass-IDs, Orte, Kennungen oder Personen aus dem Bestand in Code, Tests oder Doku.

### Kommandozeile

```
--trocken            (Standard: rechnet und berichtet, schreibt nichts)
--schreiben          (nötig zum Schreiben; beide Ausgabedateien)
--vektoren PFAD      (wiederholbar; Standard: die zwei Dateien oben)
--ereignisse/--chat-andockung/--alt-kennungen/--bestaetigung PFAD
--namen-je-person N  (Standard 5)
--stand ZEITSTEMPEL  (für byte-gleiche Wiederholung)
```

### Bestätigungsdatei (der Nutzer pflegt sie, z. B. am Handy/PC)

```json
{"hinweis": "Nur hier eingetragene Namen werden verwendet.",
 "bestaetigt": {"Person_001": "Beispielname"}}
```

Fehlt die Datei oder ist ein Eintrag leer ⇒ die Person bleibt **unbenannt**.

## Sollwerte (Vormessung des Planers, nur lesend, aus derselben Quelle)

Diese Zahlen hat der Planer **selbst** gemessen (151 Vektorzeilen aus beiden
Dateien, Altbestand aus `personen_n9f/kennungen.json`, Produktionsverfahren
„vollstaendig", Schwelle 0,45). Der Ausführer **wiederholt** sie und meldet jede
Abweichung ausdrücklich (Abweichung = Befund, kein Schönheitsfehler):

| Größe | Sollwert |
|---|---|
| Vektorzeilen gelesen | **151** (92 + 59) |
| Bilder-Arten | `gruppe 41 · leer 64 · menge 11 · unklar 35` |
| Personen (Gruppen) | **12** — davon **2 neu**, **10 wiederverwendet** |
| Gruppengrößen | `11, 10, 10, 5, 4, 4, 4, 4, 4, 3, 3, 3` |
| Personen ohne Anlass-Zuordnung | **0** |
| Anlässe mit ≥ 1 Person | **5** |
| Personen mit Kandidatennamen | **12 von 12** |
| verschiedene Kandidatennamen gesamt | **34** |
| Kandidaten je Person (größte zuerst) | `24, 19, 12, 12, 10, 10, 10, 10, 8, 8, 8, 8` |

**Offengelegter Messfehler des Planers (gehört zur Wahrheit dieses Schritts):** die
Vormessung zählte die `beteiligte` mit, filterte sie aber auf **Zeichenketten** — in
`chat_andockung.jsonl` sind `beteiligte` jedoch **Objekte** (`{"name": …, "nummer_maske": …}`).
Damit floss faktisch **nur `chat_name`** in die Zahl 34 ein. Nachgemessen (gleiche fünf
Anlässe): mit `chat_name` **und** `beteiligte` sind es **44** verschiedene Namen
(= 34 + 10, die nur in `beteiligte` stehen). Die Sollwerte beschreiben also die
`chat_name`-Fassung. Der Ausführer hat das erkannt und gemeldet — genau dafür steht die
Regel „Abweichung ist ein Befund" im Auftrag.

**Entscheidung des Planers (kein Rückfragen im Nachtlauf):** ausgeliefert wird
`chat_name` als Namensquelle, `beteiligte` nur als Rückfall. Grund: bei Gruppen ist
`chat_name` der **Gruppenname** und die `beteiligte` sind viele Personen — als
Kandidat wäre beides gemischt (Gruppenname als „Person"). Die reichere Regel
(**Einzelchat → `chat_name`, Gruppe → Teilnehmer**) ist der Folgekandidat und wird
hier nur benannt, nicht gebaut (ein Schritt pro Runde).

## Prüfkriterien (der Schritt gilt erst als fertig, wenn alle erfüllt sind)

1. **Prüfbefehl grün:** `cd backend && .venv/Scripts/python -m pytest tests/ -q`
   → Exit 0. Die **Baseline vor dem Schritt** wird gemessen und im Changelog
   genannt (`2.414` war der Stand von N27c; durch fremde Parallelarbeit kann die
   Zahl größer sein — die echte Baseline frisch zählen, nicht abschreiben).
2. **Live-Trockenlauf** gegen die echten Dateien nennt die Sollwerte oben
   (Zeile für Zeile, ohne Beschönigung; Abweichungen benennen).
3. **Zwei `--schreiben`-Läufe** mit festem `--stand` in einen **frischen** Ordner
   außerhalb des Repos sind **byte-gleich** (Größe + sha256), keine `.tmp`-Reste.
4. **Repo-Ziel** mit `--schreiben` ⇒ **Exit 2**, keine Datei entsteht.
5. **Ohne Bestätigungsdatei enthält die Ausgabe 0 Namen** (Test + Live-Lauf mit
   leerer/fehlender Datei); mit einer Probe-Bestätigung (erfundener Name) trägt
   **genau diese** Person einen Namen, alle anderen nicht.
6. **Eingaben unverändert:** Größe + mtime + sha256 von `ereignisse.jsonl`,
   `chat_andockung.jsonl`, beiden Vektordateien und `kennungen.json` vorher/nachher
   gleich; `manifest.jsonl` **existiert nicht** (nichts gebucht).
7. **Datenschutz-Scan** der neuen/geänderten Repo-Dateien: 0 Treffer für
   `@gmail`, den Eigner-Namen, Telefonnummern-Masken (Sternchen-Muster), Orte/Ordensnamen aus
   `kategorien.json`; nur erfundene Beispiele.

## Doku (gehört zum selben Commit, „code + docs")

- **Changelog** `docs/changelog-2026-09-29-n27d-personen-andockung.md`:
  Was gebaut wurde, die Sollwerte mit Ist-Werten, Prüfbefehl mit Zahl,
  Bestätigungs-Weg für den Nutzer, **offen:** Massenlauf der Gesichter über alle
  9.430 Fotos (mit der gemessenen Hochrechnung), Namensnennung im Chat-Text
  (dieser Schritt nutzt Chat-**Namen** und Beteiligte, nicht den Text).
- **Plan** `docs/plan-nachtlauf-2026-09-26.md`: neuen Schritt **N27d** in die
  Tabelle eintragen (Stand ✅ mit Zahlen) **und** einen Journal-Eintrag anhängen —
  **ans Datei-Ende** (ein zweiter Schreiber kann parallel arbeiten; die
  Schritt-Tabelle nicht per Anker mitten im Lauf umschreiben, sondern die eigene
  Zeile neu einfügen).
- **`CLAUDE.md`** (Projekt): eine Protokollzeile (Datum, Änderung, Begründung,
  geprüft von).

## Arbeitsweise für den Ausführer

- **Keine git-Befehle** (committen/pushen macht der Planer).
- Erst lesen, was schon da ist: `personen_cluster.py` (Funktionen und
  Rückgabeformen), `chat_andocken.py` (Stil, Trockenlauf, Repo-Schutz,
  `pruefe_ausserhalb_repo`), `ereignisse_bauen.py`, `kalender_andocken.py`,
  `backend/tests/test_kalender_andockung.py` (Teststil).
- Nur **reiner Code** an den Auftrag — der Auftrag selbst enthält keine
  Bestandsdaten.
- Keine Schwellen ändern (`CLUSTER_SCHWELLE`, `ANTEIL_MIN`, `MENGE_ANZAHL`,
  `CLUSTER_VERFAHREN` bleiben unangetastet) und keine bestehende Datei
  umbauen — nur **neu** anlegen.
- Am Ende melden: Zeilenzahl der beiden neuen Dateien, Anzahl Testfunktionen,
  Prüfbefehl-Ausgabe mit Exit-Code, die Live-Zahlen (Soll/Ist), und jede
  Abweichung.
