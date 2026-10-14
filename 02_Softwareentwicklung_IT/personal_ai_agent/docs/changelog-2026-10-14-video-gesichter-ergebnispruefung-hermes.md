# 14.10.2026 – Ergebnisprüfung „Video-Gesichter im Quiz“ (V1–V4), Hermes-Runde

Prüfer: **Hermes** (zweiter Prüfer nach der Rollentabelle in `AGENTS.md`).
Vorlage: `.hermes/plans/2026-10-14_video-gesichter-ergebnis.md` (Fassung 1).
Prüfgegenstand (umgesetzter Code gegen Plan `.hermes/plans/2026-10-14_video-gesichter-im-quiz.md`,
Fassung 3):

| Schritt | Commit | Inhalt |
|---|---|---|
| V1 | `a20f7fb` | `tools/foto_sortierung/video_standbilder.py`, `backend/tests/test_video_standbilder.py`, Konstante `gruppen_quiz.VIDEO_STANDBILDER_DATEINAME` |
| V2 | `c4e8535` | `backend/app/services/gruppen_quiz.py` (Karte lesen, Zusammenführen, Beispiele, Sperre), `backend/tests/test_gruppen_quiz_video.py` |
| V3 | `180f3db` | `frontend/gruppen_quiz.js`, `frontend/style.css`, `frontend/index.html`, `frontend/tests/test_gruppen_quiz.js`, `frontend/tests/test_foto_galerie.js` |
| V4 | `17c8714` | `backend/tests/test_video_standbilder_uebergabe.py` |

Codex hatte Runde 1 am 14.10. um 18:41 gefahren (**EINWAND**, vier Befunde). Seither sind die
betroffenen Dateien unverändert (gemessen an den Zeitstempeln: `video_standbilder.py` 17:42,
`gruppen_quiz.py` 18:05) — geprüft wurde also derselbe Stand.

## Urteil: EINWAND — alle vier Codex-Befunde bestätigt, dazu zwei eigene Hinweise

Nicht durch Nachlesen der Tests, sondern mit einer **eigenen Sonde** gegen die echten Funktionen
(Wegwerf-Dateien im Tempordner, erfundene Kennungen, Attrappen für pCloud, Frame-Entnahme und
Hochladen). Kein Netz-, Modell- oder Vision-Aufruf, kein Bild geöffnet, keine Kosten.

### Die vier Codex-Befunde — unabhängig nachgemessen

1. **Datenschutz: der Ergebnis-Pfad steht auf der Konsole (bestätigt).**
   `video_standbilder.py:419` baut `python tools/pcloud/uebergabe_hochladen.py --dateien {ergebnis}`
   und `:423` druckt ihn. Eigene Messung: der volle Pfad erscheint in der Ausgabe
   (`… \ergebnis1.jsonl`). Der Test `test_video_standbilder.py:271` (`test_konsole_nennt_keine_kennungen`)
   prüft nur, dass **Kennungen/Name/Dateiname** fehlen — der Pfad ist nicht geprüft.
   Der Changelog behauptet dagegen pauschal „Die Konsole zeigt nur Zahlen"; das ist so nicht
   codegenau. Einordnung: **niedrig** — der Pfad stammt aus der Konfiguration, nicht aus den Daten,
   und enthält keinen Inhalt; er kann aber den Benutzernamen (`C:\Users\sebas\…`) zeigen, wenn
   `--ergebnis` absolut gesetzt wird.

2. **Repo-Schutz über eine Verzeichnisverknüpfung umgehbar (bestätigt).**
   `pruefe_ausserhalb_repo` (`:347–353`) prüft nur `abspath`/`normcase`, löst Verknüpfungen nicht auf
   (`realpath`). Eigene Messung mit einer Windows-Verzeichnisverknüpfung (`mklink /J`): ein direkter
   Repo-Pfad wird abgewiesen (Exit 2), derselbe Pfad über eine Verknüpfung **nicht** — beim Schreiben
   landeten personenbezogene Daten im Repo. Einordnung: **niedrig/mittel** (die Verknüpfung muss
   zuerst angelegt werden; `realpath` in `:348` schließt die Lücke).

3. **Fortsetzen nach einem Abbruch verliert den nächsten Eintrag (bestätigt).**
   `_zeile_schreiben` (`:255–260`) hängt mit `open(..., "a")` unmittelbar an das Dateiende an. Eigene
   Messung: eine unvollständige JSON-Zeile ohne Zeilenumbruch am Ende, dann ein Lauf → **0** gültige
   Ergebniszeilen; die neue Zeile klebt an der abgebrochenen. Beide Leser (`video_standbilder.py:164`,
   `gruppen_quiz.py:714`) verwerfen diese eine Zeile. Einordnung: **niedrig** — heilt beim nächsten
   Lauf (die `bild_id` gilt als nicht erledigt und wird sauber neu geschrieben), kostet aber einen
   Lauf. Ein Vorab-Test „endet die Datei auf einem Zeilenumbruch?" schließt es.

4. **Ungültige Bildmaße werden als sichtbares Gesicht gezählt (bestätigt).**
   `gruppen_quiz.py:734` übernimmt `breite`/`hoehe` der Karte ungeprüft, `_video_gesichter` (`:762–766`)
   macht daraus ein sichtbares Gesicht. Eigene Messung: Karte mit `breite`/`hoehe` `null` →
   `sichtbar 1, ohne 0`, Maße `(None, None)`. Der Frontend-Ausschnitt fällt dann aus
   (`gruppen_quiz.js:439–448` passt das ganze Bild ein), das Gesicht zählt aber nicht in `videos`.
   Einordnung: **niedrig** (die Karte wird vom eigenen Werkzeug immer mit Maßen geschrieben; nur eine
   fremde/beschädigte Karte löst es aus).

### Zwei eigene Hinweise (von Codex nicht genannt)

- **A (niedrig) – der Gruppenkopf zählt die Video-Gesichter weiter roh.** `naechste()` gibt
  `gruppe.get("videos")` durch (`gruppen_quiz.py:611`); das stammt aus `personen_beispiele.json`
  (gemessen: jede Gruppe trägt ein Feld `videos`) und zählt **alle** Video-Gesichter der Gruppe.
  Die Ansicht zeigt dieselben Gesichter nach dem Standbilder-Lauf aber als normale Gesichter
  (`frontend/gruppen_quiz.js:113`). Die korrigierte Zählung („nur ohne Standbild") liefert nur
  `gesichter()` (`:896`) — der Kopf bleibt also stehen, während das Raster wächst.
- **B (niedrig) – die Lesbarkeit der Zeit hängt am Score.** In `_video_zeilen_laden` stehen
  `guete = …` und `zeit = float(z.get("zeit_s"))` im selben `try` (`gruppen_quiz.py:697–701`): ein
  unlesbarer `anteil`/`score` wirft und setzt **auch** `zeit = None`, sodass ein sonst darstellbares
  Video-Gesicht als „ohne Standbild" verworfen wird. Getrennte `try`-Blöcke beheben es.

### Kernkriterien des Plans — grün (eigene Messung)

- **Rahmen stimmig:** `bbox × skala` und das Standbildmaß passen zusammen. Frame 1920×1080 → Standbild
  1600×900 (skala 0,833333); `bbox [100, 200, 300, 400]` → `[83, 167, 250, 333]`, innerhalb der
  Standbildkanten. `_mass_passt` weist fehlende Klammern (Null/Text) ab.
- **Idempotenz:** zweiter Lauf → 0 Uploads, „Offen: 0 Videos, 0 Standbilder"; `fsync` je Zeile;
  vorhandener Name wird wiederverwendet (eigene Messung mit gefülltem Zielordner: 0 Uploads).
- **Temp-Datei immer entfernt:** nach den Läufen 0 Reste (`standbild_*`).
- **Sperre:** die Video-`gid` (z. B. `900001:0`) passt auf das `_GID`-Muster und wird über
  `_video_gids` in `ausschliessen`, `ausschliessen_person` und `zuordnen` abgewiesen
  (`gruppen_quiz.py:909`, `:1047`, `:1125`) — es gibt keine stille Falschspeicherung.
- **Kaputte Karte wirft nicht:** `_standbilder_laden` liefert `{}`, das Quiz läuft wie ohne Karte.
- **Oberfläche:** Marke nur per `textContent` (`gruppen_quiz.js:429`), Video-Kacheln nicht
  markierbar (`:557`), Cache-Kennungen erhöht (`index.html`: `gruppen_quiz.js?v=20261014A`,
  `style.css?v=20261014A`).

## Belege

- **Gezielte Testmenge aus der Vorlage (nur lesend):**
  `tests/test_video_standbilder.py tests/test_gruppen_quiz_video.py tests/test_gruppen_quiz.py
  tests/test_video_standbilder_uebergabe.py tests/test_frontend_node.py` →
  **163 passed, 1 skipped, 2 warnings** (35,05 s), Exit 0.
- **Voller Prüfbefehl im Arbeitsbaum:** `2 failed, 4321 passed, 3 skipped, 3 warnings` (402,08 s) —
  **ROT**. Die zwei Fehler sind `tests/test_datenschutz_waechter.py`
  (`test_regel_offene_routen_genau_die_bekannten_vier`, `test_regel_jede_geschuetzte_route_hat_key_schutz`):
  die **uncommittete** fremde Änderung an `backend/app/router/auth.py` (+157 Zeilen) bringt die Route
  `/api/auth/abmelden` ohne `require_api_key` mit. **Auf dem committeten Stand (`HEAD`) ist dieselbe
  Testdatei grün** (eigener Lauf in einem getrennten Verzeichnisbaum: **69 passed**). Der rote Lauf
  gehört also **nicht** zu diesem Prüfgegenstand; kein fremder Code, keine `.env`, kein Bild angefasst.
- Eigene Sonde (zwei Wegwerf-Skripte im Tempordner) — kein Netzaufruf, kein Modellaufruf, kein
  Vision-Aufruf.

## Offen und bei Sebastian

Drei der vier Codex-Befunde und beide eigenen Hinweise sind **klein** (robuste Ränder); Befund 2 ist
der einzige mit Datenwirkung (Verknüpfung). Alle sind Sache des **Masters** (Behebung), nicht dieses
Prüfers — keine Selbstfreigabe. Unverändert offen bleibt dazu: der rote Arbeitsbaum aus der fremden,
laufenden HTTPS-Arbeit (`auth.py`), der erst grün werden muss, bevor committet/gepusht wird.
