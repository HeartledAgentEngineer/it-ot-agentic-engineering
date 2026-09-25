# Changelog 2026-09-25 — Archiv/Wissensspeicher verdrahtet

Der Wissensspeicher war gebaut, aber **nicht angeschlossen**: der Router hing nicht in
der App, der Bewusstseins-Baustein stand in keinem Prompt, `backend/.env` fehlte (kein
Einbettungs-Schlüssel → nur Volltext), und `archiv_index_path` war kein echtes Setting.
Dieser Schritt schließt genau diese vier Punkte. Grundlage: `docs/konzept-wissensspeicher.md`
(§6.1, §7, §9) und Sebastians Befund „Er weiß, er hat eine Wissensdatenbank — er müsste
es wissen."

**Prüfbefehl:** `cd backend && .venv/Scripts/python -m pytest tests/ -q`
**Ergebnis:** **358 passed** (vorher 333 + **25 neue** in `tests/test_archiv_verdrahtung.py`),
Exit-Code 0, Laufzeit 129 s. Kein Test wurde abgeschwächt oder entfernt.

---

## 1) Router eingehängt (Datei:Zeile)

| Was | Datei:Zeile |
|---|---|
| Import ergänzt | `backend/app/main.py:26` (`archiv_wissen,` in der Router-Importliste) |
| Registrierung | `backend/app/main.py:175` — `app.include_router(archiv_wissen.router, dependencies=[Depends(auth.require_api_key)])`, direkt neben `archiv.router` (Zeile 174), gleiches Muster: eigener `/api`-Prefix, API-Key-Schutz, danach der Frontend-Mount als letzter Eintrag |

**Zwei Archiv-Router nebeneinander — und warum sie sich nicht überschneiden:**

| Router | Prefix | Routen |
|---|---|---|
| `app/router/archiv.py` (alt) | `/api/archiv` | `GET /api/archiv/status`, `GET /api/archiv/suche` |
| `app/router/archiv_wissen.py` (neu) | `/api/archiv/wissen` | `GET …/statistik`, `…/chronik`, `…/frage`, `…/original`, `…/ueberblick` |

Der neue Prefix liegt **unter** dem alten, die Pfadmengen sind aber **disjunkt**
(`/api/archiv/status|suche` gegen `/api/archiv/wissen/…`). Keiner der beiden Router
benutzt Pfad-Platzhalter (`{…}`), es kann also keine Route eine andere verdecken — auch
nicht bei Starlettes Matching in Registrierungsreihenfolge. Der Frontend-Mount (`/`)
kommt weiterhin zuletzt und kann deshalb keine API-Route schlucken. Genau das prüfen
`test_beide_archiv_router_sind_eingehaengt`, `test_archiv_router_ueberschneiden_sich_nicht`
und `test_api_routen_stehen_vor_dem_frontend_mount` (Route für Route, `(Pfad, Methode)`
doppelt gibt es nicht).

**Antwortet wirklich:** `test_router_antwortet_ueber_echtes_http` schickt echtes HTTP
(`TestClient(app)`, echte App, winziger Testindex) gegen `/api/archiv/wissen/statistik`
und `/api/archiv/wissen/chronik` → HTTP 200; der **alte** Router antwortet im selben Lauf
weiter (`/api/archiv/status` → 200). `test_router_antwortet_auch_mit_echtem_dienst` macht
dasselbe **ohne** Attrappe, also gegen die echten Einstellungen — auf dem PC kommt
HTTP 200 mit Zahlen, ohne Index käme ehrlich `verfuegbar: false`; beides ist kein Absturz.

---

## 2) Bewusstseins-Baustein im Prompt (Datei:Zeile)

| Was | Datei:Zeile |
|---|---|
| Baustein wird gebaut (neu) | `backend/app/services/llm_service.py:537` `_build_wissensspeicher_baustein()` |
| Eingehängt in **jedem** Prompt | `backend/app/services/llm_service.py:596` in `_build_messages`, **direkt nach** der Fokus-Anweisung (Z. 594) — wie in §6.1 der Konzeptdatei festgelegt |
| Not-Baustein bei Fehler | `backend/app/services/llm_service.py:118` `WISSENSSPEICHER_AUSFALL` (kein stilles Weglassen) |
| Textquelle (kompakt, neu) | `backend/app/services/archiv_suche.py:1133` `ArchivSuche.ueberblick_kurz()` |
| Öffentliche Funktion | `backend/app/services/archiv_suche.py:1304` `prompt_baustein(kurz=True)` |

**Der Baustein steht AUCH OHNE Suchtreffer.** Vorher hing am Prompt nur
`_build_archiv_context` (Zeile 529) — das ist die **Treffer**-Injektion und liefert ohne
Suchtreffer einen leeren String. Der neue Baustein ist davon unabhängig und steht in
jedem Aufruf. Reihenfolge im System-Prompt (keine Doppelung, jede Sache kommt einmal):

1. Fähigkeiten + System-Prompt (`load_system_prompt`)
2. Fokus-Anweisung (`KONTEXT_FOKUS_ANWEISUNG`)
3. **Wissensspeicher-Baustein** (Bewusstsein: Zahlen, Quellen, Zeitraum, Nutzungsregel)
4. Zusammenfassung älterer Unterhaltung (falls vorhanden)
5. Gedächtnis-Erinnerungen (`_build_memory_context`)
6. **Archiv-Fundstellen zur aktuellen Frage** (`_build_archiv_context`)

Punkt 3 sagt *dass* es das Archiv gibt, Punkt 6 zeigt *was* darin steht — beides
wiederholt sich nicht: der Baustein trägt ausschließlich Metadaten, die Treffer-
Injektion ausschließlich Fundstellen. Abgesichert durch
`test_baustein_steht_genau_einmal_im_prompt` (Zählung `WISSENSSPEICHER` == 1, mit **und**
ohne Treffer) und `test_baustein_und_treffer_haben_klare_reihenfolge` (Baustein steht
**vor** dem Treffer-Block „AUS DEINEN FRÜHEREN GESPRÄCHEN"; die Fundstelle selbst steht
genau einmal im Prompt).

### Wortlaut (gemessen am echten Index, 25.09.2026)

Mit Schlüssel — **506 Zeichen**:

> WISSENSSPEICHER (persönliches Chat-Archiv): 1109 Gespräche, 40627 Nachrichten,
> Zeitraum 1940-09-04 bis 2026-12-28. Quellen: chatgpt (109), claude-code (40),
> gemini (384), claude-ai (162), google-kalender (399), google-notizen (15).
> NUTZUNG: Fragen zu meiner Vergangenheit/meinen Chats ZUERST hier suchen (Hybridsuche:
> Stichwort + Bedeutung) und den Treffer über seinen Zeiger als Original nachlesen —
> NICHT im Web, das weiß nichts davon. Bei unsicher (sicher=false) Rückfrage an Sebastian
> statt Behauptung.

Ohne Einbettungs-Schlüssel — **558 Zeichen**, zusätzlich am Ende:

> Bedeutungssuche aus: kein Schlüssel — nur Wortlaut.

Beide Fassungen liegen unter der Zielgrenze **600 Zeichen** (Test
`test_baustein_ist_kurz` prüft beide). Der Baustein enthält **keine Archivinhalte**:
keine Titel, keine Zitate, keine Kennungen — nur Zahlen, Quellen, Zeitraum und die
Nutzungsregel (`test_baustein_enthaelt_keine_archivinhalte` prüft das gegen Marker, die
absichtlich im Testtext stehen). Die Quellenliste ist auf 8 Einträge begrenzt
(„+N weitere"), damit der Baustein bei wachsendem Bestand nicht aus dem Rahmen läuft.
Der Baustein fasst die Vektormatrix **nicht** an (auf dem Handy 95 MB) — er prüft nur,
ob ein Schlüssel vorhanden ist.

Der System-Prompt (`backend/system_prompt.md`, öffentliche Datei) blieb unverändert; er
sagte schon vorher, dass Zugriff auf frühere Gespräche besteht. Neu steht die **Umfangs-
Zahl** tatsächlich im Prompt — die dortige Bedingung „…und stehen die Zahlen nicht im
Kontext…" greift damit nicht mehr, statt zu widersprechen.

---

## 3) Schlüssel und Umgebung — ehrlich gelöst (ohne Werte)

**Befund (nur Variablennamen geprüft, niemals Werte):**

| Datei | Variablenname vorhanden? |
|---|---|
| `…/workspace agentic engineering/.env` (Workspace-Wurzel) | `OPENROUTER_API_KEY` — **ja** |
| `…/personal_ai_agent/backend/.env` | Datei existiert **nicht** |
| `…/personal_ai_agent/backend/.env.example` | dokumentiert u. a. `OPENROUTER_API_KEY`, `ARCHIV_DB_PATH`, `ARCHIV_VEKTOR_PATH`, `MISTRAL_API_KEY`, `ARCHIV_TOP_K` |

**Fallback (neu, dokumentiert im Code):** `backend/app/config.py`

* `config.py:36-38` — `WORKSPACE_DIR` (= zwei Ebenen über dem Projektordner),
  `WORKSPACE_ENV_FILE`, `SCHLUESSEL_FALLBACK_VARIABLE = "OPENROUTER_API_KEY"`.
* `config.py:41` — `variable_aus_env_datei(pfad, name)`: eigener, kleiner Leser, der eine
  `.env`-Datei **nur nach einem einzigen Variablennamen** durchsieht (`export …` und
  Anführungszeichen werden verstanden). Bewusst **nicht** pydantic-settings: Wäre die
  fremde Datei als ganze Konfiguration eingebunden, könnte ein Nachbarprojekt diese App
  still umstellen (`HOST`, `PORT`, …).
* `config.py:292` — `@model_validator(mode="after")`: ist `openrouter_api_key` leer,
  wird **genau dieser eine Name** aus der Workspace-Wurzel-`.env` nachgetragen. Loggt nur
  *dass* der Name übernommen wurde bzw. *dass* er fehlt — **nie einen Wert**. Kein Wert
  steht in Code, Doku, Log oder Test.

**Nachweis ohne Wertausgabe** (`env -u OPENROUTER_API_KEY`, damit die Umgebungsvariable
nicht mitzählt — sonst wäre der Beweis nichts wert, siehe „Offene Punkte"):

```
os.environ hat OPENROUTER_API_KEY: False
Name steht in der Workspace-Wurzel-.env: True
settings.openrouter_api_key gesetzt: True
```

**Ehrliche Degradation (kein stiller Ausfall):** Ohne Schlüssel bleibt die Volltextsuche
nutzbar und der Hinweis ist sichtbar. Live gegen den echten Index (Schlüssel im Prozess
geleert; ausgegeben werden nur Zähler und Status, keine Inhalte):

```
wege: {'volltext': True, 'vektor': False, 'vektor_status': 'kein_schluessel'}
anzahl Treffer: 3
sicher/grund: True eindeutig
hinweis vorhanden: True
Brick-Laenge: 558
Brick nennt Degradation: True
```

Zusätzlich im Endpunkt-Ergebnis: `hinweis = "Kein Einbettungs-Schlüssel gesetzt
(OPENROUTER_API_KEY) — gesucht wurde nur nach Wortlaut. Sinngemäße Formulierungen können
fehlen."` (bereits vorhanden in `archiv_suche.VEKTOR_HINWEIS`), und im Prompt-Baustein
der Satz „Bedeutungssuche aus: kein Schlüssel — nur Wortlaut."

**`archiv_index_path` ist jetzt ein echtes Setting:** `backend/app/config.py:191`, Standard
= der vorhandene Archivpfad
`<Workspace-Wurzel>/Chats von GPT, GEMINI, Claude/db/archiv_index.db`.
Suchreihenfolge (erster **tatsächlich vorhandener** Kandidat gewinnt), dokumentiert in
`config.py` (Z. 173-185), in `archiv_suche._pfad_kandidaten` (Z. 291) und in
`backend/.env.example`:

1. `settings.archiv_index_path` (per `.env`: `ARCHIV_INDEX_PATH`)
2. Umgebungsvariable `ARCHIV_INDEX_PATH`
3. `personal_ai_agent/archiv_index.db`
4. `personal_ai_agent/backend/archiv_index.db`
5. `<Workspace-Wurzel>/Chats von GPT, GEMINI, Claude/db/archiv_index.db`
6. `/sdcard/Download/archiv_index.db` (Handy)
7. `/data/data/com.termux/files/home/archiv_index.db` (Handy, Termux-Heim)

Ein gesetzter, aber nicht vorhandener Pfad fällt ehrlich durch auf den nächsten Kandidaten
(`test_falscher_pfad_faellt_durch_statt_zu_crashen` prüft die Reihenfolge); ist keiner da,
meldet die Suche `grund: "kein_index"` mit Rückfrage statt zu crashen
(`test_gar_kein_index_degradiert_ehrlich`).

---

## 4) Index aufs Handy (USB) — ausgeführt und belegt

```
adb -s ZY22K9RGLQ push "Chats von GPT, GEMINI, Claude/db/archiv_index.db" /sdcard/Download/archiv_index.db
→ Chats von GPT, GEMINI, Claude/db/archiv_index.db: 1 file pushed, 0 skipped.
  47.2 MB/s (251412480 bytes in 5.079s)
```

**Größe auf dem Gerät** (`adb shell ls -l`):

```
-rw-rw---- 1 u0_a323 media_rw 251412480 2026-09-25 11:41 /sdcard/Download/archiv_index.db
```

Byte-Zahl identisch zur Quelle (251412480 = 239,8 MiB) und **MD5 auf beiden Seiten gleich**
(`9b29c3706503f42622faa926fbae482e`) — die Datei ist unbeschädigt angekommen.

**Nächster Schritt auf dem Handy (Termux) — genau ein Befehl:**

```bash
mv /sdcard/Download/archiv_index.db /data/data/com.termux/files/home/archiv_index.db
```

Danach liegt die Datei **nicht mehr in `Download`** (geteilter Ordner, den jede App mit
Speicherzugriff lesen könnte) und die App liest sie ohne Android-Speicherrechte. Der
Termux-Heimordner ist Kandidat 7 der Suchreihenfolge — es ist **keine** `ARCHIV_INDEX_PATH`
Zeile nötig. Wer den Pfad festnageln will:
`ARCHIV_INDEX_PATH=/data/data/com.termux/files/home/archiv_index.db` in `backend/.env`.

---

## 5) Tests (echte Ausgaben)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
........................................................................ [100%]
358 passed, 3 warnings in 129.13s (0:02:09)
EXIT=0
```

Neu: `backend/tests/test_archiv_verdrahtung.py` — **25 Tests**, alle grün
(`.venv/Scripts/python -m pytest tests/test_archiv_verdrahtung.py -q` → `25 passed`, Exit 0).
Sie decken ab: (a) Router eingehängt + antwortet + keine Überschneidung, (b) Baustein ohne
Suchtreffer im Prompt, (c) ≤ 600 Zeichen und nur Metadaten, (d) ohne Schlüssel Volltext +
sichtbarer Hinweis, (e) `archiv_index_path` (Setting, Env-Variable, falscher Pfad, gar kein
Index), (f) genau eine Injektion — plus die Schlüssel-Fallback-Regeln (nur ein
Variablenname; fremde Variablen wirken nicht; `export`/Anführungszeichen). Die Tests fassen
das **echte** Archiv nie an: jeder baut sich im `tmp_path` einen winzigen Index aus
künstlichen Gesprächen, die Einbettung ist eine Attrappe (kein Netz, kein Schlüssel,
keine Kosten).

---

## 6) Offene Punkte

1. **`OPENROUTER_API_KEY` liegt in dieser Shell-Sitzung als Umgebungsvariable** (auf dem
   PC). Das ist gut für den Betrieb — aber es macht den Fallback *unsichtbar*: Wer nur
   `settings.openrouter_api_key` prüft, sieht „Schlüssel da" und kann nicht sagen, ob er
   aus der Umgebung oder aus der Workspace-Wurzel-`.env` kommt. Der Nachweis oben wurde
   deshalb mit `env -u OPENROUTER_API_KEY` gefahren. Auf dem **Handy** gibt es diese
   Umgebungsvariable nicht — dort greift der `.env`-Weg.
2. **Zwei Archiv-Systeme nebeneinander** (bewusst, nicht aufgeräumt): `archiv.py` +
   `archiv_service.py` lesen die **alte** `memory.db` (Mistral, 1024 Dimensionen);
   `archiv_wissen.py` + `archiv_suche.py` lesen den **neuen** `archiv_index.db` (OpenRouter,
   1536 Dimensionen). Die alte Vektordatei `db/memory.vektoren.f32` ist damit unbrauchbar;
   sie wurde **nicht** gelöscht (Sebastian: keine echten Daten löschen). Der Chat nutzt
   weiterhin den alten Weg (`router/chat.py` → `archiv_service`); wer den neuen Weg im
   Chat als **aktive Suche** will, muss `chat.py` umstellen — das ist ein eigener,
   Sebastians Entscheidung nachgelagerter Schritt.
3. **WhatsApp ist nicht im Bestand.** Im Archivordner liegen unter `raw/whatsapp/`
   tatsächlich **2 rohe Exportdateien** (Chattexte), der Index kennt aber **keine**
   WhatsApp-Quelle — er hat genau sechs Quellen (chatgpt, claude-ai, claude-code, gemini,
   google-kalender, google-notizen). Entscheidung Sebastians: nur dokumentieren, nicht
   aufnehmen; der Indexbau könnte es später ergänzen, sobald der Bestand es enthält.
   (Dateinamen werden hier bewusst nicht genannt.)
4. **Google-Fotos** (Takeout) sind bewusst nicht Teil des Textindex (unverändert).
5. **Alte Themenliste im langen Baustein** (`ueberblick()`, 911 Zeichen) bleibt bestehen —
   sie wird weiterhin vom Endpunkt `/api/archiv/wissen/ueberblick` geliefert; im Prompt
   steht ausschließlich die kompakte Fassung.

---

## Datenschutz dieses Schritts

* Archivdateien ausschließlich **lesend** geöffnet; nichts geändert, nichts gelöscht.
* In Doku, Tests und Ausgaben stehen nur **Zahlen, Quellen, Zeitraum und Strukturen** —
  keine Gesprächsinhalte, keine Zitate, keine Namen Dritter.
* **Keine Schlüsselwerte** gelesen, ausgegeben, gespeichert oder dokumentiert — aus der
  fremden `.env` wird genau ein Variablenname ausgewertet und nur weitergereicht.
* Tests benutzen künstliche Gespräche im `tmp_path`; das echte Archiv wird von keinem
  Test geöffnet.
