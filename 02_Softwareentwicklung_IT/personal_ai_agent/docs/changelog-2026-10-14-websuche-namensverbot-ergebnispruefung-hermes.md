# 14.10.2026 – Ergebnisprüfung Hermes: Websuche mit Namensverbot (`726ca00`, `a6f7020`, Stand `d8286fb`)

**Rolle:** Hermes als zweiter Prüfer (AGENTS.md, Rollentabelle). Vorlage
`.hermes/plans/2026-10-14_websuche-namensverbot-ergebnis.md`, Prüfgegenstand Plan
`.hermes/plans/2026-10-14_websuche-namensverbot.md` **Fassung 7**.
Runde 1 (Codex, 16:39) war **EINWAND** (kaputter alter Katalog, beschädigte Kontaktfelder);
`a6f7020` behebt beides. Diese Runde prüft, ob die Behebung vollständig ist und ob noch eine
Namensquelle still leer werden kann (Prüffrage 4 der Vorlage).
**Der Stand hat sich während dieser Prüfung bewegt** (Codex-Runde 2 → `d8286fb`, siehe
Abschnitt „Mitlauf“); die Befunde sind zusätzlich auf dem neuen Stand nachgemessen.

**Urteil: EINWAND** – keine Freigabe. 2 mittlere Befunde, 2 Hinweise.

## Antworten auf die sechs Prüffragen (jeweils mit Beleg)

1. **Kann irgendein Weg noch ein Such-Plugin oder `openrouter:web_search` im Hauptaufruf
   setzen? – Nein.** `llm_service._extra_body` (`:483–517`) liefert nur `provider`
   (`allow_fallbacks`, optional `data_collection`) — die `web_search`-Übergabe ist dort bewusst
   unbenutzt. `_extra_body` wird an genau drei Stellen aufgerufen (`:841` Rückfall ohne
   Werkzeuge, `:901` Werkzeug-Schleife, `:952` `chat()`), keine davon setzt ein Suchwerkzeug.
   Im ganzen Backend setzt **nur** `web_suche.py:78` `plugins: [{id: web}]`; ein zweiter
   LLM-Aufruf mit Plugin existiert nicht (gemessen per Suche über `app/`, `scripts/`, `tools/`).
   Der DSML-Rückfall läuft in denselben Rückfall (`werkzeug_schleife.py:172` → `chat_stream`),
   also ohne Plugin.
2. **Bekommt der Suchaufruf Kontext außer dem Suchtext? – Nein.** `web_suche.py:71–80`:
   `messages=[{"role":"user","content": anfrage}]`, ein Modell, `temperature`, `max_tokens`,
   `extra_body` = `provider` + `plugins`. Weitere Felder gibt es nicht (gemessen: Schlüssel
   `['extra_body','max_tokens','messages','model','temperature']`). **Aber** siehe Befund 1:
   Länge und Inhalt des Suchtextes sind unbegrenzt.
3. **Kommen Freigaben nur aus `request.message`? – Ja.** `web_suche.suchen` wird nur an zwei
   Stellen gerufen: `chat.py:1766` (`_websuche_vorab`, beide Wege `/chat` und `/stream`) und
   `llm_service.py:895` — dort ausschließlich aus dem von `chat.py:2176` durchgereichten
   `nutzer_nachricht=request.message`. Ohne Übergabe bleibt der Wert `""`, also **keine**
   Freigabe. Modelltext kann keine Freigabe erzeugen: gemessen, dass
   `freigaben("Was macht Ida Beispiel?", bestand) == []` und ein vom Modell formulierter
   „Such im Internet nach …“-Text die Sperre nicht öffnet (eigene Sonde, testgleich).
4. **Sperrt eine unlesbare Namensliste? – Ja, vollständig; aber der leere Fall bleibt.**
   Eigene Sonde gegen die echten Funktionen, acht Fälle, alle sperren:
   kaputter Katalog, Katalog in falscher Form (`{"personen": "Ida Beispiel"}`),
   `telefonbuch_namen` als Text, `teilnehmer` als Objekt, `whatsapp_name` als Zahl,
   Chat-Eintrag kein Objekt, `chats` keine Liste, Kontaktdatei kaputt → jeweils `None` →
   `ABGELEHNT_LISTE`, kein Netz. **Codex R1/1 und R1/2 sind damit erledigt.** Auf dem Stand
   `d8286fb` zusätzlich nachgemessen: beschädigter Eintrag in `personen_bestaetigt.json`,
   `bestaetigt` als Liste, Katalog-Eintrag als Text → dreimal `None` (Sperre).
   **Nicht behoben ist der leere, aber lesbare Bestand** (Befund 2).
5. **Decken die Tests die Testliste aus Fassung 7 ab? – Ja, mit einer Ausnahme.** Alle Punkte der Testliste haben Gegenstücke, inklusive der „vom Modell
   erfundenen Freigabe“ (`test_auto_freigabe_nur_aus_der_nutzernachricht`), des Hauptaufrufs
   (`test_hauptaufruf_sucht_nie_selbst`), der Rückfälle (`test_llm_rueckfall_nur_ohne_vorherigen_text`,
   DSML-Gruppe) und der Endungen (`test_bekannte_namen_sperren`). Gemessene Zahl der
   gesammelten Tests: **74 auf dem Stand `a6f7020`** (16:50), **87 auf dem Stand `d8286fb`**
   (17:12). Die Ausnahme ist der interessante Fall: der leere Bestand ist als
   **gewollt** festgehalten (`test_streng_ohne_quiz_und_ohne_katalog_ist_leer_aber_lesbar`) —
   genau dieser Fall ist auf dem Handy denkbar und dann nicht sichtbar (Befund 2).
6. **Stimmt die Doku mit dem Code? – Weitgehend ja, drei Stellen nicht** (Hinweis 4):
   der Changelog beschreibt die strenge Kontaktprüfung korrekt
   (Feldtypen, „11 neue Tests“), der `spec-tool-use-v1.md`-Abschnitt
   „Websuche mit Namensverbot“ passt zum Code (kein Hauptaufruf-Plugin, ein Weg ins Netz,
   Freigabe nur aus der eigenen Nachricht, Grenzen). Nicht mehr stimmig sind drei Stellen
   (siehe Hinweis 4).

## Befunde

### Befund 1 (mittel) – Der Suchtext hat keine Obergrenze; „kontextfrei“ gilt nur für das Backend
`web_suche.suchen` prüft den Text nur auf Namen und schickt ihn **unverändert und unbegrenzt**
weiter (`web_suche.py:55–57`); `MAX_ZEICHEN = 4000` (`:29`, `:87–88`) kürzt lediglich die
**Antwort**, nicht die Anfrage. Der Suchtext wird aber vom **Modell** gebildet, und das Modell
hat Erinnerungen, Archiv-Fundstellen und Verlauf gesehen. Es kann seinen gesamten Vorrat in
`anfrage` legen; geprüft wird davon nur, ob ein **gelisteter Name** darin steht.
**Messung (eigene Sonde, Attrappe statt Netz):** 3.480 Zeichen persönlicher Fließtext
(„Mein Bruder … meine Schwester …“) ergaben einen Suchaufruf mit 3.479 Zeichen in **einer**
Nachricht — also vollständig durchgereicht (die 1 Zeichen Differenz ist das `strip()`);
derselbe Text mit angehängtem bekanntem Namen wurde abgelehnt (die Sperre greift, aber erst
bei Namen). `web_suche.py` ist seit `726ca00` unverändert, der Befund gilt also auch auf
`d8286fb`.
Das steht in Spannung zur Absicht des Plans („Der Suchaufruf sieht keinen Kontext“), nicht
zu seinem Wortlaut — deshalb mittel und nicht hoch.
**Auflage:** eine Obergrenze für die Anfrage (Ablehnung oder klarer Hinweis) und ein Satz im
Werkzeugtext, dass die Anfrage kurz und ohne persönliche Details sein soll; dazu ein Test.

### Befund 2 (mittel) – Ein leerer, aber lesbarer Bestand ist von „nichts zu schützen“ nicht zu unterscheiden
`bekannte_namen_streng()` (`werkzeuge.py:552–573`) baut den Bestand aus den Personenquellen
und `_kontakt_namen()`; `_kontakt_namen()` liefert bei fehlender Datei still `[]`
(`werkzeuge.py:441–443`, dort selbst als gewollt kommentiert). Sind **alle** Quellen leer
(keine `personen_bestaetigt.json`, keine `personen_vorgaben.json`, keine
`personen_profile.json`, kein `gesichter_katalog.json`, keine `whatsapp_zuordnung.json`),
entsteht ein gültiger Bestand mit
**0 Teilen und 0 vollen Namen**; `websuche_schutz.enthaelt_namen` sperrt nur bei `None`
(`websuche_schutz.py:126`), also läuft **jede** Suche durch — ohne Logzeile, ohne Statuszeile,
ohne Messwert. Gemessen (eigene Sonde mit Wegwerf-Quellen, Stand `d8286fb`): alle Quellen
fehlen → `{'teile': 0, 'volle': 0}` und „Was macht Ida Beispiel?“ wird gesucht (auf dem Stand
`a6f7020` ebenso gemessen).
Der von Codex in Runde 2 gefundene Weg in diesen Zustand (beschädigte Einträge wurden still
aussortiert) ist seit `d8286fb` geschlossen — der Zustand selbst bleibt.
Warum das die **Handy-Lage treffen kann** (gemessen, nur Zahlen/Dateinamen):
- `gesichter_katalog.json` liegt laut `.gitignore:32` **nicht** im Repo (PC: `BASE_DIR`,
  `gesichter_service.py:33`) — das Handy kann ihn also nicht per Pull haben.
- Die Übergabeprotokolle des Handys (`/sdcard/Download/hermes_diag/uebergabe_letzte.txt`,
  `pcloud_uebernahme.log`) nennen `whatsapp_zuordnung.json` und `personen_bestaetigt.json`
  **0-mal** — über den bekannten Kabel-/pCloud-Weg sind sie nie angekommen.
- `personen_bestaetigt.json` wird über den Schreibpfad gelesen (`werkzeuge.py:502–512`,
  vorher `gruppen_quiz.py:179`), nicht über `_lesepfad` — die `personen_gruppen/`-Ebene, über
  die `personen_beispiele.json` ans Handy geht, hilft ihr nicht.
Das ist **kein bewiesener Ausfall** (ob das Handy die Dateien aus seiner Termux-Sicherung
hat, konnte ich nicht messen, siehe Hinweis 3), aber ein belegbar möglicher Zustand, in dem
die Zusage „Personennamen gelangen nie in eine Internetsuche“ still außer Kraft ist.
**Auflage:** den leeren Bestand sichtbar machen (Logzeile und Zähler, dazu ein Feld in der
T0-Statuszeile von `import_status`), damit „kein Bestand vorhanden“ von „es gibt nichts zu
benennen“ unterscheidbar ist; dazu ein Test. Der gewollte Satz „eine tatsächlich leere Liste ergibt
keinen Treffer“ bleibt inhaltlich richtig — er darf nur nicht stumm gelten.

### Hinweis 3 – Die vom Prüfkriterium geforderte Handymessung war in diesem Lauf nicht lesend zu bekommen
Das Prüfkriterium der Fassung 7 verlangt die Messung von `bekannte_namen_streng()` **am PC und
am Handy**, nur Zahlen. PC: erledigt (unten). Handy: nicht erhalten —
`adb shell` läuft als `shell`-Benutzer mit `HOME=/` und sieht das Termux-Heim nicht;
die Backend-API antwortet auf `GET /api/gruppen/stand` mit
„Zugriff verweigert: gültiger X-API-Key erforderlich“ (der Schlüssel steht in der Handy-`.env`,
die ich nicht öffne); ein Code-Lauf im Termux wäre ein Geräteeingriff und ist in diesem Lauf
ausgeschlossen. Lesend geprüft wurde nur, dass der Dienst läuft (`GET /health` → `ok`,
über `adb forward`). Die Handymessung bleibt offen und ist die Auflage zu Befund 2.

### Hinweis 4 – Drei Doku-Stellen hinken nach
1. `CLAUDE.md:125` nennt „`test_websuche_schutz.py` neu (63)“ — gemessen sind **87** gesammelte
   Tests auf `d8286fb` (74 auf `a6f7020`).
2. Dieselbe Zeile führt „**Offen:** Ergebnisprüfung Codex“ — Codex R1 und R2 sind gelaufen; R1
   ist in `a6f7020`, R2 in `d8286fb` behoben und im Changelog als Nachtrag dokumentiert.
   Offen bleibt nur die Handymessung (Hinweis 3).
3. `docs/changelog-2026-10-14-websuche-namensverbot.md:70` nennt als Behebung
   „`werkzeuge._katalog_personen_streng()`“ — diese Funktion gibt es seit `d8286fb` nicht mehr
   (gemessen: 0 Treffer im Code); sie wurde durch `_personen_namen_streng` ersetzt
   (`werkzeuge.py:502`). Der Absatz beschreibt damit einen Stand, den der Code nicht mehr hat.

## Mitlauf: der Stand hat sich während der Prüfung bewegt (ehrlich)

- Beim Start dieser Runde war der Kopf `a6f7020`; während der Messungen erschien
  **`d8286fb` „fix(datenschutz): Namensquellen fuer das Namensverbot direkt und streng lesen“**
  (16:56) — die Antwort auf eine **Codex-Ergebnisprüfung Runde 2**: Quiz-Übersicht und alter
  Katalog sortierten beschädigte Einträge still aus, Ergebnis „leerer Bestand, Suche offen“.
- **Folge für die Messung:** Mein erster voller Prüflauf (16:47–16:57) lief **in das
  Schreibfenster des Masters** hinein (Testdatei geändert 16:55) und meldete
  „3 failed, 4220 passed“; die drei Fehler betrafen genau die Namensquellen-Tests, die in
  diesem Moment umgeschrieben wurden. Danach isoliert nachgefahren: **87 passed** für die
  Datei. Der verbindliche Lauf steht im Bericht und läuft auf `d8286fb`.
- Meine Befunde sind auf dem neuen Stand **erneut gemessen** worden (Sonde 1–7): Befund 1
  unverändert gültig (`web_suche.py` nicht angefasst), Befund 2 unverändert gültig, die drei
  Beschädigungsfälle sperren jetzt.

## Belege dieses Laufs

- **Eigene Sonde gegen die echten Funktionen** (`werkzeuge.bekannte_namen_streng`,
  `werkzeuge._kontakt_namen`, `werkzeuge._personen_namen_streng`,
  `websuche_schutz.bestand_bauen/enthaelt_namen/freigaben`, `web_suche.pruefen/suchen`) mit
  Wegwerf-Quellen (`GRUPPEN_QUIZ_BASIS` in ein leeres Verzeichnis, Katalogpfad umgebogen) und
  **nur erfundenen Namen**: 8 Sperrfälle, 3 Beschädigungsfälle auf dem neuen Stand,
  4 Leer-/Bestandsfälle, 4 Freigabefälle, Längenmessung mit LLM-Attrappe. **Kein Netzaufruf,
  kein Modellaufruf, kein Bild geöffnet, keine Kosten.**
- **PC-Messung der Namensliste (nur Zahlen, keine Namen):** auf `a6f7020` Quiz mit **7**
  benannten Personen, Katalog vorhanden, Kontaktdatei vorhanden (**7.357** rohe Namenseinträge)
  → **8 Namensteile / 337 volle Namen / 1 Nachname**. Auf `d8286fb` (Quellen direkt, mit
  Profilnamen) → **10 Namensteile / 338 volle Namen / 2 Nachnamen**. Die Erwartung des Plans
  („Bestand > 0 und Kontakte > 0“) ist in beiden Ständen **erfüllt**.
- **Handy (nur lesend):** `adb devices` zeigt ein Gerät; `GET /health` nach `adb forward` → `ok`;
  Übergabeprotokolle auf Dateinamen geprüft (0 Treffer für die zwei Personendateien). Keine
  Schreibzugriffe, keine Installation, kein Neustart, nichts gelöscht.
- **Prüfbefehl:** voller Lauf `cd backend && .venv/Scripts/python -m pytest tests/ -q` auf `d8286fb`
  (17:2x, frisch und vollständig): **4236 passed, 2 skipped, 3 warnings, 493,13 s, kein Fehler**.
  Der erste Lauf derselben Runde (16:5x) lief in das Schreibfenster des Masters und meldete
  „3 failed, 4220 passed“ — siehe „Mitlauf“.
- **Gezielte Testmenge:** `tests/test_websuche_schutz.py` — 74 gesammelt auf `a6f7020`,
  **87 gesammelt auf `d8286fb`**.
- Prüfkreis-Eintrag (Runde 2, Hermes) und Prüfjournal der Vorlage nachgetragen (beide
  per `.gitignore` außerhalb des Commits).

## Grenzen dieses Laufs

Kein Bild geöffnet oder an ein fremdes Modell gesendet, kein Vision-Aufruf, keine
Modellkosten, kein Netzaufruf außer zwei lesenden Anfragen an den eigenen Dienst am Kabel
(`/health`, `/api/gruppen/stand` als Berechtigungsprobe), kein pCloud-Zugriff, nichts gelöscht,
keine Geräteeingriffe, keine `.env` geöffnet, keine persönlichen Dateiinhalte gelesen (nur
Zahlen und Dateinamen). Nur eigene Pfade committet (`git commit --only`, nie `git add -A`);
`status.json` nicht angefasst, fremde Änderungen im Arbeitsbaum nicht berührt.
