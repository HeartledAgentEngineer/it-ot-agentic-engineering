# Gruppierung v2, Schritt 1: fail-closed-Kern (Plan-Fassung 5.3, Auflage 1 + Auflage 6)

Datum: 20.10.2026 · Werkzeug: `tools/foto_sortierung/personen_gruppieren.py`
(Arbeitsbaum des v2-Strangs) · Plan: `.hermes/plans/2026-10-20_gruppierung-v2-fassung5.md`
(Fassung 5.3, freigegeben durch Prüfung R9 = FREI).

Dieses Dokument beschreibt **nur den Schritt 1** der Planliste („Fail-closed Kern (Auflage 1 +
6-Tor)“). Die Schritte 2–6 (G0/G1, Aliasmengen, Sicherungen/Transaktion, Snapshot,
Bewertungszahlen) sind **nicht** gebaut; v1 bleibt der Standard, und v2 schreibt weiterhin nur
nach Freigabe und nur in den Kandidatenordner.

## Was jetzt fail-closed ist

### 1. Regel B — Bestandsschutz benannter Gesichter (Auflage 1)

- **Jedes** Gesicht, dessen Kennung in der bestehenden `gesicht_zuordnung.jsonl` steht und in
  `personen_bestaetigt.json` **benannt** ist, bleibt in dieser Kennung — auch ein **unsicheres**
  Gesicht (score < 0,90 oder Ausschnitt < 64 px), das der Kern (nur saubere Gesichter) gar nicht
  gruppiert. Solche Gesichter werden nicht mehr als Andock-Kandidaten geführt, sondern nach dem
  Andocken ihrer alten Kennung zugeordnet (`geschuetzt` in `lauf_rechnen_v2`).
- Saubere Gesichter aus der alten Zuordnung sind jetzt zusätzlich **fixiert** (der Phasenvergleich
  kann sie nicht mehr umverteilen).
- **Ausnahmen sind nur die beiden ausdrücklich gespeicherten:**
  1. **feste Einzelzuordnung** (`zugeordnet`) auf ein anderes Ziel → zählt als **genehmigt**
     (`wechsel_genehmigt`), wird immer ausgewiesen, blockiert nicht;
  2. **Ausschluss** genau dieses Gesichts (`ausgeschlossen`) → das Gesicht bleibt draußen und wird
     **nicht** an eine andere Person angedockt (`ausschluss_genehmigt`), es „wechselt“ nicht.
- **Zählregel (Befund R8-1):** jede andere Änderung der Gruppenzugehörigkeit eines benannten
  Gesichts zählt als **`wechsel_unerlaubt`** und **muss 0 sein**.
- **Fail-closed-Konflikte** (Exit 2, im Text **nur die Zahl** — keine Namen, keine Bild-IDs):
  - eine benannte Kennung, die geschützte Gesichter hält, aber **keine Gruppe** hat;
  - dieselbe Kennungsgruppe steht **gleichzeitig** in `gleich` und `verschieden`
    (`Regelkonflikte: n`).
- **Ehrliche Grenze:** die in der Auflage genannte Variante „eine `verschieden`-Regel ließe sich
  nur durch einen benannten Wechsel erfüllen“ ist in v2 **nicht konstruierbar** — benannte Gruppen
  werden nie über Ähnlichkeit vereint (`_verschmelzen` mit `benannt`), eine `verschieden`-Regel
  trennt also nur und bewegt kein Gesicht (Test
  `test_verschieden_regel_bewegt_kein_benanntes_gesicht`). Der gebaute Konfliktfall ist der
  widersprüchliche Regel-Paar-Fall.

### 2. Schreib-Tor und Kandidatenordner (Auflage 6 + Auflage 1, Satz 2)

- **Neue Schalter:** `--ausgabe-kandidat` (Standard `~/foto_sortierung/kandidat_v2`),
  `--produktiv`, `--freigabe <datei.json>`.
- **v2 schreibt nie in `--ausgabe`:** ohne `--produktiv` geht die Ausgabe in den Kandidatenordner
  (ebenfalls außerhalb des Repos, geprüft über das vorhandene `pruefe_ausserhalb_repo`). Der
  produktive Ordner ist nur mit gültiger Freigabe **und** `--produktiv` erreichbar.
- **Ohne `--freigabe` endet `--verfahren v2 --schreiben` mit Exit 3** und der Meldung „Ohne
  Freigabe wird v2 nichts geschrieben“ — es wird nichts gerechnet und keine Datei angelegt.
- **Die Freigabedatei** ist ein JSON-Objekt:
  `{"snapshot_sha256": "<64 hex>", "parameter": {…}, "urteil": "pass", "werte": {…}}`.
  Der Lauf rechnet den **Snapshot-hash frisch** (`eingabe_hash`: sha256 über jede Eingabedatei —
  Inhalt oder `fehlt` — plus die Parameter) und bricht mit **Exit 3** ab, wenn
  - der `snapshot_sha256` nicht passt („die Grundlage hat sich geaendert“),
  - die `parameter` (Verfahren, `zuordnung`, `verschmelzen`, `zwilling`, `min_groesse`,
    `min_score`, `runden`) abweichen,
  - das `urteil` nicht `pass` ist,
  - die Datei keine `werte` nennt, eine der drei **Sperrzahlen** darin nicht 0 ist, oder
  - **die Sperrzahl des Laufs selbst** nicht 0 ist.
- **Sperrzahlen** (`bericht["v2"]` und `lauf["sperrzahlen"]`): `benannte_ohne_gruppe`,
  `leere_benannte_gruppe`, `wechsel_unerlaubt`. Ohne Aliasmenge (Plan-Schritt 3) sind die ersten
  beiden **dieselbe Zahl** — das steht als Kommentar im Code und wird in Schritt 3 getrennt.
- Der Bericht nennt die Wechsel und die Sperrzahlen in Klartext („UNERLAUBT 0 (muss 0 sein)“,
  „Sperrzahlen der Freigabe (alle muessen 0 sein)“).

## Was bewusst NICHT in diesem Schritt steht

- Keine Aliasmengen (Auflage 3 / Plan-Schritt 3), keine G0/G1-Pflichtquellen und kein
  Vollständigkeitsnachweis (Auflage 2 / Schritt 2), keine transaktionalen Sicherungen und kein
  `--rueckrollen` (Auflage 4 / Schritt 4), kein versionierter Basisschnappschuss (Auflage 5 /
  Schritt 5), keine erweiterten Bewertungszahlen wie `fest_verletzt` oder Namens-Reinheit je
  Kennung (Auflage 6, Tabellenzeilen 3 und 8 / Schritt 6). Die Pass/Fail-Tabelle ist deshalb noch
  nicht vollständig prüfbar; das Tor prüft heute die drei Sperrzahlen (a), (b), (c).
- Keine Änderung an `personen_bestaetigt.json`/`personen_vorgaben.json` (nur lesen), keine
  Vektoren außerhalb des PCs, keine Netzaufrufe, keine Geräteeingriffe.

## Belege (in diesem Lauf ausgeführt)

- Neue Testdatei `backend/tests/test_gruppierung_v2_fail_closed.py` — **23 Prüfungen**: Regel B
  sauber/unsicher (mit Gegenprobe, dass dasselbe Gesicht ohne alte Zuordnung wirklich zur anderen
  Person dockt), feste Zuordnung als genehmigt, Ausschluss ohne Wechselzählung, `verschieden`
  bewegt nichts, Regelkonflikt, Regel-B-Konflikt ohne Gruppe (nur Zahlen im Text), Sperrzahlen im
  Bericht; Schreib-Tor: Trockenlauf ohne Freigabe, Schreiben ohne Freigabe (Exit 3), `--produktiv`
  ohne Freigabe (Exit 3), gültige Freigabe schreibt nur in den Kandidatenordner (produktiver
  Stand byte-gleich), `--produktiv` mit Schalter schreibt produktiv, falscher Snapshot-hash,
  falsche Parameter, Urteil ≠ pass, verletzte Sperrzahl in der Datei, Sperrzahl des Laufs,
  fehlende Freigabedatei (Exit 2), Kandidatenordner im Repo verboten (Exit 2), `eingabe_hash`
  deterministisch und reaktionsfähig, `freigabe_pruefen` mit jedem Ablehnungsgrund.
- `backend/tests/test_personen_gruppieren_v2.py` — **61 Prüfungen zusammen mit der neuen Datei**
  grün; die vier Schreibprüfungen des Strangs schreiben jetzt über
  `--verfahren v2 --schreiben --produktiv --freigabe …` (eigene Hilfsfunktion), damit sie die
  Auflage 6 mitprüfen statt sie zu umgehen.
- Voller Prüfbefehl im Hauptbaum: `cd backend && .venv/Scripts/python -m pytest tests/ -q`.

## Kosten, Datenschutz, Grenzen

- Kosten: 0 USD (nur lokale Rechenzeit, keine Modellaufrufe).
- Erfundene Vektoren und erfundene Namen in den Tests; nichts unter `~/foto_sortierung`
  angefasst, keine echten Personendaten, kein Netz, keine Geräteeingriffe.
- Offen bleibt: ob die strengere Gründung die Schutzkennzahl „ohne Kennung“ hält, entscheidet der
  echte v1↔v2-Messlauf (Plan-Schritt 9) — bis dahin v1-Standard und kein Schreiben ohne Freigabe.

## Nachtrag 20.10.2026 — Auflage 2 ist gebaut (G0/G1)

Der in diesem Dokument angekündigte nächste Schritt (Auflage 2: Pflichtquellen,
Vollständigkeitsnachweis gegen den Gerätestand des Handys, Handy-Stufe mit Exit ungleich 0, und
`vorlaeufig`/`veraltet` sperren das Schreiben) ist gebaut — Dokument
`docs/changelog-2026-10-20-gruppierung-v2-g0-g1.md`. Zwei Folgen für **diesen** Stand:

* `--verfahren v2 --schreiben` braucht jetzt **zusätzlich** einen gültigen Gerätestand
  (`--geraetestand`, Standard `~/foto_sortierung/geraetestand.json`) **und** eine Grundwahrheit, die
  nicht `vorlaeufig`/`veraltet` ist. Ohne Nachweis rechnet v2 nur noch als **Trockenmessung**
  (`--ohne-geraetenachweis`); mit `--schreiben` wird dieser Schalter abgelehnt.
* Die Reihenfolge der Tore in `main()` ist festgelegt und im G0/G1-Dokument belegt: erst das
  Schreib-Tor der Auflage 6 (Exit 3 ohne `--freigabe`), dann G0 (Exit 2), dann G1 (Exit 3).
