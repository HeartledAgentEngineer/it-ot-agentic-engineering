# 21.10.2026 – Gruppierung v2, Schritt 3: Aliasmengen und Regelkonflikte

Plan: `.hermes/plans/2026-10-20_gruppierung-v2-fassung5.md` (Fassung 5.3, Auflage 3).
v1 bleibt Standard und ändert sich nicht. v2 schreibt weiterhin nur über das Tor
`--freigabe` in den Kandidatenordner.

## Was sich ändert
- **Aliasmenge je Gruppe.** Werden Gruppen über `gleich` vereint, merkt sich v2 alle
  alten Kennungen, die darin stecken: als Feld `aliase` je Gruppe und flach in
  `aliasmengen.json` (nur beim echten Schreiben, nie im Trockenlauf).
- **Ketten werden vollständig vereint.** Die `gleich`-Paare bilden zuerst eine
  transitive Hülle über alle Kennungen, auch über Kennungen ohne Gesicht
  (A = B, B = C mit gesichtslosem B → eine Gruppe, Aliasmenge {A, B, C}).
  `verschieden`-Regeln, gemeinsame Bilder und verschiedene Namen verhindern eine
  Vereinigung weiterhin. Eine gesichtslose Kennung, die mehrere getrennte
  Gruppen berührt, bleibt ohne Gruppe und sperrt die Freigabe.
- **Widerspruch in einer Kette:** Enthält eine `gleich`-Klasse irgendwo ein
  `verschieden`-Paar oder zwei verschiedene Namen, wird in dieser Klasse gar nichts
  über `gleich` vereint, auch nicht teilweise. So hängt das Ergebnis nicht von der
  Reihenfolge ab. Ihre gesichtslosen Kennungen bleiben ohne Gruppe und sperren die
  Freigabe. Im Bericht steht dazu `gleich_klassen_mit_konflikt`.
- **Sperrzahlen rechnen über die Aliasmenge.** `benannte_ohne_gruppe`, leere
  benannte Gruppen und `wechsel_unerlaubt` laufen über eine gemeinsame Funktion
  `gruppierung_bewerten._gleiche_gruppe` (transitiv). Ein `gleich`-Merge zweier
  benannter Kennungen sperrt nicht mehr, er steht als `durch_gleich_vereint` im
  Bericht.
- **Ausschlüsse gelten für die ganze Aliasmenge**, beim Andocken und im Abschluss.
  Trifft ein Ausschluss ein Vorbild der vereinten Gruppe, ist das ein
  Regelkonflikt: Exit 2, im Text nur die Zahl, nichts wird geschrieben.
- **Feste Zuordnungen** auf eine weggemergte Kennung landen in der vereinten Gruppe.
- **`gleich` ohne sauberen Kern:** Die Gruppe entsteht aus dem besten verfügbaren,
  auch unsicheren Gesicht. Ohne jedes Gesicht zählt `gleich_ohne_vorbild`.
- **`gruppierung_bewerten.py --aliase <datei>`** bewertet einen bestehenden Stand
  aliasfähig. Ohne Angabe rechnet die Bewertung kennungsgenau, und der Bericht
  sagt das in einer Hinweiszeile. Im Trockenlauf mit `--bewerten` reicht v2 die
  Aliasmengen im Speicher durch.
- `gruppen_quiz.py` bleibt unverändert und verträgt das Zusatzfeld (Test).

## v1 bleibt unverändert
Der Weg über die Klassen gilt nur in v2. v1 nimmt weiter den alten Paarweg,
sichert genau drei Dateien und zeigt im `--bewerten`-Bericht keine
Aliasmengen-Zeile (`alias_hinweis` in `gruppierung_bewerten.bericht_text` /
`vergleich_bericht` / `einzel_bericht`; das eigenständige Bewertungswerkzeug
zeigt die Zeile weiter). Ein Test vergleicht v1 in sieben Fällen Wert für Wert
mit der Fassung aus Commit `80a4c69`, dem letzten Stand vor diesem Schritt.

## Belege
- Neu: `backend/tests/test_gruppierung_v2_aliase.py`. Angepasst: ein Test in
  `test_personen_gruppieren_v2.py`, weil eine per `gleich` zusammengelegte Kennung
  nicht mehr als verloren gilt.
- Gezielte Gruppierungstests: 362 passed. Dazu der volle Prüfbefehl im
  Commit-Haken.
- Ergebnisprüfung durch Codex (gpt-6-sol, nur lesend), Runden 1–5 je EINWAND:
  1. Kette über gesichtslose Kennung
  2. Widerspruch in der Kette
  3. v1 vereinte mit
  4. v1 sicherte eine vierte Datei
  5. Hinweiszeile im v1-Bericht

  Alle fünf sind behoben, **Runde 6 FREI**. Protokoll:
  `.hermes/pruefkreis/gruppierung-v2-schritt3-pruefung-codex.md`.
- Ausführer: Claude Sonnet, weil der Codex-Worker an der Sandbox scheiterte
  („blocked by policy“). Die Korrekturen aus den Runden 4 und 5 hat der Master
  (Claude Opus) selbst gemacht.

## Offen (Plan)
Schritt 4 (Sicherungen, transaktionales Schreiben, `--rueckrollen`/`--weiter`),
5 (Basisschnappschuss), 6 (Kennzahlen), 7 (Gesamtprüfung), 9 (Messlauf durch Sebastian).
