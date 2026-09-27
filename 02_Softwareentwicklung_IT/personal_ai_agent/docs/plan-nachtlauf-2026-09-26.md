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
| N9b | **Personen-Stufe echt rechnen**: Modelle (YuNet + SFace) auf den PC holen bzw. auf dem Handy rechnen lassen, `cv2`/`onnxruntime` in **eigenem** venv (Projekt-venv bleibt unberührt), Gesichter in Jahres-Stapeln erkennen, `kachel_holen` an den echten Weg anstecken (pCloud/Handy) | echte Cluster-Anzahl je Stichprobe (Jahres-Stapel), Referenzseiten mit echten Gesichtern, Massen-Regel am echten Foto belegt | ✅ **gebaut + echt gemessen (27.09.)** — Modellweg am PC: **eigenes venv** `~/foto_sortierung/venv_gesicht` (opencv-contrib 5.0.0.93, onnxruntime 1.30.0; Projekt-venv unberührt), Modelle **öffentlich aus dem OpenCV-Zoo** nach `~/foto_sortierung/ml_models/` (232.589 B + 38.696.353 B). Werkzeug `tools/foto_sortierung/gesicht_erkennen.py` (835 Zeilen) + **80** Tests (850 Zeilen) + echte pCloud-Kachelquelle; Prüfbefehl selbst gefahren **1175 passed, Exit 0** (Baseline 1095). **Echte Messung:** 24 Bilder (16 aus 2020 + 8 aus dem bilderstärksten Mengen-Anlass), **72 Gesichter auf 19 Bildern**, 0 Fehler, 88,4 s; N9a darauf: `leer 8 · gruppe 12 · menge 0 · unklar 4`, **2 Gruppen (6 und 40)**, **6 Referenzseiten mit echten Gesichtsausschnitten** (59–102 KB), 2. Lauf **0** neue Dateien. **Befund:** Mengen-Regel greift, aber über den Zweig `leer` — die winzigen Gesichter liegen **unter** `ANTEIL_MIN`, der Zweig `menge` wurde am echten Foto **nicht** erreicht (Entscheidung: Schwelle nicht angetastet → Kandidat **N9c**). Prüfer `gpt-5.6-luna`: Runde 1 NICHT BESTANDEN wegen eines Katalog-Eintrags im Changelog (seit `92b04c3` im Repo = Fehlalarm), Runde 2 **BESTANDEN**. Doku: `docs/changelog-2026-09-27-gesicht-erkennen.md`, Auftrag `docs/auftrag-n9b-gesicht-erkennen.md` |
| N9c | **Mengen-Zweig am echten Foto erreichbar machen** (`ANTEIL_MIN` mit Messung prüfen) + `kachel_quelle` um den **Gesichtsausschnitt** ergänzen (in-memory, statt ganzes Foto) | `menge`-Zweig an echten Mengen-Fotos erreicht; Kacheln zeigen Gesichter | ✅ **bestanden (27.09.)** — `ANTEIL_MIN` **0,0005 → 0,00001** (gemessen: das alte Tor verwarf **echte** Funde, kleinste echte Detektion 0,000145 bzw. 0,000022); `kachel_quelle(..., ausschnitt=True)` schneidet in-memory um das Gesicht (**nur PIL**, Rand 0,45 × bbox, Rückfall aufs ganze Foto statt Abbruch, reine Funktion `ausschnitt_rechnen`), CLI `--ausschnitt`. Prüfbefehl selbst gefahren **1196 passed, Exit 0** (Baseline 1175); **30 echte Mengen-Bilder**: vorher `gruppe 12 · leer 9 · unklar 9 · menge 0` → nachher `gruppe 12 · leer 6 · unklar 11 · menge 1` (**„1 von 30"**, nicht schöngeredet); `gruppe` unverändert = keine Regression. **Offen als N9d:** `bbox` im Vektorzeilen-Lauf verdrahten (`kachel_quelle` liest `fileid`, N9a-Einträge tragen `bild_id`) + N9b-Lauf mit neuem `ANTEIL_MIN` wiederholen; `MENGE_ANZAHL = 6` bleibt unangetastet (N9a-Beschluss, braucht eigene Messung). Prüfer `gpt-5.6-luna`: **BESTANDEN, 0 Abweichungen**. Doku: `docs/changelog-2026-09-27-mengen-zweig.md`, Auftrag `docs/auftrag-n9c-mengen-zweig.md` |
| N9d | **Gesichtsausschnitt verdrahten + N9b-Messung wiederholen**: `bbox`/`bild_id` in der Kachelquelle zusammenführen (N9a-Einträge tragen `bild_id`, `kachel_quelle` liest `fileid`), N9b-Vektorlauf mit dem neuen `ANTEIL_MIN` über eine **breitere** Mengen-Stichprobe | Ausschnitt-Kacheln messbar schärfer; `menge`-Anteil über mehr als 30 Bilder beziffert (nicht mehr „1 von 30") | ⬜ **offen** (aus dem N9c-Befund, 27.09.) |
| N10 | **Doku + Protokoll + Abschlussbericht** (Changelogs, `CLAUDE.md`, Planjournal) | alles committet, Bericht mit Zahlen | ⬜ |

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
    `56226031437` `leer`→`unklar` (3 nutzbare), `56226986963` `leer`→`unklar` (1),
    `56226987597` `leer`→`unklar` (5), **`56226986656` `unklar`→`menge`**
    (13 nutzbare, **0** erkennbare). Das **`menge`-Bild**: fileid `56226986656`,
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
