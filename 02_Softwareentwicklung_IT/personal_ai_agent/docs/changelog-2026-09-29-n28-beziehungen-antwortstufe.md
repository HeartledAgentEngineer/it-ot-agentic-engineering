# Changelog — N28: Antwortstufe „wer war mit wem wo" aus `beziehungen.jsonl`

**Datum:** 29.09.2026 · **Auftrag:** `docs/auftrag-n28-beziehungen-antwortstufe.md`
**Vorgänger:** N27e (`beziehungen_ableiten.py`, abgenommen) — dieser Schritt
baut **nur auf** dessen Ausgabedatei auf und ändert daran nichts.

## Was entstanden ist

Die kanonische Datei `~/foto_sortierung/beziehungen.jsonl` (15.051 belegbare
Aussagen) war bisher **nur auf dem PC** und wurde von niemandem gelesen. Jetzt
ist sie **abfragbar** — als Dienst + Endpunkt und als Chat-Werkzeug.

### Neu

| Datei | Zeilen | Inhalt |
|---|---:|---|
| `backend/app/services/beziehungen_service.py` | 622 | Dienst: `datum_erkennen`, `aussagen_fuer_datum`, `beziehungen_laden`, `text_antwort`, `status_block` — rein lesend, kein Netz, keine Bilder, **keine Schreibfunktion**, **nie ein Wurf** |
| `backend/app/router/beziehungen.py` | 136 | `GET /api/beziehungen/uebersicht` und `GET /api/beziehungen/tag?datum=…&limit=…`, immer HTTP 200, immer dieselben Felder |
| `backend/tests/test_beziehungen_service.py` | 761 | **76 Testfunktionen**, komplett offline, erfundene Daten in `tmp_path` |

### Geändert

| Datei | Zeilen (neu gesamt) | Änderung |
|---|---:|---|
| `backend/app/router/chat.py` | 2.174 | Werkzeug `_beziehungen_tool` (Definition Zeile 1.235, nach `_fotos_uebersicht_tool`), an **beiden** Stellen eingehängt (Aufruf Zeile 389 = `/chat`, Zeile 1925 = `/stream`), jeweils **nach** dem Foto-Werkzeug (384 / 1921) hinter `if not werkzeug_notiz:` / `if not s_werkzeug_text:` |
| `backend/app/router/selbsttest.py` | 684 | Block `_beziehungen_info()` nach dem Muster von `_fotos_info()`, Feld `beziehungen` in der Antwortstruktur und in der Bau-Tabelle |
| `backend/app/main.py` | 350 | Import + `app.include_router(beziehungen.router, dependencies=[Depends(auth.require_api_key)])` mit deutschem Kommentarblock |
| `backend/tests/test_selbsttest.py` | — | `PFLICHT_FELDER` um `"beziehungen"` erweitert (die Prüfung vergleicht die **exakte** Schlüsselmenge und musste um den neuen Block ergänzt werden) |

Kein Umbau von `app.js`, kein Cache-Bump. Keine Änderung an
`docs/plan-nachtlauf-2026-09-26.md`, keine an `CLAUDE.md`, **keine git-Befehle**.

## Prüfbefehl

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
```

* **vorher** (Baseline, unveränderter Stand): `2789 passed, 3 warnings` — Exit **0**
* **nachher** (frisch nach der letzten Änderung): `2894 passed, 3 warnings` — Exit **0**

Das neue Testmodul stellt **76** Testfunktionen; die Sammlung umfasst jetzt
2.894 Tests. (Anmerkung: die Differenz 2.894 − 2.789 = 105 ist größer als die
76 neuen Funktionen. Isoliert nachgeprüft: Auch **ohne** die beiden neuen
Quelldateien und **ohne** das neue Testmodul sammelt die Suite 2.818 Tests in
den übrigen Dateien — die 29 übrigen Tests sind also **nicht** durch N28
entstanden, sondern waren beim Baseline-Lauf nicht mitgezählt.)

Beim ersten Durchlauf schlug einmal
`tests/test_ereignisse_bauen.py::test_haupt_schreiben_ist_byte_gleich_wiederholbar`
fehl. Ursache ist **kein** N28-Zusammenhang, sondern eine vorhandene
Zeitgrenzen-Flakiness: das Werkzeug `ereignisse_bauen.py` schreibt `stand` aus
`datetime.now().isoformat(timespec="seconds")`; fallen zwei Schreibvorgänge auf
zwei Sekunden, unterscheidet sich der Hash. Der zweite Durchlauf war grün; der
Test und das Werkzeug sind **nicht** Teil dieses Auftrags und wurden nicht
angefasst.

## Live-Beleg am echten Bestand (nur lesend)

Ausgabe in `C:/Users/sebas/foto_sortierung/n28_belege.txt` (außerhalb des Repos;
es werden **nur Zahlen/Daten/Ja-Nein** ausgegeben, keine Namen).

* Datei-Kennzahlen: **15.051** Zeilen/Aussagen, **645** verschiedene Tage,
  **2016-05-04** bis **2025-08-16**, **12** Personen-Kennungen,
  **0** bestätigte Namen, **253** Kontakte.
* Verteilung: `fotos 23` · `gemeinsam_im_chat 14.902` · `fotos_und_chat 126`.
* `GET /api/beziehungen/tag?datum=2022-08-21` → **61** Aussagen
  (**fotos 10 · gemeinsam_im_chat 6 · fotos_und_chat 45**),
  `gueltig: true`, `gekuerzt: true`, 50 gezeigt.
* `datum=2019-12-27` → **0** Aussagen, `gueltig: true`, `error: null`
  (ehrlich, kein Fehler — der plan-interne Testtag trägt keine Andockung).
* `datum=2025-06-06` → **685** Aussagen (gemeinsam_im_chat 685).
* `datum=31.02.2020` → `gueltig: false` mit deutschem `error`-Text.
* `text_antwort("2022-08-21")`: 1.223 Zeichen (≤ 2.000), enthält Datum,
  Zahlen, den `hinweis` **wörtlich** und den Schlusssatz zur Abgrenzung;
  `text_antwort("2019-12-27")`: 342 Zeichen, enthält den Satz zur fehlenden
  Andockung.
* `datum_erkennen`: `27.12.2019`/`27.12.19`/`2019-12-27`/`27. Dezember 2019` →
  `2019-12-27`; `am 3.1.2022` → `2022-01-03`; `märz`/`Maerz`/`maerz` werden
  akzeptiert; `31.02.2020`, `99.99.9999`, `2019` (Jahr allein) und Text ohne
  Datum → `None`.

## Unverändert (Prüfregel)

`beziehungen.jsonl` (12.601.994 B) und `beziehungen.json` (715 B) wurden
**nur gelesen**. sha256 vor **und** nach allen Läufen identisch:

* `beziehungen.jsonl` — `e0d0dc402abffe32373940735e888216207413e6db0d07a8b78bfa275f3cffe0`
* `beziehungen.json` — `9ec70dc2c496ead810acc3771627e31858f0e1ec62d6bb08db59c509e05080b8`

Kein `deletefile`/`deletefolder`/`rmtree` (per Quelltext-Test abgesichert),
kein Netz, keine Bilder, kein pCloud-Aufruf.

## Ehrliche Grenzen (aus dem Auftrag, bestätigt)

1. Die kanonische Datei liegt **auf dem PC**; am Handy fehlt sie (die Übergabe
   ist ein eigener Schritt wie N13c). Fehlt sie, sagt `text_antwort` das
   ehrlich („liegt noch auf dem PC") und die Routen antworten mit `ok: false`
   und deutschem `error` — nie ein 500er.
2. `name` ist in der echten Datei bei den **Personen-Kennungen** durchweg
   `null` (`anzahl_namen_bestaetigt: 0`) — die Antwort nennt deshalb
   `Person_00x`-Kennungen. Die **Namen** warten weiterhin auf den Eintrag des
   Nutzers in `personen_bestaetigt.json`. Der Dienst nennt einen Namen nur,
   wenn er **in der Datei steht**; er erfindet nie einen Namen und liest keine
   Kandidatenlisten.
3. Der plan-interne Testtag **2019-12-27** trägt keine Andockung → 0 Aussagen;
   das ist kein Fehler, sondern der Befund aus N27e.
4. Der Massenlauf der Gesichter über alle 9.430 Fotos (~15 h) ist **nicht**
   Teil dieses Schritts.

## Offen / bewusst weggelassen

* **Frontend-Zeile im Selbsttest:** Der Block steht als Feld `beziehungen` in
  der JSON-Antwort von `/api/selbsttest`. Eine eigene Klartext-Zeile wurde
  **nicht** ergänzt: `frontend/app.js` liest die Felder explizit (z. B.
  `d.fotos`), der neue Block erschiene dort also nur mit einer JS-Änderung —
  und der Auftrag verbietet einen Umbau von `app.js` ausdrücklich (die
  Chat-Antwort ist der Zweck dieses Schritts, der Selbsttest ist Beiwerk).
  Bleibt als offener Punkt.
* **Datenherkunft:** `beziehungen_laden()` liest die **Übersicht**
  (`beziehungen.json`) für die Kennzahlen und meldet `existiert: true` nur,
  wenn **beide** Dateien vorhanden und die Übersicht lesbar ist; `pfad` zeigt
  auf die Aussagen-Datei `beziehungen.jsonl`. Ein unplausibles Datum liefert
  `gueltig: false` und einen deutschen `error` ohne Wurf; ein Tag ohne Aussagen
  ist kein Fehler (`gueltig: true`, `anzahl: 0`).
* **Defekte JSON-Zeilen** in der Aussagen-Datei sind eine Zählung, kein
  Abbruch (im Modul `_aussagen_lesen`); die betreffende Testfunktion
  `test_tag_kaputte_json_zeile_ist_defekt_kein_wurf` prüft das.

## Datenschutz

In Code, Tests, Auftrag und dieser Doku stehen **keine** echten Personen-,
Chat- oder Ortsnamen und keine echten Datei-/Kontaktkennungen — nur erfundene
Beispiele (`Person_001`, „Musterperson", „Musterchat", „Beispielthema") und
Zahlen. Die Belegdatei `n28_belege.txt` enthält ausschließlich Zahlen/Daten.
Keine Schlüssel/Token in Ausgaben oder Dateien.
