# Ergebnisprüfung Runde 3 (Hermes): Websuche mit Namensverbot

Prüfer: Hermes (deepseek/deepseek-v4.1-flash, frische Sitzung), 14.10.2026, 18:0x–18:4x.
Prüfauftrag: `.hermes/plans/2026-10-14_websuche-namensverbot-ergebnis.md` (Prüffragen 1–6),
Planfassung 7.

Prüfgegenstand: die beiden **noch nicht geprüften** Behebungsläufe nach meiner Runde 2
(Befund 1: Obergrenze des Suchtexts, Befund 2: leerer Bestand) und nach Codex Runde 3
(`null`-Datei):

- `a82549b` — „Namensdatei mit Inhalt null sperrt die Websuche“ (`werkzeuge._json_streng`)
- `28e37b9` — „Suchtext des Modells begrenzt, leere Namensliste sperrt“
  (`web_suche.MAX_ANFRAGE_MODELL`, `werkzeuge.bekannte_namen_streng`, `llm_service:895`)

Beide Commits liegen lokal, der Kopf ist `28e37b9`.

## Urteil

**URTEIL: FREI** für den Code — die drei offenen Befunde (meine zwei aus Runde 2, Codex' R3)
sind **wirksam** behoben, jede Behebung ist mit eigenen Sonden nachgemessen. Dazu drei
**Hinweise zur Doku** (kein Sperrgrund, reine Textnachträge) und ein offener Punkt, der
kein Codefehler ist.

## Was gemessen ist (eigene Sonde, Wegwerf-Quellen, nur erfundene Namen)

Sonde gegen die **echten** Funktionen `werkzeuge.bekannte_namen_streng`,
`web_suche.suchen`, `websuche_schutz`; Dateipfade auf einen Tempordner umgebogen
(`gruppen_quiz._schreibpfad`/`_lesepfad`, `gesichter_service.KATALOG_DATEI`),
LLM-Aufruf durch eine Attrappe ersetzt, die Aufrufe zählt. Kein Netz-, Modell- oder
Vision-Aufruf; keine echten Personen-, Kontakt- oder Bilddaten gelesen.

| Fall | Messwert |
|---|---|
| alle Namensquellen fehlen | `bekannte_namen_streng()` → `None` (Log: „Namensliste leer“) |
| alle Dateien vorhanden, aber leer/formal gültig | `None` |
| **eine** gültige Person | Bestand `{'teile': 1, 'volle': 0}` (kein Falsch-Sperren) |
| `personen_bestaetigt/vorgaben/profile.json`, `gesichter_katalog.json` je mit Inhalt `null` | je `None` (viermal geprüft) |
| Kontaktdatei `whatsapp_zuordnung.json` mit `null` | `None` |
| leerer Bestand, Suche „Was macht Ida Beispiel?“ | abgelehnt, **0** Netzaufrufe |
| gültiger Bestand, „Wetter Hamburg morgen“ | gesucht, **1** Netzaufruf |
| gültiger Bestand, Suche mit Namen | abgelehnt, **0** Netzaufrufe |
| **3.479 Zeichen** Modelltext über den Werkzeugweg | nicht gesucht („zu lang (über 200 Zeichen)“), **0** Netzaufrufe |
| genau **200** Zeichen | gesucht, 1 Netzaufruf |
| **201** Zeichen | nicht gesucht, 0 Netzaufrufe (Text: „Suchanfrage zu lang …“) |
| **3.479 Zeichen** über den eigenen Satz (`manual`, ohne Grenze) | gesucht, 1 Netzaufruf |

Grenze im Code: `web_suche.MAX_ANFRAGE_MODELL = 200`; der Werkzeugweg
`llm_service.py:895` übergibt sie — gemessen: **beide** Aufrufstellen von
`suchen` sind damit bekannt (`llm_service.py:895` Modellweg mit Grenze,
`router/chat.py:1766` Sebastians eigener Satz ohne Grenze, wie im Plan gewollt).
Ein dritter Weg existiert nicht (Zählung im Backend: 2 Aufrufe + 1 Docstring).

Unverändert gilt (in dieser Runde gegengeprüft, nicht angefasst): der Hauptaufruf setzt
weder das Plugin `web` noch `openrouter:web_search` (`llm_service._extra_body`), der
Suchaufruf trägt genau eine Nachricht, und Freigaben kommen nur aus
`request.message`.

## Hinweise (kein Sperrgrund)

1. **`docs/spec-tool-use-v1.md` hinkt nach.** Der Abschnitt „Websuche mit Namensverbot“
   (Zeile 82 ff.) nennt als Sperrfall nur „Liste nicht lesbar (`None`) → keine Suche“.
   Die beiden neuen Regeln fehlen dort: **leerer Bestand sperrt** und
   **Modell-Suchtexte höchstens 200 Zeichen** (`MAX_ANFRAGE_MODELL`).
2. **`CLAUDE.md` Zeile 125 hinkt weiter nach.** Dort steht „`test_websuche_schutz.py` neu
   (63)“ und „Offen: Ergebnisprüfung Codex, Messung der Namensliste am Handy (Hermes)“ —
   gemessen sind **96** Tests in der Datei (frisch gesammelt und gelaufen), und die
   Ergebnisprüfungen von Codex (R1–R4) und Hermes (R2) liegen vor.
3. **Changelog-Zahl stimmt nicht.** `docs/changelog-2026-10-14-websuche-namensverbot.md`
   Zeile 150 sagt „hat jetzt 97 Tests“ — frisch gemessen und gelaufen: **96 passed**.

## Offen, aber kein Codefehler

- **Die Handymessung der Namensliste** (Prüfkriterium Fassung 7) ist lesend weiterhin nicht
  zu erhalten: das Termux-Heim ist per `adb shell` nicht sichtbar (`HOME=/`), `GET
  /api/gruppen/stand` verlangt den Schlüssel aus der Handy-`.env` (die ich nicht öffne), ein
  Code-Lauf im Termux wäre ein Geräteeingriff.
  **Die neue Regel entschärft den Fall:** Fehlen am Handy die Namensdateien, ist der Bestand
  leer → **keine Websuche**, statt „Suche ohne Schutz“. Der offene Punkt ist damit „keine
  Websuche am Handy“, nicht „ungeschützte Suche“. Der Papa-Zähler in `status.json` bleibt
  unangetastet (unverändert 6.336).
- Ein **kurzer** Modelltext (≤ 200 Zeichen) mit einem privaten Namen, den keine Quelle kennt,
  passiert weiterhin — das ist die bekannte, im Plan angenommene Grenze der Namensliste
  (Hinweis schon in Runde 1/2), nicht Gegenstand dieser Behebung.

## Belege dieses Laufs

- Eigene Sonde (`sonde_r3.py`, Wegwerfordner, Attrappen; Zahlen oben) — kein Netz, kein Modell,
  kein Bild.
- Testdatei `backend/tests/test_websuche_schutz.py`: **96 passed** (80,75 s).
- Voller Prüfbefehl `cd backend && .venv/Scripts/python -m pytest tests/ -q`: siehe Commit
  dieses Dokuments (Exit 0 gefordert, sonst kein Commit).
- Damit: nichts geändert außer diesem Dokument; keine fremde Datei angefasst, nichts gelöscht,
  `status.json` unverändert, kein pCloud-Zugriff, keine Geräteeingriffe (das angeschlossene
  Handy wurde nicht benutzt).
