# Übergabeprotokoll – Personal AI Agent

**Stand:** 28.10.2026, 12:20 Uhr
**Repo:** `workspace agentic engineering`, Branch `main`
**HEAD:** `649a163` (docs(personal-ai-agent): Uebergabeprotokoll 28.10.2026)
**Basis darunter:** `20dbb87` (fix(concertify)) — dieser Commit ist noch **nicht**
gepusht, stammt aus einer anderen Sitzung und gehört nicht zu diesem Protokoll.
**Prüfbefehl:** `cd backend && .venv/Scripts/python.exe ../tools/gate/tor.py --wartezeit 600`
(Gate mit Sperre — mehrere Agenten teilen sich diesen Arbeitsbaum, zwei
gleichzeitige Läufe machen das Tor fälschlich rot.)
**Prüfstand, gemessen in dieser Sitzung (28.10.2026):**
**6018 passed, 3 skipped, 5 warnings, Exit 0** — Laufzeit **6007 Sekunden
(1:40:07)**.
Die Zahl 2935 grün, die in der Bereichs-`CLAUDE.md` vom 29.09.2026 steht, ist
veraltet. Das Projekt ist seither stark gewachsen.
**Praxis-Hinweis:** Ein voller Prüflauf dauert rund 1 ¾ Stunden. Wer den
Prüfbefehl „nur mal kurz" startet, blockiert damit das Commit-Tor für andere
Agenten. Deshalb läuft er über `tor.py`, nicht direkt über pytest.

---

## 1. Was diese Sitzung ergeben hat (kurz, mit Beleg)

**1.1 OpenRouter-Datenschutz: der Inhalts-Schalter war die ganze Zeit an.**
Die Observability-Einstellung „Input & output logging" des Workspace war
aktiviert. Damit hat OpenRouter Prompt- und Antwortinhalte serverseitig
gespeichert — nicht der Modellanbieter, sondern OpenRouter selbst. Wichtig:
das ZDR-Routing auf der Privacy-Seite verhindert das **nicht**, ZDR regelt nur
die Anbieter-Strecke.
Erledigt: Schalter ausgeschaltet. Neuer Inhalt wird nicht mehr gespeichert.
Offen: gespeicherte Inhalte liegen mindestens 3 Monate (danach nach Ermessen
OpenRouters); kein Selbstbedienungs-Löschen, nur per Mail an
`support@openrouter.ai` durch den Kontoinhaber.
Datei mit der fertigen Löschmail: `C:\Users\sebas\Desktop\OpenRouter-Loeschantrag.md`
(Platzhalter für die Anmelde-Adresse ist noch einzusetzen, aus dem angemeldeten
Konto senden, Bestätigung des Supports aufbewahren).
Skill mit den Regeln: `ai-datenschutz-regeln` (aktualisiert 28.10.2026).

**1.2 Websuche-Bestand — gemessen, nicht geschätzt.**
Hermes (dieser Desktop-Agent) sucht **nicht** über OpenRouter:
Log-Beleg vom 28.10.2026, 11:47 — „Web search via parallel", „Web extract via
exa" und „via keenable". Das sind Hermes-eigene Anbieter.
Der Agent im Projekt nutzt OpenRouters Websuche, und zwar über den alten Weg:
`backend/app/services/web_suche.py` schickt `plugins: [{"id": "web", …}]` mit,
geschützt durch Namensprüfung (`websuche_schutz`) und kontextfreien Suchtext.
Ein Grep über das ganze Repo findet genau diesen einen Ort — **kein** advisor,
subagent, fusion, shell, bash, apply_patch, image_generation, datetime,
tool_search oder search_models wird irgendwo angefordert.
Folge für die Workspace-Werkzeugliste auf OpenRouter: „Web Search" offen lassen
(sonst bricht die Suche des Agents), alles andere kann zu — vorher aber einmal
lebend testen.

**1.3 Rechtliche Einordnung zu Bildinhalten (Ergebnis, keine Details).**
Reine Nacktbilder sind keine Pornografie; für Kinder unter 14 gibt es in
§ 184b StGB **keine** Ausnahme für Familie oder Eigenbedarf (die gibt es nur in
§ 184c für 14- bis 17-Jährige). Maßstab ist der Inhalt und ein objektiver
Betrachter, nicht die Absicht der Familie. Praktische Folge für das Archiv:
Bilder, deren eigentlicher Gegenstand der Genital- oder Gesäßbereich ist oder
die sexualisierend wirken, gehören **gelöscht**, nicht archiviert. Für
Hochsensibles: gar nicht senden, nicht „mit ZDR senden". Keine Rechtsberatung —
bei einem konkreten Grenzfall entscheidet ein Anwalt.

**1.4 Messung: wie oft der Anbieter blockiert hat.**
Genau **einmal**. Beleg: `~/foto_sortierung/n6b_probe_2022-09-05.log` —
„Fehler-code: 403", „Gemini blocked the request: PROHIBITED_CONTENT",
betroffen der Bogen `2022-09-05_Anlass-02` (123.153 Bytes).
Alle Logs des Foto-Archivs wurden danach durchsucht: kein zweiter Treffer.
Hinweis: Der Anbieterfilter feuert nicht nur bei Nacktheit. Der eine 403 sagt
also nicht, was auf dem Bogen war.

---

## 2. Offene Aufgabe A — lokaler Vorfilter + Marker „Privat"

**Ziel:** Bevor eine Kachel in einen Kontaktbogen wandert und der Bogen
rausgeht, wird sie **lokal** geprüft. Treffer heißt: Kachel wird nicht
mitgeschickt. Zusätzlich werden Anlässe mit Treffern als Vorschlag „Privat"
gelistet.

**Entschieden (Sebastian, 28.10.2026):**
- Die neue Bezeichnung heißt **Privat**.
- Geprüft wird bei **allen** Anlässen, nicht nur bei privaten — sonst geht bei
  jedem anderen Anlass weiter raus, was blockt.
- Der Marker ist ein **Vorschlag**. Bestätigt wird von Sebastian, wie bei den
  Personennamen. Die Maschine benennt nichts selbst.
- Es wird nichts gelöscht, nichts verschoben; nur das Senden entfällt.

**Noch offen:**
- Schwelle: ab wie vielen Treffer-Kacheln ein Anlass als Vorschlag „Privat"
  erscheint (ein Treffer pro Kachel, oder erst ab mehreren im Bogen).
- Ob der einmalige Rücklauf über die schon vorhandenen Bögen mitläuft
  (11 Jahres-Ordner unter `~/foto_sortierung/boegen/`, im Jahr 2022 allein 818
  Bögen, je `.jpg` und `.json`).
- Vorschlag vom 28.10.2026: erst eine **Stichprobe von 100 Kacheln** messen
  (Rechenzeit pro Kachel, Trefferquote), dann über den Umfang entscheiden.
  Sebastian hat dieser Messung noch nicht ausdrücklich zugestimmt.

**Technischer Stand, gemessen:**
- Im Projekt-venv `backend/.venv` **fehlen** `cv2` und `onnxruntime`
  (vorhanden: numpy 2.4.6, PIL 12.3.0, requests 2.34.2).
- Laut Kopfkommentar von `tools/foto_sortierung/gesicht_erkennen.py` (Zeile 9 ff.)
  liegt `cv2`/`onnxruntime` **bewusst in einem eigenen venv**; dort steht auch
  der Pfad. Dieses Werkzeug lädt `cv2` lazy, damit es ohne OpenCV importierbar
  bleibt und die Tests mit einem Attrappen-Detektor laufen.
- Also: für den Filter entweder dieses eigene venv nutzen oder einen Weg ohne
  cv2/onnxruntime bauen. Vor dem Bau klären, nicht raten.
- Vorbild für die Bauweise ist `gesicht_erkennen.py`: Bilder **nur in-memory**,
  keine Bilder auf die Platte, kein Löschaufruf, kein Schreiben ins Repo
  (Repo-Pfad ⇒ Klartextmeldung + `SystemExit(2)`), keine Namen und Pfade in der
  Ausgabe, pCloud-Quelle wird eingesteckt (Duck-Typing).
- Die Trefferliste bleibt **außerhalb** des Repos, nur Kennungen und Zählungen,
  keine Vorschaubilder, kein Katalog.
- Bei einem 403 weiterhin **nicht** blind wiederholen, sondern den Anlass offen
  liegen lassen. So macht es die Pipeline heute schon.

**Gate für den Bau:** neuer Code braucht Tests, `pytest` muss grün sein, Doku im
selben Commit. Feature über ~100 Zeilen ⇒ vorher Grill (`grillAnAgent`).

---

## 3. Offene Aufgabe B — OpenRouter-Einstellungen

- **Erledigt:** „Input & output logging" aus.
- **Offen:** Löschantrag senden (Datei auf dem Desktop, siehe 1.1).
- **Zu prüfen, nicht anzunehmen:** Der Kontoschalter „Allow 1 % data discount in
  workspaces" regelt nur die Erlaubnis — zustimmen muss jeder Workspace
  **einzeln**. Beide Ebenen ansehen (`openrouter.ai/workspaces/<id>/settings`
  und `.../observability`).
- **Nebenbei:** API-Key-Laufzeit steht auf „No expiration". Das ist verschenkte
  Sicherheit; Vorschlag 90 Tage, betroffene Schlüssel benennen.
- Nicht per API prüfbar: Diese Kontoeinstellungen sind nur im Dashboard
  sichtbar. Der Management-Key zeigt nur Key-Listen.

---

## 4. Zusammenarbeit mit dem Handy

Es gibt zwei Wege, beide mit Manifest und ausdrücklichem Rückweg. **Nie löschen,
nur kopieren und verschieben.**

**Weg 1 — pCloud, kabellos (Regelfall).**
Zielordner `/Agent/uebergabe/` im eigenen pCloud-Konto.
Schreiber: `tools/foto_sortierung/pcloud_agent_schreiber.py` (neu, noch nicht
versioniert — siehe Abschnitt 5).
Manifest: `~/foto_sortierung/uebergabe_manifest.jsonl`, je Zeile:
`zeit`, `name`, `quelle`, `ziel`, `groesse`, `pruefsumme`, `fileid`.
Letzter Eintrag: 18.10.2026, `video_standbilder.jsonl`.

**Weg 2 — ADB aufs Handy, mit Kabel.**
Ziel `/sdcard/Download/…`; Manifest `~/foto_sortierung/manifest_handy.jsonl`
mit `sha256`, `md5`, `art` (push / festgestellt), laufender Nummer (`N29b-1`)
und Feld `rueckweg` in Klartext („auf dem Handy die Übergabedatei löschen; das
PC-Original bleibt unverändert").
Voraussetzung: Datenkabel **und** USB-Modus „Dateiübertragung".

**Was aufs Handy noch fehlt:** die Übersichtsdatei
(`anlaesse-uebersicht.md` / `.html`), laut Abschlussbericht N10 offen.

**Rollen (unverändert):** Track A = PC-Hermes, Track C = lokaler Hermes am Handy
(Termux, Inbox-Daemon, FastAPI auf 8080). Das Handy zieht beim Start `main`;
auf `main` pusht nur der PC.

---

## 5. Zustand des Arbeitsbaums (wichtig für den nächsten Chat)

Im Baum liegen Änderungen, die **nicht** aus dieser Sitzung stammen. Sie dürfen
nicht mitgerissen werden:

- geändert: `backend/tests/test_bestand_und_handy_uebergabe.py`,
  `docs/agentbus-protokoll.md`, `tools/foto_sortierung/bestand_pruefen.py`,
  `docs/experimente/live_zahlen.html` und `.json`,
  `werkzeuge/fortschritt/status.json`
- neu (untracked): u. a. `tools/foto_sortierung/pcloud_agent_schreiber.py`,
  `tools/pruefkreis/hermes_plugin/`, `docs/recherche/datenkontrolle-anbieter.html`,
  `docs/recherche/ki-training-schutzformen.html`, `werkzeuge/schaufenster/`
- Konflikt-Reste: `werkzeuge/fortschritt/status [conflicted].json` und
  `status [conflicted 2].json` — aufräumen oder bewusst liegen lassen
- `main` ist **1 Commit vor** `origin/main` (nicht gepusht)

**Regeln daraus:** kein `git add -A`, kein `git commit -a`. Stattdessen
`git add <Pfad>` und `git commit --only <Pfad>`. Vor jedem Commit
`git log --oneline -3` lesen. Der Hook in `.githooks` fährt `pytest` und bricht
rote Commits ab.

---

## 6. Belegpfade (zum Nachsehen)

| Was | Pfad |
|---|---|
| 403-Belegstelle | `~/foto_sortierung/n6b_probe_2022-09-05.log` |
| Massenlauf-Themen | `~/foto_sortierung/n6b_rest_massenlauf.log` |
| Bögen je Jahr | `~/foto_sortierung/boegen/<jahr>/*.jpg` + `.json` |
| Themen-Katalog | `~/foto_sortierung/themen.jsonl` (2134 Zeilen, 48 Themen) |
| Kategorien / Ordner | `~/foto_sortierung/kategorien.json` |
| Handy-Manifest (ADB) | `~/foto_sortierung/manifest_handy.jsonl` |
| Handy-Manifest (pCloud) | `~/foto_sortierung/uebergabe_manifest.jsonl` |
| Vorbild in-memory-Bauweise | `tools/foto_sortierung/gesicht_erkennen.py` |
| Löschmail OpenRouter | `C:\Users\sebas\Desktop\OpenRouter-Loeschantrag.md` |

---

## 7. Nächster Schritt, in dieser Reihenfolge

1. Prüfbefehl frisch laufen lassen — Basislinie vor jeder Änderung. Dauert rund
   1 ¾ Stunden und läuft über `tor.py` (Sperre), nicht direkt über pytest.
   Gemessener Stand 28.10.2026: 6018 passed, 3 skipped, Exit 0.
2. Entscheidungen einsammeln: Schwelle für den Marker „Privat", Umfang des
   Rücklaufs, Zustimmung zur Messung an 100 Kacheln.
3. Messung der Stichprobe, Zahlen berichten, danach über den Umfang entscheiden.
4. Filter bauen (in-memory, kein Schreiben ins Repo, Trefferliste außerhalb),
   Tests dazu, Doku, ein Commit.
5. Löschantrag an OpenRouter senden und die Bestätigung ablegen.
6. Übersichtsdatei aufs Handy bringen (pCloud-Weg bevorzugt).
