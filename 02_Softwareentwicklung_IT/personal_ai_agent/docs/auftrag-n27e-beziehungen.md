# Feinauftrag N27e — Ableitung „wer war mit wem wo" (Verknüpfungsschicht N27, Schritt 5 von 5)

> **Rolle:** Auftrag des Planers (Hauptkontext) an **einen** Ausführer-Subagenten.
> Prüfer ist ein **frischer** Kontext mit **anderer Modellfamilie**.
> **Keine `git`-Befehle** im Auftrag. Nur Code + Tests + Doku schreiben.

## Ziel

Ein Werkzeug, das aus den **bereits vorhandenen** Verknüpfungsdaten *belegbare*
Aussagen der Form „wer war mit wem wo" ableitet — **jede Aussage mit Datum und
Quelle**, **nie geraten**. Das Werkzeug **nament niemanden**: Namen erscheinen
ausschließlich dort, wo sie in der Bestätigungsdatei des Nutzers stehen
(`~/foto_sortierung/personen_bestaetigt.json`, aus N27d — derzeit **nicht
vorhanden**, also **0** Namen). Unbestätigte Personen bleiben bei ihrer
Kennung `Person_00x` **mit `name: null`**.

## Neue Dateien (genau diese drei)

1. `tools/foto_sortierung/beziehungen_ableiten.py` — Werkzeug (Ziel ~600–900 Zeilen, deutscher Modulkopf).
2. `backend/tests/test_beziehungen_ableiten.py` — Offline-Tests (Ziel ~700–1.000 Zeilen, ≥ 90 Testfunktionen).
3. `docs/changelog-2026-09-29-n27e-beziehungen.md` — Changelog (nur Zahlen, **keine** echten Namen/Orte).

## Eingaben (nur lesend, feste Standardpfade unter `~/foto_sortierung/`)

| Datei | Zeilen (gemessen) | Inhalt |
|---|---|---|
| `personen_andockung.jsonl` (N27d) | **5** | je Anlass: `anlass_id`, `datum`, `kennung`, `personen[]` mit `kennung`, `name`, `bestaetigt`, `bilder`, `gesichter`, `quellen` |
| `chat_andockung.jsonl` (N27b) | **2.127** | je Anlass: `anlass_id`, `datum`, `chats[]` mit `chat_name`, `art` (`einzel`/`gruppe`), `nachrichten`, `medien`, `beteiligte[]` mit `name`, `nachrichten` |
| `ereignisse.jsonl` (N27a) | **2.127** | je Anlass: `anlass_id`, `datum`, `kennung`, `thema`, `kategorie`, `ziel_ordner`, `dateien` |
| `personen_bestaetigt.json` (Nutzereingabe, **darf fehlen**) | fehlt | `{"bestaetigt": {"Person_00x": "Name"}}` |

**Wiederverwenden, nicht nachbauen:** `personen_andocken.bestaetigung_lesen`
und die JSONL-Leser müssen nicht kopiert werden — nutze die Nachbarmodule
(`personen_andocken`, `ereignisse_bauen`) per Import, wenn das ohne Seiteneffekt
geht; sonst eigene kleine Leser mit **defekte Zeilen werden gezählt**, nie
geworfen. Der CLI-Zweitname `haupt = main` (wie in `personen_andocken.py`) muss
gesetzt sein, weil das Nachbarmodul `main` heißt.

## Drei Aussage-Arten (getrennt halten, nie vermischen)

1. **`fotos`** — je Anlass mit **≥ 2** verschiedenen Personen-Kennungen:
   je Kennungs-Paar **eine** Aussage. `stuetze: "fotos"`, Beleg = Summen aus
   `bilder`/`gesichter` beider Personen.
2. **`gemeinsam_im_chat`** — je Chat-Andockung (ein Chat an einem Tag) mit
   **≥ 2** verschiedenen **benannten** Kontakten: je Namens-Paar **eine**
   Aussage. `stuetze: "chat"`, Beleg = `nachrichten` beider Beteiligter,
   `chat_name`, `art` des Chats. `name == "unbekannt"` (oder leer) zählt
   **nicht** als Kontakt.
3. **`fotos_und_chat`** — je Anlass mit **≥ 1** Foto-Person **und** **≥ 1**
   benanntem Chat-Kontakt: je Paar (Person × Kontakt) **eine** Aussage.
   `stuetze: "fotos+chat"`, Belege aus **beiden** Quellen.

**Pflichtfelder je Aussagezeile** (Reihenfolge stabil, `sort_keys=True`):
`art` (= `"beziehung"`), `unterart` (eine der drei oben), `datum` (JJJJ-MM-TT),
`anlass_id`, `ereignis_kennung` (aus `ereignisse.jsonl`, falls vorhanden),
`thema`, `kategorie`, `ziel_ordner`, `personen` (Liste mit `kennung`, `name`
(**nur** bestätigt, sonst `null`), `bestaetigt`, `bilder`, `gesichter` — bei
Chat-Kontakten ohne `kennung`), `beleg` (Zahlen), `quellen` (Datei + Zeile
bzw. Anlass-Kennung, z. B. `{"andockung": "personen_andockung.jsonl:3",
"chat": "chat_andockung.jsonl:1180"}`), `hinweis` (deutscher Satz, was die
Aussage **nicht** belegt), `stand`.

**Ehrliche Abgrenzung (Pflicht, im `hinweis`):** „im selben Chat" ist
**Mitgliedschaft**, **kein** Beleg für körperliche Anwesenheit; „auf Fotos am
selben Anlass" ist **Bildbeleg**, **kein** Beleg für eine Beziehung. Unbestätigte
Kennungen sind **keine** Namen — sie dürfen **nie** aus Kandidatenlisten
(`personen_vorschlaege.json`) übernommen werden. Zusatztest: die Datei
`personen_vorschlaege.json` darf im Quelltext **nicht** vorkommen.

## Zweite Ausgabe

`~/foto_sortierung/beziehungen.json` — Übersicht: `art`, `stand`, `anzahl`
je Unterart, `anzahl_personen_kennungen`, `anzahl_namen_bestaetigt`,
`anzahl_kontakte`, `datum_von`, `datum_bis`, `quellen`, `hinweis`.

## Kommandozeile

`--ereignisse`, `--andockung`, `--chat-andockung`, `--bestaetigung`,
`--ausgabe` (JSONL), `--ausgabe-uebersicht` (JSON), `--stand`,
`--datum JJJJ-MM-TT` (nur Aussagen dieses Tages; ungültiges Datum → deutsche
Meldung + Exit 2), `--nur-bestaetigt` (nur Unterart `fotos`/`fotos_und_chat`
mit **mindestens einer bestätigten** Person), `--trocken` (**Standard**),
`--schreiben`.

**Schutz (wie in N27b/N27d, mit Tests):**

* Ausgabeziel **im Repo** → deutsche Meldung auf `stderr`, **Exit 2**, keine Datei (auch im Trockenlauf).
* Schreiben **atomar** (`.tmp` + `os.replace`), keine `.tmp`-Reste.
* Fehlende Eingabedatei → `stderr` + Exit 2.
* **Keine** Lösch-/Verschiebe-/Netz-/pCloud-/Download-Funktion (Test prüft den Quelltext).
* Kein Nachrichtentext wird gelesen; keine Nummern-Masken in der Ausgabe.
* Deterministisch: gleiche Eingaben + fester `--stand` → **byte-gleiche** Ausgabe.

## Gemessene Sollwerte (Planer-Vormessung, 29.09.2026, echte Dateien — Zeile für Zeile zu erreichen)

* `personen_andockung.jsonl`: **5** Zeilen · **12** Personen-Kennungen · **0** bestätigt.
* Unterart `fotos`: **5** Anlässe mit ≥ 1 Person (davon **2** mit genau einer
  Person → **keine** Paar-Aussage) → **23** Personen-Paare.
* Unterart `gemeinsam_im_chat`: **2.101** Anlässe mit ≥ 1 Chat · **45.040**
  Chat-Andockungen · **23.122** mit ≥ 1 benannten Kontakt · **20.543** mit genau
  einem → **14.902** Kontakt-Paare.
* Unterart `fotos_und_chat`: **5** Anlässe · **126** Paare.
* **Erwartete Aussagezeilen gesamt: 23 + 14.902 + 126 = 15.051.**
* Namen in der Ausgabe: **0** (Bestätigungsdatei fehlt). Mit einer
  **Probe-Bestätigung** (erfundener Name, z. B. `Person_001` → `Beispielname`
  in einer **temporären** Datei außerhalb des Repos): Name erscheint **genau**
  in den Aussagen, an denen `Person_001` beteiligt ist — nicht mehr, nicht weniger.

**Abweichungen sind ein Befund:** weicht eine Zahl ab, nicht stillschweigend
anpassen, sondern im Changelog **mit Ursache** dokumentieren und im Ergebnis
melden.

## Regeln (bindend)

* Tests **vollständig offline** (`tmp_path`, erfundene Beispieldaten, kein Netz,
  keine echten Personen-/Ortsnamen, keine echten Dateikennungen).
* **Nie löschen** — das Werkzeug kennt keine Löschfunktion.
* Doku **codegenau**: keine Zahl behaupten, die nicht gemessen wurde.
* Eigener Testlauf vor der Meldung: `cd backend && .venv/Scripts/python -m pytest tests/ -q` → Exit 0.
* In der Meldung: Zeilenzahlen, Testfunktions-Zahl, Live-Trockenlauf-Zahlen,
  zwei Schreibläufe byte-gleich, Repo-Ziel Exit 2.
