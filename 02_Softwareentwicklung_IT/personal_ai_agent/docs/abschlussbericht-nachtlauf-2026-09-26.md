# Abschlussbericht Nachtlauf 26./27.09.2026 — Schritt N10

> **Datum:** 28.09.2026 · **Schritt:** N10 („Doku + Protokoll + Abschlussbericht")
> aus `docs/plan-nachtlauf-2026-09-26.md` · **Rolle:** Ausführer (Subagent,
> schreibt ausschließlich Dokumentation) · **Prüfbefehl des Projekts (vom Planer
> gefahren):** `cd backend && .venv/Scripts/python -m pytest tests/ -q` →
> **1687 passed, Exit 0**.
>
> **Zahlenregel dieses Berichts:** Jede Zahl steht in einer Quelle, die hier als
> Dateiname genannt ist. Es wurde **nichts nachgerechnet, gerundet, geschätzt
> oder hochgerechnet** — außer den Stellen, die ausdrücklich als
> „Hochrechnung" oder „Schätzung" gekennzeichnet sind.

---

## 1. Auftrag und Rahmen

Der Nachtlauf lief vom 26.09.2026 (~04:30) bis in den 28.09.2026 hinein als
**Dauerlauf ohne Rückfragen**: Der Nutzer schlief 4–5 Stunden und gab vor, dass
selbst entschieden statt gefragt wird. Die Regeln stehen in `AGENTS.md`,
Abschnitt „Dauerlauf / Nachtarbeit (autonom)": keine Rückfragen, jeder Schritt
**verifiziert und einzeln committet**, **nie löschen**, jede Schreib-Operation ins
**Manifest** (rückholbar), idempotent bauen, billigste Wege zuerst
(`docs/plan-nachtlauf-2026-09-26.md`, Abschnitt „Auftrag"/„Regeln").

Verbindlich getrennt waren drei Rollen mit **getrenntem Kontext** (Plan-Abschnitt
„Rollen: Planer → Ausführer → Prüfer", nach `CLAUDE_EXTENDS.md` §6.6): **Planer**
= Hauptkontext, **Ausführer** = je Schritt ein Subagent (keine git-Befehle),
**Prüfer** = frischer Subagent aus **anderer Modellfamilie**.

Der Modell-Mix (Plan-Abschnitt „Modell-Mix") war: Planer `gpt-5.6-terra` **nur
über die Codex CLI** — dieses Kontingent war ab 27.09.2026 erschöpft („try again
at Oct 15th, 2026"), deshalb plante der Hauptagent mit
`deepseek/deepseek-v4.1-flash`; Ausführer war durchweg
`deepseek/deepseek-v4.1-flash` (Hermes-Subagenten, Cache 0,001 $/Mio); Prüfer
war `openai/gpt-5.6-luna`. Claude Code als Zweitweg war geprüft und ausgefallen
(`401 authentication_error`, OAuth-Token abgelaufen, Plan-Abschnitt
„Planer-Ersatz"). Datenschutzgrenze blieb: nur reiner Code geht an Codex.

---

## 2. Was fertig ist

Alle Zahlen stammen aus den Journal-Einträgen und den Schritt-Zeilen in
`docs/plan-nachtlauf-2026-09-26.md` (dort je Schritt mit Changelog-Verweis).
„Prüfer-Befund" nennt Modell, Rundenzahl und Endurteil.

| Schritt | Ergebnis in Zahlen | Prüfer-Befund |
|---|---|---|
| **N1** Cloud-Service selbst prüfen | Prüfbefehl **500 passed, Exit 0** (72,5 s; vorher 433 → +67 Tests). Rauchtest: `liste(0)` **18 Einträge** (17 Ordner, 1 Datei), `thumb()` **4185 Bytes** JPEG (120×120), Konto **2199,0 GB / 390,5 GB belegt** | **kein getrennter Prüfer genannt** — Selbstprüfung durch den Planer (Journal 27.09. ~05:05) |
| **N4** Themen-Stufe Werkzeug | Prüfbefehl **525 passed, Exit 0** (58,7 s; 500 + **25** neue Tests). Anlass-Regel: gleiche Minute = ein Anlass, neue Sitzung ab 30 min Lücke → **2.128 Anlässe** über alle Jahre, **380 für 2025**; 2 Kontaktbögen live (**10 Kacheln/62.566 B**, **36 Kacheln/262.437 B**); 2. Lauf: 0 geholt (idempotent) | **kein getrennter Prüfer belegt** (Journal 27.09. ~05:40) |
| **N5** Stichprobe Kosten | Vision-Blick auf den 36er-Bogen (262.437 B): **Nummern 1–36 einwandfrei lesbar**, Thema je Bogen erkannt, unbrauchbare Kacheln benannt (9/10/11, 25/26, 33/34); Kostenschätzung „deutlich unter 1 $" war **Schätzung, keine Messung** | **kein getrennter Prüfer belegt** (Plan-Zeile N5 „bestanden (27.09.)", Journal) |
| **N6** Themen je Anlass | Werkzeug `foto_themen_vision.py` + **59** Prüfungen; Prüfbefehl **628 passed, Exit 0** (Baseline 569). Live 2 Anlässe: 36 Kacheln → „Veranstaltung Publikum Bühne" **0,004354 $**; 10 Kacheln → „Konzert Band Auftritt" **0,002255 $**; 2. Lauf 0 Aufrufe | `openai/gpt-5.6-luna`: **6 Runden, 5 × nicht bestanden**, Runde 6 **bestanden** (8 von 10 Beanstandungen berechtigt) |
| **N6c** Themen-Katalog | `themen_katalog.py`, Katalog **53 Einträge, Version 3**; Prüfbefehl **657 passed, Exit 0**. Dieselben **161 Anlässe**: flash **0,209693 USD / 100 % Katalogtreffer / 14 × `Sonstiges` = 8,7 %** (37 Themen); flash-lite **0,058977 USD / 99,4 % / 18 × `Sonstiges`** (34 Themen). Sichtprobe 6 Bögen: **flash 4 : 2 flash-lite** | `openai/gpt-5.6-luna`: **1 Beanstandung** an einer Zahl (Doku korrigiert), **bestanden** (Journal ~09:55) |
| **N6b** Massenlauf Themen | Restlauf **1.967 Anlässe**, **1.962 gesehen**, 2 Fehlschläge, **7.722 Kacheln**, **5.954.092 ein / 370.113 aus Tokens = 2,711510 USD**, 94,2 min. Endstand: **2.128 Anlässe, 2.127 mit Katalog-Thema**, **48 Themen**, **242 × `Sonstiges` = 11,4 %**. Prüfbefehl **671 passed, Exit 0** (Baseline 665). Ein echter Codefehler behoben: `MAX_TOKENS = 4000` schnitt den 108-Kachel-Bogen ab → `max_tokens_fuer(anzahl)`, derselbe Anlass läuft mit **4.420 Ausgabe-Tokens** durch | `openai/gpt-5.6-luna`: **2 Runden** — Runde 1 **nicht bestanden** (3 Punkte, 2 berechtigt → Zahlen/Doku korrigiert), Runde 2 auf Commit `0318e56` **BESTANDEN, 0 Abweichungen** |
| **N6d** Zielkatalog aus eigenen Ordnern | `foto_kategorien.py` (**855 Zeilen**) + **38** Tests; Prüfbefehl **709 passed, Exit 0** (Baseline 671). Live `--zeigen`: **18 Kategorien · 113 Unterordner · 10 mit Unterordnern · 11 Buckets (10 gebunden, 1 × null)**, nichts geschrieben | `openai/gpt-5.6-luna`: **bestanden** (Rundenzahl im Journal nicht genannt) |
| **N6e** Event-Abgleich | `event_abgleich.py` (**1.060 Zeilen**) + **51** Tests; Prüfbefehl **760 passed, Exit 0** (Baseline 709). Live nur lesend: **2.134 Anlässe · 39 Vorschläge = 1,8 %** (tag 10, monat 29) · **600 schwache Hinweise** (jahr 495, spanne 105) · 2.095 ohne Vorschlag (276 davon: Kategorie fehlt im Bestand) · **112 von 113** Unterordnern erreichbar | `openai/gpt-5.6-luna`: **3 Runden** — Runde 1 **nicht bestanden** (echte Ordnernamen im Repo, Zahl 109 → 112), Runde 2 **nicht bestanden** (3 Resttreffer = blanke Kalenderjahre → als Fehlalarm begründet), Runde 3 **BESTANDEN** |
| **N7** Trockenlauf Sortieren | `foto_sortieren.py` (**1.149 Zeilen**) + **119** Tests; Prüfbefehl **879 passed, Exit 0** (Baseline 760). Live nur lesend: **9.430 Zeilen · 2.127 Anlässe · 7.616 Züge** (alle mit Dateikennung) · Doppelungen **1.534 in der CSV** (866 ohne Anlass-ID, **668** übersprungen) · **1.146 Zeilen ohne Anlass-ID** · **2.108 Ordner neu / 82 vorhanden** · **2.088 Events neu / 39 wiederverwendet** (= die 39 sicheren Vorschläge aus N6e) · 11 Kategorien | `openai/gpt-5.6-luna`: **2 Runden** — Runde 1 **nicht bestanden** (Doppelungs-Zahl irreführend, wirkungslose Assertion `… or True`), Runde 2 **BESTANDEN, „Abweichungen: keine."** |
| **N9a** Personen-Verfahren | `personen_cluster.py` (**1.510 Zeilen**) + **216** Tests; Prüfbefehl **1095 passed, Exit 0** (Baseline 879). Synthetische Stichprobe: **12 eingebaute Cluster → 12 Gruppen mit identischen Größen, 100 %**, 0 falsch zusammengelegt, 0 übersehen; 3 Massen-Bilder mit **141 kleinen Gesichtern** → `clustern: False` | `openai/gpt-5.6-luna`: **2 Runden** — Runde 1 **nicht bestanden** (Eigner-Name an 5 Stellen), Runde 2 **BESTANDEN, „Abweichungen: keine."** |
| **N9b** Personen-Stufe echt rechnen | Eigenes venv `~/foto_sortierung/venv_gesicht` (opencv-contrib 5.0.0.93, onnxruntime 1.30.0), Modelle **232.589 B + 38.696.353 B**; `gesicht_erkennen.py` (**835 Zeilen**) + **80** Tests; Prüfbefehl **1175 passed, Exit 0** (Baseline 1095). Echt gemessen: **24 Bilder, 72 Gesichter auf 19 Bildern**, 0 Fehler, 88,4 s | `openai/gpt-5.6-luna`: **2 Runden** — Runde 1 **nicht bestanden** (Katalog-Eintrag, Fehlalarm), Runde 2 **BESTANDEN**. ⚠️ **Die Messzahlen dieses Schritts sind ungültig** (N9e: „72 Gesichter / 2 Gruppen (6 und 40) / 6 Referenzseiten" messen den Fehler) |
| **N9c** Mengen-Zweig am echten Foto | `ANTEIL_MIN` **0,0005 → 0,00001**; Prüfbefehl **1196 passed, Exit 0** (Baseline 1175). **30 echte Mengen-Bilder**: alt `gruppe 12 · leer 9 · unklar 9 · menge 0` → neu `gruppe 12 · leer 6 · unklar 11 · menge 1`; Referenzseiten mit `--ausschnitt`: **7 Seiten, 552.443 Bytes, 54 Kacheln alle 200×200** | `openai/gpt-5.6-luna`: **1 Runde — BESTANDEN, 0 Abweichungen** |
| **N9d** Gesichtsausschnitt verdrahten + breitere Messung | Prüfbefehl **1205 passed, Exit 0** (Baseline 1196, +9 Tests). **92 Bilder** (80 Mengen + 12 Kontrollen), **465 Gesichter**, 358,9 s, 0 Fehler: alt `gruppe 32 · leer 27 · menge 4 · unklar 29` → neu `gruppe 32 · leer 20 · menge 10 · unklar 30`; **nur Mengen-Bilder: 4 → 10 von 80 = 12,5 %**; Kontrollbilder **0 × `menge`**; Verdrahtung: **24 Referenzseiten, 186 Kacheln alle 200×200, 1.749.798 Bytes** | `openai/gpt-5.6-luna`: **3 Runden** — Runde 1 und 2 **nicht bestanden** (Belegskripte löschten Ausgabeordner per `rmtree`; Manifest-Formulierung falsch), Runde 3 **BESTANDEN**. ⚠️ **Die Vektor-Messzahlen sind ungültig** (N9e) |
| **N9e** Cluster-Schwelle am echten Bestand | **Der Befund war ein Fehler, nicht das Clustering** (Abschnitt 4). Prüfbefehl **1316 passed, Exit 0** (Baseline 1205). Belegt: `n9d` 465 Gesichter → **72 Vektorwerte** (57 von 57 Mehrgesicht-Bildern nur identisch), `n9b` 72 → **8** (15 von 15); Bild-interne Paare: **131 von 131 mit Distanz exakt 0,0000**; nach dem Fix: **465 von 465 verschiedene Vektorwerte**, Distanzen **0,5312 / 0,8280 / 1,0667** | `openai/gpt-5.6-luna`: **2 Runden** — Runde 1 **nicht bestanden** (Formulierung zu absolut; Gegenbeleg berechtigt → Doku nachgelegt), Runde 2 auf `4a296db` **BESTANDEN, 0 Abweichungen** |
| **N9f** Personen-Ergebnisse neu rechnen | `personen_verkettung.py` (**878 Zeilen**) + **117** Tests; Prüfbefehl **1433 passed, Exit 0** (Baseline 1316). Verkettung beziffert: dichte **Durchmesser 0,9032 = 2 × Schwelle** (größte Gruppe 22) gegen vollständig **0,4417**; Bodenwahrheit **0 von 131** Paaren unter 0,45. Neu-Rechnung: **12 Gruppen** (4,4,4,4,3,11,10,3,22,3,3,3), **12 Kennungen**, **16 Referenzseiten mit 74 Gesichtsausschnitten** (alle 200×200), **745.758 Bytes**; Schwelle bewusst **unverändert 0,45** | `openai/gpt-5.6-luna`: **1 Runde — BESTANDEN, 0 Abweichungen** (9 Punkte nachgerechnet) |
| **N9g** Verfahrenswechsel + breitere Stichprobe | Prüfbefehl **1449 passed, Exit 0** (Baseline 1433, +16 Tests). **192 Bilder** aus 40 Mengen-Anlässen + 40 Kontrollen: **188 erkannt, 142 mit Gesicht, 907 Gesichter, 1.086,6 s, 9 Fehlerzeilen**; **341 geclusterte Gesichter**; Arten `gruppe 74 · leer 41 · menge 20 · unklar 48`. Bodenwahrheit **210 Paare** (0,4925 / 0,8708 / 1,1422), **0 unter 0,45**. dichte **2 von 210** verschmolzen, vollständig **0 von 210**, mittelpunkt 11 von 210 → Produktion = **vollständige Verknüpfung** | `openai/gpt-5.6-luna`: **3 Runden** — Runde 1 **BESTANDEN**, Runde 2 **nicht bestanden** (2 berechtigte Doku-Abweichungen, korrigiert), Runde 3 auf `fcf4ad4` **BESTANDEN, „Abweichungen: keine."** |
| **N11** Fotos-Fragen am Handy | `foto_uebersicht.py` (**565 Zeilen, 98 Tests**) + Dienst (**389 Zeilen**) + Router (**103 Zeilen**) + Chat-Werkzeug + Selbsttest + Frontend-Zeile (**83** weitere Tests = **181**); Prüfbefehl **1687 passed, Exit 0** (Baseline 1503). Echte Datei `~/foto_sortierung/fotos_uebersicht.json`: **344.615 Bytes**, **2.127 Anlässe · 2.098 Event-Ordner · 9.430 Zeilen · 7.616 Züge · 1.146 ohne Datum · 11 Jahre · 48 Themen · 11 Kategorien**; Rauchtest am echten Bestand ohne Netz (200, `ok: true`, `limit` geklemmt) | `openai/gpt-5.6-luna`: **3 Runden** — Runde 1 und 2 **nicht bestanden** (4 + 3 Doku-Abweichungen), Runde 3 auf `9a213c9` **BESTANDEN, 0 Abweichungen** |

**Noch offen (Plan-Zeile N10 und N11):** die Übersichtsdatei liegt **noch nicht
auf dem Handy**; die Übertragung ist nicht Teil des Schritts. Der Schritt **N8**
(echtes Sortieren) ist gesperrt (Abschnitt 5).

---

## 3. Kosten

Alle Beträge sind echte Messwerte aus den genannten Quellen; die als
„Hochrechnung" oder „Schätzung" gekennzeichneten Zeilen sind **keine**
Messungen.

| Posten | Betrag | Quelle |
|---|---|---|
| Themen-Lauf N6 (2 Anlässe live) | 0,004354 $ + 0,002255 $ | `docs/changelog-2026-09-27-themen-vision.md` |
| Themen-Lauf N6 (Ausführer-Subagent, 3 Aufträge) | 0,038 $ + 0,017 $ + 0,021 $ ≈ **0,08 $** — **Schätzung**: Addition der im Journal genannten Beträge 0,038 + 0,017 + 0,021 USD (die Quelle schreibt „zusammen rund 0,08 $") | Journal N6 |
| N6b Stapel 1 (161 Anlässe) | **0,196610 USD** = **0,001221 USD je Anlass** | Journal N6b Stapel 1 |
| N6b-Restlauf (1.967 Anlässe, 5.954.092 ein / 370.113 aus Tokens) | **2,711510 USD**, 94,2 min | `docs/changelog-2026-09-27-themen-massenlauf.md` |
| Bestand gesamt (Summe `kosten_usd` in `themen.jsonl`, inkl. N5/N6/N6c) | **2,938515 USD** | `docs/changelog-2026-09-27-themen-massenlauf.md` |
| N6c Katalog-Messung 1 (44 Einträge) | flash-lite 0,058129 USD | Journal N6c |
| N6c Katalog-Messung 2 (53 Einträge, 161 Anlässe) | flash **0,209693 USD** / flash-lite **0,058977 USD** | Journal N6c |
| 108-Kachel-Anlass nach der Korrektur | 0,012073 USD | `docs/changelog-2026-09-27-themen-massenlauf.md` |
| Rauchtest N6b-Rest (3 Anlässe vorab) | 0,0051 USD | `docs/changelog-2026-09-27-themen-massenlauf.md` |
| Ausführer-Subagenten N6b-Rest / N6d / N6e / N7 | 0,003 $ / 0,026 $ / 0,036 $ + 0,032 $ / 0,033 $ + 0,007 $ | Journal, jeweiliger Eintrag |
| Ausführer-Subagenten N9a / N9b / N9c | 0,038 $ / 0,019 $ / 0,025 $ | Journal, jeweiliger Eintrag |
| Ausführer-Subagenten N9d / N9e / N9f | 0,008 $ / 0,041 $ + 0,022 $ / 0,026 $ | Journal, jeweiliger Eintrag |
| Ausführer-Subagenten N9g / N11 (zwei Subagenten) | 0,024 $ / 0,021 $ + 0,035 $ | Journal, jeweiliger Eintrag |
| OpenRouter-Konto, Nutzung gesamt | **142,143308068 USD** | `docs/changelog-2026-09-27-openrouter-zdr.md` (Stand 27.09.2026, ~02:42–02:57 UTC) |
| OpenRouter-Konto, Monat / Woche / Tag | 94,953563739 / 22,029042594 / 1,22627935 USD | `docs/changelog-2026-09-27-openrouter-zdr.md` |
| Datenschutz-Testanfragen OpenRouter (5 echte Aufrufe) | zusammen „deutlich unter 1 Cent" (0,000007 $ bis 0,000027 $ je Anfrage) | `docs/changelog-2026-09-27-openrouter-zdr.md` |
| **Hochrechnung N6b Stapel 1** auf 2.128 Anlässe (nicht gemessen) | gemini-2.5-flash **2,60 USD**, flash-lite **0,72 USD**, gemini-3.7-flash **5,64 USD** | Journal N6b Stapel 1 |
| **Hochrechnung N6c** auf die 1.967 wartenden Anlässe (nicht gemessen) | flash 2,56 USD, flash-lite 0,72 USD | Journal N6c |
| **Schätzung N6** für den Vollauf (nicht gemessen) | Größenordnung **2–4 $** mit gemini-2.5-flash, mit flash-lite etwa ein Drittel | Journal N6 |

Die Hochrechnung aus N6b Stapel 1 (2,56 USD) wurde im echten Restlauf um
**0,15 USD (≈ 6 %)** überschritten — im Changelog notiert, nicht beschönigt
(`docs/changelog-2026-09-27-themen-massenlauf.md`).

---

## 4. Der Nachtlauf hat einen echten Fehler gefunden (N9e)

Schritt N9e sollte die Cluster-Schwelle prüfen; gefunden wurde stattdessen ein
**Fehler in der Merkmalberechnung**. `cv2.FaceRecognizerSF.alignCrop` erwartet
die **volle 15-Werte-Detektionszeile** (60 Byte); an **drei** Stellen wurde nur
das 5×2-Landmarken-Array (40 Byte) übergeben. OpenCV prüft die Form nicht und
liest 20 Byte über den Puffer hinaus → **jedes Gesicht eines Bildes bekam
denselben Ausschnitt und damit denselben Vektor**
(`docs/changelog-2026-09-27-n9e-aligncrop-fehler.md`).

Belegt wurde das an einer Prüfsumme (an einem Bild mit 6 Gesichtern, Kennung
weggelassen: mit den Landmarken **6× dieselbe** Ausschnitt-Prüfsumme und
Mittelwert **0,00 (schwarz)**, mit der vollen Zeile 6 verschiedene Ausschnitte,
Mittel 103–158)
und an den gespeicherten Messdateien: **131 von 131** Bild-Paaren erkennbarer
Gesichter hatten **Distanz exakt 0,0000**; `n9d` hatte 465 Gesichter → nur
**72** Vektorwerte, `n9b` 72 → **8**. Der Fix liegt in
`tools/foto_sortierung/gesicht_erkennen.py` (`_merkmal`,
`gesichter_mit_detektor`) **und** in `backend/face_infer.py` (`_align_face` +
Aufrufer) — **der Produktionsweg war mit betroffen**; dazu kam ein **Wächter**:
≥2 bit-identische Merkmale in einem Bild ⇒ deutsche Fehlermeldung, leere Liste,
**kein stiller Durchlauf**. Nach dem Fix: dieselben 92 Bilder → **465 von 465
verschiedene Vektorwerte**, 0 Paare bei Distanz ≈ 0.

**Damit sind die Personen-Ergebnisse aus N9b und N9d ungültig** — die
Plan-Zeilen tragen die ⚠️-Korrektur, die betroffenen Changelogs
(`…gesicht-erkennen.md`, `…n9d-verdrahtung.md`) sind nur noch als Messung **des
Fehlers** zu lesen. Der stille Durchlauf hatte den Fehler zwei Nachtläufe lang
verdeckt.

---

## 5. Was gesperrt oder offen ist (wörtlich aus dem Plan)

Jeder Punkt nennt die Quelle `docs/plan-nachtlauf-2026-09-26.md` mit Zeile; die
Sperren und Zahlen sind aus dem Plan übernommen, Kürzungen sind mit „…" oder
[…] markiert.

* **N8 (echtes Sortieren) gesperrt** (Plan-Zeile 143, wörtlich; **eine**
  Änderung: der Eigner-Name wurde durch „dein Blick" ersetzt, als **[Name
  ersetzt]** gekennzeichnet): „**N7 ist bestanden** — der Plan steht (7.616
  Züge, 2.108 neue Ordner). Vor dem Echtlauf: **dein Blick auf die 39 sicheren
  Event-Vorschläge** und auf die **1.146 Dateien ohne Datum im Namen** (bleiben
  liegen, 12,2 %); der abgelehnte Anlass `2022-09-05_Anlass-02` (403) wartet
  weiter." Die 12,2 % sind der Anteil der 1.146 an den 9.430 Zeilen
  (`changelog-2026-09-27-sortieren-trockenlauf.md`).
* **Übergabe der Übersichtsdatei** `~/foto_sortierung/fotos_uebersicht.json` ans
  Handy (Plan-Zeile 151, wörtlich): „**Offen:** die Datei muss noch aufs Handy
  (Übertragung ist nicht Teil des Schritts)".
* **N18 — Upload-Stufe gesperrt** (Plan-Zeilen 970–983, wörtlich, [Name
  ersetzt]): „Die `upload`-Stufe (17,5 GB) bleibt **gesperrt**, bis …
  ausdrücklich freigibt." Der zugehörige Lösch-Schritt (erster echter Einsatz:
  12 Kopier-Reste, 581,3 MB) war als Plan-Schritt notiert — **gebaut wurde er
  nicht** (Abschnitt 6, Positivliste ohne Löschweg).
* **N16 (APK) gesperrt** (Plan-Zeilen 1001–1007, wörtlich, [Name ersetzt]):
  „**N16 bleibt gesperrt**, bis … es freigibt."
* **`2022-09-05_Anlass-02`** — vom Anbieter abgelehnt (403
  `PROHIBITED_CONTENT`), bewusst **keine Modellumgehung** (Plan-Zeile 139,
  `changelog-2026-09-27-themen-massenlauf.md`).
* **N12–N15, N17, N19, N20 als Kandidaten** (Plan-Zeilen 953–1020 und Journal
  27.09. ~23:20/~23:00; N15 ausdrücklich „Idee, noch nicht beauftragt",
  Plan-Zeile 1019).

---

## 6. Sicherheitsnetz und Schutz

* **pCloud wurde ausschließlich lesend benutzt** (`listfolder`, `getthumbs`) —
  in allen Schritten, in jeder Journal-Runde vermerkt.
* **`~/foto_sortierung/manifest.jsonl` existiert nicht** — **0 Buchungen**; der
  Trockenlauf bucht nichts (Journal N7, N9c, N9d, N9f; das Sicherheitsnetz selbst
  ist in `changelog-2026-09-27-rueckroll-sicherung.md` beschrieben).
* **Kein Löschwerkzeug**: der Werkzeugsatz kennt nur **Ordner anlegen, Datei
  verschieben, Ordner verschieben** (Positivliste `createfolder`, `renamefile`,
  `renamefolder`, `listfolder`); angelegte Ordner bleiben beim Rückrollen
  bestehen. `pcloud_rueckrollen.py` fährt Verschiebungen rückwärts
  (`--zeigen`, `--rueckwaerts N [--wirklich]`). Das Duplikate-Werkzeug
  (`pcloud_duplikate.py`) hat ebenfalls keinen Löschweg
  (`changelog-2026-09-27-rueckroll-sicherung.md`,
  `changelog-2026-09-27-duplikate-hashes.md`). Der geplante Lösch-Schritt für
  Duplikate (N18) war als Plan-Schritt notiert, **gebaut wurde er nicht**; das
  Löschen bleibt Sache des Nutzers (Journal).
* **Nicht überschreiben:** vor jedem echten Verschieben wird der Zielordner
  gelesen; liegt dort schon ein gleichnamiges Element, wird nichts verschoben
  (pCloud würde sonst atomar ersetzen = Datenverlust).
* **Crypto Folder unberührt** — „wird nie berührt (im Konto aktiv, tabu)"
  (Plan-Abschnitt „Sicherheitsnetz").
* **Bilder nie auf Platte:** Originale nur im Arbeitsspeicher, geschrieben
  wurden nur Textzeugnisse (Vektorzeilen, Berichte) und die Produkte der
  Personenstufe — alles außerhalb des Repos unter `~/foto_sortierung/`.
* **Biometrie bleibt lokal:** Gesichts-Vektoren und Katalog verlassen den PC
  nie (nicht ins Repo, nicht an ein Fremd-LLM; `CLAUDE.md`, Abschnitt „Sicherheit:
  Fotos, Gesichter, Menschenmengen").
* **Original-Sortierschlüssel unverändert** (`md5 70642d2988b6e38ff417561ccf870ba8`
  — lokale Prüfsumme der Eingabedatei, kein Zugangswert),
  geschrieben wurde nur die Kopie `sortierschluessel_themen.csv`
  (`changelog-2026-09-27-themen-massenlauf.md`).
* **Kein Geheimnis in Ausgaben:** der pCloud-Token wird gelesen, aber nie
  ausgegeben oder geloggt (per Test belegt,
  `changelog-2026-09-27-rueckroll-sicherung.md`).

---

## 7. Lehren (Pitfalls)

1. **MSYS-Pfad an natives Python:** `/c/Users/…` an ein natives
   Windows-Python gegeben → der Ordner landete unter `C:\c\Users\…`. Regel:
   an native Werkzeuge **immer** `C:/…`-Pfade, nie `/c/…` (Journal N6c, kostete
   einen Doppel-Lauf; Daten per Kopie gerettet, nichts gelöscht).
2. **„nie `git add -A`":** ein fremder Sammelcommit im selben Arbeitsbaum nahm
   gestagte Dateien dieses Laufs mit (falsch beschriftet, inhaltlich nichts
   verloren) — Regel in `AGENTS.md`: `git commit --only <Pfade>` (Journal
   27.09. ~05:20, erneut `751280a`).
3. **Wirkungslose Assertion:** ein Test mit `… or True` prüfte nichts; ersetzt
   durch eine echte Prüfung + 7 neue Tests (Journal N7, Prüfer-Runde 1).
4. **Cache-Bump muss neuer sein als die Änderung:** `app.js?v=20260927A` war
   älter als die Änderung → auf `?v=20260927B` gesetzt (Journal N11; genau der
   Fehler, den `CLAUDE_EXTENDS.md` §5 verhindern soll).
5. **Der fremdfamiliäre Prüfer findet die Dokuzahlen:** bei N6, N6c, N6e, N7,
   N9d, N9g und N11 waren es ausschließlich Doku-Abweichungen (falsche Zählstände,
   irreführende Zahlen, unklare Bezeichnungen), die `openai/gpt-5.6-luna` vor dem
   Commit fand — der Nutzen des getrennten Kontexts war messbar.

---

## 8. Prüfbefehl

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
```

* **Ergebnis (vom Planer frisch gefahren):** **1687 passed, Exit 0**
  (Baseline **1503**, Plan-Zeile N11).
* Zusätzlich in N11: `node --check app.js` Exit 0,
  `node frontend/tests/test_selbsttest.js` „alle Prüfungen grün" (Journal N11).
* Die Prüfbefehls-Zeile im Bereichs-Regelwerk (`../CLAUDE_EXTENDS.md`) wurde auf
  diesen Stand gezogen.

---

## Quellen

Journal (Schritt-Tabelle + fortlaufende Einträge):
`docs/plan-nachtlauf-2026-09-26.md` (1.416 Zeilen).

Changelogs:
`docs/changelog-2026-09-27-foto-themen.md`,
`docs/changelog-2026-09-27-themen-vision.md`,
`docs/changelog-2026-09-27-themen-stapel1.md`,
`docs/changelog-2026-09-27-themen-katalog.md`,
`docs/changelog-2026-09-27-themen-massenlauf.md`,
`docs/changelog-2026-09-27-zielkategorien.md`,
`docs/changelog-2026-09-27-kategorien-bestand.md`,
`docs/changelog-2026-09-27-event-abgleich.md`,
`docs/changelog-2026-09-27-sortieren-trockenlauf.md`,
`docs/changelog-2026-09-27-personen-verfahren.md`,
`docs/changelog-2026-09-27-gesicht-erkennen.md`,
`docs/changelog-2026-09-27-mengen-zweig.md`,
`docs/changelog-2026-09-27-n9d-verdrahtung.md`,
`docs/changelog-2026-09-27-n9e-aligncrop-fehler.md`,
`docs/changelog-2026-09-27-n9f-verkettung.md`,
`docs/changelog-2026-09-27-n9g-verfahren.md`,
`docs/changelog-2026-09-27-n11-uebersicht-datei.md`,
`docs/changelog-2026-09-27-n11-uebersicht-endpunkt.md`,
`docs/changelog-2026-09-27-rueckroll-sicherung.md`,
`docs/changelog-2026-09-27-rueckrollwerkzeug.md` (als **überholte** Fassung
gekennzeichnet),
`docs/changelog-2026-09-27-duplikate-hashes.md`,
`docs/changelog-2026-09-27-openrouter-zdr.md` (Kostenzahlen des Kontos).
