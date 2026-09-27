# Feinauftrag N9c — Mengen-Zweig erreichbar machen + Gesichtsausschnitt-Kachel

> **Rolle:** Planer = Hauptagent. **Ausführer = Hermes-Subagent.** Danach prüft
> ein **frischer** Subagent der **anderen Modellfamilie** (`openai/gpt-5.6-luna`).
> Kein Commit durch den Ausführer — committet wird vom Planer nach Abnahme.

## Ausgangslage (gemessen, nicht behauptet)

Der Nachtlauf N9b hat die Personen-Stufe am echten Bestand gerechnet. Ergebnis:
die **Mengen-Regel greift** (Menschenmengen werden nicht angelernt), aber sie
greift über den Zweig **`leer`**, nicht über `menge`. Ursache: `ANTEIL_MIN`
(N9a) mit **0,0005** (= 0,05 % der Bildfläche) verwirft echte Gesichtsfunde.

Eigene Vormessung des Planers, **nur lesend**, 30 Bilder aus den fünf
bilderstärksten Mengen-Anlässen (Themen „Konzert und Buehne", „Fest und Feier"),
`~/foto_sortierung/n9c_probe.py`, 87,7 s, 0 Fehler:

| ANTEIL_MIN | Bild-Art über 30 Bilder |
|---|---|
| **0,0005 (heute)** | `gruppe 12 · leer 9 · unklar 9 · menge 0` |
| 0,0001 | `gruppe 12 · leer 6 · unklar 11 · menge 1` |
| 0,00005 | `gruppe 12 · leer 6 · unklar 11 · menge 1` |
| **0,00002** | `gruppe 12 · leer 6 · unklar 11 · menge 1` |
| **0,00001** | `gruppe 12 · leer 6 · unklar 11 · menge 1` |

* Kleinste **echte** Detektion in dieser Stichprobe: Anteil **0,000145**
  (`56226986656`, 13 kleine Gesichter — sie werden heute alle verworfen).
* Kleinste echte Detektion überhaupt im Nachtlauf (N9b): **0,000022**
  (16×22 px auf 4608×3456).
* Ab **0,0001** ist der Zweig `menge` am echten Foto **erreicht** und ändert
  sich bei weiterer Absenkung **nicht mehr** (die Verteilung ist ausgemessen).
* `gruppe` bleibt über **alle** Kandidaten **12** — **keine** Regression.

## Auftrag (genau ein Schritt)

### Teil 1 — `ANTEIL_MIN` auf den gemessenen Wert setzen

In `tools/foto_sortierung/personen_cluster.py`:

* `ANTEIL_MIN` von **0,0005 auf 0,00001** senken (1 × 10⁻⁵ ≈ 11×11 px bei
  12,2 MP — das ist **YuNets eigene Mindest-Box**, 10×10 px).
* Kommentar/Docstring **ehrlich umschreiben**: das Flächen-Tor ist kein
  Rausch-Tor mehr (das ist `MIN_SCORE = 0,6`); es verwirft nur noch
  **entartete Boxen**. Beleg-Zahlen der Messung nennen (0,000145 / 0,000022).
* Eine Herleitung als Kommentar, keine Behauptung.
* **Keine andere Schwelle anfassen** — `MIN_SCORE`, `ANTEIL_ERKENNBAR`,
  `MENGE_ANZAHL`, `KATALOG_SCHWELLE`, `CLUSTER_SCHWELLE`,
  `CLUSTER_MIN_NACHBAR`, `ALT_SCHWELLE` bleiben **wertgleich**. `MENGE_ANZAHL`
  bleibt 6 (das ist ein N9a-Beschluss und braucht eine eigene Messung).
* `MENGEN_PARAMS` zieht den neuen Wert automatisch nach.

### Teil 2 — Kachelquelle um den Gesichtsausschnitt erweitern

In `tools/foto_sortierung/gesicht_erkennen.py`:

* `kachel_quelle(service, max_bytes=..., groesse=None, ausschnitt=False, rand=0.45)`
  erweitern. Bei `ausschnitt=True` und brauchbarem `bbox` (vier Zahlen:
  `x, y, breite, hoehe`) wird **in-memory** um das Gesicht geschnitten:
  Rand `rand × bbox-Masse` je Seite, an die Bildgrenzen geklemmt, danach auf
  die Ziel-Kachelgröße skaliert (Vorgabe quadratisch, z. B. 200×200).
* **Nur PIL** (`_verkleinern` nutzt bereits PIL) — **kein** `cv2`, kein neuer
  Import zur Ladezeit, kein Netz, **kein** Schreiben auf Platte.
* **Rückfall statt Abbruch:** fehlender/unbrauchbarer `bbox`, unlesbare Bytes,
  entarteter Ausschnitt, fehlendes PIL → **ganzes Foto** wie bisher; eine
  Ausnahme darf **nie** nach außen dringen.
* CLI: Schalter `--ausschnitt` in `main()`; die Ausgabe nennt in Klartext, ob
  Ausschnitt oder ganzes Foto verwendet wird. Standard bleibt **ganzes Foto**
  (der Trockenlauf bleibt unverändert).
* Eine **reine, testbare** Funktion für den Schnitt (z. B.
  `ausschnitt_rechnen(bbox, breite, hoehe, rand)` →
  `(x0, y0, x1, y1)` oder `None`) — damit die Geometrie ohne Bilddatei prüfbar
  ist.

### Teil 3 — Echte Messung nach der Änderung (nur lesend)

* Die Vormessung des Planers (`~/foto_sortierung/n9c_probe.py`, 30 Bilder) mit
  dem **neuen** Stand wiederholen: `leer 6 · gruppe 12 · unklar 11 · menge 1`.
  Das `menge`-Bild **benennen** (fileid) und seine Zahl der kleinen Gesichter.
* Gegenprobe zum selben Bestand mit dem **alten** Wert 0,0005 über
  `params={"anteil_min": 0.0005}` (reine Rechnung, kein zweiter Download):
  `menge 0`, `leer 9` — die Änderung wird damit **vorher/nachher** belegt.
* Referenzseiten mit `--ausschnitt` bauen (Ausgabe **außerhalb** des Repos,
  z. B. `~/foto_sortierung/personen_echt_ausschnitt/`): Anzahl Seiten, je
  Datei Bytes; zweiter Lauf **0** neue Dateien (Idempotenz).
* Beleg, dass **kein** Original auf Platte landet (keine neuen Bilddateien
  außerhalb des Ausgabeordners; `manifest.jsonl` weiter **0** Einträge).

### Teil 4 — Tests + Doku

* Tests **offline**, `tmp_path`, kein Netz, kein `cv2`, keine echten Namen:
  * Geometrie des Ausschnitts (Rand, Klemmung, entartete Box → `None`),
  * `kachel_quelle` mit `ausschnitt=True`: quadratische Ausgabe, Platzhalter-
    Rückfall bei fehlendem bbox / kaputten Bytes, **kein** Schreiben ins Repo,
  * `ANTEIL_MIN`: die N9a-Tests, die den **alten Zahlenwert** festgenagelt
    haben, werden auf die **Regel** umgestellt (relativ zur Konstante bzw. über
    `params`), nicht gelöscht. Jede Anpassung im Changelog begründen.
* Neu: `docs/changelog-2026-09-27-mengen-zweig.md` mit allen Zahlen und
  Vorher/Nachher.
* **Datenschutz:** keine Personennamen, Orte, Ereignisnamen im Repo. Erlaubt
  sind blanke Kalenderjahre und Katalog-/Bucket-Begriffe. **Keine**
  Schwellen-Werte eines Geheimnisses, keine Vektorwerte, keine Bildbytes.

## Prüfkriterium des Schritts

1. `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **Exit 0**
   (Baseline vor dem Schritt: **1175 passed**).
2. Der Zweig `menge` ist an mindestens **einem echten Mengen-Foto** erreicht
   (Zahl nennen, 1 von 30 ist in Ordnung — nicht schönreden).
3. `gruppe` bleibt **12** auf derselben Stichprobe (keine Regression).
4. Die neuen Referenzseiten enthalten **Gesichtsausschnitte**, zweiter Lauf 0.
5. Keine schreibende pCloud-Operation, **keine** Löschfunktion, Manifest
   unverändert 0 Einträge, Originale nie auf Platte.

## Harte Regeln für den Ausführer

* **Keine** git-Befehle (kein add/commit/push) — das macht der Planer.
* Fremde Dateien nicht anfassen (`docs/experimente/live_zahlen.*`,
  `docs/recherche/*.html` gehören einem zweiten Agenten).
* An native Windows-Programme **immer** `C:/…`-Pfade, **nie** `/c/…`
  (Pitfall aus N6c: der Ordner landete unter `C:\c\Users\…`).
* Kein `git add -A`, kein `--force`.
