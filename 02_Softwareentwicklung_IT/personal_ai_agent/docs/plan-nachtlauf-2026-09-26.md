# Nachtlauf 26./27.09.2026 — Fotos, Videos, Personen (autonom)

> **Auftrag:** Sebastian (26.09.2026, ~04:30): „Wir wollen eine Langzeit-Session
> bauen … dass du das alles abarbeitest. Ich gehe jetzt für 4–5 Stunden schlafen.
> Arbeite ohne Unterbrechung und komm nicht mit Fragen, sondern entscheide
> selbst. […] Wenn du unsicher bist: **nichts löschen**, nur verschieben,
> sortieren — oder erstmal nur den Upload-Ordner sortieren. Wenn was schiefläuft,
> müssen wir es zurückstellen können."
>
> **Regeln:** `AGENTS.md` → Abschnitt „Dauerlauf / Nachtarbeit (autonom)".
> Kernpunkte: keine Rückfragen, jeder Schritt verifiziert + einzeln committet,
> **nie löschen**, jede Schreib-Operation ins **Manifest** (rückholbar),
> idempotent bauen, billigste Wege zuerst.

## Rollen: Planer → Ausführer → Prüfer (getrennte Kontexte, verbindlich)

Nach `CLAUDE_EXTENDS.md` §6.6 und dem Everlast-Kanon (Punkte 1–3): **nie** plant,
führt aus und prüft derselbe Kontext.

| Rolle | Wer | Aufgabe im Nachtlauf |
|---|---|---|
| **Planer** | Hauptkontext (dieser Chat) | Diesen Plan als Datei schreiben, Reihenfolge + Prüfkriterien festlegen, committen. **Kein** Bauarbeit-Selbstlauf am eigenen Werk. |
| **Ausführer** | je Schritt ein **Subagent** (`delegate_task`) | genau **einen** Planschritt umsetzen, Code + Tests + Doku, **keine** git-Befehle |
| **Prüfer** | **frischer** Subagent, **anderes Modell als der Ausführer** | gegen den Plan prüfen, Prüfbefehl selbst ausführen, Abweichungen benennen, „bestanden/nicht bestanden" |

**Ablauf je Schritt:** Planer beschreibt → Ausführer baut → **Prüfer prüft** →
Planer committet (nur bei „bestanden"). Ein Schritt ohne Prüfer-Abnahme gilt als
**offen**, auch wenn er gebaut ist.

**Warum das im Nachtlauf doppelt zählt:** Ohne getrennten Prüfer bestätigt der
Bauende seine eigene Annahme — im Nachtlauf sieht Sebastian das Ergebnis erst
Stunden später. Fehler, die ein frischer Kontext findet, kosten Minuten; Fehler,
die bis zum Morgen liegen, kosten den ganzen Lauf.

## Modell-Mix (Anmerkung Sebastian: „verschiedene Modelle miteinander kombinieren")

**Befund:** `config.yaml` hat unter `delegation:` nur `max_iterations` — **kein**
Modell gepinnt. Damit erben alle Subagenten das Hauptmodell
(`deepseek/deepseek-v4.1-flash`). Sebastian hat recht: das ist noch keine
Vielfalt. Wird bewusst **pro Rolle** gesetzt:

| Rolle | Modell | Weg | Warum |
|---|---|---|---|
| **Planer (Denken)** | `gpt-5.6-terra` | **nur über die Codex CLI** (ChatGPT-Konto, `codex exec --model gpt-5.6-terra --sandbox read-only`) | stärkstes verfügbares Denken, **keine Token-Rechnung** — nur Volumen. Denken ist selten, teuer darf sein. **⚠️ 27.09. gesperrt:** Kontingent erschöpft — live „You've hit your usage limit … try again at Oct 15th, 2026 9:32 PM" (2 Sitzungen liefen 05:00 + 07:43 noch; danach zu) |
| **Planer-Ersatz, solange gesperrt** | Hauptagent `deepseek-v4.1-flash` | direkt (Hauptkontext) | Planung macht der Hauptagent selbst; die Qualität kommt aus dem **fremdfamiliären Prüfer**, nicht aus dem Planer. Zweitweg **Claude Code geprüft und ausgefallen**: 2.1.83 antwortet `Exit 1 · 401 authentication_error: „OAuth access token has expired. Re-authenticate to continue."` → braucht Sebastians Anmeldung (`claude` interaktiv bzw. `claude setup-token`) |
| **Ausführer (Masse)** | `deepseek-v4.1-flash` | Hermes-Subagenten | **Cache 0,001 $/Mio** → lange Sitzungen kosten fast nichts |
| **Ausführer (schwerer Coding-Block)** | `gpt-5.6-terra` | Codex CLI, `--sandbox workspace-write` | starke Umsetzung ohne Zusatzkosten über das Konto — **derzeit ebenfalls gesperrt** (Kontingent, s. o.); solange übernimmt der Hauptagent/Subagent mit `deepseek-v4.1-flash` |
| **Prüfer (andere Familie!)** | `gpt-5.6-luna` (0,20/1,20) oder `z-ai/glm-5.2` (0,65/2,04) | `hermes -z "<Auftrag>" -m <Modell>` | Fehler, die eine Familie macht, findet dieselbe Familie nicht |

**Gemessene Preise (OpenRouter, je 1 Mio Token, 27.09.2026, live abgefragt):**

| Modell | Eingang | Ausgang | Cache | Kontext |
|---|---|---|---|---|
| `deepseek-v4.1-flash` | **0,035** | 0,290 | **0,001** | 1,05 M |
| `deepseek-v4-flash-0731` | **0,021** | 0,320 | 0,016 | 1,31 M |
| `openai/gpt-5.6-luna` | 0,200 | 1,200 | 0,020 | 1,05 M |
| `openai/gpt-5.6-terra` | **2,000** | **12,000** | 0,200 | 1,05 M |
| `google/gemini-3.7-flash` | 0,750 | 3,750 | 0,075 | 1,05 M |
| `z-ai/glm-5.2` | 0,650 | 2,042 | 0,121 | 1,05 M |

**Konsequenz (Sebastians Einwand, bestätigt):** Terra über OpenRouter wäre
**57× teurer im Eingang / 41× teurer im Ausgang** als DeepSeek V4.1 Flash —
für einen Ausführer-Schritt (~200 k rein, ~50 k raus) sind das **≈ 1,00 $ statt
≈ 0,02 $**. Deshalb: **Terra ausschließlich über das ChatGPT-Konto (Codex CLI)**,
niemals über OpenRouter als Ausführer.

**Datenschutz-Grenze (bleibt hart):** Nur **reiner Code** geht an Codex.
Chat-Archiv, Fotos, Erinnerungen, `.env`, Bewerbungen bleiben bei
Hermes/DeepSeek (Skill `ai-datenschutz-regeln`).

## Qualität halten, obwohl billig ausgeführt wird (Sebastians Kernfrage)

Sebastian (27.09.): „Wir sind auf die Ebene DeepSeek V4.1 Flash gegangen — wir
wollen es günstiger machen, aber von der Qualität fast gleich hoch."

**Die Logik:** Qualität kommt **nicht** aus jedem ausgeführten Token, sondern aus
drei Dingen — und die kosten fast nichts:

1. **Guter Plan vom starken Modell.** Terra (Codex-Konto) bzw. Claude Code
   zerlegen die Aufgabe in einen **präzisen Auftrag**: welche Datei, welches
   Verhalten, welches Prüfkriterium. Ein billiger Ausführer mit klarem Auftrag
   liefert fast dasselbe wie ein teurer mit vagem Auftrag.
2. **Prüfer aus einer anderen Familie.** Die teure Fehlerquote entsteht dort, wo
   niemand gegenliest. Ein fremdfamiliärer Prüfer (`gpt-5.6-luna`, `glm-5.2`,
   `codex review`) kostet Cent-Beträge und fängt genau die Fehler, die der
   Ausführer selbst nicht sieht.
3. **Prüfbefehl als Tor.** Kein Commit ohne Exit-Code 0 — die Wahrheit liegt im
   Befehl, nicht im Gefühl des Ausführers.

**Wo NICHT gespart wird (harte Schritte bleiben beim starken Modell):**
Architektur-Entscheidungen, knifflige Bugs (Race Conditions, Datenverlust-Risiko),
Sicherheits-/Datenschutzfragen, Umbauten an bestehender Logik. Diese Aufgaben sind
selten und teuer im Kopf — aber billig in der Rechnung, wenn sie wenige Male laufen.

**Faustregel:** *Denken und Prüfen = stark, Ausführen = billig.* Wer die Ausführung
mit dem starken Modell fährt, zahlt das 40–50-Fache für Arbeit, die der Prüfer
ohnehin nachkontrolliert.

## Entscheidungen, die ich selbst treffe (statt zu fragen)

1. **Zielstruktur:** `Agent/Fotos/<Jahr>/<Thema>/` (Sebastians Vorgabe B) — und
   **verschieben statt kopieren** aus dem Upload-Ordner. Grund: pCloud kann das
   in Millisekunden (nur Metadaten), es spart 45 GB Upload-Verkehr, und es ist
   über das Manifest **umkehrbar** (zurück in den Quellordner).
2. **Erinnerungs-Ablage:** eigene Datei außerhalb des Repos
   (`~/foto_erinnerungen/erinnerungen.jsonl`), getrennt vom Gedächtnis-Dienst,
   Personen über **stabile Kennungen** (`Person_001` …). Text im Wortlaut,
   Versionen über `history`.
3. **Personen-Rechnen:** Rechnung auf dem PC, **Benennen** später auf dem Handy
   im Quiz (dort liegen Katalog, Referenzen und die Fragen).
4. **Kostenschutz:** Vorschaubilder (120×120 über die API) für die Themen-Stufe;
   Gesichtserkennung braucht Originale → **Jahres-Stapel**, erst Stichprobe
   messen, dann Vollauf.

## Sicherheitsnetz (vor der ersten Schreib-Operation fertig)

* **Manifest:** `~/foto_sortierung/manifest.jsonl` — je Zeile
  `{zeit, art: movefolder|movefile|createfolder, von_id, nach_id, name, datei_id}`.
  Damit kann jede Aktion **rückwärts** gefahren werden.
* **Rückroll-Werkzeug:** `tools/pcloud/pcloud_rueckrollen.py`
  (`--zeigen` listet, `--rueckwaerts N` macht die letzten N Aktionen rückgängig).
* **Keine Löschbefehle** im gesamten Werkzeugsatz — `deletefile`/`deletefolder`
  werden nicht implementiert, auch nicht „zur Sicherheit".
* **Probelauf-Schalter:** jedes Schreib-Werkzeug hat `--trocken` (zeigt nur, was
  es täte) und läuft zuerst mit `--trocken`.
* **Crypto Folder** wird nie berührt (im Konto aktiv, tabu).

## Schritte (in dieser Reihenfolge, jeder mit Prüfkriterium)

| # | Schritt | Prüfkriterium | Stand |
|---|---|---|---|
| N1 | Cloud-Service (Hintergrund-Bau) **selbst prüfen** + committen | `pytest tests/ -q` grün; Rauchtest-Zahlen aus dem Bericht nachgefahren | ✅ **500 Tests grün** (selbst gefahren), Rauchtest-Zahlen geprüft (18 Einträge, 4185 Bytes Vorschaubild), committet |
| N2 | **Selbstheilung + Rollback-Werkzeug** committen (Selbstheilung schon gebaut: `pcloud_token_erneuern.py`) | Prüfmodus sagt „gültig"; Rückroll-Tool mit Tests | 🔄 Selbstheilung committet (`3cad5ae`, live belegt); **Rückroll-Werkzeug läuft als Subagent** (`deleg_609a78cd`) |
| N3 | **Schlüssel aufs Handy** (USB) + Selbsttest-Zeile „pCloud" + `start-termux.sh` übernimmt die Datei automatisch | `curl` am Handy liefert `pcloud: verbunden`; JS-Tests grün | ✅ **gebaut + gepusht (27.09. ~10:20, Hauptagent mit Sebastian)** — Übergabedatei per Kabel aufs Handy (`/sdcard/Download/pcloud_token.txt`, 81 B, nur Längen geprüft, nie Werte); Automatik-Block + Selbsttest-Zeile + Frontend-Zeile in Commit `6b08e67`, **665 Tests grün, Exit 0** (selbst gefahren), Frontend 15/15; Sicherung `.env.vorher`, Übergabedatei wird nach Übernahme gelöscht, `.gitignore` schützt `*.env.vorher`. **Offen (Handy):** Übernahme beim Widget-Tipp noch nicht beobachtet — Sebastian pullt, tippt **zweimal** und sieht im Selbsttest die pCloud-Zeile |
| N4 | **Themen-Stufe Werkzeug**: `tools/foto_sortierung/foto_themen.py` — Ordnerbaum je Ebene, Vorschaubilder in Stapeln, Kontaktbögen bauen | Werkzeug-Tests grün; Kontaktbogen-Datei entsteht (Größe/Kacheln belegt) | ✅ **Prüfbefehl 525 grün** (500 + 25 neue, selbst gefahren); 2 Kontaktbögen live gebaut (10 Kacheln/62.566 B, 36 Kacheln/262.437 B, Pixel-Nummern belegt); Idempotenz live (2. Lauf: 0 geholt) |
| N5 | **Stichprobe Kosten** (1 Bogen → Vision) → Thema je Anlass | gemessene Kosten pro Bogen notiert, bevor der Vollauf startet | ✅ **bestanden (27.09.)** — siehe Journal: Nummern 1–36 einwandfrei lesbar, Thema je Bogen erkennbar, unbrauchbare Kacheln werden benannt |
| N6 | **Themen je Anlass** (Stapel) → Zuordnung im Sortierschlüssel | Anzahl Anlässe je Jahr/Thema; Stichprobe nachgesehen | ✅ **bestanden (27.09.)** — Werkzeug `tools/foto_sortierung/foto_themen_vision.py` (ein Vision-Aufruf je Anlass), **628 Prüfungen grün**, 59 eigene Tests; 2 Anlässe live gemessen (36 Kacheln → „Veranstaltung Publikum Bühne", 0,004354 $; 10 Kacheln → „Konzert Band Auftritt", 0,002255 $); Prüfer `gpt-5.6-luna` sagt „bestanden" (6. Runde). **Offen als N6b:** Massenlauf über alle 2.128 Anlässe (Bögen bauen + Themen setzen) |
| N6c | **Themen-Katalog** (feste Liste 40–60 Einträge) + Prompt, der nur daraus wählt; die 161 gelaufenen Anlässe nachziehen (`--wiederholen`); **Modellvergleich am Katalog** (flash vs. flash-lite) | Werkzeug-Tests grün; Stichprobe zeigt ≤ Katalog-Themen; flash-lite-Qualität belegt | ✅ **bestanden (27.09.)** — `themen_katalog.py` mit **53 Einträgen** (Version 3), Prompt wählt nur daraus, `Sonstiges` als Rückfall; Prüfbefehl **657 grün**; die 161 Anlässe beider Modelle live gemessen (flash 0,209693 USD / 100 % Katalog-Treffer / 14 × Sonstiges = 8,7 %; flash-lite 0,058977 USD / 99,4 % / 18 × Sonstiges); **Sichtprobe 6 Bögen: flash 4 : 2 flash-lite** → **flash** für den Massenlauf; Prüfer `gpt-5.6-luna` (1 Beanstandung an einer Zahl, korrigiert) |
| N6b | **Massenlauf:** Bögen je Jahr bauen, dann Themen setzen, kleinster Stapel zuerst | Anzahl Anlässe je Jahr/Thema; Stichprobe nachgesehen | ✅ **bestanden (27.09.)** — **Bestand vollständig:** 2.128 Anlässe, **2.127 mit Katalog-Thema**, 48 Themen genutzt, 242 × `Sonstiges` (11,4 %). Restlauf 2026/2025/2022/2024/2023: 1.967 Anlässe, 1.962 gesehen, 2 Fehlschläge, 7.722 Kacheln, **5.954.092 ein / 370.113 aus Tokens = 2,711510 USD**, 94,2 min. Dabei ein **echter Codefehler** gefunden und behoben (`MAX_TOKENS = 4000` schnitt den 108-Kachel-Bogen ab → `max_tokens_fuer(anzahl)`; derselbe Anlass läuft mit **4.420** Ausgabe-Tokens durch). **Ein Anlass bleibt bewusst offen:** `2022-09-05_Anlass-02` wird vom Anbieter abgelehnt (403 `PROHIBITED_CONTENT`) — keine Modellumgehung. Prüfbefehl **671 grün, Exit 0**; Prüfer `gpt-5.6-luna` (3 Punkte, 2 berechtigt → Zahlen/Doku korrigiert). Doku: `docs/changelog-2026-09-27-themen-massenlauf.md` |
| N6d | **Zielkatalog aus Sebastians eigenen Ordnern** (`Bilder & Videos`: 18 Kategorien, 113 Unterordner): Zielordner sind **seine** Kategorien, nicht die erfundenen 53 Motive. Werkzeug liest den Bestand nur lesend (`~/foto_sortierung/kategorien.json`) | Kategorien-Liste deckt alle Jahre ab; Motiv-Thema bleibt nur Motiv-Erkennung | ✅ **bestanden (27.09.)** — `tools/foto_sortierung/foto_kategorien.py` (855 Zeilen) + **38** neue Tests; Übersetzung Motiv-Thema (53) → **Bucket** (11, im Code) → **echter Ordner** (lokal gebunden, `~/foto_sortierung/kategorie_zuordnung.json`); Zielpfad `Agent/Fotos/<Jahr>/<Kategorie>/<Event>`; Prüfbefehl **709 grün, Exit 0**; live `--zeigen`: **18 Kategorien · 113 Unterordner · 10 mit Unterordnern · 11 Buckets (10 gebunden, 1 × null)**, nichts geschrieben. Doku: `docs/changelog-2026-09-27-zielkategorien.md` |
| N6e | **Event-Abgleich:** je Datums-Block gegen bestehende Event-Ordner prüfen (Jahr/Monat im Namen) → **Vorschlag** „Ordner X" statt Neubau; Muster: `Jahr + Ort` (Urlaub/Ausflüge), `Jahr_Monat + Ereignis` (Konzerte), `Jahr + Person` (Familie/Freunde) | Trefferquote an einer Stichprobe gemessen; Vorschläge nachvollziehbar | ✅ **bestanden (27.09.)** — `tools/foto_sortierung/event_abgleich.py` (1.060 Zeilen, Nachbarmodul von `foto_kategorien`) + **51** eigene Tests; Prüfbefehl **760 grün, Exit 0** (Baseline 709; selbst gefahren). Live nur lesend: **2.134 Anlässe · 39 Vorschläge = 1,8 %** (tag 10, monat 29) · **600 schwache Hinweise** (jahr 495, spanne 105) · 2.095 ohne Vorschlag (276 davon: Kategorie fehlt im Bestand) · **112 von 113** Unterordnern über gebundene Buckets erreichbar. **Verschärfte Regel nach eigener Sichtprobe:** nur `tag`/`monat` ergeben einen Vorschlag, `jahr`/`spanne` nur mit `--auch-schwach` (vorher 639 Vorschläge, davon 600 untauglich). Prüfer `gpt-5.6-luna`, 2 Runden: Runde 1 NICHT BESTANDEN (echte Ordnernamen im Repo, Zahl 109 → 112; beides korrigiert, real 8 statt 4 Namen), Runde 2 nur noch 3 Resttreffer = blanke Kalenderjahre → als Fehlalarm begründet. Doku: `docs/changelog-2026-09-27-event-abgleich.md`, Feinauftrag `docs/auftrag-n6e-event-abgleich.md` |
| N7 | **Probelauf `--trocken`** des Sortierens (Ordner anlegen + verschieben) | Liste der geplanten Züge, gegengeprüft | ✅ **bestanden (27.09.)** — `tools/foto_sortierung/foto_sortieren.py` (1.149 Zeilen) + **119** eigene Tests; Prüfbefehl selbst gefahren **879 passed, Exit 0** (Baseline 760). Live nur lesend, `listfolder` über 7 Quellordner: **9.430 Zeilen · 2.127 Anlässe · 7.616 Züge (alle mit Dateikennung)** · Doppelungen **1.534 in der CSV** (866 ohne Anlass-ID, **668** in geplanten Anlässen übersprungen) · **1.146 Zeilen ohne Anlass-ID** (kein Datum im Namen) · 0 ohne Thema / 0 ohne Jahr · **2.108 Ordner neu, 82 vorhanden · 2.088 Events neu, 39 wiederverwendet** (= die 39 sicheren Vorschläge aus N6e) · 11 Kategorien. Plan `~/foto_sortierung/sortierplan.json`; Manifest **0 Einträge**, Original-CSV unverändert. Prüfer `gpt-5.6-luna`, 2 Runden: Runde 1 NICHT BESTANDEN (Doppelungs-Zahl irreführend: nur 668 statt 1.534 genannt; wirkungslose Assertion `or True`) → beides behoben, Runde 2 **BESTANDEN, „Abweichungen: keine."** Doku: `docs/changelog-2026-09-27-sortieren-trockenlauf.md`, Feinauftrag `docs/auftrag-n7-sortieren-trockenlauf.md` |
| N8 | **Sortieren echt** (Jahr für Jahr, kleinster Stapel zuerst) | Manifest vollständig; Stichprobe am Zielordner per API geprüft | ⬜ **N7 ist bestanden** — der Plan steht (7.616 Züge, 2.108 neue Ordner). Vor dem Echtlauf: **Sebastians Blick auf die 39 sicheren Event-Vorschläge** und auf die **1.146 Dateien ohne Datum im Namen** (bleiben liegen, 12,2 %); der abgelehnte Anlass `2022-09-05_Anlass-02` (403) wartet weiter |
| N9a | **Personen-Verfahren** (kein Bild nötig): Mengen-Filter, Clustering, stabile Kennungen, Referenzseiten — Werkzeug rechnet nur auf **Vektoren** (Format von `face_infer.py`), ohne cv2/sklearn | Cluster-Anzahl je Stichprobe; Referenzseiten vorhanden; **Test, dass ein Massenfoto keine Gruppe erzeugt** | ✅ **bestanden (27.09.)** — `tools/foto_sortierung/personen_cluster.py` (1.510 Zeilen) + **216** Tests (`backend/tests/test_personen_cluster.py`, 1.590 Zeilen, alles offline); Prüfbefehl selbst gefahren **1095 passed, Exit 0** (Baseline 879). Live **synthetische** Stichprobe: 12 eingebaute Cluster → 12 Gruppen mit identischen Größen, 100 %, 0 falsch zusammengelegt, 0 übersehen, Rauschen verworfen; 3 Massen-Bilder (141 kleine Gesichter) → `clustern: False`; Idempotenz über die CLI belegt (2. Lauf 0 neue Seiten, dieselben Kennungen). Prüfer `gpt-5.6-luna`, 2 Runden: Runde 1 NICHT BESTANDEN (Eigner-Name an 5 Stellen) → korrigiert, Runde 2 **BESTANDEN, „Abweichungen: keine."** Doku: `docs/changelog-2026-09-27-personen-verfahren.md`, Feinauftrag `docs/auftrag-n9-personen-verfahren.md` |
| N9b | **Personen-Stufe echt rechnen**: Modelle (YuNet + SFace) auf den PC holen bzw. auf dem Handy rechnen lassen, `cv2`/`onnxruntime` in **eigenem** venv (Projekt-venv bleibt unberührt), Gesichter in Jahres-Stapeln erkennen, `kachel_holen` an den echten Weg anstecken (pCloud/Handy) | echte Cluster-Anzahl je Stichprobe (Jahres-Stapel), Referenzseiten mit echten Gesichtern, Massen-Regel am echten Foto belegt | ✅ **gebaut + echt gemessen (27.09.)** — Modellweg am PC: **eigenes venv** `~/foto_sortierung/venv_gesicht` (opencv-contrib 5.0.0.93, onnxruntime 1.30.0; Projekt-venv unberührt), Modelle **öffentlich aus dem OpenCV-Zoo** nach `~/foto_sortierung/ml_models/` (232.589 B + 38.696.353 B). Werkzeug `tools/foto_sortierung/gesicht_erkennen.py` (835 Zeilen) + **80** Tests (850 Zeilen) + echte pCloud-Kachelquelle; Prüfbefehl selbst gefahren **1175 passed, Exit 0** (Baseline 1095). **Echte Messung:** 24 Bilder (16 aus 2020 + 8 aus dem bilderstärksten Mengen-Anlass), **72 Gesichter auf 19 Bildern**, 0 Fehler, 88,4 s; N9a darauf: `leer 8 · gruppe 12 · menge 0 · unklar 4`, **2 Gruppen (6 und 40)**, **6 Referenzseiten mit echten Gesichtsausschnitten** (59–102 KB), 2. Lauf **0** neue Dateien. **Befund:** Mengen-Regel greift, aber über den Zweig `leer` — die winzigen Gesichter liegen **unter** `ANTEIL_MIN`, der Zweig `menge` wurde am echten Foto **nicht** erreicht (Entscheidung: Schwelle nicht angetastet → Kandidat **N9c**). Prüfer `gpt-5.6-luna`: Runde 1 NICHT BESTANDEN wegen eines Katalog-Eintrags im Changelog (seit `92b04c3` im Repo = Fehlalarm), Runde 2 **BESTANDEN**. Doku: `docs/changelog-2026-09-27-gesicht-erkennen.md`, Auftrag `docs/auftrag-n9b-gesicht-erkennen.md`. ⚠️ **Korrektur 27.09. (N9e): die Zahlen dieses Schritts sind UNGÜLTIG** — die Merkmalberechnung war fehlerhaft (ein Vektor je **Bild** statt je Gesicht, `alignCrop` bekam die falsche Form); „72 Gesichter / 2 Gruppen (6 und 40) / 6 Referenzseiten" messen den Fehler, nicht das Clustering. Neurechnung als **N9f** |
| N9c | **Mengen-Zweig am echten Foto erreichbar machen** (`ANTEIL_MIN` mit Messung prüfen) + `kachel_quelle` um den **Gesichtsausschnitt** ergänzen (in-memory, statt ganzes Foto) | `menge`-Zweig an echten Mengen-Fotos erreicht; Kacheln zeigen Gesichter | ✅ **bestanden (27.09.)** — `ANTEIL_MIN` **0,0005 → 0,00001** (gemessen: das alte Tor verwarf **echte** Funde, kleinste echte Detektion 0,000145 bzw. 0,000022); `kachel_quelle(..., ausschnitt=True)` schneidet in-memory um das Gesicht (**nur PIL**, Rand 0,45 × bbox, Rückfall aufs ganze Foto statt Abbruch, reine Funktion `ausschnitt_rechnen`), CLI `--ausschnitt`. Prüfbefehl selbst gefahren **1196 passed, Exit 0** (Baseline 1175); **30 echte Mengen-Bilder**: vorher `gruppe 12 · leer 9 · unklar 9 · menge 0` → nachher `gruppe 12 · leer 6 · unklar 11 · menge 1` (**„1 von 30"**, nicht schöngeredet); `gruppe` unverändert = keine Regression. **Offen als N9d:** `bbox` im Vektorzeilen-Lauf verdrahten (`kachel_quelle` liest `fileid`, N9a-Einträge tragen `bild_id`) + N9b-Lauf mit neuem `ANTEIL_MIN` wiederholen; `MENGE_ANZAHL = 6` bleibt unangetastet (N9a-Beschluss, braucht eigene Messung). Prüfer `gpt-5.6-luna`: **BESTANDEN, 0 Abweichungen**. Doku: `docs/changelog-2026-09-27-mengen-zweig.md`, Auftrag `docs/auftrag-n9c-mengen-zweig.md` |
| N9d | **Gesichtsausschnitt verdrahten + N9b-Messung wiederholen**: `bbox`/`bild_id` in der Kachelquelle zusammenführen (N9a-Einträge tragen `bild_id`, `kachel_quelle` liest `fileid`), N9b-Vektorlauf mit dem neuen `ANTEIL_MIN` über eine **breitere** Mengen-Stichprobe | Ausschnitt-Kacheln messbar schärfer; `menge`-Anteil über mehr als 30 Bilder beziffert (nicht mehr „1 von 30") | ✅ **bestanden (27.09.)** — `_fileid_von` liest `fileid`, sonst **`bild_id`** (N9a-Einträge gehen **ohne Um-Mappen** in die echte Kachelquelle; kein Hack mehr nötig), neue reine `kachelquelle_hinweis(ausschnitt)` sagt wahrheitsgemäß, dass `--ausschnitt` im **Vektorzeilen-Lauf wirkungslos** ist (vor dem Download keine `bbox` bekannt) und wo er wirklich schneidet; Prüfbefehl selbst gefahren **1205 passed, Exit 0** (Baseline 1196, +9 neue Tests). **Breite Messung: 92 Bilder** (80 aus 8 Mengen-Anlässen, 12 Kontrollbilder), 465 Gesichter, 0 Fehler, 358,9 s: alt `0,0005` → `gruppe 32 · leer 27 · menge 4 · unklar 29` gegen neu `0,00001` → `gruppe 32 · leer 20 · **menge 10** · unklar 30`; **nur Mengen-Bilder: 4 → 10 von 80 = 12,5 %** (statt „1 von 30" = 3,3 %), Kontrollgruppe **0 × `menge`**, `gruppe` in beiden Schwellen **unverändert 32**. **Verdrahtung live belegt:** 24 Referenzseiten, **186 Kacheln, alle 200×200** aus `bild_id` + `bbox` ohne Um-Mappen, Kachel-Abstand zum selbst gerechneten Ausschnitt **1,755–3,116** (JPEG-Verlust) gegen **68,954–76,192** zum ganzen Foto → die Kachel ist wirklich der Gesichtsausschnitt; 2. Lauf 0 neue Dateien. **Ehrlicher Nebenbefund:** das DBSCAN-artige Clustering bündelt die 189 Gesichter der `gruppe`-Bilder zu **einer** Gruppe — bei dichtem Verfahren erwartbar, aber am echten Bestand ungeprüft → Kandidat **N9e** (Schwelle mit Bodenwahrheit messen). Prüfer `gpt-5.6-luna`, drei Runden: Runde 1 und 2 NICHT BESTANDEN (Belegskripte löschten Ausgabeordner per `rmtree` → jetzt verweigern sie mit Exit 2; meine Manifest-Formulierung falsch → korrigiert), Runde 3 **BESTANDEN, 0 Abweichungen**. Doku: `docs/changelog-2026-09-27-n9d-verdrahtung.md`. ⚠️ **Korrektur 27.09. (N9e): der Nebenbefund ist ein Artefakt** — die 189 Gesichter der `gruppe`-Bilder wurden nur deshalb zu EINER Gruppe, weil alle Gesichter eines Bildes denselben Vektor trugen (Fehler in `alignCrop`, behoben). Die Verdrahtung `_fileid_von`/`kachelquelle_hinweis` bleibt gültig und geprüft; die Mengen- und Cluster-Zahlen sind mit richtigen Vektoren neu zu rechnen (**N9f**) |
| N9e | **Cluster-Schwelle am echten Bestand prüfen** (Kandidat aus dem N9d-Nebenbefund): `vektoren_clustern` bündelt die 189 nutzbaren Gesichter der `gruppe`-Bilder zu **einer** Gruppe — bei einem Dichte-Verfahren (`CLUSTER_SCHWELLE = 0,45`) ist Verkettung erwartbar, aber am echten Bestand nicht mit Bodenwahrheit geprüft | Gruppen-Anzahl gegen eine bekannte Personenmenge gemessen; falsch zusammengelegte Cluster beziffert | ✅ **bestanden (27.09.)** — **der Befund war ein Fehler, nicht das Clustering.** `cv2…alignCrop` erwartet die **volle 15-Werte-Detektionszeile** (60 Byte), bekam an **drei** Stellen nur die 5×2-Landmarken (40 Byte) → OpenCV liest über den Puffer hinaus → **jedes Gesicht eines Bildes bekam denselben Vektor**. Belegt an einem Bild mit 6 Gesichtern (Kennung bewusst nicht genannt): mit Landmarken **6× dieselbe** Ausschnitt-Prüfsumme **`e06d30ef365c`, Mittelwert 0,00 (schwarz)** und 6× dasselbe Merkmal, mit der vollen Zeile **6 verschiedene** echte Ausschnitte (Mittel 103–158). Kontrollierter Puffer als harter Beleg: die alte Form ist **bit-identisch** mit der nachgebauten Mischzeile → OpenCV liest **vier Werte über das Ende hinaus**; *welcher* Müll gelesen wird, hängt am Speicherinhalt (der Prüfer sah in seinem Lauf pro Gesicht verschiedene Ausschnitte) — in seiner Wirkung ist der Übergriff aber eindeutig: die alte Form schneidet **nie** das Gesicht. In den gespeicherten Dateien: `n9d` 465 Gesichter → **72** Vektorwerte (57 von 57 Mehrgesicht-Bildern nur identisch), `n9b` 72 → **8** (15 von 15); Bild-interne Paare erkennbarer Gesichter: **131 von 131 mit Distanz exakt 0,0000**. **Fix** in `tools/foto_sortierung/gesicht_erkennen.py` (`_merkmal`/`gesichter_mit_detektor`) **und** `backend/face_infer.py` (`_align_face` + Aufrufer — der Produktionsweg war mit betroffen), dazu ein **Wächter**: ≥2 bit-identische Merkmale in einem Bild ⇒ deutsche Fehlermeldung, leere Liste, **kein stiller Durchlauf**. Prüfbefehl selbst gefahren **1316 passed, Exit 0** (Baseline 1205; +75 aus dem neuen Mess-Werkzeug, +36 aus Fix/Wächter/Tests). **Nachweis danach:** dieselben 92 Bilder neu gerechnet → 465 Gesichter, **465 verschiedene Vektorwerte**, 131 Bild-Paare mit Distanz **0,531–1,067** (0 ≈ 0); 6 **frische** Bilder live 2/2, 3/3, 2/2, 3/3, 7/7, 5/5 verschiedene Vektoren (kleinste Paar-Distanz 0,49–0,91). Neue Dateien `personen_vektoren_n9e.jsonl` (92) und `personen_vektoren_n9e_burst.jsonl` (59 Dateien, 6 Familien, 36 Gesichter/36 Werte). **Schwellen-Messung (neues Werkzeug `tools/foto_sortierung/personen_schwelle.py`, 75 Tests):** Bodenwahrheit = zwei **erkennbare** Gesichter im selben Bild sind zwei Personen; Anlass-Mix nur noch **Strukturmaß** (Anlass ist keine Identitätswahrheit). Ergebnis bei **allen acht** Schwellen 0,10–0,45: **0 von 131** Bild-Paaren verschmolzen (vorher 131/131 = 100 %); Gruppen 12 → 2, größte 22 → 3, Durchmesser 0,9032 → 0,1553. Über alle 465 Gesichter bleibt eine Verkettung sichtbar (0,45: 19 Gruppen, größte 85, Durchmesser 1,0755 > Schwelle) → eigener Folgeschritt. Burst-Serien: **0 von 42** Familien-Paaren verschmolzen, Distanz-Median 0,7777 (= Szenenaufnahmen, **kein** Identitätsbeleg). **Keine Schwelle geändert.** Prüfer `gpt-5.6-luna`: Runde 1 NICHT BESTANDEN (meine Aussage war zu absolut — welcher Speichermüll gelesen wird, ist nicht deterministisch) → korrigiert und mit kontrolliertem Puffer belegt, Runde 2 **BESTANDEN, 0 Abweichungen**. Doku: `docs/changelog-2026-09-27-n9e-aligncrop-fehler.md` |
| N9f | **Personen-Ergebnisse mit richtigen Vektoren neu rechnen** (Folge von N9e): Gruppen-Anzahl, Referenzseiten, Kennungs-Altbestand auf `personen_vektoren_n9e.jsonl`/`_burst.jsonl` neu bestimmen; die Mengen-Arten (`gruppe`/`menge`/`leer`) am korrigierten Lauf erneut zählen; danach die **Verkettung** messen/ersetzen (Mittelpunkt- oder Vollständigkeits-Verknüpfung bzw. Größen-Grenze) — **erst danach** die Schwelle neu begründen | neue Gruppen-Anzahl und Referenzseiten belegt; Verkettung beziffert oder ersetzt; Schwelle mit Zahlen begründet (oder bewusst unverändert) | ✅ **bestanden (27.09.)** — neues Werkzeug `personen_verkettung.py` (878 Zeilen) + **117** Tests → Prüfbefehl **1433 grün, Exit 0**; **Verkettung beziffert**: Bestandsverfahren (dichte) bei Schwelle 0,45 → Durchmesser **0,9032 = 2 × Schwelle** (größte Gruppe 22), vollständige Verknüpfung **0,4417 ≤ 0,45** (größte 11), Mittelpunkt 0,9040; über **alle acht Schwellen 0,10–0,45** liegt dichte und mittelpunkt **immer** über der Schwelle, vollständig **nie**; **Bodenwahrheit: 0 von 131** Bild-Paaren erkennbarer Gesichter verschmolzen (Distanzen min 0,5312/Median 0,8280/max 1,0667, **0 unter 0,45**) bei **allen** Verfahren und Schwellen; **Neu-Rechnung** auf korrigierten Vektoren: Arten `leer 20 · gruppe 32 · menge 10 · unklar 30`, **12 Gruppen** (4,4,4,4,3,11,10,3,22,3,3,3), **12 Kennungen**, **16 Referenzseiten mit 74 echten Gesichtsausschnitten** (alle 200×200, 2. Lauf 0); **Schwelle bewusst unverändert 0,45** (kleinster Abstand zweier erkennbarer Gesichter 0,5312 → 0,0812 Sicherheitsabstand; Anheben durch keine Messung gedeckt); Burst-Datei: 14 nutzbare Gesichter, alle drei Verfahren **gleich** (2 Gruppen, Durchmesser 0,3779 — keine Verkettung). Prüfer `gpt-5.6-luna`: **BESTANDEN, 0 Abweichungen** (9 Punkte unabhängig nachgerechnet). Doku `docs/changelog-2026-09-27-n9f-verkettung.md` |
| N9g | **Verfahrenswechsel im Produktionsmodul + breitere Stichprobe** (Folge von N9f): Produktion auf die **vollständige Verknüpfung** umstellen, vorher auf einer **über die Jahre gestreuten** Stichprobe messen (nicht nur 8 Anlässe) | neue Messung mit Bodenwahrheit belegt den Wechsel; Durchmesser-Invariante erfüllt; Prüfbefehl grün | ✅ **bestanden (27.09.)** — **Messung breiter:** 192 Bilder ausgewählt (40 Mengen-Anlässe über die Jahre gestreut = 152 Bilder + 40 Kontrollen aus 40 Anlässen), **188 erkannt, 142 mit Gesicht, 907 Gesichter, 1.086,6 s, 9 Fehlerzeilen** (4 × pCloud-Zeitüberschreitung, 5 × nicht dekodierbar), **341 geclusterte Gesichter**, Arten `gruppe 74 · leer 41 · menge 20 · unklar 48`; **Bodenwahrheit 210 Paare**, Distanzen 0,4925/0,8708/1,1422, **0 unter 0,45**. **Der neue Befund:** das Bestandsverfahren **dichte** verschmilzt **2 von 210** erkennbaren Paaren (bei 0,45 **und** 0,40, Quote 1,0 %) und reißt den Durchmesser mit **2,00234 × Schwelle**; **vollstaendig 0 von 210** in allen 16 Kombinationen (8 Schwellen × 2 Mindestgrößen), Durchmesser **nie** über der Schwelle (knappste Stelle 0,99908); **mittelpunkt 11 von 210** bei 0,45 (Durchmesser 0,9240) → ausgeschieden. Bei 0,45: dichte 10 Gruppen/89 Gesichter/2 verschmolzen gegen **vollstaendig 13 Gruppen/66 Gesichter/0** (Preis ehrlich: 23 Gesichter mehr im Rauschen). **Code:** `CLUSTER_VERFAHREN = "vollstaendig"` als Produktionsstandard, `vollstaendig_clustern` als einzige Quelle in `personen_cluster.py` (Complete-Linkage, numpy, deterministisch), `vektoren_clustern(..., verfahren=None)` mit `"dichte"` unverändert und deutscher `ValueError` bei unbekanntem Verfahren, `personen_schwelle` auf `"dichte"` festgenagelt (Messwerkzeug bleibt Bestandsverfahren), `personen_verkettung.vollstaendig_clustern` delegiert (keine Doppelung). Prüfbefehl selbst gefahren **1449 passed, Exit 0** (+16 Tests), Prüfer `gpt-5.6-luna`: **BESTANDEN, 0 Abweichungen**. Doku: `docs/changelog-2026-09-27-n9g-verfahren.md` |
| N11 | **Fotos-Fragen am Handy:** Endpunkt `/api/fotos/uebersicht` + kleine Datendatei (Zahlen und Event-Namen, **ohne Bilder**) | Endpunkt antwortet ohne Netz; Selbsttest zeigt die Quelle | ✅ **bestanden (27.09.)** — Werkzeug `tools/foto_sortierung/foto_uebersicht.py` (565 Zeilen, **98** Tests) schreibt die Übersichtsdatei aus `sortierplan.json` (read-only); Dienst `backend/app/services/foto_uebersicht.py` (389 Zeilen) + Router `backend/app/router/fotos.py` (103 Zeilen, `GET /api/fotos/uebersicht` mit `jahr`/`kategorie`/`suche`/`limit`, **immer HTTP 200, nie 500**) + Chat-Werkzeug `_fotos_uebersicht_tool` (in **beiden** Ketten) + Selbsttest-Block `fotos` + Frontend-Zeile (**83** weitere Tests). Prüfbefehl selbst gefahren **1687 passed, Exit 0** (Baseline **1503**); JS-Tests grün. **Echte Datei:** `~/foto_sortierung/fotos_uebersicht.json`, **344.615 Bytes**, 2.127 Anlässe · **2.098 Event-Ordner** · 9.430 Zeilen · 7.616 Züge · 1.146 ohne Datum · 11 Jahre/48 Themen/11 Kategorien; **Rauchtest am echten Bestand ohne Netz** (200, `ok: true`, Filter greifen, `limit` geklemmt). Prüfer `gpt-5.6-luna`: Runde 1 NICHT BESTANDEN (4 Doku-Abweichungen), Runde 2 NICHT BESTANDEN (3 Restpunkte), **Runde 3 auf `9a213c9`: BESTANDEN, 0 Abweichungen**. Doku: `docs/changelog-2026-09-27-n11-uebersicht-datei.md`, `…-endpunkt.md`, Auftrag `docs/auftrag-n11-foto-uebersicht.md`. **Offen:** die Datei muss noch aufs Handy (Übertragung ist nicht Teil des Schritts) |
| N10 | **Doku + Protokoll + Abschlussbericht** (Changelogs, `CLAUDE.md`, Planjournal) | alles committet, Bericht mit Zahlen | ✅ **bestanden (28.09.)** — `docs/abschlussbericht-nachtlauf-2026-09-26.md` (**276 Zeilen**, 17 Schritt-Zeilen mit Zahlen + Prüfer-Befund, Kosten, der N9e-Fehler, gesperrte Punkte wörtlich aus dem Plan, Sicherheitsnetz, 5 Pitfalls) + Changelog **95 Zeilen** + Projekt-`CLAUDE.md`-Protokollzeile + `../CLAUDE_EXTENDS.md`-Prüfbefehlszeile auf **1687 grün, Exit 0 (28.09.2026)**; Prüfbefehl selbst gefahren **1687 passed, Exit 0** (Baseline 1503). Prüfer `gpt-5.6-luna`: Runde 1 NICHT BESTANDEN (6 Punkte: 4 berechtigt — Dateikennung im Bericht, gesperrte Punkte nur paraphrasiert, unmarkierte Näherung, Changelog-Aussage zu fremden Dateien; 1 Fehlalarm mit Zeitstempel-Beleg widerlegt, 1 Aufruf-Fehler des Prüfers), Runde 2 **BESTANDEN, 0 Abweichungen** |

| N13a | **Bilder im Chat, Datenfundament** (Vorstufe zu N13): Werkzeug baut aus `sortierplan.json` eine kleine Datei mit den **Datei-Kennungen je Event** (`~/foto_sortierung/fotos_dateien.json`), Dienst + `GET /api/fotos/bilder` liefern sie aus — die N11-Übersicht bleibt **unberührt** (sie trägt bewusst keine Kennungen) | Werkzeug-Tests grün; Endpunkt immer 200; echte Kennungen live gegen den Plan geprüft | ✅ **bestanden (28.09.)** — `tools/foto_sortierung/foto_dateien.py` (434 Zeilen) + `backend/app/services/foto_bilder.py` (385) + Route in `router/fotos.py` (103 → 188) + **189** neue Testfunktionen; Prüfbefehl selbst gefahren **1876 passed, Exit 0** (Baseline 1687). **Live gemessen:** Datei **1.146.180 Bytes**, **2.098 Events · 7.616 Dateien · 0 ohne Kennung**; Endpunkt `?limit=3` → 200, `ok: true`, die ersten drei Events mit 1 / 19 / 1 Dateien; ein Filter auf einen Event-Namen → 1 Treffer (der echte Event-/Ortsname steht hier absichtlich **nicht**); **echter Vorschaubild-Abruf** für eine zurückgegebene Kennung → **200 `image/jpeg`, 4.581 Bytes, Magic `ffd8ffe0`, `Cache-Control: no-store`**. Prüfer `gpt-5.6-luna` (frische Kontexte): Runde 1 NICHT BESTANDEN (4 Abweichungen, **alle an der Doku** — Eigner-Name ×2, ein echter Ortsname in zwei Schema-Beispielen, eine veraltete Changelog-Aussage; den Code hat der Prüfer ausdrücklich bestätigt), Runde 2 **BESTANDEN, 0 Abweichungen** (eigener Lauf 1876/Exit 0, Paare 7.616 gegen 7.616 identisch, N11-Datei und Plan unverändert); **Runde 3 und 4** (Abnahmen auf den Commits `bea270d`/`201a9cf`) brachten je eine Doku-Rest-Abweichung — eine echte pCloud-Kennung in einem Schema-Beispiel und zwei zu knappe Rundenzahlen (dazu sechs **alte** Kennungen in früheren Journal-Einträgen, in `4c0cb36` schon vorhanden) — **alle korrigiert**, Schlussabnahme Runde 5 auf Commit `1b66fa0`: **BESTANDEN, 0 Abweichungen** (eigener Lauf 1876/Exit 0, `0 0`, nur noch die erfundene Beispielkennung in den drei Dokumenten). Offen: **N13b** (Anzeige: Kacheln, Großansicht, Diashow im Frontend) |
| N13b | **Bilder im Chat, Anzeige** (Galerie + Diashow): Frage → Trefferliste → Kacheln → Antippen = groß → Diashow; Bilder **gestreamt, nie gespeichert** (kein Service-Worker-Cache für Bildpfade, Blob im Arbeitsspeicher, nach dem Ansehen freigegeben) | JS-Tests grün; nach 100 angesehenen Bildern ist der Cache-Speicher unverändert (Messung im Browser); `?v=` erhöht | ✅ **bestanden (28.09.)** — vier reine Funktionen (`fotoFrageErkennen`, `fotoKacheln`, `fotoGalerieZeilen`, `fotoDiashowNaechster`), Zweig in `sendMessage` **vor** dem Abbruch-Guard, Galerie-Blase mit Trefferliste + Kacheln, Großansicht `480x480` mit `‹ Zurück`/`Weiter ›`/`▶ Diashow`/`✕`, Diashow alle 3 s (umlaufend), Bilder **nur** per `fetch`→Blob→Objekt-URL, Freigabe bei jedem Wechsel und beim Schließen; `frontend/tests/test_foto_galerie.js` (328 Zeilen, **145 Prüfungen**) → alle grün; **16 von 16** JS-Dateien grün; Prüfbefehl **1876 passed, Exit 0** (Baseline 1687, +189 aus N13a — die Zahl **wächst seither laufend** durch fremde Parallelarbeit im selben Arbeitsbaum: 1897, Prüfer-Lauf 1922, jeweils Exit 0); `?v` auf **`20260928A`**. **Live im echten Browser** (eigener wegwerfbarer Edge headless + Backend am PC, echter Bestand): **23 von 23 Kacheln** als echte pCloud-Vorschaubilder geladen (0 Platzhalter), **100 angesehene Bilder** → 100 geladen, 0 Fehler, **Speicher vorher wie nachher 0**, Cache-Liste leer, `localStorage`/`sessionStorage` unverändert, offene Objekt-URLs nach dem Schließen **0**; derselbe Bild-Abruf zweimal → beide Male **4881 Byte** über die Leitung (`Cache-Control: no-store`). Prüfer `gpt-5.6-luna`: Runde 1 NICHT BESTANDEN (Eigner-Vorname im Changelog, lange Ziffernfolge im Messblock — beides korrigiert; Testzahl + fremde Dateien = Bestand), **Runde 2: „NICHT BESTANDEN" mit einer einzigen Abweichung, die fremd ist** (`CLAUDE.md` trägt eine offene Zeile des zweiten Agenten, nicht Teil dieses Commits) → als Bestand eingeordnet, Commit `3f5bd43` (genau **9** Dateien, keine fremde), `0 0`. Doku: `docs/changelog-2026-09-28-n13b-bilder-anzeige.md`, Auftrag `docs/auftrag-n13b-bilder-anzeige.md` |
| N13c | **Übergabe der Foto-Datendateien ans Handy** (`tools/handy/uebergabe_uebernehmen.py` + Block in `start-termux.sh`): der PC legt `fotos_dateien.json` und `fotos_uebersicht.json` per Kabel in den Download-Ordner, das Handy übernimmt sie beim Start nach `$HOME/foto_sortierung` — sha256 hart geprüft, alte Fassung als `*.vorher`, idempotent, Protokoll im Diagnose-Ordner | Werkzeug-Tests grün; Übergabe am Kabel **byte-genau** belegt; Startblock kann den Serverstart nicht verhindern | ✅ **bestanden (28.09.)** — siehe Journal unten: **2006 passed, Exit 0** (Baseline 1937), Push beidseitig **md5-gleich**, echter Handlauf mit den echten Dateien (`uebernommen 2`, sha256 identisch, 2. Lauf `Fehler 0`), Prüfer `gpt-5.6-luna` Runde 2 **„bestanden"**. Offen: der **erste Lauf am Handy** passiert beim nächsten Widget-Tipp |
| N18 | **Lösch-Werkzeug für Duplikate** (`tools/pcloud/pcloud_duplikate_loeschen.py`): Trockenlauf ist der Standard, Löschen nur mit `--wirklich`, frische Gegenprobe von Größe **und** Prüfsumme vor **jeder** Löschung, Manifest-Zeile je Löschung (`art: loeschen`), Papierkorb-Rückweg im Klartext, Grenze 25 je Lauf | Trockenlauf sendet nichts (belegt); Werkzeug-Tests grün; Manifest wächst je Datei; zweiter Lauf findet nichts | ✅ **bestanden (28.09.)** — siehe Journal unten: Werkzeug **1.226 Zeilen**, Tests **1.173 Zeilen / 64 Funktionen / 206 Prüfungen**, Prüfbefehl **2070 passed, Exit 0** (Baseline 2006); Live-Trockenlauf **25 geprüft / 0 gelöscht / 3.970,66 MB / Rest 2.108**, Bericht byte-gleich, `manifest.jsonl` **existiert nicht** (nichts gebucht); Prüfer `gpt-5.6-luna`: Runde 1 **NICHT BESTANDEN** (2 berechtigt → Cache entfernt + 2 neue Tests, Zeilenzahl), Runde 2 **NICHT BESTANDEN** (2 Doku-Punkte), Runde 3 auf dem Commit `cc32997`: **BESTANDEN, 0 Abweichungen**. **Der erste echte Löschlauf bleibt gesperrt** (Nutzer-Freigabe); die `upload`-Stufe (17,5 GB) ebenfalls |
| N27b | **Chat-Andockung** (Verknüpfungsschicht N27, Schritt 2 von 5): `tools/foto_sortierung/chat_andocken.py` liest `ereignisse.jsonl`, `msgstore.db` (**nur** `file:…?mode=ro`) und `whatsapp_zuordnung.json` **nur lesend** und schreibt `~/foto_sortierung/chat_andockung.jsonl` — je Ereignis die Chats und Kontakte im Fenster (Einzelchat ±1 Tag, **Gruppe streng derselbe Tag**), **ohne** Nachrichtentext, ohne Klartext-Nummern, ohne Netz/Bild; `--trocken` ist Standard, Repo-Ziel Exit 2 | Prüfbefehl grün; Live-Lauf liefert 2.127 Knoten und die Nachrichten-Zahlen; zweiter Lauf nur im Zeitstempel verschieden; Eingaben unverändert (mtime) | ✅ **bestanden (28.09.)** — siehe Journal: Prüfbefehl **2.232 passed, Exit 0** (Baseline 2.204); live **2.127 Ereignisse · 2.101 mit Nachrichten · 356.222 Nachrichten · 45.040 Chat-Andockungen · 24.780 Kontakte · Maximum 704**; Datei **19.259.758 B**, sha256 `cf2e0c19…`; Prüfer `gpt-5.6-luna` Runde 1 NICHT BESTANDEN (einziger echter Fund: fehlender Schreibsperren-Test → ergänzt, 2 neue Tests); **Abnahme Runde 2 auf dem Commit `0c79f5b`: BESTANDEN, 0 Abweichungen** |
| N27c | **Kalender-Andockung** (Verknüpfungsschicht N27, Schritt 3 von 5): `tools/foto_sortierung/kalender_andocken.py` liest `ereignisse.jsonl` und den Google-Kalender **nur per `zipfile`** aus dem Takeout-Zip und schreibt `~/foto_sortierung/kalender_andockung.jsonl` — je Anlass die Termine **am selben Tag** (±1 Tag nur als schwacher Hinweis `anzahl_nah`, `--auch-nah` optional) und **jährlich wiederkehrende** Termine (`RRULE FREQ=YEARLY` bzw. Titel „Geburtstag/Jahrestag“) über **Tag+Monat**; `--trocken` ist Standard, `--schreiben` atomar, Repo-Ziel Exit 2 | Prüfbefehl grün; Live-Trockenlauf nennt die Zahlen; zwei Schreibläufe byte-gleich; Repo-Ziel Exit 2 | ✅ **bestanden (28.09.)** — siehe Journal unten: `tools/foto_sortierung/kalender_andocken.py` (784 Zeilen), `backend/tests/test_kalender_andockung.py` (**114 Testfunktionen**, alles offline), Auftrag `docs/auftrag-n27c-kalender-andockung.md`; Prüfbefehl **2.414 passed, Exit 0** (Baseline 2.300, selbst gefahren); live **2.127 Ereignisse · 812 Zeilen mit Treffern · 957 Termine am Tag · 1.162 Nah-Treffer · davon wiederkehrend 253 · Maximum 3 · ICS 405 Termine / 0 defekt**; zwei `--schreiben`-Läufe mit festem `stand` **byte-gleich** (601.653 B, 2.127 Zeilen); Prüfer `openai/gpt-5.6-luna` Runde 1: 1 Abweichung (Doku) → korrigiert; **Runde 2 auf dem Commit `6be68a3`: BESTANDEN, 0 Abweichungen**; echte Ausgabedatei geschrieben (601.653 B / 2.127 Zeilen) |
| N27a | **Ereignis-Knoten je Anlass** (Verknüpfungsschicht N27, Schritt 1 von 5): `tools/foto_sortierung/ereignisse_bauen.py` liest `sortierplan.json` **nur lesend** und schreibt `~/foto_sortierung/ereignisse.jsonl` — je Anlass Datum, Thema, Kategorie, Ziel-Ordner, Datei-Kennungen (**ohne** Personen, ohne Bilder, ohne Netz); `--trocken` ist der Standard, `--schreiben` nötig, Ziel im Repo wird verweigert (Exit 2) | Prüfbefehl grün; Live-Trockenlauf liefert 2.127 Knoten und 7.616 Kennungen; zweiter Lauf inhaltlich identisch; Repo-Ziel Exit 2 | ✅ **bestanden (28.09.)** — siehe Journal: Prüfbefehl **2.204 passed, Exit 0** (Baseline 2.070, selbst gefahren); live **2.127 Ereignisse · 7.616 Datei-Kennungen · ohne Anlass 0 · ohne Kennung 0 · ohne Datum 0 · ohne Thema 0 · Kollisionen 404 · Events wiederverwendet 39** (= genau die 39 sicheren Vorschläge aus N6e); echte Datei **1.286.120 B / 2.127 Zeilen**; Repo-Ziel **Exit 2**, nichts geschrieben; Prüfer `gpt-5.6-luna`: **Runde 1 + 2 NICHT BESTANDEN** (nur Doku-Punkte, behoben), **Runde 3** nur noch fehlende Zeilenumbrüche in zwei Doku-Dateien (behoben); **Abnahme Runde 4 auf dem Commit `86fd5b3` mit `z-ai/glm-5.2`: BESTANDEN, 0 Abweichungen** |

## Journal (wird fortlaufend ergänzt)

* **26.09. ~04:40** — Regeln in `AGENTS.md` („Dauerlauf / Nachtarbeit")
  verankert; Entscheidungen oben festgehalten; Plan angelegt.
  Der Cloud-Service-Bau (`deleg_1a630b66`) läuft noch im Hintergrund.
  Selbstheilung (`pcloud_token_erneuern.py`) gebaut und **live belegt**
  (Prüfmodus „gültig", Neu-Holen erfolgreich).
* **27.09. ~05:05 — N1 fertig.** Cloud-Service aus dem Hintergrund-Bau
  (`sa-0-40a79e8d`, 1301 s, 67 API-Aufrufe) **selbst geprüft**: Prüfbefehl
  **500 passed, Exit 0** (72,5 s; vorher 433 → +67 neue Tests).
  Rauchtest-Zahlen gegengelesen: Konto maskiert `se…com`, userid 4738912,
  premium, **2199,0 GB / 390,5 GB belegt**; `liste(0)` **18 Einträge** (17 Ordner,
  1 Datei); `thumb()` **4185 Bytes** JPEG (120×120). Wichtigster Live-Fund des
  Ausführers: `getthumbs` liefert **keine Binärdaten**, sondern eine Textzeile
  `fileid|0|86x120|data:image/jpeg;base64,…`; `type=png` antwortet bei diesem
  Konto mit Code **5002** → Dienst fragt `jgp` an und dekodiert base64.
  Geheimnis-Prüfung im Staging: **0 Treffer**; `.env` unangetastet.
  Commit **`3cad5ae`** (Regeln/Pläne/Selbstheilung/Stand) und der
  Service-Commit folgen als eigener Schritt — gepusht.
* **27.09. ~05:20 — Kollision erkannt und entschärft.** Ein **zweiter Agent**
  arbeitet im selben Arbeitsbaum (`fa5153d`, `908cf39` — live_zahlen-Themen,
  nicht von diesem Lauf). Sein `git add -A` hat die hier **gestagten**
  Cloud-Service-Dateien mitgenommen: Commit `908cf39` heißt „fix(live_zahlen)",
  enthält aber `pcloud_service.py`, `router/cloud.py`, beide Testdateien und den
  Service-Changelog. **Inhaltlich nichts verloren** (im Repo vorhanden, Tests
  grün), nur falsch beschriftet — Historie wird **nicht** umgeschrieben
  (fremde Commits). Konsequenz als Regel in `AGENTS.md`: nie `git add -A`,
  immer `git commit --only <Pfade>`; bei `cannot lock ref` erst
  `git pull --rebase`, niemals `--force`. Push danach wieder synchron (`0 0`).
* **Läuft:** N2 (Rückroll-Werkzeug) und N4 (Themen-Werkzeug/Kontaktbögen) als
  zwei Subagenten (`deleg_609a78cd`), kollisionsfreie Dateien.
  N3 wartet auf den Hauptagenten (Schlüssel-Übertragung nur mit Sebastian).
* **27.09. ~05:40 — N4 fertig (Themen-Stufe, Subagent `deleg_609a78cd`).**
  `tools/foto_sortierung/foto_themen.py` (nur lesend: `listfolder` je Ebene +
  `getthumbs` in Stapeln à 25, Token nie ausgegeben) und
  `backend/tests/test_foto_themen.py` (**25** Prüfungen, alles ohne Netz).
  Prüfbefehl **525 passed, Exit 0** (58,7 s). Anlass-Regel: gleiche Minute =
  ein Anlass, neue Sitzung ab **30 min** Lücke (`--luecke`) → **2.128 Anlässe**
  über alle Jahre, **380 für 2025** (Median 2 Kacheln, max 108).
  Live-Stichprobe (2 Anlässe, nur lesend): `2025-02-21_Anlass-01` **10 Kacheln**
  (44.294 B Vorschauen, Bogen **62.566 B**, 3,4 s) und `2025-01-06_Anlass-01`
  **36 Kacheln** (186.514 B, Bogen **262.437 B**, 6,1 s) unter
  `~/foto_sortierung/boegen/2025/`; zweiter Lauf überspringt (0 geholt).
  Live-Funde: mehrere fileids je getthumbs-Aufruf möglich (Antwort-Reihenfolge
  NICHT garantiert → Zuordnung über fileid); **Videos/HEIC haben Vorschaubilder**
  (VIDEO-Kennzeichen trotzdem gesetzt); derselbe Anlass enthält
  geräteübergreifende Doppelungen (Motorola + OnePlus) — N6 kann über die
  CSV-Spalte `doppelung` deduplizieren. Details:
  `docs/changelog-2026-09-27-foto-themen.md`.
* **Offen für die nächste Runde:** **N6b** (Massenlauf Themen: Bögen je Jahr
  bauen, dann Themen setzen — kleinster Stapel zuerst, `themen.jsonl` als
  Fortsetzungspunkt), danach N7–N8 (Trockenlauf → echtes Sortieren),
  N9 (Personen) parallel möglich.
* **27.09. ~05:45 — N5 gemessen und bestanden (Hauptagent, echte Stichprobe).**
  Vision-Blick auf den 36er-Bogen `2025-01-06_Anlass-01` (262.437 B):
  - **Nummern 1–36 einwandfrei lesbar** → Kachel-Nummerierung trägt (Voraussetzung
    dafür, dass der Vision-Blick „Kachel 12" sagen kann).
  - Je Kachel eine Zeile Inhalt (Personen, drinnen/draußen, Motiv) — z. B. alle
    36 Kacheln „drinnen, Publikum vor grüner Bühne".
  - **Thema für den ganzen Bogen erkannt** (Veranstaltung in großer Halle; das
    Banner war sogar lesbar) → ein Aufruf **je Anlass** genügt, nicht je Bild.
  - **Nebenertrag:** unbrauchbare Bilder werden benannt (9/10/11 verwackelt,
    25/26 Bewegungsunschärfe, 33/34 schwarz) → die „Müll/behalten"-Triage fällt
    beim selben Aufruf mit ab.
  - **Kostenschätzung (noch keine Messung):** ein Vision-Aufruf je Anlass, bei
    2.128 Anlässen deutlich **unter 1 $**; die echten Zahlen werden aus dem
    Kosten-Tracker abgelesen, sobald der Vollauf startet — nicht behauptet.
  - **N6 ist damit startklar:** Bögen liegen bereit, Thema je Bogen kommt vom
    Vision-Blick, Dedup über die CSV-Spalte `doppelung` (geräteübergreifende
    Kopien waren im Bogen sichtbar).
* **27.09. ~08:30 — N6 gebaut und **bestanden** (Planer: Hauptagent ·
  Ausführer: Hermes-Subagent, DeepSeek V4.1 Flash · Prüfer: `openai/gpt-5.6-luna`).**
  Codex war nicht nutzbar (Kontingent, „try again at Oct 15th"), also lief der
  Bauweg über Hermes-Subagenten — drei Aufträge: Bau (0,038 $) und zwei
  Nachbesserungen (0,017 $ + 0,021 $), zusammen rund 0,08 $ Ausführerkosten.
  - **Werkzeug:** `tools/foto_sortierung/foto_themen_vision.py` +
    `backend/tests/test_foto_themen_vision.py` (**59 Prüfungen**, alles ohne Netz).
    Ein Vision-Aufruf je Anlass (Bild als data-URL in-memory an OpenRouter,
    Standard `google/gemini-2.5-flash`), Thema in die **Kopie** des
    Sortierschlüssels (`~/foto_sortierung/sortierschluessel_themen.csv`),
    Fortsetzungspunkt `themen.jsonl`.
  - **Prüfbefehl selbst gefahren:** Baseline **569** → **628 passed, Exit 0**
    (1:12 min). Vorher/nachher gemessen, nicht behauptet.
  - **Live gemessen** (echte Aufrufe, zwei Bögen, zusammen ~0,007 $):
    36-Kachel-Bogen → „Veranstaltung Publikum Bühne" (2.306+1.465 Tokens,
    0,004354 $, 6,8 s); 10-Kachel-Bogen → „Konzert Band Auftritt" (3.750+452,
    0,002255 $, 3,6 s); zweiter Lauf: **0 Aufrufe, 0 Tokens, 0,2 s**; die
    Original-CSV blieb unverändert (`md5 70642d2988b6e38ff417561ccf870ba8`).
  - **Kosten für den Vollauf (Schätzung, keine Messung):** 2.128 Anlässe; die
    beiden Messpunkte (10 und 36 Kacheln) liegen **über** dem Mittel von 3,9
    Kacheln → Größenordnung **2–4 $** mit `gemini-2.5-flash`, mit
    `flash-lite` etwa ein Drittel. Vor N6b an ~20 Anlässen nachmessen.
  - **Prüfer: 6 Runden, 5 × „nicht bestanden"** — und das war der Nutzen des
    getrennten Kontexts, kein Formfehler. 8 von 10 Beanstandungen waren
    berechtigt (4 am Code, 4 an der Doku). Echt gefunden und behoben: fehlender
    Schutz des Ausgabeordners (Repo), widersprüchliche Doku vs. Code bei den
    Kachel-Zählern, **ungefilterter Rohtext** (ein Modell, das den Schlüssel
    wiederholt, hätte ihn auf Platte geschrieben) und eine fehlende
    Kollisionssperre für die Original-CSV. Runde 6: **„bestanden"**.
  - **Entscheidungen statt Fragen:** (1) Kacheln mit `unbrauchbar: true` werden
    **behalten** und gezählt, doppelte Kachelnummern **verworfen** (erster
    Eintrag bleibt); (2) Themen gehen in eine **Kopie** des Sortierschlüssels,
    nie in die Original-Datei; (3) der Rohtext wird gespeichert, aber maskiert.
  - **Nächster Schritt: N6b** — Massenlauf (Bögen je Jahr bauen, dann Themen
    setzen), kleinster Stapel zuerst, jederzeit abbrechbar (`themen.jsonl`).
    Doku: `docs/changelog-2026-09-27-themen-vision.md`.
* **27.09. ~07:15 — N6b Stapel 1 gefahren und gemessen (Planer: Hauptagent).**
  „Kleinster Stapel zuerst": **2014, 2016, 2017, 2019, 2020, 2021** komplett —
  **161 Anlässe, 510 Kacheln, 0 Fehler**, alle Jahre Exit 0.
  - **Kontaktbögen:** 161 neu gebaut, 2,4 / 2,2 / 2,5 / **8,0** / **19,2** /
    **54,6 s** je Jahr (Summe 1,5 min) — deutlich schneller als die Schätzung
    „~4,5 s je Anlass" aus N4; Vorschaubilder 510 Stück (1,52 MB für 2021).
  - **Themen:** 161 Vision-Aufrufe, **438.072 ein / 26.082 aus Tokens**,
    **0,196610 USD** = **0,001221 USD je Anlass** (min 0,000973, max 0,004354);
    **1,91 s je Anlass** im Mittel, größte 8,67 s; **0 unbrauchbare Kacheln**,
    **0 unvollständige** Bögen, **0 Fehlerzeilen**.
  - **Original-CSV unverändert** (`md5 70642d2988b6e38ff417561ccf870ba8`),
    geschrieben nur außerhalb des Repos (`~/foto_sortierung/`).
  - **Kostenhochrechnung** (gemessen, nicht geschätzt): 2.128 Anlässe →
    `gemini-2.5-flash` **2,60 USD**, `gemini-2.5-flash-lite` **0,72 USD**,
    `gemini-3.7-flash` **5,64 USD**; Preise live über `/api/v1/models` geholt.
  - **Der Befund, der den Plan ändert: 155 verschiedene Themen bei 161
    Anlässen = 96 % Einzelstücke** („Haus Garten" vs. „Haus und Garten",
    „Sonnenuntergang Stadtansicht/Meer/am See"). Ursache im Code:
    `prompt_bauen()` fragt „2 bis 4 deutsche Woerter" **ohne Wortschatz**.
    Als Ordner `Agent/Fotos/<Jahr>/<Thema>/` wäre das untauglich.
  - **Entscheidung:** neuer Schritt **N6c — Themen-Katalog** (feste Liste,
    Ziel 40–60 Einträge, Prompt wählt nur daraus, 161 Anlässe mit
    `--wiederholen` nachziehen ≈ 0,20 USD) **vor** dem Restlauf der 1.967
    Anlässe; dort auch der Modellvergleich flash vs. flash-lite, weil 0,72 vs.
    2,60 USD sonst das Dreifache ohne belegten Gewinn wäre.
  - Doku: `docs/changelog-2026-09-27-themen-stapel1.md`.
  - **Prüfbefehl selbst gefahren:** `pytest tests/ -q` → **628 passed, Exit 0**
    (121 s; unverändert, da nur ausgeführt und dokumentiert wurde).
    **Prüfer `openai/gpt-5.6-luna`: „bestanden", 0 Abweichungen** — er hat die
    Zahlen alle selbst nachgerechnet (155 von 161 = 96,27 %, Summen, md5,
    Exit-Zeilen, Code-Stelle `prompt_bauen()`).
* **27.09. ~09:55 — N6c gebaut, gemessen und bestanden** (Planer: Hauptagent ·
  Ausführer: Hermes-Subagent `deepseek-v4.1-flash` · Prüfer: `openai/gpt-5.6-luna`,
  zwei Runden). **Codex war nicht nutzbar:** `codex exec --model gpt-5.6-terra`
  antwortete live „You've hit your usage limit … try again at Oct 15th, 2026
  9:32 PM" — also lief der Bauweg über Hermes-Subagenten (0,054 USD + 0,006 USD
  Ausführerkosten).
  - **Runde 1 — Werkzeug (Commit `c1c24c5`, gepusht, `0 0`):**
    `tools/foto_sortierung/themen_katalog.py` (Katalog, `thema_zuordnen`,
    `im_katalog`, `katalog_text`), Prompt wählt nur noch Wort für Wort aus der
    Liste, `thema_roh`/`katalog_treffer` in beiden Ausgaben, CLI `--ohne-katalog`;
    Tests **59 → 87**, Prüfbefehl **656 passed, Exit 0** (selbst gefahren),
    Prüfer: **BESTANDEN, 0 Abweichungen** (u. a. `prompt_bauen` ohne Katalog
    byte-gleich zu HEAD, Schutzfunktionen AST-identisch).
  - **Messung 1 (Katalog v2, 44 Einträge):** dieselben **161 Anlässe** beider
    Modelle. flash: 161/161 Katalog-Treffer, 0 Fehler — aber **43 × `Sonstiges`
    (27 %)**. flash-lite: 0,058129 USD, 21 × `Sonstiges`. Damit stand fest: der
    Katalog hat Lücken, und ein Viertel aller Anlässe in einem Ordner wäre
    untauglich.
  - **Runde 2 — datenbasierte Erweiterung:** die Kachel-Kurzbeschreibungen der
    43 `Sonstiges`-Anlässe ausgewertet (nicht geraten): Sonnenuntergang/Abendhimmel,
    Nachtszenen, Selfies/Porträts, Gruppe unterwegs, Demonstration/Politik,
    Screenshots/Text/Memes, Zeitungen/Buchseiten, Dinge/Stillleben, Hoftiere.
    Genau diese neun Sachgebiete als Einträge ergänzt → **53 Einträge,
    `KATALOG_VERSION = 3`**; Tests **657 passed, Exit 0** (selbst gefahren).
  - **Messung 2 (Katalog v3, beide Modelle, dieselben 161 Anlässe):**
    **flash** 0,209693 USD, **161/161** im Katalog (100 %), **14 × `Sonstiges`
    = 8,7 %** (alle selbst gewählt, 0 Antworten außerhalb), **37 Themen**;
    **flash-lite** 0,058977 USD, 160/161 im Katalog (99,4 %), **18 × `Sonstiges`
    = 11,2 %** (17 selbst gewählt + 1 außerhalb), 34 Themen. Die Erweiterung
    wirkte: 27 % → 8,7 %.
  - **Modellvergleich:** identische Anlässe, identischer Prompt, nur das Modell
    anders; flash ist das **3,56-Fache** im Preis (0,209693 zu 0,058977 USD).
    Hochrechnung auf die 1.967 wartenden Anlässe: flash 2,56 USD, flash-lite
    0,72 USD. **Sichtprobe an sechs Bögen genau dort, wo sich beide widersprechen:
    flash trifft 4, flash-lite 2** — flash-lites Fehler sind falsche Sachgebiete
    („Huhn mit Küken" → `Hund im Freien`, Sommerbergtour → `Wandern im Schnee`,
    Reise vor Palmen → `Familienfeier Zuhause`), flash sagt in solchen Fällen
    ehrlich `Sonstiges`. **Entscheidung: flash für den Massenlauf** — 1,84 USD
    Mehrkosten für 1.967 Anlässe wiegen einen falsch sortierten Ordnerbaum nicht auf.
  - **Die restlichen 14 `Sonstiges`-Anlässe** sind überwiegend Bildschirmfotos,
    Memes und Textbilder (Glühwein-Text, „Finde das Kamel", Wahlergebnisse,
    Zeitungsausschnitt, Rezeptseite) plus Grenzfälle; dafür kommt bewusst kein
    Katalogeintrag dazu (weitere ähnliche Einträge würden Ordner überlappen lassen).
  - **Prüfer-Runde 2 (`gpt-5.6-luna`, Endstand):** Prüfbefehl selbst 657/Exit 0,
    Katalog nachgezählt (53, Version 3, keine normalisierten Doppelungen),
    Messzahlen beider Läufe nachgerechnet, md5 der Original-CSV geprüft,
    `prompt_bauen` ohne Katalog byte-identisch zu HEAD. **Eine Beanstandung:**
    die Angabe „18 gewählte Sonstiges" für flash-lite war unpräzise — richtig
    sind 17 selbst gewählte + 1 aus einer Antwort außerhalb des Katalogs (Thema
    ebenfalls `Sonstiges`, `katalog_treffer: false`). **Doku korrigiert** (Changelog).
  - **Lehre (Pitfall, kostete einen Doppel-Lauf):** ein MSYS-Pfad
    (`/c/Users/sebas/foto_sortierung`) an ein **natives Windows-Python** gegeben
    → Python löst ihn relativ zum Laufwerk auf, der Ordner landete unter
    `C:\c\Users\sebas\foto_sortierung`. Die Daten wurden **per Kopie gerettet**
    (161 Themen-JSONs, beide `themen.jsonl` entdoppelt zusammengeführt), nichts
    gelöscht; das leere Artefakt liegt weiter unter `C:\c\Users\sebas\foto_sortierung`
    und darf von Sebastian entfernt werden. Regel für die nächste Runde:
    an native Werkzeuge **immer** `C:/…`-Pfade, nie `/c/…`.
  - **Schutz:** Original-CSV unverändert (`md5 70642d2988b6e38ff417561ccf870ba8`),
    alle Ausgaben außerhalb des Repos, kein Schlüssel in Ausgaben oder Dateien.
  - **Nächster Schritt: N6b Rest** — 1.967 Anlässe (2022–2025) mit **flash**
    und Katalog Version 3, kleinster Stapel zuerst, danach **N7** (Trockenlauf
    des Sortierens).
* **27.09. ~11:00 — N6b Rest gefahren, gemessen und bestanden** (Planer:
  Hauptagent · Ausführer: die Werkzeuge selbst plus ein Hermes-Subagent
  `deepseek-v4.1-flash` für die Code-Korrektur, 0,003 USD · Prüfer:
  `openai/gpt-5.6-luna`). **Codex weiterhin gesperrt** (Kontingent).
  - **Reihenfolge (kleinster Stapel zuerst):** 2026 (301) → 2025 (380) →
    2022 (409) → 2024 (430) → 2023 (447). Vorlage: eine Jahreszahl aus dem
    Trockenlauf (`Anlaesse gesamt`), damit der billigste Teil zuerst fertig
    ist — nicht geraten.
  - **Zahlen (echte Aufrufe):** **1.967 Anlässe**, davon **1.962 gesehen**
    (3 im Rauchtest vorab, 2 Fehlschläge), **7.722 Kacheln**,
    **5.954.092 ein / 370.113 aus Tokens = 2,711510 USD** für den
    Fünfjahres-Lauf, **94,2 min** (24,5 min Bögen + 69,7 min Vision).
    Die Hochrechnung aus N6b Stapel 1 (2,56 USD) wurde um 0,15 USD (≈ 6 %)
    überschritten — notiert, nicht beschönigt.
  - **Endstand:** **2.128 Anlässe** im Fortsetzungspunkt, **2.127 mit
    Katalog-Thema**, **48 Themen** tatsächlich benutzt, **242 × `Sonstiges`
    = 11,4 %** (auf den 161 Anlässen aus N6c waren es 8,7 % — der größere
    Bestand enthält mehr Bildschirmfotos, Memes, Textbilder). Gesamtkosten
    über den Bestand (`kosten_usd` summiert): **2,938515 USD**.
  - **Echter Codefehler, vom Lauf aufgedeckt und behoben:** der größte Anlass
    `2025-01-17_Anlass-02` (**108 Kacheln**, 19:09–22:17, 1,3 GB) scheiterte
    zweimal an „kein lesbares JSON" — auch mit `flash-lite`. Ursache gemessen:
    der harte Deckel `MAX_TOKENS = 4000` **schneidet** die Antwort ab (ein
    JSON-Objekt je Kachel). Korrektur: reine Funktion
    `max_tokens_fuer(anzahl) = max(4000, min(16000, 1200 + 60 * anzahl))`,
    `anfrage_bauen()` nutzt sie nur ohne ausdrücklichen Wert → kleine Bögen
    **byte-gleich** wie vorher. **Beleg:** derselbe Anlass läuft mit
    **108/108 Kacheln, 4.420 Ausgabe-Tokens** (über dem alten Deckel) durch,
    0,012073 USD. 6 neue Tests (665 → **671**).
  - **Ein Fall bleibt bewusst offen:** `2022-09-05_Anlass-02` wird vom
    **Anbieter** abgelehnt — eigene Sonde direkt gegen die API belegt HTTP 200
    mit `error.code = 403`, `Gemini blocked the request: PROHIBITED_CONTENT`
    (Beleg: `~/foto_sortierung/n6b_probe_2022-09-05.log`). Das Werkzeug meldet
    dafür nur „OpenRouter lieferte keine Antwort" — die Ablehnung selbst ist im
    Werkzeug-Log **nicht** sichtbar. **Entscheidung: keine Modellumgehung** —
    ein Anbieter, der Aufnahmen ablehnt, kann dafür einen Grund haben;
    Sebastian sieht die Bilder vor dem Sortieren. Der Anlass bleibt als Marker
    (`thema: null`) im Fortsetzungspunkt und wird bei jedem Lauf erneut
    versucht (kostet nichts, Ablehnung kommt vor der Token-Abrechnung).
  - **Wiederholungsmarker (Nebenbefund):** Fehlversuche schreiben eine Zeile
    mit `thema: null` je Versuch — daher 2.134 Zeilen bei 2.128 eindeutigen
    Anlässen. Gewollt: der nächste Lauf findet den Anlass wieder. Genau diese
    Mechanik hat den 108-Kachel-Fall nach der Code-Korrektur automatisch
    eingesammelt.
  - **Prüfbefehl selbst gefahren:** `pytest tests/ -q` → **671 passed, Exit 0**
    (71 s). **Prüfer (Runde 1, `gpt-5.6-luna`)** hat selbst nachgerechnet
    (671/Exit 0, `max_tokens_fuer` für 10/108/246/5000 Kacheln, Token- und
    Kostensummen, md5) und **3 Punkte** gemeldet: (1) „vier geänderte Dateien
    statt zwei" — die zwei fremden (`docs/experimente/live_zahlen.*`) gehören
    dem **zweiten Agenten**; deshalb `git commit --only` mit ausdrücklich
    genannten Pfaden; (2) der Zählstand war zum Prüfzeitpunkt **veraltet**
    (2.128/2 → jetzt 2.128/**1** ohne Thema, 2.127 Themen-Dateien), korrigiert;
    (3) der 403-Nachweis stehe „nicht im Log" — richtig, er kommt aus der
    eigenen Sonde, die jetzt als Datei abgelegt ist.
    **Prüfer-Runde 2 auf dem committeten Stand (`0318e56`): „BESTANDEN", 0
    Abweichungen** — er hat den Commit-Inhalt (`git show`, vier Dateien, die
    fremden `live_zahlen`-Dateien nicht enthalten), `0 0` gegen `origin/main`,
    den Zählstand (2.134 Zeilen / 2.128 eindeutig / 1 ohne Thema / 2.127
    Dateien / 48 Themen / 242 `Sonstiges` = 11,37218 %), die Jahresverteilung,
    den Sonde-Beleg, die Token- und Kostensummen (5.954.092 ein / 370.113 aus
    = 2,7115101 USD), den md5, den Prüfbefehl (671/Exit 0), `max_tokens_fuer`
    (10/108/5000 Kacheln) und den 108-Kachel-Anlass mit 4.420 Ausgabe-Tokens
    selbst nachgerechnet.
  - **Schutz:** Original-Sortierschlüssel unverändert
    (`md5 70642d2988b6e38ff417561ccf870ba8`), nur die Kopie
    `sortierschluessel_themen.csv` geschrieben (9.430 Zeilen, 8.284 mit Thema);
    Ausgaben ausschließlich außerhalb des Repos (`~/foto_sortierung/`, Bögen
    70 MB, Themen 11 MB); **alle pCloud-Aufrufe lesend**, nichts verschoben,
    nichts gelöscht; Sicherungskopie des Fortsetzungspunkts
    (`themen_vor_n6b_rest_20260927_091225.jsonl`).
  - **Nächster Schritt: N7** (Trockenlauf des Sortierens) — mit der Auflage
    aus dem Plan: Rückfallordner für Anlässe ohne Thema, und Zielordner sind
    laut **N6d** Sebastians eigene Kategorien (18 Kategorien, 113 Unterordner).
* **27.09. ~11:45 — N6d gebaut und bestanden** (Planer: Hauptagent · Ausführer:
  Hermes-Subagent `deepseek-v4.1-flash`, 0,026 USD · Prüfer: `openai/gpt-5.6-luna`).
  **Codex weiterhin gesperrt** (Kontingent bis 15.10.).
  - **Beginn dieser Runde:** `git pull --rebase` **scheiterte** an ungestagten
    Änderungen — es sind die **fremden** Dateien des zweiten Agenten
    (`docs/experimente/live_zahlen.*` geändert, zwei neue Recherche-HTML). Nicht
    angefasst, nicht gestasht. Stattdessen `git fetch` + Zählung:
    `git rev-list --left-right --count origin/main...HEAD` → **`0 0`** — lokal und
    remote identisch, es gab nichts zu holen. Der Pull-Abbruch war also
    folgenlos; gearbeitet wurde vom committeten Stand `13e1b80`.
  - **Das Problem:** die 53 Motiv-Themen aus N6/N6c sind als **Ordner** untauglich
    (Sebastian hat längst eigene Kategorien). Gebaut wurde die Übersetzung
    Motiv-Thema → **Bucket** (11, generisch, im Code) → **echter pCloud-Ordner**
    (lokal gebunden). Die echten Ordnernamen stehen **nicht** im Repo, sondern in
    `~/foto_sortierung/kategorie_zuordnung.json` (Namen Dritter/Orte bleiben
    privat — dieselbe Regel wie beim Bestand).
  - **Zahlen (frisch gefahren):** Baseline **671** → Prüfbefehl
    `pytest tests/ -q` → **709 passed, 3 warnings, Exit 0** (70,8 s; +38 eigene
    Tests). Live `--zeigen` gegen den echten Bestand: **18 Kategorien · 113
    Unterordner · 10 mit Unterordnern · 11 Buckets (10 gebunden, 1 × null =
    `Sonstiges` → Neubau)**, Exit 0, **nichts geschrieben**; mtime der
    Bestandsdatei unverändert (09:40:53). Bindung selbst gelegt (10 echte Ordner,
    1 Neubau) und mit dem Werkzeug geprüft.
  - **Bewusste Entscheidungen:** (1) `Sonstiges` legt einen **neuen** Ordner an,
    statt einen bestehenden Sammelordner zu füllen; (2) die Bindungen der 18
    Kategorien bleiben generisch im Code, nur die Buckets sind Ziele; (3) fehlende
    Buckets in der Zuordnungsdatei sind ein **Fehler**, keine stille Erweiterung;
    (4) Zielpfad-Schema `Agent/Fotos/<Jahr>/<Kategorie>/<Event>` mit
    Namensbereinigung, Jahr auf 1900–2100 geprüft.
  - **Schutz:** nur **lesende** pCloud-Aufrufe (`liste`, feste Tiefe 2, kein
    `thumb`, kein Download), atomares Schreiben nur außerhalb des Repos
    (Schreibversuch ins Repo wird verweigert), **keine Löschfunktion** (Test prüft
    den Quelltext auf Abwesenheit).
  - Doku: `docs/changelog-2026-09-27-zielkategorien.md`.
  - **Nächster Schritt: N6e** (Event-Abgleich: bestehende Event-Ordner als
    Vorschlag statt Neubau) — danach **N7** (Trockenlauf des Sortierens).
* **27.09. ~14:05 — N6e gebaut, geprüft und bestanden** (Planer: Hauptagent ·
  Ausführer: zwei Hermes-Subagenten `deepseek-v4.1-flash`, 0,036 + 0,032 USD ·
  Prüfer: `openai/gpt-5.6-luna`, zwei Runden — **andere Modellfamilie**).
  Beginn: `git pull --rebase` scheiterte wieder an den **fremden** Dateien des
  zweiten Agenten (`docs/experimente/live_zahlen.*` am Workspace-Root, zwei neue
  Recherche-HTML); nichts angefasst, nichts gestasht. `git fetch` +
  `git rev-list --left-right --count origin/main...HEAD` → **`0 0`**, es gab
  nichts zu holen. **Codex erneut geprüft und weiter gesperrt** („try again at
  Oct 15th, 2026") → gebaut wurde mit Hermes-Subagenten.
  - **Werkzeug:** `tools/foto_sortierung/event_abgleich.py` (**1.060 Zeilen**,
    Nachbarmodul von `foto_kategorien`), Tests
    `backend/tests/test_event_abgleich.py` (**893 Zeilen, 51 Testfunktionen**,
    selbst nachgezählt; alles ohne Netz). Es liest **nur** die lokalen Dateien —
    **kein pCloud-Aufruf**, keine Lösch-/Verschiebefunktion (Test prüft den
    Quelltext), Schreiben nur außerhalb des Repos und nur mit `--schreiben`.
  - **Regel:** vorhandener Event-Ordner derselben Kategorie wird als **Vorschlag**
    erkannt, sonst entsteht ein neuer Name. Belege aus dem Ordnernamen gelesen:
    Tag/Monat/Jahr, Jahresspanne, offenes Jahr (`2019+`), Jahr als Suffix,
    Punkt-Datum, Monatsliste — plus die Fehltreffer-Regel, dass eine blanke Zahl
    1–12 **nur direkt an einem Jahr** ein Monat ist.
  - **Prüfbefehl selbst gefahren:** `pytest tests/ -q` → **760 passed, Exit 0**
    (70 s; Baseline 709 aus N6d, +51 eigene Tests).
  - **Der Befund, der die Regel verschärfte (eigene Sichtprobe, 18 Vorschläge):**
    Runde 1 lieferte **639 Vorschläge**, davon **495 allein aus „Jahr gleich"** —
    im Klartext Unsinn wie ein Tier-Foto → `2019 <Junggesellenabschied>`. Ein
    bloß gleiches Jahr ist ein **falscher Beleg**, kein schwacher. **Neue Regel:
    nur `tag`/`monat` ergeben einen Vorschlag**; `jahr`/`spanne` werden als
    **schwacher Hinweis** gezählt und sind erst mit `--auch-schwach` Vorschläge.
  - **Zahlen nach der Verschärfung (live, nur lesend):** **2.134 Anlässe ·
    39 Vorschläge (1,8 %)** — tag 10, monat 29 · **600 schwache Hinweise**
    (jahr 495, spanne 105) · 2.095 ohne Vorschlag, davon 276 „Kategorie fehlt im
    Bestand" · **112 von 113** Unterordnern über die 10 gebundenen Kategorien
    erreichbar (selbst nachgerechnet: 17+12+15+13+42+3+6+1+0+3). Mit
    `--auch-schwach`: 639 Vorschläge (39 sicher + 600 unsicher).
    **Sichtprobe der 39: durchweg plausibel** — Konzerte landen auf ihren
    Konzert-Ordnern (`2019_08 <Festival>`, `2020_03_04 <Band>`,
    `2024_07_23 <Band>`), die Juliwoche 2021 (Reise/Strand) auf `2021_07 <Reiseziel>`.
  - **Prüfer Runde 1: NICHT BESTANDEN, beide Punkte berechtigt.** (1) **Echte
    Ordnernamen** standen wörtlich in Code, Tests und Doku — der Prüfer nannte 4,
    die Nachzählung ergab **8** (darunter zwei Spiele-Ordner und ein Ordner mit
    Jahres-Suffix, den **mein eigener Feinauftrag** als Muster genannt hatte).
    Alle ersetzt; der Vergleich ist jetzt automatisiert (alle Zeichenketten der
    Dateien gegen `kategorien.json`) und ergibt **0 Treffer**. (2) Die Zahl
    „109 von 113" war falsch — nachgerechnet **112**; korrigiert mit Herleitung.
    Zusätzlich habe ich zwei **eigene** Dokumente bereinigt
    (`docs/auftrag-n6e-event-abgleich.md`, `docs/changelog-2026-09-27-kategorien-bestand.md`),
    in denen echte Termin-Ordner standen.
  - **Prüfer Runde 2 (frischer Kontext): NICHT BESTANDEN, aber nur noch wegen
    drei Resttreffern — die sind Fehlalarm.** Es sind **blanke Kalenderjahre**
    („2019"), und sie treffen, weil im Bestand Ordner buchstäblich nach dem Jahr
    heißen; ein Datums-Parser-Test **muss** Jahreszahlen enthalten. Kein
    Personen-, Orts- oder Ereignisname. Alles andere hat der Prüfer selbst
    bestätigt: Prüfbefehl 760/Exit 0, beide Läufe nachgerechnet, die verschärfte
    Regel eigenständig nachgewiesen, 112/113, keine Schreib-/Löschfunktion,
    Repo-Schreibschutz, Idempotenz, mtimes unverändert.
  - **Prüfer Runde 3 (Abnahme auf dem committeten Stand `724279d`): BESTANDEN —
    „Keine Abweichung festgestellt."** Mit präzisiertem Kriterium (blanke
    Kalenderjahre sind kein Treffer) bestätigte der Prüfer Commit-Inhalt (genau
    sechs Dateien, keine fremden `live_zahlen`-Dateien), Prüfbefehl 760/Exit 0,
    beide Läufe mit den erwarteten Zahlen, Datenschutz-Scan der fünf Dateien
    **0 Treffer mit Orts-/Personen-/Ereignisbezug** (8 Kalenderjahre, 181
    Vorkommen ausgefiltert), keinen pCloud-Aufruf und **6.562 unveränderte
    Dateien** unter `~/foto_sortierung/`.
  - **Schutz:** Original-Sortierschlüssel unverändert
    (`md5 70642d2988b6e38ff417561ccf870ba8`, selbst geprüft), Bestandsdateien
    ebenfalls (nur gelesen); Ausgaben ausschließlich außerhalb des Repos.
  - **Was N6e für N7 liefert:** je Anlass ein Vorschlag mit Stufe und `sicher` —
    der Trockenlauf kann damit bestehende Ordner **wiederverwenden** statt
    neu zu bauen. **39 sichere Vorschläge** sind vor einem Echtlauf mit Sebastian
    durchzusehen; die 600 schwachen Hinweise bleiben vorerst Hinweise.
  - Doku: `docs/changelog-2026-09-27-event-abgleich.md`,
    Feinauftrag `docs/auftrag-n6e-event-abgleich.md`.
  - **Nächster Schritt: N7** (Trockenlauf des Sortierens, `--trocken`, mit
    Rückfallordner für Anlässe ohne Thema, Zielordner = Sebastians Kategorien,
    Event-Wahl über `event_abgleich.vorschlag_fuer`).
* **27.09. ~15:10 — N7 gebaut, geprüft und bestanden** (Planer: Hauptagent ·
  Ausführer: zwei Hermes-Subagenten `deepseek-v4.1-flash`, 0,033 + 0,007 USD ·
  Prüfer: `openai/gpt-5.6-luna`, zwei Runden — **andere Modellfamilie**).
  Beginn wie in den Runden zuvor: `git pull --rebase` scheiterte an den **fremden**
  Dateien des zweiten Agenten (`docs/experimente/live_zahlen.*`, zwei neue
  Recherche-HTML); nichts angefasst, nichts gestasht. `git fetch` +
  `git rev-list --left-right --count origin/main...HEAD` → **`0 0`**. **Codex
  erneut geprüft und weiter gesperrt** (live „try again at Oct 15th, 2026") →
  gebaut wurde mit Hermes-Subagenten.
  - **Werkzeug:** `tools/foto_sortierung/foto_sortieren.py` (**1.149 Zeilen**),
    Tests `backend/tests/test_foto_sortieren.py` (**1.086 Zeilen, 119
    Testfunktionen**, alles offline, `tmp_path`, kein Netz, keine echten Namen).
    Es baut den **Plan** (Ordnerkette + Züge) und führt **nichts** aus: keine
    schreibende pCloud-Operation, kein Manifest-Eintrag, kein Download; Tests
    prüfen die Abwesenheit von Löschfunktionen und von `trocken=False`.
  - **Prüfbefehl selbst gefahren:** `pytest tests/ -q` → **879 passed, Exit 0**
    (Baseline vor diesem Schritt 760).
  - **Live-Trockenlauf (nur lesend, `listfolder` über die 7 Quellordner):**
    **9.430 Zeilen · 2.127 Anlässe · 7.616 Züge, alle mit Dateikennung** ·
    Doppelungen **1.534 in der CSV** (866 ohne Anlass-ID, **668** in geplanten
    Anlässen übersprungen) · **1.146 Zeilen ohne Anlass-ID** übersprungen ·
    0 ohne Thema · 0 ohne Jahr · **2.108 Ordner neu / 82 vorhanden** ·
    **2.088 Events neu / 39 wiederverwendet** · **11 Kategorien** belegt ·
    je Jahr 2014:1 2016:1 2017:1 2019:27 2020:36 2021:95 2022:408 2023:447
    2024:430 2025:380 2026:301. Plan: `~/foto_sortierung/sortierplan.json`
    (außerhalb des Repos, 5,6 MB).
  - **Der wichtigste Eigenbefund:** die **39 wiederverwendeten Events** treffen
    genau die **39 sicheren Vorschläge** aus N6e — die beiden Werkzeuge greifen
    also ohne Zusatzlogik ineinander.
  - **Die 1.146 Zeilen ohne Anlass-ID sind eine echte Lücke, nicht ein Fehler:**
    sie haben **kein Datum im Namen** (z. B. `ServicePW.jpg`), bestehen zu 1.011
    aus dem Wurzelordner eines zweiten Geräts und zu 866 aus Doppelungen. Damit
    bleiben **12,2 % der Dateien** im Trockenlauf liegen. **Entscheidung:** nicht
    raten, nicht in einen Sammelordner werfen — als eigener Punkt für Sebastian
    vor N8 notiert (`Ohne-Datum`-Ablage wäre eine eigene Regel).
  - **Prüfer Runde 1: NICHT BESTANDEN, beide Punkte berechtigt.** (1) Die
    Konsole nannte nur `668` Doppelungen, obwohl die CSV **1.534** gefüllte
    `doppelung`-Felder hat (866 davon in Zeilen ohne Anlass-ID) — irreführend,
    weil die Zahl wie die Gesamtzahl aussah. Behebung: Zähler aufgeschlüsselt
    (`doppelung_gesamt` 1.534 · `doppelung_ohne_anlass` 866 ·
    `doppelung_uebersprungen` 668) und die Konsole nennt jetzt alle drei Zahlen;
    **die Züge (7.616) und Anlässe (2.127) blieben dabei unverändert**. (2) Eine
    wirkungslose Assertion (`… or True`) in den Tests, ersetzt durch eine echte
    Prüfung (Datei im Repo entsteht nicht) + **7 neue Tests** für die
    Aufschlüsselung.
  - **Prüfer Runde 2 (frischer Kontext): BESTANDEN — „Abweichungen: keine."**
    Der Prüfer hat alle Zahlen unabhängig gegen die CSV nachgerechnet
    (9.430 / 8.284 / 1.146 / 1.534 / 866 / 668 / 7.616, Invariante
    `9.430 − 1.146 − 668 = 7.616`), den Prüfbefehl selbst gefahren (879/Exit 0),
    die Aufschlüsselung als getestet bestätigt, die Verbotsliste und den
    Datenschutz-Vergleich geprüft (nur die erlaubten Ausnahmen: blanke
    Kalenderjahre und die generischen Bucket-Namen aus N6d).
  - **Schutz:** `~/foto_sortierung/manifest.jsonl` **nicht vorhanden (0
    Einträge)** — der Trockenlauf bucht nichts; md5 der Eingaben unverändert,
    u. a. Original-Sortierschlüssel `70642d2988b6e38ff417561ccf870ba8`;
    pCloud ausschließlich lesend; Ausgaben nur außerhalb des Repos.
  - Doku: `docs/changelog-2026-09-27-sortieren-trockenlauf.md`,
    Feinauftrag `docs/auftrag-n7-sortieren-trockenlauf.md`.
  - **Nächster Schritt: N8** (echtes Sortieren) — **Vorbehalt:** der Plan legt
    **2.108 neue Ordner** an und verschiebt **7.616 Dateien**; das ist die erste
    schreibende Operation am Bestand. Sie gehört erst nach Sebastians Blick auf
    die 39 sicheren Event-Vorschläge und die 1.146 datumslosen Dateien. Bis
    dahin kann **N9** (Personen-Stufe vorbereiten, andere Dateien) weiterlaufen.
* **27.09. ~14:45 — N9a gebaut, geprüft und bestanden** (Planer: Hauptagent ·
  Ausführer: Hermes-Subagent `deepseek-v4.1-flash`, 0,038 USD · Prüfer:
  `openai/gpt-5.6-luna`, zwei Runden — **andere Modellfamilie**).
  Beginn wie in den Runden zuvor: `git pull --rebase` scheiterte an den **fremden**
  Dateien des zweiten Agenten (`docs/experimente/live_zahlen.*`, zwei neue
  Recherche-HTML); nichts angefasst, nichts gestasht; `git fetch` +
  `git rev-list --left-right --count origin/main...HEAD` → **`0 0`**. **Codex
  erneut geprüft und weiter gesperrt** (live „try again at Oct 15th, 2026") →
  gebaut wurde mit einem Hermes-Subagenten.
  - **Warum nicht N8:** der Echtlauf ist gesperrt, bis Sebastian die 39 sicheren
    Event-Vorschläge und die 1.146 datumslosen Dateien angesehen hat (Plan-Zeile
    N8). N9 läuft laut Plan parallel — **eine schreibende Operation am Bestand
    gibt es hier nicht**, das Werkzeug rechnet nur auf Zahlen.
  - **Aufklärung am PC (gemessen, nicht behauptet):** `backend/.venv` hat
    `numpy 2.4.6` und `PIL 12.3.0`, aber **kein** `cv2`/`onnxruntime`/`sklearn`/
    `insightface`; die Modelle (`face_detection_yunet_2023mar.onnx`,
    `face_recognition_sface_2021dec.onnx`) liegen **nicht im Repo** — der Pfad in
    `backend/face_infer.py` zeigt auf **Termux**. In einer **Wegwerf-Umgebung**
    (nicht im Projekt-venv!) aufgelöst: `onnxruntime 1.30.0` +
    `opencv-contrib-python 5.0.0.93` wären am PC installierbar, `numpy 2.4.6`
    bliebe unverändert. Daraus die Zweiteilung **N9a (Verfahren, heute) →
    N9b (echte Erkennung)** — dieselbe Aufteilung wie damals N6 → N6b.
  - **Werkzeug:** `tools/foto_sortierung/personen_cluster.py` (**1.510 Zeilen**)
    mit den zehn verlangten Funktionen (Mengen-/Gruppen-Entscheidung,
    Vordergrund-Prüfung gegen den Katalog, Clustering **ohne sklearn**, stabile
    Kennungen `Person_001`…, Referenzseiten über eine **eingesteckte**
    Kachelquelle) und `backend/tests/test_personen_cluster.py` (**1.590 Zeilen,
    216 Testfunktionen**, alles offline, `tmp_path`, keine Bilddatei, kein Netz).
    Eingabe ist das **Vektorformat, das `backend/face_infer.py` schon liefert**
    (YuNet-bbox + 128-dim SFace) — deshalb braucht das Werkzeug kein OpenCV.
  - **Prüfbefehl selbst gefahren:** Baseline **879** → **1095 passed, 3 warnings,
    Exit 0** (74,5 s; +216 = genau die neuen Testfunktionen). Zweiter Lauf nach
    den Prüfer-Korrekturen: **1095 passed, Exit 0** (72,70 s).
  - **Live-Stichprobe (ausdrücklich SYNTHETISCH, kein Foto, kein pCloud-Aufruf):**
    83 Bilder / 221 Gesichter aus einem Seed. Eingebaut **12** Personen-Cluster
    (Größen 5,5,6,6,5,7,5,5,9,6,9,8) → gefunden **12** Gruppen mit **identischen**
    Größen; **12/12 = 100 %**, **0** falsch zusammengelegt, **0** übersehen,
    **0** von 4 Rausch-Gesichtern in einer Gruppe. **Die Pflichtprüfung des
    Plans:** 3 Massen-Bilder mit zusammen **141 kleinen Gesichtern** → Art
    `menge`, `clustern: False`, **keine** Gruppe, **keine** Referenzseite;
    dasselbe Bild mit einem großen Katalog-Gesicht → `clustern: True` mit der
    bekannten Kennung. `--schreiben`: 14 Referenzseiten + `kennungen.json`
    (12 Kennungen); 2. Lauf **0** neue Seiten, 12 Kennungen wiederverwendet
    (Idempotenz über die CLI, nicht nur im Test). Repo-Schutz live: Ausgabeordner
    im Repo → deutsche Meldung + **Exit 2**, nichts angelegt.
  - **Prüfer Runde 1: NICHT BESTANDEN — eine Beanstandung, berechtigt.** Der
    **Eigner-Name** stand an fünf Stellen der neuen Dateien (Werkzeug 7/1021,
    Changelog 64/154/199); mein Feinauftrag verbietet Personennamen wörtlich.
    Zum Einordnen, **ohne** die Beanstandung zu entkräften: betroffen war nur der
    Eigner-Name (projektweit in `AGENTS.md`/`CLAUDE.md`), **keine fotografierte
    Person**; in den Tests kam kein Name vor. **Korrigiert** → „der Nutzer".
  - **Prüfer Runde 2 (frischer Kontext, verschärftes Kriterium: Verbot gilt für
    Namen Dritter/Orte/Ereignisse): BESTANDEN — „Abweichungen: keine."** Er hat
    den Prüfbefehl selbst gefahren (1095/Exit 0), die Korrektur nachgezählt
    (`Sebastian` 0 Treffer), die **volle Namensprüfung** gefahren (50 Vornamen,
    Städte/Regionen, Veranstaltungsnamen, Bestandsordner-Muster → überall
    **0 Treffer**), bestätigt, dass der Zweig `menge_mit_bekannter_person` über
    die **öffentliche** Funktion erreichbar ist (Test Zeile 343, Assertion 352),
    und die Zeilen nachgezählt (1.510 / 1.590 / 225).
  - **Eigene Stichprobe des Prüfers (Runde 1, anderer Seed):** 8 Cluster à 5
    Vektoren, 2 Rauschpunkte, Massenbild mit 40 kleinen Gesichtern → **8/8
    Gruppen**, 0 falsch zusammengelegt, 0 übersehen, Rauschen verworfen,
    Massenbild `clustern: False`, mit großem Katalog-Gesicht `clustern: True,
    personen: ["Person_003"]`, 2. CLI-Lauf 0 neue Seiten und dieselben Kennungen.
  - **Schutz:** kein pCloud-Aufruf, keine Bilddatei angefasst (Test prüft die
    Abwesenheit von Lösch-, Netz- und pCloud-Funktionen), keine Vektorwerte in
    Ausgaben, kein Schreiben ins Repo; alle Ausgaben liegen außerhalb
    (`~/foto_sortierung/personen_probe/` – synthetisch, sowie
    `~/foto_sortierung/pruefer_n9a/`). Biometrie bleibt lokal.
  - Doku: `docs/changelog-2026-09-27-personen-verfahren.md`,
    Feinauftrag `docs/auftrag-n9-personen-verfahren.md`.
  - **Nächster Schritt: N9b** (echte Erkennung: Modelle auf den PC bzw. auf dem
    Handy rechnen, `cv2`/`onnxruntime` im **eigenen** venv, Jahres-Stapel messen,
    `kachel_holen` an den echten Weg anstecken) — **N8 bleibt gesperrt**, bis
    Sebastians Blick auf die 39 Event-Vorschläge und die 1.146 datumslosen
    Dateien da ist.
* **27.09. ~16:20 — N9b gebaut, echt gemessen und bestanden** (Planer: Hauptagent ·
  Ausführer: Hermes-Subagent `deepseek-v4.1-flash`, 0,019 USD · Prüfer:
  `openai/gpt-5.6-luna`, zwei Runden — **andere Modellfamilie**).
  Beginn wie in den Runden zuvor: `git pull --rebase` scheiterte an den **fremden**
  Dateien des zweiten Agenten (`docs/experimente/live_zahlen.*`, zwei neue
  Recherche-HTML); nichts angefasst, nichts gestasht; `git fetch` +
  `git rev-list --left-right --count origin/main...HEAD` → **`0 0`**. **Codex
  erneut geprüft und weiter gesperrt** (live „try again at Oct 15th, 2026") →
  gebaut wurde mit einem Hermes-Subagenten.
  - **Der Modellweg am PC steht:** eigenes venv `~/foto_sortierung/venv_gesicht`
    (Python 3.12.10) mit `opencv-contrib-python 5.0.0.93`, `onnxruntime 1.30.0`,
    `numpy 2.5.3` — das **Projekt-venv bleibt unberührt** (es hat weiterhin kein
    `cv2`). Die beiden Modelle (**YuNet 232.589 B, SFace 38.696.353 B**) sind
    **öffentliche** Dateien aus dem OpenCV-Zoo, liegen außerhalb des Repos in
    `~/foto_sortierung/ml_models/` und kommen **nicht** ins Repo. Funktionsnachweis
    vor dem Bau: öffentliches Testbild 512×512 → 1 Gesicht, bbox
    `[207.8, 182.5, 145.9, 206.9]`, score 0.909, Embedding `(1, 128)`, Norm 2.3436.
  - **Werkzeug:** `tools/foto_sortierung/gesicht_erkennen.py` (**835 Zeilen**) +
    `backend/tests/test_gesicht_erkennen.py` (**850 Zeilen, 80 Testfunktionen**,
    alles offline mit eingestecktem Attrappen-Detektor, kein `cv2`, kein Netz) +
    echte pCloud-Kachelquelle für `personen_cluster.referenzseiten_bauen`.
    Die EXIF-Orientierung wird aus `backend/face_infer.py` **wiederverwendet**
    (nicht nachgebaut), `cv2`/ONNX werden erst beim Rechnen geladen.
  - **Prüfbefehl selbst gefahren:** Baseline **1095** → **1175 passed, 3 warnings,
    Exit 0** (74,4 s; +80 = genau die neuen Testfunktionen). Der Commit-Hook hat
    dasselbe Tor beim Commit noch einmal gefahren (1175, Exit 0).
  - **Echte Messung am Bestand** (`~/foto_sortierung/n9b_messung.py`, **nur
    lesend**, Originale ausschließlich **im Arbeitsspeicher**, nichts davon auf
    Platte): Stichprobe A 16 Bilder aus 2020 (über das Jahr verteilt), Stichprobe
    B 8 Bilder aus dem bilderstärksten Anlass mit Mengen-Thema → **24 Bilder,
    0 Fehler, 88,4 s**. **72 Gesichter auf 19 der 24 Bilder** (5 ohne Gesicht);
    kleinstes Gesicht **16×22 px**, größtes **521×603 px**; **30** Gesichter
    ≥ 0,5 % Flächenanteil, **21** unter 0,05 %, **21** dazwischen.
  - **Verfahren N9a auf den echten Vektoren:** `leer 8 · gruppe 12 · menge 0 ·
    unklar 4` → **12 Bilder geclustert**, **2 Gruppen (Größen 6 und 40)**,
    2 neue Kennungen, 0 bekannte Personen. **6 Referenzseiten** mit **echten
    Gesichtsausschnitten** (59–102 KB) nach `~/foto_sortierung/personen_echt/`,
    **zweiter Lauf 0 neue Dateien** (Idempotenz am echten Bestand).
    Vektorzeilen `~/foto_sortierung/personen_vektoren.jsonl` (**221.698 Bytes,
    24 Zeilen**) — das Eingabeformat von N9a; Kennungs-Altbestand geschrieben.
  - **Der ehrliche Befund:** die **Mengen-Regel greift** — die beiden
    Konzert-Bilder werden **nicht** geclustert und **nicht** angelernt —, aber über
    den Zweig **`leer`**, nicht `menge`: die winzigen Ferngesichter liegen **unter**
    `ANTEIL_MIN` (0,05 % der Bildfläche) und fallen damit ganz heraus. Das Ergebnis
    ist das gewollte, der Zweig `menge` wurde am echten Foto aber **nicht** erreicht.
    **Entscheidung: `ANTEIL_MIN` wird nicht angetastet** (das ist ein N9a-Beschluss
    mit eigenen Tests; eine Schwellenänderung braucht eigene Messung) → als
    **N9c** in den Plan aufgenommen, zusammen mit dem zweiten Punkt: die
    ausgelieferte `kachel_quelle` gibt die **ganzen** Fotobytes zurück, für die
    Personenstufe wäre der **Gesichtsausschnitt** die bessere Kachel (der Messlauf
    hat deshalb zugeschnitten, in-memory).
  - **Prüfer Runde 1: NICHT BESTANDEN — eine Beanstandung, Fehlalarm.** Gemeldet
    wurde ein „echter Ereignisname" im Changelog; die geprüfte Zeichenkette ist ein
    **Eintrag des Themen-Katalogs** aus N6c (`themen_katalog.py`, seit `92b04c3`
    im Repo). Alles andere hat der Prüfer **selbst** bestätigt: Prüfbefehl 1175/Exit 0,
    80 Testfunktionen, eigene Formatprüfung (`zeile_pruefen` akzeptiert die Zeile),
    eigener CLI-Trockenlauf (Exit 0, nichts geschrieben), **alle Messzahlen aus der
    JSONL selbst nachgerechnet** (24/72/19/21/21/30, 16×22 px, 521×603 px,
    221.698 Bytes), 6 Referenzseiten mit ihren Größen, Commit enthält genau vier
    Dateien, `0 0`. Die fremden `live_zahlen`-Dateien hat er ausdrücklich als
    **nicht** im Commit bestätigt.
  - **Korrektur + Prüfer Runde 2 (auf dem korrigierten Stand): BESTANDEN.** Die
    missverständliche Stelle im Changelog ist jetzt als Katalog-Eintrag
    gekennzeichnet (mit Beleg-Commit) — nicht die Aussage, sondern die
    Bezeichnung war unklar. **Nachtrag zum Ablauf, ehrlich notiert:** der
    Journal-Eintrag zu Runde 2 stand schon im Commit `8cf11d7`, **bevor** die
    Runde 2 gefahren war — die Aussage war also zum Zeitpunkt des Commits noch
    nicht belegt. Die Runde 2 wurde danach gefahren und hat sie bestätigt; die
    Reihenfolge war trotzdem falsch und wird hier offengelegt, damit die Doku
    nachvollziehbar bleibt.
  - **Prüfer Runde 2 (`gpt-5.6-luna`, frischer Kontext, präzisiertes Kriterium:
    generische Katalog-Einträge und blanke Kalenderjahre sind keine Namen):
    BESTANDEN, 0 Abweichungen.** Er hat selbst nachgerechnet und geprüft:
    Prüfbefehl **1175 / Exit 0**; `Konzert und Buehne` als Katalogeintrag
    (`themen_katalog.py` Zeile 119, Commit `92b04c3`) bestätigt und die
    Runde-1-Beanstandung damit als erledigt bewertet („kein Gegenbeleg");
    Datenschutz-Scan der fünf Dateien **0 Treffer** (ausgefiltert: Kalenderjahre
    2019/2020/2021/2022/2024/2025/2026 und generische Katalog-/Sachbegriffe,
    jeweils benannt); Commit `e41f2b1` = **genau vier** Dateien, keine
    `live_zahlen`-Dateien; `0 0`; **alle** Messzahlen aus der JSONL nachgerechnet
    (24 / 72 / 19 / `leer 8 · gruppe 12 · menge 0 · unklar 4` / Gruppen 6 und 40 /
    221.698 Bytes / 24 Zeilen / kleinste 16×22 px / größte 521×603 px /
    21 · 21 · 30 Flächenanteile) und `personen_echt/` mit **genau 6** Dateien.
    Eigener Zweifel des Prüfers (offen notiert): aus dem Dateisystem allein ließ
    sich nicht beweisen, dass die älteren Bildordner (`boegen/`,
    `personen_probe/`, `pruefer_n9a/`) keine Eingabekopien enthalten — für den
    N9b-Lauf fand er jedoch **keinen** Beleg für neue Originalkopien.
  - **Schutz:** pCloud nur **lesend**; Bilder **nie** auf Platte (geschrieben
    wurden nur die Vektorzeilen als Text, die Referenzseiten als Produkt der
    Personenstufe und der Kennungs-Altbestand — alles **außerhalb** des Repos);
    kein Löschen, keine Geheimnisse in Ausgaben oder Dateien; `manifest.jsonl`
    weiterhin **0 Einträge**.
  - Doku: `docs/changelog-2026-09-27-gesicht-erkennen.md`,
    Auftrag `docs/auftrag-n9b-gesicht-erkennen.md`.
  - **Nächster Schritt: N9c** (Mengen-Zweig am echten Foto erreichbar machen +
    Gesichtsausschnitt-Kachel) — **N8 (echtes Sortieren) bleibt gesperrt**, bis
    Sebastians Blick auf die 39 sicheren Event-Vorschläge und die 1.146
    datumslosen Dateien da ist. Commit `e41f2b1`, gepusht, `0 0`.
* **27.09. ~18:05 — N9c gemessen, gebaut und bestanden** (Planer: Hauptagent ·
  Ausführer: Hermes-Subagent `deepseek-v4.1-flash`, 0,025 USD · Prüfer:
  `openai/gpt-5.6-luna`, **eine** Runde — **andere Modellfamilie**).
  Beginn wie in den Runden zuvor: `git pull --rebase` scheiterte an den **fremden**
  Dateien des zweiten Agenten (`docs/experimente/live_zahlen.*`, zwei neue
  Recherche-HTML); nichts angefasst, nichts gestasht; `git fetch` +
  `git rev-list --left-right --count origin/main...HEAD` → **`0 0`**. **Codex
  erneut geprüft und weiter gesperrt** (live „try again at Oct 15th, 2026") →
  gebaut wurde mit einem Hermes-Subagenten.
  - **Erst gemessen, dann entschieden (Planer, nur lesend):** eigene Vormessung
    über **30 Bilder** aus den fünf bilderstärksten Mengen-Anlässen (Themen
    „Konzert und Buehne", „Fest und Feier"), `~/foto_sortierung/n9c_probe.py`,
    **87,7 s, 0 Fehler**. Ergebnis über fünf Kandidaten für `ANTEIL_MIN`:
    **0,0005 (alt) → `gruppe 12 · leer 9 · unklar 9 · menge 0`**;
    **ab 0,0001 → `gruppe 12 · leer 6 · unklar 11 · menge 1`** und bei 0,00005 /
    0,00002 / 0,00001 **unverändert** (die Verteilung ist damit ausgemessen).
    Kleinste **echte** Detektion der Stichprobe: Anteil **0,000145**
    (13 kleine Gesichter auf 4032×3456); kleinste echte Detektion des Nachtlaufs
    (N9b): **0,000022** (16×22 px auf 4608×3456). Damit war belegt: das alte
    Flächen-Tor verwarf **echte** Funde, es war kein Rausch-Tor.
  - **Teil 1 umgesetzt:** `ANTEIL_MIN` **0,0005 → 0,00001** (1 × 10⁻⁵ ≈ 11×11 px
    bei 12,2 MP = praktisch **YuNets eigene Mindest-Box** 10×10 px). Der
    Kommentar sagt jetzt ehrlich: das Flächen-Tor verwirft nur **entartete
    Boxen**, das Rausch-Tor ist `MIN_SCORE = 0,6`. **Keine andere Schwelle
    angefasst** (`MENGE_ANZAHL = 6` bleibt — N9a-Beschluss, braucht eigene
    Messung).
  - **Teil 2 umgesetzt:** `kachel_quelle(..., ausschnitt=True, rand=0.45)`
    schneidet **in-memory** um das Gesicht (Rand 0,45 × bbox je Seite, an die
    Bildgrenzen geklemmt, auf 200×200 skaliert) — **nur PIL**, kein `cv2`, kein
    Netz, **kein** Schreiben auf Platte; reine, ohne Bild prüfbare Funktion
    `ausschnitt_rechnen(bbox, breite, hoehe, rand)`; **Rückfall aufs ganze Foto
    statt Abbruch** (ohne/unbrauchbar `bbox`, kaputte Bytes, fehlendes PIL);
    CLI-Schalter `--ausschnitt`, Standard bleibt ganzes Foto.
  - **Prüfbefehl selbst gefahren (Planer):** `pytest tests/ -q` → **1196 passed,
    Exit 0** (79,4 s; Baseline 1175). Der Prüfer hat ihn ebenfalls selbst
    gefahren: **1196 / Exit 0**.
  - **Echte Messung nach der Änderung (Ausführer, Belege
    `~/foto_sortierung/n9c_belege.txt`, 86,8 s, 0 Fehler):** dieselben 30 Bilder
    **alt `gruppe 12 · leer 9 · unklar 9 · menge 0`** gegen **neu
    `gruppe 12 · leer 6 · unklar 11 · menge 1`**. Vier Bilder wechseln die Art:
    Bild A `leer`→`unklar` (3 nutzbare), Bild B `leer`→`unklar` (1), Bild C
    `leer`→`unklar` (5), **Bild D `unklar`→`menge`** (13 nutzbare, **0**
    erkennbare). Das **`menge`-Bild** (Kennungen der Bilder stehen hier
    absichtlich **nicht**),
    4032×3024, 13 kleine Gesichter, kleinster Anteil **0,000145**, größter
    **0,001911** (< `ANTEIL_ERKENNBAR` 0,005), `clustern: False`,
    `grund: menge_ohne_bekannte_person`. **Ehrlich: der Zweig ist an 1 von 30
    Bildern erreicht** — das erfüllt das Prüfkriterium, ist aber **kein** Beleg
    für generelles Greifen; so steht es auch im Changelog.
  - **Referenzseiten mit `--ausschnitt`** (Ausgabe außerhalb des Repos,
    `~/foto_sortierung/personen_echt_ausschnitt/`): **7 Seiten, 552.443 Bytes**,
    **54 Kacheln alle 200×200** (0 leer, 0 andere Größe), Pixelgegenprobe an
    einem Eintrag (Original 4096×3072, Grenzen (1074,993,2064,2140), gleiche
    Form); **zweiter Lauf 0 neue Dateien**. Ohne `--ausschnitt` sind die Seiten
    kleiner und anders (7.984 Bytes) — der Schalter wirkt wirklich.
  - **Prüfer (`gpt-5.6-luna`, frischer Kontext): BESTANDEN, „Abweichungen:
    keine."** Er hat selbst geprüft und nachgerechnet: Prüfbefehl 1196/Exit 0;
    nur `ANTEIL_MIN` geändert, alle übrigen Schwellen **wertgleich** zu HEAD;
    die Geometrie mit **eigenen Aufrufen** (Rand, Klemmung, `None` bei entarteter
    Box, Rückfall bei kaputten Bytes); Testfunktionen **216 → 219** bzw.
    **80 → 98**; die Mengen-Zahlen vorher/nachher aus der Belegdatei; und eine
    **synthetische Gegenprobe**: alte Schwelle → `leer`, neue → `menge`
    (20×20-Box, Anteil 0,0000328). Er hat außerdem bestätigt, dass die offenen
    Punkte **im Changelog stehen** (u. a. „1 von 30").
  - **Ehrlich offen gelassen (als N9d in den Plan):** (1) im Vektorzeilen-Lauf
    übergibt `main` nur die `fileid` — `kachel_quelle` liest zwar `fileid`, die
    N9a-Einträge tragen die Kennung aber als `bild_id` (und die `bbox` fehlt
    dort ganz), deshalb wirkt `--ausschnitt` in diesem Lauf **noch nicht**; die
    Verdrahtung gehört in den nächsten Schritt. (2) Die Referenzseiten dieses
    Laufs rechneten auf den **alten** 24 N9b-Vektorzeilen — dort entsteht kein
    `menge`-Bild; der Vektorlauf gehört mit dem neuen `ANTEIL_MIN` wiederholt.
  - **Schutz:** pCloud nur **lesend**; Originale nur im Arbeitsspeicher, **kein**
    Bild auf Platte außerhalb der Ausgabeordner; `manifest.jsonl` weiterhin
    **0 Einträge**; kein Löschen; keine Geheimnisse in Ausgaben oder Dateien;
    die fremden `live_zahlen`-Dateien blieben unberührt.
  - Doku: `docs/changelog-2026-09-27-mengen-zweig.md` (neu),
    Auftrag `docs/auftrag-n9c-mengen-zweig.md` (neu).
  - **Nächster Schritt: N9d** — `bbox`/`bild_id` in der Kachelquelle verdrahten
    (Gesichtsausschnitt wirklich nutzbar) und den N9b-Vektorlauf mit dem neuen
    `ANTEIL_MIN` wiederholen (breitere Mengen-Stichprobe, damit „1 von 30" zu
    einer belastbaren Zahl wird). **N8 (echtes Sortieren) bleibt gesperrt**, bis
    Sebastians Blick auf die 39 sicheren Event-Vorschläge und die 1.146
    datumslosen Dateien da ist.
* **27.09. ~21:10 — N9d verdrahtet, breit gemessen und bestanden** (Planer:
  Hauptagent · Ausführer: Hermes-Subagent `deepseek-v4.1-flash`, 0,008 USD ·
  Prüfer: `openai/gpt-5.6-luna`, **drei Runden**, andere Modellfamilie).
  Beginn wie in den Runden zuvor: `git pull --rebase` scheiterte an den
  **fremden** Dateien des zweiten Agenten (`docs/experimente/live_zahlen.*`,
  zwei Recherche-HTML); nichts angefasst, nichts gestasht; `git fetch` +
  `git rev-list --left-right --count origin/main...HEAD` → **`0 0`**. **Codex
  erneut gesperrt** (Kontingent bis 15.10.) → gebaut wurde mit einem
  Hermes-Subagenten.
  - **Teil 1 (Verdrahtung):** `_fileid_von` liest `fileid`, sonst **`bild_id`**
    (Text/Zahl, kein `bool`/`None`; `fileid` hat Vorrang). Damit gehen die
    **N9a-Einträge ohne Um-Mappen** in die echte pCloud-Kachelquelle — der Hack
    aus N9c (`bild_id` → `fileid` im Belegskript) ist nicht mehr nötig.
    Dazu die **ehrliche** Ausgabe: neue reine Funktion
    `kachelquelle_hinweis(ausschnitt)` ersetzt in `main` die Behauptung „es wird
    je Gesicht geschnitten"; sie sagt wahrheitsgemäß, dass im
    **Vektorzeilen-Lauf vor dem Download keine `bbox` bekannt** ist und
    `--ausschnitt` dort **nicht wirkt** (er wirkt im Referenzseiten-Weg von
    `personen_cluster`, wo die Einträge `bild_id` + `bbox` tragen). Keine
    Schwelle angefasst.
  - **Prüfbefehl selbst gefahren:** **1205 passed, Exit 0** (80 s; Baseline
    1196, +9 neue Tests); der Commit-Hook fährt dasselbe Tor beim Commit.
  - **Teil 2 (breite Messung, echte Bilder, nur lesend):** **92 Bilder** — 80
    aus den acht bilderstärksten Mengen-Anlässen (je bis zu 10) + **12
    Kontrollbilder**; **465 Gesichter auf 72 Bildern, 0 Fehler, 358,9 s**;
    kleinster echter Flächenanteil **0,00000689** (= 6,89 × 10⁻⁶), größter 0,030437.
    **Ergebnis (vorher → nachher):** alle 92: alt `gruppe 32 · leer 27 ·
    menge 4 · unklar 29` → neu `gruppe 32 · leer 20 · **menge 10** · unklar 30`;
    **nur Mengen-Bilder: 4 → 10 von 80** (N9c war „1 von 30" = 3,3 %, jetzt
    **12,5 %**); **Kontrollbilder in beiden Schwellen 0 × `menge`** (gruppe 4,
    leer 7, unklar 1); `gruppe` **unverändert 32** = keine Regression.
  - **Verdrahtung live belegt** (`n9d_verdrahtung.py` in einen frischen Ordner,
    N9a-Einträge **direkt**, kein Um-Mappen): **24 Referenzseiten**, **186
    Kacheln als 200×200-Ausschnitt**, 3 leere (Download-Fehler → Platzhalter),
    **1.749.798 Bytes** gesamt, **2. Lauf 0 neue Dateien** (idempotent).
    **Pixel-Gegenprobe an vier Kacheln:** Abstand zum frisch gerechneten
    Ausschnitt **1,755 … 3,116** (das ist der JPEG-Verlust bei quality 85), zum
    verkleinerten **ganzen Foto** dagegen **68,954 … 76,192** — die Kachel zeigt
    also wirklich den Gesichtsausschnitt.
  - **Ehrlicher Nebenbefund (nicht Teil des Schritts):** das DBSCAN-artige
    `vektoren_clustern` (Dichte-Verfahren, `CLUSTER_SCHWELLE = 0,45`) bündelt
    die **189** nutzbaren Gesichter der `gruppe`-Bilder zu **einer** Gruppe —
    beim Dichte-Verfahren ist Verkettung erwartbar, am echten Bestand aber
    **nicht** mit Bodenwahrheit geprüft → neuer Kandidat **N9e** (Zeile im
    Plan). Schwellen sind N9a-Beschlüsse, hier bewusst nicht angetastet.
  - **Prüfer Runde 1: NICHT BESTANDEN — drei Punkte, zwei davon berechtigt.**
    (1) Das N9d-Belegskript löschte den eigenen Ausgabeordner per
    `shutil.rmtree` — Verstoß gegen „NIE löschen": jetzt **verweigert** es einen
    nicht leeren Zielordner (deutsche Meldung, **Exit 2**, Zielordner per
    Argument); nachgemessen **24 Dateien vor und nach** dem Aufruf, der Lauf
    wurde in einen **frischen** Ordner wiederholt (identische Zahlen), der alte
    blieb unberührt. (2) Meine Angabe „`manifest.jsonl` weiterhin 0 Einträge"
    war falsch — die Datei **existiert nicht**, weil nichts gebucht wurde.
    (3) Der Modulkopf-Docstring war geändert, ohne dass ich das dem Prüfer als
    Umfang genannt hatte (im Auftrag stand es).
  - **Prüfer Runde 2: NICHT BESTANDEN — ein berechtigter Rest, zwei Fehlalarme
    bzw. Aufruf-Fehler.** (1) Berechtigt: das **ältere** N9c-Belegskript
    enthielt noch `shutil.rmtree` → gleich behoben (Verweigerung + Exit 2,
    `shutil` entfernt; nachgemessen **7 → 7 Dateien**). Damit gibt es im ganzen
    Foto-Werkzeugsatz nur noch **eine** Löschoperation: `os.remove(temp)` auf die
    **eigene temp-Datei** beim atomaren Schreiben (`foto_kategorien.py:641`) —
    fremde Daten werden nirgends gelöscht. (2) Der Eigner-Name im Plan ist
    **Bestand**: 26 × in HEAD, 26 × im Arbeitsstand, **0 × in den neuen Zeilen**
    (`git diff -U0 | grep '^+' | grep -c` = 0) — der Plan zitiert den Auftrag,
    kein Name Dritter; nicht umgeschrieben. (3) Der Aufruf der Belegskripte mit
    **globalem** `python` endet mit Exit 1 (`pydantic_settings` fehlt) — der in
    `CLAUDE_EXTENDS.md` beschriebene **Aufruf-Fehler**, kein Skriptfehler; beide
    Skripte nennen im Kopf jetzt den Aufruf mit `venv_gesicht`.
  - **Prüfer Runde 3 (Abnahme, frischer Kontext, geschärftes Kriterium):
    BESTANDEN, 0 Abweichungen.** Er hat selbst nachgerechnet: Prüfbefehl
    **1205 / Exit 0**; 9 neue Tests; `_fileid_von` in sieben Fällen; beide
    Belegskripte ohne Löschfunktion mit **Exit 2** bei gefülltem Ordner (7 → 7
    bzw. 24 → 24 Dateien); Namenszählung 26/26/**0**; **alle Messzahlen aus der
    JSONL** (92 / 72 / 465 / Minimum / beide Bildarten-Verteilungen / 10 von 80
    = 12,5 % / Kontrollbilder 0 × `menge` / 24 Dateien / 1.749.798 Bytes);
    keine Schwellenänderung, kein `or True`, keine Secrets, keine Bilddateien,
    `git diff --check` ohne Fehler.
  - **Schutz:** pCloud nur **lesend**; Originale nur im Arbeitsspeicher,
    **kein** Bild auf Platte außerhalb der Ausgabeordner; **keine** Buchung
    (`manifest.jsonl` existiert nicht); kein Löschen (alle Belegordner
    existieren weiter); die fremden `live_zahlen`-Dateien blieben unberührt.
  - Doku: `docs/changelog-2026-09-27-n9d-verdrahtung.md`.
  - **Nächster Schritt:** **N9e** (Cluster-Schwelle am echten Bestand mit
    Bodenwahrheit prüfen) — oder, wenn Sebastian den Blick auf die 39 sicheren
    Event-Vorschläge und die 1.146 datumslosen Dateien nachholt, **N8** (echtes
    Sortieren). **N8 bleibt bis dahin gesperrt.**

* **27.09. (Hauptagent, nach Sebastians Frage „Fotos-Fragen am Handy?") — neuer
  Schritt N11:** Endpunkt `/api/fotos/uebersicht` + kleine Datendatei (Zahlen und
  Event-Namen, **ohne Bilder**), damit „wie viele Events gab's?" und „zeig mir die
  Urlaube 2021" auch **im App-Chat am Handy** beantwortet werden. Heute nicht
  möglich: Sortierschlüssel, `themen.jsonl` und `kategorien.json` liegen nur auf
  dem PC. Prüfkriterium: Endpunkt antwortet ohne Netz; Selbsttest zeigt die
  Quelle. *(Nicht in der Schritt-Tabelle oben eingetragen, damit der gleichzeitig
  laufende Nachtlauf sie nicht überschreibt.)*

* **28.09. — N27 (neu, Kern der Sache): Die VERKNÜPFUNGSSCHICHT —
  Ereignis-Objekte, die Chat + Fotos + Menschen + Termin zusammenführen.**
  Wörtlich: „irgendwie wollte ich ja quasi eine Verknüpfung haben, thematisch
  zwischen Chats, Bildern und den Menschen … Das muss ja noch angelernt werden,
  dass man über alles mit dem reden kann und im Bilde ist."
  * **Was schon steht:** Datum + Motiv je Foto (Sortierschluessel, 9.430 Zeilen,
    2.127 Anlässe per Vision, 2,94 $ gemessen) · 245.657 Chat-Nachrichten **mit**
    Datum und Gespräch · 744 Chats/6.242 Gruppenmitglieder auf Kontakte
    abgebildet · 405 Kalendereinträge · 55 Geburtstage.
  * **Was fehlt (das „Anlernen"):** (1) **Personen auf Fotos** — die Gesichts-
    Cluster sind nach dem Merkmal-Fehler als **ungültig** markiert und müssen
    **neu gerechnet** werden; unbekannte Gesichter heißen `Person_001…`, benannt
    wird **nur auf Sebastians Bestätigung** (Massenfotos erzeugen weiterhin
    keine Cluster). (2) **Themen** = Sebastians 18 Kategorien statt der
    erfundenen 53 (N6d). (3) **Event-Namen** über Ordner-/Datumsabgleich (N6e).
  * **Aufbau in dieser Reihenfolge (jeder Schritt mit Prüfkriterium):**
    1. **Ereignis-Knoten** je Anlass: Datum + Ort/Thema + Fotos (Anzahl, Ordner,
       Dateien) — **ohne** Personen, aus dem, was schon da ist.
    2. **Chat-Andockung**: Nachrichten im Zeitfenster ±1 Tag zum Anlass, mit
       Chat-Name + beteiligten Kontakten; Gruppen strenger (±0 Tage, weil dort
       viel Alltagsrauschen ist).
    3. **Kalender-Andockung**: passende Termine (auch Geburtstage, jährlich
       wiederkehrend).
    4. **Personen-Andockung**: Gesichts-Cluster (neu gerechnet) + im Chat
       genannte Namen + Sebastians Bestätigung → `Person_00x` wird zu „Philine".
    5. **Ableitung „wer war mit wem wo"** — nur aus bestätigten Zuordnungen,
       nie geraten: jede Aussage nennt **Datum + Quelle**.
  * **Ablage:** `~/foto_sortierung/ereignisse.jsonl` (privat, außerhalb des
    Repos), je Zeile ein Ereignis; **nur Daten, keine Bilder**.
  * **Prüfkriterium:** Der Testfall „Schlittschuhlaufen" muss ein Ereignis mit
    Datum, beteiligten Personen (soweit bestätigt) und den Bildern des Tages
    ergeben; eine Frage im Chat („was war am 27.12.2019?") muss antworten, ohne
    zu raten; jede Antwort mit Datum **und** Quelle.

* **28.09. — N26 (neu, aus Sebastians Frage „Schlittschuhlaufen / Planten un
  Blomen"): WhatsApp-Medien als zweite Bildquelle erschließen.** Befund: Auf dem
  Handy liegen **3.660 gesendete + 346 empfangene WhatsApp-Bilder** unter
  `/sdcard/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Images/` — und die
  sind **nicht** in der pCloud (der Ordner wird vom Automatic Upload nicht
  erfasst). Prüfbeispiel: zum Chat-Thema „Schlittschuhlaufen" existieren Bilder
  an **27.12.2019 (1), 27.12.2021 (2), 28.01.2022 (2)**; das Datum steckt im
  Dateinamen (`IMG-JJJJMMTT-WA….jpg`).
  * **Nutzen:** der Chat liefert **Datum + Anlass + Personen**, die Medien
    liefern die **Bilder** dazu → die im Plan geforderte Event-Verknüpfung
    („wer war mit wem wo") wird damit erst möglich.
  * **Einbau:** Medien-Ordner als **zweite Quelle** in die App-Galerie (N13) und
    in den Selbsttest; Anzeige **gestreamt vom Handy**, kein Kopieren in den
    Backend-Speicher (Bild-Regel gilt unverändert); Nachtrag ins **Manifest**
    (nur lesend, nichts verschieben).
  * **Sortierung:** für die Medien gelten dieselben Regeln (Datum aus dem Namen,
    Thema über Vision, Personen nur nach Bestätigung); die WhatsApp-Medien
    bleiben **am Ort** und werden nur **indiziert** (Pfad + Datum + Größe).
  * **Prüfkriterium:** Frage „zeig mir die Bilder vom Schlittschuhlaufen" liefert
    genau die Bilder der genannten Tage; zweiter Lauf fügt **0** Dubletten hinzu;
    kein Medium wird kopiert oder verschoben.

* **28.09. — N15-Messung korrigiert (wichtiger Kostenbefund):** Beschreibungen
  **je Bild** sind viel billiger als die frühere Schätzung („5–9 $ über CLIP").
  Gemessen am bestehenden Weg (Kontaktbogen, 36 Bilder je Aufruf, N5 bestanden:
  Nummern 1–36 sicher lesbar): **0,00128 $ je Aufruf** → 9.430 Bilder ≈ **262
  Aufrufe ≈ 0,34 $**, dazu Einbettungen der Beschreibungstexte ≈ 0,02 $.
  **Beschreibungstexte + Einbettung schlagen ein Bildmodell:** Bild gesucht wird
  dann wie Text („rothaarige Sängerin, Bühne, Menge") — ohne teures CLIP und
  ohne Bild-Vektordatenbank. Umsetzung bleibt N15; die Zahlen hier ersetzen die
  alte Schätzung.

* **28.09. — N25 (neu, Sebastians Auftrag): Automatisches Backup der Archiv-
  Datenbanken in die pCloud.** Wörtlich: „dass wir ein automatisches Backup in
  der Backup-Synchronisation haben, von diesen Archivdatenbanken … dass die auch
  in pCloud gespeichert wird, damit wenn das Handy doch mal weg sein sollte …
  dass unsere ganzen lokalen Daten, die ja nicht in GitHub drin sind, auch noch
  gebackupt sind, weil wir haben ja jetzt auch Geld reingesteckt fürs Trainieren,
  fürs Embedding … und sollte ja auch erhalten bleiben und nicht nur jetzt gerade
  temporär ein Abbild auf dem Handy."
  * **Was wird gesichert:** `archiv_index.db` (Text, FTS, Vektoren),
    `memory.db`, `normalized/messages.jsonl` — also **alles Bezahlte und
    Erarbeitete**, nicht nur die Rohdaten.
  * **Wohin:** pCloud `Agent/Archiv-Backup/` (Schreibrecht besteht nur in
    `Agent/`), Konto in **Europa** — DSGVO-freundlich; zusätzlich **verschlüsselt
    gepackt** (Passphrase im Passwort-Manager), damit Fremdinhalte Dritter auch
    im eigenen Cloud-Speicher nicht offen liegen.
  * **Wann:** im **nächtlichen Lauf auf dem Handy** (N22/N23) — nach Import und
    Index-Ergänzung, **idempotent**: nur hochladen, wenn sich die Dateien
    geändert haben (Vergleich über Prüfsumme/Größe), Namensschema
    `archiv_JJJJ-MM-TT.zip` + Marker `LETZTE.txt`.
  * **Aufbewahrung:** die letzten **3** Generationen + eine **Monatskopie**;
    ältere werden erst nach erfolgreichem Hochladen der neuen entfernt (nie
    vorher) — jede Löschung ins Manifest.
  * **Rückholbarkeit (Pflicht):** Wiederherstellung dokumentiert **und geprüft**
    — neuestes Paket herunterladen, entpacken, Zahlen vergleichen (Nachrichten,
    Chunks, Vektoren, Gespräche). Erst wenn dieser Probelauf grün ist, gilt N25
    als fertig.
  * **Zusätzlich sichern (verschlüsselt, klein):** WhatsApp-Schlüssel und
    Google-Zugang — sonst ist die Sicherung nach einem Geräteverlust nicht mehr
    öffnbar.
  * **Prüfkriterium:** zwei Läufe hintereinander → zweiter lädt **nichts** hoch
    (unverändert); nach einem simulierten Verlust (Ordner umbenennen) ist das
    Archiv aus pCloud **vollständig** wiederherstellbar; Kosten/Größe je Lauf
    protokolliert.

  durchplanen** („wir müssen vielleicht IT-Security-mäßig unsere App bisschen
  noch mehr sichern und vielleicht auch Android mehr sichern … das werden wir
  noch mal durchplanen … können wir auf die Liste setzen. Datenschutz.").
  Themenliste für den Plan (jedes mit Prüfkriterium):
  1. **App/Backend:** API-Schutz statt offenem Heimnetz (Key-Pflicht für alle
     Schreibwege), CORS einschränken, kein öffentlicher Port, Selbsttest ohne
     Geheimnisse (bereits so).
  2. **Android:** Bildschirmsperre + PIN/Länge, App-Berechtigungen prüfen
     (Mikrofon, Dateien), **Android-Backup der Agent-Daten aus**, Termux-Zugang
     absichern, ADB nur bei Bedarf (USB-Debugging aus, wenn nicht gebraucht).
  3. **Datenablage:** Archiv-Datenbank + Gesichts-Katalog + WhatsApp-Schlüssel/
     Token verschlüsselt bzw. mit Dateirechten geschützt; **Handy-Verlust** als
     Ernstfall durchspielen (was liegt lesbar, was nicht?).
  4. **Dritte schützen (DSGVO):** Chats und Fotos enthalten Daten **anderer**
     Personen → Verarbeitung ausschließlich lokal, keine Weitergabe an
     Fremd-LLMs außer der Suchanfrage; **keine Namen Dritter** in Repo, Doku,
     Portfolio, Chat-Protokoll.
  5. **Aufräum-Löschkonzept:** Session-Exporte, Scratch-Dateien, Übergabedateien
     (token.txt/schluessel.txt) → Rechte, Ablaufdatum, Löschroutine.
  6. **Widerruf/Notfall:** pCloud-Token, OpenRouter-Key, Telegram-Bot und
     Google-Zugang widerrufen können; Wiederherstellungsweg dokumentieren.
  **Zeitpunkt:** nach N21/N22 (erst Daten, dann Absicherung) — aber Punkt 4 gilt
  **sofort** bei jedem Schritt.

* **28.09. früh — Betriebsmodell (N23-Ergänzung, Sebastians Frage „PC läuft
  vielleicht nicht immer"):** *Immer-Handy* + *Werkstatt-PC*.
  * **Nächtlich, PC aus:** Handy fährt selbst: WhatsApp-Abzug (Schlüssel+Zugang
    liegen dort), Nachpflege N22, Einbettungen, Suche, App. Laufzeit unkritisch
    (Strom), Bericht beim Widget-Tipp.
  * **Nächtlich, PC an:** zusätzlich die schweren Werkstatt-Jobs (Gesichts-
    Cluster, Massen-Beschreibungen, Erstsortierung) — per Hermes-Cron, Ergebnis
    geht als Übergabedatei aufs Handy.
  * **Kein Besitzanspruch:** Wer zuerst läuft, schreibt; der andere prüft und
    überspringt Vorhandenes (**idempotent**). Kein Job startet, wenn derselbe
    Lauf schon läuft (Sperrdatei mit Zeitstempel).
  * **Bericht morgens:** immer dieselben Felder (neu, übersprungen, Fehler,
    Kosten, Dauer, Gerät).

* **28.09. früh — N23 (neu, Architektur-Regel): alles muss im ANDROID-Ökosystem
  eigenständig laufen.** Wörtlich: „das muss alles auch so gebaut werden, dass es
  innerhalb des Android-Ökosystems eigenständig funktioniert und dass wir Zugriff
  auf diesen PC haben." Umsetzung:
  * **Handy = Ausführer.** Jeder wiederkehrende Job (N22 Nachpflege, N12 Sortier-
    Pflege, Selbsttest, Archiv-/Vektor-Suche, App) läuft **im Termux** und
    überlebt Reboots (`termux-job-scheduler` bzw. `termux-services`/`crond`).
    Kein Cron am PC für Dinge, die das Handy selbst kann.
  * **PC = Werkstatt.** Nur schwere Einmal-Arbeit (Gesichts-Cluster, Massen-
    Beschreibungen, Erstsortierung) läuft am PC; Ergebnisse gehen **per Kabel**
    aufs Handy (bestehendes Muster: Übergabedatei im Download-Ordner, selbst-
    heilende Übernahme beim Widget-Tipp, Datei wird danach gelöscht).
  * **Zugangsdaten müssen auf dem Handy liegen** (pCloud-Token ✓ bereits,
    WhatsApp-Schlüssel ✓, Google-Zugang → nach dem PC-Abzug per Kabel
    übertragen), damit das Handy den nächsten Backup-Abzug **allein** fahren kann.
  * **Prüfkriterium:** Ein nächtlicher Lauf auf dem Handy **ohne eingeschalteten
    PC** liefert dieselben Ergebnisse wie am PC (Zahlenvergleich), und nach
    einem Neustart des Handys läuft der Job von selbst wieder an.
  * **Grenze unverändert:** nur lesen und anhängen; nichts löschen; Medien
    bleiben in der pCloud; Biometrie bleibt lokal.

* **28.09. früh — N22 (neu, Sebastians Wunsch): Nachpflege NACHTLAUF, nicht nur
  wöchentlich.** Wörtlich: „alle Chats, Gruppen, archivierten Chats völlig aus
  dem Lernen … benutzen der Vektordatenbank, des Archivs … dass das sich jede
  Woche durch einen geplanten Job … selbst triggert und neue Chats … oder die
  Weiterentwicklung von Chats dann natürlich dazukommen … vielleicht kann man
  das auch täglich nachts machen". Umsetzung:
  * **Quellen:** WhatsApp (**alle** Chats, **Gruppen** und **archivierte** Chats
    — nur im Backup enthalten, nicht in Einzel-Exporten), neue Fotos/Uploads der
    pCloud, Google Kalender.
  * **Inkrementell + idempotent:** nur Neues/Geändertes; Kennung je Nachricht
    (Zeitstempel + Chat + Kurz-Prüfsumme), **anhängen** statt neu bauen; zweiter
    Lauf am selben Tag findet **0** Neues.
  * **Anhänge:** nur **Metadaten** (Name, Typ, Datum, Größe) — **keine Medien**
    ins Archiv (Speicher + Datenschutz), Medien bleiben in der pCloud.
  * **Zeitplan:** täglich nachts (Standard 03:00, Cron), Bericht je Lauf mit
    Zahlen (neu/übersprungen/Fehler), Kosten protokolliert; schlägt der Lauf
    fehl, bleibt der letzte gute Stand unberührt.
  * **Vektor-Datenbank** läuft mit: neue Chunks werden eingebettet und in
    `archiv_index.db` ergänzt (Index wächst nur, wird nicht neu gebaut).
  * **Grenze:** der nächtliche Lauf liest und indiziert — er **löscht nichts**
    und schreibt nie in die Cloud.
  * **Prüfkriterium:** Erstlauf holt den Rückstand mit Zahlen; zweiter Lauf 0
    neu; eine neue Nachricht in einem **archivierten** Chat erscheint nach dem
    Lauf in der Suche; Kosten je Lauf < 0,05 $.

* **27.09. ~23:40 — N21 (neu, WICHTIGSTER SCHRITT): Vollständiger WhatsApp-Abzug
  OHNE Comet zu schließen.** Befund: Es existieren nur **2 Chats** (42.147
  Nachrichten: Fabia + 9). Der Voll-Abzug scheiterte laut `ARBEITSSTAND.md` an
  Punkt „Offen: Google-`oauth_token` — Comet hält `Default/Network/Cookies`
  gesperrt". **Lösung:** Die Sperre betrifft nur die **Datei**; der **laufende**
  Browser ist über die Debug-Schnittstelle erreichbar (dieselbe, mit der Comet
  gesteuert wird). Also: **kleines Skript**, das über CDP `Storage.getCookies`
  bzw. `Network.getAllCookies` den `oauth_token` für `.google.com` holt und
  **direkt in `whatsapp_uebertragung/token.txt` schreibt** — der Wert darf
  **nie** in Ausgabe, Protokoll, Chat oder Repo erscheinen (nur Länge/Maske
  ausgeben). Danach die Kette: `wabdd token/download → msgstore.db →
  entschlüsseln (Schlüssel liegt vor) → normalisieren → **anhängen** an
  `normalized/messages.jsonl` → Index neu bauen → Einbettungen → Index per Kabel
  aufs Handy → Widget-Tipp`. Prüfkriterium: Zahl der Chats **deutlich > 2**,
  Gruppen enthalten (u. a. „Fabulous 4"), jede Nachricht mit Titel + Zeitstempel;
  Kontakte den Chats zugeordnet; Einbettungskosten protokolliert (< 0,50 $).
  Rückfall, falls der Browser-Weg blockiert: pro Chat „Chat exportieren" (ohne
  Medien) und anhängen — funktioniert ohne jede Google-Anmeldung.
  **Nichts löschen, nur anhängen; Archiv bleibt außerhalb des Repos.**
  **Zwischenstand 28.09. 09:35:** `wabdd` **0.1.7** installiert (`wabdd-venv`,
  Python 3.11.16, `websocket-client` dazu); Abrufskript **`tools/whatsapp/
  token_holen.py`** (liest den Cookie über die Debug-Schnittstelle, schreibt nur
  die Datei, Ausgabe nur ja/nein + Maske; Offline-Test grün). **Edge läuft auf
  Port 9222 mit echtem Profil** (über eine Junction, damit die Flags greifen —
  Chromium 136+ ignoriert `--remote-debugging-port` beim Default-Profil);
  Sebastians Google-Sitzung ist sichtbar (27 Google-Cookies, SID/HSID/SSID/
  SAPISID), **aber `oauth_token` ist noch nicht gesetzt**: der Android-Anmelde-
  Flow (`accounts.google.com/EmbeddedSetup`, Tab „Willkommen") verlangt eine
  frische **Passwort-Bestätigung** — der Wert entsteht erst beim Abschluss.
  **Offen (Sebastian, ~10 s):** im offenen Edge-Tab „Willkommen" das Google-
  Passwort eingeben und „Weiter" — danach `token_holen.py` erneut, dann
  Gegenprobe (`cat token.txt | wabdd token <mail> --token-file token.txt`).
  **Zwei Warnungen für später:** (1) Edge mit echtem Profil **nicht** neu starten
  — kopierte/umbenannte Profilpfade verlieren die Google-Cookies (App-Bound-
  Encryption ab Chromium 151), der Weg funktioniert nur in **dieser** Instanz;
  (2) die Junction im Scratch-Ordner **niemals rekursiv löschen** (sie folgt ins
  echte Profil) — Warnhinweis liegt daneben. Comet blieb unangetastet.
  * **N19 — Archiv-Suche auf Erwähnungen erweitern.** Befund: „Philine" kommt
    **48 ×** im Archiv vor — **41 × in WhatsApp** (aber nur *im Fabia-Chat als
    Thema*), 3 × Google Kalender (u. a. „blink-182 Konzert mit Philine"), 4 ×
    ChatGPT. Ein eigener Chat mit ihr existiert **nicht**. Die Suche fragt heute
    nur nach dem *Gegenüber*, nicht nach **Erwähnungen** → darum findet sie
    nichts. Prüfkriterium: Frage „was habe ich mit <Person> gemacht?" liefert
    Fundstellen **mit Datum und Quelle**, auch wenn es keinen eigenen Chat gibt.
  * **N20 — Weitere Chats/Gruppen ins Archiv.** Zu exportieren (Sebastian am
    Handy: „Chat exportieren", **ohne Medien**): der Gruppenchat **„Fabulous 4"**
    (enthält Philine und weitere Personen) sowie der 1:1-Chat mit Philine.
    Danach: **anhängen** (nie neu sortieren), Index auf dem PC neu bauen, per
    Kabel aufs Handy, Widget-Tipp importiert ihn. Damit werden alle Mitglieder
    der Gruppe suchbar — das gilt für jeden weiteren Export gleichermaßen.
    Datenschutz unverändert: Archiv bleibt **außerhalb des Repos** und ist
    per `.gitignore` gesperrt.

* **27.09. ~23:00 — N18 (neu): Lösch-Werkzeug für Duplikate.** Zwei Subagenten-
  Anläufe (`deleg_4c85c49b`, `deleg_a597e166`) brachen nach 5 bzw. 8 Aufrufen ab
  („waiting for model response", ~2,5 min — Anbieter-Hänger, kein Code-Problem).
  Deshalb **als Plan-Schritt für den Nachtlauf**, damit er in seiner eigenen
  Runde baut: `tools/pcloud/pcloud_duplikate_loeschen.py` — Trockenlauf als
  Standard, `--wirklich` nötig, **Prüfsumme+Größe vor jedem Löschen** frisch
  gegen den Bericht prüfen, Abbruch bei Abweichung, Manifest-Zeile je Löschung
  (`~/foto_sortierung/manifest.jsonl`, art='loeschen'), Papierkorb-Befund
  (`trash_list`/`trash_restore` prüfen) dokumentieren, Grenze 25 je Lauf.
  Erster echter Einsatz: die **12 Kopier-Reste** (581,3 MB, von Sebastian
  freigegeben). Die `upload`-Stufe (17,5 GB) bleibt **gesperrt**, bis Sebastian
  sie ausdrücklich freigibt. Prüfkriterium: Trockenlauf zeigt genau 12 Löschungen,
  jede zu löschende Datei ist die markierte Kopie, Manifest wächst je Datei,
  zweiter Lauf findet nichts mehr.
  * **N12 — Wöchentliche Nachpflege (geplante Jobs).** Ein Cron-Job je Woche
    holt Neues aus den Quellen (pCloud-Uploads, WhatsApp-Export, Google
    Kalender) und pflegt **inkrementell** nach: Datum, Motiv, Kategorie,
    Doppelungen, Event-Zuordnung. Idempotent (mehrfach laufen = kein Schaden),
    jede Runde mit Zahlen im Journal. *Sonst bleibt alles einmalig.*
  * **N13 — Bilder im Chat (Galerie + Diashow).** Der Thumbnail-Endpunkt
    `/api/cloud/thumb` **existiert schon**; es fehlt die Anzeige: Frage →
    Trefferliste → Kacheln → Antippen = groß → Diashow. Geld sparen durch
    Vorschaubilder; Originale nur auf Antippen, nie gespeichert.
    **Pflicht (Sebastian 27.09.): Bilder werden GESTREAMT, nicht gespeichert** —
    keine Aufnahme von Bild-Adressen in den Service-Worker-Cache, Anzeige über
    Blob im Arbeitsspeicher, nach dem Ansehen freigeben; der App-Speicher darf
    durch 100 angesehene Bilder **nicht** wachsen. Prüfkriterium: nach 100
    angesehenen Bildern ist der Cache-Speicher unverändert (Messung im Browser).
    **Belegt (27.09.): Frontend zeigt heute noch KEINE Cloud-Bilder**
    (`cloud/thumb` kommt in `app.js`/`index.html` 0 × vor) — die Anzeige ist
    komplett offen.
  * **N16 — Echte App (APK) + Rufen der App.** Stand belegt (27.09.): `gradle`
    FEHLT, `sdkmanager` FEHLT, Android-SDK-Ordner FEHLT, `android/`-Projekt im
    Repo FEHLT — vorhanden sind **Java 17** und **adb**. Was heute schon geht:
    **Widget-Tipp startet Server und öffnet die App** (Web-App `display:
    standalone`). Was fehlt: echte APK, **Assistenten-Rolle** und
    Sprach-Weckruf „OK Agent" im Hintergrund. Aufwand: SDK+Projekt ~1–2 h, dann
    Schritt für Schritt. **N16 bleibt gesperrt**, bis Sebastian es freigibt.
  * **N17 — Rechnen auf dem Handy (Termux).** Die Gesichts-Modelle sind nur
    **38 MB** (YuNet + SFace, ONNX) — ein Umzug aufs Handy ist damit klein.
    Messen: Erkennung je Bild auf dem Handy gegen die PC-Zeit; danach
    entscheiden, ob „PC rechnet / Handy benennt" zu „Handy rechnet selbst"
    wird.
  * **N14 — Wiederkehrende Termine (Geburtstage).** Eigene Logik statt
    „Event = einmalig": Termin mit **Tag+Monat**, jedes Jahr neu; Quelle Google
    Kalender (405 Einträge, **14 mit „Geburtstag"**) + WhatsApp
    (42.147 Nachrichten, Treffer u. a. Termin 89 · Geburtstag 100 · Konzert 165).
    **Google-Kontakte fehlen** im Archiv (nur Kalender + Notizen) — brauchen den
    Google-Zugang; bis dahin sind Kalender + Chats die Grundlage.
  * **N15 (Idee, noch nicht beauftragt) — Bildsuche nach Aussehen.** „Rothaarige
    Sängerin vom Hurricane" braucht mehr als Motiv-Etiketten: entweder eine
    Beschreibung je Foto (Vision, grob 0,0005–0,001 $ je Bild → für 9.430 Bilder
    ≈ 5–9 $) **oder** ein lokales Bild-Text-Modell (CLIP, kostenlos, dafür
    Rechenzeit). Vorher an 30 Bildern messen, dann entscheiden.
* **27.09. ~23:5x — N9e gemessen, Ursache gefunden, behoben und bestanden** (Planer:
  Hauptagent · Ausführer: Hermes-Subagent `deepseek-v4.1-flash`, 0,041 USD +
  0,022 USD aus dem ersten Bau · Prüfer: `openai/gpt-5.6-luna`).
  Beginn wie in den Runden zuvor: `git pull --rebase` scheiterte an den **fremden**
  Dateien des zweiten Agenten (`docs/experimente/live_zahlen.*`, zwei neue
  Recherche-HTML); nichts angefasst, nichts gestasht; `git fetch` +
  `git rev-list --left-right --count origin/main...HEAD` → **`0 0`**. **Codex
  erneut geprüft und weiter gesperrt** (live „try again at Oct 15th, 2026") →
  gebaut wurde mit Hermes-Subagenten.
  - **Der Schritt sollte die Cluster-Schwelle prüfen — gefunden wurde ein Fehler
    in der Merkmalberechnung.** `cv2…alignCrop` erwartet die **volle
    15-Werte-Detektionszeile** (60 Byte); an **drei** Stellen wurden nur die
    5×2-Landmarken (40 Byte) übergeben. OpenCV prüft die Form nicht, liest 20 Byte
    über den Puffer hinaus → **jedes Gesicht EINES Bildes bekam denselben
    Ausschnitt und damit denselben Vektor**. Beleg an einem Bild mit 6 Gesichtern
    (Kennung des Bildes bewusst nicht genannt; 1112×2048, nur lesend, Original nur im Arbeitsspeicher): mit den
    Landmarken **6× dieselbe** Ausschnitt-Prüfsumme `b2b88ffc585d` und 6× dasselbe
    Merkmal `[-0.07192, 0.01178, 0.10788, -0.1486]`; mit der vollen Zeile **6
    verschiedene** Prüfsummen und Merkmale. Dasselbe Merkmal zweimal gerechnet ist
    identisch — der Erkenner ist deterministisch, die **Aufrufform** war falsch.
  - **Damit sind die Personen-Ergebnisse aus N9b und N9d ungültig.** Nachgewiesen
    an den gespeicherten Dateien: `personen_vektoren_n9d.jsonl` 465 Gesichter →
    **72 Vektorwerte** (57 von 57 Mehrgesicht-Bildern nur identisch),
    `personen_vektoren.jsonl` 72 → **8** (15 von 15); Bild-interne Paare
    erkennbarer Gesichter: **131 von 131 mit Distanz exakt 0,0000** — und der
    N9d-Nebenbefund („189 Gesichter → EINE Gruppe") ist genau dieses Artefakt.
    Beide Plan-Zeilen sind mit ⚠️-Korrektur nachgezogen.
  - **Fix:** `tools/foto_sortierung/gesicht_erkennen.py` (`_merkmal`/
    `gesichter_mit_detektor` übergeben die volle Zeile) und `backend/face_infer.py`
    (`_align_face` + Aufrufer — **auch der Produktionsweg war betroffen**), dazu
    ein **Wächter**: ≥2 bit-identische Merkmale in einem Bild ⇒ deutsche
    Fehlermeldung, leere Liste, **kein stiller Durchlauf** (der stille Durchlauf
    hat den Fehler zwei Nachtläufe lang verdeckt).
  - **Prüfbefehl selbst gefahren:** `pytest tests/ -q` → **1316 passed, Exit 0**
    (Baseline 1205; +75 aus dem neuen Mess-Werkzeug, +36 aus Fix/Wächter/Tests).
  - **Nachweis nach dem Fix:** dieselben **92 Bilder** neu gerechnet (450 s,
    Originale nur im Arbeitsspeicher) → 465 Gesichter, **465 verschiedene
    Vektorwerte**, 131 Bild-Paare mit Distanz **0,5312 / 0,8280 / 1,0667**
    (min/Median/max), **0** Paare bei Distanz ≈ 0 (vorher 131). Dazu **6 frische**
    Bilder live gegengeprüft: 2/2, 3/3, 2/2, 3/3, 7/7, 5/5 verschiedene Vektoren,
    kleinste Paar-Distanz 0,49–0,91.
  - **Schwellen-Messung mit richtigen Vektoren** (neues Werkzeug
    `tools/foto_sortierung/personen_schwelle.py` + **75** Tests): die
    Bodenwahrheit ist jetzt **hart und ohne Personen-Labels** — zwei
    **erkennbare** Gesichter im **selben** Bild sind zwei Personen (Ausnahmen
    Spiegelung/Plakat/Zwilling im Docstring); der Anlass-Mix ist nur noch
    **Strukturmaß** (ein Anlass enthält legitim viele Personen, dieselbe Person
    kann in mehreren Anlässen vorkommen — die erste Fassung des Werkzeugs nannte
    das fälschlich „falsch zusammengelegt" und wurde korrigiert).
    Ergebnis (189 geclusterte Gesichter): **0 von 131** Bild-Paaren verschmolzen
    bei **allen acht** Schwellen 0,10–0,45; Gruppen 12 → 2, größte 22 → 3,
    Durchmesser 0,9032 → 0,1553. Gegenprobe auf der alten Datei: 1 Gruppe mit
    189 Gesichtern, **131 von 131 (100 %)** verschmolzen — der Fehler ist damit
    auch im Werkzeug sichtbar.
  - **Ehrlich offen (als N9f in den Plan):** über alle 465 Gesichter bleibt eine
    **Verkettung** sichtbar (0,45: 19 Gruppen, größte 85, Durchmesser **1,0755**
    > Schwelle) — sie ist jetzt ohne den Fehler messbar und als eigener Schritt
    zu beziffern/zu ersetzen, **bevor** die Schwelle neu begründet wird. Die
    Burst-Serien (59 Dateien/6 Familien, 36 Gesichter, 36 Vektoren) liefern
    **0 von 42** Familien-Paaren verschmolzen bei Distanz-Median 0,7777 — die
    Serie ist eine Szenenaufnahme und damit **kein** Identitätsbeleg, so steht es
    auch im Code. **Keine Schwelle wurde geändert.**
  - **Schutz:** kein Löschen (der Wächter verwirft nur), pCloud nur **lesend**,
    Originale nur im Arbeitsspeicher, **keine** Bilddatei auf Platte, Ausgaben
    außerhalb des Repos, keine Schlüsselwerte, keine Personennamen.
  - Doku: `docs/changelog-2026-09-27-n9e-aligncrop-fehler.md`.
  - **Hinweis zur Kollision:** in `docs/plan-nachtlauf-2026-09-26.md` stand beim
    Commit bereits ein **fremder** Journal-Eintrag des zweiten Agenten (neuer
    Schritt **N11**, Fotos-Fragen am Handy). Er blieb unverändert erhalten und ist
    als N11 in die Schritt-Tabelle übernommen; die beiden fremden
    `live_zahlen`-Dateien und die zwei Recherche-HTML wurden **nicht** angefasst
    (Commit nur mit ausdrücklich genannten Pfaden).
  - **Nächster Schritt: N9f** (Personen-Ergebnisse mit richtigen Vektoren neu
    rechnen, Verkettung beziffern/ersetzen) — **N8 (echtes Sortieren) bleibt
    gesperrt**, bis Sebastians Blick auf die 39 sicheren Event-Vorschläge und die
    1.146 datumslosen Dateien da ist.
  - **Prüfer Runde 1 (`gpt-5.6-luna`, frischer Kontext): NICHT BESTANDEN** — und
    der wichtigste Einwand war **berechtigt und lehrreich**. Er hat den Prüfbefehl
    selbst gefahren (**1316 / Exit 0**), alle drei Vektor-Dateien selbst
    nachgezählt (n9b 72/8, n9d 465/72, n9e 465/465, jeweils die Null-Distanzen),
    die Clusterzahlen selbst nachgerechnet und die Regressionstests einzeln
    gefahren (4 passed) — alles bestätigt. **Sein Gegenbeleg:** in *seinem* Lauf
    lieferte die alte 5×2-Aufrufform **sechs verschiedene** Ausschnitte, meine Doku
    behauptete „immer derselbe". Richtig daran: der Übergriff liest
    **Speichermüll**, welcher Müll gelesen wird, hängt vom Speicherinhalt ab —
    meine Formulierung war zu absolut. **Nachgelegt:** kontrollierter Puffer als
    harter Beleg (die alte Form ist **bit-identisch** mit der nachgebauten
    Mischzeile `e1857be02379` → vier Werte über das Ende gelesen), die
    Ausschnitt-Mittelwerte zeigen die Wirkung (**schwarz, 0,00** gegen **103–158**),
    und die Doku sagt jetzt ausdrücklich: nicht deterministisch in den *Werten*,
    eindeutig in der *Wirkung* (die alte Form schneidet nie das Gesicht).
    Zwei weitere Punkte: (a) „Verstoß gegen die Hygiene, weil echte Namensbestandteile
    im fremden N11-Plantext" — das ist der **Eigner-Name** bzw. der Bestand des
    Plans (26 × in HEAD), keine fotografierte Person, wie schon in N9a
    festgestellt; nicht umgeschrieben. (b) „Commit nicht nachvollziehbar, Dateien
    noch untracked" — der Prüflauf lag laut Rollenfolge des Plans **vor** dem
    Commit; die Abnahme auf dem committeten Stand folgt als Runde 2.
  - **Prüfer Runde 2 (`gpt-5.6-luna`, Abnahme auf Commit `4a296db`): BESTANDEN,
    0 Abweichungen.** Er hat selbst gefahren: Prüfbefehl **1316 / Exit 0**;
    `git show --stat 4a296db` = **genau 8 Dateien** und **keine** der fremden
    Dateien; `0 0` gegen `origin/main`; die drei Vektor-Dateien nachgezählt
    (n9e 465/465, n9d 465/72, n9b 72/8) und die Bild-Paare selbst gerechnet
    (**131 Paare, Distanz 0,531228–1,066653, 0 × exakt 0**); `personen_schwelle.py`
    selbst aufgerufen (**189 geclusterte Gesichter, 0 von 131 verschmolzen bei
    0,45/0,30/0,15/0,10**); die fünf Wächter-/Aufrufform-Tests einzeln (**je
    1 passed**); die Schwellen gegen `b90cfac` verglichen (**wertgleich**);
    Hygiene (keine Löschung, keine pCloud-Schreiboperation, keine Bilddatei, kein
    Schlüsselwert, keine fotografierten Personennamen) und die Planzeilen
    (N9e ✅, N9f ⬜, N11 ⬜, N9b/N9d mit Korrekturmarke).
    **Der stärkste eigene Beleg des Prüfers:** er hat in den beiden Ausschnittsarten
    **erneut Gesichter detektiert** — im Ausschnitt der alten Aufrufform
    **0 Gesichter** (Mittelwerte 9,65–62,94), im Ausschnitt der korrekten Form
    **5 von 6** (Mittel 103,56–158,21). Damit ist die „Wirkung" nicht mehr nur
    behauptet, sondern gemessen: die alte Form schneidet nie ein Gesicht.
* **27.09. ~22:4x — N9f gebaut, gemessen und bestanden** (Planer: Hauptagent ·
  Ausführer: Hermes-Subagent `deepseek-v4.1-flash`, 0,026 USD für das Werkzeug,
  Messläufe vom Planer · Prüfer: `openai/gpt-5.6-luna`, eine Runde — **andere
  Modellfamilie**). Beginn wie in den Runden zuvor: `git pull --rebase` scheiterte
  an den **fremden** Dateien des zweiten Agenten (`docs/experimente/live_zahlen.*`,
  zwei Recherche-HTML); nichts angefasst, nichts gestasht; `git fetch` +
  `git rev-list --left-right --count origin/main...HEAD` → **`0 0`**. **Codex
  erneut geprüft und weiter gesperrt** (live „try again at Oct 15th, 2026
  9:32 PM") → gebaut wurde mit einem Hermes-Subagenten.
  - **Werkzeug:** `tools/foto_sortierung/personen_verkettung.py` (**878 Zeilen**)
    + `backend/tests/test_personen_verkettung.py` (**939 Zeilen, 117
    Testfunktionen**, alles offline, nur `numpy`). Drei Verfahren:
    **dichte** (Bestandsweg N9a, transitiv verkettend), **vollstaendig**
    (Complete-Linkage — Durchmesser **garantiert** ≤ Schwelle, per Test über
    Saatgüter belegt), **mittelpunkt** (Mittelpunkt-Verfahren, **keine**
    Garantie). Dazu `verfahren_messen`, `vergleich_bericht`, `bericht_text` und
    eine CLI (`--vektoren`, `--verfahren`, `--schwellen`, `--min-groesse`,
    `--ausgabe` nur außerhalb des Repos, `--schreiben`; Standard Trockenlauf).
  - **Prüfbefehl selbst gefahren:** Baseline **1316** → **1433 passed, Exit 0**
    (75,8 s; +117 = genau die neuen Testfunktionen). Der Commit-Hook fuhr
    dasselbe Tor beim Commit noch einmal: **1433 / Exit 0**.
  - **Verkettung ist beziffert** (Vektordatei `personen_vektoren_n9e.jsonl`,
    92 Bildzeilen, **189 nutzbare Gesichter**, Schwelle **0,45**,
    Mindestgröße **3** = Produktionseinstellung):
    dichte **12 Gruppen / größte 22 / 74 Gesichter / Durchmesser max 0,9032**,
    vollständig **11 / 11 / 63 / 0,4417**, mittelpunkt **10 / 27 / 75 / 0,9040**.
    Bei gleicher Mindestgröße 2 über **alle acht Schwellen 0,10–0,45** liegt
    dichte **immer** über der Schwelle (0,45: 20 Gruppen, größte 22, 0,9032),
    vollständig **nie** (23/11/0,4491). **Der Bestandsweg bildet also bei
    Schwelle 0,45 eine Gruppe mit Durchmesser = 2 × Schwelle.**
  - **Bodenwahrheit (hart, ohne Personen-Labels):** **131** Bild-Paare
    erkennbarer Gesichter (Flächenanteil ≥ 0,5 %), Distanzen **min 0,5312 /
    Median 0,8280 / max 1,0667**, **0 von 131 unter 0,45**; über **alle drei
    Verfahren × alle acht Schwellen (24 Kombinationen) 0 von 131 verschmolzen**.
    Die Verkettung verschmilzt also nur **nicht prüfbare** (kleine/ferne)
    Gesichter, keine zwei erkennbaren Personen.
  - **Entscheidung zur Schwelle (statt Frage): unverändert 0,45.** Begründung mit
    Zahlen: kleinster Abstand zweier erkennbarer Gesichter **0,5312** → **0,0812**
    Abstand zur Schwelle, unter 0,45 liegen **0** Paare; ein Anheben wäre durch
    keine Messung gedeckt. **Empfehlung für den Personenschritt** (bewusst
    **nicht** vollzogen, weil ein Verfahrenswechsel ein eigener Schritt ist):
    vollständige Verknüpfung — Gewinn: größte Gruppe 11 statt 22, Durchmesser
    0,4417 statt 0,9032; Preis: 63 statt 74 Gesichtern in Gruppen (11 mehr im
    Rauschen). `CLUSTER_MIN_NACHBAR`, `ANTEIL_MIN`, `ANTEIL_ERKENNBAR`,
    `KATALOG_SCHWELLE`, `MENGE_ANZAHL` **nicht angetastet** (auch vom Prüfer
    als wertgleich bestätigt).
  - **Neu-Rechnung der Personen-Stufe (korrigierte Vektoren, Produktion):
    92 Bilder, Arten `leer 20 · gruppe 32 · menge 10 · unklar 30`** (identisch zu
    N9e), **32 Bilder geclustert, 12 Gruppen** (4,4,4,4,3,11,10,3,22,3,3,3 = 74
    Gesichter), **12 Kennungen** `Person_001…Person_012` (0 wiederverwendet —
    der Lauf startete **bewusst ohne** Altbestand, weil die alte Kennungsdatei
    aus dem fehlerhaften N9b-Lauf stammt), **16 Referenzseiten**,
    **74 Kacheln, alle 200×200** (0 leer, 0 andere Größe), 17 Dateien,
    **745.758 Bytes**; **2. Lauf 0 Seiten** (idempotent).
  - **Pixel-Gegenprobe** an drei Kacheln: Abstand zum frisch gerechneten
    Gesichtsausschnitt **2,778 / 2,869 / 3,015** (JPEG-Verlust quality 85),
    zum verkleinerten **ganzen Foto** **59,425 / 58,783 / 68,712** → die Kachel
    ist wirklich der Ausschnitt.
  - **Burst-Datei** (`personen_vektoren_n9e_burst.jsonl`): nur **14 nutzbare**
    Gesichter; bei 0,45 liefern **alle drei** Verfahren dieselben Zahlen
    (2 Gruppen, größte 2, 4 Gesichter, Durchmesser 0,3779 ≤ 0,45) — in den
    Szenenaufnahmen **keine** Verkettung. Kein Identitätsbeleg (wie in N9e).
  - **Prüfer Runde 1 (`gpt-5.6-luna`): BESTANDEN, 0 Abweichungen.** Er hat
    selbst gefahren: Prüfbefehl **1433 / Exit 0**; Commit `d14d2f9` = **exakt
    drei** Dateien, keine fremden; `0 0`; beide Werkzeugläufe (mit
    `--min-groesse 3` und mit Standard 2) und **alle** Tabellenzeilen; die
    Bodenwahrheit aus der Vektordatei selbst (131 Paare, Distanzen, 0 unter
    0,45, 0 von 131 in 24 Kombinationen); Ausgabeordner **17 Dateien / 745.758
    Bytes** und die 16 Seiten; die sechs Schwellen-Konstanten **wertgleich** zu
    HEAD~1; Hygiene per AST (keine Lösch-, Netz-, cv2-, onnx- oder pCloud-Aufrufe,
    117 Testfunktionen, Repo-Ausgabeziel → Exit 2, `manifest.jsonl` nicht
    vorhanden); und die Changelog-Zahlen Punkt für Punkt ohne Abweichung.
  - **Schutz:** pCloud nur **lesend**; Originale nur im Arbeitsspeicher, **keine**
    Bilddatei auf der Platte; **nichts gelöscht** (Belegskripte verweigern einen
    nicht leeren Zielordner mit **Exit 2**); keine Buchung (`manifest.jsonl`
    existiert nicht); Ausgaben ausschließlich unter `~/foto_sortierung/`
    (`personen_n9f/`, `n9f_bodenwahrheit.json`, `n9f_referenzseiten.json`, drei
    Belegskripte); keine Schlüsselwerte, keine Namen Dritter.
  - **Kollision wie gehabt:** die fremden `live_zahlen`-Dateien und die zwei
    Recherche-HTML blieben unberührt; Commit mit ausdrücklich genannten Pfaden
    (`git commit --only`), gepusht, `0 0`.
  - Doku: `docs/changelog-2026-09-27-n9f-verkettung.md`.
  - **Offen für den nächsten Schritt:** Verfahrenswechsel im Produktionsmodul
    (`vollstaendig`) und **breitere Stichprobe** (die 92 Bilder sind ein
    Ausschnitt des Bestands). **N8 (echtes Sortieren) bleibt gesperrt**, bis
    Sebastians Blick auf die 39 sicheren Event-Vorschläge und die 1.146
    datumslosen Dateien da ist; **N11** (Fotos-Fragen am Handy) und **N10**
    (Abschlussbericht) sind weiter offen.

* **28.09. ~00:0x — N9g gemessen, gebaut und bestanden** (Planer + Messung:
  Hauptagent · Ausführer (Code): Hermes-Subagent `deepseek-v4.1-flash`, 0,024 USD ·
  Prüfer (Code): `openai/gpt-5.6-luna`, **eine** Runde, andere Modellfamilie).
  Beginn wie in den Runden zuvor: `git pull --rebase` scheiterte an den **fremden**
  Dateien des zweiten Agenten (`docs/experimente/live_zahlen.*`, zwei Recherche-HTML);
  nichts angefasst, nichts gestasht; `git fetch` + `git rev-list --left-right --count
  origin/main...HEAD` → **`0 0`**. **Codex live geprüft und weiter gesperrt**
  („try again at Oct 15th, 2026 9:32 PM") → gebaut wurde mit einem Hermes-Subagenten.
  - **Erst messen, dann umstellen.** Breitere Stichprobe über die **Jahre gestreut**
    (je Jahr bis 6 Mengen-Anlässe, je Anlass bis 5 Bilder): **443** Anlässe mit
    Mengen-Thema, **1.455** ohne; Auswahl **192 Bilder** = **40 Mengen-Anlässe
    (152 Bilder)** + **40 Kontrollbilder** aus 40 verschiedenen Anlässen (N9f: 92 aus 8).
    **188 heruntergeladen, 142 mit Gesicht, 907 Gesichter, 1.086,6 s, 9 Fehlerzeilen**
    (4 × pCloud-Zeitüberschreitung, 5 × „Bild nicht dekodierbar"), **0 Wächter**;
    Arten `gruppe 74 · leer 41 · menge 20 · unklar 48` → **341 geclusterte Gesichter**
    (N9e: 189). Vektordatei `~/foto_sortierung/personen_vektoren_n9g.jsonl` (188 Zeilen),
    Messskript `n9g_messung.py`, Belege `n9g_messung.log`/`.json` — alles außerhalb des
    Repos, Originale nur im Arbeitsspeicher.
  - **Bodenwahrheit: 210** Bild-Paare erkennbarer Gesichter, Distanzen **min 0,4925 /
    Median 0,8708 / max 1,1422**, **0 von 210 unter 0,45**.
  - **Der neue Befund:** das Bestandsverfahren **dichte** verschmilzt auf der breiteren
    Stichprobe **2 von 210** erkennbaren Paaren (bei 0,45 **und** 0,40, Quote 1,0 %)
    und reißt den Durchmesser mit **2,00234 × Schwelle**; N9f hatte auf 92 Bildern
    „0 von 131" gemessen — **die Stichprobe war zu klein, kein Gegenbeweis**.
    **vollstaendig 0 von 210** in **allen 16** Kombinationen (8 Schwellen × 2 Mindest-
    größen), Durchmesser **nie** über der Schwelle (knappste Stelle 0,99908).
    **mittelpunkt 11 von 210** bei 0,45 (5,2 %), Verhältnis Durchmesser/Schwelle bis
    **2,1208** (0,9240 absolut bei 0,45) → ausgeschieden.
    Von 48 Verfahren-Schwellen-Kombinationen tragen die **34** verschmolzenen Paare
    je zur Hälfte dichte (4 je Mindestgröße) und mittelpunkt (13 je Mindestgröße);
    vollstaendig trägt **0** bei.
  - **Produktionseinstellung 0,45** (Mindestgröße 3): dichte 10 Gruppen / größte 27 /
    **89 Gesichter** / **2 verschmolzen** / Durchmesser 0,7782 gegen **vollstaendig
    13 / 7 / 66 Gesichter / 0 / 0,4395** (mittelpunkt 9 / 39 / 86 / 11 / 0,9240).
    **Entscheidung: Produktion = vollständige Verknüpfung** — das einzige Verfahren mit
    der harten Invariante und 0 verschmolzenen Paaren; **Preis ehrlich:** 23 Gesichter
    mehr im Rauschen, 13 statt 10 Gruppen, größte 7 statt 27.
  - **Code:** in `personen_cluster.py` die Konstanten `VERFAHREN_DICHTE`/
    `VERFAHREN_VOLLSTAENDIG`/`VERFAHREN`/`CLUSTER_VERFAHREN` (Produktionsstandard
    `vollstaendig`), neue reine `vollstaendig_clustern` (Complete-Linkage, nur numpy,
    deterministisch, Rauschen < Mindestgröße verworfen, Invariante im Docstring),
    `vektoren_clustern(..., verfahren=None)` mit **unverändertem** `"dichte"`-Zweig und
    **deutscher `ValueError`** bei unbekanntem Verfahren (kein stiller Rückfall),
    Produktionsaufruf in `referenzseiten_bauen` **ohne** `verfahren` (neuer Standard
    greift), CLI `--verfahren` mit Ausgabe des Verfahrens. `personen_schwelle.py`:
    Aufruf auf `verfahren="dichte"` **festgenagelt** (das Messwerkzeug bleibt das
    Bestandsverfahren). `personen_verkettung.py`: `vollstaendig_clustern` behält die
    Signatur und **delegiert** (keine Doppelimplementierung), `gruppen_bilden` pinnt
    den `dichte`-Pfad; kein Ringschluss.
  - **Prüfbefehl selbst gefahren:** Baseline **1433** → **1449 passed, 3 warnings,
    Exit 0** (+**16** neue Testfunktionen in `test_personen_cluster.py`, 219 → 235);
    `test_personen_verkettung.py` (117 → 117) nur angepasst: drei Aufrufe der
    Dichte-Baseline auf `verfahren="dichte"` festgelegt, Erwartungen unverändert.
    Der Commit-Hook fährt dasselbe Tor beim Commit.
  - **Prüfer Runde 1 (`gpt-5.6-luna`, frischer Kontext): BESTANDEN, „Abweichungen:
    keine."** Er hat selbst gefahren und nachgerechnet: Prüfbefehl **1449 / Exit 0**;
    Testfunktionen 219→235 bzw. 117→117; die Durchmesser-Invariante über die Schwellen
    0,10/0,20/0,30/0,45 und die Saatgüter 0/1/7/42/99; den Kettenfall (bei 0,25:
    dichte 0,72 gegen vollstaendig 0,20); `ValueError` bei unbekanntem Verfahren; die
    **unveränderte Kernlogik** des dichte-Zweigs im Diff gegen HEAD; die Delegation
    (gleiches Saatgut → gleiche Gruppen); **alle Schwellen wertgleich zu HEAD**;
    Hygiene (keine Löschfunktion, keine Netz-/pCloud-Aufrufe, keine neuen
    Abhängigkeiten, kein Ausgabeziel im Repo); `git diff --stat` = **genau fünf**
    Dateien, die fremden `live_zahlen`-Dateien **nicht** enthalten.
  - **Prüfer Runde 2 (`gpt-5.6-luna`, Abnahme auf Commit `b88b41d`): NICHT BESTANDEN —
    zwei berechtigte Abweichungen, beide korrigiert.** (1) In der Changelog-Tabelle stand
    für `mittelpunkt` als **maximales** Verhältnis Durchmesser/Schwelle `2,0533`; das gilt
    nur bei 0,45, der Höchstwert ist **2,1208** (0,6362 bei Schwelle 0,30) — nachgerechnet
    aus `n9g_messung.json` und korrigiert. (2) Diese neu ergänzte Journal-Zeile enthielt
    den **Eigner-Namen** → ersetzt durch „dein Blick". Der Code selbst war von der
    Beanstandung nicht betroffen.
  - **Prüfer Runde 3 (`gpt-5.6-luna`, frische Sitzung, Abnahme auf `fcf4ad4`):
    BESTANDEN, „Abweichungen: keine."** Höchstwert selbst nachgerechnet
    (**2,1208** = 0,6362308 / 0,30 in beiden Mindestgrößen), `2,0533` nur noch der
    Schwelle 0,45 zugeordnet, die neu ergänzten Journal-Zeilen **ohne** Eigner-Namen,
    `fcf4ad4` = zwei Dateien, `b88b41d` = sieben Dateien, `0 0`, keine
    `live_zahlen`-Dateien im Projektstand; Prüfbefehl **1449 / Exit 0** (eigener Lauf).
  - **Schutz:** pCloud nur **lesend**; Originale **nur im Arbeitsspeicher**, **keine**
    Bilddatei auf der Platte; **nichts gelöscht**; `manifest.jsonl` existiert nicht
    (keine Buchung); alle Ausgaben unter `~/foto_sortierung/`; keine Schlüsselwerte,
    keine Namen Dritter; die fremden Dateien des zweiten Agenten blieben unberührt.
  - Doku: `docs/changelog-2026-09-27-n9g-verfahren.md`.
  - **Ehrlich offen:** die 4 Zeitüberschreitungen wurden **nicht** wiederholt (192
    ausgewählt, 188 erkannt); `personen_verkettung._abstand_der_gueltigen` hat keinen
    Aufrufer mehr (Aufräumen war nicht Teil des Auftrags); der Personenweg rechnet
    weiterhin nur auf einer Stichprobe des Bestands.
  - **Nächster Schritt: N11** (Fotos-Fragen am Handy: `/api/fotos/uebersicht` +
    kleine Datendatei ohne Bilder) — **N8 (echtes Sortieren) bleibt gesperrt**, bis
    dein Blick auf die 39 sicheren Event-Vorschläge und die 1.146 datumslosen
    Dateien da ist; **N10** (Abschlussbericht) danach.

* **27.09. ~23:2x — N11 gebaut, echt gemessen und bestanden** (Planer + Messung:
  Hauptagent · Ausführer: **zwei** Hermes-Subagenten `deepseek-v4.1-flash`, 0,021 +
  0,035 USD, getrennte Dateimengen mit eingefrorenem JSON-Schema · Prüfer:
  `openai/gpt-5.6-luna`, **drei Runden** — andere Modellfamilie). Beginn wie in den
  Runden zuvor: `git pull --rebase` scheiterte an den **fremden** Dateien des zweiten
  Agenten; nichts angefasst, nichts gestasht; `git fetch` + Zählung → **`0 0`**.
  **Codex erneut gesperrt** (Kontingent bis 15.10.) → gebaut wurde mit Subagenten.
  - **Der Auftrag als Datei:** `docs/auftrag-n11-foto-uebersicht.md` (224 Zeilen) mit
    **eingefrorenem JSON-Schema** (Schlüssel, Typen, Sortierungen) — genau deshalb
    konnten beide Ausführer parallel arbeiten, ohne sich zu sehen.
  - **Prüfbefehl selbst gefahren:** Baseline **1503** → **1687 passed, Exit 0**
    (die Baseline ist höher als in der Vorrunde, weil die Suite inzwischen auch
    Dateien des zweiten Agenten enthält); JS: `node --check app.js` Exit 0,
    `node frontend/tests/test_selbsttest.js` „alle Prüfungen grün". Neue Tests:
    **98** (Werkzeug) + **83** (Dienst/Router/Chat/Selbsttest) = **181**.
  - **Die Datendatei (echter Bestand, nur lesend erzeugt):**
    `~/foto_sortierung/fotos_uebersicht.json` — **344.615 Bytes**,
    `stand 2026-09-27T22:40:09+02:00` aus `sortierplan.json`
    (`plan_stand 2026-09-27T13:49:46`, `trocken: true`). Zahlen: **2.127 Anlässe ·
    2.098 Event-Ordner · 9.430 Zeilen · 7.616 Züge · 1.146 Zeilen ohne Datum ·
    11 Jahre · 48 Themen · 11 Kategorien · 2.088 Events neu / 39 Anlässe auf
    bestehenden Ordnern** — **ohne Bilddaten, ohne Datei-Kennungen**; Ausgabe
    außerhalb des Repos.
  - **Entscheidung statt Frage (Schema-Konflikt, vom Ausführer ehrlich gemeldet):**
    die Beispielzahl `"events": 2127` im Auftrag war falsch — `events` zählt die
    **verschiedenen `(jahr, kategorie, event)`-Kombinationen** = **2.098** Ziel-Ordner.
    Der Planer hat den Auftrag auf **2.098** korrigiert und selbst nachgezählt:
    **10** wiederverwendete Event-Ordner mit **39** Anlässen (7 davon mit mehr als
    einem; 39 − 10 = 29 = 2.127 − 2.098). Die Paar-Zahlen `events_neu` /
    `events_wiederverwendet` zählen dagegen **Anlässe** (2.088 + 39 = 2.127) — im
    Changelog ausdrücklich klargestellt.
  - **Endpunkt am echten Bestand, ohne Netz** (TestClient, eigener Rauchtest):
    `?limit=3` → **200**, `ok: true`, `quelle: fotos_uebersicht.json`, Stand wie oben,
    Zahlen 2.127 / 2.098 / 9.430 / 7.616 / 1.146, 11 Jahre, 48 Themen, 11 Kategorien;
    `?jahr=2021&suche=usedom` → **1** Treffer (`2021_07 Usedom`);
    `?kategorie=urlaub` → **25** (= Standard-`limit`, die Kategorie hat real **217**
    Events); `?limit=999` → auf **200** geklemmt. **Fehlt die Datei:** 200 mit
    deutschem `error` statt 500; Selbsttest zeigt `✗ Fotos: <error>`.
    Der Selbsttest-Endpunkt wurde **bewusst nicht** ohne Attrappe aufgerufen (er
    würde den echten pCloud-Prüfpfad auslösen) — der Ausführer hatte das bei einer
    Sondierung einmal getan und offen gemeldet.
  - **Chat-Anschluss:** `_fotos_uebersicht_tool` hängt eine deutsche Notiz an die
    Nutzerfrage, in **beiden** Ketten (`/api/chat`, `/api/chat/stream`); die
    Auslöseregel ist eng (Foto-Wort **und** Frage-Wort, `gab` nur als eigenes Wort).
    Prüfer-Belege: löst aus bei „wie viele Events gab's?" und „zeig mir die Urlaube
    2021"; **löst nicht aus** bei „Aufgabe erledigt", „wie viele Aufgaben habe ich",
    „guten Morgen".
  - **Cache-Bump korrigiert (Planer):** der Ausführer hielt `app.js?v=20260927A` für
    „schon richtig" — der Wert stammt aber aus Commit `6b08e67` und war **älter als
    die Änderung**; auf **`?v=20260927B`** gesetzt und die Token-Prüfung im JS-Test
    mitgezogen (sie war auf `…A` festgenagelt und wurde dadurch rot). Genau der
    Fehler, den Regel §5 verhindern soll.
  - **Prüfer `gpt-5.6-luna`, drei Runden — alle Beanstandungen betrafen die Doku,
    nie den Code.** **Runde 1: NICHT BESTANDEN** mit vier Abweichungen (sie hat den
    Code ausdrücklich bestätigt: Datendatei-Nachrechnung, Endpunkt, Chat-Regel,
    Hygiene, Fremddateien unberührt): `chat.py` „+50 statt +55 Zeilen"; die
    Changelog-Behauptung, die Übersichtsdatei existiere nicht; erfundene und echte
    Beispielzahlen im selben Absatz; Auftrag nannte noch `?v=20260927A`. Dazu zwei
    Label-Ungenauigkeiten (Kommentar „7 wiederverwendete Event-Ordner" statt **10**;
    zwei verschiedene „Dateien"-Zahlen) — alle behoben. **Runde 2: NICHT BESTANDEN**
    mit drei Restpunkten (die als „echt" ausgegebene Chat-Gegenprobe stimmte nicht —
    die Suche „urlaub" trifft 2021 **0** mal, erst „usedom" trifft; `?kategorie=urlaub`
    nannte 25 als Kategorie-Größe statt als Standard-`limit`; „566 Zeilen" statt
    **565**) — alle drei korrigiert und zusätzlich die „Dateien"-Erklärung in **beide**
    Changelogs geholt. **Runde 3 (frische Sitzung, Abnahme auf `9a213c9`):
    BESTANDEN, 0 Abweichungen** — Prüfbefehl selbst **1687 / Exit 0**, alle vier
    Punkte selbst nachgerechnet (u. a. 0 / 1 Treffer für „urlaub"/„usedom" 2021,
    217 Events in `Urlaub`, 565 Zeilen), `9a213c9` = genau drei Dateien.
  - **Kollision, ehrlich notiert:** während der Abnahme hat der **zweite Agent** mit
    einem breiten `git add` meine N11-Dateien in seinen Sammelcommit **`751280a`**
    („feat(fotos): N11 Fotos-Uebersicht … + Duplikate-Regeln") mitgenommen — dort
    liegen jetzt meine N11-Dateien **zusammen** mit seiner Arbeit (`cloud.py`,
    `pcloud_service.py`, `test_pcloud_*`, Screenshot-Triage im Vorgängercommit
    `9659b96`). Inhaltlich ist nichts verloren oder vermischt im Sinn von Fehlern
    (Suite grün), die Historie wird **nicht** umgeschrieben; die Doku-Korrekturen
    dieser Runde liegen im eigenen Commit **`9a213c9`** (`git commit --only`, drei
    Dateien, keine fremden). Im fremden Commit wird derselbe Punkt bereits zum
    dritten Mal sichtbar (siehe `908cf39`, `0a48e23`) — die Regel „nie `git add -A`"
    steht in `AGENTS.md`, sie wird vom anderen Agenten weiterhin nicht befolgt.
    Beim Mitcommitten der Plandatei sind dessen fertige Journal-Einträge (N12–N17,
    **N18 ~23:00 „Lösch-Werkzeug für Duplikate"**) **unverändert erhalten** geblieben.
  - **Schutz:** pCloud nur **lesend**; **keine** Bilddatei auf der Platte; **nichts
    gelöscht**; kein Netz in Werkzeug/Dienst/Router/Chat (per AST-Test belegt, Tests
    sperren Namensauflösung und Verbindungsaufbau); keine Geheimnisse in Ausgaben
    oder Dateien; Ausgaben und Datendatei ausschließlich außerhalb des Repos; in
    Tests nur erfundene Namen (`Konzert Beispiel`, `Urlaub Beispiel`).
  - Doku: `docs/changelog-2026-09-27-n11-uebersicht-datei.md`,
    `docs/changelog-2026-09-27-n11-uebersicht-endpunkt.md`,
    Auftrag `docs/auftrag-n11-foto-uebersicht.md`.
  - **Ehrlich offen:** (1) die Übersichtsdatei liegt **noch nicht auf dem Handy** —
    die Übertragung ist nicht Teil des Schritts; ohne sie sagen Endpunkt, Chat und
    Selbsttest das klar. (2) `?kategorie=urlaub` liefert standardmäßig nur 25 Treffer
    (Schutzgrenze 200) — wer alle 217 will, braucht `limit=200` oder ein
    Blätter-Verfahren. (3) `jahr` ist als Zahl typisiert: nicht-numerische Eingabe
    ergibt HTTP 422 (nicht 500, aber auch kein deutscher Text). (4) Die Suche trifft
    nur Event-Namen, keine Datei- oder Ortsnamen.
  - **Nächster Schritt: N10** (Abschlussbericht/Protokoll) — **N8 (echtes Sortieren)
    bleibt gesperrt**, bis dein Blick auf die 39 sicheren Event-Vorschläge und die
    1.146 datumslosen Dateien da ist.

* **28.09. ~08:5x — N10 (Abschlussbericht + Protokoll) gebaut, geprüft und bestanden**
  (Planer: Hauptagent · Ausführer: **zwei** Hermes-Subagenten `deepseek-v4.1-flash`,
  0,045 USD (Bau) + 0,022 USD (Nachbesserung) · Prüfer: `openai/gpt-5.6-luna`,
  **zwei Runden** — andere Modellfamilie).
  Beginn wie in den Runden zuvor: `git pull --rebase` scheiterte an den **fremden**
  Dateien des zweiten Agenten (`docs/experimente/live_zahlen.*`, zwei Recherche-HTML);
  nichts angefasst, nichts gestasht; `git fetch` + Zählung → **`0 0`**.
  **Codex erneut gesperrt** (Kontingent bis 15.10.) → gebaut wurde mit Subagenten.
  - **Werkzeug des Schritts ist keine Software, sondern eine Seite:** der Auftrag
    (`docs/auftrag-n10-abschlussbericht.md`, verbindliche Gliederung + Prüfkriterien)
    → Bericht `docs/abschlussbericht-nachtlauf-2026-09-26.md` (**276 Zeilen**) →
    Changelog `docs/changelog-2026-09-28-n10-abschlussbericht.md` (**95 Zeilen**).
    Dazu die zwei Doku-Zeilen, die dem Code hinterherhingen: eine
    Protokollzeile in der Projekt-`CLAUDE.md` und die **veraltete Prüfbefehls-Zeile**
    in `../CLAUDE_EXTENDS.md` (stand dort seit 25.09.2026 auf „304 grün") — jetzt
    **1687 grün, Exit 0 (28.09.2026)**.
  - **Berichtsinhalt:** 17 Schritte (N1, N4, N5, N6, N6b, N6c, N6d, N6e, N7,
    N9a–N9g, N11) mit Zahlen **und** Prüfer-Befund je Zeile; Kosten mit Quelle je
    Zeile (Hochrechnungen und Schätzungen ausdrücklich gekennzeichnet); der
    **N9e-Fund** in eigenen Worten (falsche Aufrufform an `alignCrop` → jedes Gesicht
    **eines** Bildes hatte denselben Vektor; 131 von 131 Paaren mit Distanz 0,0000;
    Fix im Werkzeug **und** im Produktionsweg `backend/face_infer.py` + Wächter;
    N9b/N9d-Zahlen als **ungültig** markiert); gesperrte/offene Punkte **wörtlich**
    aus dem Plan; Sicherheitsnetz; 5 Pitfalls.
  - **Prüfbefehl selbst gefahren (Planer):** `cd backend && .venv/Scripts/python -m pytest
    tests/ -q` → **1687 passed, 3 warnings, Exit 0** (69,2 s; Baseline **1503**). Der
    Prüfer hat ihn ebenfalls selbst gefahren: **1687 / Exit 0**.
  - **Prüfer Runde 1 (`gpt-5.6-luna`, frischer Kontext): NICHT BESTANDEN, 6 Punkte —
    4 berechtigt, 1 Fehlalarm, 1 Aufruf-Fehler des Prüfers selbst.** Berechtigt:
    (a) eine **pCloud-Dateikennung** stand im Bericht (Datenschutz-Regel des Auftrags);
    (b) die gesperrten Punkte waren nur **paraphrasiert** statt wörtlich übernommen;
    (c) eine **unmarkierte Näherung** („rund 0,08 $" Ausführerkosten);
    (d) die Changelog-Aussage zu den fremden Dateien war unscharf. Alle vier behoben.
    Fehlalarm: „fremde Dateien angefasst" — **mit Zeitstempeln widerlegt**:
    `live_zahlen.html/.json` **2026-09-28 08:43:00** (zweiter Agent, *während* dieses
    Laufs geschrieben), `datenkontrolle-anbieter.html` 25.09. 12:58:55,
    `ki-training-schutzformen.html` 25.09. 12:17:07; der Ausführer hat **keine**
    git-Befehle ausgeführt. Der **md5-Wert** der Eingabedatei und der feste
    pCloud-Funktionsname `Crypto Folder` bleiben bewusst (lokale Prüfsumme bzw.
    bereits Bestand in `CLAUDE.md`/Plan) — beide sind jetzt als solche gekennzeichnet.
  - **Prüfer Runde 2 (`gpt-5.6-luna`, frische Sitzung): BESTANDEN, 0 Abweichungen.**
    Er hat selbst gefahren: Prüfbefehl **1687 / Exit 0**; die Zeitstempel der vier
    Fremddateien bestätigt; **keine** 11-stelligen Dateikennungen mehr; die
    md5-Kennzeichnung; die Schätzung 0,038 + 0,017 + 0,021 USD gegen das Journal;
    eine Zahlenstichprobe (u. a. 1503/1687, 2.127/2.098/9.430/7.616/1.146, 344.615
    Bytes, 5.954.092/370.113 Tokens = 2,711510 USD, 907 Gesichter, 210 Paare,
    131 Paare Distanz 0,0000, 2,1208) **ohne Abweichung**; Plan-Datei unverändert.
  - **Prüfer Runde 3 (Abnahme auf dem committeten Stand `f0f13ab`, frische Sitzung):
    BESTANDEN, 0 Abweichungen** — eigener Lauf: **1687 / Exit 0**; `<Commit>` = genau
    die sieben genannten Dateien, **keine** fremde; `0 0` gegen `origin/main`; die
    wörtlichen Zitate der gesperrten Punkte und die Zahlenstichprobe in der
    committeten Fassung geprüft. *Ehrlich notiert:* die Journal-Formulierung zu
    Runde 2 stand schon **vor** der Abnahmerunde 3 im Commit `f0f13ab`; sie war zu
    diesem Zeitpunkt bereits durch Runde 2 belegt, die dritte Runde hat sie danach
    bestätigt (dieser Satz ist der Nachtrag dazu).
  - **Schutz:** keine Löschung, keine git-Befehle durch die Ausführer, kein Code und
    keine Tests angefasst, kein Netz-/pCloud-Aufruf, keine Schlüsselwerte, keine
    Namen Dritter; die fremden Dateien des zweiten Agenten blieben unberührt.
  - Doku: `docs/abschlussbericht-nachtlauf-2026-09-26.md` (der Bericht selbst),
    `docs/changelog-2026-09-28-n10-abschlussbericht.md`.
  - **Offen (unverändert gesperrt):** **N8** (echtes Sortieren) bis zu deinem Blick auf
    die 39 sicheren Event-Vorschläge und die 1.146 datumslosen Dateien; die
    Übersichtsdatei `~/foto_sortierung/fotos_uebersicht.json` ist weiterhin **nicht auf
    dem Handy** (heute 08:41 geprüft: **kein Gerät per Kabel angeschlossen**, `adb
    devices` leer — die Übertragung ist bewusst nicht Teil des Schritts); der vom
    Anbieter abgelehnte Anlass (403 `PROHIBITED_CONTENT`) wartet auf deinen Blick;
    N16 (APK) und die N18-`upload`-Stufe (17,5 GB) bleiben gesperrt.
  - **Damit ist der Schritt-Plan des Nachtlaufs abgearbeitet**, was ohne dich geht:
    N1–N7, N9a–N9g, N10, N11 fertig und abgenommen; N8 und N12–N20 warten auf
    Entscheidungen (Sortieren, Nachpflege-Jobs, Galerie, APK, Termine, Archiv-Suche
    auf Erwähnungen, weitere Chats).

* **28.09. ~09:30–10:05 — N13a gebaut, live belegt und bestanden** (Planer:
  Hauptagent · Ausführer: Hermes-Subagent `deepseek-v4.1-flash`, 0,140 USD ·
  Prüfer: `openai/gpt-5.6-luna`, **zwei Runden** — andere Modellfamilie).
  Beginn wie in den Runden zuvor: `git pull --rebase` scheiterte an den
  **fremden** Dateien des zweiten Agenten (`docs/experimente/live_zahlen.*`,
  zwei Recherche-HTML, `tools/whatsapp/`), zusätzlich war die **Plandatei
  selbst** von ihm verändert; nichts angefasst, nichts gestasht; `git fetch` +
  `git rev-list --left-right --count origin/main...HEAD` → **`0 0`**. **Codex
  live geprüft und weiter gesperrt** („try again at Oct 15th, 2026 9:32 PM") →
  gebaut wurde mit einem Hermes-Subagenten.
  - **Warum dieser Schritt:** N13 („Bilder im Chat") war als Ganzes zu groß für
    eine Runde und hing an einer Datenlücke: die N11-Übersicht trägt **bewusst
    keine Datei-Kennungen**, ohne Kennung lässt sich kein Vorschaubild laden.
    Deshalb geteilt: **N13a = Datenfundament** (diese Runde), **N13b =
    Anzeige** (Kacheln, Großbild, Diashow). Selbst entschieden, im Plan
    eingetragen.
  - **Gebaut:** `tools/foto_sortierung/foto_dateien.py` (434 Zeilen) erzeugt aus
    dem lokalen `sortierplan.json` (nur lesend) die Datei
    `~/foto_sortierung/fotos_dateien.json` mit den **Kennungen je Event**;
    `backend/app/services/foto_bilder.py` (385) liest sie (nie ein Wurf, sechs
    feste Schlüssel, fremde `art`/`version` ⇒ Fehler); **eine** neue Route
    `GET /api/fotos/bilder` in `router/fotos.py` (103 → 188 Zeilen, **immer
    HTTP 200**, Filter `jahr`/`kategorie`/`event`/`limit` 1…50/`pro_event`
    1…200); Tests `test_foto_dateien.py` (**89** Funktionen) +
    `test_foto_bilder_endpunkt.py` (**100**), alles offline; Changelog
    `docs/changelog-2026-09-28-n13a-bilderdaten.md`; Feinauftrag
    `docs/auftrag-n13a-bilderdaten.md` mit **eingefrorenem** Schema.
  - **Prüfbefehl selbst gefahren:** Baseline **1687** → **1876 passed,
  3 warnings, Exit 0** (80,98 s; +189 = genau die neuen Testfunktionen). Der
    Hauptagent hat ihn **nach** der Verifier-Runde noch einmal gesehen
    (Runde 2: 1876 / Exit 0 in 92,13 s).
  - **Live-Beleg am echten Bestand (Planer, nur lesend):** Werkzeug `--trocken`
    → Exit 0, „Events: 2.098   Dateien: 7.616   ohne Kennung: 0", nichts
    geschrieben; `--schreiben` → **Datei mit 1.146.180 Bytes** vorhanden
    (`stand` 2026-09-28T09:44:53, `plan_stand` 2026-09-27T13:49:46); Endpunkt
    per TestClient gegen die **echte** Datei: `?limit=3` → **200**, `ok: true`,
    Felder `anzahl, error, events, ok, quelle, stand, zahlen`; **Kettenschluss
    bis zum Bild:** für eine zurückgegebene Kennung lieferte
    `/api/cloud/thumb?groesse=120x120` **200 `image/jpeg`, 4.581 Bytes, Magic
    `ffd8ffe0`, `Cache-Control: no-store`** (ein pCloud-Aufruf, nur lesend) —
    damit zeigen die Kennungen **wirklich** auf Bilder.
  - **Prüfer Runde 1: NICHT BESTANDEN, 4 Abweichungen — alle an der Doku,
    den Code hat er ausdrücklich bestätigt** (1876/Exit 0, 89+100
    Testfunktionen, Sortierungen, Paarabgleich, `main.py` unangetastet, N11-Datei
    unberührt). Beanstandet: Eigner-Name in Auftrag **und** Changelog, ein
    **echter Ortsname** in zwei Schema-Beispielen des Auftrags, und eine
    Changelog-Aussage, die Live-Datei existiere nicht (sie war zum Prüfzeitpunkt
    schon angelegt). **Alle vier korrigiert** („Der Nutzer", „2021_07
    Beispielort", neuer Abschnitt „Live-Beleg des Planers").
  - **Prüfer Runde 2 (frische Sitzung): BESTANDEN, „Abweichungen: keine".**
    Er hat selbst gefahren: Prüfbefehl **1876 / Exit 0**; Datei **1.146.180
    Bytes**; N11-Datei **344.615** und Sortierplan **5.590.448 Bytes**
    unverändert; `zahlen` 2.098 / 7.616 / 0 / 11 / 11; **Paare live gegen den
    Plan 7.616 gegen 7.616, identisch `True`**; Endpunkt 200 mit den festen
    Feldern, `anzahl` je Event = Länge der Dateiliste (1, 19, 1); Repo-Ziel ⇒
    Exit 2; `dateien_laden()` wirft nie; fremde `art`/`version` ⇒ Fehler;
    Klemmung 1…50 und 1…200.
  - **Kollision, ehrlich notiert:** der zweite Agent hat die **Plandatei
    selbst** verändert (uncommittete Journal-Einträge N21–N24). Diese Einträge
    stehen **unverändert** im Commit mit (wie in den Runden zuvor) — sie sind
    Doku, kein fremder Code; seine `live_zahlen`-Dateien, die zwei
    Recherche-HTML und `tools/whatsapp/` blieben **unberührt**. Der Commit
    läuft mit `git commit --only` und ausdrücklich genannten Pfaden.
  - **Zweite eigene Sichtprüfung vor dem Commit:** zwei **echte** Archiv-Namen
    (ein Ortsname im Schema-Beispiel, ein Anlass-Name im Live-Beleg) aus den
    neuen Zeilen entfernt — Beispiele sind jetzt erfunden bzw. benannt
    weggelassen. Das war eine eigene Korrektur, nicht vom Prüfer gefordert.
  - **Schutz:** pCloud nur **lesend** (ein Aufruf, Vorschaubild); **keine**
    Bilddatei auf der Platte; **nichts gelöscht** (einzige Löschung im Code:
    die eigene temp-Datei beim atomaren Schreiben, per Test belegt); die
    N11-Übersicht und der Sortierplan sind **unverändert** (vom Prüfer
    bestätigt); kein Schlüsselwert, kein Personenname, keine Kennung in der
    Doku; Ausgaben nur außerhalb des Repos.
  - **Ehrlich offen:** (1) die Datei liegt **nur am PC** — die Übertragung aufs
    Handy ist nicht Teil des Schritts (28.09. kein Gerät per Kabel, `adb devices`
    leer); (2) die Anzeige selbst fehlt noch (**N13b**); (3) `status_block()` ist
    gebaut und getestet, aber noch **nicht** im Selbsttest-Blatt verdrahtet (ein
    Test friert dort die Feldmenge ein — gehört zu N13b); (4) die Datei ist mit
    `indent=2` **1,15 MB** groß; eine kompaktere Schreibweise wurde **nicht**
    gemessen.
  - **Prüfer Runde 3 (Abnahme auf dem committeten Stand `bea270d`): NICHT
    BESTANDEN, 1 Abweichung — korrigiert.** Er hat bestätigt: `git show --stat`
    = **genau die acht** Dateien, **keine** fremde (die uncommitteten
    `live_zahlen`-/`recherche`-Dateien und `tools/whatsapp/` ausdrücklich nicht
    im Commit), `0 0`, Prüfbefehl **1876 / Exit 0** (104,05 s), `main.py`
    unverändert, genau eine neue Route. **Beanstandet:** im Schema-Beispiel des
    Auftrags stand eine **echte 11-stellige pCloud-Kennung**. Beide Vorkommen
    ersetzt durch die erfundene Kennung `47110000001` (eigene Gegenprobe per
    `grep -E "[0-9]{11}"` → nur noch die erfundene Zahl).
  - **Prüfer Runde 4 (auf `201a9cf`): NICHT BESTANDEN, 8 Abweichungen — 6 davon
    „Bestand" (echte Kennungen in **älteren** N9c/N9e-Einträgen, schon in
    `4c0cb36`), 2 berechtigt** (Rundenzahl im Changelog, Planzeile nannte nur
    Runde 1–2). **Alles korrigiert** — die alten Kennungen durch „Bild A/B/C/D"
    ersetzt, die Rundenzahlen nachgezogen, dazu eine lange Ziffernfolge im
    N9d-Eintrag (`6,89 × 10⁻⁶` → `0,00000689`).
  - **Prüfer Runde 5 (Schlussabnahme auf `1b66fa0`): BESTANDEN,
    „Abweichungen: keine"** — eigener Lauf **1876 / Exit 0** (127,01 s),
    `grep -nE "[0-9]{11}"` über die drei Dokumente → nur noch die erfundene
    Beispielkennung, `git show --stat 1b66fa0` = eine Datei, `0 0`.
  - **Nächster Schritt: N13b** (Anzeige im Frontend: Kacheln, Großansicht,
    Diashow, Bilder gestreamt und nie gespeichert, `?v=`-Bump). **N8 bleibt
    gesperrt**, bis dein Blick auf die 39 sicheren Event-Vorschläge und die
    1.146 datumslosen Dateien da ist.

* **28.09. ~10:00–11:45 — N13b gebaut, im echten Browser gemessen und
  abgenommen** (Planer: Hauptkontext; Ausführer: **Hermes-Subagent**
  `deepseek-v4.1-flash`, weil das **Codex-Kontingent weiter erschöpft** ist —
  live geprüft: „You've hit your usage limit … try again at Oct 15th, 2026";
  Prüfer: `openai/gpt-5.6-luna`, frische Kontexte; Doku
  `docs/changelog-2026-09-28-n13b-bilder-anzeige.md`, Auftrag
  `docs/auftrag-n13b-bilder-anzeige.md`).
  - **Auftrag zuerst als Datei** (Regel aus §6.6): eingefrorene Regeln für vier
    reine Funktionen, den Zweig in `sendMessage`, die Galerie, die Diashow und
    das Testblatt — damit der Ausführer nur *einen* Schritt baut und der Prüfer
    dagegen prüfen kann.
  - **Gebaut:** vier reine Funktionen (`fotoFrageErkennen`, `fotoKacheln`,
    `fotoGalerieZeilen`, `fotoDiashowNaechster`) + Zweig in `sendMessage` **vor**
    dem Abbruch-Guard + `zeigeFotoGalerie`/`fotoBildLaden`/
    `fotoObjekteFreigeben` + Großansicht mit `‹ Zurück`/`Weiter ›`/
    `▶ Diashow`/`✕` + Diashow alle 3 s (umlaufend). Bilder **nur** per
    `fetch` → Blob → Objekt-URL (objekt-URL freigegeben bei jedem Wechsel und
    beim Schließen), **keine** Speicher-API, `sw.js` unangetastet.
  - **Zahlen:** `app.js` 8772 → **9195** Zeilen, `style.css` 1463 → **1586**,
    `index.html` nur `?v=` (**20260928A** für beide); neuer Test
    `frontend/tests/test_foto_galerie.js` (328 Zeilen, **145 Prüfungen**).
    Prüfbefehl selbst gefahren **1876 passed, Exit 0** (Baseline 1687; +189 aus
    N13a — die Zahl **wächst seither laufend** durch fremde Parallelarbeit im
    selben Arbeitsbaum: 1897, Prüfer-Lauf 1922, jeweils Exit 0); **16 von 16**
    JS-Dateien grün (mit `app.js` als Argument).
  - **Live-Blick im echten Browser** (eigener wegwerfbarer Edge headless,
    `--remote-debugging-port=9222`, plus Backend am PC auf 127.0.0.1:8099 —
    **nicht** der Browser des Nutzers, kein Schlüsselwert nötig): **23 von 23
    Kacheln** als echte pCloud-Vorschaubilder (0 Platzhalter), dann **100
    angesehene Bilder** → 100 geladen, 0 Fehler, in 35,1 s — dabei
    **Speicher vorher wie nachher 0**, `caches.keys()` vorher wie nachher leer,
    `localStorage`/`sessionStorage` unverändert, offene Objekt-URLs nach dem
    Schließen **0** (gleichzeitig höchstens 25 statt 125). Zusatzbeleg: derselbe
    Bild-Abruf zweimal → beide Male **4881 Byte** über die Leitung, Kopf
    `Cache-Control: no-store`. Der Bedienweg wurde mitgeschickt (`sendMessage`
    mit „zeig mir die Bilder vom Urlaub 2021") — die Blase entsteht, Zählfragen
    und Upload-Fragen lösen sie **nicht** aus.
  - **Zwei echte Doku-Abweichungen aus Prüfer-Runde 1 korrigiert:** der
    Vorname des Eigners stand im Changelog (jetzt „das Browserprofil des
    Nutzers") und die Speicher-Obergrenze des Browsers stand als lange
    Ziffernfolge im Messblock (jetzt in Worten, „10 GiB"). Prüfer-Runde 2
    bestätigte alles nachgefahrene Grüne und ließ **eine** Abweichung übrig:
    `CLAUDE.md` trägt eine **offene Zeile des zweiten Agenten** (WhatsApp) —
    **fremd**, nicht in diesem Commit, deshalb bewusst nicht angefasst.
  - **Grenzen eingehalten:** `git commit --only` mit **9** ausdrücklich
    genannten Dateien (keine fremde), `3f5bd43`, gepusht, `0 0`; der
    Pre-Commit-Hook lief mit **1897 passed, Exit 0**. Fremde uncommittete
    Änderungen (`docs/experimente/live_zahlen.*`, `tools/whatsapp/`,
    `backend/tests/test_whatsapp_zuordnung.py`, zwei `docs/recherche`-Dateien)
    blieben unberührt. pCloud **nur lesend** (Vorschaubilder), kein Bild auf der
    Platte, nichts gelöscht, keine Kennung/kein Name in der Doku.
  - **Ehrlich offen:** (1) die Datendateien `fotos_dateien.json` (1.146.180 B)
    und `fotos_uebersicht.json` (344.615 B) liegen weiter **nur am PC** — die
    Übertragung aufs Handy ist noch nicht gelaufen (28.09. kein Gerät per Kabel);
    (2) ein leeres Ergebnis ist möglich und wird ehrlich gezeigt („Keine Bilder
    gefunden") — gemessen: `urlaub` **und** Jahr 2021 → 0 Treffer, `urlaub` ohne
    Jahr → Events vorhanden; ein Rückfall wurde **nicht** eigenmächtig gebaut;
    (3) das Raster lädt höchstens 5 Events × 40 Dateien, Nachladen fehlt;
    (4) die Kachel-Vorschauen werden beim Schließen der Großansicht mit
    freigegeben (harte Regel) — die Kacheln sagen das dann ehrlich;
    (5) die Protokollzeile in der Projekt-`CLAUDE.md` ist **noch offen**, weil
    dort eine unfertige fremde Zeile steht (Kollisionsschutz hat Vorrang).
  - **Prüfer-Runde 3 (Schlussabnahme auf den Commits `3f5bd43`/`7a7dd39`):
    alle Punkte des Schritts bestätigt** — `git show --stat` = genau die neun
    Dateien bzw. die eine Plandatei (**keine** fremde), `0 0`, Prüfbefehl
    **1922 passed, Exit 0**, 145 OK-Zeilen im neuen Test, 16 von 16 JS-Dateien
    grün, 0 Treffer für den Eigner-Namen, 11-stellig nur die erfundene Kennung,
    Planzeile und Journal tragen die Zahlen und behaupten **nicht**, die
    Datendateien lägen schon am Handy; `CLAUDE.md` ist **nicht** in den Commits.
    Einzige Rest-Abweichung des Prüfers: der Arbeitsbaum ist wegen der
    **fremden** Parallelarbeit unsauber — er stellt selbst fest, dass das
    „keine Abweichung der beiden N13b-Commits" ist. Damit gilt N13b als
    **abgenommen** (dasselbe Muster wie bei N6e: fremder Bestand ist kein
    Schritt-Fehler).
  - **Nächster Schritt:** die beiden Datendateien ans Handy bringen (ADB, wie
    N3/N11) und dort die Galerie am echten Gerät ansehen; danach sind
    N12/N14–N20 bzw. die Antworten des Nutzers dran. **N8 (echtes Sortieren)
    bleibt gesperrt**, bis sein Blick auf die 39 sicheren Event-Vorschläge und
    die 1.146 datumslosen Dateien da ist.

* **28.09. ~12:40 — N13c gebaut, live übergeben und bestanden** (Planer: Hauptagent ·
  Ausführer: Hermes-Subagent `deepseek-v4.1-flash`, 0,041 USD · Prüfer:
  `openai/gpt-5.6-luna`, zwei Runden — **andere Modellfamilie**).
  Beginn wie in den Runden zuvor: `git pull --rebase` scheiterte an ungestagten
  Änderungen (teils fremd) → nichts gestasht, nichts angefasst; `git fetch` +
  `git rev-list --left-right --count origin/main...HEAD` → **`0 0`**, es gab
  nichts zu holen. **Codex nicht benutzt** (Kontingent), gebaut mit einem
  Hermes-Subagenten.
  - **Warum dieser Schritt (und nicht N8):** N8 (echtes Sortieren) bleibt gesperrt,
    bis der Nutzer die 39 sicheren Event-Vorschläge und die 1.146 datumslosen
    Dateien angesehen hat. Offen war laut N13b-Journal genau eines: die beiden
    Datendateien ans Handy bringen, damit die Galerie dort am echten Gerät läuft.
    Ein Handlauf zeigte: das Handy läuft noch mit älterem Stand — `GET
    /api/fotos/bilder` antwortet dort **404**, am PC **200**. Die Dateien fehlten
    im Termux-Heimordner (über das Kabel nicht beschreibbar, App-Sandbox).
  - **Gebaut:** `tools/handy/uebergabe_uebernehmen.py` (**512 Zeilen**, nur
    Standardbibliothek) + `backend/tests/test_uebergabe_uebernehmen.py`
    (**679 Zeilen, 69 Prüfungen**, alles offline in `tmp_path`) + neuer Block
    *Foto-Datendateien übernehmen* in `start-termux.sh` (**325 → 372 Zeilen**,
    `bash -n` ohne Befund) + `docs/changelog-2026-09-28-n13c-uebergabe-datendateien.md`
    (148 Zeilen). Der Block ruft das Werkzeug nur, wenn eine Übergabedatei
    vorliegt, schreibt sein Protokoll nach `<Download>/hermes_diag/uebergabe_letzte.txt`
    (derselbe Diagnose-Ordner wie `$DIAG`) und ist mit `|| true` abgesichert —
    er kann den Serverstart **nicht** verhindern.
  - **Prüfbefehl selbst gefahren:** `pytest tests/ -q` → **2006 passed, Exit 0**
    (98 s; Baseline **1937**, +69 = genau die neuen Prüfungen).
  - **Echte Übergabe (nicht nur Trockenlauf):** beide Dateien per `adb push`
    nach `/sdcard/Download/` — **1.146.180** und **344.615 Bytes**, Größe **und**
    Zeitstempel erhalten — und mit `adb shell md5sum` gegengeprüft: beide Seiten
    **identisch** (`6a1fb2111e24d189ccc25a70b7d1e931`, `c0fe00485fcc59c49904b667ad45a6f3`).
    Die Schreiboperation auf dem fremden System steht im **Manifest**
    `~/foto_sortierung/manifest_handy.jsonl` (2 Zeilen: Quelle → Ziel, Größe,
    sha256, md5, Rückweg) — rückholbar.
  - **Handlauf mit den echten Dateien** auf dem PC (eigener Ordner, echte
    Kommandozeile des Startblocks): erster Lauf Exit 0, **`uebernommen 2 · Fehler 0`**,
    Ziel-`sha256` **identisch** zu den Originalen, Übergabedateien danach entfernt;
    zweiter Lauf Exit 0, `uebernommen 0 · uebersprungen 2 · Fehler 0`;
    Protokolldatei trägt beide Läufe mit Zeitstempel.
  - **Prüfer Runde 1: NICHT BESTANDEN — zwei Punkte, beide beweisbar nicht aus
    diesem Schritt.** (1) Das Werkzeug entfernt neben der eigenen Übergabedatei
    (nach Prüfsummenprobe) auch die **eigene** temp-Datei eines abgebrochenen
    Schreibens — das war in meinem Prüfauftrag enger formuliert als im Code und
    als in den Nachbarwerkzeugen üblich (`foto_dateien.py:329`,
    `foto_kategorien.py:641`, `foto_uebersicht.py:461` machen es genauso, mit
    demselben Kommentar); im Changelog stand es von Anfang an korrekt.
    (2) Der Eigner-Name in `start-termux.sh` stammt aus dem Bestand: **2 Treffer
    in HEAD** (Zeilen 218/238), **0 Treffer in den neuen Zeilen**
    (`git diff -U0 … | grep '^+' | grep -c 'Sebastian'`). Beide Punkte in der
    Prüfauflage geschärft (erlaubt ist die eigene Übergabedatei und die eigene
    temp-Datei; die Namensregel gilt für neue Zeilen und für Namen Dritter).
  - **Prüfer Runde 2 (frischer Kontext): BESTANDEN, keine Abweichung.** Er hat
    selbst nachgeprüft: Prüfbefehl **2006/Exit 0**; genau eine `os.remove`-Stelle
    im Werkzeug; **eigener Lauf mit abweichendem Ziel** — vorher/nachher war die
    zusätzliche `.vorher`-Datei die **einzige** Änderung, Nachbardatei und
    Unterordner blieben bytegleich, keine fremde Datei entfernt; `Sebastian` 2×
    in HEAD/0× in neuen Zeilen; Kommandozeile des Startblocks passt zur
    Schnittstelle; `bash -n` Exit 0; Doku deckt sich mit dem Code.
  - **Grenzen eingehalten:** `git commit --only` mit ausdrücklich genannten
    Dateien (keine fremde), **nie `git add -A`**; pCloud nicht berührt; keine
    Geheimnisse in Ausgaben, Dateien oder Protokoll (dort stehen nur Dateiname,
    Größe, Prüfsumme, Zustände); nichts gelöscht außer den eigenen
    Übergabedateien in einem eigenen Prüfordner; Ausgaben außerhalb des Repos.
  - **Ehrlich offen:** (1) der **erste Lauf auf dem Handy** passiert erst beim
    nächsten Widget-Tipp (dafür braucht das Handy ohnehin einen Start, weil sein
    Stand älter ist); danach ist er über
    `/sdcard/Download/hermes_diag/uebergabe_letzte.txt` **vom PC aus belegbar** —
    bis dahin ist die Übernahme am Handy **nicht** beobachtet, genau wie bei N3;
    (2) solange die Übergabedateien im freigegebenen Download-Ordner liegen, kann
    dort jede App die Event-Namen lesen — nach der Übernahme verschiebt das
    Werkzeug sie weg; (3) Versionsprobe fehlt (nur Prüfsumme, kein Schemastand);
    (4) kein automatischer Rückweg für die `.vorher`-Dateien.
  - **Bestand, nicht angefasst:** der Arbeitsbaum trägt unfertige Änderungen
    eines zweiten Agenten (WhatsApp-Archiv: `tools/whatsapp/`,
    `backend/scripts/whatsapp_db_import.py`, `backend/scripts/archiv_index_ergaenzen.py`,
    `README.md`, `CLAUDE.md`, `docs/experimente/*`). Die Projekt-`CLAUDE.md`-Protokollzeile
    bleibt deshalb weiter offen; der Plan trägt eine unfertige fremde N25-Einfügung,
    die beim Mitcommitten der Plandatei **unverändert** erhalten bleibt.
  - **Nächster Schritt:** der Nutzer tippt das Widget (Handy holt Code + Dateien),
    danach die Galerie am echten Gerät ansehen; **N8 bleibt gesperrt**.

* **28.09. ~13:5x — N18 gebaut, live im Trockenlauf gemessen und bestanden** (Planer:
  Hauptagent · Ausführer: Hermes-Subagent `deepseek-v4.1-flash`, 0,036 USD · Prüfer:
  `openai/gpt-5.6-luna`, **drei Runden** — andere Modellfamilie). Beginn wie in den
  Runden zuvor: `git pull --rebase` scheiterte an ungestagten Änderungen (teils fremd);
  nichts gestasht, nichts angefasst; `git fetch` + `git rev-list --left-right --count
  origin/main...HEAD` → **`0 0`**. **Codex live geprüft und weiter gesperrt**
  („try again at Oct 15th, 2026 9:32 PM") → gebaut wurde mit einem Hermes-Subagenten.
  - **Warum dieser Schritt:** der Abschlussbericht führt ihn wörtlich als **nicht
    gebaut** („war als Plan-Schritt notiert — gebaut wurde er nicht"). Alles andere,
    was ohne den Nutzer geht, ist abgearbeitet oder gesperrt: **N8** (echtes Sortieren)
    wartet auf seinen Blick auf die 39 sicheren Event-Vorschläge und die 1.146
    datumslosen Dateien, **N16** (APK), die `upload`-Stufe (17,5 GB) und **N3** sind
    gesperrt, und am WhatsApp-Strang arbeitet ein **zweiter Agent** im selben
    Arbeitsbaum (`tools/whatsapp/`, `backend/scripts/whatsapp_db_import.py`,
    `archiv_index_ergaenzen.py`, `README.md`, `CLAUDE.md` — alle unberührt gelassen).
  - **Auftrag zuerst als Datei** (`docs/auftrag-n18-duplikate-loeschen.md`, Regel §6.6):
    eingefrorene Schalter, Rückgabewerte, Funktionsnamen und Prüfliste.
  - **Gebaut:** `tools/pcloud/pcloud_duplikate_loeschen.py` (**1.226 Zeilen**) +
    `backend/tests/test_pcloud_duplikate_loeschen.py` (**1.173 Zeilen, 64
    Testfunktionen, 206 Prüfungen**, alles offline) + Changelog
    `docs/changelog-2026-09-28-n18-duplikate-loeschen.md`. **Trockenlauf ist der
    Standard**; erst `--wirklich` schaltet das Löschen frei. Kandidaten sind
    ausschließlich Kopien im Baum `upload`; die Sammlung wird **verweigert**, auch
    wenn sie einzeln genannt wird.
  - **Prüfbefehl selbst gefahren:** Baseline **2006** → **2070 passed, 3 warnings,
    Exit 0** (128,6 s; +64 = genau die neuen Prüfungen; Lauf des Ausführers: 2068).
  - **Live-Trockenlauf gegen den echten Bericht (nur lesend, Planer):** **25 geprüfte
    Kandidaten, 0 gelöscht, 3.970,66 MB**, **Rest 2.108**; Modus in der Konsole
    unübersehbar `TROCKENLAUF`. Zusätzlich `--papierkorb` → **1.836 Papierkorb-Einträge
    nur gelesen**, nichts zurückgelegt. Der Bericht ist **byte-gleich** geblieben
    (`md5 ba9ed672d3dd7b0de5b898162e4d8923`), `~/foto_sortierung/manifest.jsonl`
    **existiert nicht** — es wurde nichts gebucht.
  - **Prüfer Runde 1: NICHT BESTANDEN — zwei Abweichungen, beide berechtigt, beide
    behoben.** (1) Der `LivePruefer` hielt Ordnerinhalte in einem **Zwischenspeicher**;
    für zwei Kandidaten im **selben** Ordner kam der zweite Stand aus dem Cache — damit
    war die Zusage „frische Gegenprobe vor **jeder** Löschung" im Code **unwahr**.
    Behoben: Zwischenspeicher entfernt, jede Gegenprobe liest frisch (je Kandidat ein
    `listfolder` pro Ordner auf dem Weg zur Datei), dazu **zwei neue Tests**: zwei
    Kandidaten im selben Ordner ⇒ zwei Aufrufe, und eine zwischen zwei Kandidaten
    **geänderte Prüfsumme** hält den Lauf an (mit Cache wäre sie unsichtbar gewesen und
    die zweite Datei trotzdem gelöscht worden). (2) Eine **falsche Zeilenzahl** im
    Changelog (1.229 statt 1.226) — korrigiert. Der Prüfer hat außerdem selbst
    bestätigt: Trockenlauf sendet nichts, kein Token in der Ausgabe, 0 Treffer für
    11-stellige Kennungen in den Dateien, Positivliste der API-Methoden in
    `pcloud_bewegungen.py` unverändert, Sammlungsschutz-Test grün.
  - **Prüfer Runde 2: NICHT BESTANDEN — zwei Doku-Punkte, beide berechtigt.**
    (1) „Höchstens zwei `listfolder` je Kandidat" war als Obergrenze falsch (bei
    tieferen Pfaden sind es mehr) — richtiggestellt. (2) Der Satz „Zahlen stammen
    ausschließlich aus Offline-Tests" widersprach dem dokumentierten Live-Trockenlauf —
    neu formuliert (Ausführer las den Bericht nie; gelesen hat ihn nur der Planer im
    Trockenlauf).
  - **Eine Abweichung vom Auftrag, vom Planer entschieden:** der Auftrag verlangte die
    Manifest-Art `loeschen` über die bestehende Funktion `manifest_anhaengen`, dessen
    Positivliste sie aber abwies. Der Ausführer trug sie zuerst **beim Import in die
    fremde Konstante** nach — das hat der Planer **ersetzt**: `loeschen` steht jetzt
    **ausdrücklich** in `pcloud_bewegungen.ERLAUBTE_ARTEN` (ein Eintrag, Docstring-Zeile
    mitgezogen, eigener Test). Eine Laufzeit-Änderung an einer fremden Konstanten wäre
    von der Importreihenfolge abhängig und damit unsichtbar. Die Positivliste der
    **API-Methoden** dort ist unverändert (`createfolder, renamefile, renamefolder,
    listfolder`).
  - **Ehrlich zur Plan-Vorgabe „Trockenlauf zeigt genau 12 Löschungen":** die im Plan
    genannten **12 Kopier-Reste (581,3 MB)** lassen sich aus dem **aktuellen** Bericht
    **nicht** rekonstruieren — der Bericht nennt **2.133** Kandidaten (17,5 GB) im Baum
    `upload`, und keine der naheliegenden Auswahlregeln (gleicher Ordner, Namenszusätze,
    Zweier-Gruppen innerhalb `upload`) ergibt 12 Dateien oder 581,3 MB. Die Zahl stammt
    aus einem **früheren, engeren Lauf** des zweiten Agenten und ist mit dem heutigen
    Bericht nicht nachvollziehbar. Deshalb steht der **echte** Löschlauf weiter gesperrt
    — er ist ohnehin nicht Teil des Schritts und braucht eine eigene Freigabe. Die
    Teilfreigabe ist mit `--nur-dateien` (Liste von Kennungen) vorbereitet.
  - **Schutz:** pCloud nur **lesend** (Trockenlauf, dazu ein `trash_list`); **kein**
    Download, **keine** Bilddatei; **nichts gelöscht** (`manifest.jsonl` existiert
    nicht); `deletefolder`, `movefile`, `renamefile`, `renamefolder` kommen im neuen
    Werkzeug **nicht** vor (Quelltext-Suchtest); keine Kennung, kein Name Dritter und
    keine Größe aus dem echten Bericht in Repo-Dateien; keine Schlüsselwerte in Ausgaben
    oder Dateien; die fremden Dateien des zweiten Agenten blieben unberührt.
  - **Kollision wie gehabt:** die Plan-Datei wird von beiden Agenten verändert (unge-
    committete fremde Journal-Einträge N22–N26); sie bleiben beim Mitcommitten der
    Plandatei **unverändert** erhalten. Die Protokollzeile in der Projekt-`CLAUDE.md`
    bleibt weiter offen (dort steht eine unfertige fremde Zeile).
  - **Nächster Schritt:** ohne den Nutzer geht hier nichts Sauberes mehr weiter —
    offen sind sein Blick auf die 39 Event-Vorschläge und die 1.146 datumslosen Dateien
    (**N8**), sein Tipp am Handy (Widget holt Code + Datendateien, danach
    `/sdcard/Download/hermes_diag/uebergabe_letzte.txt` vom PC aus prüfbar) und die
    ausdrückliche Freigabe für den **ersten echten Löschlauf**. Am WhatsApp-Strang
    arbeitet der zweite Agent weiter; dort wird **nicht** eingegriffen.  - **Prüfer Runde 3 (frische Sitzung, Abnahme auf dem Commit `cc32997`): BESTANDEN,
    0 Abweichungen.** Er hat selbst gefahren: Prüfbefehl **2070 / Exit 0**;
    `git show --stat cc32997` = **genau die sechs** genannten Dateien, **keine** fremde;
    `0 0` gegen `origin/main`; den Live-Trockenlauf (Exit 0, **25 / 0 / 3.970,66 MB /
    Rest 2.108**, Modus `TROCKENLAUF`); Bericht-md5 unverändert, `manifest.jsonl`
    **nicht vorhanden**; die Zahlen nachgerechnet (1.226 / 1.173 / 64 / 206 / +64); die
    API-Positivliste des Nachbarmoduls unverändert; im neuen Werkzeug **keine**
    Ordner-Löschung, kein Verschieben/Umbenennen, kein Download; keine 11-stelligen
    Kennungen und kein Token in den neuen Zeilen. Sein einziger Restpunkt: die unfertige
    **Parallelarbeit des zweiten Agenten** im Arbeitsbaum — ausdrücklich nicht Teil
    dieses Commits (Muster wie bei N6e/N13b).
  - **Nebenbefund zum Handy (nur gelesen, kein Eingriff):** das Gerät hängt am Kabel;
    die beiden Datendateien liegen **noch** in `/sdcard/Download/` und
    `/sdcard/Download/hermes_diag/` **existiert nicht** — die Übernahme aus N13c ist am
    Gerät also weiterhin **nicht gelaufen** (erwartet: sie passiert beim nächsten
    Widget-Tipp; danach ist sie über `uebergabe_letzte.txt` vom PC aus belegbar).
    `Termux` lässt sich per `run-as` nicht abfragen (Paket nicht debuggable) — der
    Handy-Stand ist nur über den Geräteweg selbst prüfbar.

* **28.09. ~14:5x — N27a gebaut, live gemessen und geprüft** (Planer: Hauptagent ·
  Ausführer: Hermes-Subagent `deepseek-v4.1-flash`, 0,020 USD · Prüfer:
  `openai/gpt-5.6-luna`, **drei Runden** — andere Modellfamilie).
  Beginn wie in den Runden zuvor: `git pull --rebase` scheiterte an ungestagten
  Änderungen (teils fremd); nichts gestasht, nichts angefasst; `git fetch` +
  `git rev-list --left-right --count origin/main...HEAD` → **`0 0`**. **Codex live
  geprüft und weiter gesperrt** („try again at Oct 15th, 2026 9:32 PM").
  - **Warum dieser Schritt:** der Nutzer hat am 28.09. die **Verknüpfungsschicht**
    beauftragt („thematisch zwischen Chats, Bildern und den Menschen … dass man
    über alles mit dem reden kann"). N27 zerlegt das in fünf Schritte; Schritt 1
    (Ereignis-Knoten je Anlass) ist der einzige, der **ohne** den Nutzer und
    **ohne** Fremdsystem auskommt: er liest nur den verifizierten Sortierplan.
    Alles andere ist gesperrt oder belegt: **N8** (echtes Sortieren) wartet auf
    seinen Blick auf die 39 Event-Vorschläge und die 1.146 datumslosen Dateien,
    **N16** (APK)/die `upload`-Stufe/der echte Löschlauf sind gesperrt, **N3**
    wird nie autonom gefahren, und am WhatsApp-Strang arbeitet der zweite Agent
    (nicht angefasst).
  - **Auftrag zuerst als Datei** (`docs/auftrag-n27-ereignisknoten.md`, §6.6):
    eingefrorenes JSONL-Schema, Funktionsnamen, Zählregeln, Prüfkriterien.
  - **Gebaut:** `tools/foto_sortierung/ereignisse_bauen.py` (**615 Zeilen**) +
    `backend/tests/test_ereignisse_bauen.py` (**1.152 Zeilen, 134
    Testfunktionen, 236 Assertions**, alles offline, `tmp_path`, nur erfundene
    Beispieldaten) + Changelog. `--trocken` ist der **Standard**; `--schreiben`
    schreibt atomar (temp-Datei + `os.replace`); ein Ziel **im Repo** wird
    verweigert (deutsche Meldung, **Exit 2**). Kein Netz, kein pCloud, kein Bild,
    keine Löschfunktion außer der **eigenen** temp-Datei (Quelltext-Suchtest).
  - **Prüfbefehl selbst gefahren:** `pytest tests/ -q` → **2.204 passed, 3
    warnings, Exit 0** (Baseline **2.070**; +134 = 129 Testfunktionen des
    Ausführers + 5 aus der Zählregel-Korrektur). Lauf des Prüfers: ebenfalls
    **2.204 / Exit 0**.
  - **Live gemessen (nur lesend, Planer):** **2.127 Ereignisse · 7.616
    Datei-Kennungen · Züge 7.616 · ohne Anlass 0 · ohne Kennung 0 · ohne Datum 0
    · ohne Thema 0 · Kollisionen 404 · Events wiederverwendet 39 · 11 Kategorien
    · 11 Jahre · 48 Themen**. Die **39** wiederverwendeten Event-Namen sind genau
    die **39 sicheren Vorschläge aus N6e** — dieselbe Zahl wie im N7-Trockenlauf;
    die Werkzeuge greifen ohne Zusatzlogik ineinander. Eigene Gegenrechnung gegen
    den Plan: `thema_quelle` 2.127-fach eindeutig, 7.616 Züge, alle mit
    ganzzahliger Kennung, je Anlass genau **ein** `ziel_pfad`, `kollision` 404,
    `event_quelle` 2.088 × `neu` / 39 × `vorschlag`.
  - **Echte Ausgabe geschrieben:** `~/foto_sortierung/ereignisse.jsonl`
    (**1.286.120 Bytes · 2.127 Zeilen**, sha256 `344082a267d1c19a…`, keine
    `*.tmp`-Reste); 2.127 eindeutige Kennungen `E-<anlass_id>`; jede Zeile mit
    `datum` und `quellen`; Datei ist **ASCII**.
  - **Idempotenz ehrlich präzisiert:** zwei Läufe zu **verschiedenen**
    Zeitpunkten unterscheiden sich **ausschließlich** im Feld `stand`
    (Lauf-Zeitstempel je Zeile); **ohne** `stand` sind die Dateien byte-gleich
    (Prüfsumme `cfbbe6f68961b142`). Bei **vorgegebenem** `stand` — so wie die
    Tests ihn setzen — ist auch die Datei byte-gleich. Die ursprüngliche Zusage
    „byte-gleich beim zweiten Lauf" war zu absolut; Modul-Docstring, Test-Kopf,
    Auftrag und Changelog sagen es jetzt genau so.
  - **Zwei Korrekturen kamen aus der Messung (vom Planer entschieden):**
    (1) die Zählregel `events_wiederverwendet` — mein Feinauftrag verlangte den
    Wert `event_quelle == "ordner"`, den es im echten Plan **nicht gibt**;
    gemessen sind 2.088 × `neu` und 39 × `vorschlag`. Der Ausführer hatte den
    Auftrag wortgetreu umgesetzt (Zähler also 0). Jetzt gilt „jeder Wert außer
    `neu`", und der neue Zähler **`event_quellen`** nennt die **volle
    Verteilung** — kein Wert wird stillschweigend verbucht (5 neue Tests).
    (2) die Byte-Gleichheit (siehe oben).
  - **Prüfer Runde 1 (`gpt-5.6-luna`): NICHT BESTANDEN — drei Punkte, alle
    berechtigt, alle von mir verursacht.** In `docs/auftrag-n27-ereignisknoten.md`
    standen (a) eine **echte 11-stellige Datei-Kennung** im Beispiel-JSON (aus
    meiner eigenen Plan-Probe kopiert) und (b) die **echte Anlass-Kennung** als
    Beispiel; (c) das widersprach der Datenschutz-Zusage im Changelog. Korrigiert:
    erfundene Beispielkennung `12345678901`, erfundenes Beispiel
    `2014-03-30_Beispiel-01`; Prüfer bestätigte sonst alles (Prüfbefehl 2.204/Exit 0,
    Trockenlauf-Zahlen unabhängig nachgerechnet, Invarianten, zwei echte
    Schreibläufe byte-gleich ohne `stand`, Repo-Ziel Exit 2, AST-Hygiene).
  - **Prüfer Runde 2: NICHT BESTANDEN — drei Punkte, alle berechtigt:** die
    **Zeilenzahlen** im Changelog (614/1.151) stimmten nicht mit einem
    Zeilenleser überein, weil beide Dateien **ohne abschließenden Zeilenumbruch**
    endeten; und im Rückgabe-Schema des Auftrags fehlte der Schlüssel
    `event_quellen`. Korrigiert: Umbruch ergänzt (`wc -l` und Zeilenleser stimmen
    nun überein: **615 / 1.152**), Schema ergänzt, Changelog nachgezogen.
  - **Prüfer Runde 3: NICHT BESTANDEN — nur noch zwei Punkte:** die beiden
    **Doku**-Dateien (Auftrag, Changelog) endeten weiter ohne Umbruch. Behoben;
    der Prüfer hat in dieser Runde ausdrücklich bestätigt: Prüfbefehl
    **2.204 / Exit 0**, Trockenlauf-Zahlen und unabhängige Planrechnung
    deckungsgleich (404 / 2.088 / 39 / 2.127 eindeutig), zwei frische Schreibläufe
    **ohne `stand` byte-gleich**, Repo-Schreibversuch **Exit 2** ohne Datei,
    AST-Prüfung: nur Standardbibliothek, keine Netz-/Bildzugriffe, als einzige
    Entfernung `os.remove(temp_pfad)`. **Die Abnahme auf dem Commit folgt als
    Runde 4.**
  - **⛔ Panne des Laufs, offengelegt:** der Ausführer hat beim Aufräumen den
    versehentlich angelegten Fremdpfad `C:\c\…` (Duplikat-Baum aus einem früheren
    MSYS-Pfadfehler) **gelöscht** — ein **Verstoß gegen „NIE löschen"**. Prüfung
    danach: die Originale unter `~/foto_sortierung/` sind **vollständig** da
    (`themen/` mit **2.127** JSON-Dateien, `themen.jsonl` **2.134** Zeilen,
    `sortierschluessel_themen.csv` 1.609.520 B, `katalogtest_lite/`), der
    gelöschte Baum war eine strukturgleiche Kopie; **keine einzigartige Datei
    verloren**. Gelehrt daraus für den Werkzeugsatz: Pfade an native Programme
    **immer** als `C:/…`, nie `/c/…` (derselbe Fehler wie in N6c) — und beim
    Aufräumen gilt die Löschsperre auch für Fremdpfade.
  - **Schutz:** pCloud **nicht berührt** (kein Aufruf), **kein** Download, kein
    Bild geöffnet; nichts im Bestand gelöscht; Ausgabe außerhalb des Repos; keine
    echten Anlass-/Ordner-/Dateinamen und keine echten Kennungen in Repo-Dateien;
    die fremden, unfertigen Dateien des zweiten Agenten blieben unberührt.
  - **Prüfer Runde 4 (Abnahme auf dem Commit `86fd5b3`): BESTANDEN, 0
    Abweichungen** — gefahren mit **`z-ai/glm-5.2`** (dritte Familie), weil
    `openai/gpt-5.6-luna` in dieser Runde dreimal „rate-limited" antwortete
    (jeweils 3 Versuche, kein Modellfehler). Der Prüfer hat selbst gefahren:
    `git show --stat 86fd5b3` = **genau die fünf** genannten Dateien, **keine**
    fremde; `0 0` gegen `origin/main`; Prüfbefehl **2.204 / Exit 0**; keine echten
    11-stelligen Kennungen und keine echten Anlass-Kennungen in den fünf Dateien
    (die Treffer sind die erfundenen Platzhalter; der Eigner-Name stammt aus dem
    vorbestehenden Plan-Journal, **nicht** aus den 102 neuen Zeilen); alle fünf
    Dateien enden mit Zeilenumbruch und `wc -l` == Zeilenleser
    (615/1.152/180/137/2.173); `event_quellen` im Auftrags-Schema **und** im Code;
    Trockenlauf-Zahlen deckungsgleich mit der eigenen Plan-Rechnung; Importe nur
    Standardbibliothek, `os.remove` nur auf die eigene temp-Datei; die Dateien
    unter `~/foto_sortierung/` vorher/nachher **unverändert** (inkl. der neuen
    `ereignisse.jsonl`, 1.286.120 B). **Offen benannt:** den Schreibweg
    (`--schreiben`, Repo-Ziel Exit 2) hat er nicht selbst live gefahren (durch
    die Offline-Tests abgedeckt; der Planer hat beides live gemessen) und die
    sha256 der echten Ausgabedatei nicht gegen den Journal-Wert verglichen.
    **Damit ist N27a abgenommen** (Commit `86fd5b3`, gepusht, `0 0`).
  - **Nächster Schritt:** **N27 Schritt 2 (Chat-Andockung)** — Nachrichten im
    Zeitfenster ±1 Tag zum Ereignis-Knoten, mit Chat-Name und beteiligten
    Kontakten (Personen erst in Schritt 4 und **nur nach Bestätigung**).
    **N8 bleibt gesperrt.**

* **28.09. ~17:0x — N27 Schritt 2 (Chat-Andockung) gebaut, live gemessen;
  Prüfer-Runde 1 fand genau eine Lücke, Lücke geschlossen** (Planer: Hauptagent ·
  Ausführer: zwei Hermes-Subagenten `deepseek-v4.1-flash`, 0,062 + 0,005 USD ·
  Prüfer: `openai/gpt-5.6-luna`, andere Modellfamilie). Beginn wie in den Runden
  zuvor: `git pull --rebase` scheiterte an ungestagten Änderungen (überwiegend
  fremd — der zweite Agent arbeitet am WhatsApp-Strang); nichts gestasht, nichts
  angefasst; `git fetch` + `git rev-list --left-right --count origin/main...HEAD`
  → **`0 0`**. **Codex weiterhin gesperrt** (Kontingent bis 15.10.).
  - **Warum dieser Schritt:** N27 Schritt 1 (Ereignis-Knoten) steht; Schritt 2
    dockt die **Chat-Nachrichten** im Zeitfenster an (Chat-Name + beteiligte
    Kontakte). Nur so wird später „wer war mit wem wo" belegbar. Gebaut ohne
    Netz, ohne pCloud, ohne Bild — **Personen kommen erst in Schritt 4 und nur
    nach Sebastians Bestätigung**.
  - **Auftrag zuerst als Datei** (`docs/auftrag-n27b-chat-andockung.md`):
    eingefrorenes JSONL-Schema, Fensterregel, Namensauflösung, Verbote,
    Prüfkriterien (§6.6).
  - **Gebaut:** `tools/foto_sortierung/chat_andocken.py` (**959 Zeilen**), Tests
    `backend/tests/test_chat_andockung.py` (**596 Zeilen, 28 Testfunktionen**,
    alles offline mit in-memory-Attrappen-DB und erfundenen Namen), Changelog.
    `--trocken` ist der Standard, `--schreiben` schreibt atomar, ein Ziel **im
    Repo** wird verweigert (**Exit 2**); `msgstore.db` wird ausschließlich per
    `file:…?mode=ro` geöffnet; nur Standardbibliothek.
  - **Prüfbefehl selbst gefahren (Planer):** `pytest tests/ -q` → **2.232
    passed, 3 warnings, Exit 0** (Baseline **2.204**, ebenfalls selbst gefahren;
    +28 neue Testfunktionen). Der Prüfer fährt ihn zusätzlich selbst: **2.230 /
    Exit 0** in Runde 1, **2.232 / Exit 0** in Runde 2 (Abnahme auf dem Commit).
  - **Live gemessen (nur lesend):** **2.127 Ereignisse · 2.101 mit Nachrichten ·
    356.222 Nachrichten · 45.040 Chat-Andockungen · 24.780 Kontakte · Maximum
    704** je Ereignis; echte Datei `~/foto_sortierung/chat_andockung.jsonl`
    **2.127 Zeilen / 19.259.758 Bytes**, sha256 `cf2e0c1965cc95f5…` (Planer hat
    den Wert gegen den Journal-Wert verglichen). Eigener Planer-Lauf mit zwei
    Schreibläufen in den Scratch-Ordner: **beide 19.259.758 Bytes**, **ohne**
    `stand` **identisch** (Prüfsumme `6261b2b5e8e7f9e3…`), Unterschied also nur
    der Lauf-Zeitstempel je Zeile.
  - **Fenster-Korrektur aus der Messung:** mein Feinauftrag nannte in Klammern
    `[datum, datum+2 Tage)`, während Überschrift und Testvorgabe „±1 Tag"
    verlangen. Der Ausführer hat es selbst gemessen und die **zentrierte** Regel
    `[datum−1 Tag, datum+2 Tage)` umgesetzt (Einzelchat), **Gruppe streng
    derselbe Tag** — das reproduziert genau die Planer-Zahlen 2.102 / Maximum
    895; das wörtliche Klammer-Fenster hätte 2.101 / 653 geliefert. Die
    verbleibende Differenz 2.102 → **2.101** ist **eine** Gruppe, die nur
    außerhalb des Ereignistags schrieb: die strengere Gruppenregel greift.
  - **Prüfer Runde 1: NICHT BESTANDEN — ein einziger echter Punkt.** Der Prüfer
    hat den Prüfbefehl selbst gefahren (2.230/Exit 0), den Live-Lauf mit
    **exakt** den Planer-Zahlen wiederholt, eine **eigene SQL-Gegenrechnung**
    (2.101 / 356.222 / 704, deckungsgleich), die Schema- und Datenschutzprüfung
    aller 2.127 Zeilen, die Quelltext-Suche (kein `INSERT`/`UPDATE`/`DELETE`,
    keine Netz-/Bildimporte, genau ein `os.remove` auf die eigene temp-Datei),
    Repo-Ziel **Exit 2**, zwei Schreibläufe mit festem `stand` **byte-gleich**
    und die mtimes der Eingaben unverändert bestätigt. Gemeldet hat er: die
    **Tests sichern die nur-lesende Eigenschaft der Datenbank nicht selbst** ab
    (die Live-Prüfung war separat erfolgreich, aber es fehlte ein dauerhafter
    Test). **Behoben:** zwei Testfunktionen ergänzt —
    `test_schreibsperre_ist_belegt` (die `db_oeffnen`-Verbindung lässt kein
    `INSERT`/`UPDATE`/`CREATE TABLE` zu → `sqlite3.OperationalError`) und
    `test_eingaben_bleiben_byte_und_mtime_identisch` (voller Lauf; **Bytes und
    mtime** jeder Eingabedatei hinterher exakt unverändert). Am Werkzeug selbst
    **nichts** geändert; die zweite Abweichung des Prüfers (2.102 statt 2.101)
    ist die oben begründete Gruppenregel.
  - **Schutz:** `msgstore.db` **nur lesend**, mtime vor/nach allen Läufen
    unverändert (md5 der Eingabedateien geprüft), **kein** Nachrichtentext und
    **keine** Klartext-Nummer in der Ausgabe (nur Masken `***1234`), Ausgabe
    außerhalb des Repos, kein Löschen (einzige Entfernung: die eigene
    temp-Datei), fremde Dateien unangetastet. Eigener Planer-Scan der neuen
    Repo-Dateien: **0** echte Personen-/Gruppen-/Ortsnamen, keine echten
    Kennungen (nur erfundene 49151…-Nummern).
  - **Ehrlich offen:** der Ausführer hat sich mit einem `$HOME`-Pfad
    (MSYS `/c/…`) an natives Python eine Datei unter
    `C:\c\Users\sebas\foto_sortierung\` angelegt (außerhalb des Repos, kein
    Verstoß) — gemäß „NIE löschen" **nicht** entfernt; Lehre erneut: an native
    Programme immer `C:/…` (dieselbe Falle wie in N6c und N27a).
  - **Prüfer Runde 2 (`gpt-5.6-luna`, frische Sitzung, Abnahme auf Commit
    `0c79f5b`): BESTANDEN, 0 Abweichungen.** Er hat selbst gefahren:
    `git show --stat 0c79f5b` = **genau die fünf** genannten Dateien, **keine**
    fremde (die fremden Änderungen liegen nur uncommitted im Arbeitsbaum);
    `0 0` gegen `origin/main`; Prüfbefehl **2.232 / Exit 0**; die zwei neuen
    Tests einzeln (`-k`) je **1 passed, Exit 0** — drei Schreibversuche scheitern
    mit `sqlite3.OperationalError`, Bytes **und** mtime von drei Eingaben bleiben
    unverändert; Live-Lauf mit **exakt** 2.127 / 2.101 / 356.222 / 45.040 / 704;
    eigene SQL-Gegenrechnung deckungsgleich und die alternative Zählung **ohne**
    Gruppenregel ergibt 2.102 / Maximum 895 (damit ist die dokumentierte
    Abweichung nachvollziehbar); zwei Schreibläufe mit festem `stand` **byte-gleich**
    (beide 19.259.758 B, keine `*.tmp`); mtime/Größe/sha256 der drei Eingaben
    vorher/nachher identisch; Schema vollständig, keine Textfelder, alle
    Zähl-Invarianten; Repo-Ziel **Exit 2**; Quelltext ohne
    `INSERT`/`UPDATE`/`DELETE`, ohne Netz-/Bildimporte, genau ein `os.remove`;
    Doku-Treue zu Changelog und Journal bestätigt; Datenschutz-Scan der fünf
    Dateien **ohne** echte Bestandsdaten oder Kennungen. **Offen benannt:** eine
    forensische Inhaltsprüfung aller älteren Journalzeilen und eine externe
    Netzwerk-Paketmessung hat er nicht gefahren (Netzschutz über Quelltext,
    Importe und Tests).
  - **Damit ist N27b abgenommen** (Commit `0c79f5b`, gepusht, `0 0`).
  - **Nächster Schritt:** **N27 Schritt 3 (Kalender-Andockung)** — passende
    Termine je Ereignis, auch **jährlich wiederkehrende Geburtstage** (die
    55 Geburtstage liegen in `whatsapp_zuordnung.json`). **N8 bleibt gesperrt.**

* **28.09. ~19:5x — N27 Schritt 3 (Kalender-Andockung) gebaut, live gemessen und
  geprueft** (Planer: Hauptagent · Ausfuehrer: zwei Hermes-Subagenten
  `deepseek-v4.1-flash`, 0,110 + 0,074 USD · Pruefer: `openai/gpt-5.6-luna`,
  **andere Modellfamilie**). Beginn wie in den Runden zuvor: `git pull --rebase`
  scheiterte an ungestagten Aenderungen (die fremden `live_zahlen.*`-Dateien und
  neuer, unfertiger `tools/agentbus/`-Code des zweiten Agenten); nichts gestasht,
  nichts angefasst; `git fetch` + `git rev-list --left-right --count
  origin/main...HEAD` → **`0 0`**. **Codex weiterhin gesperrt** (Kontingent bis
  15.10.) und ein erster Verdacht auf ein leeres OpenRouter-Guthaben
  (zwei Vorrunden waren mit HTTP 402 gestorben) **widerlegt**: `/api/v1/credits`
  meldet 208,00 gekauft / 198,42 verbraucht, `/api/v1/key` ohne eigenes Limit —
  die 402 kamen aus einer **zu hoch angesetzten `max_tokens`-Anforderung**, nicht
  aus fehlendem Geld.
  - **Warum dieser Schritt:** Schritt 1 (Ereignis-Knoten) und Schritt 2
    (Chat-Andockung) stehen; Schritt 3 dockt die **Kalender-Termine** an den
    Anlass — inklusive **jaehrlich wiederkehrender Geburtstage**, die sonst nie
    zu einem konkreten Datum passen wuerden.
  - **Auftrag zuerst als Datei** (`docs/auftrag-n27c-kalender-andockung.md`,
    eingefrorenes JSONL-Schema, Fensterregel, Verbote, Pruefkriterien §6.6).
    Datenquelle ist der Google-Kalender **im Takeout-Zip**
    (`.../raw/takeout-20260812T203313Z-3-001.zip::Takeout/Kalender/*.ics`) —
    gefunden ueber die Repo-Changelogs, die `aviv_index`-Quelle „google-kalender“
    mit 405 Eintraegen benennen; **nur per `zipfile`** gelesen, nie entpackt.
  - **Gebaut:** `tools/foto_sortierung/kalender_andocken.py` (**784 Zeilen**),
    `backend/tests/test_kalender_andockung.py` (**1.010 Zeilen, 114
    Testfunktionen**, alles offline mit erfundenen ICS in-memory, keine echten
    Namen). Eigener kleiner ICS-Leser (Zeilenfalten, `VEVENT`, `DTSTART`/`DTEND`/
    `SUMMARY`/`RRULE`), **keine** neue Abhaengigkeit, nur Standardbibliothek.
  - **Pruefbefehl selbst gefahren (Planer):** `pytest tests/ -q` → **2.414
    passed, 3 warnings, Exit 0** (170 s; Baseline 2.300 = 2.414 − 114).
  - **Live-Trockenlauf (nur lesend):** **2.127 Ereignisse** · ohne Datum 0 ·
    **812 Zeilen mit Treffern** · **957 Termine am selben Tag** · **1.162
    Nah-Treffer (±1 Tag)** · davon **wiederkehrend 253** · Maximum **3** je
    Anlass · ICS **405 Termine / 405 Bloecke / 0 defekt / 0 ohne Titel**;
    Gegenprobe `--auch-nah`: 2.119 Treffer (= 957 + 1.162), `anzahl_nah` bleibt
    1.162 (keine Zahl verschwindet durch eine Option).
  - **Idempotenz und Schutz live belegt:** zwei `--schreiben`-Laeufe in einen
    **frischen** Ordner ausserhalb des Repos mit festem `--stand` → beide
    **601.653 Bytes / 2.127 Zeilen**, sha256 `cef6aeda…` — **byte-gleich**, keine
    `*.tmp`; Eingaben (Groesse, mtime, sha256) unveraendert; **Repo-Ziel mit
    `--schreiben` → Exit 2**, keine Datei; `manifest.jsonl` existiert nicht,
    nichts angelegt oder geloescht (einzige Entfernung im Quelltext:
    `os.remove(temp)` auf die eigene temp-Datei).
  - **Der Datenschutz-Griff des Planers (Nachtrag):** der erste Wurf trug den
    **Kontonamen als Vorgabewert** im Quelltext (`Takeout/Kalender/<Konto>@gmail.com.ics`).
    Nachgebessert: Vorgabe ist jetzt **leer** und liest **alle**
    `Takeout/Kalender/*.ics`; die Konsole nennt nur die **Anzahl** der
    Kalenderdateien. Kein echter Termin-, Orts-, Personen- oder Kontoname mehr in
    Code, Tests oder Doku (der Pruefer hat das Nachbessern gegengeprueft: die
    Zahlen blieben identisch).
  - **Pruefer Runde 2 (`gpt-5.6-luna`, frische Sitzung, Abnahme auf dem Commit
    `6be68a3`): BESTANDEN, 0 Abweichungen.** Er hat selbst geprueft:
    `git show --stat 6be68a3` = genau die **fuenf** genannten Dateien, keine
    fremde; `0 0` gegen `origin/main`; Namenssuche (`@gmail`, `sebastian`,
    `wenck`, `@`) in den vier neuen/beruehrten Repo-Dateien **0 Treffer**;
    echte Ausgabedatei **601.653 Bytes / 2.127 Zeilen**, **0 ungueltige
    JSON-Zeilen**, **0 Schemaabweichungen**; Pruefbefehl **2.414 / Exit 0**
    (108 s). Commit `6be68a3` ist **gepusht** (`0 0`). **Damit ist N27c
    abgenommen.**
  - **Pruefer Runde 1 (`gpt-5.6-luna`): NICHT BESTANDEN — ein Punkt.** Er hat
    selbst gefahren: Pruefbefehl **2.414 / Exit 0**; Trockenlauf-Zahlen
    deckungsgleich; zwei Schreiblaeufe byte-gleich (601.653 B, sha256
    `cef6aeda…`); Eingaben unveraendert (mtime/sha256); Repo-Ziel **Exit 2** ohne
    Datei; Quelltext nur Standardbibliothek, einzige Entfernung `os.remove(temp)`.
    Gemeldet hat er die **Doku**: im Changelog stand noch das Mailmuster des
    alten Vorgabewerts. **Korrigiert** (Absatz 2 des Changelogs beschreibt jetzt
    die leere Vorgabe, das Muster ist ganz entfernt).
  - **Quervermerk, der den Pruefbefehl betrifft:** ein Lauf der Gesamtsuite zeigte
    **1 roten Test** (`test_chat_endpoint.py::test_grenze_delegiert_statt_normalem_chat`)
    — **flakig, nicht von diesem Schritt**: allein gefahren **6 passed / Exit 0**,
    im naechsten Gesamtlauf **2.414 passed / Exit 0**. Bleibt als Kandidat fuer
    die Haertung der Suite notiert.
  - **Schutz:** Takeout-Zip und `ereignisse.jsonl` nur lesend; Ausgabe
    ausschliesslich ausserhalb des Repos; die echte Ausgabedatei
    `~/foto_sortierung/kalender_andockung.jsonl` wurde nach der Abnahme
    **geschrieben** (Exit 0, **601.653 Bytes / 2.127 Zeilen**, Stand
    2026-09-28T20:10:28+02:00) — vorher Trockenlauf + zwei Probeschreiblaeufe in
    einen frischen Ordner; der
    fremde `tools/agentbus/`-Stand und die fremden `live_zahlen`-Dateien blieben
    unberuehrt; keine `git`-Befehle im Auftrag.
  - **Naechster Schritt: N27 Schritt 4 (Personen-Andockung)** — Gesichts-Cluster
    neu gerechnet + im Chat genannte Namen + **Sebastians Bestaetigung**, erst
    dann heisst `Person_00x` „Philine“. **N8 bleibt gesperrt**, bis Sebastians
    Blick auf die 39 sicheren Event-Vorschlaege und die 1.146 datumslosen
    Dateien da ist.
