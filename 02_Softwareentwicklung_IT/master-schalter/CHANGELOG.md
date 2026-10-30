# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach
[SemVer](https://semver.org/lang/de/).

## [Unreleased]

### Behoben
- **Direktübergabe im Pop-up (`_uebergabe_direkt_starten`)**:
  * Aufruf korrigiert: `self._im_hintergrund(aktion)` statt des blockierten `_ausfuehren`, Rückgabetyp `um.Ergebnis` statt `AktionErgebnis` und Attribut `vorgang.id` statt `vorgang.vorgang_id`.

### Hinzugefügt
- **Windows Executables & Autostart (`pyproject.toml`, Autostart / `shell:startup`)**:
  * Eigenständige Windows-Executables unter `.venv/Scripts/`: `master-schalter-gui.exe` (Übersicht ohne Konsolenfenster), `master-leiste-gui.exe` (Taskleisten-Tray ohne Konsolenfenster), `master-schalter.exe`, `master-leiste.exe` und `masterwechsel.exe`.
  * Autostart-Verknüpfungen für Windows Login (`shell:startup`): `Master-Schalter.lnk` startet direkt die `master-schalter-gui.exe` und `Master-Schalter-Leiste.lnk` die `master-leiste-gui.exe`.
  * Entkoppeltes Skript `leiste_starten.cmd` auf Ausführung der `master-leiste-gui.exe` angepasst mit Prozess-Doppelstartschutz.
- **Dynamische Argon- & Gemini-Limit-Anzeige (`signale.py`, `uebersicht.py`)**:
  * Kontingentkarte liest den aktuellen Argon-Status dynamisch aus `gemini-kontingent.json` und zeigt `Argon: Limit (100 %)` bei verbrauchtem Kontingent bzw. `Argon: OK`.
  * Detailanzeige im Limit-Monitor unterscheidet präzise zwischen `Argon-Limit`, `Gemini 3.8 Flash (Master & Worker)` und `Gemini 2.5 Pro (Eingeschränkt / Ältere Generation)`.
- **Themen-Workflow & Master-Rotation konfigurierbar (`matrix_konfiguration.py`, `uebersicht.py`, `chat_discovery.py`)**:
  * Master-Rotationen (`Antigravity ➔ Hermes ➔ Codex`, `Integrative Maschine (Claude Opus 5.5 ➔ Argon ➔ Gemini 3.8 Flash)`, `Codex ➔ Antigravity ➔ Hermes`, `Hermes ➔ Antigravity ➔ Codex`, `Claude ➔ Codex ➔ Antigravity`, `Standard`) pro Thema frei einstell- und speicherbar (`mk.themen_einstellungen_schreiben`).
  * Neuer Konfigurationsbereich *Themen-Workflow & Master-Rotation* im Matrix-Dialog integriert: Beliebiges Thema auswählen, Rotation/Preset anpassen und mit einem Klick sichern.
  * *Neues Thema anlegen* belegt Prüfer, Ausführer und Master-Rotation automatisch gemäß dem gewählten oder erkannten Erst-Master vor und speichert die Konfiguration.
  * Chat-Erkennung (`chat_discovery.py`) um Claude-Code-Erkennung erweitert (`claude_chats_finden`): Prüft alle Institutionen (Antigravity, Codex, Claude) auf neue Chats, sofern sie nicht im Kontingent-Limit liegen.
- **Workflow- & Matrix-Profile mit Presets (`matrix_konfiguration.py`, `uebersicht.py`)**:
  * Vollständig konfigurierte Matrix mit Vorlagen:
    - `Standard (AGENTS.md)` (Kaskade Claude Opus -> GPT-6 Sol -> DeepSeek)
    - `Integrative Maschine (Claude Opus 5.5)` (Claude Opus 5.5 führt als Master, Gemini 3.8 Flash als Worker)
    - `Antigravity & Argon (Google AI)` (Argon als Master wenn verfügbar, Gemini 3.8 Flash als Worker)
    - `Gemini 3.8 Flash Fokus` (Gemini 3.8 Flash als Master und Worker)
    - `DeepSeek Notlauf (Budget)`
  * Tabellarische Zuordnung mit Dropdowns für jede Lage (Lage 1, 2A, 2B, 3) über alle 3 Rollen: Thinker (Master), Reviewer (Prüfer), Worker (Ausführer).
  * Antigravity-Rolle und bevorzugtes Modell frei konfigurierbar und persistent gespeichert.
- **Multi-Plattform Limit-Monitor & Detailanzeige (`limits_dialog_oeffnen`, `alle_limits_lesen`)**:
  * Neuer Button `📊 Limits & Verbräuche …` in der Kopfleiste.
  * Zeigt aufgeschlüsselte Kontingente, Rolling-Windows und Modellstatus aller 4 Plattformen:
    - Gemini / Antigravity: Argon-Limit (Agenten-Ausführung), Gemini 2.5 Pro (Thinker), Gemini 2.5 Flash (Worker), Flash Lite.
    - OpenAI ChatGPT Plus (Codex): 5h- und Wochenfenster, GPT-6 Sol / GPT-6 Luna.
    - Anthropic Claude Pro: 5h- und Wochenfenster, Claude Opus 5.5 / Claude Sonnet 5.5.
    - OpenRouter API: DeepSeek V4.1 Flash für Lagen 2A, 2B und 3.
- **Tabellen-Entstörung & Spaltenbereinigung (v0.5.0)**:
  * Gelbe Unterzeilen (`row.details`) vollständig aus der Tabelle entfernt: Jede Themenzeile ist ruhig und strikt einzeilig.
  * Spalte `Modell` aus der Tabelle entfernt: Tabelle ist übersichtlicher und bietet mehr Platz für die relevanten Spalten.
  * Veralteter oberer Sammelknopf `Übernehmen ...` entfernt (Steuerung erfolgt gezielt pro Thema via `Übergabe ...`).
  * Konkrete Anzeige in Dropdowns: `Prüfer` und `Ausführer` zeigen direkt das aufgelöste Modell (z. B. `Auto (Codex · App-Standard)`, `Workflow (Hermes · DeepSeek V4.1 Flash)`) statt nichtssagender Abstraktionen wie `Automatisch` oder `Workflow`.
- **Workflow- & Matrix-Konfigurator („Nach Kontingent“)** (`matrix_konfiguration.py`):
  * Neuer Button `⚙ Matrix & Workflow …` in der Kopfleiste.
  * Modaler Konfigurationsdialog zur Definition von „Nach Kontingent“ nach den 4 Nutzungslagen aus `AGENTS.md` (Lagen 1, 2A, 2B, 3).
  * Zuweisung von Thinker (Master), Reviewer (Prüfer), Worker (Ausführer) und Modellen sowie Gemini/Antigravity-Rolle.
  * Persistierung in `matrix-konfiguration.json` mit Fallback auf Standardwerte.
- **Automatische Chat-Erkennung für Themenneuanlage** (`chat_discovery.py`):
  * Durchsucht Antigravity (`conversation_summaries.db`), Claude und Codex nach neuen Chats.
  * Ignoriert Plattformen im Limit und filtert bereits registrierte Themen aus.
  * `+ Thema anlegen …` schlägt neu erkannte Chats automatisch vor und belegt Name und Erst-Master vor.
- **Erweiterte Kontingentanzeige**:
  * Anzeige von Argon-Status (`Argon: OK`) und Modell-Verfügbarkeiten in der Gemini/Antigravity-Karte.

- **Frontend-Redesign & Entrümpelung der Themenzeilen**:
  * Dropdowns im Dark-Theme mit hohem Kontrast (`Dunkel.TCombobox` mit dunklem Grund und weißer Schrift).
  * Zweizeiliger Detail-Fließtext unter jeder Zeile entfernt: Themenzeilen sind nun kompakt und einzeilig.
  * Farbenspiel modernisiert: Grelle Rostrot-Töne durch modernes Developer-Blau (`AKZENT_PRIMAR = "#3b82f6"`) ersetzt.
  * Veraltete Knöpfe unten (*Alle nach Kontingent*, *Alle wie vorher*, *Übergabe starten …*) und störende untere Boxen entfernt; die Tabelle nutzt nun die volle Fensterhöhe.
- **Direkte Übergabe pro Zeile & Pop-up-Dialog**:
  * Neue Spalte *Aktion*: Bei geändertem Master erscheint der Knopf *Übergabe …*.
  * Klick öffnet ein modales Pop-up mit den Optionen *„Jetzt aktuellen Master unterbrechen“* (Sofortübernahme) und *„In Warteschlange geben“* (`abgabe_modus="warten"`).
- **Gemini / Antigravity Kontingentanzeige**:
  * Dritte Karte für Gemini / Antigravity im Kontingentbereich (`signale.gemini_lesen`, `AKZENT_GEMINI = "#4285f4"`).
- **Neues Thema anlegen & Workflow-Vorgaben**:
  * Knopf *+ Thema anlegen …* in der Entwurfsleiste mit Dialog für automatische Workflow-Vorgaben und Master-Rotation.
- **Automatische Übergabe Codex → Antigravity bei Codex-Limit** (neu `agy_automatik.py`): erreicht Codex bei
  frischer Messung (≤ 10 min) im 5h- oder Wochenfenster die Schwelle und ist Claude nicht frei, gehen alle aktiven
  Paare, deren Besitzmarke `codex` trägt und deren Profil-Master `kontingent` oder `codex` ist, an `agy`. Fehlt in
  `zuordnung.json` ein bestätigtes `agy:<kennung>` für das Thema, legt `agy_senden.neues_gespraech` über
  `language_server.exe agentapi new-conversation --title="Thema: <thema>"` ein neues Antigravity-Gespräch an und
  bestätigt die Zuordnung. Danach wird `<thema>@codex:<reset>` in `automatik_ausgeloest.json` vermerkt (höchstens ein
  Versuch je Thema und Codex-Limitfenster; bei gescheiterter Chat-Anlage wird **nicht** vermerkt, der nächste Takt
  versucht es erneut) und `assistent.uebergeben(thema, "agy", von_chat=None, nach_chat=agy:<kennung>)` gestartet.
  Themen mit laufendem/blockierendem Wechselvorgang (`WECHSEL_BLOCKIEREND`) oder Modus-Zwischenmarke bleiben unberührt.
  Die Leiste ruft den Lauf im Automatiktakt nach `automatik.lauf()` auf (nur bei Hauptschalter an).
  Tests: `test_agy_automatik.py`.
- **Antigravity-Transport `agy_senden.py`**: `nachricht_senden` (`agentapi send-message`) weckt nach dem Einlegen der
  Übernahmenachricht ins Postfach zusätzlich das Ziel-Gespräch (`assistent._zustellen`, nur ohne Test-Transport; das
  Postfach bleibt der maßgebliche Weg, die Quittung erzwingt die Gültigkeit). Weil `leiste.py` außerhalb des
  Antigravity-Prozessbaums läuft, speichern `agy_hook` und `masterwechsel postfach agy …` die lokalen
  Verbindungsvariablen (`ANTIGRAVITY_LS_ADDRESS`, `ANTIGRAVITY_CSRF_TOKEN`, `ANTIGRAVITY_AGENTAPI_EXE`, …) in
  `agy-server.json` im Datenordner; sie werden nie ausgegeben oder protokolliert. Aufruf immer als Argumentliste
  ohne Shell (kein `agentapi.bat`).
- **Übersicht: „Übernehmen …“ ist angebunden** (`uebersicht_modell.entwurf_uebernehmen_aktion`,
  `uebersicht.Fenster.entwurf_uebernehmen`): aktiv nur bei offenen Entwürfen ohne Konflikt/Hinweis, schreibbarer
  Aufnahme und prüfbarem Wechselstatus; die Rückfrage listet jede Änderung, die Übernahme läuft im Hintergrund je
  Thema (`modi.master_setzen`, `pruefer_wahl.setzen`, `modi.worker_setzen`, `modi.modell_setzen`, `modi.vibe_setzen`,
  `paare.aktiv_setzen`); erfolgreich übernommene Themen verlieren ihren Entwurf, der Bericht nennt je Thema Erfolg
  oder Fehler.
- **Ausführer Antigravity in der Modellspalte**: `modell_liste` zeigt fest „Standard“ (gesperrt), der Entwurf lehnt
  eine Modellwahl mit „Antigravity verwendet den Standard des Werkzeugs“ ab.
- **Antigravity (agy) als vierte Themenrolle** (v0.6.0): `modi.MASTER_WERTE`, `WORKER_WERTE`, `ZIEL_ROLLEN`,
  `anzeige.MASTER_AUSWAHL`/`WORKER_AUSWAHL`, `kurz.MASTER_WERTE`, `chat_zuordnung.WERKZEUGE`, `postfach.ZIELE` und
  `status.WERKZEUGE` kennen `agy`; `besitz.AGY` ist die neue Besitzmarke. Zwei Stellen prüften den Besitz gegen
  eine feste Liste und wären sonst **rot** geworden: `modi._umschalten_gesperrt` (Übernahme bei Besitz `agy`) und
  `modi.geschuetzt`/`master_setzen_wenn`. Sammelbefehle (`alle kontingent`/`zurueck`) lassen wie bei Hermes auch
  eine Antigravity-Rolle stehen (`alle.GESCHUETZT`, Meldung `ausgelassen (Antigravity)`). Die Prüfer-Vorschau
  (`kurz.pruefer_text`) behandelt Antigravity als eigene Modellfamilie; Prüfer bleibt Codex.
  Tests: `test_modi.py`, `test_anzeige.py`, `test_leiste.py`, `test_uebersicht.py`, `test_alle.py`.
- **Chat-Register kennt Antigravity** (Quelle `agy`): liest `~/.gemini/<Ausprägung>/conversation_summaries.db`
  (`antigravity`, `antigravity-cli`, `antigravity-ide`), Tabelle `conversation_summaries`, ausschließlich die
  Spalten `conversation_id`, `title`, `last_modified_time`, `workspace_uris` (Reihenfolge, Arbeitsordner als
  Windows-Pfad aus `file://`-Adressen). Inhalts-Spalten werden nie angefasst (G9). Status wie bei den anderen
  Quellen: `ok`, `fehlt`, `schema unbekannt`, `nicht lesbar: <Klasse>`; eine unlesbare Ausprägung verdrängt eine
  lesbare nicht. Die Testumgebung (`conftest.py`) lenkt die Quelle automatisch auf Nichtvorhandenes um – kein Test
  liest echte Antigravity-Daten. Umgebungsvariable: `MASTER_SCHALTER_AGY_HEIM`. Tests: `test_chat_register.py`.
- **Antigravity-Empfang per Hook** (neu `agy_hook.py`, `python -m master_schalter.agy_hook EREIGNIS`): der
  Ereignisname kommt aus `sys.argv` (Antigravity legt ihn nicht auf stdin), gelesen werden nur `conversationId`
  und `invocationNum`. `SessionStart`/`PreInvocation`/`PostInvocation` melden `arbeitet` und spielen Postfach- und
  Auftragstexte als `injectSteps[].systemMessage.systemMessage` ein; `Stop` meldet `ruht` und antwortet bei
  vorliegender Nachricht `{"decision": "continue", "reason": …}`, sonst `{}` – **erst danach** wird bestätigt
  (Datei nach `erledigt/`). Weil Antigravity kein `stop_hook_active` kennt, zählt eine Schleifenbremse die
  Fortsetzungen je Gespräch (`AGY_STOP_MAX` 3, `agy-stop.json` im Datenordner, Rückstellung bei
  `invocationNum == 0`, Verfall nach 1 h); ohne sie liefe der Agent endlos. Jeder Fehler endet mit Rückgabe 0 ohne
  Ausgabe. Belegprobe: `<Arbeitsbereich>/.agents/hooks.json`. Tests: `test_agy_hook.py` (37).
- Hauptschalter Automatik im Leistenmenü (unter Themenzahl und Lage): „Hauptschalter Automatik: an“ mit Haken. Asymmetrisch
  sicher: Klick bei „an“ schaltet sofort aus (`anzeige.automatik_setzen(False)`, Menü wird aktualisiert); bei „aus“ steht
  „… aus – einschalten in der Übersicht …“ und der Klick öffnet nur die Übersicht (Ja/Nein-Rückfrage, Standard Nein) – das
  Menü ruft `automatik_setzen` nie mit `True` auf. Maßgeblich ist der frisch gelesene Zustand. Schreibfehler ⇒ Menüzeile
  „Automatik nicht geändert (<Klasse>)“ bis zur nächsten Aktualisierung, kein Absturz. Tests: `test_leiste.py`.
- Verwaiste „Prüfung läuft“-Meldung erkennen: `pruefkreis.wartet_melden` schreibt zusätzlich `"pid"`; `wartet.Meldung` hat
  `pid` (optional, kaputte Werte ⇒ keine pid), neu `wartet.lebt` (Windows: `OpenProcess`/`GetExitCodeProcess`, 87 ⇒ beendet,
  5/anderes ⇒ unbekannt; sonst `os.kill(pid, 0)`), `startzeit` (Windows `GetProcessTimes`) und `verwaist` (beendet oder
  nach der Meldung gestartet). Master-Status und Übersicht hängen „(verwaist – Prozess beendet; `warte THEMA --fertig`
  räumt auf)“ an; es wird nichts automatisch gelöscht. Tests: `test_wartet.py`, `test_pruefkreis.py`.
- Messzugang erneuert sich einmal selbst: Endet `claude_messen.messen` mit `anmeldung_abgelaufen` (Parameter
  `erneuern=True`), startet `claude_anmeldung.erneuern` genau einmal `claude auth status` (ohne Konsole, Ausgabe nach
  `DEVNULL`, 30 s Frist, Prozessbaum-Ende bei Timeout, wirft nie) und `messen` liest genau einmal neu. Gedrosselt auf einen
  Versuch je 30 min über alle Prozesse: Sperre `claude-erneuerung.lock`, Zeitstempel `claude-erneuerung.json` wird vor dem
  Start geschrieben, nicht schreibbar ⇒ kein Versuch (fail-closed), kaputt oder mehr als 30 min in der Zukunft ⇒ gilt
  als alt; die Uhrzeit wird erst unter der Sperre genommen, `taskkill` startet ohne Konsolenfenster (Codex-R1). Bleibt der Zugang
  abgelaufen: „Claude-Messzugang abgelaufen – automatische Erneuerung um HH:MM ohne Erfolg; …“. Wirksamkeit nicht belegt
  (README nennt die Erkennung). Tests: `test_claude_messen.py`, `test_claude_anmeldung.py` (u. a. zwei echte Unterprozesse);
  `conftest.py` ersetzt `claude_messen.cli_erneuern` automatisch, damit kein Test die echte CLI startet.
- Arbeitsweise je Thema (`protokoll` Standard | `vibe`): neues Modul `arbeitsweise.py`, Datei `arbeitsweise.json`
  (`{"version": 1, "themen": {thema: "vibe"}}`, streng gelesen, atomar geschrieben, nicht im Profilformat
  `themenmodi.json`). CLI `masterwechsel vibe THEMA an|aus` (nur von Hand; `modi.vibe_setzen` unter der Themensperre;
  Thema muss existieren; idempotent; nennt die Regel). `profil --json` ergänzt `arbeitsweise` und bei Vibe `vibe_regel`
  (bisherige Felder unverändert), `profil` (Text) zeigt dasselbe. Der Master-Status endet die Themenzeile bei Vibe auf
  „· VIBE“ (ungültige Datei: „· Arbeitsweise ?“ plus Hinweis). Übersichtsfenster: Spalte „Arbeitsweise“ und Umschalter
  mit Rückfrage (`uebersicht_modell.arbeitsweise_aktion`).
- Vorrang Vibe vor der Workerwahl: Vibe nur mit Ausführer Claude. `vibe an` und jedes Schreiben eines Profils mit anderem
  Ausführer bei Vibe werden abgelehnt (zentral in `modi._speichern` und vor der ersten Besitzmarke in
  `modi._umschalten_gesperrt`, damit auch `modus THEMA hermes-codex`, `master-setzen`, `alle` und der Wechselassistent
  geschützt sind). Ist `arbeitsweise.json` nicht lesbar, werden Profile mit anderem Ausführer als Claude fail-closed
  nicht geschrieben.
- Bei Vibe nennen Master-Status, Übersicht, `profil` und `master-setzen` „Prüfer Master-Kurzprüfung (Vibe, keine
  Codex-/Hermes-Gegenprüfung)“ statt des pruefkreis-Prüfers; der Worktree-Hinweis der Prüfer-Vorschau entfällt für Themen
  ohne Paar, weil diese immer im Hauptbaum schreiben (Codex-Ergebnisprüfung R1).

- `masterwechsel thema-anlegen THEMA [--master …]`: Thema ohne Codex-Paar (Profil plus Besitzdatei im Hauptarbeitsbaum,
  `modi.thema_anlegen`, `besitz.exklusiv_schreiben`); Reihenfolge Profil → Besitzdatei exklusiv, Wiederaufnahme einer halben
  Anlage („ergänzt“), Überschreibschutz für vorhandene Besitzdateien, Hauptbaum-Pflicht auch aus einem Git-Worktree.
- `modi._paar_pruefen(ohne_paar=True)`: Themen ohne Paar mit Profil gelten in `master_setzen`/`master_setzen_wenn` (damit
  `alle`), `worker_setzen`, `modell_setzen`, `fuehrt`/`geschuetzt` und `snapshot`; ihr Besitzpfad liegt immer im
  Hauptarbeitsbaum. Wechselassistent, Postfach, Automatik, `master_uebergeben_gesperrt` und `modus THEMA …` verlangen
  weiter ein Paar. Folge: `alle kontingent|zurueck` stellt jetzt auch Themen ohne Paar um (vorher „offen: Thema unbekannt“).

### Geändert
- Der Master-Status zeigt Themen ohne Paar mit „· ohne Codex-Paar“ (vorher „kein Paar“) und liest ihren Besitz aus der
  Besitzdatei im Hauptarbeitsbaum (vorher „Besitz unbekannt“).
- Master-Status statt `kurz`: `masterwechsel status` gibt jetzt die Übersicht aus, die bisher `kurz` lieferte (Verbrauch, Lage,
  Matrix, Themen, Sitzungen, Wartet worauf); die alte Zwei-Zeilen-Ausgabe (nur beide Kontingente, `cli.master_zeile`) entfällt.
  `kurz` bleibt als stiller Alias mit gleicher Ausgabe (nicht mehr in der Hilfe). Kopfzeile jetzt „Master-Status · HH:MM · Lage …
  · Hauptschalter Automatik an|aus“ (vorher „Master-Schalter · … · Automatik an“). `warte` meldet „steht im Master-Status“.
  Das Modul `kurz.py` behält seinen Namen (intern). Der lokale Chat-Befehl `/master-status` (gitignoriert, `.claude/commands`)
  liegt außerhalb dieses Pakets.
- Symbol und Menü zeigen keinen globalen Master mehr: der weiße Punkt über dem Balken entfällt (`symbol.bild` ohne
  Parameter `master`; `symbol._farbe` heißt jetzt `symbol.farbe`). Der Tooltip lautet „Lage X · Claude n % ·
  Codex n % verbraucht“ (`anzeige.tooltip_symbol`, 5-Stunden-Fenster) statt „M <Name> L<Lage> | …“, der Menükopf nennt
  die Zahl der Themen je Masterart („Themen: 3 fest · 2 nach Kontingent“, `anzeige.themen_zeile`) statt „Master: …
  seit …“. `masterwechsel status`/`master` und `master.json` bleiben unverändert.
- Leiste: Linksklick (Menüeintrag „Übersicht …“ mit `default=True`) öffnet das Übersichtsfenster als eigenen Prozess
  statt der Benachrichtigung; `fenster_befehl(modul)` kennt `fenster` und `uebersicht`, der Prozessstart steckt in
  `uebersicht_modell.modul_starten`.
- `claude_messen.messen` und `codex_messen.messen` führen den Messfehler-Status nach (Wrapper um die bisherige
  Messung `_messen`); Verhalten, Rückgabe und Ausnahmen bleiben gleich. `kurz` kennt `thema_felder`, `repo_bestimmen`
  und nimmt in `_themen` ein vorgegebenes Repo an; `kurz.verbraucht` ist jetzt `anzeige.verbraucht`.
- CLI: Über Pipes schreiben jetzt alle Befehle außer `statuszeile` UTF-8 auf stdout und stderr, auch Hilfe und Argumentfehler (vorher nur
  `kurz`); `profil`/`master-setzen` kamen über `/master-status` mit verstümmelten Umlauten an.
- `master-setzen` und `profil` (Text) zeigen den Prüfer: „Jetzt: Prüfer …“ nach der pruefkreis-Regel,
  bei „Nach Kontingent“ den Hinweis „Prüfer folgt dem Besitzer“ (`kurz.pruefer_vorschau`); JSON unverändert.
- `kurz`: Jede Themenzeile nennt den Prüfer – dieselbe Regel wie `pruefkreis.py` (Prüfer ≠ Master-Familie):
  Master wie `pruefkreis` ihn liest (`<name>.master`, auch übergeordnetes Thema): Codex ⇒ „Prüfer Hermes (Master
  Codex)“, Claude/Hermes ⇒ „Prüfer Codex“, fehlende/unlesbare Datei ⇒ „Prüfer ? (pruefkreis braucht --master)“.
  Aus einem Git-Worktree liest `kurz` die Besitzdateien im Hauptarbeitsbaum (neu `uebergabe.haupt_wurzel`).
- `kurz`: Jede Limitzeile sagt ausdrücklich „… % verbraucht“ und nennt die Zeit bis zum Reset („Reset in 3 h 33 min,
  01:39“); Überschrift „Kontingent verbraucht:“, „Als Nächstes“ mit „(in …)“. Anlass: „67 %“ war mehrdeutig;
  zuerst „… % übrig“, auf Sebastians Wunsch (28.10.) nur noch der Verbrauch (`kurz.verbraucht` statt `kurz.rest`).
- Leiste: Eine gescheiterte Claude-Messung steht mit Fehlerart und ggf. HTTP-Code im Log, z. B.
  `Claude-Messung fehlgeschlagen: … [http, HTTP 503]`, `[netz]`, `[antwort]`, `[speichern]` oder eine der
  Anmeldearten `[anmeldung_…]` (vorher nur der
  allgemeine Text; die Ausfälle vom 27.10. 12:11–12:53 ließen sich so nicht mehr erklären). Keine Antwort- oder
  Zugangsdaten im Log; der Anzeigetext im Menü bleibt unverändert.

### Neu
- Übersichtsfenster (`uebersicht.py`, Modell `uebersicht_modell.py`): Kopf mit Uhrzeit, Lage und Hauptschalter
  Automatik, Kontingent als Fortschrittsbalken („n % verbraucht“, Statusfarbe wie das Symbol), Themen-Tabelle mit
  Master-Auswahl, „Alle nach Kontingent“ / „Alle wie vorher“ (Bericht im Textfeld), „Übergabe starten …“,
  „Aktualisieren“, unten „Wartet worauf“ und Sitzungen. Jede Änderung fragt vorher (Ja/Nein, Standard Nein). Eine
  Instanz (`uebersicht.lock`), Aktualisierung alle 5 s im Hintergrund-Thread. Lesen und Schreiben nutzen dasselbe
  `repo` (Hauptarbeitsbaum); Schreiben nur, wenn `repo/.git` ein Ordner ist, sonst „Hauptarbeitsbaum nicht gefunden –
  nur Anzeige“. Plan in vier Fassungen von Codex geprüft.
- Messfehler-Status `messfehler.json` im Datenordner (`signale.messfehler_setzen/_loeschen/_lesen`): Fehler ⇒ Eintrag
  mit Kategorie, festem Text, `seit` (bleibt in der Serie) und `zuletzt`; Erfolg ⇒ Eintrag der Quelle weg; keine
  Verfallsgrenze; Schreibfehler werden verschluckt. `kurz` und die Übersicht zeigen „Claude-Messung scheitert seit
  HH:MM (letzter Versuch HH:MM): …“. Lesen-Ändern-Schreiben unter der Sperre `messfehler.json.lock` (Codex-R1).
- Übersicht nach Codex-Ergebnisprüfung R1: nach einem Lesefehler stehen keine alten Balken mehr (alle „unbekannt“,
  Hinweis „keine aktuellen Messdaten“), Automatik ist „unbekannt“ und nicht umschaltbar; die Balkenfarbe kommt aus
  dem ungerundeten Wert wie beim Symbol (96,6 % bei Schwelle 97 bleibt gelb).
- `masterwechsel alle kontingent|zurueck` (`alle.py`): alle Themen auf einmal nach Kontingent und zurück auf die
  vorher gemerkten festen Rollen (Merkdatei `alle-vorher.json`, nach Abschluss archiviert statt gelöscht). Hermes
  (Master, Besitz, abgebrochener Wechsel) bleibt unberührt. Neu in `modi`: `master_setzen_wenn` – Prüfung, Merken
  und Umschalten unter derselben Themensperre. `kurz` zeigt den Merkstand. Plan in vier Fassungen von Codex geprüft.
- `masterwechsel warte THEMA TEXT…` / `warte THEMA --fertig` (`wartet.py`): „Wartet worauf“ je Thema;
  `kurz` zeigt die Meldungen (älteste zuerst, „seit“, > 24 h „(veraltet?)“) statt der festen Zeile
  „noch keine Statusquelle“; ohne Meldung „Wartet worauf: nichts gemeldet“.
- `masterwechsel kurz` (`kurz.py`): Kurzübersicht für den Chat bei Steuerung über Remote-Sitzungen. Zeigt
  Rest-Limits mit Reset und Messzeit, Matrixlage mit Planer/Prüfer/Ausführer, je Thema Master-Vorgabe,
  Besitzer, Ausführer und wirksame Automatik (aktives Paar + Master „kontingent“ + globale Automatik),
  die drei jüngsten Sitzungen (veraltetes „arbeitet“ markiert), den nächsten Reset im Limit und
  ausdrücklich „Wartet worauf: noch keine Statusquelle“. Nur lesend; über Pipes UTF-8.
- `kurz` zeigt je Sitzung das Thema, wenn die Zuordnung Chat → Thema bestätigt ist (`zuordnung.json`);
  sonst „Thema nicht zugeordnet“. Keine Vermutung aus Titel oder Ordner.
- Tests `tests/test_kurz.py` (13), u. a. Rest statt Verbrauch, Automatik-Bedingung, unlesbarer Besitz,
  nur-lesend-Nachweis und UTF-8 über eine Pipe (ohne die Umstellung rot).

## [0.5.1] – 2026-10-27

Aufträge an Claude, Claude-Anmeldung und P9 (Codex-Kontingent aktiv messen).

### Neu
- **Aufträge an Claude (v0.5.1):** `masterwechsel claude-auftrag` legt einen Auftrag für eine Claude-Code-Sitzung
  ab (Verweis auf eine `.hermes/`-Datei, gemeinsame Dateibasis im Hauptarbeitsbaum); `masterwechsel
  claude-sitzungen` zeigt die Sitzungen aus dem Statusregister. Der Claude-Hook stellt Aufträge bei
  `UserPromptSubmit`/`PostToolUse` und – neu – bei `Stop` per `decision: block` zu (nicht bei aktivem
  `stop_hook_active`). Eine vorhandene Ergebnisdatei desselben Auftrags (`…-ergebnis-<id>.md`) verhindert die erneute Zustellung. Wechselnachrichten des
  Postfachs bleiben unverändert.
- **Claude-Anmeldung:** Taskleistenaktion öffnet unter Windows `claude auth login --claudeai` in einer eigenen
  interaktiven Konsole. Exit 0 fordert nur eine neue Messung an; deren tatsächlicher Erfolg bleibt der Beleg
  für lesbare Kontingentwerte. `CLAUDE_CONFIG_DIR` wird geteilt; leer oder ungesetzt nutzt `~/.claude`.

### Geändert
- **Claude-Messfehler:** fehlender, defekter, abgelaufener und vom Server abgelehnter lokaler Messzugang haben
  getrennte sichere Meldungen; 429 bleibt als Statuscode erhalten. Ein Messfehler erneuert nie den Cachestand.
- **Native Kontingente:** eine fehlgeschlagene OAuth-Abfrage verhindert die bestehende Automatikprüfung nicht;
  deren eigene Frische- und Sicherheitsgates bleiben wirksam. Alte Kontingentstände sind im Menü als veraltet markiert.
- **Grenzen:** kein eigener Token-Refresh und keine Aussage über Claude-Desktop-Anmeldung oder Aboablauf. Der
  Autostart bleibt ein separates offenes Thema.

### Behoben
- **Automatik löste praktisch nie aus:** `automatik._codex_frei` verlangt eine Codex-Messung von höchstens
  10 Minuten, `signale.codex_lesen` las aber nur Sitzungsdateien (`rollout-*.jsonl`), die nur frisch sind, solange
  Codex arbeitet. Arbeitet Claude und Codex ruht, war die Messung veraltet.

### Neu (P9 Codex-Messung)
- `codex_messen.messen(programm=None, frist=20.0, jetzt=None)`: startet `codex.exe app-server` (Argumentliste,
  keine Shell, `stderr` verworfen, unter Windows ohne Konsolenfenster, Umgebung ohne API-/Token-Schlüssel),
  führt `initialize`, `initialized`, `account/rateLimits/read` aus und beendet den Prozess immer (Bereinigung
  aus `modelle`). Fenster werden nach `windowDurationMins` zugeordnet (300 → 5h, 10080 → Woche), `usedPercent`
  außerhalb 0–100 ist ein Fehler. Gespeichert werden nur Prozent, Rücksetzzeit und Messzeit
  (`codex-kontingent.json`, atomar), keine Kontofelder. Fehler: `Kontingent("Codex", fehler=…)` mit festem
  Text und Fehlerklasse, nie Text aus der Antwort.
- `signale.codex_schreiben` / `codex_messung_lesen` / `codex_datei`; `signale.codex_lesen` nimmt den neueren
  Stand aus Sitzungsdateien und aktiver Messung (Verhalten ohne Messdatei unverändert).
- CLI `masterwechsel codex-messen` („Codex-Kontingent aktualisiert.“ bzw. fester Fehlertext, Exit 1).
- Leiste: Codex wird im 60-s-Messtakt höchstens alle `CODEX_TAKT_SEKUNDEN` = 300 gemessen und zusätzlich vor
  `_automatik_anfordern`, wenn die frische Claude-Messung ≥ Schwelle ist und der Codex-Stand älter als
  `CODEX_VOR_ALTER_SEKUNDEN` = 120 s ist. Läuft im Messfaden; Fehler nur mit Fehlerklasse im Log.

### Behoben (Nachbesserung P9, Runde 1)
- **Bereinigung konnte unbegrenzt hängen:** `close()` auf dem gepufferten `stdout` blockiert, solange der Lesefaden
  darin liest (z. B. wenn der Kill nicht wirkte oder ein Kindprozess die Pipe nach dem Ende des Elternprozesses offen
  hielt). `codex_messen` schließt `stdout` nun nie, solange der Lesefaden lebt, und hat eine harte Zeitgrenze
  (Gnadenfrist + Kill-Wartezeit + Einsammelfrist); bei Scheitern der feste Fehler „Bereinigung fehlgeschlagen“.
  Dieselbe Absicherung in `modelle._bereinigen` (Modellkataloge): keine Strom-Schließung bei lebendem Lesefaden,
  stattdessen der bestehende `BereinigungsFehler`.
- Prozessbaum wird unter Windows über ein Jobobjekt beendet (Prozess angehalten gestartet, zugewiesen, fortgesetzt;
  `KILL_ON_JOB_CLOSE`), auch wenn der Elternprozess zuerst endet. `taskkill /T` findet Kinder eines schon beendeten
  Elternprozesses nicht. Rückfall ohne Job: `taskkill`/Prozessgruppe.
- Scheitert der Start des Lesefadens, wird der gestartete Prozess trotzdem beendet.
- Ein Ausweichdatensatz `rateLimitsByLimitId["codex"]` mit fremder `limitId` (z. B. `premium`) gilt nie als Codex-Messung.

### Behoben (Nachbesserung P9, Runde 2 – Prüfer Hermes)
- **Angehaltener Prozess konnte als Waise bleiben:** Scheiterte `OpenProcess` für den angehalten gestarteten Prozess,
  blieb das (leere) Jobobjekt aktiv; die Bereinigung beendete nur den Job und übersprang `taskkill`, der nie
  fortgesetzte Prozess lief weiter. Jetzt wird der Job in diesem Fall geschlossen, damit der Rückfall
  `taskkill /T /F` greift. Regressionstest `test_scheitert_openprocess_wird_der_angehaltene_prozess_trotzdem_beendet`
  (ohne die Korrektur rot).

### Tests (Nachbesserung)
- Test `test_claude_hook.py::test_belegte_globale_sperre_im_eigenen_prozess` vergleicht mit einem Leerlauf-Prozessstart
  (`dauer < leerlauf + 2 s`, bis zu drei frisch verglichene Versuche gegen Lastausreißer) statt mit fester
  Wanduhrzeit (war unter Volllast rot).
- Neue Tests: Bereinigung ohne wirkenden Kill, Elternprozess endet vor dem Enkel, Rückfall ohne Job, Fadenstart scheitert,
  fremde `limitId` im Ausweichdatensatz, Lesefaden-Hänger in `modelle`.

### Tests (P9)
- `tests/test_codex_messen.py` (Attrappenprogramm als Python-Skript, nie ein echtes `codex.exe`), Ergänzungen in
  `test_leiste.py` und `test_cli.py`. `tests/conftest.py`: automatische Absicherung, dass kein Test ein echtes
  `codex.exe` startet oder `~/.master-schalter` bzw. `~/.codex` liest.

## [0.5.0] – 2026-10-25

Wechselassistent, Bausteine P1/P2 (Vorgänge, Chatliste), P4 (Ablauf und Zustellung), P3a (Claude-Empfang per Hook),
P7a (Menü, Fenster, Einstellungen, Takt) und P8/K7 (Automatik wahlweise über den Assistenten). Gebaut auf Branch
`v0.5.0-wechselassistent`, auf `main` zusammengeführt. Noch offen: neue Sitzungen starten (S0b/S0c/P5),
Hermes-Empfang (P6), Kontingent-Wächter (P3b).

### Neu
- **Automatik über den Wechselassistenten (P8, K7):** Einstellung `automatik_weg` (`alt`|`assistent`, Standard
  `alt`; unbekannt oder kaputt gilt als `alt`) mit `anzeige.automatik_weg()` / `automatik_weg_setzen()`.
  `automatik.lauf(weg=…)`: Entscheidung und alle Schutzschritte bleiben unverändert; beim Weg `assistent` wird
  die Kennung `<thema>@<reset>` zuerst dauerhaft in `automatik_ausgeloest.json` vermerkt (höchstens ein Versuch je
  Paar und Limitfenster, `faellige(…, ausgeloest=…)` behandelt sie wie bekannte Vorgänge), die Reservierung geht
  auf `claude <Zeit>` zurück und **nach dem Verlassen der Themensperre** übergibt `assistent.uebergeben(thema,
  "codex", von_chat=None, nach_chat=<Paar-Chat>)`. Ergebnis als `Stand` (Phase des neuen Vorgangs, bei Fehler
  fester Text „Wechsel nicht gestartet (<Klasse>)"), Protokolleinträge `automatik_ausgeloest` /
  `automatik_nicht_gestartet` (mit Klartext im Fenster). Der alte Weg bleibt unverändert und parallel schaltbar.
  Leiste: „Einstellungen ▸ Automatik-Weg" (zwei Radiopunkte, Haken aus der Momentaufnahme); Menü- und Statuszeilen
  nennen bei `assistent` „· über Wechselassistent". CLI: `masterwechsel automatik-weg [alt|assistent]` (ohne
  Argument: anzeigen; ungültige Eingabe wird nicht wiederholt).
- **Wechselfenster (P7a, E7):** `fenster.py` (tkinter, Standardbibliothek) mit den Bereichen Themen, „Übergabe
  starten“ (Thema, Ziel, Von-Chat, Nach-Chat, Bestätigung per Ja/Nein mit Standard Nein), Vorgänge (Phase in
  Klartext, Zustellhinweis nach E8, „Jetzt weiter“, „Abbrechen“, „Text kopieren“ für Hermes) und Protokoll in
  Klartext. Start: `python -m master_schalter.fenster` oder `masterwechsel fenster`. Nur eine Instanz
  (`zustand.instanz_sperre("fenster")`, Sperrdatei `fenster.lock`); eine zweite beendet sich still. Alle 3 s
  liest ein Hintergrund-Thread neu, Aktionen laufen ebenfalls im Hintergrund, die Oberfläche bleibt im Tk-Thread.
  Ohne Vorschlag für das Thema bleiben die Chat-Felder leer, „Übergeben“ verlangt eine ausdrückliche Wahl.
  Ein abweichender Codex-Chat wird nach dem Anlegen als Paar gemerkt (`chat_zuordnung.bestaetigen`).
- **`fenster_modell.py`:** Ansichtsmodell ohne Oberfläche (Momentaufnahme `aufnehmen`, `chat_optionen`,
  `zustellhinweis`, `protokoll_klartext`, `hinweis_fuer`, die Aktionen `uebergabe_ausfuehren`/`weiter`/`abbrechen`);
  jede Quelle einzeln fehlertolerant, Fehlertexte nur Klassennamen oder feste Sätze.
- **`assistent_vorgaenge.abbrechen(id)`:** Abbruch von Hand nur vor `rolle_gesetzt` (`ABBRECHBAR` = die
  blockierenden Phasen ohne `sende`), unter der Themensperre, Vergleich-und-Setzen nach `verworfen`, Grund
  „von Hand abgebrochen“, Protokolleintrag; spätere Phasen werden abgelehnt, ohne etwas zu ändern.
- **Takt des Wechselassistenten in der Leiste:** eigener Faden alle 10 s (`ASSISTENT_TAKT_SEKUNDEN`), unabhängig
  vom 60-s-Messtakt, ruft `assistent.fortsetzen` für jeden offenen Vorgang; Fehler nur mit Klasse im Log, kein
  Absturz; Menü wird bei Phasenwechsel neu gebaut. Beim Start einmal `wiederaufnehmen()` (Log nur mit Zählern).
- **Windows-Hinweise:** je Vorgang und Ereignis genau einmal (Merker im Speicher): Abgabe länger als 2 min
  offen (mit Fristende), „Rolle jetzt bei <Ziel>“, „<Ziel> hat übernommen ✓“, „Wechsel braucht Blick ins Fenster“
  (`fehler`/`unklar`/`verworfen`, nicht bei Abbruch von Hand). Vorgänge, die länger als 15 min nicht geändert
  wurden, melden nichts.
- **`zustand.instanz_sperre(name)`:** nicht blockierende Einzelinstanz-Sperre im Datenordner.
- **`assistent.py`:** `uebergeben(thema, ziel, von_chat, nach_chat)` legt den Vorgang an
  (Write-ahead mit Vorzustand), schickt dem alten Chat den Abgabe-Auftrag und ruft einmal
  `fortsetzen` auf. `fortsetzen(vorgang)` ist der idempotente Takt: 10-Minuten-Frist
  (`ABGABE_FRIST`) mit Info an den alten Chat (nur der Gewinner des Überspringens sendet), Rolle
  setzen unter der Themensperre (Marke ≠ Vorzustand → `verworfen`, „Stand geändert“), danach die
  Nachricht an den neuen Chat (`sende` vor dem Transport). Zustellung an Codex über `codex.exe
  queue`, an Claude/Hermes über das Postfach; Transporte laufen nie unter Themen- oder Dateisperre.
  Doppelklick-Schutz (belegte Sperre, laufender Vorgang); eine übersprungene Abgabe ergibt einen
  Zusatzsatz im Text an den neuen Master.
- **Chat-Referenzen:** `ChatRef(werkzeug, kennung)`; `Vorgang` bekommt die optionalen Felder
  `von_chat` und `nach_chat` (alte Dateien ohne diese Felder lesen weiter). Kennungen stehen nur in
  `assistent.json`.
- **`protokoll.py`:** `protokoll.jsonl` (G10) mit den Entscheidungen des Ablaufs, ohne Kennungen,
  Titel oder Inhalte; `lesen(limit)` für das spätere Fenster.
- **CLI:** `uebergeben THEMA ZIEL [--von WERKZEUG:KENNUNG] [--nach WERKZEUG:KENNUNG]` und
  `fortsetzen [VORGANG]`; beide geben nur Vorgangs-ID, Thema und Phase aus.
- **Claude-Empfang per Hook (P3a):** `claude_hook.py`, aufrufbar als `python -m master_schalter.claude_hook`.
  `UserPromptSubmit` und `PostToolUse` melden `arbeitet` und merken mit `postfach.vormerken("claude",
  session_id)` Nachrichten vor; gibt es welche, steht genau ein JSON `hookSpecificOutput` mit
  `additionalContext` (feste Einleitung plus feste Postfachtexte) auf stdout, sonst keine Ausgabe. `Stop`
  setzt nur `ruht` und blockiert nie (kein `decision: block`). Jeder Fehler (kaputtes JSON, unzulässige
  Sitzungskennung, belegte Sperre, `OSError`, Importfehler) endet mit Exit 0 ohne Ausgabe; auf Modulebene
  steht nur die Standardbibliothek, stdin wird auf 1 MB begrenzt, nur `hook_event_name` und `session_id`
  werden ausgewertet. **Der Hook ist noch nicht in eine `settings.json` eingetragen.**
- **Ausgabe vor Zustellung (Postfach):** `postfach.abholen` besteht jetzt aus `vormerken` (prüft wie bisher,
  verschiebt nichts, liefert `Vorgemerkt`) und `bestaetigen` (liest unter der Themensperre erneut, übergeht
  geänderte Dateien und trifft mit `_entscheiden` wieder dieselbe Entscheidung wie früher `abholen`:
  zustellen, verwerfen mit Grund oder liegen lassen – wechselt der Master dazwischen, wird der Vorgang
  nicht `im_chat`; wurde die Nachricht schon ausgegeben, steht sie im Chat und die Quittung scheitert, der
  Text sagt dazu „beginne keinen Schritt“). Der Hook bestätigt erst nach erfolgreicher Ausgabe; scheitert sie, bleibt die
  Nachricht liegen und kommt beim nächsten Ereignis erneut (lieber doppelt als verloren, gültig nur über die
  Quittung, G5). `abholen` verhält sich unverändert. Das Prozessende des Hooks ist hart (`os._exit(0)` nach
  letztem `flush`), damit geschlossenes stdout nicht mit stderr-Meldung und Exit 120 endet.
- **Laufzeit-Obergrenze:** `vormerken`, `bestaetigen` und `abholen` haben die optionalen Parameter `frist`
  (Sperrfrist für Themensperre und `aendern`) und `bis` (Zeitbudget als `time.monotonic()`-Zeitpunkt; danach
  wird keine weitere Datei angefasst); eine belegte Sperre lässt die Datei liegen. Der Hook nutzt 0,3 s
  Sperrfrist, 0,6 s Budget zum Vormerken und 0,4 s zum Bestätigen.
- **Statusregister (K2):** `status.py` mit `status/<werkzeug>-<kennung>.json` (`zustand`, `zeit`,
  `ereignis`), atomar geschrieben; `arbeitet` höchstens einmal je 60 s, solange der Zustand gleich bleibt;
  `lesen(werkzeug, kennung)` liefert `(zustand, zeit)` oder `None` (= unbekannt) für den späteren
  Ruhenachweis.
- `assistent_vorgaenge.phase_gewinnen` meldet zusätzlich, ob der aufrufende Prozess den Phasenwechsel
  gemacht hat; `postfach.text()` baut die festen Nachrichtentexte (auch für die Codex-Queue).

### Geändert
- **Menü nach Plan E9:** oben „Übergabe starten …“, Zeilen offener Wechsel, „Aktualisieren“, „Einstellungen ▸“,
  „Beenden“. Unter „Einstellungen ▸“: „Wechsel-Schwelle“, „Modelle aktualisieren“ (mit Katalogzeilen),
  „Automatik je Thema“ (bisher „Chats übergeben“), „Arbeitsmodus je Thema“, „Standard-Master (übrige Themen)“
  (bisher „Master wechseln“). Das Verhalten dieser Punkte ist unverändert; die Statuszeilen der Automatik bleiben
  oben. Die bestehenden Tests wurden auf die neuen Stellen umgestellt (nichts abgeschwächt); die Zahl der beim
  Start angeforderten Fäden steigt um den Takt des Assistenten.
- `abgabe_ueberspringen` gilt jetzt auch aus `abgabe_fehler` (Frist nach nicht gestartetem Transport).
- **Blockade neuer Wechsel:** nur noch in den Phasen `av.WECHSEL_BLOCKIEREND` (Rolle noch nicht gesetzt
  oder `sende`); ab `rolle_gesetzt` blockiert ein Vorgang nicht mehr.
- **Überholt:** nach erfolgreichem Rollensetzen werden die anderen Vorgänge desselben Themas in den
  Phasen `av.UEBERHOLBAR` (`rolle_gesetzt`, `gesendet`, `im_postfach`, `im_chat`, `unklar`, `fehler`)
  mit einem `av.aendern`-Schritt auf `verworfen` / „überholt“ gesetzt, mit Protokolleintrag.
- **Protokoll ohne Fremdtexte:** Fehler beim Fortsetzen, Rollensetzen und Markenprüfen nennen nur die
  Fehlerklasse (Ursache an `__cause__`); der Verwerfungsgrund bei überholter Marke ist ein fester Text.
- `wiederaufnehmen`: `abgabe_fehler` erscheint als Status `abgabe_offen` mit Fristhinweis.
- **Zustellung unter der Themensperre (Ergebnisprüfung R1):** Markenprüfung und `rolle_gesetzt → sende`
  laufen gemeinsam unter `thema_sperre` (blockierend, kurze Frist; belegt = nichts tun, nächster Takt);
  der Transport bleibt außerhalb jeder Sperre. `_rolle_setzen` wartet, solange ein anderer Vorgang
  desselben Themas in `sende` steht.
- **Abgabe-Info erst nach dem Rollenwechsel:** die Frist setzt nur noch `abgabe_uebersprungen`; die Info
  an den alten Chat geht erst raus, wenn `_rolle_setzen` den Wechsel nach `rolle_gesetzt` gewonnen hat
  (nur bei übersprungener Abgabe mit `von_chat`; Codex außerhalb jeder Sperre). Bei Absturz dazwischen
  geht sie verloren, nie nachgesendet.
- **Restfenster vor dem Transport (R2):** `_zustellen` prüft die Marke direkt vor dem Senden (außerhalb der
  Sperre) noch einmal; passt sie nicht, `sende → verworfen` (Protokoll `neu_entfallen`), nichts gesendet
  (nicht lesbar: `fehler`). Ein Restfenster bleibt grundsätzlich – die Gültigkeit erzwingt die Quittung (G5).
  `postfach.TEXT_NEU` ergänzt: „Schlägt die Quittung fehl, beginne keinen Schritt – die Nachricht gilt dann
  nicht mehr.“
- **Abgabe-Info nach Rückwechsel (R2):** vor dem Senden wird geprüft, dass der Vorgang nicht `verworfen` ist
  und die Marke noch genau diesen Wechsel trägt; sonst Protokoll `info_entfallen`. `TEXT_ABGABE_INFO`
  ergänzt: „Maßgeblich ist die Besitzmarke; prüfe im Zweifel `masterwechsel profil {thema}`.“
- **Bereinigte Ausnahmen (R2):** Jede Ausnahme, die `uebergeben` oder `fortsetzen` verlässt, ist ein
  bereinigter `AssistentFehler` (auch aus `abgabe_ergebnis` und den Aufrufen nach dem Anlegen); bleibt dabei
  `abgabe_sende` stehen, macht `wiederaufnehmen` daraus `abgabe_unklar`.
- **Fehlermeldungen ohne Pfade:** Hilfsfunktion für alle `AssistentFehler` aus fremden Ausnahmen; mit
  `OSError` in der Kette steht nur ein fester Text mit Fehlerklasse (`SperrFehler`: „Sperre gerade
  belegt“). Fremde Ausnahmetexte werden nie übernommen (nur Fehlerklasse); „Thema unbekannt“ prüft `uebergeben` selbst (Prüfung R3/R4); ungeprüfte Eingaben (Thema, Vorgangs-ID)
  und `OSError`-Texte werden in Meldungen und CLI nie wiederholt (R6).
  `uebergeben ZIEL` und `quittieren ART` ohne argparse-`choices` (kein Echo der Eingabe); `quittieren` meldet
  Vorgangs-ID-Fehler, veraltete Marke und Datei-/Sperrfehler nur mit festem Text bzw. Fehlerklasse (R7).
  `modi.py` unverändert.

### Noch nicht gebaut
- Ruhenachweis (G8b, liest das Statusregister), Hook-Eintrag in `settings.json`, Empfang im Hermes-Chat (P6;
  bis dahin „Text kopieren“ im Fenster), Starten neuer Sitzungen (S0b/S0c/P5).

## [0.4.1] – 2026-10-21

### Behoben
- **Claude-Modellkatalog nach Claude-Code-Update:** Das npm-Paket ab 2.1.3xx enthält kein `cli.js`
  mehr, sondern das native `bin/claude.exe`. `claude_programm()` liefert jetzt das Aufrufpräfix
  `(node, cli.js)` **oder** `(claude.exe,)` (Suche zusätzlich in `%APPDATA%/npm/node_modules/@anthropic-ai/claude-code/bin/`
  und `~/.local/bin/`); vorher meldete der Katalog „Programm nicht gefunden". Echter Abruf am 21.10.
  mit 2.1.304: 5 Modelle.
  Liegt noch ein altes `cli.js` herum, aber kein Node, geht die Suche zum nativen Programm weiter.
- **Tests unabhängig von der Installation:** Die Fixture `daten` setzt feste Attrappenpfade für
  `MASTER_SCHALTER_CLAUDE_CLI`/`MASTER_SCHALTER_NODE`; 8 Tests hingen zuvor davon ab, dass auf dem
  Rechner ein `cli.js` liegt. Zwei neue Tests für das native Programm.

### Geändert
- Version 0.4.1 (`__init__.py`, `pyproject.toml`).

## [0.4.0] – 2026-10-20

Gebaut 16.10. auf Branch `v0.4.0-rollen-modelle`, am 20.10. mit 0.3.5 zusammengeführt;
die 0.3.5-Reparatur (Wechselsperre außerhalb des Traycallbacks) bleibt vollständig erhalten.

### Neu
- **Rollen und Ausführermodelle je Thema (Profil v2):** `themenmodi.json` speichert je Thema
  `master` (`kontingent|claude|codex|hermes`), `worker` (`workflow|claude|codex|hermes`) und
  `modell` (Kennung oder `null`; „Nach Workflow“ nur ohne festes Modell, Hermes genau
  `deepseek/deepseek-v4.1-flash`). Alle neun ausdrücklich gewählten Master-/Ausführer-Kombinationen
  sind setzbar; Version-1-Dateien werden **nur lesend** migriert (Migration beim ersten
  ausdrücklichen Schreibvorgang), kaputte Dateien werden strikt abgelehnt statt auf Automatik
  zurückzufallen. Neue öffentliche API `profil`, `master_setzen`, `worker_setzen`,
  `modell_setzen`; Worker-/Modellwechsel lassen Masterfeld und `.master`-Marke bytegleich,
  Modellwahlen werden gegen den erfolgreich ermittelten Katalog geprüft.
- **Dynamische Modellkataloge (`modelle.py`):** Codex meldet `models` über den reinen
  App-CLI-Metadatenaufruf `debug models` (nur `visibility=list`); Claude Code über die lokale
  Control-Initialisierung ohne Anmeldung und ohne Benutzerprompt (nur `value`/`displayName` der
  eigenen passenden `control_response`). Lokaler Metadatencache (`modelle.json`), TTL 24 h,
  Fristen 30 s je Abfrage und 65 s gesamt, feste Byte-/Zeilen-/Modellgrenzen, Single-Flight je
  Anbieter, verlustfreies Mergen unter kurzer globaler Sperre; bei Fehlern bleibt das letzte gute
  Ergebnis mit sichtbarem Fehlerstatus stehen. Keine Inferenz, keine API-/Fremdprovider-Schlüssel
  im Kindprozess, Bereinigung ausschließlich des eigenen Prozessbaums
  (`taskkill /PID <eigene PID> /T /F`, keine Namenssuche). Herkunft/Grenzen offiziell dokumentiert:
  https://learn.chatgpt.com/docs/cli/reference und https://learn.chatgpt.com/docs/app-server ;
  kein Kontokatalog-Versprechen.
- **Menü „Arbeitsmodus je Thema“:** je Thema getrennte Untermenüs **Master** (`Nach Kontingent`,
  `Claude Code`, `Codex`, `Hermes`), **Ausführer** (`Nach Workflow`, `Claude Code`, `Codex`,
  `Hermes`) und **Ausführermodell** (gemeldete Modelle des gewählten Ausführers; bei „Nach
  Workflow“ deaktivierter Hinweis; bei Hermes genau `DeepSeek V4.1 Flash`). Providerherkunft immer
  sichtbar (Codex-Modelle aus dem ChatGPT-Abo, Hermes über OpenRouter kostenpflichtig), neuer
  Menüpunkt **Modelle aktualisieren**; Menü und Häkchen ausschließlich aus dem Snapshot, Aktionen
  im Hintergrund mit nichtblockierender Themensperre, Katalogabgleich mit Single-Flight und
  Drossel (30 min). Gespeicherte, nicht bestätigte Modelle bleiben sichtbar und werden nie still
  ersetzt; veraltete/fehlerhafte Kataloge werden im Menü benannt, blockieren aber nichts.
- **CLI (bestehende Befehle unverändert):** `profil THEMA [--json]`, `master-setzen THEMA MASTER`,
  `worker-setzen THEMA WORKER`, `modell-setzen THEMA MODELL|standard`,
  `modelle [PROVIDER] [--aktualisieren] [--json]`. Die JSON-Ausgabe ist maschinenlesbar; Fehler
  liefern Exit 1 und eine klare Diagnose ohne rohe Werkzeugantworten. `profil THEMA --json` ist
  vor jedem **neuen** Workerauftrag die verbindliche Provider-/Modellvorgabe (README/AGENTS).

### Geändert
- Persönliches Themenprofil: Alter `hermes-codex`-Modus wird als `hermes/codex/gpt-6-luna`
  gedeutet; die bisherigen Befehle `modus` und `setzen` bleiben kompatibel. Feste Masterrollen
  bleiben vor Automatik, manueller Sammelrückgabe und alten ACKs geschützt (Paket B).
- Version 0.4.0 (`__init__.py`, `pyproject.toml`); README auf den neuen Stand (Bedienung,
  Rollenprofil, Katalogquellen und -grenzen, verbindliche Profilabfrage, Fahrplan).

### Behoben
- **NT-Pfadpräfix-Härtung:** Die Besitzpfadprüfung vergleicht jetzt komponentenweise und toleriert
  `\\?\`-Präfixe (Windows-Race), während ein echter Pfad außerhalb des Repositorys weiter ein
  Fehler bleibt.
- **Testlast:** Der Test „ungültige Protokollantwort bei laufendem Prozess“ nutzt bewusst
  großzügige, im Docstring begründete Zeitfenster (30 s Abfrage, 20 s Kill-Wartezeit), damit
  unter Rechnerlast deterministisch „Antwort ungültig“ gilt – Kill-Args, Kind-tot und
  Katalog-unverändert bleiben scharf. Der 429-Pausentest zählt ohne Rennen gegen den
  Bestätigungsfaden.
- **Testlast beim Zusammenführen (20.10.):** Zwei Bereinigungstests lasen die PID-Datei des
  hängenden Kindskripts sofort nach dem Lauf; unter Last war das Kind noch nicht gestartet
  (`FileNotFoundError`). Sie warten jetzt bis 20 s auf die Datei (`_pid_lesen`); Budget-, Fehler-
  und Lebendprüfung bleiben unverändert scharf.

## [0.3.5] – 2026-10-20

### Behoben
- Der Menücallback reserviert die Wechselsperre vor dem Start eines Hintergrundfadens, damit ein wartender Bestätigungsdialog den Traycallback nicht festhält. Direkte Wechselaufrufe nutzen dieselbe Sperre; parallele und reentrante Aufrufe werden übersprungen.
- Dialog- und Threadstartfehler melden sich sichtbar und geben die Sperre frei. Ein Dialogabbruch wechselt nichts; nur Ja führt den bisherigen Wechsel und bei Codex die bestehende Rückgabe aus.
- Tests prüfen Dialogflags und Ablauf mit Attrappen. Eine Bedienbarkeit des nativen Dialogs auf dem Desktop ist damit nicht nachgewiesen.

### Geändert
- Version 0.3.5 (`__init__.py`, `pyproject.toml`).

## [0.3.4] – 2026-10-16

### Neu
- **Arbeitsmodus je Thema:** `masterwechsel modus THEMA [kontingent|hermes-codex]` und Taskleisten-Untermenü mit cachierten Radiooptionen. Hermes-Modus bleibt unabhängig von Quoten geschützt; Moduswahl startet keine Sitzung und erzeugt kein ACK.
- **Fail-closed Themenbesitz:** Moduswechsel entwertet offene Vorgänge in definierter Reihenfolge, behandelt Teilschreibfehler idempotent und erhält Schutz über Hermes-Besitz oder gespeicherten Hermes-Modus. Automatik, verspätete ACKs, manuelle Rückgabe und globaler Claude-Rückwechsel respektieren den Schutz.
- **Codex-Code-Worker-Regel:** README und AGENTS dokumentieren den lokal verifizierten nativen Codex-App-CLI-Aufruf mit gpt-6-luna, vorhandener ChatGPT-Anmeldung und bereinigtem technischem Auftrag; keine API-/OpenRouter-Abrechnung.

### Geändert
- Teilfehlermeldungen nennen bereits entwertete Vorgänge und den erreichten Besitz-/Modusstand; ungültige CLI-Modi liefern eine einfache Fehlermeldung mit Exit 1.
- Taskleistenstatus trennt Standard-Master und Hermes-Themen. Menüaktionen sind nicht blockierend; Modus-/Besitz-Häkchen kommen ausschließlich aus dem Aktualisierungssnapshot.
- Version 0.3.4 (`__init__.py`, `pyproject.toml`).

## [0.3.3] – 2026-10-16

### Behoben
- **Claude-Messung versteht die neue API-Form:** Der Usage-Endpunkt liefert ein leeres 5h-Fenster
  seit dem 16.10.2026 als `utilization: 0.0, resets_at: null`. Die Validierung in
  `claude_messen._fenster` und `signale._claude_filtern`/`claude_lesen` akzeptiert die fehlende
  Rücksetzzeit jetzt **nur bei 0 %** (Fenster nicht aktiv) und liest sie als „0 % / kein Reset
  geplant"; fehlende Rücksetzzeit bei Verbrauch > 0 bleibt ungültig (alte Werte bleiben stehen).
  Zuvor verwarf die Prüfung jede Antwort dieser Form und die Anzeige blieb stumm auf dem letzten
  Stand. Anzeige/Tooltip überspringen den Reset-Text, wenn keine Zeit bekannt ist. Die
  Lage-Bewertung (`rollen._bewerten`) zählt ein gemessenes 0 % ohne Rücksetzzeit als **frei**;
  fehlende Rücksetzzeit **mit** Verbrauch bleibt weiter „unbekannt".

### Geändert
- Prüfer-/Subagenten-Rolle: `gpt-6-luna` abgelöst (Input-Preis 5x), `delegation.model` =
  `deepseek/deepseek-v4.1-flash`.

## [0.3.2] – 2026-10-16

### Neu
- **Rückgabe an Codex** (`rueckgabe.py`, `dialog.py`): Bestätigungsdialog vor jedem Wechsel im Menü
  (Standard **Nein**); nach bestätigtem Wechsel auf Codex erhält jedes aktive Paar eine
  Übergabenachricht in seinen Codex-Chat (Verweis auf die laufende Übergabedatei, Grenzen-Kurzliste,
  `ACK <Kennung>`-Bitte). CLI `rueckgabe [THEMA …] [--ja] [--erneut] [--hinweis]`; ohne `--ja` nur
  Trockenlauf (schreibt und sendet nichts).
- **Kennungen** `rueckgabe-<thema>-<yyyymmddHHMMSS>-<4Hex>` (fester Aufbau, präfixfrei — der
  `ACK`-Vergleich bleibt eindeutig); `lauf_id` = Kennung; `--erneut` erzeugt immer eine frische Kennung.
- **Kopfzeilen-Übernahme:** Nur der bestätigte manuelle Weg zieht die Kopfzeile auf `ja · jetzt · HEAD`
  (die Nachricht nennt es); „nein"/fehlend/ungültig bleibt fail-closed und schreibfrei. Der Vorzustand
  steht dauerhaft in der Reservierungszeile (`… vorzustand codex <alte-id>`); die Waisen-Auflösung
  stellt ihn exakt wieder her (mit Tests) — ein spätes ACK bleibt möglich.
- **Abbruch-/Fehlerregeln:** Jeder Abbruch nach der Reservierung und vor dem Transportstart stellt den
  Vorzustand exakt wieder her (nie eine Waise); Fehler nach Prozessstart bleiben `unklar`, die
  Codex-Besitzmarke steht dann weiter. Eine aktive fremde Reservierung wird nie übernommen.
- **Startfestigkeit:** abgekoppelter Starter `leiste_starten.cmd` mit Doppelstart-Schutz und Protokoll,
  Messfehler mit Zeitstempel in `leiste.log`, Autostart-Verknüpfung (siehe README „Start und Autostart").

### Geändert
- **Menü aufgeräumt:** „Automatik Claude → Codex"-Haken entfällt (Modul bleibt, schaltbar per
  `masterwechsel automatik an|aus`); „Jetzt prüfen" ging in „Aktualisieren" auf (frisch messen,
  Zustände lesen und offene Übergaben abhaken — auch bei ausgeschalteter Automatik).
- Version 0.3.2 (`__init__.py`, `pyproject.toml`).

## [0.3.0] – 2026-10-15

### Neu
- **Automatische Übergabe Claude → Codex** (Freigabe 15.10.2026; nur Claude → Codex, nur
  eingeschaltete Paare, nur bei frischer Messung, ein Vorgang je Limitfenster, Rückweg manuell).
  Standardmäßig **aus** (`einstellungen.json`, Feld `automatik`); einschaltbar im Menüpunkt
  „Automatik Claude → Codex". Prüfung nach jeder erfolgreichen Claude-Messung (1-Minuten-Takt)
  und über „Jetzt prüfen" bzw. `masterwechsel automatik-pruefen [--trocken]`.
- **Paare** (`paare.py`, `paare.json`): Thema ↔ Codex-Chat (geprüfte, eindeutige UUID) ↔ laufende
  Übergabedatei. Das Thema wird als `re.fullmatch` geprüft (`^[a-z0-9][a-z0-9-]{0,79}$`, ein
  abschließendes Zeilenende ist damit abgelehnt); der laufende Pfad ist nicht frei, sondern exakt
  `.hermes/uebergabe/laufend/<thema>.md`. CLI `paar-setzen`, `paar-aktiv`, `paare`.
- **Sicherer Übergabepunkt:** Die laufende Übergabedatei führt in der ersten Zeile
  `Übergabebereit: ja|nein · <ISO-Zeit> · <HEAD-Kurzform>`; gelesen wird nur diese Zeile.
  Gesendet wird nur bei `ja`, Zeit ≤ 2 h und einer HEAD-Kurzform (7–12 Hexzeichen), die exakter
  Präfix des aktuellen `git rev-parse HEAD` ist. Der HEAD wird **frisch** ermittelt — vor der
  Reservierung und noch einmal nach der 30-Sekunden-Wartezeit, unmittelbar vor dem Versand; ein
  fremder Commit in dieser Zeitspanne blockiert den Versand (der HEAD-Vergleich ersetzt den
  Sekunden-Zeitvergleich).
- **Handschlag und Sperren:** Besitzdatei `<thema>.master` (`claude …` / `reserviert …` /
  `codex …`); Reservieren → 30 s warten → Kopfzeile und HEAD erneut prüfen → erst dann senden.
  Je Thema eine Betriebssystem-Sperre (`automatik-<thema>.lock`, nicht blockierend); ein belegtes
  Thema wird übersprungen. Der manuelle Rückwechsel nimmt dieselben Themensperren (blockierend,
  höchstens 5 s) in alphabetischer Reihenfolge und entwertet offene Vorgänge
  (`claude <Zeit> entwertet <ID>`); die Besitzmarke jedes Themas geht dabei wieder an Claude zurück
  (bei einem bereits bestätigten Vorgang ohne `entwertet`), damit kein Thema dauerhaft als
  „von Codex übernommen" gesperrt bleibt.
- **Vorgänge** (`vorgaenge.py`, `vorgaenge.json`): Kennung `<thema>@<Rücksetzzeit>` — je Paar und
  Limitfenster genau einer; eine vorhandene Kennung (jeder Phase) wird nie erneut gesendet. Der
  Eintrag steht dauerhaft (Phase `sende`) auf der Platte, **bevor** gesendet wird: ein Absturz
  danach führt zu keinem zweiten Versand.
- **Senden** (`codex_senden.py`): `codex.exe queue --thread <UUID> --message <Prompt>`
  (Argumentliste, keine Shell, Zeitgrenze 60 s; neueste `codex.exe` der Codex-App,
  `MASTER_SCHALTER_CODEX` hat Vorrang). Nur ein belegtes **Nicht-Starten** des Prozesses gibt den
  Besitz zurück (`fehler`); alles nach dem Start gilt konservativ als `unklar` (Codex-Besitz und
  Kennung bleiben erhalten).
- **Bestätigung** (`ack.py`): nur Assistentenantworten des Zielchats nach dem Sendezeitpunkt, die
  mit `ACK <kennung>` beginnen (Rollout-Dateien `rollout-*-<UUID>.jsonl` im Sitzungsordner). Der
  eigene Prompt zählt nie. Bestätigt wird **fail-closed** und atomar: Besitz (`<thema>.master`
  genau `codex <id>`), die frische Phase **und** das Setzen des globalen Masters liegen in **einem**
  gesperrten Abschnitt (Themensperre zuerst, darin kurz die globale Zustandssperre) — ohne
  prüfbares Repo oder bei inzwischen entwertetem Vorgang gibt es keine Bestätigung. Ein Rückwechsel
  läuft damit entweder komplett davor (dann keine Bestätigung) oder komplett danach (dann bleibt er
  der letzte Wille) und wird nie nachträglich auf Codex überschrieben. Reihenfolge im Teilschritt
  bewusst „globaler Master, dann Phase": bricht der Lauf dazwischen ab, bleibt der Vorgang offen
  und der nächste Lauf bestätigt erneut (idempotent) — nichts blockiert. Ohne ACK nach 15 Minuten
  „keine Bestätigung"; ein ACK auf einen entwerteten Vorgang bleibt wirkungslos.
- **Gültige Messwerte:** Der Codex-Verbrauch zählt nur von 0 bis 100. Negative, über 100 liegende,
  nicht endliche oder fehlende Werte gelten als **unbekannt** (`signale._fenster`/`_nur_zahlen`)
  und werden auch in der Entscheidung zurückgewiesen (`automatik._gueltiges_fenster`) — sie lösen
  nie einen Versand aus.
- **Paketoption** (`uebergabe.py`): `paket_bauen(..., *, plaene=True, minimal=False)` —
  rückwärtskompatibel. Der Automatikweg nutzt `plaene=False, minimal=True`: `_plaene` wird nicht
  aufgerufen, und der Abschnitt „Stand" enthält nur Zeitpunkt, HEAD, Anzahl Commits und die
  **Anzahl** uncommitteter Pfade — keine Betreffzeilen, keine Dateinamen. Der Prompt enthält nur
  Pfade, Kennung und Zahlen, keinen Dateiinhalt.
- **Datenordner verschoben:** `%USERPROFILE%\.master-schalter\` statt
  `%LOCALAPPDATA%\master-schalter\`. Claude- und Codex-App sind MSIX-Pakete; ihre Kindprozesse
  wurden je nach Starter in `AppData\Local\Packages\…` umgeleitet, sodass drei getrennte Zustände
  entstanden (Autostart, Codex-Start, Claude-CLI). `MASTER_SCHALTER_DATEN` bleibt Vorrang; alte
  Dateien werden nicht übernommen (Werte werden neu gemessen, Master neu gesetzt).

### Grenzen
- Der **Rückweg Codex → Claude bleibt manuell** (der Claude-Zustellweg ist unbelegt).
- Die Automatik arbeitet mit **beobachteten frischen Momentaufnahmen**; das ersetzt keine
  garantierte Quotenreservierung. Ephemere Codex-Läufe hinterlassen keine Rollouts — das
  Ausbleiben neuer Ereignisse ist deshalb ausdrücklich kein Nutzungsbeleg.
- Live-Abnahme (Probe an genau ein Paar, danach Automatik mit Schwelle) steht noch aus.

## [0.2.1] – 2026-10-15

### Neu
- **Hermes als dritter, manuell wählbarer Master** (Lage 3 der Kaskaden-Matrix: Thinker = Hermes/DeepSeek).
  `master.json` akzeptiert `"hermes"`, das Menü „Master wechseln" und `masterwechsel wechsel hermes` bieten
  ihn an; Tooltip und Statuszeile zeigen dann „M Hermes …“. Hermes hat kein eigenes Kontingent: kein
  Balken, kein weißer Punkt; `wechsel` legt wie gewohnt zuerst das Übergabepaket ab
  (`…_masterwechsel-<von>-hermes.md`).
- README-Fahrplan an die Release-Tabelle des v0.3-Plans angeglichen (Automatik = v0.3.0,
  Hermes-Sitzungen = v0.3.1, Rückweg = v0.4.0).

## [0.2.0] – 2026-10-14

### Neu
- README dokumentiert den optionalen Windows-Benutzer-Autostart über eine eigene
  `shell:startup`-Verknüpfung mit `pythonw.exe`, Startargumenten und Arbeitsordner.
  v0.2 bringt dafür kein eigenes Autostart-Menü oder Einrichtungs-Skript mit.
- Claude-Kontingent über `masterwechsel claude-messen` und im Taskleisten-Worker messen; beim
  Start, nach „Aktualisieren" und standardmäßig jede Minute (einstellbar über
  `claude_takt_min`, 1–60 Minuten). HTTP 429 löst bis zum nächsten Erfolg einen 5-Minuten-Takt aus.
- Der OAuth-Adapter liest den Access-Token zur Laufzeit aus `~/.claude/.credentials.json`, verwendet
  keinen Refresh-Token und speichert/protokolliert/zeigt den Token nicht. Beide Messfenster werden
  vor dem atomaren Schreiben auf vollständige, endliche Prozentwerte und Rücksetzzeiten geprüft.
- Aktiven Master, Wechselzeit, Kaskaden-Lage und Besetzung anzeigen.
- Masterwechsel per CLI oder Taskleistenmenü; das technische Übergabepaket wird vor dem
  Zustandswechsel geschrieben. Fehler beim Sperren oder Paketbau lassen den Zustand unverändert.
- Übergabepakete enthalten nur technische Metadaten und Pläne mit der expliziten Einordnung
  „technisch"; Datei- und Chat-Inhalte werden nicht übernommen.
- Schwelle im Taskleistenmenü auf 80, 90, 95, 97 oder 100 % einstellen.

### Grenzen
- v0.2 startet oder beschreibt keinen Chat. Der neue Master liest das Paket, wenn Sebastian ihn
  darauf hinweist.
- Die Claude-Usage-API ist eine inoffizielle Schnittstelle. Bei HTTP 401 oder abgelaufener
  Anmeldung erscheint eine generische Meldung; der bisherige Messwert bleibt erhalten.
- Nach einem Reset zeigen Tooltip und Balken bis zur nächsten Messung weiterhin 0 %; die Lage
  behandelt den Wert als unbekannt. Die Anzeige wird in v0.1.1 korrigiert.

## [0.1.0] – 2026-10-14

### Neu
- Taskleisten-Symbol (`master_schalter.leiste`) mit zwei Balken für Claude Code und Codex,
  Tooltip, Benachrichtigung per Linksklick und Menü per Rechtsklick.
- Kontingente lesen (`signale.py`): Codex aus den lokalen Sitzungsdateien (nur Zahlen, auch im
  Zwischenspeicher; inkrementell; gekürzte oder neu geschriebene Dateien werden an Größe bzw.
  geändertem Dateianfang (erste 4 KB) erkannt und von vorn gelesen; neuester Eintrag über alle
  Dateien — die Änderungszeit jeder Datei dient als Obergrenze, damit ältere Dateien gar nicht
  erst gelesen werden müssen), Claude aus der Statuszeilen-Datei.
- Befehlszeile `masterwechsel`: `status`, `statuszeile`, `claude-kontingent`.
- Schwelle für Rotfärbung einstellbar (`einstellungen.json`, Standard 97 %).

### Bekannte Grenzen
- Die Claude-Desktop-App führt die Statuszeile nicht aus; Claude-Werte kommen dann nur über
  `masterwechsel claude-kontingent` oder Claude Code im Terminal.
- Codex-Werte sind so frisch wie die letzte Codex-Sitzung (Prüfläufe mit `--ephemeral`
  schreiben keine).
